# E1 verifier report: Wave 1 exit gate

- **Verified:** main 8039d2b (branch `verify/e1`), 2026-10-15.
- **Verifier:** an independent agent; brief `docs/build_briefs/E1_verifier.md`.
- **Scratch:** git-ignored `runs/e1/` (probes, mutation copies, logs).
- **Archive 2:** never touched.

The coordinator's disposition is at the end.

## Verdict: **GO-WITH-CONDITIONS**

W1 meets the formal E1 definition:
- `make check` is green twice.
- Both cohesion gates pass with zero skips.
- The only STUB left is tracked.
- Every `assumption_id` resolves.
- A closed loop built purely from the `ports.py` bindings runs, is deterministic, and behaves sensibly: idle is in the released band, and Wf leads N2 on a PLA step.

It is not a plain GO for two reasons:
- The verifier found cohesion defects and test gaps that were not tracked.
- The central realism decision AD-46 has not been demonstrated under the control law that AD-50 adopted.

None of this blocks starting W2.1. The short must-fix list (§9) closes first. **W2.4a must not start identification until MF1 is resolved.**

---

## 1. E1 checklist

Commands ran with `.venv-build/bin/python -I`. `make check` ran under `set -o pipefail`.

| E1 item | Result | Evidence |
|---|---|---|
| `make check` green twice | PASS | Run 1: `2330 passed, 2 skipped, 20 deselected, 26 xfailed in 490.56s`, exit 0. Run 2: same counts in 506.60 s, exit 0 |
| Zero skips in conformance and event protocol | PASS | `pytest -q -rs tests/integration/test_interface_conformance.py tests/integration/test_event_protocol.py` → `64 passed in 5.54s` |
| The 2 suite skips | Tracked | `test_engine_golden.py:287` (C7/C9/C12/C13) and `:586` (C25/C27/C28) → W2.1. The reason text at `:586` is stale: W1.4–W1.6 are done |
| Static audit R1–R8 | PASS | `audit_static: 245 files, 0 errors, 1 notes`. The note is the `validation/guards/label_leak.py:113` STUB (W2.5). No `# audit: allow` lines |
| No STUB except tracked | PASS | Only `label_leak.py:113` (W2.5). `src/` imports no test fixtures |
| `docs/assumptions.md` lists every PROXY | PASS, minor gaps (§7) | 15 code PROXY markers resolve. 196/196 `assumption_id`s across 1,075 parameter entries exist |
| Every module conforms to its interface | PASS for gated scope; **1 defect outside it** | Probe over all 15 `ports.py` at n_engines 1/2/4 with exact shapes: M09 publishes `util.bus_v` as (4,), M12 binds (3,). The gate checks rank only |
| W1 acceptance tests pass | PASS | W1.1 119p/3xf; W1.2 113p/3xf; W1.3a 206p/18xf/2s; W1.3b 119p; W1.4 137p; W1.5 175p; W1.6 123p; W1.7 400p; W1.8 147p/2xf. Slow and data tests: noise ceiling on real flights (n=20+20), public Ch10 5/5, A9 performance, lead–lag table, PLA duty, label-leak null |

## 2. Acceptance coverage: does each test actually fail when it should?

| WP | Strong | Weak, or cannot fail |
|---|---|---|
| W1.1 | A4 CRN; A7 bitwise; USSA layer bases; V11 tracking (mutant killed) | **A3 PSD is circular**: targets come from the kernel's own discretised matrices, and a 2×τ mutant failed only hand-set thresholds, by a hair. A5 bands are wider than the brief (AB 3.5–5.5 vs 4–5; ≥IRP 15–22 % vs 17–20 %). PLA-duty coverage is slow-only, n=3 |
| W1.2 | A1 NESC-style cases vs DOP853; A4 voting and false-WoW (mutant killed); A5 √ΔP law; A6 | **V4** tolerance is 0.18–0.32 s against the brief's 0.2–0.3 s (hides points at 0.301 and 0.194 s). **A3** margins come only from the linear design model |
| W1.3a | A1–A3; A4 fuel signs; engine-1-to-engine-2 independence (bitwise); A7 | **A6/AD-46 runs under a direct-Wf fixture governor that AD-50 rejects** (MF1). Muir rows check sign only. AB light-off timing is circular |
| W1.3b | A1 limiters (MIN→MAX mutant failed ≥15 tests); A2 sign plus FF correlation; A4 hung start; A6 | **A1 property test has a real counterexample**: at PLA 89°, 220 K, 91.9 kPa, M0.5, PS3 transient reaches 1.0200115 against a 1.02 bound. Reproduced deterministically. A7: the real `EngineModule` is never wired through `fadec_input_connections` in a `System` in any test |
| W1.4 | A2 (35 edges, mutant killed); A4; A5; fuel-mass and brake-energy balances | Hydraulic-heat and battery balances check bookkeeping only. The end-to-end zoom-climb gauging artefact (split between M09 and M12, AD-42) is untested |
| W1.5 | A1; A3 bias ≠ deterioration (mutant killed); A7 | **A6 cannot fail**: a mutant writing M11 truth into M14's `description` passed all 25 M14 tests. A4 template windows are sums of ASSUMPTION latencies. A5 persistence check is overlap-only |
| W1.6 | A1, A2, A4, A6 (recorder off-by-one-draw mutant killed), A8 | The A3 ceiling unit test checks configuration only. No assertion that A5 `value` is independent of truth |
| W1.7 | A1, A2, A4, A5, A6, A8 (fresh-process bytes) | A3/A7 public-sample coverage runs only with `-m data` |
| W1.8 | A1; A3; A4 no look-ahead, replay, idempotency; A6 | A5 paired-variance assertion (`test_fork_crn.py:117`, n=6) still passed with CRN deliberately broken; only the CI assertion at `:119` caught it |

## 3. Xfail audit: 27 strict xfails (26 in `make check`, plus 1 slow)

**OK** (reason states the number and the resolving wave):
- idle anchors, MIL Wf, C2, C3, C10, C18 small-step, C22, C26, −400 method check (W2.3);
- C20/21, C23 (structural PROXY);
- V9;
- FCS all-points margins;
- Muir 1:1.

**Missing the measured number:**
- C4, C5, C6, C17;
- V7 (ARI −5.51/−0.87/−0.28 against −3.47/+0.60/+0.319: wrong sign at M0.7 and M1.3);
- both W2.6 priors (occupancy 0.593 / NMCD structurally 0; CANN 9.23 vs 10.6–12.7);
- VG rows.

**Mislabelled or problematic:**
- **VG rows:** a Muir-convention and model-sign question, not calibration.
- **C11:** compares a steady point with a transient snapshot, so calibration cannot fix it.
- **Engine dispersion** (1.13–1.16 vs ≥1.15) is a plan-level W1 gate and needs an explicit waiver.
- **Realised Nz / engine-cycle gates** have no target and import `phalanx.integration.telemetry_fleet_run`, which the W2.1 brief never creates, so the tripwire never fires.
- **MIL-310** has no `raises=` and no data owner.

None of the xfails hides a balance, invariance or determinism failure.

## 4. Cohesion mismatches

**Tracked:**
- AD-48.2 `ops.takeoff`;
- AD-48.4 fault-inject handlers (`fadec.`/`af.fault_inject` are never constructed in `src`);
- AD-48.6 wear;
- AD-47 brake/chute;
- AD-49 refuel and uncatalogued kinds;
- unified code table;
- `ENG.AB_LIT` producer;
- VG/`a8_min`/on-board model/P0 harmonisation (M08 commands VSV 0.873 rad vs M07 reference 0.609 rad at idle);
- recorder placement;
- entry gates 1–3 (the T5 lane sits on the harness floor at idle);
- avionics computed-outputs owner;
- `af.quat`.

**Untracked (new):**

| # | Mismatch |
|---|---|
| U1 | `util.bus_v`: M09 publishes (4,), M12 binds (3,). The W2.1 `System` build would raise a shape `ContractError` |
| U2 | **AD-48.1 scope understated.** 18 catalogued kinds from M02, M11, M14, M18 and M21 are emitted `{"doc": json}`-encoded, not just M18's. Inner keys all conform. A validator built to the catalogue would reject all hub traffic (runtime spy over the full fast suite, 2,330 tests) |
| U3 | Multi-engine FADEC lanes: M08 expects lane buffers (cap, e), but M12/M13 lanes are (1,) with no engine axis. W2.4a (4 engines) has no lane producer |
| U4 | Proxy mode has no producer for `af.mach` (M07, M12), `af.tas`/`af.alt` (M12) or `scenario.phase` (M13) |
| U5 | Cross-module index maps are defined twice with no tie test: `env.w_engine` columns (M03 vs M07), `health.engine` (M10 vs M07), `util.bus_v`/tanks (M09 vs M12), surf_pos. Consistent today; mutants m02 and m13 survive |
| U6 | Signals catalogued for M12 by AD-42 (`af.hag`, `util.brake_p`, `util.hyd_res_level`, `util.probe_heat`, `util.fuel_inlet_t`) are not bound by M12. Of 464 dictionary channels, 261 have neither an M12 sensor nor a RECORDED producer. ECS, BRK.PRESS, HYD level, ENG.FUEL_INLET_T and SPS/JFS have no plan |
| U7 | The conformance gate checks only input rank, not M11–M14 bindings, lane producers or clocks |
| U8 | `mx.monitoring` (M18→M14) and `m18.disruption` (M02→M18) are never emitted in any test |

## 5. Wiring-readiness probe

**Setup:**
- Modules: M03 `EnvironmentReplay` + M04 `PilotReplay` → M08 ↔ M07 → M12 → M13 FADEC lanes.
- 72 edges derived from bindings only; 11 back-edges delayed automatically.
- 20 out-of-scope signals held at a labelled boundary.
- 10 s at PLA 18°, then a step to 45°.

**Results:**
- Idle 66.99 % N2 / 37.9 % N1, with zero validation steps, zero fault codes and nothing non-finite.
- Wf moves within 1 tick of the step; N2 reaches 5 % of its change at 0.17 s, so **Wf leads N2**. τ63 = 1.85 s; final N2 75.2 %.
- Three fresh processes (block, block, step mode) give trace `9bf10876…` and snapshot `14d10caf…`.
- A snapshot taken mid-FADEC-frame (k=1201), restored and continued, matches bitwise.

| # | Friction |
|---|---|
| F1 | No M07 trim-at-condition API; idle start needs test-only continuation plus copying `initial_wf`/`a8`/`vg` into M08 |
| F2 | **Performance:** the M08→M07→M12→M13 cycle runs per step even in block mode, at ≈690–780 µs/step (M13 lanes ≈168, M08 ≈198, M12 ≈89, M07 ≈46). The W2.1 budget is ≈83 µs/step for the whole aircraft, and the W2.1 fused kernel excludes the in-loop lane path |
| F3 | `ENG.AB_LIT` has no producer (tracked) |
| F4 | `lane_modules()` uses a dummy ParamSet; there is no canonical M13 ParamSet for the config hash |
| F5 | Binding accessors are inconsistent across modules |
| F6 | `phalanx.fadec` re-exports `ports`, shadowing the submodule; a stale "NOT YET CATALOGUED" comment |
| F7 | M12 is monolithic: an engine-only loop must feed about 20 airframe/FCS/utility signals |

## 6. Mutation testing (cross-module): 13 of 18 non-equivalent mutants killed

**Survivors:**
- **m02:** M07 reads `env.w_engine` columns reversed.
- **m06b:** M18 `mx.action` key `tail` → `tail_no`.
- **m10:** M11 edge latency → 0.
- **m13:** M12 reads the wrong `util.bus_v` index.
- **m19:** M07 publishes `eng.t5` in °C on a K port.

**Equivalent:** m15 (frame-schedule `t_start` shift).

**Killed:**
- m01 limiter MIN→MAX;
- m03 disturbance columns swapped at M03;
- m04 PLA in degrees (incidentally);
- m05 flight hours ×60;
- m07 M14 set/clear inverted;
- m08 look-ahead check off (property test only);
- m09 noise-ceiling headroom;
- m11 bias index map;
- m12 RECORDED N1/N2 swapped;
- m14 AIRBORNE_PHASES;
- m16 JFS PTO sign;
- m17 N1.A reads N2;
- m18 hydraulic ΔP in bar.

**Within-module mutants (subagents):** 13 of 15 killed. The survivors are:
- W1.1 OU τ ×2 (caught only marginally);
- W1.5 truth written into M14 `description`.

## 7. Evidence (56 rows checked; starred rows re-verified)

**Findings:**
- M05 `servo_wn`\* is tagged DIRECT although A-W1.2-20 calls it an ASSUMPTION.
- M08 `heal_frames`\*: the donor is unnamed, and the change from a 40 ms to a 60 Hz frame base has no note.
- The 9 M08 OBM tables\* lack `proxy: true`.
- M10 `bias_speed_pct` is tagged MEASURED but is a proxy value; it should be TRANSFER.
- In `faults/graph.yaml`, 32 of 42 edges are tagged DIRECT; they should be TRANSFER.
- The M13 EGT/FF noise and ceiling entries are tagged MEASURED but are applied to Tejas; they should be ASSUMPTION.
- The M15/M16 offset σ 20 ppm conflict is not logged (R:563 vs R:1036 vs 910 ppm).
- W1.8 `aog_bin_share` claims "conflict logged", which is false (38 % of demands are unaccounted for).
- M03 USSA constants are tagged DIRECT; they should be TRANSFER/standard.
- M02 `engine_start` is 45 s against ≈40 s evidence, with no sweep.
- M11 `usage_detection_sigma` and the M02 scale height are code constants.
- The M14 `t_utc` PROXY has no row, and its replacement route does not exist.

**Restricted-value check (report App. A1):**
- The gated paths are clean: configs, src, docs/contract and **all briefs** (36 patterns, 55 hits reviewed by hand).
- Values were found **outside** the gated paths:
  - `analysis/backend_benchmark/code/workload.py`;
  - `docs/build_gates/E0_verifier_report.md`;
  - `docs/build_audit_log.md` (entries 105, 109);
  - the `tests/integration/test_fadec_limiters.py` docstring.
- The guard test does not scan briefs, docs, analysis or tests.

## 8. Behavioural readiness († = wired probe)

| Target | Shown at module level |
|---|---|
| Idle / MIL | SLS idle 65.96 % N2; 66.99 % †. MIL design 95.2 % N2. Closed-loop IRP only 92.7–93.0 % N2 (N1 held at 102 %) |
| FF→N2 lag | Fixture −0.25 s; real M07 + shaft load −0.50 s; † M03 default mix −0.50/−0.50/−0.75 s |
| FF correlation signs | Real M07 at PLA 60: r(N2,FF) +0.27…+0.32, r(N1,FF) +0.57…+0.63 (real +0.67/+0.65). † M03 default mix: r(N2,FF) +0.006…+0.11. Signs invert from **≈PLA 65** (N1 limiter) |
| N1–N2 (AD-46) | Fixture direct-Wf governor: 0.746 → 0.311 with fan_face. **Under the real M08 law, fully wired** (n=24 runs): default 0.59–0.79. Every mix that brings r(N1,N2) to ≤0.55 drives r(N1,FF) to −0.40…−0.73 and B2 to ≥0. **The joint target was not reached** |
| N1–EGT | † −0.04…−0.12 (truth T5 also ≈0) against real +0.56. Not tested anywhere in W1 |
| Noise ceiling | Holds (n=20+20) |
| Usage gates | Plan level passes (n=2,138 sorties). Engine dispersion fails (1.13–1.16). Realised gates are stubs |

## 9. Must-fix before W2

1. **MF1 (before W2.4a identification starts): AD-46 under AD-50.** Re-run reachability with M08 in the loop, including the proxy A/T outer loop, jointly with positive FF correlations. If it cannot be reached, decide on the second LP path.
2. **MF2:** harden the cohesion gate (exact shapes; M11–M14 bindings; every `lane.*` has an M13 producer or a tracked exception) and fix U1.
3. **MF3:** correct AD-48.1 and the W2.1 brief to cover all 18 doc-encoded kinds (U2).
4. **MF4:** test-only fixes:
   - an M07 module-adapter test (kills m02, m19);
   - the M08 property counterexample (`@example`, then fix or log a deviation) and a Hypothesis `@example`/seed policy;
   - a content-level M14 A6 leak test;
   - the realised-gate stubs get a real target and harness name, or become a tracked skip.

**W2 entry items:**

| Area | Items |
|---|---|
| W2.1 | The fused group includes the M12/M13 lane path (F2); M07 trim API (F1); widen entry gate 2 to ≈PLA 65; tie tests for index maps (U5); a module-level cascade-latency test (m10); exercise `mx.monitoring` and `m18.disruption`; ParamSet and accessor conventions (F4, F5) |
| W2.4a | Multi-engine lanes (U3); `af.*`/`scenario.phase` replay producers (U4); report N1–EGT |
| W2.2 | M12 channel-coverage plan (U6); M14 `events.*` full-path route; zoom-climb end-to-end test |
| Hygiene | Evidence-tag fixes (§7); missing xfail numbers and the stale skip reason; non-circular W1.1 A3 PSD targets; V4 and A5 bands back to the brief; a nonlinear FCS margin check; CRN-variance n with an F-bound; the engine-dispersion waiver; restricted values in analysis/docs/tests; extend the guard |

`git status` was clean at the end.

---

## Coordinator disposition (2026-10-15 04:57 IST)

**Accepted: GO-WITH-CONDITIONS.** Wave 1 is VERIFIED subject to the closures below. The coordinator also spot-checked the restricted-value finding and confirmed it.

| Item | Disposition |
|---|---|
| Restricted values outside the gated paths | **Fixed by the coordinator now.** The four files are redacted in the working tree. The history purge item (E3) now includes them, and the guard extension to docs/analysis/tests/tools goes to E1-HY |
| MF1 | Two parallel tracks. **(a) MF1-D:** a pre-registered, CAL-only diagnostic of what makes real fast-band N1–N2 low (lag vs independent variance, by coherence and phase), plus N1–EGT. **(b) W2.4a split:** W2.4a-1 builds the proxy chain (separate_fixed, A/T loop, U3, U4) and runs the joint reachability study; then it **stops for the coordinator's MF1 decision**. W2.4a-2 (identification on 687-CAL, quick look) starts only after that decision |
| MF2, MF4, U5, m10, U8 | Work package **E1-MF** (cohesion and tests). Runs before W2.1 |
| MF3 | Done by the coordinator: AD-48.1 amended and the W2.1 brief corrected |
| Hygiene | Work package **E1-HY**. Runs in parallel with E1-MF |
| Engine dispersion | Explicit waiver recorded in the tracker: plan-level 1.13–1.16 vs ≥1.15 (target ≈1.3). It stays a strict xfail with its number, and is resolved by W2.6 fleet allocation (owner of the per-engine utilisation spread) |
| W2.1, W2.2, W2.4a entry items | Added to the respective briefs |
