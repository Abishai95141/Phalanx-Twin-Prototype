"""Write synthetic MAT files (PREREGISTRATION section 6.4-6.5).

Each synthetic file is a copy of the source flight's MAT file in which ONLY the 16 engine arrays (N1, N2, EGT, FF
x 4) are replaced, cast to the original container dtype and shape, so real and synthetic files pass through the
identical dlio.load_flight path. The generator sees only the flight's INPUTS (PLA_1..4, ALT, MACH, TAT, PH via
r2common.load(..., with_outputs=False)); the original engine arrays are used for nothing but their dtype and
shape (container metadata), and are overwritten. Untouched variables round-trip bit-exactly (checked on every
25th file and on the first file).

Arms: R2a = M-A + M-B; R2b = M-A + M-C + M-B. Offsets: prior (one virtual tail, key "virtual_tail_1") or cal.
R1-ref: round-1 FULL texture (T1-L6, primary f_c) on the low-passed real truth, round-1 code and parameters
(read-only); only the 16 engine arrays are replaced (VRTG stays real: out of round-2 scope).

Usage: python -I s03_synth.py <src_mat_dir> <flight_list_file> <model_dir|R1REF> <arm R2a|R2b|R1ref> <offsets prior|cal>
                              <out_dir> [n_workers] [texture_results_dir (R1ref only)]
"""
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import scipy.io as sio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402
import ma_model as MAM  # noqa: E402
import mb_model as MBM  # noqa: E402
import mc_model as MCM  # noqa: E402
import synth as SY  # noqa: E402

G = {}


def load_models(model_dir):
    ma = MAM.load(os.path.join(model_dir, "ma.json"))
    mb = MBM.MB(json.load(open(os.path.join(model_dir, "mb.json"))))
    mc = MCM.MC(json.load(open(os.path.join(model_dir, "mc.json"))))
    offt = json.load(open(os.path.join(model_dir, "offstate.json")))
    return ma, mb, mc, offt


def winit(model_dir, arm, mode, out, tex):
    G.update(arm=arm, mode=mode, out=out, tex=tex)
    if arm == "R1ref":
        from pipeline import Pipe
        G["r1params"] = json.load(open(os.path.join(R.R1_RES, "model_params_primary.json")))
        G["pipe"] = Pipe(tex, G["r1params"]["fixed"]["lattice"])
    else:
        G["models"] = load_models(model_dir)


def r1ref_arrays(path):
    import config as C1
    import fitstats as FS
    from texture_model import Generator
    from dlio import load_flight
    F = load_flight(path)
    ctx = FS.build_ctx(F, G["pipe"], "primary")
    arr = Generator(G["pipe"], G["r1params"]).generate(ctx, "L6", C1.flight_id(path), arm="T1")
    return {ch: arr[ch] for ch in R.CH16}


def per_flight(args):
    path, check = args
    fn = os.path.basename(path)
    raw = sio.loadmat(path, squeeze_me=False, struct_as_record=True)
    raw = {k: v for k, v in raw.items() if not k.startswith("__")}
    meta = {ch: (raw[ch][0, 0]["data"].dtype, raw[ch][0, 0]["data"].shape) for ch in R.CH16}
    if G["arm"] == "R1ref":
        arrays = r1ref_arrays(path)
    else:
        ma, mb, mc, offt = G["models"]
        d = R.load(path, with_outputs=False)                       # inputs only
        Y = SY.synth_flight(d, ma, mb, offt, mode=G["mode"], mc=(mc if G["arm"] == "R2b" else None))
        arrays = {}
        for f in R.FAM:
            for k in range(4):
                ch = f"{f}_{k + 1}"
                dt, shp = meta[ch]
                n = int(np.prod(shp))
                y = Y[f][k]
                if y.size < n:
                    y = np.r_[y, np.full(n - y.size, y[-1])]
                arrays[ch] = MBM.cast(y[:n], dt)
    new = dict(raw)
    for ch, arr in arrays.items():
        st = raw[ch].copy()
        orig = st[0, 0]["data"]
        arr = np.asarray(arr)
        assert arr.dtype == orig.dtype, (ch, arr.dtype, orig.dtype)
        st[0, 0]["data"] = arr.reshape(orig.shape)
        new[ch] = st
    op = os.path.join(G["out"], fn)
    sio.savemat(op, new, do_compression=True, format="5")
    if check:
        from dlio import load_flight
        A, B = load_flight(path), load_flight(op)
        assert list(A) == list(B)
        for k in A:
            if k in arrays:
                assert B[k].dtype == A[k].dtype and B[k].raw.shape == A[k].raw.shape
                continue
            assert np.array_equal(A[k].raw, B[k].raw) and A[k].dtype == B[k].dtype and A[k].rate == B[k].rate, k
    return fn


def main():
    a = sys.argv
    src, lst, model_dir, arm, mode, out = a[1:7]
    nw = int(a[7]) if len(a) > 7 else 8
    tex = a[8] if len(a) > 8 else os.path.join(R.TEXTURE_DIR, "results")
    files = [l.strip() for l in open(lst) if l.strip()]
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    jobs = [(os.path.join(src, f), i % 25 == 0) for i, f in enumerate(files)]
    with Pool(nw, initializer=winit, initargs=(model_dir, arm, mode, out, tex)) as pool:
        done = pool.map(per_flight, jobs, chunksize=1)
    with open(os.path.join(out, "_synth_manifest.json"), "w") as fh:
        json.dump({"src": src, "model_dir": model_dir, "arm": arm, "offsets": mode, "n": len(done),
                   "roundtrip_checked_every": 25, "seconds": time.time() - t0, "files": done}, fh, indent=1)
    print(f"{arm}/{mode}: wrote {len(done)} files to {out} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
