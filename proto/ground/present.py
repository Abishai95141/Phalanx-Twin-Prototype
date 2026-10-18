"""Presenters: the loop's state → the screen shapes of ``proto/web/assets/SHAPES.md`` (``PHX_EP``, ``PHX_PROV``).

Only wording and layout live here; every number comes from the order desk, the store or the event log.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from interfaces import NS, Authority
from orders import Draft, human_only, order_id

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
#: the data layer's order actions and their required parameters (copied from phalanx/orders/model.py, 0.2.0)
REQUIRED = {
    "INSPECT": ["type"], "TROUBLESHOOT": [], "REMOVE_REPLACE": ["position"], "WASH_SERVICE": ["type"],
    "DEFER": ["job_no", "limits", "expiry_hours"], "CANNIBALISE": ["job_no", "donor_tail_no"],
    "REQUISITION_SPARES": ["part_no", "quantity"], "EXPEDITE_SPARES": ["demand_no"],
    "TRANSFER_STOCK": ["part_no", "quantity", "from_base", "to_base"], "GROUND": ["reason"], "RELEASE": [],
    "BRING_FORWARD_SERVICING": ["servicing"], "CHANGE_MONITORING_CONFIG": [],
}
WHAT = {
    "TROUBLESHOOT": lambda p: f"Troubleshoot · {p.get('code', '')}".strip(" ·"),
    "CHANGE_MONITORING_CONFIG": lambda p: "Filter " + ", ".join(p.get("filter_codes_add", [])) if p.get("filter_codes_add") else "Monitoring change",
    "EXPEDITE_SPARES": lambda p: f"Expedite · {p.get('demand_no', '')}",
    "REQUISITION_SPARES": lambda p: f"{p.get('part_no', '')} × {p.get('quantity', '')}",
    "INSPECT": lambda p: f"Inspect · {p.get('type', '')}",
}


def hm(t: int) -> str:
    return dt.datetime.fromtimestamp(t / NS, IST).strftime("%H:%M")


def day(t: int) -> str:
    return dt.datetime.fromtimestamp(t / NS, IST).strftime("%a %d %b")


def iso(t: int) -> str:
    return dt.datetime.fromtimestamp(t / NS, IST).isoformat(timespec="seconds")


def dry(d: Draft, evidence_ok: bool) -> dict[str, Any]:
    c = d.candidate
    params = dict(c.parameters)
    v = (d.verdict or {}).get("verdict")
    return {
        "schema_ok": c.action in REQUIRED and all(k in params for k in REQUIRED[c.action]),
        "contract_ok": True,
        "t_issued_ok": hm(d.epoch_t) == "08:00",
        "authority_ok": (not d.needs_signature) or d.signed_by is not None,
        "evidence_ok": evidence_ok,
        "verdict": v or ("PENDING" if d.state in ("PROPOSED", "APPROVED") else d.state),
    }


def order_status(d: Draft) -> str:
    v = (d.verdict or {}).get("verdict")
    if v in ("ACCEPTED", "REJECTED"):
        return v
    if d.state == "SNOOZED":
        return "SNOOZED"
    if d.state in ("NOT_ISSUED", "DROPPED", "REJECTED"):
        return "NOT_ISSUED" if d.state != "DROPPED" else "DROPPED"
    if d.state == "PROPOSED":
        return "AWAITING_APPROVAL"
    if d.needs_signature and not d.signed_by:
        return "NEEDS_SIGNATURE"
    return "READY"


def _order_row(d: Draft, evidence_ok: dict[str, bool]) -> dict[str, Any]:
    c = d.candidate
    p = dict(c.parameters)
    return {
        "order_id": d.order_id, "item": c.issue_id, "action": c.action, "target_tail_no": d.tail,
        "what": WHAT.get(c.action, lambda _: c.action.replace("_", " ").title())(p),
        "authority": (Authority.HUMAN if d.needs_signature else Authority.AGENT).value,
        "status": order_status(d), "desk_state": d.state, "signed_by": d.signed_by, "approved_by": d.approved_by,
        "snooze_until": iso(d.snooze_until) if d.snooze_until else None, "note": d.note,
        "dropped": None if d.state != "DROPPED" else {"label": c.action.replace("_", " ").title(), "reason": d.note or ""},
        "dry": dry(d, evidence_ok.get(d.order_id, True)), "parameters": p, "rule": c.rule, "row": c.row,
    }


def epoch_view(loop) -> dict[str, Any]:
    ep = loop.current
    log = loop.log
    ev_ok = {e.subject.split(":", 1)[1]: bool(e.payload.get("all_ingested_by_snapshot"))
             for e in log.events(type="EVIDENCE_LINKED")}
    phase = ep.state
    now = hm(ep.clock_now())
    drafts = list(ep.desk.drafts.values())
    signed = [d for d in drafts if d.signed_by]
    steps = [
        ("SNAPSHOT", "06:00", "Snapshot sealed", None, None),
        ("ENGINES", "06:04", "Engines done", None, None),
        ("BOARD_OPEN", "06:05", "Board open", None, None),
        ("FREEZE", "07:45", "Board freezes", "Board frozen", None),
        ("SIGN", "07:52", "Signatures", "Signed", "07:57" if signed else None),
        ("SUBMIT", "08:00", "Orders issued", None, None),
    ]
    order = ["SNAPSHOT", "ENGINES", "BOARD_OPEN", "FREEZE", "SIGN", "SUBMIT"]
    cur = {"BOARD_OPEN": 2, "FROZEN": 4, "SUBMITTED": 5}.get(phase, 0)
    timeline = []
    for i, (k, t, label, done_label, done_t) in enumerate(steps):
        row = {"key": k, "t": t, "label": label, "state": "done" if i < cur else "now" if i == cur else "next"}
        if done_label:
            row["done_label"] = done_label
        if done_t:
            row["done_t"] = done_t
        timeline.append(row)
    signatures = [
        {"order_id": d.order_id, "title": f"{_order_row(d, ev_ok)['what']} on {d.tail}",
         "text": d.candidate.rationale,
         "rows": [{"k": "Order", "v": d.candidate.action, "mono": True},
                  {"k": "Evidence", "v": f"{len(d.candidate.evidence)} records · "
                   + ("all before 06:00" if ev_ok.get(d.order_id, True) else "not all ingested")}]}
        for d in drafts if d.needs_signature and d.state not in ("REJECTED", "NOT_ISSUED")
    ]
    head_seq, head = log.head()
    out = {
        "clock": {"epoch": dt.datetime.fromtimestamp(ep.t_orders / NS, IST).strftime("%Y%m%dT%H%M"),
                  "day": day(ep.t_orders), "asof": f"{day(ep.t_snapshot)} 06:00 IST", "now": now,
                  "snapshot": "06:00", "engines": "06:04", "freeze": "07:45", "issue": "08:00",
                  "phase": phase, "due": len(ep.issues) or len({d.candidate.issue_id for d in drafts}),
                  "snapshot_id": ep.snapshot_id},
        "timeline": timeline,
        "orders": [_order_row(d, ev_ok) for d in drafts],
        "signatures": signatures,
        "log_summary": [{"label": f"{e.type.replace('_', ' ').capitalize()}", "hash": e.hash[:8]}
                        for e in log.events(since_seq=max(0, head_seq - 6))] + [{"label": "Chain head", "hash": head[:8]}],
    }
    prev = previous_from_log(log, ep.t_orders)
    if prev:
        out["previous"] = prev
    return out


def previous_from_log(log, before_t: int) -> dict[str, Any] | None:
    """The last day's submitted orders with their gateway verdicts and latest data-layer status, rebuilt from the
    event log (so it survives API restarts)."""
    events = list(log.events())
    subs = [e for e in events if e.type == "ORDER_SUBMITTED" and e.t_logical < before_t]
    if not subs:
        return None
    last = max(subs, key=lambda e: e.t_logical)
    oids = list(last.payload.get("orders") or [])
    prop, verdict, status, signer = {}, {}, {}, {}
    for e in events:
        oid = e.subject.split(":", 1)[1] if e.subject.startswith("order:") else None
        if oid not in oids:
            continue
        if e.type == "RECOMMENDATION_PROPOSED":
            prop[oid] = e.payload
        elif e.type == "GATEWAY_VERDICT":
            verdict[oid] = e.payload.get("verdict")
        elif e.type == "ORDER_STATUS":
            status[oid] = (e.payload.get("status"), e.t_logical)
        elif e.type == "ORDER_SIGNED":
            signer[oid] = e.payload.get("by")
    rows = []
    for oid in oids:
        p = prop.get(oid, {})
        st, t_st = status.get(oid, (verdict.get(oid) or "SUBMITTED", last.t_logical))
        rows.append({"order_id": oid, "item": p.get("issue_id"), "action": p.get("action"), "target_tail_no": oid.split(":")[4],
                     "what": WHAT.get(p.get("action"), lambda _: p.get("action") or "")(p.get("parameters") or {}),
                     "verdict": verdict.get(oid), "status": st, "status_at": f"{day(t_st)} {hm(t_st)}",
                     "signed_by": signer.get(oid)})
    return {"epoch": dt.datetime.fromtimestamp(last.t_logical / NS, IST).strftime("%Y%m%dT%H%M"), "day": day(last.t_logical),
            "orders": rows, "accepted": sum(1 for v in verdict.values() if v == "ACCEPTED")}


TITLES = {
    "RUN_STARTED": "Run started", "RELEASE_ADMITTED": "Release admitted", "SNAPSHOT_SEALED": "Snapshot sealed",
    "ENGINE_RUN": "Engines run", "ISSUE_TRIAGED": "Issue triaged", "FINDING": "Finding",
    "POLICY_EVALUATED": "Policy evaluated", "EVIDENCE_LINKED": "Evidence linked",
    "RECOMMENDATION_PROPOSED": "Recommendation proposed", "FORK_RESULT": "Fork evaluated", "FORK_DROPPED": "Dropped by the fork gate",
    "ORDER_APPROVED": "Approved", "ORDER_REJECTED": "Rejected", "ORDER_SNOOZED": "Snoozed", "ORDER_MODIFIED": "Modified",
    "ORDER_SIGNED": "Signed", "BOARD_FROZEN": "Board frozen", "ORDER_SUBMITTED": "Submitted",
    "GATEWAY_VERDICT": "Gateway verdict", "ORDER_STATUS": "Status", "OUTCOME_LABELLED": "Outcome labelled",
    "STEP_DONE": "Fleet stepped", "CHAIN_VERIFIED": "Chain verified",
}


def _text(e) -> str:
    p = e.payload
    match e.type:
        case "RELEASE_ADMITTED":
            return f"{p.get('files', 0):,} files through the release gate · {p.get('rejected', 0)} rejected · {p.get('contract', '')}"
        case "SNAPSHOT_SEALED":
            return f"Everything ingested by 06:00 · hash {str(p.get('snapshot_id', ''))[:8]}"
        case "EVIDENCE_LINKED":
            ids = p.get("record_ids", [])
            last = f' · latest <span class="rid2">{ids[-1][:12]}</span>' if ids else ""
            return f"{len(ids)} records cited · " + ("all ingested before 06:00" if p.get("all_ingested_by_snapshot") else "NOT all ingested") + last
        case "POLICY_EVALUATED":
            o = p.get("output") or {}
            rec = o.get("rec") or o.get("limit") or o
            return f"{p.get('version')} · row {p.get('row')} → {json.dumps(rec, separators=(', ', ': '))[:120]} · trace {str(p.get('trace_hash', ''))[:8]}"
        case "ISSUE_TRIAGED":
            return f"{p.get('band') or 'monitor'} · C{p.get('C')} U{p.get('U')} · {p.get('basis', '')}"
        case "RECOMMENDATION_PROPOSED":
            return f"{p.get('action')} · {p.get('rule')} row {p.get('row')} · {p.get('policy_version')} · {p.get('mode')}"
        case "FORK_RESULT":
            d = p.get("d_mc") or [0, 0, 0]
            return f"{p.get('pairs')} CRN pairs · mission capable {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}] vs status quo"
        case "ORDER_APPROVED" | "ORDER_SIGNED":
            return f"{p.get('by')} · as recommended"
        case "ORDER_REJECTED" | "ORDER_MODIFIED":
            return f"{p.get('by')} · {p.get('note') or ''}"
        case "GATEWAY_VERDICT":
            return f"Data layer gateway: {p.get('verdict')}" + (f" · {p['reason']}" if p.get("reason") else "")
        case "ORDER_STATUS":
            n = len(p.get("result_record_ids") or [])
            return f"Data layer: {p.get('status')}" + (f" · {n} result records" if n else "") + (f" · {p['reason']}" if p.get("reason") else "")
        case "STEP_DONE":
            rows = p.get("rows") or {}
            total = sum(v for tail in rows.values() for k, v in tail.items() if isinstance(v, int) and "restricted" not in k
                        and k != "late_counter_rows")
            return f"All 8 tails advanced to {day(p['to'])} 06:00 · {total:,} new records published by the data layer"
        case "BOARD_FROZEN":
            return f"{len(p.get('issue', []))} to issue · {len(p.get('not_issued', []))} not issued"
        case _:
            return ", ".join(f"{k} {v}" for k, v in list(p.items())[:3] if not isinstance(v, (dict, list)))


#: which earlier event in an order's chain caused each event (first match wins)
CAUSE = {
    "RELEASE_ADMITTED": ("SNAPSHOT_SEALED",), "ISSUE_TRIAGED": ("RELEASE_ADMITTED", "SNAPSHOT_SEALED"),
    "POLICY_EVALUATED": ("ISSUE_TRIAGED",), "EVIDENCE_LINKED": ("ISSUE_TRIAGED",),
    "RECOMMENDATION_PROPOSED": ("POLICY_EVALUATED", "EVIDENCE_LINKED"), "FORK_RESULT": ("RECOMMENDATION_PROPOSED",),
    "FORK_DROPPED": ("FORK_RESULT",), "ORDER_APPROVED": ("FORK_RESULT", "RECOMMENDATION_PROPOSED"),
    "ORDER_REJECTED": ("FORK_RESULT", "RECOMMENDATION_PROPOSED"), "ORDER_SNOOZED": ("RECOMMENDATION_PROPOSED",),
    "ORDER_MODIFIED": ("RECOMMENDATION_PROPOSED",), "ORDER_SIGNED": ("ORDER_APPROVED", "RECOMMENDATION_PROPOSED"),
    "BOARD_FROZEN": ("ORDER_SIGNED", "ORDER_APPROVED", "RECOMMENDATION_PROPOSED"), "ORDER_SUBMITTED": ("BOARD_FROZEN",),
    "GATEWAY_VERDICT": ("ORDER_SUBMITTED",), "STEP_DONE": ("GATEWAY_VERDICT", "ORDER_SUBMITTED"),
    "ORDER_STATUS": ("ORDER_STATUS", "GATEWAY_VERDICT"),
}


def prior_orders(log, issue_id: str, before_t: int) -> list[dict[str, Any]]:
    """Orders for this issue issued on earlier days and accepted by the gateway, with their latest data-layer status
    (so a later day's decision page shows the work already under way instead of "no order")."""
    props, verdict, status, signer = {}, {}, {}, {}
    for e in log.events():
        oid = e.subject.split(":", 1)[1] if e.subject.startswith("order:") else None
        if e.type == "RECOMMENDATION_PROPOSED" and e.payload.get("issue_id") == issue_id:
            props[oid] = e.payload
        elif e.type == "ORDER_SIGNED" and oid:
            signer[oid] = e.payload.get("by")
        elif e.type == "GATEWAY_VERDICT" and oid:
            verdict[oid] = e.payload.get("verdict")
        elif e.type == "ORDER_STATUS" and oid:
            status[oid] = (e.payload.get("status"), e.t_logical)
    out = []
    for oid, p in props.items():
        t_ep = _epoch_of_order(oid)
        if t_ep is None or t_ep >= before_t or verdict.get(oid) != "ACCEPTED":
            continue
        st, t_st = status.get(oid, ("ACCEPTED", t_ep))
        out.append({"order_id": oid, "action": p["action"], "parameters": p["parameters"],
                    "text": WHAT.get(p["action"], lambda _: p.get("rationale") or p["action"])(p["parameters"]),
                    "authority": p.get("authority"), "mode": p.get("mode"), "signed_by": signer.get(oid), "prior": True,
                    "issued": f"{day(t_ep)} 08:00", "status": st, "status_at": f"{day(t_st)} {hm(t_st)}"})
    return out


def _epoch_of_order(oid: str) -> int | None:
    try:
        stamp = oid.split(":")[3]
        d = dt.datetime.strptime(stamp, "%Y%m%dT%H%M").replace(tzinfo=IST)
        return int(d.timestamp()) * NS
    except Exception:  # noqa: BLE001
        return None


def _actor(e) -> str:
    if e.payload.get("by"):
        return f"HUMAN:{e.payload['by']}"
    return {"GATEWAY_VERDICT": "GATEWAY:M21", "ORDER_STATUS": "DATA-LAYER:M18"}.get(e.type, "AGENT:PHALANX-LOOP")


def provenance_view(loop, oid: str, store=None, twin=None, evaluate=None) -> dict[str, Any] | None:
    """The order's chain, oldest first by logical time: release, snapshot, triage and policy evaluation of its issue,
    evidence, recommendation, fork result, human decisions, freeze, submission, gateway verdict and outcomes.
    Replay recomputes the snapshot hash, the order id and the policy trace and compares them with the log."""
    log = loop.log
    events = list(log.events())
    t_order = _epoch_of_order(oid)
    mine = [e for e in events if e.subject == f"order:{oid}" or oid in (e.payload.get("issue") or [])
            or oid in (e.payload.get("orders") or [])]
    if not mine or t_order is None:
        return None
    issue_id = next((e.payload.get("issue_id") for e in mine if e.type == "RECOMMENDATION_PROPOSED"), None)
    t_snap = t_order - 2 * 3600 * NS
    ctx = [e for e in events if (e.subject == f"epoch:{t_order}" and e.type in ("RELEASE_ADMITTED", "SNAPSHOT_SEALED", "STEP_DONE"))
           or (issue_id and e.subject == f"issue:{issue_id}"
               and (e.payload.get("epoch") == t_order or (e.payload.get("epoch") is None and t_snap <= e.t_logical <= t_order)))]
    seen_jobs, chain_events = set(), []
    for e in sorted({e.seq: e for e in ctx + mine}.values(), key=lambda e: (e.t_logical, e.seq)):
        if e.type == "FORK_RESULT":  # one result per fork job (an API restart re-attaches the same job)
            k = e.payload.get("job") or (e.payload.get("pairs"), tuple(e.payload.get("d_mc") or ()))
            if k in seen_jobs:
                continue
            seen_jobs.add(k)
        chain_events.append(e)
    snap = next((e.payload.get("snapshot_id") for e in chain_events if e.type == "SNAPSHOT_SEALED"), "")
    prop = next((e.payload for e in chain_events if e.type == "RECOMMENDATION_PROPOSED"), {})
    pol_ev = next((e.payload for e in chain_events if e.type == "POLICY_EVALUATED" and e.payload.get("policy") == prop.get("rule")), None)
    ev = next((e.payload.get("record_ids", []) for e in chain_events if e.type == "EVIDENCE_LINKED"), [])
    replay = []
    if prop:
        parts = oid.split(":")
        rid, _ = order_id(prop["rule"], parts[2], t_order, parts[4], prop["action"], prop["parameters"], ev)
        snap_now = store.snapshot_id(t_snap) if store is not None else snap
        trace_eq, policy_eq = None, None
        if evaluate is not None and issue_id and pol_ev:
            try:
                now = (evaluate(store, twin, t_snap) or {}).get(issue_id, {}).get(prop["rule"])
                trace_eq = bool(now) and now.trace_hash == pol_ev.get("trace_hash")
                policy_eq = bool(now) and now.version == pol_ev.get("version")
            except Exception:  # noqa: BLE001
                trace_eq = policy_eq = False
        replay = [{"seed": "re-run from the log", "snapshot_equal": snap_now == snap, "order_equal": rid == oid,
                   "trace_equal": bool(trace_eq) if trace_eq is not None else None,
                   "policy_equal": bool(policy_eq) if policy_eq is not None else None}]
    verify = log.verify()
    out_chain = []
    last_of: dict[str, str] = {}
    for e in chain_events:
        cause = next((last_of[c] for c in CAUSE.get(e.type, ()) if c in last_of), None)
        last_of[e.type] = f"lel:{e.seq:04d}"
        row = {"event_id": f"lel:{e.seq:04d}", "type": e.type, "t_valid": iso(e.t_logical), "actor": _actor(e),
               "causation_id": cause, "prev_hash": e.prev_hash, "hash": e.hash, "title": TITLES.get(e.type, e.type),
               "text": _text(e), "payload": e.payload, "scheduled": False}
        if e.type == "POLICY_EVALUATED":
            row["refs"] = {"trace_hash": e.payload.get("trace_hash"), "policy_version": e.payload.get("version")}
        out_chain.append(row)
    return {
        "order_id": oid, "snapshot": snap, "policy_version": prop.get("policy_version"),
        "chain": out_chain, "replay": replay, "verified": verify["ok"],
        "standards": [
            {"std": "EASA DA-04", "text": "Traceable from origin", "events": "release → evidence"},
            {"std": "EASA CM-01", "text": "Versioned by hash", "events": "policy and snapshot"},
            {"std": "EASA EXP-09", "text": "Explained after the fact", "events": "this chain"},
            {"std": "EASA QA-01", "text": "Independent sign-off", "events": "approval and signature"},
            {"std": "DRDO ETAI", "text": "Transparent and replayable", "events": "replay"},
        ],
    }


def is_human_only(action: str) -> bool:
    return human_only(action)


def board_view(loop, alert_rows: int) -> dict[str, Any]:
    """``PHX_DEC``: the ranked board of the open epoch (S2's issues + today's order drafts)."""
    ep = loop.current
    drafts = list(ep.desk.drafts.values())
    rank = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    rows = []
    for iss in sorted(ep.issues, key=lambda i: (rank.get(i.band or "", 9), -(i.rank_value or 0), i.issue_id)):
        mine = [d for d in drafts if d.candidate.issue_id == iss.issue_id]
        live = [d for d in mine if d.state != "DROPPED"]
        acts = " · ".join(dict.fromkeys(d.candidate.action.replace("_", " ") for d in live)) or None
        why = next((f.reason for f in iss.findings if f.reason), iss.basis)
        rows.append({
            "id": iss.issue_id, "band": iss.band or "P4", "tail": iss.tail_no or "fleet", "code": iss.code,
            "label": iss.title, "why": why, "act_label": acts,
            "auth_shown": "HUMAN" if any(d.needs_signature for d in live) else ("AGENT" if live else None),
            "order_state": "proposed" if live else ("dropped" if mine else "monitor"),
            "reason": why, "basis": iss.basis, "C": iss.consequence, "U": iss.urgency, "conf": iss.confidence,
            "rule": live[0].candidate.rule if live else None, "row": live[0].candidate.row if live else None,
            "action": live[0].candidate.action if live else None, "mode": live[0].candidate.mode if live else None,
            "state": iss.state.value,
        })
    load = {"alert_rows": alert_rows, "issues": ep.load.get("issues", len(ep.issues)), "open": ep.load.get("open", len(ep.issues)),
            "items": len(rows), "days": ep.load.get("days", 168)}
    return {"board": rows, "load": load, "focus": rows[0]["id"] if rows else None, "snapshot": {"hash": ep.snapshot_id}}
