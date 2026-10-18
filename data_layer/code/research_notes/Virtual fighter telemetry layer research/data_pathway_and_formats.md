# Data pathway in a 4th/4.5-generation fighter, from sensor to maintenance/ground systems, and where the Phalanx simulator should emit data

Scope: the realistic data pathway (sensor → acquisition → computers and buses → onboard recording/health monitoring → download/telemetry → ground/maintenance systems), with formats, message structures, timestamps, metadata and sampling at each stage. It ends with a reasoned recommendation on where the Phalanx simulator should emit data so a downstream predictive-maintenance (PdM) system can plug in later without a redesign.

How to read the tags:
- **[DIRECT]**: the source is about the specific aircraft, system or standard named.
- **[TRANSFER: X]**: the evidence comes from analogue X. The tag says why it transfers and where it stops applying.
- **[ASSUMPTION]**: engineering judgement with no direct source.

Research conditions that affect coverage (please read):
- **The WebSearch budget ran out partway through.** The shared per-turn limit of 200 searches across all parallel agents was hit. After that I used only direct fetches of known URLs, and no search engines, proxies or archive workarounds. This mostly hurt the platform-specific items: F/A-18 MSDRS details, Tejas, Gripen and Su-30MKI recorders and bus details, and civil AHM/Skywise. Those are listed as gaps. To continue, the user can send a follow-up or raise the search limit.
- **apps.dtic.mil returned a maintenance page or HTTP 403 throughout.** gao.gov PDFs, globalsecurity.org, the eCFR and some vendor sites also returned 403 or 402 to direct fetches. Where a page's content is known only from a search-engine summary, the claim is tagged "(snippet-level)".
- **Downloaded primary documents** are in `/Users/abishaikc/Phalanx/research_sources/data_pathway/`. They include IRIG 106 Ch4/7/8/9/10/11, the 106-23 TOC, the RCC 123-16 handbook, the Alta 1553 tutorial, the 1553 review-and-rationale document, the DDC Ch10 white paper, the BEA FDR read-out study, NASA TM-84899, the GE DAS datasheet, the F-16 AIB report, GAO-20-316, and a public sample `.c10` file. Each PDF also has a text extraction.

---

## Q1. Sensor interfaces and acquisition: signal conditioning, RIUs/DAUs/data concentrators, FADEC/DEC, air data, INS/EGI, mission, utility/vehicle-management and flight-control computers; sampling, filtering and validity

### Takeaway
On a 4th/4.5-gen fighter, raw transducer signals are digitised in one of two places:
- **Inside the "owning" LRU.** The FADEC/DEC reads its engine sensors, the air data computer reads pitot-static pressures, the EGI reads its own IMU, and the quadruplex DFCC reads its own sensors.
- **In remote acquisition units (DAU/SAU/RIU).** These serve airframe and utility sensors, and serve recorders through analog, discrete, frequency, synchro, LVDT and strain inputs.

Engineering-unit (EU) values, with validity information, then leave the LRU on a digital bus. In most cases, therefore, the "first public, standard representation" of a parameter is a bus word, not a voltage. Public sources give the interface types and validity semantics well. They do not give fighter-specific acquisition rates; those must be configurable assumptions anchored to public FDR and bus-schedule examples.

### Cited Findings
- **Acquisition is done at the sensor or LRU, not centrally** [DIRECT, MIL-STD-1553 design intent]. The 1553 originator described the concept: "The digital conversion is done at the sensor, and a digital signal is sent to the computer via a dual redundant shielded twisted wire pair." This replaced A/D hardware in the central computer. — [Alta MIL-STD-1553 Tutorial & Reference Rev A, "A Brief History…"](https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf)
- **Which signals go on the bus** [DIRECT, MIL-STD-1553B rationale §10.3]:
  - Signals with bandwidth ≤400 Hz are "prime candidates" for the bus.
  - The 400 Hz–3 kHz range is "questionable" and depends on bus loading.
  - Video, audio and high-speed parallel digital signals "should be excluded".
  - Low-rate, high-urgency signals (e.g., a missile-launch alarm) "are usually better left hardwired".
  — [Review and Rationale of MIL-STD-1553A and B (MIL-HDBK-1553A Section II)](https://www.milstd1553.com/wp-content/uploads/2012/12/MIL-STD-1553B.pdf), §10.3.
  - *Consequence:* high-bandwidth vibration waveforms are not bus traffic. They are processed into features by a dedicated unit (engine monitoring/HUMS). Cross-link: engine-monitoring researcher.
- **Acquisition-unit input types on a fielded fighter recorder** [DIRECT, F-16 recorder replacement]. GE's Data Acquisition System is "a drop in replacement for the F-16 Crash Survivable Flight Data Recorder and the USAF Standard Flight Data Recorder". It consists of a Data Acquisition Unit (DAU) and an Enhanced Crash Survivable Memory Unit (ECSMU).
  - Inputs: AC/DC differential, frequency inputs, configurable I/O discretes, ratiometric, synchros, LVDT, strain gauges.
  - Digital I/O: MIL-STD-1553B, Ethernet 10/100, ARINC 429, RS-422/485, ARINC 717.
  - Functions: mishap recording, "Engine and structures monitoring", IVHM, PHM and FOQA.
  — [GE Aviation DAS datasheet](https://www.geaerospace.com/sites/default/files/2022-02/DAS-Datasheet.pdf)
- **Civil DAU concept** [TRANSFER: civil FDR/DFDAU, BEA 2005 study; same DAU-to-recorder architecture, but civil recorders use ARINC 573/717 frames, which are not fighter-specific].
  - DAUs "centralize and format data coming from sensors, onboard computers and other instruments and then transfer it to FDRs via a dedicated digital link (serial link ARINC 573 or 717)".
  - Four input types: discrete, analog (potentiometer), synchro transmitters, digital bus (ARINC 429).
  - DAUs "deal with the time sampling of parameters and of their digital encoding from the actual physical value to the recorded value".
  — [BEA, *Flight Data Recorder Read-Out: Technical and Regulatory Aspects*, May 2005, §1.2.1](https://bea.aero/uploads/tx_scalaetudessecurite/use.of.fdr_01.pdf)
- **Instrumentation split on the AFTI/F-16 test aircraft** [DIRECT, F-16 derivative, 1982].
  - PCM system 1 sampled "about 200 hardwired parameters—standard measurements such as positions, temperatures, strain gages, rates, accelerations, and air data that are signal conditioned and put directly on the PCM system".
  - PCM system 2 sampled "about 200 words selected from the A-MUX bus" through an interface box. These were "mode controls and selections, avionic and fault systems status, and parameters in engineering units."
  - In other words, the bus already carries EU values and fault and status data.
  — [NASA TM-84899, *Real-Time Data Display for AFTI/F-16 Flight Testing*, Nov 1982, "Instrumentation Systems"](https://ntrs.nasa.gov/api/citations/19830004825/downloads/19830004825.pdf)
- **FADEC/DEC interfaces**:
  - F404-GE-IN20 (Tejas Mk1) has "a FADEC system for reliable power and performance" [DIRECT]. — [Wikipedia: General Electric F404](https://en.wikipedia.org/wiki/General_Electric_F404)
  - RM12 (Gripen C/D): the F404's analogue control unit was replaced by a Volvo/GE Digital Engine Control that "communicates with the cockpit through the digital data buses" and has a hydromechanical back-up [DIRECT]. — [Wikipedia: Volvo RM12](https://en.wikipedia.org/wiki/Volvo_RM12)
  - The F404 family has an "in-flight engine condition monitoring system (IECMS)" that "monitors for critical malfunctions and keeps track of parts lifetimes" [DIRECT, family-level]. — [Wikipedia: General Electric F404](https://en.wikipedia.org/wiki/General_Electric_F404)
  - FADEC channel architecture and cross-channel data link details: not found. See Gaps; cross-link to the engine researcher.
- **Flight-control computers (redundancy and validity by voting)**:
  - Tejas: NAL-developed "full-authority quadruplex digital fly-by-wire" with an open-architecture flight control computer by BEL; the latest ADE DFCC uses a "quadraplex PowerPC-based processor" and meets DO-178C level A [DIRECT]. — [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas)
  - Su-30MKI: FBW with "quadruple redundancy"; when "the difference is significant, the faulty channel is disconnected" [DIRECT]. — [Wikipedia: Sukhoi Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI)
  - Gripen: "triplex, digital fly-by-wire" [DIRECT]. — [Wikipedia: Saab JAS 39 Gripen](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen)
  - F/A-18: quadruplex digital FBW, "the first to be installed in a production fighter" [DIRECT]. — [Wikipedia: F/A-18 Hornet](https://en.wikipedia.org/wiki/McDonnell_Douglas_F/A-18_Hornet)
  - In the AFTI/F-16, the A-MUX bus was extended to interface the three DFCS processors [DIRECT]. — [NASA TM-84899](https://ntrs.nasa.gov/api/citations/19830004825/downloads/19830004825.pdf)
- **Air data**:
  - Tejas uses a "BEL air data computer" [DIRECT]. — [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas)
  - ARINC 429 label 203 is barometric altitude from an air data computer [TRANSFER: ARINC 429 civil label convention; applies only to LRUs that speak 429]. — [Wikipedia: ARINC 429](https://en.wikipedia.org/wiki/ARINC_429); [UEI ARINC 429 tutorial](https://www.ueidaq.com/arinc-429-tutorial-reference-guide)
- **INS/GPS**:
  - Su-30MKI: "SAGEM Sigma-95 integrated GPS and ring laser gyroscope inertial navigation" [DIRECT]. — [Wikipedia: Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI)
  - F-16 MLU: "Miniaturized Airborne GPS Receiver" [DIRECT]. — [F-16.net MLU article](https://www.f-16.net/f-16_versions_article2.html)
- **Validity semantics at the digital boundary** [DIRECT, standards]:
  - **ARINC 429 SSM, bits 31/30, for BNR data:** 00 = Failure Warning, 01 = No Computed Data, 10 = Functional Test, 11 = Normal Operation. Bit 29 carries the BNR sign. For BCD, the SSM encodes sign/direction. — [Wikipedia: ARINC 429](https://en.wikipedia.org/wiki/ARINC_429)
  - **ARINC 429 receiver behaviour:** avionics "commonly flag equipment as inoperable after two consecutive missing frames". — [UEI ARINC 429 tutorial](https://www.ueidaq.com/arinc-429-tutorial-reference-guide)
  - **MIL-STD-1553 status word:** Message Error (bit 9), Service Request (bit 11), Broadcast Received (bit 15), Busy (bit 16), Subsystem Flag (bit 17), Dynamic Bus Control Acceptance (bit 18), Terminal Flag (bit 19). — [UEI MIL-STD-1553 tutorial](https://www.ueidaq.com/mil-std-1553-tutorial-reference-guide)
  - **1553 BIT access through mode codes:** 3 = Initiate Self Test, 19 = Transmit BIT Word, 18 = Transmit Last Command, 16 = Transmit Vector Word. — [Alta tutorial, Mode Code table](https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf)
- **Public sampling-rate anchors (civil FDR minimum maximum sampling intervals)** [TRANSFER: 14 CFR 121 Appendix M. These are regulatory minimums for transport aircraft, not fighter acquisition rates; fighter LRUs and maintenance recorders sample much faster for control and health purposes].

  | Parameter | Max sampling interval | Rate |
  |---|---|---|
  | Normal acceleration | 0.125 s | 8 Hz |
  | Longitudinal and lateral acceleration | 0.25 s | 4 Hz |
  | Pitch control, FBW | 0.5 s (0.25 s for §121.344(f) aircraft) | 2–4 Hz |
  | Pressure altitude, airspeed, heading | 1 s | 1 Hz |
  | Engine thrust/power and "additional engine parameters" | 1 s per engine | 1 Hz |
  | Outside air temperature, angle of attack (2 s, or 0.5 s for §121.344(f)), hydraulic-pressure-low | 2 s | 0.5 Hz |
  | Time | 4 s | 0.25 Hz |

  Footnote 18: flight-control inputs on aircraft manufactured from 6 Dec 2010 must be sampled at 0.125 s, with no interleaving. — [14 CFR Part 121 Appendix M (Cornell LII)](https://www.law.cornell.edu/cfr/text/14/appendix-M_to_part_121)

### Inferences
- [ASSUMPTION, grounded in the 1553 design intent above] For most parameters the simulator does not need voltage-level emulation to be realistic at the aircraft-system level. The realism lives in:
  1. the owning LRU's computation cycle and filtering;
  2. quantisation and scaling into a 16-bit (1553) or 19-bit (429) field;
  3. validity and status handling;
  4. the bus schedule.
  
  Voltage/frequency-level modelling is only worth it for analogue channels that a DAU/SAU acquires directly (strain, some temperatures and pressures, discretes). It is also worth it for high-bandwidth channels whose features are computed onboard (vibration).
- [ASSUMPTION] For each parameter, the canonical representation should carry: truth value, measured EU value, source LRU and channel (FADEC A/B, DFCC lane), validity state (normal / NCD / failure warning / functional test, or 1553 subsystem flag), and an acquisition timestamp. These map one-to-one onto the 429 SSM and the 1553 status/ICD conventions above.

### Gaps
- No public fighter-specific acquisition rates were found for FADEC control loops, the FADEC cross-channel data link, ADC output rates, EGI 1553 output rates or DFCC frame rates (F-16, F/A-18, Tejas, Gripen, Su-30MKI). DTIC was inaccessible and the search budget was exhausted. Cross-link: engine and engine-monitoring researcher; platform-selection researcher.
- No public source found for Tejas's utilities management/data-concentrator architecture (e.g., a "utility systems management" computer) or for remote interface units on any candidate type.

---

## Q2. Aircraft data buses: MIL-STD-1553B in detail, ARINC 429, ARINC 664/AFDX, Fibre Channel, RS-422/485, CAN/ARINC 825, MIL-STD-1760; which buses each candidate uses

### Takeaway
MIL-STD-1553B is the backbone of all five candidates where public sources speak:
- F-16, F/A-18 and Gripen are named 1553 users; Gripen has five 1553B buses.
- Tejas lists a "MIL-STD-1553B bus".
- Su-30MKI bus details are not public in fetched sources. GOST 26765.52 is the Russian 1553 equivalent.

The 1553 word and message structure, timing and error semantics are fully public. The application layer (which RT/subaddress/word carries which parameter, at what rate and scaling) is defined in proprietary ICDs and must be synthesised. ARINC 429 (point-to-point, 32-bit labelled words) is the usual interface for COTS LRUs. Newer architectures add Ethernet/AFDX (Gripen E-class), Fibre Channel and IEEE 1394b (F-35). IRIG 106 Ch10/11 can record all of these.

### Cited Findings
**MIL-STD-1553B: physical and word level** [DIRECT]
- **Rate and encoding:** 1 Mb/s, Manchester II bi-phase.
- **Words:** each word is 20 bit-times: 3-bit sync, 16 data bits, odd parity. That is 20 µs per word.
- **Response timing:** an RT must respond in 4–12 µs; the BC times out at 14 µs; the minimum inter-message gap is 4 µs. Timing is measured mid-parity to mid-sync, so dead-bus time is 2 µs less.
- **Message structures:** 10 message structures exist (BC-RT, RT-BC, RT-RT, mode codes with or without data, broadcast variants). There is no CRC; parity only.

— [Alta 1553 tutorial](https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf); [Wikipedia: MIL-STD-1553](https://en.wikipedia.org/wiki/MIL-STD-1553)

**Command word** [DIRECT]
- 5-bit RT address: 0–31, with 31 reserved for broadcast in 1553B, so 31 unique RTs.
- T/R bit: 1 = transmit.
- 5-bit subaddress: 0 or 31 = mode code; otherwise SA 1–30.
- 5-bit word count: 0 means 32 words. For mode codes, this field is the mode-code number.
- Analyser notation: "01R 04 10" = RT1, Receive, SA4, 16 words = 0x0890.

— [Alta tutorial](https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf)

**Roles** [DIRECT]
- **BC:** a single active Bus Controller; a Backup BC may take over.
- **RTs:** respond to commands.
- **Bus Monitors:** "cannot transmit"; they record bus traffic, "often a subset chosen by the application, for later analysis".

— [Wikipedia: MIL-STD-1553](https://en.wikipedia.org/wiki/MIL-STD-1553); [UEI 1553 tutorial](https://www.ueidaq.com/mil-std-1553-tutorial-reference-guide)

**Data-word conventions** [DIRECT, MIL-STD-1553B §4.3.2 and rationale]
- The MSB is transmitted first.
- The number of bits for a quantity is chosen for the required resolution.
- Multiple-precision (>16-bit) quantities are sent most-significant word first.
- "Bit packing of multiple quantities in a single data word is permitted."
- Unused bits are transmitted as zero.

— [1553 Review & Rationale](https://www.milstd1553.com/wp-content/uploads/2012/12/MIL-STD-1553B.pdf), §4.3.2.

**Standardised data words** [DIRECT, standard exists; content paywalled]
- SAE AS15532 / AS15532A ("Data Word and Message Formats") is the tri-service composite of standard 1553 data-word and message formats. It includes a word-format index and a method for defining new words. The original was issued Jan 1999 and superseded by AS15532A. Its contents were not accessible. — [SAE AS15532A listing](https://saemobilus.sae.org/standards/as15532a-data-word-message-formats) (snippet-level)

**F-16 specifics** [DIRECT]
- The standard was first used on the F-16 (1973 USAF standard; 1553A 1975; 1553B 1978; 1553C Feb 2018 is functionally equivalent to B). — [Wikipedia: MIL-STD-1553](https://en.wikipedia.org/wiki/MIL-STD-1553)
- "In some existing systems, such as the F-16, the bus controller uses 11111 to indicate a mode code command" (in addition to 00000). — [1553 Review & Rationale §20.8.1](https://www.milstd1553.com/wp-content/uploads/2012/12/MIL-STD-1553B.pdf)
- F-16 A-MUX bus: "The existing F-16 avionics subsystem elements are interfaced on a common MIL-STD-1553 F-16 avionics multiplex A-MUX data bus… The fire control computer (FCC) continues in its role as the primary A-MUX bus controller. The stores management set (SMS) provides backup A-MUX bus control capability." A second display multiplex bus (D-MUX) is also 1553. Remote terminals on the schematic: FCC, fire control navigation panel, INU, HUD, SMS, fire control radar, CADC, flight control panel, DFCS, programmable display generators/MFDs. — [NASA TM-84899, Fig. 3](https://ntrs.nasa.gov/api/citations/19830004825/downloads/19830004825.pdf)
- F-16 MLU Modular Mission Computer replaces the XFCC, HUD symbol generator and XCIU. It includes "multiplex bus modules". — [F-16.net MLU](https://www.f-16.net/f-16_versions_article2.html)
- A Scribd-hosted MMC overview states "six dual redundant MIL-STD-1553B channels". This is snippet-level and the provenance is uncertain. — [Scribd F-16 MMC](https://www.scribd.com/document/746980919/F-16-MMC)

**Other candidates** [DIRECT]
- **Gripen:** "All of the Gripen's avionics are fully integrated using five MIL-STD-1553B digital data buses." — [Wikipedia: Gripen](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen)
- **F/A-18:** "the first Navy aircraft to incorporate a digital multiplexing avionics bus". — [Wikipedia: F/A-18](https://en.wikipedia.org/wiki/McDonnell_Douglas_F/A-18_Hornet). The F/A-18 is listed among 1553 users. — [Wikipedia: MIL-STD-1553](https://en.wikipedia.org/wiki/MIL-STD-1553)
- **Tejas:** the avionics list includes a "MIL-STD-1553B bus" and a "mission computer network". — [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas)
- **Su-30MKI:** "integrates Indian systems and avionics as well as French and Israeli sub-systems". No bus details. — [Wikipedia: Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI). Russian equivalents of 1553 are GOST 26765.52-87 and GOST R 52070-2003; NATO's version is STANAG 3838. — [Wikipedia: MIL-STD-1553](https://en.wikipedia.org/wiki/MIL-STD-1553)

**BC scheduling: minor and major frames** [DIRECT, tutorials/patent; not fighter ICDs]
- "A minor frame is a group of one or more messages that is repeated at a given frequency – typically in the 1-1000 Hz… Most systems rarely go above 100 Hz (10 millisecond) in base frequency." Good practice uses ≤50% of frame time, leaving room for aperiodic messages and retries. — [Alta tutorial](https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf)
- Example schedule: Message A at 20 Hz sets the minor frame (50 ms); B at 10 Hz; C at 5 Hz; major frame 200 ms. High-priority aperiodic messages go in the next gap; low-priority ones at the end of a minor frame. — [Bloomy MIL-STD-1553B Technical Brief, Apr 2021](https://www.bloomy.com/node/907)
- An illustrative schedule with minor frames at 100 Hz, 50 Hz and 25 Hz forming a major frame. — [US5367641A](https://patents.google.com/patent/US5367641)
- **Observed rates in a real (non-fighter) public recording** [TRANSFER: KC-135 operational check recording, the only public `.c10` sample found; transport aircraft, 0.47 s window, so low-rate messages are under-observed]. My own header parse of `sample.c10` from the pyChapter10 test suite (TMATS `G\PN:D200-KC135OPSCK`, Heim D200F recorder) shows:
  - 4 recorded 1553 buses, 6 ARINC 429 channels, 8 video channels and 1 message channel.
  - Periodic 1553 messages recurring mostly at ~10 Hz (24 distinct messages) and ~20 Hz (6), with a few at ~41 Hz and ~163–248 Hz.
  - ARINC 429 labels mostly at ~10, ~20 and ~100 Hz, with both high- and low-speed buses present.
  - Ch10 1553 packets spanning 75–90 ms (consistent with the ≤100 ms packet rule).
  
  — [pyChapter10 tests/sample.c10](https://github.com/atac/pyChapter10/tree/master/tests), analysed with a local script (saved copy in `research_sources/data_pathway/pychapter10_samples/`).

**ARINC 429** [DIRECT]
- **Word:** 32 bits. Label in bits 1–8 (octal, transmitted bit-reversed); SDI in bits 9–10; data in bits 11–29 (BNR, BCD or discrete, possibly mixed); SSM in bits 30–31; odd parity in bit 32.
- **Physical:** one transmitter to ≤20 receivers; 78 Ω shielded twisted pair; bipolar RZ ±10 V; 12.5 or 100 kb/s.

— [Wikipedia: ARINC 429](https://en.wikipedia.org/wiki/ARINC_429)

- Speed tolerances: high speed "100kHz +/- 1%"; low speed 12.5 kHz (12–14.5 kHz). "Typical update rates are set to either 25, 40, or 65 ms." — [UEI ARINC 429](https://www.ueidaq.com/arinc-429-tutorial-reference-guide)
- IRIG 106 records the bus speed flag as 12.5 kHz / 100 kHz. — [IRIG 106-15 Ch10 §10.6.8](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2)

**AFDX / ARINC 664 Part 7** [DIRECT, standard; no fighter named]
- A profiled IEEE 802.3 network with virtual links: unidirectional, 16-bit VL ID, each with a Bandwidth Allocation Gap (BAG).
- Up to 4 sub-VLs per VL; redundant network pair; switches police and forward ≥4096 VLs.
- Users listed: A380, A400M, A350, B787, among others. No fighters are listed.

— [Wikipedia: AFDX](https://en.wikipedia.org/wiki/Avionics_Full-Duplex_Switched_Ethernet)

- IRIG 106 Ch11 can capture "Any User Datagram Protocol (UDP) packets from Ethernet and/or ARINC-664 Part 7" in Ethernet Data Format 1 (0x69). — [IRIG 106-22 Ch11 §11.2.15.2](https://www.trmc.osd.mil/wiki/download/attachments/240256873/chapter11.pdf?api=v2)

**Fibre Channel / IEEE 1394b (F-35)** [DIRECT]
- The F-35 avionics use "IEEE 1394b" and "Fibre Channel" buses, with integrated core processors running INTEGRITY DO-178B. — [Wikipedia: F-35](https://en.wikipedia.org/wiki/Lockheed_Martin_F-35_Lightning_II)
- IRIG 106 defines Fibre Channel (0x79/0x7A) and IEEE 1394 (0x58/0x59) packet types. — [IRIG 106-22 Ch11 Table 11-4](https://www.trmc.osd.mil/wiki/download/attachments/240256873/chapter11.pdf?api=v2)

**MIL-STD-1760 (stores)** [DIRECT]
- Defines the aircraft/store electrical interface: power (28 VDC, 115/200 VAC 400 Hz, 270 VDC), a 1553 data bus with address discretes (31 addresses), high- and low-bandwidth analogue, interlock and Release Consent discretes, and fibre optics.
- Rev E adds High-Speed 1760 (SAE AS5653): 1.0625 Gb/s using FC-AE-1553 and FC-AV.

— [Wikipedia: MIL-STD-1760](https://en.wikipedia.org/wiki/MIL-STD-1760)

**CAN, RS-422/485 and parallel** [DIRECT, recording support only]
- IRIG 106 defines CAN Bus (0x78), UART (0x50) and Parallel (0x60) packet types. — [IRIG 106-15 Ch10 Table 10-10](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2)
- The GE DAS supports RS-422/485. — [GE DAS datasheet](https://www.geaerospace.com/sites/default/files/2022-02/DAS-Datasheet.pdf)
- No candidate-fighter use of ARINC 825/CAN was found.

### Inferences
- [ASSUMPTION] A synthetic "Phalanx ICD" is unavoidable. It should use public conventions:
  - SAE-AS15532-style 16-bit words: two's-complement BNR with a documented LSB weight, packed discretes, multi-word for >16 bits.
  - 1553 RT/SA assignments per LRU.
  - Rate groups that are binary submultiples of a base minor-frame rate. Make the base rate configurable (e.g., 50 Hz → 25/12.5/6.25 Hz, or 80 Hz → 40/20/10 Hz), because no public fighter schedule was found. Public examples range from 5–100 Hz, and the KC-135 sample is mostly 10–20 Hz.
  - BIT words (mode code 19) and status-word flags as the carriers of LRU health.
- [ASSUMPTION] Model ARINC 429 for COTS-type LRUs (ADC, radar altimeter, some nav) with SSM and label rates in the 10–100 Hz band. Leave AFDX/Ethernet as an optional adapter for an E-class or newer platform.
- [INFERENCE from the 1553 bandwidth rule plus the AFTI/F-16 evidence] The bus carries EU-scaled values and fault/status words at ≤100 Hz. Anything faster (vibration) is summarised before it reaches the bus.

### Gaps
- Fighter ICD message lists and rates are not public: F-16 A-MUX/D-MUX/MMC schedules, the Tejas MC schedule, the five Gripen buses, F/A-18 MC buses.
- No public source for the Su-30MKI bus standard (1553 vs GOST MKIO, or mixed).
- The SAE AS15532A contents and the ARINC 429 label table with per-label rates (ARINC 429 Attachment 1) are paywalled.

---

## Q3. Onboard recording and health systems: CSFDR/ED-112A, maintenance/signal data recorders (F/A-18 MSDRS), engine monitoring units, HUMS/IVHM, DTC/DTU/DTE/PMD, mass memory; continuous vs event-triggered; capacity and download

### Takeaway
Fighters typically have several recording paths that are related but separate:
1. **A mishap recorder.** On the F-16: CSFDR = Signal Acquisition Unit (SAU) + Crash Survivable Memory Unit (CSMU), being replaced by the GE DAU + ECSMU and later JEDAI.
2. **Maintenance, engine and usage monitoring.** Examples: the F404 IECMS, F-16 engine operating-time tracking, HUMS on the Su-30MKI and Gripen, the "integrated health-monitoring system" on Tejas.
3. **Mission/data transfer media.** Examples: DTC, Gripen's data transfer unit, the F-35 Portable Memory Device.

The acquisition unit acts mainly as a 1553 bus monitor plus some analogue/discrete inputs. Maintenance-relevant data reaches the ground by physically carrying the memory device or by connecting a PC after the flight. Public sources do not give fighter-specific parameter lists, capacities or trigger windows.

### Cited Findings
**F-16 CSFDR**
- The F-16 has a Crash Survivable Flight Data Recorder. In the 2019 mishap, "the Crash Survivable Flight Data Recorder (CSFDR) indicates the illumination of the engine overheat light near simultaneously with the first indication of an engine malfunction". So CSFDR records cockpit caution discretes and engine indications [DIRECT].
- The report's acronym list includes:
  - SAU (Signal Acquisition Unit) and CSMU (Crash Survivable Memory Unit);
  - EDU (Engine Diagnostic Unit);
  - CEMS (Comprehensive Engine Management System);
  - DTC (Data Transfer Cartridge);
  - SDR/SDRI (Seat Data Recorder / Seat Data Recorder Interface);
  - IMDS.
  
  Tab L is "Factual Parametric, Audio, and Video Data from On-Board Recorders".
- Engine due-dates use "Engine Operation Time (EOT), which is tracked by an onboard computer". Engine inspections are at 100, 200 and 400 h.

— [USAF AIB Report, F-16C T/N 90-0755, 29 Oct 2019](https://www.f-16.net/downloads/F-16-AIB-Reports/90-0755.pdf)

**F-16 recorder replacement**
- A 2010 USAF sources-sought (FA8232-10-R-CSFDR) describes the existing system as an SAU and CSMU. It names the replacement DAS as "model 2870A2 Data Acquisition Unit (DAU) and a 3254A4 Enhanced Crash Survivable Memory Unit" [DIRECT, snippet-level; page 403 on fetch]. — [GovTribe FA8232-10-R-CSFDR](https://govtribe.com/opportunity/federal-contract-opportunity/f-16-crash-survivable-flight-data-recorder-fa823210rcsfdr)
- The GE DAS ECSMU "complies with the ED-55, ED-56a, ED-112 recorder crash survivability requirements".
- Ground support:
  - "Download is accomplished with a PC running a web-browser and needs no special software".
  - "Recorder configuration is performed by the OEM using a PC based tool to select the desired parameters, storage, exceedence checks etc."
  - "Replay, analysis and animation software" is provided.
  
  [DIRECT, F-16 replacement unit] — [GE DAS datasheet](https://www.geaerospace.com/sites/default/files/2022-02/DAS-Datasheet.pdf)
- A recent notice says the USAF intends a sole-source award to GE Aerospace for the Joint Electronic Data Acquisition Interface (JEDAI) LRU. It describes JEDAI as "the required fleet-wide replacement for the CSFDR system for the F-16C/D Block 30/32/40/42/50/52 fleet", citing "aging, high failure rates, and lack of repair options" [DIRECT, snippet-level; aggregator; date not confirmed]. — [Tenderspedia flight-recorder tenders](https://www.tenderspedia.com/keyword/flight-recorder-tenders/)

**DoD recorder policy**
- MIL-HDBK-2124, *DoD Handbook: Flight Data Recorder Standards* (10 Oct 2000), says:
  - "a Type I or Type II crash survivable memory shall be installed".
  - Type I is a deployable memory in a Crash Position Locator package, "ejected from the host aircraft before or upon crash impact". Type II is crash-hardened and fireproofed.
  - The primary purpose is mishap analysis. "Other uses of the FDR, such as aircraft maintenance, shall be as directed by the acquiring activity" (§1.1).
  
  [DIRECT] — [MIL-HDBK-2124 summary](https://segoldmine.ppi-int.com/node/67861)
- The US Navy has used deployable CVDR technology since 1993 [DIRECT]. — [Wikipedia: Flight recorder](https://en.wikipedia.org/wiki/Flight_recorder)

**ED-112** [TRANSFER: civil/EUROCAE requirement adopted by the F-16 replacement ECSMU]
- ED-112 superseded ED-55/ED-56A in March 2003.
- Crash survivability includes 3,400 g for 6.5 ms.
- FDRs typically hold about 17–25 h in a loop (citation-needed in the source).
- US rules require ≥88 parameters (up from 29).

— [Wikipedia: Flight recorder](https://en.wikipedia.org/wiki/Flight_recorder)

**Gripen** [DIRECT]
- "Mission data is recorded digitally throughout a flight. A data transfer unit can replay it in the cockpit, extract it for post-mission analysis, or load mission data into the aircraft."
- The "Health and Usage Monitoring System (HUMS)" monitors subsystem performance and gives technicians servicing information. HUMS and other data can be submitted to Saab's improvement programme.

— [Wikipedia: Gripen](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen)

**Su-30MKI** [DIRECT]
- The onboard HUMS "monitors almost every aircraft system and sub-system, and can also act as an engineering data recorder".
- 69 engine-related failures between late 2012 and early 2015. This is useful context for the engine/faults researchers.

— [Wikipedia: Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI)

**Tejas** [DIRECT]
- Tejas "has an integrated health-monitoring system". DIAT is developing HUMS for the Mk2. — [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas)

**F/A-18** [DIRECT]
- The RAAF Hornet carried an "Australian fatigue data analysis system" and "an improved video and voice recorder" as changes from the USN version.
- Design life is 6,000 flight hours. Block III Super Hornet is 10,000 h, and tanker missions "consume aircraft fatigue life expectancy faster".
- This is relevant to usage/structural recording.

— [Wikipedia: F/A-18](https://en.wikipedia.org/wiki/McDonnell_Douglas_F/A-18_Hornet); [Wikipedia: F/A-18E/F](https://en.wikipedia.org/wiki/Boeing_F/A-18E/F_Super_Hornet)

**F-35 onboard-to-offboard media** [DIRECT]
- "The Portable Memory Device (PMD)… informally referred to as the 'brick'… F-35 personnel use the PMD to store mission and maintenance data generated during flight which may then be downloaded into the ALIS SOU."
- The PMD Reader removes "maintenance data, including health-related codes".

— [GAO-20-316, March 2020, pp. 8–9](https://www.gao.gov/products/gao-20-316)

**Event capture semantics in a public standard** [DIRECT, IRIG 106 Ch9/Ch10; generic recorder]
- TMATS defines Recording Events with:
  - Event Type: External / Measurement Discrete / **Measurement Limit** / Recorder / Other;
  - Priority 1–5; Capture Mode 1–6; initial capture; limit count;
  - measurement source and name for discrete and limit events.
  
  — [IRIG 106-07 Ch9 Table 9-3, R-x\EV](https://www.trmc.osd.mil/wiki/download/attachments/113019518/chapter9.pdf?api=v2)
- Ch10 Recording Event packets (0x02) carry event number (4,096 event types), event count and occurrence time. — [IRIG 106-15 Ch10 §10.6.7.3](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2)

### Inferences
- [INFERENCE] The maintenance-relevant recorded data on these fighters is a mix of four kinds. Each needs a different simulator output type:
  1. **Continuous parametric data** (bus-monitored EU values plus some analogue).
  2. **Discrete/caution and BIT/fault-code events.**
  3. **Usage counters** (EOT, cycles, fatigue counts).
  4. **Exceedance-triggered snapshots.**
- [ASSUMPTION] Exceedance snapshot windows on military engine monitors (pre- and post-trigger seconds) are not documented in fetched sources. Model the window lengths as configurable, and cross-check with the engine-monitoring researcher. A civil ACMS analogue was not verified (gap).

### Gaps
- F/A-18 MSDRS (Maintenance Signal Data Recording Set), memory unit and signal data recorder: components, parameters, capacity, and Navy SAFE/structural processing. FIRAMS/DFIRS on F/A-18E/F. All blocked by search-budget exhaustion and DTIC downtime.
- CSFDR/ECSMU parameter list, record duration and memory capacity on the F-16. Tejas recorder (SSFDR/CSMU) and its download process. Gripen recorder formats. Su-30MKI recorders (Russian "Tester"-family or Indian units).
- The EUROCAE ED-112A parameter list and its fighter applicability (paywalled).

---

## Q4. Flight test instrumentation and telemetry as a public reference format: IRIG 106 Ch4 PCM, Ch8 bus capture, Ch7 packet downlink, Ch9 TMATS, Ch10/11 recorder format, iNET/TmNS, time distribution, open-source tooling

### Takeaway
IRIG 106 is the only fully public, byte-level, end-to-end specification covering:
- multi-bus avionics capture (1553, ARINC 429, analogue, discrete, CAN, UART, Ethernet/AFDX, Fibre Channel, video);
- self-describing metadata (TMATS setup record as the first packet);
- a rigorous time base (10 MHz 48-bit RTC mapped to IRIG/GPS time via time packets);
- streaming over UDP/TCP and over RF (Ch7).

It is used for flight test and also for mission recorders and HUMS. Mature BSD-licensed parsers exist (pyChapter10, irig106lib, c10-tools), and a public sample file allows conformance testing.

### Cited Findings
**Edition structure** [DIRECT]
- From IRIG 106-17 onward, the packet formats moved from Ch10 into Ch11, "Recorder Data Packet Format Standard". Ch10 became "Digital On-board Recorder Standard".
- IRIG 106-23 (July 2023) lists:
  - Ch4 PCM, Ch6 recorder command/control, Ch7 Packet Telemetry Downlink, Ch8 Digital Data Bus Acquisition Formatting, Ch9 TMATS (changed in 106-23), Ch10, Ch11.
  - Ch21–28 for the Telemetry Network Standard (TmNS/iNET), including Ch23 Metadata Configuration (MDL), which was significantly updated in 106-23.
  - A new Ch24 Appendix A on using Ch11 data types inside TmNS messages.
- The Data Type Version byte is 0x0A for RCC 106-22.

— [IRIG 106-23 Cover/TOC/Changes](https://www.trmc.osd.mil/wiki/download/attachments/168165620/106-23_Cover_TOC_Changes_Preface.pdf?api=v2); [IRIG 106-22 Ch11 §11.2.1](https://www.trmc.osd.mil/wiki/download/attachments/240256873/chapter11.pdf?api=v2)

**Ch10/11 packet header** [DIRECT; numbers from IRIG 106-15 Ch10 §10.6.1]
- **Header:** 24 bytes, little-endian. Fields in order:
  - Sync **0xEB25** (2 B);
  - Channel ID (2 B; 0x0000 reserved for the TMATS setup record);
  - Packet Length (4 B, a multiple of 4);
  - Data Length (4 B);
  - Data Type Version (1 B);
  - Sequence Number (1 B per channel, rolls over at 0xFF);
  - Packet Flags (1 B);
  - Data Type (1 B);
  - **48-bit Relative Time Counter at 10 MHz** (6 B; "free-running… common to all data channels");
  - Header Checksum (2 B; 16-bit sum).
- **Packet Flags:**
  - bit 7: secondary header present;
  - bit 6: intra-packet time source (RTC vs secondary-header time);
  - bit 5: RTC sync error;
  - bit 4: data overflow;
  - bits 3–2: secondary time format (Ch4 binary-weighted 48-bit / IEEE-1588 / 64-bit ERTC at 1 GHz);
  - bits 1–0: data checksum (none, 8, 16 or 32 bit).
- **Optional 12-byte secondary header:** absolute time plus checksum.
- **Packet rules:**
  - Maximum packet 524,288 B; the setup record may be 134,217,728 B.
  - "packet generation times shall be equal to or less than 100 milliseconds", so a packet holds ≤100 ms of data.
  - Stream commit ≤1000 ms.
  - No empty or filler-only packets.
  - The first packet is the Computer-Generated Format 1 setup record (TMATS); the first dynamic packet is a Time packet; time packets are sent at ≥1 Hz.

**Data types** [DIRECT, 106-15 Table 10-10 / 106-22 Table 11-4]

| Code | Type |
|---|---|
| 0x00 | User-Defined |
| 0x01 | Setup Record (TMATS) |
| 0x02 | Recording Events |
| 0x03 | Recording Index |
| 0x04 | Computer-Generated Records (106-17+) |
| 0x09 | PCM Ch4/7/8 |
| 0x0A | DQE PCM (106-22) |
| 0x11 | Time F1 |
| 0x12 | Network Time (106-17+) |
| 0x19 | MIL-STD-1553B |
| 0x1A | 16PP194 |
| 0x21 | Analog F1 |
| 0x29 | Discrete F1 |
| 0x30 | Generic Message |
| 0x38 | ARINC-429 |
| 0x40–0x44 | Video |
| 0x48–0x4A | Image |
| 0x50 | UART |
| 0x58/0x59 | IEEE 1394 |
| 0x60 | Parallel |
| 0x68 | Ethernet |
| 0x69 | Ethernet UDP / ARINC-664 |
| 0x70–0x72 | TSPI/CTS (GPS NMEA-RTCM, EAG ACMI, ACTTS) |
| 0x78 | CAN |
| 0x79/0x7A | Fibre Channel |

**1553 packet (0x19)** [DIRECT, §10.6.4.2]
- **CSDW:** Time-Tag Bits (00 = last bit of last word, 01 = first bit of first word, 10 = last bit of the command word) and a 24-bit message count.
- **Per message:** an 8-byte intra-packet time stamp (RTC, or absolute time if flag bit 6 is set) and a 6-byte intra-packet data header made of three words:
  - **Block Status Word:** bus A/B, Message Error, RT-RT, Format Error, Response Timeout (14 µs), Word Count Error, Sync Type Error, Invalid Word Error;
  - **Gap Times Word:** GAP1/GAP2 response times in 0.1 µs;
  - **Length Word:** bytes.
- Then the raw command, status and data words in bus order.

**ARINC-429 packet (0x38)** [DIRECT, §10.6.8]
- CSDW holds a 16-bit word count.
- Each 32-bit word is preceded by a 32-bit ID word: bus number (8 bits, up to 256 buses), Format Error, Parity Error, Bus Speed (12.5/100 kHz), and a 20-bit **gap time in 0.1 µs since the previous word on any bus**.
- Packet header time = time of the first word. A new packet starts if a gap exceeds 100 ms.

**Analog packet (0x21)** [DIRECT, §10.6.5]
- CSDW per subchannel: SAME flag, FACTOR (sampling-rate factor 1/2^n, n = 0–15), TOTCHAN, SUBCHAN, LENGTH (bits per sample), MODE.
- "The packet header time in an analog data packet shall correspond to the first data sample in the packet. There are no IPHs."

**Discrete packet (0x29)** [DIRECT, §10.6.6]
- Records 1–32 discrete states per event. Mode bit: record on state change, or on a time interval.

**Time packet (0x11)** [DIRECT, §10.6.3]
- CSDW gives date format (day-of-year, or month/year with leap-year bit), FMT (IRIG-B/A/G, RTC, UTC from GPS, native GPS, None) and SRC (internal / external / internal-from-RMM / none).
- The body is BCD time down to 10 ms.
- If external lock is lost, the source reverts to Internal.

**Computer-generated and event packets** [DIRECT, §10.6.7]
- Format 0 (user-defined) "cannot" contain data types already defined, or data "generated from an external input".
- Format 2 recording events: up to 4,096 event types, with counts.

**Streaming** [DIRECT, §10.3.9]
- Optional Ethernet streaming over UDP, with a UDP transfer header: version, message type full/segmented, a 24-bit UDP sequence number, and channel ID and offset for segments. IPv4 messages must be <32,726 bytes.
- Or a dedicated TCP port **10620** carrying "only the live acquisition data". The recorder has priority and "may drop some complete as well as partial packets on the TCP port".

— [IRIG 106-15 Chapter 10](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2)

**Time interpretation** [DIRECT]
- "There is no constraint on the absolute value of the RTC… it is unwise to assume the RTC value will be related to absolute clock time." Time F1 packets carry both absolute time and the RTC at that instant, so absolute time of a later packet = time-packet time + ΔRTC × 100 ns. Worked example: an RTC difference of 150,000 = 15 ms.
- "When multiple time channels are available, it is incumbent on the programmer… to select the best source of time."
- A time packet must be the first dynamic packet so RTC can be associated with clock time.

— [RCC 123-16 IRIG 106 Ch10 Programmers' Handbook §5.6, §5.5](https://www.irig106.org/docs/rcc/123-16_IRIG_106_Chapter10_Programmers_Handbook.pdf)

- If relative time is used, it must be accurate to within ±100 µs of absolute time. Chapter 10 is applied to "health and usage monitoring; mission planning, debriefing, and training; and flight operations" as well as flight test. — [DDC, *IRIG 106 Chapter 10 Standardizes MIL-STD-1553 Data Recording*, 2007](https://www.ddc-web.com/resources/FileManager/dbi/Whitepapers/IRIG106.pdf)

**Ch4 PCM (classic telemetry frames)** [DIRECT]
- Words 4–32 bits (Class I).
- Minor frame ≤8,192 bits or ≤1,024 words (Class I); ≤16,384 bits (Class II).
- Minor-frame sync pattern 16–33 bits. A frame counter is recommended.
- ≤256 minor frames per major frame. Subcommutation at 1/D of the minor frame rate.
- Three 16-bit time words: high order, low order, microseconds.

— [IRIG 106-15 Ch4 §4.3, §4.7](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter4.pdf?api=v2)

**Ch8 total bus capture into PCM** [DIRECT]
- 24-bit formatted words: optional parity, 3–4-bit bus/group ID (up to 16 buses), 4-bit content label (time high/low/µs, fill, buffer overflow, bus-specific codes), 16-bit information field.
- Frame sync **0xFAF320** (24 bits). Frame length 128–512 words. Optional CRC-16. Fill word 0xAAAA.
- An optional "response time" word for 1553.

— [IRIG 106-15 Ch8](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter8.pdf?api=v2)

**Ch7 packet telemetry downlink** [DIRECT]
- Puts Ch10 packets, TmNS messages or Ethernet into a fixed-length PCM minor frame.
- 32-bit sync 0xFE6B2840, or 0x1ACFFC1D with Reed-Solomon.
- Frame of N×223 bytes (N = 1–8). Golay-protected headers. A low-latency packet option.

— [IRIG 106-15 Ch7](https://www.trmc.osd.mil/wiki/download/attachments/113019632/Chapter7.pdf?api=v2)

**Ch9 TMATS** [DIRECT]
- Syntax is `CODE:DATA;`. The hierarchy is inferred by matching names across groups (e.g., `R-1\ID` ↔ `G\DSI-1`).
- Groups: G (General), T (Transmission), R (Tape/Storage, i.e., recorder channels), M (Multiplex/Modulation), P (PCM format), D (PCM measurement), B (Bus data), S (Packet format), A (PAM), C (Data conversion), plus vendor-specific V.
- **Recorder channel attributes:** `R-x\TK1-n` (channel ID), `R-x\CDT-n` (type: PCMIN, ANAIN, DISIN, TIMEIN, 1553IN, 429IN…), `R-x\CDLN-n` (data link name).
- **Bus attributes (B group):** `B-x\DLN`, bus type, message definitions (`B-x\TRA` RT address, `B-x\STA` subaddress, `B-x\TRM` T/R, `B-x\DWC` word count, `B-x\LBL` ARINC label, `B-x\SDI`), and measurement word positions and bit masks (`B-x\MWN`, `B-x\MBM`).
- **Data conversion (C group):**
  - measurement name `C-d\DCN`;
  - transducer type/model/**serial** (`C-d\TRD1–3`) and security classification (`TRD4`);
  - engineering units `C-d\MN3`;
  - bit weights `C-d\BWTV-n`;
  - calibration points `C-d\MC1/2/3-n`;
  - operational, alert and warning limits `C-d\MOT1–6`;
  - **sample rate** `C-d\SR`;
  - conversion types: pair sets, polynomial coefficients `C-d\CO-n`, derived `C-d\DPA`, discrete, 1553 time word `C-d\BTM`;
  - date released `C-d\CRT`.
- **Events:** `R-x\EV\…`; index `R-x\IDX\E`.

— [IRIG 106-07 Ch9 (TMATS)](https://www.trmc.osd.mil/wiki/download/attachments/113019518/chapter9.pdf?api=v2); [irig106.org Ch10 handbook: recorder setup](https://irig106.org/wiki/ch10_handbook:recorder_setup_and_configuration)

**Real TMATS from a public file** [DIRECT about the sample]
- The KC-135 sample's TMATS (327 lines) shows: `G\106:06;`, `R-1\NSB:4;`, `R-1\CDT-1:TIMEIN;` with `R-1\TFMT-1:B` (IRIG-B) and `R-1\TSRC-1:E` (external), `R-1\CDT-2:1553IN;` with `B-2\BT-1:1553;`, `R-1\EV\E:T;`, `R-1\IDX\E:T;`, and vendor V-group lines.
- The file holds one TMATS packet, a time packet, user-defined packets, 4×1553 channels, 6×429 channels, 8 video channels and a message channel.

— [pyChapter10 tests/sample.c10](https://github.com/atac/pyChapter10/tree/master/tests) (local parse)

**Time distribution** [DIRECT]
- IRIG-B: 100 bit/s, one 1-s frame. BCD day-of-year, hours, minutes and seconds plus straight binary seconds. 1 kHz AM carrier (B12x) or DC level shift (B00x).
- B122 carries **no year**. Year and leap-second fields come only through extensions.
- Typical synchronisation is within 1 µs. IRIG-A is 1 kb/s (10 Hz frames); IRIG-G is 10 kb/s (100 Hz frames, with hundredths of seconds).

— [Wikipedia: IRIG timecode](https://en.wikipedia.org/wiki/IRIG_timecode)

- 1553 can distribute time with mode code 17, "Synchronize (with data word)", which allows broadcast. — [Alta tutorial](https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf)
- A real-world pitfall: an open-source Ch10 → Elasticsearch pipeline notes "idmp1553 output does not contain Year/Month/Day", and the ingest pipeline sets dates to 1 January. — [elastickent/mil-std-1553-es README](https://github.com/elastickent/mil-std-1553-es)

**Open-source tooling (as of 2026-10-13)** [DIRECT; repo metadata via GitHub/PyPI APIs]

| Tool | Language / licence | Status | Capabilities |
|---|---|---|---|
| **pyChapter10** | Python, BSD-3-Clause | PyPI 1.1.19, Oct 2023; last push 2023-11-25; 19 stars | "Chapter 10/11 file/stream parsing and generation". Supports 1553 F1/F2, 429 F0, Analog F1, Discrete F1, Time F1, PCM F1, Ethernet F0/F1, Message F0, Video F0–F2, UART, Computer-Generated F1–F3. Not supported: Time F2, Video F3/4, TSPI, CAN, Fibre Channel. `bytes(packet)` serialises packets for writing. Tests ship public sample files: `sample.c10` (1 MB), `pcm.c10`, `ethernet.c10`, `event.c10`, `discrete.c10`. |
| **c10-tools** | BSD-3 | 1.1.4, Apr 2022 | Built on pyChapter10. Subcommands: stat, inspect, copy, dump, find, frompcap, capture, reindex, timefix, allbus, streamcheck. |
| **irig106lib** | C (Bob Baggerman / irig106.org), BSD-3 | Last push 2024-10-18; 53 stars | Read/write. Decoders for TMATS, time, 1553, 16PP194, 429, CAN, discrete, Ethernet, index, UART; video incomplete. |
| **irig106utils** | C | Last push 2021-03 | No licence declared. |
| **AcraNetwork** (Curtiss-Wright staff) | Python, **GPLv3** | 1.3.15, upload 2026-10-09 | Creates and parses Ch10/11 packets and FTI Ethernet. |
| **TelemetryWorks irig106-write / irig106-tmats** | Rust, Apache-2.0 | Created 2026 | New and immature. |

Sources: [pyChapter10](https://github.com/atac/pyChapter10); [pyChapter10 docs](https://pychapter10.readthedocs.io/en/latest/); [PyPI pychapter10](https://pypi.org/project/pychapter10/); [c10-tools](https://github.com/atac/c10-tools); [irig106lib](https://github.com/bbaggerman/irig106lib); [irig106utils](https://github.com/bbaggerman/irig106utils); [AcraNetwork docs](https://acranetwork.readthedocs.io/en/stable/chapter11.html), [PyPI](https://pypi.org/project/acranetwork/); [irig106-write](https://github.com/TelemetryWorks/irig106-write)

**Bus simulators and encoders** [DIRECT; repo metadata]

| Repo | Language / licence | Notes |
|---|---|---|
| ShubhankarKulkarni/MIL-STD-1553-Simulator | Python, GPL-2.0 | 48 stars, 2021 |
| JaskRendix/pymil1553 | Python, GPL-2.0 | 2026 |
| jbm950/Rust-1553-Simulator | Apache-2.0 | 2026 |
| mjhouse/mil_std_1553b | Rust parser, MIT | |
| aeroneous/PyARINC429 | MIT | 94 stars, 2018 |
| osnosn/FlightDataDecode | Python, LGPL-2.1 | Decodes raw QAR ARINC 573/717/767 frames |

Sources: [MIL-STD-1553-Simulator](https://github.com/ShubhankarKulkarni/MIL-STD-1553-Simulator); [pymil1553](https://github.com/JaskRendix/pymil1553); [Rust-1553-Simulator](https://github.com/jbm950/Rust-1553-Simulator); [mil_std_1553b](https://github.com/mjhouse/mil_std_1553b); [PyARINC429](https://github.com/aeroneous/PyARINC429); [FlightDataDecode](https://github.com/osnosn/FlightDataDecode)

### Inferences
- [INFERENCE] Ch10/11 is the strongest candidate for the simulator's raw on-aircraft format, for four reasons:
  1. **It is self-describing.** TMATS is embedded, which solves the "missing data-frame-layout" failure documented by BEA (Q6).
  2. **It is multi-bus and multi-rate with a common 100 ns time base.**
  3. **It can be validated.** Our writer's output can be parsed by two independent open implementations (pyChapter10 and irig106lib) and compared against the public sample.
  4. **It supports both batch (file) and live (UDP/TCP 10620) modes** with the same packets.
- [ASSUMPTION/caution] Operational (non-test) fighter maintenance recorders generally use proprietary formats; no fetched source shows any of the five candidates using Ch10 operationally. Ch10 should therefore be presented as a public surrogate, with its rationale (DDC lists HUMS and mission recorders as Ch10 applications), not as "what the Tejas records".
- [ASSUMPTION] Licensing: prefer BSD-3 tools (pyChapter10, irig106lib) inside the product. Keep GPL tools (AcraNetwork, the GPL 1553 simulators) for testing only, or check compatibility with the project licence.

### Gaps
- iNET/TmNS Chapters 21–28 and MDL (Ch23) text were not fetched (TRMC attachment URLs unknown without search).
- XidML specification details: only Wikipedia was fetched. XidML 3.0 has five components (parameters, instruments, packages, links, algorithms), with packages describing IRIG-106 Ch4 frames, 1553 messages and Ethernet packets. — [Wikipedia: XidML](https://en.wikipedia.org/wiki/XidML)

---

## Q5. Download and ground systems: post-flight download, ground stations and maintenance aids, engine health ground systems, fleet databases, flight-data monitoring and frame layouts, civil real-time analogues, F-35 ALIS/ODIN; latency

### Takeaway
For operational fighters, maintenance and health data reaches the ground **in post-flight batches**:
- **Removable media:** DTC / PMD "brick".
- **PC/ground-station download** from the recorder.

It is then decoded with a frame layout or setup record into EU, and fed into a squadron-level maintenance information system:
- USAF: IMDS and AFTO 781 forms; CEMS for engines.
- F-35: SOU → national CPE → central ALOU.

Real-time air-to-ground data exists mainly in flight test (PCM/Ch7 telemetry of selected words) and in civil fleets (ACARS reports). The dominant real-world pain points are data integrity and metadata/record linkage, not transport.

### Cited Findings
**F-35 ALIS data flow** [DIRECT]
- **ALOU:** "the central computer unit that all F-35 data are sent through". There is one ALOU, owned by the prime contractor, with separate classified and unclassified servers.
- **CPE:** provides "software and data distribution for a country's entire F-35 fleet". There is typically one per country.
- **SOU:** "the node local to each F-35 squadron". There are classified and unclassified SOUs; cases weigh about 200 lb each.
- **PMD → PMD Reader → SOU.** The PMA is the "ruggedized laptop… to view unclassified technical data, and perform and document maintenance activities".
- **Electronic Equipment Logbooks** are electronic files on parts with "part history and remaining life (hours)". An aircraft must be electronically "complete" in ALIS to fly.
- **Data-integrity findings:**
  - users at one site saw "between 0 and 400 issues per week related to inaccurate or missing electronic records";
  - 213 of 263 spare parts (81%) delivered to one location in June 2018 lacked electronic records;
  - users spend "5,000 to 10,000 hours per year manually tracking information that should be automatically and accurately captured within ALIS".
- DOD planned to rename the redesigned system the Operational Data Integrated Network (ODIN). Cloud versus on-site hosting was undecided as of March 2020.

— [GAO-20-316, *Weapon System Sustainment: DOD Needs a Strategy for Re-Designing the F-35's Central Logistics System*, 6 Mar 2020, pp. 8–15](https://www.gao.gov/products/gao-20-316) (local PDF: `research_sources/data_pathway/GAO-20-316_ALIS.pdf`)

- The original ALIS design routes "all F-35 data produced across the U.S. fleet… to a Central Point of Entry" and then to the main operating unit, "with no backup system or redundancy". — [GAO-16-439, 14 Apr 2016](https://www.gao.gov/products/gao-16-439)

**USAF maintenance records (F-16)** [DIRECT]
- "AFTO 781-series forms capture maintenance actions, inspections, servicing, configuration, current status, and flight activities for an aircraft."
- "The Integrated Maintenance Data System (IMDS) is an electronic database used to track maintenance actions, flight activity, schedule future maintenance and serve as a collective history of maintenance actions."
- Investigators reviewed 180 days of IMDS data.
- The CEMS and EDU acronyms appear in the same report.

— [USAF AIB F-16C 90-0755](https://www.f-16.net/downloads/F-16-AIB-Reports/90-0755.pdf)

**Recorder download in practice** [DIRECT]
- F-16 DAS: "Download is accomplished with a PC running a web-browser". Configuration uses an OEM PC tool for parameters and exceedance checks. Replay and animation software is provided. — [GE DAS datasheet](https://www.geaerospace.com/sites/default/files/2022-02/DAS-Datasheet.pdf)
- IRIG Ch10: "On-board recorders may have an RMM [removable memory module] capability or the on-board recorder can be removed from the acquisition platform and taken to a ground station for data download." The interface is IEEE 1394b or Ethernet. — [IRIG 106-15 Ch10 §10.3.5–10.3.6](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2)

**Flight-test ground processing (AFTI/F-16, NASA Dryden)** [DIRECT]
- Both PCM streams were telemetered on L-band in real time.
- "The total multiplex bus traffic is recorded on board and is available only for postflight data processing" (5 tracks, all bus data).
- Ground metadata: the "calibration data base file" and "lineup sheet", "a list of all parameters on the aircraft coded by parameter and calibration identification numbers", are transferred from the post-flight processor to the real-time processor.

— [NASA TM-84899](https://ntrs.nasa.gov/api/citations/19830004825/downloads/19830004825.pdf)

**FDR frame layout and decoding** [TRANSFER: civil ARINC 573/717 FDR; this is the standard public model of "recorded frame + layout document → EU", but the frame format is civil]
- "Data acquisition systems output a binary file sequenced in four-second frames. Each frame is divided into four one-second-subframes. Each subframe is divided into 64, 128, 256 or 512 'words' of 12 bits each."
- Example Data Frame Layout (DFL) entry: AIRSPEED, word 19, bits 12–1, 1 sps, all subframes; linear conversion Y = 0.25006·X kt (0–4095 counts → 0–1024 kt).
- BEA found that only 11 of 20 airlines had comprehensive DFL documents, and only 7 had filed them with the authority. BEA recommended that EASA require "data frame layout information recorded on FDRs themselves".

— [BEA FDR Read-Out Study (May 2005), §1.2.2–1.2.3, §2.4.4, §4.2](https://bea.aero/uploads/tx_scalaetudessecurite/use.of.fdr_01.pdf)

**Civil real-time analogue (ACARS)** [TRANSFER: civil air-ground datalink; illustrates real-time event/report streaming that fighters generally lack in routine ops]
- ACARS is "a digital data communication system for transmission of short messages between aircraft and ground stations", over VHF, HF or SATCOM.
- It reports OOOI events (out/off/on/in) with times.
- It "sends real-time equipment condition data and maintenance faults or abnormal events to ground stations", which airlines use for health monitoring and maintenance planning.
- Message standards: ARINC 618/633 (ARINC 597 originally).

— [Wikipedia: ACARS](https://en.wikipedia.org/wiki/ACARS)

**HUMS ground transfer** [TRANSFER: rotorcraft-centric]
- Recent advances include "automated wireless data transfer from the aircraft via WiFi or Cellular" and "Remaining Useful Life estimates". — [Wikipedia: HUMS](https://en.wikipedia.org/wiki/Health_and_usage_monitoring_systems)

**MFOQA** [DIRECT, existence only]
- Military FOQA (MFOQA) is defined as "military flight operational quality assurance". "Several national air forces have started FOQA programs." — [Wikipedia: FOQA](https://en.wikipedia.org/wiki/Flight_operations_quality_assurance)

### Inferences
- [INFERENCE] The realistic latency model for routine fighter operations is:
  - **post-flight batch** (download minutes to hours after landing; one file per sortie per recorder), with
  - **a small real-time channel** of selected events only in special cases (flight test telemetry, or a hypothetical future datalink).
  
  The ingestion layer must therefore handle large bursts of old event-time data, plus duplicates when a download is retried.
- [INFERENCE] GAO's ALIS findings map directly onto the problem statement ("health-monitoring, technical records, spares and maintenance-agency data not integrated"). The simulator should generate:
  - deliberate record-linkage keys: tail number, engine serial, LRU and part serials, sortie ID;
  - realistic metadata defects (missing or incorrect part records, out-of-date layouts) as a configurable fault class.
  
  Cross-link: maintenance-records researcher and validation researcher.

### Gaps
- F-16 ground station / debrief station products and the CEMS data flow; Navy F/A-18 ground processing (MSDRS download, SAFE structural processing); Navy engine systems.
- Download timing on fighters. Wireless download on any candidate.
- IAF systems (cross-link: maintenance-records researcher).
- ARINC 767 (Enhanced Airborne Flight Recorder) and ARINC 647A (FRED) details were not verified.
- Boeing AHM and Airbus Skywise specifics: fetches returned 404 and searches were exhausted.

---

## Q6. Metadata: parameter dictionaries (XidML, TMATS, ICDs), EU conversion, calibration, aircraft/tail/engine serials, sortie IDs, configuration; time-base semantics

### Takeaway
Every stage of the real pathway depends on an external description to turn bits into meaning:
- the ICD (1553 RT/SA/word/bit/LSB);
- the ARINC 429 label tables;
- the DFL/TMATS (location, bits, conversion, calibration);
- the configuration and record keys.

Historically, losing or mis-versioning that description is a primary failure mode (BEA; ALIS). Time also has several distinct meanings — sample, bus, record, absolute and ingest time — and public standards define precisely which instant each timestamp refers to.

### Cited Findings
**Metadata content in TMATS** [DIRECT]
- **G group:** program name, data sources.
- **R group:** channel IDs, channel types, number of source bits, events, index.
- **B group:** bus, message, measurement and bit-mask mapping.
- **C group:** measurement name, transducer type/model/**serial number**, engineering units, bit weights, calibration stimulus/telemetry/data-value points, high/low operational/alert/warning limits, **sample rate**, conversion type (pair sets, polynomial coefficients, derived algorithm, discrete), release date.

— [IRIG 106-07 Ch9](https://www.trmc.osd.mil/wiki/download/attachments/113019518/chapter9.pdf?api=v2)

- The TMATS setup record must be the first packet of a Ch10 recording, and its version field governs interpretation. — [RCC 123-16 §5.5](https://www.irig106.org/docs/rcc/123-16_IRIG_106_Chapter10_Programmers_Handbook.pdf)

**XidML** [DIRECT]
- "describes how data is acquired, processed and packaged for transmission, storage or reproduction".
- Parameters carry name, data format, unit and size in bits. Instruments carry manufacturer, part reference and serial number. Algorithms carry, e.g., linearising polynomials.

— [Wikipedia: XidML](https://en.wikipedia.org/wiki/XidML)

**Calibration/lineup as ground files** [DIRECT, AFTI/F-16]
- The "calibration data base file" and "lineup sheet" (parameters coded by parameter and calibration IDs) are maintained in the post-flight processor and transferred to real-time processing. — [NASA TM-84899](https://ntrs.nasa.gov/api/citations/19830004825/downloads/19830004825.pdf)

**DFL as metadata** [TRANSFER: civil]
- The DFL describes "location of parameters, number of bits used to encode parameters, type and method of encoding" and "the functions used to convert the recorded value into the actual physical value", backed by calibration reports.
- Incomplete or obsolete DFLs repeatedly impeded analysis. In one case an EGT conversion in the DFL was wrong.

— [BEA 2005 §1.2.2, §2.3.2](https://bea.aero/uploads/tx_scalaetudessecurite/use.of.fdr_01.pdf)

**Record keys and configuration** [DIRECT]
- F-35 Electronic Equipment Logbooks per part (history, remaining life). — [GAO-20-316](https://www.gao.gov/products/gao-20-316)
- USAF AFTO 781 captures "configuration, current status, and flight activities". IMDS tracks "flight activity". — [F-16 AIB](https://www.f-16.net/downloads/F-16-AIB-Reports/90-0755.pdf)

**Time-base semantics** [DIRECT]

| Packet type | Which instant the timestamp refers to |
|---|---|
| Ch10 1553 | The IPTS refers to a selectable bit: the first bit of the first word, the last bit of the command word, or the last bit of the last word (TTB field). |
| ARINC 429 | Packet time is the first word's time; later words are reconstructed from 0.1 µs gap times. |
| Analog | Packet time is the first sample; no per-sample stamps. |
| Discrete | Per-event intra-packet time. |
| Time packets | Map the RTC to IRIG/GPS/UTC; the source may revert from External to Internal on loss of lock (flagged). |

— [IRIG 106-15 Ch10 §10.6.3–10.6.8](https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2)

- A free-running RTC with an arbitrary start; absolute time is derived from time packets. — [RCC 123-16 §5.6](https://www.irig106.org/docs/rcc/123-16_IRIG_106_Chapter10_Programmers_Handbook.pdf)
- IRIG-B B122 lacks a year field. — [Wikipedia: IRIG timecode](https://en.wikipedia.org/wiki/IRIG_timecode)

### Inferences
- **[ASSUMPTION] Time fields for the canonical representation.** Carry six explicit times per sample or message:
  - `t_true`: simulation physics time;
  - `t_sample`: when the owning LRU acquired the value;
  - `t_bus`: when it appeared on the bus, at the Ch10 TTB-defined bit;
  - `t_record`: recorder RTC (10 MHz ticks);
  - `t_utc`: absolute time via a simulated GPS/IRIG time source, including lock-loss periods;
  - `t_ingest`: ground arrival.
  
  **Realistic offsets:**
  - `t_bus − t_sample` = LRU compute latency + wait for the BC's next poll of that subaddress (up to one rate-group period);
  - `t_record` = `t_bus` + monitor latency;
  - packets close within ≤100 ms;
  - `t_ingest` = hours later for post-flight download.
- **[ASSUMPTION] Phalanx Parameter Dictionary.** Make it the single source of truth and generate TMATS (and optionally XidML) from it. Per parameter:
  - ID, name, units;
  - source LRU and channel;
  - physical acquisition (sensor type, ADC bits, range);
  - bus mapping (bus / RT / SA / T-R / word / bit mask, or 429 label / SDI);
  - encoding (BNR two's complement, LSB weight, BCD, discrete) and validity mapping (SSM or status bit);
  - rate group;
  - calibration polynomial and calibration date;
  - sensor serial;
  - limits (operational / alert / warning, mirroring TMATS MOT1–6);
  - dictionary version and hash.
  
  **Per sortie manifest:** tail number, engine serial(s) and positions, LRU serials, software load, configuration, sortie ID, crew/mission type, dictionary version.

### Gaps
- No public fighter ICD or DFL example was found. The dictionary content must be synthetic.
- The XidML schema and iNET MDL text were not reviewed in depth.

---

## Q7. Modern ground ingestion practices: streaming platforms, schemas, time-series storage, late/out-of-order data, batch vs live, idempotency and replay; how fleets ingest bulk flight files

### Takeaway
Standard, publicly documented practices fit the post-flight-batch reality well:
- an immutable raw store (one recorder file per sortie);
- a log-based streaming backbone with keyed, idempotent writes;
- schema-registered binary records;
- event-time processing with watermarks and allowed lateness;
- columnar files for analytics.

ISO 13374 / OSA-CBM gives a recognised functional decomposition for the downstream CBM/PdM chain.

### Cited Findings
**Kafka delivery semantics** [DIRECT]
- At-most-once, at-least-once and exactly-once are defined.
- "Since 0.11.0.0, the Kafka producer also supports an idempotent delivery option which guarantees that resending will not result in duplicate entries in the log… the broker assigns each producer an ID and deduplicates messages using a sequence number."
- Transactions write atomically across partitions. Exactly-once is available with transactional producers and read-committed consumers.
- "Log compaction ensures that Kafka will always retain at least the last known value for each message key."

— [Apache Kafka design documentation](https://github.com/apache/kafka/blob/trunk/docs/design/design.md)

**Event time vs processing time** [DIRECT]
- "Event time is the time that each individual event occurred on its producing device."
- A Watermark(t) "declares that event time has reached time t".
- Watermarks are "crucial for out-of-order streams". Late elements arrive after the watermark and can be handled with allowed lateness.
- Event-time processing "incurs some latency while waiting for out-of-order events".

— [Apache Flink: Timely Stream Processing](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/)

**Schemas** [DIRECT]
- Avro schemas are JSON. Binary data carries no field names. Object container files embed the writer schema plus sync markers.
- Reader/writer schema resolution supports evolution: a new reader field with a default is filled with that default.
- Logical types include `timestamp-micros`. The fetched 1.11.1 spec does not list a nanosecond type.

— [Apache Avro 1.11.1 specification](https://avro.apache.org/docs/1.11.1/specification/)

- Parquet is "an open source, column-oriented data file format designed for efficient data storage and retrieval". — [Apache Parquet overview](https://parquet.apache.org/docs/overview/)

**Edge/IIoT and data-centric middleware** [DIRECT]
- Sparkplug 3.0 over MQTT, with birth and death certificates for state awareness. — [Eclipse Sparkplug](https://sparkplug.eclipse.org/)
- OMG DDS: brokerless, data-centric publish-subscribe with keyed topics, QoS (reliability, liveliness, durability) and XTypes type evolution. — [DDS Foundation](https://www.dds-foundation.org/what-is-dds-3/)

**CBM architecture standard** [DIRECT]
- OSA-CBM is "a standard architecture for moving information in a condition-based maintenance system". It implements ISO 13374's six functional blocks with UML-defined data structures and XML/WSDL SDK interfaces.
- Developed in 2001 with US Navy DUST funding (with Boeing and others). Latest release 3.3.1 (29 Jun 2010).

— [MIMOSA OSA-CBM](https://www.mimosa.org/mimosa-osa-cbm/)

**Bulk flight-file ingestion examples** [DIRECT]
- ALIS: PMD → PMD Reader → SOU, with centralised CPE/ALOU aggregation. — [GAO-20-316](https://www.gao.gov/products/gao-20-316)
- An open-source Ch10 → Filebeat → Elasticsearch/Kibana pipeline built on irig106lib/irig106utils (`idmp1553`). — [elastickent/mil-std-1553-es](https://github.com/elastickent/mil-std-1553-es)
- c10-tools `frompcap` / `capture` show Ch10 ↔ network-capture conversion. — [c10-tools](https://github.com/atac/c10-tools)

### Inferences
- **[ASSUMPTION] Recommended ingestion design for Phalanx.**
  1. **Raw landing zone.** Write `.c10` files (one per recorder per sortie) to object storage, immutable and named by deterministic keys (tail / sortie / recorder / file hash).
  2. **Decoder service.** A Ch10 → canonical EU decoder (pyChapter10 or irig106lib) publishes to Kafka topics keyed by `tail_no` (partition affinity preserves per-aircraft ordering).
  3. **Separate topics** for:
     - `param.samples` (EU, validity, provenance, all six times);
     - `events.bit_faults`;
     - `events.exceedances`;
     - `usage.counters`;
     - `sortie.manifest`;
     - `maint.records`.
  4. **Schemas.** Avro or Protobuf schemas in a registry.
  5. **Idempotency.** Producer idempotence plus a deterministic `record_id` = hash(tail, sortie, channel_id, packet seq/RTC, message index), so a re-downloaded file produces no duplicates downstream.
  6. **Event time.** Use event-time windows with per-sortie watermarks: a sortie arrives hours late as a burst, so a single global wall-clock watermark is wrong.
  7. **Analytics and dashboards.** Parquet partitioned by date/tail/sortie for analytics; a time-series DB for dashboards.
  8. **Replay.** Re-reading the raw `.c10` regenerates any downstream state.
- [ASSUMPTION] Kafka is the pragmatic default : tooling, replay and schema registry. MQTT/Sparkplug suits a simulated "aircraft edge → base" live link. DDS matches military avionics middleware style but adds complexity. Keep the transport behind an interface so it can be swapped.

### Gaps
- No public description was found of the exact ingestion stack of IAF, USAF or Navy fleet systems (beyond ALIS topology).
- Time-series DB product docs (TimescaleDB, InfluxDB) were not fetched. Treat product choice as open.

---

## Q8. Where should the simulator emit? Evaluation of six emission points

### Takeaway
No single emission point serves both realism and an easy downstream plug-in. The recommended architecture is layered:
- **Internally:** a canonical, acquisition-level representation, plus a versioned parameter dictionary.
- **Externally, two contracts:**
  1. **Raw system-of-record:** IRIG 106 Ch10/11 recorder files and streams, containing bus-level 1553/429, analog, discrete, time and event packets, encoded from a synthetic ICD.
  2. **Stable decoded contract:** EU parameter streams, sortie tables and maintenance/health event streams.

The downstream PdM system plugs into contract 2, which is produced by real ground-decoding code from contract 1. This mirrors the real aircraft-to-ground boundary (recorder download) and keeps alternatives open through adapters.

### Cited Findings
The evaluation draws on evidence already cited in Q1–Q7:
- 1553 carries EU values and fault/status at ≤100 Hz-class rates; high-bandwidth signals stay off the bus (1553 rationale §10.3; AFTI/F-16).
- Real maintenance data crosses to the ground by post-flight download of recorder or PMD media (GAO-20-316; GE DAS; IRIG Ch10 §10.3.5).
- Decoding depends on layout metadata, whose absence is the documented failure mode (BEA 2005; ALIS data-integrity findings).
- Ch10 provides embedded TMATS, a unified time base, file and stream modes, and open BSD-3 parsers with public sample files for conformance testing (IRIG 106 Ch10/11; RCC 123-16; pyChapter10; irig106lib).

### Inferences
See closing item (c) below for the full option-by-option evaluation and recommendation.

### Gaps
- No fighter-specific public dataset exists at bus or recorder level against which to validate content, as opposed to format. Content realism must be validated statistically against public civil or engine datasets. Cross-link: datasets researcher and validation researcher.

---

## Closing items (required by the brief): (a) key findings, (b) pipeline table, (c) emission-point evaluation and recommendation, (d) open questions and gaps, (e) ranked sources

### (a) Key findings summary
1. **Digitisation happens at the sensor-owning LRU or in acquisition units.** The first standard, public representation of most fighter parameters is a bus word carrying an EU value with validity semantics:
   - 1553 status and BIT words via mode codes 19/16/3;
   - ARINC 429 SSM (FW/NCD/FT/NO).
   
   The 1553 design rule keeps signals above about 400 Hz–3 kHz off the bus. [Alta; 1553 rationale; AFTI/F-16; Wikipedia ARINC 429]
2. **MIL-STD-1553B is the common backbone** where public sources speak: the F-16 A-MUX/D-MUX with the FCC (later MMC) as BC; F/A-18; Gripen (5 buses); Tejas. Message mapping and rates live in non-public ICDs, so a synthetic ICD is required. Public schedule examples run 5–100 Hz; the only public real recording found (KC-135) shows mostly 10–20 Hz 1553 messages and 10/20/100 Hz ARINC 429 labels.
3. **Fighter recorders** combine a bus-monitor/analogue acquisition unit with crash-survivable memory: F-16 SAU + CSMU → GE DAU + ECSMU (ED-112), with JEDAI planned. Engine and usage monitoring (F404 IECMS, F-16 EOT, CEMS) and HUMS (Gripen, Su-30MKI, Tejas) run alongside. Download is post-flight: PC/web browser, DTC or PMD.
4. **The aircraft-to-ground boundary is a post-flight batch download.** F-35 ALIS: PMD → PMD Reader → SOU → CPE → ALOU. USAF: IMDS / AFTO 781. The biggest real failures are data integrity and record linkage (ALIS: 0–400 record issues per week; 81% of spares lacking electronic records; 5–10k hours per year of manual tracking), and missing or obsolete frame-layout metadata (BEA).
5. **IRIG 106 Ch10/11 is the only fully public, byte-level standard** spanning multi-bus capture, embedded metadata (TMATS), a precise time base (10 MHz 48-bit RTC plus time packets) and batch/stream transport (UDP, TCP 10620, Ch7 RF). It has mature BSD-3 tooling (pyChapter10, irig106lib, c10-tools) and public sample files for conformance tests.
6. **Time has at least six meanings** (true, sample, bus, record, absolute, ingest). The standards pin exactly which bit or sample a timestamp refers to, and the simulator must preserve this explicitly.
7. **Recommended architecture:** canonical internal representation + parameter dictionary → adapters → (i) Ch10/11 raw files/streams and (ii) a decoded EU and event contract on a Kafka-style log with Avro/Protobuf schemas, event-time semantics, idempotent keys and Parquet sortie tables. The downstream PdM consumes (ii); (i) is the replayable system of record.

### (b) Stage-by-stage pipeline table

| Stage | Components (public examples) | Data form | Rates | Timing / latency | Metadata | Sources |
|---|---|---|---|---|---|---|
| 0. Physical sensing | Thermocouples/RTDs, pressure transducers, speed pickups, LVDT/RVDT, synchros, strain gauges, accelerometers, discretes (switches, caution lights) | Analogue voltage/current/ratiometric/frequency; synchro; discrete levels | Continuous; bandwidth from DC to kHz (vibration) | Physical truth time `t_true` | Transducer type, model, **serial**, calibration points/date (TMATS C-d\TRD, C-d\MC) | GE DAS datasheet; TMATS Ch9; AFTI/F-16 (NASA TM-84899) |
| 1. Acquisition & processing | Owning LRUs: FADEC/DEC (F404-IN20 FADEC; RM12 DEC), ADC (BEL on Tejas), EGI/INS (Sigma-95 on Su-30MKI), quadruplex/triplex DFCC; acquisition units (F-16 SAU → GE DAU; FTI PCM encoders) | Digitised counts → EU in LRU; validity via range checks and channel voting (FBW redundancy); exceedance checks configured in DAU | LRU frame rates not public; FDR minimum examples 0.125–4 s (14 CFR 121 App M) | `t_sample`; compute latency per LRU cycle | Channel ID, ADC bits, scaling, validity semantics | Wikipedia (F404, RM12, Tejas, Su-30MKI, Gripen); GE DAS; BEA §1.2; 14 CFR 121 App M |
| 2a. MIL-STD-1553B | BC = mission computer (F-16 FCC→MMC; SMS backup); RTs = LRUs; BMs = recorders/HUMS; F-16 A-MUX + D-MUX; Gripen 5 buses; Tejas 1553B | 20-bit words (3 sync + 16 data + parity); command (RT5/TR/SA5/WC5), status (ME, SR, BUSY, SSF, TF), data words; ≤32 data words/message; MSB-first, multi-word, bit packing | 1 Mb/s; minor frame typically ≤100 Hz base; examples 20/10/5 Hz and 100/50/25 Hz; KC-135 sample ~10–40 Hz | RT response 4–12 µs; timeout 14 µs; inter-message gap ≥4 µs; data age up to one rate-group period (assumption) | ICD (RT/SA/word/bit/LSB) – proprietary; SAE AS15532 standard words | Alta tutorial; 1553 rationale; UEI; Wikipedia 1553; NASA TM-84899; Bloomy; US5367641; sample.c10 |
| 2b. ARINC 429 | COTS LRUs (air data, nav, radios); GE DAS has 429 inputs | 32-bit word: label (octal, reversed) / SDI / 19-bit data (BNR/BCD/discrete) / SSM / odd parity | 12.5 or 100 kb/s; typical update intervals 25/40/65 ms; KC-135 sample ~10/20/100 Hz | ≥4-bit word gap (tutorial-level); unidirectional | Label tables (ARINC 429 attachments) – paywalled | Wikipedia ARINC 429; UEI; IRIG Ch10 §10.6.8 |
| 2c. Other networks | AFDX/ARINC 664 P7 (civil; newer military); F-35 Fibre Channel + IEEE 1394b; MIL-STD-1760 store interface (1553 + discretes + HB video; HS1760 FC 1.0625 Gb/s); CAN; RS-422/485 | Ethernet frames on virtual links with BAG; FC frames; UART bytes | 100 Mb/s (AFDX); 1.0625 Gb/s (HS1760) | Deterministic via BAG | VL tables, store ICDs | Wikipedia AFDX, F-35, MIL-STD-1760; IRIG Ch11 |
| 3. Onboard recording & health | F-16 CSFDR (SAU + CSMU) → DAS (DAU 2870A2 + ECSMU 3254A4, ED-112) → JEDAI; Seat Data Recorder; DTC; EDU / EOT counter; F404 IECMS; Gripen DTU + HUMS; Su-30MKI HUMS ("engineering data recorder"); Tejas integrated health monitoring; F-35 PMD; MIL-HDBK-2124 Type I deployable / Type II hardened | Proprietary recorder formats (public surrogates: ARINC 717 frames; IRIG Ch10 packets); event records; usage counters; fault codes | Configured per DAU program; civil FDR ≥88 parameters, about 25 h loop | Continuous loop plus event/exceedance captures (window lengths not public) | Recorder configuration (parameters, exceedances); DFL/TMATS; tail number | F-16 AIB; GE DAS; GovTribe (snippet); MIL-HDBK-2124; Wikipedia (Flight recorder, Gripen, Su-30MKI, Tejas, F404); GAO-20-316 |
| 4. FTI & telemetry (public reference) | PCM encoders (Ch4), bus-capture formatters (Ch8), Ch10/11 recorders, Ch7 packet downlink, iNET/TmNS | Ch4: 4–32-bit words, ≤8192-bit minor frames, ≤256 minor/major. Ch8: 24-bit labelled words, sync FAF320. Ch10: 24-B header (EB25, channel ID, length, sequence, flags, type, 48-bit RTC), 1553/429/analog/discrete/time/event packets | Packets ≤100 ms of data; commit ≤1 s; time packets ≥1 Hz; RTC 10 MHz | Real-time RF for selected words; full bus traffic post-flight only (AFTI) | TMATS setup record first in file (G/R/B/C groups) | IRIG 106 Ch4/7/8/9/10/11; RCC 123-16; DDC; NASA TM-84899 |
| 5. Download & ground processing | PC/web-browser download (DAS); RMM/recorder removal (Ch10); PMD Reader → SOU (F-35); debrief/replay; decoding with DFL/TMATS → EU | Recorder file per sortie → EU parameter tables + events | Batch per sortie | Minutes to hours after landing (assumption); retries create duplicates | DFL/TMATS versions; calibration DB; "lineup sheet" | GE DAS; IRIG Ch10 §10.3.5; GAO-20-316; BEA; NASA TM-84899 |
| 6. Maintenance & fleet systems | USAF IMDS + AFTO 781; CEMS (engines); F-35 SOU → CPE → ALOU; Electronic Equipment Logbooks; MFOQA; civil ACARS / FOQA analogues; OSA-CBM / ISO 13374 for CBM chain | Maintenance actions, flight activity, configuration, part life records, engine usage | Per sortie / per maintenance action; ACARS real-time messages (civil) | Fleet aggregation (CPE → ALOU); data-integrity issues | Tail/part/engine serial linkage; part history and remaining life | F-16 AIB; GAO-20-316; GAO-16-439; Wikipedia ACARS/FOQA; MIMOSA |
| 7. Ingestion/analytics (modern practice) | Object store (raw), Kafka/MQTT/DDS, schema registry (Avro/Protobuf), Flink-style event-time processing, Parquet, TSDB | Keyed records with schemas | Burst replays per sortie | Event-time watermarks per sortie; idempotent producers; log compaction for latest state | Schema versions; dictionary hash | Kafka design doc; Flink; Avro; Parquet; Sparkplug; DDS |

### (c) Emission-point evaluation and recommendation

**Option-by-option evaluation**

| Option | Realism achievable | Effort | Downstream consumers it fits | Validation possibility (public) | Reference implementations |
|---|---|---|---|---|---|
| (1) Raw physical sensor signals | Highest physical fidelity, but no operational consumer sees it outside LRUs and DAUs. Only valuable for DAU/HUMS-level channels (strain, vibration waveforms). | Very high: transducer, conditioning and ADC models per channel | Hardware-in-the-loop, DAU algorithm tests, vibration feature extraction | Weak: no fighter waveform data; only generic physics | None specific; Ch10 analog packets can carry it |
| (2) Acquisition-level digitised values (counts or EU per channel, per LRU lane, with validity) | High for noise, quantisation, sampling jitter, channel disagreement and sensor failure modes | Medium-high | Sensor-residual and fault research; source for all higher layers | Medium: civil DFL conversions; FDR sampling minima; calibration-polynomial conventions (TMATS C group) | TMATS C group; BEA DFL example |
| (3) Bus-level messages (1553 command/status/data with schedule; 429 labels with SSM) | High "avionics" realism: update rates, scaling, packing, staleness, status/BIT, bus errors | High: needs a synthetic ICD and BC scheduler | Bus monitors, recorder/HUMS emulation, decoding-layer tests, cyber/anomaly demos | Format/timing validation strong (1553/429 rules); content validation impossible (ICDs not public) | 1553 simulators (GPL/Apache); PyARINC429 (MIT); 1553 tutorials |
| (4) Recorder-level packets/files (IRIG 106 Ch10/11 with TMATS; Ch10-over-UDP/TCP for live) | High for the aircraft→ground boundary; self-describing; multi-bus; precise time. Caveat: a public surrogate for proprietary fighter recorder formats. | Medium (libraries exist) on top of (3) | Post-flight download simulation, replay, standard tooling, live streaming, Ch7 telemetry | Strong format validation: parse with pyChapter10 and irig106lib, compare with public sample.c10/pcm.c10/event.c10; `c10 stat` | pyChapter10, irig106lib, c10-tools (BSD-3); AcraNetwork (GPLv3) |
| (5) Post-download EU parameter tables per sortie (decoded, time-aligned, with quality flags and provenance) | Matches what analysts and PdM models actually consume (FDM/FOQA after DFL decode). Loses bus artefacts if generated directly. | Low-medium | PdM/AI training, dashboards, fleet analytics | Best statistical validation against public datasets (cross-link: datasets researcher) | Parquet/Avro; FlightDataDecode (civil frames) |
| (6) Ground/maintenance database events (BIT/fault codes, exceedances, usage counters, maintenance actions, part removals, technical records) | Essential for the problem (integration of health, records, spares) | Medium | Fleet availability, spares, PdM labels / ground truth | Structural plausibility against public process descriptions (IMDS/AFTO 781; ALIS EEL); no public record datasets | OSA-CBM / ISO 13374 structures; Kafka |

**Recommendation (reasoned, with alternatives kept open)** [ASSUMPTION, grounded in the cited evidence]

1. **Canonical Internal Representation (CIR) at acquisition level (option 2) plus a versioned Parameter Dictionary.**
   - Each record holds: parameter ID, `t_true`, `t_sample`, measured EU value, truth value (kept for labels and validation, never exported to the PdM contract), source LRU/lane, validity state, quality flags.
   - The dictionary also generates TMATS (and optionally XidML).
   - All fault/degradation and sensor-texture models write here. Cross-link: faults/degradation and sensor-residual researchers.
2. **Adapter A — Bus encoder (option 3).** CIR → 1553 BC schedule (configurable rate groups) and RT messages per a synthetic "Phalanx ICD" (AS15532-style words; status/BIT words), and ARINC 429 labels with SSM.
3. **Adapter B — Recorder writer (option 4), the raw system of record.**
   - Bus messages + selected analog/discrete channels + time packets + recording events → IRIG 106 Ch10/11 file per sortie, with TMATS first.
   - The same packets can be streamed live via Ch10 UDP (with transfer header) or TCP port 10620 for a "live link" demo.
   - Optionally Ch7 for an RF-telemetry illusion.
4. **Adapter C — Ground decoder (realistic ground processing).** Ch10 → decoded EU samples with quality and provenance (channel ID, RT/SA/word, ICD version, TMATS hash, all six timestamps). It publishes:
   - `param.samples` to Kafka (Avro/Protobuf);
   - Parquet sortie tables (option 5).
   
   This is the **stable downstream contract**. It is real code that would also ingest genuine Ch10 FTI data if HAL, ADA or ASTE ever provided some.
5. **Adapter D — Health and maintenance event stream (option 6).**
   - Onboard-originated events (BIT/fault codes, exceedances, usage counters such as EOT and cycles) are emitted both inside the Ch10 file (recording events, 1553 BIT words) and as decoded events.
   - Ground-originated records (maintenance actions, part removals and installs, inspections, spares, technical records) go to separate topics keyed by tail/engine/part serial and sortie ID. Defect injection reproduces ALIS-style record gaps.
6. **Fast path, kept open.** For early AI work, CIR → Adapter C's output schema directly (bypassing A/B) is allowed, but it **must produce the identical schema** and mark `provenance=direct`. Downstream code is then unaffected when the full raw path is switched on.

**Why this boundary.** The real aircraft-to-ground handover is the downloaded recorder/PMD file (GAO-20-316; GE DAS; IRIG Ch10 §10.3.5). Standardising there means the downstream PdM never depends on simulator internals. The decoding layer — where real programmes fail on metadata (BEA, ALIS) — is exercised and testable. Replay, idempotency and late data behave as they would with real downloads.

**Why not a single layer:**
- Option 5 alone hides decoding, metadata and time-alignment problems. It would force a data-layer redesign when raw sources appear.
- Option 3 alone has no file/transport or metadata container.
- Option 1 is unjustified effort for most parameters.
- Ch10 is a surrogate, not a claim about any candidate's operational recorder. If the platform choice changes, only the dictionary/ICD and adapters change.

**Alternatives held open:**
- An ARINC 717-style frame adapter: a civil-style FDR/QAR surrogate, with a 12-bit-word DFL (BEA).
- An AFDX/Ethernet adapter (Ch11 Ethernet F1) for Gripen E or F-35-like architectures.
- MQTT/Sparkplug or DDS transports in place of Kafka.
- XidML instead of or alongside TMATS for the dictionary export.

**Suggested phasing :**
- **Phase 1:** CIR + dictionary + Adapter C schema via the fast path + Adapter D events, with Kafka and Parquet.
- **Phase 2:** Adapters A + B, with round-trip tests (CIR → Ch10 → decode → compare to CIR within quantisation) using pyChapter10/irig106lib as independent parsers, plus conformance checks against the public sample files.
- **Phase 3:** live Ch10-over-UDP streaming; optional Ch7/ARINC 717 adapters.

### (d) Open questions and gaps
- **Search budget exhausted** (shared 200-search limit) and **DTIC unavailable**. These items need follow-up searching: F/A-18 MSDRS and FIRAMS/DFIRS; Navy SAFE/structural processing; USAF CEMS data flow; F-16 ground/debrief station products; Tejas recorder, HUMS and USMS architecture (DRDO Defence Science Journal papers); Gripen avionics papers (FOI/Saab); Su-30MKI bus standard and recorders; F-16 MMC bus count (only an uncertain Scribd source).
- Fighter-specific 1553 schedules and rates; EGI/ADC/FADEC output rates; FADEC cross-channel data link.
- Fighter recorder capacities, record durations, exceedance snapshot window lengths, download durations.
- EUROCAE ED-112A parameter list (paywalled); ARINC 429 label/rate tables and SAE AS15532A word formats (paywalled); ARINC 767 and ARINC 647A (FRED) not verified.
- Civil analogues (Boeing AHM, Airbus Skywise): primary pages not reachable (404) and searches exhausted.
- iNET/TmNS MDL (IRIG 106 Ch23) and XidML schema not reviewed in detail.
- Whether any candidate's operational recorders use IRIG 106 Ch10: no evidence found. Treat Ch10 as a surrogate.
- Cross-links: platform selection (bus and recorder choice per candidate); engine monitoring (IECMS, EDU, CEMS, FADEC data); datasets (public validation data); sensor residual texture (noise and quantisation at CIR); faults/degradation (BIT codes, SSM/NCD behaviour); validation/calibration (calibration records, dictionary limits); maintenance records (IMDS/AFTO 781/EEL analogues, IAF systems); modelling methodology; flight profiles (drive `t_true` event timing and sortie manifests).

### (e) Ranked list of most valuable sources
1. **IRIG 106-15 Chapter 10, Digital Recording Standard** (packet header, 1553/429/analog/discrete/time/event packets, streaming, download). Primary, byte-level. https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter10.pdf?api=v2
2. **IRIG 106-22 Chapter 11 (packet formats) and the 106-23 TOC** (current data types, ARINC-664/Ethernet, edition structure). https://www.trmc.osd.mil/wiki/download/attachments/240256873/chapter11.pdf?api=v2 ; https://www.trmc.osd.mil/wiki/download/attachments/168165620/106-23_Cover_TOC_Changes_Preface.pdf?api=v2
3. **IRIG 106 Chapter 9 (TMATS)**: the metadata model (B and C groups, events). https://www.trmc.osd.mil/wiki/download/attachments/113019518/chapter9.pdf?api=v2
4. **GAO-20-316 (ALIS)**: an authoritative description of a modern fighter's aircraft-to-fleet data flow and its data-integrity failures. https://www.gao.gov/products/gao-20-316
5. **RCC 123-16 Ch10 Programmers' Handbook**: time interpretation and practical parsing. https://www.irig106.org/docs/rcc/123-16_IRIG_106_Chapter10_Programmers_Handbook.pdf
6. **Alta MIL-STD-1553 Tutorial & Reference** and **MIL-STD-1553 Review & Rationale (MIL-HDBK-1553A §II)**: word, message, timing, mode-code, data-word and bandwidth rules. https://www.altadt.com/wp-content/uploads/dlm_uploads/2013/11/Alta-MIL-STD-1553-Tutorial-and-Reference-RevA.pdf ; https://www.milstd1553.com/wp-content/uploads/2012/12/MIL-STD-1553B.pdf
7. **NASA TM-84899 (AFTI/F-16)**: F-16 A-MUX/D-MUX, BC roles, FTI split (hardwired vs bus words), ground calibration/lineup metadata. https://ntrs.nasa.gov/api/citations/19830004825/downloads/19830004825.pdf
8. **GE DAS datasheet**: F-16 CSFDR replacement interfaces, functions and download method. https://www.geaerospace.com/sites/default/files/2022-02/DAS-Datasheet.pdf
9. **USAF AIB F-16C 90-0755**: CSFDR usage, EOT tracking, IMDS/AFTO 781, recorder/maintenance acronyms. https://www.f-16.net/downloads/F-16-AIB-Reports/90-0755.pdf
10. **BEA FDR Read-Out Study (2005)**: frame layout/DFL model, EU conversion example, metadata failure evidence. https://bea.aero/uploads/tx_scalaetudessecurite/use.of.fdr_01.pdf
11. **pyChapter10 / irig106lib / c10-tools** (code plus public sample `.c10` files). https://github.com/atac/pyChapter10 ; https://github.com/bbaggerman/irig106lib ; https://github.com/atac/c10-tools
12. **IRIG 106 Ch4, Ch7, Ch8**: PCM frames, packet downlink, total bus capture. https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter4.pdf?api=v2 ; https://www.trmc.osd.mil/wiki/download/attachments/113019632/Chapter7.pdf?api=v2 ; https://www.trmc.osd.mil/wiki/download/attachments/113019632/chapter8.pdf?api=v2
13. **DDC white paper on Ch10 for 1553**: time-stamp accuracy; Ch10 use in HUMS and mission recorders. https://www.ddc-web.com/resources/FileManager/dbi/Whitepapers/IRIG106.pdf
14. **14 CFR 121 Appendix M**: public sampling-interval anchors. https://www.law.cornell.edu/cfr/text/14/appendix-M_to_part_121
15. **Kafka design docs, Flink time concepts, Avro spec, MIMOSA OSA-CBM**: ingestion and CBM architecture. https://github.com/apache/kafka/blob/trunk/docs/design/design.md ; https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/ ; https://avro.apache.org/docs/1.11.1/specification/ ; https://www.mimosa.org/mimosa-osa-cbm/
16. **Wikipedia platform pages** (secondary; used only for public-level bus, recorder and HUMS facts): Gripen, HAL Tejas, Su-30MKI, F/A-18, F-35, F404, RM12, MIL-STD-1553, ARINC 429, AFDX, MIL-STD-1760, IRIG timecode, XidML, ACARS, Flight recorder.
