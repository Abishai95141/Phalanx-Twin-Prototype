"""M02 usage drivers for health (``usage.sortie_summary``; A-W1.1-33..35): exposure bounds, dust and salt
levels, chute streamings, time at temperature and peak Nz, from the plan. Sample: the first 12 sorties of
day 1 of the two-squadron fleet (both bases' roles), one root seed."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.environment.climatology import A_DUST
from phalanx.environment.config import load_env_config
from phalanx.scenario import phases as P
from phalanx.scenario.config import load_bases, load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import Planner
from phalanx.scenario.plan import S_NZ, S_PHASE
from phalanx.scenario.streams import STREAMS

ROOT = Path(__file__).resolve().parents[2]
PARAMS = load_scenario_params()
ENV = load_env_config()
FLEET = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")


def _planner(params=PARAMS):
    keys = RngService(11, StreamRegistry(STREAMS)).scope(KeyPath.of(scenario="drivers"))
    return Planner(params, ENV, FLEET, keys)


@pytest.fixture(scope="module")
def plans():
    pl = _planner()
    slots, runs = pl.plan_day(FLEET.start)
    return [pl.build_sortie(s) for s in slots[:12]] + [pl.build_ground_run(r) for r in runs[:1]]


def _sq(plan):
    return next(sq for sq in FLEET.squadrons if sq.sid == plan.squadron)


@pytest.mark.unit
def test_exposure_is_bounded_by_ground_time_and_engine_time(plans):
    lo_p = dataclasses.replace(PARAMS, exposure_agl_m=-1e9)  # nothing airborne counts
    hi_p = dataclasses.replace(PARAMS, exposure_agl_m=1e9)  # every engine-running segment counts
    pl, lo, hi = _planner(), _planner(lo_p), _planner(hi_p)
    for plan in plans:
        sq = _sq(plan)
        ph = plan.seg_i[:, S_PHASE]
        dur = plan.segment_durations_s()
        running = (ph != P.PREFLIGHT) & (ph != P.POSTFLIGHT)
        ground = running & ~np.isin(ph, sorted(P.AIRBORNE))
        e = pl.usage_drivers(plan, sq.base)["exposure_h"]
        assert lo.usage_drivers(plan, sq.base)["exposure_h"] == pytest.approx(dur[ground].sum() / 3600)
        assert hi.usage_drivers(plan, sq.base)["exposure_h"] == pytest.approx(dur[running].sum() / 3600)
        assert dur[ground].sum() / 3600 - 1e-12 <= e <= dur[running].sum() / 3600 + 1e-12
        assert hi.usage_drivers(plan, sq.base)["exposure_h"] == pytest.approx(plan.summary.eot_s / 3600)


@pytest.mark.unit
def test_dust_and_salt_levels(plans):
    pl = _planner()
    naliya = load_bases()["naliya"]
    assert naliya.salt_level == 1.0 and load_bases()["sulur"].salt_level == 0.0
    for plan in plans:
        d = pl.usage_drivers(plan, _sq(plan).base)
        level = 1.0 if plan.ambient[A_DUST] else PARAMS.dust_clear_level
        assert d["dust_index"] == pytest.approx(d["exposure_h"] * level)
        assert d["salt_index"] == 0.0  # Sulur and Nal are inland
        assert pl.usage_drivers(plan, naliya)["salt_index"] == pytest.approx(d["exposure_h"])


@pytest.mark.unit
def test_chute_time_at_temperature_and_peak_nz(plans):
    pl, never = _planner(), _planner(dataclasses.replace(PARAMS, chute_prob=0.0))
    for plan in plans:
        sm, d = plan.summary, pl.usage_drivers(plan, _sq(plan).base)
        full_stop = sm.landings - sm.touch_and_goes
        assert d["chute_streamed"] == (1 if full_stop > 0 else 0)  # chute_prob = 1 (A-W1.1-35)
        assert d["chute_streamed"] == int(plan.chute) and pl.chute_decision(plan) == plan.chute
        assert never.chute_decision(plan) is False
        assert d["time_at_temp_s"] == sm.irp_s >= d["ab_time_s"] == sm.ab_s
        air = np.isin(plan.seg_i[:, S_PHASE], sorted(P.AIRBORNE))
        expect = max(1.0, float(plan.seg_f[air, S_NZ].max())) if air.any() else 1.0
        assert d["max_nz"] == expect
        assert d == pl.usage_drivers(plan, _sq(plan).base)  # keyed draws: repeatable
    assert any(p.mission_type == 0 for p in plans)  # the ground run: no landing, no chute
