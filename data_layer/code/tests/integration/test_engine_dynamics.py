"""M07 dynamic shell: equilibrium = steady state (A3), kernel = reference (A7), complex step (A7), numerics.

Samples (minimal sufficient): equilibrium drift 10 s at three operating points; bitwise checks 48 ticks with
two engines, disturbances and an AB attempt (compiled vs outer-loop py_func) and 24 ticks in a fresh
``NUMBA_DISABLE_JIT=1`` process (pure NumPy/Python reference); complex step 1 s windows; step halving on an
8 s part-power fuel step; one 2 s stiff chop transient for the sub-step refinement.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

from phalanx.engine.design import build_engine_model
from phalanx.engine.kernel import engine_kernel
from phalanx.engine.layout import NX, PI, U_A8, U_WF, X_TM, Y_NAMES
from phalanx.engine.sim import EngineState, input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state

SRC = Path(__file__).resolve().parents[2] / "src"


@pytest.fixture(scope="module")
def model():
    return build_engine_model()


def _point(model, wf_frac: float, a8_ratio: float):
    u = design_inputs(model)
    u[U_WF] *= wf_frac
    u[U_A8] *= a8_ratio
    ss = steady_state(model, u)
    assert ss.converged
    return ss


@pytest.mark.integration
@pytest.mark.parametrize("wf_frac,a8_ratio", [(1.0, 1.0), (0.6, 1.1), (0.25, 1.4)])
def test_steady_state_is_dynamic_equilibrium(model, wf_frac, a8_ratio):
    """A3: started at the CLM solution with the same constant inputs, the dynamic model stays put for 10 s.
    Tolerance: 1e-9 relative on every continuous state (the steady solver's residual is ~1e-12/s)."""
    ss = _point(model, wf_frac, a8_ratio)
    st = state_from_x(model, ss.x)
    u, ui = input_block(2400, 1, ss.u)
    r = simulate(model, st, u, ui)
    drift = np.max(np.abs(r.state.f[0, :NX] - ss.x) / (np.abs(ss.x) + 1.0))
    assert drift < 1e-9, drift
    assert r.state.i[0, 4] == 0  # no surge


@pytest.mark.integration
def test_equilibrium_negative_control(model):
    """A3 is not vacuous: a 1 % fuel offset from the steady input moves the state by far more than the
    tolerance."""
    ss = _point(model, 0.6, 1.1)
    st = state_from_x(model, ss.x)
    u, ui = input_block(2400, 1, ss.u)
    u[:, :, U_WF] *= 1.01
    r = simulate(model, st, u, ui)
    assert np.max(np.abs(r.state.f[0, :NX] - ss.x) / (np.abs(ss.x) + 1.0)) > 1e-4


def _busy_block(model, n=48):
    """Two engines, different disturbances, an AB attempt on engine 1 (exercises every branch type)."""
    ss = _point(model, 0.95, 1.0)
    st = state_from_x(model, ss.x, n_engines=2)
    k = np.arange(n)
    w = np.zeros((n, 2, 5))
    w[:, 0, 0] = 0.01 * np.sin(k / 5.0)
    w[:, 1, 3] = 0.02 * np.cos(k / 3.0)
    ab = np.zeros((n, 2), dtype=np.int64)
    ab[5:, 0] = 1
    wfab = np.zeros((n, 2))
    wfab[5:, 0] = 0.5
    u, ui = input_block(n, 2, ss.u, w_engine=w, ab_enable=ab, wf_ab_cmd=wfab)
    z = np.vstack([np.linspace(-1, 1, n + 1), np.linspace(1, -1, n + 1)])
    return st, u, ui, z


@pytest.mark.integration
@pytest.mark.determinism
def test_compiled_kernel_equals_reference_bitwise(model):
    """A7: compiled kernel == NumPy reference (``engine_kernel.py_func`` outer loop) bitwise over a block, and
    chunked calls (block length is a runtime value) reproduce the single call."""
    st, u, ui, z = _busy_block(model)
    args = (model.p, model.tables, u, ui, z, model.dt, model.n_sub, model.n_delay, True)
    c = engine_kernel(st.f, st.i, st.buf, *args)
    r = engine_kernel.py_func(st.f, st.i, st.buf, *args)
    for a, b in zip(c, r, strict=True):
        assert np.array_equal(a, b)
    assert np.array_equal(st.f, state_from_x(model, st.f[0, :NX], n_engines=2).f)  # inputs untouched
    for chunk in (1, 7, 48):
        f, i, buf, ys = st.f, st.i, st.buf, []
        for j in range(0, 48, chunk):
            # each chunk gets the draws for attempts starting at its own counter
            zz = np.stack([z[e, (i[e, 5] - st.i[e, 5]) + np.arange(chunk + 1)] for e in range(2)])
            f, i, buf, y, _yi, _ = engine_kernel(
                f, i, buf, model.p, model.tables, u[j : j + chunk], ui[j : j + chunk], zz, model.dt,
                model.n_sub, model.n_delay, False,
            )  # fmt: skip
            ys.append(y)
        assert np.array_equal(np.concatenate(ys), c[3]), chunk
        assert np.array_equal(f, c[0]) and np.array_equal(i, c[1])


@pytest.mark.integration
@pytest.mark.determinism
def test_pure_python_reference_in_fresh_process(model, tmp_path):
    """A7: the same source with NUMBA_DISABLE_JIT=1 (every helper pure Python/NumPy) gives bitwise the
    compiled outputs. Two windows, digests compared across processes: 24 ticks, 1 engine, disturbance on;
    and 12 ticks of an HPT flow-capacity step at the design point that triggers the error-controlled
    refinement (sub-step doubling); and the re-review's 240-tick HPT-blockage window at 90 % fuel (where
    ``x ** 2`` once compiled to ``x * x`` but ran libm ``pow`` uncompiled: the kernel now writes integer
    powers as products). All start from the design-closure state: the steady solver's complex-step
    Jacobians differ between compiled and pure-Python complex arithmetic at about 1e-13 (float paths are
    bitwise), so a solver-produced start would differ at that level."""
    script = textwrap.dedent(
        f"""
        import hashlib, sys
        sys.path.insert(0, {str(SRC)!r})
        import numpy as np
        from phalanx.engine.design import build_engine_model
        from phalanx.engine.sim import input_block, simulate, state_from_x
        from phalanx.engine.steady import design_state, design_inputs
        m = build_engine_model()
        u0 = design_inputs(m)
        st = state_from_x(m, design_state(m))
        n = 24
        w = np.zeros((n, 1, 5)); w[:, 0, 0] = 0.01 * np.sin(np.arange(n) / 4.0)
        u, ui = input_block(n, 1, u0, w_engine=w)
        r = simulate(m, st, u, ui, record_aux=True)
        hl = np.zeros((12, 1, 10)); hl[:, 0, 5] = -0.15
        u2, ui2 = input_block(12, 1, u0, health=hl)
        r2 = simulate(m, st, u2, ui2, record_aux=True)
        r2o = simulate(m.with_p(int_tol=1e9), st, u2, ui2)
        assert not np.array_equal(r2.y, r2o.y)  # the refinement did act in this window
        # HPT blockage at 90 % fuel (W1.3a re-review case: integer powers once diverged at tick 104)
        u9 = u0.copy(); u9[0] *= 0.9
        hb = np.zeros((240, 1, 10)); hb[24:120, 0, 5] = -0.15
        u3, ui3 = input_block(240, 1, u9, health=hb)
        r3 = simulate(m, st, u3, ui3, record_aux=True)
        h = hashlib.sha256()
        for a in (r.y, r.yi, r.aux, r.state.f, r.state.i, r.state.buf, r2.y, r2.aux, r2.state.f, r2.state.i,
                  r3.y, r3.yi, r3.aux, r3.state.f, r3.state.i):
            h.update(np.ascontiguousarray(a).tobytes())
        print(h.hexdigest())
        """
    )
    path = tmp_path / "ref_run.py"
    path.write_text(script)
    env = {k: v for k, v in os.environ.items() if k != "NUMBA_DISABLE_JIT"}
    ref = subprocess.run(
        [sys.executable, "-I", str(path)], env={**env, "NUMBA_DISABLE_JIT": "1"}, capture_output=True,
        text=True, check=True, timeout=600,
    ).stdout.strip()  # fmt: skip
    comp = subprocess.run(
        [sys.executable, "-I", str(path)], env=env, capture_output=True, text=True, check=True, timeout=600
    ).stdout.strip()
    assert len(ref) == 64 and ref == comp


@pytest.mark.integration
def test_complex_step_matches_central_differences(model):
    """A7/AD-34: d(N1, T5 at 1 s after a fuel step)/d theta by complex step equals central finite differences
    for 7 calibrated parameters. Tolerance 1e-4 relative. The finite-difference step is 1e-4 relative: at 1e-6
    and below the difference quotient is dominated by output rounding (fixed-count Newton inversions leave
    about 1e-12 relative noise; observed FD scatter 1e-4 at 1e-6 and 1e-3 at 1e-7, while 1e-4 and 1e-5 agree
    with complex step to < 1e-5). Complex step needs no step-size tuning (h = 1e-30)."""
    ss = _point(model, 0.6, 1.1)
    n = 240
    u, ui = input_block(n, 1, ss.u)
    u[24:, :, U_WF] *= 1.05
    st = state_from_x(model, ss.x)
    cols = [Y_NAMES.index("n1"), Y_NAMES.index("t5")]

    def run(p, f):
        r = simulate(model, EngineState(f, st.i, st.buf.astype(f.dtype)), u, ui, p=p)
        return r.y[-1, 0, cols]

    names = ("i_lp", "i_hp", "tau_comb", "ha_metal", "s_eff_hpt", "k13", "v3")
    for nm in names:
        j = PI[nm]
        pc = model.p.astype(np.complex128)
        pc[j] += 1e-30j
        d_cs = run(pc, st.f.astype(np.complex128)).imag / 1e-30
        e = 1e-4 * abs(model.p[j])
        pp, pm = model.p.copy(), model.p.copy()
        pp[j] += e
        pm[j] -= e
        d_fd = (run(pp, st.f) - run(pm, st.f)) / (2 * e)
        assert np.all(np.abs(d_cs - d_fd) <= 1e-4 * np.abs(d_cs) + 1e-9), (nm, d_cs, d_fd)
        assert np.any(d_cs != 0.0), nm


@pytest.mark.integration
def test_step_halving_convergence():
    """A-W1.3a-6: the sub-stepped Heun integration converges at second order and n_sub = 4 is within 5e-4
    relative of n_sub = 32 on an 8 s part-power fuel step (n_sub = 2, 4, 8, 32; refinement and the stiffness
    sub-step selection switched off so
    the base scheme is measured)."""
    base_m = build_engine_model()
    ss = _point(base_m, 0.4, 1.2)
    n = 240 * 8
    out = {}
    for ns in (2, 4, 8, 32):
        m = build_engine_model(n_sub=ns).with_p(int_tol=1e9, stab_hlam=1e9)
        u, ui = input_block(n, 1, ss.u)
        u[240:, :, U_WF] *= 1.3
        out[ns] = simulate(m, state_from_x(m, ss.x), u, ui).y[:, 0, :]
    scale = np.abs(out[32]).max(axis=0) + 1e-12
    err = {ns: float(np.max(np.abs(out[ns] - out[32]) / scale)) for ns in (2, 4, 8)}
    assert err[4] < 5e-4 and err[8] < err[4] < err[2]
    assert 2.5 < err[2] / err[4] < 6.0  # second order (ideal 4)


@pytest.mark.integration
@pytest.mark.parametrize(
    "v5,wf_frac,a8_ratio,t_s",
    [(None, 1.0, 1.0, 288.15), (None, 1.0, 1.0, 318.15), (None, 0.5, 1.5, 288.15), (0.05, 1.0, 1.0, 288.15)],
)
def test_stiffness_estimate_bounds_eigenvalues(v5, wf_frac, a8_ratio, t_s):
    """A-W1.3a-6: the kernel's stiffness estimate lam_est (aux) tracks the fastest linearised eigenvalue
    (0.85-1.3 x |lambda|) at MIL, hot-day MIL, part power and the small-V5 sweep end, and the sub-step count
    it selects keeps the explicit Heun step inside its real-axis stability region (hs |lambda| < 1.8 < 2)."""
    import math

    from phalanx.engine.design import load_engine_params
    from phalanx.engine.layout import PI, U_TS, A
    from phalanx.engine.steady import linearize

    ps = load_engine_params() if v5 is None else load_engine_params().replace(v5=v5)
    m = build_engine_model(ps)
    u = design_inputs(m)
    u[U_WF] *= wf_frac
    u[U_A8] *= a8_ratio
    u[U_TS] = t_s
    ss = steady_state(m, u)
    lam = -np.linalg.eigvals(linearize(m, ss)[0]).real.min()
    est = ss.aux[A["lam_est"]]
    assert 0.85 * lam <= est <= 1.3 * lam, (est, lam)
    n = max(m.n_sub, math.ceil(m.dt * est / m.p[PI["stab_hlam"]]))
    assert m.dt / n * lam < 1.8, (n, lam)


@pytest.mark.integration
def test_default_numerics_accuracy_bound():
    """A-W1.3a-6 performance default: n_sub = 2 with refinement and NEWTON_T = 2 stays within 1.3e-4 (max
    relative output error, per-channel scale) of the n_sub = 32 reference on the 8 s part-power fuel step
    (measured 5.5e-5 with the stiffness-based count; 1.29e-4 without it; n_sub 4: 3.0e-5). Sample: one 8 s
    transient."""
    from phalanx.engine import thermo

    base = build_engine_model()
    assert base.n_sub == 2 and thermo.NEWTON_T == 2
    ss = _point(base, 0.4, 1.2)
    n = 240 * 8
    u, ui = input_block(n, 1, ss.u)
    u[240:, :, U_WF] *= 1.3
    ref = simulate(base, state_from_x(base, ss.x), u, ui, n_sub=32).y[:, 0, :]
    y = simulate(base, state_from_x(base, ss.x), u, ui).y[:, 0, :]
    scale = np.abs(ref).max(axis=0) + 1e-12
    assert float(np.max(np.abs(y - ref) / scale)) <= 1.3e-4


@pytest.mark.integration
def test_refinement_converges_stiff_events():
    """A-W1.3a-6: a fuel chop to 60 % and back at the design nozzle (fan surge pops on recovery) with a small
    LPT-exit volume (V5 0.08 m^3, inside its sweep) is unstable for plain n_sub = 4 (stiffness selection and
    refinement off: spurious extra surges, reverse core flow, N1 run-away; negative control) but the default
    numerics (n_sub 2, stiffness-based sub-step count, error-controlled refinement) reproduce the
    n_sub = 64 solution: same surge count, no reverse core flow, N1 path within 1 % (the residual is the
    one-tick quantisation of the surge-trigger instant, a discrete-event knife edge, not integration error;
    n_sub 64 and 256 agree to 5e-6). Sample: one 2 s transient."""
    from phalanx.engine.design import load_engine_params
    from phalanx.engine.layout import I_NSURGE, A

    ps = load_engine_params().replace(v5=0.08)
    runs = {}
    for lab, m in (
        ("plain4", build_engine_model(ps, n_sub=4).with_p(int_tol=1e9, stab_hlam=1e9)),
        ("default", build_engine_model(ps)),
        ("plain64", build_engine_model(ps, n_sub=64).with_p(int_tol=1e9, stab_hlam=1e9)),
    ):
        ss = steady_state(m, design_inputs(m))
        n = 480
        wf = np.full(n, ss.u[U_WF])
        wf[24:240] *= 0.6
        r = simulate(m, state_from_x(m, ss.x), *input_block(n, 1, ss.u, wf_cmd=wf), record_aux=True)
        runs[lab] = (r.y[:, 0, 0], int(r.state.i[0, I_NSURGE]), float(r.aux[:, 0, A["w5mix"]].min()))
    ref, ref_surges, _ = runs["plain64"]
    n1, surges, w5 = runs["default"]
    assert np.max(np.abs(n1 / ref - 1.0)) < 1e-2 and surges == ref_surges and w5 > 0.0
    bad, bad_surges, bad_w5 = runs["plain4"]
    assert np.max(np.abs(bad / ref - 1.0)) > 0.05 and (bad_surges != ref_surges or bad_w5 < 0.0)


@pytest.mark.integration
def test_heat_soak_slows_cold_slam_and_relaxes(model):
    """A-W1.3a-8: from a cold-metal state (metal 300 K below equilibrium) the same fuel step gives a lower T5
    (heat absorbed by the metal) than from the soaked state, and the metal relaxes with a tens-of-seconds time
    constant (between 10 and 120 s)."""
    ss = _point(model, 0.6, 1.1)
    n = 240 * 20
    u, ui = input_block(n, 1, ss.u)
    hot = simulate(model, state_from_x(model, ss.x), u, ui).y[:, 0, :]
    xc = ss.x.copy()
    xc[X_TM] -= 300.0
    cold = simulate(model, state_from_x(model, xc), u, ui, record_aux=True)
    t5 = Y_NAMES.index("t5")
    assert cold.y[240, 0, t5] < hot[240, t5] - 2.0
    tm = cold.state.f[0, X_TM]
    gap = ss.x[X_TM] - tm
    tau = 20.0 / np.log(300.0 / gap)
    assert 10.0 < tau < 120.0, tau
