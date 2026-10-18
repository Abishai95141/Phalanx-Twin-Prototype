# Tests

Tiers: `unit`, `property`, `golden`, `integration`, `statistical`, `fork` (markers in `pyproject.toml`).
`make check` runs everything except `slow` and `data`. Shared rules: `docs/build_briefs/_common.md` §2.

## Property tests (Hypothesis policy, E1-MF)

1. **Deterministic in `make check`.** `tests/conftest.py` loads the `phalanx-check` profile: `derandomize=True`
   (no example database, so no run depends on an earlier one), `deadline=None` (no wall-clock check), and
   Hypothesis' pool of literals mined from imported non-test modules switched off, so a test's examples are a
   function of the test and the pinned Hypothesis version only, whatever else the run imports. A test's own
   `@settings` override only the fields it names.
2. **Exploration is separate.** `PHALANX_HYPOTHESIS_PROFILE=phalanx-explore` draws fresh random examples (with
   the example database). Use it to look for counterexamples; never to gate a merge.
3. **Every counterexample found is pinned** as an `@example(...)` on the property, with its exact values:
   - fixed: a plain `@example` (a regression test from then on);
   - known and owned, not fixed: `@example(...).xfail(raises=<specific exception>, reason=<measured value,
     mechanism, owning WP>)`. Hypothesis treats it as strict: once fixed it fails until the `.xfail` is
     removed. Raise a specific exception class per failure kind so a different failure is not mistaken for
     the pinned one (e.g. `PS3TransientOver` in `tests/property/test_fadec_limiter_property.py`).
4. **Report the sample.** State `max_examples` and the domain in the docstring; when a counterexample shows
   the property is false on part of its domain, map that region (a small grid is enough), record it in the
   docstring with the owner, and do not widen the bounds to pass.
