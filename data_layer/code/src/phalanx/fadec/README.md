# `phalanx.fadec`: M08 FADEC, closed-loop governing and engine signal validation (W1.3b, W2.1b)

This package is the engine controller of the virtual Tejas (F404-GE-IN20 class). It covers:
- signal validation of the digitised FADEC lanes;
- a MIN/MAX fuel control law in ratio units;
- nozzle (A8) and variable-geometry scheduling;
- the afterburner sequence;
- start, flameout and relight logic, including DEEC-style sub-idle governing;
- the protection monitors.

Everything is vectorised over `n_engines`. The controller runs on its own clock domain (60 Hz) and closes the
loop with the engine (M07) through its catalogue ports only.

Binding sources: architecture §6 M08, §8, §14, AD-22, AD-31 as refined by **AD-50**, AD-39, AD-42, AD-44; the
W1.3b brief; `W1_interfaces.md`; `docs/behavioural_targets.md`; report §3, §9; f404 notes Q3-Q9;
texture_and_fault_gap_closure Q6.

Every number is in `configs/tejas/params/M08.yaml` (+ `M08/*.csv`) with an evidence tag. Assumptions are
A-W1.3b-1 ... A-W1.3b-18 and A-W2.1b-1 ... A-W2.1b-6 in `docs/assumptions.md`. **All code tables and fault codes are SYNTHETIC** (AD-19);
they are not the real IN20 FADEC's.

## Interfaces

```python
from phalanx.fadec import Fadec, FadecConfig, load_fadec_params, PREFIX  # PREFIX = "fadec"
from phalanx.fadec.ports import (
    DEFAULT_CLOCK,
    RECORDED,
    RECORDED_MISSING,
    LANE_PORTS,
    fadec_clock,
    lane_shape,
    ports,
)
from phalanx.fadec.coupling import fadec_input_connections, command_connections, lane_frames, lane_port_name
from phalanx.fadec.kernel import fadec_block  # compiled pure kernel (fused W2.1 groups)
from phalanx.fadec.reference import kernel_reference  # same source, NumPy (identity decorator)

ins, outs, bindings = ports(n_engines=1, autothrottle=False, clock=DEFAULT_CLOCK)
m08 = Fadec("fadec", load_fadec_params(), n_engines=1, initial_wf=..., initial_a8=..., event_target="m14")
```

**Clock** (AD-42). `DEFAULT_CLOCK = acquisition_clock("FADEC", 60)` from M13 (60 Hz, +50 ppm, 3.1 ms phase).
M08, its lanes and M15 share one oscillator. At truth step k, M08 runs the frames whose instants fall in
[t_{k-1}, t_k); commands apply from t_k.

**Outputs** (catalogue, rate = FADEC clock, held):

| Port | Content |
|---|---|
| `wf_cmd`, `wf_ab_cmd` | kg/s |
| `a8_cmd` | m² |
| `vg_cmd` | rad (FVG, CVG) |
| `ignition` | bit 0 main, bit 1 AB igniter |
| `ab_enable` | AB enable |
| `active_limiter` | fuel regulator code 0-11, + 16 if the nozzle T5 loop is active (`codes.decode_active_limiter`; 11 = START_N2DOT, the sub-idle start/relight governor) |
| `validation_state` | [e, ns]: 0 OK, 1 SUSPECT, 2 FAILED/held, 3 SUBSTITUTED; sensors N1, N2, T1, T25, PS3, T5 |

**RECORDED** (AD-42; M13 recorder `external=`). Layouts are in `codes.recorded_words` (A-W1.3b-16).

| Port | Channel |
|---|---|
| `n1_v`, `n2_v`, `t1_v`, `ps3_v` | ENG.N1.V, ENG.N2.V, ENG.T1.V, ENG.PS3.V (SI validated selections) |
| `t5_avg` | ENG.T5 (harness average) |
| `ign_word` | ENG.IGN |
| `flameout_word` | ENG.FLAMEOUT |
| `limit_flags` | ENG.LIMIT_FLAGS |
| `status_word` | ENG.FADEC_STATUS |
| `fault_code` | ENG.FAULT_CODES (EU value k·1000 + NNN, A-W1.7-6) |

**Not produced yet:** ENG.PLA.V and ENG.A8.V (`RECORDED_MISSING`). M08 governs on `pilot.pla` and commands A8 open
loop; it does not read the PLA resolver or nozzle LVDT lanes.

**Inputs:**
- `pla` ← `pilot.pla` [rad].
- `p0` ← `avio.p0_from_hp` on Tejas (W2.2): the F404 ECU's P0 input is an altitude signal (NASA CR-179568
  Fig. 3) [TRANSFER: F404-400], so P0 is the standard-atmosphere pressure at the avionics ADC's pressure altitude
  AD.HP, i.e. its position-error-corrected static pressure (A-W1.3b-11 PROXY retired for Tejas). Proxy mode (A/T) keeps the replayed
  `env.p_s` (no aircraft air data in the DASHlink chain); `Fadec(p0_source=ports.P0_ENV)` selects it in TEST
  FIXTURE loops without the avionics module. The ADC output is held until its first computation, so an
  integrated run initialises the ADC (trim) before M08's first frame.
- Proxy mode adds `at_engage` and `at_n1_cmd`.
- Lanes bound `lane.<channel_id>`: ENG.N1.A/B, N2.A/B, T1.A/B, T25, PS3.A/B, T5.HARNESS_A/B, AB_LIT. They carry SI
  values of the digitised readings, as sample buffers of shape `(capacity,)` (one engine; identical to M13's
  `lane_<id>` ports) or `(capacity, n_engines)`.
- ENG.AB_LIT is the M12 UV flame detector's M13 lane (W2.2; PROXY A-W2.2-15): 1 about 35 ms after M07's
  afterburner flame is established (not during lighting), 0 about 35 ms after it goes out.

**Events** (`event_target` set). `fadec.fault` and `fadec.caution` fire on every fault-bit set or clear, with
payload `{engine, code, set, sensor, lane, description, t_frame_ns, frame}`, stamped at the publishing truth
frame. Both kinds are catalogued in `configs/interfaces/w1_events.yaml` (producer M08, consumer M14) and declared
in `ports.EVENTS_OUT` (AD-44). The catalogued `fadec.fault_inject` (M11 → M08, AD-48) handler is wired in W2.1.

## Coupling contract (A7; `coupling.py`)

`fadec_input_connections(fadec_id, bindings, producers, lane_source_id)` builds the input edges:
- truth inputs are forward edges;
- lanes are **delayed back-edges** (`LANE_EDGE_NOTE`; default lane port names are M13's `lane_port(cid)`).

`command_connections(fadec_id, consumer_id, consumer_bindings)` builds the forward command edges to anything that
binds `fadec.*` (M07, M14).

The lane source must emit, at step k, the frames in [t_k, t_{k+1}) of the shared clock (`lane_frames`). M08
recomputes the same frames at step k+1 (`Fadec.frame_schedule`).

Proven by the tests:
- the scheduler wiring equals the fused fixture loop bitwise, in step and block modes and with compiled and
  reference kernels;
- a structurally different plant is governed by the unmodified module;
- the real M13 lane ports resolve with identical unit, shape and clock;
- M08 runs on the real M12→M13 lanes.

**W2.1 notes.**
1. Fused groups call `fadec_block` from another `@njit` function. Numba's on-disk cache of the caller does not
   track a callee in another file, so a fused caller must use `cache=False`, or be rebuilt when `kernel.py`
   changes. The fixture `_closed_loop` does this.
2. Initialise sensor states at trim. From a cold start, M12's two T1 lanes settle at different rates and give a
   transient T1 cross-channel soft-fail (observed at 0.45-0.72 s in `test_fadec_m13_lanes.py`).
3. ENG.AB_LIT needs an in-loop source (UV flame detector). Done in W2.2 (M12 class `uv_flame_detector` on
   `eng.ab_state`, M13 word path on the FADEC clock).
4. The analytical check needs an M07-derived on-board model before it can be switched on (AD-50).

## W2.1b: harmonised with M07 (entry gates 1-4, F1, faults)

- **Harmonisation (A-W2.1b-1, `harmonise.py`).** The schedules and the on-board-model tables are derived from
  nominal M07 SLS ISA steady sweeps (`harmonise(model)`; committed CSVs = `write_harmonised`; drift test
  `tests/integration/test_fadec_harmonise.py`): VG = M07 `vg_reference`; nozzle floor scaled so its IRP value is
  M07's MIL throat (coincidence anchor: the N1 and T5 limits meet at PLA 84); W1.3b N2c-vs-PLA shape mapped onto
  M07's corrected speeds (ground idle 66.6 % N2 at PLA 18); ratio units and OBM from the same line. The W1.3b
  fixture-matched tables moved to `tests/fadec_fixture_tables/` (TEST FIXTURE, `fadec_fixture.fixture_params`).
- **Trim (F1, `trim.py`).** `operating_point(model, cfg, pla, condition)` returns the M07 equilibrium M08
  holds at that PLA (least-fuel MIN/MAX selection, nozzle T5 loop) and the M08 initial commands
  (`initial_commands`): a run can start at post-start idle or any PLA without a settling transient (AD-46).
- **Gate 1, flameout at altitude (A-W2.1b-3).** The N2-deceleration threshold is fo_n2dot x P0/P_std (floor
  `fo_delta_min`); relight is confirmed by T5 recovery or by N2 back at the governed speed and not falling.
  Detected, relit and cleared from SLS to 40 kft, idle and PLA 60; chops are not flameouts
  (`tests/integration/test_fadec_flameout_m07.py`).
- **Gate 2, FF sign (AD-50).** Governor Kp 1.5. On M07 (n = 3 x 120 s per PLA, shaft-load disturbance):
  r(N1,FF) +0.39…+0.78 and r(N2,FF) +0.12…+0.40 at PLA 60-80, B2 −0.50 s; the sign of r(N2,FF) inverts at
  PLA 82 (the N1 limiter takes fuel under the disturbance) and stays negative in the N1-limited region
  (`tests/integration/test_fadec_m07.py`).
- **Gate 3, T1 below span (A-W2.1b-6).** Both T1 lanes pinned at the −54 °C floor are held valid (`edge_hold`);
  one lane there is still an open circuit. Residual: true N1c 1.049-1.050 at 11 km, PLA 90 (without the hold:
  substitution and a BIT code, N1c also 1.050 now that the on-board model is M07-derived; the re-review's
  1.065 was the fixture-matched model). Dictionary 0.1.3 span widening or air-data T1 removes it.
- **Gate 4, limiter hand-off (A-W2.1b-2).** Clamp-to-selected hand-off past the limit (`limiter_handoff` 27);
  PS3-max and N1 rate anticipation on 1 s-filtered rates (`ps3_lead` 1 s, `n1_lead` 1.5 s); N1 gains 2 / 1.5
  scheduled up on hot days and in thin air. Fixture 192-point grid 0/192 (was 29) with the four E1 cases green;
  M07 grid 0/192; N1 loop gain margin on M07 6.3-16.6 dB over the corners (was −0.9-16.9 dB)
  (`tests/property/test_fadec_limiter_property.py`, `tests/integration/test_fadec_limiters_m07.py`).
- **Unified codes (dictionary 0.1.2).** M08 emits the dictionary `bit_codes` (legacy W1.3b numbers in
  `codes.LEGACY_TO_UNIFIED`; `tests/unit/test_fadec_codes.py`).
- **Faults (`fadec.fault_inject`, AD-48.4, A-W2.1b-5; `faults.py`).** Nozzle-loop gain margin, fuel-schedule
  bias, fuel over-metering and throttle binding as M08 state perturbations (`Fadec.on_event`);
  `bleed_schedule_bias` is realised by M07 and refused here (catalogue retarget proposed)
  (`tests/integration/test_fadec_faults.py`).

## W2.3a item 1: ground-idle acceleration margin (A-W2.3-1, A-W2.3-3)

- **Installed fuel-control lines (A-W2.3-1).** The reference, accel/decel and feed-forward Wf/PS3 lines are
  derived from M07's steady line of the *installed* engine (SLS ISA with `harm_bleed` 0.503 kg/s and `harm_pto`
  21.8 kW, M09's ground values); below idle the reference follows that line down to `harm_line_min_n2c` 0.55,
  where the loaded engine's steady Wf/PS3 *rises* as N2 falls. The no-load line (W2.1b) left 3-20 % accel margin
  at idle and fell under the loaded requirement a few points below idle, so a sag rolled the engine back onto
  WF_MIN (W2.5 D3; the integrated aircraft's ENG-506 take-off run-down). Margin now >= 1/0.88 (the low end of a
  serviceable fuel control, Muir CF-18) from 55 % N2c to idle for every B7 deterioration and the build band, at
  M09's nominal and at the integrated aircraft's measured idle loads (35 kW, 0.54 kg/s).
- **Governor gain schedule (A-W2.3-3).** With the installed line Wf/PS3 falls as N2 rises near ground idle, and
  the ratio-unit loop with AD-57's Kp 1.5 was barely damped there (the TJ213 idle wandered 2.6 % N2 peak to
  peak; a 1 s kick did not decay). The small-signal PI gains are multiplied by `gov_ks` (derived by
  `harmonise.governor_gain_schedule` from the line slope; 1 wherever the line rises, so part power and AD-50's
  FF signs are untouched; x5.4 at ground idle with `gov_ks_margin` 5, the smallest margin whose W2.5 idle step
  overshoots < 23 % for every B7 case). Absent `gov_ks_*` parameters (the proxy sets) mean multiplier 1, bitwise.
- **Integrated aircraft (gate sortie 2, TJ213; `analysis/calibration_w23/results/integrated_takeoff_*.json`).**
  Main b7e0dee: idle N2 wander 5.0 % peak to peak, slammed from 63.7 % N2 it ran down to 45 % in 20 s on
  ACCEL/WF_MIN (ENG-506). Item 1: wander 0.44 %, slam from 66.2 % reaches N1 100 % 12 s after the throttle
  reaches IRP with no N2 dip (regulators ACCEL then N1).
- Tests: `tests/integration/test_fadec_accel_margin.py` (structural margins, W2.5 step recovery and damping,
  idle kick, slam from a sagged idle at the integrated loads, negative controls),
  `tests/integration/test_faults_bench_trim.py` (the W2.5 bench step, formerly a strict xfail),
  `tests/integration/test_fadec_harmonise.py`.

## Model (kernel.py; one FADEC frame per call of `_frame`)

### 1. Signal validation

Each sensor goes through the same template:
- range check over n frames;
- rate check over 4 frames;
- dual-lane cross-check: average when the lanes agree; safer lane on persistent disagreement (soft-fail); the
  other lane when only one is left (SUSPECT);
- analytical check against a FICA-style on-board model (25 % steady / 45 % transient), with substitution (max 3);
- heal after 10 good frames;
- hold, then substitute, when both lanes are lost.

**The analytical check is OFF by default** (`vm_analytic = 0`, AD-50). The on-board model and the ratio-unit
schedules are fixture-matched (A-W1.3b-7).

Accommodation:

| Lost or substituted | Action |
|---|---|
| Speeds | N2 limit −1,000 rpm, AB inhibit |
| T5 | AB inhibit, nozzle to its safe position |
| PS3 | AB inhibit |
| Second like failure | part-power reversion |

Failure modes can be injected (A-W1.3b-12).

### 2. Protection

- Run speed, hung-start arming and the sub-idle mode use **corrected** N2 ≥ 60 %.
- Flameout detection: measured T5 below a span-floored reference, with N2 decelerating through the governed
  demand. Auto-relight and confirmation follow.
- NASA hung-start rule: N2 < 60 % and not rising for 1 s **with PLA 14-24°**, or < 60 % for 35 s while starting.
- Sub-idle: corrected N2 < 60 % for 10 s.
- Stall: a > 40 % single-frame drop of measured PS3, held 3 s.
- T5 over-temperature and overspeed exceedances, on measured values.

### 3. Fuel

Selection is MIN{N2 governor (demand N2/√θ25 on PLA/T25, or the proxy A/T demand), N1 isochronous, N2 max, T5,
PS3 max, accel Wf/PS3}, then MAX{decel Wf/PS3}, then clamps. All of it is in **ratio units** Wf/PS3
(A-W1.3b-2), with Wf = RU × PS3 filtered 0.05 s (A-W1.3b-17).
- The N1 isochronous limiter uses the physical limit vs T1, the 104.4 % corrected cap and a 1.5 s rate lead on
  a 1 s-filtered N1 rate; its gains are scheduled on T1 and P0 (A-W2.1b-2).
- Limiters are PI with integrator feedback (C-MAPSS40k IFB) and an equilibrium clamp; past its limit a limiter
  is clamped to the selected command (bumpless hand-off, `limiter_handoff`); PS3 max has a 1 s rate lead.
- **PS3 min is off by default** (AD-50). When set, it is a floor on the governor branch only, below IRP, under the
  MIN protection limiters.
- **Sub-idle start/relight** (A-W1.3b-18, DEEC-style) applies while starting or relighting below run speed:
  - the governor and the above-idle accel schedule are replaced by an N2-rate governor (2 %/s), active from
    light-off (T5 rise);
  - fuel is trimmed by a 760 °C start T5 limit;
  - the governor output is held before light-off;
  - hand-over to the N2 governor happens at run speed.

### 4. AB

- Request at PLA ≥ 94° with N1 within 3 % of its limit.
- Nozzle pre-open 0.2 s; light-off at 5.5 RU.
- No-light declared 2.5 s after the request (150 frames, exact); 3 retries 2.4 s apart; then lockout.
- Blowout detection.

### 5. Nozzle/VG

- The A8 floor is scheduled on PLA, with pre-open during AB light-off.
- At and above IRP, the T5 loop opens the nozzle to hold T5 = f(T1, P0).
- FVG and CVG are scheduled on corrected speeds.

## Validation (acceptance → tests)

All tests are deterministic. Sample sizes are in each test docstring.

| Acc. | What | Tests |
|---|---|---|
| A1 | Each limiter wins in its regime and holds its variable; bumpless transfers; invariants over PLA/T1/altitude/Mach to the 10 kPa ceiling; PS3-min off by default and bounded when enabled; SLS ground idle in the released band, with throttle authority (fixture and real M07) | `tests/integration/test_fadec_limiters.py`, `test_fadec_closed_loop.py` (IRP bumpless + negative control), `tests/property/test_fadec_limiter_property.py` (n = 40), `tests/integration/test_fadec_m07.py` |
| A2 | Fast-band FF correlation signs (asserted); FF→N2 lag sign; mechanism (zero governor gains); direct law anti-correlated; commanded steps lead; lag table; signs on the real M07 | `tests/integration/test_fadec_closed_loop.py`, `tests/statistical/test_fadec_leadlag.py` (slow), `tests/integration/test_fadec_m07.py` |
| A3 | Pop stall, mechanical-stall timing, AB no-light/retries/lockout (exact frame), flameout relight with sub-idle governing, hung relight, cold-day idle | `tests/integration/test_fadec_cascades.py` |
| A4 | Hung start fires on N2 < 60 % not rising 1 s with PLA 14-24°, and not otherwise | `tests/unit/test_fadec_protection.py` |
| A5 | Validator rules, heal, substitution, accommodation, failure modes; no false analytical failures on a mismatched healthy engine by default | `tests/unit/test_fadec_validator.py`, `tests/integration/test_fadec_obm.py`, `tests/integration/test_fadec_m13_lanes.py` |
| A6 | Compiled == reference bitwise; step_block == step; complex-step-safe gains; snapshot mid-count; IFB clamp semantics | `tests/integration/test_fadec_kernel.py`, `tests/fork/test_fadec_snapshot.py`, `tests/unit/test_fadec_law.py` |
| A7 | Coupling API; real M13 lanes; second plant | `tests/integration/test_fadec_coupling.py`, `test_fadec_m13_lanes.py`, `tests/unit/test_fadec_ports.py` |

### A2 mechanism (AD-50)

The negative small-signal FF→N2 lag comes from the **ratio-unit (Wf/PS3) PS3-proportional metering with weak
small-signal governing**. It does not come from speed-error governing:
- it survives governor gains of zero;
- Kp ≥ 3-5 destroys it (FF becomes anti-correlated);
- a direct-Wf governor is anti-correlated. Its positive peak "lag" is the argmax of a side-lobe of that
  anti-correlation, not a lead.

On the fixture, the 4 Hz B2 of −0.25 s comes from the FF meter: it is 0.00 s with an ideal meter, and truth at
20 Hz is −0.05…−0.15 s. The fast-band correlation sign is therefore asserted alongside the lag.

The default Kp is 1.5 (W2.1b, A-W1.3b-3): with Kp 1 the W1.3a M07 limit-cycled at SLS ground idle (N2 ±2.3 %,
Wf ±15 %); with Kp 2 on the harmonised M07 r(N2,FF) inverts from PLA 75.

### A2 table: TEST FIXTURE

From `test_fadec_leadlag.py`: n = 5 sorties × 180 s, PLA 60, shaft-load AR(1) 1 %, B2 at 4 Hz on an
FF-meter-lagged Wf. Values are medians. Real targets: B2 −0.50 s; A/T −0.375 s vs manual 0.00 s;
r(N1,FF) +0.65, r(N2,FF) +0.67.

| Configuration | B2 (neg/5) | B2, ideal meter | Truth, 20 Hz | r(N1,FF) | r(N2,FF) |
|---|---|---|---|---|---|
| RU law, all governor gains 0 | −0.25 (5/5) | 0.00 | −0.10 | +0.90 | +0.76 |
| RU law, Kp 0.5 / 1 / 2 | −0.25 (5/5) | 0.00 | −0.10 / −0.10 / −0.15 | +0.84 / +0.83 / +0.76 | +0.81 / +0.77 / +0.62 |
| RU law, Kp 3 | −0.25 (5/5) | −0.25 | −0.25 | +0.50 | +0.34 |
| RU law, Kp 5 | +2.00 (side-lobe) | +2.00 | +3.20 | −0.26 | −0.31 |
| RU law, Kp 8 | erratic | — | — | −0.61 | −0.64 |
| Direct-Wf law, Kp 0.5 / 1 / 3 | +1.25…+1.75 (side-lobes) | +1.50…+2.00 | +1.5 | −0.82…−0.90 | −0.30…−0.72 |
| Manual, fixed lever (default Kp 2) | −0.25 (5/5) | 0.00 | −0.15 | +0.76 | +0.62 |
| Manual, lever activity 1.22°/s | +0.25 | +0.25 | +0.15 | −0.06 | +0.56 |
| A/T engaged, default | −0.25 (5/5) | 0.00 | −0.10 | +0.70 | +0.69 |
| A/T engaged, fast | +1.00 | +1.00 | +1.00 | +0.04 | +0.72 |

### A2 on the real W1.3a M07

The scratch run below used the defaults of this fix-back, PLA 60, n = 3 sorties × 180 s, and a lane harness
like the reviewer's. Since W1.3a merged, the signs are also asserted in `tests/integration/test_fadec_m07.py`
(3 sorties × 120 s).

| Case | B2 | B2, ideal meter | r(N1,FF) | r(N2,FF) | Note |
|---|---|---|---|---|---|
| Shaft load | −0.50 | −0.25 | +0.57…+0.63 | +0.24…+0.31 | Positive, but weaker than real |
| Combustor efficiency | −0.25 | — | ≈ +0.84 | ≈ +0.82 | r(N1,N2) 1.00: whole-engine path, AD-46 |
| All governor gains 0 | −0.25 | — | — | +0.55…+0.58 | |
| Direct law | +0.50…+0.75 | — | ≈ −0.84 | ≈ −0.66 | Anti-correlated |

Magnitudes are W2.4a joint identification items.

### A3 timelines (by construction)

The plant side of each cascade is **scripted** in the TEST FIXTURE:
- the stall onset and PS3 collapse;
- the stagnation T5 rise (derived offline to sit between 850 and 871 °C);
- the injected T5 harness failure;
- the AB that never lights.

The sub-idle persistence (10 s) was set from the same F110 trace. What is tested is M08's response: which codes,
when they appear relative to the plant/lane events, in which order, and what is not raised. The timelines do not
independently validate cascade timing.

Mechanical stall, seconds after onset:

| Code | Time (s) |
|---|---|
| Stall | 2.02 |
| T5 lane B over span | 3.15 |
| Over-temperature | 3.37 |
| T5 signal fail (injected) | 9.95 |
| Sub-idle | 14.27 |

The template is 2/4/10/13 s. With the analytical check off by default, there are no N1/PS3/T5 analytical failures.

AB no-light: declared at 2.49, 7.37, 12.25 and 17.14 s, with lockout at 17.14 s. The first is exactly 150 frames
after the request.

### Performance

Apple M4, one core; scratch benchmark of 24,000 steps.

| Path | 1 engine | 2 engines |
|---|---|---|
| Kernel | 0.08 µs/truth-step | 0.17 µs |
| `step_block` | 0.25 µs/step | 0.50 µs/step |
| Per-step `step` | ≈ 175 µs/step (Python call overhead; use `step_block`) | |

## Limitations and open items

- **Fixture plant in the W1.3b tests.** Magnitudes, settling and cascade timings of the W1.3b tests depend on
  the TEST FIXTURE (`tests/fadec_fixture.py`, A-W1.3b-15, with its own fixture-matched tables). The W2.1b tests
  close the loop on the real M07 (`tests/engine_fadec_loop.py`); full W2.1 wiring is W2.1a's.
- **PROXY (A-W2.1b-7): analytical check off by owner decision (deferred post-delivery).** Signal validation is
  range/rate/lane-compare only; in-range drift and common-mode sensor errors pass M08. The on-board model is now
  M07-derived (steady line). With `vm_analytic` on
  (W2.1b scan, PLA 60/85/40/70 steps, 40 s each) there are no false analytical failures at SLS, 315 K or
  30 kft M0.8, but on a 230 K day ENG-046 (T5 analytical fail, model substituted) is raised 14 % of the time:
  at low power the T5 harness reads its span floor while the model predicts the colder truth (the M07
  low-power T5 calibration, W2.3). Replacement route: post-delivery (lagged model terms, after W2.3).
- **Open after W2.1b:** event-mode cost (core block-mode events); an src-level M08 identification hook; the
  nozzle-fault limit cycle runs at about 0.6 Hz (T5-loop lag) vs the F100 catalogue's 1-2 Hz.
- ENG.PLA.V and ENG.A8.V are not produced. P0 comes from the W2.2 air data on Tejas (truth `env.p_s` only in
  proxy mode and TEST FIXTURE loops).
- ENG.AB_LIT has its in-loop lane producer since W2.2 (M12 UV flame detector on `eng.ab_state`, M13 word path;
  the tracked conformance exception is closed). The W2.1b harness still emulates it (lane = 1 when M07's AB is
  lit, no detector delay).
- One control channel is modelled (no channel A/B transfer). The oil-pressure and vibration exceedance bits are
  not M08's.
- The PS3 native step of 0.5 psi in the in-loop lanes flickers fuel unless filtered (A-W1.3b-17).
