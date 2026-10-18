# `phalanx.engine`: M07 F404-GE-IN20 engine truth model (W1.3a, W2.1b)

A stochastic state-space engine: a 0-D component-level model (two-spool mixed-flow afterburning turbofan) with
inter-component volume dynamics, rotor, actuator, heat-soak, tip-clearance and oil states, and discrete
afterburner, flame and surge processes. It runs at 240 Hz in closed loop with M08 (FADEC) and is driven by
the M03 process disturbances `env.w_engine` (AD-04, AD-31, AD-32, AD-46). Disturbances enter the dynamics,
never an output.

Binding sources: `docs/architecture.md` §6 M07, §7, §14, AD-09, AD-22, AD-32, AD-34, AD-43, AD-46;
`docs/build_briefs/W1.3a_engine.md`; `configs/interfaces/w1_ports.yaml`; evidence in
`research_notes/Virtual fighter telemetry layer research/f404_in20_engine_model.md` (Q1 closure, Q6
dynamics, Q11 maps, Q12 golden targets C1-C28) and `iaf_usage_and_validation_gap_closure.md` Q3 (released
idle/MIL test-cell anchors).

## Files

| File | Contents |
|---|---|
| `layout.py` | index constants: states `X_NAMES` (16), timers, int state, inputs `U_NAMES`, outputs `Y_NAMES`, aux, parameters `P_NAMES` |
| `thermo.py` | NASA-9 humid air + combustion products (McBride 2002 via pyCycle), `h(T)`, `phi(T)`, inversions (`NEWTON_T` = 2), compress/expand |
| `maps.py` | scaled pyCycle maps (AXI5 fan, HBTF HPC/HPT/LPT): compressor PR-inversion lookup, turbine lookup, unchoke factor |
| `kernel.py` | `@njit` kernel: `deriv`, `pressure_error`, `_tick` (Heun, stiffness-based sub-step count, refinement, discrete processes), `engine_kernel`, `deriv_point` |
| `design.py` | design-point closure to the IN20 ratings, derived parameters, `EngineModel`, `build_engine_model` |
| `steady.py` | equilibrium solver, `operating_line`, `vg_reference`, `linearize` (complex step) |
| `sim.py` | transient-window simulation: `EngineState`, `state_from_x`, `input_block`, `simulate` |
| `module.py` | `EngineModule` (core module, 240 Hz, `step == step_block` bitwise, keyed AB light-off draws, `eng.fault_inject` handler) |
| `faults.py` | engine fault modes (M11 `eng.fault_inject`, AD-48.4) as state perturbations: per-mode sizes `fm` -> the fault slice of the float state (`layout.FLT_NAMES`) |
| `ports.py` | `PREFIX = "eng"`, `ports(n_engines)` (inputs, outputs, catalogue bindings) |
| `corrected.py` | theta/delta corrected-parameter conventions |
| `ident.py` | AD-34 hooks: `transient_weights`, `residuals`, `jacobian_cs` |
| `_mapgen.py` | dev-time converter of pyCycle map/thermo source text to CSV (parsed with `ast`, never executed) |

Parameters: `configs/tejas/params/M07.yaml` (every value tagged; ASSUMPTION/PROXY values have `sweep` and
`assumption_id`), tables in `configs/tejas/params/M07/*.csv` (pyCycle-derived, Apache-2.0: see `NOTICE` there).

## API

```python
model = build_engine_model(ps=None, *, n_sub=None)            # EngineModel (p vector read-only; with_p(**kw))
ss = steady_state(model, u, *, x0=None, ab_state=0, flame=1, target=None)   # target=(state|diagnostic, value)
tr = trim(model, TrimCondition(t_s, p_s, mach, ...), target, *, a8=None, vg=None, x0=None)  # W2.1 F1
tr = EngineModule(...).trim(condition, target, a8=..., vg=...); EngineModule.from_trim(tr)   # start there
A, B, C, D, xn, un, yn = linearize(model, ss)                  # continuous-time, about an equilibrium
r = simulate(model, state_from_x(model, ss.x, n_engines=E), *input_block(L, E, ss.u, wf_cmd=...),
             z_ab=None, record_aux=False)                       # WindowResult(state, y, yi, aux)
res = residuals(model, names, theta, state0, u, ui, y_meas, channels, scales, weights=None)
J = jacobian_cs(model, names, theta, state0, u, ui, y_meas, channels, scales, weights=None)
EngineModule("eng", model, n_engines=1, serials=None)          # core module for System
```

**Trim at a condition (W2.1 F1).** `steady.trim` / `EngineModule.trim(condition, target)` returns a consistent
`(x, u)`: the equilibrium of the kernel at a `TrimCondition` (ambient, Mach, disturbances, bleed, PTO, fuel
temperature, health) with the fuel freed to meet a target. A target names a state (`"n1"`, `"n2"`, rad/s) or a
diagnostic (`layout.AUX_NAMES`: `"n2c"` = N2/sqrt(theta25) in rpm, `"ps3"`, `"t5"`, ...). A direct Newton solve is
tried first; a far condition falls back to a continuation path from the design point (exact either way;
`converged` must be checked). `from_trim` builds a module that starts there. The FADEC-consistent trim at a PLA
(post-start idle, AD-46) is `phalanx.fadec.trim.operating_point`, which uses this API.

Input semantics (see `ports.py`):
- `w_engine` (e, 5) = [fuel_metering, combustor_eff, inlet_recovery, shaft_load, fan_face].
  - `shaft_load` multiplies the HPC + accessory torque (1 % is about 200 kW at MIL).
  - `fan_face` lowers the fan flow capacity and efficiency: the LP-specific path (AD-46).
- `pto_power` < 0 is the starter drive. It is converted as T = P / (N2 + 1 rad/s), the M09 convention.
- `fuel_inlet_t` (from M09) is the oil-cooler sink.

Speeds: 100 % N1 = 13,270 rpm and 100 % N2 = 16,810 rpm are the percent references. The design MIL point
runs at 100 % N1 and 95.2 % N2 (`n2_mil_frac`, AD-46).

**Faults (W2.1b, AD-48.4, A-W2.1b-4).** `EngineModule.on_event` handles `eng.fault_inject` (payload `tail, mode,
param, instance, engine, clear`; declared in `ports.EVENTS_IN`). Each catalogue engine mode (`faults.MODES`, 17,
incl. `bleed_schedule_bias`, which M08 cannot realise) changes the state only: persistent modes set their size in
`fm` and the effective perturbation slice (vibration-source increments, extra spool loads, stall-margin debits,
a fuel cap, extra bleed, start faults below 60 % N2, a nozzle leak, an oil leak with pressure loss and bearing
load, lube-cooling loss, AB no-light) that `deriv`/`_tick` read; one-shot modes (flameout, pop/quick-fill stall,
AB blowout) act at onset. Magnitudes are the M07.yaml `faults` set (ASSUMPTION, sweeps). Healthy runs are
bitwise unchanged (zero slice, full oil charge). Tests: `tests/integration/test_engine_faults.py`.

## Numerics

- **Sub-steps.** Each 240 Hz tick holds inputs constant and integrates Heun sub-steps. The count is
  max(`n_sub` = 2, ceil(dt · lam_est / 1.4)), where lam_est is the kernel's stiffness estimate for the
  volume modes. That gives 3 sub-steps at MIL and 2 at part power. Plain `n_sub` 2 is unstable at MIL.
- **Refinement.** A tick whose Heun-minus-Euler pressure error exceeds 1e-3 is recomputed with twice the
  sub-steps, up to 64. This resolves surge collapse and mixer-flow stiffness.
- **Inversions.** T(h) and T(phi) are inverted with 2 Newton iterations.
- **Accuracy.** Max relative output error against 32 sub-steps is 5.5e-5 on the reference part-power
  fuel step (bound 1.3e-4).
- **Cost.** About 10–13 µs per tick per engine.
- **Determinism.** Every decision is state-based and uses real parts only. Kernel and NumPy reference agree
  bitwise. Complex-step derivatives agree with central differences. Snapshot/restore and per-step ==
  per-block are bitwise.
- **Knife edges.** Sub-step-count changes and event instants (surge trigger, AB light-off, lean blow-out)
  are discrete. Finite differences and complex step are not valid across them, which W2.3 must keep in
  mind.

## Assumptions and PROXYs

`docs/assumptions.md` A-W1.3a-1 ... A-W1.3a-20. The ones that matter most:

- **Cycle closure** (A-W1.3a-1). Only 84 kN, 70 kg/s and OPR 28 are DIRECT.
  - Dry SLS thrust is 58.7 kN against about 54 kN (C2), and MIL fuel is 10,570 lb/h against
    8,300–8,600 lb/h. The fan-to-nozzle losses look optimistic.
- **MIL at 95.2 % N2** (A-W1.3a-20, AD-46).
- **Map shapes** (A-W1.3a-2). Generic pyCycle maps, piecewise linear in speed, so linearisations are valid
  per map cell.
  - Part power does not match the released idle anchors. At 65.2 % N2: N1 35.9 % (38.9), Wf 457 lb/h
    (650–750), T5 556 K (682), thrust 0.97 kN (2.8). This is W2.3 work with map modifiers.
- **Structural PROXY: sub-idle regime** (A-W1.3a-3). A start from rest hangs at 61 % N2 with a 1,500 K T5
  peak (C20). Sortie telemetry therefore starts from post-start idle (AD-46).
- **Structural PROXY: surge** (A-W1.3a-9). An event model with no post-stall dynamics; the CDP collapse is
  too shallow (C23).
- **PROXY: vibration source** (A-W1.3a-14). Band split assumed.
- **Process-disturbance semantics** (A-W1.3a-15).
  - `k_eta_fan_face` = 0.2. Near 0.4–0.6 the fan flow and efficiency effects on N1 cancel.
  - The real fast-band N1–N2 correlation of 0.47 is reachable under the fixture governor only for
    `k_eta_fan_face` up to about 0.3. If W2.4a identifies a larger value, AD-46 needs a second
    LP-specific path, for example an LP-shaft torque term.
- **VG model** (A-W1.3a-12). VG maps are defined on a reference schedule; M08 must schedule the same
  reference (`steady.vg_reference`) for nominal operation.

## Validation (acceptance)

| Item | Tests |
|---|---|
| A1 ratings, energy balance | `tests/unit/test_engine_design.py`; `tests/golden/test_engine_golden.py::test_c1_in20_ratings`, `::test_c1_kernel_reproduces_ratings` |
| A2 corrected-parameter invariance | `tests/integration/test_engine_corrected.py` |
| A3 equilibrium | `tests/integration/test_engine_dynamics.py::test_steady_state_is_dynamic_equilibrium` (+ negative control) |
| A4 signs, Muir directions, determinism, cross-engine independence | `tests/integration/test_engine_signs.py`; per-channel disturbance signs in `test_engine_mutation_guards.py` |
| A5 transients | `tests/integration/test_engine_transients.py` |
| A6 / AD-46 stochastic structure | `tests/statistical/test_engine_stochastic_structure.py` (B1 4-Hz estimator: 0.47 inside the achievable N1–N2 range; negative controls) |
| A7 bitwise, complex step, snapshot, keyed RNG | `tests/integration/test_engine_dynamics.py`, `tests/integration/test_engine_module.py` |
| A8 C1–C28 + released anchors | `tests/golden/test_engine_golden.py` (strict xfails name the measured gap) |
| A9 µs/step | `tests/integration/test_engine_perf.py` (slow) |
| Wiring guards (review mutants) | `tests/integration/test_engine_mutation_guards.py` |
| ASSUMPTION sweeps | `tests/integration/test_engine_sweeps.py`, `tests/unit/test_engine_design.py::test_design_sweep_stays_closed` |
| Identification hooks | `tests/integration/test_engine_ident.py` |

Closed-loop tests use the labelled TEST FIXTURE governor, schedules and disturbances in
`tests/integration/test_engine_fixtures.py`. The real FADEC (M08) and disturbance model (M03) are wired in
W2.1.

## Limitations (for W2.1 / W2.3 / W2.4a)

- **Calibration-pending (W2.3):**
  - C2–C6, C10, C11, C17, C18, C22, C26 magnitudes and the -400 method check;
  - the idle anchors and the MIL fuel-flow anchor.
- **Need M08 or M06 in the loop:** C5, C7, C9, C10, C12, C13 and C17.
- **Structural PROXY limits (model changes, not calibration):** C20/C21 (sub-idle) and C23 (post-stall).
- **Deferred to W2:**
  - The I_LP conflict: C18 wants more LP inertia, C22 wants less.
  - The FF correlation sign: resolved on the M08 side in W2.1b (harmonised schedules, Kp 1.5; positive below the
    N1-limited region).
- **Surge PROXY at fixed fuel (W2.1b finding):** repeated surges with the fuel held (open loop, e.g. a bearing
  failure at MIL with nothing cutting fuel) over-speed the core (N2 about 125 % in 4 s): the PROXY collapse
  removes compressor work while the turbine keeps its fuel. In closed loop M08's N2-max and stall logic cut fuel;
  the post-stall model is a W2.3 item (C23).
- **Installation:** an uninstalled inlet (A-W1.3a-18) and a fully expanded nozzle without an A9/A8 schedule
  (A-W1.3a-19).
- **Proxy topology (AD-43):** the `separate_fixed` topology option for the DASHlink proxy is W2.4a. It reuses
  these components with proxy `n_engines = 4`.
