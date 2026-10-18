"""W2.2 M12 avionics: SMS station status (AD-51; A-W2.2-9).

The SMS is discrete: mission loading (``avio.sms_load``) sets the station content codes (synthetic
``store_station`` table), a commanded release (``avio.sms_release``) empties the station and sets its
RELEASED bit unless the store hangs (probability ``p_hung``, one keyed uniform per release command, so forks
issuing the same commands share the outcome), a jettison always empties, an unpowered SMS ignores commands.
Sample sizes per test are stated; deterministic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from phalanx.core.events import Event
from phalanx.dictionary.params import load_params
from phalanx.sensors.avionics import sms as S
from phalanx.sensors.avionics.config import build_avionics_config


def _fixture():
    name = "w22_avionics_fixture"
    if name not in sys.modules:
        p = Path(__file__).resolve().parents[1] / "integration" / "test_w22_avionics_fixture.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


FX = _fixture()
LOAD = [3, 1, 1, 2, 0, 2, 1, 1, 3]  # store_station codes per station 1..9 (0 = EMPTY)


def _module(p_hung: float | None = None):
    cfg = None
    if p_hung is not None:
        params = load_params("M12_AVIONICS")
        params["sms"] = params["sms"].replace(p_hung=p_hung)
        cfg = build_avionics_config(params=params)
    m = FX.make_module(config=cfg) if cfg is not None else FX.make_module()
    return m, m.init(m.params, m.keys)


def _ev(kind: str, t: int = 0, **payload) -> Event:
    return Event(t, kind, "avio", payload)


def _codes(state) -> list[int]:
    return [int(x) for x in state["sms_i"][S.I_CODES : S.I_CODES + S.N_STATIONS]]


@pytest.mark.unit
def test_load_release_and_jettison():
    """p_hung = 0: release empties station 2 and sets bit 1; jettison empties station 9 (bit 8); releasing an
    empty station only counts the command; a new load clears the RELEASED word."""
    m, s = _module(p_hung=0.0)
    s, _ = m.on_event(s, _ev(S.LOAD_EVENT, stations=LOAD), 0)
    assert _codes(s) == LOAD and int(s["sms_i"][S.I_RELEASED]) == 0
    s, _ = m.on_event(s, _ev(S.RELEASE_EVENT, station=2, mode="release"), 0)
    s, _ = m.on_event(s, _ev(S.RELEASE_EVENT, station=9, mode="jettison"), 0)
    s, _ = m.on_event(s, _ev(S.RELEASE_EVENT, station=5, mode="release"), 0)
    assert _codes(s) == [3, 0, 1, 2, 0, 2, 1, 1, 0]
    assert int(s["sms_i"][S.I_RELEASED]) == (1 << 1) | (1 << 8)
    assert int(s["sms_i"][S.I_NCMD]) == 3
    s, _ = m.on_event(s, _ev(S.LOAD_EVENT, stations=LOAD), 0)
    assert int(s["sms_i"][S.I_RELEASED]) == 0
    # the held words reach the recorded ports on the next step
    _, o = FX.run_direct(m, FX.default_truth(2), 2, state=s)
    assert [int(o[f"rec_stores_config_station_{k}"][-1]) for k in range(1, 10)] == LOAD


@pytest.mark.unit
def test_hung_store_keeps_its_content_but_jettison_empties():
    """p_hung = 1 (mechanism check outside the 0-0.05 sweep): every release hangs (content kept, bit clear);
    jettison still empties the station."""
    m, s = _module(p_hung=1.0)
    s, _ = m.on_event(s, _ev(S.LOAD_EVENT, stations=LOAD), 0)
    s, _ = m.on_event(s, _ev(S.RELEASE_EVENT, station=1, mode="release"), 0)
    assert _codes(s)[0] == 3 and int(s["sms_i"][S.I_RELEASED]) == 0
    s, _ = m.on_event(s, _ev(S.RELEASE_EVENT, station=1, mode="jettison"), 0)
    assert _codes(s)[0] == 0 and int(s["sms_i"][S.I_RELEASED]) == 1


@pytest.mark.statistical
def test_hung_fraction_matches_p_hung_and_is_keyed_by_command_count():
    """n = 400 release commands at the sweep's upper p_hung = 0.05 (expected 20 hung, binomial sd 4.4; band
    [7, 33] = 3 sd). The k-th command's draw is the k-th uniform of the sortie's stream whatever its time, so
    a fork issuing the same commands at other times hangs the same stores (CRN)."""
    p = 0.05

    def run(t_step: int) -> list[bool]:
        m, s = _module(p_hung=p)
        hung = []
        for k in range(400):
            s, _ = m.on_event(s, _ev(S.LOAD_EVENT, t=k * t_step, stations=LOAD), k * t_step)
            s, _ = m.on_event(s, _ev(S.RELEASE_EVENT, t=k * t_step, station=1, mode="release"), k * t_step)
            hung.append(_codes(s)[0] != 0)
        return hung

    a, b = run(10**9), run(7 * 10**9 + 3)
    assert a == b
    assert 7 <= sum(a) <= 33, sum(a)


@pytest.mark.unit
def test_unpowered_sms_ignores_commands_and_bad_payloads_are_refused():
    """With the SMS bus below v_dropout past the hold-up, a release changes nothing (the command is counted);
    out-of-range stations, unknown modes and malformed loads raise."""
    m, s = _module(p_hung=0.0)
    s, _ = m.on_event(s, _ev(S.LOAD_EVENT, stations=LOAD), 0)
    truth = FX.default_truth(240)
    truth["util.bus_v"][:, m.config.bus["SMS"]] = 0.0
    s, o = FX.run_direct(m, truth, 240, state=s)
    assert o["powered_sms"][-1] == 0
    s, _ = m.on_event(s, _ev(S.RELEASE_EVENT, station=1, mode="release"), 0)
    assert _codes(s) == LOAD and int(s["sms_i"][S.I_NCMD]) == 1
    for bad in (
        {"station": 0, "mode": "release"},
        {"station": 10, "mode": "release"},
        {"station": 1, "mode": "x"},
    ):
        with pytest.raises(ValueError):
            m.on_event(s, _ev(S.RELEASE_EVENT, **bad), 0)
    with pytest.raises(ValueError):
        m.on_event(s, _ev(S.LOAD_EVENT, stations=LOAD[:8]), 0)
    with pytest.raises(ValueError):  # code 6 is outside the 6-entry synthetic store_station table
        m.on_event(s, _ev(S.LOAD_EVENT, stations=[6] * S.N_STATIONS), 0)
