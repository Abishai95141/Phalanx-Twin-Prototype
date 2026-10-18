# Sensor Residual Texture: How Real Aircraft Measurements Differ from Ideal Signals, and How to Model/Learn It (Project Phalanx)

Scope note. These notes cover the measurement "texture" layer of the virtual fighter: what lies between the physical truth state, as produced by the engine/airframe/flight-profile models built by other researchers, and the numbers that a real fighter's sensors, avionics, buses and recorders would emit. Evidence tags used throughout:
- **[DIRECT]**: about fighter-aircraft systems specifically. Examples are the F404-GE-400 on the F/A-18, the F-18 HARV, the F-16, F-35/F135, Typhoon/EJ200 and F-22/F119.
- **[TRANSFER: X]**: from another platform or domain. Each tag says why the evidence transfers and where it stops applying.
- **[ASSUMPTION]**: not directly evidenced. Each one says how it could be validated.
- **[DERIVED]**: arithmetic or physics worked out from cited numbers.

Process caveat. Part-way through this work the shared web-search budget for the session ran out (200 searches per turn, shared by all parallel researchers). After that point, sources were reached only by direct fetches of known documents, by links inside retrieved documents, and by Crossref/arXiv identifier lookups. Some gaps listed below, especially air-data vane dynamics, fuel-quantity probes, fuel flowmeters and FADEC signal-validation logic, therefore reflect an unfinished search rather than proven unavailability. A follow-up search pass is recommended (see Gaps). All PDFs read are saved under `/Users/abishaikc/Phalanx/research_sources/sensor_texture/`.

Cross-links to parallel researchers:
- **Platform selection**: the F404-GE-IN20 (Tejas) has a FADEC; the F404-GE-400 evidence here comes from a hydromechanical-plus-ECU configuration.
- **Data pathway/formats**: full ARINC 429/717/1553 details.
- **Datasets**: DASHlink, C-MAPSS and N-CMAPSS.
- **Faults/degradation**: sensor fault catalogue.
- **Validation/calibration**: adversarial and TSTR audits.
- **Flight profiles**: regime covariates such as turbulence, power setting and g.

---

## Q1. Per-sensor-class measurement behaviour (accuracy, bias, drift, dynamics, sensitivities, failure modes)

### Takeaway
Every sensor class on a fighter departs from "truth plus white noise" in structured ways:
- **Dynamics**: lags that change with flow conditions, sometimes with more than one time constant.
- **Unit-specific fixed errors**: calibration offsets of several °C or a few % of full scale.
- **Environment-driven errors**: thermal zero/span shift, vibration rectification, de-icing heater error, attitude error.
- **Slow drift and aging**: thermocouple EMF drift, MEMS bias growth over life.
- **Discrete failure semantics**: an open probe is silently dropped from an average; a short circuit reads low and drives the control loop.

Datasheets and AGARD/NASA reports give usable numbers for thermocouples, total-temperature probes, pressure transducers, inertial sensors, oil-debris monitors and strain gauges. Public numbers for AoA-vane dynamics, fuel-quantity probes, turbine fuel flowmeters, proximity probes and current sensors were not found in this pass.

### Cited Findings

**Thermocouples / EGT harness (Type K)**
- **F404-400 harness layout** [DIRECT: F404-GE-400 on F/A-18]: the engine control uses "two identical four-probed thermocouple harnesses mounted upper and lower on the AB case", so the control signal is an average of eight probes — [NASA CR-191195 (FOCSI, GE 1994), §3.3.3, p.7](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf)
- **F404-400 probe failure semantics** [DIRECT] — [NASA CR-191195, §8.4 item 8](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf):
  - The ECU averages only the remaining good thermocouple inputs ("the open signals are not used"), so a single open probe "is not noticed".
  - "A short failure in a single probe causes an erroneously low temperature signal, resulting in an increase in fuel flow."
  - So a sensor fault changes the engine's real state through the control loop.
- **Calibration tolerance** [TRANSFER: AGARD flight-test instrumentation guide, 1973. It covers aircraft to Mach 2.3; thermocouple metallurgy has improved since, but the order of magnitude holds]: thermocouple calibration errors fall within 0.5% to 0.75% of indicated temperature, i.e. ±5 °C to ±7.5 °C at 1000 °C. A whole EGT system can be ground-checked (Jetcal) to about ±4 °C — [AGARD-AG-160 Vol.2, Trenkle & Reinhardt, §5.2.4 and §6.3](http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf)
- **Type K tolerance classes** [TRANSFER: generic IEC-class values via a tertiary source]: −40–375 °C ±1.5 °C, then ±0.004·T up to 1000 °C (class "one"); −40–333 °C ±2.5 °C, then ±0.0075·T up to 1200 °C (class "two").
- **Type K drift mechanisms** — [Wikipedia: Thermocouple](https://en.wikipedia.org/wiki/Thermocouple):
  - Mn/Al migration produces irreversible, cumulative down-scale drift.
  - A cyclic EMF change occurs at roughly 250–650 °C (short-range order).
  - "Green rot" makes the thermocouple read low.
- **Drift magnitude in turbine conditions** [TRANSFER: research turbine-blade thermocouples at 1080–1250 K. EGT probes have thicker sheaths, so this is an upper bound on drift rate] — [NASA TN D-7671, Summary and Results](https://ntrs.nasa.gov/api/citations/19740014937/downloads/19740014937.pdf):
  - 0.25 mm commercial sheathed Chromel-Alumel thermocouples drifted about 1% in 10 h (75–140 K in 100 h).
  - Special-order units showed no noticeable drift to 425 h, with ±6 K (±0.5%) spread between thermocouples.
  - Earlier engine tests saw roughly 15% failures in 2–30 h, mostly from erosion.
- **Time constant vs flow** [TRANSFER: NACA lab gas streams at M 0.3–0.9 and 1500–2500 °R. The physics, h ∝ √Re, transfers to EGT probes; the absolute τ* values are probe-specific] — [NACA TN 3766 (Glawe et al. 1956), Eq. 6 and Table I](https://ntrs.nasa.gov/api/citations/19930084456/downloads/19930084456.pdf):
  - τ = τ*·(T/1000 °R)^−0.18·(M·p)^−1/2, i.e. τ scales with the inverse square root of Reynolds number.
  - Measured τ*: bare-wire crossflow 0.40 ± 0.03 s (theory 0.43 s); platinum-shielded 0.80 ± 0.08 s.
  - Aspirated shielded probes were not first-order. Their 63% times were 0.3–0.7 s and 0.6–1.4 s: a fast initial rise followed by a slow tail from the more massive shields.
- **Probes in engine flow** [TRANSFER: AGARD] — [AGARD-AG-160 Vol.2, §5.2.3, Eqs. 79–84](http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf):
  - For probes in engine flow, time constants at two flow rates are "inversely proportional to the square root of both flowrates", τ_I/τ_II = √(W_II/W_I).
  - "The time constant can change by a ratio of three to one over the performance range of an aircraft."
  - Open-wire probes have multiple time constants. The Rosemount 102 response is modelled as 0.8·e^(−t/τ1) + 0.2·e^(−t/τ2).
  - Sealed elements can lag up to 100× more than open-wire elements.
  - Faster response to temperature rises than to falls indicates a large radiation error.
- **Bandwidth of thick-wire thermocouples** [TRANSFER: combustion/engine-exhaust thermocouples]: τ = 2πκ·d^(2−m)·v^(−m). Large-diameter thermocouples in harsh exhausts have "a low bandwidth of typically less than 1 Hz"; 20–50 µm fine wires reach 1–10 Hz. The two-thermocouple blind-identification method can estimate τ in situ — [Hung, McLoone, Irwin, Kee, Rev. Sci. Instrum. 76, 024902 (2005), Eqs. 1–3](https://mural.maynoothuniversity.ie/id/eprint/689/1/EE-McL8.pdf)
- **Transient response on the F404** [DIRECT: F404-400 ground test]: the optical T5 and the production thermocouple harness "tracked very closely with very small if any offset on a steady-state basis. During fast transients, some differences occurred, probably due to differences in probe thermal time response." — [NASA CR-191195, §10.1.3, pp.48–49](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf)
- **Parallel harness, other sources** [TRANSFER: generic turbine-outlet indication; community forum post, low authority]: harnesses use at least four thermocouples wired in parallel plus matching resistors/trim; "loss of two or more thermocouples can cause destabilised and erroneous indications" — [EASA Community post (not an official EASA publication)](https://www.easa.europa.eu/community/topics/aircraft-jet-engines-turbine-outlet-temperature-indication)

**Inlet / total temperature (RTD, TAT/CIT probes)**
- **F404-400 inlet sensors** [DIRECT: F404-400]: T1 is "a single element RTD electrical sensor, de-iced using hot air". T2.5 is a pneumatic transmitter feeding the main fuel control — [NASA CR-191195, §3.3.1–3.3.2](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf)
- **F404-400 T1 ground-test comparison** [DIRECT: F404-400 ground test] — [NASA CR-191195, §10.1.3](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf):
  - The optical T1 was "within 5 degrees C" of the electrical T1 at ambient.
  - The electrical T1 showed "a dip … with increasing airflow … most probably due to lack of dynamic recovery".
- **De-icing heat error (DHE)** [TRANSFER: AGARD; heated TAT/CIT probes] — [AGARD-AG-160 Vol.2, §5.2.2(g), Eq. 78](http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf):
  - Always positive.
  - 0.2–0.5 °C at M0.3 (altitude-dependent) and 0.12–0.3 °C at M0.8.
  - Roughly doubled for dual-element probes.
  - Grows as flow falls (lower speed, higher altitude).
- **Attitude error** [TRANSFER: AGARD]: appears beyond about ±10° flow angle with de-icing on, often beyond ±20° with it off. For older probes it appears at about ±5° — [AGARD-AG-160 Vol.2, §5.2.2(b)](http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf)
- **Ground behaviour** [TRANSFER: AGARD] — [AGARD-AG-160 Vol.2, §6.3](http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf):
  - OAT/CIT probe time constants with no flow can be "perhaps 15 minutes and more".
  - With the de-icer on, the indication "would rise to more than 100 °C".
  - With engines off, liquid-temperature indications "fluctuate and become unreliable" because of self-heating and natural convection.
- **Control-system implication** [TRANSFER: AGARD]: electronic fuel controls need shorter probe time constants than hydromechanical controls — [AGARD-AG-160 Vol.2, §6.1.2](http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf)
- **Recovery factors** [TRANSFER: tertiary source]: TAT probe ≈ 1 (≈0.98 used); flush-bulb ratiometers 0.75–0.9; ram rise ≈ V²/87² (V in kt) — [Wikipedia: Total air temperature](https://en.wikipedia.org/wiki/Total_air_temperature)
- **RTD tolerance classes** [TRANSFER: tertiary source quoting BS EN 60751:2008]: F0.3 (−50 to +500 °C), F0.15 (−30 to +300 °C), F0.1 (0 to +150 °C) — [Wikipedia: Resistance thermometer](https://en.wikipedia.org/wiki/Resistance_thermometer)
  - [ASSUMPTION] The temperature-proportional terms (e.g. ±(0.3+0.005|t|) °C for class B) should be confirmed against IEC 60751 itself.

**Pressure transducers**
- **Piezoresistive / silicon-on-insulator (SOI)** [TRANSFER: Kulite flight-test/engine-test transducers. Engine-control transducers are the same physical class but OEM specs are unpublished]:
  - Static error band typically ±0.1% FSO, of which non-linearity is the largest part.
  - Thermal zero shift spec ±1% FSO/100 °F (typical); one unit measured −0.44% FSO/100 °F, "normally the single largest error source".
  - Thermal sensitivity shift ±1% of reading/100 °F (measured −0.42%).
  - Thermal-gradient errors "are never found on pressure transducer datasheets".
  - Source: [Kulite TD-1012 "Total Error Band vs Accuracy", pp.3–6](https://kulite.com//assets/media/2021/12/Understanding-the-Pressure-Transducer-Datasheet-Total-Error-Band-vs.-Accuracy.pdf)
- **Kulite handbook, Section 3** [TRANSFER: Kulite] — [Kulite Handbook §3 (3.3–3.11)](https://kulite.com//assets/media/2024/10/section3.pdf):
  - Wideband noise ≈5 µV rms, about 1×10⁻⁴ psi on a 2 psi FS unit.
  - Hysteresis usually <0.1% FS, often 0.03%.
  - Acceleration sensitivity as low as 0.00003% FS/g.
  - Thermal compensation "is only valid for equilibrium or slow changes in temperature, not for thermal shocks".
- **Smart silicon transducer, Honeywell PPT** [TRANSFER: secondary air data / flight test] — [Honeywell PPT datasheet, pp.2–3](https://prod-edam.honeywellaerospace.com/content/dam/honeywell-edam/aero/en-us/products/navigation-and-sensors/air-data-and-pressure/precision-pressure-transducer-ppt/documents/hon-aero-at-ads-n61-2080-00-000-ppt-datasheet-a4-en-2025.pdf):
  - Total error band ±0.10% FS (digital) for 10–50 psi ranges, defined as linearity + repeatability + hysteresis + thermal + calibration over −40 to 85 °C.
  - Long-term stability 0.025% FS/yr typical.
  - Resolution to 0.001% FS digital; analog output in 1.22 mV (12-bit) steps.
  - Sample period 8.33 ms to 51.2 min; minimum response delay 17 ms.
- **PPT user-configurable deadband** [TRANSFER: Honeywell PPT]: the reading "does not vary as long as it remains within the deadband limits". There is also an integration (averaging) time, and an idle count that skips readings. This is sensor-level hold/stair-step texture — [PPT User's Manual §4 (DS/I=/IC commands)](https://prod-edam.honeywellaerospace.com/content/dam/honeywell-edam/aero/en-us/products/navigation-and-sensors/air-data-and-pressure/precision-pressure-transducer-ppt/documents/hon-aero-ads-14052-precision-pressure-transducers-users-manual-en.pdf)
- **Vibrating-cylinder transducers** [TRANSFER: AGARD flight-test series, used in "a few air data systems for aircraft"] — [AGARD-AG-160 Vol.11 (Wuest), §4.6.2](http://spaceagecontrol.com/AD-PressureAndFlowMeasurement.pdf):
  - Frequency output with a non-linear p–f relation, linearized digitally.
  - Gas-density effect corrected with an internal temperature sensor; a residual humidity effect of up to about 0.03% remains.
  - "Very insensitive to acceleration, shock and vibration"; negligible hysteresis.
  - Vibrating-beam variants are better than 0.01%.
- **Capacitive transducers**: "Temperature effects are, however, difficult to compensate" — [AGARD-AG-160 Vol.11, §4.5.3](http://spaceagecontrol.com/AD-PressureAndFlowMeasurement.pdf)
- **Pneumatic lag in tubing** [TRANSFER: AGARD; physics applies to any pitot-static or engine pressure line] — [AGARD-AG-160 Vol.11, §5.1–5.2, Eqs. 44–54](http://spaceagecontrol.com/AD-PressureAndFlowMeasurement.pdf):
  - Low-frequency delay τ = 128·µ·L·V/(π·d⁴·p). It is proportional to tube length and volume, inversely proportional to d⁴, and inversely proportional to pressure, so it grows with altitude.
  - Example: a 40 m trailing-cone line gives about 2 s delay at 10,000 m for f < 0.01 Hz.
  - Real delays deviate from the formula because of unknown dimensions, dirt or nozzles near the inlet, non-isothermal flow, and pressure-dependent capsule volume.
  - Tubing resonances appear at higher frequency.

**Air-data probes (pitot-static, AoA/AoS)**
- **AoA from a flow-angle probe** [TRANSFER: AGARD flight-test practice; physics applies directly to fighter noseboom and vane installations]: needs corrections for (i) local flow disturbance (upwash), (ii) pitch rate, and (iii) boom/aircraft bending under aerodynamic and inertial load — [AGARD-AG-160 Vol.11, §3.6.4](http://spaceagecontrol.com/AD-PressureAndFlowMeasurement.pdf)
- **Vane accuracy** [TRANSFER: AGARD, unmanned test vehicle]: a free-swivelling vane gave accuracy "better than 0.3°" under up to 20 g, M 0.5–2.8 and dynamic pressure ≥65 psi. Cylindrical direction probes are "particularly sensitive to vibrations" — [AGARD-AG-160 Vol.11, §3.6.3 and §3.6.2(e)](http://spaceagecontrol.com/AD-PressureAndFlowMeasurement.pdf)
- **Static-source accuracy** [TRANSFER: AGARD] — [AGARD-AG-160 Vol.11, §3.5.2.6 and §3.5.3](http://spaceagecontrol.com/AD-PressureAndFlowMeasurement.pdf):
  - Supersonic static probes achieve about ±0.01 q_c up to M2.5.
  - In-service pitot-static accuracy studies assumed position error constant at ±0.004 q_c. Average in-service performance was about 1/3 of the worst-case limits.
- **F-18 HARV data correction** [DIRECT: F-18 HARV]: angle-of-attack and accelerometer data were corrected for sensor offsets from the CG, and AoA "was corrected for upwash". After that, data compatibility analysis showed the data were consistent enough that no further corrections were needed — [Morelli & Klein, AIAA 95-3499 / NASA CR-203351, flight-test section](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf)
- **Pitot-static failure signatures** [TRANSFER: generic, tertiary source]:
  - Position error depends on airspeed, AoA, weight, acceleration and configuration.
  - Lag depends on tubing length, diameter and instrument volume.
  - Blocked pitot (with drain also blocked): airspeed reads high in a climb and low in a descent.
  - Blocked static: altimeter freezes; airspeed reverses sense.
  - Source: [Wikipedia: Pitot-static system](https://en.wikipedia.org/wiki/Pitot-static_system)

**Shaft-speed sensors**
- **F404-400 speed sensors** [DIRECT: F404-400] — [NASA CR-191195, §3.3.7–3.3.8 and §5.1.5 word table, p.21](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf):
  - NL uses "two electrical eddy current speed transmitters mounted on the fan frame to count the titanium fan blade tips" (dual for flight safety).
  - NH comes from a separate winding on a gearbox-mounted alternator.
  - Frequency ranges: NL 2787–10,683 Hz; NH 195–4425 Hz.
- **Prototype NH jitter** [DIRECT: F404 ground test, prototype optical NH]: the signal was "very noisy/fluctuating" because of "poor resolution in the signal's digital processing, such that a small amount of speed jitter results in a large apparent speed signal jump" — [NASA CR-191195, §10.1.3](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf)
- **Variable-reluctance sensors** [TRANSFER: generic, tertiary source]: frequency and amplitude are proportional to target speed, so each system has a practical lower speed limit. Hall sensors are "true zero-rpm" — [Wikipedia: Variable reluctance sensor](https://en.wikipedia.org/wiki/Variable_reluctance_sensor)

**Position sensors (LVDT/RVDT/potentiometer)**
- **F404-400 position sensors** [DIRECT: F404-400]: FVG uses "a single electrical LVDT position sensor mounted inside the FVG actuator". VEN uses a single LVDT in a separate housing, cooled by circulating hydraulic fluid. CVG uses mechanical feedback to the MFC — [NASA CR-191195, §3.3.4–3.3.6](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf)
- **Ground-test comparisons, two sensors on the same quantity** [DIRECT: F404 ground test] — [NASA CR-191195, §10.1.3](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf):
  - FVG optical vs LVDT: "very little offset, within approximately 0.1 inches" over a 2.7 in stroke.
  - CVG optical vs potentiometer: "offset about 10 rotational degrees (a calibration bias), but tracked very well".
  - VEN optical: "a little noisy … a scaling error such that optical sensor range was foreshortened".
- **LVDT generics** [TRANSFER: tertiary source]:
  - Excitation 1–10 kHz.
  - A small residual "quadrature" null voltage exists.
  - Safety designs monitor the sum of the secondary voltages, which stays nearly constant over the stroke; a deviation flags an internal fault.
  - Source: [Wikipedia: LVDT](https://en.wikipedia.org/wiki/Linear_variable_differential_transformer)

**Accelerometers**
- **Servo quartz-flexure, Honeywell QA-2000** [TRANSFER: navigation-grade accelerometer used in "commercial and military aircraft strap-down inertial navigation systems"] — [QA-2000 brochure (N61-2509, 2020)](https://prod-edam.honeywellaerospace.com/content/dam/honeywell-edam/aero/en-us/products/navigation-and-sensors/accelerometers-and-gyroscopes/q-flex-qa-2000-single-axis-quartz-accelerometer/documents/hon-aero-n61-2509-000-000-8989-qa-2000-accelerometer-brochure-en1.pdf):
  - Bias <4 mg; one-year bias repeatability <160 µg (-030), <220 µg (-020), <550 µg (-010).
  - Temperature sensitivity <30 µg/°C and <180 ppm/°C.
  - Scale-factor one-year repeatability <310, <500 and <600 ppm.
  - Vibration rectification <20–40 µg/g²rms (50–500 Hz) and <60–150 µg/g²rms (500–2000 Hz).
  - Intrinsic noise <7 µg rms (0–10 Hz) and <70 µg rms (10–500 Hz).
  - Bandwidth >300 Hz; misalignment <2000 µrad; resolution <1 µg.
- **MEMS tactical IMU, HG4930, factory-fresh vs 10-year end of life** [TRANSFER: tactical MEMS IMU; a direct quantification of aging] — [HG4930 datasheet, p.2](https://prod-edam.honeywellaerospace.com/content/dam/honeywell-edam/aero/en-us/products/navigation-and-sensors/inertial-measurement-units/hg4930-mems-inertial-measurement-unit/documents/hon-aero-n61-3380-000-000-hguide-4930-mems-imu-datasheet-en.pdf):

  | Accelerometer parameter | Factory fresh | 10-year end of life |
  |---|---|---|
  | In-run bias | 0.025–0.075 mg | unchanged |
  | Turn-on bias repeatability | 1.7–3.0 mg | 5–10 mg |
  | Velocity random walk | 0.03–0.06 m/s/√h | 0.09–0.12 m/s/√h |
  | Scale-factor accuracy | 70–120 ppm | 600–1000 ppm |
  | Vibration rectification error | 2–5 mg | 15–25 mg |

  Data rate 600/100 Hz; bandwidth 70/180 Hz (−90°/−3 dB).
- **Structural modes in fighter residuals** [DIRECT: F-18 HARV flight test]: residuals for α and a_z "exhibited considerable power at high frequencies, due to unmodeled structural modes"; the pitch-rate residual did not — [Morelli & Klein 1995, Results](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf)

**Gyros (RLG / FOG / MEMS)**
- **RLG, Honeywell GG1320AN** [TRANSFER: navigation-grade RLG of the type used in military INS] — [Honeywell GG1320AN page](https://www.honeywellaerospace.com/us/en/products-and-services/product/hardware-and-systems/sensors/gg1320an-digital-ring-laser-gyroscope):
  - Bias stability 0.0035 °/h typical; ARW 0.0035 °/√h.
  - Output 2000 Hz typical (5000 Hz max); latency 168 µs.
  - Magnetic sensitivity 0.002 °/h/gauss; scale factor 1,164,352 ± 18 pulses/rev.
  - [DERIVED] Angle quantum = 1,296,000″/1,164,352 ≈ 1.11 arcsec per pulse.
- **HG9900 navigation-grade IMU** (RLG + quartz accelerometers): gyro in-run bias 0.0021 °/h, repeatability 0.0041 °/h, ARW 0.0021 °/√h; accelerometer repeatability "25 micro g" (the page's units are inconsistent); 300 Hz — [Honeywell HG9900 page](https://www.honeywellaerospace.com/us/en/products-and-services/products/navigation-and-sensors/inertial-measurement-units/hg9900-inertial-measurement-unit)
- **HG1700 tactical RLG IMU**: gyro bias 1–5 °/h (1σ), ARW 0.125–0.5 °/√h; accelerometer bias 1–3 mg, VRW 0.065 ft/s/√h; 100 Hz guidance and 600 Hz control rates — [HG1700 brochure](https://prod-edam.honeywellaerospace.com/content/dam/honeywell-edam/aero/en-us/products/navigation-and-sensors/inertial-measurement-units/hg1700-inertial-measurement-unit/documents/hon-aero-n61-1619-000-001-hg1700-inertial-measurement-unit-brochure-en.pdf)
- **HG4930 MEMS gyro, fresh → 10-year end of life** — [HG4930 datasheet](https://prod-edam.honeywellaerospace.com/content/dam/honeywell-edam/aero/en-us/products/navigation-and-sensors/inertial-measurement-units/hg4930-mems-inertial-measurement-unit/documents/hon-aero-n61-3380-000-000-hguide-4930-mems-imu-datasheet-en.pdf):

  | Gyro parameter | Factory fresh | 10-year end of life |
  |---|---|---|
  | In-run bias | 0.25–0.45 °/h | 1.0–2.0 °/h |
  | Turn-on bias repeatability | 7–20 °/h | 20–60 °/h |
  | ARW | 0.04–0.06 °/√h | 0.09–0.175 °/√h |
  | Vibration rectification error | 5–10 °/h | 30–40 °/h |

  Bias stability is ">0.5 °/hr when measured over a constant operating period of one month".
- **Navigation-grade benchmark**: about 0.005 °/√h noise and 0.01 °/h drift give roughly 1 nmi/h. The paper models gyro error as white noise plus first-order Markov drift — [Wheeler et al., IEEE Sensors J. / arXiv 2202.09360, p.1](https://arxiv.org/abs/2202.09360)
- **Standards**: IEEE Std 952 (single-axis interferometric FOG) — [doi:10.1109/IEEESTD.1998.86153](https://doi.org/10.1109/IEEESTD.1998.86153); IEEE Std 647-2006 (single-axis laser gyros) — [doi:10.1109/IEEESTD.2006.246241](https://doi.org/10.1109/IEEESTD.2006.246241); IEEE Std 1293-2018 (linear accelerometers) — [doi:10.1109/IEEESTD.2019.8653544](https://doi.org/10.1109/IEEESTD.2019.8653544). Only metadata was retrieved; the full texts are paywalled. IEEE 1554 was not retrieved.
- **Allan-variance noise model**, after IEEE 952 practice — [MathWorks "Inertial sensor noise analysis using Allan variance"](https://fr.mathworks.com/help/nav/ug/inertial-sensor-noise-analysis-using-allan-variance.html); [El-Sheimy, Hou & Niu 2008, IEEE TIM, doi:10.1109/TIM.2007.908635](https://doi.org/10.1109/TIM.2007.908635):

  | Term | Allan variance | Slope (log-log) | Where read |
  |---|---|---|---|
  | Angle random walk N | N²/τ | −1/2 | τ = 1 s |
  | Rate random walk K | K²τ/3 | +1/2 | τ = 3 s |
  | Bias instability B (flicker) | — | 0 (flat) | B = σ_min/0.664 |
  | Quantization | 3Q²/τ² | −1 | — |
  | Rate ramp | — | +1 | — |

**Oil-debris monitors and chip detectors**
- **Fielded on fighters** [DIRECT: F-35/F135, Typhoon/EJ200, F-22/F119] — [Gastops F-35 guide](https://www.gastops.com/wp-content/uploads/MS1000-F-35-Lightning-II-Application-Guide.pdf); [Gastops Typhoon guide](https://www.gastops.com/wp-content/uploads/MS1000-Eurofighter-Typhoon-Application-Guide.pdf); [MetalSCAN page](https://www.gastops.com/products-services/metalscan/):
  - MetalSCAN is fitted on the F-35/F135 (sensor MS1324 at the lube-pump outlet; ferrous/non-ferrous counting, limit exceedance and trending done in the FADEC).
  - It is fitted on the Typhoon/EJ200 (MS1220 on the accessory gearbox; standalone conditioning unit plus airframe Engine Monitoring Unit).
  - It is fitted on the F-22/F119.
- **Detection thresholds by sensor bore**: minimum detectable particle (sphere) is 126/171/209/276/350 µm ferrous and 388/455/515/619/716 µm non-ferrous for bores of 1/4″ to 1″. Size reporting uses "configurable bins". The output is a **count process by size bin and type**, not a continuous signal — [Gastops MS1000 Product Overview, Specifications](https://www.gastops.com/wp-content/uploads/MS1000-Product-Overview.pdf)
- **Vendor case study** (vendor claim): an electric chip detector "did not trigger an alarm until after critical damage" — [same](https://www.gastops.com/wp-content/uploads/MS1000-Product-Overview.pdf)

**Strain gauges**
- [TRANSFER: Kulite vendor comparison, which favours silicon gauges] — [Kulite "Selecting Strain Gages: Silicon vs Metal Foil"](https://kulite.com//assets/media/2018/01/SelectingStrainGagesSiliconvsMetalFoil.pdf):

  | Property | Foil gauge | Silicon gauge |
  |---|---|---|
  | Gauge factor | 1–3 | 50–200 |
  | TCR | ~1%/100 °F | — |
  | TCGF | −3%/100 °F | — |
  | Transverse sensitivity | 3% | 1% |
  | Fatigue life | 10⁴–10⁷ cycles | — |

  Foil gauges need roughly 4000 µε for an acceptable signal, below which "low-level electrical noise affects the resolution". Their plastic backing "is more likely to exhibit creep and hysteresis".

**Gas-path measurement "non-repeatability" as used in literature** (all assume zero-mean Gaussian noise)
- **ProDiMES (C-MAPSS-based fleet benchmark)**, average σ at takeoff/cruise, "proportional to the sensed parameter magnitude" [TRANSFER: commercial high-bypass turbofan simulation] — [NASA TM-2008-215271, Table 1, p.7](https://ntrs.nasa.gov/api/citations/20080032563/downloads/20080032563.pdf):

  | Parameter | σ takeoff | σ cruise |
  |---|---|---|
  | Nf | 5.59 rpm | 4.64 rpm |
  | Nc | 15.10 rpm | 13.23 rpm |
  | Ps30 | 0.889 psia | 0.220 psia |
  | T30 | 2.47 °R | 1.92 °R |
  | T48 (EGT) | 10.20 °R | 7.55 °R |
  | Wf | 0.058 pps | 0.011 pps |
  | P2 | 0.023 psia | 0.008 psia |
  | T2 | 0.838 °R | 0.707 °R |

- **C-MAPSS** σ as % of trim: Nf 0.25, Nc 0.25, P24 0.50, T24 0.75, Ps30 0.50, T30 0.75, T48 0.75 — [Simon & Garg, NASA TM-2010-216076, Table 2](https://ntrs.nasa.gov/api/citations/20100006914/downloads/20100006914.pdf)
- **C-MAPSS40k** σ: Nf 0.360 rpm, Nc 1.23 rpm, Ps30 0.333 psia, T30 0.273 °R, T50 0.259 °R, Wf 9.03 pph; "assumed to be uncorrelated, zero-mean and normally distributed" — [Simon & Rinehart, NASA TM-2016-218926, Table 3](https://ntrs.nasa.gov/api/citations/20160001158/downloads/20160001158.pdf)
- **Bank-of-Kalman-filters study** σ as % of trim: XN2/XN25 0.25; T27D, T56, PS15, P27, PS3, PS56 0.50. These are "rough estimates derived from Lu et al." — [Kobayashi & Simon, NASA TM-2003-212526, Table 2](https://ntrs.nasa.gov/api/citations/20030067984/downloads/20030067984.pdf)

### Inferences
- [DERIVED from AGARD Eq. 82 and NACA Eq. 6] An EGT probe whose mass flux varies about 9:1 between idle and maximum power would see roughly a 3:1 change in time constant. This matches AGARD's "3 to 1" statement. The virtual fighter's T5/EGT sensor model should use τ(W) ∝ W^−0.5 with a two-exponential (0.8/0.2) response, not a fixed first-order lag.
- [DIRECT inference from FOCSI] A virtual F404-class engine should model the T5 harness as N probes with a circumferential temperature profile:
  - an open probe produces a step in the average when it is excluded;
  - a shorted probe produces a low reading, which raises commanded fuel flow and makes the true EGT rise.
  These closed-loop sensor-fault couplings are what downstream PHM models must learn.
- [DERIVED] Literature gas-path σ values (0.25–0.75% of reading, or ProDiMES absolute values) are useful magnitude anchors for snapshot non-repeatability. They are modelling assumptions, not measured residual statistics.
- [TRANSFER inference from HG4930 aging] Inertial (and probably other MEMS) error parameters should be **tail-specific and age-dependent**: draw per-unit biases at install and grow them over service life. Otherwise every simulated aircraft is identical.

### Gaps
- No public numbers found in this pass for:
  - AoA vane natural frequency and damping;
  - fighter-specific static-source position-error curves (F-16/F-18/Tejas);
  - capacitance fuel-quantity probe accuracy, attitude and slosh errors;
  - turbine fuel flowmeter accuracy and response;
  - oil pressure/temperature transducer specs;
  - proximity (eddy-current) probe specs;
  - Hall-effect current and voltage sensors (the LEM datasheet fetch failed);
  - RTD self-heating.

  Candidate sources for a follow-up search pass: NASA TM-104316 (Haering, "Airdata measurement and calibration"); Grauer NASA TM-2017-219795 (position corrections); Whitmore's pneumatic-lag TMs; Rosemount/Goodrich TR 5755 (total-temperature sensors); MIL-G-26988 / SAE AIR on fuel gauging; Eldec/Ametek/Meggitt fuel-flow datasheets; the AGARD-AG-160 flight-test instrumentation volumes on fuel flow and data acquisition.
- Measured gas-path non-repeatability from real military engines (e.g., F404/F110/RM12 EHM snapshot scatter) was not found publicly. Volponi 2014 ([doi:10.1115/1.4026126](https://doi.org/10.1115/1.4026126)) and Doel's TEMPER papers likely contain commercial-engine values but were not accessible.
- F404-GE-IN20 FADEC sensor suite and signal-validation logic are not public in what was reached.

---

## Q2. Signal-chain effects (conditioning → ADC → digital processing → bus)

### Takeaway
The signal chain imprints its own deterministic texture:
- quantization at the ADC and again at the bus/recorder word (ARINC 429 BNR LSB, 1553 16-bit, ARINC 717 12-bit);
- sensor-side averaging, deadbands and decimation;
- update-interval jitter and transport delay between asynchronous subsystems;
- validity/status codes that replace values;
- redundancy-management rules (averaging with exclusion, quad channels) that make faults appear as steps rather than noise.

Quantization alone measurably biases model estimates, not only variance.

### Cited Findings
- **Quantization model and its effect** [TRANSFER: NASA GTM transport simulation, cross-checked with an F-16 simulation; results "scale with vehicle size"] — [Grauer & Morelli, NASA TM-2013-218056, §4.2 and Table 4](https://ntrs.nasa.gov/api/citations/20140003885/downloads/20140003885.pdf):
  - Quantization is modelled as z_q = Δz·round(z/Δz). As resolution coarsens, "resolution errors manifest as increased biases in the parameter estimates".
  - Resolution needed for 2%/5%/10% derivative-accuracy budgets:

    | Measurement | 2% | 5% | 10% |
    |---|---|---|---|
    | α, β | 0.10° | 0.20° | 0.40° |
    | Dynamic pressure | 0.0089 psf | 0.145 psf | 2.24 psf |
    | Gyros | 1.87 °/s | 4.21 °/s | 5.54 °/s |
    | Accelerometers | 0.0127 g | 0.026 g | 0.052 g |
    | Surface potentiometers | 0.039° | 0.246° | 0.453° |
- **ARINC 429 word** [TRANSFER: civil avionics bus; it appears on some fighter subsystems and the Data Pathway researcher covers the details] — [AIM ARINC 429 Tutorial, pp.11–16](https://www.aim-online.com/wp-content/uploads/2019/07/aim-tutorial-oview429-190712-u.pdf):
  - 32-bit word: label 8 bits, SDI 2, data 19, SSM 2, parity 1 (odd).
  - BNR is two's complement: bit 29 is the sign and bit 28 is "½ of the maximum value of the defined parameter's scale factor", halving per bit.
  - BNR SSM codes: 00 Failure Warning, 01 No Computed Data, 10 Functional Test, 11 Normal Operation.
  - Attachment 2 of the spec tabulates, per parameter: units, range, significant bits, resolution, min/max transmit intervals and max transport delay.
  - Bit rates: 100 kbps or 12–14.5 kbps.
- **MIL-STD-1553** [DIRECT: used on F-16 (first use), F/A-18, F-15, Gripen; NATO STANAG 3838 on Tornado and Typhoon] — [Wikipedia: MIL-STD-1553](https://en.wikipedia.org/wiki/MIL-STD-1553):
  - 1 Mbit/s; 16-bit data words (20 bits with sync and parity); 1–32 data words per message.
  - The bus controller initiates all transfers; the standard "does not specify timing for particular transfers", which is left to system designers.
- **F404 FOCSI processing unit** [DIRECT: F404 FOCSI electro-optic unit on 1553] — [NASA CR-191195, §5.1.5, §5.3, p.21–24](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf):
  - Output was 14 words on MIL-STD-1553.
  - T5 was coded as "a 12 bit binary code, representing T5 temperatures from 700 to 2500 °F" plus two status bits (BIT and optical-path condition). [DERIVED] That is about 0.44 °F (0.24 K) per count.
  - The unit had a 10 ms update rate.
  - The optical T5 floors at 700 °F (a display/range clamp).
  - The T2.5 channel saturated "at its 540 °F limit during an engine acceleration" because of a calibration offset (clipping).
- **Sensor update rates and latencies**:
  - [TRANSFER: commercial engine control] "an engine controller may sample sensor data at 20 to 50 Hz, typically only a fraction of the data is transferred to ground-based health management systems" — [ProDiMES, NASA TM-2008-215271, p.5](https://ntrs.nasa.gov/api/citations/20080032563/downloads/20080032563.pdf)
  - GG1320 gyro: 2 kHz output, 168 µs latency — [Honeywell](https://www.honeywellaerospace.com/us/en/products-and-services/product/hardware-and-systems/sensors/gg1320an-digital-ring-laser-gyroscope)
  - HG1700: 100 Hz guidance / 600 Hz control — [brochure](https://prod-edam.honeywellaerospace.com/content/dam/honeywell-edam/aero/en-us/products/navigation-and-sensors/inertial-measurement-units/hg1700-inertial-measurement-unit/documents/hon-aero-n61-1619-000-001-hg1700-inertial-measurement-unit-brochure-en.pdf)
  - [TRANSFER: NASA T-2 subscale jet] Flight data "sampling rate … was 200 Hz, decimated to 50 Hz"; structural modes above 10 Hz; turbulence assessed in the 2–7 Hz band — [Morelli & Cunningham 2012, "Aircraft Dynamic Modeling in Turbulence", §III.B and §IV.A](https://ntrs.nasa.gov/api/citations/20120014567/downloads/20120014567.pdf)
- **Time skews**: data compatibility analysis removes systematic errors that are "typically biases, scale factor errors, and relative time skews". Morelli (2017) gives a method for modelling with unknown time skews — [Morelli & Grauer 2023, J. Aircraft, §Data compatibility](https://ntrs.nasa.gov/api/citations/20230001945/downloads/MorelliGrauerAdvancesAircraftSIDJOA_2023.pdf); [Morelli 2017 JGCD, doi:10.2514/1.G002008](https://doi.org/10.2514/1.G002008)
- **Sensor-internal processing** [TRANSFER: Honeywell PPT]: integration (averaging over the A/D cycle), deadband and idle-count skipping are user-configured — [PPT User's Manual §4](https://prod-edam.honeywellaerospace.com/content/dam/honeywell-edam/aero/en-us/products/navigation-and-sensors/air-data-and-pressure/precision-pressure-transducer-ppt/documents/hon-aero-ads-14052-precision-pressure-transducers-users-manual-en.pdf)
- **Redundancy architecture** [DIRECT]:
  - The F-16 has "a quadruplex (four-channel) fly-by-wire flight control system"; "the loss of one channel renders the FLCS a 'triplex' system" — [Wikipedia: F-16, citing Droste & Walker 1980](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon)
  - The F404 has dual NL speed sensors and an 8-probe T5 average with open-probe exclusion — [NASA CR-191195](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf)
- **EMI** [DIRECT: F404 test]: "apparent radiated and conducted interference" prevented the NL electro-optic circuit from working in the integrated unit. Conducted and radiated emissions testing (CE102/RE102) was part of qualification — [NASA CR-191195, §10.1.3 and environmental test section](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf)

### Inferences
- [ASSUMPTION, validate against the platform ICD from the Data Pathway researcher] Each bus-carried parameter should be encoded with its actual LSB, computed as range/2^(significant bits) per ARINC 429 Attachment 2, or its 1553 scaling. The virtual fighter should emit the decoded value with that lattice and with SSM/validity codes, so the output carries the real stair-step structure.
- [ASSUMPTION] Asynchronous subsystems (FADEC at tens of Hz, INS at 50–600 Hz, ADC, mission computer) should each run on their own clock with jitter, and the consumer should sample-and-hold the latest value. This reproduces stale-data repeats and inter-channel time skews of one or more frames. Validate by measuring repeat-run-length statistics in any real recorded data that becomes available.
- [ASSUMPTION; mechanism shown in F404 T5 and F-16 FLCS sources] Redundancy-management rules should be modelled explicitly (averaging with exclusion, mid-value select, monitor thresholds). Without them, simulated sensor faults appear as noise instead of as the steps and latches seen in real systems.

### Gaps
- No public FADEC (F404-IN20/F110/RM12) data on sample rates, anti-alias filters, digital filters, range/rate-check thresholds or mid-value-select tolerances were found.
- No published ARINC 429 Attachment-2 rows (e.g., specific label resolution and transmit intervals) were retrieved. The spec itself is paywalled; equipment installation manuals often reproduce the rows and would be a good follow-up source.

---

## Q3. Recording effects (recorder rates, framing, packing, gaps)

### Takeaway
Recorders subsample, requantize and frame the bus data:
- 12-bit words in 1-second subframes inside a 4-second frame (ARINC 717);
- per-parameter intervals from 0.125 s to 64 s (civil FDR rules);
- time correlation across parameters only "within one second";
- for engine health, often only "snapshots" at two or three operating points per flight (military: ground idle and takeoff).

These artefacts are easy for a classifier to spot and matter for PHM.

### Cited Findings
- **ARINC 717 framing** [TRANSFER: civil FDR format; the Data Pathway researcher owns the details]: 12-bit words "sent in a 4 seconds frame divided into four 1 second sub-frames". Each subframe has 64 (basic), 128, 256, 512, 1024, 2048, 4096 or 8192 words, with a sync word first. Encoding is Harvard bi-phase — [Aparna, IJERECE 3(2) 2016, §II.D](https://www.technoarete.org/common_abstract/pdf/IJERECE/v3/i2/3.pdf)
- **Civil FDR minimums** [TRANSFER: 14 CFR 121 App. M FDR rules for transport aircraft; fighters are not bound by them, but they show realistic recorder rates and resolutions] — [14 CFR 121 Appendix M (LII)](https://www.law.cornell.edu/cfr/text/14/appendix-M_to_part_121):

  | Parameter | Sampling interval | Resolution | Accuracy |
  |---|---|---|---|
  | Normal acceleration | 0.125 s | 0.004 g | ±1% of max range |
  | Longitudinal/lateral acceleration | 0.25 s | 0.004 g | — |
  | Pitch attitude | 1 s (0.25 s for some aircraft) | 0.5° | ±2° |
  | AoA | 2 s or 0.5 s | 0.3% FS | — |
  | OAT/TAT | 2 s | 0.3 °C | ±2 °C |
  | Engine thrust | 1 s per engine | 0.3% FS | ±2% |
  | Fuel quantity (CG trim tank) | 64 s | 1% FS | ±5% |
  | Surface positions | 0.5 s | 0.2–0.5% FS | ±2° |

  Two general rules: "All data recorded must be correlated in time to within one second", and the recorded values must meet range, resolution and accuracy requirements in static and dynamic conditions.
- **Engine health snapshots** [TRANSFER: engine health management practice; the military statement is explicit] — [ProDiMES, NASA TM-2008-215271, p.5](https://ntrs.nasa.gov/api/citations/20080032563/downloads/20080032563.pdf):
  - "A typical application will instead record 'snap-shot' engine gas-path measurements collected at two to three operating points during each flight."
  - "Military applications … may be limited to recordings at ground idle and takeoff."
  - The system may "wait until the engine achieves quasi-steady-state operation, and then archive the average sensor measurements recorded over a window of time".
- **Discrete semantics in real recorder data** [TRANSFER: DASHlink regional jet]:
  - Weight-on-wheels = 1 means *airborne*; the gear-down discrete reads 0 when the gear is down. These are "merely the status of an electrical circuit".
  - Per-engine N1 commands are not recorded.
  - Source: [NASA DASHlink Sample Flight Data FAQ (2014)](https://c3.ndc.nasa.gov/dashlink/static/media/other/Sample_Flight_Data_FAQ_2.doc)
- **DASHlink dataset**: 186 parameters, about three years of operations of one regional-jet type, MATLAB files, de-identified — [DASHlink Sample Flight Data](https://c3.ndc.nasa.gov/dashlink/projects/85/)

### Inferences
- [ASSUMPTION; validate with real recorder dumps] The virtual recorder should do the following:
  - place each parameter at a fixed subframe/word slot with a fixed rate;
  - store values at recorder-word resolution, independent of bus resolution;
  - carry a frame counter;
  - inject frame-sync loss and bit errors as bursts (see Q6);
  - start and stop recording on power/WOW logic, leaving gaps before engine start and after shutdown.
- [DIRECT inference for a military PHM layer] EHM-style snapshot products (averaged steady windows at ground idle and takeoff) are a separate data product from continuous recorder streams. The virtual fighter should emit both, with snapshot noise that depends on window length and operating point.

### Gaps
- No public specification of fighter crash-survivable or maintenance recorder formats (F-16, F/A-18, Tejas, Su-30MKI) was found. This should be obtained by the Data Pathway researcher.
- No empirical statistics on frame-sync loss or bit-error rates for real recorders were found.

---

## Q4. Empirical texture in real flight data (what residuals actually look like)

### Takeaway
Peer-reviewed analyses of real fighter flight data show residuals that are:
- **coloured**, with high-frequency structural-mode content on some channels and not others;
- **regime- or turbulence-dependent**;
- **affected by calibration offsets and time skews**.

The F404 ground-test comparisons between two sensors measuring the same quantity show further artefacts:
- static offsets up to about 10° (CVG) and about 0.1 in (FVG);
- scale errors;
- lag differences that appear only in transients;
- resolution-induced jitter;
- dropouts to zero;
- clipping;
- noise that grows with engine speed and vibration.

Public datasets with fighter raw sensor residual statistics (PSDs, Allan curves, kurtosis) were not found.

### Cited Findings
- **Coloured residuals, F-18 HARV** [DIRECT: F-18 HARV, 50 Hz, about 14 s maneuvers at 20° AoA] — [Morelli & Klein 1995, NASA CR-203351](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf):
  - Residuals from maximum-likelihood estimation "are almost always colored in practice, due to deterministic modeling error".
  - α and a_z residuals had broadband high-frequency power from structural modes; the q residual did not.
  - Conventional Cramér-Rao bounds were therefore "very optimistic" for pitching-moment parameters. Sample-scatter to bound ratios exceeded 3; corrected bounds matched the scatter across repeated flight maneuvers.
- **Coloured residual estimation methods** — [Morelli & Grauer 2023](https://ntrs.nasa.gov/api/citations/20230001945/downloads/MorelliGrauerAdvancesAircraftSIDJOA_2023.pdf):
  - real-time characterisation of "generally colored residuals in a sliding data window" — [Grauer 2016, doi:10.2514/6.2016-2009](https://doi.org/10.2514/6.2016-2009);
  - a filter-error method in turbulence — [Grauer & Morelli 2015, doi:10.2514/6.2015-2704](https://doi.org/10.2514/6.2015-2704);
  - noise characteristics estimated from flight data by optimal Fourier smoothing — [Morelli 1995, doi:10.2514/3.46778](https://doi.org/10.2514/3.46778).
- **Turbulence as a regime covariate** [TRANSFER: T-2 subscale jet at low altitude]: a σ_w over 2–7 Hz, computed in a sliding 30 s window and updated every 1 s, tracked pilot turbulence ratings. "Effects of turbulence on aircraft response measurements are similar to colored noise" — [Morelli & Cunningham 2012, §IV](https://ntrs.nasa.gov/api/citations/20120014567/downloads/20120014567.pdf)
- **Two sensors on the same quantity, F404-400 engine ground runs** [DIRECT: F404-400 ground runs; prototype optical vs production electrical sensors] — [NASA CR-191195, §10.1.3–10.2](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf):
  - T1 offsets within 5 °C.
  - T5 steady-state agreement but transient mismatch.
  - CVG about 10° calibration bias; FVG within about 0.1 in; VEN scaling error.
  - NH "noisy/fluctuating" from resolution-induced jitter.
  - NL "accurately tracked … for part of the speed range, but then dropped off to zero".
  - T2.5 saturated at 540 °F.
  - Optical signal fluctuations "increase at higher engine speeds (airflows/vibration levels)".
  - Optical T2.5 calibration shifted 15–20 °F after a 50 h, 350 °F cable soak.
- **Gross errors in engine diagnostics**: a robust dual Kalman filter for turbofan performance monitoring was designed "to tolerate roughly 20 to 30% faulty data". Gross errors and outliers are therefore expected in engine measurement streams [TRANSFER: OBIDICOTE turbofan model; abstract only] — [Dewallef & Léonard 2003, ORBi record](https://orbi.uliege.be/handle/2268/20915)
- **Benchmarks use ideal sensors**: the widely used C-MAPSS engine simulation runs "ideal sensors and actuators … just unity gains, with no dynamics". Users must add sensor dynamics (example fan-speed sensor bandwidth 50 rad/s), noise and bias themselves — [C-MAPSS User's Guide, NASA TM-2007-215026, §4.4](https://ntrs.nasa.gov/api/citations/20070034949/downloads/20070034949.pdf)
- **Heteroscedastic by construction**: even the ProDiMES benchmark makes σ "proportional to the sensed parameter magnitude", with different takeoff and cruise σ — [NASA TM-2008-215271, Table 1](https://ntrs.nasa.gov/api/citations/20080032563/downloads/20080032563.pdf)

### Inferences
- [DIRECT inference] For fighter-class airframes, accelerometer and flow-angle channels should carry narrow-band structural-mode content (frequencies from the airframe model, typically above about 5–10 Hz). Rate gyros mounted near the CG may carry less. Leaving this out removes a key part of the real spectral signature.
- [ASSUMPTION; validate with any real multi-flight dataset] Residual variance should be conditioned on regime: engine speed/vibration level, turbulence metric, g-load, flight phase. Treating it as constant misses the heteroscedasticity seen in both the FOCSI and T-2 evidence.
- [ASSUMPTION] Cross-sensor residual correlation should arise from shared physical causes:
  - shared temperature driving thermal zero shifts in co-located pressure transducers;
  - shared structural vibration on a_z and α;
  - shared time skew per bus;
  - common CG-offset kinematics.
  The HARV α/a_z case is direct evidence for the shared-vibration mechanism. The others need validation via residual cross-spectra on real data.

### Gaps
- No public empirical PSDs, Allan-deviation curves, kurtosis or outlier rates for production fighter sensors in flight were found.
- No published heavy-tail statistics for EGT/N1/N2/Wf in military EHM data were found.
- DASHlink-based residual-texture studies could not be retrieved after the search budget ran out.

---

## Q5. Methods to model and learn residuals, including when the true signal is unknown

### Takeaway
The best-supported approach is a physically structured, parametric measurement model (dynamics, bias/scale factor, composite coloured noise, environmental terms, quantization, bus and recorder) whose parameters are:
1. seeded from datasheets and standards;
2. refined from real data using truth-free estimation methods:
   - Allan variance or wavelet-variance (GMWM) fits on static or steady segments;
   - redundant-sensor variance separation (Grubbs, three-cornered hat, triple collocation);
   - kinematic data-compatibility checks;
   - smoother/innovation-based covariance identification (Mehra, ALS, EM; filter-error method in turbulence).

Deep generative models (TimeGAN, diffusion, flows, VAEs) are better used as conditional residual learners on top of this physics layer, and only once enough real data exists. They were not validated on aircraft sensor residuals in the sources found.

### Cited Findings
**Parametric stochastic models**
- **Allan variance and composite noise** (white, flicker/bias-instability, random walk, ramp, quantization) with standard slope/coefficient identification — [MathWorks Allan-variance example](https://fr.mathworks.com/help/nav/ug/inertial-sensor-noise-analysis-using-allan-variance.html); [El-Sheimy et al. 2008, doi:10.1109/TIM.2007.908635](https://doi.org/10.1109/TIM.2007.908635)
  - MathWorks simulates bias instability as pink (1/f) noise via a 500-pole fractal filter.
- **Generalized Method of Wavelet Moments (GMWM)** estimates composite stochastic-process parameters from wavelet variance, avoiding manual slope fitting — [Guerrier et al. 2013, JASA, doi:10.1080/01621459.2013.799920](https://doi.org/10.1080/01621459.2013.799920)
- **Mapping noise characterisation to state-space models** — [Jerath, Brennan & Lagoa 2018, Measurement, doi:10.1016/j.measurement.2017.09.012](https://doi.org/10.1016/j.measurement.2017.09.012)
- **1/f^α noise synthesis** for flicker/bias-instability terms — [Kasdin 1995, Proc. IEEE, doi:10.1109/5.381848](https://doi.org/10.1109/5.381848)
- **Quantization noise theory** (when the uniform/white approximation holds and when it fails) — [Widrow & Kollár 2008, doi:10.1017/CBO9780511754661](https://doi.org/10.1017/CBO9780511754661)
- **First-order Markov drift plus white noise** gyro model, validated by Monte Carlo — [Wheeler et al., arXiv 2202.09360](https://arxiv.org/abs/2202.09360)

**State-space and noise-covariance identification without truth**
- **Data compatibility / flight-path reconstruction**: kinematic consistency estimates biases, scale factors and time skews — [Klein & Morelli 2006 book, doi:10.2514/4.861505](https://doi.org/10.2514/4.861505); [Mulder et al. 1999, Prog. Aerosp. Sci., doi:10.1016/S0376-0421(99)00005-6](https://doi.org/10.1016/S0376-0421(99)00005-6); [Jategaonkar 2015, doi:10.2514/4.102790](https://doi.org/10.2514/4.102790); [Grauer 2015 real-time data compatibility, doi:10.2514/1.C033182](https://doi.org/10.2514/1.C033182)
- **Filter-error method** (process plus measurement noise) — [Grauer & Morelli 2015](https://doi.org/10.2514/6.2015-2704)
  - Context: equation-error ignores measurement noise and output-error ignores process noise — [Morelli & Grauer 2023](https://ntrs.nasa.gov/api/citations/20230001945/downloads/MorelliGrauerAdvancesAircraftSIDJOA_2023.pdf)
- **Innovation-based adaptive estimation of Q/R** — [Mehra 1970, IEEE TAC, doi:10.1109/TAC.1970.1099422](https://doi.org/10.1109/TAC.1970.1099422)
- **Autocovariance least squares (ALS)** — [Odelson, Rajamani & Rawlings 2006, Automatica, doi:10.1016/j.automatica.2005.09.006](https://doi.org/10.1016/j.automatica.2005.09.006)
- **EM for state-space noise parameters** — [Shumway & Stoffer 1982, doi:10.1111/j.1467-9892.1982.tb00349.x](https://doi.org/10.1111/j.1467-9892.1982.tb00349.x)
- **RTS smoother** for smoothed state estimates and residuals — [Rauch, Tung & Striebel 1965, doi:10.2514/3.3166](https://doi.org/10.2514/3.3166)
- **Coloured-residual-aware uncertainty** — [Morelli & Klein 1995](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf); [Grauer 2016](https://doi.org/10.2514/6.2016-2009)

**Redundant sensors**
- **Grubbs' method** separates each instrument's error variance using several instruments measuring the same quantity — [Grubbs 1948, JASA, doi:10.1080/01621459.1948.10483261](https://doi.org/10.1080/01621459.1948.10483261)
- **Triple collocation** estimates the error variances of three independent measurement systems without truth — [Stoffelen 1998, JGR, doi:10.1029/97JC03180](https://doi.org/10.1029/97JC03180)
- **Fighter redundancy available for this** [DIRECT]: F404 dual NL sensors and eight T5 probes — [NASA CR-191195](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf); F-16 quad FLCS — [Wikipedia F-16](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon)
- **Two-thermocouple blind identification** of probe τ in situ — [Hung et al. 2005](https://mural.maynoothuniversity.ie/id/eprint/689/1/EE-McL8.pdf)

**Steady-state and ground segments**
- Snapshot averaging over quasi-steady windows is the industry norm for gas-path data — [ProDiMES](https://ntrs.nasa.gov/api/citations/20080032563/downloads/20080032563.pdf)
- Ground-run comparisons expose offsets, scale errors and dropouts — [FOCSI](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf)
- AGARD notes that ground conditions distort OAT/CIT probes (τ of 15 min or more; self-heating) — [AGARD-AG-160 Vol.2](http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf)

**Heteroscedastic and regime-dependent models**
- GARCH — [Bollerslev 1986, doi:10.1016/0304-4076(86)90063-1](https://doi.org/10.1016/0304-4076(86)90063-1)
- Heteroscedastic Gaussian processes — [Le, Smola & Canu 2005, doi:10.1145/1102351.1102413](https://doi.org/10.1145/1102351.1102413)
- Markov regime switching — [Hamilton 1989, Econometrica, doi:10.2307/1912559](https://doi.org/10.2307/1912559)
- Turbulence metric as an observable regime covariate — [Morelli & Cunningham 2012](https://ntrs.nasa.gov/api/citations/20120014567/downloads/20120014567.pdf)

**Cross-sensor dependence**
- Low-rank Gaussian copula process for high-dimensional multivariate dependence — [Salinas et al. 2019, arXiv 1910.03002](https://arxiv.org/abs/1910.03002)
- Conditioned normalizing flows for multivariate temporal dynamics — [Rasul et al., arXiv 2002.06103](https://arxiv.org/abs/2002.06103)

**Deep generative time-series models**
- **TimeGAN** introduced the post-hoc discriminative score: a 2-layer LSTM trained to tell real from synthetic, scored by held-out classification error. It also introduced the predictive (TSTR) score — [Yoon et al., NeurIPS 2019, §5](https://proceedings.neurips.cc/paper/2019/file/c9efe5f26cd17ba6216bbe2a7d26d490-Paper.pdf)
- **TimeVAE** emphasises interpretability and domain knowledge — [Desai et al., arXiv 2111.08095](https://arxiv.org/abs/2111.08095)
- **Diffusion-TS** uses trend/season decomposition, a Fourier-based loss, and supports conditional imputation and forecasting — [Yuan & Qiao, ICLR 2024, arXiv 2403.01742](https://arxiv.org/abs/2403.01742)
- **CSDI** is a score-based diffusion model for imputation — [Tashiro et al., arXiv 2107.03502](https://arxiv.org/abs/2107.03502)
- **TSGBench** evaluation measures — [Ang et al., arXiv 2309.03755, §4](https://arxiv.org/abs/2309.03755):
  - discriminative score, predictive score, contextual-FID;
  - marginal-distribution difference, autocorrelation difference, skewness difference, kurtosis difference;
  - none of the benchmark datasets are aircraft sensor data.
- **Physics-informed hybrid learning**: universal differential equations embed learned terms inside mechanistic models — [Rackauckas et al., arXiv 2001.04385](https://arxiv.org/abs/2001.04385)

### Inferences
- [ASSUMPTION; validate by held-out discriminative/TSTR tests once real data exist] With no real fighter raw data available now, a **physics-plus-parametric** residual model with datasheet priors is the defensible first deliverable. Learned generative residuals should be added only where real data can train and validate them.
- [DERIVED from Grubbs and triple collocation] F404-style redundancy (8 T5 probes, 2 NL sensors) and multi-sensor air data (left/right probes) are natural truth-free calibration sources. Probe-to-probe scatter at steady state estimates per-probe bias spread; pairwise differences estimate individual noise variances.

### Gaps
- No publication found that trains TimeGAN, diffusion or flow models specifically on aircraft sensor *residuals* and validates them with discriminative tests. Their fidelity for this use is unproven.

---

## Q6. Missingness and dropouts

### Takeaway
Missingness in aircraft data is mostly **structured and informative**, not random:
- **by design**: snapshots only at certain regimes, per-parameter recorder rates, recording start/stop;
- **by validity logic**: SSM No Computed Data / Failure Warning, excluded probes;
- **by fault**: a sensor dropping to zero, harness opens;
- **in bursts**: sync loss, connector problems.

It should be generated with explicit mechanisms (MCAR/MAR/MNAR in the Rubin sense) rather than random masking.

### Cited Findings
- **Missing-data taxonomy** (MCAR/MAR/MNAR) — [Rubin 1976, Biometrika, doi:10.1093/biomet/63.3.581](https://doi.org/10.1093/biomet/63.3.581); [Little & Rubin 2019, doi:10.1002/9781119482260](https://doi.org/10.1002/9781119482260)
- **Informative missingness**: missing patterns "are often correlated with the target labels"; GRU-D exploits this — [Che et al., arXiv 1606.01865](https://arxiv.org/abs/1606.01865). BRITS imputes with bidirectional recurrent networks — [Cao et al., arXiv 1805.10572](https://arxiv.org/abs/1805.10572)
- **Burst-loss channel models** (two-state Markov / Gilbert–Elliott) — [Gilbert 1960, doi:10.1002/j.1538-7305.1960.tb03959.x](https://doi.org/10.1002/j.1538-7305.1960.tb03959.x); [Elliott 1963, doi:10.1002/j.1538-7305.1963.tb00955.x](https://doi.org/10.1002/j.1538-7305.1963.tb00955.x)
- **Validity-coded missingness** [TRANSFER: ARINC 429]: SSM codes 00 Failure Warning and 01 No Computed Data. The latter covers "a condition other than a system failure" that makes data unavailable — [AIM ARINC 429 tutorial, p.13](https://www.aim-online.com/wp-content/uploads/2019/07/aim-tutorial-oview429-190712-u.pdf)
- **Fault-driven missingness and structural change** [DIRECT: F404]: the NL prototype "dropped off to zero"; open T5 probes are excluded from the average — [NASA CR-191195](https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf)
- **Design-driven missingness** [TRANSFER/DIRECT statement on military EHM]: snapshot-only gas-path records, with military recordings possibly limited to ground idle and takeoff — [ProDiMES](https://ntrs.nasa.gov/api/citations/20080032563/downloads/20080032563.pdf)
- **Civil recorder rates** imply large between-sample gaps for slow parameters (fuel quantity 64 s) — [14 CFR 121 App M](https://www.law.cornell.edu/cfr/text/14/appendix-M_to_part_121)

### Inferences
- [ASSUMPTION; validate on real data] The virtual fighter's missingness model should combine several layers:
  - **Deterministic by design** (MAR given regime): recorder slot rates, EHM snapshot triggers, recording start/stop.
  - **Validity-driven** (MAR given flight condition): e.g. AoA flagged No Computed Data below a minimum airspeed; ADC data invalid on the ground.
  - **Fault-driven MNAR**: values vanish *because* the sensor is failing. This is correlated with the PHM label and is therefore informative.
  - **Gilbert–Elliott bursts** for transport/recorder dropouts (roughly MCAR with respect to aircraft state).
- [DERIVED] Imputation-based downstream pipelines (CSDI/BRITS) will learn the virtual fighter's missingness, so an unrealistic mechanism (e.g. uniform random masking) would teach the wrong prior.

### Gaps
- No public statistics on dropout rates, burst lengths or sync-loss frequency in military recorder data were found.

---

## Q7. "Ideal + iid Gaussian" vs realistic models: what matters for PHM realism and what a real-vs-synthetic classifier exploits

### Takeaway
The evidence shows that iid Gaussian residuals:
- make estimated uncertainty too optimistic by a factor of more than 3 on real fighter data;
- miss quantization-induced bias;
- miss regime-dependent variance;
- miss lags that only show up in transients;
- miss aging and drift that look like degradation;
- miss the discrete failure and validity semantics PHM must learn.

**For PHM realism the most important features are:**
- slow drifts, per-unit biases and aging;
- operating-point-dependent non-repeatability;
- transient sensor dynamics;
- redundancy and validity semantics;
- structured missingness.

**For classifier detectability the most exploitable features are likely:**
- the quantization lattice and hold patterns;
- spectral shape (structural modes, colour);
- inter-channel timing and coherence;
- marginal tails.

Most of these detectability claims are inferences and should be audited.

### Cited Findings
- **White-noise assumption understates uncertainty** [DIRECT: F-18 HARV]: conventional bounds were optimistic, with s/σ ratios above 3 — [Morelli & Klein 1995](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf)
- **Quantization biases estimates, not just variance** [TRANSFER: GTM/F-16 simulation] — [Grauer & Morelli 2013](https://ntrs.nasa.gov/api/citations/20140003885/downloads/20140003885.pdf)
- **Composite noise** [TRANSFER: inertial standards and datasheets]:
  - Gyro errors comprise white (ARW), flicker (bias instability), random-walk and ramp components — [MathWorks/IEEE 952 practice](https://fr.mathworks.com/help/nav/ug/inertial-sensor-noise-analysis-using-allan-variance.html)
  - MEMS bias and noise grow 2–4× over 10 years — [HG4930](https://prod-edam.honeywellaerospace.com/content/dam/honeywell-edam/aero/en-us/products/navigation-and-sensors/inertial-measurement-units/hg4930-mems-inertial-measurement-unit/documents/hon-aero-n61-3380-000-000-hguide-4930-mems-imu-datasheet-en.pdf)
- **Thermocouple drift can reach 1% in 10 h** for poor miniature probes [TRANSFER] — [TN D-7671](https://ntrs.nasa.gov/api/citations/19740014937/downloads/19740014937.pdf)
- **Thermal zero shift on the order of 1% FSO/100 °F** dominates pressure-transducer error [TRANSFER] — [Kulite TD-1012](https://kulite.com//assets/media/2021/12/Understanding-the-Pressure-Transducer-Datasheet-Total-Error-Band-vs.-Accuracy.pdf)
- **Benchmark simulators default to ideal sensors**, and even ProDiMES makes σ magnitude-dependent — [C-MAPSS guide §4.4](https://ntrs.nasa.gov/api/citations/20070034949/downloads/20070034949.pdf); [ProDiMES](https://ntrs.nasa.gov/api/citations/20080032563/downloads/20080032563.pdf)
- **Detectability metrics**: the discriminative score uses an LSTM classifier; TSGBench adds marginal-distribution, autocorrelation, skewness and kurtosis differences and contextual-FID — [TimeGAN](https://proceedings.neurips.cc/paper/2019/file/c9efe5f26cd17ba6216bbe2a7d26d490-Paper.pdf); [TSGBench](https://arxiv.org/abs/2309.03755)

### Inferences
- **[ASSUMPTION] Ranking for PHM realism.** Each item is followed by how to check it.
  1. Per-tail/per-unit bias and scale factor, plus slow drift and aging. These mimic or mask degradation trends. *Validate:* ensure PHM false-alarm rates on healthy synthetic fleets respond to drift magnitude.
  2. Operating-point-dependent non-repeatability of snapshot gas-path parameters. *Validate:* compare to EHM scatter when available.
  3. Sensor dynamics during transients (T5 τ(W), pressure-line lag). These create transient residuals that fault detectors see.
  4. Redundancy-management and validity semantics, including fault-to-control coupling (e.g. a T5 short raising fuel flow).
  5. Structured, informative missingness.
  6. Quantization at the recorder resolution, which matters for detecting small shifts (e.g. 0.004 g, 0.3% FS).
- **[ASSUMPTION] Ranking for real-vs-synthetic detectability.** *Validate* by training classifiers on real-vs-synthetic data with feature attribution, and by ablation (remove one texture element at a time and watch the discriminative score).
  1. Value lattice / LSB structure and repeated (held) samples. These are trivially detectable through first-difference histograms.
  2. Spectral and ACF shape, including structural-mode lines and coloured noise.
  3. Inter-channel time skews and coherence.
  4. Heteroscedasticity by regime.
  5. Tails and outliers (kurtosis).
  6. Discrete semantics, such as WOW polarity and SSM codes.
  7. Start/stop and gap patterns.

### Gaps
- No published study was found that ranks which texture features a classifier exploits on aircraft data. This needs an in-house audit, a cross-link to the Validation researcher.

---

## Synthesis

### (a) Key findings summary
1. **Every sensor class has structured, documented non-idealities larger than white noise.** Examples:
   - thermocouple calibration tolerance ±5–7.5 °C at 1000 °C;
   - EGT probe τ varying 3:1 with mass flow (τ ∝ W^−0.5) and two-time-constant responses;
   - de-icing heater error of +0.12–0.5 °C;
   - piezoresistive thermal zero shift of about 1% FSO/100 °F;
   - inertial composite noise with 2–4× aging growth;
   - oil-debris monitors that output size-binned counts with 85–350 µm ferrous thresholds.

   (AGARD-AG-160 v2/v11, NACA TN 3766, Kulite, Honeywell, Gastops.)
2. **F404 evidence gives concrete fighter-engine sensor semantics** [DIRECT]:
   - an 8-probe T5 average with open-probe exclusion, where a short reads low and raises fuel flow;
   - dual eddy-current NL blade-count sensors and an alternator-based NH;
   - LVDTs on FVG/VEN;
   - RTD T1 with hot-air de-icing;
   - and the observed artefact catalogue: offsets, scale error, transient lag mismatch, jitter, dropout, clipping, vibration-dependent noise.

   (NASA CR-191195.)
3. **Real fighter flight-test residuals are coloured and channel-specific.** Structural modes appear in α/a_z but not q. Treating them as white makes uncertainty more than 3× optimistic [DIRECT: F-18 HARV].
4. **The signal chain and recorder add deterministic texture.** Examples:
   - quantization, which biases estimates;
   - ARINC 429 BNR/SSM, 1553 16-bit and ARINC 717 12-bit framing;
   - sensor-internal deadband and averaging;
   - asynchronous rates (tens of Hz in FADECs up to kHz in gyros);
   - recorder time correlation of only about 1 s;
   - military EHM snapshots limited to ground idle and takeoff.
5. **Truth-free estimation is feasible** using:
   - Allan/GMWM fits on steady or static segments;
   - Grubbs and triple collocation on redundant sensors;
   - data compatibility for biases, scale factors and time skews;
   - Mehra/ALS/EM and the filter-error method for covariances.
6. **Gas-path benchmarks (C-MAPSS/ProDiMES) use idealized sensors** with iid Gaussian σ of about 0.25–0.75% of reading. They provide magnitude anchors but are not empirical texture.
7. **Publicly available fighter raw-sensor residual statistics are essentially absent.** The design must therefore be prior-driven now and data-refinable later.

### (b) Per-sensor-class texture parameter table

The table is split in two to keep it readable: part 1 gives errors and dynamics, part 2 gives sensitivities, artefacts and evidence.

**Part 1: errors and dynamics**

| Sensor class (fighter use) | Static accuracy / bias | Noise / resolution | Drift / aging | Dynamics / latency |
|---|---|---|---|---|
| EGT/T5 TC harness, Type K (F404: 2×4 probes averaged) | Calibration 0.5–0.75% of reading (±5–7.5 °C @1000 °C); IEC class 1 ±0.004·T, class 2 ±0.0075·T; system check ±4 °C | Lit. σ: T48 0.75% (C-MAPSS); 10.2/7.55 °R TO/cruise (ProDiMES); optical T5 code 0.44 °F/count | Up to ~1%/10 h (poor miniature TCs); cumulative down-scale drift (Type K) | τ ∝ W^−0.5, 3:1 over envelope; τ*≈0.4–0.8 s ref; 2-exponential (0.8/0.2); shielded 0.3–1.4 s (63%) |
| T1/CIT/TAT (RTD, F404 T1) | RTD F0.3/F0.15 classes; T1 optical vs electrical ≤5 °C | — | Not found | Ground (no flow) τ ≥15 min; electronic FADEC needs short τ |
| Pressure, piezoresistive/SOI | Static error band ±0.1% FSO; hysteresis <0.1% (often 0.03%) | ~5 µV rms (~1e-4 psi @2 psi FS) | Low (USAF max cal. interval); PPT 0.025% FS/yr | Line lag τ=128µLV/(πd⁴p) (∝1/p); PPT 17 ms min delay |
| Pressure, vibrating cylinder / capacitive | Vib-cyl precision ~0.01% class; humidity residual ~0.03% | Frequency output, non-linear p–f | Not found | Not found |
| Air data (pitot-static, AoA vane/probe) | Static ±0.01 q_c to M2.5; in-service position error ±0.004 q_c; vane <0.3° | AoA resolution needed 0.1° for 2% model error; FDR AoA 0.3% FS | Pitot-static "accuracy with service time" studied (in-service avg ≈1/3 of limits) | Pneumatic lag (above); vane dynamics: gap |
| Shaft speed (F404 NL eddy-current blade count; NH alternator) | Lit. σ 0.25% (C-MAPSS); Nc 15.1 rpm (ProDiMES TO) | Frequency-count quantization; NL 2.8–10.7 kHz, NH 0.2–4.4 kHz | Not found | Fan-speed sensor example BW 50 rad/s (C-MAPSS) |
| Fuel flow (turbine meter) | Lit. σ Wf 0.058 pps TO (ProDiMES); 9.03 pph (C-MAPSS40k) | Gap | Gap | Gap |
| LVDT/RVDT/pot (F404 FVG, VEN) | Two-sensor offsets: FVG ~0.1 in/2.7 in; CVG ~10° | FDR 0.2–0.5% FS; pot resolution 0.04° for 2% | Not found | Excitation 1–10 kHz |
| Accelerometer, servo quartz (QA-2000) | Bias <4 mg; 1-yr repeatability 160–550 µg; SF 310–600 ppm | <7 µg rms (0–10 Hz), <70 µg rms (10–500 Hz) | Tempco <30 µg/°C, <180 ppm/°C | BW >300 Hz |
| Accelerometer, MEMS (HG4930) | Bias repeatability 1.7–3 mg (→5–10 mg EOL) | VRW 0.03–0.06 m/s/√h (→0.09–0.12) | 2–4× growth over 10 yr | BW 70/180 Hz; 600/100 Hz output |
| Gyro, RLG nav (GG1320, HG9900) | Bias 0.002–0.0035 °/h | ARW 0.002–0.0035 °/√h; ~1.11″ pulse quantum | Not stated | 2 kHz, 168 µs latency (GG1320); 300 Hz (HG9900) |
| Gyro, RLG tactical (HG1700) | 1–5 °/h | ARW 0.125–0.5 °/√h | Not stated | 100/600 Hz |
| Gyro, MEMS (HG4930) | In-run 0.25–0.45 °/h; repeatability 7–20 °/h | ARW 0.04–0.06 °/√h | → 1–2 °/h, 20–60 °/h, 0.09–0.175 °/√h EOL | 600/100 Hz |
| Oil debris monitor (MetalSCAN on F-35, Typhoon, F-22) | Min detectable Fe 126–350 µm, NFe 388–716 µm (sphere, by bore) | Counts in configurable size bins (Fe/NFe) | — | Real-time; FADEC (F135) or EMU (EJ200) processing |
| Strain gauge, foil | GF 1–3; transverse sensitivity 3% | Noisy below ~4000 µε | Creep/hysteresis from backing | — |
| Fuel quantity (capacitance), oil P/T, proximity, current/voltage | Gap (FDR fuel qty ±5%, 1% FS res, 64 s) | Gap | Gap | AGARD: oil well-probe τ ~2× water, ~30× air |

**Part 2: environmental sensitivities, artefacts, evidence**

| Sensor class | Environmental sensitivities | Failure / artefact modes | Tag | Key sources |
|---|---|---|---|---|
| EGT/T5 TC harness | Radiation error (asymmetric up/down response); circumferential profile | Open probe excluded from average; short reads low and raises fuel flow; harness wiring faults | DIRECT (F404) + TRANSFER | CR-191195; AGARD-AG-160 v2; NACA TN 3766; TN D-7671; Wikipedia TC |
| T1/CIT/TAT | De-icing heater error +0.2–0.5 °C @M0.3, +0.12–0.3 °C @M0.8 (×2 dual element); attitude error beyond ±10°/±20° | Dip with airflow (dynamic recovery); self-heating on ground | DIRECT (F404 T1) + TRANSFER | CR-191195; AGARD-AG-160 v2 |
| Pressure, piezoresistive/SOI | Thermal zero shift ~±1% FSO/100 °F; span shift ±1% RDG/100 °F; transients invalidate compensation; accel ≥0.00003% FS/g | Deadband/hold (PPT); thermal-gradient errors; clipping at range | TRANSFER | Kulite TD-1012, Hdbk §3; Honeywell PPT; AGARD v11 |
| Pressure, vibrating cylinder / capacitive | Vib-cyl insensitive to vibration; capacitive temperature effects hard to compensate | — | TRANSFER | AGARD v11 §4.5.3, §4.6.2 |
| Air data (pitot-static, AoA) | Upwash, pitch-rate and boom-bending corrections; cylindrical probes vibration-sensitive | Blocked pitot/static signatures | DIRECT (HARV upwash/CG correction) + TRANSFER | AGARD v11; Morelli & Klein 1995; CFR App M; Grauer 2013 |
| Shaft speed | VR amplitude ∝ speed (low-speed limit) | Resolution-induced jitter jumps; dropout to zero (prototype NL) | DIRECT (F404) + TRANSFER | CR-191195; ProDiMES; Simon & Garg 2010 |
| Fuel flow | Gap | Gap | Literature assumption only | ProDiMES; Simon & Rinehart 2016 |
| LVDT/RVDT/pot | Hydraulic-fluid cooling (VEN) | Scale error; null/quadrature; sum-of-secondaries monitor | DIRECT (F404) + TRANSFER | CR-191195; Wikipedia LVDT; CFR; Grauer 2013 |
| Accelerometer, servo quartz | VRE 20–150 µg/g²rms; misalignment <2000 µrad | Structural-mode content in a_z residuals (HARV) | TRANSFER + DIRECT (HARV) | QA-2000 brochure; Morelli & Klein 1995 |
| Accelerometer, MEMS | VRE 2–5 mg (→15–25 mg EOL) | Turn-on bias jumps | TRANSFER | HG4930 datasheet |
| Gyro, RLG nav | Magnetic 0.002 °/h/gauss | — | TRANSFER | Honeywell pages |
| Gyro, RLG tactical | — | — | TRANSFER | HG1700 brochure |
| Gyro, MEMS | VRE 5–10 °/h (→30–40 EOL) | Turn-on bias jumps | TRANSFER | HG4930 datasheet |
| Oil debris monitor | Flow/bore dependent | Sparse point process; limit exceedances; (vendor claim) electric chip detectors alarm late | DIRECT (platform fit) + TRANSFER (thresholds) | Gastops MS1000 overview; F-35/Typhoon guides |
| Strain gauge, foil | TCR ~1%/100 °F; TCGF −3%/100 °F | Fatigue life 10⁴–10⁷ cycles | TRANSFER (vendor) | Kulite strain-gauge note |
| Fuel quantity, oil P/T, proximity, current/voltage | Gap | Gap | Gap | CFR App M; AGARD v2 |

### (c) Recommended residual-modelling approach and how to fit it

**Recommendation.** Build a layered, physically structured "measurement operator" y = H_chain(H_sensor(x_true, env), θ_unit, θ_age) + ε_regime. Add a learned residual layer only when real data allow it. The layers:

1. **Sensor physics, deterministic**
   - Flow-dependent dynamics: T5 τ(W) ∝ W^−0.5 with a 0.8/0.2 two-exponential response; pneumatic lag ∝ 1/p.
   - Static non-linearity and hysteresis.
   - Environmental terms: thermal zero/span shift driven by a bay-temperature state; VRE driven by vibration PSD; DHE driven by flow; attitude error beyond about ±10°.
   - Installation and kinematic terms: upwash, CG lever arms, boom bending.

   *Evidence:* AGARD, NACA, Kulite, Honeywell. *Justification:* these terms are causally tied to the virtual aircraft state, so they stay consistent with ground truth and with fault injection.
2. **Per-unit and per-tail parameters, drawn at "installation"**
   - Bias and scale factor from datasheet tolerances (e.g. thermocouple ±0.5–0.75% of reading; QA-2000 1-yr repeatability).
   - Misalignment.
   - Per-probe offsets around the T5 ring.
3. **Aging and drift**
   - Random-walk/ramp drift with rate priors (thermocouple drift up to 1%/10 h as a bad-unit tail; MEMS 2–4× growth over life).
   - Calibration and maintenance events reset some parameters. Cross-link to the maintenance-records researcher.
4. **Composite stochastic noise**
   - White (ARW/VRW).
   - Flicker/bias-instability, approximated by a sum of Gauss–Markov terms or Kasdin 1/f filtering.
   - Random walk.
   - Narrow-band structural-mode components for a_z, α and β.
   - Variance conditioned on regime covariates (N2/vibration level, turbulence σ_w(2–7 Hz), g, flight phase) via a GARCH-like or regime-switching scale.
5. **Conditioning, ADC and processing**
   - Anti-alias filtering, sample/hold, ADC quantization, saturation/clipping, deadband.
   - Sensor-internal averaging.
   - Redundancy management (average-with-exclusion, mid-value select, monitor thresholds).
   - Validity/SSM flags.
6. **Bus and recorder**
   - Per-parameter rates with clock jitter; asynchronous sample-and-hold.
   - ARINC 429 BNR LSB / 1553 scaling; ARINC 717-style 12-bit recorder words and slotting.
   - Recording start/stop logic; EHM snapshot averaging windows.
7. **Missingness**
   - By design, validity-driven, fault-driven (MNAR), and Gilbert–Elliott bursts.
8. **Optional learned residual layer** (later)
   - A conditional diffusion model (Diffusion-TS/CSDI style) or a copula/flow model.
   - Trained only on residuals r = y_real − H(x̂) from real data, conditioned on regime.
   - Preserves physics and ground-truth labels.

**Why this design, compared with the alternatives:**
- **Pure "ideal + iid Gaussian"**: refuted by the evidence (Q7).
- **Pure deep-generative modelling of whole signals**:
  - needs large real fighter datasets that are not publicly available;
  - cannot guarantee physical or causal consistency or fault-to-label alignment;
  - its validation on aircraft residuals is undocumented.
- **Parametric layers** have interpretable parameters that can be:
  - seeded from datasheets now;
  - stress-tested (ablation for PHM and for detectability);
  - refit when real data arrive.

**How to fit from data when the truth is unknown**, in order of availability:
1. **Datasheet and standard priors** (tables above) set initial distributions for per-unit parameters.
2. **Static or ground segments** (engine-off IMU, steady ground idle, hangar):
   - Allan variance or GMWM fits for N, B, K and quantization;
   - check sensor-internal deadband and hold by first-difference and run-length histograms.
3. **Redundant sensors** (8 T5 probes, dual NL, dual-channel FADEC inputs, left/right air data, INS vs ADC):
   - Grubbs / three-cornered hat / triple collocation for individual error variances;
   - pairwise differences for per-unit bias spread.
4. **Kinematic data compatibility** (flight-path reconstruction with an EKF/RTS smoother):
   - estimate biases, scale factors and time skews for accelerometers, gyros, air data and attitude.
5. **Model-based residuals**:
   - run the physics model and an RTS smoother;
   - estimate Q/R via Mehra, ALS or EM;
   - test residual whiteness; model the coloured remainder with ARMA, Gauss–Markov or narrow-band terms;
   - use the filter-error method in turbulence.
6. **Steady-state snapshots** (EHM): σ(operating point) regression for non-repeatability; heavy-tail check (kurtosis, Student-t fit); outlier rate.
7. **Recorder forensics** on any real file: sample-interval histograms, repeat runs, LSB lattice, frame counters and gaps, start/stop timing.
8. **Validation**:
   - TSTR and discriminative score (LSTM classifier);
   - TSGBench feature metrics (marginal distribution, ACF, skewness, kurtosis);
   - PSD and Allan-deviation overlays;
   - feature-attribution audit of what the classifier uses;
   - iterate on the top-ranked artefacts.

### (d) Open questions / gaps
1. Fighter-specific air-data numbers: AoA vane/probe dynamics (natural frequency, damping), position-error curves vs Mach/AoA for F-16/F/A-18/Tejas, pneumatic lag of production installations. Leads: NASA TM-104316, Grauer TM-2017-219795, Whitmore TMs.
2. Capacitance fuel-quantity gauging: accuracy, attitude/acceleration and slosh effects, densitometer compensation. Also turbine fuel-flowmeter accuracy, response and Reynolds-number effects.
3. FADEC (F404-GE-IN20, F110, RM12) data: sample rates, filters, signal-selection and validation thresholds, EHM snapshot triggers and window lengths.
4. Empirical military EHM snapshot scatter (EGT/N/Wf), heavy-tail statistics and outlier rates. Need real data or OEM papers (Volponi 2014; Doel TEMPER — not accessed).
5. Real recorder artefact statistics for fighters: sync loss, bit errors, gap frequency.
6. Proximity probes, oil P/T, chip-detector false-indication rates, Hall-effect current sensors: no numbers found.
7. Whether deep generative residual models measurably beat parametric models on aircraft data in discriminative/TSTR tests. This is untested in the literature found.
8. The quantitative ranking of classifier-exploited texture features on aircraft data needs an in-house ablation study.
9. Search budget exhaustion limited discovery. A follow-up session should run targeted searches for items 1–3 and for DASHlink-based residual studies.

### (e) Ranked list of most valuable sources (for this layer)
1. **NASA CR-191195 (FOCSI, GE 1994)**: DIRECT F404-400 sensor suite, harness averaging and failure semantics, and two-sensor artefact catalogue. https://ntrs.nasa.gov/api/citations/19940032893/downloads/19940032893.pdf
2. **AGARD-AG-160 Vol.2, In-Flight Temperature Measurements (1973)**: error taxonomy, DHE, attitude error, τ ∝ W^−0.5, two-time-constant probes, thermocouple calibration tolerance. http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf
3. **AGARD-AG-160 Vol.11, Pressure and Flow Measurement**: pneumatic lag, position error, AoA corrections, transducer types. http://spaceagecontrol.com/AD-PressureAndFlowMeasurement.pdf
4. **Morelli & Klein 1995 (F-18 HARV)**: empirical coloured residuals and structural modes; consequences of the white-noise assumption. https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf
5. **Morelli & Grauer 2023**: survey of data compatibility, filter-error, coloured-residual and time-skew methods with references. https://ntrs.nasa.gov/api/citations/20230001945/downloads/MorelliGrauerAdvancesAircraftSIDJOA_2023.pdf
6. **ProDiMES (NASA TM-2008-215271)**: snapshot practice, military snapshot limits, σ table. https://ntrs.nasa.gov/api/citations/20080032563/downloads/20080032563.pdf
7. **NACA TN 3766**: thermocouple τ correlation and measured τ*. https://ntrs.nasa.gov/api/citations/19930084456/downloads/19930084456.pdf
8. **Honeywell HG4930 datasheet**: quantified fresh-vs-end-of-life inertial error growth. (URL above)
9. **Kulite TD-1012 and Handbook §3**: pressure transducer error-budget anatomy. (URLs above)
10. **Grauer & Morelli NASA TM-2013-218056**: quantization-resolution effects with numbers. https://ntrs.nasa.gov/api/citations/20140003885/downloads/20140003885.pdf
11. **Gastops MetalSCAN MS1000 overview plus F-35/Typhoon guides**: DIRECT oil-debris monitor fit and thresholds. (URLs above)
12. **QA-2000 brochure and GG1320/HG9900/HG1700 pages**: inertial texture numbers. (URLs above)
13. **14 CFR 121 App. M**: recorder rates, resolutions, 1 s time correlation. https://www.law.cornell.edu/cfr/text/14/appendix-M_to_part_121
14. **Methods references**: GMWM, ALS, Mehra, Grubbs, triple collocation; and for ML, TimeGAN, TSGBench, Diffusion-TS, CSDI, GRU-D. (DOIs/arXiv above)
15. **NASA TN D-7671**: thermocouple drift magnitudes in turbine conditions. https://ntrs.nasa.gov/api/citations/19740014937/downloads/19740014937.pdf
