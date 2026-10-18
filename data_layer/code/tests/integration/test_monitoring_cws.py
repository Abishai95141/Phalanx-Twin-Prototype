"""CWS words (AD-42: CWS legends belong to M14): the bit map follows the dictionary encodings, M14 publishes
the words as held outputs listed in ``ports.RECORDED`` (conformance-checked like any LRU-computed recorded
channel), they follow the caution state through declaration, acknowledgement and clearing, and
``cws_words_at`` gives the exact edge times of a monitor caution.

Inputs: scripted controller reports and LRU conditions; for the edge-time check one ``monitor.observe``
chunk of T5 (TEST FIXTURE: 10 Hz for 600 s with a 10 s over-temperature bump). n = 1 sortie per test (each
checks a deterministic mechanism)."""

from __future__ import annotations

import numpy as np
import pytest
from test_interface_conformance import recorded_problems  # sibling test module (AD-42 RECORDED check)

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.monitoring import (
    CWS_PORTS,
    MonitoringConfig,
    MonitoringModule,
    bit_report_payload,
    build_cws_map,
    cws_words_at,
    load_code_table,
    load_monitoring_params,
    lru_condition_payload,
)
from phalanx.monitoring import ports as m14_ports
from phalanx.monitoring.module import KIND_BIT, KIND_CAUTION, KIND_EXCEED

pytestmark = pytest.mark.integration
D = load_dictionary()
P = load_monitoring_params()
CODES = load_code_table(D, P)
SEC = 10**9


def build():
    cfg = MonitoringConfig.from_dictionary(D, CODES, ("IN20-0001",), regime="mature")
    m = MonitoringModule("monitoring", P, config=cfg)
    sysm = System(
        [m], [], rng=RngService(0xC0DE, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail="KH2011")
    )
    return m, sysm


def t5_chunk(m) -> dict[str, np.ndarray]:
    """TEST FIXTURE: ``monitor.observe`` payload of ENG.T5 (degC), 10 Hz, 600 s, overtemperature 300-310 s."""
    t = np.arange(0, 6000) * (SEC // 10)
    v = np.where((t >= 300 * SEC) & (t < 310 * SEC), 900.0, 700.0)
    ch = np.full(t.size, m.config.channels.index("ENG.T5"), np.int64)
    return {"ch": ch, "t": t, "v": v, "validity": np.zeros(t.size, np.int64)}


def words(m, code: str) -> dict[str, int]:
    act = np.zeros(len(CODES.codes), bool)
    act[CODES.index(code)] = True
    return {p: int(v) for p, v in m.words(act).items() if int(v)}


def test_bit_map_follows_the_dictionary_encodings():
    m = build_cws_map(D, CODES)
    assert m.ports == tuple(CWS_PORTS)
    assert words(m, "ENG-005") == {"cws_legend_a": 1 << 0, "cws_master": 0b10}  # L01, CAUTION
    assert words(m, "CWS-703") == {"cws_legend_b": 1 << 13, "cws_master": 0b01, "cws_voice_uc": 1}  # L29
    assert words(m, "ELE-404") == {"cws_legend_b": 1 << 9}  # L25, ADVISORY: no master
    assert words(m, "ENG-001") == {}  # MFL: no legend
    for code, ch in (("CWS-701", "AOA"), ("CWS-702", "LOW_ALT"), ("CWS-704", "CANOPY")):
        assert words(m, code)[f"cws_voice_{ch.lower()}"] == 1
    assert m.words(np.zeros(len(CODES.codes), bool)) == {p: 0 for p in CWS_PORTS}


def test_recorded_cws_channels_conform():
    """The AD-42 RECORDED check (``test_interface_conformance.recorded_problems``) on M14's ports; M14 is not
    in that test's module list, so it is applied here."""
    _, outs, bindings = m14_ports.ports(1)
    assert m14_ports.PREFIX == "monitor" and bindings == {}
    assert set(m14_ports.RECORDED) == {p.name for p in outs}
    assert recorded_problems(m14_ports.RECORDED, {p.name: p for p in outs}) == []
    cws = sorted(c["channel_id"] for c in D.channels() if c.get("acq_lru") == "CWS")
    assert sorted(m14_ports.RECORDED.values()) == cws


def test_held_words_follow_declaration_ack_and_clear():
    _m, sysm = build()
    w = sysm.inject(
        sysm.start(),
        [
            Event(0, "monitor.sortie_start", "monitoring", {"sortie_id": "KH2011-0"}),
            Event(SEC, "monitor.bit_report", "monitoring", bit_report_payload("ENG-005", lane="A")),
            Event(2 * SEC, "monitor.bit_report", "monitoring", bit_report_payload("CWS-703")),
        ],
    )
    w, _ = sysm.run(w, 240 * 3)
    held = {p: int(w.held[f"monitoring.{p}"]) for p in CWS_PORTS}
    assert held["cws_legend_a"] & 1 and held["cws_legend_b"] & (1 << 13) and held["cws_voice_uc"] == 1
    assert held["cws_master"] & 0b11 == 0b11
    n = int(w.states["monitoring"]["o_kind"].size)
    w = sysm.inject(w, [Event(w.t_ns + 1, "monitor.ack", "monitoring", {"n": n})])  # drained, still active
    w, _ = sysm.run(w, 2)
    assert int(w.held["monitoring.cws_voice_uc"]) == 1 and int(w.held["monitoring.cws_legend_a"]) & 1
    w = sysm.inject(
        w,
        [
            Event(
                w.t_ns + 1, "monitor.bit_report", "monitoring", bit_report_payload("ENG-005", cleared=True)
            ),
            Event(
                w.t_ns + 1, "monitor.bit_report", "monitoring", bit_report_payload("CWS-703", cleared=True)
            ),
        ],
    )
    w, _ = sysm.run(w, 2)
    assert int(w.held["monitoring.cws_legend_a"]) & 1 == 0
    assert (
        int(w.held["monitoring.cws_voice_uc"]) == 0
        and int(w.held["monitoring.cws_legend_b"]) & (1 << 13) == 0
    )


def test_monitor_caution_edges_are_exact_in_cws_words_at():
    """T5 over-temperature (ENG-701, legend L08 = bit 7 of CWS.LEGEND.A) from one CIR chunk delivered at the
    start of the sortie: the held word only shows the state after the chunk, cws_words_at the exact edges."""
    m, sysm = build()
    pay = t5_chunk(m)
    w = sysm.inject(
        sysm.start(),
        [
            Event(0, "monitor.sortie_start", "monitoring", {"sortie_id": "KH2011-0"}),
            Event(1, "monitor.observe", "monitoring", pay),
        ],
    )
    w, _ = sysm.run(w, 2)
    st = w.states["monitoring"]
    i701 = CODES.index("ENG-701")
    cau = np.flatnonzero((st["o_kind"] == KIND_CAUTION) & (st["o_code"] == i701))
    exc = np.flatnonzero((st["o_kind"] == KIND_EXCEED) & (st["o_code"] == i701))
    assert cau.size == 1 and exc.size == 1
    t_on, t_off = int(st["o_t"][cau[0]]), int(st["o_t_end"][cau[0]])
    assert (t_on, t_off) == (int(st["o_t"][exc[0]]), int(st["o_t_end"][exc[0]]))
    assert 300 * SEC < t_on < 310 * SEC < t_off < 320 * SEC
    t = np.array([t_on - 1, t_on, t_off - 1, t_off])
    bit7 = (cws_words_at(m, st, t)["cws_legend_a"] >> 7) & 1
    assert bit7.tolist() == [0, 1, 1, 0]
    assert int(w.held["monitoring.cws_legend_a"]) >> 7 & 1 == 0  # closed by the end of the chunk


def test_pbit_failure_latches_until_cbit_passes():
    """An LRU condition present at power-up fails PBIT (one record, caution on); the test stays declared (no
    CBIT duplicate) and, once the condition clears, CBIT passes n_clear times and closes the caution."""
    _m, sysm = build()
    w = sysm.inject(
        sysm.start(),
        [
            Event(0, "monitor.lru_condition", "monitoring", lru_condition_payload("FCS-201", 12.0)),
            Event(1, "monitor.sortie_start", "monitoring", {"sortie_id": "KH2011-0"}),
        ],
    )
    w, _ = sysm.run(w, 2)
    assert int(w.held["monitoring.cws_legend_a"]) >> 13 & 1 == 1  # L14
    t_clear = 600 * SEC
    w = sysm.inject(
        w,
        [
            Event(
                t_clear,
                "monitor.lru_condition",
                "monitoring",
                lru_condition_payload("FCS-201", 0.0, clear=True),
            ),
            Event(t_clear + 3600 * SEC, "monitor.landing", "monitoring", {}),
        ],
    )
    w, _ = sysm.run(w, 240 * 4300)
    st = w.states["monitoring"]
    i = CODES.index("FCS-201")
    bits = np.flatnonzero((st["o_kind"] == KIND_BIT) & (st["o_code"] == i))
    cau = np.flatnonzero((st["o_kind"] == KIND_CAUTION) & (st["o_code"] == i))
    assert bits.size == 1 and cau.size == 1
    assert int(st["o_t_end"][cau[0]]) > t_clear  # closed by CBIT after the condition cleared
    assert int(w.held["monitoring.cws_legend_a"]) >> 13 & 1 == 0
