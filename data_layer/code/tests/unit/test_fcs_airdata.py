"""DFCC air-data computations (A-W1.2-25): pitot-static inversion and ICAO pressure altitude.

Grid: Mach 0.1-1.8 x altitude 0-15 km (n = 18 x 6 = 108 deterministic points); references from the forward
equations (isentropic / Rayleigh pitot) and USSA-76 (analysis.isa), independent of the DFCC code path.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.airframe.analysis import isa
from phalanx.fcs.build import build_fcs_config, fcs_param_set
from phalanx.fcs.kernel import _air_data
from phalanx.fcs.layout import F_HP, F_MACH, F_QBAR, F_VOTE, N_F, SIG_PS, SIG_PT


def _pt(ps, m):
    if m <= 1.0:
        return ps * (1 + 0.2 * m * m) ** 3.5
    return ps * (1.2 * m * m) ** 3.5 * (2.4 / (2.8 * m * m - 0.4)) ** 2.5


@pytest.mark.unit
def test_mach_qbar_pressure_altitude_inversion():
    """Mach from Pt/Ps to 1e-6 (both regimes), qbar = 0.7 Ps M^2 to 1e-9 relative, pressure altitude to 0.5 m
    vs the geopotential height of the same USSA-76 pressure (ICAO pressure altitude is geopotential)."""
    cfg = build_fcs_config(fcs_param_set())
    for h in (0.0, 3000.0, 6000.0, 9000.0, 12000.0, 15000.0):
        _, _, _, ps = isa(h)
        hg = 6356766.0 * h / (6356766.0 + h)
        for m in np.linspace(0.1, 1.8, 18):
            f = np.zeros(N_F)
            f[F_VOTE + SIG_PS] = ps
            f[F_VOTE + SIG_PT] = _pt(ps, m)
            _air_data(f, cfg.p)
            assert abs(f[F_MACH] - m) < 1e-6, (h, m, f[F_MACH])
            assert abs(f[F_QBAR] - 0.7 * ps * f[F_MACH] ** 2) <= 1e-9 * f[F_QBAR]
            assert abs(f[F_HP] - hg) < 0.5, (h, f[F_HP], hg)


@pytest.mark.unit
def test_subsonic_negative_impact_pressure_is_clamped():
    """Pt below Ps (lane noise at rest) gives Mach 0 rather than NaN."""
    cfg = build_fcs_config(fcs_param_set())
    f = np.zeros(N_F)
    f[F_VOTE + SIG_PS] = 101325.0
    f[F_VOTE + SIG_PT] = 101000.0
    _air_data(f, cfg.p)
    assert f[F_MACH] == 0.0 and np.isfinite(f[F_HP])
