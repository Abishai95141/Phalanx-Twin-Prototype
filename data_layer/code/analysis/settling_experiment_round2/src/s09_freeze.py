"""Freeze (PREREGISTRATION section 6): copy the models fitted on ALL 152 687-CAL flights into results/frozen/<variant>/
and record SHA-256 hashes of every parameter file, of the round-2 code, of the round-1 code/tables it imports, and
of the pre-registration in results/frozen_models.json. Run BEFORE any holdout data is read; then git commit.

Also writes results/manifest.json (PREREGISTRATION section 7): input hashes. Holdout archives get INTEGRITY metadata
only (zip SHA-256, size, file count and date range from the fetch log / round-1 manifest); no holdout flight is read.

Usage: python -I s09_freeze.py <fit_root (contains P/ and S/)> <results_dir> <mat687_dir> <raw2_dir>
"""
import hashlib
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402

PARAM_FILES = ["ma.json", "ma_readable.json", "mb.json", "mc.json", "offstate.json", "fit_log.txt", "flights.txt"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def manifest(res, mat687, raw2):
    import re
    import platform
    r1 = json.load(open(os.path.join(R.R1_RES, "manifest.json")))
    cal = R.cal_files()
    m = {"created": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "root_seed": R.ROOT_SEED, "python": platform.python_version(),
         "archives_round1_manifest": r1["archives"],
         "cal_mat_sha256": {f: sha(os.path.join(mat687, f)) for f in cal},
         "cal_mat_sha256_matches_round1": None, "archive2": {}}
    r1m = r1["mat_files"]
    m["cal_mat_sha256_matches_round1"] = all(
        (r1m[f]["sha256"] if isinstance(r1m[f], dict) else r1m[f]) == m["cal_mat_sha256"][f] for f in cal if f in r1m)
    log = os.path.join(raw2, "fetch.log")
    a2 = {"fetch_log": os.path.relpath(log, R.ROOT)}
    if os.path.exists(log):
        for l in open(log):
            g = re.match(r"(\S+ \S+) downloaded (\d+) bytes sha256=([0-9a-f]{64})", l.strip())
            if g:
                a2.update(downloaded_at=g.group(1), bytes_log=int(g.group(2)), sha256_log=g.group(3))
            g = re.match(r"(\S+ \S+) extracted n_mat=(\d+) first=(\S+) last=(\S+)", l.strip())
            if g:
                a2.update(extracted_at=g.group(1), n_mat=int(g.group(2)), first=g.group(3), last=g.group(4))
    z = os.path.join(raw2, "Tail_687_2.zip")
    if os.path.exists(z):
        a2["sha256_recomputed"] = sha(z)
        a2["bytes"] = os.path.getsize(z)
        a2["sha256_matches_log"] = a2["sha256_recomputed"] == a2.get("sha256_log")
    m["archive2"] = a2
    with open(os.path.join(res, "manifest.json"), "w") as fh:
        json.dump(m, fh, indent=1)
    print("manifest: CAL hashes match round 1:", m["cal_mat_sha256_matches_round1"], "| archive 2:",
          {k: v for k, v in a2.items() if k != "fetch_log"})


def main(fit_root, res, mat687, raw2):
    out = {"frozen_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "fitted_on": "all 152 687-CAL flights",
           "holdout_read_before_freeze": False, "variants": {}, "code": {}, "imported_round1": {}, "inputs": {}}
    for v in ("S", "P"):
        src = os.path.join(fit_root, v)
        dst = os.path.join(res, "frozen", v)
        os.makedirs(dst, exist_ok=True)
        files = R.cal_files()
        got = [l.strip() for l in open(os.path.join(src, "flights.txt")) if l.strip()]
        assert sorted(got) == sorted(files), f"variant {v} was not fitted on all CAL flights"
        out["variants"][v] = {}
        for f in PARAM_FILES:
            shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
            out["variants"][v][f] = sha(os.path.join(dst, f))
    for f in sorted(os.listdir(os.path.join(R.R2DIR, "src"))):
        if f.endswith(".py"):
            out["code"][f] = sha(os.path.join(R.R2DIR, "src", f))
    out["code"]["PREREGISTRATION.md"] = sha(os.path.join(R.R2DIR, "PREREGISTRATION.md"))
    for p in (os.path.join(R.TEXTURE_DIR, "dlio.py"), os.path.join(R.TEXTURE_DIR, "common.py"),
              os.path.join(R.TEXTURE_DIR, "transients.py"),
              *[os.path.join(R.R1_SRC, f) for f in ("config.py", "pipeline.py", "features.py", "learn.py", "s07_gate0.py",
                                                    "texture_model.py", "fitstats.py")],
              os.path.join(R.ROOT, "analysis", "correlation_check", "corr_check.py")):
        out["imported_round1"][os.path.relpath(p, R.ROOT)] = sha(p)
    for p in (os.path.join(R.R1_RES, f) for f in ("splits.csv", "model_params_primary.json", "native_step_cal.json",
                                                   "mechanism_decisions.json")):
        out["inputs"][os.path.relpath(p, R.ROOT)] = sha(p)
    for f in ("param_table.csv", "dropouts_sentinels.csv"):
        p = os.path.join(R.TEXTURE_DIR, "results", f)
        out["inputs"][os.path.relpath(p, R.ROOT)] = sha(p)
    with open(os.path.join(res, "frozen_models.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    manifest(res, mat687, raw2)
    print(json.dumps(out["variants"], indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
