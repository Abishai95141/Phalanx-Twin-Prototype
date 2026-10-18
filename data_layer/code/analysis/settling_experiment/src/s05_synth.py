"""Step 5 -- write synthetic MAT files for every 687-TEST flight, arm and level.

Each synthetic file is a copy of the real file in which ONLY the channel-group arrays (N1/N2/EGT/FF x4, VRTG)
are replaced, cast to that file's original dtype, so real and synthetic data pass through the identical
dlio.load_flight path. Untouched variables round-trip bit-exactly (checked on every 50th file).

Variants: primary f_c: T1 x {L0..L6, L6'} and T2 x {L0..L6, L6'} (T2-L6 = L7 = FULL T2);
          sensitivity f_c (low, high): T1-L0, T1-L6, T2-L0, T2-L6.
T2 unit structure: one virtual four-engine aircraft drawn from the CAL fleet prior (not Tail 687's own
offsets): b_k(L) = a_k + s_k (L - L_ref) + j_k(flight) + d_k * days/30, centred across the four engines,
a_k ~ N(0, s_a^2), s_k ~ N(0, s_s^2), d_k ~ N(0, s_d^2), j_k AR(1) over the date-ordered TEST flights.

Usage: python -I s05_synth.py <mat687_dir> <texture_results_dir> <results_dir> <synthetic_out_dir> [n_workers]
"""
import csv
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import scipy.io as sio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
from dlio import load_flight, parse_fname  # noqa: E402
from pipeline import Pipe  # noqa: E402
from texture_model import Generator  # noqa: E402
import fitstats as FS  # noqa: E402

G = {}


def variants():
    v = [(arm, lv, "primary") for arm in ("T1", "T2") for lv in C.LEVELS]
    v += [(arm, lv, fk) for fk in ("low", "high") for arm in ("T1", "T2") for lv in ("L0", "L6")]
    return v


def t2_biases(test_files, fixed):
    """{file: {channel: (const, slope, L_ref)}} for the virtual tail."""
    days = []
    for f in test_files:
        m = parse_fname(f)
        days.append((np.datetime64(f"{m['year']:04d}-{m['month']:02d}-{m['day']:02d}") - np.datetime64("2001-01-01")).astype(int))
    days = np.array(days, float) - min(days)
    out = {f: {} for f in test_files}
    for fam in C.FAMILIES:
        p = fixed["t2"][fam]
        r = C.rng_for("T2tail", fam)
        a = r.normal(0, p["s_a"], 4)
        s = r.normal(0, p["s_s"], 4)
        d = r.normal(0, p["s_d_30d"], 4)
        j = np.zeros((len(test_files), 4))
        rj = C.rng_for("T2jitter", fam)
        rho, sj = p["rho_j"], p["s_j"]
        j[0] = rj.normal(0, sj, 4)
        for n in range(1, len(test_files)):
            j[n] = rho * j[n - 1] + np.sqrt(1 - rho ** 2) * rj.normal(0, sj, 4)
        a, s, d = a - a.mean(), s - s.mean(), d - d.mean()
        j = j - j.mean(1, keepdims=True)
        for n, f in enumerate(test_files):
            for k in range(4):
                out[f][f"{fam}_{k + 1}"] = (float(a[k] + j[n, k] + d[k] * days[n] / 30.0), float(s[k]), p["L_ref"])
    return out


def winit(tex_res, params, biases, out_dir):
    G["pipe"] = Pipe(tex_res, params["primary"]["fixed"]["lattice"])
    G["gen"] = {fk: Generator(G["pipe"], params[fk]) for fk in params}
    G["bias"] = biases
    G["out"] = out_dir


def make_bias_fns(bdict):
    return {ch: (lambda L, c=c, s=s, Lr=Lr: c + s * (L - Lr)) for ch, (c, s, Lr) in bdict.items()}


def per_flight(args):
    path, check = args
    fn = os.path.basename(path)
    fid = C.flight_id(path)
    raw = sio.loadmat(path, squeeze_me=False, struct_as_record=True)
    raw = {k: v for k, v in raw.items() if not k.startswith("__")}
    F = load_flight(path)
    vs = variants()
    ctxs = {fk: FS.build_ctx(F, G["pipe"], fk) for fk in sorted(set(v[2] for v in vs))}
    bias = make_bias_fns(G["bias"][fn])
    n_written = 0
    for arm, lv, fk in vs:
        name = C.variant_name(arm, lv, fk)
        od = os.path.join(G["out"], name)
        os.makedirs(od, exist_ok=True)
        arrays = G["gen"][fk].generate(ctxs[fk], lv, fid, arm=arm, bias=bias if arm == "T2" else None)
        new = dict(raw)
        for ch, arr in arrays.items():
            st = raw[ch].copy()
            orig = st[0, 0]["data"]
            assert arr.dtype == orig.dtype, (ch, arr.dtype, orig.dtype)
            st[0, 0]["data"] = arr.reshape(orig.shape)
            new[ch] = st
        op = os.path.join(od, fn)
        sio.savemat(op, new, do_compression=True, format="5")
        n_written += 1
        if check:
            A, B = load_flight(path), load_flight(op)
            assert list(A) == list(B)
            for k in A:
                if k in arrays:
                    assert B[k].dtype == A[k].dtype and B[k].raw.shape == A[k].raw.shape
                    continue
                assert np.array_equal(A[k].raw, B[k].raw) and A[k].dtype == B[k].dtype and A[k].units == B[k].units \
                    and A[k].desc == B[k].desc and A[k].rate == B[k].rate, k
    return fn, n_written


def main(mat687, tex_res, res, out_dir, nw=8):
    t0 = time.time()
    rows = list(csv.DictReader(open(os.path.join(res, "splits.csv"))))
    test = sorted(r["file"] for r in rows if r["set"] == "687-TEST")
    params = {fk: json.load(open(os.path.join(res, f"model_params_{fk}.json"))) for fk in C.FC}
    biases = t2_biases(test, params["primary"]["fixed"])
    with open(os.path.join(res, "t2_virtual_tail_biases.json"), "w") as fh:
        json.dump(biases, fh)
    os.makedirs(out_dir, exist_ok=True)
    jobs = [(os.path.join(mat687, f), i % 50 == 0) for i, f in enumerate(test)]
    with Pool(nw, initializer=winit, initargs=(tex_res, params, biases, out_dir)) as pool:
        done = pool.map(per_flight, jobs, chunksize=1)
    with open(os.path.join(res, "synthetic_manifest.json"), "w") as fh:
        json.dump({"out_dir": out_dir, "variants": [C.variant_name(*v) for v in variants()],
                   "n_flights": len(done), "files_per_flight": done[0][1], "roundtrip_checked_every": 50,
                   "seconds": time.time() - t0}, fh, indent=1)
    print(f"wrote {sum(d[1] for d in done)} files in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 8)
