# Removal-risk model: backtest and champion

Source: **Simulated fleet history** (synthetic training worlds; not validated). Model `hazard` 0.2.0. Landmarks every 10 FH, horizon 15 FH; ridge 0.1 partial pooling across classes.
Fitted classes (≥ 10 events): HYDP. INSUFFICIENT_EVIDENCE: ADC, AMAGB, BCU, BRAKE, CHUTE, DFCC, ENG, FADEC, FQGS, GEN, INGPS, JFS, OBOGS, RADAR, TYRE.

Challenger chosen on validation seed [3] (fit on [1, 2]): age Brier 0.059313, landmark Brier 0.069978 → **age**.

Held-out test seed [4] (fit on [1, 2, 3]), fitted classes:

| Model | Landmarks | Events in window | Brier | AUC | C-index |
|---|---:|---:|---:|---:|---:|
| class-exposure baseline (events / flight hours per class) | 346 | 28 | 0.074414 | 0.5 | 0.5 |
| Weibull AFT on age, partially pooled (champion) | 346 | 28 | 0.059378 | 0.903 | 0.8302 |
| landmark Weibull AFT with spell covariates, partially pooled | 346 | 28 | 0.075439 | 0.896 | 0.8225 |

**Champion: Weibull AFT on age, partially pooled** — the age challenger beats the class-exposure baseline on the held-out seed.

Landmark-model covariate effects (log residual-life scale; negative = higher risk): {'age_fh': -0.0014, 'alarms_last10': -0.0476, 'alarm_rate': 0.0779, 'prior_rtok': -0.0254, 'inferred_install': 0.0083}.

Calibration of the champion (quintiles of predicted risk):

| Bin | n | Mean predicted | Observed |
|---:|---:|---:|---:|
| 1 | 70 | 0.00259 | 0.01429 |
| 2 | 69 | 0.01764 | 0.0 |
| 3 | 69 | 0.04885 | 0.0 |
| 4 | 69 | 0.09844 | 0.04348 |
| 5 | 69 | 0.2022 | 0.34783 |

Harrell's C over landmark rows (residual life vs predicted risk); rows of one spell are correlated. The class-exposure baseline gives one value per class, so its C-index within a class is 0.5.

Final model (age) on all seeds [1, 2, 3, 4]: `/home/linux1/phalanx/Phalanx-Solution/proto/runs/train/hazard_model.json`.
