"""Cross-channel cohesion check: do synthetic channels co-vary like real ones?

Compares correlation structure of the 16 engine channels (N1, N2, EGT, FF x 4 engines, 4 Hz)
between real Tail 687 TEST flights and their FULL synthetic versions (T1-L6, T2-L6), and puts the
differences next to real-vs-real baselines (687 early vs late season; 687 vs Tail 652).

Per flight, airborne-only samples (all four N1 > 25 %):
  * slow structure : Pearson correlation matrix of lowpass(x)            (0.2 Hz, as the experiment)
  * fast structure : Pearson correlation matrix of x - lowpass(x)        (the texture band)
  * EGT->FF lag    : lag (s) maximising cross-correlation of d/dt(FF_k) and d/dt(EGT_k), +-10 s
Group statistic = median over flights of each of the 120 channel-pair correlations.
Distance between groups = mean |difference| over pairs, with a flight-bootstrap 95 % CI.

Env: CORR_FC (truth low-pass cutoff, default 0.2 Hz), CORR_VARIANT (primary|low|high synthetic set).
Usage: python -I corr_check.py <mat687> <synth_root> <mat652> <splits.csv> <out_dir> [n_flights]
"""
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "analysis", "dashlink_texture"))
sys.path.insert(0, os.path.join(ROOT, "analysis", "settling_experiment", "src"))
from dlio import load_flight  # noqa: E402
from pipeline import lowpass  # noqa: E402

CH = [f"{p}_{k}" for p in ("N1", "N2", "EGT", "FF") for k in (1, 2, 3, 4)]
IU = np.triu_indices(len(CH), 1)
RATE, SEED = 4.0, 20261014
FC = float(os.environ.get("CORR_FC", "0.2"))
VAR = os.environ.get("CORR_VARIANT", "primary")


def flight_stats(path):
    F = load_flight(path)
    if any(c not in F for c in CH):
        return None
    X = np.vstack([np.asarray(F[c].x, float) for c in CH])
    n = min(x.size for x in X)
    X = X[:, :n]
    air = np.all(X[0:4] > 25.0, axis=0)
    if air.sum() < 600:  # < 2.5 min airborne at 4 Hz
        return None
    slow = np.vstack([lowpass(x, RATE, FC) for x in X])
    fast = X - slow
    s, f = slow[:, air], fast[:, air]
    keep = (s.std(1) > 0) & (f.std(1) > 0)
    if not keep.all():
        return None
    cs, cf = np.corrcoef(s)[IU], np.corrcoef(f)[IU]
    lags = []
    for k in range(4):
        a = np.diff(X[12 + k][air]); b = np.diff(X[8 + k][air])  # FF_k, EGT_k
        a = (a - a.mean()) / (a.std() + 1e-12); b = (b - b.mean()) / (b.std() + 1e-12)
        L = int(10 * RATE)
        cc = [np.mean(a[:a.size - l] * b[l:]) if l >= 0 else np.mean(a[-l:] * b[:b.size + l]) for l in range(-L, L + 1)]
        lags.append((int(np.argmax(cc)) - L) / RATE)
    return cs, cf, np.array(lags)


def group(paths):
    out = [r for r in (flight_stats(p) for p in paths) if r is not None]
    return (np.array([o[0] for o in out]), np.array([o[1] for o in out]), np.array([o[2] for o in out]))


def dist(A, B, rng, nb=2000, paired=False):
    d0 = float(np.mean(np.abs(np.median(A, 0) - np.median(B, 0))))
    bs = []
    for _ in range(nb):
        ia = rng.integers(0, len(A), len(A))
        ib = ia if paired else rng.integers(0, len(B), len(B))
        bs.append(np.mean(np.abs(np.median(A[ia], 0) - np.median(B[ib], 0))))
    return d0, [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def main(mat687, synth_root, mat652, splits_csv, out_dir, n=60):
    rng = np.random.default_rng(SEED)
    rows = list(csv.DictReader(open(splits_csv)))
    test = sorted(r["file"] for r in rows if r["set"] == "687-TEST")
    s652 = sorted(r["file"] for r in rows if r["set"] == "652")
    early = sorted(r["file"] for r in rows if r["set"] == "687-TEST" and r["temporal_group"] == "early")
    late = sorted(r["file"] for r in rows if r["set"] == "687-TEST" and r["temporal_group"] == "late")
    pick = lambda L, m: sorted(rng.choice(L, min(m, len(L)), replace=False).tolist())
    T = pick(test, n)
    real = group([os.path.join(mat687, f) for f in T])
    t1 = group([os.path.join(synth_root, f"T1_L6_{VAR}", f) for f in T])
    t2 = group([os.path.join(synth_root, f"T2_L6_{VAR}", f) for f in T])
    r652 = group([os.path.join(mat652, f) for f in pick(s652, n)])
    e, l = pick(early, n // 2), pick(late, n // 2)
    re_, rl = group([os.path.join(mat687, f) for f in e]), group([os.path.join(mat687, f) for f in l])
    res = {"n_flights": {"real687_test": len(real[0]), "T1_L6": len(t1[0]), "T2_L6": len(t2[0]),
                         "real652": len(r652[0]), "687_early": len(re_[0]), "687_late": len(rl[0])},
           "flights_687_test": T}
    for j, name in ((0, "slow_corr"), (1, "fast_corr")):
        res[name] = {
            "sim_T1_vs_real687": dist(t1[j], real[j], rng, paired=True),
            "sim_T2_vs_real687": dist(t2[j], real[j], rng, paired=True),
            "real687_early_vs_late": dist(re_[j], rl[j], rng),
            "real687_vs_real652": dist(real[j], r652[j], rng),
        }
    names = [f"{CH[i]}~{CH[k]}" for i, k in zip(*IU)]
    show = ["N1_1~N2_1", "N1_1~EGT_1", "N1_1~FF_1", "EGT_1~FF_1", "N1_1~N1_2", "N2_1~N2_2", "EGT_1~EGT_2", "FF_1~FF_2"]
    res["selected_pairs_fast_median"] = {p: {g: round(float(np.median(G[1][:, names.index(p)])), 3)
                                              for g, G in (("real687", real), ("T1_L6", t1), ("T2_L6", t2), ("real652", r652))}
                                         for p in show}
    res["selected_pairs_slow_median"] = {p: {g: round(float(np.median(G[0][:, names.index(p)])), 3)
                                              for g, G in (("real687", real), ("T1_L6", t1), ("T2_L6", t2), ("real652", r652))}
                                         for p in show}
    res["egt_ff_lag_s_median"] = {g: float(np.median(G[2])) for g, G in
                                  (("real687", real), ("T1_L6", t1), ("T2_L6", t2), ("real652", r652))}
    os.makedirs(out_dir, exist_ok=True)
    json.dump(res, open(os.path.join(out_dir, "corr_check.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "flights_687_test"}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:6], *(int(a) for a in sys.argv[6:7]))
