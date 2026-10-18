# 07 · Triage, policies and the deterministic decision loop

This is where intelligence becomes decisions. Three parts, one loop:
- **Triage** turns findings into a short, ranked list of *issues* a human can act on.
- **Policies** turn issues into candidate actions under explicit, versioned rules.
- **The decision loop** runs once per daily epoch, deterministically, with a human gate before any order.

## What we changed from the original idea

| Team idea | Decision | Why |
|---|---|---|
| A triage system for alerts | **Yes — but the unit is an issue (episode), not an alert** | On the preview, 1,325 alert rows (1,021 BIT + 304 cautions) collapse to **348 issues**; a per-alert queue would recreate the alert fatigue the PS complains about |
| "Something like ZEN" for policies | **Yes — GoRules ZEN Engine for organisational and decision policies only** | Hard constraints (airworthiness, authority, information discipline) are invariants written in tested Python mirroring the gateway, not planner-editable rule files |
| "Deterministic agentic loop" | **A deterministic MAPE-K control loop; we drop the word "agentic"** | "Agentic" signals an LLM planner; LLM outputs are not replayable and cannot sit in an airworthiness-adjacent decision path. LLMs only *around* the loop (explanations, text normalisation, authoring aid) |
| Feedback that doesn't pressure the user | **Yes — cadence-respecting, optional one-tap reasons, outcome-based learning** | Learning needs reasons, but nagging creates override fatigue; learn from outcomes and forks, review per rule with policy owners |
| Controlled, explainable recommendations | **Yes — plus "why not", evidence links, counterfactuals** | Judge quality by outcomes, not acceptance rate — automation bias inflates acceptance (Parasuraman & Manzey 2010) |

---

## Part A · Triage

### Load calibration on the preview (8 tails × 180 days, BIT regime immature)

| Quantity | Value |
|---|---|
| BIT events per FH | 1.88 (0.53 FH between events — inside the immature 0.1–1 FH band) |
| BIT events per tail per flying day | 2.2; 81 % of sorties had ≥ 1 BIT event |
| Cautions | 304 — **all share `event_id` with a PFL BIT event** (same occurrence in two topics) |
| Issues (tail, code, chained within 10 days) | **348** from 1,021 events; 51 % occur once; 170 recur ≥ 2×; 99 ≥ 3× |
| New issues per epoch | mean 1.9, p95 6, max 18 |
| Same code on ≥ 3 consecutive flights | 8.2 % of runs; longest HYD-101 on TJ107, 42 flights (a standing alarm) |
| Concentration | 27 codes; top 10 = 81 % of events ("bad actors") |
| Status-quo response | 687 BIT-evidenced jobs → 398 CND, 171 deferred-and-admin-closed, 92 R/R; 58/58 shop findings RTOK |
| No-fault labour | 3,154 of 6,270 defect man-hours (50 %) |
| Reference CBM rule "≥ 2 in 10 days → troubleshoot" | would fire ≈ once per epoch — almost always for nothing |

### What we borrowed, and from where

| Source | What transfers | What doesn't |
|---|---|---|
| ISA-18.2 / IEC 62682:2022 / EEMUA 191 Ed. 4 (2024) alarm management | rationalisation (every alarm needs a consequence and a required action); priority from **consequence × time available**; shelving / suppressed-by-design / out-of-service states; load KPIs (≈ 80/15/5 priority mix, flood, chattering, stale, bad actors) | seconds-to-minutes operator timescales — our "operator" decides once a day, so KPIs are per epoch |
| MIL-STD-882E | routing approval authority by risk level | design-time hazard method without an urgency axis |
| MIL-STD-1629A FMECA; AIAG-VDA Action Priority (2019) | FMECA effect → consequence column; **AP lookup tables, not RPN** (RPN multiplies ordinal scales and masks severity: S10/O1/D1 = 10 < 4/4/4 = 64) | — |
| MEL categories / USAF MESL (DAFI 21-103) | consequence is **mission-type dependent**; every deferral carries a category, limit and conditions | — |
| Clinical ESI v5 and NEWS2 | ordered **hard gates before any score**; a non-compensatory single-parameter override ("red score"); resources as an axis; each band names a responder | patients arrive once; our issues are chronic |
| Google SRE, Prometheus Alertmanager | every page actionable; grouping, **inhibition** (parent mutes children), time-bound silences, re-surfacing intervals | LLM "AIOps" correlation (not in a decision path) |
| Alert-fatigue evidence | 72–99 % of clinical alarms false (Sendelbach & Funk 2013); 88.8 % false arrhythmia alarms (Drew et al. 2014); **Wickens et al. 2009: 45 % false ATC alerts but no cry-wolf effect when alerts are understandable** → show *why* each item is surfaced, with base rates | — |

### Issue construction (deterministic)

| Step | Rule |
|---|---|
| D1 | Dedupe by (topic, scope, `record_id`), earliest `t_ingest` (the preview collision fix) |
| D2 | BIT + caution rows sharing `event_id` = one occurrence |
| D3 | Same (sortie, code) collapses with a count |
| D4 | Same (tail, code) within 10 days (by `t_ingest`) appends to the open issue |
| D5 | Same tail + sortie with the same top suspect LRU/serial → one issue |
| D6 | **Inhibition:** bus/power-supply codes mute dependent LRU BIT fails in the same sortie (via the graph, [09](09-knowledge-graph.md)) |
| D7 | **Suppressed by design:** for 10 sorties after a completed LOAD_SOFTWARE, ADVISORY/MFL codes on that LRU are recorded but not surfaced — unless WARNING/PFL or persistent ≥ 3 flights past the burst |
| D8 | **Standing/chatter:** persistence ≥ 5 flights with ≥ 2 prior CND outcomes → "nuisance review" for the engineering owner (who may issue a HUMAN-only CHANGE_MONITORING_CONFIG) |
| D9 | **Stale:** MONITORING with no new evidence for 3 flights or 10 days → auto-close "no recurrence" |

### Score: gates → lookup → ranked value (never a single opaque number)

1. **Gates → P1 (non-compensatory):** a WARNING/PFL code; an open grounding defect or exceedance inspection; a
   hard-time/limit breach within the planning horizon; a model P(failure before next servicing) above a critical
   threshold on a safety-critical item.
2. **AP-style lookup, Consequence C × Urgency U → P2/P3/P4:**
   - **C** from the FMECA effect and our MESL table for the *planned* mission types: 3 NMC, 2 PMC on planned
     missions, 1 PMC only on unplanned missions, 0 MFL with no effect.
   - **U** from the **time-to-act margin** M = T_fail,q10 − (T_lead + T_epoch + T_work): the 10th-percentile time
     to failure from the health posterior (calendar days at planned utilisation) minus the spares lead-time
     quantile, epoch delay and work duration. U3 if M < 0, U2 if 0–3 d, U1 if 3–14 d, U0 > 14 d.
3. **Rank within band** by expected NMC-days avoided = P(true \| evidence) × (NMC-days if unplanned − NMC-days if
   planned) − weighted cost. P(true \| evidence) starts from the code's outcome-learned prior (shrunk to the fleet
   rate, sample size shown) and is updated by persistence, corroboration and model output ([04](04-condition-monitoring-and-diagnostics.md)).
   **Confidence** (sample size, model agreement, data-quality flags) is shown; low confidence → MONITOR with an
   explicit re-check trigger, never silent suppression. Deterministic tie-break on `issue_id`.

### Issue states (ISA-18.2-inspired; `python-statemachine`)

`NEW → TRIAGED → ACKNOWLEDGED →` { `MONITORING` (explicit trigger) | `DEFERRED` (linked DEFER order with limits) |
`SHELVED` (human, time-bound, auto-unshelve) | `SUPPRESSED_BY_DESIGN` (D6/D7) | `OUT_OF_SERVICE` (HUMAN
CHANGE_MONITORING_CONFIG) | `MERGED` | `PROPOSED → APPROVED → ORDERED → IN_WORK → RESOLVED{CONFIRMED|CND|RTOK} →
CLOSED` (after 3 clean flights) } ; `REOPENED` on recurrence within 30 days (flagged REPEAT).

### Alert-load KPIs (per squadron board per epoch; start values from the preview)

| KPI | Target / alarm |
|---|---|
| Items needing a decision | median ≤ 5, p95 ≤ 10 (preview ≈ 2.9 per epoch for 8 tails after dedup); > 2× budget → **flood mode**: only P1/P2 individually, the rest grouped by root cause |
| Band mix | ≈ 5 % P1+P2, 15 % P3, 80 % P4; drift alerts the policy owner |
| Bad actors | top-10 codes' share (preview 81 %; > 20 % signals nuisance codes) |
| Standing / stale / shelved | counts and ages, audited weekly; unauthorised suppression = 0 |
| Escalation precision | escalated issues ending CONFIRMED ÷ escalated with outcome |
| Misses | unscheduled NMC / AOG events with no prior escalation at margin ≥ lead time |
| No-fault labour | man-hours on no-fault jobs per FH (preview ≈ 5.8) |

---

## Part B · Policies

### Four layers, strict precedence (higher always wins)

| Layer | Content | Where it lives | Who edits |
|---|---|---|---|
| 1 · Hard constraints (invariants) | authority matrix (read from the data layer's `authority.yaml`, never forked); `t_issued` = session time; evidence ingested; parameter schema; no RELEASE with open grounding defect; no DEFER of a grounding defect; servicing extension ≤ 20 % HUMAN-only | **typed Python**, unit-tested to mirror the gateway and M18 | engineers via code review |
| 2 · Regulatory / organisational | servicing intervals; MEL-like deferral categories and limits; cannibalisation rules; mission-essential lists (our MESL) | **ZEN JDM decision tables** in git | Engineering Officer (policy owner) |
| 3 · Decision policies | when to inspect / troubleshoot / remove given evidence; every threshold tagged ASSUMPTION with a sweep range | **ZEN JDM** | policy owner, via the policy lifecycle |
| 4 · Preferences | tie-break weights (NMC-day, man-hour, CANN, AOG demand) with schema-enforced ranges; never override 1–3 | typed YAML | planners within bounds |

### Policy engine choice

| Option | Verdict |
|---|---|
| **GoRules ZEN Engine** — MIT; Rust core, native Python wheels; JSON Decision Model (decision tables with `first`/`collect` hit policies, switch, expression nodes, sub-decisions); `evaluate(input, {"trace": true})` returns each node's input/output; embeddable MIT `jdm-editor` React component; zen-engine 2.1.3 (Oct 2026), 2.0 released Aug 2026 | **Adopt for layers 2–3.** Caveats: single-vendor governance (no external contributions; MIT lets us fork); versioning/audit are commercial features → we do them in git + our event log; **determinism traps**: zero-argument `d()`/`isToday()` read the clock and Function nodes run JavaScript → banned by CI lint; no built-in gap/overlap analysis → our own property test |
| OMG DMN 1.5 (Drools/Kogito, Camunda) | the best standard, with gap/overlap analysis and seven hit policies — but JVM-only; Python options implement only part of S-FEEL. **Borrow its hit-policy discipline and gap analysis idea** |
| Open Policy Agent (Rego) | excellent **decision-log model** (decision_id, input, result, bundle revision) — we copy it; wrong tool for planners' tables |
| AWS Cedar | authorisation only; could encode the authority matrix, cannot compute a recommendation |
| json-logic, Drools DRL, durable_rules | too low-level / opaque / unmaintained (durable_rules last release 2020) |

### Example policy (ZEN JDM, abridged) — P-DEC-01 "recurring deferred BIT code"

Hardens the reference rule (≥ 2 in 10 days, A-W1.8-22, sweep 2–5) for a CND-dominated regime:

```json
{"contentType":"application/vnd.gorules.decision",
 "nodes":[
  {"id":"in","type":"inputNode","name":"issue"},
  {"id":"dt","type":"decisionTableNode","name":"P-DEC-01 recurring deferred BIT",
   "content":{"hitPolicy":"first",
    "inputs":[{"id":"sev","field":"severity"},{"id":"job","field":"job.status"},
              {"id":"n10","field":"occ_10d"},{"id":"cons","field":"consec_flights"},
              {"id":"co","field":"corroborated"},{"id":"cnd","field":"code.nofault_rate"}],
    "outputs":[{"id":"act","field":"rec.action"},{"id":"band","field":"rec.band"},{"id":"why","field":"rec.rationale_id"}],
    "rules":[
     {"_id":"r1","sev":"'WARNING'","n10":">= 2","act":"'TROUBLESHOOT'","band":"'P1'","why":"'PFL_WARNING_RECURS'"},
     {"_id":"r2","job":"'DEFERRED'","n10":">= 2","co":"true","act":"'TROUBLESHOOT'","band":"'P2'","why":"'RECUR_CORROBORATED'"},
     {"_id":"r3","job":"'DEFERRED'","cons":">= 3","act":"'TROUBLESHOOT'","band":"'P2'","why":"'PERSIST_3_FLIGHTS'"},
     {"_id":"r4","job":"'DEFERRED'","n10":">= 2","cnd":"< 0.6","act":"'TROUBLESHOOT'","band":"'P3'","why":"'RECUR_LOW_NOFAULT_CODE'"},
     {"_id":"r5","job":"'DEFERRED'","n10":">= 2","act":"'MONITOR'","band":"'P4'","why":"'RECUR_NOFAULT_DOMINATED_REVIEW'"},
     {"_id":"r6","act":"'NONE'","band":"'P4'","why":"'NO_RULE'"}]}},
  {"id":"out","type":"outputNode","name":"rec"}],
 "edges":[{"sourceId":"in","targetId":"dt"},{"sourceId":"dt","targetId":"out"}]}
```

Other policies: **P-DEC-02** same engine serial ≥ 2 exceedances in 30 days → INSPECT BORESCOPE (P2);
**P-ORG-01** MEL-like deferral limits (grounding/WARNING → not deferrable; CAUTION/PFL mission-essential → ≤ 10 FH;
ADVISORY/MFL → ≤ 25 FH — assumptions swept on forks); **P-ORG-02** cannibalise only from an already-NMC donor when
AWP ≥ the minimum (else expedite/transfer); **P-ORG-03** DEFER_SERVICING only as a HUMAN-signed draft.

### Conflict detection

- **Static (CI):** enumerate each table's input grid → report **gaps** (no rule matches) and **overlaps** (several
  rules under a "unique" intent), copying Drools' DMN analysis.
- **Dynamic (per tail per epoch):** an action-pair conflict matrix (GROUND vs ASSIGN_SORTIE, DEFER vs TROUBLESHOOT
  on the same job, RESTRICT_USAGE vs an AB-needing mission). Resolution: layer precedence → safety-conservative
  action wins (Cedar-style "forbid overrides permit") → otherwise a human decides.

### Policy lifecycle (policy-as-code)

`DRAFT → TESTED → SHADOW → FORK-EVALUATED → CANARY → ACTIVE → RETIRED`
- TESTED: golden input/output cases + gap/overlap test + replay test.
- SHADOW: evaluated every epoch, logged, not shown.
- FORK-EVALUATED: CRN-paired **belief-mode** forks vs the incumbent and StatusQuo, KPI deltas with CIs.
- CANARY: one squadron, or shown but not the default.
- Every transition is an event signed by a human approver. `policy_version = "<name>/<semver>+jdm.<sha256[:12]>"`;
  the pinned `zen-engine` version is stored in every decision record.

The policy lifecycle and the model lifecycle ([08](08-learning-and-assurance.md)) are the **same state machine
pattern on the same event log** — promotion of a rule and promotion of a model are governed identically.

---

## Part C · The deterministic decision loop (MAPE-K)

MAPE-K (Monitor–Analyze–Plan–Execute over shared Knowledge; Kephart & Chess, IEEE Computer 2003) is the right
frame: a closed control loop with explicit shared knowledge and a defined actuation interface — for us, orders.
OODA (Boyd) is useful vocabulary for military judges ("Orient" = triage + models with uncertainty).

| Stage | Component | Deterministic contract |
|---|---|---|
| **K** | Lifecycle event log + twin state store + knowledge graph + policy bundle (hashed) + model artefacts (hashed) + `authority.yaml` from the data layer | content-hashed, append-only |
| **M** | Cut-off T_c = 06:00 IST: records with `t_ingest ≤ T_c`; gate G0; snapshot hash = H(sorted `record_id`s per topic) | no wall-clock reads; the epoch is the clock |
| **A** | Conditioning, monitoring, prediction → twin state; triage D1–D9 → issues; scoring | RNG seed = H(root, epoch, id); pinned library versions; single-threaded reductions |
| **P** | ZEN layers 2–3 → candidate actions → prescriptive ranking ([06](06-prescription-and-planning.md)) → layer-1 shield → conflict resolution → belief-fork evaluation for P1/P2 or resource conflicts → recommendation + explanation | policy and engine versions recorded; outputs sorted |
| **Human gate** | 06:00–07:45 IST **decision board** (approve / modify / reject / snooze) | inputs logged as events with actor and time |
| **E** | 08:00 IST (`t_issued` = session time): submit the frozen order set; reconcile `orders.status`; outcomes via `result_record_ids` → K | idempotent order ids |

**Epoch run states:** `IDLE → SNAPSHOT → ANALYZE → PLAN → BOARD_OPEN → FROZEN → SUBMITTED → RECONCILED`; a crash
resumes from the last event, every step keyed by `epoch_id`. Hysteresis and minimum dwell times (escalate at the
2nd occurrence, de-escalate only after 10 days / 3 clean flights) stop recommendations oscillating.

### Approval modes (levels of automation per action; Parasuraman, Sheridan & Wickens 2000)

| Mode | Actions | Behaviour |
|---|---|---|
| **HUMAN-only** (data-layer authority) | EMBODY_MODIFICATION, LOAD_SOFTWARE, CHANGE_MONITORING_CONFIG, DEFER_SERVICING | system drafts; a human signs and issues as HUMAN; silence = nothing happens |
| **Consent** | GROUND, RELEASE, REMOVE_REPLACE, CANNIBALISE, RESTRICT_USAGE, ASSIGN_SORTIE changes, DEFER, BRING_FORWARD_SERVICING | issued only if approved before the freeze |
| **Exception** (per rule, only after CANARY evidence) | routine TROUBLESHOOT, INSPECT, WASH_SERVICE, REQUISITION, EXPEDITE, TRANSFER | auto-issued unless vetoed — **the demo starts with everything on consent** |

Consent is affordable because the daily epoch removes time pressure (Olson & Sarter 2001 found consent breaks
down under time pressure). Cognitive forcing (ask the human's judgement first; Buçinca et al. 2021) only for
GROUND/RELEASE and high-cost REMOVE_REPLACE. No auto-GROUND: airworthiness is enforced by M18 and the tech log.

### Order emission

- `order_id = "phx:<rule>:<policy semver>:<epoch YYYYMMDDTHHMM>:<tail>:<action>:<blake2b8(canonical params + sorted evidence)>"`
  — matches the contract pattern; re-running an epoch yields the same ids, so the gateway's DUPLICATE makes
  retries safe; including the tail fixes the preview's cross-world collision.
- Every order cites evidence `record_id`s (the reference scheduled policy issued orders with empty evidence; ours
  never do). A pre-submission dry-run uses the data layer's `OrderGateway.evaluate` (verdict without the
  idempotency step).
- A REJECTED order returns the issue to PROPOSED with the gateway's reason; no automatic retry loops.

### Where LLMs are allowed

**Never** in any step that changes issue state, scores, policy outputs, the order set or parameters — their
outputs are not bit-reproducible and cannot be audited against a frozen policy version (DoD "traceable,
governable"; EASA assurance framing). **Allowed around the loop, labelled:** plain-language summaries of the
deterministic trace that may cite only `record_id`s already in the trace (validator-enforced); normalising noisy
free text into *frozen, hashed* derived records (replay reads the cache); helping authors draft JDM tables offline
(which then go through the policy lifecycle); the read-only assistant ([10](10-assistant.md)).

---

## Part D · Explanations and non-pressuring feedback

**Every recommendation shows** (Liao et al. XAI question bank; Lim, Dey & Avrahami 2009; Miller 2019):
1. **Rule trace** — gates passed/failed, matched table row and rationale id, policy version/hash.
2. **Evidence** — every claim cites `record_id`s with their `t_ingest` (proving information discipline).
3. **Counterfactuals** — rule-level (smallest input change that flips the action: "with 1 occurrence instead of 2
   → MONITOR"; Wachter et al. 2018) and outcome-level from belief forks ("expected NMC-days over 30 d: act now
   0.4 [0.2, 0.7] vs defer 1.1 [0.6, 1.7]").
4. **Uncertainty with base rates** — P(true fault) as an interval with n, next to the code's base rate
   ("ENG-201: 0 of n confirmed; most jobs closed CND").
5. **Why not** — for each plausible alternative, the blocking reason (authority, airworthiness, stock, threshold,
   worse fork KPI), contrasted against status quo.

**Feedback without pressure:**
1. One board per epoch; no pushes except P1; recommendations expire at the epoch and are recomputed — no
   "N ignored" counters or badges.
2. Doing nothing = status quo, stated explicitly ("if you do nothing: …"). Reasons required only for P1 overrides
   and HUMAN-only approvals (audit).
3. One-tap, optional reason codes: R1 operational need, R2 resources, R3 evidence disputed / known nuisance, R4
   already done outside the system, R5 combine with next servicing, R6 other.
4. Snooze/shelve with re-trigger ("until next servicing", "after N flights", "if it recurs").
5. **Learn offline, not online:** a weekly packet to the *policy owner*, not the planner ("P-DEC-01 r4 overridden
   70 % with R3 on AVI-204; shop findings 0/12 confirmed → propose threshold change") → through the policy
   lifecycle. Thresholds never self-tune at run time.
6. No individual scorekeeping — regret analysis per rule, never per person.
7. Quality measured by outcomes: accepted/overridden × good/bad outcome; escalation precision and lead time;
   calibration of P(true fault); per-epoch fork counterfactual (human-chosen orders vs recommendation, CRN-paired,
   belief mode); acceptance rate only as a diagnostic.

## Key sources

- GoRules ZEN — https://github.com/gorules/zen ; PyPI — https://pypi.org/project/zen-engine/ ; Python SDK trace — https://docs.gorules.io/developers/sdks/python ; JDM editor — https://github.com/gorules/jdm-editor ; dates/`d()` — https://docs.gorules.io/learn/zen-language/dates.md
- OMG DMN — https://www.omg.org/spec/DMN/ ; Drools DMN gap/overlap analysis — https://docs.drools.org/latest/drools-docs/drools/DMN/index.html
- OPA decision logs — https://www.openpolicyagent.org/docs/management-decision-logs ; Cedar — https://www.cncf.io/projects/cedar/
- IEC 62682:2022 — https://webstore.iec.ch/publication/65543 ; EEMUA 191 Ed. 4 — https://eemua.org/ ; VanCamp, "Alarm management by the numbers" — https://www.chemengonline.com/alarm-management-numbers/
- MIL-STD-882E — https://everyspec.com/MIL-STD/MIL-STD-0800-0899/MIL-STD-882E_41682/ ; AIAG-VDA Action Priority — https://www.pharmaceuticalonline.com/doc/is-it-time-to-say-goodbye-to-fmea-risk-priority-number-rpn-scores-0001
- ESI v5 — https://emscimprovement.center/documents/2177/Emergency_Severity_Index_Handbook.pdf ; NEWS2 — https://www.rcp.ac.uk/media/a4ibkkbf/news2-final-report_0_0.pdf
- Google SRE monitoring — https://sre.google/sre-book/monitoring-distributed-systems/ ; Alertmanager — https://prometheus.io/docs/alerting/latest/alertmanager/
- Drew et al. 2014 — https://pmc.ncbi.nlm.nih.gov/articles/PMC4206416 ; Wickens et al. 2009, *Human Factors* 51(4) — doi:10.1177/0018720809344720
- Parasuraman, Sheridan & Wickens 2000 — doi:10.1109/3468.844354 ; Parasuraman & Manzey 2010 — doi:10.1177/0018720810376055 ; Lee & See 2004 — doi:10.1518/hfes.46.1.50_30392 ; Olson & Sarter 2001 — doi:10.1518/001872001775900904
- Kephart & Chess 2003 (MAPE-K) — doi:10.1109/MC.2003.1160055
- python-statemachine — https://github.com/fgmacedo/python-statemachine
