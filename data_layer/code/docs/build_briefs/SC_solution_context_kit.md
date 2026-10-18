# SC: Solution-context kit (`solution_context/`)

**Goal.** The owner's team is building the downstream AI/ML solution for the problem statement (*Air Power: Predictive
Maintenance & Fleet Availability*) in a separate repository, on top of this data layer. Give them **one folder**
that holds everything they need to understand the data stream and to engineer against it:
- copies of the consumer-facing contract, schemas and dictionary artefacts;
- the supporting reference documents;
- format examples;
- a **master `README.md`** that gives the whole context in one place.

**Hard scope rule: no solution strategies.** Describe the data layer only: what it simulates, what it emits,
formats, types, semantics, guarantees, interfaces, limits and status. Never recommend:
- models, algorithms or features;
- solution architectures, metrics to optimise, or approaches.

Stating a rule the data layer enforces is fine. For example: orders citing evidence with `t_ingest` after the
decision time are rejected; consumer readers refuse `labels.truth`.

**Owned paths:**
- `solution_context/` (new);
- `tools/build_solution_context.py` (new);
- a `solution-context` target in the `Makefile`;
- one line in `tests/unit/test_dictionary_restricted_guard.py`, adding `solution_context/` to the scanned roots;
- a test file `tests/unit/test_solution_context.py`.

Touch nothing else.

## Build it with a script, not by hand

`tools/build_solution_context.py` (run with `python -I`; paths as arguments) regenerates the folder
deterministically: the same tree gives byte-identical output, with no wall-clock timestamps. It does three things.

1. **Copies** the consumer-facing artefacts from their generated sources (never edit the copies):
   - `docs/contract/contract/v0/` (`contract.md`, `arrow/`, `avro/`, `jsonschema/`, `dictionary_binding.json`) →
     `solution_context/contract/`;
   - `docs/contract/dictionary.<current>.json`, `parameters.md`, `icd.md`, `icd.csv`, `tmats.txt`,
     `tmats_setup_record.c10` → `solution_context/dictionary/`;
   - `docs/architecture.md`, `docs/behavioural_targets.md`, `docs/assumptions.md` → `solution_context/reference/`;
   - every `src/phalanx/*/README.md` → `solution_context/modules/<MNN>_<package>.md`, mapping each package to its
     module ID from the architecture table.
2. **Writes `MANIFEST.json`** with:
   - for each file: its source path, sha256 and size;
   - the source git commit;
   - the contract version, contract hash and schema hash;
   - the dictionary version and hash;
   - the generator version.
3. **Generates format examples** in `solution_context/examples/`. For every **consumer-visible** topic (never
   `labels.truth`), write a small Parquet file (plus JSON where the contract defines JSON-Schema) **through the
   real contract writers and validators**, so every example is schema-valid.
   - Use the existing example and fixture producers (`phalanx.ground.examples`, the M14/M18/M21 module paths used
     by their tests). Keep them minimal: a few records per topic, one tail, one sortie.
   - Label every example file and `examples/README.md` **FORMAT EXAMPLE, not physics, behaviour not validated**.
   - Include a reader snippet (pyarrow) in `examples/README.md`, showing how to read a topic and check its schema
     hash.

Then write the master `solution_context/README.md`, by hand, with generated tables embedded by the script. Field,
topic, enum and flag tables must be **generated from the Arrow schemas and contract spec**, not retyped, so they
cannot drift.

## The master README: required sections (context only)

1. **What this folder is.**
   - Who it is for; the source commit and versions (from the manifest).
   - How to regenerate it (`make solution-context`).
   - "Synthetic data; the ICD and code tables are synthetic, not the real Tejas ICD".
   - The credibility ceiling: NASA-STD-7009B Level 2 against proxy data.
2. **Problem-statement context.** the problem statement by title. The data layer's role is to produce what a real fleet would
   produce (sensor, bus and recorder data; BIT and fault events; maintenance records) and to accept decisions
   through the orders channel. No strategy.
3. **The virtual fleet.**
   - What is simulated: Tejas Mk1A-class aircraft and the F404-IN20; fleet calendar and missions; environment;
     airframe and FCS; engine and FADEC; utilities; health and degradation; faults and propagation; monitoring and
     BIT; maintenance and logistics; orders; forks.
   - Identities: tail, serials, sortie, engine serial.
   - The two fidelity tiers: **usage mode** (sortie summaries, fleet-years) and **telemetry mode** (full-rate
     recorder data for selected sorties and windows). They share one state and one set of random keys.
4. **The data pipeline:** truth → sensors → acquisition/texture → bus (MIL-STD-1553 / ARINC 429, synthetic ICD)
   → IRIG 106 Ch10 recorder → ground decoder → contract.
   - Fast path vs full path, and the `provenance` field.
   - What "texture" means: quantisation, noise, and recorder and clock artefacts, which are physically independent
     per sensor. All coupled behaviour comes from the physics.
5. **The data contract.**
   - Topics, with event-time and ingest-time fields, partitioning, visibility and formats (Parquet, Avro,
     JSON-Schema).
   - Per-topic purpose, identity key (`record_id` construction) and linkage keys.
   - Point to `contract/contract.md` for full field tables, and embed the generated summary tables.
6. **Time model.**
   - The time fields and their scales: `sim_utc` ns, `recorder_rtc` (not comparable across recordings), duration.
   - What each field means on the fast and full paths (AD-35, AD-45).
   - **Information discipline:** `t_ingest` and the decision time.
7. **Data quality semantics.**
   - Every `Validity` value and every `QualityFlags` bit, with its meaning.
   - Sentinels; missingness (clock-slip windows only, no random dropout); late and duplicate downloads and
     idempotency by `record_id`.
   - No NaN, explicit nullability.
   - Redundant lanes, voted `.V` channels and LRU-computed recorded channels; native steps and the recorder
     lattice.
8. **The parameter dictionary.**
   - How to navigate the dictionary JSON: channel naming, units, rates, lanes, ranges, source LRU, bus mapping.
   - Generated counts by subsystem.
   - The synthetic ICD and TMATS.
   - The channels that are "not measured / not simulated", and how the contract marks them (the coverage plan is
     coming in W2.2; say so).
9. **Events, usage and maintenance records.**
   - BIT/exceedance/caution events: detection mechanisms, severity, fault lists PFL/MFL, latch and persistence,
     suspect-LRU lists, and the false-alarm behaviour the layer reproduces.
   - Usage counters: LUIs, TAC, cycles, starts, landings, Nz counts.
   - Maintenance record types (NAMP/TO 00-20/S5000F-based, synthetic codes) with their linkage keys, event chains
     and availability states.
10. **Orders channel (the input path into the world).**
    - The order record and the action vocabulary (from the `OrderAction` enum).
    - Priorities; validation (authority, airworthiness, resources); the status lifecycle; decision epochs and
      `t_effective`.
    - Evidence as `record_id`s, and rejection of un-ingested evidence.
    - Imperfect execution (detection probability, misdiagnosis, induced defects).
    - Event sourcing: a run = f(root seed, config, dictionary, order log).
11. **Truth and labels.**
    - What `labels.truth` holds and why it is restricted (consumer readers refuse it; invariant I5).
    - The guarantees: the label-leak audit (fault and healthy data come from the identical generation path) and the
      G0 trivial-cue audit.
12. **Determinism, replay and forks.** Bitwise replay; snapshot, restore and continue; forks with common random
    numbers (CRN): changing an order does not perturb the exogenous future. What a consumer can rely on.
13. **Behaviour of the data.**
    - The real-data behaviour the layer is built to reproduce: a summary of `reference/behavioural_targets.md`.
    - The B1–B9 battery and the real-vs-real pass rule.
    - **Current validation status, stated honestly:**
      - proved: determinism and forks; the texture noise ceiling on real flights; engine–FADEC small-signal
        causality; subsystem tests; data-path decode;
      - **not yet proved:** the B1–B6 battery on synthetic flights; fan–core and EGT timing; cross-engine
        structure; fault signatures at fleet scale; the archive-2 gate.
      - Take this from `docs/build_status.md`, `docs/build_gates/E1_verifier_report.md` and the MF1-D README, with
        their dates.
14. **Stability and change policy.**
    - What is frozen (contract 0.1.0, hashes).
    - What will change: additive 0.2.0 recording/sink id; dictionary updates; the channel coverage
      classification; `events.*` through the full path.
    - Semver rules; migration notes.
    - Data availability milestones: first full sortie; skeleton milestone; calibrated fleet datasets. Give these as
      milestones, not dates.
15. **Known limitations and assumptions.** A summary, with a pointer to `reference/assumptions.md` (PROXY items
    and their replacement routes).
16. **Glossary** of every domain term used, for example:
    - engine: N1, N2, EGT/T5, FF/Wf, PLA, PS3, A8, VG, AB, IRP/MIL;
    - avionics and systems: FADEC, DFCC, ECMS, HUMS, BIT/PBIT/CBIT/IBIT, LUI, TAC, LRU, 1553, ARINC 429, Ch10,
      TMATS, CWS, OAC;
    - maintenance and operations: NAMP, S5000F, AOG, NMCS/NMCM, CAG, sortie, tail, CRN.
17. **File index** of the folder.

Write for engineers new to aviation, in clear language. Cite the source file and section for each fact (for
example "architecture §12, AD-45"). Do not invent values; anything not in the sources is "not specified".

## Safety

- **Restricted material:**
  - Do **not** copy `reports/`, `research_notes/` (including `parameter_inventory.csv`) or anything under
    `research_sources/`.
  - Never write a restricted value (report Appendix A1).
  - Extend the restricted-value guard to scan `solution_context/`, and show it passes.
- **Reserved data:** never read `research_sources/datasets/dashlink_tail687/raw2/`.
- **No look-ahead or truth:** examples exclude `labels.truth` entirely.

## Acceptance

| ID | Criterion |
|---|---|
| A1 | `make solution-context` regenerates the folder byte-identically, twice (show the sha256 of `MANIFEST.json` both times) |
| A2 | `tests/unit/test_solution_context.py`:<br>• every manifest file exists with a matching sha256;<br>• the **consumer-facing artefacts** (`contract/`, `dictionary/`) equal their current sources, so a contract or dictionary change must regenerate the kit in the same commit;<br>• `reference/` and `modules/` are **snapshots** at the manifest commit (the coordinator regenerates them at milestones), so the test checks only their manifest hashes, which keeps parallel agents editing `docs/assumptions.md` unblocked;<br>• every example validates against its topic's schema;<br>• no `labels.truth` content anywhere in the folder;<br>• the README's generated tables equal a fresh generation from the current contract |
| A3 | The restricted-value guard scans `solution_context/` and passes |
| A4 | The README covers sections 1–17 and contains no solution strategy. Self-check with a grep for words like "recommend", "should use", "model choice"; quote any hits and justify each |
| A5 | `set -o pipefail; make check` green |

## Report (final message)

- The folder tree.
- The manifest summary (versions, hashes, commit).
- Acceptance evidence.
- Anything in the sources that was unclear or contradictory, as findings.
- Commits on `wp/solution-context`, clean `git status`. Do not push or merge.
