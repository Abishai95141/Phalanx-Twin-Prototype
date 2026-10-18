"""Public API: load_dictionary and Dictionary lookups (by param, LRU, bus address, rate group; versions;
ParamSet).

Sample: the Tejas dictionary; each lookup is cross-checked against an independent scan of the compiled
content.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

from phalanx.core.module import ParamSet
from phalanx.dictionary import Dictionary, compile_bundle, load_bundle, load_dictionary
from phalanx.dictionary.yamlio import load_yaml

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"


@lru_cache(maxsize=1)
def _d() -> Dictionary:
    return Dictionary(compile_bundle(load_bundle(CONFIG)))


def test_identity_accessors():
    d = _d()
    assert d.platform == "tejas"
    assert d.dict_version == "0.1.3"
    assert len(d.dict_hash) == 64
    assert "SYNTHETIC" in d.synthetic_label
    assert load_dictionary().dict_hash == d.dict_hash
    assert load_dictionary(CONFIG).dict_hash == d.dict_hash


def test_lookup_by_param_and_measurand():
    d = _d()
    ids = [c["channel_id"] for c in d.channels_for_param("ENG.N1")]
    assert ids == ["ENG.N1.A", "ENG.N1.B", "ENG.N1.V"]
    assert [c["channel_id"] for c in d.channels_for_measurand("ENG.N1")] == ids
    assert d.channel("ENG.N1.V")["inputs"] == ("ENG.N1.A", "ENG.N1.B")
    assert d.param("ENG.N1")["evidence"]["core_tag"].startswith("TRANSFER: ")
    with pytest.raises(KeyError):
        d.channel("ENG.N9")


def test_lookup_by_lru_matches_a_scan():
    d = _d()
    for lru in ("FADEC", "BHEEM_EU", "DFCC", "GROUND"):
        expected = {
            c["channel_id"]
            for c in d.channels()
            if lru in (c["source_lru"], c["acq_lru"], c["transport"].get("rt_lru"))
        }
        assert {c["channel_id"] for c in d.by_lru(lru)} == expected, lru
    with pytest.raises(KeyError):
        d.by_lru("NOPE")


def test_lookup_by_rate_group_and_stage():
    d = _d()
    bus25 = {c["channel_id"] for c in d.by_rate_group("AV25", stage="bus")}
    assert bus25 == {c["channel_id"] for c in d.channels() if c["rates"]["bus"] == "AV25"}
    cdr16 = {c["channel_id"] for c in d.by_rate_group("CDR16", stage="record")}
    assert "FCS.VOTED.Q" in cdr16
    assert all(any(s["group"] == "CDR16" for s in d.channel(c)["sinks"]) for c in cdr16)
    assert d.rate_hz("AV12.5") == 12.5
    assert d.acquisition_rate_hz("ENG.N1.A") == 60  # FADEC-INT nominal
    assert d.acquisition_rate_hz("FUEL.QTY.TANK.F1") == 40  # LRU-INT -> ECFM-C frame


def test_units_map_for_the_fast_path():
    d = _d()
    um = d.units_map()
    assert um["ENG.N1"] == "percent"
    assert um["ELEC.TRU.VI.TRU1.VOLT"] == "V"
    assert set(um) == set(d.measurand_ids())
    for m, units in um.items():
        assert {c["units"] for c in d.channels_for_measurand(m)} == {units}  # one unit per measurand


def test_dictionary_is_read_only():
    d = _d()
    ch = d.channel("ENG.N1.V")
    with pytest.raises(TypeError):
        ch["units"] = "rpm"  # type: ignore[index]
    with pytest.raises(TypeError):
        ch["range"]["max"] = 1  # type: ignore[index]
    with pytest.raises(AttributeError):
        ch["inputs"].append("x")  # type: ignore[attr-defined]


def test_param_set_is_a_core_paramset_in_si():
    d = _d()
    ps = d.param_set("channel_reference")
    assert isinstance(ps, ParamSet)
    assert ps["n1_100pct"].unit == "radian / second"
    assert ps.value("n1_100pct") == pytest.approx(13270 * 2 * 3.141592653589793 / 60)
    assert ps.value("nz_envelope_max") == pytest.approx(8 * 9.80665)
    assert str(ps["n1_100pct"].tag) == "TRANSFER: F404-400"
    assert d.param_set("channel_reference").hash == ps.hash  # deterministic


def test_field_evidence_resolves_to_parsable_tags():
    d = _d()
    ev = d.field_evidence("ENG.N1.V", "recorder_lsb")
    assert ev["ref"] == "R-LSB-DASHLINK" and ev["tag"] == "ASSUMPTION" and not ev["proxy"]
    inv = d.field_evidence("ENG.N1.V", "range")
    assert inv["ref"] == "inv" and inv["tag"].startswith("TRANSFER: ")
    assert d.field_evidence("FTI.ALL", "transport")["proxy"] is True


def test_by_bus_address_requires_an_address():
    with pytest.raises(ValueError):
        _d().by_bus_address("AV-MUX-2")


def test_missing_path_raises():
    with pytest.raises(FileNotFoundError):
        load_dictionary(Path("/nonexistent/dictionary.json"))


def test_contract_locations_match_the_w04_contract_patterns():
    """Every channel's contract identity fits the W0.4 param.samples field patterns (fast and full path)."""
    spec = load_yaml(REPO / "src/phalanx/dictionary/contract/spec/v0/topics/param.samples.yaml")
    patterns = {f["name"]: f["pattern"] for f in spec["fields"] if isinstance(f, dict) and "pattern" in f}
    assert {"source_lru", "lane", "rt_sa_word", "label_sdi"} <= set(patterns)
    d = _d()
    seen = {"rt_sa_word": 0, "label_sdi": 0}
    for cid in d.channel_ids():
        loc = d.contract_location(cid)
        assert re.fullmatch(r"\S+", loc["param_id"]), cid
        for name in ("source_lru", "lane", "rt_sa_word", "label_sdi"):
            if loc[name] is not None:
                assert re.fullmatch(patterns[name], loc[name]), (cid, name, loc[name])
                seen[name] = seen.get(name, 0) + 1
    assert seen["rt_sa_word"] == 276 and seen["label_sdi"] == 8
    n1 = d.channel("ENG.N1.V")["transport"]
    assert d.contract_location("ENG.N1.V")["rt_sa_word"] == f"RT05/SA01/W{n1['word'] - 1:02d}"
    locs = [d.contract_location(c)["rt_sa_word"] for c in d.channel_ids()]
    on_bus = [x for x in locs if x is not None]
    assert len(on_bus) == len(set(on_bus))  # 0-based index keeps every 1553 location unique
    assert d.contract_location("NAV.RADALT")["label_sdi"] == "L100/SDI0"
    assert d.contract_location("ENG.T5")["lane"] is None
