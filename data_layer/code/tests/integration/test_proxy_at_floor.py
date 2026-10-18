"""W2.4a-2: M08 option ``at_floor_lever`` - the A/T demand floored at the demand of the lever M08 is fed.

The proxy feeds the pre-mapped idle-stop lever while the A/T is engaged (``phalanx.proxy.demand``), so with
the option the A/T cannot ask for less than the flight idle at the condition. Default 0 is the Tejas/W1.3b law
(the schedule's lowest demand): the FADEC and golden suites run with the default unchanged; here the floor
function is checked to return exactly the committed clamp in mode 0, and the option's effect in the loop.

Plant: the labelled TEST FIXTURE (`tests/fadec_fixture.py`); M08 is the real kernel. 60 s per run.
"""

from __future__ import annotations

import numpy as np
import pytest

from fadec_fixture import X_N1, Scenario, closed_loop, fixture_params, steady_state
from phalanx.fadec import FadecConfig
from phalanx.fadec.kernel import _at_floor
from phalanx.fadec.layout import C_LAYOUT

pytestmark = pytest.mark.integration
N1R = 13270 * 2 * np.pi / 60


@pytest.mark.parametrize("dem", [0.7, 0.95, 0.7 + 1e-20j])
def test_mode_0_returns_the_committed_clamp(dem):
    """Mode 0 (default): the schedule's lowest demand, whatever the lever's demand (also complex-step)."""
    y0 = 0.81234
    lo = _at_floor(0, dem, y0)
    assert lo.real == y0 and np.imag(lo) == 0.0
    assert _at_floor(1, 0.5, y0) == y0  # mode 1 with a lever demand below the schedule's lowest: unchanged
    assert _at_floor(1, 0.95, y0) == 0.95
    assert int(FadecConfig.build(fixture_params()).cfg[C_LAYOUT.index["at_floor_lever"]]) == 0


def _run(at_floor: int, lever_after_deg: float):
    """Steady at lever 60 deg; the A/T engages at 5 s (bumplessly, from the lever's demand); from 6 s the
    lever M08 is fed is ``lever_after_deg``; at 10 s the A/T asks for 15 % N1 less."""
    n = 60 * 240
    x0 = steady_state(60.0)
    n1_0 = x0[0, X_N1] / N1R
    at_eng = np.zeros(n, np.int64)
    at_eng[5 * 240 :] = 1
    cmd = np.full((n, 1), n1_0)
    cmd[10 * 240 :, 0] = n1_0 - 0.15
    pla = np.full((n, 1), 60.0)
    pla[6 * 240 :, 0] = lever_after_deg
    sc = Scenario(n, 1, pla_deg=pla, at_engage=at_eng, at_n1_cmd=cmd)
    cfg = FadecConfig.build(fixture_params()).with_cfg(autothrottle=1, at_floor_lever=at_floor)
    r = closed_loop(sc, cfg=cfg, x0=x0)
    return r.xs[-240:, 0, X_N1].mean() / N1R, n1_0


def test_option_on_floors_the_at_demand_at_the_fed_lever():
    """Option 1 with the fed lever at 60 deg (the operating point's own demand): the A/T cannot pull the
    engine below that lever's demand, so N1 stays near its start instead of following the -15 % command.
    Option 0, or option 1 with a fed lever at 30 deg (a lower floor), lets the engine go down."""
    n1_on, n1_0 = _run(1, 60.0)
    n1_off, _ = _run(0, 60.0)
    n1_low, _ = _run(1, 30.0)
    assert n1_on > n1_0 - 0.02, (n1_on, n1_0)
    assert n1_off < n1_0 - 0.10, (n1_off, n1_0)
    assert n1_low < n1_on - 0.05, (n1_low, n1_on)
