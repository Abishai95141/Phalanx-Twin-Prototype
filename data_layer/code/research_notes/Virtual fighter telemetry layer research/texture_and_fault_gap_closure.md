# Texture and fault gap closure for a Tejas-class virtual fighter (HAL Tejas Mk1A, GE F404-GE-IN20): sensor/measurement texture, signal validation and BIT, and fault/degradation signatures (Project Phalanx)

**What this note does.** It closes the specific gaps recorded at the end of `sensor_residual_texture.md`, `faults_and_degradation.md`, `empirical_dashlink_texture.md`, `f404_in20_engine_model.md`, `addendum_engine_F404_F414_monitoring.md` (the correction banner is respected: Henry T1 = 266 K, T5 = 834.3/871.0 K, ECU T5 trim ±150 °F), `tejas_utility_systems.md`, `tejas_avionics_and_parameter_inventory.md` and `not_measured_states.csv`. It does not repeat settled findings. Where a number was already in those notes it is cited as "already known" and only extended.

**Evidence tags.**
- **[DIRECT]**: about the Tejas or the F404-GE-IN20 itself.
- **[TRANSFER: platform/domain]**: from another platform; the tag says why it transfers and its limits.
- **[MEASURED]**: Phalanx's own DASHlink measurements.
- **[ASSUMPTION]**: a modelling choice, with how to validate it.
- **[DERIVED]**: arithmetic on cited numbers.

Graph-read values are marked "graph-read" and should be treated as about ±10 %.

**Method and provenance.**
- **Who did what.** Six topic helpers worked under the same source rules: air data; fuel and thin sensor classes; engine fault signatures; mechanical degradation; utility degradation; and BIT/sim-vs-real. Signal validation was done directly from the NASA DEEC/ADIA corpus.
- **Where the PDFs are.** All downloaded PDFs are under `/Users/abishaikc/Phalanx/research_sources/texture_fault_gaps/`, in the sub-folders `air_data/`, `fuel_sensors/`, `engine_faults/`, `mech_degradation/`, `utility_degradation/`, `bit_simreal/` and `signal_validation/`. Already-local copies in `research_sources/engine_data/f100/` were reused: NASA CP-2298 Papers 3, 6, 7, 8, 9, 11, 12 and NASA TM-86735.
- **Distribution checks.** DTIC scans were taken from archive.org and their "Approved for public release" cover was checked. The following were deliberately not used:
  - USAAVSCOM TR-84-D-7 / DTIC ADB083462: its pages still carry the original limited-distribution marking.
  - Douglas LB-31228 / DTIC AD0402711 (1963): it carries an ASTIA "qualified requesters" notice.
  - A Collins "proprietary" TAT slide deck.
  - Anything in `_restricted_do_not_cite/`.
- **Access notes.**
  - The afjag.af.mil AIB PDFs block scripted download. They were read in a browser and are cited by URL and page.
  - DOT&E PDFs were retrieved through the Wayback Machine because dote.osd.mil returns 403.
  - journal.accsindia.org (an ADE/ADA paper on LCA flight-control software timing) and drdo.gov.in pages were unreachable.

---

## Q1. Air-data texture: vane dynamics, upwash/sidewash and boom bending, position error with the transonic jump, pneumatic lag vs altitude, TAT recovery and heater error, ADC filtering and update rates, and Tejas-specific evidence

### Takeaway
Fighter air data has strong structured texture, and all of it is now numerically bounded from released sources.
- **Vanes** are lightly damped second-order systems whose natural frequency scales with equivalent airspeed:
  - boom vanes run about 20 Hz at 90 m/s EAS and 40 Hz at 190 m/s EAS;
  - damping ratio ζ is about 0.04–0.10 and falls with altitude.
- **Upwash, bending and misalignment:** noseboom upwash is 6–10 % of α plus a 0.4–0.7° bias; boom bending is about 0.06–0.1° per g; misalignment steps by 0.1–0.3° after radome or boom maintenance.
- **Static-source position error:**
  - noseboom installations: Δp/q_c is about +0.03–0.07 subsonic, jumps to 0.08–0.16 just below M 1, then collapses to about 0.01 once the bow shock passes the ports;
  - side or nose vents can have the opposite sign and show "fluctuating pressures" over M 0.97–1.0;
  - an Indian HAL ADC's correction implies Δp/q_c ≈ −0.09.
- **Pneumatic lag** scales as (μ/μ_SL)/δ, giving ×2.8 at 30 kft and ×4.3 at 40 kft. Flight lags are up to 3–4× ground or theory values.
- **TAT probes:** recovery factor 0.977–0.994 (M 0.5–1.6) with ±0.015 unit spread; the de-icing heater error is ≥0.2 °C and rises to about 1.3 °C at low M·ρ.
- **Update rates:** ADC outputs are 8–20 Hz; FCS sampling is 50–64 Hz behind 20–32 Hz anti-alias filters; inertial-to-air-data skews are 30–110 ms. Two ADC designs fed identical pressures differed by about 2 s in altitude-rate lag.

Tejas-direct evidence: the sensor layout (2 side probes, 1 nose probe, 2 AoA vanes); the voting-out of faulty sensors; TAT correction tables for de-icing-heater and self-heating error that depend on the heater flag; an air-data error that depended on undercarriage position; and a 1.4–1.6 local/free-stream α slope at the side probe. No Tejas vane dynamics, SSEC curve or lag values are public.

### Cited Findings

**Vane dynamics**
- **Low-inertia NASA gust vane.** [TRANSFER: research gust vane, low-inertia balsa, mass-balanced; physics transfers, not a production unit] — [NASA TN D-6193, PDF p.3 and pp.9–10](https://ntrs.nasa.gov/api/citations/19710013639/downloads/19710013639.pdf)
  - Behaves as a second-order system with f_n ≈ 0.45·√q Hz (q in N/m²): f_n = 22 Hz at q = 2,394 Pa and 40 Hz at M 1.6.
  - ζ = 0.65–0.80 at sea level, 0.50–0.65 at √σ = 0.68, 0.25–0.50 at √σ = 0.27; it falls roughly as √(density). Friction contributes ζ ≈ 0.05.
  - In the supersonic tunnel there was transient noise of 0.05° half-amplitude at about 110 Hz.
- **NACA noseboom flight-test vane.** [TRANSFER: research noseboom, not a fuselage production vane] — [NASA TN D-8242, Fig. 22, PDF p.30, graph-read](https://ntrs.nasa.gov/api/citations/19760016169/downloads/19760016169.pdf)
  - f_n ≈ 20 Hz at 90 m/s EAS and ≈ 40 Hz at 190 m/s EAS (≈ 0.21 Hz per m/s EAS).
  - ζ ≈ 0.10 at sea level, 0.077 at 6.4 km, 0.043 at 18.5 km.
  - A heavier vane carrying accelerometers had roughly half both values: f_n 8–12 Hz at 75–115 m/s; ζ 0.045 at 5 km to 0.012 at 18 km.
  - Vane float ≈ ±0.05° (to −0.15° at M 0.4) (Fig. 8a, PDF p.15).
  - Hinge moment is linear only within about ±2° ([TN D-6193, PDF p.7](https://ntrs.nasa.gov/api/citations/19710013639/downloads/19710013639.pdf)).
- **Correction model and filtering.** [TRANSFER: general flight-test practice] — [AGARD-AG-300 Vol.1 (Lawford & Nippress), §12.3.3.4, PDF p.55; cover Distribution A](https://archive.org/download/DTIC_ADA137367/DTIC_ADA137367.pdf)
  - The vane is corrected as k·ω_n²/(s² + 2ζω_n·s + ω_n²).
  - On-board filtering adds unacceptable phase lag, so zero-phase filtering is preferred for analysis.
- **Production vane dampers.** [TRANSFER: Rosemount patents, qualitative] — [US 6,612,166 B2](https://patents.google.com/patent/US6612166B2/en); [US 11,022,194 B2](https://patents.google.com/patent/US11022194B2/en)
  - Production vanes use viscous dampers. Damping tuned for high speed over-damps the vane at low speed.
  - Damper fluid viscosity varies with temperature, and damper tolerances add unit-to-unit spread. No numbers are given.
- **Vane failure textures.** [TRANSFER]
  - NACA vane "buzzing" near M 1.0 (once near M 2.0) was traced to failed ball/pivot bearings — [NACA RM L9F28a, PDF p.2](https://ntrs.nasa.gov/api/citations/20050080746/downloads/20050080746.pdf).
  - F-104 flow-angle potentiometers "changed calibrations as they wore" — [NASA TM-101714, PDF p.9](https://ntrs.nasa.gov/api/citations/19900004912/downloads/19900004912.pdf).

**Upwash, sidewash, boom bending, misalignment**
- **F-104 noseboom vanes.** [TRANSFER: noseboom installation; different forebody and boom length from Tejas] — [NASA TM-101714 (Haering; this is an F-104 report, not F-15 as some indexes say), Figs. 15–18, PDF pp.23–24, graph-read](https://ntrs.nasa.gov/api/citations/19900004912/downloads/19900004912.pdf)
  - Upwash factor ∂Δα/∂α_c is 0.062 at M_i 0.76 and about 0.10 at M_i 0.89.
  - AoA bias falls from about 0.73° (M_i 0.76) to 0.38° (M_i 0.89). Sidewash factor is 0.105–0.115.
  - Supersonic Δα ≈ 1.4° for M_i 1.0–1.2, dropping sharply near M_i 1.2 when the local shock crosses the vane, to about 0.25°. Flight-to-flight scatter is ±0.3°.
  - Residuals after calibration: α ±0.2° subsonic / ±0.3° supersonic.
- **Noseboom wind tunnel.** [TRANSFER] Δα/α ≈ 0.07–0.09 for M 0.4–1.4, tending to ~0 by M 2.5. Shock–vane interaction is not predicted — [TN D-8242, Fig. 8b, PDF p.15](https://ntrs.nasa.gov/api/citations/19760016169/downloads/19760016169.pdf).
- **F-14 nose hemispherical head.** [TRANSFER] — [NASA TM-86790, Tables 3–4, PDF p.16](https://ntrs.nasa.gov/api/citations/19870014183/downloads/19870014183.pdf)
  - Upwash factor 0.142 at 49° wing sweep and 0.330 at 22°, so wing sweep and configuration change the correction.
  - Pressure scale factor 1.08–1.15; bias 0.24–0.30 kPa.
- **Boom bending.** [TRANSFER]
  - F-104 noseboom pitch deflection measured at −0.064°/g — [TM-101714, PDF p.7](https://ntrs.nasa.gov/api/citations/19900004912/downloads/19900004912.pdf).
  - AGARD gives 0.1°/g as representative for a long vane boom, linear in n_z — [AGARD-AG-300 §12.3.3.3, PDF p.54](https://archive.org/download/DTIC_ADA137367/DTIC_ADA137367.pdf).
- **Maintenance-induced misalignment steps.** [TRANSFER] After radome removal and refit, F-104 noseboom offsets moved by 0.08° roll, 0.17° pitch and 0.26° yaw — [TM-101714, Table 1, PDF p.11](https://ntrs.nasa.gov/api/citations/19900004912/downloads/19900004912.pdf).
- **Sideslip-induced static error on a boom.** [TRANSFER] ΔCp = −2·tan²β/(1 + tan²β + tan²α), about −0.015·q at β = 5° — [NASA TM-102846, PDF p.5](https://ntrs.nasa.gov/api/citations/19900018386/downloads/19900018386.pdf).
- **AFTI/F-16 side-probe blanking.** [TRANSFER: fighter, FBW] At high sideslip in a yaw departure the side-mounted probe was blanked by the fuselage. Signal selection passed the error through until the failure threshold was reached. The result was a transient air-data failure and gain mistracking between channels — [NASA TP-2857, pp.41–42, PDF p.45](https://ntrs.nasa.gov/citations/19890014956).
- **F-18 HARV.** [TRANSFER] The production fuselage AoA probe "stopped functioning at 33°". Wingtip-boom sidewash was Δβ ≈ ±0.93° + 0.038α + 0.0045α² (σ 0.2°), and wing bending/torsion modes appeared as noise in the flow angles — [NASA TM-101729, PDF pp.11, ~16](https://ntrs.nasa.gov/api/citations/19910004140/downloads/19910004140.pdf).

**Static-source position error and the transonic jump**
- **F-104 noseboom ΔM = M − M_i.** [TRANSFER] — [TM-101714, Fig. 14, PDF p.23, graph-read](https://ntrs.nasa.gov/api/citations/19900004912/downloads/19900004912.pdf)
  - About 0.01 at M_i 0.6 and about 0.023 at 0.95, peaking at about 0.055 just below M_i 1.0.
  - It then collapses to about 0.007 at M_i 1.0, sits at 0.009–0.012 up to M 1.6, and reaches about 0 by M_i 1.95.
  - Scatter ±0.003 subsonic, ±0.005 supersonic. A radar-derived altitude bias reached −264 ft at 34 kft.
- **Transonic ambiguity.** [TRANSFER] M − M_i rises to about 0.06 and then drops to about 0 near M 1. Where d(M − M_i)/dM > 1, M_i decreases while M increases, so one indicated value maps to two true Mach numbers over a band about 0.02 M wide — [AGARD-AG-300 §7.2, Fig. 10, PDF p.40](https://archive.org/download/DTIC_ADA137367/DTIC_ADA137367.pdf).
- **Gracey, NASA RP-1046.** [TRANSFER] — [p.75–106](https://ntrs.nasa.gov/api/citations/19800015804/downloads/19800015804.pdf)
  - Fuselage-nose installations on five aircraft: Δp/q_c 0.025–0.065 at M 0.8 and 0.04–0.16 at M → 1.0, smaller for longer booms (Fig. 7.7, p.91).
  - Nose-inlet aircraft: 0.022–0.058 at M 0.8 and 0.045–0.10 at M 1.0 (Fig. 7.10, p.94).
  - Vents just aft of a jet fighter's nose: −0.035 to −0.045 at M 0.92–0.97, with a "fluctuating pressures" band of about −0.02 to −0.05 over M 0.97–1.0. The discontinuity happens below M 1.0, as local shocks pass the vents (Fig. 7.19, p.102; text p.79).
  - 1 % q_c of static error at M 2.0 and 40,000 ft equals 965 ft of altitude. The military tolerance is 25 ft per 100 KIAS (p.81).
- **Tejas side-probe position (design).** [DIRECT: ADA authors, "typical combat aircraft" front fuselage with pitot-static probes, refuelling probe and AoA vane] — [Krishna & Singh, DSJ 52(1):65–71 (2002), Figs. 2, 5–7, pp.66–69; local `research_sources/tejas_airframe/DSJ_2150.txt`](https://www.publicationsdrdo.in/index.php/dsj/article/view/2150)
  - Probe locations were chosen with CFD where the zero-Cp contours cluster; Cp at the chosen location stays within ±0.1 over the free-flight Mach range.
  - The residual position-error coefficient must stay inside the MIL-P-26292C tolerance envelope (curves A–B) and is corrected in the ADC.
  - The air-to-air refuelling probe's bow shock impinges on the fuselage at M 1.2, just behind the pitot-probe locations.
- **HAL ADC static-source error correction (SSEC).** [TRANSFER: HAL ARDC ADC on an unnamed Indian military aircraft] — [Meharu & Kuttieri, JOAST 67(2A):277–284 (2015), Table 1, p.279](https://joast.org/index.php/joast/article/download/331/310)
  - Uncorrected minus corrected altitude: +164 ft (M 0.30, 12 kft), +1,019 ft (M 0.75, 12 kft), +881 ft (M 0.75, 30 kft), +733.5 ft (M 0.612, sea level).
  - Uncorrected Mach reads 0.016–0.042 high.
  - [DERIVED, ISA] This implies Δp/q_c ≈ −0.087 to −0.100: the static source reads low, the opposite sign to noseboom installations.

**Pneumatic lag vs altitude**
- **Scaling.** [TRANSFER] λ/λ_SL = (μ/μ_SL)/δ. Ground-test lag can be up to 3× smaller than in flight — [AGARD-AG-300 pp.23–25, Fig. 6, PDF pp.31–33](https://archive.org/download/DTIC_ADA137367/DTIC_ADA137367.pdf). [DERIVED, ISA] λ/λ_SL = 1.38 / 1.94 / 2.80 / 4.29 / 6.94 at 10 / 20 / 30 / 40 / 50 kft.
- **Measured installations.** [TRANSFER]
  - YF-12A hemispherical α/β head with 640 cm of tubing: 0.15 s subsonic rising to 0.4 s at M 3. This is about 4× classical theory, attributed to port mass-flow interference. Pitot-static lag "can be as great as several seconds at high altitudes" — [NASA TN D-7819, PDF pp.8, 15, 21–22](https://ntrs.nasa.gov/api/citations/19740026347/downloads/19740026347.pdf).
  - F-14 nose head: 122–159 ms sea-level-normalised per orifice — [TM-86790, Table 2](https://ntrs.nasa.gov/api/citations/19870014183/downloads/19870014183.pdf).
  - VSRA noseboom static, 25 ft of tubing: 0.35 s first-order lag plus 0.1 s pure delay — [TM-102846, PDF p.5](https://ntrs.nasa.gov/api/citations/19900018386/downloads/19900018386.pdf).
  - ATTAS 5-hole probe: AoA 105–145 ms, AoS 130–155 ms, q 130 ms (FL90–FL240) — [DSJ 54(2):111 (2004), Tables 2–3](https://publicationsdrdo.in/index.php/dsj/article/download/2073/1103).
  - F-18 HARV HI-FADS, 8 ft of 0.06-in tubing: about 15 ms at 20 kft, −1 dB at 25 Hz, organ-pipe resonances near 90 and 180 Hz. Resonance can saturate a transducer and leave an unrecoverable bias — [NASA TM-101736, PDF p.10](https://ntrs.nasa.gov/api/citations/19910007747/downloads/19910007747.pdf).
  - Whitmore lab and flight: 40 ft × 0.081 in settles in about 0.15 s at 2,300 ft and about 0.4 s at 20 kft — [NASA TM-100430, Figs. 2–8](https://ntrs.nasa.gov/api/citations/19880010918/downloads/19880010918.pdf).
  - Gracey's worked example: λ = 1.0 s at 30 kft for 50 ft of 3/16-in line plus instruments. A 12,000 ft/min climb then gives a 200 ft altitude error and a 2.5 kt airspeed error. Electrical transducers on short lines have lag "usually so small that it is of no concern" — [RP-1046 pp.165–169](https://ntrs.nasa.gov/api/citations/19800015804/downloads/19800015804.pdf).
- **Transducer thermal error.** [TRANSFER: HiMAT] Rated 0.1 % FS within 35–70 °C, worsening by ±0.2 % FS per °C outside that band. Cold-soaked transducers below 7 °C gave random airspeed calibration errors until heater blankets were added — [NASA TM-86029, PDF pp.8, 10](https://ntrs.nasa.gov/api/citations/19840024314/downloads/19840024314.pdf).

**Total-temperature probes**
- **Recovery factor and unit spread.** [TRANSFER] r ≈ 0.96–0.99 up to M 0.7 with probe-to-probe dispersion of ±0.015; r rises above M 0.7 and tends to 1.0 supersonic — [AGARD-AG-160 Vol.2, p.47 (PDF p.55); local copy without a distribution page, see conflicts](http://spaceagecontrol.com/AD-InFlightTemperatureMeasurement.pdf).
- **Rosemount 102 (NCAR reproduction of wind-tunnel data).** [TRANSFER] — [NCAR memo 2022, Fig. 5 (PDF p.7), Fig. 22c (PDF p.30), pp.11, 22, 29](https://www.eol.ucar.edu/sites/default/files/files_live/private/TatChangesAndRecovFactor_report20220603.pdf)
  - Recovery correction for configuration a ≈ 0.13 % at M 0.6 and 0.19 % (0.11–0.27 %) for M ≥ 0.9; equivalent r ≈ 0.977 (M 0.5) to 0.994 (M 1.6).
  - De-icing heater error (DHE) vs Z = M·ρ/ρ₀: 0.2 °C floor for Z ≥ 0.3, about 1.3 °C at Z = 0.1, about 6.5 °C at Z = 0.04 (graph-read). Measured in flight at 13.6 km: 0.2–1.0 °C, typically 0.6 °C.
  - Sensor-to-sensor recovery variability < ±1.5 %. De-iced probe τ ≈ 1.3–2.3 s.
- **F-104 open-element TAT in flight.** [TRANSFER] k = 0.977–0.995 (mean 0.986, ±0.009), against wind-tunnel values of 0.992–0.999 for the same sensor type — [TM-101714, Table 8, PDF pp.8, 11](https://ntrs.nasa.gov/api/citations/19900004912/downloads/19900004912.pdf).
- **Tejas TAT correction structure.** [DIRECT] — [Rajalakshmi et al., DSJ 56(1):13–19 (2006), pp.14–15; local `research_sources/tejas_airframe/DSJ_1863.txt`](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863)
  - The Tejas air-data algorithm applies two correction look-up tables to total temperature: a de-icing-heater error table (DHE-TAB) and a self-heating error table (SHE-TAB), both indexed by a variable Z.
  - The heater state is an input flag. A software defect was found only when the heater flag was toggled in testing: with the heater failed, the DHE index was not computed and the SHE correction went wrong.
  - Vane and probe de-icing heaters are monitored for health, "failure of heaters could cause icing of the probes and vanes".

**ADC filtering, update rates, accuracy, skew**
- **AFTI/F-16 DFCS.** [TRANSFER] Control laws at 64 Hz; inputs filtered at 32 Hz; air data schedule gains asynchronously at 4 Hz — [NASA TP-2857, PDF pp.12, 45](https://ntrs.nasa.gov/citations/19890014956).
- **F-18 SRA RT-FADS.** [TRANSFER] 50 samples/s "required for flight control feedback"; 20 Hz anti-alias filters; 20-bit A/D — [NASA TM-104314, PDF p.8](https://ntrs.nasa.gov/api/citations/19960009742/downloads/19960009742.pdf).
- **ATTAS.** [TRANSFER] 50 Hz sampling, 32 Hz anti-alias. Attitude delays: φ 30 ms, θ 33 ms, ψ 110 ms — [DSJ 54(2), PDF pp.5, 9](https://publicationsdrdo.in/index.php/dsj/article/download/2073/1103).
- **F-104 IRU skews.** [TRANSFER] 0.050 s for φ, θ, p, q, r; 0.110 s for ψ, ground speed and track; 0.065 s for V_D — [TM-101714, Table 3, PDF p.11](https://ntrs.nasa.gov/api/citations/19900004912/downloads/19900004912.pdf).
- **HAL ADC.** [TRANSFER: Indian ADC] — [JOAST 67(2A), pp.278–281](https://joast.org/index.php/joast/article/download/331/310)
  - Output refresh 20 Hz on ARINC 429; flight-test recording at 64 Hz.
  - Specification accuracy: altitude ±15 ft (−2,500 to 7,500 ft), ±18 ft (10 kft), ±35 ft (30 kft), ±80 ft (50 kft); CAS ±16 / ±7 / ±4 km/h at 60 / 110 / ≥200 km/h.
  - Mach error against expected: ±0.002 (new ADC), ±0.001 (in-service ADC).
  - **Fed identical pressures, the new ADC's altitude rate lagged the in-service ADC by about 2 s, with a 3.8 m/s lower peak**, showing that filtering differs between ADC designs.
  - The test set itself had 500 ms command granularity.
- **Civil ARINC 706 ADC.** [TRANSFER] Altitude at 16/s (1 ft resolution); altitude rate at 16/s (16 ft/min resolution, ±30 ft/min below 600 ft/min, else ±5 %); Mach/CAS/TAS at 8/s; TAT/SAT at 2/s (0.25 °C, TAT ±0.5 °C) — [Revue Thommen AC32 installation manual, Tables 4–5, PDF pp.19–21](https://spaces.awi.de/download/attachments/318727453/AC32_5035_InstallationManual.pdf?api=v2).
- **Classic ADC basic accuracy.** [TRANSFER] Altitude ±15 ft at sea level to ±80 ft at 50 kft; airspeed ±2 kt at 100 kt to ±4 kt at 500 kt; Mach ±0.01 at M 0.2 to ±0.005 at M 0.95 — [Gracey RP-1046 pp.175–176](https://ntrs.nasa.gov/api/citations/19800015804/downloads/19800015804.pdf). This agrees with the HAL specification.

**Tejas-specific air-data evidence (beyond what earlier notes held)**
- [DIRECT] **Sensor set** — [DSJ 56(1) 2006, pp.13–14](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863)
  - Three pressure probes, a temperature probe and two AoA vanes.
  - Pressures are converted to electrical signals and sent to the four-channel DFCC over RS-422.
  - Faulty sensors are voted out; multiple failures set events that bring in reversionary control laws.
  - Air-data outputs also feed the HUD and the "get-U-home" panel, where a single working sensor suffices.
  - **"During flight, it was found that the airdata parameters were a function of the aircraft undercarriage operation"**, and the algorithm was modified. The position-error correction is therefore configuration-dependent (gear up/down).
- [DIRECT] **Sensor locations** (TD1/TD2/PV1 flight data): 2 side-mounted air-data probes (SADP), 2 AoA vanes (AOAV) and 1 nose air-data probe (NADP). At M 0.7 the local α at the SADP is about −20° / −2° / 29° / 38° at α_FS = −13° / 0° / 20° / 28° (graph-read), a local/free-stream slope of ≈ 1.4–1.6. Flight data at M 0.4 are linear up to α_FS ≈ 18° — [DSJ 60(6):639–652 (2010), Figs. 4–5, p.641](https://publicationsdrdo.in/index.php/dsj/article/download/582/312/2526).
- [DIRECT] Tejas Mk1A air-data computers are BEL-built (ADA/ADE/CASDIC/CSIO design) for 83 aircraft, delivered 2023–28 — [BEL press release, 16 Dec 2021](https://bel-india.in/news-bel/bel-receives-biggest-avionics-order-ever-from-hal-for-lca-tejas-fighter-aircraft-programme-3/).
- [TRANSFER/likely Tejas, aircraft unnamed] NAL flight-path reconstruction of a "high performance fighter aircraft" — [Nusrath & Singh, DSJ 70(3):231–239 (2020), Table 1, Figs. 10–13](https://publicationsdrdo.in/index.php/dsj/article/download/13596/7292)
  - Uses α_m = K_α·α + Δα.
  - Without wind modelling, reconstructed α errors reach about 2° (roller coaster) and about 5° (full flight).
  - With time-varying wind, agreement with the ADC holds to α ≈ 16° and degrades above that.
  - Estimated accelerometer biases are about 0.016 / −0.052 / 0.004 (units not stated; probably m/s²); rate-gyro biases are about −0.0047 / −0.0012 / 0.0015 (probably rad/s).

### Inferences
- [ASSUMPTION] **Vane model** (Tejas AOAV and NADP vanes): second order with f_n = k_f·V_EAS, k_f = 0.11–0.21 Hz per m/s.
  - That gives about 17–32 Hz at sea level and M 0.45, and about 14–28 Hz at 40 kft and M 0.9.
  - Set ζ either as a lightly damped boom vane (0.03–0.10, falling with altitude) or as a viscously damped production vane (unknown, temperature-dependent).
  - Because f_n sits near the 20–32 Hz anti-alias corners and 50–64 Hz frame rates, model the anti-alias filter explicitly so vane ringing aliases realistically.
  - Validate by looking for a resonant hump in the PSD of the vane signal against inertially reconstructed α in Tejas flight-test data, or obtain the vane step response from ADE/HAL.
- [ASSUMPTION] **Flow-angle corrections**:
  - α_true = (1 − k_u(M))·α_vane − b(M) − k_bend·(n_z − 1) + misalignment.
  - k_u ≈ 0.06–0.10 subsonic (noseboom) or the inverse of the SADP slope (≈ 0.65).
  - b(M) = 0.3–0.8°, with a ≈ 1° step when the shock crosses the vane at M 1.1–1.2.
  - k_bend = 0.06–0.10°/g.
  - Misalignment is redrawn (0.1–0.3°) at every radome or probe maintenance event, which creates a maintenance-correlated texture.
- [ASSUMPTION] **Static-source error**:
  - Δp/q_c(M, α, gear) with a sign set by location: noseboom +0.03–0.07, rising to 0.08–0.16 at M 0.95–1.0, then about 0.01; side vents −0.03 to −0.10 with a fluctuating band at M 0.97–1.0.
  - Include a gear-down increment (Tejas DSJ 2006 evidence; magnitude unknown).
  - The ADC applies an imperfect inverse (SSEC table error ≈ ±0.004 q_c in service, already known), so the transonic ambiguity band (≈ 0.02 M) produces realistic Mach and altitude jumps in recorded data.
- [ASSUMPTION] **Pneumatic lag**: first order with λ_SL = 0.05–0.15 s scaled by (μ/μ_SL)/δ, plus 0–0.1 s pure delay. Fault hooks: partial blockage (water, insect, ice) multiplies λ; leaks.
- [ASSUMPTION] **TAT**:
  - T_r = T_s·(1 + 0.2·r(M)·M²) with r(M) on the Rosemount curve and a per-unit offset σ_r ≈ 0.005–0.015.
  - DHE(Z) with a 0.2 °C floor, active only when the heater flag is on.
  - τ ≈ 1–2 s scaled by 1/√ṁ.
  - Fault hooks: heater failure (DHE → 0 plus icing risk, and a correction-table mismatch as on Tejas) and probe icing (frozen or large positive error).
- [ASSUMPTION] **ADC output stage**: 20 Hz output; altitude-rate filter τ ≈ 1–2 s, varied per ADC part number (2 s lag spread between designs); inertial-to-air-data skew 30–110 ms; quantisation to ARINC/1553 LSBs (as in `data_pathway_and_formats.md`).

### Gaps
- No public natural frequency, damping or time constant for a production fuselage-side AoA vane on any fighter, including Tejas. MIL-T-25627 (AoA transmitter specification) was not retrievable.
- No Tejas SSEC curve, upwash factors, boom-bending value, pneumatic line geometry, TAT probe model or ADC/DFCC filter corners and rates. The ADE/ADA paper on LCA flight-control software timing at journal.accsindia.org was unreachable. The NATO RTO-MP-SCI-162-14 Tejas flight-test paper returned 403.
- MIL-P-26292C (the position-error tolerance envelope cited by ADA) was not retrieved.
- Rosemount TR 5755 was not retrieved from an official host.

---

## Q2. Fuel measurement: capacitance gauging texture (attitude, acceleration and slosh, density and dielectric compensation, accuracy classes, the Tejas zoom-climb false low-fuel warning) and engine fuel-flowmeter type and accuracy vs flow

### Takeaway
**Capacitance gauging.**
- *Accuracy and attitude.* A Class I system allows about ±2 % near empty and ±6 % near full. Measured attitude error inside ±10° pitch/roll is ≤ 1 % FS (σ 0.35 % FS).
- *Coverage limits.* Each tank may leave ≤ 2 % of usable fuel or 10 gal unmeasured (Class I/II) below or above the probes' sensing range. When probes unwet at low fuel or high tilt, the computed quantity becomes invalid or drops.
- *Density compensation.* Compensation from dielectric constant leaves about 1–1.3 % (2σ) residual on clean fuel. Water, microbial films and stratification add 2–5 %.
- *Smoothing and response.* Fighter systems respond in seconds (F-16 indicator ≈ 6 s for a full-scale step). Transport-style filters use 15–60 s time constants that switch with the vertical-acceleration level.
- *Failure handling.* One probe out of range → reconfigure; two or more → hold the last value and flag.
- *Tejas zoom-climb case.* These mechanisms reproduce ADA's documented false low-fuel warning at > 40° pitch, max AB, < 1,200 kg fuel [DIRECT, already known]: the fuel plane follows the specific-force vector, probes unwet, and the low-level logic trips.

**Fuel flowmeters.**
- *Meter types.* Turbine (volumetric) meters respond in about 10 ms with ±2 % in-service accuracy and about 10:1 range. Angular-momentum mass meters give ±0.9 % of point in cruise but degrade at idle and maximum flow. Their output updates only every 300 ms, and about 50 % of their removals are unconfirmed.
- *Fighter engine flow range.* Idle-to-full-AB flow spans 50–140:1, so one meter cannot be accurate everywhere.
- *F404 evidence.*
  - The F404-400 had a pulse-rate engine flowmeter, and test-cell turbine meters lost signal at low speed [DIRECT].
  - CF-18 IECMS did not measure AB fuel flow in flight [DIRECT].
  - **Conflict:** the IN20 production Wf transducer type is unresolved. The pulse-rate output suggests a turbine meter, while "sampled faster than they respond" (AGARD-CP-448) suggests a slow angular-momentum meter.

### Cited Findings

**Capacitance gauging: accuracy, attitude, coverage**
- **Installed-accuracy specification.** [TRANSFER: US fighter-era installation and calibration specification; Tejas class unknown] — [MIL-G-7940C, §§3.6.4, 3.8.2, 3.10, 6.2.4, 6.3j](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-G/MIL-G-7940C_36792/)
  - Installed accuracy follows the MIL-G-26988 classes, *including* errors at sustained "normal tactical use" attitudes but not "extreme momentary attitudes".
  - Unmeasured fuel per tank: ≤ 2 % of usable volume or 10 gal, whichever is greater (Class I/II); ≤ 0.5 % or 2.5 gal (Class III).
  - Calibration needs error-vs-quantity data at ≥ 5 attitudes, and the empty tank must read zero.
- **Simmonds patent.** [TRANSFER] — [US 5,495,745 (Simmonds)](https://patents.google.com/patent/US5495745A/en)
  - "In a typical class I system, the allowed fuel measurement error may be ±2 % near empty and ±6 % near full."
  - "In a coordinated turn the fuel may not have moved, although the aircraft may be in a 3° roll": the fuel surface follows apparent gravity, not the Euler angles.
- **NADC/GE laboratory tank.** [TRANSFER: multi-probe plus densitometer system with the same plane-fit and volume-integration logic as capacitance systems] — [NADC-78187-60 (DTIC ADA091758), pp.7–14](https://archive.org/details/DTIC_ADA091758)
  - 1,000 lb full scale. Scale error: max 0.5 % FS, σ 0.29 % FS.
  - Attitude error at ±10° pitch + ±10° roll, 20–80 % fill: max 1.0 % FS, mean 0.17 %, σ 0.35 % FS.
  - At 80 % full, fuel sloshed out. At 20 % full, more than one probe unwetted and the data were invalid.
  - With one probe failed and the system reconfigured: max −0.6 % FS.
  - A coarse tank-geometry model added up to 0.57 % FS.
  - A 1 % single-probe error produced 0–1 % system error, depending on how signs combined.
  - Densitometer contribution 0.13 % FS.
  - Software: one probe out of range → reconfigure with 3 probes plus an error code; ≥ 2 out of range → hold the last mass plus an error code; parity error → hold; densitometer out of range → previous or average density. Computation cycle 5 s.
- **Probe count.** [TRANSFER] Typically 9–12 probes per tank. A broken probe is replaced by a model "virtual probe", and more probes give lower attitude variance — [US 10,564,022 B2 (Simmonds)](https://patents.google.com/patent/US10564022B2/en).
- **Civil zero-reading rule.** [TRANSFER] Indicators must read zero in level flight when only unusable fuel remains — [14 CFR 25.1337(b)(1)](https://www.law.cornell.edu/cfr/text/14/25.1337).

**Density and dielectric compensation, contamination**
- **Dielectric-to-density regression.** [TRANSFER] 95.5 % of JP-4/JP-5 samples fall within 1.3 % of the regression line (2σ ≈ 1.3 %); 51 of 55 airline samples were within ±1 %; Clausius–Mosotti nonlinearity ≈ 0.5 % between −45 and +70 °C — [Stuart 1974 (Simmonds), quoted in NADC-80254-60 (DTIC ADA104364), PDF p.30](https://archive.org/details/DTIC_ADA104364).
- **Temperature and sample effects.** [TRANSFER] The dielectric/density ratio varies about 3 % over −55 to +55 °C, so temperature correction is needed; up to 1 % sample-to-sample variation "cannot be compensated for". Some aircraft used a manual density corrector set at each refuel — [AGARD-AG-160 Vol.3, §2.6.1, pp.6–7 (DTIC AD0741610)](https://archive.org/details/DTIC_AD0741610).
- **Contamination errors.** [TRANSFER: Boeing patent background on capacitance systems] — [US 5,138,559](https://patents.google.com/patent/US5138559A/en)
  - Dielectric compensator plus water: 2–4 % combined.
  - Fungus or dirt on probes: +1–2 %.
  - Temperature stratification: up to 5 %.
- **Microbial attack.** [TRANSFER: airline experience] Microbes attack probe coatings, causing electrode corrosion, "electrical noise in the capacitance bridge" and faulty indications — [NASA TM-87706, p.1](https://ntrs.nasa.gov/citations/19860018913).
- **Component tolerances.** [TRANSFER] — [MIL-G-26988C, Table I, §§3.6.2.3, 3.6.4.1, 3.6.5.1, 3.18, 4.6.20](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-G/MIL-G-26988C_36788/)

  | Item | Class I | Class II/III |
  |---|---|---|
  | Tank-unit dry capacitance at temperature | ±1.0 % | ±0.4–0.5 % |
  | After water immersion | ±2.0 % | ±1.0 % |
  | After humidity | ±2.0 % | ±0.5 % |
  | After fungus | — | ±1.0 % |
  | Indicator dead spot | 0.2 % FS | 0.1 % FS |

  - A failed gauge drives the pointer below zero.
  - An erratic attitude-correction computer clamps corrections to zero and lights a lamp.
  - Required MTBF ≥ 3,000 h.
  - Full indicator travel must take ≤ 1 min (≤ 3× that at −55 °C).
- **F-15/F-16 gauging hardware, 1979.** [TRANSFER/near-DIRECT for fighter hardware] — [AFWAL-TR-80-2058 (DTIC ADA092907), pp.19–40, Tables A-13 to A-16](https://archive.org/details/DTIC_ADA092907)
  - The F-15 and F-16 "high frequency DC" systems (6 kHz excitation) were unaffected by anti-static additive up to 5,000 pS/m.
  - Older 400 Hz systems drifted. KC-135 full-tank reading rose +0.8 % at 500 pS/m, +1.5 % at 1,000, +2.5 % at 2,000 and +3.1 % at 3,000–4,000 pS/m, and its dead band grew from 0.25 % to 1.76 % FS. Error scales with (σ/f)².
  - **F-16 indicator response to a full-scale step: 5.8–6.6 s** (KC-135 27–29 s; A-7 12–15 s).
  - F-16 readouts moved in 10–20 lb steps, and an empty tank read 0 or −20 lb.
  - F-15 sensitivity ≈ 5.8 lb on a 4,200 lb channel (≈ 0.14 % FS).
- **Pressure-based gauging filters (transport).** [TRANSFER] Filter time constants of 15 s when parked, 45 s at a vertical-acceleration index of 0.05–0.1 ft/s², and 60 s above that, from 120/360/480 samples ([DERIVED] ≈ 8 Hz sampling) — [US 5,138,559](https://patents.google.com/patent/US5138559A/en).
- **Tejas probe.** [DIRECT, re-confirmed] The F2-F/T probe outputs a frequency that varies inversely with immersed level: period accuracy ±3 µs empty and ±5 µs wet; 230 mm long — [DDP node 10090](https://www.ddpmod.gov.in/node/10090).
  - Frequency output with high-frequency excitation suggests immunity to fuel conductivity, as in the F-15/F-16 systems [ASSUMPTION].

**Engine fuel flowmeters**
- **AGARD-AG-160 Vol.3 (1972).** [TRANSFER: flight-test handbook] — [§§2.4, 4.3.3, Table 1 p.24 (DTIC AD0741610)](https://archive.org/details/DTIC_AD0741610)

  | Meter type | Accuracy | Range and response | Reliability and failure behaviour |
  |---|---|---|---|
  | Turbine (volumetric) | Calibration nonlinearity +2/−1 % with a viscosity "hump" at low flow; a further ±2 % at fuel-temperature extremes; repeatability < 0.1 % | ≈ 10:1 range; τ ≈ 10 ms | Upstream pipework shifts calibration up to 5 %; MTBF > 10,000 h; bearing wear gives an amplitude-modulated "erratic" output; a jammed rotor raises ΔP from 1 to 6 psi |
  | Variable orifice | ±1.3 % of point | τ 50 ms | — |
  | Angular-momentum "true mass" | ≤ 0.9 % of point in cruise (fuel 30–100 °C); ~1 % adverse at fuel temperature extremes; positive error at low flow (re-circulation), negative at high flow | Rise ≈ 80 ms, but **output updated only every 300 ms** (two pulses per revolution) | MTBF ≈ 40,000 h (low-speed drive); **"approximately 50 % of all flowmeter removals … are unconfirmed"** |

  - Fuel-used accuracy in normal use (RSS): turbine with density and temperature correction ±2.1 %; variable orifice ±1.5 %; angular momentum ±0.5 %.
- **NASA High-Accuracy Fuel Flowmeter programme.** [TRANSFER]
  - Older angular-momentum meters settle in ≈ 0.75 s for a 0→4,500 kg/h step and ≈ 1.5–2 s for 13,600→18,100 kg/h; the spring-mass element alone takes ≈ 1 s — [NASA CR (HAFF Phase I), Fig. 9, PDF p.33; §3.3.2](https://ntrs.nasa.gov/citations/19830013043).
  - Production turbine meters lack viscosity compensation, so error widens at 220 K and 400 K fuel — [NASA TM-83484](https://ntrs.nasa.gov/citations/19830025612).
- **Navy flowmeter targets.** [TRANSFER] ±0.5 % of reading at 3,000–25,000 pph but ±5 % at 100 pph; repeatability ±0.1 % (high flow) and ±2 % at 200 pph; hysteresis 0.3 %; response 2 s. Idle-to-full-AB flow ratio 50:1–100:1, full scale 40,000 lb/h — [NADC-80254-60 (ADA104364), Table 1 PDF p.11; Exhibit B PDF p.102](https://archive.org/details/DTIC_ADA104364).
- **Test-cell range.** [TRANSFER] Idle-to-take-off flow ratio ≥ 140:1 in the test cell, forcing turbine-meter switching — [AEDC-TR-89-6 (ADA210547), p.1](https://archive.org/details/DTIC_ADA210547).
- **F404-specific.** [DIRECT: F404-400]
  - The RAAF F404 engine-mounted fuel-flow meter has a "pulse rate" output; the test-cell turbine meter gave too low a signal at low engine speed — [Streatfeild 1988 (ADA196265), §6.1c](https://archive.org/details/DTIC_ADA196265).
  - X-29A volumetric meters (WFE, WFAB, WFABP) were calibrated with the aircraft's own upstream lines — [NASA TP-3001, p.2](https://ntrs.nasa.gov/citations/19900015818).
  - Large AB flowmeters read low flows with great difficulty in the test cell — [NASA TM-100159](https://ntrs.nasa.gov/citations/19870020104).
  - CF-18 IECMS: AB fuel flow "not measured during flight" — [ADA219105 §7.1](https://archive.org/details/DTIC_ADA219105).
- **F100/F-15 evidence.** [TRANSFER]
  - High-accuracy flight-test meters were "used in place of the IDEEC values" — [NASA TM-1998-206560, PDF p.23](https://ntrs.nasa.gov/citations/19980228163).
  - The F100 multivariable control's FTIT estimator blends a fuel-flow lead term against the slow thermocouple — [NASA TP-2231, PDF p.11](https://ntrs.nasa.gov/citations/19840003103).
- **FADEC metering-valve-based Wf.** [TRANSFER: patents] The FADEC reads metering-valve position through an LVDT ([US 9,243,565 B2](https://patents.google.com/patent/US9243565B2/en)). The indirect method's error sources are listed (ΔP regulation, LVDT precision over temperature) but not quantified ([US 6,389,816](https://patents.google.com/patent/US6389816B1/en)).
- **Cockpit fuel-flow indicator tolerance.** [TRANSFER: legacy specification] ±10 pph (500–3,000 pph scale) and ±100 pph (3,000–15,000); ±15/±150 pph cold; pointer oscillation under vibration ±20/±200 pph; response ≤ 3 s — MIL-I-25906D, Tables I–II (Dist A; local `research_sources/texture_fault_gaps/fuel_sensors/MIL-I-25906D_fuel_flow_indicator.pdf`, downloaded from everyspec.com; exact page URL not recorded).

### Inferences
- [ASSUMPTION] **Per-tank quantity model** (F1, F1A, F2, wing and drop tanks):
  - Fit the fuel plane to the INS specific-force vector, not to pitch and roll, and integrate over a tank geometry model with ≤ 0.5 % FS model error.
  - Static error inside the Class II envelope ±(2 % of indication + 0.75 % FS). [DERIVED] On 2,458 kg that is ≈ ±68 kg at full, or ±147 kg for Class I.
  - Per-refuel density bias drawn from N(0, 0.65 %); stratification bias of 0–2 % after a hot soak; slow probe-capacitance drift of up to 1–2 % for water or microbial contamination (with added noise).
  - Low-level dead zone: the reading goes to 0 or is held while up to 2 % or 10 gal per tank remains below the lowest sensing point.
  - When the specific-force tilt unwets probes, the plane fit fails and the quantity drops or is held. This reproduces the Tejas > 40° zoom-climb false low-fuel warning, and should be a "pre-mod" configuration flag.
  - Validate with HAL probe acceptance data and the ADA attitude rig.
- [ASSUMPTION] **Gauging dynamics:**
  - probes sampled at 1–8 Hz;
  - total smoothed with τ ≈ 5–15 s in steady flight, lengthened to 45–60 s, or held, while |specific force − 1 g| exceeds a threshold;
  - 1 Hz on the bus.
  - Consistency check: gauged decrease versus integrated Wf, with a residual of ≤ 2 % per sortie.
- [ASSUMPTION] **Fuel-flow channels:**
  1. A FADEC-computed main flow from metering-valve LVDT position and ΔP: 2–3 % bias drifting with fuel temperature, specific gravity and regulator wear; fast.
  2. A measured main flowmeter. If angular-momentum: ±0.9 % of point in cruise, 2–5 % at idle (+) and near maximum (−), held for 300 ms (staircase), 80 ms rise. If turbine: ±2 %, τ 10 ms, viscosity hump at low flow.
  - No in-flight AB flow channel.
  - Flowmeter "removal NFF" ≈ 50 %.

### Gaps
- No public fighter gauging error vs g or slosh beyond the ±10° laboratory data and the Tejas zoom-climb case.
- No HAL ECFM filter constants, Tejas tank probe counts or Tejas gauging accuracy class.
- No Gripen, Typhoon or Rafale gauging papers; the Gavel Gripen thesis was unreachable (DiVA refused connection).
- IN20 production Wf transducer type and FADEC fuel-flow estimation error are not public.

---

## Q3. Engine-control (and fighter FCS) signal validation: range, rate and cross-channel checks, persistence, fault accommodation, and what the recorded signal looks like after accommodation

### Takeaway
Officially released fighter evidence is now concrete enough to build a validation layer from evidence rather than assumption. It comes from four bodies of work:
- the NASA F-15/F100 DEEC programme (NASA CP-2298 and TM-86735);
- NASA Lewis's ADIA analytical-redundancy work on a full-scale F100 (TP-2740, TP-2925, TM-89880);
- GE's F404 FADEC "FICA" demonstrator, as summarised by NASA (TM-101396);
- the AFTI/F-16 triplex digital flight-control experience (NASA TP-2857; Mackall 1984).

Together they give an evidence-anchored chain:
1. **Range check** → hard fail.
2. **Dual-channel comparison** → soft fail; the *safer* (higher) value is used.
3. **Comparison with a synthesised or model value**, with separate steady and transient tolerances (DEEC: 25 % steady, 45 % transient).
4. **Persistence counter.** Documented values: AFTI 4 iterations ≈ 62 ms; J85 4 consecutive out-of-range rates; NASA dual-channel study 25 steps = 0.5 s. ADIA heals a sensor after 10 good 40-ms updates.
5. **Accommodation.** Substitute the synthesised value; inhibit dependent functions (afterburner, nozzle trim, stall detection); drive the actuator to a fail-safe position (CIVV full-cambered, nozzle closed); cut a limit (N2 max −1,000 rpm); or transfer to a hydromechanical backup.

**What the record shows after an accommodated fault.** The raw channel shows a step, a wrap-around, or a slow excursion. A flag follows, often late because transient tolerances are wide. The channel then switches to a smoother synthesised value, and secondary control effects appear: nozzle opening, thrust loss, AB unavailable, or a sub-idle rollback after a false stall detection. It is not "more noise".

**Wide tolerances mean some real faults are never detected**, and the control law acts on the corrupted value:
- a trapped PS2 went undetected for a 20,000 ft climb;
- a vented PB triggered a false stall recovery and a sub-idle stagnation;
- a wrap-around scaling bug hid a failed-high PS2.

On the F404 specifically: the -400 ECU's dual-NL mismatch leads to part power (already known), and the GE F404 FADEC demonstrator substituted model estimates for up to three sensors at once at a 10 ms update.

### Cited Findings

**F100 DEEC fault detection and accommodation (single-channel digital control with selective redundancy and a hydromechanical backup)** [TRANSFER: F100-PW-100 DEEC → F404-IN20 FADEC; same generation of fighter digital engine control logic; the IN20 FADEC is dual-redundant and newer, so thresholds will differ]

- **Scope of the logic.** FDA can "detect and identify 160 faults" and "comprises 40% of the DEEC control logic" — [Myers, Baer-Riedhart & Maxwell, NASA TM-86735 (1985), p.3](https://ntrs.nasa.gov/citations/19850021650).
  - **Conflict:** CP-2298 Paper 3 says the DEEC detects "150 faults" — [Myers, NASA CP-2298 Paper 3, p.48](https://ntrs.nasa.gov/citations/19860015874).
- **Three accommodation levels**, each annunciated by a cockpit caution light and a bit in the DEEC diagnostic words:
  1. normal operation with notification;
  2. gas generator normal but augmentation inhibited;
  3. automatic transfer to the backup control (BUC).
  - BUC transfer is triggered by: (a) a fault that prevents control of core fuel flow or RCVV; (b) engine-protect logic seeing N1, N2 or FTIT over limit, *or a rate that will reach the limit*; (c) an independent hardware N1 overspeed circuit — [CP-2298 Paper 7 (Baer-Riedhart), pp.108, 111](https://ntrs.nasa.gov/citations/19860015878).
- **Hard and soft failures.**
  - Hard: a sensor outside its expected max/min.
  - Soft: dual signals disagree by more than a predetermined tolerance; "the more conservative (safer) sensor value is then used".
  - Redundant-sensor logic (TT2, N1, N2, RCVV, FTIT, WFGG, PLA):
    - both in range and agreeing → average;
    - disagreeing → use the higher (safer) value;
    - one out of range → use the in-range one;
    - both out of range → hold the last in-range value and transfer to BUC.
  - Source: [TM-86735, pp.3–4, Figs. 5–6](https://ntrs.nasa.gov/citations/19850021650); [Paper 7, Table 1, p.113](https://ntrs.nasa.gov/citations/19860015878).
- **Non-redundant pressures (PS2, PB, PT6M).**
  - Each pressure is range-checked together with its transducer temperature. The three vibrating-cylinder transducers share the fuel-cooled electronics, so a failed transducer-temperature reading is replaced by a neighbour's. The pressure is "declared failed after a specified number cycles" (count not given).
  - PB is synthesised continuously two ways: from PS2, TT2 and N2C (PBSYN2), and from PT6M, TT2 and N1C (PBSYN6). It is declared failed if the three values differ by more than **25 % in steady state or 45 % during transients and AB operation**.
  - Source: [Paper 7, p.115](https://ntrs.nasa.gov/citations/19860015878); [TM-86735, pp.3–4](https://ntrs.nasa.gov/citations/19850021650).
  - **Conflict (OCR):** Merrill's survey reads "225 percent", most likely a mis-scan of ±25 % — [NASA TM-101396, p.26](https://ntrs.nasa.gov/api/citations/19890004061/downloads/19890004061.pdf).
- **Accommodation actions** — [Paper 7, Table 1, p.113](https://ntrs.nasa.gov/citations/19860015878); [TM-86735, Table 1, p.7](https://ntrs.nasa.gov/citations/19850021650)

  | Failed item | Detected condition | Action |
  |---|---|---|
  | CIVV feedback | Out of range | Vanes driven full-cambered (−25°); AB and nozzle-area trim inhibited |
  | Nozzle area AJ feedback | Out of range | Nozzle full closed; AB inhibited |
  | Augmentor flow/sequence feedbacks (WFC, SVP) | Out of range | AB inhibited |
  | Duct AB metering (WFD) | Out of range | AB limited to segment 2 |
  | PS2 or PT6M | Out of range or soft | Synthesised substitute; AB and nozzle trim inhibited; PB soft-fail check bypassed |
  | PB | Failed | Synthesised; AB inhibited; **stall detection disabled** |
  | PB together with PS2 or PT6M | Both failed | BUC |
  | Both FTIT channels | Out of range | Synthesised FTIT (from PB and PT2); **N2 max reduced 1,000 rpm** |
  | Mach input | Out of range | Set to 0.15 with limits |
  | Dual power, interface loss or software integrity | Failed | BUC |

- **Built-in tests running every cycle** — [Paper 3, pp.48, 52](https://ntrs.nasa.gov/citations/19860015874); [Paper 7, p.109](https://ntrs.nasa.gov/citations/19860015878):
  - power supply surge/drop → reset and BUC;
  - cycle-time watchdog (a repeated time-out → BUC);
  - primary and secondary clock monitoring at 1.7 MHz;
  - thermocouple amplifier drift;
  - resolver power and resolver-to-digital converter;
  - torque-motor "wrap-around": two sum and four difference voltages of the dual coils;
  - open thermocouple;
  - scratch-pad RAM and PROM checksum ("as time permits");
  - parameter range checks;
  - redundant-parameter agreement;
  - open-loop/"loop shutdown" when actuator feedback does not track command;
  - "loop dynamic checks for degradation of actuator response".
- **Monitoring logics with fault-like outputs.**
  - Stall detection uses the rate of PB decrease.
  - AB blowout is detected from ΔEPR, ΔAJ or loss of the UV light-off detector.
  - Source: [Paper 3, p.49](https://ntrs.nasa.gov/citations/19860015874).
- **In-service experience: 30 flights, 35.5 flight hours, 155 airstarts, 125 manual BUC transfers.**
  - Two real sensor failures, both accommodated:
    - **TT2 channel A** went intermittent, then hard; it was flagged when it crossed the −110 °F limit, at M 1.4 and 30,000 ft. Cause: a contaminated connector. No performance loss, because the redundant channel was used.
    - **PT6M** first "failed to a value of 92 lb/in², less than the upper limit of 110 lb/in²". While it was in range the nozzle was "driven open by the high PT6M signal" to hold EPR, and augmentor pressure moved. Once it exceeded 110 psi the flag set and the nozzle returned to schedule. Cause: a contaminated PROM socket on the vibrating-cylinder transducer.
  - There were "no false failures detected" and no automatic transfers to BUC.
  - Source: [Paper 6, pp.92–93](https://ntrs.nasa.gov/citations/19860015877); [Paper 7, pp.117–119](https://ntrs.nasa.gov/citations/19860015878).
- **Induced-fault flight tests (4 flights), with switches and valves on the sensor lines** — [TM-86735, pp.4–6, Figs. 9–14](https://ntrs.nasa.gov/citations/19850021650):
  - **PS2 failed high (ported to PS6), ground:** never detected. A scaling bug wrapped values above 600 psi around (601 psi read as 1 psi). The synthesised PB from a high PS2 was about 870 psi, read as 270 psi, which was close to the true ≈290 psi.
  - **PB vented low during an idle-to-intermediate snap:** not detected, because the 45 % transient tolerance had not been reached. The stall logic declared a **false stall**, cut fuel, and "the engine decelerated to a subidle condition", unresponsive to throttle. It had to be shut down and restarted.
  - **PB failed (M 0.8, 20,000 ft, idle-to-intermediate snap):** undetected within the 45 % transient band. When the logic switched to the 25 % steady band it declared PB failed and accelerated the engine on PBSYN2. The simulation matched the response.
  - **PS2 trapped at 5,000 ft (simulated iced probe), intermediate-power climb to 30,000 ft:** undetected until the PB–PBSYN2 error reached 25 % **at 25,000 ft**. Meanwhile the engine ran at higher EPR and lower fan stall margin.
  - **CIVV feedback broken during a snap:** detected; vanes full-cambered, giving lower fan pressure ratio and lower PB.
  - **Both FTIT channels open:** the internal driver took the signal to 0 or full scale from the last good value. FTITSYN was used and N2 max cut 1,000 rpm.
  - **PS2 failed high during a max-power acceleration from M 0.8 to M 1.35:** undetected within the 45 % AB band. The engine "was downtrimming EPR (opening the nozzle)", thrust was "much lower than normal", and FTIT was "considerably lower than the simulation prediction".
  - **Dual pressure failures** (PS2 soft high plus PB hard) were not flown: simulation showed overspeed or stall potential.
- **Reversionary (BUC) mode texture.**
  - Idle N2 under BUC falls with altitude; below 65 % N2 is marginal and below 60 % undesirable.
  - Idle-to-MIL ramp results: snaps and ramps all succeeded at idle N2 > 70 %; a 5-s ramp needed idle N2 > 63 %; idle N2 < 60 % needed ≥ 7 s to avoid compressor stall.
  - On a pilot-selected BUC transfer at MIL (M 0.6, 30,000 ft), fuel flow stepped down because the BUC schedule is lower.
  - Source: [CP-2298 Paper 9, pp.141–150](https://ntrs.nasa.gov/citations/19860015880).
- **Data rates in the DEEC programme.**
  - The 50 DEEC digital words (including eleven 16-bit diagnostic words) were updated at 8 samples/s.
  - High-response pressures were recorded at 200 sps and other parameters at 20 sps, with anti-alias filters.
  - Source: [Paper 6, p.92](https://ntrs.nasa.gov/citations/19860015877). Earlier F100 EMD flights updated DEEC digital data at 5 samples/s — [NASA TM-85902, p.4](https://ntrs.nasa.gov/citations/19840016520).

**F404 FADEC "FICA" (GE, 1982)** [TRANSFER: F404 FADEC lineage → IN20; architecture, not values]
- FICA used "a simplified, fourth-order, component-level model". It was "implemented in FADEC microprocessor hardware in a 0.01-s update time increment" and checked against sea-level and altitude engine tests.
- **"Single, double, and triple substitutions of FICA-generated estimates were performed successfully"**.
- Actuator FICA was demonstrated for **exhaust-nozzle hard open and closed failures**. Thrust was maintained "by adjusting the gas generator speed reference schedule".
- Source: [Merrill, NASA TM-101396 (1988), pp.24–26](https://ntrs.nasa.gov/api/citations/19890004061/downloads/19890004061.pdf). The substituted parameters were already listed in `f404_in20_engine_model.md` Q3 (Linebrink & Vizzini, SAE 821371).
- The companion JTDE FICA compared sensor-minus-model errors to a preset threshold and covered hard failures only — [TM-101396, p.25](https://ntrs.nasa.gov/api/citations/19890004061/downloads/19890004061.pdf).

**Analytical redundancy on a full-scale F100 (ADIA)** [TRANSFER: research algorithm on F100 hardware; gives the detectability floor of model-based validation]
- **Structure.**
  - Hard failures are "out-of-range or large bias errors that occur instantaneously"; soft failures are "small bias errors or drift errors that accumulate relatively slowly".
  - Hard detection: |residual| > threshold in a single update; there is no persistence.
  - Thresholds = 2 × "adjusted standard deviation": N1 300 → 600 rpm; N2 400 → 800 rpm; PT4 30 → 60 psi; PT6 5 → 10 psi; FTIT 250 → 500 °R.
  - Soft detection: a bank of hypothesis Kalman filters forms a WSSR, smoothed with a 0.1 s first-order lag, and compared with an **adaptive threshold that expands during transients** (Mtran = 4.5 in transient, else 0; τ = 2 s). This let the steady threshold drop to 40 %, an 80 % improvement.
  - **Heal logic:** a failed sensor is declared healed if its residual stays below 10 % of the hard threshold for 10 update intervals.
  - Control update interval 40 ms.
  - Source: [Merrill, DeLaat & Bruton, NASA TP-2925 (1990), pp.6–11, Table II](https://ntrs.nasa.gov/api/citations/19900005796/downloads/19900005796.pdf); [TM-89880, Table 1](https://ntrs.nasa.gov/api/citations/19870012664/downloads/19870012664.pdf).
- **Minimum detectable failures on the real engine (10,000 ft, M 0.6; drift sized for detection ≈ 5 s after inception)** — [Merrill et al., NASA TM-89880 (AIAA-87-2259), Table 3](https://ntrs.nasa.gov/api/citations/19870012664/downloads/19870012664.pdf)
  - At PLA 50°:
    - N2 bias 350 rpm, drift 100 rpm/s;
    - N1 drift 200 rpm/s; an N1 failure smaller than the 600 rpm hard level could not be detected;
    - PT4 bias 30 psi, drift 4.0 psi/s;
    - PT6 bias 5 psi, drift 0.9 psi/s;
    - FTIT bias 200 °R, drift 100 °/s.
  - At PLA 80°: N1 and N2 −350 rpm and −125 rpm/s; PT4 −14 psi and −2.5 psi/s; PT6 −3 psi and −0.6 psi/s; FTIT −200 °R and −100 °/s.
  - Sequential failures (N1, then N2 4 s later, then PT4, then PT6) were each detected in order.
  - Open-loop operation with all sensors failed held over 75 % of the power range.
- **Earlier engine analytical redundancy** [TRANSFER] — [TM-101396, pp.3–5](https://ntrs.nasa.gov/api/citations/19890004061/downloads/19890004061.pdf)
  - J85 rate-check logic (1974): failure declared after **four consecutive out-of-range rates**; synthesised-value substitution from tables; a 15-ms frame.
  - Effects of the substitution: with one sensor failed, steady speed was held within 1 % and thrust reached 92 % of maximum. With two failed, thrust reached 87 % and acceleration time grew from 3 s to 30 s.
  - TF30 study: about 0.025 s frame; rate checks.
- **Production dual-channel FADEC (PW2037)** [TRANSFER: civil FADEC, same validation pattern] — [TM-101396, p.28](https://ntrs.nasa.gov/api/citations/19890004061/downloads/19890004061.pdf)
  - Seven dual sensors (two speeds, two pressures, two temperatures, TLA), covered by channel-to-channel comparisons plus software range and rate checks.
  - Speeds and pressures are also compared with synthesised estimates; after a dual failure the synthesised value is used.
- **NASA dual-channel diagnostic logic** [TRANSFER: commercial turbofan simulation] — [Kobayashi & Simon, NASA TM-2008-215228, Tables 2–4, p.8](https://ntrs.nasa.gov/api/citations/20080030793/downloads/20080030793.pdf)
  - Sensor σ (% of value): N1 and N2 0.25; P25 and PS3 0.50; T25, T3 and T49 0.75; T2 σ 5 °F.
  - Thresholds: dual-channel residual ±2.0σ; analytical residual ±1.4–5.2σ.
  - Residuals are low-pass filtered at 1 rad/s, and **a violation must persist for 25 consecutive steps (0.5 s)**.
  - Results: a 1.4σ bias raised an anomaly flag; 1.8σ was detected and isolated to a channel.
  - With the health baseline frozen, a 1 % health drift triggered a "component fault" flag far before maintenance was needed.

**Fighter flight-control redundancy management (for air-data and inertial channels)** [TRANSFER: AFTI/F-16 triplex asynchronous DFCS → Tejas quadruplex DFCC; asynchronous channels are a texture source]
- Inputs use good-signal averaging with a failure threshold of **15 % of full scale**. Surface commands use the same 15 % threshold plus a rate term: if the surface moved 5 % FS in the previous iteration, the threshold became 20 %.
- **Persistence was four iterations (about 62 ms).**
- Channel skew between asynchronous computers forced wider thresholds. The 15 % failure transients allowed horizontal-tail transients of 3.75° and, at low altitude and high speed, normal-acceleration transients > 3 g.
- Unresolved dual-sensor failures reconfigure the control laws.
- Source: [Mackall, NASA TP-2857 (1988), pp.12–13](https://ntrs.nasa.gov/citations/19890014956); [Mackall 1984, NASA-CP AFTI/F-16 DFCS experience, pp.473–481](https://ntrs.nasa.gov/api/citations/19840012524/downloads/19840012524.pdf).
- Flight record:
  - **15 false in-flight failures, 3 of unknown cause, and 1 real failure** (a pushed-back connector pin). The false failures were caused by design deficiencies coupling computer skew with sensor noise, not hardware.
  - Preflight BIT took about 2.5 min, with nuisance BIT failures attributed to EMI.
  - Failures required pilot reset or a power cycle.
  - Source: [Mackall 1984, pp.480–481](https://ntrs.nasa.gov/api/citations/19840012524/downloads/19840012524.pdf).
- [DIRECT] Tejas air-data sensors are voted out on mistrack, and multiple failures set reversionary-law events — [DSJ 56(1) 2006](https://www.publicationsdrdo.in/index.php/dsj/article/view/1863). The Tejas DFCC is quadruplex with cross-channel links ([BEL DFCC product page](https://bel-india.in/product/digital-flight-control-computer-dfcc-mk1)). Thresholds are not public.

**FADEC fault-code behaviour in a real event** [TRANSFER: RM12 (F404 derivative) FADEC, Gripen bird strike 2015] — [SHK RM 2019:02, pp.40–41 (Swedish), local `engine_data/rm12/shk_RM2019_02_kallinge_jas39.pdf`](https://www.shk.se/download/18.2d6f089b18faca29dc81a71f/1701764064974/RM2019_02-Slutrapport.pdf)
- The FADEC detected a flameout from **low T5 plus falling NH** and activated ignition. "When the turbine outlet temperature rose again the FADEC removed the flameout fault code", but kept ignition on for a further period to ensure stable combustion.
- The controlled variables (fuel flow, fan and compressor vane angles, nozzle area) were commanded normally throughout. "A number of consequential faults were detected" because the compressor no longer worked and the rotor speeds decayed.
- The FADEC internal memory could not be read out because the unit was too damaged.

**Civil certification frame** [TRANSFER: FAA AC 33.28-3 (2014), pp.18–20, local `signal_validation/FAA_AC_33.28-3.pdf`](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_33.28-3.pdf)
- An EECS should not cause more than one loss-of-thrust-control (LOTC) event per 100,000 engine flight hours.
- Thrust oscillations under 10 % peak-to-peak of take-off thrust are acceptable.
- LOTC is defined as inability to modulate thrust between idle and 90 % of maximum.

### Inferences
- [ASSUMPTION] **The Phalanx IN20 FADEC validation layer should reproduce four evidence-based behaviours**, not idealised detection:
  1. **Tolerance bands set wide enough to miss slow or in-band faults.** Use synthesised-vs-measured tolerances of about 25 % steady and 45 % transient for pressures (DEEC), and about ±2σ dual-channel. Model-based soft detection should have a floor similar to ADIA: N2 ≈ 2.5 % of 14,000 rpm, pressures ≈ 5–15 % of reading, T5 ≈ 100 K.
  2. **Persistence of a few frames** (4 frames / 60 ms for FCS-class monitors; 0.5 s for diagnostic residuals) plus heal logic (10 good frames).
  3. **Accommodation that changes the plant.** Examples: inhibit AB; close the nozzle; set the FVG/CVG schedule to a safe position; cut the N2/T5 limit; substitute an estimate.
  4. **Signals that create cascades.** Examples: a false stall from a vented PS3 line leading to a sub-idle rollback; nozzle opening from a high P-sensor; a trapped-inlet-pressure drift through a climb.
- [ASSUMPTION] **Recorded-texture rules after accommodation:**
  - the raw channel keeps its failure shape (stuck, ramp, wrap, 0 or full scale, intermittent) if it is still recorded;
  - the selected or "used" channel switches to a synthesised value with *lower* noise (model output) and model bias that grows in transients;
  - the fault word and caution latch at detection time;
  - a reversionary mode shows lower idle N2 at altitude and slower acceleration.
- [ASSUMPTION] **For the IN20's dual-channel FADEC**, validate the thresholds against GE/HAL data if available. Otherwise keep them as declared parameters with the DEEC/ADIA values as priors and sweep them in validation runs.

### Gaps
- F404-IN20 (and F404-102, F414, RM12) FADEC thresholds, persistence counts, fault-code dictionary, channel-change logic and synthesis models: none of these is public.
- The DEEC pressure range-check "specified number of cycles" is not given.
- Tejas DFCC and USMS redundancy-management thresholds are not public.

---

## Q4. Other thin sensor classes: oil pressure and temperature, vibration pickups and proximity probes, current and voltage sensing, hydraulic pressure, brake temperature and tyre pressure

### Takeaway
None of these sensor classes has a public fighter-specific datasheet. Officially released specifications and US/European programme reports still bound them.

**Oil-pressure transmitters**
- Legacy accuracy is ±1.5–2.0 psi; extremes, seasoning and endurance widen it to ±2.5–4.0 psi.
- Damping corresponds to τ ≈ 1 s (MIL-PRF-25435D) to ≈ 4 s with cold, viscous oil (MIL-T-5796D).
- Modern transmitters reach ±0.25 % FS with 10 ms response.
- In the USN F404 fleet the oil-pressure *transmitter* was the single largest in-flight shutdown cause (already known). The failure-mode weight therefore leans toward false-low indications, not real lube loss.

**Engine vibration**
- The EJ200, the closest modern analogue, uses two casing accelerometers conditioned to velocity, with a 500 ms processing cycle.
- Each monitored quantity is kept per speed band:
  - 1/rev amplitudes for NL and NH;
  - a programmable order;
  - broadband RMS;
  - "residual vibration energy".
- Each is compared against absolute and datum-relative limits, with separate transient and steady-state logic.
- Documented signatures:

  | Event | Signature |
  |---|---|
  | HPT blade-tip loss | Rear NH 1/rev 26 → 37 mm/s (+40 %) |
  | Rotor-bow start | Up to 55 mm/s RMS (≈ 20× normal) |
  | Surge | 95 mm/s peak-to-peak |
  | Airbrake buffet | 35 Hz tone |

- No proximity-probe use in flight was found; proximity probes appear to be test-cell only.

**Generator current sensing**
- Current transformers feeding the GCU differential protection are sampled at about 1 µs.
- The main false-trip source is intermittent open CT cables.

**Hydraulic pressure transducers**
- Modern transducers achieve ±0.25 % FS: about ±0.9 bar on a 0–345 bar range around Tejas's 280 bar system.

**Brake temperature (where fitted)**
- Brake temperature uses platinum RTDs with OVHT (> 400 °C) and differential-temperature (±65 °C from the mean) warnings.
- Readings need ≥ 3 h to settle after hard braking.
- No fighter or Tejas brake-temperature system was found.

**Tyre pressure**
- Accuracy is ±2.5 psi (Crane SmartStem; F-16 field trial 2009), against a ±3.5 psi FAA requirement.
- Readings are strongly temperature-biased: +19 % at 200 °F and −23 % at −65 °F, from 70 °F.
- False-low warnings came from leads, connector pins and carbon-dust shunting: 15–20 per 1,000–1,500 landings.

### Cited Findings

**Oil pressure and oil temperature**

*MIL-T-5796D, Tables I–II, §4.7.2* — [everyspec](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-T/MIL-T-5796D_40475/) [TRANSFER: USAF legacy 0–100 psi oil-pressure transmitter (MS28005), Dist A]

| Condition or property | Value |
|---|---|
| Scale error at room temperature | ±1.5 psi (0–30 psi); ±2.0 psi (40–100 psi) |
| After vibration or overpressure | ±2.0–3.0 psi |
| At temperature extremes, seasoning, endurance | ±2.5–4.0 psi |
| Friction | 2 psi (3 psi cold) |
| Pointer oscillation under vibration | 2 psi |
| Damping (100 → 10 psi, ~2,500 cSt oil at −65 °F) | 9 ± 3 s ([DERIVED] τ ≈ 3.9 s) |

*MIL-PRF-25435D, §§3.4.5–3.6.5, Table I* — [everyspec](https://everyspec.com/MIL-PRF/MIL-PRF-010000-29999/MIL-PRF-25435D_15720/) [TRANSFER: general aircraft pressure-transmitter performance spec, 2008, Dist A]

| Property | Value |
|---|---|
| Operating temperature | −65 to 330 °F |
| Vibration | 30 g sine, 5–2,000 Hz |
| Damping (full scale → 14 %) | 2 ± 1 s ([DERIVED] τ ≈ 1 s) |
| Overpressure | 100 % for 10 min |
| Cycle life | 10,000 cycles to 80 % FS |
| Accuracy | Left to the contract |

*Modern thin-film transducer* — [FCI AS-PT product page](https://www.fluidcomponents.com/aerospace/aerospace-products/pressure-sensors/as-pt) [TRANSFER: vendor; intended for lube oil, fuel and hydraulics]

| Property | Value |
|---|---|
| Accuracy | ±0.25 % FS (BFSL) at 25 °C, with a total error band over −55 to +125 °C |
| Response | 10 ms to 63 % |
| Stability | 0.1 % FS per year |

*F404 engine-mounted sensor environment* — [NASA CR-191195 §4.1.3, p.10](https://ntrs.nasa.gov/citations/19940032893) [DIRECT: F404-400]
- Qualification vibration: 20 g at 100–2,000 Hz, 50 g to 4 kHz, 160 g to 10 kHz.
- A thermal-cycling failure gave a "low signal level".

*Transducer technology* — [AGARD-AG-160 Vol.11, §§4.5.3, 4.5.5, 4.7.5](http://spaceagecontrol.com/AD-PressureAndFlowMeasurement.pdf) (local `sensor_texture/agard_ag160_v11_pressure_flow.txt`) [TRANSFER]
- Variable-reluctance transducers: "excellent dynamic response… extreme over pressure tolerance".
- Strain-gauge transducers: adhesive creep and limited long-term stability.
- Capacitive transducers: temperature effects "difficult to compensate".

*F-16 HYD/OIL PRESS caution* — [USAF AIB F-16CM 92-3881, PDF pp.24–25](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf) [TRANSFER: F-16]
- One light combines both systems.
- Engine-oil low pressure must persist 30 s, to suppress manoeuvre transients.

*Gap:* no fighter oil-temperature sensor specification, and no explanation of *why* the F404 oil-pressure transmitter dominated IFSDs.

**Engine vibration**

*EJ200 engine monitoring unit* — [MTU, RTO-MP-079(I) paper 7 (DTIC ADP014124), pp.7-2 to 7-12](https://archive.org/details/DTIC_ADP014124) [TRANSFER: EJ200/Typhoon, closest modern fighter analogue]

- Sensors and acquisition:

  | Item | Value |
  |---|---|
  | Accelerometers | Two casing units: front at 90°, rear at 198°; rotor dynamics < 1 kHz |
  | Conditioning | Velocity in the EMU |
  | Processing cycle | 500 ms (204.8 ms acquisition + 295.2 ms processing) |
  | Samples per set | 512 ([DERIVED] ≈ 2.5 kHz) |

- Parameters:
  - 1EO NL and 1EO NH by DFT over 10 NL revolutions;
  - a programmable order;
  - broadband RMS;
  - residual vibration energy = RMS minus the tracked orders.
- Data handling:
  - 100 NL speed bands (SB0 < 30 % NL … SB99 > 103 %), with acceleration and deceleration stored separately;
  - Datum, Max-Per-Run, Max Amplitude and Time-History stores;
  - incident pre/post histories;
  - special-study data at 2 Hz.
- Limits:
  - absolute cockpit limit;
  - lower absolute maintenance limit;
  - relative limit versus the engine's datum.
  - Each limit is split into transient and steady-state by duration, and classed by manoeuvre (normal versus high-g or gyroscopic load).
- Transducer and conditioning health are flagged.
- Observed signatures:

  | Event | Observation |
  |---|---|
  | HPT blade-tip loss | 1EO NH rear 26 → 37 mm/s |
  | Rotor-bow start | ≤ 55 mm/s RMS |
  | Surge | 95 mm/s peak-to-peak (3 events in < 1 s) |
  | Airbrake buffet | 35 Hz tone independent of rotor speed |

*RM12* — Meggitt (Vibro-Meter) supplies the RM12 vibration monitoring system. [TRANSFER: F404-derived; secondary source] Local file `engine_data/rm12/forecastintl_archived_rm12.pdf`.

*Pickup choice* — [Aviation Pros, "Fan trim balance"](https://www.aviationpros.com/home/article/10388975/fan-trim-balance) [TRANSFER: trade article]
- Velocity pickups suit fan trim balance; accelerometers suit higher frequencies.
- High-temperature accelerometers may need an external charge amplifier.
- Example sensitivity: 20 mV/ips.

*Already known* (`f404_in20_engine_model.md` Q8):
- F404 test-cell limits and levels (DSTO-TN-0530).
- One mid-frame accelerometer in flight.
- USN charge-amplifier saturation and false warnings in the absence of a > 10 kHz filter.

**Current and voltage**

*Generator differential protection* — [Vanderbilt PHM 2009](https://cs.vuse.vanderbilt.edu/koutsoxd/www/Publications/phmc_09_46.pdf) [TRANSFER]
- Current transformers are "sampled at a high rate (typically 1 µs)".
- Difference currents also arise from CT saturation, phase error and noise, so adaptive thresholds are used.
- Intermittent open CT cables are "one of the frequent types of faults" and cause false winding-fault trips.

*NASA ADAPT electrical testbed* — [ntrs 20110011109](https://ntrs.nasa.gov/citations/20110011109) [TRANSFER]
- Sensors sampled at 2 Hz.
- "Stuck" faults have zero noise; "offset" faults keep the original noise.
- Nominal data show spikes, non-Gaussian noise and large current transients at load switch-on.

*MIL-STD-704F power-quality limits* — [everyspec, Table I p.18, DC limits p.19](https://everyspec.com/MIL-STD/MIL-STD-0700-0799/download.php?spec=MIL-STD-704F.027323.pdf) [TRANSFER: US MIL power-quality standard; usable as validity and caution thresholds]

| Bus | Limits |
|---|---|
| AC 400 Hz | 108–118 V rms; 393–407 Hz; distortion factor ≤ 0.05; voltage modulation ≤ 2.5 V; frequency modulation 4 Hz |
| 28 VDC | 22–29 V; ripple ≤ 1.5 V |
| 270 VDC | 250–280 V; ripple ≤ 6.0 V |

*HAL battery display unit* — [DDP node 10096](https://www.ddpmod.gov.in/node/10096) [DIRECT-by-nomenclature]
- Integrates battery current to show Ah: full 45 Ah; charging ≤ 50 A; low warning at 30 Ah.

**Hydraulic pressure**
- [TRANSFER] Use the MIL-PRF-25435D and FCI AS-PT figures above. [DERIVED] On a 0–5,000 psi transducer, ±0.25 % FS is ±12.5 psi ≈ ±0.86 bar.
- Failure behaviour (lead breakage without strain relief, connector pin damage) is taken from the tyre-pressure service evaluations below.

**Brake temperature** — [FAA DOT/FAA/CT-82/90 (DTIC ADA127220), pp.3–4, ~36–37](https://archive.org/details/DTIC_ADA127220) [TRANSFER: DC-10 brake temperature monitoring]
- Platinum-wire RTD in a metal bulb in the brake (in use since 1973), read with a multiplexed 5 mA source.
- OVHT warning at > 400 °C; DIFF TEMP warning at ±65 °C from the all-brake mean (dragging or inoperative brake).
- Temperatures need ≥ 3 h to stabilise after hard braking.
- Already known: the Mortimore CEAS 2007 note that the probe sits in a gap and lags.

**Tyre pressure**

*FAA service evaluations* — [ADA127220](https://archive.org/details/DTIC_ADA127220); [ADA081598](https://archive.org/details/DTIC_ADA081598); [ADA065513](https://archive.org/details/DTIC_ADA065513) [TRANSFER: transport tyre-pressure systems]
- Accuracy:
  - requirement ±3.5 psi;
  - transducer plus wheel electronics ±4 psi at 150 psi and ±6 psi at 200 psi;
  - reads low when cold and high when hot: 180 psig at 70 °F became 214 psig at 200 °F and 139 psig at −65 °F.
- False-low warnings:
  - 20 per 1,000 landings / 4,000 h, and 15 per 1,500 landings / 5,000 h;
  - causes: transducer tolerance, broken leads, bent pins, and carbon dust shunting the transducer.
- Alarm logic:
  - axle-mate thresholds of 30 psi or 15 % gave nuisance alarms during brake-heat soak; 20 % was recommended;
  - warnings freeze above 60 kt.

*Crane SmartStem* [TRANSFER: vendor; F-16 field evaluation]
- "Accurate to within +/- 2.5 PSI between -20 to +125C"; passive, no battery, logs pressure and temperature — [Crane product page](https://craneae.com/Products/Sensing/SmartStemBizJets.aspx).
- The USAF AATC fitted 3 F-16s in 2009 for about 10 months — [Aviation Pros press release](https://www.aviationpros.com/home/press-release/10398019/aatc-begins-f-16-field-service-evaluation-of-smartstem).

*Already known:*
- FAA AC 20-97B: 1 % per 5 °F.
- Michelin pressure bands, detailed in Q8:

  | Pressure (% of nominal) | Action |
  |---|---|
  | 95–99 % | Re-inflate |
  | 90–94 % | Inspect |
  | < 90 % | Remove |

### Inferences
- [ASSUMPTION] **Oil pressure (psid, 1 Hz on the bus)**
  - Static error ±0.5–1 % FS, with a legacy bound of ±2 psi.
  - τ ≈ 0.5–1 s, rising to ≈ 4 s for cold, viscous oil at start.
  - Thermal zero shift ≈ 0.02 % FS/°F (vendor snippet only).
  - Failure-mode prior weighted to false-low: sense-line or connector leak, harness intermittent, drift. Add stuck and noisy modes, and keep real lube faults rarer than transmitter faults, matching the USN F404 IFSD data.
  - The caution needs a ≈ 30 s persistence.
- [ASSUMPTION] **Oil temperature**: Pt RTD with τ of several seconds (no fighter source).
- [ASSUMPTION] **Vibration channel**
  - Per speed band: tracked 1/rev with a per-engine datum.
  - Relative alarm at about 1.5–2× datum; absolute limits as in DSTO-TN-0530.
  - Gate by g and yaw rate, plus a 35 Hz airbrake-buffet tone.
  - Failure modes: open circuit (flat-line plus status flag); charge-amplifier saturation from > 10 kHz content (biased RMS); cable intermittent (spikes).
- [ASSUMPTION] **Electrical**
  - Bus voltage and current sensed at ±1–2 % FS.
  - Ripple and frequency modulation are physically generated, with MIL-STD-704F limits as the validity and caution bounds.
  - Faults: CT intermittents produce false differential trips; a stuck sensor has zero noise, while an offset sensor keeps its noise.
- [ASSUMPTION] **Tyre pressure** (ground-read on the Tejas, 245 psi main)
  - ±2.5 psi (±1 %).
  - Gas-law temperature term driven by brake heat, with a cool-down τ of hours.
  - Nuisance-low logic on axle mates (Tejas main wheels are single, so it applies to the nose pair only).
- [ASSUMPTION] **Brake temperature** (if modelled): RTD lagging by minutes. Otherwise treat heat-sink temperature as a not-measured state, as already in `not_measured_states.csv`.

### Gaps
- No fighter oil-temperature sensor specification.
- No F100, F110, F119 or RM12 vibration alarm limits in ips.
- No Hall-effect or shunt current-sensor accuracy for fighter GCUs.
- No Tejas brake-temperature or tyre-pressure system evidence.
- No fighter hydraulic-pressure caution set-point in psi or bar: the 2025 F-16 AIB states only "specified minimum operating pressure".
- Proximity probes: no evidence of in-flight use on fighter engines.

---

## Q5. Empirical scatter of military engine-health snapshots: take-off indices, test-cell repeatability, new-engine spread, and sensor vs real engine variation

### Takeaway
The evidence separates scatter into three layers [TRANSFER unless noted]:
1. **Measurement and facility** (sensor plus data system):
   - about ±0.1–0.3 % back-to-back on the same engine in one test cell;
   - about ±0.3–0.5 % run-to-run;
   - 0.5–3.5 % across facilities, with fuel flow and thrust the worst channels;
   - in flight, the 1980s F/A-18 data converter (MSDC) dominated the error budget (already known).
2. **Real engine-to-engine and build-to-build variation**:
   - about ±1 % in efficiency, flow and fuel flow after a within-tolerance rebuild (NRC T56);
   - F404-400 serviceable engines scatter about ±5 % in corrected thrust at fixed corrected N2, mostly from variable-geometry rigging. Applying VG corrections cuts scatter 2–3×.
3. **Fleet acceptance and condition**: NAVAIR's F404 test-cell acceptance window is ±1 % on speeds, temperatures, pressures, fuel flow and thrust, and ±3° on guide vanes.

The CF-18 take-off Kalman-band scatter of ±0.8–2 % (already known) therefore sits between pure measurement noise (≈ 0.1–0.5 %) and fleet-wide engine spread (≈ 1–5 %). It mixes take-off transient repeatability (±1 % with a cooled engine and throttle rate ≥ 45°/s) with residual VG and ambient effects.

### Cited Findings
- **Same J57 engines in 8 facilities.** [TRANSFER: turbojet; isolates facility and measurement scatter] — [AGARD-AR-248, §18, Table 18-1 (DTIC ADA218764)](https://archive.org/details/DTIC_ADA218764)
  - Altitude cells: about 90 % of points within ±1 % of the mean curve for 4 of 6 parameter sets. Fuel flow reached only 63 % and thrust 69 % (85 % and 92 % once one outlier facility was removed).
  - Mid-thrust spreads across altitude cells: speed ratio 0.4–0.8 %; T7/T2 0.6–2.0 %; airflow 1.3–3.6 %; thrust vs P7/P2 3.4–5.4 %; SFC 0.9–2.4 %.
  - Sea-level cells: speed 0.5 %; airflow 1.9 %; fuel flow 3.5 % (1.8 % without the outlier); thrust 0.7 %; SFC 1.8 %.
  - NRC Canada cell repeatability 0.1–0.3 %. Cycle re-match over time contributes 0.3 %; fuel properties ±1.0 % RSS.
- **Bias vs precision budget.** [TRANSFER] — [AGARDograph 307 (DTIC ADA219033)](https://archive.org/details/DTIC_ADA219033)

  | Parameter | Bias | Precision | Uncertainty |
  |---|---|---|---|
  | NH | 0.22 % | 0.09 % | 0.40 % |
  | T7/T2 | 0.53 % | 0.19 % | 0.91 % |
  | P7/P2 | 0.13 % | 0.06 % | 0.25 % |

  Net thrust uncertainty is ±0.5–1.2 %, rising above ±3 % at 20.7 kPa inlet pressure.
- **Test-cell repeatability vs a real rebuild (NRC T56, compressor rebuilt twice).** [TRANSFER: turboprop; separates measurement from real build-to-build change] — [AGARD-CP-448 Paper 26, pp.26-4 to 26-6 (DTIC ADA203800)](https://archive.org/details/DTIC_ADA203800)
  - Back-to-back: ±0.02–0.11 % for efficiencies and flows; ±0.28–0.49 % for power and SFC.
  - Run-to-run: ±0.15–0.24 % for efficiency and airflow; ±0.41 % for fuel flow. Combined worst case about ±0.5 % (RSS about ±0.33 %).
  - A rebuild within tolerance moved:
    - compressor efficiency +1.2 % then −0.84 %;
    - pressure ratio ±1.3 %;
    - fuel flow +0.73 % then −1.4 %;
    - combustor pressure ratio −1.0 % then +0.52 %.
  - Real engine scatter is therefore about ±1 %, against about ±0.3 % from measurement.
- **CF-18 F404-400 serviceable-engine scatter.** [TRANSFER: F404-400 → IN20; IN20 VG rigging tolerances unknown] — [Muir, Rudnitski & Cue, AGARD-CP-448 Paper 7, Fig. 14 and pp.7-3 to 7-5, graph-read](https://archive.org/details/DTIC_ADA203800)
  - Corrected thrust at fixed corrected N2 scatters about ±5 %; HPC variable-geometry (CVG) position about ±3–4°.
  - Most of the scatter comes from VG set-up tolerance; VG corrections cut it 2–3× (already known).
  - Eight engines run every 25 FH for 18 months were "quite repeatable", with step shifts at maintenance actions and VG re-rigging.
  - One engine's N2 signal noise made it count partial LCF cycles up to 8× faster than its twin (p.7-3). This is a sensor-texture effect on life usage.
- **F404 acceptance window.** [TRANSFER: F404-400/402 USN hush-house] ±1 % on speeds, temperatures, pressures, fuel flow and thrust; ±3° on guide vanes; 4–5 min stabilisation — [NAWCADPAX/TR-2010/22E (DTIC ADA517278), local `engine_data/f404_monitoring/DTIC_ADA517278.pdf`](https://archive.org/details/DTIC_ADA517278).
- **F404 left/right engines on HARV.** [TRANSFER: F404-400 flight] Zero-bleed thrust differed by +3.8 % (92 % N2), +1.0 % (MIL) and +7.0 % (max AB), confounded by 7–11 °R ambient differences between runs — [NASA TM-104247, Table 2, p.10; local `engine_data/f404_f414_cycle/NTRS_19920020182.pdf`](https://ntrs.nasa.gov/citations/19920020182).
- **In-flight 15-s snapshot scatter.** [TRANSFER: T55 turboshaft, RAAF Chinook] P3 coefficient of variation 1.1 %; T5 0.4 %; torque 1.3 % after outlier rejection (8.3 % before, because of aperiodic dropouts). Transducer repeatability: ±0.1 % for pressures and speeds, ±0.25 % for fuel flow — [AGARD-CP-448 Paper 25, Table 2, pp.25-5 to 25-6](https://archive.org/details/DTIC_ADA203800).
- **F100 stall-margin audit.** [TRANSFER: F100 EMD on F-15 HIDEC] The ±2σ band from engine-to-engine variation plus control tolerance spans about 0.18 in fan pressure ratio, against about 0.5 FPR between operating point and stall. The predicted stall point was within < 1 % of the actual one — [NASA TM-100431, Fig. 14 p.9, pp.2–4; local `engine_data/f100/19880011775.pdf`](https://ntrs.nasa.gov/citations/19880011775).
- **Already known [DIRECT/TRANSFER: F404-400]:**
  - CF-18 take-off Kalman-band shifts of +2–5 % against ±0.8–2 % scatter.
  - Transient data repeat within ±1 % at throttle rates ≥ 45°/s with a cooled engine.
  - Starting-speed σ is 4 % (fan) and 2 % (core).
  - IECMS vs test-cell agreement: fuel flow ±2 %, N1/N2 ±0.5 %.
  - Sources: Henry and Forsyth, in `addendum_engine_F404_F414_monitoring.md`.
- **Already measured [MEASURED: DASHlink airliner engines]:** persistent per-engine offsets of N2 ±0.4 %, EGT −7 to +5 °C and FF −4 to +3.5 %, with flight-to-flight AR(1) jitter (`empirical_dashlink_texture.md` Q5). These match the 0.3–0.5 % "installation and sensor bias" layer.

### Inferences
- [ASSUMPTION] **Snapshot model for a Tejas fleet**: y = true engine state + per-engine build offset + per-tail installation/sensor bias + per-snapshot noise. The layers are:

  | Layer | Size | Basis |
  |---|---|---|
  | Per-snapshot noise | σ ≈ 0.1–0.2 % (pressures, speeds); 0.25–0.4 % (fuel flow); ≈ 0.5–1 K (T5) | Transducer repeatability, MSDC-era 2σ |
  | Per-tail installation/sensor bias | ≈ 0.3–0.5 % | DASHlink offsets; facility bias |
  | Per-engine build offset at delivery | ≈ ±1 % in efficiency and flow, inside the ±1 % acceptance window | NRC rebuild; NAVAIR window |
  | VG rigging offset | ±2–3° | Behind the ±5 % thrust-at-N2 spread when uncorrected; redrawn at every VG rig or maintenance event |

  - Take-off transient indices add ±1 % repeatability noise, conditional on a cooled engine and a fast throttle.
  - Validate with HAL F404-IN20 pass-off data and the first months of ECMS take-off records.
- [ASSUMPTION] **Who sees what:** a PHM model sees mostly measurement noise when trending one engine, but mostly real build spread when comparing engines across the fleet. Evaluate scenario generators on both within-tail trend detection and cross-fleet ranking.

### Gaps
- No F404-IN20 production-spread data (EGT/T5 margin at MIL, N2 at MIL, thrust) and no Tejas ECMS snapshot statistics.
- No F110/F100 USAF CEMS fleet snapshot scatter was retrieved.
- Volponi and Doel (TEMPER) military examples remain unread.

---

## Q6. Fighter engine fault signatures with traces or quantified shifts: stall/surge, AB light-off failure and blowout, nozzle faults, hung/hot starts, flameout and relight, inlet distortion, FOD, VG mis-rigging, fuel-control faults

### Takeaway
Officially released fighter traces now cover most engine fault classes. Each class has a characteristic channel ordering:

- **Self-recovering (pop) stall from inlet distortion** [TRANSFER: F404-400 on F/A-18].
  - PS3 collapses from about 85 to about 10–15 psia within one sample.
  - It recovers to about 75 psia in ≤ 0.3 s and to baseline in about 3 s, with no pilot action.
  - Stalls cluster at AoA > 70° with high yaw rate.
- **Mechanical stall leading to stagnation** (blade loss, turned or reversed vanes) [TRANSFER: F110/F100].
  - N1 and N2 fall while FTIT *rises*.
  - A stall code appears about 2 s after onset; overtemperature, mode-transfer and sensor-fail codes follow over about 10 s; then a flameout or sub-idle code.
  - Generator drop-off and the EPU follow.
- **Bird damage with stall cycling** [TRANSFER: F100]: repeated stalls every 3–5 s, while the engine still delivers about 96 % thrust under stall-recovery and fan-damage logic.
- **Augmentor faults** [TRANSFER: F100 DEEC].
  - A no-light is declared if no light is detected 2.5 s after the request, followed by up to 3 retries.
  - A rumble blowout shows a 60 Hz, 2 psi peak-to-peak PAB oscillation just before the blowout.
  - Quickfill-spike stalls occurred once in 994 segment-1 lights.
  - A nozzle EPR-loop limit cycle (1–2 Hz, ±0.2 ft²) causes alternate stalls and blowouts.
- **Fuel shut-off and fuel-starvation faults** [TRANSFER: F110/F-16].
  - A partly closed main fuel shut-off valve held the engine at 70 % RPM, sub-idle, for about 3 min with no throttle response and no caution.
  - It then rolled back to about 20 %.
- **Hung relight** [TRANSFER: F100/F-16 recorder trace]: N2 flat at about 35 % while FTIT climbs about 12 °C/s.
- **Main fuel control over-fuelling** [TRANSFER: F404-400]: the take-off fuel-ratio index (Wf/PS3) runs about 13 points high, ahead of a flameout.
- **HPC damage on the F404** [TRANSFER: F404-400].
  - The damaged engine's take-off PS3 rise lags its twin by 1.5–2 s and plateaus about 4 points low.
  - Corrected-parameter shifts of +8 % PS3/P1 and +8–14 % Wf at fixed N2 (already known).
- **Bleed extraction** [TRANSFER: F404-400]: measured thrust loss is about 2–3 % per lb/s, linear in bleed.
- **Gaps:** there is still no public trace of an F404 or IN20 failed-open/failed-closed nozzle, or of an F404 hot or hung start.

### Cited Findings

**Compressor stall and surge**

*Pop stalls in F/A-18 departures* [TRANSFER: F404-400 on F/A-18A] — [NASA TM-104328 (1997), pp.3–4, Fig. 5 p.17, p.29, graph-read](https://ntrs.nasa.gov/api/citations/19970012654/downloads/19970012654.pdf)
- Test conditions: 35,000 ft, M 0.3, MIL power; 12 departures with entry yaw rates of 41–91 °/s.
- Stall statistics:
  - 5 of 12 departures stalled, 16 stalls in total (15 on the right engine, up to 10 in one departure);
  - stalls occurred only at AoA > 70°;
  - peak time-variant distortion was circumferential 0.22–0.25 and tip radial 0.10–0.12, exceeding the F404-400 design limits.
- Behaviour: all stalls started in the compressor and recovered without pilot action.
- Channel histories:
  - PS3 about 85 → 10–15 psia in about one sample; about 75 psia within ≤ 0.3 s; baseline within about 3 s;
  - fan discharge about 15 → 5 psia;
  - inlet total pressure spiked about 4 → 7–8 psia (reverse-flow pulse).
- Stalls correlated with the combined rate of aircraft motion, not with attitude.
- **Contrast:** a Gripen RM12 in an extreme inflow event showed "no recorded engine malfunction" with AB lit — [SHK RM 2002:02, p.17](https://shk.se/download/18.2d6f089b18faca29dc815d93/1698926519672/rm2002_02.pdf).
- Already known (TM-1999-206572): HARV surges recover within about 0.2 s, and stalls within 2.4 s of a previous stall are "non-isolated".

*F110-GE-100 fan-blade liberation, F-16C 88-0433 (UTTR, 4 May 2012)* [TRANSFER: F110] — [USAF AIB, pp.4–5, verified on page images (local `engine_faults/usaf_aib_execsum_2000_2013/FULL_2012_F-16C_88-0433_UTTR_4May12.pdf`); exec summary via Wayback](http://usaf.aib.law.af.mil/ExecSum2012/F-16C%2C%20UTTR%2C%204%20May%2012.pdf)
- Flight condition: 9,780 ft MSL, 301 KIAS.

  | Time (local) | Elapsed | Event |
  |---|---|---|
  | 08:27:55 | 0 s | N1 and N2 begin to drop with no throttle change |
  | 08:27:57 | +2 s | ENG 020 MFL COMPRESSOR STALL. Fan speed falls **95 % → 15 % in 0.6 s**; core falls from about 96 % to sub-idle; **FTIT starts increasing** |
  | 08:27:59 | +4 s | ENG 009 T4B OVERTEMP, ENG 017 PFL ENG MACH FAIL, ENG 023 HYBRID MODE XFER |
  | 08:28:05 | +10 s | ENG 068 T4B TEMP SIGNAL FAIL (a secondary sensor failure) |
  | 08:28:08 | +13 s | ENG 058 FLAMEOUT SUB-IDLE |
  | about +16 / +19 s | | Main generator fail; EPU running |

- Restarts were attempted in SEC and PRI modes and with the JFS. The pilot ejected after about 90 s of failed restarts.

*F110-GE-100 stage-5 stator sector installed 180° reversed, F-16CM 90-0771 (Osan, 21 Mar 2012)* [TRANSFER] — [USAF AIB, PDF pp.7, 11, 13, 26 (local `FULL_2012_F-16CM_90-0771_Osan_21Mar12.pdf`); exec summary](http://usaf.aib.law.af.mil/ExecSum2012/F-16CM%2C%20Osan%20AB%2C%2021%20Mar%2012.pdf)
- The pressure pulse caused high-cycle fatigue, and blades failed after **40.9 h / 30 sorties** since installation. The stall then liberated 27 blades in stages 6–9.
- The pilot perceived RPM and FTIT falling, but the recorder showed FTIT rising quickly (a perception-vs-record conflict).
- Ejection came 5 min 42 s after the stall.

*F100-PW-220 turned 5th-stage variable vane, F-16C 87-0358 (Holloman, 30 Apr 2024)* [TRANSFER] — [USAF AIB, pp.4–5, 11–14 (local `engine_faults/AIB_F-16_Holloman_30Apr2024.pdf`)](https://www.afjag.af.mil/Portals/77/1.%2030Apr2024%20AETC%20F-16%20Holloman%20AIB%20Report%20final.pdf)
- Vane No. 10 sat about 25° more open than its neighbours, causing high-cycle fatigue and a blade separation.
- The CSMU logged a stall at 11:43:09 and stagnation at 11:43:10; RPM was below 60 % within 5 s. This was 16 s after an AB→MIL selection, at 1,030 ft AGL and 329 KCAS.
- Pratt & Whitney recorded 6 turned-HPC-vane events in 20 years; the 5th stage cannot be borescoped.

*Other USAF AIB executive summaries, 2000–2013 (via Wayback)* [TRANSFER: F100/F110] — local copies in `engine_faults/usaf_aib_execsum_2000_2013/`
- **F-16CG 89-2094 (16 Feb 2000), RCIGV fracture:** stall leading to stagnation; 3 hot or hung airstarts; selecting SEC over-temped the HPT ([ExecSum2000](http://usaf.aib.law.af.mil/ExecSum2000/F-16CG_GoldwaterRange_16Feb00.pdf)).
- **F110 No. 4 bearing failure (F-16CG 89-2115, 30 Mar 2006):** stall cleared, but vibration remained at all power settings, with extreme vibration and repeat stalls above about 85 % RPM. Thrust was insufficient for level flight ([ExecSum2006](http://usaf.aib.law.af.mil/ExecSum2006/F-16__30March06.pdf)).
- **The same failure on 89-2050 (18 Jul 2001):** "decreasing RPM with rising FTIT"; 10 failed airstarts ([ExecSum2001](http://usaf.aib.law.af.mil/ExecSum2001/F-16CG_SE-Turkey_18Jul01.pdf)).
- **F-15E 91-0308 (12 Feb 2002):** take-off stall with immediate stagnation and fire, with the engine in secondary mode, reduced stall margin and high fuel flow ([ExecSum2002](http://usaf.aib.law.af.mil/ExecSum2002/F-15E_Lakenheath_12Feb02.pdf)).
- **Mix of about 35 engine-involved F-16 Class A events** (from about 122 summaries, an incomplete sample):

  | Cause | Share |
  |---|---|
  | Turbine blade, post or seal | ~26 % |
  | Bird, FOD or domestic object damage | ~17 % |
  | Fuel system or starvation | ~14 % |
  | Fan/compressor rotor or stator | ~11 % |
  | Bearings | ~11 % |
  | Fire, cause unspecified | ~9 % |

- **Timing examples:**
  - LPT air-seal failure to seizure in about 30 s (F-16DG 88-0167, 2001);
  - a cracked HPT blade gave no detectable precursor in the 3 months before failure (F-16CJ 92-3919, 2002).

*Bird ingestion with stall cycling, F-16D 88-0165 (F100-PW-220, Luke, 26 Jun 2013)* [TRANSFER] — [USAF AIB, pp.7–8 (local `FULL_2013_F-16D_Luke_26Jun13.pdf`)](http://usaf.aib.law.af.mil/ExecSum2013/F-16D%2C%20Luke%20AFB%2C%20AZ%2C%2026%20Jun%2013.pdf)
- About 3 birds were ingested. Sequence: a 1–2 s buzz, then a pop, then **stalls every 3–5 s**.
- The engine kept giving near-full MIL (about 96 %) for at least 2 min 30 s; the unmanned aircraft climbed to about 6,000 ft AGL after ejection.
- Two logics shaped this:
  - stall-recovery logic returns the engine to commanded power, which can re-stall it;
  - **Fan Damage Detection Logic** holds the highest non-stalling power after repeated stalls.
- Caveat: this description partly paraphrases flight-manual material quoted in the public AIB.

*Stall-margin audit and event rates* [TRANSFER: F100]
- HIDEC/ADECS used 11–13 % excess stall margin, keeping 4 % for uncertainty. One non-recoverable stall occurred at 52,000 ft and 175 kt — [NASA TM-100431](https://ntrs.nasa.gov/citations/19880011775); [NASA TM-85914](https://ntrs.nasa.gov/citations/19840025344).
- Stall-stagnations per 1,000 flight hours: F100(3) 0.2–1; F110-GE-100 0; F100-PW-220 0–0.05 — [RAND N-3618, Table 4.2 (DTIC ADA282467), local `engine_data/f110_usaf/dtic_ADA282467.pdf`](https://www.rand.org/pubs/notes/N3618.html).
- F100 Engine Diagnostic System trial: 21 stalls (11 on one engine), 2 hot starts and 2 AB blowout/mislight events in about 3,300 engine operating hours — [NASA CP-2190, pp.225–235](https://ntrs.nasa.gov/citations/19810022668). The full event table is in Q9.

**Afterburner faults** [TRANSFER: F100 DEEC; the F404-402 light-off times are already known]
- **Light-off timing and retries** — [NASA TM-86745, pp.4–6](https://ntrs.nasa.gov/citations/19880014421)
  - Normal light 0.4–0.6 s after the segment request; full sequencing 4.2–4.4 s; pressure pulses ≤ 4 kN/m² (< 6 %).
  - **No-light** is declared if the light-off detector sees nothing within **2.5 s**. The AB reverts to intermediate, the detector self-tests, and the light is retried up to 3 times. In one example the retries came at t = 6.1, 10.9 and 20.5 s, and the transient took > 30 s.
- **Quickfill stalls** — [NASA CP-2298 Paper 11, pp.182–184](https://ntrs.nasa.gov/citations/19860015882)
  - A quickfill pressure spike to about 300 psi sends excess fuel into the augmentor. The pressure pulse travels upstream and stalls the fan.
  - Stalls were mostly on segment 2; **one segment-1 quickfill stall occurred in 994 augmentor lights**.
- **Rumble blowout** — same paper
  - Just before a blowout at 45,000 ft and 175 kt, PAB sampled at 200/s showed "a discrete 60 Hz oscillation … 2 lb/in² peak to peak". It appeared as segment 4 reached full flow.
  - Rumble was detected in at least 8 idle-to-max transients in the upper-left corner of the envelope.
  - Segment 3→4 transfers caused PAB jumps and rapid nozzle opening, then blowout.
  - "Early augmentor permission" (lighting at 80 % fan speed) caused further blowouts.
- **Rumble band.** Typically 30–200 Hz; rig modes at 45 and 60 Hz (±10 Hz) and 140–165 Hz; 75 Hz at sea level static — [AFAPL-TR-78-82 (DTIC ADA065144)](https://archive.org/details/DTIC_ADA065144).
- **Blowout detection logic.** DEEC detects blowout from ΔEPR, ΔAJ or loss of the UV light-off detector, and shuts off AB fuel quickly "thus avoiding any relight stalls" — [CP-2298 Papers 3, 12](https://ntrs.nasa.gov/citations/19860015883).
- **Throttle stuck in AB.** Fuel starvation followed, with flameout 8 min after sticking (F-16CJ, 12 Mar 2007) — [ExecSum2007](http://usaf.aib.law.af.mil/ExecSum2007/F-16CJ_TonopahTestAirfield_12Mar07.pdf).

**Nozzle actuation and nozzle-loop faults** [TRANSFER: F100 DEEC]
- **EPR-loop nozzle instability** — [NASA CP-2298 Paper 12, pp.201–209](https://ntrs.nasa.gov/citations/19860015883)
  - In the upper-left envelope (45,000 ft, 175–200 kt) the nozzle oscillated at **1–2 Hz (about 1.4 Hz), amplitude up to ±0.2 ft²**.
  - Each peak drove the fan toward stall and each valley drove the augmentor toward blowout. PAB swung up to about ±2.5 psi, with fan-speed oscillation.
  - With segment-1 limiting the amplitude was ±0.1 ft² and it damped out intermittently. It was absent at intermediate power and "very sensitive to conditions".
  - Cause: small, combined differences in engine dynamics. The fix reduced gain 2× and raised the EPR-error deadband 30× (0.001 → 0.03).
  - The instability was predicted by neither analysis, simulation nor AEDC altitude tests.
  - A parallel F100 EMD report shows a 0.4 ft² peak-to-peak, ~1.5 Hz limit cycle building over 4 cycles to a fan stall — [TM-85914, p.4](https://ntrs.nasa.gov/citations/19840025344).
- **Nozzle on flameout.** [TRANSFER: F100-PW-229] The nozzle went from 11 % to about 92 % open within about 3 s of an inadvertent cutoff and stayed about 90 % during relight (graph-read) — [AIB F-16CJ 92-3890, Fig. 1, p.6](https://www.afjag.af.mil/Portals/77/AIB-Reports/2016/160602-ACC-Nellis-F-16CJ-AIB%20Report.pdf).
- **Feedback faults.** DEEC drives the nozzle fully closed on an AJ feedback fault (Q3). F404 FICA kept thrust after nozzle hard-open and hard-closed failures by re-scheduling gas-generator speed (Q3).
- **Nozzle hardware wear.** [TRANSFER: F404-102] Outer-flap cracks appeared at about 25 % of a 330 h accelerated durability test (Q7).

**Fuel-system faults and over-fuelling**
- **Partly closed main fuel shut-off valve, F-16C 92-3886 (F110-GE-129, Misawa, 22 Jul 2012)** [TRANSFER] — [USAF AIB, PDF pp.9–10, 24–25 (local `FULL_2012_F-16C_92-3886_Misawa_MFSOV_22Jul12.pdf`)](http://usaf.aib.law.af.mil/ExecSum2012/F-16C%2C%20Misawa%2C%2022%20Jul%2012.pdf)
  - At FL250 and 310 KCAS the engine stuck at **about 70 % RPM, sub-idle, for about 3 min**. There was no throttle response and no ENGINE light.
  - It then rolled back to **about 20 % RPM** (JFS-assisted) until impact.
  - Flight-manual figures quoted in the AIB (treat as indicative):
    - flameout after a fuel cut in about 6 s at MIL and about 45 s at idle;
    - windmill about 7 % RPM without the JFS;
    - ENGINE light below 60 %;
    - generators drop and the EPU starts below 50 %.
- **Fuel leak.** A leak at the fuel/oil cooler outlet caused a sudden thrust loss at 16,000 ft and a flameout landing (F-16CM 89-2102, 2009) — [ExecSum2009](http://usaf.aib.law.af.mil/ExecSum2009/F-16CM_Aviano_24Mar09.pdf).
- **Main fuel control over-fuelling** [TRANSFER: F404-400] — [AGARD-CP-448 Paper 7, p.7-3, Fig. 3 p.7-9, graph-read](https://archive.org/details/DTIC_ADA203800)
  - Take-off fuel ratio units (Wfm/PS3): a serviceable control reads about 89–92 % at 73–82 % N2, rising to 97–99 % at 87–90 %.
  - A damaged control read about 102–105 % at 79–80 % N2, about 13 points high, and preceded a flameout on start-up.
  - Field monitoring uses the values at 81 % and 87 % N2.

**Starts, flameout, relight**
- **Inadvertent cutoff and relight, F-16CJ 92-3890 (F100-PW-229, Nellis, 2 Jun 2016)** [TRANSFER] — [USAF AIB, Fig. 1, p.6, graph-read (local `engine_faults/AIB_F-16CJ_92-3890_Thunderbird_cutoff_relight_2Jun2016.pdf`)](https://www.afjag.af.mil/Portals/77/AIB-Reports/2016/160602-ACC-Nellis-F-16CJ-AIB%20Report.pdf)
  - Idle before cutoff: N2 about 79 %, N1 about 47 %, FTIT about 530 °C, nozzle about 11 %.
  - Spool-down after cutoff:

    | Time after cutoff | N2 | N1 | FTIT |
    |---|---|---|---|
    | +2 s | — | — | ~455 °C |
    | +3 s | ~60 % | — | — |
    | +4 s | — | ~24 % | — |
    | +5 s | ~50 % | — | — |
    | +10 s | ~40 % | — | — |
    | +13 s | — | ~15 % | — |
    | ~+15 s | ~35 % plateau | — | — |

  - **Relight with N2 flat at about 35 % (JFS on): FTIT climbed about 460 → 640 °C over about 15 s (≈ 12 °C/s), a hung-start signature.**
  - After the third cutoff and relight: N2 31 → 51 % over about 35 s (≈ 0.6 %/s), with FTIT about 520 → 650 °C.
  - EPU on 9 s after the first cutoff; ejection at 50 s.
- **DEEC closed-loop airstarts (F100, F-15)** [TRANSFER] — [CP-2298 Paper 8, pp.128–133](https://ntrs.nasa.gov/citations/19860015879)
  - Logic: fuel is open-loop until light-off is detected by an FTIT rise. Then fuel is modulated to hold a scheduled N2 rate, trimmed back if FTIT exceeds about 760 °C. Minimum fuel 115 kg/h; bleeds open until 56 % N2.
  - Over-fuelling stalls the compressor (hot start); under-fuelling hangs.
  - Example airstarts from a 40 % spooldown:

    | Condition | Timeline | Airstart time | Notes |
    |---|---|---|---|
    | 250 kt, 9,100 m | Light 9 s after pressurisation; idle reached | 55 s | FTIT 450–520 °C |
    | 200 kt, 9,250 m | — | 86 s | FTIT reached 600 °C on the minimum-flow stop |
    | 200 kt, 4,600 m | N2 kept falling for 10 s after light; N2/FTIT/Wf oscillated at t = 50–70 s from slightly high loop gains | 89 s | — |
    | JFS-assisted, 6,100 m, 255 kt | JFS engaged at 25 % N2; motoring at 32 % | 38 s | — |

  - Older F100 EMD logic: 40 % spooldown light at 30 % N2 and 412 °C FTIT, 45 s (vs 62 s with older logic); JFS-assisted 37 s vs 76 s unassisted — [NASA TM-85900, pp.3–5](https://ntrs.nasa.gov/citations/19840021810).
- **FADEC flameout detection.** RM12 FADEC: low T5 plus falling NH sets the flameout code and ignition; the code clears when T5 recovers (Q3). The T-50 F404-102 FADEC auto-relight hung for about 170 s until the flameout-detection schedule was changed (already known).
- **F404 maintenance diagnosis.** Start faults are classed No-Start, Hot or Stall in the RAAF F404 expert system — [ARL-PROP-TM-439 (DTIC ADA227757), local](https://archive.org/details/DTIC_ADA227757) [TRANSFER: F404-400].

**FOD, HPC damage, bleed, VG mis-rig (F404 family)**
- **HPC damage on a CF-18** [TRANSFER: F404-400] — [AGARD-CP-448 Paper 7, Fig. 5 p.7-10, p.7-5, graph-read](https://archive.org/details/DTIC_ADA203800)
  - Before damage, left and right take-off PS3 rises reach 100 % within about 0.5 s of each other at about 4–5 s.
  - After HPC damage, the damaged engine lags about 1.5–2 s and plateaus about 4 points lower (≈ 92 % vs ≈ 96 %). The model match is −5 % HPC efficiency.
  - Already known from the same paper: the CVG mis-rig and HPC-damage cross-plot shifts.
- **Bleed extraction** [TRANSFER: F404-400 on HARV] — [NASA TM-104247, Table 2, p.10](https://ntrs.nasa.gov/citations/19920020182)

  | Power | Left engine (lbf per lb/s) | Right engine (lbf per lb/s) | Engine-model prediction (lbf per lb/s) |
  |---|---|---|---|
  | 92 % N2 | −125 (1.98 %) | −100 (1.64 %) | −89 to −97 |
  | MIL | −177 (2.02 %) | −189 (2.17 %) | ≈ −245 |
  | Max AB | −371 (2.88 %) | −344 (2.85 %) | −421 to −428 |

  - Thrust loss is linear in bleed.
  - **Conflict:** the model under-predicts at part power and over-predicts at MIL and AB.
- **Sensor and harness faults during engine events** [TRANSFER]
  - F100 EDS: 85 FTIT-spread events traced to failed probes Nos. 4 and 5.
  - UTTR 2012: the T4B signal-fail code came 10 s *after* the stall, as a secondary failure.
  - RAAF T55: changing the T5 harness cleared a high health-indicator reading — [AGARD-CP-448 Paper 25](https://archive.org/details/DTIC_ADA203800).

### Inferences
- [ASSUMPTION] **Signature ordering rules for the IN20 generator** (validate against GE/HAL data):
  - (i) Pop stall from distortion: PS3 step down in ≤ 1 sample, 0.2–0.3 s partial recovery, about 3 s full recovery. Triggered when an inlet distortion index (AoA > 60–70°, yaw rate, sideslip) exceeds a margin that shrinks with HPC health. Stall code set; no thrust loss beyond a few seconds.
  - (ii) Mechanical stall leading to stagnation: N1 and N2 decay over 0.6–5 s while T5 rises. Codes cascade over 2–15 s (stall → overtemperature → mode transfer → sensor fail → flameout or sub-idle). Generators drop and the emergency power source comes on. The latent precursor is either absent (turned or reversed vane, ≈ 40 h of high-cycle fatigue) or a slow-growing crack.
  - (iii) FOD with stall cycling: repeated 3–5 s stall–recover cycles with thrust held near the commanded value, until damage logic caps power.
  - (iv) AB faults: no-light after a 2.5 s timeout plus retries; blowout preceded by 30–200 Hz rumble in augmentor pressure; quickfill stalls at about 1 per 1,000 lights at high altitude and low speed; a nozzle-loop limit cycle at 1–2 Hz as a control-tuning or actuator-degradation fault.
  - (v) Fuel-control and shut-off faults: frozen sub-idle RPM with no caution, or a take-off fuel-ratio index offset of about 10–15 %.
  - (vi) Hung start or relight: N2 plateau with T5 rising about 10–15 °C/s. Hot start: T5 overshoot with a compressor stall during light-off.
  - (vii) Bleed leak: 2–3 % thrust loss per lb/s, with T5 and N2 shifts from the engine model.
- [ASSUMPTION] **Fault codes as delayed and secondary.** Code latencies of 0.25–2 s, sensor-fail codes that follow the physical fault, and lost codes when the persistence filter outlasts the event (B-1B case in Q9) should all be modelled. A real FADEC record is otherwise unrealistically clean.

### Gaps
- No F404-IN20 or Tejas engine fault trace. The 12 Mar 2024 Jaisalmer Tejas loss has only unofficial accounts: an oil-level or oil-pump explanation, a "low whistle" or "unusual noise".
- No public command-vs-feedback trace for a failed-open or failed-closed nozzle on any F404/F110.
- No F404 hot or hung start T5 traces, and no F404 FADEC stall-recovery or auto-relight logic.
- No official numbers for the RAAF EA-18G F414 HPC failure or the Spanish and Finnish F/A-18 events (press only).
- AIB reports from 2014–2018 could not be located; Canadian and UK reports gave no engine traces.

---

## Q7. Mechanical degradation progression: bearing spall timelines with oil-debris counts and vibration, accessory-gearbox faults, chip-detector behaviour, oil analysis and oil consumption

### Takeaway
Bearing spall progression is now quantified from NASA, AFRL, GE/DARPA and GasTOPS rig and engine-bearing tests [TRANSFER]:
- **Incubation:** 1–40 h on rigs; about 37 h on a full-scale GE engine roller bearing. GasTOPS states that field cases take 50–100 FH from incubation to the knee.
- **Propagation:** roughly linear at 0.08–0.34 mm/h of spall length (about 3–4 mm²/h of area on the GE bearing). It accelerates once the spall reaches about one rolling-element spacing, or 2–4× its width.
- **Debris:** about 2–50 mg per mm of spall, and about 2.5–4 ODM counts per mg.

The main observability findings:
- SOAP/JOAP often does not see spalls at all; spalling is caught by chip detectors or oil-debris monitors (JOAP for F110/F100 says so explicitly).
- Gear-tooth cracks make no debris and are visible only to synchronous-averaged vibration, 42–103 h ahead.
- Lubrication starvation (the F-16 F110 AGB/PTO case) is a separate, fast fault class (≈ 5 engine operating hours) with essentially no precursor.

Fighter-engine oil-analysis limits and consumption limits are public in JOAP Vol III:
- F404-400/402: Fe abnormal ≥ 15 ppm or a trend of +3 ppm per 10 h. Routine USN oil analysis on the F404 was deleted in 1984.
- F110: oil-consumption limit about 0.355 L/h.

No public F404-IN20 chip, vibration or oil-consumption data exist, and no non-limited source gave chip-light nuisance rates.

### Cited Findings

**Bearing spall: initiation → propagation → failure**
- **UH-60M tail-gearbox tapered roller cups on a spall rig** [TRANSFER: helicopter roller bearing; same physics, lower speed] — [Dempsey, Bolander, Haynes & Toms, NASA TM-2011-217117, Tables 2–4, pp.7–10](https://ntrs.nasa.gov/api/citations/20110023753/downloads/20110023753.pdf)
  - Spall growth rates:

    | Cup | Load (% of rated) | Spall length (mm) | Growth rate (mm/h) |
    |---|---|---|---|
    | Cup 27 | 125 | 16.2 | 0.08 |
    | Cup 33 | 100 | 27.8 | 0.26 |
    | Cup 35 | 150 | 15.2 | 0.11 |
    | Cup 36 | 150 | 19.2 | 0.12 |

  - An earlier study on the same bearing type measured 0.14–0.34 mm/h.
  - **Conflict:** the 100 % load cup grew fastest; the authors attribute this to bearing history and to spall length.
  - Morphology: the spall first grows to the rolling-element width, then propagates circumferentially. Growth "rapidly increases" at about 2–4× the width. Aviation-engine failure is defined as a spall over 60 % of the race circumference.
  - ODM alarm: M_alarm = K·(360/N)·D·w, derived from more than 40 bearing failures, gives 309 mg for this bearing. ODM mass maps to spall length as 309 mg → 9.5 mm, 776 mg → 18.7 mm, 1,315 mg → 29.4 mm (≈ 50 mg/mm).
  - Implied remaining life from ODM alarm to 29.4 mm is ≥ 58 h.
  - The ODM used 16 size bins over 125–1,016 µm.
- **Large tapered roller bearing under simulated engine load** (29 rollers, 14.72-in pitch diameter, 3,200 rpm, 40,000 lbf) [TRANSFER] — [NASA TM-2006-214082, Tables 3–6, pp.2–5](https://ntrs.nasa.gov/api/citations/20060008937/downloads/20060008937.pdf)
  - K = 9.31 mg/(deg·in²); alarm 2,058 mg; warning = 0.1 × alarm = 205.8 mg ("initial spall development").
  - Cumulative ODM mass at successive inspections: 5.4 → 38.7 → 394 → 860 → 2,265 mg (test 2) and 117 → 246 → 3,753 mg (test 1).
  - A **healthy baseline bearing still generated 183.5 mg** of debris, which sets the false-alarm floor.
  - In the companion vibration study, RMS rose from 0.10–0.16 to 0.31–0.91 (about 2–6×) at final damage, and BPFO (835 Hz) and 2×BSF features grew — [NASA TM-2006-214380, Table 4, p.13](https://ntrs.nasa.gov/api/citations/20060045866/downloads/20060045866.pdf).
- **AFRL aero-bearing steels: M50, M50NiL and 52100 208-size ball bearings** (10,000 rpm, MIL-PRF-7808 oil, ODM on the scavenge line) [TRANSFER: aero-engine bearing steels, rig] — [Rosado, Forster et al., AFRL-RZ-WP-TP-2009-2208, pp.7–10, 44–47 (DTIC ADA510506, public release)](https://archive.org/download/DTIC_ADA510506/DTIC_ADA510506.pdf)
  - Spalls are initiated until the accelerometer exceeds **1.0 g RMS**, at a spall of about 1–2 mm. They are then propagated to a 100 mg loss, which is about a 50 mm spall (≈ 2 mg/mm).
  - Stress cycles from 10 mg to 100 mg; hours derived by the helper at 3.95×10⁶ cycles/h for M50 and M50NiL and 4.6×10⁶ for 52100:

    | Steel | 2.10 GPa, new | 2.41 GPa, new | 2.41 GPa, life-tested |
    |---|---|---|---|
    | 52100 | 5.29×10⁶ (≈ 1.2 h) | 3.34×10⁶ (≈ 0.7 h) | — |
    | M50 | 2.14×10⁸ (≈ 54 h) | 2.34×10⁷ (≈ 5.9 h) | 2.0×10⁶ (≈ 0.5 h) |
    | M50NiL | 1.42×10⁸ (≈ 36 h) | 1.07×10⁷ (≈ 2.7 h) | — |

  - Every steel showed a low-rate phase, then a "knee", then critical growth.
  - Bearings with prior service propagated about 12× faster.
  - L10: M50NiL 3.1×10⁹ cycles; 52100 5.1×10⁸ cycles.
- **Full-scale GE engine roller bearing with a seeded outer-race spall** (DARPA Engine System Prognosis) [TRANSFER: the closest fighter-engine-relevant timeline found] — [Bolander et al., PHM Society 2009, Table 1, pp.3–8](https://papers.phmsociety.org/index.php/phmconf/article/view/1631)
  - Spall area: 0.0088 in² at 1.54 h; 0.0156 in² at 38.6 h; 0.082 in² at 48.8 h; 0.125 in² at 57.1 h.
  - [DERIVED] Incubation ≈ 37 h at ~0.1 mm²/h, then ≈ 3–4 mm²/h.
  - Failure threshold: spall length equal to one roller spacing, with cage failure soon after.
  - Engine bearing spalls are "one of the leading causes of class-A mechanical failures".
  - Vibration features "may decrease as the fault develops"; the authors fused oil debris with synchronously resampled envelope vibration.
- **GasTOPS rig plus field statement** [TRANSFER: vendor] — [Mahmoud & Oszmian, European Rotorcraft Forum paper, pp.2–3, Figs. 1, 6](https://dspace-erf.nlr.nl/bitstreams/f93d7929-9002-4ae8-8bf7-4dc395857d10/download)
  - Rig: 25 mm bore, 6,000 rpm, MetalSCAN sensing Fe > 65 µm. Incubation 1–4 h; **100 Fe counts = confirmed spalling; knee ≈ 2,000 Fe counts**; the rig passes through the whole curve in under 10 h.
  - Field: "field applications generally take 50 to 100 flight hours from incubation to the spall knee".
  - Halving speed slows degradation markedly. Hybrid (ceramic-ball) bearings degrade like all-steel ones.
- **OH-58 500-hp transmission, duplex ball bearing, ODM read every 15 s** [TRANSFER] — [NASA TM-2004-212883, Table 8, p.9](https://ntrs.nasa.gov/api/citations/20040082336/downloads/20040082336.pdf)
  - A step increase in debris at about 11.5 h coincided with the chip detector indication. Accumulated debris then rose exponentially to **635.6 mg / 2,257 counts at about 33 h**, by when more than half of both races were damaged (mean particle 378 µm).
  - Particle-size distributions did *not* separate gear from bearing damage, or failure debris from normal wear.
  - HUMS vibration fault detection is quoted at about 70 %, with false warnings about 1 per 100 FH (p.1).
- **F119 ODM development** [TRANSFER: F119; vendor] — [Muir & Howe 1996 (DTIC ADP010191, Distribution A)](https://archive.org/download/DTIC_ADP010191/DTIC_ADP010191.pdf); [Howe & Muir 1998 (ADA347503)](https://archive.org/download/DTIC_ADA347503/DTIC_ADA347503.pdf)
  - Main-bearing damage "can progress very rapidly … sometimes in a matter of only a few hours".
  - F119 requirement: ≥ 125 µm Fe and 250 µm non-ferrous at 100 % detection efficiency; > 350 °F oil; > 300 psia; up to 50 % entrained air.
  - P&W large thrust-bearing test, run to about 50 g vibration: > 150,000 Fe particles > 200 µm and > 25,000 > 700 µm, with the count rate accelerating at the end.
- **Army helicopters** [TRANSFER] — [Beerbower, USAAMRDL-TR-74-100 (1975), Fig. 42, pp.48–49, 82–84, Table 2 p.21 (ADA006190)](https://archive.org/download/DTIC_ADA006190/DTIC_ADA006190.pdf)
  - CH-47: hours from the first SOAP warning to critical gear and bearing damage are Weibull with **L50 = 52 h**.
  - Engineering opinion: bearings run "50 hours or more from first detection to loss of function".
  - Army turbine-engine bearing problem mix:

    | Failure mode | Share |
    |---|---|
    | Low-cycle sliding fatigue (total) | 54 % |
    | – non-classical spalling from excessive load | 25 % |
    | – cage wear | 13 % |
    | – manufacturing errors | 8 % |
    | – skidding | 8 % |
    | Race rotation | 16 % |
    | Insufficient flow | 12 % |
    | Classical rolling fatigue | 11 % |
    | Abrasive | 4 % |
    | Miscellaneous | 3 % |

**SOAP/JOAP trends and blind spots**
- **USAF fighter-engine SOAP regression (ARINC 1974)** [TRANSFER: J79/J85/TF30/TF41 fighter engines] — [ADA052114, Tables 1 and 5, pp.6–13](https://archive.org/download/DTIC_ADA052114/DTIC_ADA052114.pdf)
  - Fe wear-metal slopes (normal → abnormal):
    - J79-15/17 (F-4): 0–0.36 → 1.08–2.85 ppm/h; the abnormal line starts 2.1–11.4 h before detection, at 15–19.5 ppm; detection at 21–32 ppm.
    - J79-11: 0.66 → 11.34 ppm/h.
    - J85 (T-38): 0.16–0.44 → 0.85–1.49 ppm/h.
    - TF30 (F-111): abnormal 1.48–5.08 ppm/h.
    - TF41 (A-7): 0.24 → 4.09 ppm/h.
  - Example record: Fe flat at about 3 ppm for about 40 h, then rising to 13 ppm, sharply in the last ~10 h.
  - 1973 programme yield: USAF 1,311 SOAP removals from 1.44 M samples, 96 % confirmed; USN fixed-wing 76.5 % confirmed (Beerbower App. B).
- **JOAP Vol III** (NAVAIR 17-15-50.3 / T.O. 33-1-37-3, 30 Aug 2013, Distribution A) [TRANSFER: F404 family and other fighter engines] — [everyspec copy; local `mech_degradation/JOAP_NAVAIR_17-15-50.3_Vol3_30AUG2013.pdf`](https://everyspec.com/USN/NAVAIR/NAVAIR_17-15-50x3_30AUG2013_49353/)
  - **F404-GE-400/402 (WP 056 00).**
    - Abnormal trend: Fe +3 ppm per 10 h; other wear metals +2–3 ppm per 10 h. The column-to-element mapping is ambiguous in the extracted text.
    - Fe ranges: normal 0–8, marginal 9–11, high 12–14, abnormal ≥ 15 ppm; other listed metals abnormal at ≥ 10 ppm.
    - **"The requirement for routine oil analysis on the F404-GE-400/402 … has been deleted"** (NAVAIRSYSCOM letter, 14 May 1984). The criteria are retained for special sampling.
  - **F404-GE-F1D2 (WP 061):** Fe trend 3 ppm per 10 h; abnormal ≥ 12 ppm.
  - **F135 (WP 057):** Fe trend 3 ppm per 10 EOH.
  - **F110-GE-100/-129 (WP 049/050).**
    - Fe trend 3 ppm per 10 h; abnormal ≥ 14 ppm.
    - Break-in allowance: up to 6 ppm per 10 EFH in the first 25 FH, 4 ppm to 60 FH, 3 ppm to 100 FH.
    - Element-to-part mapping: Ti → No.1–3 inner races spinning; Cr → No.4–5; Fe + Ni + Cr → AGB gears. "A sudden increase of Fe may indicate main bearing distress".
    - Main-bearing failures "may occur without any indication reflected in the JOAP analysis"; spalling is "detected by chip detectors".
    - **Maximum oil consumption 1.5 half-pints per EOT hour (≈ 0.355 L/h)**; lube capacity about 10.2–10.6 L.
  - **F100 (WP 046).**
    - Fe trend 4 ppm per 10 h; abnormal ≥ 15 ppm.
    - A single-sample jump of ≥ 5 ppm, or +9 ppm within 10 h, triggers a No.4 bearing teardown. Engines on surveillance are sampled after every flight.
    - Maximum consumption 0.125 gal/h ≈ 0.47 L/h.
  - **Other consumption limits:**

    | Engine | Limit | ≈ L/h |
    |---|---|---|
    | F119 | 0.15 gal/h | 0.57 |
    | F101/F118 | 0.10 gal/h | 0.38 |
    | J85-13/-21 | ½ pt/h | 0.24 |
    | TF34 | ½ pt/h | 0.24 |

    Exceeding these limits points to internal causes such as carbon-seal damage.
- **Oil-analysis trend arithmetic** [TRANSFER: USAF CEMS IV] — [ADA131055, pp.2–5](https://archive.org/download/DTIC_ADA131055/DTIC_ADA131055.pdf). Trend = Δppm × 10 / Δhours, with oil top-ups diluting the concentration.
- **SOAP blind to gear spalls** [TRANSFER] — [Lewicki 1992, ADA262479](https://archive.org/download/DTIC_ADA262479/DTIC_ADA262479.pdf). On an OH-58 rig, after 88 h with many spalled sun-gear teeth and a chip light, spectroscopy and ferrography still showed "extremely clean" oil. A planet-bearing cage failure at 91 h showed only as a sharp rise in heat generation.
- Already known: CF-18 SOAP interval 20/100 h; AES sees only particles ≲ 5 µm; QFDA wear rates (`f404_in20_engine_model.md` Q8).

**Accessory gearbox and gear faults**
- **F-16C 87-0242 (7 Jun 2011, F110-GE-100) AGB PTO-shaft forward ball-bearing failure from oil starvation** [TRANSFER: GE F110 AGB/PTO, the closest analogue to the IN20 AGB/AMAGB drive] — [USAF AIB report, pp.4, 9–21](https://www.airandspaceforces.com/PDF/SiteCollectionDocuments/Reports/2011/October%202011/Day20/ACC_F-16_AIB_101211.pdf)
  - **Cause:** glass-bead blast media from depot overhaul, plus a piece of Teflon, blocked the AGB oil supply line.
  - **Timeline:** the AGB was installed at 5,907.0 EOT h and failed at 5,912.2 EOT h (**≈ 5.2 EOT h; 1.4 aircraft flight hours**).
  - **Precursors:**
    - after sortie 1 the master chip detector's SEM/EDX gave a "Level 1 warning for 9310/4340" (gear steel), cleared as normal for a recently maintained engine;
    - JOAP was "well within limits";
    - the post-crash chip detector held only "fuzz", with no M50 bearing chips.
  - **Failure physics and signature:**
    - the balls wore down and the PTO shaft shifted forward, disengaging the bevel gears and decoupling the AGB;
    - the indicated RPM (sensed off the AGB) fell to 0 % within about 2 s, a false reading, while FTIT and oil pressure wound down more slowly;
    - both generators dropped off line and the EPU fired;
    - the JFS restart spun the AGB to a false 50 %, producing a hung start.
- **Gear tooth crack, RAN Wessex input spiral-bevel pinion** [TRANSFER] — [McFadden, ARL 1985 (ADA173851)](https://archive.org/download/DTIC_ADA173851/DTIC_ADA173851.pdf)
  - The crack started at a subsurface inclusion and grew "probably over several hundred flying hours"; the final growth took possibly 20 min.
  - "No debris are generated during crack propagation".
  - Time-synchronous averaging detected it 42 h before failure; enhanced kurtosis and phase-demodulation processing detected it 103 h before.
- **Planet-bearing race crack (AS332L2 G-REDL)** [TRANSFER] — [Flight Safety Foundation summary of AAIB 2/2011](https://flightsafety.org/asw-article/fractured-gear/)
  - An epicyclic chip warning occurred with a cumulative count of 667.
  - A race-steel particle was found but misjudged as plating scale; catastrophic failure followed **36 FH later**.
  - The last 4 min had 4 chip warnings plus low gearbox oil pressure.
- **Gear pitting debris** [TRANSFER] — [NASA TM-2003-211307, pp.37–38](https://ntrs.nasa.gov/citations/20030056593)
  - About 0.26 mg per 1/64-in pit; destructive pitting at 8.69–15.48 mg on small spur gears.
  - Undamaged runs reached up to 5.45 mg, overlapping initial pitting at 3.38 mg.
  - Fusion uses mass plus FM4/NA4 vibration features in a three-state fuzzy logic (OK, Inspect, Shutdown).

**Chip detectors**
- No non-limited source gave nuisance-versus-significant chip-light rates per 1,000 EFH (see Gaps).
- **Capture efficiency** varies with design [TRANSFER: T56] — [ARL 1989 (ADA221864), pp.1–4](https://archive.org/download/DTIC_ADA221864/DTIC_ADA221864.pdf)
  - screw-in plugs 1.2–1.4 kG field versus quick-disconnect 0.2–0.85 kG;
  - one plug captured about 1.5× the reference; shrouded types captured less;
  - insertion depth matters.
- Vendor view: chip-detector efficiency is "quite poor", prone to "fuzz" false alarms, and fuzz-burning is "still considered to be poor" — [Howe & Muir 1998, p.1](https://archive.org/download/DTIC_ADA347503/DTIC_ADA347503.pdf) [TRANSFER; vendor].
- Lead times from first chip or spectrometric sign to failure range from "a few hours" (vendor), through 21.7 h (rig), to 36 FH (G-REDL) and an L50 of 52 h (CH-47).

**Removal statistics (fault-class weights)**
- F404-GE-400 (USN, 1987–90): MTBF 67.4 h; MTBMA 19.0 h; **3.7 removals per 1,000 EFH** (goal < 2.0); MTTR 6.2 h. Comparators: TF30 2.6, TF41 3.4, J79 2.5 per 1,000 EFH. 1993 life-limit cuts averaged 46 % across 12 parts — [King & Tooker, NPS 1993, Table 2.1 p.23 (ADA277918)](https://archive.org/download/DTIC_ADA277918/DTIC_ADA277918.pdf) [TRANSFER: -400; partly already known].
- CF-18 F404 IECMS monitored N1, N2, EGT, oil pressure and vibration against limits. The flight-line troubleshooting system cut false engine removals by 50 % and LRU removals per incident by 26 % — [Paré & Muir 1998 (ADA347270)](https://archive.org/download/DTIC_ADA347270/DTIC_ADA347270.pdf) [TRANSFER; partly already known].
- [TRANSFER: F404-102 → IN20] Accelerated durability test of a T-50 F404-GE-102 with Korean-made parts: 550 cycles, 330 h at Samsung Techwin, Mar–Aug 2006. **Nozzle outer-flap cracks appeared at about 25 % of test duration**: crack lengths 4–16 mm at 8 locations on 5 parts, handled by design review — [KDTQ article, Aerospace (Korea) 2006, local `f404_in20/ksas_JAKO200673334943950.pdf`, pp.24–26 (Korean)](https://koreascience.kr/article/JAKO200673334943950.page) (site timed out on re-check; local copy authoritative).

### Inferences
- [ASSUMPTION] **Bearing state machine (per main-shaft and AGB bearing):**
  1. **Initiation:** Weibull with β ≈ 1.1–1.5 and η scaled from L10 by load, oil temperature and contamination class. Calibrate fleet onset to the Su-30 AL-31FP anchor (≈ 500 → 900 FH, already known).
  2. **Incubation:** lognormal, median 10–40 h, with debris about 0.1–1 mg/h.
  3. **Propagation:** dL/dt lognormal, median about 0.15 mm/h (range 0.08–0.34) at nominal load, scaled by a high power of Hertz stress (the AFRL data show 10× life change for 15 % stress). Apply a 1–12× multiplier for bearings with service history.
  4. **Knee:** at L ≈ πD/N (one element spacing). Beyond it the rate rises 5–10× and a cage-failure hazard applies; seizure follows in minutes to hours.
- **Bearing signatures:**
  - debris mass 2–50 mg per mm of spall (scale by width and depth); 2.5–4 ODM counts per mg for particles ≥ 250 µm;
  - chip-light capture probability 0.05–0.3 per large particle, latching when bridging mass exceeds a few mg;
  - envelope vibration at BPFO/BPFI rising non-monotonically, with broadband RMS ×2–6 near failure;
  - SOAP Fe *often flat* for spalls.
  - Validate the lead time from first chip/ODM detection to the knee: 20 h (rig) to 50–100 FH (field).
- [ASSUMPTION] **Separate fault classes with different observability:**
  - (i) spall: debris-observable;
  - (ii) sliding wear / race spinning / cage wear: SOAP-observable, abnormal Fe slope 1–11 ppm/h over 1–20 h;
  - (iii) oil starvation: no precursor, ≈ 1–10 EOT h to failure, then a coupled AGB loss of N2 indication, oil pressure, generators and fuel pump drive;
  - (iv) gear-tooth crack: vibration-only, 40–100 h warning, minutes-long terminal phase;
  - (v) carbon-seal wear: oil consumption rising toward a limit of about 0.24–0.36 L/h (F404-IN20 analogue to J85/F110; validate with the IN20 maintenance manual).
- [ASSUMPTION] **Fuzz nuisance process:** an independent Poisson process of chip lights, elevated in the first ~100 h after build or maintenance (F110 break-in limits). Maintenance-induced debris injection is a latent-fault class (F-16 glass-bead case).

### Gaps
- No public F404-IN20 (or F404-402) chip-detector logic, ODM fit, oil-consumption limit, in-flight vibration limits or Tejas chip/removal statistics.
- No non-limited source for chip-light nuisance rates per 1,000 EFH. The candidate, USAAVSCOM TR-84-D-7 (ODDS, UH-1: a chip light about every 130 FH, 86 % false), still carries its original limited-distribution marking on its pages and was not used.
- No fighter-engine imbalance or blade-damage vibration growth rates (ips per hour).
- No cause-coded removal breakdown for F110/F100/EJ200/RM12/F404.
- The DMRL "Investigations on Failures" chapters on aero-engine bearings and bevel gears are listed in its table of contents only; the online copy is a 21-page excerpt.

---

## Q8. Utility-system degradation rates and signatures: hydraulic pump wear, accumulator precharge loss, filter ΔP growth, generator bearing and diode faults, ECS heat-exchanger fouling and ACM, brake wear per landing, tyre wear per landing, shock-strut servicing loss

### Takeaway
Quantified utility degradation evidence exists, but almost all of it is civil or transport TRANSFER. Nothing new is Tejas-direct.

- **Hydraulic engine-driven pump wear** is now characterised by two field-calibrated Boeing monitoring patents:
  - The case-drain temperature rise over pump inlet sits in a speed-dependent band of 7–31 °F (3.9–17.2 °C).
  - It is flat for about 5 months, then rises convexly to a 35 °F (19.4 °C) limit at about 11.5 months.
  - Before failure, case-drain filter ΔP climbs from a 6–12 psi baseline to above 14 psi (about 6 psi/month), and replacement is required within 3 days.
  - Contamination multiplies pump wear about 4× (5 µm filtration) and 14× (15 µm) relative to 0.8 µm.
  - Fleet contamination class does not trend with flight hours.
- **Carbon brakes:** F-15C/D carbon brakes (3 rotors, like Tejas) last 1,400 landings per overhaul, against 342–439 for the incumbent heat sink.
- **Tyres:** tread wear is linear in distance and set by slip ratio, yaw and surface. It is about 0.1–0.6 kg/km at slip 0.1–0.3, and 0.04–0.47 kg/km at 4–24° yaw. F-35 tyres "require very frequent replacement".
- **ECS:** ECS packs fail from ram-air heat-exchanger fouling in 3–9 months under polluted ground operation (vs about 18-month cleaning), and are shut down above 260 °C.
- **Generators:** rotating-diode faults have specific electrical signatures (field-current rise, harmonic-ratio shift, ripple changes). CSD/IDG wear shows as frequency fluctuation at idle.
- **Not found:**
  - aircraft accumulator precharge-loss rates (only ~1 %/yr for low-pressure bladders);
  - military pump/generator MTBF;
  - shock-strut leakage rates;
  - quantified pressure-ripple growth.

### Cited Findings

**Hydraulic pumps**
- **Case-drain temperature-rise monitoring.** [TRANSFER: Boeing transport engine- and motor-driven pumps, 3,000 psi; same leakage-heat physics, since 90–95 % of pump heat goes to the case drain below 1 gpm discharge] — [US 12,265,000 B2 (Boeing, granted 1 Apr 2025), FIGs. 3, 5–7, sheets 4–5](https://patents.google.com/patent/US12265000B2/en)
  - Expected cruise rise, inlet to case drain:

    | Pump speed (rpm) | Expected rise (°F) |
    |---|---|
    | 1,000–2,000 | 7–12 |
    | 2,001–3,000 | 9–17 |
    | 3,001–4,000 | 12–22 |
    | 4,001–5,000 | 16–25 |
    | 5,001–6,000 | 19–28 |
    | 6,001–7,000 | 21–31 |

  - Overheat threshold is a 35 °F rise.
  - Maintenance timing: within 1 month if the rise is > 3 °F outside the band, otherwise within 6 months.
  - FIG. 7 trend: flat about 5 months, rising months 5–9, crossing the threshold at about 11.5 months.
  - Sampling every 30 s to 15 min.
- **Pump temperature plus case-drain filter ΔP.** [TRANSFER: Boeing pump with case-drain filter module] — [US 11,078,935 B2, col. 10–11, FIGs. 9–10](https://patents.google.com/patent/US11078935B2/en)
  - Pump-minus-reservoir ΔT: nominal 22 °C, threshold 26 °C.
  - Field case-drain filter ΔP, Oct 2015 – Apr 2016:
    - baseline about 6–12 psi with about ±3 psi flight-to-flight scatter;
    - from about 11 Mar 2016 a rise to about 18 psi, crossing the 14 psi threshold around 25 Mar;
    - message: the "pump has failed and should be replaced within … three (3) days".
  - **Conflict:** this patent uses a different temperature metric from US 12,265,000; the two are not interchangeable.
- **Navy 8,000 psi test rig.** [TRANSFER: high-pressure Navy rig] — [Grumman NADC-87162-60 (1987, approved for public release), §§2.10.4, 2.10.6 (DTIC ADA189366)](https://archive.org/details/DTIC_ADA189366)
  - Normal case-drain temperature about 245 °F (118 °C); high case-drain temperature alarm 275 °F (135 °C).
  - Fluid "temp above 190 F" warning.
  - Excess case-drain flow detected against a ground-run baseline.
- **Contamination and wear.** [TRANSFER] — [Bensch, Needelman & Lundquist (Pall), FAA Hydraulics Task Force / SAE A-6 paper, 15 Apr 1996, pp.3–8, Figs. 7, 10, 14–16, Table 5](https://www.pall.com/content/dam/pall/aerospace-defense/literature-library/non-gated/white-paper/contamination-control-paper.pdf)
  - NADC/Ohlson pump-wear test (Vickers A4 piston pump, 3,000 psi, 3,850 rpm, MIL-H-83282 at 200 °F): relative wear ≈ 1 / 4 / 14 at 0.8 / 5 / 15 µm filtration.
  - Servovalves at 2–16 mg/L of 0–10 µm dust: hysteresis +1.3–6.7 % of rated current, reversible. Permanent damage: pressure gain −17 %; null leakage 3 % → > 20 % of rated flow.
  - Fleet contamination class:
    - "No trends could be seen from the flight hour breakdown";
    - NAS 1638 averages 6.3 (B727) to 8.5 (B737);
    - NTSB samples: reservoir 7.8 (SD 2.2), rudder PCU 7.3 (SD 1.7);
    - specifications: class 9 in service.
  - An 8,000 psi tactical iron bird ran at AS4059 class 00 with 5 µm filtration and 000 with 1 µm, varying within the mission.
  - SAE ARP4268A sampling interval: 6–12 months or 1,500 h.
  - Not used: a 1963 Douglas survey (DTIC AD0402711) that makes the same "no flight-time trend" point and qualitatively links pump wear to pulsation, because it carries an ASTIA "qualified requesters" notice.

**Accumulators**
- **Precharge temperature dependence and health test.** [TRANSFER: Airbus 206-bar systems] — [US 8,494,789 B2 (Airbus), col. 5–6](https://patents.google.com/patent/US8494789B2/en)
  - Precharge is 133 bar at 20 °C, about 106 bar at −40 °C and about 152 bar at 60 °C (ideal gas).
  - Health test: compare the pressure-decay time above precharge (190 → 160 bar) with that below it (90 → 60 bar), only between −40 and +60 °C.
- **Loss-rate floor.** [TRANSFER: low-pressure automotive bladder, a lower bound] Total loss of about 10 % over ten years (about 1 %/yr) — [US 5,655,569, col. 4](https://patents.google.com/patent/US5655569A/en).
- **Industrial practice.** [TRANSFER] Piston-type permeation is negligible but seals still leak. Bladder types lose gas faster, and loss rises with temperature. Check intervals: 1 week, 3 months, then every 3–6 months — [Fluid Power Journal, 14 May 2018](https://fluidpowerjournal.com/hydraulic-accumulators-pre-charge-maintenance/).

**Generators**
- **CSD/IDG speed-regulation wear.** [TRANSFER: Airbus IDGs; applies only if the Tejas main generator has a constant-speed drive] — [Airbus Safety First, Mar 2025, pp.4–6](https://mms-safetyfirst.s3.eu-west-3.amazonaws.com/pdf/safety+first/preventing-loss-of-engine-generators-on-a320-family-a330-and-a340-aircraft.pdf)
  - Worn hydraulic blocks cause frequency fluctuations, and the GCU disconnects the generator.
  - Worst near idle (the "straight-through" speed) and on a sudden load transfer.
  - Airbus added a check every 3,000 FH or 36 months.
- **Rotating-rectifier diode faults.** [TRANSFER: aircraft brushless generators]
  - On diode failure the exciter-field AC ripple "increases in amplitude and decreases in frequency" — [US 4,486,801 (Sundstrand)](https://patents.google.com/patent/US4486801A/en).
  - A shorted diode drives reverse field current — [US 4,559,486](https://patents.google.com/patent/US4559486A/en).
  - A shorted diode causes "loss of capacity to regulate the generator output voltage". It is seen as fast voltage build-up on the PMG DC link; ripple methods are "relatively slow" — [EP 2,077,613 B1 (Hamilton Sundstrand), ¶¶3–9](https://patents.google.com/patent/EP2077613B1/en).
  - [US 9,910,083 B2 (Rolls-Royce)](https://patents.google.com/patent/US9910083B2/en):
    - An open diode reduces exciter capacity and raises field current; the machine can run "for limited time".
    - A short is the "most frequent" failure. It needs a "very large increase" in field current and the generator is usually shut down.
    - Detection uses the ratio of fundamental to 6th-harmonic magnitude of the main-field rectified voltage.
- **Power-quality limits** usable as validity thresholds: see Q4 (MIL-STD-704F).
- **Fighter generator timing evidence.** [TRANSFER: F-16]
  - Main and standby generators dropped offline about 4 s after flameout as RPM decayed, and the EPU auto-started — [AIB F-16CM 92-3881, PDF p.15](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf).
  - EPU and emergency generator restored power in about 2.5 s, "the typical delay" — [AIB F-16CM 91-0366, Spangdahlem, 11 Aug 2015, PDF p.21](https://www.usafe.af.mil/Portals/8/documents/Spangdahlem%20F-16%20AIB%20Report.pdf?ver=2016-08-30-033647-423).

**ECS**
- **Ram-air heat-exchanger fouling.** [TRANSFER: A320 packs; the ram-air side fouls during ground operation and taxi queues] — [Wright, Dixon-Hardy & Heggs, Thermal Sci. Eng. Prog. 7:184–202 (2018), accepted version pp.3, 11–12, 18, 38](https://eprints.whiterose.ac.uk/id/eprint/134707/1/FINAL.pdf)
  - Packs are normally cleaned at about 18-month C-checks.
  - One UK operator had pack failures every 3–9 months from plate-fin heat-exchanger fouling ([DERIVED] ≈ 700–2,200 FH at about 8 FH/day).
  - Mechanism: passages narrow, ΔP rises, effectiveness falls, and the pack is shut down above 260 °C.
  - Worst on the ground and at take-off/landing; "Hi" flow runs at 120 %.
- **ECS failure shares and MTBF.** [TRANSFER: commercial] — [Khalil, Reliab. Eng. & Resilience (2023/24), pp.4, 17–18](https://www.rengrj.com/article_193793_4900e8aa5d1a666d948fc7faa70a8342.pdf)
  - Failures (Al-Garni data): water extractor 61 %, heat exchanger 8 %, ACM 5 %, compressor 4 %, other 22 %.
  - Modelled ECS MTBF: 13,634–21,438 FH.
- **Fault-injection size.** [TRANSFER] Literature uses a step drop of about 30 % in heat-exchanger hA — [Ma et al., PLOS ONE 2015, p.9](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0122829&type=printable).
- No quantified ACM speed or temperature degradation was found. The claim that foil-bearing ACM MTBF exceeds 100,000 h is secondary and unverified.

**Brakes**
- **F-15 carbon brakes.** [TRANSFER: F-15 carbon brakes; the F-15C/D has 3 rotors, like Tejas] — [Collins Aerospace F-15 wheel and brake fact sheet (22-10887, 09/22), pp.1–2](https://www.rtx.com/collinsaerospace/what-we-do/industries/military-and-defense/landing-systems/wheels-and-brakes)

  | Aircraft | Carbon brake (Collins) | Incumbent heat sink |
  |---|---|---|
  | F-15E (4 rotors) | 1,400 LPO (9.33 yr) | 342 LPO (2.3 yr) |
  | F-15C/D (3 rotors) | 1,400 LPO (10 yr) | 439 LPO (2.9 yr) |

  - This implies about 150 landings/yr.
  - Brake fluid after a normal-energy stop: 227 °F (108 °C) vs 314 °F (157 °C).
- **C-130 carbon vs steel.** [TRANSFER: transport, for energy scale] — [Collins C-130 fact sheet, pp.1–2](https://www.rtx.com/collinsaerospace/what-we-do/industries/military-and-defense/landing-systems/wheels-and-brakes)
  - 2,000 vs 250 landings.
  - Normal-stop energy 23.0 vs 17.6 MJ; RTO 40.7 vs 32.5 MJ.
  - Operating temperature 154 vs 231 °C.
- Already known: 0.025 mm wear per flight (civil); carbon wear depends mainly on the number of applications; Tejas RTOs at 50/70/90 % wear.

**Tyres**
- **NASA tread-wear law.** [TRANSFER: 22×5.5 Type VII tyre, 17.8 kN load, 738 kPa] — [NASA TP-1569 (1979), Fig. 8 (PDF p.24), Fig. 15 (PDF p.33), graph-read](https://ntrs.nasa.gov/api/citations/19800004758/downloads/19800004758.pdf)
  - Wear is linear in distance at fixed slip or yaw.
  - Modern tread on concrete: ≈ 0.2 kg/km at slip 0.1 and ≈ 0.6 kg/km at 0.3. Smooth asphalt gives about half that.
  - Natural-rubber tread reaches ≈ 2.6 kg/km at slip 0.3.
  - Yawed rolling on smooth asphalt: ≈ 0.04 / 0.15 / 0.2 / 0.3 / 0.47 kg/km at 4 / 8 / 12 / 18 / 24°.
  - Wear comes from braking, yawed rolling and spin-up.
- **F-35 tyres.** [TRANSFER: F-35] Tyres "do not last as long as expected and require very frequent replacement". Worn-out removals are scored "no-defect" and so count in removal rates but not in failure metrics. MLG tyres and shock struts appear among high-driver components — [DOT&E FY2014 F-35, local `bit_simreal/DOTE_FY2014_F35.txt`](https://www.dote.osd.mil/Portals/97/pub/reports/FY2014/dod/2014f35jsf.pdf); DOT&E FY2016 F-35.
- **Michelin care manual.** [TRANSFER] — [Michelin MAT-CSM 32-45-01 Rev F (2021), §9.1 (PDF p.71), Fig. 504 (PDF p.83), §8.3 (PDF p.89–90)](https://www.faasafety.gov/files/gslac/courses/content/269/1100/Michelin%20ALC-269%20CSM%202021.pdf)
  - Pressure loss ≤ 5 % per 24 h acceptable; some airframers use 3 %.
  - Action bands (% of cold operating pressure): 95–99 % re-inflate; 90–94 % inspect, log and recheck after 24 h; 80–89 % remove; < 80 % remove both tyres of the pair.
  - Pressure changes 1 % per 3 °C.
  - Shoulder wear indicates under-inflation or frequent high-speed turning; centre wear indicates over-inflation and fewer landings.
- Already known: F-16 main tyres last 8–12 (Block 30) and 4–8 (Block 40/50) landings.

**Shock struts**
- **Landing-based strut monitoring.** [TRANSFER: generic oleo struts] — [US 9,285,007 B2 (Goodrich), col. 2–4](https://patents.google.com/patent/US9285007B2/en)
  - Gas and oil both leak over time. Topping up gas only hides oil loss.
  - Gas pressure, gas temperature and stroke are monitored at ≥ 100 Hz during landing. The transient pressure at two strokes gives a coefficient that shifts significantly with "even 2 % oil loss".
  - Per-landing gas and oil loss is logged to predict servicing.
- Related patents: gas-loss check at 2 % of moles ([US 9,856,038 B2](https://patents.google.com/patent/US9856038B2/en)); oil ≥ 90–99 % gas-saturated during servicing ([US 11,465,777 B2](https://patents.google.com/patent/US11465777B2/en)).
- No leakage rates or re-servicing intervals were found.

### Inferences
- [ASSUMPTION] **Hydraulic pump (AMAGB-driven, 280 bar)**
  - State: internal leakage coefficient k_leak(t).
  - Signature: case-drain ΔT = band(N_pump) × (1 + f(k_leak)). [DERIVED] The same leakage dissipates about 35 % more heat at 280 bar than at 207 bar.
  - Trajectory: about 5 months flat, then a convex rise to a 19 °C-rise limit, so about 12 months total for a pump that is going to fail. Scale by usage.
  - Terminal phase: a 2–4 week chip phase with case-drain filter ΔP rising from 0.4–0.8 bar to > 1 bar.
  - Wear rate multiplied by contamination class: 1 : 4 : 14 for filtration of 0.8 / 5 / 15 µm.
  - Validate with HAL iron-bird or ground-run logs and pump teardown findings.
- [ASSUMPTION] **Accumulator**
  - P0(T) = P0,20 × T/293 K.
  - Loss 0.1–1 %/yr (piston) or ≥ 1 %/yr (bladder), plus a valve-core leak fault with fast loss.
  - Observable only through decay-time tests and the number of brake applications available.
- [ASSUMPTION] **Filters**
  - Contamination class is a quasi-stationary random state per aircraft (NAS ≈ 7 ± 2), with steps after pump failures or line breaks.
  - Filter ΔP grows exponentially with captured mass (already known), from a 0.4–0.8 bar baseline.
  - ΔP-indicator pop-up as a discrete.
- [ASSUMPTION] **Generator**
  - Open diode: field current up tens of percent and the fundamental/6th-harmonic ratio shifts while output stays inside MIL-STD-704F.
  - Short diode: rapid field-current demand, then GCU trip and fallback to the standby generator or EPU.
  - If a CSD is fitted, frequency modulation grows toward the 4 Hz limit and trips occur at idle or on load steps.
- [ASSUMPTION] **ECS heat-exchanger fouling**
  - Fouling resistance grows with ground-run hours × base dust index (Jaisalmer and other desert bases high), not with flight hours.
  - Signatures: ΔP up, effectiveness down, compressor-outlet and turbine-inlet temperatures up, ACM speed shift.
  - First pack trips appear on hot-day ground runs; the cycle is 3–9 months at dirty bases and about 18 months clean.
- [ASSUMPTION] **Carbon brakes**
  - Life about 1,000–1,500 LPO (F-15C/D analogue).
  - [DERIVED] Wear per landing ≈ allowable wear ÷ LPO ≈ 0.014–0.021 mm for 20–30 mm allowable wear.
  - Wear weighted by number of applications, and higher for cold or taxi applications.
  - Per-stop temperature rise = E_brake ÷ (m_hs × c_p), increasing as the stack wears.
- [ASSUMPTION] **Tyres**
  - Tread mass loss per landing = ∫ rate(slip, yaw, surface) ds × (load ÷ 17.8 kN), plus spin-up wear.
  - Calibrate to F-16 tyre life of 4–12 landings.
  - Pressure: gas law plus leak ≤ 5 %/day, with Michelin action bands.
- [ASSUMPTION] **Shock struts**
  - Separate gas-loss and oil-loss states.
  - Gas loss gives lower static extension, a higher peak landing load and bottoming risk.
  - Oil loss changes the early-stroke stiffness and the damping.

### Gaps
- Military EDP and generator MTBF/MTBUR and removal statistics.
- Case-drain flow (L/min) versus hours.
- Quantified pressure-ripple growth.
- Aircraft accumulator precharge-loss rate.
- Filter-indicator pop-up statistics.
- Generator bearing life and oil-temperature trends.
- ACM degradation numbers.
- ECS effectiveness loss per 1,000 FH.
- Tyre mm per landing for non-F-16 fighters.
- Shock-strut loss rates.
- Fighter hydraulic caution set-points.
- Tejas-specific values for all of the above.

---

## Q9. BIT and false alarms: published thresholds, persistence logic, false-alarm and NFF rates for fighter subsystems, CND/RTOK by LRU type

### Takeaway
Fighter BIT in service is far noisier than its specifications. Every number below is [TRANSFER]; none is Tejas-specific.
- **F-35 diagnostics (DOT&E, FY2014–FY2017).**
  - Mean flight hours between false alarms: 0.09–1.03 FH, against a 50 FH requirement. That is roughly 1–11 false alarms per flight hour.
  - Ratio of false alarms to valid maintenance events: 14:1 to 1,079:1.
  - Electronic-fault isolation to one LRU: 42–84 %, against 90 %.
- **F/A-18E/F SARs.** BIT false-alarm rate 33.5–86 % of indications, against a 45 % threshold and 30 % objective. Fault detection 94.5–100 %.
- **Legacy radars (RADC field study).**
  - 22–53 % of BIT indications had no fault.
  - 28–38 % of true faults were called out to the wrong unit.
- **F-14 AWG-9.** CND 31 %, RTOK 25 %.
- **F-16.**
  - Fire-control CND+RTOK 54 %.
  - Turkish F-16 NFF 44.5 % overall, ranging from 29.5 % (RF LRUs) to 63 % (analog LRUs).
- **Missed detections are as large as false alarms.**
  - 39–58 % of EW pods that BIT called "ready" had faults.
  - 41 of 44 F-15Cs had EW faults that BIT had not reported.
- **Persistence and debounce logic.**
  - The RADC analysis gives the false-alarm reduction from m-of-n filters at ±2σ, for 100 signals tested 100 times per hour: from 454 alarms/h (1-of-1) down to 0.90 (3-of-4) and 0.04 (4-of-5).
  - Fighter examples: AFTI/F-16 four-iteration persistence (Q3); DEEC "specified number of cycles"; the F-16 HYD/OIL PRESS caution's 30-s engine-oil persistence.
  - Already known: F/A-18 IECMS exceedances "persist for several iterations".
- **Field false alarms recur across flights.** 67–81 % last one flight, 10–18 % last three or more (tail to 21 flights). Intermittents recur on the next flight 14–21 % of the time.
- **Fleets are heterogeneous.** CND/RTOK counts per tail are overdispersed relative to Poisson.

### Cited Findings

**F-35 ALIS/PHM diagnostic metrics** [TRANSFER: F-35; immature fleet; thresholds apply at 200,000 FH maturity] — DOT&E annual reports: [FY2014 pp.66–67](https://www.dote.osd.mil/Portals/97/pub/reports/FY2014/dod/2014f35jsf.pdf); [FY2015 pp.71–72](https://www.dote.osd.mil/Portals/97/pub/reports/FY2015/dod/2015f35jsf.pdf); [FY2016 pp.97–98](https://www.dote.osd.mil/pub/reports/FY2016/pdf/dod/2016f35jsf.pdf); [FY2017 pp.53–54](https://www.dote.osd.mil/pub/reports/FY2017/pdf/dod/2017f35jsf.pdf). Local copies are in `bit_simreal/`.

| Metric | Threshold | Demonstrated values |
|---|---|---|
| Fault detection coverage | 98 % | 74–81 % (2013–14); 65/73/84 % (FY15 Blk 1/2/3); 88/88/93 % (FY16); 90/96 % (FY17) |
| Fault isolation, electronic, to 1 LRC | 90 % | 42–84 % |
| Fault isolation, non-electronic, to 1 LRC | 70 % | 70–86 % |
| Fault isolation, non-electronic, to ≤3 LRC | 90 % | 80–100 % |
| Mean flight hours between false alarms | 50 FH | 0.59 → 0.23 (2013–14); 0.20/0.60/0.18 (FY15); **0.09/0.41/0.50 (FY16; 61 / 6,440 / 6,111 FH accumulated)**; 0.71/1.03 (FY17) |
| Mean flight hours between flight-safety-critical false alarms | 450 FH | 61–1,360 FH |
| Ratio of false alarms to valid maintenance events | – | 44:1 / 16:1 / 1,079:1 (FY15); 135:1 / 19:1 / 19:1 (FY16); 14:1 / 33:1 (FY17) |

- **Caveats.**
  - The FY17 value printed as "1,03" is read as 1.03 FH, because only 430 FH had accumulated.
  - DOT&E notes false alarms are under-reported: supervisors cancel known false alarms that are not yet on the nuisance filter list.
- **Main false-alarm drivers:** CNI, propulsion, EW, suspension and release, displays, and the integrated core processor (FY15 p.72; FY16 p.98).
- **The Advanced Filter and Correlate tool** targets three classes:
  - false-alarm health reporting codes (HRCs);
  - "sympathetic" HRCs, where one failure produces several work orders;
  - "conditional nuisance" HRCs that fire only in non-representative configurations.
- **Software-induced code bursts.** A FADEC software fault produced up to 40 HRCs per maintenance debrief, about 10× normal — [DOT&E FY2020 F-35, p.30](https://www.dote.osd.mil/Portals/97/pub/reports/FY2020/dod/2020f35jsf.pdf).
- **Threshold trade-off.** Coolant (PAO) leak detection needed a threshold of 2 gal/min, versus a typical 6 gal/min, to avoid excessive false alarms — [DOT&E FY2012 F-35, p.40](http://www.dote.osd.mil/pub/reports/FY2012/pdf/dod/2012f35jsf.pdf).

**F/A-18E/F avionics BIT** [TRANSFER] — [F/A-18E/F Selected Acquisition Report, 31 Dec 2011, pp.9–10](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2011_SARS/FA-18E_F-SAR_31_DEC_2011.pdf) (verified in the local text); Dec 2010 SAR, same pages.

| Metric | Objective | Threshold | Demonstrated (Dec 2011) | Demonstrated (Dec 2010) | Current estimate |
|---|---|---|---|---|---|
| Fault detection | 75 % | 65 % | 94.5 % | 100 % | 98.9 % |
| Fault isolation | 90 % | 85 % | 90.5 % | 100 % | 97.6 % |
| BIT false-alarm rate (% of indications) | 30 % | 45 % | 33.5 % | 86.0 % | 39.6 % |

- **Conflict:** the 2010 and 2011 SAR editions report different demonstrated values without explanation.
- The EA-18G met every suitability threshold except mean flight hours between BIT false alarms — [DOT&E FY2013 F/A-18E/F report, p.174](http://www.dote.osd.mil/pub/reports/FY2013/pdf/navy/2013fa18ef.pdf).

**Legacy fighter radar/fire-control BIT field study** [TRANSFER: 1970s–80s analog/early digital fighter radars; the identities "System 1 ≈ F-14 AWG-9" and "System 2 ≈ F-15 radar" are inferred from the descriptions, because the report anonymises them] — [RADC-TR-81-220 (DTIC ADA108752; Approved for public release)](https://archive.org/details/DTIC_ADA108752)

- **Outcome rates** (Tables 5-1 and 5-3, pp.34–36):

  | System | Cat I false alarms (wrong unit called out, % of true faults) | Cat II (no fault, % of indications) | Events (n) |
  |---|---|---|---|
  | System 1 | 28 % | 53 % | 1,023 |
  | System 2 | 38 % | 22 % | 915 |

- **How long Cat II false alarms persist across flights:**

  | System | 1 flight | 2 flights | ≥ 3 flights |
  |---|---|---|---|
  | System 2 | 81 % | 10 % | 10 % (tail to 15 and 21 flights) |
  | System 1 | 67 % | 15 % | 18 % |

  - **Conflict:** for System 2, Table 5-3 gives 19 two-flight events while the text on p.29 says 21.
- **Root causes of System 1 Cat II false alarms** (Table 5-6, p.43; n = 543):

  | Cause | Share |
  |---|---|
  | Undetermined | 30 % |
  | System anomalies | 26 % |
  | Invalid test | 15 % |
  | Power transient | 12 % |
  | Environment | 8 % |
  | Transmitter dump | 7 % |
  | Operator switch settings | 2 % |

- **Classification rules used in the field study** (pp.25–29):
  - recurrence window = 2 missions;
  - a cluster = ≥ 3 events on the same unit;
  - a callout followed by 2 clean flights = random Cat II.
- **Tightness of limits** (p.53, checked on the scan image):
  - per-test false-fail probability on healthy hardware: ±2σ → 4.5 %; ±3σ → 0.26 %; ±4σ → 0.006 %;
  - limits set from specification values fail unexpectedly even at ±4σ, because the operational mean and σ are not known.
- **m-of-n debounce** (Table 5-8, p.54). Setup: 100 signals, 100 tests/h each, ±2σ, independent tests, non-overlapping windows.

  | Rule | Alarms per hour |
  |---|---|
  | 1-of-1 | 454 |
  | 2-of-2 | 10 |
  | 2-of-5 | 38 |
  | 3-of-3 | 0.31 |
  | 3-of-4 | 0.90 |
  | 3-of-5 | 1.75 |
  | 4-of-5 | 0.04 |
  | 5-of-5 | 0.0004 |

  - Overlapping windows raise the false-alarm rate.
  - Tests must be spaced far enough apart to be uncorrelated (p.51).
- **BIT scale and use** (pp.10–13; App. A):
  - System 1: ~1,000 tests; a 5-min confidence test; ~60 % of the failure rate continuously monitored; < 5 % of the hardware is BIT.
  - System 2: ~150 tests; 3-min initiated BIT; 1.6 % of the hardware is BIT.
  - In-flight confidence BIT was run on < 25 % of missions.
- **F-14 AWG-9 at NAS Miramar** (VF-24/VF-211, Apr–Aug 1976; App. A pp.A-3–A-5):
  - CND: 32 of 103 downing faults (31 %).
  - RTOK: 19 of 77 assemblies sent to the shop (25 %).
  - Same fault on the next flight: 17 % after CND, 14 % after a fix, 21 % after RTOK.

**F-16 CND/RTOK** [TRANSFER] — [AFIT LSSR 49-83, abstract, pp.1–2, 5, 20–21 (DTIC ADA134449)](https://archive.org/details/DTIC_ADA134449)
- Scope: 3 wings, Apr 1981 – Mar 1982.
- **CND+RTOK share of write-ups:**

  | Subsystem (WUC) | Share of avionics malfunctions | CND+RTOK share |
  |---|---|---|
  | Fire-control system (74A00) | 25.9 % | 54 % |
  | Radar LPRF (74AB0) | 19.2 % | 12 % |
  | 74AA0 | 12.6 % | 6.2 % |

- After a CND/RTOK, the radar LPRF was written up again the same day in 45 % of cases, and within one day in 50.4 %.
- About 50 % of CND/RTOK items eventually needed repair.
- The specification required 95 % O-level fault detection and isolation.
- Per-tail counts were overdispersed relative to Poisson (λ = 1.783): 43.5 % of aircraft had zero CND/RTOK events, against 46.4 % expected.
- RTOK rates differed between shop test stations and between wings.

**F-16 NFF by LRU technology (Turkish Air Force, 2013–14)** [TRANSFER: F-16 LRUs; secondary publication] — [IEEE Instrumentation & Measurement Magazine, Aug 2016, Table 2, p.18](https://www.corrosion-protect.com/wp-content/uploads/2018/07/Mitigating-the-Impact-of-False-Alarms-in-Military-System-Final-Proof-R1.pdf)

| LRU technology | NFF rate | Count |
|---|---|---|
| RF | 29.5 % | 94/319 |
| Digital | 47.6 % | 175/368 |
| Mixed | 56.0 % | 130/232 |
| Analog | 63.0 % | 34/54 |
| **Total** | **44.5 %** | 433/973 |

**F/A-18 legacy fleet (secondary)** [TRANSFER] — [Ungar, "Causes and costs of NFF", pp.8, 29](https://www.electronics.org/system/files/technical_resource/E38&S18-02%20-%20Louis%20Ungar.pdf), citing Bain & Orwig (NDIA 2000) and ASN TB ABM 1001-01:
- F/A-18C BIT false-alarm rate > 88 %, with mean hours between false alarms < 1 FH.
- 75 % (> 83 % in some cases) of avionics CNDs caused by BIT false alarms.
- V-22 BIT false-alarm rate at OPEVAL: 92 %.

**EW BIT misses and misidentifications** [TRANSFER]

*GAO/NSIAD-89-137, pp.12–13* ([DTIC ADA212952](https://archive.org/details/DTIC_ADA212952)):

| Item | Finding |
|---|---|
| ALQ-131 Blk II jammer | BIT identified the wrong fault 27 % of the time (requirement ≤ 10 %) |
| ALR-69 radar warning receiver | Wrong identification 0–27 % by component; 34 % aggregate |
| ALQ-131 pods BIT reported as ready | 58 % had faults at the 90-day inspection |
| ALQ-119 pods BIT reported as ready | 39 % had faults at the 90-day inspection |
| F-15 ALR-56/ALQ-135 in an exercise | BIT failed to identify 90 % of malfunctions |

*GAO-01-843, pp.5–6* ([report](https://www.govinfo.gov/content/pkg/GAOREPORTS-GAO-01-843/html/GAOREPORTS-GAO-01-843.htm)), using a new flight-line tester:
- F-15C: 41 of 44 aircraft had EW faults BIT had not reported.
- F/A-18C: 14 of 16 aircraft.
- Oceana: 10 of 10 aircraft, each with ≥ 3 faults.

**F-22 integrated avionics (Jan 2004)** [TRANSFER] — [GAO-04-391](https://www.gao.gov/assets/a241715.html):
- Mean time between avionics anomalies 2.7 h, against a 5 h requirement.
- Type 1 full shutdowns about 1 per 25 h.
- MTBM 0.5 FH, against a 1.95 FH requirement.

**Maturation (civil)** [TRANSFER] — [Flight International, "Biting into false alarms" (1996)](https://flightglobal.com/biting-into-false-alarms/10024.article):
- A340/A330 central-maintenance messages fell from > 50 per flight to about 5 per flight.
- Under 20 % of removed computers had confirmed failures.

**Environmental correlation** [TRANSFER: F-16 stress recorder] — [RL-TR-91-353 (DTIC ADA247192), p.40, pp.G-3–G-4](https://archive.org/details/DTIC_ADA247192):
- The recorder used a 50–250 Hz vibration bandpass, logging peak and integral every 1 s.
- Over 60 % of F-16 flight hours were at q = 300–350 lb/ft², but over 50 % of vibration-induced failures occurred at q ≥ 1,000 lb/ft².
- Peak random vibration is about 3× RMS.

**Generic failure-mode split for alarm devices** [TRANSFER] — [MIL-HDBK-338B, Table 7.8-1, p.7-193; local `research_sources/maintenance/MIL-HDBK-338B.txt`](https://everyspec.com/MIL-HDBK/MIL-HDBK-0300-0499/MIL-HDBK-338B_15041/):

| Failure mode | Fraction |
|---|---|
| False indication | 0.48 |
| Fail to operate | 0.29 |
| Spurious | 0.18 |
| Degraded | 0.05 |

**Fighter persistence and latch evidence** (in addition to Q3):
- **F-16 HYD/OIL PRESS caution.** One shared warning light: hydraulic system A or B below a minimum (value not published), or engine oil pressure below its minimum **for 30 s**, a delay that suppresses manoeuvre transients.
- **Intermittent no-fault-found history.** The Thunderbird aircraft had repeated HYD/OIL PRESS write-ups with no fault found in the weeks before the mishap.
- **Generator dropout.** After flameout both main and standby generators dropped offline about 4 s later as RPM decayed, and the EPU auto-started.
- Source: [USAF AIB F-16CM 92-3881 (3 Dec 2025), PDF pp.15, 20–21, 24–25](https://www.afjag.af.mil/Portals/77/AIB-Reports/2025/3DEC25%20ACC%20F-16CM%20AIB%20REPORT.pdf) [TRANSFER: F-16].
- **EPU restore delay.** Power was restored in about 2.5 s, "the typical delay for starting the emergency power unit and for the emergency generator to come on line" — [USAF AIB F-16CM 91-0366, Spangdahlem, 11 Aug 2015, PDF p.21](https://www.usafe.af.mil/Portals/8/documents/Spangdahlem%20F-16%20AIB%20Report.pdf?ver=2016-08-30-033647-423) [TRANSFER].
- **DEEC false-failure record.** Zero false failures in 30 flights / 35.5 FH ([CP-2298 Paper 7](https://ntrs.nasa.gov/citations/19860015878)).
- **AFTI/F-16 false-failure record.** 15 false failures against 1 real failure ([Mackall 1984](https://ntrs.nasa.gov/api/citations/19840012524/downloads/19840012524.pdf)).
- **Helicopter HUMS vibration.** About 70 % detection, with false warnings about 1 per 100 FH ([NASA TM-2004-212883, p.1](https://ntrs.nasa.gov/api/citations/20040082336/downloads/20040082336.pdf)).

**Engine-monitoring false alarms and fault-filter side-effects** [TRANSFER: F110 EMS on F-16; F101 CITS on B-1B] — [AGARD-CP-448 papers 8 and 21 (DTIC ADA203800), pp.8-8 to 8-11 and 21-7 to 21-9](https://archive.org/details/DTIC_ADA203800)
- **F110 EMS false-alarm rates**:

  | Phase | False alarms |
  |---|---|
  | Flight test | 1 per 10 flights |
  | Ramstein | 1 per 3 flights |
  | Later software block | 1 per 14 flights |
  | Target | 1 per 200 flights |

  About 70 % of real faults were isolated to the correct LRU.
- **B-1B CITS (F101)**:
  - Over 132 engine-flights it found 7 real faults and 1 false alarm, at 0.05 codes per engine per flight.
  - The fault filter was lengthened from 3 passes (≈ 0.5 s at 4 Hz) to 6 passes (≈ 1.25 s) to stop nuisance codes.
  - During stalls, core speed then fell below the tested range before 6 passes had been met. **No code was set and the failure data were lost.**
  - Short nozzle transients caused "nozzle off schedule" false alarms that needed a timer.
  - Lesson: lengthening persistence cuts nuisance codes but can hide fast faults.
- **F100 Engine Diagnostic System trial** [TRANSFER: F100 on F-15] — [NASA CP-2190, pp.225–235](https://ntrs.nasa.gov/citations/19810022668):
  - 5 F-15s, 11 engines, ≈ 3,300 engine operating hours, ≈ 900 flights, Langley 1980–81.
  - Events detected 10 Jul–18 Dec 1980:

    | Event | Count |
    |---|---|
    | FTIT spread | 85 |
    | RCVV out of limits | 46 |
    | Vibration | 42 |
    | EEC faults | 24 |
    | Stalls (11 on one engine) | 21 |
    | Scavenge pressure | 9 |
    | Oil pressure | 4 |
    | Overtemperature | 2 |
    | Hot starts | 2 |
    | AB blowout or mislight | 2 |

  - Event-detection accuracy rose from 88.7 % to 99.7 % as the logic matured.
  - FTIT-spread events traced to failed probes Nos. 4 and 5.
- **Pilot-reported radar faults BIT did not detect** ("System 2", n = 2,097) [TRANSFER] — [RADC-TR-81-220, Table 5-4, p.39](https://archive.org/details/DTIC_ADA108752). These can seed synthetic pilot write-ups:

  | Reported fault | Count |
  |---|---|
  | Tracking | 675 |
  | Birds or jamming | 494 |
  | Scan | 323 |
  | No targets | 211 |
  | Inoperative | 185 |
  | RF no-go | 179 |
  | Range error | 30 |

**Tejas (already known, [DIRECT]):**
- DFCC continuous, pilot-initiated and maintenance BIT.
- ADC BIT coverage 90 %.
- CAG: 94 LRUs failed the ATE test pattern although serviceable.
- Mundane systems (BMS, NWS, ECS) failed far more often than the integrated flight control system, which had one channel drop-out reset in flight.

### Inferences
- [ASSUMPTION] **Two calibration regimes for the BIT/false-alarm process**, chosen per scenario (both are TRANSFER-anchored):
  - *Immature or new-type* (F-35 2014–17, F/A-18E/F 2010, legacy radars): mean hours between false alarms 0.1–1 FH; false alarm to valid event about 15–135:1; Cat II about 20–55 % of indications; Cat I about 30 % of true faults; electronic isolation to one LRU 40–85 %.
  - *Mature or specified*: ≥ 50 FH between false alarms; ≤ 1 gas-path EHM false alarm per 1,000 flights (already known); 30–45 % BIT false-alarm rate as a contractual F/A-18E/F threshold.
  - A Tejas Mk1A fleet in its first years should sit between these. Validate against IAF snag logs.
- [ASSUMPTION] **Missed detections are a first-class process.** About 40–60 % of latent EW faults are unreported (GAO). This supplies hidden degradations that the predictive-maintenance layer must find from trends rather than codes.
- [ASSUMPTION] **NFF/RTOK propensity by LRU technology** for the shop-outcome generator: RF ≈ 30 %, digital ≈ 48 %, mixed ≈ 56 %, analog ≈ 63 %, radar assemblies ≈ 25 %.
  - Per-tail rates come from a negative binomial distribution.
  - Repeat write-up within 1 day ≈ 45–50 % after CND/RTOK.

### Gaps
- No Tejas, Su-30MKI, Mirage 2000, Rafale, Typhoon or Gripen BIT false-alarm or NFF numbers beyond the already-known CAG and ADC items.
- F-35 DOT&E diagnostic tables are published only for FY2014–FY2017; FY2021–23 were unreachable.
- Bain & Orwig (F/A-18C > 88 %) was not retrieved; the figure is secondary.
- No AGARD/RTO paper on fighter BIT false alarms was found.
- No fighter subsystem threshold values (psi, volts, degrees) beyond those in Q3 and the F-16 30-s oil-pressure delay.

---

## Q10. Discriminator-relevant texture: published comparisons of simulated vs real flight and sensor data, which signal characteristics differ, and what simulators changed to close the gap

### Takeaway
No fighter-class simulated-vs-real sensor study was found. Studies on UAVs, ground vehicles, engines and bearings agree, in rank order, on what a real-vs-synthetic discriminator will exploit:

1. **Noise floor and high-frequency or vibration content.** Real accelerometer variance was about 11× that of software-in-the-loop (SITL) simulation. Simulators often export noise-free truth.
2. **Noise colour.** Real errors behave as random walk or Gauss–Markov processes with bias instability; white Gaussian noise is the worst-matching model.
3. **Per-unit systematic offsets and model-to-specific-engine mismatch.**
4. **Transient mismatch** while steady state agrees.
5. **Heavy tails and patchiness**, including non-Gaussian vertical gusts.
6. **Multi-rate, irregular timing** versus lockstep simulation.
7. **Flat-lined environment channels** (GNSS noise and jamming indices identically 0 in simulation).
8. **Fault-class-dependent gaps.**
9. **Initialisation artefacts.**

Fixes that worked:
- coloured stochastic sensor models with calibrated covariance;
- re-trimming the model to real steady-state data;
- features based on residuals against a healthy baseline;
- a small real-data fraction (≈ 10 %) or healthy-only real flights for domain adaptation;
- class-specific alignment.

These findings echo the Phalanx DASHlink measurements (quantisation lattices, structured missingness, coloured residuals, per-unit offsets, timing artefacts).

### Cited Findings
- **RflyMAD (multicopter; SIL, HIL and real flights on the PX4 stack)** [TRANSFER: same autopilot-style sensor pipeline; dynamics differ] — [Le et al., arXiv 2311.11340v2, pp.3–5, Table 4](https://arxiv.org/abs/2311.11340)
  - Real data came from ULog; simulated data came from noise-free ground truth. Everything was resampled to 10 ms by interpolation.

  | Training data → real flights | Fault-classification accuracy on real test data |
  |---|---|
  | SIL only | 63 % |
  | HIL only | 55.9 % |
  | SIL + 10 % real | 96 % |
  | SIL + 10 % real + TrAdaBoost | 97 % |
  | SIL + 10 % real + AdaBN | 98.2 % |
  | HIL + 10 % real + adaptation | 99.1 % |

  - SIL→HIL transfer reached 97 %, so simulation-to-simulation gaps are small and simulation-to-real gaps are large.
- **DDCNN (quadrotor propeller faults)** [TRANSFER] — [Tong et al., arXiv 2302.08117, Table IV p.6](https://arxiv.org/abs/2302.08117)
  - The authors attribute the gap to the vehicle body (mounting and installation errors, noise), not the sensors.

  | Method | Accuracy on real flights |
  |---|---|
  | Raw-signal CNN | 52.9 ± 9.0 % |
  | Difference features (faulty minus healthy baseline) | 85.5 ± 4.5 % |
  | Plus domain adaptation using only healthy real flights | 99.1 ± 0.5 % |

  - Larger damage gave a larger train/test offset.
- **PX4 Gazebo SITL vs real quadrotor** [TRANSFER; the paper has internal inconsistencies, flagged by the reviewer] — [Kose et al., Sensors 26(10):3188 (2026), Table 5, §§6.3, 6.8, 6.13](https://doi.org/10.3390/s26103188)
  - Variance ratios, real vs simulated:

    | Channel | Simulated | Real | Ratio |
    |---|---|---|---|
    | Vertical acceleration | 0.458 | 4.985 | ≈ 10.9× |
    | Yaw rate (gyro-z) | 0.065 | 0.077–0.109 | 1.2–1.7× |
    | Motor outputs | — | — | ≈ 1.5× |
    | Vertical velocity | 0.660 | 0.127 | Higher in simulation |

  - Jensen–Shannon divergence 0.39–0.61. Real data have more high-frequency power.
  - GNSS noise and jamming indices are 0 in simulation, against 95–120 and 20–60 in real data.
  - The magnetometer z sign differs between simulation and real data.
  - Effective IMU rate ≈ 132 Hz real vs ≈ 251 Hz simulated (low confidence).
  - Maximum tilt 72° real vs 24° simulated.
- **GPS/IMU sim2real gap (ground vehicle)** [TRANSFER: noise-model lesson applies to aircraft INS/GNSS] — [Caldararu et al., arXiv 2403.11000, Tables I–II, p.4](https://arxiv.org/abs/2403.11000)
  - Metric: a Wasserstein-based gap metric (VEPD) over velocity RMSE and spectral Wiener-entropy differences.

    | Noise model | VEPD | Spectral-entropy distance |
    |---|---|---|
    | White Gaussian | 0.155 (worst) | — |
    | Random walk | 0.043 | 0.0025 (best spectral match) |

  - Adding measurement covariance improved white noise about 8×.
- **Sensor-grounded underwater simulator** [TRANSFER: MEMS IMU and Doppler velocity log] — [Grimaldi et al., arXiv 2608.26888, Figs. 3–4](https://arxiv.org/abs/2608.26888)
  - On 9 h of real data the legacy white-noise IMU (ARW ≈ 1.6×10⁻³ rad/s, negligible bias instability) missed the real bias instability of 10⁻⁵–10⁻⁶ rad/s.
  - The fix added scale factor, misalignment, bias random walk, Gauss–Markov noise, temperature drift, vibration, LSB quantisation and range limits.
  - With white noise only, the velocity log showed negligible 3-h drift; bias random walk reproduced real drift.
- **NASA VIPR on a real turbofan** [TRANSFER: same model-based monitoring method as a fighter EHM] — [Rinehart & Simon, NASA TM-2015-218448, pp.4–5](https://ntrs.nasa.gov/citations/20150000899)
  - Simulator-derived piecewise-linear models showed "notable differences" from real nominal steady-state data and had to be re-trimmed to the specific engine.
  - Real data needed median filtering and outlier removal.
  - A bleed-valve actuator missing from the simulation had to be learned from real data.
  - Performance was good at steady state, with misclassification in transients. Persistence and a start-up blackout were tuned on real healthy data.
- **Atmospheric turbulence: measured vs Gaussian models** [TRANSFER: drives Nz, AoA and air-data texture]
  - Vertical-gust probability densities are distinctly non-Gaussian; longitudinal and lateral are about Gaussian. Spectra fit Dryden at some points and von Kármán at others — [NASA CR-2886](https://ntrs.nasa.gov/citations/19770025195).
  - The Gaussian model underestimates high-velocity gusts; a Gaussian-plus-modified-Bessel process fits better — [Reeves, Joppa & Ganzer 1976](https://ntrs.nasa.gov/citations/19760009986).
  - Patchiness appears in the 4th and higher moments — [Moorhouse & Heffley 1987, §3.2](https://ntrs.nasa.gov/citations/19870012922).
- **Bearing digital twin** [TRANSFER: rotating-machinery vibration] — [Wang et al., arXiv 2606.24954, §3.2, Table II](https://arxiv.org/abs/2606.24954)
  - The simulated envelope and noise floor "systematically deviate" from real recordings, and the gap differs by fault class.
  - Global MMD alignment added only +1.69 accuracy points; class-specific alignment added +6.16 points (to 88.13 %), and the full model reached 90.47 %.
- **ALFA real fixed-wing UAV fault flights** [TRANSFER] Real telemetry is multi-rate and irregular: navigation 20–25 Hz, IMU 10 Hz, wind 2–3 Hz, fault flags about 5 Hz. Ground-truth timing is therefore about ±200 ms — [Keipour et al., arXiv 1907.06268, p.4](https://arxiv.org/abs/1907.06268).
- **X-Plane FOQA-like data** [TRANSFER: simulator artefacts only] — [Nanduri & Sherry, ICNS 2016, pp.1–2, 7](https://catsr.vse.gmu.edu/pubs/ICNS_2016_XPlaneFOQA_IEEE.pdf)
  - 21 parameters every 2 s, against up to 500 parameters at 1 Hz in real flight-data monitoring.
  - Re-initialisation artefacts (a pitch step causing altitude error); wind randomised 0–8 kt.
- **BIT designed for a noise-free world** [TRANSFER] BIT designed for an ideal world produced "failure without a fault" from momentary excursions caused by transients and the environment — [RADC-TR-81-220, p.viii](https://archive.org/details/DTIC_ADA108752). The CAG finding that 94 serviceable LRUs failed ATE limits (already known) is the same phenomenon.

### Inferences
- [ASSUMPTION] **Use the discriminator ranking as a checklist for the Phalanx realism tests**, adding the DASHlink-measured items:
  - per-channel noise and PSD level, especially vibration-coupled channels;
  - noise colour, via Allan deviation and the ACF;
  - per-tail and per-engine offsets;
  - transient-vs-steady residual shape;
  - tail weight (kurtosis, 4σ exceedance);
  - multi-rate timing and jitter;
  - quantisation lattices;
  - structured missingness and validity gating;
  - environment channels that should never be flat;
  - initialisation and power-up artefacts.
- [ASSUMPTION] **Generate faults as differences from a healthy per-tail baseline.** Evaluate any PHM model trained on Phalanx data with baseline-residual features, because these transfer from simulation to real data far better than raw signals.
- [ASSUMPTION] **Couple the BIT layer to the sensor texture.** BIT tests should run on the same coloured, heavy-tailed sensor model; m-of-n false-alarm mathematics that assumes independent samples will understate false alarms when the noise is coloured (RADC p.51).

### Gaps
- No fighter or turbofan-fighter simulated-vs-real sensor comparison was found.
- No quantitative jitter, latency or dropout comparison between simulator and real flight logs.
- The N-CMAPSS paper (MDPI) returned 403, so its realism statements were not checked.

---

## Synthesis (required closing items a–f)

### Takeaway
The Phalanx sensor, signal-validation and fault layers can now be parameterised mostly from released fighter or fighter-adjacent evidence rather than from assumption. Three caveats remain:
- The F404-IN20/Tejas-specific values (FADEC thresholds, air-data SSEC and vane dynamics, fuel-gauging class, oil and vibration limits, fleet fault statistics) are still not public. They must remain declared, swept parameters with TRANSFER priors.
- Several important behaviours exist only as qualitative or single-case evidence. The examples are nozzle actuator fault traces, accumulator and strut leak rates, and chip-light nuisance rates.
- Discriminator studies show that colour, level, per-unit offsets and timing texture matter more than any single noise σ.

### Cited Findings — (a) Key findings
1. **Air data is lightly damped, Mach-structured and configuration-dependent.** Sources: Q1 (TN D-8242; TM-101714; AGARD-AG-300; Gracey RP-1046; JOAST 67(2A); DSJ 56(1); DSJ 60(6)).
   - Boom vanes: f_n ≈ 0.11–0.21 Hz per m/s EAS, ζ ≈ 0.04–0.10.
   - Upwash 6–10 %, bias 0.4–0.7°, boom bending 0.06–0.1°/g, misalignment steps 0.1–0.3° after maintenance.
   - Static-source error jumps to 0.08–0.16 q_c just below M 1 and then collapses. Pneumatic lag grows ×4.3 at 40 kft.
   - TAT recovery factor 0.977–0.994 with ±0.015 unit spread; de-icing heater error ≥ 0.2 °C.
   - Tejas-direct: heater-flag-dependent DHE/SHE tables; an undercarriage-dependent air-data error; sensors voted out.
2. **Fuel quantity is an attitude- and specific-force-dependent estimate, not a measurement.** Sources: Q2 (MIL-G-7940C, MIL-G-26988C, ADA091758, ADA092907, US 5,138,559, AGARD-AG-160 v3).
   - Errors: Class I ±2 % near empty / ±6 % near full; ≤ 1 % FS attitude error within ±10°; ≤ 2 % or 10 gal unmeasured per tank.
   - Density compensation leaves 1–1.3 % (2σ) residual, or 2–5 % with water, fungus or stratification.
   - F-16 indicator response ≈ 6 s.
   - Fault handling: one failed probe → reconfigure; two → hold.
   - These mechanisms reproduce the Tejas zoom-climb false low-fuel warning.
3. **Fuel flowmeters have type-specific texture.** Turbine meters: 10 ms, ±2 %. Angular-momentum meters: 300 ms update, ±0.9 % cruise and worse at the ends of the range, about 50 % of removals unconfirmed. Engine flow ranges are 50–140:1, and AB flow is not measured in flight on the CF-18 (Q2).
4. **Engine-control signal validation is evidence-based now** (Q3: CP-2298, TM-86735, TP-2925, TM-89880, TM-101396, TP-2857).
   - Checks: range check; dual-channel compare with the safer value selected; synthesised-value compare with wide tolerances (25 % steady / 45 % transient).
   - Persistence: 4 iterations ≈ 62 ms (FCS); 25 steps = 0.5 s (diagnostics); heal after 10 good frames.
   - Accommodation changes the plant: AB inhibited, nozzle closed, vanes cambered, N2 limit −1,000 rpm, BUC with lower idle N2.
   - Real failures were often undetected or mis-detected: a trapped PS2 drifted undetected over 20,000 ft of climb; a vented PB caused a false stall and sub-idle rollback; a scaling wrap-around hid a failed-high PS2.
   - F404 FADEC FICA substituted up to three sensors at a 10 ms update.
5. **Thin sensor classes are bounded by MIL specifications and programme data** (Q4).
   - Oil pressure: ±1.5–2 psi legacy or ±0.25 % FS modern; τ ≈ 1–4 s; the transmitter was the top F404 IFSD cause.
   - EJ200 vibration: per-speed-band tracked orders with datum-relative limits; blade-tip loss +40 % 1EO; rotor-bow start ≈ 20×.
   - Tyre pressure: ±2.5 psi, with large temperature bias.
   - Brake RTD: ≥ 3 h to settle.
   - Power quality: MIL-STD-704F limits.
6. **Snapshot scatter decomposes into three layers** (Q5): measurement ≈ 0.1–0.5 %; real build or engine spread ≈ ±1 %; and VG-rig-driven thrust scatter ≈ ±5 % at fixed N2 on F404-400 (cut 2–3× by VG correction). The F404 acceptance window is ±1 %.
7. **Fighter engine faults have characteristic channel orderings and code cascades** (Q6).
   - Pop stall: PS3 collapse with 0.2–3 s recovery.
   - Mechanical stall: N falls while T5 rises; codes follow over 2–13 s.
   - Bird damage: stall cycling every 3–5 s.
   - AB: 2.5 s no-light timeout; 60 Hz rumble before blowout; 1 quickfill stall per 994 lights; 1–2 Hz nozzle-loop limit cycle.
   - Fuel: shut-off valve sub-idle hang at 70 % for 3 min.
   - Starts: hung relight with T5 rising about 12 °C/s at a flat 35 % N2.
   - F404 bleed: −2–3 % thrust per lb/s.
8. **Bearing degradation is a three-phase, debris-observable process; other mechanical faults are not** (Q7).
   - Bearing: incubation 1–40 h on rigs, 50–100 FH in the field; growth 0.08–0.34 mm/h; knee at one element spacing; debris 2–50 mg/mm.
   - SOAP is often blind to spalls; F404 routine SOAP was deleted in 1984 in the USN.
   - Oil starvation (F110 AGB) kills in about 5 EOT h with no precursor.
   - Gear cracks are vibration-only, 42–103 h ahead.
   - F110 oil-consumption limit ≈ 0.355 L/h.
9. **Utility degradation has field-calibrated monitoring curves** (Q8).
   - Pump case-drain ΔT: flat about 5 months, then to a 19 °C limit at about 11.5 months.
   - Case-drain filter ΔP: 6–12 → > 14 psi in about 4 weeks.
   - Contamination: ×4 / ×14 wear multipliers.
   - F-15 carbon brakes: 1,400 LPO.
   - Tyre wear: 0.1–0.6 kg/km vs slip.
   - ECS heat exchangers foul in 3–9 months at dirty sites.
   - Diode-fault electrical signatures are documented. Accumulator, strut and ACM rates are still missing.
10. **BIT in fighters is noisy, misses faults and is persistent across flights** (Q9).
    - F-35: 0.09–1.03 FH between false alarms (requirement 50); 14–1,079 false alarms per valid event.
    - F/A-18E/F: BIT false-alarm rate 33.5–86 %.
    - Legacy radars: 22–53 % Cat II; 28–38 % Cat I.
    - NFF by LRU technology: 29.5–63 %.
    - BIT-ready EW pods had faults 39–58 % of the time.
    - Cat II alarms persist ≥ 3 flights in 10–18 % of cases.
    - m-of-n filters cut false alarms 2–4 orders of magnitude, but long filters can lose fast faults (B-1B).
11. **Discriminators exploit level, colour, offsets, transients, tails, timing and flat channels** (Q10). Healthy-baseline residuals and a small real-data fraction close most of the simulated-vs-real gap.

#### (b) Updated sensor-texture parameter table (newly covered classes)
Tags: T = TRANSFER, D = DIRECT, A = ASSUMPTION. Sources are given in Q1–Q4.

| Sensor class (Tejas/IN20 use) | Static accuracy / bias | Resolution / noise | Drift / aging | Dynamics / latency | Environmental and installation terms | Failure / artefact modes | Tag | Key sources |
|---|---|---|---|---|---|---|---|---|
| AoA/AoS vane (AOAV, NADP vanes) | Calibrated residual ±0.2° sub / ±0.3° super; float ±0.05° | FDR-class 0.044°/LSB (measured, airliner) | Pot wear gives calibration drift; bearing wear adds buzz and ζ | 2nd order, f_n 0.11–0.21 Hz per m/s EAS (≈ 14–40 Hz); ζ 0.04–0.10 boom (falls with altitude) or viscous production (unknown) | Upwash 6–10 % (noseboom) or SADP slope ≈ 1.5; bias 0.4–0.7°; shock-crossing step ≈ 1° at M 1.1–1.2; bending 0.06–0.1°/g; misalignment step 0.1–0.3° per maintenance | Buzz near M 1; blanking at high β (side probe); voted out (Tejas); heater fault → icing | T + D (layout, voting, heater monitor) | TN D-6193; TN D-8242; TM-101714; AG-300; TP-2857; DSJ 56(1), 60(6) |
| Static/total pressure (pitot-static, ADC) | ADC ±15 ft SL → ±80 ft at 50 kft; CAS ±4 km/h ≥ 200 km/h; Mach ±0.001–0.002 | ARINC 429: 1 ft; 0.0625 kt | Transducer 0.1 % FS ± 0.2 %/°C outside 35–70 °C; moisture offsets (already known) | Lag λ_SL 0.05–0.35 s × (μ/μ_SL)/δ (×4.3 at 40 kft) + 0–0.1 s delay; flight lag up to 3–4× ground | Δp/q_c: noseboom +0.03–0.07 → 0.08–0.16 at M 0.95–1.0 → ~0.01; side vents −0.03 to −0.10 with fluctuation at M 0.97–1.0; gear-dependent (Tejas); sideslip −0.015 q at 5° | Transonic ambiguity (0.02 M band); blockage (λ ×N); leak; resonance saturation bias | T + D (gear dependence) | Gracey RP-1046; AG-300; TN D-7819; TM-101736; JOAST 67(2A); DSJ 56(1) |
| ADC output stage | — | Altitude 16–20 Hz; Mach/CAS 8–20 Hz; TAT 2 Hz | — | ḣ filter τ ≈ 1–2 s, varying by ADC type (2 s lag between designs); inertial/air-data skew 30–110 ms; FCS sampling 50–64 Hz, AA 20–32 Hz | — | Validity gating; voted out | T | AC32 manual; JOAST 67(2A); TP-2857; TM-104314 |
| Total air temperature probe | Recovery factor 0.977–0.994 (M 0.5–1.6); unit spread ±0.015; flight k below tunnel by ~0.006 | 0.25 °C (ARINC) | — | τ ≈ 1.3–2.3 s (de-iced), ∝ 1/√ṁ, two-exponential | DHE 0.2 °C floor, ≈ 1.3 °C at Z = 0.1, ≈ 6.5 °C at Z = 0.04 (heater on only); self-heating ∝ 1/p_T² | Heater fail → DHE off plus icing (+10–20 °C errors); correction-table/flag mismatch (Tejas defect) | T + D (DHE/SHE tables) | AG-160 v2; NCAR 2022; TM-101714; DSJ 56(1) |
| Fuel quantity (capacitance, per tank) | Class I ±4 % ind ±2 % FS (±2 % empty / ±6 % full); II ±2 % / ±0.75 %; III ±1 % / ±0.5 %; attitude ≤ 1 % FS (σ 0.35 %) within ±10° | Dead spot 0.1–0.2 % FS; F-16 10–20 lb steps; F-15 ≈ 0.14 % FS | Probe capacitance +0.5–2 % after water, humidity or fungus; microbial noise | F-16 indicator 5.8–6.6 s full scale; filter τ 15/45/60 s (transport); 5 s compute cycle; spec ≤ 60 s | Plane follows specific force; unmeasured ≤ 2 % or 10 gal per tank; density residual 1–1.3 % (2σ), ratio varies 3 % over −55 to +55 °C; stratification ≤ 5 % | Unwetted probe → low or invalid (Tejas zoom-climb); 1 probe out → reconfigure; ≥ 2 → hold; failed gauge reads below zero | T + D (probe ±3/5 µs, zoom-climb case) | MIL-G-7940C; MIL-G-26988C; ADA091758; ADA092907; US 5,495,745; US 5,138,559; DDP 10090 |
| Fuel flow (main) | Turbine ±2 % (+2 % at fuel temperature extremes); angular momentum ±0.9 % of point in cruise, worse at idle (+) and maximum (−); RSS fuel-used ±0.5–2.1 % | Turbine repeatability < 0.1 %; indicator ±10–100 pph | Bearing wear (turbine); spring aging (angular momentum) | Turbine τ ≈ 10 ms; angular momentum 80 ms rise, **300 ms update** (older 0.75–2 s settling) | Range 10:1 per turbine meter vs 50–140:1 needed; viscosity hump at low flow; installation shift ≤ 5 % | Erratic AM output (bearing); jammed rotor; ~50 % of AM removals unconfirmed | T + D (F404 pulse-rate meter) | AGARD-AG-160 v3; HAFF; ADA104364; ADA196265 |
| FADEC Wf estimate (metering-valve LVDT) | Unquantified ([A] 2–3 %) | LVDT-limited | ΔP-regulator wear, fuel SG and temperature | Fast | — | LVDT faults → Wf estimate error | T/A | US 9,243,565; US 6,389,816 |
| Oil pressure (psid) | ±1.5–2.0 psi legacy (±2.5–4 psi at extremes); modern ±0.25 % FS | Pointer oscillation 2 psi under vibration | 0.1 % FS/yr | τ ≈ 1 s (spec) to ≈ 4 s (cold oil) | 20–160 g engine vibration environment (F404) | False-low dominant (transmitter top USN F404 IFSD cause); caution needs 30 s persistence (F-16) | T + D (F404 environment) | MIL-T-5796D; MIL-PRF-25435D; FCI; CR-191195; Glenny 1989; AIB 92-3881 |
| Oil temperature | Gap ([A] Pt RTD ±1–2 °C) | — | — | [A] τ several s | — | — | A | — |
| Engine vibration (casing accelerometer → velocity) | Datum per engine; F404 limits 1.0–1.5 ips steady, 2–5 ips transient (already known) | 512 samples at ≈ 2.5 kHz; 1EO NL/NH by DFT over 10 revolutions | Datum re-baselined after maintenance | 500 ms processing cycle; 2 Hz study data | Speed-band (100 bands) and manoeuvre (g, gyroscopic) dependence; 35 Hz airbrake buffet | Blade-tip loss +40 % 1EO; rotor-bow start ≈ 20×; surge 95 mm/s pk-pk; charge-amp saturation; open circuit flat-line | T | ADP014124; DSTO-TN-0530 |
| Hydraulic pressure | ±0.25 % FS (≈ ±0.9 bar at 280 bar) | — | 0.1 % FS/yr | 10 ms | — | Lead breakage, connector pins | T | FCI AS-PT; MIL-PRF-25435D |
| Generator/bus current and voltage | [A] ±1–2 % FS; MIL-STD-704F limits as validity bounds | CT sampled ≈ 1 µs (GCU) | — | — | Ripple and FM generated physically | CT cable intermittent → false differential trip; stuck = zero noise, offset = keeps noise | T | PHM 2009 (Vanderbilt); ADAPT; MIL-STD-704F |
| Brake temperature (RTD, if fitted) | OVHT > 400 °C; ΔT ±65 °C vs mean | — | — | Lag of minutes; ≥ 3 h to settle | Probe in a gap | Dragging or inoperative brake via ΔT | T | ADA127220; Mortimore 2007 |
| Tyre pressure | ±2.5 psi (SmartStem); spec ±3.5 psi | — | Leak ≤ 5 %/24 h acceptable | Ground-read | +19 % at 200 °F, −23 % at −65 °F (from 70 °F); 1 % per 3 °C | False-low 15–20 per 1,000–1,500 landings (leads, pins, carbon shunt) | T | ADA127220; Crane; Michelin CSM |
| FADEC-validated engine channels (selected/used value) | Synthesised substitute after accommodation; ADIA floor N2 ≈ 350 rpm, PT4 30 psi, PT6 5 psi, FTIT 200 °R | Lower noise than raw (model output) | Model bias grows in transients | Update 10 ms (F404 FADEC FICA), 40 ms (ADIA); detection 0–5 s | Wide transient tolerance (45 %) | Step or flag at detection; secondary plant effects (Q3) | T | CP-2298; TM-86735; TM-89880; TM-101396 |

#### (c) Updated fault-signature / degradation-rate table
"NM ref" points to `not_measured_states.csv`.

| # | Fault / degradation | Physical state change | Signature across channels (direction, magnitude, time scale) | Detection by BIT / monitoring | NM ref | Source (tag) |
|---|---|---|---|---|---|---|
| 1 | Pop stall from inlet distortion | HPC transiently past stall line; distortion 0.22–0.25 circumferential | PS3 85 → 10–15 psia in ≤ 1 sample, ≈ 75 psia within 0.3 s, baseline ≈ 3 s; fan discharge 15 → 5 psia; inlet Pt spike; only at AoA > 70° with high yaw rate | Stall code (PS3 rate); self-recovers | NM.ENG.HPC_HEALTH (margin) | TM-104328 (T: F404-400) |
| 2 | Mechanical stall leading to stagnation (blade liberation, reversed or turned vane) | Blade loss, flow/efficiency collapse | N1 95 → 15 % in 0.6 s; N2 → sub-idle; **T5/FTIT rises**; codes: stall +2 s, overtemperature/mode/hybrid +4 s, T sensor fail +10 s, flameout/sub-idle +13 s; generators off, EPU +16–19 s | Codes after onset; no precursor (reversed vane 40.9 h; turned vane not borescope-visible) | NM.ENG.BLADE_CRACK | AIBs 88-0433, 90-0771, 87-0358 (T: F110/F100) |
| 3 | FOD/bird with stall cycling | Fan/HPC damage, imbalance | Stalls every 3–5 s; thrust ≈ 96 % MIL held ≥ 2.5 min; damage logic caps power; vibration ↑ | Stall codes; fan-damage logic | NM.ENG.FAN_HEALTH | AIB 88-0165 (T: F100) |
| 4 | HPC damage (F404) | ηHPC −5 % equivalent | Take-off PS3 rise lags twin by 1.5–2 s, plateau −4 pts; PS3/P1 +8 %, Wf +8–14 % at fixed N2 | Ground trend (take-off indices) | NM.ENG.HPC_HEALTH | AGARD-CP-448 P7 (T: F404-400) |
| 5 | Bearing failure with stall/vibration ceiling | No.4 bearing failure | Vibration at all powers; repeat stalls above ≈ 85 % RPM; RPM ↓ with FTIT ↑; airstarts fail | Vibration and stall codes | NM.ENG.BEARING_SPALL | ExecSum 2006/2001 (T: F110) |
| 6 | AB no-light | Ignition/flame-holding failure | No LOD signal 2.5 s after request; AB lever reverts to intermediate; up to 3 retries (transient > 30 s) | AB fault code | NM.ENG.AB_SPRAYBAR | TM-86745 (T: F100) |
| 7 | AB rumble blowout | Combustion instability at segment 4 full flow | PAB 60 Hz, 2 psi pk-pk oscillation, then blowout; band 30–200 Hz | Blowout detection (ΔEPR, ΔAJ, LOD) | — | CP-2298 P11; AFAPL-TR-78-82 (T: F100) |
| 8 | Quickfill stall | Segment-fill pressure spike ≈ 300 psi | Pressure pulse → fan stall; rate 1 per 994 segment-1 lights (high altitude, low speed) | Stall code | — | CP-2298 P11 (T) |
| 9 | Nozzle EPR-loop limit cycle | Marginal loop stability (gain/dynamics mismatch, actuator degradation) | AJ oscillation 1–2 Hz, ±0.1–0.2 ft²; PAB ±2.5 psi; N1 oscillation; alternate stalls/blowouts; intermittent | Not detected as a fault; operability event | NM.ENG.NOZZLE_HW | CP-2298 P12; TM-85914 (T) |
| 10 | Nozzle feedback failure | AJ position sensor fault | Nozzle driven fully closed; AB inhibited (F100); F404 FICA maintains thrust via N2 reference | FDA flag | NM.ENG.NOZZLE_HW | CP-2298 P7; TM-101396 (T) |
| 11 | Nozzle flap cracking | Outer flap cracks 4–16 mm | No gas-path signature; found at ~25 % of a 330-h durability test | Inspection | NM.ENG.NOZZLE_HW | KDTQ 2006 (T: F404-102) |
| 12 | Main fuel shut-off valve partly closed | Fuel flow restriction | RPM stuck ≈ 70 % sub-idle ≈ 3 min, no throttle response, **no caution**; then ≈ 20 % | None until rollback | — | AIB 92-3886 (T: F110-129) |
| 13 | Main fuel control over-fuelling | Fuel schedule bias | Take-off fuel ratio Wf/PS3 ≈ 102–105 % vs 89–92 % at ≈ 80 % N2; flameout on start-up | Ground trend index | — | AGARD-CP-448 P7 (T: F404-400) |
| 14 | Hung relight / start | Under-fuelling or low N2 at light | N2 flat ≈ 35 %; FTIT ↑ ≈ 12 °C/s (460 → 640 °C over 15 s); nozzle ≈ 90 % open | Hung-start detection (rate); pilot | NM.SPS.JFS_HEALTH | AIB 92-3890 (T: F100-229); CP-2298 P8 |
| 15 | Hot start | Over-fuelling → compressor stall during light | FTIT overshoot; stall; DEEC trims fuel above ≈ 760 °C | Overtemperature code | — | CP-2298 P8; TM-85900 (T) |
| 16 | Flameout (bird/FOD), FADEC relight | Combustion loss | T5 dips then rises; NH falling; PS3 collapse; flameout code set and cleared when T5 recovers; ignition held | FADEC flameout code | — | SHK RM 2019:02 (T: RM12) |
| 17 | Bleed leak or over-extraction | Bleed fraction ↑ | Thrust −2–3 % per lb/s; T5/N2 shift | Model residual | — | TM-104247 (T: F404-400) |
| 18 | Sensor: trapped inlet static pressure (iced or plugged) | Frozen PS2 | Drift error grows with altitude; undetected until 25 % residual (20,000 ft of climb); EPR high, fan stall margin low | Synthesis-compare (late) | NM.ENG.SENSOR_TRUTH | TM-86735 (T: F100) |
| 19 | Sensor: burner pressure line broken (vented) | PB reads low | False stall detected → fuel cut → sub-idle rollback, no throttle response | Mis-detected as stall | NM.ENG.SENSOR_TRUTH | TM-86735 (T) |
| 20 | Sensor: pressure fails high in range | PS2/PT6M high | Nozzle opens (EPR trim), thrust "much lower", FTIT low; flag only when out of range (> 110 psi) | Range check (late) | NM.ENG.SENSOR_TRUTH | TM-86735; CP-2298 P7 (T) |
| 21 | Sensor: dual T5/FTIT open | Harness open | Driver goes to 0 or full scale; synthesised FTIT; N2 max −1,000 rpm | Range check | NM.ENG.SENSOR_TRUTH | TM-86735 (T) |
| 22 | Bearing spall (main shaft or AGB) | Spall length L: incubation → linear → knee | ODM 2–50 mg per mm spall, 2.5–4 counts/mg; chip light hours to tens of hours before knee; HF vibration ×2–6 RMS non-monotonic; SOAP often flat; growth 0.08–0.34 mm/h; incubation 1–40 h rig / 50–100 FH field | Chip detector, ODM, envelope vibration | NM.ENG.BEARING_SPALL | TM-2011-217117; TM-2006-214082; AFRL 2009; PHM 2009; GasTOPS ERF (T) |
| 23 | Oil starvation (AGB/PTO jet blocked) | Lube film lost | No debris or JOAP precursor; ≈ 5 EOT h to failure; N2 indication 0 in ≈ 2 s; oil pressure and generators lost; false hung JFS restart | None predictive | NM.SPS.AMAGB_WEAR; NM.ENG.OIL_CONDITION | AIB F-16C 87-0242 (T: F110) |
| 24 | Gear tooth crack | Crack length (Paris) | No debris; TSA kurtosis/phase ↑ 42–103 h before failure; final growth ~20 min | Vibration TSA only | NM.SPS.AMAGB_WEAR | McFadden 1985 (T) |
| 25 | Sliding/race wear, race spinning | Wear volume | SOAP Fe slope 0.02–0.07 ppm/h normal → 1–11 ppm/h for 1–20 h; F404 abnormal ≥ 15 ppm or +3 ppm/10 h | SOAP/JOAP | NM.ENG.OIL_CONDITION | ARINC 1974; JOAP 2013 (T: F404 family) |
| 26 | Carbon-seal wear / oil leak | Leak rate | Oil consumption → limit (F110 0.355 L/h; J85 0.24 L/h); smoke | Servicing log, oil level | NM.ENG.SEAL_WEAR | JOAP 2013 (T) |
| 27 | Hydraulic pump wear | Internal leakage ↑ | Case-drain ΔT above 7–31 °F band → 35 °F limit: flat 5 mo, threshold ≈ 11.5 mo; terminal case-drain filter ΔP 6–12 → > 14 psi in ≈ 4 wk | Trend message; replace ≤ 3 days | NM.HYD.PUMP_EFF | US 12,265,000; US 11,078,935 (T) |
| 28 | Hydraulic contamination | NAS class | No flight-hour trend; pump wear ×4/×14; servo null leak 3 → > 20 % | Sampling every 6–12 mo or 1,500 h | NM.HYD.FLUID_CONTAM | Pall 1996 (T) |
| 29 | Accumulator gas loss | Precharge ↓ | P0 ∝ T; decay-time ratio above/below precharge shortens; fewer brake applications | Decay test | NM.HYD.ACCUM_PRECHARGE | US 8,494,789; US 5,655,569 (T; rate ≥ 1 %/yr lower bound) |
| 30 | Generator diode open / short | Rectifier fault | Open: field current ↑ tens of %, fundamental/6th-harmonic ratio shift; short: very large field current, ripple ↑ amplitude ↓ frequency, GCU trip | GCU | NM.ELEC.GEN_HEALTH | US 9,910,083; US 4,486,801; EP 2,077,613 (T) |
| 31 | CSD/IDG wear (if fitted) | Speed-regulation lag | Frequency fluctuation at idle or load step → disconnect | GCU; 3,000 FH check | NM.ELEC.GEN_HEALTH | Airbus Safety First 2025 (T) |
| 32 | ECS heat-exchanger fouling | Fouling resistance ↑ | Ram ΔP ↑, effectiveness ↓, pack outlet temperature → > 260 °C shutdown; 3–9 months at dirty sites vs ≈ 18 months clean; first on hot-day ground runs | Overheat shutdown | NM.ECS.HX_FOULING | Wright 2018 (T) |
| 33 | Carbon brake wear | Stack mass ↓ | 1,400 LPO (F-15C/D 3-rotor); per-stop temperature ↑ as mass ↓; brake fluid 108 °C after a normal stop | Wear pin | NM.LG.BRAKE_WEAR | Collins F-15 (T) |
| 34 | Tyre tread wear | Tread mass ↓ | 0.1–0.6 kg/km at slip 0.1–0.3; 0.04–0.47 kg/km at yaw 4–24°; shoulder/centre patterns | Visual | NM.LG.TYRE | NASA TP-1569; Michelin (T) |
| 35 | Tyre leak | Pressure ↓ | ≤ 5 %/24 h acceptable; 90–94 % inspect; < 90 % remove; temperature bias ±20 % | Daily check; TPMS | NM.LG.TYRE | Michelin; ADA127220 (T) |
| 36 | Strut gas/oil loss | Gas moles / oil volume ↓ | Landing pressure–stroke coefficient shifts (2 % oil loss detectable); extension ↓ | Servicing check | NM.LG.STRUT_SERVICE | US 9,285,007 (T; no rate) |
| 37 | Air-data probe misalignment after maintenance | Boom/radome alignment | α/β offsets step 0.1–0.3° | Flight-test calibration | NM.AD.VANE_FRICTION / NM.AD.TRANSDUCER_DRIFT | TM-101714 (T) |
| 38 | AoA vane bearing wear | Friction ↑ | Buzz near M 1; ζ ↑; drift | Voting mistrack | NM.AD.VANE_FRICTION | NACA RM L9F28a; TM-101714 (T) |
| 39 | Probe/vane heater failure | DHE source off | TAT correction mismatch; icing risk → frozen or large error | Heater monitor (Tejas) | NM.AD.HEATER_ELEMENT | DSJ 56(1) (D); AG-160 v2 (T) |
| 40 | Fuel-probe contamination | Probe capacitance drift | +0.5–2 % quantity bias, noise; worse at low fuel | Gauging BIT (partial) | NM.FUEL.PROBE_DRIFT | MIL-G-26988C; NASA TM-87706; US 5,138,559 (T) |
| 41 | Oil-pressure transmitter fault | Transducer/line/connector | False-low reading (vs true pressure normal); stuck or noisy | Caution after 30 s; may cause precautionary IFSD | NM.ENG.SENSOR_TRUTH | Glenny 1989; MIL-T-5796D (T: F404-400) |

#### (d) Signal-validation / BIT logic template with evidence
For each validated channel *c* (dual-channel where the IN20 FADEC or Tejas DFCC provides it):

1. **Acquisition.** Sample at the channel rate behind an anti-alias filter: 50–64 Hz FCS-class with 20–32 Hz AA; 10–40 ms FADEC update (F404 FICA 10 ms; ADIA 40 ms); 1–8 Hz for slow utility channels. *Evidence:* TP-2857, TM-104314, TM-101396, TP-2925.
2. **Range (hard) check.** Fail if x_c < min_c or x_c > max_c, with min/max at physical ranges (e.g. TT2 −110 °F; PT6M 110 psi). Count n_range consecutive frames before latching:
   - FCS: 4 frames ≈ 60 ms;
   - FADEC pressure: "specified number of cycles" (value unknown; [A] 3–5 frames);
   - J85: 4 consecutive out-of-range *rates*.
   - *Evidence:* CP-2298 P7; TP-2857; TM-101396.
3. **Rate check.** Fail if |dx/dt| exceeds a physical bound for 4 consecutive frames. *Evidence:* TM-101396 (J85, TF30, PW2037).
4. **Cross-channel (soft) check.**
   - If |x_A − x_B| > tol_c: use the safer value (higher temperature or speed), set a soft-fail flag, and do not average.
   - If both are in range and agree: average.
   - If one is out of range: use the other.
   - If both are out of range: hold the last good value and enter reversion.
   - tol_c ≈ 2σ_c (NASA dual-channel) or 15 % FS + rate term (AFTI surfaces); persistence 25 steps / 0.5 s (diagnostics) or 4 frames (FCS).
   - *Evidence:* TM-86735; CP-2298 P7; TM-2008-215228; TP-2857.
5. **Analytical (synthesis/model) check.**
   - Compare x_c with x̂_c from a synthesis or model. Tolerance is 25 % steady and 45 % transient for parameter synthesis (DEEC), or an adaptive threshold that expands in transients (ADIA: Mtran 4.5, τ 2 s).
   - Minimum detectable faults are about ADIA's: N2 bias 350 rpm, drift 100–125 rpm/s; PT4 14–30 psi; PT6 3–5 psi; FTIT 200 °R.
   - Isolation via the residual ratio against the threshold. Heal after 10 good frames below 10 % of the hard threshold.
   - *Evidence:* TM-86735; TP-2925; TM-89880.
6. **Accommodation (plant-changing).**
   - substitute x̂_c (≤ 3 simultaneous substitutions on F404 FICA);
   - inhibit dependent functions (AB, nozzle trim, stall detection);
   - force actuators safe (vanes cambered, nozzle closed);
   - reduce limits (N2 −1,000 rpm);
   - on a second "like" failure or a processor fault, transfer to a reversionary or backup mode (lower idle N2 at altitude; stall-free ramps need ≥ 5–7 s at low idle N2).
   - *Evidence:* CP-2298 P7, P9; TM-101396.
7. **Physical-event monitors that can be fooled by sensor faults.**
   - Stall detection (PS3/PB rate);
   - blowout detection (ΔEPR, ΔAJ, LOD);
   - flameout detection (T5 low + NH falling; clears when T5 recovers; ignition held);
   - hung-start detection.
   - A failed sensor can trigger the wrong recovery (vented PB → false stall → sub-idle).
   - *Evidence:* TM-86735; SHK RM 2019:02; CP-2298 P3.
8. **BIT families.**
   - PBIT at power-up: Tejas FBW about 10 min (prototype); AFTI DFCS about 2.5 min; radars 3–5 min.
   - CBIT every frame: watchdog, clocks, RAM/ROM checksums, A/D wrap-around, torque-motor sum/difference, open thermocouple, loop tracking.
   - IBIT/MBIT on the ground with weight on wheels.
   - *Evidence:* CP-2298 P3; Mackall 1984; RADC-TR-81-220; already-known Tejas DFCC BIT.
9. **Exceedance and caution logic.** A limit plus persistence (oil-pressure caution 30 s; IECMS "several iterations"). Latch an event record with 5 s pre / 25–35 s post (already known). Use the PFL/MFL split.
10. **False-alarm and coverage process** (for synthetic code streams).
    - Per-test false-fail probability from a coloured-noise threshold model (±3σ → 0.26 % per test if independent).
    - Debounce sized from RADC Table 5-8 (3-of-4 cuts 454/h to 0.9/h for 100 signals at ±2σ), applied on non-overlapping windows.
    - Cat II persistence histogram: 67–81 % one flight, 10–18 % ≥ 3 flights.
    - Coverage below 100 %: missed-fault pool 40–60 % for EW-class LRUs.
    - Sympathetic code cascades and configuration-conditional nuisances.
    - Software-update code bursts (×10).
    - Maturation decay (> 50 → about 5 messages per flight).
    - Two calibration regimes: immature (0.1–1 FH between false alarms) and mature (≥ 50 FH; ≤ 1 per 1,000 flights for gas-path EHM).
    - *Evidence:* Q9.
11. **Known failure modes of the validation logic itself** (inject deliberately):
    - tolerance too wide → late or no detection;
    - scaling/wrap-around bug → failed sensor accepted;
    - persistence too long → fast fault ends before latch, code lost (B-1B);
    - asynchronous channel skew plus noise → false channel failures (AFTI: 15 false vs 1 real);
    - common-mode faults that defeat voting (already known: B-2 moisture, F-35 WoW ice).

### Inferences — what to change in the generator now
- [ASSUMPTION] Replace each "noise σ" with the layered model (per-unit offset, coloured process, quantisation, regime multiplier; see `empirical_dashlink_texture.md`) plus the class-specific physics above:
  - air data: vane second-order dynamics, Mach-structured SSEC with a transonic band, pneumatic lag scaling, TAT recovery and DHE;
  - fuel: specific-force plane fit with unwetting;
  - flowmeters: type-specific held updates;
  - oil pressure: false-low weighting.
- [ASSUMPTION] Implement the validation chain of (d) as an explicit layer between sensors and the FADEC/DFCC model, so that sensor faults change actuation and recorded fault codes have realistic latency, persistence and secondary cascades.
- [ASSUMPTION] Use (c) rows 1–21 as the engine fault library and rows 22–41 as the mechanical/utility degradation library. Each row maps to an NM state in `not_measured_states.csv`, and validation targets are the cited time scales and magnitudes.

### Gaps — (e) Remaining gaps (priority order)
1. **F404-IN20 FADEC**: channel architecture, sample rates, thresholds and persistence, synthesis models, fault-code dictionary, stall-recovery and auto-relight logic. None of these is public. Requires GE/HAL/ADA access.
2. **Tejas air data**: vane f_n/ζ, SSEC curve (gear up/down), upwash/bending values, pneumatic line geometry, TAT probe type, ADC/DFCC filter corners and output rates. The ACCS/ADE LCA software-timing paper and NATO RTO-MP-SCI-162-14 were unreachable. MIL-P-26292C and MIL-T-25627 were not retrieved.
3. **Tejas fuel gauging**: accuracy class, probe count per tank, ECFM filter constants, error vs g/slosh; the IN20 Wf transducer type.
4. **Engine fault traces still missing**: failed-open/closed nozzle (command vs feedback); F404 hot or hung start T5 traces; F404/IN20 fault-code latencies.
5. **Mechanical and utility rates**: chip-light nuisance rates per 1,000 EFH (only a limited-distribution source exists); fighter vibration growth rates; accumulator precharge loss; strut leakage; ACM degradation; generator and pump MTBF; filter-indicator statistics; tyre mm per landing beyond the F-16.
6. **Fighter BIT thresholds** for utility systems (hydraulic, generator, fuel cautions in psi/V); Tejas BIT false-alarm and NFF statistics; post-2017 F-35 diagnostic tables.
7. **Production spread** of F404-IN20 (T5 margin, N2 at MIL) and Tejas ECMS snapshot statistics.
8. **Fighter-class simulated-vs-real** sensor comparisons, and quantitative jitter/latency gap studies.
9. **Unverified or secondary items to confirm before relying on them**:
   - the F/A-18C > 88 % BIT false-alarm rate (secondary);
   - the System 1/System 2 radar identities (inferred);
   - Kose et al. 2026 internal inconsistencies;
   - the RAND F100(3) performance-loss OCR;
   - Misawa/Luke AIB figures quoted from the flight manual (indicative only);
   - the AGARD-AG-160 Vol.2 copy (spaceagecontrol) lacking a distribution page.
10. **Conflicts left open**:
    - DEEC fault count 160 (TM-86735) vs 150 (CP-2298 Paper 3);
    - PB tolerance "225 %" (OCR) vs 25 %/45 %;
    - spall rate vs load (TM-2011);
    - time from first chip sign to failure: hours (vendor) vs 36–100 FH (field);
    - angular-momentum flowmeter response 80 ms/300 ms vs 0.75–2 s;
    - F404 Wf transducer type;
    - F/A-18E/F SAR false-alarm 86 % vs 33.5 %;
    - TAT recovery, flight vs tunnel;
    - static-error sign by source location;
    - vane damping, research vs production;
    - F-16 hydraulic caution value not published.

#### (f) Ranked sources (most valuable first, for this gap closure)
1. **NASA CP-2298 (F-15/F100 DEEC), Papers 3, 6–9, 11, 12, and NASA TM-86735.** Fighter engine FDA logic, tolerances, accommodation actions, induced-fault flight results, AB rumble/quickfill/blowout, nozzle limit cycle, airstarts, BUC behaviour. https://ntrs.nasa.gov/citations/19860015878 ; https://ntrs.nasa.gov/citations/19850021650 ; https://ntrs.nasa.gov/citations/19860015882 ; https://ntrs.nasa.gov/citations/19860015883 ; https://ntrs.nasa.gov/citations/19860015879
2. **USAF AIB reports with recorded engine data**: 88-0433 UTTR 2012; 90-0771 Osan 2012; 92-3886 Misawa 2012; 88-0165 Luke 2013; 92-3890 Nellis 2016; 87-0358 Holloman 2024; 87-0242 AGB 2011; 92-3881 (2025). Code cascades, timelines, utility caution logic. https://www.afjag.af.mil/AIB-Reports/ (Wayback for pre-2014).
3. **NASA ADIA (TP-2925, TM-89880) and Merrill's survey TM-101396.** Thresholds, adaptive thresholds, heal logic, minimum detectable faults on a real F100; F404 FICA summary. https://ntrs.nasa.gov/api/citations/19900005796/downloads/19900005796.pdf ; https://ntrs.nasa.gov/api/citations/19870012664/downloads/19870012664.pdf ; https://ntrs.nasa.gov/api/citations/19890004061/downloads/19890004061.pdf
4. **AGARD-CP-448 (1988) papers 7, 8, 21, 25, 26.** F404 take-off signatures and scatter, F110/F101 EMS false alarms and fault-filter effects, T55/T56 snapshot repeatability. https://archive.org/details/DTIC_ADA203800
5. **NASA TM-101714 (F-104 air-data calibration), TN D-8242 and TN D-6193 (vane dynamics), Gracey RP-1046, AGARD-AG-300 Vol.1.** Air-data texture numbers. https://ntrs.nasa.gov/api/citations/19900004912/downloads/19900004912.pdf ; https://ntrs.nasa.gov/api/citations/19760016169/downloads/19760016169.pdf ; https://ntrs.nasa.gov/api/citations/19800015804/downloads/19800015804.pdf ; https://archive.org/download/DTIC_ADA137367/DTIC_ADA137367.pdf
6. **DOT&E F-35 reports FY2014–FY2017 and F/A-18E/F SARs.** Fighter diagnostic coverage, isolation and false-alarm metrics. https://www.dote.osd.mil/Portals/97/pub/reports/FY2014/dod/2014f35jsf.pdf (and the FY15–17 URLs in Q9)
7. **RADC-TR-81-220.** Field BIT false-alarm categories, persistence, root causes, m-of-n mathematics. https://archive.org/details/DTIC_ADA108752
8. **NASA Glenn oil-debris and bearing papers (TM-2011-217117, TM-2006-214082/214380, TM-2004-212883), AFRL-RZ-WP-TP-2009-2208, PHM 2009 Bolander.** Spall-progression timelines and debris mappings. https://ntrs.nasa.gov/api/citations/20110023753/downloads/20110023753.pdf ; https://archive.org/download/DTIC_ADA510506/DTIC_ADA510506.pdf
9. **JOAP Manual Vol III (2013).** F404/F110/F100/F135 oil-analysis limits and consumption limits. https://everyspec.com/USN/NAVAIR/NAVAIR_17-15-50x3_30AUG2013_49353/
10. **MIL-G-26988C, MIL-G-7940C, NADC-78187-60, AFWAL-TR-80-2058, AGARD-AG-160 Vol.3.** Fuel gauging and flowmeter texture. https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-G/MIL-G-7940C_36792/ ; https://archive.org/details/DTIC_ADA091758 ; https://archive.org/details/DTIC_ADA092907 ; https://archive.org/details/DTIC_AD0741610
11. **Boeing pump-monitoring patents US 12,265,000 and US 11,078,935; the Pall contamination paper; Collins F-15 brake sheet; NASA TP-1569.** Utility degradation curves. https://patents.google.com/patent/US12265000B2/en ; https://patents.google.com/patent/US11078935B2/en ; https://www.pall.com/content/dam/pall/aerospace-defense/literature-library/non-gated/white-paper/contamination-control-paper.pdf ; https://ntrs.nasa.gov/api/citations/19800004758/downloads/19800004758.pdf
12. **MTU EJ200 vibration monitoring (ADP014124).** Modern fighter vibration processing and limits logic. https://archive.org/details/DTIC_ADP014124
13. **NASA TP-2857 and Mackall 1984 (AFTI/F-16 DFCS).** FCS redundancy thresholds, persistence, false failures from skew. https://ntrs.nasa.gov/citations/19890014956
14. **Tejas-direct:** DSJ 56(1) 2006 (air-data algorithm, DHE/SHE, gear dependence), DSJ 60(6) 2010 (sensor locations), DSJ 52(1) 2002 (probe location and position error), JOAST 67(2A) 2015 (HAL ADC). https://www.publicationsdrdo.in/index.php/dsj/article/view/1863 ; https://publicationsdrdo.in/index.php/dsj/article/download/582/312/2526 ; https://joast.org/index.php/joast/article/download/331/310
15. **Simulated-vs-real studies:** RflyMAD, DDCNN, Caldararu 2024, Grimaldi 2026, NASA VIPR TM-2015-218448. https://arxiv.org/abs/2311.11340 ; https://arxiv.org/abs/2403.11000 ; https://ntrs.nasa.gov/citations/20150000899

**Search accounting.** WebSearch calls used in this pass: 6 directly plus 84 by the six topic helpers, 90 in total of the 200 shared. Repository catalogue APIs (NTRS, archive.org, Wayback CDX) and direct fetches of known URLs were used heavily and are not general search engines.
