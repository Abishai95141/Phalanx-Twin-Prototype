"""Unified BIT/fault code table, code-word layout and flight-phase codes (dictionary 0.1.2; AD-48 item 5,
A-W1.7-6, AD-49).

Sample: the whole code table (104 codes) and both code-word channels; the questions are about completeness and
one-to-one mappings, so nothing smaller answers them. Negative tests change one entry of a bundle copy.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from phalanx.dictionary import CompileError, Dictionary, compile_bundle, load_bundle
from phalanx.dictionary.yamlio import load_yaml

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"
M14_CODES = REPO / "configs" / "tejas" / "params" / "M14" / "codes.yaml"
IDENTITY = ("desc", "sev", "list", "mech", "lru", "lane", "src", "legend", "voice")


@lru_cache(maxsize=1)
def _d() -> Dictionary:
    return Dictionary(compile_bundle(load_bundle(CONFIG)))


def _fails(b, pattern):
    with pytest.raises(CompileError, match=pattern):
        compile_bundle(b)


def _table(b):
    return b.tables["code_tables"]["tables"]["bit_codes"]


def test_m14_keeps_only_behaviour_rows_one_per_bit_code():
    """W2.1c switched M14 over (AD-48 item 5): identity, meaning, index and groups live only here; M14's
    codes.yaml has one behaviour row per dictionary code, no identity field, no groups and no provisional
    FADEC translation (the legacy map below replaces it; M14's identity agreement before the switch was
    checked by this test's W0.3 version)."""
    m14 = load_yaml(M14_CODES)
    codes = _d().bit_codes()
    assert len(codes) == 104 and set(m14["codes"]) == set(codes) and codes[102:] == ("ENG-509", "ENG-510")
    assert not any(set(c) & set(IDENTITY) for c in m14["codes"].values())
    assert "groups" not in m14 and "fadec_codes" not in m14
    mon = {k for c in m14["codes"].values() for k in c.get("monitor", {})}
    assert mon == {"persist_s", "clear_s"}  # channel / limit / sense / gate are the dictionary's


def test_legacy_m08_map_is_complete_and_one_to_one():
    d = _d()
    legacy = d.content["code_tables"]["bit_codes"]["legacy"]["M08"]["codes"]
    assert len(legacy) == 41  # M08 FAULT_CODES: 30 sensor + 8 function + 3 exceedance codes
    assert len(set(legacy.values())) == 41
    assert all(new in d.bit_codes() for new in legacy.values())
    # the collision AD-48 item 5 names: M08's ENG-501 (flameout) is the table's ENG-502; ENG-501 is a stall
    assert d.translate_bit_code("ENG-501", "M08") == "ENG-502" and "stall" in d.bit_code("ENG-501")["desc"]
    assert (
        d.translate_bit_code("ENG-011", "M08") == "ENG-001"
    )  # M08 N1 lane A; table ENG-011 = nozzle feedback


@pytest.mark.parametrize(
    ("edit", "pattern"),
    [
        (lambda t: t["codes"]["ENG-002"].update(index=0), "index values must be 0..n-1"),
        (lambda t: t["codes"].update({"XYZ-001": {**t["codes"]["ENG-001"], "index": 104}}), "prefix XYZ"),
        (lambda t: t["codes"]["ENG-001"].update(legend="CWS-L01"), "only PFL codes carry a CWS legend"),
        (lambda t: t["codes"]["ENG-005"].update(legend="CWS-L31"), "not one of the 30 CWS slots"),
        (lambda t: t["codes"]["ENG-701"]["monitor"].update(channel="ENG.T9"), "not a dictionary channel"),
        (lambda t: t["codes"]["ENG-701"]["monitor"].update(limit="nonsense"), "neither a channel limit"),
        (lambda t: t["codes"]["CWS-701"].update(voice="CWS.VOICE.NOPE"), "not a CWS channel"),
        (lambda t: t["legacy"]["M08"]["codes"].update({"ENG-011": "ENG-002"}), "must be one-to-one"),
        (lambda t: t["legacy"]["M08"]["codes"].update({"ENG-011": "ENG-999"}), "not in the table"),
        (lambda t: t["codes"]["ENG-501"].update(sev="SEVERE"), "sev 'SEVERE'"),
    ],
)
def test_bit_code_table_negatives(edit, pattern):
    b = load_bundle(CONFIG)
    edit(_table(b))
    _fails(b, pattern)


def test_code_word_layout_round_trips_every_code():
    """R-CODE-WORD (from A-W1.7-6): word = k << 10 | NNN, EU = k * 1000 + NNN, both ways, for every code that
    a code-word channel can carry; 0 = no code."""
    d = _d()
    layout = d.content["code_tables"]["bit_code_format"]["word_layout"]
    assert layout["prefix_index"] == {"lsb_bit": 10, "width": 6} and layout["number"] == {
        "lsb_bit": 0,
        "width": 10,
    }
    n = 0
    for cid in ("ENG.FAULT_CODES", "FCS.BIT.LOG"):
        prefixes = d.channel(cid)["encoding"]["prefixes"]
        for code in d.bit_codes():
            if code.split("-")[0] not in prefixes:
                continue
            k, nnn = prefixes.index(code.split("-")[0]), int(code.split("-")[1])
            eu = d.code_word_eu(cid, code)
            assert eu == k * 1000 + nnn
            assert d.code_word_bits(eu) == (k << 10) | nnn
            assert d.code_word_value(d.code_word_bits(eu)) == eu
            assert d.code_word_code(cid, eu) == code
            n += 1
    assert n > 40
    assert d.code_word_eu("ENG.FAULT_CODES", None) == 0 and d.code_word_code("ENG.FAULT_CODES", 0) is None
    with pytest.raises(ValueError):
        d.code_word_eu("ENG.N1.V", "ENG-001")


def test_code_word_layout_matches_the_bus_encoder():
    """The W1.7 bus encoder (A-W1.7-6) and the dictionary layout give the same word for every engine code."""
    from phalanx.bus.icd import BusIcd
    from phalanx.bus.words import counts_for

    d = _d()
    item = BusIcd.from_dictionary(d).item("ENG.FAULT_CODES")
    codes = [c for c in d.bit_codes() if c.split("-")[0] in ("ENG", "ECM")]
    eu = np.array([d.code_word_eu("ENG.FAULT_CODES", c) for c in codes], dtype=float)
    words, bad = counts_for(item, eu)
    assert not bad.any()
    assert words.tolist() == [d.code_word_bits(int(v)) for v in eu]


def test_flight_phase_codes_match_the_m02_request():
    """The released fighter phases are exactly M02's change request (W1.1), so its name mapping upgrades."""
    from phalanx.scenario.phases import PROPOSED_DICTIONARY_CODES, dictionary_map

    codes = _d().code_table("flight_phase")["codes"]
    assert {k: codes[str(k)] for k in PROPOSED_DICTIONARY_CODES} == PROPOSED_DICTIONARY_CODES
    assert set(dictionary_map().values()) <= {int(k) for k in codes}
