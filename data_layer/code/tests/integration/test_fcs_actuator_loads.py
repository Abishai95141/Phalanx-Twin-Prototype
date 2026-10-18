"""Actuator loads (A-W1.2-9, -21): the aerodynamic hinge moments met in limit manoeuvres at the highest
dynamic pressures stay well inside the primary actuators' stall moment (piston area x sections x 280 bar x
crank arm), so the surfaces are rate-limited, never blown back, inside the flight envelope.

Closed loop through the TEST FIXTURE harness: full aft stick (g-limited pull) then full roll, 6 s at
M0.9 / 1 km (qbar ~51 kPa, ~8.6 g) and M1.2 / 3 km (qbar ~71 kPa); n = 2 deterministic runs.
"""

from __future__ import annotations

import numpy as np
import pytest
from test_fcs_fixtures import Harness, nz_of

from phalanx.airframe.aero import hinge_moments
from phalanx.airframe.kernel import O_ALPHA, O_BETA, O_QBAR
from phalanx.fcs.actuators import C_AREA, C_ARM, C_NSEC


def _stick(t):
    return (1.0 if 0.5 < t < 3.0 else 0.0, 1.0 if 3.5 < t < 5.0 else 0.0, 0.0)


@pytest.mark.integration
@pytest.mark.parametrize("mach, alt, q_min", [(0.9, 1000.0, 45e3), (1.2, 3000.0, 65e3)])
def test_primary_loads_inside_stall_load(mach, alt, q_min):
    h = Harness(mach, alt, stick=_stick)
    of, oa = h.run(6.0)
    a = h.fcfg.tab.atab
    dp_rated = 2.8e7
    stall = a[:, C_AREA] * a[:, C_NSEC] * dp_rated * a[:, C_ARM]
    worst = np.zeros(13)
    out = np.zeros(13)
    for k in range(of.shape[0]):
        hinge_moments(oa[k, O_ALPHA], oa[k, O_BETA], oa[k, O_QBAR], of[k, 0:13], h.fcfg.tab.htab, out)
        worst = np.maximum(worst, np.abs(out))
    assert oa[:, O_QBAR].max() > q_min  # the run really is at high dynamic pressure
    assert nz_of(oa).max() > 4.5  # and a real pull
    ratio = worst[0:5] / stall[0:5]
    assert np.all(ratio < 0.5), ratio
    assert np.all(ratio > 0.02), ratio  # the loads are not trivially zero (hinge model active)
