"""M22 fork modes: belief forks resample hidden state from observations only; ensemble members share the past
and differ in the future; the what-if API returns CRN-paired differences with CIs.

Sample: one 5-tail fleet, snapshot at day 30, 20-day horizons; what-if with n = 3 replicate pairs (API check).
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from test_fork_fixture_fleet import DAY, FixtureFleetBuilder

from phalanx.fork.belief import SurvivalPosterior, observed_item_hours
from phalanx.fork.service import BranchSpec, ForkService, member_root
from phalanx.fork.session import OpsSession
from phalanx.maintenance.docstate import Cow
from phalanx.orders.policies import ConditionBasedPolicy, StatusQuoPolicy

ROOT = 0xBE11


def _snap():
    b = FixtureFleetBuilder(n_tails=5, horizon_days=80)
    s = OpsSession(b, ROOT)
    s.run_until(30 * DAY)
    return b, s.snapshot()


def _fixture_doc(session):
    return json.loads(np.asarray(session.world.states["m10"]["doc"]).tobytes().decode("ascii"))


@pytest.mark.fork
def test_belief_fork_resamples_hidden_state_from_observations_only():
    b, snap = _snap()
    fs = ForkService(b, b.m18_cfg)
    post = SurvivalPosterior("m10")
    oracle = fs.fork(snap, BranchSpec("o"))
    belief = fs.fork(snap, BranchSpec("b", mode="belief", belief=post, member=0))
    do, db = _fixture_doc(oracle), _fixture_doc(belief)
    tracked = sorted(set(do["inst"].values()))
    assert sum(do["ser"][sn]["th"] != db["ser"][sn]["th"] for sn in tracked) > len(tracked) // 2
    # the posterior conditions on survival: every resampled threshold exceeds the observed usage
    assert all(db["ser"][sn]["th"] > db["ser"][sn]["u"] for sn in tracked)
    # the past (records, observations) is shared with the oracle
    assert belief.log.digest == oracle.log.digest
    # invariance: perturb the hidden truth of the snapshot world -> the posterior draws do not move
    e1 = fs.fork(snap, BranchSpec("e1", mode="ensemble", member=0))
    e2 = fs.fork(snap, BranchSpec("e2", mode="ensemble", member=0))
    p0 = post.draws(e1, particle=3)
    cow = Cow(e2.world.states["m10"])
    for sn in tracked:
        cow.doc("doc")["ser"][sn]["th"] *= 1.7
        cow.doc("doc")["ser"][sn]["u"] *= 0.3
    cow.touch("doc")
    e2.world.states["m10"] = cow.commit()
    assert post.draws(e2, particle=3) == p0
    assert post.draws(e2, particle=4) != p0  # particles differ
    # unknown latent faults are not assumed in the belief world
    known = belief.system.modules["m18"].belief_known_faults(belief.world.states["m18"])
    assert all(s["fault"] is None or s["fault"] in known for s in db["ser"].values())
    res = fs.run(snap, BranchSpec("b", mode="belief", belief=post, member=1), 20 * DAY)
    assert 0.0 <= res.kpis.mc <= 1.0


@pytest.mark.fork
def test_observed_item_hours_come_from_records():
    b, snap = _snap()
    s = OpsSession.restore(b, snap)
    rows = s.obs.as_of(s.t_utc, "maint.records").to_pylist()
    hours = observed_item_hours(rows, s.t_utc)
    fleet_fh = sum(r["flight_hours"] for r in rows if r["record_type"] == "SORTIE")
    eng = [h for sn, h in hours.items() if sn.startswith("ENG-")]
    assert eng and max(eng) <= fleet_fh + 1e-9 and sum(eng) > 0


@pytest.mark.fork
def test_ensemble_members_share_the_past_and_differ_in_the_future():
    b, snap = _snap()
    fs = ForkService(b, b.m18_cfg)
    roots = {member_root(snap.root, b.scenario, m) for m in range(4)}
    assert len(roots) == 4 and all(r < 2**128 and r != snap.root for r in roots)
    assert member_root(snap.root, b.scenario, 2) == member_root(snap.root, b.scenario, 2)
    r = [fs.run(snap, BranchSpec("e", mode="ensemble", member=m), 20 * DAY) for m in range(2)]
    assert r[0].record_digest != r[1].record_digest


@pytest.mark.fork
def test_what_if_api_returns_paired_differences_with_cis():
    b, snap = _snap()
    fs = ForkService(b, b.m18_cfg)
    ra, rb, diffs = fs.what_if(
        snap,
        BranchSpec("cbm", policy=ConditionBasedPolicy()),
        BranchSpec("sq", policy=StatusQuoPolicy()),
        20 * DAY,
        replicates=3,
    )
    assert [x.member for x in ra] == [x.member for x in rb] == [0, 1, 2]
    by = {d.kpi: d for d in diffs}
    assert set(by) >= {
        "mc",
        "fmc",
        "flying_task",
        "aog_days",
        "cann_rate",
        "man_hours",
        "cost",
        "in_flight_failures",
    }
    d = by["mc"]
    assert d.n == 3 and d.ci_low <= d.mean <= d.ci_high
    with pytest.raises(ValueError):
        fs.compare(ra, rb[:2])
