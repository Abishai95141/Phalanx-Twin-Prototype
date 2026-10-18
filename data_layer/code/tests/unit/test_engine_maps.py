"""M07 component-map lookups (``phalanx.engine.maps``): exactness on the grid, monotonicity, extensions.

Samples: the full committed AXI5 fan and HBTF HPC grids (every stable-branch node),
hypothesis cases as stated.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.engine import maps as mp
from phalanx.engine.design import build_tables, load_engine_params


@pytest.fixture(scope="module")
def tb():
    return build_tables(load_engine_params())


def _maps(tb):
    return (
        ("fan", tb.fan_nc, tb.fan_wc, tb.fan_pr, tb.fan_eff),
        ("hpc", tb.hpc_nc, tb.hpc_wc, tb.hpc_pr, tb.hpc_eff),
    )


@pytest.mark.unit
def test_compressor_lookup_reproduces_grid_nodes(tb):
    """At every stable-branch node (from the PR peak towards choke) the lookup returns the tabulated flow and
    efficiency exactly, and the stall PR of the speed line (Rline = RlineStall = 1, the first column)."""
    for _name, nc, wc, pr, ef in _maps(tb):
        for i in range(nc.size):
            jpk = int(np.argmax(pr[i]))
            for j in range(jpk, wc.shape[1]):
                w, e, prs, beyond = mp.compressor_lookup(nc[i], pr[i, j], nc, wc, pr, ef, 1.0)
                assert abs(w - wc[i, j]) < 1e-12 and abs(e - ef[i, j]) < 1e-12
                assert prs == pr[i, 0] and beyond == 0.0


@pytest.mark.property
@settings(max_examples=150, deadline=None)
@given(ncm=st.floats(0.42, 1.08), a=st.floats(0.0, 1.0), b=st.floats(0.0, 1.0))
def test_flow_falls_with_pressure_ratio_on_stable_branch(tb, ncm, a, b):
    """Static stability of the volume dynamics: on the stable branch W is non-increasing in PR at fixed
    speed."""
    for _name, nc, wc, pr, ef in _maps(tb):
        i = np.searchsorted(nc, ncm) - 1
        lo = float(min(pr[i].min(), pr[i + 1].min()))
        hi = float(max(pr[i].max(), pr[i + 1].max()))
        p1, p2 = sorted((lo + a * (hi - lo), lo + b * (hi - lo)))
        w1 = mp.compressor_lookup(ncm, p1, nc, wc, pr, ef, 1.0)[0]
        w2 = mp.compressor_lookup(ncm, p2, nc, wc, pr, ef, 1.0)[0]
        assert w2 <= w1 + 1e-12


@pytest.mark.unit
def test_beyond_peak_is_flagged_and_reduces_flow(tb):
    nc, wc, pr, ef = tb.fan_nc, tb.fan_wc, tb.fan_pr, tb.fan_eff
    i = 7  # Nc 1.0
    peak = pr[i].max()
    w_pk, _, _, b0 = mp.compressor_lookup(nc[i], peak, nc, wc, pr, ef, 1.0)
    w_hi, _, _, b1 = mp.compressor_lookup(nc[i], peak * 1.05, nc, wc, pr, ef, 1.0)
    assert b0 == 0.0 or abs(b0) < 1e-12
    assert b1 > 0.0 and w_hi < w_pk


@pytest.mark.unit
def test_fan_law_extension_below_and_above_the_grid(tb):
    """PROXY A-W1.3a-3: outside the speed grid the line is the edge line scaled by W ~ N, PR - 1 ~ N^2."""
    nc, wc, pr, ef = tb.fan_nc, tb.fan_wc, tb.fan_pr, tb.fan_eff
    for i_edge, s in ((0, 0.6), (nc.size - 1, 1.04)):
        n_edge = nc[i_edge]
        j = wc.shape[1] - 1
        pr_s = 1.0 + (pr[i_edge, j] - 1.0) * s * s
        w, e, prs, _ = mp.compressor_lookup(n_edge * s, pr_s, nc, wc, pr, ef, 1.0)
        assert abs(w - wc[i_edge, j] * s) < 1e-9 and abs(e - ef[i_edge, j]) < 1e-12
        assert abs(prs - (1.0 + (pr[i_edge, 0] - 1.0) * s * s)) < 1e-12


@pytest.mark.unit
def test_turbine_unchoke_monotone_and_choked():
    """A-W1.3a-4: flow capacity factor rises monotonically from ~0 at PR 1 to exactly 1 at/above the choke PR,
    with a continuous slope at the choke point."""
    prs = np.linspace(1.0005, 3.0, 400)
    g = np.array([mp.turbine_unchoke(p, 2.0, 1.3) for p in prs])
    assert np.all(np.diff(g) >= -1e-15)
    assert g[0] < 0.1 and np.all(g[prs >= 2.0] == 1.0)
    d = 1e-6
    left = (mp.turbine_unchoke(2.0 - d, 2.0, 1.3) - mp.turbine_unchoke(2.0 - 2 * d, 2.0, 1.3)) / d
    assert abs(left) < 1e-3  # zero slope arriving at choke


@pytest.mark.unit
def test_flow_function_c1_at_critical():
    g = 1.35
    prc = ((g + 1) / 2) ** (g / (g - 1))
    v = mp.flow_function(prc * (1 + 1e-12), g)
    assert abs(mp.flow_function(prc * (1 - 1e-9), g) - v) < 1e-8
    assert mp.flow_function(1.0, g) < 1e-3  # no flow without a pressure ratio
    # isentropic check at PR = 1.2 against the closed form
    x = 1 / 1.2
    ref = np.sqrt(2 * g / (g - 1) * (x ** (2 / g) - x ** ((g + 1) / g)))
    assert abs(mp.flow_function(1.2, g) - ref) < 1e-14


@pytest.mark.unit
def test_turbine_lookup_clamps_and_interpolates(tb):
    wp, ef = mp.turbine_lookup(100.0, 6.0, tb.hpt_np, tb.hpt_pr, tb.hpt_wp, tb.hpt_eff)
    i = int(np.flatnonzero(tb.hpt_np == 100.0)[0])
    j = int(np.flatnonzero(tb.hpt_pr == 6.0)[0])
    assert wp == tb.hpt_wp[i, j] and ef == tb.hpt_eff[i, j]
    lo = mp.turbine_lookup(10.0, 1.0, tb.hpt_np, tb.hpt_pr, tb.hpt_wp, tb.hpt_eff)
    assert lo == (tb.hpt_wp[0, 0], tb.hpt_eff[0, 0])
