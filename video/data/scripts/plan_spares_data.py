"""Page data for plan.html, plan-schedule.html, spares.html and spares-leadtime.html.

Everything is computed here from (a) the fork results in video/data/forks/ (real CRN-paired runs of the data
layer's fork service, belief mode only) and (b) the consumer fleet tree read strictly as of 2026-06-22 06:00 IST
through assure_load (contract hash checked per file, scoped dedupe by (tail_no, record_id), never
_restricted_labels/).

Spares / lead time
  * Supply demands, tail-attributed only. Demand numbers collide across the per-aircraft worlds and most SUPPLY_DEMAND
    rows (all base top-ups and most closures) carry no tail_no, so a pooled fleet lead-time distribution is not
    reliable. A closure is linked to an aircraft's demand only when it carries the same tail_no, demand number and
    open time (n = 9). Aircraft demands without a linked closure are classified: grounding (tail NMCS, job
    AWAITING_PARTS) or stale (job already CLOSED).
  * Lead time is therefore the data layer's documented AOG model (A-W1.8-10): log-normal fitted by least squares on
    the probit scale to the CAG 24/2017 IL-76 AOG timeliness bins, x Tejas OEM-support factor 0.3 x class factor
    (catalogue lead_mult) x AOG priority 1.0; parameters read from the registry YAML. Survival, quantiles and the
    expected remaining wait E[T - a | T > a] are closed-form; the 9 linked fills are shown as evidence.
  * Tyres: landings since the last tyre INSTALL (COMPONENT_LIFE) from SORTIE records; 8-landing life is the
    catalogue life quoted in every tyre job text ("HI-TIME (8 LDG)"). Chutes: USAGE.CHUTE_STREAMINGS counter
    since the last brake-chute replacement job; 45-streaming life from the job text. The fitted chute's prior
    life is not on record, so this is a lower bound.
Plan
  * S1/S2/S3 paired differences straight from results.json (belief mode); per-member mc pairs from
    scenario_S1.json; two-sided paired-t p-values and Holm adjustment computed here.
  * Schedule: SRV-L1 cadence (observed 16-day interval, median duration) projected from each tail's last
    SRV-L1; tyre changes projected from landings left at the tail's last-30-day landing rate; depot / grounded
    states from AVAILABILITY_STATE; 08:00 orders from the decision board (decision_screens_asof_20260622.json).

Run: <venv>/bin/python video/data/scripts/plan_spares_data.py
"""
import sys, json, math, re
sys.path.insert(0, "/Users/abishaikc/Phalanx-Solution/video/data/scripts")
from assure_load import *  # noqa: F401,F403  (rd, asof, SNAP, IST, OUT, pd, np)

FK = OUT + "forks/"
RES = json.load(open(FK + "results.json"))
DEC = json.load(open(OUT + "decision_screens_asof_20260622.json"))
EPOCH = pd.Timestamp("2026-06-22 08:00", tz=IST)
H_END = EPOCH + pd.Timedelta(days=30)
R = {"asof": "2026-06-22 06:00 IST", "epoch": "2026-06-22 08:00 IST"}


# ============================================================ statistics helpers
def betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > FPMIN else FPMIN); h = d
    for m_ in range(1, MAXIT + 1):
        m2 = 2 * m_
        aa = m_ * (b - m_) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = FPMIN if abs(d) < FPMIN else d
        c = 1 + aa / c; c = FPMIN if abs(c) < FPMIN else c
        d = 1 / d; h *= d * c
        aa = -(a + m_) * (qab + m_) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = FPMIN if abs(d) < FPMIN else d
        c = 1 + aa / c; c = FPMIN if abs(c) < FPMIN else c
        d = 1 / d; de = d * c; h *= de
        if abs(de - 1) < EPS:
            break
    return h


def betai(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    return bt * betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * betacf(b, a, 1 - x) / b


def p_paired(mean, sd, n):
    """Two-sided paired-t p-value."""
    if sd == 0:
        return 1.0 if mean == 0 else 0.0
    t = mean / (sd / math.sqrt(n)); df = n - 1
    return betai(df / 2, 0.5, df / (df + t * t))


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i]); m_ = len(ps); adj = [0.0] * m_; run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m_ - r) * ps[i])); adj[i] = run
    return adj


Phi = np.vectorize(lambda z: 0.5 * math.erfc(-z / math.sqrt(2)))


def nelder_mead(f, x0, step=0.3, it=400, tol=1e-9):
    n = len(x0); pts = [np.array(x0, float)] + [np.array(x0, float) + step * np.eye(n)[i] for i in range(n)]
    vals = [f(p) for p in pts]
    for _ in range(it):
        o = np.argsort(vals); pts = [pts[i] for i in o]; vals = [vals[i] for i in o]
        if abs(vals[-1] - vals[0]) < tol: break
        c = np.mean(pts[:-1], axis=0); xr = c + (c - pts[-1]); fr = f(xr)
        if fr < vals[0]:
            xe = c + 2 * (c - pts[-1]); fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = c + 0.5 * (pts[-1] - c); fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0]] + [pts[0] + 0.5 * (p - pts[0]) for p in pts[1:]]; vals = [vals[0]] + [f(p) for p in pts[1:]]
    return pts[int(np.argmin(vals))]


def lognorm_fit(T, E):
    lt = np.log(np.clip(T, 0.01, None))
    def nll(p):
        mu, ls = p; s = math.exp(ls); z = (lt - mu) / s
        ll_e = -0.5 * z[E == 1] ** 2 - math.log(s) - lt[E == 1] - 0.5 * math.log(2 * math.pi)
        ll_c = np.log(np.clip(1 - Phi(z[E == 0]), 1e-300, None))
        return -(ll_e.sum() + ll_c.sum())
    mu, ls = nelder_mead(nll, [float(np.median(lt)), math.log(max(np.std(lt), .3))])
    return float(mu), float(math.exp(ls))


def mrl(mu, s, a):
    """E[T - a | T > a] for a log-normal."""
    if a <= 0:
        return math.exp(mu + s * s / 2)
    la = math.log(a)
    num = math.exp(mu + s * s / 2) * float(Phi((mu + s * s - la) / s)); den = float(Phi((mu - la) / s))
    return num / den - a


def km(T, E):
    T = np.asarray(T, float); E = np.asarray(E, int)
    times = np.unique(T[E == 1]); S = 1.0; gw = 0.0; out = [[0.0, 1.0, 1.0, 1.0, len(T)]]
    for t in times:
        n = int((T >= t).sum()); d = int(((T == t) & (E == 1)).sum())
        S *= 1 - d / n
        if n > d: gw += d / (n * (n - d))
        if 0 < S < 1:
            se = math.sqrt(gw) / abs(math.log(S)); lo = S ** math.exp(1.96 * se); hi = S ** math.exp(-1.96 * se)
        else:
            lo = hi = S
        out.append([float(t), S, lo, hi, n])
    return out


def km_q(step, p):
    """Smallest t with S(t) <= p (None if never reached)."""
    for t, s, *_ in step:
        if s <= p:
            return t
    return None


def km_at(step, t):
    s = 1.0
    for tt, ss, *_ in step:
        if tt <= t: s = ss
        else: break
    return s


# ============================================================ records
m = asof(rd("maint.records")); u = asof(rd("usage.counters"))
so = m[m.record_type == "SORTIE"].sort_values("t_event")
jobs = m[m.record_type.isin(["DEFECT_WO", "INSPECTION"])].sort_values(["record_version", "t_ingest"]).drop_duplicates(["tail_no", "record_key"], keep="last")
jst = {(r.tail_no, r.job_no): r for r in jobs.itertuples()}
TAILS = [f"TJ10{i}" for i in range(1, 9)]

# ------------------------------------------------------------ supply demands (tail-attributed only)
# Demand numbers collide across the per-aircraft worlds and most closure (v1) rows carry no tail_no, so a closure is
# linked to an aircraft's demand only when it carries the same tail_no, demand number and open time. Tail-less rows
# (base top-ups and unlinked closures) are not attributable to an aircraft and are not used here.
d = m[m.record_type == "SUPPLY_DEMAND"].copy()
v0 = d[(d.record_version == 0) & d.tail_no.notna()].copy(); v1 = d[(d.record_version == 1) & d.tail_no.notna()].copy()
v1["T"] = (v1.t_close_dt - v1.t_open_dt).dt.total_seconds() / 86400
v1["part"] = v1.part_no.str.replace("SYN-PN-", "")
linked_keys = set(zip(v1.tail_no, v1.record_key, v1.t_open))
op = v0[[(a, k, t) not in linked_keys for a, k, t in zip(v0.tail_no, v0.record_key, v0.t_open)]].copy()
op["age"] = (SNAP - op.t_open_dt).dt.total_seconds() / 86400
op["part"] = op.part_no.str.replace("SYN-PN-", "")
av = m[m.record_type == "AVAILABILITY_STATE"].sort_values("t_event").groupby("tail_no").tail(1).set_index("tail_no")
state = {t: (av.loc[t, "availability_state"], av.loc[t, "t_event_dt"]) for t in av.index}


def classify(r):
    j = jst.get((r.tail_no, r.job_no))
    if j is not None and j.status == "CLOSED":
        return "stale"
    if state.get(r.tail_no, ("",))[0] == "NMCS" and j is not None and j.status == "AWAITING_PARTS":
        return "grounding"
    return "open_job"


op["cls"] = [classify(r) for r in op.itertuples()]
cls_counts = op.cls.value_counts().to_dict()
grounding = op[op.cls == "grounding"].iloc[0]
age_tj108 = float(grounding.age)
print("tail-attributed demands", len(v0), "linked closures", len(v1), "open", cls_counts)

# ------------------------------------------------------------ lead-time model (data layer's documented prior)
# M18 supply: wholesale lead time log-normal fitted (least squares, probit scale) to the CAG 24/2017 IL-76 AOG
# timeliness bins, x Tejas OEM-support factor 0.3 x class lead_mult x priority (AOG 1.0). Values read from the
# data layer's parameter registry (configs/tejas/params/M18.yaml, M18/catalogue.yaml); A-W1.8-10.
CFG = "/Users/abishaikc/Downloads/phalanx_data_layer_preview/code/configs/tejas/params/"
_m18 = open(CFG + "M18.yaml").read(); _cat = open(CFG + "M18/catalogue.yaml").read()
def _val(key):  # "key:\n  value: ..." in the supply block of M18.yaml (no YAML library in this environment)
    blk = _m18[_m18.index("\n  supply:"):]
    i = blk.index("\n    " + key + ":"); seg = blk[i:i + 600]
    v = re.search(r"value: (\[[^\]]*\]|[0-9.]+)", seg).group(1)
    sw = re.search(r"sweep: (\[[^\]]*\])", seg)
    return json.loads(v), (json.loads(sw.group(1)) if sw else None)
edges = [float(x) for x in _val("aog_bin_upper_days")[0]]; shares = [float(x) for x in _val("aog_bin_share")[0]]
factor, factor_sweep = _val("tejas_supply_factor"); factor = float(factor); prio = [float(x) for x in _val("priority_mult")[0]]
def _lm(cls):
    i = _cat.index("\n  " + cls + ":"); return float(re.search(r"lead_mult: ([0-9.]+)", _cat[i:i + 2000]).group(1))
lead_mult = {k: _lm(k) for k in ("TYRE", "CHUTE", "HYDP")}


def probit(p):
    lo_, hi_ = -10.0, 10.0
    for _ in range(200):
        mid = (lo_ + hi_) / 2
        if float(Phi(mid)) < p: lo_ = mid
        else: hi_ = mid
    return (lo_ + hi_) / 2


cum = np.cumsum(shares[:-1]) / sum(shares); z = np.array([probit(c) for c in cum]); x = np.log(edges)
sig = float(((z - z.mean()) * (x - x.mean())).sum() / ((z - z.mean()) ** 2).sum()); mu0 = float(x.mean() - sig * z.mean())
def model(cls):
    mu_ = mu0 + math.log(factor * lead_mult[cls] * prio[0])
    return mu_, sig
def S_ln(mu_, s_, t):
    return 1 - float(Phi((math.log(t) - mu_) / s_)) if t > 0 else 1.0
def q_ln(mu_, s_, p):
    return math.exp(mu_ + s_ * probit(p))
mc_, sc_ = model("CHUTE"); mt_, st_ = model("TYRE")
ages = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120]
grid_t = [round(0.5 * 1.04 ** i, 3) for i in range(0, 160)]
grid_t = [t for t in grid_t if t <= 200] + [200]
linked = [dict(tail=r.tail_no, part=r.part, days=round(float(r.T), 2)) for r in v1.sort_values("T").itertuples()]
R["leadtime"] = dict(
    basis="model", model=dict(source="CAG 24/2017 IL-76 AOG bins, log-normal (probit least squares) x Tejas factor x class factor; AOG priority",
                              raw_median=round(math.exp(mu0), 1), sigma=round(sig, 3), factor=factor, lead_mult=lead_mult,
                              factor_sweep=factor_sweep),
    chute=dict(median=round(q_ln(mc_, sc_, .5), 1), mean=round(math.exp(mc_ + sc_ ** 2 / 2), 1), p90=round(q_ln(mc_, sc_, .9), 1),
               s30=round(S_ln(mc_, sc_, 30), 3), s80=round(S_ln(mc_, sc_, age_tj108), 3), s180=round(S_ln(mc_, sc_, 180), 3),
               curve=[[t, round(S_ln(mc_, sc_, t), 4)] for t in grid_t], mrl=[[a, round(mrl(mc_, sc_, a), 1)] for a in ages]),
    tyre=dict(median=round(q_ln(mt_, st_, .5), 1), mean=round(math.exp(mt_ + st_ ** 2 / 2), 1), p90=round(q_ln(mt_, st_, .9), 1),
              curve=[[t, round(S_ln(mt_, st_, t), 4)] for t in grid_t]),
    linked=linked, linked_n=len(linked), linked_by_part=v1.part.value_counts().to_dict(),
    open_linked=int(len(op)), open_by_class=cls_counts,
    tj108=dict(demand=grounding.record_key, job=grounding.job_no, part=grounding.part, priority=grounding.priority,
               opened=grounding.t_open_dt.strftime("%d %b %H:%M"), age_d=round(age_tj108, 1),
               mrl=round(mrl(mc_, sc_, age_tj108), 1), s_at_age=round(S_ln(mc_, sc_, age_tj108), 3),
               linked_chute_max=round(float(v1[v1.part == "CHUTE"]["T"].max()), 1), linked_chutes=int((v1.part == "CHUTE").sum())),
    stale=[dict(tail=r.tail_no, demand=r.record_key, part=r.part, job=r.job_no, age=round(r.age, 1)) for r in op[op.cls == "stale"].sort_values("t_open").itertuples()],
)
LT = R["leadtime"]
print("model raw median", LT["model"]["raw_median"], "sigma", LT["model"]["sigma"], "chute", {k: LT["chute"][k] for k in ("median", "mean", "p90", "s30", "s80", "s180")},
      "tyre", {k: LT["tyre"][k] for k in ("median", "mean", "p90")}, "TJ108 mrl", LT["tj108"]["mrl"], "mrl", LT["chute"]["mrl"])
print("linked", linked)

# ------------------------------------------------------------ consumables
ty = m[(m.record_type == "COMPONENT_LIFE") & (m.part_no == "SYN-PN-TYRE") & (m.install_action == "INSTALL")]
cs = u[u.param_id == "USAGE.CHUTE_STREAMINGS"].sort_values("t_update")
d30 = SNAP - pd.Timedelta(days=30)
chute_jobs = jobs[jobs.discrepancy_text.fillna("").str.contains("PARACH", case=False)]
cons = []
for t in TAILS:
    last = ty[ty.tail_no == t].t_event_dt.max()
    st_ = so[so.tail_no == t]
    used = int(st_[st_.t_event_dt > last].landings.sum())
    rate = float(st_[st_.t_event_dt > d30].landings.sum()) / 30
    cj = chute_jobs[(chute_jobs.tail_no == t) & (chute_jobs.status == "CLOSED")]
    c_last = cj.t_close_dt.max() if len(cj) else pd.Timestamp("2026-01-05", tz=IST)
    streams = int(cs[(cs.tail_no == t) & (cs.t_update_dt > c_last)].increment_eu.sum())
    srate = float(cs[(cs.tail_no == t) & (cs.t_update_dt > d30)].increment_eu.sum()) / 30
    cons.append(dict(tail=t, state=state[t][0], tyre_used=used, tyre_life=8, last_tyre=last.strftime("%d %b"),
                     ldg_per_day=round(rate, 2), days_to_limit=(round((8 - used) / rate, 1) if rate > 0 else None),
                     chute_streams=streams, chute_life=45, last_chute=c_last.strftime("%d %b"), streams_per_day=round(srate, 2)))
R["consumables"] = cons
print("tyres", [(c["tail"], c["tyre_used"], c["ldg_per_day"], c["days_to_limit"], c["chute_streams"]) for c in cons])
fly = [c for c in cons if c["state"] not in ("NMCS", "NMCD")]
ldg_rate = float(np.median([c["ldg_per_day"] for c in fly])); str_rate = float(np.median([c["streams_per_day"] for c in fly]))
# useful lead time = warning horizon - lead time (model median and 90th percentile, AOG priority)
R["useful"] = dict(
    ldg_per_day=round(ldg_rate, 2), streams_per_day=round(str_rate, 2),
    tyre=dict(horizon=round(8 / ldg_rate, 1), lead_med=LT["tyre"]["median"], lead_p90=LT["tyre"]["p90"]),
    chute=dict(horizon=round(45 / str_rate, 1), lead_med=LT["chute"]["median"], lead_p90=LT["chute"]["p90"]),
    hydp=dict(horizon=None, lead_med=LT["chute"]["median"], lead_p90=LT["chute"]["p90"], confirmed_failures=0),
)
for k in ("tyre", "chute"):
    R["useful"][k]["useful_med"] = round(R["useful"][k]["horizon"] - R["useful"][k]["lead_med"], 1)
    R["useful"][k]["useful_p90"] = round(R["useful"][k]["horizon"] - R["useful"][k]["lead_p90"], 1)
print("useful", R["useful"])

# ============================================================ forks
def kp(node, k, mode="belief"):
    v = node["results"][mode]["kpis"][k]
    f = lambda x: {"m": x["mean"], "lo": x["ci_low"], "hi": x["ci_high"]}
    pdiff = v["paired_difference"]
    return dict(sq=f(v["status_quo"]), tr=f(v["treatment"]), d=f(pdiff), sd=pdiff["sd"], n=pdiff["n"],
                p=p_paired(pdiff["mean"], pdiff["sd"], pdiff["n"]))


S1n, S2n, S3n, S2L = RES["scenarios"]["S1"], RES["scenarios"]["S2"], RES["scenarios"]["S3"], RES["supplementary"]["S2_h400"]
KS = ["mc", "fmc", "nmcs", "nmcm", "aog_days", "man_hours", "flying_task", "flown_fh", "sorties", "cost"]
s1 = {k: kp(S1n, k) for k in KS + ["in_flight_failures"]}
adj = holm([s1[k]["p"] for k in KS])
for k, a in zip(KS, adj): s1[k]["p_holm"] = a
s1["in_flight_failures"]["p_holm"] = s1["in_flight_failures"]["p"]
mem = json.load(open(FK + "scenario_S1.json"))["modes"]["belief"]["members"]
pairs = [dict(m=x["member"], sq=x["status_quo"]["mc"], tr=x["treatment"]["mc"], ws=x["wall_s"]["status_quo"], wt=x["wall_s"]["treatment"]) for x in mem]
ws = S1n["results"]["belief"]["wall_s"]
R["S1"] = dict(tail="TJ107", snapshot=S1n["snapshot_id"], window=S1n["window"], n=S1n["results"]["belief"]["n_pairs"], kpis=s1, pairs=pairs,
               wall=ws, removals=S1n["results"]["belief"]["derived"]["removals"]["paired_difference"],
               orders=[dict(action=o["action"], params=o["parameters"], issuer=o["issuer_kind"]) for o in S1n["orders"]],
               status=S1n["results"]["belief"]["order_final_status_counts"],
               ts_done=json.load(open(FK + "scenario_S1.json"))["modes"]["belief"]["members"][0]["order_status"]["phx-demo:S1:20260622T023000Z:troubleshoot"][-1]["t_status_ist"])
neg = sum(1 for p in pairs if p["tr"] - p["sq"] < 0); zero = sum(1 for p in pairs if abs(p["tr"] - p["sq"]) < 1e-12)
R["S1"]["mc_pairs_better"] = sum(1 for p in pairs if p["tr"] - p["sq"] > 1e-12); R["S1"]["mc_pairs_worse"] = neg; R["S1"]["mc_pairs_equal"] = zero
print("S1 holm", {k: (round(s1[k]["d"]["m"], 3), "%.1e" % s1[k]["p"], "%.1e" % s1[k]["p_holm"]) for k in s1})
print("S1 pairs better/worse/equal", R["S1"]["mc_pairs_better"], neg, zero)

s2 = {k: kp(S2n, k) for k in ["aog_days", "nmcs", "mc", "flown_fh", "cost", "man_hours"]}
s2L = {k: kp(S2L, k) for k in ["aog_days", "nmcs", "mc", "flown_fh", "cost", "man_hours", "in_flight_failures"]}
ex = S2L["results"]["belief"]["nmcs_exit_per_member"]
sq_exit = sorted(set(x["status_quo"] for x in ex)); tr_exit = sorted(set(x["treatment"] for x in ex))
dd = (pd.Timestamp(sq_exit[0][:16], tz=IST) - pd.Timestamp(tr_exit[0][:16], tz=IST)).total_seconds() / 86400
R["S2"] = dict(tail="TJ108", snapshot=S2n["snapshot_id"], n=S2n["results"]["belief"]["n_pairs"], kpis30=s2, kpis400=s2L,
               n400=S2L["results"]["belief"]["n_pairs"], exit_sq=sq_exit, exit_tr=tr_exit, sooner_days=round(dd, 1),
               wall=S2n["results"]["belief"]["wall_s"], wall400=S2L["results"]["belief"]["wall_s"],
               demand=S2n["decision_context"]["selected_demand"], status=S2n["results"]["belief"]["order_final_status_counts"])
tj = S3n["results"]["belief"]["tyre_jobs_per_member"]
R["S3"] = dict(tail="TJ105", snapshot=S3n["snapshot_id"], n=S3n["results"]["belief"]["n_pairs"],
               kpis={k: kp(S3n, k) for k in ["nmcs", "aog_days", "mc", "flown_fh", "cost"]},
               tyre_jobs_waited=sum(x["status_quo"]["tyre_jobs_awaiting_parts"] + x["treatment"]["tyre_jobs_awaiting_parts"] for x in tj),
               tyre_jobs_opened_sq=sum(x["status_quo"]["tyre_jobs_opened"] for x in tj),
               status=S3n["results"]["belief"]["order_final_status_counts"], wall=S3n["results"]["belief"]["wall_s"],
               landings=S3n["decision_context"]["landings_since_last_tyre_install"])
print("S2", R["S2"]["sooner_days"], sq_exit, tr_exit, "S3 waited", R["S3"]["tyre_jobs_waited"], R["S3"]["status"])
tot_branches = 0; tot_s = 0.0
for node in (S1n, S2n, S3n):
    w = node["results"]["belief"]["wall_s"]; tot_branches += 2 * node["results"]["belief"]["n_pairs"]; tot_s += w["mode_total"]
R["compute"] = dict(belief_branches=tot_branches, belief_total_s=round(tot_s, 1), s1_branch_mean=ws["per_branch_mean"],
                    s1_branch_max=ws["per_branch_max"], s1_pair_mean=ws["per_pair_mean"], s1_total=ws["mode_total"])

# ============================================================ schedule (30-day horizon, as known at the snapshot)
insp = m[m.record_type == "INSPECTION"].sort_values(["record_version", "t_ingest"]).drop_duplicates(["tail_no", "record_key"], keep="last")
l1 = insp[insp.inspection_type == "SRV-L1"].sort_values("t_open")
ivs, durs = [], []
for t, g in l1.groupby("tail_no"):
    o = list(g.t_open_dt); ivs += [(b - a).total_seconds() / 86400 for a, b in zip(o, o[1:])]
    durs += [((c - a).total_seconds() / 3600) for a, c in zip(g.t_open_dt, g.t_close_dt) if pd.notna(c)]
cad = float(np.median(ivs)); dur_h = float(np.median(durs))
board = {it["tail"]: [] for it in DEC["items"] if it.get("tail")}
for it in DEC["items"]:
    if it.get("tail"):
        board[it["tail"]].append(dict(action=it["action"], code=it.get("code"), band=it["band"]))
sched = []
for t in TAILS:
    st_, since = state[t]
    row = dict(tail=t, state=st_, since=since.strftime("%d %b"), items=[], orders=board.get(t, []))
    last = l1[l1.tail_no == t].t_open_dt.max()
    if st_ != "NMCD":
        nxt = last + pd.Timedelta(days=cad)
        while nxt < H_END:
            if nxt >= EPOCH - pd.Timedelta(hours=2):
                row["items"].append(dict(kind="SRV-L1", start=round((nxt - EPOCH).total_seconds() / 86400, 3), dur=round(dur_h / 24, 3), date=nxt.strftime("%d %b")))
            nxt += pd.Timedelta(days=cad)
    c = next(x for x in cons if x["tail"] == t)
    if st_ not in ("NMCS", "NMCD") and c["ldg_per_day"] > 0:
        k = (8 - c["tyre_used"]) / c["ldg_per_day"]
        while k < 30:
            row["items"].append(dict(kind="TYRE", start=round(k, 2), date=(EPOCH + pd.Timedelta(days=k)).strftime("%d %b"))); k += 8 / c["ldg_per_day"]
    sched.append(row)
# hangar: 2 periodic-servicing slots per base (docs/architecture/06, CP-SAT example) -> days with both taken
from collections import Counter
cnt = Counter((i["date"]) for r_ in sched for i in r_["items"] if i["kind"] == "SRV-L1")
full = sorted([dt for dt, c in cnt.items() if c >= 2], key=lambda x: pd.Timestamp(x + " 2026"))
R["schedule_full_days"] = [dict(date=dt, tails=[r_["tail"] for r_ in sched for i in r_["items"] if i["kind"] == "SRV-L1" and i["date"] == dt]) for dt in full]
print("slots full", R["schedule_full_days"], "srv count", sum(cnt.values()), "tyre count", sum(1 for r_ in sched for i in r_["items"] if i["kind"] == "TYRE"))
R["schedule"] = dict(full_days=R["schedule_full_days"], cadence_d=cad, n_intervals=len(ivs), srv_l1_dur_h=round(dur_h, 1), n_durations=len(durs),
                     rows=sched, roh_completed_on_record=int(((insp.inspection_type == "ROH") & (insp.status == "CLOSED")).sum()),
                     tj108_ingest=state["TJ108"][1].strftime("%d %b %H:%M"))
print("cadence", cad, len(ivs), "dur_h", dur_h, len(durs))
for r_ in sched: print(r_["tail"], r_["state"], [(i["kind"], i["date"]) for i in r_["items"]], [o["action"] for o in r_["orders"]])

for k_ in ("S1", "S2", "S3"):  # order-status keys -> action label (fork run ids stay in forks/results.json)
    R[k_]["status"] = {kk.split(":")[-1]: vv for kk, vv in R[k_]["status"].items()}
json.dump(R, open(OUT + "plan_spares_asof_20260622.json", "w"), indent=1, default=float)

# ============================================================ page assets
A = "/Users/abishaikc/Phalanx-Solution/video/screens/assets/"
hdr = "/* generated by video/data/scripts/plan_spares_data.py — do not edit */\n"
open(A + "data-plan.js", "w").write(hdr + "window.PHX_PLAN = " + json.dumps({k: R[k] for k in ("S1", "S2", "S3", "compute", "schedule", "consumables")}, default=float) + ";\n")
open(A + "data-spares.js", "w").write(hdr + "window.PHX_SPARES = " + json.dumps({k: R[k] for k in ("leadtime", "consumables", "useful", "S2", "S3")}, default=float) + ";\n")
print("wrote", OUT + "plan_spares_asof_20260622.json")
