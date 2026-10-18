# 01 · Problem, stakeholders and KPIs

**What we are solving.** The problem statement: aircraft availability is low because maintenance is fragmented and largely
reactive; health-monitoring data, technical records, spares and maintenance agencies are not integrated, so
fault prediction is late, downtime is avoidable and assets are under-used.

## 1. Where availability is actually lost (evidence)

| Fleet / source | Finding |
|---|---|
| Su-30MKI — CAG Report 38/2015 (Table 2.8) | serviceability 55.5–59.7 % vs a 75 % norm (2006–10); "AOG" (not airworthy) 10.9–15.3 % of the fleet ≈ 27–36 % of all unserviceable aircraft; flying-task shortfall 31–43 %; cause cited: long HAL repair cycles as Cat 'D' aggregates went to the OEM |
| IAF AEW (CAG 38/2015) | rotables below the Scale of Rotables; Equipment Depot had no spares → squadron cannibalised; ATE unserviceable |
| IL-76 — CAG 24/2017 | serviceability 38 % vs 70 %; > 40 % grounded for spares and contract delays; AOG demands met within 15 days only 10.8 % of the time, 22.5 % > 6 months |
| F-35 — GAO / DOT&E | 22–30 % of time unable to fly for lack of parts (FY2017–2019); FY2023 availability 51 %, NMCS 27 %, NMCM 15 %; part repair 141 days vs a 60-day goal; FY2025 MC 44 %, FMC 25 % |
| USN Super Hornet O-level reform | a 3-day inspection averaged 10–14 days — "a lot of waiting time in between" work centres; fleet went from ≈ 50 % to > 80 % MC by FY2019 through process, visibility and decision discipline, **not prediction** |
| GAO-02-86 | ≈ 850k cannibalisations over FY1996–2000 cost ≈ 5.3 M extra man-hours; Navy CANNs under-reported by up to 50 % |
| DoD IG 2022 | no weapon system had fully implemented predictive maintenance; the main obstacle was "a lack of quality data" |
| F-35 ALIS (GAO-20-316) | inaccurate or missing data grounded flight-ready aircraft; squadrons flew aircraft ALIS said to ground |
| Our preview v0.9 (uncalibrated — illustration, not evidence) | of 1,440 tail-days: NMCS 285 (tyres 147, FADEC 57, hydraulic pump 28), NMCM 251, NMCD 38; every FADEC/hydraulic-pump AOG wait came from removing a healthy unit (all shop findings RTOK) |

**Verdict on the team's thesis** ("availability is lost mostly while aircraft wait; value comes from acting
earlier"): **confirmed, with three refinements.**
1. Waiting dominates, but it has several sources — supply (largest in supply-constrained fleets), depot
   turnaround, coordination/decision waits *inside* NMCM, and administrative/contract delay.
2. Prediction helps only where its lead time exceeds the response lead time. Many BIT-based detections give hours
   to days; wholesale lead times are weeks to months. Such predictions still pay when routed to *fast* actions
   (transfer, expedite, cannibalise, schedule into a planned down-day, restrict usage). The product computes
   **useful lead time per part class** and routes each prediction to an action whose lead time it beats.
3. The cheapest "earlier" is often not predictive at all: a daily status picture (the Navy's Maintenance
   Operations Center), prioritisation, consolidating cannibalisation, scheduling maintenance before the flying
   programme, expediting the demand that grounds the most aircraft, and **stopping NFF removals that feed good
   units into the repair pipeline**. Hence our headline KPI: **evidence-to-action latency**.

Honest scope limit: OEM delivery (F404 engines for Mk1A have run years late), industrial capacity and funding are
outside a base-level tool's control. Command views can quantify availability lost to them; they cannot fix them.

## 2. How the IAF organises maintenance (what the sources show)

- **Echelons** (CAG 38/2015): 1st line (O-level) — flight-line fault detection and LRU replacement; 2nd line
  (I-level) — base shop/lab SRU isolation with ATE; 3rd/4th line (D-level) — repair/overhaul at a **Base Repair
  Depot** (Maintenance Command, Nagpur; 13 BRDs) or HAL, foreign OEM as last resort.
- The MoD fixes each type's **flying task**; the serviceability norm is 75 %, "serviceable" meaning airworthy
  (≈ MC %, as the data layer maps it).
- Systems of record: **e-MMS** (Wipro as integrator on IBM Maximo; ≈ 170 bases, 13 BRDs) and **IMMOLS**
  (inventory ERP), both under CSDO; much historical data is still on paper (MP-IDSA, July 2026).
- Airworthiness: **CEMILAC** (design and continued airworthiness via Regional Centres at HAL divisions and BRDs);
  **DGAQA** (production QA).
- Tejas specifically: the first Mk1A squadron is planned at Nal; finished airframes have waited for F404 engines
  — single-source supply is the binding constraint, and our fleet scenario (Sulur + Nal) matches it.

## 3. Stakeholders

| Stakeholder | Decisions (cadence) | Pain points (evidence) | The question they most need answered | Primary workspace |
|---|---|---|---|---|
| **Flight-line technician / crew lead** | rectify snags, remove/replace LRUs, record work (per snag) | false BIT codes and NFF removals (F/A-18E/F BIT deficiency; ~80 % of ALIS-reported problems false in one F-35 field test); parts not at the aircraft | "Is this code real, which LRU do I pull, and is the part here?" | Aircraft Twin, issue workbench |
| **Squadron Senior Engineering Officer** (maintenance control) | job priorities, aircraft release, defer vs fix, cannibalise, crews (daily, 08:00) | tracking every jet by hand; spares not at the ED; false groundings from bad records | "Which jobs, done first, give me the most serviceable aircraft by tomorrow's programme?" | Decision Board, Readiness |
| **Flight Commander / Squadron CO** | daily flying programme, meeting the monthly task | flying-task shortfalls of 31–43 % (Su-30MKI) | "How many and which aircraft will I have each day this week?" | Readiness, Plan |
| **Station CEO / 2nd line (Tech Flight)** | servicing phasing, hangar/manpower/ATE loading (weekly) | unserviceable ATE stalls I-level repair; servicing overruns (only 30–37 % on time, IL-76) | "What is due in 30–90 days and can I phase it without losing flying?" | Plan |
| **Equipment / logistics officer** | demands and priorities (AOG/MCM/PHU), expediting, transfers, Scale of Rotables (daily/weekly) | rotables below scale; demand-driven late ordering; long lead times | "Which parts will I need within the lead-time window, and which open demand grounds the most aircraft?" | Spares |
| **BRD / HAL R&O / OEM** | induction sequencing, repair turnaround, condemn vs repair (weekly) | long repair cycles; Cat 'D' abroad; NFF units in the pipeline | "What will arrive for repair, when, and which repairs unblock the most aircraft?" | Fleet Insights (repair view) |
| **Command HQ / Air HQ (Dte of Engineering), CSDO, Maintenance Command** | policy, cross-base redistribution, contracts, mods (monthly) | fleet serviceability far below norm; contract/admin delays; paper records | "Where is availability being lost — supply, maintenance, depot, admin — and which policy or investment buys the most back?" | Fleet Insights, Plan & What-if |
| **Pilot** | accept aircraft, write-ups | repeat write-ups, nuisance cautions | "Is my aircraft fixed for good?" | (via SEO; assistant) |
| **Airworthiness & QA** (CEMILAC/RCMA, DGAQA, unit QA) | deferral limits, mod approval, record audits, model/policy approval | integrity of life and configuration records | "Are the records trustworthy, and is this deferral within limits?" | Assurance |

**Cross-cutting pain:** each stakeholder owns part of the chain (snag → part → repair → release) in a separate
system (tech log, e-MMS, IMMOLS, depot MRP). That is the PS's "not adequately integrated". The contract's join
keys — `evidence_record_ids`, demand number, serial, `order_id` — are the integration seams our twin is built on.

## 4. KPIs

Definitions follow the USAF *Metrics Handbook for Maintenance Leaders* (AFLMA, 2001), which organises metrics
around two cornerstones — **fleet availability** (MC) and **programme execution** — and tags each as
**leading** (break, fix, repeat/recur, abort, MSE, deferred discrepancies, issue effectiveness) or **lagging**
(MC, FMC, TNMCM, TNMCS). It warns against chasing single metrics ("TNMCS should not be held low at the expense of
increased CANN actions").

| KPI | Formula | Owner | Contract source | Tier that moves it | v0.9 |
|---|---|---|---|---|---|
| **MC rate** (≈ IAF serviceability) | (FMC + PMC hours) / possessed hours | SEO → Air HQ | AVAILABILITY_STATE | all; mostly prescriptive | yes (mean 0.60) |
| FMC rate | FMC / possessed | SEO | AVAILABILITY_STATE | diagnostic, prescriptive | yes (0.58) |
| TNMCM | NMCM(+B) / possessed (NMCM_S/U split) | SEO, CEO | AVAILABILITY_STATE, DEFECT_WO | prescriptive, diagnostic | yes (0.17) |
| TNMCS | NMCS(+B) / possessed | logistics | AVAILABILITY_STATE, SUPPLY_DEMAND | predictive + prescriptive | yes (0.20) |
| NMCD | depot hours / possessed | BRD/HAL | AVAILABILITY_STATE | prescriptive | yes (one tail) |
| **AOG days** | *defined explicitly in the demo*: days in NMCS with an AOG-priority demand (CAG uses "AOG" more broadly for not-airworthy) | logistics, Command | SUPPLY_DEMAND + availability | predictive + prescriptive | yes |
| CANN rate | CANNs / 100 sorties (USAF) or / 100 FH (USN), with under-reporting reconciliation | SEO | CANNIBALISATION | prescriptive | no (one tail per world) |
| Repeat/recur rate | (repeats + recurs) / pilot-reported discrepancies (repeat = next sortie; recur = 2nd–4th) | SEO, QA | DEFECT_WO + SORTIE | diagnostic | yes |
| Break rate; 8/12-h fix rate | Code-3 landings / sorties; breaks fixed within 8 h (fighters) | SEO | DEFECT_WO + SORTIE | predictive; prescriptive | partial; yes |
| Deferred discrepancies (AWM/AWP) | snapshot count / aircraft possessed | SEO, logistics | DEFECT_WO status | prescriptive | yes |
| MSE (maintenance scheduling effectiveness) | completed scheduled actions / scheduled | CEO | INSPECTION, usage | predictive + prescriptive | yes |
| Flying-task achievement / FSE | task achieved / allotted | Flight Cdr | SORTIE, plan; `flying_task` | prescriptive | yes (0.42) |
| MTBUR / MTBF | hours / unscheduled removals; / verified failures | engineering | COMPONENT_LIFE, SHOP_FINDING | diagnostic, predictive | weak |
| **NFF / RTOK / CND rate** | RTOK / shop findings; CND / troubleshoots | engineering, BRD | SHOP_FINDING, DEFECT_WO | **diagnostic** | **yes — NFF-heavy** |
| BIT false-alarm rate | FH / BIT declarations not confirmed by maintenance | engineering, CSDO | events → DEFECT_WO → outcome | diagnostic | yes |
| Issue effectiveness (fill rate) | issues / (issues + backorders) | ED | SUPPLY_DEMAND | predictive | partial |
| Repair cycle / depot TAT | (pre + repair + post − AWP days) / items | BRD/HAL | SHOP_FINDING, COMPONENT_LIFE | prescriptive | partial |
| Man-hours per FH (and **no-fault man-hours per FH**) | Σ man_hours / Σ FH | CEO, Command | DEFECT_WO, SORTIE | diagnostic, prescriptive | yes (no-fault ≈ 5.8 h/FH) |
| In-flight failures | per 1,000 FH | QA, Flight Cdr | DEFECT_WO (when-discovered in flight) | predictive | yes |
| **New: evidence-to-action latency** | t_effective(order) − t_ingest(first evidence); and → state change | SEO, Command | events, orders, maint.records | prescriptive | **yes — unique to our contract** |
| **New: useful prediction lead time** | t_predicted_failure − t_alert − (lead time + slack); share of alerts with useful lead > 0 | engineering, logistics | predictions + SUPPLY_DEMAND | predictive | needs calibrated data |

## 5. Organising the product: decision workspaces, with the four tiers as the spine

The Gartner descriptive → diagnostic → predictive → prescriptive ladder is a good **capability spine** but a poor
**top-level product structure**:
- it describes methods, not jobs; Gartner's own recent material moves to "decision intelligence" (value emerges
  when decisions are defined, governed and operationalised);
- successful products are cut by workflow and mix tiers in each: Airbus Skywise Health Monitoring (alerts
  prioritised, linked to troubleshooting, operational impact, parts near the aircraft — one maintenance-control
  workflow), easyJet runs 22 Skywise predictive models *inside its Maintenance Control Centre*, Lufthansa
  Technik AVIATAR sells modules named after jobs, USAF PANDA joins maintenance, engineering and supply data for
  those teams, and the Navy's readiness turnaround used a daily status/prioritisation process with no AI at all;
- the big failure (ALIS) failed on data integrity and trust, not missing tiers.

So: **top-level navigation = decision workspaces** ([11](11-ui-ux.md)); underneath, one shared spine — as-of
ingestion → descriptive state → diagnostic evidence chains → predictive belief state → prescriptive order engine
→ fork validation — with **tier badges** visible on every card so judges can see each PS capability. Every
recommendation card carries the same five elements: **state, why (record_ids), forecast (with uncertainty),
proposed orders (with AGENT/HUMAN authority), expected KPI delta (CRN fork vs status quo).**

## 6. Measured value elsewhere — set expectations honestly

| Source | Reported | Label |
|---|---|---|
| easyJet + Skywise predictive maintenance | 1,343 cancellations, 662 minor and 171 major delays avoided (Jan 2019–Sep 2025) | customer/vendor counterfactual |
| Boeing AHM | −64 % average delay time; −80 % recurring system delays | vendor claim |
| GE (2019 PHM keynote) | −56 % disruptions (one carrier) | vendor claim |
| USAF PANDA (B-1 example) | unscheduled breaks eliminated on targeted systems; −51 % unscheduled man-hours | single example, no baseline |
| C3 AI on PANDA | −40 % unscheduled maintenance on monitored subsystems; +6 % MC | vendor claim |
| US Army HUMS (Black Hawk battalions) | small readiness advantage; sample too small | independent thesis |
| US Navy Super Hornet | ≈ 50 % → > 80 % MC | process + visibility, no prediction |

**Takeaway:** lead with decision speed and visibility; treat prediction as an accelerator; back every claim with
CRN-paired fork KPI deltas rather than vendor-style anecdotes.

## 7. Prioritised use cases (prototype demo)

| # | Tier | Use case | KPI moved | v0.9 | Priority |
|---|---|---|---|---|---|
| D1 | descriptive | **Fleet readiness board** (per tail: SCIR state, NMC reason, open snags, AWP demand + age, servicing due, ETIC) | MC, FMC, FSE | yes | MUST |
| D2 | descriptive / diagnostic | **Downtime waterfall** (flying / FMC idle / touch maintenance / AWM / AWP-NMCS / depot / decision wait) + evidence-to-action latency | TNMCM, TNMCS, NMCD, latency | yes | MUST |
| G1 | diagnostic | **BIT triage and NFF suppression** emitting DEFER/TROUBLESHOOT orders | NFF, MMH/FH, false-alarm rate | **yes — best fit** | MUST |
| P2 | predictive | **Servicing and life-due forecast** (SRV-L1/L2/ROH, LUI limits) and availability dips | MSE, NMCM_S, flying task | yes | MUST |
| P1 | predictive | **Spares demand and AWP-risk forecast** with useful-lead-time check | TNMCS, AOG days | partial (per tail) | MUST |
| R1 | prescriptive | **Daily 08:00 plan** with human authority (ASSIGN_SORTIE, BRING_FORWARD_SERVICING, RESTRICT_USAGE, DEFER_SERVICING draft) | flying task, MC, MSE | yes (per tail) | MUST |
| R2 | prescriptive | **Spares action recommender** (REQUISITION/EXPEDITE now; TRANSFER/CANN later) | TNMCS, AOG days, CANN rate | partial | MUST |
| R3 | prescriptive | **Fork-backed what-if proof** vs StatusQuoPolicy (paired KPI deltas with CI) | all | needs in-process fork access | MUST |
| G2 | diagnostic | repeat/recur and rogue-unit detector | R/R, aborts | yes | SHOULD |
| D3 | descriptive | record-integrity monitor (duplicate snags, `XXX` serials, lag, missing part records) | data quality, false NMC | yes | SHOULD |
| P4 | predictive | per-serial removal/health forecast with a useful-lead-time gate | MTBUR, in-flight failures | method only (no true faults) | SHOULD — not the centrepiece |
| P5 | predictive | engine gas-path trend monitoring | engine removals | no (6 sorties, B7 mismatches) | NICE |

## Key sources

- CAG Report 38/2015 (Air Force), ch. 2 — https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015_chap_2.pdf
- CAG Report 24/2017 — https://saiindia.gov.in/webroot/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf ; Tribune summary — https://www.tribuneindia.com/news/archive/nation/iaf-flew-9-unairworthy-il-76s-443813
- AFLMA *Metrics Handbook for Maintenance Leaders* (2001) — http://www.ageranger.com/pdf/Maintenance_Metrics_S.pdf
- GAO-18-75, GAO-19-321, GAO-23-105341, GAO-20-316 (ALIS), GAO-02-86 — https://www.gao.gov/
- DOT&E FY2023 F-35 (via Air & Space Forces) — https://www.airandspaceforces.com/f-35-reliability-maintainability-availability-2023/
- DoD IG DODIG-2022-103 (via DefenseScoop) — https://defensescoop.com/2022/06/15/watchdog-dod-still-hasnt-fully-deployed-predictive-maintenance-on-any-weapon-systems/
- USN readiness turnaround — https://www.cpf.navy.mil/Newsroom/News/Article/2644953/ ; O-level reform — https://seapowermagazine.org/o-level-reform-lemoore-strike-fighter-squadrons-returning-more-jets-to-flight-line/
- IAF e-MMS — https://www.ajaishukla.com/2021/02/indian-air-force-goes-high-tech-in.html ; CSDO — https://www.aviation-defence-universe.com/visit-of-chief-of-defence-staff-cds-to-central-servicing-development-organisation-csdo-on-21-sep-23
- MP-IDSA, Su-30MKI AI health index (2026) — https://idsa.in/publisher/issuebrief/from-reactive-repairs-to-predictive-power-an-ai-digital-twin-health-index-for-the-su-30-mki
- CEMILAC — https://drdo.gov.in/centre_for_military_airworthines/what-we-do
- Airbus Skywise Health Monitoring — https://www.airbus.com/sites/g/files/jlcbta136/files/8ff858dcc91a6b2f35705a274c7b62b7_EN-Airbus-launches-Skywise-Health-Monitoring-with-Allegiant.pdf ; easyJet — https://www.eplaneai.com/news/easyjet-highlights-reliability-improvements-ahead-of-pam-dublin-2025
- USAF PANDA — https://defensescoop.com/2023/05/10/air-force-selects-ai-enabled-predictive-maintenance-program-as-system-of-record/
- Gartner decision intelligence — https://www.gartner.com/en/documents/7864181
