"""W2.2 M12 avionics: standby AHRS (AD-51; A-W2.2-5).

Structure under test (MEMS strapdown attitude with gravity erection and magnetic slaving): the levelled tilt
settles at the accelerometer-bias / gyro-bias equilibrium of the erection loop; a sustained turn below the
cut-out thresholds drags the vertical toward the false (centripetal) vertical (the classic AHRS turn error),
above them the erection is cut out and only gyro drift accumulates; the heading settles at the magnetic
sensor's deviation plus the slaving loop's gyro-bias offset; the output is magnetic (true - declination).
Predictions are the analytic steady states of the same loops computed from the unit's own drawn biases.
Sample sizes: one sortie (identity-keyed draws) per test, 2-11 min at 240 Hz; deterministic.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.bus.clocks import key_value
from phalanx.dictionary.params import load_params
from phalanx.sensors.avionics import ahrs as H
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
P = CFG.ahrs_p
G = float(P[H.P_G0])
DT = FX.DT


class Unit:
    """The AHRS kernel driven alone with the module's keyed draws (one sortie, one unit)."""

    def __init__(self, cfg=CFG):
        self.cfg = cfg
        self.m = FX.make_module(config=cfg)
        serial = key_value(f"{FX.IDENTITY.get('tail')}:AHRS")
        self.zon = self.m.stream("ahrs_on", serial=serial).draws(0, 2 * H.N_ON_DRAWS).reshape(2, H.N_ON_DRAWS)
        self.f, self.i = H.ahrs_initial_state()

    def run(self, fl: dict, k0: int, n: int, state=None):
        """Frames [k0, k0 + n) of a ``FX.flight`` script; returns (state, out, tru)."""
        f, i = state if state is not None else (self.f, self.i)
        tr = np.ascontiguousarray(
            np.concatenate(
                [
                    fl["af.quat"][k0 : k0 + n],
                    fl["af.omega_body"][k0 : k0 + n],
                    fl["af.f_spec_body"][k0 : k0 + n],
                ],
                axis=1,
            )
        )
        tick = int(i[H.I_TICK])
        zt = self.m.stream("ahrs_tick", sensor="AHRS").draws(tick * H.N_TICK_DRAWS, n * H.N_TICK_DRAWS)
        f, i, out, _pw, tru = H.ahrs_kernel(
            f, i, self.cfg.ahrs_p, tr, np.full(n, 28.0), zt.reshape(n, H.N_TICK_DRAWS), self.zon, DT
        )
        return (f, i), out, tru


def wrap(a):
    return (np.asarray(a) + math.pi) % (2.0 * math.pi) - math.pi


def tilt_equilibrium(f) -> tuple[float, float]:
    """(roll, pitch) error of the erection loop's steady state, heading north, wings level, alpha 0:
    psi_N = b_ay / g - tau eps_N, psi_E = -b_ax / g - tau eps_E (eps = turn-on + in-run gyro bias), and the
    computed attitude (I - [psi x]) C has roll error -psi_N and pitch error -psi_E (a +y accelerometer bias
    reads as a left roll: f_y = -g sin(roll))."""
    tau = P[H.P_ERECT_TAU]
    ba = f[H.F_BA0 : H.F_BA0 + 3]
    eps = f[H.F_BG0 : H.F_BG0 + 3] + f[H.F_BGM : H.F_BGM + 3]
    psi_n = ba[1] / G - tau * eps[0]
    psi_e = -ba[0] / G - tau * eps[1]
    return float(-psi_n), float(-psi_e)


@pytest.mark.unit
def test_erection_levels_to_the_bias_equilibrium():
    """n = 1 unit x 300 s straight (5 erection time constants, alpha = 0 so body = NED axes): the roll and
    pitch errors equal the loop's steady state from the unit's own biases within the ARW / in-run bias
    spread (sigma ~1e-4 rad; tolerance 5e-4 rad = 0.03 deg); the equilibrium is not zero (MEMS biases)."""
    n = 240 * 300
    fl = FX.flight(n, alpha0=0.0)
    u = Unit()
    (f, _), out, tru = u.run(fl, 0, n)
    roll_eq, pitch_eq = tilt_equilibrium(f)
    assert out[-1, 2] - tru[-1, 2] == pytest.approx(roll_eq, abs=5e-4)
    assert out[-1, 1] - tru[-1, 1] == pytest.approx(pitch_eq, abs=5e-4)
    assert math.hypot(roll_eq, pitch_eq) > 1e-3


@pytest.mark.unit
def test_sustained_turn_drags_the_vertical_unless_erection_is_cut_out():
    """CRN branches (n = 1 unit) from a common levelled state at 300 s, 60 s each: straight; a 15 deg bank
    turn (||f| - g| = 0.035 g and 0.75 deg/s, both under the cut-outs: erection on); a 30 deg bank turn
    (0.155 g, cut out). With common draws, the branch difference is the erection's response to the
    centripetal force: the 15 deg turn error lies between 2 deg and the false-vertical angle (15 deg); the
    30 deg turn only adds gyro drift (eps x 60 s with eps ~ 15 deg/h: 0.25 deg; bound 0.5 deg). After the
    15 deg turn the error decays with the erection time constant (< 10 % of its peak 3 tau later)."""
    n0, n1, n2 = 240 * 300, 240 * 66, 240 * 180
    t_turn = (301.0, 363.0)
    fl = {
        "straight": FX.flight(n0 + n1 + n2, alpha0=0.0),
        "b15": FX.flight(n0 + n1 + n2, alpha0=0.0, bank_deg={t_turn: 15.0}),
        "b30": FX.flight(n0 + n1 + n2, alpha0=0.0, bank_deg={t_turn: 30.0}),
    }
    u = Unit()
    s0, _, _ = u.run(fl["straight"], 0, n0)
    err = {}
    for name, script in fl.items():
        _, out, tru = u.run(script, n0, n1 + n2, state=s0)
        err[name] = np.hypot(wrap(out[:, 2] - tru[:, 2]), wrap(out[:, 1] - tru[:, 1]))  # tilt error magnitude
    d15 = np.degrees(np.abs(err["b15"] - err["straight"]))
    d30 = np.degrees(np.abs(err["b30"] - err["straight"]))
    peak = d15[:n1].max()
    assert 2.0 < peak < 15.0, peak
    assert d30[:n1].max() < 0.5, d30[:n1].max()
    k3tau = n1 + int(3 * P[H.P_ERECT_TAU] * 240) - 240 * 6
    assert d15[k3tau] < 0.1 * peak


@pytest.mark.unit
@pytest.mark.parametrize("decl_deg", [0.0, 2.0])
def test_heading_is_slaved_to_the_magnetic_sensor(decl_deg):
    """n = 1 unit x 600 s (5 slaving time constants) at track 0 and 180 deg with common draws: the heading
    error difference is the deviation's cosine term 2 C (the gyro-bias offset of the slaving loop is common),
    and the output is magnetic: declination ``decl`` shifts it by exactly -decl (sweep end 2 deg)."""
    params = load_params("M12_AVIONICS")
    params["ahrs"] = params["ahrs"].replace(mag_declination=math.radians(decl_deg))  # loaded sets are SI
    cfg = build_avionics_config(params=params)
    n = 240 * 600
    e = {}
    for track in (0.0, 180.0):
        u = Unit(cfg)
        _, out, tru = u.run(FX.flight(n, alpha0=0.0, track0_deg=track), 0, n)
        e[track] = float(wrap(out[-1, 0] - tru[-1, 0]))
    two_c = 2.0 * cfg.ahrs_p[H.P_DEV_C]
    assert e[0.0] - e[180.0] == pytest.approx(two_c, abs=2e-4)
    if decl_deg:
        _, out0, _ = Unit().run(FX.flight(n, alpha0=0.0), 0, n)
        _, out1, _ = Unit(cfg).run(FX.flight(n, alpha0=0.0), 0, n)
        assert float(wrap(out1[-1, 0] - out0[-1, 0])) == pytest.approx(-math.radians(decl_deg), abs=1e-12)
