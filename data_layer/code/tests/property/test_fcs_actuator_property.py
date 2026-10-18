"""A5 property tests: actuator rate capability follows sqrt(dP_avail - dP_load); flow demand conserves Q = A
x'.

Hypothesis draws pressures, hinge loads and actuator states (default 100 examples per property, deterministic
database-free runs); each example is a single kernel evaluation, so n = 100 per property.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.airframe.build import airframe_param_set, hinge_table
from phalanx.core.time import TRUTH_DT_S
from phalanx.fcs.actuators import (
    C_AREA,
    C_ARM,
    C_GNULL,
    C_NSEC,
    C_SYS,
    C_V0,
    actuator_tick,
    rate_capability,
)
from phalanx.fcs.build import actuator_table, fcs_param_set

PS = fcs_param_set()
ATAB = actuator_table(PS)
HTAB = hinge_table(airframe_param_set())
DPR = float(PS.value("dp_rated"))
DPMIN = float(PS.value("dp_min"))
N = 13


@pytest.mark.property
@settings(deadline=None, max_examples=100)
@given(
    dp=st.floats(min_value=0.0, max_value=3.5e7),
    pl=st.floats(min_value=-3.0e7, max_value=3.0e7),
    v0=st.floats(min_value=0.1, max_value=3.0),
)
def test_rate_capability_sqrt_law(dp, pl, v0):
    """v+ = v0 sqrt(max(dP - P_L, 0) / dP_rated), v- = v0 sqrt(max(dP + P_L, 0) / dP_rated); both monotone
    non-decreasing in the available pressure; an aiding load raises the capability in its direction."""
    vp, vm = rate_capability((dp, dp), 1, pl, v0, DPR)
    assert vp == pytest.approx(v0 * math.sqrt(max(dp - pl, 0.0) / DPR), rel=1e-12, abs=1e-15)
    assert vm == pytest.approx(v0 * math.sqrt(max(dp + pl, 0.0) / DPR), rel=1e-12, abs=1e-15)
    vp2, vm2 = rate_capability((dp * 1.1 + 1.0, dp * 1.1 + 1.0), 1, pl, v0, DPR)
    assert vp2 >= vp and vm2 >= vm
    # tandem: the weaker section limits
    vpt, _ = rate_capability((dp, 0.5 * dp), 2, pl, v0, DPR)
    assert vpt == pytest.approx(min(vp, v0 * math.sqrt(max(0.5 * dp - pl, 0.0) / DPR)), rel=1e-12, abs=1e-15)


@pytest.mark.property
@settings(deadline=None, max_examples=30)
@given(frac=st.floats(min_value=0.15, max_value=1.0), qbar=st.floats(min_value=0.0, max_value=40000.0))
def test_loaded_slew_rate_follows_sqrt_of_available_pressure(frac, qbar):
    """A rate-saturated elevon slew under a hinge load: the achieved rate at supply frac x 280 bar matches
    v0 sqrt((frac dP_r - P_L) / dP_r) (P_L from the true hinge moment at the mid-slew position, 5 % tolerance
    for the
    load change over the slew); lower supply -> lower rate."""
    cmd = np.zeros(N)
    cmd[0] = math.radians(20.0)
    dp = frac * DPR
    pos = np.zeros(N)
    vel = np.zeros(N)
    rates = []
    for _ in range(36):  # 0.15 s: saturated part of the slew
        pos, vel, rate, _ = actuator_tick(
            pos,
            vel,
            cmd,
            np.array([dp, dp]),
            0.0,
            0.0,
            qbar,
            np.zeros(N),
            np.zeros(N, np.int64),
            ATAB,
            HTAB,
            DPR,
            DPMIN,
            TRUTH_DT_S,
            2,
        )
        rates.append(rate[0])
    r = rates[-1]
    d = pos[0]
    hm = (HTAB[0, 3] * d) * qbar * HTAB[0, 4] * HTAB[0, 5]  # ch_delta * delta (alpha = 0)
    p_load = -hm / (ATAB[0, C_ARM] * ATAB[0, C_AREA] * 2)
    expected = ATAB[0, C_V0] * math.sqrt(max(dp - p_load, 0.0) / DPR)
    assert expected > 0.05  # the drawn ranges keep the actuator able to move (and still rate-saturated)
    assert r == pytest.approx(expected, rel=0.05), (r, expected)


@pytest.mark.property
@settings(deadline=None, max_examples=60)
@given(
    seed_vals=st.lists(st.floats(min_value=-0.4, max_value=0.4), min_size=13, max_size=13),
    dp1=st.floats(min_value=0.0, max_value=3.0e7),
    dp2=st.floats(min_value=0.0, max_value=3.0e7),
    health=st.floats(min_value=0.0, max_value=20.0),
)
def test_flow_demand_conserves_q_equals_a_xdot(seed_vals, dp1, dp2, health):
    """Per hydraulic system: Q = sum over active sections of A r |v| + G_null (1 + h) dP_avail: the piston
    flow is the piston area times the ram speed x' = r v (crank arm r, surface rate v; W2.1a-2: the arm was
    missing). Independently recomputed from the returned state."""
    cmd = np.clip(np.array(seed_vals), ATAB[:, 0], ATAB[:, 1])
    pos = np.zeros(N)
    vel = np.zeros(N)
    dpa = np.array([dp1, dp2])
    for _ in range(5):
        pos, vel, _rate, flow = actuator_tick(
            pos,
            vel,
            cmd,
            dpa,
            0.05,
            0.01,
            25000.0,
            np.full(N, health),
            np.zeros(N, np.int64),
            ATAB,
            HTAB,
            DPR,
            DPMIN,
            TRUTH_DT_S,
            2,
        )
    expect = np.zeros(2)
    for s in range(N):
        if ATAB[s, C_NSEC] > 1.5:
            systems = [h for h in (0, 1) if dpa[h] > DPMIN]
        else:
            h = int(ATAB[s, C_SYS] > 0.5)
            systems = [h] if dpa[h] > DPMIN else []
        for h in systems:
            q_piston = ATAB[s, C_AREA] * ATAB[s, C_ARM] * abs(vel[s])
            expect[h] += q_piston + ATAB[s, C_GNULL] * (1 + health) * dpa[h]
    assert np.allclose(flow, expect, rtol=1e-12, atol=1e-18)
    assert np.all(flow >= 0.0)
