# E1-MF: E1 must-fix: cohesion gate, `util.bus_v`, and tests that can fail

**Context.** The E1 verifier returned GO-WITH-CONDITIONS (`docs/build_gates/E1_verifier_report.md`; read all of
it). This work package closes MF2 and MF4, plus three cohesion items E1 found. It lands **before W2.1 starts**,
so keep the scope tight. Every new check needs a **negative control or mutant run** that proves it fails when it
should.

**Owned paths:**
- `tests/integration/test_interface_conformance.py`, `configs/interfaces/w1_ports.yaml` (the U1 fix and the
  exception list only);
- new test files under `tests/`;
- the minimal source fixes named below.

Report every edit outside the tests, with its reason.

**Read:**
- `_common.md`, `_w1_common.md`, `W1_interfaces.md`;
- `docs/architecture.md` AD-36, AD-42, AD-44, AD-45, AD-48;
- the READMEs of the modules you touch;
- the E1 probes: these are git-ignored scratch in the main checkout, `runs/e1/probe/` (read-only reference).

## Items

1. **MF2: harden the conformance gate (U7).**
   - **Exact input shapes:** the test checks exact shapes, not rank, for n_engines ∈ {1, 2, 4}.
   - **Coverage:** it covers **all 15 `ports.py` modules**, including M11–M14.
   - **Lane producers:** every `lane.<channel_id>` binding must resolve to an M13 lane producer for that channel,
     or sit on a **tracked exception list** in `w1_ports.yaml` that names the owning WP. Known entries:
     - `ENG.AB_LIT` → W2.1;
     - multi-engine lanes for e > 1 → W2.4a-1 (U3);
     - proxy-mode `af.*`/`scenario.phase` producers → W2.4a-1 (U4).
   - **Clock rule:** add a check of declared port rates against the producer clock. FCS lane ports declare
     `rate=None` while M13 lanes run on DFCC@80 Hz. Derive the rule from AD-36/AD-42; enforce it or list tracked
     exceptions.
   - **Negative controls:** a planted (3,) vs (4,) shape mismatch, and a planted lane with no producer, must each
     fail the gate.
2. **U1: `util.bus_v` 3 vs 4.** M09 publishes (4,) and M12 binds (3,) (`sensors/config.py`, `buses: 3`).
   - Decide which side is right from the evidence: the dictionary's electrical channels and the report/notes on
     the Tejas electrical buses (grep `bus`, `electrical`, `TRU`).
   - Fix the wrong side and cite the source.
3. **U5: index-map tie tests.** Cross-module index maps are defined twice:
   - `env.w_engine` columns: M03 `ENGINE_CHANNELS` vs M07 `W_ENGINE_NAMES`;
   - `health.engine`: M10 vs M07;
   - `util.bus_v` and the tank maps: M09 vs M12;
   - `surf_pos`: M05 vs M12;
   - any others you find.

   Prefer a single source of truth, with the consumer importing the producer's names. At minimum add tie tests.
   Show that E1 mutants **m02** (M07 reads the `env.w_engine` columns reversed) and **m13** (M12 reads the wrong
   `util.bus_v` index) now die. Run mutants on a `git archive` copy only.
4. **MF4a: M07 module-adapter test.** The `EngineModule` ports must equal the kernel/`simulate` outputs, with
   **distinct per-column disturbances**. It must kill **m02** and **m19** (M07 publishes `eng.t5` in °C on a K
   port).
5. **MF4b: M08 property counterexample.**
   - The counterexample: PLA 89°, 220 K, 91.9 kPa, M0.5. PS3 transient 1.0200115 against a 1.02 bound,
     reproducible through `inner_test`. Add it as an `@example`.
   - Root-cause it. If it is a limiter defect, fix it in M08 (minimal change; the W1.3b tests must stay green). If
     it is a legitimate transient tolerance, log a deviation with the physics.
   - Adopt a **Hypothesis policy:** a deterministic profile for `make check`, and every found counterexample
     pinned as an `@example`. Document it in the tests README or `_w1_common.md` (report the text; the
     coordinator edits briefs).
6. **MF4c: content-level M14 A6 leak test.** No M14 consumer-facing field (`description` included) may carry M11
   truth: fault mode, severity, hidden parameters. It must kill the E1 mutant that writes truth into
   `description`.
7. **MF4d: realised usage gates.**
   - The realised Nz / engine-cycle gate stubs have no target, and they import `phalanx.integration.
     telemetry_fleet_run`, which nothing will create.
   - Give them explicit targets from `docs/behavioural_targets.md`: the Nz spectrum within ±30 % of the F-16
     curve; Type III cycles and TAC per FH.
   - Give them an **exact harness entry point** that W2.1 will implement, and report the name.
   - Keep them as strict xfails with `raises=` scoped to the missing entry point only.
8. **m10: M11 cascade latency.** Add a module-level test that a graph edge's declared latency is honoured: no
   effect before it, an effect after it. Kill **m10** (edge latency → 0).
9. **U8: unexercised events.** Add tests that:
   - M18 emits `mx.monitoring` and M14 handles it;
   - M02 emits `m18.disruption` and M18 handles it.

## Acceptance

- `make check` is green with `set -o pipefail`, and the cohesion gates show **zero skips**.
- A mutant table on `git archive` copies shows **m02, m10, m13, m19 and the M14 description mutant killed**.
- The negative controls of item 1 fail as intended.

**Sample:** module-level fixtures; the minimal steps needed. State n.

## Report (final message)

- Item-by-item outcome.
- The U1 decision and its source.
- The M08 root cause and fix (or deviation).
- The harness entry-point name.
- The mutant table and the negative-control outputs.
- Every edit outside the tests.
- Commits on `wp/e1-mf`, clean `git status`. Do not push or merge.
