"""A2 availability priors (calibration-pending, strict xfail until W2.6).

The CAG/Su-30MKI priors (architecture §10): serviceability 55-60 % against a 75 % norm; about 20 % of the
fleet in 1st/2nd-line maintenance, 11-12 % in HAL repair and overhaul (NMCD), 13-14 % AOG (NMCS); and the USAF
CANN rate of 10.6-12.7 per 100 sorties [TRANSFER: GAO-02-86]. Reproducing them needs the real usage (M02) and
failure processes (M10/M11) of W2.6 and a calibration of the M18 ASSUMPTION parameters; the W1 fixture fleet
is not calibrated, so these tests must fail now (strict xfail) and are the W2.6 calibration targets.

Sample: one 8-tail fleet over 180 days (1,440 aircraft-days); the binding failure (NMCD ~ 0 in a half-year
because depot R&O is a multi-year interval) is structural, not sampling noise.
"""

from __future__ import annotations

import pytest
from test_fork_fixture_fleet import DAY, EPOCH, FixtureFleetBuilder

from phalanx.fork.kpi import compute_kpis
from phalanx.fork.session import OpsSession


@pytest.fixture(scope="module")
def kpis():
    b = FixtureFleetBuilder(n_tails=8, horizon_days=180)
    s = OpsSession(b, 0xCA9)
    s.run_until(180 * DAY)
    return compute_kpis(s.log, b.m18_cfg, t0_utc=EPOCH, t1_utc=EPOCH + 180 * DAY, tails=b.tails)


@pytest.mark.statistical
@pytest.mark.xfail(
    strict=True,
    reason="W2.6 calibration: Su-30/CAG state-occupancy priors need real M02 usage, "
    "M10/M11 failure processes and depot R&O over multi-year horizons. Measured on this sample: MC 0.593 "
    "(0.55-0.60, in), NMCS 0.114 (0.13-0.14), NMCM 0.293 (0.18-0.22), NMCD 0.000 (0.11-0.12; structurally 0 "
    "in 180 days because depot R&O is a multi-year interval)",
)
def test_state_occupancy_reproduces_su30_cag_priors(kpis):
    assert 0.55 <= kpis.mc <= 0.60
    assert 0.13 <= kpis.nmcs <= 0.14
    assert 0.18 <= kpis.nmcm <= 0.22
    assert 0.11 <= kpis.nmcd <= 0.12


@pytest.mark.statistical
@pytest.mark.xfail(
    strict=True,
    reason="W2.6 calibration: CANN rate (USAF 10.6-12.7 per 100 sorties) depends on "
    "calibrated failure rates, spares scales and the CANN threshold. Measured on this sample: 9.23 per 100 "
    "sorties (737 sorties)",
)
def test_cann_rate_matches_usaf_band(kpis):
    assert 10.6 <= kpis.cann_rate <= 12.7


@pytest.mark.statistical
def test_fixture_fleet_kpis_are_in_a_plausible_range(kpis):
    """Not a calibration claim: a sanity band that catches a broken pipeline (all down, nothing flown)."""
    assert (
        0.2 < kpis.mc < 0.98 and kpis.sorties > 100 and kpis.man_hours > 0 and 0.0 < kpis.flying_task <= 1.0
    )
    assert abs(kpis.mc - (1.0 - kpis.nmcs - kpis.nmcm - kpis.nmcd)) < 1e-9
