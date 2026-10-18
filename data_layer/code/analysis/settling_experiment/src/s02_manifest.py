"""Step 2 -- record SHA-256 hashes of every input (pre-registration section 7).

Usage: python -I s02_manifest.py <zip687> <mat687_dir> <zip652> <mat652_dir> <texture_results_dir> <results_dir>
Writes results/manifest.json (archives, every MAT file in splits.csv, reused result tables,
the pre-registration text, splits.csv itself and the package versions).
"""
import csv
import hashlib
import json
import os
import platform
import sys
from importlib import metadata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main(zip687, mat687, zip652, mat652, tex_res, res):
    out = {"created_utc": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(timespec="seconds"),
           "root_seed": C.ROOT_SEED, "python": platform.python_version(),
           "packages": {p: metadata.version(p) for p in ["numpy", "scipy", "scikit-learn", "aeon", "numba",
                                                          "pycatch22", "matplotlib"]}}
    out["archives"] = {os.path.basename(zip687): {"path": zip687, "sha256": sha256(zip687), "bytes": os.path.getsize(zip687)},
                       os.path.basename(zip652): {"path": zip652, "sha256": sha256(zip652), "bytes": os.path.getsize(zip652)}}
    exp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    out["preregistration_sha256"] = sha256(os.path.join(exp, "PREREGISTRATION.md"))
    out["splits_sha256"] = sha256(os.path.join(res, "splits.csv"))
    out["reused_tables"] = {f: sha256(os.path.join(tex_res, f)) for f in
                            ["eligible_flights.csv", "inventory_flights.csv", "param_table.csv", "dropouts_sentinels.csv",
                             "recorder_checks_flights.csv"]}
    out["reused_code"] = {f: sha256(os.path.join(C.TEXTURE_DIR, f)) for f in ["dlio.py", "common.py"]}
    mats = {}
    for r in csv.DictReader(open(os.path.join(res, "splits.csv"))):
        d = mat687 if r["tail"] == "687" else mat652
        mats[r["file"]] = {"set": r["set"], "sha256": sha256(os.path.join(d, r["file"]))}
    out["mat_files"] = mats
    with open(os.path.join(res, "manifest.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print("hashed", len(mats), "MAT files;", {k: v["sha256"][:16] for k, v in out["archives"].items()})


if __name__ == "__main__":
    main(*sys.argv[1:7])
