"""M02 -> M09 ``util.refuel`` (AD-44 catalogue; AD-49 fill-to-target): the sortie start emits the planned
fuel target per M09 tank and the station fuel temperature, and the real M09 fills each tank up to its target,
stopping at the tank volume at the mixed fuel temperature, never defuelling (A-W1.1-37).

Sample: 4 sorties with and 4 without drop tanks from day 2 of the two-squadron fleet at the station
temperature; one plan on a 45 C and a 5 C day (volume limit); explicit targets into part-full M09 tanks
(fill-to-target); negative controls (unfitted drop tank, malformed targets)."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.environment.climatology import A_T_STN
from phalanx.environment.config import load_env_config
from phalanx.scenario.config import load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import Planner
from phalanx.scenario.module import EV_SORTIE_START, ScenarioModule
from phalanx.scenario.streams import STREAMS
from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as UL
from phalanx.utilities.fuel import fuel_density
from phalanx.utilities.module import Utilities, _tank_caps
from phalanx.utilities.params import param_vector

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
PARAMS = load_scenario_params()
ENV = load_env_config()
FLEET = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
P9 = param_vector(load_m09_params())


def _plans():
    keys = RngService(5, StreamRegistry(STREAMS)).scope(KeyPath.of(scenario="refuel"))
    pl = Planner(PARAMS, ENV, FLEET, keys)
    slots, _ = pl.plan_day(FLEET.start + dt.timedelta(days=1))
    plans = [pl.build_sortie(s) for s in slots]
    return [p for p in plans if p.drop_tanks][:4] + [p for p in plans if not p.drop_tanks][:4]


def _refuels(plan, t_stn=None):
    if t_stn is not None:
        amb = np.array(plan.ambient, copy=True)
        amb[A_T_STN] = t_stn
        plan = dataclasses.replace(plan, ambient=amb)
    m02 = ScenarioModule("m02", PARAMS, ENV, plan=plan, utilities="util", t_kernel0_ns=0)
    m02.bind(RngService(1, StreamRegistry(m02.streams)).scope(KeyPath.of(scenario="refuel")))
    st = m02.init(m02.params, m02.keys)
    (ev,) = m02.initial_events()
    assert ev.kind == EV_SORTIE_START
    _, out = m02.on_event(st, ev, 0)
    return plan, [e for e in out if e.kind == "util.refuel"]


def _m09(plan, fuel=(0.0,) * UL.N_TANKS, soak=None):
    drop = bool(plan.drop_tanks)
    t_soak = float(plan.ambient[A_T_STN]) if soak is None else soak
    cfg = UtilitiesConfig(soak_temp=t_soak, fuel=fuel, drop_tanks=(drop, drop, False))
    m09 = Utilities("util", load_m09_params(), config=cfg)
    m09.bind(
        RngService(2, StreamRegistry(m09.streams)).scope(KeyPath.of(scenario="refuel", tail="T", sortie=1))
    )
    return m09, m09.init(m09.params, m09.keys)


def _apply(m09, st, refuels):
    for e in refuels:
        st, _ = m09.on_event(st, e, 0)
    return st


def _mass(st):
    return np.array([st["f"][UL.F_FUEL_M + k] for k in range(UL.N_TANKS)])


def _cap_kg(t_k):
    return _tank_caps(P9) * float(fuel_density(P9, t_k))


def _target(e) -> tuple[int, float]:
    return int(np.asarray(e.payload["tank"])), float(np.asarray(e.payload["target_kg"]))


def test_refuel_targets_fill_m09_to_the_planned_load():
    """Targets sum to the planned load; empty M09 tanks fill to min(target, volume at the fuel temperature);
    only the fitted drop tanks get fuel; the audited refuel total is the mass added."""
    plans = _plans()
    assert any(p.drop_tanks for p in plans) and any(not p.drop_tanks for p in plans)
    for plan in plans:
        plan, ev = _refuels(plan)
        t_stn = float(plan.ambient[A_T_STN])
        assert all(str(np.asarray(e.payload["tail"])) == plan.tail for e in ev)
        assert all(float(np.asarray(e.payload["t_fuel"])) == t_stn for e in ev)
        sent = dict(_target(e) for e in ev)
        assert sum(sent.values()) == pytest.approx(plan.fuel_kg, rel=1e-12)
        m09, st = _m09(plan)
        st = _apply(m09, st, ev)
        m, cap = _mass(st), _cap_kg(float(st["f"][UL.F_FUEL_T]))
        for k in range(UL.N_TANKS):
            assert m[k] == pytest.approx(min(sent.get(k, 0.0), cap[k]), rel=1e-9, abs=1e-9)
        assert m[UL.T_DTC] == 0.0 and (m[[UL.T_DTL, UL.T_DTR]].sum() > 0) == bool(plan.drop_tanks)
        assert plan.fuel_kg - 60.0 <= m.sum() <= plan.fuel_kg + 1e-6
        assert float(st["f"][UL.F_FUEL_REFUEL]) == pytest.approx(m.sum(), rel=1e-12)
        assert float(st["f"][UL.F_FUEL_T]) == pytest.approx(t_stn, abs=1e-9)  # same-temperature fuel


def test_hot_day_fills_less_mass_into_the_same_volume():
    plan = next(p for p in _plans() if p.drop_tanks)
    hot, ev_h = _refuels(plan, t_stn=318.15)
    cold, ev_c = _refuels(plan, t_stn=278.15)
    assert [_target(e) for e in ev_h] == [_target(e) for e in ev_c]  # M02 no longer clips
    m_hot = _mass(_apply(*_m09(hot), ev_h))
    m_cold = _mass(_apply(*_m09(cold), ev_c))
    assert m_hot.sum() < m_cold.sum() <= plan.fuel_kg + 1e-6


def test_fill_to_target_tops_up_and_never_defuels():
    """Part-full tanks are topped up to the target (not target + residual, the W1 'kg added' overflow);
    tanks above their target keep their fuel; warmer fuel raises the lumped fuel temperature by the
    heat-capacity mix; a repeated event is idempotent."""
    plan = next(p for p in _plans() if not p.drop_tanks)
    t0, t_in = 278.15, 298.15
    cap = _cap_kg(t0)
    residual = [0.0] * UL.N_TANKS
    residual[UL.T_F1], residual[UL.T_F2] = 0.8 * cap[UL.T_F1], 0.2 * cap[UL.T_F2]
    targets = {UL.T_F1: 0.5 * cap[UL.T_F1], UL.T_F2: 0.6 * cap[UL.T_F2], UL.T_WL: 0.6 * cap[UL.T_WL]}
    ev = [
        Event(0, "util.refuel", "util", {"tail": plan.tail, "tank": k, "target_kg": v, "t_fuel": t_in})
        for k, v in targets.items()
    ]
    m09, st0 = _m09(plan, fuel=tuple(residual), soak=t0)
    st = _apply(m09, st0, ev)
    m = _mass(st)
    assert m[UL.T_F1] == residual[UL.T_F1]  # above its target: no defuel
    assert m[UL.T_F2] == pytest.approx(targets[UL.T_F2], rel=1e-12)  # topped up, not target + residual
    assert m[UL.T_WL] == pytest.approx(targets[UL.T_WL], rel=1e-12)
    added = m.sum() - sum(residual)
    assert float(st["f"][UL.F_FUEL_REFUEL]) == pytest.approx(added, rel=1e-12)
    t_mix = float(st["f"][UL.F_FUEL_T])
    assert t0 < t_mix < t_in  # warmer fuel mixed into colder fuel and structure
    cp, c_s = float(P9[UL.P_FUEL_CP]), float(P9[UL.P_FUEL_C_STRUCT])
    c0 = sum(residual) * cp + c_s
    assert t_mix == pytest.approx((c0 * t0 + added * cp * t_in) / (c0 + added * cp), rel=1e-9)
    again = _apply(m09, st, ev)
    assert np.array_equal(again["f"], st["f"])  # idempotent


def test_refuel_rejects_an_unfitted_drop_tank_and_malformed_targets():
    plan = next(p for p in _plans() if not p.drop_tanks)
    m09, st = _m09(plan)

    def ev(**kw):
        pay = {"tail": plan.tail, "tank": UL.T_F1, "target_kg": 100.0, "t_fuel": 288.15} | kw
        return Event(0, "util.refuel", "util", pay)

    for bad in (
        ev(tank=UL.T_DTL),  # drop tank not fitted
        ev(tank=UL.N_TANKS),
        ev(target_kg=-1.0),
        ev(target_kg=float("nan")),
        ev(t_fuel=0.0),
    ):
        with pytest.raises(ContractError):
            m09.on_event(st, bad, 0)
    st2, _ = m09.on_event(st, ev(tank=UL.T_DTL, target_kg=0.0), 0)  # a zero target is a no-op
    assert np.array_equal(st2["f"], st["f"])
