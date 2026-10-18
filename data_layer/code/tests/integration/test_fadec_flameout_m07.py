"""W2.1 entry gate 1 on the REAL M07: M08 detects a main-burner flameout from sea level to 40,000 ft, relights
it and clears the flag, and a throttle chop is not a flameout (A-W2.1b-3).

Closed loop: `tests/engine_fadec_loop.py`; the flameout is the M07 state perturbation of `eng.fault_inject`
mode `flameout` (flame state set out at the start of a step; fuel keeps flowing, M08 must see it and fire the
igniters). Detection: T5 below its PLA-scheduled reference AND N2 below demand AND dN2/dt below fo_n2dot x
P0/P_std for fo_detect frames; relight confirmed by T5 back above its reference or by N2 back at the governed
speed and not falling.

Sample: 7 flight conditions x 2 power settings (idle, PLA 60) x one 30 s run (flameout at 2 s) = 14 runs, the
envelope corners of the W2.1b scan (0-40 kft); negative controls: 3 throttle chops (PLA 60 -> idle) at SLS,
30 kft and a 220 K cold day. W2.1b scan (the same runs): before the altitude schedule, idle flameouts at 20-40
kft were never detected (M07 idle rundown -3.0 %/s at 30 kft vs the -3 %/s SLS threshold).
"""

from __future__ import annotations

import numpy as np
import pytest

import engine_fadec_loop as L
from phalanx.engine.module import EngineModule
from phalanx.engine.steady import TrimCondition
from phalanx.fadec import FadecConfig, load_fadec_params
from phalanx.fadec.codes import B_FLAMEOUT
from phalanx.fadec.layout import O_FAULTS, O_IGN
from phalanx.fadec.trim import operating_point

pytestmark = pytest.mark.integration
CFG = FadecConfig.build(load_fadec_params())
N = 30 * 240
K0 = 2 * 240
POINTS = [(0, 0.0), (10_000, 0.5), (20_000, 0.6), (20_000, 0.8), (30_000, 0.6), (30_000, 0.8), (40_000, 0.8)]


@pytest.fixture(scope="module")
def eng():
    return EngineModule("eng")


def _cond(ft, mach, t_s=None):
    t, p = L.isa(ft * 0.3048)
    return TrimCondition(t_s=t if t_s is None else t_s, p_s=p, mach=mach)


@pytest.mark.parametrize("pla", [31.0, 60.0], ids=["idle", "pla60"])
@pytest.mark.parametrize("ft,mach", POINTS)
def test_flameout_is_detected_relit_and_cleared(eng, ft, mach, pla):
    cond = _cond(ft, mach)
    op = operating_point(eng.model, CFG, pla, cond)
    kill = np.zeros(N, np.int64)
    kill[K0] = 1
    r = L.run(eng, op.engine, pla, n=N, condition=cond, cfg=CFG, kill=kill)
    fo = (r.cmdi[:, 0, O_FAULTS] >> B_FLAMEOUT) & 1
    assert not fo[:K0].any()
    assert fo[K0:].any(), "flameout not detected"
    k_det = K0 + int(np.argmax(fo[K0:] == 1))
    # detected within 6 s (the slowest W2.1b case: idle at 40 kft M0.8, 4.7 s; SLS well under 1 s)
    assert (k_det - K0) / 240 < 6.0, (k_det - K0) / 240
    assert r.cmdi[k_det:, 0, O_IGN].any()  # igniters fired
    flame = r.yi[:, 0, 1]
    assert flame[K0] == 0 and flame[-1] == 1  # relit
    assert fo[-1] == 0  # flag cleared
    n2 = r.ch("n2")
    assert n2[-1] > 0.97 * n2[K0 - 1]  # back near the pre-flameout speed


@pytest.mark.parametrize(
    "ft,mach,t_s", [(0, 0.0, None), (30_000, 0.8, None), (0, 0.0, 220.0)], ids=["sls", "30kft", "cold"]
)
def test_a_throttle_chop_is_not_a_flameout(eng, ft, mach, t_s):
    """Negative control: PLA 60 -> idle at 2 s decelerates the core with T5 falling, but N2 is not below
    demand once the decel schedule has acted and no flameout may be declared."""
    cond = _cond(ft, mach, t_s)
    op = operating_point(eng.model, CFG, 60.0, cond)
    pla = np.full(N, 60.0)
    pla[K0:] = 18.0
    r = L.run(eng, op.engine, pla, n=N, condition=cond, cfg=CFG)
    fo = (r.cmdi[:, 0, O_FAULTS] >> B_FLAMEOUT) & 1
    assert not fo.any()
    assert r.ch("n2")[-1] < 0.95 * r.ch("n2")[K0 - 1]  # the chop did decelerate the core
