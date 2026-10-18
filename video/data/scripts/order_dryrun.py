"""Pre-submission gateway dry-run for the frozen 22 Jun 08:00 order set, using the data layer's own checks.

Runs the same checks as phalanx.orders.gateway.OrderGateway.evaluate, step by step, minus idempotency and the
session-bound evidence lookup (evidence ingestion is checked against our as-of store, which recorded every
evidence record's t_ingest in decision_screens_asof_20260622.json):
  1. contract validity of the orders.commands row   (phalanx.orders.model.contract_errors, contract v0)
  2. t_issued == session time (the 08:00 IST epoch)
  3. per-action parameter schema + target rules      (phalanx.orders.model.check_parameters)
  4. authority matrix                                (phalanx.orders.rules.load_authority, authority.yaml)
  5. every evidence record_id ingested by t_issued   (as-of store, latest t_ingest <= 06:00 snapshot)

Run with the forks venv (data-layer pins):  video/tools/forks/run.sh video/data/scripts/order_dryrun.py
Writes video/data/order_dryrun_20260622.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from phalanx.dictionary.contract import load_contract
from phalanx.orders.model import Order, check_parameters, contract_errors
from phalanx.orders.rules import load_authority

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "decision_screens_asof_20260622.json"
OUT = ROOT / "data" / "order_dryrun_20260622.json"

EPOCH_UTC_NS = 1782095400000000000  # 2026-06-22T02:30:00Z = 08:00 IST (same as the S1-S3 fork epoch)
SESSION_NS = EPOCH_UTC_NS

d = json.loads(SRC.read_text())
contract = load_contract("v0")
auth = load_authority()
res = []
for o in d["orders"]:
    order = Order(
        order_id=o["order_id"], issuer_id=o["issuer_id"], issuer_kind=o["issuer_kind"],
        t_issued=EPOCH_UTC_NS, t_effective=EPOCH_UTC_NS, action=o["action"], parameters=o["parameters"],
        priority=o["priority"], target_tail_no=o["target_tail_no"], target_base=o["target_base"],
        evidence=[bytes.fromhex(r) for r in o["evidence"]], policy_version=o["policy_version"],
    )
    cerr = contract_errors(order, contract, dict_version="0.1.3",
                           dict_hash="9428d30f578f0318161737a6e6235f332632b2827b76eb6d853064544e7fbc8b")
    perr = check_parameters(order)
    a_ok = auth.allowed(order.action, order.issuer_kind)
    human_only = not auth.allowed(order.action, "AGENT")
    res.append({
        "order_id": o["order_id"],
        "contract_ok": not cerr, "contract_errors": cerr,
        "t_issued_ok": order.t_issued == SESSION_NS,
        "schema_ok": not perr, "schema_errors": perr,
        "authority_ok": a_ok, "human_only": human_only,
        "evidence_ok": bool(o["evidence_all_ingested"]), "evidence_n": len(o["evidence"]),
        "evidence_latest_ingest": o["evidence_latest_ingest"],
        "verdict": "ACCEPTED" if (not cerr and not perr and a_ok and o["evidence_all_ingested"]) else "REJECTED",
    })
OUT.write_text(json.dumps({"epoch_utc_ns": EPOCH_UTC_NS, "checks": res}, indent=1))
for r in res:
    print(r["verdict"], r["order_id"], r["contract_errors"], r["schema_errors"], r["authority_ok"], r["human_only"])
