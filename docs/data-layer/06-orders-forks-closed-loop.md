# 06 · Orders, forks and the closed loop

References: kit `README.md` §10, §12; `reference/architecture.md` §11; modules M21 (orders), M22 (fork), M18;
`reference/order_authority.yaml`, `reference/order_parameter_schemas.json`.

## Why this matters

The PS asks us to *improve fleet availability*, not just predict faults. In Phalanx the only way to change the
fleet's future is to **issue orders**, and the only fair way to show improvement is to **fork the world** and
compare our policy against the status quo with common random numbers. Orders + forks are how our solution
proves impact.

## Orders (`orders.commands`)

| Field | Notes |
|---|---|
| `order_id` | globally unique, issuer-chosen, idempotent (pattern `^[A-Za-z0-9][A-Za-z0-9._:-]*$`) |
| `issuer_id`, `issuer_kind` (`AGENT`/`HUMAN`), `policy_version` | who/what decided |
| `t_issued` | must **equal the session time** (no past/future issuing) |
| `t_effective` | ≥ `t_issued`; applied at the first decision epoch ≥ max(t_issued, t_effective) — **daily 08:00 IST** |
| `target_tail_no` / `target_base` / `target_lru` / `target_serial` | target |
| `action`, `parameters` (JSON object, canonical text), `priority` (`ROUTINE`/`PHU`/`MCM`/`AOG`) | what |
| `evidence` | list of `record_id`s justifying the order — **all must be ingested by `t_issued`** |

### Action vocabulary and parameters (per-action JSON-Schema enforced by the gateway)

| Action | Required parameters | Notes |
|---|---|---|
| `INSPECT` | `type` ∈ BORESCOPE / NDT / CONDITIONAL; opt. `position` | detection probability < 1 |
| `TROUBLESHOOT` | at least one of `code`, `position` | misdiagnosis possible |
| `REMOVE_REPLACE` | `position`; opt. `install_serial` | specific S/N or any serviceable |
| `WASH_SERVICE` | `type` ∈ ENGINE_WASH / OIL / HYDRAULIC / TYRES | wash = partial fouling recovery |
| `DEFER` | `job_no`, `limits`, `expiry_hours` > 0 | no deferral of grounding defects |
| `CANNIBALISE` | `job_no`, `donor_tail_no` | |
| `REQUISITION_SPARES` | `part_no`, `quantity` ≥ 1 | |
| `EXPEDITE_SPARES` | `demand_no` | |
| `TRANSFER_STOCK` | `part_no`, `quantity`, `from_base`, `to_base` | |
| `GROUND` | `reason` | fleet-wide capable (base target) |
| `RELEASE` | opt. `reason` | no release with an open grounding defect; fleet-wide capable |
| `BRING_FORWARD_SERVICING` | `servicing` ∈ SRV-L1 / SRV-L2-MINOR / SRV-L2-MAJOR / ROH | |
| `DEFER_SERVICING` | `servicing` + one of `extend_hours` / `extend_days` | **HUMAN only**, max extension 20 % |
| `ASSIGN_SORTIE` | `date` (YYYY-MM-DD), `sorties` ≥ 0; opt. `mission_type` | applies to dates not yet planned |
| `RESTRICT_USAGE` | `limit` ∈ AB / G / NONE; opt. `value`, `until_days` | |
| `EMBODY_MODIFICATION` | `mod_id` | **HUMAN only**; fleet-wide capable |
| `LOAD_SOFTWARE` | `sw_config_id`; opt. `lru` | **HUMAN only**; triggers BIT code burst; fleet-wide capable |
| `CHANGE_MONITORING_CONFIG` | one of `filter_codes_add` / `filter_codes_remove` | **HUMAN only** (F-35 nuisance filter-list practice); masked codes are still evaluated but not recorded |

Default authority for all other actions: AGENT or HUMAN. So an automated agent can inspect, troubleshoot,
replace, wash, defer, cannibalise, requisition/expedite/transfer spares, ground/release, bring forward servicing,
assign sorties and restrict usage — but **mods, software loads, monitoring-config changes and servicing deferrals
need a human issuer** (human-in-the-loop by design).

### Gateway checks, in order

1. Idempotency — known `order_id` → `DUPLICATE` no-op.
2. Contract validity of the row → `INVALID` (never enters the world).
3. `t_issued == session time`.
4. Per-action parameter schema.
5. Authority matrix.
6. **Information discipline** — every evidence `record_id` ingested by `t_issued`, else REJECTED
   ("evidence not ingested by t_issued").
7. Applied at the next decision epoch.

Then M18 checks airworthiness and resources at execution against the authoritative tech log (no release with
open grounding defect, no deferral of grounding defect, servicing extension cap, stock and donor availability).

### Lifecycle (`orders.status`)

`status_seq` 0, 1, 2…: `ACCEPTED` (or `REJECTED` + reason) → `QUEUED` → `IN_WORK` → `COMPLETED`, or `REJECTED`
at execution. `result_record_ids` link the `maint.records` the execution produced. Rejected orders are still
logged (both `orders.commands` row and status).

### Imperfect execution

Partial engine-wash recovery; inspection probability of detection; misdiagnosis (NFF/RTOK); maintenance-induced
latent defects (latency 1 flight to ~6 years); serial changes. M18 decides *what* is done; M10/M11 decide *what
it does to the hardware*.

## Reference policies (baselines to beat)

| Policy | Behaviour |
|---|---|
| `StatusQuoPolicy` | IAF-style hard-time / reactive: hard-time retirement, scheduled servicing, reactive repair, Maintenance Control cannibalisations. Reproduces the open-loop KPIs exactly |
| `ScheduledPolicy` | status quo + engine washes and borescopes at fixed flight-hour intervals |
| `ConditionBasedPolicy` | status quo + troubleshoot when a deferred BIT code recurs + borescope after repeated engine exceedances (cites triggering records as evidence) |

Thresholds are ASSUMPTION A-W1.8-22 (swept). All three observe only the contract `as_of` the epoch.

## Event sourcing and replay

A run = pure function of (root seed, config, dictionary version, order log). Replaying an order log into a fresh
session reproduces the live run bit for bit. Re-sending an `order_id` after restore is a no-op. So **our
policy's decisions are fully auditable and reproducible** given the order log.

## Snapshot and fork (M22) — the what-if API

```python
fs = ForkService(builder, m18_cfg)
snap = fs.snapshot(session)                                 # content-hashed, at a decision epoch
spec = BranchSpec(branch_id, orders=(...), policy=None, mode="oracle"|"belief"|"ensemble", member=0, belief=None)
result = fs.run(snap, spec, horizon_ns)                     # BranchResult(kpis, order_log_hash, record_digest, ...)
runs_a, runs_b, diffs = fs.what_if(snap, spec_a, spec_b, horizon_ns, replicates=n)
diffs = fs.compare(runs_a, runs_b, paired=True)             # KpiDifference(kpi, n, mean, sd, ci_low, ci_high)
```

| Mode | Meaning | Use for us |
|---|---|---|
| **Oracle** | true hidden state; privileged | scoring/evaluation only — **never** inside the system under test |
| **Belief** | hidden states resampled consistent with observations via a pluggable posterior (`BeliefPosterior`) | our solution's own posterior (e.g. particle filter on RUL) can plug in here; reference `SurvivalPosterior` is a PROXY (Weibull TTF conditioned on survival since last observed renewal) |
| **Ensemble** | different exogenous seeds | outcome distributions / risk |

- **CRN:** member m of design A and design B share one exogenous future, so paired differences cancel shared
  noise (paired variance < independent-seed variance, F-test n = 134/arm). 95 % Student-t CIs, ≥ 3 pairs.
- Snapshot contains all module states, hidden health per serial, sensor installation states, clock phases, BIT
  counters/latches, open jobs, queues, inventories, in-transit spares, pending events, RNG counters, config and
  dictionary versions, order log.
- **Forks run in usage mode** by default (fleet-years fast); telemetry-mode forks need W2 integration.
- Today the neighbours of M18/M21 in forks are a TEST FIXTURE fleet; real M02/M10/M11/M14 arrive in W2.6.

## Session API (in-process today)

```python
s = OpsSession(builder, root)
s.run_until(t_kernel_ns)         # process events; records ingested into s.obs
s.records("maint.records")       # contract rows (JSON form), validated
s.submit([order, ...])           # through the M21 gateway (evidence checked against s.obs)
snap = s.snapshot(); s2 = OpsSession.restore(builder, snap)
```

**Open interface question:** how our separate repo submits orders / requests forks across a process or network
boundary is **not specified** by the data layer. Options: (a) import `phalanx` as a library and run sessions
in-process; (b) wrap `OpsSession`/`ForkService` in a thin service. To be agreed with the data-layer team.
