"""W1.1 A5: M02 fleet statistics inside the R§4 usage gates (plan level), on a scenario key independent of the
calibration key ('cal'; see M02.yaml header).

Sample (minimal sufficient, stated before running):
- Rate gates: the two-squadron fleet (32 aircraft) for 60 days from 2026-01-05 under scenario key 'gate'
  (~2,100 sorties, ~1,900 FH). With a per-flight usage CV of ~0.45, the relative SE of a per-FH rate is
  ~0.45 / sqrt(2,100) ~ 1 %, an order of magnitude inside every gate band.
- Surge rate: 5 surge days (2026-04-08..12) of the same fleet (~800 sorties).
- Engine dispersion (slow): 364 days (~13,000 sorties): P95 / mean of per-engine TAC per FH over 32 engines.
Gates needing the engine/airframe loop (realised PLA/N2 cycle counts, realised Nz exceedances) are in
`test_scenario_realised_usage_gates.py` (E1-MF: explicit targets and the W2.1 harness entry point).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.environment.climatology import DayWeather
from phalanx.environment.config import load_env_config
from phalanx.scenario.config import load_fleet_scenario, load_scenario_params
from phalanx.scenario.gates import DISPERSION_GATE, PLAN_GATES, fleet_stats, gate_failures
from phalanx.scenario.generator import Planner
from phalanx.scenario.streams import STREAMS

ROOT = Path(__file__).resolve().parents[2]
PARAMS = load_scenario_params()
ENV = load_env_config()
FLEET = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
START = dt.date(2026, 1, 5)


def planner(key="gate", cls=Planner):
    rng = RngService(0xA5, StreamRegistry(STREAMS))
    return cls(PARAMS, ENV, FLEET, rng.scope(KeyPath.of(scenario=key)))


@pytest.fixture(scope="module")
def sample():
    return planner().plans_between(START, 60)


#: the W1.1 brief's A5 bands (E1 verifier §2: the module's PLAN_GATES were wider, AB 3.5-5.5 per FH and
#: >=IRP 15-22 %); the test holds the generator to the brief, never to a widened band
BRIEF_BANDS = {"ab_lights_per_fh": (4.0, 5.0), "irp_frac": (0.17, 0.20)}


@pytest.mark.statistical
def test_plan_level_usage_gates(sample):
    """Plan-level gates at the brief's bands (``BRIEF_BANDS`` override the wider module bands). Measured on
    2026-10-15 (2,077 sorties, 1,834 FH): AB 4.51 per FH (bootstrap 95 % 4.29-4.72), >=IRP 17.9 %
    (17.4-18.3 %), both inside the brief's bands."""
    st = fleet_stats(sample)
    assert st.n_sorties > 1500 and st.flight_h > 1500
    gates = {**PLAN_GATES, **BRIEF_BANDS}
    assert gate_failures(st, gates) == {}, (gate_failures(st, gates), gates)


@pytest.mark.unit
def test_plan_fuel_pressure_ratio_proxy_error_vs_ussa76():
    """Exposes the PROXY limit of the plan-level fuel estimator (A-W1.1-27): its isothermal p/p0 =
    exp(-h / ISOTHERMAL_SCALE_HEIGHT_M) against the M03 USSA-76 profile at 0-15 km (geopotential; n = 7
    altitudes). The scale height is R T0 / g0 from the M03 constants; the proxy is high (conservative fuel
    cost) and the error grows to +42 % at 15 km."""
    import math

    from phalanx.environment.atmosphere import profile_tp, ussa76_profile
    from phalanx.scenario.generator import ISOTHERMAL_SCALE_HEIGHT_M

    c = ENV.constants
    r = 8314.32 / 28.9644  # M03 r_star / m0 (USSA-76)
    assert ISOTHERMAL_SCALE_HEIGHT_M == pytest.approx(r * 288.15 / 9.80665, abs=0.05)
    prof, n = ussa76_profile(ENV.layers, c)
    p0 = profile_tp(prof, n, 0.0, c.vector())[1]
    err = {}
    for h in (0.0, 3000.0, 6000.0, 9000.0, 11000.0, 13000.0, 15000.0):
        err[h] = math.exp(-h / ISOTHERMAL_SCALE_HEIGHT_M) / (profile_tp(prof, n, h, c.vector())[1] / p0) - 1.0
    assert all(e >= -1e-9 for e in err.values()), err  # never low: the plan's fuel cost is conservative
    assert err[6000.0] == pytest.approx(0.054, abs=0.005) and err[15000.0] == pytest.approx(0.42, abs=0.01)


@pytest.mark.unit
def test_brief_bands_are_not_wider_than_the_module_bands():
    """The override only ever narrows: each brief band lies inside the module's band."""
    for k, (lo, hi) in BRIEF_BANDS.items():
        assert PLAN_GATES[k][0] <= lo < hi <= PLAN_GATES[k][1], k


@pytest.mark.statistical
def test_negative_control_gates_reject_a_degenerate_generator():
    """A generator with only navigation/transit sorties (no high-activity missions) fails the cycle gates."""
    mt = PARAMS.missions
    only_nav = np.where(mt.mid == 9, 1.0, 0.0)
    p = PARAMS.with_(missions=dataclasses.replace(mt, ocu_mix=only_nav, ops_mix=only_nav))
    rng = RngService(0xA5, StreamRegistry(STREAMS))
    pl = Planner(p, ENV, FLEET, rng.scope(KeyPath.of(scenario="gate")))
    bad = gate_failures(fleet_stats(pl.plans_between(START, 10)))
    assert {"type3_per_fh", "ab_lights_per_fh", "nz5_per_1000h"} <= set(bad)


@pytest.mark.statistical
def test_sortie_duration_distribution(sample):
    """Report §4: lognormal, median ~45-55 min, P5-P95 ~25-90 min (tolerance +/- 5 min on the tails)."""
    st = fleet_stats(sample)
    assert 45.0 <= st.duration_median_min <= 55.0
    assert 20.0 <= st.duration_p05_min <= 30.0 and 85.0 <= st.duration_p95_min <= 95.0


@pytest.mark.statistical
def test_sorties_per_aircraft_per_flying_day(sample):
    """Report §4: ~1-2 sorties per aircraft per flying day in peace, 4-6 in surge."""
    pl = planner()
    flying = [
        START + dt.timedelta(days=k) for k in range(60) if pl.is_flying_day(START + dt.timedelta(days=k))
    ]
    peace = sum(1 for x in sample if x.summary.flight_s > 0) / (len(flying) * len(FLEET.tails()))
    assert 1.0 <= peace <= 2.0, peace
    surge_days = [dt.date(2026, 4, 8) + dt.timedelta(days=k) for k in range(5)]
    n = sum(len(pl.plan_day(d)[0]) for d in surge_days)
    surge = n / (len(surge_days) * len(FLEET.tails()))
    assert 4.0 <= surge <= 6.0, surge


@pytest.mark.statistical
def test_night_fraction(sample):
    st = fleet_stats(sample)
    assert 0.10 <= st.night_frac <= 0.20, st.night_frac


class _FogPlanner(Planner):
    """TEST FIXTURE at the M03 boundary: every day is a fog day with no other phenomenon."""

    def day_weather(self, sq, d):
        w = super().day_weather(sq, d)
        return DayWeather(
            w.month,
            w.z_temp,
            w.dp,
            w.dlne,
            False,
            True,
            False,
            False,
            False,
            w.wind_u,
            w.wind_dir_u,
            w.wind_jitter_u,
            w.turb_u,
        )


@pytest.mark.statistical
def test_weather_cancels_follow_the_phenomenon():
    """Fog cancels morning waves (03:00 UTC) with probability 0.8 and leaves later waves alone.
    n = 20 flying days x 2 squadrons x 1 morning wave = 40 morning waves (binomial 5-SE band)."""
    fog, clear = planner(cls=_FogPlanner), planner()
    days = [
        START + dt.timedelta(days=k) for k in range(28) if fog.is_flying_day(START + dt.timedelta(days=k))
    ][:20]
    morning_fog = morning_clear = later_fog = later_clear = 0
    for d in days:
        for pl, mf in ((fog, True), (clear, False)):
            slots, _ = pl.plan_day(d)
            m = sum(s.wave == 0 for s in slots)
            later = sum(s.wave > 0 for s in slots)
            if mf:
                morning_fog += m
                later_fog += later
            else:
                morning_clear += m
                later_clear += later
    ratio = morning_fog / morning_clear
    assert abs(ratio - (1 - PARAMS.cancel_fog)) < 0.15, ratio
    assert later_fog >= 0.8 * later_clear


@pytest.mark.statistical
@pytest.mark.slow
@pytest.mark.xfail(
    strict=True,
    reason="W2.6 calibration: plan-level engine dispersion 1.13-1.16 with the tail-affinity mechanism at "
    "the top "
    "of its sweep (A-W1.1-31); target ~1.3 needs per-tail allocation / engine usage data",
)
def test_engine_dispersion():
    """Engine-to-engine dispersion (P95 / mean of per-engine TAC per FH) over one year, 32 engines.
    Target ~1.3 (RTO-TR-028, Tornado); band 1.15-1.5 [ASSUMPTION A-W1.1-30]. Measured on key 'gate':
    1.13 (60 days), below the band: a calibration finding, reported."""
    st = fleet_stats(planner().plans_between(START, 364))
    assert DISPERSION_GATE[0] <= st.engine_dispersion <= DISPERSION_GATE[1], st.engine_dispersion
