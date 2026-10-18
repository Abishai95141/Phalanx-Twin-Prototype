"""Property tests (hypothesis) of the battery distances, the verdict rule and the sample selector."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.rng import RngService, StreamRegistry
from phalanx.validation.battery import Distance, stat_value, verdicts
from phalanx.validation.battery.config import TESTS
from phalanx.validation.battery.stats import B5Moments, FlightStats
from phalanx.validation.samples import SAMPLE_STREAM, select_flights

pytestmark = pytest.mark.property
SYMMETRIC = ("B1_fast", "B1_slow", "B1h_fast", "B1h_slow", "B2", "B3i", "B4", "B5ii")


def _group(seed: int, n: int, shift: float = 0.0) -> list[FlightStats]:
    g = np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed)))
    out = []
    for i in range(n):
        x = g.uniform(70, 100, 200)
        V = np.vander((x - 85) / 10, 4, increasing=True)
        y = (1 + 0.1 * (x - 85) / 10 + shift) * (1 + 0.01 * g.standard_normal(200))
        Vq = np.vander(g.uniform(-1, 1, 200), 3, increasing=True)
        T = g.uniform(0.6, 0.9, (121, 200))
        steps = np.column_stack([g.integers(0, 3, 12), g.integers(0, 2, 12), g.uniform(0.5, 5.0, 12) + shift])
        out.append(
            FlightStats(
                flight_id=f"f{i}",
                air_frac=0.9,
                b1_slow=g.uniform(-1, 1, 120),
                b1_fast=g.uniform(-1, 1, 120) + shift,
                b1h_slow=g.uniform(-1, 1, 120),
                b1h_fast=g.uniform(-1, 1, 120),
                b2=g.integers(-8, 8, 20) / 4.0,
                b3_coh=g.uniform(0, 1, (4, 4, 3)),
                b3_lgain=g.normal(0, 1, (4, 4, 3)),
                b3_steps=steps,
                b4=g.normal(1, 1, 12),
                b5_ff=B5Moments(XtX=V.T @ V, Xty=V.T @ y, yy=float(y @ y), sy=float(y.sum()), n=200.0),
                b5_egt=B5Moments(XtX=Vq.T @ Vq, Xty=T @ Vq, yy=(T * T).sum(1), sy=T.sum(1), n=200.0),
                b6=g.uniform(1, 2, (7, 16, 3)),
            )
        )
    return out


@settings(max_examples=12, deadline=None)
@given(seed=st.integers(0, 2**32 - 1), n=st.integers(2, 6))
def test_distance_to_itself_is_zero(seed, n):
    S = _group(seed, n)
    for t in TESTS:
        assert stat_value(t, S, S) == 0.0, t


@settings(max_examples=12, deadline=None)
@given(seed=st.integers(0, 2**32 - 1), n=st.integers(2, 6), m=st.integers(2, 6))
def test_distances_are_nonnegative_and_symmetric_where_defined(seed, n, m):
    A, B = _group(seed, n), _group(seed ^ 0x5A5A, m, shift=0.3)
    for t in TESTS:
        d = stat_value(t, A, B)
        assert np.isnan(d) or d >= 0.0, t
        if t in SYMMETRIC:
            assert stat_value(t, B, A) == pytest.approx(d, rel=1e-12, abs=1e-15), t


@settings(max_examples=12, deadline=None)
@given(seed=st.integers(0, 2**32 - 1))
def test_missing_flights_do_not_count(seed):
    """A group with None entries gives the same distance as the group without them."""
    A, B = _group(seed, 4), _group(seed ^ 1, 4, shift=0.2)
    for t in TESTS:
        d0 = stat_value(t, A, B)
        d1 = stat_value(t, [*A, None], [None, *B])
        assert (np.isnan(d0) and np.isnan(d1)) or d0 == d1, t


@settings(max_examples=30, deadline=None)
@given(
    d_sim=st.floats(0, 2, allow_nan=False),
    d_tail=st.floats(0, 2, allow_nan=False),
    spread=st.floats(0, 1, allow_nan=False),
    seed=st.integers(0, 2**32 - 1),
)
def test_verdict_rule(d_sim, d_tail, spread, seed):
    """PASS iff D_sim <= D_tail; otherwise FAIL iff the 5th percentile of the joint difference is > 0."""
    g = np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed)))
    bs = d_sim + spread * g.standard_normal(200)
    bt = d_tail + spread * g.standard_normal(200)
    sim = {t: Distance(D=d_sim, boot=bs) for t in TESTS}
    tail = {t: Distance(D=d_tail, boot=bt) for t in TESTS}
    v = verdicts(sim, tail)["B2"]
    lb = np.percentile(bs - bt, 5)
    if d_sim <= d_tail:
        assert v.verdict == "PASS"
    elif lb > 0:
        assert v.verdict == "FAIL"
    else:
        assert v.verdict == "INCONCLUSIVE"


@settings(max_examples=40, deadline=None)
@given(
    pop=st.sets(st.text(alphabet="abcdef0123456789", min_size=3, max_size=8), min_size=1, max_size=40),
    data=st.data(),
    root=st.integers(0, 2**128 - 1),
)
def test_selector_properties(pop, data, root):
    pop = sorted(pop)
    n = data.draw(st.integers(1, len(pop)))
    svc = RngService(root, StreamRegistry([SAMPLE_STREAM]))
    a = select_flights(pop, n, rng=svc, scenario="prop", purpose="p", justification="j")
    b = select_flights(list(reversed(pop)), n, rng=svc, scenario="prop", purpose="p", justification="j")
    assert a.flights == b.flights
    assert len(set(a.flights)) == n == a.n and set(a.flights) <= set(pop)
    assert list(a.flights) == sorted(a.flights)
