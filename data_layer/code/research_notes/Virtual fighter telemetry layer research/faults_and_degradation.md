# Faults and Degradation in Fighter-Aircraft Systems: physical origin, propagation, measurable signatures, and realistic modelling (Phalanx virtual-fighter telemetry layer)

Scope: how faults and degradation start physically, how they spread through the system, and how they show up in measured data, for the engine (with emphasis on low-bypass afterburning turbofans), engine mechanical parts, airframe utility systems, flight controls, and sensors. The aim is to model faults as physical state changes rather than as extra noise. Project context: "Phalanx". Candidate platforms are Tejas (F404-GE-IN20), F-16 (F100/F110), F/A-18 (F404), Gripen (RM12) and Su-30MKI (AL-31FP).

Evidence tags used throughout:
- **[DIRECT]**: about fighter aircraft or engines (or a military combat/trainer aircraft such as the T-38 or B-2, flagged as such).
- **[TRANSFER: domain]**: from another domain, with the reason it transfers and its limits.
- **[ASSUMPTION]**: not sourced, with a stated way to validate it.

Method notes for the report writer:
- PDFs were saved and text-extracted under `/Users/abishaikc/Phalanx/research_sources/faults/`. Nothing downloaded was executed.
- DTIC (apps.dtic.mil) refused automated access (HTTP 403, then a maintenance page), so DTIC fleet-reliability reports could not be read. This includes RTO-TR-028 on engine life-usage monitoring.
- USAF Accident Investigation Board (AIB) PDFs were read through the in-app browser from afjag.af.mil and pacaf.af.mil.
- Partway through the task the shared web-search budget for this turn (200 searches across all agents) ran out. After that, only known or previously found URLs were fetched. Several gaps listed below could probably be closed with more searching in a follow-up session.

Cross-links to parallel researchers:
- Engine-data researcher: thermodynamic engine models and influence matrices.
- Sensor-residual-texture researcher: noise and quantisation. This note covers sensor faults only.
- Maintenance-records researcher: maintenance-induced faults, NFF, and wash/overhaul effects.
- Modelling-methodology researcher: estimation of the stochastic models.
- Flight-profiles researcher: usage drivers such as throttle cycles, g-loads and landings.
- Data-pathway researcher: fault codes (MFL/PFL), CEMS/ECSMU recording.
- Validation researcher: calibration targets listed in the Gaps.

---

## 1. Gas-turbine degradation (low-bypass afterburning turbofan emphasis): mechanisms → component health parameters → gas-path signatures, including military-specific transient faults

### Takeaway
Gradual gas-path degradation should be modelled as slow drift in per-module flow capacity (Γ) and efficiency (η) health parameters. Each physical mechanism moves these in a characteristic direction: compressor fouling, erosion and rubbing reduce both Γ and η; turbine erosion, rubbing and thermal distortion raise Γ and lower η. Magnitudes are a few percent over thousands of cycles. These health-parameter shifts show up through the engine's closed-loop control as rising turbine temperature (FTIT/T5/EGT) and fuel flow at a fixed thrust or fan speed. Military-specific faults are mostly abrupt or transient events, not slow drifts: stalls and stagnation, vane mis-scheduling, fuel-control faults, afterburner light failures, nozzle-liner and cooling failures, and FOD. Their signatures in fighter flight data are documented: FTIT rises while N2 falls, followed by stall and afterburner fault codes, and generators dropping offline as the engine spools down.

### Cited Findings

**1a. Mechanism → health-parameter mapping**
- Urban's framework: physical problems (erosion, corrosion, fouling, built-up dirt, FOD, worn seals or excess clearances, burned/bowed/missing blades, plugged nozzles) degrade component performance (pumping capacities, compression and expansion efficiencies, temperature profile, turbine and exhaust nozzle areas). That degradation produces changes in spool speeds, fuel flow, temperatures and pressures. Urban's qualitative fault matrix marks compressor FOD with "Vibration: Yes" and a dirty compressor with "Vibration: No", so vibration helps separate FOD from fouling. [TRANSFER: industrial/aero gas turbines, AGARD-CP-165 (1975), reproduced in Cranfield ISABE short-course slides 2–3; the mapping is generic across gas turbines] — [Li, ISABE short course, citing Urban AGARD-CP-165](https://conference.isabe.org/content/scnotes/ivan/GT%20diagnostics3_4.pdf)
- Direction of health-parameter change by mechanism (Zwebek et al., as tabulated by Tahan/Tsoutsanis et al.) [TRANSFER: Cranfield performance-model studies of industrial/aero gas turbines; directions are physics-based and engine-independent, but magnitudes are not given] — [Tahan et al. review, Table 7](https://shura.shu.ac.uk/16176/8/Tsoutsanis-Performance-basedHealthMonitoring%28AM%29.pdf):
  - Compressor fouling, erosion, corrosion and blade rubbing: Γc↓, ηc↓.
  - Turbine fouling: ΓT↓, ηT↓.
  - Turbine erosion: ΓT↑, ηT↓.
  - Turbine corrosion: ΓT↓, ηT↓.
  - Turbine blade rubbing: ΓT↑, ηT↓.
  - Thermal distortion: ΓT↑, ηT↓.
  - FOD: Γ↓ and η↓ in both compressor and turbine.
- Recoverable versus non-recoverable [TRANSFER: same review] — [Tahan et al. review](https://shura.shu.ac.uk/16176/8/Tsoutsanis-Performance-basedHealthMonitoring%28AM%29.pdf):
  - Recoverable: compressor and turbine fouling (removable by washing).
  - Non-recoverable: erosion, corrosion, FOD/DOD.
- Particle size sets the mechanism. Fouling particles are typically smaller than 2–10 µm (smoke, oil mist, carbon, sea salt). Erosion particles "typically have to be larger than 10 µm". Erosion is "probably more a problem for aero engine applications" because aero engines lack the inlet filtration used on industrial machines. [TRANSFER: industrial GT study; the fighter relevance is that fighters operate unfiltered from dusty or saline bases] — [Kurz & Brun, ASME GT2011-45012](https://torroja.dmt.upm.es/congresos/asme_2011/data/pdfs/trk-19/GT2011-45012.pdf)
- JT9D teardown evidence on causes and mechanisms [TRANSFER: high-bypass commercial turbofan; the mechanisms are generic, but fighter flight loads (high g) and thermal cycling are more severe] — [Sallee 1978, NASA CR-135448, Summary](https://ntrs.nasa.gov/api/citations/19800013837/downloads/19800013837.pdf):
  - At 3,500 flights, pre-repair performance loss was attributed 40% to flight loads (case distortion, rubs, clearances), 40% to erosion (roughness, LE bluntness, camber and blade-length loss), and 20% to thermal distortion (area changes, leakage), varying ±13% with maintenance practice.
  - Dominant module mechanisms: fan, leading-edge bluntness; LPC, tip clearance; HPC, erosion (clearance, roughness, camber loss, with camber loss accelerating deterioration beyond about 3,000 cycles); HPT, tip clearance plus vane bow and twist; LPT, tip clearance.

**1b. Magnitudes and rates**
- Early-life ("short-term") step [TRANSFER: JT9D; mechanism is rub-in under flight loads, likely larger under fighter manoeuvre loads, ASSUMPTION to be validated against post-overhaul acceptance data] — [Sallee 1978](https://ntrs.nasa.gov/api/citations/19800013837/downloads/19800013837.pdf):
  - The average engine loses 1% TSFC on its first flight, growing to 1.5% by the 200th flight.
  - 55% of this loss is in the LP spool and 45% in the HP spool, caused by clearance increases from rubbing.
- Long-term deterioration and repair recovery [TRANSFER: JT9D fleet test-stand data] — [Sallee 1978](https://ntrs.nasa.gov/api/citations/19800013837/downloads/19800013837.pdf):
  - Fleet-average pre-repair TSFC deterioration is 4.4 ± 0.5% at 3,500 flights (~12,000 h).
  - Post-repair it is 3.5 ± 0.7%, mostly recovered through HPT restoration.
  - A further 1.9% TSFC could be recovered by refurbishing the cold section.
  - About 1.6% is unrecovered (distributed mechanical condition).
- Module health-parameter deterioration used as C-MAPSS reference values (Chatterjee & Litt), as percent change at initial / 3,000 cycles / 6,000 cycles [TRANSFER: 90,000-lbf class commercial turbofan model] — [Saxena et al. 2008, Table 3](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf):

  | Health parameter | Initial | 3,000 cycles | 6,000 cycles |
  |---|---|---|---|
  | Fan efficiency | −0.18 | −1.5 | −2.85 |
  | Fan flow | −0.26 | −2.04 | −3.65 |
  | LPC efficiency | −0.62 | −1.46 | −2.61 |
  | LPC flow | −1.01 | −2.08 | −4.00 |
  | HPT efficiency | −0.48 | −2.63 | −3.81 |
  | HPT flow | +0.08 | +1.76 | +2.57 |
  | LPT efficiency | −0.10 | −0.54 | −1.08 |
  | LPT flow | +0.08 | +0.26 | +0.42 |

- ProDiMES fleet-average deterioration profiles (based on Sallee, with turbine parameters adjusted), read approximately from Figure 6 [TRANSFER: commercial turbofan fleet simulation] — [Simon, ProDiMES User's Guide NASA/TM-2010-215840, p. 8](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf):
  - At 5,000 flights: ηFan ≈ −2%, γFan ≈ −3%, ηLPC ≈ −1.2%, γLPC ≈ −2%, ηHPC ≈ −5%, γHPC ≈ −9% (HPC accelerating after about 3,000 flights), ηHPT ≈ −1.3%, γHPT ≈ +1.5%, ηLPT ≈ −0.3%, γLPT ≈ +0.1%.
  - Engine-to-engine spread (cyan band) is a few tenths of a percent to several percent.
- Tip clearance sensitivity:
  - Each 0.001 in increase in HPT tip clearance raises SFC by about 0.1% and EGT by about 1 °C; 0.010 in gives about 1% SFC and 10 °C EGT.
  - "Military engines generally show slightly greater HPT tip clearance influence on SFC and EGT due to their higher operating speeds and temperatures."
  - [DIRECT qualitative statement on military engines; TRANSFER for the numbers] — [Lattime & Steinetz, NASA/TM-2002-211794](https://ntrs.nasa.gov/api/citations/20030003697/downloads/20030003697.pdf)
  - Industry rule of thumb: 0.25 mm (0.010 in) of turbine tip clearance ≈ up to 10 °C EGT and up to 1% turbine efficiency [TRANSFER: commercial] — [Melcher & Kypuros, NASA/TM-2003-212627](https://ntrs.nasa.gov/api/citations/20040031316/downloads/20040031316.pdf)
- Compressor and turbine roughness and clearance magnitudes [TRANSFER: industrial and aero component studies]:
  - Shroud roughness rising from 1.8 to 13 µm cost about 1% in flow capacity and about 1% in peak efficiency — [Kurz & Brun GT2011-45012](https://torroja.dmt.upm.es/congresos/asme_2011/data/pdfs/trk-19/GT2011-45012.pdf)
  - A 3% increase in compressor tip clearance gave −4.6% flow, −3% pressure ratio and −2.5% efficiency — [Tahan et al. review, Table 6](https://shura.shu.ac.uk/16176/8/Tsoutsanis-Performance-basedHealthMonitoring%28AM%29.pdf)
  - A clearance increase from 2.9% to 4.3% gave −2.5% efficiency and a 20% rise in surge flow coefficient — same source.
  - 10.2 µm turbine roughness gave about 2.5% efficiency loss on a two-stage turbine — same source.
- Effect of filtration on fouling-driven loss: 4% power loss after 3,000 h with a two-stage filter versus 2% with a three-stage filter (165 MW GT). Engine size and type showed "no real influence" on degradation rate between washes. [TRANSFER: industrial, but this bounds the dust-exposure effect for Indian bases] — [Kurz & Brun GT2011-45012](https://torroja.dmt.upm.es/congresos/asme_2011/data/pdfs/trk-19/GT2011-45012.pdf)
- Usage-severity evidence for fighters: the actual usage of the F404 on the F/A-18 "was significantly more severe than forecasted", leading to a life-limit reduction of "almost 50%" [DIRECT] — [Canada DND Technical Airworthiness Authority Advisory 2016-02](https://www.canada.ca/en/department-national-defence/services/military-airworthiness/technical-airworthiness-authority-overview/technical-airworthiness-regulatory-documents/technical-airworthiness-authority-advisories/2016-02.html)
- Mission profile: in Kawecki's comparison, a fighter spends 69% of fuel and 75% of mission time at cruise, versus 89% and 93% for a military transport. More time at transient and high-power conditions means more clearance excursions. [DIRECT] — [Lattime & Steinetz 2002](https://ntrs.nasa.gov/api/citations/20030003697/downloads/20030003697.pdf)

**1c. Signatures in measured gas-path parameters (influence coefficients)**
- Example steady-state fault signatures for a 1% change ("for illustration") in a Honeywell model-based diagnosis patent. The paper's example data come from an APU. [TRANSFER: Honeywell turbine/APU; gives sign and order of magnitude only] — [US 7,062,370 B2 (Vhora et al., Honeywell), Table I](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7062370):
  - HP turbine 1%: N2 −0.6%, fuel flow +0.6%, EGT +12 °F, P3 −0.5%.
  - Bleed band 1%: N2 +0.3%, fuel flow +0.7%, EGT +9 °F, P3 −0.3%.
  - Lube system 1%: hot-oil temperature +0.6%, low oil temperature +0.5%.
  - "Fault levels that warrant attention (e.g., 2% degradation of turbine) are easy enough to detect."
- ProDiMES module-fault definitions [TRANSFER: commercial turbofan; usable as a template for combined η/Γ module faults] — [ProDiMES User's Guide, Table 1 and Eq. 1, pp. 8–9](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf):
  - Fan, LPC and HPC faults: magnitude 1–7% RSS of (η, Γ), with Γ:η ratio 2:1 to 1:1, both reduced.
  - HPT and LPT faults: magnitude 1–7%, with Γ:η ratio −0.5 to −1 (Γ up, η down).
  - VSV fault: 1–7%. VBV fault: 1–19%.
  - η adjustment = magnitude/√(1+ratio²); Γ adjustment = η adjustment × ratio.
- In C-MAPSS, which has a fan-speed controller plus limit regulators on N2, EPR, HPT-exit temperature and Ps30, health-parameter changes show up as shifts in T48 (EGT), Ps30, N2, the fuel-to-Ps30 ratio and so on, and as reductions in stall margin. C-MAPSS response surfaces show EGT and HPC stall margin varying with HPC efficiency and flow loss. [TRANSFER] — [Saxena et al. 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf)
- Which channels carry the signature depends on the fighter engine's control loop. The F100-PW-229 DEEC "controls fuel flow, fan speed, engine pressure, core compressor speed, Fan Turbine Inlet Temperature (FTIT), nozzle position", with a hydromechanical SEC as backup. A deterioration fault is therefore partly absorbed by actuator moves (fuel flow, nozzle area A8, variable vanes), not only by sensed temperatures. [DIRECT] — [USAF AIB F-16CM 92-3881, 3 Dec 2025, p. 9](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf)
- Observability depends on operating point (real-engine seeded faults). In NASA VIPR ground tests on a C-17's F117 engines, mis-scheduled 14th-stage and station-2.5 bleed valves were detected and isolated at steady state but misclassified during transients. The detection statistic "dropped below the threshold" at low power settings even though the fault was still present. The model also needed re-trimming to match the real engine. [TRANSFER: military transport turbofan (PW2040-family); a real-engine result that applies directly to fighter EHM realism] — [Rinehart & Simon, NASA/TM-2015-218448](https://ntrs.nasa.gov/api/citations/20150000899/downloads/20150000899.pdf). Fault injection used hardware that overrides the engine controller's bleed-valve command for "progressive off-schedule operation" — [Gorospe, Simon & Goebel, PHM 2015](https://papers.phmsociety.org/index.php/phmconf/article/view/2546)
- Architecture: on-board logic detects larger abrupt faults, while ground-based snapshot trending detects smaller incipient faults. Fleet build tolerances and the spread of deterioration levels force wider on-board thresholds. [TRANSFER: NASA commercial-engine architecture] — [Simon, NASA/TM-2010-216358](https://ntrs.nasa.gov/api/citations/20100024368/downloads/20100024368.pdf)

**1d. Military-specific transient faults: stall/stagnation, VSV/RCVV mis-scheduling, AB, fuel control, nozzle/liner**
- F100 non-recoverable stall caused by RCVV mis-scheduling (altitude-test data) [DIRECT] — [Lee, NASA TM-81759, 1981](https://ntrs.nasa.gov/api/citations/19810016549/downloads/19810016549.pdf):
  - Conditions: F100(3) at simulated Mach 1.2 and 3,000 m. A switching delay put the RCVVs off-schedule during a rapid deceleration, lowering the HPC stall line.
  - Core speed fell from 12,790 to 10,800 rpm at stall onset.
  - Rotating stall developed in the fan and HPC at 66 Hz.
  - FTIT had been falling, then rose toward its limit after the stall. "Increasing FTIT occurring with decreasing core compressor rotational speed is a trend exhibited by other F100 engines during nonrecoverable stall."
  - Timeline: throttle trip at 33.841 s → idle at 34.215 s → stall at 35.135 s → FTIT rise at 35.214 s → RCVV back on schedule at 35.755 s (stall persisted) → shutdown at 37.876 s.
  - The disturbance was first sensed at fan discharge and reached the compressor exit and inlet within about 25–30 ms. Transducers had 500 Hz response.
- F100-PW-229 Thunderbird loss, 2025 [DIRECT] — [AIB F-16CM 92-3881](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf):
  - Mechanism: three "turned" 4th/5th-stage variable vanes (the linkage arm hook lost flush contact, "claw spread") created irregular wakes, causing high-cycle fatigue and separation of one 5th-stage and one 6th-stage blade. These stages cannot be fully borescope-inspected without engine removal.
  - The ECSMU recorded an RPM decrease with an FTIT rise, two engine-stall maintenance fault list (MFL) codes 2 s later, and about 10 s later an afterburner-failure MFL plus a thrust-low MFL.
  - Selecting SEC about 1 min 50 s later raised fuel flow, causing flameout and spool-down. Main and standby generators dropped offline and the EPU started.
  - The relight took about 20 s, but the engine would not respond above idle. The pilot ejected 4 min 21 s after the stall.
  - Engine usage: 334 total accumulated cycles (TAC) since overhaul; 12,251 TAC lifetime; about 4,940 h in-flight time at the last 50-h inspection; core module at 4,128 TAC with 1,634 TAC left to its depot interval.
- Afterburner-induced stalls on early F100s [DIRECT; secondary source] — [Wikipedia: Pratt & Whitney F100](https://en.wikipedia.org/wiki/Pratt_%26_Whitney_F100):
  - Stagnation stalls "usually occurred at high Mach and high altitude" and "could seriously damage the turbine".
  - They "could be caused by failure of the afterburner to start or by extinguishing after start", when "large jets of jet fuel were lit by the engine exhaust resulting in high pressure waves causing the engine to stall".
  - Fixes: the proximate splitter on the -200 and the DEEC on the -220, which "eliminates almost all stall-stagnations and augmentor instability issues".
  - The F100 "was found to be prone to compressor stalls and 'rollbacks'" (thrust spontaneously falling to idle) — [Wikipedia: F-16](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon)
- Fuel-control assembly fault, F110-GE-100C, Joint Base Andrews 2017 [DIRECT; press summary of the AIB] — [The Defense Post, 27 Oct 2017](https://thedefensepost.com/2017/10/27/improper-engine-control-assembly-caused-april-f-16c-crash/amp/):
  - The main engine control (MEC) differential-pressure pilot valve was assembled without its retaining ring and anti-rotation pin, so it "meter[ed] abnormally high fuel flow".
  - Effects: uncommanded acceleration, overspeed, overtemperature, fire and engine failure on the first flight after installation.
  - The overhauled MEC had failed performance tests twice before passing a static stand run.
- Nozzle-cooling and liner failure, F110-GE-129, Misawa 2018 [DIRECT] — [AIB F-16CM 92-3883 narrative](https://www.pacaf.af.mil/Portals/6/180220-PACAF-MisawaAB-Japan-F-16-AIB%20NARRATIVE%20REPORT.pdf):
  - An obsolete turbine-frame forward fairing installed in 2012 with mismatched brackets wore and fractured during an afterburner takeoff in 2018.
  - The fragment "blocked essential cooling air to the exhaust nozzle liner", heat burned through the exhaust duct, and an uncontained fire followed. Airspeed and climb-rate decayed; the pilot jettisoned tanks and landed.
  - Fleet history: fairings "cracking after … approximately 700 to 900 hours". A borescope inspection at 373 h on the fairing found nothing. Exhaust nozzle inspection is mandated every 800 EFH.
- Fan-blade migration from a maintenance omission, F100-PW-220, Holloman 2019 [DIRECT] — [AIB F-16C 90-0755](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf):
  - The 1st-stage rear air seal was not installed at depot (Sept 2016). 2nd-stage fan blades migrated 0.4–1.0 in forward over 591 h of engine operating time and were then liberated.
  - Effects: thrust loss with "near simultaneous" fire, overheat and engine lights; an uncontained fire fed by a perforated fuel tank.
- FOD and bird ingestion as shock events [DIRECT]:
  - Waterfowl ingestion just after takeoff caused "serious engine stalls"; the pilot jettisoned tanks and made a precautionary flameout landing (engine damage $1.27M) — [AIB F-16C Eielson, 28 May 2024](https://www.afjag.af.mil/LinkClick.aspx?fileticket=uW5wk5V_KDw%3d&portalid=77)
  - T-38C: a bird shattered the canopy and both J85s ingested canopy debris; one engine stopped and the other gave insufficient thrust — [AIB T-38C Columbus, 7 Nov 2022](https://www.afjag.af.mil/Portals/77/AIB-Reports/2022/7NOV22%20AETC%20T-38C%20COLUMBUS%20AFB%20MS%20AIB%20Report.pdf)
- Generic stall phenomenology [TRANSFER/secondary] — [Wikipedia: Compressor stall](https://en.wikipedia.org/wiki/Compressor_stall):
  - Rotating-stall cells travel at about 50–70% of rotor speed (part-span) or 20–40% (full-span).
  - Surge symptoms: bangs, flames, EGT rise, rotor-speed change, thrust loss.
  - Surge-margin erosion: FOD and erosion lower the surge line; dirt and wear raise the operating line.
  - Gun-gas ingestion (A-10, MiG-27) and yaw-induced TF30 stalls are noted.
- Start faults: a "hot start" comes from fuel being introduced before the HP shaft has enough speed for airflow, so temperature exceeds limits; FADEC can prevent it [TRANSFER/secondary; hung-start definition not found] — [Wikipedia: Hot start](https://en.wikipedia.org/wiki/Hot_start)

**1e. Hot-section usage damage and cycle counting**
- In USAF fighter engines, life is tracked in TAC (total accumulated cycles). The F100-PW-229 core-module depot interval inferred from the Thunderbird AIB is about 5,762 TAC (4,128 + 1,634). [DIRECT] — [AIB F-16CM 92-3881](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf)
- Informal practitioner account: TAC is "a complex calculation of engine RPM/Throttle usage". A 6 h ferry flight accrues 2–3 TAC, while a 1 h air-to-air sortie accrues 10–15 TAC. Formulas are in technical orders, not public. [DIRECT, but informal forum post; low confidence] — [f-16.net forum, That_Engine_Guy, 2009](https://www.f-16.net/forum/viewtopic.php?p=144239)
- Creep is tracked through time at temperature, using the Larson–Miller parameter LMP = T·(C + log t), with C ≈ 20–22 for metals (T in °R, t in h) — [Wikipedia: Larson–Miller relation](https://en.wikipedia.org/wiki/Larson%E2%80%93Miller_relation). LCF and TMF follow Coffin–Manson, Δε/2 = εf′(2N)^c + σf′(2N)^b/E, with c ≈ −0.5 to −0.7 — [Wikipedia: Low-cycle fatigue](https://en.wikipedia.org/wiki/Low-cycle_fatigue). [TRANSFER: generic material laws]
- Usage monitoring must be re-assessed at least every 5 years, because a change in usage severity can push life limits past safe values or retire parts early [DIRECT: Canadian military airworthiness] — [Canada TAA Advisory 2016-02](https://www.canada.ca/en/department-national-defence/services/military-airworthiness/technical-airworthiness-authority-overview/technical-airworthiness-regulatory-documents/technical-airworthiness-authority-advisories/2016-02.html). The F404's IECMS "monitors for critical malfunctions and keeps track of parts lifetimes" [DIRECT; secondary] — [Wikipedia: GE F404](https://en.wikipedia.org/wiki/General_Electric_F404)
- For a helicopter engine fleet (Lynx Gem), assumed exchange rates turned out conservative by "a factor of up to 2" once actual cycles were monitored [TRANSFER: naval helicopter turboshaft; shows usage variability at fleet level] — [Leenaarts & ten Have, NLR](https://dspace-erf.nlr.nl/bitstreams/d618a6af-2e4c-4fb3-93ee-71d00eb925c7/download)

### Inferences
- 12,251 TAC over about 4,940 engine flight hours gives roughly **2.5 TAC per EFH** for an F100-PW-229 in Thunderbird and earlier operational use. This sits between the forum's ferry rate (about 0.4 TAC/h) and air-combat rate (10–15 TAC/h). It is a usable calibration anchor for a TAC counter driven by simulated throttle and N2 histories. Caveat: in-flight time is not the same as operating time, and TAC accrued in ground runs is unknown.
- Under a fan-speed or EPR-scheduled DEEC/FADEC, gradual hot-section deterioration should appear mainly as rising FTIT/T5 and fuel flow at a given N1 or thrust, with N2 shifting. Nozzle area may also move, because fighter controls use A8 to hold fan operating point. Once FTIT reaches its limit at maximum power, the signature turns into lost thrust, slower acceleration and reduced margin, not further temperature rise. [ASSUMPTION; validate by running a closed-loop low-bypass engine model with the platform's control laws. This is a cross-link to the engine-data researcher.]
- Applying commercial deterioration rates (Sallee, C-MAPSS, ProDiMES) to a fighter engine needs a severity multiplier. The evidence points the same way: military engines are more sensitive to tip clearance, fighters spend more time at transients, and actual F404 usage was severe enough to cut life almost 50%. The appropriate multiplier is not public.
- Many fighter engine losses in the AIB sample were latent mechanical or assembly defects that gave no gas-path precursor before the event: missing air seal, turned vanes, wrong fairing part, MEC assembly. A realistic generator should therefore include "silent until abrupt" fault classes with hazard rates, not only smoothly growing gas-path drifts.

### Gaps
- No public fighter-engine (F404/F110/F100/RM12/AL-31FP) influence-coefficient matrix or deterioration rate per 1,000 EFH was found. Military OEM data and DTIC reports (for example RTO-TR-028) were inaccessible.
- No public data were found on afterburner no-light or blowout rates, nozzle-actuator fault signatures (A8 command versus feedback), igniter faults, or hung-start traces for fighter engines.
- The TAC formula (TO 00-20-5-1-1) and the F404 IECMS/EMU LCF counting algorithms are not public.
- No aero-engine compressor-wash recovery magnitudes (EGT °C recovered) were retrieved before the search budget ran out.

---

## 2. Engine mechanical faults: bearings, oil system, gearbox, imbalance, blade loss

### Takeaway
The best fighter-specific evidence is Indian: Su-30MKI AL-31FP malfunctions were dominated by bearing rolling-contact fatigue that produced metal chips in the oil. A bearing fault should therefore be modelled as a two-phase process. First a latent initiation period (hundreds of flight hours), then a propagation period in which debris generation, vibration and eventually oil-pressure anomalies grow, observed through chip detectors or oil-debris monitors and vibration channels. Public quantitative spall-growth curves for fighter engine bearings were not found. Rig data (FEMTO) shows that run-to-failure trajectories vary widely from unit to unit.

### Cited Findings
- Su-30MKI AL-31FP engine malfunctions, from Defence Minister Parrikar's March 2015 statement to Parliament as reported in 2026 [DIRECT, Indian fleet; secondary press reporting of an official statement] — [The Wire, Rahul Bedi, 15 Mar 2026](https://thewire.in/security/assam-su30mki-crash-challenge-adapting-fighter-demanding-conditions):
  - 35 AL-31FP engines had technical problems between January 2013 and December 2014.
  - Of 69 engine malfunctions investigated since 2012: 33 were metal chips in the oil system, 11 abnormal vibrations, 8 low oil pressure, and 17 not publicly explained.
  - Mechanism as stated: "metal fatigue in the power pack's bearings … caused them to chip or fragment", contaminating the oil.
  - Fixes: nine OEM improvements (lubrication, bearing fits, oil quality) applied to 25 new engines. "Earlier engine malfunctions typically tended to occur after around 500 flying hours, the improvements extended this interval to some 900 hours."
  - Fleet readiness was about 55% (~110 aircraft).
  - Unverified "online sources" cite a marketed MTBO of about 1,000 h, a total life of about 3,000 h, and early overhauls at 300–500 h.
- Tejas Mk1 loss near Jaisalmer, 12 March 2024 [DIRECT; unofficial and conflicting accounts]:
  - Officials said engine seizure was the likely cause, "caused by an oil pump malfunction"; the court of inquiry was not complete — [Indian Defence News, Jul 2024](https://www.indiandefensenews.in/2024/07/engine-seizure-led-to-iafs-first-tejas.html)
  - Anonymous sources instead said "inadequate oil levels, rather than a pump failure" or an undetected leak, and that the pilot noted "unusual engine noise" after takeoff — [IDRW, Mar 2025](https://idrw.org/scoop-iaf-tejas-crash-oil-level-issue-points-to-potential-oversight-lapses/)
- Oil-debris monitoring on fighter engines. GasTOPS MetalSCAN is installed on the F-22 (F119; originally developed for it), the F-35 (F135, and the 29,000 HP LiftSystem gearbox) and the Eurofighter (EJ200). It detects ferrous and non-ferrous particles and gives damage severity, progression and RUL. Particle-size thresholds and alarm logic are proprietary. A customer reports that it "caught over 30" failures that would have been in-flight shutdowns. [DIRECT: platform list; vendor claims] — [GasTOPS MetalSCAN product page](https://www.gastops.com/products/metalscan/)
- Bearing run-to-failure rig (PRONOSTIA/FEMTO, IEEE PHM 2012) [TRANSFER: small ball bearings under accelerated radial load; shows variability and the limits of textbook signatures, not absolute times] — [IEEE PHM 2012 Challenge details](https://github.com/wkzs111/phm-ieee-2012-data-challenge-dataset/raw/master/IEEEPHM2012-Challenge-Details.pdf):
  - Tests ran under 2,000 rpm with radial load up to the 4,000 N dynamic load rating, and stopped when vibration exceeded 20 g.
  - Lives ranged from 1 to 7 h under nominally identical conditions.
  - The bearings degraded naturally, with ball, ring and cage defects together. "Frequency signatures are difficult to obtain", and L10 life did not match the experiments.
  - Sampling: vibration at 25.6 kHz, recorded for 0.1 s every 10 s.
- Lube-system degradation signature (illustrative): a 1% lube-system fault raises hot-oil temperature by 0.6% and low oil temperature by 0.5%. Normal-operation residuals on an APU had means of 8.6 °C (HOT) and 12.1 °C (LOT), with SDs of 2.3 °C and 2.8 °C. [TRANSFER: Honeywell APU] — [US 7,062,370 B2](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7062370)
- Blade loss and imbalance: vibration helps tell FOD and blade damage ("Yes") from fouling or nozzle erosion ("No") [TRANSFER] — [Urban matrix, ISABE slides](https://conference.isabe.org/content/scnotes/ivan/GT%20diagnostics3_4.pdf). Fan-blade liberation in the Holloman F-16 gave thrust loss, fire and overheat lights, and spool-down within seconds [DIRECT] — [AIB F-16C 90-0755](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf)
- N-CMAPSS authors flag the lack of accelerometers and oil-debris monitoring in their simulated engine as a fidelity gap [TRANSFER] — [Arias Chao et al. 2021, Data 6(1):5](https://www.mdpi.com/2306-5729/6/1/5)

### Inferences
- For Su-30 or AL-31FP-like engines, a bearing-fatigue hazard with initiation around 500 FH before modification and around 900 FH after modification is a rough DIRECT calibration anchor. It suggests a Weibull initiation distribution with characteristic life of a few hundred to about 1,000 FH and wear-out shape (β > 1). The fleet split of about 48% chips, 16% vibration and 12% low oil pressure (of 69) can weight the first observable symptom in the generator. [ASSUMPTION on distribution form; validate against IAF or HAL engine removal records, cross-link to maintenance-records researcher]
- Debris, vibration and oil-pressure symptoms should be causally ordered: debris generation first, vibration rising with spall size, and oil pressure or temperature anomalies late (filter loading, pump damage) or caused by a separate oil-system fault. The Indian statistics show these symptoms arriving as separate "first detected" events, so the BIT/EHM channels should be modelled as separate detectors with different sensitivities.

### Gaps
- No public spall-propagation rates (mm² per hour), oil-debris particle-count or mass-versus-time curves, or 1/rev vibration amplitude data for fighter engine bearings were retrieved. NASA (Dempsey) oil-debris and gear studies and AFRL spall-propagation work exist but could not be located without search.
- No accessory gearbox (AGB) fault data were found. A 2011 F110 AGB oil-supply-line blockage AIB was seen only in a search snippet.
- No fighter oil-consumption trend data or chip-detector false-alarm rates were found.

---

## 3. Airframe and utility systems: hydraulics, fuel, electrical, ECS, landing gear/brakes/tyres, flight-control actuators, air data, avionics/wiring/NFF, structure

### Takeaway
USAF accident reports give unusually concrete physical fault chains for hydraulics, landing gear, electrical power and air data, with pressures, leak rates, spring forces and timelines. Many are leaks or degraded mechanical margins that stay latent until an operating condition exposes them: cold weather, emergency gear extension, or high hydraulic temperature. Many are also introduced by maintenance. Avionics and wiring faults are dominated by intermittency and NFF (30–60% NFF on removals). Quantitative public data for ECS, fuel pumps, fuel-quantity probes, tyres and brakes on fighters were not found.

### Cited Findings
**Hydraulics**
- F-16C, March ARB 2019: inlet check valves in the right flaperon integrated servo actuator (ISA) were installed improperly at overhaul [DIRECT] — [AIB F-16C 88-0477](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/F-16%2016%20May%2019%20March%20ARB%20ACC.pdf):
  - The valve leaked about 31 ml/min at 1,000 psi on the test bench. Normal system pressure is 3,100 ± 50 psi.
  - System A (≈5 gal) pressure first fluctuated between 1,500 and 2,000 psi, then between 1,000 and 2,000 psi. System B (≈7 gal) then went low.
  - Running the EPU did not raise system A. Hydraulically actuated flight controls degraded and the pilot ejected.
- F-15D, Kingsley 2023: a crack near a weld in the fuel–oil heat exchanger (FOHE) on the non-reservoir-level-sensing (non-RLS) circuit [DIRECT] — [AIB F-15D 84-0046](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/15%20MAY%2023%20AIB%20Kingsley%20ANGB%20F-15D%20Final%20Amended%20Report_Redacted.pdf):
  - A leak in the non-RLS circuit "cannot be isolated and will result in Total Utility Hydraulic System failure". Above 225 °F the thermal valve routes all fluid through the FOHE, so the leak rate rises.
  - Cockpit cues: hydraulic caution, Utility B BIT light, and a right-engine inlet light (circuit B drives the right inlet ramp). The pressure gauge initially read "just below 3,000 psi".
  - Normal braking was lost after landing.
  - Maintenance had serviced the system for a suspected leak and released the aircraft under an exceptional release.
- B-2A, Whiteman 2021 [DIRECT: military bomber; same component physics as fighters]:
  - Fatigue of a CryoFit coupling drove "a rapid loss of hydraulic fluid in the #1 and #4 hydraulic systems" (four independent 4,000 psi systems).
  - Gear lock-link springs had relaxed: the inboard spring gave 88.9 lbf against a 100 ± 5 lbf design. The gear collapsed on landing even though emergency extension had indicated down-and-locked. — [AIB B-2A 89-0129, 14 Sep 2021](https://www.afjag.af.mil/Portals/77/AIB-Reports/2021/14SEP21%20B-2%20AIB%20Report.pdf)
  - In 2022 another B-2 CryoFit coupling failure (truck position sequence valve) led to a gear collapse and fire costing more than $300M — [AIB B-2 90-0041, 10 Dec 2022](https://www.afjag.af.mil/Portals/77/AIB-Reports/2022/10Dec22%20AFGSC%20Whiteman%20B-2%20AIB.pdf)
- F-35A, Eielson 2025 [DIRECT] — [AIB F-35A 19-5535](https://www.afjag.af.mil/LinkClick.aspx?fileticket=Zigjw6p7hiw%3d&portalid=77):
  - Hydraulic fluid was serviced from a barrel holding about 33% water, with particulates above 1,024 ppm (more than twice the allowable limit).
  - The water froze in the nose and main gear struts after about 40 min at roughly 0 °F.
  - The nose gear did not retract and was canted 17°. Main-gear struts did not fully extend, so all valid weight-on-wheels (WoW) sensors declared "on ground" and the FCS switched to ground control law while airborne.
  - A similar event occurred 9 days later. A post-test after 12 h below 15 °F reproduced failure to extend.
- Pump wear and accumulator precharge parametrisation (industrial test rig) [TRANSFER: shows how to discretise severity levels, not aircraft magnitudes] — [UCI dataset 447 "Condition monitoring of hydraulic systems"](https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems):
  - Internal pump leakage: classes 0, 1, 2.
  - Accumulator pressure: 130, 115, 100, 90 bar (90 = "close to total failure").
  - Valve condition: 100, 90, 80, 73%. Cooler efficiency: 100, 20, 3%.
  - Sensors: pressure at 100 Hz, flow at 10 Hz, temperature and vibration at 1 Hz; 60 s cycles.

**Landing gear, brakes, steering**
- F-16CM, Kunsan 2019: the right main-gear downlock actuator failed and the gear collapsed on touchdown. This is "a known issue for F-16C/D blocks 40/42/50/52", addressed by TCTO 1F-16-2855. [DIRECT] — [AIB F-16CM 90-0714](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/191202-PACAF-KunsanAB-Korea-F-16%20AIB%20NARRATIVE%20REPORT.pdf)
- F-15 emergency braking: anti-skid is not available on the emergency brake system, and using it above 70 kt "increases the possibility of blown tires". So a hydraulic fault changes the tyre-failure risk during landing rollout. [DIRECT] — [AIB F-15D 84-0046](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/15%20MAY%2023%20AIB%20Kingsley%20ANGB%20F-15D%20Final%20Amended%20Report_Redacted.pdf)

**Flight-control and actuator mechanics**
- Archard-type screw/nut wear rates from the Alaska 261 MD-83 trim jackscrew [TRANSFER: transport-aircraft trim actuator; same wear physics as fighter screw actuators] — [NTSB AAR-02/01](https://www.ntsb.gov/investigations/AccidentReports/Reports/AAR0201.pdf):
  - Expected wear rate is about 0.001 in per 1,000 FH. Fleet averages were 0.0011 (DC-9, 1,329 h lubrication interval) and 0.0013 in/1,000 h (MD-80, 804 h interval).
  - A premature DC-9 case reached 0.0057. The accident nut wore at 0.012 in/1,000 FH with inadequate lubrication.
  - End-play limits are 0.003–0.040 in. The maximum allowed wear is about 22% of thread thickness; about 90% had worn away at failure.
- F-16CJ, El Paso 2016 [DIRECT] — [AIB F-16CJ 92-3890](https://www.afjag.af.mil/Portals/77/AIB-Reports/2016/160602-ACC-Nellis-F-16CJ-AIB%20Report.pdf):
  - The throttle trigger stuck intermittently. Causes: a bushing "damaged and worn due to throttle trigger clevis pin misalignment", metallic debris, and non-TO lubricant.
  - With the trigger stuck, the throttle could be rotated past the cutoff stop, shutting down the engine. This is an intermittent friction or jam fault in a pilot interface.
- F-16 FLCS is quadruplex fly-by-wire: losing one channel leaves a triplex system with "graceful degradation". It has been digital since Block 40 and has no mechanical backup. [DIRECT; secondary] — [Wikipedia: F-16](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon)

**Electrical**
- F-16C, Osan/Kunsan, 6 May 2023 [DIRECT] — [AIB F-16C 88-0549](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/6May23%20PACAF%20F-16C%20AIB%20Report.pdf):
  - A partial electrical power loss about 11 s after takeoff made the embedded GPS/INS (EGI) data invalid.
  - The aircraft reported an AGCAS failure "but … did not report a failure of the navigation or attitude equipment". The HUD pitch ladder disappeared 30–45 s later.
  - The primary attitude indication "continued to respond … but displayed unreliable and inaccurate data without failure indications". The root cause of the power disruption was inconclusive.
  - F-16 power architecture: main generator, standby generator, and emergency generator (EPU), which also supplies emergency hydraulic pressure to system A.
- Generator loss from engine spool-down (cross-system coupling) [DIRECT]:
  - Holloman 2019: main and standby generators "fell offline" during spool-down, causing a momentary power disruption before the emergency generator came online, and the radio call went unheard — [AIB F-16C 90-0755](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf)
  - The same sequence appears in the Thunderbird 2025 report — [AIB F-16CM 92-3881](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf)
- Battery capacity fade: NASA 18650 Li-ion ageing tests ended at end-of-life defined as 30% fade in rated capacity (2 Ah → 1.4 Ah) [TRANSFER: commercial cells; aircraft batteries differ in chemistry and BMS] — [NASA Li-ion battery ageing dataset](https://data.nasa.gov/dataset/li-ion-battery-aging-datasets)

**Air data**
- F-35A, Hill AFB 2022 [DIRECT] — [AIB F-35A 15-5197](https://www.afjag.af.mil/Portals/77/AIB-Reports/2022/19OCT22%20ACC%20F-35A%20388th%20FW%20Hill%20AFB%20AIB%20Report.pdf):
  - Air data system: left and right multi-function probes plus left and right flush-port modules.
  - Wake turbulence made the air data application exclude the left probe, giving an AIR DATA DEGD caution at 18:08:29.
  - The right probe intermittently read "outside input limits" several times between 18:08:27 and 18:08:30, with no caution.
  - The ADA's AoA differed from actual AoA by more than 40°, and the model-based control law commanded wrongly. The aircraft departed and the pilot ejected at 18:08:36.
- B-2A, Andersen 2008 [DIRECT: military; secondary source] — [Wikipedia: 2008 Andersen B-2 accident](https://en.wikipedia.org/wiki/2008_Andersen_Air_Force_Base_B-2_accident):
  - Moisture from heavy rain caused 3 air-data pressure transducers to give erroneous AoA and airspeed (a common-mode fault).
  - The aircraft rotated 12 kt slow. After the control law switched, an uncommanded 30° pitch-up at 1.6 g led to a stall.
- AoA vane bias, Lion Air 610 [TRANSFER: B737 MAX; the most precisely documented AoA-bias case] — [KNKT final report KNKT.18.10.35.04](https://www.aaiu.ie/sites/default/files/FRA/2018%20-%20035%20-%20PK-LQP%20Final%20Report.pdf):
  - A replacement left AoA sensor had a 21° bias "undetected during the installation test".
  - The left–right AoA difference was about 21° from takeoff roll to end of recording.
  - Effects: IAS/ALT DISAGREE, a continuous stick shaker, flight-director split (1° down versus 13° up), and repetitive automatic trim inputs.

**Avionics, wiring, intermittents, NFF**
- ADIRU data spikes, Qantas 72 [TRANSFER: A330; avionics data-path fault, which transfers to any digital air-data/INS bus] — [ATSB AO-2008-070](https://www.atsb.gov.au/investigations/ao-2008-070):
  - One ADIRU output "intermittent, incorrect values (spikes) on all flight parameters". Each spike probably came from combining one parameter's data value with another parameter's label.
  - The FCPC algorithm "could not manage a scenario where there were multiple spikes in AOA from one ADIRU that were 1.2 seconds apart".
  - Rarity: "only three known occasions of the failure mode in over 128 million hours of unit operation".
  - Example spike: altitude 37,012 relabelled as AoA 50.625° — [Wikipedia: Qantas Flight 72](https://en.wikipedia.org/wiki/Qantas_Flight_72)
- NFF rates and causes [TRANSFER mixed with DIRECT military figures] — [Khan, Phillips, Jennions & Hockley 2014, RESS 123:183](https://pure.coventry.ac.uk/ws/files/3999358/J1_R.PDF):
  - Avionics engineers estimate NFF rates of 30–50%.
  - Williams 1998: NFF makes up more than 85% of observed avionics field failures and more than 90% of maintenance costs.
  - British Airways 1992: 14% of removals overall were NFF, and some avionics reached 30%.
  - RAF 1998: 10% of reported faults were NFF.
  - NAVAIR spent $94M on NFF removals tied to unconfirmed wiring faults. Some Naval avionics NFF rates reached 60%.
  - USAF F-16 MLPRF unit: more than $2M per year in depot NFF costs.
  - Listed causes: intermittent connections (connectors, harnesses), intermittent faults (solder joints, PCBs), inadequate test coverage across maintenance levels, fault-code interpretation, BITE coverage.
  - NFF costs DoD more than US$2B per year — [Wikipedia: No fault found](https://en.wikipedia.org/wiki/No_fault_found)

**Structure (usage-driven fatigue)**
- USAF ASIP guidance [DIRECT: USAF guidance] — [MIL-HDBK-1530B (2002), §5.4.4–5.4.5](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL_HDBK_1530B.1890.pdf):
  - Loads/environment spectra survey: "100-percent of the operational air vehicle" instrumented for velocity, accelerations, altitude, fuel usage, temperature and strains, with 10–20% of the data used to build the baseline operational spectrum.
  - Individual aircraft tracking: 100% of the fleet instrumented, with "90- to 95-percent" data capture "considered reasonable".
  - Major components (wings, stabilisers, landing gear) are serialised, and inspection and repair intervals are adjusted per airframe from predicted crack growth.
- Crack growth law: da/dN = C(ΔK)^m, with m typically 2–4. Variable-amplitude loading is reduced by rainflow counting and summed with Miner's rule Σnᵢ/Nᵢ = C (usually 1), which ignores sequence effects and scatter. [TRANSFER: generic] — [Wikipedia: Paris' law](https://en.wikipedia.org/wiki/Paris%27_law); [Wikipedia: Fatigue (material)](https://en.wikipedia.org/wiki/Fatigue_(material))

### Inferences
- Hydraulic faults should be modelled as fluid-volume and leak-conductance states, plus logic states for reservoir-level sensing and isolation, not as pressure noise. Real traces show oscillating or sagging pressure (1,000–2,000 psi bands) before total loss, and pressure staying near nominal while an isolable leak drains a circuit. Consumers (brakes, inlet ramps, gear, flight controls) degrade according to which circuit is isolated.
- Temperature and environment matter as triggers. The FOHE leak rate rises above 225 °F fluid temperature, and water-contaminated fluid only freezes in cold soak. The generator needs environment-conditioned failure manifestation, which is relevant to Indian high-altitude and winter bases (Leh, Srinagar) versus hot desert bases (Jaisalmer).
- Several faults (EGI invalid without flags, right air-data probe out of limits without caution, gear "down and locked" while the springs were weak) produced no BIT annunciation. The simulated BIT layer must have imperfect coverage.

### Gaps
- No public fighter data were found for:
  - hydraulic pump case-drain flow trends, pressure ripple, or pump temperature;
  - accumulator precharge loss rates;
  - fuel boost/transfer pump degradation, filter ΔP trends, or capacitance fuel-probe faults and imbalance;
  - IDG/VSCF/generator degradation;
  - ECS heat-exchanger fouling or valve sticking;
  - tyre wear per landing, brake wear-pin rates, or shock-strut servicing loss.
- Treat these as [ASSUMPTION] in the generator until the maintenance-records researcher supplies data.
- No fighter counting-accelerometer exceedance spectra or fatigue-life-expended-per-hour figures were retrieved (for example RAAF/DSTO F/A-18, or IAF).

---

## 4. Sensor faults, BIT and redundancy management

### Takeaway
Sensor faults are a separate layer from physical degradation: the plant is healthy but the measurement is wrong. The fault classes to support, all documented, are bias/offset, drift, scale-factor error, stuck/frozen, intermittent spikes or relabelled data, noise increase, and open/short (fail-low or fail-high). Redundancy management uses voting, averaging, exclusion and short "memorisation" windows. Documented fighter events show the realistic failure points: common-mode faults (moisture, wake), intermittent faults timed against filter windows, and exclusions that leave a single unmonitored source.

### Cited Findings
- Gas-path sensor fault definitions with magnitudes in units of measurement-noise σ [TRANSFER: commercial turbofan benchmark] — [ProDiMES User's Guide, Table 1](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf):
  - Bias faults of ±1–10σ on Nf, Nc, P24, Ps30, T24, T30, T48, Wf, P2 and T2 (Pamb ±1–19σ).
  - σ values as a percentage of reading, with takeoff/cruise values:
    - Nf: 0.25% (5.59/4.67 rpm)
    - Nc: 0.17% (15.04/13.22 rpm)
    - Ps30: 0.20% (0.896/0.224 psia)
    - T30: 0.16% (2.45/1.92 °R)
    - T48: 0.50% (10.07/7.48 °R)
    - Wf: 0.60% (0.035/0.0069 pps)
    - P2: 0.15%
    - T2: 0.16%
  - "Faults in certain control feedback sensors will also result in actuator misscheduling": VSV/VBV are scheduled on corrected core speed, so Nf, Nc and T2 sensor faults move the actual vanes.
- Benchmark detection targets [TRANSFER] — [Simon, Borguet, Léonard & Zhang, NASA/TM-2013-218082](https://ntrs.nasa.gov/api/citations/20140003941/downloads/20140003941.pdf):
  - Target false-alarm rate of no more than one false alarm per 1,000 flights.
  - Abrupt faults were easier to detect than rapid (ramping) faults, and detection improved with magnitude.
  - Detection latency of a few flights lowered true-positive rates.
- Simulator sensor imperfection and failure primitives [TRANSFER: simulator framework; directly reusable] — [JSBSim FGSensor](https://jsbsim-team.github.io/jsbsim/classJSBSim_1_1FGSensor.html):
  - Imperfections: lag, noise (percent or absolute, uniform or Gaussian), quantisation (bits, min/max), drift_rate, gain (scale factor), bias, frame delay.
  - Malfunctions: `fail_low` (output −∞), `fail_high` (+∞), `fail_stuck` (hold last value).
- Real-event sensor fault types:
  - Bias: Lion Air AoA 21° — [KNKT](https://www.aaiu.ie/sites/default/files/FRA/2018%20-%20035%20-%20PK-LQP%20Final%20Report.pdf) [TRANSFER]
  - Moisture-induced common-mode offset: B-2 — [Wikipedia](https://en.wikipedia.org/wiki/2008_Andersen_Air_Force_Base_B-2_accident) [DIRECT]
  - Intermittent spikes or relabelled words: QF72 — [ATSB](https://www.atsb.gov.au/investigations/ao-2008-070) [TRANSFER]
  - Intermittent out-of-limits readings after one probe is excluded: F-35 — [AIB F-35A 15-5197](https://www.afjag.af.mil/Portals/77/AIB-Reports/2022/19OCT22%20ACC%20F-35A%20388th%20FW%20Hill%20AFB%20AIB%20Report.pdf) [DIRECT]
  - Frozen or invalid data presented without a flag after a power loss: F-16 EGI — [AIB F-16C 88-0549](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/6May23%20PACAF%20F-16C%20AIB%20Report.pdf) [DIRECT]
  - Fighter records "unreliable and inaccurate data with multiple failure indications" during an engine stall: Kunsan 2024 — [AIB F-16C 89-2013](https://www.afjag.af.mil/LinkClick.aspx?fileticket=kRfx-BSk0rY%3d&portalid=77) [DIRECT]
- Redundancy-management behaviours:
  - A330 FCPCs used the average of AOA 1 and AOA 2 when consistent, and a memorised value for 1.2 s when one deviated [TRANSFER] — [Wikipedia QF72](https://en.wikipedia.org/wiki/Qantas_Flight_72); [ATSB](https://www.atsb.gov.au/investigations/ao-2008-070)
  - F-16 FLCS quadruplex degrading to triplex [DIRECT] — [Wikipedia F-16](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon)
  - F-35 ADA exclusion with a caution for one side but none for intermittent readings on the other [DIRECT] — [AIB F-35A 15-5197](https://www.afjag.af.mil/Portals/77/AIB-Reports/2022/19OCT22%20ACC%20F-35A%20388th%20FW%20Hill%20AFB%20AIB%20Report.pdf)
  - F-35 "all valid WoW sensors" voted "on ground" because a physical fault (ice) affected every strut [DIRECT] — [AIB F-35A 19-5535](https://www.afjag.af.mil/LinkClick.aspx?fileticket=Zigjw6p7hiw%3d&portalid=77)
- On-board engine monitoring logic uses persistence on residual statistics to filter spikes and suppresses detection for the first 40 s to avoid start transients [TRANSFER: NASA VIPR implementation] — [Rinehart & Simon 2015](https://ntrs.nasa.gov/api/citations/20150000899/downloads/20150000899.pdf)
- Fighter fault-code recording: the F-16 ECSMU stores Maintenance Fault List (MFL) codes with data markers, such as engine stall, AB failure and thrust low, and recovered about 23 min of ground and 28 min of flight data. Engine records (CEMS) were reviewed for 8 years in the Misawa investigation. [DIRECT] — [AIB F-16CM 92-3881](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf); [AIB F-16CM 92-3883](https://www.pacaf.af.mil/Portals/6/180220-PACAF-MisawaAB-Japan-F-16-AIB%20NARRATIVE%20REPORT.pdf)

### Inferences
- Sensor faults in Phalanx should be separate state machines: a per-channel set of {bias, drift rate, scale factor, noise multiplier, stuck flag, intermittent on/off rate, spike rate}, applied after the physical model and before redundancy management, BIT and recording. Control-feedback sensor faults must feed back into the plant through the controller (actuator mis-scheduling), as ProDiMES describes.
- BIT should be modelled with explicit coverage (the probability that a given fault mode raises a code), latency and persistence, and a false-alarm process. Planning anchors are about 1 false alarm per 1,000 flights for gas-path EHM [TRANSFER] and NFF shares of 30–60% for avionics removals [TRANSFER/DIRECT].

### Gaps
- No public specifications were found for F-16, Tejas or other fighter air-data or engine-sensor monitor thresholds, persistence times or voting algorithms. These are classified or proprietary; use generic mid-value-select plus persistence logic and tag it [ASSUMPTION].
- No public fighter sensor failure rates (λ per sensor type) were retrieved. MIL-HDBK-217-style rates were not accessed.

---

## 5. Degradation process models: stochastic and physics-of-failure forms, usage drivers, fleet variability, maintenance resets, imperfect repair

### Takeaway
The public engine benchmarks (C-MAPSS, N-CMAPSS, ProDiMES) all use the same structure:
- random initial manufacturing variation;
- slow "normal" deterioration;
- a stochastic onset of abnormal degradation, which in N-CMAPSS is triggered by accumulated usage energy against a unit-specific Gaussian threshold;
- a faster, roughly exponential abnormal phase;
- process noise standing in for between-flight maintenance.

Physics-of-failure laws (Paris, Coffin–Manson, Larson–Miller, Archard, Arrhenius, Miner) give the usage-to-damage drivers. Gamma and Wiener/inverse-Gaussian processes give monotone and non-monotone stochastic forms. Maintenance resets should be partial: the JT9D data show about 20% of TSFC deterioration recovered at a typical shop visit. Maintenance can also inject new faults, as documented in at least 7 military mishaps here.

### Cited Findings
- C-MAPSS damage model [TRANSFER] — [Saxena et al. 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf):
  - Wear w = A·e^{B(t)} is recast as health h(t) = 1 − d − exp(a·t^b), applied separately to efficiency and flow.
  - Parameters: initial e0, f0 ∈ [0.99, 1]; a ∈ [0.001, 0.003]; b ∈ [1.4, 1.6].
  - Health index = minimum of normalised margins (fan, LPC, HPC stall margin limit 15%; EGT margin limit about 2%).
  - Process noise is a mixture of two distributions. "Between-flight maintenance" is represented as process noise, so health is "not locally monotonic". One snapshot is taken per flight on the assumption that "sudden degradation during a flight is rather unlikely".
- N-CMAPSS, which ties fault onset to usage [TRANSFER] — [Arias Chao et al. 2021](https://www.mdpi.com/2306-5729/6/1/5):
  - Initial degradation is U(0, 0.01) per sub-component, giving a health index of 0.9–1.0 (about 10% engine-to-engine spread).
  - Normal degradation is linear with slope −0.001 per cycle.
  - Onset t_s is when the cumulative "excitation energy" E(t) = ∫P(t)dt exceeds a Gaussian-distributed component threshold, representing material variability.
  - Abnormal degradation: δa = 1 − exp(a·t^b) + δn(t_s) + ξ, with a ~ U(0.001, 0.003), b ~ U(1.4, 1.6), and ξ ~ N(0, c) where c = 0.001 for efficiency and 0.002 for flow.
  - Example onsets: unit 11 (long flights) at 19 cycles, unit 15 (medium) at 24, unit 14 (short) at 36.
  - Sensor noise is set for SNR 65 dB.
  - Stated limitation: "accelerated aging as compared to typical engines with full operative lifespans on the order of thousands of cycles", and only faults that can be represented as flow or efficiency changes.
- ProDiMES fleet variability has four parts: overall rate, per-module rate, flow-versus-efficiency ratio, and initial manufacturing variation. Faults are abrupt (step) or rapid (linear ramp over N flights, e.g. 25/50/75/100%), with one fault per engine. [TRANSFER] — [ProDiMES User's Guide](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf)
- Stochastic process forms [TRANSFER: mathematical]:
  - Gamma process: independent Γ(γl, λ) increments, mean γt/λ, variance γt/λ², suited to monotone wear and "deterioration modeling" — [Wikipedia: Gamma process](https://en.wikipedia.org/wiki/Gamma_process)
  - For a drifted Wiener process X = νt + σW, the first-passage time to level α is inverse Gaussian, IG(α/ν, (α/σ)²) — [Wikipedia: Inverse Gaussian distribution](https://en.wikipedia.org/wiki/Inverse_Gaussian_distribution)
- Physics-of-failure laws [TRANSFER: material laws]:
  - Paris: da/dN = C(ΔK)^m, m ≈ 2–4 — [Wikipedia](https://en.wikipedia.org/wiki/Paris%27_law)
  - Coffin–Manson, c ≈ −0.5 to −0.7 — [Wikipedia](https://en.wikipedia.org/wiki/Low-cycle_fatigue)
  - Larson–Miller, C ≈ 20–22 — [Wikipedia](https://en.wikipedia.org/wiki/Larson%E2%80%93Miller_relation)
  - Archard: Q = K·W·L/H, with K ≈ 10⁻⁸ for mild wear and 10⁻² for severe — [Wikipedia](https://en.wikipedia.org/wiki/Archard_equation)
  - Miner's rule with rainflow counting — [Wikipedia](https://en.wikipedia.org/wiki/Fatigue_(material))
  - Arrhenius, Coffin–Manson and Eyring time-to-failure forms are summarised in the C-MAPSS paper — [Saxena et al. 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf)
- Empirical wear-rate calibration of Archard behaviour: nominal 0.001 in/1,000 FH versus 0.012 in/1,000 FH with inadequate lubrication, a 12× rate change caused by a maintenance variable [TRANSFER] — [NTSB AAR-02/01](https://www.ntsb.gov/investigations/AccidentReports/Reports/AAR0201.pdf)
- Usage drivers:
  - TAC per sortie depends on throttle activity (2–3 TAC per 6 h ferry versus 10–15 per 1 h air combat) [DIRECT, informal] — [f-16.net](https://www.f-16.net/forum/viewtopic.php?p=144239)
  - F404 usage was more severe than forecast, cutting life almost 50% [DIRECT] — [Canada TAA 2016-02](https://www.canada.ca/en/department-national-defence/services/military-airworthiness/technical-airworthiness-authority-overview/technical-airworthiness-regulatory-documents/technical-airworthiness-authority-advisories/2016-02.html)
  - Structural tracking uses per-tail usage data [DIRECT] — [MIL-HDBK-1530B](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL_HDBK_1530B.1890.pdf)
  - Particle size and filtration govern fouling and erosion rates [TRANSFER] — [Kurz & Brun 2011](https://torroja.dmt.upm.es/congresos/asme_2011/data/pdfs/trk-19/GT2011-45012.pdf)
- Maintenance resets [TRANSFER: JT9D] — [Sallee 1978](https://ntrs.nasa.gov/api/citations/19800013837/downloads/19800013837.pdf):
  - A shop visit recovered 4.4% → 3.5% TSFC (about 0.9 points, roughly 20%), mostly through the HPT.
  - Cold-section refurbishment could add 1.9% recovery.
  - About 1.6% is non-recoverable.
  - Maintenance practice changes losses by ±13%.
  - Fouling is recoverable by washing; erosion and corrosion are not — [Tahan et al.](https://shura.shu.ac.uk/16176/8/Tsoutsanis-Performance-basedHealthMonitoring%28AM%29.pdf)
- Maintenance-induced and latent faults in military aircraft [DIRECT]:
  - Missing fan air seal at depot, failing after 591 h — [AIB 90-0755](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf)
  - MEC mis-assembly, failing on the first flight — [Defense Post](https://thedefensepost.com/2017/10/27/improper-engine-control-assembly-caused-april-f-16c-crash/amp/)
  - Mis-installed ISA check valves at overhaul — [AIB 88-0477](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/F-16%2016%20May%2019%20March%20ARB%20ACC.pdf)
  - Obsolete fairing installed in 2012, failing in 2018 — [AIB 92-3883](https://www.pacaf.af.mil/Portals/6/180220-PACAF-MisawaAB-Japan-F-16-AIB%20NARRATIVE%20REPORT.pdf)
  - Water-contaminated hydraulic servicing — [AIB 19-5535](https://www.afjag.af.mil/LinkClick.aspx?fileticket=Zigjw6p7hiw%3d&portalid=77)
  - Exceptional release after an unconfirmed leak — [AIB 84-0046](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/15%20MAY%2023%20AIB%20Kingsley%20ANGB%20F-15D%20Final%20Amended%20Report_Redacted.pdf)
  - Non-TO lubricant and misalignment in the throttle trigger — [AIB 92-3890](https://www.afjag.af.mil/Portals/77/AIB-Reports/2016/160602-ACC-Nellis-F-16CJ-AIB%20Report.pdf)
- Fleet variability evidence:
  - Bearing lives vary 1–7 h on an identical rig [TRANSFER] — [FEMTO challenge](https://github.com/wkzs111/phm-ieee-2012-data-challenge-dataset/raw/master/IEEEPHM2012-Challenge-Details.pdf)
  - Fault onset varies by flight class in N-CMAPSS [TRANSFER] — [Arias Chao et al.](https://www.mdpi.com/2306-5729/6/1/5)
  - Su-30 bearing-related malfunction onset moved from about 500 to about 900 FH after design changes [DIRECT] — [The Wire](https://thewire.in/security/assam-su30mki-crash-challenge-adapting-fighter-demanding-conditions)

### Inferences
- Recommended model family (expanded in §9c):
  - Gamma processes for monotone non-recoverable wear (erosion, clearance, nut/screw wear, brake and tyre wear).
  - Wiener-with-drift plus resets for recoverable fouling.
  - A rub-in step plus fast early-life transient for post-build clearance growth (Sallee short-term).
  - Usage-energy or damage-threshold onset (N-CMAPSS style) for abnormal degradation.
  - Two-phase initiation and growth (Weibull initiation, Paris or exponential growth) for cracks and spalls.
  - Poisson shocks for FOD and bird strikes.
  - Markov on/off processes for intermittent electrical and data faults.
- Imperfect repair should combine two effects:
  - Partial restoration: an action removes a fraction ρ of recoverable damage (wash ρ high for fouling; overhaul resets the module but leaves some non-recoverable loss).
  - A small probability of a maintenance-induced fault per action, with its own latency distribution: immediate (MEC) to hundreds of hours (air seal, 591 h) to years (fairing, about 6 years).
  - This is an [ASSUMPTION] structure consistent with the cited cases; validate probabilities against maintenance and defect records.

### Gaps
- No primary sources were retrieved for the classical imperfect-repair models (Kijima virtual age, Brown–Proschan, ARA), the gamma-process maintenance survey (van Noortwijk), or the RUL-review literature. These are standard, but citations should be added in a follow-up.
- No fighter-specific washing interval or recovery data were found, and no Indian dust or salt exposure-to-erosion rate data.

---

## 6. Fault propagation and cascades: FMEA/FMECA, fault trees, dependency models, documented cross-system cascades

### Takeaway
Fault propagation in fighters follows physical couplings, and these are documented in accident reports. The main paths:
- Engine spool-down → electrical generation loss → emergency power.
- Hydraulic leak or isolation logic → loss of specific consumers (flight controls, brakes, inlet ramps, gear).
- Contamination × environment → landing-gear stroke → WoW logic → flight-control law change.
- Electrical disruption → invalid navigation and attitude data without flags.
- Engine fire → damage to flight-control actuator harnesses.

Standards (MIL-STD-1629A, ARP4761/A) and dependency-model tools (TEAMS) give the formalism. Phalanx should encode these couplings as a typed dependency graph whose edges carry physical transfer functions, not just Boolean propagation.

### Cited Findings
- MIL-STD-1629A (24 Nov 1980, now cancelled) [DIRECT: DoD standard] — [MIL-STD-1629A](https://everyspec.com/MIL-STD/MIL-STD-1600-1699/download.php?spec=MIL_STD_1629A.1556.pdf):
  - Severity categories:
    - I, Catastrophic: may cause death or weapon-system loss.
    - II, Critical: severe injury or major damage leading to mission loss.
    - III, Marginal: minor injury or damage leading to delay, loss of availability or mission degradation.
    - IV, Minor: leads to unscheduled maintenance or repair.
  - Failure-mode criticality number Cm = β·α·λp·t, where:
    - β is the conditional probability of the effect (actual loss 1.00, probable >0.10 to <1.00, possible >0 to ≤0.10, none 0);
    - α is the failure-mode ratio (summing to 1 across modes);
    - λp is the part failure rate (MIL-HDBK-217 with π-factors);
    - t is the mission-phase time in hours or cycles.
  - Worksheets record the failure detection method, compensating provisions and BIT.
- ARP4761/ARP4761A (Dec 2023) [TRANSFER: civil, but the method is used in military practice] — [Wikipedia: ARP4761](https://en.wikipedia.org/wiki/ARP4761):
  - Methods: FHA, PSSA, SSA (FMEA/FMES, FTA, dependence diagrams, Markov analysis).
  - Common Cause Analysis: zonal safety analysis; particular risks such as bird strike and engine burst; common-mode analysis.
  - Fault-tree cut sets confirm that no single failure leads to a catastrophic event. Results feed MSG-3 maintenance task development.
- TEAMS-Designer (Qualtech) builds multi-signal dependency models that link failure modes to built-in tests. Its testability analysis reports uncovered faults, redundant tests, ambiguity groups and feedback loops; the example model is a helicopter engine. [TRANSFER: tool used in aerospace] — [QSI TEAMS-Designer](https://www.teamqsi.com/products/teams-designer/)
- Documented cross-system cascades [DIRECT]:
  1. **Engine → electrical → comms:** fan-blade liberation → spool-down → main and standby generators offline → momentary power disruption (radio call not heard) → emergency generator. The fire also damaged the right aft-fuselage harnesses for the horizontal-stabiliser and flaperon ISAs. — [AIB 90-0755](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf)
  2. **Engine HCF → stall → AB failure → control-mode switch → flameout → electrical:** turned vanes → blade loss → stall MFLs → AB failure → switch to SEC → fuel-flow surge → flameout → generators offline → EPU. — [AIB 92-3881](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf)
  3. **Maintenance part substitution → structural wear → cooling blockage → liner failure → fire:** — [AIB 92-3883](https://www.pacaf.af.mil/Portals/6/180220-PACAF-MisawaAB-Japan-F-16-AIB%20NARRATIVE%20REPORT.pdf)
  4. **Actuator internal leak → dual hydraulic loss → degraded flight control:** — [AIB 88-0477](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/F-16%2016%20May%2019%20March%20ARB%20ACC.pdf)
  5. **Heat-exchanger crack → utility hydraulic loss → inlet ramp caution + brake loss → runway excursion:** — [AIB 84-0046](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/15%20MAY%2023%20AIB%20Kingsley%20ANGB%20F-15D%20Final%20Amended%20Report_Redacted.pdf)
  6. **Contaminated servicing + cold soak → strut extension failure → WoW "on ground" → FCS ground law in flight:** — [AIB 19-5535](https://www.afjag.af.mil/LinkClick.aspx?fileticket=Zigjw6p7hiw%3d&portalid=77)
  7. **Partial electrical loss → EGI invalid (no flag) → HUD pitch ladder loss → disagreement between primary and standby attitude:** — [AIB 88-0549](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/6May23%20PACAF%20F-16C%20AIB%20Report.pdf)
  8. **Hydraulic coupling fatigue → isolation of the gear lock-link actuator + weak springs → gear collapse → wing drag → fuel-tank rupture → fire** (B-2): — [AIB B-2A 2021](https://www.afjag.af.mil/Portals/77/AIB-Reports/2021/14SEP21%20B-2%20AIB%20Report.pdf); [AIB B-2 2022](https://www.afjag.af.mil/Portals/77/AIB-Reports/2022/10Dec22%20AFGSC%20Whiteman%20B-2%20AIB.pdf)
  9. **Air-data disturbance → exclusion of one probe + intermittent other → wrong model-based control-law inputs → departure:** — [AIB 15-5197](https://www.afjag.af.mil/Portals/77/AIB-Reports/2022/19OCT22%20ACC%20F-35A%20388th%20FW%20Hill%20AFB%20AIB%20Report.pdf)
- FlightGear developers note that modelling failures that "influence each other, i.e. a structural failure here produces a system failure there", is "fairly aircraft specific" and "quite tricky to organize in a clean way" [TRANSFER: simulator design experience] — [FlightGear wiki: Failure Manager](https://wiki.flightgear.org/Failure_Manager)

### Inferences
- A Phalanx propagation layer needs typed edges:
  - shaft power to generators (speed-dependent drop-out);
  - hydraulic circuit topology (RLS and non-RLS isolation, EPU feeding system A);
  - thermal (cooling-air blockage, fluid temperature thresholds);
  - data and electrical buses (consumers losing validity, with or without flags);
  - discrete logic (WoW to control law);
  - mechanical (fragment → adjacent structure, fuel tank, harnesses).
- Each edge needs a transfer function and a latency (seconds for electrical drop-out, minutes for fluid loss).
- An FMECA-style table, with severity class and detection method per mode, should be the configuration file behind the generator. TEAMS-style D-matrices can then generate the expected BIT signature set per fault, and controlled imperfect coverage creates ambiguity groups and NFF.

### Gaps
- No public fighter FMECA or dependency model (for example an F-16 or Tejas utility-system D-matrix) was found. No published bleed-leak → ECS → engine cascade for a fighter was found in this session.

---

## 7. How existing simulators inject faults, and their realism limitations

### Takeaway
Engine benchmarks (C-MAPSS, N-CMAPSS, ProDiMES) inject faults by changing module η and Γ health parameters and snapshot-sampling sensors with Gaussian noise. That captures gas-path physics but not mechanical faults (bearings, oil, vibration), control and actuator faults beyond VSV/VBV, transients, or maintenance. Flight simulators (FlightGear/JSBSim) and Simulink/Simscape provide fault primitives: serviceable flags, failure levels, sensor bias/drift/stuck, actuator hard-over/stuck, and timed or conditional triggers. They have no built-in wear physics or cross-system cascades. A realistic fighter data generator has to combine both layers and add usage-driven onset, maintenance actions, imperfect BIT, and cascades.

### Cited Findings
- **C-MAPSS** [TRANSFER] — [Saxena et al. 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf):
  - 13 health-parameter inputs (fan, LPC and HPC η, Γ and PR modifiers; HPT and LPT η and Γ) on a 90,000-lbf commercial model; 21 of 58 outputs used.
  - Exponential degradation, one snapshot per flight, mixture noise.
  - The PHM08 data "modified flow and efficiencies of the HPC module" only. The model "ignores micro-level processes".
- **C-MAPSS40k** "simulate[s] effects such as engine deterioration or faults by adjustment of the health parameter modifiers"; abrupt faults or gradual degradation are imposed as time histories of 13 health parameters [TRANSFER] — [DeCastro, Litt & Frederick, NASA/TM-2008-215303](https://ntrs.nasa.gov/api/citations/20080043619/downloads/20080043619.pdf)
- **N-CMAPSS** limitations: accelerated ageing (tens of cycles, not thousands); only faults expressible as flow or efficiency; no accelerometers or oil-debris sensors [TRANSFER] — [Arias Chao et al. 2021](https://www.mdpi.com/2306-5729/6/1/5)
- **ProDiMES** "simulated gas path fault test cases … have not been validated against actual engine fault data". Single fault per engine; abrupt or linear-ramp evolution; steady-state solver with no closed-loop control (sensor-induced actuator mis-scheduling is applied by logic) [TRANSFER] — [ProDiMES User's Guide](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf)
- Real-engine validation gap: the C-MAPSS40k-derived models "displayed notable differences in performance" from real F117 engines and had to be re-trimmed; transient diagnostics misclassified faults [TRANSFER] — [Rinehart & Simon 2015](https://ntrs.nasa.gov/api/citations/20150000899/downloads/20150000899.pdf)
- **T-MATS**: a MATLAB/Simulink toolbox of generic thermodynamic and turbomachinery blocks with public default maps. The README does not document a fault or health-parameter injection feature, so faults would be injected by scaling component maps (efficiency and flow scalars). [TRANSFER] — [NASA T-MATS GitHub](https://github.com/nasa/T-MATS)
- **FlightGear**: legacy failures are Boolean `serviceable` properties, with random failures "based on time or usage cycles" only. The newer Failure Manager supports failure levels in [0, 1], actuators, and triggers (altitude, waypoint, timeout, MTBF, MCBF). Wear models are "under consideration" and interacting failures are not handled generically. [TRANSFER] — [FlightGear wiki: Failure Manager](https://wiki.flightgear.org/Failure_Manager)
- **JSBSim** [TRANSFER]:
  - FGSensor: lag, noise, quantisation, drift_rate, gain, bias, delay; fail_low, fail_high, fail_stuck — [FGSensor docs](https://jsbsim-team.github.io/jsbsim/classJSBSim_1_1FGSensor.html)
  - FGActuator: lag, rate limit, deadband, hysteresis, bias, clip; fail_zero, fail_hardover, fail_stuck, saturation flag — [FGActuator docs](https://jsbsim-team.github.io/jsbsim/classJSBSim_1_1FGActuator.html)
- **Simscape faults**: block-level faults with Always On, Timed, Conditional, Manual and Behavioral triggers, a Fault Table and Dashboard, and custom faults through annotations — [MathWorks: Introduction to Simscape Faults](https://www.mathworks.com/help/simscape/ug/about-simscape-faults.html). **Simulink Fault Analyzer** injects faults "without modifying your design" (timed or conditional), supports FHA/FMEA, and ships a predefined behaviour library (mwfaultlib, e.g. "Add Noise") for scalar signals — [Fault Analyzer docs](https://www.mathworks.com/help/fault-analyzer/index.html); [fault behaviours](https://www.mathworks.com/help/fault-analyzer/ug/manage-fault-behaviors.html). [TRANSFER]
- **NASA PCoE data repository** (real or rig run-to-failure data for calibration) includes IMS and FEMTO bearings, Li-ion batteries, IGBTs and MOSFETs, capacitors, CFRP, aluminium lap-joint crack growth, C-MAPSS, and turbofan degradation simulation 2 (N-CMAPSS) [TRANSFER] — [NASA PCoE data set repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)

### Inferences
- Known realism shortfalls that Phalanx should address:
  - Degradation is not driven by actual usage or environment (C-MAPSS), or is driven only by a power integral (N-CMAPSS).
  - No closed-loop fighter control: no FTIT limiting, A8 scheduling, or AB stages.
  - No transient fault physics: stall, AB blowout.
  - No mechanical or oil subsystem; no cross-system cascades.
  - No maintenance actions or maintenance-induced faults.
  - BIT and recording artefacts (fault codes, persistence, NFF) are missing.
  - Noise is i.i.d. Gaussian rather than structured; this is the sensor-texture researcher's topic.

### Gaps
- NASA ADAPT electrical power testbed and DXC'09 fault-injection documentation (fault types, magnitudes) were not retrieved.
- No information was retrieved on Gripen, Tejas or IAF simulator fault-injection practice.

---

## 8. Empirical evidence: published fault cases with recorded data, and fleet statistics

### Takeaway
Public USAF AIB reports are the richest open source of fighter fault-progression evidence. They give recorded parameter sequences (RPM, FTIT, fault codes, hydraulic pressures, timing), component measurements, and maintenance history. They complement airline cases with detailed FDR traces (QF72, Lion Air 610, Alaska 261). Fleet statistics are sparse but include F110 shop-visit rates, F404 shop-visit and in-flight-event figures, the Su-30MKI failure-cause breakdown, and NFF shares.

### Cited Findings
- Fleet statistics [DIRECT]:
  - Unscheduled, engine-caused shop-visit rates per 1,000 EFH (June 1997): F110-GE-100 2.93 (1.6 M h), F110-GE-400 1.60, F110-GE-129 1.77, F101 2.35, F118 1.68 — [GE military engine status report, 15 Jun 1997](https://www.geaerospace.com/news/press-releases/defense-engines/ge-aircraft-engines-military-engine-status-report)
  - F404: "less than two shop visits per 1,000 flight hours", "6,500 hours between in-flight events", more than 12 M h by 2010 — [Wikipedia: GE F404](https://en.wikipedia.org/wiki/General_Electric_F404)
  - Su-30MKI: 69 malfunctions (33 chips, 11 vibration, 8 low oil pressure, 17 unexplained); 35 engines with problems from 2013 to 2014; about 55% availability — [The Wire 2026](https://thewire.in/security/assam-su30mki-crash-challenge-adapting-fighter-demanding-conditions)
- AIB event catalogue with data [DIRECT] (details in §§1–6):
  - F-16 engines: Holloman 2019 (F100-220 fan blade), Thunderbird 2025 (F100-229 vane/HCF), Kunsan 2024 (stall from hardware failure; "unreliable and inaccurate data"), Misawa 2018 (F110-129 liner/fire), Andrews 2017 (F110-100C MEC), Eielson 2024 (bird strike).
  - Hydraulics: March ARB 2019 (F-16 ISA), Kingsley 2023 (F-15D FOHE).
  - Electrical: Osan 2023 (F-16).
  - Landing gear: Kunsan 2019 (F-16), Eielson 2025 (F-35A), B-2 2021/2022.
  - Air data: Hill 2022 (F-35A).
  - Controls: El Paso 2016 (F-16 throttle).
  - FOD: Luke 2023 (F-35A). A flashlight left in the intake caused $14M engine damage; the post-installation engine run showed "no visual indications or health reporting codes", and damage was found from noise and inspection — [AIB F-35A Luke 2023](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/15MAR23%20AETC%20F-35A%20Luke%20AFB%20AIB%20Report.pdf)
- Transport-aircraft cases with recorded traces [TRANSFER]:
  - QF72 ADIRU spikes and FCPC 1.2 s logic — [ATSB AO-2008-070](https://www.atsb.gov.au/investigations/ao-2008-070)
  - Lion Air 610: 21° AoA bias — [KNKT](https://www.aaiu.ie/sites/default/files/FRA/2018%20-%20035%20-%20PK-LQP%20Final%20Report.pdf)
  - Alaska 261: wear-rate history — [NTSB AAR-02/01](https://www.ntsb.gov/investigations/AccidentReports/Reports/AAR0201.pdf)

### Inferences
- The AIB set gives "ground-truth scenario scripts" (initiating cause → physical progression → observations → crew and system response → outcome) that Phalanx can replay as validation scenarios. The mean engine-caused shop-visit interval implied by 1.77–2.93 per 1,000 EFH (about 340–565 EFH) is a top-level calibration target for the overall engine-fault hazard [DIRECT, but dated 1997].

### Gaps
- No Indian (IAF) official fault statistics were found beyond the Parliament reply as reported. No HAL/IAF Tejas F404-IN20 reliability data or CAG audit figures were found. USAF/USN engine removal-cause Pareto tables (DTIC) were not accessible.

---

## 9. Closing synthesis for the Phalanx telemetry layer (required items a–e)

### (a) Key findings summary
1. **Model faults as physical state.** Gas-path deterioration lives in per-module η and Γ health parameters with mechanism-specific directions, expressed through a closed-loop engine model. Mechanical, hydraulic, electrical and air-data faults live in physical quantities: fluid volume and leak conductance, spring force, spall or crack size, bias and stuck states. [TRANSFER/DIRECT; §§1–3]
2. **Gradual drift is small and slow.** It is a few percent in η and Γ over thousands of cycles. There is an early-life rub-in step (about 1% TSFC on the first flight, 1.5% by 200 flights), and HPC deterioration accelerates after about 3,000 cycles. Shop-visit recovery is partial, about 20% of loss on the JT9D. [TRANSFER]
3. **Fighter severity is higher.** Military engines are more clearance-sensitive. F404 usage was severe enough to cut life about 50%. TAC accrues at about 2.5 per EFH on an F100-229 (inferred), ranging from about 0.4 per hour on a ferry to 10–15 per hour in air combat. [DIRECT]
4. **Losses are often abrupt and latent.** Many fighter mishaps come from defects with no gas-path precursor: assembly omissions, turned vanes, wrong parts, contaminated fluid. They then progress over seconds to minutes with characteristic signatures: FTIT rising while N2 falls, stall, AB and thrust fault codes, generator drop-out, hydraulic pressure oscillation. [DIRECT]
5. **Maintenance both restores and injects faults.** Seven or more cited military cases involve maintenance-induced faults, with latencies from one flight to six years. [DIRECT]
6. **Bearing faults dominate in the Indian Su-30 fleet.** Faults first appear as chips in oil (48% of investigated cases), then vibration (16%) and low oil pressure (12%), with onset around 500 FH, or 900 FH after modifications. [DIRECT]
7. **Sensors and BIT are imperfect.** Faults are often common-mode or intermittent and often unflagged. NFF is 30–60% of avionics removals. A target false-alarm rate of about 1 per 1,000 flights is typical for gas-path EHM. [DIRECT/TRANSFER]
8. **Existing open simulators cover pieces.** Health-parameter engines, sensor and actuator primitives, and trigger frameworks exist, but none combines usage-driven onset, fighter control loops, mechanical subsystems, maintenance and cascades. [TRANSFER]

### (b) Fault-mode catalogue
Notation: ↑/↓ give the direction of change; "BIT/EHM?" says whether the fault is typically flagged on board (BIT/MFL) or found by ground trending or inspection. Tags show evidence strength.

| # | Subsystem | Mechanism | Physical state variable(s) | Observable signatures (direction / magnitude) | Typical progression time scale | Detected by BIT/EHM? | Evidence and source |
|---|---|---|---|---|---|---|---|
| 1 | Fan/compressor | Fouling (particles < 2–10 µm, salt, oil mist) | ηc↓, Γc↓, surface roughness | At fixed N1 or thrust: FTIT/T5↑, Wf↑, N2 shift; ~1% Γ and ~1% η for 1.8→13 µm roughness | 100s–1,000s h; recoverable by wash | Ground trend only | [TRANSFER] [Kurz & Brun](https://torroja.dmt.upm.es/congresos/asme_2011/data/pdfs/trk-19/GT2011-45012.pdf); [Tahan et al.](https://shura.shu.ac.uk/16176/8/Tsoutsanis-Performance-basedHealthMonitoring%28AM%29.pdf) |
| 2 | HPC/fan | Erosion (dust/sand > 10 µm): LE blunting, camber and chord loss | ηc↓, Γc↓, stall margin↓ | As #1 plus reduced stall margin; ProDiMES fleet HPC η ≈ −5%, Γ ≈ −9% at 5,000 flights | 1,000s cycles; accelerates beyond ~3,000; non-recoverable | Ground trend | [TRANSFER] [Sallee](https://ntrs.nasa.gov/api/citations/19800013837/downloads/19800013837.pdf); [ProDiMES](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf) |
| 3 | HPT/HPC | Tip-clearance growth (rubs, seal wear) | ηT↓ (ΓT↑ for turbine rub) | +1 °C EGT and +0.1% SFC per 0.001 in HPT clearance; military "slightly greater" | Step at build or first flights (1% TSFC), then slow | Ground trend | [TRANSFER+DIRECT qualitative] [Lattime & Steinetz](https://ntrs.nasa.gov/api/citations/20030003697/downloads/20030003697.pdf) |
| 4 | HPT | Erosion, oxidation, TBC loss, thermal distortion, vane bow | ηT↓, ΓT↑ (throat area) | HPT η −2.6%, Γ +1.8% at 3,000 cycles (reference); 1% HPT fault: N2 −0.6%, Wf +0.6%, EGT +12 °F, P3 −0.5% | 1,000s cycles | Ground trend; at FTIT limit, thrust loss | [TRANSFER] [Saxena](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf); [Honeywell patent](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7062370) |
| 5 | LPT | Erosion, clearance | ηLPT↓, ΓLPT↑ small | Small: η −0.5% to −1.1% at 3,000–6,000 cycles | Slow | Ground trend | [TRANSFER] [Saxena](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf) |
| 6 | Engine inlet/fan | FOD or bird ingestion | Step Γ↓ η↓ (comp and turb), imbalance | Abrupt shift, stalls, vibration "yes"; dual-engine debris ingestion possible | Instantaneous (shock) | Pilot-noticed stalls, MFL; FOD may give no code | [DIRECT] [Eielson F-16 AIB](https://www.afjag.af.mil/LinkClick.aspx?fileticket=uW5wk5V_KDw%3d&portalid=77); [Luke F-35A AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/15MAR23%20AETC%20F-35A%20Luke%20AFB%20AIB%20Report.pdf) |
| 7 | Compressor variable geometry | RCVV/VSV mis-scheduling (actuator lag, linkage, feedback sensor) | Vane angle error → stall-line shift | Rotating stall 66 Hz; N2 12,790→10,800 rpm; FTIT falls then rises; stall persists | Seconds (transient) | DEEC fault codes | [DIRECT] [NASA TM-81759](https://ntrs.nasa.gov/api/citations/19810016549/downloads/19810016549.pdf) |
| 8 | HPC blades | Turned vanes → wake → HCF crack → blade loss | Vane twist, blade crack length | RPM↓ + FTIT↑; 2 stall codes within 2 s; AB-fail + thrust-low codes at ~10 s; no response above idle | Latent (not borescope-accessible) then seconds | Fault codes only at event | [DIRECT] [Thunderbird AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf) |
| 9 | Fan rotor | Missing air seal → blade migration 0.4–1.0 in → liberation | Blade axial position, retention | Thrust loss + fire/overheat/engine lights near-simultaneous; generator drop | 591 h latent → seconds | None before event | [DIRECT] [Holloman AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf) |
| 10 | Fuel control (MEC) | Pilot-valve mis-assembly → over-metering | Wf actual vs commanded offset | Uncommanded acceleration, overspeed, overtemp, fire | First flight after installation | Not caught by stand test | [DIRECT] [Defense Post / AIB](https://thedefensepost.com/2017/10/27/improper-engine-control-assembly-caused-april-f-16c-crash/amp/) |
| 11 | Augmentor | AB no-light or blowout → raw-fuel ignition pressure pulse | AB light state | Fan/compressor stall (early F100); AB-failure code | Seconds | Fault code | [DIRECT, secondary] [Wikipedia F100](https://en.wikipedia.org/wiki/Pratt_%26_Whitney_F100); [Thunderbird AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf) |
| 12 | Exhaust nozzle/liner | Fairing wear and fracture → cooling-air blockage → liner burn-through | Fairing integrity, liner temperature | Flame from aft fuselage, airspeed and climb decay, fire | Cracks seen at ~700–900 h; 800-EFH nozzle inspection | Inspection only; fire warning at event | [DIRECT] [Misawa AIB](https://www.pacaf.af.mil/Portals/6/180220-PACAF-MisawaAB-Japan-F-16-AIB%20NARRATIVE%20REPORT.pdf) |
| 13 | Bleed valves | Mis-scheduled 14th-stage / 2.5 bleed | Bleed fraction | Gas-path residual shift; weak or undetectable at low power | Abrupt or progressive | Model-based residual (steady state) | [TRANSFER: F117] [Rinehart & Simon](https://ntrs.nasa.gov/api/citations/20150000899/downloads/20150000899.pdf) |
| 14 | Hot-section discs and blades | LCF, creep, TMF usage damage | TAC, LMP damage fraction, crack length | No gas-path signature until crack; usage counters | ~2.5 TAC/EFH (inferred); 10–15 TAC per combat hour | Usage counting (EMS/CEMS/IECMS) | [DIRECT] [Thunderbird AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf); [f-16.net (informal)](https://www.f-16.net/forum/viewtopic.php?p=144239) |
| 15 | Main-shaft bearings | Rolling-contact fatigue spall → debris | Spall size, debris mass | Chips in oil (33/69), vibration (11/69), low oil pressure (8/69) | Onset ~500 FH (→ ~900 FH after mods); rig lives vary 7× | Chip detector / ODM / vibration | [DIRECT] [The Wire](https://thewire.in/security/assam-su30mki-crash-challenge-adapting-fighter-demanding-conditions); [TRANSFER] [FEMTO](https://github.com/wkzs111/phm-ieee-2012-data-challenge-dataset/raw/master/IEEEPHM2012-Challenge-Details.pdf) |
| 16 | Oil system | Low level, leak or pump fault → starvation → seizure | Oil quantity, pressure | Oil pressure↓, unusual noise → seizure | Minutes | Oil-pressure warning | [DIRECT, unconfirmed] [IDN](https://www.indiandefensenews.in/2024/07/engine-seizure-led-to-iafs-first-tejas.html); [IDRW](https://idrw.org/scoop-iaf-tejas-crash-oil-level-issue-points-to-potential-oversight-lapses/) |
| 17 | Lube cooling | Heat-rejection loss | Oil temperatures | HOT +0.6%, LOT +0.5% per 1% fault (illustrative) | Slow | Model residual | [TRANSFER: APU] [Honeywell patent](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7062370) |
| 18 | Hydraulics (FCS actuator) | Internal leak (mis-installed ISA check valves) | Leak conductance, fluid volume | Sys A 1,500–2,000 → 1,000–2,000 psi (nominal 3,100 ± 50); 31 ml/min at 1,000 psi; then Sys B low | Within one flight | HYD pressure caution | [DIRECT] [March ARB AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/F-16%2016%20May%2019%20March%20ARB%20ACC.pdf) |
| 19 | Hydraulics (utility) | External leak, FOHE weld crack (non-isolable circuit) | Fluid volume, valve state | Hydraulic + Utility B + inlet lights; gauge ~3,000 psi early; brake loss; leak rate↑ above 225 °F | Hours to one flight | Lights; RLS logic can't isolate | [DIRECT] [Kingsley AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/15%20MAY%2023%20AIB%20Kingsley%20ANGB%20F-15D%20Final%20Amended%20Report_Redacted.pdf) |
| 20 | Hydraulic fittings | Coupling fatigue (CryoFit) | Crack → fluid loss | Rapid loss in 2 of 4 systems (4,000 psi) | Minutes | System warnings | [DIRECT: bomber] [AIB B-2A 2021](https://www.afjag.af.mil/Portals/77/AIB-Reports/2021/14SEP21%20B-2%20AIB%20Report.pdf); [AIB B-2 2022](https://www.afjag.af.mil/Portals/77/AIB-Reports/2022/10Dec22%20AFGSC%20Whiteman%20B-2%20AIB.pdf) |
| 21 | Hydraulic fluid | Water and particulate contamination | Water fraction (~33%), particulates > 1,024 ppm | Freezing at ~0 °F → strut stroke loss → false WoW; gear canted 17° | ~40 min cold soak | None until symptom | [DIRECT] [Eielson F-35A AIB](https://www.afjag.af.mil/LinkClick.aspx?fileticket=Zigjw6p7hiw%3d&portalid=77) |
| 22 | Pumps / accumulators | Pump internal leakage; precharge loss | Leakage class; precharge pressure | Rig levels: leakage 0/1/2; precharge 130→115→100→90 bar | Slow | Not specified | [TRANSFER: industrial rig] [UCI 447](https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems) |
| 23 | Landing gear | Lock-link spring relaxation | Spring force | 88.9 lbf vs 100 ± 5 lbf; collapse despite "down and locked" | Years | None | [DIRECT: B-2] [AIB B-2A 2021](https://www.afjag.af.mil/Portals/77/AIB-Reports/2021/14SEP21%20B-2%20AIB%20Report.pdf) |
| 24 | Landing gear | Downlock actuator insufficient force | Actuator force vs gear tension | Collapse on touchdown | Fleet-known issue | None | [DIRECT] [Kunsan 2019 AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/191202-PACAF-KunsanAB-Korea-F-16%20AIB%20NARRATIVE%20REPORT.pdf) |
| 25 | Screw actuators | Archard thread wear (lubrication-dependent) | Thread thickness, end play | 0.001 in/1,000 FH nominal; 0.012 with poor lube; limit 0.040 in end play | 1,000s FH | Periodic end-play check | [TRANSFER: MD-83] [NTSB AAR-02/01](https://www.ntsb.gov/investigations/AccidentReports/Reports/AAR0201.pdf) |
| 26 | Cockpit controls | Wear, misalignment, debris → intermittent binding | Friction / stuck state | Throttle trigger sticks intermittently → inadvertent cutoff | Intermittent | None | [DIRECT] [El Paso AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2016/160602-ACC-Nellis-F-16CJ-AIB%20Report.pdf) |
| 27 | Electrical distribution | Partial power disruption | Bus or consumer power state | EGI invalid without flag; HUD pitch ladder lost at 30–45 s; AGCAS fail | Abrupt | Partial (AGCAS only) | [DIRECT] [Osan AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2023/6May23%20PACAF%20F-16C%20AIB%20Report.pdf) |
| 28 | Electrical generation | Generator drop-out on engine spool-down | Shaft speed vs generator cut-out | Main + standby offline; momentary loss; EPU/emergency generator on | Seconds | Cautions | [DIRECT] [Holloman AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf) |
| 29 | Battery | Capacity fade | Capacity (Ah), impedance | EOL at 30% fade (2.0 → 1.4 Ah) | Cycles and calendar | Capacity test | [TRANSFER: 18650 cells] [NASA dataset](https://data.nasa.gov/dataset/li-ion-battery-aging-datasets) |
| 30 | Air data (pressure transducers) | Moisture ingress (common mode) | Transducer offset | AoA and airspeed error; rotation 12 kt slow; 30° pitch-up at 1.6 g | Weather-triggered | None (all channels affected) | [DIRECT: B-2, secondary] [Wikipedia](https://en.wikipedia.org/wiki/2008_Andersen_Air_Force_Base_B-2_accident) |
| 31 | Air data (probes) | Flow disturbance → exclusion + intermittent out-of-limits | Probe validity state | AIR DATA DEGD for one side; > 40° AoA error in fused value; no caution for other side | Seconds | Partial | [DIRECT] [Hill F-35A AIB](https://www.afjag.af.mil/Portals/77/AIB-Reports/2022/19OCT22%20ACC%20F-35A%20388th%20FW%20Hill%20AFB%20AIB%20Report.pdf) |
| 32 | AoA vane | Calibration bias | Bias (21°) | Constant L–R split ~21°; IAS/ALT disagree; stick shaker | From installation | Disagree alert if enabled | [TRANSFER: B737] [KNKT](https://www.aaiu.ie/sites/default/files/FRA/2018%20-%20035%20-%20PK-LQP%20Final%20Report.pdf) |
| 33 | Avionics data bus / LRU | Intermittent corrupted or relabelled words | Spike process | AoA spikes (e.g. 50.625°); failure of a 1.2 s memorisation filter | Very rare (3 in 128 M unit-h) | Partially filtered | [TRANSFER: A330] [ATSB](https://www.atsb.gov.au/investigations/ao-2008-070) |
| 34 | Avionics / wiring / connectors | Intermittent contacts, solder joints | Intermittency rate | Removals NFF 30–50% (up to 60% naval avionics); wiring-related NFF costs | Intermittent, environment-dependent | BIT false or "can't duplicate" | [TRANSFER/DIRECT] [Khan et al.](https://pure.coventry.ac.uk/ws/files/3999358/J1_R.PDF) |
| 35 | Structure | Usage-driven fatigue cracking | Crack length (Paris), damage fraction (Miner) | Exceedance and strain-derived damage per tail | 1,000s FH | Ground individual aircraft tracking (90–95% data capture) | [DIRECT guidance] [MIL-HDBK-1530B](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL_HDBK_1530B.1890.pdf) |
| 36 | Gas-path sensors | Bias/offset (±1–10σ) | Sensor bias | e.g. T48 σ = 0.5% (≈10 °R at takeoff); feedback-sensor faults mis-schedule actuators | Abrupt or ramp | Residual-based; FA target ≤ 1 per 1,000 flights | [TRANSFER] [ProDiMES](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf); [Simon et al. 2013](https://ntrs.nasa.gov/api/citations/20140003941/downloads/20140003941.pdf) |
| 37 | Any sensor or actuator | Drift, scale, stuck, fail-high/low, hard-over, deadband, hysteresis | Sensor and actuator internal states | As parameterised | Configurable | Configurable | [TRANSFER: simulator primitives] [JSBSim FGSensor](https://jsbsim-team.github.io/jsbsim/classJSBSim_1_1FGSensor.html); [FGActuator](https://jsbsim-team.github.io/jsbsim/classJSBSim_1_1FGActuator.html) |
| 38 | ECS, fuel pumps and probes, tyres, brakes, AGB, IDG | (various) | (various) | **No public quantitative fighter source found** | — | — | **GAP, [ASSUMPTION] until maintenance-records data** |

### (c) Recommended degradation and fault modelling approach

**Architecture.** Model one hidden physical state vector per tail, per engine serial, and per serialised component. Advance it with usage. Map it to observations through physics models in closed loop. Corrupt observations through a separate sensor layer. Interpret them through imperfect BIT and EHM. Reset or perturb them through maintenance events.

1. **State layer (per serialised part).**
   - Engine modules: (η, Γ) per module, plus fighter extras: A8 actuator offset or lag, VSV/RCVV schedule offset, AB ignition reliability state, liner/cooling integrity flags.
   - Damage states: TAC/LCF damage per life-limited part; LMP creep fraction; bearing spall size; oil quantity and leak rate.
   - Hydraulics: fluid volumes per circuit, internal-leak conductance, external-leak rate, pump volumetric efficiency, accumulator precharge, contamination (water fraction, particulates).
   - Electrical: generator health and cut-out speed, battery capacity.
   - Air data: probe offsets, moisture state.
   - Structure: per-zone crack length or fatigue damage.
   - Consumables: tyre tread, brake stack wear, strut gas/oil charge. These are [ASSUMPTION] states given the source gap.
2. **Usage drivers (from the flight-profile generator).**
   - Rainflow-counted N1/N2/T4 cycles for TAC and LCF, calibrated to about 2.5 TAC/EFH on average, with 0.4–15 TAC/h depending on mission.
   - Time at temperature for LMP creep.
   - g-exceedances and strain proxies for ASIP.
   - Landings and braking energy for gear, tyres and brakes.
   - Ambient dust and salt indices for Indian bases, driving fouling and erosion rates.
   - Cold soak and heat exposure as triggers for contamination and thermal faults.
3. **Process models (choose per mechanism).**
   - Recoverable fouling: Wiener-with-drift in (ηc, Γc), with drift ∝ dust index; partially reset by washes. Trade-off: simple and allows non-monotone paths, but can go negative.
   - Non-recoverable erosion, clearance and wear: gamma process, with mean rate from transferred commercial values (Sallee, C-MAPSS, ProDiMES) × a fighter severity factor S. Tag S as [ASSUMPTION], initially 1.5–2 based on the F404 life-cut evidence; validate with HAL/IAF EGT- or FTIT-margin trend data. Trade-off: monotone and physically consistent, with a closed-form first-passage time.
   - Early-life rub-in: a step plus a short exponential (about 1% TSFC-equivalent on flight 1, rising to 1.5% by about 200 flights) after every build or overhaul.
   - Abnormal-degradation onset: N-CMAPSS-style cumulative-damage threshold (usage energy, TAC or LMP) with a unit-specific random threshold, followed by an exponential-power growth law δ = 1 − exp(a·t^b) (a ~ U(0.001, 0.003), b ~ U(1.4, 1.6) per flight). Rescale to fighter cycle counts.
   - Cracks and spalls: Weibull initiation, then Paris or exponential growth. For bearings, set debris generation proportional to spall growth and vibration rising with spall size. Use the Su-30 symptom shares to calibrate first-detected-symptom probabilities and onset around 500 FH (or 900 FH after modification).
   - Shocks: Poisson FOD and bird events with severity distributions and season/base dependence; step Γ/η losses plus imbalance; stall triggering.
   - Latent defects: a per-maintenance-action probability of injecting a defect, with a latency distribution spanning one flight (MEC) to hundreds of hours (air seal, 591 h) to years (fairing). Tag as [ASSUMPTION]; calibrate from maintenance records.
   - Intermittents: two-state Markov (on/off) with environment-dependent rates (vibration, temperature, moisture), generating spikes, dropouts, and NFF on removal.
4. **Observation layer.**
   - Use a closed-loop low-bypass afterburning engine model (from the engine-data researcher's work, or T-MATS-style component maps) with the platform's control logic: fan-speed or EPR scheduling, FTIT limiting, A8 and AB staging, DEEC/SEC or FADEC.
   - Health states enter as component-map scalars, so signatures arise naturally and depend on operating point (VIPR lesson: weak at low power).
   - Utility systems use lumped physical models (hydraulic volume and pressure, electrical bus topology, air-data probe fusion).
5. **Sensor layer.** Per channel: bias, drift, scale, noise multiplier, quantisation, lag and delay, stuck, fail-high/low, and spike/relabel processes (JSBSim FGSensor primitives). Control-feedback sensor faults feed back into actuation.
6. **BIT and EHM layer.** Coverage matrix (FMECA- or TEAMS-style), thresholds with persistence (e.g. suppress detection for the first 40 s after start), a false-alarm process (≈ 1 per 1,000 flights for gas-path EHM), and fault-code generation in MFL/PFL style. Make some faults deliberately unflagged (EGI-invalid, intermittent probes, weak springs). Generate NFF outcomes for avionics removals (30–60%).
7. **Propagation layer.** A typed dependency graph (power, hydraulic, thermal, data/electrical, discrete logic, mechanical fragment), with edge transfer functions and latencies taken from the AIB cascades in §6.
8. **Maintenance layer.**
   - Wash: restores a fraction ρ_wash of fouling.
   - Module swap or overhaul: resets module states to new initial-wear draws U(0, 1%) plus a rub-in step, and leaves non-recoverable residue, as in Sallee where about 20% of TSFC loss was recovered.
   - Inspections: borescope and 800-EFH nozzle checks with detection probability by location; some stages are not accessible.
   - Every action also carries a small probability of injecting a latent fault, so repair is imperfect in both directions.

**Trade-offs.**
- Physics-based degradation (PoF plus thermodynamic model): interpretable and extrapolates to unseen usage, but needs parameters that are not publicly available for fighters.
- Purely stochastic, data-shaped processes: easy to calibrate to fleet statistics, but fault signatures are not physically consistent across sensors.

The recommended hybrid puts stochastic processes on physical states and keeps sensor signatures physically derived. Because public fighter calibration data are thin, every [TRANSFER] parameter should carry an uncertainty range and be swept in validation.

### (d) Open questions and gaps
1. Fighter-engine influence-coefficient matrices and deterioration rates (EGT/FTIT-margin loss per 1,000 EFH) for the F404-GE-IN20, F110, F100, RM12 and AL-31FP. These must be generated from a platform engine model and calibrated against any IAF or HAL trend data.
2. Afterburner light-off and blowout statistics; nozzle (A8) actuator fault signatures; igniter faults; hung and hot start traces for fighter engines.
3. Bearing spall growth rates, oil-debris count or mass trajectories, chip-detector false-alarm rates, oil consumption trends, and 1/rev vibration amplitudes for fighter engines.
4. Utility-system quantitative degradation: pump case-drain flow, accumulator precharge loss rate, fuel pump and filter ΔP, fuel-probe faults, IDG/generator wear, ECS heat-exchanger fouling, tyre wear per landing, brake wear per landing or energy, strut servicing loss.
5. Fighter BIT coverage, false-alarm rates, and redundancy-management thresholds and persistence (classified or proprietary).
6. Public TAC/LCF counting algorithms (TO 00-20-5-1-1; IECMS/EMU logic) and fighter structural fatigue-life-expended rates.
7. Indian fleet data: official Tejas F404-IN20 and Su-30 AL-31FP failure-mode statistics beyond press reports; dust and salt exposure versus erosion rates at IAF bases.
8. Primary citations for imperfect-repair models (Kijima, ARA) and the gamma-process maintenance literature; aero-engine compressor-wash recovery magnitudes.
9. DTIC-hosted reports (RTO-TR-028 engine life monitoring; Navy and USAF engine removal-cause analyses) were blocked in this session. Retry with a browser or manual download.
10. NASA ADAPT/DXC electrical fault-injection definitions were not retrieved.

### (e) Ranked list of most valuable sources
1. USAF AIB reports (afjag.af.mil / pacaf.af.mil). These are DIRECT fighter fault chains with recorded data and maintenance histories: [AIB index](https://www.afjag.af.mil/AIB-Reports/). The most useful are 92-3881 (F100-229), 90-0755 (F100-220), 92-3883 (F110-129), 88-0477 (hydraulic ISA), 84-0046 (FOHE), 19-5535 (F-35 contamination/WoW), 15-5197 (F-35 air data) and 88-0549 (electrical).
2. [Arias Chao et al. 2021, N-CMAPSS](https://www.mdpi.com/2306-5729/6/1/5): the best open template for usage-driven onset, fleet variability and abnormal-degradation laws.
3. [Simon, ProDiMES User's Guide NASA/TM-2010-215840](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf): fault magnitudes, Γ:η ratios, sensor σ and bias faults, fleet deterioration profiles.
4. [Sallee 1978, NASA CR-135448](https://ntrs.nasa.gov/api/citations/19800013837/downloads/19800013837.pdf): measured deterioration causes, short- and long-term rates, repair recovery.
5. [Saxena et al. 2008, C-MAPSS damage propagation](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf): health-parameter wear tables and exponential damage model.
6. [The Wire 2026 on Su-30MKI AL-31FP failures (Parliament reply)](https://thewire.in/security/assam-su30mki-crash-challenge-adapting-fighter-demanding-conditions): DIRECT Indian failure-mode shares and onset hours.
7. [Lattime & Steinetz NASA/TM-2002-211794](https://ntrs.nasa.gov/api/citations/20030003697/downloads/20030003697.pdf) and [Melcher & Kypuros NASA/TM-2003-212627](https://ntrs.nasa.gov/api/citations/20040031316/downloads/20040031316.pdf): tip-clearance–EGT sensitivity, with the military note.
8. [Lee, NASA TM-81759](https://ntrs.nasa.gov/api/citations/19810016549/downloads/19810016549.pdf): F100 non-recoverable stall high-response data.
9. [Rinehart & Simon NASA/TM-2015-218448 (VIPR)](https://ntrs.nasa.gov/api/citations/20150000899/downloads/20150000899.pdf) and [Simon NASA/TM-2010-216358](https://ntrs.nasa.gov/api/citations/20100024368/downloads/20100024368.pdf): real-engine seeded faults, on-board versus ground detection.
10. [Khan et al. 2014 NFF Part 1](https://pure.coventry.ac.uk/ws/files/3999358/J1_R.PDF): NFF rates and causes, including military.
11. [MIL-STD-1629A](https://everyspec.com/MIL-STD/MIL-STD-1600-1699/download.php?spec=MIL_STD_1629A.1556.pdf) and [MIL-HDBK-1530B](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL_HDBK_1530B.1890.pdf): FMECA formalism and ASIP usage tracking.
12. [NTSB AAR-02/01](https://www.ntsb.gov/investigations/AccidentReports/Reports/AAR0201.pdf), [ATSB AO-2008-070](https://www.atsb.gov.au/investigations/ao-2008-070), [KNKT PK-LQP](https://www.aaiu.ie/sites/default/files/FRA/2018%20-%20035%20-%20PK-LQP%20Final%20Report.pdf): quantified wear, intermittent spikes and bias cases.
13. [Tahan/Tsoutsanis et al. review](https://shura.shu.ac.uk/16176/8/Tsoutsanis-Performance-basedHealthMonitoring%28AM%29.pdf) and [Kurz & Brun GT2011-45012](https://torroja.dmt.upm.es/congresos/asme_2011/data/pdfs/trk-19/GT2011-45012.pdf): mechanism-to-health-parameter directions and fouling/erosion physics.
14. [JSBSim FGSensor](https://jsbsim-team.github.io/jsbsim/classJSBSim_1_1FGSensor.html) / [FGActuator](https://jsbsim-team.github.io/jsbsim/classJSBSim_1_1FGActuator.html), [FlightGear Failure Manager](https://wiki.flightgear.org/Failure_Manager), [Simscape faults](https://www.mathworks.com/help/simscape/ug/about-simscape-faults.html): implementation primitives.
15. [GE 1997 military engine status](https://www.geaerospace.com/news/press-releases/defense-engines/ge-aircraft-engines-military-engine-status-report), [Canada TAA 2016-02](https://www.canada.ca/en/department-national-defence/services/military-airworthiness/technical-airworthiness-authority-overview/technical-airworthiness-regulatory-documents/technical-airworthiness-authority-advisories/2016-02.html), [Wikipedia GE F404](https://en.wikipedia.org/wiki/General_Electric_F404): fleet-level rates and usage-severity evidence.
