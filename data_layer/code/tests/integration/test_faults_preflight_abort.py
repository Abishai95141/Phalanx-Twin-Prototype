"""W2.5 deliverable 5 end to end (A-W2.1c-6): a start failure drawn at engine start ground-aborts the sortie.

The real operations world of ``test_maintenance_protocol_runtime`` (M02 operations mode, M18, M21, sink, and
the monitored tail's M10/M11/M14), with M11 stochastic and the hung-start probability forced to 1 so that the
one power-up of the test fails its start. ``ops.power_up`` is M02's planned emission (catalogue ``planned:
W2.1a``): a test source plays it at the commit of the tail's first sortie, to M11 and M14. Expected chain: M11
draws the hung start at engine start -> ``ops.start_failure`` to M02 before take-off -> M02 ground-aborts
(``ops.ground_abort`` to M18), and no take-off, sortie-done or usage summary follows for that sortie; M11 also
sends the preflight ``truth.fault`` to M18.

Tracked gap (request to W2.1a, strict): after a ground abort M02 sends nothing to M11/M14, so M14 stays
powered (and M11 keeps the sortie prepared). ``test_m14_stays_powered_after_the_abort`` fails once M02 closes
the sortie (e.g. ``ops.sortie_done`` with ``aborted`` true and zero flight hours), as a reminder to flip it.

Sample: one committed sortie, one root seed (n = 1; the route is deterministic with the forced probability).
"""

from __future__ import annotations

import pytest
from test_maintenance_protocol_runtime import IDS, SERIAL, TAIL, D, RuntimeWorld
from test_start_failure_route import _about, _first_commit, _run_past

from phalanx.core.events import Event
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.fork.session import OpsSession
from phalanx.health import sensor_bias_channels
from phalanx.health.protocol import plain_payload, read_payload
from phalanx.scenario.module import read_doc

pytestmark = pytest.mark.integration
NS = 10**9
SEED = 0x5EED


def _m11_forced():
    cfg = FaultConfig(
        load_catalogue(),
        load_graph(),
        {"health": "m10", "monitoring": "m14", "maintenance": IDS.m18, "ops": "m02"},
        (SERIAL,),
        sensor_bias_channels(D),
        realise_physics_edges=True,
        stochastic=True,
        tail_no=TAIL,
    )
    p = load_fault_params().replace(hung_start_p=1.0)
    return FaultInjector("m11", p, config=cfg, identity={"tail": TAIL})


class PreflightWorld(RuntimeWorld):
    """The runtime world with a stochastic M11 whose hung-start probability is 1."""

    def __init__(self) -> None:
        super().__init__()
        extra = list(self._ops.extra)
        extra[2] = _m11_forced  # (M02, M10, M11, M14)
        self._ops.extra = tuple(extra)


@pytest.fixture(scope="module")
def aborted():
    s = OpsSession(PreflightWorld(), SEED)
    rec = _first_commit(s)
    sid = rec["sortie_id"]
    t_up = s.world.t_ns + NS
    doc = {"tail_no": TAIL, "sortie_id": sid, "engine_starts": 1, "cold_soak": 0}
    evs = [Event(t_up, "ops.power_up", tgt, plain_payload(doc), source="m02") for tgt in ("m11", "m14")]
    s.world = s.system.inject(s.world, evs)
    seen = _run_past(s, int(rec["t_end"]) + 60 * NS)
    return s, rec, seen


def test_start_failure_at_engine_start_ground_aborts_before_take_off(aborted):
    s, rec, seen = aborted
    sid = rec["sortie_id"]
    kinds = _about(seen, sid)
    assert ("ops.start_failure", "m02") in kinds and ("ops.ground_abort", IDS.m18) in kinds
    assert not {k for k, _ in kinds} & {"ops.takeoff", "ops.sortie_done", "usage.sortie_summary"}
    doc = read_doc(s.world.states["m02"])
    assert sid not in doc["pending"] and "start_failure_late" not in doc["n"]
    truth = [read_payload(e.payload) for e in seen if e.kind == "truth.fault"]
    assert any(d["mode"] == "FM.ENG.HUNG_START" and d["symptom"] == "preflight" for d in truth), truth


def test_m14_stays_powered_after_the_abort(aborted):
    """Tracked gap (strict reminder): M02 does not yet close an aborted sortie towards M11/M14."""
    s, rec, _ = aborted
    st = s.world.states["m14"]
    assert int(st["clock"][2]) == 1 and str(st["sortie_id"]) == rec["sortie_id"]
