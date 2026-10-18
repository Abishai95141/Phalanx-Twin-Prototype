# M22 Snapshot and fork service, operations sessions and KPIs (W1.8)

**Purpose.** Run the operations layer as a live, deterministic, closed-loop session; snapshot it at decision
epochs; fork branches with divergent order suffixes or policies; compare them with CRN-paired KPI differences
(architecture §6 M22, §11; AD-17, AD-36, AD-37, I8). Forks run in usage mode.

## Interfaces

```python
from phalanx.fork import OpsSession, ForkService, BranchSpec, SurvivalPosterior, OpsOnlyBuilder

s = OpsSession(builder, root)  # builder: a WorldBuilder (M18 + M21 + sink [+ M02/M10/M14])
s.run_until(t_kernel_ns)  # every event before t processed; records ingested into s.obs
s.records("maint.records")  # list of contract rows (JSON-document form), every batch validated
s.submit([order, ...])  # through the M21 gateway (evidence checked against s.obs)
snap = s.snapshot()  # SessionSnapshot: core snapshot bytes + record log + observations
s2 = OpsSession.restore(builder, snap)  # strict restore: bitwise continuation
```

**What-if API (signature).**

```python
fs = ForkService(builder, m18_cfg, defects_factory=None, m22=None)
snap = fs.snapshot(session)  # SessionSnapshot at t
branch = fs.fork(snap, BranchSpec(branch_id, orders=(), policy=None, mode="oracle", member=0, belief=None))
result = fs.run(
    snap, spec, horizon_ns, keep_session=False
)  # -> BranchResult(kpis, order_log_hash, record_digest, ...)
runs_a, runs_b, diffs = fs.what_if(snap, spec_a, spec_b, horizon_ns, replicates=n)
diffs = fs.compare(runs_a, runs_b, paired=True)  # -> list[KpiDifference(kpi, n, mean, sd, ci_low, ci_high)]
```

- `orders`: an order suffix (each order's `t_issued` inside the branch window); `policy`: a policy run at every
  decision epoch of the window. Both may be given.
- `mode`: `oracle` (same root, true hidden state; privileged), `ensemble` (member root
  `member_root(root, scenario, member)`, a SeedSequence spawn-key child: same state, different exogenous future),
  `belief` (hidden state resampled from observations by a pluggable posterior, then an ensemble member).
- `what_if` runs members 0..n-1 of both designs; member m of both shares one exogenous future (CRN), so the
  paired difference cancels the shared noise. Student t interval at `ci_level` (0.95), at least `min_pairs` (3)
  pairs, else an infinite interval (`configs/tejas/params/M22.yaml`, A-W1.8-21).

**KPIs** (`Kpis`, from records only, over the branch window): `mc`, `fmc`, `nmcs`, `nmcm`, `nmcd` (SCIR
occupancy from AVAILABILITY_STATE), `flying_task` (flown / planned FH), `flown_fh`, `sorties`, `aog_days`,
`cann`, `cann_rate` (per 100 sorties), `man_hours`, `cost` (relative proxy, A-W1.8-11), `in_flight_failures`.

**Belief forks.** `BeliefPosterior.apply(session, particle=k)` replaces hidden state; the hidden-state module
implements `BeliefTarget` (`belief_items`, `belief_prior`, `with_belief`). The reference `SurvivalPosterior` is a
PROXY (A-W1.8-23): Weibull time to failure conditioned on survival over the hours observed in `maint.records`
since the last observed renewal; faults unknown to maintenance are removed. It reads only the consumer
observation set and static priors (tested invariant to perturbed truth).

**Streaming additions (M19, new files only).** `streaming.ingest_index.IndexedObservationView`: an
`ObservationView` whose `ingested()` binary-searches an index of each record_id's earliest `t_ingest`; `streaming.memory_view.MemoryObservations`:
the in-memory observation set of a session (append, copy-on-write `fork`, `as_of`, `ingested`). Both agree exactly
with W0.4's `ObservationView` (property test); W0.4 behaviour is unchanged.

## Determinism, state and forkability

- Records are read from the kernel's dispatch log (`rec.<topic>` events to the sink), so record volume never grows
  module state; `RecordLog.digest` chains rows per topic (independent of batching).
- A `SessionSnapshot` holds the core snapshot bytes (module states, event queue, order log), the root, the
  record log and the observation set; its `id` hashes the core snapshot id, the record digest, t and the
  parent snapshot id (lineage).
- Randomness is identity-keyed (tail/date, serial, demand, order); a fitted part draws from its own serial's
  stream, so a branch that changes one decision leaves every other identity's draws unchanged (CRN audit).

## Validation criteria and tests

| Criterion | Tests |
|---|---|
| A5 snapshot -> restore -> continue bitwise; identical suffixes identical; different suffixes differ | `tests/fork/test_fork_snapshot.py` |
| A5 CRN audit; paired variance below independent-seed variance (one-sided F-test, n = 134 per arm, power-justified, `slow`; fast paired-CI check n = 6 in make check) | `tests/fork/test_fork_crn.py` |
| A7 round-trip of queues, inventories, in-transit spares, pending events; determinism across processes | `tests/fork/test_fork_snapshot.py`, `tests/fork/test_fork_kpis.py` |
| Fork modes and the what-if API | `tests/fork/test_fork_belief.py` |

## Known limitations

- In W1 the scenario and hidden-state neighbours are the TEST FIXTURE fleet (`tests/fork/test_fork_fixture_fleet.py`);
  real M02/M10/M11/M14 come in W2.6 through the M18 event protocol and `BeliefTarget`.
- Telemetry-mode forks (full-rate data for selected windows) are not wired here; they share state and keys with
  usage mode by construction of the kernel but need the W2 integration.
- The reference belief posterior assumes no undetected latent faults (PROXY A-W1.8-23).
