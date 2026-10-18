"""W2.4a-2 stage 1: the identified proxy plant reproduces the steady relations of 687-CAL
(A-W2.4a-19/-21/-22).

The committed verification bins (``analysis/proxy_quicklook/results/stage1/st_assess_V_adopted.json``: medians
of real quasi-steady points of 10 CAL flights that the identification did not use, with their flight
condition, bleed state and recorded N2) are the reference; no raw data is read. For the two most populated
bins of each regime the proxy M07 is solved at the recorded condition, bleed (``proxy.bleed`` with the M09
boundary values) and N2, and its fuel flow, N1 and EGT-station temperature are compared with the recorded FF,
N1 and EGT.

Tolerances (stated before the identification was assessed on these flights): fuel within 8 % (12 % at idle),
N1 within 3 % (9 % in part-power descents, the documented residual), EGT within 30 K (40 K on the ground).

Negative control (exposes the limitation the identification removes): the scaled generic maps without bleed
(neutral modifiers, the W2.4a-1 plant) miss fuel by more than 10 % and flight-idle N1 by more than 10 %.

Sample: 10 bins (2 per regime), one steady solve each by continuation from the SLS design point.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from phalanx.dictionary.params import load_param_set
from phalanx.engine.layout import U_NAMES, U_WF, X_N1, X_N2
from phalanx.engine.separate_design import build_separate_model
from phalanx.engine.steady import design_inputs, steady_state
from phalanx.proxy.bleed import BleedParams, engine_bleed

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
BINS = ROOT / "analysis" / "proxy_quicklook" / "results" / "stage1" / "st_assess_V_adopted.json"
LBH = 7936.641
#: regime -> (relative fuel, N1 [%], EGT [K]) tolerances
TOL = {
    "ground": (0.08, 3.0, 40.0),
    "flight idle": (0.12, 3.0, 30.0),
    "flight part power": (0.08, 9.0, 30.0),
    "climb/cruise < 15 kft": (0.08, 3.0, 30.0),
    "climb/cruise >= 15 kft": (0.08, 3.0, 30.0),
}


def regime(b: dict) -> str:
    n2c = b["N2"] / np.sqrt((b["TAT"] + 273.15) / 288.15)
    if b["ground"]:
        return "ground"
    if n2c < 75:
        return "flight idle"
    if n2c < 90:
        return "flight part power"
    return "climb/cruise < 15 kft" if b["ALT"] < 15000 else "climb/cruise >= 15 kft"


def pick_bins() -> list[dict]:
    bins = json.loads(BINS.read_text())["bins"]
    out = []
    for r in TOL:
        cand = sorted((b for b in bins if regime(b) == r), key=lambda b: (-b["n"], b["ALT"]))
        out += cand[:2]
    return out


def _delta(alt_ft: float) -> float:
    return (1.0 - 6.87559e-6 * min(alt_ft, 36089.0)) ** 5.2559


def solve_at(model, b: dict, bleed: BleedParams):
    """Steady state at the bin's condition, bleed and N2: SLS N2 continuation to the corrected target, then
    the ambient, Mach and bleed walked in together (the ``proxy.system.trim_engine`` path)."""
    n2_100 = float(model.params.value("n2_100pct"))
    tatk = b["TAT"] + 273.15
    th = tatk / 288.15
    mach = b["MACH"]
    t_s, p_s = tatk / (1.0 + 0.2 * mach * mach), 101325.0 * _delta(b["ALT"])
    wai = np.array([1 if (b["WAI_1"] or b["TAI"]) else 0])
    disc = (np.array([b["BLV"]]), np.array([b["PACK"]]), np.array([b["EAI"]]), wai)
    w_b = float(engine_bleed(*disc, bleed, ground=np.array([bool(b["ground"])]))[0, 0])
    u = design_inputs(model)
    s = steady_state(model, u)
    n2_target_sls = b["N2"] / 100.0 * n2_100 / np.sqrt(th)
    n2 = s.x[X_N2]
    while abs(n2 - n2_target_sls) > 1e-9:
        n2 = n2 + float(np.clip(n2_target_sls - n2, -0.01 * n2_100, 0.01 * n2_100))
        s = steady_state(model, u, x0=s.x, target=("n2", n2))
        assert s.converged
    for a in np.linspace(0.0, 1.0, 13)[1:]:
        ua = design_inputs(model)
        ua[U_NAMES.index("t_s")] = 288.15 + a * (t_s - 288.15)
        ua[U_NAMES.index("p_s")] = 101325.0 + a * (p_s - 101325.0)
        ua[U_NAMES.index("mach")] = a * mach
        ua[U_NAMES.index("t_fuel")] = ua[U_NAMES.index("t_s")] + 15.0
        ua[U_NAMES.index("bleed_extract")] = a * w_b
        ua[U_NAMES.index("pto_power")] = a * bleed.pto_w
        th_a = (288.15 + a * (tatk - 288.15)) / 288.15
        s = steady_state(model, ua, x0=s.x, target=("n2", n2_target_sls * np.sqrt(th_a)))
        assert s.converged, (b, a)
    return s


def errors(model, bleed: BleedParams, b: dict) -> tuple[float, float, float]:
    s = solve_at(model, b, bleed)
    n1_100 = float(model.params.value("n1_100pct"))
    ff = s.u[U_WF] * LBH
    return ff / b["FF"] - 1.0, 100.0 * s.x[X_N1] / n1_100 - b["N1"], s.aux_dict()["t5"] - 273.15 - b["EGT"]


@pytest.fixture(scope="module")
def bins():
    return pick_bins()


def test_identified_plant_reproduces_cal_steady_relations(bins):
    model = build_separate_model()
    bleed = BleedParams.from_params(load_param_set("M09", "boundary", platform="proxy_dashlink"))
    bad = []
    for b in bins:
        e = errors(model, bleed, b)
        tol = TOL[regime(b)]
        if not all(abs(x) <= t for x, t in zip(e, tol, strict=True)):
            bad.append((regime(b), round(b["ALT"]), round(b["N2"], 1), np.round(e, 3).tolist()))
    assert not bad, bad


def test_negative_control_generic_maps_without_bleed_miss_cal(bins):
    from phalanx.engine.separate import SF_PI

    model = build_separate_model()
    neutral = {k: 0.0 for k in SF_PI if k.endswith("_mod_a")}
    m0 = model.with_p(**neutral)
    errs = {}
    for b in bins:
        errs.setdefault(regime(b), []).append(errors(m0, BleedParams.off(), b))
    ff = [abs(e[0]) for v in errs.values() for e in v]
    assert np.median(ff) > 0.10, errs
    assert min(e[1] for e in errs["flight idle"]) > 10.0, errs["flight idle"]
