# Fighter Operating/Flight Profiles, Usage Statistics and Operating Variables (Ground Power-up to Shutdown) — for the Phalanx virtual-fighter telemetry layer

Scope note for the report writer. Project Phalanx needs a virtual fighter whose physical/operational state produces realistic observations. These notes cover sortie phases, mission types, engine duty cycles, structural usage spectra, envelope limits, Indian environmental conditions and methods to synthesise varied sortie instances. Candidate platforms: Tejas Mk1/Mk1A (F404-GE-IN20), F-16 (F100/F110), F/A-18A-D (F404), Gripen C/D (RM12), Su-30MKI (AL-31FP).

Evidence tags used throughout:
- **[DIRECT]** = statement is about that exact aircraft/engine/force.
- **[TRANSFER: X]** = taken from platform/force X; the reason it transfers and its limits are stated.
- **[ASSUMPTION]** = engineering judgement or textbook practice not verified in a source this session; validation route stated.
- **[INFERENCE]** (used inside the "Inferences" subsections) = arithmetic or reasoning on cited numbers.

Important provenance and research-process caveats:
1. **Restricted-distribution manuals.** Two of the richest phase-by-phase sources are flight manuals circulating publicly on publicintelligence.net, but they were *not officially released to the public*:
   - The F/A-18A/B/C/D NATOPS Flight Manual A1-F18AC-NFM-000 (15 Sep 2008) carries "DISTRIBUTION STATEMENT C … U.S. Government agencies only and their contractors" ([NATOPS cover](https://info.publicintelligence.net/F18-ABCD-000.pdf)).
   - The Hellenic Air Force F-16C/D Block 50/52+ Flight Manual T.O. GR1F-16CJ-1 (15 Oct 2002, Change 1, 15 Jun 2003) carries a foreign-disclosure statement ([HAF F-16 manual cover](https://info.publicintelligence.net/HAF-F16.pdf)).

   The values used from them (start sequence, idle bands, limits, pattern speeds) are unclassified operating data. However, they are **not "publicly released"** in the strict sense of the project constraint. The team should decide whether to cite them in deliverables, or to use them only to sanity-check parameter ranges. Wherever possible a public source is also given.
2. **DTIC outage and archived copies.** DTIC (apps.dtic.mil) was under maintenance during this session. RTO-TR-028 (DTIC ADA380949) was retrieved from an Internet Archive copy of the DTIC URL. All other DTIC-hosted reports (e.g., ASD-TR-82-5012 Nz exceedance handbook) could not be read.
3. **Web-search budget exhausted.** The shared web-search budget for this turn ran out partway through (a limit of 200 searches shared across all parallel agents). After that, only direct fetches of known URLs were possible. The specific gaps that further searching would close are listed in each Gaps section and in (e) at the end. The user can send a follow-up to resume searching, or raise the search limit.
4. **Local copies.** Downloaded source PDFs are saved in `/Users/abishaikc/Phalanx/research_sources/flight_profiles/`: JSSG-2007A, JSSG-2006, MIL-HDBK-1783B CHG-2, MIL-A-8866C, RTO-TR-028, the F/A-18 NATOPS, the HAF F-16 manual and checklist, the ADA Tejas brochure, the IMD Climatological Tables 1991-2020, the Chalmers RM12 thesis, NACA RM L54E18, NASA TM-85902, the CF-18 wing test paper, the ICAF 2023 and ICAS 2008 papers, and the GE F404/F110 datasheets.

Cross-links to parallel researchers:
- **Platform selection, airframe/engine data**: envelope numbers in Q5.
- **Sensor residual texture**: sampling-rate and accuracy table in Q3/Q7.
- **Faults/degradation**: deterioration, hot-day margin, reburst and QRA-start damage in Q3.
- **Validation/calibration**: calibration targets in (c) and (d).
- **Maintenance records**: TAC/EFH bookkeeping in Q3.
- **Modelling methodology**: corrected parameters in Q6, mission generator in Q7.
- **Data pathway/formats**: recording rates and per-flight records in Q7.

---

## Q1. Phase-by-phase behaviour of a 4th-gen single/twin-engine fighter sortie (power-up → shutdown), including touch-and-go and go-around

### Takeaway
Flight manuals give hard numbers for the start sequence, idle bands, run-up checks, takeoff technique, pattern and approach angle of attack (AoA), landing roll-out and shutdown cooldown:
- **F404 (F/A-18)**: idle N2 61–72 %, EGT 190–590 °C, fuel flow (FF) 420–900 pph, oil pressure 45–110 psi; on-speed approach 8.1° AoA.
- **F-16 (F100-PW-229 / F110-GE-129)**: idle 62–80 % rpm, FTIT ≤ 625–650 °C, FF 500–1,700 pph; approach 11–13° AoA; drag chute deployed at 90–170 kt.

Durations of the ground phases are less precisely documented. Design-usage data implies roughly 0.45 h of ground engine time per flight; MIL-HDBK-1783B guidance says 0.75–1.0 h. Tejas-, Gripen- and Su-30-specific phase numbers are largely not public. Use F404/F-16 data as a transfer basis: Tejas and Gripen both use F404-family engines.

### Cited Findings

**A. Power-up and pre-flight BIT / alignment**
- [DIRECT F/A-18] APU start: with the APU switch ON, the READY light comes on within 30 s. A minimum of 2 min must elapse between APU shutdown and another APU start. After both generators are on line, the APU runs for 1 min and then shuts down — [NATOPS §7.1.5, pp. III-7-13 to III-7-15](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F/A-18] Battery checks before start:
  - E-BATT and U-BATT voltage must be at least 23.5 V after the battery switch has been ON/ORIDE for at least 5 s.
  - Down to −18 °C, 20.5 V on U-BATT is acceptable.
  - Source: [NATOPS §7.1.5, p. III-7-14](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F/A-18] INS ground alignment:
  - The platform levels for the first 1–2 min (AN/ASN-130A), with NO ATT displayed.
  - Time to align is "normally less than 10 minutes" (CV align).
  - Best accuracy needs a heading change of at least 70° (180° optimum) after OK.
  - Source: [NATOPS §24.2.3, pp. VII-24](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F/A-18] Other warm-ups and BITs:
  - Helmet-mounted display tracker unit warm-up is 15–20 min.
  - The OBOGS monitor runs a power-up BIT during a 2-min warm-up, then a periodic BIT every 60 s.
  - The OBOGS degraded caution must set and clear within 15 s on BIT.
  - Source: [NATOPS pp. I-2 (OBOGS monitor), III-7-22](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F-16] Flight control system BIT takes "approximately 45 seconds" — [HAF F-16 manual, Before Taxi, p. 2-13](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F-16] EPU check is done anytime after engine start, with engine rpm raised 5 % (PW229) or 10 % (GE129) above normal idle. The EPU run light must come on within 10 s — [HAF F-16 manual, p. 2-19](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT Tejas] The Tejas Mk1 jet fuel starter was upgraded to the HAL GTSU-110 M1. An onboard Engine Condition Monitoring System "provides real time Engine Status in the Cockpit and Logs the Engine Usage Data to Compute Life Usage Indices of Life limited Parts" and also tracks vibration — [ADA Tejas brochure (Dec 2013), p. 9](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf).
- [DIRECT Tejas] The aircraft-mounted accessories gearbox (AMAGB) takes a single input from the engine power take-off and drives two hydraulic pumps, one generator and one starter unit — [ADA brochure p. 10](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf).

**B. Engine start sequence and idle stabilisation**

*F-16 with F100-PW-229, jet fuel starter (JFS) start* — [HAF F-16 manual, Starting Engine PW 229, pp. 2-8 to 2-9](https://info.publicintelligence.net/HAF-F16.pdf) [DIRECT]:
- The JFS RUN light comes on within 30 s; engine rpm then rises.
- At about 15 % rpm, hydraulic and fuel pressures rise; the SEC caution goes off by about 18 %.
- The throttle goes to IDLE at a minimum of 20 % rpm.
- Light-off occurs **within 20 s** of throttle advance (airframe vibration, rpm rise, then FTIT rise).
- The JFS shuts down automatically at about 50 % rpm; the standby generator comes on line at about 55 % rpm; the main generator follows 5–10 s later.
- "FTIT … normally peaks at less than 625 °C."
- Idle check values:
  - FF 500–1,500 pph
  - oil ≥ 15 psi
  - nozzle position > 80 %
  - RPM 65–77 %
  - FTIT ≤ 625 °C
  - hydraulic pressure 2,850–3,250 psi

*F-16 with F110-GE-129* — [HAF F-16 manual, Starting Engine GE 129, pp. 2-10 to 2-11](https://info.publicintelligence.net/HAF-F16.pdf) [DIRECT]:
- The throttle goes to IDLE at 20 % rpm, or at maximum motoring rpm if ambient ≥ 90 °F (32 °C).
- Light-off occurs **within 10 s**.
- The JFS shuts down at about 55 % rpm; the standby generator and ENGINE light off at about 60 % rpm.
- On hot days (> 90 °F) the ENGINE warning light may stay on until idle (> 70 % rpm).
- Idle check values:
  - FF 700–1,700 pph
  - oil ≥ 15 psi
  - nozzle > 94 %
  - RPM 62–80 %
  - FTIT ≤ 650 °C

*F-16 starting limits* — [HAF F-16 manual Fig. 5-2, Fig. 5-4, pp. 5-8 to 5-12](https://info.publicintelligence.net/HAF-F16.pdf) [DIRECT]:
- Ground start FTIT limit: 800 °C (PW229) or 935 °C (GE129).
- Continuous JFS motoring ≤ 4 min, then 5 min of cooling.
- At least 1 min wait between JFS start attempts.
- After a hot start, motor until FTIT < 200 °C.
- For a quick restart after shutdown, motor 1–4 min until FTIT < 200 °C.
- Motoring is defined as ≥ 22 % (PW229) or ≥ 25 % (GE129) rpm with the throttle OFF.

*F/A-18 with F404* — [NATOPS §7.1.5 pp. III-7-15 to III-7-17; §4.1.1 pp. I-4-1 to I-4-2](https://info.publicintelligence.net/F18-ABCD-000.pdf) [DIRECT]:
- The air turbine starter (ATS), driven by APU/external/crossbleed air, cranks the engine through the AMAD.
- Throttle to IDLE at a minimum of 15 % rpm.
- "Maximum EGT during start is 815 °C."
- The crank switch returns to OFF at about 60 % rpm.
- Crossbleed start needs the running engine at ≥ 80 % rpm and ≥ 1,900 pph.
- Ground idle:

  | Parameter | F404-GE-400 | F404-GE-402 |
  |---|---|---|
  | N2 | 61–72 % | 63–70 % |
  | EGT | 190–590 °C | 190–590 °C |
  | Fuel flow | 420–700 pph | 420–900 pph |
  | Nozzle | 73–84 % | 73–84 % |
  | Oil (warm) | 45–110 psi | 45–110 psi |

- Above −18 °C ambient, oil pressure must peak below 180 psi and begin decreasing within 30 s of reaching idle.
- Flight idle is 68–73 % N2.

*Thermal-soak restart rule* [DIRECT F/A-18]: if the engine was not idled 5 min before shutdown and a restart is needed between 15 min and 4 h later, motor it for 1 min at 24 % N2 — [NATOPS p. III-7-13](https://info.publicintelligence.net/F18-ABCD-000.pdf).

*Ambient effect on starting* [TRANSFER: generic military turbofan spec guidance]: "start times will be longer at both high and low inlet air temperatures than at standard day temperature." Cold starts are slower because of oil viscosity; hot starts because of low-density air. Degraded APU, battery or starter also lengthens starts — [JSSG-2007A §A.3.2.2.3, p. 156](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf).

*Cold weather* [DIRECT F/A-18]:
- Below −23 °C, set the operating engine to ≥ 1,900 pph (72–75 % rpm) for crossbleed; the start may take 5 s longer.
- Avoid hydraulic actuation for 2 min after both engines are on line.
- Maintain ≥ 70 % rpm before taxi.
- Source: [NATOPS Ch. 22, p. VI-22-1](https://info.publicintelligence.net/F18-ABCD-000.pdf).

**C. Idle behaviour depends on ambient and flight condition**
- [DIRECT F-16 PW229]:
  - Ground idle: nozzle > 80 %, rpm 65–77 %.
  - Flight idle (gear up): nozzle 0–20 %, thrust about 700 lb higher than ground idle.
  - Transient idle provides fast response if the throttle is re-advanced within 20 s.
  - "Since the DEEC maintains constant idle thrust, rpm varies with temperature and pressure altitude (higher temperature or pressure altitude results in higher rpm)."
  - Below about 30,000 ft MSL, flight-idle rpm is 70–80 % and rises with altitude.
  - Source: [HAF F-16 manual pp. 1-39 to 1-40](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F-16 GE129] The engine control likewise holds constant idle thrust and minimum bleed pressure, so rpm rises with temperature and pressure altitude. VSV reset raises idle rpm by 2–3 %; anti-ice can add up to 3 % — [HAF F-16 manual, Sec. I "Engine Operating Characteristics GE 129"](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F/A-18] "With high ambient temperature and low fuel flow (IDLE rpm) it may be necessary to increase fuel flow to prevent a FUEL HOT display" (feed fuel > 79 °C) — [NATOPS §2.2.6.1, p. I-2-16](https://info.publicintelligence.net/F18-ABCD-000.pdf).

**D. Taxi, run-up and pre-takeoff checks**
- [DIRECT F/A-18] Taxi:
  - Check brakes and nosewheel steering.
  - "At high gross weight, make all turns at minimum practicable speed and maximum practicable radius."
  - Wet brakes can lose up to 50 % of braking capacity.
  - Source: [NATOPS §7.1.7, pp. III-7-22 to III-7-23](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F-16] "Do not ride the brakes to control taxi speed. Use one firm application" — [HAF F-16 manual p. 2-18](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F/A-18] Optional MIL check before takeoff — [NATOPS §7.2.1, p. III-7-23](https://info.publicintelligence.net/F18-ABCD-000.pdf):

  | Parameter | F404-GE-400 | F404-GE-402 |
  |---|---|---|
  | N2 | 92–102 % | 90–102 % |
  | EGT | 715–830 °C | 715–880 °C |
  | Fuel flow | 6,000–9,000 pph | 6,000–12,500 pph |
  | Nozzle | 0–57 % | 0–48 % |
  | Oil | 95–180 psi | 95–180 psi |

- [DIRECT F-16]
  - Run up to about 85 % (PW229) or 90 % (GE129) rpm, check instruments, then release the brakes.
  - "An engine runup check is not required if conditions require a rolling takeoff."
  - Source: [HAF F-16 manual p. 2-20](https://info.publicintelligence.net/HAF-F16.pdf).
- [TRANSFER: Navy ground-loads spec → all land-based fighters; it is a design spectrum, not measured usage] Per taxi run, design repeated-load assumptions are:
  - hard braking (μ = 0.8) twice
  - medium braking five times
  - turning with 0.4 W side load five times
  - one pivot per three taxi runs

  Source: [MIL-A-8866C §3.7.3, p. 6](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF). JSSG-2006 gives "hard braking … twice per landing and medium braking … five times per landing" and "one [pivot] per ten landings" as typical entries — [JSSG-2006 §A.3.2.14.3(g), p. 141](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2006.010206.PDF).

**E. Takeoff (MIL vs AB), rotation, gear and flap retraction**
- [DIRECT F-16] Takeoff power and rotation — [HAF F-16 manual pp. 2-20 to 2-21](https://info.publicintelligence.net/HAF-F16.pdf):
  - "Maximum FTIT and rpm vary with temperature and pressure altitude but stabilize in 5–15 seconds."
  - Normal MIL takeoff: nozzle ≤ 20 % (PW229), or ≤ 15 % after 5 s at MIL (GE129).
  - AB takeoff: nozzle starts opening within 5 s (PW229). GE129 AB light-off within 5 s if > 40 °F, or within 10 s if ≤ 40 °F.
  - Spacing of less than 15 s behind a preceding AB takeoff raises AB blowout risk.
  - Rotate about 10 kt (non-AB) or 15 kt (AB) below computed takeoff speed to an 8–12° attitude.
  - Use nosewheel steering until the rudder is effective (about 70 kt).
  - "Insure LG is up and locked before exceeding 300 knots."
- [DIRECT F-16] Tire limits: MLG 225 kt groundspeed; NLG 217 kt (PX II) or 235 kt (PX III) — [HAF F-16 manual p. 5-2](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F/A-18] Takeoff technique — [NATOPS §7.2.2–7.2.5, pp. III-7-23 to III-7-25; Fig. 4-1, p. I-4-3](https://info.publicintelligence.net/F18-ABCD-000.pdf):
  - Takeoff trim 12° nose-up; hold aft stick until 6–8° nose-high.
  - Minimum-run takeoff: full AB, 10–12° nose-high.
  - Gear up when "definitely airborne"; flaps to AUTO.
  - Nose tire limit 190 kt groundspeed (main 210 kt); gear and flaps half/full limit 250 kt.
  - An improperly serviced nose strut can raise nosewheel lift-off speed by up to 10 kt.
- [DIRECT F404] The engine spools "from idle to full afterburner in 4 seconds" (GE claim, via [Wikipedia: General Electric F404](https://en.wikipedia.org/wiki/General_Electric_F404)).
- [TRANSFER: USAF/Navy spec guidance for TJ/TF fighter engines] Recommended maximum standard-day transient times:

  | Transient | Max time |
  |---|---|
  | Idle → intermediate (SL–10,000 ft, 0–150 kt) | 5 s |
  | Idle → maximum | 7 s |
  | 30 % → 100 % intermediate | 4 s |
  | Idle → intermediate above 10,000 ft | 12 s |
  | Idle → maximum above 10,000 ft | 14 s |
  | Intermediate ↔ maximum | 2 s |

  The "tiger start" (first start of day, idle dwell ≤ 90 s) represents alert/base-escape — [JSSG-2007A §A.3.2.2.7, pp. 170–174](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf).

**F. Climb**
- [DIRECT F/A-18] "For visibility over the nose, maintain 350 knots to 10,000 feet." Optimum climb is in the performance volume (NFM-200, not available) — [NATOPS §7.2.6, p. III-7-25](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F-16] Climb schedules — [HAF F-16 manual p. 2-22](https://info.publicintelligence.net/HAF-F16.pdf):
  - Defined by airspeed/Mach: climb at the scheduled airspeed to the scheduled Mach, then hold Mach.
  - The MIL schedule gives optimum range; the MAX AB schedule gives minimum time to climb.
  - Both are tabulated against drag index in T.O. GR1F-16CJ-1-1 (not available).
- [DIRECT F-16 PW229] With the gear handle DN and for 3 min after it is placed UP, the DEEC may close the RCVVs for stall margin. This raises MIL rpm by up to 2 %; rpm may drop up to 2 % after 3 min — [HAF F-16 manual p. 1-40](https://info.publicintelligence.net/HAF-F16.pdf).

**G. Cruise**
- [DIRECT F/A-18] "Maximum range cruise is approximated by establishing 4.2° [AoA], but no faster than Mach 0.85. Maximum endurance is approximated by establishing 5.6° AOA."
  - Cabin pressure: 8,000 ft cabin up to 23–24 kft; 10–12 kft cabin at 30,000 ft; 15–17 kft cabin at 40,000 ft.
  - Source: [NATOPS §7.2.8, p. III-7-26](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F/A-18] With JP-4 and takeoff ambient > 85 °F, idle decelerations between M1.23 and M0.9 may cause flameout — [NATOPS §7.2.8, p. III-7-26](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F-16] Cruise speed 504 kt (spec table) — [Wikipedia: F-16 specifications](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon).

**H. Mission segments (ACM/BFM, intercept, ground attack, low level, formation, aerobatics, supersonic dash, AAR)**
- [DIRECT F-16] Flight control limiters — [HAF F-16 manual, FLCS Limiters, Sec. I](https://info.publicintelligence.net/HAF-F16.pdf):
  - Below 15° AoA the maximum positive g is +9 g. In CAT I it decreases to 1 g at 25° AoA; maximum commanded AoA is about 25.5°.
  - In CAT III, maximum AoA is about 16–18°.
  - Negative g available is −3 g above about 250 kt.
- [DIRECT F-16] Over-g reporting and g-limit categories — [HAF F-16 manual pp. 5-3 to 5-4](https://info.publicintelligence.net/HAF-F16.pdf):
  - Report a possible over-g if symmetric maneuvering on the limiter results in ≥ 9.5 g / −3.2 g.
  - SYM g limits apply when roll rate ≤ 20°/s and roll inputs are not abrupt. ROLL g limits apply otherwise. This is a natural threshold for tagging asymmetric manoeuvres in synthetic data.
- [DIRECT F-16] Speed limits and prohibited manoeuvres — [HAF F-16 manual pp. 5-2 to 5-3, Fig. 5-3](https://info.publicintelligence.net/HAF-F16.pdf):
  - Maximum 800 kt from sea level to 30,000 ft; Mach 2.05 above 30,000 ft.
  - Prohibited: maximum-command rolling above M1.8 combined with > 3 g or below 35,000 ft.
  - Prohibited (CAT I): abrupt roll reversals above 550 kt below 20,000 ft.
- [DIRECT F/A-18] Supersonic restrictions — [NATOPS §4.1.3, pp. I-4-4 to I-4-5](https://info.publicintelligence.net/F18-ABCD-000.pdf):
  - At or above M1.4, roll is limited to 2 g, ½ lateral stick or 180° bank change.
  - Single-seat with external tanks: M1.8 or M1.6/635 KCAS depending on tank configuration.
  - Negative g limited to 10 s on later aircraft; 10 s minimum between negative-g manoeuvres.
- [DIRECT F/A-18] AoA limits — [NATOPS §4.1.6, pp. I-4-7 to I-4-8](https://info.publicintelligence.net/F18-ABCD-000.pdf):
  - Fighter escort configuration at CG 17–25 % MAC: "Unrestricted".
  - With A/G stores: −6° to +35° or −6° to +25°.
  - Empty external tanks on stations 2/8: −6° to +20°.
  - Flaps HALF/FULL: 0° to +15°.
- [DIRECT F-15/F100 EMD flight test] Engine response:
  - An idle-to-maximum snap at 30,000 ft/225 kt met the augmentor-initiation conditions at t ≈ 2.7 s, with a strong flame by about 4.5 s.
  - At 40,000 ft (MIL), acceleration from M1.1 to M1.15 took nearly 60 s.
  - Formation flying (10,000 ft, 400 kt) and aerial refuelling (25,000 ft, 300 kt) were used as throttle-response tasks. Thrust initially lagged throttle by nearly 180° until the DEEC software was changed.
  - Source: [NASA TM-85902, p. 3](https://ntrs.nasa.gov/api/citations/19840016520/downloads/19840016520.pdf).
- [DIRECT F/A-18] Air-to-air refuelling (drogue) — [NATOPS §9.2, pp. III-9-6 to III-9-7](https://info.publicintelligence.net/F18-ABCD-000.pdf):
  - Engaged envelope: "from the deck to 40,000 feet and 175 to 300 knots".
  - KC-135: 200–275 kt or M0.8; closure ≤ 2 kt.
  - Closure on the drogue ≤ 5 kt; the hose must be pushed 3–5 ft before fuel flows; back out at 3–5 kt.
  - Probe extend/retract ≤ 300 kt; extended ≤ 400 kt — [NATOPS Fig. 4-1](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [TRANSFER: spec guidance] "Crisp and repeatable engine response is needed during aerial refueling and aircraft carrier approaches" — [JSSG-2007A p. 174](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf). Tanking also generates many throttle excursions — [RTO-TR-028 Ch. 3, p. 3-3](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).
- [DIRECT Tejas] AoA envelope and capabilities:
  - AoA expanded from 24° (IOC-II) to 28° as a FOC criterion; in-flight refuelling also a FOC criterion — [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas).
  - "Envelope expansion upto 24 deg AOA completed", ">2430 flights", "Operational Readyness Platform scramble readiness demonstrated" (as of Dec 2013) — [ADA brochure p. 5](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf).
- [TRANSFER: Navy gust spec] Gust spectra should assume at least 4 % of life at VH at sea level — this matters for low-level segments — [MIL-A-8866C §3.6, p. 5](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF).

**I. Descent, recovery and pattern (overhead break)**
- [DIRECT F/A-18] "Normal instrument penetration is 250 knots and 4,000 to 6,000 feet per minute descent" — [NATOPS §7.3.1, p. III-7-26](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F/A-18] Field break:
  - At the break, reduce thrust (speedbrake if required). Below 250 kt, gear down and flaps FULL, then decelerate to on-speed.
  - SATS: arrive at the break at 250 kt; a 17–20 s break interval gives a 35–40 s touchdown interval.
  - Carrier: descend to 600 ft on downwind.
  - Sources: [NATOPS §7.3.2 p. III-7-27; §9.5.1; §8.2.10](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F-16] "Fly initial at 300 knots. At the break, retard throttle and open speedbrakes as required … when airspeed is below 300 knots, lower the LG … arrive on final at 11 or 13 degrees AOA." Maximum 13° AoA on final and at touchdown (Fig. 2-3) — [HAF F-16 manual pp. 2-23 to 2-25](https://info.publicintelligence.net/HAF-F16.pdf).

**J. Approach (AoA-based)**
- [DIRECT F/A-18] On-speed is 8.1° AoA:
  - "On-speed without external stores and 2,000 pounds of internal fuel is about 125 knots. Add about 2.5 knots for each 1,000 pounds increase in fuel and stores."
  - "Avoid overcontrolling the throttles as thrust response is immediate."
  - The autopilot pitch trim resets to 8.1° in the powered-approach configuration.
  - Sources: [NATOPS §7.3.2 p. III-7-27; Ch. 2/8](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F-16] Final at 11° or 13° AoA. Thrust can be reduced sooner on an 11° approach — [HAF F-16 manual p. 2-23](https://info.publicintelligence.net/HAF-F16.pdf).

**K. Landing and roll-out**
- [DIRECT F-16] Roll-out — [HAF F-16 manual pp. 2-24 to 2-25](https://info.publicintelligence.net/HAF-F16.pdf):
  - Two-point aerobraking at ≤ 13° AoA until about 100 kt (effective down to 80 kt), then lower the nose.
  - Drag chute: deploy immediately after touchdown. Above 170 kt the canopy may be lost; below 90 kt it may deploy improperly.
  - Brakes as required. Maximum brake energy per brake is 23.5 million ft·lb; in the danger zone, fuse plugs release 3–15 min after the stop — [p. 5-2](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F/A-18] Roll-out — [NATOPS §7.3.3–7.3.6, pp. III-7-27 to III-7-29](https://info.publicintelligence.net/F18-ABCD-000.pdf):
  - Throttles to IDLE at touchdown (ground idle needs WOW).
  - Get the nosewheel down, then use aft stick for stabilator braking (full aft by 100 kt).
  - Anti-skid is effective down to about 40 kt groundspeed.
  - Maximum braking: about 125 lb pedal force immediately after touchdown.
  - Aerodynamic controls become ineffective below 75–85 kt.
  - Hydroplaning: 140 kt (main) and 110 kt (nose) groundspeed.
- [DIRECT Tejas] The IAF inducted a Hybrid Brake Parachute (Gliders India) in Dec 2025: 10 kg, 17 m², deployable up to 340 km/h (180 kt) — [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas) (secondary; underlying news cited there).
- [TRANSFER: Navy design spectrum → flared field landings of land-based fighters] Sink speed per 1,000 flared field landings — [MIL-A-8866C Table I, p. 7](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF):

  | Sink speed (ft/s) | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 |
  |---|---|---|---|---|---|---|---|---|---|---|
  | Landings per 1,000 | 0.5 | 1.5 | 7 | 22 | 66 | 153 | 252 | 271 | 170 | 57 |

  The mode is 3–4 ft/s.
- [TRANSFER: same spec] Runway-roughness Nz (applications per 1,000 landings) — [MIL-A-8866C Table II, p. 8](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF):

  | Nz | 1 ± 0.05 | 1 ± 0.15 | 1 ± 0.25 | 1 ± 0.35 | 1 ± 0.45 | 1 ± 0.55 | 1 ± 0.65 | 1 ± 0.75 |
  |---|---|---|---|---|---|---|---|---|
  | Applications per 1,000 | 300,000 | 165,000 | 27,000 | 2,000 | 90 | 4 | 0.15 | 0.005 |

**L. Touch-and-go and go-around**
- [DIRECT F-16] Touch-and-go: "After touchdown, maintain landing attitude, advance the throttle, close the speedbrakes, and perform a normal takeoff" — [HAF F-16 manual p. 2-27](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F/A-18] Waveoff: "Advance the throttles to MIL or MAX as required … Raise the landing gear and flaps only after a safe climb has been established." FCLP/touch-and-go maximum gross weight is 33,000 lb (after AFC 029) — [NATOPS §7.3.10 p. III-7-30; §4.1.7 p. I-4-8](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [TRANSFER: military transport engine] Each practice touch-and-go adds one or more major engine cycles — [RTO-TR-028 Ch. 3, p. 3-4](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf). It is listed among items to validate in usage-monitor service tests — [RTO-TR-028 Ch. 7, p. 7-14](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).

**M. Taxi-in, hot refuelling, shutdown and cooldown**
- [DIRECT F/A-18] Shutdown — [NATOPS §7.4, pp. III-7-32 to III-7-35](https://info.publicintelligence.net/F18-ABCD-000.pdf):
  - "Before engine shutdown, engine should be operated at flight or ground idle for 5 minutes to allow engine temperatures to stabilize."
  - INS OFF 10 s before shutdown.
  - Hot refuelling pre-check: the fuel indication must stabilise within 45 s and must not rise more than 100 lb in the next 60 s.
- [DIRECT F-16] Shutdown — [HAF F-16 manual pp. 2-28 to 2-29](https://info.publicintelligence.net/HAF-F16.pdf):
  - EGI OFF at least 20 s before shutdown.
  - GE129: delay MAIN PWR OFF until rpm < 20 %.
  - Inlet/exhaust areas are hazardous for 10 min (PW229) or 5 min (GE129) after shutdown because of possible post-shutdown fire. If a fire occurs, motor the engine with the JFS for about 1 min.
- [DIRECT Gripen/RM12] In GKN life-tracking analyses of recorded missions, idle running before shutdown averaged **259 s** (the synthetic design mission used 660 s). Ground runs lasted 4.4–13.4 min; the average ground mission was 4.6 min — [Carlson & Gustafsson 2014, Chalmers, pp. 21–24](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf).
- [DIRECT Tejas] Hot refuelling (engine running) was carried out in Feb 2018 as part of FOC, to shorten turnaround — [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas).

**N. Ground time per flight (aggregate)**
- [TRANSFER: USAF engine design guidance] Ground operation time:
  - "Past data shows that ground operation during a mission is approximately 0.75–1.00 hours and can be added to engine flight hours per mission to derive [total operating time]."
  - Ground-run hours excluding taxi (trim and system checks) are about 5–10 % of total flight hours.
  - Source: [MIL-HDBK-1783B CHG-2, App. A.4.4, p. 42](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf).
- [TRANSFER: F-22/F119 design usage] Engine operating time is 5,400 h for 4,000 flight hours. The 1,400 ground-run hours include 50 test-cell hours, taxi, pre/post-flight checks and troubleshooting, spread over 2,938 flights — [JSSG-2007A Table XI p. 535, Table XXXVIII p. 601](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf); identification of "Aircraft H/Engine O" as F-22/F119 in [MIL-HDBK-1783B Table IV p. 34, Table XII p. 47](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf).

### Inferences
- [INFERENCE] F-22 design usage implies (1,400 − 50) h ÷ 2,938 flights ≈ **0.46 h (~28 min) of non-test-cell ground engine time per flight**, and a total-operating-time to flight-hour ratio of 1.35. MIL-HDBK-1783B's 0.75–1.0 h per mission is a more conservative bound. Sample ground time per sortie from about 20–60 min, conditioned on base layout and whether the flight is the first of the day (alignment, BIT).
- [INFERENCE] Start-to-idle duration, assembled from manual timings:
  - F-16: JFS run ≤ 30 s, plus motoring to 20 %, plus light-off ≤ 10–20 s, plus acceleration to idle (not specified).
  - F/A-18: APU ≤ 30 s plus ATS crank.
  - A synthetic start of **about 45–90 s from starter engagement to stabilised idle** is consistent with these timings. It should be validated against any recorded start trace (e.g., Tejas ECMS data, or the HAL GTSU-110 qualification report if obtainable).
- [INFERENCE] Distinct idle states should be modelled explicitly — ground idle (nozzle open, lower rpm), flight idle (nozzle closed, higher rpm, about +700 lbf on the F-16) and transient idle. Flight-idle rpm should rise with altitude and Mach, and ground-idle rpm with OAT and pressure altitude. This is a strong, realistic signature in telemetry.
- [INFERENCE] For a Tejas twin of the F404-GE-IN20, F/A-18 F404-GE-402 idle and MIL bands are the closest public transfer. The IN20 is a "-402 class" derivative with higher thrust (84 kN vs 78.7 kN) and airflow (70 vs 66 kg/s) ([GE F404 family datasheet](https://www.geaviation.com/sites/default/files/datasheet-F404-Family.pdf)), so MIL N2/EGT may sit at the upper end of the -402 bands. Single-engine installation and FADEC logic may shift idle schedules [ASSUMPTION — validate with HAL/ADA data or ECMS logs].

### Gaps
- Tejas-specific numbers were not found in public sources: start timing (GTSU-110), idle/MIL bands, takeoff/rotation speeds, approach speed/AoA, drag-chute deployment speed band, taxi limits. The ADA brochure confirms only the starter type and the ECMS. Defence Science Journal / Current Science LCA flight-test papers could not be searched after the budget ran out.
- Gripen (RM12, APU start) and Su-30MKI (AL-31FP) start sequences and idle bands: no public source found this session.
- F-16 computed takeoff speeds, approach airspeeds and climb schedules sit in T.O. GR1F-16CJ-1-1 (performance supplement), which was not read. F/A-18 performance data is in NFM-200, which was not available.
- Taxi speeds: neither manual gives numeric taxi speed limits in the procedures read. Use base standard operating procedures [ASSUMPTION].

---

## Q2. Sortie types and mission mix; sortie-length distributions; sorties/day and turnaround; annual flying hours per aircraft and per pilot

### Takeaway
- **Sortie length.** Public design and usage sources consistently put fighter sorties at about **1.0–1.5 h**:
  - F-22 design usage averages 1.36 h per flight.
  - The CF-18 recorded spectrum averages 1.17 h.
  - Gripen recorded missions run 55–174 min (median about 74 min).
- **Sorties per day.** Gripen engines average **1.7–2.7 flights per flying day**, with turnarounds as short as < 1 h. Gripen is designed for 10/20-min combat turnarounds.
- **Mission mix.** Design guidance uses 8–11 (or 14) mission profiles per type, and mission type strongly changes load-factor and engine activity.
- **Annual flying hours.** Per-aircraft and per-pilot annual hours for the IAF were **not found** in public sources this session. Only fleet-level hour totals were found for Gripen, RAAF Hornet and Swiss Hornet.

### Cited Findings
- [TRANSFER: USAF engine design guidance] "A fighter aircraft mission flight time can be 1.0 to 1.5 hours duration while a bomber … 4.0 hours" — [MIL-HDBK-1783B p. 43](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf).
- [TRANSFER: F-22 design usage] 4,000 flight hours over 2,938 flight missions (cold parts) — [JSSG-2007A Table XXXVIII, p. 601](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf). Generic JSSG guidance: 4,000 FH / 3,000 missions (fighter/attack cold parts) — [JSSG-2007A Table XXXVII, p. 600](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf).
- [TRANSFER: USAF/Navy spec] "Fighter aircraft traditionally perform 8–11 missions" (design mission types). Non-damaging dwell is removed in AMT, giving acceleration factors such as 2:1 — [JSSG-2007A §A.4.11.1.1.1, p. 440](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf).
- [TRANSFER: USN F414] "The design missions consist of 14 flight profiles, 2 ambient temperature conditions and 2 levels of engine performance deterioration," combined by weighted average — [RTO-TR-028 App. 2, p. A2-15](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).
- [DIRECT CF-18] The IARPO3a wing-test spectrum was built from Maintenance Signal Data Recording System data: 236 unique flights arranged into a 279-flight sequence representing **326 spectrum flight hours**, recorded at 10 Hz. It is a compromise spectrum for CF and RAAF usage — [Dabayeh et al. 2003, WIT Trans. Eng. Sci. 40, pp. 25–26](https://www.witpress.com/Secure/elibrary/papers/FDM03/FDM03003FU.pdf).
- [DIRECT Gripen/RM12] Mission data from one pre-fleet engine (E101) includes 14 flight missions on 7 days (1997–2013) — [Chalmers 2014, Table 5.1, p. 22](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf):
  - Flight durations (min): 54.7, 56.2, 68.4, 73.2, 72.8, 72.0, 82.3, 91.0, 89.9, 173.5, 106.3, 84.1, 71.4, 74.1.
  - Times since the previous flight: < 1 h, 2–3 h, 3–4 h, 4–5 h, 8+ h.
  - Ground missions: 5.8, 5.5, 12.4, 4.4, 13.4 min.
  - The missions were chosen "to cover different circumstances rather than to represent the average profile".
- [DIRECT Gripen/RM12] Fleet statistics — [Chalmers 2014 §5.1, p. 21](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf):
  - "The total average number of missions per day for the investigated engines are 2.25 missions/day."
  - The pre-fleet engine (used more) averaged 2.65 flights per day; the lowest-usage engine 1.74 flights per day.
  - 16 % of flying days started with a ground mission; almost twice as many days had a ground run between two flights.
  - The average ground mission is 4.6 min.
- [DIRECT Gripen] Turnaround is "10 minutes for air-to-air missions and 20 minutes for air-to-ground" with one technician and five conscripts. The design goal was operation from 500 m snow-covered strips and 800 m road bases — [Wikipedia: Saab JAS 39 Gripen](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen) (secondary).
- [DIRECT F/A-18 SATS] A 17–20 s break interval gives a 35–40 s touchdown interval — [NATOPS §9.5.1](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F-15E/F110-GE-129, Nellis AFB FSE] Two aircraft flew **536 sorties** and accumulated 1,573 EFH over 17 months (Apr 1997 – Sep 1998), with a 99.8 % mission completion rate — [GE press release, 23 Sep 1998](https://www.geaerospace.com/news/press-releases/defense-engines/field-service-evaluation-ge-powered-f-15e-highly-successful).
- [DIRECT F-15/F100 EMD flight test] 17 flights totalling 21.8 h — [NASA TM-85902, p. 3](https://ntrs.nasa.gov/api/citations/19840016520/downloads/19840016520.pdf).
- [TRANSFER: A-10 attack aircraft, via ICAF 2023 review of Newcamp, Verhagen & Curran (Aerosp. Sci. Tech. 2016)] Mission-type effects — [Mattos et al., ICAF 2023, p. 2](https://www.icaf.aero/icaf2023/proceedings/documents/75.pdf):
  - "Basic Fighter Maneuvers and Surface Attack profiles accounted for greater occurrences of vertical load factor (Nz)."
  - "Close Air Support and Navigation flight profiles are associated to a generalized lower occurrences."
  - "Load factor counts vary exponentially with flights duration."
  - "Aircraft aging has no significant effect."
- [TRANSFER: 1950s USAF jet fighters (F-86/F-84/F-94)] Load-factor peaks > 2 g per hour ranged "from 17 in transition and proficiency training to 69 in low-angle-bombing training". Instrumented operational-training missions gave 32–73 peaks/h versus 12–24 for combat and USAF training — [NACA RM L54E18, pp. 7–8](https://ntrs.nasa.gov/api/citations/19930088093/downloads/19930088093.pdf).
- [DIRECT IAF Tejas basing] No. 45 Squadron "Flying Daggers" has operated Tejas at Sulur AFS since 1 Jul 2016 — [Wikipedia: No. 45 Squadron IAF](https://en.wikipedia.org/wiki/No._45_Squadron_IAF). No. 18 Squadron "Flying Bullets" was re-raised at Sulur on 1 Apr 2020 (FOC Tejas Mk1 inducted 27 May 2020) and now flies from Naliya AFS — [Wikipedia: No. 18 Squadron IAF](https://en.wikipedia.org/wiki/No._18_Squadron_IAF). (Secondary sources.)
- [DIRECT IAF Su-30MKI basing] Bareilly, Chabua, Halwara, Jodhpur, Lohegaon (Pune), Sirsa, Tezpur, Gwalior (Maharajpur, TACDE), Thanjavur, Uttarlai — [Wikipedia: Sukhoi Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI) (secondary).
- [DIRECT RAAF F/A-18] Fleet hours and fatigue:
  - At the time of the 2018-era RCAF purchase analysis, "each of the Hornets had, on average, been flown for 4,200 hours, as compared to the nominal fatigue life of 6,000 hours."
  - In 2015 DSTG revised the fatigue damage algorithm and found the airframes "less fatigued than previously believed."
  - Source: [Wikipedia: F/A-18 Hornet in Australian service](https://en.wikipedia.org/wiki/McDonnell_Douglas_F/A-18_Hornet_in_Australian_service) (secondary; cites Cowan & Davies and Australian Aviation 2016).
- [DIRECT Swiss F/A-18] The Swiss fleet reached 50,000 flight hours in October 2008; the airframe design life was 6,000 FH — [Wikipedia: McDonnell Douglas F/A-18 Hornet](https://en.wikipedia.org/wiki/McDonnell_Douglas_F/A-18_Hornet) (secondary).
- [DIRECT Gripen/RM12] Fleet hours: over 300,000 flying hours with no engine-related accidents (Saab, Jul 2020) — [Saab newsroom](https://www.saab.com/newsroom/stories/2020/june/rm12-engine-supporting-gripen-for-more-than-300000-flying-hours). Over 143,000 fleet flight hours by Nov 2010 — [Wikipedia: Saab JAS 39 Gripen](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen).
- [DIRECT Tejas fleet history] More than 2,430 flights completed by Dec 2013 — [ADA brochure p. 5](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf). "Close to 2000 successful sorties" were flown under the IV&V regime — [ADA brochure p. 16](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf).

### Inferences
- [INFERENCE] Sortie-length model:
  - Gripen sample: mean 83.6 min, median 73.7 min, range 54.7–173.5 min, right-skewed (one 173.5-min outlier, consistent with a long transit or AAR sortie).
  - F-22 design usage: 81.7 min per flight. CF-18 spectrum: 70.1 min per flight.
  - A **lognormal sortie-duration model with median ≈ 70–80 min and 5–95 % range ≈ 45–150 min** fits all three sources. It should be conditioned by mission type (BFM/ACM shorter; navigation/AAR/ferry longer) [ASSUMPTION — validate with squadron flight-authorisation logs].
- [INFERENCE] F-15E FSE: 1,573 EFH ÷ 536 sorties = 2.93 EFH per sortie. That is ≈ 1.47 h per sortie if EFH is summed over both engines of each aircraft, or 2.9 h if counted per aircraft. The release does not say which, so treat it as weak evidence of ~1.5 h sorties at Nellis.
- [INFERENCE] Annual utilisation (all approximate, fleet size varies):
  - RAAF: 4,200 h over about 33 years (1985–2018) ≈ **125–130 h per airframe per year**.
  - Gripen fleet: (300,000 − 143,000) ÷ about 9.7 years ≈ 16,000 h per year fleet-wide.
  - P&W claim (10,000 TAC ≈ "more than 25 years") implies an F100-229 accumulates < 400 TAC per year. At 2.2–3.3 TAC per EFH (Q3) that is about 120–180 EFH per engine per year.
  These are consistent with roughly 120–200 h per year per fighter airframe in peacetime Western/Nordic service. **No IAF figure was found.**
- [INFERENCE] The NACA data and Newcamp's mission-type finding together imply that sortie type changes Nz-peak activity by roughly ×4 (17 vs 69 peaks/h above 2 g). Mission type should therefore be the primary categorical driver of structural and engine cycle content in the generator.

### Gaps
- **IAF data:** annual flying hours per aircraft and per pilot, sorties per day, mission mix by squadron type, average sortie duration (Tejas, Su-30MKI). Likely sources, not retrievable this session:
  - CAG performance audit reports on IAF fleets and flying training
  - Parliamentary Standing Committee on Defence reports
  - Lok Sabha / Rajya Sabha answers via PIB
- **USAF/USN/RAAF per-pilot annual hours and average sortie duration by type:** GAO/CBO/ANAO were not retrievable. ANAO Audit Reports No. 40 (1999–2000), No. 47 (2003–04) and No. 27 (2006–07) on Hornet operations are cited by Wikipedia, but anao.gov.au timed out.
- **Mission-mix percentages** for training vs operational squadrons: none found publicly. A default mix must be an [ASSUMPTION] (see (d)).

---

## Q3. Engine duty cycles: throttle/PLA statistics, AMT, cycle counts, time-at-power, TAC per hour, training vs operational vs combat, variability, fleet severity differences

### Takeaway
- **Design-usage rates.** Public US design-usage data gives realistic fighter engine duty-cycle rates per flight hour:
  - about 0.75 start–max–stop (Type I) cycles
  - about 5 idle–max–idle (Type III) cycles
  - about 5.5–6 cruise–IRP–cruise (Type IV) cycles
  - about 4–5 afterburner lights
  - about 17–20 % of flight time at or above IRP ("hot time"); about 5 % in afterburner
  - TAC = Type I + Type III/4 + Type IV/40 ≈ **2.2 TAC/FH** (design); measured **3.3 TAC/EFH** on F-15E/F110-129 at Nellis
- **Variability is large:**
  - Harrier per-flight life usage SD ≥ 50 % of the mean (typical 20–30 %)
  - Tornado dispersion factor (95 % quantile ÷ mean) about 1.3
  - Mirage 2000 max/min severity ratio 1.5–5 within a mission type
  - Red Arrows Hawk usage varied by a factor of 40
- **Fleet severity surprises:** F404 USN usage was "significantly more severe than forecasted", forcing life-limit cuts of nearly 50 %.

### Cited Findings
**Cycle definitions and TAC**
- [TRANSFER: USAF methodology; applies to F100/F110 and F404 USAF users] TAC definition — [RTO-TR-028 App. 1 (Maletta, GE), p. A1-3](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - **TAC = LCF + FTC/4 + CIC/40**, where LCF = engine start→IRP→stop, FTC = idle→IRP→idle, CIC = cruise→IRP→cruise.
  - "'Cruise' is not rigorously defined and the implied relationship of damage between the various types of cycles is not necessarily representative of any location within the engine."
  - TACs from different counting systems are not equivalent.
- [TRANSFER: same] MIL-HDBK-1783B states TAC = Type I + Type III/4 + Type IV/40 + Kx(other cycles) — [Table XI p. 45](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf).
- [DIRECT F-16 engines, practitioner forum, secondary] A TAC "is a form of life measurement that major engine components are tracked against"; "There is no way to predict how many 'TACs' will be used per hour or flight" — [F-16.net forum](https://www.f-16.net/forum/viewtopic.php?t=11822). A search-result summary also attributed engine-specific counter rules (¼ per MIL→idle→MIL on F100-100/-200/-220; an added 1/40 counter on the -229) to this thread, but they were not on the fetched page. Treat them as unverified; the RTO-TR-028 / MIL-HDBK-1783B formula above is the authoritative general form.

**Design-usage rates (fighter)**
- [TRANSFER: F-22/F119 design usage, cold parts, per 4,000 FH; the most complete public fighter engine usage table] — [JSSG-2007A Table XXXIX p. 602; Table XI p. 535](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf); identified as F-22/F119 in [MIL-HDBK-1783B Table XII p. 47](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf):

  | Cycle / parameter | Count over 4,000 FH |
  |---|---|
  | Type I (0–max–0) | 2,973 |
  | Type III (idle–max–idle) | 20,503 |
  | Type IV (cruise–int–cruise) | 22,074 |
  | Augmentor lights | 20,239 |
  | Augmentor time | 186 h |
  | Vector time | 109 h |
  | Vector cycles | 108,938 |
  | Time at IRP and above | 684 h |
  | Engine operating time | 5,400 h |

  Hot parts carry half these values over 2,000 FH.
- [TRANSFER: USAF guidance for early design of fighter engines] Fighter cold parts (4,000 FH): Type I 3,200; Type III 20,000; Type IV 24,000; augmentor lights 17,000; augmentor time 200 h; time at IRP and above 800 h — [MIL-HDBK-1783B Table X, p. 42](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf). Related guidance (p. 43–44):
  - "It is recommended that time at or above intermediate power not be less than 20 percent of the total flight hour requirement."
  - Augmentation time should be "no less than 5 percent", and augmentor lights "no less than 50 percent of the total number of throttle excursions".
  - "All past systems historically have had higher drag and gross weight than originally predicted."
- [TRANSFER: same] **Throttle reburst** — "occurs in a system which experiences air-to-air combat or air-to-ground usage … when an idle dwell follows a period of sustained maximum power and the idle dwell is sufficient … to achieve thermal reversal" (usually turbine disk and blade retainers). Thermal reversals also occur after high-altitude, high-Mach operation. "Hold times at idle power after a sustained period at intermediate/maximum power need to be defined." Recorded F-15/F-16 usage "used to establish distribution of dwell times as a function of aircraft type and mission type" — [MIL-HDBK-1783B p. 43](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf).
- [TRANSFER: spec lessons learned] "Operational data has revealed usage parameters not accounted for in design," notably major throttle cycles other than start–stop, partial throttle cycles, time at or above intermediate, and dwell times. This led to "significant reduction in life limits" — [JSSG-2007A §A.3.4.1.2, p. 232](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf).
- [TRANSFER: USAF; F100-PW-229] Deterioration in design: the F100-PW-229 "was designed for 1/3-life at nominal production performance and 2/3-life at full deterioration levels." Hot-parts design margins of 30–70 °F above production maximum steady-state gas temperature have been imposed — [MIL-HDBK-1783B p. 44](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf).

**Measured field rates and AMT**
- [DIRECT F110-GE-129 on F-15E] The Nellis field service evaluation (Apr 1997 – Sep 1998, 1,573 EFH, 536 sorties) maintained "**an average of 3.3 total accumulated cycles (TAC) per EFH**" with no removals, shop visits, in-flight shutdowns or stalls — [GE press release](https://www.geaerospace.com/news/press-releases/defense-engines/field-service-evaluation-ge-powered-f-15e-highly-successful).
- [DIRECT F110-GE-129] GE hardware upgrades allow "6,000 TACs between scheduled visits," a 40 % reduction in scheduled visits — [GE F110-GE-129 datasheet](https://www.geaerospace.com/sites/default/files/datasheet-F110-GE-129.pdf).
- [DIRECT F100-PW-229 EEP] The AMT at AEDC exceeded 6,000 TACs; "an average engine would need 10,000 TACs, or more than 25 years of operation, to see the same time and temperature exposure." The periodic inspection interval rises from 4,300 to 6,000 cycles — [PR Newswire, 15 Nov 2010](https://www.prnewswire.com/news-releases/pratt--whitneys-f100-229-engine-enhancement-package-completes-record-breaking-accelerated-mission-test-108144564.html); [Aero-News](https://www.aero-news.net/index.cfm?do=main.textpost&id=03129b2b-997f-41cc-874c-cf6439d3881f).
- [TRANSFER: spec] AMT method — [JSSG-2007A p. 440](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf):
  - "Each proposed aircraft mission should be analyzed to define the corresponding engine duty cycles … the non-damaging cycles are discarded as are the dwell times at part power and idle … the number of engine cycles accumulated per AMT test hour is higher than the number of cycles accumulated per flight hour."
  - AMT should include starts, hot starts and false starts, plus post-shutdown thermal cycling. Damaging dwell at intermediate is retained, as are augmentor ignitions and dwell.
- [DIRECT TURBISTAN, fighter engine-disc standard sequence derived from flight data (NLR, ten Have 1987)] "The TURBISTAN sequence contains 15,452 load reversals in a block of 100 different flights, whose average length is about 80 cycles" — [Copp et al., Res. Intell. Manuf. Assem. 2022, p. 5](https://pdfs.semanticscholar.org/aa67/e0d47f02e8bfb8f9207b8ab001ce1339e59a.pdf). The definitive report is NLR-TR 87054 L (Cold TURBISTAN), not retrieved.
- [TRANSFER: military vs civil] The military F117-PW-100 accumulates cycles "about 2–3 times" the civil PW2037 on a cycle/hour basis, from touch-and-goes, airdrops and reverser use — [RTO-TR-028 Ch. 3, p. 3-4](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).

**Variability (between flights, engines, pilots, squadrons, bases, fleets)**
- [TRANSFER: RAF Harrier/Pegasus Mk105] Data from the first 1,700 flights of 12 aircraft, recorded at 8 samples/s — [RTO-TR-028 Ch. 9 (Sapsard), pp. 9-5 to 9-7](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - "The standard deviation is at least 50 % of the mean throughout. To put this into context this ratio is usually in the order of 20 % to 30 %."
  - Correlation improved when converting "counts per flight" to "counts per hour".
  - HP compressor usage was bimodal because "one was a training squadron and the other an operational unit."
  - "Difference in the rate of life consumption between the best and worst engines is about 20 %."
  - Skew to the right is "typical of measured life usage distributions"; extreme creep values were associated with air-show demonstrations.
  - Missing data replaced by average usage added about 17 % usage.
  - Fleet means: "approximately Poisson distributions for individual engines and Normal distributions for the whole fleet."
- [TRANSFER: GAF Tornado/RB199, OLMOS monitoring] — [RTO-TR-028 Ch. 9, pp. 9-8 to 9-9](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf); [Ch. 8, p. 8-7](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - Clusters of usage values were associated with mission type.
  - "Significant differences in usage exist between the right and left engines, due to engine handling procedures (which engine is first switched on and off …)."
  - "The correlation between flight time and life usage is not as strong as might be expected."
  - "There is a sharp cut-off for low life usage values … due to the minimum power requirement for take-off, and to the start-up and shut-down stresses."
  - A 3-parameter Weibull was fitted to per-flight usage.
  - The fleet-wide normalised distribution had "lower cut-off point of about 0.5".
  - "The dispersion factor for cyclic exchange rates typically takes values of about 1.3."
- [TRANSFER: FAF Mirage 2000/M53-P2, ELMS] — [RTO-TR-028 Ch. 9, pp. 9-9 to 9-10](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - The usage unit is MMU per EFH, which "increases with throttle excursions and turbine time-at-temperature".
  - Two bases differed (high-altitude fighter mission vs low-altitude navigation mission).
  - The max/min MMU/EFH ratio within a mission type ranged "from about 1.5 to 5"; "no aircraft actually flew the mean flight profile."
  - Relevance: the IAF operates Mirage 2000s at Gwalior ([Wikipedia: List of IAF stations](https://en.wikipedia.org/wiki/List_of_Indian_Air_Force_stations)); whether IAF aircraft carry ELMS is unknown.
- [TRANSFER: RAF Hawk/Adour] Red Arrows display flying "generate[d] a wide variety of engine usage rates (a factor of 40 between extremes)" — [RTO-TR-028 Ch. 2, p. 2-11](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).
- [TRANSFER: UK EUMS, late 1970s] "Two pilots flying exactly the same route used very different amounts of engine life. One used the throttle to climb over some hills, and the other used the elevators" — [RTO-TR-028 Ch. 8, p. 8-13](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).
- [TRANSFER: same report] Squadron/base influences on life consumption — [RTO-TR-028 Ch. 8, p. 8-4](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - "base locations relative to training areas"
  - "differences in aircraft ground handling"
  - "varying interpretations of handling instructions"
  - "length and altitude of the runways"
- [TRANSFER: same report] Event-specific damage — [RTO-TR-028 Ch. 8, p. 8-6](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - "Quick Reaction Alert starts cause extreme life consumption in bore regions … hot re-slams are typically detrimental for rim areas."
  - Small-sample exchange rates for Adour and RB199 later worsened by 30 % — [Ch. 3, p. 3-5](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).
- [TRANSFER: NATO operators generally] "Countries that are smaller geographically tend to have more severe missions (more low level activity with heavy weapons loads and little or no cruise time to engagement)" — [RTO-TR-028 Ch. 3, p. 3-4](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).
- [DIRECT F404/USN] "The actual usage of the F404 engine (used in the F/A-18) was significantly more severe than forecasted, necessitating life limit reductions of almost 50 %" (Comptroller General PSAD-80-72, 30 Sep 1980). The CC-130E cyclic exchange ratio update raised cycles per airframe hour by 24 % — [Canada DND TAA Advisory 2016-02 §5.3](https://www.canada.ca/en/department-national-defence/services/military-airworthiness/technical-airworthiness-authority-overview/technical-airworthiness-regulatory-documents/technical-airworthiness-authority-advisories/2016-02.html).
- [DIRECT F404/USN] "The In-flight Engine Condition Monitoring system (IECMS) records the complete mission as well as temperature, speed, and pressure counts. The Equivalent Low Cycle Fatigue (ELCF) of each rotating part is tracked." Mission updates were completed in 1992 and 1997 — [RTO-TR-028 App. 2, p. A2-14](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf). [DIRECT CF-18 F404]: CF tracks 26 critical plus 135 tracked components — [RTO-TR-028 App. 2, p. A2-3](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).
- [DIRECT Gripen/RM12] GKN's Life Tracking System computes life to crack initiation from each flight's recorded loads. The baseline assumed the engine always starts at a uniform "Nordic median" temperature of 278 K; the study also evaluated 253 K and 303 K (Thailand-like). Including a variable start state (multiple flights per day without full cooling) "in most cases decrease[s] the life consumption", and the ambient-temperature (cool-down) effect "was small" — [Chalmers 2014, abstract and §4.2.3](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf).
- [DIRECT Tejas] The onboard ECMS logs engine usage data to compute life usage indices of life-limited parts — [ADA brochure p. 9](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf).
- [DIRECT Su-30MKI/AL-31FP] Mean time between overhaul (MTBO) is reportedly 1,000 h with a 3,000 h full life; the nozzle MTBO is 500 h. The Defence Minister told Parliament of 69 engine-related failures between late 2012 and early 2015 — [Wikipedia: Sukhoi Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI); [Wikipedia: Saturn AL-31](https://en.wikipedia.org/wiki/Saturn_AL-31) (secondary).
- [TRANSFER: generic] Typical life-usage monitoring sampling rates are compressor discs 1–2 Hz, turbine discs 1–4 Hz, shafts 1–2 Hz and turbine blades 2–8 Hz. Typical signal accuracy/resolution — [RTO-TR-028 Ch. 8 Tables 1–2, p. 8-8](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - spool speed 0.1 % / 0.05 %
  - EGT 2 K / 1 K
  - pressure altitude 100 ft / 50 ft
  - g-load 0.01 g / 0.005 g

  These are relevant to the sensor-texture researcher.

### Inferences
- [INFERENCE] Per-flight rates from F-22 design usage (2,938 flights, 1.36 h each):
  - about **7.0 idle–max–idle**, 7.5 cruise–IRP–cruise and 6.9 AB lights per flight
  - about **14 min at or above IRP** and 3.8 min in AB per flight
  - TAC ≈ (2,973 + 20,503/4 + 22,074/40)/4,000 = **2.16 TAC/FH** (2.94 per flight)

  MIL-HDBK-1783B guidance gives (3,200 + 5,000 + 600)/4,000 = **2.2 TAC/FH**. The F-15E Nellis FSE (3.3 TAC/EFH) is about 50 % above design guidance. That is plausible for weapons-school/test usage, and shows "operational/advanced tactical training" > design average.
- [INFERENCE] Calibration targets for the synthetic generator (fighter, peacetime):
  - TAC/EFH distribution centred at about 2.2, with squadron means 1.7–3.3
  - per-flight life-usage coefficient of variation about 0.5 (Harrier) and dispersion factor (95th percentile ÷ mean of per-engine rates) about 1.3 (RB199)
  - within-mission-type max/min ratio 1.5–5 (M53)
  - left/right engine asymmetry for twin-engine types (start/stop order)
  - a hard lower bound per flight (start + takeoff + shutdown)
- [INFERENCE] Hot-time fraction (17–20 % at or above IRP) and AB fraction (about 5 %) are design targets. Training squadrons (formation, instrument, navigation) will sit below; BFM/ACM and weapons-school sorties above. The NACA ×4 Nz-activity spread by mission suggests a similar ×2–4 spread in throttle excursions per hour by mission type [ASSUMPTION — validate against any recorded Tejas ECMS or IAF Mirage ELMS data].
- [INFERENCE] For Indian ops, RTO-TR-028's "smaller countries / little cruise to engagement" point and the Gripen "multiple flights per day without full cooling" finding suggest modelling **inter-flight thermal state** (engine not cold-soaked between waves). This changes start EGT transients and life usage.

### Gaps
- No public AMT duty cycles (minutes at each PLA, cycles per AMT hour) were found for F404, F110, RM12 or AL-31F. JSSG Tables XXVIIIa/b are templates only.
- No published throttle-excursion statistics (excursions per FH, PLA histograms) for RAAF/CF F404, Swiss/Finnish F404, or IAF fleets. DTIC ADA347270 (CF-18 Engine Condition Monitoring System, DND/GasTOPS) and ARL ADA164562 (F404 for RAAF, Frith 1985) were identified but not readable (DTIC down).
- Robust-AMT "hot time" figures for F100-229 (reported as 450 h vs a 231 h spec in a search summary) could not be verified; the globalsecurity page returned HTTP 402.
- The NLR TURBISTAN report (NLR-TR 87054 L) with the original flight-derived engine cycle statistics was not retrieved.

---

## Q4. Structural usage: Nz exceedance spectra, roll-rate / asymmetric statistics, MIL-STD-1530 / MIL-A-8866 usage, fatigue-meter and IAT data

### Takeaway
- **Public numbers retrieved:**
  - Historical NACA fighter Nz statistics (peaks per hour by mission; training vs combat time-to-exceed)
  - Navy design spectra for landing sink rate, runway roughness, braking and turning
  - Qualitative but authoritative USAF/Navy guidance (JSSG-2006 / MIL-A-8866C)
  - Fleet-severity evidence: CF-18 more severe than the USN test spectrum; RAAF Hornets less fatigued after a 2015 DSTG algorithm update; a Chinese fighter about 20 % lighter than design
- **Not retrieved:** modern quantitative exceedance tables (MIL-A-8866B, ASD-TR-82-5012, DSTG/NLR F/A-18 and F-16 spectra). DTIC was down and the search budget was exhausted.

### Cited Findings
- [TRANSFER: Navy repeated-loads spec, applies as a methodology] The manoeuvre spectrum "shall include symmetric pull-ups and push-overs, and asymmetric rolling pull-outs, roll reversals, and level rolls." Positive and negative Nz exceedances are specified by the procuring activity; the percentage of asymmetric manoeuvres at each load level and the total number of level rolls are proposed by the contractor. Ordering of loads must be random but flight-by-flight — [MIL-A-8866C §3.3.1, §3.5, pp. 3, 5](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF).
- [TRANSFER: Navy spec] Service life is defined by flight hours, ground–air–ground cycles, field taxi runs, takeoffs, catapults and landings by type. Fatigue compliance means no structural defects within 4× service life by analysis and 2× by full-scale test — [MIL-A-8866C §3.2–3.3.2, pp. 3–4](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF).
- [TRANSFER: earlier MIL-A-8866 issue, via AFGROW Damage Tolerant Design Handbook] MIL-A-8866 "presents tabular exceedance data for six classes of aircraft, broken out by mission segment," per 1,000 mission hours, with 3–7 segments per class. Total exceedances are "on the order of 10^5–5×10^5" (exponent formatting lost on the page) — [AFGROW DTD Handbook §5.4.1](https://afgrow.net/applications/DTDHandbook/Sections/page5_4_1.aspx). The actual fighter/trainer table values were not available.
- [TRANSFER: USAF/Navy structures guide] Load-factor spectra guidance — [JSSG-2006 §A.3.2.14.3, pp. 139–142](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2006.010206.PDF):
  - Spectra should represent "projected average usage" and "usage such that 90 percent of the fleet will be expected to meet the service life."
  - "In some cases, the asymmetric maneuver load factor spectrum can exceed the symmetric load factor spectrum."
  - "Recorded operational usage data indicates a wide variance in local load factor exceedance spectra for similar aircraft flying the same mission profiles. Factors such as pilot technique, geographical locations, aircraft performance, training, etc., all affect the actual usage."
  - A roll-rate spectrum method as a function of maximum roll capability and the Nz spectrum is in ASD-TR-72-113.
  - The standard Nz exceedance source is ASD-TR-82-5012, "Handbook of Military Aircraft Design Normal Load Factor Exceedance Data" ([reference list, line ref. in JSSG-2006](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2006.010206.PDF)).
- [TRANSFER: 1950s USAF jet fighters F-86/F-84/F-94; method and relative trends only] — [NACA RM L54E18 (Hamer, Huss, Mayer 1954), pp. 1–8](https://ntrs.nasa.gov/api/citations/19930088093/downloads/19930088093.pdf):
  - "The average flight time required to exceed a given load factor in the USAF training operations is about twice that required during combat operations" (1,150 h training vs 1,265 h combat, F-86).
  - Per manoeuvre, training load-factor probabilities were somewhat higher than combat.
  - Peaks > 2 g per hour: 17 (transition/proficiency) to 69 (low-angle bombing).
  - Probability curves follow a Pearson type III distribution up to about design limit.
  - The service-limit Nz was "exceeded by an appreciable amount" on the F-86.
- [DIRECT CF-18] — [Dabayeh, Yeung & Londei 2003, pp. 23–26](https://www.witpress.com/Secure/elibrary/papers/FDM03/FDM03003FU.pdf):
  - "The design was intended to last 6000 hours under severe US Navy usage … CF usage data and studies have shown that the OEM test spectrum is not representative."
  - "Due to the severe usage of the CF to the airframe some major structural parts are expected to fail before the end of the service life." The centre fuselage test (16,636 SFH) found three bulkheads would not meet full life.
  - The aft-fuselage test (RAAF) reached 23,090 SFH.
  - The spectrum came from MSDRS data at 10 Hz.
  - The CF and RAAF collaborated in IFOSTP.
- [DIRECT RAAF F/A-18] DSTG's 2015 revision of the fatigue-damage algorithm showed airframes "less fatigued than previously believed"; average airframe hours were about 4,200 against a 6,000 h nominal fatigue life (~2018) — [Wikipedia: F/A-18 in Australian service](https://en.wikipedia.org/wiki/McDonnell_Douglas_F/A-18_Hornet_in_Australian_service) (secondary).
- [TRANSFER: Chinese fighter, Flight Parameter Recorder (FPR)-based individual aircraft tracking] "Results of FPR recorded histories for 3 aircraft showed that the actual fatigue damages were about 20 % lighter than the design assumption." Actual store (suspension) weights varied "considerably and irregularly". Damage per cycle was computed from ng and instantaneous weight (empty + recorded fuel + stores) using a Smith–Watson–Topper-type equivalent stress and Miner's rule — [Chen, Zhu & Xue, ICAS 2008 paper 013, pp. 1–2](https://icas.org/ICAS_ARCHIVE/ICAS2008/PAPERS/013.PDF).
- [TRANSFER: NLR/F-16] A generic flexible-aircraft loads database (Prananta et al., NLR-TP-2007-381) "was successfully verified and validated against F-16 flight data" for generating fatigue load sequences for flown or predefined missions — [cited in Mattos et al., ICAF 2023, p. 3](https://www.icaf.aero/icaf2023/proceedings/documents/75.pdf).
- [TRANSFER: standard fighter wing spectrum] FALSTAFF (Fighter Aircraft Loading STAndard For Fatigue) is a standard flight-by-flight fighter load sequence. Mini-FALSTAFF is a shortened version used in coupon and component tests — [UK National Archives record](https://beta.nationalarchives.gov.uk/catalogue/id/C16508596); [scinapse record of a mini-FALSTAFF composite T-joint study](https://www.scinapse.io/papers/2065469971). Numeric block contents were not verified this session.
- [DIRECT F-16] Exceedance and g-limit definitions useful for structural-event tagging — [HAF F-16 manual pp. 5-3 to 5-4](https://info.publicintelligence.net/HAF-F16.pdf):
  - over-g report threshold ≥ 9.5 g / −3.2 g on the limiter
  - SYM vs ROLL g limits split at roll rate 20°/s or abrupt roll input
  - wingtip vortex/wake encounter g counts as asymmetric
  - false g readings above 10 g can come from INU vibration
- [DIRECT F/A-18] Lateral weight asymmetry limits: 22,000 ft·lb for field takeoff; 26,000 ft·lb in flight; 17,000 ft·lb for FCLP/carrier ≤ 33,000 lb. Acceleration with gear or flaps in transit: +0.5 to +2.0 g symmetric, +0.5 to +1.5 g unsymmetric. In moderate turbulence reduce deliberate g by 2.0 below Fig. 4-3 — [NATOPS §4.1.5, §4.1.8, pp. I-4-6, I-4-9](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT Gripen] g limits +9/−3 ("+12 if needed", per a demo-pilot interview) — [Wikipedia: Gripen specifications](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen) (secondary).

### Inferences
- [INFERENCE] For the virtual fighter, structural usage is best generated as **Nz/roll-rate time histories from the manoeuvre generator** (Q7). They can then be checked against:
  - target Nz exceedance curves per mission type (once ASD-TR-82-5012 or DSTG data is obtained)
  - relative activity ratios (×4 between low-activity and high-activity missions, NACA)
  - an asymmetric (rolling) share that can rival the symmetric spectrum (JSSG-2006)
- [INFERENCE] Individual aircraft tracking (IAT) needs mass per flight (store configuration plus fuel), not just Nz (ICAS 2008). The generator should therefore emit store configuration and fuel state as first-class per-sortie variables.
- [INFERENCE] Fleet severity can differ ×1.2 to ×2 from the design spectrum in either direction:
  - CF-18 more severe than USN design
  - F404 USN engines about 2× more severe than forecast (≈50 % life cut)
  - Chinese fighter 20 % lighter than design
  - RAAF less fatigued after algorithm revision

  A "fleet severity" scalar (or vector by structural location) is therefore a defensible scenario parameter.

### Gaps
- Quantitative Nz exceedances per 1,000 FH by mission segment (MIL-A-8866B fighter/trainer tables; ASD-TR-82-5012; USAF F-16 ASIP tracking data).
- DSTG F/A-18 and F-111 usage spectra and RAAF vs USN comparisons; NLR RNLAF F-16 Loads and Usage Monitoring; Swiss and Finnish F/A-18 usage severity; IAF fatigue-meter or IAT data (if any public).
- All of these need targeted searches of DSTG, NLR (reports.nlr.nl), ICAF national reviews and DTIC, which were impossible this session.

---

## Q5. Flight envelope and performance boundaries for candidate fighters; fuel capacity and consumption by phase

### Takeaway
- **Public envelope data (mostly manufacturer/spec-table level):**
  - Tejas: about Mach 1.6–1.8; ceiling 50,000–52,500 ft; +8/−3.5 g (IOC era) → +9 g (FOC); AoA 24° → 28°
  - F-16 Block 50: Mach 2.05; 50,000 ft; +9 g; AoA limiter about 25°
  - F/A-18C: Mach 1.8; 50,000 ft; 7.5 g design; unrestricted AoA in fighter-escort configuration
  - Gripen C/D: Mach 2; 50,000 ft; +9/−3 g
  - Su-30MKI: Mach 2.0; 56,800 ft; +9 g
- **Internal fuel:** 2,340–2,458 kg (single-engine F404-class aircraft) to 9,640 kg (Su-30MKI).
- **Fuel-flow anchors:** about 420–1,700 pph at idle; about 6,000–12,500 pph per F404 at MIL (sea level static); about 4 kg/s at full AB (RM12). Full-AB endurance on internal fuel for the light fighters is roughly 10 min at sea level.

### Cited Findings

**Envelope and fuel by aircraft**

| Aircraft | Mach / speed | Ceiling | g limits | AoA | Internal fuel | Other |
|---|---|---|---|---|---|---|
| **Tejas** | "Supersonic at all altitudes"; spec table Mach 1.8 | 50,000 ft (ADA); 16,000 m / 52,500 ft (Wikipedia) | +8/−3.5 (ADA, IOC era); +9/−3.5 (Wikipedia) | 24° (IOC-II) → 28° (FOC) | 2,458 kg (3,060 L) | MTOW 13,500 kg; clean takeoff 9,800 kg; empty 6,560 kg; external stores 3,500 kg; drop tanks 2×1,200 L, 800 L, 725 L; combat radius 739 km (459 mi); ferry 3,000 km |
| **F-16C Bl 50/52** | M2.05 (1,176 kn) at 40,000 ft clean | 50,000 ft | +9 | limiter ~25° | 7,000 lb | Roll rate 324°/s; cruise 504 kt; combat radius 295 nmi hi-lo-hi with 4×1,000 lb bombs; ferry 2,277 nmi; F110-GE-129 17,155 lbf MIL / 29,500 lbf AB; MTOW 42,300 lb (manual: 48,000 lb ground/flight GW limit) |
| **F/A-18C** | M1.8 at 40,000 ft | 50,000 ft | 7.5 g design | Unrestricted (FE config, CG 17–25 %) | 10,860 lb | Climb 50,000 ft/min; combat radius 400 nmi A-A; ferry 1,800 nmi; F404-402 11,000 lbf MIL / 17,750 lbf AB; field takeoff and catapult max 51,900 lb; flared landing 39,000 lb |
| **Gripen C/D** | Mach 2 at 15,240 m | 15,240 m | +9/−3 | not found | 3,000 L (2,340 kg) | External 3,500 L; combat radius 800 km; ferry 3,200 km; RM12 54 kN MIL / 80.5 kN AB; MTOW 14,000 kg |
| **Su-30MKI** | M2.0 high altitude; 1,350 km/h (M1.09) low altitude | 17,300 m (56,800 ft) | +9 | not found | 9,640 kg | Range 3,000 km high / 1,270 km low; 3.75 h combat mission on internal fuel; AL-31FP AB 12,500 kgf per engine; TVC ±15° (nozzles canted 32°) |

- Tejas [DIRECT] — sources: ADA brochure Dec 2013 p. 2 ([PDF](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf)); spec table citing ADA/Jackson/news ([Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas)). **Conflict:** ADA's 2013 brochure says +8/−3.5 g and 50,000 ft; Wikipedia's current table says +9/−3.5 g, 16,000 m and M1.8. The difference likely reflects IOC vs FOC standards (FOC "higher g-limit of +9 g"). Treat as unresolved until ADA/HAL FOC/Mk1A data is found. Tejas Mk1 operational radius at IOC-II: 400–500 km ([Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas)).
- F-16 [DIRECT] — sources: [Wikipedia: F-16 specifications](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon) (citing USAF fact sheet and the HAF flight manual); 48,000 lb limit from [HAF F-16 manual p. 5-3](https://info.publicintelligence.net/HAF-F16.pdf).
- F/A-18C [DIRECT] — sources: [Wikipedia: F/A-18 specifications](https://en.wikipedia.org/wiki/McDonnell_Douglas_F/A-18_Hornet); weights from [NATOPS §4.1.7 p. I-4-8](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- Gripen C/D [DIRECT] — source: [Wikipedia: Gripen specifications](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen), citing Saab/FMV.
- Su-30MKI [DIRECT] — source: [Wikipedia: Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI), citing Irkut/Sukhoi. Wikipedia lists 300 m/s and 230 m/s climb in different places (conflict).

**Engine data**
- F404 family [DIRECT, GE datasheet]:

  | Variant | Thrust class | Airflow | Pressure ratio | Weight |
  |---|---|---|---|---|
  | F404-102/402 | 17,700 lb (78.7 kN) | 146 lb/s (66 kg/s) | 26:1 | 2,282 lb |
  | F404-GE-IN20 | 19,000 lb (84 kN) | 153 lb/s (70 kg/s) | 28:1 | 2,365 lb |
  | RM12 | 18,100 lb (80.5 kN) | 152 lb/s (69 kg/s) | 27:1 | 2,325 lb |

  IN20 is "the highest thrust variant … latest hot section materials … FADEC" — [GE F404 family datasheet](https://www.geaviation.com/sites/default/files/datasheet-F404-Family.pdf).
- F404-GE-IN20 MIL thrust 12,139 lbf. The F404-GE-402 spec block gives 11,000 lbf MIL / 17,700 lbf wet with SFC 0.81 lb/lbf·h (MIL) and 1.74 (full AB); no SFC is listed for IN20 — [Wikipedia: General Electric F404](https://en.wikipedia.org/wiki/General_Electric_F404) (secondary, cites GE).
- RM12: MIL SFC 23.9 mg/(N·s) (0.844 lb/lbf·h); full AB 50.6 mg/(N·s) (1.79); fuel consumption "gas generator 1.2 kg/s, together with afterburner 4.0 kg/s"; bypass 0.31; OPR 27.5 — [Wikipedia: Volvo RM12](https://en.wikipedia.org/wiki/Volvo_RM12) (secondary).
- AL-31F: dry 7.8 tf; dry SFC 22.1 g/(kN·s); OPR 23; airflow 112 kg/s; TIT 1,665 K; bypass 0.56 — [Wikipedia: Saturn AL-31](https://en.wikipedia.org/wiki/Saturn_AL-31) (secondary).
- F110-GE-129: 29,000 lb class; airflow 270 lb/s; bypass 0.76 — [GE datasheet](https://www.geaerospace.com/sites/default/files/datasheet-F110-GE-129.pdf).

**Measured fuel-flow anchors (manuals)**
- [DIRECT F/A-18] Ground idle FF 420–700 pph (-400) or 420–900 (-402); MIL-check FF 6,000–9,000 (-400) or 6,000–12,500 pph (-402) — [NATOPS pp. III-7-17, III-7-23](https://info.publicintelligence.net/F18-ABCD-000.pdf).
- [DIRECT F-16] Idle FF 500–1,500 pph (PW229) or 700–1,700 pph (GE129) — [HAF F-16 manual pp. 2-9, 2-11](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F-16] External tank transfer maximum is 18,000 pph (300-gal tank) or 30,000 pph (370/600-gal). Wing turbine pumps alone move 6,000 pph. "Prolonged AB operation in a three tank configuration may result in engine flameout prior to depletion of external fuel." Maximum allowable FF with one reservoir empty is 25,000 pph — [HAF F-16 manual pp. 2-22, 5-2](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F/A-18] Hot-weather minimum landing fuel (older aircraft without AFC 021): "Add 90 pounds per °C … above 21 °C to 1,500 pounds" — [NATOPS Ch. 21, p. VI-21-1](https://info.publicintelligence.net/F18-ABCD-000.pdf).

**Fuel fractions by phase**
- [ASSUMPTION: textbook] Conceptual-design historical fuel fractions (Raymer, *Aircraft Design: A Conceptual Approach*): warm-up and takeoff ≈ 0.970, climb ≈ 0.985, landing ≈ 0.995. Not verified in a retrieved source this session — validate against the aircraft's performance manual or a calibrated engine/airframe model.

### Inferences
- [INFERENCE] Sea-level-static fuel flow ≈ thrust × SFC:
  - F404 at MIL ≈ 11,000 × 0.81 ≈ 8,900 pph per engine, consistent with the NATOPS MIL-check band.
  - F404 at full AB ≈ 17,750 × 1.74 ≈ 31,000 pph.
  - RM12: 54 kN × 23.9 mg/(N·s) ≈ 1.29 kg/s (≈ 4,650 kg/h) at MIL; 80.5 kN × 50.6 ≈ 4.07 kg/s (≈ 14,700 kg/h) at full AB.
  - Tejas/IN20 (transferring F404 SFC): ≈ 4,460 kg/h at MIL and ≈ 15,000 kg/h at full AB.
- [INFERENCE] Hence at sea level:
  - Tejas internal fuel (2,458 kg) lasts about **33 min at MIL or about 10 min at full AB**.
  - Gripen (2,340 kg) about 30 min MIL or 9.6 min AB.
  - F/A-18C (10,860 lb, two engines) about 37 min MIL or 10.5 min AB.

  At altitude fuel flow falls roughly with δ (Q6), so cruise endurance is much longer. These explain why AB time is about 5 % of flight time and why sortie fuel budgets cap AB usage.
- [INFERENCE] Fuel state should be a simulated state variable driving gross weight and therefore:
  - approach speed (F/A-18: +2.5 kt per 1,000 lb)
  - AoA at given g
  - structural damage per Nz cycle
  - the landing sink-rate distribution

### Gaps
- Sustained and instantaneous turn-rate data (energy–manoeuvrability diagrams) for all five aircraft; climb rates for Tejas and Gripen.
- Su-30MKI and Gripen AoA limits; Tejas Mk1A updated limits.
- Phase-by-phase fuel burn for a typical sortie (performance manuals not available).

---

## Q6. Environmental and operating conditions (Indian bases), ambient effects on engine parameters (θ, δ), weather data sources

### Takeaway
IMD 1991–2020 normals show the operating extremes the virtual fighter must reproduce:
- **Desert bases (Jodhpur/Uttarlai/Jaisalmer/Nal-Bikaner/Phalodi):** May–June afternoon means of about 40–41 °C with 970–980 hPa station pressure. That gives density altitudes of about 4,000–4,800 ft on typical days and about 5,000+ ft on record days (48.8–49.9 °C).
- **Leh:** δ ≈ 0.67 with summer density altitude about 14,500–15,300 ft; winter lows to −28 °C.
- **Coastal Naliya/Chennai:** humid and near sea level.
- **Sulur (Coimbatore) and Pune:** moderately elevated at 381–592 m.

Hot ambient raises idle rpm at constant thrust, pushes EGT/FTIT toward limits at MIL (temperature-limited thrust loss), triggers hot-weather procedures, and dust storms are frequent in the Thar (4–8 days per year).

### Cited Findings

**IMD station climatology (1991–2020)** — [DIRECT, IMD Climatological Tables of Observatories in India 1991–2020](https://imdpune.gov.in/library/public/Climatological%20Tables%201991-2020.pdf), per-station tables (e.g., Jodhpur p. 176, Leh pp. 222–223). Columns are station-level pressure and dry bulb at 0300 and 1200 UTC, mean daily max/min, mean monthly highest, and record extremes:

| Station (IMD height, m) | Hottest month | Station P 1200 UTC (hPa) | DB 1200 UTC (°C) | Mean daily max (°C) | Mean monthly highest (°C) | Record (°C) | Coldest-month mean min / record low (°C) |
|---|---|---|---|---|---|---|---|
| Jodhpur (217) | May | 975.8 | 39.8 | 41.2 | 45.0 | 48.8 | Jan 9.6 / −2.8 (Feb) |
| Bikaner (224) | May | 974.3 | 40.7 | 42.2 | 46.1 | 49.4 | Jan 7.7 / −4.0 |
| Jaisalmer (258) | Jun | 970.4 | 40.0 | 41.1 | 45.4 | 49.2 | Jan 9.3 / −5.9 |
| Barmer (193) | May | 980.2 | 40.9 | 42.3 | 46.0 | 49.9 | Jan 10.2 / −1.7 |
| Naliya (22) | May | 1001.9 | 32.6 | 35.1 | 38.4 | 44.6 | Jan 9.8 / 0.6 |
| Coimbatore (A) (395) | Apr–May | 960.9 | 31.3 | 35.0 (May; Apr 36.4) | 37.8 | 42.6 | Jan 19.2 / 12.2 |
| Pune (556) | Apr–May | 943.1 | 34.3 | 37.3 (May; Apr 37.9) | 41.0 | 44.4 | Jan 11.2 / 1.7 |
| Gwalior (207) | May | 976.4 | 39.9 | 42.1 | 45.6 | 48.3 | Jan 7.7 / −1.1 |
| Bareilly (167) | May | 980.2 | 37.1 | 39.2 | 43.6 | 47.3 (Jun) | Jan 8.4 / −1.3 |
| Ambala (270) | May | 969.3 | 36.6 | 38.4 | 43.0 | 47.8 | Jan 6.7 / −1.3 |
| Tezpur (79) | Jul | 991.0 | 29.9 | 31.9 | 35.9 | 39.5 | Jan 11.3 / 5.6 |
| Srinagar (1,585) | Jul | 831.9 | 28.3 | 30.0 | 34.2 | 38.3 | Jan −1.9 / −14.4 |
| Bengaluru HAL (901) | May | 907.5 | 30.4 | 33.0 | 36.0 | 38.0 | Jan 15.0 / 8.8 |
| Leh (3,513) | Jul | no pressure data in table | — | 28.5 | 33.4 | 36.6 | Jan −13.1 / −28.6 (Feb) |

- [DIRECT] Weather-phenomenon days per year (thunder, fog, dust storm) — same IMD source, second page of each station table:
  - Jaisalmer: 8.1 dust-storm days (peak June 2.6)
  - Bikaner: 7.6 (peak June 2.4)
  - Jodhpur: 4.1
  - Phalodi: 1.3; Barmer: 0.8
  - Ambala: 30.4 fog days (Jan 12.7, Dec 10.3)
  - Naliya: 14.8 fog days
  - Pune: 12.1 fog days
  - Coimbatore: 45.6 thunder days
  - Tezpur: monsoon thunder about 10–12 days per month (Apr–Sep)
  - Leh: 0 thunder, fog and dust-storm days; 13.4 precipitation days

**IAF airfield elevations (secondary)** — [Wikipedia: List of IAF stations](https://en.wikipedia.org/wiki/List_of_Indian_Air_Force_stations) (table based on 2009 Scramble data; "more citations needed"):

| Airfield | Elevation |
|---|---|
| Leh AFS | 3,256 m (10,682 ft) |
| Thoise | 3,070 m ([Wikipedia: Thoise AFS](https://en.wikipedia.org/wiki/Thoise_Air_Force_Station)) |
| Mudh-Nyoma | 4,200 m |
| Srinagar | 1,664 m |
| Awantipur | 1,646 m |
| Lohegaon (Pune) | 592 m |
| Sulur | 381 m |
| Jaisalmer | 270 m |
| Nal-Bikaner | 229 m |
| Jodhpur | 219 m |
| Phalodi | 213 m |
| Uttarlai | 152 m |
| Naliya | 21 m |
| Jamnagar | 21 m |
| Tambaram | 27 m |
| Thanjavur | 77 m |
| Tezpur | 73 m |
| Chabua | 107 m |
| Gwalior | 188 m |
| Bareilly | 172 m |
| Ambala | 274 m |

**Tejas environmental trials**
- [DIRECT Tejas] "LCA Under Hot weather Trial at The Hottest Part of India (Temperature > 48 °C)" and "Cold Weather Flight Trials at Leh"; wet-runway and night-flying trials — [ADA brochure pp. 4–5, 17](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf).

**Design hot-day definitions**
- [TRANSFER: US design atmospheres] The USN uses tropical day 32.1 °C and hot day 49 °C for engine performance tables; USAF uses the MIL-STD-210C 1 %-risk worldwide hot day; the Army uses a sea-level static hot day of 50 °C — [JSSG-2007A p. 138](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf).
- [TRANSFER: same] Helicopter engines' sand/dust ingestion spec is 53 mg/m³ (0–80 µm) for 54 h. Turbofans must run at intermediate power during the specified sand/dust event with limited thrust loss and SFC gain (values to be specified) — [JSSG-2007A §3.3.2.4, p. 19](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf).

**Ambient effects on engine and airframe operation**
- [DIRECT F-16] Idle rpm rises with temperature and pressure altitude (constant idle thrust). On hot days (> 32 °C) the ENGINE warning light may stay on until > 70 % rpm, and the throttle-to-idle point shifts to maximum motoring rpm. "Maximum FTIT and rpm vary with temperature and pressure altitude" at takeoff — [HAF F-16 manual p. 1-40 and Sec. I GE 129 engine characteristics; pp. 2-10, 2-20](https://info.publicintelligence.net/HAF-F16.pdf).
- [DIRECT F/A-18] Hot-weather procedures — [NATOPS Ch. 21, p. VI-21-1; §2.2.6.1; §4.1.1.4](https://info.publicintelligence.net/F18-ABCD-000.pdf):
  - Above 103 °F (39.4 °C), consider raising throttle above idle (or use APU bleed) for avionics cooling.
  - "Calculate the effect of temperature and altitude (density ratio) on takeoff and abort performance."
  - "Extended low altitude high speed flight in ambient conditions above 103 °F may cause bleed air system overheat."
  - If fuel temperature exceeds 75 °C, land as soon as practical; FUEL HOT caution at feed fuel > 79 °C.
  - AMAD caution time on the ground depends on fuel state and ambient: "15 minutes at 24 °C and 2,000 pounds fuel."
  - Oil-pressure lower limit can drop 10 psi with fuel > 38 °C.
- [DIRECT F/A-18] "Recommended braking speeds are based on tests conducted at sea level. Ground speed may be significantly higher than calibrated airspeed at airfields above sea level" — relevant to Leh and Thoise — [NATOPS §7.3.6, p. III-7-29](https://info.publicintelligence.net/F18-ABCD-000.pdf).

**Standard atmosphere and weather data sources**
- [TRANSFER: standard atmosphere] Troposphere curve fits (metric): T = 15.04 − 0.00649·h (°C, h in m); p = 101.29·[(T + 273.1)/288.08]^5.256 (kPa) — [NASA Glenn, Earth Atmosphere Model](https://www.grc.nasa.gov/www/k-12/airplane/atmosmet.html).
- [DIRECT data source] ERA5 hourly single-level reanalysis, 1940–present, 0.25° × 0.25° atmosphere grid — [Copernicus CDS ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels).
- [DIRECT data source] The Iowa Environmental Mesonet offers an "India ASOS" network download with temperature, dew point, altimeter, wind, visibility, gust and raw METAR; per-station availability not confirmed — [IEM ASOS download](https://mesonet.agron.iastate.edu/request/download.phtml?network=IN__ASOS).

### Inferences
Computed from IMD station pressures and temperatures, with ISA for Leh and Thoise (formulas below). δ = p/1013.25; θ = T/288.15 (K); PA = 145,366·(1 − δ^0.190284) ft; DA = 145,442·(1 − σ^0.234969) ft with σ = δ/θ.

**Derived atmosphere at representative bases** [INFERENCE]

| Base / condition | δ | θ | √θ | Pressure altitude | Density altitude |
|---|---|---|---|---|---|
| Jodhpur, May 1200 UTC mean (975.8 hPa, 39.8 °C) | 0.963 | 1.086 | 1.042 | 1,040 ft | ≈ 4,050 ft |
| Jodhpur, May mean monthly highest (45 °C) | 0.963 | 1.104 | — | — | ≈ 4,600 ft |
| Jodhpur, record (48.8 °C) | 0.963 | 1.117 | — | — | ≈ 5,000 ft |
| Jaisalmer / Bikaner, record (49.2–49.4 °C) | — | ≈ 1.119 | — | — | ≈ 5,100–5,200 ft |
| Pune, May (943.1 hPa, 34.3 °C) | 0.931 | 1.067 | — | ≈ 1,970 ft | ≈ 4,600 ft |
| Pune, record (43.3 °C) | 0.931 | — | — | — | ≈ 5,550 ft |
| Coimbatore/Sulur, May (960.9 hPa, 31.3 °C) | 0.948 | 1.057 | — | — | ≈ 3,650 ft |
| Coimbatore/Sulur, monthly highest (37.8 °C) | 0.948 | — | — | — | ≈ 4,350 ft |
| Naliya, May (1,001.9 hPa, 32.6 °C) | 0.989 | 1.061 | — | — | ≈ 2,400 ft |
| Leh airfield (ISA, 3,256 m) | 0.670 (678.6 hPa) | — | — | 10,680 ft | ≈ 14,500 ft (Jul mean max 28.5 °C); ≈ 15,300 ft (record 36.6 °C); ≈ 9,850 ft (Jan mean min −13.1 °C) |
| Thoise (ISA, 3,070 m) | 0.686 | — | — | — | ≈ 13,900–14,400 ft at 30–35 °C |
| Srinagar, Jul (831.9 hPa, 28.3 °C) | 0.821 | — | — | — | ≈ 8,050 ft |

- [ASSUMPTION — standard gas-turbine practice; validate with an engine deck or the cycle model from the modelling researcher] Corrected parameters remove inlet-condition effects:
  - N/√θ (corrected spool speed)
  - Wf/(δ·√θ) (corrected fuel flow)
  - EGT/θ (corrected EGT, often with an empirical exponent)
  - W·√θ/δ (corrected airflow)
  - F/δ (corrected thrust)

  Here θ and δ should be engine-inlet total temperature and pressure (including ram), not static ambient.
- [INFERENCE] Hot-day EGT pressure, illustrated: at Jodhpur's May afternoon mean (θ ≈ 1.086), holding the same corrected operating point raises physical spool speed by ≈ 4 % and absolute EGT by ≈ 8.6 %. A MIL EGT of 800 °C (1,073 K) on a standard day would map to about 1,165 K ≈ 892 °C. That exceeds the F404-GE-402 MIL steady-state limit of 880 °C ([NATOPS §4.1.1.2, p. I-4-1](https://info.publicintelligence.net/F18-ABCD-000.pdf)). The FADEC would therefore temperature-limit the engine: thrust falls and EGT sits at its limit. This is the hot-day "flat-rated / temperature-limited" signature the virtual engine should reproduce.
- [INFERENCE] Thrust and takeoff at Leh: at fixed corrected conditions, thrust scales roughly with δ (≈ 0.67), and air density is about 0.62–0.64 of sea-level standard on summer afternoons. Expect about one-third less thrust and much longer takeoff rolls and higher groundspeeds (tire and brake limits matter, cf. F-16 MLG 225 kt GS and F/A-18 nose tire 190 kt GS). This is a strong discriminating scenario for the dataset.
- [INFERENCE] Seasonal pattern for scheduling ambient sampling:
  - Rajasthan/North India: pre-monsoon hot season Apr–Jun; monsoon Jul–Sep (high humidity, thunder); winter fog season Dec–Jan (Ambala 10–13 fog days/month).
  - Ladakh: extreme winter cold Dec–Feb.
  - South (Sulur/Thanjavur): NE-monsoon rains Oct–Dec.

  The ambient sampler should be drawn per base, per month and per time of day (0300 vs 1200 UTC columns give a diurnal anchor).

### Gaps
- Leh station-level pressure is not in the IMD table; ISA was used [ASSUMPTION — validate with Leh METAR (VILH) altimeter settings or ERA5 surface pressure].
- Quantitative dust concentration (mg/m³) at Indian bases during dust storms; erosion and fouling rates.
- Actual IAF hot-day takeoff EGT/FTIT recordings, and Tejas hot-weather trial results (only the > 48 °C statement is public).
- Su-30MKI/AL-31FP and RM12 hot-day limiting behaviour.

---

## Q7. How to generate realistic, varied profile instances (mission generators, manoeuvre libraries, Markov models, pilot variability, stochastic synthesis)

### Takeaway
The best-documented public practice:
- **Building-block synthesis** (NATO RTO-TR-028): every mission starts with start-up, taxi and takeoff and ends with landing and shutdown, with manoeuvre blocks in between, smooth transitions and plausibility checks.
- **USAF "mission generation" matching** (GE/USAF): candidate profiles are chosen to match fleet statistics per sortie type — pre/post-flight time, EFH, EOT, time at IRP and AB, AB lights and cycle counts — then smoothed and damage-checked.

Variability should be layered hierarchically (fleet → base/squadron → aircraft/engine → pilot → sortie → manoeuvre) and calibrated to published dispersion statistics. Markov or semi-Markov manoeuvre sequencing is a recommended extension; no public fighter-specific Markov matrices were found.

### Cited Findings
- [TRANSFER: NATO RTO guidance, generic military engines] Building-block method — [RTO-TR-028 Ch. 8 §6.2–6.4, pp. 8-14 to 8-15](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - Analyse a representative set of missions, identify manoeuvres and their frequencies, record each manoeuvre as a block, and combine blocks into typical or synthetic missions.
  - "Every mission should begin with an engine start-up sequence, followed by taxiing (of variable duration) and take-off … finished by an engine landing and shutdown sequence."
  - Transitions must be smooth and pass plausibility checks (range, rate of change from acceleration/deceleration capability).
  - Stated assumptions: "each manoeuvre is independent of those preceding and following it"; "life usage is largely dependent on the transient elements."
- [TRANSFER: same report] Ways to obtain usage — [RTO-TR-028 Ch. 8, p. 8-14 and §7](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - instrumented single aircraft
  - randomly selected fleet recorders ("much more representative")
  - pilot interviews ("historically … not … particularly accurate")
  - flight simulators with syllabus missions

  "Pilot survey is the least expensive and least accurate method … in-flight data recorders in a random sample of the fleet … is the most accurate."
- [TRANSFER: USAF/GE] Mission generation process — [RTO-TR-028 App. 1, pp. A1-4 to A1-5](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - Electronic flight data per sortie → statistics database ("pre and post flight time, EFH, EOT, IRP and A/B Time at Takeoff, Total Time at IRP and A/B, Number of A/B Lights, and a variety of cyclic statistics") → evaluate "averages, distribution shapes and outliers" per sortie type.
  - Select a 'best fit' candidate mission per type (with pilot input on what is "most typical").
  - Smooth profiles while preserving cyclic content.
  - Compare damage to actual missions.
  - Compute thermodynamic parameters for each deterioration level and ambient condition.
  - "Damage … can be affected by where in the flight envelope engine cycles occur."
- [TRANSFER: same report] Translation of aircraft manoeuvres to engine parameters — [RTO-TR-028 Ch. 8 §6.3, p. 8-15](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - Thrust demand from an aircraft performance model.
  - "Depending on the type of manoeuvre (e.g. close formation, tanking) a certain pattern of thrust modulation must be superimposed."
  - Then inlet model → engine transient model → PLA and engine parameters.
  - "Accurate prediction of transient engine behaviour is much more difficult than … steady-state."
- [TRANSFER: same report] Monitoring statistics — [RTO-TR-028 Ch. 9 §3, p. 9-5](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - "At least 30 samples should exist for each statistical degree of freedom, for each permutation of variables such as squadron, operating base, sortie pattern, life-usage affecting modification, time of year."
  - "Doubling of fleet size … requires a 41 % increase in the number of sampled aircraft."
  - Fleet-wide usage distributions are skewed; Weibull or log-normal transformations are used.
- [TRANSFER: ICAF 2023, Embraer/ITA] Two ways to represent an operational life — [Mattos, Arbelo & Machado, ICAF 2023, pp. 5–7](https://www.icaf.aero/icaf2023/proceedings/documents/75.pdf):
  - **(i) single flight profiles** weighted by mix (e.g., 30/60/10 %)
  - **(ii) an "equivalent flight profile"** whose segment durations are weighted by mix. Ground segments (taxi, takeoff run, landing roll) are assigned per block, not summed, to avoid inflating severity.
- [TRANSFER: USAF structures guidance] Load spectra should be broken down by mission segments and use the best historical data. Durability spectra are generated for the 90th-percentile fleet usage with statistical dispersions — [JSSG-2006 §A.3.2.14.3, p. 140](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2006.010206.PDF).
- [TRANSFER: Gripen GKN LTS] Day-level sequencing: flights within a day can be assembled into one sequence because "the flight now depends on the previous flight" (thermal state). The ambient used for cool-down between flights can be varied (253–303 K) — [Chalmers 2014, abstract, §4.2](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf).
- [TRANSFER: Tornado / Harrier / Mirage statistics] Calibration targets for synthetic variability — [RTO-TR-028 Ch. 8–9](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf):
  - per-flight SD ≥ 50 % of mean
  - engine-to-engine 20 % best-vs-worst cumulative
  - dispersion factor about 1.3
  - mission-type max/min 1.5–5
  - bimodal training vs operational squadrons
  - left/right engine asymmetry
- [TRANSFER: A-10, via ICAF 2023] Nz occurrence counts grow exponentially with flight duration, and mission type (BFM/SA vs CAS/NAV) is a strong predictor. "A loads model based on the mission type can be useful for fleet planning and mission allocation strategies" — [ICAF 2023, p. 2](https://www.icaf.aero/icaf2023/proceedings/documents/75.pdf).

### Inferences
- [INFERENCE] Phalanx should implement a **hierarchical stochastic mission synthesiser** (detailed in (d)):
  1. calendar/fleet layer (flying days, waves, turnarounds)
  2. sortie layer (mission type from squadron mix, duration, configuration, fuel, base, ambient)
  3. phase grammar (fixed start/end blocks plus mission-specific middle blocks)
  4. manoeuvre layer (semi-Markov sequence of manoeuvre primitives with duration distributions)
  5. pilot layer (latent "aggressiveness/technique" parameters scaling throttle activity, g-onset, AB use; e.g., "throttle-climber vs elevator-climber")
  6. physics layer (aircraft point-mass plus engine transient model in corrected parameters)
  7. plausibility filter and statistical calibration against the targets in (c)
- [ASSUMPTION] Use a **semi-Markov chain** over manoeuvre primitives (e.g., straight-and-level, climb, descent, level turn, break turn, high-g turn, rolling pull-out, roll reversal, vertical manoeuvre, dive/pull-out, low-level weave, formation station-keeping, tanker contact, supersonic dash), with mission-type-specific transition matrices and dwell distributions. It relaxes RTO-TR-028's independence assumption and captures realistic sequencing (e.g., BFM set-up → engagement → reburst cycles → knock-it-off).
  - Validate by checking that output statistics (Nz peaks/h, Type III cycles/FH, AB lights/FH, IRP+ time fraction, TAC/FH) fall within the cited ranges. Recalibrate if IAF/ADA recorded data becomes available.
  - No public fighter manoeuvre transition matrices were found.
- [ASSUMPTION] Military ADS-B/Mode-S trajectories are generally unsuitable for fighter manoeuvre statistics (fighters often do not broadcast, and sampling is coarse). At most they could inform transit legs and pattern geometry near bases. Validate with an OpenSky/ADS-B Exchange query for IAF fighter airframes if needed. No source was checked this session.

### Gaps
- Public Markov/semi-Markov manoeuvre-sequence models or manoeuvre libraries for fighters (with numeric transition probabilities).
- Published pilot-behaviour models (throttle-technique distributions).
- Open fighter flight-data recordings (none found; NASA DASHlink-type data is civil).
- These need further literature search: AIAA/ASME mission-analysis papers, DSTG manoeuvre-recognition work, NLR loads and usage monitoring.

---

## Synthesis for the virtual-fighter data layer

### (a) Key findings summary
1. **Phase physics is well bounded by manuals for F404 (F/A-18) and F100/F110 (F-16).** These give a defensible transfer basis for Tejas (F404-IN20) and Gripen (RM12):
   - Start: starter engagement, throttle to idle at 15–20 % rpm, light-off ≤ 10–20 s, start EGT/FTIT limits 800–935 °C.
   - Idle bands: N2 61–80 %, EGT/FTIT 190–650 °C, FF 420–1,700 pph.
   - MIL checks: N2 90–102 %, EGT 715–880 °C, FF 6,000–12,500 pph.
   - Takeoff: AB light ≤ 5–10 s; rotation and gear rules.
   - Approach: F/A-18 8.1° AoA, ~125 kt at 2,000 lb fuel; F-16 11–13° AoA.
   - Landing: aerobraking or stabilator braking to ~100 kt; drag chute 90–170 kt (F-16).
   - Shutdown: 5-min idle cooldown, restart thermal rules.
2. **Engine duty-cycle design anchors (fighter, per FH):** Type III ≈ 5, Type IV ≈ 5.5–6, AB lights ≈ 4–5, IRP+ ≈ 17–20 % of time, AB ≈ 5 %, TAC ≈ 2.2/FH (3.3 measured at Nellis). Ground engine time ≈ 0.45–1.0 h per flight; EOT/FH ≈ 1.35.
3. **Variability is the norm:**
   - per-flight life-usage CV about 0.5
   - per-engine dispersion about 1.3
   - mission-type max/min 1.5–5
   - pilot technique and squadron/base effects documented
   - fleets can differ ±20–100 % from design (F404 USN about 2× worse than forecast; CF-18 harsher than USN; Chinese fighter 20 % lighter)
4. **Sorties:** about 1.0–1.5 h (median about 70–80 min, right-skewed). About 1.7–2.7 flights per flying day per engine (Gripen) with turnarounds < 1 h possible, so inter-flight thermal state matters.
5. **Indian environment** spans δ 0.67–0.99 and ambient −28 °C to 49.9 °C, with Thar dust storms of 4–8 days per year and North-Indian winter fog. Hot desert afternoons give density altitudes of about 4,000–5,200 ft; Leh about 14,500–15,300 ft. These drive idle rpm shifts, temperature-limited MIL thrust and hot-weather procedural changes.
6. **Gaps:** IAF usage statistics (hours, mission mix, sortie lengths) and modern quantitative Nz exceedance spectra (DSTG/NLR/ASD-TR-82-5012) were not obtainable this session.

### (b) Phase table (4th-gen fighter; F404/F100/F110 basis; transfer to Tejas/Gripen)

| # | Phase | Duration range | Key parameter ranges | Driving variables | Sources (tag) |
|---|---|---|---|---|---|
| 1 | Power-up, BIT, alignment | ~5–20 min (INS align < 10 min; HMD tracker warm-up 15–20 min; FLCS BIT ~45 s; OBOGS BIT 2 min; APU ready ≤ 30 s) | Battery ≥ 23.5 V (≥ 20.5 V cold); hydraulic 2,850–3,250 psi after start | First vs subsequent sortie, cold soak, GPS availability, equipment fit | [NATOPS §7.1, §24](https://info.publicintelligence.net/F18-ABCD-000.pdf); [HAF F-16 p. 2-13](https://info.publicintelligence.net/HAF-F16.pdf) (DIRECT F/A-18, F-16; TRANSFER Tejas/Gripen) |
| 2 | Engine start | ~45–90 s to stable idle [ASSUMPTION from timings]; JFS run ≤ 30 s; light-off ≤ 20 s (PW229) / ≤ 10 s (GE129) | Throttle to idle at ≥ 15 % (F404) / ≥ 20 % (F-16); start EGT ≤ 815 °C (F404); FTIT peak < 625 °C, limit 800 (PW229) / 935 °C (GE129); oil peak < 180 psi, falling within 30 s | OAT (hot/cold starts slower), residual heat (restart motoring 1–4 min, FTIT < 200 °C), starter/battery health | [NATOPS pp. III-7-13–17, I-4-1](https://info.publicintelligence.net/F18-ABCD-000.pdf); [HAF F-16 pp. 2-8–2-11, 5-12](https://info.publicintelligence.net/HAF-F16.pdf); [JSSG-2007A p. 156](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf) |
| 3 | Ground idle, post-start checks | ~2–10 min | F404 N2 61–72/63–70 %, EGT 190–590 °C, FF 420–900 pph, NOZ 73–84 %, oil 45–110 psi; F-16 rpm 62–80 %, FTIT ≤ 625–650 °C, FF 500–1,700 pph, NOZ > 80–94 %; EPU check +5/+10 % rpm | OAT and pressure altitude (idle rpm rises with both), electrical/ECS bleed load, fuel temperature | same as row 2 (DIRECT) |
| 4 | Taxi-out | ~3–15 min [ASSUMPTION; base layout]; part of ~0.45–1.0 h total ground time per flight | Near idle with brief bursts; brake applications (spec: 2 hard + 5 medium + 5 turns per taxi run) | Base layout, wet runway, gross weight, wind | [MIL-HDBK-1783B p. 42](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf); [MIL-A-8866C §3.7.3](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF); [JSSG-2007A Table XXXVIII](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf) (TRANSFER) |
| 5 | Run-up / before takeoff | ~1–5 min (optional; rolling takeoff allowed) | F404 MIL check N2 90–102 %, EGT 715–880 °C, FF 6,000–12,500 pph, NOZ 0–57 %, oil 95–180 psi; F-16 85/90 % rpm before brake release | OAT, deterioration, pilot/unit SOP | [NATOPS p. III-7-23](https://info.publicintelligence.net/F18-ABCD-000.pdf); [HAF F-16 p. 2-20](https://info.publicintelligence.net/HAF-F16.pdf) |
| 6 | Takeoff (MIL or AB) | Roll ~15–40 s [ASSUMPTION]; FTIT/rpm stabilise 5–15 s; AB light ≤ 5 s (> 40 °F) / ≤ 10 s | F-16 rotate 10/15 kt below computed speed to 8–12°; gear up < 300 kt (F-16) / < 250 kt (F/A-18); tire limits 190–235 kt GS; NOZ ≤ 15–20 % at MIL | GW, stores, OAT/density altitude (Leh δ 0.67), runway, AB vs MIL policy | [HAF F-16 pp. 2-20–2-21, 5-2](https://info.publicintelligence.net/HAF-F16.pdf); [NATOPS pp. III-7-23–25, I-4-3](https://info.publicintelligence.net/F18-ABCD-000.pdf) |
| 7 | Climb | ~2–8 min to 20–35 kft [ASSUMPTION] | F/A-18 350 kt to 10,000 ft; F-16 MIL (range) or MAX AB (time) schedules by drag index; F-16 PW229 +2 % MIL rpm for 3 min after gear up | Drag index, GW, ambient, tactical need | [NATOPS §7.2.6](https://info.publicintelligence.net/F18-ABCD-000.pdf); [HAF F-16 pp. 1-40, 2-22](https://info.publicintelligence.net/HAF-F16.pdf) |
| 8 | Transit / cruise | ~10–40 min [ASSUMPTION]; flight idle 70–80 % rpm below 30 kft (F-16) | F/A-18 max range ~4.2° AoA ≤ M0.85; endurance 5.6° AoA; F-16 cruise ~504 kt; cabin 8,000 ft to 23–24 kft | Distance to area (shorter for small countries), fuel, weather | [NATOPS §7.2.8](https://info.publicintelligence.net/F18-ABCD-000.pdf); [RTO-TR-028 p. 3-4](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf) |
| 9 | Mission segment (ACM/BFM, intercept, attack, low level, formation, aerobatics, supersonic, AAR) | ~10–45 min; sortie total 1.0–1.5 h (Gripen median ~74 min) | F-16 +9 g below 15° AoA → 1 g at 25°, −3 g above 250 kt; F/A-18 AoA unrestricted (FE config); AAR 175–300 kt, deck–40,000 ft, closure ≤ 5 kt; supersonic limits M1.4–2.05; Nz > 2 g peaks 17–69 per hour by mission; ~7 idle–max–idle and ~7 AB lights per flight (design) | Mission type (×4 activity), pilot technique, stores, fuel/AB budget | [HAF F-16 FLCS, pp. 5-2–5-4](https://info.publicintelligence.net/HAF-F16.pdf); [NATOPS §4.1, §9.2](https://info.publicintelligence.net/F18-ABCD-000.pdf); [NACA RM L54E18](https://ntrs.nasa.gov/api/citations/19930088093/downloads/19930088093.pdf); [JSSG-2007A Table XXXIX](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf); [NASA TM-85902](https://ntrs.nasa.gov/api/citations/19840016520/downloads/19840016520.pdf) |
| 10 | Descent / RTB | ~5–15 min [ASSUMPTION] | 250 kt, 4,000–6,000 fpm penetration; idle/flight idle; JP-4 hot-day idle-decel flameout caution M1.23–0.9 | Recovery type (visual/instrument), weather | [NATOPS §7.3.1, §7.2.8](https://info.publicintelligence.net/F18-ABCD-000.pdf) |
| 11 | Pattern / overhead break | ~2–6 min [ASSUMPTION]; SATS break interval 17–20 s | F-16 initial 300 kt, gear < 300 kt; F/A-18 gear and flaps < 250 kt; break at 250 kt (SATS); carrier downwind 600 ft | Formation size, traffic, wind | [HAF F-16 p. 2-23](https://info.publicintelligence.net/HAF-F16.pdf); [NATOPS §7.3.2, §9.5](https://info.publicintelligence.net/F18-ABCD-000.pdf) |
| 12 | Approach | ~1–3 min final [ASSUMPTION] | F/A-18 on-speed 8.1° AoA, ~125 kt at 2,000 lb fuel + 2.5 kt per 1,000 lb; F-16 11–13° AoA (max 13°); flaps HALF/FULL AoA 0–15° | GW (fuel and stores), wind, density altitude | [NATOPS §7.3.2, §4.1.6.2](https://info.publicintelligence.net/F18-ABCD-000.pdf); [HAF F-16 p. 2-23](https://info.publicintelligence.net/HAF-F16.pdf) |
| 13 | Landing and roll-out | ~20–60 s [ASSUMPTION] | Sink rate mode 3–4 ft/s (design distribution); F-16 aerobrake 13° AoA to ~100 kt, chute 90–170 kt; F/A-18 idle at touchdown, stabilator brake by 100 kt, anti-skid to ~40 kt GS; Tejas chute up to 180 kt | Runway state, crosswind, groundspeed at altitude, brake energy | [MIL-A-8866C Table I](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF); [HAF F-16 pp. 2-24–2-25](https://info.publicintelligence.net/HAF-F16.pdf); [NATOPS §7.3.3–7.3.6](https://info.publicintelligence.net/F18-ABCD-000.pdf); [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas) |
| 14 | Touch-and-go / go-around | +5–10 min per circuit [ASSUMPTION] | MIL/MAX re-acceleration (a major engine cycle); gear/flaps up only after a safe climb; F/A-18 touch-and-go weight ≤ 33,000 lb | Training syllabus (circuits, instrument approaches) | [HAF F-16 p. 2-27](https://info.publicintelligence.net/HAF-F16.pdf); [NATOPS §7.3.10, §4.1.7](https://info.publicintelligence.net/F18-ABCD-000.pdf); [RTO-TR-028 p. 3-4](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf) |
| 15 | Taxi-in, hot refuel (optional) | ~3–15 min; hot refuel pre-check ≤ 45 s; Gripen turnaround 10–20 min | Idle; brake heat; F/A-18 do not taxi with right engine shut down | Turnaround plan (wave ops), ambient (AMAD/fuel temperature limits) | [NATOPS §7.4](https://info.publicintelligence.net/F18-ABCD-000.pdf); [Wikipedia: Gripen](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen) |
| 16 | Shutdown and cooldown | Idle 5 min recommended (F/A-18); Gripen sample average idle 259 s; INS off 10–20 s before shutdown | If not cooled: restart window 15 min–4 h needs motoring 1 min at 24 % N2 (F404) or 1–4 min until FTIT < 200 °C (F-16); exhaust hazard 5–10 min | Next-sortie timing (thermal state), urgency | [NATOPS pp. III-7-13, III-7-34–35](https://info.publicintelligence.net/F18-ABCD-000.pdf); [HAF F-16 pp. 2-9, 2-29](https://info.publicintelligence.net/HAF-F16.pdf); [Chalmers 2014](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf) |

### (c) Usage-statistics table

| Metric | Value | Platform / force (tag) | Source |
|---|---|---|---|
| Mean flight duration | 1.36 h (4,000 FH ÷ 2,938 flights) | F-22/F119 design usage (TRANSFER) | [JSSG-2007A Table XXXVIII](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf) |
| Fighter mission duration | 1.0–1.5 h | USAF guidance (TRANSFER) | [MIL-HDBK-1783B p. 43](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf) |
| Spectrum hours per flight | 326 SFH ÷ 279 flights = 1.17 h | CF-18 (DIRECT) | [Dabayeh et al. 2003](https://www.witpress.com/Secure/elibrary/papers/FDM03/FDM03003FU.pdf) |
| Gripen sample flight durations | 54.7–173.5 min (median ≈ 74 min) | Gripen/RM12 (DIRECT) | [Chalmers 2014 Table 5.1](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf) |
| Missions per flying day per engine | avg 2.25; range 1.74–2.65 | Gripen/RM12 (DIRECT) | [Chalmers 2014 §5.1](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf) |
| Ground missions | avg 4.6 min; 16 % of days start with one | Gripen/RM12 (DIRECT) | same |
| Turnaround | 10 min A-A / 20 min A-G | Gripen (DIRECT, secondary) | [Wikipedia: Gripen](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen) |
| Ground engine time per flight | ≈ 0.46 h (F-22 derived); 0.75–1.0 h (guidance); ground runs 5–10 % of FH | USAF (TRANSFER) | [JSSG-2007A Tables XI, XXXVIII](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf); [MIL-HDBK-1783B p. 42](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf) |
| Engine operating time ÷ flight hours | 1.35 | F-22 design (TRANSFER) | [JSSG-2007A Table XI](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf) |
| Type III (idle–max–idle) per FH | 5.1 (F-22); 5.0 (guidance) | USAF (TRANSFER) | JSSG-2007A Table XXXIX; MIL-HDBK-1783B Table X |
| Type IV (cruise–IRP–cruise) per FH | 5.5 (F-22); 6.0 (guidance) | USAF (TRANSFER) | same |
| AB lights per FH | 5.1 (F-22); 4.25 (guidance) | USAF (TRANSFER) | same |
| Time at IRP+ (fraction of FH) | 17.1 % (F-22); ≥ 20 % recommended | USAF (TRANSFER) | same; [MIL-HDBK-1783B p. 43](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf) |
| AB time (fraction of FH) | 4.65 % (F-22); ≥ 5 % recommended | USAF (TRANSFER) | same |
| TAC per FH | ≈ 2.16 (F-22 derived); ≈ 2.2 (guidance) | USAF (TRANSFER, INFERENCE) | same |
| TAC per EFH (measured) | 3.3 | F-15E/F110-GE-129, Nellis FSE 1997–98 (DIRECT F110) | [GE release](https://www.geaerospace.com/news/press-releases/defense-engines/field-service-evaluation-ge-powered-f-15e-highly-successful) |
| TAC between scheduled visits | 6,000 (F110-129 upgrade); F100-229 EEP 4,300 → 6,000 | F110 / F100 (DIRECT) | [GE datasheet](https://www.geaerospace.com/sites/default/files/datasheet-F110-GE-129.pdf); [Aero-News](https://www.aero-news.net/index.cfm?do=main.textpost&id=03129b2b-997f-41cc-874c-cf6439d3881f) |
| TAC-years equivalence | 10,000 TAC ≈ > 25 years | F100-229 (DIRECT vendor claim) | [PR Newswire](https://www.prnewswire.com/news-releases/pratt--whitneys-f100-229-engine-enhancement-package-completes-record-breaking-accelerated-mission-test-108144564.html) |
| Engine-disc load sequence | ~80 cycles per flight (15,452 reversals per 100 flights) | TURBISTAN fighter disc standard (TRANSFER) | [Copp et al. 2022](https://pdfs.semanticscholar.org/aa67/e0d47f02e8bfb8f9207b8ab001ce1339e59a.pdf) |
| Per-flight life-usage CV | ≥ 0.5 (typical elsewhere 0.2–0.3) | RAF Harrier (TRANSFER) | [RTO-TR-028 p. 9-7](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf) |
| Best vs worst engine cumulative rate | ~20 % | RAF Harrier (TRANSFER) | same |
| Dispersion factor (95 % quantile ÷ mean) | ≈ 1.3 | GAF Tornado RB199 (TRANSFER) | [RTO-TR-028 p. 8-7](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf) |
| Severity scatter within mission type (max/min MMU/EFH) | 1.5–5 | FAF Mirage 2000 (TRANSFER) | [RTO-TR-028 p. 9-10](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf) |
| Usage extremes, display flying | factor 40 | RAF Hawk/Adour (TRANSFER) | [RTO-TR-028 p. 2-11](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf) |
| Fleet engine severity vs forecast | "significantly more severe"; life limits cut ~50 % | USN F404 (DIRECT F404) | [Canada TAA 2016-02](https://www.canada.ca/en/department-national-defence/services/military-airworthiness/technical-airworthiness-authority-overview/technical-airworthiness-regulatory-documents/technical-airworthiness-authority-advisories/2016-02.html) |
| Airframe actual vs design damage | ~20 % lighter | Chinese fighter, 3 aircraft (TRANSFER) | [ICAS 2008](https://icas.org/ICAS_ARCHIVE/ICAS2008/PAPERS/013.PDF) |
| Nz > 2 g peaks per hour | 17 (proficiency) – 69 (low-angle bombing); 12–24 (combat / USAF training) | 1950s USAF jets (TRANSFER, historical) | [NACA RM L54E18](https://ntrs.nasa.gov/api/citations/19930088093/downloads/19930088093.pdf) |
| Time-to-exceed, training ÷ combat | ≈ 2 | F-86 (TRANSFER, historical) | same |
| Airframe hours | avg 4,200 h vs 6,000 nominal (~2018) | RAAF F/A-18 (DIRECT, secondary) | [Wikipedia: RAAF Hornet](https://en.wikipedia.org/wiki/McDonnell_Douglas_F/A-18_Hornet_in_Australian_service) |
| Fleet hours | 50,000 FH (Oct 2008) | Swiss F/A-18 (DIRECT, secondary) | [Wikipedia: F/A-18](https://en.wikipedia.org/wiki/McDonnell_Douglas_F/A-18_Hornet) |
| Fleet hours | 143,000 FH (2010); > 300,000 FH (2020) | Gripen (DIRECT) | [Wikipedia: Gripen](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen); [Saab](https://www.saab.com/newsroom/stories/2020/june/rm12-engine-supporting-gripen-for-more-than-300000-flying-hours) |
| Engine overhaul / life | MTBO 1,000 h; life 3,000 h; nozzle 500 h; 69 engine failures 2012–15 | Su-30MKI/AL-31FP (DIRECT, secondary) | [Wikipedia: Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI) |
| Flights to date | > 2,430 (Dec 2013) | Tejas development fleet (DIRECT) | [ADA brochure](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf) |
| IAF annual hours per aircraft / pilot | **Not found** | IAF | — (gap) |

### (d) Recommended approach to synthesising realistic sortie instances

1. **Fleet/calendar layer**
   - Simulate flying days per base (weekday/weekend, seasonal pauses; e.g., reduced flying in the monsoon or Ladakh winter) [ASSUMPTION].
   - Assign aircraft to waves with 1–3 flights per day per aircraft. Calibrate to the Gripen mean of 2.25 (1.74–2.65) missions per flying day.
   - Sample turnaround gaps from a mixture: < 1 h (hot pit / quick turn), 2–5 h and overnight (Chalmers Table 5.1).
   - Carry engine and airframe thermal state between flights. RM12 life tracking shows start state matters.
   - Inject ground runs (maintenance or trim) at 5–10 % of flight hours and about 4–13 min each, with 16 % of days starting with a ground run (MIL-HDBK-1783B; Chalmers).
2. **Sortie layer**
   - Draw mission type from a squadron-role mix. [ASSUMPTION — defaults until IAF data is found; validate with squadron syllabi/flight logs]:
     - **OCU/training squadron:** ~35 % general handling/aerobatics/circuits; 20 % instrument/navigation; 20 % formation; 15 % BFM; 10 % ground attack.
     - **Operational squadron:** ~30 % ACM/BFM/intercept; 25 % air-to-ground/low level; 15 % composite/large-force; 10 % AAR; 10 % navigation/transit; 10 % check/air test.
   - Draw duration (lognormal, median 70–80 min, conditioned on type).
   - Draw configuration (stores, drop tanks), take-off fuel and base.
   - Draw ambient from IMD monthly normals with diurnal anchoring (0300/1200 UTC). For specific historical days, replace with ERA5 or METAR.
3. **Phase grammar**
   - Fixed opening: power-up/BIT → start → idle checks → taxi → run-up → takeoff (MIL/AB by policy, weight and density altitude) → climb.
   - Mission middle blocks by type (below).
   - Fixed closing: RTB descent → break/pattern (optional touch-and-go or go-around loops for training) → landing → taxi → optional hot refuel → shutdown with cooldown 3–5 min.
   - Use the parameter bands in (b) for all pre-take-off and post-landing segments.
4. **Manoeuvre layer** [ASSUMPTION]
   - Semi-Markov chain over a library of manoeuvre primitives with mission-specific transition matrices and dwell distributions.
   - Enforce envelope limits (g/AoA/Mach/q from Q5), fuel/AB budgets and plausibility (rate limits from engine transient times: idle→MIL ≤ 5 s, idle→max ≤ 7 s at low altitude).
   - Include special engine events: QRA/"tiger" starts, throttle reburst after sustained MAX, formation/AAR small-amplitude modulation, touch-and-go re-accelerations.
5. **Pilot and unit layer**
   - Latent per-pilot parameters (throttle-use propensity vs elevator use, g-onset aggressiveness, AB propensity, cooldown discipline). Per-unit SOP parameters (rolling vs static takeoff, AB vs MIL takeoff, idle cooldown).
   - Calibrate so that per-engine cumulative rates have dispersion factor about 1.3 and per-flight usage CV about 0.5, and so that mission-type severity ratios span 1.5–5.
6. **Physics layer**
   - Aircraft point-mass/6-DoF-lite with mass from fuel and stores.
   - Engine model in corrected parameters (θ, δ at inlet incl. ram), so hot/high conditions automatically raise physical N and EGT/FTIT, shift idle rpm, and invoke temperature limiting near MIL/MAX.
   - Include deterioration (cross-link to the faults researcher) so EGT margin shrinks with time.
7. **Calibration and validation targets (accept a run only if fleet statistics fall in range):**
   - Type III ≈ 5 ± 2 per FH; AB lights ≈ 4–5 per FH; IRP+ time 15–25 %; AB time 3–7 %; TAC/FH 1.7–3.3
   - Nz > 2 g peaks/h mission-dependent (× ~4 between low and high activity)
   - ground time 0.45–1.0 h per flight
   - sortie length median 70–80 min
   - landing sink-rate histogram near MIL-A-8866C Table I

   Tune against real data as soon as any Tejas ECMS, IAF Mirage ELMS or flight data recorder (FDR) data becomes available (cross-link to the validation/calibration researcher).
8. **Outputs per sortie** (cross-link to the data-pathway researcher):
   - Time series at 1–8 Hz for life-relevant engine parameters (RTO-TR-028 Table 2) and higher for vibration.
   - Per-flight summary records: EFH, EOT, Type I/III/IV counts, AB lights and time, IRP+ time, max EGT/FTIT, max/min Nz, fuel used, landings, touch-and-goes, ambient.

   This mirrors what USAF and GE extract per sortie for mission analysis.

### (e) Open questions and gaps
1. **IAF usage statistics:** annual flying hours per aircraft and per pilot, mission mix by squadron type, average sortie duration, sorties per day, rate of effort for Tejas and Su-30MKI. Need CAG audits, Parliamentary committee reports, PIB answers. Not reachable this session (search budget exhausted).
2. **Tejas-specific phase data:** GTSU-110 start timing, idle/MIL bands of F404-IN20 in Tejas, takeoff/approach speeds and AoA, drag-chute use, typical sortie profiles. Defence Science Journal / Current Science / AeSI LCA flight-test papers were not retrieved.
3. **Modern quantitative Nz exceedance spectra:** MIL-A-8866B tables, ASD-TR-82-5012, DSTG F/A-18 usage, NLR RNLAF F-16 LUMS, Swiss/Finnish F/A-18, USAF F-16 ASIP. DTIC was down; searches unavailable.
4. **AMT duty-cycle definitions and measured throttle statistics** for F404/RM12/AL-31F; RAAF/CF/Swiss F404 usage (DTIC ADA347270, ADA164562 not readable); GAO PSAD-80-72 details.
5. **Su-30MKI/AL-31FP and Gripen/RM12** start, idle and limit bands; Su-30MKI and Gripen AoA limits; turn-rate and energy–manoeuvrability data for all five types.
6. **Leh station pressure** (ISA assumed) and dust concentration statistics at Thar bases.
7. **Public fighter manoeuvre-sequence (Markov) models and pilot-behaviour models** with numeric parameters.
8. **Distribution status:** confirm whether the team may cite the NATOPS (Distribution C) and HAF F-16 manual (disclosure-restricted) in deliverables. If not, replace with public NASA/GE/JSSG anchors already listed.
9. **Tejas envelope conflict:** ADA 2013 (+8/−3.5 g, 50,000 ft, "supersonic") vs current secondary (+9/−3.5 g, 52,500 ft, M1.8). Resolve with ADA/HAL FOC or Mk1A documentation.

### (f) Ranked list of most valuable sources
1. **JSSG-2007A (Engines, Aircraft, Turbine)** — fighter design usage tables (F-22/F119), AMT method, transient-time guidance, start guidance, design hot days — [everyspec PDF](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf).
2. **MIL-HDBK-1783B CHG-2 (ENSIP)** — fighter usage guidance (cycles, hot time, AB), TAC formula, reburst, ground time per mission, F-22/B-2/C-17/T-1A program usage — [everyspec PDF](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf).
3. **NATO RTO-TR-028 (2000), Recommended Practices for Monitoring Gas Turbine Engine Life Consumption** — usage tracking, building-block mission synthesis, USAF mission generation, TAC, Harrier/Tornado/Mirage variability statistics, sampling rates — [DTIC ADA380949](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf).
4. **F/A-18A-D NATOPS A1-F18AC-NFM-000 (2008; Distribution C)** — F404 start/idle/MIL bands, limits, takeoff/pattern/approach/landing/shutdown, AAR, hot/cold weather — [copy](https://info.publicintelligence.net/F18-ABCD-000.pdf).
5. **HAF F-16C/D Flight Manual GR1F-16CJ-1 (2002/03; disclosure-restricted)** — F100-PW-229 and F110-GE-129 start/idle/limits, FLCS g/AoA limits, takeoff/landing/drag chute — [copy](https://info.publicintelligence.net/HAF-F16.pdf).
6. **IMD Climatological Tables 1991–2020** — station pressure, temperature extremes and dust/fog/thunder days for IAF bases — [IMD PDF](https://imdpune.gov.in/library/public/Climatological%20Tables%201991-2020.pdf).
7. **Chalmers 2014 thesis on RM12 life tracking (GKN LTS)** — real Gripen mission durations, flights per day, turnarounds, ground runs, idle-before-shutdown, inter-flight thermal effects — [PDF](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf).
8. **ADA Tejas brochure (Dec 2013)** — Tejas limits, GTSU-110 JFS, engine-usage ECMS, hot (> 48 °C) and Leh trials — [PDF](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf).
9. **GE F-15E/F110-129 FSE release; GE F404 and F110 datasheets; P&W F100-229 AMT releases** — measured TAC/EFH, engine data — [GE FSE](https://www.geaerospace.com/news/press-releases/defense-engines/field-service-evaluation-ge-powered-f-15e-highly-successful); [F404 datasheet](https://www.geaviation.com/sites/default/files/datasheet-F404-Family.pdf).
10. **MIL-A-8866C and JSSG-2006** — structural repeated-load spectra methodology, landing sink-rate and runway-roughness distributions, braking/turning counts — [MIL-A-8866C](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF); [JSSG-2006](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2006.010206.PDF).
11. **Canada DND TAA Advisory 2016-02** — F404 usage severity vs forecast, usage-review practice — [canada.ca](https://www.canada.ca/en/department-national-defence/services/military-airworthiness/technical-airworthiness-authority-overview/technical-airworthiness-regulatory-documents/technical-airworthiness-authority-advisories/2016-02.html).
12. **Dabayeh et al. 2003 (CF-18 wing full-scale fatigue test)** — CF vs USN usage, IFOSTP, 10 Hz MSDRS spectrum — [WIT PDF](https://www.witpress.com/Secure/elibrary/papers/FDM03/FDM03003FU.pdf).
13. **NACA RM L54E18 (1954)** — training vs combat Nz statistics and mission activity ratios (historical) — [NTRS](https://ntrs.nasa.gov/api/citations/19930088093/downloads/19930088093.pdf).
14. **ICAF 2023 Mattos et al.; ICAS 2008 Chen et al.** — equivalent vs single flight profiles, mission-type load correlation (via Newcamp 2016), FPR-based IAT with variable stores — [ICAF](https://www.icaf.aero/icaf2023/proceedings/documents/75.pdf); [ICAS](https://icas.org/ICAS_ARCHIVE/ICAS2008/PAPERS/013.PDF).
15. **NASA TM-85902 (F100 EMD in F-15)** — AB light timing, throttle-response tasks (formation, AAR) — [NTRS](https://ntrs.nasa.gov/api/citations/19840016520/downloads/19840016520.pdf).
16. **Wikipedia articles** (aircraft, engines, IAF stations, squadrons) — secondary; used only for spec-sheet and basing facts, with underlying citations to ADA/HAL/Saab/GE/USAF.
