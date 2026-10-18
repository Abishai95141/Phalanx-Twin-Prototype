"""Server check: zen-engine on this platform gives the film's P-DEC-01 result for TJ107 HYD-101 (22 Jun)."""
import json
import platform
from pathlib import Path

import zen

REPO = Path(__file__).resolve().parents[3]
ref = json.loads((REPO / "video/data/assure_policies_asof_20260622.json").read_text())
jdm = json.loads((REPO / "video/data/policies/P-DEC-01.jdm.json").read_text())
jdm = jdm.get("jdm", jdm)
res = zen.ZenEngine().create_decision(json.dumps(jdm)).evaluate(ref["input"])
out = res.get("result", res)
print(platform.machine(), "zen", ref["engine"]["version"], "| result", json.dumps(out), "| film", json.dumps(ref["result"]),
      "| equal:", out == ref["result"])
