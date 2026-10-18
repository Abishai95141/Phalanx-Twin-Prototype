"""Interim verdict on the decisive set (run-order step requested before the remaining analyses).

Applies exactly the section-6 rules of s09_decide.py (same functions) to: power checks (T1-L0, T2-L0 engine,
T1-L0 VRTG), FULL (T1-L6 engine, T2-L6 engine, T1-L6 VRTG) and the baselines tail_* and temporal_*.
Writes results/interim_verdict.json and INTERIM_VERDICT.md (Gate 0 status included).
Usage: python -I s09b_interim.py <results_dir> <experiment_dir>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
import s09_decide as D  # noqa: E402


def f3(v):
    return f"{v:.3f}"


def main(res, exp):
    fams = [("engine_T1", "sim_T1_L6_eng", "sim_T1_L0_eng", "eng"), ("engine_T2", "sim_T2_L6_eng", "sim_T2_L0_eng", "eng"),
            ("VRTG_T1", "sim_T1_L6_vrtg", "sim_T1_L0_vrtg", "vrtg")]
    out = {"note": "interim: decisive set only; same rules and code as s09_decide.py", "families": {}, "singles": {}}
    for n in ["sim_T1_L6_eng", "sim_T2_L6_eng", "sim_T1_L6_vrtg", "sim_T1_L0_eng", "sim_T2_L0_eng", "sim_T1_L0_vrtg",
              "tail_eng", "tail_vrtg", "temporal_eng", "temporal_vrtg"]:
        out["singles"][n] = D.single(res, n, C.stable_int(n) % 10000)
    for fam, full, l0, g in fams:
        power = out["singles"][l0]
        rec = {"power_L0": power and {"auc_x": power["auc_x"], "ci95": power["ci95"]}}
        for base in ("tail", "temporal"):
            prim = D.joint(res, full, f"{base}_{g}", C.stable_int(full + base) % 10000)
            rec[base] = prim
            rec[f"verdict_vs_{base}"] = D.verdict(power, prim)
            rec[f"ceiling_{base}"] = bool(prim and prim["auc_base"] >= 0.999 and prim["auc_base_ci95"][0] >= 0.99)
        out["families"][fam] = rec
    g0s = json.load(open(os.path.join(res, "gate0_smoke.json"))) if os.path.exists(os.path.join(res, "gate0_smoke.json")) else None
    g0 = json.load(open(os.path.join(res, "gate0.json"))) if os.path.exists(os.path.join(res, "gate0.json")) else None
    out["gate0_smoke"] = g0s and {k: {"lr": v["classifiers"]["lr"], "gb": v["classifiers"]["gb"],
                                      "pipeline_only_pass": v["pass_pipeline_only"], "no_gross_cue": v["no_gross_univariate_cue"]}
                                  for k, v in g0s["variants"].items()}
    out["gate0_full"] = g0 and {k: {"lr": v["classifiers"]["lr"], "gb": v["classifiers"]["gb"], "pass": v["pass"],
                                    "pipeline_only_pass": v.get("pipeline_only", {}).get("pass")}
                                for k, v in g0.items() if k in ("T1_L6_primary", "T2_L6_primary", "T1_L6p_primary")}
    with open(os.path.join(res, "interim_verdict.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)
    L = ["# Interim verdict: decisive comparisons",
         "",
         "This file covers only the decisive set. The rules are the pre-registered §6 rules, applied mechanically by the same code as the final run (`src/s09_decide.py`). AUC_x is the maximum over the D2 and D3 classifiers of the flight-level AUC on texture families. All 95 % CIs are flight-level bootstraps (2,000 resamples) that re-take the maximum in every resample.",
         "",
         "| Channel group | Power check: AUC_x(L0) [95 % CI] | AUC_sim (FULL) [95 % CI] | AUC_tail [95 % CI] | Verdict vs tail (primary) | AUC_temporal [95 % CI] | Verdict vs temporal (secondary) |",
         "|---|---|---|---|---|---|---|"]
    for fam, rec in out["families"].items():
        p, t, tm = rec["power_L0"], rec["tail"], rec["temporal"]
        if not (p and t and tm):
            L.append(f"| {fam} | not yet run | | | | | |")
            continue
        cl = " (ceiling: rule cannot fail)" if rec["ceiling_tail"] else ""
        L.append(f"| {fam} | {f3(p['auc_x'])} [{f3(p['ci95'][0])}, {f3(p['ci95'][1])}] | {f3(t['auc_sim'])} [{f3(t['auc_sim_ci95'][0])}, {f3(t['auc_sim_ci95'][1])}] | "
                 f"{f3(t['auc_base'])} [{f3(t['auc_base_ci95'][0])}, {f3(t['auc_base_ci95'][1])}] | **{rec['verdict_vs_tail']}**{cl} | "
                 f"{f3(tm['auc_base'])} [{f3(tm['auc_base_ci95'][0])}, {f3(tm['auc_base_ci95'][1])}] | **{rec['verdict_vs_temporal']}** |")
    with open(os.path.join(exp, "INTERIM_VERDICT.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
