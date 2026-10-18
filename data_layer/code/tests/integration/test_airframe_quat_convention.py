"""AD-49: ``af.quat`` is scalar-first (w, x, y, z) and rotates body vectors into NED - confirmed against
M06's own physics, not against its helper functions.

- **Direction:** with the velocity due north and the attitude yawed 10 deg right and pitched 5 deg up, M06's
  own aerodynamic angles (computed through its quaternion) are alpha = +5 deg and beta = -10 deg exactly;
  the NED -> body reading of the same four numbers would give alpha = -5 deg, beta = +10 deg.
- **Scalar first:** the published quaternion equals an independent scalar-first 3-2-1 construction
  (``Rz(psi) Ry(theta) Rx(phi)`` written as a Hamilton product of axis rotations), not the scalar-last one.
- **Kinematics:** a positive body roll, pitch or yaw rate from level flight increases roll, pitch or heading
  of the published quaternion (q_dot = q x omega_body / 2).
- The catalogue entry (``w1_ports.yaml`` ``af.quat``) states the same convention.

Kernel runs at 3 km, 150 m/s, gear up, fixed input row (``test_airframe_ground`` mass properties): 1 frame for
the direction check, 24 frames (0.1 s) per rate axis plus a no-rate baseline (n = 6 runs).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from test_airframe_ground import CG, LAT, LON, PS, J, M

from phalanx.airframe.analysis import input_row
from phalanx.airframe.build import build_config
from phalanx.airframe.geodesy import euler_to_quat, quat_to_euler
from phalanx.airframe.ic import initial_float_state
from phalanx.airframe.kernel import N_I, O_ALPHA, O_BETA, O_QN0, airframe_kernel
from phalanx.core.time import TRUTH_DT_S
from phalanx.dictionary.yamlio import load_yaml

pytestmark = pytest.mark.integration
CFG = build_config(PS, 1)
V = 150.0


def fly(q, omega=(0.0, 0.0, 0.0), n=1) -> np.ndarray:
    """TEST FIXTURE: M06's kernel from an in-flight state (velocity due north, given attitude and rate)."""
    u = input_row(1, np.zeros(13), 0.0, M, CG, J, 0.0, gear_cmd=0)
    f = initial_float_state(
        LAT, LON, 3000.0, np.array([V, 0.0, 0.0]), np.asarray(q), np.asarray(omega), 0.0, 0.0, CFG.dp
    )
    i = np.zeros(N_I, dtype=np.int64)
    c = CFG
    _, _, out = airframe_kernel(f, i, c.dp, c.ap, c.tab, c.gtab, c.ttab, np.tile(u, (n, 1)), TRUTH_DT_S, 1, 0)
    return out


def _hamilton(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ]
    )


def _axis(k, ang):
    q = np.zeros(4)
    q[0] = math.cos(ang / 2.0)
    q[1 + k] = math.sin(ang / 2.0)
    return q


def test_quat_rotates_body_into_ned():
    psi, theta = math.radians(10.0), math.radians(5.0)
    out = fly(euler_to_quat(0.0, theta, psi))[0]
    assert math.degrees(out[O_ALPHA]) == pytest.approx(5.0, abs=0.05)
    assert math.degrees(out[O_BETA]) == pytest.approx(-10.0, abs=0.05)


def test_quat_is_scalar_first_hamilton_3_2_1():
    phi, theta, psi = 0.3, 0.2, 1.1
    q_ref = _hamilton(_hamilton(_axis(2, psi), _axis(1, theta)), _axis(0, phi))  # z, then y, then x
    q = fly(q_ref)[0, O_QN0 : O_QN0 + 4]
    assert np.allclose(q, q_ref, atol=1e-4) or np.allclose(q, -q_ref, atol=1e-4)
    assert not np.allclose(q, np.roll(q_ref, -1), atol=1e-2)  # not scalar-last
    assert np.allclose(np.asarray(euler_to_quat(phi, theta, psi)), q_ref, atol=1e-12)


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_positive_body_rates_increase_the_euler_angles(axis):
    """Against the same 0.1 s with no initial rate (the untrimmed aircraft pitches on its own)."""
    omega = np.zeros(3)
    omega[axis] = 0.2
    q0 = euler_to_quat(0.0, 0.0, 0.0)
    base = np.array(quat_to_euler(fly(q0, n=24)[-1, O_QN0 : O_QN0 + 4]))
    d = np.array(quat_to_euler(fly(q0, omega, n=24)[-1, O_QN0 : O_QN0 + 4])) - base
    assert d[axis] > 0.5 * 0.2 * 24 * TRUTH_DT_S  # the commanded axis moved the right way
    assert abs(d[axis]) > 5 * np.max(np.abs(np.delete(d, axis)))  # and dominates the others


def test_catalogue_states_the_convention():
    ports = load_yaml(Path(__file__).resolve().parents[2] / "configs" / "interfaces" / "w1_ports.yaml")
    text = str(ports)
    assert "scalar-first (w, x, y, z), body -> NED" in text
