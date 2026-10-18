"""Larger CAL fold development run (DEVELOPMENT DIAGNOSTIC, never a verdict): synthesise the held-out flights of one
CV fold from the models fitted on the other folds, compute per-flight statistics, the development battery and
G0 / discriminator diagnostics.

Labels: S_R2a_prior, S_R2b_prior, S_R2a_cal, S_R2b_cal (variant S, fold models), P_R2a_prior, P_R2b_prior (if the P
fold model exists) and R1ref. Sample size: one held-out fold (50-51 flights) - the smallest set that is not the
20-flight sample batch and gives every flight an out-of-fold synthetic version (project rule 1).

Usage: python -I s11_dev_fold.py <fold> <cv_root> <mat687_dir> <texture_results_dir> <dev_root> [n_workers] [--no-disc]
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402

SRC = os.path.dirname(os.path.abspath(__file__))


def run(cmd, log):
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    with open(log, "a") as fh:
        fh.write(f"\n$ {' '.join(cmd)}\n{r.stdout}\n{r.stderr[-4000:]}\n[exit {r.returncode}]\n")
    if r.returncode != 0:
        raise SystemExit(f"failed: {' '.join(cmd)}\n{r.stderr[-3000:]}")
    print(r.stdout[-1500:], flush=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    k, cv, m687, tex, dev = args[:5]
    nw = args[5] if len(args) > 5 else "8"
    py = [sys.executable, "-I"]
    lst = os.path.join(cv, f"test_fold{k}.txt")
    syn = os.path.join(dev, f"syn_fold{k}")
    st = os.path.join(dev, f"stats_fold{k}")
    res = os.path.join(R.R2DIR, "results")
    log = os.path.join(res, f"log_dev_fold{k}.txt")
    labels = []
    for v in ("S", "P"):
        md = os.path.join(cv, v, f"fold{k}")
        if not os.path.exists(os.path.join(md, "mc.json")):
            continue
        for arm in ("R2a", "R2b"):
            for off in (("prior", "cal") if v == "S" else ("prior",)):
                lab = f"{v}_{arm}_{off}"
                labels.append(lab)
                if not os.path.exists(os.path.join(syn, lab, "_synth_manifest.json")):
                    run(py + [os.path.join(SRC, "s03_synth.py"), m687, lst, md, arm, off, os.path.join(syn, lab), nw], log)
    if not os.path.exists(os.path.join(syn, "R1ref", "_synth_manifest.json")):
        run(py + [os.path.join(SRC, "s03_synth.py"), m687, lst, "R1REF", "R1ref", "prior", os.path.join(syn, "R1ref"), nw, tex], log)
    labels.append("R1ref")
    run(py + [os.path.join(SRC, "s04_stats.py"), m687, lst, "real_cal", st, nw], log)
    for lab in labels:
        run(py + [os.path.join(SRC, "s04_stats.py"), os.path.join(syn, lab), lst, lab, st, nw], log)
    run(py + [os.path.join(SRC, "s08_dev_cv.py"), "battery", st, lst, os.path.join(res, f"dev_battery_fold{k}.json"), "real_cal",
              ",".join(labels)], log)
    if "--no-disc" not in sys.argv:
        for lab in ("S_R2a_prior", "S_R2b_prior"):
            run(py + [os.path.join(SRC, "s06_disc_guard.py"), m687, os.path.join(syn, lab), lst, os.path.join(dev, f"feat_fold{k}"),
                      lab, os.path.join(res, f"dev_disc_fold{k}_{lab}.json"), nw, tex], log)


if __name__ == "__main__":
    main()
