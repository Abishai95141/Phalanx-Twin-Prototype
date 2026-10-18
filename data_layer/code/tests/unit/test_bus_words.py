"""M15 word encoders vs the independent M17 word decoders (W1.7 acceptance A1), plus golden vectors.

A1: for **every** dictionary channel carried on a recorded bus (1553, ARINC-429, FTI PCM), engineering values
encoded by M15 and decoded by M17 -- whose conversion comes from the recording's TMATS C group, not from the
encoder -- agree within half an LSB, exactly on the recorder lattice. n = 41 values per numeric channel
(both range ends, 13 lattice points, 26 off-lattice points): enough to hit the sign bit, both word limits and
every rounding direction; discretes use every defined field bit.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.bus.icd import BusIcd, Item
from phalanx.bus.words import SSM_CODES, arinc429_words, counts_for, encode_item_words, reverse_label
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.tmats import generate_tmats
from phalanx.ground.decoder.decode import _c_groups, _item_def, _mask
from phalanx.ground.decoder.setup import parse_tmats
from phalanx.ground.decoder.words import a429_fields, eu_from_counts, join_words, label_of, odd_parity_ok

D = load_dictionary()
ICD = BusIcd.from_dictionary(D)
TMATS = parse_tmats(generate_tmats(D.compiled.content))
CG = _c_groups(TMATS)


def _values(it: Item) -> tuple[np.ndarray, bool]:
    """Test values and whether they are all on the lattice."""
    if it.encoding in ("bnr", "ubnr"):
        lo, hi = it.range_min, it.range_max
        c0, c1 = it.cal
        lattice = c0 + c1 * np.rint((np.linspace(lo, hi, 13) - c0) / c1)
        frac = np.linspace(lo, hi, 26) + 0.37 * c1  # off-lattice: rounding in both directions
        frac = np.clip(frac, lo, hi)
        ends = np.array([c0 + c1 * np.ceil((lo - c0) / c1), c0 + c1 * np.floor((hi - c0) / c1)])
        return np.concatenate([ends, lattice, frac]), False
    if it.encoding == "bitfield":
        bits = [1 << b for b in range(it.word_bits) if it.field_mask >> b & 1]
        return np.array([0, it.field_mask, *bits], dtype=np.float64), True
    if it.encoding == "enum":
        return np.arange(0, 9, dtype=np.float64), True
    if it.encoding == "code_word":
        return np.array([k * 1000 + n for k in range(len(it.prefixes)) for n in (0, 1, 42, 999)], float), True
    raise AssertionError(it.encoding)


def _decoder_conv(it: Item, bits: int):
    """The decoder's conversion for an item, built from the TMATS (as M17 does)."""
    mask = 0
    if it.encoding == "bitfield":
        mask = it.field_mask  # TMATS MBM checked separately below
    return _item_def(D, it.channel_id, (), CG.get(it.channel_id, {}), mask, bits).conv


@pytest.mark.parametrize("it", [it for m in ICD.messages for it in m.items], ids=lambda it: it.channel_id)
def test_a1_1553_items_round_trip_within_half_lsb(it: Item):
    v, exact = _values(it)
    words, sat = encode_item_words(it, v)
    assert not sat.any(), "test values are inside the dictionary range, so no word may saturate"
    conv = _decoder_conv(it, 16 * it.words)
    dec, _ = eu_from_counts(join_words(words), conv)
    if it.encoding in ("bnr", "ubnr"):
        assert np.all(np.abs(dec - v) <= 0.5 * it.lsb * (1 + 1e-9)), it.channel_id
        lattice = it.cal[0] + it.cal[1] * np.rint((v - it.cal[0]) / it.cal[1])
        on = np.isclose(v, lattice, rtol=0, atol=1e-12 * max(1.0, abs(it.lsb)))
        assert np.array_equal(dec[on], lattice[on])  # exact on the recorder lattice
    else:
        assert exact and np.array_equal(dec, v), it.channel_id


@pytest.mark.parametrize("lb", ICD.labels, ids=lambda lb: f"{lb.link}-{lb.label:o}")
def test_a1_arinc429_items_round_trip_with_ssm(lb):
    it = lb.item
    v, _ = _values(it)
    for validity, code in SSM_CODES[it.ssm_table].items():
        w, sat = arinc429_words(lb.label, lb.sdi, it, v, np.full(v.size, validity, dtype=object))
        assert not sat.any()
        label, sdi, data, ssm = a429_fields(w)
        assert np.all(label == lb.label) and np.all(sdi == lb.sdi)
        assert np.all(ssm == code)
        assert np.all(odd_parity_ok(w))
        conv = _decoder_conv(it, 19)
        dec, _ = eu_from_counts(data, conv)
        if it.encoding == "bnr":
            assert np.all(np.abs(dec - v) <= 0.5 * it.lsb * (1 + 1e-9))
        else:
            assert np.array_equal(dec, v)


@pytest.mark.parametrize("it", ICD.pcm.items, ids=lambda it: it.channel_id)
def test_a1_fti_pcm_items_round_trip(it: Item):
    v, _ = _values(it)
    words, sat = encode_item_words(it, v)
    assert not sat.any()
    assert int(words.max()) < 1 << 12
    dec, _ = eu_from_counts(words[:, 0].astype(np.int64), _decoder_conv(it, 12))
    if it.encoding in ("bnr", "ubnr"):
        assert np.all(np.abs(dec - v) <= 0.5 * it.lsb * (1 + 1e-9))
    else:
        assert np.array_equal(dec, v)


def test_every_recorded_bus_channel_is_covered_by_a1():
    """Coverage: the parametrised A1 tests above span every dictionary channel on a recorded bus."""
    recorded = {"mil1553", "mil1553_status", "mil1553_modecode", "arinc429", "fti_pcm"}
    on_bus = {c["channel_id"] for c in D.channels() if c["transport"]["type"] in recorded}
    covered = {it.channel_id for m in ICD.messages for it in m.items} | {
        lb.item.channel_id for lb in ICD.labels
    }
    covered |= {it.channel_id for it in ICD.pcm.items}
    no_word = {c for c in on_bus if D.channel(c)["encoding"]["type"] in ("none", "string", "float64")}
    assert on_bus - covered == no_word == set(), sorted(on_bus - covered)[:10]


def test_bitfield_masks_agree_with_tmats():
    """The decoder reads discrete layouts from TMATS MBM; it must equal the dictionary field layout."""
    from phalanx.ground.decoder.setup import setup_from_tmats

    setup = setup_from_tmats(generate_tmats(D.compiled.content), D)
    checked = 0
    for key, mdef in setup.messages.items():
        bgroup = next(k[: -len("\\DLN")] for k, v in TMATS.items() if k.endswith("\\DLN") and v[0] == key[0])
        from phalanx.ground.decoder.decode import _tmats_msg_number

        n = _tmats_msg_number(TMATS, bgroup, *key[1:])
        for p, (cid, wn, mt) in enumerate(mdef.measurands, start=1):
            it = ICD.item(cid)
            if it.encoding == "bitfield" and mt == "D" and len(wn) == 1:
                assert _mask(TMATS[f"{bgroup}\\MBM-1-{n}-{p}-1"][0]) == it.field_mask, cid
                checked += 1
    assert checked > 50


# ---- golden vectors (independent arithmetic from the standards) ------------------------------------------
def test_golden_1553_command_word():
    """'01R 04 10' (RT1, receive, SA4, 16 words) = 0x0890 (Alta MIL-STD-1553 tutorial notation)."""
    rt, tr, sa, wc = 1, 0, 4, 16
    assert (rt << 11) | (tr << 10) | (sa << 5) | wc == 0x0890
    m = next(m for m in ICD.messages if m.msg_id == "AV-MUX-2/RT05/T/SA02")
    assert m.data_words == 15 and m.command_word == (5 << 11) | (1 << 10) | (2 << 5) | 15 == 0x2C4F
    m32 = next(m for m in ICD.messages if m.msg_id == "AV-MUX-2/RT01/T/SA01")
    assert m32.data_words == 32 and m32.command_word & 0x1F == 0  # word count 0 means 32


def test_golden_arinc429_label_parity_and_bnr():
    """Label 0o310 sits bit-reversed in bits 1-8 (0x13); parity is odd; BNR is 19-bit two's complement."""
    assert reverse_label(0o310) == 0x13
    assert label_of(np.array([0x13]))[0] == 0o310
    rad = next(lb for lb in ICD.labels if lb.link == "RADALT-OAC")
    w, _ = arinc429_words(
        rad.label, 0, rad.item, np.array([0.0, -1.0]), np.array(["NORMAL", "NORMAL"], object)
    )
    assert int(w[0]) & 0x7FFFFC00 == (3 << 29)  # zero data, SSM 11 (normal)
    assert (int(w[1]) >> 10) & 0x7FFFF == (1 << 19) - 1  # -1 count in 19-bit two's complement
    assert odd_parity_ok(w).all()
    assert not odd_parity_ok(w ^ np.uint32(1 << 31)).any()  # a flipped parity bit is detected


def test_code_word_layout_round_trips():
    """A-W1.7-6: code k*1000 + NNN <-> word (k << 10) | NNN."""
    it = ICD.item("ENG.FAULT_CODES")
    v = np.array([0, 1042, 999, 1999], dtype=np.float64)
    words, bad = encode_item_words(it, v)
    assert not bad.any()
    assert words[:, 0].tolist() == [0, (1 << 10) | 42, 999, (1 << 10) | 999]
    dec, _ = eu_from_counts(words[:, 0].astype(np.int64), _decoder_conv(it, 16))
    assert np.array_equal(dec, v)


def test_out_of_word_values_saturate_and_are_reported():
    """A value the word cannot carry saturates at the word limit (negative control for A1)."""
    it = next(it for it in ICD.items if it.encoding == "bnr" and it.words == 1 and it.lsb)
    c0, c1 = it.cal
    too_big = np.array([c0 + c1 * 40000.0, c0 - c1 * 40000.0])
    counts, sat = counts_for(it, too_big)
    assert sat.all() and counts.tolist() == [32767, -32768]
    bad_disc = ICD.item("AD.VALID.A")
    _, sat2 = counts_for(bad_disc, np.array([0.5, -1.0, 70000.0]))
    assert sat2.all()
    with pytest.raises(ValueError):
        counts_for(it, np.array([np.nan]))
