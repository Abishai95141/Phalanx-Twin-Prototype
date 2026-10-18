"""W2.4a-2: the proxy demand pre-map (``phalanx.proxy.demand``) equals the MEASURED fuel-control law.

M08 reads its demand from the lever only (table built at the ground reference, M 0, delta = theta = 1). The
pre-map feeds it the effective lever PLA' with f_P(PLA') = f_P(PLA) + cM M + cD ln(delta) + cT (theta - 1), so
g(f_P(PLA') - cM 0.5) must equal the round-2 law g(f_P(PLA) + cM (M - 0.5) + cD ln(delta) + cT (theta - 1)) at
every flight condition whose target lies inside the lever range. Exposing checks: the reference condition maps
the lever to itself, levers below the idle stop pass unchanged (fuel cut-off), and targets beyond the top knot
hold at it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from phalanx.dictionary.params import load_param_set
from phalanx.proxy.demand import DemandPremap
from phalanx.proxy.schedules import _monotone_pchip, measured_n2c_of_pla
from phalanx.validation.dashlink import corrections

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "analysis" / "settling_experiment_round2" / "results" / "frozen" / "S" / "ma_readable.json"
DEG = np.pi / 180.0


@pytest.fixture(scope="module")
def pm():
    return DemandPremap.from_params(load_param_set("M08", "demand_premap", platform="proxy_dashlink"))


def _law(pla_deg, alt_ft, mach, tat_c):
    """Round-2 MEASURED corrected-speed demand N2/sqrt(theta2) [fraction] at the flight condition."""
    d = json.loads(FROZEN.read_text())["readable"]["FFN2"]
    f = _monotone_pchip(d["f_knots_x"], d["f_knots_y"])
    g = _monotone_pchip(d["g_knots_x"], d["g_knots_y"])
    th, de = corrections(np.atleast_1d(alt_ft), np.atleast_1d(mach), np.atleast_1d(tat_c))
    wd = f(pla_deg) + d["cM"] * (mach - 0.5) + d["cD"] * np.log(de) + d["cT"] * (th - 1.0)
    return np.asarray(g(wd)) / 100.0


def test_parameters_are_the_measured_law(pm):
    d = json.loads(FROZEN.read_text())["readable"]["FFN2"]
    assert np.allclose(np.asarray(pm.f_pla) / DEG, d["f_knots_x"], rtol=1e-12)
    lbh = 3600.0 / 0.45359237
    assert np.isclose(pm.c_mach * lbh, d["cM"]) and np.isclose(pm.c_lndelta * lbh, d["cD"])
    assert np.isclose(pm.c_theta * lbh, d["cT"]) and pm.table_mach == 0.0


CONDITIONS = [(0.0, 0.0, 15.0), (2000.0, 0.25, 12.0), (25000.0, 0.68, -12.0), (5000.0, 0.42, 8.0)]


@pytest.mark.parametrize(("alt_ft", "mach", "tat_c"), CONDITIONS)
def test_effective_lever_gives_the_measured_demand(pm, alt_ft, mach, tat_c):
    pla = np.linspace(30.0, 80.0, 26)  # inside the lever range of the f map
    cond = (np.full(26, alt_ft), np.full(26, mach), np.full(26, tat_c))
    eff = pm.effective_pla(pla[None, :] * DEG, *cond)[0]
    via_table = measured_n2c_of_pla(FROZEN, eff / DEG, mach=0.0)
    direct = _law(pla, alt_ft, mach, tat_c)
    inside = direct < measured_n2c_of_pla(FROZEN, np.array([87.71]), mach=0.0)[0]  # below the top knot
    assert np.max(np.abs(via_table[inside] - direct[inside])) < 2e-4  # the inverse is on a 4001-point grid
    if alt_ft == 0.0 and mach == 0.0:
        assert np.max(np.abs(eff / DEG - pla)) < 0.02  # the reference condition maps the lever to itself


def test_idle_stop_and_top_knot(pm):
    pla = np.array([[0.0, 3.0, 22.0, 95.0, 120.0]]) * DEG
    eff = pm.effective_pla(pla, np.full(5, 25000.0), np.full(5, 0.7), np.full(5, -15.0))[0] / DEG
    # below the idle stop: the recorded lever (the fuel cut-off logic sees it unchanged)
    assert np.array_equal(eff[:3], pla[0, :3] / DEG)
    assert np.all(eff[3:] <= 87.72)  # beyond the top knot the table is flat: held at the knot
