"""Fit M-A, M-B and M-C on a set of 687-CAL flights (all CAL for the freeze; training folds for CV).

Writes into <out_model_dir>:
  ma.json      M-A (knots, parameter vectors, layout, per-stage fit info incl. AR-inflated naive SEs)
  ma_readable.json  interpretable M-A summary (knot tables, time constants in s, offsets, exponent a)
  offstate.json     CAL engine-off readings per position (used outside running segments)
  mb.json      M-B (native-grid offsets, idiosyncratic noise sigma/phi, round-1 recorder-effect parameters)
  mc.json      M-C (VAR order, coefficients, scales, innovation covariance)
  fit_log.txt  log; flights.txt  the flights used
Usage: python -I s02_fit.py <mat687_dir> <out_model_dir> <flight_list_file|ALLCAL> <variant P|S> [K] [n_workers] [stride] [max_nfev]
                            [--init <ma.json of a previous fit (warm start)>]
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
import mc_model as MCM  # noqa: E402
import synth as SY  # noqa: E402


def _load(p):
    return R.load(p)


def fit_all(mat687, files, out, variant, K=8, nw=8, stride=7, max_nfev=100, init=None):
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    lines = []

    def log(s):
        print(s, flush=True)
        lines.append(s)
        with open(os.path.join(out, "fit_log.txt"), "w") as fh:
            fh.write("\n".join(lines) + "\n")

    cal = set(R.cal_files())
    assert set(files) <= cal, "fit flights must be 687-CAL flights"
    with open(os.path.join(out, "flights.txt"), "w") as fh:
        fh.write("\n".join(files) + "\n")
    log(f"fit on {len(files)} 687-CAL flights, variant {variant}, K={K}, stride={stride}, max_nfev={max_nfev}")
    with Pool(nw) as pool:
        ds = pool.map(_load, [os.path.join(mat687, f) for f in files])
    log(f"loaded {time.time() - t0:.0f}s")
    B = MAM.Batch(ds, [MAM.running_mask_cal(d) for d in ds])
    del ds                                          # memory: reloaded below for M-B / M-C
    log(f"batch {B.n} samples, {len(B.seg)} running segments")
    init_m = MAM.load(init) if init else None
    if init:
        log(f"warm start from {init} (variant {init_m.variant})")
    ma = MAM.MA(K, variant).fit(B, stride=stride, max_nfev=max_nfev, log=log, init=init_m)
    # in-sample fit quality per output (all loss samples, CAL offsets)
    sim = ma.simulate(B)
    w = B.w > 0
    ins = {}
    for f in R.FAM:
        e = (sim[f] - B.Y[f])[w]
        ins[f] = {"rmse": float(np.sqrt(np.mean(e ** 2))), "bias": float(np.mean(e)),
                  "R2": float(1 - np.var(e) / np.var(B.Y[f][w]))}
    log("in-sample fit: " + json.dumps(ins))
    MAM.save(ma, os.path.join(out, "ma.json"))
    with open(os.path.join(out, "ma_readable.json"), "w") as fh:
        json.dump({"readable": ma.readable(), "in_sample_fit": ins}, fh, indent=1)
    del B, sim
    with Pool(nw) as pool:
        ds = pool.map(_load, [os.path.join(mat687, f) for f in files])
    offt = SY.off_state_table(ds)
    with open(os.path.join(out, "offstate.json"), "w") as fh:
        json.dump(offt, fh, indent=1)
    log(f"engine-off table {offt}")
    mbp = MBM.fit(ds, ma, log=log)
    with open(os.path.join(out, "mb.json"), "w") as fh:
        json.dump(mbp, fh, indent=1)
    log("M-B sigma " + json.dumps({k: round(v["sigma"], 5) for k, v in mbp["noise"].items()}))
    mc = MCM.MC.fit(ds, ma, mbp, log=log)
    with open(os.path.join(out, "mc.json"), "w") as fh:
        json.dump(mc.P, fh)
    log(f"done {time.time() - t0:.0f}s")


def main():
    init = None
    if "--init" in sys.argv:
        i = sys.argv.index("--init")
        init = sys.argv[i + 1]
        del sys.argv[i:i + 2]
    a = sys.argv
    mat687, out, lst = a[1], a[2], a[3]
    files = R.cal_files() if lst == "ALLCAL" else [l.strip() for l in open(lst) if l.strip()]
    variant = a[4]
    K = int(a[5]) if len(a) > 5 else 8
    nw = int(a[6]) if len(a) > 6 else 8
    stride = int(a[7]) if len(a) > 7 else 7
    nfev = int(a[8]) if len(a) > 8 else 100
    fit_all(mat687, files, out, variant, K, nw, stride, nfev, init)


if __name__ == "__main__":
    main()
