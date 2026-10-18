<!-- Late sub-report from engine-research helper agent af4dc9aacc02642dd; preserved verbatim as an addendum to candidate_engine_and_ehm_data.md -->

# Public data for four engines with Indian relevance: AL-31F/FP, M53-P2, M88-2 and Kaveri

## Constraints on this research
- **Search budget.** The shared WebSearch budget (200 per turn, shared across agents) ran out after my 3rd search. I did not query search engines any other way.
- **How I continued.** I used direct fetches of known primary URLs, reference-link following, and OAI-PMH metadata harvests of open journals:
  - Defence Science Journal (DSJ), now at https://www.publicationsdrdo.in/index.php/dsj, all 4,009 records.
  - Vestnik of Samara University (Aerospace), 2,779 records.
  - KhAI "Aerospace Technic & Technology", 963 records.
  - MSTUCA Nauchny Vestnik, 13 pages; no AL-31F, Su-27/30, M53, M88, Kaveri or afterburning-turbofan papers.
- **Under-covered as a result:** Chinese literature (CNKI), CAG and Parliament primary documents, and French theses (theses.fr and HAL archives). The user can raise the search limit or send a follow-up to continue these.

## Files saved
All in `/Users/abishaikc/Phalanx/research_sources/engine_data/al31_m53_m88_kaveri/`:
- `AL31F_regime_table_leteckemotory.gif`
- `AL31F_altitude_speed_characteristics_leteckemotory.gif`
- `omnirole_Fiche-technique-M88.pdf` (official Snecma M88-2 datasheet, June 2009)
- `DSJ_1985_Prasad_FlatRating_GTX.pdf`
- `DSJ_2022_Sankar_DegradationModel_ModifiedOffDesign.pdf`
- `DSJ_2022_George_EGT_Afterburner_ErrorEstimation.pdf`
- `DSJ_2002_Sahoo_Gouda_CompressorBladeFailure_RussianFighterEngine.pdf`
- `DSJ_2026_Gaur_TechMgmt_IndigenousAeroEngine.pdf`
- `DRDO_DMRL_Balan_Investigations_on_Failures_monograph.pdf` (21-page preview only)
- `MoD_AR_2022-23.pdf`, `MoD_AR_2023-24.pdf`, `MoD_AR_2025-26.pdf`
- `Godrej_KDE_modules_order_2023.pdf`
- `drdo_newsletters/` (March 2023, November 2025, March 2026, September 2026)

## Tags
- **[DIRECT]** the claim is about that exact engine or system.
- **[TRANSFER: x]** the claim comes from platform x and is being carried over.
- **[ASSUMPTION]** my engineering judgement.
- **AGG** the number appears only in an aggregator or enthusiast site.

---

## 1. Saturn/Lyulka AL-31F / AL-31FP (Su-30MKI)

### Q1. Cycle and design data

**Regime table.** Scanned table, said to be from the AL-31F manual, at http://www.leteckemotory.cz/motory/al-31 [DIRECT, AGG]:

| Regime | N1 | N2 | Thrust | SFC | Airflow |
|---|---|---|---|---|---|
| Full afterburner (static) | 99 (+1/−2)% = 10,098 rpm | 100 (+0.5/−1)% = 13,300 rpm | 12,500 kgf (122.4 kN, −2%) | ≤1.92±0.04 kg/kgf·h (≤0.196 kg/N·h) | 112 (+1/−2) kg/s |
| Minimum afterburner | as above | as above | ≤8,450 kgf (82.8 kN) | ≤0.93 kg/kgf·h | 112 kg/s |
| Max dry ("максимал") | 99% = 10,098 rpm | 100±1% = 13,300 rpm | 7,770±2% kgf (76.2 kN); 7,670 kgf in the alternate column | ≤0.75 kg/kgf·h (0.0765 kg/N·h) | 112 kg/s |
| Minimum-SFC cruise | – | 85–90% (11,300–11,970 rpm) | 3,300–4,200 kgf | ≤0.67 kg/kgf·h | – |
| Idle, nozzle open | – | 70±2% (9,300 rpm) | ≤250 kgf | fuel flow 430 kg/h | – |

**Cycle and geometry** (sources as marked):

| Parameter | Value | Source |
|---|---|---|
| Max dry thrust (conflicts) | 7,600 kgf; 7,670 kgf; 7,850 kgf | airwar.ru http://www.airwar.ru/enc/engines/al31f.html; ru.wikipedia infobox; http://www.brazd.ru/al31f.html |
| N1 at 100% | ≈10,200 rpm | derived from the table [ASSUMPTION] |
| N2 at 100% | 13,300 rpm | table; https://ru.wikipedia.org/wiki/АЛ-31Ф |
| Pressure ratios | LPC 3.54, HPC 6.46, overall ≈23 | leteckemotory [AGG] |
| Max compressor exit pressure | 3.64 MPa | leteckemotory [AGG] |
| Turbine expansion ratio | 6.7 | leteckemotory [AGG] |
| Bypass ratio | 0.571 | leteckemotory, airwar, brazd |
| Bypass ratio (conflicts) | 0.56; 0.59 | ru.wikipedia text; airwar text and https://zh.wikipedia.org/wiki/AL-31發動機 |
| Turbine inlet temperature (TIT) | 1,665 K (1,392 °C) | ru.wikipedia; leteckemotory |
| TIT (conflicts) | 1,685 K; 1,600–1,700 K | zh.wikipedia; airwar |
| Turbine-exit temperature limits | ≤750 °C at M≤1.9; ≤765 °C at M>1.9; +15 °C allowed for ≤5 s in transients | leteckemotory [AGG] |
| Afterburner gas temperature | 1,809 °C at full afterburner | leteckemotory [AGG] |
| Mass | 1,520 kg (also given as 1,530 kg and 1,570 kg) | as above |
| Length / inlet diameter | 4,945–4,950 mm / 905–910 mm | as above |

**Construction:**
- 4-stage LPC with variable IGV; 9-stage HPC with variable IGV and the first 2 stators variable (brazd says 10 HPC stages, a conflict).
- 1-stage HPT and 1-stage LPT.
- Annular combustor; 11-lobe mixer.
- Sources: ru.wikipedia; http://xn--80aafy5bs.xn--p1ai/aviamuseum/dvigateli-i-vooruzhenie/aviamotorostroenie/aviamotory-sssr/turboreaktivnye/turboreaktivnyj-aviatsionnyj-dvigatel-al-31f/.

**Nozzle:**
- All-mode supersonic convergent-divergent nozzle. Flap actuators use engine fuel as the working fluid.
- Nozzle axis tilted 5° down. Sources: airwar; https://ru.wikipedia.org/wiki/Су-27.

**AL-31FP thrust vectoring (TVC):**
- ±15°, with the nozzle axes canted 32° outward so the aircraft gets pitch, roll and yaw moments (https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI, citing Gal-Or 2011).
- Rate 30°/s (https://en.wikipedia.org/wiki/Saturn_AL-31, sourced to Key Aero) [AGG].
- Vectoring adds about 110 kg and 0.4 m. Source: Aviapanorama 1997, M. Tulenkov (13 NII MO), https://www.aviapanorama.narod.ru/journal/1997_2/heart.htm [DIRECT].
- Length conflict: 4,990 mm (leteckemotory) vs 4,942 mm (ru.wikipedia).

**Life and operating limits:**
- Early engines: 100 h to first overhaul, of which ≤30 h at max regime.
- ≤15 h at dynamic pressure q≥7,500 kg/m²; ≤15 h at M≥2.0, of which ≤5 h at M≥2.2.
- Afterburner on the ground ≤20 s (leteckemotory [AGG]).
- AL-31FP time between overhauls (TBO): 1,000 h was a contract term (Aviapanorama 1997).
- Nozzle TBO 500 h; engine TBO 1,000 h; life 2,000 h (en.wikipedia). The Su-30MKI article says 3,000 h life.
- 2,500 h life after a HAL upgrade appears only in https://www1.ru/news/2026/08/06/426746-al-31fp-dlia-su-30mki-stal-sluzit-dolse-dvigatel-uvelicil-resurs-do-2500-casov-posle-modernizacii.html (citing IDRW). Unverified.

**Transients and starting** [DIRECT, AGG] (leteckemotory; ru.wikipedia gives the same 3–5/5/8 s acceleration times):

| Event | Time |
|---|---|
| Idle → max, sea-level static | 3–5 s |
| Idle → max, H<8 km | ≤5 s |
| Idle → max, H>8 km | ≤8 s |
| Idle → full afterburner | ≤7 s |
| Max → 0.95 of full afterburner | ≤3 s |
| Max → idle | 4–6 s |
| Ground start to idle (GTDE-117 starter) | ≤50 s |
| Start to max | 60–80 s |
| Starts from battery without recharge | 5 |
| Maximum number of starts | 300 |

**Manufacturer pages:** the UEC, UMPO and Rosoboronexport (ROE) AL-31F product pages now return 404 or have been removed. Only archives cited by en.wikipedia remain.

### Q2. Published models
- **Altitude-speed characteristic plot** (saved GIF; scanned Russian figure). It plots thrust and SFC against Mach at max and full afterburner, for H = 0/2/5/8/11/15 km (and up to 20 km with afterburner).
  - The dashed iso-lines labelled 251–427 are most likely inlet stagnation temperature in K [ASSUMPTION].
  - Approximate readings: dry static 76 kN; about 38 kN dry at 11 km, M2; about 150 kN with afterburner at sea level, M1.2.
  - This is the best validation target I found.
- **IR emission model:** "Mathematical simulation of AL-31F powerplant radiation in the IR range", Vestnik SSAU 13(4) 2014, pp. 99–106, DOI 10.18287/1998-6629-2014-0-4(46)-99-106 [DIRECT]. Includes the nozzle temperature field.
- **Hardware-in-the-loop (HIL) model** of a twin-spool afterburning turbofan with FADEC fault-reconfiguration models.
  - Authors: Kulikov, Arkov, Fatikov, Abdulnagimov (Ufa State Aviation Technical University) and Pogorelov (UNPP "Molniya").
  - Vestnik SSAU 8(3-2) 2009, pp. 392–400, DOI 10.18287/2541-7533-2009-0-3-2(19)-392-400.
  - The engine is not named; it is likely the AL-31F [ASSUMPTION].
- **KhAI 2020 (aktt.2020.5.04):** mentions vibratory combustion in the AL-31F afterburner.
- **Not found:** component maps, released code. Chinese papers were not searched.

### Q3. Control
**Architecture [DIRECT]:**
- Hydro-electronic system, three units:
  - КРД-99, an analogue electronic regulator-limiter (airwar; ru.wikipedia Su-27 page).
  - НР-31, the hydromechanical pump-regulator.
  - РСФ-31, the nozzle and afterburner regulator.
- The electronic system works on the main regimes. If it fails, a backup hydromechanical system takes over (Aviapanorama 1997).

**Protection functions:**
- Surge elimination.
- Automatic in-flight relight.
- "Counter-start" of the main and afterburner combustors.
- IGV and stator schedules set by the surge-prevention system.

**Digital variant:** the AL-31F M1 uses a digital КРД-99Ц [TRANSFER: M1; limited relevance to the FP].

**TVC integration [DIRECT]:**
- The Su-37 prototype drove the vectoring nozzle from aircraft hydraulics. The production AL-31FP drives it from the engine's fuel automatics (Aviapanorama 1997).
- The flight control system commands nozzle deflection while the pilot uses a conventional throttle (en.wikipedia Su-30MKI; leteckemotory).

**Not found:** schedules, gains, sensor list, BSK/RRD details.

### Q4. Monitoring
- **Limits:** the turbine-exit temperature limits are listed in Q1 [DIRECT].
- **Flight-data recorders:** "Тестер" (Tester-U3) magnetic recorders with Луч-74 ground decoding are used on manoeuvrable Soviet aircraft (https://ru.wikipedia.org/wiki/Бортовые_средства_объективного_контроля). Not confirmed for the Su-30MKI [TRANSFER].
- **Aircraft health and usage monitoring:** the Su-30MKI system "monitors almost every aircraft system" (en.wikipedia, uncited).
- **IAF practice:** the IAF runs an electronic maintenance management system that tracks each engine as a "hardware tree" of parts. It has digital-twin goals and pilot projects with IIT-Bombay on AI engine and asset maintenance. Source: Air Officer Maintenance, quoted in The Hindu, 3 Nov 2024, https://www.thehindu.com/news/national/ai-big-focus-of-su-30mki-upgrade-iaf-taking-up-pilot-projects-with-iit-mumbai-says-officer/article68826449.ece [DIRECT].
- **Not found:** vibration-monitor ("ИВ-…") and monitoring-system details, sampling rates, life-usage algorithms.

### Q5. Degradation and fleet experience
**Failures:**
- 69 engine-related failures between end-2012 and early-2015.
- Causes: bearing fatigue and low oil pressure.
- Fixes: lubrication modifications, better oil, changed bearing fitting.
- Source: en.wikipedia Su-30MKI citing Jane's (Bedi, 2015). The Jane's page is now deleted and the Parliament primary was not retrieved.

**Other fleet notes:**
- 2009 Pokhran crash after an engine fire (en.wikipedia).
- Indian fuels coke more and attack seals; this was a 1997 design concern (Aviapanorama).

**Indian degradation and engine-health-monitoring (EHM) literature:**
- **Sahoo & Gouda, DSJ 52(4) 2002, pp. 363–367:** fatigue failures of 2nd-stage compressor blades in a "Russian fighter-class aero-engine", causing accidents and incidents [TRANSFER].
- **Sankar et al. (CSIR-NAL, HAL Koraput, CEMILAC), DSJ 72(2) 2022, pp. 135–145, DOI 10.14429/dsj.72.15428** [TRANSFER: legacy twin-spool afterburning turbojet, probably R-29 class [ASSUMPTION]; same Koraput test-bed practice]:
  - Engine: 5-stage LPC plus 6-stage HPC, overall pressure ratio about 12, airflow about 100 kg/s.
  - Control: hydromechanical; holds T4 constant through nozzle area when inlet temperature is 15–45 °C.
  - Test-bed sensors: P2, T2, P4, T4, thrust, inlet dynamic pressure, total fuel flow, N1, N2.
  - Extra EHM sensors: LPC-exit Ps/Tt and HPT-exit Ps/Tt.
  - Method: NI-PXI data acquisition; nonlinear gas-path analysis.
- **DMRL monograph (Balan, 2024):** case histories on centre-main-bearing, bearing-assembly and turbine-blade failures. Only a preview is online: https://drdo.gov.in/drdo/en/documents/publications/monograph/investigations-failures-defence-hardware-components-fundamentals.
- **CEMILAC–HAL "Sukhoi Engine Division" meet on technical life extension,** August 2025 (DRDO Newsletter, November 2025).

### Q6. Indian relevance
- Su-30MKI operational since 2002 with two AL-31FP each. Replacement engines are needed because of engine life (MoD Annual Report 2023-24, PDF p.162).
- Fleet: 259 of the 272 contracted are in service (The Hindu, 2024).
- **240-engine order:**
  - Cabinet Committee on Security (CCS) approval on 2 September 2024: more than ₹26,000 crore, 54% indigenous, built at HAL Koraput, delivered from year 1 to year 8 (Economic Times, https://economictimes.indiatimes.com/news/defence/cabinet-approves-procurement-of-240-aero-engines-for-iafs-su-30-mki-aircraft-from-hal-worth-rs-26000-cr/articleshow/112999865.cms).
  - First engine delivered 1 October 2024. Koraput builds the engine from raw material (Business Standard, 2024).
- **Koraput output:** 63 engines delivered against a target of 60, capacity rising from 30 to 50 per year (₹335 crore), more than 9,000 overhauls (Times of India, October 2026, https://timesofindia.indiatimes.com/city/bhubaneswar/hal-koraput-rolls-out-2000th-engine-gets-new-shakti-line/articleshow/134743772.cms).
- **Materials:** MIDHANI holds CEMILAC clearance for materials used at HAL Koraput (MoD Annual Report 2025-26).

---

## 2. Safran (Snecma) M53-P2 (Mirage 2000H/I)

### Q1. Cycle data
**Thrust:** 64.35 kN dry and 95.13 kN with afterburner. Source: the Safran sheet of March 2011 as cited by https://fr.wikipedia.org/wiki/Snecma_M53 [DIRECT]; the sheet itself was not retrieved. en.wikipedia gives 64.7/95.1 kN.

**Cycle parameters:**

| Parameter | Value | Note |
|---|---|---|
| Airflow | 92 kg/s at 10,600 rpm (103%) | infobox says 94 kg/s |
| Overall pressure ratio | 9.8 | |
| Bypass ratio | 0.352–0.36 | varies with the control laws |
| Turbine inlet temperature | 1,560 K in the text | infobox says 1,600 K, a conflict |
| SFC | 0.90 kg/daN·h dry; 2.10 with afterburner | |
| Mass | 1,500 or 1,515 kg | |
| Length | 5,070 mm | |

**Construction:**
- Single shaft: 3-stage LP plus 5-stage HP compressor, with no IGV and no variable stators.
- 2-stage cooled turbine; annular combustor with 14 vaporiser pairs.
- Variable convergent multi-flap nozzle on fuel-hydraulic jacks; 12 modules.

**Station values:** LPC exit about 3 bar and 100–150 °C; turbine pressure falls 9→3 bar; turbine exit 850–900 °C.

### Q2. Models
None found. theses.fr and HAL archives were not searched.

### Q3. Control [DIRECT, FR wikipedia]
**Architecture:** digital computer with an autonomous hydromechanical backup that gives degraded performance.

**Four functions:**
- **Main regulation:**
  - Speed N set through fuel; nozzle area controlled.
  - Tt7 limited at full throttle.
  - Anti-surge procedure on start; fuel-to-pressure (C/P) richness limits.
- **DSV variable bypass-section valve:** frozen above 16° angle of attack.
- **Afterburner regulation.**
- **Pilot-selected fuel backup.**

**Other behaviour:** nozzle pre-opens before afterburner light-up and opens fast on deceleration; a missile-fire function shifts speed, nozzle and DSV settings. The event-recorder and life-usage-computer ("calculateur de potentiel") sections exist on the page but are empty.

### Q4. Monitoring [DIRECT]
- Cockpit parameters: N, Tt7, fuel pressure PCA, oil pressure PH, afterburner state, regulation state, DSV state.
- Limits: +9 g; negative g limited.
- Modules are replaced on condition using EGT and oil trends plus borescope.
- An engine change takes half a day plus a ground run, versus 1 h for the M88.

### Q5. Degradation / PHM
- No public data found.
- A 1995 CAG report flagged delays in IAF Mirage overhaul facilities and spare shortages (secondary, via en.wikipedia).
- 675 M53 had been delivered by 1999; 644 engines had passed 1.5 M hours by 2007.

### Q6. Indian relevance
- India operates 47 Mirage 2000 (Safran press release, 26 November 2025).
- 51 upgraded to 2000I/TI, 49 of them by HAL.
- 24 ex-French aircraft bought in 2021 for spares and engines.

---

## 3. Safran M88-2 (Rafale; IAF Rafale and Indian Navy Rafale M)

### Q1. Cycle data [DIRECT, saved Snecma datasheet]

| Parameter | Value |
|---|---|
| Thrust, afterburner | 17,000 lb (75.6 kN) |
| Thrust, dry | 11,250 lb (50.0 kN) |
| SFC, afterburner / dry | 1.70 / 0.80 kg/daN·h |
| Airflow | 65 kg/s |
| Turbine inlet temperature | 1,850 K |
| Overall pressure ratio | 24.5 |
| Bypass ratio | 0.30 |
| Weight | 1,977.5 lb (897 kg) |

**Construction:**
- 3-stage LPC with IGV; 6-stage HPC with 3 variable-stator stages.
- Single-stage cooled HPT and LPT; radial afterburner; variable convergent flap nozzle.
- FADEC; 21 modules.

**Current Safran page** (https://www.safran-group.com/products-services/m88-proven-performance-and-reliability):
- 16,500 lb (73.4 kN), a conflict with the datasheet.
- 600+ engines delivered, 1,000,000+ hours, 1 h to remove and reinstall an engine.

### Q2. Models
- "SNECMA M88 Engine Development Status" exists on scispace but was blocked by a web firewall.
- No maps or theses found.

### Q3. Control
- Redundant FADEC with two computers; both engines start in about 2 min; afterburner in about 3 s (FR wikipedia, AGG).
- The M88 T-REX upgrade gives 9 t thrust (+20%) with a new digital control (Safran, 17 June 2025).

### Q4. Monitoring
- **Condition monitoring:** an Engine Condition Monitoring System uses sensors, vibration and oil-filter-clogging signals, and adjusts TBO by usage.
  - This is from en.wikipedia summarising NATO RTO-MP-AVT-144-15, "Advanced Diagnostics in the SNECMA M-88 Engine of the Rafale Fighter".
  - The paper itself was blocked; it is the key one to obtain manually.
- **F4 standard:** adds onboard electronics to store data for integrated predictive maintenance (Safran, 13 July 2022) [DIRECT], and a "Système de Pronostic et d'Aide au Diagnostic".
- **Flight test:** about 1,000 parameters were telemetered.

### Q5. Life
- Stage-1 engines had 300 h TBO; the E4 version has more than 1,000 h and 3% lower SFC.
- The M88-4E raised inspection intervals from 2,500 to 4,000 cycles.
- French Rafale M availability was 38.6% in 2013 and 46.6% in 2014. This is aircraft-level (https://questions.assemblee-nationale.fr/q14/14-47343QE.htm and opex360).

### Q6. Indian relevance [DIRECT]
- **Fleet:** 36 IAF Rafale plus 26 Rafale M = 62 by 2030. The deal includes maintenance and production facilities (PIB press note 154353).
- **M88 maintenance, repair and overhaul (MRO) shop in Hyderabad:** 5,000 m², more than €40 M, more than 600 modules per year, IAF engines first (Safran, 26 November 2025).
- **114-aircraft follow-on order:** the Acceptance of Necessity (AoN) for 114 Rafale was granted on 12 February 2026, with Safran paired with HAL on engines (secondary).

---

## 4. GTRE Kaveri / Kaveri Derivative Engine (KDE)

### Q1. Cycle data (mostly AGG, from https://en.wikipedia.org/wiki/GTRE_GTX-35VS_Kaveri)
**Cycle (uncited unless noted):**
- 52 kN dry and 81 kN with afterburner (Jane's 2017).
- Airflow 78 kg/s; bypass ratio 0.16; overall pressure ratio 21.5 (goal 27); fan pressure ratio 3.4; HPC pressure ratio 6.4.
- Turbine inlet temperature about 1,700 K; SFC 0.78/2.03 lb/lbf·h.

**Mass (conflicting):**

| Figure | Source |
|---|---|
| 1,057 kg | Wikipedia spec table |
| 1,235 kg against a 1,100 kg specification | CAG 2010-11, via Deccan Chronicle |
| 1,180 kg | 2024 report |

**Thrust achieved (conflicting):**

| Figure | Source |
|---|---|
| 46 kN dry / 70.5 kN with afterburner | 2022 |
| 48.5 kN (KDE) | reported |
| 49–52 kN | Business Today, 9 August 2026 |
| Kaveri 2.0 targets: 55–60 kN dry / 90–100 kN with afterburner | Business Today, 9 August 2026 |

**KDE build:** 12 modules in 5 domains (Gaur et al., DSJ 76(5) 2026) [DIRECT].

**Programme facts [DIRECT]:**
- **PIB relid 90291:**
  - Sanctioned March 1989 at ₹382.81 crore; completion first due December 1996, extended to 2009; cost revised to ₹2,839 crore.
  - 9 prototypes and 4 Kabini core engines; 2,200 h of testing.
  - Flying test bed (FTB): 27 flights, 57 h, up to 12 km and M0.7.
- **PIB relid 123940:** 73 h of high-altitude testing; FADEC qualified indigenously; more than 2,550 h of testing; ₹2,101 crore spent; dry derivative chosen for the UCAV.
- **PIB PRID 1776092:** 3,217 h of testing; ₹2,035.56 crore spent.
- **PIB PRID 2148337:** two KDE projects, ₹472.42 crore and ₹251.17 crore.
- **PIB relid 66793:** first flight on the Il-76 testbed, 4 November 2010, 6 km at M0.6.

### Q2. Models
- **GTX flat-rating paper:** Prasad & Sundararajan, "Flat Rating Concept Introduced in the GTX Engine", DSJ 35(2) 1985, pp. 163–170 [TRANSFER: GTX 37-14U is the ancestor engine].
  - Throttle ratio 1.13; turbine entry temperature limit 1,450 K.
  - Limiters on overall pressure ratio, turbine entry temperature and rpm; nozzle law based on jet-pipe temperature, NH and T1.
  - Figures 3–9 can be digitised.
- **EGT measurement paper:** George & Muthuveerappan (GTRE), DSJ 72(1) 2022, pp. 10–17. Covers EGT measured in afterburner mode on the test bed.
  - Gap between measured temperature and temperature implied by thrust: 97 K.
  - Error breakdown: radiation 69 K, conduction 3 K, velocity 1 K; residual 24 K after correction.
  - The engine is probably Kaveri [ASSUMPTION].
- **GTRE small-engine control rig:** HIL and ground-checkout rigs for small-engine controls (MoD Annual Report 2023-24, PDF p.208).
- **Not found in the full DSJ harvest:** any Kaveri performance, transient or real-time model, or any KADECU HIL paper.

### Q3. Control
- KADECU FADEC built by DARE (en.wikipedia).
- KDE has an indigenous engine fuel control system, an "autonomous engine control system", a fan tolerant of high inlet distortion, and a short jet pipe (MoD Annual Report 2022-23 p.121; 2025-26 PDF p.292) [DIRECT].

### Q4. Monitoring
- Flight-test data were recorded on board and telemetered (PIB 2010) [DIRECT].
- No GTRE engine-health-monitoring paper found.

### Q5. Test and fault history
- Altitude testing at CIAM in October–December 2022; no major distress at teardown; 38 accelerated simulated mission endurance test (ASMET) cycles (MoD Annual Report 2023-24, PDF p.202).
- First engine to test (FETT) integrated July 2025; uninstalled tests done (MoD Annual Report 2025-26).
- The IAF Air Officer-in-Charge Maintenance watched a Kaveri test run on 16 July 2026 (DRDO Newsletter, September 2026).
- Causes of delay are in PIB relid 63983.
- CAG 2010-11 found 2 of 6 milestones met (secondary).

### Q6. Indian relevance
Fully indigenous engine, not in service.

---

## Gaps
- **No public maps, schedules or sampling rates** for any of the four engines.
- **Not retrieved:**
  - NATO M88 diagnostics paper.
  - Safran M53 sheet.
  - Parliament and CAG primary documents on AL-31FP failures and on Kaveri.
  - Chinese AL-31F literature.
  - Russian КРД-99 and BSK manuals.
  - Kaveri KADECU and engine-health-monitoring papers.
- **Unresolved conflicts:**
  - AL-31F: dry thrust, bypass ratio, turbine inlet temperature, HPC stage count.
  - AL-31FP: length and service life.
  - M53: turbine inlet temperature.
  - M88: afterburner thrust.
  - Kaveri: thrust and mass.
- **No public real sensor data.**

## Top sources, ranked
1. leteckemotory AL-31 page plus its two images: regime table, altitude-speed plots, limits, transients.
2. Snecma M88-2 datasheet: official cycle figures.
3. DSJ 2022 Sankar et al.: engine-health monitoring on HAL Koraput test beds.
4. FR wikipedia "Snecma M53": M53-P2 control and monitoring logic.
5. NATO RTO-MP-AVT-144-15: M88 condition monitoring (obtain manually).
6. DSJ 1985 GTX flat-rating paper.
7. MoD Annual Reports and PIB releases: Kaveri and AL-31FP facts.
8. Aviapanorama 1997: AL-31FP control and TVC.
9. Safran press releases of November 2025 and July 2022.
10. Vestnik SSAU 2009 HIL/FADEC paper and 2014 AL-31F IR paper.

## Suggested scores (0–5)

| Criterion | AL-31F/FP | M53-P2 | M88-2 | Kaveri |
|---|---|---|---|---|
| Cycle data | 4 | 3 | 4 | 3 |
| Maps / models | 2 | 1 | 1 | 2 |
| Control documentation | 2 | 3 | 2 | 2 |
| Monitoring / sensor documentation | 1 | 2 | 3 | 1 |
| Degradation / PHM literature | 2 | 1 | 2 | 1 |
| Real data availability | 1 | 0 | 1 | 1 |
| Indian relevance | 5 | 3 | 5 | 4 |

Justification:
- **AL-31F/FP:** the regime table and altitude-speed plot carry it. Control is known only at architecture level and monitoring is thin. It is the largest Indian fleet.
- **M53-P2:** a good control narrative but no models. Fleet of 47.
- **M88-2:** best official datasheet and a clear condition-monitoring and prognostics story. 62 aircraft plus more coming, and the Hyderabad MRO shop.
- **Kaveri:** primary sources cover the programme, but cycle data come from aggregators. Indigenous but not fielded.

**Indian data the team could plausibly get:**
- PIB and Parliament replies, MoD Annual Reports, DSJ papers.
- The digitised AL-31F plots above.
- A sanitised data request through the problem-statement owner (DSSC/IAF).
- NASA C-MAPSS/N-CMAPSS as a surrogate for degradation data.
