"""G3 evidence for cnd-clf 2.3.0: decision-level CRN-paired forks at earlier epochs (before promotion).

At epoch E (08:00 IST) on the TJ107 world, the decision path driven by the champion finding (HYD-101 no-fault
rate -> P-DEC-01 r3 -> TROUBLESHOOT indication path + HUMAN CHANGE_MONITORING_CONFIG draft) is compared with the
status quo (ScheduledPolicy scheduled/1.0.0) on n CRN pairs in belief mode over a 30-day horizon, exactly as the
S1 scenario does at 22 Jun, but at E = 1, 8 and 15 Jun. Orders cite the six most recent HYD-101 BIT events
ingested by E. Uses the fork helpers in video/tools/forks (read-only data-layer code).

Run: video/tools/forks/run.sh video/data/scripts/assure_g3_forks.py 2026-06-08 [n]
"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "forks"))
import numpy as np
from phx_forks import DAY, BranchSpec, TailWorld, belief_posterior, fmt_ist, iso_utc, ist_ns, order, order_json, timed_run
from phalanx.orders.policies import ScheduledPolicy

y, mo, d = map(int, sys.argv[1].split("-"))
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20
T0 = ist_ns(y, mo, d, 8)
H = 30 * DAY
tail = "TJ107"
w0 = time.perf_counter()
tw = TailWorld(tail, 205)
sess, info = tw.run_reference(T0)
snap = tw.fs.snapshot(sess)
bit = sess.obs.as_of(T0, "events.bit_faults").to_pylist()
hyd = sorted((r for r in bit if r["tail_no"] == tail and r["event_code"] == "HYD-101"), key=lambda r: (r["t_ingest"], r["record_id"]))
ev = [r["record_id"] for r in hyd[-6:]]
stamp = iso_utc(T0).replace("-", "").replace(":", "")
orders = [
    order(order_id=f"phx-g3:{stamp}:troubleshoot", issuer_id="PHALANX-PDM-AGENT", issuer_kind="AGENT", t_issued=T0,
          action="TROUBLESHOOT", parameters={"code": "HYD-101"}, target_tail_no=tail, evidence=ev,
          policy_version="phalanx-solution-demo/0.1"),
    order(order_id=f"phx-g3:{stamp}:monitoring-config", issuer_id="HUMAN-ENGG-OFFICER", issuer_kind="HUMAN", t_issued=T0,
          action="CHANGE_MONITORING_CONFIG", parameters={"filter_codes_add": ["HYD-101"]}, target_tail_no=tail, evidence=ev),
]
probe = tw.fs.fork(snap, BranchSpec("probe", mode="ensemble", member=0))
pre = [(r.order_id, r.verdict, r.reason) for r in probe.submit(orders)]
del probe
runs_sq, runs_tr = [], []
for m in range(N):
    bel = belief_posterior()
    r_sq, _ = timed_run(tw, snap, BranchSpec("g3-sq", policy=ScheduledPolicy(), mode="belief", member=m, belief=bel), H)
    r_tr, _ = timed_run(tw, snap, BranchSpec("g3-tr", orders=tuple(orders), policy=ScheduledPolicy(), mode="belief", member=m, belief=bel), H)
    r_sq.session = None; r_tr.session = None
    runs_sq.append(r_sq); runs_tr.append(r_tr)
    print(sys.argv[1], m, flush=True)
diffs = tw.fs.compare(runs_tr, runs_sq, paired=True)
out = dict(epoch=fmt_ist(T0), tail=tail, snapshot_id=snap.id, n_pairs=N, mode="belief", horizon_days=30,
           hyd101_ingested_by_epoch=len(hyd), orders=[order_json(o) for o in orders], gateway=pre,
           paired={x.kpi: dict(mean=x.mean, ci_low=x.ci_low, ci_high=x.ci_high, n=x.n) for x in diffs},
           order_log_hashes=[r.order_log_hash for r in runs_tr], wall_s=round(time.perf_counter() - w0, 1))
p = Path(__file__).resolve().parents[1] / f"assure_g3_fork_{sys.argv[1]}.json"
p.write_text(json.dumps(out, indent=1, default=str))
print("wrote", p, {k: (round(v["mean"], 3), round(v["ci_low"], 3), round(v["ci_high"], 3)) for k, v in out["paired"].items() if k in ("mc", "man_hours", "in_flight_failures")})
