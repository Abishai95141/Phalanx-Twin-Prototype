"""Re-check of the API bugs S4 found in click-through QA (run against a fresh live run, before the flow test)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8700"
ok = True


def call(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail != "" else ""))


for iid in ("TJ107-HYD-101", "TJ103-LGB-501", "TJ106-LGB-501", "TJ102-HYD-001", "TJ102-HYD-101", "TJ105-SPS-501"):
    st, d = call("GET", f"/api/workbench/{iid}")
    check(f"1 workbench {iid}", st == 200 and d.get("tests"), st)
st, d = call("GET", "/api/issues/TJ108-AOG-CHUTE")
check("1 no workbench tab for the chute", st == 200 and d.get("workbench") is False)

st, d = call("POST", "/api/issues/TJ102-HYD-101/decision", {"action": "snooze", "by": "SEO", "until": "2026-06-23"})
check("2 snooze with an ISO date", st == 200 and d["decision"]["action"] == "SNOOZED", d)

st, d = call("POST", "/api/issues/TJ103-LGB-501/decision", {"action": "approve", "by": "SEO"})
check("3 decision time is the session clock", st == 200 and "06:05" <= d["decision"]["at"] < "07:45", d)

st, ep = call("GET", "/api/epoch")
oid = next(o["order_id"] for o in ep["orders"] if o["item"] == "TJ103-LGB-501")
st, pv = call("GET", f"/api/provenance/{oid}")
times = [e["t_valid"][11:16] for e in pv["chain"]]
check("4 events carry their own times", st == 200 and "06:00" in times and "06:04" in times and len(set(times)) >= 3, times)
pol = [e for e in pv["chain"] if e["type"] == "POLICY_EVALUATED"]
check("5 policy evaluation in the chain with its trace hash", pol and pol[0].get("refs", {}).get("trace_hash"), [e["refs"] for e in pol][:2])
check("5 replay re-checks snapshot, id, trace and policy", pv["replay"] and all(pv["replay"][0][k] is True for k in
      ("snapshot_equal", "order_equal", "trace_equal", "policy_equal")), pv["replay"])
forks = [e for e in pv["chain"] if e["type"] == "FORK_RESULT"]
check("5 at most one fork result per job", len(forks) <= 1, len(forks))
print("S4 CASES", "PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
