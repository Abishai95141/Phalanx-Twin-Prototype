"""Unit tests of the verdict rules, the joint bootstrap and the battery protocol guards."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.validation.battery import (
    ROUND2_ROOT_SEED,
    Bootstrap,
    Distance,
    choose_better_arm,
    decision,
    run_battery,
    verdicts,
)
from phalanx.validation.battery.config import TESTS, VERDICT_TESTS
from phalanx.validation.battery.stats import FlightStats

pytestmark = pytest.mark.unit


def _cmp(D: dict[str, float], boot: dict[str, np.ndarray] | None = None, nb: int = 200):
    boot = boot or {}
    return {t: Distance(D=D.get(t, 0.1), boot=boot.get(t, np.full(nb, D.get(t, 0.1)))) for t in TESTS}


def test_pass_when_dsim_at_or_below_tail():
    tail = _cmp({t: 0.2 for t in TESTS})
    sim = _cmp({t: 0.2 for t in TESTS}, boot={t: np.full(200, 5.0) for t in TESTS})
    v = verdicts(sim, tail)
    assert all(r.verdict == "PASS" for r in v.values())  # D_sim <= D_tail wins even with a huge bootstrap


def test_fail_needs_one_sided_lower_bound_above_zero():
    nb = 1000
    tail = _cmp({"B2": 0.10}, boot={"B2": np.full(nb, 0.10)}, nb=nb)
    clear = np.linspace(0.12, 0.30, nb)  # D_sim - D_tail > 0 in every resample
    v = verdicts(_cmp({"B2": 0.2}, boot={"B2": clear}, nb=nb), tail)
    assert v["B2"].verdict == "FAIL"
    assert v["B2"].parts["B2"].lb95_one_sided_Dsim_minus_Dtail > 0
    straddle = np.linspace(0.0, 0.4, nb)  # 5th percentile of the difference < 0
    v = verdicts(_cmp({"B2": 0.2}, boot={"B2": straddle}, nb=nb), tail)
    assert v["B2"].verdict == "INCONCLUSIVE"


def test_multipart_rules():
    """B3/B5: PASS iff every part passes; FAIL iff any part fails; otherwise INCONCLUSIVE (DEVIATIONS D1)."""
    nb = 500
    tail = _cmp({t: 0.1 for t in TESTS}, nb=nb)
    fail_boot = np.full(nb, 0.5)
    v = verdicts(_cmp({"B3i": 0.05, "B3ii": 0.5}, boot={"B3ii": fail_boot}, nb=nb), tail)
    assert v["B3"].verdict == "FAIL" and v["B3"].parts["B3i"].verdict == "PASS"
    v = verdicts(_cmp({"B5i": 0.05, "B5ii": 0.3}, boot={"B5ii": np.linspace(0, 0.6, nb)}, nb=nb), tail)
    assert v["B5"].verdict == "INCONCLUSIVE"
    assert set(VERDICT_TESTS) == {"B1", "B2", "B3", "B4", "B5", "B6"}
    assert VERDICT_TESTS["B1"] == ("B1_fast",)  # B1 verdict on the fast band only


def test_strict_pass_uses_temporal_bar():
    tail = _cmp({t: 0.2 for t in TESTS})
    temp = _cmp({t: 0.05 for t in TESTS})
    v = verdicts(_cmp({t: 0.1 for t in TESTS}), tail, temp)
    assert v["B1"].verdict == "PASS" and v["B1"].strict_pass is False
    v = verdicts(_cmp({t: 0.01 for t in TESTS}), tail, temp)
    assert v["B4"].strict_pass is True


def test_nan_distance_is_never_pass():
    tail = _cmp({t: 0.2 for t in TESTS})
    v = verdicts(_cmp({"B4": np.nan}, boot={"B4": np.full(200, np.nan)}), tail)
    assert v["B4"].verdict == "INCONCLUSIVE"


def test_decision_rule():
    tail = _cmp({t: 0.2 for t in TESTS})
    ok = verdicts(_cmp({t: 0.1 for t in TESTS}), tail)
    assert decision(ok, g0_pass=True)["decision"] == "GO"
    assert decision(ok, g0_pass=False)["decision"].startswith("REWORK")
    bad = verdicts(_cmp({"B2": 0.5}, boot={"B2": np.full(200, 0.5)}), tail)
    d = decision(bad, g0_pass=True)
    assert d["fails"] == ["B2"] and d["decision"] != "GO"


def test_choose_better_arm_orders_by_pass_then_fail_then_ratio():
    tail = _cmp({t: 0.2 for t in TESTS})
    good = verdicts(_cmp({t: 0.1 for t in TESTS}), tail)
    bad = verdicts(_cmp({t: 0.5 for t in TESTS}, boot={t: np.full(200, 0.5) for t in TESTS}), tail)
    ranking = choose_better_arm({"bad": bad, "good": good})
    assert [r[0] for r in ranking] == ["good", "bad"]
    assert ranking[0][1] == 6 and ranking[1][2] == 6


def test_bootstrap_is_seeded_shared_and_size_checked():
    b1 = Bootstrap(np.random.SeedSequence(ROUND2_ROOT_SEED), 50)
    b2 = Bootstrap(np.random.SeedSequence(ROUND2_ROOT_SEED), 50)
    d1, d2 = b1.get("holdout", 20), b2.get("holdout", 20)
    assert all(np.array_equal(x, y) for x, y in zip(d1, d2, strict=True))
    assert b1.get("holdout", 20) is d1  # shared by key (joint bootstrap)
    with pytest.raises(ValueError):
        b1.get("holdout", 21)
    # round-2 compatibility: identical to np.random.default_rng(20261015) draws
    ref = np.random.default_rng(ROUND2_ROOT_SEED)
    assert np.array_equal(
        Bootstrap(np.random.SeedSequence(ROUND2_ROOT_SEED), 1).get("k", 20)[0], ref.integers(0, 20, 20)
    )


def _fs(i: int, v: float) -> FlightStats:
    return FlightStats(flight_id=f"f{i}", air_frac=1.0, b2=np.full(20, v), b3_steps=np.zeros((0, 3)))


def test_run_battery_guards_protocol():
    H = [_fs(i, 0.0) for i in range(4)]
    P = [_fs(i, 0.25) for i in range(4)]
    with pytest.raises(ValueError, match="unequal"):
        run_battery(H, P[:3], [0, 1], [2, 3], {}, Bootstrap(np.random.SeedSequence(1), 10))
    used = Bootstrap(np.random.SeedSequence(1), 10)
    used.get("x", 4)
    with pytest.raises(ValueError, match="fresh"):
        run_battery(H, P, [0, 1], [2, 3], {}, used)
    with pytest.raises(ValueError, match="paired"):
        run_battery(H, P, [0, 1], [2, 3], {"a": H[:3]}, Bootstrap(np.random.SeedSequence(1), 10))
    rep = run_battery(H, P, [0, 1], [2, 3], {"same": H}, Bootstrap(np.random.SeedSequence(1), 10))
    assert rep.d_tail["B2"].D == pytest.approx(0.25)
    assert rep.arms["same"].d_sim["B2"].D == 0.0
    assert rep.arms["same"].verdicts["B2"].verdict == "PASS"
    assert rep.n_flights["holdout"] == 4 and rep.to_dict()["n_boot"] == 10


def test_bootstrap_from_core_rng_is_identity_keyed():
    """Build runs draw the bootstrap from the declared validation.bootstrap stream (phalanx.core.rng)."""
    from phalanx.core.rng import RngService, StreamRegistry, UndeclaredStreamError
    from phalanx.validation.battery import BOOTSTRAP_STREAM

    svc = RngService(0xABC, StreamRegistry([BOOTSTRAP_STREAM]))
    a = Bootstrap.from_service(svc, "proxy_gate.s20", 20).get("holdout", 10)
    b = Bootstrap.from_service(svc, "proxy_gate.s20", 20).get("holdout", 10)
    c = Bootstrap.from_service(svc, "proxy_gate.full", 20).get("holdout", 10)
    assert all(np.array_equal(x, y) for x, y in zip(a, b, strict=True))
    assert not all(np.array_equal(x, y) for x, y in zip(a, c, strict=True))
    src = Bootstrap.from_service(svc, "proxy_gate.s20", 5).source
    assert src["mode"] == "phalanx.core.rng" and src["bit_generator"] == "Philox"
    with pytest.raises(UndeclaredStreamError):
        Bootstrap.from_service(RngService(0xABC, StreamRegistry()), "x", 5)
