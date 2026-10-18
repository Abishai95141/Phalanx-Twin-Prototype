"""M07 identification and linearisation hooks for W2.3/W2.4 (AD-34; brief "transient-weighted residual",
"linearisation API").

Samples: one 1 s window (240 ticks, 1 engine) with a fuel step for residuals and Jacobians; one 3 s step for
the linear-vs-nonlinear check; two operating points (100 % and 85 % N2) for stability. Smallest windows that
contain a full fuel-step transient of the fast states.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import expm

from phalanx.engine.ident import jacobian_cs, residuals, transient_weights
from phalanx.engine.layout import PI, U_A8, U_WF, X_N1, X_N2, Y_NAMES
from phalanx.engine.layout import A as AUX
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import LIN_INPUTS, LIN_OUTPUTS, design_inputs, linearize, steady_state


def _fixtures():
    path = Path(__file__).resolve().parent / "test_engine_fixtures.py"
    spec = importlib.util.spec_from_file_location("engine_fixtures_i", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["engine_fixtures_i"] = mod
    spec.loader.exec_module(mod)
    return mod


fx = _fixtures()
CHANNELS = ("n1", "n2", "t5", "ps3")
SCALES = (10.0, 10.0, 5.0, 5000.0)
NAMES = ("i_hp", "i_lp", "tau_comb")


@pytest.fixture(scope="module")
def m():
    return fx.fixture_model()


@pytest.fixture(scope="module")
def window(m):
    ss = steady_state(m, design_inputs(m, wf_cmd=0.95 * m.design.stations["wf"]))
    n = 240
    wf = np.full(n, ss.u[U_WF])
    wf[24:] *= 1.03
    u, ui = input_block(n, 1, ss.u, wf_cmd=wf)
    state0 = state_from_x(m, ss.x)
    y = simulate(m, state0, u, ui).y[:, :, [Y_NAMES.index(c) for c in CHANNELS]]
    theta = np.array([m.p[PI[nm]] for nm in NAMES])
    return state0, u, ui, y, theta, wf


@pytest.mark.unit
def test_transient_weights_marks_accel_and_decel_windows():
    """A rise and a fall of the driving signal give accel and decel windows; the rest is steady weight."""
    dt = 0.1
    s = np.zeros(300)
    s[50:200] = 1.0
    w = transient_weights(s, dt, threshold=0.5, window_s=5.0, rate_window_s=1.0, w_accel=4.0, w_decel=7.0)
    # a step at index 50 is detected over the 1 s rate window (indices 50-59); each window starts at the
    # beginning of its rate window and lasts 5 s -> accel weight on [40, 99), decel on [190, 249)
    assert np.all(w[:40] == 1.0) and np.all(w[40:99] == 4.0) and np.all(w[99:190] == 1.0)
    assert np.all(w[190:249] == 7.0) and np.all(w[249:] == 1.0)
    assert transient_weights(np.zeros(50), dt, threshold=0.5).tolist() == [1.0] * 50  # negative control


@pytest.mark.integration
def test_residuals_zero_on_own_data_and_grow_with_parameter_error(m, window):
    """Self-consistency: residuals vanish at the generating parameters; a 20 % HP-inertia error is invisible
    at equilibrium (zero residual before the step) and appears only after it; the accel weight scales it."""
    state0, u, ui, y, theta, wf = window
    r0 = residuals(m, NAMES, theta, state0, u, ui, y, CHANNELS, SCALES)
    assert np.max(np.abs(r0)) == 0.0
    th = theta.copy()
    th[0] *= 1.2
    w = transient_weights(wf, m.dt, threshold=0.01 * wf[0], window_s=0.5, rate_window_s=1.0 / 240.0)
    r1 = residuals(m, NAMES, th, state0, u, ui, y, CHANNELS, SCALES).reshape(240, len(CHANNELS))
    rw = residuals(m, NAMES, th, state0, u, ui, y, CHANNELS, SCALES, w).reshape(240, len(CHANNELS))
    assert np.max(np.abs(r1[:24])) < 1e-9 and np.max(np.abs(r1[24:])) > 1e-3
    assert w[30] == 5.0 and w[200] == 1.0
    assert np.allclose(rw[30], np.sqrt(5.0) * r1[30]) and np.allclose(rw[200], r1[200])


@pytest.mark.integration
def test_jacobian_complex_step_matches_central_difference(m, window):
    """The complex-step Jacobian of the residual window agrees with central differences (relative step 1e-6)
    to 1e-4 of its column norm for HP inertia, LP inertia and the combustor lag."""
    state0, u, ui, y, theta, _ = window
    jac = jacobian_cs(m, NAMES, theta, state0, u, ui, y, CHANNELS, SCALES)
    for j in range(theta.size):
        h = 1e-6 * theta[j]
        tp, tm = theta.copy(), theta.copy()
        tp[j] += h
        tm[j] -= h
        fd = (
            residuals(m, NAMES, tp, state0, u, ui, y, CHANNELS, SCALES)
            - residuals(m, NAMES, tm, state0, u, ui, y, CHANNELS, SCALES)
        ) / (2 * h)
        col = jac[:, j]
        assert np.linalg.norm(col) > 0.0
        assert np.linalg.norm(col - fd) <= 1e-4 * np.linalg.norm(col), (NAMES[j], np.linalg.norm(col - fd))


@pytest.mark.integration
@pytest.mark.parametrize("frac", [1.0, 0.85])
def test_linearisation_is_stable(m, frac):
    """The linearised plant at an equilibrium is asymptotically stable (all eigenvalues in the open left
    half-plane) and has the documented input/output names."""
    sch = fx.FixtureSchedules(m)
    u = design_inputs(m)
    u[U_A8] = sch.a8(frac)
    ss = steady_state(m, u, x0=sch.x_at(frac), target=("n2", frac * sch.n2_des))
    A, _, _, _, xn, un, yn = linearize(m, ss)
    assert un == LIN_INPUTS and yn == LIN_OUTPUTS and A.shape == (len(xn), len(xn))
    ev = np.linalg.eigvals(A)
    assert np.all(np.isfinite(ev)) and np.max(ev.real) < 0.0, np.sort(ev.real)[-3:]


@pytest.mark.integration
def test_linear_step_response_matches_nonlinear_small_step(m):
    """A 0.1 % fuel step: the linear model (with the fuel transport delay added) tracks the nonlinear N1, N2
    and T5 responses to within 2 % of the response size from 0.1 s after the fuel arrives to 3 s, and within
    5 % over the whole window (the first ticks differ by up to 3 % in T5 from the sub-tick timing of the
    delayed command, independent of n_sub). The step is kept small because the maps
    are piecewise linear in speed: at this point N2c is 0.2 % below an HPC speed line, and a 0.5 % step
    crosses it (the Jacobian changes there; linearisations are valid per map cell, see the README)."""
    ss = steady_state(m, design_inputs(m, wf_cmd=0.95 * m.design.stations["wf"]))
    A, B, C, D, *_ = linearize(m, ss)
    n = 240 * 3
    dwf = 0.001 * ss.u[U_WF]
    wf = np.full(n, ss.u[U_WF] + dwf)
    y = simulate(m, state_from_x(m, ss.x), *input_block(n, 1, ss.u, wf_cmd=wf)).y[:, 0]
    ad = expm(A * m.dt)
    bd = np.linalg.solve(A, (ad - np.eye(A.shape[0])) @ B[:, 0])
    dx = np.zeros(A.shape[0])
    lin = np.zeros((n, C.shape[0]))
    for k in range(n):
        uk = dwf if k >= m.n_delay else 0.0
        dx = ad @ dx + bd * uk
        lin[k] = C @ dx + D[:, 0] * uk
    for name in ("n1", "n2", "t5"):
        y0 = ss.x[X_N1] if name == "n1" else ss.x[X_N2] if name == "n2" else ss.aux[AUX[name]]
        nl = y[:, Y_NAMES.index(name)] - y0
        li = lin[:, LIN_OUTPUTS.index(name)]
        err = np.abs(nl - li) / np.max(np.abs(nl))
        assert err.max() < 0.05 and err[m.n_delay + 24 :].max() < 0.02, (name, err.max())
