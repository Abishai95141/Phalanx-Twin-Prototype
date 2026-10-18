# `phalanx.health`: M10 health state, usage damage and degradation (W1.5)

M10 holds the hidden health state of every serial on the tail: engine module deltas, mechanical damage,
component wear, actuator condition, life consumption and sensor installation bias. It advances that state once
per sortie from the sortie's usage, applies fault perturbations from M11 and resets it on maintenance. The
physics modules see health only through four held ports. The state itself leaves M10 only as restricted
`labels.truth` rows (I5).

Binding sources: architecture §5.2, §6 M10, §9.1–9.2, AD-07, AD-26; `W1_interfaces.md` "M10 Health"; AD-42
(sensor-bias index map); W1.5 brief. Evidence: report §9; `research_notes/.../faults_and_degradation*`,
`not_measured_states.csv` (50 hidden states).

## Interfaces

```python
from phalanx.health import HealthModule, HealthConfig, SortieUsage, load_health_params, sensor_bias_channels
from phalanx.health import ports  # PREFIX "health", ports(n_engines, dictionary) -> ((), outputs, {})

cfg = HealthConfig(
    engine_serials=("IN20-0001",), bias_channels=sensor_bias_channels(d), fault_target="faults"
)
m10 = HealthModule("health", load_health_params(), config=cfg)  # event-only (rate None)
```

| Port (held) | Unit | Shape | Index map |
|---|---|---|---|
| `health.engine` | 1 | (e, 10) | `layout.ENGINE_DELTAS`: fan/hpc/hpt/lpt η and flow, combustor η, nozzle area (fractional deltas) |
| `health.utility` | 1 | (23,) | **M09's `phalanx.utilities.layout.HEALTH_INDEX`** (coordinator decision): hydraulic leaks, compensator drift, filter and precharge per system, ECS, battery, JFS, AMAGB, brakes, tyres, fuel transfer. Each entry is computed from an M10 airframe state (`layout.UTILITY_SOURCES`: wear × scale, clipped below 1 where M09 needs a fraction; A-W1.5-28). The full hidden inventory (engine auxiliaries and every airframe state) is `layout.hidden_entries(e)`; it is reported by the labels, not a port. |
| `health.sensor_bias` | SI per entry | (n_M12,) | **AD-42:** M12's `SensorConfig.bias_index()`, entry i in the SI unit of that channel (`sensor_bias_channels`) |
| `health.actuator` | 1 | (13,) | `layout.ACTUATORS` (in `fcs.surf_pos` order) |

Cross-module events (AD-44, `configs/interfaces/w1_events.yaml`; declared in `ports.py` `EVENTS_IN`).
Payloads use plain top-level keys (AD-48.1; `protocol.plain_payload` / `protocol.read_payload`, which rejects
the retired `{"doc": ...}` encoding).
M18 sends them fleet-wide; an M10 ignores events for another tail (`tail` / `tail_no`):

| Event | From | Effect |
|---|---|---|
| `ops.takeoff` | M02 | AD-48.2: the sortie is airborne (`sortie_open`); health is held for the flight. While it is open, `cfg.install` / `cfg.remove` / `mx.action` on this aircraft, a second take-off and a summary of another sortie raise |
| `usage.sortie_summary` | M02 | one sortie of usage (closes the sortie opened by `ops.takeoff`) (`usage.usage_from_summary`, A-W1.5-17/18). A usage-mode summary (no `usage` key) also runs the sortie in M11 (`faults.sortie_start` with a zero onset window, `faults.sortie_end`) and M14 (`monitor.usage_sortie`). A telemetry-mode summary carries the full usage (`summary_payload`) and forwards nothing. |
| `cfg.install` / `cfg.remove` | M18 | a unit joins or leaves an M18 position (`protocol.POSITION_STATES`, A-W1.5-19). A removed unit's states wait on the shelf under its serial and come back with it bitwise. A new serial is built fresh (draws keyed by serial). Installs are forwarded to M11 (`faults.install`) and, for LRU positions, to M14 (`monitor.lru_replace`). |
| `mx.repaired` | M18 | the shelved unit is renewed: its next install builds a fresh unit (draws keyed by serial and renewal number) |
| `mx.action` | M18 | `ENGINE_WASH` removes ρ of fouling (partial recovery); `OIL` / `HYDRAULIC` / `TYRES` service their states; actions that can induce a latent defect go to M11 (`faults.maintenance`, `protocol.LATENT_ACTIONS`) |

W1.5-internal events (payloads are plain dicts, see `module.py`):

| Event | Payload | Effect |
|---|---|---|
| `health.sortie` | `SortieUsage.to_payload()` | advance every process by one sortie; emit `faults.trigger` once per item when damage reaches its failure threshold (crack, spall, `UTIL_TRIGGERS`) |
| `health.fault` | `state` (`eng:<field>`, `util:<name>`, `act:<name>`), `engine`, `delta`, `op` (add/set/mul) | M11 shock or latent defect as a state change |
| `health.maintenance` | `action` (wash, replace_engine, overhaul_module, replace_component, replace_sensor, service), `target`, `engine`, `serial`, `job` | wash removes ρ of fouling; overhaul keeps a residue; replacement draws a new serial's build state |

Usage drivers: `usage.usage_from_truth(..., **utilities.sortie_wear(state))` (telemetry mode: the LUIs
from truth plus M09's brake / tyre accrual, AD-48.6) or a usage-mode `SortieUsage`. The F404 LUIs
(Type I/III/IV, EFTC by rainflow, SRC, TAMP, EOT, full and partial PS3 cycles) and the Nz level-crossing
counters are pure kernels (`lui_kernel`, `nz_counter_kernel`; `@njit` with a bitwise-equal `.py_func`
reference; chunk invariant). M14 runs the same kernels on recorded data.

Labels: `labels.health_labels(module, state, ...)` gives HIDDEN_STATE rows (`subject_id = <NM id>/<slot>`,
physical units, category = observability class), validated against contract v0 `labels.truth`.

Belief forks (`phalanx.fork.belief.BeliefTarget`): `belief_items` are the installed engine serials,
`belief_prior` is the Weibull bearing-spall initiation in engine hours (A-W1.5-8), and `with_belief` sets the
engine's operating-hour clock and spall life to the posterior draw (a spall not yet initiated under the draw is
removed). Fault instances live in M11, so `keep_faults` is not applied here.

## Model

| Family (architecture §9.2) | Function | Used for |
|---|---|---|
| Wiener fouling, reflecting at 0, drift ∝ dust; wash fraction ρ | `wiener_fouling`, `wash` | fan/HPC fouling |
| Gamma erosion × fighter severity S | `gamma_increment` | fan/HPC/HPT/LPT erosion, coking, nozzle growth, generic wear |
| Rub-in step then exponential | `rub_in` | HPC/HPT clearance after build or overhaul |
| N-CMAPSS abnormal onset `A(exp(a (t/τ)^b) − 1)` after a Gaussian usage threshold per serial | `onset_crossed`, `onset_loss` | HPT abnormal degradation |
| Weibull initiation, then Paris or exponential growth | `weibull_life`, `paris_grow`, `exp_grow` | blade crack, bearing spall (+ debris and oil Fe) |
| Per-serial gamma rate (fleet mean and 2σ), gamma-process increments per EOT (W2.5, A-W2.5-1) | `gamma_rate_draw`, `gamma_increment` | healthy-wear filter debris (QFDA Fe, C25): adds to `debris` (kept apart as `debris_wear`), not to oil Fe, whose normal SOAP slope is the oil-borne part of the same wear |
| Incubation then growth (capped) | `incubation_growth` | hydraulic pumps, hoses, lock springs, AMAGB |
| Miner damage per Nz level crossing | in `module.py` | structural fatigue |
| Sensor bias: installation draw per sensor serial + random walk per √h | `_install_bias`, `_advance_bias` | `health.sensor_bias` (separate truth, AD-26) |

Every process is advanced from usage drivers only. Randomness comes from identity-keyed streams under
subsystem `health`: `engine_build` and `component_build` per serial, `engine_wear` per (serial, sortie),
`airframe_wear` per (tail, sortie), `sensor_install` per sensor serial and `sensor_drift` per (tail,
sortie). Bias and deterioration never share a stream or a code path (A3).

## Assumptions and PROXY items

A-W1.5-1 … A-W1.5-19 and A-W1.5-28 in `docs/assumptions.md` (W1.5 section); A-W2.5-1 (healthy-wear debris, W2.5 section). Each ASSUMPTION parameter has a sweep range
in `configs/tejas/params/M10.yaml`:

- severity S;
- fouling, wash and erosion rates;
- rub-in split;
- onset threshold and shape;
- spall and crack initiation;
- life limits;
- generic wear;
- sensor bias SD and drift;
- environment indices;
- pump incubation;
- Nz fatigue curve;
- overhaul residue;
- summary expansion weights (A-W1.5-17);
- the M09 interface conversions: pump leakage at the limit, servo leak and JFS drag rates, AMAGB loss and
  transfer-pump loss at the limit (A-W1.5-28).

The position map (A-W1.5-19) is SYNTHETIC structure, with no sweep.

**PROXY (A-W1.5-18):** a usage-mode summary gives only `max_nz`, so the Nz level crossings are one per positive
level up to it, which is a lower bound. `tests/unit/test_health_protocol.py::test_nz_from_max_nz_is_a_lower_bound`
exposes it. It is replaced by a per-mission Nz spectrum in the summary, or by telemetry-mode counting.

## Validation (acceptance → tests)

| Criterion | Tests |
|---|---|
| A1 zero rate flat; gamma monotone; Wiener drift ∝ dust; wash by ρ | `tests/property/test_health_processes_property.py` |
| C25 healthy-wear debris (Bennett QFDA Fe mean and 2σ on 1,000 serials), oil Fe slope unchanged, mechanism CRN, belief forks | `tests/golden/test_cross_module_golden.py::test_c25_healthy_oil_debris_wear_rate`, `tests/unit/test_health_wear_debris.py` |
| A2 onset statistics N-CMAPSS-like; LUI/TAC on synthetic cycles | `tests/statistical/test_health_statistical.py`, `tests/unit/test_health_usage.py` |
| A3 bias and deterioration are separate truths | `tests/property/test_health_bias_property.py` |
| Hidden-state catalogue complete (50 states, both directions) | `tests/unit/test_health_catalogue.py` |
| Module behaviour, maintenance, labels | `tests/unit/test_health_module.py` |
| AD-42 bias index map feeds M12 entry by entry | `tests/integration/test_health_faults_m12_wiring.py::test_m10_bias_vector_shifts_each_m12_channel_by_its_own_entry` |
| Ports conform to the W1 catalogue | `tests/integration/test_interface_conformance.py` (M10) |
| AD-44 events declared and handled; summary expansion; units travel with their serial; belief protocol | `tests/integration/test_event_protocol.py`, `tests/unit/test_health_protocol.py` |
| `health.utility` = M09's HEALTH_INDEX; M09 reads it (brake wear pass-through, worn pump strokes further) | `tests/unit/test_health_catalogue.py::test_utility_port_is_m09_health_index`, `tests/integration/test_faults_fcs_m09_events.py::test_m09_reads_m10_utility_vector` |
| With the real M18: start configuration reaches M10/M11; usage-mode sortie downloads into M18 | `tests/integration/test_health_faults_m18_m12_protocol.py` |
| A7 determinism, snapshot mid-sortie, CRN | `tests/fork/test_health_faults_monitoring_fork.py` |

## Known limitations

- Rates and shapes with no public Tejas or F404 value are ASSUMPTION with sweeps. None is calibrated to fleet
  data. Credibility ceiling: NASA-STD-7009B Level 2.
- Physical sensors that M12 does not model yet carry no bias (`excluded_bias_channels`). Examples: ECS,
  electrical, brake pressure, SPS and vibration channels.
- The engine auxiliary and mechanical states (VG offset, spall, crack, oil Fe, seal, FADEC/nozzle hardware)
  and several airframe states (actuator and vane friction, structure, struts, lock springs) have no port.
  They exist only as hidden states and labels until a consumer asks for them.
- Brake heat-sink temperature belongs to M09 (`OWNED_ELSEWHERE`). Brake and main-tyre wear (AD-48.6,
  A-W2.1c-5): M10 holds the hidden wear between sorties; in telemetry mode M09 accrues it in the sortie and
  hands it over at sortie end (`Utilities.sortie_wear` -> `SortieUsage.brake_wear_accrued` /
  `tyre_wear_accrued`, which replace M10's per-landing draw); in usage mode M10's surrogate is calibrated to
  M09's reference landing (`brake_energy_ref` 3.96 MJ per wheel). The nose tyre is M10's surrogate in both
  tiers.
- The serials in `HealthConfig` are not part of the System config hash. W2.1 should include them.
- One M10 per tail. M18 addresses one health module for the whole fleet, so W2.6 needs one of two things: a
  per-tail router, or a fleet-level M10. Each M10 ignores the events for other tails.
- Units installed at t = 0 start new (no initial ageing). W2.6 should seed initial ages consistent with M18's
  initial life.
- Engine positions beyond `ENG` (multi-engine) are not mapped.
