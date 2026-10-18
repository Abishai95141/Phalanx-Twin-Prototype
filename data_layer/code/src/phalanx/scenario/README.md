# `phalanx.scenario`: M02 scenario, fleet calendar and mission generator (W1.1)

The fleet's operating plan (architecture §6 M02, AD-28): a six-layer hierarchical generator whose fleet
statistics are checked against the report §4 usage gates, the held `scenario.phase` / `scenario.epoch_utc_ns`
ports, the `scenario.sortie_plan` hand-off, usage-mode sortie summaries, the order effects of M21 and the
proxy-mode replay adapter.

## Files

| File | Contents |
|---|---|
| `phases.py` | fine phase-grammar codes; mapping onto the dictionary `flight_phase` table (with proposed fighter codes) |
| `plan.py` | `SortiePlan` (segments, ambient, traits, summary; flat event payload) and `SortieSummary` |
| `usage.py` | usage counting: PLA levels with hysteresis, ASTM E1049 rainflow, Type I/III/IV, TAC, AB lights, IRP/AB time |
| `config.py` | `load_scenario_params()` (M02.yaml + CSV tables), `load_fleet_scenario()` (configs/scenarios), mission and primitive codes |
| `pilots.py` | layer 5: per-pilot latent traits, per-tail affinity, pilot rosters (1.25 per aircraft) |
| `generator.py` | `Planner`: layers 1-6 (`plan_day`, `build_sortie`, `build_ground_run`, `plans_between`), `Overrides` |
| `gates.py` | `fleet_stats`, `PLAN_GATES`, `gate_failures` (R§4 gates; bands A-W1.1-30) |
| `module.py` | `ScenarioModule` (event-only; sortie and fleet modes), `apply_order`, `overrides_from_state` |
| `replay.py` | `ReplayInputs` (FlightRecord-like arrays), `ScenarioReplay` (proxy mode) |
| `streams.py` | stream declarations |
| `ports.py` | `PREFIX = "scenario"`, `ports()` |

## Interfaces

- **Ports:** outputs `epoch_utc_ns` (int64 ns; AD-38: contract time = epoch + kernel t) and `phase` (int64,
  dictionary `flight_phase` code). No inputs.
- **Events emitted:** `scenario.sortie_plan` to the configured `plan_targets` (payload
  `SortiePlan.to_payload(t_kernel0_ns)`, incl. the usage `summary` and the M03 `ambient` vector and
  `duration_s`); self-events `scenario.phase`, `scenario.day`, `scenario.slot`, `scenario.ground_run`.
- **Sortie lifecycle (AD-48.2, W2.1c):** `ops.takeoff` {sortie_id, tail_no, t_takeoff, t_landing (planned),
  ab_lights, engine_starts, landings, dust_index} at the actual take-off (sortie mode: the plan's first
  airborne segment; operations mode: the committed sortie's take-off through the internal
  `scenario.takeoff`, never for a sortie ground-aborted before it) to `takeoff_targets` (M10, M11, M14), and
  `ops.sortie_done` at engine cut-off to `done_targets` (M11, M14; M18 always receives it in operations
  mode). Ground runs never take off. Pure helpers: `generator.airborne_window_ns(plan)`,
  `generator.exposure(params, plan)`. With a **segment source** (`segment_source="pilot"`, the telemetry
  sortie; W2.1a take-off fix, A-W2.1-9) the phase port and the lifecycle follow the flown segments M04 reports
  as `pilot.segment` instead of the plan clock: `ops.takeoff` when the take-off segment is left (the gear-up,
  planned landing = that instant + the planned airborne time), `ops.sortie_done` at the end of the flown
  plan; nothing is pre-scheduled at the sortie start.
- **Power-up (W2.5 / W2.1a, A-W2.1-11):** `ops.power_up` {tail_no, sortie_id, engine_starts, cold_soak} to
  `power_up_targets` (M05 PBIT, M11 preflight start-failure draws, M14 PBIT/CBIT) at the committed sortie's
  engine start (operations mode) or at the telemetry window start (sortie mode; the engine start is just
  before it, AD-46). `cold_soak` = 1 at or below `cold_soak_temperature` (station temperature). M05 then gets
  no `fcs.pbit_start`. A start failure (`ops.start_failure`) before the take-off ground-aborts the sortie and
  closes M11/M14 with an aborted `ops.sortie_done` (operations mode; sortie mode with a segment source).
- **Bootstrap:** the harness injects `ScenarioModule.initial_events()` (core modules cannot self-start).
- **Operations mode (AD-44; `ops=OpsLink(m18, health, kpi)`, fleet mode):** M02 is the scenario side of the
  M18 protocol (`configs/interfaces/w1_events.yaml`; declared in `ports.py` as `MODULE_IDS`, `EVENTS_OUT`,
  `EVENTS_IN`). Out: `ops.offer_request` (each flying day, 00:00 UTC), `ops.launch` (at the sortie's engine
  start), `ops.ground_abort` (an `order.tail_status` grounding, or an `ops.start_failure` from M11, before
  take-off; AD-49), `ops.sortie_done` (engine
  cut-off), `usage.sortie_summary` to M10 (sorties and ground runs: hours, TAC, starts, landings, time at or
  above IRP, peak Nz, AB time, dust/salt exposure indices, chute), `m18.disruption` (scenario
  `supply_disruptions`), `kpi.plan` to the record sink (the day's flying task) and `util.refuel` to M09
  (`utilities=`; AD-49 fill-to-target: the internal and drop-tank target per tank and the station fuel
  temperature at the sortie start; M09 checks capacity at the mixed fuel temperature); at every sortie or ground-run start
  `af.ground_elevation` {tail, h} to M06 (`airframe=`) and `fcs.pbit_start` {tail} to M05 (`fcs=`) (AD-47). In: `ops.offer` (the day is planned on the
  offered tails with the offered restrictions), `ops.launch_denied` (the slot is lost), `ops.assign`
  (ASSIGN_SORTIE: a tail's sortie count and mission type for a date), `ops.restrict` (RESTRICT_USAGE: AB, G,
  NONE, `until_days`), `ops.start_failure` (M11, AD-49: ground-abort before take-off, else counted late). Times sent to M18 are whole seconds. State: `ops_doc` (canonical JSON: pending
  sorties, restrictions, assignments, counters; `read_doc(state)`).
- **Orders consumed:** `order.tail_status`, `order.usage_restriction`, `order.programme_change`,
  `order.tail_swap`, `order.assign_mission` (table in `module.py`); pure form `apply_order(state, kind,
  payload, tails, squadrons)`. Effects apply from the next planning action (day plan or slot build).
- **Streams** (all GENERATOR, owned by M02): `scenario.weather` (scenario, base, date), `scenario.day`
  (scenario, base, date), `scenario.slot` (scenario, sortie = slot key), `scenario.pilot` (scenario,
  serial = pilot id), `scenario.tail` (scenario, tail), `scenario.ground_run` (scenario, tail, date),
  `scenario.usage` (scenario, sortie: chute draw).
- **Python API (usage mode, W1.8 / W2.6):**
  ```python
  p = load_scenario_params()
  env = load_env_config()
  fleet = load_fleet_scenario(Path("configs/scenarios/tejas_two_squadrons.yaml"))
  pl = Planner(p, env, fleet, keys)  # keys: RngService(...).scope(KeyPath.of(scenario=...))
  plans = pl.plans_between(start_date, n_days, Overrides(...))  # SortiePlan list with summaries
  stats = fleet_stats(plans)
  gate_failures(stats)
  ```

## Method and evidence

| Layer | Method | Evidence / tag |
|---|---|---|
| 1 Calendar | Mon-Fri flying (+ surge every day), 3 day waves + night wave on 60 % of days, 6 surge waves; per-slot fly probability = rate / waves (peace 1.5, surge 5 per aircraft-day); IMD-driven weather cancels; daily tail rotation; ground runs on 16 % of aircraft-days | R§4 (1-2 / 4-6 sorties per aircraft-day; night 10-20 %); IMD [DIRECT]; Chalmers 2014 [TRANSFER]; A-W1.1-20/21/29 |
| 2 Sortie | Role mix (OCU / operational), tail affinity; lognormal flight time (median 47.4 min, P5-P95 25-90) with mission multipliers and +15-30 min with tanks/AAR; AB take-off probability (weight, hot day, pilot); ambient from the IMD sampler | R§4 [ASSUMPTION, Tejas-anchored]; A-W1.1-22/23 |
| 3 Grammar | Fixed opening and closing blocks, run-up (a check against the brakes at `pla_runup`, ~90 % N2: the brakes do not hold MIL on a light aircraft), touch-and-go circuits, hot refuel in surge, cooldown | R§4 phase table; A-W1.1-24; A-W2.1-8 |
| 4 Manoeuvres | Semi-Markov over 17 primitives with PLA feed-forward and trim band, target Nz, dwell; envelope (+8 g, M1.6, 15 km); fuel budget (PROXY) truncates at bingo | A-W1.1-25, A-W1.1-27 (PROXY) |
| 5 Pilots | lognormal trait multipliers; AAR closure 2-3.5 kt mean, SD 0.7 kt; delay 0.1-0.2 s | A-W1.1-26 |
| 6 Hand-off | `SortiePlan` + `SortieSummary` counted from the planned PLA history | A-W1.1-28 |

Plan-level parameters marked "calibrated" in `M02.yaml` were set on scenario key `cal`; the A5 gate tests run
on key `gate` (independent draws).

## Validation (W1.1 A5 → tests)

| Gate | Target | `gate` key, 60 d (n = 2,138 sorties) | Test |
|---|---|---|---|
| Type III / FH | 5 +/- 2 | 6.29 | `test_scenario_usage_gates.py::test_plan_level_usage_gates` |
| AB lights / FH | 4-5 | 4.76 | idem |
| Time >= IRP | 17-20 % | 17.9 % | idem |
| AB time | ~5 % | 4.8 % | idem |
| TAC / FH | 2.2-3.3 | 2.90 | idem |
| EOT / EFH | 1.56 | 1.52 | idem |
| Per-flight usage CV | ~0.5 | 0.43 | idem |
| Nz >= 5 g, >= 7 g per 1000 h (plan) | 7,000, 1,300 (+/- 30 %) | 6,960, 1,043 | idem |
| Night | 10-20 % | 15.8 % | `test_night_fraction` |
| Flight time | median 45-55, P5-P95 25-90 min | 51.3, 27.1-91.1 | `test_sortie_duration_distribution` |
| Sorties / aircraft / flying day | 1-2 peace, 4-6 surge | in band | `test_sorties_per_aircraft_per_flying_day` |
| Engine dispersion | ~1.3 | **1.14 (one year): below band** | `test_engine_dispersion` (slow, **xfail strict: W2.6 calibration**) |
| Realised Nz spectrum, realised engine cycles | gates | need the loop | xfail strict (W2.1/W2.3) |

Other tests: `tests/unit/test_scenario_usage.py` (hand-counted histories, hysteresis, property invariants),
`tests/unit/test_scenario_plan.py` (grammar, envelope, fuel, restrictions, payload, keyed determinism, slot
stability), `tests/integration/test_scenario_module.py` (sortie mode phase/hand-off, fleet mode == pure
planner, orders, snapshot), `tests/fork/test_scenario_crn.py` (identical suffixes; grounding order leaves the
other squadron and same-tail slots bitwise identical), `tests/unit/test_scenario_replay.py`.
Operations mode: `tests/fork/test_scenario_m18_ops.py` (real M02 + real M18/M21/sink, 6 tails x 5 days, event
jump: offers, launches, denials, flights and SORTIE records agree with the usage summaries; GROUND,
RESTRICT_USAGE and ASSIGN_SORTIE orders reach the programme; mid-day snapshot restores bitwise),
`tests/unit/test_scenario_usage_drivers.py` (A-W1.1-33..35), `tests/integration/test_event_protocol.py`.

## Known limitations

- Mission mixes, primitive library and transition structure are assumptions calibrated to transfer gates
  (no public fighter manoeuvre matrices); the per-mission statistics are plausible, not validated.
- Engine dispersion is below the ~1.3 target (finding).
- The plan-level fuel estimator is a PROXY (A-W1.1-27); pilots are assigned per slot at random (a pilot can
  appear twice in one wave); no inter-sortie thermal state yet (report §4: "carry thermal state between
  sorties" belongs to M07/M09 state, which persists in telemetry runs).
- `scenario.phase` uses the DASHlink-based dictionary codes until the proposed fighter codes are released.
- Operations mode: no spare-aircraft substitution after a denied launch; ASSIGN_SORTIE applies only to dates
  not yet planned; M02 has no start-failure or air-abort process (`ops.ground_abort` comes only from a
  grounding order before take-off; `aborted` is always false); ground runs are not reported to M18, so M18's
  engine cycle counts exclude them (M10 receives them); usage drivers are plan-level (telemetry mode should
  derive them from truth ports, W2.6) [A-W1.1-36].
