"""CAL-only development: 5-fold flight-grouped cross-validation and the pseudo-holdout battery (DEVELOPMENT
DIAGNOSTICS ONLY, never verdicts; PREREGISTRATION Phase A).

Subcommands
  folds   <out_csv>                                   3-fold assignment of the 152 CAL flights (seed 20261015;
                                                       3 folds = minimal sufficient sample, see DEVIATIONS.md)
  fitq    <mat687> <cv_root> <variant> <out_json> [folds]  out-of-fold M-A fit quality per output (CAL running mask;
                                                       CAL-fitted and fleet-prior unit parameters) + grouped-jackknife
                                                       SE of every M-A parameter over the 3 fold fits
  battery <stats_dir> <flight_list> <out_json> <real_label> <label1,label2,...>
                                                       dev battery: D(synthetic label vs real, paired) for B1-B6 with
                                                       2,000 flight-bootstrap CIs, G1 and B9; dev-only reference
                                                       distances: CAL real early vs late (median date split, equal n,
                                                       a D_temp analogue) - no 687-TEST or 652 data are read in Phase A.
"""
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402

K_FOLDS = 3


def folds(out_csv):
    cal = R.cal_files()
    rng = np.random.default_rng([R.ROOT_SEED, 5])
    perm = rng.permutation(len(cal))
    fold = {cal[i]: j % K_FOLDS for j, i in enumerate(perm)}
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "fold"])
        for f in cal:
            w.writerow([f, fold[f]])
    print({k: sum(v == k for v in fold.values()) for k in range(K_FOLDS)})


def read_folds(path):
    return {r["file"]: int(r["fold"]) for r in csv.DictReader(open(path))}


def fitq(mat687, cv_root, variant, out_json, fold_ids=None):
    import ma_model as MAM
    import synth as SY
    fold = read_folds(os.path.join(cv_root, "folds.csv"))
    res = {"variant": variant, "folds": {}}
    pars = []
    pooled = {m: {f: [] for f in R.FAM} for m in ("cal", "prior")}
    fold_ids = list(range(K_FOLDS)) if fold_ids is None else fold_ids
    for k in fold_ids:
        md = os.path.join(cv_root, variant, f"fold{k}")
        ma = MAM.load(os.path.join(md, "ma.json"))
        pars.append(np.concatenate([ma.p[s] for s in ma.STAGES]))
        test = sorted(f for f, j in fold.items() if j == k)
        ds = [R.load(os.path.join(mat687, f)) for f in test]
        B = MAM.Batch(ds, [MAM.running_mask_cal(d) for d in ds])
        res["folds"][k] = {}
        for mode in ("cal", "prior"):
            sim = ma.simulate(B, override=SY.unit_params(ma, mode, f"cvfold{k}"))
            w = B.w > 0
            res["folds"][k][mode] = {}
            for f in R.FAM:
                e = (sim[f] - B.Y[f])[w]
                pooled[mode][f].append((e, B.Y[f][w]))
                res["folds"][k][mode][f] = {"rmse": float(np.sqrt(np.mean(e ** 2))), "bias": float(np.mean(e)),
                                            "R2": float(1 - np.var(e) / np.var(B.Y[f][w]))}
        print(k, res["folds"][k]["cal"], flush=True)
    res["pooled_out_of_fold"] = {}
    for mode in ("cal", "prior"):
        res["pooled_out_of_fold"][mode] = {}
        for f in R.FAM:
            e = np.concatenate([a for a, _ in pooled[mode][f]])
            y = np.concatenate([b for _, b in pooled[mode][f]])
            res["pooled_out_of_fold"][mode][f] = {"rmse": float(np.sqrt(np.mean(e ** 2))), "bias": float(np.mean(e)),
                                                  "R2": float(1 - np.var(e) / np.var(y)),
                                                  "mae": float(np.mean(np.abs(e)))}
    P = np.array(pars)
    kf = len(fold_ids)
    se = np.sqrt((kf - 1) / kf * np.sum((P - P.mean(0)) ** 2, 0)) if kf > 1 else np.full(P.shape[1], np.nan)
    ma0 = MAM.load(os.path.join(cv_root, variant, f"fold{fold_ids[0]}", "ma.json"))
    names = [f"{s}:{n}" for s in ma0.STAGES for n, _ in ma0._flat_names(s)]
    res["jackknife_se_over_folds"] = dict(zip(names, se.tolist()))
    res["fold_mean"] = dict(zip(names, P.mean(0).tolist()))
    with open(out_json, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res["pooled_out_of_fold"], indent=1))


def battery(stats_dir, lst, out_json, real_label, labels):
    import battery_eval as BE
    from s04_stats import load_stats
    files = [l.strip() for l in open(lst) if l.strip()]
    real = load_stats(stats_dir, real_label, files)
    boot = BE.Bootstrap(R.ROOT_SEED)
    out = {"note": "DEVELOPMENT DIAGNOSTIC on 687-CAL pseudo-holdout (out-of-fold synthesis). Not a verdict.",
           "n_flights": len(files), "real_label": real_label, "groups": {real_label: BE.group_values(real)}, "vs_real": {}}
    # dev-only reference: CAL early vs late (median date), equal n
    sp = {r["file"]: r["datestr"] for r in R.splits()}
    order = sorted(files, key=lambda f: sp[f])
    h = len(order) // 2
    early, late = order[:h], order[h:2 * h]
    idx = {f: i for i, f in enumerate(files)}
    SE = [real[idx[f]] for f in early]
    SL = [real[idx[f]] for f in late]
    ref = BE.compare(SE, SL, "early", "late", False, boot, real_is_B=True)
    out["dev_reference_real_early_vs_late"] = BE.summarise(ref)
    for lab in labels:
        S = load_stats(stats_dir, lab, files)
        c = BE.compare(S, real, "all", "all", True, boot)
        out["vs_real"][lab] = BE.summarise(c)
        out["groups"][lab] = BE.group_values(S)
        out["vs_real"][lab]["G1"] = BE.g1(S, real)
        out["vs_real"][lab]["B9"] = BE.b9(S, real, R.ROOT_SEED)
        print(lab, {t: round(v["D"], 3) for t, v in out["vs_real"][lab].items() if t.startswith("B") and t != "B9"}, flush=True)
    print("ref early-vs-late", {t: round(v["D"], 3) for t, v in out["dev_reference_real_early_vs_late"].items()})
    with open(out_json, "w") as fh:
        json.dump(out, fh, indent=1, default=float)


if __name__ == "__main__":
    a = sys.argv
    if a[1] == "folds":
        folds(a[2])
    elif a[1] == "fitq":
        fitq(a[2], a[3], a[4], a[5], [int(x) for x in a[6].split(",")] if len(a) > 6 else None)
    elif a[1] == "battery":
        battery(a[2], a[3], a[4], a[5], a[6].split(","))
