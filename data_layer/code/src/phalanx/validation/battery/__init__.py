"""Behavioural fidelity battery B1-B6 (architecture §14.1), ported from the pre-registered round-2 estimators.

Typical use::

    from phalanx.validation.battery import BatteryConfig, Bootstrap, flight_stats, run_battery

    cfg = BatteryConfig()                                  # DASHlink proxy configuration (round 2)
    H = [flight_stats(r, cfg) for r in holdout_records]    # real holdout
    P = [flight_stats(r, cfg) for r in partner_records]    # D_tail partner (another tail)
    S = {"arm": [flight_stats(r, cfg) for r in synthetic_records]}   # paired with the holdout
    report = run_battery(H, P, early_idx, late_idx, S, Bootstrap(np.random.SeedSequence(seed)))

Discriminators are not part of the battery (diagnostic only, AD-21/AD-30).
"""

from phalanx.validation.battery.config import TESTS, VERDICT_TESTS, BatteryConfig
from phalanx.validation.battery.evaluate import (
    BOOTSTRAP_STREAM,
    ROUND2_ROOT_SEED,
    Bootstrap,
    Distance,
    PartResult,
    TestResult,
    choose_better_arm,
    compare,
    decision,
    group_values,
    stat_value,
    summarise,
    verdicts,
)
from phalanx.validation.battery.run import ArmResult, BatteryReport, run_battery
from phalanx.validation.battery.stats import B5Moments, FlightStats, flight_stats, flight_stats_many

__all__ = [
    "BOOTSTRAP_STREAM",
    "ROUND2_ROOT_SEED",
    "TESTS",
    "VERDICT_TESTS",
    "ArmResult",
    "B5Moments",
    "BatteryConfig",
    "BatteryReport",
    "Bootstrap",
    "Distance",
    "FlightStats",
    "PartResult",
    "TestResult",
    "choose_better_arm",
    "compare",
    "decision",
    "flight_stats",
    "flight_stats_many",
    "group_values",
    "run_battery",
    "stat_value",
    "summarise",
    "verdicts",
]
