"""Guard G0 (trivial-cue audit) and discriminator diagnostics (PREREGISTRATION section 5), real vs synthetic,
paired by flight. Diagnosis only: the discriminators produce NO verdict; G0's pipeline-only subset is binding.

Features come from round-1 code, imported read-only: features.extract (D2 window/segment features, D3 residual
windows, Gate-0 metadata) with the round-1 Pipe (sentinel/LSB tables, f_c primary), learn.cv_scores /
ridge_cv_scores (GroupKFold 5 x 3, real and synthetic version of a flight in the same fold), s07_gate0.evaluate.
  G0: s07_gate0.evaluate(..., sub=True) on the pipeline-only metadata subset (counts, length, dtype, NaN,
      float32 representability): PASS iff the 95 % CI of the AUC includes 0.5 for LR and GB. The full metadata
      AUC is reported as a diagnostic.
  D2: LR and GB on 64-s window features (texture families; engine group) and on whole-segment features;
      D3: MiniRocket + ridge on 64-s residual windows. Feature-family ablation (drop one / only one texture family)
      for the strongest D2 classifier. No permutation tests (diagnostic).

Usage: python -I s06_disc_guard.py <real_mat_dir> <syn_mat_dir> <flight_list_file> <features_dir> <tag> <out_json>
                                   [n_workers] [texture_results_dir] [--no-d3]
"""
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402

G = {}


def winit(tex):
    from pipeline import Pipe
    lattice = json.load(open(os.path.join(R.R1_RES, "model_params_primary.json")))["fixed"]["lattice"]
    G["pipe"] = Pipe(tex, lattice)


def fjob(args):
    path, op = args
    import features as FT
    if os.path.exists(op):
        return None
    d = FT.extract(path, G["pipe"], "primary")
    names = d.pop("names")
    tmp = op + ".tmp.npz"
    np.savez_compressed(tmp, **d)
    os.replace(tmp, op)
    return names


def extract_all(src, files, fdir, nw, tex):
    os.makedirs(fdir, exist_ok=True)
    jobs = [(os.path.join(src, f), os.path.join(fdir, f.replace(".mat", ".npz"))) for f in files]
    names = None
    with Pool(nw, initializer=winit, initargs=(tex,)) as pool:
        for nm in pool.imap_unordered(fjob, jobs, chunksize=1):
            if nm is not None and names is None:
                names = nm
    if names is not None:
        with open(os.path.join(fdir, "_names.json"), "w") as fh:
            json.dump(names, fh)
    return json.load(open(os.path.join(fdir, "_names.json")))


def load(fdir, files, keys):
    out = []
    for f in files:
        with np.load(os.path.join(fdir, f.replace(".mat", ".npz")), allow_pickle=False) as z:
            out.append({k: z[k] for k in keys if k in z.files})
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_d3 = "--no-d3" in sys.argv
    real_dir, syn_dir, lst, fdir, tag, out_json = args[:6]
    nw = int(args[6]) if len(args) > 6 else 8
    tex = args[7] if len(args) > 7 else os.path.join(R.TEXTURE_DIR, "results")
    import learn as LN
    import s07_gate0 as G0
    TEX_FAM = ["quant", "noise", "spectral", "tails", "missing", "cross"]
    files = [l.strip() for l in open(lst) if l.strip()]
    t0 = time.time()
    names = extract_all(real_dir, files, os.path.join(fdir, "real"), nw, tex)
    extract_all(syn_dir, files, os.path.join(fdir, tag), nw, tex)
    print(f"features {time.time() - t0:.0f}s", flush=True)
    keys = ["gate0", "eng64", "engseg", "d3e64"]
    DA = load(os.path.join(fdir, "real"), files, keys)
    DB = load(os.path.join(fdir, tag), files, keys)
    n = len(files)
    seed = R.stable_int(tag) % 100000
    res = {"tag": tag, "n_flights": n}
    # ---------------- G0
    XA = np.vstack([d["gate0"] for d in DA])
    XB = np.vstack([d["gate0"] for d in DB])
    g0 = G0.evaluate(XA, XB, True, names["gate0"], seed, sub=True)
    g0full = G0.evaluate(XA, XB, True, names["gate0"], seed, sub=False)
    res["G0_pipeline_only"] = g0
    res["G0_full_metadata_diagnostic"] = {"classifiers": g0full["classifiers"], "top_univariate": g0full["top_univariate"][:10]}
    print("G0 pipeline-only", {k: (round(v["auc"], 3), v["ci95"]) for k, v in g0["classifiers"].items()}, "PASS" if g0["pass"] else "FAIL",
          "| full metadata", {k: round(v["auc"], 3) for k, v in g0full["classifiers"].items()}, flush=True)
    # ---------------- D2
    y_f = np.r_[np.zeros(n, int), np.ones(n, int)]
    pid = np.r_[np.arange(n), np.arange(n)]
    bidx = LN.boot_indices(y_f, pid, 2000, seed)
    D = DA + DB
    fam64 = np.array([nm.split("|")[0] for nm in names["eng64"]])
    famseg = np.array([nm.split("|")[0] for nm in names["engseg"]])

    def win_mat(key, fam_mask):
        Xs, rf, yr = [], [], []
        for i, d in enumerate(D):
            x = d[key]
            if x.shape[0] == 0:
                continue
            Xs.append(x[:, fam_mask])
            rf.append(np.full(x.shape[0], i))
            yr.append(np.full(x.shape[0], y_f[i]))
        X = np.vstack(Xs).astype(np.float64)
        X[~np.isfinite(X)] = np.nan
        return X, np.concatenate(rf), np.concatenate(yr)

    def auc_ci(s):
        a = LN.auc(y_f, s)
        bs = LN.boot_auc(y_f, s, bidx)
        return {"auc": a, "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}

    res["D2"] = {}
    tex64 = np.isin(fam64, TEX_FAM)
    texseg = np.isin(famseg, TEX_FAM)
    for kind in ("lr", "gb"):
        X, rf, yr = win_mat("eng64", tex64)
        s, _, _ = LN.cv_scores(kind, X, yr, rf, 2 * n, pid[rf] if False else pid[rf], seed, n_jobs=nw)
        res["D2"][f"{kind}_64_tex"] = auc_ci(s)
        Xs = np.vstack([d["engseg"][texseg] for d in D]).astype(np.float64)
        Xs[~np.isfinite(Xs)] = np.nan
        s, _, _ = LN.cv_scores(kind, Xs, y_f, np.arange(2 * n), 2 * n, pid, seed, n_jobs=nw)
        res["D2"][f"{kind}_seg_tex"] = auc_ci(s)
        print("D2", kind, {k: round(v["auc"], 3) for k, v in res["D2"].items()}, f"{time.time() - t0:.0f}s", flush=True)
    # ---------------- family ablation for the strongest D2 window classifier
    best = max(("lr", "gb"), key=lambda k: res["D2"][f"{k}_64_tex"]["auc"])
    res["ablation"] = {"classifier": f"D2_{best}_64_tex", "configs": {}}
    for fam in TEX_FAM:
        for mode in ("drop", "only"):
            m = (tex64 & (fam64 != fam)) if mode == "drop" else (fam64 == fam)
            if m.sum() == 0:
                continue
            X, rf, yr = win_mat("eng64", m)
            s, _, _ = LN.cv_scores(best, X, yr, rf, 2 * n, pid[rf], seed, n_jobs=nw)
            res["ablation"]["configs"][f"{mode}_{fam}"] = auc_ci(s)
    print("ablation", {k: round(v["auc"], 3) for k, v in res["ablation"]["configs"].items()}, f"{time.time() - t0:.0f}s", flush=True)
    # ---------------- D3 MiniRocket on 64-s residual windows
    if not no_d3:
        from aeon.transformations.collection.convolution_based import MiniRocket
        Xs, rf = [], []
        for i, d in enumerate(D):
            x = d["d3e64"]
            if x.shape[0]:
                Xs.append(x.astype(np.float32))
                rf.append(np.full(x.shape[0], i))
        X3 = np.nan_to_num(np.concatenate(Xs).astype(np.float64))
        rf = np.concatenate(rf)
        Z = LN.standardise(MiniRocket(n_kernels=10000, random_state=seed, n_jobs=nw).fit_transform(X3).astype(np.float64))
        s, _, _ = LN.ridge_cv_scores(Z, y_f[rf], rf, 2 * n, pid[rf], seed)
        res["D3_64_res"] = auc_ci(s)
        print("D3", res["D3_64_res"], f"{time.time() - t0:.0f}s", flush=True)
    res["seconds"] = time.time() - t0
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w") as fh:
        json.dump(res, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
