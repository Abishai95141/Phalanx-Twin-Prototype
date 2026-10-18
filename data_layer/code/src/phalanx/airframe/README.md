# `phalanx.airframe`: M06 airframe 6-DOF with Tejas-anchored aero (W1.2)

Rigid-body flight dynamics of the Tejas-class aircraft on a rotating WGS-84 Earth, with the AD-08 aero build-up,
a three-leg ground model, wheel brakes, weight-on-wheels and the brake chute. Truth only: every output is the
true state; sensors (M12) and acquisition (M13) turn it into observations.

Binding sources: architecture §6 M06, AD-08, AD-22, AD-42; W1.2 brief; `W1_interfaces.md` §2;
`tejas_airframe_aero_fcs.md` (Q1, Q4, Q8 validation tests V1-V12); NASA/TM-2015-218675 (check cases).

## API

```python
from phalanx.airframe.module import Airframe  # ModuleBase, 240 Hz
from phalanx.airframe.ic import AirframeIC  # initial condition (lat, lon, h, v_ned, q_nb, u_ref,...)
from phalanx.airframe.analysis import Condition, trim, short_period, lateral, make_ic, isa
from phalanx.airframe.build import airframe_param_set, build_config  # registry -> kernel tables
from phalanx.airframe.kernel import airframe_kernel, airframe_outputs, airframe_derivative

af = Airframe.from_registry("af", make_ic(cfg, cond, trim(cfg, cond)), n_engines=1)
```

- `airframe_kernel(f, i, dp, ap, tab, gtab, ttab, u[L, ·], dt, n_eng, mode)` advances L ticks (pure; `step` is
  `step_block` with L = 1). `kernel_reference` is the same source uncompiled; compiled == reference bitwise,
  also with `NUMBA_DISABLE_JIT=1` (tests).
- Analysis tools (`trim`, `short_period`, `lateral`, `time_to_double`) evaluate the **same compiled force
  model**, so V-tests and the M05 gain design are properties of the delivered model.

## Ports (`ports.py`, prefix `af`)

Inputs: `fcs.surf_pos`, `eng.thrust (e,)`, `util.mass/cg/inertia`, `env.rho/a_sound/t_s/wind_ned`,
`env.turb_vel_body/turb_rate_body`, `pilot.gear_cmd`, and (AD-47, W2.1c) `pilot.brake_cmd (2,)` (toe brakes
L/R, 0..1), `util.chute_state` (M09: 0 stowed, 1 streamed, 2 jettisoned, 3 failed; drag only while 1) and
`util.hyd_p (2,)` (the brake system's supply limits the brake torque: cmd x min(`brake_torque_max`,
`brake_torque_gain` x min(`brake_p_max`, p[`brake_hyd_system`])), A-W1.4-32; the three brake values are
M09's, tied by `tests/integration/test_airframe_brakes_chute.py`).

Outputs: `pos_geo` (lat rad, lon rad, ellipsoidal height m), `alt` (ellipsoidal height; geoid ignored,
A-W1.2-2), `vel_ned` (Earth-relative), `quat` (body → NED), `omega_body` (relative to inertial space: what the
gyros see), `f_spec_body` (specific force at the CG: what an accelerometer at the CG sees), `alpha`, `beta`,
`tas`, `mach`, `qbar`, `nz` (= −f_z / g0; 0.9976 at rest at 13° N because of J2 + centrifugal), `wow (3,)`
(nose, left, right), `wheel_speed (2,)`, `brake_energy_rate (2,)`, `hag` (CG height above the local ground
elevation: radar-altitude truth, AD-42).

Events: `af.ground_elevation {h}` (the W1 test hooks `af.brake` / `af.chute` are retired by AD-47), and
`af.fault_inject` (M11, AD-48.4, hidden; `{tail, mode, param, instance, engine, clear, leg}`): a ground-model
state perturbation per gear leg (state `flt_<mode>_<leg>` severities, layout v3): `tyre_burst` (the leg drops
by r_roll - rim_radius, + `mu_rim` rolling, x `grip_rim` lateral and braking friction), `strut_extension_failure`
(`frozen_stroke` compressed, `k_frozen` x stiffer), `gear_collapse_on_touchdown` (belly contact at the leg attach
point, PROXY), `runway_excursion` (+ `mu_soft`, x `grip_soft`); `clear` restores the leg (A-W2.1c-2). Conventions M12 must follow: `util.cg` is relative to the 34 % MAC aero reference
point; the ASA station used by M05 is 1 m ahead of it.

## Model

- **EOM:** ECEF position/velocity, body-to-ECEF quaternion, inertial body rate; J2 gravity + centrifugal +
  Coriolis; Heikkinen geodetic inversion; RK4 with 1 sub-step airborne, 4 within 15 m of the ground.
- **Aero (AD-08):** Polhamus lift (CL0 −0.015, Kp 2.25, Kv 1.54) blended to a flat plate at 33-45°; DATCOM /
  supersonic-linear-theory Mach trends; pitching moment = low-speed Cm(α) table through the NAL anchors +
  Mach static-margin shift (calibrated to the NFTC time-to-double map) + damping + elevon + slat/airbrake/gear
  increments; drag = turbulent flat plate × 7 + wave drag + K(M)·CL'² blended to zero suction at high α;
  lateral-directional from the digitised Tejas Cnβ/Clβ plus TRANSFER derivatives; hinge moments for M05.
- **Ground:** three strut + tyre spring-dampers (cubic stiffness), tanh longitudinal friction, cornering law,
  brakes with a μ_max·N cap (PROXY: no skid), exact first-order wheel spin-up, gear transit 6 s with the WoW
  retraction interlock, keel contact when the gear is not locked.

Parameters: `configs/tejas/params/M06.yaml` + `M06/*.csv`, each with evidence tag and source; assumptions
A-W1.2-1…13 in `docs/assumptions.md` (sweeps in the YAML).

PROXY items: ground effect scales induced drag only (no lift/pitch change); brakes never lock (anti-skid
idealised); no aeroelasticity; geoid undulation ignored.

## Validation

| Test | What it shows |
|---|---|
| `tests/golden/test_airframe_nesc.py` (A1) | NESC check-case family vs independent references (dropped sphere, tumbling brick, rotating WGS-84, drag); step-halving convergence |
| `tests/golden/test_airframe_vtests.py` (A2) | V1 lift curve, V2 trim α at 8 km, V3 low-speed short period (auto slats), V4 time-to-double map, V5 Cm derivatives, V6 directional, V7 ARI trend (strict xfail, W2.3), V9 required thrust physical + performance (strict xfail, needs M07), V10 approach speed, V12 departure tendency; CD0 bands |
| `tests/integration/test_airframe_ground.py` | static equilibrium, braking energy = KE loss, no-skid PROXY limits, gear transit/interlock, chute drag |
| `tests/integration/test_airframe_brakes_chute.py` | AD-47: brake torque limited by the brake system's supply (M09 values tied), pedal scaling and clipping, chute drag only while M09 streams it, M09 deploy-limit failure end to end |
| `tests/unit/test_airframe_aero.py`, `test_airframe_kernel.py` | symmetry, CD > 0, ground-effect PROXY, hinge moments, thrust moment arm |
| `tests/integration/test_airframe_module.py` | step == block, compiled == reference (in process and `NUMBA_DISABLE_JIT=1`), snapshot round-trip, events, 2-engine proxy |

V1, V3, V5 and the V2 trim points are construction checks (the core is fitted to them); V2 at M1.0, V6 shape,
V7 and V9 are the independent checks. Credibility: NASA-STD-7009B Level 2 against proxy data.

## Numba notes (bitwise compiled == interpreted)

- Same-argument `sin`/`cos` pairs go through `geodesy.sin_cos` (cos = sin(π/2 − x)): LLVM fuses `sin`+`cos`
  into `sincos`, which differs from libm in the last bit (424 / 50k arguments on darwin).
- Squares are explicit products: Numba lowers `x**2` to `x*x`, interpreted Python calls `pow`, which is not
  always correctly rounded on darwin libm.
- `cache=True` does not invalidate callers when a callee in another module changes: delete
  `__pycache__/*.nbi|*.nbc` after editing a shared helper.
