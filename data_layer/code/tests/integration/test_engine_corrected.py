"""M07 corrected-parameter invariance under an ISA offset (acceptance A2, metamorphic).

Relation: at the same corrected HP speed N2/sqrt(theta), fixed geometry (A8, VG on their corrected-speed
reference) and the same flight Mach, the corrected outputs (``phalanx.engine.corrected``) do not depend on the
engine-face total temperature and pressure, up to the effects the physics adds on purpose:

- real-gas properties (cp and gamma vary with temperature) break the temperature similarity slightly;
- absolute loads (the 50 kW accessory gearbox, A-W1.3a-16) break the pressure similarity, more so at part
  power and low pressure (more fuel per corrected thrust at altitude), which is physical.

Sample: 2 power settings (100 % and 85 % N2c) x 4 offsets (ISA -20 K, ISA +20 K, delta 0.5, delta 1.48) = 8
steady solves per model, the smallest set that covers both kinds of offset at full and part power.
Tolerances: pressure offsets with the absolute loads removed are exact to 1e-4 (the formulation is
pressure-similar); temperature offsets within 1 % (2 % for the fuel parameter, whose textbook theta**0.5
correction is known to be inexact) [architecture §14.2 steady-state band +-3 %].
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.engine.corrected import corrected
from phalanx.engine.layout import U_A8, U_PS, U_TS, X_N1, X_N2, X_P6, X_P21, X_T41, X_WFM, Y_NAMES
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state


def _fixtures():
    path = Path(__file__).resolve().parent / "test_engine_fixtures.py"
    spec = importlib.util.spec_from_file_location("engine_fixtures_c", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["engine_fixtures_c"] = mod
    spec.loader.exec_module(mod)
    return mod


fx = _fixtures()
KEYS = ("n1", "t25", "t3", "t5", "ps3", "p5", "wf", "w2", "thrust")
FRACS = (1.0, 0.85)
T_OFFSETS = ((268.15, 101325.0), (308.15, 101325.0))
P_OFFSETS = ((288.15, 50000.0), (288.15, 150000.0))


@pytest.fixture(scope="module")
def sch():
    return fx.FixtureSchedules(fx.fixture_model())


def _point(m, sch, ts: float, ps: float, frac: float) -> tuple[dict, dict]:
    """Steady point at N2c = frac x design, static ambient (ts, ps) at Mach 0; corrected and raw outputs."""
    u = design_inputs(m)
    u[U_TS], u[U_PS] = ts, ps
    u[U_A8] = sch.a8(frac)
    th, de = ts / 288.15, ps / 101325.0
    x0 = sch.x_at(frac).copy()  # initial guess scaled by similarity (only the guess)
    x0[X_N1 : X_N2 + 1] *= np.sqrt(th)
    x0[X_P21 : X_P6 + 1] *= de
    x0[X_T41] *= th
    x0[X_WFM] *= de * np.sqrt(th)
    r = steady_state(m, u, x0=x0, target=("n2", frac * sch.n2_des * np.sqrt(th)))
    assert r.converged, (ts, ps, frac)
    y = simulate(m, state_from_x(m, r.x), *input_block(1, 1, r.u)).y[0, 0]
    raw = {k: float(y[Y_NAMES.index(k)]) for k in (*KEYS, "t2", "p2")}
    return corrected(raw, raw["t2"], raw["p2"]), raw


def _deviations(m, sch, offsets):
    out = []
    for frac in FRACS:
        base_c, base_r = _point(m, sch, 288.15, 101325.0, frac)
        for ts, ps in offsets:
            c, r = _point(m, sch, ts, ps, frac)
            out.append(
                (
                    frac,
                    (ts, ps),
                    {k: c[k] / base_c[k] - 1.0 for k in KEYS},
                    {k: r[k] / base_r[k] - 1.0 for k in KEYS},
                )
            )
    return out


@pytest.mark.integration
def test_a2_pressure_offset_exact_without_absolute_loads(sch, record_property):
    """A2: with the accessory load removed, delta = 0.5 and 1.48 leave every corrected output unchanged to
    1e-4, while the raw pressures, flows and thrust change by about the delta factor (negative control)."""
    m = sch.model.with_p(p_acc_des=0.0)
    for frac, off, dc, dr in _deviations(m, sch, P_OFFSETS):
        worst = max(abs(v) for v in dc.values())
        record_property(f"a2_p_{frac}_{off[1]:.0f}_max_rel", f"{worst:.2e}")
        assert worst < 1e-4, (frac, off, dc)
        assert min(abs(dr[k]) for k in ("ps3", "w2", "thrust", "wf")) > 0.3, (frac, off, dr)


@pytest.mark.integration
def test_a2_temperature_offset_within_real_gas_band(sch, record_property):
    """A2: ISA -20 K / +20 K leave corrected outputs within 1 % (fuel parameter within 2 %), while the
    raw speeds and temperatures move by about sqrt(theta) and theta (> 3 %): the residual is the real-gas
    effect."""
    for model in (sch.model, sch.model.with_p(p_acc_des=0.0)):
        for frac, off, dc, dr in _deviations(model, sch, T_OFFSETS):
            for k, v in dc.items():
                record_property(f"a2_t_{frac}_{off[0]:.0f}_{k}", round(v * 100.0, 3))
                assert abs(v) <= (0.02 if k == "wf" else 0.01), (frac, off, k, v)
            assert abs(dr["n1"]) > 0.03 and abs(dr["t5"]) > 0.06, (frac, off, dr)


@pytest.mark.integration
def test_a2_absolute_load_breaks_pressure_similarity_physically(sch):
    """Control: with the 50 kW accessory load (A-W1.3a-16), low pressure raises corrected fuel and T5 at
    part power (the load is a larger share of HP work at altitude); the invariance test above can therefore
    fail."""
    dev = {(frac, off): dc for frac, off, dc, _ in _deviations(sch.model, sch, P_OFFSETS)}
    lo = dev[(0.85, P_OFFSETS[0])]
    hi = dev[(0.85, P_OFFSETS[1])]
    assert lo["wf"] > 1e-3 and lo["t5"] > 1e-3, lo
    assert hi["wf"] < 0.0 and hi["t5"] < 0.0, hi
    assert abs(lo["wf"]) > abs(dev[(1.0, P_OFFSETS[0])]["wf"])  # larger share at part power
