# E1: Wave 1 exit gate (independent verifier)

You are the **independent verifier** for the Wave 1 exit gate. You did not build any of it. Establish adversarially,
from evidence, whether Wave 1 (all M02–M22 modules at v1 fidelity behind frozen interfaces) is done, cohesive and
robust enough to integrate. Assume reports may be wrong; verify by running things.

## Rules

- **Read-only on the repo.** Work in your worktree at main HEAD.
  - Scratch goes in git-ignored `runs/e1/`.
  - Mutations only on a `git archive` copy.
  - Clean `git status` at the end.
  - Never push or merge.
- **Reserved data:** never read, list or load `research_sources/datasets/dashlink_tail687/raw2/`.
- **Tooling:** shared env `"$(git rev-parse --git-common-dir)/../.venv-build/bin/python" -I`; use `make check` with `set -o pipefail`.
- **Thoroughness:** no budget cap. Use minimal sufficient samples and state n.

## Read

- `RULES.md`
- `docs/build_plan.md` §4 (the W1 table and the E1 definition)
- `docs/build_status.md`, including the morning summary, carry-forward, dictionary batches and open decisions
- `docs/build_audit_log.md` (entries 41–110)
- `docs/build_briefs/_w1_common.md`, `W1_interfaces.md`, and every W1 brief
- `configs/interfaces/w1_ports.yaml` and `w1_events.yaml`
- `docs/architecture.md` AD-35…AD-50
- `docs/behavioural_targets.md`
- `docs/assumptions.md`
- every module README

## Verify

1. **E1 definition.**
   - All W1 acceptance tests pass.
   - Every module conforms to its interface.
   - `docs/assumptions.md` lists every PROXY.
   - No STUB remains except tracked integration stubs.
   - `make check` is green twice.
   - **Zero skips** in `test_interface_conformance.py` and `test_event_protocol.py`. Any skip is a finding.
2. **Acceptance coverage per WP.** For each W1 brief criterion, find the tests, run them, and judge whether each can fail.
   - List every strict xfail. Check that its reason states a measured gap and the wave that resolves it (W2.1/W2.3/W2.6, or a structural PROXY).
   - Flag any xfail that hides a W1 defect.
3. **Cohesion.** This is the core concern.
   - Port catalogue vs code: every catalogued signal has a producer, and every binding resolves.
   - Event catalogue vs code: the declared events are actually emitted and handled. Write a probe that instantiates modules and checks a sample of real emitted payloads against the catalogue, since the declarations alone missed one before.
   - RECORDED channels against the dictionary.
   - Clock consistency.
   - Units at every boundary.
   - List every remaining cross-module mismatch, including the AD-42…AD-50 W2.1 items. Say whether each is tracked.
4. **Wiring readiness probe.** From the published `ports.py` bindings alone, with no hand-wiring of signals, build a minimal closed loop and run 10 s at idle, then a PLA step:
   - M03 environment (or its replay) + M04 pilot (or replay) → M08 FADEC ↔ M07 engine;
   - M12/M13 FADEC lanes in-loop.

   Report every friction point and every place the bindings were insufficient. This informs W2.1.
5. **Determinism across modules.**
   - Fresh-process digest of the probe loop.
   - Snapshot mid-run → restore → continue, bitwise.
   - The static audit (R1–R8) is clean.
   - Spot-check `cache=False` on fused callers and the Numba stale-cache guard.
6. **Mutation testing.** Run at least 12 mutations on cross-module-relevant code, for example:
   - disturbance entry points;
   - event payload keys;
   - port units;
   - FADEC limiter selection;
   - M13 noise ceiling;
   - M18 order validation;
   - M10 bias vs deterioration separation;
   - M11 graph edge latency.

   Which survive `make check`?
7. **Evidence discipline.**
   - Spot-check at least 20 parameters across modules (at least 2 per WP) against the report and notes, including tags and sources.
   - **Check that no restricted value (report Appendix A1) appears in configs, src, docs/contract or briefs.** Known incident: a NATOPS-derived idle band was quoted in a brief and caught. Grep the briefs too.
8. **Behavioural readiness.** Report what the W1 module tests measured against `docs/behavioural_targets.md`:
   - N1–N2 achievable range;
   - FF→N2 lag sign and magnitude on M07+M08;
   - FF correlation signs;
   - noise ceiling;
   - usage gates.

   State honestly what is shown at module level and what remains for W2.4a.

## Report (final message)

- **Verdict:** GO / GO-WITH-CONDITIONS / NO-GO.
- An E1 checklist table with evidence (command plus output tail).
- An acceptance-coverage table.
- An xfail audit.
- A cohesion mismatch list (tracked or untracked).
- The wiring-probe friction list.
- A mutation table.
- An evidence table, including the restricted-value check of the briefs.
- A behavioural-readiness summary.
- **Must-fix before W2** vs **W2 entry items**.
- Clean `git status`.
