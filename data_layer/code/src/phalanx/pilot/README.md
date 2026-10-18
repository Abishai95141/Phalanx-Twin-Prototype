# `phalanx.pilot`: M04 pilot and guidance (W1.1)

Converts the M02 sortie plan into inceptor, throttle and discrete commands (architecture §6 M04): deterministic
guidance tracking the plan targets plus a crossover-type stochastic overlay with per-pilot traits; proxy hooks
for the autothrottle.

## Files

| File | Contents |
|---|---|
| `kernel.py` | the `@njit` pilot kernel (plan lookup, guidance, overlay, inceptor scaling) |
| `module.py` | `PilotModule` (Tejas mode), `PilotReplay` (proxy mode), `load_pilot_config`, `aar_closures` |
| `ports.py` | `PREFIX = "pilot"`, `ports(n_engines=1)` |

## Interfaces

| In | Bound to | | Out | Unit |
|---|---|---|---|---|
| `alt`, `tas`, `mach` | `af.alt`, `af.tas`, `af.mach` | | `stick_pitch`, `stick_roll`, `pedal` | -1..1 |
| `vel_ned`, `quat`, `omega_body` | `af.vel_ned`, `af.quat`, `af.omega_body` | | `pla` (e,) | rad |
| `nz`, `wow` | `af.nz`, `af.wow` | | `gear_cmd`, `airbrake_cmd` | int |
| `n2` (e,) | `eng.n2` | | `ab_select` (e,) | int |
| | | | `brake_cmd` (2,) toe brakes L/R (AD-47) | 0..1 |
| | | | `at_engage`, `at_n1_cmd` (e,) | proxy only (0 in Tejas mode) |

All inputs are previous-frame states (delayed back-edges). `af.quat` is read as **scalar-first**, body -> NED
(interface clarification requested). Events: `scenario.sortie_plan` loads the plan (segment times placed with
the payload's `t_kernel0_ns`). With `utilities=` (M09 id) the plan also schedules the AD-44 utility events
(`ports.py` `EVENTS_OUT`, flat payloads): `util.jfs_start` (each engine start), `util.jfs_abort` (hung start
at the end of the start segment, via the self-event `pilot.start_check`), `util.chute_deploy` /
`util.chute_jettison` (full-stop touchdown / taxi-in, when the plan streams the chute), `util.store_release`
(end of each dive pass of attack missions), `util.fire_extinguish` (after the `pilot.fire_warning` hook);
`initial_events()` returns them for a constructor plan [A-W1.1-46]. Streams: `pilot.remnant` (scenario, tail, sortie; 3 normals per tick, index =
absolute tick), `pilot.aar` (scenario, tail, sortie; one normal per AAR contact).

## Method (assumptions in `configs/tejas/params/M04.yaml`, `docs/assumptions.md` A-W1.1-40..45)

- **Guidance** [A-W1.1-40]: ground logic (start: PLA to ground idle at 20 % N2 [TRANSFER: T-50]; rotation at
  80 m/s to 12 deg); altitude -> vertical speed -> flight-path angle -> load factor with bank compensation and an
  energy guard (climb traded for speed below the target speed); track -> bank -> roll rate; manoeuvring
  primitives command their target Nz (sustained turns at bank acos(1/Nz)); speed -> PLA trim (PI, anti-windup)
  inside the plan's band, which M02 clips to the usage level of the feed-forward PLA so realised and planned
  cycle counts agree; airbrake on overspeed or plan flag.
- **Take-off and climb-out** (W2.1a take-off fix, A-W2.1-9): on the main gear above `v_rotate` the stick is
  the elevon (M05 ground law): the pilot tracks a reference attitude rising at `q_rotate` to `theta_rotate`
  (attitude-and-rate feedback, aft stick at most `stick_rotate`). The take-off segment ends when definitely
  airborne (confirmed lift-off `t_liftoff`, climbing, `h_gear_up` above the field), the landing roll starts at
  a confirmed touchdown (`t_touchdown`); the plan clock shifts by the difference (state `shift`), on live
  transitions only, and each segment change is the event `pilot.segment` (M02's phase and lifecycle source).
  Below `h_safe` above the departure field the energy guard keeps `gamma_min` of climb; the climb-out is wings
  level below `h_turn` and banks at most `bank_departure` below `h_safe`.
- **Manoeuvre primitives** (W2.1a, A-W2.1-10): a turn primitive turns at bank acos(1/Nz) until its heading,
  then flies the flight-path law; a no-turn primitive with a target Nz pulls it as a pull-up (first half of
  the dwell, up to `gamma_pull`) or, for a dive (target altitude below the previous segment's), as the
  pull-out from the pull-out height above the target until level. Airborne path corrections command at least
  `nz_push_min` (0 g).
- **Overlay** [A-W1.1-42/43]: pilot delay 0.1-0.2 s (ring buffer), neuromuscular lag 0.1 s (sticks) and 0.08 s
  (throttle), remnant (first order, 0.5 rad/s corner, per-pilot SD), throttle slew 200 deg/s. The TM-4240 /
  TM-110216 PLA rate limits are engine-model conditioning and are not applied here.
- **Inceptors** [A-W1.1-41]: +7 g / -4.5 g full-scale stick pitch (envelope +8/-3.5 g), 200 deg/s full-scale roll.
- **AAR** [A-W1.1-44]: closure per contact from the pilot's N(mean 2-3.5 kt, SD 0.7 kt), clipped to 10 kt.

## Validation (W1.1 A6/A7 → tests)

| Criterion | Test | Result |
|---|---|---|
| A6 V11 tracking spectra mostly < 0.25 Hz | `tests/statistical/test_pilot_tracking.py::test_v11_tracking_spectra_mostly_below_quarter_hertz` (2 sorties x 600 s) | pooled >= 80 % below 0.25 Hz |
| A6 PLA activity meets the M02 duty gates | `test_pla_activity_matches_the_plan_level_duty` (slow; 3 full sorties: realised counts == plan counts) | see W1.1 report |
| A6 AAR closure 2-3.5 kt, SD ~0.7 | `tests/statistical/test_pilot_aar.py` (20 pilots x 60 contacts) | pass |
| A7 compiled == reference; step == block; snapshot | `tests/integration/test_pilot_module.py` (incl. `NUMBA_DISABLE_JIT` subprocess) | pass |
| A4 CRN | `tests/fork/test_pilot_crn.py` | pass |
| AD-44 utility events | `tests/integration/test_pilot_utility_events.py` (timing on the plan; real M09 accepts them) | pass |

All closed-loop tests run against the **TEST FIXTURE** point-mass plant in
`tests/integration/test_pilot_module.py` (never imported by `src/`).

## Known limitations

- Gains are tuned on the fixture, not on M05/M06; W2.1 must retune (and reconcile the stick gradients with M05's
  command shaping).
- Toe brakes are symmetric (L = R; no differential braking for steering) and follow a phase law, not a
  stopping-distance controller; the drag chute is an event (`util.chute_deploy`).
- FCS events (AD-47, `fcs=`): `fcs.spin_mode` from the kernel's spin flag (checked once a second by
  `pilot.monitor`), `fcs.reset` after the `pilot.fcs_caution` hook (no catalogued FCS-caution input yet)
  [A-W1.1-47]; `tests/integration/test_pilot_fcs_events.py`.
- No restart after a JFS abort, and the fire warning has no catalogued source yet (`pilot.fire_warning` is the
  hook W2 wires); store releases assume a practice-weapon loadout on the outboard and centreline stations.
- No terrain following, formation geometry or tanker kinematics; AAR closure is a speed-command increment.
- `scenario.phase` is not an input: M04 follows the plan it received.
