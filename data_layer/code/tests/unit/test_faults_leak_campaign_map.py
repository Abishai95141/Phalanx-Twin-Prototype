"""The label-leak campaign covers every catalogue mode (W2.5 deliverable 6; PREREGISTRATION.md §5): each mode
is either injected through M11 (``faults.inject``), or, for an M10-process mode, set as the M10 states its
degraded condition consists of, or (the one physics mode) declared not injectable. Every mapped M10 state must
exist in M10 (an unknown state would raise inside a campaign worker, or worse, be skipped).

Sample: every catalogue mode once (the question is coverage; nothing smaller answers it)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.faults import load_catalogue
from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def _campaign():
    name = "w25_leak_campaign"
    if name not in sys.modules:
        code = ROOT / "analysis" / "faults_b7b8" / "code"
        sys.path.insert(0, str(code))
        spec = importlib.util.spec_from_file_location(name, code / "leak_campaign.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


def test_every_mode_has_an_injection_or_is_declared_physics():
    lc = _campaign()
    cat = load_catalogue()
    for mid, m in cat.items():
        evs = lc.injection(mid)
        if m.process == "physics":
            assert evs == [], mid
        elif m.process == "m10":
            assert mid in lc.M10_STATES, mid
            assert all(e.kind == "health.fault" and e.t_ns == 0 for e in evs), mid
        else:
            assert len(evs) == 1 and evs[0].kind == "faults.inject", mid
            assert evs[0].payload["mode"] == mid and evs[0].t_ns == lc.T_INJECT
    assert set(lc.M10_STATES) == {m for m, x in cat.items() if x.process == "m10"}


def test_mapped_m10_states_exist_and_change_m10():
    lc = _campaign()
    d = load_dictionary()
    m = HealthModule(
        "health", load_health_params(), config=HealthConfig(("IN20-X",), sensor_bias_channels(d), tail_no="X")
    )
    sysm = System([m], [], rng=RngService(1, StreamRegistry()), identity=KeyPath.of(scenario="m", tail="X"))
    w0 = sysm.start()
    for mid, states in lc.M10_STATES.items():
        st = w0.states["health"]
        for s, v in states:
            st, _ = m.on_event(
                st, Event(0, "health.fault", "health", {"state": s, "delta": v, "op": "set"}), 0
            )
        changed = any(not np.array_equal(st[k], w0.states["health"][k]) for k in st)
        assert changed or not states, mid
