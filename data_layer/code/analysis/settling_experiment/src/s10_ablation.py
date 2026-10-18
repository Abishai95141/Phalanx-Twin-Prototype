"""Step 10 -- diagnosis: feature-family ablation for the strongest D2 discriminator of a comparison, and input
ablation for D3 (channel-family subsets for the engine group; sentinel samples zeroed for VRTG).

For the chosen D2 classifier (the D2 texture-family classifier with the highest AUC unless given):
  all texture families; leave-one-family-out (6); single family (6). Same folds, seeds and matching as s08.
Usage: python -I s10_ablation.py <features_dir> <results_dir> <comparison> [d2_key]
Writes results/ablation/<comparison>.json
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
import learn as LN  # noqa: E402
import s08_discriminate as S8  # noqa: E402


def main(fdir, res, cname, d2key=None):
    t0 = time.time()
    names = json.load(open(os.path.join(fdir, "names.json")))
    comp = [c for c in S8.build(res) if c["name"] == cname][0]
    js = json.load(open(os.path.join(res, "disc", cname + ".json")))
    if d2key is None:
        cands = {k: v["auc"] for k, v in js["classifiers"].items() if k.startswith("D2_") and k.endswith("_tex")}
        d2key = max(cands, key=cands.get)
    _, kind, W, _ = d2key.split("_")
    A = S8.assemble(comp, fdir, names)
    seed = C.stable_int(comp["name"]) % 100000
    keep = {w: S8.match_windows(A, w, seed) for w in (64, 300)}
    okf = S8.equalise(A, keep[64], seed)
    sel = np.flatnonzero(okf)
    remap = -np.ones(len(A["y"]), int)
    remap[sel] = np.arange(sel.size)
    y = A["y"][sel]
    pid = A["pair"][sel] if A["pair"] is not None else None
    groups = A["groups"][sel]
    bidx = LN.boot_indices(y, pid, 2000, seed)
    pre = A["pre"]
    key = f"{pre}{W}"
    nm = names[key]
    if W == "seg":
        Xall = np.vstack([A["D"][i][key] for i in sel]).astype(np.float64)
        rf, yr, gr = np.arange(sel.size), y.copy(), groups.copy()
    else:
        W = int(W)
        Xs, rf, yr, gr = [], [], [], []
        for i in sel:
            k = keep[W][i]
            if k.any():
                Xs.append(A["D"][i][key][k])
                rf.append(np.full(k.sum(), remap[i]))
                yr.append(np.full(k.sum(), A["y"][i]))
                gr.append(np.full(k.sum(), A["groups"][i]))
        Xall = np.vstack(Xs).astype(np.float64)
        rf, yr, gr = np.concatenate(rf), np.concatenate(yr), np.concatenate(gr)
    Xall[~np.isfinite(Xall)] = np.nan
    fam = np.array([n.split("|")[0] for n in nm])
    out = {"comparison": cname, "classifier": d2key, "configs": {}}

    def run(tag, mask):
        if mask.sum() == 0:
            return
        s, _, _ = LN.cv_scores(kind, Xall[:, mask], yr, rf, sel.size, gr, seed, n_jobs=8)
        a = LN.auc(y, s)
        bs = LN.boot_auc(y, s, bidx)
        out["configs"][tag] = {"auc": a, "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                               "n_features": int(mask.sum())}
        print(f"  {cname} {d2key} {tag:22s} AUC {a:.3f} [{out['configs'][tag]['ci95'][0]:.3f}, "
              f"{out['configs'][tag]['ci95'][1]:.3f}] nf={mask.sum()} t={time.time() - t0:.0f}s", flush=True)
    tex = np.isin(fam, C.TEXTURE_FAMILIES)
    run("all_texture", tex)
    for f in C.TEXTURE_FAMILIES:
        run(f"drop_{f}", tex & (fam != f))
    for f in C.TEXTURE_FAMILIES:
        run(f"only_{f}", fam == f)
    # engine group: channel-family subsets within the texture families (which signals carry the cue?)
    if pre == "eng":
        chan = np.array([n.split("|")[1].split("_")[0] if n.split("|")[1] != "X" else "X" for n in nm]) if W != "seg" else \
            np.array([n.split("|")[2].split("_")[0] if n.split("|")[1] != "ratio" else n.split("|")[2].split("_")[0] for n in nm])
        for cf in C.FAMILIES:
            run(f"onlychan_{cf}", tex & (chan == cf))
    # ---- D3 input ablation (64-s residual windows)
    from aeon.transformations.collection.convolution_based import MiniRocket
    akey = f"{A['d3']}64"
    Xs, rf3, gr3 = [], [], []
    for i in sel:
        k = keep[64][i]
        if k.any():
            Xs.append(A["D"][i][akey][k].astype(np.float32))
            rf3.append(np.full(k.sum(), remap[i]))
            gr3.append(np.full(k.sum(), A["groups"][i]))
    X3 = np.nan_to_num(np.concatenate(Xs).astype(np.float64))
    rf3, gr3 = np.concatenate(rf3), np.concatenate(gr3)
    variants = {}
    if pre == "eng":
        for j, cf in enumerate(C.FAMILIES):
            variants[f"D3_64_onlychan_{cf}"] = X3[:, 4 * j:4 * j + 4, :]
    else:
        Xz = X3.copy()
        Xz[np.abs(Xz) > 500] = 0.0                   # sentinel samples (about -1900 LSB) removed
        variants["D3_64_sentinels_zeroed"] = Xz
    for tag, Xv in variants.items():
        Z = LN.standardise(MiniRocket(n_kernels=10000, random_state=seed, n_jobs=8).fit_transform(Xv).astype(np.float64))
        s, _, _ = LN.ridge_cv_scores(Z, y[rf3], rf3, sel.size, gr3, seed)
        a = LN.auc(y, s)
        bs = LN.boot_auc(y, s, bidx)
        out["configs"][tag] = {"auc": a, "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
        print(f"  {cname} {tag:30s} AUC {a:.3f} t={time.time() - t0:.0f}s", flush=True)
    os.makedirs(os.path.join(res, "ablation"), exist_ok=True)
    with open(os.path.join(res, "ablation", cname + ".json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
