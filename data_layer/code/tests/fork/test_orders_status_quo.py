"""A3: the status-quo reference policy, acting only through the orders channel on what it can observe,
reproduces the open-loop KPIs exactly.

Open loop: M18's built-in maintenance control takes the status-quo cannibalisation decisions from its tech
log. Closed loop: the built-in CANN is switched off and ``StatusQuoPolicy`` issues CANNIBALISE orders at the
same decision epochs from a fleet view rebuilt from ``maint.records`` ``as_of`` the epoch (no truth). Same
seeds, same exogenous future (CRN). Sample: one 6-tail fleet over 120 days (n = 1 paired run; the comparison
is exact, so one run with a non-trivial number of cannibalisations answers it), plus a negative control.
"""

from __future__ import annotations

import pytest
from test_fork_fixture_fleet import DAY, FixtureFleetBuilder

from phalanx.fork.service import BranchSpec, ForkService
from phalanx.fork.session import OpsSession
from phalanx.maintenance.world import InternalPolicy
from phalanx.orders.policies import PolicyContext, StatusQuoPolicy, fleet_view_from_records

ROOT = 0xBEEF
N_TAILS, DAYS = 6, 120


def _run(internal: InternalPolicy, policy):
    b = FixtureFleetBuilder(n_tails=N_TAILS, horizon_days=DAYS, internal=internal)
    s = OpsSession(b, ROOT)
    return ForkService(b, b.m18_cfg).run(
        s.snapshot(), BranchSpec("x", policy=policy), DAYS * DAY, keep_session=True
    )


@pytest.mark.fork
def test_status_quo_policy_reproduces_open_loop_kpis():
    open_loop = _run(InternalPolicy(cann=True), None)
    closed = _run(InternalPolicy(cann=False), StatusQuoPolicy())
    assert open_loop.kpis.cann >= 3, "the comparison must exercise the decision (cannibalisations happened)"
    issued = [r for r in closed.submissions if r.verdict == "ACCEPTED"]
    assert len(issued) == open_loop.kpis.cann
    assert closed.kpis == open_loop.kpis

    # every availability bin is identical, not just the totals
    def bins(r):
        return [
            (x["tail_no"], x["t_event"], x["record_version"], x["availability_state"])
            for x in r.session.records("maint.records")
            if x["record_type"] == "AVAILABILITY_STATE"
        ]

    assert bins(open_loop) == bins(closed)


@pytest.mark.fork
def test_negative_control_without_the_policy_the_kpis_differ():
    """Switching the built-in CANN off without a policy taking over changes the outcome, so the A3 equality
    above is not trivially true."""
    open_loop = _run(InternalPolicy(cann=True), None)
    no_decisions = _run(InternalPolicy(cann=False), None)
    assert no_decisions.kpis.cann == 0 and no_decisions.kpis != open_loop.kpis


@pytest.mark.fork
def test_records_view_equals_the_tech_log_view_at_every_epoch():
    """The policy's view (rebuilt from records as of the epoch) equals M18's internal view (n = 30 epochs)."""
    b = FixtureFleetBuilder(n_tails=N_TAILS, horizon_days=40)
    s = OpsSession(b, ROOT)
    m18 = s.system.modules["m18"]
    for t in b.calendar.epochs(0, 30 * DAY):
        s.run_until(t)
        from phalanx.maintenance.docstate import Cow
        from phalanx.maintenance.world import _Ctx

        internal = m18.fleet_view(_Ctx(m18, Cow(s.world.states["m18"]), t))
        observed = fleet_view_from_records(s.obs.as_of(s.t_utc, "maint.records"), s.t_utc)
        assert observed.awp == internal.awp
        assert observed.tails == internal.tails
        ctx = PolicyContext(
            t_utc=s.t_utc, catalogue=b.m18_cfg.catalogue, cann_min_awp_s=b.m18_cfg.cann_min_awp_s
        )
        assert all(o.action == "CANNIBALISE" for o in StatusQuoPolicy().decide(s.obs, ctx))
