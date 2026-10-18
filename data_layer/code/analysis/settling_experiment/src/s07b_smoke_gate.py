"""Gate-0 smoke test on a deterministic sample of 60 687-TEST flights (run-order / sanity step; the binding
Gate 0 is s07_gate0.py on all 229 flights).

Sample: numpy default_rng(20261014).choice(sorted 687-TEST files, 60, replace=False), saved to
results/smoke_flights.csv. Features for real687_primary, T1_L6_primary, T2_L6_primary, T1_L6p_primary are
extracted with the same features.extract into <features_smoke_dir> (separate from the full run).
Output: results/gate0_smoke.json with LR/GB AUC + 95 % CI, the full univariate list, and the check
"no single metadata feature has univariate AUC < 0.2 or > 0.8".

Usage: python -I s07b_smoke_gate.py <mat687_dir> <texture_results_dir> <results_dir> <synthetic_dir> <features_smoke_dir> [n_workers]
"""
import csv
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
from pipeline import Pipe  # noqa: E402
import features as FT  # noqa: E402
import learn as LN  # noqa: E402
from s07_gate0 import evaluate  # noqa: E402

LABELS = ["real687_primary", "T1_L6_primary", "T2_L6_primary", "T1_L6p_primary"]
G = {}


def winit(tex_res, lattice):
    G["pipe"] = Pipe(tex_res, lattice)


def job(args):
    path, label, out = args
    op = os.path.join(out, label, C.flight_id(path) + ".npz")
    if not os.path.exists(op):
        d = FT.extract(path, G["pipe"], "primary")
        names = d.pop("names")
        os.makedirs(os.path.dirname(op), exist_ok=True)
        np.savez_compressed(op, gate0=d["gate0"])
        return names["gate0"]
    return None


def main(mat687, tex_res, res, syn, out, nw=4):
    rows = list(csv.DictReader(open(os.path.join(res, "splits.csv"))))
    test = sorted(r["file"] for r in rows if r["set"] == "687-TEST")
    rng = np.random.default_rng(C.ROOT_SEED)
    sample = sorted(rng.choice(test, 60, replace=False).tolist())
    with open(os.path.join(res, "smoke_flights.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file"])
        w.writerows([[f] for f in sample])
    lattice = json.load(open(os.path.join(res, "model_params_primary.json")))["fixed"]["lattice"]
    jobs = []
    for lab in LABELS:
        d = mat687 if lab.startswith("real") else os.path.join(syn, lab)
        jobs += [(os.path.join(d, f), lab, out) for f in sample]
    names = None
    with Pool(nw, initializer=winit, initargs=(tex_res, lattice)) as pool:
        for nm in pool.imap_unordered(job, jobs):
            if nm is not None:
                names = nm
    if names is None:
        names = json.load(open(os.path.join(out, "names_gate0.json")))
    with open(os.path.join(out, "names_gate0.json"), "w") as fh:
        json.dump(names, fh)

    def load(lab):
        return np.vstack([np.load(os.path.join(out, lab, f.replace(".mat", ".npz")))["gate0"] for f in sample])
    R = load("real687_primary")
    result = {"n_flights": len(sample), "variants": {}}
    for lab in LABELS[1:]:
        S = load(lab)
        ev = evaluate(R, S, True, names, C.stable_int(lab) % 10000)
        ev_pipe = evaluate(R, S, True, names, C.stable_int(lab) % 10000, sub=True)
        y = np.r_[np.zeros(len(R)), np.ones(len(S))]
        uni = []
        for j, n in enumerate(names):
            v = np.r_[R[:, j], S[:, j]]
            if np.nanstd(v) == 0:
                continue
            uni.append({"feature": n, "auc": LN.auc(y, v), "mean_real": float(R[:, j].mean()), "mean_syn": float(S[:, j].mean()),
                        "n_flights_differing": int(np.sum(R[:, j] != S[:, j]))})
        uni.sort(key=lambda d: -abs(d["auc"] - 0.5))
        gross = [u for u in uni if u["auc"] < 0.2 or u["auc"] > 0.8]
        result["variants"][lab] = {"classifiers": ev["classifiers"], "pass_full_feature_set": ev["pass"],
                                   "pipeline_only": ev_pipe["classifiers"], "pass_pipeline_only": ev_pipe["pass"],
                                   "univariate_all": uni, "gross_cues_auc_outside_0.2_0.8": gross,
                                   "no_gross_univariate_cue": len(gross) == 0}
        c = ev["classifiers"]
        print(lab, "LR", round(c["lr"]["auc"], 3), c["lr"]["ci95"], "GB", round(c["gb"]["auc"], 3), c["gb"]["ci95"],
              "gross cues:", [(g["feature"], round(g["auc"], 3)) for g in gross][:12])
    with open(os.path.join(res, "gate0_smoke.json"), "w") as fh:
        json.dump(result, fh, indent=1, default=float)


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], a[3], a[4], a[5], int(a[6]) if len(a) > 6 else 4)
