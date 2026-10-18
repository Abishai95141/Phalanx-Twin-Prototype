"""Quick look (amendment A5; development diagnostic on 687-CAL only, never a verdict).

* 30 CAL flights (seed 20261015) fit a simplified M-A (same causal chain and corrections, K knots, default 5)
  and M-B (A2 native steps; idiosyncratic noise; round-1 recorder effects). No M-C.
* 20 OTHER CAL flights (next draws of the same generator) are synthesised from their inputs only
  (R2a-quick, fleet-prior offsets), and also with round-1's FULL texture on low-passed real truth (R1-ref =
  T1-L6 primary, round-1 code and parameters, read-only).
* B1 (slow/fast cohesion), B2 (lead-lag) and B5 (corrected scatter, EGT exponent) for real vs R2a-quick and
  real vs R1-ref (paired), plus a real-vs-real scale reference (the 20 eval flights vs 20 of the fit flights,
  unpaired).

Usage: python -I q01_quick_look.py <mat687_dir> <texture_results_dir> <out_results_dir> [K] [n_workers]
"""
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402
import ma_model as MAM  # noqa: E402
import mb_model as MBM  # noqa: E402
import synth as SY  # noqa: E402
import battery as BT  # noqa: E402

G = {}


def _load(p):
    return R.load(p)


def _r1ref(args):
    path, tex = args
    import config as C1                      # round-1 modules, read-only
    from pipeline import Pipe
    import fitstats as FS
    from texture_model import Generator
    from dlio import load_flight
    params = json.load(open(os.path.join(R.R1_RES, "model_params_primary.json")))
    pipe = Pipe(tex, params["fixed"]["lattice"])
    F = load_flight(path)
    ctx = FS.build_ctx(F, pipe, "primary")
    arr = Generator(pipe, params).generate(ctx, "L6", C1.flight_id(path), arm="T1")
    n = min(arr[f"N1_{k}"].size for k in (1, 2, 3, 4))
    return {f: np.vstack([np.asarray(arr[f"{f}_{k}"], float)[:n] for k in (1, 2, 3, 4)]) for f in R.FAM}


def stats_group(Ys, inputs):
    b1, b1h, b2, b5 = [], [], [], []
    for Y, d in zip(Ys, inputs):
        n = min(Y["N1"].shape[1], d["n"])
        Y = {f: Y[f][:, :n] for f in R.FAM}
        b1.append(BT.b1_stats(Y, 0.2))
        b1h.append(BT.b1_stats(Y, 0.5))
        b2.append(BT.b2_stats(Y))
        b5.append(BT.b5_moments(Y, d["theta"][:n], d["delta"][:n]))
    return {"b1": b1, "b1h": b1h, "b2": b2, "b5": b5}


def compare(SA, SB, paired, seed):
    """Distances between group A (synthetic or real) and group B (real reference)."""
    ok = [i for i in range(len(SA["b1"])) if SA["b1"][i] is not None and (not paired or SB["b1"][i] is not None)]
    okb = ok if paired else [i for i in range(len(SB["b1"])) if SB["b1"][i] is not None]
    sets = BT.boot_sets(len(ok), len(okb), paired, 2000, seed)
    out = {"n_flights": [len(ok), len(okb)]}
    for key, j, tag in (("b1", 0, "B1_slow_fc0.2"), ("b1", 1, "B1_fast_fc0.2"), ("b1h", 0, "B1_slow_fc0.5"), ("b1h", 1, "B1_fast_fc0.5")):
        A = np.array([SA[key][i][j] for i in ok])
        Bm = np.array([SB[key][i][j] for i in okb])
        d0, bs = BT.d_median_abs(A, Bm, sets)
        out[tag] = {"D": d0, "ci95": BT.ci(bs)}
    A = np.array([SA["b2"][i] for i in ok])
    Bm = np.array([SB["b2"][i] for i in okb])
    d0, bs = BT.d_median_abs(A, Bm, sets)
    out["B2_leadlag_s"] = {"D": d0, "ci95": BT.ci(bs), "median_lags_A": np.median(A, 0).tolist(),
                           "median_lags_B": np.median(Bm, 0).tolist()}
    r = BT.d_b5([SA["b5"][i] for i in ok], [SB["b5"][i] for i in okb], sets[:500])
    out["B5_scatter"] = {"D": r["D_scatter"][0], "ci95": BT.ci(r["D_scatter"][1]), "scatter_A": r["scatter"][0],
                         "scatter_B": r["scatter"][1]}
    out["B5_egt_exponent"] = {"D": r["D_a"][0], "ci95": BT.ci(r["D_a"][1]), "a_A": r["a"][0], "a_B": r["a"][1]}
    return out


def selected_pairs(S, fast=True):
    j = 1 if fast else 0
    show = ["N1_1~N2_1", "N1_1~EGT_1", "N1_1~FF_1", "EGT_1~FF_1", "N2_1~FF_1", "N1_1~N1_2", "EGT_1~EGT_2", "FF_1~FF_2"]
    A = np.array([s[j] for s in S["b1"] if s is not None])
    return {p: round(float(np.median(A[:, BT.PAIR_NAMES.index(p)])), 3) for p in show}


def main(mat687, tex, out, K=5, nw=8):
    t0 = time.time()
    log_lines = []

    def log(s):
        print(s, flush=True)
        log_lines.append(s)

    cal = R.cal_files()
    rng = np.random.default_rng(R.ROOT_SEED)
    perm = rng.permutation(len(cal))
    fit_files = sorted(cal[i] for i in perm[:30])
    eval_files = sorted(cal[i] for i in perm[30:50])
    assert not set(fit_files) & set(eval_files)
    log(f"quick look: fit {len(fit_files)} CAL flights, eval {len(eval_files)} other CAL flights, K={K}")
    with Pool(nw) as pool:
        fit_d = pool.map(_load, [os.path.join(mat687, f) for f in fit_files])
        ev_d = pool.map(_load, [os.path.join(mat687, f) for f in eval_files])
    log(f"loaded {time.time() - t0:.0f}s")
    # ---- M-A
    B = MAM.Batch(fit_d, [MAM.running_mask_cal(d) for d in fit_d])
    log(f"fit batch: {B.n} samples in {len(B.seg)} running segments")
    ma = MAM.MA(K, "P").fit(B, stride=3, max_nfev=80, log=log)   # re-run note: README (variant P, joint FFN2 stage)
    log(f"M-A fitted {time.time() - t0:.0f}s")
    # out-of-sample fit quality on the eval flights (CAL running mask; CAL offsets and prior offsets)
    Be = MAM.Batch(ev_d, [MAM.running_mask_cal(d) for d in ev_d])
    fq = {}
    for mode in ("cal", "prior"):
        sim = ma.simulate(Be, override=SY.unit_params(ma, mode))
        w = Be.w > 0
        fq[mode] = {}
        for f in R.FAM:
            e = (sim[f] - Be.Y[f])[w]
            fq[mode][f] = {"rmse": float(np.sqrt(np.mean(e ** 2))), "bias": float(np.mean(e)),
                           "R2": float(1 - np.var(e) / np.var(Be.Y[f][w]))}
    log("out-of-sample fit quality (eval flights): " + json.dumps(fq))
    # ---- M-B
    mbp = MBM.fit(fit_d, ma, log=log)
    log("M-B noise sigma: " + json.dumps({k: round(v["sigma"], 4) for k, v in mbp["noise"].items()}))
    log("M-B noise phi: " + json.dumps({k: round(v["phi"], 3) for k, v in mbp["noise"].items()}))
    mb = MBM.MB(mbp)
    offt = SY.off_state_table(fit_d)
    # ---- synthesise eval flights (inputs only)
    syn = []
    for d in ev_d:
        din = {k: v for k, v in d.items() if k not in ("Y",)}
        syn.append(SY.synth_flight(din, ma, mb, offt, mode="prior"))
    log(f"synthesised {len(syn)} flights {time.time() - t0:.0f}s")
    with Pool(nw) as pool:
        r1 = pool.map(_r1ref, [(os.path.join(mat687, f), tex) for f in eval_files])
    log(f"R1-ref generated {time.time() - t0:.0f}s")
    # ---- battery subset
    S_real = stats_group([d["Y"] for d in ev_d], ev_d)
    S_syn = stats_group(syn, ev_d)
    S_r1 = stats_group(r1, ev_d)
    S_fit = stats_group([d["Y"] for d in fit_d[:20]], fit_d[:20])
    res = {"note": "DEVELOPMENT DIAGNOSTIC on 687-CAL only (amendment A5). Not a verdict.",
           "fit_files": fit_files, "eval_files": eval_files, "K": K,
           "ma_fit_quality_eval": fq, "ma_params": ma.readable(), "mb": {k: v for k, v in mbp.items() if k != "fixed"},
           "R2a_quick_vs_real": compare(S_syn, S_real, True, 1),
           "R1ref_vs_real": compare(S_r1, S_real, True, 2),
           "real_fit20_vs_real_eval20": compare(S_fit, S_real, False, 3),
           "selected_fast_pairs": {"real": selected_pairs(S_real), "R2a_quick": selected_pairs(S_syn), "R1_ref": selected_pairs(S_r1)},
           "selected_slow_pairs": {"real": selected_pairs(S_real, False), "R2a_quick": selected_pairs(S_syn, False),
                                   "R1_ref": selected_pairs(S_r1, False)},
           "seconds": time.time() - t0}
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "quick_look.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    MAM.save(ma, os.path.join(out, "quick_look_ma.json"))
    with open(os.path.join(out, "log_quick_look.txt"), "w") as fh:
        fh.write("\n".join(log_lines) + "\n")
    for k in ("R2a_quick_vs_real", "R1ref_vs_real", "real_fit20_vs_real_eval20"):
        r = res[k]
        log(f"{k}: " + ", ".join(f"{t} {r[t]['D']:.3f} [{r[t]['ci95'][0]:.3f},{r[t]['ci95'][1]:.3f}]"
                                  for t in r if t.startswith("B")))
    log(json.dumps(res["selected_fast_pairs"]))
    log(f"done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], a[3], int(a[4]) if len(a) > 4 else 5, int(a[5]) if len(a) > 5 else 8)
