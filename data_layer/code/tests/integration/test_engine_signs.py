"""M07 physical signs (acceptance A4) and the Muir/CF-18 fault-direction matrix (C26 signs).

Muir, Rudnitski & Cue, AGARD-CP-448 paper 7, Fig. 15 [TRANSFER: F404-400 CF-18], cross-plots theta1/delta1
corrected (SLS ISA here, so corrections are 1), A8 held in the "cruise flat" region: the operating lines below
use a fixed A8 (1.1 x design MIL) and the reference VG schedule,
fuel 35-85 % of MIL (11 points). A shift is the
mean relative change of the degraded line's ordinate at the baseline abscissae.

Fault definitions follow ProDiMES (NASA/TM-2010-215840 Eq. 1, via faults_and_degradation.md): magnitude 3 %
RSS; compressors Gamma:eta = 2:1 (top of the ProDiMES 1:1-2:1 range; ProDiMES fleet-average HPC 1.8),
turbines efficiency only (as in Muir's rows). "-" entries must stay within 1 % (Henry, AGARD-CP-448 paper 37
Tbl 2: normal scatter +-0.8-2 %).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.engine.design import build_engine_model
from phalanx.engine.layout import U_A8, U_H0, U_VG1, U_VG2, U_WF, Y_NAMES, A
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state

WFS = np.linspace(0.85, 0.35, 11)
PLOTS = (
    ("W1", "N1"),
    ("N2", "N1"),
    ("Fg", "N2"),
    ("Wfm", "N2"),
    ("PS3", "N2"),
    ("T56", "P56"),
    ("N2", "P56"),
)
XFAIL_ONE_TO_ONE = (
    "W2.3 calibration: at the ProDiMES 1:1 flow/efficiency mix the fan 'N2 vs N1' shift (+0.1-0.2 %) "
    "and HPC 'Wfm vs N2' (+0.2-0.4 %) have the wrong sign; below measurement precision, set by the "
    "generic map shapes (A-W1.3a-2)"
)
XFAIL_VG_ROWS = (
    "Muir-convention and model-structure question, NOT calibration (E1 verifier §3; proposed decision in "
    "the E1-HY report, for the coordinator to record). Convention used: compressor VG 'above limits' = "
    "opened, fan VG = closed (the only readings that match the rows' W1 and PS3/Wfm/Fg signs). Measured: "
    "CVG opened 6 deg gives T56 vs P56/P1 +0.18 % (Muir down; NRC model -0.5 %); FVG closed 5 deg gives "
    "N2 vs N1 -0.98 % (Muir up) and core shifts Fg/Wfm/PS3 vs N2 -5.5/-4.0/-4.1 % and T56 vs P56/P1 +1.9 % "
    "where Muir shows no appreciable deviation (< 1 %). Resolution: W2.3 VG off-schedule model structure "
    "(A-W1.3a-12) once the convention is recorded"
)
MUIR = {  # Fig. 15 rows: +1 up, -1 down, 0 no change
    "fan": (-1, -1, -1, -1, -1, +1, +1),
    "hpc": (0, +1, -1, -1, -1, +1, +1),
    "hpt_eta": (-1, -1, +1, +1, +1, +1, -1),
    "lpt_eta": (0, +1, -1, 0, 0, +1, 0),
}


def prodimes(mag: float, ratio: float) -> tuple[float, float]:
    e = mag / np.sqrt(1.0 + ratio**2)
    return -e, -e * ratio


def health(kind: str, ratio: float = 2.0) -> np.ndarray:
    h = np.zeros(10)
    if kind == "fan":
        h[0], h[1] = prodimes(0.03, ratio)
    elif kind == "hpc":
        h[2], h[3] = prodimes(0.03, ratio)
    elif kind == "hpt_eta":
        h[4] = -0.03
    elif kind == "lpt_eta":
        h[6] = -0.03
    return h


@pytest.fixture(scope="module")
def model():
    return build_engine_model()


def operating_line(model, h=None, dvg=(0.0, 0.0)):
    out, x = [], None
    for wf in WFS:
        u = design_inputs(model)
        u[U_WF] *= wf
        u[U_A8] *= 1.1
        if h is not None:
            u[U_H0 : U_H0 + 10] = h
        if dvg != (0.0, 0.0):
            r0 = steady_state(model, u, x0=x)
            u[U_VG1], u[U_VG2] = r0.u[U_VG1] + dvg[0], r0.u[U_VG2] + dvg[1]
            r = steady_state(model, u, x0=r0.x, vg_schedule=False)
        else:
            r = steady_state(model, u, x0=x)
        assert r.converged
        x, a = r.x, r.aux
        out.append(
            dict(
                W1=a[A["w2"]], N1=r.x[0], N2=r.x[1], Fg=a[A["fg"]], Wfm=a[A["wf_line"]],
                PS3=a[A["ps3"]] / a[A["p2"]], T56=a[A["t5"]], P56=a[A["p5"]] / a[A["p2"]],
            )
        )  # fmt: skip
    return {k: np.array([o[k] for o in out]) for k in out[0]}


def shift(base, deg, y, xk) -> float:
    xb, yb, xd, yd = base[xk], base[y], deg[xk], deg[y]
    o = np.argsort(xd)
    sel = (xb >= max(xb.min(), xd.min())) & (xb <= min(xb.max(), xd.max()))
    assert sel.sum() >= 5  # overlapping range
    return float(np.mean((np.interp(xb[sel], xd[o], yd[o]) - yb[sel]) / yb[sel]))


@pytest.fixture(scope="module")
def baseline(model):
    return operating_line(model)


@pytest.mark.integration
@pytest.mark.parametrize("fault", sorted(MUIR))
def test_health_deltas_follow_muir_directions(model, baseline, fault):
    """A4 / C26 (signs): each component-deterioration class moves every cross-plot in the CF-18 direction."""
    d = operating_line(model, health(fault))
    got = [shift(baseline, d, y, x) for y, x in PLOTS]
    for (y, x), exp, s in zip(PLOTS, MUIR[fault], got, strict=True):
        if exp == 0:
            assert abs(s) < 0.01, (fault, y, x, s)
        else:
            assert np.sign(s) == exp, (fault, y, x, s, got)


@pytest.mark.integration
@pytest.mark.xfail(strict=True, reason=XFAIL_ONE_TO_ONE)
def test_muir_signs_at_one_to_one_flow_efficiency_mix(model, baseline):
    for fault in ("fan", "hpc"):
        d = operating_line(model, health(fault, ratio=1.0))
        for (y, x), exp in zip(PLOTS, MUIR[fault], strict=True):
            s = shift(baseline, d, y, x)
            assert (abs(s) < 0.01) if exp == 0 else (np.sign(s) == exp), (fault, y, x, s)


@pytest.mark.integration
def test_compressor_vg_open_signs(model, baseline):
    """Muir row 'compressor VG above limits' (read as vanes opened beyond schedule, the direction that raises
    flow and pressure at fixed N2): N2 vs N1 down, Fg/Wfm/PS3 vs N2 up, N2 vs P56/P1 down,
    W1 vs N1 '-'; and the
    6 deg magnitude of PS3/P1 vs N2 is of the NRC-model order (+8.1 %, accepted 4-16 %)."""
    d = operating_line(model, dvg=(0.0, -np.radians(6.0)))
    exp = {("N2", "N1"): -1, ("Fg", "N2"): +1, ("Wfm", "N2"): +1, ("PS3", "N2"): +1, ("N2", "P56"): -1}
    for (y, x), e in exp.items():
        assert np.sign(shift(baseline, d, y, x)) == e, (y, x)
    assert abs(shift(baseline, d, "W1", "N1")) < 0.01
    assert 0.04 < shift(baseline, d, "PS3", "N2") < 0.16


@pytest.mark.integration
@pytest.mark.xfail(strict=True, reason=XFAIL_VG_ROWS)
def test_vg_rows_full_muir_agreement(model, baseline):
    """Muir Fig. 15 rows 5 and 6 in full: compressor VG opened 6 deg (T56 vs P56/P1 down; its other cells
    are asserted in test_compressor_vg_open_signs) and fan VG closed 5 deg (W1 vs N1 down, N2 vs N1 up,
    every other cross-plot without appreciable deviation, |shift| < 1 %)."""
    d = operating_line(model, dvg=(0.0, -np.radians(6.0)))
    assert shift(baseline, d, "T56", "P56") < 0
    f = operating_line(model, dvg=(np.radians(5.0), 0.0))
    assert shift(baseline, f, "W1", "N1") < 0 and shift(baseline, f, "N2", "N1") > 0
    for y, x in (("Fg", "N2"), ("Wfm", "N2"), ("PS3", "N2"), ("T56", "P56"), ("N2", "P56")):
        assert abs(shift(baseline, f, y, x)) < 0.01, (y, x)


@pytest.mark.integration
@pytest.mark.parametrize("wf_frac,a8", [(0.9, 1.0), (0.5, 1.15), (0.25, 1.4)])
def test_more_fuel_raises_speeds_temperature_and_pressure(model, wf_frac, a8):
    """A4: +Wf -> +N2, +N1, +T5, +PS3 at steady state (fixed A8, scheduled VG), three operating points."""
    out = []
    for k in (1.0, 1.02):
        u = design_inputs(model)
        u[U_WF] *= wf_frac * k
        u[U_A8] *= a8
        r = steady_state(model, u)
        assert r.converged
        out.append((r.x[1], r.x[0], r.aux[A["t5"]], r.aux[A["ps3"]]))
    assert all(b > a for a, b in zip(out[0], out[1], strict=True)), out


@pytest.mark.integration
def test_zero_disturbance_is_deterministic_and_disturbances_enter_dynamics(model):
    """A4: with w_engine = 0 two runs are identical (no hidden randomness in M07 outside the keyed AB draw);
    each w_engine channel changes the dynamics, and none of them is added to an output directly (an output
    changes only after the state has responded: the spool deviation after one tick is < 10 % of that
    after 1 s)."""
    ss = steady_state(model, design_inputs(model, wf_cmd=0.6 * model.design.stations["wf"]))
    st = state_from_x(model, ss.x)
    u, ui = input_block(240, 1, ss.u)
    r1 = simulate(model, st, u, ui)
    r2 = simulate(model, st, u, ui)
    assert np.array_equal(r1.y, r2.y)
    names = ("w_fuel_metering", "w_combustor_eff", "w_inlet_recovery", "w_shaft_load", "w_fan_face")
    n1 = Y_NAMES.index("n1")
    for c, nm in enumerate(names):
        w = np.zeros((240, 1, 5))
        w[:, 0, c] = 0.01
        r = simulate(model, st, *input_block(240, 1, ss.u, w_engine=w))
        assert abs(r.y[-1, 0, n1] - r1.y[-1, 0, n1]) > 1e-3, nm  # moved the spool
        for k in ("n1", "n2"):  # the spools respond through their dynamics (no output jump)
            j = Y_NAMES.index(k)
            assert abs(r.y[0, 0, j] - r1.y[0, 0, j]) < 0.1 * abs(r.y[-1, 0, j] - r1.y[-1, 0, j]), (nm, k)


@pytest.mark.integration
def test_disturbance_on_engine_1_does_not_move_engine_2(model):
    """A4: n_engines = 2; a disturbance on engine 1 only leaves engine 2 bitwise unchanged."""
    ss = steady_state(model, design_inputs(model, wf_cmd=0.7 * model.design.stations["wf"]))
    st = state_from_x(model, ss.x, n_engines=2)
    base = simulate(model, st, *input_block(480, 2, ss.u))
    w = np.zeros((480, 2, 5))
    w[:, 0, :] = 0.01 * np.sin(np.arange(480) / 7.0)[:, None]
    dist = simulate(model, st, *input_block(480, 2, ss.u, w_engine=w))
    assert np.array_equal(dist.y[:, 1], base.y[:, 1]) and np.array_equal(dist.state.f[1], base.state.f[1])
    assert not np.array_equal(dist.y[:, 0], base.y[:, 0])


@pytest.mark.integration
def test_oil_and_vibration_trends(model):
    """A-W1.3a-13/14: oil pressure and vibration-source amplitudes rise with N2 (generic pump law; DSTO
    test-cell idle/MIL level ratio about 0.3-0.4); oil temperature equilibrium is above the fuel sink."""
    lo = steady_state(model, design_inputs(model, wf_cmd=0.25 * model.design.stations["wf"], a8_cmd=0.0))
    hi = steady_state(model, design_inputs(model))
    assert hi.aux[A["oil_p"]] > lo.aux[A["oil_p"]] > 0.0
    assert hi.x[15] > 288.15 + 15.0  # toil above the sink
    for k in ("vib_n1", "vib_n2"):
        ratio = lo.aux[A[k]] / hi.aux[A[k]]
        assert 0.2 < ratio < 0.8, (k, ratio)
