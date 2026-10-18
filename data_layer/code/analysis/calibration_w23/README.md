# W2.3a engine and FADEC calibration (AD-55 item 6): analysis record

Brief: `docs/build_briefs/W2.3a_engine_calibration.md`. Credibility ceiling: NASA-STD-7009B Level 2 against proxy
and transfer evidence; nothing here is validated against Tejas/IN20 data.

## Item 1: ground-idle acceleration margin (committed first, coordinator request 2026-10-15)

**Finding (W2.5 D3; W2.1a ENG-506).** M08's accel Wf/PS3 limit (`acc_k` x reference) was derived from the
no-load engine and, below idle, from the W1.3b shape, which falls as N2 falls while the loaded engine's steady
Wf/PS3 rises. With M09's idle extraction a sag of a few points put the requirement above the accel limit and
the engine rolled back onto WF_MIN with T5 rising.

**Fix.** A-W2.3-1 (installed fuel-control lines; `harmonise`, `harm_bleed`/`harm_pto`/`harm_line_min_n2c`) and
A-W2.3-3 (N2-governor gain schedule `gov_ks`, margin 5). Structural accel margin at the low end of a serviceable
fuel control (1/0.88, Muir CF-18) holds from 55 % N2c to idle for every B7 case and the build band at the
nominal loads (21.8 kW, 0.503 kg/s) and at the integrated aircraft's (35 kW, 0.54 kg/s): minimum 1.187 (F3,
integrated loads).

### Integrated aircraft (n = 1 sortie window: gate sortie 2, TJ213, root 0xA5; `code/integrated_takeoff.py`)

Idle segment 0-755 s (PLA 18), slam to IRP at 807 s. 1 s means of 240 Hz.

| configuration | idle N2 % | N2 p-p last 60 s | PTO kW mean / max | min stall margin | N2 at slam | after IRP (20 s) |
|---|---|---|---|---|---|---|
| main b7e0dee | 66.29 | 5.03 % | 29.0 / 34.8 | 0.026 | 63.75 % | N2 45.0 %, N1 17 %, ACCEL/WF_MIN (ENG-506) |
| installed lines only | 66.31 | 2.59 % | 29.0 / 34.9 | 0.029 | 63.93 % | N2 93.7 %, N1 101.7 % at 13 s |
| + gain schedule, margin 2.5 | 66.31 | 0.76 % | 29.0 / 34.9 | 0.038 | 66.13 % | N2 93.7 %, N1 100 % at 12 s |
| **item 1 (margin 5)** | 66.30 | **0.44 %** | 29.0 / 34.9 | 0.038 | 66.25 % | **N2 93.7 %, N1 100 % at 12 s, ACCEL then N1** |

Results: `results/integrated_takeoff_{main_b7e0dee,installed_lines_only,gain_margin_2p5,item1}.json` (summaries;
the 1 s series are regenerable with the script's third argument). The main row was run from an extract of
b7e0dee's `src`/`configs`/`docs` with the same script.

Observations (not item-1 scope, reported): the M07 constant-speed stall margin at idle is 0.04 (0.026-0.038 on
the idle swings), an uncalibrated low-speed map property (item 2); the transient T5 peak after the slam is
1,137 K against a steady IRP T5 of about 1,105 K (C14/C17, items 2-3).

### Governor gain-schedule margin (`code/gov_margin_sweep.py`, `results/gov_margin_sweep.json`)

Criterion stated before this sweep (after a first look at margins 2.5-10 on the F3 step alone, where 2.5 rang
for 30 s): overshoot of the W2.5 idle step (loads and deterioration stepped in from the
no-load trim) below 23 % (damping ratio > 0.42, the PM > 45 deg rule of C-MAPSS40k's scheduled setpoint loops)
for every case. Sample: 9 deterministic 30 s step runs (healthy, F1-F7, build) per margin plus one 40 s idle
kick at the integrated loads.

| margin | gain at idle | max overshoot (case) | settle to 0.2 % (worst) | kick deviation 30-40 s |
|---|---|---|---|---|
| (none, x1) | 1 | limit cycle +-4 % (F3) | not settled | 0.39 % (no decay) |
| 2.5 | 2.7 | 0.83 (F3) | 28.8 s | 0.026 % |
| 4 | 4.4 | 0.29 (F3) | 14.9 s | 0.008 % |
| **5** | **5.4** | **0.15 (F3)** | **7.9 s** | **0.005 %** |
| 6 | 6.5 | 0.08 (F1) | 5.3 s | 0.004 % |

Margin 5 is the smallest tested value meeting the criterion; it is re-derived (same criterion) after the M07
calibration of items 2-5 changes the line slope.
