"""The integrated take-off (coordinator assignment to W2.1a; A-W2.1-8, A-W2.1-9, A-W1.2-25).

Sample: gate sortie 2 (TJ213, a MIL take-off in the clean configuration, ~10 t, with a run-up) from its run-up
(window start ``RUNUP``: engine at post-start idle, aircraft parked; n = 1 take-off), through the run-up check
against the brakes, the line-up, the take-off roll, the rotation, the lift-off and 30 s of the climb-out after
the gear-up. One run, shared by the tests (1 s chunks, the event validator on).

- run-up: the brakes hold the run-up check (ground speed below 0.5 m/s) at ~90 % N2 (M02 ``pla_runup``,
  ASSUMPTION A-W2.1-8). Measured before the fix: a MIL run-up broke away at the 54 kN thrust peak on this
  aircraft: the braked main tyres hold mu_s N_main, and the thrust's nose-down moment moves load to the
  unbraked nose wheel, so the hold limit is ~0.54 W (A-W2.1-8; the anti-skid limit is for a rolling wheel);
- rotation and lift-off: the pilot rotates at or above ``v_rotate`` through M05's ground law (aft stick:
  attitude-and-rate tracking, A-W2.1-9) and the aircraft lifts off below 100 m/s without over-rotating
  (pitch below 25 deg); the climb-out loses no height (at most 5 m below its running maximum after the
  gear-up), climbs at least 100 m in the 30 s and keeps alpha below 20 deg;
- departure: wings level (bank within 5 deg) below ``h_turn`` above the field in the climb-out; before the
  fix the departure turn banked 60 deg at 20-30 m and the aircraft flew into the ground (A-W2.1-9);
- phases follow physical events: M02's phase is TAKEOFF wherever the aircraft is on its wheels after the
  take-off starts, CLIMB starts only after the confirmed lift-off at 15 m above the field and climbing (the
  gear-up), and M02 sends ``ops.takeoff`` at that instant, the tick of the ``pilot.segment`` that left the
  take-off; the event validator sees no violation;
- the DFCC reads the free-stream alpha (vane calibration = the M12 local-flow nominal, A-W1.2-25): within
  1.5 deg of the truth in the climb-out (was 1.5x the truth).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.airframe.geodesy import quat_to_euler
from phalanx.fcs.layout import F_ALPHA
from phalanx.integration.plans import gate_sorties
from phalanx.integration.sortie import SortieRunner
from phalanx.integration.system import SortieSpec, build_sortie_system
from phalanx.pilot.kernel import P_HTURN, P_VROT
from phalanx.scenario import phases as P

pytestmark = pytest.mark.integration
PORTS = ["af.vel_ned", "af.hag", "af.alt", "af.alpha", "af.quat", "af.wow", "af.tas", "eng.thrust", "eng.n2",
         "scenario.phase", "pilot.stick_pitch"]  # fmt: skip
MAX_S = 180  # the run stops 30 s after the gear-up, at the latest here
N2_100 = 16810.0 * 2.0 * np.pi / 60.0


@pytest.fixture(scope="module")
def takeoff():
    ss = build_sortie_system(
        SortieSpec(plan=gate_sorties()[1], scenario="gate", root=0xA5, start_phase="RUNUP")
    )
    names = {str(n): int(c) for c, n in ss.dictionary.code_table("flight_phase")["codes"].items()}
    r = SortieRunner(ss, validate_events=True, record=PORTS)
    st = r.begin()
    rows: dict[str, list] = {p: [] for p in PORTS}
    events: list = []
    dfcc_alpha: list = []
    climb_k = None
    while st.world.k < MAX_S * 240:
        st, outs = r.run(st, 240)
        c = outs[0]
        for p in PORTS:
            rows[p].append(np.asarray(c.trace.ports[p]))
        events += [(k, e) for k, e in c.trace.dispatched]
        dfcc_alpha.append((st.world.k - 1, float(np.asarray(st.world.states["fcs"]["f"])[F_ALPHA])))
        ph = np.asarray(c.trace.ports["scenario.phase"])
        if climb_k is None and np.any(ph == names["CLIMB"]):
            climb_k = c.k0 + int(np.flatnonzero(ph == names["CLIMB"])[0])
        if climb_k is not None and st.world.k >= climb_k + 30 * 240:
            break
    data = {p: np.concatenate(v) for p, v in rows.items()}
    return ss, r, data, events, dfcc_alpha, climb_k, names


def _euler(q):
    return np.array([quat_to_euler(x) for x in q])


def test_brakes_hold_the_runup_check(takeoff):
    _ss, _r, d, *_ = takeoff
    k_run = slice(15 * 240, 30 * 240)  # the 30 s run-up, after the spool-up
    gs = np.hypot(d["af.vel_ned"][k_run, 0], d["af.vel_ned"][k_run, 1])
    n2 = d["eng.n2"][k_run, 0] / N2_100 * 100.0
    thrust = d["eng.thrust"][k_run, 0]
    print(f"run-up: N2 {n2.min():.1f}-{n2.max():.1f} %, thrust {thrust.min() / 1e3:.1f}-"
          f"{thrust.max() / 1e3:.1f} kN, ground speed max {gs.max():.3f} m/s")  # fmt: skip
    assert 88.0 <= n2.min() and n2.max() <= 92.0
    assert thrust.min() > 30e3
    assert gs.max() < 0.5, gs.max()


def test_rotation_lift_off_and_climb_out(takeoff):
    ss, _r, d, _ev, _a, climb_k, _names = takeoff
    assert climb_k is not None, "no gear-up within the window"
    wow_any = np.any(np.asarray(d["af.wow"]) != 0, axis=1)
    k_rot = int(np.flatnonzero(np.asarray(d["pilot.stick_pitch"]) > 0.05)[0])
    k_lof = k_rot + int(np.flatnonzero(~wow_any[k_rot:])[0])
    v_rot = float(ss.modules["pilot"].cfg.vector[P_VROT])
    h = d["af.alt"] - float(ss.window.field_elev_m)
    end = climb_k + 30 * 240
    theta = np.degrees(_euler(d["af.quat"][k_rot:end])[:, 1])
    climb = h[climb_k:end]
    loss = float(np.max(np.maximum.accumulate(climb) - climb))
    alpha = np.degrees(d["af.alpha"][k_lof:end])
    print(f"rotation at {d['af.tas'][k_rot]:.1f} m/s, lift-off at {d['af.tas'][k_lof]:.1f} m/s, pitch max "
          f"{theta.max():.1f} deg, alpha max {alpha.max():.1f} deg, climb {climb[-1] - climb[0]:.0f} m in "
          f"30 s, largest height loss {loss:.1f} m")  # fmt: skip
    assert d["af.tas"][k_rot] >= v_rot - 0.5
    assert d["af.tas"][k_lof] < 100.0
    assert theta.max() < 25.0, theta.max()
    assert loss <= 5.0, loss
    assert climb[-1] - climb[0] >= 100.0
    assert alpha.max() < 20.0


def test_departure_is_wings_level_below_h_turn(takeoff):
    ss, _r, d, _ev, _a, _climb_k, names = takeoff
    h = d["af.alt"] - float(ss.window.field_elev_m)
    h_turn = float(ss.modules["pilot"].cfg.vector[P_HTURN])
    ph = np.asarray(d["scenario.phase"])
    low = np.flatnonzero((ph == names["CLIMB"]) & (h < h_turn))
    assert low.size > 240  # the climb-out spends seconds below h_turn
    bank = np.degrees(_euler(d["af.quat"][low])[:, 0])
    assert np.abs(bank).max() < 5.0, np.abs(bank).max()


def test_phases_follow_physical_events(takeoff):
    ss, r, d, events, _a, climb_k, names = takeoff
    ph = np.asarray(d["scenario.phase"])
    wow_any = np.any(np.asarray(d["af.wow"]) != 0, axis=1)
    k_to = int(np.flatnonzero(ph == names["TAKEOFF"])[0])
    on_wheels = np.flatnonzero(wow_any[k_to:]) + k_to
    assert np.all(ph[on_wheels] == names["TAKEOFF"])  # never CLIMB on the runway
    h = d["af.alt"] - float(ss.window.field_elev_m)
    assert h[climb_k] >= 15.0
    assert d["af.vel_ned"][climb_k, 2] < 0.0
    assert not wow_any[climb_k - 240 : climb_k].any()
    seg = [(k, e) for k, e in events if e.kind == "pilot.segment"]
    to = [(k, e) for k, e in events if e.kind == "ops.takeoff"]
    left = [k for k, e in seg if int(e.payload["fine"]) != P.TAKEOFF and k > k_to]
    assert to and left and {k for k, _ in to} == {left[0]}
    assert {e.target for _k, e in to} == {"faults", "health", "monitor"}
    assert r.validator.violations == []


def test_dfcc_reads_the_free_stream_alpha(takeoff):
    _ss, _r, d, _ev, dfcc_alpha, climb_k, _names = takeoff
    pairs = [(k, a) for k, a in dfcc_alpha if climb_k + 10 * 240 <= k < climb_k + 30 * 240]
    assert pairs
    err = [abs(np.degrees(a - d["af.alpha"][k])) for k, a in pairs]
    assert max(err) < 1.5, err
