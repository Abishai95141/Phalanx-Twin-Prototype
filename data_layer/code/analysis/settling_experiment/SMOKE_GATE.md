# Gate 0 smoke test (n = 60): FULL synthetic vs real 687-TEST, primary f_c

This is a run-order and sanity check, not the binding gate.
- With 60 flights it can only catch gross cues: a pass is necessary, not sufficient.
- The binding Gate 0 is `src/s07_gate0.py` on all 229 flights (`results/gate0.json`).

| | |
|---|---|
| Sample | `numpy.random.default_rng(20261014).choice(sorted 687-TEST, 60)`, listed in `results/smoke_flights.csv` |
| Data | v2 synthetic files, after the Gate-0 v1 fixes C3 and C4 in `DEVIATIONS.md` |
| Features | written to `research_sources/settling_synthetic/features_smoke/` |
| Full results | `results/gate0_smoke.json` |

| Variant | Metadata LR AUC [95 % CI] | Metadata GB AUC [95 % CI] | Any single feature with AUC < 0.2 or > 0.8? | Pipeline-only metadata (counts, length, dtype, NaN, float32) |
|---|---|---|---|---|
| T1-L6 (FULL, T1) | 0.952 [0.922, 0.981] | 0.961 [0.930, 0.984] | none | AUC 0.5: all identical |
| T2-L6 (= L7, FULL T2) | 0.948 [0.915, 0.978] | 0.953 [0.917, 0.981] | none | AUC 0.5: all identical |
| T1-L6′ | 0.935 [0.895, 0.971] | 0.964 [0.934, 0.987] | none | AUC 0.5: all identical |

## Call

- **No gross cue.** No single metadata feature reaches univariate AUC < 0.2 or > 0.8.
  - The Gate-0 v1 cues are gone: N1 first/last sample, which was 0 against 1.78 %, and the edge transients.
  - So the full v2 feature extraction was not stopped.
- **The full pre-registered metadata set still separates FULL from real (AUC about 0.95). The cue is texture, not pipeline.** The separating features are, in order:
  1. Mean trailing-zero count of the float64 mantissa, EGT_1–4. Univariate AUC 0.26–0.27; the counts differ in every flight.
  2. The same statistic for N1/N2 and VRTG.
  3. VRTG fractional-lattice sign bins (AUC 0.40/0.60).
- **All of these measure which lattice codes are used.**
  - Real EGT never uses codes ≡ 1, 4 or 7 (mod 8) of the 0.5 °C grid. The native EGT step is ≈ 0.8 °C, re-rounded to 0.5 °C.
  - Synthetic EGT uses all eight residues.
  - Real N1 and N2 over-use some residues (for N1_1: 0.16 at residues 1 and 6 against 0.115 elsewhere), which points to a similar double quantisation.
  - The L1 lattice, a uniform LSB taken from `param_table.csv`, does not model this. It is a quantiser (texture) deficiency, not a file-pipeline artefact.
- The pre-registration says to fix the pipeline, not the model, so this is reported as a finding and the model is not changed. It feeds the diagnosis in `REPORT.md`, under component 1: the word quantiser needs the native step.
- Expected binding outcome: the full 229-flight Gate 0 will most likely also fail on the full feature set for the same reason, and pass on the pipeline-only subset. `REPORT.md` states the Gate-0 status next to every verdict.
