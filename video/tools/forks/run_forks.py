"""Step 2: CRN-paired what-if forks for the three showcase decisions (S1-S3).

Usage: ./run.sh run_forks.py S1 [--n 30] [--modes belief,ensemble] [--horizon-days 30]
Writes ``video/data/forks/scenario_<S>.json`` (per-member KPIs of both arms, paired differences, orders,
evidence, verdicts, timings). ``assemble.py`` merges the scenario files into ``results.json``.

Each scenario: rebuild the preview tail world (``phx_forks.TailWorld``), run the preview's closed loop to the
decision epoch 2026-06-22 08:00 IST, snapshot, build the orders from the observation set as of the epoch only,
then for members m = 0..n-1 run both arms from the snapshot (member m of both arms shares one exogenous
future: CRN), and compare with ``ForkService.compare(paired=True)``.

Arms: status quo = ``ScheduledPolicy`` (scheduled/1.0.0, exactly the preview's policy) at every decision
epoch of the window and no extra orders; treatment = the same policy plus the scenario's orders issued at the
epoch. A single oracle status-quo run is also made, only to validate that the fork continues the published
preview bit for bit (it is never reported as a what-if number).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from phx_forks import (
    DAY,
    NS,
    PREVIEW_FLEET,
    BranchSpec,
    TailWorld,
    belief_posterior,
    bp,
    fmt_ist,
    iso_utc,
    ist_ns,
    order,
    order_json,
    timed_run,
)
from phalanx.fork.kpi import Kpis, availability_series
from phalanx.orders.policies import ScheduledPolicy

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "data" / "forks"
T0 = ist_ns(2026, 6, 22, 8)
FORK_DAYS = 205
AGENT_ID = "PHALANX-PDM-AGENT"
AGENT_POLICY = "phalanx-solution-demo/0.1"
HUMAN_ID = "HUMAN-ENGG-OFFICER"
SCENARIO_TAIL = {"S1": "TJ107", "S2": "TJ108", "S3": "TJ105"}
SCENARIO_KPIS = {
    "S1": ["man_hours", "nmcs", "nmcm", "mc", "fmc", "aog_days", "in_flight_failures", "cost", "flown_fh"],
    "S2": ["aog_days", "nmcs", "mc", "flown_fh", "cost", "fmc", "nmcm"],
    "S3": ["nmcs", "aog_days", "mc", "fmc", "nmcm", "flown_fh", "cost"],
}


def _latest(rows: list[dict]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for r in rows:
        k = (r["record_type"], r["record_key"])
        if k not in out or r["record_version"] > out[k]["record_version"]:
            out[k] = r
    return out


def _oid(scn: str, tag: str) -> str:
    return f"phx-demo:{scn}:{iso_utc(T0).replace('-', '').replace(':', '')}:{tag}"


# ---------------------------------------------------------------------------------------- order builders
def orders_s1(s, tail: str) -> tuple[list, dict]:
    """TJ107: HUMAN filter HYD-101 + AGENT troubleshoot HYD-101, citing the latest HYD-101 BIT events."""
    bit = s.obs.as_of(T0, "events.bit_faults").to_pylist()
    hyd = sorted(
        (r for r in bit if r["tail_no"] == tail and r["event_code"] == "HYD-101"),
        key=lambda r: (r["t_ingest"], r["record_id"]),
    )
    latest = hyd[-6:]  # the six most recent (three sorties' worth, 2026-06-11..06-18)
    ev = [r["record_id"] for r in latest]
    o_ts = order(
        order_id=_oid("S1", "troubleshoot"),
        issuer_id=AGENT_ID,
        issuer_kind="AGENT",
        t_issued=T0,
        action="TROUBLESHOOT",
        parameters={"code": "HYD-101"},
        priority="ROUTINE",
        target_tail_no=tail,
        evidence=ev,
        policy_version=AGENT_POLICY,
    )
    o_cfg = order(
        order_id=_oid("S1", "monitoring-config"),
        issuer_id=HUMAN_ID,
        issuer_kind="HUMAN",
        t_issued=T0,
        action="CHANGE_MONITORING_CONFIG",
        parameters={"filter_codes_add": ["HYD-101"]},
        priority="ROUTINE",
        target_tail_no=tail,
        evidence=ev,
    )
    ctx = {
        "hyd101_bit_events_ingested_by_epoch": len(hyd),
        "evidence_events": [
            {
                "record_id": r["record_id"].hex(),
                "topic": "events.bit_faults",
                "event_code": r["event_code"],
                "severity": r["severity"],
                "sortie_id": r["sortie_id"],
                "t_occurrence_ist": fmt_ist(r["t_occurrence"]),
                "t_ingest_ist": fmt_ist(r["t_ingest"]),
            }
            for r in latest
        ],
    }
    return [o_ts, o_cfg], ctx


def orders_s2(s, tail: str) -> tuple[list, dict]:
    """TJ108: AGENT expedite the AOG demand that holds the U/S (grounding) job named in the latest tech log."""
    rows = s.obs.as_of(T0, "maint.records").to_pylist()
    lat = _latest(rows)
    tl = max(
        (r for r in rows if r["record_type"] == "TECH_LOG" and r["tail_no"] == tail),
        key=lambda r: (r["t_event"], r["record_version"]),
    )
    us = set()
    for part in (tl["limitations_text"] or "").split(";"):
        part = part.strip()
        if part.startswith("U/S:"):
            us |= set(part[4:].split())
    open_aog = sorted(
        (
            r
            for (rt, _), r in lat.items()
            if rt == "SUPPLY_DEMAND" and r["status"] != "CLOSED" and r["priority"] == "AOG" and r["tail_no"] == tail
        ),
        key=lambda r: (r["t_open"] or r["t_event"], r["demand_no"]),
    )
    open_jobs = {r["job_no"]: r for (rt, _), r in lat.items() if rt == "DEFECT_WO" and r["status"] != "CLOSED"}
    candidates = [r for r in open_aog if r["job_no"] in us and r["job_no"] in open_jobs]
    if not candidates:
        raise RuntimeError("no open AOG demand holding a U/S job")
    dem = candidates[0]
    job = open_jobs[dem["job_no"]]
    ev = [dem["record_id"], job["record_id"], tl["record_id"]]
    o = order(
        order_id=_oid("S2", "expedite"),
        issuer_id=AGENT_ID,
        issuer_kind="AGENT",
        t_issued=T0,
        action="EXPEDITE_SPARES",
        parameters={"demand_no": dem["demand_no"]},
        priority="AOG",
        target_tail_no=tail,
        target_base=dem["base"],
        evidence=ev,
        policy_version=AGENT_POLICY,
    )
    ctx = {
        "tech_log_at_epoch": {
            "t_event_ist": fmt_ist(tl["t_event"]),
            "availability_state": tl["availability_state"],
            "limitations_text": tl["limitations_text"],
        },
        "open_aog_demands_in_consumer_view": [
            {
                "demand_no": r["demand_no"],
                "part_no": r["part_no"],
                "job_no": r["job_no"],
                "t_open_ist": fmt_ist(r["t_open"] or r["t_event"]),
                "job_open": r["job_no"] in open_jobs,
                "job_us_in_tech_log": r["job_no"] in us,
            }
            for r in open_aog
        ],
        "selected_demand": {
            "demand_no": dem["demand_no"],
            "part_no": dem["part_no"],
            "job_no": dem["job_no"],
            "job_text": job["discrepancy_text"],
            "t_open_ist": fmt_ist(dem["t_open"] or dem["t_event"]),
            "why": "oldest open AOG demand whose job is still open and is the U/S (grounding) entry of the "
            "latest TECH_LOG record; older 'open' AOG demands in the consumer view belong to closed jobs "
            "(stale or lagged supply records, a deliberate data-quality defect)",
        },
        "evidence_records": [
            {"record_id": dem["record_id"].hex(), "record_type": "SUPPLY_DEMAND", "key": dem["record_key"]},
            {"record_id": job["record_id"].hex(), "record_type": "DEFECT_WO", "key": job["record_key"]},
            {"record_id": tl["record_id"].hex(), "record_type": "TECH_LOG", "key": tl["record_key"]},
        ],
    }
    return [o], ctx


def orders_s3(s, tail: str) -> tuple[list, dict]:
    """TJ105: AGENT requisition two main-wheel tyres for the base before the fitted tyres reach hard time."""
    rows = s.obs.as_of(T0, "maint.records").to_pylist()
    inst = sorted(
        (
            r
            for r in rows
            if r["record_type"] == "COMPONENT_LIFE"
            and r["part_no"] == "SYN-PN-TYRE"
            and r["install_action"] == "INSTALL"
            and r["tail_no"] == tail
        ),
        key=lambda r: (r["t_event"], r["record_id"]),
    )
    last = inst[-1]
    sorties = sorted(
        (r for r in rows if r["record_type"] == "SORTIE" and r["tail_no"] == tail and r["t_event"] > last["t_event"]),
        key=lambda r: r["t_event"],
    )
    landings = sum(int(r["landings"] or 0) for r in sorties)
    life = int(next(c for c in bp_catalogue().classes if c.part_no == "SYN-PN-TYRE").v("life_landings"))
    ev = [last["record_id"], *[r["record_id"] for r in sorties]]
    o = order(
        order_id=_oid("S3", "requisition-tyres"),
        issuer_id=AGENT_ID,
        issuer_kind="AGENT",
        t_issued=T0,
        action="REQUISITION_SPARES",
        parameters={"part_no": "SYN-PN-TYRE", "quantity": 2},
        priority="MCM",
        target_base=last["base"],
        target_tail_no=None,
        evidence=ev,
        policy_version=AGENT_POLICY,
    )
    ctx = {
        "last_tyre_install": {
            "record_id": last["record_id"].hex(),
            "serial_no": last["serial_no"],
            "t_event_ist": fmt_ist(last["t_event"]),
        },
        "landings_since_last_tyre_install": landings,
        "tyre_life_landings_catalogue": life,
        "sorties_since_install": [
            {"record_id": r["record_id"].hex(), "sortie_id": r["sortie_id"], "landings": r["landings"]} for r in sorties
        ],
        "lever_choice": "REQUISITION_SPARES raises base stock (M18 _o_requisition_spares -> supply demands); "
        "WASH_SERVICE TYRES only resets M10 tyre pressure-loss states (servicing), it does not renew tyre "
        "landing life, so it is not the lever for a hard-time tyre change",
        "priority_choice": "MCM (lead-time multiplier 1.5; M18 replenishes consumed spares at MCM); "
        "ROUTINE would map to PHU (2.5x), AOG (1.0x) is reserved for an aircraft on ground",
    }
    return [o], ctx


def bp_catalogue():
    from phalanx.maintenance import load_m18_config

    return load_m18_config().catalogue


BUILDERS = {"S1": orders_s1, "S2": orders_s2, "S3": orders_s3}


# ---------------------------------------------------------------------------------------- diagnostics
def order_outcomes(sess, order_ids: list[str], t1: int) -> dict[str, Any]:
    st = sess.obs.as_of(t1, "orders.status").to_pylist()
    out = {}
    for oid in order_ids:
        rows = sorted((r for r in st if r["order_id"] == oid), key=lambda r: r["status_seq"])
        out[oid] = [
            {"status": r["status"], "reason": r["reason"], "t_status_ist": fmt_ist(r["t_status"])} for r in rows
        ]
    return out


def nmcs_exit(sess, tail: str, t0: int, t1: int) -> str | None:
    """First instant in [t0, t1) the tail leaves NMCS (from AVAILABILITY_STATE, as the KPIs use them)."""
    from phalanx.maintenance import scir

    ser = availability_series(sess.log).get(tail, [])
    cur = None
    for b, s in ser:
        if b <= t0:
            cur = s
            continue
        if b >= t1:
            break
        if cur == scir.NMCS and s != scir.NMCS:
            return fmt_ist(b)
        cur = s
    return None


def removals(sess, tail: str, t0: int, t1: int) -> dict[str, Any]:
    """Component removals in [t0, t1): COMPONENT_LIFE REMOVE rows of the branch record log (the same log the
    data layer's compute_kpis reads). A derived count; not a fork-service KPI."""
    by: dict[str, int] = {}
    for r in sess.log.rows("maint.records"):
        if (
            r["record_type"] == "COMPONENT_LIFE"
            and r["install_action"] == "REMOVE"
            and r["tail_no"] == tail
            and t0 <= int(r["t_event"]) < t1
        ):
            by[r["part_no"]] = by.get(r["part_no"], 0) + 1
    return {"total": sum(by.values()), "by_part_no": dict(sorted(by.items()))}


def tyre_jobs(sess, tail: str, t0: int, t1: int) -> dict[str, Any]:
    rows = sess.obs.as_of(t1, "maint.records").to_pylist()
    lat = _latest(rows)
    jobs = [
        r
        for (rt, _), r in lat.items()
        if rt in ("DEFECT_WO", "INSPECTION")
        and r["tail_no"] == tail
        and r["part_no"] == "SYN-PN-TYRE"
        and (r["t_open"] or 0) >= t0
    ]
    awp = set()
    for r in rows:
        if r["record_type"] in ("DEFECT_WO", "INSPECTION") and r["tail_no"] == tail and r["status"] == "AWAITING_PARTS":
            if r["part_no"] == "SYN-PN-TYRE" and t0 <= r["t_event"] < t1:
                awp.add(r["job_no"])
    return {"tyre_jobs_opened": len(jobs), "tyre_jobs_awaiting_parts": len(awp)}


# ---------------------------------------------------------------------------------------- statistics
def arm_summary(values: np.ndarray, level: float = 0.95) -> dict[str, float]:
    from scipy.stats import t as student_t

    n = values.size
    mean = float(values.mean())
    sd = float(values.std(ddof=1)) if n > 1 else 0.0
    if n < 3 or sd == 0.0:
        half = 0.0 if n >= 3 else math.inf
    else:
        half = float(student_t.ppf(0.5 + level / 2, n - 1)) * sd / math.sqrt(n)
    return {"mean": mean, "sd": sd, "ci_low": mean - half, "ci_high": mean + half, "n": int(n)}


def diff_json(d) -> dict[str, float]:
    return {"n": d.n, "mean": d.mean, "sd": d.sd, "ci_low": d.ci_low, "ci_high": d.ci_high}


# ---------------------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=sorted(BUILDERS))
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--modes", default="belief,ensemble")
    ap.add_argument("--horizon-days", type=int, default=30)
    ap.add_argument("--no-oracle-check", action="store_true")
    ap.add_argument("--fleet-days", type=int, default=FORK_DAYS, help="scenario length the world is built with")
    ap.add_argument("--tag", default="", help="output file suffix (supplementary runs)")
    a = ap.parse_args()
    scn, tail = a.scenario, SCENARIO_TAIL[a.scenario]
    horizon = a.horizon_days * DAY
    OUT.mkdir(parents=True, exist_ok=True)
    wall0 = time.perf_counter()

    if (T0 - ist_ns(2026, 1, 5, 5, 30)) + horizon > a.fleet_days * DAY:
        raise SystemExit("--fleet-days too short for the horizon (no sorties would be planned)")
    tw = TailWorld(tail, a.fleet_days)
    sess, ref_info = tw.run_reference(T0)
    snap = tw.fs.snapshot(sess)
    orders, ctx = BUILDERS[scn](sess, tail)
    oids = [o.order_id for o in orders]
    t0k = tw.kernel(T0)
    t1_utc = T0 + horizon
    doc: dict[str, Any] = {
        "scenario": scn,
        "tail": tail,
        "label": "PREVIEW v0.9 simulator, synthetic fleet, behaviour not validated",
        "epoch": {"t_utc_ns": T0, "utc": iso_utc(T0), "ist": fmt_ist(T0)},
        "horizon_days": a.horizon_days,
        "window": {"start_ist": fmt_ist(T0), "end_ist": fmt_ist(t1_utc)},
        "snapshot_id": snap.id,
        "snapshot_t_kernel_ns": snap.t,
        "root_seed": hex(bp.FLEET_ROOT),
        "scenario_key": bp.FLEET_SCENARIO,
        "fleet_days_built": a.fleet_days,
        "status_quo": "ScheduledPolicy scheduled/1.0.0 at every 08:00 IST decision epoch, no extra orders",
        "treatment": "ScheduledPolicy scheduled/1.0.0 + the orders below, issued at the epoch",
        "orders": [order_json(o) for o in orders],
        "decision_context": ctx,
        "wall_s": {"run_to_epoch": ref_info["wall_s"]},
        "modes": {},
    }
    # gateway pre-check on a throwaway restore (so a rejected order fails loudly before the replicates)
    probe = tw.fs.fork(snap, BranchSpec("probe", mode="ensemble", member=0))
    pre = probe.submit(orders)
    doc["gateway_verdicts_at_epoch"] = [
        {"order_id": r.order_id, "verdict": r.verdict, "reason": r.reason, "t_apply_ist": fmt_ist(tw.epoch + r.t_apply) if r.t_apply is not None else None}
        for r in pre
    ]
    del probe
    if any(r.verdict != "ACCEPTED" for r in pre):
        raise SystemExit(f"order not accepted: {doc['gateway_verdicts_at_epoch']}")

    # oracle continuation check (validation only): status quo, true state, same root
    if not a.no_oracle_check:
        w = time.perf_counter()
        r_or = tw.fs.run(snap, BranchSpec("sq-oracle", policy=ScheduledPolicy(), mode="oracle"), horizon, keep_session=True)
        or_s = time.perf_counter() - w
        doc["oracle_continuation_check"] = oracle_check(r_or.session, tail, t1_utc) | {"wall_s": round(or_s, 2)}
        del r_or

    for mode in a.modes.split(","):
        runs_sq, runs_tr, members = [], [], []
        w_mode = time.perf_counter()
        for m in range(a.n):
            belief = belief_posterior() if mode == "belief" else None
            sq_spec = BranchSpec(f"{scn}-sq", policy=ScheduledPolicy(), mode=mode, member=m, belief=belief)
            tr_spec = BranchSpec(f"{scn}-tr", orders=tuple(orders), policy=ScheduledPolicy(), mode=mode, member=m, belief=belief)
            r_sq, t_sq = timed_run(tw, snap, sq_spec, horizon)
            r_tr, t_tr = timed_run(tw, snap, tr_spec, horizon)
            rec = {
                "member": m,
                "root": hex(r_sq.root),
                "wall_s": {"status_quo": round(t_sq, 3), "treatment": round(t_tr, 3), "pair": round(t_sq + t_tr, 3)},
                "status_quo": r_sq.kpis.as_dict(),
                "treatment": r_tr.kpis.as_dict(),
                "record_digest": {"status_quo": r_sq.record_digest, "treatment": r_tr.record_digest},
                "order_log_hash": {"status_quo": r_sq.order_log_hash, "treatment": r_tr.order_log_hash},
                "gateway_verdicts": [
                    {"order_id": x.order_id, "verdict": x.verdict, "reason": x.reason}
                    for x in r_tr.submissions
                    if x.order_id in oids
                ],
                "order_status": order_outcomes(r_tr.session, oids, t1_utc),
            }
            rec["removals"] = {
                "status_quo": removals(r_sq.session, tail, T0, t1_utc),
                "treatment": removals(r_tr.session, tail, T0, t1_utc),
            }
            if scn == "S2":
                rec["nmcs_exit"] = {
                    "status_quo": nmcs_exit(r_sq.session, tail, T0, t1_utc),
                    "treatment": nmcs_exit(r_tr.session, tail, T0, t1_utc),
                }
            if scn == "S3":
                rec["tyre_jobs"] = {
                    "status_quo": tyre_jobs(r_sq.session, tail, T0, t1_utc),
                    "treatment": tyre_jobs(r_tr.session, tail, T0, t1_utc),
                }
            r_sq.session = None
            r_tr.session = None
            runs_sq.append(r_sq)
            runs_tr.append(r_tr)
            members.append(rec)
            print(f"{scn} {mode} m={m} sq={t_sq:.1f}s tr={t_tr:.1f}s", flush=True)
        diffs = tw.fs.compare(runs_tr, runs_sq, paired=True)  # treatment - status quo
        kpi_block = {}
        for d in diffs:
            xa = np.array([getattr(r.kpis, d.kpi) for r in runs_tr], dtype=np.float64)
            xb = np.array([getattr(r.kpis, d.kpi) for r in runs_sq], dtype=np.float64)
            kpi_block[d.kpi] = {
                "status_quo": arm_summary(xb),
                "treatment": arm_summary(xa),
                "paired_difference_treatment_minus_status_quo": diff_json(d),
            }
        from phalanx.fork.service import paired_difference

        rv_tr = np.array([x["removals"]["treatment"]["total"] for x in members], dtype=np.float64)
        rv_sq = np.array([x["removals"]["status_quo"]["total"] for x in members], dtype=np.float64)
        d_rv = paired_difference(
            "removals", rv_tr, rv_sq, level=tw.fs.m22.ci_level, paired=True, min_pairs=tw.fs.m22.min_pairs
        )
        derived = {
            "removals": {
                "definition": "component removals in the window (COMPONENT_LIFE REMOVE rows of the branch record "
                "log); derived here, not a fork-service KPI; same paired statistics as ForkService.compare",
                "status_quo": arm_summary(rv_sq),
                "treatment": arm_summary(rv_tr),
                "paired_difference_treatment_minus_status_quo": diff_json(d_rv),
            }
        }
        sub = {}
        if a.n > 10:  # the first 10 pairs (members 0-9), as originally requested
            d10 = tw.fs.compare(runs_tr[:10], runs_sq[:10], paired=True)
            sub = {d.kpi: diff_json(d) for d in d10}
        pair_walls = [x["wall_s"]["pair"] for x in members]
        branch_walls = [x["wall_s"]["status_quo"] for x in members] + [x["wall_s"]["treatment"] for x in members]
        doc["modes"][mode] = {
            "mode": mode,
            "mode_note": MODE_NOTES[mode],
            "n_pairs": a.n,
            "kpis": kpi_block,
            "derived": derived,
            "headline_kpis": SCENARIO_KPIS[scn],
            "paired_difference_first_10_pairs": sub,
            "wall_s": {
                "mode_total": round(time.perf_counter() - w_mode, 2),
                "per_branch_mean": round(float(np.mean(branch_walls)), 3),
                "per_branch_max": round(float(np.max(branch_walls)), 3),
                "per_pair_mean": round(float(np.mean(pair_walls)), 3),
                "per_pair_max": round(float(np.max(pair_walls)), 3),
            },
            "members": members,
        }
    doc["wall_s"]["total"] = round(time.perf_counter() - wall0, 2)
    doc["kpi_definitions"] = KPI_DEFS
    (OUT / f"scenario_{scn}{a.tag}.json").write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({m: {k: v["paired_difference_treatment_minus_status_quo"] for k, v in d["kpis"].items() if k in SCENARIO_KPIS[scn]} for m, d in doc["modes"].items()}, indent=1))


def oracle_check(sess, tail: str, t1_utc: int) -> dict[str, Any]:
    """Validation only: the oracle status-quo branch must reproduce the published preview records after the
    epoch (to the preview's end, day 180 = 2026-07-04 00:00 UTC; the fork world is built longer)."""
    import pyarrow.compute as pc
    import pyarrow.dataset as dset

    from reproduce import canon

    t_end = tw_epoch_end()
    out = {}
    for topic in ("maint.records", "events.bit_faults", "events.cautions"):
        spec = bp._contract().topics[topic]
        ing = spec.ingest_time
        mine = [r for r in sess.obs.as_of(min(t1_utc, t_end) - 1, topic).to_pylist() if r["tail_no"] == tail and r[ing] >= T0]
        t = dset.dataset(PREVIEW_FLEET / topic, format="parquet", partitioning=None).to_table()
        t = t.filter((pc.field("tail_no") == tail) & (pc.field(ing) >= T0) & (pc.field(ing) < min(t1_utc, t_end)))
        ref = t.to_pylist()
        out[topic] = {"rows_session": len(mine), "rows_preview": len(ref), "identical_all_columns": canon(mine) == canon(ref)}
    out["compared_window_ist"] = [fmt_ist(T0), fmt_ist(min(t1_utc, t_end))]
    out["note"] = "validation of bitwise continuation only; oracle results are never reported as what-if numbers"
    return out


def tw_epoch_end() -> int:
    import datetime as dt

    d = bp.FLEET_START + dt.timedelta(days=bp.FLEET_DAYS)
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.UTC).timestamp()) * NS


MODE_NOTES = {
    "belief": "IN-LOOP what-if: hidden state resampled from observations by the data layer's reference "
    "SurvivalPosterior (PROXY A-W1.8-23), then run as ensemble member m. See README for what it does and "
    "does not resample.",
    "ensemble": "OFFLINE evaluation: the TRUE snapshot state (privileged) with ensemble member m's exogenous "
    "future; not available to a deployed product.",
}
KPI_DEFS = {
    "mc": "mission-capable fraction of equipment-in-service time in the window (NAMP SCIR, from AVAILABILITY_STATE bins)",
    "fmc": "fully-mission-capable fraction",
    "nmcs": "fraction of time not mission capable, supply",
    "nmcm": "fraction of time not mission capable, maintenance (scheduled + unscheduled)",
    "nmcd": "fraction of time not mission capable, depot",
    "flying_task": "flown / planned flight hours",
    "flown_fh": "flight hours flown in the window",
    "sorties": "sorties flown",
    "aog_days": "aircraft-days in NMCS",
    "cann": "cannibalisations",
    "cann_rate": "cannibalisations per 100 sorties",
    "man_hours": "man-hours booked on jobs closed in the window",
    "cost": "RELATIVE cost proxy (A-W1.8-11): new spares + 0.3 x unit cost per depot repair + man-hours x mh_cost + expedite premiums; unitless, not money",
    "in_flight_failures": "defects first reported from the air (WD-AIR / WD-ABT)",
}

if __name__ == "__main__":
    main()
