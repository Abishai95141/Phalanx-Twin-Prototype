# HAL Tejas (Mk1/Mk1A) airframe, aerodynamics, flight control system, air-data and inertial sensing: evidence base and recommended aero-model construction for a "Tejas-class" virtual fighter

Scope: the flight-dynamics layer of Project Phalanx. This covers geometry and mass properties, control surfaces and actuators, flight-control architecture and laws, air-data and inertial sensors, ground-reaction inputs, performance and envelope anchors, and an evaluated method for building the aero model when Tejas aero tables are not public. Engine (F404-GE-IN20) and utility systems (hydraulics, fuel, electrical, ECS, gear/brakes hardware) belong to sibling researchers. This file only touches them where they drive the flight dynamics.

**Method notes (read first)**
- **Builds on earlier notes.** These notes build on `candidate_airframe_modelling_data.md` (Q5, Q6, Q10), `indian_fleet_platform_relevance.md` (KQ4) and `modelling_methodology.md` (§2). Points already established there are not repeated in detail; they are cross-referenced instead. The main new material comes from the Defence Science Journal (DSJ), the Journal of Aerospace Sciences & Technologies (JOAST), two archived Aeronautical Society of India (AeSI) flight-test seminar papers, ADA annual reports (local OCR), the FOI ADMIRE 4.0 model description, the OpenVSP source code, the Digital DATCOM user manual and NASA reports.
- **How the literature was searched.**
  - The DSJ OAI-PMH feed was harvested in full: 4,007 records from `https://www.publicationsdrdo.in/index.php/dsj/oai`.
  - The JOAST OAI-PMH feed was harvested in full: 910 records from `https://joast.org/index.php/joast/oai`.
  - All relevant PDFs were downloaded and read, with figures rendered and read visually where the text was image-only. Local copies are in `/Users/abishaikc/Phalanx/research_sources/tejas_airframe/`: DSJ_*.pdf, JOAST_*.pdf, AeSI_FTG2004_Aero_Data.pdf, AeSI_FTG2005_HIGH_AOA_TEJAS.pdf, FOI-R--1624--SE_ADMIRE.pdf, NASA_CR-96008_Teper_1969.pdf, NASA_TN-D-3767_Polhamus.pdf, arXiv2003.06588_ICE101_envelope.pdf and VentureCenter_26Nov2017_LCA.pdf.
- **Search budget.** 34 WebSearch calls were used, within the requested share of roughly 65. Everything else was direct fetching of known URLs, journal OAI feeds and Wayback CDX listings.
- **Access failures** (nothing was worked around through search engines):
  - The NAL repository (`nal-ir.nal.res.in`) still returns NXDOMAIN, and `nal.res.in/en/node/406` returns "Access denied".
  - The NATO STO paper MP-SCI-162-14 is behind a Cloudflare block.
  - `core.ac.uk` presents an interactive challenge, so it was not used.
  - AIAA ARC returns 403. The key LCA control-law paper (Chetty, Deodhare & Misra, AIAA GNC 2002, doi 10.2514/6.2002-4649) could therefore only be cited, not read.
  - The DRDO monograph on air-data pre-flight calibration (`drdo.gov.in/.../32-preflight-calibration.pdf`) was unreachable, and the Internet Archive was intermittently offline.
  - JOAST 2025–2026 papers are behind a subscription; only their abstracts were used.
- **Restricted material.** No restricted or distribution-limited document was used. The DTIC "ADB…" ICE reports were deliberately excluded because the "B" prefix indicates limited distribution.
- **Evidence tags.**
  - **[DIRECT]** — about Tejas or LCA itself, where the source names the aircraft.
  - **[DIRECT, unnamed]** — the source does not name the aircraft, but authorship and description identify it as LCA/Tejas. Examples: ADA IFCS or NAL National Control Law Team authors describing "a typical single-engine tailless fighter with four elevons and one rudder", or a "high performance unstable delta-wing fighter". The identification evidence is given each time, and the tag should be treated as one notch below [DIRECT].
  - **[TRANSFER: X]** — taken from platform X; the reason for and limits of the transfer are stated.
  - **[ASSUMPTION]** — engineering judgement or my own derived calculation; the validation route is stated.
- **Units.** SI unless stated. Derivatives are per radian unless stated. "c̄" is the mean aerodynamic chord.

---

## Q1. Geometry and mass properties: span, area, sweeps, MAC, lengths, weights, fuel, CG, static margin, inertias

### Takeaway
Basic geometry and weights are public, although sources conflict on several of them. An ADA flight-test paper adds the planform angles: leading-edge (LE) sweeps of 50° and 62.5°, trailing edge swept 4° forward, CG about 33.5% MAC, and wing area 38.5 m².

A 2021 paper from ADA's IFCS directorate gives a full inertia tensor for a "typical single-engine tailless fighter" at about 9,000 kg, with CG at 34% MAC. This is almost certainly the Tejas simulation model.

Static instability is published only as "time to double amplitude" (minimum 0.2 s, at M0.5–0.7 and 3–8 km). From this and from NAL derivative papers, I estimate:
- Cmα ≈ +0.05/rad at low speed (about 2% MAC unstable);
- roughly 10% MAC unstable in the high-subsonic zone of maximum instability [ASSUMPTION].

MAC is not published. Planform geometry and derivative consistency both point to c̄ ≈ 5.5 m (range 5.2–5.9 m) [ASSUMPTION].

### Cited Findings
**Geometry**
- [DIRECT] Span 8.20 m, length 13.20 m, height 4.40 m. — [ADA Tejas brochure, Dec 2013, p. 2](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf); same values on the [MoD Defence Production portal, "LCA Tejas"](https://www.ddpmod.gov.in/hi/node/6843), which lists "Width: 8.2 m".
- [DIRECT] Wing area:
  - 38.4 m² — [Wikipedia: HAL Tejas spec box](https://en.wikipedia.org/wiki/HAL_Tejas), which cites ADA/DRDO/Jane's/HAL.
  - 38.5 m² — [AeSI Flight Test Seminar 2005, Wg Cdr Vikram Singh (NFTC/ADA), "An Approach to High AoA Testing of the Tejas LCA", §5, p. 2–3](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf).
  - Conflict: 0.1 m², which is immaterial.
- [DIRECT] "It consists of a pure double delta configuration with leading edge angles of 50° and 62.5° and a trailing edge forward sweep angle of 4°. The CG lies about 33.5% of MAC and the wing area is 38.5 m². The only augmentation devices are three-piece leading edge slats, which are automatically scheduled with AoA and IMN to improve L/D, delay pitch up and increase usable AoA." — [AeSI FTG 2005, §5](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)
- [DIRECT, qualitative] Which sweep is inboard. The inboard section is swept at a shallower angle than the outboard section. So the inboard sweep is 50° and the outboard 62.5°. This is consistent with a forum estimate of "~50° near root, ~63° further out". — [Hushkit, J. Smith (aerodynamicist), 2019](https://hushkit.net/2019/10/02/tejas-thoughts-on-an-unusual-wing/); [WION](https://embed.wionews.com/photos/tejas-fighter-jet-the-aerodynamic-trick-that-makes-it-incredibly-agile-1763730595351); [Bharat-Rakshak forum (low confidence)](https://forums.bharat-rakshak.com/viewtopic.php?p=1775071)
- [DIRECT] Design-intent statements on the official ADA Tejas site, archived:
  - "Highly optimised wing, with appropriate variation of thickness, camber and twist along the span";
  - "Cross-sectional area distribution along the length, adjusted for good high speed characteristics";
  - "Leading Edge slats, scheduled for favourable aerodynamic behaviour";
  - "Wing-shielded bifurcated air intake duct, with diverters".
  — [tejas.gov.in "Leading particulars & performance" (archived Dec 2017)](https://web.archive.org/web/20171221014017/http://tejas.gov.in/specifications/leading_particulars_and_performance.html)
- [DIRECT] Composites are 43% of airframe weight per [ADA Airframe Directorate](https://www.ada.gov.in/images/af.htm), versus "45% by weight and 90% by surface area" per [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas). This is a minor conflict.
- [ASSUMPTION] Aspect ratio A = b²/S = 8.2²/38.4 = **1.75**.
- [ASSUMPTION] Mean aerodynamic chord: **c̄ ≈ 5.5 m (5.2–5.9 m)**, with root chord at centreline ≈ 7.5–8.0 m.
  - Method: I integrated a cranked planform with 50° inboard and 62.5° outboard LE sweep, a −4° trailing edge and a 4.1 m semi-span, for tip chords of 0.6–1.2 m and crank stations of 1.0–2.5 m. Solutions that reproduce S = 38.4 m² give c̄ = 5.4–5.7 m and spanwise MAC station y ≈ 1.5 m.
  - The independent check in Q4 also gives c̄ ≈ 5.5 m: NAL's dimensional derivatives reconcile with non-dimensional ones only at that value.
  - Validate against any ADA three-view, or digitise a published plan view.

**Weights and fuel**
- [DIRECT] Weights per the [ADA brochure 2013](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf) and the [ADA Mk1 page](https://www.ada.gov.in/images/mk1.htm):
  - empty 6,560 kg;
  - take-off clean 9,800 kg;
  - external stores 3,500 kg.
- [DIRECT] Conflicts with other sources:
  - CAG found limited-series-production (LSP) aircraft empty weights of **6,682–6,802 kg**, against 5,365 kg stipulated, and basic weights of 9,799–9,949 kg — [CAG Report 17 of 2015, p. 50](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
  - HAL gives external stores as 5,300 kg — [Wikipedia citing HAL](https://en.wikipedia.org/wiki/HAL_Tejas).
- [DIRECT] Max take-off mass 13,500 kg — [MoD DDP](https://www.ddpmod.gov.in/hi/node/6843). ADA AR 2017-18 records parameter identification "in heavy configuration (13.5 tons)" — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf) (local text `research_sources/indian_fleet/ada/ADA_AR_2017-18.txt`).
- [DIRECT, secondary] Internal fuel 2,458 kg (3,060 L) per [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas), versus 2,486 kg per an unsourced blog ([Alpha Defense 2026](https://alphadefense.in/2026/03/10/tejas-yesterday-today-and-tommorow/)). The fuel system belongs to the sibling researcher.
- [DIRECT] Wet-runway evaluation was flown "with aircraft mass of 9600 Kg" — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf).

**Inertias, CG, static margin**
- [DIRECT, unnamed] Mass and inertia from ADA IFCS / NAL authors. M. Jayalakshmi is with IFCS-ADA. V.V. Patel is "Group Director (Flight Control Laws – LCA Airforce)". G.K. Singh is with NAL Flight Mechanics & Control Division (FMCD). Their paper studies "a typical single-engine tailless fighter aircraft … four elevons (aileron and elevator) and one rudder", using simulation software "validated using flight data".
  - Simulation step 80 Hz (0.0125 s).
  - Mass "~9000 Kg".
  - Inertias: **Ixx = 14,087.9, Iyy = 66,558.9, Izz = 77,875.2, Izx = 2,490.5, Ixy = 162.5, Iyz = 32.5 kg·m²**.
  - CG **34.0% MAC**.
  — [Jayalakshmi, Patel & Singh, "Relook at Aileron to Rudder Interconnect", DSJ 71(2), 2021, pp. 153–161, §3.5 p. 158](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347)
- [ASSUMPTION, derived] Radii of gyration from those inertias:
  - kx = 1.25 m, ky = 2.72 m, kz = 2.94 m.
  - Non-dimensional: R̄x = 2kx/b = 0.305; R̄y = 2ky/L = 0.412; R̄z = 2kz/((b+L)/2) = 0.550.
  - Use these to rescale inertia with fuel and store state (I = m·(R̄·dim/2)²), plus point masses for stores at pylon stations. Validate by checking that the 9,000 kg values are reproduced and that mass changes give plausible short-period and roll-mode frequency shifts.
- [TRANSFER: comparators] Comparator mass properties:

  | Aircraft | Mass (kg) | Ixx | Iyy | Izz | Ixz (kg·m²) | Source |
  |---|---|---|---|---|---|---|
  | Tejas-like (ADA paper) | ~9,000 | 14,088 | 66,559 | 77,875 | 2,491 | [DSJ 71(2)](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347) |
  | ADMIRE (generic delta-canard) | 9,100 | 21,000 | 81,000 | 101,000 | 2,500 | [FOI-R--1624--SE Table 2.1](https://www.foi.se/rest-api/report/FOI-R--1624--SE) |
  | F-16 (TP-1538) | 9,299 | 12,875 | 75,674 | 85,552 | 1,331 | [NASA TP-1538](https://ntrs.nasa.gov/citations/19800005879) |
  | X-31 (cranked delta + canard, F404) | 7,257 | 4,817 | 68,666 | 66,933 | −212 | [NASA TM-2003-212145 Table 7](https://ntrs.nasa.gov/citations/20030013626) |
  | F-106B (tailless 60° delta) | 13,506 | 25,264 | 241,143 | 259,281 | 7,510 | [TM-2003-212145 Table 2](https://ntrs.nasa.gov/citations/20030013626) |

  Imperial values were converted with 1 slug·ft² = 1.35582 kg·m².
- [DIRECT] Static instability:
  - "Tejas instability is defined by 'time to double amplitude' and is one of the lowest amongst contemporary ac in the world … The region from 0.5M to 0.7M and from 3 Km to 8 Km is the zone of the highest instability with time to double amplitude dropping to 200 milli secs."
  - Fig-2 ("Time to Double Plot, 3201 series, AutoSlat") shows the following:
    - colour scale from 0/∞ to 3.5 s⁻¹ / 200 ms;
    - the highest instability (red, ~3–3.5 s⁻¹) at M ≈ 0.55–0.8, 3–10 km;
    - weak instability (t₂ > 0.7 s) below M ≈ 0.3;
    - no instability (stable) at roughly M ≥ 0.95–1.0;
    - the flight envelope polygon "FE-2" plotted for g ≤ 6 and α ≤ 23.
  — [AeSI FTG 2005, §6 and Fig-2, p. 3](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)
- [DIRECT] Configuration changes with CFD validation. A late configuration change (wing moved back, intake entry forward, fuselage lengthened) changed transonic "stability margin" by 4.03 in the wind tunnel (WT) and 3.96 in CFD: from Config A 2.48 to Config B −1.55 (WT). The units and sign convention are not stated; probably % MAC. CFD absolute error was 15–16%, but increments were within ~2%. — [K.P. Singh (ADA), "CFD Tools as Applied to Indian Combat Aircraft Configuration", JOAST 57(1), 2005, Table-1](https://joast.org/index.php/joast/article/view/677)
- [ASSUMPTION, derived] Instability level, two estimates:
  - Low speed: NAL's M0.22 short-period model (Q4) gives Cmα ≈ +0.049/rad with CLα ≈ 2.5/rad, so the aircraft is about 2% MAC unstable (slats auto, about 9 t).
  - High subsonic: reproducing t₂ = 0.2 s at M0.7/5 km (q = 18.5 kPa, CLα 3.0, Cmq −1.2, Iyy 66,559 kg·m², c̄ 5.5 m) requires Mα ≈ 19.6 s⁻², i.e. Cmα ≈ +0.33/rad, or about **11% MAC unstable**.
  - Validate by reproducing the Fig-2 map with the proxy model (see validation test V4).

### Inferences
- A Tejas-class model can be honestly parameterised with public mass and inertia data. The inertia set from the ADA IFCS paper is the single most valuable mass-property find. Its CG reference (34% MAC) agrees with NFTC's 33.5% MAC [ASSUMPTION: same aircraft; consistent with authorship].
- The instability must be Mach- and q-dependent. Tejas follows the classic relaxed-stability delta pattern: unstable subsonic, near neutral or stable at M ≳ 0.95 as the aerodynamic centre moves aft. The trim-elevon schedule therefore reverses sign across the transonic region. This matters for elevon actuator duty modelling in Q2 and Q8.

### Gaps
- Official MAC length and station, crank station, tip chord and root chord. Inboard/outboard ordering of the sweeps is inferred, not stated.
- CG travel with fuel burn and stores, and its limits (forward/aft % MAC).
- Mk1A empty weight and inertia changes. Mk1A was intended to be lighter than Mk1, per [Wikipedia "Variants"](https://en.wikipedia.org/wiki/HAL_Tejas), but no numbers were found.
- Official internal fuel mass (only the Wikipedia value was found).

---

## Q2. Control surfaces and actuation: surfaces, deflection limits, actuator characteristics, models

### Takeaway
Primary controls:
- four elevons, inboard and outboard on each wing;
- one rudder.

Secondary controls:
- six leading-edge (LE) slat actuators, three slats per wing, scheduled with AoA and Mach;
- two airbrakes on the upper rear fuselage.

The 13 actuators are imported (Moog, USA) on Mk1. Indigenous slat and airbrake actuators were delivered for Mk1A in 2024, and indigenous elevon and rudder actuators were in iron-bird testing in late 2024.

Primary actuators are quadruplex electrical, dual hydraulic at 280 bar, with direct-drive valves (DDV), about 9 Hz frequency response and 2–10 t stall load.

Deflection data from flight-control and NFTC sources:
- rudder ±30° at 100°/s;
- differential elevon ("aileron") command ±18° at 45°/s;
- elevon ±25° (secondary source, partly corroborated);
- slats up to 30°.

No official symmetric-elevon rate limit or hinge-moment data were found.

### Cited Findings
- [DIRECT] Actuator inventory:
  - "13 actuators: 4 elevon, 1 rudder, 6 LE slat and 2 airbrake".
  - Indigenisation via VSSC "DALIA" and a HAL/MTAR/Godrej consortium was delayed, so imported actuators continued.
  — [CAG 17/2015, pp. 36–37](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf), as summarised in `indian_fleet_platform_relevance.md` KQ4 S7.
- [DIRECT] Primary and secondary actuator technology, quoted from Kala (2015):
  - "Primary control surface actuators consist of Elevons and Rudder actuators. They are quadruplex in electrical and dual in hydraulics. The operating pressure is 280 bars. The state-of-the-art DDV type of control is employed … to perform BIT tests automatically from DFCC."
  - "The secondary control surface actuators consist of 6 leading edge slat actuators, which are of 3 types … single hydraulics operated with electro-hydraulics servo valve and controlled by dual electrical system. The airbrakes use open loop jacks operated from the cockpit by electro selector valves. These servo actuators have a frequency response of 9 Hz and have a stall load capability of 2–10 tons."
  - The text is ambiguous: "these servo actuators" may refer to all servo actuators or only to the secondary ones.
  - Mk2: "servo-controlled Airbrake actuator".
  — [V. Kala (ADE), JOAST 67(2A), 2015, p. 215](https://joast.org/index.php/joast/article/view/317); local copy `research_sources/indian_fleet/joast/joast_317.pdf`
- [DIRECT] Primary actuators are made by **Moog Inc., USA**. Integration testing of indigenous actuators (13 planned: 6 slat, 2 airbrake, 4 elevon, 1 rudder) began at HAL ARDC's Iron Bird in Nov 2024, in "time and frequency domains". The next step is flight testing a DFCC with a pair of indigenous elevon actuators on an LSP aircraft. — [The Week, 25 Nov 2024](https://www.theweek.in/news/defence/2024/11/25/lca-tejas-updates-integration-testing-of-india-made-actuators-begins.amp.html). ADA AR 2015-16 also records "modified actuators procured from M/s MOOG" for LCA Navy rotary gear — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf).
- [DIRECT] Mk1A secondary flight controls: ADA handed HAL the first indigenous "Leading Edge Slats and Airbrake Control Module" with "Servo-Valve based electro-hydraulic servo actuators … high pressure, redundant", produced at HAL Accessories Division, Lucknow — [PIB, 19 Apr 2024](https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2018282). ADA AR 2019-20 lists "Integration & flight testing of Indigenous Airbrake Actuators: completed" — [ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf) (local OCR).
- [DIRECT, unnamed] Rudder and aileron limits in the IFCS simulation: "the position limit of rudder and aileron control surface deflection is ±30°, and ±18° respectively and corresponding their rate limits are ±100 °/sec and ±45 °/sec. Maximum control deflection occurs at low speed and it decreases as the speed increases."
  - "Aileron" here is the differential elevon command (four elevons act "aileron and elevator").
  - Aero tables are functions of individual elevon positions loe, lie, roe, rie.
  — [DSJ 71(2), 2021, §3.5](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347)
- [DIRECT] Spin-recovery charts (vertical tunnel):
  - full out-spin rudder "δr = +30" (deg);
  - aileron axis ±25°;
  - elevator axis to 25°;
  - "some configurations required 18.5 deg In-Spin Aileron … some … 25 deg".
  — [AeSI FTG 2005, §12–13, Fig-8](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)
- [DIRECT, secondary, unsourced] Deflection ranges from a blog:
  - "Elevon deflection: ±25° … Rudder ±30°";
  - slats "Inboard up to 17.5°, Midboard up to 27.5°, Outboard up to 30° … deploy automatically".
  — [Alpha Defense, Mar 2026](https://alphadefense.in/2026/03/10/tejas-yesterday-today-and-tommorow/)
  - Partial corroboration for the slats: NFTC's directional-stability figure is at "Slat30 deg" — [AeSI FTG 2005 Fig-4](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf).
- [DIRECT] Airbrakes: "two airbrakes, located in the upper rear part of the fuselage, one each on either side of the fin" — [Wikipedia, Flight control system](https://en.wikipedia.org/wiki/HAL_Tejas).
- [DIRECT] The LCA aero data set (HAL ARDC) includes hinge-moment tables:
  - inboard elevon hinge moment: Cho, Chα, Chδe;
  - outboard elevon hinge moment: Cho, Chα, Chδe;
  - rudder hinge moment: Chβ, Chδr, Chδa.
  - CFD was used for "control surface hinge moments, load sharing" and for loads on control surfaces and LE devices "for selection of the appropriate size of the actuators".
  — [AeSI FTG 2004, Sqn Ldr (Retd) Baldev Singh & P. Jayasimha (HAL ARDC), "Aero-data set and its relevance to present day flight testing", §16](https://web.archive.org/web/20060305025452/http://www.csirwebistad.org:80/aesi/pdf/ftgseminar05/presentations/2004/Aero%20Data.pdf); [K.P. Singh, JOAST 57(1) 2005](https://joast.org/index.php/joast/article/view/677)
- [DIRECT] Behaviour in departure and hydraulic demand:
  - "departure will cause the controls to oppose the ac motion … the controls will hard over at up to max actuator rate … oscillatory deflections … large hydraulic system demands";
  - "the emergency pump can supply flow for three min but not at the rate desired for full control activity", with a backup source of "approx 60 lpm" proposed;
  - "slats being simplex in hydraulics, it may be safer to set them in the safer extended position" for high-AoA test points.
  — [AeSI FTG 2005 §14, §19(a), §25](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)
- [DIRECT] Pitch-loop timing: the elevon actuator transfer function is obtained from rig tests and cascaded with "onboard computer computation delay of 8 ms modeled as a transportation lag" — [Patel, Deodhare & Chetty, JOAST 58(4), 2006, p. 279](https://joast.org/index.php/joast/article/view/741)
- [TRANSFER: ADMIRE 4.0] Actuator template: a first-order lag with position and rate limits. Elevons ±25° at ±50°/s; rudder ±30° at ±50°/s; LE flap −10/+30° at ±20°/s; canard −55/+25° at ±50°/s; 20 ms computer delay (Padé). Mach-dependent maximum deflections are given in Fig. 2.2. — [FOI-R--1624--SE, §2.5, Table 2.2, p. 13](https://www.foi.se/rest-api/report/FOI-R--1624--SE)
  - Conflict with the older ADMIRE 3.4h figures (elevons ±30° at 150°/s; τ = 0.05 s) reported in [Härkegård PhD-820 Table 2.4](https://www.control.isy.liu.se/research/reports/Ph.D.Thesis/PhD820.pdf). The versions differ, so state which one is used.

### Inferences
- [ASSUMPTION] Recommended Tejas-class actuator model:
  - each of 4 elevons, the rudder and 6 slats as a second-order servo with ωn ≈ 2π·9 ≈ 57 rad/s and ζ ≈ 0.7 (or first-order with τ ≈ 0.018 s), plus position and rate limits;
  - 8 ms computational transport delay;
  - 12.5 ms DFCC frame (Q3).
  - Limits:
    - rudder ±30° at 100°/s [DIRECT, unnamed];
    - elevons −25/+25° [secondary] with symmetric rate **60–80°/s** [ASSUMPTION; F-16 stabilator 60°/s per TP-1538; ADMIRE 4.0 uses 50°/s]. The rate must be validated as high enough to stabilise t₂ = 0.2 s without saturation during piloted 3-2-1-1 inputs at M0.6–0.8 (validation test V8).
    - differential (roll) command ±18° at 45°/s [DIRECT, unnamed];
    - slats 0 to +17.5°/+27.5°/+30° (IB/MB/OB) at ~20°/s [ASSUMPTION: ADMIRE LEF rate].
- For predictive maintenance, actuator duty should be computed per actuator:
  - stroke and position spectra;
  - rate reversals;
  - time at rate limit;
  - hinge-moment-weighted cycles.

  Hinge moments need Chα and Chδ estimates, which DATCOM and VSPAERO can provide for flaps and elevons [ASSUMPTION], scaled so that peak loads stay inside the 2–10 t stall-load figure.

### Gaps
- Official symmetric elevon deflection range, elevon and slat rate limits, actuator bandwidth per surface, hinge-moment coefficients, airbrake deflection and opening time.
- Whether "9 Hz" refers to primary or secondary actuators.
- Slat schedule (deflection vs AoA and Mach) and slat actuator rate.

---

## Q3. Flight control system: architecture, frame time, cross-channel links, redundancy and voting, control-law structure, reversionary modes, BIT

### Takeaway
Tejas has a full-authority quadruplex digital fly-by-wire (DFBW) system with no mechanical backup.
- The DFCC has four electrically independent channels, linked by a Cross Channel Data Link (CCDL).
- It runs a 12.5 ms (80 Hz) frame with a multi-rate scheduler. About 8 ms of computation delay is modelled in stability analyses.
- Sensors: inertial and pilot-command sensors are quadruplex; air data is triplex; heater monitors are simplex.
- Voted signals are medians.
- Air data comes from a quadruplex Air Data Computer (ADC) over RS-422. Avionics data goes over MIL-STD-1553B.

Control laws are by the NAL-led National Control Law Team (NCLT). They are gain-scheduled on Mach and altitude, using longitudinal q/Nz feedback. Lateral-directional laws use stability-axis rate feedback (p, r, β, β̇), an inertial-coupling term and an aileron-to-rudder interconnect (ARI) scheduled on Mach and altitude.

Carefree and boundary-limiting features include:
- AoA and g limiting;
- automatic low-speed recovery (ALSR);
- disorientation recovery;
- autopilot modes;
- wake protection;
- Kalman-filter attitude estimation.

Reversionary and test modes:
- a "fixed-gain" backup control law with undercarriage-dependent gains;
- a pilot-selectable spin-recovery mode that disconnects feedback;
- a Flight Test Panel injecting 3-2-1-1 and sweep signals.

Built-in test (BIT) comes in continuous, pilot-initiated and maintenance forms (CBIT/PBIT/MBIT); the ADC has 90% BIT coverage.

### Cited Findings
**Architecture and timing**
- [DIRECT] "The LCA FCS is a full authority Quadruplex DFBW flight control system with no back up. The system is built around DFCC containing four identical channels … electrically independent including the input power supply … Four distributed Air Data Computers (ADC) are connected to DFCC's corresponding channel through RS 422 link … A high speed serial link called Cross Channel Data Link (CCDL) is used for communication among the four channels." — [Kala, JOAST 2015, pp. 213–214](https://joast.org/index.php/joast/article/view/317)
- [DIRECT] Processors:
  - DFCC Mk1: Intel 80960MC.
  - DFCC Mk2: MPC5566 / PowerPC 5556, with ARINC-600 connectors.
  - Mk1A DFCC (first flight on LSP-7, 19 Feb 2024): "quadraplex PowerPC based Processor, high speed autonomous state machine based I/O controller … DO-178C level-A".
  — [Kala 2015](https://joast.org/index.php/joast/article/view/317); [Ajai Shukla, Feb 2024](https://www.ajaishukla.com/2024/02/tejas-fighter-flies-with-new-digital.html); [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas)
- [DIRECT] Frame time:
  - "Since operational flight program functionality exceeded the execution time limit of more than 75% of 12.5 msec … ADE developed a single node Quadruplex Air Data Computer" — [Kala 2015, p. 215](https://joast.org/index.php/joast/article/view/317).
  - "The stability and control cycle is updated every 12.5 milli secs" — [AeSI FTG 2005 §6](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf).
  - "Various tasks are scheduled at different rates for which a pre-determined multi-rate real time scheduler is designed" — [Kala 2015, p. 216](https://joast.org/index.php/joast/article/view/317).
  - This confirms the earlier [ASSUMPTION] in `indian_fleet_platform_relevance.md`: 12.5 ms is the base frame, i.e. 80 Hz.
- [DIRECT] Interfaces: "The DFCC channels are built around 32-bit microprocessors and use a subset of the Ada programming language … The computer interfaces with pilot display elements like the MFDs through MIL-STD-1553B multiplex avionics data buses and RS-422 serial links." The DFCC drives "the elevons, rudder and leading edge slat hydraulic actuators". — [tejas.gov.in "Fly by wire" (archived Jan 2018)](https://web.archive.org/web/20180102040737/http://tejas.gov.in/technology/fly_by_wire.html)
- [DIRECT] Operational flight program (OFP) software (Ada) covers initialisation, input acquisition, redundancy management, control-law computation, output drive, BIT, synchronisation and executive. Features include "auto pilot, wake protection features, estimation of attitude based on Kalman filter". "Built-in-test features have been upgraded" for squadron and maintenance needs. BIT types: "continuous built-in-test (BIT) and pilot initiated BIT and maintenance BIT". The DFCC is "designed to operate for one hour without cooling air". — [Kala 2015](https://joast.org/index.php/joast/article/view/317)

**Redundancy, voting and monitoring**
- [DIRECT] "Redundancy level of LCA FCS sensors vary with their importance to meet the probability of loss of control requirements. The critical rate, acceleration, pilot command sensors are quadruplex, airdata sensors are triplex and few non inertial parameters like probe heaters currents are simplex. The sensors are designed to able to perform BIT tests from the DFCC to ascertain their health before each flight." — [Kala 2015, p. 215](https://joast.org/index.php/joast/article/view/317)
- [DIRECT] Voting: "The voted Pitch rate (q), Normal Acceleration (Nz) and elevon command (δe) signals (median of multiple sensor signals – is less noisy than the raw signals) are telemetered in real time" — [Patel, Deodhare & Chetty, JOAST 58(4) 2006, p. 278](https://joast.org/index.php/joast/article/view/741)
- [DIRECT] Air-data failure management: "Since the sensor failures could cause mistrack, so the faulty sensors were voted out. Multiple failures could cause certain events to be set in the control law to facilitate reversionary backup control laws to be brought into action. The airdata algorithm output are also sent for display on the head-up-display and on the get-U-home panel … a single working sensor can provide the required information." — [Rajalakshmi, Jeppu & Karunakar (ADA), "Ensuring Software Quality – Experiences of Testing Tejas Airdata Software", DSJ 56(1), 2006, p. 14](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863)
- [DIRECT] "departure may cause the air data sensors to cross the mistrack thresholds and trip … on recovery … the FCS may be in a failed state and air data will need to be re initialized … the FCS may have entered a reversionary mode. A reset should be able to clear such failures" — [AeSI FTG 2005 §25–26](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf). (In 2005: "Currently the LCA Air data system is not fail-Op, fail-safe and needs to be upgraded" (§20). ADA now states "Fail Operational, Fail Safe Air Data System" — [ADA IFCS](https://www.ada.gov.in/images/ifcs.htm).)

**Control-law structure and gain scheduling**
- [DIRECT] Development and gain scheduling:
  - Control laws were designed from WT aero data: "initial flight control laws are designed based on this wind tunnel aerodynamic data … validated in actual flight using parameter identification techniques … the control law gains and coefficients are scheduled based on air data parameters obtained from external sensors" — [AeSI FTG 2005 §10](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf).
  - "the feedback gains are scheduled as a function of Mach and altitude so that a uniform gain margin is obtained throughout the flight envelope" — [JOAST 58(4) 2006, p. 285](https://joast.org/index.php/joast/article/view/741).
- [DIRECT] Pitch-axis loop:
  - Stability margins are computed "by opening the loop at the actuator consolidation point".
  - Plant transfer functions are the pitch rate q/δe and Nz/δe, with Nz measured at a sensor forward of the CG.
  - "a low-pass filter added in the command path of the control laws to meet the handling quality requirements".
  - "Typical fighter aircraft like LCA have gain and phase crossover frequencies around 1 Hz and 3 Hz respectively."
  - The design template is gain margin ≥ 6 dB and phase margin ≥ 35°.
  - Flight-estimated margins for 12 test segments: gain margin magnitude 9.3–17.1 dB, phase margin 58–68°, all within 1.3 dB / 3.9° of linear-model predictions.
  — [JOAST 58(4) 2006, pp. 276–282, Tables 1–2](https://joast.org/index.php/joast/article/view/741)
- [DIRECT] Reversionary fixed-gain mode:
  - First-block flights of TD-1/TD-2 used "'fixed gain' mode over a restricted flight envelope using only signals from the inertial sensors (rate gyros and accelerometers)", because AoA, sideslip and air data were "not available (pending flight calibration)".
  - The fixed gains "depend on the undercarriage position … around 370 KMPH a sudden increase in gain margin can be seen. This is because the gains are reduced when undercarriage is retracted".
  - Later blocks flew "a 'scheduled gain' claw version with back up mode as 'fixed gain'".
  — [JOAST 58(4) 2006, pp. 283–284](https://joast.org/index.php/joast/article/view/741)
  - First flight (4 Jan 2001): "The control laws for the first flight were thus flown with fixed gains" — [Air Marshal R. Nambiar, Livefist, Dec 2025](https://www.livefistdefence.com/25-years-on-my-recollections-of-the-1st-tejas-flight/).
- [DIRECT, unnamed] Lateral-directional law, from the block schematic "for fighter aircraft" by ADA IFCS / NCLT authors:
  - feedback of p, r, β and β̇ to rudder and aileron;
  - "The aircraft needs to roll about the velocity vector to remove the kinematic coupling among α and β at high alpha … The angular rates in the stability axis ps = p and rs = r − p·tanα are used";
  - an inertial-coupling compensation term in the directional path, printed as Δṙ = ((Iy − Ix)/Iz)·p·r. The rigid-body yaw equation would suggest p·q, so treat the printed form with caution;
  - a feed-forward ARI gain "scheduled with Mach No. and altitude";
  - designed to MIL-F-9490D and MIL-F-8785C.
  — [DSJ 71(2) 2021, pp. 154–156](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347)
  - ARI gains (Method 1) at 6 km: **+3.47 at M0.26, −0.60 at M0.7, −0.319 at M1.3** (Table 2).
  - Fault-reconfiguration latency in the example: 0.35 s.
- [DIRECT] Carefree features and protections:
  - "Robust Control Laws for Stability and command Augmentation, Carefree Maneuvering, Autopilot Control and Ski Jump functionalities" — [ADA IFCS](https://www.ada.gov.in/images/ifcs.htm).
  - "The CLAW is carefree and ensures that various aircraft parameters are limited automatically" — [tejas.gov.in FBW (archived)](https://web.archive.org/web/20180102040737/http://tejas.gov.in/technology/fly_by_wire.html).
  - "Novel auto recovery modes like Automatic Low Speed Recovery and Disorientation Recovery Mode will also be flight tested towards attaining Carefree Maneuvering capability" — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf).
  - ALSR trials in FOC clean configuration were flown in 2017-19 — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf); [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf).
  - "boundary limiting / carefree maneuvering features" and a cockpit "AoA LIMITER" control (Fig-10) — [AeSI FTG 2005 §1, Fig-10](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf).
- [DIRECT] Spin recovery mode: "an additional pilot selectable spin recovery mode in the control laws which disconnects the feedbacks from the inertial sensors and scales the pilot stick input to give full authority over the control surfaces". The mode also routes "only nose boom data on the GUH [get-you-home] displays". — [AeSI FTG 2005 §14, §25](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)
- [DIRECT] Autopilot and navigation modes: "navigation, localizer slope capture" were flight-evaluated in 2019-20 — [ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf). Navy: Approach Angle-of-Attack Hold Control (AAHC) mode for landing, plus ski-jump CLAW — [ADA AR 2015-16, §9.1.5](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf).
- [DIRECT] Software versions that changed the envelope:
  - "New DFCC Version 7307 featured full envelope Nz clearance 8.5 g subsonic / 6 g supersonic" — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf).
  - "DFCC Version 7351 with OAC 10.0.4.0" (same report).
- [DIRECT] Flight Test Panel (FTP):
  - "a programmable function generator … for a maximum of 100 (0 to 99) test-points";
  - inputs reach the DFCC "through either of two communication channels, one simplex digital RS-422 serial link for parameter identification purposes and the other through a set of five analogue lines (four elevons and one rudder) for carrying out flutter/structural coupling tests";
  - auto-abort on "'g'-limits, actuator rate and position limits, feedback sensor and pilot input (stick/pedal) limits".
  — [JOAST 58(4) 2006, pp. 282–283](https://joast.org/index.php/joast/article/view/741)
- [DIRECT] Structural notch filters are part of the control laws: Patel is credited with the "design of structural notch filters" — [Venture Center talk abstract, 26 Nov 2017](https://www.venturecenter.co.in/pdfs/26-Nov-2017-LCA.pdf). The ADA IFCS facility list includes "Structural Coupling Tests" — [ADA IFCS](https://www.ada.gov.in/images/ifcs.htm).
- [DIRECT] Pre-flight BIT duration: TD-1 start-up included a roughly ten-minute "FBW diagnostic test … green" — [Livefist, Dec 2025](https://www.livefistdefence.com/25-years-on-my-recollections-of-the-1st-tejas-flight/). The ADC has "Built-in-testability feature with 90% coverage" and IEEE 1149.1 boundary scan — [Kala 2015](https://joast.org/index.php/joast/article/view/317).
- [DIRECT] Track record: "3000+ flight trials … flown by more than 30 test pilots without any real failure in FCS System" — [Kala 2015](https://joast.org/index.php/joast/article/view/317).
- [DIRECT, unnamed; TRANSFER caveat] NAL/CEMILAC carefree-handling research uses ADMIRE as the open-domain stand-in. It uses a command-path limiter with rate limits scheduled on dynamic pressure, plus an AoA protection that engages only when pilot inputs would exceed limits. ADMIRE's baseline is designed for about 180°/s velocity-vector roll and about 20° max operational AoA. — [Jebakumar, Pashilkar & Sundararajan, DSJ 73(3) 2023](https://www.publicationsdrdo.in/index.php/dsj/article/view/18402); [DSJ 72(4) 2022 (ALSR with forward prediction)](https://www.publicationsdrdo.in/index.php/dsj/article/view/17821). This is not Tejas data, but it shows the Indian design community's own choice of public proxy.

### Inferences
- [ASSUMPTION] A defensible Tejas-class control-law template is as follows (to be validated by the closed-loop tests in Q8):
  - **Pitch:** pitch-rate command at low dynamic pressure, blending to Nz (or C*) command at high dynamic pressure, as in ADMIRE's q/Nz blend at M0.58–0.62. Proportional-integral (PI) on the error with q and Nz feedback. Gains scheduled on Mach and altitude. Command-path low-pass prefilter. Structural notch filters. AoA limiter at 26° (subsonic) and g limiter at +8/−3.5 g, or +8.5 g subsonic / 6 g supersonic per DFCC v7307.
  - **Lateral-directional:** stability-axis roll-rate command (velocity-vector roll), β and β̇ feedback, ARI scheduled on Mach and altitude, inertial-coupling feed-forward (form as printed in DSJ 71(2); verify).
  - **Reversionary:** fixed-gain law with undercarriage-dependent gains, inertial sensors only, entered after multiple air-data failures.
  - **Timing:** 80 Hz frame, median voting of quad signals, triplex air data with mistrack monitors.
  - **BIT events:** PBIT (~10 min at start-up), CBIT (continuous), MBIT (ground).
- This structure gives the data layer realistic event streams for failure-to-reversion sequences, mistrack trips, BIT logs and telemetered voted signals.

### Gaps
- Exact pitch command variable (q, Nz or C*), blend Mach, limiter algorithm details, gain-schedule tables, roll-rate command gain and maximum roll rate.
- Monitoring thresholds: mistrack levels, persistence times, voting algorithm beyond "median", and CCDL rates.
- PBIT/CBIT/MBIT coverage figures for the DFCC and actuators (only ADC 90% is public).
- The AIAA GNC 2002 control-law paper and the AIAA ATIO 2002 stability-margin paper (Patel et al.) were not accessible.

---

## Q4. Published Tejas aerodynamics: wind tunnel, CFD, system identification derivatives, high-AoA behaviour, air-data calibration, FADS

### Takeaway
No Tejas aero tables are public. However, a substantial set of numbers can be pieced together from ADA, NAL and HAL papers and from flight-test seminar presentations:
- a low-speed WT lift curve to 30° AoA (CLmax still rising at ~35°);
- directional stability Cnβ(α) collapsing at ~25° AoA;
- rolling- and yawing-moment curves at β = 10°;
- rudder power Cnδr;
- Cm(α) shapes from AEDC and Calspan tunnels (flat to ~10°, pitch-up bump at 12–16°, nose-down break above ~20°);
- NAL longitudinal derivatives (Cmα, Cmq, Cmδe) at α_trim 4.3°, 11.9° and 11.55° (real large-amplitude-manoeuvre flight data);
- a full short-period model at M0.22/300 m;
- flight short-period estimates at M0.7/4,119 m;
- trim AoA at 8 km for M0.4/0.6/1.0;
- spin-mode characteristics.

These numbers are mutually consistent when c̄ ≈ 5.5 m and the published inertias are used. That makes them usable as calibration anchors.

The LCA aero data set (HAL, Ver 3.0) structure is also public:
- 6 tunnels, 6 models, 3,000 polars, 430 tables;
- component build-up per elevon.

### Cited Findings
**Aero data set structure and sources**
- [DIRECT] HAL ARDC's account of the LCA aero data set:
  - Effort for Ver 3.0: "No. of Tunnels used: 6; No. of Models used: 6; No. of Polars analysed: 3000; No. of Graphs plotted: 600; No. of Tables prepared: 430; No. of people involved: 6; No. of Man Years spent: 10".
  - Components: "BASIC DATA: CZo, CZα, CX, Cmo, Cmα, CYβ, Clβ, Cnβ; CONTROL POWERS: CNδe, Cmδe, CYδa, Clδa, Cnδa, CYδr, Clδr, Cnδr; IB ELEVON HM, OB ELEVON HM, RUDDER HM; EFFECT OF SLATS, AIRBRAKES, STORES, GROUND EFFECTS".
  - The pitching-moment build-up sums separate left/right × inboard/outboard elevon terms, each with its own effectiveness factor, plus undercarriage, ground-effect, airbrake and store increments, ground-effect and airbrake effects on δe power, and Cmq·q̂ + Cmα̇·α̂̇ "due to dynamic derivatives", with aeroelastic ("AE") correction factors.
  - "Six component Force and Moment data including damping derivatives and ground effect – for low angles of attack … Static, rotary, forced oscillation force & moment data for high angles of attack".
  - Sources: "DATCOM, RAE Data Sheets … CFD … Wind Tunnels … Data from aircraft of a similar class … the 'Work Horse' is still the Wind Tunnel".
  - Data from AEDC and Calspan tunnels were synthesised, "with results from larger tunnel / larger model as being more reliable".
  - Lessons learnt: "No coupling between Port and Starboard deflection effects".
  — [AeSI FTG 2004, HAL ARDC, §12–20, pp. 9–12](https://web.archive.org/web/20060305025452/http://www.csirwebistad.org:80/aesi/pdf/ftgseminar05/presentations/2004/Aero%20Data.pdf)
- [DIRECT, unnamed] Same build-up form for the rolling moment in the IFCS simulation: Cl = Clβ(β) + Clδr(α, M, δr) + Clr(M)·rb/2V + Clp(M)·pb/2V + Σ Clδa(α, M, each elevon). The tables are functions of α, β, the four elevon positions, δr and Mach. — [DSJ 71(2) 2021, eq. (10)](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347)
- [DIRECT] Global force and moment coefficients come from WT testing; CFD supplies loads, increments and air-data flow fields. Wave drag computed by CFD was under-predicted by "3% and 10% as compared to experimental and flight data". CFD reduced trainer-canopy wave drag by 50%. NAL WT Cp at M0.95, α 4.65° and 9.416°; RANS at M0.7, α 13.272° and 17.714°. — [K.P. Singh, JOAST 57(1) 2005](https://joast.org/index.php/joast/article/view/677); [Singh et al., "CFD in Aerospace Industry in India", DSJ 60(6) 2010, pp. 639–642](https://www.publicationsdrdo.in/index.php/dsj/article/view/582)
- [DIRECT] "The high angle of attack database for LCA has been generated in static, rotary balance and forced oscillation wind tunnels at TsAGI, Moscow … 1:15 scale model in the T-105 Vertical Tunnel" — [AeSI FTG 2005 §11](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)

**Lift, directional stability and high AoA (digitised from the 2005 NFTC paper)**
- [DIRECT] "Wind tunnel experiments have indicated that CL max continues to improve till approx 35° AoA."
  - Fig-3: zero vs full slats, AoA −15…30°, Mach not stated (probably low speed).
  - My readings: CL ≈ −0.65 (−15°), −0.01 (0°), 0.18 (5°), 0.41 (10°), 0.62 (15°), 0.85 (20°), ~1.03 (25°), ~1.15–1.19 (30°).
  - Slats change CL by only ±0.03.
  — [AeSI FTG 2005 §7, Fig-3](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)
- [DIRECT] Directional cliff and AoA limits:
  - "directional characteristics indicated the proverbial 'cliff' with a sudden drop in Cnβ, CRM … and CYM … at approx 25° AoA … High AoA trials to be limited to 24° … until directional stability is bolstered and augmented by rudder control up to an expected 26°. Currently the Tejas is flying to AoA limits of 20° and 22° never exceed. … significant rudder authority (CYM-Del R) even up to 30° AoA."
  - Fig-4 (M0.21, slat 30°, fuel 1,900): Cnβ ≈ +0.04–0.06/rad over α −10…15° (peak ~0.06 at 5–8°), falling to ~0 at α ≈ 23–25°, then −0.03, −0.08 and −0.135/rad at ~26°, 27° and 28°.
  - Fig-5 (β = +10°, δe = 0): yawing moment ≈ +0.013 for α 0–10°, crossing zero at ~25–27°. Rolling moment −0.005 to −0.015 at α 0–10°, reaching −0.03 at α ≈ 23° (full slats) or −0.018 (zero slats), then reversing above ~27°.
  - Fig-6 ("LCA SGE 26D, M=0.5"): **Cnδr ≈ −0.0012/deg, nearly constant from α −15° to +30°** (−0.0013 at 30°).
  - Figures were digitised by eye from rendered pages (±0.005–0.01).
  — [AeSI FTG 2005 §7, Figs. 4–6](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)
- [DIRECT] Pitching moment (Cm vs α, −4…28°, original AEDC/Calspan WT data and the synthesised set, from HAL ARDC's figure):
  - The baseline curve is ≈ 0 to −0.003 from −4° to ~11°, rises to about +0.008 at ~13°, then breaks nose-down: ≈ −0.01 (20°), −0.03 (24°), −0.066 (28°).
  - A second curve (an elevon setting) is ≈ −0.04 flat to ~10° and ≈ −0.031 at 13–16°.
  — [AeSI FTG 2004 §18 figure, p. 11](https://web.archive.org/web/20060305025452/http://www.csirwebistad.org:80/aesi/pdf/ftgseminar05/presentations/2004/Aero%20Data.pdf)
- [DIRECT] Spin modes (TsAGI vertical tunnel): "flat spin with high angular rate and oscillations in pitch and yaw". Ranges:
  - α 57–85° (most 70–80°);
  - rate 0.7–2.8 rad/s (most ~2);
  - turn duration 2.3–8.3 s (most ~3);
  - descent 76–83 m/s.
  - Recovery: out-spin rudder plus in-spin aileron, then down elevator after 2 s, or the spin chute. "It was decided that the ac would not be intentionally spun."
  — [AeSI FTG 2005 §9–12](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)
- [DIRECT] Fin buffet:
  - WT (1:10 model) buffet pressures at β up to 10°, AoA 28° and above;
  - flight-measured fin accelerations (to 100 Hz) at AoA 20–24°;
  - fin/rudder response band 15–150 Hz;
  - the validated model "is used to predict loads to clear the aircraft for further flight envelope expansion at high AoA".
  — [Kumaraswamy et al. (DIAT/ADA), JOAST 69(2) 2017](https://joast.org/index.php/joast/article/view/201). This is a usage-dependent fatigue driver for the maintenance layer.

**Flight-identified and simulator derivatives (NAL/ADA)**
- [DIRECT, unnamed] Kamali, Pashilkar & Raol (DSJ 57(4) 2007):
  - Aircraft: "a high performance delta wing fighter aircraft. It has four elevons and rudder as primary control surfaces … open loop unstable … stabilised with a highly augmented feedback control law". The authors work "on the LCA" and are NCLT members.
  - Short-period model at **M0.22, 300 m, "fuel state = 9060", gear up, automatic slat**: [α̇; q̇] = [[−0.4784, 0.9724], [0.5160, −0.4276]]·[α; q] + [−0.1842; −3.7391]·δe. Eigenvalues are −1.1618 and **+0.2558 (unstable)**.
  - Real flight data at **M0.7, 4,119 m** (DFT / RLS estimates): Zα −0.9093/−0.8969; Mα −1.5278/−1.5406; Mq −1.0404/−1.0208; Mδe −12.571/−12.581 (s⁻¹ or s⁻² as appropriate).
  — [DSJ 57(4) 2007, eq. (2), Tables 1 and 3](https://www.publicationsdrdo.in/index.php/dsj/article/view/1785)
- [DIRECT, unnamed] Parameswaran, Girija & Raol (NAL), "Estimation of Parameters with Partitioned Data from Large Amplitude Maneuvers of an Aircraft", JOAST 56(3) 2004, Tables 2–3. The fighter is "inherently unstable/augmented … relatively highly unstable", with "pitch up tendency … during certain AoA range". Units are not printed; consistency checks indicate per radian.

  | α_trim | Cmα ref / est | Cmq ref / est | Cmδe ref / est | Data |
  |---|---|---|---|---|
  | 11.90° | 0.0771 / 0.0714–0.0810 | −1.1733 / −1.25 to −1.29 | −0.3905 / −0.375 to −0.379 | simulator |
  | 4.30° | −0.0144 / −0.0102 to −0.0201 | −1.3195 / −1.16 to −1.19 | −0.4151 / −0.398 to −0.411 | simulator |
  | 11.55° | 0.0771 / 0.0580–0.0610 | −1.1733 / −0.92 to −0.99 | −0.3905 / −0.394 to −0.399 | **real flight large-amplitude-manoeuvre data** |

  — [JOAST 56(3) 2004, pp. 153–156](https://joast.org/index.php/joast/article/view/754)
- [DIRECT, unnamed] Trim AoA from the engineer-in-loop simulator (ELS). NAL's ELS was used, provided by "Dr D. Girish and Dr V. Patel, members, National Control Law Team"; under-carriage up; altitude 8,000 m:
  - **M1.0 → α₀ = 2.46°**;
  - **M0.6 → 6.59°**;
  - **M0.4 → 12.45°**.
  - "As angle of attack increases, the aileron and rudder interconnection gain in flight control system increases".
  — [Shantha Kumar, "Input Excitation Techniques for Aerodynamic Derivatives Estimation of Highly Augmented Fighter Aircraft", DSJ 49(3) 1999, p. 190, acknowledgements p. 195](https://www.publicationsdrdo.in/index.php/dsj/article/view/3828)
- [DIRECT, unnamed] Drag-polar estimation work used the ADA "FBW aircraft simulator". Roller-coaster (1g-2g-0g-1g at 0.1 g/s) and wind-up-turn (α 5–20°) manoeuvres at 8 km, M0.6/0.7/0.8/1.0. The authors published methods and fit errors only, not polar values; the polar plots have unlabelled CD axes. — [Girija, Basappa, Raol & Madhuranath, DSJ 51(1) 2001](https://www.publicationsdrdo.in/index.php/dsj/article/view/2208)
- [DIRECT] Flight-validation process:
  - PID sorties "to expand envelope … completed up to the desired Angle of Attack of 26 deg at subsonic speeds and up to 1.55 Mach/4 deg AoA at supersonic speeds" — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf).
  - "High AoA Parameter Identification sorties" — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf).
  - Trainer "PID sorties conducted up to 24° AoA" — [ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf).
  - Patel "was also responsible for estimation of aerodynamic coefficients from flight test data using nonlinear parameter estimation techniques which enabled flight validation of the aerodynamic data thereby allowing the aircraft to expand its flight envelope to lower speeds and higher angles of attack" — [Venture Center 2017](https://www.venturecenter.co.in/pdfs/26-Nov-2017-LCA.pdf).
  - A good match of flight-estimated with predicted stability margins "establishes a high degree of confidence in the non-linear simulation model" — [JOAST 58(4) 2006](https://joast.org/index.php/joast/article/view/741).

**Air-data calibration and FADS**
- [DIRECT] Air-data calibration:
  - "Air data calibration sorties have been completed on LSP8 aircraft (up to M1.6); with AAR probe and IFCS software update" and "Assessment of static port corrections in flight for the Air Data Computer" — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf).
  - Local flow corrections are "initially estimated from CFD studies and wind tunnel measurements and therefore can have significant errors especially at transonic Mach Nos." — [AeSI FTG 2005 §10](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf).
  - "It would be safe to cater for a +/− 2° tolerance in regions where AoA calibration is not accurate" (§20).
- [DIRECT] CFD sensor-location studies:
  - Euler studies cover the side-mounted (SADP) and nose (NADP) probe locations, vanes and the refuelling probe.
  - Cp contours at M0.95 and 1.6.
  - Position-error envelope per MIL-P-26292C.
  - At M1.2 the refuelling-probe shock impinges "just behind the location of the pitot probes".
  - Local flow angles vary linearly with free-stream α and β, and independently of Mach (to M1.6) at the probe.
  — [Krishna & Singh (ADA), DSJ 52(1) 2002](https://www.publicationsdrdo.in/index.php/dsj/article/view/2150)
  - CFD compared with flight local AoA and Cp at the SADP at M0.4 — [DSJ 60(6) 2010](https://www.publicationsdrdo.in/index.php/dsj/article/view/582).
- [DIRECT] Wind error during flight-path reconstruction of "a high performance fighter aircraft": neglecting wind gives "error in velocity … around 40 m/s while the error in alpha is around 5 deg" over a full flight — [Khadeeja & Singh (NAL), DSJ 70(3) 2020](https://www.publicationsdrdo.in/index.php/dsj/article/view/13596).
- [DIRECT] FADS: "A prototype of FADS is planned to be demonstrated on LCA centre line drop tank, suitably modified to house sensors and airdata computer. Requirements generation is done and procurement and fabrication work is being initiated." — [ADA AR 2020-21, Advanced Technology Development](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf). No results were found.

### Inferences
- [ASSUMPTION, derived] Converting the NAL dimensional derivatives to non-dimensional form, assuming c̄ = 5.5 m, S = 38.4 m², Iyy = 66,559 kg·m², mass 9,060 kg (sim) or 9,000 kg (flight), and ISA:
  - **M0.22/300 m (q = 3,313 Pa), simulator:**
    - CLα ≈ 2.54/rad;
    - Cmα ≈ +0.049/rad;
    - Cmq ≈ −1.10;
    - Cmδe ≈ −0.356/rad;
    - CLδe ≈ 0.98/rad;
    - trim CL ≈ 0.70, i.e. α ≈ 17° on the WT curve, where the WT local slope is ≈ 0.044–0.046/deg (≈ 2.5–2.6/rad).
    - These agree with the independent JOAST 2004 table (Cmq −1.17, Cmδe −0.39/rad, Cmα +0.077/rad at α 11.9°).
    - The mutual consistency is why c̄ ≈ 5.5 m is adopted.
  - **M0.7/4,119 m (q = 20.8 kPa), flight:**
    - CLα ≈ 2.29/rad;
    - Cmq ≈ −1.27;
    - Cmδe ≈ −0.19/rad;
    - Cmα ≈ −0.023/rad (statically stable).
    - **Conflict:** this contradicts the NFTC map, which makes M0.5–0.7 at 3–8 km the most unstable region (t₂ ≈ 0.2 s, needing Cmα ≈ +0.3/rad).
    - Likely cause: equation-error and frequency-domain estimates from closed-loop flight data are biased toward stability by feedback correlation, and Mδe may be defined on a different δe convention.
    - Treat the M0.7 Mα as unreliable. Use the map and the margin results for instability.
- [ASSUMPTION, derived] Polhamus-form fit to the Tejas WT lift curve: CL = CL0 + Kp·sinα·cos²α + Kv·cosα·sin²α.
  - Over −15…20°: CL0 = −0.015, **Kp = 2.15/rad, Kv,eff = 1.90** (residual ≤ 0.007).
  - Over −15…30°: Kp = 2.25, Kv,eff = 1.54 (residual ≤ 0.02).
  - The sharp-edged theory gives Kv ≈ 3.2 at A = 1.75 ([Polhamus TN D-3767, Fig. 9](https://ntrs.nasa.gov/citations/19670003842)).
  - So Tejas realises about 50–60% of the theoretical vortex lift. This is plausible for rounded leading edges with scheduled slats, and the fall-off above 20° is consistent with the onset of vortex breakdown.
- [ASSUMPTION, derived] Trim-AoA consistency at 8 km. For 8.5–9.0 t, required CL is:
  - 0.544–0.576 at M0.4, against the WT CL(12.45°) ≈ 0.51;
  - 0.242–0.256 at M0.6, against WT CL(6.59°) ≈ 0.25;
  - 0.087–0.092 at M1.0, against WT CL(2.46°) ≈ 0.09.
  - The ELS trim points therefore match the low-speed WT lift curve to within 0–12%, implying little net Mach growth in trimmed CLα. Compressibility gain is offset by trim (elevon-up) lift loss supersonically.
  - This is a strong, cheap calibration check for any proxy (validation test V2).
- The Cm(α) shape (flat to ~10°, a local pitch-up near 12–16°, nose-down above ~20°) agrees with the NAL table (Cmα negative at 4.3°, positive at 11.9°). It is also why NAL studied "pitch up tendency". A proxy should reproduce this locally destabilising bump, because it drives elevon trim activity in turns.

### Gaps
- Lateral-directional dynamic and control derivatives (Clp, Cnr, Clδa, Cnδa, CYβ) at any condition; none are published.
- Any Mach-dependent table (CLα(M), Cm0(M), aerodynamic-centre shift) and zero-lift drag.
- The figure-level digitisations (Fig-3/4/5/6, HAL Cm plot) are approximate. Mach and CG for Fig-3 are unstated.
- The DRDO monograph on air-data pre-flight calibration (said to contain Tejas iron-bird and flight-test chapters) was inaccessible ([search lead only](https://drdo.gov.in/drdo/sites/default/files/monographs-documents/32-preflight-calibration.pdf)).
- STO MP-SCI-162-14 (probably an LCA flight-test paper) was blocked.

---

## Q5. Air-data and inertial sensors on Tejas: probes, ADCs, vanes, temperature, INS/GPS, FCS rate and acceleration packages, sampling, redundancy, buses

### Takeaway
Air-data sensing on the Tejas uses five front-fuselage stations:
- a nose air-data probe (NADP);
- two side-mounted probes (LADP/RADP, also called SADP);
- two AoA vanes.

The vanes have quadruplex LVDTs over ±45°. There is also a sideslip (AoSS) vane, a total-temperature probe, and heater-current monitors.

Pressures go to quadruplex ADCs. Each ADC holds four transducers (Ps, Pt and two differential), accurate to 0.02% FS, and each links to its DFCC channel over RS-422.

The FCS inertial sensors are quadruplex:
- the Rate Sensor Assembly (RSA) covers ±300°/s roll and ±60°/s pitch/yaw, with a 50 Hz natural frequency;
- the Acceleration Sensor Assembly (ASA) covers ±13 g normal and ±4.5 g lateral, with a 100 Hz natural frequency.

Navigation uses a SAGEM SIGMA 95N laser-gyro INS with integrated GPS/GLONASS. HAL builds it under licence. An indigenous attitude and heading reference system (AHRS) has also been flight-tested. Avionics run on MIL-STD-1553B. The FCS uses RS-422 and the CCDL. A flight-test nose boom (with a β vane) is used for high-AoA testing.

### Cited Findings
- [DIRECT] Sensor complement: "The light combat aircraft, Tejas has three pressure probes, a temperature probe, and two angle of attack vanes … The pressures were converted to electrical signals and transmitted to the four-channel digital flight control computer (DFCC) by RS422 links. Vane and probe de-icing heaters were also monitored for their health." — [Rajalakshmi et al., DSJ 56(1) 2006, p. 14](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863)
- [DIRECT] Air-data algorithm content:
  - static- and total-pressure computations with failure detection;
  - "CAOA-LP / CAOA-RP" (AoA from the left and right probes), Mach, CAS, TAS and altitude;
  - total temperature with **de-icing heater error and self-heating error corrections**, plus a Mach correction table applied for 1.0 < M ≤ 2.0;
  - air-data parameters found in flight to be "a function of the aircraft undercarriage operation", so the algorithm was modified.
  — [DSJ 56(1) 2006, pp. 14–16](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863)
- [DIRECT] "Air data system (ADS) of Indian combat aircraft has been configured with five sensors locations on front fuselage to measure total and static pressures and local flow angularity. The sensors include two Side mounted Air Data Probes (SADP), two Angle Of Attack Vanes (AOAV) and one Nose Air Data Probe (NADP)." — [K.P. Singh, JOAST 57(1) 2005](https://joast.org/index.php/joast/article/view/677); [DSJ 60(6) 2010](https://www.publicationsdrdo.in/index.php/dsj/article/view/582)
- [DIRECT] Named LRUs: "Nose, left and right air-data probes (NADP/LADP/RADP); AoA sensor" — [ADA, "Indigenous development of LRUs for LCA-Tejas", Dec 2022](https://www.ada.gov.in/images/LRU.pdf) (via `indian_fleet_platform_relevance.md` KQ4 S5).
- [DIRECT] ADC transducers: "four pressure transducers fitted inside each ADC … 35 to 1300 mbar (Ps); 35–2700 mbar (Pt), 35–1500 mbar (Pα1/β1 and Pα2/β2) within an accuracy of 0.02% F.S. … AOA, AOSS sensor which have quadruplex LVDT and measure a range between ±45°". The Mk2 adds a second AoSS vane. The quadruplex ADC is an 80960MC with Xilinx FPGA and 90% BIT coverage. — [Kala 2015, p. 215](https://joast.org/index.php/joast/article/view/317)
- [DIRECT] FCS inertial sensors: "Rate Sensor Assembly (RSA) has a natural frequency of 50 Hz and senses rates, which range between ±300°/s (Roll), ±60°/s (Pitch and Yaw). The resolution and thresholds are 0.005°/s. Acceleration Sensor Assembly (ASA) has a natural frequency of 100Hz and measures normal and lateral accelerations in the range ±13 g and ±4.5 g … thresholds are 2 mg (Normal) and 0.2 mg (Lateral) … forced balanced". The Mk2 ASA adds longitudinal sensing. — [Kala 2015, p. 215](https://joast.org/index.php/joast/article/view/317)
- [DIRECT] The pitch/yaw RSA saturates in spins. "the Rate Sensor Assembly (RSA) would have to be checked after it is submitted to accelerations beyond its max range … will the A/D converters wrap around or change signs? And will the integrators wind up?" — [AeSI FTG 2005 §25](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf)
- [DIRECT] Flight-test air data: "a beta vane will have to be fitted and calibrated to a high level of accuracy with a flight test boom"; "only nose boom data on the GUH displays" in spin mode; pneumatic standby indicators for IAS, altitude, Mach, AoA and AoSS — [AeSI FTG 2005 §20, §23, §25](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf). TD-1's first flight had no air-data boom — [Livefist](https://www.livefistdefence.com/25-years-on-my-recollections-of-the-1st-tejas-flight/).
- [DIRECT, secondary] INS/GPS:
  - HAL ordered "more than 100 SIGMA 95N" (Sagem/Safran) "standalone inertial laser gyro navigation system" with integrated GPS/GLONASS, for "Sukhoi fighters and the Tejas fighters of the LCA programme" (DefExpo, 22 Feb 2008) — [DefenceTalk](https://defencetalk.com/india-orders-over-one-hundred-sigma-95-navigation-systems-14894).
  - HAL produces the INGPS (SIGMA 95, strapdown RLG plus GPS) under licence from Safran, plus a strapdown AHRS standby and an indigenous G3INS (GPS/GLONASS/GAGAN) — [HAL navigation products](https://hal-india.co.in/backend/product/inertial-navigation-system). That page does not name platforms.
  - "AHRS (Aircraft Heading & Reference System) from an Indian vendor is integrated and being flight tested on LSP5 aircraft" — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf).
- [DIRECT, unnamed] An NAL attitude-estimation study on "a high performance aircraft" (onboard autonomous sensors, validated with full-range manoeuvring flight data) states that "most aircraft will have both IN-GPS and AHRS for redundancy". "For the class of aircraft discussed … sensors don't exhibit very high drift rates and the constant bias model is found to be sufficient." — [Kamali & Jain, DSJ 66(6) 2016](https://www.publicationsdrdo.in/index.php/dsj/article/view/8838)
- [TRANSFER: DRDO RINS] DRDO's ring-laser-gyro INS (RINS): 0.01°/h bias stability, ARW 0.003°/√h, 1 nm/h unaided, 30 m GPS-aided, MIL-1553B / ARINC-429 / RS-422 interfaces. Its fit on Tejas is not established. — [Reddy & Saraswat, DSJ 63(2) 2013](https://www.publicationsdrdo.in/index.php/dsj/article/view/4254)
- [DIRECT; ASSUMPTION re LCA] An ADE 1553B example interface-control message gives LRU health status at 12.5 Hz, with 4 minor frames per major frame — [Trivedi, JOAST 63(4) 2011](https://joast.org/index.php/joast/article/view/598).
- [TRANSFER: ADMIRE/HIRM sensor models] Templates:
  - air data (VT, α, β, h): 1/(1 + 0.02s);
  - inertial (p, q, r, nz): (1 + 0.005346s + 0.0001903s²)/(1 + 0.03082s + 0.0004942s²);
  - attitude: 1/(1 + 0.0323s + 0.00104s²).
  — [FOI-R--1624--SE §2.6](https://www.foi.se/rest-api/report/FOI-R--1624--SE)
  - The quantified F/A-18 probe and INS error models are in `candidate_airframe_modelling_data.md` Q4/Q10, and noise texture belongs to the sensor-residual researcher.

### Inferences
- [ASSUMPTION] Recommended sensor layer for the virtual Tejas (validate against any telemetry sample the team can obtain):
  - **4× RSA:** second-order, ωn = 2π·50 rad/s, ζ ≈ 0.7; saturation ±300°/s roll and ±60°/s pitch/yaw; quantisation 0.005°/s.
  - **4× ASA:** second-order, 100 Hz; saturation ±13 g / ±4.5 g; thresholds 2 mg / 0.2 mg.
  - **Air data:**
    - 3 probes (NADP, LADP, RADP) feeding 4 ADCs, each with 4 transducers (0.02% FS);
    - 2 AoA vanes with 4 LVDTs each (±45°), plus 1 AoSS vane;
    - total air temperature (TAT) probe with heater-error terms.
  - **Position error:** functions of Mach, α, β and undercarriage state.
  - **Sampling:** 80 Hz into the DFCC, median-voted. Mistrack monitors latch failures and fall back to the fixed-gain law after multiple air-data failures.
  - **Navigation:** INGPS at 50 Hz on 1553B, plus AHRS standby.
- The heater, undercarriage and transonic position-error dependencies are realistic, documented sources of air-data residual structure for the predictive-maintenance layer.

### Gaps
- Exact sample rates per sensor in the DFCC, the 1553B update rates of INS and air-data parameters, the FDR parameter list and rates, and vane and probe dynamic response.
- Mk1A INS fit (SIGMA 95N vs indigenous) was not confirmed.
- No AoA calibration curve or position-error coefficients are public.

---

## Q6. Ground-reaction modelling inputs: gear geometry, tyres, chute, approach and landing, take-off

### Takeaway
Public ground-reaction data are thin:
- **Tricycle gear:** single main wheels retracting inward, and a steerable twin nose wheel retracting forward. Wheelbase about 4.34 m (secondary source).
- **Main wheel:** an HAL main wheel with a carbon brake is listed on the MoD portal: 26″ × 8.00″-14, 18 PR, 16.9 bar, 6,090 kg maximum static load per wheel. The platform is unnamed, but the load is consistent with Tejas MTOW.
- **Brake parachute:** the hybrid brake parachute is 17 m², deployable up to 285 km/h normal and 340 km/h emergency.
- **Landing speed:** a vendor sheet gives about 260 km/h (low confidence).
- **Gear retraction:** CLAW gain switching shows the gear is retracted by roughly 370 km/h CAS.
- **Crosswind:** trials were flown at 15–20 kt.

No official approach AoA, rotation speed, track or strut data were found.

### Cited Findings
- [DIRECT, secondary] Gear layout: "hydraulically powered, retractable tricycle gear … Two single wheels that fold inward … Steerable twin wheels that retract forward … Wheelbase: 4.34 m" — [Alpha Defense 2026](https://alphadefense.in/2026/03/10/tejas-yesterday-today-and-tommorow/). The same layout appears in [naval-technology (search snippet)](https://www.naval-technology.com/projects/hal-tejas/).
- [DIRECT, platform unnamed] HAL main wheel (MoD DDP listing):
  - "Tyre Size – 26" X 8.00"-14", 18 PR; tyre pressure 16.9 bar";
  - "Max static load/wheel – 6090 kg; Max dynamic landing load – 10200 kg; Nominal loaded radius 284 mm"; wheel mass 18 kg;
  - "designed to operate with a carbon brake".
  — [MoD DDP, Main Wheel](https://www.ddpmod.gov.in/hi/node/9654)
  - [ASSUMPTION] This is probably the Tejas Mk1/Mk1A main wheel: Tejas uses carbon-carbon brakes per [ADA GS](https://www.ada.gov.in/images/gs.htm), and 6,090 kg/wheel ≈ 0.9 × 13.5 t / 2. Confirm with HAL.
- [DIRECT] Brake parachute (hybrid, ADRDE design, Gliders India):
  - deployment speed (normal/emergency) "285 kmph / 340 Kmph";
  - mass ≈ 10 kg;
  - Uni-cross canopy, 17 m² area, 5.750 m span;
  - life "08 years or 45 streaming";
  - pilot chute 0.05 m²; auxiliary chute 0.90 m².
  — [MoD DDP, Brake Parachute (Hybrid) for LCA](https://www.ddpmod.gov.in/hi/node/8027)
  - Conflict: Wikipedia gives 340 km/h only, and a vendor sheet gives "Aircraft landing speed Normal 260 Kmph, Emergency 300 Kmph". The vendor figures may be copied from the vendor's Su-30 sheet, and the vendor page now returns 404. — [Gliders India (search snippet)](https://glidersindia.in/products/category/5/product/7)
- [DIRECT] Gear and CLAW interaction: fixed-gain CLAW gains switch with undercarriage position, with a jump in gain margin "around 370 KMPH … when undercarriage is retracted" — [JOAST 58(4) 2006](https://joast.org/index.php/joast/article/view/741).
- [DIRECT] Other ground-handling trials and studies:
  - cross-wind landing and take-off trials "in cross winds between 15–20 knots, in different heavy configurations, both symmetric and asymmetric", at Jamnagar — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf);
  - "evaluating a new landing technique while approaching at a higher angle of attack" (LSP5) and "evaluation of the new take-off technique" (LSP7) — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf);
  - "Studies on Non-linear Dynamics (LCO) of Shimmy Phenomenon in Nose Landing Gear" — [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf);
  - first flight landing "with tail chute … deployed as planned", gear down throughout — [Livefist](https://www.livefistdefence.com/25-years-on-my-recollections-of-the-1st-tejas-flight/).
  - Brake hardware (BHEEM software, wear-limited rejected take-off) is covered by the sibling utility-systems notes.
- [DIRECT] Navy: "higher sink rate (4 m/s)" clearance from RCMA (Aircraft) for shore-based test facility (SBTF) tests — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf). The Air Force variant's design sink rate was not found.

### Inferences
- [ASSUMPTION] Rough speeds from the WT lift curve:
  - Take-off at 9,800 kg rotating to α ≈ 12° (CL ≈ 0.5, with ground effect ignored and the AB thrust vertical component T·sinα ≈ 18 kN) gives lift-off ≈ 82–90 m/s (≈ 295–325 km/h).
  - Approach at 7.5–8 t with α ≈ 12–14° (CL ≈ 0.55) gives ≈ 75–77 m/s (≈ 270–280 km/h).
  - Both are consistent with chute deployment ≤ 285 km/h and the ~260 km/h vendor landing speed.
  - Validate against IAF or ADA performance data, or against squadron videos timed for ground roll.
- [ASSUMPTION] Gear model:
  - main track ≈ 2.2–2.6 m (from scaled photographs; must be measured);
  - oleo struts as nonlinear springs plus dampers (polytropic gas, n ≈ 1.1–1.3) sized for 3.05 m/s design sink rate [TRANSFER: MIL-A-8863/JSSG-2006 practice, see `flight_profiles_and_usage.md`];
  - tyre vertical stiffness from the 26×8.00-14 tyre (284 mm loaded radius);
  - nose-wheel steering with shimmy damping.

### Gaps
- Main-gear track, strut stroke, gear positions relative to the CG, nose tyre size, tail-strike angle, rotation speed, approach speed and AoA, landing distance, take-off distance and Air Force design sink rate.

---

## Q7. Performance and envelope anchors for validating a proxy aero model

### Takeaway
Several anchors are well documented in ADA and MoD sources:
- **Mach:** M1.6 cleared in operational clean configuration (OCC), and air data calibrated to M1.6.
- **Supersonic AoA and g:** 1.55 M at 4° AoA (PID); 6 g at M1.2.
- **Subsonic g and AoA:** 8.5 g at M0.87; AoA cleared to 26° at subsonic speeds in OCC.
- **High speed at sea level:** 620 kt / M0.95.
- **IOC envelope:** 1,350 km/h, 50,000 ft, 6 g, 22°.
- **Ceiling:** 15 km (ADA), 50,000 ft (MoD), 16 km (HAL, per Wikipedia).
- **Instability:** time to double amplitude 0.2 s.

The g-limit conflict resolves as follows:
- +8/−3.5 g is the IOC-era and current MoD production figure;
- +9/−3.5 g is the ADA website and Jane's figure, probably the design or structural limit;
- 8.5 g subsonic was flown and cleared in DFCC v7307.

For AoA, use 26° as the cleared operational limit. 28° is the FOC target cited by Wikipedia.

Turn rates exist only in journalism (ITR ~30°/s, STR 15–16°/s).

### Cited Findings
- [DIRECT] Supersonic and subsonic envelope clearances:
  - "Parameter Identification Trials (PIDs) … completed up to the desired Angle of Attack of 26 deg at subsonic speeds and up to 1.55 Mach/4 deg AoA at supersonic speeds";
  - "Operational Clean Configuration … envelope expansion up to the desired level of 26 degree AoA / 1.6 Mach";
  - "high 'g' manoeuvres (up to 6 g) at supersonic speeds 1.2 Mach … Trials upto 8.5g at subsonic speeds (0.87 Mach)";
  - flutter clearance with tandem 1,000 lb bombs "upto the desired speed of 620 Kts / 0.95 Mach, low level".
  — [ADA AR 2018-19, pp. 11–12](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)
- [DIRECT] Earlier clearances:
  - "Envelope expansion up to '8g' manoeuvre performance and 23 deg Angle of Attack was completed and cleared for operational clean configuration";
  - trainer "supersonic flight up to 1.3 Mach".
  — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf)
  - Navy: "+8g to −3.5g" — [ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf).
- [DIRECT] IOC: "LCA can reach speeds upto 1350 kmph, height of 50000 ft, pull 6g and reach an angle of attack of 22 degrees." — [CEMILAC note, JOAST 66(1) 2014](https://joast.org/index.php/joast/article/view/441). IOC-II reached 24°, against an FOC criterion of 28° — [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas). In 2005: "flying to AoA limits of 20° and 22° never exceed" — [AeSI FTG 2005](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf).
- [DIRECT] Headline specifications:
  - ADA Mk1 page: "Max Speed: Supersonic at all altitudes; Service Ceiling: 15 Km; g Limits: +9/−3.5" — [ADA Mk1](https://www.ada.gov.in/images/mk1.htm).
  - ADA brochure 2013: "+8/−3.5", 50,000 ft — [ADA brochure](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf).
  - MoD production portal: "G limits: +8g / −3.5g; Max speed: 1.6 Mach; Service ceiling: 50,000 feet; Engine Thrust (A/B): 85 KN; Max Takeoff Mass: 13,500 Kgs; Hard Points: 09" — [MoD DDP](https://www.ddpmod.gov.in/hi/node/6843).
  - Wikipedia spec box: M1.8 (Jane's), ceiling 16,000 m (HAL), g +9/−3.5, wing loading 255.2 kg/m², T/W 1.07 (a news source) — [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas).
  - Conflicts:
    - Max Mach is 1.6 (MoD, ADA AR) vs 1.8 (Jane's).
    - Ceiling is 15 vs 16 km.
    - T/W 1.07 implies a mass of ~8.1 t at 85 kN, whereas at 9.8 t clean T/W ≈ 0.88.
- [DIRECT, secondary] FOC: "higher g-limit of +9 g" and "increased angle of attack" — [Wikipedia, Variants](https://en.wikipedia.org/wiki/HAL_Tejas). "Capable of pulling sustained 8G turns and has a defined 26-degree Angle of Attack" (pre-FOC reporting) — [Life of Soldiers, Feb 2017](https://www.lifeofsoldiers.com/2017/02/22/after-a-stellar-performance-at-aero-india-tejas-steadily-throttles-towards-all-crucial-foc-certification).
- [DIRECT, low confidence] Turn performance: Bahrain 2016 display claims of ITR "near 30 deg/s", STR "15 to 16 deg/s" and a 350 m minimum radius. Some sources say 12°/s. Forum posts cite an ASR STR of 18°/s. — [WION](https://embed.wionews.com/photos/tejas-fighter-jet-the-aerodynamic-trick-that-makes-it-incredibly-agile-1763730595351); [DefenceXP](https://www.defencexp.com/?p=8806); [Bharat-Rakshak forum](https://forums.bharat-rakshak.com/viewtopic.php?p=1972027). Not official.
- [DIRECT] The Operational Data Manual (ODM) performance validation covered "Level Acceleration, Sustained Turn, Level Deceleration, Cruise, and Descent at different altitudes and Mach Numbers", "Max Climb rate", and "High AoA 'pushover' performance … with slats extended/retracted". The data were "accepted", but no numbers are public. — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)
- [DIRECT] Stability-margin, instability and trim anchors are in Q3/Q4: gain margin 9–17 dB, phase margin 58–68°; t₂ 0.2 s; trim α at 8 km.

### Inferences
- [ASSUMPTION] Validation envelope for the proxy:
  - Mach ≤ 1.6 (dash), ceiling ≈ 15–16 km;
  - Nz limiter +8 g operational (8.5 g available subsonic in flight-test CLAW), 6 g supersonic, −3.5 g;
  - AoA limiter 26° subsonic, with an AoA schedule decreasing to ≈ 4–6° at M1.5;
  - sea-level speed ≥ 620 kt.
  - Turn-rate checks should be treated as soft: ITR 25–30°/s near corner speed at 8 g; STR ~15°/s at low altitude.

### Gaps
- Official ITR/STR, climb rate, specific excess power (Ps) contours, acceleration times, take-off and landing distances, combat radius and fuel-flow-based range data. The ODM exists but is not public.

---

## Q8. Aero-model construction options for a tailless compound/cranked delta, evaluated against what a predictive-maintenance data layer needs; drag polar

### Takeaway
No single public database is adequate on its own.

Rescaled F-16 tables are the poorest structural match: tailed, no elevons, low Mach only. ADMIRE/GAM is the closest complete delta model with four elevons, and Indian researchers already use it as the open stand-in. Its canards, 45 m² wing and different stability levels must be neutralised. DATCOM and VSPAERO are useful only for Mach trends and missing linear derivatives:
- VSPAERO has no active vortex-lift model in the current source, so Polhamus must be added externally;
- DATCOM treats "double delta" planforms subsonically but cannot capture vortex breakdown or the Cnβ cliff, and has no real transonic methods.

The most defensible approach is a **Tejas-anchored parametric build (option f)**:
- the longitudinal core is fitted directly to the published Tejas anchors;
- lateral-directional and nonlinear shapes come from ADMIRE/GAM, cross-checked against F-106B (public tailless delta tables), ICE 101 and F-16XL data;
- Mach scaling comes from DATCOM and VSPAERO;
- drag comes from a build-up with Delta-method or DATCOM wave-drag trends;
- everything is calibrated and validated against the anchors in Q1–Q7.

### Cited Findings
**(a) F-16 TP-1538 (rescaled)**
- [DIRECT about the F-16] Low-speed tables, α −20…90°, β ±30°, no Mach effects; stabilator, flaperon, leading-edge flap (LEF) and rudder controls — [NASA TP-1538](https://ntrs.nasa.gov/citations/19800005879) (see `candidate_airframe_modelling_data.md` Q2).
- Limits for Tejas: there is no elevon-only control mapping, and tail-induced damping (Cmq) and trim characteristics differ from a tailless delta. Re-referencing does not create the delta vortex-lift shape or the 25° Cnβ cliff.

**(b) FOI ADMIRE / Saab GAM**
- [DIRECT about ADMIRE] General description:
  - "a generic small single seated, single engine fighter aircraft with a delta-canard configuration … envelope is up to Mach 1.2 and 6000 m altitude";
  - "a secondary goal was to provide the research community with an unlimited model that could freely be distributed";
  - control effectors: "left and right canard, leading edge flaps, four elevons, rudder and throttle … air brakes and … landing gear";
  - FCS: "pitch rate control below Mach number 0.58 … load factor control [≥ M0.62] … α-limiter … roll control around the velocity vector … angle of sideslip control";
  - 20 ms computer delay; first-order engine lag 0.5/(s + 0.5); thrust tables over altitude and Mach;
  - uncertainty parameters for mass, CG, inertia, aero coefficients and sensors;
  - GAM validity plots extend to Mach 2.5, with α validity shrinking with Mach (Fig. 2.2).
  - Users register at admire@foi.se. The model description is freely downloadable; current access to the model files was not verified.
  — [Forssell & Nilsson, FOI-R--1624--SE (2005)](https://www.foi.se/rest-api/report/FOI-R--1624--SE)
- [DIRECT] Indian adoption: NAL, CEMILAC and ADA researchers use ADMIRE as "open domain" stand-in for low-speed recovery, carefree protection and nonlinear-dynamic-inversion (NDI) controller design — [DSJ 72(4) 2022](https://www.publicationsdrdo.in/index.php/dsj/article/view/17821); [DSJ 73(3) 2023](https://www.publicationsdrdo.in/index.php/dsj/article/view/18402); [Lathasree, Pashilkar & Sundararajan, DSJ 74(6) 2024](https://www.publicationsdrdo.in/index.php/dsj/article/view/19488).

**(c) USAF Digital DATCOM**
- [DIRECT about DATCOM] Capabilities and limits:
  - "Straight tapered, cranked, or double delta planforms are treated";
  - "classification … as either cranked (aspect ratio > 3) or double delta (aspect ratio < 3) is relevant to only the subsonic speed regime";
  - "Transonic methods for most of the aerodynamic data do not exist. The recommended procedure requires fairing between subsonic and supersonic data";
  - "Only one high lift or control device can be analyzed at a time";
  - "ground effect methods are only applicable to longitudinal stability parameters at subsonic speeds";
  - "longitudinal methods reflect only a midwing position";
  - outputs include CLq, Cmq, CLα̇, Cmα̇, Clp, CYp, Cnp, Cnr and Clr where the methods exist.
  — [AFFDL-TR-79-3032 Vol I (Digital Datcom User's Manual), §2.4.5, §6.1.4](https://archive.org/details/DTIC_ADA086557)
  - Earlier notes record the validation gaps for subsonic high-α and transonic pitching moment — [AFWAL-TR-84-3084 via `modelling_methodology.md`](https://contrails.library.iit.edu/item/162306).
  - Tejas (A = 1.75) therefore falls in DATCOM's "double delta" class.

**(d) OpenVSP / VSPAERO + Polhamus**
- [DIRECT about the tool] What VSPAERO actually supports:
  - The current OpenVSP main-branch VSPAERO case-file keywords include `StallModel` and Karman–Tsien compressibility (`KarmanTsienCorrection_`), but **no vortex-lift / leading-edge-suction option**.
  - A Carlson-type `CalculateLeadingEdgeSuctionFraction(Mach, ToC, RoC, EtaToC, AoA, Sweep)` routine is defined in `VSP_Solver.C`, but it is **not called** anywhere in that file or in `vspaero.C`. It returns 0 for supersonic normal Mach.
  — [OpenVSP `src/vsp_aero/Solver/VSP_Solver.C`](https://github.com/OpenVSP/OpenVSP/blob/main/src/vsp_aero/Solver/VSP_Solver.C); [`vspaero.C`](https://github.com/OpenVSP/OpenVSP/blob/main/src/vsp_aero/Solver/vspaero.C) (main branch, tree sha 5240ef2…, read 13 Oct 2026)
  - VSPAERO 3.45.0 "stall implicit" with caution about validation — [OpenVSP blog](https://openvsp.org/blogs/?p=763).
- [DIRECT about the method] Polhamus suction analogy: CL = Kp·sinα·cos²α + Kv·cosα·sin²α. Kp is the potential lift-curve slope, ≈ 2.2–2.3 at A ≈ 1.75 (read from Fig. 6). For sharp-edged deltas, "the value of Kv increases slightly from a value of 3.14 for an aspect ratio of 0 to a value of about 3.45 for an aspect ratio of 4". — [Polhamus, NASA TN D-3767 (1966), eqs. 5, 12–15, Figs. 6 and 9](https://ntrs.nasa.gov/citations/19670003842)

**(e) Public databases for deltas and tailless fighters**
- [DIRECT about F-106B] The F-106B is a single-engine tailless 60° delta with elevons and a rudder.
  - "Low-speed static and dynamic forced oscillation wind tunnel tests on a 15% scale model … NASA Langley 30- by 60-foot … –5° ≤ α ≤ 50°".
  - Component build-up with CL0(α, δe), CD0(α, δe), Cm0(α, δe), CNq(α), Cmq(α), Clβ(α), Cnβ(α), Clp, Clr, Cnp, Cnr and control increments.
  - Elevator ±28°, aileron ±7°, rudder ±25°.
  - Public MATLAB code: NASA LAR-17463-1.
  — [Garza & Morelli, NASA TM-2003-212145, pp. 33–36](https://ntrs.nasa.gov/citations/20030013626)
  - Stability and control derivatives and transfer functions for the F-106B at 12 flight conditions, M0.2–2.0 and sea level to 40,000 ft (nominal W = 29,776 lb; CG about 26–30.5% MGC by condition; OCR uncertain) — [Teper, NASA CR-96008 (1969), Section IV](https://ntrs.nasa.gov/citations/19690022405). The OCR of the tables is poor, so values must be read from page images.
- [DIRECT about X-31] Cranked delta plus canard, with an F404 engine. Static data −5° ≤ α ≤ 55°, β ±18°, plus forced-oscillation dynamics — [TM-2003-212145, pp. 54–56](https://ntrs.nasa.gov/citations/20030013626).
- [DIRECT about ICE 101] Lockheed Martin "Innovative Control Effectors" tailless fighter. "A high-fidelity aerodynamic model was released based on wind tunnel tests from Lockheed Martin". It has 108 nonlinear look-up tables as functions of δ, M, α, β, p, q, r; 13 effectors (LEF, all-moving tips, spoiler-slot deflectors, pitch flaps, elevons, multi-axis thrust vectoring); a trim set M0.4–1.2 at 10–30 kft; and runs in Simulink at 100 Hz. Reference: Niestroy, Dorsett & Markstein, AIAA 2017-1757. — [arXiv 2003.06588 (Zhang et al. 2020), §IV.A](https://arxiv.org/abs/2003.06588); [doi 10.2514/6.2017-1757](https://doi.org/10.2514/6.2017-1757). ICE 101 has no vertical tail, so its directional data do not transfer. The DTIC ICE reports with "B" (limited) accession numbers were not used.
- [DIRECT about delta/double-delta supersonic data] At M1.60, 1.90 and 2.16: "Double-delta wings had lower zero-lift drag than delta wings of the same aspect ratio, while delta wings had lower drag due to lift". Trailing-edge flap pitch-control forces depended only on flap planform. The supersonic design and analysis system (SDAS) "did not consistently predict … low-sweep, low-fineness-ratio wing-body configurations". — [Wood & Covell, NASA TP-2433 (1985)](https://ntrs.nasa.gov/citations/19850021610)
- [DIRECT about the Delta Method] An empirical drag-polar method "developed from analysis of 19 subsonic and supersonic military aircraft", for clean-wing polars to buffet onset and about M2 — [Feagin & Morrison, NASA CR-151971 (1978)](https://ntrs.nasa.gov/citations/19790009630) (abstract via search; full text not read).
- Cranked-arrow F-16XL static and oscillatory data — [NTRS 19980007406](https://ntrs.nasa.gov/citations/19980007406); [NTRS 20040110955](https://ntrs.nasa.gov/citations/20040110955) (from earlier notes).

**(f) Tejas drag polar**
- [DIRECT] No Tejas CD0 or induced-drag factor (K) is public. NAL's drag-polar methods paper withholds axis values ([DSJ 51(1) 2001](https://www.publicationsdrdo.in/index.php/dsj/article/view/2208)). CFD wave drag was within 3% of WT and 10% of flight ([JOAST 57(1) 2005](https://joast.org/index.php/joast/article/view/677)).

### Inferences
**Evaluation matrix** [ASSUMPTION; 0–5 scores reflect the evidence above]

| Option | Configuration match to Tejas | Envelope (α / β / Mach) | Completeness (controls, damping, ground effect) | Calibratability to Tejas anchors | Access / legal | Effort | PdM-relevant outputs (trim δe, drag→thrust, actuator activity) | Verdict |
|---|---|---|---|---|---|---|---|---|
| (a) F-16 TP-1538 rescaled | 1 (tailed, stabilator) | 4 / 4 / 0 | 5 | 2 | 5 | Low | 2 (wrong trim-elevon physics) | Fallback only; use for post-stall shapes > 30° if ever needed |
| (b) ADMIRE/GAM, canards fixed | 3 (delta, 4 elevons, LEF, rudder; canard and 45 m² mismatch) | 3 / 2 / 3 (aero data to M2.5; FCS to M1.2) | 5 (+ actuators, sensors, FCS, uncertainty) | 3 | 3 (description public; files via FOI registration, unverified) | Medium | 4 | **Best shape and structure donor** |
| (c) Digital DATCOM | 3 (double-delta input) | 1 (linear, no breakdown) / 1 / 3 (no transonic) | 2 | 2 | 5 | Low | 2 | Mach-trend and missing-linear-derivative supplier |
| (d) VSPAERO + Polhamus | 4 (exact planform, 4 elevons) | 2 (attached flow; manual vortex lift) / 1 / 2 | 2 (no viscous drag, poor Cnβ) | 3 | 5 | Medium | 3 (hinge moments, control derivatives) | Geometry-specific control derivatives and hinge moments |
| (e) Public delta / tailless data (F-106B, ICE 101, X-31, F-16XL, TP-2433) | 3 (F-106B tailless delta; ICE finless) | 4 / 3 / 2 (Teper F-106B to M2.0) | 4 | 3 | 4 (ICE files access unclear) | Medium | 3 | Cross-check and shape library |
| **(f) Tejas-anchored parametric build** using (b)–(e) | 4 | 3 / 3 / 3 | 4 | **5** | 5 | Medium–High | **5** | **Recommended** |

**Recommended construction (f)** [ASSUMPTION; each step lists its validation]
1. **Table architecture.** Mirror the HAL "Aero Data Set" structure. Coefficients are built up from basic(α, β, M), plus per-surface increments for the left/right inboard/outboard elevons with no port/starboard coupling, rudder, slats(α, M schedule), airbrake, gear, ground effect and stores, plus dynamic derivatives (Cmq, Cmα̇, Clp, Clr, Cnp, Cnr, CYp, CYr) and hinge moments for inboard, outboard and rudder. Sources: [AeSI FTG 2004](https://web.archive.org/web/20060305025452/http://www.csirwebistad.org:80/aesi/pdf/ftgseminar05/presentations/2004/Aero%20Data.pdf); [DSJ 71(2)](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347).
2. **Longitudinal core** (Tejas data, low speed):
   - CL(α) from the Polhamus-form fit (CL0 −0.015, Kp 2.15, Kv,eff 1.9 for α ≤ 20°; Kv tapered to ~1.5 at 30°; CL still rising to ~35° then breaking);
   - Cm(α) shaped like the HAL curve, flat to 10° with a pitch-up bump at 12–16° and a nose-down break, shifted so that Cmα ≈ +0.05/rad at low speed (2% MAC unstable at CG 34% MAC);
   - Cmq ≈ −1.1 to −1.3; Cmδe ≈ −0.36 to −0.41/rad split over 4 elevons (inboard and outboard weighting from VSPAERO); CLδe ≈ 1.0/rad.
3. **Mach extension.** Apply DATCOM, VSPAERO and Prandtl–Glauert ratios to CLα, CLδe and Cmδe. Set the aerodynamic-centre shift so that the instability reproduces the NFTC t₂ map: Cmα rising to ≈ +0.3/rad at M0.6–0.8 (q-dependent) and falling through neutral at M ≈ 0.95–1.0. Use supersonic trends from Teper F-106B and TP-2433.
4. **Lateral-directional.**
   - Cnβ(α) from the Tejas Fig-4 shape (+0.05/rad flat, cliff at 25°);
   - Clβ(α) from Fig-5 (≈ −0.08/rad at 10° to −0.15/rad at 23°, full slats);
   - Cnδr = −0.0012/deg (≈ −0.069/rad) flat to 30°;
   - Clp, Cnr, Clδa, Cnδa, CYβ from ADMIRE/GAM and F-106B, scaled by S·b and checked with VSPAERO/DATCOM;
   - then tune Clδa/Cnδa and Cnβ Mach trends until a linearised model reproduces the published ARI gain trend (+3.5 at M0.26 to −0.6 at M0.7 to −0.3 at M1.3, at 6 km) with the paper's Method 1.
5. **Drag** [ASSUMPTION; validate in V9]:
   - CD = CD0(M) + K(M)·CL² up to moderate α, switching to CD ≈ CD0 + CL·tan α (zero suction, Polhamus) at high α.
   - CD0 ≈ 0.016 (M < 0.8) rising to ≈ 0.035–0.040 near M1.1–1.2, then ≈ 0.030–0.033 at M1.6.
   - K ≈ 0.30 subsonic with slats auto, ≈ 0.45 at M1.6.
   - Store, pylon and refuelling-probe increments from DATCOM or Delta-method build-up.
6. **Controls, actuators, FCS, sensors** as in Q2, Q3 and Q5.

**Validation tests** (pass criteria are proposals)
- **V1 Lift:** CL(α) at M ≈ 0.2 within ±0.03 of the digitised Tejas WT curve over α −15…30°, with CLmax still increasing to ≥ 30°.
- **V2 Trim AoA at 8 km, clean, gear up, 8.5–9.0 t:** α_trim within ±1° of 12.45° (M0.4), 6.59° (M0.6) and 2.46° (M1.0).
- **V3 Low-speed short period (M0.22/300 m, ~9.06 t, slats auto):** open-loop eigenvalues ≈ +0.26 s⁻¹ (±0.1) and −1.16 s⁻¹ (±0.3); Mδe ≈ −3.7 s⁻² (±20%).
- **V4 Instability map:** t₂ ≈ 0.2–0.3 s in M0.5–0.8 / 3–8 km; t₂ > 0.7 s below M0.3; stable or neutral above M ≈ 0.95–1.0.
- **V5 Cm derivatives:** at α 4.3° and 11.9°, Cmα = −0.014 ± 0.03 and +0.077 ± 0.03 per rad; Cmq −1.2 ± 0.3; Cmδe −0.39 ± 0.05.
- **V6 Directional:** Cnβ +0.04 to +0.06/rad for α ≤ 15°, zero crossing at 23–26°; CYM ≈ +0.013 and CRM ≈ −0.015 to −0.03 at β = 10° for α 10–23°; Cnδr −0.0012/deg ± 20%.
- **V7 ARI trend:** the paper's Method 1 on the linearised proxy gives positive ARI at M0.26/6 km and negative at M0.7 and M1.3, with magnitudes within a factor of 1.5.
- **V8 Closed loop:**
  - margins with an 8 ms delay plus 9 Hz actuators: gain margin ≥ 6 dB (target 9–17 dB) and phase margin ≥ 35° (target 58–68°); crossovers ~1 Hz (gain) and ~3 Hz (phase);
  - no actuator rate saturation for piloted 3-2-1-1 inputs (bandwidth ~1–1.5 Hz) at M0.6–0.8;
  - limiters hold 26° AoA subsonic, +8/−3.5 g, 6 g at M1.2 and ≤ 4–6° AoA at M1.55.
- **V9 Performance:**
  - with the sibling F404-IN20 thrust model: level M1.6 achievable at ~11–12 km clean; sea level ≥ 620 kt; ceiling 15–16 km;
  - soft checks: STR ≈ 15°/s and ITR ≈ 25–30°/s at low altitude;
  - fuel-flow and endurance consistent with ~2.46 t internal fuel (cross-link to the engine and fuel notes).
- **V10 Ground:**
  - lift-off ≈ 290–325 km/h at 9.8 t; approach ≈ 260–285 km/h;
  - gear retracted before ≈ 370 km/h CAS;
  - chute deploy ≤ 285 km/h normal.
- **V11 Pilot-input realism:** synthetic pilot-model stick spectra mostly < 0.25 Hz for tracking tasks (highest tracking frequency ~0.04 Hz in the flight data of [Hebbar & Pashilkar (NAL), DSJ 66(1) 2016](https://www.publicationsdrdo.in/index.php/dsj/article/view/9196)), with test-input bandwidth ~1–1.5 Hz ([JOAST 58(4) 2006](https://joast.org/index.php/joast/article/view/741)).
- **V12 Departure behaviour (optional):** beyond about 26° with the limiter off, Cnβ goes negative and a departure follows, with spin modes in the α 57–85° and 0.7–2.8 rad/s ranges. The FCS must prevent entry.

### Gaps
- Final ADMIRE model-file availability (register via admire@foi.se), ICE 101 data-file availability, and readable Teper F-106B derivative tables (needs manual page reading).
- Any public Tejas CD0, K or Ps data. The drag model remains [ASSUMPTION] until calibrated to engine thrust and the V9 performance anchors.

---

## Synthesis: key findings, parameter table, model recommendation, gaps, sources

### (a) Key findings summary
1. **Tejas data are much richer than earlier notes assumed, but scattered.** NAL, ADA and HAL authors published, often without naming the aircraft:
   - a full inertia tensor (≈ 9 t: 14,088 / 66,559 / 77,875 / 2,491 kg·m², CG 34% MAC);
   - a low-speed short-period model (unstable root +0.256 s⁻¹ at M0.22);
   - Cm derivatives from simulator and real flight large-amplitude-manoeuvre data;
   - trim AoA at 8 km;
   - stability margins from flight;
   - ARI gains vs Mach;
   - the aero-data-set architecture (430 tables, per-elevon build-up, hinge moments).

   NFTC's 2005 seminar paper adds:
   - LE sweeps of 50°/62.5° and the −4° trailing edge;
   - the WT CL(α) to 30° (CLmax still rising to ~35°);
   - a Cnβ cliff at ~25° AoA, rolling- and yawing-moment curves, and Cnδr;
   - the time-to-double map (minimum 0.2 s at M0.5–0.7, 3–8 km);
   - spin modes;
   - the 12.5 ms control cycle.

   These numbers are mutually consistent with c̄ ≈ 5.5 m.
2. **FCS architecture is documented well enough to model:**
   - quadruplex DFBW with no backup, four channels plus CCDL, 80 Hz frame and multi-rate scheduler, 8 ms computation delay;
   - median voting; quadruplex inertial, triplex air data, simplex heater monitors;
   - quadruplex ADCs over RS-422; avionics over 1553B;
   - laws gain-scheduled on Mach and altitude;
   - fixed-gain reversionary law with undercarriage-dependent gains;
   - spin-recovery mode; Flight Test Panel (RS-422 PID and 5 analogue flutter lines);
   - carefree, ALSR and disorientation-recovery features, AoA limiter;
   - CBIT, PBIT (~10 min) and MBIT; ADC BIT coverage 90%.
3. **Actuation:**
   - 13 actuators (4 elevon, 1 rudder, 6 slat, 2 airbrake);
   - primaries are Moog quadruplex-electrical, dual-hydraulic at 280 bar, with DDV; ~9 Hz response; 2–10 t stall load;
   - rudder ±30° at 100°/s; differential elevon ±18° at 45°/s;
   - Mk1A indigenous slat and airbrake modules (2024); elevon and rudder indigenisation in iron-bird test.
4. **Sensors:**
   - RSA ±300/±60°/s at 50 Hz; ASA ±13/±4.5 g at 100 Hz;
   - ADC transducers Ps 35–1,300, Pt 35–2,700 and Δp 35–1,500 mbar at 0.02% FS;
   - AoA/AoSS vanes with quadruplex LVDTs over ±45°;
   - NADP plus 2 SADP plus 2 AoA vanes, plus a TAT probe with heater and self-heating corrections; air data depends on undercarriage state;
   - SIGMA 95N laser-gyro INS/GPS plus indigenous AHRS;
   - air data calibrated to M1.6; FADS planned on a centreline drop tank.
5. **Envelope anchors (DIRECT):**
   - M1.6 / 26° AoA cleared in OCC; 1.55 M at 4° AoA (PID);
   - 8.5 g at M0.87; 6 g at M1.2; 620 kt / M0.95 at low level;
   - IOC: 1,350 km/h, 50,000 ft, 6 g, 22°;
   - g conflict resolved as +8/−3.5 operational (MoD) and +9 design/FOC (ADA website, Jane's).
6. **Model choice.** Build a Tejas-anchored parametric aero model:
   - HAL table architecture;
   - Tejas data for lift, pitch and directional cores;
   - ADMIRE/GAM and F-106B for missing lateral and nonlinear shapes;
   - DATCOM and VSPAERO (with external Polhamus) for Mach trends and hinge moments;
   - build-up drag.

   Validate with the 12 tests above. Do not use rescaled F-16 tables as the primary model.

### (b) Build-ready parameter table

| # | Parameter | Value | Unit | Tag | Source | Confidence |
|---|---|---|---|---|---|---|
| 1 | Span | 8.20 | m | DIRECT | [ADA brochure](https://www.ada.gov.in/images/IOC%20content/ADA-%20Tejas%20Brochure%20Final.pdf); [MoD DDP](https://www.ddpmod.gov.in/hi/node/6843) | High |
| 2 | Length / height | 13.20 / 4.40 | m | DIRECT | same | High |
| 3 | Wing reference area | 38.4 (38.5 in NFTC paper) | m² | DIRECT | [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas); [AeSI 2005](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf) | High |
| 4 | Aspect ratio | 1.75 | – | ASSUMPTION (b²/S) | derived | High |
| 5 | LE sweep inboard / outboard | 50 / 62.5 | deg | DIRECT (values); order inferred | [AeSI 2005 §5](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf); [Hushkit](https://hushkit.net/2019/10/02/tejas-thoughts-on-an-unusual-wing/) | Medium |
| 6 | Trailing-edge sweep | −4 (forward) | deg | DIRECT | AeSI 2005 §5 | Medium |
| 7 | Mean aerodynamic chord c̄ | 5.5 (5.2–5.9) | m | ASSUMPTION | planform integration plus derivative consistency (Q1, Q4) | Low–Medium |
| 8 | Reference CG | 33.5–34.0 | % MAC | DIRECT / DIRECT, unnamed | AeSI 2005; [DSJ 71(2)](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347) | Medium |
| 9 | Empty mass | 6,560 (LSP actual 6,682–6,802) | kg | DIRECT (conflict) | [ADA Mk1](https://www.ada.gov.in/images/mk1.htm); [CAG 17/2015 p. 50](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf) | High |
| 10 | Clean take-off / MTOW | 9,800 / 13,500 | kg | DIRECT | ADA Mk1; MoD DDP | High |
| 11 | External stores | 3,500 (ADA) vs 5,300 (HAL) | kg | DIRECT (conflict) | ADA Mk1; [Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas) | Medium |
| 12 | Internal fuel | 2,458 (3,060 L) | kg | DIRECT, secondary | Wikipedia | Medium |
| 13 | Ixx / Iyy / Izz / Ixz (at ~9,000 kg) | 14,088 / 66,559 / 77,875 / 2,491 | kg·m² | DIRECT, unnamed | DSJ 71(2) §3.5 | Medium |
| 14 | Ixy / Iyz | 162.5 / 32.5 | kg·m² | DIRECT, unnamed | DSJ 71(2) | Medium |
| 15 | Non-dim. radii of gyration R̄x / R̄y / R̄z | 0.305 / 0.412 / 0.550 | – | ASSUMPTION (derived) | from #13 | Medium |
| 16 | Time to double amplitude (min) | 0.20 (M0.5–0.7, 3–8 km) | s | DIRECT | AeSI 2005 Fig-2 | Medium–High |
| 17 | Cmα, low speed (M0.22, slats auto) | ≈ +0.05 (≈ 2% MAC unstable) | /rad | DIRECT, unnamed + derived | [DSJ 57(4)](https://www.publicationsdrdo.in/index.php/dsj/article/view/1785) | Medium |
| 18 | Cmα, high subsonic (to reproduce t₂ = 0.2 s) | ≈ +0.3 (≈ 10–11% MAC) | /rad | ASSUMPTION | derived from #16 | Low–Medium |
| 19 | Cmα at α_trim 4.3° / 11.9° / 11.55° (flight) | −0.014 / +0.077 / +0.058 | /rad (presumed) | DIRECT, unnamed | [JOAST 56(3)](https://joast.org/index.php/joast/article/view/754) | Medium |
| 20 | Cmq | −1.0 to −1.3 | – | DIRECT, unnamed | JOAST 56(3); DSJ 57(4) (derived) | Medium |
| 21 | Cmδe (low speed) | −0.36 to −0.41 | /rad | DIRECT, unnamed | same | Medium |
| 22 | CLδe (M0.22) | ≈ 0.98 | /rad | ASSUMPTION (derived) | DSJ 57(4) | Low–Medium |
| 23 | CL(α) WT: CL0 / Kp / Kv,eff | −0.015 / 2.15 / 1.9 (α ≤ 20°; Kv ≈ 1.5 to 30°) | –, /rad | DIRECT data, ASSUMPTION fit | AeSI 2005 Fig-3; [TN D-3767](https://ntrs.nasa.gov/citations/19670003842) | Medium |
| 24 | CL at 10° / 20° / 30° (low speed) | 0.41 / 0.85 / 1.15 | – | DIRECT (digitised) | AeSI 2005 Fig-3 | Medium |
| 25 | AoA for CLmax | ~35 | deg | DIRECT | AeSI 2005 §7 | Medium |
| 26 | Cnβ (α ≤ 15°) / zero crossing | +0.04 to +0.06 / 23–25° AoA | /rad, deg | DIRECT (digitised) | AeSI 2005 Fig-4 | Medium |
| 27 | Clβ (α 10° → 23°, full slats) | ≈ −0.08 → −0.15 | /rad | DIRECT (digitised, β = 10°) | AeSI 2005 Fig-5 | Low–Medium |
| 28 | Cnδr (M0.5, α −15…30°) | ≈ −0.0012 | /deg | DIRECT (digitised) | AeSI 2005 Fig-6 | Medium |
| 29 | Clp, Cnr, Clδa, Cnδa, CYβ | not public; from ADMIRE/GAM or F-106B, scaled | – | TRANSFER | [FOI-R--1624--SE](https://www.foi.se/rest-api/report/FOI-R--1624--SE); [TM-2003-212145](https://ntrs.nasa.gov/citations/20030013626) | Low |
| 30 | ARI gain at 6 km: M0.26 / 0.7 / 1.3 | +3.47 / −0.60 / −0.319 | – | DIRECT, unnamed | DSJ 71(2) Table 2 | Medium |
| 31 | Trim α at 8 km: M0.4 / 0.6 / 1.0 | 12.45 / 6.59 / 2.46 | deg | DIRECT, unnamed | [DSJ 49(3)](https://www.publicationsdrdo.in/index.php/dsj/article/view/3828) | Medium |
| 32 | CD0 (M < 0.8 / ~M1.15 / M1.6) | 0.016 / 0.035–0.040 / 0.030–0.033 | – | ASSUMPTION | V9 calibration | Low |
| 33 | Induced-drag factor K (subsonic / M1.6) | 0.30 / 0.45 | – | ASSUMPTION | Polhamus zero-suction bound K ≤ 1/Kp ≈ 0.47 | Low |
| 34 | Control surfaces | 4 elevons (IB/OB per side), 1 rudder, 6 slats (3 per side), 2 airbrakes | count | DIRECT | CAG 17/2015; [Kala](https://joast.org/index.php/joast/article/view/317) | High |
| 35 | Elevon deflection (symmetric) | ±25 | deg | DIRECT, secondary (partly corroborated) | [Alpha Defense](https://alphadefense.in/2026/03/10/tejas-yesterday-today-and-tommorow/); AeSI 2005 Fig-8 | Low–Medium |
| 36 | Differential elevon ("aileron") limit / rate | ±18 / ±45 | deg, deg/s | DIRECT, unnamed | DSJ 71(2) | Medium |
| 37 | Rudder limit / rate | ±30 / ±100 | deg, deg/s | DIRECT, unnamed + DIRECT | DSJ 71(2); AeSI 2005 | Medium–High |
| 38 | Elevon symmetric rate limit | 60–80 | deg/s | ASSUMPTION | validate in V8 | Low |
| 39 | Slat max deflection IB / MB / OB | 17.5 / 27.5 / 30 | deg | DIRECT, secondary (30° corroborated) | Alpha Defense; AeSI 2005 Fig-4 | Low–Medium |
| 40 | Actuator hydraulics / electrical redundancy | dual at 280 bar / quadruplex, DDV | – | DIRECT | Kala 2015 | High |
| 41 | Actuator frequency response / stall load | 9 / 2–10 | Hz / t | DIRECT (scope ambiguous) | Kala 2015 | Medium |
| 42 | DFCC frame / computation delay | 12.5 (80 Hz) / 8 | ms | DIRECT | Kala; AeSI 2005; [JOAST 58(4)](https://joast.org/index.php/joast/article/view/741) | High |
| 43 | Pitch-loop crossovers (gain / phase) | ~1 / ~3 | Hz | DIRECT | JOAST 58(4) | Medium–High |
| 44 | Flight gain margin / phase margin | 9.3–17.1 / 58–68 (template ≥ 6 dB / 35°) | dB / deg | DIRECT | JOAST 58(4) Table 2 | High |
| 45 | RSA range (roll / pitch-yaw), bandwidth, resolution | ±300 / ±60 deg/s, 50 Hz, 0.005 deg/s | – | DIRECT | Kala 2015 | High |
| 46 | ASA range (Nz / Ny), bandwidth, thresholds | ±13 / ±4.5 g, 100 Hz, 2 / 0.2 mg | – | DIRECT | Kala 2015 | High |
| 47 | ADC transducers Ps / Pt / Δp, accuracy | 35–1,300 / 35–2,700 / 35–1,500 mbar, 0.02% FS | – | DIRECT | Kala 2015 | High |
| 48 | AoA / AoSS vane range | ±45 (quadruplex LVDT) | deg | DIRECT | Kala 2015 | High |
| 49 | Air-data sensors | NADP + LADP/RADP + 2 AoA vanes + AoSS vane + TAT | – | DIRECT | [DSJ 56(1)](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863); [JOAST 57(1)](https://joast.org/index.php/joast/article/view/677) | High |
| 50 | Sensor redundancy | inertial and pilot command quadruplex; air data triplex; heaters simplex | – | DIRECT | Kala 2015 | High |
| 51 | ADC BIT coverage | 90 | % | DIRECT | Kala 2015 | High |
| 52 | INS | SAGEM SIGMA 95N laser-gyro INS + GPS/GLONASS; indigenous AHRS on test | – | DIRECT, secondary | [DefenceTalk](https://defencetalk.com/india-orders-over-one-hundred-sigma-95-navigation-systems-14894); [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf) | Medium |
| 53 | Wheelbase | 4.34 | m | DIRECT, secondary | Alpha Defense | Low–Medium |
| 54 | Main tyre / pressure / static load per wheel | 26×8.00-14 18PR / 16.9 bar / 6,090 kg | – | DIRECT (platform unnamed) | [MoD DDP wheel](https://www.ddpmod.gov.in/hi/node/9654) | Low–Medium |
| 55 | Brake chute area / deploy speed normal-emergency | 17 m² / 285–340 km/h | – | DIRECT | [MoD DDP chute](https://www.ddpmod.gov.in/hi/node/8027) | High |
| 56 | Landing speed (normal) | ~260 | km/h | DIRECT, vendor (possibly copied) | Gliders India snippet | Low |
| 57 | Gear retracted by | ~370 | km/h CAS | ASSUMPTION (from CLAW gain switch) | JOAST 58(4) | Low–Medium |
| 58 | Max Mach (cleared) | 1.6 (Jane's 1.8) | – | DIRECT (conflict) | [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf); MoD DDP; Wikipedia | High (1.6) |
| 59 | Service ceiling | 15 km / 50,000 ft (HAL 16 km) | – | DIRECT (conflict) | ADA Mk1; MoD DDP; Wikipedia | Medium |
| 60 | g limits | +8 / −3.5 operational; +9 design or FOC; 8.5 g flown at M0.87; 6 g at M1.2 | g | DIRECT (conflict resolved) | MoD DDP; ADA Mk1; ADA AR 2018-19 | Medium–High |
| 61 | AoA limit | 26 (subsonic, OCC); ~4 at M1.55; FOC target 28 | deg | DIRECT | ADA AR 2018-19; Wikipedia | Medium–High |
| 62 | Low-level max cleared | 620 kt / M0.95 | – | DIRECT | ADA AR 2018-19 | High |
| 63 | IOC envelope | 1,350 km/h; 50,000 ft; 6 g; 22° | – | DIRECT | [JOAST 66(1)](https://joast.org/index.php/joast/article/view/441) | High |
| 64 | ITR / STR | ~30 / 15–16 | deg/s | DIRECT, journalism | WION; DefenceXP | Low |
| 65 | Spin modes (not to be entered) | α 57–85°, 0.7–2.8 rad/s, descent 76–83 m/s | – | DIRECT | AeSI 2005 §11 | Medium |
| 66 | Engine thrust (AB, SLS) | 85 | kN | DIRECT | MoD DDP (engine model: sibling) | High |

### (c) Evaluated aero-model construction options and recommendation
See the matrix and numbered recipe in Q8.

**Recommendation:** option (f), a Tejas-anchored parametric model:
- HAL-style component build-up tables;
- longitudinal core fitted to the Tejas WT lift curve, the NAL Cm derivatives, the trim-AoA points and the time-to-double map;
- directional core from the Tejas Cnβ, CRM, CYM and Cnδr curves;
- missing lateral, damping and control derivatives from ADMIRE/GAM (primary donor; canards fixed at the GAM trim schedule and their increments excluded) and the NASA F-106B tables, scaled by S·b·c̄ and checked with VSPAERO and DATCOM;
- Mach trends from DATCOM, VSPAERO, the Teper F-106B data and TP-2433;
- drag from a CD0(M) + K(M)·CL² build-up blended to zero-suction at high α.

Reasons:
- For the predictive-maintenance data layer, the outputs that matter are trimmed α and elevon positions vs Mach, altitude and mass; thrust demand from the drag polar; and actuator stroke and rate histories. These depend most on the longitudinal core, which is exactly where Tejas-specific public anchors exist.
- Rescaled F-16 tables would systematically misrepresent tailless elevon trim, so they would misrepresent actuator duty, the variable a maintenance model consumes.
- ADMIRE alone would carry canard-delta stability and a 45 m² wing.

Acceptance: pass validation tests V1–V11 before data generation. Label every parameter in metadata with its tag (DIRECT / TRANSFER / ASSUMPTION) and source.

### (d) Open questions and gaps
1. Official MAC length and station, crank station, tip and root chords, CG limits and CG travel with fuel; Mk1A mass and inertia changes.
2. Lateral-directional damping and control derivatives (Clp, Cnr, Clδa, Cnδa, CYβ) and any Mach-dependent table. Possible sources: the AIAA GNC 2002 control-law paper (doi 10.2514/6.2002-4649) and the AIAA ATIO 2002 stability-margin paper. Both are behind AIAA paywalls.
3. Symmetric elevon range and rate, slat schedule and rate, hinge-moment coefficients, and actuator bandwidth per surface. Does "9 Hz" refer to the primaries?
4. Pitch command type, blend point, limiter algorithms and gain tables; voting thresholds and persistence; DFCC BIT coverage.
5. Tejas CD0, K and Ps data (the Operational Data Manual is not public); official STR/ITR, climb rate, take-off and landing distances, approach AoA and speed, rotation speed.
6. Gear track, strut characteristics, nose tyre, design sink rate (Air Force variant), tail-strike angle.
7. The air-data position-error and AoA calibration curves. The DRDO monograph "pre-flight calibration" was inaccessible (`drdo.gov.in` returned "inaccessible"), and nothing is archived in the Wayback Machine.
8. Mk1A navigation fit (SIGMA 95N vs indigenous) and Mk1A FCS law changes.
9. Access to ADMIRE model files (admire@foi.se), ICE 101 data files (AIAA 2017-1757 release mechanism), and readable F-106B derivative tables in Teper CR-96008.
10. NAL repository (NXDOMAIN), STO MP-SCI-162-14 (Cloudflare) and paywalled JOAST 2025–26 papers (e.g. JOAST 1141 on WT sting effects on Cm0 of a fighter at transonic speed) remain unread.

### (e) Ranked sources (most valuable first)
1. **NFTC/ADA, "An Approach to High AoA Testing of the Tejas LCA", AeSI Flight Test Seminar 2005.** Sweeps, CG, area, 12.5 ms cycle, t₂ map, CL(α), Cnβ(α), CRM/CYM, Cnδr, spin modes, CLAW and air-data behaviour in departure. [Archived PDF](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf); local `research_sources/tejas_airframe/AeSI_FTG2005_HIGH_AOA_TEJAS.pdf`.
2. **Jayalakshmi, Patel & Singh, "Relook at Aileron to Rudder Interconnect", DSJ 71(2) 2021.** Inertia tensor, CG 34% MAC, rudder and aileron limits and rates, lateral law structure, ARI vs Mach, aero-table form. [DSJ](https://www.publicationsdrdo.in/index.php/dsj/article/view/15347).
3. **Patel, Deodhare & Chetty, "Accelerated Flight Envelope Expansion Using Near Real Time Stability Margin Estimation", JOAST 58(4) 2006.** Crossovers, 8 ms delay, flight margins, fixed vs scheduled gains, undercarriage gain switch, Flight Test Panel. [JOAST](https://joast.org/index.php/joast/article/view/741).
4. **V. Kala (ADE), "Design and Development of FCS for LCA-Tejas", JOAST 67(2A) 2015.** DFCC, ADC and sensor specifications, redundancy, actuators, BIT. [JOAST](https://joast.org/index.php/joast/article/view/317).
5. **HAL ARDC (Baldev Singh & Jayasimha), "Aero-Data Set and its relevance…", AeSI FTG 2004.** LCA aero-data-set architecture and effort; AEDC/Calspan Cm(α). [Archived PDF](https://web.archive.org/web/20060305025452/http://www.csirwebistad.org:80/aesi/pdf/ftgseminar05/presentations/2004/Aero%20Data.pdf).
6. **Kamali, Pashilkar & Raol, DSJ 57(4) 2007.** Unstable short-period model at M0.22 and flight estimates at M0.7. [DSJ](https://www.publicationsdrdo.in/index.php/dsj/article/view/1785).
7. **Parameswaran, Girija & Raol, JOAST 56(3) 2004.** Cmα, Cmq and Cmδe from simulator and real large-amplitude-manoeuvre flight data. [JOAST](https://joast.org/index.php/joast/article/view/754).
8. **ADA Annual Reports 2015-16 to 2021-22.** Cleared envelope (26° AoA / M1.6, 1.55 M at 4°, 8.5 g, 6 g at M1.2, 620 kt), DFCC versions, air-data calibration to M1.6, FADS plan, AHRS. [ADA AR index](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf); local OCR in `research_sources/indian_fleet/ada/`.
9. **Rajalakshmi, Jeppu & Karunakar, DSJ 56(1) 2006.** Tejas air-data sensor set, algorithm, failure voting and reversion. [DSJ](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863).
10. **Shantha Kumar, DSJ 49(3) 1999.** Trim AoA at 8 km (ELS). [DSJ](https://www.publicationsdrdo.in/index.php/dsj/article/view/3828).
11. **FOI-R--1624--SE (ADMIRE 4.0 model description).** Proxy structure: actuators, sensors, FCS, engine, uncertainties, availability. [FOI](https://www.foi.se/rest-api/report/FOI-R--1624--SE).
12. **K.P. Singh, JOAST 57(1) 2005, and Singh et al., DSJ 60(6) 2010.** ADS sensor layout, CFD/WT/flight comparisons, wave-drag accuracy, stability-margin increments. [JOAST](https://joast.org/index.php/joast/article/view/677); [DSJ](https://www.publicationsdrdo.in/index.php/dsj/article/view/582).
13. **Krishna & Singh, DSJ 52(1) 2002.** Probe and vane location, position-error method. [DSJ](https://www.publicationsdrdo.in/index.php/dsj/article/view/2150).
14. **Garza & Morelli, NASA TM-2003-212145, and Teper, NASA CR-96008.** F-106B tailless delta and X-31 public data. [TM](https://ntrs.nasa.gov/citations/20030013626); [CR](https://ntrs.nasa.gov/citations/19690022405).
15. **Polhamus, NASA TN D-3767; Wood & Covell, NASA TP-2433; Digital DATCOM AFFDL-TR-79-3032; OpenVSP VSPAERO source.** Method capabilities and limits. [TN D-3767](https://ntrs.nasa.gov/citations/19670003842); [TP-2433](https://ntrs.nasa.gov/citations/19850021610); [DATCOM](https://archive.org/details/DTIC_ADA086557); [VSPAERO](https://github.com/OpenVSP/OpenVSP/blob/main/src/vsp_aero/Solver/VSP_Solver.C).
16. **MoD DDP product pages (LCA Tejas, main wheel, brake parachute).** Official production specifications. [LCA](https://www.ddpmod.gov.in/hi/node/6843); [wheel](https://www.ddpmod.gov.in/hi/node/9654); [chute](https://www.ddpmod.gov.in/hi/node/8027).
17. **ICE 101 public model (Niestroy et al., AIAA 2017-1757, via arXiv 2003.06588).** Tailless Mach-dependent LUT model, structure only. [arXiv](https://arxiv.org/abs/2003.06588).
18. **Secondary or low confidence:** [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas); [Alpha Defense 2026](https://alphadefense.in/2026/03/10/tejas-yesterday-today-and-tommorow/); [The Week 2024](https://www.theweek.in/news/defence/2024/11/25/lca-tejas-updates-integration-testing-of-india-made-actuators-begins.amp.html); [Livefist 2025](https://www.livefistdefence.com/25-years-on-my-recollections-of-the-1st-tejas-flight/); turn-rate journalism.
