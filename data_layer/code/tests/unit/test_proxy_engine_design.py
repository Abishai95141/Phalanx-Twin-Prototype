"""W2.4a A1 (design side): the M07 ``separate_fixed`` topology closes its design point on the MEASURED
anchors,
stays closed over the declared cycle sweeps, and leaves the Tejas ``mixed_ab`` path untouched.

Sample: the design point (deterministic closure) plus the corners of the declared BPR/FPR/OPR sweeps (8
closures)
and two 2 s transients for the invariance checks (the smallest windows that show a percent-speed response).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.module import Param, ParamSet
from phalanx.engine.design import build_engine_model
from phalanx.engine.kernel import deriv_point, engine_kernel
from phalanx.engine.layout import NP, P_NAMES, U_WF, Y_N1, Y_N2, Y_T5
from phalanx.engine.separate import SF_P_NAMES, deriv_point_sf, engine_kernel_sf
from phalanx.engine.separate_design import (
    SeparateFixedModel,
    build_separate_model,
    load_proxy_engine_params,
)
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state
from phalanx.engine.topology import MIXED_AB, SEPARATE_FIXED, kernel_functions, topology_of

pytestmark = pytest.mark.unit
REPO = Path(__file__).resolve().parents[2]
FROZEN = REPO / "analysis" / "settling_experiment_round2" / "results" / "frozen" / "S" / "ma_readable.json"


@pytest.fixture(scope="module")
def ps():
    return load_proxy_engine_params()


@pytest.fixture(scope="module")
def model(ps):
    return build_separate_model(ps)


def _with(ps: ParamSet, **over) -> ParamSet:
    vals = {k: ps[k] for k in ps}
    for k, v in over.items():
        o = ps[k]
        vals[k] = Param(v, o.unit, o.tag, o.source, o.proxy, o.note)
    return ParamSet(ps.name, vals)


def test_topology_dispatch_keeps_the_tejas_kernel_objects(model):
    """A1: a plain EngineModel dispatches to the original compiled objects (the mixed_ab path is the same code
    and the same function objects as before the hook); the proxy model dispatches to the separate kernel."""
    tejas = build_engine_model()
    assert topology_of(tejas) == MIXED_AB
    k, d = kernel_functions(tejas)
    assert k is engine_kernel and d is deriv_point
    assert topology_of(model) == SEPARATE_FIXED
    assert kernel_functions(model) == (engine_kernel_sf, deriv_point_sf)
    assert isinstance(model, SeparateFixedModel)
    # parameter layout: the base layout first, then the separate-flow extras
    assert SF_P_NAMES[:NP] == P_NAMES and model.p.size == len(SF_P_NAMES)
    with pytest.raises(ValueError, match="unknown M07 topology"):
        topology_of(type("M", (), {"topology": "bogus"})())


def test_design_reproduces_measured_anchors(model):
    """A-W2.4a-2: the closure lands exactly on the MEASURED round-2 anchors (EGT-station temperature and
    corrected fuel flow at the top-knot corrected speeds) and on the declared BPR."""
    d = json.loads(FROZEN.read_text())["readable"]
    st = model.design.stations
    assert abs(st["t5"] - 918.78) < 1e-6 and abs(st["wf"] - 0.44372) < 1e-12
    assert abs(st["bpr"] - 5.0) < 1e-12
    n1c_top, n2c_top = d["N1"]["h_knots_y"][-1], d["N1"]["h_knots_x"][-1]
    p = model.params
    assert abs(100.0 * float(p.value("n1_design_frac")) - n1c_top) < 1e-4
    assert abs(100.0 * float(p.value("n2_design_frac")) - n2c_top) < 1e-4
    # separate flow: two nozzles, both expanding (the cycle closes), core nozzle unchoked at SLS
    assert st["npr8"] > 1.05 and st["npr18"] > 1.05
    assert st["fg_bypass"] > st["fg_core"] > 0.0  # high bypass: most thrust from the fan stream


@pytest.mark.parametrize("bpr", [4.0, 6.5])
@pytest.mark.parametrize("fpr", [1.4, 1.75])
@pytest.mark.parametrize("opr", [10.0, 18.0])
def test_design_sweep_stays_closed(ps, bpr, fpr, opr):
    """A-W2.4a-1: the corners of the declared BPR x FPR x OPR sweep close on the same anchors, and the design
    state is an equilibrium of the kernel (max |dx/dt| relative < 1e-6 per second). The one corner with the
    highest bypass ratio and fan pressure ratio at the lowest OPR cannot drive its fan at the anchored EGT
    (the
    core nozzle would have to expand below ambient): the closure refuses it explicitly instead of returning a
    non-physical cycle (feasibility map in the W2.4a report)."""
    kw = dict(bpr_design=bpr, fpr_design=fpr, opr_design=opr)
    if (bpr, fpr, opr) == (6.5, 1.75, 10.0):
        with pytest.raises(ValueError, match="cycle does not close"):
            build_separate_model(_with(ps, **kw))
        return
    m = build_separate_model(_with(ps, **kw))
    st = m.design.stations
    assert abs(st["t5"] - 918.78) < 1e-6 and abs(st["wf"] - 0.44372) < 1e-10
    assert st["npr8"] > 1.0 and st["npr18"] > 1.0
    from phalanx.engine.steady import design_state

    x = design_state(m)
    dx, _ = deriv_point_sf(x, 0, 1, 0, 0.0, design_inputs(m), m.p, m.tables, -1.0)
    assert np.max(np.abs(dx[:8]) / (np.abs(x[:8]) + 1.0)) < 1e-6


def _pct_response(m, n=480):
    """Percent-speed and T5 response to a 5 % fuel step from a mid-power equilibrium (2 s)."""
    d = m.design.derived
    u0 = design_inputs(m)
    x = steady_state(m, u0).x
    for f in np.arange(0.98, 0.879, -0.02):
        s = steady_state(m, u0, x0=x, target=("n2", f * d["n2_des"]))
        x = s.x
    u, ui = input_block(n, 1, s.u)
    u[48:, :, U_WF] *= 1.05
    r = simulate(m, state_from_x(m, s.x), u, ui)
    return np.stack([r.y[:, 0, Y_N1] / d["n1_des"], r.y[:, 0, Y_N2] / d["n2_des"], r.y[:, 0, Y_T5]], axis=1)


def test_reference_speed_has_no_behavioural_effect(ps):
    """A-W2.4a-6: the 100 % rpm references are not public; with the rotor energy times fixed, changing them by
    -40 % (N1) and +30 % (N2) changes the percent-speed and T5 transient only at rounding level (< 1e-9
    relative)."""
    a = _pct_response(build_separate_model(ps))
    b = _pct_response(
        build_separate_model(
            _with(
                ps, n1_100pct=0.6 * float(ps.value("n1_100pct")), n2_100pct=1.3 * float(ps.value("n2_100pct"))
            )
        )
    )
    assert np.max(np.abs(a - b) / np.abs(a)) < 1e-9
    # negative control: the rotor energy time itself does change the response
    c = _pct_response(build_separate_model(_with(ps, h_lp_s=1.2)))
    assert np.max(np.abs(a[:, 0] - c[:, 0])) > 1e-4


def test_gear_ratio_has_no_effect_beyond_reflected_inertia(ps):
    """A-W2.4a-5: with a lossless gearbox, the gear ratio only renames the LPT map speed (absorbed by the
    design
    scaler): geared (3.0) and direct-drive (1.0) give the same transient to rounding level."""
    a = _pct_response(build_separate_model(_with(ps, gear_ratio=1.0, eta_gearbox=1.0)))
    b = _pct_response(build_separate_model(_with(ps, gear_ratio=3.0, eta_gearbox=1.0)))
    assert np.max(np.abs(a - b) / np.abs(a)) < 1e-9
    # the gearbox efficiency is not neutral
    c = _pct_response(build_separate_model(_with(ps, gear_ratio=3.0, eta_gearbox=0.98)))
    assert np.max(np.abs(a - c) / np.abs(a)) > 1e-4


def test_unknown_parameter_name_in_with_p_is_rejected(model):
    with pytest.raises(KeyError):
        model.with_p(not_a_parameter=1.0)
    m2 = model.with_p(a18=model.p[SF_P_NAMES.index("a18")] * 1.01)
    assert isinstance(m2, SeparateFixedModel) and m2.topology == SEPARATE_FIXED
    assert not m2.p.flags.writeable
