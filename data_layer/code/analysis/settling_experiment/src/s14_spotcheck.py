"""Spot-check a discriminator result (e.g. one downloaded from a Kaggle shard) before it is merged into results/disc.

Checks: JSON keys and classifier set equal to a local reference result; n_flights per class equal to the comparison
definition; AUCs and CIs within [0, 1] with lo <= auc <= hi; npz present with y, pair, flights and one score
vector per classifier of the right length; s09_decide.single() can read it.
Usage: python -I s14_spotcheck.py <results_dir> <candidate.json> [reference_any_local.json]
"""
import json
import os
import shutil
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s08_discriminate as S8  # noqa: E402
import s09_decide as D  # noqa: E402


def main(res, cand, ref=None):
    js = json.load(open(cand))
    z = np.load(cand[:-5] + ".npz")
    name = js["name"]
    comp = [c for c in S8.build(res) if c["name"] == name]
    problems = []
    if not comp:
        problems.append("unknown comparison name")
    else:
        c = comp[0]
        exp = [len(c["A"][1]), len(c["B"][1])]
        if c["paired"] and js["n_flights_class"] != exp:
            problems.append(f"n_flights {js['n_flights_class']} != {exp}")
        if not c["paired"] and (js["n_flights_class"][0] != js["n_flights_class"][1] or js["n_flights_class"][0] > min(exp)):
            problems.append(f"n_flights {js['n_flights_class']} vs lists {exp}")
    if ref:
        rk = set(json.load(open(ref))["classifiers"])
        if set(js["classifiers"]) != rk:
            problems.append(f"classifier set differs: {sorted(set(js['classifiers']) ^ rk)}")
    for k, v in js["classifiers"].items():
        if not (0 <= v["ci95"][0] <= v["auc"] + 1e-9 and v["auc"] <= v["ci95"][1] + 1e-9 <= 1 + 1e-9):
            problems.append(f"{k}: AUC/CI inconsistent {v['auc']} {v['ci95']}")
        if k not in z.files or z[k].shape != z["y"].shape:
            problems.append(f"{k}: score vector missing or wrong length")
    for f in ("y", "pair", "flights"):
        if f not in z.files:
            problems.append(f"npz lacks {f}")
    tmp = tempfile.mkdtemp(dir=res)
    try:
        os.makedirs(os.path.join(tmp, "disc"))
        shutil.copy(cand, os.path.join(tmp, "disc", name + ".json"))
        shutil.copy(cand[:-5] + ".npz", os.path.join(tmp, "disc", name + ".npz"))
        s = D.single(tmp, name, 1)
        summary = {"auc_x": s["auc_x"], "ci95": s["ci95"], "best": s["best_classifier"]}
    except Exception as e:  # noqa: BLE001
        problems.append(f"s09 single() failed: {e!r}")
        summary = None
    finally:
        shutil.rmtree(tmp)
    out = {"candidate": cand, "name": name, "ok": not problems, "problems": problems, "auc_x_summary": summary,
           "d1_channels": len(js.get("D1", {})), "seconds": js.get("seconds")}
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main(*sys.argv[1:4])
