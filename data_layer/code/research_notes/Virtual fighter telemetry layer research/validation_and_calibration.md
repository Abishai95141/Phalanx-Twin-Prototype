# Validation, Calibration and Realism Testing of the Phalanx Virtual-Fighter Telemetry Layer

Scope: how to show that the Phalanx aircraft data generator ("virtual fighter") produces observations that resemble real aircraft data. Covers V&V standards, metrics beyond RMSE, discriminator (real-vs-synthetic classifier) tests, calibration and system identification, what to do without the target fighter's own data, and regression and reproducibility practice. Researched 2026-10-13.

**Evidence tags.**
- **[DIRECT]** means the claim is established in aerospace simulation or validation practice.
- **[TRANSFER: domain]** means the claim comes from another field. The reason it applies here, and its limits, are given inline.
- **[ASSUMPTION]** means it is my own engineering judgement or inference, not taken from a source.

**Process note.** Partway through, the shared WebSearch budget for this session ran out (200 calls across all agents). After that I used only two kinds of source:
- direct fetches of primary documents I could identify by URL;
- primary documents other Phalanx researchers had already saved in `/Users/abishaikc/Phalanx/research_sources/`.

Gaps caused by this are flagged. PDFs I downloaded myself are in `/Users/abishaikc/Phalanx/research_sources/validation/`.

**Cross-links to parallel researchers.** Where these notes touch another researcher's area, I state the validation consequence and point to that researcher's notes rather than covering the area myself:
- platform selection
- datasets
- sensor residual texture
- faults/degradation
- maintenance records
- modelling methodology
- data pathway/formats
- flight profiles

---

## 1. Model V&V frameworks and standards: what they require, which tolerances exist, and how flight-test data is matched

### Takeaway
No standard defines realism for a synthetic predictive-maintenance telemetry generator. Several standards still give Phalanx usable building blocks:
- **NASA-STD-7009B:** a credibility scale. Its validation scale tops out at Level 2 when only a "representative system" is available, which describes Phalanx's proxy-data situation exactly.
- **ASME V&V 20:** a way to separate model error from noise in the measurements.
- **ASME V&V 40:** effort scaled to the risk of a wrong decision.
- **MIL-STD-3022:** documentation templates.
- **FAA 14 CFR Part 60 / EASA CS-FSTD(A) / ICAO 9625:** the most concrete numeric template. These are time-history "objective tests" with per-parameter tolerances (e.g., short period ±1.5° pitch or ±2°/s pitch rate and ±0.1 g; engine spool-up ±10% of time-to-90%). They also forbid tuning the model so it is correct only at the test points.

### Cited Findings

**Definitions and credibility frameworks**
- [DIRECT] NASA-STD-7009B was approved 5 March 2024. Its definitions (§3.2):
  - *Validation:* "The process of determining the degree to which a model or a simulation is an accurate representation of the real world from the perspective of the intended uses of the M&S."
  - *Verification:* "the extent to which an M&S is compliant with its requirements and specifications."
  - *Referent:* "Data, information, knowledge, or theory against which simulation results can be compared." The referent may be the real-world system (RWS), "a similar or analogous system (whereby the closeness of the referent to the RWS becomes pertinent), or a higher-fidelity M&S."
  - Source: [NASA-STD-7009B PDF](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf), §3.2.
- [DIRECT] NASA-STD-7009B record-keeping requirements, all from the [same PDF](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf):
  - [M&S 43] acceptance criteria for verification, validation, uncertainty and sensitivity (§4.1.1.5);
  - [M&S 11] assumptions and abstractions, with their rationale;
  - [M&S 13] M&S limits;
  - [M&S 14] permissible uses;
  - [M&S 45] data sets and supporting software;
  - [M&S 46] units and coordinate frames;
  - [M&S 18] the "domain of validation" (§4.2.5);
  - [M&S 19] how uncertainty in the *referent* data was characterized (§4.2.7);
  - [M&S 47] guidance covering "parameter calibrations" and computational requirements (§4.2.1.9).
- [DIRECT] Under 7009B §4.2.5, the real data used for validation gets the same scrutiny as the model. Its sources, acquisition and processing "are to be assessed with the same level of rigor as the validation of the respective M&S." Validation may compare against "the system the M&S is representing or an acceptable alternative (e.g., a testbed, prototype, or similar representative system)." [NASA-STD-7009B](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf), §4.2.5.
- [DIRECT] NASA-STD-7009B Table 9 (Appendix E.3.4) defines validation levels:
  - **Level 4:** favorable comparison with RWS measurements "in its operating environment"; validation points "completely span the domain of operation"; all response quantities.
  - **Level 3:** RWS "in a representative environment"; points "significantly span" the domain; all *important* quantities.
  - **Level 2:** "measurements from a representative system"; points within the domain; "at least some of the important response quantities."
  - **Level 1:** conceptual validation only.
  - **Level 0:** insufficient evidence.
  - Levels are discrete with "no intentions for partial credit." No level above 1 is allowed without conceptual validation first. "Favorable comparison" requires "at a minimum, some overlap between the uncertainty intervals around the means."
  - Source: [NASA-STD-7009B](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf), App. E, Tables 6 and 9.
- [DIRECT] The M&S capability factors under [M&S 48] are Data Pedigree, Verification, Validation, Development Technical Review and Process/Product Management. Data-pedigree Level 2 needs "Uncertainties in all data are at least estimated." [NASA-STD-7009B](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf), §4.2.1.8, Table 7.
- [DIRECT] AIAA G-077-1998 sets common V&V terminology (it was written for CFD). It is "not intended for certification or accreditation." It stresses that "there is no fixed level of credibility or accuracy that is applicable to all CFD simulations as this depends upon the purpose." It recommends a building-block approach that breaks complex problems into "sub-problems of lower complexity." Source: [NAFEMS review of AIAA G-077](https://www.nafems.org/downloads/edocs/aiaa_guide_review.pdf).
- [DIRECT; originally CFD and heat transfer] ASME V&V 20 (as applied in the 2008 Lisbon workshop procedure, which is adapted from V&V 20-2008):
  - **Comparison error:** E = S − D (simulation minus data).
  - **Validation uncertainty:** U_val = √(U_num² + U_input² + U_D²).
  - **Interval for model error:** δ_model ∈ [E − U_val, E + U_val] at about 95% confidence.
  - **If |E| ≫ U_val:** then δ_model ≈ E, and that information "can possibly be used to improve the model."
  - **If |E| ≤ U_val:** the modelling error is "within the 'noise level'" and model improvements are "more problematic."
  - **Caveat:** when the same parameter uncertainty affects both simulation and experimental data reduction, the terms cannot be separated by simple root-sum-square.
  - Source: [V&V 20-based workshop validation procedure](https://maretec.tecnico.ulisboa.pt/~maretec.daemon/html_files/VV2010_files/ValidationProcedure.pdf).
- [TRANSFER: medical-device modelling] ASME V&V 40:
  - It defines model risk from "model influence" (the model's weight in the totality of evidence) and "decision consequence."
  - Credibility goals and activities should be "commensurate with model risk."
  - It transfers because the framework is generic. Its examples, however, are medical.
  - Source: secondary summary via [PMC6966181](https://pmc.ncbi.nlm.nih.gov/articles/PMC6966181).
- [DIRECT; secondary summaries] DoD VV&A:
  - DoDI 5000.61 was reissued 17 September 2024 ([DoDI 5000.61 PDF](https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/500061p.pdf); the site blocked automated retrieval, so the date comes from a search summary).
  - MIL-STD-3022 (28 Jan 2008; CHG-1 2012) gives templates for an Accreditation Plan, V&V Plan, V&V Report and Accreditation Report, with DIDs DI-MSSM-81750 to 81753.
  - The V&V Plan template centres on scoping the V&V effort and "acceptability criteria."
  - Sources: [EverySpec MIL-STD-3022](https://everyspec.com/MIL-STD/MIL-STD-3000-9999/MIL-STD-3022_4197/); [SE Goldmine summary](https://segoldmine.ppi-int.com/node/68091).
- [TRANSFER: general simulation (Winter Simulation Conference)] Sargent (2010) catalogues validation techniques, including:
  - **Turing tests:** experts "are asked if they can discriminate between system and model outputs," with statistical tests given in Schruben (1980);
  - **Face validity;**
  - **Historical data validation:** driving the model with recorded "traces";
  - **Event validity;**
  - **Extreme-condition and degenerate tests;**
  - **Internal validity:** replications to measure stochastic variability;
  - **Parameter variability-sensitivity analysis;**
  - **Predictive validation.**

  He recommends minimum steps that include specifying "the amount of accuracy required ... prior to starting the development" and a "schedule for periodic review of the model's validity." This transfers because these are model-agnostic and widely used for discrete and continuous simulators. Source: [Sargent, WSC 2010](https://www.informs-sim.org/wsc10papers/016.pdf), §4 and §8.

**Flight-simulator qualification: how objective tests and flight-test matching work**
- [DIRECT] 14 CFR Part 60, Appendix A, Attachment 2 §2.b states:
  - Tolerances exist "because mathematical modeling and acquisition and development of reference data are often inexact."
  - "When two tolerance values are given for a parameter, the less restrictive may be used."
  - A percentage-only tolerance "applies to the maximum value of that parameter within its normal operating range."
  - Source: [LII text of App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60); [eCFR](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-D/part-60/appendix-Appendix%20A%20to%20Part%2060).
- [DIRECT] Part 60 App. A Att. 2 §2.d–2.g:
  - Engineering judgement "must not be limited to a single parameter."
  - When a time history cannot be matched throughout, "differences must be justified by providing a comparison of other related variables."
  - "It is not acceptable to program the FFS so that the mathematical modeling is correct only at the validation test points."
  - Tests should be at "operating weights and centers of gravity (CG) typical of normal operation."
  - Enough data must be provided to verify the flight condition and configuration.
  - "Each simulator subsystem may be tested independently, but overall integrated testing ... must be accomplished."
  - Source: [LII App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60).
- [DIRECT] Part 60 App. A §9 sets out how flight data must be recorded and presented so it can be matched:
  - The flight-test plan must record the control inputs, atmospheric conditions, initial conditions, weight/CG and "All other information necessary to recreate the flight test conditions in the FFS" (§9.a(1)(b)).
  - Data must have "resolution sufficient to determine compliance with the tolerances" and be presented "Without alteration, adjustments, or bias." Calibration corrections are allowed if explained, and data "may be re-scaled, digitized" (§9.b).
  - A snapshot test requires steady state "from 4 seconds prior to, through 1 second following" the snapshot (§9.e).
  - Source: [eCFR App. A](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-D/part-60/appendix-Appendix%20A%20to%20Part%2060).
- [DIRECT] Part 60 Table A2A, FFS objective-test tolerances. Values are from the 2015 CFR edition; the current eCFR shows this table only as images after the December 2022 amendment, so check against the current edition.

  | Test | Tolerance |
  |---|---|
  | 1.b.1 ground acceleration time and distance | ±5% time and distance, or ±5% time and ±200 ft |
  | 1.d.1 / 1.d.2 level-flight acceleration / deceleration | ±5% time |
  | 1.d.3 cruise performance | ±0.05 EPR or ±5% N1 or ±5% torque; ±5% fuel flow |
  | 1.f.1 / 1.f.2 engine acceleration / deceleration | (±10% Tt) and (±10% Ti, or ±0.25 s). Ti = time from throttle movement to 10% response of a critical engine parameter; Tt = time to 90% of go-around power or 90% decay from max take-off power |
  | 2.c.1–2.c.4 power, flap, spoiler and gear change dynamics | ±3 kt, ±100 ft, ±20% or ±1.5° pitch |
  | 2.c.5 longitudinal trim | ±0.5° trim surface, ±1° elevator, ±1° pitch, ±5% net thrust |
  | 2.c.8 stall | ±3 kt for buffet, warning and stall speeds; ±2° bank |
  | 2.c.9 phugoid | ±10% period, ±10% time to ½ or double amplitude, or ±0.02 damping ratio |
  | 2.c.10 short period | ±1.5° pitch or ±2°/s pitch rate; ±0.10 g |
  | 2.d.4 spiral | correct trend and ±2° or ±10% bank in 20 s |
  | 2.d.6 rudder response | ±2°/s or ±10% yaw rate |
  | 2.d.7 Dutch roll | ±0.5 s or ±10% period; ±10% time to ½ or double amplitude, or ±0.02 damping; ±20% or ±1 s for the time between bank and sideslip peaks |

  Sources: [2015 CFR App. A PDF](https://www.govinfo.gov/content/pkg/CFR-2015-title14-vol2/pdf/CFR-2015-title14-vol2-part60-appA.pdf); Ti/Tt definitions from [eCFR Part 60](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-D/part-60).
- [DIRECT] Part 60 Att. 2 §4.b gives control-dynamics (transient) tolerances for underdamped free responses:
  - time to first zero crossing P0 ±10%;
  - P1 ±20%; P2 ±30%; Pn ±10(n+1)%;
  - overshoot amplitudes ±10% of A1;
  - residual band ±5% of the initial displacement;
  - only overshoots greater than 5% count, and the simulator must show "the same number of significant overshoots to within one";
  - for critically or over-damped responses, time to 90% of steady state within ±10%.
  - Source: [LII App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60).
- [DIRECT] Part 60 Att. 2 §11 covers engineering-simulator (non-flight-test) reference data:
  - The provider must enable "replication of the engineering simulation results within 40% of the corresponding flight test tolerances."
  - "A test is failed when the results clearly fall outside of the prescribed tolerance(s)."
  - Expected sources of difference: hardware, "Iteration rates," "Execution order," "Integration methods," "Processor architecture," and "Digital drift" (interpolation methods, data handling, auto-test trim tolerances).
  - Source: [LII App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60).
- [DIRECT] EASA CS-FSTD(A) Issue 2 (ED Decision 2018/006/R), Appendix 1 to AMC1 FSTD(A).300:
  - Tolerances are "a measure of quality of match using flight test data as a reference."
  - Flight test "is subject to many sources of potential error, e.g. instrumentation errors and atmospheric disturbance."
  - For engineering-simulator reference data, "20% of the corresponding 'flight test' tolerances would be appropriate." **Note the conflict:** FAA Part 60 allows 40% for the same case.
  - EASA defines "Proof-of-match (POM)" as agreement "within defined tolerances between model responses and flight test cases at identical test and atmospheric conditions."
  - Its tolerances mostly match the FAA's: short period ±1.5° or ±2°/s and ±0.1 g; phugoid ±10% period; engine acceleration ±10% Ti or ±0.25 s and ±10% Tt.
  - For ground acceleration EASA gives "±5% or ±1.5 s time" and "±5% or ±61 m (200 ft)" distance.
  - Source: [EASA CS-FSTD(A) Issue 2 page](https://www.easa.europa.eu/en/document-library/certification-specifications/cs-fstda-issue-2) ([PDF](https://www.easa.europa.eu/en/downloads/46529/en)).
- [DIRECT] Lineage of the standards, per EASA:
  - The 1992 RAeS international standards were the core document for ICAO Doc 9625 (1995).
  - A 2001 FAA/JAA international review was "the basis for a major modification of the ICAO Manual and for this CS."
  - Compliance should account for the IATA "Flight Simulation Training Device Design & Performance Data Requirements."
  - Source: [EASA CS-FSTD(A) Issue 2](https://www.easa.europa.eu/en/downloads/46529/en), AMC1 FSTD(A).300.
- [DIRECT] Part 60 Att. 2 §12–§13, validation data roadmap and alternate engines:
  - A "validation data roadmap (VDR)" must identify "in matrix format" the data source for each test, with rationale where engineering-simulation data substitute for flight test.
  - Tests are split into those "dependent on engine type or thrust rating and those that are not."
  - Engine-specific flight data are needed when thrust rating exceeds the validated rating by ≥5% or is ≥15% below it.
  - Throttle-calibration data must come from a test airplane or bench "with the correct engine controller (both hardware and software)."
  - Source: [LII App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60).
- [DIRECT] Part 60 Att. 2 §16, continuing qualification:
  - Results are over-plotted against the Master QTG (MQTG), i.e., the simulator's own initial-qualification results.
  - "There are no suggested tolerances between flight simulator continuing qualification and MQTG validation test results."
  - Differences "other than variations attributable to repeatability issues" should be investigated.
  - Source: [LII App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60).
- [DIRECT] Part 60, high angle of attack and subjective evaluation:
  - Strict time-history evaluation "may not adequately validate the aerodynamic model in an unsteady and potentially unstable flight regime, such as stalled flight." So there are no strict tolerances beyond the stall-identification AoA; a Statement of Compliance on data sources and methods is required instead.
  - Some stall cases "may be subjectively evaluated by a qualified subject matter expert (SME) pilot."
  - Source: [LII App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60), Attachment 7.

**Engine-model acceptance in practice**
- [DIRECT] F404 engine test cell (US Navy/USAF test-cell upgrade, Roemer et al.):
  - A generic thermodynamic engine model, tuned from test-cell data, was compared against 21 engines from several test cells. For T45 the model "appeared to be generally within 1% error, good enough to use for diagnostic purposes." This was before bleeds and variable geometry were fully modelled.
  - Performance assessment uses standard-day-corrected data and "gold" or "correlator" engine signature curves.
  - Shifts are tested with a two-sample t-test.
  - Source: [DTIC ADA408947](https://apps.dtic.mil/sti/citations/ADA408947) (local copy: `research_sources/engine_data/f404_monitoring/DTIC_ADA408947.pdf`).
- [DIRECT; noisy OCR] Australian ARL review of F404 in-flight engine monitoring data (rapid accelerations, 5–30 °C inlet temperature):
  - For the same engine, fuel flow was consistent "to within ±2%" and N1/N2 "to within ±0.5%."
  - A bias between test-cell and airborne-system data had to be removed by a bias-correction technique.
  - This gives a natural-variability floor for engine-parameter matching.
  - Source: [DTIC ADA219105, ARL-PROP-TM-450](https://apps.dtic.mil/sti/citations/ADA219105) (local: `research_sources/engine_data/f404_monitoring/DTIC_ADA219105.txt`).
- [DIRECT] NASA's C-MAPSS40k engine model was built "to match the characteristics of data provided by a flight test of a highly instrumented engine during steady-state and transient maneuvers," with those data "serving as validation." [NTRS 20100037767](https://ntrs.nasa.gov/citations/20100037767).

**NATO**
- [DIRECT] NATO RTO-TR-028 (2000), Ch. 7 on engine life-monitoring algorithms:
  - Reduced-order models are validated by running "a standard sortie that covers all of the expected flight conditions and exercises all of the logic" through both the full and reduced models.
  - The reduced model is "declared equivalent" when mean computed damage matches and "the maximum difference is below a defined limit."
  - "the reduced modelling approximation is only valid for the situations where it has been calibrated." Accuracy should be re-checked "for each new flight profile."
  - Changes must go back through V&V under configuration control.
  - Source: NATO RTO-TR-028 / AC/323(AVT)TP/22 (public release; local copy `research_sources/flight_profiles/RTO-TR-028.pdf`; online URL not recorded).

### Inferences
- [ASSUMPTION] **Phalanx should state its 7009B credibility level honestly.** Without data from the target fighter, the "Validation" factor caps at Level 2 (a representative system). Levels 3–4 need RWS measurements. The [M&S 18] domain-of-validation record should list which regimes (ground run, take-off, cruise, high-g manoeuvre) and which channels each proxy actually covers.
- [ASSUMPTION] **Part 60 / CS-FSTD is the best available template for an "objective test guide" (QTG) for Phalanx.** Each test would record:
  - flight condition and configuration;
  - input (replayed from the real record);
  - compared parameters;
  - tolerance;
  - data source, via a VDR-style matrix;
  - pass/fail with engineering judgement.

  The fighter-relevant subset is: engine Ti/Tt transients, short-period and Dutch-roll modal tests, trims, and level-acceleration times.
- [ASSUMPTION] **Reuse the two-tier tolerance idea.** Tier 1 tolerances apply against real (proxy) data. Tier 2 applies against Phalanx's own golden reference ("MQTG"), set at about 20–40% of Tier 1, following EASA and FAA. The list of benign differences in Part 60 §11 (integration method, iteration rate, interpolation) is effectively a list of what Phalanx's regression tests must control.
- [ASSUMPTION] **The civil tolerances are not the right absolute numbers for a fighter predictive-maintenance data generator.** Their intended use is pilot training. What transfers is the *structure*:
  - percentage-or-absolute "less restrictive" tolerances;
  - modal-parameter tolerances (period, time to half amplitude, damping);
  - transient-timing tolerances (Ti/Tt);
  - multi-parameter judgement.

  Phalanx's own tolerances should be set risk-informed (V&V 40) from the intended use: training and testing PdM and fleet-availability models.

### Gaps
- I could not read the full text of ICAO Doc 9625, ASME V&V 10-2019, V&V 20-2009 or V&V 40-2018 (paywalled). Their content here comes from derived documents (EASA, the workshop procedure, PMC summary). A search summary mentioned ASME VVUQ 20.1 (multivariate validation metric, 2025); I could not verify it.
- I found no military-specific simulator-qualification tolerance standard (fighter flight simulators or engine models). Search was exhausted before I could look for one.
- Industry engine-model acceptance tolerances against test-cell data (OEM practice, SAE ARP test-cell correlation documents) were not found. Only the F404 test-cell example (about 1% on T45) and in-flight repeatability (±2% Wf, ±0.5% N1/N2) are cited.
- NATO MSG/SISO GM-VV (Generic Methodology for VV&A) was not retrieved.
- I did not find an online URL for RTO-TR-028.

---

## 2. Metric families beyond RMSE, and the strengths and failure modes of synthetic time-series evaluation suites

### Takeaway
RMSE on aligned time histories is only one of several metric families, and it requires input-matched replay. Each family catches a different kind of unrealism:
- distributional distances and tests: marginals and tails;
- spectral and autocorrelation measures: noise "texture" and dynamics;
- transient and modal metrics: Part 60-style period, damping and Ti/Tt;
- dependence measures: cross-channel physics;
- event-rate and missingness statistics: operational artefacts;
- physical-invariant checks: kinematic and thermodynamic consistency;
- downstream-utility tests: TSTR, and how well results on sim data predict results on real data.

ML synthetic-time-series suites (TimeGAN scores, Context-FID, TSGBench, SDMetrics, Synthcity, α-precision/β-recall) are useful. Benchmark studies show they are unstable, depend on the architecture and embedding used, and disagree with one another, so none can act as a sole acceptance criterion.

### Cited Findings

**Transient, modal and point-comparison metrics (aerospace)**
- [DIRECT] Part 60 transient metrics give a ready template for step, doublet and free-response comparisons:
  - period-by-period tolerances (P0 ±10%, P1 ±20%, …);
  - overshoot amplitude ±10% of A1;
  - residual band ±5%;
  - significant-overshoot count within one;
  - time to 90% ±10%;
  - engine Ti (10% response) and Tt (90% response) timing tolerances.

  Source: [LII App. A, Att. 2 §4](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60); [2015 CFR Table A2A](https://www.govinfo.gov/content/pkg/CFR-2015-title14-vol2/pdf/CFR-2015-title14-vol2-part60-appA.pdf).
- [DIRECT] NASA aircraft system identification evaluates models using:
  - parameter uncertainties, signal-to-noise ratio, F ratios, R², predicted squared error (PSE), and correlations among model terms.

  It states: "the most important evaluation ... is made by examining the predictive capability of the model using data that were not used to identify the model." Source: [Morelli & Grauer 2023, J. Aircraft, doi:10.2514/1.C037274](https://doi.org/10.2514/1.C037274), Fig. 2 and text (local: `research_sources/sensor_texture/morelli_grauer_2023_advances_sid.pdf`).
- [DIRECT] **Residual colour matters.** In output-error analysis of flight-test data the "measurement noise is model-dependent and colored, because the modeling error usually lies in the same frequency band as the aircraft rigid body dynamics." Consequences:
  - Conventional Cramér–Rao bounds were "optimistic (i.e., too small)," with error-to-bound ratios exceeding 3 for almost every parameter.
  - Bounds corrected for coloured residuals matched the scatter seen across repeated manoeuvres.
  - For Phalanx, the spectrum of residuals between real and simulated signals is itself a validation target, not just their variance.
  - Source: [Morelli & Klein 1995, AIAA 95-3499](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf).

**Uncertainty-aware comparison metrics**
- [DIRECT / TRANSFER: computational-mechanics UQ] The V&V 20 comparison error E with U_val (see Q1) gives a "model error versus noise" decision rule. [V&V 20 procedure](https://maretec.tecnico.ulisboa.pt/~maretec.daemon/html_files/VV2010_files/ValidationProcedure.pdf).
- [TRANSFER: reliability / UQ] The area validation metric with u-pooling (Ferson et al. 2008):
  - It compares the model's predictive CDF with observations and pools across conditions via the probability integral transform.
  - Ling & Mahadevan show that Bayesian interval hypothesis testing, the reliability-based metric and the area metric "can all account for directional bias." They also show the Bayes factor and the reliability metric relate to classical p-values.
  - It requires a probabilistic (stochastic) model output. Phalanx's seeded ensembles provide one.
  - Source: [Ling & Mahadevan, arXiv:1206.5014](https://arxiv.org/abs/1206.5014).

**Distributional tests and distances**
- [TRANSFER: statistics] Tools for marginal and multivariate distribution comparison:
  - two-sample KS ([scipy ks_2samp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html));
  - k-sample Anderson–Darling. Its p-values are floored at 0.1% and capped at 25% unless a permutation method is used; the docs show a capped 0.25 becoming 0.699 under permutation ([scipy anderson_ksamp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.anderson_ksamp.html));
  - 1-D Wasserstein ([scipy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wasserstein_distance.html));
  - energy distance ([scipy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.energy_distance.html));
  - kernel MMD. This is an integral probability metric over the unit ball of an RKHS, with quadratic-time and linear-time estimators and distribution-free or asymptotic nulls ([Gretton et al., JMLR 2012](https://jmlr.org/papers/v13/gretton12a.html));
  - deep-kernel MMD, which "includes classifier-based two-sample tests as a special case" and reportedly improves on them ([Liu et al., ICML 2020](https://arxiv.org/abs/2002.09116)).
- [TRANSFER: econometrics] **Dependence breaks i.i.d. tests.** Time-series data "is characterized by the correlation between observations that are near in time," and the i.i.d. assumption "rarely holds" ([scikit-learn CV guide](https://scikit-learn.org/stable/modules/cross_validation.html)). Block bootstraps (stationary, circular; the moving-block variant is not recommended) with `optimal_block_length` give confidence intervals that account for dependence ([arch bootstrap docs](https://arch.readthedocs.io/en/latest/bootstrap/timeseries-bootstraps.html)). The limit: block length must be chosen per channel and regime.

**Temporal, spectral and dependence structure**
- [TRANSFER: signal processing / econometrics] Standard tools for temporal structure:
  - ACF/PACF ([statsmodels acf](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.acf.html), [pacf](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.pacf.html));
  - Welch PSD ([scipy welch](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html));
  - magnitude-squared coherence Cxy = |Pxy|²/(Pxx·Pyy) via Welch ([scipy coherence](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.coherence.html));
  - cross-correlation lags ([scipy correlation_lags](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlation_lags.html));
  - DTW ([tslearn DTW guide](https://tslearn.readthedocs.io/en/stable/user_guide/dtw.html));
  - Granger tests. The null is that x2 does not Granger-cause x1; ssr-F, χ², likelihood-ratio and parameter-F tests are returned ([statsmodels grangercausalitytests](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.grangercausalitytests.html));
  - mutual information ([scikit-learn mutual_info_regression](https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.mutual_info_regression.html)).

  These transfer because aircraft channels are coupled dynamical signals. Limits: coherence and Granger tests assume stationarity within the window, so compute them per regime.

**Event rates, missingness, envelopes**
- [TRANSFER: discrete-event simulation] Sargent's "event validity" compares occurrence counts between model and system (e.g., number of fires) ([Sargent 2010](https://www.informs-sim.org/wsc10papers/016.pdf)). For Phalanx the events would be exceedances, fault codes and BIT events. Two Poisson rates with different exposures can be compared with the E-test ([scipy poisson_means_test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.poisson_means_test.html)).
- [TRANSFER: tabular synthetic data] SDMetrics provides `MissingValueSimilarity`, `BoundaryAdherence`, `RangeCoverage`, `KSComplement`, `TVComplement`, `CorrelationSimilarity` and `ContingencySimilarity` ([SDMetrics index](https://docs.sdv.dev/sdmetrics/llms.txt)). These are simple checks for missingness patterns and envelopes. Limit: they are tabular, not temporal.
- [TRANSFER: statistics] For tails, a peaks-over-threshold generalized Pareto fit ([scipy genpareto](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.genpareto.html)) is one route to comparing extreme-value behaviour. No aerospace-specific tail-validation standard was found (see Gaps).

**Physical-invariant checks**
- [DIRECT] Data compatibility analysis checks measured flight data "for kinematic consistency" by identifying "systematic instrumentation errors ... typically biases, scale factor errors, and relative time skews." [Morelli & Grauer 2023](https://doi.org/10.2514/1.C037274). The same reconstruction (integrating rates against measured attitudes and velocities) can be run on Phalanx output as an invariant test.
- [DIRECT] Engine models are closed with energy balance between spools ("used to match the two machines on the basis of energy conservation") and with choked-flow limits. [DTIC ADA408947](https://apps.dtic.mil/sti/citations/ADA408947). In Phalanx, spool power balance and mass-flow continuity can be asserted as invariants.
- [TRANSFER: general simulation] Extreme-condition and degenerate tests check that model structure and outputs are plausible for "any extreme and unlikely combination of levels of factors" ([Sargent 2010](https://www.informs-sim.org/wsc10papers/016.pdf)).

**Synthetic time-series evaluation suites: what they compute and how they fail** (all [TRANSFER: ML generative modelling]; they transfer because Phalanx output is synthetic multivariate time series; limits noted per item)
- **TimeGAN** ([Yoon et al., NeurIPS 2019](https://proceedings.neurips.cc/paper/2019/file/c9efe5f26cd17ba6216bbe2a7d26d490-Paper.pdf)):
  - Three desiderata: diversity, fidelity and usefulness ("train-on-synthetic, test-on-real").
  - Discriminative score: the paper describes a "2-layer LSTM" post-hoc classifier.
  - The official code differs from the paper:
    - a single `GRUCell` with hidden size dim/2;
    - 2000 iterations, batch size 128;
    - 80/20 train/test split;
    - `discriminative_score = np.abs(0.5-acc)`;
    - an apparent bug: `generated_time` is computed from `ori_data`.
  - Source: verified in [discriminative_metrics.py](https://github.com/jsyoon0823/TimeGAN/blob/master/metrics/discriminative_metrics.py) and `utils.py`.
  - Predictive score: a post-hoc next-step predictor trained on synthetic data, tested on real data, scored by MAE.
- **TSGBench** ([Ang et al., VLDB 2024](https://arxiv.org/abs/2309.03755)):
  - Twelve measures:
    - model-based: DS, PS, Context-FID on TS2Vec embeddings;
    - feature-based: marginal distribution difference, autocorrelation difference, skewness difference, kurtosis difference;
    - distance-based: Euclidean distance, DTW;
    - training time;
    - t-SNE and distribution plots.
  - Documented failure modes:
    - DS and PS depend on post-hoc training, so "random initialization causes inconsistent results";
    - they depend on the architecture, are "sensitive to dataset size," and short sequences (e.g., 24 points) may lack periodic information;
    - DS had high standard deviation relative to its mean and was insensitive to sequence length;
    - at one length, random samples scored *better* DS than identical inputs;
    - on one Energy dataset almost all methods scored about 0.5 DS (saturation);
    - measures disagree: LS4 scores high on DS/PS but low on C-FID.
  - TSGBench also adds a domain-adaptation generalization test.
- **Survey and benchmark of measures:**
  - The survey "Evaluation is key" finds no universally accepted evaluation procedure and warns of a "do as you like" practice ([Stenger et al., J. Big Data 2024](https://doaj.org/article/de615751470e4fbb886d39f9359045a0)).
  - STEB benchmarks 41 measures and finds "the choice of upstream time series embedding heavily impacts the final score" ([STEB, arXiv:2505.21160](https://arxiv.org/abs/2505.21160)).
- **Context-FID:** a "Frechet-Inception Distance-like score." In two forecasting tasks, the lowest-scoring models were the best-performing ones; this is an observed pattern, not a guarantee. [Jeha et al., PSA-GAN](https://arxiv.org/abs/2108.00981).
- **TSTR/TRTS:** Esteban et al. train on synthetic and test on real, "and vice-versa," and use MMD on toy data. [arXiv:1706.02633](https://arxiv.org/abs/1706.02633).
- **α-Precision / β-Recall / Authenticity** ([Alaa et al., ICML 2022](https://arxiv.org/abs/2102.08921)):
  - Sample-level metrics for fidelity, diversity and generalization.
  - Authenticity flags "unauthentic" samples copied from training data.
  - Computed via minimum-volume sets in an embedding.
  - Limit: they depend on the embedding.
- **Library conventions conflict:**
  - SDMetrics `LSTMDetection` (beta): score = 1 − accuracy, so 1.0 means indistinguishable. It is designed for "multiple sequences" without one-to-one mapping ([SDMetrics docs](https://docs.sdv.dev/sdmetrics/data-metrics/metrics-in-beta/detection-sequential)).
  - Synthcity `detection_xgb/mlp/linear/gmm`: 0 means indistinguishable. Synthcity also provides `prdc`, `alpha_precision`, `wasserstein_dist` and `jensenshannon_dist` ([Synthcity README](https://github.com/vanderschaarlab/synthcity)).
  - TimeGAN DS: 0 means indistinguishable.
- **A discriminator can be fooled:** GAN training "may appear successful but the trained distribution may be far from target distribution in standard metrics"; generalization holds only for a weaker "neural net distance." So a limited-capacity discriminator failing cannot certify closeness. [Arora et al., arXiv:1703.00573](https://arxiv.org/abs/1703.00573).

**Layered and downstream sim-to-real metrics**
- [TRANSFER: automotive radar] Ngo et al. measure the radar simulation-to-reality gap in layers:
  - explicit: point-cloud distance Dpp, Gaussian Wasserstein, and low-level properties such as detection count;
  - implicit (downstream): multi-object tracking scored by OSPA and IoU;
  - each metric is normalized to [0,1] and averaged into a gap score G.

  This transfers as a structure for combining metric families; the specific metrics are radar-specific. Source: [ITSC 2021, arXiv:2106.08372](https://arxiv.org/abs/2106.08372).
- [TRANSFER: robotics] The Sim-vs-Real Correlation Coefficient (SRCC) asks whether ranking methods in simulation predicts their ranking in reality. In Habitat, success-metric SRCC was 0.18. The gap came from agents exploiting simulator imperfections ("sliding" along walls). Tuning simulator parameters raised SRCC to 0.844. Source: [Kadian et al., RA-L 2020](https://arxiv.org/abs/1912.06321). The Phalanx analogue: does ranking PdM models on Phalanx data predict their ranking on real proxy data?

### Inferences
- [ASSUMPTION] **Metric families map to Phalanx failure modes:**

  | Failure mode | Metrics that catch it |
  |---|---|
  | Wrong noise texture | PSD and ACF of residuals and of the raw signal; residual whiteness and colour compared with the real residual spectrum (cross-link: sensor residual texture researcher) |
  | Wrong dynamics | Part 60-style modal and transient metrics on replayed manoeuvres; Ti/Tt for spool-up |
  | Wrong coupling | coherence, lagged cross-correlation, partial correlation, MI, Granger on regime-segmented windows; physical invariants |
  | Wrong operations | event rates (Poisson E-test), regime-dwell distributions, missingness and dropout patterns (cross-links: flight-profiles and data-pathway researchers) |
  | Wrong degradation | trend-slope and rate distributions vs fleet data (cross-links: faults/degradation and maintenance-records researchers) |
  | Wrong tails | POT/GPD exceedance comparison; AD test with permutation p-values |

- [ASSUMPTION] **Always compute metrics by regime.** Following Part 60 flight-condition columns and the 7009B domain of validation, use regimes such as ground idle, take-off, climb, cruise, combat manoeuvre, approach and engine transient. A global KS over a whole sortie mostly measures differences in regime mix. That is a flight-profile issue, not a sensor-model issue.
- [ASSUMPTION] **Report every metric against a real-vs-real reference distance.** Examples are two disjoint real fleets, two tail numbers, or two seasons. Without that floor, numbers such as Wasserstein = 0.3 cannot be interpreted. The same applies to tolerances: no acceptance tolerance should be tighter than the real system's own repeatability (e.g., F404 in-flight Wf ±2%, N1/N2 ±0.5%; [DTIC ADA219105](https://apps.dtic.mil/sti/citations/ADA219105)).
- [ASSUMPTION] **Fix ML-suite parameters before use.** Pin and record the classifier, embedding, seed and number of repeats. Report mean ± SD over at least 5–10 repeats, given TSGBench's documented DS variance. Normalize score conventions (0 vs 1 as "indistinguishable") in the Phalanx report.

### Gaps
- I did not retrieve or verify aerospace-specific guidance on tail and extreme-value validation of sensor data, on copula-based dependence comparisons, or Theil's inequality coefficient (TIC) thresholds used in flight-simulation model validation.
- I did not confirm from a primary source the claim that AD is more tail-sensitive than KS (the scipy page does not say).
- The full STEB ranking of which of the 41 measures are most reliable was not read (abstract only).

---

## 3. Discriminator-based validation (classifier two-sample tests): design, interpretation, turning results into simulator fixes, pitfalls and significance

### Takeaway
A real-vs-synthetic classifier is a valid two-sample test with a simple null distribution (accuracy ~ N(½, 1/(4·n_te))) and interpretable outputs. Its result depends on the classifier, the sample size and the data's dependence structure, and it can be fooled in both directions:
- **Wrongly passed:** a too-weak or poorly trained classifier, or a narrow feature view, lets an unrealistic simulator pass.
- **Wrongly failed:** a trivial cue (sample rate, rounding, file artefacts, record length), domain shift between different aircraft, or leakage between related windows (overlapping windows or windows from the same flight split across train and test) makes it fail.

To use it well:
1. Canonicalize the data pathway first.
2. Compare like with like.
3. Split train and test by flight or aircraft.
4. Test significance with group-level permutation.
5. Use a ladder of classifiers, from simple features to raw sequences.
6. Interpret results through feature-family ablation, not saliency maps alone.

Passing is necessary but never sufficient.

### Cited Findings
- [TRANSFER: ML statistics] **C2ST procedure** (Lopez-Paz & Oquab):
  - Label real 0 and synthetic 1, shuffle, split, train a classifier, and use held-out accuracy as the statistic.
  - Under H0, n_te·t̂ ~ Binomial(n_te, ½), so t̂ ≈ N(½, 1/(4n_te)).
  - Approximate power is Φ((ε√n_te − Φ⁻¹(1−α)/2)/√(¼ − ε²)), where ε is the true excess accuracy.
  - There is a trade-off: flexible classifiers find more structure but need more training data, leaving a smaller test set.
  - Interpretability: per-sample probabilities "explain where the two distributions differ"; classifier feature importances show which features matter; accuracy is in interpretable units.
  - The paper assumes equal sample sizes (m = n).
  - Source: [ICLR 2017, arXiv:1610.06545](https://arxiv.org/abs/1610.06545).
- [TRANSFER: mathematical statistics] **Theory** (Kim, Ramdas, Singh & Wasserman, Annals of Statistics):
  - If a classifier's true error stays ε-better than chance, the permutation-based accuracy test is consistent in any dimension. Its type-I error "can always be controlled non-asymptotically ... using permutations."
  - For Gaussian mean shifts, accuracy-based LDA tests lose only a constant factor in power versus Hotelling (asymptotic relative efficiency 1/√π).
  - Their advice: if the alternative can be specified, use a well-tailored statistic. If the data are "highly structured or abundant" and differences cannot be specified, use flexible classifier accuracy.
  - Source: [arXiv:1602.02210](https://arxiv.org/abs/1602.02210).
- [TRANSFER: ML statistics] Deep-kernel MMD "includes classifier-based two-sample tests as a special case" and "improves on them in general" ([Liu et al., ICML 2020](https://arxiv.org/abs/2002.09116)). Friedman's earlier variant applies a univariate test (e.g., Mann–Whitney/KS) to classifier *scores* rather than thresholded accuracy (described in [Kim et al.](https://arxiv.org/abs/1602.02210) §1.4). Scores carry more information than 0/1 accuracy, and Lopez-Paz notes zero-one statistics "can exhibit high variance."
- [TRANSFER: time-series ML] **Classifier design options:**
  - **catch22:** 22 interpretable features selected from 4,791 filtered hctsa features across 93 classification datasets. They are about 1000× faster to compute, with about 7% average accuracy loss. Categories: linear and nonlinear autocorrelation, successive differences, value distributions and outliers, and fluctuation scaling ([Lubba et al., arXiv:1901.10200](https://arxiv.org/abs/1901.10200); [pycatch22](https://github.com/DynamicsAndNeuralSystems/pycatch22)).
  - **tsfresh FRESH:** each feature is tested "individually and independently" against the label, with Benjamini–Yekutieli multiple-testing control ([tsfresh docs](https://tsfresh.readthedocs.io/en/latest/text/feature_filtering.html)).
  - **ROCKET:** random convolutional kernels plus a linear classifier, giving "state-of-the-art accuracy" at "a fraction of the computational expense" ([Dempster et al., arXiv:1910.13051](https://arxiv.org/abs/1910.13051)).
  - **Recurrent detectors:** the TimeGAN (GRU) and SDMetrics `LSTMDetection` classifiers ([TimeGAN code](https://github.com/jsyoon0823/TimeGAN/blob/master/metrics/discriminative_metrics.py); [SDMetrics](https://docs.sdv.dev/sdmetrics/data-metrics/metrics-in-beta/detection-sequential)).
- [TRANSFER: explainable ML] **Interpretation tools and their limits:**
  - **SHAP** gives additive Shapley-value attributions per prediction ([Lundberg & Lee, NIPS 2017](https://arxiv.org/abs/1705.07874); [shap](https://github.com/shap/shap)).
  - **Permutation importance** must be computed on held-out data and is only meaningful for a good model. With correlated features, "both show lower importance even if both are actually important"; the remedy is to cluster correlated features and keep one per cluster ([scikit-learn](https://scikit-learn.org/stable/modules/permutation_importance.html)).
  - **Saliency for time series:** saliency methods "fail to reliably and accurately identify feature importance over time" because they conflate the time and feature dimensions; temporal saliency rescaling helps ([Ismail et al., NeurIPS 2020](https://arxiv.org/abs/2010.13924)).
  - **Saliency sanity checks:** "some existing saliency methods are independent both of the model and of the data generating process" ([Adebayo et al.](https://arxiv.org/abs/1810.03292)).
- [TRANSFER: shortcut learning] Shortcut learning means "decision rules that perform well on standard benchmarks but fail to transfer" ([Geirhos et al., Nature Machine Intelligence 2020](https://arxiv.org/abs/2004.07780)).
- [TRANSFER: audio deepfake detection] **A concrete trivial cue.** In ASVspoof, genuine audio has longer leading and trailing silence:
  - A model using only leading-silence duration reached about 85% accuracy (EER 15.1%).
  - Trimming silence raised a full model's EER from 3.6% to 15.5%.

  This shows how a "realism" discriminator can score highly on an artefact of the collection pipeline. Phalanx analogues include record padding, start-up and shut-down segments, timestamp regularity, quantization steps and sample rate. Source: [Müller et al., ASVspoof 2021 workshop, arXiv:2106.12914](https://arxiv.org/abs/2106.12914).
- [TRANSFER: ML methodology] **Leakage and dependence:**
  - Leakage appears in 8 types across 329 papers in 17 fields; "model info sheets" are proposed to catch it ([Kapoor & Narayanan](https://arxiv.org/abs/2207.07048)).
  - When samples come from groups (subjects, experiments, devices), use group-wise CV so that "all the samples in the validation fold come from groups that are not represented at all in the paired training fold."
  - Shuffling time-ordered data gives "an inflated validation score."
  - Source: [scikit-learn CV guide](https://scikit-learn.org/stable/modules/cross_validation.html).
- [TRANSFER: computer vision] **SimGAN:** a discriminator was used to *refine* simulator output, and realism was then checked with a human "Visual Turing test."
  - 10 subjects identified real vs refined images correctly 517/1000 times (51.7%, p = 0.148), which is chance level.
  - On unrefined synthetic images they scored 162/200 (p ≤ 10⁻⁸).
  - Downstream gaze-estimation error fell from 11.2 (synthetic) to 7.8 (refined).
  - Source: [Shrivastava et al., CVPR 2017, arXiv:1612.07828](https://arxiv.org/abs/1612.07828).
- [TRANSFER: robotics] **A classifier used as a calibrator.** The "Search Param Model" predicts from real observations whether each simulator parameter is "higher or lower than the true real-world values" and shifts parameters iteratively ([Du et al., ICRA 2021](https://arxiv.org/abs/2104.07662)).
- [TRANSFER: ML operations] **Adversarial validation** (a classifier separating training data from new data) is used at Uber to detect concept drift before inference. I saw only the abstract; mechanics are not verified. [Pan et al., arXiv:2004.03045](https://arxiv.org/abs/2004.03045).
- [TRANSFER: simulation-based inference] Classifier diagnostics between surrogate and simulator: "Passing these sanity checks does not guarantee that an estimator is correct, but failing them is an indication of problems." "None of these diagnostics address the issues encountered if the model is misspecified." [Cranmer, Brehmer & Louppe, PNAS 2020](https://arxiv.org/abs/1911.01429).
- [DIRECT] The human Turing test is an established simulation-validation technique, with statistical tests in Schruben (1980) ([Sargent 2010](https://www.informs-sim.org/wsc10papers/016.pdf)). Part 60 relies on SME pilot subjective evaluation where objective tolerances fail, e.g., post-stall ([LII App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60)).
- [GAP] I found **no aerospace-telemetry example** of a real-vs-synthetic classifier used to validate a simulator in the time available; search was exhausted. The closest documented examples are the radar layered-gap work ([Ngo et al.](https://arxiv.org/abs/2106.08372)), which uses no classifier, and the robotics and vision cases above.

### Inferences
- [ASSUMPTION, computed from Lopez-Paz's null] **Critical accuracy and power.**
  - One-sided α = 0.05 critical accuracies by number of *independent* test units:

    | n_te | Critical accuracy |
    |---|---|
    | 100 | 0.582 |
    | 200 | 0.558 |
    | 500 | 0.537 |
    | 1000 | 0.526 |
    | 5000 | 0.512 |

  - Power to detect a true accuracy of 0.55: about 0.41 at n_te = 200 and about 0.94 at n_te = 1000.
  - Power to detect 0.52: about 0.35 at n_te = 1000 and about 0.88 at n_te = 5000.
  - **Important:** overlapping windows from one sortie are not independent. Count independent units as flights or sorties, or use a group-level permutation test that keeps all windows of a flight in one fold and permutes labels at flight level.
- [ASSUMPTION] **A Phalanx discriminator protocol.**
  1. **Trivial-cue audit first.** Train a classifier on metadata-only features: record length, sample-interval jitter, LSB/rounding histogram, NaN and dropout runs, start and end segments, header fields. If it beats chance, fix the pipeline (cross-link: data-pathway researcher) before any realism claim.
  2. **Canonicalize both classes** through the identical ingest path: same resampling, the same ARINC-429/1553-style word quantization, same units and same file container.
  3. **Match conditions.** Compare Phalanx-simulating-proxy-X against real-proxy-X in the same regimes and ambient bins. Never compare simulated-Tejas against real-airliner data: the classifier would detect the platform, not the simulator.
  4. **Use a classifier ladder:**
     - per-channel marginal tests;
     - catch22/tsfresh plus regularized logistic regression or gradient boosting, per channel and cross-channel;
     - ROCKET or a small CNN/GRU on raw multichannel windows;
     - each at two or three window lengths, e.g., 2 s, 30 s and a whole regime segment, since TSGBench warns short windows miss periodic structure.
  5. **Ablate by feature family** and record the accuracy drop for each: spectral, noise statistics (variance, kurtosis, Allan-type), quantization and LSB, timing and jitter, cross-channel lag and coherence, transient shape, regime transitions.
  6. **Map each family to a simulator module and fix it:**
     - noise and texture model (sensor-texture researcher);
     - ADC and bus encoding (data pathway);
     - actuator, engine and controller dynamics (modelling methodology);
     - schedules (flight profiles).
  7. **Re-test** with fresh seeds *and* a re-trained classifier, plus one classifier family held out from development. This avoids overfitting the simulator to a fixed discriminator.
  8. **Report accuracy against a real-vs-real baseline.** Example: real tail A vs real tail B, or two seasons. For proxy validation the acceptance goal is "sim-vs-real distinguishability ≤ real-vs-real (different-airframe) distinguishability," not "accuracy = 0.5."
- [ASSUMPTION] Use balanced accuracy or AUC if class sizes differ, and down-sample to m = n for the binomial null.
- [ASSUMPTION] **Never use the discriminator as the definition of realism,** because:
  - (i) failing to detect a difference is weak evidence ([Arora](https://arxiv.org/abs/1703.00573), [Cranmer](https://arxiv.org/abs/1911.01429));
  - (ii) detection is dominated by whatever cue is easiest, which may be irrelevant to PdM;
  - (iii) it gives no information about physically important but rarely seen regimes (faults, extremes).

  It should sit in the protocol beside physics checks, objective tests and SME review (see §7).

### Gaps
- I found no published guidance on discriminator window length for flight or engine telemetry. The window-length recommendation above is an assumption.
- Calibrated "realism thresholds" for discriminator accuracy in any aerospace qualification context: none found.
- The internals of Uber's adversarial validation were not read (abstract only).

---

## 4. Calibration and system identification: the real data → model → residual → correction → validation loop

### Takeaway
Calibration has to be separated from validation, and the model's discrepancy from reality has to be modelled explicitly. Otherwise parameters absorb structural error and become biased and overconfident (Kennedy & O'Hagan; Brynjarsdóttir & O'Hagan; Tuo & Wu).

The aircraft community's proven loop is:
1. data compatibility analysis;
2. model structure determination;
3. parameter estimation (equation-error, output-error, filter-error, time or frequency domain);
4. diagnostics;
5. validation on data not used for identification (NASA LaRC).

Engine models are matched by tuning component-map scalars or health parameters with Kalman-type trackers. These problems are often underdetermined: there are more health parameters than sensors, and measurement bias is indistinguishable from deterioration.

History matching, simulation-based inference (SBI) and hybrid residual learning are powerful additions. Each has documented failure modes: overconfident posteriors, non-identifiability, and extrapolation outside the training regime.

### Cited Findings

**Statistical calibration with discrepancy**
- [TRANSFER: computer-experiment statistics] **Kennedy & O'Hagan (2001)** Bayesian calibration:
  - Predictions account for "all sources of uncertainty, including the remaining uncertainty in the fitted parameters."
  - It corrects for "model inadequacy revealed when observations differ from predictions even at the best-fitting parameter values."
  - Model discrepancy is a Gaussian process.
  - Sources: [JRSS-B 63(3):425–464](https://academic.oup.com/jrsssb/article/63/3/425/7083367); GP-discrepancy description in [Tuo & Wu](https://arxiv.org/abs/1507.07280).
- [TRANSFER: inverse problems] **Brynjarsdóttir & O'Hagan (2014):**
  - Calibrating without discrepancy "can yield biased parameter estimates and overconfident predictions."
  - Discrepancy "can be confounded with the parameters being learned."
  - A GP discrepancy gives correct predictions "within the range of the data," but true parameters are recovered only with "realistic priors on the model discrepancy."
  - Source: [Inverse Problems 30:114007](https://iopscience.iop.org/article/10.1088/0266-5611/30/11/114007).
- [TRANSFER: statistics] **Tuo & Wu:**
  - The KOH method "may lead to unreasonable estimate for imperfect computer models," because the calibration parameter is unidentifiable.
  - They propose "L2 calibration," defined as the L2 projection, which is semiparametrically efficient; ordinary least squares is consistent but not efficient.
  - Source: [arXiv:1507.07280](https://arxiv.org/abs/1507.07280).
- [TRANSFER: complex-simulator UQ] **History matching** (Andrianakis et al., PLoS Comput Biol 2015):
  - Implausibility measures how far the emulator mean lies from data, scaled by observation, emulator, ensemble and discrepancy variances.
  - Cutoff of 3 by Pukelsheim's 3-sigma rule; a χ² cutoff for multivariate versions.
  - Iterative "waves" (9 waves in the case study).
  - Discrepancy variance set at 10% of simulator output variance, as an illustration.
  - It needs only means and variances.
  - "It can reveal when a simulator cannot match the data at all," whereas fully probabilistic methods "would still return a posterior."
  - Source: [PLoS Comput Biol 10.1371/journal.pcbi.1003968](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003968).

**Simulation-based inference**
- [TRANSFER: physics / ML] **Cranmer, Brehmer & Louppe:** ABC and classical density estimation suffer from the curse of dimensionality. Summary statistics "invariably discard" information. Neural methods offer amortization. Diagnostics (calibration via parametric bootstrap, classifiers between surrogate and simulator, ensembles) are necessary-not-sufficient, and none address misspecification. Source: [PNAS 2020, arXiv:1911.01429](https://arxiv.org/abs/1911.01429).
- [TRANSFER] The **`sbi`** package implements NPE/SNPE (A, B, C, TSNPE), NLE/SNLE, NRE/SNRE (A, B, C, BNRE) and MNLE ([sbi README](https://github.com/sbi-dev/sbi); [Tejero-Cantero et al.](https://arxiv.org/abs/2007.09114)).
- [TRANSFER] **Hermans et al. (TMLR 2022):** all benchmarked SBI algorithms "may produce non-conservative credible regions." They propose an "expected coverage" diagnostic; ensembles give more reliable approximations. [arXiv:2110.06581](https://arxiv.org/abs/2110.06581).
- [TRANSFER] **Simulation-based calibration (SBC):** under correct inference, rank statistics of prior draws within posterior samples are uniform ([Talts et al.](https://arxiv.org/abs/1804.06788)). This is a test of the *inference code*, usable as a unit test of any Phalanx calibration pipeline.

**Aircraft system identification (flight dynamics)**
- [DIRECT] **The NASA LaRC process** (Fig. 2): prior information → experiment design → measured data → data compatibility analysis → model structure determination and parameter estimation → diagnostics → model validation on "different sets of data," with feedback loops. Details:
  - Equation error has "a closed-form analytical solution."
  - Output error "results in the best match to measured outputs" but needs iterative nonlinear optimization.
  - Both are maximum-likelihood under their own assumptions and work in the time or frequency domain.
  - Filter error "includes both process noise ... and measurement noise" via a Kalman filter. It is more general but has "issues with convergence and identifiability."
  - Orthogonal optimized multisine inputs make experiments efficient.
  - SIDPAC has more than 400 MATLAB files and is used at more than 100 institutions.
  - Source: [Morelli & Grauer 2023, doi:10.2514/1.C037274](https://doi.org/10.2514/1.C037274).
- [DIRECT] **Global nonlinear F-16 aerodynamic models** were identified with multivariate orthogonal functions and predicted squared error (PSE). They showed "less than 10% difference" from wind-tunnel data for a simulated doublet. [Morelli, NTRS 20040110310](https://ntrs.nasa.gov/citations/20040110310).
- [DIRECT] **Sensor and mass-property error budgets** were derived by progressively degrading data (noise, resolution, bias) in Monte Carlo runs, giving "recommendations ... for maximum allowable errors" to reach a desired model accuracy. The results were checked on an F-16 simulation. [Grauer & Morelli, NASA/TM-2013-218056](https://ntrs.nasa.gov/citations/20140003885).
- [DIRECT] **Coloured residuals** require corrected parameter-uncertainty bounds (see Q2). [Morelli & Klein 1995](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf).

**Engine model matching and adaptation**
- [DIRECT] **Review of performance adaptation** (Tahan, Tsoutsanis, Muhammad & Abdul Karim, Applied Energy 198:122–144, 2017):
  - Performance adaptation "uses an optimization algorithm to tune the non-measurable component parameters" so model outputs match measurements.
  - Constant-factor map scaling needs a "highly similar" reference engine and known design points.
  - Li et al. used genetic algorithms for "linear and nonlinear scaling factor functions."
  - Stage-stacking and regression map-fitting are alternatives.
  - Component maps are usually proprietary.
  - Source: [SHU Research Archive 16176](https://shura.shu.ac.uk/16176/).
- [DIRECT] **T-MATS** exposes map scalars C_Nc, C_PR, C_Wc and C_Eff, and corrects speed and flow to standard day (518.67 °R, 14.7 psia). These are the "tuning/scalar factors" used to match an engine model to data. [NASA/TM-2014-216638](https://ntrs.nasa.gov/citations/20140012486).
- [DIRECT] **Self-tuning engine models** (Armstrong & Simon, PHM Society 2012):
  - A piecewise-linear Kalman filter adjusts "health parameters" to remove "model mismatch."
  - "Often times the number of sensors ... is less than the number of health parameters," which makes the problem underdetermined.
  - Estimating only a subset causes "'smearing' effects."
  - Source: local `research_sources/methodology/phm2012_armstrong_simon.pdf`; online URL not recorded.
- [DIRECT] **Optimal tuner selection** builds the tuning vector q = V*·h as linear combinations of all health parameters. V* is chosen to minimize the theoretical mean-squared estimation error. [Simon & Garg, NASA/TM-2010-216076](https://ntrs.nasa.gov/citations/20100006914).
- [DIRECT] **Bias and deterioration cannot be told apart.** For the F100 Performance Seeking Control estimator, "An equivalence relation between the biases and engine deviation parameters stems from an observability study; therefore, it is undecided whether the estimated engine deviation parameters represent the actual engine deviation or whether they simply reflect the measurement biases." [España & Gilyard, NASA TM-4551, 1993](https://ntrs.nasa.gov/citations/19940017406).
- [DIRECT] A **bank of Kalman filters** can isolate sensor and actuator faults while estimating component performance parameters. [Kobayashi & Simon, NASA/TM-2003-212526](https://ntrs.nasa.gov/citations/20030067984).

**Digital-twin updating and robotics calibration**
- [TRANSFER: structural digital twins] Kapteyn et al. model asset and twin as coupled dynamical systems in a probabilistic graphical model. A UAV structural twin was calibrated with experimental data and updated in flight from sensor data. [arXiv:2012.05841](https://arxiv.org/abs/2012.05841). The National Academies (2024) define a digital twin as "dynamically updated through bidirectional data flows" and list VVUQ needs as an open question ([NASEM 26894](https://www.nationalacademies.org/publications/26894)).
- [TRANSFER: robotics] Robotics methods for closing the sim-to-real gap:
  - **SimOpt** adapts the simulator parameter distribution "using a few real world roll-outs" ([Chebotar et al.](https://arxiv.org/abs/1810.05687)).
  - **BayesSim** computes a likelihood-free posterior over simulator parameters from real trajectories ([Ramos et al., RSS 2019](https://arxiv.org/abs/1906.01728)).
  - **Neural-augmented simulation** trains an RNN on sim-vs-real trajectory differences, i.e., hybrid residual learning ([Golemo et al., CoRL 2018](http://proceedings.mlr.press/v87/golemo18a.html)).

**Hybrid residual learning: benefits and risks**
- [TRANSFER: scientific ML] **APHYNITY** makes the physics explain "as much of the data as possible" and the ML term "only ... information that cannot be captured by the physical model." Minimizing the ML term's norm gives "existence and uniqueness" of the decomposition and lets the physical parameters be identified. [Yin et al., arXiv:2010.04456](https://arxiv.org/abs/2010.04456) (local copy in `research_sources/methodology/arxiv/`).
- [TRANSFER: scientific ML] "hybrid model performance guarantees are limited to the training distribution." APHYNITY failed on a shifted test distribution, and "expert augmentation" improves generalization. [Wehenkel et al., TMLR 2023](https://arxiv.org/abs/2202.03881).
- [TRANSFER: ML theory] "ReLU MLPs quickly converge to linear functions along any direction from the origin," so they "do not extrapolate most nonlinear functions." [Xu et al., ICLR 2021](https://arxiv.org/abs/2009.11848).

### Inferences
- [ASSUMPTION] **Recommended Phalanx calibration loop.** The modelling-methodology researcher owns the model architecture; this loop covers only calibration and validation.
  1. **Data compatibility on the real (proxy) data.** Run kinematic reconstruction and estimate bias, scale factor and time skew per channel, so that sensor errors in the real data are not "calibrated into" the simulator.
  2. **Split data.** Separate by flight or sortie into calibration, validation and untouched test sets. Keep whole regimes (e.g., all high-g data from one fleet) out of calibration to test extrapolation (cf. RTO-TR-028's warning).
  3. **Identify physics parameters per subsystem:**
     - flight dynamics: equation-error or output-error on manoeuvre segments (doublets, multisines if available);
     - engine: map scalars and health parameters via optimization or Kalman tuning, with tuner selection that respects observability.
  4. **Run history matching first.** Use emulators of key outputs (e.g., EGT margin at take-off, spool-up Ti/Tt, cruise fuel flow) to rule out implausible parameter regions and to detect structural inadequacy (an empty non-implausible space means the model, not the parameters, is wrong).
  5. **Then run Bayesian calibration** (KOH-style or L2) with *informative, physically bounded* discrepancy priors, e.g., discrepancy smooth in corrected speed and small at design point. Alternatively use SBI with an expected-coverage and SBC check.
  6. **Analyse residuals by regime:** mean bias, spectrum and colour, heteroscedasticity, cross-channel residual correlation, and the V&V 20 decision (|E| vs U_val).
  7. **Correct, in this order of preference:**
     - (a) structural physics fix;
     - (b) parameterized physics term;
     - (c) constrained ML residual: minimum-norm, bounded output, gated to regimes seen in training, with an out-of-distribution flag that falls back to physics-only outside the training envelope.
  8. **Validate on held-out flights and regimes** with the full metric set (§2) and the discriminator (§3).
  9. **Version the result:** record calibration data hashes, priors, posteriors, the code version and the decision ([M&S 47] "parameter calibrations"; §6).
- [ASSUMPTION] **Keep bias separate from deterioration in the simulator itself.** The España & Gilyard bias/degradation equivalence implies that Phalanx must generate sensor bias and component deterioration as *separate* latent processes with separate ground truth. Downstream PdM evaluation can then test whether models confuse them. This is a realism requirement, not just a calibration nuisance (cross-link: faults/degradation researcher).

### Gaps
- I did not retrieve the CIFER frequency-domain cost-function acceptance guidelines (Tischler & Remple; commonly quoted average J ≤ 100 for acceptable models), nor time-domain mismatch criteria (Theil inequality coefficient thresholds). They are **unverified** in this session and should not be used until confirmed from the primary text.
- I could not access primary texts of Jategaonkar's *Flight Vehicle System Identification* or Klein & Morelli's book (AIAA pages blocked). The method descriptions above come from Morelli & Grauer (2023).
- Higdon et al. (2008) high-dimensional-output calibration and Arendt et al. (multi-response identifiability) were not retrieved.
- UKF/EKF joint state–parameter estimation: covered here only through NASA engine Kalman-tuner work; general UKF literature was not fetched.

---

## 5. Strategy when the target fighter's data is unavailable

### Takeaway
Treat proxy data as a "representative system" referent (7009B Level 2) and validate what transfers:
- physics invariants and kinematic consistency;
- sensor-physics laws and noise structure;
- dimensionless and corrected relationships (corrected speed and flow, ratios, time constants, modal parameters);
- event and regime structure.

Do not validate absolute fighter-specific levels against airliner or UAV data. Split every test into "platform-independent" and "platform-dependent," as Part 60 does for alternate engines.

Fill platform-dependent gaps with:
- published fighter flight-test and engine reports (digitized at resolution better than ½ the tolerance);
- open NASA fighter models (F-16, F/A-18 HARV) as higher-fidelity referents;
- documented SME and Turing-style reviews by pilots and maintainers.

### Cited Findings
- [DIRECT] 7009B allows validation against "an acceptable alternative (e.g., a testbed, prototype, or similar representative system)." For a similar or analogous system "the closeness of the referent to the RWS becomes pertinent." That caps the validation factor at Level 2. [NASA-STD-7009B](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf), §3.2, §4.2.5, Table 9.
- [DIRECT] **Part 60 alternate-engine logic as a proxy template.** Tests independent of engine type can use "validation data from any engine application." Engine-dependent tests need engine-specific data. Thrust-rating changes of ≥5% up or ≥15% down trigger new flight data. Throttle calibration needs the correct controller hardware and software. [LII App. A, Att. 2 §13](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60).
- [DIRECT] **Alternative data sources (Part 60 §17, Levels A/B):**
  - "Airplane Maintenance Manual, the Airplane Flight Manual (AFM), Airplane Design Data, the Type Inspection Report (TIR), Certification Data or acceptable supplemental flight test data" may be used.
  - This is justified by a "history of successful comparisons" of modelling techniques.
  - Synchronized video must let parameters be measured "to at least 1/2 of the tolerance authorized."
  - Elsewhere, data "may be re-scaled, digitized" if explained (§9.b(5)).
  - Source: [LII App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60); [eCFR](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-D/part-60/appendix-Appendix%20A%20to%20Part%2060).
- [DIRECT] **Corrected parameters** remove ambient effects: T-MATS corrects speed and flow with Tstd = 518.67 °R and Pstd = 14.7 psia ([NASA/TM-2014-216638](https://ntrs.nasa.gov/citations/20140012486)). F404 test-cell diagnostics require "Standard-day corrected engine instrumentation data" ([DTIC ADA408947](https://apps.dtic.mil/sti/citations/ADA408947)). Constant-factor map scaling from a "highly similar" reference engine is a recognized (if limited) way to borrow component characteristics ([Tahan, Tsoutsanis et al.](https://shura.shu.ac.uk/16176/)).
- [DIRECT] **Calibration does not travel automatically.** RTO-TR-028: "the reduced modelling approximation is only valid for the situations where it has been calibrated." New flight profiles require re-checking accuracy. (NATO RTO-TR-028, local copy `research_sources/flight_profiles/RTO-TR-028.pdf`.)
- [DIRECT] **Open fighter models and data as referents** (cross-link: platform-selection, datasets and modelling researchers):
  - NASA's global nonlinear F-16 aerodynamic model ([NTRS 20040110310](https://ntrs.nasa.gov/citations/20040110310));
  - F/A-18 HARV simulation model and F404-specific monitoring and test-cell reports archived by other researchers (`research_sources/airframe_data/`, `research_sources/engine_data/f404_monitoring/`).
- [DIRECT] **Sensor-physics laws transfer across platforms.** The thermocouple time constant scales as τ ∝ (T)^-0.18·(M·p)^-1/2 (NACA TN 3766, as recorded by the sensor-texture researcher, [NTRS PDF](https://ntrs.nasa.gov/api/citations/19930084456/downloads/19930084456.pdf)). Laws like this can be validated on proxy data and applied to the fighter.
- [DIRECT] **SME evaluation is formally used** where objective tests fail, e.g., SME pilot evaluation of high-altitude and turning-flight stalls and of stall buffet ([LII App. A, Attachment 7](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60)). Face validity and Turing tests are standard techniques ([Sargent 2010](https://www.informs-sim.org/wsc10papers/016.pdf)).
- [TRANSFER: computer vision] **A Turing-test design with statistics:** fixed counts of real and synthetic items per subject, randomized order, reference examples visible, and a binomial p-value on aggregate correct calls (517/1000, p = 0.148, vs 162/200, p ≤ 10⁻⁸). [Shrivastava et al.](https://arxiv.org/abs/1612.07828).
- [TRANSFER: data extraction] WebPlotDigitizer offers "computer vision assisted data extraction from charts" ([automeris.io](https://automeris.io/)). I found no accuracy statement on the page.
- [DIRECT] **Data quality limits what calibration can identify.** Grauer & Morelli quantify how noise, resolution and bias errors degrade identified-model accuracy and give maximum allowable errors ([NASA/TM-2013-218056](https://ntrs.nasa.gov/citations/20140003885)). Use this to judge whether digitized or low-rate proxy data can support a given calibration.

### Inferences
- [ASSUMPTION] **Proxy-validation matrix.** For each Phalanx output channel, label each property P (platform-independent) or D (platform-dependent):

  | Property class | Label | Validate against | Credibility claim |
  |---|---|---|---|
  | Sensor transfer functions and lag laws, noise spectra shape, quantization and bus encoding, sampling jitter, dropout patterns | P | Any proxy with the same sensor or bus class (airliner FDR/QAR, GA, UAV, test-cell, NASA flight data) | Up to 7009B Level 2 |
  | Kinematic consistency (rates vs attitudes vs velocities), energy and mass balance, monotonic engine relationships (EGT vs fuel flow vs corrected speed at fixed ambient) | P | Physics invariants; any proxy | Physics-based; strong |
  | Dimensionless and corrected relationships: corrected spool-speed vs corrected flow lines, Ti/Tt ratios normalized by engine class, short-period and Dutch-roll damping ratios (not frequencies), climb and acceleration time ratios | P/D (scaled) | Proxy plus published fighter reports | Level 2; flag scaling assumptions |
  | Absolute levels: thrust, EGT limits, fuel-flow magnitudes, g-envelope, mission-specific regime durations | D | Only fighter-specific published sources (flight manuals, NASA F-16/F-18 reports, engine datasheets, digitized plots) and SME review | Level 1–2 with SME sign-off |
  | Degradation and fault signatures | D | Engine-family literature, fleet maintenance statistics, SME (cross-links: faults/degradation and maintenance-records researchers) | Level 1–2 |

- [ASSUMPTION] **Validate the fighter configuration by "simulate the proxy, then swap the platform."** First configure Phalanx to emulate the proxy platform (e.g., a commercial turbofan or the C-MAPSS-class engine; cross-link: datasets researcher) and pass the full §2/§3 battery against real proxy data. Then change *only* the platform-dependent modules to the fighter configuration. Credibility then rests on the shared modules having been validated and the swapped modules being sourced from documents. This mirrors Part 60's "engine-independent tests from any engine; engine-dependent from engine-specific data."
- [ASSUMPTION] **Digitization rule.** Digitize published plots only when the digitized resolution is at most ½ the tolerance to be applied, by analogy with Part 60 §17.i. Record axis calibration points, digitization repeatability (digitize twice, report the spread), and the source figure ID in the VDR.
- [ASSUMPTION] **SME protocol.**
  - Pilots review flight-parameter traces.
  - Maintainers review engine trend plots and fault and BIT logs.
  - Each judge gets a balanced, randomized mix of real proxy (or redacted real) and synthetic items, with reference examples visible.
  - Score with a binomial test. Collect free-text reasons for every "synthetic" call: these are the actionable outputs, mirroring discriminator explanations.
  - Separate *face validity* questions ("is this plausible for a Tejas/F404?") from *Turing* questions ("which is real?"), since only the latter is a distinguishability test.

### Gaps
- No public, fighter-specific time-series telemetry suitable for Turing tests was identified here (cross-link: datasets researcher).
- I found no published accuracy study of plot digitization tools in this session.
- I found no evidence of how corrected-parameter relationships validated on high-bypass airliner engines transfer to low-bypass afterburning fighter engines (F404/RM12/AL-31). Treat as a scaling assumption to be confirmed against F404 public reports.

---

## 6. Simulator regression testing and reproducibility

### Takeaway
Reproducibility of a stochastic simulator needs four things:
1. deterministic, hierarchical random-number streams (SeedSequence spawning or counter-based generators keyed by scenario, aircraft and sensor);
2. golden reference outputs, analogous to the flight simulator's MQTG, compared by over-plot plus tolerances;
3. three kinds of tests: property-based tests, metamorphic tests (physics-motivated relations between runs) and statistical regression tests (distribution equality or equivalence across versions with fresh seeds);
4. versioning of every model assumption, dataset and calibration (DVC/MLflow), run automatically in continuous validation.

NASA-STD-7009B and Part 60 already require most of this in documentary form.

### Cited Findings
- [TRANSFER: scientific computing] **NumPy seed management:**
  - Spawn child streams with `SeedSequence.spawn()` or `Generator.spawn()`; grandchildren are possible.
  - Use 128-bit entropy seeds (`secrets.randbits`).
  - Collision probability is about n²·2⁻¹²⁸; a million streams gives about 2⁻⁸⁸.
  - "UNSAFE! Do not do this! worker_seed = root_seed + worker_id". Prefer `default_rng([worker_id, root_seed])`.
  - Philox keys and `jumped()` streams are alternatives.

  Source: [NumPy parallel RNG docs](https://numpy.org/doc/stable/reference/random/parallel.html).
- [TRANSFER: HPC] **Counter-based PRNGs** (Philox, Threefry, AES-based) "pass rigorous statistical tests (including TestU01's BigCrush)," "produce at least 2⁶⁴ unique parallel streams ... each with period 2¹²⁸ or more," and need "little or no memory for state." This makes per-entity, order-independent random streams possible. [Salmon et al., SC11, doi:10.1145/2063384.2063405](https://doi.org/10.1145/2063384.2063405) (local: `research_sources/methodology/random123_sc11.pdf`).
- [DIRECT] **NASA-STD-7009B on regression and configuration management:**
  - Regression testing is "Selective checking ... to verify that modifications have not caused unintended effects."
  - Code verification uses regression and unit testing and must consider "changes to the development environment, which includes the compilers, libraries, operating system, and computer hardware."
  - Record updates ("solution adjustment, change of parameters, calibration, and test cases") with a "unique version identifier, description, and the justification."
  - Include "test cases ... that span the M&S limits."
  - Keep models and data in "a controlled CM system."
  - Echo all inputs to a log as solution verification.
  - Source: [NASA-STD-7009B](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf), §3.2, §4.2.2, App. E.3.3.
- [DIRECT] **Part 60 golden reference practice:**
  - The MQTG is the "master document ... to which flight simulator continuing qualification evaluation test results are compared."
  - Over-plotting against the MQTG is encouraged, and there are "no suggested tolerances" against it.
  - Unexplained differences beyond repeatability are investigated.
  - Automatic test drivers are required at Levels C/D, but manual execution must remain possible.
  - Source: [LII App. A](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60).
- [DIRECT] **Benign sources of numerical difference to control** are listed in Part 60 §11 and EASA App. 1 to AMC1 FSTD(A).300: iteration rates, execution order, integration methods, processor architecture, interpolation methods and data handling ([LII](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60); [EASA](https://www.easa.europa.eu/en/downloads/46529/en)).
- [DIRECT] **Configuration control in a NATO engine-life context:**
  - Changes to reduced-order algorithms "will have to go through the verification and validation process."
  - Pre- and post-modification data "must be kept and must be identified separately."
  - Source: NATO RTO-TR-028 Ch. 7 (local copy).
- [TRANSFER: general simulation] Stochastic simulators need replication-based "internal validity" checks and a "schedule for periodic review" ([Sargent 2010](https://www.informs-sim.org/wsc10papers/016.pdf)).
- [TRANSFER: software testing] **Property-based testing:** Hypothesis generates inputs over a described range, "including edge cases," and supports replaying failed tests ([Hypothesis docs](https://hypothesis.readthedocs.io/en/latest/)).
- [TRANSFER: software testing] **Metamorphic testing** (DeepTest, ICSE 2018) uses "transformation-specific metamorphic relations between multiple executions" (e.g., steering should not change much under lighting changes). Relations defined too tightly give many false positives; too permissive, many false negatives. The authors relax relations to "within the error ranges of the original" inputs. [Tian et al., arXiv:1708.08559](https://arxiv.org/abs/1708.08559).
- [TRANSFER: software testing] **Golden-file fixtures:** pytest-regressions provides `num_regression`, `dataframe_regression`, `ndarrays_regression`, `data_regression`, `file_regression` and `image_regression` ([pytest-regressions](https://pytest-regressions.readthedocs.io/en/latest/)).
- [TRANSFER: MLOps] **Versioning and tracking:**
  - DVC tracks data through `.dvc` pointer files committed to Git, with remote storage, `dvc push/pull` and pipelines ([DVC start](https://doc.dvc.org/start)).
  - MLflow logs parameters, metrics, artifacts, tags and dataset metadata (`log_input`) per run, with search and comparison across runs ([MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)).
- [TRANSFER: Bayesian computation] SBC rank-uniformity checks provide a regression test for calibration and inference code ([Talts et al.](https://arxiv.org/abs/1804.06788)).

### Inferences
- [ASSUMPTION] **Seed architecture.** One root seed per dataset release. Spawn streams by a fixed key path, (scenario, aircraft tail, flight, subsystem, sensor, noise-component), using SeedSequence spawn keys or Philox keys, never seed arithmetic. Adding a sensor or aircraft then does not perturb other streams. Store the key path in each record's metadata so any record can be regenerated alone.
- [ASSUMPTION] **Regression test tiers:**
  1. **Bitwise or near-bitwise determinism** for the same seed, platform and version. Run on a pinned container with pinned BLAS and threads; 7009B notes the effect of compiler, library and hardware changes.
  2. **Golden objective-test suite ("Phalanx MQTG"):** replayed manoeuvres and engine transients, with Tier-2 tolerances of about 20–40% of the Tier-1 validation tolerances (EASA/FAA analogy), plus over-plot artefacts.
  3. **Statistical regression:**
     - N independent-seed ensembles from the old and new versions;
     - compare per-regime distributions and spectra with permutation or bootstrap tests;
     - prefer *equivalence* testing (difference within a pre-set margin) over "no significant difference," because large ensembles make trivial differences significant;
     - re-run the discriminator battery between old and new versions;
     - an *intended* model change must show up and be documented; any other difference must not.
  4. **Metamorphic relations specific to aircraft physics, with tolerance bands:**
     - resampling at 2× rate leaves PSD below the old Nyquist frequency unchanged;
     - an ISA temperature offset leaves corrected spool-speed and flow relationships invariant;
     - mirrored lateral inputs give mirrored lateral responses;
     - a time shift of the scenario gives a time-shifted output;
     - zero degradation rate gives a flat health trend apart from noise;
     - more degradation gives a monotone decrease in EGT margin;
     - a fault-free run gives no fault codes, apart from the configured false-alarm rate.
  5. **Property-based invariants:** envelope limits, non-negativity, energy and mass balance residual below a threshold, sensor saturation behaviour, and units.
- [ASSUMPTION] **Continuous validation pipeline.** On every merge: run tiers 1–2 and the property tests. Nightly: run tiers 3–4 plus the §2 metric battery and the §3 discriminator ladder against frozen real proxy splits. The output is a dashboard and an automatically generated "credibility card" (7009B factor levels, domain of validation, open issues).

  **Assumption registry.** Keep every modelling assumption as a versioned record with ID, statement, source, date, owner, affected modules and tests, and status, linked from DVC and MLflow runs. This implements [M&S 11] and [M&S 47].

### Gaps
- I found no aerospace-specific guidance on statistical regression testing of *stochastic* simulators. Part 60 assumes deterministic replays plus repeatability. The equivalence-testing recommendation is an assumption; no source was fetched for TOST or equivalence tests.
- Hypothesis shrinking and stateful-testing details were not verified (main docs page only).

---

## 7. Synthesis (requested end-matter): key findings, staged validation protocol, open gaps, ranked sources

### Takeaway
Phalanx should use a **layered, risk-informed credibility case**:
- objective tests modelled on flight-simulator qualification;
- physics-invariant and kinematic checks;
- regime-wise statistical batteries;
- a carefully controlled real-vs-synthetic discriminator;
- downstream-utility tests;
- structured SME/Turing reviews.

It is supported by an explicit calibration loop with discrepancy modelling and by regression and reproducibility machinery. Its credibility claims should be stated honestly: with proxy data the validation factor is NASA-STD-7009B Level 2.

### Cited Findings — (a) Key findings summary
1. [DIRECT] **Credibility levels.** Validation against a "representative system" earns at most NASA-STD-7009B Validation Level 2. Levels 3–4 need real-system data ([NASA-STD-7009B Table 9](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf)).
2. [DIRECT] **Concrete numeric tolerances exist.** Flight-simulator objective tests (Part 60 Table A2A / CS-FSTD(A)) include:
   - short period ±1.5° pitch or ±2°/s and ±0.1 g;
   - phugoid ±10% period;
   - Dutch roll ±0.5 s or ±10% period, ±0.02 damping;
   - engine acceleration ±10% Tt and (±10% Ti or ±0.25 s);
   - cruise ±5% fuel flow;
   - control-dynamics period tolerances of ±10% (P0) to ±10(n+1)% (Pn).

   Engineering-simulator reference data must match within 40% (FAA) or 20% (EASA) of these. Tolerances must not be met by tuning only at the test points ([LII](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60); [2015 CFR](https://www.govinfo.gov/content/pkg/CFR-2015-title14-vol2/pdf/CFR-2015-title14-vol2-part60-appA.pdf); [EASA](https://www.easa.europa.eu/en/downloads/46529/en)).
3. [DIRECT] **Engine-model practice.** A tuned F404 test-cell model was about 1% on T45 across 21 engines, "good enough ... for diagnostic purposes" ([DTIC ADA408947](https://apps.dtic.mil/sti/citations/ADA408947)). Same-engine in-flight repeatability was about ±2% fuel flow and ±0.5% N1/N2 ([DTIC ADA219105](https://apps.dtic.mil/sti/citations/ADA219105)). These are natural floors for engine tolerances.
4. [DIRECT] **The sysID loop.** Aircraft system identification gives a proven calibrate-then-validate loop: data compatibility, structure, EE/OE/filter-error, diagnostics, prediction on unseen data. Real residuals are coloured, and ignoring that makes uncertainty bounds optimistic ([Morelli & Grauer 2023](https://doi.org/10.2514/1.C037274); [Morelli & Klein 1995](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf)).
5. [DIRECT/TRANSFER] **Calibration without explicit discrepancy is biased and overconfident.** Discrepancy and parameters are confounded. In engines, sensor bias and deterioration can be observationally equivalent ([Brynjarsdóttir & O'Hagan](https://iopscience.iop.org/article/10.1088/0266-5611/30/11/114007); [Tuo & Wu](https://arxiv.org/abs/1507.07280); [España & Gilyard](https://ntrs.nasa.gov/citations/19940017406)).
6. [TRANSFER] **C2ST is principled but needs careful setup.** It has a simple binomial null and interpretable outputs ([Lopez-Paz & Oquab](https://arxiv.org/abs/1610.06545); [Kim et al.](https://arxiv.org/abs/1602.02210)). It is easily dominated by shortcuts ([Müller et al.](https://arxiv.org/abs/2106.12914)) and leakage ([scikit-learn](https://scikit-learn.org/stable/modules/cross_validation.html)). Its failure to discriminate cannot certify closeness ([Arora et al.](https://arxiv.org/abs/1703.00573); [Cranmer et al.](https://arxiv.org/abs/1911.01429)).
7. [TRANSFER] **ML synthetic-time-series metrics are unstable and disagree.** TimeGAN DS/PS, Context-FID and TSGBench measures vary with initialization, architecture, dataset size and embedding ([TSGBench](https://arxiv.org/abs/2309.03755); [STEB](https://arxiv.org/abs/2505.21160)). Reference implementations can differ from their papers ([TimeGAN code](https://github.com/jsyoon0823/TimeGAN/blob/master/metrics/discriminative_metrics.py)).
8. [TRANSFER] **Downstream predictivity is a powerful complementary metric.** Robotics improved sim-vs-real correlation from 0.18 to 0.844 by tuning simulator parameters ([Kadian et al.](https://arxiv.org/abs/1912.06321)).
9. [TRANSFER] **Hybrid residual models are only trustworthy inside their training distribution** unless constrained ([Wehenkel et al.](https://arxiv.org/abs/2202.03881); [Xu et al.](https://arxiv.org/abs/2009.11848)). Minimum-norm decompositions restore identifiability ([APHYNITY](https://arxiv.org/abs/2010.04456)).
10. [DIRECT/TRANSFER] **Reproducibility needs** hierarchical seeded RNG streams ([NumPy](https://numpy.org/doc/stable/reference/random/parallel.html); [Random123](https://doi.org/10.1145/2063384.2063405)), a golden reference (Part 60 MQTG) and version-controlled assumptions, data and calibrations ([NASA-STD-7009B](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf); [DVC](https://doc.dvc.org/start); [MLflow](https://mlflow.org/docs/latest/ml/tracking/)).

### Inferences — (b) Staged validation protocol proposal (all [ASSUMPTION] unless a citation is shown)

**Acceptance-criteria philosophy**
- **Intended use first.** Write the Phalanx intended use and decision consequence before choosing criteria, scaling rigour to model risk ([V&V 40 summary](https://pmc.ncbi.nlm.nih.gov/articles/PMC6966181); [Sargent step 2](https://www.informs-sim.org/wsc10papers/016.pdf); [M&S 43](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf)). The intended use is: training and benchmarking PdM and fleet-availability models; demonstrating the data-streaming architecture.
- **Tolerance rule.** Tolerance = max(measurement-uncertainty floor U_val, real-vs-real natural-variability floor, intended-use requirement). It is never tighter than real repeatability.
- **Interpretation rule.** Use V&V 20 logic: |E| ≤ U_val means "within noise," not "proven correct" ([V&V 20 procedure](https://maretec.tecnico.ulisboa.pt/~maretec.daemon/html_files/VV2010_files/ValidationProcedure.pdf)).
- **Failure rule.** A test fails when it "clearly" falls outside tolerance. Judgement covers multiple related parameters, never one alone ([Part 60 Att. 2 §2.d, §11](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60)).
- **No tuning to the test points.** Calibration and validation data are disjoint by flight. Hold out at least one regime family from calibration ([Part 60 §2.e](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60)).
- **Report per factor.** Report credibility per 7009B factor (data pedigree, verification, validation level, review, process) and per channel and regime ("domain of validation"), not as a single realism score.

**Layer 0: Governance (before building)**
- Intended-use statement, risk rating, acceptance criteria for verification, validation, uncertainty and sensitivity.
- Validation-data roadmap (VDR) matrix: test × data source × P/D label × tolerance.
- V&V Plan following the MIL-STD-3022 template.
- Assumption registry.

**Layer 1: Component unit verification (every commit)**
- Analytic or closed-form checks: first-order lag step response τ; quantizer LSB and saturation; ARINC/1553 encode–decode round trip; thermocouple lag law vs NACA TN 3766 scaling; actuator rate limits.
- Property-based tests for units, ranges and monotonicity.
- Metamorphic relations per component.
- Deterministic seeds.
- Metrics: exact equality or absolute tolerance. Pass = 100%.

**Layer 2: Subsystem validation against proxy or reference data (per release)**
- **Engine** (F404-class configured as the proxy engine first):
  - steady-state corrected-parameter lines (N2c vs Wfc, EGT vs N2c) within max(1–2%, real repeatability);
  - transient Ti/Tt within ±10% / ±0.25 s analogues;
  - spool energy-balance residual about 0;
  - calibrate map scalars and health parameters with observability-aware tuners.
- **Flight dynamics:**
  - replay recorded inputs from NASA F-16/F-18 or proxy data;
  - Part 60-style modal tests (short period, Dutch roll, phugoid) and trims, with tolerances adapted from Table A2A;
  - kinematic-consistency reconstruction residuals.
- **Sensors and data pathway:** noise PSD and Allan-type statistics, quantization histograms, sample-interval jitter, dropout runs vs proxy recorder data (cross-links: sensor-texture and data-pathway researchers).
- Record E, U_val and |E|/U_val for each test.

**Layer 3: Integrated scenario validation (per release)**
- Full sorties along realistic profiles (cross-link: flight-profiles researcher).
- Regime segmentation accuracy.
- Cross-subsystem consistency: throttle → spool → EGT → fuel flow → thrust → acceleration.
- Event and exceedance rates vs real (Poisson E-test).
- Envelope adherence and invariants.
- RTO-TR-028-style "standard sortie" exercising all logic paths.

**Layer 4: Statistical ensemble validation (nightly)**
- Per regime and channel:
  - KS/AD (permutation p), Wasserstein/energy, MMD;
  - ACF/PSD/coherence distances;
  - lagged cross-correlation and MI;
  - tail POT comparisons;
  - missingness;
  - area metric with u-pooling over conditions.
- All with block-bootstrap CIs.
- Each compared against the real-vs-real reference distance.
- Pass when the sim-vs-real distance is ≤ the real-vs-real distance (or within a pre-agreed multiple) for P-labelled properties.

**Layer 5: Discriminator battery (nightly or weekly)**
- Trivial-cue audit → canonicalized pipeline → matched conditions → classifier ladder (features → ROCKET/CNN/GRU) at 2–3 window lengths.
- GroupKFold by flight and aircraft; group-level permutation test.
- Report accuracy and AUC with CI next to the real-vs-real baseline.
- Feature-family ablation plus SHAP/permutation importance (clustered).
- Every significant finding becomes a ticket against a simulator module, which is then re-tested with fresh seeds and a fresh classifier.
- Use the critical-accuracy table in §3 to size test sets; target at least 1000 independent windows from at least 50 flights per class.

**Layer 6: Downstream utility (per release)**
- TSTR and TRTS for the PdM tasks: RUL, anomaly detection, fault isolation.
- SRCC-style test: does ranking candidate PdM models on Phalanx data predict their ranking on real proxy data?
- α-precision/β-recall/authenticity to catch mode collapse and copying of proxy records.

**Layer 7: SME / face / Turing review (milestones)**
- Pilots and maintainers; balanced, randomized real vs synthetic sets; binomial test; reasons logged.
- Face-validity checklist for fighter-specific (D-labelled) behaviour that proxies cannot validate.
- SME sign-off recorded as 7009B "technical review" evidence.

**Layer 8: Regression and continuous validation (always)**
- Golden "Phalanx MQTG" over-plots.
- Tier-2 tolerances (about 20–40% of Tier-1).
- Statistical equivalence tests between versions.
- DVC/MLflow lineage.
- Credibility card regenerated per release.
- Periodic re-validation when proxy data, profiles or calibrations change (RTO-TR-028; Sargent step 8).

### Gaps — (c) Open questions and gaps
- **Search budget.** The WebSearch budget ran out partway through. These items were not retrieved and may change some recommendations:
  - aerospace examples of C2ST or adversarial validation of flight or engine simulators;
  - military flight-simulator qualification tolerances;
  - CIFER and Theil-coefficient acceptance thresholds;
  - SAE/OEM engine test-cell correlation tolerances;
  - NATO MSG/SISO GM-VV.
- **Paywalled primary texts not read:** ICAO Doc 9625, ASME V&V 10/20/40 and AIAA G-077, Klein & Morelli and Jategaonkar books. Their content here is through derived or authoritative summaries.
- **Part 60 table edition.** Table A2A values come from the 2015 CFR edition; the current eCFR table is an image after the 2022 amendment. Values agree with EASA 2018 for spot-checked rows, but confirm against the current edition.
- **No validated method yet** for transferring corrected-parameter relationships from high-bypass proxy engines to afterburning low-bypass fighter engines.
- **Open question for the team:** what discriminator accuracy, relative to the real-vs-real baseline, is "good enough" for the PdM intended use? This should be set by sensitivity studies (does PdM performance change when the discriminator-detected artefacts are removed?), not by convention.
- **Online URLs not recorded** for NATO RTO-TR-028 and Armstrong & Simon (PHM 2012); local copies exist.

#### (d) Ranked list of most valuable sources
1. **NASA-STD-7009B (2024):** credibility factors, validation levels, referent and representative-system concept, record requirements. [PDF](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf)
2. **14 CFR Part 60 App. A, Attachment 2:** objective-test structure, Table A2A tolerances, matching rules, engineering-sim 40% rule, MQTG regression practice. [LII](https://www.law.cornell.edu/cfr/text/14/appendix-A_to_part_60); [2015 CFR PDF](https://www.govinfo.gov/content/pkg/CFR-2015-title14-vol2/pdf/CFR-2015-title14-vol2-part60-appA.pdf)
3. **EASA CS-FSTD(A) Issue 2:** tolerance rationale, 20% engineering-sim rule, Proof-of-Match, ICAO 9625 lineage. [PDF](https://www.easa.europa.eu/en/downloads/46529/en)
4. **Morelli & Grauer 2023, "Advances in Aircraft System Identification at NASA Langley":** the calibrate/validate loop for aircraft. [doi](https://doi.org/10.2514/1.C037274)
5. **Lopez-Paz & Oquab 2017 (C2ST)** and **Kim et al. (Annals of Statistics):** significance and power of discriminator tests. [arXiv 1610.06545](https://arxiv.org/abs/1610.06545); [arXiv 1602.02210](https://arxiv.org/abs/1602.02210)
6. **TSGBench (VLDB 2024):** documented failure modes of DS/PS/C-FID. [arXiv](https://arxiv.org/abs/2309.03755)
7. **Brynjarsdóttir & O'Hagan 2014** plus **Kennedy & O'Hagan 2001** plus **Tuo & Wu:** discrepancy and identifiability. [IOP](https://iopscience.iop.org/article/10.1088/0266-5611/30/11/114007); [JRSS-B](https://academic.oup.com/jrsssb/article/63/3/425/7083367); [arXiv](https://arxiv.org/abs/1507.07280)
8. **España & Gilyard NASA TM-4551** plus **Simon & Garg** plus **Armstrong & Simon:** engine-model tuning observability; bias–deterioration equivalence. [NTRS](https://ntrs.nasa.gov/citations/19940017406); [NTRS](https://ntrs.nasa.gov/citations/20100006914)
9. **Roemer et al. (F404 test cell)** and **ARL-PROP-TM-450:** concrete engine-model accuracy and repeatability numbers. [DTIC](https://apps.dtic.mil/sti/citations/ADA408947); [DTIC](https://apps.dtic.mil/sti/citations/ADA219105)
10. **Andrianakis et al. 2015 (history matching tutorial).** [PLoS CB](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003968)
11. **Morelli & Klein 1995 (coloured residuals).** [NTRS](https://ntrs.nasa.gov/api/citations/19970012888/downloads/19970012888.pdf)
12. **ASME V&V 20-based validation procedure (E, U_val).** [PDF](https://maretec.tecnico.ulisboa.pt/~maretec.daemon/html_files/VV2010_files/ValidationProcedure.pdf)
13. **Sargent 2010 (validation technique catalogue, Turing tests, minimum steps).** [WSC](https://www.informs-sim.org/wsc10papers/016.pdf)
14. **Cranmer et al. 2020** plus **Hermans et al. 2022** plus **Talts et al.:** SBI pitfalls and coverage diagnostics. [arXiv](https://arxiv.org/abs/1911.01429); [arXiv](https://arxiv.org/abs/2110.06581); [arXiv](https://arxiv.org/abs/1804.06788)
15. **Müller et al. 2021** plus **Geirhos et al. 2020** plus **Kapoor & Narayanan:** shortcut and leakage pitfalls. [arXiv](https://arxiv.org/abs/2106.12914); [arXiv](https://arxiv.org/abs/2004.07780); [arXiv](https://arxiv.org/abs/2207.07048)
16. **SimGAN (CVPR 2017)** and **Kadian et al. (RA-L 2020):** human Turing-test statistics and downstream sim-to-real predictivity. [arXiv](https://arxiv.org/abs/1612.07828); [arXiv](https://arxiv.org/abs/1912.06321)
17. **NATO RTO-TR-028 Ch. 7:** validation of reduced engine-life algorithms, "valid only where calibrated." (local copy)
18. **NumPy parallel RNG docs** plus **Random123:** reproducible stream management. [NumPy](https://numpy.org/doc/stable/reference/random/parallel.html); [doi](https://doi.org/10.1145/2063384.2063405)
19. **Wehenkel et al. / APHYNITY / Xu et al.:** hybrid residual-learning risks. [arXiv](https://arxiv.org/abs/2202.03881); [arXiv](https://arxiv.org/abs/2010.04456); [arXiv](https://arxiv.org/abs/2009.11848)
20. **Alaa et al. 2022 (α-precision/β-recall/authenticity)** and **Synthcity/SDMetrics** documentation (conventions). [arXiv](https://arxiv.org/abs/2102.08921); [Synthcity](https://github.com/vanderschaarlab/synthcity); [SDMetrics](https://docs.sdv.dev/sdmetrics/data-metrics/metrics-in-beta/detection-sequential)
