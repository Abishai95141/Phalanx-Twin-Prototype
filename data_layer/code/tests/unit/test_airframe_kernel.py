"""M06 kernel force assembly: thrust line and moment arm (A-W1.2-12), mass-property inputs.

One deterministic state (aircraft at rest relative to the air at 10 km, so aerodynamic and ground forces are
absent); n = 2 CG positions.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.airframe.analysis import input_row, reference_mass_properties
from phalanx.airframe.build import airframe_param_set, build_config
from phalanx.airframe.geodesy import euler_to_quat, q_to_dcm
from phalanx.airframe.ic import initial_float_state
from phalanx.airframe.kernel import F_Q0, F_VX, F_WX, airframe_derivative

PS = airframe_param_set()
CFG = build_config(PS, 1)


@pytest.mark.unit
@pytest.mark.parametrize("cg", [(0.0, 0.0, 0.0), (0.2, 0.05, 0.1)])
def test_thrust_moment_arm(cg):
    """Thrust T along the configured axis through the configured point: the specific-force change is T/m on
    that axis, and J * (change of body angular acceleration) = (p_thrust - cg) x T exactly (no aero at zero
    airspeed, no ground contact at 10 km)."""
    m, _cg0, j = reference_mass_properties(PS)
    cg = np.asarray(cg)
    q = euler_to_quat(0.1, 0.05, 0.3)
    f = initial_float_state(
        math.radians(13.0),
        math.radians(77.6),
        10000.0,
        np.zeros(3),
        np.asarray(q),
        np.zeros(3),
        0.0,
        0.0,
        CFG.dp,
    )
    t = 50e3
    xd0, _ = airframe_derivative(
        f,
        CFG.dp,
        CFG.ap,
        CFG.tab,
        CFG.gtab,
        CFG.ttab,
        input_row(1, np.zeros(13), 0.0, m, cg, j, 10000.0),
        1,
        0,
    )
    xd1, _ = airframe_derivative(
        f, CFG.dp, CFG.ap, CFG.tab, CFG.gtab, CFG.ttab, input_row(1, np.zeros(13), t, m, cg, j, 10000.0), 1, 0
    )
    axis = CFG.ttab[0, 3:6]
    point = CFG.ttab[0, 0:3]
    ceb = np.zeros((3, 3))
    q_to_dcm(f[F_Q0], f[F_Q0 + 1], f[F_Q0 + 2], f[F_Q0 + 3], ceb)
    dv = xd1[F_VX : F_VX + 3] - xd0[F_VX : F_VX + 3]
    assert np.allclose(ceb.T @ dv, t / m * axis, rtol=1e-12, atol=1e-12)
    dw = xd1[F_WX : F_WX + 3] - xd0[F_WX : F_WX + 3]
    assert np.allclose(j @ dw, np.cross(point - cg, t * axis), rtol=1e-9, atol=1e-6)
    assert point[0] == pytest.approx(-5.0) and point[2] == 0.0 and np.array_equal(axis, [1.0, 0.0, 0.0])
