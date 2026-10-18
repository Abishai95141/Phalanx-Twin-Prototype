# `phalanx.fcs`: M05 quadruplex DFCC replica and the 13 actuators (W1.2)

A behavioural replica of the Tejas digital flight-control computer (four channels, 80 Hz frame, 8 ms
computation delay, mid-value voting, Mach/altitude gain scheduling, limiters, reversionary laws, CBIT/PBIT/MBIT)
driving 13 valve-controlled hydraulic actuators loaded by the true hinge moments. The control laws see only
digitised sensor lanes and discretes; the actuators are physical devices that read plant truth.

Binding sources: architecture §6 M05, §8, AD-22, AD-36, AD-42; W1.2 brief; `W1_interfaces.md` §1-§3;
`tejas_airframe_aero_fcs.md` Q2/Q3; Kala JOAST 67(2A) 2015; Patel et al. JOAST 58(4) 2006.

## API

```python
from phalanx.fcs.module import Fcs, FcsIC, frame_schedule
from phalanx.fcs.build import fcs_param_set, build_fcs_config  # clock defaults to the M13 DFCC clock
from phalanx.fcs.ports import RECORDED, NOT_MODELLED, VOTED_SIGNALS, lane_inputs
from phalanx.fcs.design import main as design_main  # regenerate M05/gains.csv, fixed_gains.csv

fcs = Fcs.from_registry("fcs", FcsIC(surf=trim_surfaces, alpha=a, mach=m, hp=h, on_ground=False))
```

Kernel: `fcs_kernel(f, i, p, tab, u[L, N_U], fr[L], off[L], dt, tf, n_sub_act, crit_mask)`; `frame_schedule`
supplies `fr` (DFCC sample in this step) and `off` (steps until the command applies) from the shared clock in
exact integer arithmetic. Compiled == reference bitwise (also under `NUMBA_DISABLE_JIT=1`).

## Ports (`ports.py`, prefix `fcs`)

- **Lanes** (88 inputs): `lane_port(cid)` bound to `lane.<channel_id>` (M13 in-loop lanes, SI, sample buffers
  of capacity 1 on the DFCC clock, which each lane port declares: `ports.dfcc_clock()`, W2.1c): RSA p/q/r, ASA Nz/Ny, AoA vanes L/R, AoSS vane, Ps, Pt (A-D), stick pitch,
  stick roll, pedal (A-D), surface positions (A-D elevons and rudder, A-B slats and airbrakes; airbrake stroke
  in m). `AD.TAT` is the only DFCC lane not consumed.
- **Discretes / plant:** `af.wow (3,)` (proximity switches; stuck faults by `fcs.wow_fault`), `pilot.gear_cmd`,
  `pilot.airbrake_cmd`, and for the actuators `af.alpha/beta/qbar`, `util.hyd_dp_avail (2,)`,
  `health.actuator (13,)`.
- **Catalogue outputs:** `surf_pos`, `surf_rate`, `hyd_flow_demand (2,)`, `law_state`, `channel_status (4,)`.
- **Recorded computed channels** (`RECORDED`, 48 ports `rec_<channel id>`, AD-42; held at the last frame):
  voted `.V` positions, inceptors, `FCS.RSA.P/R.V`, `FCS.ASA.NY.V`, `FCS.VOTED.Q/NZ/DE`, elevon and rudder
  `.CMD`, `FCS.MODE.LAW/FLAGS`, `FCS.CH.STATUS.A-D`, 13 `FCS.ACT.BIT.*`, `FCS.AIRDATA_MISTRACK`,
  `AV.LRU.BIT.DFCC`. Words are int64, dimensionless.
- **Not modelled** (`NOT_MODELLED`, with reasons): `FCS.KALMAN_ATT.PITCH/ROLL`, `FCS.BIT.LOG`,
  `AV.RT.STATUS.DFCC`, `AV.LRU.HEALTH.DFCC.{LINK,PORT,MEMORY}`, `AV.SW_CONFIG.DFCC`.

Surface order of every 13-vector: elevon LO, LI, RI, RO; rudder; slats OB_L, MB_L, IB_L, IB_R, MB_R, OB_R;
airbrake L, R.

## Model

- **Timing:** frames at the DFCC acquisition-clock instants (`acquisition_clock("DFCC", 80)`; on the default
  clock, truth steps k ≡ 0 mod 3); commands apply at the first truth frame at or after t_sample + 8 ms.
- **Redundancy:** channels FAILED/DROPOUT/CCDL_FAIL contribute no lanes; mid-value select per signal; mistrack
  persistence fails a lane (latched until `fcs.reset`); two-lane disagreement loses the signal; L/R vane
  mistrack excludes both vanes → air-data loss → fixed-gain reversion (latched). Failed position lanes show as
  `LVDT_SUM_FAIL` in `FCS.ACT.BIT`.
- **Laws:** pitch PI on a q/Nz-blended error (q below M0.90, Nz above M1.00), Nz fed back at the ASA station
  (1 m ahead of the CG reference: M12 must place the ASA there), gains bilinear in Mach × pressure altitude;
  limiters clip the command (V-based g limit, AoA allowance with lead and Mach-scheduled time constant);
  stability-axis roll-rate PI; yaw: β + washed-out stability-axis yaw rate + ARI + pedal; slats on α and Mach;
  open-loop airbrakes; GROUND law (direct links) on persistent main-gear WoW with no airspeed interlock by
  default (the documented false-WoW cascade); spin mode; fixed-gain reversion with gear-dependent gains.
- **BIT:** 23 SYNTHETIC subsystems per channel; CBIT persistence and latching; critical faults drop the channel;
  PBIT/MBIT timed state machines on the ground; servo-coil and jam faults by `fcs.actuator_fault`.
- **Actuators:** 9 Hz / ζ 0.7 servo, rate ∝ √(ΔP_avail − P_load) per active section, Q = A·ẋ + leakage, jam
  and hydraulic-loss freeze, RK4 with 2 sub-steps; complex-step safe.
- **Gain design** (`design.py`, `linear.py`): pole placement on the trimmed M06 short period, candidate poles
  scored on the lifted 80 Hz loop (delay, servo, RSA 50 Hz / ASA 100 Hz). 122/144 grid points feasible; GM
  7.3-16.5 dB (median 10.9), PM 41-101° (median 62.9).

Parameters: `configs/tejas/params/M05.yaml` + `M05/*.csv`; assumptions A-W1.2-20…30 in `docs/assumptions.md`.
PROXY (A-W1.2-29): no β̇/inertial-coupling feed-forward, no Kalman attitude, no notch filters, no
autopilot/ALSR, PBIT/MBIT do not move surfaces, no hydraulic pressure-switch BIT bits, TAT unused.

## Validation

| Acceptance | Tests |
|---|---|
| A3 margins | `tests/golden/test_fcs_margins.py` (every designed point ≥ 6 dB / 35°, recomputed from the committed tables; medians in the 9-17 dB / 58-68° target; all-points target = strict xfail, W2.3) |
| A4 laws, limiters, faults | `tests/integration/test_fcs_closed_loop.py` (trim hold, steps, AoA/g limiters, lane hard-over, false-WoW cascade + interlock control, hydraulic loss, reversion, 3-2-1-1 without rate saturation), `test_fcs_voting.py`, `test_fcs_bit.py`, `test_fcs_laws.py` |
| A5 actuators | `tests/property/test_fcs_actuator_property.py` (√ law, Q = A·ẋ), `tests/unit/test_fcs_actuators.py`, `tests/integration/test_fcs_actuator_loads.py` |
| A6 determinism | `tests/integration/test_fcs_module.py` (step == block, compiled == reference incl. `NUMBA_DISABLE_JIT=1`, mid-frame snapshot), complex step in `test_fcs_actuators.py` |
| Interfaces | `tests/integration/test_fcs_interfaces.py` (clock agreement with M13 sampling, delay, RECORDED partition, WoW faults), `tests/integration/test_interface_conformance.py` |
| Design drift | `tests/integration/test_fcs_design_drift.py` (committed gains = design output at 3 points + fixed set) |

Regenerate the gains after any change to the M06 aero, mass properties or M05 design settings (~8 min):
`python -I -c "import sys; sys.path.insert(0, 'src'); from phalanx.fcs.design import main; main(['configs/tejas/params'])"`.
