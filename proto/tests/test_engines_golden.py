"""Phase 1-B engines against the film's 22 Jun values (DEVELOPMENT.md §5.1, §5.3).

Every difference from the film is written down in ``proto/ground/triage/golden-22jun.md`` with its reason; the
assertions below are the values our engines compute, next to the film's in comments.

    python -m pytest proto/tests/test_engines_golden.py -q
"""

from __future__ import annotations

import datetime as dt
import sys
import time
from pathlib import Path

import pytest

PROTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROTO / "ground"))

from engines import cnd, drift, episodes, isolation, leadtime, life, similar
from engines.common import MODELS, context
from interfaces import NS, Source, Tier
from store import Store
from twin import Twin

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
T = int(dt.datetime(2026, 6, 22, 6, 0, tzinfo=IST).timestamp()) * NS


@pytest.fixture(scope="module")
def world():
    store = Store.for_preview()
    twin = Twin(store)
    return store, twin, context(store, twin, T)


def test_funnel(world):
    _, _, ctx = world
    f = episodes.funnel(ctx)
    assert (f["alert_rows"], f["bit_rows"], f["caution_rows"]) == (1192, 921, 271)
    assert f["occurrences"] == 921  # every caution shares its event_id with a BIT row (D2)
    assert (f["issues"], f["open"]) == (326, 33)
    assert f["suppressed"] == 0  # D6 inhibition removes none on 22 Jun (as the film found)


def test_tj107_hyd101_issue(world):
    _, _, ctx = world
    ep = next(e for e in episodes.open_episodes(ctx) if e.issue_id == "TJ107-HYD-101")
    assert ep.severity == "CAUTION" and ep.n == 43
    assert ctx.consecutive("TJ107", "HYD-101") == 34
    rec = episodes.recent_occurrences(ctx, ep)
    assert rec.sortie_id.nunique() == 6  # the six occurrences the film's orders cite
    so = set(ctx.sorties("TJ107").sortie_id)
    assert (len(ctx.fired_sorties("TJ107", "HYD-101") & so), len(so)) == (59, 61)


def test_cnd_hyd101(world):
    _, _, ctx = world
    r = cnd.code_rates(ctx, "HYD-101")
    # film: 107 jobs (71 CND, 35 R/R, 1 TS), 0 confirmed — not reproducible with (tail, job) keys; see golden-22jun.md
    assert (r.jobs, r.closed, r.no_fault, r.removed, r.pending) == (121, 120, 85, 35, 2)
    assert (r.confirmed, r.labelled) == (0, 118)
    assert [round(x, 3) for x in r.p_confirmed] == [0.004, 0.0, 0.021]  # film 0.005 [0.000, 0.023] (n 107)
    assert (r.units_rtok, r.units_benched) == (33, 33)  # film: 33 of 33 pumps RTOK
    assert round(r.p_rtok[0], 3) == 0.986 and [round(x, 2) for x in r.p_rtok[1:]] == [0.93, 1.0]  # film 0.985 [0.93, 1.00]
    h = cnd.issue_history(ctx, "TJ107", "HYD-101")
    assert (h["jobs"], h["man_hours"], h["actions"]["AT-CND"], h["actions"]["AT-RR"]) == (63, 792.3, 33, 29)


def test_cnd_champion_stays(world):
    _, _, ctx = world
    c = cnd.challenger(ctx)
    assert (c.n_train, c.n_test) == (449, 139)  # identical to the film's assurance run
    assert (c.brier_champion, c.brier_challenger) == (0.1008, 0.1072)
    assert c.champion == "per-code base rate"  # §5.3: the learned challenger does not beat it


def test_isolation_tj107(world):
    _, _, ctx = world
    r = isolation.analyse(ctx, "TJ107", "HYD-101")
    assert round(r.posterior["IND"], 2) == 0.56 and round(r.posterior["AMAGB"], 2) == 0.44
    assert r.posterior["HYD_PUMP"] < 1e-4  # §5.1: pump < 0.0001 at the central assumptions
    assert r.hi["HYD_PUMP"] < 1e-3  # worst of the 30 (d × leak) settings: 0.0002
    assert r.bench["HYD_PUMP"] == (27, 0)  # TJ107's own pumps benched under HYD-101 jobs (film: 28 matched)
    best = r.tests[0]
    assert (best.test.name, best.test.mh, best.best_in, r.settings) == ("Indication-path isolation", 7.3, 19, 24)
    assert [(x.test.id, x.test.mh, x.best_in) for x in r.tests] == [("T1", 7.3, 19), ("T2", 8.3, 5), ("T3", 18.7, 0)]


def test_isolation_any_issue(world):
    _, _, ctx = world
    n = 0
    for ep in episodes.open_episodes(ctx):
        r = isolation.analyse(ctx, ep.tail_no, ep.code)
        if ep.suspects:
            assert r is not None and abs(sum(r.posterior.values()) - 1) < 1e-9
            n += 1
            if len(ctx.code_jobs(ep.code)):  # a code with job history gets ranked tests
                assert r.tests and all(x.test.mh > 0 for x in r.tests), ep.issue_id
    assert n == 33  # every open issue's code has suspect LRUs


def test_similar_tj107(world):
    _, _, ctx = world
    c = similar.cases(ctx, "TJ107-HYD-101")[0]
    assert (c.issue_id, c.n_alerts, c.confirmed_units) == ("TJ102-HYD-101", 24, 0)  # film: TJ102 · 24 flights since 9 Apr
    assert dt.datetime.fromtimestamp(c.first / NS, IST).strftime("%d %b") == "09 Apr"


def test_leadtime(world):
    _, _, ctx = world
    lt = leadtime.fit(ctx)
    assert (lt.closed, lt.closed_median, lt.closed_p90) == (127, 4.6, 38.3)  # §5.1
    assert (lt.n, lt.censored, lt.orphan, lt.km_median, lt.km_p90) == (146, 19, 28, 5.8, 91.6)  # film assurance run
    assert leadtime.predict(ctx, "SYN-PN-TYRE", "AOG") == (4.7, 54.8)
    assert leadtime.predict(ctx, "SYN-PN-CHUTE", "AOG") == (27.9, 326.9)


def test_life(world):
    _, _, ctx = world
    it = {(x.tail_no, x.part_no): x for x in life.items(ctx)}
    ty = it[("TJ105", "SYN-PN-TYRE")]
    assert (ty.used, ty.limit, ty.left, ty.fitted, round(ty.rate_per_day, 2)) == (7, 8, 1, 2, 0.87)  # TJ105 at 7 of 8
    assert (it[("TJ105", "SYN-PN-CHUTE")].used, it[("TJ105", "SYN-PN-CHUTE")].limit) == (31, 45)  # film: 31 streamings
    assert all(x.left > 0 for x in it.values())  # no item past its limit on 22 Jun


def test_drift(world):
    _, _, ctx = world
    s = {x.series: x for x in drift.scans(ctx)}
    fleet = s["fleet"]
    assert (fleet.weeks, fleet.glr, fleet.p_value) == (24, 1.08, 0.625)  # film: GLR 1.08, week of 18 May, p 0.625
    assert dt.datetime.fromtimestamp(fleet.split_start / NS, IST).strftime("%d %b") == "18 May"
    assert not any(x.alert for x in s.values())  # §5.3: no alert outside known change points


@pytest.mark.parametrize("mod", [episodes, cnd, isolation, similar, leadtime, life, drift])
def test_findings_carry_provenance(world, mod):
    store, twin, ctx = world
    ids = {v for v in MODELS.values()}
    ing = ctx.ingest_of_rid
    any_tail: dict[str, int] = {}
    for (_, rid), ti in ing.items():
        any_tail[rid] = min(ti, any_tail.get(rid, ti))
    fs = mod.run(store, twin, T)
    assert fs
    for f in fs:
        assert isinstance(f.tier, Tier) and f.reason and f.reason.endswith(".")
        for b in f.beliefs:
            assert (b.model_id, b.model_version) in ids and b.source == Source.FLEET
        for e in f.evidence:  # every cited record exists and was ingested by the snapshot
            ti = ing.get((f.tail_no, e.hex())) if f.tail_no else any_tail.get(e.hex())
            assert ti is not None and ti <= T, (f.engine, f.subject, e.hex())


def test_engines_runtime():
    """NFR-03: engines per epoch ≤ 20 s (fresh store and context)."""
    store = Store.for_preview()
    twin = Twin(store)
    t0 = time.perf_counter()
    for mod in (episodes, cnd, isolation, similar, leadtime, life, drift):
        mod.run(store, twin, T)
    assert time.perf_counter() - t0 < 20
