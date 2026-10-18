"""AD-47 (W2.1c): brakes and chute are ports, not M06 events.

- ``pilot.brake_cmd`` (toe brakes L/R, 0..1) scales the brake torque the **brake system's supply** allows:
  T = cmd x min(brake_torque_max, brake_torque_gain x min(brake_p_max, util.hyd_p[brake_hyd_system]))
  (A-W1.4-32: "M06 must limit brake torque by the supply"). The gain, metered maximum and system index are
  M09's brake hardware values, tied here to ``M09.yaml``.
- ``util.chute_state`` (M09: 0 stowed, 1 streamed, 2 jettisoned, 3 failed) applies the chute drag only while
  streamed, so M09's deploy-speed limits and failures govern (a deploy above the emergency limit fails).

Deterministic kernel runs on a level runway from 30 m/s in a near-vacuum (rolling friction 0, as
``test_airframe_ground.py``), 1 s settle + 2 s braking per case (n = 1 run per case, 6 cases); chute cases are
single evaluations at the M0.25 / 1 km trim.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from test_airframe_ground import CG, PS, Ground, J, M, _vacuum

from phalanx.airframe.analysis import Condition, make_ic, trim
from phalanx.airframe.build import build_config
from phalanx.airframe.ic import initial_float_state
from phalanx.airframe.kernel import (
    N_SURF,
    O_ALPHA,
    O_BETA,
    O_FX,
    O_PBL,
    O_QBAR,
    O_VN,
    U_BRAKE,
    U_CHUTE,
    U_HYDP,
    airframe_outputs,
)
from phalanx.core.events import Event
from phalanx.dictionary.params import load_params
from phalanx.utilities import Utilities, UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L

pytestmark = pytest.mark.integration
O = N_SURF + 1  # first column after the single engine's thrust
BAR = 1.0e5


def _brake_run(cmd=(1.0, 1.0), hyd=(280 * BAR, 280 * BAR)):
    """Mean brake force per main wheel [N] over 2 s of braking after a 1 s settle: the absorbed power
    (af.brake_energy_rate) over the ground speed (the wheels roll without slip, PROXY A-W1.2-10)."""
    g = Ground(v=30.0, atmosphere=_vacuum, mu_roll=0.0)
    g.u[O + U_HYDP : O + U_HYDP + 2] = hyd
    g.run(240)
    g.u[O + U_BRAKE : O + U_BRAKE + 2] = cmd
    out = g.run(480)
    v = np.linalg.norm(out[:, O_VN : O_VN + 3], axis=1)
    return (out[:, O_PBL : O_PBL + 2] / v[:, None]).mean(axis=0)


def test_brake_parameters_are_m09s():
    """The supply limit uses M09's brake hardware: gain, metered maximum and system index equal M09.yaml."""
    m09 = {k: v for s in load_params("M09").values() for k, v in s.items()}
    for m06_key, m09_key in (
        ("brake_torque_gain", "brk_torque_gain"),
        ("brake_p_max", "brk_p_max"),
        ("brake_hyd_system", "brk_hyd_system"),
    ):
        assert float(PS.value(m06_key)) == float(m09[m09_key].value), m06_key


def test_brake_torque_is_limited_by_the_brake_system_supply():
    """At 30 bar on the brake system (SYS2) the torque is gain x 30 bar, below the anti-skid cap: the brake
    force is that torque over the rolling radius (0.5 %: the friction-sign regularisation). With the brake
    system at 0 bar there is no braking even with full pedal; the other system's pressure does not matter; at
    the nominal 280 bar the anti-skid cap mu_brake_max x N binds (W1 behaviour), well above the low-supply
    force."""
    gain, r = float(PS.value("brake_torque_gain")), float(PS.value("r_roll"))
    p_low = 30 * BAR
    f_low = _brake_run(hyd=(280 * BAR, p_low))
    assert f_low == pytest.approx(np.full(2, gain * p_low / r), rel=0.005)
    assert np.all(_brake_run(hyd=(280 * BAR, 0.0)) == 0.0)
    f_sys1_out = _brake_run(hyd=(0.0, 280 * BAR))  # SYS1 failed: the brakes are on SYS2
    f_nom = _brake_run()
    assert np.array_equal(f_sys1_out, f_nom)
    mu = float(PS.value("mu_brake_max"))
    assert np.all(f_nom < mu * M * 9.81)  # anti-skid capped (two mains share the weight with the nose)
    p_max = float(PS.value("brake_p_max"))
    assert np.all(f_nom < 0.5 * gain * min(p_max, 280 * BAR) / r)  # far below the nominal supply limit
    assert np.all(f_nom > 1.5 * f_low)


def test_brake_command_scales_and_clips():
    """Half pedal gives half the supply-limited torque; the command is clipped to [0, 1]."""
    p_low = 30 * BAR
    full = _brake_run(hyd=(280 * BAR, p_low))
    half = _brake_run(cmd=(0.5, 0.5), hyd=(280 * BAR, p_low))
    over = _brake_run(cmd=(1.5, 1.5), hyd=(280 * BAR, p_low))
    neg = _brake_run(cmd=(-0.2, -0.2), hyd=(280 * BAR, p_low))
    assert half == pytest.approx(0.5 * full, rel=0.005)
    assert np.array_equal(over, full) and np.all(neg == 0.0)


def _trim_point():
    cfg = build_config(PS, 1)
    cond = Condition(1000.0, 0.25, M, CG, J)
    tr = trim(cfg, cond, guess=(0.2, 0.0, 3e4))
    ic = make_ic(cfg, cond, tr, h_ground=0.0)
    f = initial_float_state(
        ic.lat, ic.lon, ic.h, np.asarray(ic.vel_ned), np.asarray(ic.quat_nb), np.zeros(3), 0.0, 0.0, cfg.dp
    )
    return cfg, tr, f


def _chute_force(state: int) -> np.ndarray:
    cfg, tr, f = _trim_point()
    u = tr.u.copy()
    u[O + U_CHUTE] = state
    base = airframe_outputs(f, cfg.dp, cfg.ap, cfg.tab, cfg.gtab, cfg.ttab, tr.u, 1, 0)
    out = airframe_outputs(f, cfg.dp, cfg.ap, cfg.tab, cfg.gtab, cfg.ttab, u, 1, 0)
    return (out[O_FX : O_FX + 3] - base[O_FX : O_FX + 3]), base


def test_chute_drag_only_while_streamed():
    """util.chute_state 1 adds qbar CdS / m along -v_air; stowed (0), jettisoned (2) and failed (3) add
    none."""
    d1, base = _chute_force(1)
    a, b = base[O_ALPHA], base[O_BETA]
    unit = np.array([math.cos(a) * math.cos(b), math.sin(b), math.sin(a) * math.cos(b)])
    expected = -base[O_QBAR] * float(PS.value("chute_cds")) / M * unit
    assert np.allclose(d1, expected, rtol=1e-9, atol=1e-12)
    for s in (0, 2, 3):
        assert np.all(_chute_force(s)[0] == 0.0), s


def test_m09_chute_state_drives_m06_drag():
    """End to end at the port: M09 streams the chute below its normal deploy limit (state 1, M06 drag) and
    fails it above the emergency limit (state 3, no drag); a jettison (state 2) removes the drag."""
    ps = load_m09_params()
    m09 = Utilities("util", ps, config=UtilitiesConfig(engine_running=True))
    v_ok = 0.9 * float(ps.value("chute_v_normal"))
    v_bad = 1.1 * float(ps.value("chute_v_emerg"))
    states = []
    for v, jettison in ((v_ok, False), (v_bad, False), (v_ok, True)):
        st = m09.init(ps, None)
        st["f"][L.F_LAST_TAS] = v  # TEST FIXTURE: the TAS M09 saw on its last step
        st, _ = m09.on_event(st, Event(0, "util.chute_deploy", "util", {"tail": "T", "emergency": False}), 0)
        if jettison:
            st, _ = m09.on_event(st, Event(1, "util.chute_jettison", "util", {"tail": "T"}), 1)
        states.append(int(m09.initial_outputs(st)["chute_state"]))
    assert states == [1, 3, 2]
    drag = [bool(np.any(_chute_force(s)[0] != 0.0)) for s in states]
    assert drag == [True, False, False]
