# `phalanx.sensors`: M12 sensor physics and sensor dynamics (W1.6)

Truth → physical sensor output: the `s_phys`, `s_dyn` and `s_inst` stages of the normative measurement chain
(architecture §7). Coupled behaviour stays in the truth physics (M07/M06/M09); this module adds only what each
sensor physically does to the quantity it measures. M13 (`phalanx.acquisition`) then samples, adds idiosyncratic
noise, quantises and builds CIR.

Binding sources: architecture §6 M12, §7, AD-07, AD-22, AD-23, AD-26; W1.6 brief; `W1_interfaces.md` §2-§3;
round-2 REPORT §3.2 (τ_FFs 0.218 s, τ_TC,ref 0.81 s, proxy).

## Interfaces

```python
from phalanx.sensors.config import build_sensor_config  # channel map + M12.yaml + dictionary -> tables
from phalanx.sensors.module import SensorPhysics, apply_sensor_fault, SENSOR_FAULT_EVENT, FAULT_STREAM
from phalanx.sensors import ports  # PREFIX "sens", ports(n_engines)

cfg = build_sensor_config(load_dictionary())  # 132 Tejas channels, 129 elements
m12 = SensorPhysics("sens", load_param_set("M12", "constants"), cfg)  # 240 Hz, compiled kernel
cfg.groups["k"]  # index map of the K-unit group (channel indices)
cfg.bias_index()  # health.sensor_bias index map (= cfg.channels)
```

| Port | Unit | Shape | Meaning |
|---|---|---|---|
| inputs `eng_n1`, `af_alpha`, `env_p_s`, … | SI (catalogue) | catalogue | W1 truth signals named in the channel map (bindings = catalogue keys, e.g. `eng_n1 -> eng.n1`) |
| `health_sensor_bias` | SI per channel (`"1"` port, as the catalogue) | (n_ch,) | installation bias + aging per channel (M10, hidden truth; index map = `cfg.bias_index()`) |
| outputs `s_<group>` | group SI unit | (n_group,) | sensor reading `s_inst` per SI-unit group (`k`, `pa`, `rad`, `rad_per_s`, `kg_per_s`, `m_per_s2`, `1`, `m`, `kg`, `v`) |
| outputs `x_<group>` | group SI unit | (n_group,) | true measurand at the frame end (only for CIR `truth_value`, restricted) |

**Sensor-fault events** (M11 → M12; event kind `sensor_fault`, target = the M12 module id). Payload:
`channel` (dictionary id), `mode` ∈ `bias | drift | stuck | open | short | intermittent | spikes | slow |
probe_open | probe_short | clear`, `value` (SI: bias step; drift rate per s; short reading; spike amplitude;
probe short reading; `slow` = τ multiplier ≥ 1), `rate` (1/s: spike rate, intermittent state changes),
`duty` (intermittent open fraction), `probe` (harness probe index). Faults change state only (I6); open reads the
bottom of the channel's range; an open T5 probe drops out of its harness average; a shorted probe reads low.

## Model (per class; numbers in `configs/tejas/params/M12.yaml`, structure in `M12/channel_map.yaml`)

| Class | H_sensor | D_sensor | Evidence |
|---|---|---|---|
| T5 harness (2 × 4 probes) | probe = T5 (+ pattern offset 0) | each probe 1st order, τ = τ_ref (W/W_ref)^-0.5, W = `eng.w2` | F404-400 band 1.25–3.9 s (TRANSFER); AGARD law; A-W1.6-4 |
| N1, N2 pick-offs | shaft speed | none (interval averaging in M13) | CR-191195 (TRANSFER) |
| T1 RTD / T25 | inlet / HPC-inlet temperature (+0.2 K de-icing) | 1st order, flux-scaled | A-W1.6-3, -5 |
| PS3, P5, oil P/T, hyd P/T | linear | 1st order | MIL-PRF-25435D (TRANSFER); A-W1.6-6, -7, -19 |
| Fuel flow (main, AB) | `eng.wf`, `eng.wf_ab` | 1st order (+ optional update hold) | round-2 τ_FFs (proxy) transferred, A-W1.6-8 |
| LVDT/RVDT (A8, VG, PLA, surfaces, stick, pedal) | linear (A8 % stroke ∝ area; airbrake mm = arm·angle) | none | A-W1.6-9, -10 |
| Static / total pressure | p_s + k(M) q_c (PROXY: Mach-only table); pitot isentropic / Rayleigh | 1st order, λ = λ_SL (μ/μ_SL)/δ | Gracey, AGARD-AG-300 (TRANSFER); A-W1.6-11, -12 |
| AoA / AoS vanes (4 pick-offs share one vane) | (1 + k_u)·angle + b(M) + k_bend (n_z − 1) | 2nd order, f_n = k_f V_EAS, ζ | TN D-8242, TM-101714 (TRANSFER); Tejas SADP slope (DIRECT); A-W1.6-13 |
| TAT | T_s (1 + 0.2 r(M) M²) + DHE(Mρ/ρ₀) while `util.probe_heat` is on (W2.2; was a constant) | 1st order, τ ∝ (ρV)^-0.5 | NCAR Rosemount 102 (TRANSFER); A-W1.6-14 |
| W2.2 item 2: brake pressure (`util.brake_p`), reservoir level (`util.hyd_res_level`), fuel inlet RTD (`util.fuel_inlet_t`), ECS duct / compartment RTDs and absolute pressures (`util.ecs_t` / `util.ecs_p` points) | linear | brake: the hydraulic transducer (10 ms); level: none; RTDs 5 / 3 / 20 s; ECS pressure 50 ms | A-W2.2-16 |
| Rate gyros, accelerometers | body vector on the installed axis (NZ reads −f_z) | 2nd order (50 / 100 Hz) | Kala JOAST 2015 (DIRECT ranges); A-W1.6-15 |
| Fuel gauge (per tank) | PROXY: attitude term, unwetting under specific-force tilt, 2 % dead zone | 1st order 6 s | MIL-G-7940C, AFWAL-TR-80-2058 (TRANSFER); zoom-climb warning (DIRECT); A-W1.6-17 |
| Wheel speed, DC bus voltage | linear | none | |
| AB UV flame detector (ENG.AB_LIT, W2.2) | PROXY: 1 when `eng.ab_state` ≥ level (lit), else 0 | 1st order τ = 50 ms, then the FADEC input comparator (trip 0.5): a 0/1 discrete | CR-191195 §3.3.9 (TRANSFER: single UV detector); A-W2.2-15 |

Then `s_inst = s_dyn (harness: average over non-open probes) + b_install` → meter update hold → fault mode
(→ input comparator for a discrete class, so faults act on the detector signal).
First-order lags: exact first-order-hold solution. Second-order: trapezoidal rule on `n_sub` = 8 sub-steps.
Every element starts in steady state at its first truth frame (A-W1.6-2).

## Assumptions and PROXY items

A-W1.6-1 … A-W1.6-20 in `docs/assumptions.md` (W1.6 section). PROXY: A-W1.6-12 (position error is a Mach-only
table) and A-W1.6-17 (fuel gauge without tank geometry); W2.2 adds PROXY A-W2.2-15 (UV flame detector: a
deterministic first-order response + comparator). Each has a test that exposes its limit
(`tests/integration/test_w22_ab_lit.py::test_detection_delay_is_deterministic_proxy` for A-W2.2-15).

## Validation (acceptance → tests)

| Criterion | Tests |
|---|---|
| A1 τ laws (AGARD W^-0.5, pneumatic ×4.29 at 40 kft), vane 2nd order f_n ∝ EAS, class behaviours | `tests/unit/test_sensors_dynamics.py`, `tests/unit/test_sensors_physics.py` |
| Sensor-fault modes, CRN of fault draws | `tests/unit/test_sensors_faults.py` |
| A8 kernel = NumPy reference bitwise, block = steps, complex step vs central FD | `test_sensors_dynamics.py::test_compiled_equals_reference_bitwise_and_block_equals_steps`, `::test_complex_step_matches_central_difference` |
| Snapshot round trip, CRN across a fault fork | `tests/fork/test_acquisition_fork.py` |
| Configuration vs dictionary and catalogue | `tests/unit/test_sensors_config.py`, `tests/integration/test_sensors_ports.py` |

## Known limitations

- **Not modelled (no truth port or no public form):** FCS.HEATER_I.*, AD.DPA/DPB (side-probe flow-angle
  pressures: pressure coefficients not public), the ECS channels without an M09 point (ACM turbine inlet, supply
  duct, TCV, switches, LSS), brake pedals and antiskid flags, the reservoir LOW switches, battery/generator/TRU
  electrical, ENG.VIB.* (M14 vibration features), SPS.*. (W2.2 phase B added ENG.FUEL_INLET_T, BRK.PRESS, the
  reservoir level transmitters and the ECS points; NAV.RADALT is the avionics radar altimeter's.) LRU-computed channels (`.V` voted words, ADC air data, INS, AHRS, gauged totals) are computed
  by their LRU's module and recorded by M13's computed-channel path.
- Vane damping is constant (evidence: falls with altitude); no vane buzz, blanking or shock fluctuation terms.
- Accelerometers sit at the CG (no lever arm; needs ω̇ from M06).
- The T5 probes see one T5 (no circumferential profile; parameter `pattern` exists, value 0).
- Oil-pressure damping does not lengthen with cold oil (evidence ≈1 → 4 s).
- Index maps of `fcs.surf_pos` slats, `util.fuel_mass` tanks and `util.bus_v` buses are the producers'
  published maps: the input sizes come from M09's `layout.TANKS`/`BUSES` (`config.producer_dims`; `util.bus_v`
  is (4,): DC main, DC essential, DC emergency, AC main, of which the three ELEC.DCBUS.V channels read 0-2,
  E1-MF U1), and `tests/integration/test_index_map_ties.py` ties every indexed channel to the producer's
  names (E1-MF U5). The spanwise slat order behind M05's names remains A-W1.6-16.
