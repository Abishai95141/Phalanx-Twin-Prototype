# Tejas-class Utility and Secondary Systems: architecture, sensors, normal behaviour, coupling to engine and flight state, degradation, and modelling fidelity (Project Phalanx)

Scope: secondary power (AMAGB, PTO shaft, jet fuel starter), hydraulics, fuel, electrical power, environmental control and life support, landing gear/brakes/tyres/steering/brake parachute, and the utility management computers (USMS, ECFM, brake management) with their BIT and cautions, for the HAL Tejas Mk1/Mk1A "Tejas-class virtual fighter". Engine-internal lubrication, the F404 start schedule and FADEC behaviour belong to the engine sibling (`f404_in20_engine_model.md`). Ground-reaction dynamics belong to the airframe/FCS sibling. This note covers the aircraft side of those interfaces.

Evidence tags. **[DIRECT]** = a source names Tejas/LCA. **[DIRECT part; Tejas fitment = ASSUMPTION]** = an Indian (mostly HAL) product page gives numbers for a part but does not name the aircraft; the reason for the Tejas attribution and how to validate it are given. **[TRANSFER: platform/standard]** = borrowed from another aircraft or a standard, with the reason it transfers and its limits. **[ASSUMPTION]** = engineering judgement, with a validation path. Derived numbers (arithmetic on cited values) are labelled "derived".

Method and access notes. About 62 WebSearch calls were used (the agreed share was about 65). Many sources were reached by direct fetch, by scanning the Department of Defence Production (DDP) product catalogue node by node, and by reading saved PDFs. Downloaded sources are under `/Users/abishaikc/Phalanx/research_sources/tejas_utility/` (`ddp_products/` has extracted text of 33 DDP product pages, `donors/` has the Gripen, standards and PHM papers). These failed during this session: every drdo.gov.in page ("inaccessible at this time"/404), diva-portal.org (connection refused, so Gavel's Gripen fuel-system thesis was not read), the NATO STO paper MP-SCI-162-14 (Cloudflare block), journal.accsindia.org (DNS failure), the DSJ search (HTTP 500), tdf.drdo.gov.in (refused) and the Internet Archive, including its DTIC mirrors ("temporarily offline"). Where a fact about one of those pages comes only from a search-engine excerpt, it is marked "(search-index excerpt; page not retrievable)". No document in `_restricted_do_not_cite/` or any distribution-limited manual was used.

---

## KQ1. Secondary power: AMAGB, PTO shaft, jet fuel starter (GTSU-110), gearbox lubrication

### Takeaway
The secondary power chain is now well documented from official Indian sources. The F404 engine gearbox drives a CVRDE-designed, lubrication-free PTO shaft. That shaft drives a single-input, four-output AMAGB at a rated 16,810 rpm (equal to the F404's 100 % N2). The AMAGB carries two hydraulic pumps, one generator and the GTSU-110 jet fuel starter (110 kW, 52 kg, twin-shaft with a free power turbine). The AMAGB has a self-contained lubrication system, a 750 h life and more than 6,000 fleet flying hours. The starter's documented weak points are cold/altitude starting and oil consumption. So all hydraulic and electrical generation speeds are slaved to N2. The JFS adds a battery- and temperature-dependent start-success process with oil-consumption trending.

### Cited Findings
**AMAGB [DIRECT]**
- The AMAGB is "a single input, multi output gear box". It "receives its input drive from the Engine through Power Take-Off and drives 4 aircraft accessories on its output pads viz., 2 Hydraulic pumps, 1 Generator & 1 starter unit" — [ADA General Systems page](https://www.ada.gov.in/images/gs.htm).
- HAL's product listing (DDP) says the AMAGB "takes its input drive from the TEJAS ENGINE through a Power Take-Off (PTO) shaft at rated speed of 16,810 rpm". The four accessories "cater to major part of hydraulic & electrical power requirements of the aircraft and hence form a crucial part of the Secondary Power System" — [DDP node 8779, "AMAGB (LCA)"](https://www.ddpmod.gov.in/node/8779). The same text, with "CVRDE has been entrusted with abinitio design and development of an AMAGB for LCA ... sanctioned by ADA", appears in the Government Open Data catalogue (published 9 May 2013) — [data.gov.in catalogue entry](https://www.data.gov.in/catalog/aircraft-mounted-accessory-gearbox-light-combat-aircraft-tejas).
- DRDO describes the AMAGB as "lightweight, compact, high speed, single input and multi-output gearbox of aeronautical standards and self-contained lubrication system". It "has successfully logged more than 6000 flying hours", and the ToT went to HAL(E) Bangalore for series production. A separate DRDO statement says AMAGB "life was enhanced upto 750 hrs". CVRDE "designed and developed 13 types of high speed LCA-AMAGB Bearings" — [DRDO "AMAGB for LCA"](https://drdo.gov.in/amagb-lca); [DRDO "Bearings for LCA Tejas"](https://drdo.gov.in/bearings-lca-tejas) (search-index excerpts; pages not retrievable). Note: 6,000 FH is cumulative fleet experience and 750 h is a per-unit life/TBO. These are different metrics, not a conflict.
- ADA lists AMAGB bearings and AMAGB castings (pattern tooling, inspection fixture) among technology-development projects (2015-22) — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf); [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf); [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf) (OCR).
- CEMILAC listed "Clearance of long duration sortie in respect of AMAGB and integration of advanced JFS" as an open FOC challenge — [Arun, Mahuli & Jayapal, JOAST 67(2A) 2015](https://joast.org/index.php/joast/article/view/325).
- ADA's test facilities include a "Low Temperature Test Rig ... Used for soaking Aircraft Mounted Accessory Gear Box (AMAGB) & for motoring test run" (Freon cold chamber, "temperature upto 54 °C", presumably −54 °C) and a "Secondary Power Supply Rig" — [ADA GS integration facilities](https://www.ada.gov.in/images/GS%20Integration%20facilities.htm).
- Mk2: "Engine Gear Box (EGB) – Power Take Off (PTO) – AMAGB critical speed margin issue was resolved" and "Optimization of Electrical load on AMAGB pad for LCA AF Mk2 was completed" — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf); [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf) (OCR). Shaft critical speeds and pad loads are design-tracked quantities.

**PTO shaft [DIRECT]**
- DRDO's indigenous PTO shaft (CVRDE Chennai) first flew on LSP-3 at Bengaluru on 14 Mar 2023. It transmits power "between aircraft engine gear box and Aircraft Mounted Accessory Gear Box". It is "light weight, high speed, lubrication free", accommodates "misalignments that arise in the drive line", and uses a patented "Frequency Spanning Technique" to operate across engine speeds. ToT went to Godrej & Boyce and Lakshmi Technology — [Aviation & Defence Universe, Mar 2023](https://aviation-defence-universe.com/maiden-successful-flight-test-of-drdos-indigenous-power-take-off-shaft-conducted-on-lca-tejas-in-bengaluru).
- Shaft rating: "peak starting torque of 410 Nm and normal operating torque of 118 Nm at 16,810 rpm" — [DRDO "Power Take Off shaft of LCA Tejas"](https://www.drdo.gov.in/power-take-shaft-lca-tejas-0) (search-index excerpt; page not retrievable).
- Derived: 118 N·m × 16,810 rpm (1,760 rad/s) ≈ **208 kW** normal transmitted power. A 110 kW starter delivering 410 N·m implies peak starter torque near 2,560 rpm, about 15 % N2. That is consistent with starter assistance being greatest just before light-off (see the engine sibling's start sequence).
- 16,810 rpm equals the F404 compressor (N2) design speed, 16,810 rpm (ARL, Frith 1985), and 100 % N2 ≈ 280 Hz ≈ 16,800 rpm (DSTO), as compiled in `f404_in20_engine_model.md` [TRANSFER: F404-400 → IN20]. The PTO therefore turns at about 1:1 with N2. [ASSUMPTION; validate the gear ratio with ADA/CVRDE]

**Jet fuel starter GTSU-110 [DIRECT]**
- "The Jet Fuel Starter (JFS) ... is a twin shaft gas turbine consisting of a centrifugal compressor driven by an axial turbine, reverse flow combustor, digital electronic fuel control system and a free power turbine that supplies the motive power for starting the LCA engine". Intake diameter 0.29 m, length 0.64 m, weight 52 kg, power 110 kW — [DDP node 8778, "GTSU-110 (LCA)"](https://www.ddpmod.gov.in/node/8778).
- The JFS is used "for ground starts and in-flight relight" — [ADA PS integration facilities](https://www.ada.gov.in/images/PS%20Integration%20facilities.htm). Mk2 work: "Studies for inflight re-start with JFS" and "high power GTSU-127 for LCA Mk2" — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf); [ADA Propulsion page](https://www.ada.gov.in/images/ps.htm).
- CAG findings:
  - JFS performance is "very critical particularly while operating in the Himalayan Terrain, where the temperature goes below (–) 16 degrees centigrade".
  - The ASR requires two consecutive starts. The IAF asked for three (two engine starts and a dry rollover).
  - GTSU-110 M1 "could not be proved for the mandatory three consecutive starts" in trials at Leh in Jan 2013 and Jan 2014.
  - Bangalore trials (Jan 2014) showed "excessive oil consumption by JFS beyond permitted levels".
  - The first series aircraft were delivered with the original GTSU-110 pending M2 retrofit.
  - Source: [CAG Report 17 of 2015, p. 35](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
- CAG also names JFS as a "low reliability" critical LRU on the LSP fleet — [CAG 17/2015, p. 42](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
- Cold trial (Jan 2015, Leh): "three consecutive starts using indigenous gas turbine starter at -15 °C with 85% charged battery". The aircraft was "cold soaked for 18-20 hours (even 42 hours on one occasion)" with "no heating source". Rig trials with a modified starting schedule ran at Leh (3,260 m) in Jul–Aug 2014, and start capability was shown at 5.6 km. Source: HAL chairman via [Indian Defence Review, 2 Feb 2015](https://indiandefencereview.com/lca-tejas-passes-cold-weather-test-at-leh/).
- The DRDO statement adds that the JFS was rig-tested "across the operating altitudes including Leh (10,700 ft.) and Khardungla (18300 ft.)", that control software was tuned for "all operating altitudes with no adjustments from cockpit", and that the "GE-F404-IN20 start-up control schedule was varied with several control patches". It notes that three consecutive starts "with a partially charged battery" is the stringent case — [LiveFist reproduction of the DRDO release](https://www.livefistdefence.com/?p=236) (search-index excerpt).
- M2 fix: "JFS GTSU 110M2 (with self contained lubrication system) ... Each Engine ground run encompassed three successive engine starts ... and oil consumption assessed" — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) (OCR); "JFS with self contained oil tank (GTSU 110M2)" is a continuing project (ADA AR 2019-22).

**Transfer: F404-family airframe-mounted drives**
- F/A-18 HARV flight-research recordings include AMAD (airframe-mounted accessory drive) cautions as 40-sample/s discretes: "L AMAD OIL LOW", "R AMAD OIL LOW", "L AMAD OIL TEMP HIGH", "R AMAD OIL TEMP HIGH" — [NASA CR-201670, App. A, PDF pp. ~58-63](https://ntrs.nasa.gov/citations/19970014822). [TRANSFER: F/A-18 AMAD is the functional analogue of the Tejas AMAGB. It shows the typical health signals of an airframe gearbox (oil level and oil temperature cautions). Limit: AMAD design and thresholds differ.]
- T-50 (F404-GE-102): APU → air turbine starter → AMAD → PTO shaft → engine-mounted accessory drive. Starter cut-out ≈55 % N2, idle ≈63–70 % N2 — compiled in `f404_in20_engine_model.md` from Jung et al. 2006 [TRANSFER: closest public F404 start chain].

### Inferences
- [ASSUMPTION] AMAGB output-pad speeds are fixed gear ratios of N2. Pump and generator speeds therefore track N2 between about 60–70 % (ground idle) and 100–105 %. Any N2-proportional signal (pump flow capability, generator excitation margin, AMAGB oil churning heat) should be computed from N2 through constant ratios. Validate the ratios with CVRDE/ADA drawings.
- [ASSUMPTION] AMAGB load torque = Σ pump torques (ΔP·D/(2π·η_m)) + generator input (P_e/(η·ω)) + gear/bearing losses. The PTO's 118 N·m normal operating torque (≈208 kW) is a calibration ceiling for the summed accessory load at 100 % N2.
- [ASSUMPTION] JFS start-success model: P(success) falls with lower ambient temperature (oil viscosity, battery cranking power), higher pressure altitude, lower battery state of charge and a starter oil-level deficit. Use the CAG/HAL anchors: M1 failed 3-in-a-row at Leh in Jan 2013/14, and M2 or the modified schedule passed at −15 °C with an 85 % battery after an 18–20 h soak.
- [ASSUMPTION] JFS oil consumption should be a per-start increment with fleet scatter, plus a degraded mode (excess consumption) and a maintenance "oil uplift" record (M1 vs M2).

### Gaps
- AMAGB gear ratios, pad speeds, weight, oil quantity and type, oil temperature/level/chip sensors and their thresholds: not public. The F/A-18 AMAD cautions are the only transfer.
- GTSU-110 start-cycle timing (time to engagement and cut-out), JFS speed and EGT limits, starter-motor battery current and clutch details: not found. HAL AERDC design papers were not located.
- How the JFS supports in-flight relight (motoring assistance profile, altitude/airspeed limits): not public. Only the statement that it is used for relight.

---

## KQ2. Hydraulic system (two 280 bar systems, pumps, reservoirs, accumulators, filters, consumers, sensors)

### Takeaway
Tejas has two hydraulic systems at a nominal 280 bar (≈4,060 psi; MIL-H-5440 "Class 4000"-like). They are powered by two AMAGB-driven pumps. Primary FCS actuators (4 elevons, 1 rudder) are dual-hydraulic tandem units, slats are single-hydraulic, and the airbrakes are open-loop jacks via electro-selector valves. The system has 9 filters of 6 types, hydraulically unlocked mechanical uplocks, and emergency undercarriage and park-brake cable controls. HAL product pages give credible LRU numbers that are probably Tejas parts: a bootstrap reservoir (LH/RH; 280/5.5 bar; 9.5 L; −54 to +135 °C; MIL-H-5606; level sensor), an airbrake actuator (2.5–5 t, 294 mm, dual LVDT) and an electro-selector valve (40 L/min, 12.5 bar ΔP). Tejas pump flow rating and type are not confirmed. A search-index excerpt suggests 110 L/min at 280 bar per pump, and the PTO power budget is consistent with that.

### Cited Findings
**Architecture and consumers [DIRECT]**
- Elevons and rudder are quadruplex electrical and "dual hydraulic at 280 bar". The six leading-edge slat actuators (three types) are single-hydraulic with EHSV and dual electrical control. Airbrakes are open-loop jacks via electro-selector valves. "These servo actuators have a frequency response of 9 Hz and ... stall load capability of 2-10 tons" — [Kala (ADE), JOAST 67(2A) 2015](https://joast.org/index.php/joast/article/view/317).
- 13 FCS actuators: 4 elevon, 1 rudder, 6 LE slat, 2 airbrake — [CAG 17/2015, pp. 36-37](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf). Indigenous LE-slat actuators and the airbrake control module ("Servo-Valve based electro-hydraulic servo actuators", "high pressure, redundant") were handed to HAL Lucknow for the Mk1A — [PIB 19 Apr 2024](https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2018282).
- "Hydraulic System is fitted with 9 filters of 6 types". Uplocks lock "mechanical[ly] and unlocking is controlled hydraulically" — [ADA GS page](https://www.ada.gov.in/images/gs.htm).
- The landing gear is hydraulically retracted. Its LRUs include a "Flow Synchronizer", "Progressive Pressure Control Valve", "Emergency Under Carriage Selector Valve", "Control Cable – Under Carriage Emergency" and "Control Cable – Park Brake Control" (all still imported in Dec 2022) — [ADA LRU indigenisation list](https://www.ada.gov.in/images/LRU.pdf) (image PDF, read by rendering).
- Hydraulic and nosewheel-steering work: "Analytical Study of LCA Nose Landing Gear Steering System with Associated Hydraulics"; "MEMS based Pressure Transducers for Hydraulic system"; "MEMS based Temperature sensor for Hydraulic system"; "Development of Airworthy Axial Piston Pump 30 LPM" (platform not stated) — [ADA AR 2017-18, pp. 19-20](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf).
- Hydraulic LRUs (HAL Lucknow work package) were 93 months late, and fuel-sensor/hydraulic LRUs 58 months late — [CAG 17/2015, work-centre table](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf). "Heat exchangers, pumps, sensors" of General Systems were imported — [CAG 17/2015, Annexure (indigenisation table)](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
- HAL Lucknow environmental qualification for flight-control and utility actuators covers MIL-STD-810F high/low temperature, humidity, salt fog, altitude, icing and blowing sand. Bores and rods are chrome-plated against sand and dust — [Agarwal et al. (HAL ASE R&DC Lucknow), JOAST 69(1A) 2017](https://joast.org/index.php/joast/article/view/211).

**HAL product pages: numbers, with attribution caveats**
- **Bootstrap hydraulic reservoir** [DIRECT part; Tejas fitment = ASSUMPTION — 280 bar with MIL-H-5606 and an LH/RH pair matches only Tejas among HAL-built fighters (Su-30MKI uses Russian fluids); validate with HAL Lucknow]:
  - "(LH/RH) Separated type (bootstrap) where reservoir fluid is self-pressurized through a differential area piston".
  - "level-sensing device, bleed device", port for a low-pressure relief valve.
  - HP side 280 bar, LP side 5.5 bar; −54 °C to +135 °C; MIL-H-5606 fluid; 28 V DC; total volume 9.5 L (+300/−100 cc); 490 × 280 × 305 mm; dry weight ≤12.0 kg.
  - Source: [DDP node 9659](https://www.ddpmod.gov.in/node/9659).
- **Air brake actuator** [DIRECT part; Tejas fitment = ASSUMPTION — open-loop, cockpit-initiated airbrake jack with LVDT matches Kala's description]:
  - "double acting differential area type hydraulic Actuator with in-built coaxial dual core LVDT for open loop control".
  - Fluids DEF STAN 91-48 / MIL-H-5606E / H/AIR 3520A / MIL-H-83282; −54 to 135 °C.
  - System pressure 281 kgf/cm² (≈276 bar); load 2,500–5,000 kgf; stroke 294 (+2) mm; ≤6.8 kg.
  - Source: [DDP node 9660](https://www.ddpmod.gov.in/node/9660).
- **Electro-selector valve** [DIRECT part; Tejas fitment = ASSUMPTION — 280 bar, airbrake-type selector]:
  - "3-position, 4-way double-solenoid (LH and RH) open neutral selector", with an NRV at the inlet.
  - 280 bar; maximum flow 40 L/min; maximum pressure drop 12.5 bar at 40 L/min; 28 V DC; −54 to +135 °C; 1.8 kg.
  - Source: [DDP node 9661](https://www.ddpmod.gov.in/node/9661).
- **Variable-delivery hydraulic pump, 12 L/min** [TRANSFER: HAL trainer/helicopter-class pump (207 bar, "operates landing gear and brakes") — not Tejas; it shows HAL's pump type]:
  - "variable delivery positive displacement axial piston pump with built in pressure compensator mechanism".
  - Inlet 3.5 ± 0.5 bar g; speed 3,959 ± 80 rpm; ≥12 L/min; full-flow pressure 197–207 ± 4 bar; ≤1.8 kg.
  - Source: [DDP node 9658](https://www.ddpmod.gov.in/node/9658).
- **Brake/emergency accumulator** [DIRECT part; platform unstated]:
  - "adequate for 10 brake applications in case of failure of main hydraulic system. It also dampens out any pressure pulsation".
  - Operating 68 ± 4 bar; gas charge 50 bar; 0.41 L; 1.25 kg.
  - Source: [DDP node 9656](https://www.ddpmod.gov.in/node/9656).
- **Pump flow (unverified)**: a search-engine summary of a DRDO page in an AMAGB context mentioned "two hydraulic pumps rated at 110 lpm at 280 bar each" (search-index excerpt from a [DRDO page](https://www.drdo.gov.in/hi/node/2803); page not retrievable; a repeat search did not reproduce it). Treat it as a lead, not a fact.

**Transfer: standards and donor aircraft**
- MIL-H-5440H (Distribution A) [TRANSFER: US design standard. Tejas follows MIL standards per CEMILAC, though which hydraulic spec is not stated]:
  - Type II fluid limit +275 °F (+135 °C), matching HAL's −54/+135 °C ratings. MIL-H-5606 low limit −65 °F (−54 °C). Pressure Class 4000 = 4,000 psi nominal (≈276 bar).
  - Pumps "shall use an internal pressure regulating device ... to maintain constant pressure at varying flow demands" plus an independent relief valve.
  - Per-pump pressure indication on multi-pump engine-driven systems. A low-pressure warning light per system, from a pressure switch, that must not flicker during normal flight-control operation.
  - An "automatic diagnostic monitor system" covering pumps, accumulators, filters, reservoir fluid levels, reservoir fluid temperature and system free air, stored in flight and displayed on the ground.
  - Filter condition "shall be monitored electronically". A non-bypass pressure filter per pump, a bypass-type return filter and a bypass-type case-drain filter per pump. No suction filter. Contamination Class 8 per AS4059.
  - Variable-delivery pumps must keep case cooling flow at zero output flow.
  - The design report must include fluid temperature vs time "including the maximum temperatures due to single failures such as worn pumps and relief valve bypass".
  - Source: [MIL-H-5440H, §§1.2, 3.6.1, 3.6.3.4, 3.6.13, 3.6.15, 3.11.9, 3.11.19, 6.x](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-H/MIL-H-5440H_14866/).
- F-15D utility hydraulics: above 225 °F (107 °C) a thermal valve routes all fluid through the fuel-oil heat exchanger. A weld crack there produced a non-isolable leak and loss of braking — [AIB F-15D 84-0046](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/15%20MAY%2023%20AIB%20Kingsley%20ANGB%20F-15D%20Final%20Amended%20Report_Redacted.pdf) (already in `faults_and_degradation.md`) [TRANSFER: thermostatic fuel-cooling logic; Tejas HX routing unknown].
- F-16 ISA check-valve leak: system A oscillated at 1,500–2,000 psi then 1,000–2,000 psi (nominal 3,100 ± 50 psi). System capacities ≈5 gal (A) and ≈7 gal (B) — [AIB F-16C 88-0477](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/F-16%2016%20May%2019%20March%20ARB%20ACC.pdf) [TRANSFER].
- F/A-18 HARV recorded "BRANCH 1A/1B/2A/2B HYD PRES NORMAL", "L/R HYDRO PRESSURE FAIL CH.1–4", "HYD SYS 1/2 OIL LEVEL LOW" as 40-sample/s discretes, and "STRAKE HYDRO PRESSURE 2A" as an 80-sample/s analog — [NASA CR-201670 App. A](https://ntrs.nasa.gov/citations/19970014822) [TRANSFER: shows that FCS channels see per-channel hydraulic-pressure discretes and that analog hydraulic pressure was rare in research recordings].
- NASA HARV actuator model: rate limits "as a Function of Hydraulic Pressure and External Load", with required "Hydraulic Fluid Flow (in³/sec)" computed per actuator. The linear model is valid at 90 °F fluid and 2,765 psid across the actuator — [NASA TM-110216, PDF p. ~99](https://ntrs.nasa.gov/citations/19960027892) [TRANSFER: modelling template for actuator flow demand].
- Embraer EDP: "variable displacement axial piston pump with pressure compensation system to deliver constant discharge pressure of 3.000 psi". Common failure mode: "looseness of the regulator valve spring which decreases the pump discharge pressure", sensed at no-load conditions. Run-to-failure CIs over ≈500–800 cycles — [Gomes et al., PHM 2012](https://papers.phmsociety.org/index.php/phmconf/article/view/2085) [TRANSFER: civil EDP of the same type class].

### Inferences
- [ASSUMPTION] Model each system as a pressure-compensated variable-displacement pump with maximum flow Q_max = D·n_pump(N2)·η_v. Steady discharge pressure holds at ≈280 bar while demand ≤ Q_max. It sags only when actuator demand exceeds Q_max (low N2 on the ground with simultaneous gear, NWS and control sweeps; windmill N2 in flight) or when leakage rises. Validate D and pad ratio against an HAL/ADA pump datasheet. If the 110 L/min figure is confirmed, Q_max(100 % N2) ≈ 110 L/min and the hydraulic power ≈ 51 kW per pump (derived), so about 103 kW for both. With generator and losses this sits inside the ≈208 kW PTO normal rating (derived consistency check).
- [ASSUMPTION] Actuator flow demand Q_i = A_i·|ẋ_i|. A tandem elevon actuator with a 10 t stall load at 280 bar needs ≈35 cm² total effective area, ≈17.5 cm² per system half (derived: 98.1 kN / 28 MPa). At 100 mm/s that is ≈10.5 L/min per system per elevon (derived). Four elevons plus rudder plus slats at full rate can approach several tens of L/min per system. That is why pressure ripple and sag correlate with FCS activity (gust, high-AoA, PIO) and are visible in the data.
- [ASSUMPTION] Reservoir level indication = fluid volume in the bootstrap reservoir, a function of temperature (thermal expansion), accumulator charge state, actuator rod positions (differential volumes, e.g. gear down vs up) and leakage. A slow downward trend at matched temperature and configuration is the leakage signature.
- [ASSUMPTION] Assignment of consumers to systems is not public. Use: system 1 and system 2 both feed the tandem primaries; one system feeds slats, gear, NWS, wheel brakes and the airbrake; the brake accumulator gives about 10 applications on loss of that system (HAL accumulator text). Validate with an ADA hydraulic schematic.

### Gaps
- Pump vendor, type confirmation, displacement and rated flow; pad speed; case-drain arrangement; heat-exchanger type and location (fuel-cooled or air-cooled); fluid in service (MIL-H-5606 vs MIL-PRF-83282/87257); the 9 filter locations and their ΔP-indicator type (visual pop-up vs electrical); accumulator count and precharges; assignment of consumers to systems; emergency power (no EPU/RAT is documented for Tejas). None found in public sources.

---

## KQ3. Fuel system (tanks, gauging, transfer/feed, refuelling, AAR, drop tanks, heat sink, warnings)

### Takeaway
Public Tejas fuel-system facts:
- named fuselage tanks F1, F1A and F2 plus wing tanks (wing-fore probes);
- internal fuel about 2,458 kg / 3,060 L (secondary source);
- 1,200 L, 800 L and 725 L drop tanks, with a three-drop-tank ferry demonstrated;
- pressure refuelling and hot refuelling; air-to-air refuelling from Il-78 at 250–295 kt;
- capacitance gauging probes (HAL Lucknow, frequency/period output) processed by the ECFM controller with attitude compensation;
- an "F2 pump" with auto operation, a higher-capacity DC fuel pump for windmill relight, auto-transfer logic, and fuel-tank pressurisation from the ECS.

One documented data artefact matters: a low-fuel warning and F1/F2 content drop during >40° nose-up climbs at max AB with <1,200 kg remaining. The tank-by-tank capacities, transfer sequence, boost-pump ratings and fuel-temperature limits are not public. Use transfer donors (Gripen, F/A-18) and MIL-G-26988C for gauging behaviour.

### Cited Findings
**Tejas facts [DIRECT]**
- Internal fuel 2,458 kg (3,060 L); drop tanks 2 × 1,200 L inboard, 800 L, and 725 L centreline — [Wikipedia HAL Tejas spec table](https://en.wikipedia.org/wiki/HAL_Tejas) [DIRECT, secondary; 2,458/3,060 ≈ 0.803 kg/L is consistent with Jet A-1/ATF density].
- CAG:
  - IOC Mk1 did not meet the ASR on "reduced internal fuel capacity", "non-achievement of single point defueling" and "fuel system protection" (pp. 13-14).
  - Fuel-system deficiency is a permanent waiver, so "all the LCA Mk-I would have deficiencies in Fuel System" (p. 42).
  - LSP-7 introduced "Major changes in fuel system".
  - "fuel leak" is listed among structural problems (p. 42).
  - Source: [CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
- Zoom-climb artefact:
  - "fuel drop and low fuel warning being posted when climb is initiated with low fuel and high pitch angle at maximum after burner", fixed by a mod "on F1A fuel tank" — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf).
  - Verification: "zoom climb, at fuel remaining less than 1200 Kg, pitch up >40° (after optimization of fuel pick up and vent mod in F1A tank) ... towards resolving low fuel warning/drop in F1/F2 tank contents during high pitch climb with max after burner" — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) (OCR).
  - Trainer: "Flight Performance Assessment of LCA Trainer Fuel System Modifications: Zoom climb performance has been characterized" — [ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf) (OCR).
- "Higher capacity DC fuel pump for improved performance during in-flight engine wind mill relight: integration and flight testing ... on LSP3 ... completed" — [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf) (OCR).
- Navy NP2 production-standard features:
  - "Fuel Dump System", "Pressure and Hot refueling", "Fuel auto transfer functionality", "Updated ECFM systems", "Attitude Compensated Fuel System".
  - "ECFM software is updated ... for Enhanced Fuel gauging, F2 Pump Auto Operation, Fuel dumping and Hot refueling".
  - NP1: "Partial Pressure Refueling up to 25 psi demonstrated"; NP2: "Hot Refueling at 50 psi".
  - Source: [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf).
- Hot refuelling ("refuelling after a sortie, with engine running") began as practice on LSP-8, "enhancing sortie generation rate" — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf).
- AAR:
  - LSP-8 drew fuel from an IAF Il-78 "in different altitudes at speeds ranging from 250 knots-295 knots and from all fuel stations of the tanker" — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) (OCR).
  - Later phases: drop tanks fitted "with fuel content gauging probes for full fuel top up during AAR"; day/night wet contacts; buddy refuelling from Su-30 pods "(104 contacts)" — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf) (OCR).
  - The AAR probe is Cobham-supplied — [Wikipedia HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas) [secondary].
- Gauging hardware:
  - "Trials for Fuel gauging with new fuel 18 series fuel gauging probes" — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) (OCR).
  - "Development and Supply of Fuel Gauging Probe P/N 188100000, Issue-4" — [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf); [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf) (OCR).
  - CEMILAC technical-approval listings name HAL Accessories Division, Lucknow probes: "Fuel Content Gauge (FCG) F2-A/B Probe Pt. No. 187800000", "Top Mounted Fuel Content Gauging Probe (Fuselage Tank FCG Probe) Pt. No. 232000000" (TA-1863), "DFM-Fuel Sensors W-F/1 Probe (Wing Tank Fore-immersed probe), Pt. No. 239200000" (TA-1809) — [DRDO node 10962](https://drdo.gov.in/drdo/node/10962); [node 10975](https://drdo.gov.in/drdo/node/10975); [node 10972](https://drdo.gov.in/drdo/node/10972) (search-index excerpts; pages not retrievable) [DIRECT-by-nomenclature: the "F2" and "18-series" naming matches ADA's Tejas usage].
- HAL "Fuel Content Gauging Probe (F2-F/T)" [DIRECT part; Tejas fitment = ASSUMPTION — "F2" tank naming]:
  - "concentric precision aluminum alloy tubes insulated from each other to form capacitance plates. The sensing capacitance is converted into frequency by stable oscillator circuit ... within the flange head ... output ... is frequency, which varies inversely with immersed fuel level".
  - Period accuracy ±3 µs empty, ±5 µs wet; length 230 ± 2 mm; ≤350 g.
  - Source: [DDP node 10090](https://www.ddpmod.gov.in/node/10090).
- A DRDO TDF requirement for indigenous fuel probes states that "both fuel gauging sensor and level switch sensor shall be capacitive type", with operating media JET A-1/JP-8/JP-5 — [TDF "Fuel Probe for Aircraft Application"](https://tdf.drdo.gov.in/node/4963) (search-index excerpt; page not retrievable). Level switches (low-level and refuel shut-off) are therefore probably also capacitive.
- The ECS "supplies compressed air for pressurisation of cockpit, radar and fuel tank" — [ADA CEF page](https://www.ada.gov.in/images/cef.htm). Mk2 lists "Wing tanks pressurisation enhancement" and "Wing fuel tanks partitioning" — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf).
- The Environment Control and Fuel Monitoring (ECFM) system comprises "ECFM-C (ECFM Controller), ECS-CP (ECFM Control Panel) and GRP (Ground Refueling Panel)" and controls "the environment of the cockpit and the avionics bay on the LCA" — [L&T Precision Engineering, avionics & life-support page](https://larsentoubro.com/lt-pes/our-offerings/electronics-products-and-systems/avionics-and-life-support-systems) (search-index excerpt; the live page now requires sign-in).

**Transfer donors**
- Gripen fuel-system model [TRANSFER: Saab Gripen, same weight class, F404-family engine; methodology and structure transfer, numbers do not]:
  - "300 components and a control unit with 270 input signals and 80 output signals".
  - Simulated states: flows, pressures, pump speeds, sensor and control signals.
  - Inputs: flight conditions including g-forces and altitude; engine fuel consumption as the energy interface.
  - Refuelling of "the seven tanks" was simulated (content and tank pressure vs time).
  - Tanks were modelled as low-order air dynamics with fuel treated algebraically, because fuel "is approximately 10 times less compressible than air" (as stated) and makes the equations stiff.
  - About 50 % of LRU removals are NFF, which makes the monitoring software worth simulating.
  - Source: [Lantto, Ellström, Steinkellner & Jareland, ICAS 2006 paper 039](https://icas.org/ICAS_ARCHIVE/ICAS2006/PAPERS/039.PDF).
- F/A-18 HARV fuel signals (40 samples/s): fuel quantity left/right wing, tanks 1–4 and total; "FUEL TANKS PRESSURE"; "L/R BOOST PRESS LOW"; "TANK NO 2/3 START OF DEPLET"; "TANK NO 1/2 EMPTY"; "FUEL LOW"; "BINGO FUEL"; "FUEL DUMP OPEN"; "EXT TANK PRESSURIZED/OVERPRESSURIZED"; "LT/RT FUEL INLET TEMP"; "FUEL GAGING SYS IN TEST"; "REFUEL PROBE EXTENDED" — [NASA CR-201670 App. A](https://ntrs.nasa.gov/citations/19970014822) [TRANSFER: F404-family fighter fuel signal set; Tejas is single-engine].
- MIL-G-26988C (capacitance gauging) accuracy classes: Class I ±4 % of indication ±2 % of full scale; Class II ±2 % of indication ±0.75 % FS; Class III ±1 % of indication ±0.5 % FS. It requires attitude-error correction from a fuel-attitude sensor and stored correction data, and dielectric-constant-based density compensation (mass indication) — [MIL-G-26988C, Table I and §§3.6.2–3.6.3](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-G/MIL-G-26988C_36788/) [TRANSFER: US gauging spec; Tejas class unknown].
- MIL-F-17874B (Navy aircraft fuel-system installation and test, 1965; OCR scan) [TRANSFER: legacy US requirement; shows conventional warning architecture]:
  - A low-fuel-level warning in gas-turbine aircraft should indicate roughly a small percentage of internal fuel (the OCR digit is unclear) "or 30 minutes of fuel remaining in the engine(s) feed tank(s) at maximum range cruise power at 10,000 feet, whichever is less".
  - "The low level warning system shall be entirely independent of the fuel gaging system".
  - Drop-tank fuel is transferred directly to the engine feed tanks.
  - Tanks keep 5 % expansion space; feed shut-off ≤3 s at sea-level take-off power; refuelling surge limited to 120 psig.
  - Cockpit/refuel-panel indications: boost-pump pressure, transfer-pump pressure, impending fuel-filter bypass, low-level warning.
  - Source: [MIL-F-17874B, §§3.3.4.4, 3.3.9.3.3.1, 3.3.13](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-F/MIL-F-17874B_20580/).
  - For Tejas, the DRDO TDF requirement for a capacitive "level switch sensor" separate from the gauging probe is consistent with an independent low-level switch [ASSUMPTION].
- Fuel as heat sink:
  - Jet-fuel temperature at the combustor nozzles must stay below coking limits, e.g. 325 °F (163 °C) for JP-4/JP-5 — [US 4,776,536](https://patents.google.com/patent/US4776536).
  - Typical coking limit "about 300° F" at the nozzle, with starting fuel temperature from about 60 °F (standard day) to 120 °F (hot day). Recirculated fuel can return to tanks at up to 300 °F — (patent search excerpts) [TRANSFER: generic fighter thermal-management patents; Tejas limits unknown].
- Civil recorder practice: fuel quantity recorded at 64 s resolution intervals with 1 % FS resolution — [14 CFR 121 App. M, via `sensor_residual_texture.md`](https://www.law.cornell.edu/cfr/text/14/appendix-M_to_part_121) [TRANSFER: texture for slow-rate logging only].

### Inferences
- [ASSUMPTION] Feed architecture: F1/F1A/F2 are fuselage tanks. F2, with an "F2 pump", auto operation and multiple probes (A/B, F/T), is the feed/collector region. Wing and drop tanks transfer into the fuselage group under ECFM auto-transfer logic, assisted by ECS tank pressurisation. Validate with an ADA fuel schematic.
- [ASSUMPTION] The zoom-climb artefact is a physical slosh/pick-up phenomenon: at high pitch and longitudinal acceleration with low contents, fuel migrates aft in F1/F1A/F2. Probe-indicated contents drop, which trips the low-fuel logic. The generator should reproduce attitude/acceleration-dependent gauging error that grows as contents fall. ADA reports the effect as resolved by a pick-up/vent modification, so it can be a configuration-dependent "pre-mod" behaviour.
- [ASSUMPTION] Fuel flow comes from the engine model. The sibling's derived SLS MIL Wf is ≈8,270 lb/h (≈1.04 kg/s). With max AB SFC ≈1.84 lb/lbf/h on the -400 base, AB Wf is several kg/s. So 2,458 kg internal lasts ≈40 min at MIL SLS and ≈10 min at full AB (derived, order-of-magnitude). The tank-depletion sequence must track this to keep CG within limits.
- [ASSUMPTION] Fuel temperature per tank rises with heat rejected by the engine fuel-oil cooler (engine sibling) and the hydraulic/ECS fuel-cooled heat exchangers. It rises fastest at low fuel flow (idle, hot-day ground holds) and low remaining fuel. That links the Indian hot-day environment (Jaisalmer soak 39–42 °C) to fuel- and oil-temperature cautions.

### Gaps
- Tank-by-tank capacities, transfer sequence and CG schedule; number and location of probes; boost/transfer pump type, voltage (DC confirmed for the windmill-relight pump; AC 400 Hz transfer-pump motor work is a future-technology item in ADA AR 2020-21) and flow; negative-g provisions; fuel-temperature limits and heat-exchanger arrangement; refuel/defuel valve logic; vent-system design. None public.
- The Gavel (2007) thesis on Gripen fuel systems was unreachable (DiVA refused connection).

---

## KQ4. Electrical power (generation, conversion, storage, buses, emergency power, power quality)

### Takeaway
The confirmed Tejas electrical facts are:
- one engine-driven main AC generator on an AMAGB pad (imported; rating not public);
- a DRDO 5 kW brushless DC generator that backs up critical loads if the main AC generator fails (PMG + exciter + main stage, FPGA/DSP regulator with BITE, 1,250 h endurance test);
- a DC emergency bus;
- a battery that also cranks the JFS (Ni-Cd replaced Ag-Zn on the naval prototype; Li-ion under development for Mk2).

HAL product pages add plausible Tejas-class conversion parts: two 7.5 kW/250 A TRUs fed from 115/200 V 3-phase 400 Hz, a master box that reconfigures among two TRUs, the 5 kW DC generator and a 45 Ah battery, and a battery Ah display with a 30 Ah low warning. Power-quality texture (steady-state bands, ripple, transients, 50 ms transfer interrupts, emergency and starting voltage floors) can be taken directly from MIL-STD-704F (Distribution A). Generator dropout on spool-down and bus transfers are documented on F-16s.

### Cited Findings
**Tejas facts [DIRECT]**
- Imports include "Electrical Generators" — [CAG 17/2015, Annexure (indigenisation table), p. ~62](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf). The generator is on the AMAGB ("1 Generator") — [ADA GS](https://www.ada.gov.in/images/gs.htm). ADA runs an "Electrical System Test Rig" that "Tests power generation & distribution system of LCA" — [ADA GS integration facilities](https://www.ada.gov.in/images/GS%20Integration%20facilities.htm).
- DRDO "5 kW brushless DC Generating system for LCA Tejas":
  - Backs up critical loads for flight safety if the main AC generator fails.
  - "Generator comprises of Permanent Magnet stage, Main Exciter and Main Generator facilitating autonomous mode".
  - "FPGA/DSP based embedded controller featuring precise voltage regulation with BITE facility to meet stringent MIL standards".
  - "successfully completed 1250 hours of Endurance test".
  - Source: [DRDO page](https://drdo.gov.in/5-kw-brushless-dc-generating-system-lca-tejas-0) (search-index excerpts; page not retrievable).
  - ADA AR 2020-21: "Indigenous development of 5kW DC generator is in progress" — [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf) (OCR).
- Mk2 electrical-system optimisation: weight saving of ≈60 kg achievable, "Optimization of DC emergency bus electrical loads was completed", "Optimization of Electrical load on AMAGB pad for LCA AF Mk2 was completed", and Li-ion battery development via NSTL and ISRO — [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf) (OCR).
- Batteries: naval prototype mod "Ni-Cd Battery in place of Ag-Zn battery in NP1" — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf). The JFS cold-start requirement was demonstrated "with 85% charged battery" — [IDR, Feb 2015](https://indiandefencereview.com/lca-tejas-passes-cold-weather-test-at-leh/).
- Future-technology work: "Liquid cooled Variable Speed Constant Frequency 60/75kVA Aircraft Generator" with NFTDC and IISc; "Variable Speed Constant frequency converter (VSCF) with liquid cooling" — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf) (OCR). This shows the direction for Mk2/AMCA, not the Mk1A fit.
- DFCC: four channels with independent power inputs; the DFCC is "designed to run 1 h without cooling air" — [Kala, JOAST 67(2A)](https://joast.org/index.php/joast/article/view/317). The ADC was designed to MIL-STD-704D (same source).

**HAL electrical-conversion products [DIRECT part; Tejas fitment = ASSUMPTION — the master box's source set (two TRUs + 5 kW DC generator + 45 Ah battery) matches the DRDO Tejas 5 kW DC backup generator; validate with HAL]**
- Transformer-rectifier unit: input 115 V (L-N)/200 V (L-L) 3-phase 400 Hz; output regulated 28 V DC nominal, 250 A, 7.5 kW; overload 150 % for 2 min, 200 % for 1 min, 400 % for 1 s; efficiency 90 % at 250 A; 12.8 kg — [DDP node 9646](https://www.ddpmod.gov.in/node/9646).
- "AC Master Box": "receives power from two Transformer Rectifier Units, 5KW DC Generator, 45AH Battery. It distributes power to Main Bus, Essential Bus, Emergency Bus, Alert-1 and Alert-2 Bus. Unit automatically reconfigures based on availability of input power source". Bus list: 3-ph AC Main, 3-ph AC Essential, 1-ph AC Emergency, 3-ph AC Alert-1, 1-ph AC Alert-2; nominal 28 V DC, 115 V AC — [DDP node 9647](https://www.ddpmod.gov.in/node/9647). Note an internal inconsistency on the page: DC sources are listed with AC buses.
- Battery Ah display unit: integrates battery-terminal current to show available Ah; "Fully charged indication 45 AH", "Charging current 50 A", "Battery low warning output 30 AH" — [DDP node 10096](https://www.ddpmod.gov.in/node/10096).
- Static inverter: 28 V DC → 115 Vrms ± 2 % single-phase, 250 VA, >60 % efficiency; protections for over-voltage, over-frequency, over-current, reverse polarity and over-temperature — [DDP node 9648](https://www.ddpmod.gov.in/node/9648) (platform unstated; plausible feed for a 1-phase AC emergency bus).
- [TRANSFER: HAL helicopter DC distribution, ALH-class] DC master box: 22–29 V DC normal, 16 V DC emergency; main-bus loads 100 A and 50 A; emergency bus 110 A and 50 A; battery hot bus 7.5 A; protections include ground-power protection, battery-discharge monitoring and short-circuit protection — [DDP node 9649](https://www.ddpmod.gov.in/node/9649).

**Standards and donor aircraft**
- MIL-STD-704F w/Change 1 (5 Dec 2016) [TRANSFER: the Tejas ADC was designed to MIL-STD-704D; 704F is the current public version and gives texture bands]:
  - 400 Hz AC normal: steady voltage 108.0–118.0 V RMS; unbalance ≤3.0 V; modulation ≤2.5 V RMS; phase difference 116–124°; distortion factor ≤0.05; crest factor 1.31–1.51; DC component ±0.10 V; steady frequency 393–407 Hz; frequency modulation 4 Hz; peak ±271.8 V.
  - Variable-frequency AC: 360–800 Hz, ≤250 Hz/s rate of change (normal), ≤500 Hz/s (abnormal).
  - 28 V DC normal: 22.0–29.0 V steady; distortion factor ≤0.035; ripple ≤1.5 V. 270 V DC: 250–280 V, ripple ≤6.0 V.
  - Bus/source transfer: voltage and frequency may vary between zero and normal limits for up to 50 ms.
  - DC emergency operation 16–29 V; DC during electric starting 12–29 V.
  - Source: [MIL-STD-704F CHG-1, Tables I–IV, §§5.1, 5.2.4–5.2.5, 5.3.2](https://everyspec.com/MIL-STD/MIL-STD-0700-0799/MIL-STD-704F_CHG-1_55461/).
- AFTI/F-16 DFCS power: "the 40 kVA primary generator and the 5 kVA emergency generator through ac to dc converters, a 500 VA permanent magnet generator (PMG) on the emergency generator, and two batteries". The DFCS needed only 28 V DC — [NASA TP-2857, PDF p. 14](https://ntrs.nasa.gov/citations/19890014956). An EPU energised at high engine rpm caused a PMG voltage surge and an overvoltage-relay disconnect of the primary electrical system ("design oversight") — [TP-2857, PDF p. ~42](https://ntrs.nasa.gov/citations/19890014956) [TRANSFER: single-engine FBW fighter power architecture of the same class].
- F-16 spool-down: main and standby generators "fell offline" during spool-down, causing a momentary power disruption before the emergency generator came online — [AIB F-16C 90-0755 (Holloman 2019)](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf). Partial power loss made EGI data invalid without flags — [AIB F-16C 88-0549](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/6May23%20PACAF%20F-16C%20AIB%20Report.pdf) (both already in `faults_and_degradation.md`) [TRANSFER].
- F/A-18 HARV electrical discretes (40 samples/s): "L/R GEN OUT", "UTILITY BATTERY LOW", "UTILITY BATT/CHAR FAIL", "EMERGENCY BATTERY LOW", "EMER BATTERY/CHARGER FAIL", "BATTERY SW CHK", "ESSENTIAL AVIONICS HOT", ±5 V monitors — [NASA CR-201670 App. A](https://ntrs.nasa.gov/citations/19970014822) [TRANSFER].

### Inferences
- [ASSUMPTION] Source logic as a state machine. Main AC generator online when N2 ≥ a cut-in threshold and the GCU reports voltage/frequency inside MIL-STD-704F bands. It trips offline on under-speed (spool-down, flameout), over-/under-voltage, over-/under-frequency or internal fault. Loss of the main generator transfers critical DC loads to the 5 kW DC backup and battery, with a ≤50 ms transfer interruption. Battery-only operation sags toward the 16 V emergency floor and the 30 Ah low warning. Validate thresholds with ADA electrical schematics.
- [ASSUMPTION] Whether the main generator is constant-frequency (IDG/CSD) or variable-frequency is unknown. The HAL TRU's 400 Hz input and ADA's later move to VSCF suggest a constant-frequency 400 Hz system. Model frequency as 400 Hz ± 7 Hz (normal band) once online, with small N2-transient excursions. Do not make it proportional to N2 unless VF is confirmed.
- [ASSUMPTION] Main-generator rating: use 30–40 kVA by transfer from the F-16 Block 30/AFTI (40 kVA). That is consistent with two 7.5 kW TRUs (15 kW DC) plus radar, ECS fans and heaters, and pitot heaters on AC. Replace with the Tejas value if one is found.
- [ASSUMPTION] Electrical load must be mission-phase dependent: ground/APU-less ground power, JFS crank (battery current spike), taxi, take-off, cruise, combat (radar transmit, EW, weapons), probe/windscreen heating in icing or cold, landing. Battery Ah integrates charge/discharge (HAL display semantics). Power-quality texture comes from 704F bands (ripple ≤1.5 V on 28 V; AC modulation ≤2.5 V RMS).

### Gaps
- Main generator rating, type (CF vs VF), cooling (oil or air) and vendor; TRU count and ratings on Tejas; battery chemistry and capacity on Mk1/Mk1A; bus names and load-shed logic; whether the 5 kW DC generator is AMAGB-driven or engine-gearbox-driven; generator-control-unit BIT codes. None public.

---

## KQ5. Environmental control, life support (OBOGS/LOX), avionics cooling, anti-icing and demisting

### Takeaway
The Tejas ECS is a bleed-air system. It cools the pilot and avionics and pressurises the cockpit, radar and fuel tanks, and (Mk1A) feeds OBOGS. Imported ECS LRUs include:
- bleed-inlet and high/low pressure switches;
- temperature sensors spanning −55 to 100 °C and −55 to 300 °C;
- a hot-air-leak detection control box and sensing element.

Indian programmes added a cabin shut-off valve, a cabin pressure control system (CPCS), and LP-bleed shut-off and non-return valves for Mk2. ADA built 10 types of compact plate-fin heat exchangers.

A HAL "primary heat exchanger" (34.5 kg/min, 6.56 bar, ≤578 °C in, <170 °C out) is a probable Tejas part. A HAL-ARDC paper on an "advanced fighter" bootstrap ECS gives bleed conditions of 2.8–6.4 bar and 175–440 °C over 75–97 % engine rpm, and 4 samples/s temperature/pressure measurement. OBOGS uses PSA/zeolite and was cleared to 50,000 ft on PV-3 in 2025. Mk1 used LOX, with a 0–5 L indicator feeding ECFM-C.

Normal-behaviour texture: ECS condensate drained after humid-weather flights (official PIB statement), hot-soak trials at 39–42 °C, and MIL-E-18927E pressurisation-rate and WBGT limits. A fighter cockpit pressure schedule of about 5 psi differential above 23,000 ft is a transfer, not a Tejas fact.

### Cited Findings
**Tejas facts [DIRECT]**
- "The Environmental Control System (ECS) is designed to give a high degree of comfort to the pilot and to provide adequate cooling to all onboard electronic systems. The compressed air for pressurisation of cockpit, radar and fuel tank is also supplied by ECS" — [ADA CEF page](https://www.ada.gov.in/images/cef.htm). ADA has the "First ECS integration facility in India", which "Qualifies Environmental Control System of LCA" — [ADA GS facilities](https://www.ada.gov.in/images/GS%20Integration%20facilities.htm).
- Imported ECS LRUs (Dec 2022): "Pressure switch (bleed air inlet)", "Pressure switch-High", "Pressure switch-Low", "Temperature sensor (-55°C to 100°C)", "Temperature sensor (-55°C to 300°C)", "Hot Air Leak detection Control Box", "Hot Air Leak Sensing Element" — [ADA LRU list](https://www.ada.gov.in/images/LRU.pdf).
- ADA designed "10 types of compact plate-fin Heat Exchangers" and a "Gimbal Assembly with venturi" rated to 650 °C, 37 bar g and 10 mm movement in three axes. Gimbal joints with a venturi are typical of bleed ducting with a flow-limiting venturi [ASSUMPTION on function] — [ADA GS](https://www.ada.gov.in/images/gs.htm).
- Technology development: "Cabin Shut Off Valve (CBSOV) of ECS"; "Cabin Pressure Control System (CPCS) of ECS for TEJAS"; "Shut Off Valve" and "Non Return Valve (NRV) for ECS of LCA-AF Mk2 - Low Pressure (LP) Bleed"; "Temperature Sensors for ECS of LCA-Tejas" — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf); [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf); [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf). The LP-bleed items for Mk2 suggest Mk2 adds an LP bleed port, and that Mk1/Mk1A take bleed from one high-pressure port [ASSUMPTION; consistent with the HAL paper below].
- Mk2: "Location and envelope of Environmental Control and Fuel Monitoring (ECFM) unit was finalised" — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf) (OCR). The ECFM comprises ECFM-C, ECS-CP and GRP — [L&T](https://larsentoubro.com/lt-pes/our-offerings/electronics-products-and-systems/avionics-and-life-support-systems) (search-index excerpt).
- ADA scientists published "Real Time Control Systems of a Fighter Aircraft" (Garg, Uma, Usha, Saraf, ADA) covering three LCA real-time control systems: FCS, anti-skid brake control and environment control. The abstract notes that one system's performance "degrades considerably when the other system fails" — [ACCS journal](https://journal.accsindia.org/show.article.php?id=14) (abstract via search; full text unreachable).
- CAG lists "Water seepage ... in critical areas of aircraft including cockpit, radar, DFCC, avionics bay" and "low reliability" of the "Cockpit Pressure Transducer (CPTCV)". CAG's footnote oddly describes the CPTCV as giving control-surface position feedback — an internal inconsistency in the source — [CAG 17/2015, p. 42](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
- Hot-weather trials: at Jaisalmer, PV-6 and SP-6 were hot-soaked at 39–42 °C, then flew "low level high speed runs to assess the temperature (rise) of specific LRUs as well as general system performance after hot soak" — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) (OCR).
- Dubai Air Show, Nov 2025: the PIB Fact Check unit said the fluid seen under the Tejas Mk1 was "routine, intentional draining of condensed water from the aircraft's Environmental Control System (ECS) and On-Board Oxygen Generating System (OBOGS)", a standard procedure in humid conditions — [newsonair/PIB Fact Check, 20 Nov 2025](https://www.newsonair.gov.in/pib-fact-check-no-oil-leak-in-tejas-mk1-at-dubai-air-show).
- Life support:
  - OBOGS integration on PV-3: zero-zero ejection checks "with no OBOGS interference" and ground tests with a breathing simulator (2017-19) — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf); [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf).
  - OBOGS is based on "Pressure Swing Absorption (PSA) technology used for on-Board oxygen generation on Tejas" — [MoD Annual Report 2021-22, p. 206](https://mod.gov.in/sites/default/files/AR_0.pdf).
  - DEBEL ILSS high-altitude trials on PV-3 (4 Mar 2025) up to 50,000 ft with high-g manoeuvres checked oxygen concentration, demand breathing, 100 % oxygen availability, anti-g valve function and the breathing system across taxi, take-off, cruise, g-turns and landing. ILSS LRUs include a low-pressure breathing regulator, emergency oxygen system, oxygen sensor and anti-g valve — [The Defense Post, 13 Mar 2025](https://thedefensepost.com/2025/03/13/indias-drdo-life-support-sysem/amp/); [StratNews Global](https://stratnewsglobal.com/defence-and-security/drdo-conducts-high-altitude-trials-of-ilss-for-lca-tejas/). Sources disagree on the number of ILSS LRUs (10 vs 11).
- HAL "Digital Lox Indicator / Transmitter" (Mk1 LOX): indicates LOX quantity "for ground crew and transmit variable frequency output to ECFM-C for display on MFD"; 28 V DC, ≤200 mA; 0–5 L on two displays; accuracy ±0.4 L; output ≈6,000→5,300 Hz — [DDP node 10089](https://www.ddpmod.gov.in/node/10089) [DIRECT-by-nomenclature: ECFM-C is Tejas-specific]. Conflict: Mk1 is described as LOX-equipped (Wikipedia citing MoD), yet PIB described OBOGS condensate draining on a Mk1 at Dubai. Either some Mk1s carry OBOGS or the PIB wording is generic. Flag for validation.

**HAL ECS components [DIRECT part; Tejas fitment = ASSUMPTION]**
- "Primary Heat Exchanger": cools engine charge (bleed) air with ram air; "cross-counter flow Plate Fin Heat Exchanger with a single pass for the cold stream (Ram air) and a two passes for the hot stream". Hot side: air 34.5 kg/min (0.575 kg/s), operating pressure 6,564 mbar, maximum inlet 578 °C, outlet <170 °C; 344 × 230 × 454 mm; 23 kg — [DDP node 10095](https://www.ddpmod.gov.in/node/10095). Fitment reasoning: a 578 °C inlet matches F404 HPC-discharge temperatures (≈520 °C at SLS, higher at high Mach and hot day, per the engine sibling). ADA's plate-fin HX family and the HAL paper's 6.4 bar upper bleed pressure are consistent. Validate with HAL Lucknow.
- "Turbofan Cold Air Unit": bleed "from the last stage of engine compressor"; centrifugal fan driven by a radial-inflow turbine; turbine inlet 8 ± 0.1 kg/cm² abs at 100 (+5) °C; turbine temperature drop 100 °C; flow 525 ± 25 kg/h; 72,000 rpm; 4.5 kg with oil — [DDP node 10091](https://www.ddpmod.gov.in/node/10091) (platform unstated; a simple-cycle machine, so probably not the Tejas bootstrap ACM).

**Transfer: Indian fighter ECS model, standards, donors**
- HAL ARDC + NIT Trichy, "advanced fighter" ECS (aircraft unnamed) [TRANSFER: Indian fighter ECS practice; the aircraft could be Tejas or another HAL type]:
  - Bootstrap cycle. Bleed "drawn from the engine compressor from its last stage". Path: pre-cooler, PHE, ACM compressor, SHE, reheater, condenser, high-pressure water separator, ACM turbine.
  - Temperature-control valves (TCVs) bypass hot air to the ACM outlet (anti-ice and temperature control) and to the cabin-supply mix.
  - Cabin mean temperature T_mean = 0.25·T_inlet + 0.75·T_outlet.
  - Combat-aircraft bleed generally "exceed 2068 kPa (300 psi) & 873 K".
  - In-air cases: engine rpm 75–97 % → bleed 2.8–6.4 bar and 175–440 °C.
  - Sampling of "four samples per sec" for temperature and pressure.
  - TCV is an electrically actuated butterfly, A_eff = A₀(1 − cos θ), with compressible-orifice mass flow. Valve drive times 6–10 s full stroke.
  - Variable time-delay control scheduled on bleed pressure and its rate of change cuts TCV actuations from ≈311 (PID) to ≈71–82 per run.
  - Source: [Arunachalam & Varadappan, Heliyon 8(11) e11727, 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9708630/).
- Gripen ECS [TRANSFER: Saab Gripen; architecture and modelling practice]:
  - Input air bled "from the engine or the Auxiliary Power Unit", conditioned "through a series of heat exchangers, a compressor-turbine set-up, a condenser, a series of valves, and controlling software".
  - Subscribers: "fuel system, on board oxygen generating system, anti-g system, avionics".
  - Controlling software "sampled at 30Hz".
  - The high-fidelity Modelica model has >100 inputs/outputs, ≈9,000 variables and 14 nonlinear systems of equations. It exists at three fidelity levels (desktop high fidelity; fixed-step export with increased time constants; low-fidelity real-time for HIL).
  - Operating-domain inputs: altitude, Mach, PLA plus ambient pressure, temperature and humidity. Bleed temperature is computed from measured bleed pressure using adiabatic compression with known compressor efficiency.
  - "the switch of bleed supply air from auxiliary power unit to engine" causes pressure oscillations through the ECS.
  - Source: [Hällqvist, Eek, Lind & Gavel, SIMS 56 (2015)](https://ep.liu.se/ecp/119/020/ecp15119020.pdf); [Hällqvist et al., ICAS 2016-0188](https://www.icas.org/ICAS_ARCHIVE/ICAS2016/data/papers/2016_0188_paper.pdf).
- F404 customer bleed (HARV): ≈5 % of HPC inlet flow at ≥30 kft, up to ≈7.2 % below 30 kft at PLA 50–70°, ≈2.6–3.5 % in AB; minimum leak bleed ≈0.7 lb/s; maximum specification bleed ≈3.0–4.2 lb/s; customer bleed from HPC stage 7 — compiled in `f404_in20_engine_model.md` from [NASA TM-104247](https://ntrs.nasa.gov/citations/19920020182) [TRANSFER: F404-400; IN20 bleed schedule unknown]. Consistency check: the probable-Tejas PHX rating of 0.575 kg/s (1.27 lb/s) sits inside the 0.7–4.2 lb/s range.
- MIL-E-18927E (Navy ECS general spec; publicly downloadable; no distribution statement found in the extracted text) [TRANSFER: US standard; Tejas compliance not stated]:
  - Aircraft with a ceiling above 20,000 ft shall be pressurised. Fighter cabins follow the spec's Figure 2 schedule (figure not machine-readable).
  - Pressure-change rate in normal operation ≤0.2 psi/s (decreasing and increasing); emergency release/repressurisation ≤1.0 psi/s decreasing and ≤0.5 psi/s increasing.
  - Engine-power transients must not move cabin ΔP more than 0.1 psi beyond tolerance.
  - Occupants on pressure-demand oxygen never above 50,000 ft cabin altitude.
  - Fighter pilot-envelope temperature within curves of Fig. 4; WBGT ≤90 °F (32 °C) in flight and ≤95 °F (35 °C) on the ground.
  - Avionics kept within the steady-state thermal limit for any condition lasting >15 min.
  - Source: [MIL-E-18927E, §§3.4.1–3.4.4](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-E/MIL-E-18927E_11721/).
- Fighter pressure schedule: the F-22 design followed "previous fighter aircraft systems which maintain 5.0 psi differential pressure above 23,000 ft" — [Webb & Pilmanis, SAFE 1997, DTIC ADA426909](https://apps.dtic.mil/sti/pdfs/ADA426909.pdf) (search-index excerpt; DTIC and its mirrors unavailable) [TRANSFER]. Derived check: ISA pressure at 8,000 ft (10.92 psia) minus at 23,000 ft (5.97 psia) ≈ 4.95 psi. So "unpressurised to 8,000 ft, isobaric 8,000 ft cabin up to ≈23,000 ft, then constant 5 psi ΔP" is internally consistent.
- B737-200 ECS faults: "Fault detection is particularly difficult, due to the lack of instrumentation and the ability of the ECS's control system to mask symptoms". A 1D thermodynamic model simulated degraded heat exchangers, valves and the water separator — [Esperon-Miguez, Jennions et al., IJPHM 2019](https://papers.phmsociety.org/index.php/ijphm/article/view/2731) [TRANSFER: civil pack; masking principle transfers].
- F/A-18 HARV ECS-related discretes: "LT/RT BLEED OFF", "L/R ATSCV OPEN", "OXYGEN LEV LOW", "OXYGEN GAGING SYS IN TEST", "ESSENTIAL AVIONICS HOT", "INLET ICE", "ICE DETECTOR FAIL", "L/R ENG ANTI ICE VLV", "SWIVEL PROBE TOTAL TEMP" — [NASA CR-201670 App. A](https://ntrs.nasa.gov/citations/19970014822) [TRANSFER].

### Inferences
- [ASSUMPTION] Bleed pressure P_b and temperature T_b are engine-state outputs. Take them from the engine model (stage-7/HPC-exit pressure and temperature) or, until coupled, from a lookup on N2 and inlet conditions anchored to the HAL range (75→97 % rpm: 2.8→6.4 bar, 175→440 °C) and the 578 °C PHX maximum. The ECS flow-control valve holds mass flow near 0.5–0.6 kg/s. Cockpit and avionics supply temperatures follow TCV control at 4–30 Hz with valve stroke times of 6–10 s. Expect slow limit-cycling of supply temperature (the HAL paper's TD/PID oscillation results) rather than white noise.
- [ASSUMPTION] Ambient coupling: ram-air cooling capacity ∝ ρ·V·(T_ram − T_hx). On Indian hot days at low speed (taxi, hold, Jaisalmer 39–42 °C) the PHX/SHE outlet temperature rises and avionics cooling margin shrinks. The DFCC can tolerate 1 h without cooling air. High humidity (coastal bases, monsoon) produces condensate (drained post-flight per PIB) and water-separator loading.
- [ASSUMPTION] Cockpit pressure: unpressurised below ≈8,000 ft, isobaric ≈8,000 ft cabin to ≈23,000 ft, then 5.0 psi ΔP, with ≤0.2 psi/s rates (transfer). A cockpit pressure transducer (CPTCV-class) and the CPCS make this observable. Leaks (canopy seal) show as a cabin-altitude excess at high altitude. Validate the schedule with ADA.

### Gaps
- Tejas bleed port, bleed pressure/temperature schedule, ECS flow, ACM wheel count, heat-exchanger set, avionics air vs liquid loop (the Mk1A AESA is reported liquid-cooled in secondary sources only), CPCS schedule, anti-icing and demisting provisions, and the ECS caution list. None public. MIL-E-18927E Figure 2 (fighter schedule) was not machine-readable in the everyspec scan.

---

## KQ6. Landing gear, brakes, tyres, nosewheel steering and brake parachute

### Takeaway
The Tejas has a hydraulic tricycle gear: single inward-retracting main wheels and a steerable twin-wheel forward-retracting nose gear. It has carbon-carbon brakes (3 rotors, 4 stators) on 26 × 8.0-14 main tyres (Mk1; 16.9 bar on the probable HAL wheel) and twin 360 × 135-6 nose tyres (7 bar). The microprocessor brake management system has an anti-skid manifold and brake-feel potentiometers (brake-by-wire). Electro-hydraulic nosewheel steering has input and feedback potentiometers and a free-castor solenoid. A 17 m² brake parachute deploys at ≤285 km/h (≤340 km/h emergency), with a life of 45 streamings or 8 years.

Measured or degradation anchors:
- rejected take-offs at 50 %, 70 % and 90 % brake wear;
- the 7 Feb 2026 brake-system software event (brake failure → tyre burst → runway excursion → ≈2-month fleet grounding);
- F-16 main tyres of almost the same size last only 4–12 landings.

### Cited Findings
**Tejas facts [DIRECT]**
- "hydraulic retractable tricycle-type landing gear developed by HAL" (search-index excerpt); "two single, inward-retracting main wheels and a steerable twin-wheel forward-retractable nose gear" — [naval-technology.com Tejas profile](https://www.naval-technology.com/projects/hal-tejas/) [secondary].
- Brakes: "Carbon-Carbon composites" that provide drag, absorb kinetic energy as heat and hold the aircraft against engine thrust — [ADA GS](https://www.ada.gov.in/images/gs.htm). ADA's "Microprocessor Controller Brake Management System" (same page) and "microprocessor based utility and brake management systems" — [GlobalSecurity LCA design page](https://www.globalsecurity.org/military/world/india/lca-design.htm) [secondary]. Carbon brake disc work: "Development of carbon brake disc using Needle Punched Perform technology" — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf). ADA has a brake dynamometer — [ADA GS facilities](https://www.ada.gov.in/images/GS%20Integration%20facilities.htm).
- Imported landing-gear LRUs: "Brake Feel Module Input Potentiometer", "Nose Wheel Steering Free Castor Solenoid Valve", "Nose Wheel Steering Input Potentiometer", "Nose Wheel Steering Position Sensor (Feedback Potentiometer)", "Antiskid Brake Manifold"; hydraulic "Control Cable-Park Brake Control" — [ADA LRU list](https://www.ada.gov.in/images/LRU.pdf).
- Brake-wear test points:
  - "Reject take off High Speed Taxi Run in high mass configuration (2 X 1200 ltr DTs + 2 X 1000 lbs bombs + LDP) was conducted with 50% naturally worn out brake pads. Trials are slated to continue up to 90%" — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) (OCR).
  - RTO in heavy configuration "with naturally worn out brakes; in stages, with brake wear out condition at 70% and 90%" — [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf) (OCR).
  - A 13.5 t AUW take-off was demonstrated — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf).
- CAG: LSP deficiencies included "brake management system, brake parachute, undercarriage system" — [CAG 17/2015, p. 42](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf). FOC challenge: brake and brake-parachute refinement — [JOAST 67(2A)](https://joast.org/index.php/joast/article/view/325).
- Mk2 programme: "The specifications of brakes were released"; "Indigenous tyre development initiated" — [ADA AR 2019-20, 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf) (OCR). ADA studied "Non-linear Dynamics (LCO) of Shimmy Phenomenon in Nose Landing Gear" and "Emergency Landing of Tejas with only nose wheel down" — [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf). Navy MLG was certified for 6.8 m/s sink rate; NP1 landed at 3.1 m/s — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf).
- Tyres: the Mk1 main tyre is 26 × 8.0-14. Mk2 (MRF) uses a 27.5 × 7.5-16 main and a 360 × 135-6 nose tyre, two nose tyres per assembly — [idrw.org, 10 Mar 2025, citing an ADA tender](https://idrw.org/made-in-india-focus-ada-seeks-local-suppliers-for-lca-af-mk2-tyres/) [secondary]. The Mk1 used Dunlop tyres (2019) — [Indian Defence News, Feb 2019](https://www.indiandefensenews.in/2019/02/mrf-could-make-tyres-for-tejas-other.html) (search excerpt) [secondary].
- HAL "Main Wheel" [DIRECT part; Tejas fitment = ASSUMPTION, strongly supported because the tyre size equals the Mk1 main tyre]:
  - bowl-type light-alloy wheel with loose flange and lock ring, designed "to operate with Carbon Brake".
  - Tyre 26" × 8.00"-14", 18 PR; tyre pressure 16.9 bar (245 psi); maximum static load 6,090 kg per wheel; nominal loaded radius 284 mm; maximum dynamic landing load 10,200 kg; 18 kg.
  - Source: [DDP node 9654](https://www.ddpmod.gov.in/node/9654).
- HAL "Nose Wheel" [same basis: twin nose wheels, 360 × 135-6]: "twin nose wheel arrangement", tubeless 360 mm × 135 mm-6", 8 PR; 7 bar; 975 kg static per wheel; loaded radius 156.5 mm; maximum dynamic 4,080 kg; 4 kg — [DDP node 9655](https://www.ddpmod.gov.in/node/9655).
- HAL "Brake Unit: Carbon" [same basis]: "Carbon-Carbon Composite heat sink with three rotor discs interposed between four stator discs. The rotors are keyed to the wheel through 7 drive tenons and the stators are keyed to brake chassis with help of 10 tenon slots on torque tube" — [DDP node 9657](https://www.ddpmod.gov.in/node/9657). The page's specification block repeats the nose-wheel data, an error on the page.
- HAL "Anti Skid Control Unit" [DIRECT part; platform unstated]: "limits deceleration of aircraft wheel to 7 meter/second²"; 28 V DC; 2 independent channels; input from a wheel-speed transducer; output skid valve ON/OFF — [DDP node 10092](https://www.ddpmod.gov.in/node/10092).
- HAL "Brake Master Cylinder" (foot-operated, 68 ± 10 bar) and "Nose Door Jack" (3,000 psi) — [DDP 10094](https://www.ddpmod.gov.in/node/10094), [DDP 10093](https://www.ddpmod.gov.in/node/10093) [not Tejas: Tejas uses brake-feel potentiometers and 280 bar].
- Brake parachute (hybrid) for LCA (Tejas), GIL/ADRDE:
  - main canopy uni-cross, 17 m², span 5.750 m; spring-loaded pilot chute 0.05 m²; auxiliary chute 0.90 m²;
  - deployment speed 285 km/h normal / 340 km/h emergency; system mass ≈10 kg;
  - life "08 years or 45 streaming whichever is earlier"; orders from the IAF and HAL.
  - Source: [DDP node 8027](https://www.ddpmod.gov.in/node/8027).
  - Inducted by the IAF in Dec 2025 — [Wikipedia HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas) [secondary].
- 7 Feb 2026 event:
  - ThePrint's editor's note says the incident "took place while the aircraft was taking off, and not during landing", with a "suspected brake failure" "followed by a tyre burst" and runway overrun at a forward base — [ThePrint, 22 Feb 2026](https://theprint.in/defence/suspected-brake-failure-leads-to-tejas-accident-after-landing-airframe-likely-to-be-written-off/2860898/).
  - HAL's chairman cited "a software glitch in the brake system". The fleet (34 aircraft per the Tribune) was grounded until about 8 Apr 2026 — [The Tribune, 2 Apr 2026](https://www.tribuneindia.com/news/india/iafs-grounded-tejas-jets-to-resume-flying-next-week-after-software-fix-says-hal-chairman/).
  - Conflicts: idrw/AFI reported "after touchdown" and "around 30 single-seat" aircraft; Wikipedia gives 36 including 6 trainers and names Naliya — [idrw](https://idrw.org/a-troubled-touchdown-suspected-brake-failure-behind-latest-tejas-accident/); [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas). The software fix cleared a Local Modification Committee before validation flights — [idrw](https://idrw.org/hal-chief-confirms-tejas-grounding-issue-fixed-iaf-jets-likely-to-return-to-skies-within-a-week/) [secondary].

**Transfer donors**
- F-16 main tyres:
  - The F-16 Block 30 main tyre (25.5 × 8.0-14, tested at 14,000 lb vertical load and 310 psi) shows "Excessive tire wear due to large contact pressures, large slip velocity".
  - Approximate life: "F-16 Block 30...8-12 landings; F-16 Block 40 & 50...4-8 landings".
  - In dynamometer tests radial tyres wore more than bias, "however, in the field, radial tires have longer life".
  - Source: [Chawla, USAF Wright Laboratory, NASA NTRS 19960009454](https://ntrs.nasa.gov/citations/19960009454) [TRANSFER: almost the same tyre size and load as the Tejas main tyre (26 × 8.00-14; 6,090 kg static ≈ 13,400 lb; 245 psi); runway, braking and slip differ].
- Carbon brake wear and temperature [TRANSFER: civil transport; mechanisms transfer, magnitudes differ for fighters]:
  - A carbon brake "may achieve as many as 2500 landings between overhauls". Wear per flight cycle for a whole carbon brake is "in the region of 0.001" (0.025mm)".
  - Wear depends on "carbon temperature, braking power applied, engine idle thrust, runway conditions, taxi time and humidity". Low-temperature taxi braking gives abrasive wear; high-energy braking forms a protective friction film; very high temperature causes oxidation.
  - Proposed model inputs: brake energy (from mass and wheel landing/taxi speeds), brake temperature and heat-pack mass.
  - The temperature probe sits in a gap, causing a lag. Tyres must cool about 3 h before manual pressure checks. Tyre-pressure systems should compensate for gas temperature.
  - Source: [Mortimore (Airbus UK), CEAS 2007-340](https://www.fzt.haw-hamburg.de/pers/Scholz/ewade/2007/CEAS2007/papers2007/ceas-2007-340.pdf).
  - Carbon wear "is primarily dependent upon the total number of braking applications", while steel wear is proportional to energy absorbed — [US 7,963,620 "Carbon brake wear for aircraft"](https://patents.google.com/patent/US7963620); [US 10,907,696](https://patents.google.com/patent/US10907696).
- Brake temperature thresholds (Boeing): brake-temperature indication thresholds "on/off" of 371/315, 427/362, 538/338, 430/330 and 550/450 °C across models and brake types. Temperatures ratchet up over successive short-turnaround flights — [Boeing AERO, "Brake temperature"](https://www.leonardo-in-flight.nl/PDF/Boeing%20AERO%20Brakes.pdf) [TRANSFER: civil thresholds; texture only].
- Tyre pressure (FAA AC 20-97B):
  - A tyre "should maintain the inflation pressure within 5 percent of the initial pressure for a period of 24 hours".
  - "± 5º F change ... will alter gauge pressure by 1 percent".
  - "Cold" = at ambient or at rest ≥2 h; service pressure 100–105 % of specified.
  - 90–100 % → reinflate; <90 % → remove; <80 % → remove tyre and axle-mate.
  - Gauges ±2 %.
  - Source: [FAA AC 20-97B (2005), ¶5](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-97B.pdf) [TRANSFER: civil guidance; physics general].
- Emergency braking: F-15 emergency brakes lack anti-skid, raising blown-tyre risk above 70 kt — [AIB F-15D 84-0046](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/15%20MAY%2023%20AIB%20Kingsley%20ANGB%20F-15D%20Final%20Amended%20Report_Redacted.pdf) [TRANSFER].
- WoW and gear discretes on F/A-18 HARV (40 samples/s): "WEIGHT ON WHEELS", "NG/LMG/RMG WOW SW FAIL", "GEAR DOWN", "NOSEGEAR DOWN", "GEAR NOT UP", "LNDG GEAR HANDLE DOWN", "LAND GEAR CNTL UNIT FAIL", "ANTI SKID L/H / R/H XDCR FL", "ANTI SKID CONT FL", "ANTI SKID VLV CHK FL", "ANTI SKID SW OFF", "PARKING BRAKE SET", "NWS FAIL CAUT", "NOSE WHEEL STEERING BIT", "CH2/CH4 NWS SOV OPEN", plus spin-chute deploy/jettison/unsafe cautions — [NASA CR-201670 App. A](https://ntrs.nasa.gov/citations/19970014822) [TRANSFER]. F-35A: frozen-water strut extension loss made all WoW sensors read "on ground" in flight — [AIB F-35A 19-5535](https://www.afjag.af.mil/LinkClick.aspx?fileticket=Zigjw6p7hiw%3d&portalid=77) (in `faults_and_degradation.md`).

### Inferences
- [ASSUMPTION] Brake energy per stop E = ½·m·V² minus aerodynamic drag, chute and thrust contributions. Examples (derived): a 9.5 t landing at 75 m/s (270 km/h) has ≈26.7 MJ total kinetic energy; a 13.5 t RTO at 80 m/s (288 km/h) has ≈43 MJ, shared by two brakes plus drag. Heat-sink temperature rise ΔT ≈ E_brake/(m_hs·c_carbon), followed by Newtonian cooling with a time constant of tens of minutes (ventilation- and wind-dependent). The heat-sink mass is unknown, so calibrate m_hs so an RTO at 90 % wear stays below a fuse-plug-like limit.
- [ASSUMPTION] Brake wear per landing = a·N_applications + b·E_absorbed·f(T). The count term dominates for carbon and taxi snubs on cold carbon are costly. Wear-pin length or "% worn" is a ground-inspected state (ADA uses % worn). Use ADA's 50/70/90 % RTO points as states that must stay operable.
- [ASSUMPTION] Tyre wear per landing: draw tyre life from a distribution centred on about 5–15 landings (F-16 analogue), increased by heavy weights, hot runways, crosswind and anti-skid cycling, decreased with radial construction. Tyre pressure = gas-law temperature compensation plus 0–5 %/24 h leak, plus step loss on cuts.
- [ASSUMPTION] Anti-skid: wheel-speed sensors per main wheel; the BMS modulates or cycles a skid valve. The HAL ASCU's 7 m/s² wheel-deceleration limit and on/off valve may be a legacy design, while Tejas's "microprocessor" BMS probably modulates. Model slip-ratio control at ≥100 Hz only if the airframe sibling's ground-roll model needs it. Otherwise emit brake pressure and anti-skid activity discretes at 20–80 Hz.

### Gaps
- Gear retraction/extension times, emergency extension mechanism (cable-released free-fall is implied by "U/C emergency control cable" and selector, but not confirmed), WoW sensor type and logic, brake pressure range, brake temperature sensing (if any), wear-pin practice, BMS architecture and software functions, tyre life and pressure limits for Tejas, and NWS authority and speed scheduling. None public.

---

## KQ7. Utility Systems Management (USMS, ECFM, brake management), BIT and cautions; fire, ice and other utility sensors

### Takeaway
Tejas utility systems are run by microprocessor electronic units, not by a single central computer. Prototypes had four EUs for engine, electrical, hydraulic, fuel and ECS functions, meant to be merged into two in production. ADA now names a "Computer Controlled Utility System & Management System (USMS) with dual redundant Processor" integrated with the avionics (OAC) and FCS. A separate ECFM controller (L&T) handles the ECS and fuel monitoring, with a cockpit control panel and a ground refuelling panel, and receives LOX quantity for MFD display. The brake management system is a separate microprocessor unit; its software caused the 2026 grounding. The MFDs show engine, hydraulics, electrical, FCS and ECS pages "on a need-to-know basis".

No public paper gives USMS I/O lists, bus rates or BIT coverage. The MIL-H-5440H diagnostic-monitor requirements, F/A-18 caution sets, ADE's 1553 health-word example (12.5 Hz) and USAF fire-detection reliability statistics are the best transfer anchors. Fire protection on Tejas is documented only as a cartridge-fired extinguisher bottle triggered by push-button or crash switch. Ice detection on Tejas is not documented; probe-heater currents are monitored simplex by the DFCC.

### Cited Findings
**Tejas facts [DIRECT]**
- "Computer Controlled Utility System & Management System (USMS) with dual redundant Processor". ADA integrated avionics "with vital onboard systems such as Flight Control System, Utility Systems Management System, Environmental Control System, Weapons" — [ADA Avionics & Weapon Systems page](https://www.ada.gov.in/images/sys.htm).
- Mechanical systems comprise ">150 LRUs", "mostly software driven and microprocessor based"; "dual redundant processor based utility services management systems" — [CEMILAC, JOAST 67(2A) 2015](https://joast.org/index.php/joast/article/view/325).
- NFTC lessons-learned paper: "four microprocessor based Electronic Units (EUs) monitor and control the onboard General Systems such as Engine, Electrical, Hydraulic, Fuel and Environmental Control Systems (ECS)"; "in the production version, these functionalities would be combined thereby reducing the number of Electronic units to two" — [Raveendran & Prabhu (NFTC/ADA), "Tejas Flight Test: Lessons Learned So Far", NATO RTO-MP-SCI-162 paper 14, 2005](https://www.sto.nato.int/publications/STO%20Meeting%20Proceedings/RTO-MP-SCI-162/MP-SCI-162-14.pdf) (search-index excerpt; PDF blocked by Cloudflare).
- ECFM: ECFM-C controller, ECS-CP control panel, GRP ground refuelling panel; controls cockpit and avionics-bay environment — [L&T](https://larsentoubro.com/lt-pes/our-offerings/electronics-products-and-systems/avionics-and-life-support-systems) (search-index excerpt). "ECFM software ... for Enhanced Fuel gauging, F2 Pump Auto Operation, Fuel dumping and Hot refueling" — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf). LOX transmitter → "ECFM-C for display on MFD" — [DDP node 10089](https://www.ddpmod.gov.in/node/10089).
- "The multifunction displays provide information on engine, hydraulics, electrical, flight control and environmental control system on a need-to-know basis" — [GlobalSecurity LCA design](https://www.globalsecurity.org/military/world/india/lca-design.htm) [secondary, consistent with ADA glass-cockpit pages].
- DFCC BIT: continuous, pilot-initiated and maintenance BIT. Non-inertial sensors "such as probe heater currents" are simplex. Sensors run BIT from the DFCC before each flight — [Kala, JOAST 67(2A)](https://joast.org/index.php/joast/article/view/317).
- Engine ECMS: "Provides real time Engine Status in the Cockpit and Logs the Engine Usage Data to Compute Life Usage Indices of Life limited Parts. It also tracks Vibration Monitoring System" — [ADA Propulsion page](https://www.ada.gov.in/images/ps.htm) (engine sibling scope).
- Mk1A HUMS: Park Controls & Communications received a production order for 124 PCAMi-1000 HUMS data-acquisition units for the Tejas Mk1A, an indigenous replacement for a US-imported DAU, about 10 months after CEMILAC clearance — [Aviation & Defence Universe](https://www.aviation-defence-universe.com/pcc-advances-indigenous-hums-capability-with-pcami-1000-production-order) (search excerpt). ADA initiated indigenous HUMS in 2018-19 — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf).
- Mk2: "Aircraft Maintenance Terminal (AMT)" model finalised; "Undercarriage Display Unit"; 65 Electrical Interface Diagrams — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf) (OCR).
- Fire: "Fire Extinguisher Bottle is used to store and discharge fire extinguishant on initiation of catridge by Push-button selection or automatically by a crash warning switch located in the airframe" — [ADA GS](https://www.ada.gov.in/images/gs.htm). ECS hot-air leak detection (control box and sensing element) — [ADA LRU list](https://www.ada.gov.in/images/LRU.pdf). LSP-7 added "all weather clearance LRUs" — [CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
- ADE 1553 practice (developmental glass-cockpit programme, probably LCA): an LRU → bus-controller "Gives health status" message at 12.5 Hz with link, port and memory status and device temperature words; 4 minor frames per major frame — [Trivedi (ADE), JOAST 63(4) 2011](https://joast.org/index.php/joast/article/view/598) [ASSUMPTION that it is LCA].

**Transfer anchors**
- MIL-H-5440H §3.6.15: an automatic diagnostic monitor "integral with each hydraulic system" must detect out-of-tolerance conditions in flight, indicate "maintenance actions needed such as filter replacement, accumulator recharging and over temperature", store the data and display it on the ground. It must cover pumps, accumulators, filters, reservoir levels, reservoir temperature and free air — [MIL-H-5440H](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-H/MIL-H-5440H_14866/) [TRANSFER].
- Gripen fuel system: the control unit model has 270 inputs and 80 outputs. Monitoring-software V&V with physical models was emphasised because NFF is about 50 % of removals — [Lantto et al., ICAS 2006](https://icas.org/ICAS_ARCHIVE/ICAS2006/PAPERS/039.PDF) [TRANSFER: utility-controller I/O scale].
- USAF fire detection, 1965–70: "approximately 50 percent of the fires were not detected by the fire or overheat detection system" and "83 percent of the fire and overheat warnings were false" — [DTIC AD0663213](https://apps.dtic.mil/sti/tr/pdf/AD0663213.pdf) (search-index excerpt; DTIC unavailable) [TRANSFER: historic; modern loops are better, but it shows that a fire-warning channel needs both missed-detection and false-alarm processes].
- F/A-18 HARV utility caution set (40 samples/s discretes), including "MASTER CAUTION", "FIRE EXTINGUISHER LOW", "ICE DETECTOR FAIL", "INLET ICE", AMAD, generator, battery, hydraulic, fuel, anti-skid, WoW and NWS items — [NASA CR-201670 App. A](https://ntrs.nasa.gov/citations/19970014822) [TRANSFER].

### Inferences
- [ASSUMPTION] Production Tejas utility computing: (1) the dual-redundant USMS (hydraulic, electrical, engine-utility, landing-gear status, probably fire/warning logic) and (2) the ECFM-C (ECS control and fuel gauging/transfer/refuel). The BMS is a separate brake computer and the DFCC owns actuator BIT. All report to the OAC over MIL-STD-1553B for MFD pages and warnings. Validate with ADA. Model each as a monitor process that samples analog inputs (pressures, temperatures, quantities) at 10–80 Hz, applies thresholds with persistence/debounce timers and latching, and emits caution/warning discretes and maintenance fault codes with ground-readable storage (the Mk2 AMT concept).
- [ASSUMPTION] Imperfect BIT: give every caution a missed-detection probability and a false-alarm rate. Fire warnings especially need both processes (USAF historic 50 %/83 %); ECS faults are masked by control loops (B737 study). NFF removal rates of 30–60 % in prior notes apply to utility electronics such as the BMS, ECFM-C and USMS.

### Gaps
- USMS processor, I/O count, sampling rates, bus messages, BIT coverage and fault-code lists; the ECFM-C/USMS split; the fire-detection loops/zones on Tejas; ice detector presence; the caution/warning list. None public. The ACCS paper (ADA authors) and the NATO NFTC paper are the best leads but could not be opened.

---

## KQ8. Tejas utility LRU and vendor evidence (attribution table)

### Takeaway
The Department of Defence Production (DDP) product catalogue, ADA's LRU list, CEMILAC technical-approval listings and DRDO lab pages together give about 30 utility LRUs with numbers. Each needs an attribution confidence because several HAL pages omit the platform. The table grades them. "Named" means the source names LCA/Tejas. "Probable" means the nomenclature or physics match only Tejas among HAL types. "Other/unknown" means a HAL-built item used only as a transfer.

### Cited Findings
| LRU | Key numbers | Attribution | Source |
|---|---|---|---|
| AMAGB | 1 input / 4 outputs (2 hydraulic pumps, 1 generator, 1 starter); PTO 16,810 rpm; self-contained lube; >6,000 FH; life 750 h | Named [DIRECT] | [DDP 8779](https://www.ddpmod.gov.in/node/8779); [data.gov.in](https://www.data.gov.in/catalog/aircraft-mounted-accessory-gearbox-light-combat-aircraft-tejas); [DRDO](https://drdo.gov.in/amagb-lca) |
| PTO shaft (CVRDE) | 410 N·m peak start, 118 N·m normal at 16,810 rpm; lubrication-free; flown 14 Mar 2023 on LSP-3 | Named [DIRECT] | [ADU](https://aviation-defence-universe.com/maiden-successful-flight-test-of-drdos-indigenous-power-take-off-shaft-conducted-on-lca-tejas-in-bengaluru); [DRDO](https://www.drdo.gov.in/power-take-shaft-lca-tejas-0) |
| JFS GTSU-110 | 110 kW, 52 kg, 0.29 m × 0.64 m; free power turbine; digital fuel control | Named [DIRECT] | [DDP 8778](https://www.ddpmod.gov.in/node/8778) |
| 5 kW brushless DC generator (DRDO) | backup to main AC generator; PMG + exciter + main; FPGA/DSP GCU with BITE; 1,250 h endurance | Named [DIRECT] | [DRDO](https://drdo.gov.in/5-kw-brushless-dc-generating-system-lca-tejas-0) |
| Brake parachute (GIL/ADRDE) | 17 m²; 285/340 km/h; 10 kg; 8 yr / 45 streamings | Named [DIRECT] | [DDP 8027](https://www.ddpmod.gov.in/node/8027) |
| ECS sensors (imported) | temperature sensors −55–100 °C and −55–300 °C; bleed, high and low pressure switches; hot-air leak detection | Named [DIRECT] | [ADA LRU.pdf](https://www.ada.gov.in/images/LRU.pdf) |
| Landing-gear/brake LRUs (imported) | brake-feel pots; NWS input and feedback pots; NWS free-castor solenoid; anti-skid manifold; park-brake and emergency U/C cables; emergency U/C selector valve; flow synchroniser; progressive pressure control valve | Named [DIRECT] | [ADA LRU.pdf](https://www.ada.gov.in/images/LRU.pdf) |
| Fuel probes (HAL Lucknow) | F2-A/B (P/N 187800000); fuselage top-mounted (232000000); wing-fore immersed W-F/1 (239200000); 18-series P/N 188100000 | Named (ADA) / nomenclature (CEMILAC TA) | [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf); [DRDO 10962](https://drdo.gov.in/drdo/node/10962) |
| Fuel probe F2-F/T | capacitance → frequency in flange head; ±3 µs empty / ±5 µs wet; 230 mm; ≤350 g | Probable (F2) | [DDP 10090](https://www.ddpmod.gov.in/node/10090) |
| LOX indicator/transmitter | 0–5 L ±0.4 L; frequency output to ECFM-C | Probable (ECFM-C) | [DDP 10089](https://www.ddpmod.gov.in/node/10089) |
| Bootstrap reservoir (LH/RH) | 280/5.5 bar; 9.5 L; −54/+135 °C; MIL-H-5606; level sensor | Probable (280 bar + 5606) | [DDP 9659](https://www.ddpmod.gov.in/node/9659) |
| Airbrake actuator | 281 kgf/cm²; 2.5–5 t; 294 mm; dual-core LVDT; open loop | Probable | [DDP 9660](https://www.ddpmod.gov.in/node/9660) |
| Electro-selector valve | 280 bar; 40 L/min; 12.5 bar at 40 L/min; double solenoid | Probable | [DDP 9661](https://www.ddpmod.gov.in/node/9661) |
| Main wheel + carbon brake | 26 × 8.00-14 18 PR; 16.9 bar; 6,090 kg static; 10,200 kg dynamic; brake 3 rotors / 4 stators | Probable (Mk1 tyre size) | [DDP 9654](https://www.ddpmod.gov.in/node/9654); [DDP 9657](https://www.ddpmod.gov.in/node/9657) |
| Nose wheel (twin) | 360 × 135-6 8 PR; 7 bar; 975 kg static; 4,080 kg dynamic | Probable (twin nose, size) | [DDP 9655](https://www.ddpmod.gov.in/node/9655) |
| Primary heat exchanger | 34.5 kg/min; 6.56 bar; ≤578 °C in; <170 °C out; plate-fin cross-counterflow | Probable (F404 bleed temperatures) | [DDP 10095](https://www.ddpmod.gov.in/node/10095) |
| TRU | 115/200 V 400 Hz → 28 V 250 A, 7.5 kW; overloads 150 %/2 min, 200 %/1 min, 400 %/1 s | Probable (paired with the 5 kW DC gen master box) | [DDP 9646](https://www.ddpmod.gov.in/node/9646) |
| Master box / battery display | 2 TRUs + 5 kW DC gen + 45 Ah battery; buses Main/Essential/Emergency/Alert-1/2; 45 Ah full, 30 Ah low warning | Probable | [DDP 9647](https://www.ddpmod.gov.in/node/9647); [DDP 10096](https://www.ddpmod.gov.in/node/10096) |
| Accumulator (brake) | 68 bar; 50 bar N₂; 0.41 L; 10 brake applications | Unknown | [DDP 9656](https://www.ddpmod.gov.in/node/9656) |
| Anti-skid control unit | 2 channels; wheel-speed input; on/off skid valve; 7 m/s² wheel decel limit | Unknown | [DDP 10092](https://www.ddpmod.gov.in/node/10092) |
| Turbofan cold air unit | 8 kg/cm² abs, 100 °C in; ΔT 100 °C; 525 kg/h; 72,000 rpm | Unknown (simple cycle) | [DDP 10091](https://www.ddpmod.gov.in/node/10091) |
| VD hydraulic pump 12 L/min; brake master cylinder; nose-door jack; DC master box; static inverter; FCG-04 gauging (100 lb units); FQMS electronic box (0.5–20 mA) | various | Other HAL types → [TRANSFER] | [DDP 9658](https://www.ddpmod.gov.in/node/9658), [10094](https://www.ddpmod.gov.in/node/10094), [10093](https://www.ddpmod.gov.in/node/10093), [9649](https://www.ddpmod.gov.in/node/9649), [9648](https://www.ddpmod.gov.in/node/9648), [9645](https://www.ddpmod.gov.in/node/9645), [9662](https://www.ddpmod.gov.in/node/9662) |

- Tejas platform data (DDP): MTOW 13,500 kg; F404-IN20 85 kN (AB); +8/−3.5 g; M1.6; 50,000 ft; 9 hardpoints; Mk1A orders of 73+10 (2021) and 68+29 (Sept 2025) — [DDP node 6843](https://www.ddpmod.gov.in/node/6843).
- HAL Lucknow Accessories Division makes hydraulic pumps, accumulators, electro-selectors, bootstrap reservoirs, valves, ECS cold-air units, water extractors, NRVs, venturis, fuel-quantity instruments, AC/DC generators, master boxes, inverters, TRUs, undercarriages, wheels and brake LRUs. It claims ">400 types" of accessories designed for LCA Mk1A and Mk2 — [HAL Accessories Division Lucknow](https://hal-india.co.in/backend/production-unit/accessories-division-lucknow/).

### Inferences
- [ASSUMPTION] Use "Named" items as hard parameters, "Probable" items as defaults flagged for HAL confirmation, and "Other/unknown" items only for texture (e.g., pump type, anti-skid logic, accumulator sizing).

### Gaps
- The DDP pages lack drawings, part numbers and platform names for most items. CEMILAC TA PDFs (TA-1809, TA-1863) were unreachable.

---

## KQ9. Transfer donors: what transfers from Gripen, F/A-18, F-16 and the standards, and the limits

### Takeaway
The best transfer donors split by role:
- **Gripen** (Saab/Linköping): modelling architecture and fidelity ladders for fuel and ECS, plus ECS subscriber lists. Few numbers.
- **F/A-18 HARV parameter catalogue**: the realistic set of utility discretes and their 40 samples/s recording rate on an F404 fighter.
- **AFTI/F-16 and USAF AIB reports**: electrical and hydraulic architecture plus fault cases.
- **F-16 Wright-Lab tyre data**: fighter tyre life.
- **MIL-STD-704F, MIL-H-5440H, MIL-E-18927E, MIL-G-26988C**: normal-behaviour bands and monitoring requirements.
- **Civil PHM papers**: degradation physics and indicators.

Each transfer must keep its platform label and be replaced by Tejas values when found.

### Cited Findings
- Gripen vehicle systems = fuel, ECS, hydraulic, auxiliary power, escape, electrical power and landing gear. Modelling challenges are "different combinations of compressible fluids (air) and heavy incompressible fluids (fuel, oil) where acceleration vector matters, nonlinear effects such as turbulent flow cavitation and saturation and controlling software". Rig uncertainty sources include sensor "Drift, influence of temperature, wear" and "low dynamic response capability, noise, sampling rate, calibration" — [Steinkellner, Andersson, Gavel, Lind & Krus, ICAS 2010 paper 025](https://icas.org/ICAS_ARCHIVE/ICAS2010/PAPERS/025.PDF).
- Gripen fuel and ECS specifics: see KQ3 and KQ5 — [ICAS 2006-039](https://icas.org/ICAS_ARCHIVE/ICAS2006/PAPERS/039.PDF); [SIMS 2015](https://ep.liu.se/ecp/119/020/ecp15119020.pdf).
- HARV catalogue: discretes and fuel quantities recorded at 40 samples/s, FCS surfaces at 160 samples/s, selected analogs at 80 samples/s. "the number at the beginning of the parset name, such as 160.0 ... is the rate at which the parameter was recorded" — [NASA CR-201670, p. A-1 area (PDF p. ~38)](https://ntrs.nasa.gov/citations/19970014822).
- AFTI/F-16 40 kVA + 5 kVA + 500 VA PMG + 2 batteries — [NASA TP-2857](https://ntrs.nasa.gov/citations/19890014956).
- Standards: MIL-STD-704F ([everyspec](https://everyspec.com/MIL-STD/MIL-STD-0700-0799/MIL-STD-704F_CHG-1_55461/)); MIL-H-5440H, Distribution A ([everyspec](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-H/MIL-H-5440H_14866/)); MIL-E-18927E ([everyspec](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-E/MIL-E-18927E_11721/)); MIL-G-26988C ([everyspec](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-G/MIL-G-26988C_36788/)); MIL-F-17874B ([everyspec](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-F/MIL-F-17874B_20580/)). Local copies are in `research_sources/tejas_utility/donors/`.
- Tejas engineering practice follows "43 main military standards" — [CEMILAC, JOAST 67(2A)](https://joast.org/index.php/joast/article/view/325). The ADC was built to MIL-STD-704D/461C/810E — [Kala](https://joast.org/index.php/joast/article/view/317). This supports using US MIL-STD bands as defaults.

### Inferences
- [ASSUMPTION] Transfer rules for the generator:
  - Bands and limits from standards → normal-behaviour envelopes and caution thresholds.
  - Signal sets and rates from HARV → bus/recorder layer.
  - Architecture from AFTI/F-16 and Gripen → source/consumer topology where Tejas is silent.
  - Degradation magnitudes from civil PHM → shape only, rescaled to fighter usage.

### Gaps
- No Gripen hydraulic or electrical numbers were found. The F/A-18 and F-16 hydraulic pump flows are in limited-distribution manuals, which are excluded.

---

## KQ10. Degradation-relevant behaviour per utility system (what degrades, what reveals it, what BIT/caution exists)

### Takeaway
For each subsystem there is now at least a mechanism and an observable, though rarely a fighter-specific rate. Hydraulic pumps degrade volumetrically (leakage ↑, case drain ↑, compensator set-point drift ↓P). Filters clog with ΔP rising exponentially in captured contaminant. Accumulators lose precharge slowly, or quickly through valve-core leaks. Heat exchangers foul and lose effectiveness, which ECS control masks until saturation. Generators fail mostly at rotating rectifiers and bearings. Batteries fade. Carbon brakes wear per application. Tyres wear in 4–12 landings on F-16-class fighters and leak ≤5 %/day. JFS shows start failures in cold and at altitude, plus oil consumption. Gearboxes and bearings show oil-temperature and debris signatures. Tejas-specific degradation evidence: JFS (cold/altitude, oil consumption), brakes (RTO at 50–90 % wear; 2026 software event), fuel-system leaks and gauging artefacts, water seepage into avionics bays, and the low reliability of JFS and CPTCV.

### Cited Findings
- **Hydraulic pump**:
  - Volumetric degradation "is the main failure mode of a hydraulic pump". η_vol = Q_eff/Q_theo is trended over flight cycles by linear regression to a limit. Leakage-compensation in cruise is a usable operating point. Sensor accuracies in the prototype: Δp ±0.2 % FS, fluid temperature 0.5 °C, flow 0.3 % of reading — [Bischof, Thielecke & Metzler (TUHH), PHME 2022](https://papers.phmsociety.org/index.php/phme/article/download/3341/1908) [TRANSFER: civil motor-pump; mechanism transfers to EDPs].
  - Compensator-spring loosening lowers discharge pressure. The CI is the per-flight average no-load pressure, degrading roughly linearly with an unknown slope over hundreds of cycles to a threshold monitor — [Gomes et al., PHM 2012](https://papers.phmsociety.org/index.php/phmconf/article/view/2085) [TRANSFER].
  - Earlier work used "pump pressure, case drain flow and case drain temperature" (Byington et al. 2003, cited by Gomes et al.).
  - A case-drain filter on each pump is mandated by [MIL-H-5440H §3.11.9.2.4](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-H/MIL-H-5440H_14866/).
- **Leakage/temperature coupling**: leaks rise with fluid temperature; thermal-valve routing at 225 °F; water-contaminated fluid freezes in cold soak and causes false WoW — (`faults_and_degradation.md` §3, AIB reports) [TRANSFER].
- **Filters**: ΔP across the element "increases exponentially" with cumulative contaminant captured. A remaining-capacity/rate method gives remaining life — [US 6,855,249 (MEMS fluidic PHM)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6855249). Aircraft-engine filter monitoring uses ΔP normalised to reference conditions against a reference clogging curve — [US 8,352,200](https://patents.google.com/patent/US8352200). Cranfield models three clogging phases with particle-filter RUL for fuel filters — [Cranfield thesis](https://dspace.lib.cranfield.ac.uk/handle/1826/9988) [TRANSFER]. Tejas has 9 hydraulic filters of 6 types [DIRECT]; ΔP indicators are an [ASSUMPTION].
- **Accumulators**: patents track gas-charge leakage over time to project servicing and treat a normal-loss baseline versus faster leak as integrity loss — [US 12,286,985](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12286985); [US 11,919,626](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11919626) [TRANSFER]. The UCI rig used precharge levels 130/115/100/90 bar ("90 = close to total failure") — (`faults_and_degradation.md`). No fighter rate was found.
- **Heat exchangers (ECS)**: a fouling factor on 0–1, with <0.4 green, 0.4–0.8 yellow (advisory) and >0.8 red (warning); fleet RUL estimation — [US 10,242,508](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10242508); [US 10,534,359](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10534359). Control masks symptoms; limited instrumentation — [IJPHM 2019 B737 ECS](https://papers.phmsociety.org/index.php/ijphm/article/view/2731) [TRANSFER]. Tejas: water seepage into the cockpit, radar, DFCC and avionics bay (CAG p. 42); CPTCV low reliability [DIRECT].
- **Generators**: the rotating rectifier is "the most prone component to failure" (2024 review); diode faults appear in the output-voltage spectrum and the exciter field-current ripple — [NWPU 2021](https://pure.nwpu.edu.cn/en/publications/fault-diagnosis-of-rotating-rectifier-in-more-electric-aircraft-t/); [Acta Aeronautica 2024](https://hkxb.buaa.edu.cn/EN/10.7527/S1000-6893.2024.30405). IDGs have inlet/outlet oil temperature sensors, and a per-flight maximum-temperature trend is alarmed — [US 12,429,512](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12429512). A Navy SBIR sought F-18 generator bearing prognostics plus winding thermal monitoring — [Navy SBIR topic](https://www.navysbir.com/06_s/19.htm) [TRANSFER]. The DRDO 5 kW generator has BITE [DIRECT].
- **Battery**: end of life at 30 % capacity fade on NASA 18650 data — (`faults_and_degradation.md`) [TRANSFER]. Tejas: JFS starts depend on battery state (85 % in the Leh trial) [DIRECT].
- **Brakes and tyres**: KQ6 anchors (carbon wear per application; 0.025 mm per cycle civil; F-16 tyres 4–12 landings; ≤5 %/24 h tyre leak) [TRANSFER]. Tejas RTO at 50/70/90 % wear [DIRECT]. Brake-system software defect → tyre burst → runway excursion (2026) [DIRECT].
- **JFS / AMAGB**: M1 failed 3-start requirement cold/high; M1 excessive oil consumption; M2 self-contained oil system; AMAGB 750 h life; AMAGB bearings indigenised [DIRECT]. F/A-18 AMAD oil low and oil temperature high cautions [TRANSFER].
- **Fire detection**: historic 50 % missed and 83 % false — [DTIC AD0663213](https://apps.dtic.mil/sti/tr/pdf/AD0663213.pdf) (search excerpt) [TRANSFER].
- **Fuel**: Tejas "fuel leak" (structural), gauging artefacts at high pitch with low fuel, a probe redesign (18-series, Issue-4), and higher-capacity DC pump retrofit [DIRECT].

### Inferences
- [ASSUMPTION] Degradation-to-observable map for the generator (summary; full table in Synthesis (b)):
  - pump η_v ↓ → hydraulic pressure sag under demand at low N2, case-drain flow/temperature ↑, fluid temperature ↑;
  - compensator drift → no-load pressure ↓ (per-flight CI);
  - filter clog → ΔP ↑ (exponential) → bypass/pop-up discrete;
  - precharge ↓ → faster pressure decay after pump-off, more pump cycling, brake applications available ↓;
  - HX fouling → PHX outlet temperature ↑ and TCV position saturating, then cockpit/avionics temperature excursion only at the limit;
  - rectifier diode → AC ripple and 6-pulse harmonics ↑, GCU BITE;
  - bearing → AMAGB/generator oil temperature ↑ and debris;
  - tyre/brake → inspection-only states (wear %, pressure) plus RTO-capability constraints.

### Gaps
- Fighter-specific rates for every utility mechanism are missing. Treat all rates as [ASSUMPTION] calibrated to maintenance-interval proxies (750 h AMAGB life; 45 chute streamings; 4–12 tyre landings; ADA brake wear tests).

---

## KQ11. Modelling approach and fidelity: evidence from programmes that model these systems

### Takeaway
Industrial practice (Saab Gripen) uses physical lumped-parameter models (Easy5, then Modelica/Dymola) with the real control software in the loop, at several fidelity levels. The low-fidelity real-time ECS version uses deliberately enlarged time constants for fixed-step solvers. Fuel tanks are modelled as low-order air dynamics with algebraic fuel to avoid stiffness. Time steps follow explicit stability rules. Civil PHM practice uses 1D thermodynamic ECS models with effectiveness degradation, empirical linear-trend pump models, and rig data at 100 Hz (pressure)/10 Hz (flow)/1 Hz (temperature) for texture.

### Cited Findings
- Time-step rules for explicit Euler: first-order tank dynamics need h ≪ 2/ω_b. Lightly damped (δ ≈ 0.1) second-order hydraulic-actuator dynamics need h ≪ 0.1/ω_b, so Euler "cannot be recommended for second order systems with low damping". Alternatives: change integrator, reduce h, or remove dynamics above model bandwidth (ω_n > 0.7·ω_m, else make it algebraic) — [Lantto et al., ICAS 2006-039, §§5–6](https://icas.org/ICAS_ARCHIVE/ICAS2006/PAPERS/039.PDF).
- ECS fidelity ladder: (1) high-fidelity Dymola, (2) fixed-step export with increased time constants, (3) low-fidelity real-time for HIL. Controlling software sampled at 30 Hz. Steady-state detection uses windowed standard deviation or variation coefficients on altitude, Mach and PLA — [Hällqvist et al., SIMS 2015](https://ep.liu.se/ecp/119/020/ecp15119020.pdf); [ICAS 2016-0188](https://www.icas.org/ICAS_ARCHIVE/ICAS2016/data/papers/2016_0188_paper.pdf).
- HAL fighter ECS: AMESim 1D model with compressible valve flow and lookup-table controllers; four samples/s sensing — [Heliyon 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9708630/).
- B737 ECS: a 1D thermodynamic model (component efficiencies and HX effectiveness) simulates degraded HX, valves and water separator — [IJPHM 2019](https://papers.phmsociety.org/index.php/ijphm/article/view/2731).
- Modelling tool notes (Modelica MSL, DLR ThermofluidStream, Simscape) and UCI hydraulic-rig texture — (`modelling_methodology.md` §4).

### Inferences
- See Synthesis (d) for the per-system recommendation.

### Gaps
- No open fighter utility-system model was found (Modelica/FMU, Easy5 libraries are proprietary).

---

## Synthesis (required closing items a–f)

### (a) Key findings summary
1. **Secondary power is now well documented** [DIRECT]. F404 engine gearbox → CVRDE PTO shaft (lubrication-free; 118 N·m normal / 410 N·m peak start at a rated 16,810 rpm ≈ 100 % N2; ≈208 kW derived) → CVRDE/HAL AMAGB (single input, four pads: 2 hydraulic pumps, 1 generator, 1 starter; self-contained lubrication; 750 h life; >6,000 fleet FH) → GTSU-110 JFS (110 kW, 52 kg; free power turbine; ground start and relight assistance). Every utility power source is slaved to N2 through fixed ratios.
2. **The JFS is the best-evidenced utility degradation/availability story** [DIRECT]. Cold and altitude start failures (M1 at Leh, Jan 2013/2014), excessive oil consumption (M1), an M2 with a self-contained oil tank, the three-consecutive-start requirement, and a −15 °C/85 % battery/18–20 h soak demonstration with F404 start-schedule patches. A start-success model must depend on battery state, ambient temperature and altitude.
3. **Hydraulics** [DIRECT core + probable HAL parts]. Two 280 bar systems; tandem dual-hydraulic primaries; single-hydraulic slats; open-loop airbrakes on electro-selector valves; 9 filters of 6 types; hydraulic unlocking of mechanical uplocks; emergency gear and park-brake cables. Probable Tejas LRUs: LH/RH bootstrap reservoirs (280/5.5 bar, 9.5 L, −54/+135 °C, MIL-H-5606, level sensor), an airbrake actuator (2.5–5 t, 294 mm, dual LVDT) and an electro-selector valve (40 L/min). Pump flow is unconfirmed (an unverified excerpt says 110 L/min per pump, consistent with the PTO power budget).
4. **Fuel** [DIRECT]. F1/F1A/F2 fuselage tanks plus wing tanks (fore probes), about 2,458 kg internal, 1,200/800/725 L drop tanks, pressure and hot refuelling, AAR at 250–295 kt, an ECFM-C controlling gauging, auto-transfer, F2 pump auto operation, dump (naval), and attitude-compensated gauging with HAL capacitance probes (frequency/period output). A documented high-pitch, max-AB, low-fuel (<1,200 kg) gauging artefact triggered false low-fuel warnings until a pick-up/vent mod.
5. **Electrical** [DIRECT core + probable parts]. An imported main AC generator on the AMAGB; a DRDO 5 kW brushless DC backup generator (PMG/exciter/main; FPGA/DSP GCU with BITE); a DC emergency bus; and a battery that cranks the JFS. Probable HAL parts: two 7.5 kW/250 A TRUs, an auto-reconfiguring master box, and a 45 Ah battery with a 30 Ah low warning. MIL-STD-704F supplies normal, abnormal, emergency and transfer bands. The main generator rating and type are not public.
6. **ECS** [DIRECT core + transfers]. A bleed-air bootstrap-class system for cockpit, avionics, radar and fuel-tank pressurisation and OBOGS. ECS sensors span −55 to 100/300 °C, with bleed/high/low pressure switches and hot-air-leak detection. Probable PHX: 0.575 kg/s, 6.56 bar, ≤578 °C in, <170 °C out. HAL's fighter ECS paper gives 2.8–6.4 bar and 175–440 °C bleed over 75–97 % rpm, 4 samples/s sensing and TCV limit-cycling behaviour. Gripen ECS control runs at 30 Hz with an APU→engine bleed switch transient. PIB confirms ECS/OBOGS condensate draining in humid conditions.
7. **Landing gear/brakes/tyres/chute** [DIRECT + probable]:
   - Gear: hydraulic tricycle with twin forward-retracting nose wheels.
   - Brakes: carbon-carbon, 3 rotors/4 stators; brake-by-wire pedals; anti-skid manifold.
   - Tyres: Mk1 main 26 × 8.0-14 (probable 16.9 bar, 6,090 kg static); nose 360 × 135-6 (7 bar).
   - Brake chute: 17 m² hybrid, deploy ≤285/340 km/h, 45 streamings / 8 years.
   - Wear tests: RTO at 50/70/90 % brake wear.
   - The 2026 brake-software event (brake failure → tyre burst → runway excursion → ≈2-month fleet grounding) is a ready-made configuration-driven fault chain.
   - The F-16 analogue (same tyre class) gives 4–12 landings per main tyre.
8. **Utility management** [DIRECT]. Prototypes had four EUs (engine, electrical, hydraulic, fuel, ECS) merged into two for production. ADA's dual-redundant USMS, an L&T ECFM (controller, ECS control panel, ground refuelling panel) and a microprocessor BMS sit alongside the DFCC (actuator BIT, simplex probe-heater currents) and the ECMS. The Mk1A adds an indigenous HUMS DAU (PCC PCAMi-1000, 124 units). No USMS I/O, rate or BIT detail is public.
9. **The best normal-behaviour bands come from public MIL standards** (MIL-STD-704F, MIL-H-5440H, MIL-E-18927E, MIL-G-26988C). The best signal-set/rate realism comes from the F/A-18 HARV catalogue (utility discretes and fuel quantities at 40 samples/s; one analog hydraulic pressure at 80 samples/s). The best modelling-practice evidence comes from Saab Gripen papers (lumped physics with real control software; fidelity ladders; stiffness and time-step rules).
10. **Degradation evidence is mechanism-rich but rate-poor.** Pump volumetric loss and compensator drift, exponential filter ΔP, precharge leakage, HX fouling masked by control, rectifier-diode and bearing faults in generators, application-count carbon-brake wear, tyre wear and leak, and JFS cold-start and oil consumption all have mechanisms and observables. Almost no fighter-specific rates are public. Calibrate to interval proxies (AMAGB 750 h; chute 45 streamings; tyres 4–12 landings; ADA brake-wear test points).

### (b) Per-system sensor inventory (signals the generator should emit)
Rates: "model" = suggested internal update; "bus/rec" = what a 1553/recorder stream would plausibly carry. HARV 40/80 samples/s values are the F/A-18 research-recording [TRANSFER] anchor.

| System | Signal | Sensor type | Range / units | Likely rate | Driver variables | Related signals | Tag | Source |
|---|---|---|---|---|---|---|---|---|
| Secondary power | AMAGB input speed | derived from N2 (FADEC) | 0–≈17,500 rpm (rated 16,810) | model 80 Hz; bus 10–20 Hz | N2 | pump/generator speeds | DIRECT rated speed; ratio ASSUMPTION | [DDP 8779](https://www.ddpmod.gov.in/node/8779) |
| Secondary power | AMAGB oil temperature / temp-high caution | RTD or thermistor + switch | −54…≈150 °C; caution discrete | 1 Hz analog; 40 Hz discrete | accessory load torque, N2, ambient, oil-cooling | oil level, chip | TRANSFER (F/A-18 AMAD) | [CR-201670](https://ntrs.nasa.gov/citations/19970014822) |
| Secondary power | AMAGB oil level low / chip | level switch; magnetic chip detector | discrete | 40 Hz discrete; ground inspection | leakage, consumption; bearing spall debris | oil temp | ASSUMPTION (self-contained lube DIRECT) | [DRDO](https://drdo.gov.in/amagb-lca); CR-201670 |
| Secondary power | JFS speed, JFS EGT | mag pickup; thermocouple | rpm; 0–1,000 °C (ASSUMPTION) | 20 Hz during start | battery SOC, OAT, pressure altitude, fuel schedule | N2, crank current | ASSUMPTION | [DDP 8778](https://www.ddpmod.gov.in/node/8778) |
| Secondary power | Start record (attempt, success, time-to-idle, consecutive count) | computed event | event | per start | as above | battery Ah | DIRECT requirement | [CAG 17/2015 p.35](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf) |
| Secondary power | JFS oil quantity / consumption | level (M2 self-contained tank) | L or % | per run / per start | starts, wear | start record | DIRECT existence; values ASSUMPTION | [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) |
| Hydraulics (×2) | System pressure | strain-gauge/MEMS transducer | 0–350 bar; nominal 280 | model 200–500 Hz; bus 20–80 Hz | N2 (pump speed), actuator flow demand, leakage, temperature | reservoir level, LP switch, actuator rates | DIRECT nominal; sensor ASSUMPTION | [Kala](https://joast.org/index.php/joast/article/view/317); [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf) |
| Hydraulics (×2) | Low-pressure warning | pressure switch | discrete | 40 Hz | as above | master caution | TRANSFER | [MIL-H-5440H §3.6.13.1](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-H/MIL-H-5440H_14866/) |
| Hydraulics | Hydraulic pressure status per DFCC channel | pressure switches | discrete ×4 | 40–80 Hz | as above | actuator BIT | TRANSFER | [CR-201670](https://ntrs.nasa.gov/citations/19970014822) |
| Hydraulics (×2) | Fluid temperature | MEMS/RTD | −54…+135 °C | 1–4 Hz | pump losses, leakage throttling, HX cooling, ambient | fuel temp | DIRECT range (HAL parts); MIL-H-5440 Type II | [DDP 9659](https://www.ddpmod.gov.in/node/9659) |
| Hydraulics (×2) | Reservoir level (+ low-level discrete) | level-sensing device in bootstrap reservoir | 0–9.5 L (0–100 %) | 1 Hz | temperature, gear/actuator positions, accumulator state, leakage | pressure | DIRECT part (probable) | [DDP 9659](https://www.ddpmod.gov.in/node/9659) |
| Hydraulics | Filter ΔP / clog (9 filters, 6 types) | ΔP switch / pop-up | discrete (+ maintenance flag) | on change; per-flight summary | flow, viscosity (temperature), contaminant mass | fluid temp | DIRECT count; indicator ASSUMPTION | [ADA GS](https://www.ada.gov.in/images/gs.htm); MIL-H-5440H |
| Hydraulics | Pump case-drain flow/temp | flowmeter/RTD | L/min; °C | 1 Hz (if fitted) | volumetric wear | pressure | TRANSFER (civil EDP PHM); Tejas unknown | [Gomes et al.](https://papers.phmsociety.org/index.php/phmconf/article/view/2085) |
| Hydraulics | Accumulator precharge | gas gauge (ground) | bar (e.g., 50 bar N₂ brake accumulator) | inspection | gas leakage, ambient temperature | brake applications available | TRANSFER/part | [DDP 9656](https://www.ddpmod.gov.in/node/9656) |
| Hydraulics/FCS | Airbrake position | dual-core LVDT | 0–294 mm | 40–80 Hz | command, pressure, air load (2.5–5 t) | speedbrake discrete | DIRECT part (probable) | [DDP 9660](https://www.ddpmod.gov.in/node/9660) |
| Fuel | Contents per tank (F1, F1A, F2, wing, DTs) | capacitance probe, frequency/period output | kg; probe ±3/±5 µs | model 1–10 Hz; bus 1–40 Hz | Wf, transfer logic, pitch/roll, Nx/Nz, slosh, density/temperature | total, CG, low-fuel | DIRECT probes | [DDP 10090](https://www.ddpmod.gov.in/node/10090); [DRDO TA](https://drdo.gov.in/drdo/node/10962) |
| Fuel | Total fuel; low-fuel; bingo | computed; low-level from an independent capacitive level switch (TRANSFER/ASSUMPTION) | kg; discretes | 1–40 Hz | as above + attitude artefact | contents | DIRECT artefact | [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf); [MIL-F-17874B](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-F/MIL-F-17874B_20580/) |
| Fuel | F2/boost pump pressure-low; pump status | pressure switch; current | discrete | 40 Hz | pump health, Nz < 0, low level | engine inlet pressure | DIRECT ("F2 pump") + TRANSFER | [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf); CR-201670 |
| Fuel | Fuel temperature (feed/engine inlet) | RTD | −40…+120 °C (ASSUMPTION) | 1 Hz | Wf, FOHE/HX heat, ambient, fuel remaining | oil and hydraulic temps | TRANSFER | [CR-201670](https://ntrs.nasa.gov/citations/19970014822) |
| Fuel | Tank pressurisation; DT pressurised/over-pressure | pressure switch/transducer | ≈0.1–0.5 bar g (ASSUMPTION) | 1–10 Hz | ECS supply, altitude, vent | transfer status | DIRECT function; values ASSUMPTION | [ADA CEF](https://www.ada.gov.in/images/cef.htm) |
| Fuel | Refuel/AAR/hot-refuel events | discretes (probe, valves, GRP preset) | event | event | ops | contents | DIRECT | [ADA ARs](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf) |
| Electrical | Main generator V (per phase), f, I; GEN OUT | GCU sensing | 108–118 V RMS; 393–407 Hz; A | model 10–50 Hz RMS | N2 (cut-in/underspeed), load, GCU state | bus V, TRU | TRANSFER (704F) | [MIL-STD-704F](https://everyspec.com/MIL-STD/MIL-STD-0700-0799/MIL-STD-704F_CHG-1_55461/) |
| Electrical | TRU 1/2 output V, I | shunt/Hall | 22–29 V; 0–250 A (overload 150/200/400 %) | 10 Hz | DC load | DC bus V | DIRECT part (probable) | [DDP 9646](https://www.ddpmod.gov.in/node/9646) |
| Electrical | 5 kW DC backup generator V/I/status + BITE | GCU (FPGA/DSP) | 28 V; ≈0–180 A (derived 5 kW/28 V) | 10 Hz | main generator failure | emergency bus | DIRECT | [DRDO](https://drdo.gov.in/5-kw-brushless-dc-generating-system-lca-tejas-0) |
| Electrical | Battery V, I, Ah; BATT LOW | shunt + integrator | 0–45 Ah; warning 30 Ah; 50 A charge | 1–10 Hz; Ah per s | JFS crank, charging, temperature | DC bus | DIRECT part (probable) | [DDP 10096](https://www.ddpmod.gov.in/node/10096) |
| Electrical | DC buses (main/essential/emergency) V | voltage sense | 22–29 V normal; 16–29 V emergency; 12–29 V starting; ripple ≤1.5 V | 10–50 Hz | sources, transfers (≤50 ms) | BIT resets | TRANSFER | [MIL-STD-704F](https://everyspec.com/MIL-STD/MIL-STD-0700-0799/MIL-STD-704F_CHG-1_55461/) |
| ECS | Bleed-inlet pressure (switch; transducer ASSUMPTION) | pressure switch/transducer | in flight ≈2.8–6.4 bar abs (TRANSFER); duct design 37 bar g | 4–30 Hz | N2/PLA, altitude, Mach, OAT | bleed temp, PHX out | DIRECT switch; TRANSFER values | [ADA LRU.pdf](https://www.ada.gov.in/images/LRU.pdf); [Heliyon 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9708630/) |
| ECS | Bleed / PHX-outlet / turbine-inlet temperature | RTD/TC (−55…300 °C class) | °C (PHX in ≤578, out <170 probable) | 4 Hz | engine state, ram cooling, fouling | TCV position | DIRECT range; probable PHX | [ADA LRU.pdf](https://www.ada.gov.in/images/LRU.pdf); [DDP 10095](https://www.ddpmod.gov.in/node/10095) |
| ECS | ACM outlet / cockpit supply / cockpit temperature | RTD (−55…100 °C class) | °C; T_mean = 0.25·T_in + 0.75·T_out | 4 Hz (HAL); control 30 Hz (Gripen) | TCV control, OAT, humidity, sun load | TCV | DIRECT range; TRANSFER logic | [Heliyon 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9708630/); [SIMS 2015](https://ep.liu.se/ecp/119/020/ecp15119020.pdf) |
| ECS | TCV / flow-control valve position | resolver/pot (ASSUMPTION) | 0–90°; 6–10 s full stroke | 4–30 Hz | temperature error, bleed pressure | temps | TRANSFER | [Heliyon 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9708630/) |
| ECS | Cockpit pressure / cabin altitude | cockpit pressure transducer (CPTCV) | psia; ΔP ≤5 psi; rates ≤0.2 psi/s | 4–10 Hz | altitude, ECS flow, canopy-seal leakage | CPCS valve | DIRECT existence; TRANSFER schedule | [CAG p.42](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf); [MIL-E-18927E](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-E/MIL-E-18927E_11721/) |
| ECS | Pressure-high / pressure-low switches; hot-air-leak detection | switches; continuous sensing element + control box | discretes | 40 Hz | duct over-pressure, duct leak | bleed shut-off | DIRECT | [ADA LRU.pdf](https://www.ada.gov.in/images/LRU.pdf) |
| ECS | Avionics cooling air temperature; avionics-hot caution | RTD + discrete | °C | 1–4 Hz | ECS flow, OAT, ground ops | DFCC/LRU temps | DIRECT function; TRANSFER caution | [ADA CEF](https://www.ada.gov.in/images/cef.htm); CR-201670 |
| Life support | OBOGS O₂ concentration, outlet pressure, OBOGS fail | O₂ sensor (in ILSS), pressure transducer | % O₂; kPa | 1 Hz | ECS supply pressure, altitude, demand, sieve health | breathing regulator | DIRECT existence; ranges ASSUMPTION | [Defense Post](https://thedefensepost.com/2025/03/13/indias-drdo-life-support-sysem/amp/) |
| Life support | LOX quantity (Mk1) | capacitance transmitter, frequency output ≈6,000→5,300 Hz | 0–5 L ±0.4 L | 0.1–1 Hz | consumption, boil-off | O₂ low | DIRECT part (probable) | [DDP 10089](https://www.ddpmod.gov.in/node/10089) |
| Landing gear | Gear up/down-locked ×3; handle; doors | proximity switches | discretes | 40 Hz | handle, hydraulic pressure, emergency cable | WoW | TRANSFER (HARV) + DIRECT uplock design | [ADA GS](https://www.ada.gov.in/images/gs.htm); CR-201670 |
| Landing gear | WoW per gear | strut proximity/switch | discretes | 40–80 Hz | strut compression, servicing state | FCS ground law, NWS, anti-skid | TRANSFER | CR-201670; F-35 AIB (faults note) |
| Brakes | Brake-feel (pedal) input L/R | potentiometers | 0–100 % | 40–80 Hz | pilot | brake pressure | DIRECT LRU | [ADA LRU.pdf](https://www.ada.gov.in/images/LRU.pdf) |
| Brakes | Wheel speed L/R; skid-valve activity; anti-skid fail | wheel-speed transducer; valve current | rpm; discrete | 100–200 Hz internal; 40 Hz recorded | ground speed, μ, brake pressure | decel (≤7 m/s² limit on HAL ASCU) | DIRECT (manifold) + part | [ADA LRU.pdf](https://www.ada.gov.in/images/LRU.pdf); [DDP 10092](https://www.ddpmod.gov.in/node/10092) |
| Brakes | Brake pressure per wheel | transducer (ASSUMPTION) | 0–≈200 bar (ASSUMPTION) | 40 Hz | pedal, anti-skid | wheel speed | ASSUMPTION | — |
| Brakes | Heat-sink temperature (model state; sensor unknown) | — | 0–≈600 °C | 1 Hz | brake energy, cooling | wear, tyre temp | TRANSFER thresholds | [Boeing AERO](https://www.leonardo-in-flight.nl/PDF/Boeing%20AERO%20Brakes.pdf) |
| Brakes | Brake wear (% worn) | inspection (pin) | 0–100 % | per inspection | applications, energy, temperature | RTO capability | DIRECT (% worn metric) | [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf) |
| Tyres | Tyre pressure (cold check) | hand gauge ±2 % | main 16.9 bar; nose 7 bar | daily / pre-flight | gas temperature (1 %/≈2.8 °C), leak ≤5 %/24 h | tyre wear | DIRECT part + TRANSFER rules | [DDP 9654](https://www.ddpmod.gov.in/node/9654); [FAA AC 20-97B](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-97B.pdf) |
| Tyres | Tread wear / landings on tyre | inspection | landings (≈4–12 F-16 analogue) | per landing | mass, speed, slip, braking, crosswind | brake use | TRANSFER | [Chawla NTRS](https://ntrs.nasa.gov/citations/19960009454) |
| NWS | Input pot, feedback pot, free-castor solenoid, NWS fail | pots; solenoid state | ±deg; discretes | 40–80 Hz | pedals, WoW, ground speed | yaw rate (ground) | DIRECT LRUs | [ADA LRU.pdf](https://www.ada.gov.in/images/LRU.pdf) |
| Brake chute | Deploy / jettison / unsafe; streaming count | discretes; log | event; count ≤45 | event | landing speed ≤285 (≤340) km/h | brake energy | DIRECT life + TRANSFER cautions | [DDP 8027](https://www.ddpmod.gov.in/node/8027) |
| Fire | Engine-bay fire/overheat warning; extinguisher fired | detector loop (ASSUMPTION); cartridge | discretes | 40 Hz | bay temperature, leaks | crash switch | DIRECT (bottle) + TRANSFER detection stats | [ADA GS](https://www.ada.gov.in/images/gs.htm); [DTIC AD0663213](https://apps.dtic.mil/sti/tr/pdf/AD0663213.pdf) |
| Ice/heating | Probe-heater currents (pitot, AoA) | current sense (simplex, DFCC) | A | 80 Hz (DFCC frame) | OAT, icing, heater health | air-data validity | DIRECT existence | [Kala](https://joast.org/index.php/joast/article/view/317) |
| Utility mgmt | USMS/ECFM/BMS health words, fault codes, master caution | 1553 messages | words/bits | ≈12.5 Hz health (ADE example) | all of the above | OAC/MFD | ASSUMPTION/TRANSFER | [Trivedi, JOAST](https://joast.org/index.php/joast/article/view/598) |

### (c) Cross-system coupling map (driver → driven, with direction and evidence)
| # | Driver (state) | Driven (state) | Mechanism / sign | Time scale | Tag / source |
|---|---|---|---|---|---|
| 1 | Engine N2 | AMAGB, pump and generator speeds | Fixed gear ratios; PTO rated 16,810 rpm at ≈100 % N2 | instant | DIRECT speed ([DDP 8779](https://www.ddpmod.gov.in/node/8779)); ratio ASSUMPTION |
| 2 | N2 (pump speed) × actuator demand | Hydraulic pressure | Pressure-compensated pump holds 280 bar until demand > Q_max(N2); sag and ripple at low N2 + high demand | 10–100 ms | ASSUMPTION; MIL-H-5440H §3.6.3.4 |
| 3 | Flight condition (q, Mach, AoA) + FCS activity | Actuator flow demand → hydraulic pressure, fluid temperature | Hinge moment sets ΔP across actuator, rate sets flow (Q = A·ẋ); losses heat the fluid | ms (flow); minutes (temperature) | TRANSFER ([TM-110216](https://ntrs.nasa.gov/citations/19960027892)) |
| 4 | Hydraulic pressure | FCS actuator rate limits, airbrake extension, gear and brake capability | Rate limit ∝ √(ΔP_available − ΔP_load) | ms | TRANSFER (TM-110216) → airframe sibling |
| 5 | Hydraulic fluid temperature | Leakage, pump η_v | Viscosity ↓ → internal leakage ↑ → η_v ↓ | minutes | TRANSFER (MIL-H-5440 thermal analysis; F-15 AIB) |
| 6 | N2 (spool-down/flameout) | Main generator online state | Underspeed → generator offline → transfer to 5 kW DC backup/battery (≤50 ms interruption) | 0.05–1 s | TRANSFER ([Holloman AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf); 704F) |
| 7 | Electrical bus state | USMS/ECFM/BMS/DFCC function, BIT logs | Transients cause resets and nuisance BIT; loss causes degraded modes | ms–s | TRANSFER (AFTI, F-16 AIBs) |
| 8 | Battery state of charge, OAT, altitude | JFS start success | Cold or low SOC lowers cranking power; altitude lowers JFS power | per start | DIRECT ([CAG](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf); [IDR](https://indiandefencereview.com/lca-tejas-passes-cold-weather-test-at-leh/)) |
| 9 | JFS torque | N2 during start (via AMAGB/PTO) | JFS 110 kW free turbine → PTO (≤410 N·m) → engine | 20–40 s | DIRECT ratings; sequence in engine sibling |
| 10 | N2/PLA, altitude, Mach, OAT | Bleed pressure and temperature | 75→97 % rpm: 2.8→6.4 bar, 175→440 °C (HAL fighter); up to ≈578 °C at PHX inlet | s | TRANSFER ([Heliyon](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9708630/)) + probable part |
| 11 | Bleed extraction | Engine thrust and T5 | ≈1 % more bleed at MIL ≈ −2 % thrust (F404 -400) | s | TRANSFER (engine sibling, TM-104247) |
| 12 | Bleed + ram air (Mach, altitude, OAT, humidity) | Cockpit/avionics supply temperature, cockpit pressure, condensate | Bootstrap cycle; TCV control 4–30 Hz; water separator | s–min | DIRECT function + TRANSFER |
| 13 | ECS supply | Fuel-tank pressurisation, OBOGS feed, radar pressurisation | Pneumatic subscribers | s | DIRECT ([ADA CEF](https://www.ada.gov.in/images/cef.htm)) + TRANSFER (Gripen) |
| 14 | ECS cooling | Avionics/DFCC temperature → BIT, NFF | Cooling loss → LRU temperature ↑ (DFCC tolerates 1 h) → intermittent faults; water seepage → faults | min–h | DIRECT ([Kala](https://joast.org/index.php/joast/article/view/317); CAG p.42) |
| 15 | PLA/AB | Fuel flow → contents per tank → CG | Depletion and transfer sequence | s–min | DIRECT (tanks) + engine sibling |
| 16 | Pitch attitude, Nx, Nz, slosh | Probe-indicated contents, low-fuel warning, boost-pump inlet | Fuel surface tilt and migration; false low-fuel at >40° pitch, max AB, <1,200 kg | s | DIRECT ([ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)) |
| 17 | Fuel flow (heat-sink capacity) | Fuel, engine-oil and hydraulic temperatures | Low Wf + hot ambient raise temperatures; fuel recirculation limits | min | TRANSFER (patents; F-15 FOHE) |
| 18 | Landing mass, touchdown speed, chute, runway μ | Brake energy → heat-sink temperature → wear, tyre temperature/pressure | E = ½mV² minus drag and chute; carbon wear mainly per application | s (energy); min (cooling) | DIRECT (chute limits, RTO) + TRANSFER |
| 19 | Hot refuelling / short turnarounds | Cumulative brake and tyre temperatures | Incomplete cooling between sorties | h | DIRECT (hot refuel) + TRANSFER ([Boeing AERO](https://www.leonardo-in-flight.nl/PDF/Boeing%20AERO%20Brakes.pdf)) |
| 20 | WoW | FCS law, NWS enable, anti-skid enable, gear-handle lock, ECS ground mode, recorder and BIT modes | Discrete mode switch (false WoW can switch to ground law in flight) | instant | TRANSFER (F-35 AIB) |
| 21 | Ambient cold soak | Battery capacity, hydraulic viscosity, accumulator precharge, tyre pressure, JFS start | Gas law and viscosity; Leh/Himalayan cases | h | DIRECT (JFS) + TRANSFER |
| 22 | Dust, sand, salt (Indian bases) | Filter ΔP growth, actuator seal wear, HX fouling | Contaminant ingress; MIL-STD-810F sand/salt qualification | 100s h | DIRECT ([JOAST 211](https://joast.org/index.php/joast/article/view/211)) + TRANSFER |
| 23 | Hydraulic system loss | Wheel brakes (accumulator ≈10 applications), gear (emergency cable), NWS | Back-up paths | event | DIRECT part ([DDP 9656](https://www.ddpmod.gov.in/node/9656)) + DIRECT cables |
| 24 | Brake-software configuration | Braking effectiveness → tyre burst → runway excursion → fleet grounding | Configuration-driven fault chain | event / weeks | DIRECT ([ThePrint](https://theprint.in/defence/suspected-brake-failure-leads-to-tejas-accident-after-landing-airframe-likely-to-be-written-off/2860898/); [Tribune](https://www.tribuneindia.com/news/india/iafs-grounded-tejas-jets-to-resume-flying-next-week-after-software-fix-says-hal-chairman/)) |
| 25 | DC fuel pump capacity | Windmill relight success | Fuel pressure at low N2 | s | DIRECT ([ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf)) |

### (d) Recommended modelling approach per system, fidelity, time step and calibration anchors
| System | Model form (fidelity) | States | Couplings in → out | Step | Fault/degradation parameters | Calibration anchors |
|---|---|---|---|---|---|---|
| AMAGB + PTO | Algebraic kinematics (fixed ratios) + torque sum + 1–2-state lumped oil thermal model | oil temperature, oil quantity, bearing damage index | N2 → pad speeds; accessory torques → PTO torque/power; oil temperature → caution | 50 ms (thermal 1 s) | oil leak rate, bearing spall growth (debris/temperature), life counter (h) | 16,810 rpm rated; 118 N·m normal / 410 N·m start; 750 h life; >6,000 FH fleet [DIRECT] |
| JFS | Discrete-event start sequencer + low-order spool (1st-order speed, EGT lag) + probabilistic start success | JFS speed, EGT, oil quantity, battery SOC draw, consecutive-start count | battery, OAT, altitude → success/time; torque → N2 (engine sibling) | 20–50 ms during start | oil consumption per start (M1 high, M2 nominal), cold-start margin, igniter/fuel-control faults | 110 kW, 52 kg; 3 consecutive starts at −15 °C, 85 % battery, 18–20 h soak; M1 failures Leh Jan 2013/14; rig at 3,260 m and 5.6 km [DIRECT] |
| Hydraulics (×2) | Lumped-parameter network per system: pressure node (bulk modulus + accumulator), pressure-compensated variable pump (flow-limited by N2), actuator flow sinks from FCS/gear/brake demands, relief valves, leakage conductances, bootstrap reservoir volume; 1-state thermal per system | P, reservoir volume, fluid temperature, accumulator gas volume/pressure, filter loading | N2, FCS rates and loads (airframe sibling), gear/brake/NWS events → pressure, temperature, level, LP discretes | 1–5 ms if pressure dynamics are explicit (stiff; implicit or reduced per Lantto); 10–20 ms quasi-static | η_v (internal leakage), compensator set-point drift, external leak rate, precharge loss, filter clog coefficient (exponential ΔP), water/particulate contamination, seal wear | 280 bar; 9.5 L reservoir (probable); LP 5.5 bar; −54/+135 °C; 9 filters/6 types; actuator 9 Hz and 2–10 t stall; ESV 12.5 bar at 40 L/min; airbrake 2.5–5 t/294 mm; pump flow TBD (110 L/min lead) |
| Fuel | Tank network: mass states per tank; transfer, feed and refuel state machine (ECFM-C-like); boost-pump curve vs Nz; gauging model (probe heights from attitude, acceleration and slosh, MIL-G-26988 error classes, density compensation); per-tank lumped fuel temperature; tank-ullage pressure (low-order air dynamics, fuel algebraic) | m_i, T_fuel_i, p_ullage_i, valve and pump states | Wf (engine) out; HX heat in; ECS pressurisation in; attitude/Nx/Nz in → contents, CG, warnings | 0.1 s (mass, temperature); 10–50 ms if feed pressure modelled | probe drift/offset, probe wetting faults, pump wear (pressure-low), valve stuck, vent blockage, leak (structural) | 2,458 kg internal; DT volumes; zoom-climb artefact (>40° pitch, <1,200 kg, max AB); hot refuel 50 psi; partial pressure refuel 25 psi; AAR 250–295 kt; probe ±3/±5 µs [DIRECT] |
| Electrical | Quasi-static bus/source network with source-selection state machine (main gen, 2 TRUs, 5 kW DC backup, battery, ground power); load table per mission phase; battery Thevenin/SOC model with temperature; stochastic power-quality overlay within 704F bands (ripple, modulation, transients, ≤50 ms transfers) | gen state, bus voltages, battery SOC and temperature, load set | N2 → gen online; mission phase → loads; JFS crank → battery | 20–100 ms (overlay 1–5 ms if harmonic texture needed) | rectifier-diode faults (ripple, harmonics), bearing/oil-temperature trend, regulator drift, battery capacity fade, contactor faults | 704F tables; 5 kW DC backup with BITE; TRU 7.5 kW/250 A and overloads (probable); 45 Ah/30 Ah warning (probable); AFTI 40 kVA/5 kVA donor |
| ECS + life support | Quasi-steady thermodynamic network (ε-NTU heat exchangers, simplified ACM compressor/turbine with shaft speed, compressible valve flows per HAL eqn.) + first-order thermal lags for cockpit and avionics bays + pressure-control loop (cabin schedule) + TCV controller at 4–30 Hz; OBOGS as a concentration vs inlet pressure/flow lookup | ACM speed, HX outlet temperatures, cockpit temperature and pressure, avionics bay temperatures, TCV angles, water-separator loading | bleed P/T (engine), Mach/altitude/OAT/humidity → temperatures, pressures, condensate; ECS → fuel pressurisation, OBOGS | 50 ms (control 33–250 ms) | HX effectiveness loss (fouling factor 0–1), valve sticking/slow drive, ACM bearing drag, duct leak (hot-air leak), sensor drift, water-separator clog, canopy-seal leak | bleed 2.8–6.4 bar / 175–440 °C over 75–97 % rpm (TRANSFER); PHX 0.575 kg/s, ≤578 °C in, <170 °C out (probable); sensor ranges; MIL-E-18927 rates and WBGT; 5 psi ΔP above 23,000 ft (TRANSFER); Jaisalmer soak 39–42 °C; Gripen control 30 Hz |
| Landing gear, brakes, tyres, NWS, chute | Gear sequencing state machine (locks, doors, emergency cable path); WoW per strut from the airframe sibling's strut model; brake: energy → lumped heat-sink temperature with convective cooling; wear = count + energy·f(T); anti-skid as slip controller only if needed; tyre: gas-law pressure, leak, wear per landing; chute: deploy-speed check and streaming counter | lock states, WoW, brake temperature and wear, tyre pressure and wear, chute life | landing mass/speed/runway (airframe sibling) → energy; hydraulics → availability; BMS software configuration → fault mode | 10 ms (anti-skid); 50 ms (sequencing); 1 s (thermal); per-landing (wear) | brake-software defect mode, anti-skid transducer fault, wear-out, tyre cut and leak, uplock/downlock spring relaxation, strut servicing loss | tyre sizes, pressures and loads (probable); 4–12 landings/tyre (TRANSFER); RTO at 50/70/90 % wear [DIRECT]; chute 285/340 km/h, 45 streamings, 8 yr [DIRECT]; ASCU 7 m/s² (part) |
| USMS/ECFM/BMS/BIT | Discrete-event monitor layer: thresholds + persistence timers + latching + priority; fault-code dictionary; imperfect coverage (miss/false-alarm probabilities); 1553-like message scheduler (health words ≈12.5 Hz) | latched cautions, fault logs, NFF flags | all subsystem signals → cautions, maintenance logs, HUMS frames | 12.5–80 Hz | sensor faults (bias, stuck, intermittent), BIT coverage gaps, nuisance trips on bus transients | 4 EUs → 2 in production; dual-redundant USMS; ECFM-C/ECS-CP/GRP; MIL-H-5440 diagnostic list; fire-detection historic 50 % missed/83 % false (TRANSFER) |

Implementation notes [ASSUMPTION]:
- Couple through explicit interfaces (N2, Wf, bleed P/T and flow, FCS actuator rates and loads, WoW, landing energy, bus voltages). This matches the modular approach in `modelling_methodology.md`.
- Use the Gripen fidelity ladder. A "desktop" high-fidelity variant (Modelica/FMU) verifies the "streaming" variant (NumPy state-space/algebraic, fixed step, enlarged time constants) used to produce data at scale.
- Emit utility signals through the sensor-texture layer, then the bus/recorder layer, at the rates in table (b). Use discrete cautions at 40 samples/s, as in HARV.

### (e) Open questions and gaps (priority order)
1. **Hydraulic pump rating** (flow per pump, displacement, pad speed), pump vendor and type, and consumer-to-system assignment. The "110 L/min at 280 bar" lead needs confirmation from DRDO/CVRDE AMAGB documentation (drdo.gov.in was inaccessible) or ADA.
2. **Main generator** rating, type (CF/IDG vs VF), cooling, vendor; bus/load-shed logic; drive of the 5 kW DC generator; battery chemistry/capacity on Mk1/Mk1A.
3. **Fuel tank capacities**, transfer sequence, CG schedule, probe count, boost-pump specs, negative-g provisions, fuel-temperature limits and heat-exchanger arrangement (fuel-cooled hydraulic/ECS/generator?).
4. **ECS**: bleed port and schedule, ACM configuration, cockpit pressure schedule, avionics liquid loop on Mk1A (AESA), caution list, CPCS behaviour.
5. **USMS/ECFM/BMS** I/O lists, bus rates, BIT/fault codes; fire-detection zones; ice detector presence. Leads: ACCS paper (Garg et al., ADA) and the NATO NFTC paper (blocked here).
6. **Landing gear** timings, emergency extension design, WoW logic, brake pressure and temperature sensing, BMS anti-skid algorithm, and tyre and brake life on Tejas.
7. Platform confirmation for the "probable" HAL parts (reservoir, airbrake actuator, ESV, wheels and brake, PHX, TRU, master box, LOX transmitter, F2-F/T probe). One HAL Lucknow/ADA confirmation would upgrade them to [DIRECT].
8. AMAGB oil system sensors and limits; JFS start timing, EGT and speed limits.
9. Fighter-specific degradation rates (pump η_v decline per FH, filter ΔP growth, precharge loss, HX fouling, generator TBOs). Only proxies exist.
10. Unread sources: Gavel (2007) thesis (DiVA down); Eek (2016) thesis; CEMILAC TA PDFs TA-1809/TA-1863; DRDO lab pages; DTIC (archive offline). WebSearch budget is nearly used (≈62 of ≈65), so a later pass should start with these direct fetches.

### (f) Ranked sources (most valuable first)
1. **DDP/MoD product catalogue (HAL, GIL entries)**: the only public numeric specs for Tejas utility LRUs and probable parts — e.g. [AMAGB 8779](https://www.ddpmod.gov.in/node/8779), [GTSU-110 8778](https://www.ddpmod.gov.in/node/8778), [brake chute 8027](https://www.ddpmod.gov.in/node/8027), [reservoir 9659](https://www.ddpmod.gov.in/node/9659), [main wheel 9654](https://www.ddpmod.gov.in/node/9654), [PHX 10095](https://www.ddpmod.gov.in/node/10095), [TRU 9646](https://www.ddpmod.gov.in/node/9646), [LOX 10089](https://www.ddpmod.gov.in/node/10089). Local text in `research_sources/tejas_utility/ddp_products/`.
2. **ADA web pages, LRU list and Annual Reports 2015-22**: architecture statements, LRU names, test anchors (JFS M2, brake-wear RTOs, zoom-climb fuel artefact, hot soak, AAR, OBOGS) — [GS](https://www.ada.gov.in/images/gs.htm), [LRU.pdf](https://www.ada.gov.in/images/LRU.pdf), [sys](https://www.ada.gov.in/images/sys.htm), [ARs](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf).
3. **CAG Report 17 of 2015**: JFS cold/altitude failures and oil consumption, LSP deficiencies (fuel, BMS, chute, U/C, water seepage, CPTCV), imports — [PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
4. **JOAST 67(2A) 2015 (Kala; CEMILAC)**: hydraulic/actuator facts, BIT, USMS, FOC issues — [317](https://joast.org/index.php/joast/article/view/317), [325](https://joast.org/index.php/joast/article/view/325).
5. **DRDO lab pages and PTO/AMAGB/5 kW generator releases** (via search excerpts) and the [ADU PTO article](https://aviation-defence-universe.com/maiden-successful-flight-test-of-drdos-indigenous-power-take-off-shaft-conducted-on-lca-tejas-in-bengaluru).
6. **Public MIL standards**: [MIL-STD-704F](https://everyspec.com/MIL-STD/MIL-STD-0700-0799/MIL-STD-704F_CHG-1_55461/), [MIL-H-5440H](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-H/MIL-H-5440H_14866/), [MIL-E-18927E](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-E/MIL-E-18927E_11721/), [MIL-G-26988C](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-G/MIL-G-26988C_36788/).
7. **NASA CR-201670 (F/A-18 HARV parameter catalogue)**: realistic utility discrete set and recording rates — [NTRS](https://ntrs.nasa.gov/citations/19970014822).
8. **Saab/Linköping Gripen papers**: modelling practice, fidelity, ECS subscribers, step-size rules — [ICAS 2006-039](https://icas.org/ICAS_ARCHIVE/ICAS2006/PAPERS/039.PDF), [SIMS 2015](https://ep.liu.se/ecp/119/020/ecp15119020.pdf), [ICAS 2016-0188](https://www.icas.org/ICAS_ARCHIVE/ICAS2016/data/papers/2016_0188_paper.pdf), [ICAS 2010-025](https://icas.org/ICAS_ARCHIVE/ICAS2010/PAPERS/025.PDF).
9. **HAL-ARDC fighter ECS paper (Heliyon 2022)**: Indian fighter bleed range, ECS architecture, sampling, control behaviour — [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9708630/).
10. **USAF Wright-Lab F-16 tyre paper**: fighter tyre life per landing — [NTRS 19960009454](https://ntrs.nasa.gov/citations/19960009454).
11. **PHM papers**: [Gomes et al. 2012 (EDP)](https://papers.phmsociety.org/index.php/phmconf/article/view/2085), [Bischof et al. 2022 (pump η_v)](https://papers.phmsociety.org/index.php/phme/article/download/3341/1908), [Esperon-Miguez et al. 2019 (ECS faults)](https://papers.phmsociety.org/index.php/ijphm/article/view/2731), [Mortimore CEAS 2007 (gear/brake/tyre HM)](https://www.fzt.haw-hamburg.de/pers/Scholz/ewade/2007/CEAS2007/papers2007/ceas-2007-340.pdf).
12. **FAA AC 20-97B and Boeing AERO brakes**: tyre pressure/leak rules and brake-temperature thresholds — [AC 20-97B](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-97B.pdf), [AERO](https://www.leonardo-in-flight.nl/PDF/Boeing%20AERO%20Brakes.pdf).
13. **NASA TP-2857 (AFTI/F-16) and USAF AIB reports**: electrical/hydraulic architecture and fault cases — [TP-2857](https://ntrs.nasa.gov/citations/19890014956); AIBs as cited.
14. **Official/news items for events**: [newsonair/PIB fact check](https://www.newsonair.gov.in/pib-fact-check-no-oil-leak-in-tejas-mk1-at-dubai-air-show), [IDR Leh](https://indiandefencereview.com/lca-tejas-passes-cold-weather-test-at-leh/), [Tribune](https://www.tribuneindia.com/news/india/iafs-grounded-tejas-jets-to-resume-flying-next-week-after-software-fix-says-hal-chairman/), [ThePrint](https://theprint.in/defence/suspected-brake-failure-leads-to-tejas-accident-after-landing-airframe-likely-to-be-written-off/2860898/).
15. **Patents** (degradation indicator forms only): HX fouling factor, filter ΔP, accumulator gas leakage, IDG oil temperature, carbon-brake wear — as cited in KQ10.
