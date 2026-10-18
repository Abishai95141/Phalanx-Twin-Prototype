"""M02 emits the catalogued ``ops.power_up`` (W2.5 request to W2.1a; A-W2.1-11).

On the integrated telemetry System (first gate sortie, n = 1 plan, the first 1-3 s of the window):

- at the window start (the engine start is just before it, AD-46) M02 sends ``ops.power_up`` {tail_no,
  sortie_id, engine_starts, cold_soak} to M05, M11 and M14; M05 runs its PBIT from it (no ``fcs.pbit_start``),
  M14 powers up (no runner ``monitor.sortie_start`` hook), M11 opens the pre-sortie (preflight draws);
- ``cold_soak`` is 1 exactly when the sortie's station temperature is at or below ``cold_soak_temperature``;
- a start failure (``ops.start_failure``, as M11 sends it) before the take-off ground-aborts the sortie: M02
  closes M11 and M14 with an aborted ``ops.sortie_done``, a second one is counted late, and the runner ends
  the run as ``SortieAborted('ground_abort')``.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.environment.climatology import A_T_STN
from phalanx.fcs.layout import I_PBIT
from phalanx.integration.plans import gate_sorties
from phalanx.integration.sortie import SortieAborted, SortieRunner, SortieState
from phalanx.integration.system import SortieSpec, build_sortie_system
from phalanx.scenario.module import POWER_UP_KEYS, read_doc

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def ss():
    return build_sortie_system(SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5))


def _failure(ss, t_ns: int) -> Event:
    pay = {"tail_no": ss.window.tail, "sortie_id": ss.window.sortie_id, "mode": "FM.SPS.JFS_COLD_START_FAIL"}
    return Event(t_ns, "ops.start_failure", "scenario", pay, source="faults")


def test_power_up_at_the_window_start(ss):
    w = ss.system.inject(ss.start(), ss.bootstrap_events())
    w, tr = ss.system.run(w, 240)
    ups = [(k, e) for k, e in tr.dispatched if e.kind == "ops.power_up"]
    assert sorted(e.target for _k, e in ups) == ["faults", "fcs", "monitor"]
    assert {k for k, _e in ups} == {0}
    for _k, e in ups:
        assert set(e.payload) == set(POWER_UP_KEYS)
        assert str(np.asarray(e.payload["sortie_id"])) == ss.window.sortie_id
        assert int(np.asarray(e.payload["engine_starts"])) == 1
    kinds = {e.kind for _k, e in tr.dispatched}
    assert "fcs.pbit_start" not in kinds and "monitor.sortie_start" not in kinds
    assert int(np.asarray(w.states["monitor"]["clock"])[2]) == 1  # M14 powered (PBIT)
    assert int(np.asarray(w.states["fcs"]["i"])[I_PBIT]) != 0  # M05 PBIT started from the power-up
    assert str(w.states["faults"]["pre_sortie"]) == ss.window.sortie_id


def test_cold_soak_follows_the_station_temperature(ss):
    m02 = ss.modules["scenario"]
    thr = float(m02.p.cold_soak_k)
    for dt_k, cold in ((-0.5, 1), (0.0, 1), (0.5, 0)):
        amb = np.array(ss.window.ambient, dtype=np.float64, copy=True)
        amb[A_T_STN] = thr + dt_k
        assert m02._power_up(replace(ss.window, ambient=amb))["cold_soak"] == cold


def test_start_failure_ground_aborts_and_closes_m11_m14(ss):
    w = ss.system.inject(ss.start(), [*ss.bootstrap_events(), _failure(ss, 2 * 10**9)])
    w, tr = ss.system.run(w, 3 * 240)
    done = [e for _k, e in tr.dispatched if e.kind == "ops.sortie_done"]
    assert sorted(e.target for e in done) == ["faults", "monitor"]
    assert all(bool(np.asarray(e.payload["aborted"])) for e in done)
    assert all(float(np.asarray(e.payload["flight_hours"])) == 0.0 for e in done)
    assert ss.modules["scenario"].aborted(w.states["scenario"])
    assert int(np.asarray(w.states["monitor"]["clock"])[2]) == 0  # M14 powered down
    w = ss.system.inject(w, [_failure(ss, w.k * 10**9 // 240 + 10**9)])
    w, _ = ss.system.run(w, 2 * 240)
    assert read_doc(w.states["scenario"])["start_failure_late"] == 1


def test_runner_ends_a_ground_aborted_sortie(ss):
    r = SortieRunner(ss, validate_events=True)
    st = r.begin()
    st = SortieState(
        ss.system.inject(st.world, [_failure(ss, 10**9)]), st.rec, st.usage, st.started, st.ended
    )
    with pytest.raises(SortieAborted) as ei:
        r.run(st, 3 * 240)
    assert ei.value.kind == "ground_abort"
    assert r.validator.violations == []
