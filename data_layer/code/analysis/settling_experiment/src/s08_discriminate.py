"""Step 8 -- discriminator ladder D1-D3 for every comparison (pre-registration section 4).

Comparisons (class 0 vs class 1):
  sim_<arm>_<level>_<group>[_<fc>] : real 687-TEST vs its synthetic versions (paired, 229 vs 229)
  tail_<group>[_<fc>]              : 687-TEST (random 110) vs 652 (110); windows matched on regime x TAT bin
  tailjul_<group>                  : 687-TEST July 2001 vs 652 July 2003, equal counts, matched as above
  temporal_<group>[_<fc>]          : 687-TEST Mar-May vs Jul-Sep (equal counts), matched as above
Groups: eng (16 engine channels, cross-channel features) and vrtg.
Discriminators per comparison:
  D2  LR and GB on texture-family features of 64-s windows, 300-s windows and whole segments (flight rows)
      [+ the same with all families incl. levels, secondary]
  D3  MiniRocket + ridge on residual windows (64 s, 300 s) [+ raw z-normalised 64-s windows, secondary]
  D1  per channel KS and Anderson-Darling (midrank) on pooled residual samples of the matched 64-s windows,
      chi-square on pooled first-difference (LSB) and lattice-fraction histograms; flight-level permutation p.
AUC: flight level, GroupKFold 5 x 3, bootstrap 2,000 (pairs resampled for paired designs), permutation
1,000 for D3 (batched ridge) and D1; D2 classifiers use the number of permutations given by --perm-d2
(windows) and --perm-seg (segment LR), default 0, because each D2 permutation is a full 15-fold refit
(see DEVIATIONS.md section F).

Usage: python -I s08_discriminate.py <features_dir> <results_dir> <comparison-name-regex> [--perm-d2 N] [--jobs N]
"""
import argparse
import csv
import json
import os
import re
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
import learn as LN  # noqa: E402

NB = 2000
NPERM = 1000


# ---------------------------------------------------------------- comparison definitions
def build(res, flight_sample=0):
    rows = list(csv.DictReader(open(os.path.join(res, "splits.csv"))))
    test = sorted(r["file"] for r in rows if r["set"] == "687-TEST")
    s652 = sorted(r["file"] for r in rows if r["set"] == "652")
    month = {r["file"]: int(r["month"]) for r in rows}
    rng = np.random.default_rng([C.ROOT_SEED, 1])
    test110 = sorted(rng.choice(test, len(s652), replace=False).tolist())
    jul7 = [f for f in test if month[f] == 7]
    jul2 = [f for f in s652 if month[f] == 7 and f.startswith("6522003")]
    n = min(len(jul7), len(jul2))
    rng = np.random.default_rng([C.ROOT_SEED, 2])
    jul7 = sorted(rng.choice(jul7, n, replace=False).tolist())
    jul2 = sorted(rng.choice(jul2, n, replace=False).tolist())
    early = [f for f in test if month[f] <= 5]
    late = [f for f in test if month[f] >= 7]
    n = min(len(early), len(late))
    rng = np.random.default_rng([C.ROOT_SEED, 3])
    early = sorted(rng.choice(early, n, replace=False).tolist())
    late = sorted(rng.choice(late, n, replace=False).tolist())
    comps = []
    for fk in C.FC:
        sfx = "" if fk == "primary" else f"_{fk}"
        levels = C.LEVELS if fk == "primary" else ["L0", "L6"]
        for grp in ("eng", "vrtg"):
            for arm in (("T1", "T2") if grp == "eng" else ("T1",)):
                for lv in levels:
                    comps.append({"name": f"sim_{arm}_{lv}_{grp}{sfx}", "group": grp, "fc": fk, "kind": "sim",
                                  "arm": arm, "level": lv, "paired": True,
                                  "A": (f"real687_{fk}", test), "B": (C.variant_name(arm, lv, fk), test)})
            comps.append({"name": f"tail_{grp}{sfx}", "group": grp, "fc": fk, "kind": "tail", "paired": False,
                          "A": (f"real687_{fk}", test110), "B": (f"real652_{fk}", s652)})
            comps.append({"name": f"temporal_{grp}{sfx}", "group": grp, "fc": fk, "kind": "temporal", "paired": False,
                          "A": (f"real687_{fk}", early), "B": (f"real687_{fk}", late)})
            if fk == "primary":
                comps.append({"name": f"tailjul_{grp}", "group": grp, "fc": fk, "kind": "tailjul", "paired": False,
                              "A": (f"real687_{fk}", jul7), "B": (f"real652_{fk}", jul2)})
    if flight_sample:
        # verification batches only (local-vs-Kaggle reproducibility): simulation comparisons are restricted to a
        # seeded sample of 687-TEST flights; every list above is built exactly as in the full run; names get _s<N>
        samp = sorted(np.random.default_rng([C.ROOT_SEED, 99]).choice(test, flight_sample, replace=False).tolist())
        for c in comps:
            if c["kind"] == "sim":
                c["A"] = (c["A"][0], samp)
                c["B"] = (c["B"][0], samp)
            c["name"] += f"_s{flight_sample}"
    return comps


# ---------------------------------------------------------------- data assembly
def load_class(fdir, label, files, keys):
    out = []
    for f in files:
        z = np.load(os.path.join(fdir, label, f.replace(".mat", ".npz")))
        out.append({k: z[k] for k in keys if k in z.files})
    return out


def assemble(comp, fdir, names):
    g = comp["group"]
    pre = "eng" if g == "eng" else "vrtg"
    d3 = "d3e" if g == "eng" else "d3v"
    keys = [f"{pre}64", f"{pre}300", f"{pre}seg", "meta64", "meta300", f"{d3}64", f"{d3}300", f"d3z{g[0]}64"] + \
           [k for ch in (C.ENG if g == "eng" else [C.VRTG]) for k in (f"d1r_{ch}", f"d1d_{ch}", f"d1f_{ch}")]
    la, fa = comp["A"]
    lb, fb = comp["B"]
    DA = load_class(fdir, la, fa, keys)
    DB = load_class(fdir, lb, fb, keys)
    flights = [(la, f) for f in fa] + [(lb, f) for f in fb]
    y = np.r_[np.zeros(len(fa), int), np.ones(len(fb), int)]
    D = DA + DB
    if comp["paired"]:
        pid = np.r_[np.arange(len(fa)), np.arange(len(fb))]
        groups = pid.copy()
    else:
        pid = None
        groups = np.arange(len(flights))
    return {"flights": flights, "y": y, "D": D, "pair": pid, "groups": groups, "pre": pre, "d3": d3, "g": g}


def match_windows(A, W, seed):
    """Window keep-masks per flight: regime x TAT-bin strata, equal window counts per class (unpaired)."""
    D, y = A["D"], A["y"]
    keep = [np.ones(d[f"meta{W}"].shape[0], bool) for d in D]
    if A["pair"] is not None:
        return keep
    rng = np.random.default_rng([C.ROOT_SEED, W, seed])
    strata = {}
    for i, d in enumerate(D):
        m = d[f"meta{W}"]
        for j in range(m.shape[0]):
            key = (int(m[j, 0]), int(np.floor(m[j, 3] / C.TAT_BIN_C)))
            strata.setdefault(key, {0: [], 1: []})[int(y[i])].append((i, j))
    keep = [np.zeros(d[f"meta{W}"].shape[0], bool) for d in D]
    for key, cl in sorted(strata.items()):
        n = min(len(cl[0]), len(cl[1]))
        for c in (0, 1):
            if n == 0:
                continue
            idx = rng.choice(len(cl[c]), n, replace=False)
            for t in idx:
                i, j = cl[c][t]
                keep[i][j] = True
    return keep


def equalise(A, keepW, seed):
    """Drop flights without matched windows, then equalise flight counts by random removal (unpaired)."""
    y = A["y"]
    has = np.array([k.any() for k in keepW])
    ok = has.copy()
    if A["pair"] is None:
        rng = np.random.default_rng([C.ROOT_SEED, 7, seed])
        i1, i0 = np.flatnonzero(ok & (y == 1)), np.flatnonzero(ok & (y == 0))
        n = min(i1.size, i0.size)
        ok = np.zeros_like(ok)
        ok[np.sort(rng.choice(i1, n, replace=False))] = True
        ok[np.sort(rng.choice(i0, n, replace=False))] = True
    else:
        both = np.zeros(ok.size, bool)
        for p in np.unique(A["pair"]):
            ix = np.flatnonzero(A["pair"] == p)
            if has[ix].all():
                both[ix] = True
        ok = both
    return ok


def feature_mask(names, fams):
    return np.array([n.split("|")[0] in fams for n in names])


# ---------------------------------------------------------------- D1
def d1_tests(A, keep64, okf, rng_seed):
    y = A["y"][okf]
    pid = A["pair"][okf] if A["pair"] is not None else None
    Dk = [A["D"][i] for i in np.flatnonzero(okf)]
    kk = [keep64[i] for i in np.flatnonzero(okf)]
    perms = LN.perm_labels_flight(y, pid, NPERM, rng_seed)
    allY = np.vstack([y, perms])
    chans = C.ENG if A["g"] == "eng" else [C.VRTG]
    out = {}
    rng = np.random.default_rng([C.ROOT_SEED, 11, rng_seed])
    for ch in chans:
        vals, fl = [], []
        for i, (d, k) in enumerate(zip(Dk, kk)):
            r = d[f"d1r_{ch}"]
            m = np.repeat(k, 64)[:r.size]
            v = r[m]
            if v.size > 200:
                v = rng.choice(v, 200, replace=False)
            vals.append(v)
            fl.append(np.full(v.size, i))
        v = np.concatenate(vals).astype(float)
        fl = np.concatenate(fl)
        uq, inv = np.unique(np.round(v, 6), return_inverse=True)
        H = np.zeros((len(Dk), uq.size))
        np.add.at(H, (fl, inv), 1)
        ks, ad = ks_ad_batch(allY, H)
        # lattice histograms
        hd = np.vstack([d[f"d1d_{ch}"] for d in Dk]).astype(float)
        hf = np.vstack([d[f"d1f_{ch}"] for d in Dk]).astype(float)
        cd, cf = chi2_batch(allY, hd), chi2_batch(allY, hf)
        out[ch] = {k: {"stat": float(s[0]), "p_perm": float((1 + np.sum(s[1:] >= s[0])) / (1 + NPERM))}
                   for k, s in (("KS", ks), ("AD", ad), ("chi2_diff", cd), ("chi2_latfrac", cf))}
    return out


def ks_ad_batch(Ys, H):
    """Two-sample KS and Anderson-Darling (Scholz-Stephens, midrank) for each label row of Ys (B x n_flights)."""
    l = H.sum(0)
    N = l.sum()
    B = np.cumsum(l)
    Ba = B - l / 2
    den = Ba * (N - Ba) - N * l / 4
    good = den > 0
    f1 = Ys @ H                                   # (B, L) counts of class 1 per distinct value
    n1 = f1.sum(1, keepdims=True)
    f0 = l[None, :] - f1
    n0 = N - n1
    M1 = np.cumsum(f1, 1)
    M0 = np.cumsum(f0, 1)
    ks = np.max(np.abs(M1 / n1 - M0 / n0), 1)
    Ma1 = M1 - f1 / 2
    Ma0 = M0 - f0 / 2
    t1 = (l * (N * Ma1 - n1 * Ba) ** 2)[:, good] / den[good]
    t0 = (l * (N * Ma0 - n0 * Ba) ** 2)[:, good] / den[good]
    ad = (N - 1) / N ** 2 * (t1.sum(1) / n1[:, 0] + t0.sum(1) / n0[:, 0])
    return ks, ad


def chi2_batch(Ys, Hf):
    c1 = Ys @ Hf
    c0 = Hf.sum(0)[None, :] - c1
    tot = c1 + c0
    m = tot[0] > 0
    n1 = c1.sum(1, keepdims=True)
    n0 = c0.sum(1, keepdims=True)
    N = n1 + n0
    e1 = tot * n1 / N
    e0 = tot * n0 / N
    return (((c1 - e1) ** 2 / np.maximum(e1, 1e-12) + (c0 - e0) ** 2 / np.maximum(e0, 1e-12))[:, m]).sum(1)


# ---------------------------------------------------------------- main per comparison
def run(comp, fdir, res, names, perm_d2, jobs, perm_seg=0):
    t0 = time.time()
    A = assemble(comp, fdir, names)
    seed = C.stable_int(comp["name"]) % 100000
    keep = {W: match_windows(A, W, seed) for W in (64, 300)}
    okf = equalise(A, keep[64], seed)
    y_f = A["y"]
    nfl = len(y_f)
    pre = A["pre"]
    out = {"name": comp["name"], "kind": comp["kind"], "group": comp["group"], "fc": comp["fc"],
           "level": comp.get("level"), "arm": comp.get("arm"), "n_flights_class": [int((okf & (y_f == c)).sum()) for c in (0, 1)],
           "classifiers": {}}
    sel = np.flatnonzero(okf)
    remap = -np.ones(nfl, int)
    remap[sel] = np.arange(sel.size)
    y = y_f[sel]
    pid = A["pair"][sel] if A["pair"] is not None else None
    groups = A["groups"][sel]
    bidx = LN.boot_indices(y, pid, NB, seed)
    permF = LN.perm_labels_flight(y, pid, NPERM, seed + 1)
    scores = {}

    def record(key, s, perm_aucs=None, nperm=0, extra=None, win=None):
        a = LN.auc(y, s)
        bs = LN.boot_auc(y, s, bidx)
        rec = {"auc": a, "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "n_boot": int(bs.size)}
        if win is not None:
            ws, wy, wrf = win
            bw = LN.boot_auc_windows(wy, ws, wrf, bidx[:500])
            rec["auc_window"] = LN.auc(wy, ws)
            rec["auc_window_ci95"] = [float(np.percentile(bw, 2.5)), float(np.percentile(bw, 97.5))]
            scores[key + "__win"] = ws.astype(np.float32)
            scores[key + "__rf"] = wrf.astype(np.int32)
        if perm_aucs is not None:
            rec["p_perm"] = float((1 + np.sum(perm_aucs >= a)) / (1 + perm_aucs.size))
            rec["n_perm"] = int(perm_aucs.size)
        if extra:
            rec.update(extra)
        out["classifiers"][key] = rec
        scores[key] = s
        print(f"  {comp['name']:28s} {key:22s} AUC {a:.3f} [{rec['ci95'][0]:.3f},{rec['ci95'][1]:.3f}]"
              + (f" p={rec['p_perm']:.4f}" if 'p_perm' in rec else "") + f"  t={time.time() - t0:.0f}s", flush=True)

    # ---------------- D2 on windows and segments
    for W in (64, 300, "seg"):
        key = f"{pre}{W}"
        nm = names[key]
        for famset, tag in ((C.TEXTURE_FAMILIES, "tex"), (C.FEATURE_FAMILIES, "all")):
            fm = feature_mask(nm, famset)
            if W == "seg":
                X = np.vstack([A["D"][i][key] for i in sel])[:, fm].astype(np.float64)
                rf = np.arange(sel.size)
                yr = y.copy()
                gr = groups.copy()
            else:
                Xs, rf, yr, gr = [], [], [], []
                for i in sel:
                    k = keep[W][i]
                    if not k.any():
                        continue
                    Xs.append(A["D"][i][key][k][:, fm])
                    rf.append(np.full(k.sum(), remap[i]))
                    yr.append(np.full(k.sum(), y_f[i]))
                    gr.append(np.full(k.sum(), A["groups"][i]))
                X = np.vstack(Xs).astype(np.float64)
                rf, yr, gr = np.concatenate(rf), np.concatenate(yr), np.concatenate(gr)
            X[~np.isfinite(X)] = np.nan
            for kind in ("lr", "gb"):
                if tag == "all" and kind == "gb" and W != "seg":
                    continue                       # secondary all-family runs: LR on windows, both on segments
                s, _, wsc = LN.cv_scores(kind, X, yr, rf, sel.size, gr, seed, n_jobs=jobs)
                pa = None
                nper = perm_seg if (W == "seg" and kind == "lr") else perm_d2
                if nper and tag == "tex":
                    pa = []
                    for b in range(nper):
                        yb = permF[b][rf]
                        sb, _, _ = LN.cv_scores(kind, X, yb, rf, sel.size, gr, seed, n_jobs=jobs)
                        pa.append(LN.auc(permF[b], sb))
                    pa = np.array(pa)
                record(f"D2_{kind}_{W}_{tag}", s, pa, extra={"n_rows": int(X.shape[0]), "n_features": int(fm.sum())},
                       win=(wsc, yr, rf) if W != "seg" else None)
    # ---------------- D3 MiniRocket
    from aeon.transformations.collection.convolution_based import MiniRocket
    for W, akey, tag in ((64, f"{A['d3']}64", "res"), (300, f"{A['d3']}300", "res"), (64, f"d3z{A['g'][0]}64", "rawz")):
        Xs, rf, gr = [], [], []
        for i in sel:
            k = keep[W][i]
            if not k.any():
                continue
            Xs.append(A["D"][i][akey][k].astype(np.float32))
            rf.append(np.full(k.sum(), remap[i]))
            gr.append(np.full(k.sum(), A["groups"][i]))
        X3 = np.concatenate(Xs).astype(np.float64)
        X3 = np.nan_to_num(X3, nan=0.0, posinf=0.0, neginf=0.0)
        rf, gr = np.concatenate(rf), np.concatenate(gr)
        yr = y[rf]
        mr = MiniRocket(n_kernels=10000, random_state=seed, n_jobs=jobs)
        Z = mr.fit_transform(X3).astype(np.float64)
        Z = LN.standardise(Z)
        PL = (2 * permF[:, rf] - 1.0).T                    # (rows, B)
        s, ps, wsc = LN.ridge_cv_scores(Z, yr, rf, sel.size, gr, seed, perm_labels=PL)
        pa = np.array([LN.auc(permF[b], ps[b]) for b in range(ps.shape[0])])
        record(f"D3_{W}_{tag}", s, pa, extra={"n_rows": int(Z.shape[0]), "n_features": int(Z.shape[1])}, win=(wsc, yr, rf))
        del Z, X3
    # ---------------- D1
    out["D1"] = d1_tests(A, keep[64], okf, seed + 2)
    out["seconds"] = time.time() - t0
    os.makedirs(os.path.join(res, "disc"), exist_ok=True)
    with open(os.path.join(res, "disc", comp["name"] + ".json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)
    np.savez(os.path.join(res, "disc", comp["name"] + ".npz"), y=y, pair=(pid if pid is not None else -np.ones(y.size, int)),
             flights=np.array([f"{A['flights'][i][0]}/{A['flights'][i][1]}" for i in sel]),
             **{k: v for k, v in scores.items()})
    print(f"{comp['name']} done in {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("features_dir")
    ap.add_argument("results_dir")
    ap.add_argument("pattern")
    ap.add_argument("--perm-d2", type=int, default=0)
    ap.add_argument("--perm-seg", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--flight-sample", type=int, default=0)
    a = ap.parse_args()
    names = json.load(open(os.path.join(a.features_dir, "names.json")))
    comps = [c for c in build(a.results_dir, a.flight_sample) if re.fullmatch(a.pattern, c["name"])]
    print("comparisons:", [c["name"] for c in comps], flush=True)
    for c in comps:
        if a.skip_existing and os.path.exists(os.path.join(a.results_dir, "disc", c["name"] + ".json")):
            continue
        run(c, a.features_dir, a.results_dir, names, a.perm_d2, a.jobs, a.perm_seg)


if __name__ == "__main__":
    main()
