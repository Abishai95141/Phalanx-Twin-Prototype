# Public aerospace datasets that can teach a virtual-fighter telemetry generator (Project Phalanx)

Scope: a catalogue of real (and the best simulated) aerospace datasets. For each one it records what it can and cannot teach the Phalanx data-generation and streaming layer: sensor texture, flight-phase statistics, cross-sensor physics, degradation trajectories, maintenance linkage, and real-vs-synthetic testing.

**Evidence tags**
- [DIRECT]: checked against the dataset's own page, documentation or file metadata in this session.
- [TRANSFER: platform]: my reasoning about how far the evidence carries to a fighter, with limits stated.
- [ASSUMPTION]: not verified.

**How things were checked (2026-10-13)**
- WebSearch was unavailable for this whole session. The shared per-turn budget had already been used by parallel agents, and the first query was refused. So discovery came only from known URLs, links followed from fetched pages, catalogue APIs (Zenodo, Figshare, DataCite, Crossref, Semantic Scholar, NTRS citation-by-ID) and HTTP HEAD requests.
- Effect on coverage: the broad Kaggle, Mendeley, IEEE DataPort and Harvard Dataverse sweep is incomplete, and TU Delft Citation data could not be located. Both are listed under Gaps.
- No dataset contents were downloaded. Sizes come from HTTP `Content-Length`. For NASA DASHlink, only zip central directories (file names and sizes) were read, via HTTP range requests. The PX4 public-log metadata index (`dbinfo.json`, 32.6 MB gzip, no logs) was parsed in a scratch directory.

**Documentation saved** under `/Users/abishaikc/Phalanx/research_sources/datasets/`:
- `DASHlink_full_data_documentation.pdf`
- `DASHlink_Sample_Flight_Data_FAQ_2.doc`
- `PHM2021_Data_Challenge.pdf`
- `NGAFID_maintenance_dataset_arXiv2210.07317.pdf`
- `HUMS2023_Data_Challenge_dataset_description_v1.1.1.pdf`
- `HUMS2025_Data_Challenge_Dataset_Description.pdf`
- `FLEA_Data_FAQ.pdf`
- `ESA-ADB_arXiv2406.17826.pdf`
- `Saxena2008_CMAPSS_DamagePropagation.pdf`
- `AriasChao2020_FusingPhysicsDL_arXiv2003.00732.pdf`
- `Matthews2013_JAIS_DASHlink.pdf`
- `Das2010_MKAD_KDD.pdf`

**Cross-links to parallel notes** (same folder):
- `sensor_residual_texture.md`: noise and quantisation models.
- `faults_and_degradation.md`: C-MAPSS health-parameter tables.
- `flight_profiles_and_usage.md`: fighter sortie and usage statistics.
- `maintenance_records_and_events.md`: SDRS and ASRS schemas.
- `data_pathway_and_formats.md`: bus and recorder formats.
- `validation_and_calibration.md`: discriminator protocol.
- `candidate_airframe_modelling_data.md`: NASA fighter reports, AeroBench and JSBSim.
- `indian_fleet_platform_relevance.md`

---

## Q1. Dataset-by-dataset catalogue: owner, access, structure, labels, and what each can and cannot teach the simulator

### Takeaway
No public raw telemetry from a fighter exists in any dataset found. The best real airframe-level source is NASA DASHlink "Sample Flight Data":
- 35 tails of one four-engine regional-jet type.
- 186 parameters per flight, each with its own sampling rate.
- About 245 GB compressed, an estimated ~1.8×10⁵ flights.

The best maintenance-linked real flight data is NGAFID plus MaintNet (Cessna 172, 1 Hz). The best simulated degradation source is N-CMAPSS, whose real flight conditions were taken from DASHlink Tail 687 (as stated for its 2020 precursor study).

Each other family teaches one narrow layer and should be used only for that layer:
- UAV logs (PX4, ALFA, RflyMAD): timestamping, dropouts and fault-labelling mechanics.
- Helicopter HUMS (Airbus, DSTG): vibration texture.
- Spacecraft telemetry (ESA-AD, SMAP/MSL): irregular sampling, gaps and rare-event semantics.

### Cited Findings

#### 1.1 NASA DASHlink "Sample Flight Data" (project 85): regional-jet fleet flight-recorder data

**Owner and contents**
- Owner is NASA Ames (shared by Bryan Matthews). The data was recorded on one type of regional jet in commercial service over three years, de-identified, and is not part of any airline FOQA programme [DIRECT] — [DASHlink project 85](https://c3.ndc.nasa.gov/dashlink/projects/85/)
- Each per-flight MATLAB file holds 186 parameters. Each parameter is a structure with the sensor recordings, sampling rate, units, description and parameter ID [DIRECT] — [data.gov: Flight Data For Tail 652](https://catalog.data.gov/dataset/flight-data-for-tail-652)
- The project has 37 resources: 35 tail datasets (Tails 652–687; no Tail 679 exists), the curated 4-class set, and an FAQ [DIRECT] — [project resources list](https://c3.ndc.nasa.gov/dashlink/projects/85/resources/) and pages [2](https://c3.ndc.nasa.gov/dashlink/projects/85/resources/?page=2) through [5](https://c3.ndc.nasa.gov/dashlink/projects/85/resources/?page=5)
- Data.gov lists the data as public access with "no license information" and last modified 2025-03-31 [DIRECT] — [data.gov](https://catalog.data.gov/dataset/flight-data-for-tail-652)

**Size and file structure (HEAD requests, 2026-10-13)**
- 310 zip archives, ~245.4 GB compressed. Each tail has 7–11 archives of ~0.84 GB (5.6–8.9 GB per tail). Zip timestamps are 29 Jan 2014 [DIRECT] — e.g. [Tail_652_1.zip](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/Tail_652_1.zip)
- Zip central directories (file names only) show one `.mat` per flight, named `<tail><YYYYMMDDhhmm>.mat`, for example `652200101092009.mat`. So each file carries tail ID and start date/time. Sizes are 0.04–3.2 MB uncompressed, median ≈1.3 MB [DIRECT, from the Tail_652_1 zip directory] — [Tail_652_1.zip](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/Tail_652_1.zip)
- Flights per archive: 558–676 in 21 full-size archives sampled [DIRECT]. From that, total ≈ 1.8×10⁵ flights [ASSUMPTION: extrapolated, not a full count].
- Tails 652, 653 and 654 hold ~4,195–4,459 flights each, dated Jan/Mar 2001 to mid-2003 [DIRECT, from zip directories]

**Quirks**
- The last archives of several tails contain files dated Oct 2009–2010. Examples: Tail_670_10 has 626 files from 2004 plus 95 from 2009–10; Tail_687_9 has 307 plus 89. This is either later data or recorder-clock errors; unresolved [DIRECT observation, cause unknown] — [Tail_670_10.zip](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/Tail_670_10.zip)
- The aircraft has **four engines**. Fan speeds are recorded per engine as N2.1–N2.4. N1 Command is a thrust-demand surrogate sent to all four engines, the per-engine command is not recorded, and N1CO flags an override [DIRECT] — [DASHlink Flight Data FAQ (Mar 2014)](https://c3.ndc.nasa.gov/dashlink/static/media/other/Sample_Flight_Data_FAQ_2.doc)
- Flight-phase parameter PH is enumerated: 0 Unknown, 1 Preflight, 2 Taxi, 3 Takeoff, 4 Climb, 5 Cruise, 6 Approach, 7 Rollout [DIRECT] — [FAQ](https://c3.ndc.nasa.gov/dashlink/static/media/other/Sample_Flight_Data_FAQ_2.doc)
- Discrete-parameter oddities [DIRECT] — [FAQ](https://c3.ndc.nasa.gov/dashlink/static/media/other/Sample_Flight_Data_FAQ_2.doc):
  - WOW = 1 means airborne, and LGDN shows 0 when the gear is down. These are inverted circuit states.
  - Enumerations for LMOD, VMODE, TMODE and MRK were "under investigation".
  - DWPT units are unconfirmed.
  - A `_1` filename suffix is an anonymisation artefact.
- Per-parameter sampling rate is stored in each file [DIRECT]. The commonly quoted range of 0.25–16 Hz was **not** verified from primary documentation this session. Confirm it by reading the `Rate` field of one file [ASSUMPTION].
- The airframe type is not disclosed by NASA [DIRECT]. Four engines on a "regional jet" fits a BAe 146/Avro RJ-class aircraft [ASSUMPTION].

**What real flight-recorder data looks like, from NASA's own FOQA work (not necessarily this public set)**
- Records are "contaminated with missing data, out-of-bounds variables, noisy recordings, amplitude spikes" from sensor or recording faults. Typical flights have 5000–6000 samples at about 1 Hz and ~350 parameters [DIRECT] — [Matthews et al. 2013, JAIS](https://c3.ndc.nasa.gov/dashlink/static/media/publication/JAIS_matthews_2013.pdf)
- In one regional-carrier fleet of ~3,500 flights (160 parameters at 1 Hz), a conservative data-quality filter kept only ~2,500 "cleaned" flights [DIRECT] — [Das et al. 2010, KDD (MKAD)](https://c3.ndc.nasa.gov/dashlink/static/media/publication/fp723-Das.pdf)

**Use by other datasets**
- Real flight conditions for the N-CMAPSS precursor study came from "DASHlink – Flight Data For Tail 687" [DIRECT] — [Arias Chao et al. 2020, arXiv:2003.00732, ref. 27](https://arxiv.org/abs/2003.00732)
- The PHM 2025 challenge shows a DASHlink Tail_687 flight (`687200104141245.mat`) as its reference flight profile [DIRECT] — [PHM 2025 challenge](https://data.phmsociety.org/phm-north-america-2025-conference-data-challenge/)

**Can teach** [TRANSFER: civil 4-engine jet → fighter]
- Recorder texture: multi-rate parameters, discrete/enumerated words with odd polarity, recorder spikes and dropouts, de-identification artefacts.
- Phase-segmented statistics, using PH plus autopilot modes.
- Cross-sensor physics among air data, attitude, control surfaces, flaps and gear, and multi-engine spool speeds.
- Fleet-level tail-to-tail variation: 35 tails of one type.
- Per-engine spread under a common command, from N2.1–N2.4. This is analogous to Su-30MKI twin-engine asymmetry; for single-engine Tejas only the method carries over.

**Cannot teach**
- Fighter manoeuvre envelope: high g, high AoA, afterburner transitions, supersonic flight.
- Military-engine parameters (nozzle area, AB fuel, FTIT/EGT limits).
- Maintenance labels: none are included.
- Fault ground truth.
- The aircraft's own 1553-bus or HUMS formats.

#### 1.2 DASHlink "Curated 4 Class Anomaly Detection Data Set" (resource 1018)
- 160-second final-approach windows for ~99K flights, taken as each crosses 1,000 ft before touchdown. Shared by Matthews, updated 2022-12-22 [DIRECT] — [DASHlink resource 1018](https://c3.ndc.nasa.gov/dashlink/resources/1018/)
- Files: `DASHlink_full_fourclass_raw_comp.npz` (1.6 GB) and a metadata CSV (3.9 MB). Licence "N/A" [DIRECT] — [resource 1018](https://c3.ndc.nasa.gov/dashlink/resources/1018/)
- Each instance is 160 s × 20 variables. Classes: Nominal 0, Speed High 1, Path High 2, Flaps Late Setting 3 [DIRECT] — [documentation PDF (POC Milad Memarzadeh)](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/DASHlink_full_data_documentation.pdf)
- The 20 variables are aileron L/R, corrected AoA, baro altitude, CAS, selected course, drift angle, left elevator, T.E. flap, glideslope deviation, selected heading, localizer deviation, core speed average, total pressure, pitch, roll, rudder, true heading, vertical acceleration and wind speed [DIRECT] — [documentation PDF](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/DASHlink_full_data_documentation.pdf)
- "Core speed avg" is described as the average over "the four engines" [DIRECT] — [documentation PDF](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/DASHlink_full_data_documentation.pdf)
- **Can teach:** approach-phase operational anomaly classes; a ready benchmark for discriminating approach behaviour. **Cannot teach:** native rates. The time axis is in seconds, so multi-rate texture is lost to 1 Hz resampling [DIRECT on 160 s × 20; texture loss is my inference].

#### 1.3 Other relevant DASHlink datasets (catalogue crawl of all 760 resources)

**Maintenance Action Recommendation (MAR), resources 842/843** — [DASHlink 842](https://c3.ndc.nasa.gov/dashlink/resources/842/)
- Cases created automatically or by engineers. Each "problem" maps to a maintenance action. "Nuisance" cases are auto-generated cases that engineers judged not worth raising. Events carry an event code plus a snapshot of all onboard parameters [DIRECT]
- Data comes from "an industrial piece of equipment"; the domain is withheld for proprietary reasons [DIRECT]
- Files: Train/Test Case→Problem, Nuisance and Case→Events-and-Parameters CSVs. The event files are 653.7 MB and 960.1 MB, and the page's size labels are inconsistent [DIRECT]
- Contributors are D. Garvey and N. Eklund (GE); listed under "PHM Data Challenges" [DIRECT]
- **Can teach:** structure linking fault codes, parameter snapshots and confirmed maintenance actions, including false-alarm (nuisance) handling. **Cannot teach:** aviation semantics [TRANSFER: unknown industrial asset].

**FLEA (Flyable Electro-Mechanical Actuator)** — [FLEA FAQ](https://c3.ndc.nasa.gov/dashlink/resources/505/), e.g. [2010_09_02 Lab](https://c3.ndc.nasa.gov/dashlink/resources/908/)
- 13 laboratory sets: nominal, ballscrew jam (including ±40 lb loads), spall and dead position sensor. 57 MB–1.2 GB each, ~5.6 GB total [DIRECT]
- Channels: actuator X (fault-injected), Y (nominal) and Z (load). Measured: 3-axis nut accelerometers, nut and motor temperatures, positions, load cell, motor voltages, currents and torques, PWM duty cycles [DIRECT] — [FLEA Data FAQ PDF](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/FLEA_Data_FAQ.pdf)
- Rates: 20–50 kHz accelerometers, usually 1 kHz for the rest. Scenarios last 30 s or 2 min. Formats are .data (text), .tdms and .bin, and channel sets change between sessions [DIRECT] — [FLEA Data FAQ PDF](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/FLEA_Data_FAQ.pdf)
- **Can teach:** EMA degradation texture and current–torque–position–temperature coupling [TRANSFER: flight-control/utility actuators; fighter primary controls are mostly hydraulic].

**ADAPT electrical power system** — [DASHlink 143](https://c3.ndc.nasa.gov/dashlink/resources/143/)
- Lab EPS "simulating the functions of a typical aerospace vehicle power system". 128 sensors at 2 Hz, runs of about 5 min [DIRECT]
- Faults were injected physically (disconnects, breakers) or in software through an "Antagonist" that alters commands and sensor data [DIRECT]
- More data in the DXC'09/'10/'13 competitions, e.g. [DXC'10 competition data](https://c3.ndc.nasa.gov/dashlink/resources/250/) (10–23 MB zips) [DIRECT]
- **Can teach:** electrical-bus fault signatures and sensor-fault injection patterns.

**Disk Defect Data** — [DASHlink 314](https://c3.ndc.nasa.gov/dashlink/resources/314/)
- Physical spin-rig simulator of engine disks. Blade-tip clearance for 32 blades sampled once per revolution, ~3 min per run, medium and large disk cracks. 15.6 MB [DIRECT]
- **Can teach:** rotor-crack signatures in once-per-rev clearance data [TRANSFER: engine rotor health; fighter EMS rarely records tip clearance].

**Other related resources**
- Northern California TRACON radar tracks (Jan–Mar 2006, SFO noise office) for trajectory clustering [DIRECT] — [DASHlink 132](https://c3.ndc.nasa.gov/dashlink/resources/132/)
- ASRS fuel-related GA set (resource page with no files) — [DASHlink 905](https://c3.ndc.nasa.gov/dashlink/resources/905/)
- MKAD synthetic data, a known-synthetic counterpart for discriminator sanity checks [ASSUMPTION: catalogue entry seen in a search listing, not fetched] — [data.gov catalogue entry](https://catalog-beta.data.gov/dataset/mkad-synthetic-data)
- PHM 2009 gearbox: 560 runs, 401.5 MB [DIRECT] — [DASHlink 997](https://c3.ndc.nasa.gov/dashlink/resources/997/)
- PHM 2019 lap-joint Lamb-wave data: 1.8 MB [DIRECT] — [DASHlink 1014](https://c3.ndc.nasa.gov/dashlink/resources/1014/)

#### 1.4 NASA C-MAPSS "Turbofan Engine Degradation Simulation" (2008) and the PHM08 challenge
- Simulated with C-MAPSS: four sets under different operating-condition and fault-mode combinations. Zip is 12.4 MB [DIRECT] — [NASA PCoE repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/); [S3 zip](https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip)
- PHM08 challenge data is "currently unavailable" from NASA (contact C. Teubert) [DIRECT] — [PCoE repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)

**How the data was generated** [DIRECT] — [Saxena, Goebel, Simon & Eklund 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf)
- One snapshot per flight at cruise.
- Exponential flow/efficiency degradation from a random initial wear of 0.99–1.
- Process noise from mixture distributions.
- Measurement noise added "since there was no real data available to characterize true noise levels"; the authors used "simplistic normal noise distributions".
- Six flight conditions: altitude 0–42 kft, Mach 0–0.84, TRA 20–100.

**Structure as usually reported** [ASSUMPTION: widely reported from the zip readme, not re-read]
- FD001–FD004 with 100/260/100/249 training units.
- 3 operational settings and 21 sensors.

**Can teach**
- Health-index and margin-based end-of-life logic.
- The direction of sensor shifts under HPC/HPT/fan/LPC flow and efficiency loss.
- A negative control for the real-vs-synthetic discriminator.

**Cannot teach** [TRANSFER: generic large commercial turbofan → F404/RM12/AL-31FP; the "90k-lbf class" label often attached to C-MAPSS is ASSUMPTION, not verified here]
- Sensor texture.
- Within-flight dynamics: there is only one point per cycle.
- Real noise.
- Military cycles: afterburner, throttle transients.

#### 1.5 N-CMAPSS ("Turbofan Engine Degradation Simulation-2") and the PHM 2021 challenge

**Generation and real/simulated split**
- Run-to-failure trajectories for a small fleet "under realistic flight conditions", built with C-MAPSS by NASA, ETH Zurich and PARC. The zip is **15.76 GB** [DIRECT] — [PCoE repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/); [S3 zip (HEAD)](https://phm-datasets.s3.amazonaws.com/NASA/17.+Turbofan+Engine+Degradation+Simulation+Data+Set+2.zip)
- Two added fidelity levels: (1) "real flight conditions as recorded on board of a commercial jet"; (2) degradation tied to operation history. The data also provides health and fault class, and the paper is CC-BY [DIRECT] — [Arias Chao et al. 2021, *Data* 6(1):5, abstract](https://api.semanticscholar.org/graph/v1/paper/DOI:10.3390/data6010005?fields=abstract) (the MDPI full text returned HTTP 403 here)
- Engine is a high-bypass twin-spool turbofan. All rotating components (fan, LPC, HPC, HPT, LPT) can lose flow and efficiency [DIRECT] — [PHM 2021 challenge PDF](https://data.phmsociety.org/wp-content/uploads/sites/9/2021/08/2021_Data_Challenge.pdf)
- Units fall into flight classes 1 (1–3 h), 2 (3–5 h) and 3 (>5 h). Flight cycles cover **only climb, cruise and descent with alt > 10,000 ft** [DIRECT] — [same PDF](https://data.phmsociety.org/wp-content/uploads/sites/9/2021/08/2021_Data_Challenge.pdf)
- **Simulated vs real:** the scenario descriptors w (altitude, Mach, TRA, T2) come from real flight traces. The measurements x_s come from the C-MAPSS model with synthetic noise. In the 2020 precursor the real traces came from DASHlink Tail 687 [DIRECT for the precursor] — [arXiv:2003.00732](https://arxiv.org/abs/2003.00732). That the published N-CMAPSS uses the same source is [ASSUMPTION].

**Variables**
- Challenge files: w = 4 (alt, Mach, TRA, T2). x_s = 14 (Wf, Nf, Nc, T24, T30, T48, T50, P15, P2, P21, P24, Ps30, P40, P50). Auxiliary = unit, cycle, flight class and health state hs. RUL is in cycles [DIRECT] — [PHM 2021 PDF](https://data.phmsociety.org/wp-content/uploads/sites/9/2021/08/2021_Data_Challenge.pdf)
- The 2020 precursor also exposed 11 virtual sensors (P45, W21, W22, W25, W31, W32, W48, W50, SmFan, SmLPC, SmHPC) and calibration/health parameters. It was sampled at 0.1 Hz [DIRECT] — [arXiv:2003.00732, Tables 2–4](https://arxiv.org/abs/2003.00732)
- The public N-CMAPSS sampling rate (commonly quoted as 1 Hz) was not verified here [ASSUMPTION].

**Sub-datasets and challenge**
- DS01 (10 units, HPT efficiency), DS03 (15), DS04 (10, fan), DS05 (10, HPC), DS06 (10, LPC+HPC), DS07 (10, LPT), DS08a/c/d (15/10/10, all modes). DS02 is in the repository but excluded from the challenge. Format is HDF5 [DIRECT] — [PHM 2021 PDF](https://data.phmsociety.org/wp-content/uploads/sites/9/2021/08/2021_Data_Challenge.pdf)
- The 2021 challenge had a 90-unit development set and a 2.94 GB validation `.h5` [DIRECT] — [challenge page](https://data.phmsociety.org/2021-phm-conference-data-challenge/); [validation file (HEAD)](https://phm-datasets.s3.amazonaws.com/Data_Challenge_2021_N-CMAPSS_DS_Validation_f.h5)

**Can teach**
- Physically consistent cross-sensor relations of a turbofan along real mission profiles.
- Non-linear (normal → abnormal) degradation onset.
- Flight-class-dependent damage.
- Degradation and health-state labels.

**Cannot teach** [TRANSFER: commercial high-bypass → low-bypass afterburning F404/RM12/AL-31FP]
- Real noise, quantisation or dropouts.
- Taxi, takeoff, landing or below-10k-ft regimes.
- Afterburner, nozzle or variable-geometry military schedules.

#### 1.6 Other PHM Society challenges relevant to aerospace (2008 → 2026)
The repository lists challenges for 2019, 2021–2026, PHMAP 2023 and PHM Europe 2026, plus a NASA PCoE mirror [DIRECT] — [PHM Society data repository](https://data.phmsociety.org/)

**2024 (NA): helicopter turbine engines** [DIRECT] — [PHM 2024](https://data.phmsociety.org/phm2024-conference-data-challenge/)
- Seven assets of the same make and model, 4 for training and 3 for test/validation.
- Channels: OAT, mean gas temperature, power available, IAS, net power, compressor speed, and measured vs target torque.
- Targets: health state 0/1 plus a torque-margin distribution.
- Training rows are shuffled with asset IDs removed.
- Zips: 22.6 MB training and 0.36 MB test (HEAD).
- Real vs simulated is not stated [DIRECT absence].

**2025 (NA): commercial engine maintenance-event prediction** [DIRECT] — [PHM 2025](https://data.phmsociety.org/phm-north-america-2025-conference-data-challenge/)
- Eight engines (ESN101–108), up to 15,000 points over 2,001 flights.
- Up to 8 snapshots per flight (takeoff, climb, cruise…).
- Metadata includes cumulative maintenance counts. 16 sensed variables, 14 primary.
- Targets: cycles to HPT shop visit (≤~6,000), HPC shop visit (≤~12,500) and HPC water-wash (≤~1,250).
- Zips: 7.8 MB training and 6.1 MB test.
- Data origin is not stated. The page cites DASHlink and NASA AGTF30/T-MATS as background, so the data is likely simulated [ASSUMPTION].
- **Can teach:** sawtooth degradation with maintenance resets (water-wash recovery), and snapshot-based engine-condition-monitoring formats [TRANSFER: commercial engine trend monitoring → fighter EMS trend data].

**2023 (NA): gearbox** [DIRECT] — [PHM 2023](https://data.phmsociety.org/phm2023-conference-data-challenge/)
- Gearbox degradation at 15 speeds × 6 torques for training; 11 health levels at test.
- Teaches generalisation to unseen operating conditions.

**PHMAP 2023: spacecraft propulsion (JAXA)** [DIRECT] — [PHMAP 2023](https://data.phmsociety.org/phmap-2023-data-challenge/)
- Simulator-generated data covering bubble anomalies, solenoid-valve faults and unknown faults.

**2026 (NA): gear spall** [DIRECT] — [PHM 2026](https://data.phmsociety.org/phm-north-america-2026-conference-data-challenge/)
- Gear-tooth spall damage estimated from inexpensive sensors, with imaging available only for training.

**PHM Europe 2026** [DIRECT] — [PHM Europe 2026](https://data.phmsociety.org/phm-europe-2026-conference-data-challenge/)
- A servomotor door test bench; not aerospace.

**Other years**
- 2022: rock-drill pressure data [DIRECT] — [PHM 2022](https://data.phmsociety.org/2022-phm-conference-data-challenge/)
- 2019: aluminium lap-joint Lamb waves (structural crack growth); see 1.3.
- 2018: ion-mill etch [DIRECT] — [DASHlink 1009](https://c3.ndc.nasa.gov/dashlink/resources/1009/)
- 2014: asset-health scoring for "industrial remote monitoring and diagnostics". The chairs were D. Garvey and R. Wigny (pwc.ca) [DIRECT] — [PHM 2014 data challenge page](https://phmsociety.org/conference/annual-conference-of-the-phm-society/annual-conference-of-the-prognostics-and-health-management-society-2013/data-challenge/) (this URL path says 2013 but the page breadcrumb says 2014). Whether the data is from Pratt & Whitney Canada engines is [ASSUMPTION: unverified].
- 2010: milling; 2011: anemometers [DIRECT] — [PCoE repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)

#### 1.7 NGAFID Aviation Maintenance Dataset (Yang & Desell, arXiv:2210.07317, Oct 2022)

**NGAFID platform**
- NGAFID is part of FAA-funded ASIAS. Pilots and operators upload on-board avionics data (e.g. G1000) voluntarily, and "the FAA cannot see your data" [DIRECT] — [ngafid.org](https://ngafid.org/)
- The full database holds more than 900,000 hours from 780,000+ flights across 12 aircraft types from 65 fleets. Access to the full database is not public [DIRECT on counts] — [arXiv:2210.07317 §3.1](https://arxiv.org/abs/2210.07317)

**Released maintenance dataset** [DIRECT] — [arXiv PDF](https://arxiv.org/pdf/2210.07317)
- 31,177 flight hours across 28,935 flights, all Cessna 172 from one flight school.
- Linked to 2,111 unplanned maintenance events in 36 issue types.
- The 5 flights before and after each maintenance event are included.
- 23 channels at 1 Hz (>100 M rows): volt1/2, amp1/2, FQtyL/R, E1 FFlow/OilT/OilP/RPM, CHT1–4, EGT1–4, OAT, IAS, VSpd, NormAc, AltMSL.

**Labels**
- Labels are derived from MaintNet logbook records clustered by experts. The largest classes are intake gasket leak/damage (4,244 flights) and rocker cover (2,157) [DIRECT] — [arXiv appendix](https://arxiv.org/pdf/2210.07317)
- The benchmark subset has 19 classes, 5,844 post-maintenance flights and 5,602 pre-maintenance flights [DIRECT] — [arXiv](https://arxiv.org/pdf/2210.07317)

**Raw vs processed and privacy** [DIRECT] — [arXiv §3.3–3.5](https://arxiv.org/pdf/2210.07317)
- "Full dataset is provided without any preprocessing". About 1% of points are NaN, from sensor initialisation, in-flight sensor failure or recorder failure.
- Values are unscaled; only the benchmark subset is MinMax-scaled.
- Serial number, flight date, latitude/longitude and maintenance text are removed.

**Files and licence**
- Zenodo has `all_flight.tar.gz` (4.29 GB) and `2days.tar.gz` (1.13 GB), CC-BY-4.0. The paper instead states GNU GPL v3.0, so the licence statements conflict [DIRECT] — [Zenodo record 6624956](https://doi.org/10.5281/zenodo.6624956); [arXiv §1.1](https://arxiv.org/pdf/2210.07317)
- Format: Dask Parquet plus a `flight_header.csv`. Partitions do not guarantee timestep order [DIRECT] — [GitHub NGAFIDDATASET](https://github.com/hyang0129/NGAFIDDATASET)
- Also mirrored on [Kaggle](https://www.kaggle.com/datasets/hooong/aviation-maintenance-dataset-from-the-ngafid) (HTTP 200).

**Benchmarks and follow-on work**
- ConvMHSA reached 76.1% binary and 56.3% multiclass accuracy; MiniRocket 59.8% / 50.4% [DIRECT] — [arXiv Table 2](https://arxiv.org/pdf/2210.07317)
- A 2024 phase-of-flight paper uses per-second GA data [DIRECT] — [arXiv:2402.11185 (via S2 citation graph)](https://arxiv.org/abs/2402.11185)
- A "GATS" GA flight-safety time-series dataset cites NGAFID. Its metadata could not be resolved [DIRECT on existence in the citation graph].

**Can teach**
- Real 1 Hz recorder texture: NaN dropouts [DIRECT], and probably coarse engine-monitor quantisation [ASSUMPTION; check after download].
- Maintenance-event linkage and pre/post-maintenance distribution shift.
- Pilot-induced variance swamping fault signal. The authors stress this: "a significant portion of variance … is explained by pilot action".

**Cannot teach** [TRANSFER: GA piston → fighter turbofan]
- Turbine-engine parameters.
- High-rate dynamics.
- Calendar or tail effects, because dates and tails were removed.

#### 1.8 MaintNet aviation logbook (RIT)
- Library of logbook datasets (aviation, automotive, facility) with abbreviation, morphosyntactic and term-bank resources [DIRECT] — [Akhbardeh, Desell & Zampieri, COLING 2020 demo](https://aclanthology.org/2020.coling-demos.2/)
- Aviation logbook: 6,169 de-identified problem/action records from 2012–2017, as a CSV. Source listed as "NGAFID and Open Socrata" [DIRECT] — [MaintNet datasets page](https://people.rit.edu/fa3019/MaintNet/datasets.html); [aircraft dataset page](https://people.rit.edu/fa3019/technical/aircraft.html) (file `data/maintnet_aviation_dataset_deidentified.csv`)
- The authors will not answer data requests. Licence terms are referred to but not stated [DIRECT] — [datasets page](https://people.rit.edu/fa3019/MaintNet/datasets.html)
- **Can teach:** real mechanic free-text style (abbreviations, misspellings) to generate realistic maintenance records and to train text-to-fault-code mapping. Cross-link: `maintenance_records_and_events.md`.

#### 1.9 CAFUC2 GA anomaly benchmark (Sci. Data 2026): real flights plus physics-based injected faults
- 120 real QAR sorties (~1 M points) from Civil Aviation Flight University of China. Aircraft: C172R/S and Cirrus SR20/SR20 G6 [DIRECT] — [PMC13570879](https://pmc.ncbi.nlm.nih.gov/articles/PMC13570879/)
- 22 channels at 1 Hz [DIRECT]:
  - Geospatial: lat, lon, AltMSL, AltGPS.
  - Kinematic: VSpd, pitch, roll, LatAc, NormAc, HDG, TRK.
  - Thermodynamic: fuel flow, oil temp, RPM, CHT1–4, EGT1–4.
- Four injected anomalies: throttle surge with EGT/CHT thermal lag, path deviation, cylinder misfire, and pitch excursion with coupled Nz/VSpd. Released as 120 normal plus 480 anomalous CSVs, CC BY 4.0 [DIRECT] — [Zenodo 19124264](https://zenodo.org/records/19124264); [code (MIT)](https://github.com/lnnnm/CAFUC2_code)
- Realism was checked visually and by t-SNE only. Course-deviation and misfire detection was near chance (AUC ≈ 0.5) [DIRECT] — [PMC13570879](https://pmc.ncbi.nlm.nih.gov/articles/PMC13570879/)
- **Can teach:** a template for fault injection into real traces, closely matching Phalanx's own approach; paired counterfactuals for discriminator tests. **Cannot teach:** fighter physics [TRANSFER: GA].

#### 1.10 Airbus Helicopter Accelerometer Dataset (ETH Zurich / Airbus SAS, 2020)
- Flight-test helicopter vibration from accelerometers at various positions and axes. 1024 Hz, cut into 1-minute sequences (61,440 samples) [DIRECT] — [DataCite record](https://api.datacite.org/dois/10.3929/ethz-b-000415151); [handle](http://hdl.handle.net/20.500.11850/415151)
- 1,677 normal training sequences and 594 validation sequences with an unknown share of anomalies (abnormal sensor behaviour). HDF5 (`dftrain`, `dfvalid`) plus CSV, 1.04 GB, CC BY-NC-SA 4.0 [DIRECT] — [DataCite](https://api.datacite.org/dois/10.3929/ethz-b-000415151)
- "All data has been multiplied by a factor … but no other normalization procedure was carried out" [DIRECT]
- That the CSV holds the validation ground truth is [ASSUMPTION]. The ETH landing page returned HTTP 500/429 here.
- **Can teach:** real high-rate vibration texture and sensor-failure signatures in flight-test instrumentation, which is the realistic failure class for validating instrumentation. **Cannot teach:** absolute levels, which are scaled, or fighter engine/accessory-gearbox spectra [TRANSFER: helicopter airframe → fighter AMAD/engine vibration pickups].

#### 1.11 DSTG (Australia) HUMS data challenges: Bell 206B-1 (OH-58) main rotor gearbox, Helicopter Transmission Test Facility

**HUMS2023: planet-gear rim crack**
- Seeded EDM notch with a crack propagating over load cycles 147–241. Gearbox runs 6000 rpm in, 344 rpm out [DIRECT] — [HUMS2023 description PDF](https://www.humsconference.com.au/HUMS2023/HUMS2023_Data_Challenge_dataset_description_v1.1.1.pdf)
- Load cycle: 50/75/100/125% for 2/2/2/24 min [DIRECT]
- Released data covers the last 60 cycles: 526 four-channel hunting-tooth synchronous averages at 125% load, 6.1 GB. Raw files exceed 84 MB each [DIRECT]
- Accelerometers: IP-1, RF-2, RL-3, RR-4 [DIRECT]
- Challenge terms: no third-party sharing; credit DSTG [DIRECT] — [T&C](https://www.humsconference.com.au/HUMS2023datachallenge/terms-conditions.html)
- A larger public release is "conditionally available to everyone" via DSTG. That page returned HTTP 403 here [DIRECT on the statement] — [HUMS2023 challenge page](https://www.humsconference.com.au/HUMS2023datachallenge/)

**HUMS2025: upper-casing fatigue crack**
- The crack appeared unexpectedly during a pinion spall test [DIRECT] — [HUMS2025 description PDF](https://www.humsconference.com.au/HUMS2025datachallenge/The%20HUMS2025%20Data%20Challenge%20Dataset%20Description.pdf)
- 86 load cycles (100/125/150/125%, 20 min each) [DIRECT]
- Released: 1,830 hunting-tooth SSA files (2.55 GB), plus 204 + 210 raw files at 100% and 125% load (5.38 + 5.66 GB), 13.6 GB in total. Raw files have 4 vibration channels plus a tachometer, 30 s at 65,573.77 Hz (NI-PXI, delta-sigma), with timestamped filenames [DIRECT]
- The full test generated ~156 GB of raw data, acquired every ~4 min [DIRECT]
- Registration is closed [DIRECT] — [HUMS2025 page](https://www.humsconference.com.au/HUMS2025datachallenge/)

**HUMS2027: naturally occurring planet-bearing inner-race spall (2004 endurance test, 80.21 h)**
- Channels: 6 (Tach1, RR-1, IP-2, Tach2, RF-3, RL-4) at 51,200 Hz, 15 s files, plus wear-debris mass (Fe_Cum_mg), oil temperature and test hours [DIRECT] — [HUMS2027 dataset page](https://www.humsconference.com.au/HUMS2027datachallenge/dataset.html)
- The dataset page lists 20 files (768,000 × 6), 323 MB [DIRECT] — [dataset page](https://www.humsconference.com.au/HUMS2027datachallenge/dataset.html)
- **Registration closes 31 Oct 2026.** Access is restricted with a personalised link and no sharing [DIRECT] — [access page](https://www.humsconference.com.au/HUMS2027datachallenge/download.html); [terms](https://www.humsconference.com.au/HUMS2027datachallenge/terms-conditions.html)

**Papers and use**
- Papers using HUMS2023 data include Sawalhi, Wang & Blunt (2024), *Sensors* 24:2593 [DIRECT citation in HUMS2025 doc] — [HUMS2025 PDF](https://www.humsconference.com.au/HUMS2025datachallenge/The%20HUMS2025%20Data%20Challenge%20Dataset%20Description.pdf)
- **Can teach:** real gearbox fault progression with wear-debris coupling (debris jump at 56.97 h; test stopped at 80.21 h) [DIRECT]. Also SSA/TSA processing of the kind HUMS pipelines use. **Cannot teach:** fighter gearbox kinematics [TRANSFER: helicopter MRGB → fighter AMAD/accessory gearbox; mesh frequencies differ].

#### 1.12 CMU ALFA (AirLab Failure and Anomaly) fixed-wing UAV dataset
- Carbon Z T-28 (2 m span) with Pixhawk running modified ArduPlane 3.9.0beta1 that can disable control surfaces in flight. Onboard Jetson TX2 with ROS/MAVROS [DIRECT] — [KiltHub/Figshare record](https://doi.org/10.1184/R1/12707963)
- 47 processed autonomous flights: 23 full engine failures and 24 control-surface faults (aileron, rudder, elevator, combinations). 66 min of normal flight and 13 min post-fault. Many hours of raw data also included [DIRECT] — [KiltHub](https://doi.org/10.1184/R1/12707963); [AirLab page](https://theairlab.org/alfa-dataset/)
- Ground truth gives fault type and time [DIRECT]
- Files: processed.zip 272 MB, raw.zip 721 MB, dataflash.zip 541 MB, telemetry.zip 211 MB. CC BY 4.0. Formats are ROS bag, CSV and MAT [DIRECT] — [Figshare API](https://api.figshare.com/v2/articles/12707963)
- Key papers: Keipour, Mousaei & Scherer, IJRR 2020 (doi:10.1177/0278364920966642); ICRA 2019 [DIRECT] — [AirLab page](https://theairlab.org/alfa-dataset/)
- **Can teach:** real asynchronous ROS-timestamped autopilot topics, and sudden actuator-fault onset with labelled times. **Cannot teach:** jet-engine or fighter-scale dynamics [TRANSFER: small electric UAV].

#### 1.13 PX4 Flight Review public logs (ULog) and ArduPilot

**Format and licence**
- Public logs are licensed CC-BY (PX4) and a download script exists [DIRECT] — [review.px4.io/browse](https://review.px4.io/browse)
- The script is rate-limited (10 requests/min) and filters by mav type, flight modes, error labels, rating and airframe [DIRECT] — [download_logs.py](https://raw.githubusercontent.com/PX4/flight_review/main/app/download_logs.py)
- ULog format [DIRECT] — [ULog spec](https://docs.px4.io/main/en/dev_log/ulog_file_format.html):
  - Every topic carries its own monotonic µs `timestamp`; `multi_id` separates redundant sensors.
  - Dropout (`O`) messages record lost data in ms.
  - Parameters are logged at start and on change.
  - Info keys include `ver_hw`.
  - Log-level string messages (ERR, WARNING) are timestamped.

**Public-log index (parsed `dbinfo.json`)** [DIRECT] — [dbinfo (redirects to cdn.logs.px4.io/dbinfo.json)](https://review.px4.io/dbinfo)
- **476,531 public logs**. Of these, 35,613 have `sys_hw = PX4_SITL` (simulation) and the rest are real boards (e.g. FMU v6C 78,903; v5 60,121).
- Mav types: quadrotor 324,797, fixed wing 28,441, standard VTOL 25,723, others.
- Median duration 1.4 min; ~27.8k hours across logs under 24 h.
- Ratings are mostly empty. crash_sw_hw = 402, crash_pilot = 188, unsatisfactory = 1,020.
- 1,263 logs carry user error labels. Label codes map to Other, Vibration, Airframe-design, Sensor-error, Component-failure, Software, Human-error and External-conditions [DIRECT] — [config_tables.py](https://raw.githubusercontent.com/PX4/flight_review/main/app/plot_app/config_tables.py)

**ArduPilot:** no consolidated public log archive was found or verified this session [ASSUMPTION: logs exist mostly as forum attachments].

**Can teach:** the clearest public example of real asynchronous multi-rate timestamps, logged dropouts, redundant-sensor instances and warning/error event streams. **Cannot teach:** aircraft-scale physics or maintenance [TRANSFER: MEMS UAV avionics → fighter IMU/air-data; texture mechanics transfer, magnitudes do not].

#### 1.14 Other UAV fault datasets

**RflyMAD (Beihang)** [DIRECT] — [arXiv:2311.11340](https://arxiv.org/abs/2311.11340); [dataset page](https://rfly-openha.github.io/documents/4_resources/dataset.html)
- 5,629 multicopter cases: 2,566 SIL, 2,566 HIL and 497 real flights; ~3,283 min of fault time; ~114 GB.
- 11 fault types: motor, propeller, low voltage, wind, load loss, sensor noise, accelerometer, gyroscope, magnetometer, barometer, GPS.
- 6 flight statuses.
- Per case: ULog, TLog, flight information, 120 Hz ground truth (simulation only), ROS bags (real only) and CSV.
- Non-commercial licence. Mirrored on Kaggle.
- Real archives: Real-Motor 5.57 GB, Real-Sensors 4.01 GB, Real-No Fault 0.97 GB.

**PADRE (Poznań)** [DIRECT] — [GitHub](https://github.com/AeroLabPUT/UAV_measurement_data)
- Multirotor flights with propeller faults on 1–4 rotors.
- Accelerometers, gyroscopes, microphones and more, as raw, preprocessed and DSP outputs.

**UAV Attack Dataset (IEEE DataPort, doi:10.21227/00dg-0d12)** [DIRECT] — [IEEE DataPort](https://ieee-dataport.org/open-access/uav-attack-dataset)
- PX4 v1.11.3, Holybro S500.
- GPS spoofing and jamming (HackRF) live, plus SIL/HIL with DoS.
- ULog plus CSV, 683.88 MB. Free IEEE account needed.

**Can teach:** sensor-fault and spoofing signatures, and matched sim-vs-real pairs. **Cannot teach:** fighter-scale physics [TRANSFER: small UAV].

#### 1.15 ADS-B: OpenSky Network and adsb.lol (including military)

**OpenSky** [DIRECT] — [OpenSky FAQ](https://opensky-network.org/about/faq)
- Military aircraft "are not being filtered". However, OpenSky does not offer MLAT, so Mode-S-only military aircraft show altitude but no position, and military aircraft that "really do not want to be tracked" switch transponders off.
- Full historical access is only for research institutions, aviation authorities and government (non-profits case by case). Private individuals generally are not granted it. Commercial use needs a licence.
- REST state vectors: anonymous users get 10 s time resolution (latest only); authenticated users get 5 s within 1 h. Daily credit quotas apply [DIRECT] — [OpenSky REST docs](https://openskynetwork.github.io/opensky-api/rest.html)
- A public sample bucket holds `flights/`, `states/`, `raw/`, `metadata/`, `incident-data/` and `trino-tables/` [DIRECT] — [s3.opensky-network.org/data-samples](https://s3.opensky-network.org/data-samples)

**adsb.lol**
- Daily globe-history dumps (readsb trace JSON, gzipped per aircraft) as GitHub releases under **ODbL 1.0**. The 2026 repository is 1,835 GiB [DIRECT] — [adsb.lol historical data](https://www.adsb.lol/docs/open-data/historical/); [globe_history README](https://github.com/adsblol/globe_history)
- readsb `dbFlags` carry military (bit 1), interesting, PIA and LADD flags, and a `filter_mil` option exists [DIRECT] — [readsb README-json](https://github.com/wiedehopf/readsb/blob/dev/README-json.md)
- adsb.lol runs mlat-server [DIRECT] — [globe_history README](https://github.com/adsblol/globe_history)

**Can teach:** the only open *real* kinematic traces of military fast jets: position, baro/geo altitude, ground speed and track, where transponders broadcast. Also airspace-level sortie timing statistics. **Cannot teach:** any onboard sensor, engine or maintenance data. Coverage of Indian Air Force fighters is unknown and probably sparse [ASSUMPTION]. Cross-link: `flight_profiles_and_usage.md`.

#### 1.16 TU Delft Cessna Citation II (PH-LAB) flight-test data
- Not located or verified this session. Without WebSearch, no 4TU.ResearchData record or other public PH-LAB time-history release could be found from known URLs [DIRECT absence of verification]. Treat any availability claim as [ASSUMPTION]. Cross-link: `candidate_airframe_modelling_data.md`.

#### 1.17 FAA / NASA open aviation safety data

**NASA ASRS:** Database Online (DBOL) is live; the page notes planned maintenance on 25 Sep 2026 [DIRECT] — [ASRS DBOL](https://asrs.arc.nasa.gov/search/database.html). NASA has studied ASRS text mining [DIRECT] — [DASHlink 24 listing (crawl)](https://c3.ndc.nasa.gov/dashlink/resources/24/)

**FAA SDRS (Service Difficulty Reporting System)** [DIRECT] — [SDRS home](https://sdrs.faa.gov/); [query page](https://sdrs.faa.gov/Query.aspx)
- Public search of "All Processed Reports" (Malfunction or Defect reports and SDRs).
- Query fields: operator, registration, difficulty date, JASC (ATA) code, aircraft/engine/propeller make and model, part name/make/number, and problem description.
- Look-up tables are available as a zip.

**NTSB:** `avall.zip` (96.6 MB, updated 1 Oct 2026), monthly updates, Pre2008 and PRE1982. The downloadable set moves to an API on 5 Apr 2027 [DIRECT] — [NTSB avdata](https://data.ntsb.gov/avdata)

**ASIAS:** the FAA ASIAS programme hosts NGAFID; operator data is not public [DIRECT] — [ngafid.org](https://ngafid.org/)

**Can teach:** realistic defect vocabulary, ATA/JASC coding and part-level failure frequency for civil types. **Cannot teach:** sensor data. Military types are absent [TRANSFER]. Cross-link: `maintenance_records_and_events.md`.

#### 1.18 UCI repository

**Condition Monitoring of Hydraulic Systems (Helwig et al. 2015)** [DIRECT] — [UCI 447](https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems)
- Real test rig: 2,205 cycles of 60 s.
- Rates: PS1–6 and EPS1 at 100 Hz; FS1–2 at 10 Hz; TS1–4, VS1 and the virtual CE/CP/SE at 1 Hz.
- Graded faults:
  - Cooler: 100/20/3%.
  - Valve: 100/90/80/73%.
  - Pump leakage: 0/1/2.
  - Accumulator: 130/115/100/90 bar.
- Also a "stable" flag.
- Tab-delimited text, 73.1 MB, CC BY 4.0.
- **Can teach:** graded hydraulic degradation with multi-rate coupling [TRANSFER: industrial rig → aircraft hydraulic system; pressures and topology differ].

**Condition Based Maintenance of Naval Propulsion Plants (Coraddu et al. 2014)** [DIRECT] — [UCI 316](https://archive.ics.uci.edu/dataset/316/condition+based+maintenance+of+naval+propulsion+plants)
- Numerical simulator of a CODLAG frigate gas turbine. 11,934 steady-state points.
- Compressor decay kMc 1→0.95 and turbine kMt 1→0.975, on a 0.001 grid. CC BY 4.0.
- **Can teach:** a steady-state decay-to-sensor mapping (simulated). **Cannot teach:** texture or transients.

#### 1.19 NASA PCoE component datasets and CWRU
- PCoE repository: 21 entries, several now "currently unavailable" (PHM08, Trebuchet, Capacitor-2, Small-Sat Power, Fatigue Crack, Accelerated Battery Life) [DIRECT] — [PCoE repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)
- Zip sizes (HEAD) [DIRECT] — [S3 bucket](https://phm-datasets.s3.amazonaws.com/NASA/4.+Bearings.zip):
  - IMS Bearings 1.08 GB
  - Batteries 0.21 GB
  - Randomized Battery Usage 1.07 GB
  - HIRF Battery (Edge 540 aircraft in a HIRF chamber) 1.09 GB
  - FEMTO 1.16 GB
  - CFRP Composites 4.64 GB
- IMS bearings are on data.gov under U.S. Government Works terms [DIRECT] — [data.gov IMS Bearings](https://catalog.data.gov/dataset/ims-bearings)
- Li-ion aging: 18650 cells cycled to 30% capacity fade (2 Ah → 1.4 Ah), with EIS [DIRECT] — [DASHlink 133](https://c3.ndc.nasa.gov/dashlink/resources/133/)
- CWRU bearings [DIRECT] — [CWRU apparatus](https://engineering.case.edu/bearingdatacenter/apparatus-and-procedures)
  - 2 hp motor with EDM faults of 0.007–0.040 in on inner race, ball and outer race; 0–3 hp, 1797–1720 rpm.
  - 12 kHz, plus 48 kHz for drive-end faults; MATLAB .mat. Speed and load were recorded by hand.
- **Can teach:** bearing-fault spectral texture and battery capacity-fade trajectories [TRANSFER: generic rotating machinery → engine/AMAD bearings; aircraft battery chemistry may differ].

#### 1.20 Spacecraft telemetry: real texture, different physics

**NASA SMAP / MSL (Hundman et al. KDD 2018)** [DIRECT] — [telemanom README](https://github.com/khundman/telemanom); [Kaggle mirror](https://www.kaggle.com/datasets/patrickfleith/nasa-anomaly-detection-dataset-smap-msl)
- 82 channels (55 SMAP, 27 MSL) with 105 labelled anomaly sequences (point and contextual).
- Command one-hot inputs included.
- Values "pre-scaled between (-1,1)" and time anonymised.

**ESA Anomalies Dataset / ESA-ADB (Kotowski et al. 2024)** [DIRECT] — [arXiv:2406.17826 Table 1](https://arxiv.org/abs/2406.17826)
- Three missions, two used for benchmarking.
- Mission1: 76 channels, 698 telecommands, 774.9 M points over 14 years.
- Mission2: 100 channels, 776.7 M points over 3.5 years.
- 844 annotated events: 148 anomalies, 690 rare nominal events and 4 communication gaps.
- Per-channel labels.
- "Irregular timestamps, varying sampling rates, anomalies in training data, communication gaps, and an overabundance of telecommands". Names, timelines and measured types are anonymised.
- Zenodo zips: 3.78, 4.10 and 3.73 GB. No licence field in the Zenodo metadata [DIRECT] — [Zenodo 12528696](https://doi.org/10.5281/zenodo.12528696). Code and Kaggle competition: [GitHub ESA-ADB](https://github.com/kplabs-pl/ESA-ADB)

**OPSSAT-AD** [DIRECT] — [arXiv:2407.04730](https://arxiv.org/abs/2407.04730); [Zenodo 12588359 (API)](https://zenodo.org/api/records/12588359)
- ESA CubeSat telemetry.
- `segments.csv` (18 MB) of raw segments plus `dataset.csv` of features. CC BY 4.0.

**ESA Kelvins Mars Express Power Challenge (2016)** [DIRECT] — [Kelvins page](https://kelvins.esa.int/mars-express-power-challenge/)
- Three Martian years of MEX telemetry used to predict thermal-subsystem power. The competition is over.

**Can teach:** realistic irregular sampling, communication gaps, commanded "rare nominal" events vs anomalies, and channel-specific labels. These are directly analogous to a fighter downlink/telemetry stream and to maintenance-mode events [TRANSFER: telemetry-link semantics only, not flight physics].

#### 1.21 Military and fighter data: what exists publicly

**Real data**
- No public raw fighter telemetry, FDR or HUMS dataset was found:
  - DASHlink's 118 projects and ~760 resources contain no fighter data [DIRECT, from the crawl] — [DASHlink projects](https://c3.ndc.nasa.gov/dashlink/projects/)
  - NGAFID and PHM sets are civil.
  - DSTG's public challenge data is helicopter gearbox only.
- DSTG fighter usage data and USAF/IAF HUMS data: none public found [DIRECT absence].
- The only real fighter-state traces found are ADS-B/MLAT tracks (1.15).

**Simulators and models (simulated; useful as physics backbones, not texture)**
- AeroBench F-16 (Python port; "Distribution A" public release; F-16 GCAS benchmark, Heidlauf et al., ARCH 2018) [DIRECT] — [GitHub AeroBenchVVPython](https://github.com/stanleybak/AeroBenchVVPython)
- JSBSim F-16 model [DIRECT exists] — [JSBSim aircraft/f16](https://github.com/JSBSim-Team/jsbsim/tree/master/aircraft/f16)
- NASA TP-1538 (1979), fighter stall/post-stall simulator study (the classic F-16 aero source) [DIRECT] — [NTRS 19800005879](https://ntrs.nasa.gov/citations/19800005879)
- SIDPAC (300+ MATLAB system-ID tools; "U.S. and Foreign Release" by request) [DIRECT] — [NASA software LAR-16100-1](https://software.nasa.gov/software/LAR-16100-1)
- Engine models:
  - **C-MAPSS40k is U.S. Government Purpose Release only**, so it is not obtainable by an Indian team [DIRECT] — [LEW-18624-1](https://software.nasa.gov/software/LEW-18624-1)
  - AGTF30 (T-MATS) is open source [DIRECT] — [LEW-19717-1](https://software.nasa.gov/software/LEW-19717-1); [GitHub AGTF30](https://github.com/nasa/AGTF30)
  - [T-MATS](https://github.com/nasa/T-MATS) and [pyCycle](https://github.com/OpenMDAO/pyCycle) are public (HTTP 200).
- **Can teach:** fighter flight dynamics and engine cycle structure for the physics core. **Cannot teach:** real sensor texture. Cross-link: `candidate_airframe_modelling_data.md` and `modelling_methodology.md`.

### Inferences
- The realistic transfer chain for Phalanx has three layers:
  1. **Physics backbone:** fighter airframe and engine models (JSBSim/AeroBench F-16, AGTF30/T-MATS-style cycle models tuned to F404-class data).
  2. **Mission and phase statistics:** fighter manuals and usage spectra (sibling note) plus ADS-B military tracks.
  3. **Measurement texture:** learned from DASHlink, NGAFID, PX4 ULog, Airbus and HUMS raw data, then re-parameterised to fighter sensor specifications.

  No single public dataset spans all three.
- DASHlink and N-CMAPSS are coupled by provenance: Tail 687 supplies N-CMAPSS's real flight conditions. Phalanx can therefore validate a "real profile + simulated engine" pipeline against the real DASHlink engine channels of the same tail. That gives a rare check of simulated vs real engine response under identical real flight conditions [inference from 1.1 and 1.5].
- NGAFID + MaintNet is the only public pairing of *real flight recordings* with *real maintenance logbook* labels. Its labels are weak (±2 days, flight-level), which matches how fighter maintenance records (e.g. Form-700-type entries) would link to sorties [TRANSFER: GA flight school → squadron line maintenance].
- PX4 SITL vs real logs (35.6k vs ~441k, same schema) and RflyMAD SIL/HIL/real are ready-made testbeds for the Phalanx real-vs-synthetic discriminator protocol. They are format-identical and differ only in physics and texture.

### Gaps
- DASHlink parameter list and per-parameter rates were not read, because downloading data is forbidden by the brief. The 0.25–16 Hz range and the 186-name list should be confirmed by opening one `.mat` after approval.
- N-CMAPSS full-text details (virtual sensors and θ in the public release, sampling rate, exact per-DS unit counts including DS02) are unverified because MDPI blocked access.
- PHM 2024 and 2025 data provenance (real vs simulated) is not stated on the pages.
- TU Delft Citation II, ArduPilot public logs, Mendeley, Harvard Dataverse and a broader IEEE DataPort/Kaggle sweep were not covered because of the WebSearch outage.

---

## Q2. Which datasets keep raw texture (quantisation, dropouts, true timestamps, asynchronous rates) and which destroy it?

### Takeaway
Raw texture survives in:
- DASHlink tail files (native multi-rate recorder parameters).
- PX4 ULog, ALFA and RflyMAD real logs (per-topic µs timestamps, logged dropouts).
- NGAFID (unscaled 1 Hz with NaNs).
- ESA-AD (irregular timestamps, gaps).
- Airbus helicopter (1024 Hz, scaled only).
- UCI hydraulic (native multi-rate).
- DSTG HUMS2025/2027 raw vibration.
- FLEA (DAQ-raw).

Texture is destroyed or synthetic in:
- C-MAPSS (one snapshot per cycle, Gaussian/mixture noise).
- N-CMAPSS x_s (model outputs with synthetic noise).
- SMAP/MSL (scaled to ±1, time anonymised).
- The DASHlink curated 4-class set (1 Hz windows).
- HUMS2023 (synchronous averages only).
- PHM 2024 (shuffled rows).

### Cited Findings

| Dataset | Values | Time base | Async / multi-rate | Dropouts / NaN | Visible quantisation | Normalisation | Source |
|---|---|---|---|---|---|---|---|
| DASHlink Sample Flight Data | Real recorder engineering values [DIRECT] | Flight start in filename; per-parameter rate field [DIRECT] | Yes: each parameter has its own rate [DIRECT] | Expected (FOQA spikes and missing data) [DIRECT for NASA FOQA generally] | Discrete/enumerated words, inverted binary states [DIRECT] | None stated; de-identified | [data.gov](https://catalog.data.gov/dataset/flight-data-for-tail-652); [FAQ](https://c3.ndc.nasa.gov/dashlink/static/media/other/Sample_Flight_Data_FAQ_2.doc); [Matthews 2013](https://c3.ndc.nasa.gov/dashlink/static/media/publication/JAIS_matthews_2013.pdf) |
| DASHlink curated 4-class | Real, windowed | 160 s at 1 s steps | No (resampled) [inference] | Not stated | Flap "Discrete" | Not stated | [doc PDF](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/DASHlink_full_data_documentation.pdf) |
| NGAFID maintenance set | Real, unscaled [DIRECT] | 1 Hz timestep index; dates removed [DIRECT] | No (single 1 Hz) | ~1% NaN [DIRECT] | Likely (GA engine monitor) [ASSUMPTION] | None in full set [DIRECT] | [arXiv](https://arxiv.org/pdf/2210.07317) |
| PX4 ULog (public logs, RflyMAD, UAV Attack) | Real (and SITL) | Per-topic µs timestamps [DIRECT] | Yes [DIRECT] | Dropout messages in ms [DIRECT] | Sensor-native | None | [ULog spec](https://docs.px4.io/main/en/dev_log/ulog_file_format.html) |
| CMU ALFA | Real ROS topics | ROS timestamps (bag) [DIRECT format] | Yes [ASSUMPTION: typical MAVROS] | Not stated | Native | None | [KiltHub](https://doi.org/10.1184/R1/12707963) |
| ESA-AD | Real telemetry (anonymised) | Irregular timestamps [DIRECT] | Varying sampling rates [DIRECT] | Communication gaps [DIRECT] | Not stated | Anonymised types and timelines [DIRECT] | [arXiv:2406.17826](https://arxiv.org/abs/2406.17826) |
| SMAP/MSL | Real | Time anonymised [DIRECT] | No | Not stated | May survive in levels | Scaled to (-1,1) [DIRECT] | [telemanom](https://github.com/khundman/telemanom) |
| Airbus helicopter | Real accelerometer | 1024 Hz, 1-min cuts [DIRECT] | No (single rate) | Abnormal sequences in validation | Scaled by a constant factor [DIRECT] | Factor only [DIRECT] | [DataCite](https://api.datacite.org/dois/10.3929/ethz-b-000415151) |
| DSTG HUMS2025 / HUMS2027 raw | Real DAQ | 65,573.77 Hz / 51,200 Hz; timestamped filenames [DIRECT] | Tach plus vibration channels | Not stated | Delta-sigma ADC [DIRECT] | None stated | [HUMS2025 PDF](https://www.humsconference.com.au/HUMS2025datachallenge/The%20HUMS2025%20Data%20Challenge%20Dataset%20Description.pdf); [HUMS2027](https://www.humsconference.com.au/HUMS2027datachallenge/dataset.html) |
| DSTG HUMS2023 | Synchronous averages | Angle domain | n/a | n/a | Lost by averaging | Processed [DIRECT] | [HUMS2023 PDF](https://www.humsconference.com.au/HUMS2023/HUMS2023_Data_Challenge_dataset_description_v1.1.1.pdf) |
| UCI hydraulic | Real rig | Fixed 60 s cycles | 100 / 10 / 1 Hz [DIRECT] | None [DIRECT] | Native | Raw, no feature extraction [DIRECT] | [UCI 447](https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems) |
| FLEA | Real lab DAQ | Seconds from start [DIRECT] | 20–50 kHz vs ~1 kHz [DIRECT] | Not stated | Native | None | [FLEA FAQ](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/FLEA_Data_FAQ.pdf) |
| ADAPT EPS | Real lab | 2 Hz [DIRECT] | No | Software "Antagonist" alters sensor data [DIRECT] | Switch states | None | [DASHlink 143](https://c3.ndc.nasa.gov/dashlink/resources/143/) |
| OpenSky / adsb.lol | Real ADS-B / MLAT | Message timestamps; REST resampled to 5/10 s [DIRECT] | Irregular reception | Coverage gaps [DIRECT: no MLAT on OpenSky] | ADS-B encoding (e.g. 25-ft altitude steps) [ASSUMPTION] | None | [OpenSky REST](https://openskynetwork.github.io/opensky-api/rest.html); [readsb](https://github.com/wiedehopf/readsb/blob/dev/README-json.md) |
| C-MAPSS | Simulated | Per cycle (1 snapshot per flight) [DIRECT] | No | No | No | Synthetic noise [DIRECT] | [Saxena 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf) |
| N-CMAPSS | w real, x_s simulated [DIRECT] | Regular (1 Hz reported [ASSUMPTION]; precursor 0.1 Hz [DIRECT]) | No | No | No | Raw engineering units in files | [PHM 2021 PDF](https://data.phmsociety.org/wp-content/uploads/sites/9/2021/08/2021_Data_Challenge.pdf); [arXiv:2003.00732](https://arxiv.org/abs/2003.00732) |
| PHM 2024 | Unknown origin | Shuffled, asset IDs removed [DIRECT] | n/a | n/a | n/a | Not stated | [PHM 2024](https://data.phmsociety.org/phm2024-conference-data-challenge/) |
| PHM 2025 | Unknown origin | Snapshot per phase (≤8 per flight) [DIRECT] | No | Optional sensors missing in some test sets [DIRECT] | n/a | "Preprocessing recommended" [DIRECT] | [PHM 2025](https://data.phmsociety.org/phm-north-america-2025-conference-data-challenge/) |

### Inferences
- For *learning residuals*, prefer DASHlink tail files, PX4 real ULog, NGAFID full set, ESA-AD, Airbus and HUMS raw. Never fit noise models to C-MAPSS or N-CMAPSS x_s: their noise is the authors' assumed distributions, explicitly not real.
- De-identification itself leaves artefacts a discriminator could exploit:
  - DASHlink `_1` filenames and dates.
  - NGAFID removed dates and positions.
  - ESA-AD anonymised timelines.

  Phalanx's synthetic records should not be compared with these on fields that real fighter data would carry in non-anonymised form [inference].
- The dropout/gap model should be split three ways:
  - Recorder-level (DASHlink, NGAFID NaN).
  - Logger-level (ULog `O` messages).
  - Link-level (ESA-AD communication gaps, ADS-B reception).

  The three have different statistics [inference].

### Gaps
- Actual quantisation step sizes, dropout rates and rate maps were not measured. That needs the data downloaded and is cross-linked to `sensor_residual_texture.md`.
- Whether DASHlink files contain engineering-unit values or raw counts is unverified [ASSUMPTION: engineering units, since units are stored].

---

## Q3. Practical access as of 2026-10-13: link status, sizes, formats, registration, licences

### Takeaway
Most key datasets download directly without registration:
- DASHlink, NASA PCoE (S3), Zenodo (NGAFID, ESA-AD, OPSSAT-AD), Figshare (ALFA), UCI, CWRU, PX4.

Registration or approval is needed for:
- OpenSky full history (institutional).
- IEEE DataPort (free account).
- PHM challenge submissions (data links are public S3).
- **DSTG HUMS2027 (deadline 31 Oct 2026)**.

Licences range from public domain/US-Gov works (NASA) through CC BY (UCI, ALFA, PX4, OPSSAT-AD, CAFUC2), CC BY-NC-SA (Airbus) and ODbL (adsb.lol) to non-commercial (RflyMAD) and no-share (HUMS).

### Cited Findings

| Dataset | Verified URL (status 2026-10-13) | Size (verified) | Format | Registration | Licence |
|---|---|---|---|---|---|
| DASHlink Sample Flight Data | [project 85](https://c3.ndc.nasa.gov/dashlink/projects/85/) (200) | 310 zips, ~245.4 GB; ~6–9 GB per tail [DIRECT HEAD] | MATLAB .mat in .zip | None for download | Not stated [DIRECT]; NASA public |
| DASHlink curated 4-class | [res. 1018](https://c3.ndc.nasa.gov/dashlink/resources/1018/) | 1.6 GB npz + 3.9 MB csv [DIRECT] | .npz | None | N/A [DIRECT] |
| N-CMAPSS | [S3 zip](https://phm-datasets.s3.amazonaws.com/NASA/17.+Turbofan+Engine+Degradation+Simulation+Data+Set+2.zip) (200) | 15.76 GB [DIRECT] | HDF5 | None | Paper CC-BY [DIRECT]; data terms not stated |
| C-MAPSS | [S3 zip](https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip) (200) | 12.4 MB [DIRECT] | Text | None | Not stated |
| PHM 2021 validation | [S3](https://phm-datasets.s3.amazonaws.com/Data_Challenge_2021_N-CMAPSS_DS_Validation_f.h5) (200) | 2.94 GB [DIRECT] | .h5 | Challenge closed | — |
| PHM 2024 / 2025 | [2024](https://data.phmsociety.org/phm2024-conference-data-challenge/), [2025](https://data.phmsociety.org/phm-north-america-2025-conference-data-challenge/) | 22.6 MB + 0.36 MB / 7.8 MB + 6.1 MB [DIRECT] | zip (tabular) | Application form only for submission [DIRECT] | PHM terms (not retrieved) |
| NGAFID maintenance | [Zenodo 6624956](https://doi.org/10.5281/zenodo.6624956) | 4.29 GB + 1.13 GB [DIRECT] | Parquet (Dask) + CSV | None | CC-BY-4.0 (Zenodo) vs GPL-3.0 (paper) [DIRECT conflict] |
| MaintNet aviation | [aircraft page](https://people.rit.edu/fa3019/technical/aircraft.html) (200) | 6,169 rows [DIRECT] | CSV | None | "Follow license guideline" (unspecified) [DIRECT] |
| CAFUC2 | [Zenodo 19124264](https://zenodo.org/records/19124264) | Not retrieved (API rate-limited) | CSV (600 files) [DIRECT] | None | CC BY 4.0 [DIRECT] |
| Airbus helicopter | [handle](http://hdl.handle.net/20.500.11850/415151) (landing page 500/429 here) | 1.04 GB [DIRECT DataCite] | HDF5 + CSV | None stated | CC BY-NC-SA 4.0 [DIRECT] |
| DSTG HUMS2027 | [download page](https://www.humsconference.com.au/HUMS2027datachallenge/download.html) (200) | 323 MB as listed [DIRECT] | MATLAB | **Register by 31 Oct 2026** | Restricted, no sharing [DIRECT] |
| DSTG HUMS2023 public release | DSTG page (403 to automated fetch) | 6.1 GB (challenge subset) [DIRECT] | MATLAB | Conditional | Conditional [DIRECT statement] |
| CMU ALFA | [Figshare](https://doi.org/10.1184/R1/12707963) | 0.27 / 0.72 / 0.54 / 0.21 GB [DIRECT] | ROS bag, CSV, MAT | None | CC BY 4.0 [DIRECT] |
| PX4 public logs | [browse](https://review.px4.io/browse); [index](https://review.px4.io/dbinfo) | Index 32.6 MB (gz); 476,531 logs [DIRECT] | ULog | None (rate-limited script) | CC-BY [DIRECT] |
| RflyMAD | [dataset page](https://rfly-openha.github.io/documents/4_resources/dataset.html) (200) | ~114 GB total; real ≈10.6 GB [DIRECT] | ULog, TLog, CSV, bag | None (Beihang Yunpan / Kaggle) | Non-commercial [DIRECT] |
| UAV Attack | [IEEE DataPort](https://ieee-dataport.org/open-access/uav-attack-dataset) (200) | 683.88 MB [DIRECT] | ULog, CSV | Free IEEE account [DIRECT] | Not stated |
| PADRE | [GitHub](https://github.com/AeroLabPUT/UAV_measurement_data) (200) | Not retrieved | Raw, preprocessed, DSP | None | Not retrieved |
| OpenSky | [FAQ](https://opensky-network.org/about/faq) (200 with a browser user-agent) | Samples bucket [DIRECT] | JSON/CSV/Avro (Trino) | Institutional approval for full history [DIRECT] | Non-commercial; commercial needs licence [DIRECT] |
| adsb.lol | [historical](https://www.adsb.lol/docs/open-data/historical/) (200) | 1,835 GiB for 2026 so far [DIRECT] | gz JSON traces (split tar) | None | ODbL 1.0 [DIRECT] |
| UCI hydraulic | [UCI 447](https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems) | 73.1 MB [DIRECT] | Text | None | CC BY 4.0 [DIRECT] |
| UCI naval GT | [UCI 316](https://archive.ics.uci.edu/dataset/316/condition+based+maintenance+of+naval+propulsion+plants) | Not retrieved | Text | None | CC BY 4.0 [DIRECT] |
| FLEA | [project 45 resources](https://c3.ndc.nasa.gov/dashlink/projects/45/resources/) | ~5.6 GB across 13 zips [DIRECT] | .data / .tdms / .bin | None | N/A |
| ADAPT / DXC | [DASHlink 143](https://c3.ndc.nasa.gov/dashlink/resources/143/) | ~0.2–23 MB zips [DIRECT] | Text, MAT, .scn | None | N/A |
| DASHlink MAR | [DASHlink 842](https://c3.ndc.nasa.gov/dashlink/resources/842/) | ~1.6 GB CSVs [DIRECT] | CSV | None | N/A |
| PCoE batteries, IMS, FEMTO, CFRP, HIRF | [PCoE repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) | 0.21–4.64 GB [DIRECT] | MAT, text | None | US Gov works (IMS on data.gov) [DIRECT] |
| CWRU | [Bearing Data Center](https://engineering.case.edu/bearingdatacenter) (200) | Not retrieved | .mat [DIRECT] | None | Not stated [DIRECT] |
| SMAP/MSL | [Kaggle mirror](https://www.kaggle.com/datasets/patrickfleith/nasa-anomaly-detection-dataset-smap-msl) (200) | Not retrieved | .npy, CSV labels | Kaggle account | Code Apache-2.0; data not stated |
| ESA-AD | [Zenodo 12528696](https://doi.org/10.5281/zenodo.12528696) | 3.78 / 4.10 / 3.73 GB [DIRECT] | zip (CSV/Parquet [ASSUMPTION]) | None | Not stated in metadata [DIRECT] |
| OPSSAT-AD | [Zenodo 12588359](https://zenodo.org/api/records/12588359) | 18 MB + 0.5 MB [DIRECT] | CSV | None | CC BY 4.0 [DIRECT] |
| NTSB | [avdata](https://data.ntsb.gov/avdata) (200) | avall.zip 96.6 MB [DIRECT] | MDB in zip | None | Public |
| FAA SDRS | [SDRS](https://sdrs.faa.gov/) (200) | Query exports | Web query plus look-up tables | None for search | Public |
| C-MAPSS40k (software) | [LEW-18624-1](https://software.nasa.gov/software/LEW-18624-1) | — | MATLAB/Simulink | **US Gov purpose only** [DIRECT] | Restricted |
| AGTF30 / T-MATS / pyCycle | [AGTF30](https://github.com/nasa/AGTF30), [T-MATS](https://github.com/nasa/T-MATS), [pyCycle](https://github.com/OpenMDAO/pyCycle) | — | MATLAB / Python | None | Open source [DIRECT for AGTF30] |

### Inferences
- **Indian-team constraints** [TRANSFER: team located in India]:
  - C-MAPSS40k cannot be obtained.
  - OpenSky full history needs an institutional request (a university affiliation may qualify).
  - HUMS data terms forbid redistribution, so derived models are fine but raw data cannot be bundled with the deliverable.
  - Airbus (NC-SA) and RflyMAD (NC) restrict commercial follow-on.
- The DASHlink server answered range and HEAD requests but was slow (~20–130 s per zip directory, with one stall). Budget several days to fetch 245 GB, or start with Tail 687 (~7.15 GB) [DIRECT timing from this session].

### Gaps
- PHM Society data terms of use, PADRE licence, CWRU terms, ESA-AD licence and the CAFUC2 size were not retrieved.

---

## Q4. Domain-gap caveats when transferring from commercial, GA, UAV, helicopter or spacecraft data to a fighter

### Takeaway
Every public source differs from a fighter (Tejas Mk1/Mk1A F404-GE-IN20, F/A-18 F404, Gripen RM12, F-16, Su-30MKI) in at least one first-order respect:
- Manoeuvre envelope.
- Engine type: afterburning low-bypass vs high-bypass or piston.
- Sensor suite and recording architecture: 1553-bus/EMS vs ARINC-717 FDR, G1000 or PX4.
- Maintenance regime.

Transfer only distribution *shapes and mechanisms*, then re-scale with fighter-specific specifications from sibling notes.

### Cited Findings and transfer reasoning

**Commercial four-engine regional jet (DASHlink)** [TRANSFER: civil transport → fighter]
- What transfers: recorder-level texture (multi-rate, discrete words, spikes and dropouts), per-engine spread under a common command (N2.1–N2.4 follow a common N1 command with engine-to-engine differences from "age of the engine, sensor biases, offsets in the fuel delivery system, performance deterioration" [DIRECT] — [FAQ](https://c3.ndc.nasa.gov/dashlink/static/media/other/Sample_Flight_Data_FAQ_2.doc)), and phase-segmentation logic.
- What does not: g and AoA ranges, throttle-transient rates, afterburner, and sortie structure (ACM, weapons, low level). Flight phases 0–7 cover only airline phases.

**Commercial engine simulations (C-MAPSS, N-CMAPSS, PHM 2025)** [TRANSFER: high-bypass commercial → low-bypass afterburning]
- What transfers: health-parameter-to-sensor sensitivity *directions*, margin-based end-of-life, and water-wash/shop-visit resets.
- What does not: AB/nozzle schedules, much faster cycle accumulation per hour, and fighter TAC/LCF counting. N-CMAPSS excludes flight below 10,000 ft [DIRECT] — [PHM 2021 PDF](https://data.phmsociety.org/wp-content/uploads/sites/9/2021/08/2021_Data_Challenge.pdf). Cross-link: `faults_and_degradation.md`, `flight_profiles_and_usage.md` (cycle counting).

**General aviation (NGAFID, CAFUC2, MaintNet)** [TRANSFER: piston trainer → fighter trainer/line ops]
- What transfers: training-sortie variability dominated by pilot action. NGAFID authors note "a significant portion of variance in flight data is explained by pilot action and not the condition of the airplane's parts" [DIRECT] — [arXiv](https://arxiv.org/pdf/2210.07317). Also maintenance-event linkage at day resolution, and free-text logbook style.
- What does not: CHT/EGT-per-cylinder physics, 1 Hz-only rates, and civil maintenance regulations.

**Small UAVs (PX4, ALFA, RflyMAD, PADRE)** [TRANSFER: MEMS autopilot → fighter avionics]
- What transfers: timestamping/asynchrony/dropout mechanics, redundant-sensor instances (`multi_id`), fault-onset labelling conventions, and sim-vs-real pairs.
- What does not: sensor grades (MEMS vs navigation-grade INS), vehicle dynamics and power plant.

**Helicopters (Airbus, DSTG HUMS, PHM 2024)** [TRANSFER: rotorcraft drivetrain/turboshaft → fighter engine/AMAD]
- What transfers: vibration-channel texture, SSA/TSA processing, wear-debris coupling, and torque-margin trend checks.
- What does not: rotor-dominated spectra and gear-mesh frequencies (e.g. 1900 Hz and 568 Hz meshes at 6000 rpm input [DIRECT] — [HUMS2023 PDF](https://www.humsconference.com.au/HUMS2023/HUMS2023_Data_Challenge_dataset_description_v1.1.1.pdf)), which differ from engine/accessory gearbox orders.

**Spacecraft (ESA-AD, SMAP/MSL, OPSSAT-AD)** [TRANSFER: housekeeping telemetry → fighter downlink/maintenance data streams]
- What transfers: irregular sampling, communication gaps, telecommand-induced "rare nominal events" vs anomalies [DIRECT] — [arXiv:2406.17826](https://arxiv.org/abs/2406.17826), and per-channel labelling.
- What does not: any flight-physics relationships.

### Inferences
- Use a "mechanism vs magnitude" rule: learn *mechanisms* (rates, gaps, quantisation behaviour, coupling structure) from public data, and set *magnitudes* (ranges, noise levels, rates, limits) from fighter documents in the sibling notes.
- Discriminator tests should be run *within* domain: civil-real vs Phalanx-civil-mode synthetic, or ADS-B-real fighter tracks vs Phalanx tracks. A real-civil vs synthetic-fighter discriminator would trivially succeed on the domain gap and measure nothing [inference; cross-link `validation_and_calibration.md`].

### Gaps
- No public fighter data exists to quantify the gap directly.
- IAF ADS-B visibility and the existence of any de-classified Indian (DRDO/ADA/HAL) flight-test datasets were not established.

---

## Q5. Synthesis

### Takeaway — (a) Key findings summary
1. **No public raw fighter telemetry exists.**
   - Real fighter-state data is limited to ADS-B/MLAT kinematics. adsb.lol publishes ODbL daily traces with a readsb military flag [DIRECT] — [adsb.lol](https://www.adsb.lol/docs/open-data/historical/); [readsb](https://github.com/wiedehopf/readsb/blob/dev/README-json.md).
   - OpenSky does not filter military aircraft but lacks MLAT [DIRECT] — [OpenSky FAQ](https://opensky-network.org/about/faq).
2. **DASHlink Sample Flight Data is the strongest real airframe-level texture source.** It has 35 tails, 310 zips, ~245 GB, an estimated ~1.8×10⁵ flights, 186 multi-rate parameters, a four-engine aircraft, a phase code (PH) and documented discrete-state quirks [DIRECT] — [project 85](https://c3.ndc.nasa.gov/dashlink/projects/85/); [FAQ](https://c3.ndc.nasa.gov/dashlink/static/media/other/Sample_Flight_Data_FAQ_2.doc).
3. **N-CMAPSS is the strongest simulated degradation source.** Its real flight conditions came from DASHlink Tail 687 (precursor study) [DIRECT] — [arXiv:2003.00732](https://arxiv.org/abs/2003.00732). Its sensor noise is synthetic. C-MAPSS noise was explicitly assumed because no real data was available [DIRECT] — [Saxena 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf).
4. **NGAFID + MaintNet is the only real flight-data ↔ maintenance-logbook pairing.** It covers 28,935 flights, 2,111 events and 36 classes, at 1 Hz with ~1% NaN [DIRECT] — [arXiv:2210.07317](https://arxiv.org/abs/2210.07317).
5. **Raw-texture mechanics are best documented in PX4 ULog.** It has µs per-topic timestamps and explicit dropout messages, across 476,531 public logs of which 35,613 are SITL [DIRECT] — [ULog spec](https://docs.px4.io/main/en/dev_log/ulog_file_format.html); [dbinfo](https://review.px4.io/dbinfo).
6. **Ready-made real-vs-synthetic testbeds exist:**
   - RflyMAD: 2,566 SIL / 2,566 HIL / 497 real [DIRECT] — [RflyMAD](https://rfly-openha.github.io/documents/4_resources/dataset.html).
   - CAFUC2: 120 real + 480 injected [DIRECT] — [PMC13570879](https://pmc.ncbi.nlm.nih.gov/articles/PMC13570879/).
   - PX4 SITL vs real logs.
7. **Time-critical item: DSTG HUMS2027.** Real, naturally developing gearbox spall data at 51.2 kHz with wear debris; registration closes **31 Oct 2026** [DIRECT] — [HUMS2027](https://www.humsconference.com.au/HUMS2027datachallenge/download.html).

### Cited Findings — (b) Ranked tables per use-case

**(a) Learning residual texture**

| Rank | Dataset | Why | Main caveat | Source |
|---|---|---|---|---|
| 1 | DASHlink Sample Flight Data (tail files) | Real recorder multi-rate parameters, discrete words, fleet of 35 tails | Civil; rates and parameter list need confirming on download | [project 85](https://c3.ndc.nasa.gov/dashlink/projects/85/) |
| 2 | PX4 real-hardware ULog (and RflyMAD real, ALFA) | µs timestamps, asynchronous topics, logged dropouts, redundant sensors | MEMS UAV sensors | [ULog spec](https://docs.px4.io/main/en/dev_log/ulog_file_format.html) |
| 3 | NGAFID full set | Unscaled 1 Hz G1000-class data with ~1% NaN, 31k hours | GA piston; dates removed | [arXiv](https://arxiv.org/pdf/2210.07317) |
| 4 | ESA-AD | Irregular timestamps, varying rates, communication gaps at scale (1.55 bn points) | Spacecraft physics; anonymised | [arXiv:2406.17826](https://arxiv.org/abs/2406.17826) |
| 5 | Airbus helicopter accelerometers | 1024 Hz flight-test vibration plus instrumentation-fault anomalies | Constant scale factor; helicopter | [DataCite](https://api.datacite.org/dois/10.3929/ethz-b-000415151) |
| 6 | DSTG HUMS2025 / HUMS2027 raw | 51–66 kHz delta-sigma vibration, tachometer, debris | Test rig; restricted | [HUMS2025 PDF](https://www.humsconference.com.au/HUMS2025datachallenge/The%20HUMS2025%20Data%20Challenge%20Dataset%20Description.pdf) |
| 7 | UCI hydraulic | 100/10/1 Hz real rig sensors | Industrial rig | [UCI 447](https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems) |
| 8 | FLEA lab | 1 kHz electrical plus 20–50 kHz accelerometers on EMAs | Lab only; channel sets vary | [FLEA FAQ](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/FLEA_Data_FAQ.pdf) |
| — | Do not use: C-MAPSS, N-CMAPSS x_s, SMAP/MSL scaled values, HUMS2023 TSA | Synthetic noise or processed | — | [Saxena 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf) |

**(b) Flight-phase and profile statistics**

| Rank | Dataset | Why | Caveat | Source |
|---|---|---|---|---|
| 1 | DASHlink Sample Flight Data | PH phase code 0–7, autopilot modes, ~10⁵ flights, timestamps | Airline phases only | [FAQ](https://c3.ndc.nasa.gov/dashlink/static/media/other/Sample_Flight_Data_FAQ_2.doc) |
| 2 | adsb.lol (military flag) / OpenSky | Only real fast-jet trajectories; open licence (ODbL) | Kinematics only; sparse military broadcast | [adsb.lol](https://www.adsb.lol/docs/open-data/historical/); [OpenSky FAQ](https://opensky-network.org/about/faq) |
| 3 | NGAFID | 28,935 training-school flights (pattern work, manoeuvres) | GA | [arXiv](https://arxiv.org/abs/2210.07317) |
| 4 | N-CMAPSS scenario descriptors w | Real alt/Mach/TRA traces by flight class | Above 10 kft only | [PHM 2021 PDF](https://data.phmsociety.org/wp-content/uploads/sites/9/2021/08/2021_Data_Challenge.pdf) |
| 5 | CAFUC2 | 120 sorties with geospatial and kinematic channels | Small | [PMC13570879](https://pmc.ncbi.nlm.nih.gov/articles/PMC13570879/) |
| 6 | PX4 index (flight-mode durations per log) | Mode-time statistics across 476k logs | UAV | [dbinfo](https://review.px4.io/dbinfo) |

**(c) Engine degradation trajectories**

| Rank | Dataset | Why | Caveat | Source |
|---|---|---|---|---|
| 1 | N-CMAPSS | Run-to-failure, 7 failure modes, operation-dependent damage, health labels | Simulated, commercial high-bypass | [PCoE](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) |
| 2 | PHM 2025 | Snapshots plus cumulative maintenance counts; HPT/HPC shop visit and water-wash targets | Provenance not stated | [PHM 2025](https://data.phmsociety.org/phm-north-america-2025-conference-data-challenge/) |
| 3 | PHM 2024 (turboshaft torque margin) | Turbine health vs torque margin across 7 engines | Shuffled; provenance not stated | [PHM 2024](https://data.phmsociety.org/phm2024-conference-data-challenge/) |
| 4 | C-MAPSS FD001–004 | Simple baseline and negative control | 1 point per cycle | [S3 zip](https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip) |
| 5 | NGAFID pre/post maintenance | Real engine-related issues (intake gasket, cylinder, oil) | Piston engine | [arXiv](https://arxiv.org/pdf/2210.07317) |
| 6 | UCI naval GT | Compressor and turbine decay grid | Simulated steady state | [UCI 316](https://archive.ics.uci.edu/dataset/316/condition+based+maintenance+of+naval+propulsion+plants) |
| 7 | DASHlink disk defect / DSTG HUMS | Rotor-crack and gearbox-crack progression | Rig data | [DASHlink 314](https://c3.ndc.nasa.gov/dashlink/resources/314/); [HUMS2023](https://www.humsconference.com.au/HUMS2023/HUMS2023_Data_Challenge_dataset_description_v1.1.1.pdf) |

**(d) Cross-sensor relationships**

| Rank | Dataset | Why | Caveat | Source |
|---|---|---|---|---|
| 1 | DASHlink Sample Flight Data | 186 real coupled parameters (air data, attitude, surfaces, 4 engines, AP modes) | Civil | [data.gov](https://catalog.data.gov/dataset/flight-data-for-tail-652) |
| 2 | N-CMAPSS | Thermodynamically consistent 14 x_s plus virtual sensors | Model-generated | [arXiv:2003.00732](https://arxiv.org/abs/2003.00732) |
| 3 | NGAFID | Electrical, fuel, engine and air-data coupling | GA | [arXiv](https://arxiv.org/pdf/2210.07317) |
| 4 | ADAPT EPS | 128 sensors with fault injection | Lab | [DASHlink 143](https://c3.ndc.nasa.gov/dashlink/resources/143/) |
| 5 | PX4 ULog / ALFA | IMU, EKF, actuator and power coupling | UAV | [ULog spec](https://docs.px4.io/main/en/dev_log/ulog_file_format.html) |
| 6 | FLEA | Motor current, torque, position, temperature and load | Lab EMA | [FLEA FAQ](https://c3.ndc.nasa.gov/dashlink/static/media/dataset/FLEA_Data_FAQ.pdf) |
| 7 | UCI hydraulic | Pressure, flow, temperature and power | Rig | [UCI 447](https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems) |
| 8 | ESA-AD | Channel groups plus telecommands | Spacecraft | [arXiv](https://arxiv.org/abs/2406.17826) |

**(e) Maintenance-text linkage**

| Rank | Dataset | Why | Caveat | Source |
|---|---|---|---|---|
| 1 | NGAFID + MaintNet | Real flights ↔ 36 logbook-derived classes; 6,169 real problem/action texts | Text withheld in NGAFID; GA | [arXiv](https://arxiv.org/abs/2210.07317); [MaintNet](https://people.rit.edu/fa3019/technical/aircraft.html) |
| 2 | FAA SDRS | JASC/ATA-coded defect reports with problem descriptions, by make/model/part | Civil; reporting bias | [SDRS query](https://sdrs.faa.gov/Query.aspx) |
| 3 | DASHlink MAR (PHM 2013-era) | Event codes plus parameter snapshots → maintenance action; nuisance cases | Unknown industrial domain | [DASHlink 842](https://c3.ndc.nasa.gov/dashlink/resources/842/) |
| 4 | PHM 2025 | Cumulative maintenance counters aligned with sensor snapshots | Provenance not stated | [PHM 2025](https://data.phmsociety.org/phm-north-america-2025-conference-data-challenge/) |
| 5 | NASA ASRS | Narrative safety reports | Not maintenance records | [ASRS](https://asrs.arc.nasa.gov/search/database.html) |
| 6 | NTSB avall | Accident narratives and findings | Rare events | [NTSB](https://data.ntsb.gov/avdata) |

**(f) Real-vs-synthetic discriminator testing**

| Rank | Dataset | Why | Caveat | Source |
|---|---|---|---|---|
| 1 | RflyMAD | Same fault taxonomy and ULog schema across SIL, HIL and real | Multicopter; non-commercial | [RflyMAD](https://rfly-openha.github.io/documents/4_resources/dataset.html) |
| 2 | PX4 public logs | 35,613 PX4_SITL vs ~441k real-board logs, identical format | Mixed vehicles and quality | [dbinfo](https://review.px4.io/dbinfo) |
| 3 | CAFUC2 | Paired real normal plus physics-injected anomalies (same flights) | Injected realism only visually checked | [PMC13570879](https://pmc.ncbi.nlm.nih.gov/articles/PMC13570879/) |
| 4 | DASHlink Tail 687 vs N-CMAPSS | Same real flight conditions, real vs simulated engine channels | Different engine types (4-engine RJ vs CMAPSS turbofan) | [arXiv:2003.00732](https://arxiv.org/abs/2003.00732) |
| 5 | UAV Attack | SIL/HIL vs live, with attacks | Small | [IEEE DataPort](https://ieee-dataport.org/open-access/uav-attack-dataset) |
| 6 | C-MAPSS (known-synthetic) vs DASHlink (known-real) | Sanity control for the discriminator | Trivially separable | [Saxena 2008](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf) |

### Gaps — (c) Open questions
1. DASHlink: the exact 186-parameter list, per-parameter rates (the 0.25–16 Hz claim) and units; the reason for the 2009–2010 file dates; why Tail 679 is absent; the airframe type.
2. N-CMAPSS public release: sampling rate, presence of virtual sensors and θ, exact unit counts per DS (including DS02); MDPI blocked.
3. Real vs simulated origin of PHM 2024 (helicopter turboshaft) and PHM 2025 (engine maintenance).
4. Airbus helicopter validation labels: file name and availability.
5. TU Delft Citation II (PH-LAB) public flight-test data: existence, licence, rates.
6. Public fighter or military data:
   - NASA Armstrong fighter time histories exist only as report plots (see `candidate_airframe_modelling_data.md`).
   - DSTG fighter usage data is not public.
   - IAF ADS-B visibility is unknown.
7. ArduPilot public log corpora; an engine test-cell dataset (none found); VIPR or other NASA engine ground-test data (not found on DASHlink).
8. Licences not stated: ESA-AD, DASHlink, PHM Society terms, PADRE, CWRU, SMAP/MSL data. The NGAFID CC-BY vs GPL conflict needs resolving with the authors.
9. Broad Kaggle, Mendeley, IEEE DataPort and Harvard Dataverse sweep not performed because WebSearch was unavailable. A follow-up session with search should run it.
10. GATS dataset (cites NGAFID): authors, content and access unresolved.

### Inferences — (d) Recommended first datasets to acquire (in order, with verified sizes)

**Core set**
1. **DASHlink Tail 687**: 9 zips, **7.15 GB**. Start with `Tail_687_1.zip` (~0.84 GB) to confirm the parameter list and rates. Then add a second tail for tail-to-tail variation (e.g. Tail 652, 6.10 GB) and the curated 4-class npz (**1.6 GB**) as a labelled approach benchmark — [project 85](https://c3.ndc.nasa.gov/dashlink/projects/85/); [res. 1018](https://c3.ndc.nasa.gov/dashlink/resources/1018/)
2. **N-CMAPSS**: **15.76 GB**. This is the degradation backbone and pairs with Tail 687 — [S3](https://phm-datasets.s3.amazonaws.com/NASA/17.+Turbofan+Engine+Degradation+Simulation+Data+Set+2.zip)
3. **NGAFID**: `all_flight.tar.gz` **4.29 GB**, plus `2days.tar.gz` **1.13 GB**, plus the **MaintNet aviation CSV** (6,169 rows) for maintenance linkage — [Zenodo](https://doi.org/10.5281/zenodo.6624956); [MaintNet](https://people.rit.edu/fa3019/technical/aircraft.html)
4. **PX4 public-log index**: **32.6 MB gz**. Then a targeted download, via the rate-limited script, of fixed-wing/VTOL logs labelled crash, error or vibration (a few GB) and a matched PX4_SITL subset — [dbinfo](https://review.px4.io/dbinfo); [download_logs.py](https://raw.githubusercontent.com/PX4/flight_review/main/app/download_logs.py)
5. **RflyMAD**: Real-No Fault **0.97 GB**, Real-Sensors **4.01 GB**, HIL-No Fault **1.41 GB**, SIL-No Fault **1.64 GB**, for a first discriminator test — [RflyMAD](https://rfly-openha.github.io/documents/4_resources/dataset.html)
6. **CMU ALFA processed**: **272 MB** (raw 721 MB optional) — [Figshare](https://doi.org/10.1184/R1/12707963)

**Second tier**
7. **ESA-AD Mission1**: **3.78 GB** — [Zenodo](https://doi.org/10.5281/zenodo.12528696)
8. **Airbus helicopter**: **1.04 GB** — [handle](http://hdl.handle.net/20.500.11850/415151)
9. **Small controls and quick wins**:
   - UCI hydraulic **73.1 MB**
   - C-MAPSS **12.4 MB** (negative control)
   - PHM 2025 (**7.8 + 6.1 MB**) and PHM 2024 (**22.6 MB**)
   - FLEA `2010_09_02` (**294 MB**)

   Sources: [UCI 447](https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems); [PHM 2025](https://data.phmsociety.org/phm-north-america-2025-conference-data-challenge/); [FLEA](https://c3.ndc.nasa.gov/dashlink/resources/908/)

**Time-critical action**
10. **Register for DSTG HUMS2027 before 31 Oct 2026**. The dataset page lists 323 MB; data is restricted and non-shareable — [HUMS2027 access](https://www.humsconference.com.au/HUMS2027datachallenge/download.html)

**Optional**
11. **adsb.lol**: 2–3 sample days filtered by the military `dbFlags` bit. About 6.4 GiB/day [ASSUMPTION: 1,835 GiB ÷ ~285 days of 2026] — [adsb.lol](https://www.adsb.lol/docs/open-data/historical/)
12. **CAFUC2** (Zenodo 19124264): small CSVs, size not retrieved — [Zenodo](https://zenodo.org/records/19124264)
