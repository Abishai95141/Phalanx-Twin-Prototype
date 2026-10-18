# Grounding Phalanx's Virtual Tejas in Evidence

*Revision 2 (2026-10-14). Changes from revision 1:*
- *Section 8: the periodic bursts and the recorder clock offset are corrected to be one clock-domain-slip mechanism.*
- *Section 13: the timing model is updated to match.*
- *Section 14: the maintenance-orders channel (M21) and the forkable world (M22) are added.*
- *Section 16: decisions D18–D20 are added.*
- *Section 17: the texture settling experiment becomes the gate before Tejas modules.*

**Bottom line.** Phalanx should build a **"Tejas-class" virtual fighter**. It combines a HAL Tejas Mk1A airframe, flight-control system and utility suite with a **GE F404-GE-IN20 modelled as a "composite F404"**.
- **Truth state** comes from physics: 6-DOF flight dynamics, a 0-D component-level engine with a FADEC replica, and lumped utility networks.
- **Observations** pass through an explicit sensor, signal-validation, bus and recorder chain.
- **Residual texture** is fitted to measured real recorder data rather than invented.
- **Faults** are hidden physical states driven by usage, kept separate from sensor faults.
- **Maintenance records** are generated as a linked, deliberately imperfect event stream.
- **Decisions** enter through a typed, logged orders channel, and the world can be snapshotted and forked. Prescriptive advice can therefore act on the fleet and be tested against counterfactuals without breaking reproducibility.

**Why the Tejas.** It is the IAF's highest-future-weight fighter (220 planned), has the most public system-level documentation of any IAF type, and visibly shows the fragmented, multi-agency maintenance problem the problem statement describes ([CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf); [Kala, JOAST 67(2A)](https://joast.org/index.php/joast/article/view/317)). Its engine shares the F404 family with the F/A-18 A–D and the Gripen RM12, whose monitoring systems are publicly documented ([AGARD-CP-448](https://archive.org/details/DTIC_ADA203800)).

**What public information supports.** It supports a credible *structure* for almost every layer: architecture, sensor sets, control logic, monitoring semantics, record types, usage statistics and data formats. It does **not** support fighter-specific absolute values for most limits, schedules, rates and texture parameters. Those must be declared as provenance-tagged, swept assumptions or transfers.

**Credibility ceiling.** No fighter telemetry is public, so validation against proxies caps credibility at **NASA-STD-7009B Validation Level 2** ([NASA-STD-7009B](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf)). The design therefore treats every parameter as replaceable data. The downstream AI consumes the ground-decoder output, not the simulator internals. When DSSC, IAF or HAL data arrive, they recalibrate the layers without a redesign.

---

## How to read this report

**Evidence tags** are kept from the underlying notes and appear per claim or per table row.

| Tag | Meaning |
|---|---|
| **[DIRECT]** | About the Tejas, the F404-GE-IN20 or the IAF itself. |
| **[DIRECT-part]** | An Indian (mostly HAL/DDP) product page gives the numbers but does not name the aircraft. Treat as one notch below [DIRECT]. |
| **[DIRECT-unnamed]** | An ADA/ADE/NAL author describes "a typical tailless fighter" that is almost certainly the LCA. Treat as one notch below [DIRECT]. |
| **[TRANSFER: X]** | Borrowed from platform, fleet or standard X, with a stated reason and limits. |
| **[MEASURED]** | Computed by Phalanx from real NASA DASHlink regional-jet recorder data (Tail 687, archive 1). These are real-data measurements but **not fighter data**; any fighter use is a transfer. |
| **[ASSUMPTION]** | Engineering judgement or arithmetic, with a validation route. |
| *(snippet-level)* / *(search excerpt)* | Known only from a search-engine excerpt; weaker evidence. |

**Source restrictions.** Two circulating manuals are restricted: an F/A-18 A–D NATOPS copy (Distribution C) and a Hellenic AF F-16 flight manual (foreign-disclosure statement). Values that came only from them are **not used as evidence** anywhere in this report. Officially released replacements are used where they exist. Items still unreplaced are listed by name in Appendix A as *sanity-check only / open*.

**Credibility ceiling.** Validation against a representative or proxy system earns at most NASA-STD-7009B Validation Level 2. Levels 3–4 need real-system data ([NASA-STD-7009B Table 9](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf)). Read every validation claim below against that ceiling.

**No premature lock-in.** Recommendations are the current best direction, not final choices. Section 16 is a decision register. For each major choice it records the evidence, the alternatives held open and what would change the decision.

## Contents

0. [The Tejas Mk1A with a composite F404 is the right target](#0-the-tejas-mk1a-with-a-composite-f404-is-the-right-target)
1. [Q1 — Seventeen documented systems, unequally worth modelling](#1-q1--seventeen-documented-systems-unequally-worth-modelling)
2. [Q2 — 189 observables, 50 hidden states, and the gap between them](#2-q2--189-observables-50-hidden-states-and-the-gap-between-them)
3. [Q3 — Corrected parameters and N2 tie the variables together](#3-q3--corrected-parameters-and-n2-tie-the-variables-together)
4. [Q4 — Tejas sorties are short, surge-capable and task-limited](#4-q4--tejas-sorties-are-short-surge-capable-and-task-limited)
5. [Q5 — Data leaves the aircraft as a post-flight download, not a live stream](#5-q5--data-leaves-the-aircraft-as-a-post-flight-download-not-a-live-stream)
6. [Q6 — No public fighter telemetry exists; each dataset teaches one layer](#6-q6--no-public-fighter-telemetry-exists-each-dataset-teaches-one-layer)
7. [Q7 — Physics carries the truth path; data-driven methods carry texture and speed](#7-q7--physics-carries-the-truth-path-data-driven-methods-carry-texture-and-speed)
8. [Q8 — Real residuals are lattices, bursts, offsets and colour, not Gaussian noise](#8-q8--real-residuals-are-lattices-bursts-offsets-and-colour-not-gaussian-noise)
9. [Q9 — Faults live in hidden physical states that usage drives and maintenance resets](#9-q9--faults-live-in-hidden-physical-states-that-usage-drives-and-maintenance-resets)
10. [Q10 — Calibrate on the proxy, then swap the platform](#10-q10--calibrate-on-the-proxy-then-swap-the-platform)
11. [Q11 — A discriminator is a test, not a definition of realism](#11-q11--a-discriminator-is-a-test-not-a-definition-of-realism)
12. [Q12 — Five keys and deliberate defects link telemetry to the logbook](#12-q12--five-keys-and-deliberate-defects-link-telemetry-to-the-logbook)
13. [Q13 — One canonical sample with six timestamps and explicit validity](#13-q13--one-canonical-sample-with-six-timestamps-and-explicit-validity)
14. [Q14 — Twenty-two replaceable modules, a closed decision loop and forkable worlds](#14-q14--twenty-two-replaceable-modules-a-closed-decision-loop-and-forkable-worlds)
15. [What public information can and cannot deliver](#15-what-public-information-can-and-cannot-deliver)
16. [Decision register](#16-decision-register)
17. [Prioritised gaps and next concrete steps](#17-prioritised-gaps-and-next-concrete-steps)
18. [Conclusion](#18-conclusion)
- [Appendix A — Restricted, unreplaced, snippet-level and conflicting values](#appendix-a--restricted-unreplaced-snippet-level-and-conflicting-values)
- [Appendix B — Where the detail lives](#appendix-b--where-the-detail-lives)

---

## 0. The Tejas Mk1A with a composite F404 is the right target

The choice was made in two research stages.
- **Stage 1** scored candidate aircraft on public modelling data and on relevance to the problem owner.
- **Stage 2** stress-tested that choice with Tejas-specific research.

The two stages pulled in different directions. The decision holds only because Stage 2 changed the evidence.

**Stage 1 favoured the F/A-18 on modelling data alone.** The rubric scored seven criteria from 0 to 5: aero, systems, engine, sensors, flight data, PHM literature and India relevance.
- **F/A-18 A–D: 26/35, the highest.** It has a documented NASA aero database (α −10…90°, β ±20°, Mach 0–2), flight-identified derivatives, quantified air-data and INS models, and a real ~2,000-parameter telemetry catalogue ([TM-110216](https://ntrs.nasa.gov/citations/19960027892); [CR-201670](https://ntrs.nasa.gov/citations/19970014822)).
- **Tejas: 12/35.** Aero and sensors scored 1 because only specifications appeared to be public.
- **Engines.** The F100-PW-220 has the deepest public modelling corpus: a complete real-time model with normalised maps, DEEC control logic and Kalman health parameters ([TM X-3261](https://ntrs.nasa.gov/citations/19750019996); [CP-2298](https://ntrs.nasa.gov/citations/19860015871)). Once Indian relevance was weighted in, a "composite F404" targeted at the IN20 already came first at 24.5/40. It led the F404-400/402 (23), the F100-PW-220 (22) and the AL-31FP (21) ([GE F404 data sheet](https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf)).

**Stage 2 removed the main objection to the Tejas.** Stage 2 harvested the Defence Science Journal in full (≈4,000 records) and JOAST in full (≈900 records). NAL, ADA and HAL authors turned out to have published a great deal, often without naming the aircraft:
- a full inertia tensor at ≈9 t: Ixx/Iyy/Izz/Ixz = 14,088/66,559/77,875/2,491 kg·m², CG 34 % MAC ([DSJ 71(2)](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347));
- a low-speed short-period model with an unstable root of +0.256 s⁻¹ at M0.22 ([DSJ 57(4)](https://www.publicationsdrdo.in/index.php/dsj/article/view/1785));
- flight-estimated Cmα, Cmq and Cmδe ([JOAST 56(3)](https://joast.org/index.php/joast/article/view/754));
- a wind-tunnel lift curve, Cnβ(α) with a cliff near 25° AoA, and a time-to-double map ([AeSI FTG 2005](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf));
- flight stability margins and an 8 ms computation delay ([JOAST 58(4)](https://joast.org/index.php/joast/article/view/741));
- DFCC, sensor and actuator specifications ([Kala](https://joast.org/index.php/joast/article/view/317)).

**Stage 2 supersedes the Stage-1 Tejas aero and sensor scores.** The longitudinal flight-dynamics core and the FCS/air-data sensor layer can now be anchored on [DIRECT] or [DIRECT-unnamed] Tejas data.

**Relevance to the problem owner is decisive.**
- **Future weight.** The Tejas has the highest future weight in the IAF: 220 LCA planned and 2 Mk1 squadrons today ([18th LS 12th Report](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_12.pdf?source=loksabhadocs)).
- **Indian design authority.** ADA, ADE, HAL and CEMILAC hold design authority. A demonstrator can therefore credibly propose integrating DFCC BIT, ECMS/HUMS, e-MMS and IMMOLS data.
- **The the problem statement failure modes appear in public records:**
  - in 2015, 69 LRUs had no HAL repair-and-overhaul capacity and 167 LRUs depended on imports ([CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf));
  - GE engine supply delays;
  - jet-fuel-starter start failures in the cold and at altitude at Leh;
  - a false-warning artefact in fuel gauging ([ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf));
  - a fleet-wide grounding of about two months in Feb–Apr 2026 over brake-system software ([Tribune](https://www.tribuneindia.com/news/india/iafs-grounded-tejas-jets-to-resume-flying-next-week-after-software-fix-says-hal-chairman/)).

That last pattern matters for design. **Tejas availability risk today is dominated by supply-chain, software-configuration and engineering-authority events, not by squadron wear-out.** The generator must therefore emit configuration and fleet-grounding events, not only component wear [DIRECT pattern; ASSUMPTION as a generator requirement].

**The engine is the weakest Tejas link, and transfer donors close it.**
- **What GE publishes about the IN20.** Only four numbers: 84 kN (19,000 lb class) maximum thrust, 70 kg/s airflow, OPR 28 and 1,072 kg. Qualitatively, it adds FADEC, single-crystal turbine blades, -402 parentage and "330 h AMT ≈ 1,000 flight hours" ([GE data sheet](https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf); [GE 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight)).
- **What ADA publishes.** Only that the Tejas has an Engine Condition Monitoring System that computes life-usage indices and monitors vibration ([ADA Propulsion](https://www.ada.gov.in/images/ps.htm)).
- **F404-400/402 donors.** Officially released Australian, Canadian, US Navy and NASA documents fix the architecture, sensors, control structure, operating lines, transient constants, monitoring and life counting ([ARL 1985](https://archive.org/details/DTIC_ADA164562); [CR-191195](https://ntrs.nasa.gov/citations/19940032893)).
- **FADEC-era donors.** RM12 and F404-GE-102 (T-50) sources supply the FADEC-era behaviour ([SHK RM 2019:02](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf); [KSAS 2006](https://koreascience.kr/article/JAKO200616039849001.pdf)).

**The resulting donor map** is explicit, and every donor is labelled in the parameter metadata.

| Layer | Primary anchor | Transfer donors | Role of the donor |
|---|---|---|---|
| Airframe geometry, mass, inertia, longitudinal aero, FCS, air data, actuators | Tejas [DIRECT / DIRECT-unnamed] | — | Anchor |
| Lateral-directional damping and control derivatives, nonlinear shapes | — | FOI ADMIRE/GAM (canards neutralised); NASA F-106B tailless delta; F-16 TP-1538 only as a fallback | Shape and structure donor ([FOI-R--1624--SE](https://www.foi.se/rest-api/report/FOI-R--1624--SE); [TM-2003-212145](https://ntrs.nasa.gov/citations/20030013626)) |
| Engine cycle, sensors, control, monitoring, life usage | GE IN20 ratings [DIRECT] | F404-400/402 (F/A-18 A–D, CF-18, RAAF); RM12 (Gripen); F404-GE-102 (T-50) | Primary engine donors |
| Engine modelling method, FDA logic, health-parameter estimation | — | NASA F100 corpus; C-MAPSS40k/MAPSS; T-MATS; pyCycle | Methods template, not the displayed platform |
| Utilities | Tejas LRU facts [DIRECT / DIRECT-part] | MIL-STD-704F, MIL-H-5440H, MIL-E-18927E, MIL-G-26988C; Gripen modelling practice; F/A-18 HARV signal catalogue | Normal-behaviour bands and signal sets |
| Fleet availability and maintenance ecosystem | IAF process facts [DIRECT] | CAG Su-30MKI and MiG-21 Bison figures; USN/USAF/UK record systems | Calibrates availability; templates for records |
| Recorder and residual texture | — | DASHlink Tail 687 [MEASURED]; IECMS quantisation and precision; F/A-18C 1553 word lists | Mechanisms and magnitudes |

**Rejected alternatives, and what would revive each:**
- **Su-30MKI.** This is the strongest audited embodiment of the problem. CAG reports 55.50–59.73 % serviceability against a 75 % norm, AOG of 10.90–15.32 % and flying-task shortfalls of 31–43 % ([CAG 38/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf)). But it has almost no open system-level documentation. The AL-31FP's public cycle data are aggregator-grade and its monitoring layer is undocumented, so a high-fidelity model would be mostly assumption. It is kept as the **calibration source for the fleet-availability layer**. It becomes the target only if DSSC/IAF prioritise it and can supply sanitised data; the same architecture would then carry an AL-31FP dictionary.
- **F/A-18 A–D.** The best-documented real fighter, but irrelevant to the IAF. Retained as the engine and monitoring donor.
- **F-16.** Has the richest open-source code, but its public aero covers low speed only, its engine family is unrelated and its public sensor data are minimal. Kept as a verification referent (NESC check cases) and a post-stall fallback.
- **Gripen.** The closest configuration analogue (single-engine delta, F404-derived RM12), but not an IAF type. Used as an enrichment source.
- **Mirage 2000, Rafale and Eurofighter.** Only headline data are public.
- **F100-PW-220.** The best-understood engine, but used only as a methods template because its India relevance is minimal.

**Fidelity follows maintenance relevance.** The purpose is predictive maintenance and fleet availability, so modelling effort goes where maintenance signals originate:
- the engine gas path and its monitoring;
- hydraulic and actuator duty;
- the texture of the recorder and data pathway;
- the event and record streams.

Lateral-directional high-α aerodynamics, avionics internals and detailed ECS thermodynamics get only enough fidelity to keep cross-system couplings physically consistent [ASSUMPTION; Section 7 gives the per-behaviour allocation].

---

## 1. Q1 — Seventeen documented systems, unequally worth modelling

CEMILAC's airworthiness account lists **17 systems, 344 LRUs and 33 embedded software systems** for the Tejas ([CEMILAC, JOAST 67(2A)](https://joast.org/index.php/joast/article/view/325)). An older secondary figure of ">500 LRUs" is superseded by CEMILAC's 344. Delivery status is also a constraint: **no Mk1A had been delivered by 15 May 2026**, and HAL targets about 20 in FY 2026-27 ([HAL analyst call](https://hal-india.co.in/backend/wp-content/uploads/2026/05/Transcript_May15-2026-signed.pdf)). A "Mk1A-representative" model therefore rests on Mk1 evidence plus announced Mk1A changes:
- a new mission computer, digital map generator, smart MFDs and indigenous DACS;
- an indigenous PowerPC DFCC;
- an indigenous HUMS data-acquisition unit.

The table below assigns modelling fidelity by maintenance relevance. Each row gives the publicly evidenced facts and what has to be borrowed.

| System | Public Tejas facts (tag) | Borrowed or assumed | Fidelity, and why |
|---|---|---|---|
| **Airframe and mass** | Span 8.20 m; length 13.20 m; wing area 38.4 m²; LE sweeps 50°/62.5°; TE −4°; empty 6,560 kg (LSP actual 6,682–6,802 kg); clean take-off 9,800 kg; MTOW 13,500 kg; inertia tensor above [DIRECT / DIRECT-unnamed] ([ADA brochure](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf); [DSJ 71(2)](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347)) | MAC ≈5.5 m and CG travel [ASSUMPTION]; internal fuel ≈2,458 kg (secondary) | Medium-high: trim drives actuator duty and thrust demand |
| **Flight control** | Quadruplex digital FBW with no mechanical backup; 4 channels plus cross-channel data link; 80 Hz frame (12.5 ms); 8 ms computation delay; median voting; gains scheduled on Mach and altitude; fixed-gain reversionary law with undercarriage-dependent gains; AoA limiter; CBIT/PBIT/MBIT; 23 diagnosable subsystems per channel (92 in total) [DIRECT] ([Kala](https://joast.org/index.php/joast/article/view/317); [JOAST 58(4)](https://joast.org/index.php/joast/article/view/741); [JOAST 782](https://joast.org/index.php/joast/article/view/782)) | Gain tables, blend points, voting thresholds [ASSUMPTION/TRANSFER] | High: BIT, channel dropouts and actuator commands are maintenance signals |
| **Actuation** | 13 actuators (4 elevons, 1 rudder, 6 slats, 2 airbrakes); Moog quadruplex-electrical, dual-hydraulic primaries at 280 bar with direct-drive valves; ~9 Hz response; 2–10 t stall load; rudder ±30° at 100°/s; differential elevon ±18° at 45°/s [DIRECT / DIRECT-unnamed] | Symmetric elevon ±25° (secondary); symmetric rate 60–80°/s [ASSUMPTION] | High: actuator stroke and rate histories drive hydraulic and actuator wear |
| **Air data and inertial** | Nose probe (NADP), two side probes (SADP), two AoA vanes, AoSS vane, TAT probe; quadruplex ADCs over RS-422; transducers Ps 35–1,300 / Pt 35–2,700 / Δp 35–1,500 mbar at 0.02 % FS; vanes with quadruplex LVDTs over ±45°; rate sensors ±300/±60 °/s at 50 Hz; accelerometers ±13/±4.5 g at 100 Hz; ADC BIT coverage 90 %; heater-flag-dependent temperature correction tables; air-data error depends on undercarriage state [DIRECT] ([Kala](https://joast.org/index.php/joast/article/view/317); [DSJ 56(1)](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863)) | SIGMA 95N laser-gyro INS/GPS (secondary); vane dynamics and position error [TRANSFER] | High for texture and BIT; medium for dynamics |
| **Engine (F404-GE-IN20)** | 84 kN AB thrust; 70 kg/s; OPR 28; 1,072 kg; FADEC; ECMS with life-usage indices and vibration monitoring [DIRECT] | Stages 3-7-1-1; 100 % N1 = 13,270 rpm; 100 % N2 = 16,810 rpm [TRANSFER: -400]. BPR ≈0.28, fan PR ≈4.35, T4 ≈1,780 K [ASSUMPTION from cycle closure]. Dry thrust ≈54 kN (aggregator + closure) | Highest: most maintenance value and best monitoring donors |
| **Secondary power** | PTO shaft: 118 N·m normal / 410 N·m peak start at a rated 16,810 rpm. AMAGB: four pads (2 hydraulic pumps, 1 generator, 1 starter), self-contained lubrication, 750 h life. GTSU-110 JFS: 110 kW, 52 kg, free power turbine. Requirement of 3 consecutive starts [DIRECT] ([DDP AMAGB](https://www.ddpmod.gov.in/node/8779); [DDP GTSU-110](https://www.ddpmod.gov.in/node/8778); [CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf)) | Gear ratios; JFS timing and EGT limits [ASSUMPTION] | Medium-high: JFS start success is a documented availability story |
| **Hydraulics** | Two 280 bar systems; tandem dual-hydraulic primaries; single-hydraulic slats; 9 filters of 6 types [DIRECT]; probable bootstrap reservoirs of 9.5 L with level sensor [DIRECT-part] | Pump flow unconfirmed (a "110 L/min" lead is a search excerpt) | High: leakage, pressure sag and filter loading are classic PHM targets |
| **Fuel** | F1, F1A and F2 fuselage tanks plus wing tanks; ≈2,458 kg internal; drop tanks of 1,200/800/725 L; gauging and transfer by ECFM-C; capacitance probes (±3/±5 µs); air-to-air refuelling at 250–295 kt; documented false low-fuel warning at >40° pitch, max AB and <1,200 kg fuel [DIRECT] ([ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)) | Tank capacities, transfer sequence, CG schedule | Medium: gauging artefacts matter more than tank physics |
| **Electrical** | Imported main AC generator on the AMAGB; DRDO 5 kW brushless DC backup generator whose GCU has BITE [DIRECT]; probable two 7.5 kW/250 A TRUs and a 45 Ah battery with a 30 Ah warning [DIRECT-part] | Main generator rating (not public); bus bands from MIL-STD-704F [TRANSFER] | Medium |
| **ECS and life support** | Bleed-air bootstrap-class ECS for cockpit, avionics, radar and fuel pressurisation; OBOGS; LOX on Mk1; hot-air-leak detection [DIRECT] | HAL fighter ECS: bleed 2.8–6.4 bar and 175–440 °C over 75–97 % rpm [TRANSFER: HAL fighter] ([Heliyon 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9708630/)) | Low-medium: needed for bleed–engine coupling and for avionics-cooling-related NFF |
| **Landing gear, brakes, tyres, chute** | Carbon-carbon brakes (3 rotors / 4 stators); brake-by-wire with anti-skid; main tyre 26×8.0-14 (probable 16.9 bar); 17 m² chute deployed at ≤285 km/h (normal) and ≤340 km/h (emergency), life 45 streamings / 8 years; RTO tests at 50/70/90 % brake wear; 2026 brake-software event [DIRECT / DIRECT-part] ([DDP chute](https://www.ddpmod.gov.in/hi/node/8027)) | Tyre and brake wear per landing [TRANSFER: F-16, F-15] | Medium-high: per-landing counters and a ready-made fault chain |
| **Avionics and warnings** | Open Architecture Computer (OAC) as the hub, combining mission computer, display processor, video switching and mission preparation/retrieval; MIL-STD-1553B; Centralised Warning System with 30 red/amber legends and 4 voice warnings, ARINC-429 plus 30 discrete inputs and a FADEC warning interface [DIRECT / DIRECT-part] ([tejas.gov.in OAC](http://web.archive.org/web/2015/http://www.tejas.gov.in:80/technology/open_architecture_computer_for_avionics.html)) | Number and allocation of buses; ICD ("three 1553B buses" is a secondary claim only) | Low for internals; high as the data path |
| **Utility management** | Four electronic units on prototypes became two in production (BHEEM-EU, ECFM-C); dual-redundant utility management system; microprocessor brake management system [DIRECT] ([NFTC 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)) | I/O lists, BIT logic, rates | Medium: this is the caution and BIT layer |
| **Recording and health** | Crash data recorder fed by DFCC 1553; MPDRU function absorbed into the OAC; digital video recorder; ECMS usage log; FTI of ≈1,500 parameters with 12 telemetry stations; Mk1A HUMS DAU (PCC PCAMi-1000, 124-unit production order, Feb 2026) [DIRECT] ([ADU](https://www.aviation-defence-universe.com/pcc-advances-indigenous-hums-capability-with-pcami-1000-production-order)) | Formats, parameter lists, rates [TRANSFER/ASSUMPTION] | High: this is the pathway the AI sees |
| **Structure** | +8/−3.5 g operational, +9 g design/FOC; 8.5 g flown at M0.87; 6 g at M1.2 [DIRECT]; IAF fatigue-index practice (Hawk 100 FI) [DIRECT IAF] | Exceedance spectra [TRANSFER: F-16] | Low: usage counters only |

---

## 2. Q2 — 189 observables, 50 hidden states, and the gap between them

**The observable inventory is a seed for a synthetic ICD, not a claim about the real one.** Phalanx has consolidated **189 logical parameters**, each with 33 fields: identity, units, origin sensor and LRU, class, range, resolution, native/bus/recorder rates, redundancy, five sink flags, validity flags, physical drivers, related parameters, texture mechanisms, three rate-group fields, evidence tag and source (`parameter_inventory.csv`).

| Breakdown | Counts |
|---|---|
| By subsystem | Engine 41 (including 8 LUIs and TAC); FCS 31; air data 20; avionics status/warnings/recorder/metadata 20; navigation 14; hydraulics 10; usage counters 10; ECS and life support 9; electrical 8; gear/brakes/chute 7; secondary power 6; fuel 6; ground-inspection bridges 6; fire 1 |
| By class | 80 measured; 54 computed; 23 discretes; 20 counters; 6 events; 6 ground inspections |
| By evidence | 62 DIRECT-only; 70 DIRECT plus transfer or assumption; 44 transfer-led; 9 assumption-only |

Expanding redundancy turns these into **well over 300 physical channels**: 12 rate-sensor channels, 8 accelerometers, 16 ADC transducers, 12 vane LVDTs, 8 T5 probes and ~20 surface positions. The Tejas FTI adds about 1,300 test-only parameters [DIRECT count; ASSUMPTION mapping]. The weakest rows are the engine-monitoring content and all bus- and recorder-level specifics, which rest on F404 and F/A-18 transfers.

**Sensor physics is public for the F404 family and partly public for the Tejas FCS.** The key sensor classes are below.

| Class | Tejas / IN20 specifics | Tag and source |
|---|---|---|
| Fan speed N1 | 2 eddy-current pickups counting 42 fan blades (0.7 Hz/rpm) | TRANSFER: -400 ([CR-191195](https://ntrs.nasa.gov/citations/19940032893)) |
| Core speed N2 | Separate winding on the gearbox-mounted alternator (0.239 Hz/rpm) | TRANSFER: -400 (same) |
| EGT (T5) | 2 × 4-probe Type K harness averaged with open-probe exclusion; a shorted probe reads low and raises fuel flow; τ 1.25–3.9 s depending on mass flux; ±18 °F system error | TRANSFER: -400 ([CR-1998-208416](https://ntrs.nasa.gov/citations/19980219005)) |
| T1 (inlet temperature), PS3, P5, Wfm, A8, FVG/CVG, PLA | RTD with hot-air de-icing; pressure transducers (a dedicated IECMS P3 transducer on the -400); pulse-rate fuel-flow meter; LVDT positions | TRANSFER: -400 |
| Oil, vibration, debris | Oil pressure (psid) and temperature; mid-frame accelerometer with N1/N2 1/rev tracking; 3 sumps, 5 bearings, 7 chip detectors | TRANSFER: -400 ([ARL 1985](https://archive.org/details/DTIC_ADA164562); [DSTO-TN-0530](https://archive.org/details/DTIC_ADA423658)) |
| Legacy aircraft data chain (upper bound) | Resolution: N 16 rpm, T 1 K, PS3 0.5 psia, P5 0.06 psia. 2σ precision: N1 154 rpm, N2 138 rpm, T5 2.0 K, PS3 1.2 psia. Readings "within one bit toggle" | TRANSFER: -400 IECMS ([Henry, AGARD-CP-448](https://archive.org/details/DTIC_ADA203800)); OCR-corrected values |
| FCS inertial | Rate sensors ±300/±60 °/s, 50 Hz, 0.005 °/s; accelerometers ±13/±4.5 g, 100 Hz, thresholds 2/0.2 mg; quadruplex | DIRECT ([Kala](https://joast.org/index.php/joast/article/view/317)) |
| Air data | Quadruplex ADC transducers at 0.02 % FS; vanes ±45°; triplex voting; heater currents simplex | DIRECT |
| Hydraulic pressure | ±0.25 % FS (≈ ±0.9 bar at 280 bar); 10 ms | TRANSFER: MIL-PRF-25435D class |
| Fuel quantity | Capacitance probes with frequency output; Class I gauging ±2 % near empty / ±6 % near full | DIRECT probes; TRANSFER class ([MIL-G-26988C](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-G/MIL-G-26988C_36788/)) |
| Electrical | Voltage, current and frequency within MIL-STD-704F bands | TRANSFER ([MIL-STD-704F](https://everyspec.com/MIL-STD/MIL-STD-0700-0799/MIL-STD-704F_CHG-1_55461/)) |
| Gear and brakes | Lock and WoW discretes; wheel speed; brake pedal pots; NWS pots | DIRECT LRUs ([ADA LRU list](https://www.ada.gov.in/images/LRU.pdf)); TRANSFER rates |

**Each signal goes to a different subset of sinks, which is the fragmentation the problem statement complains about.** Of the 189 rows, the evidenced/assumed counts per sink are:
- cockpit: 72 / 44;
- crash recorder: 93 / 56;
- ECMS/HUMS: 89 / 25;
- maintenance download: 108 / 67;
- FTI-only: 3.

The generator should emit these sinks as **separate streams with different subsets and rates**. The downstream AI then has to reconcile partially overlapping sources, just as real maintainers do [ASSUMPTION grounded in the inventory].

**What is not measured is where maintenance value hides.** `not_measured_states.csv` lists **50 hidden physical states** in four observability classes.

| Observability class | Examples (state IDs) | How it shows in measured signals | What reveals it |
|---|---|---|---|
| Model-observable only | Fan/HPC/HPT/LPT health (`NM.ENG.*_HEALTH`), tip clearance, VG actuation, true sensor value (`NM.ENG.SENSOR_TRUTH`), hydraulic pump efficiency, compensator drift, actuator leak, ECS heat-exchanger fouling, ACM wear, fuel-probe drift, generator health, JFS health, battery SOH, FCS/air-data biases, vane friction, heater element | Small shifts in corrected cross-plots, residuals against a model, voting mistracks | Gas-path analysis, model residuals, ground runs |
| Usage-inferred only | Disc LCF life, blade creep, structural fatigue, brake wear and temperature, tyre wear, chute life, AMAGB wear | Counters only (LUIs, TAC, Nz counts, landings, streamings) | Life tracking; inspection at interval |
| Late-symptom only | Blade crack, bearing spall, seal wear, nozzle hardware, AB spray bar, fuel nozzles, FADEC hardware, hose fittings, gear lock springs, wiring, solder fatigue, actuator friction | Nothing until late: chips, vibration, stalls, codes | Chip detector, ODM, borescope, failure |
| Ground inspection only | Accumulator precharge, filter loading, fluid contamination, oil condition, strut servicing, composite damage, water ingress or corrosion | Not on any bus | Servicing checks, sampling, NDT |

Several engine quantities that analysts would want are **not measured in flight at all**:
- engine airflow and gross thrust exist only in the test cell ([Muir et al., AGARD-CP-448 paper 7](https://archive.org/details/DTIC_ADA203800));
- afterburner fuel flow is not measured in flight on the CF-18 [TRANSFER];
- T25 is internal to the FADEC;
- LUI gates and weightings are unpublished.

**Hidden states cannot be uniquely recovered from observables.** For the F100, an observability study showed that sensor biases and engine deviation parameters are equivalent, so "it is undecided whether the estimated engine deviation parameters represent the actual engine deviation or whether they simply reflect the measurement biases" ([España & Gilyard, TM-4551](https://ntrs.nasa.gov/citations/19940017406)). Phalanx must therefore generate sensor bias and component deterioration as **separate latent processes with separate ground truth**, so that downstream models can be tested for confusing them.

---

## 3. Q3 — Corrected parameters and N2 tie the variables together

**Engine variables collapse onto corrected-parameter lines, imperfectly.**
- Normalising by inlet temperature and pressure ratios (θ, δ), using N/√θ, W√θ/δ and Wf/(δ√θ), is standard practice. F404 test-cell diagnostics require "standard-day corrected" data ([Roemer et al., DTIC ADA408947](https://apps.dtic.mil/sti/citations/ADA408947)).
- On real recorder data, θ/δ correction reduces fuel-flow scatter **from 22 % to 2 %**. The best-fitting exponents are not the textbook ones, and about 2 % altitude-structured residual remains [MEASURED] ([Phalanx DASHlink analysis](../analysis/dashlink_texture/results/corrected_exponent_scan.csv); data from [DASHlink Tail 687](https://c3.ndc.nasa.gov/dashlink/resources/664/)).
- The generator should therefore produce near-collapse with a structured residual, not perfect collapse.

**The F404 control structure determines how faults appear.** For the -400:
- **Below IRP:** N2 is scheduled on PLA and T2.5, and A8 on PLA, with a PS3 ≤ 80 psia override.
- **At or above IRP:** NL is held isochronously as a function of T1, with a 104.4 % corrected cap, and a PS3 ≥ 425 psia limit. **A8 is modulated to hold T5 = f(T1, P0).**
- **Throughout:** accel/decel limits act on Wf/PS3; fan VG follows N1c and compressor VG follows N2c; AB fuel is scheduled in ratio units with nozzle pre-open and an N1-within-3 % permission ([ARL 1985](https://archive.org/details/DTIC_ADA164562); [NAWCADPAX/RTR-2001/1](https://archive.org/details/DTIC_ADA407860); [CR-1998-208416](https://ntrs.nasa.gov/citations/19980219005)).

Deterioration therefore shows up differently by regime. At IRP it appears **as A8 opening and an NL/thrust shortfall at the T5 limit**; below IRP it appears as higher T5 and Wf at a given N2 [TRANSFER: F100 DEEC behaviour, "FTIT rises to hold EPR until the limit, then thrust falls" ([CP-2298](https://ntrs.nasa.gov/citations/19860015871))].

**Fault signatures have known directions in corrected cross-plots.** The CF-18 programme published a direction matrix (θ1/δ1-corrected; W1 and Fg exist only in the test cell) ([Muir et al., AGARD-CP-448 paper 7](https://archive.org/details/DTIC_ADA203800)):

| Fault | W1 vs N1 | N2 vs N1 | Fg vs N2 | Wfm vs N2 | PS3/P1 vs N2 | T56 vs P56/P1 | N2 vs P56/P1 |
|---|---|---|---|---|---|---|---|
| Fan flow/efficiency loss | ↓ | ↓ | ↓ | ↓ | ↓ | ↑ | ↑ |
| HPC flow/efficiency loss | — | ↑ | ↓ | ↓ | ↓ | ↑ | ↑ |
| HPT efficiency loss | ↓ | ↓ | ↑ | ↑ | ↑ | ↑ | ↓ |
| LPT efficiency loss | — | ↑ | ↓ | — | — | ↑ | — |
| Fan VG above limits | ↓ | ↑ | — | — | — | — | — |
| Compressor VG above limits | — | ↓ | ↑ | ↑ | ↑ | ↓ | ↓ |

Measured magnitudes anchor the scale:
- **HPC blade damage:** about −5 % HPC efficiency equivalent, giving +8 % PS3/P1 and +8–14 % Wf at fixed N2.
- **6° compressor-VG mis-rig:** about +8 % PS3/P1 and +11 % Wf.
- **Correcting for VG and A8 positions** cuts scatter 2–3×.

**The F404 "can take considerable component damage and still pass the EPR performance verification test"** (same source). Transient (take-off) data detect implanted faults with higher sensitivity than steady-state data ([Eustace et al., JEGTP 1994](https://doi.org/10.1115/1.2906789)).

**Measured cross-sensor structure is strong and lagged.** In real cruise data [MEASURED] ([results](../analysis/dashlink_texture/results/engines_crosssensor_summary.csv); [transients](../analysis/dashlink_texture/results/transients_summary.csv)):
- residual correlations: r(N1, N2) = 0.87, r(N1, FF) = 0.75, r(N1, EGT) = 0.53;
- EGT lags the spools by 0.75–1.25 s;
- time constants: N1 0.9–1.3 s accelerating and 2–3 s decelerating; fuel flow ≈1.3 s; EGT 3–6 s.

Generating FF, N1, N2 and EGT from one engine state, rather than independently, is what produces these correlations.

**Airframe-to-maintenance relationships run through trim and actuator duty.**
- Published Tejas trim AoA at 8 km is 12.45° at M0.4, 6.59° at M0.6 and 2.46° at M1.0 ([DSJ 49(3)](https://www.publicationsdrdo.in/index.php/dsj/article/view/3828)).
- Trimmed elevon positions, actuator stroke and rate histories, hydraulic flow (Q = A·ẋ) and rate limits that scale with √(ΔP available − ΔP load) [TRANSFER: HARV] are the variables a maintenance model consumes.
- This is why the aero model is anchored on the Tejas longitudinal core. Rescaled F-16 tables would misrepresent tailless elevon trim and therefore actuator duty.

**N2 is the master variable for the utility systems.** Every utility power source is slaved to N2 through fixed ratios. The coupling map ([tejas_utility_systems synthesis](https://www.ddpmod.gov.in/node/8779); [Heliyon 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9708630/); [TM-104247](https://ntrs.nasa.gov/citations/19920020182)) contains these key edges:

| Driver | Driven | Mechanism and sign | Time scale | Tag |
|---|---|---|---|---|
| N2 | AMAGB, pump and generator speeds | Fixed gear ratios | Instant | DIRECT speed; ratios ASSUMPTION |
| N2 × actuator demand | Hydraulic pressure | Compensated pump holds 280 bar until demand exceeds Q_max(N2); sag at low N2 and high demand | 10–100 ms | ASSUMPTION; MIL-H-5440H |
| Hydraulic temperature | Leakage, pump volumetric efficiency | Viscosity ↓ → leakage ↑ | Minutes | TRANSFER |
| N2 spool-down | Main generator online state | Underspeed → generator offline → 5 kW DC backup/battery (≤50 ms transfer) | 0.05–1 s | TRANSFER (AIB) |
| Battery SOC, OAT, altitude | JFS start success | Cold or low charge reduces cranking power | Per start | DIRECT (Leh failures) |
| N2/PLA, altitude, Mach, OAT | Bleed pressure and temperature | 75→97 % rpm gives 2.8→6.4 bar and 175→440 °C | Seconds | TRANSFER: HAL fighter |
| Bleed extraction | Thrust and T5 | ≈1 % more bleed at MIL ≈ −2 % thrust | Seconds | TRANSFER: -400 |
| Pitch, Nx, Nz, slosh | Indicated fuel, low-fuel warning | Fuel surface tilt; false low-fuel at >40° pitch, max AB, <1,200 kg | Seconds | DIRECT |
| Fuel flow (heat-sink capacity) | Fuel, oil and hydraulic temperatures | Low Wf plus hot ambient raises temperatures | Minutes | TRANSFER |
| Landing mass, speed, chute, runway μ | Brake energy → heat-sink temperature → wear | E = ½mV² minus drag and chute | s to min | DIRECT limits + TRANSFER |
| WoW | FCS law, NWS, anti-skid, ECS, recorder and BIT modes | Discrete mode switch (a false WoW can select the ground law in flight) | Instant | TRANSFER (F-35 AIB) |
| Cold soak | Battery, viscosity, precharge, tyre pressure, JFS | Gas law and viscosity | Hours | DIRECT + TRANSFER |
| Dust, sand, salt | Filter ΔP, seal wear, HX fouling, compressor fouling | Contaminant ingress | 100s of hours | DIRECT (Indian fouling) + TRANSFER |

**Ambient conditions act through the same relationships.**
- Indian bases span δ ≈ 0.67–0.99 and ambient temperatures from −28 to 49.9 °C. Hot desert afternoons give density altitudes of about 4,000–5,200 ft, and Leh about 14,500–15,300 ft ([IMD Climatological Tables 1991–2020](https://imdpune.gov.in/library/public/Climatological%20Tables%201991-2020.pdf)).
- Hot or high conditions automatically raise physical N and EGT, shift idle rpm and invoke T5 limiting near MIL, provided the engine model is written in corrected parameters.
- Humidity matters too. A micro-turbojet transfer gives wet-versus-dry thrust −2.8 % and SFC +1.3 % ([KARI](https://koreascience.or.kr/article/JAKO201074648803472.do)); this is unverified for low-bypass fighter engines.

**Encode all of this as one typed dependency graph.** Edge types are shaft power, hydraulic, thermal, data/electrical, discrete logic and mechanical. Each edge carries a transfer function and a latency. The same graph then serves three purposes:
- normal-behaviour coupling;
- fault propagation (Section 9);
- validation invariants such as energy and mass balance (Section 10).

---

## 4. Q4 — Tejas sorties are short, surge-capable and task-limited

**IAF usage is set by a flying task and limited by serviceability.**
- **How the task is set.** The MoD fixes annual flying tasks in squadron "Policy Pages" against a 75 % serviceability norm.
- **What fleets achieve.** Audited fighter fleets achieved about **45–70 % of task**: Su-30MKI 57–69 % (2004–09) and MiG-21 Bison 44–71 %. Low serviceability was the main cause ([CAG 38/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf)).
- **Total volume.** Accident-rate tables imply that the IAF flies a roughly constant **≈2.4–2.6 lakh flying hours per year** across all types (1990–2018) [DIRECT data → INFERENCE] ([16th LS 47th Report](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_47.pdf?source=loksabhadocs)).

A virtual squadron should therefore plan sorties from a task, then cancel or abort a fraction driven by simulated serviceability, weather and bird activity. That is the IAF's own causal chain.

**Tejas sorties are shorter than Western squadron sorties, and the stage-2 model supersedes stage 1.**
- **Development flying (to IOC):** per-aircraft averages of 30–51 min and a fleet mean of ≈38 min (2,441 sorties, 1,560.8 h). Only 1–5 sorties per aircraft per month, against an ADA-desired 22 ([CAG 17/2015 Annex III](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf)).
- **FY 2018-19:** 524 sorties averaging ≈40 min, and 32–75 h per aircraft ([ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)).
- **Squadron donors:** FINAF ≈52 min, RAAF ≈72 min and a Gripen median of ≈74 min [TRANSFER] ([ICAF Finland 2017](https://sarjaweb.vtt.fi/julkaisut/muut/2017/ICAF_Doc2433_Finland_Review_2017.pdf); [White et al. 2015](https://www.humsconference.com.au/Papers2015/Non_peer_Reviewed/White01.pdf); [Chalmers 2014](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf)).
- **Recommended Mk1A squadron model:** a lognormal with **median ≈45–55 min and 5th–95th percentile ≈25–90 min**, shifted up by 15–30 min with drop tanks or air-to-air refuelling [ASSUMPTION; validate against squadron authorisation books].
- **Supersession.** This replaces the stage-1 median of 70–80 min, which rested on Gripen and USAF guidance.

**Surge capacity is documented.** In Gagan Shakti 2018 the IAF flew **>11,000 sorties (≈9,000 fighter) in 15 days at 80 % serviceability** ([PIB](https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=178885)). The Tejas flew 6 sorties per aircraft per day with 8 aircraft, with snags on 6 of them on day 1 ([ANI via Business Standard](https://www.business-standard.com/article/news-ani/india-made-tejas-acquits-itself-well-at-gagan-shakti-18-118042500151_1.html), secondary). Use a scenario parameter of **≈1–2 sorties per aircraft per flying day in peacetime and 4–6 in surge**. Night sorties are ≈10–20 % [ASSUMPTION; all 52 operational bases are night-capable ([18th LS 2nd Report](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs))]. Base climates come from IMD monthly counts of rain, thunder, fog and dust days:
- Coimbatore/Sulur: 68.5 rain, 45.6 thunder, 6.5 fog and ≈0.9 dust days per year;
- Naliya: ≈27 rain, 14.9 fog;
- Bikaner: 7.6 dust days ([IMD](https://imdpune.gov.in/library/public/Climatological%20Tables%201991-2020.pdf)).

**The phase table below uses only officially released or physics-derived values.** Restricted-manual values are excluded; unreplaced items are listed in Appendix A.

| Phase | Released or derived anchors | Tag and source |
|---|---|---|
| Power-up and BIT | The prototype FBW diagnostic took ≈10 min (TD-1); DFCC sensor BIT runs before each flight; modern LRUs are faster [ASSUMPTION] | DIRECT ([Kala](https://joast.org/index.php/joast/article/view/317)); prototype timing secondary |
| Engine start | GTSU-110 JFS. T-50 (F404-102 FADEC) timeline: PLA to idle at ≈20 % N2, light-off ≈27 s, starter cut-out ≈55 % N2, idle ≈63–70 % N2 at ≈40 s. Hung-start monitor: N2 < 60 % and not rising for 1 s, or < 60 % for 35 s. Requirement of 3 consecutive starts; −15 °C / 85 % battery / 18–42 h soak demonstration | DIRECT (Tejas) ([CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf)); TRANSFER: -102 ([KSAS 2006](https://koreascience.kr/article/JAKO200616039849001.pdf)); NASA rule ([TM-101702](https://ntrs.nasa.gov/citations/19900013006)) |
| Ground idle | F404-400 test cell: fuel flow 685 lb/h, N2 10,960 rpm (≈65 %), N1 5,159 rpm, 632 lbf; idle EGT ≈409 °C | TRANSFER: -400 ([USAF IERA Vol. 3](https://archive.org/details/DTIC_ADA361473); [CR-191195](https://ntrs.nasa.gov/citations/19940032893)) |
| Taxi | USAF default (combat aircraft): taxi-out 18.5 min, taxi-in 11.3 min | TRANSFER ([USAF Air Emissions Guide](https://archive.org/details/DTIC_ADA577276)) |
| Run-up / MIL | MIL: N2 15,994 rpm (≈95 %), N1 13,167 rpm (≈99 %), fuel flow 7,739 lb/h, 9,608 lbf; intermediate 6,464 lb/h; steady-state T5 limit 830 °C (-400) | TRANSFER: -400 ([IERA](https://archive.org/details/DTIC_ADA361473); [TM-101702](https://ntrs.nasa.gov/citations/19900013006)) |
| Take-off | Lift-off ≈290–325 km/h at 9.8 t [ASSUMPTION: physics]; AB light-off 0.7–2.7 s MIL→max and 3.6–8.0 s flight idle→max; nozzle closes ≈1 s after a slam and stays closed ≈4 s; take-off record lasts 6–10 s | TRANSFER: -402/-400 ([NAWCADPAX/RTR-2001/1](https://archive.org/details/DTIC_ADA407860); [AGARD-CP-448](https://archive.org/details/DTIC_ADA203800)) |
| Climb, cruise, mission | Cleared envelope: M1.6, 26° AoA subsonic (≈4° at M1.55), +8/−3.5 g, 8.5 g at M0.87, 6 g at M1.2, 620 kt / M0.95 at low level, ceiling 15 km; measured AAR closure 1.7–4.3 kt against a 10 kt design maximum | DIRECT ([ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf); [DSJ 70(2)](https://www.publicationsdrdo.in/index.php/dsj)) |
| Approach and landing | Approach ≈260–285 km/h [ASSUMPTION: physics]; sink rate per MIL-A-8866C (mode 3–4 ft/s); naval LCA structure cleared to 5.8 m/s and flown to 3.7–3.9 m/s | TRANSFER ([MIL-A-8866C](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF)); DIRECT naval |
| Chute | Deploy ≤285 km/h (154 kt) normal, ≤340 km/h (184 kt) emergency; 45 streamings / 8 years | DIRECT ([DDP](https://www.ddpmod.gov.in/hi/node/8027)) |
| Shutdown | Gripen recorded average idle before shutdown 259 s | TRANSFER ([Chalmers 2014](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf)) |
| Turnaround | Hot refuelling demonstrated; up to 5 ski-jump sorties per day (naval prototype); no minute figures | DIRECT |

**Engine duty-cycle targets come from USAF design guidance and F404-family fleet data.** The targets below are calibration gates, not exact values. Variability is the norm:
- per-flight life-usage CV ≈0.5;
- engine-to-engine dispersion factor ≈1.3;
- mission-type severity ratio (max/min) 1.5–5 ([RTO-TR-028](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf)).

USN F404 usage was severe enough to cut life limits by about 50 % ([Canada TAA 2016-02](https://www.canada.ca/en/department-national-defence/services/military-airworthiness/technical-airworthiness-authority-overview/technical-airworthiness-regulatory-documents/technical-airworthiness-authority-advisories/2016-02.html)).

| Metric | Target | Source |
|---|---|---|
| Type III (idle–max–idle) cycles per FH | ≈5 (gate 5 ± 2) | [JSSG-2007A](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf); [MIL-HDBK-1783B](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf) |
| AB lights per FH | 4–5 | same |
| Time at IRP and above / in AB | 17–20 % / ≈5 % of FH | same |
| TAC per FH | ≈2.2 (design); 3.3 per EFH measured (F-15E/F110); 3.5 TAC and 6.2 AB lights per sortie (F110 AMT) | same; [GE FSE](https://www.geaerospace.com/news/press-releases/defense-engines/field-service-evaluation-ge-powered-f-15e-highly-successful); [GE 2004](https://www.geaerospace.com/news/press-releases/f110-ge-129-slep-engine-achieves-major-milestone) |
| Engine operating time per EFH | **1.56 (FINAF F404-402, preferred for the F404 family)**; 1.35 (F-22 design, alternative) | [ICAF Finland 2017](https://sarjaweb.vtt.fi/julkaisut/muut/2017/ICAF_Doc2433_Finland_Review_2017.pdf); JSSG-2007A |
| AMT equivalence | IN20: 330 h AMT ≈ 1,000 FH | DIRECT ([GE 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight)) |
| Nz exceedances per 1,000 h | F-16 operational: ≈7,000 at 5 g, ≈1,300 at 7 g, ≈10 at 9 g (graph-read ±30 %); roll peaks ≈13 % of Nz peaks | TRANSFER ([AGARD R-815](https://archive.org/details/DTIC_ADA324348); [ASD-TR-72-113](https://archive.org/details/DTIC_AD0761491)) |
| Fleet severity index | RNLAF F-16: 1.03 at home vs 0.31 on deployment; FINAF and RAAF Hornet usage more severe than design | TRANSFER ([NLR-TP-98172](https://reports.nlr.nl/items/654cb62e-1a8f-489f-a987-e47b44d39317/full)) |

**Generate sortie instances hierarchically and check them against fleet statistics.** The generator has six layers:
1. **Calendar layer.** A fleet calendar driven by the flying task, with seasonal weather-cancel probabilities from IMD monthly day counts.
2. **Sortie layer.** Mission type drawn from a squadron-role mix. Defaults for OCU and operational squadrons are [ASSUMPTION] until IAF syllabi are available. Then draw duration, configuration, base, and ambient conditions from IMD normals or ERA5 replay.
3. **Phase grammar.** A fixed opening (power-up → start → idle → taxi → take-off → climb), mission blocks, and a fixed closing (RTB → pattern, with optional touch-and-go loops → landing → taxi → optional hot refuel → shutdown).
4. **Manoeuvre layer.** A semi-Markov library of manoeuvre primitives that respects envelope, fuel and AB budgets.
5. **Pilot layer.** Latent per-pilot traits: throttle activity, g-onset aggressiveness, AB propensity, cooldown discipline, and AAR closure speed. For AAR closure, use a per-pilot mean of 2–3.5 kt with SD ≈0.7 kt; the NFTC data show a clear pilot effect.
6. **Physics layer.** Mass from fuel and stores, engine in corrected parameters, and deterioration.

Accept a configuration only if fleet statistics fall inside the gates above. Carry thermal state between sorties, because short turnarounds affect brakes, oil and start conditions.

---

## 5. Q5 — Data leaves the aircraft as a post-flight download, not a live stream

**The public Tejas data path is clear at the front end and dark at the back end.**

*On board*, each DFCC channel carries:
- a 1553B interface;
- RS-422 links to the ADCs;
- a cross-channel data link.

The DFCC's 1553 output feeds the crash data recorder, the Get-U-Home panel and FTI ([NFTC 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)). The OAC is the avionics hub, and utility and health management report "system health and warnings to the pilot through" it ([tejas.gov.in Systems](http://web.archive.org/web/2016/http://www.tejas.gov.in:80/specifications/systems.html)). Other recording and monitoring elements on board are:
- a digital video recorder;
- the ECMS usage log;
- the CWS with its FADEC warning interface;
- for Mk1A, a configurable HUMS DAU with Ethernet master–slave expansion. Its RTD, thermocouple, pressure, vibration and 1553/ARINC inputs are *(snippet-level)* ([PCC](https://www.parkcontrols.com/industries/air)).

*On the ground*, the public elements are:
- an aircraft systems maintenance simulator (ASMS);
- ADE's Automatic Fault Diagnosis System for the DFCC, which maps failed test-step numbers to 92 subsystems through per-subsystem offsets ([JOAST 782](https://joast.org/index.php/joast/article/view/782));
- the IAF's e-MMS (paperless since April 2020), IMMOLS, the IAF–HAL "Havai" portal and AFNET.

**No public statement says that e-MMS ingests on-board data.** The aircraft → squadron → BRD/HAL/ADA flow is not described anywhere, so it has to be modelled on released precedents [TRANSFER]:
- **F/A-18 IECMS:** maintenance recorder tape (≈7 flights) → ECAMS ground station → Parts Life Tracking;
- **F-16/F110 EMS:** data transfer cartridge → ground station at the aircraft maintenance unit → base engine management → central system;
- **F-35 ALIS:** PMD → reader → SOU → CPE → ALOU ([AGARD-CP-448](https://archive.org/details/DTIC_ADA203800); [GAO-20-316](https://www.gao.gov/products/gao-20-316)).

**Real programmes fail at decoding and linkage, not at transmission.** The aircraft-to-ground boundary is a **post-flight batch download**. The documented failures are data integrity and record linkage:
- ALIS saw 0–400 record issues per week at one site;
- 81 % of delivered spares lacked electronic records;
- staff spent 5,000–10,000 hours per year on manual tracking ([GAO-20-316](https://www.gao.gov/products/gao-20-316)).

Missing or obsolete frame-layout metadata is the other failure. In one case the EGT conversion in a recorder's data frame layout was simply wrong ([BEA 2005](https://bea.aero/uploads/tx_scalaetudessecurite/use.of.fdr_01.pdf)). At NAS Lemoore, I-level technicians had to reconcile engine logbooks against two systems before work could start, which averaged **14 days** ([Hagan & Slack 2006](https://archive.org/details/DTIC_ADA462668)).

**The recommended emission design is layered, with the ground decoder as the contract.** Recommendations are [ASSUMPTION grounded in the cited evidence].

| Layer | What it is | Content | Why |
|---|---|---|---|
| **CIR** (canonical internal representation) | Acquisition-level samples plus a versioned Parameter Dictionary | Per sample: parameter ID, all time fields, measured EU value, truth value (internal only), source LRU/lane, validity, quality flags | All fault, degradation and texture models write here once |
| **Adapter A: bus encoder** | CIR → 1553 bus-controller schedule and RT messages per a **synthetic "Phalanx ICD"** (AS15532-style words, status and BIT words), plus ARINC-429 labels with SSM | Update rates, scaling, packing, staleness, status/BIT, bus errors | Realistic avionics artefacts; the real ICD is not public |
| **Adapter B: recorder writer** | Bus messages + analog/discrete + time + recording events → **IRIG 106 Ch10/11** file per sortie, with TMATS first; optional live Ch10 over UDP / TCP 10620 | Raw system of record | The only fully public byte-level standard spanning multi-bus capture, metadata and time ([IRIG 106 Ch10](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2); [TMATS Ch9](https://www.trmc.osd.mil/wiki/download/attachments/113019518/chapter9.pdf?api=v2)) |
| **Adapter C: ground decoder** | Ch10 → decoded EU samples with quality and provenance → Kafka topics and Parquet sortie tables | **The stable downstream contract** | Mirrors real ground decoding; would also ingest genuine Ch10 FTI data |
| **Adapter D: health and maintenance events** | On-board events (BIT, exceedances, usage counters) inside Ch10 *and* decoded; ground records keyed by tail, serial and sortie | Event and record streams | Linkage and data-quality realism |
| **Fast path** | CIR → Adapter C's schema directly, marked `provenance=direct` | Same schema | Early AI work, without lock-in |

**Why the downstream AI plugs in at the ground-decoder contract.**
- It mirrors the real boundary. Real maintenance data cross to the ground by downloading recorder or PMD media, so standardising there means the PdM system never depends on simulator internals.
- It exercises the decoding layer, where real programmes fail on metadata. That layer becomes real, testable code rather than an idealisation.
- Replay, idempotency, duplicate downloads and late arrival behave as they would with real downloads.
- The same decoder can ingest genuine Ch10 FTI data if HAL, ADA or ASTE ever provide some, so the AI can be evaluated on real data without change.
- Simulator modules can be swapped, recalibrated or replaced by real feeds without breaking the AI, because only the dictionary and adapters change.

The Ch10 choice is explicitly a **surrogate**. No evidence shows that any candidate's operational recorder uses IRIG 106. Alternatives held open:
- an ARINC 717 frame adapter (civil FDR/QAR style);
- an AFDX/Ethernet adapter (Mk2 TSN-like);
- MQTT/Sparkplug or DDS transports;
- XidML alongside TMATS.

**Phase the build so value arrives early.**
- **Phase 1:** CIR + dictionary + fast path + event adapter, on Kafka and Parquet.
- **Phase 2:** Adapters A and B, with round-trip tests (CIR → Ch10 → decode → compare with CIR within quantisation). Use independent BSD-3 parsers ([pyChapter10](https://github.com/atac/pyChapter10), irig106lib) and conformance checks against public sample `.c10` files.
- **Phase 3:** live Ch10-over-UDP streaming and optional Ch7/ARINC 717 adapters.

Keep the sinks separate: crash recorder (continuous loop, bus monitor), ECMS log, HUMS DAU, OAC maintenance log, and FTI (test only). Each has different subsets and rates, so the downstream system faces real fragmentation [ASSUMPTION].

---

## 6. Q6 — No public fighter telemetry exists; each dataset teaches one layer

**No raw fighter telemetry was found in any public dataset.** Real fighter-state data is limited to ADS-B/MLAT kinematics. adsb.lol publishes ODbL daily traces with a military flag ([adsb.lol](https://www.adsb.lol/docs/open-data/historical/)). Every other dataset teaches one layer and must be used only for that layer.

| Dataset | Size / access | What it can teach | What it cannot | Phalanx use |
|---|---|---|---|---|
| **NASA DASHlink Sample Flight Data** | 35 tails, ~245 GB; 186 multi-rate parameters; Tail 687: 9 zips, 7.15 GB; archive 1 (0.84 GB) **already measured** ([project 85](https://c3.ndc.nasa.gov/dashlink/projects/85/)) | Recorder texture: lattices, sentinels, bursts, validity gating, clock artefacts, per-unit offsets, regime heteroscedasticity, cross-sensor lags | Fighter dynamics, duty cycle, military recorders; autothrottle effects do not transfer | Texture mechanisms and priors (Section 8); proxy for "simulate the proxy" |
| DASHlink curated 4-class anomaly set | 1.6 GB | Labelled approach anomalies | Fighter faults | Detector benchmark |
| **N-CMAPSS** | 15.76 GB ([S3](https://phm-datasets.s3.amazonaws.com/NASA/17.+Turbofan+Engine+Degradation+Simulation+Data+Set+2.zip)) | Usage-driven onset and degradation laws; 7 failure modes; real flight conditions taken from DASHlink Tail 687 ([arXiv 2003.00732](https://arxiv.org/abs/2003.00732)) | Real sensor noise (synthetic); low-bypass AB engine | Degradation-template backbone; known-synthetic contrast |
| C-MAPSS | 12.4 MB | Baseline wear tables | Texture (iid noise assumed "because no real data was available") ([Saxena 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf)) | Negative control |
| **NGAFID + MaintNet** | 4.29 GB + 6,169 logbook rows ([arXiv 2210.07317](https://arxiv.org/abs/2210.07317); [MaintNet](https://people.rit.edu/fa3019/technical/aircraft.html)) | The only real flight ↔ maintenance pairing: 28,935 flights, 2,111 events, 36 classes, 1 Hz, ~1 % NaN; logbook text texture | Fighter physics (GA piston) | Linkage, text texture, pre/post-maintenance shifts |
| PX4 ULog index | 476,531 logs (35,613 SITL) ([dbinfo](https://review.px4.io/dbinfo)) | µs timestamps, logged dropouts, asynchronous rates; sim vs real in one format | Fighter sensors | Timing texture; discriminator testbed |
| **RflyMAD** | ~8 GB of real/HIL/SIL subsets ([RflyMAD](https://rfly-openha.github.io/documents/4_resources/dataset.html)) | One fault taxonomy across SIL, HIL and real flights | Fighter dynamics | **Testing the discriminator itself** |
| CAFUC2; CMU ALFA | small; 272 MB | Real flights with physics-injected anomalies; real fault flights | Fighter | Injection-realism comparison |
| ESA-AD | 3.78 GB ([arXiv 2406.17826](https://arxiv.org/abs/2406.17826)) | Irregular sampling and gaps at scale | Aircraft physics | Missingness stress tests |
| Airbus helicopter accelerometers; **DSTG HUMS2025/2027** | 1.04 GB; HUMS2027 raw spall data at 51.2 kHz | Vibration texture; natural spall progression with debris | Fighter engine | AMAGB/bearing vibration texture |
| UCI hydraulic rig; NASA FLEA | 73.1 MB; 294 MB | Pump leakage/precharge levels; EMA electrical texture | Aircraft parameters | Hydraulic/actuator degradation shapes |
| PHM 2024/2025 | small | Snapshot + maintenance-count linkage | Provenance unclear | Maintenance-count features |
| **Published fighter reports** (NASA F404 operating points TM-100159, CR-198052, TM-4538, TM-4240 step responses; Henry/Muir IECMS; KSAS T-50 airstarts; SHK RM12 trace; AIB recorded engine data; AGARD R-815) | Report figures and tables | Absolute fighter levels, transients and fault signatures | Raw texture | Calibration and validation targets, digitised at ≤ ½ the tolerance |

**Recommended acquisition order**, from the datasets note:
1. Further DASHlink Tail 687 archives and a second tail (Tail 652, 6.10 GB), for drift persistence and tail-to-tail spread.
2. N-CMAPSS.
3. NGAFID + MaintNet.
4. The PX4 index plus targeted fixed-wing logs and a matched SITL subset.
5. RflyMAD real/HIL/SIL subsets.
6. ALFA.

**Time-critical:** DSTG HUMS2027 registration closes **31 Oct 2026**; the data are restricted and non-shareable ([HUMS2027](https://www.humsconference.com.au/HUMS2027datachallenge/download.html)).

**Do not learn texture** from C-MAPSS, the N-CMAPSS sensor channels, the scaled SMAP/MSL values or the HUMS2023 TSA data. Their noise is synthetic or processed.

---

## 7. Q7 — Physics carries the truth path; data-driven methods carry texture and speed

**The fighter-simulation literature converges on first-principles structure plus empirical tables.** Examples include NASA HARV, the TP-1538 F-16, MAPSS and the F404 table-plus-lag model. **ML is absent from the truth path in all of them** ([TM-110216](https://ntrs.nasa.gov/citations/19960027892); [MAPSS](https://ntrs.nasa.gov/citations/20040035577)).

Generative and black-box ML carries documented failure modes for a *truth* generator:
- physically inconsistent outputs: a black-box network was inconsistent in **≈73 % of time steps** despite lower RMSE ([Daw/Karpatne](https://arxiv.org/abs/1710.11431));
- memorisation of training data ([Carlini et al.](https://arxiv.org/abs/2301.13188));
- linear extrapolation off-support ([Xu et al.](https://arxiv.org/abs/2009.11848));
- no agreed evaluation metrics ([TSGBench](https://arxiv.org/abs/2309.03755)).

There is also no public fighter data to train on. Hybrids help PHM *estimation*, with a RUL horizon about 127 % longer on N-CMAPSS ([Arias Chao](https://arxiv.org/abs/2003.00732)). But they are identifiable only with constraints such as minimum-norm residuals ([APHYNITY](https://arxiv.org/abs/2010.04456)), and they are trustworthy only inside their training distribution ([Wehenkel et al.](https://arxiv.org/abs/2202.03881)).

The recommended technique per behaviour is below. "v1" is the current best direction; "kept open" lists the live alternatives.

| # | Behaviour | Technique class | Recommended v1 | Key evidence | Kept open / what would change it |
|---|---|---|---|---|---|
| 1 | Baseline atmosphere | Physics (standard) | USSA-1976 / ISA | Equals ICAO to 32 km | — |
| 2 | Climatic extremes | Lookup / envelope | MIL-HDBK-310 profile and envelope tables | [MathWorks atmosnonstd](https://www.mathworks.com/help/aerotbx/ug/atmosnonstd.html) | — |
| 3 | Real Indian weather | Empirical replay | ERA5 replay + METAR override; IGRA for validation | [ERA5](https://confluence.ecmwf.int/display/CKB/ERA5%3A+data+documentation) | Stochastic weather generator if fleet-scale runs need it |
| 4 | Turbulence and gusts | Statistical / state-space | von Kármán forming filters (Dryden for tests); 1−cos gust; log-profile shear; own RNG stream | MIL-F-8785C/1797 | Gaussian + modified-Bessel mixture for non-Gaussian vertical gusts ([NASA CR-2886](https://ntrs.nasa.gov/citations/19770025195)) |
| 5 | Rigid-body motion | Physics | Quaternion 6-DOF (JSBSim propagator or own) | [JSBSim](https://github.com/JSBSim-Team/jsbsim); NESC check cases | — |
| 6 | Aerodynamics | Lookup + system identification | **Tejas-anchored parametric build-up** (HAL table architecture; longitudinal core fitted to Tejas anchors; lateral from ADMIRE/GAM and F-106B; Mach trends from DATCOM/VSPAERO; build-up drag) | Section 0 sources; [Polhamus TN D-3767](https://ntrs.nasa.gov/citations/19670003842) | Rescaled F-16 tables only as fallback; real Tejas SI data would replace donors |
| 7 | FCS and actuators | Engineering relationships / state-space | Published-structure replica: gain-scheduled law, 80 Hz, 8 ms delay, limiters, reversion; Tustin actuators with rate and position limits, ~9 Hz | [Kala](https://joast.org/index.php/joast/article/view/317); [JOAST 58(4)](https://joast.org/index.php/joast/article/view/741) | Real CLAW tables if released |
| 8 | Gear and ground | Physics (lumped) | Spring–damper–friction contacts; brake energy → lumped heat sink | JSBSim BOGEY | — |
| 9 | Pilot and mission | Statistical / time-series | Deterministic guidance + crossover-type stochastic overlay; semi-Markov manoeuvre library | Crossover model; [DSJ 66(1)](https://www.publicationsdrdo.in/index.php/dsj/article/view/9196) tracking spectra | HMM/mixture once IAF usage data exist; RL agents excluded (unvalidated, non-deterministic) |
| 10 | Engine steady state | Physics + lookup | 0-D component model of a two-spool mixed-flow afterburning turbofan (pyCycle), scaled maps, humid-air thermodynamics | [pyCycle](https://github.com/OpenMDAO/pyCycle); MAPSS military CLM | NPSS/GSP; OEM deck if ever released |
| 11 | Engine transients | Physics / state-space | Rotor ODEs (I_HP ≈3, I_LP ≈3.5 kg·m², tuned), volumes, metal-temperature and tip-clearance states, AB light-off state machine, surge model | [TP-1034](https://ntrs.nasa.gov/citations/19770024210); [TM-4240](https://ntrs.nasa.gov/citations/19910009766) | Table + lag only as a labelled surrogate (≈3 % steady / up to 25 % transient error) |
| 12 | FADEC | Engineering relationships / logic | MIN/MAX selection of schedules and limiters, accel/decel Wf/PS3, VG and AB scheduling, flameout detection + auto-relight, FDIA with model substitution; tune with TTECTrA | [C-MAPSS40k control](https://ntrs.nasa.gov/citations/20100037768); [TTECTrA](https://github.com/nasa/TTECTrA) | Real IN20 FADEC logic if obtainable |
| 13 | Fast engine surrogate | System identification / state-space | PWL/LPV models identified from the CLM, labelled with error envelopes | [Armstrong & Simon](https://papers.phmsociety.org/index.php/phmconf/article/view/2136) | NN surrogate only within a sampled domain |
| 14 | Oil and fuel temperatures | Physics (lumped thermal) | Lumped-capacitance nodes driven by speed, load and Wf | MAPSS thermal states | Parameters are [ASSUMPTION] until data arrive |
| 15 | Engine vibration | Empirical / statistical | Order-tracked spectral synthesis (1×N1, 1×N2, harmonics + broadband), amplitude tied to fault states; per-speed-band processing | [EJ200 ADP014124](https://archive.org/details/DTIC_ADP014124); [DSTO-TN-0530](https://archive.org/details/DTIC_ADA423658) | Rotor-dynamic FE (unjustified effort) |
| 16 | Utility systems | Physics (lumped networks) + discrete-event | Hydraulic network with leakage conductances; fuel tank network with gauging model; average-value electrical network; ε-NTU ECS; gear/brake state machines | [Gripen practice](https://icas.org/ICAS_ARCHIVE/ICAS2006/PAPERS/039.PDF); MIL standards | Modelica FMUs as a high-fidelity "desktop" verifier |
| 17 | Sensor dynamics | Physics / engineering laws | τ ∝ W^−0.5 thermocouple; pneumatic lag; second-order vanes; heater error; position error | [AGARD-AG-160](http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf); Section 8 | — |
| 18 | Residual texture | Statistical / time-series | Layered parametric model fitted to [MEASURED] data (Section 8) | DASHlink measurement | Conditional diffusion/copula on residuals only, once real fighter data exist |
| 19 | Degradation | Statistical + physics-of-failure | Gamma, Wiener, threshold-onset, Paris, Poisson and Markov processes on physical states | Section 9 | PoF-only models if parameters become available |
| 20 | Sortie/fleet regimes | Statistical | Scripted mission catalogue + seeded sampling | Section 4 | Fitted HMM/mixture when IAF usage arrives |
| 21 | Maintenance and logistics | Empirical / statistical discrete-event | Event chains with empirical delay distributions | Section 12 | — |
| 22 | Learned corrections | Learned / hybrid | **None in v1**; v2 minimum-norm residuals behind feature flags, gated to the training domain | APHYNITY; Wehenkel | Enable only with real data and ablation evidence |
| 23 | Limits and envelopes | Lookup / envelope | Versioned tables | — | — |

**Separate the truth integrator from LRU sampling; this resolves a conflict between notes.** The notes recommend three different rates:
- the methodology note: a fixed 120 Hz major frame (JSBSim);
- the avionics note: independent clock domains (DFCC 80 Hz; FADEC 50–67 Hz; 1553 at 50/25/12.5 Hz);
- the engine note: an engine step of at least 200 Hz.

These are compatible if:
1. physics runs on a fixed step that is an integer multiple of the main domains — **240 Hz** is 3×80, 2×120 and 4×60;
2. stiff engine and hydraulic states sub-step internally;
3. each LRU domain samples truth on its **own drifting oscillator**, interpolating truth at its own tick.

This keeps the physics deterministic and produces realistic staleness, duplication and skew [ASSUMPTION; verify by step-halving and by checking that duplicate/skip statistics match a 40 Hz producer polled at 50 Hz].

The airframe↔engine and airframe↔FCS loops are broken by documented one-frame delays. A fixed Gauss–Seidel order runs environment → guidance → FCS → engine → airframe → utilities → sensors.

---

## 8. Q8 — Real residuals are lattices, bursts, offsets and colour, not Gaussian noise

**Phalanx's own measurement on real recorder data refutes "ideal + iid Gaussian".**
- **What was measured.** Archive 1 of DASHlink Tail 687 (651 files, 2001-03-20 to 2001-09-14, SHA-256 recorded). It was analysed with deterministic scripts in `analysis/dashlink_texture/`, seeded with `default_rng(687)` and re-runnable in about 15 minutes. The platform is a four-engine regional jet, **not a fighter**.
- **Main result.** Recorded data form a lattice-valued, frame-aligned stream. Its dominant texture is:
  - deterministic quantisation, with physical noise often below one LSB;
  - structured missingness that uses no NaNs;
  - regime-dependent, coloured variation;
  - persistent per-unit offsets with drift;
  - recorder timing artefacts.

| Measured finding [MEASURED] | Values | Result file |
|---|---|---|
| Rates and format | 186 parameters at 0.25/1/2/4/8/16 Hz (23/88/18/49/4/4); **zero NaNs** in 121,086 parameter-records | [param_table.csv](../analysis/dashlink_texture/results/param_table.csv) |
| Lattices | Every continuous channel lies on a regular grid; N1/N2 0.03125 %, EGT 0.5 °C, FF 8 lb/h, AoA 180°/4096, attitude 180°/16384 | same |
| Missingness | Zero-word sentinels in analog paths (vertical accelerometer 2.9 %, lateral/longitudinal 1.2–1.3 %); **periodic bursts every ≈1,099 samples lasting 9–24 s with 15–35 % loss**; correlated across channels (lift 6–80). **These bursts are clock-domain slip windows, not an independent dropout process (see the timing row and the correction below)** | [dropout_bursts.csv](../analysis/dashlink_texture/results/dropout_bursts.csv) |
| Validity gating and glitches | CAS/GS/TAS read 0 below 30/50/100 kt; all-ones words; invalid date triplets in 0.58 % of frames; inverted discretes (WOW, LGDN, LGUP, NSQT) | [recorder_glitch_frames.csv](../analysis/dashlink_texture/results/recorder_glitch_frames.csv) |
| Steady-segment noise (σ in LSB) | Oil P/T, TAT, FF 0.25–0.5 (pure toggling); EGT 0.6–0.8 (staircase); N1 1.3–2.4, N2 0.85–1.4 (coloured); accelerations 1–3.5 in cruise and 6–16 on ground; tails 15–90× Gaussian at 4σ | [texture_summary.csv](../analysis/dashlink_texture/results/texture_summary.csv) |
| Heteroscedasticity | Inertial and air-data HF noise ×10 on runway roll, ×1.3–1.8 on approach; engine-speed noise peaks ×3 at 50–70 % N1 | [hetero_summary_phase.csv](../analysis/dashlink_texture/results/hetero_summary_phase.csv) |
| Four-engine natural experiment | Persistent offsets: N2 ±0.4 %, EGT −7…+5 °C, FF −4…+3.5 %, oil pressure −6…+7 psi. EGT drift +1.3 °C per 30 days on one engine. Oil-pressure steps of 3–8 psi over two weeks | [engines_summary.csv](../analysis/dashlink_texture/results/engines_summary.csv) |
| Timing | 6 s clock-word granularity; clock word 917.6 ppm fast against sample count (median, n = 590 flights); fixed skews of 0.04–0.25 s; one lost frame in 748,592 | [recorder_checks_flights.csv](../analysis/dashlink_texture/results/recorder_checks_flights.csv) |

**Correction: bursts and clock offset are one mechanism** [MEASURED]. The first version of this report listed the periodic bursts and the clock offset as two separate texture features, and suggested the bursts might be a NASA processing artefact. They are one mechanism. A recorder that samples a source on a clock offset by Δ from the source's update clock loses one sample period of alignment every 1/(f·Δ) seconds. Near each slip, reads collide with source updates and return the sentinel. The measured burst intervals match that prediction at every rate:

| Rate f | Predicted 1/(f·Δ) with Δ = 917.6 ppm | Observed burst interval (median) | Implied Δ |
|---|---|---|---|
| 8 Hz | 136 s | 137 s | 912 ppm |
| 4 Hz | 272 s | 275 s | 909 ppm |
| 2 Hz | 545 s | 549 s | 911 ppm |
| 1 Hz | 1,089 s | 1,099 s | 910 ppm |

The ≈0.8 % gap between the burst-implied Δ (≈910 ppm) and the clock-word Δ (917.6 ppm) is consistent with the bursts measuring recorder clock against source clock, while the clock word measures recorder clock against GMT. That would put the source ≈8 ppm off GMT [ASSUMPTION; tested as P1–P5 in [the settling experiment](../analysis/settling_experiment/PREREGISTRATION.md)].

Converting burst duration to absolute time (duration × Δ) gives a collision window of ≈22 ms at 8 Hz, ≈17 ms at 4 Hz, ≈15 ms at 2 Hz and ≈9 ms at 1 Hz. That points to a conversion or update interval of order 10–20 ms in the acquisition unit [ASSUMPTION].

Consequences:
- Missingness is **generated by** the clock-domain model (Section 13), not by a separate dropout process.
- Burst period, phase and co-occurrence across channels all follow from oscillator offsets.
- The "tens of ppm" oscillator assumption is replaced by a per-LRU offset parameter whose measured proxy value is ≈910 ppm.

Figures: [σ vs LSB](<../research_notes/Virtual fighter telemetry layer research/figures/dashlink/fig_sigma_over_lsb.png>), [residual PSD](<../research_notes/Virtual fighter telemetry layer research/figures/dashlink/fig_residual_psd.png>), [engine offsets over flights](<../research_notes/Virtual fighter telemetry layer research/figures/dashlink/fig_engine_offsets_over_flights.png>).

**The measured mechanisms map onto twelve residual-model components.** Some transfer as mechanisms only; some transfer with their values. Notation: x = truth, y = recorded value, L = channel LSB.

| # | Component | Model and fitted values [MEASURED] | Transfer to the Tejas-class fighter |
|---|---|---|---|
| 1 | Word quantiser, no artificial dither | y = L·round((x + b_unit + e)/L); choose σ_e so recorded σ/LSB matches (oil 0.3–0.4, FF 0.4–0.5, EGT 0.6–0.8, N 1–1.5 independent) | Mechanism yes. LSBs come from F404/1553 scaling (16-bit words are much finer than 12-bit ARINC 717). The F404 legacy chain is the coarse bound: 16 rpm, 1 K, 0.5 psia ([Henry](https://archive.org/details/DTIC_ADA203800)). Where no LSB is known, choose it so steady σ ≈0.3–1.5 LSB [ASSUMPTION] |
| 2 | Coloured process component | AR(1)/Gauss–Markov; lag-1 φ: N1 0.83–0.94 (τ_c ≈1.3–4 s), EGT 0.85, FF 0.77–0.84 | Mechanism (closed-loop activity); fighter pilot inputs replace autothrottle |
| 3 | Regime multiplier | σ(regime) = σ_cruise·m: take-off/roll ≈10; approach 1.3–1.8; mid-power engine speeds ≈3 | Mechanism yes; fighter structural modes and high g add their own content |
| 4 | Heavy-tail mixture | Rare scaled draws giving 0.1–0.5 % beyond 4σ and excess kurtosis 0.3–3 | Mechanism yes; vertical gusts are genuinely non-Gaussian |
| 5 | Per-unit bias and drift | b_unit with SDs N2 ≈0.39 %, EGT ≈5 °C, FF ≈40 lb/h, oil P ≈5.5 psi, PLA ≈0.6°; flight-to-flight AR(1) jitter; occasional drift and steps | As fleet priors per tail and engine; refit across tails on a single-engine fleet |
| 6 | Structured missingness **as clock-domain slip** (merged with 11) | Recorder read times on the recorder clock; source updates on the source clock offset by Δ ≈ 910 ppm. A read that falls in a collision window w ≈ 10–20 ms around a source update returns the sentinel with in-window probability p ≈ 0.15–0.35. Bursts emerge with period 1/(f·Δ) and are phase-related across rates. Lost samples are written as sentinels, not NaN. Digital-bus channels show no sentinel losses; whether they show stale or duplicate reads at slips is under test (P4). *Superseded:* an independent periodic Gilbert–Elliott process (kept only as comparator L6′) | Mechanism yes. Δ, w and p are platform parameters: Δ comes from LRU oscillator tolerances and nominal-rate mismatches; w comes from acquisition-unit conversion time |
| 7 | Glitch words | All-ones at 10⁻⁵–10⁻⁴ per record-hour; corrupted frame-0 identity words; invalid clock words | Mechanism yes |
| 8 | Validity gating | Zero or hold below thresholds | Thresholds come from the Tejas ADC/INS ICD (unknown) |
| 9 | Deadband and episodic freeze | ≈1° lever deadband; whole-channel freezes of 1–3 min in ≈4 % of flights on one unit | Mechanism yes; rates unknown for fighters |
| 10 | Channel dynamics and latencies | EGT τ 3–6 s; fixed skews 0.04–0.25 s; derived-word latencies (+5 s / +3 s) | τ(W) form transfers (AGARD); magnitudes from F404 data |
| 11 | Recorder timing | Implicit frame time, coarse clock word, frame loss ≈10⁻⁶. The rate mismatch (Δ) is the same parameter that drives component 6 | Mechanism yes; numbers do not transfer |
| 12 | Cross-channel consistency | One engine state drives FF, N1, N2 and EGT; leave ≈2 % structured corrected-parameter residual | Yes, qualitatively |

**What does not transfer:** autothrottle-driven common-mode variance (common-mode share 0.4–0.7 in A/T cruise), airline phase durations and throttle duty (0.78 N1 cycles ≥60 % per hour, against ≈5.75 fighter Type I+III cycles per FH by design), four-engine equalisation, and the airliner engine's own time constants ([Q10 transfer matrix, Phalanx DASHlink note](../analysis/dashlink_texture/results/flight_level_summary.json)). The measured order of importance for realism is [MEASURED-informed ASSUMPTION]:
1. lattice quantisation without dither;
2. clock-domain slip (structured missingness and recorder timing, one mechanism);
3. per-unit bias and drift;
4. regime-dependent variance;
5. cross-channel consistency and lags.

**This ranking, and the premise of learning texture from a proxy, are under test.** The [settling experiment](../analysis/settling_experiment/PREREGISTRATION.md) asks one question: can synthetic DASHlink data, made by applying this texture model to a smooth truth, get as close to real as one real tail is to another? Its rules were fixed before any results. The test covers N1, N2, EGT, FF and VRTG, uses a trivial-cue audit and a discriminator ladder, and compares against a tail-vs-tail baseline. Nothing Tejas-specific is built on this layer until it reports.

**Wrap the stochastic layers in a physically structured measurement operator.** The model is y = H_chain(H_sensor(x_true, env), θ_unit, θ_age) + ε_regime. The sensor term carries class-specific physics, now quantified from released fighter or fighter-adjacent evidence [TRANSFER] ([texture gap closure sources](https://ntrs.nasa.gov/api/citations/19760016169/downloads/19760016169.pdf)).

*Air data:*
- vane f_n ≈0.11–0.21 Hz per m/s EAS and ζ ≈0.04–0.10;
- upwash 6–10 %, bias 0.4–0.7°, boom bending 0.06–0.1°/g;
- **misalignment steps of 0.1–0.3° after maintenance**;
- static-source error jumping to 0.08–0.16 q_c just below M1 ([Gracey RP-1046](https://ntrs.nasa.gov/api/citations/19800015804/downloads/19800015804.pdf));
- pneumatic lag ×4.3 at 40 kft;
- TAT recovery factor 0.977–0.994 and a de-icing heater error ≥0.2 °C;
- Tejas-direct heater-flag correction tables and gear-dependent error ([DSJ 56(1)](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863)).

*Fuel quantity:*
- Class I gauging ±2 % near empty / ±6 % near full;
- attitude error ≤1 % FS within ±10°;
- density-compensation residual 1–1.3 % (2σ);
- indicator response ≈6 s;
- one failed probe reconfigures, two failed probes hold ([MIL-G-26988C](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-G/MIL-G-26988C_36788/)).

This reproduces the Tejas zoom-climb false low-fuel warning.

*Fuel-flow meters:*
- turbine meters: τ ≈10 ms, ±2 %;
- angular-momentum meters: 300 ms update, ±0.9 % in cruise.

*Oil pressure:*
- ±1.5–2 psi on legacy units, τ 1–4 s;
- false-low readings dominate; the transmitter was the top F404 IFSD cause ([Glenny 1989](https://archive.org/details/DTIC_ADA210374)).

*FADEC-validated channels:*
- after accommodation, these carry synthesised substitutes with lower noise;
- a step or flag appears at detection ([TM-86735](https://ntrs.nasa.gov/citations/19850021650)).

The chain layers add anti-alias filtering, sample-and-hold, quantisation, saturation, redundancy management (average-with-exclusion, mid-value select), validity flags and bus/recorder rates.

**Fit residuals without knowing the truth, then refit when fighter data arrive.** In order of availability:
1. datasheet priors;
2. Allan variance or GMWM on static or ground segments;
3. Grubbs or triple collocation on redundant sensors (8 T5 probes, dual NL, quadruplex FCS sensors);
4. kinematic data compatibility with an EKF/RTS smoother for biases, scale factors and time skews;
5. model-based residuals with Mehra, ALS or EM covariance estimation;
6. snapshot regression for scatter and heavy tails;
7. recorder forensics: interval histograms, LSB lattice, frame counters ([Morelli & Grauer 2023](https://doi.org/10.2514/1.C037274)).

The DASHlink scripts are written to rerun on any new data by remapping channel names and regime definitions.

Two practices are explicitly rejected:
- the iid Gaussian σ of 0.25–0.75 % of reading used by gas-path benchmarks, which supplies magnitude anchors but no texture;
- treating coloured fighter residuals as white, which made uncertainty bounds more than 3× optimistic on the F-18 HARV ([Morelli & Klein 1995](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf)).

---

## 9. Q9 — Faults live in hidden physical states that usage drives and maintenance resets

**The architecture puts stochastic processes on physical states and keeps signatures physically derived.**

*State and observation:*
- Keep one hidden state vector per tail, per engine serial and per serialised component.
- Advance it with usage drivers from the flight-profile generator.
- Map it to observations through the closed-loop physics models, so signatures depend on operating point. The VIPR lesson is that signatures are weak at low power ([Rinehart & Simon](https://ntrs.nasa.gov/citations/20150000899)).

*Sensor faults:*
- Corrupt observations in a **separate** sensor-fault layer.
- Feed control-sensor faults back into actuation through an explicit **signal-validation layer**.

*Interpretation and propagation:*
- Interpret observations through imperfect BIT and EHM with incomplete coverage and false alarms.
- Propagate effects through a typed dependency graph.
- Reset or perturb states through maintenance actions that both restore and inject faults ([faults synthesis](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf)).

The hybrid trades interpretability for parameters that fighters do not publish. Every [TRANSFER] parameter therefore carries an uncertainty range and is swept in validation.

**Choose the process model per mechanism.**

| Mechanism class | Process | Parameters and anchors | Tag |
|---|---|---|---|
| Recoverable fouling | Wiener-with-drift on (η, Γ), drift ∝ dust index, partial reset by washing | ≈1 % Γ and ≈1 % η for roughness 1.8→13 µm ([Kurz & Brun](https://torroja.dmt.upm.es/congresos/asme_2011/data/pdfs/trk-19/GT2011-45012.pdf)) | TRANSFER |
| Non-recoverable erosion, clearance, wear | Gamma process; mean rate from commercial data × **fighter severity factor S** | A few % η/Γ over thousands of cycles; HPC accelerates after ~3,000 cycles; ProDiMES fleet HPC η ≈ −5 % at 5,000 flights; **S initially 1.5–2**, from the ≈50 % F404 life cut | TRANSFER + ASSUMPTION (S) |
| Early-life rub-in | Step + short exponential after every build | ≈1 % TSFC on flight 1, ≈1.5 % by ~200 flights ([Sallee](https://ntrs.nasa.gov/api/citations/19800013837/downloads/19800013837.pdf)) | TRANSFER |
| Abnormal onset | Cumulative usage energy vs unit-specific random threshold, then δ = 1 − exp(a·t^b) | a ~ U(0.001, 0.003), b ~ U(1.4, 1.6), rescaled to fighter cycles ([Arias Chao 2021](https://www.mdpi.com/2306-5729/6/1/5)) | TRANSFER |
| Cracks and spalls | Weibull initiation + Paris/exponential growth; debris ∝ spall growth | Bearing: incubation 1–40 h on rigs, 50–100 FH in the field; growth 0.08–0.34 mm/h; debris 2–50 mg per mm of spall ([NASA TM-2011-217117](https://ntrs.nasa.gov/api/citations/20110023753/downloads/20110023753.pdf)). Su-30 first symptoms: chips 48 %, vibration 16 %, low oil pressure 12 %; onset ≈500 FH, or ≈900 FH after modification ([The Wire](https://thewire.in/security/assam-su30mki-crash-challenge-adapting-fighter-demanding-conditions)) | TRANSFER + DIRECT (IAF fleet) |
| Shocks (FOD, birds) | Poisson with severity distribution, season and base dependence | Step Γ/η loss + imbalance; stall cycling every 3–5 s after bird damage | DIRECT (AIB) |
| Latent maintenance-induced defects | Per-action injection probability with a latency distribution | Latencies: one flight (MEC mis-assembly), 591 h (missing air seal), ≈6 years (wrong fairing) ([AIB 90-0755](https://www.afjag.af.mil/Portals/77/AIB-Reports/2019/AIB%20Final%20Report_F-16C.pdf)) | DIRECT cases; probability ASSUMPTION |
| Intermittents | Two-state Markov with environment-dependent rates | Removals NFF 30–60 % for avionics ([Khan et al.](https://pure.coventry.ac.uk/ws/files/3999358/J1_R.PDF)) | TRANSFER |
| Utility wear | Monitoring curves from patents and field data | Pump case-drain ΔT flat ≈5 months, then reaches its limit at ≈11.5 months; case-drain filter ΔP 6–12 → >14 psi in ≈4 weeks ([US 12,265,000](https://patents.google.com/patent/US12265000B2/en)); contamination wear ×4/×14; ECS HX fouling in 3–9 months at dirty sites; carbon brakes 1,400 landings (F-15); tyres 4–12 landings (F-16) | TRANSFER |
| Tejas-specific events | Discrete-event | JFS cold/altitude start failure; zoom-climb gauging artefact; brake-software configuration defect → tyre burst → excursion → fleet grounding; FCS channel dropout + reset | DIRECT |

**Build the engine fault library from released fighter traces.** Each fault has a channel ordering and code cascade [TRANSFER: F100/F110/F404 AIBs and NASA DEEC flight tests] ([CP-2298](https://ntrs.nasa.gov/citations/19860015871); [TM-86735](https://ntrs.nasa.gov/citations/19850021650)):

| Fault | Signature |
|---|---|
| Pop stall | PS3 85 → 10–15 psia within one sample, recovering over 0.2–3 s |
| Mechanical stall from blade loss | N falls while **T5 rises**; stall codes +2 s, overtemperature +4 s, sensor fail +10 s, flameout/sub-idle +13 s; generators drop |
| AB no-light | No light-off detected 2.5 s after request; up to 3 retries |
| AB rumble before blowout | 60 Hz pressure oscillation |
| Quickfill stall | About 1 per 994 segment-1 lights |
| Nozzle-loop limit cycle | 1–2 Hz, not detected as a fault |
| MFC over-fuelling | Take-off fuel ratio ≈102–105 % against a serviceable 88–100 % |
| Hung start | N2 flat near 35 % while EGT rises ≈12 °C/s |
| Shut-off valve partly closed | Sub-idle hang at ≈70 % for 3 min **with no caution** |
| Bleed leak | −2–3 % thrust per lb/s |

**Sensor faults:**
- **Trapped inlet static pressure.** Drifted undetected through 20,000 ft of climb.
- **Vented burner-pressure line.** Read as a false stall, causing fuel cut-off and sub-idle rollback.
- **Pressure failing high but in range.** Opened the nozzle and lost thrust before any flag.
- **T5 harness bias.** A 60 °C bias changed the identified fan-spool time constant from 0.77 s to 2.11 s ([Merrington, AGARD-CP-448](https://archive.org/details/DTIC_ADA203800)).

These are the cases where sensor faults and component faults interact, and they must be generated as such.

**Signal validation and BIT form an explicit layer between sensors and controllers.** The released evidence supports this template [TRANSFER] ([TM-101396](https://ntrs.nasa.gov/api/citations/19890004061/downloads/19890004061.pdf); [TP-2857](https://ntrs.nasa.gov/citations/19890014956); [RADC-TR-81-220](https://archive.org/details/DTIC_ADA108752)).

| Step | Logic | Evidence-based values |
|---|---|---|
| Range check | Fail outside physical range after n consecutive frames | FCS: 4 frames ≈ 60 ms; FADEC: [ASSUMPTION] 3–5 frames |
| Rate check | Fail if dx/dt exceeds a physical bound for 4 frames | J85/TF30/PW2037 practice |
| Cross-channel | Large disagreement → use the safer value and set a soft-fail flag (never average); agreement → average; one out → use the other; both out → hold and revert | Tolerance ≈2σ or 15 % FS plus a rate term; persistence 0.5 s (diagnostics) or 4 frames (FCS) |
| Analytical | Compare with a model or synthesis value; 25 % steady / 45 % transient tolerances; adaptive thresholds; heal after 10 good frames | Minimum detectable: N2 bias ≈350 rpm, FTIT ≈200 °R |
| Accommodation | Substitute (≤3 sensors on F404 FICA, 10 ms update); inhibit AB, nozzle trim and stall detection; force actuators safe; reduce N2 limit by ≈1,000 rpm; revert on a second like failure | Plant-changing, so recorded behaviour changes |
| BIT families | PBIT at power-up (Tejas prototype ≈10 min); CBIT every frame; IBIT/MBIT on the ground with WoW | DIRECT types (Tejas) |
| Exceedances and cautions | Limit + persistence (oil-pressure caution 30 s; IECMS "several iterations"); latch an event with 5 s pre + 25 s (USN) or 35 s (CF) post; PFL/MFL split | TRANSFER: IECMS |
| Failure modes of the validator itself (inject deliberately) | Tolerance too wide (late detection); scaling wrap-around (failed sensor accepted); persistence too long (fast fault lost); asynchronous skew plus noise (AFTI saw 15 false channel failures for 1 real); common-mode faults that defeat voting | DIRECT cases |

**BIT in fighters is noisy, incomplete and persistent, so model it that way.** Evidence on false alarms and coverage:
- The F-35 achieved **0.09–1.03 flight hours between false alarms** against a 50 h requirement ([DOT&E FY2014](https://www.dote.osd.mil/Portals/97/pub/reports/FY2014/dod/2014f35jsf.pdf)).
- F/A-18E/F BIT false-alarm rates were 33.5–86 %.
- NFF by LRU technology runs 29.5–63 %.
- Category II alarms persist for ≥3 flights in 10–18 % of cases.
- F110 EMS isolated about 70 % of real faults correctly at service entry.
- On the F101 the "potential" false-alarm rate fell from 25 to 2 per flight with maturity.
- The CAG found 94 serviceable LRUs that failed an IAF ATE pattern ([CAG 38/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf)).

Generate:
- an explicit missed-detection probability and false-alarm rate per caution;
- a CND/NFF propensity per code;
- sympathetic code cascades and code bursts after software updates.

Calibrate two regimes:
- **immature:** 0.1–1 FH between false alarms;
- **mature:** ≥50 FH, and ≤1 per 1,000 flights for gas-path EHM.

**Run BIT on the same coloured, heavy-tailed sensor model.** Independent-sample m-of-n mathematics understates false alarms when noise is coloured (RADC).

**Propagation follows documented cascades.** Typed edges carry transfer functions and latencies: seconds for electrical drop-out, minutes for fluid loss. Released accident reports supply the templates:
- **Engine → electrical:** fan-blade liberation → spool-down → generators offline → emergency power.
- **Engine → AB → electrical:** turned vanes → blade loss → stall codes → AB failure → control-mode switch → flameout → generators off.
- **Hydraulic:** actuator internal leak → dual hydraulic loss.
- **Utility → braking:** heat-exchanger crack → utility hydraulic loss → brake loss → runway excursion.
- **Contamination → control law:** contaminated servicing + cold soak → strut extension failure → false WoW → FCS ground law in flight.
- **Electrical → avionics:** partial electrical loss → navigation data invalid **without a flag** ([AIB index](https://www.afjag.af.mil/AIB-Reports/); [Eielson F-35A AIB](https://www.afjag.af.mil/LinkClick.aspx?fileticket=Zigjw6p7hiw%3d&portalid=77)).

An FMECA-style table, with a severity class and detection method per mode, is the configuration file behind the generator ([MIL-STD-1629A](https://everyspec.com/MIL-STD/MIL-STD-1600-1699/download.php?spec=MIL_STD_1629A.1556.pdf)). TEAMS-style dependency matrices then derive expected BIT signatures, with deliberate ambiguity groups and NFF.

**Imperfect maintenance works in both directions.**
- **Washing** restores a fraction ρ of fouling.
- **Module overhaul** resets a module to new initial wear, U(0, 1 %) plus a rub-in step, but leaves non-recoverable residue. JT9D shop visits recovered only ≈20 % of TSFC loss ([Sallee](https://ntrs.nasa.gov/api/citations/19800013837/downloads/19800013837.pdf)).
- **Inspections** have location-dependent detection probabilities; some stages are not borescope-accessible.
- **Every action** carries a small probability of injecting a latent defect.

Generate faults as **differences from a healthy per-tail baseline**. In sim-to-real studies, baseline-residual features transfer far better than raw signals: real-flight accuracy rose from 52.9 % (raw CNN) to 85.5 % with difference features ([DDCNN](https://arxiv.org/abs/2302.08117)).

---

## 10. Q10 — Calibrate on the proxy, then swap the platform

**The calibration loop separates calibration from validation and models discrepancy explicitly.** Calibrating without a discrepancy term "can yield biased parameter estimates and overconfident predictions" ([Brynjarsdóttir & O'Hagan](https://iopscience.iop.org/article/10.1088/0266-5611/30/11/114007)). The aircraft system-identification community's loop is proven ([Morelli & Grauer 2023](https://doi.org/10.2514/1.C037274)). The recommended Phalanx loop runs:
1. **Data compatibility on the real (proxy) data.** Estimate per-channel bias, scale factor and time skew, so sensor errors are not "calibrated into" the simulator.
2. **Split by flight.** Separate calibration, validation and untouched test sets, and hold whole regimes out to test extrapolation.
3. **Identify parameters per subsystem.** Use equation-error or output-error for flight dynamics. For the engine, tune map scalars and health parameters with observability-aware tuner selection ([Simon & Garg](https://ntrs.nasa.gov/citations/20100006914)).
4. **History matching first.** An implausibility cutoff of 3 rules out impossible regions. If no plausible region remains, the model structure, not the parameters, is wrong ([Andrianakis et al.](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003968)).
5. **Bayesian or L2 calibration** with informative, physically bounded discrepancy priors.
6. **Residual analysis by regime.** Check bias, spectrum, colour, heteroscedasticity and cross-channel correlation, using the V&V 20 test |E| ≤ U_val.
7. **Correct, in order of preference:** a structural physics fix; then a parameterised physics term; then a constrained ML residual (minimum-norm, bounded, gated to seen regimes, with an out-of-distribution fallback).
8. **Validate** on held-out flights and regimes.
9. **Version** data hashes, priors, posteriors, code and the decision.

**Validate what transfers, and label each property P (platform-independent) or D (platform-dependent).**

| Property class | Label | Validate against | Credibility |
|---|---|---|---|
| Sensor lag laws, noise-spectrum shape, quantisation, bus encoding, sampling jitter, dropout patterns | P | Any proxy with the same sensor or bus class (DASHlink, NGAFID, PX4, test-cell, NASA flight data) | Up to Level 2 |
| Kinematic consistency, energy and mass balance, monotonic engine relationships | P | Physics invariants | Strong |
| Corrected and dimensionless relationships (corrected speed–flow lines, transient time ratios, modal damping ratios) | P/D (scaled) | Proxy + published fighter reports | Level 2, with scaling flagged |
| Absolute levels (thrust, EGT limits, fuel flow, g envelope, regime durations) | D | Fighter-specific released sources, digitised plots, SME review | Level 1–2 |
| Degradation and fault signatures | D | Engine-family literature, fleet statistics, SME | Level 1–2 |

**"Simulate the proxy, then swap the platform."** First configure the shared modules to emulate a proxy and pass the full statistical battery against real proxy data:
- recorder and sensor-texture modules emulate DASHlink;
- degradation modules emulate the C-MAPSS-class engine.

Then change **only** the platform-dependent modules to the Tejas/IN20 configuration. Credibility rests on the shared modules having been validated and on the swapped modules being sourced from documents. This mirrors the flight-simulator rule that engine-independent tests may use data from any engine, while engine-dependent tests need engine-specific data ([14 CFR Part 60 App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60)).

**Calibration targets exist for the engine, the airframe and fleet behaviour.**
- **Engine.** An ordered list of 28 targets (C1–C28). It starts with exact reproduction of the DIRECT IN20 ratings. It continues through F404-400 corrected airflow vs N1c (scaled ×1.05), MIL nozzle tables vs altitude, part-power ground points, altitude thrust ratios, AB thrust ratio vs fuel–air ratio, slam step responses (TM-4240), take-off transient indices, AB light-off times, T-50 ground start and airstart tables, the RM12 flameout rundown trace, surge recovery, vibration levels, oil-debris wear rates, and **correct sign of every fault in the Muir matrix** [TRANSFER] ([F404 engine note sources](https://ntrs.nasa.gov/citations/19970027377)).
- **Airframe.** Tests V1–V12 [ASSUMPTION pass criteria]:
  - CL(α) at M≈0.2 within ±0.03 of the digitised Tejas wind-tunnel curve;
  - trim α at 8 km within ±1° of 12.45/6.59/2.46°;
  - low-speed short-period eigenvalues ≈ +0.26 s⁻¹ (±0.1) and −1.16 s⁻¹ (±0.3);
  - time-to-double ≈0.2–0.3 s in M0.5–0.8 at 3–8 km;
  - flight-estimated Cm derivatives;
  - Cnβ zero crossing at 23–26°;
  - ARI gain sign trend vs Mach;
  - closed-loop margins ≥6 dB / ≥35° (target 9–17 dB / 58–68°) with 8 ms delay and 9 Hz actuators;
  - performance (level M1.6 at ~11–12 km, ≥620 kt at sea level);
  - ground speeds;
  - pilot-input spectra mostly below 0.25 Hz ([tejas_airframe sources](https://joast.org/index.php/joast/article/view/741)).
- **Fleet behaviour.** The usage gates of Section 4 and the availability priors of Section 12.

**Tolerances must never be tighter than real repeatability.** The rule is tolerance = max(measurement-uncertainty floor, real-vs-real variability, intended-use requirement). Calibration and validation data are disjoint, and there is no tuning at the test points. Available numbers:

| Domain | Threshold or floor | Source |
|---|---|---|
| Engine model vs transferred targets | ±3 % steady state; ±25 % on transient timing (the F404 simple model's own accuracy) [ASSUMPTION] | [TM-4240](https://ntrs.nasa.gov/citations/19910009766) |
| Engine measurement floor | Test cell (AGARD UETP, J57): airflow ±0.7 %, thrust ±0.9 %, SFC ±1.4–1.5 %, rotor speed ±0.24 % at 82.7 kPa; ≈±2.5–3.5 % at altitude-cell conditions. F404 in-flight vs test cell: Wf ±2 %, N1/N2 ±0.5 %. Tuned F404 test-cell model ≈1 % on T45 across 21 engines | [TM-88943](https://ntrs.nasa.gov/api/citations/19870019124/downloads/19870019124.pdf); [ADA219105](https://apps.dtic.mil/sti/citations/ADA219105); [ADA408947](https://apps.dtic.mil/sti/citations/ADA408947) |
| Frequency-domain fit | CIFER cost J_ave ≤ 100 acceptable; individual J ≤ ≈200 | [arXiv 2506.23302](https://arxiv.org/pdf/2506.23302) citing Tischler & Remple |
| Time-domain fit | Theil inequality coefficient ≤ 0.25; RMS fit ≤ 1–2 (rotorcraft guideline) | [Licitra et al.](https://arxiv.org/pdf/1711.10010) |
| Simulator objective tests | Short period ±1.5° pitch or ±2°/s and ±0.1 g; Dutch roll ±0.5 s or ±10 % period; engine acceleration ±10 % time; engineering-simulator reference data within 40 % (FAA) or 20 % (EASA) of these | [14 CFR Part 60](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60) |
| Snapshot scatter | Measurement ≈0.1–0.5 %; real engine-to-engine spread ≈±1 %; VG-rig thrust scatter ≈±5 % at fixed N2 (F404-400); F404 acceptance window ±1 % | [AGARD-CP-448](https://archive.org/details/DTIC_ADA203800) |

Stage 1 had marked the CIFER and TIC thresholds as unverified. **Stage 2 sourced them**, but only through recent papers that cite Tischler & Remple and Jategaonkar; the primary books were not read.

**Report credibility honestly, per factor and per regime.**
- No military numeric simulator-tolerance standard exists. The UK MAA qualifies military training devices against civil CS-FSTD / ICAO 9625 "with tolerances adjusted to suit military usage" and re-tests against the master QTG over a rolling 12 months ([RA 2375](https://assets.publishing.service.gov.uk/media/661cf46208c3be25cfbd3d7a/RA2375_Issue_5.pdf)).
- Combine that practice with the NATO/SISO GM-VV acceptance argument (claims → evidence → conditional acceptance) ([NLR-TP-2013-598](https://reports.nlr.nl/items/d3e9b03e-34ce-42d5-9ac9-f6b3beb8ba29/full)).
- Publish a "credibility card" per release, giving NASA-STD-7009B factor levels per channel and regime, with the domain of validation stated.

---

## 11. Q11 — A discriminator is a test, not a definition of realism

**A real-vs-synthetic classifier is a valid two-sample test with a simple null and known failure modes.**
- **Null distribution.** Under the null, held-out accuracy is ~N(½, 1/(4·n_te)) ([Lopez-Paz & Oquab](https://arxiv.org/abs/1610.06545)).
- **Critical accuracies** at one-sided α = 0.05 by number of *independent* test units [ASSUMPTION, computed]:
  - n_te = 100 → 0.582;
  - n_te = 200 → 0.558;
  - n_te = 500 → 0.537;
  - n_te = 1,000 → 0.526;
  - n_te = 5,000 → 0.512.
- **Power.** To detect a true accuracy of 0.55, power is ≈0.41 at n_te = 200 and ≈0.94 at 1,000.
- **Independence.** Overlapping windows from one sortie are not independent. Count flights, or permute labels at flight level.

**The test can be fooled in both directions.**
- **Wrongly passed:** a weak or poorly trained classifier, or a narrow feature view.
- **Wrongly failed, through trivial cues.** In audio deepfake detection, leading-silence duration alone gave ≈85 % accuracy ([Müller et al.](https://arxiv.org/abs/2106.12914)). Phalanx analogues are record padding, start-up segments, timestamp regularity, quantisation and sample rate.
- **Wrongly failed, through leakage.** Windows from one flight in both train and test inflate scores.
- **Wrongly failed, through domain shift.** Comparing simulated Tejas against real airliner data detects the platform, not the simulator.

**The Phalanx protocol** [ASSUMPTION, assembled from the cited practice]:
1. **Trivial-cue audit first.** Train on metadata-only features (record length, interval jitter, LSB histogram, dropout runs, start/end segments, headers). If this beats chance, fix the pipeline before any realism claim.
2. **Canonicalise both classes** through the identical ingest path. Pass synthetic data through the same Ch10 → decoder chain as real data.
3. **Match conditions.** Compare Phalanx-simulating-proxy-X against real proxy X, in the same regimes and ambient bins.
4. **Use a classifier ladder:** per-channel marginal tests → catch22/tsfresh features with regularised logistic regression or gradient boosting → ROCKET or a small CNN/GRU on raw multichannel windows. Run each at 2 s, 30 s and whole-segment windows.
5. **Use GroupKFold by flight and aircraft**, with a group-level permutation test. Target ≥1,000 independent windows from ≥50 flights per class.
6. **Ablate by feature family:** spectral, noise statistics, quantisation, timing, cross-channel lag, transient shape, regime transitions. Use clustered permutation importance; time-series saliency maps are unreliable ([Ismail et al.](https://arxiv.org/abs/2010.13924)).
7. **Map each significant family to a simulator-module ticket.** Re-test with fresh seeds *and* a re-trained classifier, and keep one classifier family held out from development, so the simulator is not overfitted to a fixed discriminator.
8. **Report against a real-vs-real baseline** (tail A vs tail B, or two seasons). The goal is **"sim-vs-real distinguishability ≤ real-vs-real distinguishability"**, not 0.5.
9. **Report per regime:** TPR, TNR and balanced accuracy. In the only aerospace example found, an LSTM reached 0.608 overall accuracy while its **TNR was 0.269**, so most *real* samples were called synthetic; per-cluster accuracy was 0.65–0.87 ([SIDs 2024](https://sesarju.eu/sites/default/files/documents/sid/2024/papers/SIDs_2024_paper_054%20final.pdf)).

**Published sim-vs-real studies show what discriminators exploit.** In rank order ([RflyMAD](https://arxiv.org/abs/2311.11340); [Caldararu et al.](https://arxiv.org/abs/2403.11000); [VIPR](https://ntrs.nasa.gov/citations/20150000899)):
1. Noise floor and high-frequency content. Real accelerometer variance was ≈11× that of SITL.
2. Noise colour. White Gaussian was the worst model and random walk the best.
3. Per-unit offsets.
4. Transient mismatch while steady state agrees.
5. Heavy tails.
6. Multi-rate, irregular timing.
7. Flat-lined environment channels.
8. Fault-class-dependent gaps.
9. Initialisation artefacts.

Together with the DASHlink mechanisms, this list is the realism checklist. Sim-to-real fixes that worked:
- coloured noise with calibrated covariance;
- re-trimming to real steady-state data;
- healthy-baseline residual features;
- a small real fraction. Training on SIL only gave 63 % fault-classification accuracy on real flights; adding 10 % real data gave 96–98 %.

**Test the test before trusting it.** Use RflyMAD (SIL/HIL/real), PX4 SITL vs real logs, and C-MAPSS vs DASHlink as a known-separable sanity control.

**Keep the discriminator one mechanism among several.** Three reasons:
- failing to detect a difference is weak evidence;
- detection is dominated by whatever cue is easiest, which may be irrelevant to predictive maintenance;
- it says nothing about rare regimes such as faults and extremes ([Cranmer et al.](https://arxiv.org/abs/1911.01429)).

It sits beside:
- physics and kinematic invariants;
- objective tests;
- regime-wise statistical batteries compared with real-vs-real distances (KS/AD, Wasserstein, MMD, ACF/PSD, tail and missingness, with block-bootstrap CIs);
- downstream-utility tests (TSTR/TRTS, and whether PdM-model rankings on Phalanx data predict rankings on real proxy data);
- α-precision/β-recall/authenticity checks against copying;
- structured SME and Turing reviews by pilots and maintainers, scored with a binomial test, with face-validity questions kept separate from "which is real?" questions.

**What accuracy is "good enough" remains open.** Set it by sensitivity studies — does PdM performance change when the detected artefacts are removed? — not by convention.

---

## 12. Q12 — Five keys and deliberate defects link telemetry to the logbook

**Military maintenance records share one architecture, and the IAF's is public only in outline.** USAF, USN and UK MOD systems all use:
- a per-aircraft status log;
- per-defect work documents with a unique job number;
- five coded dimensions: system/WUC, when-discovered, how-malfunctioned, action-taken, type-maintenance;
- free text;
- two-person certification;
- separate serialised component life records ([NAMP 4790.2E](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf); [TO 00-20-2](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/); [UK MAM-D](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf)).

The IAF's public facts are:
- 1st/2nd-line (squadron/base) and 3rd/4th-line (BRD/HAL/OEM) maintenance;
- hard-time and calendar life with engineering extensions;
- AOG demands;
- e-MMS and IMMOLS ([IAF RTI Handbook](https://indianairforce.nic.in/Resources/pdf/utilities/RTI-Handbook-updated-as-on-19-Apr-23.pdf); [CAG 24/2017](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf)).

IAF form layouts and code tables are not public. Phalanx therefore uses USN/USAF structure, the UK Form 700 heritage (closest to the IAF) and the ASD S5000F exchange model, with **IAF-style relabelled synthetic codes**.

| Record type | Trigger | Key content | Template |
|---|---|---|---|
| Sortie / flight record | Each flight | Tail, sortie ID, crew, mission, hours, landings, cycles, starts | NAVFLIR; AFTO 781H |
| Aircraft status / technical log | Continuous | Serviceability state, deferred defects, limitations | UK F700; AFTO 781K |
| Defect work order ("snag") | Pilot write-up, HMS/BIT code, inspection | Job no., discovered-by, system code, malfunction, action, text, times, signatures | NAMP work order; AFTO 781A |
| Component life records | Install/remove | P/N, S/N, maker, time/cycles at removal and installation | AESR/log cards; F-35 EEL; IAF engine log book |
| Inspection / servicing | Interval or exceedance | Look/fix phases, findings | NAMP Control/Look/Fix; IAF 2nd-line servicing |
| Supply / AOG demand | Part needed | Demand number, priority, dates | NAMP requisition; CAG AOG |
| Cannibalisation | Part robbed | Two linked jobs; donor and recipient S/N | AF Form 2414; NAMP CANN |
| Modification / TCTO | Order issued | Order ID, status, grounding date | TCTO/TD; IAF STI/SI/mods |
| Exceedance / conditional inspection | Overtemperature, overspeed, over-g, hard landing | Down until inspected; historical-record entry | NAMP §9.2.3.3 |
| Shop / depot finding | Turn-in | Confirmed / RTOK / BCM; NRTS reasons | NAMP; USAF NRTS |
| Availability state log | Status changes | 15-min-binned mission-capability states | NAMP SCIR |
| Standards exchange | All of the above | Event, MaintenanceEvent, DetectionMechanism (with false-alarm rate), NFF report | [S5000F](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf) |

**Five keys carry the linkage.**
1. Aircraft tail.
2. Sortie ID (date + take-off time).
3. Job number (an IAF-style "snag number").
4. The component triplet (P/N, S/N, maker), with time/cycles at removal and installation.
5. Demand/document number.

Phalanx adds:
- engine and module serials;
- a software-configuration ID (essential for the Tejas, given the 2026 brake-software event);
- the telemetry `record_id` hash, so any work order can point to the exact samples and events that triggered it.

**Telemetry enters the record system through codified, public precedents.**
- USN health-monitoring data are formally inside the maintenance-records system. Maintenance Control reviews HMS BIT and condition indicators after each flight and raises work orders with when-discovered code "I" (HMS-identified). QA trends each aircraft over 50 flights ([NAMP §10.37](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf)).
- The F-35 defers a health code and monitors it for three consecutive flights before an administrative close ([4790.35D](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/4790.35D.pdf)).

These give the event-to-record transitions.

**Event chains follow documented sequences and timings.** Durations are anchored to official examples; others are [ASSUMPTION].

| Chain | Sequence | Timing anchors |
|---|---|---|
| 1. Engine lube anomaly, no abort | Oil-pressure fluctuation in AB → CBIT code + caution → landing → pilot write-up → download, HMS codes attached → troubleshooting → oil-pressure transmitter found faulty → part demand (or cannibalisation) → R/R + ground run → inspector sign-off → release; removed unit to shop (confirmed or RTOK) | Same-day repair ≈3 h elapsed (official IGB chip example); with awaiting-parts, days to three weeks; depot turnaround months (F-35 average 72 days) |
| 2. BIT false alarm | Code set, no pilot complaint → WO → ground BIT passes → CND, or defer and monitor 3 flights → admin close; recurrence → R/R → bench RTOK → rogue-unit tracking → nuisance filter list | Per NAMP/TO 00-20-2 codes |
| 3. Exceedance | EGT or g limit exceeded → download → conditional-inspection WO (aircraft down) → borescope or inspection → close, or engine removal + logbook update | — |
| 4. Scheduled servicing | Interval reached → control/look/fix jobs → discrepancies found in phase → release | IAF IL-76 second-line servicings finished on time in only 30–37 % of cases ([CAG 24/2017](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf)) |
| 5. Modification / life-limited part | Order issued → compliance WO; part approaching limit → opportunistic or hi-time removal → new S/N → record update; variant: engine returns from OEM overhaul with an unfilled log book | CAG IAF case |
| 6. Tejas JFS cold start [DIRECT basis] | Cold soak at a high base → JFS start failure(s) → start-record event → aircraft unavailable → JFS/battery troubleshooting → retry or replace → three-consecutive-start check | Leh M1 failures; −15 °C demonstration |
| 7. Tejas brake-software configuration [DIRECT basis] | Software load X → brake failure on landing → tyre burst → runway excursion → fleet-wide grounding → joint IAF–HAL–CEMILAC clearance of corrected software → staged return | ≈2 months (Feb–Apr 2026) |
| 8. Tejas fuel-gauging artefact [DIRECT basis] | High-pitch, max-AB, low-fuel manoeuvre → false low-fuel caution → write-up → CND → modification as fix | ADA AR 2018-19 |

**Fleet availability should be computed, not asserted, and calibrated on audited IAF data.**
- Compute mission-capability states deterministically from job states, SCIR-style in 15-minute bins.
- Priors for state occupancy come from the Su-30MKI: ≈20 % in first- and second-line maintenance, 11–12 % in HAL repair and overhaul, and 13–14 % AOG awaiting major systems ([Business Standard 2014](https://www.business-standard.com/article/economy-policy/govt-takes-note-of-su-30mki-s-poor-serviceability-114102300006_1.html)).
- Overall serviceability was 55–60 % against a 75 % norm ([CAG 38/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf)).
- AOG supply delays (IL-76, 2010–15): **10.83 % of demands met within 15 days and 22.49 % after more than 6 months** ([CAG 24/2017](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf)).
- These come from ageing Russian-origin fleets and are pessimistic for an OEM-supported F404 fleet. Treat them as priors, with a "Tejas supply-chain events" layer on top (engine deliveries, LRU repair capacity, software clearance).

**Inject data-quality defects deliberately, with documented magnitudes.**

| Defect | Magnitude or example | Source |
|---|---|---|
| Cannibalisation under-reporting | Up to 50 %; USN 8.8–9.6 CANNs per 100 FH; USAF 10.6–12.7 per 100 sorties | [GAO-02-86](https://www.gao.gov/assets/gao-02-86.pdf) |
| Missing electronic part records | 213 of 263 delivered spares (81 %) at one F-35 site; 0–400 record issues per week | [GAO-20-316](https://www.gao.gov/assets/gao-20-316.pdf) |
| Manual parallel tracking | 5,000–10,000 h per year | same |
| Aircraft under-reported | A squadron reported 12 of 14 aircraft held | [CAG 24/2017](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf) |
| Unfilled engine log books after OEM overhaul | IAF IL-76 case | same |
| Wrong form or field | Weight recorded on the wrong UK form; smoke pod fitted/removed ≥4 times unrecorded | [UK SI Hawk XX204](https://assets.publishing.service.gov.uk/media/5d9c9f73e5274a596f829ba9/20191007-HAWK_T_Mk1a_XX204_SI_Redacted-Final.pdf) |
| Record-reconciliation delay | Average 14 days at NAS Lemoore I-level | [Hagan & Slack](https://archive.org/details/DTIC_ADA462668) |
| Free-text noise | 97 of 106 non-standard tokens in civil logbook samples | [MaintNet](https://arxiv.org/abs/2005.12443) |
| Missing S/N, duplicate snags, delayed close-out, download duplicates | Default "XXX" S/N; retries re-deliver files | NAMP; data-pathway practice |
| Recorded health data that never reached the cockpit | F-35B ZM152 | [UK SI ZM152](https://assets.publishing.service.gov.uk/media/651d73e4e4e658001459d95d/Service_Inquiry_into_the_loss_of_F-35B_Lightning_ZM152__BK-18_.pdf) |

Every defect is applied **after** ground truth is recorded, and is logged in a defect manifest. Evaluators can then measure how well the AI recovers through, or detects, bad records.

---

## 13. Q13 — One canonical sample with six timestamps and explicit validity

**Time has six meanings, and public standards pin each one down.** IRIG 106 Ch10 defines exactly which bit or sample a timestamp refers to:
- for 1553 data, a selectable bit of the message;
- for ARINC 429, the first word plus gap times;
- for analog data, the first sample;
- for time packets, the mapping of a free-running 10 MHz counter to IRIG/GPS/UTC, which reverts to internal time on loss of lock ([IRIG 106 Ch10](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2); [RCC 123-16](https://www.irig106.org/docs/rcc/123-16_IRIG_106_Chapter10_Programmers_Handbook.pdf)).

The canonical sample therefore carries six times, with realistic offsets [ASSUMPTION grounded in the standard]:

| Time field | Meaning | Realistic offset model |
|---|---|---|
| `t_true` | Physics time of the true value | — |
| `t_sample` | When the owning LRU acquired it | LRU tick on its own drifting oscillator |
| `t_bus` | When it appeared on the bus (at the Ch10-defined bit) | LRU compute latency + wait for the bus controller's next poll (0 to one producer period) |
| `t_record` | Recorder counter ticks | `t_bus` + monitor latency; packets close within ≤100 ms |
| `t_utc` | Absolute time via a simulated GPS/IRIG source | Includes lock-loss periods (flagged) |
| `t_ingest` | Arrival at the ground | Hours later, as a per-sortie burst after download |

**The canonical sample record** (the decoded contract published by the ground decoder; the internal CIR adds the truth value):

| Field | Content |
|---|---|
| `record_id` | Deterministic hash of (tail, sortie, channel ID, packet sequence/counter, message index) for idempotency |
| `param_id`, `dict_version`, `dict_hash` | Parameter-dictionary key and version |
| `tail_no`, `sortie_id`, `engine_serial` (where relevant) | Linkage keys |
| `source_lru`, `lane` / `channel`, `bus`, `rt_sa_word` or `label_sdi` | Provenance on the acquisition and bus path |
| `t_true` *(CIR only)*, `t_sample`, `t_bus`, `t_record`, `t_utc`, `t_ingest` | Six times, stored as int64 ticks (Avro 1.11.1 has no nanosecond logical type) |
| `value_eu`, `raw_counts`, `units` | Decoded engineering value and raw word |
| `validity` | Enumerated: NORMAL, NO_COMPUTED_DATA, FUNCTIONAL_TEST, FAILURE_WARNING (ARINC 429 SSM semantics), plus BUS_INVALID (1553 status/validity words) |
| `quality_flags` | Bit set: SENTINEL, GATED, HELD_STALE, DUPLICATE_POLL, SUBSTITUTED (FADEC/validator synthesised), VOTED_OUT, OUT_OF_RANGE, CLOCK_SUSPECT, TIME_SOURCE_INTERNAL, DUPLICATE_DOWNLOAD, DECODER_INTERPOLATED (ground-side only) |
| `provenance` | `full_path` (via bus and Ch10) or `direct` (fast path) |
| `rng_key_path` *(manifest-linked)* | (scenario, tail, sortie, subsystem, sensor, noise component) for exact regeneration |
| `truth_value` *(CIR and label topic only)* | Never exported to the PdM contract; kept for labels and validation |

**Events get their own record.** Each event carries:
- the S5000F Event fields (identifier, occurrence time, group, severity, description, confirmed status);
- a DetectionMechanism (PBIT, CBIT, MBIT, IBIT, exceedance or pilot) with its false-alarm rate;
- an IRIG Ch10 recording-event number;
- a PFL/MFL level, latch state, persistence count, suspect-LRU list with isolation confidence, and a pointer to its snapshot window (e.g. 5 s pre + 25–35 s post).

**Emit every event twice:**
- inside the per-sortie Ch10 file, as recording events with the underlying discretes and BIT words;
- as a decoded event on the ground stream.

The downstream system thus faces realistic duplication and late arrival ([S5000F](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf); [TMATS](https://www.trmc.osd.mil/wiki/download/attachments/113019518/chapter9.pdf?api=v2)).

**Rate groups sit in asynchronous clock domains, and realism comes from their boundaries.**

| Group | Rate | Domain | Contents | Tag |
|---|---|---|---|---|
| FCS80 / 40 / 20 / 10 | 80 Hz base, binary sub-rates | DFCC | Rate sensors, accelerometers, commands, surfaces, voting, CBIT | DIRECT 80 Hz; TRANSFER sub-rates (F/A-18 FCC) |
| FADEC-INT | 50–67 Hz | FADEC | Engine sensors, loops, limiters, flameout logic | TRANSFER (NASA templates) |
| AV50 / AV25 / AV12.5 / AV6.25 | 1553 minor 50 Hz, major 12.5 Hz | Avionics bus controller | INS (50), air data and engine performance (25), health/status and fuel (12.5), slow temperatures and electrical (6.25) | DIRECT-unnamed (ADE 12.5 Hz health message ([JOAST 598](https://joast.org/index.php/joast/article/view/598))) + ASSUMPTION |
| SLOW1 / EVT | 1 Hz / on change | Bus and recorders | Time, LSS, battery, vibration features; discretes, cautions, BIT | TRANSFER |
| ECMS10 / ECMS1 | 10 Hz / 1 Hz + windows | ECMS | Gas path at 10 Hz; oil, vibration, Nz, valves at 1 Hz; LUIs twice per flight | TRANSFER: IECMS |
| CDR16 / 8 / 4 / 1 | 16/8/4/1 Hz | Crash recorder | Controls, surfaces, Nz / attitudes / air data and engine / utility | ASSUMPTION (DASHlink 0.25–16 Hz; 14 CFR App. M minima) |
| HUMS / HF / FTI | 1–10 Hz + bursts / kHz raw → 1 Hz features / 64–800 Hz | DAU / vibration front end / FTI | Utility analogs; vibration; test-only parameters | DIRECT (DAU exists) + TRANSFER |
| SORTIE / INSP | Per sortie / per inspection | Ground | Counters, configuration, inspection measurements | DIRECT/TRANSFER |

Each LRU and acquisition unit runs on its own oscillator with a **frequency offset Δ** (a per-unit parameter), and the bus controller polls asynchronously. On DASHlink the measured proxy for recorder-vs-source Δ is ≈910 ppm. That is much larger than a crystal's tolerance of tens of ppm, which points to a nominal-rate mismatch rather than oscillator error [MEASURED; interpretation ASSUMPTION]. The decoder must then handle:
- duplicated samples (a 40 Hz producer polled at 50 Hz);
- skipped samples (80 → 25 Hz);
- fixed skews;
- clock drift;
- **slip windows**: every 1/(f·Δ) seconds a consumer's read phase crosses the producer's update instant. Reads inside the collision window (≈10–20 ms on DASHlink) return a sentinel (analog paths) or possibly a stale or duplicate value (digital paths; under test).

These are the same artefact classes measured on DASHlink. Its periodic dropout bursts are exactly these slip windows (Section 8 correction), so a single clock-domain model generates both the timing texture and the structured missingness. All rates and divisors live in the dictionary and the sortie manifest, so a real Tejas schedule would change data, not code.

**Topics, storage and manifests follow standard ingestion practice.**
- **Raw landing zone.** Immutable `.c10` files named by deterministic keys.
- **Topics** (Avro or Protobuf in a schema registry), partitioned by `tail_no` to keep per-aircraft order:
  - `param.samples`;
  - `events.bit_faults`;
  - `events.exceedances`;
  - `usage.counters`;
  - `sortie.manifest`;
  - `maint.records`;
  - `orders.commands` (inbound decisions from the AI or human planners) and `orders.status` (accepted, queued, in work, completed, rejected, with reasons). See Section 14, "Closing the loop";
  - a restricted `labels.truth` topic.
- **World snapshots.** Content-hashed snapshot files in object storage, each referenced by a manifest record (snapshot ID, sim time, parent, order-log hash). These are needed for forking.
- **Delivery semantics.** Producer idempotence plus the deterministic `record_id`, so re-downloads produce no duplicates downstream. Event-time windows with **per-sortie watermarks**: a global wall-clock watermark is wrong when sorties arrive hours late as bursts ([Kafka design](https://github.com/apache/kafka/blob/trunk/docs/design/design.md); [Flink time](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/)).
- **Analytics.** Parquet partitioned by date, tail and sortie.

The **Parameter Dictionary** is the single source of truth and generates TMATS. Per parameter it holds:
- ID, name and units;
- source LRU and channel;
- sensor type, ADC bits and range;
- bus mapping;
- encoding and LSB;
- validity mapping;
- rate groups;
- calibration polynomial and date;
- sensor serial;
- limits;
- evidence tag and source;
- version and hash.

The **sortie manifest** records:
- tail and engine/LRU serials;
- software load and configuration;
- mission type;
- dictionary version;
- seeds and stream table;
- code commit and library versions.

---

## 14. Q14 — Twenty-two replaceable modules, a closed decision loop and forkable worlds

**Every module declares typed ports in SI units, parameters with provenance, a state vector and get/set-state.** This is the FMI contract, without forcing FMI on the core loop ([FMI 3.0](https://fmi-standard.org/docs/3.0/)). Modules can therefore be tested, replaced and calibrated independently.

| ID | Module | Inputs → outputs | Key assumptions | Unit / verification tests | Validation criterion |
|---|---|---|---|---|---|
| M01 | Parameter dictionary and provenance registry | Sources → versioned, hashed parameter sets; TMATS export | Synthetic ICD labelled as such | Schema, units and hash round-trip; every row has a tag and source | 100 % rows tagged; TMATS parses in pyChapter10 |
| M02 | Scenario, fleet calendar and mission generator | Flying task, bases, climate, **flying-programme orders (M21)** → sortie plans and tail assignments | Mission mix [ASSUMPTION] | Seeded determinism; distribution unit tests; order-driven reassignment tests | Usage gates of Section 4 |
| M03 | Environment | Base, date → atmosphere, wind, turbulence, humidity | ERA5 smoothing | USSA tables to 1e-6; MIL-HDBK-310 reproduction; turbulence PSD vs analytic | ERA5-vs-IGRA residuals |
| M04 | Pilot and guidance | Plan, state → stick, pedal, PLA | Crossover overlay parameters | Tracking-spectrum checks | Tejas pilot spectra mostly < 0.25 Hz (V11) |
| M05 | FCS (DFCC replica) and actuators | Commands, sensors → surface commands, positions, BIT | Gains and thresholds | Step responses; rate/position limits; 8 ms delay | Margins and limiters (V8) |
| M06 | Airframe 6-DOF and aero database | Forces, mass → state | Donor derivatives | NESC check cases; step-halving | V1–V7, V9, V10 |
| M07 | Engine truth model (CLM + dynamic shell) | PLA, ambient, health scalars → stations, thrust, Wf | Maps, inertias, T4 | Energy balance ≈0; corrected-parameter invariance under ISA offset | C1–C28 within ±3 % / ±25 %; Muir signs |
| M08 | FADEC and engine signal validation | Sensors → actuator commands, substitutions, fault codes | Thresholds [TRANSFER] | Limiter tests; injected-sensor-fault responses | Released fault cascades reproduced qualitatively |
| M09 | Utility systems | N2, bleed, Wf, FCS demand, WoW, landing energy → pressures, temperatures, quantities, voltages, discretes | Pump flow, generator rating | Mass and energy balance; 704F bands | Coupling-map signs; ADA test points (JFS, RTO wear, zoom-climb artefact) |
| M10 | Health state, usage damage and degradation | Usage drivers → hidden states per serial | Severity factor S; rates | Zero rate → flat trend; monotone gamma | N-CMAPSS-style onset statistics; life-counter accrual |
| M11 | Fault injection and propagation graph | Fault schedule, FMECA → state perturbations, cascades | Edge latencies | Graph acyclicity per step; edge transfer tests | AIB cascade orderings and latencies |
| M12 | Sensor physics | Truth → sensor outputs | Unit tolerances | τ laws vs NACA/AGARD; vane second-order response | Air-data, fuel and oil class behaviours (Section 8) |
| M13 | Acquisition and residual texture | Sensor outputs, clock-domain phases (M15) → quantised, noisy, gapped samples (CIR) | Fighter LSBs; per-unit Δ, collision window w | Quantiser LSB/saturation; slip period = 1/(f·Δ) and phase relations across rates | σ/LSB, ACF, PSD, tails, missingness vs [MEASURED] priors and proxy data; settling-experiment verdict |
| M14 | Monitoring and BIT (CBIT/PBIT/IBIT, CWS, ECMS/HUMS, LUIs, exceedances) | CIR → cautions, codes, snapshots, counters | Coverage and false-alarm rates | Persistence/latch logic; LUI counting on synthetic cycles | Calibrated false-alarm regimes; event-rate Poisson tests |
| M15 | Bus encoder and clock domains | CIR → 1553/429 messages | Synthetic ICD and schedules | Encode/decode round-trip; ≤50 % bus loading | Duplicate/skip/skew statistics |
| M16 | Recorder writer and download simulator | Messages, events → Ch10 files, download batches | Ch10 as surrogate | Conformance vs public sample `.c10`; `c10 stat` | Independent parsers agree |
| M17 | Ground decoder → canonical contract | Ch10 → `param.samples`, events, Parquet | Dictionary versions | CIR → Ch10 → decode within quantisation | Identical schema on fast and full paths |
| M18 | Maintenance, logistics and records simulator | Events, states, supply, **validated orders (M21)** → work orders, records, availability, order outcomes | Delay distributions; IAF code tables; action-outcome models (wash recovery ρ, inspection detection, misdiagnosis, induced defects) | Key integrity; SCIR arithmetic; resource/authority rule tests | Su-30/CAG priors; defect-rate targets; status-quo policy reproduces open-loop KPIs |
| M19 | Streaming and storage | Contract → Kafka, Parquet, manifests | Transport choice | Idempotency under replay; watermarks | Replays bit-identical to live |
| M20 | Validation and calibration harness | Everything → credibility card | Tolerances | SBC on calibration code; leakage checks | Layers 0–8 (Sections 10–11) |
| M21 | Orders and decision interface | `orders.commands` + the decision-maker's observation set at the epoch → validated, scheduled orders to M18/M02; `orders.status` | Decision-epoch calendar; authority, airworthiness and resource rules | Schema validation; no-look-ahead; idempotent order IDs; replay determinism | Reference policies reproduce open-loop behaviour; executed orders appear as normal records |
| M22 | World-state snapshot and fork service | All module states, RNG counters, queues, inventories, order log → content-hashed snapshots; branches with divergent order suffixes | Snapshot granularity (sortie boundaries by default) | Snapshot → restore → continue is bitwise identical; identical suffixes give identical branches; CRN audit | Paired (CRN) KPI differences have lower variance than independent-seed comparisons |

**Reproducibility rests on seeded per-module streams, manifests and versioned assumptions.**
- **RNG streams.** One 128-bit root seed per dataset release. Streams are spawned by a fixed key path (scenario, tail, sortie, subsystem, sensor, noise component), using NumPy `SeedSequence` spawn keys or counter-based Philox keys — **never seed arithmetic**. NumPy explicitly warns against `root_seed + worker_id` ([NumPy parallel RNG](https://numpy.org/doc/stable/reference/random/parallel.html); [Random123](https://doi.org/10.1145/2063384.2063405)). Adding a sensor or aircraft then does not perturb other streams, and any single sortie of any tail can be regenerated alone.
- **Manifests.** Each run records the git commit, config and data hashes, library versions, BitGenerator name and stream table.
- **Provenance and assumptions.** Every assumption is a versioned record (ID, statement, source, owner, affected modules and tests, status), linked to DVC data versions and MLflow runs. This implements NASA-STD-7009B's requirement to record calibrations and parameter changes with justification.
- **Transport timing never feeds back; decisions do, through one door.** Pub/sub replays or taps deterministic recorder output read-only, so message delivery, broker lag or consumer speed never alters simulation state. Decisions are a different path. They enter only through the orders channel (M21), stamped with the simulation time at which they take effect, and are recorded in the order log. *(The first version of this report said "streaming never feeds back" without this distinction, which would have left prescriptive analytics nothing to act on.)*
- **Units.** Checked with pint at configuration load and module boundaries in validation mode, and stripped to float64 SI arrays in hot loops.

### Closing the loop: maintenance orders and a forkable world

The first version of this design could evaluate *prediction* but not *advice*. Two requirements were missing. Fleet availability is driven by decisions as much as by wear: when to inspect, which part to fit, which aircraft flies which sortie, whether to cannibalise. A prescriptive system therefore needs (a) a way to act on the simulated fleet, and (b) a way to test "what if we had done X instead" [ASSUMPTION grounded in Section 12's record systems and the CAG availability mechanisms].

**(a) The orders channel (M21).** Decisions are explicit, typed inputs.

| Field | Content |
|---|---|
| `order_id` | Globally unique; re-sending the same ID is a no-op (idempotent) |
| `issuer` | Human planner or AI agent ID, plus the policy or model version |
| `t_issued`, `t_effective` | Simulation times; `t_effective` is at or after the next decision epoch |
| `target` | Tail, base, LRU or serial number |
| `action` | From the Section 12 record vocabulary, listed below |
| `parameters`, `priority` | Action-specific; supply priorities AOG/MCM/PHU |
| `evidence` | `record_id`s of the samples, events or records that justified the order |

**Action vocabulary:**
- inspect (borescope, conditional, NDT);
- troubleshoot a fault code;
- remove/replace (with a specific S/N or "any serviceable");
- engine wash and servicing (oil, hydraulic, tyres);
- defer a defect (with limits and an expiry);
- cannibalise from a donor tail;
- requisition or expedite spares;
- transfer stock between bases;
- ground or release an aircraft;
- bring forward or defer scheduled servicing;
- assign or reassign sorties and mission types;
- restrict usage (e.g., an AB or g limit);
- embody a modification or software load;
- change monitoring configuration (BIT filter lists, thresholds).

**Orders are requests, and execution is imperfect.**
- M21 checks authority and airworthiness: an aircraft with an open grounding defect cannot be released.
- M18 checks resources and supplies: tradesmen and shifts, ground equipment, hangar slots, and stock plus the supply pipeline using the CAG-calibrated delay distributions. It accepts, queues, partially executes or rejects the order, and reports the outcome on `orders.status`.
- Execution uses the Section 9 and 12 outcome models:
  - a wash restores only a fraction ρ of fouling;
  - inspections have detection probabilities;
  - troubleshooting can replace the wrong LRU (NFF/RTOK);
  - any maintenance action can inject a latent defect;
  - a part swap changes serial numbers and therefore the hidden-state trajectory.
- Every executed order produces the same records a human-initiated job would (work order, signatures, part movements, availability-state changes). The AI's own actions therefore reappear in the data it later reads.

**Information discipline keeps advice honest.**
- The decision-maker sees only the ground-decoder contract and the maintenance records, with `t_ingest ≤ t_decision`. Truth and label topics are never visible.
- An order whose `evidence` cites data not yet ingested is rejected. This blocks look-ahead leakage.
- Decision epochs are explicit and configurable: post-download, the daily maintenance meeting, weekly flying-programme planning.
- In live mode, orders arriving between epochs are applied at the next epoch boundary in simulation time, never at their wall-clock arrival time.

**Determinism is preserved by event sourcing.** A run is a pure function of (root seed, configuration, dictionary version, order log). A live closed-loop session records its order log. Replaying that log reproduces the session bit-for-bit, including the AI's influence on the fleet.

**(b) The forkable world (M22).**
- **Snapshot.** At any decision epoch (sortie boundaries by default, mid-sortie optional) the complete world state is serialised and content-hashed:
  - every module's state: physics, per-serial hidden health, sensor unit biases and drift, clock-domain phases, BIT persistence counters and latches;
  - open work orders, queues, inventories and in-transit spares;
  - schedules and pending events;
  - RNG stream counters;
  - configuration and dictionary versions;
  - the order log so far.

  Fleet-level state is small. Full physics state is needed only at sortie boundaries.
- **Fork.** A branch is a parent snapshot plus a divergent order suffix (copy-on-write). Any number of branches can run from one snapshot.
- **Common random numbers.** Exogenous randomness comes from counter-based streams keyed by *identity*, not by draw order. Keys are tail, serial, date, sortie and event index. This covers weather, mission demand, bird strike/FOD, sensor noise and each component's intrinsic failure threshold. Branches therefore share the same exogenous future, and differences between them are caused by the decisions. A part fitted in one branch draws from its own serial's stream, which is identical in every branch where that serial is installed. This is why the key-path RNG design above must be in place from the first line of code: it cannot be retrofitted.
- **Three fork modes:**
  1. **Oracle fork.** Copies the true state. It scores advice against what was actually there (regret, value of information). This is privileged, and never exposed to the AI under test.
  2. **Belief fork.** Resamples hidden states from a distribution consistent with what the decision-maker could observe at t: the AI's own posterior or particles, or the simulator's prior conditioned on the observed stream. It tests whether advice is robust to what was not knowable.
  3. **Ensemble forks.** N branches with different exogenous seeds, giving outcome distributions.
- **What-if API.** `snapshot(t)` → `fork(snapshot, branch_id, order_suffix | policy)` → `run(horizon)` → KPIs. The KPIs are MC/FMC availability, flying-task achievement, AOG days, cannibalisation rate, maintenance man-hours, a cost proxy and in-flight failures. Branches are compared by CRN-paired differences with confidence intervals.
- **Reference policies** are built in so advice is always benchmarked against "what would have happened anyway": an IAF-style hard-time/reactive status quo, a scheduled policy and simple condition-based thresholds.

**Requirements this places on every module.** Each module must:
- implement complete `get_state` / `set_state` (already part of the module contract above);
- draw all randomness through the key-path RNG service, never a global generator;
- have no wall-clock dependencies;
- keep no state outside its declared state vector.

**Regression tests come in four tiers plus property tests** ([validation note](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf)):
1. **Bitwise determinism** for the same seed, platform and version, in a pinned container with pinned BLAS and threads.
2. **A golden "Phalanx MQTG".** Replayed manoeuvres and engine transients, with over-plots and Tier-2 tolerances of about 20–40 % of the validation tolerances.
3. **Statistical regression** between versions using fresh-seed ensembles and *equivalence* tests rather than "no significant difference", plus a re-run of the discriminator battery.
4. **Physics metamorphic relations.**
   - 2× resampling leaves the PSD below the old Nyquist unchanged.
   - An ISA offset leaves corrected relationships invariant.
   - Mirrored lateral inputs give mirrored responses.
   - Zero degradation gives a flat health trend.
   - More degradation gives a monotone EGT-margin loss.
   - A fault-free run gives only the configured false-alarm rate.
5. **Property-based invariants:** envelope limits, non-negativity, balance residuals, saturation and units.
6. **Closed-loop and fork tests:**
   - snapshot → restore → continue is bitwise identical to an uninterrupted run;
   - two forks with identical order suffixes are bitwise identical;
   - a CRN audit shows exogenous draws for shared entities are identical across branches;
   - orders citing un-ingested evidence are rejected, and the decision interface exposes no truth fields;
   - re-sending an `order_id` changes nothing;
   - replaying a recorded order log reproduces a live closed-loop session.

**Run it as a continuous pipeline.**
- **On every merge:** tiers 1–2 and property tests.
- **Nightly:** tiers 3–4, the statistical battery and the discriminator ladder against frozen real proxy splits.

**The build sequence mirrors the emission phasing.**
- **Phase 0 (gate):** the [settling experiment](../analysis/settling_experiment/PREREGISTRATION.md). The texture layer (M13) is not built for the Tejas until it reports, and its diagnosis decides which texture components need rework.
- **Phase 1:** M01–M14 at v1 fidelity with the fast path (M17 schema), M18 and M19, plus M21 (minimal vocabulary: inspect, replace, defer, ground/release, assign sortie) and M22 (snapshot/restore at sortie boundaries). The last two come first because determinism and complete state capture are expensive to retrofit.
- **Phase 2:** M15–M16 and full-path round-trip tests; the full M21 vocabulary; belief forks.
- **Phase 3:** calibration against any real data obtained, plus live streaming and live closed-loop sessions.

---

## 15. What public information can and cannot deliver

| Category | What it covers | How it is validated and corrected |
|---|---|---|
| **Genuinely achievable from public information** | Tejas architecture (FCS, sensors, actuators, avionics hub, recorders, utility LRUs); longitudinal aero core and inertia; envelope; F404 architecture, sensors, control structure, operating lines, transient constants, monitoring semantics (rates, buffers, LUI definitions) and fault-signature directions; utility normal bands (MIL standards); recorder and bus formats (IRIG 106, 1553, ARINC 429); record systems and codes (NAMP, TO 00-20, S5000F); IAF process facts and audited availability; measured real-recorder texture mechanisms | Reproduction of published tables, traces and tests (C1–C28, V1–V12); format conformance; process plausibility; Level 2 against proxies |
| **Must be approximated (transfer with scaling)** | IN20 cycle details (BPR, PRs, T4, dry thrust); lateral-directional and Mach-dependent aero; FADEC schedules, thresholds and persistence; texture parameter values (LSBs, noise, offsets) for fighter sensors and chains; deterioration rates (commercial × severity factor); BIT coverage and false-alarm rates; utility degradation rates; sortie mix and usage spectra; supply delays | Sweep within transfer ranges; check signs, orders of magnitude and corrected relationships; "simulate the proxy, then swap"; SME review |
| **Unavoidable assumptions (no public basis)** | Phalanx ICD (bus allocation, RT map, message rates); crash-recorder parameter list and loop; ECMS exceedance limits and LUI gates; HUMS scope; oil-system numbers; CWS legend logic; IAF form fields and code tables; IAF per-aircraft and per-pilot hours and Tejas squadron mission mix; fighter severity factor S; latent-defect injection probabilities; per-LRU clock drift | Declare in the assumption registry with ranges; make them configurable dictionary data; test PdM sensitivity to each; replace when DSSC/IAF/HAL data arrive |
| **Ceiling** | NASA-STD-7009B Validation Level 2 for platform-independent properties; Level 1–2 with SME sign-off for platform-dependent levels and fault signatures | Level 3–4 only with real Tejas/IN20 data |

**Progressive correction works because the architecture isolates where real data would land:**
- recorder or IECMS-type samples → M13/M14 texture and monitoring parameters, via the existing DASHlink refit scripts;
- engine trend data → M07/M10 health and deterioration parameters, via the calibration harness;
- ICD excerpts → the M01 dictionary and M15/M16 adapters only;
- record templates → M18 code tables only;
- usage logs → M02 mixtures.

In each case the downstream contract stays unchanged.

---

## 16. Decision register

| # | Decision | Current recommendation | Evidence | Alternatives held open | What would change it |
|---|---|---|---|---|---|
| D1 | Target aircraft | Tejas Mk1A-class with F404-IN20 as a composite F404 | Section 0; [CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf); stage-2 Tejas literature | Su-30MKI/AL-31FP; F/A-18-class as a fully defensible proxy | DSSC/IAF priority on the Su-30 with sanitised data; an IAF request for a specific fleet |
| D2 | Aero model | Tejas-anchored parametric build-up with ADMIRE/F-106B donors | Section 7; V1–V12 | Rescaled F-16 tables; full ADMIRE; VSPAERO/DATCOM-only | Release of Tejas aero tables or NAL SI data |
| D3 | Engine model | pyCycle CLM + dynamic shell + FADEC replica; PWL surrogate for fleet runs | MAPSS/C-MAPSS40k templates; F404 corpus | Table + lag (with labelled error); T-MATS online CLM | IN20 deck or maps from GE/HAL; compute limits |
| D4 | Role of ML | Not in the truth path; texture and surrogates only; hybrids in v2 behind flags | [PGNN 73 %](https://arxiv.org/abs/1710.11431); APHYNITY; Wehenkel | Diffusion/copula residual layer | Real fighter residual data plus ablation showing a gain |
| D5 | Residual model | Layered parametric model fitted to [MEASURED] DASHlink; class-specific physics | Section 8 | Learned residuals | Fighter recorder data (refit) |
| D6 | Degradation family | Stochastic processes on physical states; separate sensor-fault layer; imperfect maintenance | Section 9 | Pure PoF; pure data-shaped processes | Fleet trend data; HAL/IAF defect statistics |
| D7 | Emission boundary | Layered: CIR → bus → Ch10 → **ground decoder contract**; fast path with identical schema | Section 5; [GAO-20-316](https://www.gao.gov/products/gao-20-316); [BEA](https://bea.aero/uploads/tx_scalaetudessecurite/use.of.fdr_01.pdf) | Decoded-only output; bus-only | DSSC requires a specific format or a live link |
| D8 | Recorder container | IRIG 106 Ch10/11 + TMATS as a surrogate | Public byte-level standard and tools | ARINC 717 frames; proprietary-like custom format | Disclosure of the actual Tejas CDR/HUMS format |
| D9 | Transport and schema | Kafka + Avro/Protobuf + Parquet | Kafka/Flink/Avro docs | MQTT/Sparkplug; DDS; TSDB for dashboards | Downstream team or deployment constraints |
| D10 | Rate groups and timing | Asynchronous domains (DFCC 80, FADEC 50–67, 1553 50/25/12.5/6.25, recorder decimation); 240 Hz truth step | Section 13; Kala; ADE 12.5 Hz | 120 Hz single master frame | Real Tejas 1553 schedule / FADEC frame |
| D11 | Sensor list | 189-row inventory as a dictionary seed, labelled synthetic | `parameter_inventory.csv` | Larger HARV-like set; smaller CDR-like set | Real ICD or CDR list |
| D12 | Fault-code structure | Synthetic `SSS-NNN` echoing ADE subsystem offsets; PFL/MFL split; S5000F mapping | [JOAST 782](https://joast.org/index.php/joast/article/view/782); AGARD-CP-448 | F/A-18 MMP-style 3-digit codes | Tejas fault-code dictionary |
| D13 | Maintenance schema | NAMP/TO 00-20 structure + UK F700 heritage + S5000F; IAF-relabelled codes | Section 12 | Pure S5000F; e-MMS-mimicking schema | IAF templates from DSSC |
| D14 | Validation target | Level-2 credibility card; tolerance = max(floors); real-vs-real baselines | Sections 10–11 | Single realism score | Real Tejas data enabling Level 3 |
| D15 | Discriminator role | One test in a battery; never the definition | [Cranmer](https://arxiv.org/abs/1911.01429); [Müller](https://arxiv.org/abs/2106.12914) | Discriminator-driven refinement (SimGAN-like) | Evidence that PdM utility tracks discriminator scores |
| D16 | Reproducibility | Key-path SeedSequence/Philox streams; manifests; DVC/MLflow; assumption registry | NumPy; Random123; 7009B | — | — |
| D17 | Sortie-length model | Lognormal median 45–55 min (Tejas-anchored) | CAG/ADA Tejas data; FINAF/RAAF | Gripen-based median 70–80 min | IAF squadron sortie data |
| D18 | Decision feedback | Closed loop through a typed, sim-time-stamped, logged orders channel (M21) applied at decision epochs; execution by M18/M02 with resource limits and imperfect outcomes | Section 14 "Closing the loop"; NAMP/TO 00-20 action vocabulary; CAG availability mechanisms | Open loop (prediction only); free-form API calls applied at wall-clock time (breaks determinism) | Downstream team needs a different decision cadence or action set (change the epoch calendar and vocabulary, not the mechanism) |
| D19 | What-if evaluation | Snapshot/fork service (M22) with identity-keyed common random numbers; oracle, belief and ensemble forks | Section 14; NumPy/Random123 key-path streams | Re-running from t = 0 per scenario (slow, no CRN); independent-seed comparisons (high variance) | Snapshot cost at the chosen granularity; evidence that belief forks need the AI's own posterior format |
| D20 | Missingness model | Generated by the clock-domain slip mechanism (per-unit Δ, collision window w) instead of an independent dropout process | Section 8 correction (burst period = 1/(f·Δ) at all four rates) | Independent periodic Gilbert–Elliott (comparator L6′) | Settling-experiment mechanism checks P1–P5 failing |

---

## 17. Prioritised gaps and next concrete steps

| Priority | Gap | Why it matters | Route |
|---|---|---|---|
| 1 | IN20 FADEC logic, limits (start EGT, MIL EGT, oil-pressure bands, overspeed), fault-code dictionary, sample rates | Drives exceedances, codes and accommodation behaviour | Request via the PS owner (HAL Engine Division / ADA / GE); otherwise keep as swept [ASSUMPTION] |
| 2 | Tejas bus topology, ICD excerpts, crash-recorder parameter list and rates, HUMS scope, ECMS parameters and snapshot windows | Defines the observable stream | Request via the PS owner; leads: HAL Korwa SSFDR type approvals, PCC/HAL HUMS documents |
| 3 | IAF per-aircraft and per-pilot hours, Tejas squadron mission mix, serviceability and AOG statistics | Calibrates usage and availability | Parliament Q&A (browser session), CAG 15/2024 full text, CAG Air Force reports 2016–25; request via the PS owner |
| 4 | Any real F404/IN20 or Tejas recorder/IECMS sample (even sanitised, minutes long) | The only route above Level 2 for texture | Request via the PS owner; refit with the existing DASHlink scripts |
| 5 | IAF record templates (Form-700 equivalents, e-MMS data model, engine log-book format, snag codes) | Makes the records layer native | Request via the PS owner or retired IAF engineers |
| 6 | Tejas lateral-directional derivatives, MAC and CG limits, drag polar, approach/take-off numbers | Aero completeness and ground phases | Paywalled AIAA GNC 2002 / ATIO 2002 papers; NAL repository (DNS-blocked here); ADMIRE files via admire@foi.se |
| 7 | Utility rates (pump flow, generator rating, accumulator/strut leakage, chip-light nuisance rates) | Degradation calibration | DRDO/CVRDE pages (inaccessible this session); CEMILAC type approvals |
| 8 | Fighter sim-vs-real comparisons; MUAD/AEE numeric envelopes; CIFER coherence threshold; SAE ARP741 | Validation thresholds | Targeted searches; paywalled standards |
| 9 | Open conflicts (Appendix A) | Consistency | Resolve as sources appear; otherwise keep configurable |

**Concrete next steps, in order:**
1. **Register for DSTG HUMS2027 before 31 Oct 2026** (restricted, non-shareable vibration spall data for AMAGB/bearing texture) ([HUMS2027](https://www.humsconference.com.au/HUMS2027datachallenge/download.html)).
2. **Settle the texture premise before building Tejas modules** (in progress). Simulate DASHlink with the texture model for N1, N2, EGT, FF and VRTG. Run the trivial-cue audit, then the discriminator ladder against held-out Tail 687 flights, with a Tail 687 vs Tail 652 baseline. The rules were fixed before any results ([PREREGISTRATION.md](../analysis/settling_experiment/PREREGISTRATION.md)). If synthetic data cannot get as close to real as one real tail is to another, rework the "learn texture from the proxy" premise before anything depends on it.
3. Stand up M01 (dictionary seeded from the 189-row CSV and the 50-state CSV), the fast-path contract (M17/M19), and the M21/M22 skeleton (key-path RNG, order log, snapshot/restore). M13 follows the settling verdict. The downstream AI team can start on the contract immediately.
4. Implement the engine CLM and FADEC and run C1–C28; implement the aero build-up and run V1–V12.
5. Acquire further DASHlink archives (Tail 687 archives 2–9; Tail 652 archives closer to 2001) to test drift persistence, flight-to-flight variation of Δ and tail-to-tail spread. Then N-CMAPSS, NGAFID + MaintNet and RflyMAD; the PX4 logs are already local.
6. Draft the assumption registry and the first credibility card.

**Requests to the PS owner (DSSC/IAF)** — each one replaces a block of assumptions:
- a sanitised extract of Tejas ECMS/HUMS/crash-recorder data, in any format, with its parameter list and rates;
- the IN20 cockpit and maintenance limits and the ECMS exceedance and LUI definitions, at whatever classification level is releasable to a hackathon;
- the Tejas CWS legend list and the BIT/fault-code structure;
- blank e-MMS/IMMOLS or Form-700-equivalent templates and the snag/action code lists;
- squadron-level flying-task, hours, sortie-length and serviceability statistics for the Tejas (or the Su-30MKI if that fleet is preferred);
- confirmation of which fleet the problem owner wants the demonstrator to represent;
- whether IAF/HAL would accept IRIG 106 Ch10 plus a decoded Kafka/Parquet contract as the demonstration interface.

---

## 18. Conclusion

The research changes the question from "can Phalanx copy a fighter's data?" to "can Phalanx make every gap explicit and replaceable?". Public sources fix almost everything about how a Tejas-class fighter's data are *structured*: which systems exist, what is measured and what is hidden, how variables couple through corrected parameters and N2, how data leave the aircraft, how records link to telemetry, and what real recorder texture looks like. Public sources fix almost nothing about the fighter-specific *numbers* that a maintenance AI would latch onto, such as limits, thresholds, noise levels and rates. The defensible product is therefore not a "realistic Tejas". It is a **realistic Tejas-shaped measurement process with labelled, swept parameters**, whose ground-decoder contract would accept real data unchanged. That last property is the strongest argument to put before DSSC and the IAF: the same pipeline that trains the AI on synthetic data can ingest their data on the day they share it.

Two findings should shape priorities. First, the dominant realism risks are not exotic physics. They are mundane chain effects — quantisation lattices, structured missingness, per-unit offsets, timing skew, imperfect BIT and dirty records — which simulators routinely omit and discriminators detect first. Getting these right is cheap and well evidenced. Second, the Tejas's documented availability shocks came from engine supply, a starter in the cold, a fuel-gauging artefact and a brake-software load, not from slow gas-path wear. A predictive-maintenance demonstrator that models only degradation curves would miss the failure modes the problem owner actually experiences. Configuration, supply and engineering-authority events belong in the generator alongside physics.

---

## Appendix A — Restricted, unreplaced, snippet-level and conflicting values

**A1. Restricted-manual values with no released replacement found — sanity-check only / open.** These parameters exist in sibling notes only from the restricted F/A-18 NATOPS copy or the Hellenic AF F-16 manual. Their values are deliberately not reproduced here and must not appear in deliverables as evidence. Unreplaced items:
- F404 maximum start EGT;
- F404 idle, start-peak and MIL oil-pressure bands;
- F404-402 MIL steady EGT limit;
- the thermal-soak restart (motoring) rule;
- F/A-18 on-speed approach AoA;
- F/A-18 take-off trim and rotation, tyre-speed, gear and climb speeds, cruise AoAs and roll-out braking items;
- F/A-18 hot-weather items (fuel-hot threshold, avionics cooling, AMAD limits);
- F-16 start FTIT limits and JFS timings;
- F-16 final-approach AoA;
- F-16 drag-chute band;
- F-16 over-g report thresholds;
- F-16 FLCS BIT duration and EPU check;
- F-16 tyre and brake-energy limits;
- F-16 shutdown items.

**Replaced items** (now cited from released sources in Section 4):
- F404 idle and MIL fuel flow, N1/N2 and thrust (USAF IERA test cell);
- idle EGT (test-cell point) and the -400 T5 limit of 830 °C;
- F-16 idle fuel flow (F100-229, F110-129) and the idle-rpm band (AIB);
- F-16 approach and touchdown speeds and aerobraking attitude (AIB);
- F-16 AoA and g limiters (TP-1538; AGARD R-815);
- F/A-18 carrier approach-speed regression (NADC-91027-60);
- AAR closure (Tejas-class NFTC data);
- chute speeds (Tejas DDP).

**Partly replaced:**
- start sequence (T-50 KSAS timeline);
- idle-before-shutdown (Gripen 259 s);
- MIL-check N2 (points, not a band).

**A2. Snippet-level or indicative-only items (weaker evidence):**
- PCAMi-1000 input types and its HUMS configuration claim;
- CEMILAC TA-1849 SSFDR composition;
- the HAL MCSRDC brochure listing the Mk1A mission computer;
- the DRDO avionics-page details;
- the "110 L/min" hydraulic pump-flow lead (search-index excerpt);
- the Edwards AFB F-16 engine-event/MFL pairing (releasability unverified; sanity-check only);
- several GAO/USAF pilot-hour figures (search excerpts);
- AGARD R-815 spectra (graph-read ±25–30 %);
- Misawa/Luke AIB figures quoted from a flight manual (indicative only);
- the F/A-18C >88 % BIT false-alarm rate (secondary).

**A3. Stage-2 supersessions and resolved conflicts:**

| Item | Earlier value or position | Current position | Basis |
|---|---|---|---|
| Tejas public modelling data | Aero and sensors scored 1/5 (stage 1) | Longitudinal aero, inertia, FCS, air data and actuators anchored on DIRECT/DIRECT-unnamed data | Stage-2 DSJ/JOAST/AeSI harvest |
| Henry IECMS precision table | T1 test-cell 296 K; T5 934.3/971.0 K; ECU T5 trim +15 °F | **T1 266 K; T5 834.3 K (test cell) / 871.0 K (aircraft); XN2 2σ 138 rpm; trim ±150 °F** | Page-image check (OCR errors) |
| Squadron sortie length | Median 70–80 min | Median 45–55 min [ASSUMPTION], Tejas-anchored | CAG/ADA Tejas data |
| Engine time per flight hour | 1.35 (F-22 design) | 1.56 (FINAF F404-402) preferred | ICAF Finland 2017 |
| CIFER J / TIC thresholds | Unverified | J_ave ≤ 100, TIC ≤ 0.25 sourced (via secondary citations) | arXiv 2506.23302; arXiv 1711.10010 |
| Sensor noise model | C-MAPSS/ProDiMES iid σ | Layered measured texture | DASHlink measurement |
| Aero basis | F/A-18 or F-16 tables | Tejas-anchored build; F-16 as fallback only | Stage-2 aero evaluation |
| g limits | +9/−3.5 vs +8/−3.5 | +8/−3.5 operational; +9 design/FOC | MoD DDP; ADA |
| LRU count | >500 | 344 | CEMILAC 2015 |
| Engine mass | 1,035 kg (tejas.gov.in) | 1,072 kg | GE data sheet |
| Master frame | 120 Hz single frame | 240 Hz truth step + asynchronous LRU domains | This synthesis [ASSUMPTION] |

**A4. Conflicts left open (keep configurable or flag):**
- IECMS post-event window: 25 s vs 35 s;
- F404-400 MIL thrust: 10,000 vs 10,600 vs 10,700 lbf;
- PLA rate limits: 19.03/26.81 vs 14/22 °/s;
- -402 BPR: 0.27 vs 0.29;
- Tejas maximum Mach: 1.6 (cleared) vs 1.8 (Jane's);
- ceiling: 15 vs 16 km;
- external stores: 3,500 vs 5,300 kg;
- Tejas fleet at the 2026 grounding: 34 vs 36;
- No. 18 Squadron base, and the first Mk1A unit;
- IN20 engines received: 6 vs 7;
- Jaisalmer 2024 crash cause: oil pump vs oil level;
- 124 HUMS DAUs vs 180 Mk1A ordered;
- "three 1553B buses" (secondary only);
- DEEC fault count: 160 vs 150;
- angular-momentum flowmeter response: 80/300 ms vs 0.75–2 s;
- time from first chip sign to failure: hours vs 36–100 FH.

## Appendix B — Where the detail lives

| Topic | Note (in `research_notes/Virtual fighter telemetry layer research/`) |
|---|---|
| Platform choice, Indian fleet evidence | `indian_fleet_platform_relevance.md`; `candidate_airframe_modelling_data.md`; `candidate_engine_and_ehm_data.md` |
| Airframe, aero, FCS, air data | `tejas_airframe_aero_fcs.md` |
| Engine model and monitoring | `f404_in20_engine_model.md`; `addendum_engine_F404_F414_monitoring.md` (correction banner applies); `addendum_engine_AL31_M53_M88_Kaveri.md` |
| Utilities | `tejas_utility_systems.md` |
| Avionics, recording, BIT, inventory, rate groups | `tejas_avionics_and_parameter_inventory.md`; `parameter_inventory.csv`; `not_measured_states.csv` |
| Texture (literature, measured, gap closure) | `sensor_residual_texture.md`; `empirical_dashlink_texture.md` (scripts in `analysis/dashlink_texture/`); `texture_and_fault_gap_closure.md` |
| Faults and degradation | `faults_and_degradation.md`; `texture_and_fault_gap_closure.md` |
| Usage and profiles | `flight_profiles_and_usage.md` (restricted-source values superseded); `iaf_usage_and_validation_gap_closure.md` |
| Data pathway and formats | `data_pathway_and_formats.md` |
| Maintenance records | `maintenance_records_and_events.md` |
| Modelling methodology | `modelling_methodology.md` |
| Validation and calibration | `validation_and_calibration.md`; `iaf_usage_and_validation_gap_closure.md` (Q6) |
| Datasets | `public_aerospace_datasets.md` |
