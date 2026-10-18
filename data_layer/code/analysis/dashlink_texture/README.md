# DASHlink Tail 687 measurement-texture analysis (Phalanx)

Empirical characterisation of recorded flight-data "texture" (rates, LSBs, sentinels/dropouts,
stuck values, timing, residual statistics, four-engine spread, transients) from NASA DASHlink
"Sample Flight Data", **Tail 687, first archive only** (`Tail_687_1.zip`).
Results feed `research_notes/Virtual fighter telemetry layer research/empirical_dashlink_texture.md`.

## Data

* Source: <https://c3.ndc.nasa.gov/dashlink/resources/664/> (Flight Data For Tail 687; licence "N/A",
  no login required). File: <https://c3.ndc.nasa.gov/dashlink/static/media/dataset/Tail_687_1.zip>
* HEAD on 2026-10-13: `Content-Length: 837837074`, `Last-Modified: Wed, 29 Jan 2014 23:48:30 GMT`.
* SHA-256 of the downloaded zip: `8a8b3f60e53e08fd085edb89ce7266a4c0b745831f6f88f5babfaac70f8f04a5`
  (also in `results/extract_report.json`).
* 651 MAT-v5 files (one per record) extracted to
  `research_sources/datasets/dashlink_tail687/raw/mat/` (untrusted data; only parsed with
  `scipy.io.loadmat`, never executed). 10 files with suffix `_1` are byte-identical to their twin
  except `DATE_DAY`; they are excluded from all statistics except the raw inventory.

## Environment

```
uv venv /Users/abishaikc/Phalanx/.venv          # CPython 3.14.6
uv pip install --python /Users/abishaikc/Phalanx/.venv/bin/python -r requirements.txt
```
`requirements.txt` pins numpy 2.5.4, scipy 1.18.1, matplotlib 3.11.2 (+ their dependencies).
All scripts are run with the venv interpreter in isolated mode (`-I`), from this directory,
with data paths passed as arguments.

## Exact commands (in order)

```
cd /Users/abishaikc/Phalanx/analysis/dashlink_texture
PY=/Users/abishaikc/Phalanx/.venv/bin/python
RAW=/Users/abishaikc/Phalanx/research_sources/datasets/dashlink_tail687/raw
FIG="/Users/abishaikc/Phalanx/research_notes/Virtual fighter telemetry layer research/figures/dashlink"
mkdir -p results "$FIG"
$PY -I extract.py $RAW/Tail_687_1.zip $RAW/mat > results/extract_report.json
$PY -I inventory.py        $RAW/mat results 8      # per-flight + per-parameter metadata, all 651 files
$PY -I param_table.py      results                 # one row per parameter (186)
$PY -I dropouts.py         $RAW/mat results 8      # sentinels, co-occurrence, sibling-stuck runs
$PY -I recorder_checks.py  $RAW/mat results 8      # frame counter, sync/identity words, GMT, discretes, skews
$PY -I sample_flights.py   results 40 687          # eligible set + stratified sample (seed 687)
$PY -I texture.py          $RAW/mat results "$FIG" # steady-window residual texture (40 sampled flights)
$PY -I engines.py          $RAW/mat results "$FIG" 8   # 4-engine experiment, cross-sensor, corrected params
$PY -I corrected_exponents.py results              # theta-exponent scan for EGT / FF corrections
$PY -I transients.py       $RAW/mat results "$FIG" 8   # throttle steps, time constants, stale samples
$PY -I flight_level.py     $RAW/mat results "$FIG" 8   # durations, phases, rainflow throttle/N1 cycles
$PY -I dropout_bursts.py   $RAW/mat results 8      # burst / periodicity structure of dropouts
$PY -I make_tables.py      results                 # markdown tables used in the notes
```
Total run time on an Apple-silicon laptop with 8 workers: about 15 minutes.

## Scripts

| Script | Purpose | Main outputs (`results/`) |
|---|---|---|
| `dlio.py` | MAT loader, filename parser, LSB estimator, run-length helpers | — |
| `common.py` | steady-window detection, sentinel cleaning, SG detrend, ACF, Allan, PSD | — |
| `extract.py` | safe extraction (basename-only, name-pattern filter) + SHA-256 | `extract_report.json` |
| `inventory.py` | per flight x parameter: rate, dtype, n, range, LSB, grid regularity, repeats, constant runs, spikes, sub-frame change pattern | `inventory_flights.csv`, `inventory_params.csv`, `param_meta.csv` |
| `param_table.py` | aggregate to one row per parameter | `param_table.csv` |
| `dropouts.py` | global-min/max sentinel occurrences, isolation, phase rates, frame position, cross-parameter co-occurrence, sibling-referenced stuck runs | `dropouts_*.csv/json` |
| `recorder_checks.py` | frame counter, sync & identity words, GMT clock, discrete polarity, discrete event lags, inter-channel skews, duplicate content | `recorder_*.csv/json` |
| `sample_flights.py` | eligibility + stratified random sample | `eligible_flights.csv`, `sample_flights.csv` |
| `texture.py` | residual metrics per steady window; heteroscedasticity by phase / N1; spectral lines | `texture_*.csv`, `hetero_*.csv`, `texture_spectra.npz` |
| `engines.py` | offsets, Grubbs-type independent / common-mode variance, offset drift, cross-sensor correlation & lags, corrected-parameter collapse | `engines_*.csv` |
| `corrected_exponents.py` | best theta exponent for EGT and FF corrections | `corrected_exponent_scan.csv` |
| `transients.py` | PLA step detection, FOPDT fits, t10/t50/t90, stale-sample fraction | `transients_*.csv` |
| `flight_level.py` | record/airborne durations, PH phase times, rainflow PLA / N1 cycles | `flight_level*.{csv,json}` |
| `dropout_bursts.py` | Fano factors, burst durations, periodicity, Gilbert-Elliott-style parameters | `dropout_bursts.csv` |
| `make_tables.py` | markdown tables | `tables_*.md` |

## Determinism

* Sample: 40 flights, strata = {Mar-May, Jul, Aug, Sep 2001} x record-duration tercile,
  proportional allocation with minimum 2 per stratum, `numpy.random.default_rng(687)`.
  List in `results/sample_flights.csv` (and in the notes).
* Everything else is deterministic (no randomness). Multiprocessing only parallelises per-flight
  work; results are aggregated in file order.

## Method parameters (documented choices)

* Detrending: Savitzky-Golay, 30-s window, polynomial order 2 (`common.SG_SECONDS`).
* Steady windows: see `common.regime_windows` docstring (cruise 300 s with autothrottle trim
  allowed; climb 120 s; ground idle 120 s with per-engine running check).
* Sentinel = parameter's archive-wide min or max value; "isolated" = both neighbours differ by more
  than max(10 LSB, 5 x robust sigma of first differences).
* Sibling-stuck rule: one engine constant >= 30 s while all three siblings move >= 5 LSB, airborne.
* HF noise estimator for heteroscedasticity: sqrt(mean(d2x^2)/6) on 30-s blocks (0.5 % tails trimmed).
