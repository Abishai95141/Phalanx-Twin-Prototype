# 13 · Decision register and challenged ideas

Every major architectural decision, the alternatives considered, the deciding evidence and its status. "Revisit
when" names the evidence that would change it. Detailed rationale and sources live in the linked docs.

## Ideas we challenged (from the original brief)

| # | Original idea | Outcome | Deciding evidence | Doc |
|---|---|---|---|---|
| C1 | Availability is lost mostly while waiting; value comes from acting earlier | **Confirmed with refinement:** waiting dominates (supply, depot, decision and coordination waits), but the recoverable waiting has three sources — inventory policy, self-inflicted NFF demand, capacity queues; prediction pays only where its lead time beats the response lead time; the cheapest "earlier" is often visibility and selectivity | CAG 38/2015, 24/2017; GAO/DOT&E F-35; USN Super Hornet turnaround; preview decomposition (NMCS 50 %, tyres 37 % of downtime, all FADEC/HYDP AOG waits from healthy removals) | [01](01-problem-stakeholders-kpis.md), [06](06-prescription-and-planning.md) |
| C2 | Organise by descriptive / diagnostic / predictive / prescriptive | **Changed:** organise by stakeholder decision workspaces; the four tiers are the capability spine with visible badges | Skywise, AVIATAR, PANDA, Navy MOC are workflow-cut; ALIS failed on data trust, not missing tiers; Gartner's move to decision intelligence | [01](01-problem-stakeholders-kpis.md), [11](11-ui-ux.md) |
| C3 | Full 3D mock of the aircraft as the digital-twin screen | **Kept, constrained:** 3D is a spatial index and lens over the twin state with six acceptance tests; numbers live in linked 2D panels; our own stylised segmented model, watermarked synthetic | HCI evidence on 2D vs 3D (St. John 2001, Tory 2006, Cockburn 2002, Munzner); industry health monitoring is 2D; model licences (only one uncertain CC BY Tejas mesh) | [02](02-digital-twin.md), [11](11-ui-ux.md) |
| C4 | Transformer time-series models such as TimesFM 3 | **Demoted to a baseline row:** TimesFM-3 weights are non-commercial/non-production; TSFMs do not handle censoring, competing causes, first-passage or maintenance resets; leaderboard claims self-reported and contaminated; for anomaly detection they match one-line baselines | TimesFM-3 licence; Hyndman 2026; Meyer et al. 2025; ICLR 2026 "one-liners"; TSB-AD | [05](05-prediction.md), [04](04-condition-monitoring-and-diagnostics.md) |
| C5 | A triage system | **Kept, re-unitised:** the unit is an issue (episode), not an alert; non-compensatory gates then an AP-style C × U lookup, never RPN | preview: 1,325 alert rows → 348 issues; ISA-18.2/IEC 62682; AIAG-VDA AP vs RPN; ESI/NEWS2 | [07](07-triage-policy-decision-loop.md) |
| C6 | "Something like ZEN" for policies | **Kept for organisational and decision policies;** hard constraints are tested Python invariants | GoRules ZEN (MIT, Rust, Python, traces); determinism traps (`d()`, JS function nodes); no gap/overlap analysis | [07](07-triage-policy-decision-loop.md) |
| C7 | A deterministic agentic loop | **Renamed and constrained:** a deterministic MAPE-K control loop; no LLM in any decision step | replayability, DoD "traceable/governable", EASA assurance | [07](07-triage-policy-decision-loop.md) |
| C8 | Feedback loop that does not pressure the user | **Kept:** cadence-bound, optional one-tap reasons, learning offline per rule, outcome-based quality (not acceptance rate) | automation bias (Parasuraman & Manzey 2010); override studies; Wickens 2009 | [07](07-triage-policy-decision-loop.md) |
| C9 | ML lifecycle features (promotion, drift, state machines, gates, CMMS, registry, pipeline, monitoring, audit) | **Unified:** one hash-chained Lifecycle Event Log; every lifecycle a state machine on it; registry/CMMS/audit as projections; EASA offline-learning (frozen versions) | EASA Concept Paper Issue 02 objectives; DRDO ETAI; Phalanx's own event sourcing | [08](08-learning-and-assurance.md) |
| C10 | A CMMS | **Integrate, don't replace:** thin CMMS view + Maximo-shaped work-request outbox | IAF e-MMS is Maximo-based; APM pattern; PS "not integrated" | [08](08-learning-and-assurance.md) |
| C11 | Graph systems for isolation, relationships, applicability, more | **One curated property graph** (DuckDB + NetworkX); GraphRAG, GNNs, causal discovery, OWL rejected | 777 CMC/TEAMS pattern; GraphRAG-Bench; data size and structure | [09](09-knowledge-graph.md) |
| C12 | Local AI assistant with read access to everything | **Kept as a constrained analyst:** typed read-only tools, render-by-reference numbers, belief-only forks, drafts only, dashboards stay the source of truth | BFCL multi-turn weakness; text-to-SQL accuracy; prompt-injection risks; NIST CAISI | [10](10-assistant.md) |

## Architecture decisions

| ID | Decision | Alternatives considered | Why | Status | Revisit when |
|---|---|---|---|---|---|
| D01 | Build strictly on the frozen contract (0.2.0) with a hash allowlist; read by column name | reading internal simulator outputs | P5 real-data readiness; contract owner's validator | adopted | contract major bump |
| D02 | Bitemporal as-of store in DuckDB over Parquet; `as_of(t)` as the only read API | Feast, XTDB, Postgres/Timescale, Kafka | MIT, embedded, sub-second on 163 M rows; Feast default leaks late backfills | adopted | multi-user production deployment |
| D03 | Scoped identity (`tail_no` as world scope) for the preview | global `record_id` dedupe | 3,388 colliding maint records; serials/jobs/orders reused across worlds | adopted (temporary) | shared-world fleet (W2.6) |
| D04 | Component registry YAML as the single crosswalk (mesh ↔ LRU ↔ suspect ids ↔ part no ↔ system code ↔ channels ↔ zones) with build-time tests | ad-hoc mapping in UI code | makes "3D connected to data" a testable property; resolves naming conflicts | adopted | — |
| D05 | Twin = asset + fleet + simulation twins over a belief state; the simulator is the world, not our twin | presenting simulator state as the twin | AIAA/NASEM definitions; Kapteyn et al. PGM; avoids label leak | adopted | — |
| D06 | Event/BIT/NFF intelligence as the first diagnostic engine | parameter anomaly detection first | data is event-dominated; NFF is the measured pain; demonstrable on v0.9 | adopted | — |
| D07 | Physics/baseline residuals + EWMA/CUSUM/GLR/PCA for parameter health | deep TSAD, TSFMs, MSET2 | ProDiMES, TSB-AD, TimeEval; MSET2 proprietary | adopted (phase 2 Kalman/tuner) | B7 signatures validated |
| D08 | D-matrix + leaky noisy-OR isolation, learned from outcomes; never copy simulator catalogue/graph | GDE, GNN, causal discovery | 777 CMC / TEAMS practice; data-light; honest | adopted | ≥ 50 CONFIRMED findings |
| D09 | Explicit sensor-vs-component layer with "undetermined" | ignore the confound | NASA TM-4551; the data layer scores it | adopted | A/B lanes in consumer data |
| D10 | Bayesian hierarchical cause-specific Weibull AFT for removal hazard | Cox only, RSF/GBM survival, DeepSurv/DeepHit | 0–5 failures per class; censoring/truncation/competing causes | adopted (GBM challenger at ≥ 50 events) | event counts grow |
| D11 | State-space (Wiener/gamma, UKF/PF) engine health prognostics | C-MAPSS-style deep RUL | irregular sparse snapshots; no run-to-failure labels | adopted for phase B | health indicator available |
| D12 | Structural availability-conditioned usage model; reliability-based spares demand | univariate forecasting, TSFMs | preview: corr 0.74 with MC; MAE 4.8 → 1.65 with known availability | adopted | — |
| D13 | TSFMs only as Apache-2.0 zero-shot baselines; no TimesFM-3 in product | TimesFM-3 as core | licence; task mismatch; contaminated benchmarks | adopted | licence change + backtest wins |
| D14 | Expected-cost decision rules with VOI for inspections | fixed thresholds only | decision theory; POD < 1; explainable | adopted | — |
| D15 | CP-SAT rolling-horizon flight-and-maintenance plan; opportunistic grouping per tail now | one-shot MIP, metaheuristics, RL | air-force FMP literature; scale limits of one-shot | adopted (fleet after W2.6) | shared-world fleet |
| D16 | Single-site METRIC marginal analysis + consumable reorder points | multi-echelon VARI-METRIC, Croston-only | military practice; single-echelon simulator | adopted | multi-echelon supply in the simulator |
| D17 | No reinforcement learning | deep/multi-agent/offline RL | no deployment evidence; sample cost; artefacts; explainability | rejected | validated simulator + long logs |
| D18 | Fork gate: belief-mode CRN forks with KN/OCBA; oracle/ensemble only offline | ensemble forks in the loop | unsafe defaults in the fork API; optimizer's curse | adopted | — |
| D19 | Triage unit = issue; gates → C × U lookup → value; ISA-18.2 states; load KPIs | per-alert queue, RPN scores | preview load; alarm-management standards | adopted | — |
| D20 | Four-layer policies: Python invariants, ZEN (org + decision), YAML preferences; policy lifecycle with fork evaluation | everything in a rules engine; DMN/Drools; OPA | determinism, editability, testability | adopted | — |
| D21 | Deterministic MAPE-K daily epoch (06:00 snapshot, 07:45 freeze, 08:00 submit); consent by default; exception mode per rule after canary | LLM agent loop; full automation | replay, authority matrix, automation-bias evidence | adopted | — |
| D22 | Deterministic, content-addressed order ids including tail and evidence hash | data-layer reference ids | idempotent retries; fixes preview collision | adopted | — |
| D23 | One hash-chained Lifecycle Event Log; registry/CMMS/audit as projections | separate stores per feature | EASA CM-01/EXP-09; Phalanx event sourcing | adopted | — |
| D24 | MLflow 3 registry (aliases), Evidently, river, pandera, python-statemachine | ClearML (SSPL), W&B, alibi-detect (BSL), NannyML (inactive), Soda (ELv2) | licences, activity, air-gap | adopted | — |
| D25 | Promotion gates G0–G5 incl. CRN fork superiority and safety non-inferiority; INSUFFICIENT_EVIDENCE outcome; preview models capped at demo | accuracy-only gates | EASA learning assurance; preview reality | adopted | — |
| D26 | Known change-points (software loads, mods, releases, washes, installs) segment drift monitoring | generic drift alarms | ECM re-baselining practice; alert fatigue | adopted | — |
| D27 | Curated knowledge graph in DuckDB tables + NetworkX; LadybugDB optional | Neo4j, Memgraph (BSL), FalkorDB (SSPL), Kùzu (archived) | size < 10k nodes; licences; air-gap | adopted | graph > 10⁶ edges |
| D28 | Assistant: gpt-oss-20b default via llama.cpp; Gemma 4 / Granite 4.1 step-up; Qwen as comparator only; chosen by our golden set | text-to-SQL agent, GraphRAG, Chinese-origin default | licences, sovereignty perception, eval evidence | adopted | MoD procurement guidance |
| D29 | UI: seven decision workspaces + 3D twin + assistant drawer; same five-part card everywhere | tier-named navigation; chat-first home | stakeholder research; SA design; HAX guidelines | adopted | user testing |
| D30 | 3D stack: React + three.js + R3F + drei; own Blender model; 2D SVG fallback from the same registry | xeokit (AGPL), Babylon, model-viewer | licences; node-level picking; React state sharing | adopted | — |

## Questions for the data-layer team (blocking or shaping decisions)

1. Cross-repo interface for orders and forks (in-process only today) — shapes D18, D21, deployment.
2. Shared-world fleet (W2.6) timeline — unblocks D03 removal, D15, D16 pooling, cannibalisation.
3. Persistent faults and CONFIRMED outcomes (W2.5b) — unblocks D08/D10 true-fault parameters.
4. Vibration/oil-debris observability and `MX.*` inspection transport — shapes D11.
5. A/B lanes in consumer `param.samples` — unblocks D09 lane checks.
6. Fix or document: cross-world collisions, null-tail SHOP_FINDING, narrative vs dictionary code mismatch,
   `ENG.T5` floor without a flag, constant `detection_far_per_fh`, unsafe fork defaults, planned flight hours not
   in the contract (full list in [03](03-data-foundation.md)).
