# Phalanx Insights Register

This is a living register of everything learned so far, held in one place for later synthesis.

**How entries work.** Each entry gives:
- the insight;
- its status, which is one of:
  - **Confirmed** (measured or tested);
  - **Evidenced** (published sources);
  - **Decided** (a design decision with a rationale);
  - **Open**;
- a pointer to where the full detail lives.

**Where the detail lives:**
- binding decisions: `docs/architecture.md`;
- rules: `RULES.md`;
- evidence: `reports/Virtual fighter telemetry layer research.md` (**[R§n]**) and `research_notes/`;
- experiments: `analysis/*/`.

**Rule for this file.** Append, don't rewrite. Superseded entries are marked *superseded by #n*.

*Started 2026-10-14; covers the research phase, the DASHlink measurement, settling rounds 1–2 (round 2 in
progress) and the planning discussions.*

---

## A. Platform and problem

| # | Insight | Status | Pointer |
|---|---|---|---|
| A1 | The target is HAL Tejas Mk1A-class with the F404-IN20 modelled as a "composite F404". It is the IAF's own future fleet (220 planned), is the best publicly documented IAF fighter, and shows the problem statement fragmentation directly. | Decided | R§0; AD-01 |
| A2 | Su-30MKI is the strongest *audited* example of the availability problem (55–60 % serviceability vs a 75 % norm), but lacks open technical data. It calibrates the fleet-availability layer, not the physics. | Evidenced | R§0, R§12 |
| A3 | The documented Tejas availability shocks were supply, a starter failing in the cold, a fuel-gauging artefact and a brake-software load, not slow wear. Configuration, supply and engineering-authority events must be in the generator. | Evidenced | R§0, R§18 |
| A4 | No public fighter telemetry exists anywhere, so credibility is capped at NASA-STD-7009B Level 2 against proxy data. | Evidenced | R§6, R§15 |
| A5 | The public record fixes the *structure* of the data almost completely, but almost none of the fighter-specific *numbers*. The defensible product is a realistic Tejas-shaped measurement process with labelled, swept parameters. | Decided | R§18 |

## B. Real data behaviour (measured)

| # | Insight | Status | Pointer |
|---|---|---|---|
| B1 | Recorder data is lattice-valued and frame-aligned. It contains no NaN; lost samples are written as bottom-of-scale sentinels. | Confirmed | `analysis/dashlink_texture/`; R§8 |
| B2 | Periodic dropout bursts and the recorder clock offset are **one mechanism**: clock-domain slip. Burst period = 1/(f·Δ), with Δ ≈ 910 ppm. The 0.8 % gap to the 917.6 ppm clock word reflects recorder-vs-source vs recorder-vs-GMT. | Confirmed (user correction, verified on data) | R§8 correction; round-1 P1/P5 |
| B3 | Slip sentinels hit analog acquisition paths only. Digital channels show no stale reads at slips. | Confirmed | Round-1 CLOSEOUT (P4 refuted) |
| B4 | The collision window is about constant in absolute time (≈10–20 ms), consistent with a fixed conversion interval. | Confirmed | Round-1 P5 |
| B5 | **Double quantisation.** EGT never uses residues 1, 4 and 7 mod 8 of its 0.5 °C lattice, which implies a native step of 0.8 °C. N1/N2 have a native step of 0.04 %. FF uses a single 8 lb/h lattice. | Confirmed | Gate-0 smoke; `native_step_cal.json` |
| B6 | Fast fluctuations up to about 0.5 Hz are mostly **coupled engine dynamics**, not sensor noise. Within-engine fast correlations in real data: N1–FF 0.65, N1–EGT 0.56, N1–N2 0.43. | Confirmed | `analysis/correlation_check/` |
| B7 | In recorded data, N2 leads measured FF by about 0.5 s, then N1, then EGT. ~~This points to fuel-flow meter dynamics, i.e. sensor physics.~~ *Superseded by C12.* | Confirmed (CAL); fix ⟂R2 | Round-2 QUICK_LOOK; amendment A6 |
| B8 | Corrected-parameter collapse is imperfect. FF scatter falls from 22 % to 2 %, and the EGT exponent is 0.5–0.7, not 1. | Confirmed | R§3 |
| B9 | Real-vs-real distinguishability can be total. Tail 687 vs 652 engine AUC = 1.000; the same tail across seasons gives 0.968 (engine) and 0.868 (VRTG). | Confirmed | Round-1 CLOSEOUT |
| B10 | Per-engine persistent offsets drift over time, and oil-pressure offsets step. Unit-to-unit spread is real and structured. | Confirmed | R§8 |

## C. Modelling and validation lessons

| # | Insight | Status | Pointer |
|---|---|---|---|
| C1 | **Physics carries coupling; texture carries only sensor-independent effects.** Splitting truth from texture with a frequency cutoff mislabels real dynamics as noise. | Decided (AD-04) | E5/E6 in `docs/architecture.md` §18 |
| C2 | A physics-structured engine chain restores much of the coupling. Quick look: N1–FF 0.55 (real 0.62, round 1 0.05). Out-of-sample R²: FF 0.98, N2 0.97, N1 0.99, EGT 0.91. | Confirmed (CAL dev) | Round-2 QUICK_LOOK |
| C3 | Unit variation must sit in component health and sensor installation bias, not in output offsets. Output offsets distort the corrected-parameter laws (B5 0.093 vs 0.049). | Decided (AD-07); values ⟂R2 | Amendment A7 |
| C4 | An explicit sensor-dynamics stage belongs between truth and texture: FF meter lag, thermocouple τ ∝ W⁻⁰·⁵. | Decided (AD-23); values ⟂R2 | Amendment A6 |
| C5 | Development numbers (20-flight sample, quick fits) give fast-band distance 0.173 (physics), 0.154 (+ coupled correction) and 0.297 (round 1), against 0.053 real-vs-real. A gap remains, and the lead–lag order is not yet fixed. | Open ⟂R2 | `dev_battery_sample20.json` |
| C6 | **"Distinguishable" is not "unusable".** Even two real aircraft are perfectly separable. The realism question is fitness for purpose: behaviour, causal structure, and whether downstream methods rank and transfer the same. | Decided (AD-21, AD-30) | `docs/architecture.md` §14 |
| C7 | Discriminators locate differences but must not decide pass or fail. The primary rule "AUC_sim ≤ AUC_tail" can be non-informative when the tail baseline sits at the ceiling. | Confirmed | Round-1 CLOSEOUT |
| C8 | In round 1 the slow-band behaviour was inherited from the real signal and could not fail. Causal structure can only be tested when a model *generates* the outputs, hence model-in-the-loop round 2 and proxy mode in the build. | Decided | Round-2 prereg §1 |
| C9 | Sensor bias and component deterioration are observationally confounded (TM-4551), so they must be separate latent truths. | Evidenced, decided (AD-26) | R§2 |
| C10 | Shortcut-learning protection is the label-leak audit: healthy and faulty data must come from the identical generation path. | Decided | RULES.md §4; architecture §14 |
| C12 | The N2-leads-FF inversion is **not** explained by meter lag. The fitted FF τ is only ≈0.23 s, and the inversion persists with the sensor stage. It vanishes only with the coupled discrepancy layer. Most likely cause: **closed-loop governing**, where the controller corrects disturbances, so speed moves before fuel. The engine (M07) and FADEC (M08) must run in closed loop for B2. | Dev evidence; ⟂R2 | Round-2 agent report 16:45; AD-31 |
| C13 | **Round 2 verdict: REWORK.** On Tail 652, every arm went 0/6 on B1–B6 against real-vs-real bars; G0 passed. A deterministic, open-loop, input-driven engine model plus texture is not enough. | Confirmed (pre-registered) | `analysis/settling_experiment_round2/REPORT.md` |
| C14 | Deterministic physics driven by shared inputs **over-couples** engines and spools: fast-band EGT_1–EGT_2 0.99 vs 0.59 real; N1–N2 0.92 vs 0.47. Real engines need **per-unit process disturbances** entering the dynamics. | Confirmed → AD-32 | REPORT §3.1 |
| C15 | The lead–lag inversion is closed-loop. Meter lag fits only 0.22 s, and the inversion persists open-loop. Post hoc: A/T engaged −0.375 s vs manual 0.0 s over 82 flights. | Confirmed (post hoc part labelled) → AD-31 gate | REPORT §3.2 |
| C16 | A level-dominated output-error fit under-identifies dynamics. Decel τ FF is 0.25 s vs 1.58 s real; several τ sit at bounds. Dynamics need transient-weighted identification. | Confirmed → AD-34 | REPORT §3.3 |
| C17 | The coupled statistical discrepancy layer (M-C) helps (B1 −37 %, B2 −45 %, B4 −54 %) but is insufficient, and it decorrelates engines too far. Statistical patches can't replace missing mechanisms. | Confirmed → AD-29 PROXY fallback only | REPORT §2 |
| C18 | The texture form is settled: double quantiser exact (G1 0.01–0.02); independent noise at or below quantiser variance. | Confirmed | REPORT §3.5 |
| C19 | The CAL development battery (51-flight fold) predicted the holdout outcome closely. Development diagnostics on calibration folds are a cheap early warning, and cross-tail transfer was not the cause of failure. | Confirmed | REPORT §5 |
| C11 | Faults are best expressed as deviations from each aircraft's own healthy baseline. One sim-to-real study saw real-flight accuracy rise from 52.9 % to 85.5 %. | Evidenced | R§9 |

## D. Claims framing (DSSC)

| # | Insight | Status |
|---|---|---|
| D1 | **Can claim:** the architecture integrates fragmented data (telemetry, BIT, records, spares, agencies), which is the core of the problem statement. Predictive policies can beat reactive practice by margins that hold across plausible assumptions, shown with ground truth plus forks. The pipeline ingests real data unchanged. Credibility: Level 2 against proxy data. | Decided |
| D2 | **Shouldn't claim:** absolute accuracy on real Tejas/IAF failures, or "indistinguishable from real aircraft data". | Decided |
| D3 | Fit-for-purpose criteria sit next to realism: method ranking agreement (e.g. Kendall τ ≥ 0.7), a TSTR/TRTR threshold, no shortcut features, and robustness of conclusions under sensitivity sweeps. | Decided (B9 in battery) |
| D4 | The strongest message to DSSC/IAF: the same pipeline that trains on synthetic data ingests their data on the day they share it, through the same contract. | Decided |

## E. Compute and infrastructure

| # | Insight | Status | Pointer |
|---|---|---|---|
| E1 | The data layer is CPU-bound by nature: small-state time stepping, event logic, byte encoding and I/O. GPUs don't help. Speed comes from parallelism across tails, sorties and forks, plus compiled hot loops. | Decided (AD-22) | architecture §13 |
| E2 | JAX helps with gradient-based calibration (autodiff), batched forks (`vmap`) and functional state (snapshots). It doesn't help event logic or I/O, and CPU/GPU float differences complicate golden tests. Numba vs JAX is decided by a phase-1 benchmark. | Open ⟂B | architecture §13 |
| E3 | Per-sortie cost target with a compiled core: about 1–2 CPU-min per sortie-hour including encoding. Uncompiled physics is 3–5× slower. | Estimate (benchmark to confirm) | — |
| E4 | **Two-tier fidelity** (usage mode for fleet-years, telemetry mode for selected sorties) cuts fleet generation about 10×, e.g. ≈300 → ≈30 CPU-h. | Decided (AD-10) | architecture §13 |
| E5 | Compute is not the bottleneck; development and review are. A compressed multi-agent build needs about 20–40 machine-hours. At a human pace (6 weeks) it was about 75 h. | Estimate | — |
| E6 | Kaggle: CPU kernels have 4 cores and Python 3.13; the pinned stack installs. Datasets mount at `/kaggle/input/datasets/<owner>/<slug>/`. Wrappers must fail loudly, because Kaggle reported a failed run as COMPLETE. Results reproduce local exactly (≤3e-13). | Confirmed | `analysis/settling_experiment/results/log_kaggle.txt` |
| E7 | **TPU is not available through the Kaggle CLI** on this account. `enable_tpu`, `Tpu1VmV38` and `TpuV5E8` all ran on the 4-CPU default with 0 TPU hours used. Kaggle helps by running batches in parallel, not through faster machines (4 cores vs 10 locally). | Confirmed | log_kaggle; this register |
| E8 | **Agents' Kaggle uploads and pushes are blocked by the auto-mode safety classifier** ("data exfiltration"), even with a project allow rule. The workable pattern: agents stage folders and write commands to `kaggle_pending_cmds.txt`; the coordinating session reviews and runs them. | Confirmed (process) | RULES.md §8 |
| E10 | Engine-model calibration is dominated by finite-difference Jacobians: about 34 simulations per iteration over 9–13.5 M samples, 44 min per stage on a 3-fold CV. Autodiff (JAX) or forward sensitivities would cut this about 30×. This is concrete input to the AD-22 benchmark. | Confirmed | Round-2 agent report |
| E11 | Memory, not cores, limited parallel fitting. Four fits at about 5 GB each on a 16 GB machine thrashed swap. Rules: cap concurrency by RAM; preallocate Jacobians; write outputs only at loss samples. | Confirmed | Round-2 DEVIATIONS |
| E9 | The NASA DASHlink server has been unreachable since 14 Oct 13:39 IST. Holdout plans need a pre-registered fallback; Tail 652 was used. | Confirmed | `research_sources/.../raw2/fetch.log` |

## F. Process lessons

| # | Insight | Status |
|---|---|---|
| F1 | **Sample → verify → scale** caught 7 bugs before any full run: filter edge padding, gating float tolerance, Kaggle mount path, sample-mode subset size, silent COMPLETE, a NaN in parameter bounds, and the corrected-vs-physical FF unit mix. About an hour was wasted in round 1 before the rule existed. | Confirmed; now a rule (RULES.md §1) |
| F2 | Use the minimal sufficient sample for every check. Most questions are answered by 1–20 flights. Discriminator permutation tests are the dominant compute cost, so trim them except at milestones. | Decided (RULES.md §1) |
| F3 | Pre-register, then amend only through a timestamped log before any holdout data is read. The design can still change mid-way while staying honest (round-2 A1–A8). | Confirmed practice |
| F4 | Stop experiments whose remaining outputs can't change a decision, and close them out explicitly: no verdict claimed, lessons recorded. Round 1 was stopped this way. | Confirmed practice |
| F5 | Agent-written analysis must be spot-checked by the coordinator against the raw files. Example: the user's own clock-slip check corrected a misreading in the report. | Confirmed practice |
| F6 | The real build doesn't wait for experiments. Only M13's internals and M07's acceptance details depend on round 2; everything else is green. | Decided |
| F7 | A multi-agent build realistically takes about 1 day for an end-to-end skeleton and about 2–3 days for a full v1. The limiters are contracts-first (serial), integration, calibration loops and review bandwidth, not compute. | Estimate (build plan) |

| F8 | Keep the pristine holdout for the model that can still pass. After a primary REWORK, the archive-2 confirmatory run was paused (user-confirmed) and archive 2 reserved as the build's proxy-mode gate (AD-33). | Decided |
| F9 | Subagents can't write report files ("return findings as text"). The coordinator saves the report verbatim from the hand-back and credits the author in the commit. | Confirmed practice |
| F10 | After REWORK, the user chose **Option B**: fold the rework into the build (no round 3), with the proxy-mode gate as the acceptance test. | Decided |

## G. Open questions (tracked)

| # | Question | Resolved by |
|---|---|---|
| G1 | ~~Does physics + sensor dynamics meet the B1/B2 bars…?~~ **Answered: no (C13–C17).** New question: do closed-loop control + per-unit process disturbances (AD-31/32) pass B1–B6? | Build proxy-mode gate on archive 2 (AD-33) |
| G2 | Are Numba or JAX the physics backend? | Phase-1 benchmark |
| G3 | Fault and event behaviour fidelity (B7/B8), and downstream fitness (B9). | Build: Tejas fault library; NGAFID/RflyMAD proxies |
| G4 | ~~Tail 687 archive 2 confirmation~~. Downloaded 16:55; **reserved, unread**, as the AD-33 gate. | Build |
| G5 | Real Tejas parameters (ICD, CDR list, ECMS/LUI gates, IN20 limits, IAF records). | DSSC/IAF/HAL requests (architecture §19) |
