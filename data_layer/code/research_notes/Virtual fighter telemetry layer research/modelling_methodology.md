# Modelling methodology for the Phalanx virtual-fighter telemetry layer: which approach fits which behaviour, and how to structure it modularly and reproducibly

Scope: this note covers how each behaviour of a virtual fighter (environment, flight dynamics, engine, utility systems, sensors interface, mission/pilot behaviour) should be modelled. It weighs first-principles physics, engineering relations, system identification (SI), state-space, empirical/lookup/envelope, statistical, time-series, learned ML and hybrid physics+ML approaches on accuracy, data needs, identifiability, computational cost and how easily each can be validated. It also covers modular co-simulation and reproducibility. Adjacent topics are left to parallel researchers and cross-linked: platform selection, engine data, datasets, sensor residual texture, faults/degradation, validation/calibration, maintenance records, data pathway/formats and flight profiles.

Evidence tags:
- **[DIRECT]**: evidence from fighter or military aircraft modelling, or from military standards.
- **[TRANSFER: domain]**: evidence from another domain. The note says why it transfers and where it stops applying.
- **[ASSUMPTION]**: my engineering judgement, not established by a source.

Process notes:
- Primary PDFs and source files I read are saved under `/Users/abishaikc/Phalanx/research_sources/methodology/`. They are only read, never executed.
- The shared web-search budget (200 calls per turn) ran out partway through the work. After that, claims were checked only by fetching known primary URLs directly or by reading downloaded documents.
- Claims supported only by a search-result summary, without the source being opened, are marked "(search-summary only)".

---

## 1. Atmosphere and environment: standard, climatic-extreme and real-weather atmospheres, humidity, turbulence, gusts and wind shear

### Takeaway
Use deterministic, standard-defined models for the baseline atmosphere (USSA-1976/ISA) and for climatic extremes (MIL-HDBK-310 profiles and envelopes). Use specification-defined stochastic forming filters for turbulence (von Kármán preferred, Dryden acceptable; MIL-F-8785C / MIL-HDBK-1797), and the 1−cosine and log-profile forms for discrete gusts and low-altitude shear. Drive realism at Indian bases with real data rather than ML:
- ERA5 reanalysis for upper-air structure.
- IGRA radiosondes as point "truth".
- METAR/ISD for surface conditions.

Humidity measurably changes engine performance, so carry it as a first-class state into the engine model, for example pyCycle's water-to-air ratio input. None of these environment behaviours needs ML. The evidence favours standards plus data replay.

### Cited Findings

**Standard atmosphere**
- [DIRECT: US government standard] U.S. Standard Atmosphere 1976 (NASA-TM-X-74335 / NOAA-S/T 76-1562) tabulates properties to 1000 km in SI units. It "is identical with the ICAO Standard (1964) up to 32 km and the ISO Standard (1973) to 50 km." Sources: [EverySpec record](https://everyspec.com/NASA/NASA-General/NASA_TM-X-74335_37294/) (description) and [NTRS record 19770009539](https://ntrs.nasa.gov/citations/19770009539) (abstract, Parts 1–4).
- [DIRECT: tooling] Open-source implementations:
  - `ussa1976`: implements NASA-TM-X-74335, MIT licence, outputs 14 variables. [ussa1976 docs](https://ussa1976.readthedocs.io/)
  - `ambiance`: ICAO 1993 atmosphere to 80 km, Apache-2.0 (search-summary only). [ambiance docs](https://ambiance.readthedocs.io/en/stable/)
  - pyCycle ships its own `US1976.py` element. [pyCycle elements directory](https://github.com/OpenMDAO/pyCycle/tree/master/pycycle/elements)

**Climatic extremes (MIL-HDBK-310 / MIL-STD-210C)**
- [DIRECT] MathWorks implements MIL-HDBK-310 (23 June 1997) and MIL-STD-210C (9 Jan 1987). [atmosnonstd](https://www.mathworks.com/help/aerotbx/ug/atmosnonstd.html) (Specification parameter) and [Non-Standard Day 310 block](https://www.mathworks.com/help/aeroblks/nonstandardday310.html) (Description, Limitations).
  - Extreme parameters: high/low temperature, density and pressure. Frequencies: 1%, 5%, 10%, 20% and "extreme values".
  - Two model types:
    - "Profile" is "recommended for simulation of vehicles vertically traversing the atmosphere".
    - "Envelope" gives the per-altitude extreme, for near-constant-altitude flight.
  - Data cover 0–80 km. Some envelope cases are held between about 1 and 30 km because the handbook lacks data. Data south of 60°S are excluded. The metric and English tables disagree at some altitudes. No humidity extreme is exposed in this implementation.
- [DIRECT; search-summary only] The aircraft "Hot / Tropical / Standard / Polar / Cold Day" vocabulary and the 1%/5%/10%/20% hot/cold days are mapped to MIL-HDBK-310 paragraphs 5.3.1.x and Tables XIX/XX by SAE AS210, which notes that the originating military specs are no longer in force. [SAE AS210](https://saemobilus.sae.org/content/AS210) (page would not render, so not verified).

**Turbulence**
- [DIRECT] MathWorks Dryden and von Kármán blocks implement MIL-F-8785C, MIL-HDBK-1797 and MIL-HDBK-1797B. Sources: [Dryden (continuous)](https://www.mathworks.com/help/aeroblks/drydenwindturbulencemodelcontinuous.html) and [von Kármán (continuous)](https://www.mathworks.com/help/aeroblks/vonkarmanwindturbulencemodelcontinuous.html) (Description, Algorithms, Limitations).
  - Low altitude (<1000 ft): L_w = h, L_u = L_v = h/(0.177+0.000823h)^1.2 for MIL-F-8785C; σ_w = 0.1·W20, σ_u = σ_v = σ_w/(0.177+0.000823h)^0.4.
  - Medium/high altitude (>2000 ft): L = 1750 ft, σ from an exceedance-probability table with options 2×10⁻¹ to 10⁻⁶ (10⁻² light, 10⁻³ moderate, 10⁻⁵ severe).
  - Linear interpolation between 1000 and 2000 ft.
  - Both generate turbulence by passing band-limited white noise (default sample time 0.1 s) through forming filters. The von Kármán filters are rational approximations of the irrational spectra.
  - Stated limitations: frozen-turbulence assumption; clear-air average; no terrain roughness, lapse rate, wind shear or mean-wind magnitude effects.
- [DIRECT, secondary] Cole & Wickenheiser report that von Kármán "better matches data of continuous turbulence" and that MIL-F-8785C §3.7.1 requires von Kármán "when feasible". Measured low-altitude UAV data showed slightly higher low-frequency amplitudes than Dryden. [arXiv 1905.09954, Ch. 3](https://ar5iv.labs.arxiv.org/html/1905.09954)

**Gusts and wind shear**
- [DIRECT] Discrete gust: MIL-F-8785C "1−cosine" shape with amplitude, length and start time per axis. [MathWorks Discrete Wind Gust](https://www.mathworks.com/help/aeroblks/discretewindgustmodel.html)
- [DIRECT] Leahy (NASA) notes that the MIL-SPEC gives a curve of gust magnitude versus half-wavelength derived from Dryden but "fails to list the equation necessary to reproduce the curve", and derives that equation. [NTRS 20080014847](https://ntrs.nasa.gov/citations/20080014847) (abstract)
- [DIRECT] Wind shear: u_w = W20·ln(h/z0)/ln(20/z0), valid for 3 ft < h < 1000 ft. z0 = 0.15 ft for Category C phases (takeoff, approach, landing) and 2.0 ft otherwise. [MathWorks Wind Shear Model](https://www.mathworks.com/help/aeroblks/windshearmodel.html)

**Humidity**
- [TRANSFER: piston engines, 1933] Brooks & Garlock: water vapour acts as an inert diluent, and the humidity effect at altitude up to 25,000 ft equals the sea-level effect. This led NACA to include humidity in its standard correction basis. [NTRS 19930091500](https://ntrs.nasa.gov/citations/19930091500) (abstract)
- [TRANSFER: 200 lbf micro-turbojet, altitude test cell] KARI measured net thrust −2.826% and SFC +1.325% in wet versus dry air. The effect was largest at "summer sea level, high flight Mach number and low engine rpm". [Lee et al. 2010, KoreaScience](https://koreascience.or.kr/article/JAKO201074648803472.do) (abstract). This transfers only qualitatively to a low-bypass afterburning turbofan.
- [TRANSFER: CF6 commercial turbofans; search-summary only] A TU Delft thesis reports that EGT at identical N1 can drop by up to 12 K across 0–3.1 wt% absolute humidity, that humidity sensitivity varies with power setting, and that airline EGT-margin monitoring does not correct for humidity. [TU Delft repository](https://repository.tudelft.nl/file/File_ca635b96-e396-42c9-825f-3b66cb626278) (link returned 404 when fetched)
- [DIRECT: tool capability] pyCycle's `wet_simple_turbojet.py` example uses CEA thermodynamics with a `WAR` (water-to-air ratio) input. Its comment notes that "DEFAULT TABULAR thermo doesn't include WAR, so must use CEA here". [pyCycle example](https://github.com/OpenMDAO/pyCycle/blob/master/example_cycles/wet_simple_turbojet.py) (lines 14–23)

**Real weather for Indian air bases**
- [DIRECT: data source] ERA5 pressure-level data, CC-BY licence. [CDS ERA5 pressure levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels) and [ECMWF ERA5 documentation](https://confluence.ecmwf.int/display/CKB/ERA5%3A+data+documentation)
  - Hourly, 1940 to present, 37 levels (1000–1 hPa). Reanalysis on a 0.25° grid; the native HRES is about 31 km.
  - A 10-member ensemble at 3-hourly intervals gives *relative*, not absolute, uncertainty.
  - About 5 days latency for the preliminary ERA5T.
  - Variables include temperature, specific and relative humidity, u/v/w wind and geopotential. Single-level variables include 2 m T/dewpoint, surface pressure, 10/100 m winds, instantaneous 10 m gust and boundary-layer height.
- [DIRECT: data source; my analysis of the station list] IGRA v2 holds radiosonde soundings from more than 2,800 stations. [NCEI IGRA](https://www.ncei.noaa.gov/products/weather-balloon/integrated-global-radiosonde-archive)
  - The station list ([igra2-station-list.txt](https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt)) contains 108 Indian entries; 61 have data into 2025–2026.
  - Active examples: New Delhi/Safdarjung (1930–2026), Jodhpur (1935–2026), Gwalior (1938–2026), Bareilly (1973–2026), Pune (1926–2026), Bengaluru (1926–2026), Srinagar (1962–2026), Guwahati (1956–2026), Barmer and Jaisalmer (2015–2026).
  - Ended or historic-only: Ambala (to 2021), Jamnagar (1973–1975 only), Tezpur (1973–1975 only).
- [DIRECT: data source] The Iowa Environmental Mesonet `IN__ASOS` network lists 145 Indian METAR stations. [IEM network table](https://mesonet.agron.iastate.edu/sites/networks.php?network=IN__ASOS)
  - Includes Air Force stations: VAJM Jamnagar AFS (archive from Nov 2022), VAOZ Nasik Ojhar AFS, VEAB Allahabad Bamrauli AFS, VEKU Silchar Kumbhigram AFS, VISP Saharanpur Sarsawa AFS.
  - Also VIJO Jodhpur, VIGR Gwalior, VAPO Pune, VOBG Bengaluru.
  - VIAX Adampur is not listed.
  - A third-party description states IEM performs little QC (search-summary only). [Earth2Studio IEM_ASOS docs](https://nvidia.github.io/earth2studio/main/modules/generated/data/dataframe/IEM_ASOS/)
- [DIRECT: data source] NOAA ISD merges hourly and synoptic surface observations (METAR, SYNOP, AWS) from more than 100 sources and more than 20,000 stations. [NCEI ISD](https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database)

### Inferences
- [ASSUMPTION] Recommended environment stack:
  - USSA-1976 as the reference/default.
  - MIL-HDBK-310 1% / 10% hot and cold profiles as named "test atmospheres" for envelope stress.
  - An "observed atmosphere" mode: ERA5 profiles interpolated to base lat/lon/time, with surface values overridden by METAR/ISD at the airfield and IGRA used for validation.
  
  This keeps every atmospheric state traceable to a public source and lets the PHM layer see realistic seasonal and diurnal OAT and humidity cycles. Examples: Rajasthan summer for Jodhpur/Barmer, winter fog season in the Indo-Gangetic plain, monsoon humidity.
- [ASSUMPTION] Turbulence should be a separate stochastic module with its own random stream (section 8). Use the von Kármán forming filter for production runs and Dryden for cheap tests. Choose intensity class by sampling exceedance probability per sortie, or tie it to ERA5 boundary-layer height and wind.
  - The turbulence time step must be decoupled from the 0.1 s default noise sample. Generate noise at the airframe frame rate so that the band-limited spectrum covers the airframe and structural modes of interest.
- [ASSUMPTION] Humidity should flow from ERA5/METAR dewpoint into the engine module as specific humidity or WAR. The KARI and TU Delft results show effects of the same order as engine-to-engine scatter, about 1–3% thrust and up to about 12 K EGT. Ignoring humidity would therefore plant a confounder in exactly the variables PHM uses.
- ERA5 resolution (about 31 km, hourly) cannot represent turbulence, convective gusts or microbursts. Stochastic turbulence must be superimposed on ERA5 mean winds rather than replaced by them. [ASSUMPTION, based on the ERA5 resolution cited above]

### Gaps
- No source found on thermals or convective-updraft models relevant to fighter operations, or on Indian-specific turbulence or wind-shear climatology. The search budget ran out before this could be pursued.
- MIL-F-8785C, MIL-HDBK-1797 and MIL-HDBK-310 full texts were not read directly. Parameter values come from MathWorks implementations and secondary sources. MathWorks notes metric/English inconsistencies in its MIL-HDBK-310 tables.
- Humidity sensitivity for low-bypass mixed-flow afterburning engines specifically (F404/RM12/AL-31FP) was not found. Cross-link: engine-data researcher.
- How well ERA5 matches Indian radiosondes in the boundary layer was not checked. IGRA-vs-ERA5 comparison is a natural validation task for the validation/calibration researcher.

---

## 2. Flight dynamics: 6-DOF, aerodynamic data, flight control and actuators, landing gear, open-source frameworks, pilot/guidance models and numerical integration

### Takeaway
Fighter flight dynamics should be first-principles rigid-body equations of motion (quaternions; flat-Earth acceptable for short sorties, rotating WGS-84 available at little cost) driven by *empirical* aerodynamic lookup tables. Public fighter aero databases exist for the F-16 (NASA TP-1538 wind-tunnel data) and the F/A-18 HARV (NASA TM-110216).

JSBSim is a credible open-source core. It has:
- a rotating-Earth quaternion EOM;
- a default 120 Hz frame;
- an F-16 model built on TP-1538 data with a FLCS-like control system and spring/damper gear;
- Python wheels;
- NASA NESC F-16 verification check cases available in DAVE-ML.

Its engine model, however, is an Aero-Matic thrust-fraction table and is unsuitable for engine telemetry. A dedicated engine module is required (section 3).

For other airframes, DATCOM and OpenVSP/VSPAERO are only gap-fillers: they are weak at high angle of attack and in transonic flow. NASA fighter simulations ran at 80 Hz with RK2 and discretised actuators. Pilot behaviour for data generation is best handled by a guidance/autopilot layer, with crossover-model behaviour added where a human-like tracking signature is wanted.

### Cited Findings

**JSBSim core**
- [DIRECT: tooling] JSBSim is a C++, XML-configured, LGPL-2.1 flight dynamics model. Binary Python wheels are available (`pip install jsbsim`, Python 3.10–3.14). It can run in standalone batch mode or be embedded, and has a MATLAB S-function interface; the README does not mention FMU export. [JSBSim README](https://github.com/JSBSim-Team/jsbsim)
- [DIRECT: tooling, from source] Equations of motion. [FGPropagate.h / FGPropagate.cpp](https://github.com/JSBSim-Team/jsbsim/blob/master/src/models/FGPropagate.cpp) (class documentation; constructor lines 91–94; `Integrate()` lines 338–420), [FGFDMExec.cpp](https://github.com/JSBSim-Team/jsbsim/blob/master/src/FGFDMExec.cpp) (line 101) and [FGInertial.h](https://github.com/JSBSim-Team/jsbsim/blob/master/src/models/FGInertial.h) ("Starting conversion to WGS84").
  - "The integration accounts for a rotating Earth."
  - State is held in ECEF/ECI with an attitude quaternion.
  - Default integrators: rotational rate and position use rectangular Euler, translational rate uses Adams–Bashforth 2, translational position uses Adams–Bashforth 3.
  - Selectable alternatives: trapezoidal, AB2–AB5, Buss1/2, local linearisation.
  - Default time step `dT = 1.0/120.0`.
- [DIRECT: tooling, from source] Actuator lag uses the bilinear (Tustin) transform: `ca = dt·a/(2+dt·a)`, `cb = (2−dt·a)/(2+dt·a)`. [FGActuator.cpp](https://github.com/JSBSim-Team/jsbsim/blob/master/src/models/flight_control/FGActuator.cpp) (`InitializeLagCoefficients`)
- [DIRECT: tooling, from source] FCS channels can run at integer sub-rates (`execrate` = 2 runs every other frame, 4 every fourth). [FGFCSChannel.h](https://github.com/JSBSim-Team/jsbsim/blob/master/src/models/FGFCSChannel.h) (lines 58–63)

**JSBSim F-16 model**
- [DIRECT] The JSBSim F-16 model ("General Dynamics F-16A", Block 32, author Erik Hofman, 2001) cites NASA TP-1538 "wind tunnel data", the F-16 Dash-1 and NASA ground-effect reports. [f16.xml](https://github.com/JSBSim-Team/jsbsim/blob/master/aircraft/f16/f16.xml) (fileheader; ground_reactions lines 84–214; flight_control from line 308)
  - FCS built from 3 `pid`, 5 `scheduled_gain`, 11 `switch`, 13 `summer`, 9 `kinematic` and 7 `aerosurface_scale` components.
  - Spring/damper "BOGEY" gear: e.g., nose spring 17,250 lb/ft, damping 4,250 lb/ft/s, friction coefficients 0.8 static / 0.5 dynamic / 0.02 rolling.
  - Fuel tanks with locations, which give fuel-burn CG shift.
- [DIRECT] The F-16 engine in JSBSim, `F100-PW-229.xml`, was generated by "Aero-Matic v 0.8". [F100-PW-229.xml](https://github.com/JSBSim-Team/jsbsim/blob/master/engine/F100-PW-229.xml)
  - Scalar inputs: milthrust 17,800 lb, maxthrust 29,000 lb, BPR 0.4, TSFC 0.74, ATSFC 2.05.
  - Thrust tables (IdleThrust, MilThrust, AugThrust) are fractions versus Mach and density altitude.
- [DIRECT] The FGTurbine class works as follows. [FGTurbine docs](https://jsbsim-team.github.io/jsbsim/classJSBSim_1_1FGTurbine.html)
  - In the Run phase, N2 = IdleN2 + throttle·(MaxN2 − IdleN2), with first-order "Seek" spool lags.
  - Oil temperature is set to 366 K in Run.
  - EGT equals total air temperature when the engine is off.

**Public fighter aerodynamic data**
- [DIRECT] NASA TP-1538 (Nguyen et al., Dec 1979) is a piloted-simulation study using F-16 wind-tunnel data. It covers relaxed static stability, inertia-coupling pitch departures and deep-stall trim. [NTRS 19800005879](https://ntrs.nasa.gov/citations/19800005879) (abstract)
- [DIRECT; search-summary only] The University of Minnesota F-16 package's high-fidelity tables span α −20° to 90° and β ±30°, from TP-1538. [UMN SEC software page](https://dept.aem.umn.edu/~balas/darpa_sec/SEC.Software.html)
- [DIRECT; search-summary only] A 2026 Nguyen & Lowenberg package reimplements TP-1538 in Julia, MATLAB and Simulink with 4th-, 8th- and 12th-order variants, trim, linearisation and sweeps. [MRF proceedings](https://mrforum.com/product/9781644904251-263/)
- [DIRECT] Morelli fitted the F-16 subsonic (16%-scale) wind-tunnel database with multivariate orthogonal-function polynomials. The result showed "less than 10% difference" from the tabulated data for a doublet at 10° α, Mach 0.26, sea level. Analytic partial derivatives give global LPV models. [Morelli, NTRS 20040110310 PDF](https://ntrs.nasa.gov/api/citations/20040110310/downloads/20040110310.pdf) (abstract; Results)
- [DIRECT] NASA TM-110216 (Messina et al., 1996) describes the f18harv batch simulation. [NTRS 19960027892](https://ntrs.nasa.gov/citations/19960027892) (§1, §2 ACSL description, §4.1, §5.2)
  - Aero database spans α −10° to +90°, β ±20°, Mach 0–2.0 and 0–60,000 ft. Dynamic increments come from forced-oscillation and rotary-balance wind-tunnel rigs.
  - Integration: ACSL RK2 with maximum step 0.0125 s (80 Hz). "No systematic investigation of integration methods has been made."
  - The digital control law runs as an 80 Hz DISCRETE block.
  - Sensor models include actual sample rates (α probe updated at 40 Hz; INS outputs delayed to 40 Hz), INS lever-arm correction, a 5 Hz rate filter and a 2.5 Hz acceleration filter.
- [DIRECT] HARV flight-versus-full-scale-wind-tunnel pressure distributions at α = 30°, 45° and 60° showed "very good agreement", with minor forebody vortex differences. [NTRS 19950007817](https://ntrs.nasa.gov/citations/19950007817) (abstract)

**Gap-filler aero tools**
- [DIRECT] JSBSim's FAQ ranks aero data sources in order: flight test first; then wind tunnel or CFD; DATCOM/DATCOM+ "if no flight test data is available"; Aeromatic as a quick start. It warns "the model is only as good as the time and effort spent in preparing it." [JSBSim FAQ](https://jsbsim.sourceforge.net/FAQ.html)
- [DIRECT] USAF Datcom validation (AFWAL-TR-84-3084): "lack of test data prevented validation of several empirical methodologies (e.g., Subsonic High Angle-of-Attack Pitching Moment and Transonic Pitching Moment)". [Sharpes 1985, IIT Contrails](https://contrails.library.iit.edu/item/162306)
- [DIRECT; secondary, low confidence] Blake (AIAA-85-4070) compared Digital DATCOM dynamic derivatives for four fighters against wind tunnel and flight data. Most were within criteria except subsonic yaw damping. [Scribd copy](https://www.scribd.com/document/618727557/Datcom-Fighter) (search-summary only)
- [TRANSFER: general aircraft] VSPAERO is a linear potential-flow vortex-lattice/panel solver. OpenVSP 3.45.0 made stall "an implicit part of the solution" but advises users to "tread carefully" and repeat prior validation studies. [OpenVSP 3.45.0 release](https://openvsp.org/blogs/?p=763). A 2021 thesis found results reliable only "if the simulation is set up with care" and tested mostly simple wings (search-summary only). [Mariën thesis](https://www.fzt.haw-hamburg.de/pers/Scholz/arbeiten/TextMarien.pdf)

**Other frameworks and EOM choices**
- [TRANSFER: UAV autopilots] ArduPilot SITL can use standard JSBSim releases as its flight dynamics backend. The default model is the Rascal110 RC aircraft. [ArduPilot SITL with JSBSim](https://ardupilot.org/dev/docs/sitl-with-jsbsim.html)
- [DIRECT: tooling] Simulink Aerospace Blockset offers two kinds of 6-DOF block:
  - Flat-Earth blocks treat the flat-Earth frame as inertial ("an excellent approximation"), with constant mass/inertia unless a variable-mass block is used. [6DOF (Euler Angles)](https://www.mathworks.com/help/aeroblks/6dofeulerangles.html)
  - The ECEF quaternion block models a WGS-84 rotating ellipsoid with Coriolis and centrifugal terms and neglects precession, nutation and polar motion. [6DOF ECEF (Quaternion)](https://www.mathworks.com/help/aeroblks/6dofecefquaternion.html)

**Verification resources**
- [DIRECT] NASA NESC check cases (NESC-RP-12-00770; NASA/TM-2015-218675) cover 17 atmospheric cases. [NESC 2015 check cases](https://nescacademy.nasa.gov/flightsim/2015)
  - F-16 cases include subsonic and supersonic trim flyouts, altitude/airspeed/heading/lateral steps and circumnavigation of the North Pole and equator.
  - Models are encoded in DAVE-ML.
  - Seven tools ("several NASA and one open-source") were compared by over-plotting and difference-plotting. The page does not name the open-source tool.
- [DIRECT] DAVE-ML is "an XML application to encode complete flight vehicle dynamic models", following ANSI/AIAA S-119-2011 naming, axis and table conventions. [daveml.org](https://daveml.org/)

**Pilot models**
- [DIRECT] The crossover model (McRuer & Krendel, AGARDograph 188) is Yp·Yc ≈ ωc·e^(−τs)/s. Typical ωc is 1–10 rad/s and τ is 0.1–0.2 s. It is valid only near crossover and not for discrete step inputs. [MathWorks Crossover Pilot Model](https://www.mathworks.com/help/aeroblks/crossoverpilotmodel.html)
- [DIRECT] Bachelder et al. (NASA Ames/Army):
  - A variable time delay explains extra phase lag with lead equalisation.
  - Hess's Structural Model adds an injected "remnant" to represent nonlinearity and time variation "in quasilinear fashion".
  
  [NTRS 20180001222 PDF](https://ntrs.nasa.gov/api/citations/20180001222/downloads/20180001222.pdf) (§I–II)

**Integration and step size**
- [TRANSFER: general real-time simulation; search-summary of MathWorks doc] Real-time targets need fixed-step, fixed-cost solvers. Higher-order methods can force larger steps. Explicit methods are unstable on stiff networks. [MathWorks Solvers for Real-Time Simulation](https://www.mathworks.com/help/simscape/ug/solvers-for-real-time-simulation.html)

### Inferences
- [ASSUMPTION] Recommended flight-dynamics core:
  - JSBSim (C++ core driven from Python) for EOM, aero tables, FCS and gear, run at a fixed 120 Hz. This exceeds the 80 Hz NASA HARV precedent.
  - Actuators discretised with Tustin. These are A-stable, so fast actuators do not destabilise at 120 Hz, but phase is distorted near Nyquist. Fast actuator modes that matter for hydraulic telemetry can be sub-stepped inside the actuator module.
  - Set all four JSBSim integrators explicitly in config rather than relying on defaults, and record them in the run manifest.
- [ASSUMPTION; DIRECT evidence base] Platform-dependent aero source:
  - **F-16:** TP-1538 tables. They are low-speed; supersonic coverage in JSBSim f16.xml must be checked against provenance.
  - **F/A-18:** HARV TM-110216 tables.
  - **Tejas/Gripen/Su-30:** no public database was found. An F-16 or F-18 database would have to be adapted (scaled, re-referenced) or estimated with DATCOM/VSPAERO, and labelled as low-fidelity at high α and transonic Mach.
  
  Cross-link: platform-selection researcher. Evidence richness favours F-16 or F/A-18, and the F/A-18 shares the F404 engine family with Tejas.
- [ASSUMPTION] Do not use JSBSim's FGTurbine outputs (EGT, oil temperature, N1/N2) as telemetry. Oil temperature is a constant 366 K and spools are linear in throttle. Couple JSBSim's thrust and fuel flow to an external engine module that returns thrust and fuel flow, using JSBSim's "direct" thruster or an external-reactions input.
- [ASSUMPTION] Pilot/mission behaviour should be a deterministic guidance layer (waypoints, manoeuvre segments such as climb, cruise, ACM turns, ground attack and recovery) feeding autopilot loops through the FCS. An optional human-pilot stochastic overlay (crossover-type gain and delay plus remnant noise) gives realistic stick-input texture. Cross-link: flight-profiles researcher.
- Verification path [ASSUMPTION]:
  1. Reproduce the NESC F-16 check cases in our JSBSim configuration (both flat- and round-Earth).
  2. Reproduce published TP-1538 / HARV trim points.
  3. Treat any later aero-table edits as versioned data with regression checks.

### Gaps
- Not verified whether JSBSim was the open-source tool in the NESC comparison, or whether f16.xml covers supersonic Mach with traceable data.
- No public aerodynamic database found for Tejas, Gripen or Su-30MKI.
- No primary-source quantification found of Digital DATCOM error for fighter static coefficients at high α. Only the Datcom validation gaps above and a secondary summary for dynamic derivatives.
- Manoeuvre-automaton and trajectory-generation literature for fighters was not researched after the search budget ran out. Defer to the flight-profiles researcher.
- Stevens/Lewis/Johnson (F-16 actuator 20.2/(s+20.2), ±25°, 60°/s) could not be verified from a primary source. TensorAeroSpace documents ±25° and 60°/s (search-summary only). [TensorAeroSpace F-16 docs](https://tensoraerospace.readthedocs.io/en/latest/model/f16/)

---

## 3. Engine performance and dynamics: 0-D component models, maps, mixed-flow afterburning turbofans, transients, linear/state-space and on-board models, data-driven and hybrid engine models, control logic, thermal and vibration

### Takeaway
The evidence favours a **physics-based 0-D component-level model (CLM)** as the engine "truth" generator. It should use scaled component maps, shaft-inertia ODEs, controller schedules, limiters and MIN-MAX selection, and lumped thermal states such as hot-section metal temperature and heat-soak/tip-clearance debits.

The NASA model families document exactly this pattern:
- MAPSS: a *military low-bypass mixed-flow afterburning* engine at 2,500 Hz with a 50 Hz controller.
- C-MAPSS/C-MAPSS40k: 13 health parameters, sensor and actuator dynamics, stall-margin debits, validated against flight test.

Open, scriptable options are:
- pyCycle: steady-state design/off-design, with a mixed-flow afterburning turbofan example and humidity (WAR) support.
- T-MATS: Simulink, Newton–Raphson, dynamic examples.

Both use demonstration maps that must be scaled and treated as assumptions.

Cheaper representations each have documented accuracy costs:
- Table plus first-order lag: NASA F404 model within 3% steady state but only within 25% in transients.
- Piecewise-linear state-space: residuals grow in transients, and stall margin linearises poorly.

These are valid as fast surrogates, not as truth. Data-driven engine models (NARX, LSTM, neural ODE) have no public fighter-engine training data, so they cannot be the primary generator. Hybrid models such as eSTORM have value for on-board *estimation*, which is the PHM side, not for generation.

### Cited Findings

**MAPSS (military engine)**
- [DIRECT] Parker & Guo describe MAPSS. [NASA/TM-2003-212543, NTRS 20030093721](https://ntrs.nasa.gov/citations/20030093721) (Engine Model Description) and [NTRS 20100021296](https://ntrs.nasa.gov/citations/20100021296) (abstract)
  - The engine is a "modern high-pressure ratio, dual-spool, low bypass, military-type engine".
  - Components: fan with variable inlet stators, booster, HPC, double-annular combustor, HPT/LPT, **mixer, afterburner**, nozzle, forward blocker doors and an aft VABI (variable-cycle capability).
  - CLM states: LP and HP rotor speeds and "average hot section temperature (i.e. metal temperature)". Each step iterates to "mass, energy, and momentum balance within a certain tolerance".
  - Actuator lags are modelled. The original FORTRAN model ran at 50 Hz.
  - In MAPSS, the CLM runs at 2,500 Hz and the controller at 50 Hz.

**NASA F404 models in fighter simulations**
- [DIRECT] Johnson (NASA TM-4240, AIAA 90-2166) built a simple dynamic F404-GE-400 model for the F-18 HARV simulator. [NTRS 19910009766](https://ntrs.nasa.gov/citations/19910009766) (abstract)
  - It uses "tabular data generated from a complete nonlinear dynamic engine model supplied by the manufacturer", with dynamics from "a throttle rate limiter and low-pass filter".
  - Accuracy: "within 3 percent of the steady state response, and within 25 percent of the transient response" of the full model, at M 0.2 and 0.7, 35,000 ft.
- [DIRECT] The HARV simulation's F404 model works as follows. [TM-110216 §4.1](https://ntrs.nasa.gov/citations/19960027892)
  - Table lookup on lagged PLA, Mach and altitude: 12 Mach × 7 altitude grids at idle, mil, min-AB and max-AB for gross thrust, ram drag, nozzle area, NPR, turbine discharge pressure, fuel flow and drag. Interpolated every 0.0125 s.
  - Transients: first-order lag on PLA with τ = 0.625 s (non-AB) and 0.55 s (AB), plus increase-only rate limits of 14 and 22 deg/s.
  - Fuel-usage effects on weight, CG and inertia "were neglected".

**C-MAPSS family (commercial engines)**
- [TRANSFER: 40k-lbf commercial turbofan; the method transfers, the numbers do not] C-MAPSS40k is "a physics-based, component-level model". [May et al., NASA/TM-2010-216810, NTRS 20100037767](https://ntrs.nasa.gov/citations/20100037767) (§2.1.1–2.1.3, §2.2.2, §3.3–3.6, §4)
  - Components are represented as infinitesimal volumes balanced by an iterative mass-flow solver, with up to 200 iterations per step; capping at 56 iterations gave real-time on the authors' laptop at reduced accuracy.
  - Shaft speeds integrate torque imbalance. Maps use corrected speed plus "EM-lines" for numerical uniqueness.
  - Sensors: Nf, Nc, T2, T25, T30, T50, P2, P25, Ps30, P50, with user-set Gaussian noise variance.
  - Actuators: fuel valve rate limits and hysteresis plus a 40 ms transport delay; VSV PI loop with 1% backlash.
  - 13 health parameters (flow, efficiency and PR scalars) represent deterioration, and faults appear as abrupt shifts.
  - Transient stall-margin debits cover heat transfer ("slow time decaying heat transfer between the compressor blades and casing"), tip clearance and deterioration.
  - Matched to "dynamic flight test data of a highly instrumented engine".
  - A linearisation routine returns A, B, L, C, D, M (states Nf and Nc; L and M map health parameters) for piecewise-linear models.
- [TRANSFER: commercial] Csank & May describe the C-MAPSS40k control design. [NASA/TM-2010-216811, NTRS 20100037768](https://ntrs.nasa.gov/citations/20100037768) (§3–§5)
  - Gain-scheduled PI setpoint control on EPR or Nf.
  - Limit regulators as PI loops: max Nf/Nc (set at 110% of the highest normal speeds), max Ps3, acceleration schedule, min Ps3, min Wf/Ps3 ratio-unit.
  - A **MIN-MAX** selector: "The minimum fuel flow command is selected since it corresponds to the limiter that is closest to its limit." Integral wind-up protection.
- [TRANSFER: commercial] The C-MAPSS (90k) user guide notes: ideal sensors and actuators by default; 13 health parameters; an example first-order fan-speed sensor at 50 rad/s and FMV at 20 rad/s; and a warning that the supplied controller gains assume no sensor or actuator dynamics. [NTRS 20070034949](https://ntrs.nasa.gov/citations/20070034949) (§4.4)

**Open tools**
- [DIRECT: tool capability] pyCycle's `mixedflow_turbofan.py` builds fan, LPC, HPC, burner, HPT, LPT, **Mixer**, **afterburner** (second `Combustor`) and a CD nozzle with `num_burners=2`. It uses CEA or tabular thermodynamics and design/off-design balances. [pyCycle example](https://github.com/OpenMDAO/pyCycle/blob/master/example_cycles/mixedflow_turbofan.py)
- [DIRECT: tool; from source] pyCycle's `Shaft` element outputs net torque (`trq_net`) with no inertia state. It is a steady-state balance, so transients need an external dN/dt = trq_net/(J·ω) wrapper. [shaft.py](https://github.com/OpenMDAO/pyCycle/blob/master/pycycle/elements/shaft.py)
- [TRANSFER: tool validation] pyCycle results agree with an identical NPSS model "within 0.03%" and give analytic derivatives (search-summary of abstract). [Hendricks & Gray 2019, Aerospace 6(8):87](https://www.mdpi.com/2226-4310/6/8/87)
- [TRANSFER: tool] T-MATS (NASA; MATLAB/Simulink; Apache-2.0). [T-MATS User's Guide, NASA/TM-2014-216638](https://ntrs.nasa.gov/citations/20140012486) (§1, §4.3–4.4, Table 4) and [GitHub](https://github.com/nasa/T-MATS)
  - Newton–Raphson solvers with Jacobian calculation.
  - Map lookups on (Nc, R-line) with linear scalars C_Nc, C_PR, C_Wc, C_Eff.
  - "Default maps and constants in T-MATS are intended only for demonstration."
- [TRANSFER: tool] GasTurb "is also able to simulate transient behavior, taking into account heat soakage and tip clearance effects". It is commercial with a free trial. [gasturb.com](https://www.gasturb.com/)
- [TRANSFER: tool status] GSP "is no longer supported by NLR"; TU Delft provides limited support. [gspteam.com](https://gspteam.com/)

**Transient modelling choices**
- [TRANSFER: general gas turbines; search-summaries only] Intercomponent-volume (ICV) versus constant-mass-flow (CMF) transient methods:
  - Fawke & Saravanamuttoo (SAE 710550) introduced both and reported "good agreement between engine test and simulation". [SAE 710550](https://saemobilus.sae.org/papers/digital-computer-methods-prediction-gas-turbine-dynamic-response-710550)
  - Maccallum's thesis found differences mainly in the HP compressor during variable-geometry movement, with ICV "the more valid". [Glasgow thesis](https://theses.gla.ac.uk/5335/1/2000MaccallumDSc_vol1.pdf)
  - A 2024 summary says ICV is more accurate but needs smaller steps, and CMF is commonly used for initialisation. [MDPI Energies](https://www.mdpi.com/1996-1073/19/6/1465)
- [TRANSFER: generic HPT] Chapman, Kratz, Guo & Litt built a first-principles HPT tip-clearance model (thermal and mechanical deformation of rotor, shroud and blade) integrated with an engine simulation. [NTRS 20160012685](https://ntrs.nasa.gov/citations/20160012685) (abstract)

**Linear, on-board and hybrid models**
- [TRANSFER: commercial] Armstrong & Simon (PHM 2012) extracted a piecewise-linear self-tuning model from C-MAPSS40k. [PHM Society paper](https://papers.phmsociety.org/index.php/phmconf/article/view/2136) (§3.1, §5–6)
  - The PWL model "shows a noticeable increase in the residuals during transients".
  - Highly nonlinear outputs "such as stall margins, may not lend themselves to linearization… large mismatches even when great care is taken".
  - The self-tuning model runs "approximately an order of magnitude faster" than the nonlinear model.
  - Observability requires "at least as many measurements as health parameters", which motivates tuner subsets or optimal linear combinations.
- [TRANSFER: commercial] eSTORM is a hybrid that fuses "a physics-based model approach and an empirical model approach" for on-board performance tracking. [Volponi & Simon, NASA/CR-2008-215272, NTRS 20080032604](https://ntrs.nasa.gov/citations/20080032604)
  - Per a secondary summary, it is a piecewise-linear model plus neural-network output correction, verified on the PW6000 (search-summary only). [MDPI Aerospace 2025](https://www.mdpi.com/2226-4310/12/3/175)
- [TRANSFER: commercial] Connolly et al. used a piecewise-linear on-board model derived from C-MAPSS40k with an optimal-tuner Kalman filter to estimate thrust and stall margin for model-based control. [NTRS 20140009131](https://ntrs.nasa.gov/citations/20140009131)

**Engine-data template**
- [TRANSFER: commercial PHM dataset generation] N-CMAPSS used "real flight conditions as recorded onboard of commercial jets" (altitude, Mach, TRA, T2) as inputs to C-MAPSS. Fleet degradation was modelled as engine-to-engine initial variability (about 10% of health index) plus linear normal degradation, with a smooth transition to steeper abnormal degradation of HPT/LPT efficiency and flow. [Arias Chao et al., arXiv 2003.00732 §4.1](https://arxiv.org/abs/2003.00732)

### Inferences
- [ASSUMPTION; DIRECT evidence from MAPSS and HARV] Use two engine representations behind one interface.
  - **(a) Truth CLM**, a two-spool mixed-flow afterburning turbofan:
    - Built in pyCycle for steady-state design/off-design. Pre-tabulate component maps and off-design "decks", including WAR for humidity.
    - Wrapped with shaft-inertia ODEs, lumped metal-temperature (heat-soak) states, a clearance state, a gain-scheduled PI plus MIN-MAX limiter controller, and actuator/sensor dynamics.
    - Alternative: T-MATS if MATLAB is acceptable.
  - **(b) Fast surrogate:** HARV-style tables plus lag/rate limits, or a C-MAPSS-style PWL state-space model generated from (a). Use it only for flight-dynamics coupling or batch fleet runs, and mark its known transient error envelope (about 25% for the table/lag form).
- [ASSUMPTION] Health-parameter hooks should follow the C-MAPSS convention (flow/efficiency/PR scalars per component), so the faults/degradation researcher's models plug in without touching the thermodynamics. N-CMAPSS shows this produces credible PHM benchmarks. Cross-link: faults/degradation and datasets researchers.
- [ASSUMPTION] Map provenance is the dominant fidelity risk. Generic maps (T-MATS "demonstration", pyCycle default maps) scaled to a published design point reproduce the design point but not the F404/RM12/AL-31FP off-design shape. Store scaled maps as versioned data with a provenance record and sensitivity tests. Cross-link: engine-data researcher.
- [ASSUMPTION] Oil and fuel temperature: model them as lumped-capacitance nodes (heat-to-oil from bearings/gearbox as a function of spool speeds and load, fuel as a heat sink via fuel–oil heat exchangers). The evidence that lumped thermal states belong in engine CLMs is MAPSS's metal-temperature state and the C-MAPSS40k heat-transfer debit. FGTurbine's constant 366 K oil temperature shows that FDM-grade engines cannot supply this telemetry.
- [ASSUMPTION] Vibration: generate tracked-order spectra (1×N1, 1×N2 and harmonics, with amplitude driven by imbalance/fault parameters, plus broadband noise) as a separate module fed by spool speeds. No fighter-specific source was found (see Gaps). Cross-link: sensor-residual-texture and faults researchers.
- Data-driven engine models (NARX/LSTM/neural ODE) need many hours of real engine transients that are not public for fighter engines. As truth generators they would also inherit the ML extrapolation risks in section 6. Their legitimate role is as *surrogates trained on CLM output*, for example to accelerate fleet runs, validated against the CLM. [ASSUMPTION; supported by section 6 and section 7 evidence]

### Gaps
- No public component maps or detailed cycle data were found for F404-GE-IN20, RM12, F110/F100 or AL-31FP. The SAE paper on the GE nonlinear F404 model (SAE 821401) is paywalled. Cross-link: engine-data researcher.
- Quantitative heat-soakage impact on fighter-engine transients was not obtained; the Cranfield papers returned HTTP 403.
- Could not obtain NARX/LSTM/neural-ODE gas-turbine accuracy studies because the search budget was exhausted. This section relies on general ML-extrapolation evidence in section 6.
- Not verified whether MAPSS and C-MAPSS40k are distributable to non-US teams. NASA's catalogue restricts C-MAPSS40k to federal employees and contractors (search-summary only; [NASA software LEW-18624-1](https://software.nasa.gov/software/LEW-18624-1)).
- No source found for rotor-dynamics-informed vibration spectra of fighter engines, or for lubrication-system models suitable for PHM.

---

## 4. Utility systems: hydraulic, fuel, electrical and thermal networks; tooling; fidelity for PHM

### Takeaway
Utility systems are best modelled as **lumped-parameter physical networks** (Modelica Standard Library / ThermofluidStream / Simscape / bond graphs) at the fidelity where fault parameters map to physical quantities: leakage area, friction, blockage factor, accumulator precharge, pump efficiency. The best-documented PHM precedent is physics simulation with parameterised fault severities plus seeded noise, used to train classifiers. Real rig data such as the UCI hydraulic dataset can calibrate texture.

Aircraft-specific open utility-system PHM models were *not* verified in this pass. This is the thinnest evidence area.

### Cited Findings
- [TRANSFER: tooling] The Modelica Standard Library v4.1.0 (BSD-3, commercial use allowed) models "mechanical (1D/3D), electrical (analog, digital, machines), magnetic, thermal, fluid, control systems and hierarchical state machines". [MSL GitHub](https://github.com/modelica/ModelicaStandardLibrary)
- [TRANSFER: thermofluid systems, aeronautics-institute provenance] DLR's ThermofluidStream library (developed by DLR's Institute of System Architectures in Aeronautics) uses a scheme in which "all non-linear equations can be brought into explicit form", for "robust modeling of even complex architectures". It is based on MSL 4.1.0 and largely OpenModelica-compatible. [ThermofluidStream README](https://github.com/DLR-SR/ThermofluidStream); paper: Zimmer, Meißner & Weber, *Electronics* 11(22):3790, 2022.
- [TRANSFER: tooling] BondGraphTools is an Apache-2.0 Python bond-graph toolkit. The repository was archived (read-only) on 18 June 2025. [GitHub](https://github.com/BondGraphTools/BondGraphTools)
- [TRANSFER: industrial pump, Simscape] MathWorks generates fault data from a Simscape triplex reciprocating pump. [MathWorks multi-class fault detection example](https://www.mathworks.com/help/predmaint/ug/multi-class-fault-detection-using-simulated-data.html)
  - Faults: cylinder leak (0–3.6% of max valve area), blocked inlet (factor 0.8–0.53) and bearing friction (0–6e-4), each at 10 severity levels.
  - Single, double and triple fault groups, with noise enabled and a different noise seed per run.
  - Spectral and statistical condition indicators train an SVM: about 90.6% validation accuracy, 100% fault-presence detection. Small blocking faults "cannot be reliably detected".
- [TRANSFER: industrial hydraulic test rig; real data] The UCI "Condition monitoring of hydraulic systems" dataset (Helwig et al. 2015, CC BY 4.0). [UCI dataset 447](https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems)
  - 2,205 cycles of 60 s each.
  - Sensors: pressures and motor power at 100 Hz; flows at 10 Hz; temperatures, vibration and virtual efficiencies at 1 Hz.
  - Graded cooler, valve, internal pump leakage and accumulator conditions.
- [DIRECT] JSBSim's F-16 models fuel tanks (locations, capacities, contents) and gear spring/damper/friction coefficients. [f16.xml](https://github.com/JSBSim-Team/jsbsim/blob/master/aircraft/f16/f16.xml) (propulsion and ground_reactions). The NASA HARV simulation neglected fuel-usage effects on weight, CG and inertia. [TM-110216 §4.1](https://ntrs.nasa.gov/citations/19960027892)

### Inferences
- [ASSUMPTION] Build each utility subsystem (hydraulics A/B, fuel feed/transfer, electrical generation and distribution, ECS/thermal) as its own lumped network module, coupled to the airframe and engine through explicit interfaces:
  - hydraulic demand from actuator rates and loads;
  - generator load from avionics and ECS states;
  - fuel flow from the engine;
  - heat loads to fuel and oil.
  
  Write them in Modelica and export as FMUs, or as small NumPy/Numba ODEs. Pick the fidelity that makes each PHM-relevant fault a physical parameter. Precedent: the triplex-pump example and C-MAPSS health parameters.
- [ASSUMPTION] Calibrate *texture* (noise level, sample rate, cycle variability) against real rig data such as UCI hydraulic. Do not claim aircraft-specific absolute values without aircraft data. Cross-link: datasets and sensor-texture researchers.
- [ASSUMPTION] Utility-system fidelity can be lower than engine fidelity at first. Ordering of priority should follow which subsystems drive availability in the maintenance-records research. Cross-link: maintenance-records researcher.

### Gaps
- Not verified: aircraft-specific open hydraulic, electrical or fuel system models used for PHM, such as more-electric-aircraft Modelica studies or NASA ADAPT-type electrical testbeds. The search budget ran out, and attempted MathWorks aircraft-example URLs returned 404.
- No public fighter hydraulic or electrical architecture parameters were found (pressures, pump displacements, accumulator volumes, generator ratings). These are needed from the platform/engine-data researchers or Flight Manual-level public sources.

---

## 5. System identification: methods, identifiability, and when SI beats first principles

### Takeaway
SI is the established way to turn **flight or wind-tunnel data** into aerodynamic and propulsion models:
- equation-error with stepwise regression or orthogonal functions;
- biased estimators under collinearity;
- subspace methods for LTI state-space.

NASA showed fighter-relevant success: HARV derivatives from flight data at α 10–50°, and F-16 global polynomial models within about 10%. Identifiability failures are documented and concrete: air-data biases, collinearity in manoeuvres, and fewer sensors than health parameters.

For Phalanx there is no access to real IAF flight data. SI's main roles are therefore:
1. compressing the truth models into fast, verifiable surrogates (global polynomials, LPV, piecewise-linear);
2. calibrating against *published* time histories;
3. later, if real data arrive, a principled path to recalibrate.

### Cited Findings
- [DIRECT] Klein, Ratvasky & Cobleigh estimated HARV aerodynamic parameters from flight data at α 10°–50°. [NASA TM-102692, NTRS 19900019262](https://ntrs.nasa.gov/citations/19900019262) (abstract)
  - Data compatibility checks found "accuracy of air data was degraded by unexplained bias errors".
  - Stepwise regression produced the model structure and least-squares estimates.
  - "Because of high data collinearity in several maneuvers", estimates were redone with principal-components regression and mixed estimation.
  - Influential parameters were "estimated with acceptable accuracy and most of them are in agreement with wind tunnel results", and simulated responses predicted well.
- [DIRECT] Morelli's multivariate orthogonal functions on the F-16 wind-tunnel database gave a polynomial global model within 10% for a doublet, and analytic derivatives give global LPV models. [NTRS 20040110310](https://ntrs.nasa.gov/api/citations/20040110310/downloads/20040110310.pdf)
- [TRANSFER: eight aircraft databases] Grauer & Morelli's 45-term "generic nonlinear aerodynamic" model reproduced trim, modal frequencies and damping, "91% accurate state histories and 80% accurate aerodynamic coefficient histories". [NTRS 20140011902](https://ntrs.nasa.gov/citations/20140011902) (abstract)
- [TRANSFER: subscale twin-jet transport] Morelli identified global nonlinear models of all six coefficients "from a single maneuver" and combined them with a propulsion model from engine ground tests to "produce a high-fidelity nonlinear flight simulation very efficiently". [NTRS 20120001458](https://ntrs.nasa.gov/citations/20120001458) (abstract)
- [DIRECT: tooling] NASA SIDPAC (LAR-16100-1, MATLAB) has more than 300 programs for experiment design, data compatibility, modelling, parameter estimation and validation, released to US and foreign users on request. [NASA software catalogue](https://software.nasa.gov/software/LAR-16100-1)
- [TRANSFER: generic tooling] MATLAB `n4sid` is subspace estimation of discrete state-space models from time- or frequency-domain data. Hankel singular values guide order selection. MOESP, CVA and SSARX weightings are available, and SSARX "is better at capturing feedback effects" for closed-loop data. [MathWorks n4sid](https://www.mathworks.com/help/ident/ref/n4sid.html)
- [TRANSFER: commercial engine] Identifiability in engine health estimation: a Kalman filter on augmented health states requires "at least as many measurements as health parameters", and engines usually have fewer sensors than health parameters. [Armstrong & Simon 2012](https://papers.phmsociety.org/index.php/phmconf/article/view/2136) (§3)
- [TRANSFER: commercial engine] C-MAPSS40k's linearisation produces (A, B, L, C, D, M) at a user-chosen point, for piecewise-linear models and controller design. [NTRS 20100037767 §3.3](https://ntrs.nasa.gov/citations/20100037767)

### Inferences
- [ASSUMPTION] SI beats first principles when (i) measured data exist for the exact vehicle and (ii) physics parameters are uncertain. HARV and Morelli show that SI outperforms handbook prediction there. Neither condition holds for an IAF fleet in a hackathon.
- [ASSUMPTION] In Phalanx, SI should be used to:
  - derive fast PWL/LPV surrogates from the CLM and JSBSim, which can be checked against the truth model;
  - fit compact polynomial aero models where table storage or smoothness matters;
  - provide a calibration harness, so that if real FDR/HUMS data become available, the same pipeline re-estimates parameters with documented identifiability diagnostics (collinearity, observability rank, Cramér–Rao bounds).
- [ASSUMPTION] Identifiability checks to include as unit tests:
  - data-compatibility (kinematic consistency) checks on generated sensor streams, which catches unit, sign and bias errors;
  - condition number and collinearity of regressors for any calibrated parameter set;
  - observability rank of health-parameter augmentations versus the sensor set.

### Gaps
- Output-error and filter-error methods (Jategaonkar/DLR), frequency-domain SI (CIFER) and Klein & Morelli textbook content were not verified from primary sources. AIAA pages returned 403 and the search budget ran out. These methods are standard but uncited here.
- No public fighter flight-test time-history dataset suitable for calibration was confirmed in this pass, beyond the HARV and TP-1538 literature. Cross-link: datasets researcher.

---

## 6. Empirical, statistical, time-series and generative ML models: where they fit and documented dangers

### Takeaway
Empirical lookup/envelope models are the *proven* fighter-simulation workhorse for aero and engine-deck behaviour: TP-1538 tables, HARV engine tables, JSBSim tables. Classical statistical and time-series models are appropriate for stochastic texture and regime structure:
- regression and Gaussian processes for small-data emulators (O(n³) cost);
- ARIMA/state-space for coloured noise and drift;
- mixtures and HMMs for regime switching.

Generative deep models (GANs, diffusion, transformers, flows) are the riskiest choice for a *truth* generator. Documented failures include:
- mode collapse and instability;
- no agreed evaluation metrics;
- memorisation and extraction of training data (images);
- physically inconsistent outputs, with high accuracy coexisting with 73% inconsistent time steps;
- poor extrapolation, since ReLU MLPs become linear off-support;
- transformers beaten by one-layer linear models in long-horizon forecasting.

There is also no public fighter telemetry to train them on.

### Cited Findings
- [DIRECT] Fighter simulations use tables: HARV aero (α −10° to 90°, Mach 0–2) and F404 engine tables interpolated at 80 Hz [TM-110216](https://ntrs.nasa.gov/citations/19960027892); JSBSim F-16 aero and thrust tables [f16.xml](https://github.com/JSBSim-Team/jsbsim/blob/master/aircraft/f16/f16.xml).
- [TRANSFER: GP methodology] GP prediction "typically scales as O(n³)", and for n > 10,000 storing the Gram matrix and solving is "prohibitive on modern workstations". [Rasmussen & Williams, GPML Ch. 8](http://gaussianprocess.org/gpml/chapters/RW8.pdf) (opening paragraph)
- [TRANSFER: tooling] statsmodels' state-space module provides SARIMAX, UnobservedComponents, VARMAX, dynamic factor models, Kalman filter and smoother, simulation smoothers and `simulate` methods. [statsmodels statespace](https://www.statsmodels.org/stable/statespace.html)
- [TRANSFER: generative TS] TimeGAN (NeurIPS 2019) argues a good generator "should preserve temporal dynamics" and combines supervised and adversarial objectives in a learned embedding. [Yoon, Jarrett & van der Schaar](https://papers.nips.cc/paper_files/paper/2019/hash/c9efe5f26cd17ba6216bbe2a7d26d490-Abstract.html)
- [TRANSFER: generative TS] Brophy et al. survey of time-series GANs. [arXiv 2107.11098](https://arxiv.org/abs/2107.11098) (§1–2)
  - Challenges: "training stability, evaluation and privacy risk"; GANs "suffer from issues such as non-convergence, diminishing/vanishing gradients, and mode collapse".
  - For time-series GANs "there has not been an agreement reached on the generated data's evaluation metrics".
- [TRANSFER: TS generation benchmarking] TSGBench identifies "ambiguous evaluation measures" and biased dataset choices in time-series generation research, and proposes standardised measures including discriminative and predictive scores. [arXiv 2309.03755](https://arxiv.org/abs/2309.03755) (abstract)
- [TRANSFER: generative TS] Diffusion-TS (ICLR 2024) is a diffusion-based multivariate time-series generator using a decomposition-guided transformer. [arXiv 2403.01742](https://arxiv.org/abs/2403.01742)
- [TRANSFER: images → any generative model trained on scarce real data] Carlini et al. showed "diffusion models memorize individual images from their training data and emit them at generation time", extracting more than a thousand training examples. Diffusion models were "much less private than prior generative models such as GANs". [arXiv 2301.13188](https://arxiv.org/abs/2301.13188) (abstract)
- [TRANSFER: environmental physics] Physics-guided NNs (lake temperature). [Daw/Karpatne et al., arXiv 1710.11431 §4](https://arxiv.org/abs/1710.11431)
  - A black-box NN cut RMSE from 1.69 (physics model) to 1.18 °C but produced physically inconsistent density–depth relations in "almost 73% of the time-steps".
  - Feeding physics output as an input (PGNN0) remained inconsistent about 72% of the time.
  - Only adding a physics-based loss gave RMSE 0.73 with near-zero inconsistency.
- [TRANSFER: ML theory] "ReLU MLPs quickly converge to linear functions along any direction from the origin, which implies that ReLU MLPs do not extrapolate most nonlinear functions." [Xu et al., ICLR 2021, arXiv 2009.11848](https://arxiv.org/abs/2009.11848) (abstract)
- [TRANSFER: forecasting] "LTSF-Linear surprisingly outperforms existing sophisticated Transformer-based LTSF models in all cases, and often by a large margin" on nine real datasets. [Zeng et al., arXiv 2205.13504](https://arxiv.org/abs/2205.13504) (abstract)

### Inferences
- [ASSUMPTION] Assign roles as follows:
  - **Lookup/envelope**: aero coefficients, engine decks, MIL-HDBK-310 atmospheres, schedules and limits. Tables are versioned data.
  - **Regression/GP**: small-data emulators of expensive sub-models, such as CLM off-design points for map sensitivities, only within the sampled domain.
  - **State-space / ARIMA / coloured-noise models**: sensor noise, drift, bias random walks. Cross-link: sensor-residual-texture researcher.
  - **Mixture / HMM**: sortie- and fleet-level regime variability, such as mission-type mix and pilot style clusters, if real or published usage statistics exist. Cross-link: flight-profiles and maintenance-records researchers.
  - **Generative deep models**: not for primary generation. If used at all, use them only to add texture *on top of* physics outputs, trained on public real data, with physics-consistency checks and TSGBench-style discriminative/predictive scores plus memorisation tests.
- [ASSUMPTION] Every learned component needs an explicit validity domain: input bounds and a regime classifier. Outside it the component must refuse or fall back to physics, because ReLU-type models extrapolate linearly.

### Gaps
- No studies found applying GAN or diffusion generation to fighter or engine telemetry with physical-consistency evaluation.
- HMM/regime-switching applications to flight-phase data were not researched (search budget exhausted).
- Mixture-model evidence for operating-regime clustering (for example the C-MAPSS multi-condition subsets) was not verified from a primary source.

---

## 7. Hybrid physics + ML: when hybrids improve fidelity and when they harm it

### Takeaway
Hybrids reliably help when (a) a credible physics model exists, (b) the ML part is restricted to a well-posed residual or parameter role, and (c) training covers the deployment distribution. In aerospace PHM, physics-calibrated health parameters fed to deep nets improved turbofan RUL accuracy by 16–47% RMSE and extended the prediction horizon by about 127% on N-CMAPSS.

Hybrids harm in four documented ways:
- **Non-identifiability:** the ML term can absorb the physics, F = Fp + Fa is "not unique", and the physical parameters lose meaning.
- **Distribution shift:** hybrid guarantees are "limited to the training distribution".
- **Unconstrained residual learning:** it cannot enforce physics.
- **PINN soft constraints:** they make optimisation ill-conditioned.

Also: "Data generation applications also do not make sense for residual modeling."

For Phalanx's *generator*, hybrids are therefore a later-stage calibration tool, used once real data exist. They are not a substitute for physics.

### Cited Findings
- [TRANSFER: commercial turbofan PHM; synthetic C-MAPSS data] Hybrid prognostics (physics-model calibration of unobservable health parameters, then a DNN with physics-augmented features) versus purely data-driven. [Arias Chao et al., arXiv 2003.00732](https://arxiv.org/abs/2003.00732) (abstract; §5 Tables 5–6)
  - RMSE reduced 16–47% and s-score 21–68%.
  - Average prediction horizon increased 127%.
  - Required less training data and was less sensitive to unrepresentative training flights.
- [TRANSFER: commercial engine] eSTORM: a hybrid of a physics-based and an empirical model for on-board engine performance tracking. [NTRS 20080032604](https://ntrs.nasa.gov/citations/20080032604)
- [TRANSFER: dynamical systems ML] APHYNITY: "The decomposition F = Fp + Fa is in general not unique… all the dynamics could be captured by the Fa component." If only existence is guaranteed, "the identified physical parameters are not uniquely determined". The authors minimise ‖Fa‖ to restore uniqueness. [Yin et al., arXiv 2010.04456 §3](https://arxiv.org/abs/2010.04456)
- [TRANSFER: dynamical systems ML] "Hybrid model performance guarantees are limited to the training distribution". APHYNITY "is unable to predict accurately… for a shifted test distribution", which motivates "expert augmentation". [Wehenkel et al., TMLR 2023, arXiv 2202.03881](https://arxiv.org/abs/2202.03881) (abstract; Fig. 1)
- [TRANSFER: statistics of computer-model calibration] The Kennedy–O'Hagan GP-discrepancy calibration "may lead to unreasonable estimate for imperfect computer models". Tuo & Wu propose L2 calibration. [Tuo & Wu, arXiv 1507.07280](https://arxiv.org/abs/1507.07280) (abstract)
- [TRANSFER: survey] Willard et al. [arXiv 2003.04919 §3.4.1 and §4](https://arxiv.org/abs/2003.04919)
  - Residual modelling is "the oldest and most common" hybrid, but "one key limitation… is its inability to enforce physics-based constraints".
  - "Data generation applications also do not make sense for residual modeling since the purpose is to simulate a data distribution rather than improve on a physical model."
- [TRANSFER: SciML] Universal differential equations: a UODE plus sparse regression recovered Lotka–Volterra equations from limited data and extrapolated beyond the training window, where SINDy with derivative smoothing on the same data failed. [Rackauckas et al., arXiv 2001.04385 §2.3.1, Figs 2–3](https://arxiv.org/abs/2001.04385)
- [TRANSFER: PDE learning] PINNs. [Krishnapriyan et al., arXiv 2109.01050](https://arxiv.org/abs/2109.01050) (abstract)
  - They "can easily fail to learn relevant physical phenomena for even slightly more complex problems".
  - Soft PDE regularisation makes the problem "more ill-conditioned", and failures are "not due to the lack of expressivity".
  - Curriculum or sequence-to-sequence training gave 1–2 orders of magnitude lower error.

### Inferences
- [ASSUMPTION] The Chao et al. gain is on data *generated by* C-MAPSS and calibrated with a C-MAPSS-family physics model. Because the model is well specified, the benefit is likely optimistic for real engines. It nonetheless supports a design where the generator exposes health parameters and physically meaningful intermediate variables, so that downstream hybrid PHM models can use them. Cross-link: validation/calibration researcher.
- [ASSUMPTION] Recommended hybrid policy for Phalanx:
  1. **v1 generator**: no learned components in the physics path.
  2. **v2**: once real data are available (public analogues such as N-CMAPSS or UCI hydraulic, or later IAF data), add *minimum-norm* residual terms (APHYNITY-style) or UDE-style learned closures for specific sub-models with known structural error, such as map off-design shape or heat-soak dynamics.
     - Require identifiability checks: the physics parameters must remain stable when the residual is added.
     - Require out-of-distribution tests across flight regimes.
  3. Never let a residual model define the *distribution* of generated data without physics constraints.
- [ASSUMPTION] Each hybrid component must be swappable for its pure-physics counterpart via configuration, so its contribution can be ablated and its harm detected.

### Gaps
- No aerospace-specific study found showing a hybrid *degrading* fidelity versus physics alone in flight or engine simulation. The harm evidence is from general dynamical-systems ML and statistics.
- Neural-ODE applications to gas turbines were not retrieved (search budget exhausted).

---

## 8. Modularity, co-simulation and reproducibility: FMI/SSP/DEVS/HLA, multi-rate scheduling, algebraic loops, fixed-step solvers, RNG streams, configuration and units, Python performance

### Takeaway
Structure the simulator as **FMI-shaped modules** (explicit inputs, outputs, parameters and units; state save/restore) orchestrated by a **deterministic fixed-step, integer-multi-rate, Gauss–Seidel-ordered master**. Treat algebraic loops explicitly, either with a documented unit delay or with iteration plus rollback inside a module.

Give every stochastic module its own **spawned, recorded RNG stream**: NumPy SeedSequence or counter-based Philox/Threefry. Pin library versions, because NumPy does not guarantee Generator streams across feature releases. Version all tables and parameter sets with provenance (SSP-style), and validate units at interfaces. The Mars Climate Orbiter loss shows the cost of skipping this.

In Python, keep heavy numerics in compiled cores (JSBSim C++, Numba nopython, optional JAX) and keep pub/sub streaming *outside* the deterministic loop.

### Cited Findings

**FMI and SSP**
- [TRANSFER: standards; widely used in aerospace and automotive] FMI 3.0. [fmi-standard.org/docs/3.0](https://fmi-standard.org/docs/3.0/)
  - Interface types (§1.2.1–1.2.3):
    - Model Exchange: the importer integrates.
    - Co-Simulation: the FMU "typically contains its own solver or scheduler".
    - Scheduled Execution: the importer triggers model partitions.
  - New in 3.0 (§1.1): clocks "to more exactly control timing of events", arrays, binary type, early return, and Event Mode and Intermediate Update Mode in Co-Simulation.
  - Clocks (§2.2.8, §2.3): periodic, countdown and triggered.
  - State save/restore (§2.2.7.4): `fmi3GetFMUState` copies internal FMU state so a step can be retried.
  - Units (§2.4.3): each unit's `BaseUnit` holds "the exponents of the seven SI base units" plus `rad`, with factor and offset; `DisplayUnit` adds name, factor, offset and inverse.
  - Metadata (§2.4.1): `generationTool`, `version` and `generationDateAndTime` attributes; a mandatory `instantiationToken` (§2.3.1).
  - Section 4.2.1 refers to `fixedInternalStepSize` for fixed-step FMUs that cannot reach requested times exactly.
- [TRANSFER: standard] SSP 2.0.1 (May 2026) is a "tool independent standard to define complete systems consisting of one or more component models" and their parameterisation. The SSP Traceability layered standard (v1.0.0) adds "information for calibration and measurement". [ssp-standard.org](https://ssp-standard.org/)
- [TRANSFER: tooling]
  - FMPy supports FMI 1.0, 2.0 and 3.0, Co-Simulation and Model Exchange, on Windows, Linux and macOS. [FMPy](https://github.com/CATIA-Systems/FMPy)
  - OMSimulator is "The OpenModelica FMI & SSP-based co-simulation environment", pip-installable. [OMSimulator](https://github.com/OpenModelica/OMSimulator)

**Co-simulation theory**
- [TRANSFER: co-simulation survey] Gomes et al., "Co-simulation: State of the art". [arXiv 1702.00686](https://arxiv.org/abs/1702.00686)
  - Jacobi versus Gauss–Seidel coupling (§4.2): Gauss–Seidel "allows for interpolations of inputs, which is more accurate, but hinders the parallelization potential".
  - Algebraic loops (§4.3.2): "neglecting an algebraic loop can lead to a prohibitively high error". Fixed-point iteration with state rollback is better.
  - Determinism (§3.3.2) is compositional, given a deterministic `Select` function for simultaneous events.
  - Multi-rate (§6.3): Van Acker et al. generate FMI orchestrators that detect algebraic loops from feedthrough information, separate fast and slow units, and use the largest communication step dividing all preferred steps.
  - Compositional stability (§4.3.5): communication step size cannot shrink arbitrarily because of cost and round-off.
  - Standards (§5.2.9): FMI for continuous time, HLA for discrete event; "both standards have limitations for hybrid co-simulation".

**Multi-rate precedents in aero simulations**
- [DIRECT]
  - HARV: 80 Hz RK2 airframe; 80 Hz FCS DISCRETE block; sensors at 40 Hz with delays. [TM-110216 §2, §5.2](https://ntrs.nasa.gov/citations/19960027892)
  - JSBSim: 120 Hz default with integer `execrate` sub-rates. [FGFDMExec.cpp](https://github.com/JSBSim-Team/jsbsim/blob/master/src/FGFDMExec.cpp), [FGFCSChannel.h](https://github.com/JSBSim-Team/jsbsim/blob/master/src/models/FGFCSChannel.h)
  - MAPSS: CLM at 2,500 Hz, controller at 50 Hz. [NTRS 20100021296](https://ntrs.nasa.gov/citations/20100021296)
  - C-MAPSS40k: iteration count capped for real time, trading accuracy. [NTRS 20100037767 §3.6](https://ntrs.nasa.gov/citations/20100037767)

**Random-number streams**
- [TRANSFER: numerical computing] NumPy parallel RNG guidance. [NumPy parallel RNG docs](https://numpy.org/doc/stable/reference/random/parallel.html)
  - `spawn()` gives independent streams "with very high probability"; collision probability is about n²·2⁻¹²⁸, about 2⁻⁸⁸ for a million streams.
  - `worker_seed = root_seed + worker_id` is "UNSAFE!"; use `default_rng([worker_id, root_seed])`.
  - Philox keys give "unique, independent streams" if stream IDs are not reused.
  - Seed with 128 bits of entropy.
- [TRANSFER: numerical computing] NEP 19 policy. [NEP 19](https://numpy.org/neps/nep-0019-rng-policy.html)
  - "Breaking stream-compatibility in order to introduce new features or improve performance will be allowed with caution" on X.Y releases.
  - Only BitGenerator `bytes()`, `integers()` and `random()` are stream-guaranteed.
  - For exact bit-for-bit results "one should use the exact version of numpy".
- [TRANSFER: HPC] Counter-based PRNGs (Philox, Threefry, AES) "pass rigorous statistical tests (including TestU01's BigCrush) and produce at least 2⁶⁴ unique parallel streams… each with period 2¹²⁸ or more", with little or no state memory. [Salmon et al., SC11, "Parallel Random Numbers: As Easy as 1, 2, 3"](https://www.thesalmons.org/john/random123/papers/random123sc11.pdf)
- [TRANSFER: tooling] JAX uses explicit keys and "a modern Threefry counter-based PRNG that's splittable". Global RNG state conflicts with JIT reordering. "Never reuse keys (unless you want identical outputs)". [JAX random numbers](https://docs.jax.dev/en/latest/random-numbers.html)

**Reproducibility and units**
- [TRANSFER: computational science] Sandve et al., "Ten Simple Rules for Reproducible Computational Research" (PLoS Comput Biol 2013). [PLoS](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003285) The rules: track how every result was produced; avoid manual data manipulation; archive exact program versions; version-control all scripts; record intermediate results; note random seeds; store raw data behind plots; generate hierarchical output; link text to results; provide public access.
- [DIRECT: aerospace failure] The Mars Climate Orbiter root cause was "the failure to use metric units in the coding of a ground software file, 'Small Forces'". Thruster data in English units were fed where metric was required. [MCO Mishap Investigation Board Phase I report](https://llis.nasa.gov/llis_lib/pdf/1009464main1_0641-mr.pdf) (Executive Summary)
- [TRANSFER: tooling] pint can "define, operate and manipulate physical quantities", supports many NumPy operations "without monkey patching", and handles uncertainties. BSD licence. [pint](https://github.com/hgrecco/pint)

**Python performance**
- [TRANSFER: tooling] Numba "works best on code that uses NumPy arrays and functions, and loops". Nopython mode runs "entirely without the involvement of the Python interpreter". The first call includes compile time. It gives little or no benefit for pandas-heavy code. [Numba 5-minute guide](https://numba.readthedocs.io/en/stable/user/5minguide.html)

**Verification and model exchange**
- [DIRECT] NESC check cases (F-16 in DAVE-ML) and DAVE-ML give standard, tool-neutral verification and model-exchange artefacts for the flight-dynamics module. [NESC 2015](https://nescacademy.nasa.gov/flightsim/2015), [daveml.org](https://daveml.org/)

### Inferences
**Architecture** [ASSUMPTION; precedents cited above]
- Module list:
  1. Environment: atmosphere, weather replay, turbulence, gust and shear.
  2. Mission/guidance and pilot.
  3. FCS and actuators.
  4. Airframe 6-DOF (JSBSim).
  5. Engine: truth CLM or surrogate, plus engine controller.
  6. Utilities: hydraulic, fuel, electrical, ECS/thermal.
  7. Degradation/fault state, per flight and per cycle. Cross-link: faults researcher.
  8. Sensor/measurement layer: sampling, quantisation, latency, bias and noise. Cross-link: sensor-texture researcher.
  9. Recorder/bus, outputting canonical Parquet and HDF5 plus a manifest. Cross-link: data-pathway researcher.
- Each module declares typed ports with SI units (FMI BaseUnit semantics), parameters with provenance, a state vector, and `get_state`/`set_state` (the FMI GetFMUState equivalent).

**Scheduling**
- Fixed major frame of 1/120 s, matching JSBSim.
- Integer sub-rates:
  - airframe, FCS and actuators: 120 Hz (actuators sub-stepped internally if stiff);
  - engine CLM: 120 Hz outer step with internal iteration or sub-steps, as MAPSS and C-MAPSS40k do internally;
  - sensors at native rates, for example 40 Hz INS-like and 1–20 Hz bus parameters;
  - thermal and utility: 1–10 Hz;
  - degradation: per sortie or cycle.
- Fixed Gauss–Seidel order: environment → guidance → FCS → engine → airframe → utilities → sensors.
- The airframe↔engine and airframe↔FCS loops are broken by one-frame delays chosen and documented explicitly. Verify by halving the frame and checking convergence, per the Gomes guidance on algebraic loops and stability.

**Determinism**
- No wall-clock dependence; fixed-step integrators only; deterministic tie-breaking for same-time events.
- Pub/sub streaming (Kafka, MQTT, ZeroMQ) replays the recorded deterministic outputs or taps them read-only. Message timing therefore never feeds back into simulation state. Cross-link: data-pathway researcher.

**RNG streams**
- One 128-bit root entropy per run.
- Streams are derived deterministically as `SeedSequence([module_id, tail_no, sortie_no, root])` or Philox keys from a registered stream table.
- Record the root seed, stream table, NumPy version and BitGenerator name in the manifest.
- Use counter-based generators where random access is needed, for example regenerating one sortie of one tail without replaying the fleet.

**Configuration and provenance**
- Every assumption is a named, versioned parameter set (YAML or SSP-like) with a source citation.
- Tables (aero, maps, decks, atmospheres) are content-hashed data artefacts.
- Each run manifest records the git commit, config hashes, data hashes, library versions and seeds (Sandve rules 1–6).
- Regression tests compare against golden outputs: NESC F-16 cases, MIL-HDBK-310 tables, C-MAPSS-like trend checks.

**Units**
- Use pint at configuration load and at module boundaries, in debug or validation mode only. Strip to plain float64 SI arrays inside Numba hot loops for performance.
- Add a kinematic-consistency check on outputs, borrowed from the SI practice in section 5, to catch unit and sign errors.

**Performance**
- JSBSim C++ via pip; engine and utility ODEs in Numba.
- JAX only if gradient-based calibration is needed, and then with explicit key handling.
- Avoid pandas in inner loops.
- Fleet-level runs are parallelised over sorties and tails, which is embarrassingly parallel because of the stream design.

**Selective FMI**
- Adopt FMI and SSP *formats* where they bring tool reuse, for example Modelica utility models exported as FMUs and run under FMPy or OMSimulator.
- Do not force FMI on the core loop if Python-native modules are simpler. The key is to keep the FMI *contract* (ports, units, state save/restore) so modules can be exported later.

### Gaps
- DEVS and HLA were only covered through the Gomes survey. No aerospace PHM-simulator example using HLA or DEVS was examined. HLA's value appears to be for distributed, multi-simulator federations, which Phalanx v1 does not need.
- Not verified: FMI 3.0 Co-Simulation capability-flag definitions (`canHandleVariableCommunicationStepSize`, `mightReturnEarlyFromDoStep`), because the relevant spec section was not reached in the fetched extracts.
- Floating-point determinism across CPUs, BLAS thread counts and GPU reductions was not researched. Pinning thread counts and avoiding non-deterministic reductions is an [ASSUMPTION]-level recommendation.

---

## 9. Synthesis: decision matrix, architecture implications, open questions and ranked sources

### Takeaway

**(a) Key findings summary**
1. The literature for fighter and military simulation (NASA HARV, TP-1538 F-16, MAPSS, the Johnson F404 model, MIL-F-8785C/1797/310) consistently uses **first-principles structure plus empirical tables**:
   - 6-DOF EOM with aero lookup tables;
   - component-level engine physics with scaled maps and controller limit logic;
   - specification-defined stochastic turbulence;
   - standard and climatic atmospheres.
   
   ML is absent from the truth path in all of these.
2. JSBSim is a sound airframe core. Its FGTurbine engine model is not adequate for engine telemetry; oil temperature, for example, is constant.
3. Cheaper engine representations carry quantified penalties. The table-plus-lag model is about 3% steady-state but up to 25% wrong in transients. Piecewise-linear residuals grow in transients and stall margin linearises poorly. Use them as labelled surrogates only.
4. The most transferable PHM data-generation template is the C-MAPSS/N-CMAPSS approach: a physics CLM, 13 health parameters, real flight-condition replay and controlled stochastic degradation. For Phalanx it should be re-instantiated for a low-bypass afterburning engine; MAPSS shows this is feasible.
5. Generative and black-box ML carry documented, serious failure modes: inconsistency, memorisation, mode collapse, extrapolation, evaluation ambiguity. With no public fighter telemetry, ML should not be the generator.
6. Hybrids help PHM *estimation* (RUL horizon about +127%) but harm through non-identifiability and distribution shift. Add them only later, as minimum-norm residuals with ablation switches.
7. Reproducibility requires:
   - fixed-step deterministic multi-rate orchestration;
   - explicit algebraic-loop handling;
   - spawned or counter-based RNG streams with pinned library versions;
   - SI-unit contracts;
   - versioned, provenance-tagged tables and parameter sets.

### Cited Findings

**(b) Decision matrix.** Tags and sources as in sections 1–8. "Public calibration data" lists what can calibrate or validate each row without IAF data.

| # | Behaviour | Candidate approaches considered | **Recommended (v1)** | Key evidence (tag) | Data needed | Public calibration / validation data | Validation method | Main risks |
|---|---|---|---|---|---|---|---|---|
| 1 | Baseline atmosphere (T, p, ρ, a vs h) | First-principles standard; lookup | **USSA-1976 / ISA standard model** | USSA-1976 equals ICAO to 32 km [DIRECT] ([EverySpec](https://everyspec.com/NASA/NASA-General/NASA_TM-X-74335_37294/)) | None | NASA-TM-X-74335 tables; `ussa1976`/`ambiance` packages | Table comparison to 1e-6 relative | Low; units confusion (geometric vs geopotential altitude) |
| 2 | Climatic extremes (hot/cold/tropical/polar, 1–20%) | Envelope lookup; profile lookup; statistical | **MIL-HDBK-310 profile (climb/descent) and envelope (level) lookups** | MIL-HDBK-310 implementation, Profile vs Envelope [DIRECT] ([MathWorks](https://www.mathworks.com/help/aeroblks/nonstandardday310.html)) | Handbook tables | MIL-HDBK-310 / MIL-STD-210C tables (via [atmosnonstd](https://www.mathworks.com/help/aerotbx/ug/atmosnonstd.html)) | Reproduce tables; check that envelope values are not used as consistent profiles | Envelope values are not physically consistent profiles; metric/English inconsistencies |
| 3 | Real weather at Indian bases (T, p, humidity, wind profiles) | Reanalysis replay; radiosonde replay; stochastic weather generator; ML | **ERA5 replay + METAR/ISD surface override; IGRA for validation** | ERA5 hourly, 37 levels, about 31 km [DIRECT data] ([ECMWF](https://confluence.ecmwf.int/display/CKB/ERA5%3A+data+documentation)); 61 active Indian IGRA stations [analysis] ([IGRA list](https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt)); 145 IN METAR stations incl. AFS [DIRECT data] ([IEM](https://mesonet.agron.iastate.edu/sites/networks.php?network=IN__ASOS)) | Base lat/lon, dates | ERA5 (CC-BY), IGRA v2, IEM/ISD METAR | ERA5-vs-IGRA profile residuals; METAR-vs-ERA5 2 m T/dewpoint | Grid-box smoothing (no turbulence or microburst); IEM QC weak; ERA5T revisions |
| 4 | Humidity effect on engine | Ignore; empirical correction factors; thermodynamic (wet-air CEA) | **Thermodynamic: carry WAR into engine CLM (pyCycle CEA wet air)** | Wet vs dry thrust −2.8%, SFC +1.3% [TRANSFER: micro-turbojet] ([KARI](https://koreascience.or.kr/article/JAKO201074648803472.do)); pyCycle WAR [DIRECT tool] ([example](https://github.com/OpenMDAO/pyCycle/blob/master/example_cycles/wet_simple_turbojet.py)) | Dewpoint/specific humidity from row 3 | KARI and TU Delft trends (qualitative) | Sensitivity sweep: ΔEGT, ΔFn vs WAR | Fighter-engine magnitude unverified; tabular thermo lacks WAR |
| 5 | Continuous turbulence | Dryden filter; von Kármán filter; measured-spectrum replay; ML | **von Kármán forming filters (Dryden for tests), MIL-F-8785C/1797 parameters, own RNG stream** | Spec forms, scale lengths, exceedance table [DIRECT] ([MathWorks Dryden](https://www.mathworks.com/help/aeroblks/drydenwindturbulencemodelcontinuous.html)); von Kármán preferred §3.7.1 [DIRECT, secondary] ([Cole](https://ar5iv.labs.arxiv.org/html/1905.09954)) | Altitude, airspeed, exceedance probability | Spec spectra | PSD of generated gusts vs analytic spectra; intensity statistics | Frozen-turbulence limit; noise sample rate vs frame rate; no terrain or convective effects |
| 6 | Discrete gusts and low-altitude shear | 1−cosine; log-profile; microburst models | **1−cosine gust and MIL-F-8785C log-profile shear** | [DIRECT] ([gust](https://www.mathworks.com/help/aeroblks/discretewindgustmodel.html), [shear](https://www.mathworks.com/help/aeroblks/windshearmodel.html), [Leahy](https://ntrs.nasa.gov/citations/20080014847)) | W20, z0, gust amplitude and length | METAR surface wind/gusts | Shape and amplitude checks; z0 by flight phase | Microbursts and thermals not covered |
| 7 | Rigid-body 6-DOF motion | Flat-Earth Euler; quaternion flat-Earth; rotating WGS-84 quaternion | **JSBSim rotating-Earth quaternion EOM, fixed 120 Hz, integrators set explicitly** | JSBSim source [DIRECT tool] ([FGPropagate](https://github.com/JSBSim-Team/jsbsim/blob/master/src/models/FGPropagate.cpp)); HARV RK2 at 80 Hz [DIRECT] ([TM-110216](https://ntrs.nasa.gov/citations/19960027892)) | Mass and inertia, CG | NESC F-16 check cases (DAVE-ML) | Reproduce NESC cases; step-halving convergence | Default integrator mix is low-order; Euler-angle singularity if flat-Euler used |
| 8 | Aerodynamic forces and moments | Lookup tables; global polynomial (SI); DATCOM; VSPAERO; CFD; ML | **Wind-tunnel/flight-derived lookup tables (F-16 TP-1538 or F/A-18 HARV); DATCOM/VSPAERO only as labelled gap-fillers** | TP-1538, HARV ranges [DIRECT] ([NTRS 19800005879](https://ntrs.nasa.gov/citations/19800005879), [TM-110216](https://ntrs.nasa.gov/citations/19960027892)); Datcom high-α gaps [DIRECT] ([AFWAL-TR-84-3084](https://contrails.library.iit.edu/item/162306)) | Coefficient tables vs α, β, Mach, surfaces | TP-1538 data; HARV database; HARV flight-derived derivatives ([TM-102692](https://ntrs.nasa.gov/citations/19900019262)) | Trim points vs published; NESC; modal checks | No public data for Tejas, Gripen or Su-30; F-16 data low-speed; DATCOM weak at high α and transonic |
| 9 | Flight control laws and actuators | Published FCS replicas; generic C*/NDI law; learned controller | **Published/JSBSim F-16 FCS (pid, scheduled gains, switches) or generic gain-scheduled law; Tustin actuators with rate and position limits** | f16.xml FCS [DIRECT]; Tustin lag [DIRECT tool] ([FGActuator](https://github.com/JSBSim-Team/jsbsim/blob/master/src/models/flight_control/FGActuator.cpp)); HARV 80 Hz FCS [DIRECT] | Gains, schedules, limits, actuator bandwidths | TP-1538 FCS description; HARV RFCS | Step and doublet responses; handling-qualities metrics | Actual Tejas/Gripen laws unavailable; aliasing near Nyquist |
| 10 | Landing gear and ground | Spring–damper–friction contact; detailed oleo | **JSBSim BOGEY spring/damper/friction contacts** | f16.xml gear [DIRECT] | Spring and damping, friction | Public gear data scarce | Touchdown load and bounce plausibility | Weight-on-wheels logic and brake heating not modelled |
| 11 | Mass properties and fuel CG | Constant; tank-based burn | **Tank-based fuel burn coupled to engine fuel flow** | JSBSim tanks [DIRECT]; HARV neglected fuel effects [DIRECT] | Tank capacities and locations | Public brochures (cross-link: platform researcher) | Mass-balance closure (fuel in = burned + remaining) | Transfer-sequence logic unknown |
| 12 | Pilot / mission following | Deterministic guidance + autopilot; manoeuvre library; crossover/structural pilot model; RL agents | **Deterministic guidance and autopilot loops + optional crossover-type stochastic pilot overlay (gain, τ 0.1–0.2 s, remnant)** | Crossover model [DIRECT] ([MathWorks](https://www.mathworks.com/help/aeroblks/crossoverpilotmodel.html)); remnant [DIRECT] ([NTRS 20180001222](https://ntrs.nasa.gov/api/citations/20180001222/downloads/20180001222.pdf)) | Mission profiles (cross-link: flight-profiles researcher) | Published pilot-model parameter ranges | Tracking-error spectra; crossover frequency checks | Crossover valid only near ωc; RL agents unvalidated and non-deterministic |
| 13 | Engine steady-state gas path (stations, N1/N2, Wf, EGT, nozzle) | 0-D CLM (pyCycle/NPSS/T-MATS/GasTurb/GSP/PROOSIS); decks; regression; ML | **0-D CLM of two-spool mixed-flow afterburning turbofan (pyCycle), scaled maps, WAR** | MAPSS military CLM [DIRECT] ([NTRS 20030093721](https://ntrs.nasa.gov/citations/20030093721)); pyCycle mixed-flow AB example [DIRECT tool]; within 0.03% of NPSS [TRANSFER, search-summary] | Design point, maps, bleeds, cooling | Published thrust/SFC/airflow (cross-link: engine-data researcher); N-CMAPSS for method | Cycle checks vs published ratings; NPSS-style cross-check | Map shape provenance; supplied maps are for demonstration |
| 14 | Engine transients (spools, volumes, heat soak, tip clearance) | Shaft-inertia ODE + CMF; ICV; table + lag; PWL state-space; NARX/LSTM/NODE | **Shaft-inertia ODE + CMF iteration (ICV optional), lumped metal-temperature and clearance states** | MAPSS metal-temperature state [DIRECT]; C-MAPSS40k stall-margin debits [TRANSFER]; table + lag only 25% transient accuracy [DIRECT] ([TM-4240](https://ntrs.nasa.gov/citations/19910009766)) | Spool inertias, thermal masses | Published accel times (idle→max); C-MAPSS40k behaviour | Accel/decel time and overshoot vs public data; surge-margin trajectories | Inertia and thermal values unknown; ICV stiffness |
| 15 | Engine control (schedules, limiters, MIN-MAX) | Physics-based controller replica; table schedules; learned policy | **Gain-scheduled PI + max/min limit regulators + MIN-MAX selection + accel/decel schedules + wind-up protection; AB light/scheduling logic** | [TRANSFER: commercial] ([NTRS 20100037768](https://ntrs.nasa.gov/citations/20100037768)); MAPSS 50 Hz digital controller [DIRECT] | Limits (N, T, P), schedules | Public limits (cross-link: engine-data) | Limit-protection tests; no limit exceedance across envelope | Fighter-specific AB and nozzle schedules unknown |
| 16 | Fast engine surrogate for fleet runs | Tables + lag; PWL state-space; NN surrogate trained on CLM | **PWL/LPV or table surrogate generated from the CLM, labelled with its error envelope** | PWL transient residuals, ~10× speed [TRANSFER] ([Armstrong & Simon](https://papers.phmsociety.org/index.php/phmconf/article/view/2136)); HARV/Johnson tables [DIRECT] | CLM runs | Self-generated | Surrogate vs CLM error budgets per regime | Stall margin poorly linearised; transient error |
| 17 | Engine health / degradation hooks | Health-parameter scalars; physics-of-failure; data-driven | **C-MAPSS-style health-parameter scalars per component, driven by the faults module** | 13 health parameters [TRANSFER] ([NTRS 20100037767](https://ntrs.nasa.gov/citations/20100037767)); N-CMAPSS generation [TRANSFER] ([arXiv 2003.00732](https://arxiv.org/abs/2003.00732)) | Degradation laws (cross-link: faults researcher) | N-CMAPSS, C-MAPSS | Fingerprint/sensitivity matrix checks | Observability (#sensors < #health parameters) |
| 18 | Oil and fuel temperatures, lubrication | Lumped-capacitance thermal network; constant; regression | **Lumped-capacitance nodes driven by spool speed, load and fuel flow** | Lumped thermal states in CLMs [DIRECT, MAPSS]; FDM constant oil temperature shows the gap [DIRECT] ([FGTurbine](https://jsbsim-team.github.io/jsbsim/classJSBSim_1_1FGTurbine.html)) | Heat loads, capacities, HX effectiveness | Few public data (gap) | Warm-up time constants; steady-state plausibility | Parameters largely assumed |
| 19 | Engine vibration | Order-tracked spectral synthesis; rotor-dynamic FE; ML generative | **Order-tracked spectral synthesis (1×N1, 1×N2, harmonics + broadband), amplitude tied to fault parameters** | No fighter-specific source found [ASSUMPTION]; spectral condition indicators for physics-simulated faults [TRANSFER] ([MathWorks pump](https://www.mathworks.com/help/predmaint/ug/multi-class-fault-detection-using-simulated-data.html)) | Spool speeds, sensor locations | None verified (gap) | Spectral-peak tracking vs N1/N2 | Unvalidated amplitudes |
| 20 | Hydraulic system | Lumped fluid network (Modelica/Simscape/bond graph); empirical; ML | **Lumped-parameter network with physical fault parameters (leak area, friction, precharge)** | Physics fault simulation for PHM [TRANSFER] ([MathWorks pump](https://www.mathworks.com/help/predmaint/ug/multi-class-fault-detection-using-simulated-data.html)); MSL Fluid [TRANSFER] | Pump, accumulator, actuator parameters | UCI hydraulic rig (CC BY 4.0) | Pressure-transient shape; texture vs UCI | Aircraft-specific parameters missing |
| 21 | Fuel system | Tank/pump/valve lumped network; table | **Lumped tank/feed network coupled to JSBSim tanks and engine Wf** | JSBSim tanks [DIRECT]; MSL/ThermofluidStream [TRANSFER] | Tank layout, pump curves | None verified | Mass balance; feed-pressure plausibility | Transfer logic unknown |
| 22 | Electrical system | Average-value network; detailed switching; table | **Average-value lumped network (generator, buses, loads)** | MSL Electrical [TRANSFER] | Generator rating, load schedule | None verified (gap) | Power balance; voltage regulation | Thin evidence |
| 23 | ECS / thermal management | Lumped thermofluid network; table | **ThermofluidStream / MSL lumped network or simplified heat balance** | DLR ThermofluidStream [TRANSFER] | Heat loads, bleed | None verified | Energy balance | Bleed coupling to engine |
| 24 | Operating regime / sortie variability | Scripted mission mix; mixture/HMM fitted to usage; ML | **Scripted mission catalogue + seeded random sampling of parameters (v1); mixture/HMM only if usage statistics exist** | [ASSUMPTION]; regime-shift sensitivity of data-driven models [TRANSFER] ([arXiv 2003.00732 §4.1](https://arxiv.org/abs/2003.00732)) | Mission types and frequencies (cross-link: flight-profiles, maintenance records) | Public usage spectra (if found) | Distribution checks vs targets | Unrepresentative mission mix leads to PHM bias |
| 25 | Stochastic texture on signals (noise, drift, bias) | Gaussian white; coloured (AR/state-space); GAN/diffusion | **State-space / AR coloured noise + bias random walks per sensor, seeded streams** | statsmodels state-space [TRANSFER]; generative risks [TRANSFER] ([Brophy](https://arxiv.org/abs/2107.11098), [Carlini](https://arxiv.org/abs/2301.13188)) | Noise specs (cross-link: sensor-texture researcher) | UCI hydraulic, N-CMAPSS noise levels | PSD and autocorrelation match | Over-smooth or over-regular texture |
| 26 | Learned residual / hybrid corrections | None; residual NN; UDE; APHYNITY minimum-norm; PINN | **None in v1; v2 minimum-norm residuals / UDE on specific sub-models once real data exist** | Hybrid gains [TRANSFER] ([Chao](https://arxiv.org/abs/2003.00732)); non-uniqueness and shift harms [TRANSFER] ([APHYNITY](https://arxiv.org/abs/2010.04456), [Wehenkel](https://arxiv.org/abs/2202.03881)); PINN failures [TRANSFER] ([Krishnapriyan](https://arxiv.org/abs/2109.01050)) | Real data | N-CMAPSS, UCI | Ablation on/off; parameter-stability checks; out-of-distribution tests | Absorbs physics; breaks identifiability |

### Inferences

**(c) Architecture implications** (detail in section 8)
1. The hierarchy follows the evidence: physics core (EOM, CLM, networks), then empirical tables as versioned data, then stochastic texture modules with seeded streams, then optional learned residuals behind feature flags. Each layer can be switched off for ablation.
2. Separate the **truth engine CLM** from the **FDM thrust interface**. JSBSim receives thrust and fuel flow from the engine module; its own FGTurbine is never used for telemetry.
3. A deterministic fixed-step multi-rate master at 120 Hz with integer sub-rates and a documented Gauss–Seidel order. Loop-breaking delays are explicit and tested by step-halving.
4. FMI-shaped module contracts: SI units, typed ports, state get/set, metadata. SSP-like parameter sets carry provenance. This lets Modelica utility FMUs and Python modules coexist.
5. RNG: SeedSequence or Philox stream registry keyed by (module, tail, sortie). Root entropy and library versions go in every manifest.
6. A verification ladder per module:
   - standards reproduction: USSA, MIL-HDBK-310, NESC F-16, turbulence PSDs;
   - published-trend reproduction: engine ratings, acceleration times, HARV trims;
   - cross-model checks: CLM vs surrogate error budgets;
   - texture checks: PSD and autocorrelation vs public real data.
   
   Cross-link: validation/calibration researcher.
7. Streaming and pub/sub run downstream of a deterministic recorder, so live streams equal replayed streams bit-for-bit. Cross-link: data-pathway researcher.

**Platform implication** (cross-link: platform researcher) [ASSUMPTION]: public evidence is richest for:
- the F-16: TP-1538 aero, JSBSim model, NESC check cases;
- the F/A-18: HARV aero DB, NASA F404 engine-model approach.

Tejas shares the F404 family with the F/A-18, but its tailless-delta aero has no public database found. A "Tejas-like" virtual aircraft would need an F/A-18/F404 engine pairing with substituted aero, disclosed as an assumption.

### Gaps

**(d) Open questions and gaps**
1. Public component maps and transient data for F404-IN20, RM12, F100/F110 and AL-31FP. Cross-link: engine-data researcher.
2. Public aero databases for Tejas, Gripen and Su-30MKI; supersonic provenance of JSBSim f16.xml.
3. Engine vibration and lubrication models suitable for PHM, and utility-system (hydraulic, electrical, fuel, ECS) aircraft parameters: no verified public sources.
4. Humidity sensitivity of low-bypass afterburning engines.
5. Indian turbulence, shear and thermal climatology; ERA5-vs-IGRA boundary-layer skill at Indian bases.
6. Output-error, filter-error and frequency-domain (CIFER) SI sources; NARX, LSTM and neural-ODE gas-turbine accuracy studies. These were not retrieved because the shared web-search budget was exhausted. A follow-up session could close them.
7. Distributability of MAPSS and C-MAPSS40k to Indian teams. C-MAPSS40k appears restricted to US federal users per the NASA catalogue (search-summary only).
8. Whether JSBSim was the open-source tool in the NESC 2015 comparison.
9. Cross-platform floating-point determinism for Numba, BLAS and JAX.

**(e) Ranked list of most valuable sources** (value to Phalanx's modelling decisions)
1. NASA TM-110216, F/A-18 HARV simulation: aero DB ranges, F404 table and lag engine model, 80 Hz RK2, sensor modelling. [NTRS 19960027892](https://ntrs.nasa.gov/citations/19960027892)
2. C-MAPSS40k and its control-design companion: CLM structure, health parameters, MIN-MAX limiters, stall-margin debits, linearisation. [NTRS 20100037767](https://ntrs.nasa.gov/citations/20100037767), [NTRS 20100037768](https://ntrs.nasa.gov/citations/20100037768)
3. MAPSS (Parker & Guo): military low-bypass mixed-flow afterburning CLM, 2,500 Hz / 50 Hz, metal-temperature state. [NTRS 20030093721](https://ntrs.nasa.gov/citations/20030093721), [NTRS 20100021296](https://ntrs.nasa.gov/citations/20100021296)
4. JSBSim source plus the f16.xml and F100 files: EOM, integrators, 120 Hz, Tustin actuators, execrate, FGTurbine limits. [GitHub](https://github.com/JSBSim-Team/jsbsim)
5. NESC 6-DOF check cases (F-16 in DAVE-ML). [nescacademy.nasa.gov/flightsim/2015](https://nescacademy.nasa.gov/flightsim/2015)
6. Johnson NASA TM-4240, F404 simple model with 3% / 25% accuracy. [NTRS 19910009766](https://ntrs.nasa.gov/citations/19910009766)
7. Armstrong & Simon (PHM 2012), PWL accuracy limits. [PHM Society](https://papers.phmsociety.org/index.php/phmconf/article/view/2136)
8. pyCycle repository: mixed-flow afterburning example, WAR, steady-state shaft. [GitHub](https://github.com/OpenMDAO/pyCycle); T-MATS user's guide. [NTRS 20140012486](https://ntrs.nasa.gov/citations/20140012486)
9. MathWorks MIL-spec environment implementations: Dryden, von Kármán, gust, shear, MIL-HDBK-310. [Dryden](https://www.mathworks.com/help/aeroblks/drydenwindturbulencemodelcontinuous.html), [atmosnonstd](https://www.mathworks.com/help/aerotbx/ug/atmosnonstd.html)
10. Gomes et al., co-simulation state of the art. [arXiv 1702.00686](https://arxiv.org/abs/1702.00686); FMI 3.0 spec. [fmi-standard.org](https://fmi-standard.org/docs/3.0/)
11. NumPy parallel RNG and NEP 19. [NumPy](https://numpy.org/doc/stable/reference/random/parallel.html), [NEP 19](https://numpy.org/neps/nep-0019-rng-policy.html); Random123. [SC11](https://www.thesalmons.org/john/random123/papers/random123sc11.pdf)
12. Arias Chao et al., physics + DL hybrid on N-CMAPSS, including the dataset-generation template. [arXiv 2003.00732](https://arxiv.org/abs/2003.00732)
13. Klein et al., HARV SI from flight data (identifiability lessons). [NTRS 19900019262](https://ntrs.nasa.gov/citations/19900019262); Morelli F-16 and global models. [NTRS 20040110310](https://ntrs.nasa.gov/api/citations/20040110310/downloads/20040110310.pdf), [NTRS 20120001458](https://ntrs.nasa.gov/citations/20120001458)
14. ERA5 documentation, IGRA station list, IEM IN__ASOS network. [ECMWF](https://confluence.ecmwf.int/display/CKB/ERA5%3A+data+documentation), [IGRA](https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt), [IEM](https://mesonet.agron.iastate.edu/sites/networks.php?network=IN__ASOS)
15. Hybrid and ML-risk papers: APHYNITY, expert augmentation, PGNN, PINN failure modes, extrapolation, diffusion memorisation, TS-GAN survey. [2010.04456](https://arxiv.org/abs/2010.04456), [2202.03881](https://arxiv.org/abs/2202.03881), [1710.11431](https://arxiv.org/abs/1710.11431), [2109.01050](https://arxiv.org/abs/2109.01050), [2009.11848](https://arxiv.org/abs/2009.11848), [2301.13188](https://arxiv.org/abs/2301.13188), [2107.11098](https://arxiv.org/abs/2107.11098)
