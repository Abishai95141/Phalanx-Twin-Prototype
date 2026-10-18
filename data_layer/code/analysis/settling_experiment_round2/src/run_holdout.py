"""Phase B: holdout evaluation with the FROZEN round-2 models (PREREGISTRATION sections 2, 4-6, 8; amendments A1, A8).

Do not run before the freeze commit. The runner refuses to start if any frozen parameter file or any round-2 source
file differs from the SHA-256 recorded in results/frozen_models.json (pass --allow-code-change only for a logged
deviation).

Steps
  0. Archive-2 status from <raw2>/fetch.log (fetcher markers "downloaded <n> bytes sha256=<h>" and
     "extracted n_mat=<n>"), reported with its time relative to the fallback deadline 2026-10-15 10:00 IST.
     Amendment A1: the fallback is already triggered; Tail 652 archive 8 is the PRIMARY holdout; archive 2 is a
     confirmatory holdout (--holdout 687a2) run with the identical frozen models when it is available.
  1. Holdout flight list saved BEFORE any analysis: 652 = the 110 eligible round-1 "652" flights (<= 200, so all);
     687a2 = eligible archive-2 flights (round-1 rule), sample of 200 with seed 20261015 if more.
     Bar groups (equal flight counts): D_tail partner = round-1 687-TEST (652 mode) or Tail 652 (687a2 mode),
     random sample of the holdout's size (seed 20261015); D_temp = holdout early vs late (median flight date).
  2. Synthesis from holdout INPUTS ONLY (s03_synth.py): variants S (primary, A6+A7) and P (pre-registered) x arms
     R2a, R2b x offsets prior (primary) / cal (secondary); and R1-ref (round-1 FULL texture, reference only).
     Synthetic MAT files under <syn_root>/<holdout>[_s<N>]/<label>/.
  3. Per-flight statistics (s04_stats.py) for real holdout, partner, and every synthetic label.
  4. Battery B1-B6 with joint flight bootstrap (2,000), per-test verdicts vs D_tail, STRICT PASS vs D_temp, B9, G1.
  5. G0 (binding, pipeline-only metadata) and discriminator diagnostics (s06_disc_guard.py) for S/P x R2a/R2b, prior.
  6. results/holdout_<holdout>[_s<N>]/results.json, figures, and REPORT.md (s10_report.py).

Usage:
  python -I run_holdout.py --holdout 652 --m687 <687 mat dir> --m652 <652 mat dir (read-only)> --raw2 <raw2 dir>
         --syn-root <synthetic root> [--sample 20] [--nw 8] [--steps all|0,1,2,3,4,5,6] [--no-d3]
"""
import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402

SRC = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(R.R2DIR, "results")
DEADLINE = "2026-10-15 10:00:00"
# code whose change after the freeze would change the synthetic data or the evaluation (hash-checked, binding)
BINDING_CODE = {"r2common.py", "ma_model.py", "mb_model.py", "mc_model.py", "synth.py", "s03_synth.py", "battery.py",
                "battery_eval.py", "s04_stats.py", "s06_disc_guard.py", "run_holdout.py"}
VARIANTS = ("S", "P")
ARMS = ("R2a", "R2b")
OFFS = ("prior", "cal")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_freeze(allow_code_change):
    fz = json.load(open(os.path.join(RES, "frozen_models.json")))
    bad = []
    for v, files in fz["variants"].items():
        for f, h in files.items():
            if sha(os.path.join(RES, "frozen", v, f)) != h:
                bad.append(f"frozen/{v}/{f}")
    for f, h in fz["code"].items():
        if f not in BINDING_CODE:
            continue                       # recorded at the freeze, not binding (report layout, dev/post-hoc scripts)
        p = os.path.join(SRC, f)
        if not os.path.exists(p) or sha(p) != h:
            bad.append(f"src/{f}")
    for f, h in fz["imported_round1"].items():
        if sha(os.path.join(R.ROOT, f)) != h:
            bad.append(f)
    if bad and not allow_code_change:
        raise SystemExit(f"frozen hash mismatch, refusing to run: {bad}")
    return {"frozen_at": fz["frozen_at"], "mismatches": bad}


def archive2_status(raw2):
    log = os.path.join(raw2, "fetch.log")
    st = {"fetch_log": log, "downloaded": False, "sha256": None, "bytes": None, "extracted": False, "n_mat": None,
          "extracted_at": None, "before_deadline": None, "last_line": None}
    if not os.path.exists(log):
        return st
    lines = [l.strip() for l in open(log) if l.strip()]
    st["last_line"] = lines[-1] if lines else None
    for l in lines:
        m = re.match(r"(\S+ \S+) downloaded (\d+) bytes sha256=([0-9a-f]{64})", l)
        if m:
            st.update(downloaded=True, bytes=int(m.group(2)), sha256=m.group(3))
        m = re.match(r"(\S+ \S+) extracted n_mat=(\d+)", l)
        if m:
            st.update(extracted=True, n_mat=int(m.group(2)), extracted_at=m.group(1))
    if st["extracted_at"]:
        st["before_deadline"] = st["extracted_at"] <= DEADLINE
    st["mat_dir_exists"] = os.path.isdir(os.path.join(raw2, "mat"))
    st["ready"] = bool(st["downloaded"] and st["extracted"] and st["mat_dir_exists"])
    return st


def eligible_meta(path):
    from dlio import load_flight, parse_fname
    m = parse_fname(path)
    F = load_flight(path)
    ph, w = F["PH"].x, F["WOW"].x
    return {"file": m["file"], "datestr": m["datestr"], "dup": m["dup_suffix"], "duration_s": F["FRMC"].x.size * 4,
            "n_wow": int(np.sum(np.abs(np.diff(w)) > 0)), "t_ph5": float(np.sum(ph == 5) / F["PH"].rate),
            "t_ph12": float(np.sum((ph == 1) | (ph == 2)) / F["PH"].rate)}


def holdout_lists(holdout, a, out):
    """Write and return {holdout, partner, early, late} flight lists (and the dir of each group)."""
    rows = R.splits()
    date = {r["file"]: r["datestr"] for r in rows}
    rng = np.random.default_rng(R.ROOT_SEED)
    if holdout == "devcal":
        # runner verification on CAL data only (before the freeze): CAL lists stand in for holdout and partner
        H = [l.strip() for l in open(a.dev_holdout_list) if l.strip()]
        partner = [l.strip() for l in open(a.dev_partner_list) if l.strip()][:len(H)]
        hdir = pdir = a.m687
        assert set(H) | set(partner) <= set(R.cal_files()), "devcal mode accepts CAL flights only"
    elif holdout == "652":
        H = sorted(r["file"] for r in rows if r["set"] == "652")
        hdir = a.m652
        test = sorted(r["file"] for r in rows if r["set"] == "687-TEST")
        partner = sorted(rng.choice(test, min(len(H), len(test)), replace=False).tolist())
        pdir = a.m687
    else:
        from dlio import list_flights
        from multiprocessing import Pool
        mdir = os.path.join(a.raw2, "mat")
        paths = list_flights(mdir)
        if not paths:                                  # extracted into a sub-directory
            for root, _, fs in os.walk(mdir):
                if any(f.endswith(".mat") for f in fs):
                    mdir, paths = root, list_flights(root)
                    break
        with Pool(a.nw) as pool:
            metas = pool.map(eligible_meta, paths)
        el = sorted(m["file"] for m in metas if (not m["dup"]) and m["duration_s"] >= 1800 and m["n_wow"] == 2
                    and m["t_ph5"] >= 600 and m["t_ph12"] >= 60)
        for m in metas:
            date[m["file"]] = m["datestr"]
        H = sorted(rng.choice(el, 200, replace=False).tolist()) if len(el) > 200 else el
        with open(os.path.join(out, "list_sample200.txt"), "w") as fh:     # saved before any analysis (section 2)
            fh.write("\n".join(H) + "\n")
        hdir = mdir
        s652 = sorted(r["file"] for r in rows if r["set"] == "652")
        n = min(len(H), len(s652))
        partner = sorted(rng.choice(s652, n, replace=False).tolist())
        if len(H) > n:
            # equal flight counts in every comparison (section 2): Tail 652 has 110 eligible flights, so D_sim, D_tail and
            # D_temp use a seeded subsample of the saved 200 (DEVIATIONS.md, clarification)
            H = sorted(rng.choice(H, n, replace=False).tolist())
        pdir = a.m652
        with open(os.path.join(out, "archive2_eligibility.json"), "w") as fh:
            json.dump({"n_files": len(paths), "n_eligible": len(el), "metas": metas}, fh)
    if a.sample:
        H = sorted(np.random.default_rng([R.ROOT_SEED, 99]).choice(H, min(a.sample, len(H)), replace=False).tolist())
        partner = sorted(np.random.default_rng([R.ROOT_SEED, 98]).choice(partner, len(H), replace=False).tolist())
    order = sorted(H, key=lambda f: date[f])
    h = len(order) // 2
    early, late = sorted(order[:h]), sorted(order[len(order) - h:])
    lists = {"holdout": H, "partner": partner, "early": early, "late": late}
    for k, v in lists.items():
        with open(os.path.join(out, f"list_{k}.txt"), "w") as fh:
            fh.write("\n".join(v) + "\n")
    meta = {"holdout": holdout, "holdout_dir": hdir, "partner_dir": pdir, "n": {k: len(v) for k, v in lists.items()},
            "median_date_split": [date[early[-1]], date[late[0]]] if h else None,
            "date_range": [date[order[0]], date[order[-1]]]}
    with open(os.path.join(out, "lists_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    return lists, meta


def input_check(path):
    """Report-only input validity of one holdout flight (inputs only; pre-specified before the freeze): fraction of
    airborne (WOW = 1) MACH samples equal to 0, TAT and ALT ranges, PLA range per lever. No flight is excluded."""
    from dlio import load_flight
    F = load_flight(path)
    air = np.repeat(F["WOW"].x == 1, 4)
    m = F["MACH"].x
    n = min(m.size, air.size)
    out = {"file": os.path.basename(path), "MACH_dtype": F["MACH"].dtype,
           "MACH_zero_frac_airborne": float(np.mean(m[:n][air[:n]] == 0)) if air[:n].any() else None,
           "TAT_range": [float(F["TAT"].x.min()), float(F["TAT"].x.max())],
           "ALT_range": [float(F["ALT"].x.min()), float(F["ALT"].x.max())],
           "PLA_range": [float(np.ptp(F[f"PLA_{k}"].x)) for k in (1, 2, 3, 4)]}
    out["flag"] = bool((out["MACH_zero_frac_airborne"] or 0) > 0.05 or min(out["PLA_range"]) < 5 or out["ALT_range"][1] < 5000)
    return out


def run(cmd, log):
    t = time.time()
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    with open(log, "a") as fh:
        fh.write(f"\n$ {' '.join(cmd)}\n{r.stdout}\n{r.stderr}\n[exit {r.returncode}, {time.time() - t:.0f}s]\n")
    if r.returncode != 0:
        raise SystemExit(f"step failed: {' '.join(cmd)}\n{r.stderr[-3000:]}")
    return r.stdout


def labels():
    return [f"{v}_{arm}_{off}" for v in VARIANTS for arm in ARMS for off in OFFS] + ["R1ref"]


def battery_all(sdir, lists, out):
    import battery_eval as BE
    from s04_stats import load_stats
    H, P, E, L = lists["holdout"], lists["partner"], lists["early"], lists["late"]
    SH = load_stats(sdir, "real_holdout", H)
    SP = load_stats(sdir, "real_partner", P)
    idx = {f: i for i, f in enumerate(H)}
    SE, SL = [SH[idx[f]] for f in E], [SH[idx[f]] for f in L]
    boot = BE.Bootstrap(R.ROOT_SEED)
    tail = BE.compare(SP, SH, "partner", "holdout", False, boot, real_is_B=True)
    temp = BE.compare(SL, SE, "late", "early", False, boot, real_is_B=True)
    res = {"D_tail": BE.summarise(tail), "D_temp": BE.summarise(temp), "arms": {},
           "groups": {"real_holdout": BE.group_values(SH), "real_partner": BE.group_values(SP)}}
    for lab in labels():
        S = load_stats(sdir, lab, H)
        sim = BE.compare(S, SH, "holdout", "holdout", True, boot)
        ver = BE.verdicts(sim, tail, temp)
        res["arms"][lab] = {"D_sim": BE.summarise(sim), "verdicts": ver, "B9": BE.b9(S, SH, R.ROOT_SEED),
                            "G1": BE.g1(S, SH), "group": BE.group_values(S)}
        print(lab, {t: v["verdict"] for t, v in ver.items()}, flush=True)
    return res


def choose(res, g0):
    """Decision per (variant, offsets): better of R2a/R2b (more PASS, fewer FAIL, smaller mean D_sim/D_tail)."""
    import battery_eval as BE
    out = {}
    for v in VARIANTS:
        for off in OFFS:
            cands = []
            for arm in ARMS:
                lab = f"{v}_{arm}_{off}"
                ver = res["arms"][lab]["verdicts"]
                npass = sum(x["verdict"] == "PASS" for x in ver.values())
                nfail = sum(x["verdict"] == "FAIL" for x in ver.values())
                ratio = np.nanmean([p["D_sim"] / p["D_tail"] for x in ver.values() for p in x["parts"].values()
                                    if p["D_tail"] and np.isfinite(p["D_tail"]) and p["D_tail"] > 0])
                cands.append((-npass, nfail, ratio, arm, lab))
            cands.sort()
            best = cands[0]
            g0key = f"{v}_{best[3]}_prior"
            g0_pass = g0.get(g0key, {}).get("pass") if off == "prior" else g0.get(g0key, {}).get("pass")
            dec = BE.decision(res["arms"][best[4]]["verdicts"], bool(g0_pass) if g0_pass is not None else False)
            dec["better_arm"] = best[3]
            dec["g0_pass_used"] = g0_pass
            dec["ranking"] = [(c[3], -c[0], c[1], float(c[2])) for c in cands]
            out[f"{v}_{off}"] = dec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", choices=["652", "687a2", "devcal"], default="652")
    ap.add_argument("--dev-models", default=None, help="devcal only: model root with S/ and P/ (instead of results/frozen)")
    ap.add_argument("--dev-holdout-list", default=None)
    ap.add_argument("--dev-partner-list", default=None)
    ap.add_argument("--m687", required=True)
    ap.add_argument("--m652", required=True)
    ap.add_argument("--raw2", required=True)
    ap.add_argument("--syn-root", required=True)
    ap.add_argument("--tex", default=os.path.join(R.TEXTURE_DIR, "results"))
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--nw", type=int, default=8)
    ap.add_argument("--steps", default="all")
    ap.add_argument("--no-d3", action="store_true")
    ap.add_argument("--allow-code-change", action="store_true")
    a = ap.parse_args()
    steps = set(range(7)) if a.steps == "all" else {int(s) for s in a.steps.split(",")}
    tag = a.holdout + (f"_s{a.sample}" if a.sample else "")
    out = os.path.join(RES, f"holdout_{tag}")
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, "log_runner.txt")
    syn = os.path.join(a.syn_root, tag)
    sdir = os.path.join(syn, "_stats")
    py = [sys.executable, "-I"]
    state_p = os.path.join(out, "state.json")
    state = json.load(open(state_p)) if os.path.exists(state_p) else {}
    state["freeze_check"] = check_freeze(a.allow_code_change) if a.holdout != "devcal" else {"frozen_at": "devcal (not frozen)", "mismatches": []}
    model_root = a.dev_models if a.holdout == "devcal" else os.path.join(RES, "frozen")
    state["archive2"] = archive2_status(a.raw2)
    state["mode"] = {"holdout": a.holdout, "primary": a.holdout == "652",
                     "note": "Amendment A1: Tail 652 archive 8 is the primary holdout (cross-tail transfer); Tail 687 "
                             "archive 2 is confirmatory when available."}
    if a.holdout == "687a2" and not state["archive2"]["ready"]:
        raise SystemExit("archive 2 is not downloaded, hash-recorded and extracted: " + json.dumps(state["archive2"]))
    json.dump(state, open(state_p, "w"), indent=1)
    print("archive-2 status:", json.dumps(state["archive2"]), flush=True)
    if 1 in steps or not os.path.exists(os.path.join(out, "lists_meta.json")):
        lists, meta = holdout_lists(a.holdout, a, out)
    else:
        lists = {k: [l.strip() for l in open(os.path.join(out, f"list_{k}.txt")) if l.strip()]
                 for k in ("holdout", "partner", "early", "late")}
        meta = json.load(open(os.path.join(out, "lists_meta.json")))
    print("lists:", meta["n"], flush=True)
    ic_p = os.path.join(out, "input_checks.json")
    if not os.path.exists(ic_p):
        from multiprocessing import Pool
        with Pool(a.nw) as pool:
            ic = pool.map(input_check, [os.path.join(meta["holdout_dir"], f) for f in lists["holdout"]])
        json.dump({"n_flagged": int(sum(r["flag"] for r in ic)), "rows": ic}, open(ic_p, "w"), indent=1)
        print("input checks: flagged", sum(r["flag"] for r in ic), "of", len(ic), flush=True)
    hdir, pdir = meta["holdout_dir"], meta["partner_dir"]
    LH, LP = os.path.join(out, "list_holdout.txt"), os.path.join(out, "list_partner.txt")
    if 2 in steps:
        for v in VARIANTS:
            for arm in ARMS:
                for off in OFFS:
                    lab = f"{v}_{arm}_{off}"
                    if not os.path.exists(os.path.join(syn, lab, "_synth_manifest.json")):
                        run(py + [os.path.join(SRC, "s03_synth.py"), hdir, LH, os.path.join(model_root, v), arm, off,
                                  os.path.join(syn, lab), str(a.nw)], log)
        if not os.path.exists(os.path.join(syn, "R1ref", "_synth_manifest.json")):
            run(py + [os.path.join(SRC, "s03_synth.py"), hdir, LH, "R1REF", "R1ref", "prior", os.path.join(syn, "R1ref"),
                      str(a.nw), a.tex], log)
    if 3 in steps:
        run(py + [os.path.join(SRC, "s04_stats.py"), hdir, LH, "real_holdout", sdir, str(a.nw)], log)
        run(py + [os.path.join(SRC, "s04_stats.py"), pdir, LP, "real_partner", sdir, str(a.nw)], log)
        for lab in labels():
            run(py + [os.path.join(SRC, "s04_stats.py"), os.path.join(syn, lab), LH, lab, sdir, str(a.nw)], log)
    if 4 in steps:
        res = battery_all(sdir, lists, out)
        with open(os.path.join(out, "battery.json"), "w") as fh:
            json.dump(res, fh, indent=1, default=float)
    g0 = {}
    if 5 in steps:
        for v in VARIANTS:
            for arm in ARMS:
                lab = f"{v}_{arm}_prior"
                oj = os.path.join(out, "disc", f"{lab}.json")
                if not os.path.exists(oj):
                    cmd = py + [os.path.join(SRC, "s06_disc_guard.py"), hdir, os.path.join(syn, lab), LH,
                                os.path.join(syn, "_features"), lab, oj, str(a.nw), a.tex]
                    if a.no_d3 or v == "P":
                        cmd.append("--no-d3")
                    run(cmd, log)
    for v in VARIANTS:
        for arm in ARMS:
            oj = os.path.join(out, "disc", f"{v}_{arm}_prior.json")
            if os.path.exists(oj):
                g0[f"{v}_{arm}_prior"] = json.load(open(oj))["G0_pipeline_only"]
    if 6 in steps:
        res = json.load(open(os.path.join(out, "battery.json")))
        state["decision"] = choose(res, g0)
        state["g0"] = {k: {"pass": v["pass"], "classifiers": v["classifiers"]} for k, v in g0.items()}
        json.dump(state, open(state_p, "w"), indent=1, default=float)
        run(py + [os.path.join(SRC, "s10_report.py"), out, tag], log)
    print("done", tag, flush=True)


if __name__ == "__main__":
    main()
