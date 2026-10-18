"""Post-hoc diagnostics of the label-leak audit (DEVIATIONS.md, 2026-10-15; no verdict changes).

From the saved per-pair features of the pre-registered campaign:
1. G0 on the *structural* pipeline-only facts (sample count, count over rate, dtype, NaN, run frames and
   seconds), i.e. the binding subset without float32 representability, which is a function of the recorded
   values (a physical level change moves it);
2. the texture-only audit stratified by catalogue class: gradual degradation (level faults) vs abrupt
   (shock, transient, discrete, latent, intermittent, sensor level) modes, to locate the separation.

Usage: python -I leak_posthoc.py OUT_DIR
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
SRC = HERE.parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phalanx.faults import load_catalogue  # noqa: E402
from phalanx.validation.guards import g0_audit, label_leak_audit  # noqa: E402

SEED = 25


def _res(r) -> dict:
    return {
        "passed": bool(r.passed),
        "classifiers": {k: {"auc": float(v["auc"]), "ci95": [float(x) for x in v["ci95"]]} for k, v in r.classifiers.items()},
        "n_rows": dict(r.n_rows),
        "top": [(t[0], round(float(t[1]), 3)) for t in r.top_univariate[:5]],
    }


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    pairs = [json.loads(s) for s in (out / "leak_pairs.jsonl").read_text().splitlines()]
    pairs.sort(key=lambda d: (d["mode"], d["k"]))
    cat = load_catalogue()
    res: dict = {}
    names = pairs[0]["g0_names"]
    struct = [j for j, n in enumerate(names) if n.endswith(("_n", "_n_over_rate", "_dtype", "_hasnan", "record_frames", "record_s"))]
    XA = np.array([[d["g0"][0][j] for j in struct] for d in pairs], float)
    XB = np.array([[d["g0"][1][j] for j in struct] for d in pairs], float)
    res["g0_structural_identical_pairs"] = int(np.sum(np.all(XA == XB, axis=1)))
    res["g0_structural"] = _res(
        g0_audit(XA, XB, [names[j] for j in struct], paired=True, seed=SEED, subset="full")
    )
    tex = [d for d in pairs if not d["texture_visible"]]
    for label, sel in (
        ("texture_degradation", [d for d in tex if cat[d["mode"]].cls == "degradation"]),
        ("texture_abrupt", [d for d in tex if cat[d["mode"]].cls != "degradation"]),
    ):
        X, y, g = [], [], []
        for p, d in enumerate(sel):
            X += [d["texture"][0], d["texture"][1]]
            y += [0, 1]
            g += [p, p]
        r = label_leak_audit(np.array(X), np.array(y), np.array(g), sel[0]["texture_names"],
                             feature_set="texture_only", seed=SEED)
        res[label] = _res(r) | {"modes": sorted({d["mode"] for d in sel})}
    (out / "leak_posthoc.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    for k, v in res.items():
        if isinstance(v, dict):
            print(k, "PASS" if v["passed"] else "FAIL", v["classifiers"], v["n_rows"], v["top"][:3])
        else:
            print(k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
