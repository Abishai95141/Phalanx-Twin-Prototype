"""A1 (closed loop): each schedule/limiter wins the MIN/MAX selection in its regime and holds its variable.

TEST FIXTURE plant (`tests/fadec_fixture.py`). Each regime is one deterministic 40 s run (9,600 truth steps)
started near the operating point; the last 2 s are checked. Ambient conditions select the regime (cold day ->
104.4 % corrected N1 cap; high dynamic pressure -> PS3 max; altitude idle -> PS3 min); two limiters that the
fixture cannot reach at default settings are exposed by moving one parameter (named in the test).
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from fadec_fixture import X_N1, X_N2, X_PS3_OUT, X_T5TC_A, Scenario, closed_loop, fixture_params, steady_state
from phalanx.fadec import FadecConfig
from phalanx.fadec.codes import (
    L_GOV_N2,
    L_N1,
    L_N2MAX,
    L_PS3MAX,
    L_PS3MIN,
    L_T5,
    NOZZLE_T5_BIT,
)

pytestmark = pytest.mark.integration
N = 40 * 240
N1R = 13270 * 2 * np.pi / 60
N2R = 16810 * 2 * np.pi / 60
PSI = 6894.757293168361


def _run(pla, *, t_amb=288.15, p_amb=101325.0, mach=0.0, start_pla=None, **p):
    cfg = FadecConfig.build(fixture_params())
    if p:
        cfg = cfg.with_p(**p)
    x0 = steady_state(
        start_pla if start_pla is not None else min(pla, 84.0), t_amb=t_amb, p_amb=p_amb, mach=mach
    )
    sc = Scenario(
        N,
        1,
        pla_deg=np.full((N, 1), pla),
        t_amb=np.full(N, t_amb),
        p_amb=np.full(N, p_amb),
        mach=np.full(N, mach),
    )
    r = closed_loop(sc, cfg=cfg, x0=x0)
    tail = slice(N - 480, N)
    return r, r.limiter[tail, 0], r.xs[N - 479 :, 0]


def test_part_power_is_governed_on_the_n2_schedule():
    _, codes, _ = _run(60.0, start_pla=60.0)
    assert (codes == L_GOV_N2).all()


def test_at_irp_n1_is_isochronous_at_its_physical_limit():
    _, codes, x = _run(95.0)
    assert ((codes & 15) == L_N1).all()
    assert abs(x[:, X_N1].mean() / N1R - 1.02) < 0.002
    assert not (codes & NOZZLE_T5_BIT).any()  # standard day: T5 below its limit, nozzle on its floor


def test_on_a_hot_day_the_nozzle_opens_to_hold_t5_at_irp():
    _, codes, x = _run(95.0, t_amb=313.15)
    assert ((codes & 15) == L_N1).all()  # fuel still N1-isochronous
    assert (codes & NOZZLE_T5_BIT).all()  # A8 modulated above its floor
    assert abs(x[:, X_T5TC_A].mean() - (273.15 + 830.0)) < 8.0  # T5 = f(T1, P0) held


def test_n1_cap_binds_on_a_cold_day():
    _, codes, x = _run(95.0, t_amb=230.0)
    assert ((codes & 15) == L_N1).all()
    cap = 1.044 * np.sqrt(230.0 / 288.15)
    assert abs(x[:, X_N1].mean() / N1R - cap) < 0.003  # 104.4 % corrected


def test_ps3_max_limits_at_high_dynamic_pressure():
    _, codes, x = _run(95.0, mach=0.9, start_pla=84.0)
    assert ((codes & 15) == L_PS3MAX).all()
    assert abs(x[:, X_PS3_OUT].mean() / PSI - 476.0) < 3.0


def test_ps3_min_is_off_by_default_so_altitude_idle_is_governed():
    """AD-50: the PS3-min override is off by default; altitude idle sits on the N2 schedule."""
    _, codes, _ = _run(18.0, t_amb=223.15, p_amb=26500.0, mach=0.6, start_pla=40.0)
    assert not ((codes & 15) == L_PS3MIN).any()
    assert ((codes & 15) == L_GOV_N2).all()


@pytest.mark.parametrize("pla", [31.0, 95.0])
def test_enabled_ps3_min_stays_under_the_protection_limiters(pla):
    """With the optional 80 psia PS3 floor enabled at 40,000 ft, Mach 0.3 (the former MAX-branch reading drove
    N1c to 1.075 here), the floor acts only in the governor branch below IRP: the N1 limit (104.4 % corrected
    cap) still bounds it, and at and above IRP it does not act at all. (Mach 0.3, not 0: at Mach 0 the
    tropopause T1 of -56.5 degC is below the T1 sensor span bottom, -54 degC, so the lane saturates warm and
    the
    cap is applied on a 2.5 K warm T1 - a dictionary span finding, outside the flight envelope.)"""
    t, p, m = 216.65, 18750.0, 0.3
    r, codes, x = _run(pla, t_amb=t, p_amb=p, mach=m, start_pla=40.0, ps3_min=80.0 * PSI)
    n1c = x[:, X_N1] / N1R / np.sqrt(t * (1 + 0.2 * m * m) / 288.15)
    assert n1c.max() <= 1.044 * 1.005
    if pla < 87.0:
        assert set(np.unique(codes & 15).tolist()) <= {L_PS3MIN, L_N1}
    else:
        assert not ((r.limiter[:, 0] & 15) == L_PS3MIN).any()


def test_n2_max_limiter_wins_when_its_limit_is_within_reach():
    """Exposed by lowering n2_max to 98 % (the fixture reaches ~101-102 % N2 at the N1 limit)."""
    _, codes, x = _run(95.0, n2_max=0.98)
    assert ((codes & 15) == L_N2MAX).all()
    assert abs(x[:, X_N2].mean() / N2R - 0.98) < 0.002


def test_t5_fuel_limiter_takes_over_when_the_nozzle_loop_cannot_act():
    """Exposed by disabling the nozzle T5 loop (a8_kp = a8_ki = 0) on a hot day: fuel then holds T5 at the
    limit plus the 20 K fuel-limiter margin."""
    _, codes, x = _run(95.0, t_amb=313.15, a8_kp=0.0, a8_ki=0.0)
    assert ((codes & 15) == L_T5).all()
    assert abs(x[:, X_T5TC_A].mean() - (273.15 + 830.0 + 20.0)) < 8.0


def test_sls_ground_idle_is_in_the_released_band_and_the_throttle_has_authority():
    """SLS, standard day, default configuration (PS3 minimum off): ground idle (PLA 18 deg) N2 lies in the
    released 63-70 % band (T-50 F404-102 ground idle ~63 % graph-read and 'about 70 %' text, KSAS 2006;
    F404-400
    test cell ~65 %, USAF IERA Vol. 3 - report §4), and steady N2 rises with PLA across 18-75 deg in steps of
    at least 1 % on the N2 governor (throttle authority). The notes table's 'flight idle' band is
    NATOPS-derived (restricted, Appendix A1) and is not used."""
    n2 = []
    for pla in (18.0, 31.0, 45.0, 60.0, 75.0):
        _, codes, x = _run(pla, start_pla=pla)
        assert ((codes & 15) == L_GOV_N2).all(), pla
        n2.append(x[:, X_N2].mean() / N2R)
    assert 0.63 <= n2[0] <= 0.70, n2[0]
    assert all(b - a >= 0.01 for a, b in itertools.pairwise(n2)), n2
