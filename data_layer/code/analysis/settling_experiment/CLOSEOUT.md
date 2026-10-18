# Settling experiment, round 1: close-out (stopped early by design)

**Stopped:** 2026-10-14 ~14:55 IST. All round-1 processes were terminated.

**Decision:** made by the user and the coordinator.

**Reason:**
- The primary pre-registered rule (§6, PASS if AUC_sim ≤ AUC_tail) became non-informative. The real Tail 687 vs Tail 652 baseline sits at the AUC ceiling (1.000) on engine channels.
- Validation has pivoted to behavioural and causal fidelity, with AUC kept as a diagnostic only. See `../settling_experiment_round2/PREREGISTRATION.md` (commit f6aa660).
- Every round-1 output that round 2 depends on was already complete.

**Status of the pre-registered verdict:** **not issued.** The FULL-model comparisons (sim_T1_L6, sim_T2_L6) were still running when the experiment was stopped. No PASS/FAIL is claimed, and none should be inferred.

## What was completed (results on disk)

| Item | Result | Where |
|---|---|---|
| Splits, manifest | 152 CAL / 229 TEST / 110 Tail 652 flights, seed 20261014 | `results/splits.csv`, `results/manifest.json` |
| **Mechanism check P1–P5** (clock-domain slip, CAL only) | **P1 confirmed:** one Δ (~910 ppm) explains every burst rate. **P4 refuted:** digital channels show no stale or duplicate reads at slips. **P5 confirmed:** the collision window is about constant in absolute time. **P2/P3:** "untestable"/"refuted" under the strict operational tests, "confirmed" under the literal pre-registered wording. | `results/mechanism_decisions.json`, `results/mechanism_summary.json`, `DEVIATIONS.md` §B |
| Texture model fit (CAL; f_c 0.2 / 0.05 / 0.5 Hz) | Parameters for L0–L7 | `results/model_params_*.json`, `results/fit_report_*.json` |
| **Gate 0** (trivial-cue audit), after two pipeline fixes (filter edge padding; float tolerance in the gating rule) | **Pipeline-only metadata:** pass (AUC 0.5; counts, length, dtype, NaN and float32 identical). **Full metadata set:** fails for FULL (LR 0.94, GB 0.99), driven by **double quantisation**. Example: real EGT never uses codes ≡ 1, 4, 7 (mod 8) of its 0.5 °C lattice, which implies a native step of ≈0.8 °C. | `results/gate0.json`, `SMOKE_GATE.md`, `DEVIATIONS.md` §C |
| **Native-step diagnostic** (CAL only) | Native steps and residue patterns per channel, e.g. N1 shows a period-32 pattern with unused codes. Feeds round-2 model M-B. | `results/native_step_cal.json` |
| **Real-vs-real baselines** (flight-level AUC, best classifier) | Tail engine 1.000; tail VRTG 0.998; temporal engine (687 Mar–May vs Jul–Sep) 0.968 [0.931, 0.992]; temporal VRTG 0.868 [0.779, 0.939]. Several classifiers sit lower. | `results/disc/*`, `results/log_disc_decisive_base.txt` |
| **Power check** (L0 straw man, "ideal + Gaussian") | AUC 1.000 for T1 and T2 engine, so the test has power | `results/log_disc_decisive_sim*.txt` |
| **Kaggle reproducibility** | Kaggle (Py 3.13) vs local (Py 3.14) on sim_T1_L1_eng, 40 flights: agree = true; max AUC/CI difference 0.0; per-flight score difference ≤ 3e-13 | `results/log_kaggle.txt` |
| **Cross-channel cohesion** (coordinator analysis) | Slow band matches real, but is inherited by construction. In the fast band, cross-engine correlations are reproduced, but **within-engine coupling is missing**: N1–FF 0.65 real vs 0.04 synthetic. Distance 0.32 vs 0.02–0.05 for real vs real. | `../correlation_check/README.md` |

## What was not completed (dropped)

- **FULL sim-vs-real comparisons** for T1/T2 engine and VRTG. These would have produced the pre-registered verdict.
- **Feature-family ablations, ablation ladder L1–L5 and L6′, f_c sensitivity, July-matched subset.**
  - Kaggle shards a–d and f–h were never pushed.
  - shard_e (VRTG ladder) was pushed and may complete on Kaggle; its output is not used.
- **Window-level permutation tests** for segment-level D2.

None of these would change a decision. Round 2 re-runs discriminator diagnostics, including family ablation, on the new model.

## Lessons carried into round 2

1. **Coupled dynamics belong to the physics model, not the texture layer.** Splitting truth from texture with a frequency cutoff mislabels real engine dynamics as noise.
2. **Rounding is native step plus recorder lattice (double quantisation), not one LSB.**
3. **Missingness and timing are one clock-domain mechanism** (Δ ≈ 910 ppm on this recorder).
4. **Sample-batch-then-verify caught five bugs before any full run:** filter edge padding, gating float tolerance, Kaggle mount path, sample-mode subset size, and a silently COMPLETE status on failure.
5. **Real-vs-real distinguishability can be total** (tail AUC = 1.0). Realism bars must be distances relative to real-vs-real variation, not "indistinguishable".
