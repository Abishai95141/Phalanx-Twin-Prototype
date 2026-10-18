"""W2.4a A1 (structural side): the M07 ``separate_fixed`` topology passes the M07 structural tests.

- equilibrium = steady state, with a negative control (A3 analogue);
- signs: fuel, shaft load, fan-face distortion, inlet recovery, bypass-nozzle health act in the physical
direction;
  the fan-face path is LP-specific (AD-46);
- determinism: compiled kernel == NumPy reference (``py_func``) bitwise over a busy block and chunked calls,
  and the same source in a fresh ``NUMBA_DISABLE_JIT=1`` process; ``EngineModule`` step == step_block bitwise;
- complex step == central differences for calibrated parameters (AD-22/AD-34);
- cross-engine independence (a disturbance on engine 1 leaves engine 2 bitwise unchanged);
- exposing tests of the PROXY maps (A-W2.4a-3/-8): steady N1c(N2c) against the MEASURED round-2 relation,
and the
  fan stall margin along the operating line. The off-design levels against 687-CAL (the W2.4a-1 part-power
  fuel gap and ram-driven LP spool, A-W2.4a-19, removed by the W2.4a-2 identification, A-W2.4a-21/-22) are
  tested in ``test_proxy_steady.py``, with the unidentified plant as the negative control.

Samples (minimal sufficient): equilibrium 10 s at three operating points; bitwise 48 ticks x 2 engines (and
24 ticks
in the fresh process); complex step 1 s windows for 7 parameters; signs 2 s per channel; operating line 1 % N2
steps from 98 % to 60 % corrected core speed (the range of the measured relation's knots).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest
from scipy.interpolate import PchipInterpolator

from phalanx.core.time import truth_step_times_ns
from phalanx.engine.layout import NX, U_NAMES, U_WF, X_N1, X_N2, Y_N1, Y_N2, Y_NAMES, Y_T5, Y_WF
from phalanx.engine.module import EngineModule
from phalanx.engine.separate import SF_PI, engine_kernel_sf
from phalanx.engine.separate_design import build_separate_model
from phalanx.engine.sim import EngineState, input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state

pytestmark = pytest.mark.integration
SRC = Path(__file__).resolve().parents[2] / "src"
FROZEN = (
    Path(__file__).resolve().parents[2]
    / "analysis"
    / "settling_experiment_round2"
    / "results"
    / "frozen"
    / "S"
    / "ma_readable.json"
)
_POINTS: dict = {}


@pytest.fixture(scope="module")
def model():
    return build_separate_model()


def point(model, n2c_frac: float):
    """Steady state at a corrected-core-speed fraction of design, SLS, by 1 % continuation from design."""
    key = round(n2c_frac, 4)
    if key not in _POINTS:
        d = model.design.derived
        u0 = design_inputs(model)
        s = steady_state(model, u0)
        f = 1.0
        while f > n2c_frac + 1e-9:
            f = max(n2c_frac, f - 0.01)
            s = steady_state(model, u0, x0=s.x, target=("n2", f * d["n2_des"]))
            assert s.converged, f
        _POINTS[key] = s
    return _POINTS[key]


@pytest.mark.parametrize("frac", [1.0, 0.85, 0.66])
def test_equilibrium_is_dynamic_equilibrium(model, frac):
    """Started at the steady solution with the same constant inputs, the dynamic model stays put for 10 s
    (every continuous state within 1e-9 relative; no surge, flame kept)."""
    ss = point(model, frac)
    st = state_from_x(model, ss.x)
    u, ui = input_block(2400, 1, ss.u)
    r = simulate(model, st, u, ui)
    drift = np.max(np.abs(r.state.f[0, :NX] - ss.x) / (np.abs(ss.x) + 1.0))
    assert drift < 1e-9, drift
    assert r.state.i[0, 4] == 0 and r.yi[-1, 0, 1] == 1


def test_equilibrium_negative_control(model):
    ss = point(model, 0.85)
    u, ui = input_block(2400, 1, ss.u)
    u[:, :, U_WF] *= 1.01
    r = simulate(model, state_from_x(model, ss.x), u, ui)
    assert np.max(np.abs(r.state.f[0, :NX] - ss.x) / (np.abs(ss.x) + 1.0)) > 1e-4


def _response(model, **w_or_u):
    """End-of-window outputs (2 s) minus the start, for a step applied at 0.1 s at 85 % N2c."""
    ss = point(model, 0.85)
    n = 480
    u, ui = input_block(n, 1, ss.u)
    for k, v in w_or_u.items():
        if k in U_NAMES:
            u[24:, 0, U_NAMES.index(k)] += v
    r = simulate(model, state_from_x(model, ss.x), u, ui)
    return r.y[-1, 0] - r.y[0, 0]


def test_signs(model):
    """Physical directions at part power (2 s after a step): more fuel speeds both spools and heats T5;
    HP shaft load slows N2; the fan_face LP shaft-torque path (AD-46 amended, efficiency only) lowers the
    airflow and N1, moving N1 several times more than N2; lower inlet recovery lowers both; a larger
    core nozzle (health nozzle_area) unloads
    the LPT exit pressure (P5 falls)."""
    n1, n2, t5, p5 = (Y_NAMES.index(k) for k in ("n1", "n2", "t5", "p5"))
    d = _response(model, wf_cmd=0.01 * point(model, 0.85).u[U_WF])
    assert d[n1] > 0 and d[n2] > 0 and d[t5] > 0
    d = _response(model, w_shaft_load=0.01)
    assert d[n2] < 0
    base = point(model, 0.85).x
    d = _response(model, w_fan_face=0.01)
    w2 = Y_NAMES.index("w2")
    # AD-46 amended (flow share 0): fan_face is the LP shaft-torque path, a fan-efficiency loss; the fan needs
    # more power at the same pressure ratio, so N1 and the airflow fall
    assert d[w2] < 0 and d[n1] < 0
    assert abs(d[n1] / base[X_N1]) > 3.0 * abs(d[n2] / base[X_N2]), "fan_face must be LP-specific (AD-46)"
    # the original AD-46 flow path (flow share 1) for contrast: lower flow capacity, N1 rises
    d1 = _response(model.with_p(fan_face_flow_share=1.0, k_eta_fan_face=0.2), w_fan_face=0.01)
    assert d1[w2] < 0 and d1[n1] > 0
    d = _response(model, w_inlet_recovery=-0.01)
    assert d[n1] < 0
    d = _response(model, h_nozzle_area=0.02)
    assert d[p5] < 0


def _busy_block(model, n=48):
    ss = point(model, 0.95)
    st = state_from_x(model, ss.x, n_engines=2)
    k = np.arange(n)
    w = np.zeros((n, 2, 5))
    w[:, 0, 0] = 0.01 * np.sin(k / 5.0)
    w[:, 0, 4] = 0.01 * np.cos(k / 4.0)
    w[:, 1, 3] = 0.02 * np.cos(k / 3.0)
    u, ui = input_block(n, 2, ss.u, w_engine=w)
    u[20:, 1, U_WF] *= 0.8  # a chop on engine 2 (sub-step and refinement paths)
    return st, u, ui, np.zeros((2, n + 1))


@pytest.mark.determinism
def test_compiled_kernel_equals_reference_bitwise(model):
    """Compiled kernel == ``engine_kernel_sf.py_func`` bitwise over a busy 2-engine block, and chunked calls
    reproduce the single call (block length is a runtime value; AD-22, AD-36)."""
    st, u, ui, z = _busy_block(model)
    args = (model.p, model.tables, u, ui, z, model.dt, model.n_sub, model.n_delay, True)
    c = engine_kernel_sf(st.f, st.i, st.buf, *args)
    r = engine_kernel_sf.py_func(st.f, st.i, st.buf, *args)
    for a, b in zip(c, r, strict=True):
        assert np.array_equal(a, b)
    for chunk in (1, 7, 48):
        f, i, buf, ys = st.f, st.i, st.buf, []
        for j in range(0, 48, chunk):
            f, i, buf, y, _yi, _ = engine_kernel_sf(
                f, i, buf, model.p, model.tables, u[j : j + chunk], ui[j : j + chunk], z, model.dt,
                model.n_sub, model.n_delay, False,
            )  # fmt: skip
            ys.append(y)
        assert np.array_equal(np.concatenate(ys), c[3]), chunk
        assert np.array_equal(f, c[0]) and np.array_equal(i, c[1])


@pytest.mark.determinism
def test_pure_python_reference_in_fresh_process(tmp_path):
    """The same source with NUMBA_DISABLE_JIT=1 (every helper pure Python/NumPy) gives the compiled digest
    (24 ticks from the design-closure state with fuel and fan-face disturbances)."""
    script = textwrap.dedent(
        f"""
        import hashlib, sys
        sys.path.insert(0, {str(SRC)!r})
        import numpy as np
        from phalanx.engine.separate_design import build_separate_model
        from phalanx.engine.sim import input_block, simulate, state_from_x
        from phalanx.engine.steady import design_state, design_inputs
        m = build_separate_model()
        st = state_from_x(m, design_state(m))
        n = 24
        w = np.zeros((n, 1, 5)); w[:, 0, 0] = 0.01 * np.sin(np.arange(n) / 4.0); w[:, 0, 4] = 0.005
        u, ui = input_block(n, 1, design_inputs(m), w_engine=w)
        r = simulate(m, st, u, ui, record_aux=True)
        h = hashlib.sha256()
        for a in (r.y, r.yi, r.aux, r.state.f, r.state.i, r.state.buf):
            h.update(np.ascontiguousarray(a).tobytes())
        print(h.hexdigest())
        """
    )
    path = tmp_path / "ref_run.py"
    path.write_text(script)
    env = {k: v for k, v in os.environ.items() if k != "NUMBA_DISABLE_JIT"}
    ref = subprocess.run(
        [sys.executable, "-I", str(path)], env={**env, "NUMBA_DISABLE_JIT": "1"}, capture_output=True,
        text=True, check=True, timeout=900,
    ).stdout.strip()  # fmt: skip
    comp = subprocess.run(
        [sys.executable, "-I", str(path)], env=env, capture_output=True, text=True, check=True, timeout=900
    ).stdout.strip()
    assert len(ref) == 64 and ref == comp


def test_complex_step_matches_central_differences(model):
    """AD-22/AD-34: d(N1, T5 at 1 s after a fuel step, with a fan-face disturbance on)/d theta by complex step
    equals central differences (1e-4 relative step) to 1e-4 relative, for 9 calibrated parameters including
    the separate-flow ones (bypass nozzle area and discharge, gearbox efficiency, reflected LP inertia) and
    the identified off-design map modifiers (W2.4a-2: fan flow, HPC speed line)."""
    ss = point(model, 0.85)
    n = 240
    w = np.zeros((n, 1, 5))
    w[:, 0, 4] = 0.004
    u, ui = input_block(n, 1, ss.u, w_engine=w)
    u[24:, :, U_WF] *= 1.05
    st = state_from_x(model, ss.x)
    cols = [Y_N1, Y_T5]

    def run(p, f):
        r = simulate(model, EngineState(f, st.i, st.buf.astype(f.dtype)), u, ui, p=p)
        return r.y[-1, 0, cols]

    for nm in (
        "i_lp",
        "i_hp",
        "a18",
        "cd18",
        "eta_gearbox",
        "k_eta_fan_face",
        "v5",
        "fan_wc_mod_a",
        "hpc_nc_mod_a",
    ):
        j = SF_PI[nm]
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


@pytest.mark.determinism
def test_cross_engine_independence(model):
    """A disturbance on engine 1 leaves engine 2 bitwise unchanged (no hidden cross-engine coupling)."""
    ss = point(model, 0.9)
    st = state_from_x(model, ss.x, n_engines=2)
    n = 240
    w = np.zeros((n, 2, 5))
    w[:, 0, :] = 0.01
    u, ui = input_block(n, 2, ss.u, w_engine=w)
    u0, ui0 = input_block(n, 2, ss.u)
    a = simulate(model, st, u, ui)
    b = simulate(model, st, u0, ui0)
    assert np.array_equal(a.y[:, 1], b.y[:, 1])
    assert not np.array_equal(a.y[:, 0], b.y[:, 0])


@pytest.mark.determinism
def test_module_step_equals_block_and_four_engines(model):
    """``EngineModule`` with the separate_fixed model (proxy n_engines = 4): step == step_block bitwise; the
    initial outputs are the steady design point; no afterburner state ever."""
    ss = point(model, 0.9)
    m = EngineModule("eng", model, n_engines=4, init_x=ss.x, init_u=ss.u)
    from phalanx.core.rng import KeyPath, RngService, StreamRegistry

    m.bind(RngService(7, StreamRegistry(m.streams)).scope(KeyPath.of(scenario="t", tail="P", sortie=1)))
    s0 = m.init(m.params, None)
    out0 = m.initial_outputs(s0)
    assert np.allclose(out0["n2"], ss.x[X_N2])
    n = 12
    rng_w = np.linspace(0, 0.01, n * 4 * 5).reshape(n, 4, 5)
    inputs = {
        "wf_cmd": np.full((n, 4), ss.u[U_WF]),
        "wf_ab_cmd": np.zeros((n, 4)),
        "a8_cmd": np.full((n, 4), 0.1),
        "vg_cmd": np.tile(ss.x[[10, 11]], (n, 4, 1)),
        "ignition": np.zeros((n, 4), np.int64),
        "ab_enable": np.ones((n, 4), np.int64),
        "t_s": np.full(n, 288.15),
        "p_s": np.full(n, 101325.0),
        "q_spec": np.zeros(n),
        "mach": np.zeros(n),
        "w_engine": rng_w,
        "bleed_extract": np.zeros((n, 4)),
        "pto_power": np.zeros((n, 4)),
        "fuel_inlet_t": np.full((n, 4), ss.u[U_NAMES.index("t_fuel")]),
        "health": np.zeros((n, 4, 10)),
    }
    t = truth_step_times_ns(np.arange(n, dtype=np.int64))
    sb, ob = m.step_block(s0, inputs, t, 1.0 / 240)
    s = s0
    for k in range(n):
        s, o = m.step(s, {kk: v[k] for kk, v in inputs.items()}, int(t[k]), 1.0 / 240)
        for kk in o:
            assert np.array_equal(o[kk], ob[kk][k]), kk
    for kk in sb:
        assert np.array_equal(s[kk], sb[kk]), kk
    assert np.all(ob["ab_state"] == 0) and np.all(ob["wf_ab"] == 0.0)


def _measured_h():
    d = json.loads(FROZEN.read_text())["readable"]["N1"]
    return PchipInterpolator(np.asarray(d["h_knots_x"]), np.asarray(d["h_knots_y"]))


def test_operating_line_against_measured_n1c_n2c(model):
    """Exposing test of PROXY A-W2.4a-3/-8/-21 (no booster component; scaled AXI5 fan map with the identified
    off-design modifiers) and of the cycle assumptions A-W2.4a-1: the steady SLS N1c(N2c) operating line
    against the round-2 MEASURED Mach-independent relation (frozen M-A h-map, 687-CAL) between 60 % and 98 %
    N2c. The W2.4a-1 generic plant had max |error| 4.3 % N1. The W2.4a-2 identification (fitted at the
    recorded flight conditions) matches h within 2 % N1 in cruise and at flight idle but leaves the model's h
    dependent on flight Mach: at SLS, N1 is 3-7 % low between 84 and 96 % N2c (CAL take-off rolls at M 0.2: -4
    %, the documented limitation of the speed-dependent modifier family, A-W2.4a-21). The bound 8 % N1 records
    it."""
    h = _measured_h()
    n1_100, n2_100 = float(model.params.value("n1_100pct")), float(model.params.value("n2_100pct"))
    errs = []
    for f in np.arange(0.98, 0.605, -0.02):
        s = point(model, float(f))  # SLS ISA: corrected = physical (theta2 = 1)
        n2c = 100.0 * s.x[X_N2] / n2_100
        n1c = 100.0 * s.x[X_N1] / n1_100
        errs.append(n1c - float(h(n2c)))
    errs = np.asarray(errs)
    assert np.max(np.abs(errs)) < 8.0, errs
    # the relation is monotone in the model too
    assert np.all(np.diff([point(model, float(f)).x[X_N1] for f in np.arange(0.98, 0.605, -0.02)]) < 0)


def test_fan_margin_positive_along_operating_line(model):
    """Exposing test of the PROXY fan map (A-W2.4a-8) and the low-PR margin convention (A-W2.4a-9): the fan
    and HPC stall margins stay above the surge trigger from design down to 60 % N2c at SLS; the fan's relative
    margin shrinks toward idle (about +0.8 % at 62 %), which is why the PROXY trigger sits at -1 %."""
    trig = model.p[SF_PI["sm_trigger"]]
    sm = []
    for f in np.arange(0.98, 0.605, -0.02):
        a = point(model, float(f)).aux_dict()
        sm.append((a["sm_fan"], a["sm_hpc"]))
    sm = np.asarray(sm)
    assert np.all(sm > trig), sm
    assert np.all(sm[:, 0] > 0.0)
    assert sm[-1, 0] < 0.02  # the thin low-PR margin is real in this map (documented limitation)


def test_fuel_flow_is_metered_flow_output(model):
    """``eng.wf`` is the metered flow including the fuel-metering disturbance (same semantics as mixed_ab)."""
    ss = point(model, 0.9)
    w = np.zeros((24, 1, 5))
    w[:, 0, 0] = 0.02
    u, ui = input_block(24, 1, ss.u, w_engine=w)
    r = simulate(model, state_from_x(model, ss.x), u, ui)
    assert np.allclose(r.y[-1, 0, Y_WF], r.state.f[0, 8] * 1.02, rtol=1e-15)
    assert r.y[-1, 0, Y_N2] > 0


def test_gas_path_lag_prototype(model):
    """PROTOTYPE A-W2.4a-23 (W2.4a-2 stage 3, off by default): with the gas-path thermal lag on, the station
    T5 equals the gas T5 at steady state, follows a fuel step as a first-order lag (kappa = 1: 63 % of the gas
    change after one time constant), and leaves the cycle (N1, N2) unchanged; tau = 0 is the committed
    kernel."""
    tau = 1.0
    m_on = model.with_p(gp_lag_tau=tau, gp_lag_kappa=1.0)
    ss_off = point(model, 0.85)
    ss_on = steady_state(m_on, ss_off.u, x0=ss_off.x)
    assert ss_on.converged
    assert abs(ss_on.aux_dict()["t5"] - ss_off.aux_dict()["t5"]) < 1e-6  # unity at steady state
    n = 2 * 240
    u, ui = input_block(n, 1, ss_off.u)
    u[24:, 0, U_WF] *= 1.02
    r_off = simulate(model, state_from_x(model, ss_off.x), u, ui)
    r_on = simulate(m_on, state_from_x(m_on, ss_on.x), u, ui)
    assert np.allclose(r_on.y[:, 0, Y_N1], r_off.y[:, 0, Y_N1], rtol=1e-10)  # the cycle is untouched
    assert np.allclose(r_on.y[:, 0, Y_N2], r_off.y[:, 0, Y_N2], rtol=1e-10)
    # the station T5 lags the gas T5: compare the change from the step at 0.1 s to 1.1 s (one tau later) with
    # the first-order response of the gas history (discrete, 240 Hz)
    gas = r_off.y[:, 0, Y_T5]
    k = np.arange(n)
    lag = np.empty(n)
    xs = gas[0]
    a = 1.0 - np.exp(-1.0 / (240.0 * tau))
    for j in k:
        xs = xs + a * (gas[j] - xs)
        lag[j] = xs
    j1 = 24 + 240
    assert abs((r_on.y[j1, 0, Y_T5] - gas[0]) - (lag[j1] - gas[0])) < 0.05 * abs(gas[j1] - gas[0])
    assert abs(r_on.y[j1, 0, Y_T5] - gas[0]) < 0.8 * abs(gas[j1] - gas[0])  # a real lag, not the gas
