# Phalanx settling experiment, round 2: model-in-the-loop behavioural fidelity

This experiment asks whether synthetic recorder data reproduce the real data's behavioural and causal structure as
closely as real data reproduce themselves across tails. The synthetic data come from a physics-structured engine
model (M-A) driven by real inputs, plus a sensor/acquisition texture (M-B) and an optional coupled discrepancy
layer (M-C).

- `PREREGISTRATION.md` is binding. Its §9 holds amendments A1–A8: the fallback holdout is triggered now; native
  steps; the M-B/M-C variance split; recorder effects; quick look; sensor-dynamics stage; physical unit variation;
  reporting both ways.
- Departures are in `DEVIATIONS.md`, the quick look in `results/QUICK_LOOK.md`, and results in `REPORT.md`.
- Credibility ceiling: NASA-STD-7009B Level 2 against proxy (airliner) data.

## Inputs (data are parsed only, never executed; every path is passed as an argument)

| Input | Path | Use |
|---|---|---|
| Tail 687 archive 1, 687-CAL (152 flights) | `research_sources/datasets/dashlink_tail687/raw/mat/` | **the only data used for fitting** |
| Round-1 splits, model parameters, native-step diagnostic, mechanism decisions | `analysis/settling_experiment/results/` | read-only |
| Round-1 code (`dlio.py`, `common.py`, `transients.py`, `pipeline.py`, `features.py`, `learn.py`, `s07_gate0.py`, `texture_model.py`, `fitstats.py`, `config.py`) and `analysis/correlation_check/corr_check.py` | — | imported read-only; SHA-256 in `results/frozen_models.json` |
| Tail 652 archive 8 (primary holdout, A1) | `/Users/abishaikc/phalanx/data/raw/dashlink_tail652/extracted/` | **read-only, Phase B only** |
| Tail 687 archive 2 (confirmatory holdout) | `research_sources/datasets/dashlink_tail687/raw2/` | fetch-log status only, until available |
| Synthetic files, features, development fits (regenerable, gitignored) | `research_sources/settling_round2_synthetic/` | outputs |

## Environment

Round 2 reuses the round-1 environment unchanged; no package was added (`requirements.txt`):

```
uv venv /Users/abishaikc/Phalanx/.venv-settling --python 3.14
uv pip install --python /Users/abishaikc/Phalanx/.venv-settling/bin/python -r requirements.txt
```

## Exact commands

Run from this directory, with `-I`.
- `R2_THREADS` sets the threads used by the M-A Jacobian (default 4).
- Times are on an Apple-silicon laptop with 10 cores.

```
cd /Users/abishaikc/Phalanx/analysis/settling_experiment_round2
PY=/Users/abishaikc/Phalanx/.venv-settling/bin/python
M687=/Users/abishaikc/Phalanx/research_sources/datasets/dashlink_tail687/raw/mat
M652=/Users/abishaikc/phalanx/data/raw/dashlink_tail652/extracted
RAW2=/Users/abishaikc/Phalanx/research_sources/datasets/dashlink_tail687/raw2
TEX=/Users/abishaikc/Phalanx/analysis/dashlink_texture/results
SYN=/Users/abishaikc/Phalanx/research_sources/settling_round2_synthetic
DEV=$SYN/dev

# 0. self-tests: numba PCHIP == scipy; fused kernels == numpy reference; B1 == corr_check  (results/log_selftest.txt)
$PY -I src/t01_selftest.py $M687 ../correlation_check

# 1. quick look (A5; development only; results/QUICK_LOOK.md documents the code state it ran with)
$PY -I src/q01_quick_look.py $M687 $TEX results 5 8

# 2. sample batch: fit on 20 CAL flights, synthesise 20 other CAL flights, dev battery
for V in S P; do $PY -I src/s02_fit.py $M687 $DEV/sample20_$V results/dev_sample20_fit_flights.txt $V 8 4 7 100; done
for V in S P; do for A in R2a R2b; do
  $PY -I src/s03_synth.py $M687 results/dev_sample20_eval_flights.txt $DEV/sample20_$V $A prior $DEV/syn_sample20/${V}_${A}_prior 8; done; done
$PY -I src/s03_synth.py $M687 results/dev_sample20_eval_flights.txt R1REF R1ref prior $DEV/syn_sample20/R1ref 8 $TEX
$PY -I src/s04_stats.py $M687 results/dev_sample20_eval_flights.txt real_cal $DEV/stats_sample20 8
for L in S_R2a_prior S_R2b_prior P_R2a_prior P_R2b_prior R1ref; do
  $PY -I src/s04_stats.py $DEV/syn_sample20/$L results/dev_sample20_eval_flights.txt $L $DEV/stats_sample20 8; done
$PY -I src/s08_dev_cv.py battery $DEV/stats_sample20 results/dev_sample20_eval_flights.txt results/dev_battery_sample20.json \
    real_cal S_R2a_prior,S_R2b_prior,P_R2a_prior,P_R2b_prior,R1ref
$PY -I src/s06_disc_guard.py $M687 $DEV/syn_sample20/S_R2a_prior results/dev_sample20_eval_flights.txt $DEV/feat_sample20 \
    S_R2a_prior results/dev_disc_sample20_S_R2a_prior.json 3

# 3. runner verification on CAL only (devcal mode: CAL lists stand in for holdout/partner; dev models, no freeze)
$PY -I src/run_holdout.py --holdout devcal --m687 $M687 --m652 /nonexistent --raw2 $RAW2 --syn-root $SYN/devcal_runner \
    --dev-models $DEV/models_sample20 --dev-holdout-list results/dev_sample20_eval_flights.txt \
    --dev-partner-list results/dev_sample20_partner_flights.txt --nw 4 --no-d3

# 4. 3-fold flight-grouped CV on CAL (S all folds; P fold 0), out-of-fold fit quality, larger-fold dev battery
$PY -I src/s08_dev_cv.py folds $DEV/cv/folds.csv            # = results/cv_folds.csv
for k in 0 1 2; do awk -F, -v k=$k 'NR>1 && $2!=k {print $1}' $DEV/cv/folds.csv > $DEV/cv/train_fold$k.txt
                   awk -F, -v k=$k 'NR>1 && $2==k {print $1}' $DEV/cv/folds.csv > $DEV/cv/test_fold$k.txt; done
for k in 0 1 2; do R2_THREADS=5 $PY -I src/s02_fit.py $M687 $DEV/cv/S/fold$k $DEV/cv/train_fold$k.txt S 8 4 7 100; done
R2_THREADS=5 $PY -I src/s02_fit.py $M687 $DEV/cv/P/fold0 $DEV/cv/train_fold0.txt P 8 4 7 100
$PY -I src/s08_dev_cv.py fitq $M687 $DEV/cv S results/cv_fit_quality_S.json
$PY -I src/s08_dev_cv.py fitq $M687 $DEV/cv P results/cv_fit_quality_P.json 0
# larger CAL fold (fold 0, 51 held-out flights): synthesis from fold-0 models, stats, dev battery, G0/diagnostics
$PY -I src/s11_dev_fold.py 0 $DEV/cv $M687 $TEX $DEV 5        # -> results/dev_battery_fold0.json, dev_disc_fold0_*.json
# post hoc (not pre-registered): autothrottle-engaged vs manual FF->N2 lead-lag on CAL real data
$PY -I -c "import sys; sys.path.insert(0,'src'); import r2common as R; print('\n'.join(R.cal_files()))" > $SYN/tmp/cal_all.txt
$PY -I src/q02_at_leadlag.py $M687 $SYN/tmp/cal_all.txt results/posthoc_at_leadlag_cal_ph5.json 3 --phases 5
$PY -I src/q02_at_leadlag.py $M687 $SYN/tmp/cal_all.txt results/posthoc_at_leadlag_cal_ph456.json 3 --phases 4,5,6

# 5. freeze: fit on ALL 152 CAL flights, copy to results/frozen/, hash, commit (before any holdout read)
R2_THREADS=4 $PY -I src/s02_fit.py $M687 $DEV/final/S ALLCAL S 8 4 7 300 --init $DEV/cv/S/fold0/ma.json   # ~23 min
R2_THREADS=6 $PY -I src/s02_fit.py $M687 $DEV/final/P ALLCAL P 8 4 7 300 --init $DEV/final/S/ma.json       # ~5 min
# run fits at most two at a time (each needs ~5-8 GB RAM)
$PY -I src/s09_freeze.py $DEV/final results $M687 $RAW2        # also writes results/manifest.json (integrity metadata only)
git add analysis/settling_experiment_round2 && git commit -m "Freeze round-2 models ..."

# 6. Phase B (A1: Tail 652 primary). Sample batch of 20 holdout flights first, then the full run.
$PY -I src/run_holdout.py --holdout 652 --m687 $M687 --m652 $M652 --raw2 $RAW2 --syn-root $SYN --sample 20 --nw 8 --no-d3
$PY -I src/run_holdout.py --holdout 652 --m687 $M687 --m652 $M652 --raw2 $RAW2 --syn-root $SYN --nw 8
# confirmatory archive-2 run: NOT RUN. Archive 2 is reserved, unread, for the build's proxy-mode acceptance gate
# (DEVIATIONS.md F1; user-confirmed). The command, when authorised, is:
#   $PY -I src/run_holdout.py --holdout 687a2 --m687 $M687 --m652 $M652 --raw2 $RAW2 --syn-root $SYN --nw 8
```

## Scripts

| Script | Purpose |
|---|---|
| `src/r2common.py` | constants, seeds (`SeedSequence` keyed by flight/engine/component), ISA corrections θ, δ, 4-Hz loader via `dlio.load_flight` |
| `src/ma_model.py` | M-A: monotone PCHIP maps (numba), fused simulation kernels, staged output-error fit, unit parameters and fleet prior, variants P and S |
| `src/mb_model.py` | M-B: double quantiser (native grid fitted on CAL code usage), idiosyncratic AR(1) noise, round-1 recorder effects, container cast |
| `src/mc_model.py` | M-C: per-engine VAR(p ≤ 8) with cross terms, 16×16 innovation covariance, numba simulator |
| `src/synth.py` | one synthetic flight from inputs only (running state from PH) |
| `src/s02_fit.py` | fit M-A, M-B, M-C on a list of CAL flights |
| `src/s03_synth.py` | synthetic MAT files: copy of the source file, only the 16 engine arrays replaced; R1-ref generator |
| `src/battery.py`, `src/s04_stats.py` | per-flight B1–B6, B9 statistics and G1 residue counts |
| `src/battery_eval.py` | distances, joint flight bootstrap, verdicts, decision rule, B9, G1 |
| `src/s06_disc_guard.py` | G0 (binding, pipeline-only metadata) and discriminator diagnostics (D2, D3, family ablation) |
| `src/s08_dev_cv.py` | CAL folds, out-of-fold fit quality with jackknife SEs, development battery |
| `src/s09_freeze.py` | freeze: copy models fitted on all CAL, SHA-256 of models, code and inputs |
| `src/run_holdout.py` | Phase B runner (archive-2 status, lists, synthesis, stats, battery, G0/diagnostics, report) |
| `src/s10_report.py` | tables, figures, REPORT.md skeleton |
| `src/q01_quick_look.py` | quick look (A5) |
| `src/t01_selftest.py` | self-tests |

## PROXY items (project rule 2) and evidence tags

| Item | Label | Evidence | Exposed by | Replacement in the Tejas build |
|---|---|---|---|---|
| Engine running state from PH 2..7; no start/shutdown transients | PROXY | `[MEASURED]` engines start/stop inside PH 2 on CAL (`log_sample_batches.md` #1) | B6 ground phases; airborne-mask fraction | M07 start/shutdown sequencing driven by M04 orders |
| Engine-type maps from four positions of one tail; fleet prior = across-position SD (n = 4) | PROXY | `[MEASURED]` 687-CAL | primary vs CAL-offset contrast; holdout on another tail | M10 health-state population model |
| Gas-path + thermocouple lag split; τ_TC ∝ W^−0.5 | model choice | `[TRANSFER: AGARD]` thermocouple scaling via `research_notes/.../texture_and_fault_gap_closure.md`; `[MEASURED]` τ on CAL | B2 N1→EGT, B3 EGT τ | M12 thermocouple model |
| FF measurement first-order lag | model choice | `[TRANSFER]` flowmeter dynamics (same note, Q2); `[MEASURED]` τ_FFs on CAL | B2 FF→N2 | M12 flowmeter model (type unresolved for IN20) |
| M-C VAR discrepancy | statistical layer (arm R2b only) | `[MEASURED]` CAL residuals | R2a vs R2b contrast | M07/M08 closed-loop dynamics (what M-C stands in for) |

Every fitted parameter is `[MEASURED]` on 687-CAL, with uncertainties in `results/frozen/*/ma_readable.json`
(naive, AR-inflated) and `results/cv_fit_quality_S.json` (grouped jackknife). `docs/assumptions.md` is outside this
folder's ownership; the coordinator carries these rows over.
