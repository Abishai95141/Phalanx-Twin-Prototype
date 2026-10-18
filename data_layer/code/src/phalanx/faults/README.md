# `phalanx.faults`: M11 fault injection and the propagation graph (W1.5)

M11 schedules faults: stochastic onsets, scripted orders, M10 damage thresholds and maintenance-induced latent
defects. It applies each one only as an event to the module that owns the affected state, and it propagates
cascades along a typed dependency graph. It owns no physics. A faulty run and a healthy run take the same
generation path and differ only in state values (I6; the label-leak guard checks this). Fault truth leaves M11
only as restricted FAULT labels.

Binding sources: architecture §6 M11, §9.2–9.3, AD-18, AD-27, AD-37, AD-42; `W1_interfaces.md` "M11
Faults"; W1.5 brief. Evidence: report §9; `research_notes/.../faults_and_degradation*` (FD#1–38) and
`texture_and_fault_gap_closure*` (TFG#1–41).

## Interfaces

```python
from phalanx.faults import FaultInjector, FaultConfig, load_catalogue, load_graph, load_fault_params

cfg = FaultConfig(
    load_catalogue(),
    load_graph(),
    targets={"health": "health", "sensors": "sens", "monitoring": "monitoring", "engine": ...},
    engine_serials=("IN20-0001",),
    bias_channels=sensor_bias_channels(d),
    realise_physics_edges=True,
)  # usage mode; False in telemetry mode (PD-W1.5-1)
m11 = FaultInjector("faults", load_fault_params(), config=cfg)  # event-only, no ports
```

Events handled: the catalogued `ops.power_up` (M02, W2.5, emission planned for W2.1a: the engine start of a
committed sortie; the preflight start-failure modes are drawn here, onsets at the power-up instant, each from
its own generator of the sortie stream, so the outcome equals the take-off path's and no other draw moves; the
sortie start then skips them; drivers `engine_starts` and `cold_soak`, A-W2.5-2), the catalogued
`ops.takeoff` / `ops.sortie_done` (M02, AD-48.2: the telemetry-mode sortie
starts at the actual take-off with onsets over the planned airborne window [t_takeoff, t_landing] and the
plan's drivers, bitwise as the W1 hook would; it ends at engine cut-off with the flight hours; another
tail's events are ignored; a sortie started through both paths raises), and the W1.5-internal
`faults.sortie_start` (optional
`window_s`: onsets in [t, t + window]; usage mode uses 0), `faults.install` (from M10: the serial now at an
M18 position), `faults.sortie_end`, `faults.inject` (scripted; `mode`, optional
`severity`, `covered`, `engine`, `key`, and for the generic sensor mode `sensor_mode`, `magnitude`, `rate`,
`rate_per_s`, `duty`, `probe`, `factor`, `level`), `faults.trigger` (from M10), `faults.maintenance`
(`job`, `action`); internal `faults.onset`, `faults.node`, `faults.clear` and `faults.sensor_hold`.

Events emitted (I6: state changes only; AD-44 kinds declared in `ports.py` `EVENTS_OUT`):

| Target | Event | Payload |
|---|---|---|
| M18 (`maintenance`) | `truth.fault` | `fault_id` (`<tail>:<mode>#<instance>`), `tail`, `pos`, `serial`, `mode`, `symptom`, `grounding`. Hidden truth, plain keys (AD-48.1), at the first whole second after onset (`maintenance.py`, A-W1.5-27). |
| M18 | `truth.fault_clear` | `fault_id`, when an instance clears on its own. A fault whose unit is replaced leaves with the unit, and M18 keeps it by serial. |
| M18 | `truth.incident` | `tail`, `kind`, `positions`: JFS cold-start failure (`start_failure`), the brake-software defect, a bird strike |
| M10 | `health.fault` | `state`, `engine`, `delta` (× severity), `op` |
| M12 | `sensor_fault` | **exactly** `{channel, mode, value, rate, duty, probe}` (AD-42; `sensor_faults.sensor_fault_payload`) |
| M14 | `monitor.lru_condition` | `code`, `magnitude` (σ of the BIT statistic), `covered`, `instance`, `clear` |
| M09 | `util.fault` (AD-44) | `tail`, `mode`: `gen_fail`, `bk_fail`, `fire_onset`, `fire_loop_open`, `fire_loop_short`; the clear sends `gen_restore`, `bk_restore`, `fire_out` or `fire_loop_ok` (A-W1.5-29) |
| M05 | `fcs.channel_fault`, `fcs.actuator_fault`, `fcs.wow_fault` (AD-47) | `tail`, `channel`/`subsystem` (DFCC subsystem name resolved by M05's layout), `surface`/`mode` (jam, servo; + `channel`), `leg`/`value`; `active` false on clear |
| M02 | `ops.start_failure` (AD-49, catalogued, hidden; target `"ops"`) | `tail_no`, `sortie_id`, `mode`: the onset of a start failure (`maintenance.START_FAILURES`: JFS cold start, hung start, hot start). M02 ground-aborts the sortie if it has not taken off. With `ops.power_up` (W2.5) the start failures are drawn at engine start and the report precedes the take-off, so M02 ground-aborts (`tests/integration/test_faults_preflight_abort.py`); `ops.power_up` replaces the proposed `ops.launch` because M18 may still deny a launch, while a power-up exists only for a committed sortie. **Until M02 emits `ops.power_up` (W2.1a)** M11 learns of a sortie at `ops.takeoff` or from M10's usage-mode forwarding, the report arrives at or after take-off and M02 only counts it (A-W2.1c-6). |
| M07/M08/M06 | `eng.fault_inject`, `fadec.fault_inject`, `af.fault_inject` (AD-48.4, catalogued, hidden) | `tail`, `mode`, `param` (× severity), `instance`, `engine`, `clear`; `af.fault_inject` adds `leg` (M06 gear leg 0 nose, 1 left, 2 right, -1 all; from the effect's `legs`, `leg`, `leg: "*"` = a main leg by the instance's choice, or `leg: key` = the trigger key's side). A clear repeats the onset's choice (state `inst_choice`), so a `"*"` channel, surface or leg clears the one it set. These names avoid M08's own `fadec.fault`. |

Sensor-fault mapping (catalogue units → AD-42 SI payload). `magnitude` is a fraction of the channel span ×
severity:

| Mode | Payload |
|---|---|
| bias, spikes | `value` = magnitude × severity × span |
| drift | `value` = `rate_per_s` × span (per second), held as a bias at its bound once it reaches magnitude × severity × span |
| intermittent | M12 dropout with `rate` and `duty` (`intermittent_rate_duty` converts two transition rates) |
| short | `value` = the `level` fraction of the range (default: top) |
| probe_short | `value` = the `level` fraction of the range (default: bottom) |
| slow | `value` = time-constant `factor` (≥ 1) |
| stuck, open, probe_open, clear | no value (M12 holds, or reads the bottom of the range) |

The channel must be in M10's bias index map, which is M12's channels.

Data:

- `configs/tejas/faults/catalogue.yaml`: 83 modes covering FD#1–38, TFG#1–41, the Tejas-specific
  events (JFS cold-start failure, gauging artefact, brake-software defect, FCS channel dropout) and scripted
  modes for the M09 and M05 fault hooks (backup failure, fire-loop open/short, actuator jam, servo coil);
- `configs/tejas/faults/graph.yaml`: 45 nodes, 42 typed edges G01–G42 (shaft, hydraulic, thermal,
  data_electrical, discrete, mechanical; transfer gain, threshold, lag or delay; fixed, uniform or log-uniform
  latency) and the six AIB templates;
- `configs/tejas/faults/hidden_states.yaml`: the 50 hidden states plus the bias and life extensions.

Other public functions:

- `labels.fault_labels(...)`: FAULT rows, with `subject_id = <mode>#<instance>[@key]`, `category` = the
  mode id and `serial_no` = the engine serial for engine modes;
- `leak.leak_features(records, feature_set)`: the `texture_only` and `metadata_only` features of the
  label-leak audit, which W2.5 wires into `phalanx.validation.guards`.

## Randomness (AD-37, CRN)

| Stream | Key | Generators |
|---|---|---|
| `faults.sortie` | (scenario, tail, sortie) | one per mode index |
| `faults.latent` | (scenario, tail, job) | one per maintenance job |
| `faults.instance` | (scenario, tail, event = instance number) | one per scripted or triggered fault |

A sortie flown in two forks gets the same exogenous faults, whatever orders came before it.

## Assumptions and PROXY items

A-W1.5-20 … A-W1.5-27 in `docs/assumptions.md`:

- onset rates with no public value;
- bird and FOD ingestion and severity;
- latent-defect probabilities and latency;
- Markov intermittents;
- graph latencies and the mechanism split;
- sensor-fault rates and shapes;
- coverage;
- the M18 truth mapping: position, symptom, grounding and incidents (A-W1.5-27).

**PROXY (A-W1.5-26):** in usage mode, a covered fault whose mode has detection codes but no explicit
monitoring effect shifts its first code's BIT statistic by `usage_detection_sigma` (8 σ). This stands in for
the detection physics of M08, M05 and M09, which do not run in usage mode. `test_faults_module::
test_usage_detection_stand_in_only_when_covered` exposes it (telemetry mode never emits it). It is replaced
when W2.1 runs the controllers' own monitors.

## Validation (acceptance → tests)

| Criterion | Tests |
|---|---|
| A4 graph acyclic per step, typed edges, transfer functions, the six AIB templates | `tests/unit/test_faults_graph.py` |
| Catalogue covers both research catalogues; faults are state perturbations only | `tests/unit/test_faults_catalogue.py` |
| Onset rates (Poisson, per-event, Markov) with n and exact 99 % CIs; CRN across forks | `tests/statistical/test_faults_statistical.py` |
| Injector behaviour: shocks, cascades in both modes, latent defects, transient clear, labels | `tests/unit/test_faults_module.py` |
| AD-42 payload and channels | `tests/unit/test_faults_sensor.py` |
| AD-42 events accepted and applied by the real M12 | `tests/integration/test_health_faults_m12_wiring.py`, `tests/integration/test_health_faults_m18_m12_protocol.py::test_sensor_fault_events_drive_m12` |
| AD-44 declarations; `truth.*` handled by the real M18 (fault on the installed serial, transient clear, incident job) | `tests/integration/test_event_protocol.py`, `tests/integration/test_health_faults_m18_m12_protocol.py` |
| Label-leak front end: metadata null, texture null (5 replicates, one-sided), planted leak caught | `tests/integration/test_faults_label_leak.py` |
| A7 determinism, snapshot, CRN | `tests/fork/test_health_faults_monitoring_fork.py` |

## Known limitations

- In telemetry mode, per-event faults are timed uniformly within the sortie, not at their driver event (for
  example, an AB light). W2.1 can pass driver times.
- `physics` graph edges are left to the module dynamics in telemetry mode. The cascade order is then an
  invariant to check (M20/B7), not something M11 enforces.
- Texture-visible sensor-fault classes (spikes, stuck, intermittent) leak by nature. W2.5 must exclude them
  from the texture-only audit or judge them separately.
- The guard's pre-registered two-sided rule false-fails null data through below-chance AUCs. The tests use the
  one-sided rule (AD-40).
- Telemetry mode: the sortie starts at `ops.takeoff` (AD-48.2) with the plan's per-sortie drivers and the
  planned airborne window (A-W2.1c-3), not the realised ones. In usage mode M10 still forwards it from
  `usage.sortie_summary`, with onsets at the summary time (a world uses one path; both raise).
- Belief forks: removing faults that M18 does not know about (`keep_faults`) is not implemented in M11 yet.
- Utility hardware faults (pump failure, fitting and FOHE cracks, ISA check valve, AMAGB) act through M10
  states that M09 reads in `health.utility`. Gear collapse, tyre burst, strut extension failure and runway
  excursion reach M06 as `af.fault_inject` (AD-48.4); partial power loss and brake loss keep only their graph,
  monitoring and incident effects.
- AND gates take the sortie's cold soak (`faults.sortie_start` `cold_soak`, or `cold_soak` on an injected
  fault) as the `env.cold_soak` condition.
