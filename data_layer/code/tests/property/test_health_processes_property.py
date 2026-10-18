"""M10 process families: acceptance A1 (zero rate flat; gamma monotone; Wiener drift ∝ dust index; wash resets
by fraction ρ) as property tests, plus the moments of each process against its definition.

Random variates come from identity-keyed Philox generators built per example (no global RNG)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.health import processes as pr


def _gen(*key: int) -> np.random.Generator:
    return np.random.Generator(np.random.Philox(np.random.SeedSequence(20261014, spawn_key=key)))


pos = st.floats(min_value=1e-6, max_value=1e3, allow_nan=False)
small = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


@pytest.mark.property
@given(x=small, du=pos, dust=pos, z=st.floats(-5, 5))
def test_zero_rate_is_flat(x, du, dust, z):
    """A1: zero drift and zero diffusion leave fouling unchanged; a zero gamma rate gives exactly zero wear;
    zero usage leaves every process unchanged."""
    assert pr.wiener_fouling(x, 0.0, 0.0, du, dust, z) == pytest.approx(x, abs=0.0)
    assert pr.gamma_increment(_gen(1), 0.0, 0.3, 100.0, du) == 0.0
    assert pr.gamma_increment(_gen(2), 1e-3, 0.3, 100.0, 0.0) == 0.0
    assert pr.wiener_fouling(x, 1e-3, 1e-2, 0.0, dust, z) == x
    assert pr.incubation_growth(x, 5.0, 0.0, 1.0, 10.0) == x
    assert pr.exp_grow(1e-3, 0.1, 0.0) == 1e-3


@pytest.mark.property
@settings(max_examples=40, deadline=None)
@given(rate=st.floats(1e-6, 1e-2), cv=st.floats(0.05, 1.0), ref=st.floats(10, 1e4), k=st.integers(0, 10_000))
def test_gamma_paths_are_monotone(rate, cv, ref, k):
    """A1: a gamma-process path never decreases (every increment ≥ 0)."""
    g = _gen(3, k)
    x = 0.0
    for du in (0.5, 1.0, 3.0, 0.0, 7.0):
        inc = pr.gamma_increment(g, rate, cv, ref, du)
        assert inc >= 0.0
        x += inc
    assert x >= 0.0


@pytest.mark.property
def test_gamma_moments_match_definition():
    """Mean = rate·du and CV(du) = cv·sqrt(ref/du), n = 20,000 increments (relative SE of the mean ≈ 0.4 %,
    of the variance ≈ 1.4 % at CV 0.6; tolerances 3 SE)."""
    g = _gen(4)
    rate, cv, ref, du = 2e-3, 0.3, 1000.0, 250.0
    x = np.array([pr.gamma_increment(g, rate, cv, ref, du) for _ in range(20_000)])
    mean, cv_du = rate * du, cv * math.sqrt(ref / du)
    assert x.mean() == pytest.approx(mean, rel=3 * cv_du / math.sqrt(x.size))
    assert x.std() / x.mean() == pytest.approx(cv_du, rel=0.05)


@pytest.mark.property
def test_wiener_mean_and_variance_linear_in_exposure():
    """Away from the reflecting boundary the Wiener fouling increment has mean μ·d·du and variance σ²·d·du
    (n = 20,000 normal variates from a keyed stream; tolerance 3 SE)."""
    g = _gen(5)
    mu, sig, x0 = 1e-4, 1e-3, 1.0  # x0 far from 0: reflection inactive
    for dust, du in ((1.0, 100.0), (3.0, 100.0), (1.0, 400.0)):
        z = g.standard_normal(20_000)
        inc = np.array([pr.wiener_fouling(x0, mu, sig, du, dust, zi) for zi in z]) - x0
        assert inc.mean() == pytest.approx(mu * dust * du, abs=3 * sig * math.sqrt(dust * du / z.size))
        assert inc.var() == pytest.approx(sig**2 * dust * du, rel=0.05)


@pytest.mark.property
@given(dust=st.floats(0.1, 5.0), du=st.floats(1.0, 1e4))
def test_wiener_drift_proportional_to_dust(dust, du):
    """A1: with the noise switched off (z = 0) the fouling drift is exactly proportional to the dust index."""
    mu = 2e-5 / 3600.0
    one = pr.wiener_fouling(0.0, mu, 1e-4, du, 1.0, 0.0)
    k = pr.wiener_fouling(0.0, mu, 1e-4, du, dust, 0.0)
    assert k == pytest.approx(dust * one, rel=1e-12)


@pytest.mark.property
@given(x=st.floats(0.0, 1.0), rho=st.floats(0.0, 1.0))
def test_wash_resets_by_fraction_rho(x, rho):
    """A1: a wash removes exactly the fraction ρ of recoverable fouling; ρ outside [0, 1] is rejected."""
    assert pr.wash(x, rho) == pytest.approx(x * (1.0 - rho), abs=1e-15)
    with pytest.raises(ValueError):
        pr.wash(x, 1.5)


@pytest.mark.property
@given(x=st.floats(0.0, 1e-3), z=st.floats(-50, 50))
def test_wiener_fouling_never_negative(x, z):
    """Reflecting boundary: a fouling loss is never negative (a plain Wiener path could be)."""
    assert pr.wiener_fouling(x, 1e-6, 1e-3, 10.0, 1.0, z) >= 0.0


@pytest.mark.property
@given(n=st.integers(1, 2000))
def test_rub_in_step_then_monotone_to_c0_plus_c1(n):
    """Rub-in: 0 before flight 1, c0 on flight 1, monotone towards c0 + c1 (Sallee form)."""
    c0, c1, tau = 0.01, 0.005, 67.0
    assert pr.rub_in(0, c0, c1, tau) == 0.0
    v, v2 = pr.rub_in(n, c0, c1, tau), pr.rub_in(n + 1, c0, c1, tau)
    assert c0 <= v <= v2 <= c0 + c1
    assert pr.rub_in(200, c0, c1, tau) == pytest.approx(0.015, rel=0.04)  # ≈1.5 % by ~200 flights


@pytest.mark.property
@given(t=st.floats(0.0, 500.0), a=st.floats(0.001, 0.003), b=st.floats(1.4, 1.6))
def test_onset_loss_zero_at_onset_monotone_convex(t, a, b):
    tau, amp = 10.0, 0.05
    assert pr.onset_loss(0.0, a, b, tau, amp) == 0.0
    l0, l1, l2 = (pr.onset_loss(t + d, a, b, tau, amp) for d in (0.0, 1.0, 2.0))
    assert 0.0 <= l0 <= l1 <= l2
    assert (l2 - l1) >= (l1 - l0) - 1e-15  # convex (accelerating abnormal degradation)


@pytest.mark.property
def test_paris_growth_matches_ode_integration():
    """Closed-form Paris growth equals a fine explicit integration of da/dN = C (Y Δσ sqrt(π a))^m."""
    a0, c, m, ds = 1e-4, 1e-11, 3.0, 200.0
    a = a0
    for _ in range(20_000):
        a += c * (ds * math.sqrt(math.pi * a)) ** m * 0.1
    assert pr.paris_grow(a0, 2000.0, c, m, ds) == pytest.approx(a, rel=1e-3)
    assert pr.paris_grow(a0, 0.0, c, m, ds) == a0
    assert pr.paris_grow(a0, 10.0, c, 2.0, ds) > a0  # m = 2 closed form branch


@pytest.mark.property
def test_weibull_life_moments_and_latent_draw_consumption():
    """Weibull initiation life has the right mean; a latent draw always consumes two variates (CRN-stable)."""
    g = _gen(6)
    shape, scale = 1.5, 8000.0
    x = np.array([pr.weibull_life(g, shape, scale) for _ in range(20_000)])
    assert x.mean() == pytest.approx(scale * math.gamma(1 + 1 / shape), rel=0.03)
    g1, g2 = _gen(7), _gen(7)
    pr.latent_draw(g1, 0.0, 50.0, 2.0)
    pr.latent_draw(g2, 1.0, 50.0, 2.0)
    assert g1.random() == g2.random()


@pytest.mark.property
@given(state=st.integers(0, 1), u=st.floats(0.0, 0.999999))
def test_markov_two_state_transitions(state, u):
    p_on, p_off = 0.2, 0.7
    new = pr.markov_two_state(state, p_on, p_off, u)
    if state:
        assert new == (0 if u < p_off else 1)
    else:
        assert new == (1 if u < p_on else 0)


@pytest.mark.property
@given(age=st.floats(0.0, 300.0), du=st.floats(0.0, 300.0))
def test_incubation_growth_flat_then_linear_capped(age, du):
    onset, grow = 150.0, 200.0
    x = pr.incubation_growth(0.0, age, du, onset, grow)
    expected = max(0.0, min(1.0, (max(age + du, onset) - max(age, onset)) / grow))
    assert x == pytest.approx(expected, abs=1e-12)
