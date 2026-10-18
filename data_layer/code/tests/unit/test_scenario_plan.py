"""M02 sortie plans: grammar order, envelope and fuel invariants, restrictions, payload round trip,
keyed determinism, slot-key stability under tail swaps. Small deterministic samples (one fleet day =
10-40 plans)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.environment.config import load_env_config
from phalanx.scenario import phases as P
from phalanx.scenario.config import load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import GROUND_RUN, Overrides, Planner
from phalanx.scenario.plan import S_AB_OK, S_ALT, S_MACH, S_NZ, S_PHASE, S_PLA, SortiePlan
from phalanx.scenario.streams import STREAMS

ROOT = Path(__file__).resolve().parents[2]
PARAMS = load_scenario_params()
ENV = load_env_config()
FLEET = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
DAY = dt.date(2026, 1, 6)  # a Tuesday


def planner(key="unit", root=0x5CE):
    rng = RngService(root, StreamRegistry(STREAMS))
    return Planner(PARAMS, ENV, FLEET, rng.scope(KeyPath.of(scenario=key)))


@pytest.fixture(scope="module")
def day_plans():
    pl = planner()
    slots, runs = pl.plan_day(DAY)
    return pl, slots, runs, [pl.build_sortie(s) for s in slots]


OPENING = [P.PREFLIGHT, P.ENGINE_START, P.GROUND_IDLE, P.TAXI_OUT]
CLOSING_TAIL = [P.APPROACH, P.LANDING, P.TAXI_IN]


def _phases(plan: SortiePlan) -> list[int]:
    return [int(x) for x in plan.seg_i[:, S_PHASE]]


@pytest.mark.unit
def test_grammar_opening_and_closing(day_plans):
    _, _slots, _, plans = day_plans
    assert len(plans) > 10
    for pl in plans:
        ph = _phases(pl)
        assert ph[:4] == OPENING
        takeoff = ph.index(P.TAKEOFF)
        assert set(ph[4:takeoff]) <= {P.RUNUP, P.TAXI_OUT}
        assert ph[takeoff + 1] == P.CLIMB and ph[takeoff + 2] == P.TRANSIT
        assert P.MISSION in ph and ph[-1] == P.SHUTDOWN
        land = len(ph) - 1 - ph[::-1].index(P.LANDING)
        assert ph[land - 1] == P.APPROACH and ph[land + 1] == P.TAXI_IN
        assert pl.summary.landings == 1 + pl.summary.touch_and_goes


@pytest.mark.unit
def test_envelope_fuel_and_cycle_sanity(day_plans):
    _, _, _, plans = day_plans
    for pl in plans:
        seg = pl.seg_f
        air = np.isin(pl.seg_i[:, S_PHASE], list(P.AIRBORNE))
        assert np.all(seg[:, S_NZ] <= PARAMS.nz_max + 1e-12) and np.all(seg[:, S_MACH] <= PARAMS.mach_max)
        assert np.all(seg[air, S_ALT] <= PARAMS.ceiling_m) and np.all(seg[air, S_ALT] >= pl.field_elev_m)
        assert np.all((seg[:, S_PLA] >= 0) & (seg[:, S_PLA] <= PARAMS.pla_max_ab + 1e-12))
        s = pl.summary
        assert s.type1 == 1 and s.eot_s > s.flight_s > 10 * 60
        assert s.fuel_kg < pl.fuel_kg  # plan-level fuel budget (PROXY) never exceeds the fuel on board
        assert s.ab_s <= s.irp_s


@pytest.mark.unit
def test_restrictions_are_honoured():
    pl = planner()
    slots, _ = pl.plan_day(DAY)
    ov = Overrides(no_ab={"*"}, g_limit={"*": 5.0})
    for s in slots:
        plan = pl.build_sortie(s, ov)
        assert plan.summary.ab_lights == 0 and plan.summary.ab_s == 0.0
        assert np.all(plan.seg_i[:, S_AB_OK] == 0) and np.max(plan.seg_f[:, S_NZ]) <= 5.0
        assert np.max(plan.seg_f[:, S_PLA]) < PARAMS.pla_min_ab


@pytest.mark.unit
def test_payload_round_trip_and_phase_lookup(day_plans):
    _, _, _, plans = day_plans
    pl = plans[0]
    back, t0 = SortiePlan.from_payload(pl.to_payload(12345))
    assert t0 == 12345
    for name in ("seg_f", "seg_i", "t_off_ns", "ambient", "pilot_traits"):
        assert np.array_equal(getattr(back, name), getattr(pl, name)), name
    assert back.summary == pl.summary.__class__.from_vector(pl.summary.vector())
    assert (back.sortie_id, back.rng_key, back.tail, back.engine_serials) == (
        pl.sortie_id,
        pl.rng_key,
        pl.tail,
        pl.engine_serials,
    )
    assert pl.phase_at(0) == P.PREFLIGHT and pl.phase_at(pl.t_end_off_ns) == P.POSTFLIGHT


@pytest.mark.unit
def test_keyed_determinism_and_independence():
    a = planner()
    b = planner()
    sa, _ = a.plan_day(DAY)
    sb, _ = b.plan_day(DAY)
    assert sa == sb
    assert [x.to_payload()["seg_f"].tobytes() for x in map(a.build_sortie, sa[:5])] == [
        x.to_payload()["seg_f"].tobytes() for x in map(b.build_sortie, sb[:5])
    ]
    other, _ = planner(key="other").plan_day(DAY)
    assert [s.key for s in other] != [s.key for s in sa] or [s.tail for s in other] != [s.tail for s in sa]


@pytest.mark.unit
def test_tail_swap_keeps_the_slot_draws():
    """CRN: a slot flown by another tail keeps its key and every slot draw; with the mission held, the whole
    plan is unchanged apart from the tail. A swapped-in tail is not double-booked in that wave."""
    import dataclasses

    pl = planner()
    slots, _ = pl.plan_day(DAY)
    s = slots[0]
    base = pl.build_sortie(s)
    spare = next(t for t in s.squadron.tails if t != s.tail)
    moved = dataclasses.replace(s, tail=spare)
    swapped = pl.build_sortie(moved, Overrides(mission={s.key: base.mission_type}))
    assert swapped.rng_key == base.rng_key and swapped.tail == spare != base.tail
    for name in ("t_off_ns", "seg_f", "seg_i", "pilot_traits", "ambient"):
        assert np.array_equal(getattr(swapped, name), getattr(base, name)), name
    assert swapped.summary == base.summary
    # through the calendar: the swap order is applied and the spare flies only that slot in the wave
    slots2, _ = pl.plan_day(DAY, Overrides(tail_swap={s.key: spare}))
    by_key = {x.key: x for x in slots2}
    assert by_key[s.key].tail == spare
    same_wave = [x for x in slots2 if x.wave == s.wave and x.squadron.sid == s.squadron.sid]
    assert sum(x.tail == spare for x in same_wave) == 1
    assert [x.key for x in slots2] == [x.key for x in slots]  # the fly decisions are slot draws


@pytest.mark.unit
def test_non_flying_days_and_grounding():
    pl = planner()
    sunday = dt.date(2026, 1, 11)
    assert pl.plan_day(sunday) == ([], [])
    tails = set(FLEET.tails())
    grounded = {t for t in tails if t.startswith("TJ1")}
    slots, runs = pl.plan_day(DAY, Overrides(unavailable=grounded))
    assert slots and not ({s.tail for s in slots} & grounded) and not ({r.tail for r in runs} & grounded)


@pytest.mark.unit
def test_ground_run_plan():
    pl = planner()
    _, runs = pl.plan_day(DAY)
    gr = pl.build_ground_run(runs[0]) if runs else None
    if gr is None:
        pytest.skip("no ground run on this day for this key")
    assert gr.mission_type == GROUND_RUN and gr.summary.flight_s == 0 and gr.summary.type1 == 1
    assert gr.summary.eot_s == pytest.approx(PARAMS.ground_run_s, rel=1e-6)


@pytest.mark.property
@settings(max_examples=10, deadline=None)
@given(day=st.integers(0, 360), key=st.sampled_from(["p1", "p2", "p3"]))
def test_plans_valid_on_any_day(day, key):
    pl = planner(key=key)
    d = FLEET.start + dt.timedelta(days=day)
    slots, _ = pl.plan_day(d)
    for s in slots[:3]:
        plan = pl.build_sortie(s)
        assert np.all(np.diff(plan.t_off_ns) > 0)
        assert plan.summary.type1 == 1 and plan.summary.flight_s > 0
        assert np.max(plan.seg_f[:, S_NZ]) <= PARAMS.nz_max + 1e-12
        assert plan.t_start_utc_ns < int(s.t_takeoff_utc_s) * 10**9
        assert plan.seg_f[:, S_PLA].max() * 180 / np.pi <= 130.0 + 1e-9
