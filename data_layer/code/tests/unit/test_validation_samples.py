"""A5: the sample selector is deterministic (phalanx.core.rng streams) and records n and its justification."""

from __future__ import annotations

import json

import pytest

from phalanx.core.rng import RngService, StreamRegistry, UndeclaredStreamError
from phalanx.validation.samples import (
    SAMPLE_STREAM,
    load_sample,
    population_sha256,
    save_sample,
    select_flights,
    temporal_halves,
)

pytestmark = pytest.mark.unit
POP = [f"f{i:03d}" for i in range(50)]
ROOT = 0x5048414C414E58_20261014


def _rng(root: int = ROOT) -> RngService:
    return RngService(root, StreamRegistry([SAMPLE_STREAM]))


def _sel(pop=POP, n=10, rng=None, scenario="w05.unit", index=0):
    return select_flights(
        pop, n, rng=rng or _rng(), scenario=scenario, index=index, purpose="p", justification="j"
    )


def test_build_selection_is_deterministic_and_order_invariant():
    a = _sel()
    b = _sel(pop=list(reversed(POP)))
    assert a.flights == b.flights and len(a.flights) == 10 and list(a.flights) == sorted(a.flights)
    assert set(a.flights) <= set(POP)
    assert a.source["mode"] == "phalanx.core.rng" and a.source["bit_generator"] == "Philox"
    assert a.source["path"] == "scenario=s:w05.unit/subsystem=s:validation/component=s:flight_sample"


def test_identity_keys_give_independent_samples():
    """Another campaign, index or root draws another sample (identity-keyed, not order-keyed)."""
    a = _sel()
    assert _sel(scenario="w05.other").flights != a.flights
    assert _sel(index=1).flights != a.flights
    assert _sel(rng=_rng(ROOT + 1)).flights != a.flights
    svc = _rng()  # drawing other selections first does not change a selection (no hidden draw counter)
    _sel(rng=svc, scenario="w05.other")
    _sel(rng=svc, index=5)
    assert _sel(rng=svc).flights == a.flights


def test_undeclared_stream_is_refused():
    with pytest.raises(UndeclaredStreamError):
        _sel(rng=RngService(ROOT, StreamRegistry()))


def test_sample_records_n_justification_population_and_source(tmp_path):
    s = select_flights(
        POP,
        5,
        rng=_rng(),
        scenario="w05.smoke",
        purpose="smoke",
        justification="1-3 sorties smoke rule (RULES.md rule 1)",
    )
    p = tmp_path / "sample.json"
    save_sample(s, p)
    d = json.loads(p.read_text())
    assert d["n"] == 5 and d["justification"].startswith("1-3") and d["population_size"] == 50
    assert d["population_sha256"] == population_sha256(POP)
    assert d["source"]["root_hex"] == f"{ROOT:032x}" and d["source"]["index"] == 0
    assert load_sample(p) == s


def test_round2_compat_mode_is_explicit():
    r2 = select_flights(POP, 5, entropy=[20261015, 99], purpose="p", justification="j")
    assert r2.source == {
        "mode": "round2_compat",
        "bit_generator": "PCG64",
        "entropy": [20261015, 99],
        "spawn_key": [],
    }
    with pytest.raises(ValueError, match="either"):
        select_flights(POP, 5, rng=_rng(), scenario="x", entropy=1, purpose="p", justification="j")
    with pytest.raises(ValueError, match="either"):
        select_flights(POP, 5, purpose="p", justification="j")


def test_selection_rejects_missing_justification_bad_n_and_duplicates():
    with pytest.raises(ValueError, match="justification"):
        select_flights(POP, 5, rng=_rng(), scenario="x", purpose="p", justification="  ")
    with pytest.raises(ValueError):
        select_flights(POP, 51, rng=_rng(), scenario="x", purpose="p", justification="j")
    with pytest.raises(ValueError, match="duplicate"):
        select_flights([*POP, "f000"], 5, rng=_rng(), scenario="x", purpose="p", justification="j")
    with pytest.raises(ValueError, match="scenario"):
        select_flights(POP, 5, rng=_rng(), purpose="p", justification="j")


def test_temporal_halves_split_at_median_date():
    flights = [f"x{i}" for i in range(7)]
    dates = {f: f"2001-0{1 + (6 - i) % 7}-01" for i, f in enumerate(flights)}
    early, late = temporal_halves(flights, dates)
    assert len(early) == len(late) == 3 and not set(early) & set(late)
    assert max(dates[f] for f in early) < min(dates[f] for f in late)
