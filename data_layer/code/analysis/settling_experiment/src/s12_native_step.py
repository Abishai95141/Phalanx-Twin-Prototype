"""CAL-only diagnostic (no model change): does the use of lattice codes imply a native quantisation step
that differs from the recorder LSB (double quantisation, e.g. a 0.8 degC sensor step re-rounded to 0.5 degC)?

For every group channel, on 687-CAL only:
  code k = rint(x / LSB) (VRTG: code of the float32 affine map, code 0 = sentinel excluded);
  c_k  = number of samples on code k (all CAL flights pooled);
  dense range = codes between the 1st and 99th percentile of the samples;
  ratio_k = c_k / centred 33-code moving average of c  (removes the shape of the value distribution);
  model: the signal is first quantised with native step r (in LSB) and offset phi, then re-rounded to the
         recorder lattice, so code k receives n_k(r, phi) = #{m : k - 1/2 <= m r + phi < k + 1/2} native values;
  fit: r in [0.25, 4] (step 0.0005), phi in [0, 1) (step 0.02), maximise corr(ratio_k, n_k) over the dense range.
Evidence reported: fraction of never-used codes in the dense range, the residue-usage table modulo the
implied period P (smallest P <= 64 with P / r within 1 % of an integer), best r and its correlation,
and the best correlation among r in [0.95, 1.05] (= "no double quantisation" reference).

Usage: python -I s12_native_step.py <mat687_dir> <texture_results_dir> <results_dir>
Writes results/native_step_cal.json
"""
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
from dlio import load_flight  # noqa: E402
from pipeline import Pipe  # noqa: E402

RGRID = np.arange(0.25, 4.0 + 1e-9, 0.0005)
PHIS = np.arange(0.0, 1.0, 0.02)


def codes(pipe, ch, x):
    m = pipe.sentinel_mask(ch, x)
    x = x[~m]
    if ch == C.VRTG:
        a, b = pipe.lattice[ch]["a"], pipe.lattice[ch]["b"]
        k = np.rint((x - b) / a).astype(np.int64)
        return k[k > 0]
    return np.rint(x / pipe.lsb[ch]).astype(np.int64)


def fit(c, lo, hi):
    k = np.arange(lo, hi + 1)
    cc = c[lo:hi + 1].astype(float)
    w = 33
    sm = np.convolve(c.astype(float), np.ones(w) / w, mode="same")[lo:hi + 1]
    ratio = np.where(sm > 0, cc / np.maximum(sm, 1e-12), np.nan)
    ok = np.isfinite(ratio)
    k, ratio = k[ok], ratio[ok]
    rz = (ratio - ratio.mean()) / (ratio.std() if ratio.std() > 0 else 1)
    best = (-2, None, None)
    ref = -2
    for i in range(0, RGRID.size, 400):
        rs = RGRID[i:i + 400][:, None, None]
        ph = PHIS[None, :, None]
        kk = k[None, None, :]
        n = np.floor((kk + 0.5 - ph) / rs) - np.floor((kk - 0.5 - ph) / rs)
        nm = n.mean(2, keepdims=True)
        ns = n.std(2, keepdims=True)
        z = np.where(ns > 0, (n - nm) / np.where(ns > 0, ns, 1), 0)
        corr = (z * rz[None, None, :]).mean(2)
        j = np.unravel_index(np.argmax(corr), corr.shape)
        if corr[j] > best[0]:
            best = (float(corr[j]), float(RGRID[i + j[0]]), float(PHIS[j[1]]))
        near = (RGRID[i:i + 400] >= 0.95) & (RGRID[i:i + 400] <= 1.05)
        if near.any():
            ref = max(ref, float(corr[near].max()))
    return best, ref, float(np.mean(cc == 0))


def main(mat687, tex_res, res):
    rows = list(csv.DictReader(open(os.path.join(res, "splits.csv"))))
    cal = [r["file"] for r in rows if r["set"] == "687-CAL"]
    lattice = json.load(open(os.path.join(res, "model_params_primary.json")))["fixed"]["lattice"]
    pipe = Pipe(tex_res, lattice)
    acc = {ch: [] for ch in C.GROUP}
    for f in cal:
        F = load_flight(os.path.join(mat687, f))
        for ch in C.GROUP:
            acc[ch].append(codes(pipe, ch, F[ch].x))
    out = {"source": "687-CAL only (152 flights)", "channels": {}}
    for ch in C.GROUP:
        k = np.concatenate(acc[ch])
        c = np.bincount(k - k.min())
        lo, hi = (np.percentile(k, [1, 99]) - k.min()).astype(int)
        (corr, r, phi), ref, miss = fit(c, lo, hi)
        step = pipe.step(ch)
        P = next((p for p in range(1, 65) if abs(p / r - round(p / r)) < 0.005 and round(p / r) >= 1), None)
        res_tab = None
        if P and P > 1:
            kk = np.arange(lo, hi + 1) + k.min()
            cnt = c[lo:hi + 1]
            res_tab = [float(cnt[(kk % P) == q].sum() / cnt.sum()) for q in range(P)]
        out["channels"][ch] = {"recorder_step": step, "dense_codes": int(hi - lo + 1),
                               "frac_unused_codes_in_dense_range": miss,
                               "best_native_step_lsb": r, "best_native_step_units": r * step, "best_offset": phi,
                               "corr_best": corr, "corr_best_near_r1": ref,
                               "implied_period_codes": P, "residue_usage_mod_P": res_tab}
        print(f"{ch:6s} unused {miss:.3f} r* {r:.4f} LSB = {r * step:.5g} units  corr {corr:.3f} (r~1: {ref:.3f})  P={P}"
              + (f" residues {np.round(res_tab, 3).tolist()}" if res_tab else ""), flush=True)
    with open(os.path.join(res, "native_step_cal.json"), "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
