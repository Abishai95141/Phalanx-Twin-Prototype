## Run facts (holdout 652)

- Flights: {'holdout': 110, 'partner': 110, 'early': 55, 'late': 55} (holdout dates 2003-06-25T20:41 to 2010-03-15T18:14; median split ['2003-07-09T15:35', '2003-07-09T17:34']).
- Freeze check: frozen at 2026-10-14 17:14:38 IST; mismatches [].
- Holdout input checks (report only, no exclusion): 0 of 110 flights flagged (airborne MACH zeros > 5 %, PLA range < 5 deg or ALT max < 5,000 ft): [].
- Archive-2 status: ready=True, downloaded=True, extracted=True, last log line: `2026-10-14 16:55:13 extracted n_mat=602 first=687200109141013.mat last=687200112311241.mat`.

### Verdicts — PRIMARY: variant S (A6+A7), fleet-prior unit parameters

| Test | part | D_sim R2a | D_sim R2b | D_tail | D_temp | R2a | R2b | strict R2a | strict R2b |
|---|---|---|---|---|---|---|---|---|---|
| B1 | B1_fast | 0.313 | 0.196 | 0.047 | 0.045 | FAIL | FAIL | False | False |
| **B1** | test | | | | | **FAIL** | **FAIL** | False | False |
| B2 | B2 | 0.388 | 0.212 | 0.050 | 0.000 | FAIL | FAIL | False | False |
| **B2** | test | | | | | **FAIL** | **FAIL** | False | False |
| B3 | B3i | 0.499 | 0.417 | 0.078 | 0.058 | FAIL | FAIL | False | False |
| B3 | B3ii | 0.816 | 0.682 | 0.115 | 0.100 | FAIL | FAIL | False | False |
| **B3** | test | | | | | **FAIL** | **FAIL** | False | False |
| B4 | B4 | 1.491 | 0.690 | 0.154 | 0.086 | FAIL | FAIL | False | False |
| **B4** | test | | | | | **FAIL** | **FAIL** | False | False |
| B5 | B5i | 0.150 | 0.686 | 0.491 | 0.209 | PASS | FAIL | True | False |
| B5 | B5ii | 0.190 | 0.200 | 0.030 | 0.170 | FAIL | FAIL | False | False |
| **B5** | test | | | | | **FAIL** | **FAIL** | False | False |
| B6 | B6 | 1.230 | 1.675 | 0.488 | 0.747 | FAIL | FAIL | False | False |
| **B6** | test | | | | | **FAIL** | **FAIL** | False | False |

Decision rule (S, prior): **GO WITH FIXES or REWORK (depends on module attribution of the FAILs; see report)**; better arm R2b; PASS count 0; FAILs ['B1', 'B2', 'B3', 'B4', 'B5', 'B6']; G0 used True; ranking [['R2b', 0, 6, 4.462854265118014], ['R2a', 0, 6, 5.8466071160861315]].

### Verdicts — Variant P (pre-registered structure), fleet-prior unit parameters

| Test | part | D_sim R2a | D_sim R2b | D_tail | D_temp | R2a | R2b | strict R2a | strict R2b |
|---|---|---|---|---|---|---|---|---|---|
| B1 | B1_fast | 0.336 | 0.215 | 0.047 | 0.045 | FAIL | FAIL | False | False |
| **B1** | test | | | | | **FAIL** | **FAIL** | False | False |
| B2 | B2 | 0.450 | 0.225 | 0.050 | 0.000 | FAIL | FAIL | False | False |
| **B2** | test | | | | | **FAIL** | **FAIL** | False | False |
| B3 | B3i | 0.536 | 0.502 | 0.078 | 0.058 | FAIL | FAIL | False | False |
| B3 | B3ii | 0.891 | 0.713 | 0.115 | 0.100 | FAIL | FAIL | False | False |
| **B3** | test | | | | | **FAIL** | **FAIL** | False | False |
| B4 | B4 | 1.679 | 0.766 | 0.154 | 0.086 | FAIL | FAIL | False | False |
| **B4** | test | | | | | **FAIL** | **FAIL** | False | False |
| B5 | B5i | 0.416 | 0.580 | 0.491 | 0.209 | PASS | FAIL | False | False |
| B5 | B5ii | 0.190 | 0.190 | 0.030 | 0.170 | FAIL | FAIL | False | False |
| **B5** | test | | | | | **FAIL** | **FAIL** | False | False |
| B6 | B6 | 1.205 | 1.673 | 0.488 | 0.747 | FAIL | FAIL | False | False |
| **B6** | test | | | | | **FAIL** | **FAIL** | False | False |

Decision rule (P, prior): **GO WITH FIXES or REWORK (depends on module attribution of the FAILs; see report)**; better arm R2b; PASS count 0; FAILs ['B1', 'B2', 'B3', 'B4', 'B5', 'B6']; G0 used True; ranking [['R2b', 0, 6, 4.707191024571516], ['R2a', 0, 6, 6.418795714509946]].

### Verdicts — Secondary: variant S, CAL-fitted unit parameters

| Test | part | D_sim R2a | D_sim R2b | D_tail | D_temp | R2a | R2b | strict R2a | strict R2b |
|---|---|---|---|---|---|---|---|---|---|
| B1 | B1_fast | 0.320 | 0.188 | 0.047 | 0.045 | FAIL | FAIL | False | False |
| **B1** | test | | | | | **FAIL** | **FAIL** | False | False |
| B2 | B2 | 0.375 | 0.275 | 0.050 | 0.000 | FAIL | FAIL | False | False |
| **B2** | test | | | | | **FAIL** | **FAIL** | False | False |
| B3 | B3i | 0.496 | 0.422 | 0.078 | 0.058 | FAIL | FAIL | False | False |
| B3 | B3ii | 0.812 | 0.694 | 0.115 | 0.100 | FAIL | FAIL | False | False |
| **B3** | test | | | | | **FAIL** | **FAIL** | False | False |
| B4 | B4 | 1.454 | 0.689 | 0.154 | 0.086 | FAIL | FAIL | False | False |
| **B4** | test | | | | | **FAIL** | **FAIL** | False | False |
| B5 | B5i | 0.063 | 0.782 | 0.491 | 0.209 | PASS | FAIL | True | False |
| B5 | B5ii | 0.190 | 0.190 | 0.030 | 0.170 | FAIL | FAIL | False | False |
| **B5** | test | | | | | **FAIL** | **FAIL** | False | False |
| B6 | B6 | 1.263 | 1.696 | 0.488 | 0.747 | FAIL | FAIL | False | False |
| **B6** | test | | | | | **FAIL** | **FAIL** | False | False |

Decision rule (S, cal): **GO WITH FIXES or REWORK (depends on module attribution of the FAILs; see report)**; better arm R2b; PASS count 0; FAILs ['B1', 'B2', 'B3', 'B4', 'B5', 'B6']; G0 used True; ranking [['R2b', 0, 6, 4.606325465890112], ['R2a', 0, 6, 5.780595793838325]].

### Verdicts — Secondary: variant P, CAL-fitted unit parameters

| Test | part | D_sim R2a | D_sim R2b | D_tail | D_temp | R2a | R2b | strict R2a | strict R2b |
|---|---|---|---|---|---|---|---|---|---|
| B1 | B1_fast | 0.283 | 0.182 | 0.047 | 0.045 | FAIL | FAIL | False | False |
| **B1** | test | | | | | **FAIL** | **FAIL** | False | False |
| B2 | B2 | 0.456 | 0.294 | 0.050 | 0.000 | FAIL | FAIL | False | False |
| **B2** | test | | | | | **FAIL** | **FAIL** | False | False |
| B3 | B3i | 0.603 | 0.504 | 0.078 | 0.058 | FAIL | FAIL | False | False |
| B3 | B3ii | 0.900 | 0.694 | 0.115 | 0.100 | FAIL | FAIL | False | False |
| **B3** | test | | | | | **FAIL** | **FAIL** | False | False |
| B4 | B4 | 1.618 | 0.779 | 0.154 | 0.086 | FAIL | FAIL | False | False |
| **B4** | test | | | | | **FAIL** | **FAIL** | False | False |
| B5 | B5i | 0.387 | 0.579 | 0.491 | 0.209 | PASS | FAIL | False | False |
| B5 | B5ii | 0.180 | 0.190 | 0.030 | 0.170 | FAIL | FAIL | False | False |
| **B5** | test | | | | | **FAIL** | **FAIL** | False | False |
| B6 | B6 | 1.234 | 1.678 | 0.488 | 0.747 | FAIL | FAIL | False | False |
| **B6** | test | | | | | **FAIL** | **FAIL** | False | False |

Decision rule (P, cal): **GO WITH FIXES or REWORK (depends on module attribution of the FAILs; see report)**; better arm R2b; PASS count 0; FAILs ['B1', 'B2', 'B3', 'B4', 'B5', 'B6']; G0 used True; ranking [['R2b', 0, 6, 4.786842728788342], ['R2a', 0, 6, 6.319181592931264]].

### All arms: D_sim (synthetic vs real holdout, paired) with the bars

| label | B1_fast | B1_slow | B1h_fast | B2 | B3i | B3ii | B4 | B5i | B5ii | B6 |
|---|---|---|---|---|---|---|---|---|---|---|
| S_R2a_prior | 0.313 | 0.018 | 0.668 | 0.388 | 0.499 | 0.816 | 1.491 | 0.150 | 0.190 | 1.230 |
| S_R2a_cal | 0.320 | 0.021 | 0.683 | 0.375 | 0.496 | 0.812 | 1.454 | 0.063 | 0.190 | 1.263 |
| S_R2b_prior | 0.196 | 0.017 | 0.405 | 0.212 | 0.417 | 0.682 | 0.690 | 0.686 | 0.200 | 1.675 |
| S_R2b_cal | 0.188 | 0.017 | 0.294 | 0.275 | 0.422 | 0.694 | 0.689 | 0.782 | 0.190 | 1.696 |
| P_R2a_prior | 0.336 | 0.021 | 0.661 | 0.450 | 0.536 | 0.891 | 1.679 | 0.416 | 0.190 | 1.205 |
| P_R2a_cal | 0.283 | 0.016 | 0.551 | 0.456 | 0.603 | 0.900 | 1.618 | 0.387 | 0.180 | 1.234 |
| P_R2b_prior | 0.215 | 0.016 | 0.463 | 0.225 | 0.502 | 0.713 | 0.766 | 0.580 | 0.190 | 1.673 |
| P_R2b_cal | 0.182 | 0.018 | 0.216 | 0.294 | 0.504 | 0.694 | 0.779 | 0.579 | 0.190 | 1.678 |
| R1ref | 0.311 | 0.001 | 0.153 | 0.244 | 0.310 | 0.138 | 1.025 | 0.063 | 0.000 | 0.120 |
| **D_tail** | 0.047 | 0.010 | 0.019 | 0.050 | 0.078 | 0.115 | 0.154 | 0.491 | 0.030 | 0.488 |
| **D_temp** | 0.045 | 0.005 | 0.016 | 0.000 | 0.058 | 0.100 | 0.086 | 0.209 | 0.170 | 0.747 |

### Descriptive group values

| group | B5 scatter | B5 a | B2 lags eng1 (FF→N2, FF→N1, N2→N1, FF→EGT, N1→EGT) | airborne frac |
|---|---|---|---|---|
| real_holdout | 0.034 | 0.73 | [-0.5, 0.0, 0.5, 0.75, 0.25] | 0.912 |
| real_partner | 0.050 | 0.70 | [-0.5, 0.0, 0.5, 0.75, 0.25] | 0.922 |
| S_R2a_prior | 0.029 | 0.54 | [0.25, 0.25, 0.0, 0.75, 0.0] | 0.982 |
| S_R2a_cal | 0.036 | 0.54 | [0.25, 0.25, 0.0, 0.75, 0.0] | 0.985 |
| S_R2b_prior | 0.057 | 0.53 | [0.0, 0.0, 0.5, 0.75, 0.25] | 0.889 |
| S_R2b_cal | 0.060 | 0.54 | [0.0, 0.0, 0.0, 0.25, 0.0] | 0.888 |
| P_R2a_prior | 0.020 | 0.54 | [0.25, 0.5, 0.0, 1.0, 0.0] | 0.989 |
| P_R2a_cal | 0.021 | 0.55 | [0.25, 0.5, 0.0, 1.0, 0.0] | 0.921 |
| P_R2b_prior | 0.053 | 0.54 | [0.0, 0.0, 0.5, 0.75, 0.25] | 0.894 |
| P_R2b_cal | 0.053 | 0.54 | [0.0, 0.0, 0.0, 0.25, 0.0] | 0.882 |
| R1ref | 0.036 | 0.73 | [-0.25, 0.0, 0.5, 0.5, -0.25] | 0.904 |

### B9 (report only) and G1 (diagnostic)

| label | TRTR R² ridge/gbm | TSTR R² ridge/gbm | TSTR/TRTR ridge/gbm | ranking agrees | G1 TV N1/N2/EGT/FF |
|---|---|---|---|---|---|
| S_R2a_prior | 0.815/0.957 | 0.753/0.883 | 0.924/0.923 | True | 0.021/0.015/0.016/0.106 |
| S_R2a_cal | 0.815/0.957 | 0.724/0.875 | 0.887/0.914 | True | 0.026/0.012/0.013/0.091 |
| S_R2b_prior | 0.815/0.957 | 0.762/0.883 | 0.935/0.922 | True | 0.017/0.011/0.014/0.028 |
| S_R2b_cal | 0.815/0.957 | 0.775/0.875 | 0.950/0.914 | True | 0.018/0.011/0.013/0.031 |
| P_R2a_prior | 0.815/0.957 | 0.752/0.872 | 0.923/0.911 | True | 0.020/0.018/0.015/0.131 |
| P_R2a_cal | 0.815/0.957 | 0.760/0.872 | 0.932/0.911 | True | 0.025/0.012/0.011/0.095 |
| P_R2b_prior | 0.815/0.957 | 0.761/0.881 | 0.933/0.920 | True | 0.017/0.011/0.013/0.029 |
| P_R2b_cal | 0.815/0.957 | 0.764/0.877 | 0.937/0.916 | True | 0.018/0.011/0.013/0.029 |
| R1ref | 0.815/0.957 | 0.809/0.957 | 0.993/1.000 | True | 0.208/0.192/0.270/0.012 |

### G0 (binding) and discriminator diagnostics (no verdict)

| label | G0 pipeline-only LR AUC [CI] | GB AUC [CI] | G0 | full-metadata LR/GB (diag.) | D2 LR/GB 64 s | D2 LR/GB seg | D3 64 s |
|---|---|---|---|---|---|---|---|
| P_R2a_prior | 0.500 [0.5, 0.5] | 0.500 [0.5, 0.5] | PASS | 1.000/1.000 | 1.000/1.000 | 1.000/1.000 | – |
| P_R2b_prior | 0.500 [0.5, 0.5] | 0.500 [0.5, 0.5] | PASS | 1.000/1.000 | 1.000/1.000 | 1.000/1.000 | – |
| S_R2a_prior | 0.500 [0.5, 0.5] | 0.500 [0.5, 0.5] | PASS | 1.000/1.000 | 1.000/1.000 | 1.000/1.000 | 1.000 |
| S_R2b_prior | 0.500 [0.5, 0.5] | 0.500 [0.5, 0.5] | PASS | 1.000/1.000 | 1.000/1.000 | 1.000/1.000 | 1.000 |

Family ablation, P_R2a_prior, D2_lr_64_tex: drop_cross 1.000, drop_missing 1.000, drop_noise 1.000, drop_quant 1.000, drop_spectral 1.000, drop_tails 1.000, only_cross 1.000, only_missing 1.000, only_noise 1.000, only_quant 1.000, only_spectral 1.000, only_tails 1.000

Family ablation, P_R2b_prior, D2_lr_64_tex: drop_cross 1.000, drop_missing 1.000, drop_noise 1.000, drop_quant 1.000, drop_spectral 1.000, drop_tails 1.000, only_cross 1.000, only_missing 1.000, only_noise 1.000, only_quant 1.000, only_spectral 1.000, only_tails 1.000

Family ablation, S_R2a_prior, D2_lr_64_tex: drop_cross 1.000, drop_missing 1.000, drop_noise 1.000, drop_quant 1.000, drop_spectral 1.000, drop_tails 1.000, only_cross 1.000, only_missing 1.000, only_noise 1.000, only_quant 1.000, only_spectral 1.000, only_tails 1.000

Family ablation, S_R2b_prior, D2_lr_64_tex: drop_cross 1.000, drop_missing 1.000, drop_noise 1.000, drop_quant 1.000, drop_spectral 1.000, drop_tails 1.000, only_cross 1.000, only_missing 1.000, only_noise 1.000, only_quant 1.000, only_spectral 1.000, only_tails 1.000

### Automatic attribution evidence (input to the module attribution in the report)

- B1_fast: R2a→R2b (M-C) S/prior 0.313→0.196; P→S (A6+A7) R2a 0.336→0.313; prior→cal offsets S/R2a 0.313→0.320; R1-ref 0.311; D_tail 0.047
- B2: R2a→R2b (M-C) S/prior 0.388→0.212; P→S (A6+A7) R2a 0.450→0.388; prior→cal offsets S/R2a 0.388→0.375; R1-ref 0.244; D_tail 0.050
- B3i: R2a→R2b (M-C) S/prior 0.499→0.417; P→S (A6+A7) R2a 0.536→0.499; prior→cal offsets S/R2a 0.499→0.496; R1-ref 0.310; D_tail 0.078
- B3ii: R2a→R2b (M-C) S/prior 0.816→0.682; P→S (A6+A7) R2a 0.891→0.816; prior→cal offsets S/R2a 0.816→0.812; R1-ref 0.138; D_tail 0.115
- B4: R2a→R2b (M-C) S/prior 1.491→0.690; P→S (A6+A7) R2a 1.679→1.491; prior→cal offsets S/R2a 1.491→1.454; R1-ref 1.025; D_tail 0.154
- B5i: R2a→R2b (M-C) S/prior 0.150→0.686; P→S (A6+A7) R2a 0.416→0.150; prior→cal offsets S/R2a 0.150→0.063; R1-ref 0.063; D_tail 0.491
- B5ii: R2a→R2b (M-C) S/prior 0.190→0.200; P→S (A6+A7) R2a 0.190→0.190; prior→cal offsets S/R2a 0.190→0.190; R1-ref 0.000; D_tail 0.030
- B6: R2a→R2b (M-C) S/prior 1.230→1.675; P→S (A6+A7) R2a 1.205→1.230; prior→cal offsets S/R2a 1.230→1.263; R1-ref 0.120; D_tail 0.488

### Figures

![holdout_652_battery_ratio.png](../../figures/holdout_652_battery_ratio.png)
![holdout_652_b1_fast_scatter.png](../../figures/holdout_652_b1_fast_scatter.png)
![holdout_652_b2_lags.png](../../figures/holdout_652_b2_lags.png)
