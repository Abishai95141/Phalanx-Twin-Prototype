"""DFCC law details (A-W1.2-28, -29): the slat schedule and the PROXY features that are deliberately absent.

Open loop on the M05 module with scripted lanes (no airframe); deterministic grids stated per test.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from test_fcs_voting import base_inputs, make, run

from phalanx.core.events import Event
from phalanx.fcs.layout import F_PEND, FLAG_ALSR, FLAG_AP
from phalanx.fcs.ports import NOT_MODELLED, RECORDED

DEG = math.pi / 180.0


def _slat_cmd(alpha, mach):
    mod = make(mach=mach, alpha=alpha)
    st = mod.init(mod.params, None)
    st, _ = run(mod, st, base_inputs(3, mach=mach, alpha=alpha))  # one DFCC frame
    return st["f"][F_PEND + 5 : F_PEND + 11], mod


@pytest.mark.integration
def test_slat_schedule():
    """Slats deploy linearly with alpha from 4 to 16 deg and fade out between M0.80 and M0.90 (smoothstep);
    the six panels scale with their travel (OB, MB, IB mirrored). Grid: 5 alphas x 3 Machs (n = 15)."""
    for mach, fade in ((0.5, 1.0), (0.85, 0.5), (0.95, 0.0)):
        for a_deg, sg in ((0.0, 0.0), (4.0, 0.0), (10.0, 0.5), (16.0, 1.0), (22.0, 1.0)):
            cmd, mod = _slat_cmd(a_deg * DEG, mach)
            p = mod.params
            mx = np.array([p.value(k) for k in ("slat_max_ob", "slat_max_mb", "slat_max_ib")])
            expect = sg * fade * np.concatenate([mx, mx[::-1]])
            assert np.allclose(cmd, expect, atol=1e-12), (mach, a_deg, cmd, expect)


@pytest.mark.integration
def test_slats_fully_extended_in_reversion():
    """Air-data loss (both vanes excluded) latches the fixed-gain law: slats go to the safe extended
    position."""
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(60)
    from test_fcs_voting import L, _vane_calibration

    vk1, vc0, _, _ = _vane_calibration()
    for c in "abcd":  # the right vane reads the local flow of alpha + 8 deg
        inp[L("aoa_r", c)][:] = vk1 * (0.05 + 8 * DEG) + vc0
    st, _ = run(mod, st, inp)
    p = mod.params
    mx = np.array([p.value(k) for k in ("slat_max_ob", "slat_max_mb", "slat_max_ib")])
    assert np.allclose(st["f"][F_PEND + 5 : F_PEND + 11], np.concatenate([mx, mx[::-1]]))


@pytest.mark.integration
def test_proxy_features_absent():
    """PROXY exposure (A-W1.2-29): no autopilot/ALSR (mode-flag bits 0-1 never set), no Kalman attitude
    (FCS.KALMAN_ATT not produced), PBIT does not drive the surfaces (commands unchanged while it runs), no
    hydraulic pressure-switch BIT (HYD_PRESS_FAIL bits 8-11 stay 0 with both systems lost)."""
    mod = make(on_ground=True, mach=0.0, h=0.0, alpha=0.0)
    st = mod.init(mod.params, None)
    st, _ = mod.on_event(st, Event(0, "fcs.pbit_start", "fcs"), 0)
    inp = base_inputs(240, mach=0.0, h=0.0, alpha=0.0, wow=6)
    inp["hyd_dp_avail"][:] = 0.0
    st, out = run(mod, st, inp)
    assert np.all(out["rec_fcs_mode_flags"] & (FLAG_AP | FLAG_ALSR) == 0)
    assert "FCS.KALMAN_ATT.PITCH" in NOT_MODELLED and "FCS.KALMAN_ATT.PITCH" not in RECORDED.values()
    assert out["rec_av_lru_bit_dfcc"][-1] & 8  # IBIT in progress (PBIT running)
    assert np.all(st["f"][F_PEND : F_PEND + 5] == 0.0)  # ground law, zero stick: PBIT moved nothing
    for name in RECORDED:
        if name.startswith("rec_fcs_act_bit_"):
            assert np.all(out[name] & 0xF00 == 0), name
