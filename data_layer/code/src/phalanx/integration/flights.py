"""Whole-sortie flights shared by the slow acceptance checks (A5 validator, A6 smoke, A10 behaviour glance).

``fly(plan)`` runs one telemetry sortie from post-start idle with everything on (the event validator, the
physical invariants, the recorder and the M14 feed) chunk by chunk until the window end or the first
``SortieAborted``, and keeps what those checks need: the validator's verdict, the abort (kind, instant,
phase), the realised usage, and the engine channels at 4 Hz: truth ports sampled every 60th truth step, and
recorded channels as the 4 Hz sample-and-hold of the M13 CIR (the DASHlink word rate of the battery
estimators). Results are cached per process by ``(sortie_id, scenario, root)``, so the checks that share a
sortie fly it once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from .plans import GATE_ROOT, GATE_SCENARIO, gate_sorties
from .sortie import SortieAborted, SortieRunner
from .system import SortieSpec, build_sortie_system

#: 4 Hz: the DASHlink engine word rate the B1/B2 estimators were registered at (BatteryConfig.rate_hz)
GLANCE_HZ = 4
STEP_STRIDE = 240 // GLANCE_HZ
ENGINE_TRUTH = ("eng.n1", "eng.n2", "eng.t5", "eng.wf")
#: recorded engine channels (voted speeds, averaged T5, metered fuel flow), dictionary EU
ENGINE_RECORDED = ("ENG.N1.V", "ENG.N2.V", "ENG.T5", "ENG.WFM")


@dataclass
class Flight:
    sortie_id: str
    mission_type: str
    flown_s: float
    abort: SortieAborted | None
    abort_phase: str | None
    liftoff_s: float | None
    violations: list
    checked_events: int
    realised: object | None
    #: 4 Hz series (index j at t = j / 4 s from the window start): truth ports (SI) and recorded channels (EU)
    truth: dict[str, np.ndarray] = field(default_factory=dict)
    recorded: dict[str, np.ndarray] = field(default_factory=dict)
    phase: np.ndarray | None = None
    #: the sortie's ``sortie.manifest`` record (one validated row; recorder stop at the window end or at the
    #: last chunk before the abort)
    manifest: object | None = None


def diverse_sorties(n: int = 5, days: int = 10) -> list:
    """The first sortie of each mission type in the gate sample (gate plan order), up to ``n``."""
    picked, seen = [], set()
    for p in gate_sorties(days=days):
        if p.mission_type not in seen:
            picked.append(p)
            seen.add(p.mission_type)
        if len(picked) == n:
            break
    return picked


def _hold(t_s: np.ndarray, v: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Sample-and-hold of samples (t_s, v) on ``grid`` (NaN before the first sample)."""
    j = np.searchsorted(t_s, grid, side="right") - 1
    out = np.full(grid.size, np.nan)
    ok = j >= 0
    out[ok] = v[j[ok]]
    return out


@lru_cache(maxsize=16)
def _fly(sortie_id: str, scenario: str, root: int) -> Flight:
    plan = next(p for p in gate_sorties(days=10) if p.sortie_id == sortie_id)
    ss = build_sortie_system(SortieSpec(plan=plan, scenario=scenario, root=root))
    r = SortieRunner(
        ss,
        validate_events=True,
        cir_channels=ENGINE_RECORDED,
        keep_cir=True,
        record=[*ENGINE_TRUTH, "af.wow", "scenario.phase"],
    )
    st = r.begin()
    truth: dict[str, list] = {p: [] for p in ENGINE_TRUTH}
    phase: list = []
    rec: dict[str, list] = {c: [] for c in ENGINE_RECORDED}
    locs = {c: ss.dictionary.contract_location(c) for c in ENGINE_RECORDED}
    abort = None
    liftoff = None
    while st.world.k < r.end_step(st):
        try:
            st, outs = r.run(st, min(r.chunk, r.end_step(st) - st.world.k))
        except SortieAborted as e:
            abort = e
            break
        for c in outs:
            P = c.trace.ports
            j0 = (-c.k0) % STEP_STRIDE
            for p in ENGINE_TRUTH:
                truth[p].append(np.asarray(P[p])[j0::STEP_STRIDE, 0])
            phase.append(np.asarray(P["scenario.phase"])[j0::STEP_STRIDE])
            if liftoff is None:
                wow = np.all(np.asarray(P["af.wow"])[:, 1:] == 1, axis=1)
                off = np.flatnonzero(~wow)
                if off.size:
                    liftoff = (c.k0 + int(off[0])) / 240.0
            tab = c.cir.table if hasattr(c.cir, "table") else c.cir
            pid = np.array(tab.column("param_id").to_pylist())
            lane = np.array([x or "" for x in tab.column("lane").to_pylist()])
            ts = (tab.column("t_sample").to_numpy() - ss.epoch_utc_ns) / 1e9
            val = tab.column("value").to_numpy()
            for cid, loc in locs.items():
                sel = (pid == loc["param_id"]) & (lane == (loc["lane"] or ""))
                rec[cid].append((ts[sel], val[sel]))
    realised = None
    if abort is None:
        st = r.close(st)
        realised = r.realised_usage(st)
    manifest = r.manifest(st)
    flown = st.world.k / 240.0 if abort is None else abort.k / 240.0
    truth_a = {p: np.concatenate(v) if v else np.empty(0) for p, v in truth.items()}
    n4 = next(iter(truth_a.values())).size
    grid = np.arange(n4) / GLANCE_HZ
    recorded = {}
    for cid, parts in rec.items():
        t = np.concatenate([a for a, _ in parts]) if parts else np.empty(0)
        v = np.concatenate([b for _, b in parts]) if parts else np.empty(0)
        o = np.argsort(t, kind="stable")
        recorded[cid] = _hold(t[o], v[o], grid)
    ph = np.concatenate(phase) if phase else np.empty(0, np.int64)
    abort_phase = None if abort is None else abort.phase
    return Flight(
        sortie_id=plan.sortie_id,
        mission_type=str(plan.mission_type),
        flown_s=flown,
        abort=abort,
        abort_phase=abort_phase,
        liftoff_s=liftoff,
        violations=list(r.validator.violations),
        checked_events=int(sum(r.validator.seen.values())),
        realised=realised,
        truth=truth_a,
        recorded=recorded,
        phase=ph,
        manifest=manifest,
    )


def fly(plan, *, scenario: str = GATE_SCENARIO, root: int = GATE_ROOT) -> Flight:
    """One whole sortie of the gate sample (cached per process; module docstring)."""
    return _fly(plan.sortie_id, scenario, int(root))


__all__ = ["ENGINE_RECORDED", "ENGINE_TRUTH", "GLANCE_HZ", "Flight", "diverse_sorties", "fly"]
