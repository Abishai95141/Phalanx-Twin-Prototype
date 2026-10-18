"""Step 6 -- extract features from every real and synthetic file through dlio.load_flight.

Labels: real687_<fc>, real652_<fc> for each truth cut-off key, and every synthetic variant (which carries
its own cut-off key). Output: <features_dir>/<label>/<flight>.npz plus <features_dir>/names.json.

Usage: python -I s06_features.py <mat687_dir> <mat652_dir> <texture_results_dir> <results_dir>
                                 <synthetic_dir> <features_dir> [n_workers] [only_label_prefix]
"""
import csv
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
from pipeline import Pipe  # noqa: E402
import features as FT  # noqa: E402

G = {}


def winit(tex_res, lattice):
    G["pipe"] = Pipe(tex_res, lattice)


def job(args):
    path, label, fk, out = args
    op = os.path.join(out, label, C.flight_id(path) + ".npz")
    if os.path.exists(op):
        return label, None
    d = FT.extract(path, G["pipe"], fk)
    names = d.pop("names")
    os.makedirs(os.path.dirname(op), exist_ok=True)
    tmp = op + ".tmp.npz"
    np.savez_compressed(tmp, **d)
    os.replace(tmp, op)
    return label, names


def main(mat687, mat652, tex_res, res, syn, out, nw=8, only=""):
    t0 = time.time()
    rows = list(csv.DictReader(open(os.path.join(res, "splits.csv"))))
    lattice = json.load(open(os.path.join(res, "model_params_primary.json")))["fixed"]["lattice"]
    test = [r["file"] for r in rows if r["set"] == "687-TEST"]
    t652 = [r["file"] for r in rows if r["set"] == "652"]
    jobs = []
    for fk in C.FC:
        jobs += [(os.path.join(mat687, f), f"real687_{fk}", fk, out) for f in test]
        jobs += [(os.path.join(mat652, f), f"real652_{fk}", fk, out) for f in t652]
    mp = os.path.join(res, "synthetic_manifest.json")
    man = json.load(open(mp)) if os.path.exists(mp) else {"variants": []}
    for v in man["variants"]:
        fk = v.split("_")[-1]
        jobs += [(os.path.join(syn, v, f), v, fk, out) for f in test]
    if only:
        jobs = [j for j in jobs if j[1].startswith(only)]
    print(len(jobs), "jobs", flush=True)
    names = {}
    with Pool(nw, initializer=winit, initargs=(tex_res, lattice)) as pool:
        for i, (label, nm) in enumerate(pool.imap_unordered(job, jobs, chunksize=2)):
            if nm is not None and not names:
                names = nm
            if i % 500 == 0:
                print(i, f"{time.time() - t0:.0f}s", flush=True)
    if names:
        with open(os.path.join(out, "names.json"), "w") as fh:
            json.dump(names, fh)
    print(f"done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], a[3], a[4], a[5], a[6], int(a[7]) if len(a) > 7 else 8, a[8] if len(a) > 8 else "")
