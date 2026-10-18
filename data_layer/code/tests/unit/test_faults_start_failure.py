"""AD-49 start-failure route, M11 side: the onset of a start-failure mode (JFS cold start, hung start, hot
start; ``maintenance.START_FAILURES``) sends ``ops.start_failure`` {tail_no, sortie_id, mode} to the ``"ops"``
target (M02); other modes, and a world without an ``"ops"`` target (W1 wiring), send nothing. The M02 end is
``tests/integration/test_start_failure_route.py``.

TEST FIXTURES: ``Recorder`` modules at the module boundary (``test_faults_module.build``). n = 1 onset per
mode (deterministic, scripted).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_faults_module import SEC, TARGETS, build, run_to

from phalanx.core.events import Event
from phalanx.dictionary.yamlio import load_yaml
from phalanx.faults.maintenance import START_FAILURES
from phalanx.health.protocol import read_payload

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
START = Event(SEC, "faults.sortie_start", "faults", {"sortie_id": "KH2011-7", "duration_s": 3600.0})


def _reports(recs):
    return [read_payload(e.payload) for _, e in recs["ops"].log if e.kind == "ops.start_failure"]


@pytest.mark.parametrize("mode", sorted(START_FAILURES))
def test_start_failure_onset_is_reported_to_m02(mode):
    sysm, _f, _h, recs = build(targets=(*TARGETS, "ops"))
    ev = Event(2 * SEC, "faults.inject", "faults", {"mode": mode, "covered": True})
    run_to(sysm, sysm.inject(sysm.start(), [START, ev]), 3 * SEC)
    got = _reports(recs)
    assert got == [{"tail_no": "KH2011", "sortie_id": "KH2011-7", "mode": mode}]
    spec = load_yaml(ROOT / "configs" / "interfaces" / "w1_events.yaml")["events"]["ops.start_failure"]
    assert set(spec["payload"]) <= set(got[0]) and spec["producer"] == "M11" and spec["consumers"] == ["M02"]


def test_other_modes_and_an_unwired_target_send_nothing():
    sysm, _f, _h, recs = build(targets=(*TARGETS, "ops"))
    ev = Event(2 * SEC, "faults.inject", "faults", {"mode": "FM.FCS.CHANNEL_DROPOUT", "covered": True})
    run_to(sysm, sysm.inject(sysm.start(), [START, ev]), 3 * SEC)
    assert _reports(recs) == []
    sysm, _f, _h, recs = build()  # W1 wiring: no "ops" target
    ev = Event(2 * SEC, "faults.inject", "faults", {"mode": "FM.SPS.JFS_COLD_START_FAIL", "covered": True})
    run_to(sysm, sysm.inject(sysm.start(), [START, ev]), 3 * SEC)
    assert all(e.kind != "ops.start_failure" for r in recs.values() for _, e in r.log)
