# 08 · Learning and assurance: one lifecycle on one event log

The team listed model promotion, drift identification, state machines, quality gates, CMMS, model registry,
learning pipeline, monitoring and audit trail. The research converges on a single design that makes them **one
system**: an append-only, hash-chained **Lifecycle Event Log (LEL)**, with every lifecycle modelled as a state
machine whose transitions are events in that log. The model registry, CMMS view, dashboards and audit trail are
*projections* of the log, not separate stores.

## Why one log

- Phalanx is already event-sourced: a run is a pure function of (seed, config, dictionary version, order log), and
  replay is bit-exact. If our side is event-sourced too, any recommendation can be replayed and the whole chain
  evidence → decision → order → world → outcome → label → retrain is reproducible.
- Cross-lifecycle causality becomes a join on `causation_id`: alert → issue → recommendation → order → work order
  → shop finding → label → model version.
- It satisfies the assurance objectives by construction (configuration management, operational monitoring,
  post-operation explainability — below).

```text
LEL event = {event_id, stream=<entity>:<id>, seq, type,
             t_valid (sim time), t_recorded (wall time),
             actor (AGENT | HUMAN:<id>), causation_id, correlation_id,
             refs {release_id, contract_hash, dict_hash, feature_spec_hash, model_version,
                   policy_version, record_ids[], order_id, fork_result_id},
             payload, prev_hash, hash = blake2b(prev_hash ‖ canonical_json(event))}
```

Same hashing primitive the contract uses for `record_id`. Append-only table (UPDATE/DELETE forbidden), periodic
signed checkpoint of the chain head — tamper-evident logging in the Crosby & Wallach / Certificate Transparency
(RFC 6962) tradition. Merkle trees only if there are many writers or external auditors; avoid immudb (BSL).

## The state machines (all transitions are LEL events)

| Machine | States |
|---|---|
| DatasetRelease | ANNOUNCED → INGESTED → VALIDATED → ADOPTED → SUPERSEDED (attributes: maturity PREVIEW/VALIDATED, contract, dictionary, commit, seeds, MANIFEST sha) |
| DataBatch | DISCOVERED → CHECKSUM_OK → SCHEMA_OK (or MIGRATED) → CONTENT_VALID → ADMITTED; or QUARANTINED → RELEASED / REJECTED |
| ModelVersion | DRAFT → CANDIDATE → SHADOW → CHALLENGER → CHAMPION → RETIRED; side states SUSPENDED, ROLLED_BACK, **REVALIDATION_REQUIRED** |
| PolicyVersion | DRAFT → TESTED → SHADOW → FORK-EVALUATED → CANARY → ACTIVE → RETIRED ([07](07-triage-policy-decision-loop.md)) |
| Issue (triage) | NEW → TRIAGED → … → RESOLVED → CLOSED / REOPENED ([07](07-triage-policy-decision-loop.md)) |
| Recommendation | PROPOSED → APPROVED / MODIFIED / REJECTED → ORDER_ISSUED → (mirrors `orders.status`) → OUTCOME_OBSERVED → LABELLED → LEARNED; EXPIRED / SUPERSEDED |
| Work order (CMMS mirror, read-only) | OPEN → IN_WORK → AWP / AWM / DEFERRED → CLOSED (from `maint.records` versions) |
| Label | PENDING → PROVISIONAL → CONFIRMED / RTOK / BCM, or CENSORED; REVISED |
| EpochRun | IDLE → SNAPSHOT → ANALYZE → PLAN → BOARD_OPEN → FROZEN → SUBMITTED → RECONCILED |

Declared with **python-statemachine 3.x** (MIT; statecharts, guards, diagrams); each machine is a reducer
`state = fold(apply, events_for(stream))`.

## The unified lifecycle (one diagram in words)

```text
UPSTREAM RELEASE  {release_id = sha256(MANIFEST), contract_hash, dict_hash, code_commit, seeds, maturity}
  └─▶ [1] G0 integrity + contract gate (doc 03)            DataBatch SM → ADMITTED | QUARANTINED
  └─▶ [2] bitemporal as-of store  ──▶ [2b] change-point registry (DICT/CONTRACT release, SW load, MOD,
                                       BIT regime, monitoring config, install/remove, wash, base/season)
  └─▶ [3] feature + label builders (pure functions of store, as_of, spec hash; labels carry t_known)
  └─▶ [4] offline training → frozen model → MLflow run + LoggedModel
  └─▶ [5] registry: ModelVersion SM; MLflow aliases are a projection of the log
        gates G0..G5, each an event with an evidence bundle (report hashes, fork result ids, approver)
  └─▶ [6] SHADOW: scores every 08:00 IST epoch from as_of(t); recommendations logged, never submitted
  └─▶ [7] CHAMPION → Recommendation SM → order → CMMS view + work-request outbox
  └─▶ [8] monitoring: gate stats · ODD checks · drift segmented by [2b] · alert rate · label-free
        performance estimate · matured-label calibration by slice · harmful-shift test · fork KPI tracking
        → Alert SM → {EXPECTED_SHIFT | RECALIBRATE | RETRAIN | ROLLBACK | SUSPEND | DISMISS}
  └─▶ [9] learning from outcomes: SHOP_FINDING / INSPECTION → Label SM → retrain trigger → back to [3]
ALL boxes append to ONE Lifecycle Event Log.  Projections: registry · CMMS view · alert queue · dashboards ·
provenance ("why order X?") · OpenLineage-shaped JSON.
```

## Assurance anchor: EASA learning assurance (+ India, DoD, NIST)

EASA's *AI Concept Paper Issue 02* (Mar 2024) — the W-shaped learning-assurance process — covers **offline
learning only: the model is frozen at approval**. Design consequence: **every retrain produces a new frozen
version that re-enters the gates; no self-updating model in the decision path.** (EASA has since published NPA
2025-07 "DS.AI" and a Proposed Issue 03 in June 2026; ED-324/ARP6983 is not yet published — cite it as an
emerging standard, not a compliance basis.) Our PdM advisory is EASA **Level 1B** (human approves); auto-issued
AGENT orders edge toward Level 2, which is why the demo keeps everything on consent.

| EASA objective | What it asks | Our mechanism |
|---|---|---|
| DA-04 | data quality requirements incl. traceability "from origin to final operation", independence of train/val/test | contract-hash gate; MANIFEST sha per file; `record_id` lineage; label spec |
| DM-06 | independent data sets | split **by tail and by time block**, never by row; a sortie never spans sets |
| DM-08 | re-verify the operational design domain (ODD) | ODD spec per model version: bases, seasons, BIT regime, `sw_config_id`, mission types, contract/dictionary versions |
| LM-04 / LM-14 | generalisation evidence | held-out tails + conformal intervals (no formal bounds claimed) |
| LM-11/12/13 | stability, robustness | seed/fold variance; perturbation suite (sentinels, freezes, clock offsets, missing channels) |
| CM-01 | versioning, baselining, change control, reproducibility, archiving | registry + LEL + hashes; reproducibility by Phalanx order-log replay |
| SA-02/03, EXP-05..09 | record data for continuous safety assessment; monitor inputs within ODD, outputs within bounds; record what's needed to explain behaviour after operations | monitoring spec shipped with each model version; LEL decision provenance |
| QA-01 | process assurance | gate decisions signed by a reviewer other than the model author |

**India:** DRDO's **Evaluating Trustworthy AI (ETAI)** framework (Scientific Analysis Group; launched 17 Oct 2024
by CDS Gen. Anil Chauhan; five principles: reliability & robustness, safety & security, transparency, fairness,
privacy) — we map its principles onto the gates (fairness = per-base/per-squadron non-inferiority; privacy =
`crew_id` pseudonymous and not a feature without justification). CEMILAC has no ML-specific guidance; the closest
precedent is **HUMS maintenance credit** (FAA AC 29-2C MG 15 / EASA AMC 29.1465), introduced via Controlled
Service Introduction — our shadow → challenger → canary sequence is the ML analogue. **US DoD RAI Toolkit**
(SHIELD: …Log for traceability, Detect via continuous monitoring) and **NIST AI RMF MEASURE 2.4** (compare
production metrics with pre-deployment metrics) are cross-references.

## Promotion gates (one evidence bundle per gate, all logged)

| Gate | Criteria |
|---|---|
| **G0 Data** | release sha verified; contract hash allowlisted; dictionary registered; zero unresolved quarantines in the training window; simulator-artefact (aborted) sorties excluded; point-in-time and shuffle-the-future tests pass; restricted-path audit clean; metadata-only classifier at chance |
| **G1 Offline backtest** (rolling-origin, as-of, held-out tails and later time block) | beats the rule baseline (ConditionBasedPolicy) and non-inferior to the champion on primary metrics (time-dependent AUC/Uno's C at H, IPCW Brier, precision at the operating point, false alarms per 100 FH); **useful lead time**; per-slice non-inferiority (base, BIT regime, `sw_config_id`, season, engine-age band) with INSUFFICIENT_EVIDENCE below n_min; calibration (ECE ≤ 0.05, slope 0.8–1.2); stability; robustness budget; conformal coverage within ±2 pp; ODD document |
| **G2 Shadow** (≥ 14 daily epochs) | 100 % of would-be orders pass a gateway dry-run (schema, authority, evidence ingested); alert volume within budget; disagreements with the champion reviewed; no ODD-violation surges |
| **G3 Fork evaluation (CRN)** | snapshots at ≥ 3 epochs across regimes; StatusQuo vs champion vs challenger on the same exogenous members; ≥ 20 pairs by power analysis; **superiority on the primary KPI** (lower 95 % CI of Δmc > 0, or ≥ −δ when justified by cost); **safety KPIs strictly non-inferior** (Δ in_flight_failures upper CI ≤ ε); secondary KPIs with Holm correction; zero HUMAN-only actions attempted by AGENT; oracle-world forks as evaluation, **belief-mode** forks reported too |
| **G4 Human approval** | named role independent of the model author signs the bundle |
| **G5 Canary** | one squadron for K epochs; auto-rollback on harmful-shift test, alert-rate budget breach, gateway rejection rate > ε, or kill-switch; rollback = alias swap to `@previous_champion` + LEL event |
| **Mandatory demotion** | any new release, contract or dictionary hash moves the champion to REVALIDATION_REQUIRED; G0–G1 re-run automatically; G3 if features changed |

Gates may return **INSUFFICIENT_EVIDENCE**, distinct from pass/fail — essential on the preview, where several
targets have no positive class. Every model trained on v0.9 carries `data_maturity=PREVIEW`, can reach CHAMPION
only in the demo environment, and is forced to REVALIDATION_REQUIRED when calibrated data lands.

## Drift: separate known regime change from surprise

- **Taxonomy:** covariate drift P(X), concept drift P(Y|X) (e.g. BIT maturity changes what a code means), prior
  shift P(Y) (dusty season), and schema/contract change (a gate failure, not drift).
- **Known change-points are annotations, not alarms.** A change-point registry is populated automatically from
  `maint.records` (MODIFICATION, COMPONENT_LIFE), `orders.commands` (LOAD_SOFTWARE, CHANGE_MONITORING_CONFIG,
  WASH_SERVICE) and upstream release events. Drift reference windows are segmented at change-points; per-serial
  baselines reset (engine-condition-monitoring practice: re-baseline after removal/reinstallation, CUSUM trend
  reset after alerting — Bechhoefer, HUMS 2023); inside a settling window after a known change, alarms route to
  EXPECTED_SHIFT_REVIEW; if the new regime is outside the model's ODD, recommendations are demoted to advisory.
- **Only harmful shifts page anyone:** Podkopaev & Ramdas (ICLR 2022) sequential tests flag shifts that *raise
  risk*; conformal test martingales (Vovk) for "retrain or not"; Rabanser et al. (NeurIPS 2019) for detection
  methods; BBSE label-shift correction (Lipton et al., ICML 2018).

| Signal | Action |
|---|---|
| Contract/schema hash not allowlisted | quarantine (gate) |
| Feature drift, no estimated loss, no known change | log, widen monitoring |
| Drift aligned with a known change-point | re-baseline; recalibration check; ODD review |
| Inputs outside ODD | abstain / human review on affected tails |
| Score drift + label-free performance drop | human review; prepare rollback |
| Calibration error rises (labels matured) | recalibrate → new version, fast-track gates |
| Harmful-shift test fires | suspend champion → rule-based fallback policy; retrain |
| Alert rate per FH above budget | threshold review (alert-fatigue risk) |

## Learning from delayed, noisy outcomes

- **Labels are events** with `t_valid` (when the condition held), `t_known` = `t_ingest` of the outcome record,
  source `record_id`s and a confidence class; revisable when a record version changes. Targets kept separate:
  (a) symptom present / maintenance-worthy, (b) component confirmed faulty (CONFIRMED only), (c) time-to-event.
- **Censoring** handled by survival framing ([05](05-prediction.md)); a hand-weighted rule label model (Snorkel-style
  weak supervision is optional).
- **Truth is used only offline** to *measure* proxy-label noise — exactly the evidence DA-04/DM-02 ask for.
- **Active learning = choosing inspections:** ground-inspection-class states are observable only through
  INSPECT orders, so an inspection is a label query with a cost; rank by expected information gain per man-hour
  and evaluate the inspection policy itself on forks.
- **Retraining is event-driven with a calendar backstop:** new release/contract/dictionary → revalidate; N matured
  labels (e.g. ≥ 30 outcomes); harmful-drift or calibration alarm; enough post-change-point data; monthly.
- The preview-trainable, label-rich target that exercises the whole loop now: **P(BIT-triggered defect is
  confirmed vs CND/RTOK)**.

## CMMS: integrate, don't replace

A CMMS is the system of record for assets, work requests and orders, preventive schedules, labour, parts and
history (ISO 55000 asset-management context). The IAF's e-MMS is IBM Maximo-based (public reporting; Wipro as
integrator). The enterprise **APM pattern** is insight → work request → approved work order in the CMMS.
Installing a second CMMS would contradict the PS ("not adequately integrated").

- **Build a thin CMMS view**, not a CMMS: a projection over `maint.records` (latest version per key, as of t),
  joined with our issues, recommendations and orders.
- **Work-request outbox adapter** emitting Maximo-shaped work requests (status mapping: OPEN ↔ WAPPR/APPR/WSCH,
  AWP ↔ WMATL, AWM/DEFERRED ↔ WSCH/WPCOND, IN_WORK ↔ INPRG, CLOSED ↔ COMP→CLOSE). In the simulator the "CMMS
  write" is an `orders.commands` row; in production it would be a Maximo integration call.
- **Interop vocabulary:** ISO 13374 / MIMOSA OSA-CBM's six blocks map onto our modules — Data Acquisition =
  contract ingest; Data Manipulation = as-of store and conditioning; State Detection = monitoring; Health
  Assessment = per-serial health; Prognostic Assessment = prediction; Advisory Generation = recommendation and
  order.
- Rejected: Atlas CMMS (AGPL, no aircraft configuration management), Odoo Maintenance (drags in Odoo), openMAINT
  (facility focus), Fiix/UpKeep (SaaS).

## Monitoring and provenance

Panels: data health per release; drift segmented by change-points; ODD coverage; score and alert rate per FH;
label-free performance estimate (our own ~50-line CBPE — NannyML has been inactive since Jul 2025); matured-label
performance and calibration by base/regime/`sw_config`; gateway outcomes (REJECTED reasons); fork KPI deltas of
the champion vs status quo. Lineage as **OpenLineage-shaped events in the LEL** (no Marquez server — releases
stalled since Oct 2024).

**Decision provenance:** every recommendation event carries model and policy versions, feature/label spec hashes,
`as_of`, evidence `record_id`s, `release_id`, contract and dictionary hashes, fork evaluation ids and the
approving human. "Why was order X issued?" is one query; replaying the order log in Phalanx reproduces the world
bit for bit.

## Tool picks

| Need | Pick | Licence | Rejected |
|---|---|---|---|
| Storage / as-of | DuckDB + pyarrow over Parquet | MIT | Feast, XTDB, Kafka |
| Data gates | data layer `Contract.validate` + pandera | team / MIT | Soda v4 (ELv2), deequ |
| Registry / tracking | **MLflow 3.x** (SQLite + file store; aliases `@shadow`, `@challenger`, `@champion`, `@previous_champion` set only by the gate service after the LEL event) | Apache-2.0 | ClearML (SSPL server), W&B (licensed server) |
| Drift reports | Evidently 0.7 | Apache-2.0 | alibi-detect (BSL 1.1) |
| Streaming detectors | river (ADWIN, Page–Hinkley on alert rates and residuals) | BSD-3 | stale libraries |
| Survival / conformal | lifelines, PyMC, MAPIE | MIT / Apache / BSD-3 | scikit-survival internal only (GPL-3) |
| State machines | python-statemachine 3.x | MIT | XState (UI only) |
| Event log | own append-only table + blake2b hash chain | — | immudb (BSL), Kafka |
| Policy evaluation | data-layer ForkService (belief mode in loop) | team | custom simulators |

## Prototype scope

**Skip:** Feast/XTDB/Kafka, Marquez, Kubernetes, MLflow multi-user auth, GX Data Docs, Snorkel, formal
generalisation bounds, Merkle trees, installing any CMMS, streaming everything.
**Keep — these carry the story:** the release gate including the live 0.1.0 → 0.2.0 / dictionary 0.1.3 bridge and
aborted-run tagging; the as-of store with the shuffle-the-future test; the model state machine with MLflow aliases
and rollback; the CRN fork gate vs StatusQuo; change-point-annotated drift ("expected shift after a software load"
vs a true alarm); the outcome → label → retrain loop on BIT confirmation; the hash-chained LEL with one-click
"why was this order issued?"; one table mapping EASA objective IDs, SHIELD, NIST and ETAI to these mechanisms.

## Key sources

- EASA AI Concept Paper Issue 02 — https://www.easa.europa.eu/en/document-library/general-publications/easa-artificial-intelligence-concept-paper-issue-2 ; Proposed Issue 03 — https://www.easa.europa.eu/en/newsroom-and-events/news/easa-releases-latest-issue-its-concept-paper-artificial-intelligence ; NPA 2025-07 — https://www.easa.europa.eu/document-library/notices-of-proposed-amendment/npa-2025-07
- MLEAP final report — https://www.easa.europa.eu/en/newsroom-and-events/news/artificial-intelligence-easa-publishes-final-report-machine-learning
- DRDO ETAI — https://indiaai.gov.in/news/trustworthy-ai-framework-launched-for-critical-defence-operations
- DoD RAI Toolkit / SHIELD — https://www.ai.mil/docs/ADOD24/DAGR_SHIELD_and_the_DoD_RAI_Toolkit.pdf ; NIST AI RMF — https://doi.org/10.6028/NIST.AI.100-1
- HUMS for credit (EASA IP170) — https://www.easa.europa.eu/download/imrbpb/IP170%20R0%20HUMS%20for%20credit.pdf
- MLflow registry & stages deprecation — https://mlflow.org/docs/latest/ml/model-registry/ ; https://github.com/mlflow/mlflow/issues/10336
- Evidently — https://docs.evidentlyai.com/metrics/customize_data_drift ; river — https://riverml.xyz/latest/api/overview/
- Rabanser et al. "Failing Loudly" — https://arxiv.org/abs/1810.11953 ; Podkopaev & Ramdas — https://arxiv.org/abs/2110.06177 ; BBSE — https://arxiv.org/abs/1802.03916
- Bechhoefer, HUMS 2023 — https://www.humsconference.com.au/Papers2023/7_HUMS_Data_Science_and_Analytics_7_4_Bechhoefer.pdf
- DuckDB ASOF JOIN — https://duckdb.org/docs/current/guides/sql_features/asof_join.html ; Fowler, bitemporal history — https://martinfowler.com/articles/bitemporal-history.html
- IBM Maximo work-order statuses — https://www.ibm.com/docs/en/maximo-manage/continuous-delivery?topic=orders-work-order-statuses ; MIMOSA OSA-CBM / ISO 13374 — https://www.mimosa.org/mimosa-osa-cbm/
- OpenLineage — https://openlineage.io/docs/ ; RFC 6962 — https://www.rfc-editor.org/rfc/rfc6962
- Breck et al., The ML Test Score — https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/
