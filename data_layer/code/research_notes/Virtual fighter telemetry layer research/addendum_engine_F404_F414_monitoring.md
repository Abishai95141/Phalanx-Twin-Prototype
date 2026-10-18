<!-- Late sub-report from engine-research helper agent abe2ab5ee57d9f43f; preserved verbatim as an addendum to candidate_engine_and_ehm_data.md -->

> **CORRECTION (from f404_in20_engine_model.md, verified on page images):** Henry, AGARD-CP-448 paper 37 Table 1 — test-cell T1 = 266 K (not 296 K), test-cell T5 = 834.3 K (not 934.3 K), aircraft T5 = 871.0 K (not 971.0 K); earlier values were OCR errors. The F404-400 ECU T5 trim range is ±150 °F (not +15 °F). LUI Type I cycle is 'Off → Intermediate → Idle'.

# Phalanx research sub-agent report: F404/F414 engine health monitoring, life usage, ground systems, PHM literature and Indian relevance

## How the research went (read this first)

- **Web search ran out partway through.** The 200-call web-search budget, shared by every agent in this turn, was used up early. After that I made no new searches. I only fetched documents I had already identified, plus known primary URLs (GE, ADA, IEEE). This is the main reason Finland, Switzerland, Spain, T-50 and the Tejas CAG material are thin. A follow-up session with more search budget could fill those gaps.
- **DTIC itself was unavailable.** apps.dtic.mil returned "Under Maintenance" or HTTP 403. I used the archive.org mirrors of the same DTIC documents (`https://archive.org/details/DTIC_<ID>`), which are the identical scanned files.
- **Local copies.** All PDFs and extracted text are in `/Users/abishaikc/Phalanx/research_sources/engine_data/f404_monitoring/`. I did not write any notes files. The OCR of the ADA annual reports is in the session scratchpad only.
- **Tags.** [DIRECT] = about that exact engine or system. [TRANSFER: x] = taken from a related platform, with the reason and limits. [ASSUMPTION] = my engineering judgement.

---

## Q1. F/A-18A–D IECMS / EMS on the F404-GE-400/402: architecture, parameters, triggers, life usage, ground use

### What the onboard system is made of
- [DIRECT] **Who built it.** The IECMS was an original F/A-18 full-scale-development requirement. McDonnell Aircraft (MCAIR) was the integrator. GE supplied the F404 sensor package and the software algorithms. The system was designed using FMEA, MSG-2 analysis and life-cycle-cost trade studies.
  - Source: Hess (NAVAIR), "Overview of US Navy EMS programs", AGARD-CP-448 (1988), paper 2, pp. 2-4 to 2-5. https://archive.org/details/DTIC_ADA203800
- [DIRECT] **Main parts** (same source, p. 2-5; I checked the page image):
  - **Engine sensors.** 13 sensors are used; all but 5 are also needed for engine control or cockpit display. Signals reach the airframe as analog or frequency signals, one discrete wire per signal.
  - **Airframe inputs** (taken from the flight control system at no extra cost): Mach, altitude, freestream total temperature, angle of attack, normal load factor, fuel pressure, fuel temperature.
  - **MSDC.** The Bendix Maintenance Signal Data Converter sits in the right leading-edge extension (LEX). It digitises the engine signals and is shared with 7 other aircraft systems.
  - **MSDR / tape.** The Maintenance Signal Data Recorder, under the left LEX, writes to a Tape Magazine Unit. Recording happens on anomalies and before take-off (for trending). The tape also holds airframe fatigue data and a "crash tape" record. Capacity is about 7 flights.
  - **MMP.** The Maintenance Monitor Panel in the nose-wheel well shows a 3-digit code. There are 44 engine codes and 231 codes for other systems. Each code points into the maintenance-manual troubleshooting trees.
  - **Mission Computer.** It holds all IECMS logic: 5,400 16-bit words, 2–4 % of MC capacity. The logic falls into three groups: continuous monitoring, "as required" monitoring, and life usage.
  - **Cockpit display.** Five engine parameters are always shown on digital gauges. Eight more can be called up on the DDI, which also has a record button.
- [DIRECT] **Recorder names.** The Signal Data Recording Set is designated AN/ASM-612. RAAF troubleshooting rules refer to MMP codes 709 and 759.
  - Sources: Larkin, Frith & Findlay, IFDIS, ARL-PROP-TM-439 (1987), ch. 6 and rule 083, https://archive.org/details/DTIC_ADA227757 ; Forsyth, ARL-PROP-TM-450 (1989), glossary, https://archive.org/details/DTIC_ADA219105
- [DIRECT] **Later F/A-18C (F404-GE-402).** On a 2000 flight test aircraft (BuNo 164869), the engine words on the 1553 bus come from an "SDC" (Signal Data Computer) and go to the MC. The words are:
  - EGT (°C); compressor discharge pressure (psia); turbine discharge pressure (psia); NL and NH (rpm)
  - engine inlet temperature (°C); oil pressure (psid); nozzle position (%); main fuel flow (pph)
  - fuel inlet temperature (°C); turbine discharge temperature (°C)
  - discretes: inlet ice, bleed-air leak, bleed off
  - PLA left/right and compressor-speed lockup come from flight control computer B
  - The test's data system sampled all words at 20 samples/s. That is the test system's rate, not necessarily the native bus rate.
  - Source: NAWCADPAX/RTR-2001/1, Table E-3 and para 18. https://archive.org/details/DTIC_ADA407860
  - [ASSUMPTION] The later "SDC" replaced the early "MSDC". The documents show the different names; the exact transition lot was not found.
- [DIRECT] **The engine control unit's own monitoring (F404-400 ECU).** It is fuel-cooled, engine-mounted and powered by the engine alternator. Its monitor functions are overspeed detection, detection of various electrical failures, detection of a stuck nozzle control, and signals to the airframe monitoring system. It has a J61 test connector.
  - Its control functions: isochronous N1 limiting above intermediate, turbine temperature control, afterburner fuel scheduling, fan variable geometry and AB nozzle scheduling. The hydromechanical main fuel control handles compressor variable geometry.
  - Source: Forsyth 1989, App. A.1.1. https://archive.org/details/DTIC_ADA219105
- [DIRECT] **IECMS signals on engine connectors.** The E1 plug carries compressor-inlet total temperature, LPT-outlet total temperature, exhaust nozzle area and N1. The E2 plug carries N2. There is a dedicated P3 IECMS transducer.
  - Source: Streatfeild, ARL Aero-Prop-TM-446 (1988), §5.12–5.14. https://archive.org/details/DTIC_ADA196265

### Event triggers and stored records
- [DIRECT] **Triggers.**
  - Limit exceedances on fan speed, compressor speed, EGT, oil pressure and vibration. Each sets a cockpit caution, an MMP code and an event record.
  - Sensor-range failures on N1, N2, compressor delivery pressure, exhaust gas pressure, inlet temperature and oil pressure.
  - Flameout, detected from compressor delivery pressure and rotor-speed behaviour.
  - A take-off thrust evaluation: computed thrust from exhaust gas pressure and nozzle position.
  - A pilot record button.
  - Source: Paré & Muir (1998), pp. 2–3. https://archive.org/details/DTIC_ADA347270
- [DIRECT] **Length of an event record — sources disagree.**
  - Hess (p. 2-5) says 5 s before plus 25 s after the event. The pre-event part is a rolling 5 s buffer frozen when the trigger fires.
  - Canadian sources say 5 s before plus 35 s after, about 40 s in total: Muir, Rudnitski & Cue, CP-448 paper 7, p. 7-1, and Paré & Muir 1998, p. 2.
  - The US Navy general engine specification MIL-E-5007E (AS), 1983, as quoted by Hess p. 2-2, also asks for 5 s pre and 25 s post.
- [DIRECT] **Take-off record.** It starts when the throttle reaches take-off power and ends at lift-off, typically 6–10 s.
  - Source: Muir et al., p. 7-1.
- [DIRECT] **Recorded parameters and rates (CF-18 IECMS, Table 1 of Muir et al., p. 7-7).**

| Parameter | Rate |
|---|---|
| Pressure altitude, Mach, AOA, total temperature T0, engine inlet temperature T1 | 10 Hz |
| N1, N2, T56 (EGT), P56, PS3, main fuel flow Wfm, PLA, nozzle position A8 | 10 Hz |
| Normal acceleration Nz, main oil pressure, vibration, fuel temperature, anti-ice valve position, bleed-air door position | 1 Hz |

- [DIRECT] **Ground smoothing applied to take-off data** (Table 2): exponential curve fit for N1 and N2; spike/flat removal plus gap filling plus a 2-point moving average for Wfm; a 2-point moving average for PS3, T56 and P56.
- [DIRECT] **Sources disagree on "continuous" recording.** The Canadian policy paper says the CF-18 can record 13 engine parameters continuously to tape (Schofield et al., CP-448 paper 4, p. 4-3). Hess, Muir and Henry all describe recording as event, take-off or pilot triggered.
  - [ASSUMPTION] "Continuous" probably refers to monitoring, not recording.

### Measurement noise and quantisation (directly usable for synthetic data)
- [DIRECT] **Henry, CP-448 paper 37, Table 1 (p. 37-4)**, precision at 2σ.

| Channel | Test-cell target | Aircraft target | Aircraft 2σ precision | MSDC digital resolution |
|---|---|---|---|---|
| T1 | 296 K | 296.1 K | 1.3 K | 1.0 K |
| XN1 | 10,962 rpm | 10,560 rpm | 154 rpm (MSDC alone 153.6) | 16 rpm |
| XN2 | 14,215 rpm | 14,204 rpm | 139 rpm | 16 rpm (OCR "Is"; probable) |
| PS3 | 209.1 psia | 137.9 psia | 1.2 psia | 0.5 psia |
| P5 | 34.5 psia | 24.7 psia | 0.14 psia | 0.06 psia |
| T5 | 934.3 K | 971.0 K | 2.0 K | 1.0 K |

  - The MSDC, not the engine sensors, dominated the error: most temperature and pressure readings sat within one bit "toggle" of the mean.
  - The fuel-flow meters were sampled faster than they can respond.
- [DIRECT] **Repeatability.** Transient take-off data repeated within ±1 % when: throttle rate ≥ 45°/s; analysis is limited to the window when the nozzle is closed (the nozzle closes within about 1 s and stays closed about 4 s); ambient temperature is similar; and the engine has cooled. Starting-speed standard deviation was 4 % for the fan and 2 % for the core.
  - Source: Henry, pp. 37-2 to 37-5.
- [DIRECT] **Further repeatability figures.** NRCC compared IECMS data with test-cell data: fuel flows agreed within ±2 % and N1/N2 within ±0.5 %.
  - Source: Forsyth 1989, §7.

### Life-usage algorithms
- [DIRECT] **Eight GE-defined Life Usage Indices (LUIs)** are computed in the MC, written to tape, and passed to ground Parts Life Tracking (Hess, pp. 2-5 to 2-6):
  1. Full N2 cycle ("Type I"): off → intermediate → idle.
  2. Partial N2 cycle ("Type III"): idle → intermediate → idle.
  3. Equivalent Full Thermal Cycles (EFTC): HPT blade thermal cycles weighted by size of the cycle.
  4. Stress Rupture Counts: accumulate faster at higher HPT blade metal temperature.
  5. Time At Max Power (TAMP): time at intermediate or above.
  6. Full PS3 cycle: core pressure cycle near maximum allowed PS3; only occurs at high speed and low altitude.
  7. Partial PS3 cycle: PS3 reaches 85 % of maximum allowable.
  8. Engine operating time at or above ground idle.
  - Hess lists only these eight. Paré & Muir also say eight LUIs. Running sums are written to tape twice per flight (Paré & Muir, p. 2).
- [DIRECT] **How EFTC is driven.** It is computed in the mission computer from turbine exhaust gas temperature. For René 125 HPT blades the EFTC limit is about 1,000 h of average operation; DS René 80 blades are expected to give about twice that. About "twenty odd" components are tracked this way, most with roughly 4,000 h average life.
  - Source: ARL, "The GE F404 – Engine of the RAAF's New Fighter" (1985), p. 4. https://archive.org/details/DTIC_ADA164562
- [DIRECT] **Real usage was harsher than designed.** Accelerated Service Test data showed time at maximum temperature about 60 % above the original life analysis, and afterburner light-ups also up about 60 %. US Navy and Canadian experience tended to confirm this (same source, p. 3).
- [DIRECT] **Total Accumulated Cycles (TAC): not found for the F404.** F404 life accounting uses the LUIs above, not TAC.
  - [TRANSFER: USAF F100/F110] TAC is a USAF concept; see the F100/F110 agents.
- [DIRECT] **Canada converts LUIs to airframe hours.** Estimated AFH life = life limit (in LCF counts) ÷ the fleet-average LUI per AFH, which is mission-mix specific. Canada uses a 400 h "fallout window" and 400 h periodic inspections.
  - Source: Stemate, DND ORD PR 2002/02, paras 17–19. https://archive.org/details/DTIC_AD1003532
- [DIRECT] **Counting error caused by sensor noise.** A noisy N2 signal made one engine accumulate partial-N2 counts up to 8× faster than its twin on the same aircraft (Muir et al., p. 7-3).

### US Navy ground use
- [DIRECT] **1980s.** The Enhanced Comprehensive Asset Management System (ECAMS) ground station was only marginally functional and was added "as an after-thought". This limited IECMS use. The 4,000 h engine figure comes from the savings estimate: one life-limited part saved more than $18.10 per engine flight hour, i.e. $72,400 over a 4,000 h engine life (Hess, pp. 2-6 to 2-7).
- [DIRECT] **Lessons the Navy recorded** (same source):
  - The avionics left out a required high-frequency vibration filter. Signals above 10 kHz saturated the electronics, and the fleet switched off the cockpit vibration warning.
  - An exceedance should persist for several computer iterations before it is declared.
  - The tape survived most F/A-18 crashes.
- [DIRECT] **Parts Life Tracking System (PLTS).** The F404 maintenance plan has IECMS accumulate the life-limiting parameters for PLTS. Life used is computed in the ECAMS ground station and tracked by installation (aircraft → engine → module → assembly). The record travels with the engine to I- and D-level.
  - Source: King & Tooker, NPS thesis (1993), pp. 21–24. https://archive.org/details/DTIC_ADA277918
- [DIRECT] **2000s.** The NALDA Aircraft Engine Maintenance System Decision Support System (AEMS DSS) holds module removal histories. Its TMSREMSERNO report gives each module serial number, usage at removal, removal reason code and date, exportable to HTML or Excel.
  - The SAME (Simulated Automated Maintenance Environment) server tracks engine movement.
  - Source: Schoch, NPS thesis (2003), §IV.B. https://archive.org/details/DTIC_ADA418270 ; Hagan & Slack, NPS (2006), p. 22. https://archive.org/details/DTIC_ADA462668
  - DECKPLATE and NALCOMIS data were used for F414/EA-18G analysis (Hood, Khan & Story, NPS 2013, p. 29). https://archive.org/details/DTIC_ADA585693
- [DIRECT] **Evidence for the problem statement "fragmented records" problem.** At NAS Lemoore I-level, technicians must reconcile the engine logbook against AEMS and SAME before work can start. This takes 30 minutes when everything matches, otherwise weeks; the average was 14 days (Hagan & Slack 2006, p. 22).
- [DIRECT] **Supply-data errors.** Errors in the F404 master data file (error type "AF") were significantly linked to backorders and low supply material availability.
  - Source: Burson, NPS (2003). https://archive.org/details/DTIC_ADA414804
- **Not found publicly:** the acronyms "SEMS" and "ECMS" as US Navy F404 systems, and any "Comprehensive Engine Trending" program. The search budget ran out before I could pursue them.

---

## Q2. F414 in the F/A-18E/F: the advanced IECMS
- [DIRECT] **Primary paper.** Hall, Leary, Lapierre, Hess & Bladen, "F/A-18E/F F414 advanced IECMS", IEEE Aerospace Conference 2001, vol. 6, pp. 3069–3082, doi 10.1109/AERO.2001.931325. https://ieeexplore.ieee.org/document/931325
  - The abstract (retrieved) says the C/D IECMS was extended for the F414-GE-400. It combines diagnostic algorithms, engine-control computer and sensors, and airframe computers; it compares baseline and advanced capability; and it gives examples of anomalies caught in ground runs and in flight.
  - IEEE index terms include Memory Unit, High Vibration, Chip Detection, Oil Pressure, Fault Detection and Isolation, Life Tracking, and "Hz rate".
  - The full text is paywalled and was not read.
- [DIRECT, secondary summary of Hall et al.] **Improvements over the C/D system:** better aircrew displays and more cautions/advisories; more mission-computer resources; a new FADEC with strong fault detection and isolation; better monitoring hardware and signal processing; expanded memory-unit recording; an engine-mounted master electrical chip detector; more maintenance codes. In Navy technical evaluation it achieved 100 % engine-failure detection and 0 % false alarms.
  - Source: Hood, Khan & Story (2013), pp. 17–18. https://archive.org/details/DTIC_ADA585693
- [DIRECT] **F414 life usage.** Life used is measured through "nine matrices with 214 elements". The data are collected by "IECAMS", uploaded into the mission computers, downloaded after each flight, and sent up-line to the SAME server; the fleet sees it as the 72N engine configuration report.
- [DIRECT] **F414-GE-400 module life limits in 2008:**

| Module | Limit | Basis |
|---|---|---|
| Fan | 4,000 h | EOT |
| HPC | 4,000 h | EOT |
| Combustor | 4,000 h | EOT |
| HPT | 1,850 h | LUI |
| LPT | 4,000 h | EOT |
| Afterburner | 3,431 h | EOT |

  - Source: Hersey, Thompson & Rowlett, NPS (2008), pp. 14–15, Table 1. https://archive.org/details/DTIC_ADA493918
- [DIRECT] **2003 module high-time table** (Schoch, App. C, Table 13). Limits were given in EOT or ELCF, converted at a factor of 1.2 ELCF per EOT hour. Examples: fan 6,420 ELCF = 5,350 EOT; HPT 1,444–2,980 ELCF = 1,203–2,483 EOT; LPT 19,950–22,830 ELCF.
  - [ASSUMPTION] The 1.2 ELCF/EOT figure is a usable LCF-per-hour rate for synthetic usage.
- [DIRECT] **Sources disagree on F414 intervals.** The 2013 Growler thesis gives scheduled module intervals of fan 2,000, HPC 1,700, combustor 4,000, HPT 2,220, LPT 4,000 and AB 2,000 h, with a ±10 % window (Table 9). These differ from the 2008 limits; age-exploration changes over time are the likely cause.
- [DIRECT] **F414 reliability.**
  - 2012 fleet engine MTBF was 582 h. Growler engines at Whidbey Island: 1,148 h (30 failures; 46 aircraft; 17,223 FH).
  - Afterburner module MTBF 673 h; 66.6 % of afterburner defects were main spray bars.
  - There is a 200 h engine inspection (window 180–220 h).
  - Source: Hood et al. (2013), pp. 11, 33, 39–41.
- [DIRECT] **Navy engine removal reason codes** (about 120 codes; e.g. 1L FOD, 2N metal in oil, 3D vibration, 6Q compressor stall, 6V LCF, 7G high time (counts), 8F JOAP lab recommendation). These are ready-made labels for synthetic maintenance records.
  - Source: Schoch (2003), App. B. https://archive.org/details/DTIC_ADA418270
- [DIRECT] **I-level F414 work** includes troubleshooting the FADEC (Hagan & Slack, p. 15).
- **Not found publicly:** F414 IECMS parameter list or sampling rates, FADEC-recorded fault-code lists, any Navy remote or prognostic program for the F414, and ADEM. The search budget was exhausted.

---

## Q3. Allied operators' published F404 work

### Canada (CF-18): the richest public record
- [DIRECT] **Ground ECMS.** Canada began building an Engine Condition Monitoring System in 1983 (Paré & Muir 1998, pp. 1–11). https://archive.org/details/DTIC_ADA347270
  - It has four tiers: Portable CF-18 Ground Stations at each squadron, which read the tape into an "Aircraft Data File"; base-level ECMS at Cold Lake and Bagotville; a central ECMS at the overhaul contractor Orenda, updated nightly; and an NDHQ viewer.
  - It tracks 26 life-limited and 54 logistically critical components per engine.
  - The tape holds 7–10 flights. It is downloaded immediately after any MMP event.
- [DIRECT] **Flight Line Troubleshooting System.** Its fault library covers more than 45 F404 failure modes. It isolates the faulty LRU in 60–70 % of cases without ground runs.
  - Measured benefits (1990–91 against 1993): 26 % fewer LRU removals per incident; 50 % fewer false engine removals; 24 % fewer serviceable fuel controls and 61 % fewer serviceable control assemblies returned to depot; payback about 8 months.
- [DIRECT] **Performance Monitor.** It computes nine take-off "condition indicators" (rotor acceleration times, N1/N2 ratio, fuel ratio units, nozzle position) and interprets them with a rule-based expert system.
- [DIRECT] **Effect of a sudden life cut.** In March 1992 a US Navy uncontained stage-1 fan disk failure led to life reductions of more than 1,000 EFH. The ECMS allowed fallout forecasting and mix-and-match rotor rebuilds.
- [DIRECT] **Take-off health indices** (Muir, Rudnitski & Cue, CP-448 paper 7):
  - fuel ratio units Wfm/PS3, monitored at 81 % and 87 % N2;
  - fan and core acceleration time while the nozzle is closed;
  - PS3 rise time to 250 psi, compared left engine against right.
- [DIRECT] **Test-cell fault isolation** (same paper):
  - Uses an NRC component-level F404 model.
  - Seven baseline pairs, e.g. Wfm/δ1√θ1 against N2/√θ1, PS3/P1 against N2/√θ1, T56/θ1 against P56/P1.
  - Correcting for variable-geometry position cuts data scatter by 2–3×.
  - The F404 can carry considerable component damage and still pass the EPR acceptance test.
  - The trial ran ground runs every 25 FH on 8 engines for 18 months.
- [DIRECT] **Henry's statistical shift detection.** A Kalman-filter-updated confidence band detected HPC damage on engine 376020 (Henry, Table 2):
  - shifts of +2 % to +5 % in cross-plots against nominal scatter of ±0.8 % to ±2 %;
  - performance shifts not caused by faults came from throttle overshoot into AB, inlet screens left on, reslams and inlet temperature.
- [DIRECT] **Vibration.** The F404 has one accelerometer in flight and three in the test cell. In-flight vibration monitoring "did not function up to expectations": no engine removed for an in-flight vibration exceedance was rejected in the test cell.
  - Source: Schofield et al., CP-448 paper 4, p. 4-3.
- [DIRECT] **Oil wear debris (QFDA)** (Bennett et al. 1996, Table I). https://archive.org/details/DTIC_ADP010173
  - Wear rates in µg/h, mean / 2σ. CF188 (26 filters): Fe 0.475/1.68, Ni 0.627/2.43, Ag 0.080/0.254. USN F/A-18 (38 filters): Fe 6.1/13.27, Ni 7.71/18.31 (different preparation method).
  - Two engines with confirmed faults (a radial drive shaft failure; a chip in the screen plug) exceeded 2σ on 5 elements each.
  - Some table values are OCR-garbled.
- **Not retrieved:**
  - Cue & Muir, ASME 90-GT-357. Only a Semantic Scholar stub was seen: https://www.semanticscholar.org/paper/Engine-Performance-Monitoring-and-Troubleshooting-Cue-Muir/7325b76b095e4347221d8d7a5b67e04d9a4e503a
  - Cue & Muir, "Climatic considerations", AGARD-CP-480 (1990).

### Australia (RAAF Hornet; ARL/DSTO)
- [DIRECT] **Ground data systems.** RAAF ground processing used CAC's Maintenance Data & Service Life Monitoring System (MD&SLMS), the CAMM parts tracking system and a Unit Computing Facility that collected MSDRS/IECMS data. It was supplemented by borescope, chip-detector debris, vibration signatures and SOAP.
  - Sources: ARL 1985, p. 6 (https://archive.org/details/DTIC_ADA164562); IFDIS 1987, ch. 6.
- [DIRECT] **Engine control unit spares problem.** Australia had no tester for the engine control unit. The RAAF planned on 8 faulty plus 8 falsely removed units per year, with an 18-month repair pipeline.
  - Source: Forsyth 1989, App. A.3–A.4.
- [DIRECT] **EGT-bias fault test (Merrington, ARL, CP-448 paper 36).** Back-to-back F404 tests with a faulty EGT harness (bias about 60 °C) changed the identified fan-spool gain K_N and time constant τ_N: about 22.1 and 2.11 s with the fault (the no-fault values are garbled in OCR).
  - Event-record sampling of 5–10 Hz is described as typical.
  - The simulation noise assumed was NL σ about 0.3 % and WF σ 0.6 % at 50 Hz (NL value is an OCR-uncertain reading).
- [DIRECT] **Ways GE and the Navy test centre suggested to implant faults.** Set the variable guide vanes to their limits; reset the density corrector; move the T2.5 sensor; change nozzle actuator lengths; bleed off PS3.
  - The engine control unit has three trim potentiometers: N1 ±300 rpm (about 10 rpm per click), T5 +15 °F (about 2.5 °F per click), AB ratio units ±65.
  - Source: Glenny, ARL-PROP-TM-455 (1989), pp. 13–17. https://archive.org/details/DTIC_ADA210374
- [DIRECT] **RAAF test-cell vibration limits** (DSTO-TN-0530, Marsden 2003, Table 4 and App. A), in inches/s average. https://archive.org/details/DTIC_ADA423658
  - Front frame: 1.5 (N1 1/rev and overall, steady); 2.0 (transient).
  - Mid-frame (the IECMS accelerometer, 4 o'clock): 1.0 (N1 and N2 1/rev and overall, steady); 2.0 (transient).
  - Rear mount ring: N1 1/rev 1.0, N2 1/rev 1.3, overall 1.0 steady (1.5 in AB), 5.0 transient.
  - The transient limit stays in force for 5 s after an N2 change.
  - Baseline overall levels go from about 0.15–0.3 ips at idle to 0.5–1.0 ips at military power/AB.

### Finland, Switzerland, Spain
- **Not found publicly within this session.** No primary sources were reached before the search budget ran out. Hess notes Spain operated the F/A-18 IECMS in 1988. That is the only mention.

---

## Q4. Public PHM / degradation / fault studies and real data

### Reliability and life data (DIRECT)
- **F404 fleet, 1987–90** (NAVAIR via King & Tooker, Table 2.1):

| Measure | Actual | Goal |
|---|---|---|
| MTBF | 67.4 h | >72 h |
| Mean time between maintenance actions | 19.0 h | — |
| Removals per 1,000 EFH | 3.7 | <2.0 |
| Maintenance man-hours per EFH | 0.8 | — |
| MTTR | 6.2 h | — |

- **NAVAIR 1993 life reductions** (King & Tooker, Table 1.1, original → FY94 hours):
  - HPC stage 1–2: 2,240 → 1,500
  - HPT disk: 10,500 → 7,200
  - HPT cooling plate: 2,100 → 1,600
  - LPT disk: 10,520 → 6,240
  - Reductions ranged 14–64 %, averaging 46 %.
  - **The printed table is internally inconsistent for the fan rows.** Stage 1 5,850 → 1,870 implies 68 %, but 62.3 % is printed. I checked the page image; this is in the source, not an OCR error.

### Test-cell diagnostics (DIRECT)
- Roemer et al. (2002), F404 test-cell upgrade at NAS Jacksonville. https://archive.org/details/DTIC_ADA408947
  - Gas-path data at 1–10 Hz (10 Hz specified); vibration at ≥2.5 kHz, 10 kHz preferred, 1 Hz–1 kHz band with <2.5 Hz resolution.
  - Most common sensor faults: accelerometer harnesses, CVG and FVG position sensors, CIT probes, PT5 probes, EGT thermocouples, wiring.
  - Methods: fuzzy logic and neural-network sensor validation fused with Dempster–Shafer.

### Fault-injection guidance for synthetic data (TRANSFER)
- [TRANSFER: same engine, test cell] Faults that show clearly in transient data: HPC damage, control-unit trim shifts, EGT harness bias, fuel-control over-fuelling (seen in fuel-ratio-unit traces before a flameout), and variable-geometry misadjustment. These are good candidates for injected faults.

### Public datasets
- **None found for the F404/F414.**
- Digitisable material:
  - CP-448: fuel-ratio-unit traces, acceleration-time trends, PS3 left/right traces, fault-signature bar charts, 18-month trend plots, Henry's cross-plots.
  - QFDA iron wear-rate scatter plots.
  - The 2009 F404-GE-400 bio-fuel test (NAWCADPAX/TR-2010/22E) has corrected-parameter plots, but only as JP-5 vs blend deltas with a ±1 % acceptance band. https://archive.org/details/DTIC_ADA517278

---

## Q5. HAL Tejas (F404-GE-IN20), KAI T-50 (F404-GE-102) and Tejas Mk2 (F414-INS6)
- [DIRECT] **ADA's own description of Tejas engine monitoring.** ADA's Propulsion directorate page says the Tejas has an onboard Engine Condition Monitoring System. It shows real-time engine status in the cockpit, logs engine usage data to compute life usage indices for life-limited parts, and includes vibration monitoring. https://www.ada.gov.in/images/ps.htm
  - Nothing public gives its parameters, rates, triggers or algorithms.
- [DIRECT] **Funding and recorder line items in ADA's 2015-16 annual report.**
  - An "Engine Health Monitoring" investment line under General Systems in Naval LCA FSED Phase 1: Rs 57.48 million cumulative to 31 March 2016, against 32.42 million the year before (p. 87).
  - "Mission Preparation & Data Retrieval Unit" (Rs 24.8 million) and "Crash Data Recorder" (Rs 51.6 million) under Air Force FSED Phase 2 avionics (p. 75).
  - IN20 engines power PV6 and LSP2–LSP8 (p. 11).
  - https://www.ada.gov.in/images/Annual_Report_2015-16.pdf
- [DIRECT] **Other Tejas items on ADA pages.**
  - FADEC engine control and a jet fuel starter for ground start and in-flight relight. https://www.ada.gov.in/images/PS%20Integration%20facilities.htm
  - A dual-redundant Utility Systems Management System computer. https://www.ada.gov.in/images/sys.htm
- [DIRECT] **"Indigenous HUMS" for the LCA Mk1A** (ADA annual reports 2018-19 to 2021-22, scanned; I OCR'd them). Listed under IFCS: design studies done (2018-20); vendor purchase order (2020-21); "HUMS development to meet Mk1A requirements being initiated" (2021-22). The reports do not say whether it covers the engine.
- [DIRECT] **GE statements on the IN20.**
  - FADEC; single-crystal turbine blades; higher-flow fan; derived from the -402; above 19,000 lb (85 kN) thrust.
  - 330 h of Accelerated Mission Testing, equated to 1,000 h of flight.
  - Orders: 17 engines in 2004, 24 more in 2007; 99 engines for $716 million (2021).
  - Sources: https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-engines-ordered-india-light-combat-aircraft ; https://www.geaerospace.com/news/press-releases/defense-engines/hindustan-aeronautics-ltd-orders-99-f404s-tejas-light-combat
  - GE data sheet, IN20: 84 kN, 153 lb/s, pressure ratio 28:1. https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf
- [Aggregator only: Wikipedia, unverified] IN20 delivery delays (first engine 25 March 2025) and a 113-engine deal on 7 November 2025.
- [DIRECT] **KAI T-50 (F404-GE-102).** GE says only that it is a T-50 derivative supplied by Samsung Techwin. FADEC and single-engine redundancy are stated on Wikipedia without a citation. **Monitoring details: not found publicly.**
- [DIRECT] **F414-INS6 (Tejas Mk2).** Selected by ADA (GE F414 data sheet). **Monitoring details: not found publicly.**
- **CAG 2015 LCA audit:** the cag.gov.in PDF URLs I tried returned 404, and The Hindu summary could not be fetched. **The DIAT in-flight health monitoring article** (Indian Express, 2011) could not be fetched.
- [TRANSFER: F404-GE-402 → IN20] The IN20 derives from the -402, but replaces the -400/-402 analog control unit plus hydromechanical fuel control with a FADEC. On an aircraft with a USMS and FADEC, the 10 Hz/1 Hz parameter set, LUI concepts and event logic likely carry over conceptually.
  - [ASSUMPTION] On a FADEC engine the recorded signals and life counting would come from the FADEC rather than a separate converter, and quantisation would differ from the MSDC figures.
  - How to validate: HAL or ADA technical orders, or IAF maintenance documentation.

---

## Monitoring system tables

### A. F/A-18A–D IECMS (F404-GE-400/402)

| Item | Content | Source |
|---|---|---|
| Parameters | 13 engine sensors (5 dedicated to IECMS) plus airframe Mach, altitude, TT, AOA, Nz, fuel pressure/temperature. Recorded list in the 10 Hz/1 Hz table above. Later C: SDC bus words EGT, CDP, TDP, NL, NH, T1, oil pressure, nozzle %, Wfm, fuel inlet temperature, T5. | Hess p. 2-5; Muir Table 1; ADA407860 Table E-3 |
| Rates | 10 Hz gas path/flight; 1 Hz for oil pressure, vibration, fuel temperature, valve/door positions, Nz | Muir et al. Table 1 |
| Triggers | Exceedance (N1, N2, EGT, oil pressure, vibration); sensor-range fail; flameout (PS3 and speed logic); take-off; pilot button. 44 engine MMP codes. Exceedances should persist several iterations. | Paré & Muir pp. 2–3; Hess pp. 2-5 to 2-7 |
| Stored data | Event records 5 s pre + 25 s post (Navy) or + 35 s post (CF). Take-off record 6–10 s. LUI sums written twice per flight. Tape 7–10 flights; also airframe fatigue and crash data. | Hess; Muir; Paré & Muir |
| Life algorithms | 8 LUIs (Type I / Type III N2 cycles, EFTC, SRC, TAMP, full/partial PS3 cycles, EOT). Thresholds and weighting functions are not public. | Hess pp. 2-5 to 2-6 |
| Ground use | Navy: ECAMS → PLTS, later AEMS DSS / SAME / NALCOMIS / DECKPLATE. CF: PCGS → ECMS (FLTS, Life Usage Monitor, Performance Monitor, Logistics Planning Model). RAAF: UCF / MD&SLMS / CAMM, IFDIS prototype. | see Q1/Q3 |

### B. F/A-18E/F advanced IECMS (F414-GE-400)

| Item | Content | Source |
|---|---|---|
| Parameters | FADEC sensors + airframe computers; engine-mounted master electrical chip detector; vibration; oil pressure. Full list unknown. | Hall 2001 abstract and index terms; Hood et al. pp. 17–18 |
| Rates | unknown (index term "Hz rate" only) | — |
| Triggers | More cautions/advisories and maintenance codes; full list unknown | Hood et al. |
| Stored data | Expanded memory-unit recording; downloaded every flight | Hood et al.; Hersey et al. p. 15 |
| Life algorithms | LUI from 9 matrices / 214 elements; HPT limit in LUI hours; ELCF at 1.2 per EOT hour for forecasting | Hersey et al.; Schoch App. C |
| Ground use | SAME server → 72N report; AEMS DSS; NALCOMIS; DECKPLATE | Hersey; Hagan & Slack; Hood |

### C. Tejas ECMS (F404-GE-IN20)

| Item | Content | Source |
|---|---|---|
| Parameters | unknown ("real-time engine status"); FADEC-controlled engine | ADA ps.htm; PS facilities page |
| Rates | unknown | — |
| Triggers | unknown | — |
| Stored data | engine usage log; MPDRU and crash data recorder exist | ADA ps.htm; AR 2015-16 p. 75 |
| Life algorithms | "life usage indices of life-limited parts" (details unknown) | ADA ps.htm |
| Ground use | unknown; ASMS maintenance trainer exists | ADA asms.htm |

### D. RAAF/USN F404 test cells (ground layer)

| Item | Content | Source |
|---|---|---|
| Parameters/rates | Gas path 1–10 Hz; vibration ≥2.5–10 kHz; 3 accelerometers; N1/N2 tracking | Roemer 2002; DSTO-TN-0530 |
| Triggers/limits | 1.0–1.5 ips steady, 2.0–5.0 ips transient (see Q3) | DSTO-TN-0530 Table 4 |

---

## Source conflicts flagged
1. **Event record length:** 5 s + 25 s (Hess; MIL-E-5007E) vs 5 s + 35 s (Canadian sources).
2. **Tape capacity:** about 7 flights (Hess) vs 7–10 flights (Paré & Muir).
3. **"Continuous recording of 13 parameters"** (Schofield) vs triggered recording (all other sources).
4. **Converter name:** MSDC (1980s) vs SDC (2000 F/A-18C). The recorder set is also named inconsistently: "Maintenance Signal Data Recording Set" vs "Maintenance Data Signal Recording System".
5. **F414 module limits/intervals** differ between 2003, 2008 and 2013 sources.
6. **NAVAIR 1993 fan-row "% lost"** is inconsistent with the printed hours.
7. **Lifed component count:** 26 (CF) vs "twenty odd" (ARL 1985).
8. **MTBF definitions** differ: F404 67.4 h (1987–90, all failures) vs F414 582 h (2012).

## Gaps
- **Not retrieved:**
  - Doane & Kinley, AIAA-83-1237: the AIAA site blocked access with a bot check, which I did not bypass.
  - Hall et al. 2001 full text (paywalled).
  - Cue & Muir, ASME 90-GT-357, and AGARD-CP-480.
- **Not found publicly:** IECMS limit values (EGT, N1/N2 overspeed, oil pressure, in-flight vibration thresholds); the LUI threshold and weighting functions; the MMP code dictionary (only 709/759 seen); F414 IECMS parameter list and rates; TAC for the F404.
- **Not reached (search budget):** Finland, Switzerland, Spain; further DSTO RAAF usage and LCF reports; the US Navy "SEMS/ECMS" names; DECKPLATE details.
- **India:** no public IN20 ECMS details; the CAG 2015 report could not be retrieved; nothing on T-50 or F414-INS6 monitoring.

## Top sources for deep reading (ranked)
1. **AGARD-CP-448 (1988)**, papers 2, 4, 7, 36 and 37 — the architecture, parameter/rate table, precision table, LUI definitions and trending methods, with digitisable plots. https://archive.org/details/DTIC_ADA203800 (local `DTIC_ADA203800.pdf`)
2. **Paré & Muir (1998)** — the complete CF ECMS ground architecture and quantified benefits. https://archive.org/details/DTIC_ADA347270
3. **NAWCADPAX/RTR-2001/1** — the F/A-18C 1553 engine word list with units (a schema template). https://archive.org/details/DTIC_ADA407860
4. **DSTO-TN-0530** — F404 vibration limits and baseline levels by power setting. https://archive.org/details/DTIC_ADA423658
5. **Schoch (2003) and Hersey et al. (2008)** — F414 life limits, ELCF conversion, AEMS reports and removal codes. https://archive.org/details/DTIC_ADA418270 , https://archive.org/details/DTIC_ADA493918
6. **Hood, Khan & Story (2013)** — F414 MTBF and intervals, and a summary of Hall et al. https://archive.org/details/DTIC_ADA585693
7. **King & Tooker (1993)** — F404 life-reduction table and reliability metrics. https://archive.org/details/DTIC_ADA277918
8. **Bennett et al. QFDA (1996)** — F404 oil-debris wear-rate statistics. https://archive.org/details/DTIC_ADP010173
9. **Hagan & Slack (2006)** — the 14-day records-reconciliation finding, directly relevant to the problem statement. https://archive.org/details/DTIC_ADA462668
10. **ADA ps.htm and ADA annual reports** — the only primary Indian statements on Tejas engine monitoring.

## Suggested scores (0–5)

| Engine | Monitoring / sensor documentation | Degradation / PHM literature | Real data availability | Indian relevance |
|---|---|---|---|---|
| F404-GE-400/402 | **4** — architecture, rates, triggers, LUIs, precision public; limits and algorithms not | **3** — CF and ARL trending, fault library, oil debris, EGT bias; key ASME/AIAA papers unread | **2** — tables and plots only, no datasets | **3** — the IN20 is a -402 derivative; methods transfer, hardware differs (FADEC) |
| F404-GE-IN20 | **1** — one ADA paragraph plus FADEC | **0** | **0** | **5** |
| F404-GE-102 | **0.5** — FADEC only (uncited) | **0** | **0** | **2** — the closest architectural analogue (single-engine, FADEC) to the IN20 |
| F414 | **2.5** — Hall abstract, LUI matrices, data flow, life limits | **1.5** | **1.5** — MTBF and removal statistics | **4** — INS6 for Tejas Mk2 and AMCA |

## Synthetic-data takeaways [ASSUMPTION, grounded in the DIRECT figures above]
- Stream gas-path channels at 10 Hz and slow channels at 1 Hz.
- Quantise with the converter resolutions (about 16 rpm, 1 K, 0.5 psia) and add the 2σ noise from Henry's table.
- Build event snapshots of 5 s pre plus 25 or 35 s post, and a 6–10 s take-off record per flight.
- Accumulate the 8 LUIs per flight. For the F414, use about 1.2 ELCF per EOT hour.
- Emit 3-digit MMP-style codes and Navy removal-reason codes.
- Batch downloads every 7–10 flights (tape era); for F414 or Tejas, download after every flight.