"""Fleet insights as of the snapshot (Mon 22 Jun 2026 06:00 IST).

Reads the v0.9 consumer fleet trees only (never _restricted_labels), keeps every record with
t_ingest <= T, scopes identity by (tail_no, record_id) and resolves the latest record_version per
(tail_no, record_type, record_key). SHOP_FINDING rows carry no tail_no, so each is linked to its world
by matching job_no + serial_no against that world's COMPONENT_LIFE REMOVE record.

Writes video/data/insights_asof_20260622.json and video/screens/assets/data-insights.js.
Run: <venv>/bin/python video/data/scripts/insights_asof.py
"""
import sys, os, re, json, bisect, collections
sys.path.insert(0, os.path.dirname(__file__))
from phx_load import *            # rd(topic), B, IST, pd, np
import pyarrow.dataset as pds

T = pd.Timestamp("2026-06-22 06:00", tz=IST)
T0 = pd.Timestamp("2026-01-05 05:30", tz=IST)
W30 = T - pd.Timedelta(days=30)
V = "/Users/abishaikc/Phalanx-Solution/video/data/"
OUT = {}

m = rd("maint.records"); mk = m[m.t_ingest_dt <= T]
ev = rd("events.bit_faults"); ek = ev[ev.t_ingest_dt <= T]
ca = rd("events.cautions"); ck = ca[ca.t_ingest_dt <= T]
lat = mk.sort_values(["record_version", "t_ingest"]).drop_duplicates(["tail_no", "record_type", "record_key"], keep="last")
TAILS = sorted(m.tail_no.dropna().unique())

# ------------------------------------------------------------------ occupancy (latest version per record_key)
av_all = mk[mk.record_type == "AVAILABILITY_STATE"]
av = av_all.sort_values("record_version").drop_duplicates(["tail_no", "record_key"], keep="last").sort_values("t_event")

def occ(w0, w1):
    tot = collections.defaultdict(float)
    for t, a in av.groupby("tail_no"):
        times = list(a.t_event_dt) + [w1]; sts = list(a.availability_state)
        for i, s in enumerate(sts):
            s0 = max(times[i], w0); s1 = min(times[i + 1], w1)
            if s1 > s0: tot[s] += (s1 - s0).total_seconds() / 86400
    return tot

def rates(o):
    P = sum(o.values())
    mc = o.get("FMC", 0) + o.get("PMCM", 0) + o.get("PMCS", 0)
    nmcm = o.get("NMCM_S", 0) + o.get("NMCM_U", 0)
    return dict(possessed=round(P, 1), mc_days=round(mc, 1), fmc_days=round(o.get("FMC", 0), 1), pmc_days=round(o.get("PMCM", 0), 1),
                nmcm_days=round(nmcm, 1), nmcs_days=round(o.get("NMCS", 0), 1), nmcd_days=round(o.get("NMCD", 0), 1),
                mc=round(mc / P, 4), fmc=round(o.get("FMC", 0) / P, 4), tnmcm=round(nmcm / P, 4),
                tnmcs=round(o.get("NMCS", 0) / P, 4), nmcd=round(o.get("NMCD", 0) / P, 4))

L168, L30 = rates(occ(T0, T)), rates(occ(W30, T))
OUT["lagging"] = {"d168": L168, "d30": L30}

# ------------------------------------------------------------------ downtime attribution (same versioning)
part = {}
for _, r in mk[mk.record_type.isin(["DEFECT_WO", "INSPECTION"])].sort_values("record_version").iterrows():
    k = (r.tail_no, r.record_key)
    if k not in part:
        part[k] = r.part_no if isinstance(r.part_no, str) else (r.inspection_type if isinstance(r.inspection_type, str) else "-")
attr = {}
for name, f in (("NMCS", {"NMCS"}), ("NMCM", {"NMCM_U", "NMCM_S"}), ("NMCD", {"NMCD"})):
    out = collections.defaultdict(float)
    for tail, g in mk.groupby("tail_no"):
        a = av[av.tail_no == tail]
        ser = list(zip(a.t_event_dt, a.availability_state))
        tl = g[g.record_type == "TECH_LOG"].sort_values("t_event"); times = list(tl.t_event_dt); txts = list(tl.limitations_text)
        for (b, s), nxt in zip(ser, ser[1:] + [(T, None)]):
            if s not in f: continue
            dur = (min(nxt[0], T) - max(b, T0)).total_seconds() / 86400
            if dur <= 0: continue
            i = bisect.bisect_right(times, b) - 1
            txt = txts[i] if i >= 0 else ""
            jobs = []
            for p in (txt or "").split(";"):
                p = p.strip()
                if p.startswith("U/S:"): jobs += p[4:].split()
            keys = sorted({part.get((tail, j), "?") for j in jobs}) or ["none"]
            for k in keys: out[k] += dur / len(keys)
    attr[name] = dict(total=round(sum(out.values()), 1), by={k: round(v, 1) for k, v in sorted(out.items(), key=lambda kv: -kv[1])})
OUT["downtime"] = attr

# ------------------------------------------------------------------ flying
so = lat[lat.record_type == "SORTIE"]
fh168 = so.flight_hours.sum(); fh30 = so[so.t_event_dt > W30].flight_hours.sum()
OUT["flying"] = dict(fh168=round(fh168, 1), sorties168=len(so), fh30=round(fh30, 1), sorties30=int((so.t_event_dt > W30).sum()))

# ------------------------------------------------------------------ BIT-evidenced jobs and outcomes
dw = lat[lat.record_type == "DEFECT_WO"]
mh_max = mk[mk.record_type == "DEFECT_WO"].groupby(["tail_no", "record_key"]).man_hours.max()
emap = dict(zip(ek.tail_no + ":" + ek.rid, ek.event_code)); eing = dict(zip(ek.tail_no + ":" + ek.rid, ek.t_ingest_dt))
rows = []
for _, j in dw.iterrows():
    evs = j.evidence_record_ids
    code, first = None, None
    if evs is not None and len(evs):
        keys = [j.tail_no + ":" + bytes(x).hex() for x in evs]
        codes = [emap[k] for k in keys if k in emap]
        if codes:
            code = codes[0]; first = min(eing[k] for k in keys if k in eing)
    rows.append(dict(tno=j.tail_no, job=j.job_no, key=j.record_key, code=code, first_ing=first, act=j.action_taken_code,
                     mal=j.malfunction_code, wd=j.when_discovered, part=j.part_no, status=j.status, t_open=j.t_open_dt,
                     t_close=j.t_close_dt, mh=float(mh_max.get((j.tail_no, j.record_key), 0) or 0)))
J = pd.DataFrame(rows)
JB = J[J.code.notna()]
OUT["jobs"] = dict(defect_jobs=len(J), bit_evidenced=len(JB), mh_total=round(J.mh.sum(), 1),
                   actions=J.act.fillna("none").value_counts().to_dict())

RTOK_JOBS = set()
# ------------------------------------------------------------------ removals and shop findings by part class
cl = mk[mk.record_type == "COMPONENT_LIFE"]
rem = cl[cl.install_action == "REMOVE"]
rem_all = m[(m.record_type == "COMPONENT_LIFE") & (m.install_action == "REMOVE")]
sfd = pds.dataset(B + "maint.records", format="parquet", partitioning=None).to_table(
    filter=pds.field("record_type") == "SHOP_FINDING",
    columns=["record_id", "part_no", "serial_no", "job_no", "shop_finding", "t_event", "t_ingest"]).to_pandas()
sfd["rid"] = sfd.record_id.apply(lambda b: bytes(b).hex())
sfd["t_ev"] = pd.to_datetime(sfd.t_event, utc=True).dt.tz_convert(IST)
sfd["t_ing"] = pd.to_datetime(sfd.t_ingest, utc=True).dt.tz_convert(IST)
def link(r):
    c = rem_all[(rem_all.job_no == r.job_no) & (rem_all.serial_no == r.serial_no) & (rem_all.t_event_dt <= r.t_ev)]
    w = sorted(c.tail_no.unique())
    return w[0] if len(w) == 1 else None
sfd["world"] = sfd.apply(link, axis=1)
sfk = sfd[sfd.t_ing <= T].sort_values("t_ingest").drop_duplicates(["world", "rid"])
sf_linked = sfk[sfk.world.notna()]
OUT["shop"] = dict(rows_total=len(sfd), rid_unique_global=int(sfd.rid.nunique()), asof_rows=len(sfk),
                   asof_linked=len(sf_linked), asof_unlinked=int(sfk.world.isna().sum()),
                   findings=sf_linked.shop_finding.value_counts().to_dict(),
                   naive_global_dedupe_asof=int(sfd[sfd.t_ing <= T].rid.nunique()))
RTOK_JOBS.update(set(zip(sf_linked[sf_linked.shop_finding == 'RTOK'].world, sf_linked[sf_linked.shop_finding == 'RTOK'].job_no)))

# ------------------------------------------------------------------ leading indicators
# RTOK_JOBS: (tail, job_no) whose removed unit returned RTOK
def nofault(df):  # closed jobs with no fault found: CND, admin close, or R/R whose removed unit the shop found RTOK
    rr = df.apply(lambda r: (r.tno, r.job) in RTOK_JOBS, axis=1) if len(df) else False
    return df[(df.status == "CLOSED") & (df.act.isin(["AT-CND", "AT-ADM"]) | ((df.act == "AT-RR") & rr))]

sor = mk[mk.record_type == "SORTIE"].sort_values("t_event")
sorties_by_tail = {t: list(g.sortie_id) for t, g in sor.groupby("tail_no")}
stime_by_tail = {t: list(g.t_event_dt) for t, g in sor.groupby("tail_no")}
code_sorties = ek.groupby(["tail_no", "event_code"]).sortie_id.apply(set).to_dict()

def repeat_recur(df):
    rep = rec = n = 0
    for _, j in df[(df.status == "CLOSED") & df.code.notna()].iterrows():
        st = stime_by_tail.get(j.tno, []); ids = sorties_by_tail.get(j.tno, [])
        i = bisect.bisect_right(st, j.t_close)
        nxt = ids[i:i + 4]
        if len(nxt) < 4: continue          # follow-up window not yet observed as of T
        n += 1
        fired = code_sorties.get((j.tno, j.code), set())
        if nxt[0] in fired: rep += 1
        elif any(s in fired for s in nxt[1:4]): rec += 1
    return dict(repeat=rep, recur=rec, n=n, rate=round((rep + rec) / n, 4) if n else None)

def deferred_at(t):
    mt = m[m.t_ingest_dt <= t]
    l = mt[mt.record_type == "DEFECT_WO"].sort_values(["record_version", "t_ingest"]).drop_duplicates(["tail_no", "record_key"], keep="last")
    d = l[l.status.isin(["DEFERRED", "AWAITING_PARTS"])]
    return dict(deferred=int((d.status == "DEFERRED").sum()), awp=int((d.status == "AWAITING_PARTS").sum()), n=len(d),
                per_ac=round(len(d) / 8, 2), by_tail=d.tail_no.value_counts().to_dict())

lead = {}
for nm, w0, fh in (("d168", T0, fh168), ("d30", W30, fh30)):
    Jw = J[(J.t_close.notna()) & (J.t_close > w0) & (J.t_close <= T)]
    JBw = Jw[Jw.code.notna()]
    nf = nofault(Jw)
    evw = ek[ek.t_occurrence_dt > w0]
    closed_bit = JBw[JBw.status == "CLOSED"]
    lead[nm] = dict(
        repeat_recur=repeat_recur(Jw),
        nofault_mh=round(nf.mh.sum(), 1), nofault_mh_per_fh=round(nf.mh.sum() / fh, 2), defect_mh=round(Jw.mh.sum(), 1),
        nofault_share_mh=round(nf.mh.sum() / Jw.mh.sum(), 3),
        bit_events=len(evw), bit_per_fh=round(len(evw) / fh, 2), fh=round(fh, 1),
        bit_jobs_closed=len(closed_bit), bit_jobs_confirmed=0,
        bit_not_confirmed_share=1.0 if len(closed_bit) else None,
        fh_per_unconfirmed_bit=round(fh / len(evw), 2))
lead["d168"]["deferred"] = deferred_at(T); lead["d30"]["deferred"] = deferred_at(W30)
OUT["leading"] = lead

# ------------------------------------------------------------------ bad-actor Pareto (BIT events by code) + outcome mix
vc = ek.event_code.value_counts()
tot = int(vc.sum()); cum = 0; par = []
oc = JB.groupby("code").act.value_counts().unstack(fill_value=0)
for c, n in vc.items():
    cum += n
    o = oc.loc[c].to_dict() if c in oc.index else {}
    par.append(dict(code=c, n=int(n), share=round(n / tot, 4), cum=round(cum / tot, 4),
                    sev=ek[ek.event_code == c].severity.iloc[0], lru=ek[ek.event_code == c].source_lru.iloc[0],
                    desc=ek[ek.event_code == c].description.iloc[0],
                    jobs=int(sum(o.values())), cnd=int(o.get("AT-CND", 0)), rr=int(o.get("AT-RR", 0)), adm=int(o.get("AT-ADM", 0)),
                    ts=int(o.get("AT-TS", 0)), dfr=int(o.get("AT-DEF", 0)), confirmed=0))
OUT["pareto"] = dict(total=tot, codes=len(vc), top10_share=round(vc.head(10).sum() / tot, 4), rows=par)

pc = []
for p, g in rem.groupby("part_no"):
    unsched = J[(J.part == p) & (J.act == "AT-RR")]
    s = sf_linked[sf_linked.part_no == p]
    pc.append(dict(part=p, removals=len(g), serials=int(g.groupby(["tail_no", "serial_no"]).ngroups),
                   bit_driven=int(((unsched.mal == "MAL-BIT")).sum()), wear=int((unsched.mal == "MAL-HT").sum()),
                   shop=len(s), rtok=int((s.shop_finding == "RTOK").sum()), confirmed=int((s.shop_finding == "CONFIRMED").sum())))
OUT["parts"] = sorted(pc, key=lambda d: -d["removals"])
rg = rem[rem.serial_no != "XXX"].groupby(["tail_no", "part_no", "serial_no"]).agg(n=("t_event", "size"), last=("t_event_dt", "max"), first=("t_event_dt", "min")).reset_index()
rg = rg[~rg.part_no.isin(["SYN-PN-TYRE"])].sort_values(["n", "last"], ascending=[False, False])
rog = []
for _, r in rg.head(8).iterrows():
    s = sf_linked[(sf_linked.world == r.tail_no) & (sf_linked.serial_no == r.serial_no)]
    pcls = [x for x in pc if x["part"] == r.part_no][0]
    # class mean removals per serial-position for context
    rog.append(dict(tail=r.tail_no, part=r.part_no, serial=r.serial_no, removals=int(r.n), shop=len(s),
                    rtok=int((s.shop_finding == "RTOK").sum()), first=r["first"].strftime("%d %b"), last=r["last"].strftime("%d %b"),
                    class_mean=round(pcls["removals"] / pcls["serials"], 2)))
OUT["rogue"] = rog

# ------------------------------------------------------------------ record integrity
xr = mk[mk.serial_no == "XXX"]
ent = xr.drop_duplicates(["tail_no", "record_type", "record_key"])
SN = re.compile(r"REMOVED\s+S/?N\s+([A-Z0-9-]+-\d{6})")
SNI = re.compile(r"INSTALLED\s+S/?N\s+([A-Z0-9-]+-\d{6})")
rep = 0
for _, r in ent.iterrows():
    txts = mk[(mk.tail_no == r.tail_no) & (mk.job_no == r.job_no) & (mk.record_type == "DEFECT_WO")].corrective_action_text.dropna() if isinstance(r.job_no, str) else []
    if any(SN.search(t or "") for t in txts): rep += 1
OUT["xxx"] = dict(rows=len(xr), entities=len(ent), by_type=ent.record_type.value_counts().to_dict(),
                  by_tail=ent.tail_no.fillna("unscoped").value_counts().to_dict(), repairable_from_text=rep,
                  rows_by_type=xr.record_type.value_counts().to_dict())

# only demands that carry a tail (AOG demands against an aircraft); base-level demands have no tail_no
dem = lat[(lat.record_type == "SUPPLY_DEMAND") & lat.tail_no.notna()]
dopen = dem[dem.status != "CLOSED"]
inst = cl[cl.install_action == "INSTALL"]
stale = []
for _, d in dopen.iterrows():
    i = inst[(inst.tail_no == d.tail_no) & (inst.part_no == d.part_no) & (inst.t_event_dt > d.t_open_dt)]
    if len(i):
        stale.append(dict(tail=d.tail_no, demand=d.demand_no, part=d.part_no, prio=d.priority, opened=d.t_open_dt.strftime("%d %b"),
                          installed=i.t_event_dt.min().strftime("%d %b"), serial=i.sort_values("t_event").serial_no.iloc[0],
                          age_d=round((T - d.t_open_dt).total_seconds() / 86400, 1)))
stale_ids = {(x["tail"], x["demand"]) for x in stale}
waiting = [dict(tail=d.tail_no, demand=d.demand_no, part=d.part_no, opened=d.t_open_dt.strftime("%d %b"), age_d=round((T - d.t_open_dt).total_seconds() / 86400, 1))
           for _, d in dopen.iterrows() if (d.tail_no, d.demand_no) not in stale_ids]
OUT["demands_waiting"] = waiting
OUT["demands"] = dict(tail_linked=len(dem), open=len(dopen), closed=int((dem.status == "CLOSED").sum()), open_by_prio=dopen.priority.value_counts().to_dict(), stale=sorted(stale, key=lambda s: -s["age_d"]))

lag_inst = []
for _, j in dw[dw.corrective_action_text.notna()].iterrows():
    mm = SNI.search(j.corrective_action_text)
    if not mm: continue
    sn = mm.group(1)
    hit = inst[(inst.tail_no == j.tail_no) & (inst.serial_no == sn)]
    if len(hit) == 0 or hit.t_event_dt.max() < (j.t_open_dt - pd.Timedelta(days=0)):
        lag_inst.append(dict(tail=j.tail_no, job=j.job_no, serial=sn, part=j.part_no, closed=j.t_close_dt.strftime("%d %b %H:%M") if pd.notna(j.t_close_dt) else None))
OUT["install_lag"] = lag_inst

lag = []
for rt, g in mk[mk.record_type != "SHOP_FINDING"].groupby("record_type"):
    h = (g.t_ingest_dt - g.t_event_dt).dt.total_seconds() / 3600
    lag.append(dict(type=rt, n=len(g), p10=round(h.quantile(.1), 2), med=round(h.median(), 2), p90=round(h.quantile(.9), 2), max=round(h.max(), 1), over24=round(float((h > 24).mean()), 4), n24=int((h > 24).sum())))
h = (sfk.t_ing - sfk.t_ev).dt.total_seconds() / 3600
lag.append(dict(type="SHOP_FINDING", n=len(sfk), p10=round(h.quantile(.1), 2), med=round(h.median(), 2), p90=round(h.quantile(.9), 2), max=round(h.max(), 1), over24=round(float((h > 24).mean()), 4), n24=int((h > 24).sum())))
for nm, df, col in (("BIT_EVENT", ek, "t_occurrence_dt"), ("CAUTION", ck, "t_occurrence_dt")):
    h = (df.t_ingest_dt - df[col]).dt.total_seconds() / 3600
    lag.append(dict(type=nm, n=len(df), p10=round(h.quantile(.1), 2), med=round(h.median(), 2), p90=round(h.quantile(.9), 2), max=round(h.max(), 1), over24=round(float((h > 24).mean()), 4), n24=int((h > 24).sum())))
OUT["ingest_lag"] = sorted(lag, key=lambda d: d["med"])

# ------------------------------------------------------------------ evidence-to-decision latency
cjb = JB[JB.t_close.notna() & (JB.t_close <= T)]
sq = ((cjb.t_close - cjb.first_ing).dt.total_seconds() / 3600).values
def next8(t):
    c = t.normalize() + pd.Timedelta(hours=8)
    return c if t <= c - pd.Timedelta(hours=2) else c + pd.Timedelta(days=1)   # 06:00 snapshot cut-off
lp = np.array([(next8(t) - t).total_seconds() / 3600 for t in ek.t_ingest_dt])
lp_paired = np.array([(next8(t) - t).total_seconds() / 3600 for t in cjb.first_ing])
def q(a): return dict(n=int(len(a)), p10=round(float(np.quantile(a, .1)), 1), median=round(float(np.median(a)), 1),
                      p90=round(float(np.quantile(a, .9)), 1), max=round(float(np.max(a)), 1), min=round(float(np.min(a)), 2),
                      over24=int((a > 24).sum()), over72=int((a > 72).sum()), mean=round(float(np.mean(a)), 1))
edges = [0.5, 1, 2, 4, 8, 12, 16, 20, 24, 36, 48, 72, 96, 144, 192, 288, 480, 1000]
def hist(a):
    return np.histogram(np.clip(a, edges[0], edges[-1] - 1e-6), bins=edges)[0].tolist()
OUT["latency"] = dict(status_quo=q(sq), loop=q(lp), loop_paired=q(lp_paired), edges=edges, h_sq=hist(sq), h_loop=hist(lp),
                      sq_values=sorted(round(float(x), 2) for x in sq), loop_values=sorted(round(float(x), 2) for x in lp))

json.dump(OUT, open(V + "insights_asof_20260622.json", "w"), indent=1, default=str)
open("/Users/abishaikc/Phalanx-Solution/video/screens/assets/data-insights.js", "w").write(
    "/* computed by video/data/scripts/insights_asof.py — as of 22 Jun 2026 06:00 IST, t_ingest <= T */\nwindow.PHX_INS = " +
    json.dumps({k: v for k, v in OUT.items()}, default=str) + ";\n")
s = dict(OUT); s["latency"] = {k: v for k, v in OUT["latency"].items() if not k.endswith("values")}
print(json.dumps(s, indent=1, default=str))
