"""Compare a discriminator result computed locally with the same comparison computed on Kaggle.

Reports, per classifier, |AUC_local - AUC_kaggle| (flight level and window level -- the window-level AUC is not at the
ceiling, so it is the sensitive check) and the CI-bound differences, plus the maximum over classifiers,
and whether they agree to the tolerance (AUC 0.005, CI bounds 0.01; D1 statistics relative 1e-6 / p-values 0.01).
Usage: python -I s13_kaggle_verify.py <local.json> <kaggle.json> [out.json]
"""
import json
import sys


def main(a, b, out=None):
    A, B = json.load(open(a)), json.load(open(b))
    rows, mx_auc, mx_ci = {}, 0.0, 0.0
    for k in sorted(set(A["classifiers"]) | set(B["classifiers"])):
        if k not in A["classifiers"] or k not in B["classifiers"]:
            rows[k] = "missing on one side"
            continue
        x, y = A["classifiers"][k], B["classifiers"][k]
        d = abs(x["auc"] - y["auc"])
        dc = max(abs(x["ci95"][0] - y["ci95"][0]), abs(x["ci95"][1] - y["ci95"][1]))
        rows[k] = {"auc_local": x["auc"], "auc_kaggle": y["auc"], "abs_diff": d, "ci_max_abs_diff": dc}
        if "auc_window" in x and "auc_window" in y:
            dw = abs(x["auc_window"] - y["auc_window"])
            rows[k].update({"auc_window_local": x["auc_window"], "auc_window_kaggle": y["auc_window"], "window_abs_diff": dw})
            d = max(d, dw)
        mx_auc, mx_ci = max(mx_auc, d), max(mx_ci, dc)
    d1 = 0.0
    for ch in A.get("D1", {}):
        for t in A["D1"][ch]:
            sa, sb = A["D1"][ch][t]["stat"], B["D1"][ch][t]["stat"]
            d1 = max(d1, abs(sa - sb) / max(abs(sa), 1e-12))
    # out-of-fold flight scores (continuous; sensitive even when the AUC is at the ceiling)
    import os
    import numpy as np
    za, zb = a[:-5] + ".npz", b[:-5] + ".npz"
    score_diff = None
    if os.path.exists(za) and os.path.exists(zb):
        A2, B2 = np.load(za), np.load(zb)
        score_diff = {}
        for k in A2.files:
            if k in B2.files and A2[k].dtype.kind == "f" and A2[k].shape == B2[k].shape:
                score_diff[k] = float(np.nanmax(np.abs(A2[k] - B2[k]))) if A2[k].size else 0.0
        same_flights = bool(np.array_equal(A2["flights"], B2["flights"]))
    res = {"per_classifier": rows, "max_abs_oof_score_diff": score_diff and max(score_diff.values()),
           "oof_score_diff_by_key": score_diff, "same_flight_order": score_diff is not None and same_flights, "max_abs_auc_diff": mx_auc, "max_abs_ci_diff": mx_ci, "max_rel_d1_stat_diff": d1,
           "n_flights_local": A["n_flights_class"], "n_flights_kaggle": B["n_flights_class"],
           "agree": bool(mx_auc <= 0.005 and mx_ci <= 0.01 and A["n_flights_class"] == B["n_flights_class"])}
    print(json.dumps(res, indent=1))
    if out:
        json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
