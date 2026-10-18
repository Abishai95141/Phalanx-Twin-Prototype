"""W2.2 M12 avionics: INS/GPS error model (AD-51; A-W2.2-2, A-W2.2-3, A-W2.2-4).

The INS output is truth seen through a structured error state, so these tests check the structure's
consequences against analytic predictions of the same model and against the navigation-grade class evidence
(A-W2.2-2: 0.01 deg/h, 1 nm/h unaided, 30 m aided; TRANSFER), never against tuned outputs:

- aided steady state: position error = the GPS Gauss-Markov error through the ``aid_pos_tau`` loop
  (sigma_h sqrt(tau_g / (tau_g + tau_a))), velocity likewise with the Doppler error, tilt = accelerometer
  bias / g, heading = east gyro bias / (Omega cos lat);
- unaided: Schuler-bounded horizontal drift inside the 1 nm/h class, vertical held by the baro loop;
- heading observable only under horizontal specific force (turns), which also excite velocity errors;
- errors are correlated states (no white noise on the navigation outputs);
- output filters with the TM-110216 bandwidths; FOM from the INS's own error estimate.

Sample sizes are stated per test (sorties = identity-keyed seeds; fixed list, deterministic).
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.bus.clocks import key_value
from phalanx.core.rng import KeyPath
from phalanx.sensors.avionics import ins as N
from phalanx.sensors.avionics.config import build_avionics_config


def _fixture():
    name = "w22_avionics_fixture"
    if name not in sys.modules:
        p = Path(__file__).resolve().parents[1] / "integration" / "test_w22_avionics_fixture.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


FX = _fixture()
CFG = build_avionics_config()
P = CFG.ins_p
G = float(P[N.P_G0])
LAT = math.radians(13.0)
RR = FX.R_EARTH + 3000.0


def _ident(k: int) -> KeyPath:
    return KeyPath.of(scenario="W22", tail="KH2001", sortie=f"SRT{k:04d}")


def kernel_run(ident: KeyPath, truth16: np.ndarray, dt: float, *, unaided: bool = False, h_baro=None):
    """Run the INS kernel alone on (L, 16) truth with the module's keyed draws for ``ident``."""
    m = FX.make_module(identity=ident, config=CFG)
    L = truth16.shape[0]
    zt = m.stream("ins_tick", sensor="INGPS").draws(0, L * N.N_TICK_DRAWS).reshape(L, N.N_TICK_DRAWS)
    serial = key_value(f"{ident.get('tail')}:INGPS")
    zon = m.stream("ins_on", serial=serial).draws(0, 2 * N.N_ON_DRAWS).reshape(2, N.N_ON_DRAWS)
    hb = truth16[:, 2] if h_baro is None else h_baro
    truth = np.ascontiguousarray(np.concatenate([truth16, hb[:, None]], axis=1))
    f, i = N.ins_initial_state()
    if unaided:
        i[N.I_FIX] = N.FIX_NONE
        i[N.I_HFIX] = N.FIX_NONE
    return N.ins_kernel(
        f, i, P, CFG.fom_bounds, truth, np.full(L, 28.0), np.ones(L, np.int64), zt, zon, dt, 8
    )


def straight_truth(L: int, dt: float) -> np.ndarray:
    """(L, 16) straight, level, wings-level flight north at 200 m/s, 3,000 m (columns of ins_kernel)."""
    t = np.arange(1, L + 1) * dt
    tr = np.zeros((L, 16))
    tr[:, 0] = LAT + 200.0 * t / RR
    tr[:, 1] = math.radians(77.6)
    tr[:, 2] = 3000.0
    tr[:, 3] = 200.0
    tr[:, 6] = 1.0
    tr[:, 15] = -G
    return tr


@pytest.mark.statistical
def test_aided_errors_match_the_loop_predictions():
    """n = 48 sorties x 30 s at 240 Hz (96 horizontal axis samples; RMS relative SE 1/sqrt(2n) = 7 %, 10 % for
    heading with 48): end-of-run errors against the analytic steady state of the same loops, tolerance 30 %
    (>= 3 SE). The aided CEP (1.1774 sigma) is inside the 30 m navigation-grade class (TRANSFER)."""
    L, dt = 240 * 30, 1.0 / 240.0
    tr = straight_truth(L, dt)
    pos, vel, tilt, hdg = [], [], [], []
    for k in range(48):
        _, _, out, st, tru = kernel_run(_ident(k), tr, dt)
        assert st[-1, 0] == N.MODE_HYBRID and st[-1, 1] == N.FIX_3D
        pos += [(out[-1, 0] - tru[-1, 0]) * RR, (out[-1, 1] - tru[-1, 1]) * RR * math.cos(tru[-1, 0])]
        vel += [out[-1, 3] - tru[-1, 3], out[-1, 4] - tru[-1, 4]]
        tilt += [out[-1, 7] - tru[-1, 7], out[-1, 8] - tru[-1, 8]]
        hdg.append((out[-1, 6] - tru[-1, 6] + math.pi) % (2 * math.pi) - math.pi)
    rms = {
        k: float(np.sqrt(np.mean(np.square(v))))
        for k, v in (("pos", pos), ("vel", vel), ("tilt", tilt), ("hdg", hdg))
    }
    pred = {
        "pos": P[N.P_GPS_SIG_H] * math.sqrt(P[N.P_GPS_TAU] / (P[N.P_GPS_TAU] + P[N.P_AID_POS_TAU])),
        "vel": P[N.P_GPS_VSIG] * math.sqrt(P[N.P_GPS_VTAU] / (P[N.P_GPS_VTAU] + P[N.P_AID_VEL_TAU])),
        "tilt": P[N.P_BA_SIG] / G,
        "hdg": P[N.P_BG_SIG] / (P[N.P_OMEGA] * math.cos(LAT)),
    }
    for k in pred:
        assert rms[k] == pytest.approx(pred[k], rel=0.30), (k, rms[k], pred[k])
    assert 1.1774 * rms["pos"] <= 30.0 * 1.3  # aided CEP in the 30 m class


@pytest.mark.statistical
def test_free_inertial_drift_is_navigation_grade_and_the_vertical_is_baro_held():
    """n = 16 sorties x 1 h unaided (GPS fix absent), error dynamics at dt = 0.05 s (every error time constant
    >= 1 s; ARW and accelerometer noise scale with 1/sqrt(dt)). The median radial drift after 1 h is inside
    the 1 nm/h navigation-grade class (DRDO RINS, TRANSFER) and not zero (analytic R eps (t - sin(w_s t)/w_s)
    = 0.4 nmi for the 0.005 deg/h bias); the vertical channel follows the baro reference (no free-inertial
    divergence) and the FOM is the bin of its own estimate (30 m + 1 nm/h x 1 h)."""
    dt = 0.05
    L = int(3600 / dt)
    tr = straight_truth(L, dt)
    radial, vert, fom = [], [], []
    for k in range(16):
        _, _, out, st, tru = kernel_run(_ident(k), tr, dt, unaided=True)
        assert st[-1, 0] == N.MODE_INERTIAL and st[-1, 1] == N.FIX_NONE
        e0 = np.array([(out[0, 0] - tru[0, 0]) * RR, (out[0, 1] - tru[0, 1]) * RR * math.cos(tru[0, 0])])
        e1 = np.array([(out[-1, 0] - tru[-1, 0]) * RR, (out[-1, 1] - tru[-1, 1]) * RR * math.cos(tru[-1, 0])])
        radial.append(float(np.hypot(*(e1 - e0))))
        vert.append(float(np.max(np.abs(out[:, 2] - tru[:, 2]))))
        fom.append(int(st[-1, 2]))
    med_nmi = float(np.median(radial)) / 1852.0
    assert 0.1 <= med_nmi <= 1.0, med_nmi
    assert max(vert) < 3.0 * P[N.P_GPS_SIG_V]  # initial GPS vertical error decaying, no divergence
    sig_1h = P[N.P_GPS_SIG_H] * 1.1774 + P[N.P_CEP_RATE] * 3600.0
    assert fom == [1 + int(np.sum(sig_1h > CFG.fom_bounds))] * 16


@pytest.mark.unit
def test_vertical_follows_the_non_standard_atmosphere_when_unaided():
    """n = 1 sortie x 600 s unaided with the baro reference 150 m high (a cold day): the INS altitude
    converges to the baro altitude (error -> h_baro - h) with the loop time constant; aided it stays on
    GPS."""
    dt = 0.05
    L = int(600 / dt)
    tr = straight_truth(L, dt)
    _, _, out, _, tru = kernel_run(_ident(0), tr, dt, unaided=True, h_baro=tr[:, 2] + 150.0)
    assert out[-1, 2] - tru[-1, 2] == pytest.approx(150.0, abs=5.0)
    _, _, out, _, tru = kernel_run(_ident(0), tr, dt, h_baro=tr[:, 2] + 150.0)
    assert abs(out[-1, 2] - tru[-1, 2]) < 4.0 * P[N.P_GPS_SIG_V]


@pytest.mark.unit
def test_heading_is_corrected_only_under_horizontal_specific_force():
    """CRN fork (n = 1 sortie): from a common state at t = 10 s, branch A flies straight and branch B turns at
    60 deg bank for 60 s. With identical exogenous draws, B's heading error decays at
    (|f_h|/g)^2 / heading_tau while A's stays (gyro drift only); B's turn also couples the heading error
    into velocity (-psi x f)."""
    n0, n1 = 240 * 10, 240 * 64
    a_truth = FX.default_truth(n0 + n1)
    b_truth = FX.default_truth(n0 + n1, bank_deg={(11.0, 73.0): 60.0})
    m = FX.make_module()
    s0, _ = FX.run_direct(m, a_truth, n0)
    psi0 = float(s0["ins_f"][N.F_PSI + 2])
    assert abs(psi0) > 1e-4  # precondition: this sortie's gyrocompassing error is not tiny
    sa, oa = FX.run_direct(m, a_truth, n1, state=s0, k0=n0)
    sb, ob = FX.run_direct(m, b_truth, n1, state=s0, k0=n0)
    for k in (N.F_BG0, N.F_BGM, N.F_BA0, N.F_BAM, N.F_EGPS, N.F_EVGPS):  # common random numbers
        assert np.array_equal(sa["ins_f"][k : k + 3], sb["ins_f"][k : k + 3])
    psi_a, psi_b = float(sa["ins_f"][N.F_PSI + 2]), float(sb["ins_f"][N.F_PSI + 2])
    assert abs(psi_a - psi0) < 0.05 * abs(psi0)
    # 58 s at fh^2 = tan^2(60) = 3 (plus ramps): exp(-3 * 58 / 120) = 0.23
    assert abs(psi_b) < 0.4 * abs(psi0)
    # velocity: with common draws the branch difference isolates the -psi x f coupling. Bounds: <= the steady
    # response psi0 f_h tau_v of an undecayed, non-rotating forcing; >= 0.3 of it (the forcing rotates with
    # the turn at 0.085 rad/s and psi decays at 1/40 s: analytic peak ~0.5)
    dvn = (ob["rec_nav_ins_vn"] - ob["tru_nav_ins_vn"]) - (oa["rec_nav_ins_vn"] - oa["tru_nav_ins_vn"])
    dve = (ob["rec_nav_ins_ve"] - ob["tru_nav_ins_ve"]) - (oa["rec_nav_ins_ve"] - oa["tru_nav_ins_ve"])
    ddv = np.hypot(dvn, dve)
    assert np.all(ddv[:240] == 0.0)  # identical until the bank starts
    scale = abs(psi0) * G * math.tan(math.radians(60.0)) * P[N.P_AID_VEL_TAU]
    assert 0.3 * scale <= ddv.max() <= scale, (ddv.max(), scale)


@pytest.mark.unit
def test_navigation_errors_are_correlated_states_not_white_noise():
    """n = 1 sortie x 30 s aided: the position and attitude errors are smooth states (lag-1 autocorrelation of
    their 240 Hz series > 0.99, frame-to-frame change < 0.1 of their spread), unlike ideal + white noise."""
    n = 240 * 30
    _, o = FX.run_direct(FX.make_module(), FX.default_truth(n), n)
    for rec, tru, scale in (
        ("rec_nav_ins_lat", "tru_nav_ins_lat", RR),
        ("rec_nav_ins_roll", "tru_nav_ins_roll", 1.0),
        ("rec_nav_ins_vn", "tru_nav_ins_vn", 1.0),
    ):
        e = (o[rec] - o[tru]) * scale
        e = e - e.mean()
        r1 = float(np.dot(e[1:], e[:-1]) / np.dot(e, e))
        assert r1 > 0.99, (rec, r1)  # white noise: |r1| < 3 / sqrt(n) = 0.035
        assert np.std(np.diff(e)) < 0.1 * np.std(e), rec  # white noise: sqrt(2)


@pytest.mark.unit
def test_rate_and_acceleration_outputs_follow_the_tm110216_filters():
    """n = 1 sortie x 10 s (one 30 deg bank entry at zero angle of attack, so the body yaw rate g sin(mu) / V
    ramps without the sin(alpha) mu' step): a second-order low-pass lags a ramp by 2 zeta / wn, so the
    narrow-band rate lags the wide-band rate by 2 zeta (1/wn_nb - 1/wn_wb) = 80 ms (5 %); ACCEL is the body
    specific force (Z = -g / cos(mu), Y = 0 in the coordinated turn)."""
    n = 240 * 10
    truth = FX.default_truth(n, alpha0=0.0, bank_deg={(2.0, 20.0): 30.0})  # alpha 0: r = g sin(mu) / V
    _, o = FX.run_direct(FX.make_module(), truth, n)
    t = FX.frame_times(n)
    nb, wb = o["rec_nav_ins_body_rates_r_nb"], o["rec_nav_ins_body_rates_r_wb"]
    level = 0.5 * wb[240 * 3]  # mid-ramp of the yaw rate (the bank ramps over 2-4 s)

    def crossing(x):
        k = int(np.argmax(x >= level))
        return t[k - 1] + (level - x[k - 1]) / (x[k] - x[k - 1]) * (t[k] - t[k - 1])

    lag = crossing(nb) - crossing(wb)
    pred = 2.0 * (P[N.P_NB_ZETA] / P[N.P_NB_WN] - P[N.P_WB_ZETA] / P[N.P_WB_WN])
    assert lag == pytest.approx(pred, rel=0.05)
    k = 240 * 8
    assert o["rec_nav_ins_accel_z"][k] == pytest.approx(-G / math.cos(math.radians(30.0)), abs=0.01)
    assert o["rec_nav_ins_accel_y"][k] == pytest.approx(0.0, abs=0.01)  # coordinated: no side force


@pytest.mark.unit
def test_figure_of_merit_grows_with_the_unaided_error_estimate():
    """n = 1 sortie x 400 s unaided: FOM = bin of (1.1774 sigma_GPS + cep_rate x t_unaided); aided it is the
    bin of the GPS term alone (A-W2.2-4)."""
    dt = 0.05
    L = int(400 / dt)
    tr = straight_truth(L, dt)
    _, _, _, st, _ = kernel_run(_ident(0), tr, dt, unaided=True)
    t = np.arange(1, L + 1) * dt
    sig = P[N.P_GPS_SIG_H] * 1.1774 + P[N.P_CEP_RATE] * t
    expected = 1 + np.sum(sig[:, None] > CFG.fom_bounds[None, :], axis=1)
    assert np.array_equal(st[:, 2], expected)
    assert st[0, 2] == 2 and st[-1, 2] == 6
    _, _, _, st, _ = kernel_run(_ident(0), tr[:2400], dt)
    assert np.all(st[:, 2] == 2)
