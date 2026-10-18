# Maintenance & Operational Records and Event Chains for a Virtual Fighter (Phalanx)

Scope: how real military (plus some civil) maintenance and operational information is structured and written, so that synthetic telemetry/BIT events can be linked to realistic records. The emphasis is on what applies to the IAF.

**Evidence tags.** [DIRECT] means the claim concerns the force or system the source itself governs, and the force is named in the claim. [TRANSFER: X→IAF] means the practice is documented for force X and is proposed as a template for the IAF; a reason and the limits follow. [ASSUMPTION] means it is not verified in a public source.

**Downloaded primary documents** are saved in `/Users/abishaikc/Phalanx/research_sources/maintenance/`, with `.txt` extractions alongside:
- TO 00-20-1 (2013) and TO 00-20-2 (2003, Change 2 2007)
- NAMP COMNAVAIRFORINST 4790.2E (28 Oct 2024) and the F-35 supplement 4790.35D
- UK MAM-D; MOD F799/5A(C17A); two UK Service Inquiries
- Three CAG IAF reports and the CAG LCA report
- The IAF RTI Handbook, Suo-Moto Disclosure and Doctrine
- S5000F Issue 4.0 and MIL-HDBK-338B
- FAA AC 120-17B, AC 121-22D and AC 20-109B, plus the SDRS lookup tables
- GAO-02-86, GAO-01-587, GAO-16-439, GAO-20-316, GAO-23-105341 and GAO-23-106217
- MaintNet and NIST TLP papers

**Version caveats.**
- The current TO 00-20-1 (26 Sep 2022) and the current TO 00-20-2 (reportedly Change 33, Dec 2024) are hosted on tinker.af.mil, which returned HTTP 403. The 2013 and 2007 public editions on EverySpec were used instead. Code tables are long-lived, but individual codes may have changed.
- DAFI 21-101 and DAFI 21-103 (static.e-publishing.af.mil), USAF AIB reports (afjag.af.mil), DOT&E F-35 reports, and the older NAMP 4790.2C chapter PDFs on navalsafetycommand.navy.mil were all blocked (403/404) and were not read.
- The web-search budget was exhausted partway through. Later sources were reached by direct navigation of known publisher sites (gov.uk, cag.gov.in, gao.gov, faa.gov, s-series.org, indianairforce.nic.in, navair.navy.mil).

**Cross-links to parallel researchers:**
- Engine data / F404 parameters → see *engine data* notes.
- Sensor residual texture and fault/degradation physics → see those notes. This file only specifies how such events surface in records.
- Data pathway/formats → see *data pathway* notes. The NAMP SMART-aircraft module and the F-35 SOU/PMD flow below are the record-side counterpart.
- Flight profiles → sortie/flight-record fields (AFTO 781, NAVFLIR, MOD F724-726) are listed here.

---

## Q1. Military maintenance data systems and forms with public documentation (USN NAMP, USAF 00-20 series, UK MOD Form 700, IAF/HAL)

### Takeaway
All three Western systems share one skeleton:
- **A per-aircraft "technical log"** holds the current state: USAF AFTO 781 binder/IMDS; USN Aircraft Discrepancy Book/AADB in NALCOMIS OOMA; UK MOD F700C/GOLDesp.
- **Per-defect work documents** carry a unique job number: USAF JCN; USN JCN+MCN; UK SNOW/ORN.
- **Coded fields** describe the defect: what system (WUC), when discovered, how it malfunctioned, what action was taken, type of maintenance.
- **Free-text** discrepancy and corrective-action narratives accompany the codes.
- **Signatures and certification levels** close the job: corrected-by/inspected-by; 1st/2nd/3rd signature.
- **Separate component/engine life records** stay with serialized parts: AFTO 95/781J/781K + CEMS; AESR/ASR/MSR/SRC/EHR; MOD F731/F744-749 ERCs.

The IAF publicly confirms the RAF-derived "1st–4th line servicing" structure (O/I/D levels), BRDs, Maintenance Command, IMMOLS and an "eMMS" organisation. However, no public IAF form layout was found in this research. Form 700-style IAF records are therefore an inference.

### Cited Findings

**USAF — T.O. 00-20-1 (Aerospace Equipment Maintenance Inspection, Documentation, Policies and Procedures, 15 Jun 2013 public edition)**
- [DIRECT] The USAF lists its Maintenance Information Systems (MIS) as IMDS, REMIS, G081, CEMS, PAMS, ALERTS, ALSMS, DRILS and RAMPOD. "REMIS is the system of record for all maintenance data documentation." F-22 IMIS and F-35 ALIS use "embedded electronic forms" — [TO 00-20-1 (2013) §3.2, p.3-1](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).
- [DIRECT] Use of automated forms is mandatory. As a minimum, MIS-generated AFTO 781A, 781J, 781K and 95 count as automated forms. Dates are written YYYYMMDD and times on the 24-hour clock. A "minimum signature" is first initial + last name + employee number/USERID — [TO 00-20-1 §§3.3–3.6, pp.3-1/3-2; §5.1](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).
- [DIRECT] The AFTO 781 series provides "a maintenance, inspection, service, configuration, status, and flight record". Forms 781, 781A, 781F, 781H and 781K are mandatory in the aircraft forms binder, in the order 781F, 781B, 781, 781H, 781A — [TO 00-20-1 §§5.1, 5.3, p.5-1](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).
- [DIRECT] The individual forms:
  - **AFTO 781** — "source document for recording individual flying time, sorties and/or events". It is entered into the MIS at maintenance debriefing.
  - **AFTO 781A (Maintenance Discrepancy and Work Document)** — blocks FROM/TO, MDS, SERIAL NUMBER, PAGE, SYM, JCN, DATE DISC, DOC NUMBER (supply document number if back-ordered), CF 781A / XF 781K, DATE CORRECTED, WUC/REFERENCE DESIGNATOR, STA CODE (GEO-LOC), DISCREPANCY, DISCOVERED BY, EMPLOYEE NO/USERID, CORRECTIVE ACTION, CORRECTED BY, INSPECTED BY, EMPLOYEE NUMBER.
  - **AFTO 781H** — status (symbol history and exceptional release), airframe time, landings (full-stop/total), cartridge/JFS starts, engine cycles and servicing data.
  - **AFTO 781J** — engine flight document: airframe time, oil sample X, oil added, engine position, oil change time, engine time and cycles.
  - **AFTO 781K** — inspection status, engine data (position, serial number, change-due time), calendar/hourly inspections, and delayed discrepancies/TCTOs, with SYM, JCN, DOCUMENT NUMBER and GROUND DATE/TIME.
  - Source: [TO 00-20-1 §§5.6–5.14, pp.5-2 to 5-36](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).
- [DIRECT] **Status symbols.**
  - **Red X** = "unsafe or unserviceable and will not be flown". It is also used when work starts on an urgent TCTO, when an FO inspection is required after intake/exhaust work, when a major inspection starts, and for impoundment.
  - **Red Dash** = condition unknown (e.g., an operational check or FCF due, inspection due, PDM due).
  - **Red Diagonal** = a discrepancy not urgent enough to ground.
  - A black last-name initial over the symbol clears it.
  - Clearing rules: a Red X requires both a CORRECTED BY and an INSPECTED BY signature; a Red Dash requires INSPECTED BY; a Red Diagonal requires CORRECTED BY. A Red X may be downgraded to a Red Diagonal for a one-time flight.
  - Source: [TO 00-20-1 Ch 4, pp.4-1 to 4-4](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).
- [DIRECT] **Writing rules for 781A.**
  - One defect per block; review existing entries before writing to avoid duplicates.
  - Repeat/recurring discrepancies are flagged by writing "Repeat/Recurring".
  - Red X corrective actions must cite a TO reference ("function number/fault code for MIDAS based TOs").
  - Operational checks are written "OP CK GOOD"/"OP CK BAD".
  - Cannot-duplicate items are written "Cannot Duplicate Malfunction" or "CND".
  - Duplicates are closed by referencing the original entry.
  - Source: [TO 00-20-1 §§5.4.1.1, 5.7.3.16–5.7.3.19.6, pp.5-1 to 5-10](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).
- [DIRECT] **Engine historical record** requirements include recording the airframe serial number, total time and engine position at installation. Each record line should read "TT ___, TSO ___, Cycles ___". Over-speed, over-temperature and FOD events and life-limited component removals are also recorded — [TO 00-20-1 §9.1.6, p.9-1](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).

**USAF — T.O. 00-20-2 (Maintenance Data Documentation, 15 Jun 2003, Change 2 15 Apr 2007, Distribution A)**
- [DIRECT] **Discovery modes.** Jobs enter the database in four ways: during a scheduled event; as an individual unscheduled discrepancy; from a debriefing tied to a flight; and "by an on-board recording device and would be input electronically" — [TO 00-20-2 §3.1.1.2, p.3-1](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **JCN.** The base-level JCN is 9 characters: ordinal day YYDDD plus a 4-character sequence (e.g., 960410001). Every action related to a job carries the same JCN. Phase inspections use a letter in the 6th position. A cannibalization (CANN) creates two JCNs: one for the T/U actions and one for facilitate-other-maintenance (FOM) work — [TO 00-20-2 §4.2, pp.4-1/4-2; Fig 4-1](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Code field formats:**
  - Workcenter: 5 characters
  - ID number: 5 characters ("A" + last 4 of the serial for aircraft)
  - SRD: 3 characters (it also flags MICAP/MDD/TCTO reportability)
  - Type Maintenance: 1 character
  - Component Position: 1 digit (required for engine WUCs 21–29)
  - WUC: 5 characters. The first 2 characters are the system; the 3rd–4th are subsystem/assembly; the 5th is the reparable item. A "9"/"99" means NOC (not otherwise coded). Letters I and O are not used.
  - Action Taken: 1 character
  - When Discovered: 1 character
  - How Malfunctioned: 3 characters
  - Units: 2 digits
  - Crew size: 1 digit
  - Start/stop time: Julian day + hhmm, with "no case" exceeding 10 hours per entry.
  - Systems with BIT report the "fault codes (primary if multiple codes)" in block 16 or in the narrative.
  - Source: [TO 00-20-2 Ch 4, pp.4-1 to 4-12](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Narrative standards.** The discrepancy should "completely describe the problem, including multiple Built in Test (BIT) fault codes". The corrective action must closely match the ATC/WUC/HMC used. Minimally acceptable phrasings are listed, e.g., "troubleshot (item)", "inspected (item) - could not duplicate write-up no defect found", "(item) loose - adjusted and ops checked good" — [TO 00-20-2 §§4.13–4.14, pp.4-5/4-6](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Action Taken codes (App E)** include:
  - "H" = equipment checked, no repair required. It must be used with HMC 672/799/812/948; on-equipment it is termed CND.
  - "B" = bench checked serviceable. This is BCS at base level and RTOK at depot.
  - "R" = remove & replace; "P" = removed; "Q" = installed; "S" = remove & reinstall.
  - "T"/"U" = cannibalization removal/replacement.
  - "Y" = troubleshoot; "X" = test-inspect-service; "L" = adjust; "G" = repair/replace minor parts; "F" = repair.
  - "0"–"9" = NRTS reasons (e.g., 4 = lack of parts, 9 = condemned).
  - Source: [TO 00-20-2 App E, pp.E-1 to E-3](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **How Malfunctioned codes (App G)** carry a "type defect": 1 = inherent, 2 = induced, 6 = no defect. Selected codes:
  - Engine and condition-monitoring: 175 "Condition Monitoring-Adverse EGT/TIT Trend"; 178 "Vibration Trend"; 180 "Adverse Oil Consumption Trend"; 182–189 performance/borescope trends; 191 High EGT; 192 Over Temperature; 193 Excessive Stalls; 202 Low Oil Pressure; 372 Metal in Sump/Screen or on MAG Plug; 916 JOAP Removal.
  - BIT-related: 644 "Built-in Test (BIT) Indicated Fault"; 672 "BIT False Alarm"; 674 "BIT Fault Indicated Wrong Unit"; 675 "BIT Fault Not Duplicated, Parameters Confirmed by Data"; 676 "BIT Fault Not Duplicated on Ground, Parameters Do Not Confirm Fault".
  - No-defect and other: 799 "No Defect"; 800 removed/reinstalled to FOM; 812 defect caused by associated equipment; 875 removal for/after cannibalization; 879 "Expiration of maximum cycles/sorties"; 901 Intermittent; 948 Operator Error.
  - Source: [TO 00-20-2 App G, pp.G-1 to G-8](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **When Discovered codes (App H, aircraft set):** A Before Flight-Abort; B Before Flight-No Abort; C In-Flight-Abort; D In-Flight-No Abort; E After Flight; F Between Flights-Ground crew; H Thru-flight; J Preflight; K Hourly postflight; M Phased/Scheduled/Periodic inspection; P FCF; Q Special inspection; R QC check; S Depot; U Oil analysis; W In-shop; X Engine test cell; Y Upon receipt from supply; 2 "During Operation of Malfunction Analysis and Recording Equipment … (MADAR)" — [TO 00-20-2 App H, pp.H-1 to H-3](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Type Maintenance codes (App F)** include: A Service; B Unscheduled; D Scheduled inspection; E Hourly postflight/minor; P Major periodic/phased; R Depot; S Special inspection; T TCTO; Y Transient — [TO 00-20-2 App F](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Systems.**
  - REMIS (G099) subsystems: EIMSURS (inventory/status/utilization), PPS (MDD, equipment availability, aircraft debriefing) and GCSAS (configuration, TCTO).
  - CEMS (D042) is the "USAF standard data system for the tracking of Air Force Engine Status, Accountability, and Critical parts life tracking", with sub-systems D042A–G.
  - Source: [TO 00-20-2 §§2.2, 2.7, pp.2-1 to 2-8](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).

**US Navy/USMC — NAMP, COMNAVAIRFORINST 4790.2E (28 Oct 2024; public at NAVAIR)**
- [DIRECT] **The OOMA Work Order (WO), which replaces the paper VIDS/MAF (OPNAV 4790/60)**, records scheduled and unscheduled maintenance including "when and how the discrepancy was discovered". It also records corrective actions, parts, job status (In Work/AWM/AWP/Complete), man-hours and elapsed time, who performed and who inspected, readiness status (U/P/D, EOC/SCIR), removals/installations including cannibalization, and TD incorporation — [NAMP Ch 15 §15.1.2, p.15-1](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **WO data fields** (§15.3, pp.15-5 to 15-11):
  - MCN: 7-character tracking number.
  - JCN: 9 characters = 3-character ORG code + 3-digit Julian day + 3-character serial. Contingency JCNs may be 9, 10 or 11 characters.
  - Type WO (2 characters), ORG CODE, MODEX (side number), BUNO/SERNO (6 digits), ASSY CD/TEC, WORK CENTER, CF REQ, QA REQ.
  - TD fields (INTRM CD, CODE, BASIC NO, REV LTR, AMEND, PART, KIT NO), TURN-IN DOC.
  - WUC/UNS (7-position in OOMA, e.g., "2619370", "27DC200").
  - TRANS (2 digits), M/L (1 = O, 2 = I, 3 = D), ITEM PRC, ACTION TAKEN, MAL CODE (3 characters), DISC CODE, TYPE MAINT.
  - Removed/Installed item: CAGE, serial number (last 15 characters), part number (last 32 characters), date.
  - MAN HRS, ELAPSED HRS (EMT), RECEIVED/IN WORK/COMPLETED date-time, EOC, WO STATUS CD (U/D/P), METER, IN PROCESS INSP, SAFETY/EI, POSIT, FID, SYSTEM REASON.
  - (H-Z) Failed/Required Material (up to 19 failed-part records): A/T, MAL, CAGE, P/N, QTY, PROJ, PRI, DATE ORD, DDSN, DATE RCVD, NOMEN.
  - DISCREPANCY, CORRECTIVE ACTION, INITIATED BY, CORRECTED BY, INSPECTED BY, MAINT CONTROL.
  - Source: [NAMP §15.3](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Aircrew write-ups.** For discrepancies they discover (WD codes A, B, C, D, E, F, P), the pilot/aircrew initiates one WO per discrepancy, filling DISCREPANCY, PILOT/INITIATOR, RECEIVED date-time, BUNO, U/D/P and DISCOVERED CODE. Maintenance Control assigns the EOC per the type-specific Mission Essential Subsystem Matrix (MESM) — [NAMP §15.2.4.3(c), pp.15-3/15-4](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Narrative guidance with official examples.**
  - Discrepancy example: "Engine oil pressure fluctuating approximately 50 PSI while in afterburner…"
  - Corrective action must include the defect found, the actions taken, the publication used, "FOD/corrosion free", an operational/leak check statement and the PEMA serial number.
  - Source: [NAMP §15.3.6, pp.15-10/15-11](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Record lifecycle.** When Maintenance Control approves a completed WO, it stays in the Automated Aircraft Discrepancy Book (AADB) "for 10 subsequent flights". Completed WOs are kept locally for 12 months and then "in the DECKPLATE Aviation Data Warehouse (ADW) indefinitely". They are associated by BUNO and SERNO and transfer with the aircraft — [NAMP §§15.2.2(b), 15.2.6, pp.15-3/15-4](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Codes in Appendix E.**
  - Action Taken: A no repair required; B minor parts; C repair; D work stoppage (repair elsewhere); L AWP; N close-out; P removed; Q installed; R remove & replace; S remove & reinstall; T cannibalization; Y troubleshooting; Z corrosion; 0 look-phase. BCM 1–9 = beyond capability of maintenance reasons.
  - Awaiting Maintenance reasons: M1–M9, MF, CT.
  - Job status codes: e.g., IW, JC, WP, WQ, M3.
  - MAL codes are organised as corrosion C01–CE3, fiber optic F01–F06, wiring W00–W62, LO L01–L05, and three groups (Conditional/no-fault, Reason for Removal, Reasons for Failure). Examples: 799 "NO DEFECT - malfunction could not be duplicated, item checks good"; 922 "ENGINE MONITORING SYSTEM INDICATES OVERTEMP LIMIT EXCEEDED"; 320 compressor stalls; 916 JOAP; 812–818 cannibalization reasons.
  - TD codes, time/cycle prefix codes, TRANS codes, TEC/Assembly codes, Type Maintenance codes (including C "Predictive Maintenance"), Type WO codes, When Discovered codes, and Work Center codes.
  - Source: [NAMP App E, pp.E-1 to E-52](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Navy WD codes now include health-monitoring sources:** "I. Between Flights HMS Identified Fault … due to onboard (Aircraft) or off board (Ground Station) HMS identified fault", "N. NAE Data Analytics", and "R. QA Inspection" (which includes QA trend analysis of HMS data). Type Maintenance "C. Predictive Maintenance" is "executed prior to component functional failure" — [NAMP App E, pp.E-37, E-44/E-45](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Logbooks and records.**
  - Navy aircraft logbook forms: Monthly Flight Summary (OPNAV 4790/21A: flight hours MO/PERIOD/SINCE NEW, landings, arrested landings, catapults); Inspection Record (4790/22A); Repair/Rework (4790/23A); Technical Directives (4790/24A); Miscellaneous/History (4790/25A); Installed Explosive Device Record; Equipment Operating Record.
  - Component records: AESR (OPNAV 4790/29), Module Service Record, Assembly Service Record, EHR card and Scheduled Removal Component (SRC) card.
  - All are now maintained electronically as "Configuration Management Auto Log-set (CM ALS)".
  - Logbook dates use YYMMDD. Corrections are lined out (no correction fluid). O-level activities may not purge records.
  - Source: [NAMP Ch 8, §§8.2.7, 8.5, 8.6, pp.8-5, 8-18 to 8-21](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **On-board data in OOMA.** OOMA's "SMART Aircraft Module" strips onboard data by flight: "structure fatigue information, strain gauge data, engine LUI and diagnostics data, engine management system data, flight control system data, position data, avionics system data, fault codes, and component life time or cycle data". It offers debrief with an IETM and diagnostics/prognostics — [NAMP Ch 13, p.13-2](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).

**UK — MOD Form 700 series (MAA Manual of Airworthiness Maintenance – Documentation, MAM-D Part 1, Issue 5)**
- [DIRECT] **Raising a task.** "For each task, the person reporting the Fault, or detailing the work, is to raise an entry in the relevant Maintenance Log (ML) (eg MOD Form 707A)". Each arising gets a "Serial Number of Work (SNOW), coupled with the Serial Number of the Air System or work area and date … to create an Originating Reference Number (ORN)" — [MAM-D Part 1 Ch 2.2 §2.2](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf) ([publication page](https://www.gov.uk/government/publications/manual-of-airworthiness-maintenance-documentation-mam-d)).
- [DIRECT] **Serviceability state.** The technical log "(eg MOD Form 700) is to reflect the serviceability state of the Air System at all times". An aircraft is unserviceable if, for example, a limitation or deferred fault is due in the Limitations Log (F703) or the Acceptable Deferred Fault Log (F704), a component change or preventive task is due, an SI(T) is due, or "there is an open ML entry". Deferral moves an ML fault to the Limitations or ADF log. The "3rd signature" individual certifies completion — [MAM-D Ch 2.1 §§4–6](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf).
- [DIRECT] **MOD F700C binder sections:**
  - 1 Maintenance Log
  - 2 Limitations Log
  - 3 ADF Log
  - 4 Flight Servicing and Usage
  - 5 Forecast of Preventive Maintenance
  - 6 Weight and Moment
  - 7 Mechanical
  - 8 Avionic
  - 9 Role Equipment/Weapons
  - 10 Miscellaneous
  - 11 Index/Leading Particulars/MARC

  Minimum forms are F701 Leading Particulars, F702 W&B, F703 Limitations, F704 ADF, F705 Flight Servicing Certificate, F707A Aircraft Maintenance Log, F710 MARC, F713 Register, F721 Forecast and F724-726 Flying/Equipment Running Logs. Engineering Record Cards are held in F700D — [MAM-D Ch 3.1 §2.3, §4.1 Table 3, §2.4](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf).
- [DIRECT] **Component and repair records.** Removed items carry their faults and limitations onto the Equipment Conditioning Label (MOD F731). Repairs are recorded on the Maintenance & Repair Record Card (F745) or the component record cards (F749/F735 series). Modifications go on F746. Electronic IS (e.g., "GOLDesp") can generate Maintenance Work Orders (MWO) and "Default Processes" — [MAM-D Ch 2.1 §§2.5, 7–10](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf).
- [DIRECT] **Conventions.**
  - Erroneous entries are "ruled through and 'EinE' entered" (Entered in Error).
  - Pre-flight faults are worded "Pre-flight Maintenance to be carried out".
  - Admin entries are worded "For recording purposes only".
  - Lost records are replaced by duplicates marked "Duplicate Form" in red, under an F700Z certificate.
  - Source: [MAM-D Ch 2.1 §§14, 17; Ch 2.2 §2.2; Ch 3.1 §4.4](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf).
- [DIRECT] **US-sourced UK fleets** (C-17A, RC-135W) use MOD F707B(C17A) Maintenance Work Orders with USAF code systems: Work Type (= Type Maintenance), When Discovered (A, B, C, D, F, H, J, M, Q, 3, 5), How Malfunctioned and Action Taken, citing T.O. E00-01-0001-0x001 code TOs. Usage codes include Cycles/Counts/Fatigue Index, Landings (Arrested, Braked, Deck, Paved, Roller, Short, Vertical) and Starts — [MOD Form 799/5A(C17A) IFU (rev. May 26)](https://assets.publishing.service.gov.uk/media/6a313ea5141f0690ad5fa40e/799-5A_C17A_.pdf).

**IAF / HAL / Indian public descriptions**
- [DIRECT] **Maintenance Command.** IAF Maintenance Command (HQ Nagpur) "is responsible for all product support, maintenance, repair and overhaul of all variants of aircraft, vehicles, aero-engines, missiles, radars…". Stations have a Chief Engineering Officer (CEO) supervising "maintenance/ logistics activities", and Command HQs have a Senior Maintenance Staff Officer (SMSO) — [IAF Suo-Moto Disclosure, Jul 2025, paras 7(g), pp.~5–6](https://indianairforce.nic.in/Resources/pdf/utilities/SUO_MOTO_DISCLOSURE%20_JUL_2025.pdf).
- [DIRECT] **Air HQ maintenance organisation.**
  - AOM (Air Officer-in-Charge Maintenance) oversees DG (Aircraft), DG (Systems), ACAS (Maintenance Plans) and ACAS (Logistics).
  - ACAS (Eng A) handles Russian-origin fighters (MiG-21 variants, MiG-27, MiG-23UB, MiG-29, Su-30). ACAS (Eng B) handles non-Russian-origin fighters, vintage aircraft and RPAs, assisted by "PD Eng (J,M & LCA)".
  - Duties include "approve extension on aircraft servicing", liaison with "repair agencies (IAF BRDs / HAL Divisions / OEMs abroad)", and "Provisioning and procurement actions in case of AOG/ MCM/ PHU spares".
  - Source: [IAF RTI Handbook (updated 19 Apr 2023), AOM Branch, pp.~30](https://indianairforce.nic.in/Resources/pdf/utilities/RTI-Handbook-updated-as-on-19-Apr-23.pdf).
- [DIRECT] **ACAS (Maintenance Plans)** "is assisted by Air Cmde MP, Air Cmde Indg and Air Cmde eMMS/ CSDO". Its duties include "policy and procedure for monitoring and improving the reliability and maintainability of aircraft aero-engines, rotables", "long term maintenance plans for third and fourth line servicing", and policies on "publications and maintenance documents … TSI Vol I Leaflets and promulgation of TSIs, SIs, STIs and modification through routine order Pt-III". ACAS (Logistics) is responsible for "Implementation of IMMOLS in Air Force"; the glossary expands IMMOLS as "Integrated Material Management On Line System" — [IAF RTI Handbook, ACAS (MP) and ACAS (Lgs) sections and glossary](https://indianairforce.nic.in/Resources/pdf/utilities/RTI-Handbook-updated-as-on-19-Apr-23.pdf).
- [DIRECT] **Maintenance levels in IAF terms.** "Ist line servicing ('O' level maintenance), IInd line servicing ('I' level maintenance), and IIIrd & IVth line servicing ('D' level maintenance)".
  - O-level is at the flight-line parking area, with "fault detection and isolation down to Line Replaceable Unit (LRU)".
  - I-level is at the base lab/shop and isolates the faulty SRU within the LRU.
  - D-level repairs/overhauls SRUs "either by vendor or Base Repair Depot (BRD)".
  - Source: [CAG Report No. 38 of 2015 (Air Force), para 2.1.3, pp.20–21](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf).
- [DIRECT] **IAF documentation and schedules named by CAG:** "Schedules of maintenance for first and second line servicing", "Scales of Tools, Testers and Ground Equipment (TTGE)", "Recovery Plan of aircraft from Aircraft on Ground (AOG)", "Indian Air Force Publications (IAP) 1501, 1502 and 1541", and "engine log books" — [CAG Report No. 24 of 2017 (Air Force), para 2.7, pp.31, 39](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf).
- [DIRECT] **HAL ROH for the LCA.** The ASR made the manufacturer responsible for "defect investigation, repair and overhaul". Of LCA's 344 LRUs, "90 LRUs were considered non-repairable", ROH existed for 185, and 69 were pending. HAL planned an LTRA (long-term repair agreement) for 29 LRUs and ROH for 39. CAG also cites "delay in snags analysis, slow recovery of aircraft from rectification, shortage of critical LRUs at flight hangar" — [CAG Report No. 17 of 2015 (LCA), paras 4.2.2, 4.4, pp.40, 47](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
- [DIRECT] **Inventory and audit data.** CAG noted "a computerised inventory management system" in IAF stores (2014) and listed "AFNET and IMMOLS" as protected assets (2016). A "Discrepancy Report (DR)" is the mechanism for supplier defects, with BRD time limits — [CAG 34 of 2014 §3.7.6.1](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2014/Union_Compliance_Defence_Air_force_Navy_34_2014.pdf); [CAG 18 of 2016, Ch 5 table](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2016/Union_Defence_Services_Air_Force_Report_No_18_of_2016.pdf).
- [DIRECT] **Doctrine.** IAF doctrine says "enterprise level digitisation drives the techno-logistics" and names "Equipment maintenance" as a force-sustenance process — [IAF Doctrine (2022), Foreword and pp.~79–83](https://indianairforce.nic.in/Resources/pdf/header/latest-Doctrine-22-Feb.pdf).

### Inferences
- [TRANSFER: RAF/UK MOD F700 → IAF] The IAF's vocabulary — "1st–4th line servicing", TETTRA (type training), AFOs/IAPs/TSIs, "snags", "DR" — matches RAF heritage. A MOD Form 700-like structure is therefore the most plausible template for IAF aircraft technical records:
  - a fault/maintenance log with unique serial numbers
  - a deferred-defect log
  - a limitations log
  - a flight servicing certificate
  - forecast logs
  - component record cards

  Limit: the IAF form numbers, block names and code lists are not public. The generator should label IAF-style fields generically (e.g., "Snag No.", "Line of Servicing") and avoid inventing official form numbers.
- [TRANSFER: USN NAMP / USAF 00-20-2 → IAF] For the coded layer (WUC/When-Discovered/How-Mal/Action-Taken/Type-Maint), the USN and USAF tables are the best-documented public schemes. They map cleanly to S5000F/S1000D concepts (Q2). Use them as structural templates, relabelled as "Phalanx code tables". Limit: IAF code values are unknown, and Russian-origin fleets (Su-30MKI) likely follow different OEM documentation [ASSUMPTION].
- [ASSUMPTION] The IAF "eMMS" (Air Cmde eMMS/CSDO under ACAS MP) is probably an e-Maintenance Management System. Its data model is not public. Combined with IMMOLS (materials) this gives exactly the "fragmented systems" the PS describes. The Phalanx generator can emit two linked but separately-keyed streams — maintenance (eMMS-like) and materiel (IMMOLS-like) — joined only through demand/document numbers and tail/serial numbers.

### Gaps
- No public IAF form layouts (Form 700 equivalents, servicing schedules, engine log book format) or IAF code tables were found. IAP 1501/1502/1541 are cited by CAG but are not public.
- No public description of eMMS functionality, or of HAL's ROH documentation (e.g., overhaul work cards, "Aircraft History Book"), was found.
- CEMILAC/DGAQA records (defect investigation reports, airworthiness concessions) could not be accessed. DRDO/DGAQA pages returned 404 or were unreachable.
- The DAFI 21-101/21-103 primary text was not read (403). USAF status-code definitions were taken from GAO (Q2).

---

## Q2. Standards for maintenance/in-service data and reliability/availability metrics

### Takeaway
**S5000F (ASD/AIA)** is the publicly downloadable in-service feedback standard. Its data model (Event, MaintenanceEvent, ExplanatoryFactor, LogBookEntry, DownTimePeriod, DetectionMechanism with a false-alarm rate, the NFF report, and UC50403 "Report maintenance performed") is a ready-made schema for Phalanx's linked records.

Availability metrics are defined precisely:
- **Navy:** 15-minute "SCIR binning", with NMCD > NMCS > NMCM-U > NMCM-S > PMCS > PMCM precedence, and MC/FMC computed over Equipment-In-Service hours.
- **USAF:** MTBF-1/2, MTBM-6, CND/BCS/RTOK, CANN and abort/break/fix rates as explicit algorithms over coded MDD records.
- **IAF:** "serviceability" percentage against a target (e.g., 70% for IL-76/78).

### Cited Findings
- [DIRECT] **S5000F structure.** S5000F Issue 4.0 (2024-04-30) covers in-service data feedback chapters for:
  - RAMCT (reliability, availability, maintainability, capability, testability) analysis (Ch 3)
  - maintenance analysis (Ch 4)
  - safety (Ch 5)
  - supply (Ch 6)
  - LCC (Ch 7)
  - warranty (Ch 8)
  - "Product health and usage monitoring" (Ch 9)
  - obsolescence (Ch 10)
  - fleet management (Ch 11)
  - software (Ch 12)
  - configuration (Ch 13)
  - contracts (Ch 14)
  - in-service environment (Ch 15)
  - data model/exchange (Ch 24–26)

  Source: [S5000F Issue 4.0, Chap 1 §4](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf) ([downloads](https://www.s-series.org/s5000f/downloads/)).
- [DIRECT] **S5000F Event class.** Attributes: eventIdentifier, eventOcurrenceDateTime [sic], eventGroup, eventSeverity, eventDescription, eventConfirmedStatus. Associations: EventAffectedBreakdownElement, DownTimePeriod, LogBookEntry ("An Event instance can be optionally logged in a LogBookEntry"), ExplanatoryFactor (examples "explosion", "human error", "strong lateral wind"), EventReporter and ProductUsagePhase. MaintenanceEvent inherits these attributes and adds maintenanceEventCategoryType — [S5000F Chap 24, §§4.52.3.2, 4.52.3.9, 4.114.3.6](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf).
- [DIRECT] **S5000F DetectionMechanism** has detectionMechanismType (e.g., BIT) and "detectionMechanismFalseAlarmRate", linked to FailureDetection. The "ReportMaintenancePerformed" exchange (UC50403) aggregates:
  - MaintenanceEvent, Event, Action, ExplanatoryFactor
  - SerializedHardwarePart, SerializedProductVariant
  - TaskRequirement, TechnicalOrder, ServiceBulletin
  - MaintenanceOrganization, MaintenancePerson, MaintenanceLevel, Facility
  - DamageAnalysis, DigitalFile, WorkItem, ZoneElement, WarrantyEvent, among others

  Source: [S5000F Chap 24 §4.57.3.3; Chap 24.5 Fig 15, p.20](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf).
- [DIRECT] **S5000F BIT and NFF definitions.**
  - BIT types: "(a) power-on built-in tests (P-BIT) … (b) continuous built-in tests (C-BIT) … (c) initiated built-in tests (I-BIT), executed upon order from the operator or from the maintenance team".
  - No Fault Found: "the item is sent for repair with a report of failure but subsequently it is not possible to reproduce or detect the reported failure".
  - Repair shops must issue an "NFF report" including "the inspection and test performed".
  - HUMS chapter: records should cover "error or fault codes and descriptions", component and system functional status, usage profile and operating parameters. It also notes "HUMS could detect false alarms".
  - Source: [S5000F Chap 30 definitions; Chap 4 §4.7; Chap 9 §§1–3.5](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf).
- [DIRECT] **Sister S-series specifications.** S3000L is the Logistic Support Analysis specification with "a detailed UML model and schema". S4000P covers preventive maintenance, with "In-Service Maintenance Optimization (ISMO) methodology to review and adjust preventive maintenance plans based on usage data". S1000D (jointly ASD/AIA/ATA) is the technical-publications specification — [s-series.org S3000L](https://www.s-series.org/s3000l/), [S4000P](https://www.s-series.org/s4000p/), [S1000D](https://www.s-series.org/s1000d/).
- [DIRECT, civil] **ATA 100/iSpec 2200 chapter numbering** (CC-SS-SS). Examples: 21 Air Conditioning, 24 Electrical Power, 27 Flight Controls, 28 Fuel, 29 Hydraulic, 31 Indicating/Recording, 32 Landing Gear, 34 Navigation, 45 Central Maintenance System, 49 APU, 71 Power Plant, 72 Engine, 73 Engine Fuel and Control, 75 Bleed Air, 76 Engine Controls, 77 Engine Indicating, 79 Oil, 80 Starting. This is a secondary source — [Wikipedia "ATA 100"](https://en.wikipedia.org/wiki/ATA_100). The FAA's JASC codes in the SDRS lookup tables use the same 4-digit chapter scheme (e.g., 7200 Engine, 7700 Engine Indicating, 7900 Oil) — [FAA SDRS Look-Up Tables (JASC)](https://sdrs.faa.gov/Documents/SDRS%20Look-Up%20Tables.zip).
- [DIRECT, civil] **MSG-3/MRB.** FAA AC 121-22D describes "the MSG-3 process" through which the OEM/TCH produces the MRBR. Failure Effect Categories "5 and 8 safety tasks" require verification — [FAA AC 121-22D §§8.1, 10.2](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_121-22D.pdf).
- [DIRECT, civil] **AC 120-17B reliability programs.**
  - Data types: aircraft maintenance log (mechanical irregularities), IFSD, operational interruptions, unscheduled component removals, shop findings, MEL deferrals, chronic systems, aircraft and engine health monitoring, SDRs, flight logs.
  - Data quality requires recording standards, data audits, feedback, and "A common coding convention … to correlate mechanical irregularities … with defects found during routine maintenance tasks, shop teardown reports".
  - Definitions of NFF, "Rogue Units" (same serialized LRU, identical faults, repetitive unscheduled removals) and "Chronic Units/Systems".
  - Alert levels are set by standard deviation or Poisson methods.
  - Source: [FAA AC 120-17B, Ch 3 Table 3-1, §3.3, §4.1, §5.1.1](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_120-17B.pdf).
- [DIRECT] **USAF standard algorithms (TO 00-20-2 App L).**
  - Inherent failures (Type 1) = on-equipment records with How-Mal class 1 and ATC F/K/L, or P/R with no related off-equipment "B" (bench-check serviceable).
  - MTBF-1 = flying hours × QPA × UF / inherent failures. "MTBF-1 is the mean time between a verified failure. All bench check serviceables are subtracted out. No cannot duplicates are included".
  - MTBM-Total uses Type 1+2+6 actions.
  - CND = on-equipment ATC "H" with HMC 672/799/812/948; CND rate = CND/total actions × 100.
  - BCS rate, RTOK rate, NRTS and condemnation rates are defined similarly.
  - CANN rate = CANNs/sorties × 100.
  - Abort air = debrief deviation code "AA" or "AI"; abort ground = "GA". BREAK = debrief landing status code "3". 4/8/12-hour fix rates are also defined.
  - MTBR, removals/1000 FH and MTTR are included.
  - Source: [TO 00-20-2 App L, pp.L-1 to L-19](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Navy readiness definitions and rates.**
  - SCIR definitions: NMCD, NMCS (awaiting parts), NMCM-U, NMCM-S, PMCS, PMCM, FMC. EMT, AWM and AWP are maintenance-time components, and "SCIR GRIPE LIFE = AWP + EMT + AWM". Unaccounted time becomes "Computer Generated AWM (AWM 0)".
  - "Data binning reduces overall aircraft status into 15-minute increments of the highest degraded priority": NMCD > NMCS > NMCM-U > NMCM-S > PMCS > PMCM.
  - MC% = (EIS hrs − (NMCD+NMCS+NMCM)) / EIS × 100. FMC% additionally subtracts PMCS and PMCM.
  - Worked example: 12 aircraft, April, EIS = 7,680 h, MC 62.5%, FMC 30.0%.
  - EOC codes (C–K degrade to PMC; L = no IMC flight; Z = down) are prefilled from the WUC via the MESM.
  - Source: [NAMP §§9.2–9.4, pp.9-29 to 9-37](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **US DoD common metrics:**
  - "Mission capable rate. The percentage of total time when an aircraft possessed by a squadron can fly and perform at least one mission."
  - NMCM: not capable of any mission because of maintenance.
  - NMCS: not capable because of "lack of a repair part".
  - The Air Force also measures aircraft availability and NMC for both supply and maintenance. "Total not mission capable supply" includes NMCS plus NMC-both.
  - The F-16 met its MC goal in 0 of 11 fiscal years (FY2011–21): 936 aircraft, 160,116 FH in FY2020, average lifetime 7,357 h (C) and 6,604 h (D).
  - Source: [GAO-23-106217, pp.6–7, 232, and KC-10 page](https://www.gao.gov/assets/gao-23-106217.pdf).
- [DIRECT] **F-35 rates:** fleet mission-capable rate "stood at about 55 percent in March 2023"; military depots repaired components "on average, in 72 days" (the program goal is 60–90 days) — [GAO-23-105341, pp.11–13](https://www.gao.gov/assets/gao-23-105341.pdf).
- [DIRECT] **IAF serviceability concept and values.** "Serviceability denotes that the aircraft are airworthy…" The desired IL-76/IL-78 serviceability is "70 per cent". Actual 2010–16 averages were 38% (IL-76) and 49% (IL-78); on average 41% and 32% respectively were grounded. Serviceability of the IL-78 aerial refuelling pods ranged 43.25–66.67% — [CAG 24 of 2017, para 2.7.4 and 2.7.3(f), pp.34–36](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf).
- [DIRECT] **Testability/false-alarm definitions.** "FALSE ALARM: A fault indicated by BIT or other monitoring circuitry where no fault can be found or confirmed." "The two most commonly reported symptoms of false alarms are CND and RTOK." Causes include environmental factors, diagnostics design, degradation, tolerances and maintenance-induced factors (connectors, wiring). The USAF Time Stress Measurement Device records environmental stress around anomalies to reduce RTOK/CND — [MIL-HDBK-338B, Definitions and §7.x testability, pp.~ definitions; text at "False alarms"](https://everyspec.com/MIL-HDBK/MIL-HDBK-0300-0499/MIL-HDBK-338B_15041/).

### Inferences
- [TRANSFER: S5000F → Phalanx/IAF] S5000F is a NATO-neutral ASD/AIA standard and is freely downloadable. It is an appropriate canonical schema for Phalanx's linked records:
  - telemetry anomaly → Event (eventGroup = HUMS/BIT, eventSeverity)
  - pilot debrief → Event with EventReporter
  - work order → MaintenanceEvent + Action, with TaskRequirement = FIM/IETM task
  - part swap → SerializedHardwarePart removal/installation
  - shop finding/NFF → NFF report
  - downtime → DownTimePeriod

  Limit: the IAF has not publicly adopted S5000F. It is a design choice, not an IAF fact.
- [TRANSFER: USN SCIR binning → IAF availability] The 15-minute precedence binning gives a deterministic, auditable way to compute availability from synthetic job states. The IAF's public KPI is "serviceability %" of the held/available fleet. Phalanx should compute both a SCIR-style MC/FMC and an IAF-style serviceability %, and document the mapping as an assumption.
- [TRANSFER: USAF App L → Phalanx metrics] The coded-record algorithms (CND rate, BCS/RTOK, MTBF-1 excluding CND/BCS) imply that the generator must emit linked on-equipment and off-equipment (shop) records with consistent WUC and JCN. Otherwise downstream reliability metrics cannot be reproduced.

### Gaps
- The ATA Spec 2000 Chapter 11 record layouts (reliability data exchange) are paywalled; no public field list was obtained.
- The MIL-STD-1388-2B LSAR data tables could not be fetched (an EverySpec link guess returned 404). S3000L (downloadable from s-series.org) is the modern successor in practice, but its LSA tables were not reviewed in depth.
- MSG-3 logic details (the decision diagram and FEC 5–9 definitions beyond "5 and 8 safety") come from the ATA document, which was not accessed.
- DAFI 21-103 definitions of NMCB/PMCB/TNMCM formulas were not verified from the primary source (403). Only the GAO paraphrase is used.

---

## Q3. BIT and fault reporting; health monitoring; false alarms/NFF; F-35 PHM/ALIS/ODIN

### Takeaway
BIT exists in three standard flavours (P-BIT, C-BIT, I-BIT). Fault codes flow into maintenance documents as narrative and/or a dedicated field, with "primary" plus additional codes.

Navy policy now explicitly ties HMS BIT/CI (condition indicator) data to Work Orders:
- When-Discovered "I" for HMS-identified faults, "N" for fleet analytics, and "R" for QA trend analysis.
- Type Maintenance "C" for predictive maintenance.
- A last-10/last-50-flight trending regime.

The F-35 supplement documents an explicit **false-alarm workflow**: suspected Health Reporting Code (HRC) false alarms are "deferred and monitored for three (3) consecutive flights", and nuisance codes go to filter lists. Quantitative fighter-fleet NFF/false-alarm rates were **not** found in accessible public sources. One IAF test-equipment example shows large false-fail fractions.

### Cited Findings
- [DIRECT] **BIT definitions** — see S5000F above (P-BIT/C-BIT/I-BIT) — [S5000F Chap 30](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf).
- [DIRECT] **USAF BIT recording.** "Systems that have BIT fault reporting will report fault codes (primary if multiple codes) in block 16 of the AFTO Form 349, the appropriate field of an automated system, or in the discrepancy narrative" — [TO 00-20-2 §4.29, p.4-12](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/). How-Mal codes 644/672–676 distinguish BIT-indicated faults, false alarms, wrong-unit indications and not-duplicated faults with or without data confirmation — [TO 00-20-2 App G, p.G-6](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Navy HMS (NAMPSOP 10.37, ATA = Automated Trending and Analysis).**
  - HMS "produce Built In Test/Condition Indicator (BIT/CI) data in numeric codes, such as the F/A-18 and EA-18 Automated Maintenance Environment (FAME) Maintenance Status Panel codes, or as actual performance numbers, such as the vibration readings" of H-60 IMDS/HUMS.
  - Trend reports include "BIT/CI Logic Inspection (BLIN) and BIT Operational Accumulative (BOA)".
  - Health monitoring systems by type: F-35 → ALIS; KC-130J → DTADS; P-8A → GHMS; E-2D → ALE; MV-22 → CAMEO.
  - Source: [NAMP §10.37.2, pp.10-429/10-430](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Navy HMS procedures.**
  - Maintenance Control "Review HMS BIT/CI data after return from each flight and issue Work Orders (WO) with appropriate Equipment Operational Capability (EOC) code … A detailed description of the malfunction and the associated HMS BIT/CI code(s) … must be annotated in the WO discrepancy block".
  - Maintenance Control keeps the last 10 flights of HMS data with the ADB. QA compiles and trends "the last 50 flights for each BUNO".
  - QA looks for "High rate of HMS BIT/CI fault code(s) per flight hour", high WD A/C abort rates, and components with high "Action Taken Code A with Malfunction Code 799 (no defect)".
  - Removals of components flagged as substandard performers must begin "WRA is listed as a substandard performer on ATA Report (month and year…)" and include flight hours and sorties since installation.
  - Source: [NAMP §10.37.4, pp.10-435/10-436](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Navy fleet-level HMS metrics** (quarterly ATA reports):
  - MTBF of systems by BUNO, WRAs by NSN/SERNO and SRAs
  - "Flight Hours Between Critical System BIT/CI Indication (FH/BIT set rate)"
  - flights between BIT/CI indications
  - flight hours between WD A/B/C/D events
  - flight hours between removals
  - average time to repair
  - average AWP time
  - "average number of maintenance actions between repair attempts"
  - A "Bad Actors" program per MIL-STD-1798

  Source: [NAMP §10.37.3.1.1(c),(g), pp.10-432/10-433](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Official F/A-18E/F-style WO examples** (example data, not real records) show MSP codes in discrepancies:
  - "MSP 646 L CHANNEL A FADEC TERMINAL FAIL POPPED DURING LPT" → corrective "REMOVED AND REPLACED FADEC. CONDUCTED LPT CODE CLEARED OP CHECK GOOD…". Coded WUC 27DC100, TRANS 25, AT R, MAL 956, Disc H.
  - "FADEC ADVISORY ON DECK THAT WOULD NOT CLEAR… CHANNEL B FAULT CODES 009 078 304" → main fuel control replaced, EOC Z (down).
  - "JAMMER DEGD AFTER BIT AIRBORNE. MSP 410, LOW BAND RECEIVER FAIL." → "RESEATED … SYSTEM CHECKS GOOD ON DECK IAW IETM".
  - Source: [NAMP Figs 15-7, 15-8, 15-41, pp.15-80, 15-81, 15-114](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **F-35 HRC handling (NAMP F-35 supplement).**
  - "Post-flight Vehicle System Built in Test (VS BIT) check will be performed and all HRCs reviewed prior to releasing the aircraft SFF", per the HRC Significant List.
  - "For suspected HRC false alarms, the WO is deferred and monitored for three (3) consecutive flights … If no maintenance is performed, the maintenance event is administratively closed and will be FID coded as 'D40' with a How Malfunction Code (HMC) of '000' and Action Taken Code (AT) of 'O'."
  - Nuisance HRCs go to a "Nuisance Filter List (NFL)", "Conditional HRC Anomaly List" or "HRC Correlation Filter List as sympathetic HRC".
  - HRC = "An alphanumeric representation detailing a reportable fault, status or event".
  - Life-limited part "holes with Electronic Equipment Log (EEL) Alerts" block release.
  - Source: [COMNAVAIRFORINST 4790.35D (19 Oct 2023), §§5.1.6, 15.2.4, App A](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/4790.35D.pdf).
- [DIRECT] **F-35 ALIS architecture and data quality.**
  - The SOU server is the squadron node.
  - The Portable Memory Device ("brick") stores "mission and maintenance data generated during flight"; a PMD reader unloads "maintenance data, including health-related codes"; the PMA laptop is used to "perform and document maintenance activities".
  - Electronic Equipment Logbooks carry "part history and remaining life (hours)". Aircraft must be "electronically 'complete'" to fly.
  - Source: [GAO-20-316, pp.8–9, 14](https://www.gao.gov/assets/gao-20-316.pdf).
- [DIRECT] **ALIS to ODIN.** DOD renamed ALIS as ODIN; as of April 2022 "the transition date from ALIS to ODIN is undetermined" — [GAO-23-105341, App. recommendations status](https://www.gao.gov/assets/gao-23-105341.pdf); [GAO-20-316 product page](https://www.gao.gov/products/gao-20-316).
- [DIRECT] **Cockpit alerts versus recorded health data (UK F-35B ZM152 Service Inquiry).**
  - The integrated caution, advisory and warning (ICAW) system showed no engine alerts.
  - Inlet debris monitoring data "was recorded for subsequent aircraft health analysis, but not displayed to the pilot".
  - Air flow was 6% low and compressor exit pressure 30% below nominal, so FADEC cut core fuel flow by 32% "and therefore did not raise any cautions or warnings". The panel found the "lack of an appropriate warning to the pilot was a contributory factor".
  - Source: [UK DSA SI F-35B ZM152, paras 1.4.117–1.4.125](https://assets.publishing.service.gov.uk/media/651d73e4e4e658001459d95d/Service_Inquiry_into_the_loss_of_F-35B_Lightning_ZM152__BK-18_.pdf).
- [DIRECT, civil] **Alert hierarchy** (14 CFR 25.1322):
  - "Warning: … immediate flightcrew awareness and immediate flightcrew response"
  - "Caution: … immediate … awareness and subsequent … response"
  - "Advisory: … awareness and may require subsequent … response"
  - Colours: red for warning, amber/yellow for caution.
  - The alert function must "minimize the effects of false and nuisance alerts".

  Source: [14 CFR §25.1322](https://www.ecfr.gov/current/title-14/part-25/section-25.1322).
- [DIRECT] **IAF test-equipment false fails.** Of 130 LRUs tested on an IAF Communication ATE, "94 LRUs did not match the ATE test pattern, though LRUs were serviceable". Air HQ said test limits "were stringent". As a result, "complete LRU had to be sent to OEM … resulting in longer turn-around time" — [CAG 38 of 2015, para 2.1.3.2, pp.24–25](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf).

### Inferences
- [TRANSFER: USN NAMP / F-35 → IAF/Phalanx] Telemetry-derived events should create work orders in **two distinct ways**:
  1. **Aircrew-reported**, with WD A–E: free text, cockpit-message wording, U/P/D status.
  2. **Data-reported** at post-flight download, with WD "I"-equivalent (HMS fault) or "N"-equivalent (analytics): text quoting BIT/HRC codes, and Type Maint "C" if predictive.

  Limit: IAF code letters unknown. The same physical fault can, and often should, produce both a pilot write-up and a BIT-code WO. This creates the duplicate-entry phenomenon that TO 00-20-1 tells writers to avoid.
- [TRANSFER: F-35 HRC workflow → Phalanx] Model false alarms as a **state machine**:
  - HRC/BIT raised → WO opened → deferred and monitored for N flights.
  - If no recurrence → administrative close (CND/no-defect code).
  - If recurrence → troubleshooting (AT "Y") → part swap.
  - Nuisance codes are eventually suppressed by a filter-list software update.

  This reproduces realistic CND/A-799 rates without inventing numbers.
- The F-35B case shows Phalanx must allow **anomalies that never reach the cockpit** (health data recorded but no ICAW) as well as **cockpit cautions without underlying faults** (false alarms). These are two separate error modes.

### Gaps
- **No accessible public numeric NFF/CND/RTOK or BIT false-alarm rates for F-16, F/A-18, Gripen, Su-30MKI or Tejas fleets were found.** DOT&E F-35 reports (which give HRC/false-alarm statistics) returned 403. Peer-reviewed NFF studies (e.g., Söderholm 2007; Khan et al. 2014) were not accessible. Phalanx should treat NFF fraction as a tunable parameter, documented as an assumption.
- F-16 Pilot Fault List/Maintenance Fault List formats, F/A-18 nose-wheel-well DDI/MSP logic tables, Gripen RM12 and Su-30MKI BIT outputs: no public primary source was accessed. Only the NAMP's mention of "FAME Maintenance Status Panel codes" and three example MSP numbers were found.
- ARINC 604/624 central maintenance computer specifics are paywalled. ATA chapter 45 "Central Maintenance System" exists in the numbering, but no field-level content was found.

---

## Q4. Style of real entries (pilot write-ups, corrective actions, logbooks) and public corpora

### Takeaway
Real entries are:
- **Uppercase and terse**, heavy with abbreviations: R/R, IAW, OP CK GOOD, CND, FOD, PEMA, IETM, L/H, R/H, #2 ENG, CHKD, SN/S/N.
- **Reference-laden**: publication or task numbers, part and serial numbers, PEMA/tool serial numbers.
- **Formulaic** in close-out wording: "AREA FOD FREE AND SECURED", "OPS CHECK GOOD", "IAW".
- **Imperfect**: misspellings and run-on errors appear even in official examples.

Pilot write-ups describe the symptom and context (phase of flight, power setting, cockpit message or code). Corrective actions describe the finding, the action, the reference and the check. Public corpora (MaintNet aviation logbooks, FAA SDRS, NASA ASRS) give civil text texture. Official NAMP/USAF guidance gives the military canon.

### Cited Findings
- [DIRECT] **Official Navy WO examples** (verbatim short fragments from NAMP figures):
  - Discrepancy "IGB CHIP LIGHT CAME ON DURING FLIGHT." → corrective "…A SINGLE STEEL (MAGNETIC) CHIP WAS FOUND. CHIP IS WITHIN LIMITS. PERFORMED FULL DRAIN AND FLUSH… PERFORMED ONE HOUR PENALTY TURN. NO FUTHER CHIPS FOUND." Coded AT Y, MAL 185, Disc C, TM B, Man-hrs 11.0, Elapsed 3.0. Note the misspelling "FUTHER" in the official example.
  - Cannibalization corrective: "REMOVED AND REPALCED BEACON RECEIVER WITH SN: TXJ00041. BEACON RECEIVER BIT GO IAW IETM." Note "REPALCED".
  - Source: [NAMP Figs 15-6, 15-12, pp.15-79, 15-85](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **More official examples:**
  - "AFT AVIONICS COOLING FAN FILTER CLOGGED." → "REMOVED AND REPLACED … IAW IETM. AREA FOD FREE AT TIME OF INSPECTION. PEMA S/N: …" (phase fix: Type WO PF, Disc M, TM G).
  - "REPLACE OBOGS CONCENTRATOR DUE TO HI-TIME" (MAL 804, Disc O).
  - "CORROSION ON THE CARGO HOOK THRUSTER MOUNTING PLATE…" (MAL C73, Disc Q, TM S).
  - TD compliance: "COMPLIED WITH AYB-1638 TO INSPECT RESCUE HOIST HOOKS … CHECKS GOOD. AREA FOD FREE AND SECURED."
  - Source: [NAMP Figs 15-29, 15-33, 15-36, 15-48, pp.15-102, 15-106, 15-109, 15-121](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **USAF canonical phrasings:**
  - "OP CK GOOD"/"OP CK BAD"
  - "FCF completed, aircraft released for flight."
  - "Cannot Duplicate Malfunction" or "CND"
  - "PCW, see forms dated FROM___, TO___"
  - "Symbol upgraded to a Red X, see page ___, item ___"
  - Warning notes such as "NOTE - DO NOT APPLY ELECTRICAL POWER TO FUEL SYSTEM - FIRE HAZARD"
  - Partial-work entries such as "…steps 1 thru 25 CW IAW 1C-5B-5-5JG-2…" and "…steps 26 thru 30 NCW"
  - Source: [TO 00-20-1 §§4.6, 5.4, 5.7.3.16.4, 5.7.3.16.7, 5.7.3.19](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).
- [DIRECT] **USAF minimally acceptable corrective-action language** lists phrases like "hardware loose - replaced minor hardware on (item)" and "(item) had no output - bench checked and repaired". Work-in-progress close-outs ("Bench check in progress", "troubleshooting (item)") go with 00 units — [TO 00-20-2 §4.14.2](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **UK conventions.** ML/MWO columns are "Work Required"/"Work Done". Stock phrases include "Pre-flight Maintenance carried out on [system], no further flight servicing required" and "For recording purposes only". Errors are marked "EinE" — [MAM-D Ch 2.1 §§14, 17; Ch 2.2 §2.2](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf).
- [DIRECT, civil] **MaintNet aviation dataset** (University of North Dakota aviation program): 6,169 instances, 76,866 tokens. Example issue/action pairs:
  - "CAP SCREWE MISSING, L/H ENG #4 BAFLE" → "INSTALLED NEW SCREW. CHKD ENG"
  - "#3 FWD PUSH ROD TUBE GSK LEAKING @ EGNINE" → "REMOVED & REPLACED #3 FWD PUSH ROD TUBE SEALS…"

  In a 200-document sample, 97 of 106 unique tokens were "non-standard". Off-the-shelf spellcheckers corrected only 12–59%; a domain Levenshtein method reached 97%. MaintNet also hosts FAA "Safety" (25,558 instances) and "Accident" (5,268) text sets — [Akhbardeh, Desell & Zampieri, MaintNet (arXiv 2005.12443), Tables 1–3](https://arxiv.org/abs/2005.12443).
- [DIRECT, industrial] **NIST Technical Language Processing.** Maintenance work orders are "the 'clinical notes' of an asset". They contain "(a) messy, unstructured raw text; and (b) inconsistent, incomplete, incorrect, or missing codes and data formats". Examples include "Hyd leak at saw atachment. Hydromat Saw 012, hydpump not working; rep with new HS012." Standard NLP fails on such text, e.g., stemming fails to merge "hyd"/"hydraulic", and a negation can be lost so that "pump WAS working" is output — [Brundage et al., Manufacturing Letters 2021 (NIST pub 931138), §§1–2, Table 1](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=931138) ([NIST page](https://www.nist.gov/publications/technical-language-processing-unlocking-maintenance-knowledge)).
- [DIRECT, civil] **FAA SDRS coded fields** (lookup tables):
  - How Discovered: B Boroscope, C Functional Check, E Eddy Current, V Visual, X X-Ray…
  - Nature of Condition: A Flame/Fire, E Vibration/Buffet, J Warning Indication, M Over Temp, N False Warning, R Partial RPM/PWR loss, X Engine Flameout…
  - Precautionary Procedure: A Unsched Landing, C Aborted Takeoff, E Engine Shutdown…
  - Stage of Operation: TO, CL, CR, DE, AP, LD, TX, IN (insp/maint)…
  - Part Condition: 340 terms (e.g., CHAFED, COKED, CRACKED, CORRODED)
  - Time Since code: O/R/I
  - JASC system codes
  - Source: [FAA SDRS Look-Up Tables (2026-07)](https://sdrs.faa.gov/Documents/SDRS%20Look-Up%20Tables.zip); [AC 20-109B §13](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-109B_FAA.pdf).
- [DIRECT, civil] **NASA ASRS** holds de-identified narratives from "pilots, controllers, mechanics…" plus analyst-coded fields, and exports to CSV/XLS — [NASA ASRS Database Online](https://asrs.arc.nasa.gov/search/database.html).
- [DIRECT] **UK servicing narrative style** (Service Inquiry). Example: "Eng 1 started the engine elements of the servicing at 21:13 … removed the right intake blank"; "at 03:29 signed for completion of their aspects of the POS/BOS"; and the discovery in the "Red Gear log" that "there was no entry for the fitting of blanks" — [UK SI F-35B ZM152, paras 1.3.54–1.3.64](https://assets.publishing.service.gov.uk/media/651d73e4e4e658001459d95d/Service_Inquiry_into_the_loss_of_F-35B_Lightning_ZM152__BK-18_.pdf).

### Inferences
- [TRANSFER: USN/USAF/civil → IAF] The IAF is English-language with RAF heritage, so it likely uses similar terse uppercase snag text with IAF-specific abbreviations (e.g., "snag", "u/s", "R&R", "IAW TO/IAP", "FOD check carried out"). Limit: no public IAF snag-text corpus was found. Text generators should be configurable, and IAF wording should be validated with domain experts.
- To imitate realism, generate text from templates with:
  1. symptom + condition + code (pilot)
  2. finding + action + reference + check + housekeeping phrase (maintainer)
  3. controlled noise: misspellings around 1–5% of tokens [ASSUMPTION], abbreviation variants, occasional missing reference, and P/N transposition (the NAMP Fig 15-11 example shows removed P/N 70400-08163-043 versus installed 70400-08613-043, likely a transposition [ASSUMPTION]).

### Gaps
- USAF Accident Investigation Board reports, which quote AFTO 781 entries, could not be accessed (afjag.af.mil 403), so no verbatim F-16 781A entries were extracted.
- The Hawk T1 XX189 and Tornado ZA557 Service Inquiries are scanned images (no text layer). OCR was not performed.
- No public IAF pilot-snag or engine-log text examples were found.

---

## Q5. Data linkage, configuration status, supply/CANN, maintenance levels and flows, time-lags and data quality

### Takeaway
Records link through a small set of keys:
- aircraft ID: tail/BUNO/serial/MODEX
- job ID: JCN/MCN/SNOW-ORN
- component ID: CAGE + P/N + S/N, with time/cycle prefix values at removal and installation
- supply ID: document number, DDSN, requisition, priority/project code
- flight ID: sortie or flight record date/time, flight hours, landings, cycles

Data flows O→I→D through turn-in tags and the same JCN; serialized components carry their own log cards. Public evidence shows systematic data-quality problems:
- under-reporting of cannibalizations by up to 50%
- missing or corrupt electronic part records (81% of delivered F-35 spares lacked records at one site)
- engine logbooks not filled by an overhaul OEM (IAF IL-76)
- forms used incorrectly (Hawk W&M)
- aircraft under-reported (IAF IL-76)
- manual spreadsheets running alongside the system of record
- schedule overruns and AOG demand delays measured in months

### Cited Findings
- [DIRECT] **Component tracking fields (Navy WO).** Removed and installed items carry CAGE, S/N and P/N. Time/cycle prefix codes are five-character values such as "A0027" (type equipment hours), "E" (AESR operating hours since overhaul), "L" (landings), "P" (cycles), "S" (starts), "T" (catapult shots) and "W"/"X" (warranty expiry/contract number) — [NAMP §§15.3.2–15.3.3; App E Time or Cycle Prefix Codes, pp.E-30 to E-32](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Configuration as a by-product.** "A by-product of MDD is the maintenance of the actual configuration as it pertains to serial tracked and time-change items" — [TO 00-20-2 §1.4.1.1.5](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/). REMIS GCSAS is the AF configuration/TCTO system — [TO 00-20-2 §2.2.4.3](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Supply linkage (Navy).**
  - The failed/required material section records PROJ (NAVSUP project code), PRI (DoD 4140.1-R priority), DATE ORD, DDSN (MILSTRIP requisition number) and DATE RCVD.
  - AWP time starts when the requisition is placed. Job status changes to AWP and then to M3 on receipt.
  - Local issue response standards: priority 1–3 within 1 hour, 4–8 within 2 hours, 9–15 within 24 hours.
  - Source: [NAMP §15.3.5, §15.2.5(c), §6.6.2](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **USAF supply linkage.** Back-ordered parts get a "DOC NUMBER" in the 781A, carried forward to the 781K. Removed reparables get an AFTO Form 350 tag, and NRTS (not reparable this station) reasons are coded — [TO 00-20-1 §§5.7.3.11, 5.14.6.4](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/); [TO 00-20-2 Ch 3, App E](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Cannibalization records.**
  - USAF: AF Form 2414 verification worksheet or automated equivalent; ATC "T" for removal and "U" for replacement; HMC 799 (875 for engines). The narrative states the donor and recipient serial numbers. CANN "may be indicative of support problems" — [TO 00-20-2 Ch 5](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
  - Navy: CANN WOs only from Maintenance Control, Type WO "CM", TRANS 18 (19 for engines), with MAL 812–818 recording the reason — [NAMP §15.5.1.5, App E](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
  - The official example shows the CANN discrepancy text "Cannibalized item: … for Modex 212 Original MCN: 3FU8TZA" — [NAMP Fig 15-12](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **CANN magnitude (US).**
  - FY1996–2000: "about 850,000 cannibalizations, requiring about 5.3 million additional maintenance hours".
  - Navy data "reportedly understated by as much as 50 percent"; the Air Force "under-reports"; the Army does not collect servicewide figures.
  - Navy average rate 8.8–9.6 CANNs per 100 flying hours (FA-18C 11.2, FA-18E 21.5 in FY2000).
  - Air Force average 10.6–12.7 per 100 sorties (FY2000 average 11.6; F-16C 9.5; F-15C 22.0; F-15E 22.8).
  - Source: [GAO-02-86, Results in Brief p.2; pp.7–10; App II–III Tables 1–2](https://www.gao.gov/assets/gao-02-86.pdf).
- [DIRECT] **Maintenance levels and flows (Navy).**
  - The JCN "provides a link with the maintenance actions performed by the IMA in support of an O-level maintenance discrepancy".
  - Turn-in documents are auto-generated for reparables inducted into the IMA.
  - M/L values: 1 = O-level, 2 = I-level, 3 = D-level.
  - Components received faulty from supply are coded WD "Y", with a new JCN.
  - Missing SRC/ASR/MSR/EHR/AESR records make a component "NRFI" (not ready for issue).
  - Source: [NAMP §§15.3.1(b), 15.3.1(o), 15.5.1.3, 15.5.1.4](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **IAF flows and delays.**
  - TV3-117 helicopter engines due for overhaul/TTL extension are "received at 3 Base Repair Depot (BRD) from where they are dispatched to the OEM after getting approval from Air HQ". In 2013 only 44 of 76 due engines were sent, and "23 and 28 aircraft on ground (AOG) demands" were pending for engines in Jan 2014 and Jan 2015.
  - "Total technical life (TTL) of 3000 hours".
  - IL-76 engines are to be overhauled "after 2000 flying hours or 1500 Flight Cycles or 10 calendar years, whichever is earlier", but were flown beyond the limits without approval.
  - Source: [CAG 24 of 2017, paras 2.4, 2.7, pp.23–24, 39](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf).
- [DIRECT] **IAF AOG demand timeliness (IL-76, 2010–15).**
  - Norm: if spares for grounded aircraft "were available in stock they should be issued within 24 hours".
  - 2,899 AOG demands: 10.83% met within 15 days, 3.41% within 16 days–1 month, 25.18% within 1–6 months, 22.49% after more than 6 months.
  - IL-78: 770 demands, with 32.72% met after more than 6 months.
  - Second-line servicings at 300/900/1800 flying hours had prescribed durations of 22/35/50 days (IL-76). Only 36.84% of IL-76 and 30% of IL-78 servicings were completed within the prescribed time.
  - Source: [CAG 24 of 2017, para 2.7.4(a)–(b), Tables 2–5, pp.36–38](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf).
- [DIRECT] **IAF data-quality realities.**
  - "The Squadron … had been reporting the availability and operations of only 12 aircraft" out of 14 held; two were floats at another base.
  - "the OEM did not fill up the engine log books".
  - Maintenance continued on outdated OEM manuals, and there were unauthorised deviations from OEM bulletins.
  - Source: [CAG 24 of 2017, paras 2.7.2, 2.7.4(c), pp.31, 39](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf).
  - Shortage of rotables against the approved Scale of Rotables left an aircraft AOG "for want of rotables" — [CAG 38 of 2015, para 2.1.3.4](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf).
- [DIRECT] **F-35 data-quality realities.**
  - Electronic records "are frequently incorrect, corrupt, or missing, resulting in ALIS signaling that the aircraft should be grounded".
  - One site saw "between 0 and 400 issues per week".
  - Of 263 spare parts delivered to one site in June 2018, 213 (81%) lacked electronic records.
  - Users spend "5,000 to 10,000 hours per year manually tracking information", including in Excel.
  - One site was grounded "9,262 hours or 9 percent of possible flight hours" due to unresolved ALIS ARs, mainly missing or inaccurate parts records.
  - Source: [GAO-20-316, pp.13–15, 19, 23–24](https://www.gao.gov/assets/gao-20-316.pdf).
  - Eglin squadron leadership estimated "approximately 150 man-hours per week" on ALIS workarounds and "14 manual products" — [GAO-16-439, pp.29–30](https://www.gao.gov/assets/gao-16-439.pdf).
- [DIRECT] **UK data-quality example.** On the RAF Red Arrows Hawk, the smoke pod had been "fitted/removed on at least 4 occasions without the W&M record being updated". Basic weight "was recorded on the MF701 where as it should be recorded on the MF702" — [UK DSA SI Hawk T Mk1A XX204, paras 1.4.50–1.4.52, fn 29](https://assets.publishing.service.gov.uk/media/5d9c9f73e5274a596f829ba9/20191007-HAWK_T_Mk1a_XX204_SI_Redacted-Final.pdf).
- [DIRECT] **Institutional data-quality controls.**
  - Navy: supervisors and analysts screen every WO for "WUC, WD, TM, MAL, SCIR documentation, and logbook documentation"; there is a Reliability Control Board degrader analysis based on WO data accuracy.
  - USAF: a "ER" activity identifier marks entries "documented incorrectly … excluded from data compilations"; MDD man-hours "must NOT be used for manning decisions … Work centers must not inflate repair actions".
  - Source: [NAMP §§15.2.2(b), 14.1.6](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf); [TO 00-20-2 §§1.4.3, 4.25](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Time-lag rules.**
  - WO completion time "will not be able to be backdated prior to the last job status".
  - SCIR changes create a new MCN under the same JCN, with a computer-generated received time.
  - Start/stop entries are closed for any delay over 15 minutes.
  - Source: [NAMP §§15.2.5(d), 9.2.3.4](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf); [TO 00-20-2 §4.27](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).

### Inferences
- [TRANSFER: USN/USAF → Phalanx] The minimum key set for linkage should be:
  - aircraft tail
  - sortie/flight ID (date + takeoff time)
  - job number (IAF-style "snag no." or JCN equivalent)
  - component triplet (P/N, S/N, CAGE/maker) with time/cycles at removal and installation
  - demand/document number

  Inject realistic breaks: missing S/N (default "XXX" in OOMA), wrong form/field, delayed close-out, duplicate snags, under-reported CANNs, and log-card gaps after OEM overhaul.
- [TRANSFER: CAG IAF data → Phalanx calibration] The CAG distributions are rare public IAF-specific numbers for synthetic-supply-delay calibration: AOG demands met within 15 days about 11%, more than 6 months about 22–33%, and second-line servicing on time 30–37%. Limit: they apply to aging Russian-origin transport fleets, so they are pessimistic for Tejas/F404 or for OEM-supported fleets.

### Gaps
- No empirical study quantifying WUC mis-coding rates or free-text error rates in military fighter data was retrieved. RAND and AFIT studies were not reachable without search, and Lukens et al. (PHM Society 2019) was cited by NIST but not read.
- No public IAF data on time-lags between squadron, BRD and HAL record updates.

---

## Q6. Realistic event chains (sensor anomaly → … → return to service), scheduled inspections, TCTO/modification, life-limited parts

### Takeaway
Public documents give enough procedural detail to build event chains with realistic ordering and documents:
- discovery code and status symbol
- WO/MWO opened, with up/partial/down status
- troubleshooting (separate JCN/WO when lengthy)
- parts ordered (priority, requisition) or cannibalization (two linked jobs)
- part swap with S/N/time captured
- operational/leak check or FCF
- inspector sign-off
- aircraft release

Official example WOs show realistic durations: hours for same-shift repairs, days to three weeks when awaiting parts.

### Cited Findings
- [DIRECT] **Official example timelines (NAMP):**
  - IGB chip light (in-flight, Disc C): Received 29 Jan 2019 11:31 → In Work 11:39 → Completed 16:12. 11.0 man-hours, 3.0 elapsed hours; troubleshooting WO (AT Y) — [Fig 15-6](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
  - FADEC advisory (Disc A, EOC Z down): Received 20 Nov 2019 09:46 → In Work 12:30 → part removed 15:11 → 10 consumable parts ordered and received 17:24–17:34 → new control installed 07 Dec 20:22 → Completed 10 Dec 11:16. 34.3 man-hours, 13.5 elapsed hours — [Fig 15-8](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
  - Cannibalization (Type WO CM, TRANS 18, AT T, MAL 814, Disc O): Received 19 Apr 07:39 → removed 10:45 → original requisition dated 09 Jan, part received 23 Apr → installed 05 May 10:10 → completed 05 May 23:24 — [Fig 15-12](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
  - MSP 646 FADEC (Disc H, AT R): Received 02 Oct 20:31 → In Work 03 Oct 15:00 → installed 17:37 → completed 19:03 — [Fig 15-41](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **USAF chain rules.**
  - The finder enters a discrepancy with a symbol (Red X if unsafe) and a JCN.
  - If parts are back-ordered, the DOC NUMBER is entered; non-Red-X items may be transferred to the 781K as delayed discrepancies.
  - The operational check is part of the action ("OP CK GOOD"). If it cannot be done concurrently, a new linked 781A entry is made; in-flight op checks are signed by aircrew.
  - For a Red X, the technician signs CORRECTED BY and the inspector signs INSPECTED BY and initials over the symbol.
  - An exceptional release (781H) is required before flight and is never allowed on a Red X.
  - Source: [TO 00-20-1 Ch 4; §§5.4, 5.7, 5.12.2.2.7](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).
- [DIRECT] **Navy release rules.**
  - Safe-for-flight certification includes reviewing the AADB, downing discrepancies and QA sign-offs, servicing, fuel samples (valid ≤24 h), oil consumption, HMS data (FAME), W&B, forced removals, overdue TDs, and flight-hour accuracy over the last ten "A sheets".
  - Daily inspections are valid up to 72 h; turnaround inspections 24 h.
  - Pilots enter the NAVFLIR (flight record) into OOMA "immediately after each flight".
  - Source: [NAMP §§5.1.5.4, 5.1.6.2, 5.3.5.2–5.3.5.3, pp.5-9 to 5-11, 5-36](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **Scheduled inspections.**
  - USAF inspection concepts: PR/BPO/TH/HPO, Periodic (PE), Phase (PH), Isochronal (ISO), HSC, PDM. Phase-inspection JCNs use 6th-position letters A–Z by phase number.
  - Navy major inspections use Control/Look/Fix WOs (Type WO PC/PL/PF). A JCN serial "A00" is used for the first aircraft inspection of the day.
  - Inspection-found discrepancies use WD "M" and TM "G".
  - Source: [TO 00-20-1 Ch 2](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/); [TO 00-20-2 Fig 4-1](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/); [NAMP §15.5.2.1](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
- [DIRECT] **TCTO/TD compliance.**
  - USAF Red X applies on receipt of immediate-action TCTOs or when urgent/safety TCTO work starts. Red Diagonal applies for urgent or Category I routine safety TCTOs. The 781K lists "open TCTOs grounding within 120 days".
  - Navy TD WOs carry CODE/BASIC NO/REV/AMEND/PART/KIT, TRANS 41/47 and TD status codes C/P/D/W/Q. The example is "COMPLIED WITH AYB-1638 …".
  - Source: [TO 00-20-1 §§4.2.3, 4.4.3, 5.14.6](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/); [NAMP App E TD codes; Fig 15-48](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
  - IAF promulgates "TSIs, SIs, STIs and modification through routine order Pt-III" — [IAF RTI Handbook, ACAS (MP)](https://indianairforce.nic.in/Resources/pdf/utilities/RTI-Handbook-updated-as-on-19-Apr-23.pdf).
- [DIRECT] **Life-limited and time-change items.**
  - USAF Time-Change Items are replaced at -6 TO intervals, considered due at the nearest scheduled inspection. Overdue life-sustaining TCIs get a Red X.
  - Navy hi-time removal example: "REPLACE OBOGS CONCENTRATOR DUE TO HI-TIME", MAL 804, Disc O. MAL codes 866 and 879 cover expiry of maximum time or cycles. Engine and modules are tracked on AESR/MSR.
  - IAF TTL and overhaul limits are as given in Q5.
  - Source: [TO 00-20-1 Ch 6, §4.2.3.7](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/); [NAMP Fig 15-36; App E](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf); [TO 00-20-2 App G](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
- [DIRECT] **Exceedances and conditional inspections.** SCIR applies for a conditional inspection where "an overlimit condition exists, for example, hard landing, bolter, overspeed, or overtemp, that restricts the aircraft from further flight until the inspection is completed" — [NAMP §9.2.3.3(b)](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf). USAF historical records require entries for "overstresses and hard landings" and engine "overspeed, overtemperature" — [TO 00-20-1 §9.1.5.9, §9.1.6.7](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).

### Inferences
- See closing section (c) for assembled chains. Durations are taken from the official examples and the CAG/GAO distributions. Unsourced values are tagged [ASSUMPTION].

### Gaps
- No public IAF example of a complete snag lifecycle with timestamps.
- No public fighter-specific (F-16/Tejas) exceedance-report formats (e.g., engine overtemp printouts, g-exceedance records) were retrieved. The engine-data researcher may cover the F404 EMS/ECU.

---

## Closing synthesis (required items a–e)

### (a) Key findings summary
1. **Common record architecture.** USAF, USN and UK all use:
   - a per-aircraft status log
   - per-defect work documents with a unique job number
   - five coded dimensions: system/WUC, when-discovered, how-malfunctioned, action-taken, type-maintenance
   - free text
   - two-person certification (corrected/inspected)
   - separate serialized component life records

   [DIRECT for each force; TRANSFER to IAF as a template.]
2. **IAF public facts.**
   - 1st/2nd line = O/I level at squadron/base; 3rd/4th line = D level at BRD/HAL/OEM.
   - Maintenance Command, with BRDs, EDs (equipment depots), ASPs and MCUs.
   - Air HQ maintenance branch with eMMS and IMMOLS functions.
   - "Serviceability %" against targets (70% for the IL fleet).
   - AOG demands, TTL and overhaul limits.
   - Known data-quality failures: under-reporting, missing engine log entries, out-of-limit operation without recorded approval.
3. **Health monitoring is now formally inside the maintenance-records system** (Navy NAMP 10.37 and When-Discovered I/N/R, Type-Maint C; F-35 HRC workflow). This is a direct, public precedent for Phalanx's "telemetry → record" linkage.
4. **False alarms and NFF are institutionalised:**
   - code families: USAF ATC H/B; HMC 672/675/676/799/812; Navy A-799
   - the F-35 3-flight deferral then admin-close (FID D40, HMC 000, AT O)
   - nuisance filter lists
   - The **numeric** fighter NFF rates were not publicly accessible.
5. **Availability computation is precisely specified** (Navy SCIR 15-min binning, MC/FMC formulas; USAF App L algorithms; GAO definitions). Phalanx can compute availability from synthetic job states deterministically.
6. **Data-quality realities are well documented and should be injected deliberately:**
   - CANN under-reporting up to 50% (GAO-02-86)
   - 81% of F-35 spares without electronic records at one site (GAO-20-316)
   - manual parallel tracking of 5,000–10,000 hours per year
   - wrong-form W&M entries (UK SI)
   - aircraft under-reported and engine logbooks unfilled (CAG)
   - typos even in official examples (NAMP figures)
   - 97/106 non-standard tokens in civil logbook samples (MaintNet)

### (b) Record types: fields, codes, sources

| Record type | Purpose / trigger | Key fields (verbatim names where available) | Code systems | Primary sources | IAF applicability |
|---|---|---|---|---|---|
| USAF AFTO 781A Maintenance Discrepancy & Work Document | Every discrepancy (aircrew or maintenance) | FROM/TO, MDS, SERIAL NUMBER, SYM, JCN, DATE DISC, DOC NUMBER, CF 781A/XF 781K, DATE CORRECTED, WUC/REF DESIGNATOR, STA CODE, DISCREPANCY, DISCOVERED BY, EMPLOYEE NO, CORRECTIVE ACTION, CORRECTED BY, INSPECTED BY | Red X / Red Dash / Red Diagonal; WUC; JCN | [TO 00-20-1 §5.7](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/) | TRANSFER (structure) |
| USAF AFTO 781H Flight Status & Maintenance | Aircraft status and flight/servicing totals | Inspection certification (PR/BPO/TH…), STATUS TODAY symbols, EXCEPTIONAL RELEASE, AIRFRAME TIME, LANDINGS (FULL STOP/TOTAL), JFS STARTS, ENGINE CYCLE, SERVICING DATA | Symbols | [TO 00-20-1 §5.12](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/) | TRANSFER |
| USAF AFTO 781J Engine Flight Document | Engine time/cycles/oil | DATE, AIRFRAME TIME, OIL SAMPLE (X), OIL ADDED, ENGINE POS #, OIL CHANGE TIME, ENGINE TIME, CYCLES | — | [TO 00-20-1 §5.13](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/) | TRANSFER (engine log) |
| USAF AFTO 781K Inspection/Engine/Delayed discrepancies | Due inspections, engine S/N, deferred defects, TCTOs | NEXT DUE, ENG SER NUMBER, ENG CHANGE DUE TIME, SYM, JOB CONTROL NUMBER, DOCUMENT NUMBER, GROUND DATE/TIME | Red Dash / Diagonal only | [TO 00-20-1 §5.14](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/) | TRANSFER (≈ UK ADF/limitations logs) |
| USAF MDD record (AFTO 349 / IMDS line) | Coded maintenance action | JCN, Workcenter, ID number, WUC, ATC, WDC, HMC, Units, Start/Stop, Crew size, Category of labor, Component position, BIT fault code (block 16), FSC/P/N/S/N/operating time, Tag number | ATC (App E), TMC (App F), HMC (App G), WDC (App H), Support General (App I) | [TO 00-20-2 Ch 4, Apps](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/) | TRANSFER (code structure) |
| USAF AFTO 95 / CEMS engine & historical record | Permanent history (TCTO, TCI, damage, overtemp) | "TT, TSO, Cycles", engine position, airframe S/N | — | [TO 00-20-1 Ch 9](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/); [TO 00-20-2 §2.7](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/) | TRANSFER |
| USAF AF Form 2414 / CANN record | Cannibalization verification | Two JCNs (T/U and FOM); donor and recipient S/N in narrative | ATC T/U; HMC 799/875 | [TO 00-20-2 Ch 5](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/) | TRANSFER |
| USN OOMA Work Order / OPNAV 4790/60 VIDS/MAF | Every maintenance action (O/I level) | MCN, JCN (ORG+DAY+SER), TYPE WO, ORG CODE, MODEX, BUNO/SERNO, ASSY CD, WORK CENTER, TD fields, WUC/UNS, TRANS, M/L, ITEM PRC, ACTION TAKEN, MAL CODE, DISC CODE, TYPE MAINT, Removed/Installed CAGE/SN/PN/date, MAN HRS, ELAPSED HRS, RECEIVED/IN WORK/COMPLETED, EOC, U/D/P, METER, POSIT, SYSTEM REASON, (H-Z) failed parts (A/T, MAL, PN, QTY, PROJ, PRI, DATE ORD, DDSN, DATE RCVD), DISCREPANCY, CORRECTIVE ACTION, signatures | App E: AT, MAL, WD (incl. I/N/R), TM (incl. C predictive), TRANS, Type WO, TD codes, AWM, job status, time/cycle prefixes | [NAMP Ch 15, App E](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf) | TRANSFER (best public template) |
| USN SCIR / readiness | Mission-capability time accounting | EOC (3-character), U/P/D, AWP/AWM/EMT, 15-min bins | NMCD/NMCS/NMCM-U/S/PMCS/PMCM | [NAMP Ch 9](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf) | TRANSFER (availability engine) |
| USN logbook & CM ALS (OPNAV 4790/21A, /22A, /23A, /24A, /25A, AESR, MSR, ASR, EHR, SRC) | Flight summary, inspections, rework, TDs, history, component life | Flying hours MO/PERIOD/SINCE NEW, landings, CATs/arrests, inspection type and hours, TD numbers, component time/cycles | YYMMDD dates | [NAMP Ch 8](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf) | TRANSFER (≈ IAF engine log book / history) |
| USN NAVFLIR (OPNAV 3710/4) / AADB "A sheet" | Flight record and aircrew acceptance | Flight hours, landings, aircrew; last 10 flights kept with HMS data | — | [NAMP §§5.1.5–5.1.6, 14.1.3.5](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf) | TRANSFER (sortie record) |
| F-35 CMMS WO / HRC / EEL (ALIS → ODIN) | Health-code-driven maintenance | HRC, VS BIT, FID code, HMC, AT; EEL (part history, remaining life) | HRC Significant List, NFL, Correlation Filter List | [4790.35D](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/4790.35D.pdf); [GAO-20-316](https://www.gao.gov/assets/gao-20-316.pdf) | TRANSFER (PHM-era pattern) |
| UK MOD F700C technical log (F707A ML, F707B MWO, F703 Limitations, F704 ADF, F705 FSC, F721 Forecast, F724-726 usage, F701/702) | Air-system serviceability state and work | SNOW, ORN, Work Required, Work Done, 1st/2nd/3rd signatures, AFRC (flying requirement) | "EinE", MOD Form 799 IFUs | [MAM-D](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf) | TRANSFER (closest heritage to IAF) |
| UK Engineering Record Cards (F731 conditioning label, F744 airframe, F745 repair, F746 mods, F749/F735 components) | Component and airframe history | Nomenclature, S/N, repair scheme, ORN/SNOW link | — | [MAM-D Ch 2.1 §§7–10](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf) | TRANSFER |
| IAF engine log books, servicing schedules (1st/2nd line), AOG demands, DR (discrepancy report), BRD/HAL ROH task | IAF-specific (public existence only) | Not public | Not public | [CAG 24/2017](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf); [CAG 38/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf); [CAG 34/2014](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2014/Union_Compliance_Defence_Air_force_Navy_34_2014.pdf) | DIRECT (existence); fields = ASSUMPTION |
| S5000F in-service feedback messages (Event, MaintenanceEvent, LogBookEntry, DownTimePeriod, DetectionMechanism, NFF report) | Standards-based exchange | eventIdentifier, eventOcurrenceDateTime, eventGroup, eventSeverity, eventDescription, eventConfirmedStatus, maintenanceEventCategoryType, detectionMechanismFalseAlarmRate | S-series data model | [S5000F Issue 4.0](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf) | Design choice for Phalanx |
| FAA SDR (civil) | Service difficulty report | How Discovered, Nature of Condition, Precautionary Procedure, Stage of Operation, Part Condition, Time Since (O/R/I), JASC | SDRS lookup tables | [FAA SDRS](https://sdrs.faa.gov/) | TRANSFER (text/coding texture only) |

### (c) Evidence-based example event chains (synthetic, for Phalanx)

All times are illustrative. **Durations are anchored to cited examples**; others are marked [ASSUMPTION]. Codes are shown in USN/USAF form to make the mapping explicit. In Phalanx they should be relabelled to Phalanx/IAF-style tables.

**Chain 1 — Engine lube-system anomaly, in-flight caution, no abort → part replacement (F404-class fighter)**
1. **T0 sortie 2 (11:05)**:
   - Telemetry: oil pressure fluctuation during afterburner. The pattern mirrors the NAMP example discrepancy "Engine oil pressure fluctuating approximately 50 PSI while in afterburner".
   - Onboard: C-BIT logs an engine-monitoring fault code, and a caution is presented [ASSUMPTION that it reaches the cockpit; see the F-35B case for the alternative where data is recorded but not displayed].
2. **Landing 11:52 → debrief 12:10.**
   - Pilot opens a write-up per discrepancy, with WD D (in-flight, no abort), status P or D per the MESM/EOC.
   - Text: "ENG OIL PRESS FLUCTUATES ±50 PSI IN AB, NORMAL OTHER REGIMES. CAUTION LT ON 2 SEC." [ASSUMPTION wording, modelled on NAMP §15.3.6].
   - Source: [NAMP §15.2.4.3(c)](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
3. **Post-flight data download 12:20.**
   - HMS fault codes are reviewed by Maintenance Control. If no aircrew write-up existed, a separate WO with WD "I" would be raised. Here the codes are added to the pilot WO's discrepancy block.
   - QA adds the flight to the BUNO 50-flight trend.
   - Source: [NAMP §10.37.4.1.2–3](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
4. **Troubleshooting 12:40–15:10** (separate troubleshooting WO / AT "Y" with a system-level WUC if lengthy). Fault isolation per the IETM/FIM task finds the oil pressure transmitter faulty (Navy MAL 191–196 family; USAF HMC 202). Source: [NAMP §15.5.1.1; App E](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
5. **Part demand 15:20.**
   - Requisition with priority/project code. If stocked: issue in ≤1–2 h (priority 1–8) [NAMP §6.6.2].
   - If not stocked (AWP): the IAF analogue is the AOG demand. Per CAG IL-76 data, only ~11% of AOG demands were met within 15 days.
   - Alternative: Maintenance Control authorises a CANN from a hangar-queen aircraft (two jobs, AT T/U, MAL 814/815) [GAO-02-86; NAMP Fig 15-12].
6. **Install 17:30–18:30.**
   - Removed and installed P/N, S/N and CAGE recorded with time prefix (e.g., E-hours on the engine component).
   - Engine ground run / leak check; corrective text: "R/R #1 ENG OIL PRESS XMTR IAW [task]. GND RUN OPS CHK GOOD, NO LEAKS. AREA FOD FREE." [ASSUMPTION wording, modelled on NAMP Fig 15-8].
7. **Inspector sign-off 18:45** → status Up → Safe-for-flight review (including HMS data) → aircraft released. Source: [NAMP §5.1.6.2](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
8. **Shop (I/D level) days to months later.**
   - The removed unit is sent on a turn-in document to the I-level/BRD. Bench check outcomes:
     - (a) confirmed failure → repair/BCM/NRTS to depot (HAL/OEM)
     - (b) BCS/RTOK (no fault found) → the on-aircraft record later counts in CND/NFF statistics; repeated BCS on the same S/N → rogue unit
   - Depot repair turnaround of the order of months: F-35 average 72 days at military depots [GAO-23-105341]; IAF LRUs sent to OEM have "longer turn-around time" [CAG 38/2015].

**Chain 2 — BIT/HRC false alarm → monitor → admin close (avionics)**
1. **Sortie N:** I-BIT/C-BIT code set (e.g., a radar-receiver fault). No pilot complaint, or the pilot writes "RADAR FAIL CAUTION MOMENTARY, BIT GO ON RECYCLE" [ASSUMPTION].
2. **Post-flight:** WO opened with WD "I" (HMS-identified) or the aircrew code; status Up (no EOC) or Partial per the MESM.
3. **Ground check:** I-BIT passes and the code does not reproduce. Two branches:
   - USAF-style: ATC H with HMC 799/672/676 = CND.
   - F-35 style: WO deferred and monitored for 3 consecutive flights; no recurrence → admin close (FID "D40", HMC "000", AT "O").
   - Source: [TO 00-20-2 App E/G](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/); [4790.35D §15.2.4](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/4790.35D.pdf).
4. **Recurrence path:** the code returns on sortie N+2 → write-up flagged "Repeat/Recurring" → troubleshooting → LRU R/R → shop result BCS → QA tracks the A-799 rate by P/N/S/N. Nuisance codes eventually go to a filter list after an engineering AR. Source: [TO 00-20-1 §5.7.3.16.10](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/); [NAMP §7.4.4(c)](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).

**Chain 3 — Exceedance → conditional inspection (over-temperature or over-g)**
1. Telemetry exceedance (e.g., EGT above limit for X s, or a g-limit exceeded) is recorded by engine/aircraft monitoring. The cockpit may or may not alert. Text code family: Navy MAL 922 "ENGINE MONITORING SYSTEM INDICATES OVERTEMP LIMIT EXCEEDED"; USAF HMC 192/482.
2. Post-flight download → conditional inspection WO (Type WO CC/CL/CF; WD "Q"; TM "S"). The aircraft is down because "an overlimit condition exists … that restricts the aircraft from further flight until the inspection is completed".
3. Engine borescope/inspection per manual. Historical record entry for overtemp/overstress (AFTO 95 / logbook "Miscellaneous/History").
4. Outcome: within limits → close and release; out of limits → engine removal (TRANS 23/25, AT R), engine log/AESR update, spare engine install, ground run.
5. Sources: [NAMP §9.2.3.3(b), App E](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf); [TO 00-20-1 §§9.1.5.9, 9.1.6.7](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).

**Chain 4 — Scheduled phase/periodic inspection with fix-phase defects**
1. Aircraft reaches an inspection interval (flight hours or calendar). This is forecast in the 781K, NAMP inspection record or UK F721 forecast. The IAF analogue is a 2nd-line servicing at fixed hours (CAG: IL-76 at 300/900/1800 h with 22/35/50 days prescribed).
2. Control WO/JCN with an inspection serial (e.g., Navy "A00"; USAF 6th-position phase letter). Look-phase WOs use AT "0" and ITEMS PROC 0. Discrepancies found get WD "M" and TM "G" (fix-phase WOs, Type WO PF), e.g., "AFT AVIONICS COOLING FAN FILTER CLOGGED".
3. Panels removed are documented (local panel sheets). FOD/IPI inspections. Status is down (SCIR "Z") if disassembly cannot be reversed within 2 hours.
4. Completion → forecast updated (next due) → FCF if required (Red Dash / WD "P" findings) → release.
5. Realistic overrun: only 30–37% of IL-fleet second-line servicings finished within the prescribed days [CAG 24/2017].

**Chain 5 — TCTO/modification and life-limited part retirement**
1. A TD/TCTO is issued (e.g., an urgent inspection of hardware). The USAF symbol depends on urgency (Red X immediate or Red Diagonal urgent). It is listed in the 781K with a grounding date. The IAF analogue is an "STI/SI" or modification order [RTI Handbook].
2. TD WO with code/basic number/kit. Compliance text: "COMPLIED WITH [TD] … CHECKS GOOD". TD status C, or D (does not apply, QA-verified).
3. Life-limited part approaching its limit: forecast flags it → opportunistic removal (USAF HMC 880) or hi-time removal (Navy MAL 804/866/879) → new S/N installed → component card/EEL updated → removed part to depot/condemnation.
4. Data-quality variant: an engine returns from OEM overhaul with an unfilled log book (CAG), or a spare arrives without its electronic record (GAO) → the part is NRFI or a manual record is reconstructed.

### (d) Open questions / gaps
- IAF-specific form layouts, field names and code tables (Form 700 equivalents, eMMS data model, IMMOLS document numbers, engine log book format, HAL ROH documentation, AOG/MCM/PHU priority definitions) were not public. Ask DSSC/IAF mentors or retired IAF engineers for sanitized templates.
- Numeric NFF/CND/BIT false-alarm rates for fighter fleets (F-16, F/A-18, Gripen, Su-30MKI, Tejas) were not obtained. The DOT&E F-35 reports and peer-reviewed NFF literature were inaccessible here.
- F-16 PFL/MFL and F/A-18 MSP/DDI logic, and Su-30MKI/Gripen fault-reporting formats: no public primary text was found.
- ATA Spec 2000 Ch 11, ARINC 624, MSG-3 full logic and MIL-STD-1388-2B tables are paywalled or were not retrieved.
- Current USAF code tables (TO 00-20-2, Dec 2024) and DAFI 21-101/21-103 could not be accessed; 2007/2013 editions were used.
- No quantitative study of WUC mis-coding or free-text error rates in military fighter data was retrieved.
- USAF AIB reports with verbatim AFTO 781 entries were not accessible (403). Scanned UK SIs were not OCR'd.

### (e) Ranked list of most valuable sources
1. **NAMP COMNAVAIRFORINST 4790.2E (28 Oct 2024)** — complete, current, public. It covers WO fields, all code tables (incl. HMS-era WD I/N and TM C), SCIR/MC math, HMS trending policy, logbooks, and 50+ example WOs with realistic text and timestamps — [PDF](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf).
2. **TO 00-20-2 Maintenance Data Documentation (2003/Ch2 2007)** — USAF code tables (ATC/TMC/HMC/WDC), JCN rules, BIT reporting, CANN, and App L reliability algorithms — [EverySpec](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-2_4007/).
3. **TO 00-20-1 (2013)** — AFTO 781 series fields, Red X/Dash/Diagonal logic, writing rules and phrasings — [EverySpec](https://everyspec.com/USAF/USAF-Tech-Manuals/TO_00-20-1_15JUN2013_49351/).
4. **CAG Reports 24/2017, 38/2015, 17/2015 (IAF)** — the only public IAF-specific evidence on maintenance levels, serviceability, AOG timeliness, servicing overruns, TTL/overhaul limits and record failures — [24/2017](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf), [38/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf), [17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
5. **COMNAVAIRFORINST 4790.35D (F-35 supplement)** — HRC/PHM false-alarm workflow, EEL alerts and VS BIT at release — [PDF](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/4790.35D.pdf).
6. **UK MAM-D (MOD Form 700 series)** — the closest heritage model to IAF records — [PDF](https://assets.publishing.service.gov.uk/media/6a0b10e0c510c3913d82678e/MAM-D.pdf).
7. **S5000F Issue 4.0** — standards-based schema for linked in-service events (Event, MaintenanceEvent, DetectionMechanism, NFF report) — [PDF](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf).
8. **IAF RTI Handbook (2023) & Suo-Moto Disclosure (2025)** — IAF maintenance organisation, eMMS/IMMOLS, line-servicing terms — [RTI](https://indianairforce.nic.in/Resources/pdf/utilities/RTI-Handbook-updated-as-on-19-Apr-23.pdf), [Suo-Moto](https://indianairforce.nic.in/Resources/pdf/utilities/SUO_MOTO_DISCLOSURE%20_JUL_2025.pdf).
9. **GAO-20-316 / GAO-16-439 / GAO-23-105341 (F-35 ALIS/ODIN)** and **GAO-02-86 (cannibalizations)**, **GAO-23-106217 (MC definitions)** — quantified data-quality and readiness realities — [20-316](https://www.gao.gov/assets/gao-20-316.pdf), [02-86](https://www.gao.gov/assets/gao-02-86.pdf), [23-106217](https://www.gao.gov/assets/gao-23-106217.pdf).
10. **UK DSA Service Inquiries (F-35B ZM152; Hawk XX204)** — real servicing timelines, record errors, and recorded health data that never reached the cockpit — [ZM152](https://assets.publishing.service.gov.uk/media/651d73e4e4e658001459d95d/Service_Inquiry_into_the_loss_of_F-35B_Lightning_ZM152__BK-18_.pdf), [XX204](https://assets.publishing.service.gov.uk/media/5d9c9f73e5274a596f829ba9/20191007-HAWK_T_Mk1a_XX204_SI_Redacted-Final.pdf).
11. **MaintNet (arXiv 2005.12443)** and **NIST TLP (Brundage et al. 2021)** — text texture and NLP pitfalls of logbook data — [MaintNet](https://arxiv.org/abs/2005.12443), [NIST](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=931138).
12. **FAA AC 120-17B (reliability programs: NFF, rogue/chronic units, data quality)**, **FAA SDRS lookup tables**, **14 CFR 25.1322**, **MIL-HDBK-338B (false alarm/CND/RTOK definitions)** — civil and handbook framing — [AC 120-17B](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_120-17B.pdf), [SDRS](https://sdrs.faa.gov/), [25.1322](https://www.ecfr.gov/current/title-14/part-25/section-25.1322), [MIL-HDBK-338B](https://everyspec.com/MIL-HDBK/MIL-HDBK-0300-0499/MIL-HDBK-338B_15041/).
