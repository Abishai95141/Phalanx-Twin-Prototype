# E1-HY: E1 hygiene (evidence tags, xfail honesty, weak acceptance tests, restricted-value guard)

**Context.** The E1 verifier returned GO-WITH-CONDITIONS (`docs/build_gates/E1_verifier_report.md`; read §2, §3
and §7). This work package closes the hygiene list. It runs in parallel with E1-MF, which owns the conformance
gate, the `util.bus_v` fix, the index-map ties, the M07 adapter test, the M08 property test, the M14 leak test,
the realised usage gates, the M11 latency test and the U8 event tests. **Do not touch those.**

**Owned paths:**
- `configs/tejas/params/*.yaml` (tags, sources, sweeps, `proxy` flags; **no value changes** unless an item says
  so);
- `docs/assumptions.md`;
- the existing W1.1, W1.2, W1.3a and W1.8 test files named below;
- `tests/unit/test_dictionary_restricted_guard.py`;
- code comments and PROXY labels in `src/` for the code constants named below.

## Items

1. **Evidence tags (§7).** Fix each, citing the evidence:
   - M05 `servo_wn`: ASSUMPTION with a sweep, matching A-W1.2-20. Report any design consequence.
   - M08 `heal_frames`: name the F100 DEEC/ADIA donor, and note the change from a 40 ms frame base to 60 Hz.
   - The nine M08 on-board-model tables: `proxy: true`.
   - M10 `bias_speed_pct`: TRANSFER (proxy N2, n=4).
   - `faults/graph.yaml`: the 32 accident-board edges become TRANSFER.
   - M13 EGT/FF noise and ceilings: ASSUMPTION when applied to Tejas, per the M13 header.
   - M03 USSA constants: standard/TRANSFER, as M12 tags them.
   - M02 `engine_start`: about 40 s per the evidence, or justify 45 s; add a sweep.
2. **Conflicts.** Log the ones that are claimed but not logged:
   - the M15/M16 clock offset σ: 20 ppm vs R:563 vs R:1036 vs the 910 ppm architecture value. State which value
     applies where, and why.
   - W1.8 `aog_bin_share`: the "conflict logged" claim is false, and 38 % of demands are unaccounted for. Log the
     conflict, or fix the accounting with evidence.
3. **Unlabelled constants.**
   - M11 `usage_detection_sigma`: a PROXY label in the code.
   - The M02 isothermal scale height: a parameter, or a labelled constant with its source.
   - The M14 `t_utc` PROXY needs its own `docs/assumptions.md` row. The stated replacement route (W1.7) does not
     exist; name the real one (W2.2, M17 `events.*`).
4. **Xfail honesty (§3).**
   - Put the measured number in each reason that lacks it: C4, C5, C6, C17; V7 (the ARI sign at M0.7/M1.3); the
     two W2.6 priors; the VG rows.
   - Fix the stale skip reason at `tests/*/test_engine_golden.py:586`.
   - **VG rows:** a Muir-convention and model-sign question, not calibration. Write a proposed decision-register
     entry in your report; the coordinator records it.
   - **C11:** compare like with like (steady vs steady), or reclassify it as a test-design defect with the reason.
   - **MIL-310:** add `raises=` and name the data owner.
5. **W1.1 A3 non-circular PSD.**
   - Take the targets from the **continuous-time analytic** spectra, independent of the kernel's discretised
     matrices.
   - Tighten the thresholds with a stated statistical justification, so that a 2×τ mutant fails clearly.
   - Show the mutant run.
6. **W1.1 A5 and W1.2 V4 bands back to the brief.**
   - The bands are: AB 4–5 per FH; ≥IRP 17–20 %; V4 0.2–0.3 s.
   - Where the measurement fails at the brief's band, use a **strict xfail with the measured number and the
     resolving wave**. A failure is a finding; do not widen the band.
7. **W1.2 A3 nonlinear margins.** Add a nonlinear-loop margin check of the FCS (gain and delay injection in the
   nonlinear simulation) at a minimal stated set of flight points. Compare it with the linear design margins.
8. **W1.8 CRN variance (`test_fork_crn.py:117`).** The paired-variance assertion passed with CRN broken. Replace
   it with an F-test bound at a power-justified n, and show it fails with CRN broken.
9. **Restricted-value guard.**
   - Extend `SCAN_ROOTS` to `docs/` (all of it: briefs, gates, audit log), `analysis/` (text and code; skip
     binaries and data), `tests/` and `tools/`. `research_notes/` stays unscanned: it is internal evidence.
   - Run it and review every hit by hand.
   - If any value remains after the coordinator's 2026-10-15 redaction of four files, **redact it in place**
     (`[value redacted: restricted, report App. A1]`) and list it in your report: file, line and parameter, never
     the value.
   - The negative controls must still pass.

## Acceptance

- `make check` is green with `set -o pipefail`.
- Every changed tag cites its evidence. The mutant and negative-control runs of items 5, 8 and 9 are shown.

## Report (final message)

- Item-by-item outcome.
- New xfails, with their numbers.
- The VG decision-register proposal.
- Any redactions (location only).
- Commits on `wp/e1-hy`, clean `git status`. Do not push or merge.
