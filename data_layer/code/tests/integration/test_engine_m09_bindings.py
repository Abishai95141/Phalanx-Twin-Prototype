"""M07 side of the M09 couplings (W2.1b): the oil model's sink is `util.fuel_inlet_t`, and `util.pto_power`
follows the M09 start-drive convention (P = min(P_avail, T_peak (w + w_floor)); M07 applies the load torque
P / (N2 + 1 rad/s), so a negative power is a starter drive).

Samples: kernel derivatives at the design point and at a stopped HP spool (exact relations); one 60 s
open-loop module run pair at the design point for the oil sink (n = 14,400 steps each).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.engine.design import build_engine_model
from phalanx.engine.kernel import N_FLOOR, deriv_point
from phalanx.engine.layout import P_NAMES, PTO_W_FLOOR, U_NAMES, X_N2, X_TOIL
from phalanx.engine.module import EngineModule

pytestmark = pytest.mark.integration
U_PTO, U_TFUEL = U_NAMES.index("pto_power"), U_NAMES.index("t_fuel")


@pytest.fixture(scope="module")
def model():
    return build_engine_model()


def _dn2(model, x, u):
    dx, _ = deriv_point(x, 0, 1, 0, 0.0, u, model.p, model.tables, -1.0)
    return float(dx[X_N2])


def test_pto_power_is_converted_to_torque_with_the_m09_floor(model):
    eng = EngineModule("eng", model)
    x, u = eng._init_x.copy(), eng._init_u.copy()
    i_hp = float(model.p[P_NAMES.index("i_hp")])
    base = _dn2(model, x, u)
    for p_w in (50e3, -50e3):
        u2 = u.copy()
        u2[U_PTO] = p_w
        want = -p_w / (x[X_N2] + PTO_W_FLOOR) / i_hp
        assert _dn2(model, x, u2) - base == pytest.approx(want, rel=1e-9)
    # extraction decelerates, a starter drive accelerates
    u2 = u.copy()
    u2[U_PTO] = 50e3
    assert _dn2(model, x, u2) < base
    # a slow spool (starter regime, 50 rad/s): the same exact relation, and a starter drive accelerates it
    xs = x.copy()
    xs[X_N2] = 50.0
    u0, us = u.copy(), u.copy()
    u0[U_PTO], us[U_PTO] = 0.0, -20e3
    assert _dn2(model, xs, us) - _dn2(model, xs, u0) == pytest.approx(
        20e3 / (50.0 + PTO_W_FLOOR) / i_hp, rel=1e-9
    )
    # a stopped spool: the kernel's speed guard (N_FLOOR) bounds the torque; the starter still turns it
    xs[X_N2] = 0.0
    assert _dn2(model, xs, us) - _dn2(model, xs, u0) == pytest.approx(
        20e3 / (N_FLOOR + PTO_W_FLOOR) / i_hp, rel=1e-9
    )


def test_fuel_inlet_temperature_is_the_oil_cooler_sink(model):
    """A 20 K warmer fuel inlet (M09) warms the oil: the derivative at the design point and the 60 s
    response."""
    eng = EngineModule("eng", model)
    x, u = eng._init_x.copy(), eng._init_u.copy()
    dx0, _ = deriv_point(x, 0, 1, 0, 0.0, u, model.p, model.tables, -1.0)
    u2 = u.copy()
    u2[U_TFUEL] += 20.0
    dx1, _ = deriv_point(x, 0, 1, 0, 0.0, u2, model.p, model.tables, -1.0)
    assert dx1[X_TOIL] > dx0[X_TOIL]

    n = 60 * 240
    s0 = eng.init(eng.params, None)
    e = eng.n_engines

    def inputs(t_fuel):
        return {
            "wf_cmd": np.full((n, e), u[0]),
            "wf_ab_cmd": np.zeros((n, e)),
            "a8_cmd": np.full((n, e), u[2]),
            "vg_cmd": np.broadcast_to(u[3:5], (n, e, 2)).copy(),
            "ignition": np.zeros((n, e), np.int64),
            "ab_enable": np.zeros((n, e), np.int64),
            "t_s": np.full(n, 288.15),
            "p_s": np.full(n, 101325.0),
            "q_spec": np.zeros(n),
            "mach": np.zeros(n),
            "w_engine": np.zeros((n, e, 5)),
            "bleed_extract": np.zeros((n, e)),
            "pto_power": np.zeros((n, e)),
            "fuel_inlet_t": np.full((n, e), t_fuel),
            "health": np.zeros((n, e, 10)),
        }

    t = np.arange(n, dtype=np.int64)
    _, ya = eng.step_block(s0, inputs(u[U_TFUEL]), t, 1.0 / 240.0)
    _, yb = eng.step_block(s0, inputs(u[U_TFUEL] + 20.0), t, 1.0 / 240.0)
    rise = float(yb["oil_t"][-1, 0] - ya["oil_t"][-1, 0])
    assert 0.0 < rise <= 20.0 + 1e-9, rise  # the sink pulls the oil up, never by more than the sink moved
    assert np.array_equal(ya["n2"], yb["n2"])  # the oil loop does not feed back on the spools
