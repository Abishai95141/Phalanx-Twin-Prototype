# RULES.md — Project Phalanx

## Mission

Phalanx is for problem statement 26249 (MoD/DSSC): *Air Power: Predictive Maintenance & Fleet Availability*.

**This repository builds the data layer only:** a robust, deterministic, forkable **virtual Tejas-class fleet**
(HAL Tejas Mk1A, GE F404-GE-IN20). Its physical and operational state produces the data a real fleet would:
- sensor data, bus data and recorder data;
- BIT and fault events;
- maintenance records.

Downstream predictive-maintenance and availability solutions plug into its data contract and its orders channel.
They are not built here.

> We are not generating random numbers that look like aircraft data. We are building a virtual aircraft whose
> physical and operational state produces observations that resemble what a real aircraft would generate.

**Done means:**
1. Every module meets its acceptance tests.
2. The behavioural fidelity battery passes against real-vs-real bars.
3. The ground-decoder contract is stable.
4. Any run can be replayed bit-for-bit and forked from any snapshot.

## Before you decide anything: consult the evidence first

Extensive research has already been done. **Do not make a design, modelling, parameter or validation decision
from your own assumptions until you have checked these sources, in this order:**

1. **`docs/architecture.md`.** The binding architecture spec: the decision register (AD-01 onward; §17 is the authoritative list), module specs and acceptance tests. If it decides something, follow it.
2. **`reports/Virtual fighter telemetry layer research.md`.** The full research report (~20k words): evidence, rationale, numbers, sources, alternatives held open. **grep it for context** on any topic you touch before deciding. The path contains spaces, so quote it:
   ```bash
   grep -n -i "<keyword>" "reports/Virtual fighter telemetry layer research.md"
   ```
   Useful keywords:
   - aircraft and engine: `F404`, `IN20`, `EGT`, `PS3`, `FADEC`, `DFCC`, `1553`, `Ch10`, `hydraulic`, `JFS`;
   - recorder and texture: `quantis`, `slip`, `clock`;
   - faults and validation: `BIT`, `false alarm`, `LUI`, `Muir`, `C1–C28`, `V1–V12`;
   - operations: `sortie`, `CAG`, `NAMP`, `S5000F`, `fork`, `orders`.

   Appendix A lists restricted, unreplaced and conflicting values; check it before using any limit or number.
3. **`research_notes/Virtual fighter telemetry layer research/`.** Detailed notes behind the report (~300k words), plus `parameter_inventory.csv` and `not_measured_states.csv`. grep these for parameter-level detail.
4. **`analysis/*/`.** Experiment results (`README.md`, `CLOSEOUT.md`, `REPORT.md`, `DEVIATIONS.md`). These record measured facts that supersede earlier assumptions.

**Precedence when sources disagree:**
1. `docs/architecture.md`
2. experiment results
3. the research report
4. the research notes

Report any conflict you find; don't resolve it silently.

**If none of these covers your question:**
- Say so explicitly.
- Propose a decision with an evidence tag, the alternatives and what would change it.
- Record it as a proposed `docs/architecture.md` decision-register entry for the coordinator to approve.

Never invent a parameter value without searching first. Never present a choice as established if it isn't
recorded in these sources.

## Non-negotiable rules

### 1. Minimal sufficient sample
- **Every test, validation, architectural check and experiment uses the smallest data sample that can answer its question.** Scale up only when a stated requirement demands it: statistical power, CI width, or coverage of a rare regime.
- **Default ladder:** smoke = 1–3 sorties or flights; integration = 5–20; statistical check = the minimum n for the stated CI or power, which you write down before running. Full datasets only for final generation or a pre-registered final evaluation.
- **Always sample → verify → scale.** Run the small batch, check outputs (format, values, invariants, agreement with a reference), and only then run larger. Log each check.
- Record the sample size and its justification in the result file. A result without a stated n is incomplete.
- Choose samples deterministically: fixed seed, saved list of flights or sorties.

### 2. No shallow proxies
- Never replace a physical or behavioural mechanism with a stand-in that only *looks* right. Banned as deliverables:
  - "ideal signal + Gaussian noise";
  - independent per-channel noise standing in for coupled dynamics;
  - constant or linear placeholders presented as models;
  - mocks of the system under test;
  - hard-coded or tuned-to-pass outputs;
  - metrics with no real-vs-real baseline;
  - a discriminator AUC used as proof of realism.
- **Coupled behaviour must come from the physics or dynamic model.** The texture layer carries only effects that are physically independent per sensor: quantisation (native step + recorder lattice), sensor noise, recorder and clock artefacts.
- If a simplification is unavoidable, it must:
  - be labelled `PROXY` in code and in the parameter dictionary;
  - carry an evidence tag and a source;
  - have a test that would expose its limitation;
  - be listed in `docs/assumptions.md` with how it gets replaced.

  An unlabelled proxy is a defect.
- Mocks are allowed only at module boundaries inside unit tests, never in a deliverable path.

### 3. Evidence discipline
- Every parameter, limit, rate and model choice carries a tag:
  - `[DIRECT]`: Tejas, IN20 or IAF itself;
  - `[TRANSFER: source]`: from another platform, with the reason and the limits;
  - `[MEASURED]`: from our own analysis of real data;
  - `[ASSUMPTION]`: with its validation route.

  Each also needs a citation (URL or `research_notes/...`).
- **Evidence base:**
  - `reports/Virtual fighter telemetry layer research.md`, the source of the decision register;
  - `research_notes/Virtual fighter telemetry layer research/`, including `parameter_inventory.csv` and `not_measured_states.csv`;
  - `analysis/*/` (experiment results).
- **Never use or cite** restricted or limited-distribution documents (`research_sources/_restricted_do_not_cite/`). Use only officially released, unclassified material.
- Don't fabricate numbers. If a value is not public, say so, sweep it inside a plausible range, and tag it `[ASSUMPTION]`.

### 4. Validation
- **The primary gate is the behavioural fidelity battery**, each test judged against real-vs-real bars:
  - B1 cohesion: slow/fast-band correlation structure;
  - B2 lead–lag order;
  - B3 dynamic response;
  - B4 directional dependence;
  - B5 physical laws: corrected parameters, EGT exponent;
  - B6 regime behaviour;
  - B7 fault signatures;
  - B8 BIT/event behaviour;
  - B9 downstream fitness: TSTR, ranking agreement.

  Pass means synthetic-vs-real distance ≤ real-vs-real distance (tail-vs-tail; the temporal comparison is the stricter bar).
- **Binding guards:**
  - trivial-cue audit: generation must leave no pipeline artefacts;
  - label-leak audit: fault and healthy data come out of the identical generation path.
- Discriminators (C2ST, MiniRocket and similar) are **diagnostics only**. They locate differences; they never decide pass or fail.
- **Experiments are pre-registered** (`analysis/*/PREREGISTRATION.md`) and committed before any data is generated or holdout data is read.
  - Deviations go in `DEVIATIONS.md` with the date, reason, and results both ways.
  - Never fit or tune on test or holdout data.
- Credibility ceiling: NASA-STD-7009B Level 2 against proxy data. State it in reports, and never overclaim.

### 5. Determinism, state and forkability
- Physics and texture are **pure step functions over explicit state**, in SI units, checked at module boundaries.
- Every module implements complete `get_state` / `set_state`. No hidden state, no wall-clock dependence, no global RNG.
- **Randomness comes from identity-keyed counter-based streams:** key path (scenario, tail, serial, sortie, subsystem, sensor, component), via NumPy SeedSequence spawn keys or Philox/Threefry. Never seed arithmetic.
  - This is what gives forks common random numbers. Changing an order must not perturb the exogenous future.
- **Decisions enter only through the orders channel (M21).** Orders are stamped with simulation time, logged, validated against resources and airworthiness, and applied at decision epochs.
  - A run is a pure function of (root seed, config, dictionary version, order log).
  - Message or transport timing never alters state.
- **Required tests:**
  - snapshot → restore → continue is bitwise identical to an uninterrupted run;
  - identical fork suffixes give identical branches;
  - a CRN audit;
  - replay of an order log reproduces the live run;
  - no look-ahead: the decision interface sees only data ingested up to the decision time, never truth.

### 6. Data contract
- The stable boundary for downstream users is the **ground-decoder contract**:
  - `param.samples`, `events.*`, `usage.counters`, `maint.records`, `orders.*`, `sortie.manifest`;
  - canonical sample record with six time fields, a validity enum, quality flags, provenance, `record_id` and dictionary version.
- The parameter dictionary (M01) is the single source of truth: it generates TMATS, bus maps and schemas.
- Synthetic ICD and code tables are labelled synthetic. Never claim they are the real Tejas ICD.
- Contract changes require a version bump, a migration note, and a decision-register entry.

### 7. Engineering
- **Python stack:** pinned versions; scripts run with `python -I`; data paths passed as arguments; nothing executed from data directories (downloaded data is untrusted).
- **Hot loops** are compiled: Numba or JAX on CPU, chosen by the phase-1 benchmark.
- **Two-tier fidelity:** usage mode (fleet-years, sortie summaries) and telemetry mode (full-rate recorder data for selected sorties and windows) share one state and one set of RNG keys.
- **Every module ships with:** typed ports, parameters with provenance, unit and property tests, an acceptance test, and a short README stating assumptions and validation criteria.
- **Compute:** multi-core CPU first; Kaggle for parallel batches (private datasets and kernels only).

### 8. Process
- **Filesystem:** read/write only inside `/Users/abishaikc/Phalanx`, plus read-only `/Users/abishaikc/phalanx/data/raw/` when a task needs it. Never touch other directories.
- **Git:** agents commit small, focused changes locally with clear messages. Only the coordinating session pushes. Never commit `research_sources/`, credentials, large regenerable artefacts or local editor settings.
- **Kaggle:** agents never run Kaggle upload or push commands themselves. They stage the folder and write the exact command to the task's `kaggle_pending_cmds.txt`; the coordinating session reviews it and runs it. Never print, copy or upload the Kaggle token.
- **Ownership:** agents edit only the modules or folders they are assigned. Interfaces change only through the coordinator.
- **Reporting:** report failures and limitations plainly; a failed test is a finding. Never claim a check passed without showing its output.
- **Build tracking:**
  - `docs/build_status.md` is the tracker; `docs/build_audit_log.md` is the append-only audit log; `docs/build_briefs/` holds the agent briefs. The coordinator maintains all three.
  - Nothing merges to `main` unless `make check` passes: lint, format check, the static determinism audit and the tests.

## Architecture (summary; the binding spec is `docs/architecture.md`)

**Pipeline:** truth physics → sensors → acquisition/texture → bus → recorder (IRIG 106 Ch10) → ground decoder → streams and storage, with event, record and order streams alongside.

| ID | Module | ID | Module |
|---|---|---|---|
| M01 | Parameter dictionary and provenance | M12 | Sensor physics |
| M02 | Scenario, fleet calendar, missions | M13 | Acquisition and texture (form settled by round 2) |
| M03 | Environment and process disturbances (USSA-76, MIL-HDBK-310, ERA5; AD-32) | M14 | Monitoring and BIT (CBIT/PBIT/IBIT, CWS, ECMS/HUMS, LUIs) |
| M04 | Pilot and guidance | M15 | Bus encoder and clock domains |
| M05 | FCS (DFCC replica) and actuators | M16 | Recorder writer and download |
| M06 | Airframe 6-DOF and Tejas-anchored aero | M17 | Ground decoder → canonical contract |
| M07 | F404-IN20 engine (component-level model + dynamics) | M18 | Maintenance, logistics, records |
| M08 | FADEC and signal validation | M19 | Streaming and storage |
| M09 | Utility systems | M20 | Validation and calibration harness |
| M10 | Health state and degradation | M21 | Orders and decision interface |
| M11 | Fault injection and propagation | M22 | World snapshot and fork service |

## Round 2 outcome and reserved data

- **Round 2 is resolved** (`analysis/settling_experiment_round2/REPORT.md`, verdict REWORK). Its lessons are requirements in architecture v1.0:
  - AD-31: closed-loop governing;
  - AD-32: per-unit process disturbances;
  - AD-33: archive-2 proxy-mode gate;
  - AD-34: transient-weighted dynamic identification.

  The open-loop deterministic model plus texture is the negative baseline the build must beat.
- **Tail 687 archive 2 (`research_sources/datasets/dashlink_tail687/raw2/`) is reserved and unread.** It is the holdout for the AD-33 proxy-mode gate. Never read, list or load it until that gate's pre-registration is committed.

---
*Approved by the project owner on 2026-10-14; amended 2026-10-14 (consult-the-evidence-first section, owner request); amended 2026-10-14 (synced with architecture v1.0: AD-35 range, round-2 outcome, reserved archive 2, build tracking and the `make check` merge gate; owner approved); amended 2026-10-14 (decision range AD-01…AD-40; owner approved); amended 2026-10-15 (decision range made open-ended, "AD-01 onward", so it does not go stale as the register grows; owner approved). Changes need owner approval and a commit that explains the reason.*
