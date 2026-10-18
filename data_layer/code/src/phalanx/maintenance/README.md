# M18 Maintenance, logistics and records (W1.8)

**Purpose.** The maintenance organisation of a Tejas fleet as a discrete-event world (architecture §6 M18, §10;
AD-19, AD-20): configuration control, snags and troubleshooting, supply, servicing, inspections, modifications,
hard-time retirement, depot turnaround, manpower and hangar slots. Its records (`maint.records`, contract v0) are
what a downstream predictive-maintenance or availability tool sees. Availability is *computed* from job states,
SCIR-style in 15-minute bins; it is never an input.

M18 decides only from tech-log knowledge. Hidden truth (actual faults, sent by M10/M11) is used only to decide
*outcomes*: does a ground check reproduce the fault, is the removed unit really bad, does an inspection find a
latent fault.

## Interfaces

```python
from phalanx.maintenance import (
    MaintenanceWorld,
    FleetSpec,
    OpsTargets,
    InternalPolicy,
    load_m18_config,
    DefectInjector,
    cann_plan,
)

cfg = load_m18_config()  # M18.yaml + M18/catalogue.yaml + M18/codes.yaml, provenance-checked
cfg2 = cfg.with_values(tejas_supply_factor=1.0)  # sweeps; the overrides are recorded in params
cfg3 = cfg.with_catalogue_values({"HYDP": {"p_isolate": 0.9}})  # per-class values (new catalogue hash)

m18 = MaintenanceWorld(
    "m18",
    cfg,
    FleetSpec.from_scenario(fleet_scenario, bases={"sulur": "SUL"}),  # or FleetSpec(tails, bases, tail_base)
    epoch_utc_ns=...,
    calendar=DecisionCalendar(...),
    dict_version=...,
    dict_hash=...,
    targets=OpsTargets(m21="m21", sink="sink", scenario="m02", health="m10", monitoring="m14"),
    internal=InternalPolicy(cann=True),  # cann=False when a policy issues CANNIBALISE orders
)
```

Engine identity (W2.1c): `engine_serial` is a contract linkage key, so the M02 scenario's installed engine serials
(`IN20-<token>`, default token the tail number) are the single source of truth. `FleetSpec.from_scenario` passes
them as `engine_serials` with their `engine_serial_prefix`: M18 installs them at the ENG position and mints
spares and new procurement as `<prefix>-nnnnnn` (never reusing a scenario serial); M10, M11 and M14 are
configured with the same serials (`tests/integration/test_engine_serial_identity.py`). A bare `FleetSpec`
keeps the W1 behaviour (M18 mints `ENG-nnnnnn` for every engine) and breaks that tie; use it only in M18-only
tests.

`MaintenanceWorld` is an event-only `ModuleBase` (`rate = None`; usage mode runs it with the kernel's event
jump). All state is explicit numpy arrays plus canonical-JSON documents (`docstate.Cow`, copy-on-write), so
`core.snapshot` captures queues, inventories, in-transit spares and pending work. Randomness comes from
identity-keyed streams only: per tail (`tail_exec`, occurrence index from the local day and a slot), per serial,
per demand. The usual way to run it is `phalanx.fork.OpsSession` (see `src/phalanx/fork/README.md`).

Other public pieces: `scir` (states, precedence, `bin_states` reference binning, `kpis_from_occupancy`),
`rules.cann_plan` (the status-quo cannibalisation rule, shared with `orders.policies.StatusQuoPolicy`),
`records` (row builders, `rows_to_table` validates every batch against contract v0), `defects.DefectInjector`.

## Event protocol (what W2.6 wires to M02, M10/M11 and M14)

Every payload uses plain top-level keys (AD-48.1, `phalanx.health.protocol.plain_payload` /
`read_payload`; nested values travel as canonical JSON text named in `json_keys`); times are kernel ns,
whole seconds (A-W1.8-14).

**Inbound**

| kind | from | doc | effect |
|---|---|---|---|
| `m18.start` | session (t = 0) | `{}` | initial configuration and life (A-W1.8-20), `cfg.install` per position, first TECH_LOG / AVAILABILITY_STATE, daily review |
| `ops.offer_request` | M02 | `day`, `reply_to` | replies `ops.offer` with the tails that are MC, on the ground, not held and not in work, plus usage restrictions |
| `ops.launch` | M02 | `sortie_id`, `tail_no`, `reply_to` | marks the tail flying, or replies `ops.launch_denied` with a reason |
| `ops.ground_abort` | M02 | `tail_no`, `sortie_id` | start failure etc.: the tail is back on the ground |
| `ops.sortie_done` | M02 | `sortie_id`, `tail_no`, `t_takeoff`, `t_landing`, `flight_hours`, `landings`, `engine_cycles`, `engine_starts`, `chute_streamed`, `mission_type`, `crew_id`, `aborted` | SORTIE record 0.5 h later, usage accrual (hours, cycles, landings, streamings), pilot write-ups 0.3 h later |
| `obs.event` | M14 (via the contract) | `topic`, `row` (an `events.*` row at its `t_ingest`) | HMS review 0.33 h later: defect, defer-and-monitor (non-grounding BIT), or conditional inspection (exceedance) |
| `truth.fault` | M10/M11 | `fault_id`, `tail`, `pos`, `serial`, `mode`, `symptom` (`pilot`, `both`, `preflight`, `latent`, `bit`), `grounding` | hidden: the fault travels with its serial |
| `truth.fault_clear` | M10/M11 | `fault_id` | hidden: fault no longer active |
| `truth.incident` | M10/M11 | `tail`, `kind` (`start_failure` or an incident), `positions` | JFS start failure (preflight snag) or an incident write-up (e.g. brake excursion) |
| `order.exec` | M21 | `order` (an `orders.commands` row) | executes one of the 18 actions at its decision epoch |
| `m18.disruption` | scenario | `cls`, `factor`, `t0`, `t1` | supply lead-time factor for a class over a window |

**Outbound**

| kind | to | doc |
|---|---|---|
| `ops.offer`, `ops.launch_denied`, `ops.assign`, `ops.restrict` | scenario (M02) | tails offered / denial reason / ASSIGN_SORTIE / RESTRICT_USAGE parameters |
| `cfg.install`, `cfg.remove` | health (M10) | `tail`, `pos`, `serial` (+ `cls`) |
| `mx.action` | health (M10), and monitoring (M14) for `SWLOAD` | `tail`, `pos`, `action` (`RR`, wash/servicing type, `MOD`, `SWLOAD`), `serial` / `mod_id` / `sw_config_id`, `job_no` |
| `mx.repaired` | health (M10) | `serial`, `level` (`base`, `depot`): the unit is renewed |
| `mx.monitoring` | monitoring (M14) | `tail`, CHANGE_MONITORING_CONFIG parameters |
| `order.progress` | M21 | `order_id`, `status` (QUEUED, IN_WORK, COMPLETED, REJECTED), `reason`, `result_record_ids` |
| `rec.maint.records` | record sink | `row` (+ `hints` for the defect injector) |

Imperfect execution is shared: M18 decides *what* is done and records it; M10/M11 decide *what it does to the
hardware* (partial wash recovery, induced defects on a new install). The W1 fixture fleet
(`tests/fork/test_fork_fixture_fleet.py`, TEST FIXTURE) implements the M02/M10/M11/M14 side of this protocol.

## Records

The §10 types: SORTIE, TECH_LOG, DEFECT_WO, COMPONENT_LIFE, INSPECTION, SUPPLY_DEMAND, CANNIBALISATION,
MODIFICATION, EXCEEDANCE_INSPECTION, SHOP_FINDING, AVAILABILITY_STATE. Synthetic, IAF-relabelled code tables
(`M18/codes.yaml`: when-discovered, type-maintenance, action-taken, malfunction, inspection, servicing levels;
each code carries its meaning and the transfer source) and synthetic part numbers (`SYN-...`), labelled synthetic.
Every new state of a record is a new `record_version`; `t_ingest` is the moment the entry exists.

- AVAILABILITY_STATE: one record per tail per 15-min bin *in which the binned state changes* (the state persists
  until the next record; a later degradation in the same bin is a new version). Bin state = most degraded of the
  carried-in state and every state entered in the bin (NAMP precedence NMCD > NMCS > NMCM-U > NMCM-S > PMCS >
  PMCM > FMC).
- TECH_LOG carries the instantaneous state in `availability_state` and the limitations text (U/S jobs,
  deferrals, `GROUNDED BY ORDER`, limits).

**Data-quality defects** (`DefectInjector`) are applied after truth, per record identity (batch-independent):
CANN under-reporting (whole actions), missing part records, wrong form, reconciliation lag, free-text noise,
"XXX" serials, duplicate snags. Each defect is written to the restricted `labels.truth` manifest (DEFECT rows).

## Assumptions (tagged; registry rows A-W1.8-1 … A-W1.8-17, -20 in `docs/assumptions.md`)

- Manpower and shifts, record/work delays, servicing intervals and durations, inspection PODs, troubleshooting
  and R/R times, diagnosis probabilities, shop/depot times, rotable pools, initial fleet state: `[ASSUMPTION]`
  with sweeps in `configs/tejas/params/M18.yaml` and the catalogue.
- Wholesale lead time: log-normal fitted to the CAG IL-76 AOG bins `[DIRECT IAF, transport fleet]` times a Tejas
  OEM-support factor 0.3 `[ASSUMPTION, sweep 0.1-1]`; AOG/MCM/PHU multipliers 1/1.5/2.5.
- DIRECT anchors: CAG 17/2015 (4 reserve engines for 20 aircraft), DDP AMAGB 750 h life, drag chute 45
  streamings / 8 years, IST offset. TRANSFER: NAMP crew size and 15-min bins, F-35 deferral of BIT codes, GAO
  CANN man-hours, brake and tyre lives.
- **PROXY A-W1.8-17:** single-echelon supply pipeline (base stock + base shop/depot loop + wholesale pool); the
  real chain is multi-echelon (base / BRD / HAL / OEM).

## Validation criteria and tests

| Criterion | Tests |
|---|---|
| A1 key integrity, SCIR arithmetic, resource and authority rules | `tests/unit/test_maintenance_scir.py`, `tests/property/test_maintenance_scir_property.py`, `tests/fork/test_maintenance_contract.py`, `tests/unit/test_maintenance_world.py` |
| A2 priors (calibration, strict xfail W2.6), defect rates, supply bins, diagnosis outcomes | `tests/fork/test_maintenance_priors.py`, `tests/statistical/test_maintenance_{defects,supply,outcomes}.py` |
| A6 contract conformance, restricted manifest | `tests/fork/test_maintenance_contract.py` |
| A7 determinism, snapshot round-trip | `tests/fork/test_fork_snapshot.py`, `tests/fork/test_fork_kpis.py` |
| Event chains 1-8 | `tests/unit/test_maintenance_world.py`, `tests/fork/test_maintenance_chains.py` |

## Known limitations

- Availability priors (Su-30/CAG occupancy, USAF CANN band) are calibration targets for W2.6: they need real M02
  usage and M10/M11 failure processes (two strict xfails).
- One working window per day for all bases; no skill trades; hangar slots only for periodic servicing.
- The supply chain is the PROXY above; wholesale stock is unlimited (lead time only).
- Performance: about 0.9 s per tail-year with the fixture fleet (pure Python event handlers); a 40-tail
  fleet-decade is ~6 min per run.
