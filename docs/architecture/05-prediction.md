# 05 · Prediction (predictive intelligence)

Questions this layer answers: **What will be removed or fail, by which cause, and when? How much will each tail
fly? How many spares will we need, and how long will they take to arrive? Will this defect turn out to be
no-fault-found?** Every prediction carries uncertainty, a model version and the evidence it used, and is
written into the twin state ([02](02-digital-twin.md)).

## Headline decisions (and the challenge to "TimesFM 3")

1. **The core predictive problem is time-to-event under heavy censoring, not forecasting.** Our targets are
   time-to-removal/failure with right-censoring (units still installed), left truncation (units enter
   observation mid-life), competing causes (confirmed failure vs NFF removal vs hard-time/policy removal) and
   few events per part class. That is **survival analysis and state-space degradation modelling**.
2. **TimesFM 3 exists but is not the right core model — and we cannot ship it.** Google released TimesFM-3.0
   on 31 Aug 2026 (330 M parameters, native multivariate, covariates, 9 quantiles), but its downloadable weights
   are under a **non-commercial, non-production licence** (production only via Google Cloud BigQuery). That
   rules it out of an on-premises/air-gapped MoD deployment. More fundamentally, time-series foundation models
   (TSFMs) forecast regularly sampled series; they have no likelihood for censored lifetimes, no competing
   causes, no first-passage distributions and no notion of maintenance resets. Leaderboard leads are
   self-reported and contested (TimesFM-3, Chronos-2, TiRex-2 and Toto 2.0 all claim #1), and independent
   critiques find pervasive train/test leakage (Meyer et al., arXiv 2510.13654; Hyndman, Aug 2026).
   **Decision: TSFMs appear only as a zero-shot baseline row in forecasting backtests, using Apache-2.0 models
   (Chronos-2, TimesFM-2.5, Toto 2.0, IBM TTM), and enter the product only if they beat tuned classical and
   structural baselines in our own as-of backtest.**
3. **The preview cannot train a failure model, and we say so.** v0.9 has 59 component removals (41 tyres),
   **0 CONFIRMED shop findings**, 361 defect jobs (by global key; ~1,000 per world) with ~60 % closed
   could-not-duplicate. What it *can* train: the **CND/NFF classifier**, the **supply lead-time survival model**
   (134 closed + 24 open demands), **usage forecasting**, **tyre demand** (deterministic from landings), and the
   Bayesian removal-hazard machinery with honest "insufficient events" posteriors.
4. **Usage is driven by availability, not by its own history.** A backtest on the preview: next-4-week flying
   hours per tail correlate 0.74 with the tail's mission-capable fraction; a historical-mean forecast has MAE
   4.8 FH (mean 9.2 FH), while rate × *known* future availability reaches MAE 1.65 FH. The forecastable signal
   is the output of our own availability model — no univariate forecaster can learn it from the FH series.

## Predictive stack

| # | Target | Primary model | Baselines / challengers | Demonstrable on v0.9 |
|---|---|---|---|---|
| P1 | P(defect closes CND/NFF); later P(RTOK \| removal) | calibrated gradient boosting / logistic on BIT family, persistence, software-load window, co-occurring exceedances, serial history | per-code base rate | **Yes** |
| P2 | Component removal hazard by cause, P(removal of cause k in (t, t+H]) | **Bayesian hierarchical cause-specific Weibull AFT** (PyMC) on a usage clock, partial pooling across part classes, serial frailty for rogue units | Weibull/Weibayes (= the data layer's reference posterior), KM / Aalen–Johansen; discrete-time-hazard LightGBM once ≥ ~50 pooled events | Machinery yes; failure cause no |
| P3 | Engine health index and remaining life | healthy-baseline residual HI ([04](04-condition-monitoring-and-diagnostics.md)) + per-serial **state-space degradation model** (Wiener fouling with wash-reset jumps, gamma/monotone erosion, Bayesian updating; UKF or particle filter via NASA progpy for onset) → first-passage remaining-life distribution, fused with usage life (1,000 FH hard time, disc LCF on TAC) | deep RUL and TSFM trend as offline ablations | No (no health indicator in v0.9) |
| P4 | Usage per tail/serial (FH, landings, TAC, LUIs) | **structural hierarchical rate model**: planned flying task × predicted MC days × rate per MC day by tail/squadron/mission mix; counters as ratios to FH | historical rate, ETS (statsforecast), one Apache-2.0 TSFM zero-shot | **Yes** |
| P5 | Spares demand over the lead-time window | **reliability-based demand**: Σ over installed serials of P(removal in window) (all causes, incl. NFF) → Poisson-binomial lead-time demand; tyres = forecast landings ÷ empirical replacement interval (8–14 landings) | Croston/SBA/TSB/ADIDA; a TSFM row, scored on service level not MAE | Tyres yes |
| P6 | Supply lead time | **survival model of demand fulfilment** (log-normal AFT / KM, priority covariate, open demands censored, pooled across parts) | empirical quantiles | **Yes** (median 4.6 d, p90 37 d, max 107 d — tyre-dominated) |

### Why these models (the 10-point summary)

| Aspect | Removal hazard (P2) | Engine health (P3) | CND classifier (P1) |
|---|---|---|---|
| Stakeholder problem | logistics and the Engineering Officer need "which serials will need replacing before the spare can arrive" | engine shop needs early, explainable wear-out warnings | technicians and SEngO need "is this snag worth troubleshooting or a nuisance?" |
| KPI | NMCS, AOG days, fill rate, lead-time hit rate | in-flight failures, unscheduled engine removals, NMCM | no-fault man-hours, NFF rate, NMCM |
| How it works | log T = βᵀx + σε on a usage clock; log η_class ~ N(μ_group, τ) partial pooling; censored and left-truncated likelihood terms; separate hazards per cause | X(t) = μΛ(t) + σB(Λ(t)) for fouling (non-monotone, wash = jump), gamma increments for erosion; Bayesian update of unit drift; first-passage time to threshold | supervised classification on outcomes, calibrated (Platt/beta) with conformal sets |
| Evidence | Abernethy *New Weibull Handbook* (Weibayes at 0–2 failures); arXiv 2011.03140 (hierarchical field-failure prediction); Fine & Gray 1999 competing risks | Si et al., EJOR 213(1) 2011 (statistical RUL review); van Noortwijk, RESS 2009 (gamma processes); Gebraeel et al. 2005; Daigle & Goebel 2013; Lövberg (PHM 2021 winner) healthy-baseline normalisation | Khan et al. NFF 2014; MAPIE / conformal |
| Open source | PyMC (Apache-2.0), lifelines (MIT), scikit-survival (GPL-3, internal only) | NASA progpy (NOSA, active), numpy/statsmodels | LightGBM/XGBoost (Apache/MIT), MAPIE (BSD-3) |
| Strengths | honest with 0–5 failures per class; censoring, truncation, competing causes; interpretable β/η; posterior plugs into the fork service's `BeliefPosterior` | handles irregular sparse snapshots exactly; native uncertainty; no run-to-failure labels needed | label-rich now; directly drives NFF reduction |
| Limits | needs cause labels (0 CONFIRMED in v0.9); covariates limited by event count (~10 events per covariate) | needs a health indicator (not in v0.9); signature signs unvalidated | labels reflect M18's policy, not truth |
| Data | COMPONENT_LIFE install/remove + item hours/cycles, usage counters, cause from DEFECT_WO action + SHOP_FINDING | telemetry snapshots, washes (orders), installs, SOAP (once MX values reach the contract) | events, DEFECT_WO, SHOP_FINDING |

**Rejected:** DeepSurv/DeepHit (need hundreds–thousands of events; pycox unmaintained since 2024);
similarity-based RUL (needs run-to-failure libraries); C-MAPSS/N-CMAPSS-style deep RUL as the main model
(piecewise-linear target assumption, run-to-failure assumption, dense telemetry, airliner→fighter transfer
unsupported — kept only as an offline ablation).

### Staying honest when the simulator uses the same families

Phalanx generates degradation with Wiener, gamma, Weibull and N-CMAPSS-style processes. Choosing these families
is legitimate — they are the standard reliability families used on real engines — but a model can look good
only because its family matches the generator. Protocol:
1. Learn parameters only from contract data. **Never copy registry values** (e.g. spall Weibull β 1.5,
   η 8,000 EOT h) into priors; if used, report as a labelled "oracle-prior" upper bound.
2. Misspecification ablation: for every family the generator uses, fit one it does not (log-normal AFT,
   piecewise-exponential, KM/RSF).
3. Sweep robustness: evaluate on worlds generated with different sweep settings and seeds we did not tune on.
4. Score decisions, not just RUL error: CRN-paired forks against StatusQuo, Scheduled and ConditionBased.
5. Always report the plain Weibull baseline — it *is* the reference posterior.

## Prediction is only useful if it beats the lead time

The prescriptive research quantified the limit using the data layer's own supply model (log-normal fitted to
CAG IL-76 bins × Tejas factor 0.3, heavy-tailed: mean ≈ 5.4 × median): for a typical LRU at AOG priority the
lead time has median ≈ 29 days and mean ≈ 159 days; with no stock on the shelf, a 30-day warning avoids only
≈ 13 % of expected AOG days and a 90-day warning ≈ 26 %. So:
- for randomly failing LRUs the lever is **stock, pooling and expediting** ([06](06-prescription-and-planning.md)),
  with predictions feeding *demand rates* rather than per-unit alarms;
- per-unit early warnings pay for **wear-out items with long, reliable warning** (engine hot section, bearing
  debris, life-counted parts) — the horizon H for each part class is set ≥ its p90 lead time, and "useful lead
  time" is a first-class evaluation metric.

## Evaluation under information discipline

1. As-of feature store: every feature and label join filters each topic by its own `t_ingest ≤ t`; labels are
   cut at t + H with ingest-time-aware outcomes (a removal ingested after a 14-day lag still counts for scoring,
   never for features).
2. Rolling-origin backtests at daily epochs; a gap ≥ label horizon between train and test; grouping by serial.
3. Censoring-aware metrics: Uno's IPCW C-index, time-dependent AUC at each H, IPCW integrated Brier score,
   calibration per horizon; conformalized survival bounds (Candès, Lei & Ren, JRSS-B 2023) for statements like
   "with 90 % confidence this pump survives ≥ X FH".
4. Operational metrics: lead-time hit rate (share of removals first flagged ≥ the part's p90 lead time before),
   false alerts per 100 FH, NFF removals avoided.
5. Forecasting: MASE and CRPS on rolling origins vs tuned ETS and the structural model; spares scored on
   service level / fill rate / backorder-days, not MAE (Chin, Cheng & Gunawan, ICDM-26: accuracy rank and
   service rank correlate −0.555 on real spare-parts data).
6. Decision level: CRN-paired fork KPI deltas with CIs — the claim judges care about.

## Key sources

- google-research/timesfm (TimesFM-3 licence notice) — https://github.com/google-research/timesfm ; model card — https://huggingface.co/google/timesfm-3.0-pytorch
- Chronos-2 — https://arxiv.org/abs/2510.15821 ; Toto 2.0 — https://arxiv.org/abs/2605.20119 ; IBM TTM — https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2
- Hyndman, "Evaluating time series foundation model claims" (2026) — https://robjhyndman.com/hyndsight/foundation_models.html
- Meyer et al., TSFM leakage — https://arxiv.org/abs/2510.13654 ; GIFT-Eval — https://arxiv.org/abs/2410.10393 ; fev-bench — https://arxiv.org/abs/2509.26468
- Chin, Cheng & Gunawan, "Accuracy Is Not Service" — https://arxiv.org/abs/2609.13840
- Si et al., EJOR 213(1) 2011 — https://ideas.repec.org/a/eee/ejores/v213y2011i1p1-14.html
- Arias Chao et al., N-CMAPSS (*Data* 6(1) 2021) — https://doi.org/10.3390/data6010005 ; PHM 2021 winners — https://data.phmsociety.org/2021-phm-conference-data-challenge-winners/
- Lövberg, PHM 2021 — https://papers.phmsociety.org/index.php/phmconf/article/view/3108
- Hierarchical Bayesian field-failure prediction — https://arxiv.org/abs/2011.03140 ; hierarchical gamma processes in Stan — https://arxiv.org/abs/2406.11216
- Conformalized survival analysis — https://arxiv.org/abs/2103.09763
- NASA progpy — https://github.com/nasa/progpy ; PyMC — https://pypi.org/project/pymc/ ; lifelines — https://github.com/CamDavidsonPilon/lifelines ; MAPIE — https://github.com/scikit-learn-contrib/MAPIE ; statsforecast — https://github.com/Nixtla/statsforecast
- MIL-HDBK-189C (Crow-AMSAA) — https://www.dote.osd.mil/Portals/97/docs/TEMPGuide/MIL-HDBK-189C.pdf
