"""A1 SCIR arithmetic (property): the incremental 15-minute binning inside M18 equals the reference
``scir.bin_states`` applied to the instantaneous state changes M18 publishes in its tech log.

Changes are driven by GROUND/RELEASE orders delivered to M18 at arbitrary whole-second times (several per bin,
exactly on boundaries, long gaps). Sample: hypothesis, 40 examples of 1-14 changes over 2 days.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.events import Event
from phalanx.fork.builder import OpsOnlyBuilder
from phalanx.fork.kpi import availability_series, occupancy_window
from phalanx.fork.session import OpsSession
from phalanx.health.protocol import plain_payload
from phalanx.maintenance import scir
from phalanx.maintenance.config import load_m18_config
from phalanx.maintenance.world import FleetSpec

NS = 1_000_000_000
EPOCH = 1_790_035_200 * NS
W = 900 * NS
_CFG = None


def _cfg():
    global _CFG
    if _CFG is None:
        c = load_m18_config()
        _CFG = c.with_values(srv_interval_fh_s=(10**9,) * 4, srv_interval_s=(10**9,) * 4)
    return _CFG


def _order(t, oid, action):
    row = {
        "order_id": oid,
        "action": action,
        "parameters": {"reason": "x"} if action == "GROUND" else {},
        "target_tail_no": "T01",
        "target_base": None,
        "priority": "ROUTINE",
    }
    return Event(t, "order.exec", "m18", plain_payload({"order": row}), source="test")  # AD-48.1


@pytest.mark.property
@settings(max_examples=40, deadline=None)
@given(
    times=st.lists(
        st.one_of(st.integers(1, 172_800), st.integers(1, 190).map(lambda b: b * 900)),
        min_size=1,
        max_size=14,
    )
)
def test_incremental_binning_equals_reference(times):
    b = OpsOnlyBuilder(FleetSpec(("T01",), ("SUL",), (0,)), EPOCH, m18_cfg=_cfg())
    s = OpsSession(b, 3)
    evs = [
        _order(t * NS, f"o{i}", "GROUND" if i % 2 == 0 else "RELEASE") for i, t in enumerate(sorted(times))
    ]
    s.world = s.system.inject(s.world, evs)
    t_end = 3 * 86_400 * NS
    s.run_until(t_end)
    tl = [r for r in s.records("maint.records") if r["record_type"] == "TECH_LOG"]
    changes = [(int(r["t_event"]), scir.RANK[r["availability_state"]]) for r in tl]
    t0 = changes[0][0]
    ref = scir.bin_states(changes[1:], t0, EPOCH + t_end, W, initial=changes[0][1])
    got = availability_series(s.log)["T01"]
    # persist-until-next-record series -> per-bin states over the same window
    expanded = []
    for bstart, _ in ref:
        state = None
        for gb, gs in got:
            if gb <= bstart:
                state = gs
        expanded.append((bstart, state))
    assert expanded == ref
    occ_ref = scir.occupancy(ref, W, t0=t0, t1=EPOCH + t_end)
    assert occupancy_window(got, t0, EPOCH + t_end) == occ_ref
