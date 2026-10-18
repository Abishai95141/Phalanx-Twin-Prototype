"""W2.1 entry gate 4 on the REAL M07: the N1 isochronous loop keeps >= 6 dB gain margin at the cold and hot
corners, and the 192-point limiter grid holds on the real engine (A-W2.1b-2).

Closed loop: `tests/engine_fadec_loop.py` (real M07 + real M08 kernels, TEST FIXTURE lanes).

Gain margin by simulation: the N1 regulator gains (n1_kp, n1_ki) are scaled by k and a 1 s, 2 % shaft-load
pulse is applied at the N1 limit (PLA 87, start at the PLA 86 operating point); the loop is stable at k when
the N1 peak-to-peak over 22-30 s is below 0.7 x that over 8-16 s. GM >= 6 dB <=> stable at k = 2. Lanes
without native-step quantisation (`fine_lanes`), so a quantisation limit cycle cannot mask the decay. n = one
30 s run (7,200 steps) per (corner, k). Measured (W2.1b, bisection to 0.06 in k, final configuration): 220 K
SLS 7.0 dB; 220 K / 92 kPa / M0.5 6.3 dB; 220 K / 30 kPa / M0.9 9.5 dB; 288 K SLS 9.2 dB; 288 K / 60 kPa /
M0.5 10.6 dB; 288 K / 30 kPa / M0 16.6 dB; 320 K SLS 9.5 dB; 320 K / 30 kPa / M0.5 15.9 dB (W1.3b gains on the
harmonised M08: -0.6, -0.9, 8.0, 1.9, 6.8, -, 4.9, 16.9 dB).
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

import engine_fadec_loop as L
from phalanx.engine.module import EngineModule
from phalanx.engine.steady import TrimCondition
from phalanx.fadec import FadecConfig, load_fadec_params
from phalanx.fadec.codes import FUEL_LIMITER, L_FUEL_OFF
from phalanx.fadec.layout import O_LIMITER, O_WF, P_LAYOUT
from phalanx.fadec.trim import operating_point

pytestmark = pytest.mark.integration
CFG = FadecConfig.build(load_fadec_params())
P = {k: float(CFG.p[i]) for k, i in P_LAYOUT.index.items()}
SECS = 30
N = SECS * 240


@pytest.fixture(scope="module")
def eng():
    return EngineModule("eng")


def _decay_ratio(eng, cond, k, *, n1_holds=True):
    cfg = CFG.with_p(n1_kp=P["n1_kp"] * k, n1_ki=P["n1_ki"] * k)
    op = operating_point(eng.model, CFG, 86.0, cond)
    w = np.zeros((N, 5))
    w[240:480, 3] = 0.02
    r = L.run(eng, op.engine, 87.0, n=N, condition=cond, cfg=cfg, w=w, fine_lanes=True)
    n1 = r.ch("n1") / L.N1R
    if n1_holds:
        assert np.mean((r.cmdi[-2400:, 0, O_LIMITER] & 15) == 2) > 0.9  # the N1 limiter holds fuel
    return np.ptp(n1[22 * 240 :]) / max(np.ptp(n1[8 * 240 : 16 * 240]), 1e-12)


@pytest.mark.parametrize(
    "t_s,p_s,mach",
    [(220.0, 101_325.0, 0.0), (220.0, 92_000.0, 0.5), (320.0, 101_325.0, 0.0)],
    ids=["cold-sls", "cold-dense-m05", "hot-sls"],
)
def test_n1_loop_gain_margin_is_at_least_6db_at_the_corners(eng, t_s, p_s, mach):
    ratio = _decay_ratio(eng, TrimCondition(t_s=t_s, p_s=p_s, mach=mach), 2.0)
    assert ratio < 0.7, ratio


def test_margin_metric_detects_an_unstable_loop(eng):
    """Negative control: at 4x the gains (12 dB) the cold sea-level loop limit-cycles (measured GM 7.0 dB)."""
    # (a limit cycle at the N1 limit hands fuel to the governor on each down-swing: no N1-holds check here)
    ratio = _decay_ratio(eng, TrimCondition(t_s=220.0, p_s=101_325.0, mach=0.0), 4.0, n1_holds=False)
    assert ratio > 0.9, ratio


GRID = tuple(
    itertools.product((85.0, 89.0, 95.0, 110.0), (220.0, 250.0, 288.0, 320.0), (30_000.0, 60_000.0, 92_000.0,
                      101_325.0), (0.0, 0.5, 0.9))
)  # fmt: skip


@pytest.mark.slow
@pytest.mark.parametrize("pla,t_amb,p_amb,mach", GRID)
def test_limiter_grid_192_on_m07(eng, pla, t_amb, p_amb, mach):
    """The E1-MF grid on the real M07 from its operating point at min(PLA, 84) (n = 192, 10 s each), with the
    property test's bounds: N1 vs min(N1 limit(T1), 104.4 % sqrt(theta1)) 2 % transient / 0.5 % over the last
    2 s, true corrected N1 the same, N2 vs its overspeed 1 % / 0.5 %, PS3 2 % / 0.5 %; defined regulator
    codes;
    bumpless selection (< 3 % fuel step at a regulator change)."""
    cond = TrimCondition(t_s=t_amb, p_s=p_amb, mach=mach)
    op = operating_point(eng.model, CFG, min(pla, 84.0), cond)
    n, settle, tail = 10 * 240, 3 * 240, 2 * 240
    r = L.run(eng, op.engine, pla, n=n, condition=cond, cfg=CFG)
    t1 = op.engine.aux[0]
    n1lim = min(np.interp(t1, CFG.tables.n1lim_x, CFG.tables.n1lim_y), P["n1c_cap"] * np.sqrt(t1 / 288.15))
    for name, v, tr in (
        ("N1", r.ch("n1")[settle:] / L.N1R / n1lim, 1.02),
        ("N1c", r.ch("n1")[settle:] / L.N1R / np.sqrt(t1 / 288.15) / P["n1c_cap"], 1.02),
        ("N2", r.ch("n2")[settle:] / L.N2R / P["n2_max"], 1.01),
        ("PS3", r.ch("ps3")[settle:] / P["ps3_max"], 1.02),
    ):
        assert v.max() <= tr, (name, "transient", float(v.max()))
        assert v[-tail:].max() <= 1.005, (name, "steady", float(v[-tail:].max()))
    code = r.cmdi[settle:, 0, O_LIMITER] & 15
    assert set(np.unique(code).tolist()) <= set(FUEL_LIMITER) - {L_FUEL_OFF}
    wf = r.cmdf[settle:, 0, O_WF]
    sw = np.flatnonzero(np.diff(code) != 0) + 1
    if sw.size:
        assert (np.abs(wf[sw] - wf[sw - 1]) / np.maximum(wf[sw - 1], 1e-6)).max() < 0.03
