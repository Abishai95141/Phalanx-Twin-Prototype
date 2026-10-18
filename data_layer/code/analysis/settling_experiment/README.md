# Phalanx settling experiment

This experiment tests whether residual texture learned from one proxy aircraft makes synthetic recorder
data as hard to tell from real data as one real tail is from another. It follows `PREREGISTRATION.md`,
which is binding. Departures are listed in `DEVIATIONS.md`, and the results are in `REPORT.md`.

## Inputs (data are parsed only, never executed)

| Input | Path | Access |
|---|---|---|
| Tail 687, archive 1 (651 MAT files) | `/Users/abishaikc/Phalanx/research_sources/datasets/dashlink_tail687/raw/mat/` | read |
| Tail 652, archive 8 (180 MAT files) | `/Users/abishaikc/phalanx/data/raw/dashlink_tail652/extracted/` | **read-only** |
| Earlier texture analysis | `/Users/abishaikc/Phalanx/analysis/dashlink_texture/` | reused unchanged: `dlio.py`, `common.py` and `results/` (eligible flights, LSBs, sentinels, clock checks) |

SHA-256 hashes of both archives, all 491 MAT files used, the reused tables and code, and the
pre-registration are in `results/manifest.json`.

## Environment

aeon's MiniRocket needs numba, which needs numpy ≤ 2.3. The existing `.venv` (numpy 2.5.4) is left
untouched, so this experiment uses a separate environment:

```
uv venv /Users/abishaikc/Phalanx/.venv-settling --python 3.14     # CPython 3.14.6 (same interpreter as .venv)
uv pip install --python /Users/abishaikc/Phalanx/.venv-settling/bin/python -r requirements.txt
```

## Exact commands (in order)

Run every script with `-I` (isolated mode), from this directory, and pass data paths as arguments.
Wall-clock times are from an Apple-silicon laptop with 10 cores.

```
cd /Users/abishaikc/Phalanx/analysis/settling_experiment
PY=/Users/abishaikc/Phalanx/.venv-settling/bin/python
M687=/Users/abishaikc/Phalanx/research_sources/datasets/dashlink_tail687/raw/mat
Z687=/Users/abishaikc/Phalanx/research_sources/datasets/dashlink_tail687/raw/Tail_687_1.zip
M652=/Users/abishaikc/phalanx/data/raw/dashlink_tail652/extracted
Z652=/Users/abishaikc/phalanx/data/raw/dashlink_tail652/Tail_652_8.zip
TEX=/Users/abishaikc/Phalanx/analysis/dashlink_texture/results
SYN=/Users/abishaikc/Phalanx/research_sources/settling_synthetic          # gitignored, regenerable
FEA=$SYN/features
$PY -I src/s01_splits.py      $M687 $M652 $TEX results 8          # splits.csv (seed 20261014) -- first
$PY -I src/s02_manifest.py    $Z687 $M687 $Z652 $M652 $TEX results # manifest.json (SHA-256)
$PY -I src/s03_mechanism.py   $M687 $M652 $TEX results 8          # P1-P5; decisions from 687-CAL (~1 min)
$PY -I src/s04_fit.py         $M687 $TEX results 8                # L0..L6, L6', T2 prior on 687-CAL (~6 min)
$PY -I src/s05_synth.py       $M687 $TEX results $SYN 8           # 24 variants x 229 TEST flights (~40 min, 10 GB)
$PY -I src/s06_features.py    $M687 $M652 $TEX results $SYN $FEA 8 # features of 6,513 files (~1.5 h)
$PY -I src/s07_gate0.py       $FEA results                        # Gate 0 (trivial-cue audit)
$PY -I src/s08_discriminate.py $FEA results 'sim_.*_primary|sim_[^_]*_[^_]*_(eng|vrtg)|tail.*|temporal.*' --perm-d2 PERM
$PY -I src/s09_decide.py      results                             # decision rules -> verdicts.json
$PY -I src/s10_ablation.py    $FEA results sim_T1_L6_eng          # and sim_T2_L6_eng, sim_T1_L6_vrtg, tail_eng, tail_vrtg
$PY -I src/s11_figures.py     results figures
```

`PERM` is the number of permutations used for the window-level D2 classifiers. `REPORT.md` gives the
value used for each comparison; the reason is in `DEVIATIONS.md` §F. D3, D1 and the segment-level LR
always use 1,000 permutations.

## Scripts

| Script | Purpose | Main outputs |
|---|---|---|
| `src/config.py` | constants, seeds; `SeedSequence` streams keyed by (flight, channel, component) | — |
| `src/pipeline.py` | regimes from PH/WOW/ALT; truth = Butterworth-4 `sosfiltfilt` of the cleaned signal; lattices; windows | — |
| `src/s01_splits.py` | eligibility rule, 40/60 split of 687, 652 eligibility | `results/splits.csv`, `results/inventory_652.csv` |
| `src/s02_manifest.py` | input hashes and package versions | `results/manifest.json` |
| `src/s03_mechanism.py` | P1–P5: per-flight Δ, slot phases, folded profiles, window fits, clock-word Δ, digital stale reads | `results/mechanism_*.{csv,json,npz}` |
| `src/texture_model.py` | the generator: levels L0–L6, L6′, arm T2 | — |
| `src/fitstats.py` | residual moments shared by fitting and calibration | — |
| `src/s04_fit.py` | CAL-only fit and simulation-based calibration | `results/model_params_<fc>.json`, `results/fit_report_<fc>.json` |
| `src/s05_synth.py` | synthetic MAT files: copy of the real file with only the group arrays replaced (original dtype) | `$SYN/<arm>_<level>_<fc>/*.mat`, `results/synthetic_manifest.json`, `results/t2_virtual_tail_biases.json` |
| `src/features.py`, `src/s06_features.py` | D1/D2/D3 inputs and Gate-0 metadata via `dlio.load_flight` | `$FEA/<label>/<flight>.npz`, `$FEA/names.json` |
| `src/s07_gate0.py` | metadata-only classifier | `results/gate0.json` |
| `src/learn.py` | grouped CV (5×3), flight scores, bootstrap, permutations, kernel ridge | — |
| `src/s08_discriminate.py` | D1, D2 (LR, GB on 64-s, 300-s and segment features), D3 (MiniRocket) | `results/disc/<comparison>.{json,npz}` |
| `src/s09_decide.py` | AUC_x, joint bootstrap, section-6 rules, f_c sensitivity, L6 vs L6′ | `results/verdicts.json`, `results/auc_table.csv`, `results/decision_table.md` |
| `src/s10_ablation.py` | feature-family and channel-family ablation; D3 input ablation | `results/ablation/<comparison>.json` |
| `src/s11_figures.py` | figures | `figures/*.png` |

## Model specification (fixed on 687-CAL before any TEST synthesis)

The full definitions are in the docstrings of `src/texture_model.py` and `src/s04_fit.py`, with the
clarifications in `DEVIATIONS.md` §D. In brief:

| Level | Content |
|---|---|
| L0 | iid Gaussian, with σ per channel and regime |
| L1 | Adds the recording lattice (N1/N2 0.03125 %, EGT 0.5 °C, FF 8 lb/h, VRTG float32 code map) |
| L2 | Adds AR(1) noise in the residual band, with a 4-engine common-mode split |
| L3 | Adds power-bin and per-segment variance multipliers |
| L4 | Adds a heavy-tail scale mixture of the innovations |
| L5 | Adds validity gating, glitch words and episodic freezes |
| L6 (FULL, T1) | Adds VRTG missingness from clock-domain slip: Δ drawn from the CAL per-flight values (median 910.5 ppm), w = 22.5 ms (0.18 of a beat cycle at 8 Hz), p = 0.148, random phase. Digital channels are unchanged because P4 was refuted. |
| L6′ | L5 plus the old periodic Gilbert–Elliott model: Np = 1,096 samples, bad-state duration taken from the CAL burst durations, p_bad = 0.158, p_good = 2.3e-5 |
| L7 (FULL, T2) | L6 applied to truth_common + b_k. b_k comes from one virtual aircraft drawn from the CAL fleet prior; its parameters are in `model_params_primary.json` under `fixed.t2`. |
