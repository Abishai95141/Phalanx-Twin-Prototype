"""Belief forks: hidden states resampled consistent with what the decision-maker could observe at t (AD-17).

The posterior is pluggable (``BeliefPosterior.apply(session, particle=...)``); a downstream solution can pass
its own (its particles or posterior). The reference implementation :class:`SurvivalPosterior` is deliberately
simple [PROXY A-W1.8-23]:

- each serial tracked by the hidden-state module gets a new time to failure drawn from its prior **conditioned
  on survival** over its observed operating hours since its last observed renewal (a CONFIRMED shop finding)
  or since the first record (ages before the record start are unknown: left truncation), and its usage clock
  is set to those observed hours;
- faults the maintenance organisation does not know about (no write-up, not under an open defect) are removed:
  the reference posterior assumes no undetected latent faults.

Inputs are the consumer observation set (``maint.records`` as of t) and static prior parameters, never truth
(I5); a test perturbs the hidden truth of the snapshot and checks the posterior output does not move.

Hidden-state modules opt in by implementing :class:`BeliefTarget` (the W1 fixture does; W2.6 asks M10/M11 to).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from phalanx.core.rng import KeyPath, RngService, Stream, StreamDecl, StreamRegistry, Variate
from phalanx.core.state import State

BELIEF_DECL = StreamDecl(
    "m22",
    "belief",
    ("scenario", "serial"),
    Variate.GENERATOR,
    owner="M22",
    description="belief-fork resample per serial, indexed by particle number",
)


class BeliefTarget(Protocol):
    def belief_items(self, state: State) -> list[str]: ...

    def belief_prior(self, state: State, serial: str) -> tuple[str, Mapping[str, float]]: ...

    def with_belief(
        self, state: State, draws: Mapping[str, Mapping[str, float]], keep_faults: set[str]
    ) -> State: ...


class BeliefPosterior(Protocol):
    def apply(self, session: Any, *, particle: int) -> None: ...


def observed_item_hours(maint_rows: list[Mapping[str, Any]], t_utc: int) -> dict[str, float]:
    """Operating hours per serial since its last observed renewal (or first record), from maint.records
    only."""
    events: list[tuple[int, int, Mapping[str, Any]]] = []
    for r in maint_rows:
        rt = r["record_type"]
        if rt in ("COMPONENT_LIFE", "SHOP_FINDING", "SORTIE") and int(r["t_event"]) <= t_utc:
            order = {"SHOP_FINDING": 0, "COMPONENT_LIFE": 1, "SORTIE": 2}[rt]
            events.append((int(r["t_event"]), order, r))
    events.sort(key=lambda e: (e[0], e[1], str(e[2]["record_key"]), int(e[2]["record_version"])))
    hours: dict[str, float] = {}
    where: dict[str, str] = {}  # serial -> tail while installed
    for _, _, r in events:
        rt = r["record_type"]
        if rt == "SHOP_FINDING" and r["shop_finding"] == "CONFIRMED" and r["serial_no"]:
            hours[r["serial_no"]] = 0.0
        elif rt == "COMPONENT_LIFE" and r["serial_no"]:
            hours.setdefault(r["serial_no"], 0.0)
            if r["install_action"] == "INSTALL":
                where[r["serial_no"]] = r["tail_no"]
            else:
                where.pop(r["serial_no"], None)
        elif rt == "SORTIE":
            fh = float(r["flight_hours"] or 0.0)
            for sn, tail in where.items():
                if tail == r["tail_no"]:
                    hours[sn] = hours.get(sn, 0.0) + fh
    return hours


@dataclass
class SurvivalPosterior:
    """Reference posterior (see module docstring). Weibull priors: params ``shape`` and ``scale_h``."""

    health_id: str
    m18_id: str = "m18"

    def draws(self, session: Any, *, particle: int) -> dict[str, dict[str, float]]:
        maint = session.obs.as_of(session.t_utc, "maint.records").to_pylist()
        usage = observed_item_hours(maint, session.t_utc)
        mod = session.system.modules[self.health_id]
        state = session.world.states[self.health_id]
        rng = RngService(session.root, StreamRegistry([BELIEF_DECL]))
        out: dict[str, dict[str, float]] = {}
        for sn in sorted(mod.belief_items(state)):
            fam, prm = mod.belief_prior(state, sn)
            if fam != "weibull":
                raise ValueError(f"reference posterior supports weibull priors, got {fam}")
            k, lam = float(prm["shape"]), float(prm["scale_h"])
            u_h = float(usage.get(sn, 0.0))
            path = KeyPath.of(
                scenario=session.builder.scenario, serial=sn, subsystem="m22", component="belief"
            )
            v = float(Stream(rng, path, BELIEF_DECL).generator(int(particle)).random())
            th_h = lam * ((u_h / lam) ** k - math.log(1.0 - v)) ** (1.0 / k)
            out[sn] = {"u_s": u_h * 3600.0, "th_s": th_h * 3600.0}
        return out

    def apply(self, session: Any, *, particle: int) -> None:
        draws = self.draws(session, particle=particle)
        m18 = session.system.modules[self.m18_id]
        keep = m18.belief_known_faults(session.world.states[self.m18_id])
        session.world.states[self.m18_id] = m18.belief_clear_unknown(session.world.states[self.m18_id], keep)
        mod = session.system.modules[self.health_id]
        session.world.states[self.health_id] = mod.with_belief(
            session.world.states[self.health_id], draws, keep
        )


__all__ = ["BELIEF_DECL", "BeliefPosterior", "BeliefTarget", "SurvivalPosterior", "observed_item_hours"]
