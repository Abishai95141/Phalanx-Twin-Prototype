# `phalanx.integration`: the truth loop of one aircraft (W2.1a integration core)

Wires the merged truth-layer modules (M02-M14) into one deterministic telemetry-mode `System` per sortie, built
**from the published `ports.py` bindings** (never hand-wired), runs its continuous segment as one compiled fused
loop that is bitwise equal to the per-step scheduler path, checks every dispatched cross-module event against the
catalogue, and drives a sortie with the M13 recorder and the M14 feed.

Binding sources: architecture §4, §5 (I1-I8), §7, §8, AD-22, AD-35…AD-53; `docs/build_briefs/W2.1_truth_loop.md`
(W2.1a part); `W1_interfaces.md`; `configs/interfaces/w1_ports.yaml`, `w1_events.yaml`; E1 verifier report §4-§6.

## Files and public API

| File | Contents |
|---|---|
| `wiring.py` | `connections(modules, bindings, prefix_of, lane_ports, *, m_id, exceptions, boundary)` -> core `Connection`s from bindings; `BACK_EDGES` (documented one-frame delays); `tracked_exceptions(config)` |
| `system.py` | `SortieSpec`, `build_sortie_system(spec) -> SortieSystem`, `telemetry_window(plan, start_phase)`, `SortieConfig` (per-tail configuration in the config hash), `BoundaryHold` (PROXY source for a tracked missing producer), `canonical_param_set(module)` |
| `initial.py` | post-start initial conditions the modules cannot take yet: `engine_post_start_trim` (M07+M08 closed-loop idle trim), `pilot_at_idle` (M04) |
| `fused.py` | `TruthLoopGroup`: the core `FusedGroup` of the continuous loop (one `@njit(cache=False)` pass calling the modules' kernels) |
| `validate.py` | `EventValidator`, `ValidatingEventQueue`, `validating(world, validator)`; `INTERNAL_PROTOCOLS`, `TRACKED` |
| `sortie.py` | `SortieRunner(ss, *, chunk_steps, cir_channels, feed_monitor, record, validate_events, keep_cir)`: `begin`, `run`, `run_to_end`, `close`, `snapshot`/`restore` (composite), `realised_usage`, `observed_counters`; `SortieAborted` |
| `plans.py` | `flying_sorties(fleet, start, days, *, scenario, root)`, `gate_sorties()` (deterministic samples) |
| `realised_usage.py` | `realised_fleet_stats(fleet, start, days, *, scenario, root, max_sorties) -> FleetStats` (the E1-MF entry point), `ObservedUsageUnavailable` |
| `flights.py` | `fly(plan) -> Flight` (one whole sortie with validator, invariants, recorder and M14 feed; cached per process, shared by the slow A5/A6/A10 checks), `diverse_sorties(n)` (first sortie of each mission type) |
| `manifest.py` | `sortie_manifest(runner, st, *, t_ingest, provenance, run_manifest, ...)` -> the validated one-row `sortie.manifest` table (contract v0; the topic had no producer); `SortieRunner.manifest(st)`, and `run_to_end` emits it into `SortieResult.manifest` |
| `perf.py` | `measure(ss) -> PerfTable` (A9: per-module per-step path, in-loop kernels, fused loop, `System.run`, runner) |

```python
from phalanx.core.numba_cache import configure_numba_cache

configure_numba_cache()  # run entry points: before any kernel import
from phalanx.integration.plans import gate_sorties
from phalanx.integration.system import SortieSpec, build_sortie_system
from phalanx.integration.sortie import SortieRunner

ss = build_sortie_system(SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5))
run = SortieRunner(ss, validate_events=True)  # validation on in tests, off in production
st = run.begin()
st, chunks = run.run(st, 60 * 240)  # 60 s from post-start idle, 1 s chunks
snap = run.snapshot(st)  # composite: world + recorder + realised usage
```

## The System (deliverable 1)

- **Order** (architecture §8, with PD-W2.1a-1): event-only modules first (M02 scenario, M10 health, M11 faults,
  M14 monitor, boundary holds, sortie config), then `env (M03) -> pilot (M04) -> fadec (M08) -> eng (M07) -> af
  (M06) -> util (M09) -> sens (M12) -> acq_fadec, acq_dfcc (M13) -> fcs (M05) -> avio (M12 avionics)` (the
  fused group). The avionics extension (AD-51, W2.2: INS/GPS, AHRS, ADC, radar altimeter, SMS) closes the loop
  since M08 reads the ADC's P0 altitude signal one frame late (W2.2 f1b3bc9, back-edge `("avio", "fadec")`):
  the fused group runs the ADC in its compiled loop and the module's own block step after it, and checks that
  both give the same P0 and ADC state bit for bit. The ADC starts at the field static pressure
  (`initial.adc_at_field`), so M08's first frame reads the field P0.
- **Sortie lifecycle (AD-48.2, W2.1c; A-W2.1-9):** M02 runs with M04 as its segment source: M04 reports each
  flown segment change as `pilot.segment` (the take-off ends at the gear-up, the landing roll starts at the
  confirmed touchdown, never on the plan clock), and M02 sets its phase port from it, sends `ops.takeoff` to
  M10/M11/M14 when the take-off segment is left and `ops.sortie_done` to M11/M14 at the end of the flown plan
  (engine cut-off); the runner injects only M14's power-up hook at the window start.
- **PD-W2.1a-1 (proposed decision; conflict with architecture §8 reported):** M05 frames at step k on the sample
  of `[t_k, t_k+1)` and reads it from its lane input in the same step (`fcs/ports.py`: "a frame falls in exactly
  the steps where M13 delivers a sample"). Behind a delayed lane back-edge (FCS before the lanes, §8 order) it
  reads the previous step's empty buffer: its voted signals are zero (measured;
  `test_architecture_order_reads_empty_dfcc_lanes`). So the DFCC runs after its lanes, and its outputs reach the
  plant through documented one-frame delays (`fcs -> af/util/sens`). Alternative: M05 adopts M08's lane
  back-edge contract (frames of `[t_k-1, t_k)` at step k), which restores the §8 order (W2.1c owns M05).
- **Back-edges**: every delayed connection carries its documented reason from `BACK_EDGES`; an undocumented one
  fails the build; every documented one is used (tested).
- **Identity and hash (AD-48.8):** System identity (scenario, tail, sortie = plan RNG key). Serials, per-tail
  configuration, the telemetry window and the post-start initial conditions are the `SortieConfig` ParamSet.
- **Telemetry window (AD-46):** from the first GROUND_IDLE instant; pre-window history is the initial condition
  (fuel loaded, engine and pilot at post-start idle, aircraft at M06's static equilibrium on its gear).
- **Tracked exceptions:** none since the W2.2 merge (c325285): the FADEC reads M13's `lane.ENG.AB_LIT` (M12 UV
  flame detector) from the bindings; a future tracked exception would get a labelled `BoundaryHold` (PROXY
  A-W2.1-1, closed). M11 effect targets whose consumer has no handler yet
  (`eng/fadec/af.fault_inject`, AD-48.4) are left unwired and tracked (`UNHANDLED_FAULT_TARGETS`, stale-checked).

## The fused truth loop (deliverable 2)

`TruthLoopGroup` covers all eleven continuous members, including the in-loop M12/M13 lane path (E1 F2) and
the avionics ADC's P0. Per truth
step it runs, in order, each module's own compiled kernel with `L = 1`, exactly the calls the per-step path
makes; a signal bus carries the values consumed inside the loop (delayed edges read its start-of-step copy).
Kernel input layouts and output maps are **derived by probing the modules' own packing and unpacking code**
with id-valued arrays; keyed noise and clock schedules come from the modules' own methods per block. M08's
fault/caution events are emitted as `Fadec.step` emits them. Bitwise equality with the per-step path is the
acceptance test (A4). `cache=False` (carry-forward).

## Runtime event validator (deliverable 3)

Every event the scheduler dispatches between two modules must use a catalogued kind with the catalogued producer
and consumer and every catalogued key as a plain top-level key (AD-48.1); documented package-internal protocols
(W1.5 `health.*`/`faults.*`/`monitor.*`) and tracked uncatalogued kinds (`scenario.sortie_plan`, W2.1c AD-49)
are explicit, stale-checked lists. Hooked through the world's event queue: the config hash and snapshots are
unchanged; on in tests, off in production.

## Recorder placement (AD-42 provisional; proposed decision PD-W2.1a-2)

The M13 recorder stays **outside the scheduler**: `SortieRunner` feeds it chunk-wise from the M12 trace (and the
owning modules' `RECORDED` ports), so it never enters the hot loop. Its state cannot be derived from the World
(AR(1), freeze, deadband and interval-counting states of the non-lane channels depend on the signal history:
shown by the negative control in `tests/fork/test_integration_sortie.py`). A mid-sortie snapshot is therefore
the runner's composite snapshot (world + recorder state + realised-usage state + cursor) at a chunk boundary;
restore -> continue is bitwise equal to the uninterrupted run. **M22 must snapshot telemetry sorties through the
runner.** The M14 CIR feed is a `monitor.observe` event at each chunk end (1 s: the ECMS processing frame,
A-W2.1-4), pushed to the world queue, so it is part of the world snapshot.

## Assumptions and PROXY items

A-W2.1-1 … A-W2.1-10 in `docs/assumptions.md` (section "W2.1a Integration core").

## Validation (acceptance -> tests)

| ID | Test |
|---|---|
| Deliverable 1 | `tests/integration/test_integration_system.py` |
| A1 | `tests/fork/test_integration_sortie.py` (in-process, fresh process, composite snapshot, CRN audit, validation mode) |
| A2 | `tests/integration/test_integration_balances.py` |
| A3 | `tests/integration/test_integration_convergence.py` |
| A4 | `tests/integration/test_integration_fused.py` |
| A5 | `tests/integration/test_integration_validate.py` |
| A6 | `tests/integration/test_integration_smoke.py` |
| A7 | `tests/integration/test_integration_recorded_lanes.py` |
| A8 | `tests/integration/test_interface_conformance.py`, `tests/integration/test_event_protocol.py` (zero skips) |
| A9 | `tests/integration/test_integration_perf.py`, `phalanx.integration.perf` |
| A10 | `tests/statistical/test_integration_behaviour_glance.py` (development glance, not a gate) |
| `sortie.manifest` | `tests/integration/test_integration_manifest.py` (schema-valid, one per sortie, linkage with `param.samples` and `events.*`, identity) |

## Step-halving result (A3)

Run-up segment (idle to the run-up power, 3 s, n = 1; MIL before the A-W2.1-8 run-up change): the 240 Hz truth-step error of every M06, M07 and M09 output is below
one recorder count of the channel that records it (1e-3 of peak for unrecorded ports) and falls when the step
halves, **except M07 N1, T5 and thrust** (1.16 and 2.87 counts, 1.34x tolerance): M07's fuel transport-delay
line holds the metered flow once per tick, a first-order staircase; without the delay line the engine errors
are 3-4 orders smaller. Reported to W2.1b (interpolate within the tick); strict xfail. M06 kinematics differ
at 1e-8 of scale (RK4 with ground sub-steps: rounding-level, no asymptotic order).

## Behaviour glance (A10, development only, not a gate)

5 mission-type-diverse gate sorties, flown portions (13-39 % PREFLIGHT idle, 57-86 % TAXI incl. the run-up,
2-4 % TAKEOFF, about 1 % CLIMB on the runway), registered round-2 B1/B2 estimators, one engine, 4 Hz, medians:

| pair | truth | recorded | real Tail 652 | structure (Tejas mode) |
|---|---|---|---|---|
| r fast N1-N2 | 0.69 | 0.68 | 0.47 | coupled, not lockstep: holds (round-2 open loop 0.92) |
| r fast N1-EGT | 0.32 | 0.43 | 0.56 | positive: holds |
| r fast N1-FF | 0.36 | 0.58 | 0.65 | positive: holds |
| r fast N2-FF | 0.60 | 0.89 | 0.67 | positive: holds |
| lag FF->N2 (s) | +0.25 | 0.00 | -0.50 | negative (closed-loop governing): **not reproduced** |
| lag N2->N1 (s) | 0.00 | 0.00 | +0.50 | fan follows core: lag 0 at 4 Hz, not shown |
| lag FF->EGT (s) | 0.00 | +0.25 | +0.75 | positive: truth 0 (T5 is a gas temperature), recorded +0.25 |

The sample is almost all ground idle and taxi, not the airborne mix of the real medians: a structural first
look for W2.3/W2.4 only.

## Performance (A9) against the 5x real-time floor

Floor (owner scope change, coordinator AD-55; replaces the >= 50x / 83 us target): **>= 5x real time for the
whole Tejas aircraft in telemetry mode, <= 833 us per 240 Hz step for one tail**, judged on the `SortieRunner`
in process CPU time. `phalanx.integration.perf.measure`, best of 5, gate sortie 1 at post-start idle, on a CPU
shared with the other work packages (load average 11.6; measured after the W2.2 merge, which brought the
AB_LIT lane and the avionics; the earlier table at load 35 gave 409 us CPU, 10.2x):

| module | per-step path (us) | in-loop kernel (us/step) |
|---|---|---|
| env (M03) | 77 | 2.0 |
| pilot (M04) | 33 | 0.9 |
| fadec (M08) | 410 | 0.8 |
| eng (M07) | 81 | 39.4 |
| af (M06) | 59 | 18.4 |
| util (M09) | 36 | 4.6 |
| sens (M12) | 161 | 24.3 |
| acq_fadec (M13 lanes) | 362 | 1.1 |
| acq_dfcc (M13 lanes) | 1304 | 2.8 |
| fcs (M05) | 283 | 8.5 |
| **sum** | 2806 | 103 |

| path | wall us/step | CPU us/step | real-time factor (CPU) |
|---|---|---|---|
| fused compiled loop only | 120 | - | - |
| fused `step_block` (block 240) | 145 | - | - |
| `System.run`, fused | 168 | 164 | 25.4x |
| **`SortieRunner`, whole aircraft** | 208 | **199** | **20.9x (floor 5x: met)** |
| `System.run`, per-step path (no fused group) | 5474 | 5287 | 0.8x |

The floor is met with about 4x margin (2x at load 35), so no further optimisation is done (the minimal-optimisation rule of
the scope change). The fused in-loop M12/M13 lane path (E1 F2) is what makes it: the lanes alone cost about
1.7 ms per step on the per-step path, and the unfused aircraft runs at 0.8x real time. Under heavier machine
load the same measurement gave up to 2.2 ms/step wall clock (load average 49 with three of this package's
jobs running): plan batch generation with one job per core. If the floor is ever missed, the order of work
is M07 (stability-limited Heun sub-steps, ~45 % of the kernel time), M12 (trapezoid sub-steps of the
second-order elements, ~20 %), M06 ground sub-steps (~15 %), then the Python work outside the compiled loop
(M08's spurious ENG-013/023/053 toggling cuts blocks; per-block draws and lane-output assembly).

## Known limitations

- The aircraft does not yet complete a sortie (diverse gate sorties after the W2.2 merge). Fixed in W2.1a
  (A-W2.1-8/9/10): the brakes hold the run-up check (~90 % N2), the pilot rotates through M05's ground law,
  phases and `ops.takeoff` follow physical events, the climb-out is wings level below 120 m, pull-ups stop at
  30 deg, dives pull out at the bottom, path corrections unload to 0 g at most. Open: a 4 g MIL turn primitive
  overshoots its heading and departs (TJ212 at 2,200 s; M04 guidance transitions, M05/M06 departure
  resistance), and the idle-to-MIL take-off acceleration runs down on M08's acceleration schedule on TJ213,
  TJ109, TJ115 (M07/M08, W2.1b). A6 and the realised gates are strict xfails on `SortieAborted`.
- The realised usage is computed from truth in the runner and is not yet sent to M10 (M10's telemetry sortie
  stays open from `ops.takeoff`); M14's OAC counts come from `ops.sortie_done` (plan values, PROXY A-W2.1c-4).
- 10 of 23 M14 input channels have no producer or no recording path (`ENG.PLA.V`, `LG.WOW`, `NAV.RADALT`, ...).
- Performance: 20.9x real time for the whole aircraft (CPU time, one tail, load 11.6; 10.2x at load 35): the 5x
  floor is met (A9).
