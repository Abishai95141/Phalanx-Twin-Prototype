# M21 Orders and decision interface (W1.8)

**Purpose.** The one door through which decisions enter the simulated fleet (architecture §6 M21, §11; AD-16,
I5). Orders are typed, stamped with simulation time, validated, logged in the world's order log and applied at
decision epochs, so a run is a pure function of (root seed, config, dictionary version, order log). Message or
transport timing never alters state.

## Interfaces

```python
from phalanx.orders import (
    Order,
    OrderGateway,
    SubmitResult,
    OrdersModule,
    RecordSink,
    DecisionCalendar,
    StatusQuoPolicy,
    ScheduledPolicy,
    ConditionBasedPolicy,
    PolicyContext,
    load_authority,
)
from phalanx.orders.replay import dump_order_log, load_order_log, order_log_hash, replay

order = Order(
    order_id="AIRHQ:20261014:001",
    issuer_id="AIRHQ",
    issuer_kind="HUMAN",  # or "AGENT"
    t_issued=t_now_utc_ns,
    t_effective=t_now_utc_ns,
    action="INSPECT",
    parameters={"type": "BORESCOPE"},
    target_tail_no="KH2001",
    evidence=(record_id_bytes, ...),
    priority="ROUTINE",
    policy_version=None,
)
results = session.submit([order])  # -> list[SubmitResult(order_id, verdict, reason, t_apply)]
```

**Vocabulary (§11.1; parameter schemas in `model.ACTION_SCHEMAS`, A-W1.8-19).** INSPECT, TROUBLESHOOT,
REMOVE_REPLACE, WASH_SERVICE, DEFER, CANNIBALISE, REQUISITION_SPARES, EXPEDITE_SPARES, TRANSFER_STOCK, GROUND,
RELEASE, BRING_FORWARD_SERVICING, DEFER_SERVICING, ASSIGN_SORTIE, RESTRICT_USAGE, EMBODY_MODIFICATION,
LOAD_SOFTWARE, CHANGE_MONITORING_CONFIG. Fleet-wide actions (GROUND, RELEASE, EMBODY_MODIFICATION,
LOAD_SOFTWARE, CHANGE_MONITORING_CONFIG) may target a base instead of a tail.

**Gateway checks, in order:**

1. idempotency (`OrderGateway.submit`): an `order_id` already in the world's order log or the M21 registry
   is a `DUPLICATE` no-op;
2. contract validity of the `orders.commands` row; an invalid row is `INVALID` and never enters the world;
3. `t_issued` must equal the session time;
4. per-action parameter schema;
5. authority matrix (`configs/policies/authority.yaml`, A-W1.8-18);
6. information discipline: every evidence `record_id` must be ingested by `t_issued` in the decision-maker's
   observation set (`ObservationView.ingested` semantics; the in-memory and indexed views agree with it
   exactly). This blocks look-ahead;
7. the order applies at the first decision epoch at or after `max(t_issued, t_effective)` (daily 08:00 local by
   default, `configs/tejas/params/M21.yaml`, A-W1.8-16).

Accepted and rejected orders both enter the world as `order.submit` events (so the verdict is part of the logged
order stream); `OrdersModule` publishes the `orders.commands` row and the `orders.status` lifecycle
(`status_seq` 0, 1, ...: ACCEPTED/REJECTED, then QUEUED, IN_WORK, COMPLETED or REJECTED reported by M18).
Airworthiness and resources are checked by M18 when it executes the order against the authoritative tech log
(`rules.airworthiness`): no release with an open grounding defect, no deferral of a grounding defect, servicing
extensions within the cap, stock and donor availability, and so on. A failed execution check is REJECTED with
the reason.

**Replay.** `orders_in(world.order_log)` extracts the order stream; `dump_order_log` / `load_order_log` give a
canonical byte form and `order_log_hash` its identity; `replay(session, events, until)` re-injects the events into
a fresh session and reproduces the live run bitwise (records and world snapshot).

## Reference policies (`configs/policies/`)

Policies observe only the contract `as_of` the decision epoch and act only through orders:

- `StatusQuoPolicy` (IAF-style hard-time / reactive status quo): hard-time retirement, scheduled servicing and
  reactive repair are M18's standing procedures; the status-quo decisions are Maintenance Control's
  cannibalisations, issued with the same rule M18 uses in open loop (`maintenance.rules.cann_plan`) on a fleet
  view rebuilt from records (`fleet_view_from_records`). With M18's built-in CANN off it reproduces the open-loop
  KPIs exactly (A3).
- `ScheduledPolicy`: status quo plus engine washes and borescopes at fixed flight-hour intervals.
- `ConditionBasedPolicy`: status quo plus troubleshooting when a deferred BIT code recurs, and a borescope after
  repeated engine exceedances; its orders cite the triggering records as evidence.

Thresholds are `[ASSUMPTION]` A-W1.8-22 with sweeps in the YAML files.

## Validation criteria and tests

| Criterion | Tests |
|---|---|
| A4 schema validation, authority, idempotency | `tests/unit/test_orders_model.py` |
| A4 no look-ahead (property) and index/view equivalence | `tests/property/test_orders_no_lookahead_property.py` |
| A4 replay bitwise; resent orders are no-ops after restore | `tests/fork/test_orders_replay.py` |
| A3 status quo reproduces open loop; records view = tech-log view | `tests/fork/test_orders_status_quo.py` |
| A6 `orders.commands` / `orders.status` conformance and lifecycle | `tests/fork/test_maintenance_contract.py` |
| Policies act at their thresholds on ingested evidence | `tests/fork/test_orders_policies.py` |

## Known limitations

- One decision calendar for the whole fleet (daily epochs); sortie-boundary epochs are snapshots, not order
  application points.
- Per-action parameter schemas are M21's (A-W1.8-19); the contract leaves them open.
- The authority matrix and the 20 % servicing-extension cap are assumptions (A-W1.8-18).
