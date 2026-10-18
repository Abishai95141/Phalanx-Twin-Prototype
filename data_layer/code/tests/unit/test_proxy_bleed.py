"""W2.4a-2: customer bleed and power off-take of the proxy engines from the recorded discretes (A-W2.4a-22).

The rule (``phalanx.proxy.bleed.engine_bleed``): packs and wing/tail anti-ice are shared by the engines with
an open bleed valve; engine anti-ice draws from its own engine; bit k = engine k + 1. Exposing tests: an
engine with its valve closed gets no pack share, a single open valve carries the whole demand, nothing is
drawn with every valve closed and anti-ice off, and the boundary producer serves the per-engine series sample
by sample.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.proxy.bleed import BleedParams, engine_bleed
from phalanx.proxy.inputs import synthetic_inputs
from phalanx.proxy.replay import ProxyBoundary

P = BleedParams(w_pack=0.4, w_eai=0.1, w_wai=0.8, pto_w=30e3)


def test_all_valves_open_share_the_demand_equally():
    b = engine_bleed(np.array([15]), np.array([3]), np.array([0]), np.array([0]), P)
    assert b.shape == (4, 1)
    assert np.allclose(b[:, 0], 2 * 0.4 / 4)


def test_closed_valve_gets_no_share_and_one_valve_carries_all():
    b = engine_bleed(np.array([0b0101, 0b0001]), np.array([1, 3]), np.array([0, 0]), np.array([1, 0]), P)
    # sample 0: engines 1 and 3 open; demand = 1 pack + wing/tail anti-ice
    assert np.allclose(b[:, 0], [(0.4 + 0.8) / 2, 0.0, (0.4 + 0.8) / 2, 0.0])
    # sample 1: only engine 1 open carries both packs
    assert np.allclose(b[:, 1], [0.8, 0.0, 0.0, 0.0])


def test_engine_anti_ice_draws_from_its_own_engine_whatever_the_bleed_valve():
    b = engine_bleed(np.array([0]), np.array([3]), np.array([0b1000]), np.array([0]), P)
    assert np.allclose(b[:, 0], [0.0, 0.0, 0.0, 0.1])  # bit 3 = engine 4 (MEASURED for EAI)


def test_nothing_is_drawn_with_valves_closed_and_anti_ice_off():
    b = engine_bleed(np.zeros(5, int), np.full(5, 3), np.zeros(5, int), np.ones(5, int), P)
    assert np.all(b == 0.0)


@pytest.mark.parametrize("pto", [0.0, 25e3])
def test_boundary_serves_the_bleed_series_and_the_offtake(pto):
    inp = synthetic_inputs(5.0)
    n = inp.n
    blv = np.where(np.arange(n) < n // 2, 0, 15)
    inp = type(inp)(**{**inp.__dict__, "blv": blv, "pack": np.full(n, 3), "eai": np.zeros(n, int),
                       "wai": np.zeros(n, int)})  # fmt: skip
    rec = inp.replay_inputs()
    bleed = inp.bleed(P)
    bd = ProxyBoundary("boundary", rec, 3, bleed_kgs=bleed, pto_w=pto)
    out = bd._at(np.arange(n))
    assert np.array_equal(out["bleed_extract"], bleed.T)
    assert np.all(out["bleed_extract"][: n // 2] == 0.0) and np.allclose(out["bleed_extract"][n // 2 :], 0.2)
    assert np.all(out["pto_power"] == pto)


def test_inputs_without_discretes_mean_no_bleed():
    inp = synthetic_inputs(2.0)
    assert np.all(inp.bleed(P) == 0.0)
    assert np.all(inp.window(0, 4).bleed(P) == 0.0)
