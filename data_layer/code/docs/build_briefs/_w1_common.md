# Wave 1 common rules (read after `_common.md`, before your WP brief)

Wave 1 builds every module to v1 fidelity **behind fixed interfaces**. Nine agents work in parallel; W2.1 wires
everything together. Your module must work when plugged in, so these rules matter more than in Wave 0.

## 1. Read, in order

1. `docs/build_briefs/_common.md`: all rules there still apply.
2. This file.
3. `docs/build_briefs/W1_interfaces.md`: **frozen ports**. Implement your side exactly.
4. Your WP brief.
5. `docs/architecture.md`: your module sections in §6, plus §5.5/AD-36, §7, §8, §9–§11 as relevant, AD-22, AD-35…AD-40.
6. `src/phalanx/core/README.md`: kernel API, `ModuleBase`, `StreamDecl`, snapshots.
7. `docs/build_status.md`: the "Carry-forward into the W1 briefs" section. These are measured lessons from Wave 0.
   Also read `docs/behavioural_targets.md`: the real-data behaviour (correlations, lead–lag, time constants, causal structure, physical laws) your module must help reproduce, and the round-2 failures it must not repeat.
8. Grep the research report and notes for your subsystem before every modelling decision.

## 2. Module implementation rules

- **Contract:** subclass `phalanx.core.module.ModuleBase`.
  - Declare `ports_in` / `ports_out` (names, SI units, shapes, rates) **matching `W1_interfaces.md`**, plus `state_schema`, `streams` (`StreamDecl`, AD-37), `rate` (or `None`) and `emits_events`.
  - Publish `src/phalanx/<pkg>/ports.py` with `PREFIX` and `ports(n_engines=1) -> (inputs, outputs, bindings)`.
    - Port names are lowercase snake_case.
    - Catalogue keys are `<prefix>.<port>`. The authoritative catalogue is `configs/interfaces/w1_ports.yaml`.
    - **`tests/integration/test_interface_conformance.py` must pass for your module with no skip.** It checks units (pint-equivalent), dtypes, shapes for n_engines 1 and 2, missing outputs, uncatalogued outputs and unbound inputs.
    - Controller lane inputs bind as `lane.<channel_id>` and carry SI values (`W1_interfaces.md` §1).
- **Kernels (AD-22, Numba):**
  - Continuous dynamics live in `@njit` (fastmath off, `cache=True`) pure functions over flat arrays: float64 and int64 state vectors with name→index constants, a flat float64 parameter vector, tables as NamedTuples, and RNG blocks passed in as arrays.
  - Ship a **pure-NumPy reference** of each kernel. A test asserts that kernel and reference agree **bitwise**, over a block and per step.
  - **Copy the worked example:** `src/phalanx/core/example_kernel.py` with `core.layout.StateLayout` / `ParamLayout`. The reference is the kernel's own `py_func`, so they are bitwise equal by construction, and it is complex-step safe. Clock-domain outputs use `core.sampling.sample_ports` / `samples_for_steps` (value, `_t`, `_n`, `_first` ports). Never use NaN padding; validation mode rejects NaN/inf at every port.
  - **Usage mode:** event-only systems automatically use `System(event_jump=True)`.
  - `step_block` must equal repeated `step` bitwise (AD-36).
  - Avoid known non-conformities: `math.tanh` vs `np.tanh`, and `np.sum` vs sequential add. Use identical primitives in the reference and the kernel.
- **Complex-step safety:** this applies to calibrated kernels (M07 dynamics, M08 loop gains, M09 hydraulics/fuel/thermal, M05 actuators, M12 sensor dynamics).
  - Comparisons and branches use `.real`.
  - No `abs`, `min` or `max` on complex values without a complex-safe helper.
  - Include a test: complex-step derivative vs central finite difference for a few parameters.
- **Parameters:** every number lives in `configs/tejas/params/<MODULE>.yaml` (format `phalanx.params/1`; loader `phalanx.dictionary.params.load_params`), with units, tag, source, and a sweep plus `assumption_id` for ASSUMPTION.
  - Tables go in `configs/tejas/params/<MODULE>/*.csv`.
  - `tests/unit/test_dictionary_params.py::test_repo_param_files_all_valid` enforces this.
  - **Dictionary-change protocol:**
    - `configs/tejas/dictionary/`, `docs/contract/` and the contract spec are **coordinator-owned** in Wave 1. Do not edit them.
    - If you need a channel, range, rate, unit or code-table change, put it in your report: give the channel, the field, the new value, its evidence tag and source, and why.
    - The coordinator batches the accepted changes into **one dictionary release per merge batch** (version bump, `releases.yaml`, `make contract-docs`). This keeps the hash stable while you work.
- **Determinism audit:** `tools/audit_static.py` fails on these (allow a line only with `# audit: allow Rn <reason>`):
  - global or legacy RNG;
  - unseeded generators, bit generators or SeedSequence (including via from-imports);
  - stdlib `random`;
  - wall-clock reads (including `from time import ...`);
  - builtin `hash()`;
  - seed arithmetic;
  - OS entropy or process identity (`os.urandom`, `uuid4`, `secrets`, `id()`, `getpid`).

  Iterating a `set` of strings is process-order-dependent and not statically detectable: sort first.
- **Randomness:** only through `StreamDecl` and the core RNG service, keyed per `W1_interfaces.md` §1. CRN across forks must hold for your streams; include a test.
- **Hidden truth:** health, biases and fault states never reach CIR or consumer topics.
- **Proxy readiness:** engine-side code is vectorised over `n_engines`. Platform specifics come from parameter files, never from code constants. W2.4 adds a `configs/proxy_dashlink/params/` set.
- **Neighbours:**
  - Code only against `W1_interfaces.md` ports.
  - In unit and integration tests you may build **test fixtures** at your module boundary, e.g. a first-order plant feeding your controller. These must be clearly labelled `TEST FIXTURE`, live under `tests/`, and never be imported by `src/`.
  - Real cross-module coupling is W2.1's job.
- **Acceptance tests that need calibration** (C1–C28, V1–V12 values, usage gates fed by real data) can't pass in W1:
  - implement them now with their targets and tolerances;
  - if they fail before W2.3 calibration, mark them `@pytest.mark.xfail(strict=True, reason="W2.3 calibration: <what>")`;
  - list every one in your report.

  Structural and physical-law tests (balances, signs, invariances, monotonicity, determinism) must **pass** in W1.

## 3. Process

- **Owned paths:** given in your brief; usually `src/phalanx/<pkg>/`, `configs/tejas/params/<MODULE>.yaml` plus its folder, and `tests/*/test_<pkg>_*.py`.
  - Assumption rows go in **your WP section** of `docs/assumptions.md` (pre-created).
- **Test runtime:** `make check` is now ~2.5–5 min, and nine agents share a 10-core machine.
  - During development, run your own tests (`pytest -q tests -k <pkg>`).
  - Run the full `make check` before each commit you'll report, and before your final report.
  - Mark tests longer than ~20 s `slow`. Keep them out of `make check` but run them yourself and report them.
- **Main moves while you work.** Merge `main` (no rebase) before your final report and make sure `make check` passes on the merged tree.
- **Report additionally:**
  - your published ports, and any mismatch with `W1_interfaces.md`;
  - every `xfail(strict=True)` calibration-pending test;
  - every parameter tagged ASSUMPTION with its sweep;
  - what W2.1 must do to wire you in.
