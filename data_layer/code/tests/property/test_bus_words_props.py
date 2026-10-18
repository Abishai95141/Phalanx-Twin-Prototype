"""Property: M15 word encoding and M17 decoding agree within half an LSB for any in-range value of any numeric
bus channel (A1 beyond the fixed grid of tests/unit/test_bus_words.py)."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.bus.icd import BusIcd
from phalanx.bus.words import arinc429_words, encode_item_words
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.tmats import generate_tmats
from phalanx.ground.decoder.decode import _c_groups, _item_def
from phalanx.ground.decoder.setup import parse_tmats
from phalanx.ground.decoder.words import a429_fields, eu_from_counts, join_words

D = load_dictionary()
ICD = BusIcd.from_dictionary(D)
CG = _c_groups(parse_tmats(generate_tmats(D.compiled.content)))
NUMERIC_1553 = [it for m in ICD.messages for it in m.items if it.encoding in ("bnr", "ubnr")]
NUMERIC_PCM = [it for it in ICD.pcm.items if it.encoding in ("bnr", "ubnr")]
RADALT = next(lb for lb in ICD.labels if lb.item.encoding == "bnr")


@settings(max_examples=300, deadline=None)
@given(st.sampled_from(NUMERIC_1553 + NUMERIC_PCM), st.floats(0.0, 1.0))
def test_numeric_round_trip_within_half_lsb(it, u):
    v = np.array([it.range_min + u * (it.range_max - it.range_min)])
    words, sat = encode_item_words(it, v)
    assert not sat.any()
    bits = 12 if it in NUMERIC_PCM else 16 * it.words
    conv = _item_def(D, it.channel_id, (), CG[it.channel_id], 0, bits).conv
    raw = join_words(words) if bits != 12 else words[:, 0].astype(np.int64)
    dec, _ = eu_from_counts(raw, conv)
    assert abs(dec[0] - v[0]) <= 0.5 * it.lsb * (1 + 1e-9)


@settings(max_examples=200, deadline=None)
@given(
    st.floats(0.0, 1.0), st.sampled_from(["NORMAL", "NO_COMPUTED_DATA", "FUNCTIONAL_TEST", "FAILURE_WARNING"])
)
def test_arinc_bnr_round_trip_and_ssm(u, validity):
    it = RADALT.item
    v = np.array([it.range_min + u * (it.range_max - it.range_min)])
    w, _ = arinc429_words(RADALT.label, 0, it, v, np.array([validity], dtype=object))
    _, _, data, ssm = a429_fields(w)
    conv = _item_def(D, it.channel_id, (), CG[it.channel_id], 0, 19).conv
    dec, _ = eu_from_counts(data, conv)
    assert abs(dec[0] - v[0]) <= 0.5 * it.lsb * (1 + 1e-9)
    codes = {int(k): s for k, s in D.code_table("ssm_bnr")["codes"].items()}
    assert codes[int(ssm[0])] == validity
