# Wave 1 interface catalogue (frozen for W1; changes only through the coordinator)

This file fixes **what flows between W1 work packages**. Each WP implements its side exactly as written. If an
interface below is wrong or missing something you need, stop and report it with a concrete proposal. Do not
invent a private variant. W2.1 wires these ports together. Mismatches found there are defects in whichever side
departed from this file.

Binding background:
- `docs/architecture.md` §4 (layers), §5.5 + AD-36 (module contract), §7 (measurement chain), §8 + AD-35 (time, rate groups vs clock domains), AD-22 (Numba kernels), AD-37 (RNG), AD-38 (CIR in engineering units), AD-39 (dictionary conventions).
- `src/phalanx/core/README.md`.

## 1. Conventions

- **Machine-readable catalogue (authoritative for names, units, dtypes and shapes):** `configs/interfaces/w1_ports.yaml`. It is enforced by `tests/integration/test_interface_conformance.py` at every merge.
  - **Port names are lowercase snake_case** (core rule). A catalogue key `<prefix>.<port>` means module prefix plus port name, e.g. `eng.t5`, `fadec.wf_cmd`.
  - **Each package publishes `src/phalanx/<pkg>/ports.py`** with:
    - `PREFIX: str`, e.g. `"eng"`;
    - `def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]`, returning `(inputs, outputs, bindings)`.

    `bindings` maps each input port name to the catalogue signal it reads, e.g. `{"n2_meas": "eng.n2"}`. W2.1 builds the wiring from these bindings.
  - **Controller lane inputs** (DFCC and FADEC) are bound as `lane.<dictionary channel_id>`, e.g. `{"n2_a": "lane.ENG.N2.A"}`.
    - The port carries the **SI value of the digitised reading**. Core ports are SI-only, so M13's in-loop path quantises in EU, then converts with `Dictionary.eu_to_si`.
    - Recorded CIR stays in EU (AD-38).
    - The W2.1 test "controller saw = recorded" compares `eu_to_si(cir.value)` with the lane value.
    - The conformance test checks the channel exists and the unit matches `eu_conversion(channel).si_units`.

- **Units:** SI inside modules and on every truth port (AD-36). Angles in rad, temperatures in K, pressures in Pa,
  rotor speeds in rad/s, mass flow in kg/s, power in W.
  - Engineering units (percent, degC, lb/h, psia, …) appear **only** after M13 acquisition, i.e. in CIR and in
    controller lane values. M13 converts SI to EU using the dictionary units (AD-38).
  - Percent-speed references come from dictionary constants: N1 100 % = 13,270 rpm; N2 100 % = 16,810 rpm.
- **Port names:** `<module>.<signal>`. Multi-unit signals carry a leading unit axis: engines `e`, hydraulic systems
  `h`, tanks `k`, gear legs `g`, surfaces `s`.
- **Engine count:** every engine-side kernel (M07, M08, M12 engine sensors, M03 engine disturbances) is vectorised
  over `n_engines ≥ 1`.
  - Tejas: `n_engines = 1`.
  - Proxy mode (DASHlink Tail 687, a **four-engine regional jet** with separate-flow high-bypass engines, no AB, W2.4): `n_engines = 4`. Cross-engine independence (B1) is tested there. Topology: AD-43.
  - Never hard-code a single engine.
- **Rates:** truth ports update at 240 Hz unless marked.
  - Controllers run in their own clock domain, and their outputs are applied at the first truth frame after the compute instant (AD-36, §8):
    - DFCC: rate group 80 Hz, exact;
    - FADEC: 60 Hz nominal (AD-39), clock domain;
    - FCS sensor lanes: 80 Hz.
  - Slow modules: M10 updates at sortie boundaries in usage mode. In telemetry mode its health is a held port, perturbed only by M11 events.
- **Kernels (AD-22):** every continuous module provides an `@njit` kernel over flat state arrays: `float64` and `int64` state vectors, a flat `float64` parameter vector, tables as NamedTuples, and RNG blocks fed in as input arrays.
  - It also provides a pure-NumPy reference implementation that agrees **bitwise**.
  - The `ModuleBase` wrapper (`phalanx.core`) handles ports, state schema, snapshots and streams.
  - Calibrated kernels must be **complex-step safe**: M07 dynamics, M08 loop gains, M09 hydraulics/fuel/thermal, M05 actuators and M12 sensor dynamics. Each needs a complex-step vs central-FD test.
- **RNG:** every stochastic element declares a `StreamDecl` keyed by the right identity kinds (AD-37).
  - Installation bias: `(scenario, serial)`.
  - Process disturbance: `(scenario, tail, serial, sortie)`.
  - Sensor noise: `(scenario, tail, sortie, sensor)`.

  Draws are indexed by tick, sample or event number, held in state. No module draws from another module's stream.
- **Hidden truth:** health states, biases and fault states are never written to CIR or contract consumer topics. They are exposed only through restricted labels (M10/M11 → `labels.truth`).

## 2. Truth-layer ports

### M02 Scenario → M04, M18, M21 (event-driven)

| Port / event | Content | Notes |
|---|---|---|
| `scenario.epoch_utc_ns` | int64 | AD-38: contract time = epoch + kernel t |
| `scenario.sortie_plan` (event) | sortie_id, tail, config, base, mission type, phase segments `[(phase, t_start_ns, targets: alt m, Mach or TAS m/s, heading rad, g, AB allowed, ...)]` | M04 consumes; M18 for records |
| `scenario.phase` | int phase code (dictionary code table) | Held port for M04, M14 and the validation `phase` |

### M03 Environment and process disturbances → M06, M07, M09, M05, M12

| Port | Unit | Shape | Notes |
|---|---|---|---|
| `env.t_s`, `env.p_s`, `env.rho`, `env.a_sound` | K, Pa, kg/m³, m/s | () | At aircraft altitude (uses `af.alt` with a one-frame delay) |
| `env.q_spec` | kg/kg | () | Specific humidity |
| `env.wind_ned` | m/s | (3,) | |
| `env.turb_vel_body`, `env.turb_rate_body` | m/s, rad/s | (3,), (3,) | von Kármán (Dryden in tests) |
| `env.w_engine` | 1 | (e, 5) | **Process disturbances (AD-32, AD-46):** columns = `[fuel_metering, combustor_eff, inlet_recovery, shaft_load, fan_face]`; dimensionless fractional perturbations. `fan_face` = fan-face distortion acting on fan flow capacity and efficiency (LP-spool-specific) |
| `env.w_bleed_pto` | 1 | (e,) | Fractional bleed/PTO load variation |
| `env.w_hyd` | m³/s | (h,) | Hydraulic demand variation |

Each disturbance = aircraft-common component + unit-specific component, with configurable PSD (state-space
shaping filter) and cross-unit coherence. Values are proxy-identified in W2.4; W1 ships the structure, with tagged
placeholder parameters swept in tests.

### M04 Pilot → M05, M08 (+ proxy autothrottle)

| Port | Unit | Notes |
|---|---|---|
| `pilot.stick_pitch`, `pilot.stick_roll`, `pilot.pedal` | 1 (−1…1) | Normalised inceptors |
| `pilot.pla` | rad | (e,) power lever angle |
| `pilot.gear_cmd`, `pilot.airbrake_cmd`, `pilot.ab_select` | int | Discretes |
| `pilot.at_engage`, `pilot.at_n1_cmd` | int, 1 | **Proxy mode only** (autothrottle state and N1 command; architecture §14.3) |

### M05 FCS and actuators ↔ M06, M09

| Port | Unit | Shape | Notes |
|---|---|---|---|
| `fcs.surf_pos` | rad | (13,) | Order: elevon LO, LI, RI, RO; rudder; slats 1–6; airbrake L, R |
| `fcs.surf_rate` | rad/s | (13,) | |
| `fcs.hyd_flow_demand` | m³/s | (h=2,) | Q = A·ẋ summed per system |
| `fcs.law_state`, `fcs.channel_status` | int | (), (4,) | Normal/reversionary; quadruplex channel health |

Inputs:
- FCS sensor lanes: rates, accelerations, air data and WoW, digitised per lane at 80 Hz by M12/M13 in-loop kernels (see §3);
- `util.hyd_dp_avail` (Pa, (2,)).

### M06 Airframe → M03, M07, M09, M12

| Port | Unit | Shape | Notes |
|---|---|---|---|
| `af.pos_geo` | rad, rad, m | (3,) | lat, lon, alt (geometric) |
| `af.alt` | m | () | Geometric (ellipsoidal) altitude; M03 derives pressure altitude (AD-49) |
| `af.vel_ned` | m/s | (3,) | |
| `af.quat` | 1 | (4,) | Scalar-first (w, x, y, z), body → NED (AD-49) |
| `af.omega_body` | rad/s | (3,) | |
| `af.f_spec_body` | m/s² | (3,) | Specific force at the CG |
| `af.alpha`, `af.beta`, `af.tas`, `af.mach`, `af.qbar` | rad, rad, m/s, 1, Pa | () | |
| `af.nz` | 1 | () | Load factor |
| `af.wow` | int | (g=3,) | Weight on wheels per leg |
| `af.wheel_speed` | rad/s | (2,) | Main wheels (brakes) |
| `af.brake_energy_rate` | W | (2,) | |
| `af.hag` | m | () | Height above ground |

Inputs:
- `fcs.surf_pos`;
- `eng.thrust`;
- `util.mass`, `util.cg`, `util.inertia`;
- M03 atmosphere and turbulence.

### M07 Engine → M06, M09, M12 (per engine `e`)

| Port | Unit | Notes |
|---|---|---|
| `eng.n1`, `eng.n2` | rad/s | Rotor speeds |
| `eng.t2`, `eng.t25`, `eng.t3`, `eng.t5` | K | t5 = T56 station truth (M12 models the harness) |
| `eng.p2`, `eng.ps3`, `eng.p5` | Pa | |
| `eng.wf` | kg/s | Actual main fuel flow; `eng.wf_ab` for afterburner |
| `eng.a8` | m² | Nozzle throat area |
| `eng.vg_igv`, `eng.vg_vsv` | rad | Variable geometry |
| `eng.w2` | kg/s | Airflow |
| `eng.thrust` | N | |
| `eng.oil_t`, `eng.oil_p` | K, Pa | |
| `eng.vib_src` | m/s² | (bands,) vibration source amplitudes |
| `eng.stall_margin` | 1 | |
| `eng.ab_state`, `eng.flame_state` | int | |
| `eng.bleed_p3`, `eng.bleed_t3` | Pa, K | Bleed port conditions for M09 ECS |

Inputs:
- `fadec.*` commands;
- inlet conditions from M06/M03;
- `env.w_engine`;
- `util.bleed_extract` (kg/s), `util.pto_power` (W);
- `health.engine` (see M10).

### M08 FADEC → M07, M14 (per engine `e`; FADEC clock domain, 60 Hz nominal)

| Port | Unit | Notes |
|---|---|---|
| `fadec.wf_cmd`, `fadec.wf_ab_cmd` | kg/s | |
| `fadec.a8_cmd` | m² | |
| `fadec.vg_cmd` | rad | (2,) IGV, VSV |
| `fadec.ignition`, `fadec.ab_enable` | int | |
| `fadec.active_limiter` | int | Code of the MIN/MAX-selected schedule or limiter |
| `fadec.validation_state` | int | (n_engine_sensors,) per-sensor validation status (OK, suspect, failed, substituted) |
| Events | — | Fault codes and caution discretes (`events.bit_faults` / `events.cautions` payloads via M14) |

Inputs:
- `pilot.pla`, and in proxy mode `pilot.at_*`;
- FADEC sensor lanes (N1, N2, T1, T25, PS3, T5 per lane), digitised by M12/M13 in-loop kernels (see §3).

### M09 Utilities → M05, M06, M07, M12

| Port | Unit | Shape |
|---|---|---|
| `util.hyd_p`, `util.hyd_dp_avail`, `util.hyd_t` | Pa, Pa, K | (h=2,) |
| `util.bleed_extract` | kg/s | (e,) |
| `util.pto_power` | W | (e,) |
| `util.fuel_mass` | kg | (k,) |
| `util.mass`, `util.cg`, `util.inertia` | kg, m, kg·m² | (), (3,), (3,3) |
| `util.bus_v` | V | (buses,) |
| `util.gen_online`, `util.batt_soc` | int, 1 | |
| `util.ecs_t`, `util.ecs_p` | K, Pa | (points,) |
| `util.brake_t`, `util.brake_wear`, `util.tyre_wear` | K, 1, 1 | (2,) |
| `util.jfs_state` | int | () |
| `util.fuel_inlet_t` | K | (e,) |
| `util.brake_p` | Pa | (2,) |
| `util.hyd_res_level` | 1 | (h,) |
| `util.probe_heat` | int | () |

Inputs:
- `eng.n2` (master variable);
- `eng.bleed_*`;
- `eng.wf` (fuel burn);
- `fcs.hyd_flow_demand`;
- `af.*`;
- `env.*`, `env.w_hyd`, `env.w_bleed_pto`;
- `health.utility`.

### M10 Health → M05, M07, M09, M12 (held ports; slow)

| Port | Unit | Shape | Content |
|---|---|---|---|
| `health.engine` | 1 | (e, 10) | Component deltas `[fan_eta, fan_flow, hpc_eta, hpc_flow, hpt_eta, hpt_flow, lpt_eta, lpt_flow, comb_eta, nozzle_area]` (fractional; 0 = nominal build) |
| `health.utility` | 1 | (n,) | Pump efficiency, leakage conductance, filter loading, accumulator precharge, brake/tyre wear state, … (index map published by M10) |
| `health.sensor_bias` | SI | (channels,) | Per physical channel installation bias plus drift (hidden; AD-07, AD-26). **Separate from component deterioration** |
| `health.actuator` | 1 | (13,) | Actuator wear/leakage |

M10 also emits the restricted `labels.truth` records for these states.

### M11 Faults → target modules (events)

Fault events go through the core event queue to the target module's `on_event`, as **state perturbations**: a
health delta, a sensor-fault mode change, or a discrete failure. The typed dependency graph (AD-27) is data
(`configs/tejas/faults/graph.yaml`), consumed by M11 and by validation invariants.

**Sensor-fault modes** (applied in M12 at `s_inst` / `s_meas`, architecture §7): bias step, drift, stuck,
intermittent, spikes, open/short, slow response.

## 3. Observation layer and the in-loop path

The measurement chain (architecture §7) runs **twice from the same kernels and streams**:

1. **In-loop**, inside the truth loop, at the controller's clock domain. It produces the lane values the DFCC and FADEC actually use.
2. **Recording**, for every dictionary channel at its acquisition rate. It produces CIR.

At acquisition level, the CIR value of a lane at an instant **is** the value the controller saw: same kernel, same stream draw index (A6 in W1.6; a W2.1 test).

**LRU-computed recorded channels** (voted `.V` words, the FADEC `ENG.T5` average, status, mode and BIT words, gauged totals) are **supplied by the owning module**. Publish each as an output port and list it in `ports.py` as `RECORDED = {port_name: channel_id}`, in SI (or dimensionless for discrete/code words). M13's recorder takes them via `external=` (AD-42). The conformance test checks each against the dictionary.

| Stage | Owner | Kernel signature (conceptual) |
|---|---|---|
| `H_sensor`: physics, incl. harness averaging, position error, gauging | M12 | `s_phys = H(x_true_interp, env, sensor_state, fault_mode)` |
| `D_sensor`: dynamics (FF meter lag, TC τ ∝ W^-0.5, vane 2nd order) | M12 | State-space per channel |
| `b_install + aging`: hidden bias | M12 (state from `health.sensor_bias`) | |
| `n_indep`: idiosyncratic noise, at or below the measured level | M13 | Keyed stream per sensor |
| `Q_rec(Q_nat(·))`: double quantiser, saturation | M13 | Dictionary native step and recorder LSB |
| Artefacts: glitch, gating, freeze, sentinel (never NaN) | M13 | |
| EU conversion | M13 | Dictionary units |

**M13 output (CIR):** `phalanx.ground.cir.CIR_SCHEMA` exactly, built from:
- `param_id`, `source_lru`, `lane` from `Dictionary.contract_location`;
- `sample_index` per stream;
- `t_true`, `t_sample` from the clock domain;
- `value` (EU), `truth_value` (restricted), `validity`, `quality_flags` (acquisition stage), and `rng_key_path`.

**Noise ceiling (W0.5 finding):** adding independent ±1 LSB noise to real flights FAILs B1, B3 (i) and B4. M13 noise
must not exceed the measured idiosyncratic level; test it.

## 4. Data path and operations interfaces

- **M15/M16/M17 (W1.7):** consume CIR batches. They produce:
  - Ch10 files and recording events;
  - decoded `param.samples` in the **identical** contract schema, with `provenance = full_path`.

  `record_id` follows AD-38 (cumulative packet sequence). The dictionary provides `by_bus_address`, `by_rate_group`, TMATS and ICD.
- **M14 (W1.5):** consumes CIR, lane validation states and events. It emits `events.bit_faults`, `events.exceedances`, `events.cautions` and `usage.counters`, per the contract v0 schemas.
- **M18/M21/M22 (W1.8):**
  - consume events, usage counters, health labels (oracle forks only) and orders;
  - emit `maint.records`, `orders.status` and availability;
  - read observations only through `ObservationView.as_of` (I5);
  - snapshot and fork via `phalanx.core.snapshot` (AD-36).
- **Contract schemas** come from `phalanx.dictionary.contract.load_contract("v0")`. Never hand-write a schema.

## 5. Cross-module event protocol (AD-44)

- **Authoritative catalogue:** `configs/interfaces/w1_events.yaml`. It is the M18 hub protocol: scenario ↔ maintenance (`ops.*`), health/faults → maintenance (`truth.*`, hidden), maintenance → health/monitoring (`cfg.*`, `mx.*`), monitoring → maintenance (`obs.event`), faults → sensors (`sensor_fault`), orders ↔ maintenance (`order.*`), usage drivers (`usage.sortie_summary`).
- **Internal events:** names of events internal to a module are free.
- **Cross-boundary events:** every event that crosses a module boundary uses a catalogued kind, with at least the listed payload keys.
- **Declaration:** each producing or consuming package declares `MODULE_IDS`, `EVENTS_OUT` and `EVENTS_IN` in `ports.py`.
- **Enforcement:** `tests/integration/test_event_protocol.py` checks the declarations, including produced events that are catalogued but not declared. E1 requires M02, M10, M11, M12, M14, M18 and M21 to declare.

