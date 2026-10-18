# `phalanx.acquisition`: M13 acquisition and residual texture (W1.6)

Physical sensor output → digitised acquisition value: the `s_meas` and `s_acq` stages of the normative chain
(architecture §7), the clock-domain sampling of each acquiring LRU (§8) and the CIR (W0.4 `CIR_SCHEMA`). Only
**sensor-independent** effects live here (AD-04): idiosyncratic noise, the double quantiser, saturation, gating,
deadband, episodic freeze, glitch words and analog slip-window sentinels. No coupled dynamics.

Binding sources: architecture §6 M13, §7, §8, AD-04, AD-05, AD-06, AD-38; W1.6 brief; `W1_interfaces.md` §3;
round-2 REPORT §3.5 and PREREGISTRATION A2-A4; W0.5 noise-ceiling finding; `docs/behavioural_targets.md`.

## Two entry points, one path

```python
from phalanx.acquisition.config import build_acquisition_config
from phalanx.acquisition.core import AcquisitionCore, STREAMS  # the shared path; stream declarations
from phalanx.acquisition.module import LaneAcquisition, lane_channels, lane_port  # in-loop
from phalanx.acquisition.record import AcquisitionRecorder, frames_from_trace  # recording -> CIR

lanes = lane_channels(d, sens_cfg, "FADEC")  # FADEC-acquired M12 channels (DFCC: DFCC + ADC lanes)
acq = build_acquisition_config(d, lanes, sensor_channels=sens_cfg.channels)
m13 = LaneAcquisition("acq_fadec", params, sens_cfg, acq, d)  # ports lane_<id>, _t, _n, _first, _q
rec = AcquisitionRecorder(
    build_acquisition_config(d, all_ids, sensor_channels=sens_cfg.channels), rng.scope(system_identity)
)
state, records = rec.process(rec.init_state(), k0, S, X, phase, external={"ENG.N2.V": (v_si, truth_si)})
cir = rec.to_cir(load_contract("v0"), tail_no, sortie_id, records, epoch_ns=scenario_epoch_utc_ns)
```

- **In-loop** (`LaneAcquisition`, 240 Hz module): for each controller lane a clock-domain sample buffer
  (`core.sampling`): `lane_<id>` = SI value of the digitised reading (quantised in EU, then `eu_to_si`),
  `lane_<id>_t` instants [ns], `lane_<id>_n` count this step, `lane_<id>_first` absolute index of slot 0,
  `lane_<id>_q` acquisition flags the hardware knows (sentinel, saturation, gating). A controller binds
  `lane.<channel_id>` to `lane_<id>` (`ports.lane_bindings()`). Inputs: `sens.s_<group>` and `scenario.phase`.
- **Recording** (`AcquisitionRecorder`, explicit state, chunk-independent): consumes M12 frames (e.g. a trace
  chunk, `frames_from_trace`) plus externally computed values for LRU-computed channels, emits per-stream samples
  and a validated `CirBatch`.
- Both call `AcquisitionCore.process` with the same tables and the same keyed streams indexed by **absolute sample
  number**, so `eu_to_si(CIR value) == lane value` bitwise at every acquisition instant (A6, tested through the
  scheduler).

## Model (numbers in `configs/tejas/params/M13.yaml`; rules in `M13/acquisition_map.yaml`; grids from M01)

Per sample, in this order (see `kernel.py`): point or interval-average sampling (frequency sensors: period
counting, A-W1.6-29) → deadband → AR(1) noise with phase multiplier and heavy-tail mixture → native step, recorder
lattice, saturation (`OUT_OF_RANGE`) → gating (`NO_COMPUTED_DATA` + `GATED`) → episodic freeze (unflagged) →
glitch word (top of scale, unflagged) → analog slip sentinel (bottom of scale, `SENTINEL`).

- **Clock domains** (A-W1.6-21): one `core.time.ClockDomain` per crystal and rate. The crystal is the dictionary
  acquisition domain: the acquisition rate group's domain LRU (FCS80 → DFCC, FADEC-INT → FADEC, FTI → FTI_DAS,
  so ENG.WFAB is on FTI_DAS), else the channel's `acq_lru`; `clock_consistency_problems` enforces it at build.
  FADEC 60 Hz +50 ppm, phase 3.1 ms; DFCC exact 80 Hz on truth frames k ≡ 0 mod 3 (the ADC air-data channels
  ride on it); utility EU, ECFM-C, FTI DAS with small offsets. One oscillator per LRU across its rates. W2.2
  phase B added the avionics and digital LRU clock sets (INGPS, AHRS, RADALT, SMS, CWS, OAC, RADAR, ECMS;
  A-W2.2-13), so the INS/GPS, AHRS and radar-altimeter outputs and every dictionary word are acquirable.
- **Word path** (W2.2, A-W2.2-12): a status, discrete, enum or code word (encoding bitfield / enum / code_word,
  no native step) is the producer's integer. `MODE_HOLD` reads the word published last (the frame-start value,
  held, never interpolated); step 1 with full scale = the word's bits (a code word: largest prefix × scale +
  number); no noise, deadband, freeze, gate, glitch or slip. An event-driven word (no periodic acquisition rate)
  is read at its bus refresh rate (`config.acquisition_rate`). Tested exact through M15/M16/M17
  (`tests/integration/test_w22_word_path.py`, with an interpolating negative control).
- **Slip** (AD-06, A-W1.6-24): a converter clock offset by Δ_conv (910 ppm, the DASHlink value) from the read
  clock; analog channels convert in slots spread over one period; a read within ±w/2 of its conversion returns
  the sentinel with p_in. Bursts recur every 1/(f·Δ) with fixed phase relations; there is no other dropout.
  Enabled for the utility EU, ECFM-C and FTI DAS, not for FADEC/DFCC/ADC (no separate converter clock).
- **Noise ceiling** (A-W1.6-22/23): N1 lanes 0.61 native steps (0.019 %), N2 0.16 (0.005 %), T5 and WFM 0, other
  sensors 0.144 steps (half the quantiser σ), computed words 0. `build_acquisition_config` refuses any channel
  whose effective σ (× max phase multiplier × tail inflation) exceeds the measured idiosyncratic level of its
  class (N1 0.0313 %, N2 0.0082 %, EGT 0, FF 0; q/√12 elsewhere).
- **Converter step** (dictionary 0.1.2 migration, W2.2; 0.1.3): the 12 FADEC lanes (N1, N2, T1, PS3, PLA, A8;
  A/B) are quantised at the FADEC converter resolution (span / 2^14, R-FADEC-ADC, A-W0.3-41), finer than the
  recorded word; since dictionary 0.1.3 it is their `native_step` (0.1.2 carried it as `converter_step`). Their
  noise and ceilings are given in EU (`sigma_eu`: `noise_n1`, `noise_n2`, `noise_fadec_*`, `ceiling_fadec_*`),
  equal to the W1.6 EU levels, so the move changed no quantiser, noise or ceiling (tested against a 0.1.2 view in
  `tests/integration/test_w22_datapath_migrations.py`). A dictionary that carries `converter_step` (the DASHlink
  proxy) still quantises at it, and the builder refuses its noise or ceiling in steps.

## Evidence for the noise ceiling (A3)

`tests/integration/test_acquisition_noise_ceiling_data.py` (data, slow; 20 Tail-652 flights vs 20 Tail-687, round-2
sample batch, 2,000 resamples): adding M13's AR(1) noise at the measured idiosyncratic level on top of real flights
(≈2× the idiosyncratic variance) PASSES all six tests (B1 fast D_sim 0.0026 vs bar 0.046; B3 (i) 0.020 vs 0.096;
B4 0.049 vs 0.161), while ±1 LSB of independent noise FAILs B1 (0.102), B3 (i) (0.207) and B4 (0.538),
reproducing the W0.5 finding.

## Wiring notes for W2.1

1. Order: truth modules → `SensorPhysics` (M12) → `LaneAcquisition` per controller; controllers read their lanes
   through documented one-frame-delayed back-edges (or a fused loop). Wire `phase` from `scenario.phase` without
   delay, and feed the recorder the same phase sequence.
2. Controllers and M15 take their clock from `config.acquisition_clock(lru, rate)`, the domain M13 samples on.
3. Declare `core.STREAMS` in the run's `StreamRegistry` (the recorder refuses otherwise) and give the recorder
   `rng.scope(system_identity)`: same identity → same keyed noise as the in-loop lanes.
4. Run the recorder from the sortie start (≈1 ms per simulated second for all 132 channels), chunk by chunk
   from the M12 trace; its AR(1), freeze and counting states must evolve over the same samples as the lanes'.
5. LRU-computed channels (`.V` voted words, FADEC `ENG.T5`, gauged totals, ADC air data) need their owner's SI
   value per truth frame as `external={channel: (value, truth)}`.
6. `health.sensor_bias` index map = `SensorConfig.bias_index()`; M11 sensor-fault payload in the M12 README.

## Assumptions

A-W1.6-21 … A-W1.6-32 in `docs/assumptions.md` (W1.6 section); the W2.2 word path and LRU clock sets are
A-W2.2-12 and A-W2.2-13 (W2.2 section). No PROXY items in M13.

## Validation (acceptance → tests)

| Criterion | Tests |
|---|---|
| A2 double quantiser, saturation, lattice; G1 vs the measured residue usage | `tests/unit/test_acquisition_quantiser.py` |
| A3 noise σ, ACF, PSD, tails; ceiling (config + negative tests; real-data battery) | `tests/statistical/test_acquisition_noise_statistics.py`, `tests/unit/test_acquisition_noise.py`, `tests/integration/test_acquisition_noise_ceiling_data.py` |
| A4 slip period 1/(f·Δ), analog only, no NaN, no independent dropout | `tests/unit/test_acquisition_slip.py`, `tests/unit/test_acquisition_core.py::test_no_nan_for_any_channel` |
| A5 CIR conformance, EU, truth only in `truth_value` | `tests/unit/test_acquisition_record.py` |
| A6 controller saw = recorded, bitwise | `tests/integration/test_acquisition_inloop_vs_record.py` |
| A7 G0 hook on healthy vs fault runs (+ leaky negative control) | `tests/integration/test_acquisition_g0.py` |
| A8 compiled = reference, block independence, snapshot round trip, CRN per sensor stream | `tests/unit/test_acquisition_core.py`, `tests/fork/test_acquisition_fork.py` |
| Artefacts, clocks | `tests/unit/test_acquisition_artefacts.py`, `tests/unit/test_acquisition_clocks.py` |
| Word path: held, exact, on the LRU clock, compiled = reference, through the full path (W2.2) | `tests/integration/test_w22_word_path.py` |

## Known limitations

- The value read on an analog path is the signal at the read instant; the converter's sample-and-hold staleness
  (≤ one period) is not modelled (A-W1.6-24).
- Phase multipliers are 1 (the measured heteroscedasticity is coupled residual owned by M03/M07).
- Recorder/bus timing (duplicates, skips, time words) is M15/M16; CIR is acquisition-level.
- `cir_from_streams` builds Python lists (≈0.3 s per minute of all 132 channels); the kernels themselves run the
  60 s recording in 0.04 s.
