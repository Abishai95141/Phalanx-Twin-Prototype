"""Per-flight battery statistics (B1-B6, B9 rows) and G1 residue counts for one group of MAT files, read through
dlio.load_flight (r2common.load). Output: <stats_dir>/<label>/<flight>.npz (arrays only; loaded with
allow_pickle=False).

Usage: python -I s04_stats.py <mat_dir> <flight_list_file> <label> <stats_dir> [n_workers]
"""
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402
import battery as BT  # noqa: E402

RESP = {"N1": 0, "FF": 1, "EGT": 2}
DIRS = {"accel": 0, "decel": 1}
G1_P = {"N1": 32, "N2": 32, "EGT": 8, "FF": 8}


def g1_counts(Y):
    air = BT.air_mask(Y)
    out = {}
    for f in R.FAM:
        P = G1_P[f]
        rows = []
        for k in range(4):
            c = np.rint(Y[f][k][air] / R.LSB_REC[f]).astype(np.int64)
            rows.append(np.bincount(c % P, minlength=P))
        out[f"g1_{f}"] = np.array(rows, np.int64)
    return out


def job(args):
    path, op = args
    d = R.load(path)
    st = BT.flight_stats(d["Y"], d)
    z = {"air_frac": np.array(st["air_frac"])}
    for k in ("b1_slow", "b1_fast", "b1h_slow", "b1h_fast", "b2", "b3_coh", "b3_lgain", "b4", "b6"):
        if st[k] is not None:
            z[k] = np.asarray(st[k], float)
    z["b3_steps"] = np.array([(RESP[g], DIRS[dr], t) for g, dr, t in st["b3_steps"]], float).reshape(-1, 3)
    if st["b5"] is not None:
        mf, me = st["b5"]
        for k, v in mf.items():
            z[f"b5_ff_{k}"] = np.asarray(v, float)
        for k, v in me.items():
            z[f"b5_egt_{k}"] = np.asarray(v, float)
    if st["b9"] is not None:
        z["b9_X"], z["b9_y"] = st["b9"]
    z.update(g1_counts({f: d["Y"][f] for f in R.FAM}))
    tmp = op + ".tmp.npz"
    np.savez_compressed(tmp, **z)
    os.replace(tmp, op)
    return os.path.basename(path)


def load_stats(stats_dir, label, files):
    """List (aligned with files) of dicts of arrays (None when the file is missing)."""
    out = []
    for f in files:
        p = os.path.join(stats_dir, label, f.replace(".mat", ".npz"))
        if not os.path.exists(p):
            out.append(None)
            continue
        with np.load(p, allow_pickle=False) as z:
            out.append({k: z[k] for k in z.files})
    return out


def main():
    a = sys.argv
    mat_dir, lst, label, sdir = a[1:5]
    nw = int(a[5]) if len(a) > 5 else 8
    files = [l.strip() for l in open(lst) if l.strip()]
    od = os.path.join(sdir, label)
    os.makedirs(od, exist_ok=True)
    jobs = [(os.path.join(mat_dir, f), os.path.join(od, f.replace(".mat", ".npz"))) for f in files
            if not os.path.exists(os.path.join(od, f.replace(".mat", ".npz")))]
    t0 = time.time()
    with Pool(nw) as pool:
        for i, _ in enumerate(pool.imap_unordered(job, jobs, chunksize=1)):
            pass
    print(f"stats {label}: {len(jobs)} flights in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
