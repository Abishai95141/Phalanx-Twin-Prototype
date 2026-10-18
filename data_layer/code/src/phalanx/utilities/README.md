# `phalanx.utilities`: M09 utility systems (W1.4)

AMAGB/PTO, two 280 bar hydraulic systems, the fuel tank network (true quantities, transfer, feed, burn, heat sink)
and mass properties, the electrical
network, the bleed-air ECS, the GTSU-110 jet fuel starter, brakes/tyres/chute and the engine-bay fire zone, as one
AD-22 Numba kernel inside the §5.5 module contract. **N2 is the master variable** (report §3).

Binding sources: `docs/architecture.md` §6 M09, §9.2 (utility wear rows), §10 (event chains 6-8), AD-22, AD-34,
AD-35...AD-37; `docs/build_briefs/W1.4_utilities.md`; `W1_interfaces.md` (frozen ports). Evidence: report §1, §3,
§4, §9 and Appendix A1; `research_notes/.../tejas_utility_systems.md` (KQ1-KQ11, Synthesis a-f); the released
donor documents (MIL-STD-704F, MIL-H-5440H, MIL-E-18927E, MIL-G-26988C, MIL-F-17874B, HAL Heliyon 2022, Chawla,
Mortimore, Boeing AERO). Restricted values (App. A1: F-16 JFS timings, F-16 tyre/brake-energy limits, F/A-18
AMAD/fuel-hot limits) are not used.

## Files

| File | Contents |
|---|---|
| `ports.py` | `PREFIX = "util"`, `ports(n_engines) -> (inputs, outputs, bindings)` (exactly the catalogue); `RECORDED` (AD-42 LRU-computed channels) |
| `layout.py` | State/input/output/parameter layouts with checked index constants; index maps (tanks, buses, ECS points, gear, `health.utility`) |
| `params.py` | `load_m09_params()`, `param_vector()`, `config_vector()`, `power_quality_bands()` |
| `_num.py` | complex-step-safe helpers (`cmax`, `cmin`, `clip`, `cabs`, `pos`) |
| `hydraulics.py` | compensated pump, leakage (viscosity), accumulator (gas law), relief, filter, reservoir, thermal node, fuel-cooled HX |
| `fuel.py` | free-surface geometry, slosh, pick-up wetness, transfer/feed, tank-fuel temperature, mass properties (no gauge: AD-42) |
| `electrical.py` | generator/backup/battery source logic, transfer interruption, battery Thevenin + 1-RC, 704F classifiers |
| `ecs.py` | bleed extraction (venturi), PHX epsilon-NTU, ACM expansion (PROXY), TCV, cabin pressure, cockpit/avionics nodes |
| `jfs.py` | GTSU-110 start sequencer (battery-cranked spool, ignition draw, free-turbine drive, outcomes) |
| `landing.py` | carbon heat sink, brake wear, tyre wear/skid/burst |
| `fire.py` | bay air temperature and detector loop |
| `kernel.py` | the fused per-tick kernel `utilities_kernel` and `kernel_reference` (= `py_func`) |
| `module.py` | `Utilities(ModuleBase)`, `UtilitiesConfig`, events, `truth_view`, `carry_over` |
| `coupling.py` | loader for the report §3 coupling-sign table (`configs/tejas/params/M09/coupling_signs.csv`) |

## Public API

```python
from phalanx.utilities import Utilities, UtilitiesConfig, load_m09_params, ports, PREFIX
ps = load_m09_params()                                   # ParamSet "tejas.M09" (SI, tags, sources, PROXY flags)
m = Utilities("util", ps, n_engines=1, config=UtilitiesConfig(soak_temp=258.15, batt_soc=0.85, jfs_variant=2))
UtilitiesConfig(soak_temp, p_amb, fuel=None | 8 kg, drop_tanks=(L, R, C), stores=5 kg, batt_soc, jfs_variant,
                f1a_mod, engine_running, brake_temp=None | (L, R), jfs_oil_l=None)   # sortie initial conditions
m.pack_inputs(inputs, n) -> u[n, 42 + 6 n_engines];  m.unpack_outputs(out, outi) -> {port: array}
m.truth_view(state, health=None, p_amb=101325.0) -> dict   # SI truth without a catalogued port (tests, W2.1)
m.carry_over(state) -> UtilitiesConfig                     # next sortie: fuel, battery, hot brakes, JFS oil, config
m.sortie_wear(state) -> {brake_wear_accrued, tyre_wear_accrued, brake_energy_j, landings}  # AD-48.6 -> M10
utilities_kernel(f, i, p, u, cfg, u_ign, dt) -> (f, i, out, outi)   # AD-22 block kernel; kernel_reference = py_func
classify_dc28(v, bands, emergency=, starting=, transfer=) / classify_ac400(v, f_hz, bands, transfer=)  # 704F
```

## Ports (`W1_interfaces.md` §2, `configs/interfaces/w1_ports.yaml`)

Outputs (240 Hz): `util.hyd_p`, `util.hyd_dp_avail`, `util.hyd_t` (h = 2; pressures **gauge** Pa;
`hyd_dp_avail = max(p - p_return, 0)`), `util.bleed_extract` (e), `util.pto_power` (e; **positive = power drawn
from the engine; negative = JFS power delivered into the engine during a start**), `util.fuel_mass` (k = 8, true
contents: F1, F1A, F2, wing L, wing R, drop tank centreline, inboard L, inboard R), `util.mass`, `util.cg` (m, body axes x
fwd / y right / z down, **from the datum = reference CG at 34 % MAC of the DSJ 71(2) 9,000 kg loading**),
`util.inertia` (tensor J about the CG, off-diagonals -Ixy, -Ixz, -Iyz), `util.bus_v` (DC main, DC essential,
DC emergency, AC main V rms), `util.gen_online`, `util.batt_soc`, `util.ecs_t` / `util.ecs_p` (bleed manifold,
PHX outlet, turbine outlet, cockpit, avionics bay; **absolute** Pa), `util.brake_t`, `util.brake_wear`,
`util.tyre_wear` (left, right main; wear = sortie-start wear from `health.utility` + accrued), `util.jfs_state`
(0 off, 1 crank, 2 accelerating, 3 engaged, 4 coasting after a successful start, 5 coasting after a failed or
aborted start). AD-42 additions: `util.fuel_inlet_t` (e; K, tank fuel plus the hydraulic HX heat carried by the
engine-bound flow), `util.brake_p` (left, right main; Pa gauge, A-W1.4-32), `util.hyd_res_level` (h; reservoir
fill fraction), `util.probe_heat` (air-data/TAT probe heaters on). AD-47 (W2.1c): `util.chute_state` (0 stowed, 1
streamed, 2 jettisoned, 3 failed by a deploy above the emergency limit); M06 applies the chute drag while it is 1.

**Recorded LRU-computed channels (AD-42, `ports.RECORDED`):** `util.amagb_speed` -> `SPS.AMAGB.SPEED` (rad/s,
PTO pad of the generator engine), `util.gen_out` -> `ELEC.GEN.OUT` (1 = generator offline), `util.batt_ah` ->
`ELEC.BATT.AH` (C, charge remaining of the faded capacity), `util.batt_low` -> `ELEC.BATT.LOW` (below the 30 Ah
warning), `util.bk_bite` -> `ELEC.BACKUP.STATUS.BITE` (backup-generator fault), `util.cabin_alt` ->
`ECS.CABIN_P.CABIN_ALT` (m, ISA inverse of cabin pressure).

Index maps follow M12's assumed orders (A-W1.6-16): tanks `layout.TANKS`, buses `layout.BUSES`, ECS points
`layout.ECS_POINTS`, gear `layout.GEAR`.

Inputs (bindings): `eng.n2`, `eng.bleed_p3`, `eng.bleed_t3`, `eng.wf`, `eng.wf_ab`, `fcs.hyd_flow_demand`,
`af.f_spec_body`, `af.tas`, `af.mach`, `af.wow` (nose, left main, right main), `af.wheel_speed`,
`af.brake_energy_rate`, `env.t_s`, `env.p_s`, `env.rho`, `env.w_hyd`, `env.w_bleed_pto`, `health.utility`
(index map `layout.HEALTH_INDEX`, 23 entries, proposed to M10).

**Power-at-zero-speed convention (JFS start):** the PTO start drive is torque limited, so the delivered power
is `P = min(P_avail, T_peak (w_pto + w_floor))` with `jfs_w_floor = 1 rad/s`; M07 must convert with the same
floor, `T = -P / (w + w_floor)`.

## Model summary and assumptions (tagged; rows A-W1.4-1...32 in `docs/assumptions.md`; A-W1.4-16 retired by AD-42)

- **AMAGB/PTO** [DIRECT rated speed, peak torque; ratios/losses ASSUMPTION A-W1.4-1]: pads at fixed ratios to
  N2; PTO power = pump shaft power + generator shaft power + gear losses (~speed^2) - JFS start power.
- **Hydraulics** [DIRECT 280 bar, 2 systems, 9.5 L reservoir; ASSUMPTION A-W1.4-2...11]: see `hydraulics.py`.
  Explicit Euler with 8 sub-steps per tick. All shaft power becomes fluid heat; the HX rejects it into the
  engine-bound fuel (C_min = Wf cp), so low fuel flow -> hotter fluid.
- **Fuel** [DIRECT tank names, 3,060 L, drop tanks, zoom-climb event; ASSUMPTION A-W1.4-12...15, 17]: see
  `fuel.py`. **AD-42: M09 owns the true quantities, transfer, feed, burn, fuel as a heat sink and the tank
  geometry (`M09/tanks.csv`, incl. probe stations for M12); the gauge and the low-fuel warning are M12's.** The
  true-quantity half of the zoom-climb event is M09's: the F1A forward pick-up uncovers at high aft surface slope
  and low F1A contents, transfer stalls and max-AB burn drains F1/F2. The F1A pick-up station was **calibrated
  to the DIRECT anchor** (feed group below 600 kg within 45 s only for > 40 deg, max AB, < ~1,200 kg, pre-mod).
  **PROXY A-W1.4-15:** one pitch-plane free surface with one slosh mode for all tanks (roll-plane tilt absent).
- **Electrical** [DIRECT 5 kW backup, 45 Ah/50 A/30 Ah, TRU 90 %; TRANSFER MIL-STD-704F; ASSUMPTION
  A-W1.4-18...22]: source selection with <= 50 ms transfer interruptions; essential bus shed on the battery alone.
- **ECS** [DIRECT-part PHX rating, venturi; TRANSFER HAL bleed range, schedule, rates; ASSUMPTION A-W1.4-23...25]:
  **PROXY A-W1.4-24:** the bootstrap ACM is a single turbine expansion.
- **JFS** [DIRECT 110 kW, 410 N m, Leh/CAG anchors; TRANSFER T-50 cut-out 55 % N2; ASSUMPTION A-W1.4-26/27]:
  M1/M2 differences (cold drag, start schedule, oil use) **calibrated to the CAG/HAL anchors**. JFS rated speed
  60,000 rpm is an ASSUMPTION (not public) that M12/M13 need as the EU reference of `SPS.JFS.SPEED`.
- **Brakes/tyres/chute** [DIRECT 3R/4S, RTO points, chute limits; TRANSFER 1,400 landings, 4-12 landings;
  ASSUMPTION A-W1.4-28...30]: heat-sink mass calibrated so a 13.5 t RTO at 90 % wear stays below 1,000 degC.
  AD-48.6: the accrual of a sortie goes to M10 at sortie end (`sortie_wear`), which holds the wear between
  sorties; M10's usage-mode surrogate is calibrated to M09's reference landing (A-W2.1c-5).
- **Fire** [DIRECT bottle; ASSUMPTION A-W1.4-31]: physical detector loop; missed/false alarms arise from
  ventilation and loop faults; imperfect-BIT statistics are M14's.

## Validation criteria (W1.4 acceptance -> tests)

| ID | Tests |
|---|---|
| A1 balances | `tests/integration/test_utilities_module.py::test_a1_balances_close_over_a_minimal_sortie`; `test_utilities_hydraulics.py::test_fluid_volume_balance_closes`; `test_utilities_fuel.py::test_transfer_sequence_and_mass_conservation`; `test_utilities_electrical.py::test_battery_charge_balance_and_charging`; `test_utilities_landing.py::test_rto_test_points_at_50_70_90_wear`; `tests/property/test_utilities_property.py::test_fuel_mass_is_conserved` |
| A2 coupling signs | `tests/integration/test_utilities_coupling.py` (35 edges incl. all 13 report §3 rows; negative control of the checker) |
| A3 ADA points | `test_utilities_jfs.py` (cold/altitude anchors), `test_utilities_landing.py::test_rto_test_points_at_50_70_90_wear`, `test_utilities_fuel.py::test_f1a_pickup_stall_boundary` (true quantities; the gauge artefact is M12's, AD-42) |
| A4 electrical | `test_utilities_electrical.py::test_spool_down_transfer_within_50ms`, `::test_704f_classification_band_edges` |
| A5 kernels | `tests/integration/test_utilities_kernel.py` (compiled == py_func and == NUMBA_DISABLE_JIT bitwise, chunking, 12 complex-step derivatives), `tests/unit/test_utilities_kernels.py` (leaves), `tests/integration/test_utilities_module.py` (step == block through the scheduler, validation mode), `tests/fork/test_utilities_snapshot.py` (snapshot round-trip, CRN) |

## Known limitations

- The ground model, wheel dynamics, anti-skid/brake-management software and brake torque are M06's; M09 consumes
  `af.brake_energy_rate` and `af.wheel_speed`. The brake-software event therefore enters through M06.
- Gear retraction/extension and NWS hydraulic demand are not modelled (no port); FCS actuator demand is.
- No catalogued ports exist yet for: filter dP, tank fuel temperature, JFS speed/EGT/oil, AMAGB oil temperature,
  generator V/f/I, fire states. (The chute state is `util.chute_state` since W2.1c, AD-47.) `truth_view()` exposes them; see the W1.4 report for the proposed
  catalogue additions.
- Fuel inertia treats fuel as rigid level-surface boxes (no slosh in the inertia, A-W1.4-17).
- **Numba cache:** `cache=True` keys a cached function on its own source file only. After editing a leaf module
  (e.g. `jfs.py`), delete `src/phalanx/utilities/__pycache__/*.nb*` or the fused kernel can run a stale leaf.
  Fresh checkouts and CI are unaffected.
- Performance (this machine, darwin-arm64): ~1.8 us/step kernel only, ~2.0 us/step including input packing
  (block of 24,000 ticks, best of 3), for 1 and 2 engines.
