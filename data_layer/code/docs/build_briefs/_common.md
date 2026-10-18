# Common rules for every build agent (read before your WP brief)

You are one of several agents building the Phalanx data layer in parallel. A coordinator (the main session)
reviews and merges your work. Your WP brief says what you own. These rules apply to all WPs and are not
negotiable. They repeat the binding `RULES.md`, which you must also read in full.

## 1. Consult the evidence before deciding

In this order:
1. `docs/architecture.md` (binding);
2. `reports/Virtual fighter telemetry layer research.md`: grep it, and quote the path because it contains spaces;
3. `research_notes/Virtual fighter telemetry layer research/`;
4. `analysis/*/` results.

**Precedence:** architecture > experiments > report > notes.
- If sources conflict, or the spec looks wrong, **report it**. Don't resolve it silently.
- If no source covers a choice you must make:
  - make the most defensible choice;
  - tag it;
  - add a row to your section of `docs/assumptions.md`;
  - list it in your report as a **proposed decision** (alternatives, and what would change it).

## 2. Robustness bar ("every build is robust")

- **No shallow proxies** (RULES.md rule 2).
  - Anything simplified is labelled `PROXY` in the code, has a test that exposes its limits, and has a row in `docs/assumptions.md`.
  - Mocks only at module boundaries inside unit tests.
- **Determinism** (RULES.md rule 5):
  - no global RNG, no stdlib `random`, no wall-clock reads, no builtin `hash()` for anything persistent, no seed arithmetic;
  - `tools/audit_static.py` enforces this, and a pytest fixture fails any test that touches the global RNG;
  - if you genuinely need a wall-clock read (benchmark timing only), annotate the line `# audit: allow R4 <reason>`.
- **Time:** int64 nanoseconds everywhere (AD-35). Truth step k is at `(k*10**9)//240` ns.
- **SI units** inside modules; units declared on ports.
- **Tests:** test what can break, not what is trivially true.
  - Every acceptance criterion in your brief maps to at least one named test.
  - Include property tests (hypothesis) for invariants, and negative tests that show a check actually fails when it should.
  - A test that cannot fail is a defect.
- **Minimal sufficient sample:** if a test uses data, use the smallest deterministic sample that answers the question. Record n and the reason in the test docstring or result file. Always sample → verify → scale.
- **Real data:**
  - read only;
  - pass paths as arguments or environment variables;
  - never execute anything from data directories.
  - **Tail 687 archive 2 (`research_sources/datasets/dashlink_tail687/raw2/`) is RESERVED. Never read it, list its contents or load it.**
- **Paths in worktrees:** you work in a git worktree, so git-ignored data is **not** in your checkout. Use
  absolute paths under the main repo for those:
  - `/Users/abishaikc/Phalanx/research_sources/...` (DASHlink data, round-2 synthetic outputs);
  - `/Users/abishaikc/Phalanx/.venv-settling` (the round-1/2 experiment environment, if you must run old code);
  - large `analysis/dashlink_texture/results/*.csv` intermediates.

  Tracked files (`docs/`, `reports/`, `research_notes/`, `analysis/`) are in your checkout.
- **Performance:** keep inner loops vectorised or compiled. Don't optimise prematurely; make it correct first.

## 3. Engineering conventions

- **Python environment:** the shared, pinned `.venv-build` at the main repo root. From your checkout:
  - `make check` must be green before you report. It runs lint, format check, the static audit and the non-slow tests.
  - `make fmt` formats your code.
  - Run Python as `"$(git rev-parse --git-common-dir)/../.venv-build/bin/python" -I ...`.
  - Tests import `phalanx` from `./src` of your checkout (pytest `pythonpath`).
  - Scripts outside `tests/` that need `phalanx` must insert their checkout's `src` into `sys.path` from `__file__`.
- **Dependencies:** don't edit `pyproject.toml` or `uv.lock`. If you need a package that isn't installed, stop and report it with the reason. The coordinator adds it.
- **Ownership:** edit only the paths your brief assigns. You may read anything in the repo.
  - **Shared files you may append to:** your own section of `docs/assumptions.md`.
  - Everything else outside your paths, including `docs/architecture.md`, `docs/build_*.md`, `RULES.md`, `pyproject.toml` and `Makefile`: propose changes in your report instead.
- **Code style:** typed (PEP 604), docstrings stating units and evidence tags, small pure functions, no hidden state.
  - Every module directory gets a `README.md`: purpose, interfaces, assumptions (tagged), validation criteria, known limitations.
- **Tests** go under `tests/<tier>/` with file names prefixed by your package (e.g. `tests/unit/test_core_rng.py`). Tiers: unit, property, golden, integration, statistical, fork. Use the pytest markers in `pyproject.toml`.
- **Git:**
  - commit on your worktree branch in small, focused commits with clear messages;
  - **never push, never merge, never rebase `main`**;
  - don't commit generated large files, data or anything under `research_sources/`.
- **Kaggle:** never run Kaggle upload or push commands. If you need batch compute, stage it and write the exact command into `kaggle_pending_cmds.txt` in your work folder.
- **Filesystem:**
  - read/write only inside the repo (your worktree), plus the main repo's `.venv-build`;
  - read-only `/Users/abishaikc/phalanx/data/raw/` if your WP needs it;
  - nothing else on this machine.

## 4. Report back (your final message)

1. **What you built:** files, and their public API with signatures.
2. **Acceptance criteria → tests:** a table with test name and PASS/FAIL, plus the exact `make check` tail output.
3. **Sample sizes** used, with the justification.
4. **Conflicts** found, and **proposed decisions** (alternatives, and what would change them).
5. **Assumptions and PROXY items** added.
6. **Known limitations and open items**, and what the next wave needs from you.
7. **Branch name and commit hashes.**

Report failures plainly. A failing test you couldn't fix is a finding, not something to hide. Never claim a check
passed without showing its output.
