"""Step 7 -- Gate 0, the trivial-cue audit (pre-registration section 4).

A metadata-only classifier (per-channel sample counts, record length, dtype, NaN presence, fraction of values
on the lattice, histogram of value/LSB fractional parts, float bit-pattern statistics, sentinel counts,
first and last samples) must be at chance: PASS = the 95 % bootstrap CI of the flight-level AUC includes 0.5,
for both LR and GB. Rows = files; GroupKFold 5 x 3 with the real and synthetic version of a flight in the
same fold. Also reports the univariate AUC of every metadata feature (|AUC - 0.5| ranking) for diagnosis.

Usage: python -I s07_gate0.py <features_dir> <results_dir> [tag]
Writes results/gate0[_tag].json
"""
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
import learn as LN  # noqa: E402


def load(fdir, label, files):
    return np.vstack([np.load(os.path.join(fdir, label, f.replace(".mat", ".npz")))["gate0"] for f in files])


PIPELINE_ONLY = ("_n", "_n_over_rate", "_dtype", "_hasnan", "_f32repr", "record_frames", "record_s")


BITPATTERN = ("_mantissa_tz_mean", "_f32repr")
LATTICE = ("_lat_on",) + tuple(f"_fracbin{k}" for k in range(10))


def evaluate(XA, XB, paired, names, seed, sub=False):
    if sub == "no_bitpattern":
        keep = [j for j, n in enumerate(names) if not n.endswith(BITPATTERN)]
        XA, XB, names = XA[:, keep], XB[:, keep], [names[j] for j in keep]
    elif sub == "no_bitpattern_no_lattice":
        keep = [j for j, n in enumerate(names) if not n.endswith(BITPATTERN + LATTICE)]
        XA, XB, names = XA[:, keep], XB[:, keep], [names[j] for j in keep]
    elif sub:
        keep = [j for j, n in enumerate(names) if n.endswith(PIPELINE_ONLY)]
        XA, XB, names = XA[:, keep], XB[:, keep], [names[j] for j in keep]
    X = np.vstack([XA, XB])
    y = np.r_[np.zeros(len(XA), int), np.ones(len(XB), int)]
    if paired:
        pid = np.r_[np.arange(len(XA)), np.arange(len(XB))]
        groups = pid
    else:
        pid = None
        groups = np.arange(len(y))
    bidx = LN.boot_indices(y, pid, 2000, seed)
    out = {"classifiers": {}}
    for kind in ("lr", "gb"):
        if np.all(np.nanstd(X, 0) == 0):
            out["classifiers"][kind] = {"auc": 0.5, "ci95": [0.5, 0.5], "pass": True, "note": "all features identical"}
            continue
        s, _, _ = LN.cv_scores(kind, X, y, np.arange(len(y)), len(y), groups, seed, n_jobs=8)
        a = LN.auc(y, s)
        bs = LN.boot_auc(y, s, bidx)
        ci = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
        out["classifiers"][kind] = {"auc": a, "ci95": ci, "pass": bool(ci[0] <= 0.5 <= ci[1])}
    uni = []
    for j, n in enumerate(names):
        v = X[:, j]
        if np.nanstd(v) == 0:
            continue
        a = LN.auc(y, v)
        uni.append((n, float(a), float(np.nanmean(XA[:, j])), float(np.nanmean(XB[:, j]))))
    uni.sort(key=lambda t: -abs(t[1] - 0.5))
    out["top_univariate"] = uni[:15]
    out["pass"] = all(c["pass"] for c in out["classifiers"].values())
    return out


def main(fdir, res, tag=""):
    names = json.load(open(os.path.join(fdir, "names.json")))["gate0"]
    rows = list(csv.DictReader(open(os.path.join(res, "splits.csv"))))
    test = sorted(r["file"] for r in rows if r["set"] == "687-TEST")
    s652 = sorted(r["file"] for r in rows if r["set"] == "652")
    man = json.load(open(os.path.join(res, "synthetic_manifest.json")))
    real = {fk: load(fdir, f"real687_{fk}", test) for fk in C.FC}
    out = {}
    for v in man["variants"]:
        fk = v.split("_")[-1]
        XB = load(fdir, v, test)
        out[v] = evaluate(real[fk], XB, True, names, C.stable_int(v) % 10000)
        out[v]["pipeline_only"] = evaluate(real[fk], XB, True, names, C.stable_int(v) % 10000, sub=True)
        if v.endswith("_primary") and ("L6" in v):
            for sb in ("no_bitpattern", "no_bitpattern_no_lattice"):
                out[v][sb] = evaluate(real[fk], XB, True, names, C.stable_int(v) % 10000, sub=sb)
        c = out[v]["classifiers"]
        print(f"{v:18s} LR {c['lr']['auc']:.3f} {c['lr']['ci95']}  GB {c['gb']['auc']:.3f} {c['gb']['ci95']}  "
              f"{'PASS' if out[v]['pass'] else 'FAIL'}  pipeline-only {'PASS' if out[v]['pipeline_only']['pass'] else 'FAIL'}"
              f"  top: {out[v]['top_univariate'][:3]}", flush=True)
    rng = np.random.default_rng([C.ROOT_SEED, 1])
    test110 = sorted(rng.choice(test, len(s652), replace=False).tolist())
    out["tail_baseline(info)"] = evaluate(load(fdir, "real687_primary", test110), load(fdir, "real652_primary", s652),
                                          False, names, 5)
    c = out["tail_baseline(info)"]["classifiers"]
    print("tail (info)", c, out["tail_baseline(info)"]["top_univariate"][:5])
    with open(os.path.join(res, f"gate0{('_' + tag) if tag else ''}.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
