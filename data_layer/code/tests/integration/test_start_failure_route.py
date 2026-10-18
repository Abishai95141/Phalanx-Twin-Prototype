"""AD-49 start-failure route: M11 -> M02 ``ops.start_failure`` -> M18 ``ops.ground_abort``.

- **M02** (real operations world: M02 + M18 + M21 + sink + M10/M11/M14 of one tail): a start failure reported
  after the launch commit and before take-off ground-aborts that sortie (``ops.ground_abort`` to M18;
  no ``ops.takeoff`` / ``ops.sortie_done`` / ``usage.sortie_summary`` for it); a report at or after
  take-off is too late - counted (``n.start_failure_late``), the sortie flies on; a report naming another
  tail is ignored the same way.
- **M11** (producer) is tested in ``tests/unit/test_faults_start_failure.py``; here a test source plays it.

Sample (stated before running): the 2-tail Sulur world of ``test_maintenance_protocol_runtime`` from Monday
2026-01-05, one root seed, run to the first flying day's first committed sortie of the monitored tail and on
past its end (n = 1 sortie per arm).
"""

from __future__ import annotations

import pytest
from test_maintenance_protocol_runtime import DAY, NS, SEED, TAIL, RuntimeWorld, _steps

from phalanx.core.events import Event
from phalanx.fork.session import OpsSession
from phalanx.health.protocol import plain_payload, read_payload
from phalanx.scenario.module import read_doc

pytestmark = pytest.mark.integration


def _session():
    s = OpsSession(RuntimeWorld(), SEED)
    return s


def _first_commit(s: OpsSession):
    """Run the world until a sortie of the monitored tail is committed ('flying') and not yet airborne;
    returns that pending record."""
    t = 0
    while t < 2 * DAY:
        t += 600 * NS
        s.world, _ = s.system.run(s.world, _steps(s, t))
        doc = read_doc(s.world.states["m02"])
        recs = [
            r
            for r in doc["pending"].values()
            if r["tail_no"] == TAIL and r["state"] == "flying" and int(r["t_takeoff"]) > s.world.t_ns + 2 * NS
        ]
        if recs:
            return min(recs, key=lambda r: int(r["t_takeoff"]))
    raise AssertionError("no committed sortie of the monitored tail in two days")


def _report(s: OpsSession, t: int, sid: str, tail: str = TAIL):
    doc = {"tail_no": tail, "sortie_id": sid, "mode": "FM.SPS.JFS_COLD_START_FAIL"}
    s.world = s.system.inject(
        s.world, [Event(t, "ops.start_failure", "m02", plain_payload(doc), source="m11")]
    )


def _run_past(s: OpsSession, t: int):
    s.world, tr = s.system.run(s.world, _steps(s, t))
    return [e for _, e in tr.dispatched]


def _about(events, sid):
    return [(e.kind, e.target) for e in events if str(read_payload(e.payload).get("sortie_id", "")) == sid]


def test_start_failure_before_takeoff_ground_aborts_the_sortie():
    s = _session()
    rec = _first_commit(s)
    sid, n0 = rec["sortie_id"], read_doc(s.world.states["m02"])["n"]["ground_abort"]
    _report(s, s.world.t_ns + NS, sid)
    seen = _about(_run_past(s, int(rec["t_end"]) + 60 * NS), sid)
    assert ("ops.ground_abort", "m18") in seen
    assert not {k for k, _ in seen} & {"ops.takeoff", "ops.sortie_done", "usage.sortie_summary"}
    doc = read_doc(s.world.states["m02"])
    assert sid not in doc["pending"] and doc["n"]["ground_abort"] == n0 + 1
    assert "start_failure_late" not in doc["n"]


@pytest.mark.parametrize("late", ["after_takeoff", "other_tail"])
def test_late_or_misaddressed_report_is_counted_and_the_sortie_flies(late):
    s = _session()
    rec = _first_commit(s)
    sid = rec["sortie_id"]
    if late == "after_takeoff":
        _run_past(s, int(rec["t_takeoff"]) + 60 * NS)
        _report(s, s.world.t_ns + NS, sid)
    else:
        _report(s, s.world.t_ns + NS, sid, tail="NOT-" + TAIL)
    seen = _about(_run_past(s, int(rec["t_end"]) + 60 * NS), sid)
    assert ("ops.ground_abort", "m18") not in seen and ("ops.sortie_done", "m18") in seen
    assert read_doc(s.world.states["m02"])["n"]["start_failure_late"] == 1
