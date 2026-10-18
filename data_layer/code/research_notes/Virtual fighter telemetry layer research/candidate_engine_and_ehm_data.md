# Candidate fighter engines and their engine-health-monitoring (EHM) systems: depth of public data (Project Phalanx)

**Scope.** This note asks which candidate fighter engine can be modelled most faithfully from public information, and documents exactly what is public for each. "Faithfully" covers the thermodynamic cycle, control, transients, sensors, monitoring and degradation.

Engines covered:
- F404 family: -400/-402, IN20, -102
- RM12
- F414
- F100: -100/-200/-220/-229, plus the EMD/PW1128 derivative
- F110: -100/-129/-400/-132
- AL-31F/FP
- M53-P2
- M88-2
- GTX-35VS Kaveri / KDE

**Cross-links.** These topics are covered by parallel researchers and are only touched here:
- IAF platform relevance
- airframe modelling
- public datasets (C-MAPSS/N-CMAPSS)
- sensor residual texture
- faults and degradation
- validation and calibration
- maintenance records
- modelling methodology
- data pathway and formats
- flight profiles

**Method and limits (read first).** The coordinator ran this as six parallel deep-dive sub-agents plus direct checks.
- **Search cap.** The shared WebSearch budget for the turn (200 calls across all agents) ran out early. After that, work continued only through:
  - direct fetches of known primary URLs;
  - the NASA NTRS catalogue;
  - archive.org mirrors of DTIC documents. DTIC itself (apps.dtic.mil) was "Under Maintenance" or returned 403 for the whole session.
  - **Under-covered as a result:** Chinese CNKI AL-31F literature, Swedish DiVA full texts (unreachable), French theses, Indian CAG primary reports, and ASME/AIAA/SAE full texts (paywalled or behind bot checks).
- **Local copies.** All PDFs relied on are saved under `/Users/abishaikc/Phalanx/research_sources/engine_data/`, in subfolders `f404_f414_cycle/`, `f404_monitoring/`, `rm12/`, `f100/`, `f110_usaf/`, `al31_m53_m88_kaveri/`, `open_models/` and `synthesis_checks/`.
- **Verification.** Key numbers were spot-checked in those local copies:
  - AGARD-CP-448: IECMS, F100-PW-220 EMS, F110-GE-100 EMS and M53 papers;
  - NASA TM-4240, TM-104326 and TP-1056;
  - SHK RM 2019:02;
  - RTO-TR-028 and MIL-HDBK-1783B;
  - DSJ 2022 (Sankar).
- **Evidence tags.** Each claim is tagged:
  - [DIRECT]: about the exact engine or system;
  - [TRANSFER: source]: borrowed from another engine, with the reason it transfers and its limits;
  - [ASSUMPTION]: engineering judgement, with a note on how to validate it;
  - "AGG": a number found only in an aggregator (Wikipedia, Forecast International, enthusiast sites). Treat as unverified.

---

## 1. Public cycle and design data per engine (incl. station numbering)

### Takeaway
Every candidate has public headline numbers: thrust, airflow, OPR, weight, and usually stage counts. Turbine inlet temperature, EGT/FTIT redlines, 100% spool speeds and SFC are almost never in a primary source; they come from aggregators or have to be inferred from test data.

Two engines stand out:
- **F404-GE-400**: NASA flight and altitude-cell reports give unusually rich *operating-point* data (airflow, NPR, T8, A8, N1 scale, PLA map).
- **AL-31F**: an enthusiast site reproduces an apparently manual-derived regime table with speeds, SFCs, limits and transient times. It is complete, but its provenance is unverified (AGG).

### Cited Findings

#### Consolidated headline table (sea-level static, standard day unless noted; "nf" = not found publicly)

**Thrust, airflow and pressure ratios**

| Engine | Max AB thrust | Dry/MIL thrust | Airflow | OPR | BPR |
|---|---|---|---|---|---|
| F404-GE-400 | ≈16,000 lbf [DIRECT, TM-1999-206572; TM-101702] (16,100 in TM-107601; conflict) | ≈10,700 lbf [DIRECT] (10,000 in NASA 19970001572; conflict) | max corrected ≈145 lbm/s [DIRECT]; MIL in flight 144.9–146 [DIRECT, CR-198052 Tbl C1] | nf (family 26:1) | ≈0.33 ("≈¼ of fan air bypassed") [DIRECT, TM-88273 p.3] |
| F404-GE-402 / -102 / -103 | 17,700 lb class (78.7 kN) [DIRECT, GE sheet] | 11,000 lbf (AGG) | 146 lb/s [DIRECT] | 26:1 [DIRECT] | 0.34 (AGG) |
| F404-GE-IN20 (Tejas) | 19,000 lb class (84 kN) [DIRECT, GE sheet]; ">19,000 lb (85 kN)" [DIRECT, GE 2007 release] | 12,139 lbf (AGG) | 153 lb/s (70 kg/s) [DIRECT] | 28:1 [DIRECT] | nf |
| RM12 (Gripen C/D) | 80.5 kN (18,100 lb) [DIRECT, GE RM12 sheet] | 54 kN (AGG, Forecast Intl) | 69 kg/s (152 lb/s) [DIRECT, GE]; 68 (sv-wiki) and 71.67 (FI) conflict | 27:1 [DIRECT, GE] (27.5 AGG) | ≈0.31 (AGG) |
| F414-GE-400 / -39E / INS6 | 22,000 lb class (98 kN) [DIRECT, GE F414 sheet] | 13,000 lbf (AGG) | 170 lb/s [DIRECT] | 30:1 [DIRECT] | 0.25 [DIRECT, MTU] |
| F100-PW-100/-200 | "25,000 lb class"/111 kN [DIRECT, NASA TP-1228 p.2]; 23,930 (AGG) | 14,690 (AGG) | design corrected 98.4 kg/s (217 lb/s), F100(2) [DIRECT, TP-1069 p.8] | 24 (AGG) | 0.8 [DIRECT, CP-2298 P3] vs ≈0.6 [TM-86745] (conflict) |
| F100-PW-220 | 23,830 lb [DIRECT, RAND N-3618 Tbl 1.1] | 14,590 (AGG) | 228 lb/s [RAND] | 24 [RAND] | 0.63 [RAND] |
| F100-PW-229 | 29,160 lb / 129.7 kN [DIRECT, P&W via RTX] | 17,800 (AGG) | 248 (AGG) | 32:1 [DIRECT, P&W] | 0.36 [DIRECT, P&W] |
| F110-GE-100 | 28,200 (AGG) | measured IRT 16,778 lb in test cell [DIRECT, ESL-TR-89-13 Tbl 4] | 260.45 lb/s corrected at IRT [DIRECT] | 30.4 (AGG) | 0.87 (AGG) |
| F110-GE-129 | 29,000 lb class (129 kN) [DIRECT, GE sheet] | 17,155 (AGG) | 270 lb/s [DIRECT] | 30.7 [DIRECT, MTU] | 0.76 [DIRECT, GE] |
| AL-31F / FP | 12,500 kgf (122.6 kN) (AGG, leteckemotory regime table) | 7,770 kgf ±2% (76.2 kN) (AGG); 7,600/7,670/7,850 elsewhere (conflict) | 112 (+1/−2) kg/s (AGG) | ≈23 (LPC 3.54 × HPC 6.46) (AGG) | 0.571 (AGG; 0.56/0.59 conflict) |
| M53-P2 | 95.13 kN [DIRECT via fr-wiki citing Safran 2011 sheet; sheet not retrieved] | 64.35 kN | 92 kg/s at 10,600 rpm (fr-wiki) | 9.8 | 0.35–0.36 |
| M88-2 | 75.6 kN (17,000 lb) [DIRECT, Snecma sheet 06/2009]; 73.4 kN on current Safran page (conflict) | 50.0 kN [DIRECT] | 65 kg/s [DIRECT] | 24.5 [DIRECT] | 0.30 [DIRECT] |
| Kaveri GTX-35VS | 81 kN target (AGG, Jane's via en-wiki); achieved ≈70.5 kN AB / 46 kN dry (2022, secondary) | 52 kN target | 78 kg/s (AGG) | 21.5 (goal 27) (AGG) | 0.16 (AGG) |

**Stages, temperatures and SFC**

| Engine | Stages (fan/LPC – HPC – HPT – LPT) | TIT | SFC dry / AB |
|---|---|---|---|
| F404-GE-400 | 3–7–1–1 [DIRECT, TM-4240 p.2; TP-3001 p.3] | nf | nf |
| F404-GE-402 / -102 / -103 | 3–7–1–1 (AGG) | nf | 0.81 / 1.74 (AGG) |
| F404-GE-IN20 (Tejas) | 3–7–1–1 (AGG / TRANSFER) | nf | nf |
| RM12 (Gripen C/D) | 3–7–1–1 [DIRECT, SHK p.16] | ≈1,426 °C "estimated" (AGG) | 0.844 / 1.79 lb/lbf·h (AGG) |
| F414-GE-400 / -39E / INS6 | 3–7–1–1 (AGG) | nf | 0.84 / 1.85 (AGG) |
| F100-PW-100/-200 | 3–10–2–2 [DIRECT, TM X-3261 p.3] | nf | nf |
| F100-PW-220 | 3–10–2–2 [DIRECT, CR-179447] | nf | 0.73 (dry) [RAND] |
| F100-PW-229 | 3–10–2–2 [DIRECT, TM-1998-206560] | 2,460 °F (AGG) | 0.76 / 1.94 (AGG) |
| F110-GE-100 | 3–9–1–2 (AGG) | nf | nf |
| F110-GE-129 | 3–9–1–2 (AGG). NASA TM-104326 p.6 says "seven-stage" HPC (conflict) | 2,750 °F (AGG) | nf |
| AL-31F / FP | 4–9–1–1 (ru-wiki; brazd says 10-stage HPC) | 1,665 K (ru-wiki; 1,685 K zh-wiki) | ≤0.75 / ≤1.92 kg/kgf·h (AGG) |
| M53-P2 | single shaft: 3 LP + 5 HP compressor, 2-stage turbine | 1,560 K (text) vs 1,600 K (infobox) | 0.90 / 2.10 kg/daN·h (en-wiki) |
| M88-2 | 3–6–1–1 [DIRECT] | 1,850 K [DIRECT] | 0.80 / 1.70 kg/daN·h [DIRECT] |
| Kaveri GTX-35VS | 3–6–1–1 (AGG) | ≈1,700 K (AGG) | 0.78 / 2.03 (AGG) |

Sources for both tables:
- [GE F404 sheet](https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf)
- [GE RM12 sheet](https://www.geaerospace.com/sites/default/files/datasheet-RM12.pdf)
- [GE F414 sheet](https://www.geaviation.com/sites/default/files/datasheet-F414-Family.pdf)
- [MTU F414](https://www.mtu.de/engines/military-aircraft-engines/fighter-aircraft/f414/)
- [GE IN20 2007 release](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-engines-ordered-india-light-combat-aircraft)
- [NASA TM-4240](https://ntrs.nasa.gov/citations/19910009766)
- [NASA TP-3001](https://ntrs.nasa.gov/citations/19900015818)
- [NASA TM-88273](https://ntrs.nasa.gov/citations/19880010923)
- [NASA TM-1999-206572](https://ntrs.nasa.gov/citations/19990024943)
- [NASA CR-198052](https://ntrs.nasa.gov/citations/19970027377)
- [NASA TM-101702](https://ntrs.nasa.gov/citations/19900013006)
- [NASA TM-107601](https://ntrs.nasa.gov/citations/19920024293)
- [Forecast Intl RM12 (archived)](https://www.forecastinternational.com/archive/disp_pdf.cfm?DACH_RECNO=989)
- [SHK RM 2019:02](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf)
- [NASA TM X-3261](https://ntrs.nasa.gov/citations/19750019996)
- [NASA TP-1228](https://ntrs.nasa.gov/citations/19780015152)
- [NASA TP-1069](https://ntrs.nasa.gov/citations/19780013169)
- [NASA CP-2298 Paper 3](https://ntrs.nasa.gov/citations/19860015874)
- [NASA TM-86745](https://ntrs.nasa.gov/citations/19880014421)
- [RAND N-3618](https://www.rand.org/pubs/notes/N3618.html)
- [NASA CR-179447](https://ntrs.nasa.gov/citations/19910010772)
- [NASA TM-1998-206560](https://ntrs.nasa.gov/citations/19980228163)
- [P&W F100 page via RTX](https://www.rtx.com/prattwhitney/products/military-engines/f100)
- [ESL-TR-89-13, DTIC ADA234251](https://apps.dtic.mil/sti/tr/pdf/ADA234251.pdf)
- [GE F110-GE-129 sheet](https://www.geaerospace.com/sites/default/files/datasheet-F110-GE-129.pdf)
- [MTU F110](https://mtu.de/engines/military-aircraft-engines/fighter-aircraft/f110)
- [NASA TM-104326](https://ntrs.nasa.gov/citations/19970003552)
- [leteckemotory AL-31](http://www.leteckemotory.cz/motory/al-31)
- [ru-wiki AL-31F](https://ru.wikipedia.org/wiki/АЛ-31Ф)
- [fr-wiki M53](https://fr.wikipedia.org/wiki/Snecma_M53)
- Snecma M88-2 sheet (June 2009), local copy `al31_m53_m88_kaveri/omnirole_Fiche-technique-M88.pdf`
- [Safran M88 page](https://www.safran-group.com/products-services/m88-proven-performance-and-reliability)
- [en-wiki Kaveri](https://en.wikipedia.org/wiki/GTRE_GTX-35VS_Kaveri)

#### Speeds, limits and operating points that matter for a telemetry generator

**F404-GE-400**
- **100% N1 ≈ 13,270 rpm** [DIRECT]. Four sources agree:
  - N1 instrument range 0–13,270 rpm ([TP-3001 Tbl 2](https://ntrs.nasa.gov/citations/19900015818));
  - NL pickup 0.7 Hz/rpm (42 fan blades), with 2,787 Hz = 30% and 10,683 Hz = 115% ([NASA CR-191195](https://ntrs.nasa.gov/citations/19940032893) §4.7.2; [NASA CR-1998-208416](https://ntrs.nasa.gov/citations/19980219005) §3.3);
  - "5% (664 rpm)" (CR-1998-208416 §7.8.2);
  - N1 accuracy ±132.7 rpm = 1% ([CR-198052](https://ntrs.nasa.gov/citations/19970027377)).
- **100% N2: not found publicly.** The NH sensing range is 816–18,515 rpm (alternator, 0.239 Hz per core rpm) [DIRECT, CR-191195 §3.1].
- **T5 (EGT) numeric limit: not found publicly.**
  - The T5 limit is reached "just prior to IRP", "generally… above 1250°F" [DIRECT, CR-1998-208416 §7.2.3].
  - The production T5 sensing range is 700–1,600 °F [DIRECT, CR-191195 §3.1].
  - A test-cell sweep (read from plot) gives ≈770 °F at idle and ≈1,500 °F at max [DIRECT, CR-191195 Fig. 33].
- **PLA map**: flight idle 31°, IRP 87°, min AB ≈94°, max AB 130° [DIRECT, [TM-4240](https://ntrs.nasa.gov/citations/19910009766) p.2; [TM-100159](https://ntrs.nasa.gov/citations/19870020104) p.7].
  - Conflict: an F-18 tested in 1992 used idle 35° and IRP 102° ([TM-4538](https://ntrs.nasa.gov/citations/19940010668)). The rigging depends on the control version.
- **A8**:
  - Sensor range 220–540 in² [DIRECT, TP-3001 Tbl 2].
  - Flight idle ≈400 in²; MIL ≈220 in²; max AB 343–370 in² [DIRECT, TM-4240 p.3 and Fig. 9e; [TM-110216](https://ntrs.nasa.gov/citations/19960027892) §4.1].
  - IRP at low altitude 249–303 in² with AE9/AE8 = 1.24–1.49 [DIRECT, [TM-4538](https://ntrs.nasa.gov/citations/19940010668) Tbls 2–4].
- **Ground IRP calibration point** [DIRECT, TM-4538]: NPR 2.72, T8 1,672 °R, W8 120.6 lb/s, A8 264 in², FG 8,718 lbf.

**F404 in the field (C/D-era IECMS data)** [DIRECT, AGARD-CP-448 paper 37 (Henry) Tbl 1, [archive.org DTIC ADA203800](https://archive.org/details/DTIC_ADA203800)]
- Aircraft target points: XN1 10,560 rpm, XN2 14,204 rpm, T5 971.0 K, PS3 137.9 psia, P5 24.7 psia.
- Test-cell target points: XN1 10,962 rpm, XN2 14,215 rpm.

**RM12 in-flight points** [DIRECT, digitised by a sub-agent from [SHK RM 2019:02](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf) Fig. 18, p.41]
- At PLA ≈67° (1,400 ft, 304 kt): NL ≈83%, NH ≈89%, PS3C ≈1,390–1,630 kPa, T5 ≈950 K, A8 ≈19–20%.
- At PLA ≈49°: NL 64%, NH ≈80%, PS3C ≈800 kPa, T5 ≈790 K.
- Maximum spool speeds: LP 221 r/s (≈13,260 rpm), HP 280 r/s (≈16,800 rpm) (AGG, en-wiki).
- Fan structural reference speed: 212.2 r/s [DIRECT, [Meyer 2014](https://publications.lib.chalmers.se/records/fulltext/201537/201537.pdf) p.3].
- [ASSUMPTION] 13,260 rpm is consistent with the F404's 13,270 rpm 100% N1. Validate against a Swedish or GE primary source.

**F100**
- 100% N2 = 14,000 rpm [DIRECT, [CP-2298](https://ntrs.nasa.gov/citations/19860015871) symbols; [TM-85902](https://ntrs.nasa.gov/citations/19840016520)].
- FTIT limit of 1,720 °F (938 °C) in the P&W status deck CCD 1148-0.0, which "closely approximates -220" [TRANSFER, [CR-179447](https://ntrs.nasa.gov/citations/19910010772) p.3].
- PSC limit for the PW1128 (EMD) FTIT: 2,300 °R (1,840 °F) [DIRECT EMD, [TM-4494](https://ntrs.nasa.gov/citations/19940006733)].
- PLA: idle ≈20°, IRP 83°, max AB 130° for F100(3) [DIRECT, [TP-1034](https://ntrs.nasa.gov/citations/19770024210) p.6].
- Rotor inertias, -100(1): HP 5.152 and LP 6.10 kg·m² [DIRECT, [TM X-3261](https://ntrs.nasa.gov/citations/19750019996) Tbl I].

**F110-GE-100 test cell** [DIRECT, S/N 509153, Tinker AFB 1988, [ESL-TR-89-13](https://apps.dtic.mil/sti/tr/pdf/ADA234251.pdf) Tbl 4 p.22]

| Setting | N1 (rpm) | N2 (rpm) | Airflow, corrected (lb/s) | Fuel flow (lb/h) | Thrust (lb) | T4B |
|---|---|---|---|---|---|---|
| Idle | 3,301.5 | 10,651.5 | — | 1,104.5 | 700 | — |
| IRT | 8,184 | 14,643.5 | 260.45 | 10,673 | 16,778 | 806.7 °C |

**F110-GE-129, F-16XL ship 2** [DIRECT, [NASA TM-104326](https://ntrs.nasa.gov/citations/19970003552) Tbls 4–6]
- Idle at PLA 20°; IRT at PLA 85°.
- Ground run at 2,270 ft, PLA 85.2°: N1 8,215, N2 14,710 rpm, PS3 314 psia, WFE 9,385 lb/h, EGT 1,996 °R, A8 444 in².
- 39 measured operating points in total, each against the GE deck. Spot-checked in the local copy.

**AL-31F** (AGG, [leteckemotory](http://www.leteckemotory.cz/motory/al-31); the site says it is based on the AL-31F manual; primary not verified)
- Spool speeds: N1 99% = 10,098 rpm; N2 100% = 13,300 rpm.
- Regimes: idle N2 70% (9,300 rpm), ≤250 kgf; cruise N2 85–90%.
- Turbine-exit gas temperature limit: ≤750 °C at M ≤1.9; ≤765 °C at M >1.9; +15 °C allowed for ≤5 s in transients.
- AL-31FP thrust vectoring: ±15° per nozzle with nozzle axes canted 32° (en-wiki Su-30MKI, AGG); TVC adds ≈110 kg [DIRECT, [Aviapanorama 1997](https://www.aviapanorama.narod.ru/journal/1997_2/heart.htm)].

**M53-P2**: 10,600 rpm = 103% (fr-wiki) [DIRECT-secondary, [fr-wiki M53](https://fr.wikipedia.org/wiki/Snecma_M53)].

#### Station numbering
- **SAE AS755.**
  - AS755G (2024) is the current performance station designation standard; nomenclature has moved to AS6502 [DIRECT, [SAE AS755G page](https://www.sae.org/standards/as755g-aircraft-propulsion-system-performance-station-designation)].
  - The full text is paywalled. ARP755-style stations for a two-spool mixed-flow afterburning turbofan are drawn in [Grönstedt & Rosell 2022](https://research.chalmers.se/publication/528520) Fig. 1: 0, 2, 13/16 (bypass), 21/25, 3, 4, 45, 5, 6 (mixed), 7, 8 (throat), 9 (exit).
- **F404 public literature**: 0 free stream, 1 engine face (T1/PT1), 2.1 fan discharge (PS21), 2.5 HPC inlet (T2.5), 3 HPC discharge (PS3), 4 combustor exit, 5 LPT rotor exit (TT5 = EGT), 5.58/"56" LPT discharge plane (PT56/T56), 6 AB inlet, 7 nozzle inlet, 8 throat, 9 exit [DIRECT, [TP-3001](https://ntrs.nasa.gov/citations/19900015818) Fig. 2].
  - There is **no station 4.5** in F404 documents; EGT is measured at LPT exit.
  - In the PSL report, station 1 is the airflow-measuring station and 2 the engine face (conflict) ([TM-100159](https://ntrs.nasa.gov/citations/19870020104) App. A).
- **F100/PW1128**: 2 fan face, 2.5 HPC inlet, 3 HPC exit, 4 HPT inlet, 4.5 LPT inlet (= FTIT), 6 augmentor inlet (PT6), 7 throat [DIRECT, [TM-4426](https://ntrs.nasa.gov/citations/19930003967)].
- **F110**:
  - The GE EMS uses T2 (fan inlet), T2.5, PS3 and T4B (HPT blade metal temperature by pyrometer) [DIRECT, AGARD-CP-448 paper 11 Tbl 1].
  - NASA uses 1 as engine face and 2.5 as core inlet ([TM-104326](https://ntrs.nasa.gov/citations/19970003552) Fig. 3).
- **RM12**: its signal names (NLPC, NHPC, FVG, CVG, A8, PS3C, T5) match F404 naming [DIRECT names, SHK Fig. 18; TRANSFER of meaning from F404].

### Inferences
- [ASSUMPTION] For the F404 family, publicly available *measured* operating points are richer than headline datasheets. They can anchor a cycle model at the engine face (Wc vs N1c), across the fan (PS21/PT2), at the nozzle (NPR, T8, A8) and in thrust. Missing quantities (TIT, OPR for the -400, T5 limit) can be bracketed from test data:
  - T5 limit just above 1,250 °F;
  - fan PR ≈4 from PS21/PT2 3.6–4.0 [DIRECT, CR-198052 Tbl 5];
  - HPC PR ≈6.5 if OPR ≈26.
  - Validate by cycle-matching TM-100159, CR-198052 and TM-4538 simultaneously.
- [TRANSFER: F404-GE-402 → F404-GE-IN20] The IN20 is a -402 derivative with a higher-flow fan, single-crystal turbine blades and a FADEC ([GE 2004 release](https://www.geaerospace.com/news/press-releases/defense-engines/ge-awarded-105-million-development-contract-india); [GE 2007 release](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-engines-ordered-india-light-combat-aircraft)).
  - Scaling a calibrated -400/-402 cycle to 153 lb/s, OPR 28 and 84 kN is defensible.
  - Limits: the IN20's TIT uplift and its FADEC schedules are unknown.
- [ASSUMPTION] RM12 and F404-IN20 sit at almost identical points: 69 vs 70 kg/s, OPR 27 vs 28, 80.5 vs 84 kN, 3-7-1-1 stages. RM12 public flight data (SHK) can therefore serve as a second calibration source for an IN20 model.

### Gaps
- TIT and turbine-exit temperature limit schedules are not found publicly for any US/Swedish engine. Only aggregators give them for AL-31F, M53 and Kaveri; M88-2 has an official TIT (1,850 K).
- 100% N2 rpm for F404/IN20/F414 and N1/N2 redlines for F404/F414/F110: not found. These sit in limited-distribution NATOPS and GE operating instructions; do not use leaked copies (see Section 6 Gaps).
- F110 stage count conflict (9-stage per AGG vs "seven-stage" in NASA TM-104326) is unresolved.
- Kaveri cycle numbers are aggregator-only. The CAG 2010-11 audit was not retrieved.
- SAE AS755 full text was not read (paywalled).

---

## 2. Component maps, open-source and published models (incl. calibration to these engines)

### Takeaway
**No actual (dimensional) component maps for any candidate engine are public.**

The F100 family is the clear exception for *model* depth. NASA published:
- a complete real-time nonlinear F100 model with equations;
- normalised ("fraction of design") fan/HPC/turbine/AB maps;
- rotor inertias and gas volumes;
- linearised state-space models;
- onboard Kalman-filter models with health parameters.

For the F404, NASA published GE-model-derived steady-state tables plus first-order transient constants. RM12 models exist in Swedish industry/academia but are proprietary.

Open tools are available but none is calibrated to a candidate engine:
- **Open source**: pyCycle and T-MATS.
- **US-only release**: MAPSS (generic military, documentation public).
- **Export-controlled**: NPSS.
- **Commercial**: GasTurb.
- **Legacy**: GSP.

### Cited Findings

#### Engine-specific published models

**F404-GE-400**
- **Manufacturer model, referenced only.** GE Dynamic Real Time Model (GE Report R88AEB427) [DIRECT, [TM-4240](https://ntrs.nasa.gov/citations/19910009766) p.2–3]:
  - component-level (fan, core, combustor, turbines, AB, nozzle);
  - about 6,250 lines of FORTRAN including installation effects;
  - 4 ms per 20 ms frame on a Gould SEL 97.
  - **Not public.**
- **GE in-flight thrust deck 83112** [DIRECT, [TP-3001](https://ntrs.nasa.gov/citations/19900015818) Fig. 3]:
  - Inputs: PT1, TT1, FVG, N1, N2, PS3, WFE, PT5.58, WFAB, A8, PS0, altitude, Mach.
  - Built from more than 1,500 Naval Air Propulsion Center altitude points.
  - The structure is public; the deck is not.
- **NASA simple dynamic engine model** [DIRECT, [TM-4240](https://ntrs.nasa.gov/citations/19910009766) Fig. 5; verified locally]:
  - Tables of FG, ram drag, NPR and A8 vs (M, altitude, PLA): 4 PLA breakpoints × 7 altitudes × 12 Mach numbers.
  - The PLA command goes through a rate limiter (increasing PLA only) and a first-order lag:
    - τ = 0.625 s non-AB, 0.550 s AB;
    - rate limits +19.03 °/s non-AB, +26.81 °/s AB.
  - Accuracy against the GE model at M0.2 and M0.7, 35 kft: within 3% steady state, within 20–25% in transients.
  - Figures 9–10 (PLA step history idle→MIL→max AB→min AB→idle) are digitisable.
  - The f18harv simulation uses the same τ but **14/22 °/s** rate limits [DIRECT, [TM-110216](https://ntrs.nasa.gov/citations/19960027892) §4.1]. Conflict; possibly a units difference.
- **GE compact real-time F404-GE-400 model** [DIRECT, [SAE 821401, French 1982](https://saemobilus.sae.org/papers/development-a-compact-real-time-turbofan-engine-dynamic-simulation-821401)]: a full-range nonlinear model run on an engine-mounted digital computer as a signal source in a failure-protection scheme. Abstract only.
- **Calibration-grade test data** [DIRECT; all digitisable]:
  - corrected airflow vs corrected fan speed, and dry thrust vs N1c ([TM-100159](https://ntrs.nasa.gov/citations/19870020104) Figs. 6–8);
  - AB thrust ratio vs augmentor FAR at PLA 94–130° (same, Fig. 8);
  - PS21/PT2 vs Wc table, and in-flight airflow at seven power settings ([CR-198052](https://ntrs.nasa.gov/citations/19970027377) Tbl 5, Tbl C1);
  - IRP and part-power NPR/T8/W8/A8/FG tables ([TM-4538](https://ntrs.nasa.gov/citations/19940010668) Tbls 2–4);
  - bleed-to-thrust sensitivities ([TM-104247](https://ntrs.nasa.gov/citations/19920020182) Tbl 2).
- **Other model leads.** DSTO, NRC Canada and thesis models of the F404 were **not searched** (search cap).
  - An NRC component-level F404 model is referenced as used for CF-18 test-cell fault isolation [DIRECT, AGARD-CP-448 paper 7].

**RM12**
- Volvo Aero/GKN's "RM12 multipurpose model" runs in Chalmers' GESTPAN code. It is proprietary [DIRECT, Höglund 2003 thesis, [urn:nbn:se:hv:diva-369](http://urn.kb.se/resolve?urn=urn:nbn:se:hv:diva-369)].
- RM12-model research:
  - H∞ multivariable control (Härefors 1997, *Control Engineering Practice*);
  - thrust and health Kalman filters (Henriksson & Grönstedt 2005/2011, [Chalmers 139944](https://research.chalmers.se/en/publication/139944));
  - gas-path analysis on **two real RM12 test-bed data sets**, one heavily degraded after accelerated mission testing and one low-hours development engine ([Grönstedt & Wallin GT2004-53591](https://research.chalmers.se/en/publication/10173));
  - fault-injection simulation: clogged fuel nozzle, OGV hole, sensor faults ([Viborg 2004, LiU](http://urn.kb.se/resolve?urn=urn:nbn:se:liu:diva-2178)).
  - All are paywalled or abstract-only; no maps or code were released [DIRECT].

**F100**
- **TM X-3261** (-100(1)) [DIRECT, [TM X-3261](https://ntrs.nasa.gov/citations/19750019996)]:
  - Complete real-time model patterned on P&W deck CCD 1015: all equations, including volume dynamics (eqs B53–B65); rotor inertias; gas volumes; loss coefficients; fuel LHV 44.07 MJ/kg; a 0.05 s T3 lag; and a FORTRAN listing.
  - **Normalised maps** for fan tip/hub, HPC (with an RCVV effect), HPT/LPT flow and enthalpy drop, AB efficiency, duct loss and nozzle (Figs. 16–23).
  - Validation: errors of about 4% of design fan speed (AB, altitude) and about 3% in fan airflow/FPR at high altitude, against the P&W deck; idle→MIL and MIL→MAX transients in Figs. 13–15.
- **TP-1034** re-matches the model to -100(3) (deck CCD 1103-1.0). It adds vane off-schedule functions, Reynolds effects and fan/HPC surge-margin equations [DIRECT, [TP-1034](https://ntrs.nasa.gov/citations/19770024210)].
- **Linear models**: a 16-state, 5-input, 7-output system with matrices and eigenvalues at several points [DIRECT, [TP-1261](https://ntrs.nasa.gov/citations/19780022953)]. MVCS 5×5×5 models are in [TP-1056](https://ntrs.nasa.gov/citations/19770026225) and [TP-2231](https://ntrs.nasa.gov/citations/19840003103).
- **Onboard models for PW1128 (EMD, the -229 precursor)** [TRANSFER: PW1128 → -220/-229, same DEEC family; [TM-4426](https://ntrs.nasa.gov/citations/19930003967); [PSC workshop](https://ntrs.nasa.gov/citations/19950026592)]:
  - Kalman-filter state-variable model: x = [N1, N2, TMT]; u = [WF, AJ, CIVV, RCVV, HPX, BLD]; y = [PT6, PT4, FTIT, N1, N2].
  - 49 matrix sets scheduled on PT4 (23–260 psi).
  - Five component-deviation (health) parameters: DELPT, DEHPT, AAHT, DWHPC, DWFNA.
  - Accuracy goal ±2%; in-flight net propulsive force within 3%.
- **Parallel-compressor distortion model** (P&W, F100(3), blade-row level) predicted stall at 180° distortion amplitude 0.45 vs 0.43 seen on the engine [DIRECT, [CR-135388](https://ntrs.nasa.gov/citations/19780014153)].
- **NLR TERTS F100-PW-220 real-time model** [DIRECT, [NLR-TP-2002-069](https://reports.nlr.nl/handle/10921/666); read locally, `open_models/NLR-TP-2002-069_TERTS.pdf`]:
  - Engine as modelled: ≈110 kN max thrust, OPR 25.
  - Model structure: 8 states / 8 errors; DEEC, nozzle-control and AB-fuel-control sub-models.
  - Validated against manufacturer installed-performance data (N1, N2, thrust, fuel flow across the envelope) within 5%. A large deviation appears beyond M1.2 at 0 ft because special control laws are omitted.
  - Figures: MIL fuel flow vs Mach at 0/20/40 kft (Fig. 4); MIL→MAX-AB slam thrust ≈55→105 kN over ≈5 s with AB-segment light-up peaks (Fig. 8); idle→MAX-AB N1/N2 (Fig. 9).
  - Rates: ≥60 Hz is needed for AB control; it ran at 100 Hz.
  - The model is **not released**; the figures are digitisable.
- **NLR GSP model of the F100-PW-220** used for HPT-blade lifing from RNLAF F-16 flight data, at a 0.05 s integration step [DIRECT, [NLR-TP-2001-402](https://reports.nlr.nl/bitstreams/9eb019de-dcbb-40c3-b826-5c54b9eabc7b/download); read locally]. Not released.

**F110**
- The GE cycle deck R89AEB216 ("Cycle Deck User's Manual for F110-GE-129 Performance") is referenced and validated by NASA against flight data, but **not public** [DIRECT, [TM-104326](https://ntrs.nasa.gov/citations/19970003552) p.12, Figs. 8–10].
- An F110-type real-time simulation translated from a GE FORTRAN deck [DIRECT, [TM-102409](https://ntrs.nasa.gov/citations/19900003302)]:
  - "backbone" maps (Converse & Griffin, NASA CR-174645);
  - 10 ms step;
  - rotor speeds within 2% steady-state and 4% transient of the deck.
  - No numeric maps.

**AL-31F**
- A scanned Russian altitude-speed characteristic (thrust and SFC vs Mach at max/full AB, H = 0–20 km) is saved as `al31_m53_m88_kaveri/AL31F_altitude_speed_characteristics_leteckemotory.gif` [DIRECT-AGG, [leteckemotory](http://www.leteckemotory.cz/motory/al-31)]. It is the best digitisable validation target for this engine.
- An AL-31F IR emission model with nozzle temperature field [DIRECT, [Vestnik SSAU 2014](https://doi.org/10.18287/1998-6629-2014-0-4(46)-99-106)].
- A USATU/"Molniya" HIL model of an unnamed twin-spool AB turbofan with FADEC reconfiguration ([Vestnik SSAU 2009](https://doi.org/10.18287/2541-7533-2009-0-3-2(19)-392-400)). That the engine is the AL-31F is an [ASSUMPTION] from the Ufa authorship.
- Chinese "某型涡扇" literature was not searched (cap).

**Indian engines**
- Indian test-bed-calibrated modelling exists but is anonymised:
  - **Rath (HAL Koraput Engine Division / IIT Kanpur), Mishra (RCMA-Engines, CEMILAC) and Kushari (IIT Kanpur)** built a GasTurb model of a "twin-spool mixed-flow low-bypass turbofan" validated on extensive test-bench baselines, and used it to assess degradation over service hours [DIRECT, [IJTJE 41(2):407–419, 2024, doi:10.1515/tjj-2023-0064](https://doi.org/10.1515/tjj-2023-0064); affiliations from the Crossref record]. The paper does not name the engine.
  - [ASSUMPTION] Because HAL Koraput builds and overhauls the AL-31FP (and has overhauled the RD-33), this is very likely AL-31FP or RD-33 data. Validate by reading the full text, which is paywalled.
- **Kaveri**: no Kaveri performance, transient or real-time model was found in a full OAI harvest of the Defence Science Journal (4,009 records). The 1985 GTX flat-rating paper (Prasad & Sundararajan, DSJ 35(2)) documents the control-law lineage with digitisable figures [TRANSFER: Kaveri ancestor; local copy `al31_m53_m88_kaveri/DSJ_1985_Prasad_FlatRating_GTX.pdf`].

#### Open / generic tools (what an Indian student team can actually use)
- **pyCycle** (OpenMDAO, Apache-2.0) `mixedflow_turbofan.py` [DIRECT tool facts, [GitHub](https://github.com/OpenMDAO/pyCycle/blob/master/example_cycles/mixedflow_turbofan.py)]:
  - Elements: inlet → fan → splitter → LPC → HPC (bleeds) → burner → HPT → LPT → mixer → afterburner → CD nozzle.
  - Design point: 35 kft / M0.8, 5,500 lbf; fan PR 3.3, LPC PR 1.935, HPC PR 4.9 (OPR ≈31.3); BPR 1.05; T4 3,200 °R; AB 3,400 °R.
  - Maps: generic AXI5, LPCMap, HPCMap, HPTMap, LPTMap.
  - Steady-state only; not calibrated to any fighter engine.
- **T-MATS** (NASA, Apache-2.0, Simulink) [DIRECT, [GitHub nasa/T-MATS](https://github.com/nasa/T-MATS)]:
  - Examples: JT9D, AGTF30, generic gas turbine (SS and dynamic), linearisation, volumes.
  - **No military/AB example**, but it provides Mixer, variable-geometry compressor, nozzle and sensor/actuator blocks (repository tree checked via the GitHub API).
- **MAPSS** (NASA GRC) [DIRECT, [NASA/TM-2004-212968](https://ntrs.nasa.gov/citations/20040035577); read locally]:
  - Engine: a generic "high-pressure ratio, dual-spool, low-bypass, military-type, variable cycle turbofan with digital controller".
  - Rates: CLM at 2,500 Hz, controller at 50 Hz.
  - States: XNL, XNH, TMPC.
  - Five control modes (high/medium/low power, fan-stall-margin, overspeed), blended by PLA.
  - 158 outputs, including a sensor set (xn2c, xn25c, ps21c, p27dc, t27dc, p27c, t27c, t3c, ps15c, p16c, ps3c, t5bc, t56c, ps56c, p58c).
  - **10 health parameters** (flow and efficiency scalars for fan, booster tip/hub, HPT, LPT) and per-sensor and per-actuator bias constants.
  - Release type is **"U.S. Release Only"** [DIRECT, [NASA software catalog LEW-17674-1](https://software.nasa.gov/software/LEW-17674-1)]. The documentation is a usable template; the code is likely inaccessible to an Indian team.
  - C-MAPSS is restricted similarly ([LEW-18315-1](https://software.nasa.gov/software/LEW-18315-1)).
- **NPSS**: sold by SwRI under export-control terms ([SwRI registration](https://www2.swri.org/www2/npss/register-cl.asp)). Sales are restricted by country (AGG, [Wikipedia NPSS](https://en.wikipedia.org/wiki/Numerical_Propulsion_System_Simulation)).
- **GasTurb 15**: commercial, free trial ([gasturb.com](https://www.gasturb.com/)). It is the tool used by the Indian HAL/IIT Kanpur degradation study above.
- **GSP**: "no longer supported by NLR"; limited support from TU Delft ([gspteam.com](https://gspteam.com/)).
- **Grönstedt & Rosell 2022** (Chalmers/Saab, *Fluids* 7(1):21) [DIRECT tool facts, [Chalmers 528520](https://research.chalmers.se/publication/528520)]:
  - Generic low-BPR mixed-flow fighter engine in GESTPAN: FPR 5.4, HPC PR 5.8, 90 kg/s, BPR 0.45, TIT 1,950 K, controller limits OPR 32 and T4 2,260 K.
  - Table 2 lists 10 fighter mission points (thrust/altitude/Mach) usable as thrust-demand test cases.
  - Not calibrated to any candidate engine.

### Inferences
- [ASSUMPTION] Recommended modelling route for an F404-IN20 virtual engine:
  1. Use pyCycle (steady-state design and off-design) or a T-MATS Simulink build (transient) with generic maps scaled to the F404 operating line (TM-100159 and CR-198052).
  2. Adopt the TM X-3261 F100 *structure* for dynamics: rotor inertias scaled by mass-flow and diameter, volume dynamics, and a heat-soak state (TMPC as in MAPSS).
  3. Validate against TM-4240 step responses, TM-4538 IRP tables and the SHK RM12 transient.
  4. This is a [TRANSFER: F100 → F404] of method, not of numbers.
- [ASSUMPTION] Expected absolute accuracy without OEM maps is ±3–5% steady state. That matches the TERTS (5%) and TM-4240 (3%) experience, and is adequate for realistic telemetry texture but not for certification-grade thrust.
- [TRANSFER: MAPSS → any candidate] The MAPSS health-parameter set (flow and efficiency scalars per component) plus sensor and actuator bias constants is a ready-made, publicly documented schema for injecting degradation into a synthetic engine.

### Gaps
- No public dimensional maps for any candidate engine. NASA withholds F100 design scalars (maps are normalised).
- F404/F414/IN20/F110 theses (NPS, AFIT, Cranfield, DSTO, NRC) were not searched because of the search cap.
- The Swedish RM12 theses on DiVA could not be retrieved (site unreachable).
- Chinese AL-31F gas-path and performance papers were not searched.
- The Kaveri real-time model and KADECU hardware-in-the-loop papers were not found.
- NATO RTO-TR-044 ("Performance Prediction and Simulation of Gas Turbine Engine Operation", 2002) could not be downloaded (STO server returned Cloudflare 524). It is a candidate source of military test cases.

---

## 3. Engine control documentation (sensed/scheduled parameters, modes, limiters, transients, start)

### Takeaway
The **F100 DEEC** (production on the -220 from 1986) is by far the best-documented fighter engine control in the public domain. NASA CP-2298 gives:
- sensors, outputs and control loops;
- open-loop schedules (as functions of what variables);
- limiters, stall detection/recovery and fault-detection-and-accommodation tables;
- flight transient time histories.

The **F404-GE-400** (hydromechanical main fuel control + analog ECU) is documented qualitatively: modes, limit loops, variable-geometry roles, sensor ranges, AB light-off sequence and actuator slew rates.

FADEC-era engines (IN20, -102, F414, RM12, M88, Kaveri, F110-GE-129) are documented only as "FADEC with backup". Their schedules, limits and transient times are not public.

### Cited Findings

#### F404-GE-400 (and by transfer the RM12 / IN20 control architecture)

**Architecture** [DIRECT; [TP-3001](https://ntrs.nasa.gov/citations/19900015818) p.3; [TM-104247](https://ntrs.nasa.gov/citations/19920020182) p.3; [CR-1998-208416](https://ntrs.nasa.gov/citations/19980219005) §7; Forsyth 1989 App. A.1.1, [archive.org DTIC ADA219105](https://archive.org/details/DTIC_ADA219105)]
- Throttle mechanically linked to a hydromechanical main fuel control (MEC).
- Engine-mounted, fuel-cooled, alternator-powered electrical control unit/assembly (ECU/ECA) made by Lockheed Martin Fort Wayne.
- AB fuel control and a variable exhaust nozzle power unit.
- The ECU performs isochronous N1 limiting above intermediate, turbine temperature control, AB fuel scheduling and fan variable geometry (FVG) and nozzle scheduling, plus overspeed and stuck-nozzle monitoring. The MEC handles compressor variable geometry (CVG).
- Three ECU trim potentiometers [DIRECT, Glenny ARL-PROP-TM-455, [archive.org DTIC ADA210374](https://archive.org/details/DTIC_ADA210374)]:
  - N1 ±300 rpm (≈10 rpm/click);
  - T5 +15 °F (≈2.5 °F/click);
  - AB ratio units ±65.

**Control modes**
- Below IRP: the MEC schedules N2 from throttle and a temperature input (T2.5 per TM-104247; T1 per TP-3001; conflict). A8 is scheduled from PLA, and NL "floats".
- At or above IRP: the ECU schedules max N1 = f(T1) and modulates A8 to hold T5/T56 on its limit schedule, which is a function of T1 and ambient pressure [DIRECT, TM-104247 p.3; CR-1998-208416 §7.2.3].
- NH is not directly limited; it is limited aerodynamically by T5, NL and PS3 [DIRECT, CR-1998-208416 §7.2.5].
- "N2 lockup" at M1.2 / 30 kft [DIRECT, [TM-100159](https://ntrs.nasa.gov/citations/19870020104) p.7].

**Variable geometry**
- FVG is closed-loop on T1-corrected NL and has the highest bandwidth in the control.
- FVG stroke is 2.7 in, with maximum slew of about 2.16 in/s at sea level [DIRECT, CR-1998-208416 §7.2.2, §7.6.1].
- CIGV is scheduled vs compressor corrected speed [DIRECT, [TM-1999-206572](https://ntrs.nasa.gov/citations/19990024943) §2.2].

**AB light-off sequence** [DIRECT, TP-3001 p.3; TM-88273 p.4]
1. Ignitors on.
2. Nozzle opens slightly above its IRT position.
3. The T56 schedule is temporarily reset lower.
4. Pilot plus minimum main AB fuel is delivered.
5. The UV flame sensor confirms light-off.
6. The hold is released and main AB fuel goes to the throttle-selected level.

AB hardware: 6 pilot and 24 main spraybars.

**Sensors** [DIRECT, [CR-191195](https://ntrs.nasa.gov/citations/19940032893) §3.1; TP-3001 Tbl 2]

| Sensor | Type | Range |
|---|---|---|
| T1 | RTD | −65 to 300 °F |
| T2.5 | thermocouple | −65 to 535 °F |
| T5 | 2 harnesses × 4 probes; total system error ±18 °F | 700–1,600 °F |
| FVG | LVDT | 0–2.7 in |
| CVG | rotary | −3.5 to 52.5° |
| VEN (nozzle) | LVDT | 6.923 in |
| NL | 2 magnetic pickups | 2,787–10,683 Hz |
| NH | alternator | 195–4,425 Hz |
| PS3 | — | 0–500 psi |
| WFE (main fuel flow) | — | 0–12,000 lb/h |
| WFAB (AB fuel flow) | — | 0–30,000 lb/h |
| AB flame | UV | on/off |

- **Digitisable**: a test-cell throttle sweep over ≈80 s (CR-191195 Fig. 33):
  - FVG ≈2.5 → 0 in;
  - CVG ≈48° → 3–12°;
  - T5 ≈770 → 1,500 °F.

**Transients** [DIRECT-derived from TM-4240 parameters]
- Slam idle (31°) → MIL (87°) at 19.03 °/s takes ≈2.9 s. MIL → max AB (130°) at 26.81 °/s takes ≈1.6 s. With τ ≈0.55–0.63 s, idle → max AB is ≈4.5–5 s.
- This is consistent with the commonly quoted "≈4 s idle→max" (AGG; primary not located).
- Using TM-110216's 14/22 °/s gives ≈6 s.
- Deceleration is faster than acceleration, and min AB → max AB is faster than idle → MIL ([TM-4240](https://ntrs.nasa.gov/citations/19910009766) p.3).

**Start** [DIRECT, CR-1998-208416 §7.2.5; [TM-101702](https://ntrs.nasa.gov/citations/19900013006) p.5]
- Ignition is permitted at NH 10–45%.
- NASA's hung-start monitoring rule (not a GE limit): N2 <60% and not increasing for 1 s, or <60% for 35 s.
- **Not found publicly:** start time, light-off N2, start T5 limit.

**FADEC-era descendants**
- **F404-GE-IN20**: "advanced FADEC" with "redundant features" for single-engine use [DIRECT, [GE 2004](https://www.geaerospace.com/news/press-releases/defense-engines/ge-awarded-105-million-development-contract-india)]. Tejas also has a jet fuel starter for ground start and in-flight relight [DIRECT, [ADA PS integration facilities](https://www.ada.gov.in/images/PS%20Integration%20facilities.htm)].
- **F404-GE-102**: FADEC "derived from GE's F414" [DIRECT, GE 2014 sheet]. GE's 2020 sheet attributes this to the -103 instead (conflict).
- **RM12** [DIRECT, [SHK RM 2019:02](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf) pp.16, 41–43]:
  - FADEC plus a mechanical throttle cable for emergency control ("nödreglering").
  - The FADEC controls fuel flow, FVG, CVG and A8.
  - Flameout detection: low T5 plus decaying NH triggers auto-ignition; the fault code clears when T5 recovers.
  - Windmill relight needs more than 350 kt; an APU-assisted restart takes 45–85 s.
  - Bird-ingestion spec: recover 90% of max dry thrust within 4.7 s after a 0.5 kg bird at 178 kt (35% at 330 kt).
  - Original design requirement: redundant control/ignition with "two failsafe backup modes" [DIRECT, [ASME 88-GT-305](https://asmedigitalcollection.asme.org/GT/proceedings/GT1988/79191/V002T02A020/236864), first page].

#### F100 (-100/-200 UFC + EEC; -220 DEEC; -229 IDEEC)

**-100/-200**
- The hydromechanical Unified Fuel Control meters main fuel as f(PLA, N2, T13 (P13 per TP-1261), PS3), positions RCVV, meters AB fuel to 5 zones, and sets nozzle area [DIRECT, [TP-1034](https://ntrs.nasa.gov/citations/19770024210) p.2].
- The supervisory EEC positions CIVV = f(corrected fan speed) and trims fuel and nozzle [DIRECT, [TP-1228](https://ntrs.nasa.gov/citations/19780015152) p.2].

**DEEC** [DIRECT, [CP-2298](https://ntrs.nasa.gov/citations/19860015871) Paper 3 ([19860015874](https://ntrs.nasa.gov/citations/19860015874)) pp.33–55; Paper 7 ([19860015878](https://ntrs.nasa.gov/citations/19860015878))]
- **Inputs**: dual TT2, FTIT, N1 and N2; single PS2, PB and PT6M; PLA; 11 resolvers; UV light-off detector; Mach word.
- **Outputs**: 7 servos (CIVV, RCVV, WFGG, WFAC, WFAD, SVP, AJ); 3 solenoids; 9,600-baud UART.
- **Computer**: 3.4 MHz, 14K words, 79 schedules, 500 constants, 150 detectable faults.
- **Fuel loop**: WFGG holds N1C2 (PI control) within N2, FTIT and PB limits.
- **Nozzle loop**: AJ holds EPR = PT6M/PT2 = f(N1C2) at IRP/AB. Above M1.4 the nozzle holds N1C2 while fuel sits on the FTIT limit.
- **Open-loop schedules**: CIVV = f(N1C2); RCVV = f(N2C25, TT2); start bleeds = f(N2, TT2).
- **Stall detection**: rate of PB decay (STLSIG = f(PLA, PB)), with recovery by fuel cut and nozzle opening. AB blowout detection is also included.
- **Fault detection and accommodation**: three levels (normal / AB inhibit / transfer to the hydromechanical backup control BUC), with a sensor-by-sensor action table (Paper 7 Tbl 1).
- **Degradation masking**: as the engine deteriorates, FTIT rises to hold scheduled EPR until the FTIT limit, after which thrust falls (Paper 3 p.50). This is a key synthetic-degradation signature.

**Transient specification** [DIRECT, -100(3), [TP-1056](https://ntrs.nasa.gov/citations/19770026225) Tbl I and p.8]
- Sea-level static, no bleed. Times to 90% of thrust change:

| Throttle change | Time to 90% | Time to 98% |
|---|---|---|
| Idle → IRP | 4.0 s | 15 s |
| 30% → IRP | 3.5 s | — |
| IRP → idle | 3.0 s | — |
| Idle → max AB | 8.0 s | — |

- ±13.34 kN steps from 25–45% thrust must reach 90% within 1.2 s. Times may be up to 125% of these with maximum bleed and power extraction.
- The table is partly garbled in the text layer; the values were read by a sub-agent and partly confirmed locally.

**Flight transients and starts**
- DEEC MIL → MAX in flight completed in ≈4 s, with segment-1 quickfill ending ≈0.4 s after the snap [DIRECT, CP-2298 Paper 11].
- Airstarts: spooldown 50–70 s at 250 kt; JFS-assisted ≈40–65 s; start bleeds closed at 56–61% N2 depending on software version [DIRECT, [TM-85900](https://ntrs.nasa.gov/citations/19840021810) Tbl 1].
- **-229**: full-authority IDEEC plus a hydromechanical "get-home" control [DIRECT, [TM-1998-206560](https://ntrs.nasa.gov/citations/19980228163) p.3]. No further logic found.

#### F110
- **F110-GE-100** [DIRECT, AGARD-CP-448 papers 11 and 21, [archive.org DTIC ADA203800](https://archive.org/details/DTIC_ADA203800); read locally]:
  - Hydromechanical MEC plus an electronic "full authority" Augmentor-Fan-Temperature Control (AFTC). The AFTC acts through torque motors: main fuel (MTM), fan IGV (IGVTM), A8 (A8TM) and augmentor fuel (WFRTM).
  - Sensors: T2, T2.5, PS3, T4B by HPT-blade pyrometer, NF, NG, IGV, A8, fan duct pressure ratio, lube quantity and temperature.
  - The AFTC exposes ≈23 analog inputs plus 5 discretes; the aircraft supplies 6 more.
  - Secondary-mode fault codes exist (e.g., "C/STALL*SEC FLT").
- **F110-GE-129**: "single channel Digital Engine Control (DEC) with a hydro-mechanical backup", designed to MIL-STD-1783 damage tolerance [DIRECT, RTO-TR-028 §5.3.3, local copy `research_sources/flight_profiles/RTO-TR-028.pdf`]. Idle is PLA 20° and IRT PLA 85° [DIRECT, [TM-104326](https://ntrs.nasa.gov/citations/19970003552)].
- No schedules, transient or start times found for either variant.

#### AL-31F/FP, M53-P2, M88-2, Kaveri
- **AL-31F** [DIRECT, [airwar](http://www.airwar.ru/enc/engines/al31f.html); [Aviapanorama 1997](https://www.aviapanorama.narod.ru/journal/1997_2/heart.htm)]:
  - Hydro-electronic control: КРД-99 analogue electronic regulator-limiter, НР-31 hydromechanical pump-regulator, РСФ-31 nozzle/AB regulator.
  - On electronic failure, control reverts to the hydromechanical system.
  - Functions: surge elimination, auto-relight, "counter-start" of main and AB combustors.
  - AL-31FP TVC nozzles are driven by the engine's own fuel automatics and commanded by the flight control system.
  - Transients (AGG, [leteckemotory](http://www.leteckemotory.cz/motory/al-31)):

| Event | Time |
|---|---|
| Idle → max, sea level static | 3–5 s |
| Idle → max, below 8 km | ≤5 s |
| Idle → max, above 8 km | ≤8 s |
| Idle → full AB | ≤7 s |
| Max → idle | 4–6 s |
| Ground start to idle | ≤50 s |

- **M53-P2** [DIRECT-secondary, [fr-wiki M53](https://fr.wikipedia.org/wiki/Snecma_M53), probably from Armée de l'air course material]:
  - Digital computer with an autonomous hydromechanical backup.
  - Sub-systems: speed N via fuel; nozzle area with a Tt7 limit at full throttle; variable bypass-section valve (frozen above 16° AoA); AB regulation; nozzle pre-opening before AB light; missile-fire ("tir") enrichment cut.
  - [DIRECT, AGARD-CP-448 paper 19] An engine "calculateur de régulation" with a redundancy lamp.
- **M88-2**: dual-channel FADEC [DIRECT, Snecma sheet]. The T-REX version gets new digital control [DIRECT, Safran 17 Jun 2025, per sub-agent].
- **Kaveri**:
  - KADECU FADEC by DARE (AGG).
  - FADEC "designed, developed and qualified indigenously" [DIRECT, [PIB relid 123940](https://pib.gov.in/newsite/PrintRelease.aspx?relid=123940); URL built from the release ID].
  - The KDE has an indigenous Engine Fuel Control System and an "autonomous engine control system" [DIRECT, MoD Annual Report 2022-23 p.121, local copy `al31_m53_m88_kaveri/MoD_AR_2022-23.pdf`].
  - No schedules published.

### Inferences
- [TRANSFER: F404-GE-400 → RM12 → IN20] RM12 crash-recorder channel names (NLPC, NHPC, FVG, CVG, A8, PS3C, T5) and FADEC-controlled variables (fuel, FVG, CVG, A8) match the F404-400 control architecture. A virtual IN20 FADEC can therefore reuse the F404 control *structure*:
  - N2 schedule below IRP;
  - N1 limit = f(T1) and a T5 limit via A8 at/above IRP;
  - FVG = f(N1c), CVG = f(N2c);
  - the published AB light-off sequence.
  - Limits: FADEC gains, limit values and any IN20-specific logic (single-engine protection, auto-relight thresholds) are unknown. Validate with HAL/ADA or IAF technical publications if obtainable through the PS owner.
- [TRANSFER: F100 DEEC → any FADEC engine] DEEC fault-accommodation levels, stall-detection logic and the "FTIT rises to hold EPR" degradation-masking behaviour are generic modern-FADEC behaviours. They can be used to give the virtual engine realistic fault codes and degraded-mode behaviour.

### Gaps
- Numeric control schedules, limit values and gains: not public for any candidate.
- FADEC fault-code dictionaries for IN20, F414, RM12, M88 and Kaveri: not found.
- Start sequences and ground start times for F404/IN20/F414/F110: not found. AL-31F "≤50 s to idle" is AGG.
- The F404-GE-402 control changes vs the -400: not found.

---

## 4. Engine monitoring systems (on-board EHM, life usage, ground systems)

### Takeaway
Public monitoring documentation is **deepest for 1980s-era US systems**, mainly through AGARD-CP-448 (1988):
- **F/A-18 F404 IECMS**: architecture, 10 Hz/1 Hz parameter list, event buffers, MSDC quantisation, 2σ precision, 8 life-usage indices, ground flow in USN/CF/RAAF use.
- **F100-PW-220 EMS/EDU**: 4 Hz DEEC data, 21 event types, ground units, field statistics.
- **F110-GE-100 EMS**: parameter list, 2 scans/s buffers, fault codes, T4B time-at-temperature, TAC counters, ground software to MEETS.

RM12 has a public recorder architecture plus a well-described fleet Life Tracking System. M53 has a public life-usage computer concept. M88 has an ECMS described only second-hand. The AL-31FP, IN20, F414 (partly), F110-GE-129, F100-PW-229 and Kaveri monitoring systems are essentially undocumented in public.

### Cited Findings

#### F/A-18A–D IECMS (F404-GE-400/402)
Sources (all locally verified in `f404_monitoring/DTIC_ADA203800.txt`):
- AGARD-CP-448, [archive.org DTIC ADA203800](https://archive.org/details/DTIC_ADA203800), papers 2 (Hess, NAVAIR), 4 (Schofield et al., Canada), 7 (Muir, Rudnitski & Cue, Canada) and 37 (Henry).
- Paré & Muir 1998, [archive.org DTIC ADA347270](https://archive.org/details/DTIC_ADA347270).

**Architecture** [DIRECT, Hess pp.2-4 to 2-6]
- 13 engine sensors, of which 5 are IECMS-only. Analog or frequency signals, one wire each.
- Airframe parameters: Mach, altitude, freestream TT, AoA, Nz, fuel pressure and temperature.
- Bendix Maintenance Signal Data Converter (MSDC), shared with 7 other systems.
- Maintenance Signal Data Recorder writing to a Tape Magazine Unit (≈7 flights; also airframe fatigue and crash data).
- Maintenance Monitor Panel with 3-digit codes: 44 engine codes and 231 for other systems.
- All logic in the Mission Computer: 5,400 16-bit words, 2–4% of capacity.
- Cockpit: 5 parameters always shown, 8 more on the DDI, plus a pilot record button.

**Recorded parameters and rates (CF-18)** [DIRECT, Muir et al. Tbl 1, p.7-7]

| Rate | Parameters |
|---|---|
| 10 Hz | PALT, Mach, AoA, T0, T1, N1, N2, T56, P56, PS3, Wfm, PLA, A8 |
| 1 Hz | Nz, oil pressure, vibration, fuel temperature, anti-ice valve, bleed door |

**Event records** [DIRECT]
- 5 s pre-event (rolling buffer frozen at trigger) + 25 s post-event (Hess; also MIL-E-5007E as quoted by Hess p.2-2).
- 5 s + 35 s in Canadian practice (Muir p.7-1; Paré & Muir p.2). Conflict.
- Take-off record runs from take-off power to lift-off, ≈6–10 s.
- Triggers:
  - exceedances on N1, N2, EGT, oil pressure and vibration;
  - sensor-range failures;
  - flameout (PS3 and rotor-speed logic);
  - take-off thrust check;
  - pilot button.
- Navy lesson learned: an exceedance should persist several iterations before being declared.

**Quantisation and noise (directly usable for synthetic texture)** [DIRECT, Henry Tbl 1, p.37-4; 2σ aircraft precision / MSDC resolution]

| Channel | Aircraft 2σ precision | MSDC resolution |
|---|---|---|
| T1 | 1.3 K | 1.0 K |
| XN1 | 154 rpm | 16 rpm |
| XN2 | 139 rpm | 16 rpm (OCR-probable) |
| PS3 | 1.2 psia | 0.5 psia |
| P5 | 0.14 psia | 0.06 psia |
| T5 | 2.0 K | 1.0 K |

- The MSDC, not the sensors, dominated the error.
- Transient take-off data repeat within ±1% for throttle rates ≥45°/s, within the nozzle-closed window (≈1 s to close, ≈4 s closed).

**Life usage: eight GE-defined Life Usage Indices (LUIs)** [DIRECT, Hess pp.2-5 to 2-6; locally verified]
1. Full N2 cycle ("Type I", off → intermediate → idle).
2. Partial N2 cycle ("Type III", idle → intermediate → idle).
3. Equivalent Full Thermal Cycles (HPT blade thermal cycles weighted by magnitude).
4. Stress Rupture Counts (rate increases with HPT blade metal temperature).
5. Time at Max Power (at or above intermediate).
6. Full PS3 cycle (near maximum allowed PS3; high speed, low altitude).
7. Partial PS3 cycle (PS3 ≥85% of maximum allowable).
8. Engine operating time (≥ ground idle).

LUI sums are written to tape twice per flight (Paré & Muir).

- The EFTC limit for René 125 HPT blades is ≈1,000 h of average operation.
- In real usage, time at maximum temperature and AB light-ups both ran ≈60% above the design life analysis [DIRECT, ARL 1985, [archive.org DTIC ADA164562](https://archive.org/details/DTIC_ADA164562) pp.3–4].
- A noisy N2 signal made one engine accumulate partial-N2 counts up to 8× faster than its twin (Muir p.7-3). This is a realistic sensor-artefact failure mode for a synthetic dataset.
- [DIRECT] TAC is **not** used for the F404. Its life accounting is LUI-based.

**Later F/A-18C (F404-GE-402) bus words** [DIRECT, NAWCADPAX/RTR-2001/1 Tbl E-3, [archive.org DTIC ADA407860](https://archive.org/details/DTIC_ADA407860)]
- From the Signal Data Computer (SDC) to the MC over 1553: EGT (°C), CDP, turbine discharge pressure, NL/NH (rpm), T1, oil pressure (psid), nozzle position (%), main fuel flow (pph), fuel inlet temperature, T5, plus discretes.
- The test data system sampled these at 20 sps; that is not necessarily the native bus rate.

**Ground systems**
- **US Navy** [DIRECT; Hess pp.2-6 to 2-7; King & Tooker NPS 1993, [archive.org DTIC ADA277918](https://archive.org/details/DTIC_ADA277918); Schoch NPS 2003, [archive.org DTIC ADA418270](https://archive.org/details/DTIC_ADA418270); Hagan & Slack NPS 2006, [archive.org DTIC ADA462668](https://archive.org/details/DTIC_ADA462668)]:
  - ECAMS ground station (only "marginally functional") → Parts Life Tracking System → later NALDA AEMS DSS, SAME server, NALCOMIS, DECKPLATE.
  - At NAS Lemoore I-level, reconciling the engine logbook against AEMS/SAME averaged **14 days** before work could start. This is direct evidence of the "fragmented records" problem in the problem statement.
- **Canada (CF-18 ECMS)** [DIRECT, Paré & Muir 1998]:
  - Portable ground stations → base ECMS → central ECMS at Orenda (nightly) → NDHQ.
  - Tracks 26 life-limited and 54 logistically critical parts per engine.
  - Flight Line Troubleshooting System covers more than 45 failure modes and isolates the LRU in 60–70% of cases.
  - Measured results: 50% fewer false engine removals; payback ≈8 months.
- **RAAF**: MD&SLMS / CAMM / Unit Computing Facility [DIRECT, ARL 1985; IFDIS 1987, [archive.org DTIC ADA227757](https://archive.org/details/DTIC_ADA227757)].

#### F/A-18E/F F414 advanced IECMS
- Hall et al., IEEE Aerospace 2001, [doi:10.1109/AERO.2001.931325](https://ieeexplore.ieee.org/document/931325), abstract only. Improvements summarised by Hood, Khan & Story (NPS 2013), [archive.org DTIC ADA585693](https://archive.org/details/DTIC_ADA585693) pp.17–18 [DIRECT]:
  - FADEC-based fault detection and isolation;
  - expanded memory-unit recording;
  - engine-mounted master chip detector;
  - in Navy technical evaluation: 100% detection, 0% false alarms.
- Life usage via "nine matrices with 214 elements", downloaded every flight to the SAME server (72N report) [DIRECT, Hersey et al. NPS 2008, [archive.org DTIC ADA493918](https://archive.org/details/DTIC_ADA493918) pp.14–15].
- Module limits in 2008: fan, HPC, combustor and LPT 4,000 h EOT; HPT 1,850 h (LUI); AB 3,431 h.
- Forecasting conversion of ≈1.2 ELCF per EOT hour (Schoch 2003 App. C).

#### F100-PW-220 EMS / EDU (also covers the -229 lineage) [DIRECT, AGARD-CP-448 paper 18 (Pratt & Whitney), pp.18-1 to 18-4, [archive.org DTIC ADA203800](https://archive.org/details/DTIC_ADA203800); read locally]
- **Five subsystems**:
  - DEEC and a dedicated engine-mounted Engine Diagnostic Unit (EDU);
  - flight-line Data Collection Unit (DCU; 30 s battery-powered download; one DCU serves a squadron);
  - Engine Analyzer Unit (EAU; test and reprogramming of DEEC/EDU limits);
  - Ground Station Unit (GSU), the link to base logistics.
- **Data path**: the DEEC sends ≈300 items every 250 ms (4 Hz) to the EDU over a 9,600-bps serial bus, with 8-bit fault codes per failure. The EDU computes on a 250 ms cycle. High-speed events are detected by the DEEC and recorded later by the EDU.
- **21 recorded engine events**:
  - temperature and speed: turbine overtemperature, low- and high-rotor overspeed;
  - operability: augmentor anomaly, stall detect, stagnation detect, dieout detect, compressor vane flutter, low thrust, inhibited augmentor;
  - starting: hot ground start, hot air start, no start, start bleed failure;
  - control: control auto-transfer, slow turbine temperature probe;
  - oil: low and high oil pressure;
  - anti-icing: overtemperature, failed open, failed closed.
  - For example, an overtemperature event records its duration and peak temperature.
- **Field results** (to Aug 1987; 19,043 EFH; 9,502 sorties): effectiveness 99.3%, confirmation rate 92.7%. EMS engines needed ≈33% fewer maintenance man-hours per flight hour and were flight-ready ≈5× more often than the rest of the F100 fleet.
- **Lineage** (same paper):
  - F100 Engine Diagnostic System, 2,500+ h on F-15 F100-PW-100;
  - initial production Events History Recorder.
  - EDS event menu: hot start, N2 overspeed, FTIT overtemperature, FTIT spread, oil, vibration, EEC fault, stall, AB blowout, RCVV, main fuel pump. Trend records need 180 s of stabilisation [DIRECT, [CP-2190](https://ntrs.nasa.gov/citations/19810022668)].
- **RNLAF F-16 operational recording** [DIRECT, [NLR-TP-2001-402](https://reports.nlr.nl/bitstreams/9eb019de-dcbb-40c3-b826-5c54b9eabc7b/download); read locally]:
  - FACE system (RADA ACE-based Flight Monitoring Unit + Data Recording Unit) records DEEC signals at **maximum 4 Hz**: core fuel flow, AB fuel flow, nozzle position, Mach, altitude, air temperature.
  - These were sufficient to drive a GSP engine model for HPT-blade creep/LCF lifing.
  - Error budget: FACE + data reduction ≈1%; GSP <2%; component loading ≈10%; life prediction 20–50%.
- **F100-PW-229 EDU and TAC**: P&W cites 6,000-TAC capability [DIRECT, [P&W via RTX](https://www.rtx.com/prattwhitney/products/military-engines/f100)]. EDU parameter lists and triggers for the -229 were not found publicly.

#### F110-GE-100 EMS (F-16C/D Blk 30/40) [DIRECT, AGARD-CP-448 papers 11 (Turkish AF) and 21 (Dyson & Ashby, GE), [archive.org DTIC ADA203800](https://archive.org/details/DTIC_ADA203800); read locally]
- **Hardware**:
  - engine-mounted EMS Processor (EMSP; digitises AFTC analog signals, computes parts-life data);
  - airframe EMS Computer (EMSC; diagnostics and storage, 1553 to the fire-control computer);
  - flight-line Data Display and Transfer Unit (DDTU);
  - Remote Status Panel (GO/NOGO).
- **Parameters** (Tbl 1):
  - engine: T4B, EPLA, T2, IGV, PS3, MVPOS, MTM, IGVTM, lube quantity and temperature, NF, NG, APLA, A8, fan duct ΔP/P, AUGPOS, WFRTM, A8TM, A/I, flame detector, AB initiation;
  - aircraft: Mach, AoA, Nz, total fuel flow, altitude, gear-up.
- **Recording**: 2 scans/s (12 pre-event scans = 6 s). Buffer sizes by trigger (Tbl 3):

| Trigger | Pre-event scans | Post-event scans | Total |
|---|---|---|---|
| Overtemperature / overspeed | 12 | 18 | 30 |
| Flameout / power loss / stall | 12 | 4 | 16 |
| Other faults | — | 4 | 4 |
| Pilot request | 12 | 4 | 16 |
| Trend (take-off, ≈M0.3) | — | 4 | 4 (2 s) |

  - Trend data: 18 engine parameters, 6 aircraft parameters and 5 discretes.
  - Seven trended parameters: T4B, WF, A8, NG, CDP, NF, lube quantity.
- **Parts life tracking**:
  - time above T4B limits at 5 levels (1,600/1,630/1,660/1,685/1,705 °F);
  - engine operating time; augmentor time and on/off cycles; LCF, Full Thermal Cycles and Cruise-Intermediate-Cruise cycles.
- **Ground flow**: DDTU → Zenith Z-248 with GE Ground Station Software → base Engine Management Branch → MEETS (USAF Logistics Management Center).
- **Real TAC example** (MEETS Tbl 8; verified): a bearing with LCF 107, FTC 579, CIC 389 shows TAC 261.5 against a 2,000 limit (1,738.5 remaining). This matches TAC = LCF + FTC/4 + CIC/40.
- **Field experience**: ≈70% of real faults isolated to the correct LRU (target 90%). False alarms ranged from 1 per 3 flights to 1 per 14 flights depending on software block [DIRECT, paper 21].
- **F110-GE-129 CEDU**: no public description found this session. Its existence and naming are not verified from a primary public source.

#### Cross-cutting US definitions (life usage and data systems)
- **TAC = LCF + FTC/4 + CIC/40**, where LCF = start → IRP → stop, FTC = idle → IRP → idle, and CIC = cruise → IRP → cruise [DIRECT, NATO RTO-TR-028 (2000, Distribution A) App. 1 pp.A1-3/A1-4; local copy `research_sources/flight_profiles/RTO-TR-028.pdf`; verified].
  - Equivalently, TAC = Type I + Type III/4 + Type IV/40 + Kx·(other cycles) [DIRECT, MIL-HDBK-1783B CHG2 App. Tbl XI p.45; local copy `research_sources/flight_profiles/MIL-HDBK-1783B_CHG2.pdf`; verified].
  - RTO-TR-028 cautions that TACs are "simple gate based counters… not universally equivalent".
- **MIL-HDBK-1783B Tbl X** design usage guidance for fighters (cold / hot parts) [DIRECT]:

| Usage measure | Cold parts | Hot parts |
|---|---|---|
| Type I cycles | 3,200 | 1,600 |
| Type III cycles | 20,000 | 10,000 |
| Type IV cycles | 24,000 | 12,000 |
| AB lights | 17,000 | 8,500 |
| AB time | 200 h | 100 h |
| Time at IRP+ | 800 h | 400 h |

  - Ground operation adds 0.75–1.0 h per mission.
- **Generic monitoring guidance** [TRANSFER: generic NATO guidance; RTO-TR-028 Ch. 8 Tbls 1–2]:
  - Recommended sampling: discs 1–2 Hz, turbine discs 1–4 Hz, turbine blades 2–8 Hz.
  - Accuracy: spool speed 0.1%, turbine blade temperature 4 K, EGT 2 K.
- **USAF data systems**:
  - CEMS (D042) is the USAF standard data system for engine status, accountability and critical-parts life tracking. Its 7 subsystems (D042A–G) interface with REMIS [DIRECT, T.O. 00-20-2 §2.7; local copy `research_sources/maintenance/TO_00-20-2_2007.pdf`].
  - JSSG-2007A requires the engine health monitoring system to be compatible with CAMS/CEMS (USAF) and AEMS/NALDA (USN) [DIRECT, JSSG-2007A A.3.7.6.1; local copy `research_sources/flight_profiles/JSSG-2007A.pdf`].

#### RM12 (Gripen C/D)
- **On-board recorders** [DIRECT, [SHK RM 2019:02](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf) §1.11 pp.19–20, Fig. 18]:
  - crash-protected CSMU with engine parameters;
  - DTU-GC (ground-crew data transfer unit) holding system health, fault status and engine parameters;
  - FADEC internal memory;
  - DTU-P and the video recorder.
  - CSMU engine channels: NLPC, NHPC, PLA, FVG, CVG, A8, PS3C, T5, plus AoA and altitude.
  - **Sampling rates not stated.**
- **GKN Life Tracking System (LTS)**:
  - Logged flight data plus models give wear for **140 rotating parts** (more than 60% of spares cost). Launched 2011/2012 (conflict). Used also by the Thai, Hungarian and Czech fleets. Saved "several hundred MSEK" [DIRECT, [GKN 2022 blog](https://www.mynewsdesk.com/se/gkn-aerospace-sweden/blog_posts/data-fraan-varje-enskilt-flygpass-hjaelper-flygvapnet-att-spara-miljoner-107056); [AIN 2011](https://www.ainonline.com/aviation-news/2011-06-23/paris-2011-volvo-aero-launches-tracking-system-saab-gripens-rm12-engine)].
  - Method [DIRECT, [Meyer 2014](https://publications.lib.chalmers.se/records/fulltext/201537/201537.pdf)]:
    - rainflow counting;
    - LCF crack-initiation (Coffin–Manson) lifing for most parts;
    - fan stages 1–3 inspected at fixed intervals (fretting), with the interval cut to one-fifth after the first inspection;
    - legacy on-board level-crossing counting of full and partial NH cycles;
    - the LTS database omits ground runs, which under-counts crack growth by 2.47–9.08%.
- **Maintenance structure** [DIRECT, [Patriksson et al. 2008](http://www.math.chalmers.se/Math/Research/Preprints/2008/45.pdf)]:
  - 7 modules; life-limited parts in a precedence graph (10/8/2/1/10/10/2 per module).
  - Life limits are set so that P(failure) < 1/1,000.

#### M53 (Mirage 2000) [DIRECT, AGARD-CP-448 paper 19, C. Sprung (SNECMA), "Le calculateur de potentiel sur le réacteur M53", [archive.org DTIC ADA203800](https://archive.org/details/DTIC_ADA203800); read locally]
- An airframe-mounted life-usage computer ("calculateur de potentiel") records engine operating parameters and expresses consumed life in **"heures de mission mixée"** (mixed-mission hours).
- Relative life consumption per mission type, with ferry = 1:

| Mission type | Relative consumption |
|---|---|
| Ferry | 1 |
| Ground-alert interception | 39 |
| Low-altitude interception | 5 |
| "Plastron" (adversary/target role) | 81 |
| Low-altitude penetration | 1.5 |
| Aerobatics | 2.75 |
| One "mixed mission" hour | 16 |

- The unit reads the engine serial number through a coded connector on the engine regulation computer, so it declares a fault if the engine is swapped without reinitialisation.
- Ground terminal (TSD) → base microcomputer → central computer.
- The variant (M53-5 vs -P2) is not stated. [TRANSFER: M53 family → M53-P2.]
- Cockpit parameters: N, Tt7, fuel pressure, oil pressure, AB/regulation/DSV states [DIRECT-secondary, [fr-wiki M53](https://fr.wikipedia.org/wiki/Snecma_M53)].

#### M88-2, AL-31FP, Tejas IN20, Kaveri
- **M88-2**: the Engine Condition Monitoring System uses engine sensors, vibration and oil-filter clogging data, and adjusts TBO by usage. This comes from en-wiki's summary of NATO RTO-MP-AVT-144-15, "Advanced Diagnostics in the SNECMA M-88 Engine of the Rafale Fighter"; the paper itself was not retrieved (secondary).
  - Rafale F4 adds on-board storage for predictive maintenance [DIRECT, Safran 13 Jul 2022, per sub-agent].
- **AL-31FP**: no engine-monitoring-system description found.
  - Soviet-era "Тестер" (Tester-U3) recorders with Луч-74 ground decoding are documented for Soviet aircraft generally; not confirmed for the Su-30MKI [TRANSFER: Su-27 family, [ru-wiki](https://ru.wikipedia.org/wiki/Бортовые_средства_объективного_контроля)].
  - The IAF runs an electronic maintenance management system with an engine "hardware tree", and has IIT-Bombay pilot projects on AI-based engine maintenance and digital twins [DIRECT, [The Hindu, 3 Nov 2024](https://www.thehindu.com/news/national/ai-big-focus-of-su-30mki-upgrade-iaf-taking-up-pilot-projects-with-iit-mumbai-says-officer/article68826449.ece)].
- **Tejas (F404-GE-IN20)**: ADA states Tejas has an on-board **Engine Condition Monitoring System** that shows real-time engine status, logs usage to compute **life usage indices** of life-limited parts, and includes vibration monitoring [DIRECT, [ADA Propulsion page](https://www.ada.gov.in/images/ps.htm)].
  - ADA's annual report lists "Engine Health Monitoring" (Naval LCA; Rs 57.48 M cumulative) and a "Mission Preparation & Data Retrieval Unit" [DIRECT, [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf) pp.75, 87].
  - A dual-redundant Utility Systems Management System exists [DIRECT, [ADA systems](https://www.ada.gov.in/images/sys.htm)].
  - Parameters, rates, triggers and algorithms: **not public**.
- **Kaveri**: flying-testbed data were recorded on board and telemetered [DIRECT, [PIB relid 66793](https://pib.gov.in/newsite/PrintRelease.aspx?relid=66793); URL built from the release ID]. No EHM paper found.

### Inferences
- [TRANSFER: F/A-18 IECMS → Tejas ECMS] ADA's own wording ("life usage indices of life-limited parts", real-time status, vibration monitoring) mirrors GE's F404 IECMS LUI concept. A virtual Tejas engine can defensibly emit the eight F404 LUIs per flight, plus 10 Hz/1 Hz gas-path/slow channels and 5 s + 25 s event snapshots.
  - Limits: on a FADEC engine the data would come from the FADEC rather than a separate MSDC, so quantisation and rates would differ, and LUI thresholds are not public.
  - Validate through IAF/HAL technical records obtained via the PS owner (DSSC/IAF).
- [ASSUMPTION] A realistic Phalanx telemetry design can borrow concrete, publicly documented numbers:
  - rates: 10/1 Hz (IECMS), 4 Hz (DEEC→EDU, FACE) and 2 scans/s (F110 EMS);
  - buffers: 5 + 25/35 s (IECMS) and 12 + 18 scans (F110);
  - quantisation: 16 rpm, 1 K, 0.5 psia (MSDC);
  - noise: Henry's 2σ table;
  - life counters: the 8 LUIs; T4B time-at-level bins; TAC = LCF + FTC/4 + CIC/40; mixed-mission hours (M53).
  - This gives a "family of realistic formats" rather than one invented one.

### Gaps
- IECMS limit values (EGT, N1/N2 overspeed, oil pressure, vibration thresholds), LUI weighting functions and the MMP code dictionary (only 709/759 seen): not public.
- F414 IECMS parameter list and rates, F110-GE-129 CEDU, F100-PW-229 EDU specifics: not found.
- RM12 sampling rates and triggers: not found. The LTS primary paper (Andersson, ISABE 2011, pp.1957–1965) is paywalled.
- M88 ECMS primary paper (RTO-MP-AVT-144-15) not retrieved.
- AL-31FP monitoring (Russian on-board engine monitoring systems, vibration monitors): nothing found.
- Tejas ECMS details: nothing beyond ADA's paragraph.
- USN "SEMS/ECMS" names and USAF ETD/IETDS and T.O. 00-25-257 contents: not found.

---

## 5. Public PHM / degradation / fault studies and real data

### Takeaway
There is **no public raw time-series or run-to-failure dataset for any candidate fighter engine.** What is public:
- **Calibration tables**: NASA operating points for F404-400, F100 and F110-129.
- **Digitisable plots**: transients, fault signatures, trend plots, usage histograms.
- **Fleet statistics**: MTBF, removal rates, life cuts, wear-debris rates.
- **Degradation magnitudes and observer designs**: F100/PW1128 Kalman health parameters with sensor noise, and RM12 gas-path analysis on real test-bed data (results only).

Indian work exists (HAL Koraput/CEMILAC/IIT Kanpur; CSIR-NAL) but uses **normalised or anonymised** data.

### Cited Findings

**F404**
- **CF-18 trending** [DIRECT, AGARD-CP-448 papers 7 and 37, [archive.org DTIC ADA203800](https://archive.org/details/DTIC_ADA203800)]:
  - take-off indices: fuel ratio units Wfm/PS3 at 81% and 87% N2; fan/core acceleration times while the nozzle is closed; PS3 rise time to 250 psi compared left vs right;
  - test-cell baseline cross-plots (e.g., Wfm/δ√θ vs N2/√θ, PS3/P1 vs N2/√θ, T56/θ vs P56/P1); variable-geometry correction cuts scatter 2–3×;
  - Kalman-band detection of HPC damage: +2% to +5% shifts against ±0.8% to ±2% nominal scatter;
  - the F404 can carry considerable component damage and still pass the EPR acceptance test.
- **EGT-harness bias of ≈60 °C** changed the identified fan-spool dynamics (K_N ≈22.1, τ_N ≈2.11 s with the fault) [DIRECT, CP-448 paper 36, Merrington, ARL; OCR partially garbled].
- **Oil debris (QFDA)** wear rates, µg/h, mean/2σ [DIRECT, Bennett et al. 1996, [archive.org DTIC ADP010173](https://archive.org/details/DTIC_ADP010173)]:
  - CF188: Fe 0.475/1.68; Ni 0.627/2.43; Ag 0.080/0.254.
  - USN: Fe 6.1/13.27 (different preparation method).
  - Two engines with confirmed faults exceeded 2σ on 5 elements each.
- **Vibration limits (RAAF test cell)**, in inches/s [DIRECT, DSTO-TN-0530, [archive.org DTIC ADA423658](https://archive.org/details/DTIC_ADA423658) Tbl 4]:
  - Steady: front frame 1.5; mid-frame (the IECMS accelerometer) 1.0; rear N2 1/rev 1.3.
  - Transient: 2.0–5.0, held for 5 s after an N2 change.
  - Baseline overall level ≈0.15–0.3 at idle rising to 0.5–1.0 at MIL/AB.
  - In-flight vibration monitoring "did not function up to expectations" [DIRECT, CP-448 paper 4].
- **Fleet reliability** [DIRECT, King & Tooker NPS 1993, [archive.org DTIC ADA277918](https://archive.org/details/DTIC_ADA277918)]:
  - F404 1987–90: MTBF 67.4 h; 3.7 removals per 1,000 EFH; MTTR 6.2 h.
  - NAVAIR 1993 life cuts of 14–64%, e.g., HPT disk 10,500 → 7,200 h.
  - The printed table has an internal inconsistency in the fan rows.
- **F414 reliability** [DIRECT, Hood et al. 2013, [archive.org DTIC ADA585693](https://archive.org/details/DTIC_ADA585693)]: 2012 fleet engine MTBF 582 h; AB-module MTBF 673 h, with 66.6% of AB defects in the main spray bars.
- **Navy engine-removal reason codes** (≈120, e.g., 2N metal in oil, 3D vibration, 6Q compressor stall, 6V LCF) [DIRECT, Schoch 2003 App. B, [archive.org DTIC ADA418270](https://archive.org/details/DTIC_ADA418270)]. These are ready-made labels for synthetic maintenance records.
- **Test-cell sensor faults** most common at NAS Jacksonville: accelerometer harnesses, CVG/FVG position sensors, CIT probes, PT5 probes, EGT thermocouples, wiring [DIRECT, Roemer et al. 2002, [archive.org DTIC ADA408947](https://archive.org/details/DTIC_ADA408947)].
- **Surge pressure time histories** during HARV departures: HPC-initiated, self-recovering [DIRECT, [TM-1999-206572](https://ntrs.nasa.gov/citations/19990024943) App. B].

**F100**
- **Deterioration magnitudes**:
  - "Experienced" losses: fan −1.0%, compressor −2.0%, HPT −2.5% efficiency [DIRECT, [TP-1056](https://ntrs.nasa.gov/citations/19770026225) p.8, locally verified].
  - The degraded PW1128 flown in PSC had ≈2% HPC and HPT loss and ran hotter FTIT [TRANSFER, [TM-4426](https://ntrs.nasa.gov/citations/19930003967)].
  - HPT −2.5% and LPT −1.0% can be estimated to ±0.25% [DIRECT, [TM-104233](https://ntrs.nasa.gov/citations/19910015833)].
- **Sensor noise standard deviations for synthetic data** [DIRECT/TRANSFER EMD, TM-104233 eq. 14; N1, N2, PT4, PT6 and FTIT taken from flight data]:
  - pressures: PT6 0.09 psi, PT4 0.6 psi;
  - temperatures: TT4.5 (FTIT) 5.0 °R;
  - speeds: N1 and N2 15 rpm.
  - Biases used in PSC work: FTIT +70°, AJ +2.0 in², WF +180 lb/h (TM-4426).
  - Hard-failure thresholds: N1 600 rpm, N2 800 rpm, FTIT 500 °R [DIRECT, [TP-2740](https://ntrs.nasa.gov/citations/19870015898) Tbl I].
- **Fault signatures** [DIRECT]:
  - nonrecoverable stall with 66 Hz rotating stall; N2 12,790 → 10,800 rpm while FTIT rises ([TM-81759](https://ntrs.nasa.gov/citations/19810016549));
  - AB rumble at 50–60 Hz before blowout;
  - quickfill pressure spikes to 300 psi causing stalls (1 in 994 lights);
  - nozzle/EPR limit cycle at 1–2 Hz ([CP-2298](https://ntrs.nasa.gov/citations/19860015871)).
- **Fleet metrics**, F100(3) vs -220 [DIRECT, [RAND N-3618](https://www.rand.org/pubs/notes/N3618.html) Tbl 4.2]:

| Metric | F100(3) | -220 |
|---|---|---|
| Stall-stagnations per 1,000 FH | 0.2–1 | 0–0.05 |
| Removals per 1,000 FH | 7.3 | 3.6–4.4 |
| Performance loss | 1% per 400 cycles | <2% per 4,000 cycles |

- **Bleed effects on the -220**: +20 °F FTIT per 1% bleed until the 1,720 °F limit, then thrust drops more than 6% [DIRECT-deck, [CR-179447](https://ntrs.nasa.gov/citations/19910010772)].

**F110**
- Only EMS trend-plot examples (ΔT4B, %ΔWF, Δ%NF vs baseline) and false-alarm statistics are public [DIRECT, AGARD-CP-448 papers 11 and 21].
- Usage ratios: 110.5 h EOT vs 69.0 h flight time; 213 AB lights; 4.3 h AB [DIRECT, CP-448 paper 11 Tbl 7].
- ROKAF, Turkish, Japanese and AFRL PHM literature was not searched (cap).

**RM12**
- Gas-path analysis on two real test-bed data sets, one degraded after accelerated mission testing and one low-hours [DIRECT, [GT2004-53591](https://research.chalmers.se/en/publication/10173); abstract only, data not released].
- Fleet usage statistics [DIRECT, [Meyer 2014](https://publications.lib.chalmers.se/records/fulltext/201537/201537.pdf)]:
  - histogram of partial NH cycles per mission (Fig. 4.4b);
  - crack depth vs LTS flight hours for 11 engines (Fig. 4.9);
  - real usage gave on average 31.1% (maximum 67.8%) more fan-disc life than the most severe engine.
- Weibull time-to-failure parameters after repair (scale 45.7–371, shape 1.36–3.04; time unit not stated) [DIRECT, [Patriksson et al. 2008](http://www.math.chalmers.se/Math/Research/Preprints/2008/45.pdf) Tbl 4].
- **Only public RM12 flight transient**: a 30 s, 10-channel trace through a cormorant-strike flameout and run-down, with all HPC stages damaged [DIRECT, [SHK RM 2019:02](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf) Fig. 18].

**AL-31FP / Indian legacy engines**
- **69 engine-related Su-30MKI failures** between end-2012 and early 2015, attributed to bearing fatigue and low oil pressure (secondary: en-wiki Su-30MKI citing a deleted Jane's article). The primary Parliament answer was not retrieved.
- **Rath, Mishra & Kushari 2024** (HAL Koraput / CEMILAC / IIT Kanpur) [DIRECT, [doi:10.1515/tjj-2023-0064](https://doi.org/10.1515/tjj-2023-0064)]:
  - model-predicted EGTs for degraded engines agreed with measured test-bed data;
  - estimated HPC efficiency drop and operating-line shift over service hours.
  - The engine is unnamed; that it is the AL-31FP or RD-33 is an [ASSUMPTION].
- **Sankar et al.** (CSIR-NAL / HAL Koraput / CEMILAC) [DIRECT, DSJ 72(2) 2022, [doi:10.14429/dsj.72.15428](https://doi.org/10.14429/dsj.72.15428); read locally]:
  - Engine: a legacy twin-spool turbojet with 5-stage LPC + 6-stage HPC, OPR ≈12, ≈100 kg/s, hydromechanical control holding T4 via nozzle area. [ASSUMPTION] R-29 class.
  - Test-bed sensors (OEM sensors via NI-PXI) plus added LPC-exit and HPT-exit pressure and temperature sensors.
  - Gas-path analysis that accounts for how the control mode masks degradation.
  - Data are **normalised "to withhold the actual performance data"**.
- **EGT measurement error** in AB on a GTRE engine test bed [DIRECT, George & Muthuveerappan, DSJ 72(1) 2022 pp.10–17; local copy `al31_m53_m88_kaveri/DSJ_2022_George_EGT_Afterburner_ErrorEstimation.pdf`]:
  - gas temperature 97 K off thrust-derived temperature;
  - components: radiation 69 K, conduction 3 K, velocity 1 K;
  - 24 K after correction.
  - Useful for thermocouple error models [TRANSFER to any AB engine].
- **2nd-stage compressor blade fatigue** in a "typical Russian fighter-class aero-engine" [TRANSFER: Russian engines at HAL; Sahoo & Gouda, DSJ 52(4) 2002 pp.363–367; local copy `al31_m53_m88_kaveri/DSJ_2002_Sahoo_Gouda_CompressorBladeFailure_RussianFighterEngine.pdf`].

### Inferences
- [ASSUMPTION] Public PHM material is sufficient to *parameterise* realistic degradation and faults:
  - module efficiency/flow deltas of 1–2.5%;
  - EGT/FTIT margin erosion masked by the control (DEEC "FTIT rises to hold EPR"; Sankar's control-mode masking);
  - stall/rumble frequencies;
  - oil-debris wear-rate distributions;
  - vibration limits and baselines;
  - sensor biases, noise and quantisation;
  - LCF-counting artefacts.
  - It is insufficient to *validate* a degradation trajectory against real fleet data for any candidate. Validation must rely on digitised plots and fleet-level statistics (MTBF, removal rates, life cuts).
- [ASSUMPTION] Indian authors' practice of normalising data suggests that real IAF/HAL data, if released through the PS owner, will likely arrive normalised. The Phalanx generator should therefore support emitting normalised as well as engineering-unit channels.

### Gaps
- No public datasets for any candidate engine. Cross-link: the public-datasets researcher (C-MAPSS/N-CMAPSS as commercial-engine surrogates).
- Not retrieved: the primary CAG and Parliamentary documents on AL-31FP failures; the CAG 2015 LCA audit; the CAG 2010-11 Kaveri audit (cag.gov.in URLs returned 404).
- Paywalled and unread: Cue & Muir (ASME 90-GT-357), AGARD-CP-480, the ISABE 2011 RM12 papers, Hall et al. 2001.

---

## 6. Scoring, ranking and recommendation

### Takeaway
On **public modelling fidelity alone**, the **F100-PW-220** (with the -100/F100(3)/EMD NASA corpus) ranks first, the **F404-GE-400/402** second, and the RM12 and F110-GE-100 next.

Weighting in **Indian relevance**, the best choice is a **"composite F404" model targeted at the F404-GE-IN20 (Tejas Mk1/Mk1A)**. It is built from:
- F404-GE-400/402 NASA data;
- the F/A-18 IECMS monitoring semantics;
- the RM12 FADEC-era recording and LTS lifing practice;
- the F100 NASA corpus used as a *method* template (model structure, DEEC-style control/FDA, Kalman health parameters).

The **AL-31FP** is the highest-relevance alternative (largest IAF fleet, HAL Koraput production), but its public cycle data are aggregator-grade and its monitoring layer is undocumented.

### Cited Findings

#### (a) Key findings summary
1. **No candidate has public dimensional component maps, control schedules or redlines.** These come only from OEM decks and limited-distribution manuals. All faithful models must use generic maps scaled to public operating points ([TM X-3261](https://ntrs.nasa.gov/citations/19750019996) is normalised; F404, RM12 and F110 decks are referenced but not public).
2. **The F100 has the deepest public modelling corpus**: a full real-time model with equations, normalised maps, inertias and volumes; linear models; DEEC logic and FDA; Kalman health parameters with sensor noise; the TERTS validation. It also has a well-documented -220 EMS/EDU (4 Hz DEEC data, 21 events) [DIRECT; Sections 2–4].
3. **The F404 has the best-documented on-aircraft monitoring system** (F/A-18 IECMS: rates, buffers, quantisation, 2σ noise, 8 LUIs, three nations' ground systems). It also has rich NASA operating-point data and documented transient constants [DIRECT; Sections 1–4].
4. **The F404-GE-IN20 has almost no variant-specific public data** beyond GE's datasheet (84 kN, 70 kg/s, OPR 28, FADEC) and ADA's statement that Tejas has an ECMS computing life usage indices. Its fidelity must come by transfer from the -400/-402 and RM12 [DIRECT; Sections 1, 4].
5. **The RM12 adds a public FADEC-era flight transient** (SHK), a crash-recorder channel list matching F404 naming, and a well-described fleet LTS (140 parts, rainflow, Coffin–Manson, crack growth) [DIRECT; Sections 1, 4].
6. **The F110-GE-100 EMS is fully described publicly** (parameters, 2 scans/s buffers, fault codes, T4B time-at-level, TAC). The F110-GE-129 has 39 public measured operating points. Neither has public schedules or maps [DIRECT; Sections 1, 4].
7. **The AL-31F/FP, M53-P2, M88-2 and Kaveri** have strong Indian relevance but thin public engineering data:
   - AL-31F: an AGG regime table and altitude-speed chart.
   - M88-2: an official datasheet with TIT; its ECMS paper was not retrieved.
   - M53: a life-usage-computer paper (mixed-mission hours).
   - Kaveri: primary programme facts, aggregator cycle.
8. **Public Indian degradation work exists but is anonymised or normalised** (HAL Koraput/CEMILAC/IIT Kanpur GasTurb study; CSIR-NAL GPA).

#### (b) Scoring table (0–5) and ranked recommendation

Scores are the coordinator's synthesis, consolidating the sub-agents' suggestions and adjusted after cross-checking. For example, the F100-PW-220 monitoring score was raised from 2 to 4 after locating the CP-448 paper 18 EMS description.

Rubric (0 = nothing public; 5 = enough public detail to build that layer with high fidelity without OEM data):
- **Cycle**: cycle and design data.
- **Maps/models**: component maps and published models.
- **Control**: control documentation.
- **Monitoring**: monitoring and sensor documentation.
- **PHM**: degradation and PHM literature.
- **Real data**: real data availability (tables, traces, statistics).
- **India**: Indian relevance.

| Engine | Cycle | Maps/models | Control | Monitoring | PHM | Real data | **Fidelity sum (/30)** | India | **Weighted total (/40)** = fidelity + 2×India |
|---|---|---|---|---|---|---|---|---|---|
| F404-GE-IN20 *as composite F404 (via -400/-402 + RM12 transfer)* | 2.5 (GE sheet + transfer) | 2 | 2.5 | 3 | 2.5 | 2 | **14.5** | 5 | **24.5** |
| F404-GE-400/402 (F/A-18 A-D) | 3 | 2 | 3 | 4 | 3 | 2 | **17** | 3 | **23** |
| F100-PW-220 (incl. F100(3)/EMD transfer) | 3 | 3 | 4 | 4 | 4 | 2 | **20** | 1 | **22** |
| AL-31F / AL-31FP (Su-30MKI) | 3 (complete but AGG) | 2 | 2 | 1 | 2 | 1 | **11** | 5 | **21** |
| F100-PW-200 / -100 | 3 | 4 | 3 | 3 | 3 | 2 | **18** | 1 | **20** |
| M88-2 (Rafale) | 3 | 1 | 2 | 2 | 1.5 | 1 | **10.5** | 4 | **18.5** |
| Volvo RM12 (Gripen C/D) | 3 | 1 | 2 | 3 | 3 | 1.5 | **13.5** | 2 | **17.5** |
| F414 (E/F, Gripen E, Tejas Mk2) | 2 | 1 | 1 | 2.5 | 1.5 | 1 | **9** | 4 | **17** |
| F110-GE-100 (F-16 Blk 30/40) | 3 | 1 | 2 | 4 | 1.5 | 2 | **13.5** | 1 | **15.5** |
| GTX-35VS Kaveri / KDE | 2 | 1 | 1 | 1 | 1 | 0.5 | **6.5** | 4 | **14.5** |
| F110-GE-129 (F-16 Blk 50/70, F-15) | 3 | 2 | 1 | 1 | 1 | 3 | **11** | 1.5 | **14** |
| F100-PW-229 (F-16 Blk 52, F-15E) | 3 | 2 | 2 | 1 | 2 | 2 | **12** | 1 | **14** |
| M53-P2 (Mirage 2000) | 2 | 1 | 2 | 2 | 1 | 0 | **8** | 3 | **14** |
| F404-GE-102 (T-50) | 2 | 1 | 1 | 0.5 | 0 | 0 | **4.5** | 2 | **8.5** |

Score justifications (citations are in Sections 1–5):
- **F404-GE-400/402**
  - Cycle 3: NASA operating points, 100% N1, A8 and PLA map are public. TIT, -400 OPR, T5 limit and N2 scale are missing.
  - Maps/models 2: no maps; the TM-4240 tables-plus-lag model and calibration curves are public.
  - Control 3: qualitative modes, sensors with ranges, AB sequence and slew rates; no numbers for schedules.
  - Monitoring 4: IECMS is fully described except limits and LUI weights.
  - PHM 3: CF/ARL trending, oil debris, vibration limits, reliability.
  - Real data 2: tables and plots only.
  - India 3: parent of the IN20.
- **IN20 composite**: inherits the -400/-402 scores, discounted for transfer uncertainty (FADEC and hot-section changes). Monitoring is set to 3 because ADA confirms an ECMS with LUIs but gives no detail. India 5: Tejas Mk1/Mk1A is the IAF's indigenous fighter, with 99 + 113 engines ordered (GE release; second order secondary).
- **F100-PW-220**: Maps/models 3, because the F100(3)/EMD models and TERTS validation transfer but there are no -220 maps. Control 4: DEEC loops, schedules-as-functions and FDA are public, numeric schedules are not. Monitoring 4 (CP-448 paper 18 + RNLAF FACE). PHM 4 (Kalman health, noise, deterioration magnitudes).
- **F100-PW-200/-100**: Maps/models 4, because TM X-3261/TP-1034 is a complete model with normalised maps for this exact engine family.
- **AL-31F/FP**: Cycle 3, because the dataset is complete (speeds, SFC, limits, transient times) but aggregator-sourced. Monitoring 1: nothing public. India 5: ≈259–272 Su-30MKI; a 240-engine HAL Koraput order approved Sept 2024 (secondary press; Economic Times URL not captured, verify).
- **RM12**: Monitoring 3 (recorder architecture plus LTS), PHM 3 (Swedish body of work, mostly paywalled), Real data 1.5 (one 30 s trace plus usage statistics).
- **F110-GE-100**: Monitoring 4 from CP-448 papers 11 and 21.
- **F110-GE-129**: Real data 3 from NASA TM-104326's 39 measured points.
- **M88-2**: Cycle 3 from the official datasheet including TIT. India 4: 36 IAF + 26 Rafale M ordered; Hyderabad M88 MRO shop.
- **Kaveri**: indigenous and strategic (India 4), but not fielded and with aggregator-only cycle data.

**Ranked recommendation (with trade-offs)**
1. **Primary target: F404-GE-IN20 built as a "composite F404" virtual engine** (weighted 24.5/40).
   - Pros:
     - highest Indian relevance;
     - best-documented monitoring semantics (IECMS → Tejas ECMS "life usage indices");
     - NASA F404 calibration data;
     - RM12 FADEC-era channels and lifing;
     - a defensible transfer chain (-402 → IN20; RM12 ≈ IN20 class).
   - Cons:
     - every IN20-specific number beyond the GE datasheet is a transfer or assumption;
     - FADEC logic, limits and Tejas ECMS formats are unknown.
2. **Methodological backbone / validation surrogate: F100-PW-220** (fidelity 20/30). Use its NASA model structure, DEEC control and FDA logic, Kalman health-parameter set and EMS/EDU event taxonomy to make the F404 composite behave realistically, and to cross-validate the generator on an engine whose behaviour is publicly pinned down. It is not recommended as the *displayed* platform: India relevance 1.
3. **High-relevance alternative: AL-31FP (Su-30MKI)** (weighted 21/40).
   - Choose this only if the PS owner (DSSC/IAF) prioritises the Su-30MKI fleet and can supply sanitised data.
   - Its public cycle data are complete but unverified (AGG), and its monitoring layer would have to be invented by transfer from the F404, F110 or F100.
4. **M88-2**: good official cycle sheet and a current Indian fleet. Thin model and monitoring documentation; obtain RTO-MP-AVT-144-15 to improve it.
5. **RM12**: use as an enrichment source for the F404 composite rather than as a target (Gripen is not IAF).
6. **F110-GE-100/-129, F100-PW-229, M53-P2, F414, Kaveri, F404-GE-102**: lower combined scores.
   - The F-16 Block 50/52 engines (-129/-229) are noticeably *less* documented than the older -100/-220, so an "F-16" choice should mean an F100-PW-220 or F110-GE-100 model.

### Inferences
- [ASSUMPTION] The choice of "most faithful" engine depends on whether Phalanx values *verifiable physics* (F100-PW-220) or *operational relevance plus credible monitoring semantics* (composite F404/IN20). The hybrid (an IN20 face on an F100-proven method) captures most of both. It can be presented honestly to judges with the tags above.
- [ASSUMPTION] Validation plan for the composite F404:
  - steady state against TM-100159, CR-198052 and TM-4538 tables;
  - transients against TM-4240 Figs. 9–10, TP-1056 transient specifications ([TRANSFER] as a sanity envelope) and the SHK RM12 Fig. 18 trace;
  - monitoring outputs against IECMS rates, buffers, quantisation and 2σ noise;
  - life counters against the LUI definitions and MIL-HDBK-1783B usage tables.

### Gaps

#### (c) Open questions / gaps
- **Variant-specific F404-GE-IN20 data**: TIT, T5 limit, N1/N2 redlines, FADEC modes, Tejas ECMS parameter list, rates and LUI definitions. Ask ADA/HAL/IAF through the PS owner.
- **Search cap and access problems**: the shared search budget was exhausted, DTIC was down and DiVA was unreachable. The following were therefore **not searched** and should be in a follow-up pass (the user can send a follow-up message or raise the search limit):
  - DSTO/NRC/NPS/AFIT/Cranfield F404 and F414 model theses;
  - Chinese AL-31F gas-path papers;
  - ROKAF/Turkish/Japanese F110 PHM papers;
  - USN SEMS/ECMS and USAF ETD/IETDS documents;
  - Finnish/Swiss/Spanish F404 work;
  - FOI RM12 reports;
  - French M53/M88 theses;
  - CAG/Parliament primaries (AL-31FP failures, LCA 2015 audit, Kaveri 2010-11 audit).
- **Paywalled or blocked key papers to obtain manually**:
  - Powell 1991 (ASME JEGTP 113:1–10, F404 design);
  - Hall et al. 2001 (F414 advanced IECMS);
  - Andersson ISABE 2011 (RM12 LTS);
  - RTO-MP-AVT-144-15 (M88 advanced diagnostics);
  - Larsson et al. ASME 88-GT-305 (RM12 vs F404 deltas);
  - Grönstedt & Wallin GT2004-53591;
  - Rath et al. 2024 IJTJE (to identify the HAL Koraput engine);
  - NATO RTO-TR-044 (download failed, Cloudflare 524).
- **Unresolved conflicts**:
  - F404-400 dry thrust (10,000 vs 10,700 lbf);
  - TM-4240 vs TM-110216 PLA rate limits;
  - IECMS post-event length (25 vs 35 s);
  - RM12 airflow (68/69/71.7 kg/s);
  - F110 HPC stage count (9 vs 7);
  - AL-31F dry thrust, BPR and TIT;
  - M53 TIT;
  - M88-2 AB thrust (75.6 vs 73.4 kN);
  - Kaveri thrust and weight;
  - F100-100 BPR (0.8 vs 0.6).
- **Compliance flag for the report writer**: sibling folders contain manuals that are probably not genuine public releases. Do **not** use them as sources:
  - `research_sources/flight_profiles/HAF_F16CD_Flight_Manual_GR1F-16CJ-1.pdf`, which carries a foreign-disclosure restriction (flagged by the F110 sub-agent);
  - `FA18_ABCD_NATOPS_publicintelligence.pdf`. The F/A-18 NATOPS is normally limited distribution; Distribution Statement C is believed but not verified.
  - These were not used here.

#### (d) Ranked list of most valuable sources for later deep reading
1. **AGARD-CP-448, "Engine Condition Monitoring – Technology and Experience" (1988)**, [archive.org DTIC ADA203800](https://archive.org/details/DTIC_ADA203800). Papers 2, 4, 7, 37 (F404 IECMS, USN/CF), 18 (F100-PW-220 EMS/EDU), 11 and 21 (F110-GE-100 EMS), 19 (M53 life computer) and 36 (ARL fault tests). The single most valuable public source for engine monitoring formats, rates, buffers, noise and life counters across three candidate families.
2. **NASA TM X-3261 + TP-1034 + TP-1261** ([19750019996](https://ntrs.nasa.gov/citations/19750019996), [19770024210](https://ntrs.nasa.gov/citations/19770024210), [19780022953](https://ntrs.nasa.gov/citations/19780022953)). A complete, implementable F100 real-time model with normalised maps, inertias, volumes and linear models: the method backbone.
3. **NASA CP-2298** (DEEC flight evaluation), [19860015871](https://ntrs.nasa.gov/citations/19860015871). The best public fighter FADEC logic, FDA table and flight transients.
4. **NASA TM-4240** ([19910009766](https://ntrs.nasa.gov/citations/19910009766)) and **CR-1998-208416** ([19980219005](https://ntrs.nasa.gov/citations/19980219005)). F404 transient constants with digitisable step responses; the most explicit F404 control-logic description.
5. **NASA TM-100159, CR-198052, TM-4538, TP-3001** ([19870020104](https://ntrs.nasa.gov/citations/19870020104), [19970027377](https://ntrs.nasa.gov/citations/19970027377), [19940010668](https://ntrs.nasa.gov/citations/19940010668), [19900015818](https://ntrs.nasa.gov/citations/19900015818)). F404 calibration-grade operating points, sensor ranges and the station diagram.
6. **NASA TM-4426, TM-104233, PSC workshop** ([19930003967](https://ntrs.nasa.gov/citations/19930003967), [19910015833](https://ntrs.nasa.gov/citations/19910015833), [19950026592](https://ntrs.nasa.gov/citations/19950026592)). Kalman health parameters, sensor noise and biases: the degradation-injection schema.
7. **SHK RM 2019:02** ([PDF](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf)) and **Meyer 2014** ([PDF](https://publications.lib.chalmers.se/records/fulltext/201537/201537.pdf)). The only public RM12 flight trace and FADEC logic; LTS lifing internals and real-mission cycle statistics.
8. **NATO RTO-TR-028 (2000)** and **MIL-HDBK-1783B CHG2**, local copies in `research_sources/flight_profiles/`. TAC definitions, usage tables, monitoring sampling and accuracy guidance.
9. **NASA TM-104326** ([19970003552](https://ntrs.nasa.gov/citations/19970003552)). 39 measured F110-GE-129 operating points against the GE deck.
10. **NASA MAPSS Users' Guide** ([20040035577](https://ntrs.nasa.gov/citations/20040035577)) and **NLR TERTS** ([NLR-TP-2002-069](https://reports.nlr.nl/handle/10921/666)). Generic military-engine sensor and health-parameter schema; F100-PW-220 real-time validation and transients.
11. **Canadian and NPS reports**: Paré & Muir 1998 ([ADA347270](https://archive.org/details/DTIC_ADA347270)), Schoch 2003 ([ADA418270](https://archive.org/details/DTIC_ADA418270)), Hersey 2008 ([ADA493918](https://archive.org/details/DTIC_ADA493918)), Hagan & Slack 2006 ([ADA462668](https://archive.org/details/DTIC_ADA462668)). Ground-system architecture, removal codes, life limits and record-fragmentation evidence.
12. **Indian sources**:
    - [ADA Propulsion page](https://www.ada.gov.in/images/ps.htm) (Tejas ECMS);
    - [Rath et al. 2024](https://doi.org/10.1515/tjj-2023-0064) (HAL Koraput degradation, paywalled);
    - [Sankar et al. DSJ 2022](https://doi.org/10.14429/dsj.72.15428) (Indian test-bed gas-path analysis);
    - the [leteckemotory AL-31](http://www.leteckemotory.cz/motory/al-31) regime table and altitude-speed chart (AGG, but the best AL-31F validation target);
    - Snecma M88-2 datasheet (local).
