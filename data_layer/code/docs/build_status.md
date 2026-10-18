# Build status (tracker)

## Morning summary for the owner (updated 2026-10-15 04:57 IST)

**Wave 1 is complete and independently verified: GO-WITH-CONDITIONS** (`docs/build_gates/E1_verifier_report.md`).
- `make check` is green twice: 2,330 passed.
- The cohesion gates pass with zero skips.
- A closed loop built purely from the published connections runs deterministically. Idle is 67 % N2, inside the
  released band, and fuel leads N2 on a throttle step.

**What the verifier found** (none of it blocks starting Wave 2):
- **One realism decision is not yet demonstrated (MF1).**
  - Requirement: fan–core correlation (N1–N2 0.47) together with positive fuel correlations, under the control
    law we adopted (AD-50).
  - In its study, every setting that lowered N1–N2 flipped the fuel–fan correlation negative. N1–EGT came out ≈ 0
    against a real +0.56.
  - That study had no autothrottle and no recorder texture, both present in the real data.
  - Two tracks are running:
    - a **pre-registered real-data diagnostic** on the calibration flights only: is the low N1–N2 caused by lag,
      by independent fan input, or by quantisation?
    - the **proxy-engine build** with the autothrottle, followed by a reachability study.
  - **The model is not fitted to real data until this is decided.**
- **Cohesion defects nobody had tracked.**
  - A bus-voltage shape mismatch (3 vs 4) would have crashed integration.
  - 18 event types use an encoding the catalogue doesn't describe.
  - Duplicated index maps have no tie test.
  - 5 of 18 cross-module code mutations went undetected by the tests.
  - These are being fixed now, with tests proven to fail on the defects.
- **Restricted values found outside the guarded folders** (an old gate report, the audit log, one test docstring, a
  benchmark comment). **I redacted them immediately.** They are also added to the pre-release history-purge list,
  and the guard now extends to every folder.

**Running now** (four agents, independent scopes):
1. **E1-MF:** cohesion gate hardening, the bus fix, and tests that kill the surviving mutations.
2. **E1-HY:** evidence-tag corrections, honest xfail reasons, stronger weak tests, and the guard extension.
3. **MF1-D:** the real-data diagnostic above (calibration flights only; the reserved archive is untouched).
4. **W2.4a-1:** the proxy engine chain (four engines, autothrottle) and the reachability study. It stops before
   any fitting.

**Next:**
- W2.1 (assembling the full aircraft) starts as soon as E1-MF and E1-HY merge. Its brief now includes the
  verifier's items: the engine trim API, the in-loop sensor path in the fast kernel (≈700 µs/step today against an
  83 µs budget), and the event-encoding migration.
- I decide MF1 from the evidence the two tracks produce, and record it in the architecture.

**Waiting on you:** nothing. The decisions are recorded in "Open decisions" with their evidence.

---


**Owner of this file:** the coordinator (main session). Agents never edit it.

- **Plan:** `docs/build_plan.md` v1.0-draft. Approved by the owner on 2026-10-14 ("start with wave 0").
- **Audit trail:** `docs/build_audit_log.md`. **Agent briefs:** `docs/build_briefs/`.

**States:**

| State | Meaning |
|---|---|
| NOT STARTED | Work has not begun |
| BRIEFED | Brief written, agent not yet launched |
| IN PROGRESS | Agent is working |
| IN REVIEW | Coordinator is reviewing the diff and re-running the checks |
| MERGED | On `main` with `make check` green |
| VERIFIED | Independent verifier re-ran the tests and gates at the wave exit |
| BLOCKED | Waiting on something; the blocker is named |

## Wave 0: contracts and framework

| WP | Title | Owner | Branch | State | Tests (n) | Blockers / notes | Updated (IST) |
|---|---|---|---|---|---|---|---|
| W0.1 | Repo and tooling | coordinator | main | MERGED | 31 passed | — | 2026-10-14 18:44 |
| W0.2 | Core kernel | agent A | wp/w0.2-core | MERGED (67efa3a) | 174 passed (144 core) | A1–A11 PASS; decisions recorded as AD-36/37 | 2026-10-14 19:38 |
| W0.3 | Dictionary (M01) | agent B | wp/w0.3-dictionary | MERGED (a70eeb3) | 511 on main (135 dictionary) | 189 params → 464 channels; dict 0.1.0 (hash e2b446cc…); 39 assumption rows | 2026-10-14 20:33 |
| W0.4 | Contract v0, CIR, storage, replay, fast path | agent C | wp/w0.4-contract | MERGED (96f29e3) | 375 passed on main (201 W0.4) | Contract v0 (0.1.0) is DRAFT; freeze needs owner approval at E0 | 2026-10-14 20:02 |
| W0.5 | Validation harness skeleton (M20) | agent D | wp/w0.5-validation | MERGED (54fd954) | 584 on main; data tests re-run by coordinator: 5 passed | B1–B6 reproduce round 2 (s20 and full 110); exposed W0.3 bnr_lsb defect (fixed 78002d8) | 2026-10-14 20:59 |
| W0.6 | Backend benchmark (AD-22) | agent E | wp/w0.6-benchmark | MERGED | A1 re-verified by coordinator | **AD-22 = Numba** | 2026-10-14 20:33 |
| W0.X | Integration: wire M01 ↔ contract generator ↔ core | coordinator | main | MERGED | 515 on main (4 W0.X) | docs/contract/ published + drift test; real-dictionary fast path → store → replay → leak audit; AD-39 | 2026-10-14 20:38 |
| E0 | Exit gate (verifier) | verifier agent | verify/e0 | **PASSED** (GO-WITH-CONDITIONS; all must-fix items closed) | 584 ×3; data 5/5; 27/28 mutations caught | Report: `docs/build_gates/E0_verifier_report.md`. Must-fix: contract freeze (owner); restricted values in the dictionary (→ 0.1.1); audit hardening (done); dictionary protocol (done). Fix-backs running on W0.2–W0.5 | 2026-10-14 21:36 |

**E0 checklist:**
- [ ] `make check` green on `main`
- [ ] I1, I2, I3 and I8 pass on the toy system
- [x] Contract v0 generated by M01 and frozen (**owner approved**; AD-41; hash 18d7627b…)
- [x] Backend decided (AD-22 → D: Numba)
- [x] W1 briefs written (draft, 4fb3e69)

## Carry-forward into the W1 briefs (from W0 reports)

- **W0.5:**
  - **M13 noise ceiling:** adding independent ±1 LSB noise to *real* flights FAILs B1, B3 (i) and B4, because the fast band is quantisation-dominated. M13 sensor noise must stay at or below the measured idiosyncratic level (AD-05 / round-2 A3). Check every W1.6 noise setting against this.
  - W2.4 produces `FlightRecord`s from the contract (mapping in `src/phalanx/validation/README.md`), uses `select_flights` and `Bootstrap.from_service`, and writes a new pre-registration (alignment rule, G0 sidedness, pinned versions).
  - W2.5 implements `leak_features` (currently a STUB in the validation guards).
  - W3.3 fills in the credibility card.
  - B7, B8 and B9 are not ported yet; they arrive with W2.5 and W3.
  - Map W0.3 unit strings onto `BatteryConfig.units` (proxy mode).
  - Test robustness note: Hypothesis harvests literal constants from collected modules, so the examples tried depend on which test files are collected. The full suite is deterministic; subsets can differ. This is what exposed the `bnr_lsb` bug.
- **W0.2 follow-ups (E0):**
  - Clock-domain modules emit variable sample counts with `core.sampling.sample_ports` / `samples_for_steps` (values, `_t`, `_n`, `_first`), never NaN. Validation mode now rejects NaN/inf at every port.
  - The kernel layout (`core.layout.StateLayout` / `ParamLayout`) has a worked example in `core/example_kernel.py`: compiled = `py_func` reference, bitwise; complex-step safe.
  - Usage mode: `System(event_jump=True)` is automatic for event-only systems; 0.24 s per tail-year.
- **W1.2 numerical pitfalls (for W2 agents):**
  - LLVM fuses `sin`+`cos` into `sincos`, which differs from interpreted code (424/50k arguments on darwin). Use `phalanx.airframe.geodesy.sin_cos`.
  - Compiled `x**2` becomes `x*x`, but interpreted Python calls libm `pow`, which is not correctly rounded on darwin. Write explicit products.
  - `cache=True` does not invalidate callers when a callee in another module changes, and concurrent processes can poison the cache. Delete `__pycache__/*.nbi|*.nbc` after editing shared helpers; fused callers use `cache=False`.
- **W0.6 (AD-22 Numba):**
  - Module kernels are `@njit` pure functions over flat arrays: float64 and int64 state vectors with name→index constants, a flat float64 param vector, tables as NamedTuples. No dicts in kernels.
  - A module's rate group is owned by the scheduler (absolute k). Only sub-rates **inside** a kernel keep a phase counter in the int state (see `core/example_kernel.py`).
  - RNG blocks are fed in as inputs.
  - `prange` over units, with no cross-unit reductions.
  - Calibrated kernels (M07, M08, M09 dynamics, M05 actuators) must be **complex-step safe**: comparisons on the real part, no `abs`/`min` that break complex, etc. Each needs a test of complex step vs central finite differences.
  - Avoid the numba `workqueue` threading layer being entered concurrently.
  - Re-run the W0.6 harness on the real M07/M08 step after W1.
  - x86 bitwise behaviour is unmeasured: run s05/s00 on Kaggle before any cross-platform reproducibility claim.
- **W0.3:**
  - W1 modules build their ParamSets via `d.param_set()` or dictionary `constants`. Engine maps and gains are not seeded yet; each W1 WP adds its tables.
  - FADEC nominal rate is 60 Hz (band 50–67), as a clock domain.
  - Contract `param_id` = `measurand_id`; word index 0-based in the contract (1553/TMATS are 1-based).
  - M15/M16 consume `by_bus_address`, `by_rate_group` and the TMATS generator.
- **W0.4:**
  - W1.6 (M13) emits CIR with `sample_index`, in engineering units, and `rng_key_path` as `KeyPath.canonical()` text.
  - W1.7 follows the full-path `record_id` rules: cumulative packet count; fills `t_bus`, `t_record`, `raw_counts` and the bus fields; same schema as the fast path.
  - M02 owns `scenario_epoch_utc_ns`.
  - W1.5 and W1.8 produce events, counters, records and order status against the contract schemas.
  - M21 uses `ObservationView.as_of` / `.ingested`, which should be indexed in W1.8.
  - Open semantic question for W1.7: what `t_sample` means on the full path (the true acquisition instant vs what a decoder can know).
  - Telemetry I/O budget: fast path + write ≈ 4.3 µs/record. Consider a compiled `record_id` and validating once.
  - Before any dataset release, run the leak audit with that run's seeds and sampled truth values.
- **W0.2:**
  - Non-divisor rates (FADEC 50–67 Hz, AV50…, CDR, ECMS) are **clock domains**, not rate groups (architecture §8).
  - The FCS ↔ airframe ↔ engine ↔ FADEC loop becomes one segment and **needs a fused, compiled `step_block`** (W2.1), or it runs on the slow per-step fallback (~13 µs vs ~1.7 µs/step).
  - Every module declares `StreamDecl`s keyed by the right identity kinds. Example: installation bias keyed by (scenario, serial), so it is constant across sorties.
  - Draw indices are by tick, sample or event number, held in state.
  - **Numerical pitfalls:**
    - `math.tanh` ≠ `np.tanh` (921/5,000 values differ);
    - `np.sum` ≠ sequential addition, while `np.add.accumulate` matches it.

    Reference and compiled kernels must use the same primitives.
  - Numba (fastmath off) was bitwise equal to the Python reference in the probe. JAX x64 was not (22,956/24,000 values differ, max 6e-16), and a length-1 `lax.scan` ≠ longer scans.

## Wave 1: module build

Briefs are drafted (`docs/build_briefs/_w1_common.md`, `W1_interfaces.md`, `W1.*.md`). Agents launch after E0 GO.
W1.0 (the model-parameter registry) is merged in 4fb3e69.

| WP | Title | Owner | Branch | State | Tests (n) | Blockers / notes | Updated (IST) |
|---|---|---|---|---|---|---|---|
| W1.1 | World inputs (M02, M03, M04) | agent | wp/w1.1-world | MERGED (bf6ddd3) | 1927 on main | Usage gates PASS at plan level (2,138 sorties); disturbances incl. fan_face; M02↔M18 ops; 3 strict xfails (W2.1/W2.6); AD-49 | 2026-10-15 01:33 |
| W1.2 | Airframe and FCS (M05, M06) | agent | wp/w1.2-airframe-fcs | MERGED (b497fcb) | 1607 on main | V2 trim, V3 short-period, V4 pass; margins ≥6 dB/35° at 122 points; 3 strict xfails (V7, V9 needs M07, target band); AD-47 | 2026-10-15 01:03 |
| W1.3a | Engine truth model (M07) | agent | wp/w1.3a-engine | MERGED (6a0932d) | 2139 on main | Review → fixes → re-review confirmed; fan_face; MIL 95.2 %; 18 strict xfails (W2.3 calibration + 2 structural PROXY limits) | 2026-10-15 02:39 |
| W1.3b | FADEC and closed-loop governing (M08) | agent | wp/w1.3b-fadec | MERGED (a32b389) | 2330 on main | Review → fixes (AD-50) → re-review → 4 tests; W2.1 entry gates recorded | 2026-10-15 04:00 |
| W1.4 | Utilities (M09) | agent | wp/w1.4-utilities | MERGED (8c14117) | 1482 on main | A1–A5 PASS; 35/35 coupling signs; gauge moved to M12 (AD-42); events declared (AD-44) | 2026-10-15 00:52 |
| W1.5 | Health, faults, BIT (M10, M11, M14) | agent | wp/w1.5-health-faults-bit | MERGED (dab5e34) | 1791 on main | A1–A7 PASS; BIT regimes in band; wired to real M05/M09/M12/M18; AD-48 | 2026-10-15 01:26 |
| W1.6 | Sensors and acquisition (M12, M13) | agent | wp/w1.6-sensors-acquisition | MERGED (60f6236) | 829 on main (119 W1.6) | A1–A8 PASS; noise ceiling holds on real flights; AD-42 recorded | 2026-10-14 23:49 |
| W1.7 | Data path (M15, M16, M17) | agent | wp/w1.7-data-path | MERGED (555cd26) | 1337 on main (415 W1.7) | A1–A8 PASS; full path = fast-path schema; t_sample semantics AD-45; per-sink recordings PROXY (contract 0.2.0 in W2.2) | 2026-10-15 00:36 |
| W1.8 | Operations (M18, M21, M22) | agent | wp/w1.8-operations | MERGED (42cfbcc) | 932 on main | A1–A7 PASS; 2 strict xfails (W2.6 priors); CRN variance ÷2.3; event protocol adopted as AD-44 | 2026-10-15 00:26 |

**E1 gate (2026-10-15 04:57): GO-WITH-CONDITIONS.** Wave 1 is VERIFIED subject to E1-MF, E1-HY and MF1 (see Wave 2). Report: `docs/build_gates/E1_verifier_report.md`.

## Dictionary 0.1.2 batch: **released and merged** (5259eb5). Remaining migrations are W2.1 items:
- M14 → `d.bit_codes()`, M08 → the unified codes via `translate_bit_code`;
- M16 → the dictionary TMATS EV/IDX;
- M15/M17 → the code-word layout;
- M13 → `converter_step` with noise in EU.

### Dictionary 0.1.3 batch (open)
1. ENG.T1 span bottom −54 °C is above the ISA tropopause (−56.5 °C): widen it per evidence, or document the saturation (W1.3b finding).

### Original batch list

1. `mil1553_validity_bit`: a set invalid bit maps to **BUS_INVALID** (AD-45). Check that the W1.7 decoder tests follow it.
2. From W1.7:
   - code-word bit layout into the dictionary (A-W1.7-6);
   - an ICD freshness-counter word (makes DUPLICATE_POLL exact);
   - TMATS `R-1\EV` / `R-1\IDX` attributes generated by M01 (M16 currently overlays them);
   - analog and discrete recorder channels.
3. AD.DPA/DPB range 35–1,500 mbar for a differential pressure: the inventory row says so. This is an evidence check (likely a research-note error).
4. SPS.JFS.SPEED `eu_reference_for: [SPS.JFS.SPEED]` → M09 param `jfs_rated_speed` (60,000 rpm, ASSUMPTION, A-W1.4-26).
6. FADEC lane native steps should reflect the FADEC ADC resolution, not the bus LSB (W1.3b: 0.5 psi PS3 steps make fuel flicker without the filter).
11. `flight_phase` code table: add 8–15 (ENGINE_START, MISSION, DESCENT, PATTERN, TOUCH_AND_GO, SHUTDOWN, GROUND_RUN, HOT_REFUEL; W1.1).
10. **One FADEC/BIT code table** (M14's 102 codes incl. the FADEC set, groups, limit ids, CWS legend/voice map) promoted to the dictionary; M08 and M14 reference it (AD-48 item 5).
9. `fcs_law` code table: add 3 = GROUND (W1.2; M05 already emits it).
7. M10 `health.utility` index map: adopt `phalanx.utilities.layout.HEALTH_INDEX` (23 entries; W1.4 proposal).
5. **Done:** M13 clock-consistency rule + test (W1.6 follow-up, c24c5bb); ENG.WFAB on FTI_DAS.
8. **W2.1 requirement:** a runtime event-protocol validator on the event queue that checks every dispatched cross-module event payload against `w1_events.yaml`. Declarations alone missed the M18 `mx.action` MOD payload having no `pos`.

## Wave 2: integration and calibration

Skeleton milestone at W2.2. AD-33 gate at W2.4b.

| WP | Title | Owner | Branch | State | Tests (n) | Blockers / notes | Updated (IST) |
|---|---|---|---|---|---|---|---|
| E1-MF | E1 must-fix: conformance gate (exact shapes, all 15 ports.py, lane producers, clocks, proxy chain, tracked exceptions), `util.bus_v` (M09 4 buses correct), index-map ties, M07 adapter, M08 property, M14 leak, realised gates, M11 latency, U8 | agent | wp/e1-mf | MERGED (d60f56a) | 2362 on main; cohesion 71, zero skips | Mutants m02/m19/m13/m10/m14d killed. M08 limiter hand-off: 29/192 grid violations pinned as strict xfails → W2.1 entry gate 4 | 2026-10-15 06:33 |
| E1-HY | E1 hygiene: evidence tags, conflicts, xfail numbers, W1.1 A3 PSD, A5/V4 bands, FCS nonlinear margins, CRN F-bound, restricted guard on all folders | agent | wp/e1-hy | MERGED (4aeb756) | 2385 on main | A5 holds at brief bands; V4 strict xfail (W2.3); nonlinear FCS margins hold at 3 points; CRN F-test (n=134/arm); guard on docs/analysis/tests/tools + notes replacement tables; 2 more restricted citations redacted; v_brake_on → 110 kt (released anchor) | 2026-10-15 06:58 |
| MF1-D | CAL-only diagnostic: lag vs independent variance vs texture behind fast-band N1–N2 (pre-registered) | agent | wp/mf1-diag | MERGED (a2030e1) | analysis only; n = 20 / 30 flights | **Phase-dominant**: fan lags core ≈55° (0.19–0.5 Hz), phase share 0.91, texture negligible; N1-specific input 24 %, half common. AD-52 (P) | 2026-10-15 06:33 |
| W2.4a-1 | Proxy chain (separate_fixed, A/T, U3 multi-engine lanes, U4 replay producers), A2 self-test, MF1 joint reachability study | agent | wp/w2.4a-proxy | MERGED (21c7866) | 2447 in its worktree | Fan lag confirmed (N2→N1 −43/−67° vs −46/−72°); joint target not reachable un-identified: plant T5 leads spools; fan_face flow path fails, LP torque path works; A2: staged indirect ID required | 2026-10-15 11:09 |
| W2.1 | Truth-loop integration (W2.1a/b/c) | agents | — | W2.1a/b/c MERGED (W2.1a squash 7e6342b); **A6 OPEN** | 2832 in W2.1a worktree | Take-off passes; sorties fly to ~2,000 s; A6 blockers: idle accel margin (W2.3a), FCS negative-g/AoA limiting (M05) and M04 turn/track blending + energy management (W2.1a-2 continuation) | 2026-10-15 19:20 |
| SC | Solution-context kit | agent | wp/solution-context | RETIRED from git (2026-10-15 14:10) | — | Owner: not needed any more (solution build under way with the Downloads copies). Builder kept: `make solution-context` generates on request (git-ignored); drift test removed so no merge depends on it | 2026-10-15 14:10 |
| W2.4a-2 | Proxy identification on 687-CAL + B1–B6 quick look (staged plan in brief) | agent | wp/w2.4a-proxy | IN PROGRESS | — | MF1 decided (AD-52 D); stages: steady levels → re-reach → gas-path lag (if needed) → bank → staged indirect ID → quick look → W2.4b prereg draft | 2026-10-15 11:09 |
| W2.3a | Engine/FADEC calibration, priority subset (AD-55 item 6) | agent | wp/w2.3a-engine-cal | IN PROGRESS | — | Ground-idle accel margin first; fan lag; EGT; C-points; B7 signature mismatches; usage-mode surrogate | 2026-10-15 17:43 |
| W2.5 | Faults, BIT, label-leak audit (AD-55) | agent | wp/w2.5-faults | MERGED (c13c200); follow-up W2.5b QUEUED | 2788 on main | 11 priority modes validated, 72 unvalidated; B7: LPT erosion PASS, other gas-path cells → W2.3a; progression laws, C25, spall, pump, brakes, tyres PASS; generator code FAIL (no declarer); B8 FA rates PASS, NFF/CND FAIL (no persistent true faults in ops worlds); leak: invariance/metadata PASS, texture/G0 FAIL as pre-registered → AD-59; STUB removed | 2026-10-15 17:43 |
| W2.6 | Operations loop (AD-55) | agent | wp/w2.6-ops | IN PROGRESS | — | Started early in usage mode; M02 requests via coordinator until W2.1 merges | 2026-10-15 13:52 |
| W2.2 | Observation and data path | agent | wp/w2.2-datapath | Phase A + part 1 MERGED; part 2 waits for W2.1 | 2762 (gated tree = main) | Contract 0.2.0 frozen; ENG.AB_LIT; M08 P0 from ADC; BRK/HYD/ECS/fuel-inlet sensors; TAT heater; word path + LRU clocks; coverage reach 162; deferred: af.gear_pos term, RT/bus-status/BIT word producers (part 2) | 2026-10-15 17:09 |

**Open from W1.6 (AD-42):** avionics computed outputs (INGPS/ADC/AHRS/RADAR/SMS) need an owner in W2.2 (proposal: an M12 avionics sensor-system extension). The recorder's placement outside the scheduler needs a snapshot decision in W2.1.

**Sequencing (audit #68):** the gate is split into two steps, to get behavioural evidence earlier.
- **W2.4a (proxy configuration + development quick look)** starts once M03/M07/M08/M12/M13 merge, in parallel with W2.1/W2.2. It needs only the engine-side chain driven by recorded DASHlink inputs.
- **W2.4b (pre-registered archive-2 gate)** runs once, last.

## Wave 3: hardening and delivery

Not started.

## Open decisions and conflicts

| # | Item | Raised by | Status |
|---|---|---|---|
| 3 | Restricted fragments in git history (d1db97d, a8bb3e9) + research-notes annotations | verifier / agent B | **Decided (owner, option a):** no rewrite now; **release-blocking for E3:** purge history and notes annotations before any public release or submission Purge list extended 2026-10-15 04:57: the pre-redaction history of `docs/build_gates/E0_verifier_report.md`, `docs/build_audit_log.md` (entries 105, 109), `tests/integration/test_fadec_limiters.py`, and `analysis/backend_benchmark/code/workload.py` (E1). |
| 6 | VG-rows xfail is a Muir-convention / model-sign question, not calibration (E1 §3) | E1 verifier | **Decided: AD-53** (per-row convention; <1 % = no appreciable deviation; open cells → W2.3) |
| 10 | Owner-approved scope reductions (AD-55): ≥5× real-time floor; FADEC on-board-model check deferred; W2.5 priority fault set (leak audit on all); predictive-vs-reactive demo moved downstream; lighter E2. W2.3 calibration on a priority subset (owner, 2026-10-15 11:53; AD-55 item 6) | owner | **Decided (2026-10-15 11:47)** |
| 9 | Research-notes OCR error: Henry Table 1 T5 given as 971.0/934.3 K in `candidate_engine_and_ehm_data.md`:157 and `addendum_engine_F404_F414_monitoring.md` (~l.82); the page image shows 871.0/834.3 K (C11 uses the correct values) | E1-HY | Recorded here as an erratum; notes are internal evidence and are not rewritten. Anyone citing these lines must use the page values |
| 8 | M05 `servo_wn` now ASSUMPTION (sweep ×0.75–1.25): at ×0.75 the M0.8/SL point fails PM (30.5° < 35°) with the committed gains | E1-HY | **W2.3:** gain schedule must hold margins across the servo sweep, or the sweep is narrowed with evidence |
| 7 | E1 conditions | E1 verifier | MF2, MF3, MF4 **closed** (E1-MF, coordinator); hygiene closed (E1-HY). **MF1 open** (AD-52 P → D after the W2.4a-1 reachability study) |
| 5 | Engine dispersion plan-level 1.13–1.16 vs ≥1.15 (target ≈1.3, RTO-TR-028) | E1 verifier | **Waived for W1 (coordinator, 2026-10-15 04:57):** strict xfail with its number; resolved by W2.6 calibration (tail-affinity / fleet allocation) |
| 4 | **MF1: AD-46 under AD-50** | E1 verifier | **Decided (coordinator, 2026-10-15 11:09): AD-52 → D.** Fan lag primary (confirmed on proxy); secondary LP input = shaft-torque path (AD-46 amended); gas-path timing open (W2.4a-2 stage 3); staged indirect identification |
| 2 | G0 sidedness | agent D | **Closed:** owner chose one-sided (AD-40) |
| 1 | RULES.md lists "AD-01…AD-30" and an "Open items that depend on round 2" section; both are stale against architecture v1.0 | coordinator | **Closed:** amendment approved by the owner and applied |
