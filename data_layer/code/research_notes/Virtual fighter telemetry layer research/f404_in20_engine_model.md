# F404-GE-IN20 (Tejas Mk1A) as a "composite F404": evidence base for a physics-based engine model (Project Phalanx)

**Purpose.** This note collects the public evidence needed to build a realistic virtual F404-GE-IN20: thermodynamic cycle, components and stations, sensors, control, steady-state calibration targets, transients, start/relight, oil and vibration, monitoring and life-usage counting, cockpit limits/cautions, deterioration and fault signatures, and existing models. It builds on `candidate_engine_and_ehm_data.md` and `addendum_engine_F404_F414_monitoring.md` and does not repeat their content except where a value is corrected or needed for the parameter table.

**Evidence tags (used on every claim).**
- **[DIRECT]** = about the F404-GE-IN20 itself.
- **[TRANSFER: X]** = from variant/platform X (F404-GE-400, -402, -102, RM12, F414, F100, generic NASA engine), with the reason it transfers and its limits.
- **[ASSUMPTION]** = engineering judgement or my own derivation, with how to validate it.
- "AGG" = number found only in an aggregator (Wikipedia, Forecast International, defence-news sites). Treat as unverified.

**How the work was done (read first).**
- Web searches: about 55 of the shared budget were used (within this researcher's ~65 share). Everything else came from direct fetches of known URLs, Crossref metadata look-ups (DOI/abstract only), archive.org DTIC mirrors and NASA NTRS PDFs already saved locally.
- Local primary documents (NASA, DTIC/ARL/DSTO, AGARD-CP-448, NAWCAD, NPS, Chalmers, SHK, NASA C-MAPSS/MAPSS) were read page-by-page; numbers that matter were checked on rendered page images where the scan OCR was unreliable. Four parallel extraction passes were run over the local corpus; their page-level citations are carried through below.
- **New downloads** (saved, read only, nothing executed) in `/Users/abishaikc/Phalanx/research_sources/f404_in20/`:
  - `ksas_2006_T50_airstart.pdf` — Jung et al., "T-50 Engine Airstart Test", J. Korean Soc. Aero. Space Sci. 34(2):90–95 (2006), F404-GE-102 FADEC airstarts and ground start.
  - `ksas_JAKO200673334943950.pdf` — DTaQ (Korea) magazine article on T-50 engine (F404-102) localised-parts durability testing.
  - `swiss_militaerjustiz_FA18_Glamondans_2015_report.pdf` — Swiss Military Justice press dossier on the 14 Oct 2015 F/A-18 crash (engine stall caution).
- **Source restrictions honoured.** Nothing from `research_sources/_restricted_do_not_cite/` (F/A-18 NATOPS, HAF F-16 manual/checklist) was opened or cited. Values that sibling notes took from the NATOPS copy are listed in Q7 with officially released replacements where found.
- **Corrections to earlier Phalanx notes (verified on page images):**
  - Henry (AGARD-CP-448 paper 37, Table 1, PDF p.402): test-cell T1 target is **266 K** (not 296 K), test-cell T5 target **834.3 K** (not 934.3 K), aircraft T5 target **871.0 K** (not 971.0 K), aircraft XN2 precision **138 rpm** — [AGARD-CP-448 p.37-4](https://archive.org/details/DTIC_ADA203800). The earlier figures were OCR errors.
  - ECU T5 trim range is **±150 °F** (≈2.5 °F per click), not "+15 °F" — [Glenny, ARL-PROP-TM-455, pp.19–20](https://archive.org/details/DTIC_ADA210374) (page image).
  - The "Powell 1991 F404 design paper" exists: S. F. Powel(l), "On the Leading Edge: Combining Maturity and Advanced Technology on the F404 Turbofan Engine", *J. Eng. Gas Turbines Power* 113:1–10 (1991), also ASME 90-GT-149 — [doi:10.1115/1.2906525](https://doi.org/10.1115/1.2906525). Abstract only (paywalled); it covers the -402, F412 and derivative/growth plans, "Building Block" component development, digital and fibre-optic controls.

---

## Q1. Cycle definition: what is published for the IN20, what is missing, which variant differences matter, and a self-consistent design point

### Takeaway
GE publishes only four IN20 cycle numbers: 19,000 lb class / 84 kN maximum (AB) thrust, 153 lb/s (70 kg/s) airflow, overall pressure ratio 28:1 and 2,365 lb (1,072 kg) weight, plus qualitative features (higher-flow fan, FADEC, single-crystal turbine blades, "latest hot-section materials", single-engine features, derived from the -402). Everything else must be transferred. The single most useful new anchor found here is an officially released 1985 Australian (ARL) table for the F404-GE-400 that gives **TIT 1,390 °C, fan PR 4.1 at 13,270 rpm, HPC PR 6.0 at 16,810 rpm, BPR 0.34, OPR 25, 142 lb/s, 10,600/16,000 lbf, SFC 0.78/1.84**; an NPS thesis gives the **-402 as fan PR 4.3, HPC PR 6.23, OPR 27, BPR 0.27, 17,775 lbf**. A hand cycle-closure (shown below) indicates that an IN20 with OPR 28, ~70 kg/s, BPR ≈0.27–0.30, fan PR ≈4.3–4.4 and combustor-exit temperature ≈1,770–1,790 K (≈+110–130 °C over the -400, consistent with the reported RM12 uplift of +105 °C) closes the mixer pressure balance and gives ≈54–57 kN dry thrust, matching the aggregator's 54.0 kN.

### Cited Findings

**IN20: what GE and Indian official sources state [DIRECT]**
- Thrust class 19,000 lb / 84 kN; airflow 153 lb/s / 70 kg/s; pressure ratio 28:1; weight 2,365 lb / 1,072 kg; length 154 in; maximum diameter 35 in; inlet diameter 28 in (sea level, standard day). The -102/103/402 column: 17,700 lb / 78.7 kN, 146 lb/s, 26:1, 2,282 lb. RM12: 18,100 lb / 80.5 kN, 152 lb/s, 27:1, 2,325 lb — [GE F404 family data sheet (2020/2022)](https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf) (local copy `engine_data/f404_f414_cycle/GE_F404_Family_Data_Sheet.pdf`).
  - The same sheet: the IN20 "incorporates GE's latest hot section materials and technologies, as well as a FADEC"; the -102/-103 FADEC is "derived from GE's F414 engine"; the -402 has "advanced technology and materials applied to the turbine and afterburner sections" — same source.
  - **No dry (MIL) thrust, BPR, fan PR, TIT, T5 limit, rotor speeds or SFC are published by GE for the IN20.**
- "Based on the F404-GE-402, the F404-GE-IN20 is the highest-rated F404 model. It includes a higher-flow fan, increased thrust, a Full Authority Digital Electronic Control (FADEC) system, single-crystal turbine blades and a variety of single-engine features"; >19,000 lb (84 kN) uninstalled thrust; 330 h Accelerated Mission Testing ≈ 1,000 flight hours; first Tejas flight with IN20 on 20 June 2008 reached Mach 1.1 — [GE press release, 20 Jun 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight).
- The IN20 is "a variant of the F404-GE-402, modified to power the single-engine LCA with redundant features and a control system with an advanced FADEC"; earlier LCA prototypes flew the F404-GE-F2J3 (from 2001) — [GE press release, 5 Feb 2004](https://www.geaerospace.com/news/press-releases/defense-engines/ge-awarded-105-million-development-contract-india).
- ADA lists "Successful Integration and Flight Testing of GE-F404-F2J3 and IN20 Engines", "Upgradation of Jet Fuel Starter for LCA Mk I", "Upgradation of Engine Ground Test Facility to test IN20 Engine", and an onboard Engine Condition Monitoring System — [ADA Propulsion page](https://www.ada.gov.in/images/ps.htm).
- CAG: the LCA Mk-I "with GE-F-404-IN20 engine" was granted 20 permanent waivers on ASR parameters it "cannot achieve"; the Empowered Committee (Oct 2007) judged a "higher capacity and bigger aero engine" necessary; the Kaveri, meant for LCA, achieved 70 kN against a requirement of 81 kN and weighed 1,235 kg against 1,100 kg — [CAG Report No. 17 of 2015, pp.2, 30–31](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf) (local `indian_fleet/CAG_17_2015_LCA.pdf`). [DIRECT for the IN20 shortfall; TRANSFER (Kaveri requirement) as the LCA's original engine-size target: 81 kN, 1,100 kg.]
- Dry thrust 12,139 lbf (54.0 kN) appears only in Wikipedia's IN20 spec block, which cites the GE data sheet — but the GE sheet does not contain it — [Wikipedia F404](https://en.wikipedia.org/wiki/General_Electric_F404) (AGG; citation does not support it). Forecast International gives exactly the same 12,140 lbst as the **RM12** dry rating ([Forecast Intl RM12 archive](https://www.forecastinternational.com/archive/disp_pdf.cfm?DACH_RECNO=989), local `engine_data/rm12/forecastintl_archived_rm12.pdf` p.1), so the "IN20 dry thrust" may be a copied RM12 value. Treat 54 kN as AGG.
- The F404-GE-F2J3 (LCA development engine) is listed at 18,100 lb / 80.5 kN in an enthusiast spec page — [milavia LCA specs](https://milavia.net/aircraft/lca/lca_specs.htm) (AGG; seen only as a search-result snippet, page not opened). GE says the F2J3 engines flew "nearly 900 flights, cumulatively covering nine engines" — [GE 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight).
- A Turkish encyclopaedia gives a maximum TIT of 1,390 °C for "the F404" ([kureansiklopedi](https://kureansiklopedi.com/tr/detay/general-electric-f404-motoru-5d6fd), AGG), which matches the ARL table below for the -400.

**F404-GE-400: officially released cycle anchors**
- ARL (Australian DoD) 1985, Fig. 3 (verified on page image) [TRANSFER: -400 → IN20 parent family; same stage count, same flowpath envelope, IN20 adds flow/temperature]:

  | Item | F404-GE-400 |
  |---|---|
  | Length / diameter | 159 in / 35 in |
  | Weight | 2,180 lb |
  | Mass flow | 142 lb/s (64.4 kg/s) |
  | Bypass ratio | 0.34 |
  | Overall pressure ratio | 25 |
  | Turbine inlet temperature | 1,390 °C (1,663 K) |
  | Max thrust AB / non-AB | 16,000 / 10,600 lbf (71.2 / 47.2 kN) |
  | SFC AB / non-AB | 1.84 / 0.78 lb/h/lbf |
  | Fan | 3 stages, PR 4.1, 13,270 rpm |
  | Compressor | 7 stages, PR 6.0, 16,810 rpm |

  Source: Frith, "The General Electric F404 – Engine of the RAAF's New Fighter", ARL-AERO-PROP-TM-426, Jul 1985, PDF p.15 — [archive.org DTIC ADA164562](https://archive.org/details/DTIC_ADA164562).
- Same source: average HPC stage temperature rise 52 °C; tip speed 1,592 ft/s; about 11 % of compressor-discharge air (≈520 °C) cools the HP nozzle guide vanes; all turbine blading cooled (convection, impingement, film); single-stage HPT and LPT chosen to cut part count at some cost in turbine efficiency; derived from the YJ101 — PDF pp.7, 9–10.
- NASA: SLS IRP ≈10,700 lbf, max AB ≈16,000 lbf, maximum corrected airflow ≈145 lbm/s — [NASA TM-1999-206572 p.3](https://ntrs.nasa.gov/citations/19990024943); "≈¼ of fan air bypassed" — [NASA TM-88273, PDF p.5](https://ntrs.nasa.gov/citations/19880010923) (wording "approximately one-quarter of the fan discharge air is bypassed" is ambiguous; read as BPR ≈0.33). [TRANSFER: -400]
- 100 % N1 = 13,270 rpm (four consistent NASA statements; see Q3) and **100 % N2 = 280 Hz one-per-rev ≈ 16,800 rpm** in the RAAF test-cell vibration system ("250 Hz ≈ 90 % N2") — [DSTO-TN-0530 (Marsden 2003)](https://archive.org/details/DTIC_ADA423658) (OCR) — consistent with ARL's 16,810 rpm compressor speed and GE's popular statement that "at full throttle the engine's fan turns at 13,200 revolutions per minute while a compressor ... can reach ... 16,800 rpm", with "core temperatures of up to 1037 degrees Celsius" (station not stated) — [GE Reports, 3 Apr 2014](https://www.ge.com/news/reports/03-04-2014sting-in-the-tail-hornets-live-to-fly-another-day). [TRANSFER: -400]

**F404-GE-402 vs -400 (NPS and Navy sources)**
- NPS thesis table (verified on page image) [TRANSFER: -402 → IN20, the IN20's stated parent]:

  | Item | -400 | -402 |
  |---|---|---|
  | Weight | 2,180 lb | 2,282 lb |
  | Bypass ratio | 0.34 | 0.27 |
  | Thrust | 16,012 lb | 17,775 lb |
  | Overall pressure ratio | 25:1 | 27:1 |
  | Fan pressure ratio | 3.9 | 4.3 |
  | Compressor pressure ratio | 6.3 | 6.23 |
  | Thrust/weight | 7.1 | 8.1 |

  Source: Stearns, "Logistics Simulations Metamodel for F404-GE-400 Engine Maintenance", NPS thesis, Dec 1998, Table II.1 (PDF p.23); the -402 (EPE) gives +11 % thrust (PDF pp.22–23) — [archive.org DTIC ADA359328](https://archive.org/details/DTIC_ADA359328).
- **Conflict:** another NPS thesis gives -400: OPR 26, BPR 0.32; -402: OPR 26, BPR 0.29, 17,700 lb, SFC 1.74 — [Schoch 2003, Table 3](https://archive.org/details/DTIC_ADA418270); GE gives the -402 as 26:1 and 146 lb/s. The flight-test report on the slotted flameholder says the -402 lights off harder "because of higher A/B temperature and velocity", that flameholder life is lower on the -402 "because of higher temperature severity", and (contradicting the tables) that the -402 has a "higher bypass ratio" — [NAWCADPAX/RTR-2001/1, pp.8–9](https://archive.org/details/DTIC_ADA407860).
- The +200 °F turbine-temperature uplift for the -402 "Core II" appears only on gaming forums — not used ([War Thunder forum](https://forum.warthunder.com/t/f-a-18-hornet-legacy-history-performance-discussion/3725?page=30), AGG, unverified).

**RM12 (closest public sibling of the IN20)**
- GE: 18,100 lb (80.5 kN), 152 lb/s (69 kg/s), 27:1, 2,325 lb, FADEC with hydromechanical backup, redundant ignition — [GE RM12 data sheet](https://www.geaerospace.com/sites/default/files/datasheet-RM12.pdf) (local `rm12/ge_datasheet_RM12.pdf`). [TRANSFER: RM12 → IN20; same 3-7-1-1 core and nacelle envelope, single-engine FADEC, nearly identical flow/OPR/thrust]
- Forecast International (AGG): dry 12,140 lbst (54.0 kN); BPR ≈0.31; fan airflow +10 % over the -400 (p.2) but +5 % on p.3 (internal conflict); OPR 27 at ≈158 lb/s (conflicts with GE's 152 lb/s); TIT *estimated* 2,600 °F (1,426 °C); **TIT +105 °C versus F404-GE-400**; DSR80 HPT blades; IN718 discs replacing René 95; CD nozzle area ratio ≈1.6:1; five main bearings; six modules — [Forecast Intl RM12](https://www.forecastinternational.com/archive/disp_pdf.cfm?DACH_RECNO=989) pp.1–4.
  - **Conflict:** +105 °C over the -400's 1,390 °C (ARL) would give ≈1,495 °C, not FI's 1,426 °C estimate. Both are plausible for different station definitions (T4 combustor exit vs T41 rotor inlet).
- RM12 fan exit temperature "188 °C at 15 °C inlet" → total-temperature ratio 1.600 → fan PR ≈4.0–4.4 for polytropic efficiency 0.85–0.90 — [Meyer 2014, Chalmers MSc, p.2](https://publications.lib.chalmers.se/records/fulltext/201537/201537.pdf) (the PR conversion is my derivation); "about 1/4 of fan air goes to the bypass" (BPR ≈0.33) — [Carlson & Gustafsson 2014, p.1](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf).
- Development papers (metadata/abstract only, paywalled): Daub, "F404/RM12 – A key step in the F404 growth plans", AIAA-85-1461 ([doi](https://doi.org/10.2514/6.1985-1461)); Larsson, Veno & Daub, "Development of the F404/RM12 for the JAS 39 Gripen", ASME 88-GT-305 ([doi](https://doi.org/10.1115/88-gt-305)).

**F404-GE-102 (T-50) and F414**
- -102: 17,700 lb class, FADEC "derived from GE's F414", single-engine safety features — [GE data sheet](https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf). It is the only other single-engine FADEC F404 with **published flight data** (airstarts, ground start; see Q6–Q7) [TRANSFER: -102 → IN20; same FADEC lineage and single-engine role].
- A T-50 localised-parts durability test ran an accelerated mission test of **550 cycles, 330 h total**, followed by teardown inspection; an outer nozzle flap cracked at ≈25 % of the test — [DTaQ (Korea) article, KoreaScience JAKO200673334943950](https://koreascience.kr/article/JAKO200673334943950.pdf). This matches GE's IN20 "330 hours of Accelerated Mission testing" ([GE 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight)), suggesting a common F404-derivative AMT standard of ≈1.67 cycles per AMT hour [ASSUMPTION].
- F414 numbers (98 kN, 170 lb/s, 30:1, BPR 0.25) are in the earlier note; they matter only as the FADEC/hot-section technology donor.

**Which differences matter for the model**
- Airflow: 142 (-400, ARL) / ≈145 corrected max (-400, NASA) → 146 (-402) → 152 (RM12) → 153 lb/s (IN20). A 5–8 % flow increase with the same 28-in inlet implies a re-bladed, higher specific-flow fan ("higher-flow fan") [DIRECT statement; magnitude derived].
- Pressure ratio 25 → 26/27 → 27 → 28; fan PR 3.9–4.1 → 4.3 → 4.0–4.4 (RM12 derived) → IN20 unknown.
- BPR 0.34 → 0.27–0.29 (-402) → 0.31–0.33 (RM12) → IN20 unknown. Sources conflict on direction.
- Hot section: René 125 → DSR80 HPT blades (-400 later) → single-crystal (IN20); TIT +105 °C for RM12 — magnitude for IN20 unknown.
- Control: analog ECU + hydromechanical MFC (-400/-402) → FADEC (RM12, -102, IN20). This changes **sensor set, resolution, sampling, fault handling and limiting logic**, not the thermodynamics.

**Self-consistent IN20 design-point proposal [ASSUMPTION — hand calculation, to be formalised in pyCycle]**
Method: ideal-gas station-by-station closure at SLS ISA, MIL and max AB, with stated assumptions: fan polytropic efficiency 0.87–0.89, HPC 0.88–0.90, HPT/LPT polytropic 0.88–0.89; combustor ΔP 5 %, η 0.99; 11 % of core flow as HP-NGV cooling (ARL), ≈7 % blade/disc cooling; bypass duct loss 3 %; mixer 2 %; dry AB duct 4 %; nozzle Cv 0.98; LHV 43.1 MJ/kg; cp 1.005 (cold) / 1.17–1.21 (hot) kJ/kg·K; 150 kW power off-take. **Check of the method on the -400 (ARL numbers):** with fan PR 4.1, HPC PR 6.0, BPR 0.34, 64.4 kg/s and T41 ≈1,600–1,660 K, the closure gives T5 ≈1,080–1,140 K (≈810–870 °C), core/bypass mixer total-pressure ratio ≈0.87–0.95 and dry thrust ≈47 kN, consistent with ARL's 10,600 lbf and NASA's measured T5 ≈1,500 °F (≈816 °C) at high power in the test cell ([CR-191195 Fig. 33](https://ntrs.nasa.gov/citations/19940032893)). Applied to the IN20:

| Quantity (SLS ISA) | Proposed value | Basis |
|---|---|---|
| Inlet mass flow W2 | 69.4–70 kg/s | GE [DIRECT] |
| OPR | 28 | GE [DIRECT] |
| Fan PR (PT21/PT2) | 4.3–4.4 | -402 4.3 (NPS), RM12 4.0–4.4 (derived) [TRANSFER] |
| HPC PR | 6.4–6.5 | 28 / fan PR [ASSUMPTION] |
| BPR | 0.27–0.30 | -402 0.27–0.29, RM12 0.31 [TRANSFER]; solved by mixer static-pressure match |
| T3 | ≈850–860 K | closure |
| T4 (combustor exit) | ≈1,770–1,790 K (≈1,495–1,520 °C) | -400 1,390 °C + RM12-type uplift ≈+105–130 °C [TRANSFER + ASSUMPTION] |
| T41 (HPT rotor inlet) | ≈1,680–1,700 K | after 11 % NGV cooling mix |
| HPT / LPT PR | ≈3.1–3.2 / ≈2.1–2.2 | closure |
| T5 at MIL (EGT, LPT exit) | ≈1,130–1,160 K (≈860–890 °C) | closure; close to the T5 limit as NASA describes ("T5 reaches its limit just prior to IRP") |
| Mixed-out T6 at MIL | ≈1,020 K | closure |
| Dry nozzle PR at MIL | ≈3.5–3.8 | closure |
| Dry gross thrust (= net at SLS) | ≈54–57 kN | closure vs AGG 54.0 kN |
| Core fuel flow at MIL | ≈1.1–1.2 kg/s (≈8,700–9,500 lb/h) | closure; idealised SFC ≈0.72 lb/h/lbf is below the -400's 0.78 and the -402's AGG 0.81, so expect real efficiencies ≈2–4 points lower |
| Max-AB T7 | ≈2,050–2,150 K | needed for 84 kN with ≈71 kg/s and ≈1,170–1,180 m/s effective jet velocity |
| AB fuel at max AB | ≈2.4–2.7 kg/s (≈19,000–21,500 lb/h) | closure with AB efficiency 0.90–0.92 |
| Max-AB SFC | ≈1.5–1.7 lb/h/lbf | closure; -400 1.84 (ARL), -402 1.74 (AGG) |

- Key closure sensitivity: with fan PR 4.4 and T41 at only 1,650 K the core total pressure at the mixer is ≈13 % below the bypass, which a real mixer would not tolerate; raising T41 to ≈1,700 K (or lowering fan PR to ≈4.0) restores balance. This is the main argument that the IN20 runs a hotter turbine than the -400, consistent with GE's "single-crystal turbine blades".
- How to validate: run the pyCycle mixed-flow example re-designed per Q11 at SLS dry, then check MIL thrust against 54 kN, T5 against the -400/-402 limit range, and max-AB thrust (as an off-design point with scheduled A8) against 84 kN; adjust T4 and fan PR.

### Inferences
- [ASSUMPTION] The IN20 cycle is best represented as "-402 core thermodynamics (fan PR ≈4.3, BPR ≈0.27–0.30) + RM12-class flow (≈70 kg/s) + ≈+100–130 °C turbine-temperature uplift (single-crystal HPT blades)". This reproduces every published IN20 number and the AGG dry thrust within ≈5 %.
- [ASSUMPTION] Because the IN20 at SLS-ISA MIL appears to sit close to its T5 limit, the virtual engine should show EGT-limited (thrust-lapsing) behaviour on hot Indian days at MIL — the signature sibling notes flagged for Jodhpur-type days. This is a strong, checkable output of the model.
- [ASSUMPTION] Do not treat 12,139 lbf as an IN20 fact; present it as "≈54 kN (AGG; consistent with closure)".

### Gaps
- IN20 dry thrust, BPR, fan PR, HPC PR, T41, T5 limits, 100 % N1/N2 rpm, SFC dry/wet: not found in any officially released source.
- Powell 1991 / ASME 90-GT-149, Larsson 1988 and Daub 1985 full texts (likely to give -402/RM12 deltas) are paywalled; only metadata/abstract read.
- The -402 BPR direction conflict (0.27 / 0.29 vs "higher bypass ratio") is unresolved.

---

## Q2. Components, stations, bearings and sumps

### Takeaway
The IN20 can be modelled with the standard F404 flowpath: 3-stage fan with variable inlet guide vanes (FVG/FIGV), 7-stage HPC with variable IGV plus stage-1–2 variable stators (CVG), annular combustor (18 fuel nozzles), single-stage HPT and LPT, forced mixer, afterburner (6 pilot + 24 main spraybars), and a hydraulically actuated, cam-linked hinged-flap CD nozzle. Five main bearings in three sumps (A, B, C); six modules plus a separate accessory gearbox. F404 documents use station 1 (engine face), 2.1 (fan exit), 2.5 (HPC inlet), 3 (HPC exit), 4 (combustor exit), 5 (LPT exit; EGT/T5), 5.58/"56" (LPT discharge measuring plane), 6 (AB inlet), 7, 8 (throat), 9 (exit). There is no published IN20-specific mechanical description; all detail is [TRANSFER: -400/-402].

### Cited Findings
- **Flowpath** [TRANSFER: -400]: 3-stage fan driven by the LPT with variable fan inlet guide vanes scheduled with rotor speed; HPC with variable IGV and two rows of variable stators scheduled with corrected compressor speed; annular combustor adapted from the CF6 with **18 fuel nozzles** and swirlers; bypass and core mixed before the afterburner; AB with **6 pilot and 24 main spraybars** and circumferential fuel modulation, with a light-off detector staging the main bars after the pilot lights; variable nozzle also varied in dry operation — [Frith 1985, PDF pp.6, 9–10](https://archive.org/details/DTIC_ADA164562).
  - Steenken et al. treat the fan stage-1 stators as variable as well; NASA TM-101702 mentions only fan IGVs plus HPC IGVs and stators 1–2 (conflict) — [TM-1999-206572 p.3](https://ntrs.nasa.gov/citations/19990024943); [TM-101702](https://ntrs.nasa.gov/citations/19900013006). The RM12 accident report says "variable guide vanes in the inlet stage, first fan stage and first compressor stages" — [SHK RM 2019:02, p.17](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf) [TRANSFER: RM12].
  - Nozzle: "hinged-flap, cam-linked exhaust nozzle ... hydraulically actuated"; three VEN actuators; VEN hydraulic power unit driven from the gearbox — [NASA TP-3001 p.3](https://ntrs.nasa.gov/citations/19900015818); [CR-191195 §3.3.6](https://ntrs.nasa.gov/citations/19940032893). RM12 nozzle area ratio ≈1.6:1 (FI, AGG).
- **Modules** [TRANSFER: -400]: Fan, HPC, Combustor, HPT, LPT, Afterburner; accessory gearbox separate — [Frith 1985 Fig. 40](https://archive.org/details/DTIC_ADA164562); [King & Tooker 1993 pp.32–33](https://archive.org/details/DTIC_ADA277918). Combustor and AB modules have no life-limited parts in CF practice — [Stemate 2002, PDF pp.15, 19–20](https://archive.org/details/DTIC_AD1003532).
- **Bearings and sumps** [TRANSFER: -400]: five numbered main bearings from the CF module breakdowns — fan module: #1 and #2 inner race (+ oil pressure transmitter, front frame); HPC module: #3 and #2 outer (+ PTO, oil cooler, CVG actuator, fuel nozzles/manifolds); HPT module: #4 (+ fan drive shaft); LPT module: #5 (+ exhaust frame) — [Stemate 2002 Annex A, PDF pp.66–68](https://archive.org/details/DTIC_AD1003532). Sumps A, B and C; C-sump redesigned with 21 fewer parts than the YJ101 — [Frith 1985 Figs. 6, 37](https://archive.org/details/DTIC_ADA164562). Bearing types (ball/roller): not found.
  - [ASSUMPTION] The usual two-spool arrangement — #1 fan thrust/roller and #2 in sump A, #3 HPC thrust ball in sump B, #4 inter-shaft/HPT roller and #5 LPT roller in sump C — is plausible but unverified; #4 is the bearing cited in in-flight shutdowns (Q8).
- **Accessory gearbox** [TRANSFER: -400]: driven by the HP (compressor) rotor; drives lube and scavenge pumps, VEN power unit, alternator (ECU power, ignition power, NH signal) and main and AB fuel pumps; customer bleed from HPC stage 7 — [TP-3001 p.3](https://ntrs.nasa.gov/citations/19900015818); [Conners 1989 (X-29 F404), NTRS 19900002425](https://ntrs.nasa.gov/citations/19900002425). The engine drives an airframe-mounted accessory drive (AMAD) through a power-take-off shaft — [AGARD-CP-448 paper 37, p.37-2](https://archive.org/details/DTIC_ADA203800); on Tejas a JFS + AMAD + PTO arrangement exists — [CAG 17/2015 p.7, footnote 4](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf) (technologies developed in the technology-demonstration phase include "Jet fuel Starter and Aircraft Mounted Accessory Gear Box") [DIRECT: Tejas].
- **Materials** [TRANSFER: -400]: fan Ti; fan discs and forward compressor spool Ti-17; HPC blades stages 1–3 Ti, 4–5 A286, 6–7 IN718; HPT nozzle M509 bands + MA754 vanes; HPT blades cast René 125, later DSR80 (≈2× life); LPT nozzle and blades cast René 80; rear compressor spool and turbine discs direct-aged IN718; retainers and aft shaft René 95; combustor liner Hastelloy X; AB casing Ti; flameholder IN625; nozzle René 41 — [Frith 1985 Figs. 30–31, PDF pp.10, 42–43](https://archive.org/details/DTIC_ADA164562). IN20: "single-crystal turbine blades" [DIRECT, GE 2008].
- **Station numbering**:
  - NASA thrust work: 0 free stream, 1 engine inlet face, 2.5 HPC inlet, 3 HPC discharge, 4 combustor discharge, 5 LPT rotor discharge, 5.58 LPT discharge measuring plane (20-probe PT rakes), 6 AB inlet, 7 nozzle inlet, 8 throat, 9 exit — [TP-3001 Fig. 2](https://ntrs.nasa.gov/citations/19900015818); TM-104247 adds 2 = fan inlet and labels 5 "LPT discharge" — [TM-104247 Fig. 3](https://ntrs.nasa.gov/citations/19920020182).
  - ARL: 1, 2.5, 3, 4, 5, 6, 7, 8, 9 — [Streatfeild 1988 App. E](https://archive.org/details/DTIC_ADA196265); station 2.1 = fan outlet duct — [Glenny 1989 p.14](https://archive.org/details/DTIC_ADA210374); station 4.2 = LPT inlet in the Jacksonville cell — [Roemer 2002 p.4](https://archive.org/details/DTIC_ADA408947).
  - In the PSL report station 1 is the airflow-measuring station and 2 the engine face (conflict) — [TM-100159 App. A](https://ntrs.nasa.gov/citations/19870020104).
  - Names used for the same EGT quantity: T5, TT5, T56, EGT, T5HA (corrected) — all LPT-exit gas temperature. There is no station 4.5 FTIT on the F404.
  - [ASSUMPTION] For Phalanx, adopt SAE AS755-style names with F404 aliases: `T1 (TT2)`, `PS21`, `T25`, `PS3`, `T5 (EGT, =TT5)`, `PT56`, `A8`, `NL (N1)`, `NH (N2)`, `FVG`, `CVG`, `WFM`, `WFAB`.

### Inferences
- [ASSUMPTION] The model architecture needs the following component elements: inlet; fan (single map, or tip/hub split if PS21 vs core inlet matters); splitter; HPC with variable geometry; bleeds (stage-7 customer bleed; NGV/blade/LPT cooling); burner; HPT; LPT; bypass duct; mixer; AB (pilot + main zones); variable CD nozzle. pyCycle's mixed-flow example has all of them except the variable geometry and AB zoning, and has an extra LPC that must be removed (Q11).
- [ASSUMPTION] Five bearings / three sumps / seven chip-detector points (Q8) are enough to drive a realistic oil-debris and vibration fault model keyed to module and bearing.

### Gaps
- IN20 mechanical differences from the -402 (fan blade count, fan diameter change, HPT blade design, cooling flows) are not public.
- Bearing types and sump pressurisation details are not public.

---

## Q3. Sensors: complete F404-family set, control vs monitoring, redundancy, types, ranges and resolution

### Takeaway
The F404-GE-400 sensor set is fully documented in public NASA/GE fibre-optic (FOCSI) reports: T1 (RTD), T2.5 (pneumatic, MFC only), T5 (2 × 4-probe Type-K harnesses, ECU averages 8 probes and drops open probes), NL (dual eddy-current pickups counting 42 fan blades, 0.7 Hz/rpm), NH (alternator winding, 0.239 Hz/rpm), FVG (LVDT), CVG (mechanical feedback to MFC), VEN/A8 (LVDT), PS3 (pneumatic), PLA (LVDT in MFC), AB UV flame detector, fuel flowmeters, oil pressure, oil tank level, one mid-frame accelerometer and seven chip detectors. The FADEC-era IN20/-102/RM12 sensor set is not public; the F414 FADEC donor and the 1982 GE F404 FADEC demonstrator show that a FADEC replaces the pneumatic/mechanical paths with electrical ones and adds model-based sensor substitution. Recorded/bus resolutions (MSDC: 16 rpm, 1 K, 0.5 psia) and noise come from AGARD-CP-448.

### Cited Findings

**Sensor table (F404-GE-400) [TRANSFER: -400 → IN20 measurement physics; FADEC changes signal path, not the sensing principle]**

| Parameter | Type / location | Range, scaling, accuracy | Used by | Source |
|---|---|---|---|---|
| T1 (TT1, CIT) | single-element RTD through front frame, hot-air de-iced; excited by ECU | FOCSI range −65 to 300 °F; NASA instrument −60 to 400 °F ±1 % FS; T1 ±2 °R with −3 °R bias in HARV airflow work | ECU: NL limit, T5 limit, FVG, AB schedules | [CR-191195 §3.3.1](https://ntrs.nasa.gov/citations/19940032893); [CR-1998-208416 §3.1.1](https://ntrs.nasa.gov/citations/19980219005); [TP-3001 Tbl 2](https://ntrs.nasa.gov/citations/19900015818); [CR-198052 p.72](https://ntrs.nasa.gov/citations/19970027377) |
| T2.5 (CIT to MFC) | single pneumatic transmitter (GE P/N 5033T50P02) on compressor mid-frame; **no electrical signal** on the -400 | −65 to 535 °F | MFC: N2 schedule, CVG | [CR-191195 §3.3.2, §3.4, §8.1.2](https://ntrs.nasa.gov/citations/19940032893) |
| T5 (TT5/T56/EGT) | two identical harnesses, 4 probes each (2 long + 2 short), upper and lower on AB case; ECU averages good probes; **open probe ignored; shorted probe reads low → fuel flow increases** | 700–1,600 °F range; total system error ±18 °F; τ ≈1.3–3.9 s vs mass flux (spec band, Q6) | ECU: T5 limiter, flameout/hot-start/post-shutdown-fire detection | [CR-1998-208416 §3.2.4, Fig. 3](https://ntrs.nasa.gov/citations/19980219005); [CR-191195 §3.3.3, §8.4](https://ntrs.nasa.gov/citations/19940032893) |
| NL (N1) | **two** eddy-current transmitters on fan frame counting 42 Ti fan-blade tips → f = 0.7 × rpm | 2,787 Hz = 30 %, 10,683 Hz = 115 % (100 % = 13,270 rpm); 1–2 Vpp at 2.8 kHz up to 6 Vpp at 10.7 kHz; NASA ±1 % (±132.7 rpm) | ECU: N1 governing, FVG schedule; any mismatch between the two inputs → fuel reduced to part power | [CR-1998-208416 §3.3.3, §7.7.3](https://ntrs.nasa.gov/citations/19980219005); [CR-191195 §4.7.2, Chit 2](https://ntrs.nasa.gov/citations/19940032893) |
| NH (N2) | separate winding on gearbox-mounted alternator (9 poles; gearbox/core 1.59091) → f = 0.239 × core rpm; same alternator powers ECU and ignition | 195–4,425 Hz (≈816–18,500 rpm) | ECU: ignition permissive 10–45 % NH, NL-sensor-failure interlock; MFC reads NH mechanically | [CR-191195 §4.8.2](https://ntrs.nasa.gov/citations/19940032893); [CR-1998-208416 §7.2.5](https://ntrs.nasa.gov/citations/19980219005) |
| FVG | single LVDT inside FVG actuator (primary + secondary) | 2.7 in stroke; ±2° ≡ ±0.108 in (≈18.5°/in); NASA instrument 0–55° ±2 % | ECU closed loop | [CR-1998-208416 §3.5.3, §7.4](https://ntrs.nasa.gov/citations/19980219005); [TP-3001 Tbl 2](https://ntrs.nasa.gov/citations/19900015818) |
| CVG (HPVG) | mechanical feedback link actuator → MFC (no electrical signal on -400) | −3.5 to 52.5° (FOCSI); −5 to +55° ±2 % (NASA) | MFC | [CR-191195 §3.3.5](https://ntrs.nasa.gov/citations/19940032893); [TP-3001 Tbl 2](https://ntrs.nasa.gov/citations/19900015818) |
| VEN / A8 | single LVDT position transmitter in separate hydraulic-fluid-cooled housing | 6.923 in stroke; A8 220–540 in² ±2 % | ECU | [CR-191195 §3.3.6](https://ntrs.nasa.gov/citations/19940032893); [TP-3001 Tbl 2](https://ntrs.nasa.gov/citations/19900015818) |
| PS3 (CDP) | pneumatic to MFC and AB control; separate IECMS P3 transducer | 0–500 psi ±0.1 % (test) | MFC accel/decel limits; AB fuel ratio units; IECMS | [TP-3001 p.4](https://ntrs.nasa.gov/citations/19900015818); [Streatfeild 1988 §5.12–5.14](https://archive.org/details/DTIC_ADA196265) |
| PT56/P5 (LPT discharge pressure) | IECMS/airframe signal ("turbine discharge pressure") | NASA rake 0–60 psia | IECMS, thrust calc | [Conners 1989 Tbl 1](https://ntrs.nasa.gov/citations/19900002425); [CR-179568 Fig. 3](https://ntrs.nasa.gov/citations/19890003885) |
| PLA | LVDT in MFC read by ECU (mechanical throttle linkage to MFC) | 0–130° ±2 % | ECU | [CR-179568 Fig. 3](https://ntrs.nasa.gov/citations/19890003885) |
| AB flame | single UV detector on AB case (200–270 nm) | on/off | ECU AB light-off logic | [CR-191195 §3.3.9, §4.9](https://ntrs.nasa.gov/citations/19940032893) |
| Fuel flows | flowmeters (WFE main; WFAB AB; WFABP pilot in test) | 0–12,000 / 0–30,000 / 0–1,500 lb/h ±2 % | IECMS / test | [TP-3001 Tbl 2](https://ntrs.nasa.gov/citations/19900015818) |
| Oil pressure | oil pressure transmitter in fan module (front frame) | psid on 1553 bus | IECMS exceedance, cockpit | [Stemate 2002 Annex A](https://archive.org/details/DTIC_AD1003532); [NAWCADPAX/RTR-2001/1 Tbl E-3](https://archive.org/details/DTIC_ADA407860) |
| Oil tank level, lube pump ΔP | liquid-level sensor; lube pump differential-pressure switch | — | airframe | [CR-179568 Fig. 3, §3.1.2](https://ntrs.nasa.gov/citations/19890003885) |
| Vibration | one piezoelectric accelerometer at mid-frame ("ECMS 4 o'clock") in flight; 3 in test cell | Q8 | IECMS (1 Hz) | [DSTO-TN-0530](https://archive.org/details/DTIC_ADA423658) |
| Chip detectors | 7 detectors + NOAP sample fitting | Q8 | maintenance | [Frith 1985 Fig. 37](https://archive.org/details/DTIC_ADA164562) |

- **Component counts on the -400** (whole engine control/monitoring): 3 pressure sensors, 3 shaft-speed sensors, 9 temperature sensors, 1 flow sensor, 1 liquid-level sensor, 5 switches, 5 torque motors, 5 solenoids, 1 rotary and 5 linear position sensors, 1 flame detector, 1 linear accelerometer — [NASA CR-179568 §3.1.2](https://ntrs.nasa.gov/citations/19890003885). [TRANSFER: -400]
- **13 engine sensors feed the IECMS, of which 5 are IECMS-only** — [Hess, AGARD-CP-448 p.2-5](https://archive.org/details/DTIC_ADA203800).
- **Bus words on the later F/A-18C (-402)**: EGT (°C), CDP (psia), turbine discharge pressure (psia), NL/NH (rpm), T1, oil pressure (psid), nozzle position (%), main fuel flow (pph), fuel inlet temperature, T5, discretes; PLA and "compressor speed lockup" from the flight control computer — [NAWCADPAX/RTR-2001/1 Tbl E-3](https://archive.org/details/DTIC_ADA407860). [TRANSFER: -402]
- **Resolution and noise (IECMS/MSDC, verified on page image)**: MSDC resolution T1 1.0 K, N1/N2 16 rpm, PS3 0.5 psia, P5 0.06 psia, T5 1.0 K; aircraft 2σ precision T1 1.3 K, XN1 154 rpm, XN2 138 rpm, PS3 1.2 psia, P5 0.14 psia, T5 2.0 K; engine-sensor 2σ in the test cell T1 0.1 K, XN1 9.6 rpm, XN2 7.2 rpm, PS3 0.7 psia, P5 0.09 psia, T5 0.6 K — [Henry, AGARD-CP-448 Tbl 1, p.37-4](https://archive.org/details/DTIC_ADA203800). "The MSDC is a significant source of precision error"; fuel-flow meters are sampled faster than they respond. [TRANSFER: -400 aircraft data chain; a FADEC will have different (likely finer) quantisation]
- **FADEC-era analogues**:
  - GE's 1982 F404 FADEC demonstrator ran standard F404 logic and added **FICA (Failure Indication and Corrective Action)**, which "utilizes a real time engine model to calculate and substitute replacement values" for failed **fan speed, core speed, compressor discharge pressure, compressor inlet temperature, LPT discharge temperature and main fuel flow**, plus actuator-failure correction and adaptive start fuel scheduling (sea-level tests at Lynn, altitude at NAPC Trenton) — [Linebrink & Vizzini, SAE 821371](https://saemobilus.sae.org/content/821371). [TRANSFER: F404 FADEC lineage → IN20; architecture of sensor substitution, not values]
  - RM12 crash-recorder engine channels: NLPC, NHPC, PLA, FVG, CVG, A8 (%), PS3C, T5 — [SHK RM 2019:02 Fig. 18](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf). [TRANSFER: RM12 FADEC naming]
  - F414 advanced IECMS: FADEC fault detection and isolation, engine-mounted master electrical chip detector — [Hood, Khan & Story 2013 pp.17–18](https://archive.org/details/DTIC_ADA585693) (from the earlier addendum).
  - IN20: FADEC "with redundant features" — [GE 2004](https://www.geaerospace.com/news/press-releases/defense-engines/ge-awarded-105-million-development-contract-india) [DIRECT]; channel count not public.
- **Common test-cell sensor faults** (Jacksonville F404 cell): OEM accelerometer harness; CVG/FVG position sensors; CIT probes; PT5 probes; EGT thermocouples; harness connections — [Roemer et al. 2002 Tbl 2](https://archive.org/details/DTIC_ADA408947). [TRANSFER: -400/-402]

### Inferences
- [ASSUMPTION] Phalanx IN20 sensor layer: T1 (RTD, dual on FADEC), T2.5 (electrical on FADEC — the -400 pneumatic path disappears), PS3 (electrical transducer, dual), T5 (8-probe average with exclusion logic), NL (dual eddy-current, 42 pulses/rev), NH (alternator, 0.239 Hz/rpm), FVG/CVG/A8 (LVDT/RVDT, dual-wound), WFM and WFAB (flowmeters), oil pressure, oil temperature, oil level, filter ΔP switch, chip detector discretes, mid-frame accelerometer. Validate with HAL/ADA documentation.
- [ASSUMPTION] Emulate the -400 failure semantics explicitly because they create realistic signatures: T5 short → fuel up / true EGT up; NL dual-sensor mismatch → part-power fallback; FICA-style model substitution on a FADEC.

### Gaps
- IN20 FADEC channel count, sensor duplication, sampling rates, bit resolution, and signal-validation thresholds: not public.
- Oil temperature sensor and filter ΔP switch existence on the F404 are inferred from generic practice and the -400 "lube pump differential pressure" switch, not documented values.

---

## Q4. Control: modes, schedules, limiters, FADEC vs hydromechanical, and a simulation-ready loop structure

### Takeaway
The -400/-402 control is documented well enough to rebuild its **structure**: below intermediate (IRP, PLA 87°) the hydromechanical MFC schedules **N2 = f(PLA, T2.5)** with **A8 = f(PLA)** and NL floating; at and above IRP the ECU **isochronously governs NL = f(T1)** (via a fuel-trim torque motor) and **modulates A8 to hold T5 on a schedule f(T1, Pamb)**; core fuel is always bounded by **acceleration and deceleration Wf/PS3 (ratio-unit) schedules**; the MFC overrides when PS3 ≤ 80 psia and the ECU when PS3 ≥ 425 psia; FVG = f(N1/√θ1) (fastest loop), CVG = f(N2/√θ2.5); the AB is commanded in Wr/PS3 ratio units with nozzle pre-opening and temporary T5 reset. No gains, bandwidths or numeric schedules (except an FVG schedule plot) are public. For the IN20 FADEC, the C-MAPSS40k pattern (scheduled PI on a power setpoint + MIN/MAX limit-regulator selection + ratio-unit accel/decel limits + integrator windup protection) is the most defensible public template.

### Cited Findings

**Hardware split and functions [TRANSFER: -400/-402]**
- Four control elements: throttle, main fuel control (MFC), electrical control unit (ECU), AB fuel control; throttle mechanically positions the MFC power lever — [TP-3001 p.3](https://ntrs.nasa.gov/citations/19900015818). The ECU is analog with trim potentiometers; it is fuel-cooled and powered by the engine alternator — [CR-1998-208416 §7.8](https://ntrs.nasa.gov/citations/19980219005); [Forsyth 1989 App. A.1.1](https://archive.org/details/DTIC_ADA219105).
- **Interface diagram** (best architecture figure) — [NASA CR-179568 Fig. 3](https://ntrs.nasa.gov/citations/19890003885):
  - MFC inputs: NH (mechanical), T2.5 (pneumatic), PS3 (pneumatic), PLA link, Mach-number signal ("NH lockup"), rocket-gas-ingestion signal ("reset comp VG").
  - MFC outputs: main Wf; desired CVG (hydraulic, mechanical feedback); AB fuel permission (hydraulic).
  - MFC ↔ ECU electrical: PLA (LVDT), ignition on, "fan VG + NL reset", A8 schedule, AB permission, **Wf trim (torque motor in MFC)**, Wf feedback (LVDT).
  - ECU outputs: desired A8 → torque motor → VEN power unit; desired FVG → torque motor → servo; **"Wr/PS3 desired" → torque motor in AB fuel control** (AB commanded in ratio units; AB control outputs main and pilot AB flows); ignition exciter control.
  - ECU inputs: NL (dual), T1, T5 harness, AB flame, NH (alternator), P0 altitude signal.
- **ECU monitor functions**: fan overspeed detection, electrical failures, stuck nozzle; power-lever override for weapons release and the approach power control system — [Forsyth 1989 p.38](https://archive.org/details/DTIC_ADA219105) (page image).
- **Trims**: N1 ±300 rpm (≈10 rpm/click), T5 ±150 °F (≈2.5 °F/click), AB ratio units ±65 — [Glenny 1989 pp.19–20](https://archive.org/details/DTIC_ADA210374). ECU test schedules named "FVG Schedule; XNL–T1 Schedule; A8–T1 Schedule; WFR Schedule; T1–T5 Schedule" — [CR-1998-208416 §10.6](https://ntrs.nasa.gov/citations/19980219005).

**Modes and limits [TRANSFER: -400]**
- ARL Fig. 28 (page image): below IRP, "N2 scheduled with PLA and trimmed by T2.5", overridden when **PS3 ≤ 80 psia**; NL floats. At IRP and above, **NL max controlled, trimmed with T1 (when P0 ≥ 10 psia), overridden when PS3 ≥ 425 psia; max T5 controlled, trimmed with T1; N2 floats**. Core fuel held between **acceleration and deceleration Wf/PS3 schedules**. A8 schedule: "idle flat, loiter, cruise flat", then a floor scheduled with PLA and T1, trimmed open by a T5 function — [Frith 1985 Fig. 28, PDF p.40](https://archive.org/details/DTIC_ADA164562).
- ARL Fig. 29: T1 regimes — T1 < 440 °R stall-margin protection; 410–530 °R maximum compressor-pressure limit; 500–650 °R turbine-inlet-temperature limit; 570–620 °R actual fan-speed limit; **cold-day corrected fan speed capped at 104.4 %** at low Mach/cold altitude — [Frith 1985 PDF p.11](https://archive.org/details/DTIC_ADA164562). This is the F404 "flat-rating / T1 bias" structure.
- NASA: below MIL "N2 and A8 are scheduled. Throttle position and compressor inlet temperature (T25) schedule N2. The throttle position schedules A8"; at MIL and above max N1 and max T56 are scheduled; "the VEN is modulated to maintain the scheduled T56 which is a function of T1 and ambient pressure" — [TM-104247 p.3](https://ntrs.nasa.gov/citations/19920020182). TP-3001 says TT1 instead of T25 (conflict; the FOCSI interface diagram supports T2.5) — [TP-3001 p.3](https://ntrs.nasa.gov/citations/19900015818).
- "During a slow throttle advance, NL reaches its scheduled limit just prior to IRP"; "T5 reaches its limit just prior to IRP ... at T5 temperatures above 1250 °F"; "NH is aerodynamically limited by maximum T5, NL, and PS3" (no NH governor above IRP) — [CR-1998-208416 §7.2.1–7.2.5](https://ntrs.nasa.gov/citations/19980219005).
- **N2 lockup**: prevents rotor-speed reduction when PLA is pulled below IRP at some conditions (driven by aircraft Mach signal); engaged at M1.2/30 kft in PSL — [TM-100159 p.8](https://ntrs.nasa.gov/citations/19870020104); [CR-179568 Fig. 3](https://ntrs.nasa.gov/citations/19890003885).
- **HARV special logic**: selectable turbine-discharge-temperature (T56) bias for extra stall margin at high AOA — [TM-104247 p.3](https://ntrs.nasa.gov/citations/19920020182). [TRANSFER: example of a T5-schedule reset used for operability]
- **AB light-off sequence**: igniters on → nozzle opens slightly above IRT position → T5 schedule temporarily reset lower → pilot + minimum main AB fuel → UV light-off detected → igniters off and main AB fuel to the throttle-selected level; augmentor "fully modulating" — [TP-3001 p.3](https://ntrs.nasa.gov/citations/19900015818).
- **AB permission in snaps** (-402): above 11,000 ft on a flight-idle→max snap the control holds fuel demand at "20.5 ratio units" (5.5 needed to start AB) and holds AB off until fan speed is within 3 % of its limit ("vapor puff" logic) — [NAWCADPAX/RTR-2001/1 p.9](https://archive.org/details/DTIC_ADA407860). [TRANSFER: -402]
- **FVG schedule (digitised, CR-198052 Fig. 31, ±1°)**: ≤73 % N1c: 47.5–52.5° (closed); 80 %: 36–40°; 90 %: 16.5–20°; 95 %: 8–12°; 100 %: −1 to +2°; 101–105 %: ≈0°; ≈108 %: 4–8.5° — [CR-198052 p.59](https://ntrs.nasa.gov/citations/19970027377). [TRANSFER: -400; IN20 "higher-flow fan" will shift it]
- **CVG**: ≈48–52° at idle → ≈1–14° at high power (two traces 10° apart in a ground sweep) — [CR-191195 Fig. 33](https://ntrs.nasa.gov/citations/19940032893). NAPC ran FVG and CVG up to 10° off schedule without distress; 1st/3rd-stage HPC blade failures were traced to one malfunctioning VG vane in high-g decelerations, where T1 lag drove CVG off schedule across a flutter boundary — [Glenny 1989 pp.15, 19–20](https://archive.org/details/DTIC_ADA210374).
- **A8**: flight idle 400 in² (fixed schedule); MIL ≈218–221 in² (HARV, GE model) or 249–298 in² (flight, TM-4538); max AB ≈343–400 in² — [TM-4240 p.5, Figs. 9–10](https://ntrs.nasa.gov/citations/19910009766); [TM-4538 Tbls 2–4](https://ntrs.nasa.gov/citations/19940010668).
- **Actuator data**: FVG stroke 2.7 in, max slew ≈80 % stroke/s (2.16 in/s) at sea level; FVG loop needs the highest bandwidth — [CR-1998-208416 §7.5–7.6](https://ntrs.nasa.gov/citations/19980219005).
- **Customer bleed limits** (HARV): ≈5 % of HPC inlet flow at ≥30 kft; up to ≈7.2 % below 30 kft between PLA 50–70°; ≈2.6–3.5 % in AB; 1 % more bleed at MIL costs ≈2 % thrust — [TM-104247 Fig. 5, p.12](https://ntrs.nasa.gov/citations/19920020182).
- **ECU/FADEC history**: a 1984 trial of GE's digital ECU (DECU) found it "not very reliable"; RM12 used a digital control "single channel plus backup" and has a "combat mode (higher T5) in the A/B range" — [Forsyth 1989 p.26](https://archive.org/details/DTIC_ADA219105) (page image). [TRANSFER: RM12 combat rating concept]

**FADEC-era behaviour [TRANSFER: RM12, -102]**
- RM12 FADEC controls fuel flow, FVG, CVG and A8; mechanical throttle cable for emergency (backup) control; **flameout detection = low T5 + falling NH → igniters on, latched until T5 recovers, ignition held on longer to confirm stable burning** — [SHK RM 2019:02 pp.17, 42](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf).
- F404-GE-102 (T-50) FADEC: **flameout declared when measured EGT is below a reference EGT scheduled on altitude and PLA AND the N2 deceleration rate exceeds a set value**; auto-relight then fires igniters independently of the pilot; the schedule had to be modified after failed auto-relights — [Jung et al. 2006, KSAS 34(2), p.92](https://koreascience.kr/article/JAKO200616039849001.pdf) (Korean; translated).

**Simulation-ready controller template [TRANSFER: NASA C-MAPSS40k / MAPSS → IN20 FADEC; structure only]**
- C-MAPSS40k: sample time 0.015 s; setpoint (Nf or EPR) from PLA, altitude, Mach, ambient; setpoint PI with Kp/Ki scheduled on altitude/Mach plus a scheduled gain before the integrator and a low-pass on the error (GM > 6 dB, PM > 45°); limit regulators (PI, constant gains) for Nf max, Nc max, Ps3 max, Ps3 min, **Ncdot acceleration schedule vs corrected Nc** and **minimum ratio unit Wf/Ps3**; selection = **MIN{setpoint, Nf max, Nc max, Ps3 max, accel} then MAX{that, Ps3 min, RU min}**; integrator anti-windup e − IFB·(Wf_reg − Wf_cmd) — [NASA TM-2010-216811 pp.2–11](https://ntrs.nasa.gov/citations/20100037768). Actuators: fuel transport delay 40 ms; FMV position loop with rate limits; VSV PI with 1 % backlash — [TM-2010-216810 p.6](https://ntrs.nasa.gov/citations/20100037767).
- C-MAPSS (90k): fan-speed demand rate limit +500/−300 rpm/s; sensor lag 50 rad/s (fan speed), FMV 20 rad/s; 75 linear designs scheduled on P2 × corrected fan speed — [NASA TM-2007-215026 pp.9–10, 33–38](https://ntrs.nasa.gov/citations/20070034949).
- MAPSS (military, low-bypass): controller 50 Hz, engine model 2,500 Hz; variable vanes open-loop scheduled; Wf, A8 and A16 from five regulators (high/medium/low power by PLA band, fan stall margin, XNL overspeed) **blended by PLA**; states XNL, XNH and TMPC (hot-section metal temperature, "heat soak") — [NASA TM-2004-212968 pp.2–3](https://ntrs.nasa.gov/citations/20040035577).

### Inferences
- [ASSUMPTION] **Recommended IN20 FADEC structure** (Phalanx):
  1. PLA → (shaped by rate limit and lag) → power demand.
  2. Below IRP: N2c demand = f(PLA) (schedule shape from -400 MFC logic), PI on Wf; A8 = f(PLA) (idle flat at ≈400 in² equivalent, closing to MIL).
  3. At/above IRP: NL demand = f(T1) (isochronous; cold-day cap 104.4 % corrected) via PI on Wf; T5 limiter via PI on A8 with T5 limit = f(T1, P0); NH floats.
  4. Limit regulators in MIN/MAX select on Wf: N1 max, N2 max, PS3 max (≈425 psia-class override), PS3 min (≈80 psia-class override), accel Wf/PS3 max = f(N2c), decel Wf/PS3 min = f(N2c), T5 max.
  5. Open-loop vanes: FVG = f(N1/√θ1) (digitised schedule), CVG = f(N2/√θ2.5).
  6. AB: zone logic with permission (N1 within 3 % of limit), pre-open A8, T5 reset, pilot then main fuel in Wr/PS3 ratio units, UV light-off confirm, light-off timers (Q6).
  7. Protection: NL overspeed, flameout detection (T5 below f(alt, PLA) AND dN2/dt below threshold) → auto-relight.
  8. Redundancy/FDIA: dual sensors with mismatch tests and model substitution (FICA).
  - Validate by reproducing NASA PSL/flight operating lines (Q5) and the TM-4240 step responses (Q6).
- [ASSUMPTION] The -400 overrides "PS3 ≤ 80 psia" and "PS3 ≥ 425 psia" can be used directly as the PS3 min/max limiter values for a composite F404, scaled by 28/25 for OPR if needed (≈90/475 psia).

### Gaps
- Numeric N2 vs PLA schedule, NL-limit vs T1 schedule, T5-limit vs T1/P0 schedule, accel/decel ratio-unit schedules, AB fuel schedules, gains and loop rates: not public for any F404 variant.
- IN20 FADEC modes (backup/reversionary behaviour, combat rating, single-engine protections) and its sample rate: not public.

---

## Q5. Steady-state calibration targets (N1, N2, T5, Wf, PS3, A8, airflow, thrust vs PLA), corrections and digitisable plots

### Takeaway
There is no public table of N1/N2/T5/Wf/PS3 vs PLA for any F404 at sea-level static. What exists, and is calibration-grade, is: (1) **corrected airflow vs corrected fan speed** from two independent NASA calibrations (agree within 0–4 %; max ≈145–146 lb/s corrected, saturating at ≈100–103 % N1c); (2) **nozzle-throat conditions at MIL in flight and on the ground** (NPR, T8 ≈935–940 K constant with altitude, W8, A8, FG) from NASA TM-4538; (3) **PSL altitude-cell thrust ratios, AB thrust ratio vs AB fuel-air ratio (1.50–1.55 at f/a 0.062–0.066)** and exhaust surveys; (4) installed ground thrust at 92 % N2 / MIL / max AB with bleed sensitivities; (5) Henry's IECMS target points (part-power take-off point: N1 10,560 rpm, N2 14,204 rpm, T5 871 K, PS3 137.9 psia, P5 24.7 psia); (6) two X-29 flight points with N1, A8, fuel flows and thrust; (7) a digitised FVG schedule and the CF-18 fault-free cross-plot axes. All are for the -400 (HARV engines also have nozzle divergent flaps removed). For the IN20 they are **shape** targets after scaling flow by 153/145 and thrust by 84/71 (max AB) — [TRANSFER: -400 → IN20].

### Cited Findings

**T1. Corrected airflow vs corrected fan speed [TRANSFER: -400; HIGH value]**
- CR-198052 Fig. 2 (outdoor Test Cell 2 with bellmouth, three down-power sweeps; airflow uncertainty 1.6 % RSS; within 1 % of the GE status-cycle model; fan speed limit raised 2.5 % for the test). Correlation line (N1c %, Wc lb/s): (20, 16) (40, 35) (65, 61.5) (75, 75) (80, 87) (90, 114) (95, 129.5) (100, 145) (105, ≈146.5) (113, ≈146). Selected data points: (56.1, 52.4) (70.0, 66.7) (80.2, 87.8) (90.6, 115.6) (95.3, 130.3) (98.6, 141.4) (100, 144.9) (102–102.9, 146.1) — [NASA CR-198052 p.18](https://ntrs.nasa.gov/citations/19970027377) (graph-read ±0.5 %/±1 lb/s).
- TM-100159 Fig. 6 (NASA Lewis PSL, engine S/N 215-209, 9 flight conditions collapse onto one curve): N1c 8,000 / 9,000 / 10,000 / 11,000 / 11,500 / 12,000 / 12,500 / 13,000 / 13,500 / 13,600–13,900 rpm → 55.8 / 63.3 / 73.8 / 91.1 / 102.3 / 114.2 / 125.3 / 137.3 / 144.8 / ≈146 lb/s — [NASA TM-100159 p.24](https://ntrs.nasa.gov/citations/19870020104) (graph-read ±1 %; normalising constant 150 lb/s).
- In flight at ≈25 kft: flight idle Wc 63.5–71.2 lb/s (≈68–71 % N1c); "85 % N1C" points 107.9–110.6 lb/s (label may be nominal; curve gives ≈101 lb/s at 85 %); MIL/min AB/max AB 144.4–146.0 lb/s (airflow unchanged by AB); windmill ≈14–16 lb/s — [CR-198052 Tbl C1, p.76](https://ntrs.nasa.gov/citations/19970027377).
- Fan-discharge static ratio: PS21/PT2 vs reference airflow — 1.10→34.0, 1.60→61.2, 2.00→80.0, 2.67→109.3, 3.00→121.8, 3.40→138.4, 3.60→145.0, 4.00→146.0 lb/s — [CR-198052 Tbl 5, p.43](https://ntrs.nasa.gov/citations/19970027377). Ground PS21/Pcell ≈3.5 at 143–146 lb/s (Fig. 3).

**T2. Nozzle conditions at MIL and part power (flight and ground) [TRANSFER: -400]**
- Climb at MIL (TM-4538 Tbl 2, IFT-deck outputs from measured engine data; throttle scale idle 35°, MIL 102°): M0.32/3,850 ft NPR 2.93, T8 1,687 °R, W8 127.6 lb/s, A8 274.6 in², FG 9,125 lbf; M0.61/7,292 ft 3.09, 1,683.6 °R, 132.7, 298.3, 9,703; M0.68/12,324 ft 3.375, 1,689.6, 116.6, 293.4, 8,810; M0.77/22,331 ft 4.42, 1,687.2, 89.2, 261.5, 7,381; M0.89/32,307 ft 5.24, 1,682.9, 66.4, 251.2, 5,726 — [NASA TM-4538 p.10](https://ntrs.nasa.gov/citations/19940010668) (page image). **MIL T8 ≈ 935–939 K at all altitudes → T5-limited nozzle control** [derived].
- Ground static, tied down at 2,350 ft (ambient not given): throttle 80/87/92/102 → NPR 2.055/2.330/2.610/2.720; T8 1,437/1,528/1,622/1,672 °R; W8 91.3/100.7/110.1/120.6 lb/s; A8 249/249/249/264 in²; **FG 4,979/6,122/7,326/8,718 lbf** — [TM-4538 Tbl 4, p.11](https://ntrs.nasa.gov/citations/19940010668).
- Level flight ≈3,800 ft: throttle 75 (M0.34) FG 5,305; 80 (M0.61) 7,119; 100 (M0.80) 12,673; 102 (M0.92) 14,289 lbf (same table set, Tbl 3).

**T3. PSL altitude-cell thrust and AB ratios [TRANSFER: -400]**
- PLA: IRP 87°, min AB 94°, AB points 100/110/120°, max AB 130°; 10-min soak at IRP; part-power points approached from above and set by N2; ≈0.20 kg/s customer bleed at MIL and above — [TM-100159 pp.3–8](https://ntrs.nasa.gov/citations/19870020104).
- Corrected gross thrust Fg/δ2 as fraction of 16,000 lbf: text values 0.475 (M0.5) and 0.50 (M0.9) at 30 kft and 12,250 rpm N1c; 0.65 (10 kft) and 0.60 (40 kft) at M0.8, 13,000 rpm; unthrottled IRP points at N1c ≈13,500–13,900 rpm with 0.79–0.88 — [TM-100159 p.8, Fig. 7](https://ntrs.nasa.gov/citations/19870020104).
- **AB thrust ratio** (corrected AB thrust / corrected IRP thrust) reaches **1.50–1.55 at AB f/a ≈0.062–0.066** (f/a defined on air left after core combustion, stoichiometric 0.06727) — [TM-100159 Fig. 8, p.15](https://ntrs.nasa.gov/citations/19870020104). Off-standard days: corrected airflow still collapses; dry corrected thrust higher on hot day, AB corrected thrust higher on cold day (Figs. 9–11).
- Exhaust survey (uncorrected, jet core): M0.9/24 kft MIL PT9 197–202 kPa, TT9 1,033–1,052 K; max AB 168–191 kPa, 1,913–2,070 K; M0.4/30 kft MIL 109–114 kPa, 971–985 K; max AB 94–106 kPa, 1,762–2,047 K — [TM-100159 Tbl II](https://ntrs.nasa.gov/citations/19870020104). Radiation-corrected peaks up to 3,750–3,800 °R (≈2,100 K) at max AB — [TM-88273 pp.11–13](https://ntrs.nasa.gov/citations/19880010923).

**T4. Installed ground thrust and bleed sensitivity (HARV, nozzle divergent flaps removed) [TRANSFER: -400]**

| Setting | Engine | Alt (ft) / ΔT (°R) | FN at zero bleed, measured / GE model (lbf) | Δthrust per lb/s bleed, meas / model |
|---|---|---|---|---|
| 92 % N2 | L | 2,084 / +34 | 6,311 / 5,875 | −125 / −97 |
| 92 % N2 | R | 2,143 / +45 | 6,079 / 5,503 | −100 / −89 |
| MIL | L | 2,093 / +11 | 8,774 / 9,194 | −177 / −245 |
| MIL | R | 2,093 / +18 | 8,690 / 9,086 | −189 / −246 |
| Max AB | L | 2,082 / +29 | 12,873 / 13,241 | −371 / −421 |
| Max AB | R | 2,094 / +34 | 12,033 / 12,983 | −344 / −428 |

Source: [NASA TM-104247 Tbl 2, p.10](https://ntrs.nasa.gov/citations/19920020182). Minimum leak bleed ≈0.7 lb/s; maximum specification bleed ≈3.0–4.2 lb/s.

**T5. IECMS target points and X-29 flight points [TRANSFER: -400]**
- Henry: test-cell target T1 266 K, XN1 10,962 rpm, XN2 14,215 rpm, PS3 209.1 psia, P5 34.5 psia, T5 834.3 K; aircraft target T1 296.1 K, XN1 10,560, XN2 14,204 rpm, PS3 137.9 psia, P5 24.7 psia, T5 871.0 K (snapshot during take-off acceleration with nozzle closed) — [AGARD-CP-448 paper 37, Tbl 1](https://archive.org/details/DTIC_ADA203800) (page image).
- X-29A F404-GE-400 in flight: 30 kft, M0.9, PLA 87°: N1 13,187 rpm, A8 231.9 in², core Wf 4,590 lb/h, PT5.6 27.95 psia, FN 4,547 lbf; 30 kft, M1.2, PLA 130°: N1 13,537 rpm, A8 420.2 in², core Wf 5,652 lb/h, AB Wf 14,107 lb/h, FN 10,477 lbf — [Conners 1989, NASA, Tbl 3](https://ntrs.nasa.gov/citations/19900002425) (OCR).
- X-29 PSL: IRT at 10,000 ft FG ≈8,497 lbf (M≈0.45) → ≈10,499 lbf (M≈0.8); max AB at 30,000 ft FG ≈13,010 lbf at M≈1.2 — [TP-3001 Fig. 14](https://ntrs.nasa.gov/citations/19900015818) (back-computed from printed uncertainty annotations).
- HARV IRP at 35 kft, M0.3–0.4: engine inlet ≈3.16 psia (likely wall static), PS21 ≈13.8 psia, CDP ≈96 psia — [TM-1999-206572 Fig. 9](https://ntrs.nasa.gov/citations/19990024943) (graph-read). Implies PS3/PT2 ≈26 at cold-day IRP [ASSUMPTION: PT2 ≈3.7 psia].
- Cruise fuel flow: F/A-18 pair at M0.56/25 kft ≈3,300–3,700 lb/h total (≈1,650–1,850 lb/h per engine) — [NASA TM-2003-210734 Fig. 9b](https://ntrs.nasa.gov/citations/20030075684) (axis mislabelled lbm/s).
- Ground test sweep (GE outdoor cell, 22 Apr 1994): T5 ≈768 °F at ground idle, **≈1,500 °F plateau at MIL and max AB**; FVG 2.50 in (idle) → 0.03–0.07 in (high power); CVG ≈48–52° → ≈1–14°; T2.5 ≈105 °F → 375–380 °F; ground-idle PLA ≈13–15° — [CR-191195 Fig. 33](https://ntrs.nasa.gov/citations/19940032893) (graph-read; transient sweep).
- **GE dynamic model at 35 kft** (HARV nozzle): M0.2 — FG ≈0.9/2.85/3.4/4.3 klbf at flight idle/MIL/min AB/max AB, NPR ≈1.5/4.05/4.35/3.75, A8 400/218/232/370 in²; M0.7 — FG ≈1.15/4.25/5.0/6.7 klbf, NPR ≈1.65/5.4/6.0/5.55, A8 400/221/228/346 in² — [TM-4240 Figs. 9–10](https://ntrs.nasa.gov/citations/19910009766) (graph-read).
- **Max-AB gross-thrust envelope table** (HARV nozzle, klbf, graph-read ±0.3), e.g. SL: 15.8 (M0) … 26.9 (M1.2) … 36.0 (M1.8); 30 kft: 5.8 … 14.6 … 22.5; 50 kft: 1.9 … 5.8 … 9.9 — [TM-4240 Fig. 4](https://ntrs.nasa.gov/citations/19910009766) (full 7 × 12 grid digitised by the extraction pass; available on request from the scratch files).

**T6. Ratings and SLS anchors (with conflicts)**
- -400 SLS: 16,000 lbf max AB (several NASA reports); MIL 10,700 lbf ([TM-1999-206572](https://ntrs.nasa.gov/citations/19990024943)) vs 10,000 lbf ([TM-4771 p.8](https://ntrs.nasa.gov/citations/19970001572)) vs 10,600 lbf ([Frith 1985](https://archive.org/details/DTIC_ADA164562)); SFC 0.78 / 1.84 lb/h/lbf (Frith) → SLS MIL core Wf ≈8,270 lb/h and max AB total ≈29,400 lb/h [derived].
- IN20: 84 kN / 19,000 lbf max AB, 70 kg/s, OPR 28 [DIRECT]; dry ≈54 kN (AGG).

**T7. Correction conventions**
- TM-100159: δ = PT/101.325 kPa, θ = TT/288.15 K at the engine face; Wc = W√θ2/δ2, N1c = N1/√θ2, Fg/δ2 (exponent 0.5) — [TM-100159 pp.12–14](https://ntrs.nasa.gov/citations/19870020104).
- CF-18 cross-plots use θ1/δ1 corrections: Wfm/(δ1√θ1) vs N2/√θ1, PS3/P1 vs N2/√θ1, T56/θ1 vs P56/P1, N2 vs N1 — [Muir et al., AGARD-CP-448 paper 7](https://archive.org/details/DTIC_ADA203800). Correcting also for variable-geometry position (FVG, CVG, A8) cuts scatter 2–3×.
- NAWCAD test-cell acceptance (bio-fuel test): "classical delta and theta" based on **screen temperature and cell ambient pressure**; fuel corrected for SG and LHV; correlations N2C vs N1C, FVG vs N1C, CVG vs N2C, EPR vs N1C, CDPC vs N2C, T5HAC vs N1C, WFC vs N2C, FN vs N1C/WFC/T5HAC, A8 vs PLA; acceptance ±1 % (speed, temperature, pressure, fuel flow, thrust), ±3° (vanes); RH limit 75 %; stabilisation 5 min — [NAWCADPAX/TR-2010/22E pp.6–9](https://archive.org/details/DTIC_ADA517278). **That report plots only % deltas; it contains no absolute engine values** (so it is not a calibration source, only a test-procedure template).
- [ASSUMPTION] For EGT the usual empirical correction is T5/θ^x with x ≈0.9–1.0; no F404 exponent is published.

**T8. Digitisable figures ranked for calibration [TRANSFER: -400]**
1. CR-198052 Fig. 2 (Wc vs N1c) — HIGH; digitised above.
2. CR-198052 Fig. 3 (Wc vs PS21/Pcell) — HIGH (fan operating-line proxy).
3. CR-198052 Fig. 31 (FVG schedule) — HIGH; digitised in Q4.
4. TM-100159 Fig. 6 (Wc vs N1c, 9 conditions) — HIGH.
5. TM-100159 Fig. 7 (Fg/δ vs N1c, altitude) — HIGH (use text anchors; symbols ambiguous).
6. TM-100159 Fig. 8a–c (AB thrust ratio vs AB f/a) — HIGH for the AB model.
7. TM-100159 Figs. 9–11 (hot/cold day) — MEDIUM-HIGH.
8. TM-4240 Fig. 4 (max-AB FG vs Mach/altitude) — HIGH for envelope shape (HARV nozzle caveat).
9. TM-4538 Tables 2–4 — exact (not plots) — HIGH.
10. TM-4240 Figs. 9–10 (step responses) — MEDIUM (Q6).
11. AGARD-CP-448 paper 7 Figs. 3–5, 11, 15–18 and paper 37 Tbl 2 (fault cross-plots and take-off indices) — HIGH for health-monitoring texture (Q10).
12. FOCSI Fig. 33 (ground sweep) — MEDIUM.

### Inferences
- [ASSUMPTION] Calibrate the IN20 model in this order: (a) fan map speed lines so Wc(N1c) reproduces the CR-198052/TM-100159 curve scaled by 153/145.5 ≈1.05 with saturation at ≈100–103 % N1c; (b) MIL T5/T8 so that mixed-out T8 at MIL is altitude-invariant (≈935–940 K for the -400; ≈1,000–1,030 K for the hotter IN20 per Q1 closure); (c) MIL and max-AB thrust to 54 kN (AGG) and 84 kN [DIRECT]; (d) AB f/a vs thrust ratio to the 1.50–1.55 shape (IN20 needs ≈1.55–1.6); (e) bleed sensitivity to ≈2 % thrust per 1 % bleed at MIL.
- [ASSUMPTION] Henry's take-off target (N1 79.6 %, N2 84.5 % of 16,810, T5 871 K, PS3 137.9 psia) is a convenient single "part-power take-off snapshot" check for the transient model.

### Gaps
- No public SLS N1/N2/T5/Wf/PS3 vs PLA table for any F404; no IN20 data of any kind.
- HARV-based thrust values are for nozzles without divergent flaps and some deteriorated engines (right engine ≈1,529 h); MIL A8 conflicts between HARV (≈220 in²) and flight (249–298 in²) data are unresolved.

---

## Q6. Transients: accelerations, decelerations, AB light-off, stall, flameout/relight, heat soak and inertias

### Takeaway
Public F404 transient evidence is: the NASA/GE simple-model constants (τ = 0.625 s dry / 0.55 s AB plus a rate limit on increasing PLA of 19.03/26.81 °/s, or 14/22 °/s in the HARV simulation), CF-18 take-off transient facts (nozzle fully closed ≈1 s after a slam and held ≈4 s, max-fuel schedule engaged above ≈50 °/s throttle rate, N1 acceleration time over the nozzle-closed window ≈0.75–1.25 s, PS3 plateau in 4–5 s), an identified fan-spool small-step time constant of ≈0.77 s, F404-402 AB light-off times (MIL→max typically 0.7–2.7 s, flight idle→max 3.6–8 s, with slow/no-light criteria), HPC-initiated surge pressure histories that self-recover within ≈0.2 s, a full RM12 FADEC bird-strike flameout trace, and F404-GE-102 (T-50) spooldown/APU-assisted/auto-relight tables. Rotor inertias, volumes and heat-soak constants are not public for any F404; they must be scaled from F100/generic data and tuned to the time constants above.

### Cited Findings
- **Simple F404 model (GE-model derived)**: PLA → first-order lag (τ 0.625 s non-AB, 0.550 s AB) with a rate limit only on increasing PLA (+19.03 °/s non-AB, +26.81 °/s AB); engine parameters respond "approximately first-order"; min-AB→max-AB faster than flight-idle→MIL; decelerations faster than accelerations; accuracy vs GE nonlinear model 3 % steady, ≈20 % (FG, FNP, NPR) and 25 % (A8) transient, worst at ≈8 s into flight idle→MIL — [NASA TM-4240 pp.3–6, Fig. 5](https://ntrs.nasa.gov/citations/19910009766). The HARV simulation uses the same τ but **14/22 °/s**, an 80 Hz engine model, and FG = 0 when lagged throttle < 15 % — [TM-110216 §4.1](https://ntrs.nasa.gov/citations/19960027892) (conflict unresolved). [TRANSFER: -400]
- MDC "QT Half" F/A-18 engine model: throttle servo gain 33 with ±56 °/s rate limit and integrator bounded 31–130°; AB thrust rate limits as functions of altitude and dynamic pressure; gyroscopic moments not modelled — [NASA TM-107601 Figs. 6.1–6.5](https://ntrs.nasa.gov/citations/19920024293). [TRANSFER: -400 installed]
- **Derived slam times** [ASSUMPTION from TM-4240 constants]: flight idle (31°) → MIL (87°) ≈2.9 s of rate-limited command plus ≈0.6 s lag; MIL → max AB (130°) ≈1.6 s + lag; idle → max AB ≈4.5–5 s (≈6 s with the HARV 14/22 °/s).
- **CF-18 take-off transients** [TRANSFER: -400]: on a slam the VEN starts closing just after throttle movement, is fully closed in ≈1 s and stays closed ≈4 s; the maximum fuel schedule is engaged above ≈50 °/s throttle rate; data repeat within ±1 % at ≥45 °/s with a cooled engine; starting speeds at the ground-idle stop have σ 4 % (fan) and 2 % (core) — [Henry, AGARD-CP-448 paper 37, pp.37-2 to 37-5](https://archive.org/details/DTIC_ADA203800). Take-off starting speed can be anywhere from ground idle to ≈90 % N2 — [Muir et al., paper 7, p.7-2](https://archive.org/details/DTIC_ADA203800).
  - N1 acceleration time over the nozzle-closed interval: band ≈1.0–1.25 s before a fuel-control adjustment, ≈0.75 s (±0.1 s) after; PS3 reaches its plateau in ≈4–5 s; left/right time-to-250 psi PS3 used as a cold-section indicator — [Muir et al., Figs. 4–5](https://archive.org/details/DTIC_ADA203800) (graph-read).
  - NAPC used a false P3 signal to slow accelerations (quoted as "from 4–5 s") to improve turbine blade life — [Glenny 1989 p.20](https://archive.org/details/DTIC_ADA210374) (OCR).
- **Identified fan-spool dynamics** [TRANSFER: -400 test cell]: for a ≈5 % fan-speed step, healthy fan-spool fit gain ≈8.41 (partly legible) and **time constant 0.77 s**; with a 60 °C EGT-harness bias: gain 22.10, τ 2.11 s; estimation needs ≥10 Hz sampling (25–50 Hz near-optimal) with N1 noise 0.2 % and Wf noise 1.5–2 % — [Merrington, AGARD-CP-448 paper 36, pp.36-4 to 36-9](https://archive.org/details/DTIC_ADA203800).
- **AB light-off (F404-GE-402 S/N 360127/360408, production flameholder)** — [NAWCADPAX/RTR-2001/1 Tbls 6, E-5, pp.13–19, 63–64](https://archive.org/details/DTIC_ADA407860) [TRANSFER: -402, the IN20 parent]:
  - MIL→max AB: mostly 0.7–2.7 s; one 5.5 s; slow light 6.1 s at 30,500 ft/150 KCAS/M0.41/T1 −35 °C.
  - Flight idle→max AB: typically 3.6–8.0 s; slow lights 9.6–13.6 s at ≈40–50 kft below 160 KCAS; one no-light at 48,250 ft/115 KCAS/M0.48/T1 −48 °C; light-off slows as T1 falls.
  - Criteria: slow light >9 s (FI→max) or >6 s (MIL→max); engine-specification no-light >15 s (FI→max) / >6 s (MIL→max); stabilisation when EGT changes <5 °C/s.
  - Flameholder durability: production 686 AB lights to failure (slotted designs 513–602).
- **Surge/stall** [TRANSFER: -400 HARV]: compressor-discharge pressure collapses from ≈85 to ≈10 psia almost instantly and recovers within ≈0.2 s (35 kft, IRP); all surges initiated in the compressor and recovered without pilot action; stalls within 2.4 s of a previous stall are "non-isolated" (engine not back in thermal equilibrium); inlet-lip-to-engine-face propagation ≈20 ms; peak circumferential distortion 0.22–0.25 exceeded the F404-400 design guidance limits by up to 25 % — [NASA TM-1999-206572 pp.18–33, Fig. 9](https://ntrs.nasa.gov/citations/19990024943).
  - Swiss F/A-18D (F404-GE-402) 14 Oct 2015: during aggressive low-speed, high-AOA manoeuvring with rapid throttle movements the left engine stalled; voice warning "engine left, engine left" and caution "L STALL"; flight-manual action: affected engine throttle to idle (reduces engine pressure and clears the stall); the power loss was visible on the engine page but the active alarm came **≈24 s late** (unexplained) — [Swiss Military Justice report, 7 Jun 2017, pp.2–3](https://www.newsd.admin.ch/newsd/message/attachments/48614.pdf) (local copy). [TRANSFER: -402]
  - Stall cockpit procedure displayed by a NASA expert-system demo: throttle to flight idle; reduce AOA; if not cleared, throttle OFF then flight idle; if persistent, EPU on, throttle off, airstart — [NASA TM-101702 Fig. 6](https://ntrs.nasa.gov/citations/19900013006). [TRANSFER: -400 F-18]
- **RM12 bird-strike flameout and rundown (FADEC, CSMU data, graph-read)** — [SHK RM 2019:02 Fig. 18, pp.38–43, 52–53](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf) [TRANSFER: RM12]:
  - At impact (304 kt, 1,400 ft, PLA ≈49°): NL ≈64 %, NH ≈80 %, T5 ≈800 K, PS3C ≈800 kPa.
  - PS3C → 138 kPa in <1 s; NH ≈64 % within ≈1 s, ≈48 % at +15 s (slower than a throttle chop because compressor work vanished); NL ≈19 % at +5 s, ≈9 % at +15 s; T5 dips to ≈756 K at +0.8 s then rises to ≈1,000 K (+6 s) and ≈1,150 K (+15 s) from aft burning at high FAR; A8 opens in steps to ≈66 % by +15 s; CVG ≈20° → ≈51°.
  - Certification: after a 0.5 kg bird, recover 90 % of max dry thrust within 4.7 s at 178 kt (35 % at 330 kt).
  - Restart: healthy engine relights automatically; windmill restart needs >350 kt; APU-assisted restart 45–85 s.
- **F404-GE-102 (T-50) airstarts** — [Jung et al. 2006, KSAS 34(2):90–95, Tables 1–2, Figs. 3–8](https://koreascience.kr/article/JAKO200616039849001.pdf) (page images; Korean) [TRANSFER: -102 FADEC, single-engine; closest public analogue of IN20 relight]:
  - Test envelope: spooldown 20–35 kft, M0.55–0.9; APU-assisted 15–20 kft, M0.35–0.8; auto-relight at 30–40 kft (M0.67 at 40 kft).
  - Spooldown airstarts (PLA OFF then back to IDLE): initial %N2 / dwell at OFF (s) / %N2 when PLA set to IDLE / %N2 at turn-around / time to idle (s): 20 kft M0.75: 83 / 10 / 50 / 43 / 12; 20 kft M0.55: 83.6 / 11.5 / 48.1 / 41 / 19.4; 25 kft M0.83: 87.3 / 13 / 53.2 / 48.5 / 15; 25 kft M0.6: 83.7 / 10 / 53.3 / 46.3 / 16.6; 30 kft M0.85: 87 / 7.4 / 60 / 52.3 / 13.8; 30 kft M0.67: 83 / 5.9 / 60 / 51.9 / 14.6; 35 kft M0.87: 78 / 2.5 / 70 / 64.3 / 8; 35 kft M0.74: 87 / 2.3 / 70 / 66.6 / 5.4; 30 kft M0.9: 89.5 / 44 / 38 / 36 / 16; 30 kft M0.8: 85 / 69 / 25 / 24 / 26 (minimum 24 % N2, still a normal relight).
  - APU-assisted (ATS engaged when N2 falls below its threshold): initial %N2 / dwell (s) / %N2 at ATS engagement / %N2 at PLA idle / time to idle (s): 20 kft M0.39: 87.7 / 58.4 / 36.2 / 34 / 22; 20 kft M0.6: 85 / 25 / 36.9 / 36 / 20; 20 kft M0.8: 76.9 / 30.4 / 39.7 / 38.5 / 17.4; 15 kft M0.35: 87.7 / 70 / 35.1 / 34 / 25; 15 kft M0.55: 87 / 23 / 35 / 34.3 / 18; 15 kft M0.75: 76.3 / 27.4 / 37 / 37.2 / 17.3.
  - Auto-relight at 40 kft M0.67: first attempts ended in a **hung start** (no response for ≈170 s) because the FADEC flameout detection was late and ignition occurred at too low an N2; after modifying the flameout-detection schedule, a PLA OFF→IDLE (≈1 s) induced flameout relit with N2 dipping from ≈85–90 % to ≈70 % and recovering in ≈10 s (graph-read).
  - Higher flight speed shortens time to idle (ram turns the rotor faster; pumping torque falls at altitude).
- **Ignition/relight logic (-400)**: ignition permissive at NH 10–45 %; T5 also used to detect main and AB flameouts, hot starts and post-shutdown fires — [CR-1998-208416 §7.2.3, §7.2.5](https://ntrs.nasa.gov/citations/19980219005). IECMS flameout detection from CDP and rotor-speed behaviour — [Paré & Muir 1998 p.4](https://archive.org/details/DTIC_ADA347270).
- **T5 thermocouple time constant (F404 spec band at 1,500 °F, graph-read)**: mass flux 5/10/15/20/25/30 lb/s·ft² → τ upper 3.9/3.0/2.5/2.25/2.05/1.97 s, lower 2.6/2.0/1.7/1.5/1.35/1.25 s; measured points ≈2.9 s at 8.5, ≈2.1 s at 20, ≈1.75 s at 28 lb/s·ft² — [CR-1998-208416 Fig. 3](https://ntrs.nasa.gov/citations/19980219005). [TRANSFER: -400; directly usable sensor dynamics]
- **Inertias, volumes, heat soak (no F404 data)**:
  - F100-PW-100(3) real-time model: I_H 565.35 and I_L 610.00 N·cm·s² (≈5.65 and 6.10 kg·m²); volumes V3 0.0468, V4 0.0468, V4.1 0.6561, V6 0.8470, V7 0.7128, V13 1.427 m³; T3 and T13 lags 0.05 s; digital update ≈7.5 ms — [NASA TP-1034 Tbl I, pp.6, 47](https://ntrs.nasa.gov/citations/19770024210). [TRANSFER: method only]
  - Generic 100 kg/s mixed-flow engine assumed I_LP 30, I_HP 20 kg·m² with results insensitive to ×2/÷2 changes — Grönstedt 2000 PhD thesis (Chalmers, GESTPAN), pp.61–65 — local copy `research_sources/engine_data/rm12/chalmers_2000_gronstedt_phd.pdf` (online URL not captured).
  - MAPSS keeps a **hot-section metal temperature state TMPC (heat soak)**; Litt et al.'s F100 piecewise-linear model has "burner exit slow-response temperature" and "fan-turbine-inlet slow-response temperature" states — [MAPSS TM-2004-212968 p.2](https://ntrs.nasa.gov/citations/20040035577); [Litt 1989](https://ntrs.nasa.gov/citations/19890011624).
  - A stall within 2.4 s of a previous one is "non-isolated" because the engine had not re-established thermal equilibrium — [TM-1999-206572 p.29](https://ntrs.nasa.gov/citations/19990024943) — qualitative evidence that heat soak matters on F404 time scales.

### Inferences
- [ASSUMPTION] Start from F100 inertias scaled by mass flow to the power ≈1.5 (F404/F100 ≈ 0.55–0.6): I_HP ≈3 kg·m², I_LP ≈3.5 kg·m² for the IN20, then tune so that (a) an idle→MIL slam with the IN20 controller gives N1 rise ≈3–4 s and NPR/FG within the TM-4240 envelope, (b) the nozzle-closed take-off acceleration window gives N1 acceleration time ≈0.8–1.2 s, and (c) a small fuel step gives fan-spool τ ≈0.8 s near 90 % N1. Validate against TM-4240 Figs. 9–10 and Muir Figs. 4–5.
- [ASSUMPTION] Model heat soak with one lumped HPT/combustor metal-temperature state (τ ≈ tens of seconds) feeding tip-clearance and a T5 offset, as MAPSS TMPC does; tune so that a hot re-slam shows slightly slower acceleration and higher T5 overshoot (CF-18 "re-slam" shifts, Q10).
- [ASSUMPTION] Use the T-50 tables directly as IN20 relight acceptance targets: spooldown relight N2 floor ≥24 %, time-to-idle 5–26 s, APU/JFS-assisted engagement at ≈35–40 % N2 and 17–25 s to idle.

### Gaps
- No public F404 rotor inertias, volumes, heat-soak time constants or acceleration schedules; no IN20 transient data.
- No public F404 relight envelope (F/A-18 envelope is in the restricted NATOPS); the T-50 test-point plot gives only the tested points, not the boundary.

---

## Q7. Start and shutdown (Tejas JFS GTSU-110, start sequence, idle values) and replacement of NATOPS-derived values

### Takeaway
Tejas starts its IN20 with HAL's **GTSU-110 jet fuel starter** (twin-shaft gas turbine, 110 kW, 52 kg) through the aircraft-mounted accessory gearbox; it is also used for in-flight relight assistance. Official Indian sources (CAG 2015, HAL/DRDO statements) document the ASR requirement of ≥2 consecutive starts (IAF wants 3: two main-engine starts plus a dry rollover), GTSU-110 M1's failure to prove three consecutive starts in Leh trials (2013–14), excess JFS oil consumption, and the eventual Jan 2015 success at −15 °C with an 85 %-charged battery after 18–42 h cold soak — achieved partly by "several control patches" to the **IN20 start-up control schedule**. No IN20 start timeline (light-off N2, EGT peak, time to idle) is public. The best public F404-family start timeline is the F404-GE-102 ground start in the T-50 paper (rotation → throttle to idle at ≈20 % N2 → light-off ≈27 s → starter cut-out at ≈55 % N2 → idle ≈63 % N2 at ≈40 s). Several idle/MIL bands that sibling notes took from the F/A-18 NATOPS could only be partly replaced from officially released sources (table below).

### Cited Findings

**Tejas JFS and start requirements [DIRECT]**
- "The Jet Fuel Starter (JFS) for starting the main engine of Light Combat Aircraft (LCA) is a twin shaft gas turbine consisting of a centrifugal compressor driven by an axial turbine, reverse flow combustor, digital electronic fuel control system and a free power turbine providing the motive power for starting"; power 110 kW, weight 52 kg, length 0.64 m, intake diameter 0.29 m; manufacturer HAL — [Department of Defence Production, GTSU-110 (LCA)](https://www.ddpmod.gov.in/hi/node/8778).
- CAG (official audit): JFS performance "becomes very critical particularly while operating in the Himalayan Terrain, where the temperature goes below (–) 16 degrees centigrade. As per the ASR, the LCA power plant and intake should permit at least two consecutive starts"; ADA approached HAL Engine Design Bureau in Nov 1984; first JFS unit delivered Feb 1994, 12 units from Aug 2002 (Rs 25.81 crore); GTSU-110 had two-consecutive-start capability; IAF later required **three consecutive starts "to cater for two main engine starts and dry rollover in-between"**; modified **GTSU 110 M1** (sanctioned Sept 2011) "could not be proved for the mandatory three consecutive starts in the high altitude trials and in cold weather trials held in January 2013 and January 2014 respectively at Leh"; "excessive oil consumption by JFS beyond permitted levels" seen at Bangalore (Jan 2014); **GTSU 110 M2** mooted (2014); early SP aircraft delivered with the original JFS — [CAG Report No. 17 of 2015, pp.34–35](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
- HAL chairman (Feb 2015): "three consecutive starts using indigenous gas turbine starter at −15 °C with 85 % charged battery", aircraft "cold soaked for 18–20 hours (even 42 hours on one occasion)" with no heating; rig trials with a modified starting schedule at Leh (3,260 m) in Jul–Aug 2014; start capability demonstrated at 5,600 m (rig) — [Indian Defence Review, 2 Feb 2015](https://indiandefencereview.com/lca-tejas-passes-cold-weather-test-at-leh/) (secondary report of HAL statement). A DRDO statement quoted in the same coverage says the JFS "control software ... was fine tuned to work at all operating altitudes with no adjustments from cockpit" and that the "GE-F404-IN20 engine start up control schedule was also varied with several control patches to establish reliable start" (rig tests at Leh 10,700 ft and Khardung La 18,300 ft) — DRDO statement of 28 Jan 2015 as reported by [Livefist Defence](https://www.livefistdefence.com/?p=236) (the starter was developed by HAL AERDC; three consecutive start-ups after overnight soak at around −15 °C "with a partially charged battery"). [DIRECT, secondary reporting of official statements]
- ADA: JFS for ground start and in-flight relight; "Upgradation of Jet Fuel Starter for LCA Mk I"; "high power GTSU-127 for LCA Mk2" — [ADA Propulsion page](https://www.ada.gov.in/images/ps.htm); [ADA PS integration facilities](https://www.ada.gov.in/images/PS%20Integration%20facilities.htm) (earlier addendum).

**F404 start sequence and timing [TRANSFER: -102 (T-50 FADEC), -400]**
- T-50 start system: APU → air turbine starter (ATS) → aircraft-mounted accessory drive (AMAD) → PTO shaft → engine-mounted accessory drive (EMAD). Net accelerating torque T_net = I·α = T_starter + T_combustion − T_friction − T_pumping − T_accessories. Normal ground start: APU on, ATS accelerates engine to a set speed, PLA moved OFF→IDLE, light-off at **≈27 s**, then ATS cut-out and the engine accelerates to idle on turbine torque alone — [Jung et al. 2006, KSAS 34(2), p.91, Figs. 1–2](https://koreascience.kr/article/JAKO200616039849001.pdf).
  - Fig. 2 (graph-read ±1 s / ±2 %): rotation begins ≈14 s; PLA to idle (≈20°) at ≈21–22 s with N2 ≈20 %; light-off ≈27 s; starter speed peaks/cuts out ≈37 s at ≈55 %; N2 reaches a stable **≈63 %** idle at ≈40 s (≈26 s from rotation to idle).
  - Ground-simulated spooldown test: "initial idle engine speed about 70 %" — p.93 (a second idle figure; the 63 vs 70 % difference is likely ambient/bleed related).
- F404-400 control: ignition permissive at NH 10–45 % — [CR-1998-208416 §7.2.5](https://ntrs.nasa.gov/citations/19980219005); normal-start status sequence "Starting engine → PLA to ground idle → Lite-off → Normal start"; NASA hung-start monitoring rule: N2 < 60 % and not increasing for 1 s with PLA between 14 and 24°, or N2 < 60 % for 35 s — [NASA TM-101702](https://ntrs.nasa.gov/citations/19900013006).
- Start-failure troubleshooting (RAAF IFDIS, three tables: no start, hot start, stall start): checks include main igniter firing **2–3 times per second while motoring**, fuel-shutoff arms, compressor turns by hand through the power transmission shaft, fuel vapour at exhaust, throttle rig at MIL; stall-start rule: fuel problem if MFC density setting mismatches the fuel, impending fuel-filter bypass indicated, or PS3 line broken — [Larkin, Frith & Findlay, ARL-PROP-TM-439, pp.16, 36–39](https://archive.org/details/DTIC_ADA227757). [TRANSFER: -400]
- GE's 1982 F404 FADEC demonstrated "adaptive starting fuel scheduling" — [SAE 821371](https://saemobilus.sae.org/content/821371).
- RM12 APU-assisted in-flight restart 45–85 s — [SHK RM 2019:02 p.43](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf).
- Generic: start times are longer at both high and low inlet temperature than on a standard day — [JSSG-2007A §A.3.2.2.3](https://everyspec.com/USAF/USAF-General/download.php?spec=JSSG-2007A.012946.pdf) (from sibling note).

**Shutdown, idle and cool-down**
- NAWCAD uninstalled performance run: ground idle 5 min → IRP 5 min → max AB 1 min → IRP minus 200…1,400 rpm N1 in 200 rpm steps (4 min each) → ground idle 2 min → shutdown — [NAWCADPAX/TR-2010/22E Tbl 1, pp.6–7](https://archive.org/details/DTIC_ADA517278). [TRANSFER: -400]
- The ECU uses T5 to detect post-shutdown fires — [CR-1998-208416 §7.2.3](https://ntrs.nasa.gov/citations/19980219005).
- Flight-idle corrected airflow ≈63.5–71.2 lb/s at ≈25 kft (≈68–71 % N1c) — [CR-198052 Tbl C1](https://ntrs.nasa.gov/citations/19970027377); a NASA expert-system display with the throttle at flight idle (PLA 32, 27,458 ft, M0.45) shows N1 75.8 %, N2 84.4–84.8 %, but it is a **stall scenario** (tt5 866.6 °C, PS3 9.89 psia), so it is not a normal flight-idle reference — [TM-101702 Fig. 6](https://ntrs.nasa.gov/citations/19900013006) (page image). Ground idle T5 ≈768 °F (≈409 °C) in a test-cell sweep — [CR-191195 Fig. 33](https://ntrs.nasa.gov/citations/19940032893). Flight-idle A8 is scheduled to 400 in² — [TM-4240 p.5](https://ntrs.nasa.gov/citations/19910009766). PLA: ground idle ≈18° (ARL Fig. 28; NASA bleed-limit figure) vs ≈13–15° (FOCSI ground sweep); flight idle 31° — [Frith 1985 Fig. 28](https://archive.org/details/DTIC_ADA164562); [TM-104247 Fig. 5](https://ntrs.nasa.gov/citations/19920020182).

**Replacement status for values that sibling notes took from the restricted F/A-18 NATOPS**

| NATOPS-derived value (in `flight_profiles_and_usage.md`) | Officially released replacement found | Status |
|---|---|---|
| Max EGT during start 815 °C | none | **Not replaced** |
| Throttle to IDLE at ≥15 % rpm | T-50 (-102): PLA to idle at ≈20 % N2 (graph-read), KSAS 2006 Fig. 2; -400 ignition permissive NH 10–45 % (CR-1998-208416) | Partly replaced [TRANSFER] |
| Crank switch off ≈60 % rpm | T-50: starter cut-out ≈55 % N2 (graph-read); NASA hung-start rule threshold 60 % N2 (TM-101702) | Partly replaced [TRANSFER] |
| Ground idle N2 61–72 % (-400) / 63–70 % (-402) | T-50 (-102): ≈63 % (Fig. 2) and "about 70 %" (text) | Partly replaced [TRANSFER: -102] |
| Ground idle EGT 190–590 °C | -400 test cell ≈409 °C (≈768 °F) at ground idle, CR-191195 Fig. 33 | Single point only |
| Ground idle fuel flow 420–700 / 420–900 pph | none (bio-fuel test gives only % deltas) | **Not replaced** |
| Ground idle nozzle 73–84 % | flight-idle A8 400 in² scheduled (TM-4240) within 220–540 in² sensor range; % scale not equivalent | Partly replaced (different unit) |
| Idle oil pressure 45–110 psi; peak <180 psi falling within 30 s | none | **Not replaced** |
| Flight idle 68–73 % N2 | flight-idle Wc 68–71 % N1c at 25 kft (CR-198052); T-50 steady N2 78–89 % before spooldown tests at 20–35 kft (not necessarily idle). TM-101702 Fig. 6 (N2 ≈84.8 % at PLA 32, 27 kft) is a stall scenario and should not be used | Partly replaced (altitude points, not SLS) |
| MIL-check N2 92–102 % / 90–102 % | Henry test-cell target XN2 14,215 rpm (≈84.6 % of 16,810, part-power take-off point); ARL design N2 16,810 rpm; DSTO 100 % N2 = 280 Hz | **Not replaced** as a band |
| MIL-check EGT 715–830 °C (-400) | **T5C steady-state limit 830 °C** shown on a NASA monitoring display, TM-101702 Fig. 6; T5 ≈1,500 °F (816 °C) at MIL in test cell (CR-191195 Fig. 33); limit reached "above 1250 °F" (CR-1998-208416) | Upper bound replaced [TRANSFER: -400] |
| MIL steady EGT limit 880 °C (-402) | none | **Not replaced** |
| MIL-check fuel flow 6,000–9,000 / 6,000–12,500 pph | derived SLS MIL Wf ≈8,270 lb/h from ARL thrust × SFC (10,600 lbf × 0.78) | Replaced by derivation [TRANSFER + ASSUMPTION] |
| MIL-check nozzle 0–57 % / 0–48 % | MIL A8 218–298 in² (NASA) | Partly replaced (area, not %) |
| MIL-check oil 95–180 psi | none | **Not replaced** |
| Thermal-soak restart: motor 1 min at 24 % N2 if restarted 15 min–4 h after an un-cooled shutdown | none | **Not replaced** |
| Crossbleed start ≥80 % / ≥1,900 pph | n/a for single-engine Tejas | Not needed |
| 5-min idle before shutdown recommended | NAWCAD run ends with 2 min GI before shutdown (test-cell practice, not a cockpit rule) | Partly replaced |

### Inferences
- [ASSUMPTION] Phalanx IN20 start model: JFS torque curve (110 kW peak free-turbine power, ≈(1–N/N_max)-shaped torque) driving N2 through the gearbox; ignition when PLA reaches idle and NH ≥ ≈15–20 %; light-off within ≈5–8 s of fuel-on; starter cut-out ≈55 % N2; idle ≈63–70 % N2 at ≈40 s from JFS engagement on a standard day; longer at Leh-type altitude and in cold soak; EGT start peak an [ASSUMPTION] ≈600–750 °C (no officially released number). Hung start = N2 stagnating below ≈60 % (NASA rule); hot start = T5 above a start limit (value to be supplied by IAF/HAL). Include a "dry rollover" (motoring without fuel) mode required by the IAF three-start ASR and a JFS battery-state dependence.
- [ASSUMPTION] Oil pressure at idle/MIL must be modelled from generic gear-pump physics (∝ N2 with relief-valve cap and viscosity/temperature dependence) until an officially released F404 value is found.

### Gaps
- No officially released IN20 (or F404) start EGT limit, light-off time, time-to-idle, oil-pressure bands or thermal-soak restart rules were found; these remain dependent on the restricted NATOPS or on HAL/IAF documents.
- GTSU-110 rotational speeds, output torque curve and run time limits are not public.

---

## Q8. Lubrication and vibration behaviour

### Takeaway
Public F404 lubrication data are structural, not numeric: a self-contained dry-sump lube system with three sumps (A, B, C), gearbox-driven lube and scavenge pumps, an oil cooler in the HPC module, lube and VEN-oil filter bypass indicators, **seven chip detectors** (oil tank, A sump, B sump, C-sump scavenge, C-sump gravity drain, accessory gearbox forward and aft) plus a NOAP sample fitting, oil-pressure exceedance monitoring at 1 Hz, and oil-debris statistics (SOAP intervals; QFDA wear rates per element). **No officially released oil tank capacity, pressure-vs-speed band, temperature limit, consumption limit or filter ΔP was found.** Vibration is well documented for the RAAF test cell (sensors, filters, limits by location and power, typical levels from idle to AB, 1/rev tracking) and qualitatively for flight (single mid-frame accelerometer; in-flight vibration monitoring "has not functioned up to expectations"; US Navy saturation problem without a >10 kHz filter).

### Cited Findings

**Lubrication [TRANSFER: -400]**
- Built-in features list: "self-contained lube system", "lube and VEN oil filter bypass indicators", "fuel filter bypass indicators", self-contained VEN hydraulic system, overspeed/overtemperature protection, flame sensor "to prevent hard lights" — [Frith 1985 Fig. 8, PDF p.20](https://archive.org/details/DTIC_ADA164562).
- Chip detectors (Fig. 37, page image): oil tank; "A" sump; "B" sump; "C" sump scavenge; "C" sump gravity drain; accessory gearbox forward; accessory gearbox aft; plus NOAP oil sample fitting — [Frith 1985 PDF p.49](https://archive.org/details/DTIC_ADA164562).
- Lube and scavenge pumps are driven by the HP-rotor accessory gearbox — [TP-3001 p.3](https://ntrs.nasa.gov/citations/19900015818); [CR-179568 Fig. 3](https://ntrs.nasa.gov/citations/19890003885). The -400 airframe interface carries an oil tank level signal and a lube-pump differential-pressure signal (CR-179568 Fig. 3).
- Oil cooler is part of the HPC module; oil pressure transmitter is part of the fan module — [Stemate 2002 Annex A](https://archive.org/details/DTIC_AD1003532). Fuel-oil heat-exchanger performance: not found.
- IECMS: oil pressure is an exceedance parameter (cockpit caution + MMP code + event record) and has a sensor-range validity check; recorded at 1 Hz; F/A-18C bus words IELOPL/IELOPR in psid — [Paré & Muir 1998 p.3](https://archive.org/details/DTIC_ADA347270); [Muir et al. Tbl 1](https://archive.org/details/DTIC_ADA203800); [NAWCADPAX/RTR-2001/1 Tbl E-3](https://archive.org/details/DTIC_ADA407860).
- **In-flight shutdown causes Jan 1986 – Apr 1988 (USN F404)**, read from a bar chart: oil pressure transmitter ≈13 (largest), C-sump oil supply line ≈12, electronic control ≈9, AB spraybar pigtail ≈7, AB liner ≈7, stage-3 HPC blade ≈7, MFC discharge hose ≈4, #4 bearing ≈4, LPT blade ≈4, MFC ≈3, stage-1 HPC blade ≈3, gray harness ≈3, vapor-puff relay ≈3, HPC lever arms ≈3, plus 23 single-event causes — [Glenny 1989 Tbl 1, p.28](https://archive.org/details/DTIC_ADA210374) (page image; counts approximate). [TRANSFER: -400] **This is the best public "oil-system failure mode" frequency set: sensor (transmitter) faults outnumber true lube failures.**
- **SOAP** (CF): one third of the fleet sampled every 20 h, the rest every 100 h; atomic-emission spectrometry only sees particles ≲5 µm (fine filters remove most debris); results within 24 h; filter debris analysis being developed — [Schofield et al., AGARD-CP-448 paper 4, Tbl 1, pp.4-2 to 4-10](https://archive.org/details/DTIC_ADA203800).
- **QFDA wear rates (µg/h, mean / 2σ; 26 CF188 filters, 38 USN filters; different preparation methods)** — [Bennett et al. 1996, Tbl I](https://archive.org/details/DTIC_ADP010173) (page image):

  | Element | CF188 mean | CF188 2σ | USN mean | USN 2σ |
  |---|---|---|---|---|
  | Fe | 0.4747 | 1.6813 | 6.11 | 13.27 |
  | Ag | 0.0805 | 0.2543 | 2.51 | 13.28 |
  | Al | 0.0259 | 0.0537 | 0.6 | 0.87 |
  | Cu | 0.1128 | 0.4883 | 0.37 | 0.6 |
  | Mg | 0.0032 | 0.0067 | 0.1 | 0.21 |
  | Ni | 0.6270 | 2.4289 | 7.71 | 18.31 |
  | Pb | 0.0451 | 0.0651 | 1.33 | 4.44 |
  | Ti | 0.0068 | 0.0326 | 0.18 | 0.48 |
  | Cd | 0.0119 | 0.0415 | 0.18 | 0.64 |
  | Mn | 0.0055 | 0.0184 | 0.07 | 0.13 |
  | V | 0.0056 | 0.085 | 0.07 | 0.12 |
  | Zn | 0.0363 | 0.0893 | 0.48 | 0.96 |

  - Normal-wear limit = mean + 2σ; one element over limit = potential problem, more than one = definite problem. Engine 376028 (radial drive shaft failure) exceeded Fe, Ag, Cu, Ni, Mn; engine 376269 (chip on screen plug) exceeded Ag, Al, Ni, Ti, Cd. Filters ≤10 µm.
- F414 adds an engine-mounted "master electrical chip detector" — [Hood, Khan & Story 2013 pp.17–18](https://archive.org/details/DTIC_ADA585693) [TRANSFER: F414 → IN20 FADEC era; IN20 chip-detector type unknown].

**Vibration [TRANSFER: -400]**
- In flight: one accelerometer, the IECMS mid-frame unit ("ECMS 4 o'clock"); test cell: front frame, mid-frame and rear mount ring — [DSTO-TN-0530](https://archive.org/details/DTIC_ADA423658); [Schofield et al. p.4-3](https://archive.org/details/DTIC_ADA203800). Upgraded RAAF transducers: Endevco 6222S-20A piezoelectric accelerometers, 20 pC/g (front, rear), 50 pC/g (mid-frame); old front/rear pickups were velocity coils.
- Signal chain: units in/s average; full scale 5.0 ips peak; 4-pole Butterworth high-pass, −5 % corner at 70 Hz (20 Hz option tested); input low-pass ≈1 kHz; tracking filters on N1 1/rev at all three sensors and N2 1/rev at mid-frame and rear; speed reference 250 Hz ≈90 % N2, 100 % N2 = 280 Hz — [DSTO-TN-0530](https://archive.org/details/DTIC_ADA423658) (OCR).
- **Test-cell limits (in/s average; from A1-F404A-MMI-200, 1 Mar 1993, WP 017 00, as tabulated by DSTO)** — [DSTO-TN-0530 Tbl 4](https://archive.org/details/DTIC_ADA423658) (page image):

  | Location | N1 1/rev steady | N2 1/rev steady | Overall steady | Overall transient |
  |---|---|---|---|---|
  | Front frame | 1.5 | — | 1.5 | 2.0 |
  | Mid-frame (ECMS) | 1.0 | 1.0 | 1.0 | 2.0 |
  | Rear mount ring | 1.0 | 1.3 | 1.0 (1.5 in AB) | 5.0 |

  The transient limit applies from a throttle movement (detected as an N2 change) until 5 s after it.
- **Typical levels (in/s average, Williamtown engine 058; columns GI / FI / 13,500 / 15,000 / 15,500 rpm (probably N2) / MIL / AB)** — [DSTO-TN-0530 p.10](https://archive.org/details/DTIC_ADA423658) (page image):
  - Baseline (old sensors): front 0.19/0.14/0.29/0.63/0.85/0.63/0.74; mid 0.16/0.15/0.30/0.31/0.31/0.42/0.48; rear 0.28/0.20/0.37/0.66/0.68/0.75/0.99.
  - New system run 1: front 0.07/0.07/0.15/0.42/0.37/0.42/0.45; mid 0.10/0.04/0.30/0.30/0.34/0.34/0.45; rear 0.37/0.22/0.35/0.57/0.60/0.70/0.82.
  - Mid-frame agreed within ≈10 % between systems; old front/rear read ≈40 %/20 % high (calibration drift). Tindal engine 036 (OCR): mid 0.30/0.20/0.25/0.25/0.34/0.34/0.50/0.55 at GI/FI/13,500/14,500/15,000/15,500/MIL/AB.
- Jacksonville F404 test-cell vibration requirement: 2–8 channels AC-coupled at 5 Hz; sampling ≥2,500 Hz (10 kHz preferred); ≥2,048 FFT lines; 1 Hz–1 kHz with <2.5 Hz resolution; N1 1/rev speed reference — [Roemer et al. 2002 Tbl 1](https://archive.org/details/DTIC_ADA408947).
- In flight: an IECMS vibration exceedance sets a maintenance code, but the system "has not functioned up to expectations"; exceedances must be corroborated; no engine removed for in-flight vibration was rejected in the test cell — [Schofield et al. p.4-3](https://archive.org/details/DTIC_ADA203800). USN: the avionics omitted a required high-frequency filter, the accelerometer saturated and gave false warnings, the fleet disabled the cockpit vibration warning; recommendation to filter >10,000 Hz before the charge amplifier — [Hess, AGARD-CP-448 p.2-6](https://archive.org/details/DTIC_ADA203800). IECMS records vibration at 1 Hz.
- Tejas ECMS "tracks Vibration Monitoring System" — [ADA Propulsion page](https://www.ada.gov.in/images/ps.htm) [DIRECT; no parameters].
- Engine excitation: one-per-rev excitation range "66 to 280 Hz" in the FOCSI environmental specification — [CR-191195 p.32](https://ntrs.nasa.gov/citations/19940032893) (66 Hz ≈ 30 % N1 1/rev; 280 Hz = 100 % N2 1/rev) [TRANSFER: -400].

### Inferences
- [ASSUMPTION] Vibration channel model: mid-frame accelerometer overall velocity (ips avg) = √(N1-1/rev² + N2-1/rev² + broadband²), with 1/rev amplitudes ∝ unbalance × N² filtered by a mount-resonance transfer function, tuned so healthy levels follow ≈0.1–0.3 ips at idle and ≈0.35–0.5 ips at MIL/AB at mid-frame; transient spikes allowed to 2× for 5 s after N2 changes; fault modes raise the relevant 1/rev or broadband component; add an in-flight saturation/false-alarm mode (USN lesson) and a "no fault found" fraction (CF lesson).
- [ASSUMPTION] Oil model: oil pressure = f(N2, oil temperature) with relief cap; oil temperature from heat rejection ∝ power and fuel-oil cooler effectiveness ∝ fuel flow (hot at low fuel flow/high ambient); consumption a slow drain with leak faults; chip-detector events and QFDA element signatures by bearing/sump location; a dominant **oil-pressure-transmitter fault** class (false low readings) as in the USN IFSD data.

### Gaps
- Oil tank capacity, oil type, pressure and temperature limits, consumption limit, filter ΔP and fuel-oil heat-exchanger characteristics: not found in officially released material.
- In-flight vibration levels by power setting (as opposed to test-cell) and IN20 accelerometer location: not found.

---

## Q9. Monitoring logic, life-usage counting, cockpit limits/cautions and Tejas ECMS facts

### Takeaway
The eight GE Life Usage Indices (LUIs) are publicly **named and qualitatively defined** (Hess 1988), but their gate levels and weighting functions are not public. Canadian shop data show how LUIs are used in practice (part limits in LCF counts, EFT counts or engine operating time; conversion to airframe hours through a fleet-average LUI-per-AFH; 150–400 AFH fall-out windows) and give part limits from which per-AFH accrual rates of ≈2–8 LCF counts/AFH and ≈22 EFT counts/AFH can be inferred. ADA confirms the Tejas ECMS computes "Life Usage Indices of Life limited Parts", shows real-time engine status and tracks vibration, but gives no definitions. The recommended Phalanx implementation is an explicit, documented re-creation of the eight LUIs using rainflow/hysteresis gates on N2 and PS3 and a blade-metal-temperature model for EFTC/stress rupture, cross-checked against the USAF TAC formula and the RM12 Life Tracking System method. Officially released cockpit-caution evidence is limited to the F/A-18 "L STALL" caution (Swiss report), the IECMS exceedance list, the -400 T5C limit of 830 °C on a NASA display, and RM12/T-50 FADEC flameout logic.

### Cited Findings

**LUI definitions and practice [TRANSFER: -400/-402 IECMS → Tejas ECMS]**
- The eight LUIs (verified on page images): (1) full N2 rpm cycle "Type I" ("an Off to Intermediate to Idle N2 RPM Cycle"); (2) partial N2 rpm cycle "Type III" (idle → intermediate → idle); (3) Equivalent Full Thermal Cycles (HPT blade temperature cycles weighted by cycle magnitude); (4) stress rupture counts (accumulate faster at higher HPT blade metal temperature); (5) TAMP, time at intermediate or above; (6) full PS3 cycle (CDP near maximum allowed; high speed, low altitude only); (7) partial PS3 cycle (CDP reaches 85 % of maximum allowable); (8) engine operating time at or above ground idle — [Hess, AGARD-CP-448 paper 2, pp.2-5 to 2-6](https://archive.org/details/DTIC_ADA203800).
  - Checked on the page image (p.2-5): Type I is "Off to Intermediate to Idle" — i.e. the cycle closes at idle, not at shutdown, unlike the USAF LCF definition (start → IRP → stop). One extraction pass misread this as "→ off".
- EFTC is computed in the mission computer **from turbine exhaust gas temperature**; for René 125 HPT blades the EFTC limit ≈1,000 h of average operation, DSR80 about twice that; ≈20 tracked components, most ≈4,000 h average life — [Frith 1985 p.10](https://archive.org/details/DTIC_ADA164562).
- Running LUI sums written to tape twice per flight; CF tracks 26 life-limited and 54 logistically critical components — [Paré & Muir 1998 pp.3, 9, 11](https://archive.org/details/DTIC_ADA347270).
- **Canadian shop-visit report example (page image)**: part / LUI type / limit — 6045T37P04 LCF 15,200; 6025T94P03 LCF 6,300; 6025T96P05 LCF 15,200; fuel nozzle insert LCF 14,000; **HPT (DSR80) blade EFT 30,000**; 6046T66P01 EOT 2,800; 6049T69P01 LCF 4,300; 74A180003-T111A/B OPH 300; fallout window 150 AFH; assumed 30 AFH/month — [Paré & Muir 1998 Fig. 7, p.10](https://archive.org/details/DTIC_ADA347270). Implied accrual rates (my arithmetic from the projected remaining AFH): ≈2–8 LCF counts per AFH for rotor parts, ≈22 EFT counts per AFH for the HPT blade, ≈1.33 EOT h per AFH [ASSUMPTION/derived].
- CF conversion: estimated AFH life = life limit (LCF counts) ÷ fleet-average LUI counts per AFH; 400 h fall-out window and 400 h periodic inspection; any lifed item under 100 h at a snag triggers a parts-life change-out; eight lifed "components" (fan module, HPC rotor, combustor case, fuel nozzles, #4 bearing, HPT rotor, fan drive shaft, LPT rotor) — [Stemate 2002, PDF pp.16–22](https://archive.org/details/DTIC_AD1003532).
- USN record rules: F404-400/402 test-cell running time must be logged because the engines are tracked by operating time plus LUI; LUI values are recorded to the thousandth — [COMNAVAIRFORINST 4790.2E (NAMP), PDF pp.345–346](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf) (local `maintenance/NAMP_4790.2E_2024.pdf`).
- Real usage was harsher than designed: time at maximum temperature ≈+60 % and AB light-ups ≈+60 % over the original life analysis — [Frith 1985 p.8](https://archive.org/details/DTIC_ADA164562); life limits were cut "almost 50 %" — [Canada TAA Advisory 2016-02](https://www.canada.ca/content/dam/dnd-mdn/documents/technical-airworthiness/english/taa-2016-02.pdf); USN 1993 cuts of 14–64 % (e.g., fan stage 1 5,850 → 1,870 h; HPT disk 10,500 → 7,200 h; LPT disk 10,520 → 6,240 h) — [King & Tooker 1993 Tbl 1.1](https://archive.org/details/DTIC_ADA277918).
- A noisy N2 signal made one engine accumulate partial-N2 counts up to 8× faster than its twin — [Muir et al. p.7-3](https://archive.org/details/DTIC_ADA203800) (sensor-artefact failure mode for synthetic data).
- Singapore's F404 (A-4SU) used a Jet Electronics engine temperature cycle counter recording equivalent full cycles, TAMP and engine hours — [Glenny 1989 p.26](https://archive.org/details/DTIC_ADA210374). [TRANSFER: F404-100D]
- F414: life used is computed through "nine matrices with 214 elements"; ≈1.2 ELCF per EOT hour used for forecasting — earlier addendum ([Hersey et al. 2008](https://archive.org/details/DTIC_ADA493918); [Schoch 2003](https://archive.org/details/DTIC_ADA418270)).

**Comparison methods**
- USAF TAC = LCF + FTC/4 + CIC/40 (LCF: start → IRP → stop; FTC: idle → IRP → idle; CIC: cruise → IRP → cruise) — [NATO RTO-TR-028 App. 1](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf); equivalently Type I + Type III/4 + Type IV/40 — [MIL-HDBK-1783B CHG-2 Tbl XI](https://everyspec.com/MIL-HDBK/MIL-HDBK-1500-1799/download.php?spec=MIL-HDBK-1783B_CHG-2.026101.pdf). Fighter design usage guidance (hot parts): 1,600 Type I, 10,000 Type III, 12,000 Type IV cycles, 8,500 AB lights, 100 h AB, 400 h at IRP+ (same Tbl X; from earlier note).
- RM12 Life Tracking System (GKN): logged NH/NL histories (resampled to 1 point per 3 s), steady-state "data creator" filling unmeasured values, **rainflow counting on turning points**, Coffin–Manson + Palmgren–Miner crack initiation with Neuber correction for most of 140 rotating parts; fan dovetails lifed by NASGRO crack propagation with inspection intervals; legacy on-board **level-crossing counting of full and partial NH cycles**; omitting ground runs under-counts crack growth by 2.47 %, ground plus missing missions by 9.08 %; the A3B3 mixed-mission spectrum is non-conservative for most engines; disc-to-disc life spread +31 % mean (+68 % max) — [Meyer 2014](https://publications.lib.chalmers.se/records/fulltext/201537/201537.pdf); [Carlson & Gustafsson 2014 pp.7–12](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf). [TRANSFER: RM12 FADEC-era practice]
- RM12 maintenance structure: ≈200 engines; modules removed as units; life limits in cycles with P(failure before limit) < 1/1,000; LPT has 10 parts (4 safety-critical); LPT nozzle cracks inspected every 200 FH; Weibull lives — [Patriksson et al. 2008](http://www.math.chalmers.se/Math/Research/Preprints/2008/45.pdf).

**Event triggers and monitoring logic [TRANSFER: IECMS]**
- Exceedance parameters fan speed, compressor speed, EGT, oil pressure, vibration → cockpit caution + 3-digit MMP code + ≈40 s record (5 s pre + 35 s post, CF) or 5 s + 25 s (USN); sensor-range validity checks on N1, N2, CDP, exhaust gas pressure, inlet temperature, oil pressure; flameout detection from CDP and rotor-speed behaviour; exceedances should persist several iterations — [Paré & Muir 1998 pp.3–4](https://archive.org/details/DTIC_ADA347270); [Hess pp.2-5 to 2-7](https://archive.org/details/DTIC_ADA203800).
- MMP codes 709/759 (RAAF troubleshooting rule 083) are resolved by any of: bad recorder data; hot section out of limits on borescope; **recorded inlet temperature >38 °C when the code was set**; FOD; >2.0 V DC on a specified harness check; **>5 °C left/right inlet-temperature difference at ground idle**; VEN positioning/reporting problem — [ARL-PROP-TM-439 p.37](https://archive.org/details/DTIC_ADA227757) (page image).
- NASA F-18 monitoring expert system: anomaly classes hot start, hung start, stall, overtemperature, flameout, overspeed, AB malfunction; indicator lights N1 > N1max, N2 > N2max, T5 > T5max, low lube pressure, fuel temperature, skin temperature, nozzle LVDT temperature (thresholds not legible); **T5C steady-state limit shown as 830 °C** — [NASA TM-101702 Tbl 3, Fig. 6](https://ntrs.nasa.gov/citations/19900013006). [TRANSFER: -400]
- ECU protections: NL overspeed solenoid (de-energised by NH logic), fan overspeed detection, stuck-nozzle detection, T5 limiting — [CR-1998-208416 §7.2](https://ntrs.nasa.gov/citations/19980219005); [Forsyth 1989 p.38](https://archive.org/details/DTIC_ADA219105).

**Cockpit cautions (officially released only)**
- F/A-18D (F404-GE-402): aural "engine left, engine left" and caution **"L STALL"** on engine stall; the engine page showed the power loss; action: affected engine to idle — [Swiss Military Justice report 2017, p.2](https://www.newsd.admin.ch/newsd/message/attachments/48614.pdf). [TRANSFER: -402]
- RM12: FADEC sets a flameout fault code that clears when T5 recovers; checklists: bird strike → 275 kt; flameout → >350 kt — [SHK RM 2019:02 pp.18–19, 42, 53](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf). [TRANSFER: RM12]
- F-18 stall procedure and EPU/airstart logic (NASA display) — Q6.
- Not found in released sources: numeric F404 caution thresholds for oil pressure, N1/N2 overspeed, AB failure.

**Tejas ECMS and recording [DIRECT]**
- "The Onboard Engine Condition Monitoring System Provides real time Engine Status in the Cockpit"; "Logs the Engine Usage Data to Compute Life Usage Indices of Life limited Parts"; "It also tracks Vibration Monitoring System" — [ADA Propulsion page](https://www.ada.gov.in/images/ps.htm).
- ADA annual report 2015-16: "Engine Health Monitoring" line (Naval LCA, Rs 57.48 M cumulative), "Mission Preparation & Data Retrieval Unit" and "Crash Data Recorder" line items — [ADA AR 2015-16 pp.75, 87](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf) (earlier addendum); "indigenous HUMS" for Mk1A being initiated (ADA AR 2018-19 to 2021-22, OCR, earlier addendum).
- Aggregator claims that the IN20 has "more than 6,500 total accumulated cycles (TAC) between in-flight events" conflate GE's "6,500 hours between in-flight events" family statistic — [IDRW](https://idrw.org/no-90-95-kn-engine-planned-for-tejas-mk1a-f404-to-stay-for-now/) (AGG; do not use).

### Inferences
- [ASSUMPTION] **Recommended Phalanx LUI implementation** (each gate is an assumption to be replaced by IAF/HAL values; all computed at ≥4 Hz on FADEC-rate N2, PS3, T5):
  1. *EOT*: integrate time with N2 ≥ ground-idle threshold (e.g. ≥55 % N2).
  2. *TAMP*: integrate time with PLA ≥ IRP detent (87° equivalent) or NL within 1 % of its scheduled limit.
  3. *Type I (full N2 cycle)*: one count per engine start whose N2 history goes off → IRP band (≥ 95 % of the IRP N2 at the prevailing T1) → back to idle (Hess definition); fractional counts by peak level optional. Later idle → IRP → idle excursions in the same run are Type III.
  4. *Type III (partial N2 cycle)*: hysteresis/level-crossing count of excursions from below a lower gate (flight-idle N2 + 5 %) to above the IRP band and back below the lower gate; implement as rainflow on the N2 history with a dead-band ≥2 × the N2 noise (≥2 × 138 rpm) to avoid the 8× noise inflation seen in CF data.
  5. *EFTC*: estimate HPT blade metal temperature Tm = T41 − ε·(T41 − T_coolant) with ε ≈0.5–0.6 (or a T5-based correlation, as GE did from EGT); rainflow-count Tm; EFTC += Σ (ΔTm_i/ΔTm_full)^b with b ≈3 (Coffin–Manson-type) where ΔTm_full is the cold-start → IRP swing.
  6. *Stress rupture counts*: SRC += Δt / t_r(Tm, σ ∝ N2²) via a Larson–Miller parameter (C ≈20); report in "equivalent hours at reference Tm".
  7. *Full PS3 cycle*: count each excursion above 95 % of PS3_max (PS3_max ≈425–475 psia class, Q4) returning below 50 %.
  8. *Partial PS3 cycle*: as 7 but upper gate 85 % of PS3_max (documented gate).
  - Report alongside TAC (USAF formula) and an RM12-style rainflow damage sum so that judges can see three independent life metrics agree in trend.
- [ASSUMPTION] Life-limit library for synthetic records: use Canadian/USN magnitudes (e.g., LCF limits 4,300–15,200 counts; HPT blade 30,000 EFT; disk lives 6,000–10,000 h after cuts) scaled to IN20 single-crystal HPT (longer blade life), and keep a "life-cut event" mechanism (sudden limit reduction, as in 1992–93).

### Gaps
- LUI gate levels, EFTC/stress-rupture formulas and weights, Tejas ECMS parameter list/rates/triggers/caution names: not public.
- No officially released F404 numeric caution thresholds (oil pressure, overspeed, AB fail).

---

## Q10. Deterioration and fault signatures specific to the F404

### Takeaway
F404-specific degradation evidence is mostly **signature direction and magnitude in corrected cross-plots**, not deterioration rates. The CF-18 programme (NRC component-level F404 model + test-cell fault implants) published a 6-fault × 7-cross-plot direction matrix, measured-vs-model shifts for a CVG mis-rig/flameout case and an HPC-damage case (e.g., +8 % PS3/P1 vs N2, +8–14 % Wf vs N2, ≈−1 to −2 % N2 vs N1), Kalman-band take-off shifts of +2–5 % against ±0.8–2 % scatter, fuel-ratio-unit overfuelling before a flameout, and the warning that an F404 "can carry considerable component damage and still pass the EPR acceptance test". Australian work showed an EGT-harness bias changes identified fan-spool dynamics, and Eustace et al. (JEGTP 1994) showed transient (take-off) data detect implanted faults with higher sensitivity than steady-state data. No public F404 deterioration rate per 1,000 EFH or wash-recovery magnitude was found; rates must be transferred from F100/commercial sources with a severity factor.

### Cited Findings
- **Fault-direction matrix (CF-18 F404-400; θ1/δ1-corrected baselines; page image)** — [Muir, Rudnitski & Cue, AGARD-CP-448 paper 7, Fig. 15](https://archive.org/details/DTIC_ADA203800):

  | Fault | W1 vs N1 | N2 vs N1 | Fg vs N2 | Wfm vs N2 | PS3/P1 vs N2 | T56 vs P56/P1 | N2 vs P56/P1 |
  |---|---|---|---|---|---|---|---|
  | Fan flow/efficiency degradation | ↓ | ↓ | ↓ | ↓ | ↓ | ↑ | ↑ |
  | HPC flow/efficiency degradation | — | ↑ | ↓ | ↓ | ↓ | ↑ | ↑ |
  | HPT efficiency degradation | ↓ | ↓ | ↑ | ↑ | ↑ | ↑ | ↓ |
  | LPT efficiency degradation | — | ↑ | ↓ | — | — | ↑ | — |
  | Fan VG above limits | ↓ | ↑ | — | — | — | — | — |
  | Compressor VG above limits | — | ↓ | ↑ | ↑ | ↑ | ↓ | ↓ |

  W1 and Fg exist only in the test cell. Correcting for FVG, CVG and A8 positions cuts scatter 2–3×; data are captured in the A8 "cruise flat" region; airflow deviations are largest at mid power — same paper pp.7-3, 7-13.
- **Measured vs NRC-model shifts (page image)** — [Muir et al. Figs. 17–18](https://archive.org/details/DTIC_ADA203800):

  | Baseline | Test-cell flameout (S/N 6060), measured | Model: 6° CVG shift | HPC blade damage (S/N 6076), measured | Model: −5 % HPC efficiency |
  |---|---|---|---|---|
  | W1 vs N1 | −0.3 % | 0.0 % | +0.3 % | −0.6 % |
  | N2 vs N1 | −1.0 % | −1.5 % | −0.7 % | −0.5 % |
  | Fg vs N2 | +12.6 % | +11.7 % | +12.2 % | +6.0 % |
  | Wfm vs N2 | +13.6 % | +11.1 % | +8.0 % | +9.6 % |
  | PS3/P1 vs N2 | +7.9 % | +8.1 % | +8.2 % | +9.6 % |
  | T56 vs P56/P1 | +0.3 % | −0.5 % | +2.9 % | +5.3 % |
  | N2 vs P56/P1 | −1.9 % | −1.5 % | −1.8 % | −0.7 % |

- **Take-off (transient) indices**: fuel ratio units Wfm/PS3 during a slam, monitored at 81 % and 87 % N2 — serviceable MFC ≈88–100 % of nominal across the range, damaged MFC peaks ≈105 % near 79 % N2 (overfuelling before a flameout); N1/N2 acceleration times over the nozzle-closed window; PS3 time to 250 psi left vs right; trend groups of 8 engines run every 25 FH for 18 months showed step shifts at MFC/combustor/AB/HPT changes (e.g., N2 vs N1 deviation ≈−1 % → ≈−0.5 % after replacements) — [Muir et al. pp.7-1 to 7-4, Figs. 3–5, 16](https://archive.org/details/DTIC_ADA203800) (graph-read). Nine Canadian condition indicators (rotor acceleration times, N1/N2 ratio, fuel ratio units, VEN position, etc.) feed a rule-based Performance Monitor; the Flight Line Troubleshooting System covers 45 failure modes and isolates the LRU in 60–70 % of cases — [Paré & Muir 1998 pp.8–12](https://archive.org/details/DTIC_ADA347270).
- **Kalman-band detection of HPC damage (take-off data; shift / normal scatter)**: P5/δ vs PS3/δ at 125 psia +2 % / ±1.0 %; T5/θ vs PS3/δ at 150 psia +3 % / ±0.8 %; XN2/√θ vs PS3/P5 at 5.75 +3 % / ±1.0 %; T5/θ vs PS3/P5 at 5.5 +5 % / ±2.0 %; T5/θ vs P5/δ at 35 psia +2 % / ±0.8 %; T5/θ vs XN1/√θ at 11,500 rpm +2 % / ±0.8 %. Non-fault shifts came from throttle overshoot into AB, inlet screens left on, re-slams and T1 changes — [Henry, AGARD-CP-448 paper 37, Tbl 2](https://archive.org/details/DTIC_ADA203800) (page image).
- "The F404 can take considerable component damage and still pass the EPR performance verification test, except for fan and nozzle problems" — [Muir et al. p.7-5](https://archive.org/details/DTIC_ADA203800).
- **EGT-harness bias**: a 60 °C bias changed the identified fan-spool model from (gain ≈8.4, τ 0.77 s) to (22.1, 2.11 s) — [Merrington, paper 36](https://archive.org/details/DTIC_ADA203800); robust fault-detection methods were applied to F404 test data — [Villaneuva, Merrington, Ninness & Goodwin, IFAC 1991](https://doi.org/10.1016/s1474-6670(17)51188-x) (metadata only).
- **Fault implant tests** (ARL/RAAF, SLS test cell): "not only is there similar fault information contained within the transient data, but the faults can be detected with increased sensitivity using these data" — [Eustace, Woodyatt, Merrington & Runacres, JEGTP 116:178–183 (1994), ASME 92-GT-082](https://doi.org/10.1115/1.2906789) (abstract via Crossref; full text paywalled). Implant methods suggested by GE/NAPC: set VG to limits, reset the MFC density corrector, move the T2.5 sensor, change nozzle actuator lengths, bleed off PS3 — [Glenny 1989 pp.13–17](https://archive.org/details/DTIC_ADA210374).
- **Test-cell diagnostic practice (Jacksonville)**: root-cause faults fan/LPC/HPC/HPT/LPT efficiency, 2.5 bleed, 2.9 bleed, discharge area, stator-vane mis-rig; diagnostic parameters Wf, N2, T45, P25, T25, T3, P3 at 10 Hz; model matched T45 on 21 engines within ≈1 % — [Roemer et al. 2002 p.8](https://archive.org/details/DTIC_ADA408947). [TRANSFER: -400/-402 and F1D2]
- **NRC Canada**: IAR/GasTOPS produced steady-state model software packages for the J57, T56, F404 and J85; DND-funded steady-state and transient F404 test data "improve the DND F404 model used in on-going engine health monitoring programs at DND bases" and "the DND F404 transient model" — [NRC IAR Gas Turbine Laboratory page (archived 2007)](https://bac-lac.wayback.archive-it.org/web/20071120002212/http://iar-ira.nrc-cnrc.gc.ca/gtl/gtl_10_e.html). Model itself not public.
- **Wash**: the NRCC research F404 had 4 compressor water-wash nozzles — [Glenny 1989 p.14](https://archive.org/details/DTIC_ADA210374); no F404 wash-recovery magnitudes found.
- **Usage severity and life cuts**: Q9.
- **Fleet reliability**: USN F404 1987–90 MTBF 67.4 h, 3.7 removals/1,000 EFH; module MTBF Feb 1997–Jul 1998: engine 383.5 h, fan 679.6, HPC 769.3, combustor 696.3, HPT 692.3, LPT 641.3, AB 515.5 h — [King & Tooker 1993 Tbl 2.1](https://archive.org/details/DTIC_ADA277918); [Stearns 1998 Tbl II.2](https://archive.org/details/DTIC_ADA359328) (page image). Flameholder replacement is the #1 cause of unscheduled -402 removals — [NAWCADPAX/RTR-2001/1 p.8](https://archive.org/details/DTIC_ADA407860).
- **HARV "significantly deteriorated" engine** at ≈1,529 h EOT (qualitative) — [TM-1999-206572 p.15](https://ntrs.nasa.gov/citations/19990024943).
- **Transferable magnitudes (not F404)**: F100 "experienced" deterioration fan −1.0 %, compressor −2.0 %, HPT −2.5 % efficiency — [NASA TP-1056 p.8](https://ntrs.nasa.gov/citations/19770026225); F100-220 performance loss <2 % per 4,000 cycles vs 1 % per 400 cycles for F100(3) — [RAND N-3618](https://www.rand.org/pubs/notes/N3618.html); DEEC behaviour "FTIT rises to hold EPR until the limit, then thrust falls" — [NASA CP-2298 Paper 3 p.50](https://ntrs.nasa.gov/citations/19860015874) (all from earlier notes). [TRANSFER: F100 → F404 control analogue: on the F404 the nozzle holds T5 at IRP, so deterioration shows first as **A8 opening and NL/thrust shortfall at the T5 limit**, and below IRP as higher T5 and Wf at a given N2]

### Inferences
- [ASSUMPTION] Phalanx degradation model: MAPSS-style flow/efficiency scalars per module (fan, HPC, HPT, LPT) plus VG offsets (FVG, CVG), nozzle-area bias, MFC fuel-scheduling bias (ratio units), sensor biases (T5 harness, PS3, N2 noise). Drive them with gamma-process drifts (rates from F100/commercial × a fighter severity factor 1.5–2) and step events (FOD, blade damage, MFC fault, harness fault). Validate signature **directions** against the Muir matrix and **magnitudes** against the Muir/Henry measured shifts (HPC damage ≈ −5 % ηHPC equivalent; CVG mis-rig 6° → +8 % PS3/P1, +11 % Wf at fixed N2).
- [ASSUMPTION] Implement CF-18-style take-off health indices in the synthetic ECMS output (fuel ratio units at 81/87 % N2, N1/N2 acceleration times in the nozzle-closed window, PS3 time-to-250 psi), because these are the indices a real F404 fleet actually trended.

### Gaps
- No F404 deterioration rates (EGT margin loss per 1,000 EFH), wash recovery, or IN20 fault statistics in officially released sources.
- Cue & Muir, ASME 90-GT-357 / JEGTP 113 (1991), and Eustace et al. 1994 full texts not read (paywalled).

---

## Q11. Open-source and published models usable for a composite F404

### Takeaway
No public dimensional F404 component maps or full models exist. Usable assets: (1) **pyCycle `mixedflow_turbofan.py`** (Apache-2.0) has every needed element except variable geometry and AB zoning, but carries an LPC that must be removed and an off-design setup with a fixed A8 and an always-lit AB; (2) **NASA T-MATS** (Simulink, open source) for the dynamic shell; (3) **NASA MAPSS/C-MAPSS40k documentation** for the controller pattern, health parameters and sensor/actuator models (code is US-release-only); (4) **NASA TM-4240 table-plus-lag F404 model** (3 % steady / 20–25 % transient vs GE model) as a fallback and a validation reference; (5) **NASA F100 TP-1034** equations, normalised maps, inertias and volumes as a method template; (6) RM12 academic work (GESTPAN, H∞ control, Linköping model-based diagnosis) — proprietary models, results only.

### Cited Findings
- **pyCycle mixed-flow example** (local `methodology/pycycle_src/mixedflow_turbofan.py.txt`, from [GitHub](https://github.com/OpenMDAO/pyCycle/blob/master/example_cycles/mixedflow_turbofan.py)):
  - Topology: inlet → inlet duct → fan (AXI5 map) → splitter → core duct → **LPC (LPCMap)** → duct → HPC (HPCMap, bleed `cool1`) → bleed `cool3` → burner → HPT (cooled by cool3) → duct → LPT (cooled by cool1) → duct → mixer (stream 1) ; bypass duct → mixer (stream 2) → mixer duct → afterburner (second Combustor) → CD nozzle with Cfg. Thermo CEA (Jet-A); tabular option available.
  - Design (35 kft, M0.8): Fn 5,500 lbf; T4 3,200 °R; AB 3,400 °R (a **cycle parameter**, so the AB is lit at every point); fan PR 3.3 (η 0.8948), LPC 1.935 (0.9243), HPC 4.9 (0.8707); HPT η 0.8888, LPT 0.8996; LP 4,666 rpm, HP 14,706 rpm; HPX 250 hp; duct dP/P 0.0048–0.0107, burner and AB 0.054; Cfg 0.9933; cooling bleeds 5.07 % (mid-HPC → LPT) and 6.72 % (HPC exit → HPT); **mixer total-pressure ratio target ER = 1.05 sets BPR** (BPR is solved, not 1.05 — this corrects the earlier Phalanx note).
  - Off-design: W balanced to the design nozzle throat area (fixed A8); BPR balanced by mixer static-pressure match; FAR to T4 and AB temperature; shaft speeds to power balance; map scalars and areas held from design.
  - **Pitfall found in the local `shaft.py`**: the balances use `pwr_in = −pwr_out`, which excludes HPX, so power extraction may have no effect on the solution; use `pwr_net = 0` (as the turbojet example does) — local `shaft.py.txt` L63–72 vs `mixedflow` L140–146.
  - Re-design to IN20 [ASSUMPTION]: delete LPC and its duct/ports; SLS (MN ≈1e-6); design **dry** at SLS (remove FAR_ab balance) with W ≈70 kg/s fixed or Fn ≈54 kN target; fan PR ≈4.3–4.4, HPC ≈6.4–6.5, T4 ≈3,200 °R (1,778 K), lower the BPR bound to ≈0.05 and target BPR ≈0.27–0.30 via ER; then run wet as off-design with a scheduled A8 (lit throat area 1.5–2.0× dry is typical — Grönstedt PhD p.111); raise Newton iterations; fix the HPX balance.
- **T-MATS** (NASA, open source): solver iterates component errors with a Newton–Raphson Jacobian each time step; shaft speeds integrated outside the solver — [NASA TM-2014-216638 pp.7–8](https://ntrs.nasa.gov/citations/20140012486); repository [nasa/T-MATS](https://github.com/nasa/T-MATS) (no military/AB example; Mixer, variable-geometry compressor and nozzle blocks available).
- **MAPSS / C-MAPSS40k** (Q4, Q6): controller, health parameters (fan/booster/HPT/LPT flow and efficiency scalars), sensor and actuator bias constants, TMPC heat soak; C-MAPSS40k surge-margin definition SM = 100(PR_surge − PR_op)/PR_op with transient debits and 8–24 % reserve logic — [TM-2004-212968](https://ntrs.nasa.gov/citations/20040035577); [TM-2010-216810 pp.9–11](https://ntrs.nasa.gov/citations/20100037767). Parker & Guo's military-engine CLM (single-stage high-PR fan, booster, HPC, double-annular combustor, AB, VABI) reached <1 % steady-state error — [NASA TM-2003-212543](https://ntrs.nasa.gov/citations/20030093721).
- **NASA F404 simple model**: tables of FG, ram drag, NPR, A8, inlet and nozzle drag on 4 PLAs (FI, MIL, min AB, max AB) × 7 altitudes × 12 Machs plus PLA lag/rate limit; ≈0.3 ms per 20 ms frame — [TM-4240](https://ntrs.nasa.gov/citations/19910009766); HARV implementation with 29 12 × 7 arrays, T56-bias and AOA factors, windmill drag — [TM-110216 §4.1](https://ntrs.nasa.gov/citations/19960027892). GE's full model R88AEB427 (≈6,250 lines FORTRAN, component-level, iterative) and in-flight thrust deck 83112 are referenced but not public — [TM-4240](https://ntrs.nasa.gov/citations/19910009766); [TP-3001](https://ntrs.nasa.gov/citations/19900015818). GE spec deck 80031A/LP005S accuracy 8.74 % (2σ) over PLA 40–130 but −29.7 % bias at PLA 31 — [TP-3001 Tbl 6](https://ntrs.nasa.gov/citations/19900015818). [TRANSFER: -400]
- **GE compact real-time F404 model** (engine-mounted computer, failure protection; SAE 821401, abstract) and **FADEC FICA model** (SAE 821371) — [SAE 821401](https://saemobilus.sae.org/papers/development-a-compact-real-time-turbofan-engine-dynamic-simulation-821401); [SAE 821371](https://saemobilus.sae.org/content/821371).
- **F100 method template**: equations, normalised maps (fraction of design corrected speed/PR/flow with vane off-schedule shifts and Reynolds shifts), inertias, volumes, lags — [TP-1034](https://ntrs.nasa.gov/citations/19770024210); 4-state piecewise-linear real-time model with slow-response temperature states — [Litt 1989](https://ntrs.nasa.gov/citations/19890011624).
- **RM12 academic models (results only)**: Grönstedt PhD (GESTPAN general tool, DASSL implicit ODAE, volume dynamics; generic mixed-flow design case LP π 5.0, BPR 0.5, T4 1,800 K; inertias 30/20 kg·m² assumed); Rosell & Grönstedt 2022 generic low-BPR fighter engine (FPR 5.4, HPC 5.8, 90 kg/s, BPR 0.45, T4 1,950 K; 10 mission thrust points; installed intake PT2/PT0 0.894 at M0) — [Fluids 7(1):21](https://doi.org/10.3390/fluids7010021); Härefors H∞ control of RM12 — [Control Eng. Practice 1997](https://doi.org/10.1016/s0967-0661(97)84358-4); Grönstedt & Wallin GT2004-53591 RM12 diagnostics on two real test-bed data sets — [doi](https://doi.org/10.1115/gt2004-53591); Klein & Östling 1998 LiU MSc "Modellbaserad diagnos på turbojetmotorn RM12" (linearised Volvo RM12 model, balanced/modal reduction, minimal polynomial basis residuals; full text link returned 404) — [VTI catalogue](https://bibliotek.vti.se/bib/242106).
- **NASA TTECTrA** (Tool for Turbine Engine Closed-loop Transient Analysis; Apache-2.0 per README; User's Guide NASA TM-2014-216663): a MATLAB/Simulink tool that designs a scheduled PI fuel controller with only the fundamental transient limiters (acceleration/deceleration, speed/pressure limits) for a user's Simulink engine model from piecewise-linear state-space models — [github.com/nasa/TTECTrA](https://github.com/nasa/TTECTrA). Directly usable to generate the IN20 FADEC core loop on a T-MATS shell [TRANSFER: generic subsonic-engine tool; AB/nozzle loops must be added].
- **NASA TCML** (Tip Clearance Modeling Library; NASA licence) models dynamic HPT tip-clearance variation (thermal/centrifugal growth) — [github.com/nasa/TCML](https://github.com/nasa/TCML) — a ready template for the heat-soak/clearance state that drives re-slam and deterioration effects [TRANSFER: method].
- **GSP / NPSS / GasTurb**: earlier note (GSP unsupported by NLR; NPSS export-controlled; GasTurb commercial).

### Inferences
- [ASSUMPTION] Best route for Phalanx: pyCycle (re-designed, SLS dry design + scheduled-A8 off-design incl. AB) to generate steady-state performance tables over (altitude, Mach, ΔISA, PLA/N1c, health scalars) → embed tables in a dynamic shell with two rotor ODEs (+ optional volumes), a heat-soak state, actuator/sensor models and the FADEC of Q4 (C-MAPSS40k pattern) → sensor/recorder layer (Q3, Q9). Keep the TM-4240 table-plus-lag model as an independent "sanity" thrust model.

### Gaps
- No public F404 maps; pyCycle's maps are generic (AXI5 etc.), so map shape (surge line, efficiency islands) is an assumption.
- MAPSS/C-MAPSS code is US-release-only; only documentation is usable.

---

## Q12. Synthesis: key findings, parameter table, recommended model architecture, calibration targets, gaps and ranked sources

### Takeaway
A defensible IN20 model is achievable as a **composite F404**: GE's four IN20 numbers fix the size and rating; officially released Australian, Canadian, US Navy and NASA F404-400/402 documents fix the architecture, sensors, control structure, operating lines, transient constants, monitoring and life-usage logic; RM12 and F404-GE-102 (T-50) public sources supply the FADEC-era behaviour (flameout detection, auto-relight, airstart timings, life tracking); NASA C-MAPSS40k/MAPSS/T-MATS/TTECTrA and pyCycle supply the open modelling machinery. Every IN20-specific value beyond the GE sheet is a transfer or an assumption and is tagged so below.

### Cited Findings

#### (a) Key findings summary
1. **Published IN20 data are limited to** 84 kN (19,000 lb class) max thrust, 70 kg/s (153 lb/s), OPR 28, 1,072 kg, higher-flow fan, FADEC with redundant/single-engine features, single-crystal turbine blades, -402 parentage, 330 h AMT ≈1,000 flight hours — [GE data sheet](https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf); [GE 2004](https://www.geaerospace.com/news/press-releases/defense-engines/ge-awarded-105-million-development-contract-india); [GE 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight). The widely quoted 54 kN dry thrust is aggregator-only (and equals FI's RM12 dry rating).
2. **New officially released F404-400 cycle anchors**: TIT 1,390 °C, fan PR 4.1 @ 13,270 rpm, HPC PR 6.0 @ 16,810 rpm, BPR 0.34, OPR 25, 142 lb/s, 10,600/16,000 lbf, SFC 0.78/1.84 — [ARL 1985](https://archive.org/details/DTIC_ADA164562); **-402**: fan PR 4.3, HPC 6.23, OPR 27, BPR 0.27, 17,775 lbf — [NPS 1998](https://archive.org/details/DTIC_ADA359328); 100 % N2 = 280 Hz ≈16,800 rpm — [DSTO-TN-0530](https://archive.org/details/DTIC_ADA423658).
3. **Hand cycle closure** shows the IN20 numbers are mutually consistent with fan PR ≈4.3–4.4, BPR ≈0.27–0.30, HPC PR ≈6.4–6.5 and T4 ≈1,770–1,790 K (≈+110–130 °C over the -400; RM12 +105 °C), giving ≈54–57 kN dry and T5 near its limit at SLS MIL [ASSUMPTION].
4. **Control structure (-400)** is documented: below IRP N2 = f(PLA, T2.5) and A8 = f(PLA) with PS3 ≤ 80 psia override; at/above IRP NL = f(T1) isochronous (cold-day cap 104.4 % corrected) with PS3 ≥ 425 psia override, and A8 modulated to hold T5 = f(T1, P0); accel/decel Wf/PS3 limits; FVG = f(N1c) (digitised schedule), CVG = f(N2c); AB in Wr/PS3 ratio units with nozzle pre-open, T5 reset, N1-within-3 % permission — [ARL Fig. 28](https://archive.org/details/DTIC_ADA164562); [NASA CR-1998-208416](https://ntrs.nasa.gov/citations/19980219005); [CR-179568](https://ntrs.nasa.gov/citations/19890003885); [NAWCADPAX/RTR-2001/1](https://archive.org/details/DTIC_ADA407860).
5. **Sensor physics** are fully public for the -400 (FOCSI), including frequency scalings (0.7 Hz/rpm NL, 0.239 Hz/rpm NH), T5 8-probe averaging and failure semantics, T5 τ vs mass flux, and IECMS quantisation/noise — [CR-191195](https://ntrs.nasa.gov/citations/19940032893); [Henry, AGARD-CP-448](https://archive.org/details/DTIC_ADA203800). Earlier Phalanx values for Henry's T1/T5 targets were OCR errors (corrected here).
6. **Transient and relight targets** now include F404-402 AB light-off times and criteria, CF-18 take-off acceleration facts, a fan-spool τ ≈0.77 s, HARV surge histories, the RM12 bird-strike rundown trace and **F404-GE-102 (FADEC) spooldown/APU-assisted/auto-relight tables and a ground-start timeline** — [NAWCAD](https://archive.org/details/DTIC_ADA407860); [AGARD-CP-448](https://archive.org/details/DTIC_ADA203800); [SHK](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf); [KSAS 2006](https://koreascience.kr/article/JAKO200616039849001.pdf).
7. **Tejas start**: GTSU-110 JFS (110 kW, 52 kg, twin-shaft, free power turbine); ASR ≥2 consecutive starts, IAF 3 (two starts + dry rollover); M1 failed Leh trials 2013–14 and burned excess oil; Jan 2015 success at −15 °C/85 % battery after IN20 start-schedule "control patches" — [DDP](https://www.ddpmod.gov.in/hi/node/8778); [CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf); [Livefist/DRDO](https://www.livefistdefence.com/?p=236).
8. **Oil/vibration**: structure (3 sumps, 5 bearings, 7 chip detectors), IFSD cause frequencies (oil-pressure transmitter the top cause), QFDA wear statistics and full test-cell vibration limits/levels are public; **oil quantities, pressures, temperatures and consumption are not**.
9. **Life usage**: the 8 LUIs are defined qualitatively (Type I = off → intermediate → idle; partial PS3 gate 85 %), CF part limits (e.g., HPT DSR80 blade 30,000 EFT; LCF 4,300–15,200) and conversion practice are public; gates/weights are not. TAC and the RM12 rainflow LTS provide cross-check methods.
10. **Officially released replacements** were found for only some NATOPS-derived idle/MIL values (Q7 table); start EGT limit, idle fuel flow, oil-pressure bands, -402 MIL EGT limit and thermal-soak restart rules remain unreplaced.

#### (b) Parameter table (parameter, value, unit, tag, source, confidence)

| # | Parameter | Value | Unit | Tag | Source | Confidence |
|---|---|---|---|---|---|---|
| 1 | Max (AB) thrust, SLS ISA | 84 (19,000 lb class; ">19,000 lb uninstalled") | kN | DIRECT | [GE data sheet](https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf); [GE 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight) | High |
| 2 | Inlet airflow (max) | 70 (153) | kg/s (lb/s) | DIRECT | GE data sheet | High |
| 3 | Overall pressure ratio | 28 | – | DIRECT | GE data sheet | High |
| 4 | Dry weight | 1,072 (2,365) | kg (lb) | DIRECT | GE data sheet | High |
| 5 | Length / max dia / inlet dia | 391 / 89 / 71 | cm | DIRECT | GE data sheet | High |
| 6 | Stage count fan–HPC–HPT–LPT | 3–7–1–1 | – | TRANSFER: -400 (same family; RM12 identical) | [ARL 1985 Fig. 3](https://archive.org/details/DTIC_ADA164562); [SHK p.17](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf) | High |
| 7 | Dry (MIL) thrust, SLS | ≈54 (12,140) | kN (lbf) | AGG + ASSUMPTION (closure 54–57) | [Wikipedia](https://en.wikipedia.org/wiki/General_Electric_F404); Q1 closure | Medium-low |
| 8 | Bypass ratio | 0.28 (range 0.27–0.30) | – | TRANSFER: -402 0.27–0.29, RM12 0.31 + ASSUMPTION | [NPS 1998](https://archive.org/details/DTIC_ADA359328); [Schoch 2003](https://archive.org/details/DTIC_ADA418270); FI RM12 | Low-medium |
| 9 | Fan PR (total) at max | 4.35 (4.3–4.4) | – | TRANSFER: -402 4.3; -400 3.9–4.1; RM12 4.0–4.4 (derived) | NPS 1998; ARL 1985; [Meyer 2014](https://publications.lib.chalmers.se/records/fulltext/201537/201537.pdf) | Medium-low |
| 10 | HPC PR | 6.45 (6.4–6.5) | – | ASSUMPTION (28 / fan PR); -400 6.0–6.3, -402 6.23 | ARL; NPS | Medium-low |
| 11 | Combustor-exit temperature T4 at max | 1,780 (1,770–1,790) | K | ASSUMPTION: -400 1,663 K + ≈105–130 K uplift | ARL 1985; [Forecast Intl RM12](https://www.forecastinternational.com/archive/disp_pdf.cfm?DACH_RECNO=989) (AGG) | Low |
| 12 | -400 turbine inlet temperature | 1,390 °C (1,663 K) | °C | TRANSFER: -400 (station undefined) | ARL 1985 Fig. 3 | Medium |
| 13 | T5 (EGT) at SLS MIL | 1,130–1,160 | K | ASSUMPTION (closure) | Q1 | Low-medium |
| 14 | T5 steady-state limit (-400) | 830 | °C | TRANSFER: -400 (NASA monitoring display) | [TM-101702 Fig. 6](https://ntrs.nasa.gov/citations/19900013006) | Medium |
| 15 | T5 at MIL/max AB (-400 test cell) | ≈1,500 (≈1,089 K) | °F | TRANSFER: -400 | [CR-191195 Fig. 33](https://ntrs.nasa.gov/citations/19940032893) | Medium |
| 16 | Mixed nozzle T8 at MIL (-400) | 935–939, altitude-invariant | K | TRANSFER: -400 | [TM-4538 Tbl 2](https://ntrs.nasa.gov/citations/19940010668) | High (for -400) |
| 17 | 100 % N1 (fan) | 13,270 | rpm | TRANSFER: -400 (IN20 assumed same mechanical speed) | [TP-3001](https://ntrs.nasa.gov/citations/19900015818); [CR-191195](https://ntrs.nasa.gov/citations/19940032893); ARL | High (-400) / Medium (IN20) |
| 18 | 100 % N2 (core) | 16,810 (280 Hz 1/rev) | rpm | TRANSFER: -400 | ARL 1985; [DSTO-TN-0530](https://archive.org/details/DTIC_ADA423658) | High (-400) / Medium (IN20) |
| 19 | Max corrected airflow (-400) / curve | 145–146 at ≥100 % N1c (curve in Q5) | lb/s | TRANSFER: -400 | [CR-198052 Fig. 2](https://ntrs.nasa.gov/citations/19970027377); [TM-100159 Fig. 6](https://ntrs.nasa.gov/citations/19870020104) | High |
| 20 | Cold-day corrected fan-speed cap | 104.4 | % | TRANSFER: -400 | ARL 1985 Fig. 29 | Medium |
| 21 | SFC MIL / max AB (-400) | 0.78 / 1.84 | lb/h/lbf | TRANSFER: -400 | ARL 1985 | Medium |
| 22 | SLS MIL core fuel flow | ≈8,270 (-400 derived); IN20 ≈8,700–9,500 | lb/h | ASSUMPTION | ARL; Q1 | Medium-low |
| 23 | AB thrust ratio at max AB | 1.50–1.55 (-400); IN20 ≈1.56 | – | TRANSFER + ASSUMPTION | [TM-100159 Fig. 8](https://ntrs.nasa.gov/citations/19870020104) | Medium |
| 24 | AB fuel-air ratio at max AB | 0.062–0.066 | – | TRANSFER: -400 | TM-100159 Fig. 8 | Medium |
| 25 | Max-AB nozzle T7 | 2,050–2,150 | K | ASSUMPTION; -400 survey up to ≈2,070 K uncorrected | Q1; TM-100159 Tbl II | Low-medium |
| 26 | HP-NGV cooling air | ≈11 % of CDP flow (≈520 °C) | % | TRANSFER: -400 | ARL 1985 | Medium |
| 27 | Customer bleed port / limits | HPC stage 7; ≈2.6–7.2 % of HPC inlet flow by regime | % | TRANSFER: -400 | [TM-104247 Fig. 5](https://ntrs.nasa.gov/citations/19920020182) | Medium |
| 28 | Bleed thrust sensitivity at MIL | ≈2 % thrust per 1 % bleed | – | TRANSFER: -400 | TM-104247 | Medium |
| 29 | PLA detents | GI ≈18, FI 31, IRP 87, min AB ≈92–94, max AB 130 | deg | TRANSFER: -400 rigging | ARL Fig. 28; [TM-4240](https://ntrs.nasa.gov/citations/19910009766); TM-100159 | High (-400) |
| 30 | PS3 max / min overrides | ≥425 / ≤80 | psia | TRANSFER: -400 | ARL Fig. 28 | Medium |
| 31 | FVG schedule | 47.5–52.5° (≤73 % N1c) → ≈0° (100–105 %) | deg | TRANSFER: -400 | CR-198052 Fig. 31 | Medium |
| 32 | FVG actuator stroke / max slew | 2.7 / 2.16 | in / in/s | TRANSFER: -400 | [CR-1998-208416](https://ntrs.nasa.gov/citations/19980219005) | Medium |
| 33 | CVG range idle → max | ≈48–52 → ≈0–14 | deg | TRANSFER: -400 | CR-191195 Fig. 33 | Medium-low |
| 34 | A8 at flight idle / MIL / max AB | 400 / 218–298 / 343–420 | in² | TRANSFER: -400 | TM-4240; TM-4538; [Conners 1989](https://ntrs.nasa.gov/citations/19900002425) | Medium |
| 35 | AB permission logic | N1 within 3 % of limit; 20.5 RU hold, 5.5 RU to start AB | – | TRANSFER: -402 | [NAWCADPAX/RTR-2001/1 p.9](https://archive.org/details/DTIC_ADA407860) | Medium |
| 36 | ECU trims | N1 ±300 rpm; T5 ±150 °F; AB ±65 RU | – | TRANSFER: -400 | [Glenny 1989](https://archive.org/details/DTIC_ADA210374) | Medium |
| 37 | Ignition permissive | NH 10–45 | % | TRANSFER: -400 | CR-1998-208416 | Medium |
| 38 | FADEC sample time (template) | 0.015–0.02 | s | TRANSFER: C-MAPSS40k/MAPSS (generic) | [TM-2010-216811](https://ntrs.nasa.gov/citations/20100037768); [MAPSS](https://ntrs.nasa.gov/citations/20040035577) | Low (IN20) |
| 39 | Fuel transport delay / FMV τ | 0.040 / 0.05 | s | TRANSFER: generic NASA | [TM-2010-216810](https://ntrs.nasa.gov/citations/20100037767); [TM-2007-215026](https://ntrs.nasa.gov/citations/20070034949) | Low-medium |
| 40 | PLA lag τ dry / AB | 0.625 / 0.550 | s | TRANSFER: -400 (GE-model fit) | TM-4240 | Medium |
| 41 | PLA rate limit (increasing) dry / AB | 19.03 / 26.81 (HARV sim 14 / 22) | deg/s | TRANSFER: -400 | TM-4240; [TM-110216](https://ntrs.nasa.gov/citations/19960027892) | Medium (conflict) |
| 42 | Nozzle closure on slam / held closed | ≈1 / ≈4 | s | TRANSFER: -400 (CF-18) | [Henry, AGARD-CP-448](https://archive.org/details/DTIC_ADA203800) | Medium |
| 43 | N1 acceleration time (nozzle-closed window) | 0.75–1.25 | s | TRANSFER: -400 | Muir et al. Fig. 4 | Medium-low |
| 44 | Fan-spool small-step τ | ≈0.77 | s | TRANSFER: -400 | Merrington, AGARD-CP-448 paper 36 | Medium-low |
| 45 | AB light-off MIL→max / FI→max | 0.7–2.7 / 3.6–8.0 (slow >6 / >9; no-light spec >6 / >15) | s | TRANSFER: -402 | NAWCADPAX/RTR-2001/1 | Medium-high |
| 46 | Surge pressure recovery | ≈0.2 | s | TRANSFER: -400 | [TM-1999-206572](https://ntrs.nasa.gov/citations/19990024943) | Medium |
| 47 | Rotor inertia HP / LP | ≈3 / ≈3.5 | kg·m² | ASSUMPTION (F100 5.65/6.10 scaled) | [TP-1034](https://ntrs.nasa.gov/citations/19770024210) | Low |
| 48 | T5 thermocouple τ | 1.25–3.9 (vs mass flux 30–5 lb/s·ft²) | s | TRANSFER: -400 | CR-1998-208416 Fig. 3 | Medium |
| 49 | JFS (GTSU-110) | 110 kW; 52 kg; 0.64 m; intake 0.29 m; twin-shaft, free PT, digital fuel control | – | DIRECT (Tejas) | [DDP](https://www.ddpmod.gov.in/hi/node/8778) | High |
| 50 | Consecutive-start requirement | ASR ≥2; IAF 3 (2 starts + dry rollover) | starts | DIRECT | [CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf) | High |
| 51 | Cold-start demonstration | −15 °C, 85 % battery, 18–42 h soak, 3 starts | – | DIRECT | [IDR 2015](https://indiandefencereview.com/lca-tejas-passes-cold-weather-test-at-leh/); [Livefist/DRDO](https://www.livefistdefence.com/?p=236) | Medium-high |
| 52 | Ground start timeline | PLA→idle at ≈20 % N2; light-off ≈27 s; starter cut-out ≈55 %; idle ≈63 % (70 % in text) at ≈40 s | – | TRANSFER: -102 (FADEC, ATS start) | [KSAS 2006 Fig. 2](https://koreascience.kr/article/JAKO200616039849001.pdf) | Medium |
| 53 | Hung-start monitor rule | N2 <60 % not rising 1 s (PLA 14–24°) or <60 % for 35 s | – | TRANSFER: NASA monitoring rule (not a GE limit) | TM-101702 | Medium-low |
| 54 | Spooldown airstart | relight from ≥24 % N2; time to idle 5.4–26 s (20–35 kft) | – | TRANSFER: -102 | KSAS 2006 Tbl 1 | Medium |
| 55 | Assisted airstart | engagement 35–40 % N2; time to idle 17–25 s (15–20 kft) | – | TRANSFER: -102 | KSAS 2006 Tbl 2 | Medium |
| 56 | Flameout detection | T5 < f(alt, PLA) AND dN2/dt < threshold → auto-relight | – | TRANSFER: -102, RM12 | KSAS 2006 p.92; SHK p.42 | Medium |
| 57 | Speed-sensor scaling NL / NH | 0.7 / 0.239 | Hz per rpm | TRANSFER: -400 | CR-191195 | High (-400) |
| 58 | T5 harness | 2 × 4 probes averaged; ±18 °F system error | – | TRANSFER: -400 | CR-1998-208416; CR-191195 | High (-400) |
| 59 | Aircraft data chain resolution / 2σ | N 16 rpm / 154 (N1), 138 (N2); T 1 K / 2 K (T5); PS3 0.5 / 1.2 psia | – | TRANSFER: -400 IECMS | Henry Tbl 1 | Medium (FADEC will differ) |
| 60 | Recording rates and event buffers | 10 Hz gas path, 1 Hz slow; 5 s pre + 25/35 s post | – | TRANSFER: -400 IECMS | earlier addendum; AGARD-CP-448 | Medium |
| 61 | Bearings / sumps / chip detectors | 5 / 3 (A, B, C) / 7 + NOAP | count | TRANSFER: -400 | ARL 1985; [Stemate 2002](https://archive.org/details/DTIC_AD1003532) | Medium-high |
| 62 | Test-cell vibration limits (mid-frame) | 1.0 steady (N1, N2 1/rev, overall); 2.0 transient (5 s) | in/s avg | TRANSFER: -400 | DSTO-TN-0530 Tbl 4 | High (-400) |
| 63 | Typical mid-frame vibration | ≈0.04–0.3 idle → 0.34–0.55 MIL/AB | in/s avg | TRANSFER: -400 | DSTO-TN-0530 | Medium |
| 64 | Oil-debris normal wear (CF188 Fe) | 0.47 mean, 1.68 2σ | µg/h | TRANSFER: -400 | [Bennett et al. 1996](https://archive.org/details/DTIC_ADP010173) | Medium |
| 65 | Oil pressure / temperature / tank capacity | not found | – | ASSUMPTION required | — | None |
| 66 | LUIs | 8 (Type I, Type III, EFTC, SRC, TAMP, full PS3, partial PS3 at 85 %, EOT) | – | TRANSFER: -400/-402 → Tejas ECMS "LUIs" | [Hess](https://archive.org/details/DTIC_ADA203800); [ADA](https://www.ada.gov.in/images/ps.htm) | Medium (defs) / Low (gates) |
| 67 | Example life limits (CF) | HPT DSR80 blade 30,000 EFT; rotor parts 4,300–15,200 LCF; 2,800 h EOT part | counts / h | TRANSFER: -400 | [Paré & Muir 1998 Fig. 7](https://archive.org/details/DTIC_ADA347270) | Medium |
| 68 | LUI accrual per airframe hour | ≈2–8 LCF; ≈22 EFT; ≈1.33 EOT h | per AFH | ASSUMPTION (derived from CF report) | Paré & Muir 1998 | Low |
| 69 | Accelerated mission test | 330 h ≈ 1,000 flight h (IN20); 550 cycles in 330 h (-102) | h / cycles | DIRECT / TRANSFER: -102 | GE 2008; [DTaQ](https://koreascience.kr/article/JAKO200673334943950.pdf) | Medium-high |
| 70 | TAC (USAF, comparison) | LCF + FTC/4 + CIC/40 | – | TRANSFER: USAF | [RTO-TR-028](https://apps.dtic.mil/sti/pdfs/ADA380949.pdf) | High (definition) |
| 71 | Fleet reliability anchors | USN F404 MTBF 67.4 h (1987–90); engine MTBF 383.5 h (1997–98) | h | TRANSFER: -400 | [King & Tooker](https://archive.org/details/DTIC_ADA277918); [Stearns](https://archive.org/details/DTIC_ADA359328) | Medium |

### Inferences

#### (c) Recommended engine-model architecture and calibration-target list

**Architecture [ASSUMPTION; each block cites its template]**
1. **Steady-state component layer (offline)** — pyCycle mixed-flow model re-designed per Q11 (no LPC; SLS dry design at W ≈70 kg/s, OPR 28, fan PR ≈4.35, BPR ≈0.28, T4 ≈1,780 K; AB as off-design with scheduled A8; HPX balance fixed), with CEA wet-air thermodynamics for humidity. Generic maps scaled; fan speed lines tuned to the CR-198052/TM-100159 Wc(N1c) curve × 1.05. Output: tables over altitude, Mach, ΔISA, power setting and health scalars (flow/efficiency per fan, HPC, HPT, LPT; VG offsets), or a residual-based on-line CLM (T-MATS) if real-time iteration is acceptable.
2. **Dynamic shell (online, ≥200 Hz engine step)** — two rotor ODEs (I_HP ≈3, I_LP ≈3.5 kg·m², tuned), optional volume states at burner/mixer (F100 TP-1034 structure), a lumped hot-section metal-temperature (heat-soak) state and HPT tip-clearance state (MAPSS TMPC / NASA TCML), T3/T13 lags 0.05 s, AB light-off state machine with ignition delay and slow/no-light probability rising as T1 and dynamic pressure fall (NAWCAD data), surge event model (CDP collapse/recovery ≈0.2 s; non-isolated re-stall window 2.4 s), windmill/spool-down physics for relight (T-50/RM12 data).
3. **FADEC layer (50–67 Hz)** — Q4 structure: PLA shaping; N2c schedule below IRP; isochronous NL = f(T1) at/above IRP with 104.4 % corrected cap; T5 limiter on A8; MIN/MAX selection of setpoint and limiters (N1, N2, PS3 max/min, accel/decel Wf/PS3, T5); FVG/CVG schedules; AB ratio-unit scheduling with permission, nozzle pre-open, T5 reset; flameout detection and auto-relight; FDIA with dual-sensor checks and FICA-style model substitution; fault codes. Core loop can be auto-tuned with **NASA TTECTrA**.
4. **Sensor and data-chain layer** — physical sensors with FOCSI scalings and dynamics (T5 τ(mass flux), 8-probe harness with open/short failure semantics, dual NL with mismatch logic, NH alternator, LVDT position sensors, PS3 transducer, flowmeters, oil pressure/temperature, mid-frame accelerometer with N1/N2 1/rev tracking, chip detectors), then FADEC/bus quantisation and noise (MSDC-class values as an upper bound), recorder rates and event buffers (10/1 Hz; 5 s pre + 25/35 s post; take-off snapshot).
5. **Health and usage layer** — degradation scalars driven by gamma-process drift and step faults; 8 LUIs per Q9 implementation; TAC and rainflow LTS cross-checks; CF-18 take-off health indices (fuel ratio units at 81/87 % N2, acceleration times, PS3 time-to-250 psi); oil-debris and vibration fault signatures by bearing/sump.

**Calibration-target list (in recommended order)**

| # | Target | Data | Source | Applicability |
|---|---|---|---|---|
| C1 | IN20 ratings | 84 kN max AB; 70 kg/s; OPR 28 (SLS ISA) | GE data sheet | DIRECT |
| C2 | Dry thrust | ≈54 kN | Wikipedia/FI (AGG) + closure | ASSUMPTION |
| C3 | Corrected airflow vs N1c | curve (Q5 T1) scaled ×1.05 | CR-198052 Fig. 2; TM-100159 Fig. 6 | TRANSFER -400 |
| C4 | Fan static-pressure ratio vs flow | PS21/PT2 table | CR-198052 Tbl 5, Fig. 3 | TRANSFER -400 |
| C5 | MIL nozzle conditions vs altitude | NPR 2.93–5.24, T8 ≈937 K constant, W8, A8, FG | TM-4538 Tbl 2 | TRANSFER -400 (scale T8 up for IN20) |
| C6 | Ground part-power to MIL | throttle 80/87/92/102: NPR, T8, W8, A8, FG | TM-4538 Tbl 4 | TRANSFER -400 |
| C7 | Altitude thrust ratios | Fg/δ2 anchors at 10–40 kft | TM-100159 p.8, Fig. 7 | TRANSFER -400 |
| C8 | AB thrust ratio vs AB f/a | 1.50–1.55 at 0.062–0.066 | TM-100159 Fig. 8 | TRANSFER -400 |
| C9 | Max-AB thrust envelope shape | 7 alt × 12 Mach FG table | TM-4240 Fig. 4 | TRANSFER -400 (HARV nozzle) |
| C10 | Installed thrust & bleed sensitivity | 92 % N2 / MIL / max AB; −100 to −428 lbf per lb/s | TM-104247 Tbl 2 | TRANSFER -400 |
| C11 | Part-power take-off snapshot | N1 10,560, N2 14,204 rpm, T5 871 K, PS3 137.9, P5 24.7 psia | Henry Tbl 1 | TRANSFER -400 |
| C12 | In-flight points | 30 kft M0.9 PLA 87 and M1.2 PLA 130 (N1, A8, Wf, WFAB, FN) | Conners 1989 Tbl 3 | TRANSFER -400 |
| C13 | Cruise fuel flow | ≈1,650–1,850 lb/h per engine at M0.56/25 kft | TM-2003-210734 Fig. 9b | TRANSFER -400 |
| C14 | T5 at MIL and limit | ≈1,500 °F test cell; 830 °C limit | CR-191195 Fig. 33; TM-101702 Fig. 6 | TRANSFER -400 |
| C15 | Vane schedules | FVG vs N1c table; CVG idle/high-power levels | CR-198052 Fig. 31; CR-191195 Fig. 33 | TRANSFER -400 |
| C16 | Step/slam responses | FG, NPR, A8 vs time (FI→MIL→max→min AB) at 35 kft M0.2/M0.7 | TM-4240 Figs. 9–10 | TRANSFER -400 |
| C17 | Take-off transient indices | nozzle closed ≈1 s/≈4 s; N1 accel time 0.75–1.25 s; PS3 plateau 4–5 s; fuel ratio units 88–100 % | AGARD-CP-448 papers 7, 37 | TRANSFER -400 |
| C18 | Fan-spool dynamics | τ ≈0.77 s small step | AGARD-CP-448 paper 36 | TRANSFER -400 |
| C19 | AB light-off timing | MIL→max 0.7–2.7 s; FI→max 3.6–8.0 s; slow/no-light criteria | NAWCADPAX/RTR-2001/1 | TRANSFER -402 |
| C20 | Ground start | ≈26 s rotation-to-idle, light-off ≈27 s, idle ≈63–70 % N2 | KSAS 2006 Fig. 2 | TRANSFER -102 |
| C21 | Airstarts | Tables 1–2 (spooldown, APU-assisted); auto-relight N2 dip ≈85→70 % | KSAS 2006 | TRANSFER -102 |
| C22 | Flameout rundown | NH/NL/T5/PS3/A8/CVG traces after bird strike | SHK RM 2019:02 Fig. 18 | TRANSFER RM12 |
| C23 | Surge | CDP 85→10 psia, recovery ≈0.2 s | TM-1999-206572 Fig. 9 | TRANSFER -400 |
| C24 | Vibration | test-cell levels and limits by power | DSTO-TN-0530 | TRANSFER -400 |
| C25 | Oil debris | QFDA element wear rates mean/2σ | Bennett et al. 1996 | TRANSFER -400 |
| C26 | Fault signatures | Muir direction matrix and measured shifts; Henry take-off shifts | AGARD-CP-448 papers 7, 37 | TRANSFER -400 |
| C27 | Cold-start capability | 3 starts at −15 °C, 85 % battery, 18–42 h soak | CAG 2015; HAL/DRDO 2015 | DIRECT |
| C28 | Data-chain texture | resolution and 2σ precision | Henry Tbl 1 | TRANSFER -400 |

- [ASSUMPTION] Acceptance tolerances for the virtual engine: ±3 % steady-state vs TRANSFER targets after scaling (matching TM-4240's own 3 %), ±25 % on transient timing (TM-4240's transient accuracy), exact reproduction of DIRECT IN20 ratings, and correct **sign** of every fault signature in the Muir matrix.

### Gaps

#### (d) Open questions / gaps
1. **IN20-specific cycle values**: dry thrust, BPR, fan/HPC PR, T41/T4, T5 limits, 100 % N1/N2 rpm, SFC — none officially released. Best routes: ADA/HAL/IAF via the PS owner; Powell 1991 (JEGTP 113:1–10) and Larsson 1988 (ASME 88-GT-305) full texts for -402/RM12 deltas.
2. **FADEC**: channel count, backup mode, sample rate, schedules, gains, limit values, fault-code dictionary — not public for IN20/-102/RM12.
3. **NATOPS-only values not replaced** (Q7 table): start EGT limit, idle fuel flow, idle/MIL oil pressure, -402 MIL EGT limit (880 °C in the restricted copy), thermal-soak restart rule, MIL-check N2 band.
4. **Oil system numbers** (capacity, pressure vs N2, temperature limits, consumption, filter ΔP, fuel-oil cooler) — none found in released material.
5. **LUI gates and weightings** (N2 levels for Type I/III, EFTC and SRC formulas) — not public; Phalanx must declare its own.
6. **Rotor inertias, volumes, heat-soak constants and accel/decel schedules** — no F404 data; tuned assumptions required.
7. **Relight envelope boundary** — only tested points (T-50) and RM12 >350 kt rule.
8. **Deterioration rates and wash recovery** for F404/IN20 — none public.
9. **Conflicts left open**: -400 MIL thrust 10,000 vs 10,600 vs 10,700 lbf; -402 BPR 0.27 vs 0.29 vs "higher than -400"; -400 OPR 25 vs 26; RM12 airflow 152 vs 158 lb/s and fan flow +10 % vs +5 %; RM12 TIT 1,426 °C vs (-400 1,390 °C + 105 °C); PLA rate limits 19.03/26.81 vs 14/22 °/s; dry N2 schedule temperature input T1 vs T2.5; MIL A8 ≈220 vs 249–298 in²; Henry's earlier OCR values (corrected here).
10. **Searches not run (budget)**: Finnish/Swiss/Spanish F404 technical papers; CF-18 flight-safety reports with engine traces (the 2010 Lethbridge FSIR summary gives no engine data); Korean KSAS papers on T-50 engine EHM beyond the airstart paper; Indian conference papers on LCA intake–engine compatibility; DoD IG audits on F404 life-limited parts (media.defense.gov blocked automated download).

#### (e) Ranked sources (most valuable first)
1. **ARL-AERO-PROP-TM-426 (Frith 1985), "The GE F404 – Engine of the RAAF's New Fighter"** — the only officially released F404 cycle table (TIT, fan/HPC PR and speeds), control-mode chart, materials, sumps and chip detectors. https://archive.org/details/DTIC_ADA164562
2. **AGARD-CP-448 (1988)** — papers 2 (LUIs), 7 (fault matrix, take-off indices), 36 (fan-spool identification), 37 (precision, take-off shifts). https://archive.org/details/DTIC_ADA203800
3. **NASA CR-191195 / CR-179568 / CR-1998-208416 (GE FOCSI/OCLPC)** — sensor physics, interface diagram, control logic, T5 τ. https://ntrs.nasa.gov/citations/19940032893 ; https://ntrs.nasa.gov/citations/19890003885 ; https://ntrs.nasa.gov/citations/19980219005
4. **NASA CR-198052 and TM-100159** — corrected airflow, FVG schedule, PS21 tables, PSL thrust and AB ratios. https://ntrs.nasa.gov/citations/19970027377 ; https://ntrs.nasa.gov/citations/19870020104
5. **NASA TM-4538, TM-4240, TM-104247, TP-3001** — MIL nozzle tables, simple dynamic model and step responses, installed thrust/bleed, PLA map. https://ntrs.nasa.gov/citations/19940010668 ; https://ntrs.nasa.gov/citations/19910009766 ; https://ntrs.nasa.gov/citations/19920020182 ; https://ntrs.nasa.gov/citations/19900015818
6. **Jung et al. 2006, "T-50 Engine Airstart Test" (KSAS 34(2))** — FADEC F404-102 ground start and airstart tables (local copy). https://koreascience.kr/article/JAKO200616039849001.pdf
7. **NAWCADPAX/RTR-2001/1** — F404-402 AB light-off times/criteria, AB permission logic, 1553 engine words. https://archive.org/details/DTIC_ADA407860
8. **DSTO-TN-0530 (Marsden 2003)** — vibration sensors, limits, levels, 100 % N2 = 280 Hz. https://archive.org/details/DTIC_ADA423658
9. **CAG Report 17 of 2015 + DDP GTSU-110 page + HAL/DRDO 2015 statements** — Tejas JFS and start requirements. https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf ; https://www.ddpmod.gov.in/hi/node/8778
10. **SHK RM 2019:02 + Meyer 2014 + Carlson & Gustafsson 2014** — RM12 FADEC flameout logic, rundown trace, LTS method. https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf ; https://publications.lib.chalmers.se/records/fulltext/201537/201537.pdf ; https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf
11. **Paré & Muir 1998; Stemate 2002; Glenny 1989; Larkin et al. 1987 (IFDIS)** — CF/RAAF life tracking, part limits, IFSD causes, ECU trims, troubleshooting thresholds. https://archive.org/details/DTIC_ADA347270 ; https://archive.org/details/DTIC_AD1003532 ; https://archive.org/details/DTIC_ADA210374 ; https://archive.org/details/DTIC_ADA227757
12. **NASA C-MAPSS40k (TM-2010-216810/216811), MAPSS (TM-2004-212968), T-MATS, TTECTrA, TP-1034** — controller/dynamic-shell templates. https://ntrs.nasa.gov/citations/20100037768 ; https://ntrs.nasa.gov/citations/20040035577 ; https://github.com/nasa/T-MATS ; https://github.com/nasa/TTECTrA ; https://ntrs.nasa.gov/citations/19770024210
13. **pyCycle mixed-flow example** — steady-state cycle code base. https://github.com/OpenMDAO/pyCycle/blob/master/example_cycles/mixedflow_turbofan.py
14. **GE data sheet and press releases** — the only DIRECT IN20 facts. https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf
15. **Stearns 1998 / King & Tooker 1993 (NPS)** — -400 vs -402 table, life cuts, reliability. https://archive.org/details/DTIC_ADA359328 ; https://archive.org/details/DTIC_ADA277918
16. **Bennett et al. 1996 (QFDA)** and **Swiss Military Justice 2017 report** — oil-debris statistics; "L STALL" caution and stall procedure. https://archive.org/details/DTIC_ADP010173 ; https://www.newsd.admin.ch/newsd/message/attachments/48614.pdf
17. **Paywalled, to obtain**: Powell 1991 JEGTP 113:1–10 (https://doi.org/10.1115/1.2906525); Eustace et al. 1994 JEGTP 116:178–183 (https://doi.org/10.1115/1.2906789); Larsson et al. ASME 88-GT-305 (https://doi.org/10.1115/88-gt-305); Daub AIAA-85-1461 (https://doi.org/10.2514/6.1985-1461); Williams & Wendel AIAA-84-1330 (https://doi.org/10.2514/6.1984-1330); Linebrink & Vizzini SAE 821371.
