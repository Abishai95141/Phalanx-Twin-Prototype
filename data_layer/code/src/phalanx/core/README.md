# `phalanx.core`: the kernel (W0.2)

The 240 Hz truth scheduler, rate groups, LRU clock domains, the event queue, the module contract with
ports and units, identity-keyed RNG streams, explicit state and its canonical encoding, world snapshots and
the run manifest. Every Wave 1–3 module plugs into these interfaces.

Binding sources: `docs/architecture.md` §5 (I1–I8, §5.5 contract), §8 (time, rate groups, clock domains),
§11.2 (snapshot/fork), §13 (two tiers, compiled hot loops), §15 (RNG, manifest, test tiers), AD-10, AD-11,
AD-15, AD-16, AD-17, AD-22 (Numba), AD-35, AD-36, AD-37. Evidence: report §7 ("separate the truth integrator from LRU
sampling"), §8 (clock-domain slip), §14 (RNG streams, CRN, forks, manifests).

## Files

| File | Contents |
|---|---|
| `time.py` | AD-35 int64-ns time base, truth grid, interpolation weights, `RateGroup`, `ClockDomain` |
| `rng.py` | `KeyPath`, `StreamDecl`, `StreamRegistry`, `RngService`, `Stream`, `Keys`, draw ledger, `crn_audit` |
| `state.py` | `Field`, `StateSchema`, canonical tree encoding, digests, `freeze` |
| `units.py` | pint SI checks (`parse_unit`, `units_compatible`, `strip_quantity`) |
| `module.py` | `Port`, `EvidenceTag`, `Param`, `ParamSet`, `Module` protocol, `ModuleBase` |
| `events.py` | `Event`, `EventQueue` |
| `scheduler.py` | `Connection`, `FusedGroup`, `System`, `World`, `Trace` |
| `snapshot.py` | `snapshot`, `read_snapshot`, `restore`, `snapshot_id` |
| `manifest.py` | `RunManifest`, `build_manifest`, `read_git_commit`, `write_manifest` |
| `canonical.py` | canonical JSON, blake2b with per-family personalisation |
| `sampling.py` | clock-domain **sample buffers**: `max_samples_per_step`, `sample_ports`, `samples_for_steps` |
| `layout.py` | AD-22 flat vectors: `StateLayout` (float64 `f` + int64 `i` with names), `ParamLayout` |
| `example_kernel.py` | **AD-22 worked example** (reference, not physics): `@njit` kernel over flat vectors inside `ModuleBase` |
| `toy.py` | **kernel test fixture, not a physics deliverable** (spring–damper truth, drifting-clock sensor, PD loop, monitor/counter events, slow sampler, event-only usage system); also the worked example of the contract |

## Public API (what W1 modules code against)

```python
# time.py
NS_PER_S = 1_000_000_000; TRUTH_HZ = 240; TRUTH_DT_S = 1/240
truth_step_time_ns(k: int) -> int                      # (k*10**9)//240, exact
truth_step_times_ns(k: ndarray[int64]) -> ndarray[int64]
latest_truth_step(t_ns: int) -> int                    # max{k : t_k <= t}
truth_interp(t_ns: int) -> tuple[int, Fraction]        # (k, w), value = x_k + w (x_{k+1} - x_k)
truth_interp_weights(t_ns: ndarray) -> tuple[ndarray, ndarray]
RateGroup(divisor: int = 1, phase: int = 0)            # .hz .dt_s .runs_at(k) .ticks(k0, k1); RG_240, RG_80, ...
ClockDomain(name, f_nom_hz, offset_ppm=0, phase_ns=0)  # exact rationals (int | str | Fraction | float via repr)
  .sample_time_ns(n) -> int; .sample_times_ns(n0, count) -> ndarray[int64]
  .first_index_at_or_after(t) -> int; .index_at_or_before(t) -> int; .indices_in(t0, t1) -> (n0, n1)

# rng.py
KeyPath.of(**components) -> KeyPath                    # kinds: scenario base tail serial date sortie job order
                                                       #        subsystem sensor component event (this order)
StreamDecl(subsystem, component, identity: tuple[str, ...], variate=Variate.NORMAL, block_size=4096, owner, description)
StreamRegistry(decls).declare(decl) / .lookup(subsystem, component) / .table() / .digest()
RngService(root: int (128-bit), registry, *, ledger=None)
  .stream(path) -> Stream; .generator(path, index=0) -> np.random.Generator   # "stream(key_path) -> Generator"
  .block(path, b) -> ndarray; .draws(path, start, count) -> ndarray; .scope(identity) -> Keys
Stream.draws(start, count) / .block(b) / .take(position, count) -> (ndarray, new_position) / .generator(index)
Keys.stream(subsystem, component, **extra_identity) -> Stream    # projects identity onto the decl's kinds
DrawLedger(); crn_audit(ledger_a, ledger_b) -> CrnReport(.ok, .identical, .consumption_differs, ...)
generator_state_tree(gen) / generator_from_state_tree(tree)       # sequential Generator state, if ever needed

# state.py
Field(name, dtype, shape)            # shape entries int or None (variable)
StateSchema(name, version, fields)   # .validate(tree) .make(**values) .names
encode_tree(tree, *, kind, name, version) -> bytes; decode_tree(bytes, kind=None) -> DecodedTree
tree_digest(tree) -> str; trees_equal(a, b) -> bool; freeze(tree) -> read-only views

# module.py
Port(name, unit, dtype="<f8", shape=(), rate=None)     # coherent SI; "ns" only on integer ports
Param(value, unit, tag, source, proxy=False, note="")  # tag: DIRECT[-unnamed|-part], TRANSFER: <donor>, MEASURED, ASSUMPTION
ParamSet(name, {name: Param}) -> .hash .value(k) .replace(**values) .proxies()
class ModuleBase:                                      # implements the protocol boilerplate
    version: str; ports_in: tuple[Port, ...]; ports_out: tuple[Port, ...]
    rate: RateGroup | None (None = event-only); state_schema: StateSchema
    streams: tuple[StreamDecl, ...]; emits_events: bool = False
    step_block_emits_events: bool = False                # step_block returns events too (block mode)
    def __init__(self, id: str, params: ParamSet, *, identity: Mapping[str, str | int] | None = None)
    def init(self, params, keys) -> State
    def initial_outputs(self, state) -> Outputs          # outputs at t_0 (and after events, for event-only modules)
    def step(self, state, inputs, t: int, dt: float) -> (State, Outputs) | (State, Outputs, list[Event])
    def step_block(self, state, inputs, t: ndarray[int64], dt: float)
        -> (State, Outputs) | (State, Outputs, list[(t_emit_ns, Event)])                 # optional
    def on_event(self, state, event, t: int) -> (State, list[Event])
    def get_state(self, state) -> bytes; def set_state(self, data) -> State
    def stream(self, component, **extra) -> Stream       # a declared stream for this module's identity

# events.py
Event(t_ns, kind, target, payload={}, priority=0, seq=-1, source="external")   # order key (t_ns, priority, seq)
EventQueue().push(e) -> stamped e; .pop(); .pop_due(t); .next_time(); .get_state(); EventQueue.from_state(b)

# scheduler.py
Connection(src="mod.port", dst="mod.port", delayed=False, note="")
System(modules, connections, *, rng, identity: KeyPath, fused=(), dict_hash="", validate=False,
       purity_check=False, block_len=1024, event_jump=True)     # .event_only: no continuous module
  .start() -> World; .run(world, n, *, mode="block"|"step", record=()) -> (World, Trace)
  .inject(world, events) -> World; .config_hash; .describe(); .execution(); .output_ports()
FusedGroup protocol: id, members, [emits_events], step_block(states, ext_inputs, held0, k, dt_truth)
    -> (states, outputs) | (states, outputs, list[(t_emit_ns, member_id, Event)])

# sampling.py (clock-domain sample buffers) / layout.py (AD-22 flat vectors)
max_samples_per_step(domain, divisor=1) -> int
sample_ports(name, unit, capacity, domain) -> (Port name, name_t, name_n, name_first)
samples_for_steps(domain, n_next, t_start[], t_end[]) -> StepSamples(.times .step .slot .count
    .first_of_step .next_index; .pack(values, capacity) -> (values[n, cap], times[n, cap]))
StateLayout(name, version, floats, ints) -> .schema .pack(**values) .unpack(state) .f/.i.check(**constants)
ParamLayout(names).vector(params) -> read-only float64[n]

# snapshot.py / manifest.py
snapshot(system, world, *, parent="") -> bytes; snapshot_id(bytes) -> str
read_snapshot(bytes) -> SnapshotInfo; restore(system, bytes, *, strict=True) -> World
build_manifest(system, *, git_commit=None | repo=..., backend, order_log_hash, data_hashes) -> RunManifest

# numba_cache.py (stale-cache guard)
configure_numba_cache(base=None) -> Path   # call first in a run entry point, before importing kernels
numba_cache_dir(base=None) -> Path; source_digest() -> str; numba_cache_status() -> dict (manifest)
```

## Semantics a module author must know

1. **Time.** All times are int64 ns. Step `k` is at `t_k = (k·10⁹)//240`; physics uses `dt = divisor/240` s.
   `step(state, inputs, t, dt)` receives `t = t_k` of the step being taken; outputs are the values at the
   *end* of the step (`t_{k+1}`).
2. **Gauss–Seidel order** is the list order passed to `System`. An input from an earlier module sees its
   output from this step. A `delayed` connection sees the producer's output as it was at the start of the
   step (one-frame delay). Back-edges and self-edges must be delayed **and documented** (`note`), or the
   build fails. A forward delayed edge is the way to get "the previous frame" (the toy sensor uses one to
   interpolate between `x(t_k)` and `x(t_{k+1})`).
3. **Rate groups** run on `k % divisor == phase`; outputs are held between ticks. Rates that do not
   divide 240 Hz (1553 at 50/12.5 Hz, FADEC 50–67 Hz) are **clock domains**: the module runs at 240 Hz (or a
   divisor) and computes its own samples with `ClockDomain` and the sample-buffer pattern below.
4. **Randomness** only through declared streams: `self.stream("component", **identity)`. Address draws by
   an **absolute index stored in state** (a tick counter, a sample number, an event/job number), never by
   "how many have I drawn so far" in a hidden object. Index draws by things that do not depend on decisions
   (time, sample number, identity), or the CRN audit will (correctly) fail.
5. **State** is a flat dict of NumPy arrays matching `state_schema`; never mutate inputs or state in
   place (validation mode passes read-only views). Everything the next step needs must be in state;
   `get_state`/`set_state` must round-trip bit-for-bit.
6. **`step_block` must equal repeated `step` bitwise.** Use one arithmetic path for both (a shared scalar
   function or a compiled kernel called by both). Pitfalls measured on this machine (darwin-arm64,
   NumPy 2.5.4): `math.tanh` and `np.tanh` differ in 921 of 5,000 values; `np.sum` (pairwise) differs from
   sequential addition while `np.add.accumulate` matches it. On other platforms SIMD transcendental kernels
   can differ between array and scalar paths, so test, don't assume.
7. **Events.** At the start of step `k` every queued event with `t_ns <= t_k` is dispatched in
   `(t_ns, priority, seq)` order; events at exactly `t_k` produced by handlers dispatch in the same phase.
   Events returned by `step` (only if `emits_events = True`) must not be in the past and dispatch at the
   first later step with `t_k >= t_ns`. Event-emitting modules can run as blocks: see "Events from
   step_block" below. Event-only modules (`rate=None`) refresh their outputs from
   `initial_outputs(state)` after each event. Dispatch is quantised to the truth frame (≤ 4.17 ms); the
   event's own `t_ns` stays exact.
8. **Orders** enter as events via `System.inject` (logged in `world.order_log`, hashed into snapshots and
   manifests). M21 builds on this.
9. **No NaN, ever, at a port.** Validation mode rejects NaN/inf at every port boundary (step, step_block,
   fused groups, initial outputs). "No value yet" is expressed by an explicit count or validity port, never by
   NaN (architecture §12: sentinels and validity, not NaN).
10. **Validation mode** (`validate=True, purity_check=True`) passes read-only state and inputs, checks
   schemas, port dtype/shape/units/finiteness, and calls every `step`, `step_block`, fused `step_block` and
   `on_event` twice to expose hidden state. The full toy system is tested bit-identical to production mode
   in step and block mode (`tests/integration/test_core_validation_mode.py`). Production mode makes none of
   these calls.

## Events from `step_block` (block-mode event emission)

A module with `emits_events = True` runs per step unless it also sets `step_block_emits_events = True`. Then:

- `step_block` returns `(state, outputs, events)`, where `events` is a list of `(t_emit_ns, Event)`.
  `t_emit_ns` is the time of the tick that emitted the event; it must be one of the block's step times at
  which the module runs. `event.t_ns >= t_emit_ns`, as for `step`.
- Within one tick, list the events in exactly the order `step` returns them. The simplest way is to make
  `step` = `step_block` with L = 1 and generate events in one helper (see `ToyMonitor._tick`).
- A fused group whose members emit events declares `emits_events = True` and returns
  `(states, outputs, [(t_emit_ns, member_id, Event), ...])`.
- The scheduler orders all events of a block by (emission step, module order, list position), which is
  the per-step push order, so `seq` numbers and the `(t_ns, priority, seq)` dispatch order match stepping.
- **Cut rule.** If an emitted event's dispatch step (`max(k_emit + 1, first step with t_k >= t_ns)`) falls
  inside the block, the scheduler **cuts the block there**, whatever the target: it discards the pass,
  re-runs up to that step, dispatches, and continues. This is bitwise identical to per-step execution for
  every target — a later segment (FADEC → M14), an earlier segment the rest of the block depends on, or
  the emitting segment itself. The dispatch steps seen in the discarded pass end the following blocks
  (a hint, re-checked every time), so a stream of events costs about one discarded pass per
  `block_len` steps rather than one per event. On the test emitter (64 events in 2,400 steps), there were
  68 block passes with 3 discarded.
- Measured on the toy with `block_len=1024` (n = 24,000 steps, best of 3): a 240 Hz event-emitting monitor
  costs 11.33 µs/step per step versus 4.62 µs/step as a block (129 events), against 0.84 µs/step with no
  monitor. The toy monitor's `step_block` is a Python loop; a compiled kernel that returns transition
  flags pays only for the ticks that emit.

Tests: `tests/integration/test_core_block_events.py` covers block = per-step bitwise (including dispatch logs)
for three target placements × block lengths 1/7/64/1024 × plain/fused, a mid-block snapshot in validation
mode, and negative controls showing that without the cut the earlier-segment and same-segment cases
diverge.

## Numba cache (stale-cache guard)

Numba's `cache=True` keys a compiled function by its own file's path and timestamp. **It does not notice
changes to constants imported from other modules**: swapping two index constants in a `layout.py` without
touching the kernel file silently keeps the old compiled kernel. `tests/integration/test_core_numba_cache.py`
reproduces this as a negative control. The rule:

- **Production runs** call `phalanx.core.configure_numba_cache()` first, before importing any kernel
  module. It refuses if a cached kernel is already loaded. It sets `NUMBA_CACHE_DIR` to
  `src/phalanx/__pycache__/numba/src-<digest16>`, where the digest is blake2b over every `*.py` file in the
  package. Any source edit therefore selects a fresh directory, and identical sources share one, including
  across concurrent processes. The run manifest (v2) records `numba_cache = {source_digest, key,
  configured}`. Hashing the package takes about 10 ms. Old `src-*` directories are git-ignored and safe to
  delete.
- **Tests:** `tests/conftest.py` sets a fresh per-session `NUMBA_CACHE_DIR`
  (`.pytest_cache/numba-cache-<pid>`, removed at session end) before anything imports numba, so
  `make check` always compiles from the current sources. Worker processes spawned by tests inherit the
  session directory. Measured cost: 35.2 s of Numba compilation (54 top-level compiles) per full test
  session, against 0.1 s with a warm cache. Wall time was 351 s vs 312 s on a loaded machine. Setting
  `PHALANX_TEST_REUSE_NUMBA_CACHE=1` skips the guard, for timing comparisons only.
- Kernels take parameters as arrays (AD-22) and never bake in values from data files, so the `*.py` sources
  are the complete compile-time input.

## Emitting a variable number of samples per step (clock-domain sample buffers)

A module on its own oscillator produces 0, 1 or more samples per truth step. Ports have fixed shapes, so
use a **fixed-capacity buffer plus explicit count and index ports** (`core/sampling.py`, used by
`ToySensor`):

| Port | dtype, shape | Meaning |
|---|---|---|
| `y` | float64 `(capacity,)` | values in slots `[0, n)`; slots `>= n` hold 0 and carry no meaning |
| `y_t` | int64 ns `(capacity,)` | sample instants in slots `[0, n)` |
| `y_n` | int64 `()` | `n`, the number of valid samples this step |
| `y_first` | int64 `()` | absolute sample index of slot 0 (sample index = `y_first + slot`) |

- `capacity = max_samples_per_step(domain, divisor)`; `sample_ports("y", unit, capacity, domain)` declares
  the four ports.
- Keep `n_next` (the next absolute sample index) in state, starting at `domain.first_index_at_or_after(0)`.
- `samples_for_steps(domain, n_next, t_start, t_end)` assigns samples to steps for one step or a whole
  block with the same arithmetic, so `step` (a block of one) equals `step_block` bitwise. Store
  `next_index` back into state.
- Index per-sample noise by the absolute sample index (`stream.draws(first, count)`): the noise of sample
  `n` never depends on which truth step it fell in. M13's CIR `sample_index` is this index.
- Consumers read `[:n]` only.

## AD-22 kernel layout (worked example: `core/example_kernel.py`)

The reference module `ExampleOscillator` shows the AD-22 layout inside the normal contract:

- **State** = `{"f": float64[nf], "i": int64[ni]}` declared by `StateLayout(name, version, floats, ints)`,
  with module-level index constants (`X, V, U_CMD = 0, 1, 2`; `TICK, N_GOV = 0, 1`) checked against the
  names at import (`LAYOUT.f.check(x=X, ...)`). Snapshots, `get_state`/`set_state` and schemas are unchanged.
- **Parameters** = one read-only float64 vector from the ParamSet (`ParamLayout(names).vector(params)`,
  `P_*` constants); calibration perturbs by index. Integer configuration is passed as int arguments.
- **Kernel** = one `@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)` function
  `(f, i, p, inputs[L], noise[L], dt, ...) -> (f', i', out[L, ·])`, scalar locals, fresh copies returned,
  block length L a runtime value.
- `step_block` fetches the keyed noise block for ticks `[TICK, TICK + L)` and calls the kernel; **`step` is
  `step_block` with L = 1**, so per-step and block execution are bitwise identical by construction.
- **NumPy reference** = `_kernel.py_func` (the same source uncompiled, i.e. what `NUMBA_DISABLE_JIT=1`
  runs); `ExampleOscillator(..., compiled=False)` runs it through the scheduler. Tests show compiled ==
  reference bitwise for 2,400 ticks and for block lengths 1/7/1024.
- **Complex-step safe**: output arrays take the state dtype, no comparisons/`abs`/`min`/int casts on
  derivative-carrying values; the test computes d x / d stiffness by complex step (h = 1e-30) and matches
  central differences to 1e-6 relative (AD-34 pattern).

### Where the rate-group phase lives

Two different things are called "phase":

1. **The module's own rate group** (`rate = RateGroup(divisor, phase)`): owned by the scheduler, which runs
   the module on `k % divisor == phase` using the absolute step `k`. `k` is the world's clock and is saved in
   every snapshot header, so this phase is exact at any snapshot step **without** a copy in module state. Do
   not duplicate it in the int state: two sources of truth can disagree.
2. **An internal sub-rate inside one kernel** (a governor updated every 3rd tick inside a 240 Hz module, or
   the 80 Hz FCS inside a fused 240 Hz truth-loop kernel): the kernel does not see `k`, so its phase lives in
   the **int state** as a tick counter (`TICK % GOV_DIV` in the example). This is what W0.6 D5 measured, and
   the example's snapshot test at k = 1201 (not a multiple of 3) covers it.

So "rate-group phase lives in the int state" is right for case 2 and wrong for case 1.

### RNG state in snapshots

A snapshot stores the RNG *identity* (mapping version, root, registry digest, NumPy version). Each stream's
key path is static configuration (system identity + module identity + `StreamDecl`), so it is covered by
the config hash. Each consumer's position is an absolute draw index in its module state (`TICK`, `n_next`,
an event or job number), and block index and offset are derived from it (`b = i // B`, `offset = i % B`).
This is the same information as "key path, block index and offset" (W0.6 §14.3), stored once.

## Usage mode: event jump

If a system has no continuous module (`System.event_only`: every module has `rate=None`), block-mode `run()`
jumps from one dispatch step straight to the next instead of stepping. This is bitwise identical to stepping
(same snapshots, traces and dispatch logs; tested against the per-step interpreter and against block mode
with the jump off). Measured on the toy usage system (renewals every ~3 h, so 2,939 renewals and 6,857
dispatched events per tail-year; best of 3): **0.24 s per tail-year**, versus about 84 s at
`block_len=1024` and 1.6 s at `block_len=864,000` without the jump (30-day runs extrapolated × 365/30). That
is ≈ 500× and ≈ 10× faster. Pass `event_jump=False` to disable it. Do not record ports over fleet-years:
`Trace` rows are per step; use the dispatch log or the module states.

## RNG reproducibility contract (mapping v1)

`component → 4 uint32 words = blake2b-128("kind␟type␟value", person="phx.rngkey.v1")` (fixed width: NumPy
alone aliases `spawn_key=(2**32,)` with `(0, 1)`, shown by a test); draw unit `(path, tag, index)` →
`Generator(Philox(SeedSequence(entropy=root128, spawn_key=words + (tag, lo32, hi32))))`; block `b` = the
first `block_size` variates of unit `(path, variate_tag, b)`; draw `i` = element `i % B` of block `i // B`.
Pinned by `tests/golden/test_core_rng_golden.py`. NumPy is pinned (NEP 19 allows distribution changes in
feature releases), so `restore(strict=True)` also checks the NumPy version.

## Assumptions (tagged; registered in `docs/assumptions.md`, section W0.2)

| ID | Statement | Tag |
|---|---|---|
| A-W0.2-1 | One constant fractional frequency offset per clock domain per run (no aging, temperature drift or phase jitter) | [ASSUMPTION] (round-1 P2 [MEASURED]: within-flight Δ half-difference SD 1.46 ppm, n = 152 flights) |
| A-W0.2-2 | LRU sampling interpolates truth linearly between consecutive 240 Hz frames on the floored-ns grid | [ASSUMPTION] (report §7; verify by step-halving, W2.1) |
| A-W0.2-3 | Event dispatch is quantised to the next truth frame (≤ 4.17 ms, causal) | [ASSUMPTION] |
| A-W0.2-4 | Toy fixture parameter values are arbitrary test values, never used outside kernel tests | [ASSUMPTION] (fixture) |

No `PROXY` items: the kernel models no physics.

## Validation criteria (W0.2 acceptance → tests)

| ID | Test(s) |
|---|---|
| A1 | `tests/integration/test_core_determinism.py` (in-process, 2 fresh subprocesses) |
| A2 | `tests/property/test_core_module_state_property.py`, `tests/property/test_core_state_property.py`, `tests/unit/test_core_state.py` |
| A3 | `tests/fork/test_core_snapshot.py` (k ∈ {0, 1, 239, 1201, 2399, 2400, pending event} × 3 mode pairs; held-output negative control) |
| A4 | `tests/fork/test_core_fork_crn.py` (identical suffixes; CRN audit; state-dependent-draw negative control) |
| A5 | `tests/property/test_core_rng_property.py`; `test_adding_streams_and_consumers_leaves_existing_outputs_unchanged` |
| A6 | `tests/integration/test_core_scheduler.py::test_block_execution_equals_per_step_bitwise` (9 configs × block 1/7/1024), `test_interleaved_modes...`, `tests/integration/test_core_compiled_block.py` (Numba), `tests/integration/test_core_kernel_layout.py` (AD-22 example), `tests/integration/test_core_event_jump.py` (usage mode) |
| Block events | `tests/integration/test_core_block_events.py` |
| Numba cache guard | `tests/integration/test_core_numba_cache.py` |
| I2/I3 end to end | `tests/integration/test_core_validation_mode.py` (full toy and usage system, validation vs production, step and block) |
| A7 | `tests/unit/test_core_time.py`, `tests/property/test_core_time_property.py` |
| A8 | `tests/unit/test_core_module.py` (build-time and validation-mode mismatches; zero unit calls in production) |
| A9 | `tests/unit/test_core_events.py`, `tests/property/test_core_events_property.py`, pending-event snapshot case |
| A10 | `make check` (ruff, format, static audit, tests) |
| A11 | `tests/golden/test_core_rng_golden.py` |

## Known limitations

- **Python overhead.** Reference interpreter ≈ 40 µs/step for 3–5 toy modules (≈ 100× real time); block
  mode 1.5–13 µs/step (n = 24,000 steps, best of 3, this machine). A loop that runs through the per-step
  segment fallback is ≈ 8× slower than the same loop with a fused `step_block` (13.1 vs 1.7 µs/step). The real truth loop
  (FCS ↔ airframe ↔ engine ↔ FADEC, joined by one-frame delays) will be one segment and **needs a fused,
  compiled `step_block`** to reach the §13 telemetry target.
- An event-emitting module runs per step unless it opts into `step_block_emits_events`. Each in-block
  dispatch costs a block cut (see "Events from `step_block`").
- The event jump applies only to event-only systems; a system with any continuous module (even a 1 Hz one)
  steps through every truth frame in blocks.
- Fused groups are hand-written per loop; the kernel checks their membership and output shapes, and the
  A6-style test is the only proof of equivalence.
- The purity check (validation mode) catches hidden state that changes outputs between identical calls; it
  cannot see a hidden cache that never changes results.
- A FADEC on a 50–67 Hz clock acting inside the 240 Hz loop has its control updates resolved to truth
  frames (≤ 4.17 ms timing quantisation); DFCC 80 Hz is exact (divisor 3).
- The draw ledger keeps every validated draw in memory (validation/tests only).
- Snapshots are full copies (no copy-on-write); M22 owns forking at scale.
