"""M12 sensor physics per class (acceptance A1: class behaviours for air data, fuel and engine sensors).

Data-free: constructed steady truth, checked against the closed-form physics each class implements (ISA,
pitot, recovery factor, AGARD pneumatic scaling) and the documented failure semantics (T5 harness). n per test
is a few hundred frames (enough for the slowest element to settle where settling matters).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import truth_step_times_ns
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_param_set, load_params
from phalanx.sensors import kernel as K
from phalanx.sensors.config import build_sensor_config, unit_group
from phalanx.sensors.module import BIAS_PORT, FAULT_STREAM, SENSOR_FAULT_EVENT, SensorPhysics

pytestmark = pytest.mark.unit
DT = 1.0 / 240.0
G0 = 9.80665


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


@pytest.fixture(scope="module")
def m12():
    return load_params("M12")


def make(d, *channels, params=None):
    cfg = build_sensor_config(d, channels=channels, params=params)
    m = SensorPhysics("sens", load_param_set("M12", "constants"), cfg)
    keys = RngService(0x16, StreamRegistry([FAULT_STREAM])).scope(
        KeyPath.of(scenario="T", tail="T1", sortie="S1")
    )
    m.bind(keys)
    return m


def inputs(m, L, values, bias=None):
    out = {}
    for s in m.config.inputs:
        v = np.asarray(values.get(s.signal, 0.0), dtype=np.float64)
        out[s.port] = np.broadcast_to(
            v.reshape((L, *s.shape)) if v.size == L * s.size else v, (L, *s.shape)
        ).copy()
    out[BIAS_PORT] = np.zeros((L, m.config.n_ch)) if bias is None else bias
    return out


def run(m, values, L, state=None, k0=0, bias=None):
    st = m.init(m.params, m.keys) if state is None else state
    t = truth_step_times_ns(np.arange(k0, k0 + L, dtype=np.int64))
    return m.step_block(st, inputs(m, L, values, bias), t, DT)


def chan(m, out, cid, kind="s"):
    c = m.config.channel_index(cid)
    g = unit_group(m.config.si_units[c])
    return out[f"{kind}_{g}"][..., m.config.groups[g].index(c)]


AIR = {"env.p_s": 50000.0, "env.t_s": 250.0, "af.mach": 0.8, "env.rho": 0.7, "af.tas": 250.0, "af.nz": 1.0}


def test_t5_harness_open_and_short_probe(d):
    """F404 harness semantics (CR-191195, CR-1998-208416): a shorted probe reads low and pulls the harness
    average down; an open probe drops out of the average. Harness B is unaffected (n = 2 x 2,400 frames)."""
    m = make(d, "ENG.T5.HARNESS_A", "ENG.T5.HARNESS_B")
    vals = {"eng.t5": 900.0, "eng.w2": 50.0}
    st, out = run(m, vals, 2400)
    assert chan(m, out, "ENG.T5.HARNESS_A")[-1] == pytest.approx(900.0)
    ev = Event(
        0,
        SENSOR_FAULT_EVENT,
        "sens",
        {"channel": "ENG.T5.HARNESS_A", "mode": "probe_short", "probe": 0, "value": 600.0},
    )
    st, _ = m.on_event(st, ev, 0)
    st, out = run(m, vals, 2400, st, 2400)
    assert chan(m, out, "ENG.T5.HARNESS_A")[-1] == pytest.approx((3 * 900.0 + 600.0) / 4)
    assert chan(m, out, "ENG.T5.HARNESS_B")[-1] == pytest.approx(900.0)
    ev = Event(
        0, SENSOR_FAULT_EVENT, "sens", {"channel": "ENG.T5.HARNESS_A", "mode": "probe_open", "probe": 0}
    )
    st, _ = m.on_event(st, ev, 0)
    st, out = run(m, vals, 10, st, 4800)
    assert chan(m, out, "ENG.T5.HARNESS_A")[-1] == pytest.approx(900.0)  # 3 good probes remain
    # the harness truth label is the gas T5 regardless of probe faults (hidden fault state)
    assert chan(m, out, "ENG.T5.HARNESS_A", "x")[-1] == 900.0


def test_tat_recovery_and_heater_error(d, m12):
    """TAT: T_r = T_s (1 + 0.2 r(M) M^2) + DHE(Z) with the heater on (NCAR Rosemount 102, TRANSFER);
    heater off removes DHE. The truth label is the total temperature with r = 1 (n = 4,800 frames)."""
    m = make(d, "AD.TAT")
    _, out = run(m, {**AIR, "util.probe_heat": 1.0}, 4800)  # heater state from util.probe_heat (W2.2)
    ps = m12["tat_probe"]
    rx, ry = np.asarray(ps.value("rec_mach")), np.asarray(ps.value("recovery"))
    zx, zy = np.asarray(ps.value("dhe_z")), np.asarray(ps.value("dhe"))
    r = np.interp(0.8, rx, ry)
    z = 0.8 * 0.7 / 1.225
    expect = 250.0 * (1 + 0.2 * r * 0.64) + np.interp(z, zx, zy)
    assert chan(m, out, "AD.TAT")[-1] == pytest.approx(expect, abs=1e-9)
    assert chan(m, out, "AD.TAT", "x")[-1] == pytest.approx(250.0 * 1.128)
    m_off = make(d, "AD.TAT")
    _, out_off = run(m_off, {**AIR, "util.probe_heat": 0.0}, 4800)
    assert chan(m_off, out_off, "AD.TAT")[-1] == pytest.approx(250.0 * (1 + 0.2 * r * 0.64), abs=1e-9)


def _step_tau(m, cid, base, key, lo, hi, L):
    """Time constant from the 63.2 % crossing of the response to a step of ``key`` (a ramp over frame 1):
    for a first-order lag the crossing is tau + DT/2 after the ramp starts; y[i] is at (i + 1) DT after it."""
    v = np.full(L, lo)
    v[1:] = hi
    _, out = run(m, {**base, key: v}, L)
    y = chan(m, out, cid)[1:]
    f = (y - lo) / (hi - lo)
    j = int(np.argmax(f >= 1 - np.exp(-1)))
    return (j + (1 - np.exp(-1) - f[j - 1]) / (f[j] - f[j - 1])) * DT - 0.5 * DT


def test_pneumatic_lag_scales_with_altitude(d, m12):
    """Pitot line lag lambda = lambda_SL (mu/mu_SL)/delta (AGARD-AG-300): the measured lag at the ISA 40 kft
    point is 4.29x the sea-level lag (report: 'x4.3 at 40 kft'). n = 480 frames per run."""
    m = make(d, "AD.PT.A")
    sl = {"env.t_s": 288.15, "env.p_s": 101325.0, "af.mach": 0.0}
    hi = {"env.t_s": 216.65, "env.p_s": 18753.6, "af.mach": 0.0}
    tau_sl = _step_tau(m, "AD.PT.A", sl, "env.p_s", 101325.0, 101525.0, 480)
    tau_hi = _step_tau(m, "AD.PT.A", hi, "env.p_s", 18753.6, 18853.6, 960)
    assert tau_sl == pytest.approx(float(m12["total_pressure"].value("lambda_sl")), rel=0.01)
    assert tau_hi / tau_sl == pytest.approx(4.29, rel=0.01)


def test_position_error_is_mach_only_proxy(d, m12):
    """PROXY A-W1.6-12 exposed: the static-port reading is p_s + k(M) q_c with k from the side-probe table;
    it does not respond to alpha, beta or anything else (no gear, sideslip or fluctuation terms)."""
    m = make(d, "AD.PS.A")
    ps = m12["static_pressure"]
    k = np.interp(0.8, np.asarray(ps.value("pe_mach")), np.asarray(ps.value("pe_k")))
    qc = 50000.0 * ((1 + 0.2 * 0.64) ** 3.5 - 1)
    _, out = run(m, AIR, 240)
    assert chan(m, out, "AD.PS.A")[-1] == pytest.approx(50000.0 + k * qc, rel=1e-12)
    assert k < 0  # side vents read low (Gracey RP-1046; HAL ADC SSEC)
    _, out2 = run(m, {**AIR, "af.alpha": 0.3, "af.beta": 0.1}, 240)
    assert chan(m, out2, "AD.PS.A")[-1] == chan(m, out, "AD.PS.A")[-1]


def test_transonic_jump_in_position_error(d, m12):
    """The side-probe table has its transonic dip just below M1 and collapses past the shock (|dk| > 0.02)."""
    ps = m12["static_pressure"]
    mx, kx = np.asarray(ps.value("pe_mach")), np.asarray(ps.value("pe_k"))
    assert np.interp(0.97, mx, kx) - np.interp(1.05, mx, kx) < -0.05
    assert np.all(np.abs(kx) <= 0.1)  # Tejas design bound |Cp| <= 0.1 (DSJ 52(1), DIRECT)


def test_vane_local_angle_and_shared_element(d, m12):
    """The four LVDT pick-offs of one vane share its dynamics; alpha_local = (1 + ku) alpha + b(M) at steady
    state; the sideslip vane reads (1 + ku_beta) beta; truth labels are the free-stream angles."""
    lanes = [f"AD.AOA_VANE_L.{x}" for x in "ABCD"]
    m = make(d, *lanes, "AD.AOSS_VANE.A")
    assert m.config.n_el == 2
    vals = {**AIR, "af.alpha": 0.08, "af.beta": 0.02}
    _, out = run(m, vals, 720)
    pa, pb = m12["vane_aoa"], m12["vane_aoss"]
    b = np.interp(0.8, np.asarray(pa.value("bias_mach")), np.asarray(pa.value("bias")))
    expect = (1 + float(pa.value("ku"))) * 0.08 + b
    for cid in lanes:
        assert chan(m, out, cid)[-1] == pytest.approx(expect, rel=1e-9)
        assert chan(m, out, cid, "x")[-1] == 0.08
    assert chan(m, out, "AD.AOSS_VANE.A")[-1] == pytest.approx((1 + float(pb.value("ku"))) * 0.02, rel=1e-9)


def test_fuel_gauge_unwets_under_tilt_proxy(d, m12):
    """PROXY A-W1.6-17 exposed: level flight reads the mass; with the specific force tilted 60 deg (zoom climb
    at high thrust) a low tank unwets and reads low (the Tejas false low-fuel mechanism); below 2 % it reads
    empty. No tank geometry: the reading depends only on fill, tilt and the coefficients. n = 4 x 4,800."""
    m = make(d, "FUEL.QTY.TANK.F1")
    cap = float(m12["fuel_tanks"].value("cap_internal"))
    level = {"af.f_spec_body": np.array([0.0, 0.0, -G0])}
    tilt = {"af.f_spec_body": np.array([G0 * np.sin(np.pi / 3), 0.0, -G0 * np.cos(np.pi / 3)])}
    _, o1 = run(m, {**level, "util.fuel_mass": 300.0}, 4800)
    assert chan(m, o1, "FUEL.QTY.TANK.F1")[-1] == pytest.approx(300.0, rel=1e-6)
    _, o2 = run(m, {**tilt, "util.fuel_mass": 0.2 * cap}, 4800)
    gauge = m12["fuel_gauge"]
    st_ = np.sin(np.pi / 3)
    f_unwet = float(gauge.value("unwet")) * st_
    base = 0.2 * cap + float(gauge.value("att")) * cap * st_
    assert chan(m, o2, "FUEL.QTY.TANK.F1")[-1] == pytest.approx(base * 0.2 / f_unwet, rel=1e-6)
    assert chan(m, o2, "FUEL.QTY.TANK.F1")[-1] < 0.5 * 0.2 * cap
    _, o3 = run(m, {**level, "util.fuel_mass": 0.01 * cap}, 4800)
    assert chan(m, o3, "FUEL.QTY.TANK.F1")[-1] == pytest.approx(0.0, abs=1e-6)


def test_inertial_sensor_axes(d):
    """Installed axes: NZ reads -f_z (+1 g in level flight), NY reads f_y; rate gyros read their body rate."""
    m = make(d, "FCS.ASA.NZ.A", "FCS.ASA.NY.A", "FCS.RSA.P.A", "FCS.RSA.R.A")
    vals = {"af.f_spec_body": np.array([0.5, 1.5, -G0]), "af.omega_body": np.array([0.3, -0.2, 0.1])}
    _, out = run(m, vals, 240)
    assert chan(m, out, "FCS.ASA.NZ.A")[-1] == pytest.approx(G0, rel=1e-9)
    assert chan(m, out, "FCS.ASA.NY.A")[-1] == pytest.approx(1.5, rel=1e-9)
    assert chan(m, out, "FCS.RSA.P.A")[-1] == pytest.approx(0.3, rel=1e-9)
    assert chan(m, out, "FCS.RSA.R.A")[-1] == pytest.approx(0.1, rel=1e-9)


def test_installation_bias_is_added_to_its_channel_only(d):
    """health.sensor_bias (AD-07) enters s_inst of its own channel (index map = config channel order) and
    never the truth label; other channels are bit-identical."""
    m = make(d, "ENG.N2.A", "ENG.N2.B", "ENG.PS3.A")
    vals = {"eng.n2": 1700.0, "eng.ps3": 2e6}
    _, out0 = run(m, vals, 24)
    b = np.zeros((24, m.config.n_ch))
    b[:, m.config.channel_index("ENG.N2.B")] = 1.5
    _, out1 = run(m, vals, 24, bias=b)
    assert chan(m, out1, "ENG.N2.B")[-1] == chan(m, out0, "ENG.N2.B")[-1] + 1.5
    assert chan(m, out1, "ENG.N2.A")[-1] == chan(m, out0, "ENG.N2.A")[-1]
    assert chan(m, out1, "ENG.PS3.A")[-1] == chan(m, out0, "ENG.PS3.A")[-1]
    np.testing.assert_array_equal(chan(m, out1, "ENG.N2.B", "x"), chan(m, out0, "ENG.N2.B", "x"))
    assert m.config.bias_index() == m.config.channels


def test_kernel_constants_come_from_parameters(d, m12):
    """No hidden physics constants: the kernel's constant vector is exactly the M12 'constants' set."""
    cfg = build_sensor_config(d, channels=("AD.PS.A",))
    c = m12["constants"]
    assert cfg.k[K.K_P_SL] == c.value("p_sl") and cfg.k[K.K_GAMMA] == c.value("gamma")
    assert cfg.n_sub == c.value("n_sub")
