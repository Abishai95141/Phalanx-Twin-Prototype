# `phalanx.sensors.avionics` — M12 avionics sensor-system extension (AD-51)

One 240 Hz module, `AvionicsSystem`, owns the computed avionics outputs that the AD-42 inventory left without
a producer: INS/GPS, standby AHRS, the ADC computation, the radar altimeter and the SMS station status, plus
the electrical supply path from `util.bus_v` to each of them. Fidelity is "just enough" (P3): each output is
truth seen through a **structured error state** whose structure comes from the evidence, never
"ideal + Gaussian noise". Every number lives in `configs/tejas/params/M12_AVIONICS.yaml` with an evidence tag
(TRANSFER or ASSUMPTION), a sweep and an assumption id; the ADC's nominal correction tables are the M12
parameter sets of the probes it reads (`static_pressure`, `vane_aoa`, `vane_aoss`, `tat_probe`).

```python
from phalanx.sensors.avionics.config import build_avionics_config
from phalanx.sensors.avionics.module import AvionicsSystem

avio = AvionicsSystem("avio", build_avionics_config(), dictionary)  # ports: phalanx.sensors.avionics.ports
```

## Ports

| Direction | Ports | Notes |
|---|---|---|
| in (truth) | `af.pos_geo`, `af.vel_ned`, `af.quat`, `af.omega_body`, `af.f_spec_body`, `af.hag`, `af.wow`, `af.mach`, `af.tas`, `af.alpha`, `af.beta`, `af.qbar`, `env.p_s`, `env.t_s`, `util.bus_v`, `util.probe_heat`, `pilot.gear_cmd` | catalogue signals (`input_bindings()`) |
| in (lanes) | `lane.AD.{PS,PT,AOA_VANE_L,AOA_VANE_R,AOSS_VANE}.{A..D}`, `lane.AD.TAT` | M13 DFCC/ADC in-loop lanes on the DFCC acquisition clock (sample buffers) |
| out | `rec_<channel>` for 54 dictionary channels (`ports.RECORDED`) | SI for numeric channels, int words for status/discrete channels; M13 records them as `external=` channels |
| out | `tru_<channel>` for the 37 numeric channels (`ports.TRUTH`) | restricted truth companions (CIR `truth_value` only) |
| out | `radalt_ssm`, `powered_{ingps,ahrs,radalt,sms}` | ARINC-429 SSM of NAV.RADALT; LRU power (phase B: RT silence on the bus) |
| out | `p0_from_hp` (Pa) | The FADEC's P0 altitude signal (W2.2): the standard-atmosphere static pressure at the ADC's pressure altitude AD.HP (= its corrected static pressure; `adc.static_pressure_at`). M08 binds `p0` to it (the F404 ECU's P0 input is an altitude signal, NASA CR-179568 Fig. 3, TRANSFER) |

Events in (proposed catalogue additions, `ports.EVENTS_IN_PROPOSED`): `avio.sms_load {stations}`,
`avio.sms_release {station, mode}`.

## Models (assumption rows in `docs/assumptions.md`, W2.2 section)

| Subsystem | Structure | Rows |
|---|---|---|
| Supply | each LRU on one M09 bus; below `v_dropout` (16 V) longer than the 50 ms hold-up it drops out; in flight the INS/GPS solution then **freezes with unchanged status words** (navigation invalid without a flag, report l.741); on the ground a power cycle re-aligns (ALIGN, flagged) | A-W2.2-1 |
| INS/GPS | psi-angle error state: IMU turn-on biases per power-on, Gauss-Markov in-run biases, ARW / accelerometer white noise; `-psi x f` specific-force coupling and Schuler loop; loosely coupled GPS aiding (position and Doppler-velocity loops toward Gauss-Markov GPS errors, tilt to its accelerometer-bias equilibrium, heading only under horizontal specific force); unaided: free horizontal channels and a baro-inertial vertical loop on the pressure altitude of `env.p_s`; gyrocompass alignment errors; TM-110216 output filters; FOM from the INS's own error estimate | A-W2.2-2, -3, -4 |
| AHRS | MEMS strapdown psi-angle error, erection toward the accelerometer vertical (cut out above 0.1 g or 3 deg/s: the classic turn error below the cut-outs), magnetic slaving with a one-cycle deviation, magnetic output | A-W2.2-5 |
| ADC | mid-value vote of the digitised quad lanes, lane monitors (AD.VALID bits), static-source position-error correction at the indicated Mach, isentropic / Rayleigh Mach, ICAO pressure altitude, CAS, TAS, qbar, SAT from TAT with recovery and heater-error correction (heater flag `util.probe_heat`), AoA / beta from the corrected vanes, HDOT filter; undercarriage term **PROXY** at the ADC stage | A-W2.2-6, -7, -10 |
| Radar altimeter | beam geometry (nearest return inside the half-angle), loss of track beyond 60 deg tilt or 5,000 ft (NCD, value held), per-unit scale and zero errors keyed by serial, terrain/vegetation height as a spatial Gauss-Markov process indexed by along-track cell, tracker lag | A-W2.2-8 |
| SMS | event-driven station content codes and RELEASED word; hung store with `p_hung` per release command; jettison always empties; unpowered SMS ignores commands | A-W2.2-9 |

Determinism (RULES.md rule 5): every kernel is `@njit` (fastmath off) over flat explicit state; the NumPy
reference is the kernel's `py_func`; `step` is `step_block` with L = 1. Draws come from identity-keyed streams
(`module.STREAMS`): INS/AHRS ticks indexed by tick, turn-on errors by power-on count and unit serial, radar
altimeter installation errors by (scenario, serial), terrain by along-track cell, hung stores by release
command count. Forks therefore share their exogenous future (CRN), and the radar altimeter's terrain belongs
to the place flown over.

## Validation (tests and what they establish)

| Test file | Criteria |
|---|---|
| `tests/unit/test_w22_avionics_power.py` | hold-up boundary (11 vs 12 frames), in-flight freeze without a flag, ground re-alignment with fresh draws, bus allocation, `v_dropout` sweep wiring |
| `tests/unit/test_w22_avionics_ins.py` | aided errors = the loops' analytic steady state (n = 48 sorties, 30 %), 1 h free-inertial drift inside 1 nm/h (n = 16), baro-held vertical, heading observable only in turns (CRN fork), correlated error states (no white noise), TM-110216 filter lag (5 %), FOM bins |
| `tests/unit/test_w22_avionics_ahrs.py` | erection equilibrium from the unit's biases, turn error below / above the cut-outs (CRN), slaving and declination |
| `tests/unit/test_w22_avionics_radalt.py` | beam geometry with installation errors, NCD hold, terrain by place, serial-keyed installation errors |
| `tests/unit/test_w22_avionics_sms.py` | load / release / jettison / hung, hung fraction (n = 400), CRN by command count, unpowered, refusals |
| `tests/integration/test_w22_avionics_adc.py` | truth -> M12 -> M13 -> ADC: corrections remove most raw probe errors, HDOT in a climb, PROXY exposers (gear term absent from the lanes; DPA/DPB bits constant), lane monitor and vote, heater state through probe and correction together, compiled == reference == step mode |
| `tests/unit/test_w22_avionics_determinism.py` | compiled == reference, step == block, partition invariance, snapshot / restore at two cuts, CRN forks and identity separation, scheduler purity check |
| `tests/integration/test_w22_avionics_ports.py`, the E1-MF gate (`test_interface_conformance.py`, "M12A") | gate bindings close (exact unit, dtype, shape, clock), RECORDED rules, single owner, recording path and its named gaps |

Fixture: `tests/integration/test_w22_avionics_fixture.py` (kinematically consistent flight scripts, the chain
builder; test-only).

## Known limitations and open items

- **PROXY A-W2.2-7**: the undercarriage air-data term is applied at the ADC stage; the M12 probes and vanes (and
  so the DFCC's own lanes) do not see it. Replacement: a gear term in the M12 static-source / vane physics after
  W2.1a, and an `af.gear_pos` port from M06 (today the gear position ramps from `pilot.gear_cmd`).
- **PROXY A-W2.2-10**: AD.DPA / AD.DPB are not simulated; their AD.VALID bits always read valid.
- Since W2.2 phase B M12's TAT probe reads its heater state from `util.probe_heat`, the flag the ADC corrects
  with; a failed heater with the flag on (the M11 heater-fault mode) is not modelled yet (G-PROBE-HEAT).
- Recording path: since W2.2 phase B M13 has clock sets for the INGPS, AHRS and RADALT domains and a word path
  for the status words, so every avionics channel is recorded.
- The phase-A NAV.RADALT conflict (dictionary `signal: analog` vs AD-51) is closed by dictionary 0.1.3
  (`signal: computed`, R-AD51-COMPUTED).
- No GPS-denial input: the INS is aided whenever powered and not re-acquiring; transport-rate and Earth-rate
  cross-coupling terms are omitted (A-W2.2-2). No complex-step derivative path is implemented for these kernels.
- Performance: about 10 us per 240 Hz frame for the whole module (compiled, block 2,400, build machine), plus
  a one-off Numba compilation (cached).
