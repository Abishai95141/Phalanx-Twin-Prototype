"""Step 9 -- apply the pre-registered decision rules (section 6) mechanically.

AUC_x = max over the D2 (texture families) and D3 (residual windows) classifiers of the flight-level AUC.
Bootstrap of AUC_x re-takes the max in every resample (selection included).
Joint bootstrap for AUC_sim - AUC_baseline: 687-TEST flights are resampled once and shared by the simulation
comparison (pairs) and the baseline's 687 class; 652 (or the late group) is resampled independently.
  power check : lower 95 % bound (2.5th percentile) of AUC_x(L0) > 0.6, else INCONCLUSIVE (no power)
  PASS        : AUC_sim <= AUC_tail (point estimates)
  FAIL        : one-sided 95 % lower bound (5th percentile) of AUC_sim - AUC_tail > 0
  otherwise   : INCONCLUSIVE
Usage: python -I s09_decide.py <results_dir>
Writes results/verdicts.json, results/auc_table.csv, results/decision_table.md
"""
import csv
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
import learn as LN  # noqa: E402

B = 2000


def primary_keys(js):
    return [k for k in js["classifiers"] if (k.startswith("D2_") and k.endswith("_tex")) or
            (k.startswith("D3_") and k.endswith("_res"))]


def load(res, name):
    p = os.path.join(res, "disc", name + ".json")
    if not os.path.exists(p):
        return None
    js = json.load(open(p))
    z = np.load(os.path.join(res, "disc", name + ".npz"), allow_pickle=False)
    return js, z


def flight_keys(z):
    """List of (687 file or None, other id) per row: TEST file identity for joint resampling."""
    out = []
    for s in z["flights"]:
        label, f = str(s).split("/")
        out.append((label, f))
    return out


def auc_x(y, S, idx=None):
    vals = []
    for s in S:
        yy, ss = (y, s) if idx is None else (y[idx], s[idx])
        m = np.isfinite(ss)
        if len(np.unique(yy[m])) < 2:
            continue
        vals.append(LN.fast_auc(yy[m], ss[m])[0])
    return max(vals) if vals else np.nan


def joint(res, sim_name, base_name, seed):
    a = load(res, sim_name)
    b = load(res, base_name)
    if a is None or b is None:
        return None
    ja, za = a
    jb, zb = b
    ka, kb = primary_keys(ja), primary_keys(jb)
    ya, yb = za["y"], zb["y"]
    Sa = [za[k] for k in ka]
    Sb = [zb[k] for k in kb]
    fa, fb = flight_keys(za), flight_keys(zb)
    pa = za["pair"]
    # sim: pairs indexed by TEST file
    test_files = sorted(set(f for (lab, f), yy in zip(fa, ya) if yy == 0))
    rows_by_file_a = {}
    for i, (lab, f) in enumerate(fa):
        rows_by_file_a.setdefault(f, []).append(i)
    # baseline: class-0 rows that are 687-TEST flights; class-1 rows resampled independently
    base0 = {}
    base1 = []
    for i, ((lab, f), yy) in enumerate(zip(fb, yb)):
        if yy == 0:
            base0.setdefault(f, []).append(i)
        else:
            base1.append(i)
    base1 = np.array(base1)
    rows_by_file_b = {}
    for i, (lab, f) in enumerate(fb):
        rows_by_file_b.setdefault(f, []).append(i)
    shared = all(f in rows_by_file_a for f in base0)       # baseline class 0 drawn from the same TEST pool
    rng = np.random.default_rng(seed)
    obs_a, obs_b = auc_x(ya, Sa), auc_x(yb, Sb)
    diffs, ba, bb = [], [], []
    tf = np.array(test_files)
    b0_files = np.array(sorted(base0))
    for _ in range(B):
        draw = rng.choice(tf, tf.size, replace=True)
        ia = np.concatenate([rows_by_file_a[f] for f in draw])
        if jb["kind"] == "sim":
            ib = np.concatenate([rows_by_file_b[f] for f in draw if f in rows_by_file_b])
            xa, xb = auc_x(ya, Sa, ia), auc_x(yb, Sb, ib)
            ba.append(xa)
            bb.append(xb)
            diffs.append(xa - xb)
            continue
        if shared and jb["kind"] in ("tail", "tailjul"):
            d0 = [f for f in draw if f in base0]
            if len(d0) < 5:
                continue
            i0 = np.concatenate([base0[f] for f in d0])
        else:
            d0 = rng.choice(b0_files, b0_files.size, replace=True)
            i0 = np.concatenate([base0[f] for f in d0])
        i1 = rng.choice(base1, base1.size, replace=True)
        ib = np.r_[i0, i1]
        xa, xb = auc_x(ya, Sa, ia), auc_x(yb, Sb, ib)
        ba.append(xa)
        bb.append(xb)
        diffs.append(xa - xb)
    diffs = np.array(diffs)
    return {"sim": sim_name, "baseline": base_name, "auc_sim": obs_a, "auc_base": obs_b, "diff": obs_a - obs_b,
            "diff_lower95_one_sided": float(np.percentile(diffs, 5)), "diff_ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
            "auc_sim_ci95": [float(np.percentile(ba, 2.5)), float(np.percentile(ba, 97.5))],
            "auc_base_ci95": [float(np.percentile(bb, 2.5)), float(np.percentile(bb, 97.5))],
            "n_boot": int(diffs.size), "joint_resampling_of_shared_687_test": bool(shared and jb["kind"] in ("tail", "tailjul"))}


def single(res, name, seed):
    a = load(res, name)
    if a is None:
        return None
    js, z = a
    ks = primary_keys(js)
    y = z["y"]
    S = [z[k] for k in ks]
    pid = z["pair"] if (z["pair"] >= 0).all() else None
    idx = LN.boot_indices(y, pid, B, seed)
    bs = np.array([auc_x(y, S, ix) for ix in idx])
    best = max(ks, key=lambda k: js["classifiers"][k]["auc"])
    return {"name": name, "auc_x": auc_x(y, S), "ci95": [float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))],
            "best_classifier": best, "n_flights_class": js["n_flights_class"],
            "per_classifier": {k: {kk: js["classifiers"][k].get(kk) for kk in ("auc", "ci95", "p_perm", "n_perm")}
                               for k in js["classifiers"]}}


class WinIndex:
    """Window-level scores of the window classifiers of one comparison (exploratory, post hoc)."""

    def __init__(self, js, z):
        self.keys = [k for k in primary_keys(js) if "_seg_" not in k and (k + "__win") in z.files]
        self.y = z["y"]
        self.S, self.rows = {}, {}
        for k in self.keys:
            w, rf = z[k + "__win"].astype(float), z[k + "__rf"]
            self.S[k] = (w, rf)
            ro = {}
            for i, f in enumerate(rf):
                ro.setdefault(int(f), []).append(i)
            self.rows[k] = {f: np.array(v) for f, v in ro.items()}

    def auc_x(self, idx=None):
        vals = []
        for k in self.keys:
            w, rf = self.S[k]
            if idx is None:
                r = np.arange(w.size)
            else:
                rr = [self.rows[k][f] for f in idx if f in self.rows[k]]
                if not rr:
                    continue
                r = np.concatenate(rr)
            yy = self.y[rf[r]]
            if len(np.unique(yy)) < 2:
                continue
            vals.append(LN.fast_auc(yy, w[r])[0])
        return max(vals) if vals else np.nan


def joint_window(res, sim_name, base_name, seed, nboot=500):
    """Post-hoc, unsaturated companion of joint(): the same rule at window level (64-s and 300-s windows)."""
    a, b = load(res, sim_name), load(res, base_name)
    if a is None or b is None:
        return None
    Wa, Wb = WinIndex(*a), WinIndex(*b)
    fa, fb = flight_keys(a[1]), flight_keys(b[1])
    ya, yb = a[1]["y"], b[1]["y"]
    rows_a = {}
    for i, (lab, f) in enumerate(fa):
        rows_a.setdefault(f, []).append(i)
    base0, base1, rows_b = {}, [], {}
    for i, ((lab, f), yy) in enumerate(zip(fb, yb)):
        rows_b.setdefault(f, []).append(i)
        if yy == 0:
            base0.setdefault(f, []).append(i)
        else:
            base1.append(i)
    base1 = np.array(base1)
    tf = np.array(sorted(set(f for (lab, f), yy in zip(fa, ya) if yy == 0)))
    rng = np.random.default_rng(seed)
    d, xa_l, xb_l = [], [], []
    for _ in range(nboot):
        draw = rng.choice(tf, tf.size, replace=True)
        ia = np.concatenate([rows_a[f] for f in draw])
        if b[0]["kind"] == "sim":
            ib = np.concatenate([rows_b[f] for f in draw if f in rows_b])
        else:
            d0 = [f for f in draw if f in base0] if b[0]["kind"] in ("tail", "tailjul") else \
                list(rng.choice(np.array(sorted(base0)), len(base0), replace=True))
            if len(d0) < 5:
                continue
            ib = np.r_[np.concatenate([base0[f] for f in d0]), rng.choice(base1, base1.size, replace=True)]
        xa, xb = Wa.auc_x(ia), Wb.auc_x(ib)
        xa_l.append(xa)
        xb_l.append(xb)
        d.append(xa - xb)
    d = np.array(d)
    oa, ob = Wa.auc_x(), Wb.auc_x()
    return {"auc_sim_window": oa, "auc_base_window": ob, "diff": oa - ob,
            "diff_lower95_one_sided": float(np.percentile(d, 5)), "diff_ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
            "auc_sim_ci95": [float(np.percentile(xa_l, 2.5)), float(np.percentile(xa_l, 97.5))],
            "auc_base_ci95": [float(np.percentile(xb_l, 2.5)), float(np.percentile(xb_l, 97.5))], "n_boot": int(d.size),
            "classifiers": Wa.keys}


def verdict(power, prim):
    if power is None or prim is None:
        return "NOT RUN"
    if not power["ci95"][0] > 0.6:
        return "INCONCLUSIVE (no power)"
    if prim["auc_sim"] <= prim["auc_base"]:
        return "PASS"
    if prim["diff_lower95_one_sided"] > 0:
        return "FAIL"
    return "INCONCLUSIVE"


def main(res):
    names = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(res, "disc", "*.json")))
    singles = {n: single(res, n, C.stable_int(n) % 10000) for n in names}
    rows = []
    for n, s in singles.items():
        if s is None:
            continue
        rows.append({"comparison": n, "auc_x": f"{s['auc_x']:.3f}", "ci_lo": f"{s['ci95'][0]:.3f}", "ci_hi": f"{s['ci95'][1]:.3f}",
                     "best": s["best_classifier"], "n_per_class": "/".join(map(str, s["n_flights_class"])),
                     **{k: f"{v['auc']:.3f}" for k, v in s["per_classifier"].items()}})
    keys = sorted(set().union(*[r.keys() for r in rows]), key=lambda k: (k not in ("comparison", "auc_x", "ci_lo", "ci_hi", "best", "n_per_class"), k))
    with open(os.path.join(res, "auc_table.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    out = {"singles": singles, "verdicts": {}, "sensitivity": {}}
    fams = [("engine_T1", "sim_T1_L6_eng", "sim_T1_L0_eng", "eng"), ("engine_T2", "sim_T2_L6_eng", "sim_T2_L0_eng", "eng"),
            ("VRTG_T1", "sim_T1_L6_vrtg", "sim_T1_L0_vrtg", "vrtg")]
    for fk in C.FC:
        sfx = "" if fk == "primary" else f"_{fk}"
        for fam, full, l0, g in fams:
            full_n, l0_n = full + sfx, l0 + sfx
            power = singles.get(l0_n)
            rec = {"full": full_n, "power_L0": power and {"auc_x": power["auc_x"], "ci95": power["ci95"]}}
            l0w = joint_window(res, l0_n, f"tail_{g}{sfx}", 5) if fk == "primary" else None
            if l0w:
                rec["posthoc_window_power_L0"] = {"auc_x": l0w["auc_sim_window"], "ci95": l0w["auc_sim_ci95"]}
            for base in ("tail", "temporal", "tailjul"):
                if base == "tailjul" and fk != "primary":
                    continue
                prim = joint(res, full_n, f"{base}_{g}{sfx}", C.stable_int(full_n + base) % 10000)
                rec[base] = prim
                rec[f"verdict_vs_{base}"] = verdict(power, prim)
                if fk == "primary" and base != "tailjul":
                    pw = joint_window(res, full_n, f"{base}_{g}{sfx}", C.stable_int(full_n + base + "w") % 10000)
                    rec[f"posthoc_window_{base}"] = pw
                    if pw and l0w:
                        rec[f"posthoc_window_verdict_vs_{base}"] = verdict(
                            {"ci95": l0w["auc_sim_ci95"]}, {"auc_sim": pw["auc_sim_window"], "auc_base": pw["auc_base_window"],
                                                            "diff_lower95_one_sided": pw["diff_lower95_one_sided"]})
            (out["verdicts"] if fk == "primary" else out["sensitivity"]).setdefault(fk, {})[fam] = rec
    # L6 vs L6'
    out["L6_vs_L6p"] = {}
    for g, arm in (("eng", "T1"), ("eng", "T2"), ("vrtg", "T1")):
        j = joint(res, f"sim_{arm}_L6_{g}", f"sim_{arm}_L6p_{g}", 77)
        out["L6_vs_L6p"][f"{arm}_{g}"] = j
    with open(os.path.join(res, "verdicts.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)
    lines = ["| Family | Power check: AUC_x(L0) [95% CI] | AUC_sim (FULL) [95% CI] | AUC_tail [95% CI] | diff, one-sided 95% LB | Verdict vs tail (primary) | AUC_temporal [95% CI] | Verdict vs temporal (secondary) |",
             "|---|---|---|---|---|---|---|---|"]
    for fam, rec in out["verdicts"]["primary"].items():
        p = rec["power_L0"]
        t, tm = rec.get("tail"), rec.get("temporal")
        f2 = lambda v: f"{v:.3f}"  # noqa: E731
        lines.append(f"| {fam} | {f2(p['auc_x'])} [{f2(p['ci95'][0])}, {f2(p['ci95'][1])}] | "
                     f"{f2(t['auc_sim'])} [{f2(t['auc_sim_ci95'][0])}, {f2(t['auc_sim_ci95'][1])}] | "
                     f"{f2(t['auc_base'])} [{f2(t['auc_base_ci95'][0])}, {f2(t['auc_base_ci95'][1])}] | "
                     f"{f2(t['diff'])}, {f2(t['diff_lower95_one_sided'])} | **{rec['verdict_vs_tail']}** | "
                     f"{f2(tm['auc_base'])} [{f2(tm['auc_base_ci95'][0])}, {f2(tm['auc_base_ci95'][1])}] | {rec['verdict_vs_temporal']} |")
    with open(os.path.join(res, "decision_table.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    for fk, d in out["sensitivity"].items():
        for fam, rec in d.items():
            print(fk, fam, rec["verdict_vs_tail"], rec["verdict_vs_temporal"],
                  {b: (round(rec[b]["auc_sim"], 3), round(rec[b]["auc_base"], 3)) for b in ("tail", "temporal") if rec.get(b)})
    print("L6 vs L6'", {k: (v and (round(v['auc_sim'], 3), round(v['auc_base'], 3), round(v['diff_ci95'][0], 3), round(v['diff_ci95'][1], 3))) for k, v in out["L6_vs_L6p"].items()})


if __name__ == "__main__":
    main(sys.argv[1])
