"""W2.1 entry gate 3: T1 below its span (-54 degC floor vs the -56.5 degC stratosphere) (A-W2.1b-6).

Closed loop on the REAL M07 (`tests/engine_fadec_loop.py`) at 11 km ISA (216.65 K), Mach 0.1 (T1 = 217.1 K,
2 K below the span floor), PLA 90 (N1 limit with the 104.4 % corrected cap), 20 s from the operating point.
Both T1 lanes saturate at the floor. With the edge hold the pair stays valid and the law uses the floor value:
true corrected N1 then sits about 0.5 % above the cap (sqrt(219.15/217.1)); without it (negative control, edge
mask 0) both lanes range-fail and the law substitutes (W2.1b measurement: N1c 1.050 either way at M0; the
hold keeps a healthy sensor valid). A single lane forced to the floor (open circuit) still
range-fails with the hold on. n = 3 runs of 4,800 steps.
"""

from __future__ import annotations

import numpy as np
import pytest

import engine_fadec_loop as L
from phalanx.engine.module import EngineModule
from phalanx.engine.steady import TrimCondition
from phalanx.fadec import FadecConfig, load_fadec_params
from phalanx.fadec.codes import S_T1, V_OK, V_SUSPECT
from phalanx.fadec.layout import O_SEL, O_VSTATE, P_LAYOUT
from phalanx.fadec.trim import operating_point

pytestmark = pytest.mark.integration
CFG = FadecConfig.build(load_fadec_params())
P = {k: float(CFG.p[i]) for k, i in P_LAYOUT.index.items()}
T_S, P_S = L.isa(11_000.0)
COND = TrimCondition(t_s=T_S, p_s=P_S, mach=0.1)
N = 20 * 240


@pytest.fixture(scope="module")
def eng():
    return EngineModule("eng")


def _run(eng, cfg, lane_bias=None):
    op = operating_point(eng.model, CFG, 86.0, COND)
    return L.run(eng, op.engine, 90.0, n=N, condition=COND, cfg=cfg, lane_bias=lane_bias)


def test_stratosphere_t1_pair_is_held_at_the_span_floor(eng):
    r = _run(eng, CFG)
    tail = slice(-2400, None)
    t1_true = r.ch("t2")[tail]
    assert t1_true.max() < 219.15 - 1.0  # the inlet really is below the span
    assert (r.cmdi[tail, 0, O_VSTATE + S_T1] == V_OK).all()
    assert np.allclose(r.cmdf[tail, 0, O_SEL + S_T1], 219.15, atol=1e-3)
    n1c = r.ch("n1")[tail] / L.N1R / np.sqrt(t1_true / 288.15)
    # residual of holding the floor: cap x sqrt(219.15 / T1) (+ the 0.5 % settling allowance)
    bound = P["n1c_cap"] * np.sqrt(219.15 / t1_true.mean()) * 1.005
    assert n1c.max() <= bound, (n1c.max(), bound)
    assert n1c.mean() > P["n1c_cap"]  # the residual is real (documented, A-W2.1b-6)


def test_without_the_hold_both_lanes_range_fail(eng):
    r = _run(eng, CFG.with_cfg(edge_hold=0))
    tail = slice(-2400, None)
    assert (r.cmdi[tail, 0, O_VSTATE + S_T1] != V_OK).all()


def test_one_lane_at_the_floor_is_still_an_open_circuit(eng):
    """At Mach 0.8 the inlet is inside the span; lane A forced 60 K low (saturating at the floor) must fail
    while lane B carries on (soft fail), hold or no hold."""
    cond = TrimCondition(t_s=T_S, p_s=P_S, mach=0.8)
    op = operating_point(eng.model, CFG, 60.0, cond)
    bias = np.zeros(12)
    bias[2 * S_T1] = -60.0
    r = L.run(eng, op.engine, 60.0, n=10 * 240, condition=cond, cfg=CFG, lane_bias=bias)
    assert (r.cmdi[-240:, 0, O_VSTATE + S_T1] == V_SUSPECT).all()
