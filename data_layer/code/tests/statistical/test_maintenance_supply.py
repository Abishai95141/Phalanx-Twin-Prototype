"""A2 supply calibration: with the Tejas OEM-support factor set to 1 (the pure CAG prior), AOG requisitions
are met on the CAG IL-76 timeliness distribution (conditional on the four reported bins).

Sample size: n = 400 AOG demands for one class (lead multiplier 1). The 99.9 % binomial half-width at the
cumulative shares 0.175 / 0.230 / 0.637 is 0.062 / 0.069 / 0.079; the 2-parameter log-normal fit itself
deviates by <= 0.06 from the 3 cumulative points (unit test), so the tolerance is the sum.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.fork.builder import OpsOnlyBuilder
from phalanx.fork.session import OpsSession
from phalanx.maintenance.config import load_m18_config
from phalanx.maintenance.world import FleetSpec
from phalanx.orders.model import Order

NS = 1_000_000_000
DAY = 86_400 * NS
EPOCH = 1_790_035_200 * NS
N = 400


@pytest.mark.statistical
def test_aog_lead_times_reproduce_the_cag_bins_at_factor_one():
    cfg = load_m18_config().with_values(tejas_supply_factor=1.0)
    b = OpsOnlyBuilder(FleetSpec(("T01",), ("SUL",), (0,)), EPOCH, m18_cfg=cfg)
    s = OpsSession(b, 0x5099)
    s.run_until(3600 * NS)
    res = s.submit(
        [
            Order(
                "AOG-ALL",
                "H",
                "HUMAN",
                s.t_utc,
                s.t_utc,
                "REQUISITION_SPARES",
                {"part_no": "SYN-PN-HYDP", "quantity": N},
                priority="AOG",
                target_base="SUL",
            )
        ]
    )
    assert res[0].verdict == "ACCEPTED"
    s.run_until(4000 * DAY)
    dem = [
        r
        for r in s.records("maint.records")
        if r["record_type"] == "SUPPLY_DEMAND" and r["status"] == "CLOSED" and r["order_id"] == "AOG-ALL"
    ]
    assert len(dem) >= 0.95 * N  # the CAG tail: a few demands outlast 4,000 days (log-normal sigma 1.84)
    lead_d = np.array([(r["t_close"] - r["t_open"]) / DAY for r in dem] + [np.inf] * (N - len(dem)))
    shares = np.array([0.1083, 0.0341, 0.2518, 0.2249])
    target = np.cumsum(shares[:-1]) / shares.sum()
    got = np.array([(lead_d <= e).mean() for e in (15.0, 30.0, 180.0)])
    tol = 3.29 * np.sqrt(target * (1 - target) / N) + 0.06
    assert np.all(np.abs(got - target) <= tol), (got, target, tol)
    assert math.isclose(float(np.median(lead_d)), cfg.lead_median_days(), rel_tol=0.25)


@pytest.mark.statistical
def test_tejas_factor_and_priority_scale_the_lead_time():
    """Structure and CRN: the same demand identities draw the same normal deviate, so an OEM-supported fleet
    (factor 0.3) and PHU priority (x2.5) scale every individual lead time exactly (n = 200 demands per
    arm)."""
    leads = {}
    for factor, prio in ((1.0, "AOG"), (0.3, "AOG"), (0.3, "PHU")):
        cfg = load_m18_config().with_values(tejas_supply_factor=factor)
        b = OpsOnlyBuilder(FleetSpec(("T01",), ("SUL",), (0,)), EPOCH, m18_cfg=cfg)
        s = OpsSession(b, 0x5099)
        s.run_until(3600 * NS)
        s.submit(
            [
                Order(
                    "Q",
                    "H",
                    "HUMAN",
                    s.t_utc,
                    s.t_utc,
                    "REQUISITION_SPARES",
                    {"part_no": "SYN-PN-HYDP", "quantity": 200},
                    priority=prio,
                    target_base="SUL",
                )
            ]
        )
        s.run_until(3000 * DAY)
        leads[(factor, prio)] = {
            r["demand_no"]: r["t_close"] - r["t_open"]
            for r in s.records("maint.records")
            if r["record_type"] == "SUPPLY_DEMAND" and r["status"] == "CLOSED" and r["order_id"] == "Q"
        }  # not the routine replenishments of the run

    def ratios(a, b):
        shared = sorted(set(leads[a]) & set(leads[b]))
        assert len(shared) > 150
        return np.array([leads[a][k] / leads[b][k] for k in shared if leads[b][k] > 3600 * NS])

    assert np.allclose(ratios((0.3, "AOG"), (1.0, "AOG")), 0.3, rtol=1e-4)  # whole-second rounding only
    assert np.allclose(ratios((0.3, "PHU"), (0.3, "AOG")), 2.5, rtol=1e-4)
