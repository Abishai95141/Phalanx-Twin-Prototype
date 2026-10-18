"""M05 actuator physics (A5, A6): servo response, rate law, stops, faults, complex-step safety, bitwise
reference.

Samples: single deterministic trajectories (0.2-2 s at 240 Hz); the complex-step check uses 120 ticks.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.airframe.build import airframe_param_set, hinge_table
from phalanx.core.time import TRUTH_DT_S
from phalanx.fcs.actuators import C_AREA, C_ARM, C_GCP, C_V0, C_WN, actuator_tick, actuator_tick_reference
from phalanx.fcs.build import actuator_table, fcs_param_set

PS = fcs_param_set()
ATAB = actuator_table(PS)
HTAB = hinge_table(airframe_param_set())
DPR = float(PS.value("dp_rated"))
DPMIN = float(PS.value("dp_min"))
N = 13


def _run(
    cmd, n, *, dp=(DPR, DPR), qbar=0.0, alpha=0.0, health=None, jam=None, pos0=None, atab=ATAB, dtype=float
):
    pos = np.zeros(N, dtype) if pos0 is None else np.asarray(pos0, dtype)
    vel = np.zeros(N, dtype)
    health = np.zeros(N, dtype) if health is None else np.asarray(health, dtype)
    jam = np.zeros(N, np.int64) if jam is None else np.asarray(jam, np.int64)
    cmd = np.asarray(cmd, dtype)
    dpa = np.asarray(dp, dtype)
    hist, rates, flows = [], [], []
    for _ in range(n):
        pos, vel, rate, flow = actuator_tick(
            pos, vel, cmd, dpa, alpha, 0.0, qbar, health, jam, atab, HTAB, DPR, DPMIN, TRUTH_DT_S, 2
        )
        hist.append(pos.copy())
        rates.append(rate.copy())
        flows.append(flow.copy())
    return np.array(hist), np.array(rates), np.array(flows)


@pytest.mark.unit
def test_small_signal_bandwidth_is_9_hz():
    """A 0.5 deg sine at 9 Hz (no load, rated pressure) comes out at |H| = 1/(2 zeta) = 0.714 (-2.9 dB) +/-5
    %:
    the second-order servo with the published ~9 Hz natural frequency."""
    f = 9.0
    n = 480
    pos = np.zeros(N)
    vel = np.zeros(N)
    out = []
    for k in range(n):
        cmd = np.zeros(N)
        cmd[0] = math.radians(0.5) * math.sin(2 * math.pi * f * k * TRUTH_DT_S)
        pos, vel, _, _ = actuator_tick(
            pos,
            vel,
            cmd,
            np.array([DPR, DPR]),
            0.0,
            0.0,
            0.0,
            np.zeros(N),
            np.zeros(N, np.int64),
            ATAB,
            HTAB,
            DPR,
            DPMIN,
            TRUTH_DT_S,
            2,
        )
        out.append(pos[0])
    tail = np.array(out[240:])
    amp = 0.5 * (tail.max() - tail.min())
    assert abs(amp / math.radians(0.5) - 1 / (2 * 0.7)) < 0.05 * 0.714


@pytest.mark.unit
def test_no_load_rate_limit_and_stops():
    """A full-travel step runs at the no-load rate (80 deg/s elevon, 100 deg/s rudder) and stops at the
    limits."""
    cmd = np.array([math.radians(40.0)] * 4 + [math.radians(60.0)] + [math.radians(40.0)] * 6 + [1.5, 1.5])
    hist, rates, _ = _run(cmd, 480)
    assert abs(np.max(rates[:, 0]) - ATAB[0, C_V0]) < 1e-6 * ATAB[0, C_V0] + 1e-9
    assert abs(np.max(rates[:, 4]) - ATAB[4, C_V0]) < 1e-6 * ATAB[4, C_V0] + 1e-9
    assert np.all(hist[-1] <= ATAB[:, 1] + 1e-15)
    assert hist[-1, 0] == ATAB[0, 1] and hist[-1, 4] == ATAB[4, 1]  # on the mechanical stop
    assert rates[-1, 0] == 0.0


@pytest.mark.unit
def test_surface_freezes_when_hydraulics_lost():
    """Exposes the A-W1.2-20 simplification: with both systems below dp_min a surface holds its position (a
    real
    unpowered surface would float to its hinge-moment equilibrium). Slats (system 2 only) freeze when system 2
    alone is lost while the tandem elevons keep moving on system 1."""
    cmd = np.full(N, math.radians(10.0))
    hist, _, flows = _run(cmd, 120, dp=(0.0, 0.0), qbar=20000.0, pos0=np.full(N, 0.01))
    assert np.allclose(hist[-1], 0.01)
    assert np.all(flows == 0.0)
    hist2, _, flows2 = _run(cmd, 120, dp=(DPR, 0.0), pos0=np.zeros(N))
    assert hist2[-1, 0] > math.radians(9.0)  # elevon on system 1 section
    assert np.allclose(hist2[-1, 5:11], 0.0)  # slats on system 2 frozen
    assert np.all(flows2[:, 1] == 0.0) and np.all(flows2[:, 0] > 0.0)


@pytest.mark.unit
def test_jam_and_servo_leak_droop():
    """A jammed surface does not move; cross-port leakage (health) makes a loaded actuator droop (servo error
    grows with leakage) - the PHM signature the M10 actuator health is meant to produce."""
    cmd = np.full(N, math.radians(5.0))
    jam = np.zeros(N, np.int64)
    jam[1] = 1
    hist, _, _ = _run(cmd, 240, jam=jam)
    assert hist[-1, 1] == 0.0 and hist[-1, 0] > math.radians(4.9)
    errs = []
    for h in (0.0, 10.0, 100.0):
        hist, _, _ = _run(cmd, 480, qbar=40000.0, health=np.full(N, h))
        errs.append(abs(hist[-1, 0] - cmd[0]))
    assert errs[0] < errs[1] < errs[2]
    assert errs[2] > 10 * errs[0]


@pytest.mark.unit
def test_kernel_bitwise_equals_numpy_reference():
    """Compiled actuator_tick == its py_func (same source, uncompiled) bitwise over 240 ticks with load and
    leak."""
    args0 = None
    pos = np.zeros(N)
    vel = np.zeros(N)
    pr, vr = pos.copy(), vel.copy()
    g = np.random.Generator(np.random.Philox(51))  # fixed test input, not a simulation stream
    for _ in range(240):
        cmd = g.uniform(-0.3, 0.3, N)
        h = np.full(N, 2.0)
        args0 = (
            cmd,
            np.array([2.5e7, 2.2e7]),
            0.1,
            0.02,
            30000.0,
            h,
            np.zeros(N, np.int64),
            ATAB,
            HTAB,
            DPR,
            DPMIN,
        )
        pos, vel, rate, flow = actuator_tick(pos, vel, *args0, TRUTH_DT_S, 2)
        pr, vr, rate_r, flow_r = actuator_tick_reference(pr, vr, *args0, TRUTH_DT_S, 2)
        assert np.array_equal(pos, pr) and np.array_equal(vel, vr)
        assert np.array_equal(rate, rate_r) and np.array_equal(flow, flow_r)
    assert args0 is not None


@pytest.mark.unit
@pytest.mark.parametrize("col", [C_V0, C_WN, C_AREA, C_ARM, C_GCP])
def test_complex_step_matches_central_difference(col):
    """AD-34: d(final elevon position)/d(parameter) by complex step (h = 1e-30) through the same kernel equals
    the
    central finite difference to 1e-5 relative, for a rate-saturated, loaded, leaking manoeuvre (120
    ticks)."""
    base = np.array(ATAB)
    cmd = np.zeros(N)
    cmd[0] = math.radians(20.0)

    def final(at, dtype):
        hist, _, _ = _run(cmd, 120, qbar=35000.0, alpha=0.05, health=np.full(N, 50.0), atab=at, dtype=dtype)
        return hist[-1, 0]

    h = 1e-30
    atc = base.astype(np.complex128)
    atc[0, col] += 1j * h * base[0, col]
    d_cs = final(atc, np.complex128).imag / (h * base[0, col])
    eps = 1e-6
    ap, am = base.copy(), base.copy()
    ap[0, col] *= 1 + eps
    am[0, col] *= 1 - eps
    d_fd = (final(ap, float) - final(am, float)) / (2 * eps * base[0, col])
    assert d_cs != 0.0
    assert abs(d_cs - d_fd) <= 1e-5 * abs(d_cs) + 1e-12, (d_cs, d_fd)
    assert final(base.astype(np.complex128), np.complex128).real == final(base, float)
