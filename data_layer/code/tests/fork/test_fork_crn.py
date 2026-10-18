"""A5 common random numbers (I8) and the variance benefit of CRN-paired comparisons.

- CRN audit: two branches from one snapshot with different order suffixes consume identity-keyed draws; draws
  for a shared identity are identical (failure thresholds per serial and life, sortie plans per tail and
  date); the audit sees the decision-caused divergence (the grounded tail's sorties) as consumption
  differences only.
- Variance (A5, E1-HY item 8): the variance of CRN-paired KPI differences is below that of independent-seed
  differences, as a one-sided **F-test** on disjoint member sets (independent variance estimates). The
  former check (``var_p < var_i`` on n = 6 pairs sharing their treatment runs) passed with CRN broken (E1
  verifier §2): at a true ratio of ~2 and 5 degrees of freedom it is close to a coin flip.
  Design, stated before running (pilots on members 10000+, 20000+ and 30000+, disjoint from the test's):
  the MC-difference variance ratio var_indep / var_paired was 2.08 (n = 120 disjoint pairs; 90 % CI
  1.54-2.82), 2.22 (n = 60) and 2.49 (n = 150); design ratio rho = 2.0. Level alpha = 0.01 (the chance the
  test passes with CRN broken), power 0.95 at rho = 2.0 -> n = 134 differences per arm (F(133, 133)), i.e.
  536 branch runs of 20 days on the 4-tail fixture fleet (about 55 s, so ``slow``; run by ``make test``).
  ``make check`` keeps the fast CRN-sensitive check: the n = 6 paired CI of the grounding effect excludes 0
  (it fails with CRN broken).
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from scipy import stats
from test_fork_fixture_fleet import DAY, EPOCH, FixtureFleetBuilder

from phalanx.core.rng import DrawLedger, crn_audit
from phalanx.fork.service import BranchSpec, ForkService, member_root, paired_difference
from phalanx.fork.session import OpsSession
from phalanx.orders.model import Order

ROOT = 0xC2C2


def _thresholds(session) -> dict[tuple[str, int], float]:
    doc = json.loads(np.asarray(session.world.states["m10"]["doc"]).tobytes().decode("ascii"))
    return {(sn, int(s["life"])): float(s["th"]) for sn, s in doc["ser"].items()}


def _snap(n_tails=4, t=30 * DAY):
    b = FixtureFleetBuilder(n_tails=n_tails, horizon_days=90)
    s = OpsSession(b, ROOT)
    s.run_until(t)
    return b, s.snapshot()


def _ground(b, t_kernel, tail, days):
    t1 = b.calendar.next_epoch(t_kernel + days * DAY)
    return [
        Order(
            "G-1",
            "H",
            "HUMAN",
            EPOCH + t_kernel,
            EPOCH + t_kernel,
            "GROUND",
            {"reason": "what-if"},
            target_tail_no=tail,
        ),
        Order("R-1", "H", "HUMAN", EPOCH + t1, EPOCH + t1, "RELEASE", {}, target_tail_no=tail),
    ]


@pytest.mark.fork
def test_crn_audit_shared_identities_draw_identical_values():
    b, snap = _snap()
    fs = ForkService(b, b.m18_cfg)
    la, lb = DrawLedger(), DrawLedger()
    t = b.calendar.next_epoch(snap.t)
    sa = fs.fork(snap, BranchSpec("a"), ledger=la)
    sb = fs.fork(snap, BranchSpec("b"), ledger=lb)
    for s, orders in ((sa, []), (sb, _ground(b, t, b.tails[0], 5))):
        for o in orders:
            s.run_until(o.t_issued - EPOCH)
            s.submit([o])
        s.run_until(snap.t + 20 * DAY)
    rep = crn_audit(la, lb)
    assert rep.values_differ == ()
    assert len(rep.identical) > 10
    grounded = [p for p in rep.diverged() if b.tails[0] in p]
    assert grounded, "the grounded tail's sorties diverge (decision-caused), and the audit sees it"
    # exogenous outcome identity: a serial's failure threshold for a given life is the same in both branches
    ta, tb = _thresholds(sa), _thresholds(sb)
    shared = sorted(set(ta) & set(tb))
    assert len(shared) > 50 and all(ta[k] == tb[k] for k in shared)


@pytest.mark.fork
def test_negative_control_a_different_root_changes_the_exogenous_draws():
    """Same identity, same root -> same draw (oracle fork); same identity, derived root -> a different
    draw."""
    b, snap = _snap()
    fs = ForkService(b, b.m18_cfg)
    so, so2 = fs.fork(snap, BranchSpec("o")), fs.fork(snap, BranchSpec("o2"))
    se = fs.fork(snap, BranchSpec("e", mode="ensemble", member=0))
    assert se.root == member_root(snap.root, b.scenario, 0) != snap.root

    def draw(s):
        m02 = s.system.modules["m02"]
        return float(m02.stream("sortie", tail=b.tails[1], date="2026-11-02").generator(0).random())

    assert draw(so) == draw(so2) != draw(se)
    so.run_until(snap.t + 20 * DAY)
    se.run_until(snap.t + 20 * DAY)
    assert so.log.digest != se.log.digest


F_ALPHA, F_POWER, F_RHO_DESIGN, F_N = 0.01, 0.95, 2.0, 134  # design: module docstring


def _mc(fs, snap, branch, member, orders=()):
    spec = BranchSpec(branch, orders=orders, mode="ensemble", member=member)
    return fs.run(snap, spec, 20 * DAY).kpis.mc


@pytest.mark.fork
def test_paired_ci_resolves_the_grounding_effect():
    """Fast CRN-sensitive check (n = 6 CRN pairs, 20 days): grounding a tail for 4 days lowers MC and the
    paired 95 % CI resolves it. With CRN broken the pairs are independent and the n = 6 CI no longer
    excludes 0 (E1 verifier §2; E1-HY mutant run). The variance claim itself is the slow F-test below."""
    b, snap = _snap()
    fs = ForkService(b, b.m18_cfg)
    n = 6
    ground = _ground(b, b.calendar.next_epoch(snap.t), b.tails[0], 4)
    base = np.array([_mc(fs, snap, "base", m) for m in range(n)])
    trt = np.array([_mc(fs, snap, "trt", m, ground) for m in range(n)])
    d = paired_difference("mc", trt, base, level=0.95, paired=True)
    assert d.n == n and d.ci_high < 0  # grounding a tail lowers MC, and the paired CI resolves it


@pytest.mark.unit
def test_f_test_design_has_the_stated_power():
    """The stated n gives power >= 0.95 at the design ratio and level 0.01; one fewer than the minimal n
    would not (so n is the power-justified minimum, not padding)."""

    def power(n):
        return stats.f.sf(stats.f.isf(F_ALPHA, n - 1, n - 1) / F_RHO_DESIGN, n - 1, n - 1)

    assert power(F_N) >= F_POWER > power(F_N - 1)


@pytest.mark.fork
@pytest.mark.slow
def test_paired_difference_variance_below_independent_seed_variance():
    """A5 as a one-sided F-test (design in the module docstring): H0 var_paired >= var_indep is rejected at
    alpha = 0.01. Paired differences use members 0..133 (treatment and base share the member root);
    independent differences use treatment members 134..267 against base members 268..401 (no shared
    roots), so the two variance estimates are independent and the ratio is F(133, 133) under H0."""
    b, snap = _snap()
    fs = ForkService(b, b.m18_cfg)
    n = F_N
    ground = _ground(b, b.calendar.next_epoch(snap.t), b.tails[0], 4)
    paired = np.array([_mc(fs, snap, "trt", m, ground) - _mc(fs, snap, "base", m) for m in range(n)])
    indep = np.array(
        [_mc(fs, snap, "trt", n + m, ground) - _mc(fs, snap, "base", 2 * n + m) for m in range(n)]
    )
    var_p, var_i = float(paired.var(ddof=1)), float(indep.var(ddof=1))
    ratio = var_i / var_p
    p = float(stats.f.sf(ratio, n - 1, n - 1))
    assert p < F_ALPHA, (var_p, var_i, ratio, p)
