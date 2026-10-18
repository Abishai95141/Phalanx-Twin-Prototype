"""A3: pitch-loop stability margins of the delivered M05 gains, recomputed from the committed tables.

The margins are evaluated on the lifted 80 Hz loop (8.33 ms computation delay, 9 Hz servo, 50/100 Hz RSA/ASA,
ASA lever arm; ``linear.lifted_pitch_loop``) at the trimmed M06 short period of each designed point, using the
gains read back from ``configs/tejas/params/M05/gains.csv`` and ``fixed_gains.csv`` (not the design search).
Requirement: GM >= 6 dB and PM >= 35 deg at every designed point (JOAST 58(4) template). Target: 9-17 dB and
58-68 deg (the published Tejas range): met by the medians, not at every point (strict xfail below).

n = 122 feasible schedule points (every designed point of the 16 x 9 grid) + the 2 fixed-gain sets.
The 22 infeasible grid points (trim alpha > 20 deg, i.e. outside the flyable envelope at the reference mass)
reuse the nearest lower-altitude gains and carry no margin claim.

**Nonlinear-loop margins (E1 verifier §2, E1-HY item 7).** The margins above come from the linear design
model only. The second half of this file injects a loop gain K and an extra transport delay d (whole 240 Hz
ticks) at the plant input (the symmetric elevon, the linear model's loop-break point) of the nonlinear M05 +
M06 closed loop (the W1.2 TEST FIXTURE harness: 6-DOF airframe, DFCC replica on its 80 Hz clock, actuators
with their rate law, interpolated gain schedule; ideal sensor lanes), excites it with a 0.1 deg, 0.1 s
elevon pulse and classifies the 8 s response: oscillatory loss of stability (upper gain margin, delay
margin) when the elevon deviation, its 2 s moving average removed, no longer decays (late peak >= 0.9 x
early peak); aperiodic divergence (lower gain margin of the open-loop-unstable airframe) when the alpha
deviation grows; departure (|alpha - trim| > 3 deg) counts as both.

Sample: n = 3 grid flight points, chosen to span the regimes and the margin range: M0.6/4 km (subsonic,
GM 10.1 dB), M0.85/2 km (the high-q transonic corner, among the weakest points: GM 7.75 dB, PM 47 deg) and
M1.2/10 km (supersonic, open-loop stable airframe). Measured by bisection (E1-HY scratch run, recorded here;
the test itself brackets, it does not bisect):

- M0.6/4 km. Linear design (with RSA/ASA): K_up 3.18 (10.06 dB), K_lo 0.211, delay 76.6 ms. Linear, ideal
  sensors: K_up 3.33 (10.46 dB), K_lo 0.208, 79.7 ms. Nonlinear harness: K_up 3.30 (10.37 dB), K_lo 0.211,
  83-88 ms.
- M0.85/2 km. Design: K_up 2.44 (7.75 dB), K_lo 0.206, 44.9 ms. Ideal sensors: K_up 2.53 (8.07 dB), K_lo
  0.199, 47.8 ms. Nonlinear: K_up 2.56 (8.15 dB), K_lo 0.208, 50-54 ms.
- M1.2/10 km. Design: K_up 4.25 (12.58 dB), no lower margin, 157 ms. Ideal sensors: K_up 4.64 (13.33 dB),
  162.9 ms. Nonlinear: K_up 4.82 (13.65 dB), no lower margin, 158-163 ms.

(Delay margin of the linear loops = PM / w_gc.) Like with like (ideal sensors on both sides), the nonlinear
loop reproduces the linear margins within 0.3 dB in gain and -3 % to +13 % in delay; the design model's
RSA/ASA lag makes its margins the conservative ones. The test brackets each nonlinear margin around the
ideal-sensor linear prediction (gain +-10 %, i.e. +-0.8 dB; delay -15 %/+20 %: one tick is 4.2 ms, 9 % of
the smallest margin, and the 12.5 ms DFCC frame phase against the injection instant is not in the
continuous-delay approximation PM / w_gc) and checks the requirement directly in the nonlinear loop: stable
at K = 2 and K = 0.5 (+-6 dB) and with the extra delay equivalent to 35 deg at the design gain-crossover
frequency.
"""

from __future__ import annotations

import csv
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.airframe.analysis import Condition, reference_mass_properties, short_period, trim
from phalanx.airframe.build import airframe_param_set, build_config
from phalanx.airframe.kernel import O_ALPHA
from phalanx.core.time import TRUTH_DT_S
from phalanx.fcs.build import fcs_param_set, settings_from_params
from phalanx.fcs.design import blend, pitch_margins
from phalanx.fcs.linear import PitchGains, lifted_pitch_loop, margins_discrete

M05 = Path(__file__).resolve().parents[2] / "configs" / "tejas" / "params" / "M05"
APS = airframe_param_set()
CFG = build_config(APS, 1)
FPS = fcs_param_set()
S = settings_from_params(FPS)
MASS, CG, J = reference_mass_properties(APS)


def _rows(name):
    with open(M05 / name, encoding="utf-8") as fh:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(fh)]


def _margins(mach, alt, r, *, gear=0.0, w=None):
    cond = Condition(alt, mach, MASS, CG, J, gear=gear)
    tr = trim(CFG, cond, guess=(0.05 if mach > 0.5 else 0.2, 0.0, 30000.0))
    sp = short_period(CFG, cond, tr)
    g = PitchGains(r["g_n"], r["g_q"], r["g_i"], r["g_ff"])
    return pitch_margins(sp, g, blend(mach, S) if w is None else w, S)


@pytest.fixture(scope="module")
def schedule_margins():
    rows = [r for r in _rows("gains.csv") if r["feasible"] > 0.5]
    return rows, [_margins(r["mach"], r["alt"], r) for r in rows]


@pytest.mark.golden
def test_every_designed_point_meets_6db_35deg(schedule_margins):
    rows, ms = schedule_margins
    assert len(rows) == 122
    bad = [
        (r["mach"], r["alt"], m.gm_db, m.pm_deg)
        for r, m in zip(rows, ms, strict=True)
        if not (m.stable and m.gm_db >= 6.0 and m.pm_deg >= 35.0)
    ]
    assert not bad, bad
    # the recomputation reproduces the margins recorded by the design (same model, same tables)
    for r, m in zip(rows, ms, strict=True):
        assert m.gm_db == pytest.approx(r["gm_db"], rel=1e-6) and m.pm_deg == pytest.approx(
            r["pm_deg"], rel=1e-6
        )


@pytest.mark.golden
def test_fixed_gain_sets_meet_6db_35deg():
    """Fixed-gain reversion sets at their design points (gear up M0.5/3 km, gear down M0.25/300 m; pitch-rate
    command, w = 0)."""
    for r in _rows("fixed_gains.csv"):
        name = "down" if r["gear"] > 0.5 else "up"
        m = _margins(
            float(FPS.value(f"fixed_{name}_mach")),
            float(FPS.value(f"fixed_{name}_alt")),
            r,
            gear=r["gear"],
            w=0.0,
        )
        assert m.stable and m.gm_db >= 6.0 and m.pm_deg >= 35.0, (name, m)


@pytest.mark.golden
def test_median_margins_in_the_published_target_band(schedule_margins):
    _, ms = schedule_margins
    gm = np.median([m.gm_db for m in ms])
    pm = np.median([m.pm_deg for m in ms])
    assert 9.0 <= gm <= 17.0 and 58.0 <= pm <= 68.0, (gm, pm)


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 redesign on the calibrated M06: 8/122 points below 9 dB GM and "
    "19/122 below 58 deg PM (high-q transonic M0.6-0.9 at 0-6 km, where the airframe is most "
    "unstable), 25/122 above 68 deg PM",
)
def test_every_point_in_the_published_target_band(schedule_margins):
    _, ms = schedule_margins
    assert all(9.0 <= m.gm_db <= 17.0 and 58.0 <= m.pm_deg <= 68.0 for m in ms)


@pytest.mark.golden
def test_target_band_counts_recorded(schedule_margins):
    """Records the current distribution (exact counts) so a regression in the design shows up here."""
    _, ms = schedule_margins
    gm_in = sum(9.0 <= m.gm_db <= 17.0 for m in ms)
    pm_in = sum(58.0 <= m.pm_deg <= 68.0 for m in ms)
    assert (gm_in, pm_in) == (114, 78)
    assert min(m.gm_db for m in ms) > 7.0 and min(m.pm_deg for m in ms) > 40.0
    assert math.isfinite(max(m.pm_deg for m in ms))


# ------------------------------------------------------------------ nonlinear-loop margins (E1-HY item 7)
def _harness_module():
    path = Path(__file__).resolve().parents[1] / "integration" / "test_fcs_fixtures.py"
    spec = importlib.util.spec_from_file_location("fcs_fixtures_margins", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fcs_fixtures_margins"] = mod
    spec.loader.exec_module(mod)
    return mod


FX = _harness_module()
NL_POINTS = [(0.6, 4000.0), (0.85, 2000.0), (1.2, 10000.0)]
T_NL = 8.0
DEG = math.pi / 180.0


def linear_loop_margins(mach, alt, *, sensors=True):
    """(Margins, K_up, K_lo, delay margin s) of the linear design loop at a grid point. K_up / K_lo are the
    loop-gain factors at the plant input that move the nearest negative-real-axis crossing onto -1 from
    either side (K_lo = 0 if there is none); the delay margin is PM / w_gc."""
    r = next(x for x in _rows("gains.csv") if x["mach"] == mach and x["alt"] == alt)
    cond = Condition(alt, mach, MASS, CG, J)
    tr = trim(CFG, cond, guess=(0.05 if mach > 0.5 else 0.2, 0.0, 30000.0))
    sp = short_period(CFG, cond, tr)
    g = PitchGains(r["g_n"], r["g_q"], r["g_i"], r["g_ff"])
    rsa, asa = (S.rsa_wn, S.asa_wn) if sensors else (0.0, 0.0)
    ad, bd, cd, dd = lifted_pitch_loop(
        sp.a, sp.b, sp.nz_alpha, sp.nz_de, g, blend(mach, S), S.n_ref, S.q_ref, wn=S.servo_wn,
        zeta=S.servo_zeta, frame=S.frame, delay=S.delay, x_asa=S.x_asa, g0=S.g0, rsa_wn=rsa,
        rsa_zeta=S.sensor_zeta, asa_wn=asa, asa_zeta=S.sensor_zeta,
    )  # fmt: skip
    m = margins_discrete(ad, bd, cd, dd, S.frame)
    w = np.logspace(-3, math.log10(math.pi / S.frame * 0.999), 6000)
    eye = np.eye(ad.shape[0])
    lw = np.array(
        [-(cd @ np.linalg.solve(z * eye - ad, bd))[0, 0] - dd[0, 0] for z in np.exp(1j * w * S.frame)]
    )
    up, lo = [], []
    for k in range(w.size - 1):
        i0, i1 = lw[k].imag, lw[k + 1].imag
        if i0 * i1 < 0.0:
            c = lw[k] + i0 / (i0 - i1) * (lw[k + 1] - lw[k])
            if c.real < 0.0:
                (up if 1.0 / abs(c) > 1.0 else lo).append(1.0 / abs(c))
    return m, min(up), (max(lo) if lo else 0.0), math.radians(m.pm_deg) / m.w_gc


class PlantInputInjection:
    """TEST FIXTURE ``surf_hook``: the symmetric elevon reaching M06 becomes trim + K (sym(k - d) - trim) plus
    a 0.1 deg, 0.1 s pulse at t = 0.5 s; the differential (roll) part passes unchanged."""

    def __init__(self, k_gain: float, d_ticks: int):
        self.k, self.d = k_gain, d_ticks
        self.hist: list[float] = []
        self.trim: float | None = None

    def __call__(self, k: int, pos: np.ndarray) -> np.ndarray:
        sym = float(np.mean(pos[0:4]))
        diff = pos[0:4] - sym
        if self.trim is None:
            self.trim = sym
        self.hist.append(sym)
        delayed = self.hist[-1 - self.d] if len(self.hist) > self.d else self.trim
        pulse = 0.1 * DEG if 0.5 <= k * TRUTH_DT_S < 0.6 else 0.0
        pos[0:4] = self.trim + self.k * (delayed - self.trim) + pulse + diff
        return pos


def _window(x, a, b):
    return x[int(a / TRUTH_DT_S) : int(b / TRUTH_DT_S)]


def nonlinear_unstable(mach, alt, k_gain=1.0, d_ticks=0) -> bool:
    """Classification of the 8 s pulse response (module docstring): departure, oscillatory non-decay (for
    K >= 1 or an extra delay) or aperiodic growth (for K < 1)."""
    inj = PlantInputInjection(k_gain, d_ticks)
    h = FX.Harness(mach, alt, surf_hook=inj)
    e, a = [], []
    for _ in range(int(T_NL / TRUTH_DT_S)):
        of, oa = h.tick()
        e.append(float(np.mean(of[0:4])) - (inj.trim or 0.0))
        a.append(oa[O_ALPHA] - h.trim.alpha)
        if abs(a[-1]) > 3.0 * DEG:
            return True
    e, a = np.array(e), np.array(a)
    if k_gain >= 1.0 or d_ticks:
        hp = e - np.convolve(e, np.ones(480) / 480.0, mode="same")  # remove phugoid and trends (2 s)
        late, early = _window(hp, T_NL - 2.0, T_NL - 1.0), _window(hp, 1.5, 3.5)
        return float(np.max(np.abs(late))) >= 0.9 * float(np.max(np.abs(early)))
    return float(np.max(np.abs(_window(a, T_NL - 2.0, T_NL)))) > float(np.max(np.abs(_window(a, 1.0, 3.0))))


@pytest.mark.golden
def test_nonlinear_classifier_negative_controls():
    """The classifier is not vacuous: at M0.85/2 km the nominal loop is stable, K = 4 (above the linear
    upper margin 2.53) and K = 0.1 (below the lower margin 0.199) are unstable, and so is an extra 30-tick
    (125 ms) delay against a 48 ms margin."""
    m, a = 0.85, 2000.0
    assert not nonlinear_unstable(m, a)
    assert (
        nonlinear_unstable(m, a, 4.0) and nonlinear_unstable(m, a, 0.1) and nonlinear_unstable(m, a, 1.0, 30)
    )


@pytest.mark.golden
@pytest.mark.parametrize(("mach", "alt"), NL_POINTS)
def test_nonlinear_loop_margins_match_the_linear_prediction(mach, alt):
    """A3 in the nonlinear loop (n = 3 flight points, module docstring): the requirement holds (stable at
    K = 2, K = 0.5 and with the 35-deg-equivalent extra delay at the design crossover), and each nonlinear
    margin lies in the stated bracket around the ideal-sensor linear prediction. The design (sensor) model's
    margins are no larger than the ideal-sensor ones (sensor lag only removes margin)."""
    m_d, kup_d, klo_d, tau_d = linear_loop_margins(mach, alt)
    _, kup, klo, tau = linear_loop_margins(mach, alt, sensors=False)
    assert kup_d <= kup * (1 + 1e-9) and tau_d <= tau * (1 + 1e-9)
    # requirement in the nonlinear loop
    d35 = math.floor(math.radians(35.0) / m_d.w_gc / TRUTH_DT_S)
    assert not nonlinear_unstable(mach, alt, 2.0), "upper 6 dB"
    assert not nonlinear_unstable(mach, alt, 0.5), "lower 6 dB"
    assert not nonlinear_unstable(mach, alt, 1.0, d35), ("35 deg delay", d35)
    # brackets around the linear prediction
    assert not nonlinear_unstable(mach, alt, 0.9 * kup) and nonlinear_unstable(mach, alt, 1.1 * kup)
    if klo > 0.0:
        assert not nonlinear_unstable(mach, alt, 1.1 * klo) and nonlinear_unstable(mach, alt, 0.9 * klo)
    else:
        assert klo_d == 0.0 and not nonlinear_unstable(mach, alt, 0.1)  # open-loop stable: no lower margin
    d_lo, d_hi = math.floor(0.85 * tau / TRUTH_DT_S), math.ceil(1.2 * tau / TRUTH_DT_S)
    assert not nonlinear_unstable(mach, alt, 1.0, d_lo) and nonlinear_unstable(mach, alt, 1.0, d_hi)
