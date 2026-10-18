"""W2.1 F1: the M07 trim-at-condition API (`EngineModule.trim`, `steady.trim`) returns a consistent (x, u).

A trim is an equilibrium of the M07 kernel at the condition with the commands in `u`: started there with
those constant inputs the dynamic model stays put (the A3 property, now at any condition and target). Targets
can be a state ("n1", "n2") or a diagnostic ("n2c" = N2/sqrt(theta25) in rpm, "ps3"); far conditions are
reached by the continuation path; an infeasible target is reported as not converged and `from_trim` refuses
it.

Sample (minimal sufficient): 7 conditions (SLS idle and part power, a cold and a hot day, 20/30/40 kft cruise,
the cold stratosphere at low Mach) x 10 s of drift each (2,400 ticks): the drift bound is a property of each
equilibrium, so one run per condition answers it; 1 infeasible target (negative control).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.engine.layout import AUX_NAMES, NX, U_A8, U_WF, X_N1, X_N2
from phalanx.engine.module import EngineModule
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import TrimCondition, steady_state

pytestmark = pytest.mark.integration
N1R = 13270.0 * 2.0 * np.pi / 60.0
N2R = 16810.0 * 2.0 * np.pi / 60.0
A = {n: j for j, n in enumerate(AUX_NAMES)}


def _isa(h_m: float) -> tuple[float, float]:
    if h_m <= 11000.0:
        t = 288.15 - 0.0065 * h_m
        return t, 101325.0 * (t / 288.15) ** 5.255877
    return 216.65, 22632.06 * float(np.exp(-(h_m - 11000.0) / 6341.62))


def _cond(ft: float, mach: float, dt_isa: float = 0.0) -> TrimCondition:
    t, p = _isa(ft * 0.3048)
    return TrimCondition(t_s=t + dt_isa, p_s=p, mach=mach)


@pytest.fixture(scope="module")
def eng():
    return EngineModule("eng")


CASES = [
    # (condition, target, nozzle area m^2)
    (_cond(0, 0.0), ("n2", 0.666 * N2R), 0.2206),  # SLS ground idle
    (_cond(0, 0.0), ("n2c", 0.72 * 16810.0), 0.2206),  # SLS part power, corrected-core-speed target
    (_cond(0, 0.0, -30.0), ("n1", 0.95 * N1R), 0.19),  # cold day
    (_cond(0, 0.0, 30.0), ("n2", 0.9 * N2R), 0.19),  # hot day
    (_cond(20000, 0.8), ("n2c", 0.70 * 16810.0), 0.2206),
    (_cond(30000, 0.8), ("n1", 0.85 * N1R), 0.2206),
    (_cond(40000, 0.9), ("n2c", 0.74 * 16810.0), 0.19),
]


@pytest.mark.parametrize("cond,target,a8", CASES)
def test_trim_is_an_equilibrium_of_the_kernel_at_the_condition(eng, cond, target, a8):
    """The trim meets its target exactly and the kernel started there with u stays put for 10 s (relative
    drift < 1e-8 on every continuous state; the solver residual is ~1e-12/s)."""
    tr = eng.trim(cond, target, a8=a8)
    assert tr.converged
    name, val = target
    got = tr.x[X_N1 if name == "n1" else X_N2] if name in ("n1", "n2") else tr.aux[A[name]]
    assert got == pytest.approx(val, rel=1e-9)
    assert tr.u[U_A8] == pytest.approx(a8) and tr.u[U_WF] > 0.0
    st = state_from_x(eng.model, tr.x)
    u, ui = input_block(2400, 1, tr.u)
    r = simulate(eng.model, st, u, ui)
    drift = np.max(np.abs(r.state.f[0, :NX] - tr.x) / (np.abs(tr.x) + 1.0))
    assert drift < 1e-8, drift


def test_trim_matches_the_direct_steady_solver_near_the_design_point(eng):
    """Where the direct Newton solve converges, `trim` returns exactly what `steady_state` returns (the
    existing "n2" target semantics are unchanged by the target generalisation)."""
    c = TrimCondition()
    tr = eng.trim(c, ("n2", 0.9 * eng.model.design.stations["n2"]))
    ss = steady_state(eng.model, c.inputs(eng.model), target=("n2", 0.9 * eng.model.design.stations["n2"]))
    assert tr.converged and ss.converged
    np.testing.assert_array_equal(tr.x, ss.x)
    np.testing.assert_array_equal(tr.u, ss.u)


def test_continuation_path_reaches_the_same_equilibrium_as_the_direct_solve(eng):
    """The continuation path (forced with ``direct=False``: design point -> 40 kft M0.9 at a low corrected
    core speed in stages) ends on the same equilibrium the direct Newton solve finds (relative 1e-9): the
    fallback a far or awkward condition uses is exact, not an approximation."""
    from phalanx.engine.steady import trim

    c = _cond(40000, 0.9)
    target = ("n2c", 0.68 * 16810.0)
    direct = trim(eng.model, c, target, a8=0.2206)
    cont = trim(eng.model, c, target, a8=0.2206, direct=False)
    assert direct.converged and cont.converged
    assert cont.aux[A["n2c"]] == pytest.approx(target[1], rel=1e-9)
    np.testing.assert_allclose(cont.x, direct.x, rtol=1e-9, atol=1e-6)


def test_from_trim_starts_the_module_there_and_refuses_an_unconverged_trim(eng):
    """`from_trim` gives a module whose initial state and outputs are the trim; an infeasible target (a
    corrected core speed far above MIL) does not converge and is refused (negative control)."""
    c = _cond(0, 0.0)
    tr = eng.trim(c, ("n2", 0.75 * N2R), a8=0.2206)
    m = eng.from_trim(tr)
    st = m.init(m.params, None)
    np.testing.assert_array_equal(st["f"][0, :NX], tr.x)
    out = m.initial_outputs(st)
    assert out["n2"][0] == tr.x[X_N2] and out["wf"][0] == pytest.approx(tr.u[U_WF])
    bad = eng.trim(c, ("n2c", 0.95 * 16810.0), a8=0.2206)
    assert not bad.converged
    with pytest.raises(RuntimeError):
        eng.from_trim(bad)
