"""W2.1b: M08 fault codes are re-keyed to the dictionary's unified BIT/fault code table (dictionary 0.1.2
`bit_codes`, AD-48 item 5) through the dictionary's legacy map (`translate_bit_code(code, "M08")`).

Ties (each fails if either side drifts): every M08 code is a row of `Dictionary.bit_codes()`; the dictionary
translates every M08 legacy (W1.3b) code to exactly the code M08 emits; the dictionary's M08 legacy map has no
entry M08 lacks; lanes agree; the ENG.FAULT_CODES word is the dictionary's code-word EU value of the
highest-priority active code. Negative control: the W1.3b numbering collided with M14's (legacy ENG-501 was
the flameout; unified ENG-501 is the compressor stall), so the flameout bit must now emit ENG-502.

Sample: the whole table (41 codes); deterministic.
"""

from __future__ import annotations

import pytest

from phalanx.dictionary import load_dictionary
from phalanx.fadec.codes import (
    B_FLAMEOUT,
    B_STALL,
    FAULT_BY_BIT,
    FAULT_CODES,
    LEGACY_TO_UNIFIED,
    active_codes,
    code_word,
)

pytestmark = pytest.mark.unit
D = load_dictionary()


def test_every_m08_code_is_the_dictionary_translation_of_its_legacy_code():
    table = set(D.bit_codes())
    legacy = D._content["code_tables"]["bit_codes"]["legacy"]["M08"]["codes"]
    assert set(legacy) == set(LEGACY_TO_UNIFIED) == {f.legacy for f in FAULT_CODES}
    for f in FAULT_CODES:
        assert f.code in table, f
        assert D.translate_bit_code(f.legacy, "M08") == f.code, f
        row = D.bit_code(f.code)
        assert (row.get("lane") or "") == f.lane, (f, row.get("lane"))
        assert f.code.startswith("ENG-")


def test_fault_code_word_is_the_dictionary_code_word_of_the_top_priority_code():
    for bit, f in FAULT_BY_BIT.items():
        assert code_word(1 << bit) == D.code_word_eu("ENG.FAULT_CODES", f.code), f
    # exceedance beats function beats sensor (M08's priority rule), on unified codes
    mask = (1 << 0) | (1 << B_STALL) | (1 << 38)
    assert active_codes(mask) == ["ENG-001", "ENG-501", "ENG-701"]
    assert code_word(mask) == D.code_word_eu("ENG.FAULT_CODES", "ENG-701")
    assert code_word(0) == 0


def test_negative_control_legacy_numbering_is_not_emitted():
    """The W1.3b flameout code ENG-501 means 'compressor stall' in the unified table: M08 must emit ENG-502
    for its flameout bit and ENG-501 for its stall bit."""
    assert FAULT_BY_BIT[B_FLAMEOUT].code == "ENG-502" and FAULT_BY_BIT[B_FLAMEOUT].legacy == "ENG-501"
    assert FAULT_BY_BIT[B_STALL].code == "ENG-501"
    assert "flameout" in D.bit_code("ENG-502")["desc"].lower()
    assert "stall" in D.bit_code("ENG-501")["desc"].lower()
