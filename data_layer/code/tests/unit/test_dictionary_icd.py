"""SYNTHETIC Phalanx ICD: unique bus addresses, word fit, bit fields, per-RT expansion, lookups (W0.3 A3).

Sample: all 294 recorded channels of the Tejas dictionary (260 1553 data items, 16 status/mode-code words, 8
ARINC-429 labels, 10 FTI PCM words). Collision negatives move one item onto another's address.
"""

from __future__ import annotations

import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import pytest

from phalanx.dictionary import CompileError, Dictionary, compile_bundle, load_bundle
from phalanx.dictionary.icd import icd_csv, icd_markdown, icd_rows

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"


@lru_cache(maxsize=1)
def _bundle():
    return load_bundle(CONFIG)


@lru_cache(maxsize=1)
def _compiled():
    return compile_bundle(_bundle().copy())


def _content():
    return _compiled().content


def _ch(b, sub, pid, cid):
    return b.sources[sub]["parameters"][pid]["channels"][cid]


def test_bus_addresses_unique():
    """Independent re-check: no two 1553 items share a data word; 429 labels and FTI words are unique."""
    words: dict[tuple, str] = {}
    singles: dict[tuple, str] = {}
    msg_len: dict[tuple, set] = defaultdict(set)
    for cid, ch in _content()["channels"].items():
        t = ch["transport"]
        if t["type"] == "mil1553":
            key = (t["bus"], t["rt"], t["tr"], t["sa"])
            msg_len[key].add(t["message_words"])
            assert 1 <= t["sa"] <= 30 and t["word"] + t["words"] - 1 <= t["message_words"] <= 32, cid
            for w in range(t["word"], t["word"] + t["words"]):
                assert (*key, w) not in words, (cid, words.get((*key, w)))
                words[(*key, w)] = cid
            vkey = ("valid", *key, ch["validity"]["word"], ch["validity"]["bit"])
            assert vkey not in singles, cid
            singles[vkey] = cid
            assert ch["validity"]["word"] < t["word"], cid
        elif t["type"] in ("mil1553_status", "mil1553_modecode"):
            key = (t["type"], t["bus"], t["rt"])
            assert key not in singles, cid
            singles[key] = cid
        elif t["type"] == "arinc429":
            key = ("429", t["link"], t["label"], t["sdi"])
            assert key not in singles, cid
            singles[key] = cid
        elif t["type"] == "fti_pcm":
            key = ("fti", t["stream"], t["word"])
            assert key not in singles, cid
            singles[key] = cid
    assert all(len(v) == 1 for v in msg_len.values())
    assert len(words) > 250


def test_rt_addresses_match_the_topology():
    c = _content()
    for cid, ch in c["channels"].items():
        t = ch["transport"]
        if t["type"].startswith("mil1553"):
            bus = c["buses"]["mil1553"][t["bus"]]
            if t["rt"] == 31:
                assert t["tr"] == "R" and t["rt_lru"] == bus["bc"], cid
            else:
                assert bus["rts"][t["rt_lru"]]["address"] == t["rt"], cid


def test_word_collision_fails():
    b = _bundle().copy()
    a = _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.V")["transport"]
    other = _ch(b, "engine.yaml", "ENG.N2", "ENG.N2.V")
    other["transport"] = dict(a)
    with pytest.raises(CompileError, match="collision"):
        compile_bundle(b)


def test_arinc429_label_collision_fails():
    b = _bundle().copy()
    m = _ch(b, "avionics_status.yaml", "CWS.MASTER", "CWS.MASTER")
    legend = _ch(b, "avionics_status.yaml", "CWS.LEGEND", "CWS.LEGEND.A")
    m["transport"]["label"] = legend["transport"]["label"]
    with pytest.raises(CompileError, match="address collision"):
        compile_bundle(b)


def test_fti_word_collision_fails():
    b = _bundle().copy()
    a = _ch(b, "air_data.yaml", "AD.BOOM", "AD.BOOM.ALPHA")
    c = _ch(b, "air_data.yaml", "AD.BOOM", "AD.BOOM.BETA")
    c["transport"]["word"] = a["transport"]["word"]
    with pytest.raises(CompileError, match="address collision"):
        compile_bundle(b)


def test_rt_address_mismatch_fails():
    b = _bundle().copy()
    _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.V")["transport"]["rt"] = 6
    with pytest.raises(CompileError, match="is not the address of FADEC"):
        compile_bundle(b)


def test_duplicate_rt_address_in_topology_fails():
    b = _bundle().copy()
    b.tables["buses"]["mil1553"]["AV-MUX-2"]["rts"]["ECFM_C"]["address"] = 7  # BHEEM_EU's
    with pytest.raises(CompileError, match="RT address 7 used by"):
        compile_bundle(b)


def test_words_fit_range_and_lsb():
    for cid, ch in _content()["channels"].items():
        t, enc = ch["transport"], ch["encoding"]
        if t["type"] == "mil1553":
            assert t["words"] == enc["words"] == math.ceil(enc["word_bits"] / 16), cid
        if t["type"] in ("arinc429", "fti_pcm"):
            assert enc["words"] == 1, cid
            assert enc["word_bits"] == (19 if t["type"] == "arinc429" else 12), cid


def test_bitfield_words_have_unique_bits():
    n = 0
    for cid, ch in _content()["channels"].items():
        enc = ch["encoding"]
        if enc["type"] != "bitfield":
            continue
        n += 1
        used: set[int] = set()
        names = [f["name"] for f in enc["fields"]]
        assert len(names) == len(set(names)), cid
        for f in enc["fields"]:
            bits = set(range(f["lsb_bit"], f["lsb_bit"] + f["width"]))
            assert not bits & used and max(bits) < enc["word_bits"], cid
            used |= bits
    assert n > 60


def test_per_rt_rows_cover_every_rt():
    c = _content()
    rts = {
        (bus, v["address"], lru) for bus, b in c["buses"]["mil1553"].items() for lru, v in b["rts"].items()
    }
    assert len(rts) == 8
    for pid, kind in (("AV.RT.STATUS", "mil1553_status"), ("AV.LRU.BIT", "mil1553_modecode")):
        got = {
            (ch["transport"]["bus"], ch["transport"]["rt"], ch["transport"]["rt_lru"])
            for ch in c["channels"].values()
            if ch["param_id"] == pid
        }
        assert got == rts, pid
        assert all(c["channels"][x]["transport"]["type"] == kind for x in c["parameters"][pid]["channel_ids"])
    health = {c["channels"][x]["unit_id"] for x in c["parameters"]["AV.LRU.HEALTH"]["channel_ids"]}
    assert health == {lru for _, _, lru in rts}


def test_icd_outputs_are_labelled_synthetic_and_complete():
    c = _content()
    rows = icd_rows(c)
    assert {r["channel_id"] for r in rows} == {
        cid
        for cid, ch in c["channels"].items()
        if ch["transport"]["type"] in ("mil1553", "mil1553_status", "mil1553_modecode", "arinc429", "fti_pcm")
    }
    csv_text = icd_csv(c)
    md = icd_markdown(c)
    assert csv_text.startswith("# SYNTHETIC Phalanx ICD") and "NOT the real Tejas ICD" in csv_text
    assert md.startswith("# SYNTHETIC Phalanx ICD") and "NOT the real Tejas ICD" in md
    assert icd_csv(c) == csv_text and icd_markdown(c) == md  # deterministic


def test_lookups_by_bus_address_agree_with_transport():
    d = Dictionary(_compiled())
    for ch in d.channels():
        t = ch["transport"]
        if t["type"] == "mil1553":
            hits = d.by_bus_address(t["bus"], rt=t["rt"], tr=t["tr"], sa=t["sa"], word=t["word"])
            assert [h["channel_id"] for h in hits] == [ch["channel_id"]]
        elif t["type"] == "arinc429":
            assert (
                d.by_bus_address(t["link"], label=t["label"], sdi=t["sdi"])[0]["channel_id"]
                == ch["channel_id"]
            )
        elif t["type"] == "fti_pcm":
            assert d.by_bus_address(t["stream"], word=t["word"])[0]["channel_id"] == ch["channel_id"]
    status = d.rt_status_channel("AV-MUX-2", 5)
    assert status is not None and status["channel_id"] == "AV.RT.STATUS.FADEC"
