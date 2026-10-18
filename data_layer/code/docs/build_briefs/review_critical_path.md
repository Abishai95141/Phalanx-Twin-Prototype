# Adversarial pre-merge review: critical-path modules (W1.3a engine, W1.3b FADEC)

You are an **independent reviewer**. You did not build this module. Your job is to find what is wrong, shallow or
unproven **before** it reaches `main`. Assume the builder's report may be optimistic. Verify by running things.

## Rules
- **Read-only on the repo.** You work in a fresh worktree checked out at the builder's branch head.
  - Scratch work goes in a git-ignored folder (`runs/review/`).
  - Mutation experiments only on a `git archive` copy; never edit tracked files.
  - Never push or merge.
- **Reserved data:** never read, list or load `research_sources/datasets/dashlink_tail687/raw2/`.
- **Python:** use the shared env via `"$(git rev-parse --git-common-dir)/../.venv-build/bin/python" -I`.
- **Budget:** be thorough; there is no cap. State n for anything statistical.

## Read
1. `RULES.md` and `docs/build_briefs/_common.md`, `_w1_common.md`, `W1_interfaces.md`.
2. The module brief: `W1.3a_engine.md` or `W1.3b_fadec.md`.
3. `docs/architecture.md`: §6 M07/M08, §7, AD-04, AD-22, AD-31, AD-32, AD-34, AD-36.
4. `analysis/settling_experiment_round2/REPORT.md` §3 and §8. This is why the module exists: the open-loop deterministic model over-coupled the engines and inverted the lead–lag.
5. The builder's report, which the coordinator gives you, and the module README.

## Review questions (answer each with evidence)
1. **Physics fidelity vs the research.** For at least 10 parameters and structural choices, does each trace to the report or notes with the right tag?
   - Grep for every one.
   - Flag any number with no source, any `[DIRECT]` that is really a transfer, and any restricted value (report App. A1).
2. **Shallow proxies (RULES.md rule 2).** Is any coupled behaviour faked? Look for:
   - independent noise standing in for dynamics;
   - lookup outputs instead of states;
   - constant or linear placeholders;
   - disturbances added to outputs instead of entering the dynamics (AD-32);
   - a "closed loop" that is really open loop.

   Name file:line for each.
3. **The round-2 failure modes, re-tested.** Run the module, with the labelled test-fixture partner, at minimal sufficient n.
   - (a) Is within-engine coherence < 1 at high frequency?
   - (b) With n_engines = 2 and independent unit disturbances, is the cross-engine correlation well below 1?
   - (c) For W1.3b, with process disturbance only: does small-signal Wf lag N2 (negative FF→N2 lag)? With commanded PLA steps: does Wf lead?
   - Report numbers. Say whether the tests in the suite actually assert these things, or just print them.
4. **Determinism and kernel contract.** Check each:
   - Numba kernel = NumPy reference, bitwise;
   - `step_block` = repeated `step`;
   - snapshot → restore → continue is bitwise identical;
   - complex-step derivatives = central FD;
   - no static-audit escapes.

   Run each yourself.
5. **Interface conformance.** `test_interface_conformance.py` passes with no skip for this module. Check the units, shapes and bindings by hand against `configs/interfaces/w1_ports.yaml`.
6. **Test quality.** Run at least 8 mutations on the module's critical code:
   - signs, time constants, limiter selection, disturbance entry point;
   - complex-step-safe helpers, state indices.

   Which are caught by `make check`? A survivor is a finding.
7. **Calibration readiness (AD-34).** Does the transient-window API and the transient-weighted residual exist? Is it usable for W2.3/W2.4? Try it on a synthetic step with a known time constant and recover the time constant.
8. **Performance.** Measure µs/step for 1 and 2 engines, against the W0.6 0.79 µs/step workload.

## Report (final message)
- **Verdict:** MERGE / MERGE-WITH-FIXES / BLOCK.
- One table per question above, with evidence (command plus output tail).
- **Must-fix before merge** vs **can-fix in W2**, prioritised.
- `git status` clean at the end.
