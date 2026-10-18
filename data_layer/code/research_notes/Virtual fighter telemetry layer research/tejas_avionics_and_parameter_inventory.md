# Tejas avionics, recording, health-monitoring and BIT architecture, and the canonical Phalanx parameter and event inventory for a "Tejas-class" virtual fighter (Project Phalanx)

**What this note is.** It does two things. (1) It fills the remaining public-information gaps on how HAL Tejas data is acquired, carried, recorded, monitored and downloaded. (2) It consolidates all earlier Phalanx research into a canonical, evidence-tagged inventory: what exists on the aircraft, what is measured, what is *not* measured, where each measurement starts, what drives it, and where it goes. The inventory is the seed for a **clearly labelled synthetic Phalanx ICD**. It is **not** a claim about the real Tejas ICD, which is not public.

**Deliverables (same folder):**
- `parameter_inventory.csv`: 189 logical parameters, 33 columns, one row per parameter.
- `not_measured_states.csv`: 50 hidden physical states, 14 columns.
- This note: architecture findings, compact inventory tables, event inventory, rate-group recommendation, and the closing items (a)–(f).

**Evidence tags (used on every claim and every CSV row).**
- **[DIRECT]**: the source is about Tejas/LCA itself.
- **[DIRECT-part]**: an Indian product page (HAL/DDP) gives the numbers, but the platform is not named; the reason for assuming Tejas fitment is given.
- **[DIRECT-unnamed]**: an ADE/ADA author describes "a typical combat aircraft" that is almost certainly LCA.
- **[TRANSFER: X]**: borrowed from platform or standard X, with why it transfers and its limits.
- **[MEASURED]**: texture values measured in `empirical_dashlink_texture.md`.
- **[ASSUMPTION]**: engineering judgement, with a validation route.
- "(snippet-level)": known only from a search-engine excerpt because the page could not be fetched.

**Method and access notes (read first).**
- **Earlier notes read and built on, not repeated:** `data_pathway_and_formats.md`, `tejas_airframe_aero_fcs.md`, `f404_in20_engine_model.md`, `tejas_utility_systems.md`, `addendum_engine_F404_F414_monitoring.md`, `candidate_engine_and_ehm_data.md`, `sensor_residual_texture.md`, `empirical_dashlink_texture.md`, `maintenance_records_and_events.md`, `indian_fleet_platform_relevance.md` (KQ3, KQ4, KQ6), `faults_and_degradation.md`.
  - The correction banner in the F404 addendum was applied: Henry's test-cell T1 is 266 K, test-cell T5 834.3 K, aircraft T5 871.0 K, and the ECU T5 trim is ±150 °F.
- **Literature sweeps:**
  - Full OAI-PMH harvests of JOAST (910 records) and the Defence Science Journal (4,009 records) were filtered for avionics, recording, BIT and health-monitoring titles.
  - The DDP/MoD product catalogue was queried through the site's own search.
  - ADA annual reports 2015-16 to 2021-22 were re-read (local text and OCR) for avionics and recorder lines.
  - Archived tejas.gov.in pages (ADA, 2015–2016) were found through Wayback CDX listings.
- **About 35 WebSearch calls were used** (of about 60 available). The rest of the work was direct fetches of known URLs, journal OAI feeds, Wayback CDX listings and the DDP site's own search.
- **Access failures:** drdo.gov.in and the CEMILAC TA PDFs ("inaccessible at this time"); globalsecurity.org (HTTP 402); defenseindustrydaily (403); USAF e-publishing (403); fliphtml5 (403); ADA AR 2016-17 (server error). Facts from these are marked snippet-level.
- **New local sources** are in `/Users/abishaikc/Phalanx/research_sources/tejas_avionics/`. Nothing was executed. They are:
  - JOAST 208, 215, 261, 319, 331, 598, 782 and 863 (PDF + text);
  - the NATO RTO-MP-SCI-162 paper 14 (NFTC "Tejas Flight Test: Lessons Learned So Far");
  - archived tejas.gov.in pages;
  - DDP product pages (CWS, DFDR, DACS, I-DMG, SMFD, G3INS, anti-skid unit, LCA);
  - the Park Controls PCAMi-1000 page;
  - the ADA ASMS page;
  - `HARV_CR-201670_AppA_parsed_OCR.tsv`, an OCR parse of the 1,713 HARV raw parameters with their recording rates.
- **Source restrictions.** Nothing from `_restricted_do_not_cite/` was opened. Some numbers in sibling notes came only from the restricted F/A-18 NATOPS: idle/MIL oil-pressure bands, the 880 °C -402 MIL EGT limit, FUEL HOT at 79 °C, the 815 °C start EGT, and the HAF F-16 "FCS BIT ≈45 s". These are not used as inventory values. Where they are mentioned they are flagged **"restricted-source; sanity-check only"**.

---

## Q1. Tejas avionics architecture (public): mission computer, 1553B buses and bus control, how DFCC, utility management, FADEC/ECMS, air data, INS/GPS, displays and warnings connect; Mk1A/Mk2 changes; avionics integration rigs

### Takeaway
Tejas is a federated, MIL-STD-1553B-based fighter:
- **Avionics core.** An ADA-designed Open Architecture Computer (OAC) is the avionics "heart". It combines the functions of the earlier mission computer, display processor, video switching unit and mission preparation and retrieval unit. It "drives the parameters from almost all the other systems". [DIRECT]
- **Utility and health management** reports "system health and warnings to the pilot through" the OAC. [DIRECT]
- **Flight control.** The quadruplex DFCC is a separate flight-critical computer. Each channel carries a 1553B interface, RS-422 links to the ADCs, and a cross-channel data link. Its 1553 output feeds the crash data recorder, the Get-U-Home (GUH) panel and the FTI. [DIRECT]
- **Utility computing.** Utility functions run in microprocessor electronic units: four on prototypes, merged into two in production. ADA documents name them **HEEM-EU** (2015-16), **BHEEM** (2018-19, which also handles braking control) and **ECFM** (ECS and fuel monitoring). [DIRECT]
- **Warnings.** A HAL SLRDC Centralised Warning System has 30 red/amber legends, audio tones, four voice warnings, ARINC-429 + 30 discrete inputs, and a "FADEC engine warning interface". [DIRECT-part; ADA budget lines make Tejas fitment probable]
- **Bus count.** "Three 1553B buses" with a 32-bit mission computer is stated only in prototype-era secondary sources. [secondary]
- **Mk1A** brings a new mission computer, DMG, Smart MFDs, an indigenous DACS and an indigenous DFCC [DIRECT]. HAL's DMG and DACS products carry 1553B, ARINC-429, ARINC 818 and Ethernet I/O [DIRECT-part]. **Mk2** moves to a time-sensitive-network (TSN) Ethernet backbone [DIRECT].

The real bus allocation, bus-controller and RT assignments, message rates, and the FADEC-to-aircraft interface are not public.

### Cited Findings

**Mission/avionics computer (OAC) and displays**
- [DIRECT] "Open Architecture Computer (OAC) designed and developed by ADA, combines the functions of earlier mission computer, display processor, video switching unit, mission preparation and retrieval unit. It is designed based on open system interfaces standards … OAC drives three multi-function displays, HUD and the helmet-mounted display." — [tejas.gov.in, OAC page (ADA, 2015, archived)](http://web.archive.org/web/2015/http://www.tejas.gov.in:80/technology/open_architecture_computer_for_avionics.html)
- [DIRECT, snippet-level] The DRDO avionics page adds: VME-based open hardware "with inbuilt redundancy"; MIL-STD-1553B interface "compatible to other aircraft"; IEEE 12207 software; caters to digital maps; an OAC development rig. The page now returns 404; content is from the search-index summary. — [drdo.gov.in/drdo/avionics](https://drdo.gov.in/drdo/avionics)
- [DIRECT] CEMILAC: "ADA has designed the avionic architecture of LCA with Open Architecture Computer (OAC) as a heart of not only avionic system but driving the parameters from almost all the other systems … designed with the contribution of 53 LRUs". — [Peter Arun et al., JOAST 67(2A) 2015](https://joast.org/index.php/joast/article/view/325) (local `indian_fleet/joast/joast_325.txt`)
- [DIRECT] "The new generation glass cockpit comprises Multi Function Displays (MFD), Head Up Display (HUD) and Stand by Instrumentation System driven by Open Architecture Mission and Display Computer … **The advanced utility and health management system provides system health and warnings to the pilot through a Open Architecture Computer (OAC).**" — [tejas.gov.in, Specifications–Systems (ADA, 2016, archived)](http://web.archive.org/web/2016/http://www.tejas.gov.in:80/specifications/systems.html)
- [DIRECT] Cockpit evolution:
  - The technology demonstrators had two MFDs, a HUD, an MFK, an MFR switch and a HUD-UFCP.
  - "The production version will have three MFDs and two Smart Standby Display Units (SSDU), with a Multi Function UFCP".
  
  — [Raveendran & Prabhu (NFTC/ADA), RTO-MP-SCI-162 paper 14, 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)
- [DIRECT] SSDU "software has been upgraded to introduce additional features for monitoring critical aircraft system parameters and to bring in 2 MFD concept for the future" (Navy LCA). The OAC was upgraded "to cater for DFCC 9008". Software version identifiers appear throughout: DFCC 7307/7351/9008; OAC 10.0.4.0/10.5.2; radar 7_008A; BHEEM 1.9.08. — [ADA AR 2017-18 (Navy avionics)](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf); [ADA AR 2018-19 §10.1.7 and flight-test sections](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) (OCR). Earlier, ski-jump software was "integrated on OAC, MF-UFCP, SSDU & FSDU" — [ADA AR 2015-16 §9.1.8](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf)
- [DIRECT] ADA's budget heads for LCA AF FSED Phase 2 avionics list:
  - "DP, MC, CCU, VSU combined units & OSA";
  - "SIB, SSB & PIB";
  - "Mission Preparation & Data Retrieval Unit";
  - "Crash Data Recorder";
  - "Centralised Warning System";
  - "Cockpit command controller & CIU";
  - "Mod./Maint of AV LRUs".
  
  Engineering-change lines include "HEEM - EU", "CWS hardware improvements", "Video Digital Recorder", "Signal & Data Processor" and "FCG probes". — [ADA AR 2015-16, Investments in LCA AF FSED Phase 2, pp. 75–79](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf) (local text)
- [secondary, prototype era] "All these systems are integrated on **three 1553B buses** by a centralised 32-bit mission computer (MC)". The MC handles weapon computations, flight management and reconfiguration/redundancy management. "Dual redundant display processors (DP)" generate the display imagery. "Reversionary mission functions are provided by a control and coding unit (CCU)". "Microprocessor based utility and brake management systems". "More than five hundred LRUs". — [FAS DOD-101 LCA page (last updated Dec 1999, citing Flight International, Nov 1998)](https://man.fas.org/dod-101/sys/ac/row/lca.htm)
  - Same text on GlobalSecurity (HTTP 402 to fetch).
  - **Conflict:** CEMILAC 2015 counts **344 LRUs**, not ">500". The three-bus figure is unconfirmed by any ADA/HAL document found.

**Bus control and the 1553 practice at ADE**
- [DIRECT-unnamed] ADE's ASIML-1553 paper describes the bus-controller schedule ("BCX") and ICD of "a typical combat aircraft":
  - **Operational phases with different schedules:** "Initialization, Operational Flight Programme, Post-flight Data Retrieval".
  - A minor frame is the GCD of message frequencies; the major frame is the LCM. Example: 4 minor frames per major frame.
  - Example message: LRU3 → BC, 4 words, "**Rate 12.5 Hz**", "Gives health status". Words 00–02 hold link, port and memory status codes (local/external failure codes in bits 00–07/08–15). Word 03 holds device temperature, 2's complement, °F, resolution 0.1.
  - "Six changes were made to the ICD" in five years.
  - Avionics data may be split across more than one bus "for increased reliability, isolation of unrelated messages, avoiding bus overloading".
  
  — [Trivedi (ADE), JOAST 63(4) 2011](https://joast.org/index.php/joast/article/view/598) (local PDF). LCA identification = [ASSUMPTION] (ADE author, developmental glass-cockpit fighter).
- [TRANSFER: generic 1553 architecture] The mission computer is normally the bus controller for all 1553 channels. No Tejas document assigns the BC role; see the Gaps. — [Alta 1553 tutorial via `data_pathway_and_formats.md` Q2](https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf)
- [DIRECT, snippet-level] The Stores Management System "integrates stores using weapon bus and provides interface to cockpit through OAC". Pylon interface hardware includes "a compact intelligent MIL-STD-1553B remote terminal (RT) with dual redundant processor". — [drdo.gov.in/drdo/avionics (search-index summary)](https://drdo.gov.in/drdo/avionics); [ADA Avionics page: weapons compatible with "MIL-STD-1760C"](https://www.ada.gov.in/images/sys.htm)

**DFCC, air data and the flight-control data path**
- [DIRECT] "The Digital Flight Control Computer (DFCC) is the heart of the flight control system, which interfaces with cockpit controls, sensors, actuators, and also the onboard avionics system". Fig. 1 shows **DFCC → MIL-STD-1553 → CDR, GUH, FTI**. — [Raveendran & Prabhu, RTO-MP-SCI-162-14](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)
- [DIRECT] DFCC internals:
  - Each of the 4 channels has five PWBs.
  - The **Digital Module** contains "CPU, Memories, Transputer, Watch dog Monitor, **1553B**, RS 422, D/A and A/D, Serial Controller (SILC) and **Cross Channel Data Link**".
  - The Analog Modules drive "five primary actuators, six secondary actuators" and interface the FCS sensors.
  - The Power Supply Module has monitoring circuits.
  - "DFCC contains **23 sub systems in each channel**" (92 in total).
  
  — [Santhiseela & Janarthanan (ADE), JOAST 57(4) 2005](https://joast.org/index.php/joast/article/view/782)
- [DIRECT] Further FCS facts:
  - Four ADCs on RS-422 to their DFCC channels.
  - FCS outputs include "1553B avionics data".
  - 12.5 ms frame; multi-rate scheduler.
  - BIT types: continuous, pilot-initiated and maintenance.
  - Ground test equipment connects through a transputer Serial Peripheral Interface Link.
  
  — [Kala (ADE), JOAST 67(2A) 2015](https://joast.org/index.php/joast/article/view/317). The DFCC "interfaces with pilot display elements like the MFDs through MIL-STD-1553B multiplex avionics data buses and RS-422 serial links" — [tejas.gov.in FBW page (archived), via `tejas_airframe_aero_fcs.md` Q3](https://web.archive.org/web/20180102040737/http://tejas.gov.in/technology/fly_by_wire.html)
- [DIRECT] "The airdata algorithm output are also sent for display on the head-up-display and on the get-U-home panel … a single working sensor can provide the required information". — [Rajalakshmi et al., DSJ 56(1) 2006](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863)
- [TRANSFER: HAL trainer (HJT-36 class) ADC, not Tejas] An indigenous ADC output on **ARINC-429 refreshes at 20 Hz**; onboard FTI recorded it at **64 Hz**. — [Meharu & Kuttieri (HAL ARDC), JOAST 67(2A) 2015](https://joast.org/index.php/joast/article/view/331) (local PDF). This shows the Indian practice that ADC → avionics outputs run well below the 80 Hz DFCC frame.

**Utility management: the electronic units**
- [DIRECT] "Four microprocessor based Electronic Units (EUs) monitor and control the onboard General Systems such as Engine, Electrical, Hydraulic, Fuel and Environmental Control Systems (ECS). In the production version, these functionalities would be combined thereby reducing the number of Electronic units to two." Tejas has a "'brake by wire' system controlled by the **Digital Hydraulic Electronic Unit (DHEU)**". — [Raveendran & Prabhu 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf). This upgrades the earlier "search-index excerpt" in `tejas_utility_systems.md` KQ7 to a read primary source.
- [DIRECT] Production EU names:
  - "**HEEM - EU**" (Rs 220 M engineering-change line) — [ADA AR 2015-16 p. 79](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf).
  - "**BHEEM** version 1.9.08 improved version trials". "A new functionality has been introduced in BHEEM software to control braking for shore and deck tyre pressure separately". "Interface requirements for BHEEM and ECFM finalized" (Navy) — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) (OCR).
  - "Location and envelope of Environmental Control and Fuel Monitoring (ECFM) unit was finalised" (Mk2) — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf).
  - [ASSUMPTION] Expansions: HEEM = Hydraulic/Electrical/Engine Monitoring-type EU, and BHEEM = Brake + HEEM. Neither expansion is published; the reasoning is the four-into-two merger, DHEU brake-by-wire, and braking control in BHEEM software. Validate with ADA.
- [DIRECT] ADA: "Computer Controlled Utility System & Management System (USMS) with dual redundant Processor". CEMILAC: "dual redundant processor based utility services management systems". — [ADA sys.htm](https://www.ada.gov.in/images/sys.htm); [JOAST 67(2A) CEMILAC](https://joast.org/index.php/joast/article/view/325)
  - [ASSUMPTION] "USMS" is the generic name for the BHEEM-EU + ECFM-C pair.

**Engine control and monitoring interfaces**
- [DIRECT] The IN20 has a FADEC. The onboard ECMS "Provides real time Engine Status in the Cockpit and Logs the Engine Usage Data to Compute Life Usage Indices of Life limited Parts. It also tracks Vibration Monitoring System". — [ADA Propulsion page](https://www.ada.gov.in/images/ps.htm)
- [DIRECT-part] HAL SLRDC Centralised Warning System:
  - 2 Display Units + 1 Electronic Unit; 30 RED/AMBER legends; audio tones;
  - voice warnings for "AOA Exceedance, Low altitude, Canopy unlock & Under carriage extension";
  - fire-warning lamp interface with "unmutable red tone"; master-alarm flasher;
  - "Capable to receive **ARINC/Discrete signals from FADEC Engine warning Interface for health monitoring**";
  - interfaces: **ARINC-429 + 30 discrete signals**; MIL-STD-411C alerting.
  
  — [DDP: Centralized Warning System (CWS), HAL](https://www.ddpmod.gov.in/en/resources/products/centralized-warning-system-cws) (local text). Tejas fitment is **probable**: ADA's LCA budget has "Centralised Warning System" (Rs 52.5 M) and "CWS hardware improvements". The FADEC interface is consistent with the F404-IN20, but it is not proof of fitment: other HAL types such as the IJT and Hawk also have digital engine controls.
- [Gap] Whether the FADEC is a 1553 RT or talks ARINC-429 to the OAC/utility EU is not public. A generic vendor note says military FADECs "will use a MIL-STD-1553 bus" (snippet-level, Pickering whitepaper). The F/A-18C engine words reached the mission computer from a separate Signal Data Computer — [NAWCADPAX/RTR-2001/1 Table E-3](https://archive.org/details/DTIC_ADA407860) [TRANSFER].

**Navigation and other LRUs**
- [DIRECT, secondary] SIGMA 95N INGPS ordered for Su-30 and Tejas (2008) — [DefenceTalk, via `tejas_airframe_aero_fcs.md` Q5](https://defencetalk.com/india-orders-over-one-hundred-sigma-95-navigation-systems-14894). AHRS from an Indian vendor flight-tested on LSP5 — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf).
- [DIRECT-part] HAL Korwa G3INS: roll/pitch 0.1°, true heading 0.1°, magnetic heading 1.5° RMS, horizontal velocity 1 m/s, 1 nm/h, angular rate to 400°/s. Platform not named. — [DDP G3INS](https://www.ddpmod.gov.in/en/resources/products/g3ins-gps-glonass-gagan-ins-system)
- [DIRECT] Mk1A is equipped with "AESA Radar, EW suite …, Digital Map Generator (DMG), Smart Multi-function Displays (SMFD), Combined Interrogator and Transponder (CIT), Advanced Radio Altimeter". — [DDP LCA Tejas page](https://www.ddpmod.gov.in/en/resources/products/lca-tejas)
- [DIRECT-part] HAL Korwa I-DMG works "based upon commands and information received via the **MIL-STD-1553B multiplex Data Bus**". Video out: DVI-D, STANAG 3350 RGsB and **ARINC 818**. — [DDP I-DMG](https://www.ddpmod.gov.in/en/resources/products/i-dmgindigenous-digital-map-generator)
- [DIRECT-part] HAL SLRDC DACS-2300A was "derived from … Audio Management Unit IJT, LCA":
  - digital I/O "MIL STD 1553B, ARINC 429, ETHERNET & USB";
  - self-test "POST, IBIT and CBIT";
  - interfaces to "the Cockpit Voice Recorder and Voice Data Recorder".
  
  ADA AR 2021-22 says an indigenous DACS for Mk1A was completed. — [DDP DACS](https://www.ddpmod.gov.in/en/resources/products/digital-audio-control-system-dacs-2300a-series); [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf)

**Mk1A and Mk2 changes**
- [DIRECT] Mk1A:
  - "Development of Mission Computer hardware and Smart MFD are in progress at HAL with support from ADA" (2018-19).
  - Critical design reviews of "AESA Radar, EW Suite, Mission Computer, DMG and SMFD" completed (2021-22).
  - Existing OAC software was migrated to a new Ada compiler and VxWorks.
  - "Version_0" / "Version_1" avionics software builds.
  - Global specifications and software ICDs prepared for AESA, EW, CIT, MC, DMG and SMFD.
  
  — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf); [2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf); [2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf) (OCR)
- [DIRECT, snippet-level] A HAL MCSRDC brochure lists "Mission Computers for LCA Mk1A, DARIN III, Mirage 2000 I/TI, Hawk-I, Hawk Mk 132, MiG-29K, IJT", plus a HUMS ground station for LUH/UH-M. — [fliphtml5 "Mission Systems Development at HAL" (403 to fetch)](https://fliphtml5.com/ufnff/rjyv/Mission_Systems_Development_at_HAL)
  - Mistral Solutions (AXISCADES) received an ≈₹80 crore order to manufacture Mk1A Mission Computer and SMFD hardware, plus an ≈₹25 crore single-board-computer order (Feb 2026) — [The Machine Maker](https://themachinemaker.com/news/axiscades-technologies-limited-secures-₹80-crore-avionics-hardware-order-for-lca-mk1a-programme/) (trade press).
  - **Conflict:** an IDRW commentary says the OAC/mission computer is "designed by ADE, produced by HAL". The ADA site says ADA designed the OAC. Treat ADA as authoritative for Mk1, and HAL (MCSRDC) for the Mk1A MC hardware.
- [DIRECT] Mk1A DFCC: "Quadraplex Power PC based Processor, high speed autonomous state machine based I/O controller … DO178C level-A" (first flight Feb 2024) — [`tejas_airframe_aero_fcs.md` Q3](https://www.ajaishukla.com/2024/02/tejas-fighter-flies-with-new-digital.html). HAL–BEL contract (Dec 2021): 20 types of LRUs including DFCCs, ADCs, weapon computers, RWR and HUD LRUs, 2023–2028 — [Airforce Technology](https://www.airforce-technology.com/news/hal-signs-contract-with-bel-tejas-mk1a/).
- [DIRECT] Mk2:
  - "Committee Report for High Speed Ethernet Interface released. Committee agreed to go ahead with **Time Sensitive Network (TSN)**."
  - "Development of Mission Management and Display Computer (MMDC) was initiated at RCI".
  - BEL to develop 6 avionics LLRUs.
  
  — [ADA AR 2020-21 §9.1.11](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf) (OCR). An older report on Mk II mentions AFDX-based back-up avionics (secondary, snippet-level; Defense Industry Daily 403).

**Avionics integration and test rigs (where faults are reproduced)**
- [DIRECT] ADA avionics rig: evaluates "warning philosophy" and SMS "Timing, data latency"; acts as a "test facility for trouble-shooting/fault diagnosis and rectification up to cassette/module level"; has "Provision to create and investigate fault reported during flight".
  - Dynamic Avionics Integration Rig (DAIR): "Digital Avionics Systems of LCA integrated & tested under dynamic conditions in distributed software environment".
  - Weapon integration rig: "hardware-in-loop simulation, error injection and data acquisition".
  
  — ADA "Avionics & Weapon Systems Test Facilities" page ([likely URL](https://www.ada.gov.in/images/Systems%20Integration%20facilities.htm), which returned HTTP 500 at writing; read from the local copy `research_sources/indian_fleet/ada/Systems_Integration_facilities.htm.txt` saved by an earlier Phalanx researcher)
- [DIRECT] Further rigs and test equipment:
  - Iron Bird (hydraulics, undercarriage, real actuators, DFCC, ADCs, OAC, 6-DOF model).
  - FTI integration rig ("about 1500 parameters"; PCM decommutation; "Playback facility for Flight Data Recorder (FDR)").
  - ETS/AETS with fault insertion; AIRDATS/AIRDATS-E.
  - IV&V lab: "7 safety critical and 23 mission critical software systems".
  - Budget lines for "Ground Checkout System", "Automatic Test Equipment Complex (ATEC)", "STTE" and "Maintenance Simulator".
  
  — [ADA IFCS & FT facilities](https://www.ada.gov.in/images/Other%20Integration%20facilities1.htm); [Kala 2015](https://joast.org/index.php/joast/article/view/317); [ADA IV&V](https://www.ada.gov.in/images/ivv.htm); [ADA AR 2015-16 pp. 76–79](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf)
  - **Conflict:** CEMILAC counts 33 embedded software systems; ADA IV&V counts 7 + 23 = 30 evaluated.

### Inferences
- [ASSUMPTION; validate against any Tejas ICD extract] **A defensible synthetic Phalanx bus topology:**
  - **AV-MUX-1 (mission):** BC = OAC/MC; RTs = INS/GPS, displays (SMFD/DMG), radar, EW, CIT, DACS.
  - **AV-MUX-2 (vehicle systems):** BC = OAC; RTs = DFCC (one 1553 subsystem per channel), FADEC/ECMS gateway, BHEEM-EU, ECFM-C, SSDU, CWS gateway.
  - **WPN-MUX:** SMS weapon bus with pylon RTs.
  - **Bus monitors (listen-only):** crash data recorder and HUMS DAU on AV-MUX-2 (and AV-MUX-1). This follows the NFTC figure (DFCC → 1553 → CDR) and the F-16 DAU/F/A-18 MSDRS bus-monitor precedent in `data_pathway_and_formats.md` Q3.
  - **Point-to-point:** CWS takes ARINC-429 and discretes; ADC → DFCC is RS-422; DFCC channels use the CCDL.
  
  This matches "three 1553B buses" and the separate weapon bus. Label it as synthetic in the Phalanx ICD.
- [ASSUMPTION] **The utility "health" path the generator should emulate.**
  1. Sensors feed the utility EUs (BHEEM-EU, ECFM-C) and the FADEC/ECMS.
  2. These send health and status words on 1553 to the OAC.
  3. The OAC drives CWS legends, MFD pages and SSDU, and logs faults for post-flight retrieval (its MPRU function).
  4. The ECMS keeps its own usage log.
  5. The CDR and the Mk1A HUMS DAU tap the buses.
  
  This reproduces two realistic error modes. Data can be recorded but not displayed (the F-35B case in `maintenance_records_and_events.md` Q3), and a warning can be displayed without an underlying fault.
- [ASSUMPTION] Versioned dictionary design should expect frequent ICD changes. ADE reports six ICD changes in five years, and the ADA ARs show software-version-driven envelope and behaviour changes (DFCC v7307 etc.). Version tags (OAC/DFCC/FADEC/EU software) belong in every sortie header.

### Gaps
- Number, names and allocation of Tejas 1553 buses; which unit is BC/back-up BC; RT addresses and message rates; whether the FADEC/ECMS is a 1553 RT or an ARINC-429 source; the utility EU (BHEEM/ECFM) I/O lists. No ADA/HAL document found.
- HEEM/BHEEM acronym expansion. Whether the ECMS is a separate LRU, FADEC software, or part of an EU.
- CWS legend list (30 legends) and the caution/warning logic.
- Any Mk1A Ethernet/Fibre Channel use: only Mk2 TSN is documented; Mk1A LRUs (DACS, DMG) have Ethernet/ARINC 818 ports, but use on Tejas is unconfirmed.

---

## Q2. Recording and download: crash data recorder, MPDRU, digital video recorder, flight-test instrumentation and telemetry, Mk1A HUMS, ground/debrief software, maintenance trainer, and the aircraft → squadron → BRD/HAL/ADA data path

### Takeaway
Public Tejas evidence confirms these recording and download elements, but not their formats or parameter lists:
- **On board:** a **Crash Data Recorder** that receives DFCC data over 1553; a **Mission Preparation & (Data) Retrieval** function, now inside the OAC; a **Video Digital Recorder**; the **ECMS usage log**; and FTI on test aircraft (≈1,500 parameters, DAS + selected-parameter telemetry + DRU, 12 real-time monitoring stations at NFTC).
- **Mk1A HUMS.** ADA started it in 2018-19 and finished design studies. In 2020-21 vendor selection was complete and the PO was "being placed". In February 2026 Park Controls & Communications (PCC) publicised a production order for **124 PCAMi-1000 HUMS data-acquisition units**. These replace a US-imported HUMS DAU and were CEMILAC-cleared about 10 months earlier.
- **PCAMi-1000.** It is a field-configurable, modular DAU with Ethernet master–slave expansion, capturing data, audio and video. Snippet-level: RTD, thermocouple, pressure, vibration and 1553/ARINC inputs.
- **Not public:** the HUMS scope (engine, structure or utility), the CDR vendor and standard, the CDR parameter count, and the MPDRU media.
- **Ground side:** an ASMS maintenance/diagnostic simulator built by the LCA ILS team; an ADE expert-system Automatic Fault Diagnosis System (AFDS) for the DFCC; ground check-out and ATE complexes; a Mk2 Aircraft Maintenance Terminal. IAF fleet records run in e-MMS, IMMOLS and the IAF–HAL "Havai" portal.

The end-to-end aircraft → squadron → BRD/HAL/ADA data flow is not described publicly. It has to be modelled on F/A-18 IECMS, F110 EMS and F-35 ALIS precedents.

### Cited Findings

**Crash data recorder, MPDRU, video**
- [DIRECT] ADA AR 2015-16, FSED Phase 2 "Avionics – other items":
  - "Mission Preparation & Data Retrival Unit" Rs 24,796,222 (Rs 22,980,789 the year before);
  - "Crash Data Recorder" Rs 51,552,964 (Rs 47,319,964);
  - "Centralised Warning System" Rs 52,511,749;
  - next line: "Balance stage payment with: HAL-MCSRDC".
  
  Engineering change orders: "Video Digital Recorder" Rs 171,066,521; "CWS hardware improvements" Rs 29,918,812. The **Navy** FSED Phase 1 investments have their own lines: MPDRU Rs 1,027,563; Crash Data Recorder Rs 11,785,723; "Centralised Warning Panel – CWP/CWS" Rs 10,644,750; "Engine Health Monitoring" Rs 57.5 M. — [ADA AR 2015-16 pp. 75–79 (AF FSED Ph 2), pp. 87–89 (Navy FSED Ph 1)](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf) (local text)
- [DIRECT] The MPRU function has since been absorbed: the OAC "combines the functions of … mission preparation and retrieval unit". — [tejas.gov.in OAC](http://web.archive.org/web/2015/http://www.tejas.gov.in:80/technology/open_architecture_computer_for_avionics.html)
- [DIRECT] DFCC → MIL-STD-1553 → **CDR**, GUH, FTI (Fig. 1). — [Raveendran & Prabhu 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf). After the Nov 2025 Dubai crash the IAF was reported to be retrieving the "flight data recorder (FDR) and cockpit voice recorder" — [Tribune](https://www.tribuneindia.com/news/india/pilot-killed-in-tejas-crash-at-dubai-show/amp) (press).
- [DIRECT-part; Tejas fitment unconfirmed] HAL Avionics Division, Korwa, makes:
  - an **SSFDR/CVFDR** for fixed- and rotary-wing aircraft;
  - a deployable FDR;
  - a "Fly By Wire Data Acquisition Unit (FBW-DAU)";
  - special test equipment for FDRs.
  
  "LCA" appears in its western-origin avionics list. — [HAL Avionics Division Korwa](https://hal-india.co.in/backend/production-unit/avionics-division-korwa/)
  - A CEMILAC type approval (TA-1849) covers an SSFDR of 3 LRUs: Data Acquisition Unit, Recording Unit, Control & Indication Unit. Software by BAeHAL, hardware by SLN Technology. (snippet-level; drdo.gov.in inaccessible) — [TA-1849](https://drdo.gov.in/drdo/sites/default/files/2021-10/TA-1849.PDF)
  - HAL's DFDR: crash-proof memory "as per ED-112"; 25 h data, 2 h × 4-channel audio; ARINC-429, ARINC-717, Ethernet, RS-422/232; ED-112A — [DDP DFDR](https://www.ddpmod.gov.in/en/resources/products/dfdrdeployable-flight-data-recorder).
  - These give the **Indian recorder design envelope** (ED-112A, 25 h loop, 429/717/Ethernet inputs). They do not establish what Tejas carries.
- [TRANSFER: HAL Jaguar DARIN III, designed at MCSRDC] The upgrade avionics include a "Mission Computer (MC), Engine and Flight Instrument System (EFIS), Solid State Digital Video Recording System (SSDVRS), Solid State Flight Data Recorder (SSFDR)". This is a contemporary HAL fighter avionics fit with separate video and flight-data recorders. — search-index summary of HAL statements ([DefenceTalk](https://defencetalk.com/hal-carries-out-maiden-flight-of-upgraded-indian-jaguar-aircraft-45740)) (snippet-level)

**Flight-test instrumentation and telemetry**
- [DIRECT] FTI:
  - integration rig "Acquires about 1500 parameters from various aircraft systems";
  - telemetry front end; PCM decommutation; GPS time display; FDR playback;
  - on-board FTI = Data Acquisition System + real-time telemetry "for selected parameters" + Data Recording Unit;
  - "telemetry ground facility with twelve real time monitoring stations".
  
  — [ADA facilities](https://www.ada.gov.in/images/Other%20Integration%20facilities1.htm); [ADA NFTC](https://www.ada.gov.in/images/nftc.htm)
- [DIRECT] Further FTI facts:
  - "Advanced Subminiature Telemetry System" (TD project, 2015-16).
  - "Feasibility studies to reduce wiring requirements of telemetry during flight tests" (2018–22).
  - Budget lines "AMCs Telemetry", "FTC_Telemetry Equipment AMC", "FTC_Telemetry Bandwidth Charges" (2021-22).
  - Real-time telemetry linked remote trial sites to NFTC via INSAT/fibre and Leh–Pathankot–NFTC (press).
  - Voted q, Nz and δe are telemetered in real time.
  
  — [ADA ARs](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf); [Livefist](https://www.livefistdefence.com/phase-2-of-lca-tejas-weapon-tests/); [JOAST 58(4)](https://joast.org/index.php/joast/article/view/741)
- [DIRECT] NFTC lesson (f): "Record More and Not Less Parameters … a few minor failures in the flight control system of which the cause could not be conclusively established due to lack of sufficient data." — [Raveendran & Prabhu 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)
- [TRANSFER] Indian FTI rate anchors: HAL trainer FTI recorded ADC outputs at 64 Hz ([JOAST 331](https://joast.org/index.php/joast/article/view/331)). The F/A-18 HARV research data system recorded about 2,000 parameters at 10–800 samples/s in 10-bit PCM (see Q4 and Q7).

**Mk1A HUMS**
- [DIRECT] Programme status by year:
  - 2018-19 / 2019-20: "Development of Indigenous HUMS has been initiated. Design studies have been completed."
  - 2020-21: "Commercial process for vendor selection has been completed and Purchase Order is being placed."
  - 2021-22: "HUMS development to meet Mk1A requirements is being initiated"; budget lines "AF_Support Activity for HUMS" Rs 697,736 and "HUMS_AMC" Rs 199,758.
  
  — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf), [2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf), [2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf) (OCR)
- [DIRECT] PCC "has received a production order for **124 units** of its PCAMi-1000, a Health and Usage Monitoring System (HUMS) Data Acquisition Unit (DAU)" for the HAL-built Tejas Mk1A.
  - It is "an indigenous alternative to a highly versatile and sophisticated HUMS DAU solution that was earlier sourced through imports from the USA".
  - Order placed about 10 months after CEMILAC clearance.
  - Claimed benefit: "reduces replacement cycles for faulty sub-systems from several months to hours".
  - Future platforms: Tejas Mk2, AMCA, TEDBF.
  
  Published **4 Feb 2026** (page metadata). — [Aviation & Defence Universe](https://www.aviation-defence-universe.com/pcc-advances-indigenous-hums-capability-with-pcami-1000-production-order)
- [DIRECT, vendor] "PCAMi-1000: PARK Compact Avionics Module for Instrumentation … rugged Data Acquisition Unit … also serves as a key support unit for Health and Usage Monitoring Systems (HUMS) in flight vehicles … Field Configurable: proprietary bus architecture and pluggable modules … **Master-Slave Distributed Architecture: Supports seamless integration via Ethernet** … collecting and processing data, audio, and video". PCC also makes PCM encoders for FTI (PCM-32S: 32 analog channels, 12-bit ADC, 3 RS-422 ports, ≤2 Mb/s). — [Park Controls, Air products](https://www.parkcontrols.com/industries/air) (local text)
  - (snippet-level) "RTD, thermocouple, pressure and vibration" inputs; "MIL-1553 and ARINC" bus inputs; 3/6/9/13-slot chassis; "can be configured as a health and utility management system" — [aerospace-technology.com PCC profile (dead link)](https://www.aerospace-technology.com/?p=18604).
- [Inference flagged] 124 units does not equal the 83 (73 + 10) aircraft of the 2021 Mk1A contract. The 2025 contract (68 + 29 = 97) brings the total to 180. Spares, rigs or a partial batch could explain 124; no source says.

**Ground, debrief and maintenance-training software**
- [DIRECT] ASMS (Aircraft Systems Maintenance Simulator):
  - "Defect analysis simulation in ASMS imparts analytical skills to reduce down time for rectification";
  - can function as a "'Job Performance Simulator' and Diagnostic Simulator";
  - courseware by the "integrated Logistics Support (ILS) Team of Light Combat Aircraft Programme".
  
  — [ADA ASMS page (archived 2021)](http://web.archive.org/web/20211123033754/https://www.ada.gov.in/images/asms.htm) (local copy)
- [DIRECT] ADE's **Automatic Fault Diagnosis System (AFDS)** for the LCA DFCC is a ground expert system (generic expert-system shell):
  - diagnoses faults "in various subsystems (92 subsystems)", "channel wise, subsystem level", from test results produced by a Testing Services tier;
  - failed test-step numbers map to knowledge-base antecedents through per-subsystem base offsets ("IDC"; e.g. right inboard elevon subsystem IDC = 3300);
  - outputs "Block.dat" (failed functional blocks) and "Mon.dat" (failed monitoring lines);
  - "independent of Test Facility and Test Equipment".
  
  — [JOAST 57(4) 2005](https://joast.org/index.php/joast/article/view/782); [JOAST 69(1A) 2017](https://joast.org/index.php/joast/article/view/261)
- [DIRECT] Mk2: "Model of aircraft maintenance terminal (AMT) has been finalized". Stores coding is configurable through the LAD, BDU or AMT. — [ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf)
- [DIRECT] IAF records systems: e-MMS (paperless since Apr 2020), IMMOLS, the IAF–HAL "Havai" e-portal, and AFNET — [`indian_fleet_platform_relevance.md` KQ6](https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf). No public statement says e-MMS ingests on-board data.
- [DIRECT] Test-fleet maintenance by ADA: "Aircraft and Facility Maintenance for LCA AF Mk1 (Tejas)"; 9 aircraft maintained; 4,499 flights as of 23 Mar 2020. — [ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf)

**Precedents for the post-flight data path (officially released)**
- [TRANSFER: F-16/F110 EMS, Turkish AF and GE papers in AGARD-CP-448]
  - The EMS stores faults on the **data transfer cartridge** via the mux bus.
  - The ground station sits at the Aircraft Maintenance Unit "adjacent to the flightline". Exceedance, fault and pilot-initiated data are reviewed there.
  - Trend and parts-life data go to the base Engine Management Branch, then to the central system (MEETS).
  - Pilot-initiated save: "12 pre-event data (6 seconds) and 4 post event data (2 seconds) scans", i.e. 2 Hz scans.
  
  — [AGARD-CP-448 papers 11 and 21](https://archive.org/details/DTIC_ADA203800) (local text)
- [TRANSFER: F/A-18 IECMS] MSDRS tape (≈7 flights) → ECAMS ground station → Parts Life Tracking — [`addendum_engine_F404_F414_monitoring.md` Q1](https://archive.org/details/DTIC_ADA203800). [TRANSFER: F-35] PMD → SOU → CPE → ALOU — [`data_pathway_and_formats.md` Q5](https://www.gao.gov/products/gao-20-316).

### Inferences
- [ASSUMPTION] **Recommended Phalanx post-flight data path (synthetic):**
  1. **On the aircraft:**
     - **CDR**: continuous loop, ED-112A-class, bus-monitor of AV-MUX-2 + DFCC data, about 25 h loop.
     - **ECMS log**: LUI sums written twice per flight, exceedance snapshots, take-off record.
     - **HUMS DAU (PCAMi-1000-like)**: configurable analog + bus acquisition, vibration features, event bursts.
     - **OAC maintenance/fault log and mission data** (its MPRU function).
     - **DVR**: video.
  2. **At the squadron (flight line, minutes to hours after landing):**
     - download per sortie per recorder into a squadron ground station;
     - decode to engineering units with a versioned dictionary;
     - pilot debrief write-up;
     - BIT/HUMS-driven work orders (`maintenance_records_and_events.md` Q3).
  3. **Upward (days):**
     - e-MMS-like records, IMMOLS-like spares demand and Havai-like HAL exchange;
     - BRD/HAL ROH shop findings flow back;
     - ADA receives RFAs and engineering data via HAL for design fixes (ADA's RFA practice is [DIRECT] in the NFTC paper).
- [ASSUMPTION] The CDR is the "always recorded" baseline. HUMS and ECMS are the maintenance baseline. FTI is test-only. In the generator the sinks should be separate streams with different parameter subsets and rates (see the CSV sink columns), so the downstream AI faces the real problem of fragmented, partially overlapping sources.

### Gaps
- CDR vendor, standard (ED-112/ED-112A?), parameter count and list, sampling rates, loop duration and download interface; MPDRU/OAC data-retrieval media (cartridge? Ethernet?).
- HUMS scope (engine/structure/utility/avionics), sensor list, sample rates, download path, and whether it absorbs the ECMS function. The "earlier imported US DAU" model is unknown.
- DVR format. Squadron debrief/ground-station software. Whether e-MMS ingests any on-board data.
- FTI PCM/telemetry formats (IRIG 106 Ch4/Ch10 use is likely but not documented).

---

## Q3. BIT and fault reporting on Tejas (PBIT/CBIT/MBIT/IBIT per system, fault-code structure) and the closest officially released analogues

### Takeaway
**Tejas BIT is public only at the level of "types exist":**
- The DFCC has continuous, pilot-initiated and maintenance BIT. Sensors are BIT-tested from the DFCC before each flight, and actuators "perform BIT tests automatically from DFCC".
- The ADC has 90 % BIT coverage plus IEEE 1149.1 boundary scan.
- The DACS has POST/IBIT/CBIT; the 5 kW DC generator has BITE; the CWS has a lamp test.
- The prototype "FBW diagnostic test" at start-up took about ten minutes.
- The DFCC is organised as 23 diagnosable subsystems per channel (92 in total). ADE's ground Automatic Fault Diagnosis System maps failed test-step numbers to subsystems through per-subsystem base offsets (e.g. IDC 3300 = right inboard elevon). This is the only public hint of a Tejas fault-identification structure.

**No Tejas in-service fault-code list, USMS/FADEC BIT coverage or cockpit fault-list format is public.**

**Officially released analogues give a usable template:**
- F/A-18 IECMS: a 3-digit Maintenance Monitor Panel code, 44 engine codes + 231 others, each tied to troubleshooting trees.
- F-16/F110 EMS: up to 80 engine fault flags (the MFL); a PFL subset drives the avionics caution and master caution; faults are stored on the data transfer cartridge.
- HARV FCS BIT discretes.
- 1553 mode codes 3/19 for BIT initiate/read.
- NAMP: HMS BIT/CI codes drive work orders.
- S5000F Event/DetectionMechanism classes (with false-alarm rate).
- S1000D fault-isolation data modules (secondary sources only).

### Cited Findings
**Tejas (DIRECT)**
- DFCC BIT:
  - "continuous built-in-test (BIT) and pilot initiated BIT and maintenance BIT";
  - "Built-in-test features have been upgraded" for squadron operation and maintenance;
  - sensors "perform BIT tests from the DFCC to ascertain their health before each flight";
  - primary actuators "perform BIT tests automatically from DFCC";
  - ADC "Built-in-testability feature with 90% coverage", IEEE 1149.1.
  
  — [Kala, JOAST 67(2A) 2015](https://joast.org/index.php/joast/article/view/317)
- TD-1's first-flight start-up included a roughly ten-minute "FBW diagnostic test … green" — [Livefist, Dec 2025 (via `tejas_airframe_aero_fcs.md` Q3)](https://www.livefistdefence.com/25-years-on-my-recollections-of-the-1st-tejas-flight/).
- DFCC diagnosable structure and the ground AFDS (subsystem test-step IDC offsets, "Block.dat"/"Mon.dat" outputs, normal/error-page/auto modes showing all 92 subsystems' status) — [JOAST 57(4) 2005](https://joast.org/index.php/joast/article/view/782); [JOAST 69(1A) 2017](https://joast.org/index.php/joast/article/view/261).
- In-flight FCS failure experience: "no significant failures except for a channel dropout once in flight, which was reset immediately". Mundane systems (BMS, NWS, ECS) failed far more often than the IFCS. — [Raveendran & Prabhu 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)
- Air-data failures: sensors "voted out"; "multiple failures could cause certain events to be set in the control law" leading to reversionary laws — [DSJ 56(1) 2006](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863). After a departure, "the FCS may be in a failed state and air data will need to be re initialized … A reset should be able to clear such failures" — [AeSI FTG 2005](https://web.archive.org/web/20070928061842/http://www.csirwebistad.org/aesi/pdf/ftgseminar05/presentations/2005/HIGH_AOA_TEJAS.pdf).
- Utility and engine monitoring: the "advanced utility and health management system provides system health and warnings to the pilot through" the OAC — [tejas.gov.in Systems](http://web.archive.org/web/2016/http://www.tejas.gov.in:80/specifications/systems.html). ECMS logs usage and tracks vibration — [ADA ps.htm](https://www.ada.gov.in/images/ps.htm).
- [DIRECT-part] Self-test on likely Tejas LRUs:
  - DACS: "Self test - POST, IBIT and CBIT" ([DDP DACS](https://www.ddpmod.gov.in/en/resources/products/digital-audio-control-system-dacs-2300a-series));
  - CWS: "Test facility to check the health of display unit lamps" ([DDP CWS](https://www.ddpmod.gov.in/en/resources/products/centralized-warning-system-cws));
  - 5 kW DC generator: GCU "with BITE" ([DRDO](https://drdo.gov.in/5-kw-brushless-dc-generating-system-lca-tejas-0), via `tejas_utility_systems.md`).
- [DIRECT, false alarms in Indian practice] On an IAF communication ATE, "94 LRUs did not match the ATE test pattern, though LRUs were serviceable" — [CAG 38/2015 (via `maintenance_records_and_events.md` Q3)](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf). An IAF officer's JOAST paper on 3-D audio warnings notes existing IAF warning tones/messages sit in 350 Hz–4 kHz and could be fed over 1553 to a warning unit — [JOAST 69(1A) 2017](https://joast.org/index.php/joast/article/view/215).

**Officially released analogues (TRANSFER)**
- **F/A-18A–D IECMS:**
  - nose-wheel-well Maintenance Monitor Panel shows a **3-digit code**; **44 engine codes and 231 codes for other systems**, each pointing into maintenance-manual troubleshooting trees;
  - IECMS logic sits in the mission computer (continuous, "as required", life usage);
  - exceedances "should persist for several computer iterations";
  - event record 5 s pre + 25 s post (Navy) or + 35 s post (CF); take-off record 6–10 s; pilot record button.
  
  — [Hess, AGARD-CP-448 paper 2](https://archive.org/details/DTIC_ADA203800); [Paré & Muir 1998](https://archive.org/details/DTIC_ADA347270); RAAF troubleshooting rule for MMP codes 709/759 — [ARL-PROP-TM-439](https://archive.org/details/DTIC_ADA227757) (via `f404_in20_engine_model.md` Q9).
- **F-16/F110 EMS:**
  - "The ENS has the capacity for detecting/transmitting up to **80 different fault flags** … known as the **Maintenance Fault List (MFL)** … A small subset … **Pilot Fault List (PFL)** … faults which warrant caution messages";
  - the EFCC assigns codes and stores faults; a PFL item illuminates the avionics caution → master caution; F-ACK shows the fault on the DED;
  - "data transfer cartridge … can be taken to a loader-reader unit";
  - about 70 % of real faults were correctly isolated to the LRU in initial service;
  - on the F101/B-1B the "potential" false-alarm rate fell from 25 per flight to 2 per flight.
  
  — [AGARD-CP-448 papers 11 and 21](https://archive.org/details/DTIC_ADA203800) (local text, `engine_data/f404_monitoring/DTIC_ADA203800.txt`)
- **F/A-18 HARV research data stream (40 samples/s discretes):**
  - per-channel "CH1–CH4 … PROCESSOR OFF / STICK FAIL / AOA FAIL / PITCH CAS FAIL / DEGRADED / SERVO FAIL / SOV OPEN";
  - "QUAD SENSOR FAIL", "DUAL PORT RAM INVALID", "MUX BUS INVALID";
  - FCS BIT controls: "BIT INITIATE/TEST STOP", "MAINT TEST FUNCTIONS", "INFLIGHT", "NOSE WHEEL STEERING BIT", "CLEAR BLIN CODES SIGNAL";
  - "MASTER CAUTION", "FCS CAUT FLAG", "RESET OK".
  
  — [NASA CR-201670 App. A](https://ntrs.nasa.gov/citations/19970014822) (local OCR parse)
- **1553 BIT access:** mode code 3 = Initiate Self Test, 19 = Transmit BIT Word. Status-word Subsystem Flag and Terminal Flag carry LRU health. — [`data_pathway_and_formats.md` Q1 (Alta tutorial, UEI)](https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf)
- **USN maintenance usage of BIT:**
  - HMS "Built In Test/Condition Indicator (BIT/CI) data in numeric codes, such as … FAME Maintenance Status Panel codes";
  - Maintenance Control reviews HMS BIT/CI after each flight and issues Work Orders;
  - example MSP codes ("MSP 646 L CHANNEL A FADEC TERMINAL FAIL", FADEC channel B fault codes "009 078 304");
  - F-35 false-alarm workflow: defer and monitor for 3 consecutive flights.
  
  — [NAMP and F-35 supplement via `maintenance_records_and_events.md` Q3](https://www.navair.navy.mil/sites/g/files/jejdrs536/files/document/%5Bfilename%5D/CNAFINST4790.2E%20w%20ama%204-7.pdf)
- **S5000F:**
  - Event class: eventIdentifier, eventOcurrenceDateTime, eventGroup, eventSeverity, eventDescription, eventConfirmedStatus;
  - DetectionMechanism with type (e.g. BIT) and "detectionMechanismFalseAlarmRate";
  - P-BIT/C-BIT/I-BIT definitions.
  
  — [S5000F Issue 4.0](https://umbraco.asd-europe.org/media/cbclxuxp/s5000f_issue_4-0.pdf) (via `maintenance_records_and_events.md` Q2)
- **S1000D (secondary, snippet-level):**
  - the Fault data module "provid[es] a dedicated structure for Fault Isolation procedures";
  - fault reporting distinguishes **detected, isolated, observed and correlated** faults;
  - sample "observed fault" modules list fault codes with descriptions.
  
  — [Adobe FrameMaker S1000D help](https://help.adobe.com/en_US/framemaker/s1000d/WS9ad62b8fb4f8a997-4a02f1412e146f7d2a-8000.html); [S1000D tutorial (TPSMG, SlideShare)](https://www.slideshare.net/slideshow/s1000d-tutorial/38915276); [docuneering demo DM](https://www.docuneering.com/s1000d/demo/pdf/DMC-S1000DLIGHTING-AAA-D00-00-00-00AA-413A-A_007-00_EN-US.pdf). The S1000D specification itself was not read.
- [snippet-level; USAF e-publishing returned 403, so releasability not verified; sanity-check only] An Edwards AFB instruction pairs F-16 engine event numbers with MFL/PFL codes: "Event 1020 (MFL/PFL 028) Engine Stall", "Event 1190 (MFL/PFL 042) Low Main Oil Pressure". It says engine data are downloaded and screened after every high-AoA flight. — [Edwards AFBI 21-102](https://static.e-publishing.af.mil/production/1/edwardsafb/publication/edwardsafbi21-102/edwardsafbi21-102.pdf)

### Inferences
- [ASSUMPTION; validate with ADA/HAL] **Recommended synthetic Phalanx fault-code structure (clearly labelled synthetic):**
  - `SSS-NNN` = subsystem block + fault number, echoing ADE's per-subsystem test-step offsets (IDC). Example: DFCC channel c, subsystem k → block 3000 + 100·k, step n.
  - Each code carries: detecting mechanism (PBIT/CBIT/MBIT/IBIT/exceedance), level (PFL = cockpit/CWS legend; MFL = maintenance-only), LRU suspect list with isolation confidence (F110 experience ≈70 % correct isolation at entry into service), latch/clear semantics, persistence count, and a false-alarm/NFF propensity.
  - Map each code to an S5000F Event + DetectionMechanism record. Keep a PFL/MFL split: CWS legends ≈30 visible to the pilot versus a larger MFL (F110: ≤80 for the engine alone; F/A-18: 275 MMP codes aircraft-wide).
- [ASSUMPTION] **BIT timing model:**
  - **PBIT** at power-up: minutes on early FBW (Tejas TD-1 ≈10 min), seconds to a minute on modern LRUs. Gate the "ready for taxi" state on it.
  - **CBIT** every frame, with persistence counters (IECMS "several iterations").
  - **IBIT/MBIT** only on the ground with WoW, producing ground-test fault logs (AFDS-like) that can disagree with in-flight CBIT ("can-not-duplicate").

### Gaps
- Tejas fault-code lists, the PFL/MFL equivalent, USMS/BHEEM/ECFM BIT coverage, FADEC BIT/fault-code format, ECMS exceedance thresholds, and the cockpit fault-display page format.
- S1000D primary text (Issue 5/6 fault information chapter) not read.

---

## Q4. Canonical parameter inventory (consolidated across all Phalanx notes, the NASA F/A-18 HARV CR-201670 catalogue and the F/A-18 IECMS/SDC 1553 word lists)

### Takeaway
**`parameter_inventory.csv` holds 189 logical parameters across 16 subsystem groups.** Each row has 33 fields:
- identity and subsystem;
- physical quantity and units;
- origin (sensor type and LRU, or computing LRU) and the measured/computed/inferred class;
- range, native resolution and recommended quantization;
- native, bus and recorder rates;
- redundancy;
- five sink flags (cockpit, crash recorder, ECMS/HUMS, maintenance download/MPDRU-OAC, FTI-only);
- validity/status flags; physical drivers; related parameters;
- texture mechanisms, with links to `sensor_residual_texture.md` / `empirical_dashlink_texture.md`;
- three rate-group fields (acquisition → bus → record);
- evidence tag, source URLs, and notes and conflicts.

**What the rows are built from:**
- Tejas-specific architecture and LRU facts dominate the FCS, air data, utility and warning rows.
- F404 sensor physics, IECMS/SDC bus words and recording rates fill the engine rows.
- HARV and F/A-18C word lists set the rate and validity conventions.

The CSV is ready to seed a versioned Phalanx parameter dictionary. Every bus/RT/word mapping must still be invented and labelled synthetic. Where no source gives a quantization, the CSV applies an [ASSUMPTION] rule: choose the LSB so steady-state σ is about 0.3–1.5 LSB, the range measured on DASHlink channels.

### Cited Findings
**Inputs consolidated (with what each contributed)**
- **Tejas FCS/air data** [DIRECT]: RSA ±300/±60 °/s, 0.005 °/s, 50 Hz; ASA ±13 g/±4.5 g, 2 mg/0.2 mg, 100 Hz; quadruplex inertial and pilot-command sensors; triplex air data; simplex heater currents; 4 ADCs with 4 transducers each (Ps 35–1300 mbar, Pt 35–2700 mbar, Pα/β 35–1500 mbar, 0.02 % FS); vanes with quad LVDTs ±45°; 12.5 ms frame; actuator facts. — [Kala 2015](https://joast.org/index.php/joast/article/view/317); [`tejas_airframe_aero_fcs.md` Q2, Q3, Q5](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863)
- **Engine** [TRANSFER: F404-400/-402]:
  - sensor types and ranges (FOCSI); MSDC resolution (N 16 rpm; T 1 K; PS3 0.5 psia; P5 0.06 psia) and aircraft 2σ precision (N1 154 rpm, N2 138 rpm, T5 2.0 K, PS3 1.2 psia);
  - IECMS recording rates (10 Hz: altitude, Mach, AoA, T0, T1, N1, N2, T56, P56, PS3, Wfm, PLA, A8; 1 Hz: Nz, oil pressure, vibration, fuel temperature, anti-ice valve, bleed door);
  - F/A-18C SDC → MC bus words (EGT °C, CDP psia, TDP psia, NL/NH rpm, T1 °C, oil pressure psid, nozzle %, Wfm pph, fuel inlet °C, T5 °C, per-tank corrected fuel quantities in lb; discretes: inlet ice, RLCS temperature high, bleed-air leak, bleed off);
  - 8 LUIs.
  
  — [Henry/Muir/Hess, AGARD-CP-448](https://archive.org/details/DTIC_ADA203800); [NAWCADPAX/RTR-2001/1 Table E-3 (approved for public release)](https://archive.org/details/DTIC_ADA407860); [`f404_in20_engine_model.md` Q3, Q9, Q12](https://ntrs.nasa.gov/citations/19940032893)
- **F/A-18C 1553 mux measurand list (20 samples/s test data system)** [TRANSFER]:
  - **ADC words** carry validity words (IAVAL3/IAVAL4) and double-word (MSW/LSW) altitudes; also local/true AoA, Mach, TAS/IAS, total and static pressure, ambient/total temperature, altitude rate, "fuel tanks pressurized" and "refuel probe extended" discretes.
  - **FCC-A words**: rates, accelerations, local/true AoA, stick/pedal, autopilot mode discretes.
  - **FCC-B words**: WOW, compressor-speed lockup, bleed doors, PLA, all surface positions, gear down-and-locked.
  - **SDC**: engine and fuel.
  - **INS**: narrow/wide-band rates, attitudes, velocities, position (MSW/LSW), accelerations.
  
  — [NAWCADPAX/RTR-2001/1 Table E-3](https://archive.org/details/DTIC_ADA407860) (local text)
- **F/A-18 HARV CR-201670 App. A** [TRANSFER; research aircraft]:
  - My OCR parse recovered **1,713 raw parameters for Flight 295**. The report says "approximately 2000 aircraft parameters" were telemetered.
  - By recording rate: 1 sps 2, 10 sps 283, 25 sps 505, 40 sps 656, 80 sps 192, 160 sps 34, 320 sps 36, 800 sps 5.
  - Regex classification of the OCR descriptions (approximate, ±10 %): ≈835 research pressure taps (10/25/320 sps); ≈300 FCS/RFCS status, command and BIT words (40/80 sps); ≈67 control/surface signals (40/80/160 sps); ≈58 INS/nav (40 sps); ≈49 engine/AMAD (40 sps); ≈48 air data (40–160 sps); ≈47 inertial/motion (40–800 sps); ≈32 fuel, ≈22 hydraulic/RLCS, ≈20 electrical, ≈22 cautions/advisories (all 40 sps); ≈29 structural loads/temperatures (40/160 sps).
  - **Production-aircraft system data (engine, fuel, hydraulics, electrical, gear, cautions) appear uniformly at 40 sps.** Research FCS internals and validity words are at 80 sps; surface positions, boom air data and CG accelerations at 160 sps; tail accelerometers at 800 sps.
  
  — [NASA CR-201670](https://ntrs.nasa.gov/citations/19970014822); local parse `research_sources/tejas_avionics/HARV_CR-201670_AppA_parsed_OCR.tsv`; HARV PCM words were 10-bit ([`candidate_airframe_modelling_data.md` Q9](https://ntrs.nasa.gov/api/citations/19980007172/downloads/19980007172.pdf))
- **Utility systems** [DIRECT + DIRECT-part + TRANSFER]: the per-system signal list of `tejas_utility_systems.md` Synthesis (b), carried row-for-row into the CSV with the same sources (DDP nodes, ADA LRU list, MIL-STD-704F, MIL-H-5440H, HARV) — [`tejas_utility_systems.md`](https://www.ddpmod.gov.in/node/8779)
- **Texture classes** [MEASURED]: quantisation LSBs (N1/N2 0.03125 %, EGT 0.5 °C, FF 8 lb/h, AoA 180°/4096, attitude 180°/16384, oil P 2.442 psi, oil T 1.343 °C), dropout/sentinel behaviour, validity gating, inverted discretes, clock artefacts — [`empirical_dashlink_texture.md` Q11(b)](https://c3.ndc.nasa.gov/dashlink/projects/85/)

**Inventory summary statistics** (computed from the CSV)

| Count | Value |
|---|---|
| Logical parameters (rows) | **189** |
| By subsystem | Engine 32 (+ 8 ECMS LUIs + 1 ground TAC); FCS 31; air data 20; avionics status/warnings/recorder/metadata 20; navigation 14; hydraulics 10; usage counters 10; ECS and life support 9; electrical 8; landing gear/brakes/NWS/chute 7; secondary power 6; fuel 6; ground-inspection bridges 6; fire 1 |
| By class | measured (analog/digital) 80; computed/derived 54; discrete 23; counters 20; events 6; ground inspection 6 |
| By evidence basis | DIRECT only 62; DIRECT + TRANSFER/ASSUMPTION 70; TRANSFER-led (no Tejas source) 44; TRANSFER + ASSUMPTION 4; ASSUMPTION only 9. Of these, 17 rows rest partly on DIRECT-part (Indian product, Tejas fitment probable) |
| Sinks (Y = evidenced, ? = assumed) | cockpit Y 72 / ? 44; crash recorder Y 93 / ? 56; ECMS/HUMS Y 89 / ? 25; maintenance download Y 108 / ? 67; FTI-only 3 |
| Acquisition groups | FCS80 49; LRU-internal 52; FADEC-internal 18; event 30; per-sortie 24; inspection 6; FTI 5; high-frequency raw 3 |
| Bus groups | AV25 37; AV50 polling the DFCC buffer (FCS40) 30; event 29; download 24; AV6.25 19; AV50 13; AV12.5 10; SLOW1 8; none 12; FTI 5 |
| Record groups | CDR16 29; CDR4 28; CDR4-8 13; CDR1 + HUMS 28; ECMS10 + CDR4 10; ECMS1 (+CDR1) 6; events 30; per-sortie 24 |
| Rows carrying a conflict note or a restricted-source flag | 62 (3 restricted-source flags) |

- [Inference] Expanding redundancy, the 189 logical rows correspond to well over 300 physical channels. Examples: 12 RSA, 8 ASA, 12 pilot-command, 16 ADC transducer, 12 vane-LVDT, 8 T5-probe and about 20 primary-surface position channels. Tejas FTI adds roughly 1,300 further test-only parameters (about 1,500 total).

**Compact inventory tables** (full detail in the CSV). Legend:
- Sinks: CP = cockpit; CDR = crash data recorder; ECMS/HUMS; DL = maintenance download (OAC log/MPDRU function); FTI-only. "?" = assumed.
- Rate groups: acquisition → bus → record (definitions in Q7).

**Engine (F404-GE-IN20)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `ENG.PLA` | Power lever angle | LVDT/RVDT (on -400: LVDT in MFC read by ECU) | measured | 0-130 (GI~18, FI 31, IRP 87, min AB ~9… [deg] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CDR ECMS/HUMS DL | TRANSFER |
| `ENG.N1` | Fan (LP) rotor speed | 2 eddy-current pickups counting 42 fan blades (f = 0.7 Hz/rpm) | measured | 0-115 % [rpm / %N1 (100% = 13,2…] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CP CDR ECMS/HUMS DL | DIRECT+TRANSFER |
| `ENG.N2` | Core (HP) rotor speed | separate winding on gearbox-mounted alternator (f = 0.239 Hz/rpm) | measured | 0-110 % [rpm / %N2 (100% = 16,8…] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CP CDR ECMS/HUMS DL | TRANSFER |
| `ENG.T1` | Compressor inlet total temperature (CIT) | single-element RTD in front frame, hot-air de-iced | measured | -54 to +149 (FOCSI -65..300 degF) [degC] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CDR? ECMS/HUMS DL | TRANSFER |
| `ENG.T25` | HPC inlet temperature | pneumatic transmitter to MFC on -400 (no electrical signal); electrica… | measured (FADEC-internal) | -54 to 280 [degC] | FADEC-INT -> none -> none | - | ASSUMPTION |
| `ENG.PS3` | Compressor discharge static pressure (CDP) | pressure transducer (FADEC); separate IECMS P3 transducer on -400 | measured | 0-500 [psia] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CDR ECMS/HUMS DL | TRANSFER |
| `ENG.P5` | Turbine discharge pressure (PT56) | pressure transducer | measured | 0-60 [psia] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CDR? ECMS/HUMS DL | TRANSFER |
| `ENG.T5` | Exhaust gas / LPT discharge temperature (EGT, T56) | 2 x 4-probe Type-K harnesses; ECU/FADEC averages good probes | measured (averaged) | 371-871 (700-1600 degF) [degC] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CP CDR ECMS/HUMS DL | DIRECT+TRANSFER |
| `ENG.T5.HARNESS_A` | T5 harness A average | 4-probe Type-K harness | measured (FADEC-internal) | 371-871 [degC] | FADEC-INT -> none -> none | ECMS/HUMS? DL? | TRANSFER+ASSUMPTION |
| `ENG.T5.HARNESS_B` | T5 harness B average | 4-probe Type-K harness | measured (FADEC-internal) | 371-871 [degC] | FADEC-INT -> none -> none | ECMS/HUMS? DL? | TRANSFER+ASSUMPTION |
| `ENG.WFM` | Main (core) fuel flow | turbine flowmeter | measured | 0-12,000 [lb/h] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CP? CDR ECMS/HUMS DL | TRANSFER |
| `ENG.WFAB` | Afterburner fuel flow | flowmeter (test) / FADEC demand (aircraft) [ASSUMPTION] | computed (FADEC demand) on aircraft; measured in FTI | 0-30,000 [lb/h] | FTI -> FTI PCM / telemetry -> FTI DRU | FTI-only | TRANSFER+ASSUMPTION |
| `ENG.A8` | Exhaust nozzle area / position | LVDT in VEN actuator (hydraulic-fluid cooled housing) | measured | 220-540 in2 [in2 or %] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CP CDR ECMS/HUMS DL | TRANSFER |
| `ENG.FVG` | Fan variable geometry angle | LVDT in FVG actuator | measured | 0-55 [deg] | FADEC-INT -> none -> CDR4 | CDR? ECMS/HUMS? DL? | TRANSFER |
| `ENG.CVG` | Compressor variable geometry angle | mechanical feedback to MFC on -400; electrical on FADEC [ASSUMPTION] | measured | -5 to 55 [deg] | FADEC-INT -> none -> CDR4 | CDR? ECMS/HUMS? DL? | TRANSFER |
| `ENG.AB_LIT` | Afterburner light (flame detector) | UV flame detector 200-270 nm | measured discrete | 0/1 [0/1] | FADEC-INT -> AV25 -> ECMS10 + CDR4 | CP CDR ECMS/HUMS DL | TRANSFER |
| `ENG.OIL_P` | Engine oil pressure | oil pressure transmitter in fan module | measured | 0-200 [ASSUMPTION] [psid] | FADEC-INT -> AV12.5 -> ECMS1 + CDR1 | CP CDR ECMS/HUMS DL | TRANSFER |
| `ENG.OIL_T` | Engine oil temperature | RTD [ASSUMPTION: existence inferred from generic practice] | measured | -54 to 180 [degC] | FADEC-INT -> AV6.25 -> ECMS1 + CDR1 | CP? CDR? ECMS/HUMS? DL? | ASSUMPTION |
| `ENG.OIL_LEVEL` | Engine oil tank level / low-level | liquid-level sensor (-400) | measured | 0-100 % / 0-1 [% or 0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | TRANSFER |
| `ENG.LUBE_DP` | Lube pump / filter differential pressure switch | differential pressure switch | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP? CDR? ECMS/HUMS DL | TRANSFER+ASSUMPTION |
| `ENG.CHIP` | Chip detector status (master electrical chip detector) | 7 magnetic chip detectors + NOAP sample fitting (-400, ground-inspecte… | inspection (-400) / measured discrete (F414-style) | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP? CDR? ECMS/HUMS? DL? | TRANSFER |
| `ENG.VIB.OVERALL` | Engine vibration, overall velocity (mid-frame) | piezoelectric accelerometer at mid-frame (ECMS 4 o'clock); raw >=2.5-1… | computed feature from measured raw vibration | 0-5 ips (full scale) [in/s (avg)] | HF -> SLOW1 -> ECMS1 (features); raw only FTI/test cell | CP? CDR? ECMS/HUMS DL | DIRECT+TRANSFER |
| `ENG.VIB.N1_1REV` | Engine vibration tracked at N1 1/rev | piezoelectric accelerometer at mid-frame (ECMS 4 o'clock); raw >=2.5-1… | computed feature from measured raw vibration | 0-5 ips (full scale) [in/s (avg)] | HF -> SLOW1 -> ECMS1 (features); raw only FTI/test cell | CP? CDR? ECMS/HUMS DL | DIRECT+TRANSFER |
| `ENG.VIB.N2_1REV` | Engine vibration tracked at N2 1/rev | piezoelectric accelerometer at mid-frame (ECMS 4 o'clock); raw >=2.5-1… | computed feature from measured raw vibration | 0-5 ips (full scale) [in/s (avg)] | HF -> SLOW1 -> ECMS1 (features); raw only FTI/test cell | CP? CDR? ECMS/HUMS DL | DIRECT+TRANSFER |
| `ENG.FUEL_INLET_T` | Engine fuel inlet temperature | RTD | measured | -40 to 120 [degC] | FADEC-INT -> AV6.25 -> ECMS1 + CDR1 | CP? CDR? ECMS/HUMS DL | TRANSFER |
| `ENG.IGN` | Ignition on | FADEC output state | computed discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP? CDR ECMS/HUMS DL | TRANSFER |
| `ENG.FADEC_STATUS` | FADEC channel-in-control / health status word | FADEC BIT (cross-channel compare, sensor/actuator monitors) | computed | - [bit-packed] | LRU-INT -> AV12.5 -> CDR1 + HUMS | CP CDR ECMS/HUMS DL | DIRECT+TRANSFER |
| `ENG.FAULT_CODES` | FADEC / ECMS maintenance fault list (codes) | FADEC/ECMS diagnostics | computed event | - [code] | EVT -> EVT -> EVT (on change) | CP CDR? ECMS/HUMS DL | TRANSFER |
| `ENG.FLAMEOUT` | Flameout detected / auto-relight active | FADEC logic: T5 < f(alt, PLA) and dN2/dt < threshold | computed discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | TRANSFER |
| `ENG.LIMIT_FLAGS` | Engine exceedance flags (N1/N2 overspeed, T5 over-temp, oil-pressure low, vibrat… | ECMS/FADEC limit logic with persistence | computed discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | TRANSFER |
| `ENG.THRUST_EST` | Computed engine thrust (take-off thrust check) | computed from P5 and nozzle position | computed | 0-20,000 [lbf] | ECMS10 -> none -> ECMS take-off record | ECMS/HUMS DL | TRANSFER |
| `ENG.BLEED_STATE` | Engine bleed off / bleed door / anti-ice valve state | valve position switches | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP? CDR? ECMS/HUMS DL | TRANSFER |

**Engine usage (ECMS)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `LUI.TYPE1` | Full N2 cycle (Type I: off -> intermediate -> idle) | computed from N2, PS3, T5/turbine temperature histories | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT+TRANSFER |
| `LUI.TYPE3` | Partial N2 cycle (Type III: idle -> intermediate -> idle) | computed from N2, PS3, T5/turbine temperature histories | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT+TRANSFER |
| `LUI.EFTC` | Equivalent full thermal cycles (HPT blade temperature cycles weighted by size) | computed from N2, PS3, T5/turbine temperature histories | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT+TRANSFER |
| `LUI.SRC` | Stress-rupture counts (HPT blade metal temperature) | computed from N2, PS3, T5/turbine temperature histories | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT+TRANSFER |
| `LUI.TAMP` | Time at intermediate or above | computed from N2, PS3, T5/turbine temperature histories | computed counter | cumulative [h] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT+TRANSFER |
| `LUI.PS3_FULL` | Full PS3 cycle (CDP near max allowed) | computed from N2, PS3, T5/turbine temperature histories | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT+TRANSFER |
| `LUI.PS3_PART` | Partial PS3 cycle (CDP reaches 85 % of max) | computed from N2, PS3, T5/turbine temperature histories | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT+TRANSFER |
| `LUI.EOT` | Engine operating time at or above ground idle | computed from N2, PS3, T5/turbine temperature histories | computed counter | cumulative [h] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT+TRANSFER |

**Engine usage (ground)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `USAGE.TAC` | Total accumulated cycles (USAF form, comparison metric) | computed from N2/PLA history | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | - | TRANSFER |

**Flight control (DFCC)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `FCS.RSA.P` | Rate Sensor Assembly body rate p | Rate Sensor Assembly (natural frequency 50 Hz) | measured (x4) + voted | +/-300 deg/s (roll) [deg/s] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR DL? | DIRECT |
| `FCS.RSA.Q` | Rate Sensor Assembly body rate q | Rate Sensor Assembly (natural frequency 50 Hz) | measured (x4) + voted | +/-60 deg/s (pitch) [deg/s] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR DL? | DIRECT |
| `FCS.RSA.R` | Rate Sensor Assembly body rate r | Rate Sensor Assembly (natural frequency 50 Hz) | measured (x4) + voted | +/-60 deg/s (yaw) [deg/s] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR DL? | DIRECT |
| `FCS.ASA.NZ` | Acceleration Sensor Assembly nz | force-balanced accelerometer assembly (natural frequency 100 Hz) | measured (x4) + voted | +/-13 g [g] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP CDR ECMS/HUMS? DL? | DIRECT |
| `FCS.ASA.NY` | Acceleration Sensor Assembly ny | force-balanced accelerometer assembly (natural frequency 100 Hz) | measured (x4) + voted | +/-4.5 g [g] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP CDR ECMS/HUMS? DL? | DIRECT |
| `FCS.VOTED.Q` | Voted pitch rate | median of 4 RSA channels | computed | +/-60 [deg/s] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR DL? | DIRECT |
| `FCS.VOTED.NZ` | Voted normal acceleration | median of 4 ASA channels | computed | -3.5 to +9 (envelope +8/-3.5; v7307: 8… [g] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP CDR ECMS/HUMS? DL? | DIRECT |
| `FCS.VOTED.DE` | Voted elevon (pitch) command | control-law output | computed | +/-25 (secondary source) [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR DL? | DIRECT |
| `FCS.STICK.PITCH` | Stick pitch command | pilot command sensors (LVDT type ASSUMPTION) | measured (x4) + voted | -100..100 % [% or mm] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR DL? | DIRECT |
| `FCS.STICK.ROLL` | Stick roll command | pilot command sensors (LVDT type ASSUMPTION) | measured (x4) + voted | -100..100 % [% or mm] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR DL? | DIRECT |
| `FCS.PEDAL` | Rudder pedal command | pilot command sensors (LVDT type ASSUMPTION) | measured (x4) + voted | -100..100 % [% or mm] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR DL? | DIRECT |
| `FCS.ELEVON.LOB.POS` | Elevon position LOB | actuator position transducer (quad electrical, dual hydraulic, DDV) | measured | +/-25 (secondary); diff. aileron +/-18… [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP? CDR DL? | DIRECT |
| `FCS.ELEVON.LOB.CMD` | Elevon command LOB | control-law output | computed | +/-25 [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR? DL? | DIRECT+ASSUMPTION |
| `FCS.ELEVON.LIB.POS` | Elevon position LIB | actuator position transducer (quad electrical, dual hydraulic, DDV) | measured | +/-25 (secondary); diff. aileron +/-18… [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP? CDR DL? | DIRECT |
| `FCS.ELEVON.LIB.CMD` | Elevon command LIB | control-law output | computed | +/-25 [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR? DL? | DIRECT+ASSUMPTION |
| `FCS.ELEVON.RIB.POS` | Elevon position RIB | actuator position transducer (quad electrical, dual hydraulic, DDV) | measured | +/-25 (secondary); diff. aileron +/-18… [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP? CDR DL? | DIRECT |
| `FCS.ELEVON.RIB.CMD` | Elevon command RIB | control-law output | computed | +/-25 [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR? DL? | DIRECT+ASSUMPTION |
| `FCS.ELEVON.ROB.POS` | Elevon position ROB | actuator position transducer (quad electrical, dual hydraulic, DDV) | measured | +/-25 (secondary); diff. aileron +/-18… [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP? CDR DL? | DIRECT |
| `FCS.ELEVON.ROB.CMD` | Elevon command ROB | control-law output | computed | +/-25 [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR? DL? | DIRECT+ASSUMPTION |
| `FCS.RUDDER.POS` | Rudder position | actuator position transducer | measured | +/-30 (rate 100 deg/s) [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP? CDR DL? | DIRECT |
| `FCS.RUDDER.CMD` | Rudder command | control-law output | computed | +/-30 [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CDR? DL? | DIRECT |
| `FCS.SLAT.POS` | Leading-edge slat positions (6 actuators, IB/MB/OB per side) | EHSV actuator position feedback (dual electrical, single hydraulic) | measured | 0-30 (IB 17.5, MB 27.5, OB 30; seconda… [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP? CDR DL? | DIRECT |
| `FCS.AIRBRAKE.POS` | Airbrake position (2 open-loop jacks) | dual-core LVDT (probable HAL part, 294 mm stroke) | measured | 0-294 [mm] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP CDR DL? | DIRECT+DIRECT-part |
| `FCS.ACT.BIT` | Actuator BIT / servo status words (per actuator) | DFCC automatic actuator BIT (DDV/EHSV current, LVDT sum monitors) | computed | - [bit-packed] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP CDR DL | DIRECT+TRANSFER |
| `FCS.CH.STATUS` | DFCC channel status (x4) and CCDL status | DFCC redundancy management (watchdog monitor, CCDL) | computed | healthy/failed/reset per channel [enum/bits] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP CDR DL | DIRECT |
| `FCS.MODE` | FCS mode / law state (scheduled-gain, fixed-gain reversion, spin-recovery, autop… | DFCC mode logic | computed | enum [enum] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP CDR DL | DIRECT |
| `FCS.AIRDATA_MISTRACK` | Air-data sensor mistrack / exclusion flags | DFCC/ADC monitors | computed | - [bits] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP CDR DL | DIRECT |
| `FCS.HEATER_I` | Probe/vane heater currents (NADP, LADP, RADP, AoA vanes, TAT) | current sense | measured | 0-10 [ASSUMPTION] [A] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP? CDR? DL | DIRECT |
| `FCS.KALMAN_ATT` | DFCC Kalman-filter attitude estimate (pitch, roll) | Kalman filter on inertial sensors | computed | pitch +/-90, roll +/-180 [deg] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR16 | CP? CDR? DL? | DIRECT+ASSUMPTION |
| `FCS.BIT.LOG` | DFCC PBIT/CBIT/MBIT results and fault log | DFCC BIT (23 subsystems per channel, 92 total) | computed event | - [records] | EVT -> EVT -> EVT (on change) | CP CDR? DL | DIRECT |
| `FCS.FTP` | Flight Test Panel test-point number / excitation active / auto-abort | programmable function generator (100 test points), RS-422 PID link + 5… | computed | 0-99 [enum] | FTI -> FTI PCM / telemetry -> FTI DRU | CP FTI-only | DIRECT |

**Air data (ADC x4)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `AD.PS` | Static pressure (per probe/transducer) | pressure transducers inside each ADC (4 per ADC) fed from NADP/LADP/RA… | measured | 35-1300 mbar [mbar] | FCS80 -> AV25 -> CDR4 | CDR? DL? | DIRECT |
| `AD.PT` | Total pressure | pressure transducers inside each ADC (4 per ADC) fed from NADP/LADP/RA… | measured | 35-2700 mbar [mbar] | FCS80 -> AV25 -> CDR4 | CDR? DL? | DIRECT |
| `AD.DPA` | Differential pressure P-alpha (AoA, probe-derived) | pressure transducers inside each ADC (4 per ADC) fed from NADP/LADP/RA… | measured | 35-1500 mbar [mbar] | FCS80 -> AV25 -> CDR4 | CDR? DL? | DIRECT |
| `AD.DPB` | Differential pressure P-beta (sideslip, probe-derived) | pressure transducers inside each ADC (4 per ADC) fed from NADP/LADP/RA… | measured | 35-1500 mbar [mbar] | FCS80 -> AV25 -> CDR4 | CDR? DL? | DIRECT |
| `AD.AOA_VANE_L` | AoA vane left (quad LVDT) | vane with quadruplex LVDT | measured | +/-45 deg [deg] | FCS80 -> AV25 -> CDR4 | CDR DL? | DIRECT |
| `AD.AOA_VANE_R` | AoA vane right (quad LVDT) | vane with quadruplex LVDT | measured | +/-45 deg [deg] | FCS80 -> AV25 -> CDR4 | CDR DL? | DIRECT |
| `AD.AOSS_VANE` | Sideslip vane (quad LVDT; Mk2 adds second) | vane with quadruplex LVDT | measured | +/-45 deg [deg] | FCS80 -> AV25 -> CDR4 | CDR DL? | DIRECT |
| `AD.TAT` | Total air temperature | total temperature probe (heated) | measured | -60 to +150 [ASSUMPTION] [degC] | FCS80 -> AV25 -> CDR4 | CDR ECMS/HUMS DL? | DIRECT |
| `AD.HP` | Pressure altitude | air-data algorithm (static & total pressure computations, Mach correct… | computed | -2,000 to 60,000 [ft] | FCS80 -> AV25 -> CDR4 | CP CDR ECMS/HUMS DL? | DIRECT+TRANSFER |
| `AD.HBARO` | Baro-corrected altitude | air-data algorithm (static & total pressure computations, Mach correct… | computed | -2,000 to 60,000 [ft] | FCS80 -> AV25 -> CDR4 | CP CDR ECMS/HUMS? DL? | DIRECT+TRANSFER |
| `AD.CAS` | Calibrated airspeed | air-data algorithm (static & total pressure computations, Mach correct… | computed | 0-800 [kt] | FCS80 -> AV25 -> CDR4 | CP CDR ECMS/HUMS? DL? | DIRECT+TRANSFER |
| `AD.TAS` | True airspeed | air-data algorithm (static & total pressure computations, Mach correct… | computed | 0-1,100 [kt] | FCS80 -> AV25 -> CDR4 | CP CDR ECMS/HUMS? DL? | DIRECT+TRANSFER |
| `AD.MACH` | Mach number | air-data algorithm (static & total pressure computations, Mach correct… | computed | 0-2.0 [-] | FCS80 -> AV25 -> CDR4 | CP CDR ECMS/HUMS DL? | DIRECT+TRANSFER |
| `AD.AOA` | Corrected / voted angle of attack | air-data algorithm (static & total pressure computations, Mach correct… | computed | -10 to +45 [deg] | FCS80 -> AV25 -> CDR4 | CP CDR ECMS/HUMS DL? | DIRECT+TRANSFER |
| `AD.BETA` | Sideslip angle | air-data algorithm (static & total pressure computations, Mach correct… | computed | +/-30 [deg] | FCS80 -> AV25 -> CDR4 | CP? CDR ECMS/HUMS? DL? | DIRECT+TRANSFER |
| `AD.SAT` | Static air temperature | air-data algorithm (static & total pressure computations, Mach correct… | computed | -80 to +60 [degC] | FCS80 -> AV25 -> CDR4 | CP? CDR ECMS/HUMS? DL? | DIRECT+TRANSFER |
| `AD.HDOT` | Pressure altitude rate | air-data algorithm (static & total pressure computations, Mach correct… | computed | +/-60,000 [ft/min] | FCS80 -> AV25 -> CDR4 | CP? CDR ECMS/HUMS? DL? | DIRECT+TRANSFER |
| `AD.QBAR` | Dynamic pressure | air-data algorithm (static & total pressure computations, Mach correct… | computed | 0-2,500 [psf] | FCS80 -> AV25 -> CDR4 | CP? CDR ECMS/HUMS? DL? | DIRECT+TRANSFER |
| `AD.VALID` | Air-data validity / status words | ADC BIT (90 % coverage) + monitors | computed | - [bits] | FCS80 -> AV25 -> CDR4 | CP CDR DL | DIRECT+TRANSFER |
| `AD.BOOM` | Flight-test nose boom alpha/beta/Ps/Pt | FTI nose boom with calibrated beta vane | measured (FTI) | - [deg / mbar] | FTI -> FTI PCM / telemetry -> FTI DRU | CP FTI-only | DIRECT |

**Navigation (INS/GPS, AHRS, radar altimeter)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `NAV.INS.LAT` | Present position latitude | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | +/-90 [deg] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.LON` | Present position longitude | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | +/-180 [deg] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.ALT` | Baro-inertial altitude | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | -2,000 to 60,000 [ft] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.VN` | North velocity | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | +/-3,000 [ft/s] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.VE` | East velocity | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | +/-3,000 [ft/s] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.VD` | Vertical velocity | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | +/-1,000 [ft/s] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.HDG_TRUE` | True heading | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | 0-360 [deg] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.PITCH` | Pitch attitude | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | +/-90 [deg] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.ROLL` | Roll attitude | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | +/-180 [deg] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.BODY_RATES` | Body rates (narrow/wide band) | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | +/-400 [deg/s] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.INS.ACCEL` | Platform / body accelerations | strapdown RLG + accelerometers, GPS-aided | computed (from measured inertial data) | +/-12 g [ft/s2] | LRU-INT -> AV50 -> CDR4-8 | CP CDR DL? | DIRECT+TRANSFER |
| `NAV.GPS.STATUS` | GPS fix / FOM / INS mode | INGPS | computed | - [enum] | LRU-INT -> AV50 -> CDR4-8 | CP CDR? DL? | TRANSFER |
| `NAV.AHRS` | Standby AHRS attitude/heading | strapdown AHRS | computed | - [deg] | LRU-INT -> AV25 -> CDR4 | CP CDR? DL? | DIRECT |
| `NAV.RADALT` | Radar altitude | radar altimeter (Mk1A: advanced radio altimeter) | measured | 0-5,000 [ASSUMPTION] [ft] | LRU-INT -> AV25 -> CDR4 | CP CDR DL? | DIRECT |

**Secondary power (AMAGB, PTO, JFS)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `SPS.AMAGB.SPEED` | AMAGB input speed | derived from N2 via fixed ratio | computed | 0-17,500 (rated 16,810) [rpm] | LRU-INT -> AV12.5 -> CDR1 + HUMS | CDR? ECMS/HUMS? DL? | DIRECT+ASSUMPTION |
| `SPS.AMAGB.OIL_T` | AMAGB oil temperature / temp-high caution | RTD or thermistor + switch | measured | -54 to ~150 [degC / 0/1] | LRU-INT -> SLOW1 -> SLOW1 | CP CDR ECMS/HUMS DL | TRANSFER |
| `SPS.AMAGB.OIL_LOW` | AMAGB oil level low / chip | level switch; magnetic chip detector | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | DIRECT+TRANSFER+ASSUMPTION |
| `SPS.JFS.SPEED` | JFS (GTSU-110) speed | magnetic pickup | measured | 0-110 % [%] | LRU-INT -> AV12.5 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | ASSUMPTION |
| `SPS.JFS.EGT` | JFS exhaust gas temperature | thermocouple | measured | 0-1,000 [ASSUMPTION] [degC] | LRU-INT -> AV12.5 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | ASSUMPTION |
| `SPS.JFS.OIL_QTY` | JFS oil quantity / consumption (M2 self-contained tank) | level sensor/inspection | measured or inspection | - [L or %] | SORTIE -> download -> SORTIE | ECMS/HUMS? DL | DIRECT+ASSUMPTION |

**Hydraulics (2 x 280 bar systems)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `HYD.SYS1.P` | Hydraulic SYS1 pressure | strain-gauge/MEMS transducer | measured | 0-350 (nominal 280) [bar] | LRU-INT -> AV25 -> CDR1 + HUMS | CP CDR ECMS/HUMS DL | DIRECT+TRANSFER+ASSUMPTION |
| `HYD.SYS1.LP` | Hydraulic SYS1 low-pressure warning | pressure switch | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | TRANSFER |
| `HYD.SYS1.T` | Hydraulic SYS1 fluid temperature | MEMS/RTD | measured | -54 to +135 [degC] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | DIRECT |
| `HYD.SYS1.LEVEL` | Hydraulic SYS1 reservoir level (+ low level) | level-sensing device in bootstrap reservoir | measured | 0-100 % [% (0-9.5 L)] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | DIRECT-part+TRANSFER |
| `HYD.SYS2.P` | Hydraulic SYS2 pressure | strain-gauge/MEMS transducer | measured | 0-350 (nominal 280) [bar] | LRU-INT -> AV25 -> CDR1 + HUMS | CP CDR ECMS/HUMS DL | DIRECT+TRANSFER+ASSUMPTION |
| `HYD.SYS2.LP` | Hydraulic SYS2 low-pressure warning | pressure switch | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | TRANSFER |
| `HYD.SYS2.T` | Hydraulic SYS2 fluid temperature | MEMS/RTD | measured | -54 to +135 [degC] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | DIRECT |
| `HYD.SYS2.LEVEL` | Hydraulic SYS2 reservoir level (+ low level) | level-sensing device in bootstrap reservoir | measured | 0-100 % [% (0-9.5 L)] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | DIRECT-part+TRANSFER |
| `HYD.FILTER_DP` | Hydraulic filter delta-P / clog indicators (9 filters, 6 types) | delta-P switch / pop-up | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | ECMS/HUMS DL | DIRECT+ASSUMPTION |
| `HYD.CH_STATUS` | Hydraulic pressure status per DFCC channel | pressure switches | measured discrete | 0/1 [x4] | FCS80 -> AV50 poll of DFCC buffer updated at FCS40 -> CDR4 | CP? CDR DL | TRANSFER |

**Fuel (ECFM-C)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `FUEL.QTY.TANK` | Fuel contents per tank (F1, F1A, F2, wing L/R, drop tanks) | capacitance probes, frequency/period output (attitude-compensated gaug… | measured -> computed (gauged) | 0-2,458 kg internal [kg] | LRU-INT -> AV12.5 -> CDR1 + HUMS | CP CDR ECMS/HUMS DL | DIRECT+TRANSFER |
| `FUEL.TOTAL` | Total fuel; low-fuel and bingo discretes | computed + independent low-level switch [ASSUMPTION] | computed | 0-2,458 internal (+ drop tanks 1,200/8… [kg / 0/1] | LRU-INT -> AV12.5 -> CDR1 + HUMS | CP CDR ECMS/HUMS DL | DIRECT |
| `FUEL.BOOST_P` | F2/boost pump pressure-low; pump status | pressure switch; current | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | DIRECT+TRANSFER |
| `FUEL.TEMP` | Fuel temperature (feed) | RTD | measured | -40 to +120 [ASSUMPTION] [degC] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | TRANSFER |
| `FUEL.TANK_PRESS` | Tank pressurisation / drop-tank pressurised/over-pressure | pressure switch/transducer | measured | 0.1-0.5 bar g [ASSUMPTION] [bar g / 0/1] | EVT -> EVT -> EVT (on change) | CP? CDR? ECMS/HUMS DL | DIRECT+TRANSFER |
| `FUEL.REFUEL_EVT` | Refuel / AAR / hot-refuel / dump events | discretes (probe, valves, GRP preset) | measured discrete | - [-] | EVT -> EVT -> EVT (on change) | CP? CDR? DL | DIRECT |

**Electrical power**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `ELEC.GEN.V` | Main AC generator voltage (per phase) | GCU sensing | measured | 108-118 normal (704F) [V rms] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | TRANSFER |
| `ELEC.GEN.F` | Main AC generator frequency | GCU sensing | measured | 393-407 normal [Hz] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | TRANSFER |
| `ELEC.GEN.I` | Main AC generator load current | CT | measured | 0-? (rating not public) [A] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | ASSUMPTION |
| `ELEC.GEN.OUT` | Generator off-line (GEN OUT) | GCU | computed discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | TRANSFER |
| `ELEC.TRU.VI` | TRU 1/2 output voltage and current | shunt/Hall | measured | 22-29 V; 0-250 A (overloads 150/200/40… [V / A] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | DIRECT-part |
| `ELEC.BACKUP.STATUS` | 5 kW brushless DC backup generator V/I/BITE status | GCU (FPGA/DSP) with BITE | measured + computed | 28 V; ~0-180 A [V / A / bits] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | DIRECT |
| `ELEC.BATT` | Battery voltage, current, ampere-hours; BATT LOW | shunt + integrator (display unit) | measured + computed | 0-45 Ah; warning 30 Ah; 50 A charge [V / A / Ah] | LRU-INT -> SLOW1 -> SLOW1 | CP CDR? ECMS/HUMS DL | DIRECT-part |
| `ELEC.DCBUS.V` | DC bus voltages (main / essential / emergency) | voltage sense | measured | 22-29 normal; 16-29 emergency; 12-29 s… [V] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | TRANSFER |

**ECS and life support**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `ECS.BLEED_P` | Bleed-air inlet pressure (switch; transducer ASSUMPTION) | pressure switch / transducer | measured | in flight ~2.8-6.4 bar abs; duct desig… [bar abs] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | DIRECT+TRANSFER |
| `ECS.BLEED_T` | Bleed / PHX outlet / ACM turbine inlet temperatures | RTD/TC (-55..300 degC class) | measured | PHX in <=578, out <170 (probable part) [degC] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | DIRECT+DIRECT-part |
| `ECS.COCKPIT_T` | ACM outlet / cockpit supply / cockpit temperature | RTD (-55..100 degC class) | measured | -55 to 100 [degC] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP? CDR? ECMS/HUMS DL | DIRECT+TRANSFER |
| `ECS.TCV` | Temperature/flow control valve position | resolver/pot [ASSUMPTION] | measured | 0-90 [deg] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CDR? ECMS/HUMS DL | TRANSFER |
| `ECS.CABIN_P` | Cockpit pressure / cabin altitude (CPTCV) | cockpit pressure transducer | measured | dP <= 5 psi [psia / ft] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP CDR? ECMS/HUMS DL | DIRECT+TRANSFER |
| `ECS.SWITCHES` | ECS pressure high/low switches; hot-air leak detection | pressure switches; continuous sensing element + control box | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | DIRECT |
| `ECS.AVIONICS_T` | Avionics cooling-air temperature; avionics-hot caution | RTD + discrete | measured | - [degC / 0/1] | LRU-INT -> AV6.25 -> CDR1 + HUMS | CP CDR? ECMS/HUMS DL | DIRECT+TRANSFER |
| `LSS.OBOGS` | OBOGS O2 concentration, outlet pressure, OBOGS fail (Mk1A) | O2 sensor; pressure transducer | measured | - [% / kPa] | LRU-INT -> SLOW1 -> SLOW1 | CP CDR? ECMS/HUMS DL | DIRECT+ASSUMPTION |
| `LSS.LOX_QTY` | LOX quantity (Mk1) | capacitance transmitter, frequency output to ECFM-C | measured | 0-5 L (+/-0.4 L) [L] | LRU-INT -> SLOW1 -> SLOW1 | CP ECMS/HUMS DL | DIRECT-part |

**Landing gear, brakes, tyres, NWS, chute**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `LG.POSITION` | Gear up-locked / down-locked (x3), handle, doors | proximity switches | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR DL | DIRECT+TRANSFER |
| `LG.WOW` | Weight-on-wheels per gear | strut proximity/switch | measured discrete | 0/1 [0/1] | EVT -> FCS40 -> EVT (on change) | CP? CDR ECMS/HUMS DL | TRANSFER |
| `BRK.PEDAL` | Brake-feel pedal input L/R | potentiometers | measured | 0-100 % [%] | LRU-INT -> AV25 -> CDR4 | CDR ECMS/HUMS? DL | DIRECT |
| `BRK.WHEEL_SPEED` | Wheel speed L/R; skid-valve activity; anti-skid fail | wheel-speed transducer; valve current | measured | - [rpm / 0/1] | LRU-INT -> AV25 -> CDR4 | CP? CDR ECMS/HUMS DL | DIRECT+DIRECT-part |
| `BRK.PRESS` | Brake pressure per wheel | transducer [ASSUMPTION] | measured | 0-~200 [ASSUMPTION] [bar] | LRU-INT -> AV25 -> CDR4 | CDR? ECMS/HUMS DL | ASSUMPTION |
| `NWS.STATE` | NWS input/feedback pots, free-castor solenoid, NWS fail | potentiometers; solenoid state | measured | +/- NWS range [deg / 0/1] | LRU-INT -> AV25 -> CDR4 | CP CDR ECMS/HUMS? DL | DIRECT |
| `CHUTE.STATE` | Brake chute deploy / jettison / unsafe | discretes | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR DL | DIRECT+TRANSFER |

**Fire protection / warnings**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `FIRE.WARN` | Engine-bay fire/overheat warning; extinguisher fired; extinguisher low | detector loop [ASSUMPTION]; cartridge circuit | measured discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS DL | DIRECT+DIRECT-part+TRANSFER |

**Avionics status, warnings, recorder & metadata**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `AV.1553.BUS_STATUS` | 1553B bus A/B channel status per bus (>=3 buses) | bus controller monitoring | computed | - [bits] | LRU-INT -> AV12.5 -> CDR1 + HUMS | CDR? DL | DIRECT+TRANSFER |
| `AV.RT.STATUS` | 1553 RT status word per LRU (message error, service request, busy, subsystem fla… | 1553 RT protocol | computed | - [bits] | LRU-INT -> AV50 -> CDR4-8 | CDR? DL | TRANSFER |
| `AV.LRU.BIT` | LRU BIT word (mode code 19) per avionics/utility LRU | LRU self-test (PBIT/CBIT/IBIT) | computed | - [bits] | LRU-INT -> AV12.5 -> CDR1 + HUMS | CP CDR? ECMS/HUMS? DL | DIRECT+TRANSFER |
| `AV.LRU.HEALTH` | LRU health-status message (link, port, memory status, device temperature) | LRU self-monitor | computed | - [codes / degF (0.1 reso…] | LRU-INT -> AV12.5 -> CDR1 + HUMS | CDR? ECMS/HUMS? DL | DIRECT-unnamed+ASSUMPTION |
| `AV.SW_CONFIG` | Software/configuration versions (OAC, DFCC, radar, BHEEM, ECFM, FADEC), stores c… | configuration management | computed | e.g. DFCC 7307/7351/9008; OAC 10.0.4.0… [strings] | SORTIE -> download -> SORTIE | CP? CDR ECMS/HUMS? DL | DIRECT |
| `CWS.LEGEND` | Centralized Warning System legends (30 red/amber) | CWS EU from ARINC-429 + 30 discrete inputs | computed discrete | 0/1 [0/1 x30] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS? DL | DIRECT-part |
| `CWS.MASTER` | Master warning / master caution (flasher) | CWS | computed discrete | 0/1 [0/1] | EVT -> EVT -> EVT (on change) | CP CDR DL | DIRECT-part |
| `CWS.VOICE.AOA` | Voice warning: AoA exceedance | CWS voice generator | computed event | - [-] | EVT -> EVT -> EVT (on change) | CP CDR DL? | DIRECT-part |
| `CWS.VOICE.LOW_ALT` | Voice warning: Low altitude | CWS voice generator | computed event | - [-] | EVT -> EVT -> EVT (on change) | CP CDR DL? | DIRECT-part |
| `CWS.VOICE.CANOPY` | Voice warning: Canopy unlock | CWS voice generator | computed event | - [-] | EVT -> EVT -> EVT (on change) | CP CDR DL? | DIRECT-part |
| `CWS.VOICE.UC` | Voice warning: Undercarriage extension | CWS voice generator | computed event | - [-] | EVT -> EVT -> EVT (on change) | CP CDR DL? | DIRECT-part |
| `SYS.EVENT_MARKER` | Pilot event marker / record button | cockpit switch | measured discrete | 0/1 [-] | EVT -> EVT -> EVT (on change) | CDR ECMS/HUMS DL | TRANSFER |
| `SYS.TIME` | UTC / GPS time and recorder RTC | GPS / IRIG time / free-running RTC | measured | - [s] | LRU-INT -> SLOW1 -> SLOW1 | CP CDR ECMS/HUMS DL | TRANSFER |
| `SYS.IDS` | Tail number, engine serial, sortie ID, LRU serials | configuration | computed | - [strings] | SORTIE -> download -> SORTIE | CDR ECMS/HUMS DL | TRANSFER |
| `SYS.PHASE` | Derived flight phase (WoW, speed, altitude, throttle) | derived | computed | - [-] | SORTIE -> download -> SORTIE | - | MEASURED+ASSUMPTION |
| `STRUCT.NZ_COUNTERS` | Normal-acceleration level-crossing counters (8 g-levels, set/reset levels) | accelerometer at CG + counting logic | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | TRANSFER |
| `STRUCT.STRAIN` | Structural strain gauges (MLG, wing, stores) | foil strain gauges | measured (FTI) | - [microstrain] | FTI -> FTI PCM / telemetry -> FTI DRU | - | DIRECT |
| `FTI.ALL` | FTI parameter set (~1,500 parameters; DAS + selected telemetry + DRU) | FTI DAS (PCM), bus monitors | measured/computed | - [-] | FTI -> FTI PCM / telemetry -> FTI DRU | - | DIRECT+TRANSFER |
| `DVR.VIDEO` | Digital video recorder (HUD/MFD video) and cockpit audio | video/audio capture | measured | - [-] | video -> video -> DVR media | DL | DIRECT+ASSUMPTION |
| `STORES.CONFIG` | Stores / drop-tank configuration and release events | SMS station status (pylon interface 1553 RT) | computed | 9 hard points [enum] | EVT -> EVT -> EVT (on change) | CP CDR ECMS/HUMS? DL | DIRECT |

**Aircraft usage counters**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `USAGE.FLIGHT_HOURS` | Flight hours (WoW-off to WoW-on) | derived from discretes/analogs | computed counter | cumulative [h] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | TRANSFER |
| `USAGE.LANDINGS` | Landings (incl. touch-and-go, arrested for navy) | derived from discretes/analogs | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | TRANSFER |
| `USAGE.GEAR_CYCLES` | Landing-gear retraction/extension cycles | derived from discretes/analogs | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | ASSUMPTION |
| `USAGE.CHUTE_STREAMINGS` | Brake-chute streamings (life 45 streamings / 8 years) | derived from discretes/analogs | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT |
| `USAGE.BRAKE_APPLICATIONS` | Brake applications / brake energy per landing | derived from discretes/analogs | computed counter | cumulative [count / MJ] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | ASSUMPTION |
| `USAGE.JFS_STARTS` | JFS start attempts / successes / consecutive starts | derived from discretes/analogs | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT |
| `USAGE.AMAGB_HOURS` | AMAGB operating hours (life 750 h) | derived from discretes/analogs | computed counter | cumulative [h] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT |
| `USAGE.AB_LIGHTS` | Afterburner light-ups | derived from discretes/analogs | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | TRANSFER |
| `USAGE.ENGINE_STARTS` | Engine starts (ground) and relights (air) | derived from discretes/analogs | computed counter | cumulative [count] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | TRANSFER |
| `USAGE.G_EXCEEDANCE` | Over-g / over-AoA / overspeed exceedances | derived from discretes/analogs | computed counter | cumulative [count + record] | SORTIE -> download -> SORTIE | ECMS/HUMS DL | DIRECT+TRANSFER |

**Ground inspection measurements (not on aircraft data path)**

| ID | Parameter | Origin (sensor / LRU) | Class | Range [units] | Acq -> bus -> record | Sinks | Tag |
|---|---|---|---|---|---|---|---|
| `MX.TYRE_P` | Tyre pressure cold check | hand gauge (+/-2 %) | ground inspection | main 16.9 / nose 7 bar (probable parts… [bar] | INSP -> none -> maintenance record | - | DIRECT-part+TRANSFER |
| `MX.BRAKE_WEAR` | Brake wear (pin) % worn | wear-indicator pin | ground inspection | 0-100 % [%] | INSP -> none -> maintenance record | - | DIRECT |
| `MX.ACCUM_PRECHARGE` | Accumulator N2 precharge | gas gauge | ground inspection | brake accumulator 50 bar N2 (part) [bar] | INSP -> none -> maintenance record | - | DIRECT-part+TRANSFER |
| `MX.OIL_SERVICING` | Engine / AMAGB / JFS oil added at servicing | servicing record | ground inspection | - [L] | INSP -> none -> maintenance record | - | DIRECT+TRANSFER |
| `MX.SOAP` | Oil analysis (spectrometric Fe etc.) | lab spectrometer (JOAP-like) | ground inspection | normal wear CF188 Fe 0.47 ug/h mean [ppm / ug/h] | INSP -> none -> maintenance record | - | TRANSFER |
| `MX.BORESCOPE` | Borescope findings (hot section, blades) | borescope | ground inspection | pass/limit/reject [grade] | INSP -> none -> maintenance record | - | TRANSFER |

### Inferences
- [ASSUMPTION] **How to turn the CSV into the versioned Phalanx dictionary (no code written here):**
  - Add per-row bus mapping (synthetic RT/SA/word/bit, or ARINC 429 label/SDI/SSM), encoding (BNR LSB from the `recommended_quantization` column, sign, multi-word), calibration polynomial, sensor serial, TMATS limit fields, dictionary version and hash. The field list follows `data_pathway_and_formats.md` Q6.
  - Keep `truth` values in the canonical representation only; never export them to the downstream contract.
  - Treat the three rate-group fields as separate clocks (Q7) so that staleness, aliasing and duplicate samples arise naturally at the bus and recorder boundaries.
- [ASSUMPTION] **Rows tagged TRANSFER-led (44) are the highest-risk for "Tejas-likeness".** Most are engine rows (F404-400 numbers on an IN20 FADEC). Give these rows wider priors (bias, quantisation, rate) and a `fidelity=transfer` flag so validation can down-weight them.

### Gaps
- No Tejas ICD, recorder data-frame layout or ECMS/HUMS parameter list is public. All bus/word mappings and most rates are synthetic.
- IN20 FADEC sensor duplication, oil temperature/filter ΔP existence, and chip-detector type (electrical vs magnetic) are unconfirmed.
- Tejas brake temperature, brake pressure and tyre-pressure sensing are unconfirmed (assumed absent or ground-only; see Q5).

---

## Q5. NOT-measured inventory: physical states that matter for maintenance but are not directly observable

### Takeaway
**`not_measured_states.csv` lists 50 hidden states:** engine 17, hydraulics 7, landing gear/brakes/tyres 6, air data 3, electrical 3, ECS 3, structure 3, secondary power 2, FCS 2, fuel 2, avionics 1, life support 1. Evidence: 17 rest at least partly on Tejas-specific statements, 1 on an Indian part page (DIRECT-part), 30 are transfer-led, and 2 are assumption-only.

For each state the file gives the measured signals that carry partial information, how the state shows up in them, and the inspection or maintenance action that reveals it.

**Four observability classes emerge:**
1. **Model-observable** (gas-path component health, compensator drift, HX fouling). These need a physics model plus corrected parameters, and are partly masked by control loops.
2. **Usage-inferred only** (disk LCF and blade creep life consumed; structural fatigue; brake and tyre wear; chute life). Only counters exist.
3. **Late-symptom only** (bearing spall, blade cracks, hose fatigue, lock-spring relaxation, wiring). Nothing shows until a discrete trips, chips appear, or a sudden failure occurs.
4. **Ground-inspection only** (accumulator precharge, filter loading before the ΔP trip, composite delamination, corrosion, oil chemistry).

The generator must keep these as hidden states that drive the measured rows. Their truth must reach only the maintenance/inspection event stream, never the aircraft data stream.

### Cited Findings
- Component health, tip clearance, crack, bearing, seal, VG and nozzle mechanisms and signatures — [`faults_and_degradation.md` §9(b) #1–17, #36](https://ntrs.nasa.gov/api/citations/20100005639/downloads/20100005639.pdf) [TRANSFER]; life-usage logic and limits — [`f404_in20_engine_model.md` Q9](https://archive.org/details/DTIC_ADA347270) [TRANSFER].
- Tejas-specific hidden-state evidence [DIRECT]:
  - brake wear % tested at 50/70/90 % ([ADA AR 2018-19, 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf));
  - a twin hydraulic hose rupture (one ruptured hose cut the other) ([NFTC 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf));
  - water seepage into cockpit, radar, DFCC and avionics bays, fuel leaks, "cracking of turkey feathers, de-lamination" ([CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf));
  - AMAGB life 750 h ([DDP 8779](https://www.ddpmod.gov.in/node/8779));
  - chute life 45 streamings / 8 years ([DDP 8027](https://www.ddpmod.gov.in/node/8027));
  - JFS cold-start failures and excessive oil consumption ([CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf));
  - ADC digital-module reliability modification ([ADA AR 2019-22 via `indian_fleet_platform_relevance.md` KQ4](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf));
  - a Fatigue Test Specimen build ([ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf)).
- Hydraulic diagnostic expectations [TRANSFER]: a MIL-H-5440H diagnostic monitor must indicate "filter replacement, accumulator recharging and over temperature" — [MIL-H-5440H](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-H/MIL-H-5440H_14866/).
- Electronics aging [TRANSFER]: RUL of avionics single-board computers from thermal/vibration history — [DSJ 75(3) 2025](https://www.publicationsdrdo.in/index.php/dsj/article/view/20913).

**Not-measured list (compact; full detail in the CSV)**

| ID | Hidden state | Measured signals with partial information | How it shows | Revealing inspection / action | Tag |
|---|---|---|---|---|---|
| `NM.ENG.FAN_HEALTH` | Fan flow capacity and isentropic efficiency | ENG.N1; ENG.T5; ENG.WFM; ENG.PS3; ENG.T1; ENG.A8; AD.MACH; AD.HP | at fixed corrected thrust/N1: T5 up, Wf up, N2 shift; needs a gas-path model and corrected parameters to separ… | engine wash recovery; test-cell performance run; borescope for FOD/erosion | TRANSFER (gas-path diagnostics literature; ProDiMES/C-MAPSS) |
| `NM.ENG.HPC_HEALTH` | HPC flow capacity, efficiency and stall margin | ENG.N2; ENG.PS3; ENG.T5; ENG.WFM; ENG.CVG; ENG.FAULT_CODES | PS3 lower and T5/Wf higher at fixed N2; stalls/pop-stall events become more likely during transients | test-cell run; borescope; stall-event investigation | TRANSFER |
| `NM.ENG.HPT_HEALTH` | HPT efficiency and NGV throat area (flow capacity) | ENG.T5; ENG.N2; ENG.WFM; ENG.PS3; LUI.EFTC; LUI.SRC | 1 % HPT fault ~ N2 -0.6 %, Wf +0.6 %, EGT +12 degF, P3 -0.5 % (reference engine); T5 margin to limit shrinks; … | borescope (hot section); module removal and shop inspection | TRANSFER |
| `NM.ENG.LPT_HEALTH` | LPT efficiency / flow capacity | ENG.T5; ENG.P5; ENG.N1 | small shifts (eta -0.5 to -1.1 % at 3,000-6,000 cycles, reference) | borescope; shop visit | TRANSFER |
| `NM.ENG.TIP_CLEARANCE` | HPT/HPC blade tip clearance | ENG.T5; ENG.WFM; ENG.N2 (transient heat-soak behaviour) | ~+1 degC EGT and +0.1 % SFC per 0.001 in HPT clearance (reference); step after rub | borescope; shop measurement at overhaul | TRANSFER (Lattime & Steinetz) |
| `NM.ENG.BLADE_CRACK` | Blade/vane crack length (HCF/LCF), coating loss | ENG.VIB.*; ENG.T5; ENG.N1; ENG.N2; ENG.FAULT_CODES | usually no signature until liberation (stall codes, RPM drop, FTIT/T5 rise in seconds) | borescope; NDT at shop visit; fleet campaign inspections | TRANSFER: USAF F-16 AIB cases (F100/F110 blade failures); me… |
| `NM.ENG.DISK_LIFE` | Disk/shaft LCF life consumed (crack initiation fraction) | LUI.TYPE1; LUI.TYPE3; LUI.PS3_FULL; LUI.PS3_PART; LUI.EOT; ENG.N2 | counters accumulate with throttle activity; no gas-path signature | life-limit removal per lifed-part tracking; NDT at overhaul | DIRECT (Tejas ECMS computes LUIs) + TRANSFER (F404 limits) |
| `NM.ENG.BLADE_CREEP` | HPT blade creep / stress-rupture life consumed | LUI.SRC; LUI.EFTC; LUI.TAMP; ENG.T5 | counters only | shop inspection; blade stretch measurement | TRANSFER (F404 IECMS) |
| `NM.ENG.BEARING_SPALL` | Main-shaft bearing spall size / debris mass | ENG.CHIP; ENG.VIB.*; ENG.OIL_P; ENG.OIL_T; MX.SOAP | chips in oil (most common indicator), vibration rise, low oil pressure late | chip-detector inspection; SOAP/JOAP; filter debris analysis; borescope | TRANSFER: Indian Su-30MKI AL-31FP failure statistics (other … |
| `NM.ENG.SEAL_WEAR` | Oil/air seal wear and internal oil leakage | ENG.OIL_LEVEL; MX.OIL_SERVICING; ENG.OIL_P | rising oil consumption between servicings; level-low events | oil consumption trend from servicing records; borescope for coking | TRANSFER / ASSUMPTION |
| `NM.ENG.OIL_CONDITION` | Oil degradation and contamination (wear metals, fuel dilution, oxidation) | MX.SOAP; ENG.CHIP; ENG.OIL_T | indirect only | oil sampling (SOAP/JOAP), periodic | TRANSFER (CF-18 Fe 0.47 ug/h mean) |
| `NM.ENG.FUEL_NOZZLE` | Fuel-nozzle coking / spray-pattern degradation | ENG.T5.HARNESS_A; ENG.T5.HARNESS_B; ENG.T5 | harness-to-harness spread and T5 profile change [ASSUMPTION] | borescope; nozzle flow-check at shop (fuel nozzle insert is a lifed part on CF F404) | TRANSFER / ASSUMPTION |
| `NM.ENG.VG_ACTUATION` | FVG/CVG actuator and linkage wear, feedback-sensor drift | ENG.FVG; ENG.CVG; ENG.N2; ENG.FAULT_CODES | schedule error -> stall-margin loss; rotating stall in extreme cases | rigging check; test-cell run | TRANSFER: F100 RCVV mis-scheduling case (NASA TM-81759) |
| `NM.ENG.NOZZLE_HW` | Exhaust nozzle flap/seal/actuator wear; liner/fairing cracks | ENG.A8; ENG.T5; FIRE.WARN | A8 tracking error; at failure: fire warning, thrust loss | nozzle inspection (e.g. 800-EFH class on other fleets) | TRANSFER: F-16 Misawa AIB (nozzle fairing/liner) |
| `NM.ENG.AB_SPRAYBAR` | Afterburner spray-bar condition | ENG.AB_LIT; ENG.A8; ENG.FAULT_CODES | slow/no-light AB, rumble [ASSUMPTION] | AB inspection at shop visit | TRANSFER (F414 NPS thesis) |
| `NM.ENG.SENSOR_TRUTH` | True value vs reported value of engine sensors (T5 thermocouple drift, speed-pic… | ENG.T5; ENG.T5.HARNESS_A; ENG.T5.HARNESS_B; ENG.N1 (dual pickups) | harness disagreement; dual-pickup mismatch; residual vs model | test-cell calibration; harness check (TC resistance); RAAF rule: >5 degC L/R inlet-temperature diffe… | TRANSFER |
| `NM.ENG.FADEC_HW` | FADEC electronics aging (connector, solder, component drift) | ENG.FADEC_STATUS; ENG.FAULT_CODES | intermittent channel faults, nuisance codes | bench test at I-level (FADEC troubleshooting is I-level work on F414) | TRANSFER |
| `NM.SPS.AMAGB_WEAR` | AMAGB gear/bearing wear | SPS.AMAGB.OIL_T; SPS.AMAGB.OIL_LOW; USAGE.AMAGB_HOURS | oil temperature rise, chip/level discretes late | chip inspection; overhaul at 750 h life | DIRECT (life) / ASSUMPTION (sensors) |
| `NM.SPS.JFS_HEALTH` | JFS turbine/compressor wear and start-power margin | SPS.JFS.SPEED; SPS.JFS.EGT; SPS.JFS.OIL_QTY; USAGE.JFS_STARTS; ELEC.BATT | longer time-to-idle, higher JFS EGT, failed cold/altitude starts | JFS ground run; oil consumption check (M1 excessive consumption) | DIRECT (CAG; ADA AR) |
| `NM.SPS.BATT_SOH` | Battery capacity fade / state of health | ELEC.BATT; SPS.JFS.SPEED | lower voltage under JFS crank; earlier BATT LOW | capacity test at battery bay | DIRECT-part (45 Ah, 30 Ah warning; Tejas fitment probable) +… |
| `NM.HYD.PUMP_EFF` | Pump volumetric efficiency / internal leakage | HYD.SYS1.P; HYD.SYS2.P; HYD.SYS1.T; SPS.AMAGB.SPEED | pressure sag under high demand at low N2; higher fluid temperature | pump flow test on ground rig; case-drain check | TRANSFER (MIL-H-5440H; industrial rig data) |
| `NM.HYD.COMPENSATOR` | Pressure-compensator set-point drift | HYD.SYS1.P; HYD.SYS2.P | steady-state pressure offset from 280 bar | ground pressure check | ASSUMPTION |
| `NM.HYD.ACCUM_PRECHARGE` | Accumulator nitrogen precharge | HYD.SYS1.P (transient response); MX.ACCUM_PRECHARGE | faster pressure dips in transients; fewer brake applications available on accumulator | gauge check during servicing (MIL-H-5440H diagnostic monitor lists accumulator recharging) | TRANSFER |
| `NM.HYD.FILTER_LOADING` | Filter loading before delta-P indicator trips | HYD.FILTER_DP; HYD.SYS1.T | nothing until the pop-up/switch trips; cold-oil nuisance trips | filter element inspection/replacement; fluid particle count | DIRECT (filter count) + TRANSFER |
| `NM.HYD.FLUID_CONTAM` | Fluid contamination (particles, water) | HYD.FILTER_DP; FCS.ACT.BIT | servo-valve sticking, filter trips; water freezing gave false WoW on one F-35A | fluid sampling and particle count | TRANSFER: F-35A Eielson AIB (water in hydraulic fluid) |
| `NM.HYD.ACTUATOR_LEAK` | Actuator seal wear and internal leakage; servo-valve null shift | FCS.ELEVON.*.POS; FCS.ELEVON.*.CMD; FCS.ACT.BIT; HYD.SYS1.P | increased tracking error, null offset, lower stall load; BIT trips late | actuator rig test; leak check at shop | TRANSFER |
| `NM.HYD.HOSE_FITTING` | Hose/fitting fatigue and chafing | HYD.SYS1.P; HYD.SYS1.LEVEL; HYD.SYS2.P; HYD.SYS2.LEVEL | sudden pressure/level loss (Tejas flight test: hose rupture in one system ruptured the other) | visual inspection; leak checks | DIRECT (Tejas NFTC lessons learned) |
| `NM.FCS.ACTUATOR_FRICTION` | Actuator/linkage friction and backlash | FCS.ELEVON.*; FCS.RUDDER.POS; FCS.ACT.BIT | limit-cycle or tracking error at small amplitude [ASSUMPTION] | end-play / backlash check; actuator rig | TRANSFER (screw-actuator wear 0.001 in/1,000 FH nominal, MD-… |
| `NM.FCS.SENSOR_BIAS` | RSA/ASA true bias and scale drift | FCS.RSA.*; FCS.ASA.*; NAV.INS.BODY_RATES | channel-to-channel spread; mistrack trips | sensor assembly calibration on test set | TRANSFER (sensor class data) |
| `NM.AD.TRANSDUCER_DRIFT` | ADC pressure-transducer drift and moisture-induced offsets | AD.PS; AD.PT; AD.HP; AD.CAS; FCS.AIRDATA_MISTRACK; NAV.INS.ALT | altitude/airspeed disagreement with INS/GPS; mistrack only if single channel | pitot-static leak and calibration test (air data test set); ADC digital module reliability work on T… | DIRECT (Tejas ADC reliability modification) + TRANSFER (B-2 … |
| `NM.AD.VANE_FRICTION` | AoA/AoSS vane bearing friction and misalignment | AD.AOA_VANE_L; AD.AOA_VANE_R; AD.AOSS_VANE | L/R split, sluggish response, bias | vane calibration/alignment check | TRANSFER (B737 vane bias case) |
| `NM.AD.HEATER_ELEMENT` | Probe/vane heater element degradation | FCS.HEATER_I; AD.TAT | drop in current; icing-related air-data errors | heater resistance check | DIRECT (simplex heater current monitoring) |
| `NM.FUEL.PROBE_DRIFT` | Fuel-probe contamination/drift; true quantity vs gauged | FUEL.QTY.TANK; FUEL.TOTAL; ENG.WFM (integrated burn) | disagreement between gauged depletion and integrated fuel flow; refuel-uplift mismatch | probe check; gauging calibration; uplift reconciliation | DIRECT (Tejas probes) + TRANSFER (MIL-G-26988 error classes) |
| `NM.FUEL.PUMP_WEAR` | Boost/transfer pump wear | FUEL.BOOST_P; ENG.FUEL_INLET_T | pressure-low at high demand/negative g; relight difficulty (Tejas fitted higher-capacity DC pump for windmill … | pump flow test | DIRECT (DC pump change) + ASSUMPTION |
| `NM.ELEC.GEN_HEALTH` | Generator bearing wear, rectifier diode degradation | ELEC.GEN.V; ELEC.GEN.F; ELEC.GEN.I; ELEC.DCBUS.V | increased ripple/harmonics; trips | generator bench test; overhaul | TRANSFER |
| `NM.ELEC.WIRING` | Wiring and connector degradation (insulation, chafing, corrosion, fretting) | AV.LRU.BIT; AV.RT.STATUS; AV.1553.BUS_STATUS; FCS.CH.STATUS; ENG.FADEC_STATUS | intermittent BIT codes, bus retries, can-not-duplicate removals (NFF 30-60 %) | insulation resistance, continuity, TDR; connector inspection | DIRECT (CAG: water seepage in DFCC/avionics bay) + TRANSFER … |
| `NM.AV.SOLDER_FATIGUE` | Electronic board solder-joint fatigue / component aging | AV.LRU.HEALTH (device temperature); ECS.AVIONICS_T; AV.LRU.BIT | late intermittent faults | environmental screening; bench test; RUL models (DRDO SBC study) | TRANSFER (DSJ 75(3) 2025) |
| `NM.ECS.HX_FOULING` | Heat-exchanger fouling (effectiveness loss) | ECS.BLEED_T; ECS.COCKPIT_T; ECS.TCV; ECS.AVIONICS_T | TCV runs further open for same outlet temperature; reduced margin on hot days | HX flow/pressure-drop test; cleaning | TRANSFER |
| `NM.ECS.ACM_WEAR` | Air-cycle machine bearing wear | ECS.COCKPIT_T; ECS.BLEED_T | reduced cooling capacity | ACM overhaul/test | ASSUMPTION |
| `NM.ECS.CANOPY_SEAL` | Canopy seal and cabin leakage | ECS.CABIN_P; ECS.BLEED_P | cabin altitude higher than schedule | cabin pressure-decay test | TRANSFER (MIL-E-18927E schedules) |
| `NM.LSS.OBOGS_SIEVE` | OBOGS molecular-sieve degradation | LSS.OBOGS | lower O2 % at given demand; earlier OBOGS fail | bed replacement per schedule; test | DIRECT (OBOGS on Mk1A) + ASSUMPTION |
| `NM.LG.BRAKE_WEAR` | Brake heat-sink wear between inspections | USAGE.BRAKE_APPLICATIONS; BRK.PRESS; BRK.WHEEL_SPEED; MX.BRAKE_WEAR | none in flight data; inferred from application counts and energy | wear-pin inspection (RTO cleared at 70/90 % worn on Tejas) | DIRECT (Tejas wear % trials) |
| `NM.LG.BRAKE_TEMP` | Brake heat-sink temperature | BRK.PRESS; BRK.WHEEL_SPEED; AD.CAS (touchdown); CHUTE.STATE | energy-based estimate only | post-landing thermal check (procedural) | ASSUMPTION / TRANSFER (Boeing AERO brake energy) |
| `NM.LG.TYRE` | Tyre tread wear, cuts and pressure loss between checks | USAGE.LANDINGS; MX.TYRE_P; BRK.WHEEL_SPEED | none in flight data; burst on landing in extreme cases (2026 Tejas brake-software event: tyre burst) | daily/pre-flight pressure check; visual tread check | DIRECT (event) + TRANSFER (tyre life) |
| `NM.LG.STRUT_SERVICE` | Shock-strut gas/oil servicing state | LG.WOW; FCS.ASA.NZ (touchdown) | false WoW and changed touchdown dynamics (F-35A frozen strut case) | strut extension/pressure check | TRANSFER (USAF AIB) |
| `NM.LG.LOCK_SPRING` | Lock-link spring relaxation; downlock actuator force margin | LG.POSITION | none until collapse | spring force test; rigging check | TRANSFER: B-2 and F-16 AIB cases |
| `NM.LG.CHUTE` | Brake-chute fabric/riser degradation | USAGE.CHUTE_STREAMINGS; CHUTE.STATE | none; deploy failures | inspection; life 45 streamings / 8 years | DIRECT (DDP brake chute) |
| `NM.STR.FATIGUE` | Fatigue damage / crack initiation and growth at critical locations | FCS.VOTED.NZ; STRUCT.NZ_COUNTERS; STORES.CONFIG; FUEL.TOTAL (mass); AD.QBAR | usage spectra only (Nz exceedances, mass, stores) | NDT at scheduled inspections; individual aircraft tracking per MIL-HDBK-1530; full-scale fatigue tes… | TRANSFER (MIL-HDBK-1530B) + DIRECT (ADA fatigue test specime… |
| `NM.STR.COMPOSITE` | Composite delamination/disbond (45 % CFC structure) | none (latent) | none | ultrasonic C-scan, tap test; CAG reported delamination and cracking of "turkey feathers" on LSPs | DIRECT (CAG 17/2015; composite share from NFTC paper) |
| `NM.STR.CORROSION_WATER` | Corrosion and water ingress (bays, connectors) | AV.LRU.BIT (intermittents); ECS.AVIONICS_T | intermittent electrical faults after rain/humidity | visual inspection; drainage checks; CAG reported water seepage in cockpit, radar, DFCC and avionics … | DIRECT (CAG 17/2015) |

### Inferences
- [ASSUMPTION] Each hidden state needs three generator hooks:
  1. a degradation process (rate, driver variables, maintenance reset or partial repair);
  2. a coupling into one or more measured rows, through the physics model or the sensor model;
  3. an inspection observation model (what the inspector records, with its own error and quantisation, e.g. brake wear in 5 % steps).
  
  Ground truth for AI labels comes from (1). The AI should only ever see (2) and (3).
- [ASSUMPTION] Several states are deliberately **invisible** to the aircraft data path (composite delamination, accumulator precharge, lock-spring relaxation). Including them makes the "fragmented records" problem of the problem statement real: the only evidence lives in inspection records, keyed by tail and part serial.

### Gaps
- Fighter-specific degradation rates for most utility states (pump efficiency, filter loading, precharge loss, HX fouling) remain unpublished. Only interval proxies exist (`tejas_utility_systems.md` KQ10).
- Whether the Mk1A HUMS adds sensing for any of these (e.g. AMAGB vibration, brake temperature, structural strain) is unknown.

---

## Q6. Event inventory: cautions/warnings/advisories, exceedances, BIT faults, life-usage updates, pilot-initiated records, maintenance-relevant discrete events

### Takeaway
**Events fall into seven families:**
1. CWS cautions and warnings with voice alerts;
2. exceedances with snapshot records;
3. BIT/fault codes;
4. usage-counter updates;
5. pilot-initiated records and write-ups;
6. maintenance-relevant discrete events (starts, relights, AB, gear, WoW, chute, refuel, stores, mode reversions);
7. recorder/system events (power, time-source changes, bus-error bursts, downloads, configuration changes).

**Evidence of trigger logic:**
- Tejas-specific: CWS legends and voices; FCS reversion, reset and channel dropout; the low-fuel artefact; JFS start requirements; BIT types.
- Transfers: F404 IECMS triggers and persistence; FADEC flameout logic; the NASA hung-start rule; IRIG 106 recording-event semantics.

Each event in the generator should carry the S5000F Event fields and an IRIG 106 Ch10 recording-event number.

### Cited Findings and event table

| Event ID | Family | Trigger logic (as public sources allow) | Producer → sinks | Record content | Evidence |
|---|---|---|---|---|---|
| `EVT.CWS.RED` / `EVT.CWS.AMBER` | Caution/warning | CWS EU detects a condition from ARINC-429 words or one of 30 discretes. Legend lit, audio tone, master alarm flasher. Fire lamp → unmutable red tone. Lamp-test function | CWS → cockpit; CDR (on change); OAC log | legend ID, on/off time, ack | DIRECT-part ([DDP CWS](https://www.ddpmod.gov.in/en/resources/products/centralized-warning-system-cws)); Tejas fitment probable ([ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf)) |
| `EVT.VOICE.{AOA,LOW_ALT,CANOPY,UC}` | Voice warning | AoA exceedance; low altitude; canopy unlock; undercarriage extension (logic not public) | CWS → audio (AMU/DACS) → CVR if fitted | event time, type | DIRECT-part ([DDP CWS](https://www.ddpmod.gov.in/en/resources/products/centralized-warning-system-cws)) |
| `EVT.FIRE` | Warning | Fire/overheat detector. Extinguisher fired by push-button or automatically by crash switch | detector → CWS; CDR | warning on/off; bottle fired | DIRECT ([ADA GS](https://www.ada.gov.in/images/gs.htm)); detection statistics TRANSFER |
| `EVT.FUEL.LOW` / `BINGO` | Caution | Gauged contents below threshold. **Known false trigger** at >40° pitch, max AB, <1,200 kg remaining (fixed by tank/pick-up modification) | ECFM-C → CWS/MFD; CDR | time, contents per tank, attitude | DIRECT ([ADA AR 2017-18, 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)) |
| `EVT.HYD.LP` | Caution | System pressure below switch threshold (two systems). Also dual-system loss after hose rupture | pressure switch → EU → CWS; CDR; HUMS | system, time, pressure trace | DIRECT event ([NFTC 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)); TRANSFER logic (MIL-H-5440H) |
| `EVT.ELEC.GEN_OUT` | Caution | GCU trips the main generator (underspeed or fault) → backup 5 kW DC generator / battery; transfer ≤50 ms | GCU → EU → CWS; CDR | time, bus voltages | DIRECT backup gen ([DRDO](https://drdo.gov.in/5-kw-brushless-dc-generating-system-lca-tejas-0)); TRANSFER 704F |
| `EVT.FCS.DEGRADE` | Caution/BIT | Channel failure or dropout (reset possible); air-data mistrack trips; multiple air-data failures → reversion to fixed-gain law; spin mode selection | DFCC → OAC/CWS; CDR via 1553; FTI | channel, subsystem, mode, reset | DIRECT ([Kala](https://joast.org/index.php/joast/article/view/317); [DSJ 56(1)](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863); [NFTC](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)) |
| `EVT.ENG.CAUTION` | Caution | FADEC/ECMS "engine warning interface" (ARINC/discretes) to CWS: e.g. oil pressure low, overtemperature, overspeed, flameout, stall ("L STALL"-type on F/A-18) | FADEC/ECMS → CWS; ECMS log; CDR | condition, snapshot | DIRECT-part (CWS); TRANSFER ([Swiss F/A-18 report via `f404_in20_engine_model.md` Q9](https://www.newsd.admin.ch/newsd/message/attachments/48614.pdf)) |
| `EVT.EXC.ENG` | Exceedance | N1, N2, T5, oil pressure or vibration beyond limit, persisting several iterations → caution + code + record of **5 s pre + 25 s post** (USN) or **+35 s post** (CF) | ECMS → ECMS log; DL | 10 Hz gas path + 1 Hz slow parameters in window | TRANSFER ([Hess; Paré & Muir](https://archive.org/details/DTIC_ADA347270)) |
| `EVT.EXC.G` / `EVT.EXC.AOA` / `EVT.EXC.SPEED` | Exceedance | Nz beyond +8/−3.5 g (DFCC v7307: 8.5 g subsonic, 6 g supersonic); AoA beyond the limiter (IOC 22°, PID to 24°); speed/Mach beyond the clearance (IOC 1,350 km/h; M1.6) | DFCC/OAC → log; CDR; counters | peak value, duration, configuration | DIRECT limits ([ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf); [CEMILAC IOC note via KQ4](https://joast.org/index.php/joast/article/view/441)); logic ASSUMPTION |
| `EVT.BIT.PBIT` | BIT | Power-up and pre-flight BIT (DFCC sensor BIT before each flight; FBW diagnostic ≈10 min on TD-1) → go/no-go | DFCC, ADC, LRUs → OAC log; cockpit | pass/fail per subsystem | DIRECT ([Kala](https://joast.org/index.php/joast/article/view/317); [Livefist](https://www.livefistdefence.com/25-years-on-my-recollections-of-the-1st-tejas-flight/)) |
| `EVT.BIT.CBIT` | BIT | Continuous monitors (mistrack, watchdog, wrap-around, range). Latched faults → fault code; PFL subset → CWS | LRUs → 1553 BIT words/status flags → OAC log; CDR | code, LRU, channel, time, latch state | DIRECT existence; TRANSFER code structure ([F110 MFL/PFL](https://archive.org/details/DTIC_ADA203800)) |
| `EVT.BIT.MBIT` / `IBIT` | BIT | Ground maintenance or initiated BIT with WoW (1553 mode code 3; AFDS ground diagnosis) | LRU → OAC/ground test set → maintenance record | test-step results, subsystem diagnosis | DIRECT ([JOAST 782](https://joast.org/index.php/joast/article/view/782)); TRANSFER (1553 mode codes) |
| `EVT.BUS.ERR` | System | 1553 no-response, parity/Manchester errors, retries, Subsystem/Terminal flag set; burst behaviour | BC/OAC → log; bus monitor (CDR/HUMS) | bus, RT, error type, count | TRANSFER (1553 standard); ASSUMPTION rates |
| `EVT.LUI.UPDATE` | Usage | Running LUI sums written **twice per flight** | ECMS → ECMS log → DL | 8 LUI values, EOT | DIRECT (Tejas ECMS computes LUIs, [ADA](https://www.ada.gov.in/images/ps.htm)); TRANSFER (twice per flight, [Paré & Muir](https://archive.org/details/DTIC_ADA347270)) |
| `EVT.TAKEOFF_RECORD` | Usage/trend | Throttle reaches take-off power → lift-off (typically 6–10 s); trend data and thrust check | ECMS → log → DL | 10 Hz gas path; computed thrust | TRANSFER ([Muir et al.](https://archive.org/details/DTIC_ADA203800)) |
| `EVT.USAGE.SORTIE` | Usage | End of sortie: flight hours, landings, gear cycles, chute streamings, AB lights, starts/relights, brake applications, Nz level-crossing counts (8 g-levels), JFS starts | OAC/ECMS/HUMS → DL → maintenance records | counter deltas | DIRECT (chute life, JFS starts); TRANSFER (fatigue meter 8 levels, [JOAST 863](https://joast.org/index.php/joast/article/view/863)) |
| `EVT.PILOT.MARK` | Pilot-initiated | Record button / event marker → buffered pre-event + post-event capture | cockpit → ECMS/OAC/HUMS log | window of selected parameters | TRANSFER (F/A-18 IECMS record button; F110: 12 pre (6 s) + 4 post (2 s) scans; HARV "PILOT EVENT" at 40 sps) |
| `EVT.PILOT.WRITEUP` | Pilot-initiated | Debrief write-up of observed anomalies ("Pilot and Maintenance observations" closed through the RSD; RFAs in flight test) | ground → maintenance record | free text + codes | DIRECT practice ([CEMILAC](https://joast.org/index.php/joast/article/view/325); [NFTC](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)); format TRANSFER (NAMP) |
| `EVT.START` | Discrete | JFS start (GTSU-110) → light-off → starter cut-out (≈55 % N2) → idle (≈63–70 % N2 at ≈40 s; T-50 data). Outcomes: success, hung start (N2 <60 % not rising 1 s, or <60 % for 35 s), hot start (threshold not public), JFS failure. Requirement: 3 consecutive starts (2 starts + dry rollover) | FADEC/EU → ECMS/HUMS; DL; counters | timeline, peak T5, JFS EGT, battery state | DIRECT requirement ([CAG 17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf)); TRANSFER timings ([KSAS 2006](https://koreascience.kr/article/JAKO200616039849001.pdf); [TM-101702](https://ntrs.nasa.gov/citations/19900013006)) |
| `EVT.SHUTDOWN` | Discrete | PLA to cut-off; spool-down; post-shutdown T5 monitoring | FADEC → ECMS | spool-down time, residual T5 | TRANSFER (-400 post-shutdown fire detection via T5, [CR-1998-208416](https://ntrs.nasa.gov/citations/19980219005)) |
| `EVT.FLAMEOUT` / `EVT.RELIGHT` | Discrete | T5 < f(altitude, PLA) and dN2/dt < threshold → flameout flag → auto-relight. Spool-down airstart from ≥24 % N2; JFS-assisted relight; windmill relight helped by a higher-capacity DC fuel pump | FADEC → CWS; ECMS; CDR | times, N2 at relight, success | TRANSFER (F404-102, RM12); DIRECT (JFS relight; DC pump, [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf)) |
| `EVT.AB` | Discrete | AB selected → light-off detected by UV flame sensor (0.7–2.7 s MIL→max); no-light/blow-out → fault | FADEC → ECMS counter | light time, failures | TRANSFER (F404-402 NAWCAD) |
| `EVT.GEAR` / `EVT.WOW` | Discrete | Gear handle and lock transitions; emergency extension (cable); WoW transitions define take-off and landing (and FCS ground law) | EU/DFCC → CDR; counters | times, touchdown Nz peak | DIRECT design (uplocks, emergency cable); TRANSFER (HARV/F/A-18C words) |
| `EVT.CHUTE` | Discrete | Deploy at ≤285 (≤340) km/h; jettison; unsafe | EU → CDR; counter | speed at deploy, streaming count | DIRECT ([DDP 8027](https://www.ddpmod.gov.in/node/8027)) |
| `EVT.REFUEL` | Discrete | Hot refuel, pressure refuel, AAR contact, fuel dump (Navy) | ECFM-C/GRP → log | quantities, times | DIRECT ([ADA ARs](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf)) |
| `EVT.STORES` | Discrete | Store release/jettison; configuration change | SMS → OAC log; CDR | station, store type | DIRECT (SMS, MIL-STD-1760C) |
| `EVT.SYS.POWER` / `EVT.SYS.TIME` / `EVT.SYS.CONFIG` / `EVT.DOWNLOAD` | System | Power-up/down; GPS/IRIG time lock and loss; software load or LRU swap (serial change); post-flight download (retries can produce duplicates) | OAC/recorders/ground | version and serial manifest | DIRECT (version naming); TRANSFER ([IRIG 106 Ch10 time and recording events](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2); ALIS record defects) |

- [DIRECT, exclusion] ADA's "Degraded Data Warning Assessment" concerns weapon-system data quality (Derby missile trials), not aircraft health. It belongs to mission avionics, not this inventory — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf).
- [TRANSFER] IRIG 106 recording events: TMATS Event Type (External / Measurement Discrete / Measurement Limit / Recorder / Other), priority, capture mode, limit count. Ch10 event packets carry event number (4,096 types), count and time — [`data_pathway_and_formats.md` Q3](https://www.trmc.osd.mil/wiki/download/attachments/113019518/chapter9.pdf?api=v2).

### Inferences
- [ASSUMPTION] **Emit every event twice:**
  - inside the per-sortie Ch10 file, as recording events plus the underlying discretes and BIT words;
  - as decoded S5000F-shaped event records on the ground stream.
  
  This lets the downstream system face real duplication and late arrival.
- [ASSUMPTION] Give each caution an explicit **missed-detection probability** and **false-alarm rate**, and each BIT code a **CND/NFF propensity**. This reproduces the F110 "70 % correct isolation" and F101 "2 potential false alarms per flight" maturity effects and the Tejas low-fuel artefact, without inventing Tejas statistics.

### Gaps
- CWS legend list; Tejas caution thresholds and persistence timers; ECMS exceedance limits and snapshot windows; whether pilot event marking exists on Tejas.

---

## Q7. Rate groups and timing: synthesis and recommendation for the virtual aircraft

### Takeaway
The public evidence supports **at least three asynchronous clock domains**:
- **DFCC flight-control domain:** 80 Hz base (12.5 ms) [DIRECT], with binary sub-rates 40/20/10 Hz [TRANSFER: F/A-18 FCC 80/40/20/10 sps].
- **FADEC engine-control domain:** ≈50–67 Hz [TRANSFER: generic NASA FADEC templates].
- **Avionics/utility 1553 domain**, scheduled by the bus controller. ADE's example health message at 12.5 Hz with 4 minor frames per major frame implies a 50 Hz minor / 12.5 Hz major frame [DIRECT-unnamed]. Public 1553 schedules run 5–100 Hz.

Recording then **decimates per sink**:
- ECMS: 10 Hz gas-path and 1 Hz slow parameters, plus event windows [TRANSFER: IECMS].
- Crash recorder: about 1–16 Hz per parameter [ASSUMPTION; anchored by DASHlink's measured 0.25–16 Hz and the 14 CFR App M minima].
- FTI: 64–800 Hz [TRANSFER].
- Vibration: raw at kHz rates, processed onboard to 1 Hz features.

The recommended structure is in the table below.

### Cited Findings (evidence for timing)
- Tejas DFCC: 12.5 ms frame; ADC offloading because OFP exceeded "75% of 12.5 msec"; multi-rate scheduler; 8 ms computation delay modelled in stability analysis — [Kala 2015](https://joast.org/index.php/joast/article/view/317); [JOAST 58(4)](https://joast.org/index.php/joast/article/view/741) [DIRECT].
- F/A-18 FCC: "sampling rates of 80, 40, 20 and 10 samples per second used by the actual aircraft flight control computer" — [NASA TM-107601 §9.2 (via `candidate_airframe_modelling_data.md`)](https://ntrs.nasa.gov/api/citations/19920024293/downloads/19920024293.pdf) [TRANSFER].
- HARV recording: production-system data at 40 sps; RFCS internals at 80; surfaces, booms and CG accelerations at 160; pressure taps at 10/25/320; tail accelerometers at 800 — [CR-201670 App. A](https://ntrs.nasa.gov/citations/19970014822) [TRANSFER].
- F/A-18C 1553 mux measurands recorded at 20 sps by the test data system — [NAWCADPAX/RTR-2001/1](https://archive.org/details/DTIC_ADA407860) [TRANSFER].
- CF-18 IECMS: 10 Hz and 1 Hz groups; 5 s + 25/35 s windows — [Muir et al.](https://archive.org/details/DTIC_ADA203800) [TRANSFER].
- ADE 1553 example: 12.5 Hz health status; 4 minor frames per major frame — [JOAST 63(4)](https://joast.org/index.php/joast/article/view/598) [DIRECT-unnamed].
- HAL trainer ADC: ARINC-429 output refresh 20 Hz; FTI recording 64 Hz; ADTS stimulus 2 Hz — [JOAST 67(2A)](https://joast.org/index.php/joast/article/view/331) [TRANSFER: Indian trainer].
- 1553 practice: minor frames "rarely go above 100 Hz"; ≤50 % bus loading recommended. KC-135 public Ch10 sample: mostly ~10/20 Hz, some ~41 and ~163–248 Hz — [`data_pathway_and_formats.md` Q2](https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf) [TRANSFER].
- DASHlink QAR: 0.25/1/2/4/8/16 Hz parameter rates; fixed inter-channel skews 0.04–0.25 s; 6-s GMT granularity; 917 ppm clock-rate error; ≈10⁻⁶ frame loss — [`empirical_dashlink_texture.md` Q1, Q8](https://c3.ndc.nasa.gov/dashlink/projects/85/) [MEASURED].
- Bus suitability: signals ≤400 Hz are "prime candidates" for 1553; faster signals (vibration) are processed off-bus — [MIL-STD-1553B rationale §10.3 via `data_pathway_and_formats.md` Q1](https://www.milstd1553.com/wp-content/uploads/2012/12/MIL-STD-1553B.pdf) [DIRECT standard].

**Recommended rate-group structure for the virtual Tejas-class aircraft**

| Group | Period / rate | Clock domain | Typical contents (CSV IDs) | Evidence tag |
|---|---|---|---|---|
| `FCS80` | 12.5 ms / 80 Hz | DFCC minor frame | RSA, ASA, pilot commands, surface positions and commands, voting, CBIT monitors, ADC inputs over RS-422 | DIRECT (Tejas 12.5 ms) |
| `FCS40` / `FCS20` / `FCS10` | 25 / 50 / 100 ms | DFCC sub-rates | DFCC transmit buffers for the 1553 RT, mode logic, gain scheduling, slow CBIT, outer loops | TRANSFER (F/A-18 FCC 80/40/20/10) + ASSUMPTION (allocation) |
| `FADEC-INT` | 15–20 ms / 50–67 Hz | FADEC | engine sensors, control loops, limiters, flameout logic | TRANSFER (NASA C-MAPSS40k/MAPSS templates) |
| `AV50` | 20 ms / 50 Hz | avionics 1553 minor frame (BC) | INS words; BC poll of DFCC buffers (40 Hz producer → 50 Hz poll gives repeated/stale samples) | ASSUMPTION grounded in the ADE example (12.5 Hz with 4 minor frames) |
| `AV25` | 40 ms / 25 Hz | 1553 | air data to avionics; engine performance words; hydraulic pressure; brakes/NWS; radar altimeter | TRANSFER (HAL trainer ADC 20 Hz; F/A-18C 20 sps) + ASSUMPTION |
| `AV12.5` | 80 ms / 12.5 Hz (major frame) | 1553 | LRU health/status words, FADEC status, fuel contents, AMAGB/JFS, oil pressure, bus status | DIRECT-unnamed (ADE 12.5 Hz health message) |
| `AV6.25` | 160 ms / 6.25 Hz | 1553 | slow temperatures, electrical, ECS, hydraulic temperature/level | ASSUMPTION (keeps binary submultiples of the major frame) |
| `SLOW1` | 1 s / 1 Hz | 1553 / recorders | time words, OBOGS/LOX, battery, vibration features | TRANSFER (IECMS 1 Hz; DASHlink 1 Hz class) |
| `EVT` | on change | owning LRU, carried in status words | discretes, cautions, BIT codes, mode changes | TRANSFER (IRIG 106 event semantics) |
| `ECMS10` / `ECMS1` | 100 ms / 1 s + windows | ECMS record | gas path at 10 Hz; oil/vibration/Nz/fuel temperature/valves at 1 Hz; 5 s pre + 25–35 s post; take-off 6–10 s; LUIs twice per flight | TRANSFER (CF-18/USN IECMS) |
| `CDR16` / `CDR8` / `CDR4` / `CDR1` | 16 / 8 / 4 / 1 Hz | crash recorder (bus monitor) | FCS controls, surfaces and Nz at 16; attitudes and rates at 8; air data and engine at 4; utility at 1; discretes on change | ASSUMPTION (DASHlink measured 0.25–16 Hz; 14 CFR App M minima: Nz 8 Hz, FBW controls 8 Hz) |
| `HUMS` | configurable 1–10 Hz + bursts | HUMS DAU (PCAMi-1000-like) | utility analogs (RTD/TC/pressure), bus-monitored words, vibration features; event-triggered raw bursts | DIRECT (DAU exists) + ASSUMPTION (rates) |
| `HF` | 1–10 kHz raw | vibration front-end | accelerometer waveforms → features at 1 Hz (raw only in FTI/test cell) | TRANSFER (DSTO F404 vibration; 1553 ≤400 Hz rule) |
| `FTI` | 64–800 Hz | FTI PCM/DRU/telemetry | test-only parameters (≈1,500), strain, boom air data | TRANSFER (HAL trainer 64 Hz; HARV 25–800 sps) + DIRECT (count) |
| `SORTIE` / `INSP` | per sortie / per inspection | ground | counters, configuration, inspection measurements | DIRECT/TRANSFER per row |

**Parameter IDs by bus rate group** (from `parameter_inventory.csv`, column `rate_group_bus`; acquisition and record groups are in their own columns):

- `AV50 poll of DFCC buffer updated at FCS40` (30): `FCS.RSA.P`, `FCS.RSA.Q`, `FCS.RSA.R`, `FCS.ASA.NZ`, `FCS.ASA.NY`, `FCS.VOTED.Q`, `FCS.VOTED.NZ`, `FCS.VOTED.DE`, `FCS.STICK.PITCH`, `FCS.STICK.ROLL`, `FCS.PEDAL`, `FCS.ELEVON.LOB.POS`, `FCS.ELEVON.LOB.CMD`, `FCS.ELEVON.LIB.POS`, `FCS.ELEVON.LIB.CMD`, `FCS.ELEVON.RIB.POS`, `FCS.ELEVON.RIB.CMD`, `FCS.ELEVON.ROB.POS`, `FCS.ELEVON.ROB.CMD`, `FCS.RUDDER.POS`, `FCS.RUDDER.CMD`, `FCS.SLAT.POS`, `FCS.AIRBRAKE.POS`, `FCS.ACT.BIT`, `FCS.CH.STATUS`, `FCS.MODE`, `FCS.AIRDATA_MISTRACK`, `FCS.HEATER_I`, `FCS.KALMAN_ATT`, `HYD.CH_STATUS`
- `AV50` (13): `NAV.INS.LAT`, `NAV.INS.LON`, `NAV.INS.ALT`, `NAV.INS.VN`, `NAV.INS.VE`, `NAV.INS.VD`, `NAV.INS.HDG_TRUE`, `NAV.INS.PITCH`, `NAV.INS.ROLL`, `NAV.INS.BODY_RATES`, `NAV.INS.ACCEL`, `NAV.GPS.STATUS`, `AV.RT.STATUS`
- `AV25` (37): `ENG.PLA`, `ENG.N1`, `ENG.N2`, `ENG.T1`, `ENG.PS3`, `ENG.P5`, `ENG.T5`, `ENG.WFM`, `ENG.A8`, `ENG.AB_LIT`, `AD.PS`, `AD.PT`, `AD.DPA`, `AD.DPB`, `AD.AOA_VANE_L`, `AD.AOA_VANE_R`, `AD.AOSS_VANE`, `AD.TAT`, `AD.HP`, `AD.HBARO`, `AD.CAS`, `AD.TAS`, `AD.MACH`, `AD.AOA`, `AD.BETA`, `AD.SAT`, `AD.HDOT`, `AD.QBAR`, `AD.VALID`, `NAV.AHRS`, `NAV.RADALT`, `HYD.SYS1.P`, `HYD.SYS2.P`, `BRK.PEDAL`, `BRK.WHEEL_SPEED`, `BRK.PRESS`, `NWS.STATE`
- `AV12.5` (10): `ENG.OIL_P`, `ENG.FADEC_STATUS`, `SPS.AMAGB.SPEED`, `SPS.JFS.SPEED`, `SPS.JFS.EGT`, `FUEL.QTY.TANK`, `FUEL.TOTAL`, `AV.1553.BUS_STATUS`, `AV.LRU.BIT`, `AV.LRU.HEALTH`
- `AV6.25` (19): `ENG.OIL_T`, `ENG.FUEL_INLET_T`, `HYD.SYS1.T`, `HYD.SYS1.LEVEL`, `HYD.SYS2.T`, `HYD.SYS2.LEVEL`, `FUEL.TEMP`, `ELEC.GEN.V`, `ELEC.GEN.F`, `ELEC.GEN.I`, `ELEC.TRU.VI`, `ELEC.BACKUP.STATUS`, `ELEC.DCBUS.V`, `ECS.BLEED_P`, `ECS.BLEED_T`, `ECS.COCKPIT_T`, `ECS.TCV`, `ECS.CABIN_P`, `ECS.AVIONICS_T`
- `SLOW1` (8): `ENG.VIB.OVERALL`, `ENG.VIB.N1_1REV`, `ENG.VIB.N2_1REV`, `SPS.AMAGB.OIL_T`, `ELEC.BATT`, `LSS.OBOGS`, `LSS.LOX_QTY`, `SYS.TIME`
- `EVT` (29): `ENG.OIL_LEVEL`, `ENG.LUBE_DP`, `ENG.CHIP`, `ENG.IGN`, `ENG.FAULT_CODES`, `ENG.FLAMEOUT`, `ENG.LIMIT_FLAGS`, `ENG.BLEED_STATE`, `FCS.BIT.LOG`, `SPS.AMAGB.OIL_LOW`, `HYD.SYS1.LP`, `HYD.SYS2.LP`, `HYD.FILTER_DP`, `FUEL.BOOST_P`, `FUEL.TANK_PRESS`, `FUEL.REFUEL_EVT`, `ELEC.GEN.OUT`, `ECS.SWITCHES`, `LG.POSITION`, `CHUTE.STATE`, `FIRE.WARN`, `CWS.LEGEND`, `CWS.MASTER`, `CWS.VOICE.AOA`, `CWS.VOICE.LOW_ALT`, `CWS.VOICE.CANOPY`, `CWS.VOICE.UC`, `SYS.EVENT_MARKER`, `STORES.CONFIG`
- `download` (24): `LUI.TYPE1`, `LUI.TYPE3`, `LUI.EFTC`, `LUI.SRC`, `LUI.TAMP`, `LUI.PS3_FULL`, `LUI.PS3_PART`, `LUI.EOT`, `USAGE.TAC`, `SPS.JFS.OIL_QTY`, `AV.SW_CONFIG`, `SYS.IDS`, `SYS.PHASE`, `STRUCT.NZ_COUNTERS`, `USAGE.FLIGHT_HOURS`, `USAGE.LANDINGS`, `USAGE.GEAR_CYCLES`, `USAGE.CHUTE_STREAMINGS`, `USAGE.BRAKE_APPLICATIONS`, `USAGE.JFS_STARTS`, `USAGE.AMAGB_HOURS`, `USAGE.AB_LIGHTS`, `USAGE.ENGINE_STARTS`, `USAGE.G_EXCEEDANCE`
- `FTI PCM / telemetry` (5): `ENG.WFAB`, `AD.BOOM`, `STRUCT.STRAIN`, `FTI.ALL`, `FCS.FTP`
- `none` (12): `ENG.T25`, `ENG.T5.HARNESS_A`, `ENG.T5.HARNESS_B`, `ENG.FVG`, `ENG.CVG`, `ENG.THRUST_EST`, `MX.TYRE_P`, `MX.BRAKE_WEAR`, `MX.ACCUM_PRECHARGE`, `MX.OIL_SERVICING`, `MX.SOAP`, `MX.BORESCOPE`
- `video` (1): `DVR.VIDEO`
- `FCS40` (1): `LG.WOW`


### Inferences
- [ASSUMPTION] **Timing realism comes from the boundaries between domains, not from any single rate.** Run each LRU on its own drifting oscillator (tens of ppm). Let the BC poll asynchronously, so `t_bus − t_sample` varies between zero and one producer period. Let recorders time-tag at receipt.
  - The decoder then has to deal with duplicated samples (40 Hz producer → 50 Hz poll), skipped samples (80 → 25 Hz), fixed skews and clock drift. These are the same artefacts measured in DASHlink.
  - Use the six-time-field convention of `data_pathway_and_formats.md` Q6: `t_true`, `t_sample`, `t_bus`, `t_record`, `t_utc`, `t_ingest`.
- [ASSUMPTION] Make every group configurable in the dictionary (base rates, divisors, recorder decimation) and record the configuration in the sortie manifest. When real Tejas schedules become known, only the dictionary changes.

### Gaps
- No Tejas 1553 schedule, FADEC frame rate, ADC/INS output rate, CDR sampling plan or HUMS configuration is public. Every non-DFCC rate above is TRANSFER or ASSUMPTION.

---

## Synthesis (required closing items a–f)

### Takeaway
**Publicly evidenced Tejas architecture:**
- ADA OAC/MC as avionics and health hub; quadruplex DFCC (80 Hz) with its own 1553 output to CDR/GUH/FTI.
- Two utility EUs in production (BHEEM-EU, ECFM-C); FADEC + ECMS; CWS with voice; ≥3 1553 buses (secondary) plus a weapon bus.
- Recorders and retrieval: CDR, MPRU-in-OAC and a DVR; ≈1,500-parameter FTI; a 124-unit indigenous HUMS DAU for Mk1A.

This is enough to build a **credible, explicitly synthetic** Phalanx ICD. The inventory (189 parameters, 50 hidden states, about 30 event types, 15 rate groups) is structured to seed the versioned dictionary. Its weakest links are the engine monitoring content and all bus- and recorder-level specifics, which rest on F404/F/A-18 transfers.

### Cited Findings — (a) Key findings
1. **Avionics hub.** The ADA OAC combines mission computer, display processor, video switching and mission preparation and retrieval. It drives 3 MFDs, the HUD and the HMD. The "utility and health management system provides system health and warnings to the pilot through" it. [DIRECT] — [tejas.gov.in OAC](http://web.archive.org/web/2015/http://www.tejas.gov.in:80/technology/open_architecture_computer_for_avionics.html); [tejas.gov.in Systems](http://web.archive.org/web/2016/http://www.tejas.gov.in:80/specifications/systems.html)
2. **DFCC data path.** Each DFCC channel has its own 1553B interface, RS-422 and CCDL; 23 diagnosable subsystems per channel (92 in total). DFCC → 1553 → CDR, GUH, FTI. [DIRECT] — [JOAST 782](https://joast.org/index.php/joast/article/view/782); [NFTC 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)
3. **Utility EUs.** Four prototype EUs (engine, electrical, hydraulic, fuel, ECS) became two in production: BHEEM-EU and ECFM-C. Prototypes had a "Digital Hydraulic Electronic Unit" for brake-by-wire. [DIRECT] — [NFTC 2005](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf); [ADA AR 2015-16, 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)
4. **Warning system.** HAL SLRDC CWS: 2 display units + 1 electronic unit, 30 red/amber legends, four voice warnings, ARINC-429 + 30 discretes, FADEC warning interface. Tejas fitment is probable from ADA budget lines. [DIRECT-part] — [DDP CWS](https://www.ddpmod.gov.in/en/resources/products/centralized-warning-system-cws)
5. **Recording on Tejas:** a Crash Data Recorder; an MPDRU, whose function is now inside the OAC; a Video Digital Recorder; ECMS usage logging; and FTI of about 1,500 parameters with 12 telemetry stations. Vendor, standard and parameter lists are not public. [DIRECT] — [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf); [ADA NFTC/facilities](https://www.ada.gov.in/images/nftc.htm)
6. **Mk1A HUMS.** ADA initiated it in 2018-19; vendor selection was complete and the PO "being placed" in 2020-21. PCC received a 124-unit PCAMi-1000 HUMS DAU production order (published 4 Feb 2026); it replaces a US-imported DAU and is field-configurable, Ethernet master–slave, data/audio/video. Scope is not public. [DIRECT] — [ADU](https://www.aviation-defence-universe.com/pcc-advances-indigenous-hums-capability-with-pcami-1000-production-order); [PCC](https://www.parkcontrols.com/industries/air)
7. **Avionics generations:**
   - Mk1A: HAL mission computer (MCSRDC; Mistral builds hardware), DMG (1553B, ARINC 818), SMFD, CIT, DACS (1553B/429/Ethernet; POST/IBIT/CBIT), PowerPC DO-178C DFCC.
   - Mk2: TSN Ethernet, MMDC, AMT.
   
   [DIRECT / DIRECT-part] — [ADA ARs 2018–22](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf); [DDP](https://www.ddpmod.gov.in/en/resources/products/i-dmgindigenous-digital-map-generator)
8. **BIT is public only as types and coverage.** DFCC CBIT/PBIT/MBIT; sensor and actuator BIT from the DFCC; ADC 90 % coverage; ≈10-min FBW pre-flight diagnostic on TD-1; ground AFDS diagnosing 92 DFCC subsystems from test-step numbers. [DIRECT] — [Kala](https://joast.org/index.php/joast/article/view/317); [JOAST 261](https://joast.org/index.php/joast/article/view/261)
9. **Released analogues for fault-code design.** F/A-18 IECMS MMP (3-digit, 44 engine + 231 other codes); F110 EMS MFL (≤80 flags) with PFL subset → master caution; data transfer cartridge; about 70 % correct LRU isolation in early service. [TRANSFER] — [AGARD-CP-448](https://archive.org/details/DTIC_ADA203800)
10. **Rate evidence** converges on asynchronous clock domains: DFCC 80 Hz (DIRECT); F/A-18 FCC 80/40/20/10 Hz; HARV system data at 40 sps; F/A-18C mux at 20 sps; IECMS 10/1 Hz; ADE 1553 health at 12.5 Hz; HAL trainer ADC at 20 Hz; DASHlink QAR 0.25–16 Hz (MEASURED).
11. **Not measured.** Most maintenance-critical states are hidden: component efficiencies, clearances, cracks, life consumed, bearing spalls, pump efficiency, precharge, filter loading, brake and tyre wear, structural fatigue, wiring. They reach maintainers only through partial signals, counters or inspection, which is exactly the fragmentation the problem statement describes. [TRANSFER/DIRECT mix]

#### (b) Inventory summary statistics and rate-group recommendation
- **Statistics (from `parameter_inventory.csv`, 189 rows).**
  - By subsystem: engine 41 (incl. 8 LUIs and TAC); FCS 31; air data 20; avionics status/warnings/recorder/metadata 20; navigation 14; hydraulics 10; usage counters 10; ECS/life support 9; electrical 8; gear/brakes/NWS/chute 7; secondary power 6; fuel 6; ground-inspection bridges 6; fire 1.
  - By class: measured 80; computed 54; discrete 23; counters 20; events 6; inspection 6.
  - By evidence basis: DIRECT-only 62; DIRECT + transfer/assumption 70; transfer-led 44; transfer + assumption 4; assumption-only 9.
  - By sink: crash recorder 93 (+56 assumed); ECMS/HUMS 89 (+25); maintenance download 108 (+67); cockpit 72 (+44); FTI-only 3.
  - 62 rows carry conflict or caveat notes; 3 restricted-source flags.
- **Rate-group recommendation** (full table in Q7):
  - DFCC domain: `FCS80` / `FCS40` / `FCS20` / `FCS10`.
  - FADEC domain: `FADEC-INT`, 50–67 Hz.
  - Avionics 1553 domain: `AV50` minor / `AV25` / `AV12.5` major / `AV6.25` / `SLOW1`.
  - Recorder groups: `ECMS10`/`ECMS1` + event windows; `CDR16`/`CDR8`/`CDR4`/`CDR1`; `HUMS` (configurable); `HF` (kHz raw → 1 Hz features); `FTI` (64–800 Hz).
  - Ground groups: `EVT`, `SORTIE`, `INSP`.
  
  Domains run on independent drifting clocks with asynchronous polling, which yields realistic staleness, duplication and skew.

### Inferences — (c) Not-measured list (summary; full detail in `not_measured_states.csv`)
- **Model-observable only** (need gas-path, hydraulic or thermal models):
  - `NM.ENG.FAN_HEALTH`, `NM.ENG.HPC_HEALTH`, `NM.ENG.HPT_HEALTH`, `NM.ENG.LPT_HEALTH`, `NM.ENG.TIP_CLEARANCE`, `NM.ENG.VG_ACTUATION`, `NM.ENG.SENSOR_TRUTH`;
  - `NM.HYD.PUMP_EFF`, `NM.HYD.COMPENSATOR`, `NM.HYD.ACTUATOR_LEAK`;
  - `NM.ECS.HX_FOULING`, `NM.ECS.ACM_WEAR`, `NM.ECS.CANOPY_SEAL`, `NM.LSS.OBOGS_SIEVE`;
  - `NM.FUEL.PROBE_DRIFT`, `NM.FUEL.PUMP_WEAR`, `NM.ELEC.GEN_HEALTH`, `NM.SPS.JFS_HEALTH`, `NM.SPS.BATT_SOH`;
  - `NM.FCS.SENSOR_BIAS`, `NM.AD.TRANSDUCER_DRIFT`, `NM.AD.VANE_FRICTION`, `NM.AD.HEATER_ELEMENT`.
- **Usage-inferred only (counters):** `NM.ENG.DISK_LIFE`, `NM.ENG.BLADE_CREEP`, `NM.STR.FATIGUE`, `NM.LG.BRAKE_WEAR`, `NM.LG.BRAKE_TEMP`, `NM.LG.TYRE`, `NM.LG.CHUTE`, `NM.SPS.AMAGB_WEAR`.
- **Late-symptom only:** `NM.ENG.BLADE_CRACK`, `NM.ENG.BEARING_SPALL`, `NM.ENG.SEAL_WEAR`, `NM.ENG.NOZZLE_HW`, `NM.ENG.AB_SPRAYBAR`, `NM.ENG.FUEL_NOZZLE`, `NM.ENG.FADEC_HW`, `NM.HYD.HOSE_FITTING`, `NM.LG.LOCK_SPRING`, `NM.ELEC.WIRING`, `NM.AV.SOLDER_FATIGUE`, `NM.FCS.ACTUATOR_FRICTION`.
- **Ground inspection only:** `NM.HYD.ACCUM_PRECHARGE`, `NM.HYD.FILTER_LOADING`, `NM.HYD.FLUID_CONTAM`, `NM.ENG.OIL_CONDITION`, `NM.LG.STRUT_SERVICE`, `NM.STR.COMPOSITE`, `NM.STR.CORROSION_WATER`.

#### (d) Event inventory (summary; full table in Q6)
- **Cautions/warnings:** `EVT.CWS.RED`/`AMBER`, `EVT.VOICE.*` (AoA, low altitude, canopy, U/C), `EVT.FIRE`, `EVT.FUEL.LOW`/`BINGO` (with the documented high-pitch false trigger), `EVT.HYD.LP`, `EVT.ELEC.GEN_OUT`, `EVT.FCS.DEGRADE`, `EVT.ENG.CAUTION`.
- **Exceedances:** `EVT.EXC.ENG` (5 s + 25/35 s windows), `EVT.EXC.G`/`AOA`/`SPEED`.
- **BIT:** `EVT.BIT.PBIT`/`CBIT`/`MBIT`/`IBIT`, `EVT.BUS.ERR`.
- **Usage:** `EVT.LUI.UPDATE` (twice per flight), `EVT.TAKEOFF_RECORD`, `EVT.USAGE.SORTIE`.
- **Pilot:** `EVT.PILOT.MARK`, `EVT.PILOT.WRITEUP`.
- **Discrete maintenance events:** `EVT.START` (JFS; 3-consecutive-start requirement; hung/hot start), `EVT.SHUTDOWN`, `EVT.FLAMEOUT`/`RELIGHT`, `EVT.AB`, `EVT.GEAR`/`WOW`, `EVT.CHUTE`, `EVT.REFUEL`, `EVT.STORES`.
- **System:** `EVT.SYS.POWER`/`TIME`/`CONFIG`, `EVT.DOWNLOAD`.

### Gaps — (e) Open questions and gaps (priority order)
1. **Tejas bus topology and ICD:**
   - number and role of the 1553 buses; BC/back-up BC; RT map; message rates;
   - FADEC/ECMS interface type (1553 RT vs ARINC-429 vs discrete);
   - BHEEM-EU/ECFM-C I/O lists.
   
   Leads: ADA/ADE design papers (an AIAA GNC 2002 control-law paper and the ACCS paper are known but inaccessible); CEMILAC TA documents (drdo.gov.in inaccessible during this session); HAL MCSRDC/ARDC publications.
2. **Crash data recorder:** vendor, ED-112/ED-112A compliance, parameter list and count, rates, loop length, download interface. Leads: HAL Korwa SSFDR/CVFDR TA documents (TA-1811/1849/1895/1923); IAF court-of-inquiry press statements.
3. **Mk1A HUMS:** scope (engine/structure/utility), sensor list, sample rates, the prior imported US DAU model, data format, ground station. Lead: PCC/HAL press releases; an ADA AR after 2021-22 (not online; the AR 2016-17 PDF returned a server error).
4. **ECMS:** parameter list, rates, triggers, LUI gates, vibration limits, and whether ECMS is FADEC-resident or a separate LRU.
5. **CWS legend list** and caution logic; SSDU "critical aircraft system parameters" list.
6. **Squadron download and debrief tooling;** whether e-MMS ingests on-board data; how ECMS/HUMS data reaches HAL Engine Division / GE and the BRDs.
7. **FTI formats** (PCM/IRIG use), sampling rates and telemetry list.
8. **Unsearched within budget:** Shodhganga/IISc/IIT theses on LCA avionics/USMS; Aero India seminar proceedings beyond JOAST; DRDO newsletters (drdo.gov.in down).

**Conflicts flagged**
- LRU count: ">500 LRUs" (FAS 1999, citing Flight International 1998) vs **344 LRUs** (CEMILAC 2015). Use 344.
- Software systems: 33 embedded (CEMILAC) vs 7 + 23 = 30 evaluated (ADA IV&V).
- Bus count "three 1553B" appears only in 1998/1999 secondary text, not in ADA/HAL sources.
- OAC/MC designer:
  - ADA (tejas.gov.in) vs "ADE design, HAL production" (IDRW commentary).
  - Mk1A MC by HAL MCSRDC (snippet-level brochure) with hardware by Mistral (trade press).
  - DFCC "developed by BEL" (Wikipedia) vs ADE design with BEL production (Kala; HAL–BEL contract).
- Engine data on tejas.gov.in (1,035 kg; 9,163 kgf / 20,200 lb) vs GE data sheet (1,072 kg; 84 kN / 19,000 lb class). Use GE.
- IECMS event window: 5 s + 25 s (USN) vs 5 s + 35 s (CF).
- HUMS status wording: "PO being placed" (AR 2020-21) vs "HUMS development to meet Mk1A requirements is being initiated" (AR 2021-22) vs a production order for 124 DAUs (published Feb 2026). The sequencing is plausible (development contract → production) but unconfirmed.
- 124 HUMS DAUs vs 83 + 97 = 180 Mk1A aircraft ordered: reason unknown.

#### (f) Ranked sources (most valuable first)
1. **Raveendran & Prabhu (NFTC/ADA), "Tejas Flight Test: Lessons Learned So Far", RTO-MP-SCI-162 paper 14 (2005).** DFCC → 1553 → CDR/GUH/FTI; four EUs → two; DHEU brake-by-wire; cockpit evolution; failure experience; "record more parameters". [archived PDF](http://web.archive.org/web/20131227221522/http://ftp.rta.nato.int:80/public/PubFullText/RTO/MP/RTO-MP-SCI-162/MP-SCI-162-14.pdf)
2. **Kala (ADE), JOAST 67(2A) 2015:** DFCC/ADC architecture, sensors, frame time, BIT types. https://joast.org/index.php/joast/article/view/317
3. **Santhiseela et al. (ADE), JOAST 57(4) 2005 and 69(1A) 2017:** DFCC channel internals (1553B, CCDL, 23 subsystems/channel) and the ground AFDS diagnostic structure. https://joast.org/index.php/joast/article/view/782 ; https://joast.org/index.php/joast/article/view/261
4. **ADA Annual Reports 2015-16 to 2021-22:** budget lines (MPDRU, CDR, CWS, DVR, HEEM-EU, GCS, maintenance simulator), BHEEM/ECFM/SSDU, Mk1A MC/DMG/SMFD/DACS, HUMS timeline, Mk2 TSN/AMT. https://www.ada.gov.in/images/Annual_Report_2015-16.pdf (and 2017-18 … 2021-22)
5. **tejas.gov.in archived pages (OAC; Specifications–Systems):** OAC functions; utility and health management through the OAC. http://web.archive.org/web/2015/http://www.tejas.gov.in:80/technology/open_architecture_computer_for_avionics.html
6. **NASA CR-201670 (HARV ANSER data retrieval), App. A:** a real F/A-18 parameter catalogue with recording rates (1,713 parameters parsed). https://ntrs.nasa.gov/citations/19970014822
7. **NAWCADPAX/RTR-2001/1, Table E-3:** F/A-18C 1553 mux measurand list (ADC/FCC/SDC/INS words, validity words, MSW/LSW). https://archive.org/details/DTIC_ADA407860
8. **AGARD-CP-448 (1988):** F/A-18 IECMS (Hess; Muir; Henry), F110 EMS MFL/PFL and data transfer cartridge (papers 11, 21). https://archive.org/details/DTIC_ADA203800
9. **DDP/MoD product catalogue (HAL):** CWS, DFDR, DACS, I-DMG, SMFD, G3INS, anti-skid, LCA page. https://www.ddpmod.gov.in/en/resources/products/centralized-warning-system-cws
10. **Trivedi (ADE), JOAST 63(4) 2011:** 1553 BC schedule and ICD conventions; 12.5 Hz health message; post-flight data-retrieval phase; ICD churn. https://joast.org/index.php/joast/article/view/598
11. **Park Controls PCAMi-1000 page and the ADU order article (Feb 2026):** Mk1A HUMS DAU. https://www.parkcontrols.com/industries/air ; https://www.aviation-defence-universe.com/pcc-advances-indigenous-hums-capability-with-pcami-1000-production-order
12. **CEMILAC, JOAST 67(2A) 2015:** OAC as "heart"; 344 LRUs; 53 avionics LRUs; dual-redundant utility management. https://joast.org/index.php/joast/article/view/325
13. **Supporting Phalanx notes:** `empirical_dashlink_texture.md` (measured texture); `f404_in20_engine_model.md` (engine sensors and LUIs); `tejas_utility_systems.md` (utility signals); `maintenance_records_and_events.md` (BIT → work orders, S5000F); `data_pathway_and_formats.md` (1553/Ch10/time semantics).
