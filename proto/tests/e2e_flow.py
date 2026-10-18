"""End-to-end flow against a running prototype (the demo's script, automated). Not part of the unit suite.

    python proto/tests/e2e_flow.py http://127.0.0.1:8701        # through the tunnel
    proto/deploy/remote.sh '$PHX_PY proto/tests/e2e_flow.py'     # on the server (default http://127.0.0.1:8700)

Walks one day: board → decide (approve, sign, reject) → advance (orders through the data layer's gateway) →
next morning → provenance (chain verified, replay equal) → outcomes logged. ADVANCES THE LIVE RUN BY ONE DAY;
reset afterwards with ``proto/deploy/services.sh reset``.
"""

from __future__ import annotations

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8700"
ok = True


def call(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail != "" else ""))


ep = call("GET", "/api/epoch")
check("epoch open", ep["clock"]["phase"] == "BOARD_OPEN", ep["clock"]["epoch"])
day0 = ep["clock"]["epoch"]
board = call("GET", "/api/board")
check("board has decisions", len(board["board"]) >= 7, f"{len(board['board'])} rows · funnel {board['load']}")
ids = [r["id"] for r in board["board"]]

hero = "TJ107-HYD-101"
iss = call("GET", f"/api/issues/{hero}")
check("issue detail", iss["id"] == hero and iss["orders"], f"{len(iss['orders'])} orders · impact {iss.get('impact') and iss['impact']['d_mc']}")
call("POST", f"/api/issues/{hero}/decision", {"action": "approve", "by": "SEO"})
human = [o for o in iss["orders"] if o["authority"] == "HUMAN"]
for o in human:
    call("POST", f"/api/orders/{o['order_id']}/sign", {"by": "ENGG-OFFICER"})
for p1 in [r["id"] for r in board["board"] if r["band"] == "P1"]:
    call("POST", f"/api/issues/{p1}/decision", {"action": "approve", "by": "SEO"})
worse = [r["id"] for r in board["board"] if r["id"] not in (hero,) and r["order_state"] == "proposed"
         and (call("GET", f"/api/issues/{r['id']}").get("impact") or {}).get("d_mc", [0, 0, 0])[2] < 0]
for w in worse:
    call("POST", f"/api/issues/{w}/decision", {"action": "reject", "by": "SEO", "reason": "worse than doing nothing in paired simulations"})
ep = call("GET", "/api/epoch")
ready = [o for o in ep["orders"] if o["status"] == "READY"]
check("decisions recorded", len(ready) >= 1 + len(human), f"{len(ready)} ready · rejected {worse}")
hero_orders = [o["order_id"] for o in ep["orders"] if o["item"] == hero and o["status"] == "READY"]

nxt = call("POST", "/api/epoch/advance", {})
check("advanced one day", nxt["clock"]["epoch"] != day0, f"{day0} → {nxt['clock']['epoch']}")
prev = nxt.get("previous") or {}
acc = [o for o in prev.get("orders", []) if o["status"] == "ACCEPTED"]
check("gateway accepted the issued orders", len(acc) >= len(ready), f"{len(acc)} ACCEPTED of {len(ready)} issued")

for oid in hero_orders:
    pv = call("GET", f"/api/provenance/{oid}")
    types = [e["type"] for e in pv["chain"]]
    need = {"SNAPSHOT_SEALED", "EVIDENCE_LINKED", "RECOMMENDATION_PROPOSED", "ORDER_APPROVED", "GATEWAY_VERDICT"}
    check(f"provenance chain {oid.split(':')[-2]}", need <= set(types) and pv["verified"], " → ".join(types))
    check(f"replay gives the same id {oid.split(':')[-2]}", all(r["order_equal"] for r in pv["replay"]))
v = call("POST", "/api/provenance/verify", {})
check("hash chain verifies", v["ok"], f"{v['events']} events")
rd = call("GET", "/api/readiness")
check("readiness is the next morning", rd["asof"].startswith("2026-06-23"), rd["asof"])
print("E2E", "PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
