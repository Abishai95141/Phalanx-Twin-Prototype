"""W1.1 A6 for M04: tracking spectra mostly below 0.25 Hz (V11) and PLA activity consistent with the M02 duty
gates, on the TEST FIXTURE plant of tests/integration/test_pilot_module.py.

V11 operationalised [A-W1.1-45]: >= 80 % of the stick-input variance (mean removed) below 0.25 Hz in tracking
windows. Sample (stated before running): 2 navigation/instrument sorties x 600 s from the start of the
outbound
transit (cruise, turns, climbs/descents: tracking tasks), 240 Hz -> Welch with nperseg = 2**14 (68 s,
df = 0.015 Hz), 50 % overlap (16 segments per window). The 0.8 threshold is checked on the pooled windows.

PLA duty (slow): 3 full sorties closed-loop; realised usage counts from the M04 PLA output (same counter as
the plan) must reproduce the plan-level summary: Type I and AB lights equal, Type III within +/- 1, time at
IRP and in AB within 3 % of flight time.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest
from scipy import signal

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import TRUTH_HZ, latest_truth_step
from phalanx.environment.config import load_env_config
from phalanx.scenario import phases as PH
from phalanx.scenario.config import INST_NAV, NAV_TRANSIT, load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import Planner
from phalanx.scenario.plan import S_PHASE
from phalanx.scenario.streams import STREAMS
from phalanx.scenario.usage import count_usage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
from test_pilot_module import FT_DEG, build

ROOT = Path(__file__).resolve().parents[2]


def plans_of(missions, n, key="v11", day0=dt.date(2026, 1, 6)):
    p, env = load_scenario_params(), load_env_config()
    fleet = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
    pl = Planner(p, env, fleet, RngService(0x46, StreamRegistry(STREAMS)).scope(KeyPath.of(scenario=key)))
    out = []
    d = day0
    while len(out) < n:
        slots, _ = pl.plan_day(d)
        for s in slots:
            plan = pl.build_sortie(s)
            if plan.mission_type in missions and len(out) < n:
                out.append(plan)
        d += dt.timedelta(days=1)
    return out


@pytest.mark.statistical
def test_v11_tracking_spectra_mostly_below_quarter_hertz():
    low = total = 0.0
    fracs = []
    for plan in plans_of((INST_NAV, NAV_TRANSIT), 2):
        s = build(plan, start_phase=PH.TRANSIT, lead_s=0.0)
        _, tr = s.run(s.start(), 600 * TRUTH_HZ, record=["pilot.stick_pitch", "pilot.stick_roll"])
        for name in ("pilot.stick_pitch", "pilot.stick_roll"):
            x = tr.ports[name][60 * TRUTH_HZ :]  # skip the 60 s initial capture transient of a cold start
            f, pxx = signal.welch(x - x.mean(), fs=TRUTH_HZ, nperseg=2**14, noverlap=2**13)
            lo_p = float(pxx[f < 0.25].sum())
            tot_p = float(pxx.sum())
            fracs.append(lo_p / tot_p)
            low += lo_p
            total += tot_p
    assert low / total >= 0.80, fracs
    assert min(fracs) >= 0.6, fracs


@pytest.mark.statistical
@pytest.mark.slow
def test_pla_activity_matches_the_plan_level_duty():
    for plan in plans_of(tuple(range(1, 11)), 3, key="duty"):
        s = build(plan, start_phase=PH.ENGINE_START, lead_s=5.0)
        n = latest_truth_step(s.t0_plan + int(plan.t_end_off_ns)) + 5 * TRUTH_HZ
        _, tr = s.run(s.start(), n, record=["pilot.pla"])
        pla = tr.ports["pilot.pla"][:, 0] * FT_DEG
        u = count_usage(pla, 1.0 / TRUTH_HZ)
        sm = plan.summary
        assert u.type1 == sm.type1 and u.ab_lights == sm.ab_lights, (u, sm)
        assert abs(u.type3 - sm.type3) <= 1, (u, sm)
        assert abs(u.irp_s - sm.irp_s) <= 0.03 * sm.flight_s and abs(u.ab_s - sm.ab_s) <= 0.03 * sm.flight_s
        assert int(plan.seg_i[0, S_PHASE]) == PH.PREFLIGHT
