"""W2.2 M12 avionics: interface conformance of ``phalanx.sensors.avionics.ports`` (AD-42, AD-51).

Since W2.2 phase B the E1-MF gate (tests/integration/test_interface_conformance.py) discovers nested
``ports.py`` modules and gates the avionics extension as "M12A" in every configuration. This file keeps the
avionics-specific checks on top: every binding closes with exact unit, dtype, shape and clock (Tejas,
n_engines 1); the RECORDED channels pass the gate's recorded-channel rules; each channel has one owner; the
recording path (M13) acquires every avionics channel: the computed numeric channels without independent
recorder noise on their LRU's clock set, the status words through the word path (W2.2 phase B closed the
phase-A acquisition gaps G-ACQ-CLOCK-INGPS/AHRS/RADALT and G-ACQ-WORDS).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from phalanx.acquisition import kernel as K
from phalanx.acquisition.config import acquisition_domain_lru, build_acquisition_config
from phalanx.core.rng import StreamRegistry
from phalanx.dictionary import load_dictionary
from phalanx.sensors.avionics import channels as C
from phalanx.sensors.avionics import ports as AP
from phalanx.sensors.avionics.module import STREAMS
from phalanx.sensors.config import build_sensor_config


def _gate():
    name = "w22_interface_gate"
    if name not in sys.modules:
        p = Path(__file__).resolve().parent / "test_interface_conformance.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


G = _gate()
D = load_dictionary()
INS, OUTS, BINDINGS = AP.ports(1)
#: the acquisition domain (crystal owner) of each avionics LRU's outputs
DOMAINS = {
    "NAV.INS.": "INGPS",
    "NAV.GPS.": "INGPS",
    "NAV.AHRS.": "AHRS",
    "NAV.RADALT": "RADALT",
    "STORES.": "SMS",
}


@pytest.mark.integration
def test_avionics_bindings_close_in_the_gate():
    cfg = G.CONFIGS["e1"]
    pubs = dict(G.config_pubs(cfg))
    pubs["M12A"] = G.Pub("M12A", AP.PREFIX, tuple(INS), tuple(OUTS), dict(BINDINGS), dict(AP.RECORDED))
    res = G.gate(cfg, pubs=pubs)
    assert not res["unexpected"], "\n".join(map(str, res["unexpected"]))
    assert not res["stale"]
    assert not [pb for pb, _ in res["tracked"] if pb.consumer == "M12A"]
    lanes = {s for s in BINDINGS.values() if s.startswith("lane.")}
    assert len(lanes) == 21  # the quadruplex ADC lanes + TAT, all from M13's DFCC lane producer


@pytest.mark.integration
def test_recorded_channels_against_the_dictionary():
    """Every RECORDED port is a published output of an LRU-computed dictionary channel with the channel's SI
    unit (dictionary 0.1.3 classes NAV.RADALT computed, AD-51 / R-AD51-COMPUTED: the phase-A conflict is
    closed)."""
    problems = G.recorded_problems(dict(AP.RECORDED), {p.name: p for p in OUTS})
    assert problems == []
    assert set(AP.RECORDED.values()) == set(C.ALL) and set(AP.TRUTH.values()) == set(C.NUMERIC)
    by = {p.name: p for p in OUTS}
    for port, cid in AP.RECORDED.items():
        if cid in C.WORDS:
            assert by[port].dtype in ("<i8", "int64") and by[port].unit == "1"


@pytest.mark.integration
def test_each_recorded_channel_has_one_owner():
    """No avionics channel is also an M12 sensor channel or another package's RECORDED channel."""
    m12 = set(build_sensor_config(D).channels)
    assert not set(C.ALL) & m12
    for mod in G.ALL_PKG:
        if mod == "M12A":  # the avionics extension itself (gated since W2.2 phase B)
            continue
        assert not set(C.ALL) & set(G.published(mod, 1).recorded.values()), mod


@pytest.mark.integration
def test_recording_path_for_the_avionics_channels():
    """M13 acquires every avionics channel as an LRU-computed (external) channel with zero recorder noise
    (acquisition_map rules, A-W1.6-32): the numeric outputs on their LRU's clock set (INGPS, AHRS, RADALT
    since W2.2 phase B; the ADC outputs on the DFCC's), the status words through the word path (held, no
    quantiser, A-W2.2-12)."""
    acq = build_acquisition_config(D, list(C.ALL))
    assert all(s < 0 for s in acq.sensor_index)
    assert float(abs(acq.sigma_eff_eu).max()) == 0.0
    for c, cid in enumerate(acq.channels):
        assert (int(acq.Q[c, K.AQ_MODE]) == K.MODE_HOLD) is (cid in C.WORDS), cid
        lru = acq.domains[int(acq.domain_of[c])].lru
        want = next((v for k, v in DOMAINS.items() if cid.startswith(k)), "DFCC")
        assert lru == want == acquisition_domain_lru(D, cid), cid


@pytest.mark.unit
def test_streams_are_identity_keyed():
    reg = StreamRegistry(list(STREAMS))
    assert len(reg) == len(STREAMS) == 7
    for s in STREAMS:
        assert s.subsystem == "avionics" and "scenario" in s.identity
        assert set(s.identity) <= {"scenario", "tail", "serial", "sortie", "sensor"}
