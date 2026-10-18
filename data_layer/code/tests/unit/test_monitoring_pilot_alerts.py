"""AD-49: M14 (CWS) raises the catalogued pilot hooks - ``pilot.fire_warning`` for the engine-fire warning and
``pilot.fcs_caution`` for a flight-control pilot-fault-list caution - when the CWS record opens, and the real
M04 reacts to them (``util.fire_extinguish`` / ``fcs.reset`` after its reaction time).

- FIR-501 from the recorded fire-warning discrete (``FIRE.WARN`` CIR samples through ``monitor.observe``: the
  real limit-monitor path, persistence included);
- FCS-201 (DFCC channel fail) from a controller BIT report;
- ENG-005 (a CWS caution with no catalogued pilot reaction) and an FCS MFL advisory raise nothing;
- no ``pilot_target`` (the W1 wiring): nothing is sent.

TEST FIXTURES: a short synthetic CIR chunk (``FIRE.WARN`` 0 then 1 at 10 Hz) and a ``Sink`` standing in for
M04 at the module boundary; the real M04's handler then reacts to the captured event. n = 1 sortie per case.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.yamlio import load_yaml
from phalanx.ground.cir import CIR_SCHEMA
from phalanx.monitoring import (
    MonitoringConfig,
    MonitoringModule,
    cir_chunk_payload,
    load_code_table,
    load_monitoring_params,
)
from phalanx.monitoring.module import pilot_alert
from phalanx.pilot.module import PilotModule, load_pilot_config

pytestmark = pytest.mark.unit
D = load_dictionary()
P = load_monitoring_params()
CODES = load_code_table(D, P)
SEC = 10**9
EPOCH = 1_800_000_000 * SEC
CAT = load_yaml(Path(__file__).resolve().parents[2] / "configs" / "interfaces" / "w1_events.yaml")["events"]


class Sink(ModuleBase):  # TEST FIXTURE: stands in for M04 at the module boundary
    version, rate = "0", None

    def __init__(self, mid="m04"):
        super().__init__(mid, ParamSet("sink", {}))
        self.got: list[tuple[int, Event]] = []

    def init(self, params, keys):
        return {}

    def on_event(self, state, event, t):
        self.got.append((t, event))
        return state, []


def build(pilot_target="m04", extra=()):
    cfg = MonitoringConfig.from_dictionary(
        D, CODES, ("IN20-0001",), regime="mature", pilot_target=pilot_target
    )
    m = MonitoringModule("m14", P, config=cfg)
    sink = Sink()
    sysm = System(
        [m, sink, *extra],
        [],
        rng=RngService(7, StreamRegistry()),
        identity=KeyPath.of(scenario="S1", tail="KH2011"),
    )
    return m, sink, sysm


def fire_chunk(m, t_on_s=10.0, n_s=30.0) -> dict:
    """TEST FIXTURE: the recorded fire-warning discrete, 0 until ``t_on_s`` then 1, 10 Hz."""
    t = np.arange(0.0, n_s, 0.1)
    v = (t >= t_on_s).astype(np.float64)
    loc = D.contract_location("FIRE.WARN")
    n = t.size
    ts = (EPOCH + (t * 1e9).astype(np.int64)).tolist()
    rows = {
        "param_id": ["FIRE.WARN"] * n,
        "source_lru": [loc["source_lru"]] * n,
        "lane": [None] * n,
        "sample_index": list(range(n)),
        "t_true": ts,
        "t_sample": ts,
        "value": v.tolist(),
        "truth_value": v.tolist(),
        "validity": ["NORMAL"] * n,
        "quality_flags": [0] * n,
        "rng_key_path": [None] * n,
    }
    return cir_chunk_payload(m.config, pa.table(rows, schema=CIR_SCHEMA), epoch_utc_ns=EPOCH)


def m04_reaction(t, ev):
    """The real M04's reaction to an M14 alert event (its handler, as the scheduler would call it)."""
    pm = PilotModule("m04", load_pilot_config(), utilities="util", fcs="fcs")
    pm.bind(
        RngService(3, StreamRegistry(pm.streams)).scope(KeyPath.of(scenario="S1", tail="KH2011", sortie=1))
    )
    _, out = pm.on_event(pm.init(pm.params, pm.keys), ev, t)
    return [(e.kind, e.target) for e in out]


def bit(t, code):
    return Event(
        t, "monitor.bit_report", "m14", {"code": code, "lane": "", "persistence": 0, "cleared": False}
    )


def _alerts(sink):
    return [(e.kind, dict(e.payload)) for _, e in sink.got]


def _plain(p):
    return {k: str(np.asarray(v).item()) for k, v in p.items()}


def test_pilot_alert_classification():
    by = CODES.by_code
    assert pilot_alert(by["FIR-501"]) == "pilot.fire_warning"
    assert {c.code for c in CODES.codes if pilot_alert(c) == "pilot.fcs_caution"} == {
        "FCS-101",
        "FCS-102",
        "FCS-201",
        "FCS-501",
        "FCS-502",
    }
    assert pilot_alert(by["ENG-005"]) is None and pilot_alert(by["FCS-001"]) is None
    for kind in ("pilot.fire_warning", "pilot.fcs_caution"):
        assert CAT[kind]["producer"] == "M14" and CAT[kind]["consumers"] == ["M04"]


def test_fire_warning_from_the_recorded_discrete():
    m, sink, sysm = build()
    evs = [
        Event(0, "monitor.sortie_start", "m14", {"sortie_id": "KH2011-1"}),
        Event(31 * SEC, "monitor.observe", "m14", fire_chunk(m)),
    ]
    sysm.run(sysm.inject(sysm.start(), evs), 32 * 240)
    got = [(e.kind, _plain(e.payload), t) for t, e in sink.got]
    assert [(k, p) for k, p, _ in got] == [("pilot.fire_warning", {"tail": "KH2011", "code": "FIR-501"})]
    assert set(CAT["pilot.fire_warning"]["payload"]) <= set(got[0][1])
    assert got[0][2] >= 31 * SEC  # never before the observation that raised it
    assert m04_reaction(*sink.got[0]) == [("util.fire_extinguish", "util")]


def test_fcs_caution_from_a_bit_report_and_no_alert_for_other_codes():
    _m, sink, sysm = build()
    evs = [
        Event(0, "monitor.sortie_start", "m14", {"sortie_id": "KH2011-1"}),
        bit(2 * SEC, "ENG-005"),  # CWS caution, no catalogued pilot reaction
        bit(3 * SEC, "FCS-001"),  # FCS MFL advisory: no legend
        bit(4 * SEC, "FCS-201"),  # DFCC channel fail: PFL caution
    ]
    sysm.run(sysm.inject(sysm.start(), evs), 5 * 240)
    got = [(e.kind, _plain(e.payload), t) for t, e in sink.got]
    assert [(k, p) for k, p, _ in got] == [("pilot.fcs_caution", {"tail": "KH2011", "code": "FCS-201"})]
    assert got[0][2] == 4 * SEC
    assert m04_reaction(*sink.got[0]) == [("fcs.reset", "fcs")]


def test_no_pilot_target_sends_nothing():
    _m, sink, sysm = build(pilot_target=None)
    evs = [Event(0, "monitor.sortie_start", "m14", {"sortie_id": "KH2011-1"}), bit(4 * SEC, "FCS-201")]
    sysm.run(sysm.inject(sysm.start(), evs), 5 * 240)
    assert sink.got == []
