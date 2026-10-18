# Candidate fighter airframes: how much public physical-modelling data exists, and which can be modelled most faithfully

Scope: public, unclassified 6-DOF modelling data (aero, mass/inertia, geometry, actuators, flight control laws, engine/thrust, sensors, ground reactions, flight-test validation) for F-16, F/A-18 A-D (incl. NASA HARV), Gripen (via FOI ADMIRE/Saab GAM), HAL Tejas, Su-27/Su-30, Mirage 2000, Rafale, Eurofighter, plus generic research fighters (GARTEUR HIRM, NASA generic models). Project context: Phalanx, first deliverable is a realistic data-generation and streaming layer, not the AI.

Method note (read first):
- Primary documents were downloaded and read directly (text extraction plus page images for tables). Local copies are in `/Users/abishaikc/Phalanx/research_sources/airframe_data/`: NASA TP-1538, TM-107601, TM-110216, TM-2003-212145, TP-97-206539, TP-1999-206573, CR-201670, TP-2857, the DGLR 2024 ADMIRE paper, Härkegård's LiU Lic-875 and PhD-820 theses, the ACC 2011 ADMIRE paper, and the Chakraborty 2011 F/A-18 paper. Model files (JSBSim, FlightGear F-16, AeroBenchVV) were inspected from GitHub raw sources.
- **Search budget limit:** partway through this task, the shared web-search budget for the turn ran out (limit 200 WebSearch calls across all agents). After that, only direct fetches of known URLs were used. As a result, the Tejas system-identification literature, Su-27/Su-30 academic datasets, flight-manual legal status, and the F-16XL/X-29/X-31/F-15 HIDEC/ACTIVE raw-data question are less well covered than the US airframes. They are listed as explicit gaps; nothing there has been invented.
- DTIC (apps.dtic.mil) blocked automated downloads ("The request is blocked"), so DTIC-only documents are cited only from search-result metadata.
- Evidence tags: [DIRECT] = about that exact aircraft or system; [TRANSFER: X] = taken from platform X, with the reason and limits given; [ASSUMPTION] = engineering judgement, with a note on how to validate it.

Cross-links to parallel researchers: engine and EHM data (F404/F110/AL-31FP internals), sensor residual texture (noise and bias models), faults/degradation, maintenance records (PFL/MFL, caution lists), data pathway and formats (MIL-STD-1553, PCM telemetry), validation/calibration, flight profiles, IAF platform relevance. Items below that belong mainly to those topics are marked "→ cross-link".

---

## Q1. Per-candidate inventory: what public 6-DOF modelling data exists?

### Takeaway
Only two real fighters have **complete, wind-tunnel-derived, nonlinear 6-DOF data in the public domain**: the **F-16** (NASA TP-1538 full low-speed tables, printed in the report) and the **F/A-18** (NASA f18bas/f18harv simulation, documented in TM-107601 and TM-110216, plus flight-identified derivatives from the HARV). For Gripen, the closest public model is Saab's *generic* GAM inside FOI's ADMIRE, not Gripen data. For Tejas, Su-27/30, Mirage 2000, Rafale and Eurofighter, no public aerodynamic coefficient tables were found. Only geometry/mass headline figures and flight-control architecture statements are public for them.

### Cited Findings
**F-16 [DIRECT]**
- Aero: tables of CX, CZ, Cm, CY, Cl, Cn as functions of α and β (and stabilator δh), with leading-edge-flap and speed-brake increments and damping derivatives. Ranges: −20° ≤ α ≤ 90° and −30° ≤ β ≤ 30°. Source: low-speed (M = 0.1–0.2) static and forced-oscillation tests of subscale models at NASA Ames and Langley. Mach, Reynolds-number and aeroelastic effects are not included. — [NASA TP-1538, p. 9 and App. B pp. 36–40](https://ntrs.nasa.gov/citations/19800005879)
- Mass and geometry: weight 91,188 N (20,500 lb). Inertias Ix 12,875, Iy 75,674, Iz 85,552, Ixz 1,331 kg·m² (9,496 / 55,814 / 63,100 / 982 slug·ft²). Span 9.144 m, S 27.87 m², c̄ 3.45 m, reference CG 0.35 c̄. — [TP-1538 Table I, p. 43 (PDF p. 50)](https://ntrs.nasa.gov/api/citations/19800005879/downloads/19800005879.pdf)
- Control laws, actuators and engine thrust tables are also published in the same report (details in Q2). — [TP-1538 App. A–B](https://ntrs.nasa.gov/citations/19800005879)

**F/A-18 A-D [DIRECT]**
- NASA Langley f18bas: nonlinear 6-DOF with engine model, sensors, and first-order rate/position-limited actuators. Includes a simplified FCS v8.3.3 (Auto Flap Up CAS). Wind-tunnel-derived aero database covers α −10° to +90° and β ±20°, with quasi-static elasticity. — [NASA TM-107601 summary and §1.2](https://ntrs.nasa.gov/citations/19920024293)
- f18harv extends this to the HARV: aero database for α −10° to +90°, β ±20°, Mach 0.0–2.0 and altitude 0–60,000 ft, with HARV thrust-vectoring and ANSER increments, a DFRC-supplied engine model and "high-fidelity" sensor models. — [NASA TM-110216, p. 1 and summary](https://ntrs.nasa.gov/citations/19960027892)
- Flight-identified derivatives (HARV and basic F-18) are published in separate reports (Q4). — [Iliff & Wang TP-97-206539](https://ntrs.nasa.gov/citations/19980007172); [TP-1999-206573](https://ntrs.nasa.gov/citations/19990019364)

**Gripen C/D [TRANSFER: Saab GAM / FOI ADMIRE]**
- Saab's Generic Aerodata Model (GAM) "contains aerodynamic data for a small fighter aircraft, not unlike JAS 39 Gripen". It was released by Saab AB (Backström, Saab report, May 1997). — [Härkegård Lic. thesis Lic-875, §7.1.1 p. 87 and refs [5], [64]](https://www.rt.isy.liu.se/research/reports/LicentiateThesis/Lic875.pdf)
- FOI's ADMIRE wraps GAM in Simulink, adding actuators, sensors, engine and FCS. Details in Q5. — [Härkegård PhD-820, §2.4 pp. 21–22](https://www.control.isy.liu.se/research/reports/Ph.D.Thesis/PhD820.pdf)
- Limit of the transfer: GAM is explicitly *generic*. It is not certified Gripen data, and no source equates it with Gripen.

**HAL Tejas [DIRECT, architecture only]**
- ADA describes a "full authority quadruplex digital fly-by-wire" FCS. The flight control computer and air data system are fail-operational/fail-safe, and actuators have hydraulic and electrical redundancy. No numbers are given. — [ADA IFCS page](https://www.ada.gov.in/images/ifcs.htm)
- ADA's aerodynamics page lists wind-tunnel, CFD and flight-data-analysis activities for an "aerodynamically unstable tailless compound delta" but publishes no data. — [ADA Aerodynamics & Performance page](https://www.ada.gov.in/images/ard2.htm)
- Headline specifications (Mk1A): length 13.2 m, span 8.2 m, wing area 38.4 m², empty 6,560 kg, gross 9,800 kg, MTOW 13,500 kg, internal fuel 2,458 kg, F404-GE-IN20 at 85 kN with afterburner, +9/−3.5 g. — [Wikipedia: HAL Tejas, Specifications](https://en.wikipedia.org/wiki/HAL_Tejas)

**Su-30MKI [DIRECT, headline only]**
- FBW "with quadruple redundancy" (uncited in the article). AL-31FP at 123 kN with afterburner. Nozzles ±15° in one plane, mounted 32° outward. Empty 18,400 kg, MTOW 38,800 kg, wing area 62 m², +9 g. Navigation: SAGEM Sigma-95 GPS with ring-laser-gyro INS. — [Wikipedia: Sukhoi Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI)

**Mirage 2000, Rafale, Eurofighter [DIRECT, headline only]**
- Mirage 2000: FBW with "four analog computers" and relaxed stability. M53-P2 at 65 kN dry and 95 kN with afterburner. Wing area 41 m². — [Wikipedia: Mirage 2000](https://en.wikipedia.org/wiki/Dassault_Mirage_2000)
- Rafale: digital FBW, aerodynamically unstable. M88 at 50 kN dry and 75 kN with afterburner. Load limits −3.6 to +9 g. — [Wikipedia: Rafale](https://en.wikipedia.org/wiki/Dassault_Rafale)
- Eurofighter: quadruplex digital FBW and relaxed stability. EJ200 at 60 kN dry. Airframe life 6,000 h. — [Wikipedia: Eurofighter Typhoon](https://en.wikipedia.org/wiki/Eurofighter_Typhoon)

### Inferences
- "Exact mechanics" from public information is achievable only for the F-16 (low-speed envelope) and F/A-18 (full-envelope database structure, with flight-test-identified derivatives). For every other candidate, the airframe dynamics must come from a proxy. [ASSUMPTION — validate by repeating targeted searches in a fresh session for NAL/TsAGI/ONERA/DLR datasets; see Gaps]

### Gaps
- No public aero coefficient tables were found for Tejas, Su-27/30, Mirage 2000, Rafale or Eurofighter. The targeted academic searches for Su-27 and Tejas could not be completed after the search budget ran out (see Q6 and Q7).

---

## Q2. NASA TP-1538 (Nguyen et al., 1979): content, limits, and its descendants (Stevens & Lewis, open-source code)

### Takeaway
TP-1538 is the root of almost every public F-16 model. It prints complete low-speed nonlinear tables for α −20°…90° and β ±30°, plus actuator models, the CAS control laws, LEF schedule and thrust tables. It has **no Mach dependence**, and it represents the 1979-era F-16 (pre-Block 15 tail). Stevens & Lewis use a reduced subset (α −10°…45°, second-order terms dropped, linear CY). Most GitHub F-16 sims (AeroBenchVV, f16-flight-dynamics, UMN/isrlab) implement either the S&L subset or the full TP-1538 "high-fidelity" tables.

### Cited Findings
- [DIRECT] Bibliographic: NASA-TP-1538 (L-12854), Dec 1979, Nguyen, Ogburn, Gilbert, Kibler, Brown, Deal (Langley). Distribution: public. 233 pages. — [NTRS 19800005879](https://ntrs.nasa.gov/citations/19800005879)
- [DIRECT] The simulation was run on the Langley Differential Maneuvering Simulator, driven by a CDC CYBER 175 with fixed 1/32 s integration. Aero data came from low-speed (M = 0.1–0.2) static and forced-oscillation tests. — [TP-1538 p. 9](https://ntrs.nasa.gov/api/citations/19800005879/downloads/19800005879.pdf)
- [DIRECT] Static aero is tabulated against α (−20° to 90°) and β (−30° to 30°). Dynamic (damping) data are tabulated at β = 0 over the same α range. The coefficient build-ups include LEF (0–25°) and speed-brake (0–60°) increments, aileron data at δa = 20°, rudder data at δr = 30°, a stabilator effectiveness factor η(δh), and a deep-stall ΔCm,ds(α, δh). Moments are referenced to 0.35 c̄. — [TP-1538 App. B pp. 37–40](https://ntrs.nasa.gov/api/citations/19800005879/downloads/19800005879.pdf)
- [DIRECT] Table III breakpoints (as printed for CX): β = −30, −25, −20, −15, −10, −8, −6, −4, −2, 0, +2 … +30°. α = −20 to 90°, in 5° steps up to 60° and then 70, 80, 90°. Separate tables are given for δh = −25° and −10° and further deflections. — [TP-1538 Table III, pp. 45–46](https://ntrs.nasa.gov/api/citations/19800005879/downloads/19800005879.pdf)
- [DIRECT] Actuators:
  - Stabilator: first-order lag 0.0495 s, rate limit 60°/s, ±25°.
  - Differential tail: 0.0495 s, 60°/s, ±5.375°.
  - Ailerons (flaperons): 0.0495 s, 80°/s, ±21.5°.
  - Rudder: 0.0495 s, 120°/s, ±30°.
  - LEF: first-order 0.136 s, 25°/s, maximum 25°.
  — [TP-1538 App. A pp. 34–35; Table I p. 43](https://ntrs.nasa.gov/api/citations/19800005879/downloads/19800005879.pdf)
- [DIRECT] Control laws:
  - Pitch: normal-acceleration-command CAS with washed-out pitch rate, filtered nz feedback and forward-loop integrator. Artificial static stability comes from α feedback.
  - α-limiter: reduces commanded g by 0.322 g/deg between α 15° and 20.4°, and by 1.322 g/deg above 20.4°, giving about 25° α in 1 g.
  - LEF schedule: δlef = 1.38·(2s+7.25)/(s+7.25)·α − 9.05·q̄/ps + 1.45.
  - Roll: roll-rate command up to 308°/s, with a departure-prevention mode above α = 29°.
  - Yaw: stability-axis yaw damper and aileron-rudder interconnect (ARI).
  — [TP-1538 App. A pp. 34–35](https://ntrs.nasa.gov/api/citations/19800005879/downloads/19800005879.pdf)
- [DIRECT] Engine:
  - Thrust is a first-order lag on throttle command, with a variable time constant and throttle gearing (Fig. 66).
  - Table VI gives Tidle, Tmil and Tmax for M 0.2–1.0 at altitudes 0–15,240 m (0–50,000 ft). At sea level and M 0.2: Tmil 56,401 N (12,680 lb) and Tmax 95,276 N (21,420 lb).
  - Engine angular momentum is fixed at 216.9 kg·m²/s (160 slug·ft²/s).
  — [TP-1538 App. B p. 40; Table VI (PDF p. 99)](https://ntrs.nasa.gov/api/citations/19800005879/downloads/19800005879.pdf)
- [DIRECT] Buffet onset is near α = 15° and rises roughly linearly with α. Its frequency content represents three primary structural modes. — [TP-1538 App. C p. 41](https://ntrs.nasa.gov/api/citations/19800005879/downloads/19800005879.pdf)
- [DIRECT] Validation status: the report is a piloted-simulation study. One evaluation pilot was a USAF test pilot and one a contractor test pilot involved in F-16 high-α flight test. The report does not present a quantitative comparison of the model against flight data. — [TP-1538 p. 9](https://ntrs.nasa.gov/api/citations/19800005879/downloads/19800005879.pdf)
- [DIRECT] Stevens & Lewis subset, as documented by NASA:
  - Data from a 16%-scale model, out of ground effect, gear up, no stores. Static data for −10° ≤ α ≤ 45° and −30° ≤ β ≤ 30°; dynamic data at β = 0.
  - Simplified by dropping second-order dependencies. For example, CY = −0.02β + 0.021(δa/20) + 0.086(δr/30) + rate terms.
  - Limits: δe ±25°, δa ±21.5°, δr ±30°.
  - Thrust tables cover h 0–50,000 ft and M 0–1 (idle/mil/max).
  - Throttle gearing: Pc = 64.94·δth for δth ≤ 0.77, else 217.38·δth − 117.38. Power-lag time constant schedule: 1/τ* = 1.0 for ΔP ≤ 25, 0.1 for ΔP ≥ 50, and 1.9 − 0.036·ΔP in between.
  — [Garza & Morelli, NASA TM-2003-212145, pp. 29–33](https://ntrs.nasa.gov/citations/20030013626)
- [DIRECT] The open-source S&L implementation (AeroBenchVV) uses a CX table at α = −10…45° (12 points, 5° steps) × δe = −24, −12, 0, 12, 24°. Its thrust tables reproduce TP-1538 Table VI values (e.g., Tmil 12,680 lb, Tmax 21,420 lb at SL, M 0.2) plus an M = 0 row. Its "air data computer" (`adc.py`) only converts V and h into Mach and q̄ using a simple atmosphere; there are no sensor errors. — [AeroBenchVVPython `cx.py`, `thrust.py`, `adc.py`](https://github.com/stanleybak/AeroBenchVVPython/tree/master/code/aerobench/lowlevel)
- [DIRECT] AeroBenchVV (Heidlauf, Collins, Bolender, Bak, ARCH 2018) carries a "Distribution A: Approved for Public Release" marking (88ABW-2020-2188), GPL-3.0. It offers both "stevens" (tables) and "morelli" (polynomial) aero options. — [AeroBenchVVPython README and `subf16_model.py`](https://github.com/stanleybak/AeroBenchVVPython)
- [DIRECT] The UMN (Balas/Russell) Simulink F-16 has a "low-fidelity" mode (S&L) and a "high-fidelity" mode using the full TP-1538 tables (α −20° to 90°, β ±30°) with the LEF implemented. Core file: `nlplant.c`. — [UMN SEC software page](https://dept.aem.umn.edu/~balas/darpa_sec/SEC.Software.html)
- [DIRECT] isrlab/F16-Model-Matlab (MIT licence) is a revised implementation of the UMN package. Its aerodynamics come from TP-1538 and its structure from S&L. — [isrlab/F16-Model-Matlab](https://github.com/isrlab/F16-Model-Matlab)
- [DIRECT] EthanJamesLew/f16-flight-dynamics (GPL-3.0) is a C++/Python implementation of the S&L 3rd-edition model, tested against AeroBenchVV. Its authors state "No claim is made about its accuracy". — [f16-flight-dynamics README](https://github.com/EthanJamesLew/f16-flight-dynamics)

### Inferences
- The S&L/AeroBenchVV F-16 is suitable for producing *kinematically plausible* trajectories at M ≤ ~0.6–0.8. Mach effects (transonic CLα and Cmα shift, wave drag) are absent and must be patched with assumptions. [ASSUMPTION — validate against T.O. performance charts or published F-16 transonic data if found]
- TP-1538 represents an early F-16 airframe. The FlightGear F-16 authors enlarged all elevator effects by 25% for the Block 15+ enlarged stabilator (see Q3). A Block 50/52 model built on TP-1538 therefore needs a [TRANSFER: early F-16 → Block 50/52] tail-effectiveness correction plus updated mass and inertia. [ASSUMPTION]

### Gaps
- The Stevens, Lewis & Johnson (3rd ed., 2015) appendix tables could not be checked page by page this session. The ranges above come from NASA's documentation of the S&L model and from S&L-derived code.
- No public F-16 dataset with Mach-dependent coefficients was found. The F-16/VISTA low-speed database by Wright Laboratory/Bihrle (α −80° to +90°, β ±30°, per a search snippet of DTIC ADA327869) could not be downloaded because DTIC blocked it.

---

## Q3. JSBSim and FlightGear F-16 and F/A-18 models: provenance, fidelity, engine model

### Takeaway
JSBSim's core F-16 (Hofman, 2001) is TP-1538/S&L-derived (α −10°…45°). It adds a few Mach tables of unstated provenance, a notional PID flight control system and a generic Aero-Matic turbine engine. The FlightGear OPRF F-16 is far richer. It uses full TP-1538 tables, an FLCS reconstructed from AFIT theses, TP-1538, TN D-8176 and a leaked/circulating Dash-1 (T.O. GR1F-16CJ-1), plus a Pilot Fault List emulation. Its engine models (F100/F110) are still generic JSBSim turbines scaled from handbook data. **JSBSim's core repository has no F/A-18.** No FlightGear F/A-18 with documented NASA provenance was found.

### Cited Findings
- [DIRECT] JSBSim `f16.xml` metadata:
  - Author Erik Hofman, created 2001-12-28, GPL. Description: "Models an F-16A Block-32 (Basic US configuration)".
  - References: William Green "General Dynamics F-16 Dash-1" (1987), NASA TP-1538, Richard Murray's Caltech F-16 page, and NASA dynamic-ground-effect reports H-1999 (F-15) and H-2177.
  - Inertias are the TP-1538 values (9,496 / 55,814 / 63,100 / −982 slug·ft²). Empty weight 17,400 lb.
  — [JSBSim f16.xml](https://github.com/JSBSim-Team/jsbsim/blob/master/aircraft/f16/f16.xml)
- [DIRECT] JSBSim F-16 fidelity details:
  - Aero tables span α −0.175…0.785 rad (−10°…45°, i.e., the S&L range). About 40 coefficient functions.
  - Only a handful of Mach tables, e.g., CDmach = 0 up to M 0.81, 0.023 at M 1.1 and 0.015 at M 1.8, plus CYβ(M) and Clβ(M).
  - FCS is notional: roll-rate, g-load and yaw PID loops.
  - Actuators are "kinematic" full-travel times (0.3 s aileron/elevator, 0.4 s rudder), not first-order lags.
  - Landing gear is spring-damper "BOGEY" contacts: nose 17,250 lb/ft and 4,250 lb/ft/s; mains 37,500 lb/ft and 7,500 lb/ft/s.
  — [JSBSim f16.xml](https://github.com/JSBSim-Team/jsbsim/blob/master/aircraft/f16/f16.xml)
- [DIRECT] The JSBSim engine `F100-PW-229.xml` was generated by Aero-Matic v0.8 with these parameters: milthrust 17,800 lbf, maxthrust 29,000 lbf, bypass ratio 0.4, TSFC 0.74, ATSFC 2.05, idle N1/N2 40/53%. It uses generic normalised idle/mil/augmented thrust tables vs Mach and density altitude. — [JSBSim engine/F100-PW-229.xml](https://github.com/JSBSim-Team/jsbsim/blob/master/engine/F100-PW-229.xml)
- [DIRECT] The JSBSim core aircraft directory includes f15, f16, f22, f104, F4N, T38 and A4, but **no F/A-18**. — [JSBSim aircraft directory](https://github.com/JSBSim-Team/jsbsim/tree/master/aircraft)
- [DIRECT] FlightGear OPRF F-16 (NikolaiVChr/f16, GPL-2.0) covers YF-16, Blocks 10, 20, 30, 32, 40, 42, 50, 52 (the default) and 60. — [NikolaiVChr/f16 README](https://github.com/NikolaiVChr/f16)
- [DIRECT] Its aero file states: "Where nothing else is mentioned the aerodynamics come from TP 1538". Block 15+ elevator effects are "25% enlarged due to enlarged hstab". TN D-8176 is used for α 50°+. Listed as missing wind-tunnel data: gear dynamics, ground effect, wave drag, TEF dynamics, stores dynamics, canopy, and "Dynamics of high speed". — [jsb-aerodynamics-block15.xml header](https://github.com/NikolaiVChr/f16/blob/master/Systems/jsb-aerodynamics-block15.xml)
- [DIRECT] Its FCS sources are AD-A055-417 ("Main source", an AFIT thesis on F-16 pitch-rate control), AD-A189-675 (Kassan 1987 AFIT SIMTACS thesis), TP-1538, TN-D-8176 (servo filters, LEF schedule), ICAS-90-5.10.2, AFSC 32657C and "T.O.GR1F-16CJ-1". The FCS includes structural notch filters: pitch band-stop about 4.75–19.08 Hz; roll band-stops at 8, 11.6 and 6.35 Hz; yaw band-stop at 5.6 Hz. Actuator rate limits are 60/80/120°/s. — [jsb-controls.xml](https://github.com/NikolaiVChr/f16/blob/master/Systems/jsb-controls.xml); thesis identification from search metadata of [DTIC ADA055417](https://apps.dtic.mil/sti/pdfs/ADA055417.pdf)
- [DIRECT] OPRF engine files cover F100-PW-200/220/229 and F110-GE-100/129/132. The F110-GE-129 file uses milthrust 17,000 lbf, maxthrust 29,000 lbf, BPR 0.76, TSFC 0.661, ATSFC 1.9, with sources "Turbofan and Turbojet Engines: Database Handbook by Elodie Roux; AeromatiC++". Its idle-thrust table is identical to the generic JSBSim table. — [Engines/F110-GE-129.xml](https://github.com/NikolaiVChr/f16/blob/master/Engines/F110-GE-129.xml)
- [DIRECT] OPRF systems:
  - The hydraulics file says it was "modified from F-15 by Richard"; JFS accumulator charging assumes 12% N2.
  - `failures.nas` implements a pilot-fault-list emulation with entries such as "FLCS AOA FAIL", "HYD A FAIL", "GEN MAIN FAIL", "EPU FAIL", "TANK LEAK", "FLCS BIT FAIL".
  - The static-pressure model is a single sensor with error-factor 0.1.
  — [jsb-hydraulics.xml](https://github.com/NikolaiVChr/f16/blob/master/Systems/jsb-hydraulics.xml); [Nasal/failures.nas](https://github.com/NikolaiVChr/f16/blob/master/Nasal/failures.nas); [Systems/f16-airdata.xml](https://github.com/NikolaiVChr/f16/blob/master/Systems/f16-airdata.xml)
- [DIRECT] Richard Harrison's FlightGear F-15 FDM is "based on the windtunnel derived aerodynamic data found in (AFIT/GAE/ENY/90D-16)". His F-14 uses AFWAL-TR-80-3141 and NASA TN D-6909. No F/A-18 data source is listed on his aerodata page. — [zaretto.com aerodata downloads](https://zaretto.com/node/23)
- [DIRECT] An unlicensed GitHub C++ F/A-18 sim (willcmc/f18-env) claims AoA coverage of −14° to +90° "based off flight data from NASA's HARV program". It is MATLAB-Coder-generated, with no licence file. — [willcmc/f18-env](https://github.com/willcmc/f18-env)

### Inferences
- Engine realism in all JSBSim/FlightGear F-16 variants is low for health-monitoring purposes. N1, N2, EGT and fuel flow come from JSBSim's generic turbine model, not F100/F110 maps. Hand engine physics to the engine researcher's models (→ cross-link). [ASSUMPTION]
- The OPRF F-16's FLCS and PFL emulation is a useful *template* for which flight-control fault discretes exist. It is still a hobby reconstruction of a restricted manual and should not be cited as authoritative. [ASSUMPTION]

### Gaps
- The FlightGear fgaddon SourceForge listing returned no content to automated fetch, so third-party FG Su-27, Mirage 2000 and Gripen models could not be inventoried.
- The legal status of the "T.O. GR1F-16CJ-1" copy used by OPRF is unknown (see Q8).

---

## Q4. NASA F/A-18 and HARV aerodynamic model and simulation: report numbers, content, and database availability

### Takeaway
The F/A-18 has the best-documented public simulation of any candidate. NASA TM-107601 (f18bas) and TM-110216 (f18harv) document:
- an MDC-derived database (α −10°…90°, β ±20°, M 0–2);
- actuator nonlinearities;
- the 8.3.3 CAS control laws;
- an F404 engine model with seven output variables;
- detailed AoA-probe, air-data, INS, accelerometer and gyro models with real sample rates.

Flight-identified stability and control derivatives (α 3°…70°, subsonic) are published by Iliff & Wang and by Napolitano. Caveat: the numerical aero and engine tables live in the ACSL/FORTRAN code, which in 1992 "can be obtained from the authors". No current public download of the f18harv code or database was found.

### Cited Findings
- [DIRECT] TM-107601 (Buttrill, Arbuckle, Hoffler, July 1992):
  - f18bas is written in ACSL. Aero comes from MDC reports A7247 vols 1–2 and the MDC batch simulation `mdcf18`; MDC A8575 holds the wind-tunnel and propulsion history.
  - Includes a simplified FCS v8.3.3 Auto-Flap-Up CAS (longitudinal, lateral, directional).
  - "The source code can be obtained from the authors."
  — [NTRS 19920024293](https://ntrs.nasa.gov/citations/19920024293); [PDF §1.2, §5.1](https://ntrs.nasa.gov/api/citations/19920024293/downloads/19920024293.pdf)
- [DIRECT] Reference geometry and mass:
  - S = 400 ft², c̄ = 11.523 ft, b = 37.42 ft.
  - Default weight 33,310 lb at CG FS 455.0 / WL 102.8 in. Ixx 23,000, Iyy 151,293, Izz 169,945, Ixz −2,971 slug·ft².
  - Fighter-escort case (60% internal fuel): 31,665 lb, with Ixx/Iyy/Izz/Ixz = 22,337 / 120,293 / 138,945 / −2,430 slug·ft².
  — [TM-107601 Tables 3.4–3.5, p. 20](https://ntrs.nasa.gov/api/citations/19920024293/downloads/19920024293.pdf)
- [DIRECT] Actuators (MDC A8449 values):

  | Surface | Rate limit | Position limit | Lag time constant |
  |---|---|---|---|
  | Stabilator | ±40°/s | −24°/+10.5° | 1/30 s |
  | Rudder | ±61°/s | ±30° | 1/40 s |
  | Aileron | ±100°/s | −25°/+45° | 1/48 s |
  | TEF | ±18°/s | −8°/+45° | 1/20 s |
  | LEF | ±18°/s | −3°/+34° | 1/20 s |

  Also modelled: 12-bit DAC minimum commands (e.g., stabilator 0.0083°), hydromechanical thresholds, and a 3,000 psi supply with slew rate proportional to (Ps − Pl)^½. The speed brake runs at 24°/s over 0–60°. — [TM-107601 Tables 8.6–8.7, p. 81; §8.3](https://ntrs.nasa.gov/api/citations/19920024293/downloads/19920024293.pdf)
- [DIRECT] FCS timing: the simulation calls the FCS every 1/40 s as "a compromise between the various sampling rates of 80, 40, 20 and 10 samples per second used by the actual aircraft flight control computer". — [TM-107601 §9.2](https://ntrs.nasa.gov/api/citations/19920024293/downloads/19920024293.pdf)
- [DIRECT] f18bas sensor set (ISENS = 1, MDC models):
  - Static-pressure and impact-pressure position errors as functions of Mach and sensed α.
  - AoA probe: bias 1.9° gear-up and 1.2° gear-down, gain a function of Mach, output limited to −14°…56°, lever arm 24 ft.
  - Accelerometers at FS 306.75 / BL 10.5 / WL 91.3 in, with lever-arm correction. Hysteresis, bias, quantisation and misalignment are *not* modelled.
  - Rate gyros with output limits.
  — [TM-107601 §7.1–7.5, pp. 61–66](https://ntrs.nasa.gov/api/citations/19920024293/downloads/19920024293.pdf)
- [DIRECT] TM-110216 (Messina, Strickland, Hoffler, Carzoo, Bundick, Yeager, Beissner, May 1996), f18harv:
  - Aero database covers α −10°…90°, β ±20°, M 0.0–2.0, h 0–60,000 ft.
  - The DFRC batch simulation was treated as the "truth model" because considerable work compared it with HIL and flight results. f18harv's actuator, sensor and engine models were replaced with the DFRC ones.
  — [NTRS 19960027892](https://ntrs.nasa.gov/citations/19960027892); [PDF §1.0–1.2](https://ntrs.nasa.gov/api/citations/19960027892/downloads/19960027892.pdf)
- [DIRECT] HARV mass properties:

  | Configuration | Weight (lb) | Ixx | Iyy | Izz | Ixz |
  |---|---|---|---|---|---|
  | Light | 31,617.7 | 22,163.0 | 172,237.5 | 186,823.1 | −2,043.1 |
  | Heavy | 37,618.7 | 22,938.3 | 179,130.1 | 194,003.0 | −2,507.3 |
  | Empty | 29,615.0 | — | — | — | — |

  Inertias in slug·ft². — [TM-110216 Table 2.3, p. 12](https://ntrs.nasa.gov/api/citations/19960027892/downloads/19960027892.pdf)
- [DIRECT] HARV F404 engine model (from DFRC FORTRAN/Ada):
  - Steady-state table look-up of nozzle area, drag, gross thrust, nozzle pressure ratio, turbine discharge pressure, ram drag and fuel flow, at idle, MIL, min A/B and max A/B. Windmill drag is a separate table.
  - Grid: 12 Mach points (0–1.8) × 7 altitudes (0–50 kft).
  - Engine dynamics: first-order PLA lag with τ 0.625 s (non-A/B) and 0.55 s (A/B), rate limits 14°/s and 22°/s on increasing throttle.
  - Sample time 0.0125 s. Fuel-burn effects on mass and inertia are neglected.
  — [TM-110216 §4.1, p. 37](https://ntrs.nasa.gov/api/citations/19960027892/downloads/19960027892.pdf)
- [DIRECT] HARV sensor models:
  - AoA probe: first-order 0.073 s lag (as printed), pitch-rate upwash correction with lp = 24 ft, limited +56°/−14°. The real HARV probe was sampled at 40 Hz.
  - INS: lever-arm transfer, then 2nd-order filters (ωn 15.896 rad/s, ζ 0.707 on body rates; ωn 34.557 rad/s, ζ 0.707 on accelerations), updated at 40 Hz. Note: the prose says "5 Hz" for rates and "2.5 Hz" for accelerations, which is inconsistent with the equations.
  - Mission Computer inertial AoA/β algorithm: used when α_probe exceeds 30°. Wind estimate filter τ = 0.8 s (non-manoeuvring) or 20 s (manoeuvring).
  - MIL-STD-1553 bus delays are not modelled.
  — [TM-110216 §5.2, pp. 70–76](https://ntrs.nasa.gov/api/citations/19960027892/downloads/19960027892.pdf)
- [DIRECT] ANSER aero increments were built from wind-tunnel tests: 6% model at DTRC, 16% at LaRC 30×60, full-scale at Ames 80×120, forced-oscillation and 10% rotary-balance tests. — [TM-110216 §3.3, p. 23](https://ntrs.nasa.gov/api/citations/19960027892/downloads/19960027892.pdf)
- [DIRECT] Flight-identified derivatives:
  - HARV longitudinal: α 10°–60°, maximum-likelihood with state noise. NASA/TP-97-206539.
  - HARV lateral-directional: α 10°–70°, compared with basic F-18 and predicted values. NASA/TP-1999-206573. Some HARV fairings were adjusted using basic-F-18 derivatives.
  - Basic F-18 lateral-directional at high α: Feb 1997.
  - WVU/Napolitano HARV set: α 10°–60° (NCC 2-759).
  — [TP-97-206539](https://ntrs.nasa.gov/citations/19980007172); [TP-1999-206573](https://ntrs.nasa.gov/citations/19990019364); [Iliff & Wang 1997, basic F-18](https://ntrs.nasa.gov/citations/19970010502); [Napolitano & Spagnuolo 1993](https://ntrs.nasa.gov/citations/19940020331)
- [DIRECT] Other related NASA work: Hall (1991) documents linearisation of the tabular nonlinear F18 HARV sim. Messina (1995) used the HARV sim aero model to extract strake increments from flight. — [Hall 1991](https://ntrs.nasa.gov/citations/19920004624); [Messina 1995](https://ntrs.nasa.gov/citations/19960012499)
- [DIRECT] An open-literature F/A-18 model (UMN, Chakraborty/Seiler/Balas, JGCD 2011) uses closed-form polynomial fits to HARV flight data (Napolitano; Iliff & Wang), with mass 1,034.5 slug and the TM-107601 inertias. It neglects actuator dynamics and reproduces the falling-leaf mode. — [Chakraborty et al. 2011 (UMN PDF)](https://dept.aem.umn.edu/~SeilerControl/Papers/2011/ChakrabortyEtAl_11JGCD_NonlinearF18Analysis.pdf)

### Inferences
- Even without the f18harv code, the published TMs plus flight derivatives and polynomial models are enough to build an F/A-18 model whose structure (actuator limits, sensor errors, FCS sample rates) is [DIRECT]. Coefficient values outside the published derivative plots would have to be reconstructed. [ASSUMPTION — validate by requesting f18harv/f18bas source through NASA software release (software.nasa.gov) or the authors' successors]

### Gaps
- Current public availability of the f18bas/f18harv code and database (MDC-derived tables) is unconfirmed. TM-107601 points only to "the authors" (1992).
- MDC reports A7247, A7813, A8449 and A8575 are cited but are not publicly available as far as found.

---

## Q5. FOI ADMIRE (and Saab GAM), GARTEUR HIRM, NASA generic fighter models

### Takeaway
ADMIRE is a **complete, freely distributed, but generic** single-engine delta-canard fighter in MATLAB/Simulink. It has aero, mass/CG/inertia, engine, actuators, sensors, FCS, and trim/linearisation tools. Its aero comes from Saab's GAM ("not unlike JAS 39 Gripen"), extended to α 90° longitudinally. It is the best public *Gripen-class/Tejas-class configuration proxy*, but it is not Gripen data and it is not flight-validated. HIRM (DERA/GARTEUR) has the widest α/β data but is distributed by permission only. NASA's Garza-Morelli collection provides public bare-airframe models of several fighters.

### Cited Findings
- [DIRECT] Versions and documentation:
  - Development began in 1997. Release 4.1 dates from 2006.
  - Documentation: Forssell & Nilsson, "ADMIRE … Version 4.0, Model Description", FOI-R--1624--SE (2005); Vooren, "Expanding ADMIRE's Aerodynamic Envelope for High Angles of Attack", FOI-R--0771--SE (2002); Hagström, "The ADMIRE Benchmark Aircraft Model", in Springer LNCIS 365 (2007).
  — [DGLR 2024 paper (Geiser, Logothetis, Birkenseer), §2 and refs 4–6](https://www.dglr.de/publikationen/2024/630061.pdf); [Springer LNCIS 365](https://link.springer.com/10.1007/978-3-540-73719-3)
- [DIRECT] ADMIRE 3.4h (2003), maintained by FOI:
  - Aero based on GAM (Saab AB, Backström 1997) and extended for high α.
  - Control surfaces: canards, LEFs, inboard/outboard elevons, rudder, plus thrust vectoring (thrust-vectoring "lack of documentation" noted).
  - Actuators: first-order τ = 0.05 s (20 rad/s bandwidth).
  - Limits below M 0.5: canards −55°/+25° at 50°/s; elevons ±30° at 150°/s; rudder ±30° at 100°/s.
  - Envelope: M ≤ 1.2, h ≤ 6,000 m. Longitudinal aero to α 90°; lateral aero only to α 30°.
  — [Härkegård PhD-820, §2.4 and Table 2.4, pp. 21–22](https://www.control.isy.liu.se/research/reports/Ph.D.Thesis/PhD820.pdf)
- [DIRECT] Original GAM data covered only −10° ≤ α ≤ 30° and −20° ≤ β ≤ 20°. GAM/ADMIRE was listed as "Publicly available: Yes", downloadable from KTH. Comparison table: HIRM "Not in general"; FDC toolbox (non-fighter) "Yes". — [Härkegård Lic-875, §7.1, pp. 87–88 and ref [64]](https://www.rt.isy.liu.se/research/reports/LicentiateThesis/Lic875.pdf)
- [DIRECT] Mass and geometry:

  | Model | Mass (kg) | Ix | Iy | Iz | Ixz | S (m²) | b (m) | c̄ (m) |
  |---|---|---|---|---|---|---|---|---|
  | ADMIRE/GAM | 9,100 | 21,000 | 81,000 | 101,000 | 2,500 | 45 | 10 | 5.2 |
  | HIRM | 15,296 | — | 163,280 | — | — | 37.16 | 11.4 | 3.511 |

  Inertias in kg·m². — [Lic-875 App. 7.A, p. 100](https://www.rt.isy.liu.se/research/reports/LicentiateThesis/Lic875.pdf); [DGLR 2024 Tab. 1](https://www.dglr.de/publikationen/2024/630061.pdf)
- [DIRECT] ADMIRE FCS behaviour:
  - Longitudinal stick commands pitch rate, lateral stick commands roll rate, and pedals command sideslip.
  - Gains are scheduled over Mach and altitude down to M 0.22 at 66 ft.
  - There is no aerodynamic ground-effect model, so landings need an artificial flare.
  — [DGLR 2024 §2](https://www.dglr.de/publikationen/2024/630061.pdf)
- [DIRECT] ADMIRE "is a freely and publicly available advanced simulation model of a generic fighter aircraft … The model incorporates actuator and sensor models … includes trim and linearisation routines". — [Ameho & Prempain, ACC 2011](https://skoge.folk.ntnu.no/prost/proceedings/acc11/data/papers/0904.pdf)
- [DIRECT] ADMIRE has dynamic models of "an engine, actuators, atmosphere, and sensors" and 12 states. One chapter attributes it to "The Aeronautical Research Institute of Sweden" (FFA, an FOI predecessor). — [Kemer, Başak, Özmen, IntechOpen 2022](https://www.intechopen.com/chapters/83768)
- [DIRECT] HIRM (DERA, UK):
  - Built from wind-tunnel and drop tests of a small-scale model, scaled up "to create an aircraft of F-18 proportions".
  - Data cover −50° ≤ α ≤ 120° and −50° ≤ β ≤ 50°.
  - Used as the GARTEUR robust flight control design challenge benchmark. Use required DERA permission.
  — [Härkegård Lic-875 §7.1.2](https://www.rt.isy.liu.se/research/reports/LicentiateThesis/Lic875.pdf)
- [DIRECT] NASA Garza & Morelli collection (TM-2003-212145, software LAR-17463-1):
  - Aircraft: F-16, F-106B, F-14 (α −5°…50°, β ±20°, M 0–1), F-4, X-31 (α −5°…55°, β ±18°), A-7, FASER, HL-20. All are bare-airframe.
  - "For many of the simulated aircraft, engine data was not available … the engine model for the F-16 aircraft was used, and the output thrust was scaled". This includes the X-31's F404.
  — [NTRS 20030013626, pp. 6, 29–60](https://ntrs.nasa.gov/citations/20030013626); [NASA software LAR-17463-1](https://software.nasa.gov/software/LAR-17463-1)
- [DIRECT] Other NASA generic and fighter-adjacent data:
  - Hoffler, Fears & Carzoo (1997) define a generic airplane model concept with four specific models for piloted simulation.
  - F-16XL wind-tunnel static and oscillatory data (10% and 18% models, α 20–60°) are public.
  — [NTRS 19970017364](https://ntrs.nasa.gov/citations/19970017364); [F-16XL longitudinal](https://ntrs.nasa.gov/citations/19980007406); [F-16XL lateral](https://ntrs.nasa.gov/citations/20040110955)

### Inferences
- [TRANSFER: ADMIRE → Gripen C/D / Tejas Mk1A] ADMIRE matches both in class: single engine, delta planform, about 9 t mass (Tejas gross 9,800 kg; ADMIRE 9,100 kg). Wing areas differ (45 m² vs Tejas 38.4 m²), and ADMIRE has canards where Tejas is tailless with elevons only. It is therefore a *configuration-class* proxy, not a type proxy. [ASSUMPTION — validate by comparing ADMIRE trimmed α/δ vs published Tejas manoeuvre limits]
- ADMIRE's freely distributable status makes it the lowest legal-risk "complete aircraft" for a hackathon deliverable. Its current download location must be confirmed. [ASSUMPTION]

### Gaps
- The ADMIRE engine model (thrust law; any RM12/F404 basis) and sensor-model parameters were not read. The FOI-R--1624--SE PDF was not retrieved, and https://www.foi.se/admire returned 404 on 2026-10-13.
- Current ADMIRE licence terms and download URL are unverified.
- The GARTEUR HIRM technical description and the AIAA Controls Design Challenge model (Brumbaugh, NASA CR-186019) were not retrieved.

---

## Q6. HAL Tejas: NAL/ADA system-identification derivatives, aero and mass data

### Takeaway
What is public: architecture (NAL CLAW-team control laws, quadruplex digital FBW, fail-op ADS), headline specs, AoA clearance limits and engine rating. No Tejas aero coefficient tables, derivative estimates, inertia data or actuator data were found in the sources reachable this session. A Tejas model therefore requires [TRANSFER] for aero (ADMIRE or F-16 class), engine (F404-GE-400 → IN20) and sensor/FCS structure (F/A-18).

### Cited Findings
- [DIRECT] Tejas uses a NAL-developed full-authority quadruplex digital FBW, needed for relaxed static stability. ADA chose this over a Dassault-proposed triplex-digital-plus-analog design. NAL's CLAW team developed the control laws, tested on an Iron Bird with over 50 hours of pilot testing. (Wikipedia cites Rajkumar, *Tejas Story*, 2007.) — [Wikipedia: HAL Tejas, refs 36, 39](https://en.wikipedia.org/wiki/HAL_Tejas)
- [DIRECT] The DFCC was developed by ADE and manufactured by BEL. An indigenous quadruplex PowerPC-based DFCC (DO-178C level A claim) flew on LSP-7 on 19 Feb 2024. A DRDO type-approval document for the DFCC is listed. — [Wikipedia: HAL Tejas, refs 148–149, 169–171](https://en.wikipedia.org/wiki/HAL_Tejas); [DRDO TA-1569 (as cited by Wikipedia)](https://www.drdo.gov.in/sites/default/files/2021-10/TA-1569.PDF)
- [DIRECT] AoA limit was 24° at IOC-II and expanded to 28° at FOC. — [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas)
- [DIRECT] ADA facilities: Iron Bird, Engineering-in-Loop Simulator, Mini-Bird, Real-Time Simulator, air data test station. FCC and ADS are described as "fail operational, fail safe". — [ADA IFCS](https://www.ada.gov.in/images/ifcs.htm)
- [DIRECT] ADA's aerodynamics directorate lists wind-tunnel model testing, CFD and "flight data analysis to evaluate aerodynamic, engine, and aircraft performance". No data are published there. — [ADA Aerodynamics & Performance](https://www.ada.gov.in/images/ard2.htm)
- [DIRECT] Wikipedia's Tejas reference list contains no Defence Science Journal, NAL or AIAA technical papers on Tejas aerodynamics or system identification. — [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas)

### Inferences
- [TRANSFER: F/A-18 F404-GE-400 model (TM-110216) → Tejas F404-GE-IN20] Same engine family. Scale the idle/MIL/AB thrust to IN20's 85 kN (Wikipedia). The 7-variable structure (fuel flow, NPR, TDP, nozzle area) and PLA lag/rate limits carry over. Limit: IN20 has different fan/core and FADEC schedules, and the inlet is single and side-mounted. → cross-link to the engine researcher.
- [TRANSFER: F/A-18 quad FCS → Tejas quad DFBW] Channelised failure discretes (CH1–CH4) and 80/40/20/10 Hz rate groups are plausible templates for a quadruplex FBW. Tejas actual rates are unknown. [ASSUMPTION]

### Gaps
- NAL flight-data system-identification reports and Defence Science Journal papers on LCA derivative estimation could not be located. The search budget was exhausted, and nal-ir.nal.res.in did not resolve on 2026-10-13. Next step: search the DSJ archive (publications.drdo.gov.in) and the NAL IR for "LCA parameter estimation", "flight path reconstruction LCA", and the Girija/Raol/Singh/Kamali/Pashilkar NAL authors. This is an unverified lead from domain knowledge and is not reported as fact.
- Tejas inertias, CG range, actuator rate limits, sensor sample rates and FCS iteration rates were not found publicly.

---

## Q7. Su-27/Su-30: aerodynamic datasets in Russian, Chinese or academic literature

### Takeaway
No public tabular Su-27/Su-30 aerodynamic dataset was verified this session. Public material is limited to design-philosophy statements (e.g., 3–5% MAC subsonic longitudinal instability), headline specs, FBW redundancy, and AL-31FP thrust and nozzle geometry. The Su-30MKI is the most India-relevant twin-engine type but the least modellable from public data.

### Cited Findings
- [DIRECT] The Su-27 had the Soviet Union's first operational FBW. The design aimed for "longitudinal instability of 3-5% mean aerodynamic chord" subsonic. — [Wikipedia: Su-27 (ref [8])](https://en.wikipedia.org/wiki/Sukhoi_Su-27)
- [DIRECT] Su-30MKI:
  - FBW "with quadruple redundancy" (uncited). AL-31FP at 123 kN with afterburner. TVC ±15° in one plane, nozzles canted 32° outward.
  - Reported engine-related failures: 69 between late 2012 and early 2015 (Defence Minister's statement), mainly bearing fatigue and low oil pressure.
  - MTBO 1,000 h and life 3,000 h (uncited).
  — [Wikipedia: Su-30MKI (ref [109], [110])](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI)

### Inferences
- A Su-30MKI virtual fighter would need [TRANSFER: F/A-18 (twin engine, twin tail, LEX) or HIRM ("F-18 proportions")] for aero, plus thrust-vectoring logic. The [TRANSFER] limits are large: Su-27 has an integral body, canards (MKI), and three-surface/TVC control. [ASSUMPTION]

### Gaps
- Unverified leads, to search in a fresh session:
  - TsAGI-published high-α data (Goman/Khrabrov unsteady-aero work) and the Russian monograph on supersonic-aircraft aerodynamics edited by G.S. Byushgens.
  - Chinese journal papers modelling "Su-27-class" fighters.
  - English translations of the Su-27 flight manual (RLE).
  These come from domain knowledge only and have no source this session.

---

## Q8. Public flight manuals and performance documents (F-16 Dash-1, F/A-18 NATOPS, Su-27 manual): content and legal status

### Takeaway
Two public models visibly rely on F-16 manuals. JSBSim cites a "General Dynamics F-16 Dash-1" (William Green, 1987), and FlightGear OPRF cites "T.O. GR1F-16CJ-1" for LEF/TEF logic, CAT I/III schedules, trim and standby gains. Copies therefore circulate, but their distribution status could not be verified this session. Treat them as **restricted-distribution technical orders** unless a public-release statement is found. Do not ingest them into a Ministry-of-Defence-facing deliverable without that check.

### Cited Findings
- [DIRECT] JSBSim F-16 references "General Dynamics F-16 Dash-1" (William Green, 1987, ISBN listed as 0-7232-3458-2). — [JSBSim f16.xml fileheader](https://github.com/JSBSim-Team/jsbsim/blob/master/aircraft/f16/f16.xml)
- [DIRECT] OPRF F-16 FCS file lists "T.O.GR1F-16CJ-1" as the source for LEF and TEF conditions, CAT I and III schedules, trim, standby gains and the gear-up condition. It cites specific pages (e.g., "GR1F-16CJ-1 page 1-120, 1-135, 1-137"). — [NikolaiVChr/f16 jsb-controls.xml](https://github.com/NikolaiVChr/f16/blob/master/Systems/jsb-controls.xml)
- [DIRECT] OPRF also cites "The Israeli document" for certain FCS values (provenance unstated). — [jsb-controls.xml](https://github.com/NikolaiVChr/f16/blob/master/Systems/jsb-controls.xml)
- [DIRECT] Public, citable FBW descriptions that avoid the manuals: Droste & Walker (1980), "The General Dynamics Case Study on the F-16 Fly-by-Wire Flight Control System" (AIAA), cited by Wikipedia for quadruplex FLCS, limiters and graceful degradation. — [Wikipedia: F-16 refs 84–92](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon)

### Inferences
- [ASSUMPTION — validate by reading the cover/distribution-statement page of any copy before use] USAF T.O. 1F-16x-1 and USN NATOPS A1-F18AC-NFM-000 normally carry restrictive distribution statements and export-control notices. Typical contents are operating limits, performance charts, systems descriptions, caution/warning/advisory lists, PFL/MFL (F-16) and engine operating limits. Those are exactly what a fault-list layer needs. → cross-link to faults/degradation and maintenance-records researchers.

### Gaps
- None of the following was verified this session: the exact distribution statement of any F-16 Dash-1 or F/A-18 NATOPS revision; whether any revision was released via FOIA or approved for public release; the status of Su-27 manual translations. Repeat the search with "distribution statement" plus the T.O. number.

---

## Q9. Public flight-test datasets and time histories (HARV, AFTI/F-16, F-16XL, X-29, X-31, F-15)

### Takeaway
NASA reports provide **plotted** time histories, identified derivatives and, critically, a **real F/A-18 telemetry parameter catalogue with recording rates** (CR-201670). No public raw-data download was found for any of these programmes. HARV data moved between Dryden and Langley by internal FTP in `cmp3` format.

### Cited Findings
- [DIRECT] HARV instrumentation:
  - Three-axis accelerometers, attitude and rate gyros, surface position transducers and redundant air data.
  - Production AoA sensors were valid only to about 35° AoA, so AoA, AoA rate, β and β rate were computed in the mission computer from INS data. High-α air data came from wingtip swivelling pitot probes with α/β vanes and from a flush air data system on the nose.
  - Telemetry: two asynchronous PCM encoders with 10-bit words, up to 2,000 parameters, and rates up to 2,142 Hz on selected signals. PID data were thinned to 40 Hz and corrected for CG offset, upwash, sidewash, boom bending and sensor and filter lags.
  - Engines had a real-time thrust measurement system. The right engine carried 63 inlet pressure sensors and a 40-probe high-response rake.
  — [Iliff & Wang TP-97-206539, pp. 13–14](https://ntrs.nasa.gov/api/citations/19980007172/downloads/19980007172.pdf)
- [DIRECT] CR-201670 (Yeager, March 1997), ANSER flights July 1995–May 1996:
  - About 2,000 parameters were telemetered and stored at DFRC.
  - Retrieval used GetFdas, GetData and Xplot, with `arm_xxx.cmp3`, `Rxxxy.cmp3` and `Pxxxy.cmp3` files moved by FTP to LaRC.
  - Appendix A lists available raw parameters for Flight 295 (7-11-95) with recording rates.
  — [NTRS 19970014822](https://ntrs.nasa.gov/citations/19970014822); [PDF App. A](https://ntrs.nasa.gov/api/citations/19970014822/downloads/19970014822.pdf)
- [DIRECT] CR-201670 Appendix A, examples by recording rate:
  - **160 Hz**: angular accelerations; L/R boom AoA and sideslip; CG accelerations; stabilator positions; lateral stick force.
  - **80 Hz**: RFCS internals (AoA INS, pitch rate, Mach, impact pressure, thrust-vectoring commands).
  - **40 Hz (1553/mission computer)**:
    - Engine: L/R N1 and N2, EGT, turbine discharge pressure, compressor discharge pressure P3, main fuel flow, engine inlet temperature, oil pressure, nozzle position, PLA.
    - FCS per channel (CH1–CH4): servo fail, AOA fail, processor off, stick fail, rudder-pedal fail, "BADSA DATA FAIL", pitch/roll/yaw CAS fail, degraded.
    - Servo-amp/LVDT sum-monitor fail; hydraulic branch 1A/1B/2A/2B pressure normal.
    - Advisories/cautions: HYD 1/2 oil level low, AMAD oil low and temp high, L/R GEN OUT, anti-skid failures, bingo fuel, per-tank fuel quantities, pitot heat off.
    - INS: narrow- and wide-band body rates, platform accelerations and velocities, validity flags.
  - **320 Hz**: pressure taps. **800 Hz**: vertical-tail accelerometers. **25 Hz**: LEX/forebody pressures.
  — [CR-201670 App. A, pp. A-3 onward](https://ntrs.nasa.gov/api/citations/19970014822/downloads/19970014822.pdf)
- [DIRECT] AFTI/F-16 (Mackall, NASA TP-2857, Nov 1988):
  - Flight-crucial triplex asynchronous DFCS with a triple-redundant analog independent backup unit (IBU).
  - Sensors sampled at 64 Hz and filtered at 32 Hz; longitudinal modes iterated at 64 Hz.
  - Dual-redundant 1 MHz MIL-STD-1553B bus controlled by the fire-control computer; DFCS parameters output at 50 Hz.
  - Production F-16 quadruplex analog actuators retained.
  — [NTRS 19890014956](https://ntrs.nasa.gov/citations/19890014956); [PDF](https://ntrs.nasa.gov/api/citations/19890014956/downloads/19890014956.pdf)
- [DIRECT] HARV programme: Dryden flew the HARV April 1987 – September 1996, 385 research flights (per NASA reference page as summarised in search results). — [NASA: F-18 HARV](https://www.nasa.gov/reference/f-18-harv/)

### Inferences
- CR-201670 is the single most valuable public document for the telemetry layer's *signal dictionary and rate groups*. It shows how a real quadruplex FCS, F404 engines, INS and utility systems appear on a fighter's bus and instrumentation stream. → cross-link to the data-pathway/format and sensor-texture researchers.

### Gaps
- No public raw time-history files were found for HARV, AFTI/F-16, F-16XL, X-29, X-31 or F-15 HIDEC/ACTIVE. Searches specific to X-29, X-31 and F-15 HIDEC/ACTIVE could not be run after the search budget ran out. NASA DASHlink is known (domain knowledge) to host airline rather than fighter data. Not verified this session.

---

## Q10. Public descriptions of sensor suites relevant to flight dynamics (air data, AoA/β, INS, FCS gyros and accelerometers, redundancy, sample rates)

### Takeaway
Only the F/A-18 has quantitative public sensor models. These cover AoA-probe bias, gain, limits and lag; position errors; accelerometer location; INS filters; 40/80 Hz rates; and quad-channel FCS fault discretes. F-16 public data give the FLCS architecture (quadruplex, analog on A/B, digital from Block 40) and AFTI DFCS sampling. All other types have architecture statements only.

### Cited Findings
- [DIRECT] F/A-18 sensor models: see the Q4 bullets ([TM-107601 §7](https://ntrs.nasa.gov/api/citations/19920024293/downloads/19920024293.pdf); [TM-110216 §5.2](https://ntrs.nasa.gov/api/citations/19960027892/downloads/19960027892.pdf)). Real channelisation (CH1–CH4) and rate groups are in [CR-201670 App. A](https://ntrs.nasa.gov/api/citations/19970014822/downloads/19970014822.pdf).
- [DIRECT] F-16: quadruplex FLCS that degrades gracefully to triplex. The FLCC "began as an analog system on the A/B variants but has been supplanted by a digital computer system beginning with the F-16C/D Block 40". Limiters on attitude, airspeed and AOA/g, with a 9 g and 25° AOA limit. — [Wikipedia: F-16 (Droste & Walker 1980; Hoh & Mitchell 1983)](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon)
- [DIRECT] AFTI/F-16 DFCS sampling at 64 Hz with 32 Hz filtering and 1553B at 1 MHz. — [NASA TP-2857](https://ntrs.nasa.gov/citations/19890014956)
- [DIRECT] Gripen: "triplex, digital fly-by-wire" with mechanical backup for the throttle. The 1989 prototype crash was PIO from the FCS pitch-control routine; the 1993 crash involved "high amplification" of quick stick inputs. — [Wikipedia: JAS 39 Gripen](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen)
- [DIRECT] Other types:
  - Tejas: quadruplex digital FBW; ADS fail-op/fail-safe. — [ADA IFCS](https://www.ada.gov.in/images/ifcs.htm)
  - Su-30MKI: quadruple-redundancy FBW; RLG INS + Sigma-95 GPS. — [Wikipedia: Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI)
  - Mirage 2000: four analog computers. — [Wikipedia: Mirage 2000](https://en.wikipedia.org/wiki/Dassault_Mirage_2000)
  - Eurofighter: quadruplex digital. — [Wikipedia: Typhoon](https://en.wikipedia.org/wiki/Eurofighter_Typhoon)
  - Rafale: digital FBW. — [Wikipedia: Rafale](https://en.wikipedia.org/wiki/Dassault_Rafale)

### Inferences
- [TRANSFER: F/A-18 → any quadruplex-FBW candidate] The F/A-18 sensor-error structure is the best public starting point for the sensor residual layer: probe bias and Mach-dependent gain, probe saturation, position error vs Mach and α, INS filter bandwidths, and the MC inertial-α takeover above 30°. → cross-link to the sensor residual texture researcher.

### Gaps
- No public numbers were found for F-16 production FLCS sensor sample rates or rate-gyro/accelerometer redundancy counts (beyond "quadruplex"), nor for Tejas or Su-30 sensor rates.

---

## Q11. Synthesis: which candidate can be modelled most faithfully, and where proxies are unavoidable

### Takeaway
On public evidence, the **F/A-18 A-D (HARV-anchored)** is the most faithfully modellable real fighter overall. The **F-16** is a close second for airframe aero at low speed, with the strongest open-source code ecosystem. **ADMIRE** is the most *complete and freely usable* model but is generic. **Tejas and Su-30MKI** score highest on India relevance but lowest on public modelling data. A defensible plan is a two-tier approach: an F404-family, F/A-18-anchored physics core, used either as the named target or as the documented proxy source for a "Tejas-Mk1A-representative" virtual fighter.

### Cited Findings
Score justifications, keyed to the rubric in (b):
- **F/A-18 aero = 4**: database with α −10…90°, β ±20°, M 0–2 is documented ([TM-110216](https://ntrs.nasa.gov/citations/19960027892)) and flight-identified derivatives are published ([TP-97-206539](https://ntrs.nasa.gov/citations/19980007172), [TP-1999-206573](https://ntrs.nasa.gov/citations/19990019364)). Not 5 because the numerical tables sit in non-public code ([TM-107601](https://ntrs.nasa.gov/citations/19920024293)).
- **F/A-18 sensors = 5**: quantified probe, air-data and INS models ([TM-110216 §5.2](https://ntrs.nasa.gov/api/citations/19960027892/downloads/19960027892.pdf)) plus the real parameter catalogue with rates ([CR-201670](https://ntrs.nasa.gov/citations/19970014822)).
- **F/A-18 engine = 4**: F404 7-variable model structure with lag and rate limits ([TM-110216 §4.1](https://ntrs.nasa.gov/api/citations/19960027892/downloads/19960027892.pdf)); recorded N1, N2, EGT, TDP, P3 and fuel flow ([CR-201670](https://ntrs.nasa.gov/citations/19970014822)).
- **F/A-18 flight data = 3**: rich reports and parameter lists, no public raw files.
- **F-16 aero = 4**: full printed tables but low-speed only ([TP-1538](https://ntrs.nasa.gov/citations/19800005879)).
- **F-16 engine = 3**: TP-1538/S&L thrust tables and lag ([TM-2003-212145](https://ntrs.nasa.gov/citations/20030013626)); generic JSBSim turbines ([F100-PW-229.xml](https://github.com/JSBSim-Team/jsbsim/blob/master/engine/F100-PW-229.xml)).
- **F-16 sensors = 3**: AFTI DFCS rates ([TP-2857](https://ntrs.nasa.gov/citations/19890014956)) and architecture statements.
- **F-16 flight data = 2**: no comparable public parameter catalogue found.
- **ADMIRE aero = 4 / realism caveat**: complete package, M ≤ 1.2, α to 90° longitudinal ([Härkegård PhD-820](https://www.control.isy.liu.se/research/reports/Ph.D.Thesis/PhD820.pdf)), but generic. Scored 2 when used *as Gripen* ([TRANSFER]).
- **Tejas aero = 1, sensors = 1**: only specs and architecture are public ([ADA](https://www.ada.gov.in/images/ifcs.htm); [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas)). Engine = 2 via [TRANSFER] from F404-GE-400.
- **Su-30MKI**: headline data only ([Wikipedia](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI)). India relevance 5 (about 260–272 in IAF per Wikipedia). PHM = 2 because engine-failure statistics are public.
- **Relevance to India**: Tejas and Su-30MKI are IAF mainstays; the IAF operates 51 upgraded Mirage 2000s ([Wikipedia Mirage 2000](https://en.wikipedia.org/wiki/Dassault_Mirage_2000)) and the Rafale. The F/A-18 and Gripen gain 2 points through F404/RM12 engine commonality with Tejas Mk1/1A ([Wikipedia Gripen: RM12 "licence-built derivative of the General Electric F404-400"](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen); [Wikipedia Tejas: F404-IN20](https://en.wikipedia.org/wiki/HAL_Tejas)).
- **Maintenance/PHM scores are [ASSUMPTION]**. They reflect the expected volume of open literature (USN/RAAF/CF-18 F404 and structural fatigue programmes; USAF F-16 engine monitoring) and were not verified this session. → defer to the maintenance-records and faults researchers.

### Inferences
- The project should not claim "exact mechanics" for Tejas or Su-30MKI. It can claim "documented-physics proxies with India-relevant parameterisation". [ASSUMPTION]

### Gaps
- See (c) below.

### (a) Key findings summary
1. **F-16 (TP-1538 lineage)**:
   - Fully printed nonlinear low-speed tables: α −20…90°, β ±30°, M 0.1–0.2 test data, no Mach or aeroelastic effects.
   - Mass and inertia: 20,500 lb; 9,496 / 55,814 / 63,100 / 982 slug·ft².
   - Actuators: 0.0495 s lags, 60/80/120°/s.
   - g-command CAS, α-limiter, LEF schedule, and idle/MIL/MAX thrust tables (0–50 kft, M 0.2–1.0) with a power lag.
   - S&L, AeroBenchVV, UMN/isrlab and JSBSim all derive from it. FlightGear OPRF adds a reconstructed FLCS and PFL but only a generic engine.
   - It is the pre-Block 15 airframe, so Block 50/52 needs tail, mass and engine corrections.
2. **F/A-18 A-D (NASA f18bas/f18harv + HARV flight tests)**:
   - Documented database: α −10…90°, β ±20°, M 0–2, 0–60 kft.
   - Actuator rate/position/lag and 12-bit DAC nonlinearities; FCS v8.3.3 CAS; FCC rate groups 80/40/20/10 Hz.
   - F404 7-variable engine model.
   - Quantified AoA-probe, air-data and INS models.
   - Flight-identified derivatives (α 3–70°).
   - A real telemetry parameter catalogue (about 2,000 params; 25–800 Hz groups; per-channel FCS fault discretes; N1, N2, EGT, TDP, P3, fuel flow).
   - Weakness: numerical tables live in NASA code (1992: "obtain from authors"), and there is no public raw flight data.
3. **ADMIRE (FOI) / GAM (Saab)**:
   - A complete, freely distributed generic delta-canard single-engine fighter: 9,100 kg; S 45 m²; M ≤ 1.2; h ≤ 6 km; α to 90° longitudinal / 30° lateral.
   - Actuators τ 0.05 s; canard 50°/s, elevon 150°/s, rudder 100°/s.
   - Includes FCS, engine and sensors; no ground effect.
   - The best legal-risk-free proxy for a Gripen/Tejas-class airframe, but not type data.
4. **HIRM**: α −50…120°, β ±50°, at "F-18 proportions"; access by permission.
5. **Tejas, Su-27/30, Mirage 2000, Rafale, Eurofighter**: only headline specs, FBW architecture and engine ratings were found. No coefficient tables, inertia, actuator or sensor-rate data.
6. **Manuals**: F-16 Dash-1 copies (e.g., "T.O. GR1F-16CJ-1") are demonstrably circulating and used by hobby sims. Their public-release status is unverified; treat them as restricted.

### (b) Rubric table and ranked recommendation

Scores are 0–5 per criterion. Totals are unweighted, out of 35. Tags show the evidence basis of each row.

| Candidate | Aero data | Systems doc (FCS/actuators/utility) | Engine data (sim-level) | Sensor/avionics doc | Flight-data availability | Maint./PHM literature* | Relevance to India | Total |
|---|---|---|---|---|---|---|---|---|
| **F/A-18 A-D (incl. HARV)** [DIRECT] | 4 | 4 | 4 | 5 | 3 | 4* | 2 (F404 commonality with Tejas) | **26** |
| **F-16 A/C (Blk 50/52 via correction)** [DIRECT/TRANSFER] | 4 (low-speed only; Blk50 tail needs [TRANSFER]) | 3 | 3 | 3 | 2 | 4* | 1 | **20** |
| **ADMIRE (generic research fighter, as itself)** [DIRECT] | 4 (complete but generic) | 3 | 3 | 3 | 0 | 0 | 2 (Tejas-class proxy) | **15** |
| **Gripen C/D (via ADMIRE/GAM)** [TRANSFER] | 2 | 2 | 2 (RM12 ← F404 transfer) | 2 | 0 | 1* | 2 (MRFA candidate; F404 family)* | **11** |
| **HAL Tejas Mk1/1A** [DIRECT specs + TRANSFER physics] | 1 | 1 | 2 (F404-GE-400 → IN20 transfer) | 1 | 1* (NAL SysID work unverified) | 1* | 5 | **12** |
| **Su-27/Su-30MKI** [DIRECT headline] | 1 | 2* | 1 | 1 | 0 | 2 | 5 | **12** |
| **Mirage 2000** [DIRECT headline] | 1* | 1 | 1 | 1 | 0 | 1* | 4 | **9** |
| **Rafale** [DIRECT headline] | 0 | 1 | 1 | 1 | 0 | 0 | 4 | **7** |
| **Eurofighter** [DIRECT headline] | 0 | 1 | 1 | 1 | 0 | 1* | 1 | **5** |
| **GARTEUR HIRM (generic)** [DIRECT, restricted] | 3 | 2 | 1 | 2 | 0 | 0 | 0 | **8** |
| **NASA Garza-Morelli collection (generic, public)** [DIRECT] | 3 | 1 | 1 (scaled F-16 engine) | 0 | 0 | 0 | 0 | **5** |

\* = [ASSUMPTION] or unverified this session: the PHM column overall, Su-27 manual availability, Mirage III/2000 academic data, MRFA status, and NAL system-identification literature. Each score can be re-validated with one targeted search of the type named in (c).

**Ranked recommendation (fidelity of "exact mechanics" from public data):**
1. **F/A-18 A-D (F404-GE-400/402).**
   - Pros: highest sensor, FCS, engine and telemetry realism; flight-validated derivatives; a real bus/instrumentation parameter dictionary; the same engine family as Tejas Mk1/1A; twin-engine L/R comparison is useful for health analytics.
   - Cons: low IAF relevance; full aero tables need NASA code access (otherwise use the published derivatives or polynomial models); restricted NATOPS.
2. **F-16 (TP-1538 + S&L + OPRF FLCS).**
   - Pros: complete printed tables and the most open-source code; PFL template.
   - Cons: low-speed aero only; early-tail airframe; generic engine; minimal public sensor data; low India relevance.
3. **ADMIRE as a "Tejas/Gripen-class" generic airframe.**
   - Pros: complete, consistent, freely distributed; single-engine delta similar to Tejas in mass.
   - Cons: canards and 45 m² wing (Tejas: tailless, 38.4 m²); not flight-validated; engine and sensor details unverified.
4. **Tejas Mk1A, only as a "representative" build:** ADMIRE or F-16 airframe proxy + F404 engine transferred from the HARV model and scaled to 85 kN IN20 + F/A-18 quadruplex FCS/sensor template + public Tejas specs (mass 6,560/9,800/13,500 kg; S 38.4 m²; AoA limit 28°; +9/−3.5 g).
5. **Su-30MKI**: high relevance but data-poor. Defer.
6. **Mirage 2000, Rafale, Eurofighter**: not recommended.

**Practical recommendation:** build the physics/telemetry core on **F/A-18-documented structures**:
- actuator nonlinearities;
- sensor-error models;
- FCS rate groups and channelised fault discretes;
- F404 engine variable set;
- CR-201670 signal catalogue and rates.

Then instantiate either (A) an "F/A-18C-class" target for maximum defensibility, or (B) a "Tejas-Mk1A-representative" target that uses those structures plus ADMIRE or F-16 aero. Option B must carry explicit proxy labelling of every [TRANSFER] parameter in the metadata. Choose B if the jury values IAF relevance over strict type fidelity. [ASSUMPTION — final choice depends on the IAF-relevance and engine researchers' findings]

### (c) Open questions / gaps
1. Is the NASA f18bas/f18harv source and database (MDC-derived tables) publicly obtainable today, for example via software.nasa.gov, Langley, or university copies? If yes, the F/A-18 aero score rises to 5.
2. ADMIRE 4.1: current download URL, licence text, and engine and sensor model descriptions (FOI-R--1624--SE).
3. Tejas: NAL/ADA system-identification reports and DSJ papers with LCA derivative estimates. Also any published inertia, CG range, actuator rates or FCS iteration rates.
4. Su-27/Su-30: any TsAGI, Chinese or academic tabular aero dataset; status of RLE (flight manual) translations.
5. Distribution statements of F-16 Dash-1 (1F-16A-1 / 1F-16C-1 / GR1F-16CJ-1) and F/A-18 NATOPS copies that circulate publicly.
6. Mach-dependent public F-16 aero (F-16/VISTA Bihrle database, DTIC ADA327869, blocked here); Block 50/52 mass and inertia.
7. Public raw flight-test files for X-29 and X-31 (F404), F-15 HIDEC/ACTIVE, F-16XL and AFTI/F-16. None were found; X-29, X-31 and F-15 were not searched after the budget ran out.
8. Maintenance/PHM literature scores (column 6) need verification by the maintenance and faults researchers.

### (d) Ranked list of most valuable sources for deep reading
1. **NASA CR-201670**, HARV ANSER flight-test data retrieval: about 2,000-parameter catalogue with rates, FCS channel fault discretes, engine and INS parameters. [NTRS 19970014822](https://ntrs.nasa.gov/citations/19970014822) (local: `research_sources/airframe_data/NASA_CR-201670_HARV_ANSER_data_retrieval.pdf`)
2. **NASA TM-110216**, f18harv simulation: engine, sensor and INS models, envelope, mass. [NTRS 19960027892](https://ntrs.nasa.gov/citations/19960027892)
3. **NASA TM-107601**, f18bas: aero build-up, actuator nonlinearities, FCS 8.3.3, sensors, mass/geometry. [NTRS 19920024293](https://ntrs.nasa.gov/citations/19920024293)
4. **NASA TP-1538**, full F-16 tables, CAS laws, actuators, thrust tables. [NTRS 19800005879](https://ntrs.nasa.gov/citations/19800005879)
5. **Iliff & Wang TP-97-206539 / TP-1999-206573**, plus the basic F-18 1997 report: flight-identified derivatives and HARV instrumentation and data processing. [19980007172](https://ntrs.nasa.gov/citations/19980007172), [19990019364](https://ntrs.nasa.gov/citations/19990019364), [19970010502](https://ntrs.nasa.gov/citations/19970010502)
6. **Härkegård PhD-820 (§2.4) and Lic-875 (§7, App. 7.A)**: ADMIRE/GAM/HIRM parameters, limits, envelope, availability. [PhD-820](https://www.control.isy.liu.se/research/reports/Ph.D.Thesis/PhD820.pdf), [Lic-875](https://www.rt.isy.liu.se/research/reports/LicentiateThesis/Lic875.pdf)
7. **FOI-R--1624--SE (ADMIRE 4.0 model description)**, not retrieved: the key document for ADMIRE engine and sensor models (cited in [DGLR 2024](https://www.dglr.de/publikationen/2024/630061.pdf)).
8. **Garza & Morelli NASA TM-2003-212145 / LAR-17463-1**: public MATLAB F-16 (S&L) and other fighter airframes; engine-lag model. [NTRS 20030013626](https://ntrs.nasa.gov/citations/20030013626)
9. **NASA TP-2857 (AFTI/F-16 DFCS)**: F-16 digital FCS sampling, 1553B, redundancy management, BIT. [NTRS 19890014956](https://ntrs.nasa.gov/citations/19890014956)
10. **FlightGear OPRF F-16 repo** (`jsb-controls.xml`, `jsb-aerodynamics-block15.xml`, `failures.nas`): reconstructed FLCS, notch filters, PFL template, list of missing data. [GitHub](https://github.com/NikolaiVChr/f16)
11. **AeroBenchVVPython / isrlab F16-Model-Matlab / UMN SEC**: ready-to-run S&L and TP-1538 implementations (public release, GPL/MIT). [AeroBenchVV](https://github.com/stanleybak/AeroBenchVVPython), [isrlab](https://github.com/isrlab/F16-Model-Matlab)
12. **Chakraborty, Seiler, Balas 2011 (JGCD)**: open polynomial F/A-18 model from HARV flight data. [PDF](https://dept.aem.umn.edu/~SeilerControl/Papers/2011/ChakrabortyEtAl_11JGCD_NonlinearF18Analysis.pdf)
13. **ADA IFCS and Aerodynamics pages; Wikipedia HAL Tejas specs/FCS**: the only public Tejas modelling anchors found. [ADA IFCS](https://www.ada.gov.in/images/ifcs.htm), [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas)
14. **F-16XL wind-tunnel oscillatory data (Klein et al.)**: unsteady-aero model identification method, transferable to delta-wing proxies. [19980007406](https://ntrs.nasa.gov/citations/19980007406), [20040110955](https://ntrs.nasa.gov/citations/20040110955)
