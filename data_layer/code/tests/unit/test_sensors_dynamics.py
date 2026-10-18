"""M12 sensor dynamics (acceptance A1 laws, A8 kernel equivalence and complex-step safety).

Data-free: every input is a constructed truth trajectory with a known analytic or high-accuracy reference.
Sample sizes are frames of 1/240 s, stated per test.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_params
from phalanx.sensors import kernel as K
from phalanx.sensors.config import build_sensor_config

DT = 1.0 / 240.0
pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


@pytest.fixture(scope="module")
def m12():
    return load_params("M12")


def cfg_for(d, *channels, params=None):
    return build_sensor_config(d, channels=channels, params=params)


def rows(cfg, L, values):
    """Truth matrix (L, n_u): ``values`` maps signal -> scalar, (L,) or (L, size) array."""
    U = np.zeros((L, cfg.n_u))
    for s in cfg.inputs:
        if s.signal in values:
            v = np.asarray(values[s.signal], dtype=np.float64)
            U[:, s.col0 : s.col0 + s.size] = np.broadcast_to(
                v.reshape(v.shape[0] if v.ndim else 1, -1), (L, s.size)
            )
    return U


def init_state(cfg, dtype=np.float64):
    ef = np.zeros((cfg.n_el, K.N_EF), dtype=dtype)
    ef[:, K.EF_SLOW] = 1.0
    ci = np.zeros((cfg.n_ch, K.N_CI), dtype=np.int64)
    ci[:, K.CI_HOLDIDX] = -1
    return ef, np.zeros((cfg.n_el, K.N_EI), np.int64), np.zeros((cfg.n_ch, K.N_CF), dtype=dtype), ci


def run(cfg, U, *, el_p=None, kernel=K.m12_kernel, state=None, k0=0, n_sub=None, bias=None):
    L = U.shape[0]
    ef, ei, cf, ci = (
        state if state is not None else init_state(cfg, (el_p if el_p is not None else cfg.el_p).dtype)
    )
    t_end = ((np.arange(k0, k0 + L, dtype=np.int64) + 1) * 10**9) // 240
    b = np.zeros((L, cfg.n_ch)) if bias is None else bias
    return kernel(
        ef,
        ei,
        cf,
        ci,
        cfg.el_i,
        cfg.el_p if el_p is None else el_p,
        cfg.ch_i,
        cfg.ch_p,
        cfg.tx,
        cfg.ty,
        cfg.toff,
        cfg.cols,
        cfg.k,
        U,
        b,
        t_end,
        np.zeros((L, cfg.n_ch)),
        DT,
        cfg.n_sub if n_sub is None else n_sub,
    )


def test_lag1_matches_exact_ramp_response(d, m12):
    """Oil-pressure transmitter (tau 1 s, TRANSFER MIL-PRF-25435D) driven by a ramp from a steady start:
    y(t) = u(t) - r tau (1 - exp(-t/tau)). The first-order-hold solution is exact (n = 480 frames)."""
    cfg = cfg_for(d, "ENG.OIL_P")
    tau = float(m12["oil_pressure"].value("tau"))
    L = 480
    t = np.arange(L) * DT  # frame j ends at (j + 1) DT; ramp starts at the end of frame 0
    r = 2.0e4
    u = 3.0e5 + r * t
    S = run(cfg, rows(cfg, L, {"eng.oil_p": u}))[4][:, 0]
    exact = u - r * tau * (1.0 - np.exp(-t / tau))
    np.testing.assert_allclose(S, exact, rtol=1e-12, atol=1e-6)


def _tau_from_step(y, y0, y1):
    """Time [s] after the ramp start at which a step response crosses 63.2 % (y[i] is at (i + 1) DT after it;
    linear interpolation between frames)."""
    f = (y - y0) / (y1 - y0)
    j = int(np.argmax(f >= 1.0 - np.exp(-1.0)))
    a, b = f[j - 1], f[j]
    return (j + (1.0 - np.exp(-1.0) - a) / (b - a)) * DT


@pytest.mark.parametrize("w_frac", [1.0, 0.25, 0.05])
def test_flux_scaled_time_constant(d, m12, w_frac):
    """T5 probe: tau = tau_ref (W/W_ref)^-0.5 (AGARD law, AD-23). A step (ramp over one frame) at constant
    airflow W gives the 63.2 % time; it must equal the law within 1 % (n = 3,000 frames)."""
    cfg = cfg_for(d, "ENG.T5.HARNESS_A")
    ps = m12["tc_t5"]
    tau_ref, w_ref = float(ps.value("tau")), float(ps.value("w_ref"))
    L = 3000
    t5 = np.full(L, 800.0)
    t5[1:] = 900.0
    S = run(cfg, rows(cfg, L, {"eng.t5": t5, "eng.w2": w_frac * w_ref}))[4][:, 0]
    # the step is a ramp over frame 1; the response of a lag to a one-frame ramp is delayed by DT/2
    tau_meas = _tau_from_step(S[1:], 800.0, 900.0) - 0.5 * DT
    assert tau_meas == pytest.approx(tau_ref * w_frac**-0.5, rel=0.002)


def test_flux_law_floor_caps_tau(d, m12):
    """Below the floor W/W_ref = w_min_frac the time constant stops growing (engine off: no infinite tau)."""
    cfg = cfg_for(d, "ENG.T5.HARNESS_A")
    ps = m12["tc_t5"]
    tau_cap = float(ps.value("tau")) * float(ps.value("w_min_frac")) ** -0.5
    L = 6000
    t5 = np.full(L, 800.0)
    t5[1:] = 900.0
    S = run(cfg, rows(cfg, L, {"eng.t5": t5, "eng.w2": 0.0}))[4][:, 0]
    assert _tau_from_step(S[1:], 800.0, 900.0) - 0.5 * DT == pytest.approx(tau_cap, rel=0.002)


def _second_order_reference(t_end, u_fun, wn, zeta):
    sol = solve_ivp(
        lambda t, z: [z[1], wn * wn * (u_fun(t) - z[0]) - 2 * zeta * wn * z[1]],
        (0.0, t_end[-1]),
        [0.0, 0.0],
        t_eval=t_end,
        rtol=1e-11,
        atol=1e-14,
        max_step=DT / 20,
    )
    return sol.y[0]


def test_lag2_step_matches_analytic(d, m12):
    """Rate gyro (w_n 2 pi 50 Hz, zeta 0.7): trapezoidal sub-stepping vs a tight ODE solution of the same
    piecewise-linear input. Error < 0.5 % of the step at n_sub = 8 and shrinks ~4x at n_sub = 16 (2nd order).
    n = 120 frames (0.5 s, > 60 time constants)."""
    cfg = cfg_for(d, "FCS.RSA.Q.A")
    ps = m12["rate_gyro"]
    wn, zeta = float(ps.value("wn")), float(ps.value("zeta"))
    L = 120
    q = np.full(L, 0.1)
    q[0] = 0.0
    om = np.zeros((L, 3))
    om[:, 1] = q
    t_end = (np.arange(L) + 1) * DT
    ref = _second_order_reference(t_end, lambda t: 0.1 * min(max((t - DT) / DT, 0.0), 1.0), wn, zeta)
    e8 = np.max(np.abs(run(cfg, rows(cfg, L, {"af.omega_body": om}), n_sub=8)[4][:, 0] - ref))
    e16 = np.max(np.abs(run(cfg, rows(cfg, L, {"af.omega_body": om}), n_sub=16)[4][:, 0] - ref))
    assert e8 < 0.005 * 0.1
    assert e16 < e8 / 3.0
    assert run(cfg, rows(cfg, L, {"af.omega_body": om}))[4][-1, 0] == pytest.approx(0.1, abs=1e-9)


def test_vane_natural_frequency_scales_with_eas(d, m12):
    """AoA vane: f_n = kf V_EAS (TN D-8242 form). A small alpha step rings at the damped frequency
    w_n sqrt(1 - zeta^2); doubling EAS doubles it (within 2 %). n = 240 frames per run, 8 sub-steps."""
    cfg = cfg_for(d, "AD.AOA_VANE_L.A")
    ps = m12["vane_aoa"]
    kf, zeta = float(ps.value("kf")), float(ps.value("zeta"))
    freqs = []
    for eas in (60.0, 120.0):
        L = 240
        a = np.full(L, 0.05)
        a[0] = 0.04
        vals = {"af.alpha": a, "af.tas": eas, "env.rho": 1.225, "af.mach": 0.3, "af.nz": 1.0}
        S = run(cfg, rows(cfg, L, vals))[4][:, 0]
        x = S - S[-1]
        tt = (np.arange(L) + 1) * DT
        crossings = [tt[j] - x[j] * DT / (x[j + 1] - x[j]) for j in range(1, L - 1) if x[j] * x[j + 1] < 0]
        f_meas = 1.0 / (2.0 * np.mean(np.diff(crossings[:12])))
        f_exp = kf * eas * np.sqrt(1.0 - zeta**2)
        assert f_meas == pytest.approx(f_exp, rel=0.02)
        freqs.append(f_meas)
    assert freqs[1] / freqs[0] == pytest.approx(2.0, rel=0.02)


def test_steady_start_has_no_transient(d):
    """A-W1.6-2: the first frame primes every element in steady state, so constant truth gives constant
    readings from frame 0 (no artificial start transient), for every Tejas sensor class (n = 48 frames)."""
    cfg = build_sensor_config(d)
    L = 48
    # the W1.6 inputs keep their values (inputs W2.2 added are set apart, so the enumeration does not move)
    w22 = {
        "eng.ab_state",
        "util.brake_p",
        "util.hyd_res_level",
        "util.fuel_inlet_t",
        "util.ecs_t",
        "util.ecs_p",
    }
    w22.add("util.probe_heat")
    numeric = [s for s in cfg.inputs if s.signal not in w22]
    vals = {s.signal: np.full((L, s.size), 1.0 + 0.1 * j) for j, s in enumerate(numeric)}
    vals["eng.ab_state"] = np.full((L, 1), 2.0)  # afterburner lit: the UV flame detector reads a steady 1
    vals["util.probe_heat"] = np.ones((L, 1))  # TAT heater on, as the W1.6 test assumed (heater_on)
    for sig in w22 - {"eng.ab_state", "util.probe_heat"}:
        size = next(s.size for s in cfg.inputs if s.signal == sig)
        vals[sig] = np.full((L, size), 0.5)
    vals.update({"env.p_s": 50000.0, "env.t_s": 250.0, "af.mach": 0.8, "env.rho": 0.7, "af.tas": 250.0})
    vals["af.f_spec_body"] = np.tile([0.0, 0.0, -9.80665], (L, 1))
    S = run(cfg, rows(cfg, L, vals))[4]
    np.testing.assert_array_equal(S, np.broadcast_to(S[0], S.shape))


def test_static_elements_follow_truth(d):
    """LVDT/RVDT, speed pick-offs and bus voltages carry no M12 dynamics (A-W1.6-10): the reading equals the
    truth at every frame of an arbitrary trajectory (n = 100 frames)."""
    cfg = cfg_for(d, "ENG.CVG", "ENG.N2.A", "ELEC.DCBUS.V.MAIN")
    L = 100
    g = np.random.Generator(np.random.Philox(np.random.SeedSequence(16, spawn_key=(1,))))
    vals = {
        "eng.vg_vsv": g.normal(size=L),
        "eng.n2": 1700 + g.normal(size=L),
        "util.bus_v": 28 + g.normal(size=(L, 4)),  # M09 publishes 4 buses (E1-MF U1)
    }
    _, _, _, _, S, X = run(cfg, rows(cfg, L, vals))
    np.testing.assert_array_equal(S, X)
    np.testing.assert_array_equal(S[:, cfg.channel_index("ENG.CVG")], vals["eng.vg_vsv"])


def test_meter_update_hold_staircase(d, m12):
    """Meter update interval (angular-momentum meters update every 300 ms, A-W1.6-8 sweep end): the reading
    is constant between updates and changes only when floor(t / 0.3 s) advances (n = 720 frames = 3 s)."""
    params = dict(m12)
    params["fuel_flowmeter_main"] = m12["fuel_flowmeter_main"].replace(update_interval=0.3)
    cfg = cfg_for(d, "ENG.WFM", params=params)
    L = 720
    t_end = ((np.arange(L, dtype=np.int64) + 1) * 10**9) // 240
    S = run(cfg, rows(cfg, L, {"eng.wf": 0.5 + 0.1 * np.sin(np.arange(L) * DT)}))[4][:, 0]
    upd = t_end // 300_000_000
    changes = np.flatnonzero(np.diff(S) != 0) + 1
    assert set(changes) <= set(np.flatnonzero(np.diff(upd) != 0) + 1)
    assert len(changes) >= 9


def test_compiled_equals_reference_bitwise_and_block_equals_steps(d):
    """A8: the compiled kernel equals its NumPy reference (py_func) bitwise, and one block of L frames equals
    L blocks of one frame, for every Tejas channel (n = 240 frames)."""
    cfg = build_sensor_config(d)
    L = 240
    g = np.random.Generator(np.random.Philox(np.random.SeedSequence(16, spawn_key=(2,))))
    U = rows(cfg, L, {s.signal: 1.0 + 0.05 * g.normal(size=(L, s.size)) for s in cfg.inputs})
    U[:, cfg.cols[K.COL_PS]] = 5e4 + 100 * g.normal(size=L)
    U[:, cfg.cols[K.COL_TS]] = 250.0
    U[:, cfg.cols[K.COL_TAS]] = 200.0
    U[:, cfg.cols[K.COL_MACH]] = 0.7 + 0.01 * g.normal(size=L)
    a = run(cfg, U)
    b = run(cfg, U, kernel=K.m12_kernel.py_func)
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)
    st = init_state(cfg)
    Ss = []
    for j in range(L):
        *st, S1, _ = run(cfg, U[j : j + 1], state=tuple(st), k0=j)
        Ss.append(S1[0])
    np.testing.assert_array_equal(np.array(Ss), a[4])


@pytest.mark.parametrize(
    ("channel", "pset", "pname", "col"),
    [
        ("ENG.OIL_P", "oil_pressure", "tau", K.PE_TAU),
        ("ENG.T5.HARNESS_A", "tc_t5", "tau", K.PE_TAU),
        ("AD.AOA_VANE_L.A", "vane_aoa", "zeta", K.PE_ZETA),
        ("AD.AOA_VANE_L.A", "vane_aoa", "kf", K.PE_KF),
        ("AD.PS.A", "static_pressure", "lambda_sl", K.PE_TAU),
    ],
)
def test_complex_step_matches_central_difference(d, channel, pset, pname, col):
    """A8 / AD-34: d(reading)/d(dynamic parameter) by complex step (h = 1e-30) through the same kernel
    equals the central finite difference within 1e-6 relative (n = 120 frames of a sinusoidal truth)."""
    cfg = cfg_for(d, channel)
    L = 120
    t = np.arange(L) * DT
    vals = {
        "eng.oil_p": 3e5 + 2e4 * np.sin(6 * t),
        "eng.t5": 900 + 30 * np.sin(4 * t),
        "eng.w2": 40.0,
        "af.alpha": 0.05 + 0.01 * np.sin(20 * t),
        "af.tas": 100.0,
        "env.rho": 1.0,
        "af.mach": 0.3,
        "af.nz": 1.0,
        "env.p_s": 5e4 + 500 * np.sin(5 * t),
        "env.t_s": 250.0,
    }
    U = rows(cfg, L, vals)
    p0 = float(cfg.el_p[0, col])
    pc = cfg.el_p.astype(np.complex128)
    pc[:, col] += 1e-30j
    S_c = run(cfg, U, el_p=pc)[4]
    d_cs = S_c.imag / 1e-30
    h = 1e-6 * abs(p0)
    pp, pm = cfg.el_p.copy(), cfg.el_p.copy()
    pp[:, col] += h
    pm[:, col] -= h
    d_fd = (run(cfg, U, el_p=pp)[4] - run(cfg, U, el_p=pm)[4]) / (2 * h)
    assert np.max(np.abs(d_cs)) > 0
    np.testing.assert_allclose(d_cs, d_fd, rtol=1e-5, atol=1e-6 * np.max(np.abs(d_fd)))


@pytest.mark.parametrize(("tau_ref", "w_frac"), [(0.81, 1.0), (1.75, 1.0), (1.75, 0.5)])
def test_thermocouple_lag_delays_the_measured_egt(d, m12, tau_ref, w_frac):
    """The thermocouple stage shapes the measured lead-lag (behavioural targets: FF->EGT +0.75 s is partly TC
    lag): for a 0.1 Hz T5 oscillation the harness reading lags the gas by arctan(w tau)/w (first-order phase
    lag), with tau = tau_ref (W/W_ref)^-0.5. tau_ref 0.81 s is the round-2 proxy fit ([MEASURED], tests only);
    1.75 s the Tejas assumption (A-W1.6-4). Phase by projection on sin/cos over n = 14,400 frames (exactly 6
    cycles) after a 20 s settle; tolerance 2 ms."""
    p = dict(m12)
    p["tc_t5"] = m12["tc_t5"].replace(tau=tau_ref)
    cfg = cfg_for(d, "ENG.T5.HARNESS_A", params=p)
    L = 19200
    t = (np.arange(L) + 1) * DT
    f = 0.1
    t5 = 900.0 + 20.0 * np.sin(2 * np.pi * f * t)
    w_ref = float(m12["tc_t5"].value("w_ref"))
    S = run(cfg, rows(cfg, L, {"eng.t5": t5, "eng.w2": w_frac * w_ref}))[4][:, 0]
    w = 2 * np.pi * f
    tt, b = t[4800:], S[4800:] - 900.0
    lag_s = np.arctan2(-np.dot(b, np.cos(w * tt)), np.dot(b, np.sin(w * tt))) / w
    tau = tau_ref * w_frac**-0.5
    assert lag_s == pytest.approx(np.arctan(w * tau) / w, abs=0.002)
