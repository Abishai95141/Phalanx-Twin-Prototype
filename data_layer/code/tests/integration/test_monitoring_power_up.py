"""W2.5 deliverable 4 (W2.1c proposal 4): power-up BIT at engine start through the catalogued
``ops.power_up``.

M14 runs PBIT when the aircraft powers up at engine start (``ops.power_up`` {tail_no, sortie_id}), CBIT from
then on (taxi included), and keeps that power-up at ``ops.takeoff``; without a power-up the take-off still
powers up (PROXY A-W2.1c-4, retired when M02 emits ``ops.power_up``). The PBIT pass of a sortie draws from
the sortie's own keyed streams, so the PBIT outcome is the same whichever event powers the monitor up; only
its instant moves to engine start.

M02 emits ``ops.power_up`` (W2.1a; the strict tracked exception that held its absence is retired with the
catalogue's ``planned`` flag): ``test_m02_declares_the_power_up``.

Sample: one tail, one sortie per test; the PBIT-equality check uses 12 sorties with a forced PBIT failure
condition so that PBIT records exist (deterministic keyed draws)."""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.yamlio import load_yaml
from phalanx.health.protocol import plain_payload
from phalanx.monitoring import (
    MonitoringConfig,
    MonitoringModule,
    load_code_table,
    load_monitoring_params,
    lru_condition_payload,
)
from phalanx.monitoring.codes import MECHANISMS
from phalanx.monitoring.module import KIND_BIT
from phalanx.monitoring.ports import EVENTS_IN, POWER_UP_KEYS
from phalanx.scenario.module import TAKEOFF_KEYS

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
CAT = load_yaml(ROOT / "configs" / "interfaces" / "w1_events.yaml")["events"]
D = load_dictionary()
P = load_monitoring_params()
CODES = load_code_table(D, P)
NS = 10**9
TAIL = "KH2011"
T_UP, T_TO = 60 * NS, 660 * NS  # engine start, take-off 10 min later (report §9: PBIT at power-up)


def _system(regime: str = "immature") -> System:
    cfg = MonitoringConfig.from_dictionary(D, CODES, ("IN20-0001",), regime=regime, tail_no=TAIL)
    m = MonitoringModule("m14", P, config=cfg)
    return System(
        [m], [], rng=RngService(0x9B17, StreamRegistry()), identity=KeyPath.of(scenario="PU", tail=TAIL)
    )


def _up(t: int, sid: str = "S1", tail: str = TAIL) -> Event:
    doc = {"tail_no": tail, "sortie_id": sid, "engine_starts": 1, "cold_soak": 0}
    return Event(t, "ops.power_up", "m14", plain_payload(doc), source="m02")


def _takeoff(t: int, sid: str = "S1") -> Event:
    doc = {k: 0 for k in TAKEOFF_KEYS} | {
        "sortie_id": sid,
        "tail_no": TAIL,
        "t_takeoff": t,
        "t_landing": t + NS,
    }
    return Event(t, "ops.takeoff", "m14", plain_payload(doc), source="m02")


def _run(sysm: System, evs, t_end: int):
    w = sysm.inject(sysm.start(), evs)
    w, _ = sysm.run(w, (t_end * 240) // NS + 2 - w.k)
    return w.states["m14"]


def test_power_up_event_is_catalogued_and_declared():
    spec = CAT["ops.power_up"]
    assert spec["producer"] == "M02" and "M14" in spec["consumers"] and not spec.get("planned")
    assert tuple(spec["payload"]) == POWER_UP_KEYS == EVENTS_IN["ops.power_up"]


def test_power_up_runs_pbit_at_engine_start_and_take_off_keeps_it():
    """A PBIT failure forced by an LRU condition is declared at the power-up instant, minutes before the
    take-off; CBIT runs from the power-up (its first declarations can precede the take-off)."""
    code = next(c.code for c in CODES.codes if c.src == "internal")
    cond = Event(0, "monitor.lru_condition", "m14", lru_condition_payload(code, 12.0, covered=True))
    st = _run(_system(), [cond, _up(T_UP), _takeoff(T_TO)], T_TO + NS)
    assert int(st["clock"][2]) == 1 and str(st["sortie_id"]) == "S1"
    assert int(st["clock"][1]) == T_UP  # the CBIT grid starts at engine start
    c = CODES.by_code[code].index
    pbit = (st["o_kind"] == KIND_BIT) & (st["o_code"] == c)
    assert pbit.any() and int(st["o_t"][pbit].min()) == T_UP


def test_pbit_outcome_is_the_same_whichever_event_powers_up():
    """Keyed per sortie and code: powering up at engine start only moves the PBIT records in time (12
    sorties of the immature regime, so that some PBIT records exist without a forced condition)."""
    records = {}
    for arm in ("power_up", "takeoff"):
        rows = []
        for k in range(12):
            sid = f"S{k}"
            evs = [_up(T_UP, sid), _takeoff(T_TO, sid)] if arm == "power_up" else [_takeoff(T_TO, sid)]
            st = _run(_system(), evs, T_TO + NS)
            t_on = T_UP if arm == "power_up" else T_TO
            pb = (st["o_kind"] == KIND_BIT) & (st["o_t"] == t_on) & (st["o_mech"] == MECHANISMS.index("PBIT"))
            rows.append(tuple(sorted(int(x) for x in st["o_code"][pb])))
        records[arm] = rows
    assert records["power_up"] == records["takeoff"]
    assert sum(len(r) for r in records["power_up"]) > 0, "no PBIT record in 12 sorties: the check is empty"


def test_power_up_protocol_errors_and_other_tails():
    sysm = _system()
    with pytest.raises(ContractError, match="while sortie"):
        _run(sysm, [_up(T_UP, "S1"), _up(T_UP + NS, "S2")], T_UP + 2 * NS)
    with pytest.raises(ContractError, match="take-off of"):
        _run(sysm, [_up(T_UP, "S1"), _takeoff(T_TO, "S2")], T_TO + NS)
    st = _run(sysm, [_up(T_UP, "S1"), _up(T_UP + NS, "S1")], T_UP + 2 * NS)  # repeated: a no-op
    assert int(st["clock"][2]) == 1 and int(st["clock"][1]) == T_UP
    st = _run(sysm, [_up(T_UP, "S1", tail="KH9999")], T_UP + NS)  # another tail's power-up is not ours
    assert int(st["clock"][2]) == 0 and st["o_kind"].size == 0


def test_m02_declares_the_power_up():
    """M02 (W2.1a) declares ``ops.power_up`` with the catalogued payload; the ``planned`` flag is gone."""
    m02 = importlib.import_module("phalanx.scenario.ports")
    assert tuple(dict(m02.EVENTS_OUT)["ops.power_up"]) == tuple(CAT["ops.power_up"]["payload"])
    assert "planned" not in CAT["ops.power_up"]
    assert np.isfinite(T_TO)
