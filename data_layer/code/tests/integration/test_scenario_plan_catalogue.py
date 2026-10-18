"""AD-49: ``scenario.sortie_plan`` and ``kpi.plan`` are catalogued; the real producers match the catalogue.

- ``scenario.sortie_plan``: M02's emitted plan payload (sortie mode, a real plan) carries exactly the declared
  ``PLAN_KEYS`` (+ the optional usage-mode ``summary``); the real M03 and M04 consume it.
- ``kpi.plan``: the declarations of M02 (producer) and M21 (RecordSink consumer) match the catalogue; the
  emitted payload is checked at run time by ``test_maintenance_protocol_runtime`` (now a required kind).

Sample: one sortie plan from day 2 of the two-squadron fleet (n = 1).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.dictionary.yamlio import load_yaml
from phalanx.environment.config import load_env_config
from phalanx.scenario.config import load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import Planner
from phalanx.scenario.module import EV_SORTIE_START, PLAN_EVENT, ScenarioModule
from phalanx.scenario.ports import EVENTS_OUT, PLAN_KEYS
from phalanx.scenario.streams import STREAMS

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
CAT = load_yaml(ROOT / "configs" / "interfaces" / "w1_events.yaml")["events"]
PARAMS = load_scenario_params()
ENV = load_env_config()
FLEET = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")


def _plan():
    keys = RngService(5, StreamRegistry(STREAMS)).scope(KeyPath.of(scenario="plan-cat"))
    pl = Planner(PARAMS, ENV, FLEET, keys)
    slots, _ = pl.plan_day(FLEET.start + dt.timedelta(days=1))
    return pl.build_sortie(slots[0])


def test_sortie_plan_payload_is_the_catalogued_plan():
    plan = _plan()
    m02 = ScenarioModule("m02", PARAMS, ENV, plan=plan, plan_targets=("env", "pilot"), t_kernel0_ns=0)
    m02.bind(RngService(1, StreamRegistry(m02.streams)).scope(KeyPath.of(scenario="plan-cat")))
    st = m02.init(m02.params, m02.keys)
    (ev,) = m02.initial_events()
    assert ev.kind == EV_SORTIE_START
    _, out = m02.on_event(st, ev, 0)
    plans = [e for e in out if e.kind == PLAN_EVENT]
    assert sorted(e.target for e in plans) == ["env", "pilot"]
    spec = CAT[PLAN_EVENT]
    assert spec["producer"] == "M02" and spec["consumers"] == ["M03", "M04"]
    assert tuple(spec["payload"]) == PLAN_KEYS == EVENTS_OUT[PLAN_EVENT]
    for e in plans:
        assert set(e.payload) - {"summary"} == set(PLAN_KEYS)


def test_real_m03_and_m04_consume_the_plan():
    from phalanx.environment.module import EnvironmentModule
    from phalanx.pilot.module import PilotModule, load_pilot_config

    plan = _plan()
    pay = plan.to_payload(0)
    pm = PilotModule("pilot", load_pilot_config(), utilities="util")
    pm.bind(
        RngService(3, StreamRegistry(pm.streams)).scope(KeyPath.of(scenario="plan-cat", tail="T", sortie=1))
    )
    _, out = pm.on_event(pm.init(pm.params, pm.keys), Event(0, PLAN_EVENT, "pilot", pay, source="m02"), 0)
    assert out  # the plan's utility events (start, chute, stores) are scheduled
    env = EnvironmentModule("env", ENV, n_engines=1)
    env.bind(
        RngService(4, StreamRegistry(env.streams)).scope(KeyPath.of(scenario="plan-cat", tail="T", sortie=1))
    )
    st0 = env.init(env.params, env.keys)
    st, _ = env.on_event(st0, Event(0, PLAN_EVENT, "env", pay, source="m02"), 0)
    assert any(not np.array_equal(np.asarray(st[k]), np.asarray(st0[k])) for k in st0)  # the plan was taken


def test_kpi_plan_payload_and_consumers():
    spec = CAT["kpi.plan"]
    assert spec["producer"] == "M02" and spec["consumers"] == ["M21", "M22"]
    assert tuple(spec["payload"]) == EVENTS_OUT["kpi.plan"]
    from phalanx.orders.ports import EVENTS_IN as M21_IN

    assert tuple(spec["payload"]) == M21_IN["kpi.plan"]
