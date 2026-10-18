"""Data for the Decision board, Issue workbench (TJ107 HYD-101) and 08:00 epoch screens.

Reads the v0.9 preview fleet tree strictly as of t_ingest <= 2026-06-22 06:00 IST (never _restricted_labels),
dedupes by (tail_no, record_id), and writes video/data/decision_screens_asof_20260622.json.

Run:  <venv>/bin/python video/data/scripts/decision_screens_data.py
(pandas + pyarrow venv; see SPEC.md)
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[2]  # video/
OUT = ROOT / "data" / "decision_screens_asof_20260622.json"
B = "/Users/abishaikc/Downloads/phalanx_data_layer_preview/data/v0.9/fleet/"
IST = "Asia/Kolkata"
SNAP = pd.Timestamp("2026-06-22 06:00", tz=IST)
EPOCH = pd.Timestamp("2026-06-22 08:00", tz=IST)


def scope_key(df: pd.DataFrame) -> str:
    """World scope: each preview tail is its own world (orders.status has no tail column -> order_id)."""
    return next(c for c in ("target_tail_no", "tail_no", "order_id") if c in df)


def rd(topic: str) -> pd.DataFrame:
    d = ds.dataset(B + topic, format="parquet", partitioning=None)
    tb = d.to_table()
    for i, f in enumerate(tb.schema):
        if pa.types.is_list(f.type) and pa.types.is_fixed_size_binary(f.type.value_type):
            tb = tb.set_column(i, f.name, tb.column(i).cast(pa.list_(pa.binary())))
    df = tb.to_pandas()
    df["rid"] = df.record_id.apply(lambda b: bytes(b).hex())
    key = scope_key(df)
    tcol = next((c for c in ("t_ingest", "t_issued", "t_status") if c in df), None)
    if tcol:
        df = df.sort_values(tcol)
    df = df.drop_duplicates([key, "rid"])
    for c in list(df.columns):
        if c.startswith("t_") and not c.endswith("_dt") and pd.api.types.is_numeric_dtype(df[c]):
            df[c + "_dt"] = pd.to_datetime(df[c].astype("Int64"), unit="ns", utc=True).dt.tz_convert(IST)
    return df


def asof(df: pd.DataFrame) -> pd.DataFrame:
    for c in ("t_ingest_dt", "t_issued_dt", "t_status_dt"):
        if c in df:
            return df[df[c] <= SNAP]
    return df


def _betacf(a, b, x):
    # continued fraction for the regularized incomplete beta (Numerical Recipes 6.4)
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for mm in range(1, 400):
        m2 = 2 * mm
        aa = mm * (b - mm) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + mm) * (qab + mm) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > 1e-300 else 1e-300
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-14:
            break
    return h


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def beta_ppf(q, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def jeffreys(k: int, n: int) -> list[float]:
    """Jeffreys Beta(k+1/2, n-k+1/2): posterior mean and equal-tailed 95 % interval."""
    a, b = k + 0.5, n - k + 0.5
    return [a / (a + b), beta_ppf(0.025, a, b), beta_ppf(0.975, a, b)]


def hm(ts: pd.Timestamp) -> str:
    return ts.strftime("%d %b %H:%M")


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ------------------------------------------------------------------ load
topics = ["events.bit_faults", "events.cautions", "maint.records", "orders.commands", "orders.status",
          "usage.counters"]
raw = {t: rd(t) for t in topics}
A = {t: asof(df) for t, df in raw.items()}
bit, cau, m = A["events.bit_faults"], A["events.cautions"], A["maint.records"]

# ------------------------------------------------------------------ snapshot hash (doc 07: H(sorted record_ids per topic))
snap_obj = {}
snap_counts = {}
for t in topics:
    df = A[t]
    key = scope_key(df)
    ids = sorted(f"{'' if pd.isna(tl) else tl}:{r}" for tl, r in zip(df[key], df.rid))
    snap_obj[t] = ids
    snap_counts[t] = len(ids)
snapshot_hash = hashlib.sha256(canon(snap_obj).encode()).hexdigest()

# ------------------------------------------------------------------ helpers on maint.records
dwo = m[m.record_type == "DEFECT_WO"].copy()
jobs_last = dwo.sort_values(["tail_no", "job_no", "record_version"]).groupby(["tail_no", "job_no"]).tail(1)


def code_jobs(tail: str | None, code: str) -> pd.DataFrame:
    j = jobs_last if tail is None else jobs_last[jobs_last.tail_no == tail]
    return j[j.discrepancy_text.fillna("").str.contains(code, regex=False)]


sorties = m[m.record_type == "SORTIE"].copy()

# ------------------------------------------------------------------ fleet code outcomes (base rates)
shop = m[m.record_type == "SHOP_FINDING"]
confirmed_shop = int((shop.shop_finding != "RTOK").sum())
# a job belongs to a code when any version cites an event of that code as evidence; keyed (tail_no, job_no)
# because job numbers collide across the eight preview worlds. Confirmed = a shop finding other than RTOK
# (there are none in the preview as of the snapshot).
evmap = {(t, r): c for t, r, c in zip(bit.tail_no, bit.rid, bit.event_code)}
_rows = []
for (tail, job), gg in dwo.sort_values("record_version").groupby(["tail_no", "job_no"]):
    codes = set()
    for lst in gg.evidence_record_ids:
        for b_ in (lst if lst is not None else []):
            c_ = evmap.get((tail, bytes(b_).hex()))
            if c_:
                codes.add(c_)
    last_ = gg.iloc[-1]
    for c_ in codes:
        _rows.append((tail, job, c_, last_.action_taken_code, last_.status, float(last_.man_hours)))
JOBC = pd.DataFrame(_rows, columns=["tail_no", "job_no", "code", "act", "status", "mh"])
code_out = {}
for code in ["HYD-101", "LGB-501", "SPS-501", "ENG-201", "AVI-201", "AVI-203", "AVI-204", "ADC-002", "ELE-405"]:
    j = JOBC[JOBC.code == code]
    ac = j.act.value_counts(dropna=False).to_dict()
    code_out[code] = {"n": int(len(j)), "cnd": int(ac.get("AT-CND", 0)), "rr": int(ac.get("AT-RR", 0)),
                      "ts": int(ac.get("AT-TS", 0)), "adm": int(ac.get("AT-ADM", 0)), "def": int(ac.get("AT-DEF", 0)),
                      "open": int((j.status != "CLOSED").sum()), "confirmed": confirmed_shop}

# ------------------------------------------------------------------ TJ107 HYD-101
T = "TJ107"
e107 = bit[(bit.tail_no == T) & (bit.event_code == "HYD-101")].sort_values("t_ingest")
s107 = sorties[sorties.tail_no == T].sort_values("t_event")
sids = list(s107.sortie_id)
fired_set = set(e107.sortie_id)
fired = [s in fired_set for s in sids]
runs, cur = [], 0
for f in fired:
    if f:
        cur += 1
    else:
        if cur:
            runs.append(cur)
        cur = 0
runs.append(cur)
gr_events = sorted(set(e107.sortie_id) - set(sids))

j107 = code_jobs(T, "HYD-1")  # includes one OCR-damaged 'HYD-11' text
j107 = j107[j107.when_discovered.notna()]
mh107 = float(j107.man_hours.sum())
ac107 = j107.action_taken_code.value_counts(dropna=False).to_dict()

# latest evidence (same six records the S1 fork cited)
ev6 = e107.tail(6)
evidence_hyd = [{"rid": r.rid, "sortie": r.sortie_id, "t_occ": hm(r.t_occurrence_dt), "t_ingest": hm(r.t_ingest_dt),
                 "persistence": int(r.persistence_count), "mech": r.detection_mechanism}
                for r in ev6.itertuples()]
assert all(ev6.t_ingest_dt <= SNAP)

# pump component life (TJ107)
cl = m[(m.record_type == "COMPONENT_LIFE") & (m.part_no == "SYN-PN-HYDP") & (m.tail_no == T)].copy()
rem = cl[cl.install_action == "REMOVE"]
serials_on_record = sorted(cl.record_key.unique())
serial_values_on_remove = sorted(rem.serial_no.unique())

# R/R events from job text (complete), cross-checked against COMPONENT_LIFE
rr_rx = re.compile(r"REMOVED S/N (\S+?),? INSTALLED S/N (\S+?)\.")
all_versions = m[(m.tail_no == T) & m.job_no.notna() & m.corrective_action_text.fillna("").str.contains("HYDP")]
rr_jobs = []
for job, g in all_versions.sort_values("record_version").groupby("job_no"):
    r = g.iloc[-1]
    mt = rr_rx.search(r.corrective_action_text)
    if not mt:
        continue
    has_cl = bool(((rem.job_no == job)).any())
    t_close = r.t_close_dt if pd.notna(r.t_close_dt) else r.t_event_dt
    rr_jobs.append({"job": job, "removed": mt.group(1), "installed": mt.group(2), "t_close": t_close,
                    "t_open": r.t_open_dt, "mh": float(r.man_hours), "cl_record": has_cl,
                    "record_type": r.record_type})
rr_jobs.sort(key=lambda x: x["t_close"])

# SYS1 serial timeline: start HYDP-000001 (SYS2 = HYDP-000002 never removed)
sys1 = [(pd.Timestamp("2026-01-01", tz=IST), "HYDP-000001", False)]
for r in rr_jobs:
    sys1.append((r["t_close"], r["installed"], not r["cl_record"]))
# 19 Jun install of HYDP-000010 has no ingested INSTALL record -> inferred (job text only)
inst_ingested = set(cl[cl.install_action == "INSTALL"].job_no)
inferred_jobs = [r["job"] for r in rr_jobs if r["job"] not in inst_ingested]


def sys1_at(ts):
    s = sys1[0]
    for x in sys1:
        if x[0] <= ts:
            s = x
    return s


strip = []
for r in s107.itertuples():
    takeoff = pd.Timestamp(r.sortie_id.split("-")[1], tz="UTC").tz_convert(IST)
    s_at = sys1_at(takeoff)
    strip.append({"sid": r.sortie_id, "d": takeoff.strftime("%d %b"), "t": round((takeoff - pd.Timestamp("2026-01-05", tz=IST)).total_seconds() / 86400, 3),
                  "fired": r.sortie_id in fired_set, "serial": s_at[1], "inferred": s_at[2] or (s_at[0] >= pd.Timestamp("2026-06-19", tz=IST))})
removal_marks = [{"t": round((r["t_close"] - pd.Timestamp("2026-01-05", tz=IST)).total_seconds() / 86400, 3), "removed": r["removed"],
                  "installed": r["installed"], "job": r["job"], "cl": r["cl_record"]} for r in rr_jobs]
serials_sys1 = []
for s in strip:
    if not serials_sys1 or serials_sys1[-1] != s["serial"]:
        serials_sys1.append(s["serial"])
distinct_sys1 = sorted({x[1] for x in sys1})

# shop findings for pumps (no tail_no on SHOP_FINDING rows; matched to TJ107 by job_no + serial / job text)
sfp = shop[shop.part_no == "SYN-PN-HYDP"]
rr_by_job = {r["job"]: r for r in rr_jobs}
sf_tj107 = [r for r in sfp.itertuples() if r.job_no in rr_by_job and (r.serial_no in (rr_by_job[r.job_no]["removed"], "XXX"))]
n_sf = len(sfp)
n_sf_rtok = int((sfp.shop_finding == "RTOK").sum())

P_conf = jeffreys(0, code_out["HYD-101"]["n"])
P_rtok = jeffreys(n_sf_rtok, n_sf)

# availability effect per R/R job: non-FMC hours of TJ107 between job open and close
av = m[(m.record_type == "AVAILABILITY_STATE") & (m.tail_no == T)].sort_values("t_event")
av_t = list(av.t_event_dt)
av_s = list(av.availability_state)


def down_hours(t0, t1):
    tot = {}
    for i, (ts, st) in enumerate(zip(av_t, av_s)):
        te = av_t[i + 1] if i + 1 < len(av_t) else SNAP
        a, b = max(ts, t0), min(te, t1)
        if b > a and st != "FMC":
            tot[st] = tot.get(st, 0) + (b - a).total_seconds() / 3600
    return tot


# evidence-chain lanes: latest four pump removals
lanes = []
for r in rr_jobs[-4:]:
    g = dwo[(dwo.tail_no == T) & (dwo.job_no == r["job"])].sort_values("record_version")
    ev_ids = set()
    for lst in g.evidence_record_ids:
        for b in (lst if lst is not None else []):
            ev_ids.add(bytes(b).hex())
    evs = e107[e107.rid.isin(ev_ids)]
    ev0 = evs.iloc[0] if len(evs) else None
    steps = [f"{x.status}{'·' + x.action_taken_code if isinstance(x.action_taken_code, str) else ''}" for x in g.itertuples()]
    ts_mh = None
    gts = g[g.action_taken_code == "AT-TS"]
    if len(gts):
        ts_mh = float(gts.iloc[0].man_hours)
    sf = [x for x in sf_tj107 if x.job_no == r["job"]]
    dh = down_hours(r["t_open"], r["t_close"])
    lanes.append({
        "event": None if ev0 is None else {"rid": ev0.rid, "sortie": ev0.sortie_id, "t_occ": hm(ev0.t_occurrence_dt), "t_ingest": hm(ev0.t_ingest_dt)},
        "job": r["job"], "opened": hm(r["t_open"]), "closed": hm(r["t_close"]), "mh": round(r["mh"], 1),
        "ts_mh": None if ts_mh is None else round(ts_mh, 1),
        "awp": bool((g.status == "AWAITING_PARTS").any()),
        "removed": r["removed"], "installed": r["installed"], "cl_record": r["cl_record"],
        "shop": None if not sf else {"finding": sf[0].shop_finding, "serial": sf[0].serial_no, "t": hm(sf[0].t_event_dt), "t_ingest": hm(sf[0].t_ingest_dt)},
        "down_h": {k: round(v, 1) for k, v in dh.items()},
        "down_total_h": round(sum(dh.values()), 1),
        "steps": steps,
    })

# man-hours by response type (TJ107 HYD-101 jobs)
cnd_mh = j107[j107.action_taken_code == "AT-CND"].man_hours
rr_mh = j107[j107.action_taken_code == "AT-RR"].man_hours
sps_fim = jobs_last[jobs_last.corrective_action_text.fillna("").str.contains("PHX-FIM-SPS")].man_hours
mh_stats = {
    "fim_hyd_cnd": {"median": round(float(cnd_mh.median()), 1), "n": int(len(cnd_mh)), "p25": round(float(cnd_mh.quantile(.25)), 1), "p75": round(float(cnd_mh.quantile(.75)), 1)},
    "task_hydp_rr": {"median": round(float(rr_mh.median()), 1), "n": int(len(rr_mh)), "p25": round(float(rr_mh.quantile(.25)), 1), "p75": round(float(rr_mh.quantile(.75)), 1)},
    "fim_sps_cnd": {"median": round(float(sps_fim.median()), 1), "n": int(len(sps_fim))},
}

# ------------------------------------------------------------------ suspect posterior (leaky noisy-OR prior, binomial update)
# Hypotheses: HYD_PUMP (SYS1 pump), AMAGB, IND (indication path: BHEEM EU channel / pressure switch / harness = leak).
# Prior: contract suspect_lrus isolation confidences 0.8 / 0.2, scaled by (1 - leak); leak = ASSUMPTION.
# Evidence: n_sf bench outcomes on pumps removed from SYS1, all RTOK.
# P(RTOK | pump faulty) = 1 - d (d = shop detection probability, ASSUMPTION); P(RTOK | pump healthy) = 1.
supp = [x for x in e107.suspect_lrus.iloc[-1]]
iso = {s["lru"]: float(s["isolation_confidence"]) for s in supp}


def posterior(d, leak, k=n_sf_rtok):
    pri = {"HYD_PUMP": iso["HYD_PUMP"] * (1 - leak), "AMAGB": iso["AMAGB"] * (1 - leak), "IND": leak}
    lik = {"HYD_PUMP": (1 - d) ** k, "AMAGB": 1.0, "IND": 1.0}
    z = sum(pri[h] * lik[h] for h in pri)
    return {h: pri[h] * lik[h] / z for h in pri}, pri


D0, L0 = 0.6, 0.20
post0, prior0 = posterior(D0, L0)
sweep_d = [0.3, 0.45, 0.6, 0.75, 0.9]
sweep_l = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
grid = []
for L in sweep_l:
    row = []
    for dd in sweep_d:
        p, _ = posterior(dd, L)
        order = sorted(p, key=lambda h: -p[h])
        row.append({"d": dd, "leak": L, "p": {h: p[h] for h in p}, "top": order[0]})
    grid.append(row)
pump_max = max(c["p"]["HYD_PUMP"] for r in grid for c in r)
flip_leak = iso["AMAGB"] / (1 + iso["AMAGB"])  # AMAGB*(1-L) = L  ->  L = a/(1+a)
# sequential trace of the pump share as bench outcomes arrive (central assumptions)
seq = [posterior(D0, L0, k)[0]["HYD_PUMP"] for k in range(0, n_sf_rtok + 1)]

# ------------------------------------------------------------------ next-best test: expected information gain per man-hour
S_T, FP_T = 0.7, 0.05  # ASSUMPTION: test sensitivity (swept 0.3-0.9) and false-positive rate


def H(p):
    return -sum(v * math.log2(v) for v in p.values() if v > 0)


def eig(p, sens_by_h):
    """sens_by_h[h] = P(test positive | h)."""
    pp = sum(p[h] * sens_by_h[h] for h in p)
    post_pos = {h: p[h] * sens_by_h[h] / pp for h in p} if pp > 0 else p
    pn = 1 - pp
    post_neg = {h: p[h] * (1 - sens_by_h[h]) / pn for h in p} if pn > 0 else p
    return H(p) - (pp * H(post_pos) + pn * H(post_neg)), pp


def tests(sens=S_T, fp=FP_T, d=D0):
    return [
        {"id": "T1", "name": "Indication-path isolation", "detail": "BHEEM EU channel · pressure switch · harness continuity",
         "proc": "PHX-FIM-HYD", "mh": mh_stats["fim_hyd_cnd"]["median"], "mh_n": mh_stats["fim_hyd_cnd"]["n"],
         "mh_src": "TJ107 PHX-FIM-HYD troubleshooting jobs", "sens": {"HYD_PUMP": fp, "AMAGB": fp, "IND": sens}},
        {"id": "T2", "name": "AMAGB drive check", "detail": "pad spline · oil · drive to SYS1 pump",
         "proc": "start-system FIM", "mh": mh_stats["fim_sps_cnd"]["median"], "mh_n": mh_stats["fim_sps_cnd"]["n"],
         "mh_src": "fleet PHX-FIM-SPS jobs (AMAGB sits in the start ambiguity group; no AMAGB jobs on record)",
         "sens": {"HYD_PUMP": fp, "AMAGB": sens, "IND": fp}},
        {"id": "T3", "name": "Remove and replace pump again", "detail": "status-quo response · bench test of removed unit",
         "proc": "PHX-TASK-HYDP", "mh": mh_stats["task_hydp_rr"]["median"], "mh_n": mh_stats["task_hydp_rr"]["n"],
         "mh_src": "TJ107 PHX-TASK-HYDP R/R jobs", "sens": {"HYD_PUMP": d, "AMAGB": 0.0, "IND": 0.0}},
    ]


def rank_tests(p, sens=S_T, fp=FP_T, d=D0):
    out = []
    for t in tests(sens, fp, d):
        g, ppos = eig(p, t["sens"])
        out.append({**{k: v for k, v in t.items() if k != "sens"}, "eig": g, "p_pos": ppos, "eig_per_mh": g / t["mh"]})
    return sorted(out, key=lambda x: -x["eig_per_mh"])


nbt = rank_tests(post0)
nbt_sweep = {}
for L in sweep_l:
    for sens in [0.3, 0.5, 0.7, 0.9]:
        pp, _ = posterior(D0, L)
        r = rank_tests(pp, sens=sens)
        nbt_sweep[f"{L}|{sens}"] = [x["id"] for x in r]
top_counts = {}
for v in nbt_sweep.values():
    top_counts[v[0]] = top_counts.get(v[0], 0) + 1

# ------------------------------------------------------------------ similar cases
def runs_detail(tail, code):
    s = sorties[sorties.tail_no == tail].sort_values("t_event")
    ev = set(bit[(bit.tail_no == tail) & (bit.event_code == code)].sortie_id)
    out, start, n = [], None, 0
    lst = list(s.itertuples())
    for i, r in enumerate(lst):
        if r.sortie_id in ev:
            if n == 0:
                start = r
            n += 1
        else:
            if n:
                out.append((start, lst[i - 1], n, r))
            n = 0
    if n:
        out.append((start, lst[-1], n, None))
    return out


sim = []
for start, end, n, brk in runs_detail(T, "HYD-101"):
    t0, t1 = start.t_event_dt - pd.Timedelta(hours=3), (brk.t_event_dt if brk is not None else SNAP)
    jj = j107[(j107.t_open_dt >= t0) & (j107.t_open_dt <= t1)]
    a = jj.action_taken_code.value_counts().to_dict()
    sim.append({"tail": T, "run": n, "from": start.t_event_dt.strftime("%d %b"), "to": end.t_event_dt.strftime("%d %b"),
                "break": None if brk is None else brk.sortie_id, "break_d": None if brk is None else brk.t_event_dt.strftime("%d %b"),
                "jobs": int(len(jj)), "rr": int(a.get("AT-RR", 0)), "cnd": int(a.get("AT-CND", 0)), "mh": round(float(jj.man_hours.sum()), 1)})

# TJ102 HYD-101 issue chain (D4: same tail+code within 10 days), from 9 Apr
e102 = bit[(bit.tail_no == "TJ102") & (bit.event_code == "HYD-101")].sort_values("t_ingest")
chain, last = [], None
for r in e102.itertuples():
    if last is None or (r.t_ingest_dt - last) > pd.Timedelta(days=10):
        chain = []
    chain.append(r)
    last = r.t_ingest_dt
s102 = sorties[(sorties.tail_no == "TJ102") & (sorties.t_event_dt >= chain[0].t_event if False else sorties.t_event_dt >= chain[0].t_occurrence_dt - pd.Timedelta(hours=2))]
j102 = code_jobs("TJ102", "HYD-10")
j102 = j102[j102.t_open_dt >= chain[0].t_occurrence_dt - pd.Timedelta(hours=1)]
a102 = j102.action_taken_code.value_counts().to_dict()
rem102 = m[(m.record_type == "COMPONENT_LIFE") & (m.part_no == "SYN-PN-HYDP") & (m.tail_no == "TJ102") & (m.install_action == "REMOVE")]
sim102 = {"tail": "TJ102", "since": chain[0].t_occurrence_dt.strftime("%d %b"), "events": len(chain), "sorties": int(len(s102)),
          "jobs": int(len(j102)), "rr": int(a102.get("AT-RR", 0)), "cnd": int(a102.get("AT-CND", 0)), "adm": int(a102.get("AT-ADM", 0)),
          "mh": round(float(j102.man_hours.sum()), 1), "removals_on_record": int(len(rem102)),
          "removals_since": int((rem102.t_event_dt >= chain[0].t_occurrence_dt).sum()),
          "shop_findings_matched": 0}

# procedure references on TJ107 HYD-101 jobs
refs = {}
for txt, job, t in zip(j107.corrective_action_text.fillna(""), j107.job_no, j107.t_close_dt):
    for ref in re.findall(r"PH-?X?-?[A-Z]+-[A-Z0-9]+", txt):
        if ref in ("PHX-FIM-HYD", "PHX-TASK-HYDP"):
            r0 = refs.setdefault(ref, {"n": 0, "last_job": None, "last": None})
            r0["n"] += 1
            if r0["last"] is None or (pd.notna(t) and t > r0["last"]):
                r0["last"], r0["last_job"] = t, job
for r0 in refs.values():
    r0["last"] = r0["last"].strftime("%d %b") if r0["last"] is not None else None

# ------------------------------------------------------------------ board items
def ev_list(tail, code, k):
    e = bit[(bit.tail_no == tail) & (bit.event_code == code)].sort_values("t_ingest").tail(k)
    return [{"rid": r.rid, "sortie": r.sortie_id, "t_occ": hm(r.t_occurrence_dt), "t_ingest": hm(r.t_ingest_dt), "sev": r.severity} for r in e.itertuples()]


def occ_10d(tail, code):
    """occurrences in the 10 days up to the latest ingested occurrence (P-DEC-01 input occ_10d)."""
    e = bit[(bit.tail_no == tail) & (bit.event_code == code)]
    if not len(e):
        return 0
    last = e.t_occurrence_dt.max()
    return int((e.t_occurrence_dt >= last - pd.Timedelta(days=10)).sum())


ev103 = ev_list("TJ103", "LGB-501", 2)
ev106 = ev_list("TJ106", "LGB-501", 2)
ev105 = [x for x in ev_list("TJ105", "SPS-501", 4)]
assert occ_10d("TJ105", "SPS-501") == 4

# P4 group: open advisory issues on CND-dominated codes recurring >= 2 in the last 10 days
iss = pd.read_csv(ROOT / "data" / "issues_asof_20260622.csv")
iss["last"] = pd.to_datetime(iss["last"])
open_iss = iss[iss["last"] >= SNAP - pd.Timedelta(days=10)]
p4codes = ["ENG-201", "AVI-201", "AVI-203", "AVI-204", "ADC-002", "ELE-405"]
p4 = []
POWER = {"ELE-405", "ENG-401"}  # D6: power-supply codes inhibit dependent LRU BIT fails in the same sortie
p4_inhibited = []
for r in open_iss[(open_iss.sev == "ADVISORY") & open_iss.code.isin(p4codes)].itertuples():
    k = occ_10d(r.tail, r.code)
    if k < 2:
        continue
    e = bit[(bit.tail_no == r.tail) & (bit.event_code == r.code)]
    e = e[e.t_occurrence_dt >= e.t_occurrence_dt.max() - pd.Timedelta(days=10)]
    pw = set(bit[(bit.tail_no == r.tail) & bit.event_code.isin(POWER)].sortie_id)
    if r.code not in POWER and set(e.sortie_id) <= pw:
        p4_inhibited.append({"tail": r.tail, "code": r.code, "by": "ELE-405/ENG-401 same sorties"})
        continue
    p4.append({"tail": r.tail, "code": r.code, "occ10": k, "n": int(r.n)})
p4_n = sum(code_out[c]["n"] for c in p4codes)
p4_codes_used = sorted({x["code"] for x in p4})

TJ108_EV = ["9531749ae89a0cc67c771e3f8c6803fb", "538009832804198691b4a8a246f0ae2d", "5c24ba776ce2bb1d588e6fc61e4ec084"]
TJ105_EV = ["5c6b07c27b7aaeebc11923c313ee33ec", "e05999a98367ee3af85c86c4598a0bfd", "72260e735c197742696b12a953e0a547",
            "0adf6ad884bdd7487e845dd618a1a0ba", "257b288af732947465ae434e627c14d0", "1dbebf4255b9efc25d700e8196ee1d83",
            "b8d779e5dc3de275964ea8f28d8862ee"]
# verify those ids exist and are ingested by the snapshot
for tail, ids in (("TJ108", TJ108_EV), ("TJ105", TJ105_EV)):
    sub = m[(m.tail_no == tail) & m.rid.isin(ids)]
    assert len(sub) == len(ids), (tail, len(sub))
    assert (sub.t_ingest_dt <= SNAP).all()
ing = {r: hm(t) for r, t in zip(m.rid, m.t_ingest_dt)}

# TJ108 demand age; TJ105 tyre landings since last install
dem = m[(m.tail_no == "TJ108") & (m.record_type == "SUPPLY_DEMAND") & (m.demand_no == "D-sulur-26093-0002")].sort_values("record_version")
dem_open = dem.iloc[0].t_event_dt
dem_age_d = round((SNAP - dem_open).total_seconds() / 86400, 1)
tyre_sorties = m[(m.tail_no == "TJ105") & m.rid.isin(TJ105_EV[1:])]
tyre_landings = int(tyre_sorties.landings.sum())
s105 = sorties[(sorties.tail_no == "TJ105") & (sorties.t_event_dt >= SNAP - pd.Timedelta(days=30))]
ldg_per_day_105 = round(float(s105.landings.sum()) / 30, 2)

tri = json.loads((ROOT / "data" / "triage_asof_20260622.json").read_text())

CO = code_out
items = [
    {"id": "TJ103-LGB-501", "band": "P1", "tail": "TJ103", "code": "LGB-501", "title": "Gear unsafe", "sev": "WARNING",
     "reason": f"WARNING recurred · {ev103[0]['t_occ'][:6]} and {ev103[1]['t_occ'][:6]}", "basis": "Gate G1 · WARNING recurs ≤ 10 d",
     "C": 3, "U": 3, "u_basis": "2nd WARNING in 4 d", "p": jeffreys(0, CO["LGB-501"]["n"]), "p_n": CO["LGB-501"]["n"], "conf": "med",
     "action": "TROUBLESHOOT", "params": {"code": "LGB-501"}, "rule": "P-DEC-01", "row": "r1", "rationale": "PFL_WARNING_RECURS",
     "evidence": ev103, "priority": "ROUTINE", "target_tail_no": "TJ103", "target_base": None, "auth": "AGENT", "mode": "consent"},
    {"id": "TJ106-LGB-501", "band": "P1", "tail": "TJ106", "code": "LGB-501", "title": "Gear unsafe", "sev": "WARNING",
     "reason": f"WARNING recurred · {ev106[0]['t_occ'][:6]} and {ev106[1]['t_occ'][:6]}", "basis": "Gate G1 · WARNING recurs ≤ 10 d",
     "C": 3, "U": 3, "u_basis": "2nd WARNING in 8 d", "p": jeffreys(0, CO["LGB-501"]["n"]), "p_n": CO["LGB-501"]["n"], "conf": "med",
     "action": "TROUBLESHOOT", "params": {"code": "LGB-501"}, "rule": "P-DEC-01", "row": "r1", "rationale": "PFL_WARNING_RECURS",
     "evidence": ev106, "priority": "ROUTINE", "target_tail_no": "TJ106", "target_base": None, "auth": "AGENT", "mode": "consent"},
    {"id": "TJ107-HYD-101", "band": "P2", "tail": "TJ107", "code": "HYD-101", "title": "Standing alarm", "sev": "CAUTION",
     "reason": f"{runs[-1]} consecutive flights · {len(rem)} removals, 0 confirmed", "basis": "P-DEC-01 r3 · D8 nuisance review",
     "C": 3, "U": 0, "u_basis": "FMC · 0 of 107 confirmed", "p": P_conf, "p_n": CO["HYD-101"]["n"], "conf": "high",
     "action": "TROUBLESHOOT", "params": {"code": "HYD-101"}, "rule": "P-DEC-01", "row": "r3", "rationale": "PERSIST_3_FLIGHTS",
     "evidence": evidence_hyd, "priority": "ROUTINE", "target_tail_no": "TJ107", "target_base": None, "auth": "AGENT", "mode": "consent",
     "second": {"action": "CHANGE_MONITORING_CONFIG", "params": {"filter_codes_add": ["HYD-101"]}, "auth": "HUMAN", "mode": "HUMAN-only draft",
                "rule": "P-DEC-01", "row": "D8", "rationale": "STANDING_NUISANCE_REVIEW"}},
    {"id": "TJ108-AOG-CHUTE", "band": "P2", "tail": "TJ108", "code": "SYN-PN-CHUTE", "title": "AOG brake chute", "sev": "NMCS",
     "reason": f"Grounded {round(dem_age_d):.0f} d · oldest open AOG demand", "basis": "AP lookup · C3 × U3",
     "C": 3, "U": 3, "u_basis": f"NMCS {dem_age_d:.0f} d", "p": None, "p_note": "observed", "conf": "high",
     "action": "EXPEDITE_SPARES", "params": {"demand_no": "D-sulur-26093-0002"}, "rule": "P-ORG-02", "row": "r2", "rationale": "AOG_NO_DONOR_EXPEDITE",
     "evidence": [{"rid": r, "t_ingest": ing[r]} for r in TJ108_EV], "priority": "AOG", "target_tail_no": "TJ108", "target_base": "sulur", "auth": "AGENT", "mode": "consent"},
    {"id": "TJ105-TYRE", "band": "P3", "tail": "TJ105", "code": "SYN-PN-TYRE", "title": "Tyre at limit", "sev": "LIFE",
     "reason": f"{tyre_landings} of 8 landings · next landing reaches limit", "basis": "AP lookup · C2 × U3",
     "C": 2, "U": 3, "u_basis": f"1 landing left · {ldg_per_day_105} ldg/d", "p": None, "p_note": "counted", "conf": "high",
     "action": "REQUISITION_SPARES", "params": {"part_no": "SYN-PN-TYRE", "quantity": 2}, "rule": "P-SPR-01", "row": "r1", "rationale": "LIFE_LANDINGS_REORDER",
     "evidence": [{"rid": r, "t_ingest": ing[r]} for r in TJ105_EV], "priority": "MCM", "target_tail_no": None, "target_base": "sulur", "auth": "AGENT", "mode": "consent"},
    {"id": "TJ105-SPS-501", "band": "P3", "tail": "TJ105", "code": "SPS-501", "title": "JFS start fail", "sev": "CAUTION",
     "reason": f"{len(ev105)}× in 10 d · {ev105[0]['t_occ'][:6]} to {ev105[-1]['t_occ'][:6]}", "basis": "AP lookup · C3 × U1",
     "C": 3, "U": 1, "u_basis": "4 in 10 d · starts recovered", "p": jeffreys(0, CO["SPS-501"]["n"]), "p_n": CO["SPS-501"]["n"], "conf": "med",
     "action": "TROUBLESHOOT", "params": {"code": "SPS-501"}, "rule": "P-DEC-01", "row": "AP", "rationale": "AP_C3_U1",
     "evidence": ev105, "priority": "ROUTINE", "target_tail_no": "TJ105", "target_base": None, "auth": "AGENT", "mode": "consent"},
    {"id": "P4-ADVISORY", "band": "P4", "tail": "5 tails", "code": " · ".join(p4_codes_used), "title": f"{len(p4)} advisory issues", "sev": "ADVISORY",
     "reason": "CND-dominated codes · grouped by root cause", "basis": "P-DEC-01 r5 · RECUR_NOFAULT_DOMINATED",
     "C": 1, "U": 0, "u_basis": "advisory · no mission effect", "p": jeffreys(0, p4_n), "p_n": p4_n, "conf": "high",
     "action": "MONITOR", "params": None, "rule": "P-DEC-01", "row": "r5", "group": p4, "auth": None, "mode": "monitor"},
]
items[-1]["tail"] = f"{len({x['tail'] for x in p4})} tails"


def order_id(rule, semver, tail, action, params, evidence):
    h = hashlib.blake2b(canon({"parameters": params, "evidence": sorted(evidence)}).encode(), digest_size=8).hexdigest()
    return f"phx:{rule}:{semver}:{EPOCH.strftime('%Y%m%dT%H%M')}:{tail}:{action}:{h}", h


SEMVER = {"P-DEC-01": "1.4.0", "P-ORG-02": "1.2.0", "P-SPR-01": "1.0.0"}
POLV = {"P-DEC-01": "P-DEC-01/1.4.0+jdm.3f9c0d7a", "P-ORG-02": "P-ORG-02/1.2.0+jdm.71b0e4c2", "P-SPR-01": "P-SPR-01/1.0.0+jdm.c5a91d08"}
orders = []
for it in items:
    if it["action"] == "MONITOR":
        continue
    evs = [e["rid"] for e in it["evidence"]]
    oid, h = order_id(it["rule"], SEMVER[it["rule"]], it["tail"], it["action"], it["params"], evs)
    o = {"order_id": oid, "digest": h, "item": it["id"], "band": it["band"], "action": it["action"], "parameters": it["params"],
         "issuer_kind": "AGENT", "issuer_id": "PHALANX-PDM-AGENT", "policy_version": POLV[it["rule"]],
         "priority": it["priority"], "target_tail_no": it["target_tail_no"], "target_base": it["target_base"],
         "evidence": evs, "rule": it["rule"], "row": it["row"], "tail": it["tail"]}
    it["order_id"] = oid
    orders.append(o)
    if it.get("second"):
        s = it["second"]
        oid2, h2 = order_id(s["rule"], SEMVER[s["rule"]], it["tail"], s["action"], s["params"], evs)
        orders.append({"order_id": oid2, "digest": h2, "item": it["id"], "band": it["band"], "action": s["action"], "parameters": s["params"],
                       "issuer_kind": "HUMAN", "issuer_id": "HUMAN-ENGG-OFFICER", "policy_version": None, "priority": "ROUTINE",
                       "target_tail_no": it["target_tail_no"], "target_base": None, "evidence": evs, "rule": s["rule"], "row": s["row"], "tail": it["tail"]})
        s["order_id"] = oid2
for o in orders:
    o["evidence_max_ingest"] = max(ing.get(r) or hm(bit[bit.rid == r].t_ingest_dt.iloc[0]) for r in o["evidence"]) if False else None
    # latest t_ingest among the evidence (strictly from the as-of store)
    ts = []
    for r in o["evidence"]:
        x = bit[(bit.rid == r)]
        if len(x):
            ts.append(x.t_ingest_dt.iloc[0])
        else:
            ts.append(m[m.rid == r].t_ingest_dt.iloc[0])
    o["evidence_latest_ingest"] = hm(max(ts))
    o["evidence_all_ingested"] = bool(max(ts) <= SNAP)

out = {
    "asof": "2026-06-22 06:00 IST", "epoch": "2026-06-22 08:00 IST",
    "snapshot": {"hash": snapshot_hash, "algo": "sha256(canonical_json({topic: sorted('tail:record_id')}))", "counts": snap_counts,
                 "records": int(sum(snap_counts.values()))},
    "load": {"bit_events": tri["events_total"], "cautions": tri["cautions_total"], "alert_rows": tri["events_total"] + tri["cautions_total"],
             "issues": tri["issues_total"], "open": tri["issues_open"], "items": len(items), "budget": 10,
             "bands": {"P1": 2, "P2": 2, "P3": 2, "P4": 1}, "p4_issues": len(p4), "p4_inhibited": p4_inhibited},
    "code_outcomes": code_out, "confirmed_shop_findings_fleet": confirmed_shop,
    "items": items, "orders": orders,
    "tj107": {
        "sorties": len(sids), "fired": int(sum(fired)), "runs": runs, "events": int(len(e107)), "gr_events": gr_events,
        "jobs": int(len(j107)), "mh": round(mh107, 1), "actions": {str(k): int(v) for k, v in ac107.items()},
        "removal_records": int(len(rem)), "rr_jobs": len(rr_jobs), "rr_jobs_without_cl": [r["job"] for r in rr_jobs if not r["cl_record"]],
        "serials_on_record": serials_on_record, "serial_values_on_remove": serial_values_on_remove, "sys1_serials": distinct_sys1,
        "shop": {"n": n_sf, "rtok": n_sf_rtok, "matched_tj107": len(sf_tj107)},
        "p_confirmed": P_conf, "p_rtok": P_rtok, "evidence": evidence_hyd,
        "inferred_install_jobs": inferred_jobs,
        "strip": strip, "removal_marks": removal_marks, "lanes": lanes, "mh_stats": mh_stats,
        "posterior": {"prior": prior0, "post": post0, "d": D0, "leak": L0, "iso": iso, "grid": grid, "sweep_d": sweep_d, "sweep_leak": sweep_l,
                      "pump_max_over_sweep": pump_max, "flip_leak": flip_leak, "seq_pump": seq},
        "nbt": nbt, "nbt_top_counts": top_counts, "nbt_sens": S_T, "nbt_fp": FP_T,
        "similar": sim, "tj102": sim102, "refs": refs,
    },
    "tj108": {"demand_open": dem_open.strftime("%d %b %H:%M"), "age_d": dem_age_d},
    "tj105": {"tyre_landings": tyre_landings, "ldg_per_day": ldg_per_day_105},
}
OUT.write_text(json.dumps(out, indent=1, default=str))
print("wrote", OUT)
print("snapshot", snapshot_hash, snap_counts)
print("tj107", {k: out["tj107"][k] for k in ["sorties", "fired", "runs", "events", "jobs", "mh", "actions", "removal_records", "rr_jobs", "rr_jobs_without_cl", "shop", "sys1_serials", "inferred_install_jobs"]})
print("P_conf", P_conf, "P_rtok", P_rtok)
print("post0", post0, "pump_max", pump_max, "flip", flip_leak)
print("nbt", [(x["id"], round(x["eig"], 3), x["mh"], round(x["eig_per_mh"], 4)) for x in nbt], top_counts)
print("mh_stats", mh_stats)
print("lanes", json.dumps(lanes, indent=0, default=str)[:3000])
print("similar", sim, sim102)
print("refs", refs)
print("p4", len(p4), p4, p4_n, "inhibited", p4_inhibited)
print("code_out", code_out)
for o in orders:
    print(o["order_id"], o["evidence_latest_ingest"], o["evidence_all_ingested"])
for it in items:
    print(it["id"], it["band"], it["C"], it["U"], it.get("p"), it.get("p_n"))
print("tyre", tyre_landings, ldg_per_day_105, "dem", dem_open, dem_age_d)
