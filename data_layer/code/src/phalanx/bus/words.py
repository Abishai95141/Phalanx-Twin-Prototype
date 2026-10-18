"""Engineering value -> bus word encoders (M15), vectorised.

Conventions (all from the dictionary; rule R-ICD-WORDS, R-ICD-429, R-ICD-FTI-PCM, AD-39):

- **BNR / UBNR** (AS15532 style): ``counts = rint((value - c0) / c1)`` with the dictionary linear calibration
  ``EU = c0 + c1 * counts`` (c1 = recorder LSB, rule R-CAL-LINEAR). BNR is two's complement in ``word_bits``,
  UBNR unsigned. Counts that do not fit the word saturate at the word limits (a word cannot carry them); the
  ground decoder then flags the decoded value OUT_OF_RANGE when it is outside the dictionary range.
  ``rint`` is round-half-to-even, so values already on the recorder lattice (M13 output) encode exactly.
- **32-bit quantities** span two 1553 data words, most-significant word first (MIL-STD-1553B §4.3.2).
- **bitfield / enum**: the EU value is the integer word value (dimensionless); bits outside the defined
  fields are transmitted as zero (MIL-STD-1553B: unused bits are zero).
- **code_word** (synthetic ``SSS-NNN`` fault codes, rule R-CODES-SYNTHETIC): EU value ``k * scale + NNN``
  where ``k`` is the prefix index in the channel's ``prefixes`` list; the word puts ``k`` and ``NNN`` in the
  bit fields of the dictionary's ``bit_code_format.word_layout`` (``Item.code_layout``; rule R-CODE-WORD,
  A-W0.3-43; 0.1.2: k in bits 15-10, NNN in bits 9-0, scale 1000). Dictionary 0.1.2 migration (W2.2): the W1.7
  constant layout (A-W1.7-6) is gone; the bytes are unchanged.
- **ARINC-429** words are 32-bit integers in bus order with bit n of the standard at integer bit n-1: label
  bits 1-8 (octal label, MSB first on the wire, so bit-reversed in the integer), SDI 9-10, data 11-29
  (BNR: 19-bit two's complement, sign in bit 29), SSM 30-31, odd parity in bit 32.

Values must be finite (the CIR never carries NaN); a non-finite value raises.
"""

from __future__ import annotations

import numpy as np

from .icd import Item

__all__ = [
    "SSM_CODES",
    "arinc429_words",
    "counts_for",
    "encode_item_words",
    "reverse_label",
    "words_from_counts",
]

#: validity symbol -> ARINC-429 SSM code (bits 31,30 as an integer), per table (dictionary code tables
#: ``ssm_bnr`` / ``ssm_dis``). BUS_INVALID has no SSM code: it is sent as FAILURE_WARNING (A-W1.7-7).
SSM_CODES = {
    "ssm_bnr": {"FAILURE_WARNING": 0, "NO_COMPUTED_DATA": 1, "FUNCTIONAL_TEST": 2, "NORMAL": 3},
    "ssm_dis": {"NORMAL": 0, "NO_COMPUTED_DATA": 1, "FUNCTIONAL_TEST": 2, "FAILURE_WARNING": 3},
}


def _limits(encoding: str, bits: int) -> tuple[int, int]:
    if encoding == "bnr":
        return -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return 0, (1 << bits) - 1


def counts_for(item: Item, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Integer counts for ``values`` (EU) and a mask of values that saturated the word.

    Returns ``(counts int64, saturated bool)``; counts are signed for BNR (two's complement range).
    """
    v = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(v)):
        raise ValueError(f"{item.channel_id}: non-finite value (the CIR never carries NaN)")
    bits = item.word_bits
    enc = item.encoding
    if enc in ("bnr", "ubnr"):
        if item.cal is None:
            raise ValueError(f"{item.channel_id}: numeric word without calibration")
        c0, c1 = item.cal
        raw = np.rint((v - c0) / c1)
        lo, hi = _limits(enc, bits)
        sat = (raw < lo) | (raw > hi)
        return np.clip(raw, lo, hi).astype(np.int64), sat
    if enc in ("bitfield", "enum"):
        raw = np.rint(v)
        lo, hi = 0, (1 << bits) - 1
        sat = (raw < lo) | (raw > hi) | (raw != v)
        c = np.clip(raw, lo, hi).astype(np.int64)
        if enc == "bitfield":
            c &= item.field_mask
        return c, sat
    if enc == "code_word":
        lay = item.code_layout
        if lay is None:
            raise ValueError(f"{item.channel_id}: code_word item without the dictionary code-word layout")
        raw = np.rint(v).astype(np.int64)
        k, nnn = np.divmod(np.clip(raw, 0, None), lay.scale)
        k_max, n_max = (1 << lay.k_width) - 1, (1 << lay.n_width) - 1
        bad = (raw != v) | (raw < 0) | (k >= max(len(item.prefixes), 1)) | (k > k_max) | (nnn > n_max)
        word = (np.clip(k, 0, k_max) << lay.k_lsb) | (np.clip(nnn, 0, n_max) << lay.n_lsb)
        return np.where(bad, 0, word).astype(np.int64), bad
    raise ValueError(f"{item.channel_id}: encoding {enc!r} is not a bus word encoding")


def words_from_counts(item: Item, counts: np.ndarray) -> np.ndarray:
    """1553 / PCM data words for counts: shape (n, item.words), uint16, MSW first."""
    c = np.asarray(counts, dtype=np.int64)
    bits = item.word_bits
    u = c & ((1 << bits) - 1)  # two's complement in `bits`
    if item.words == 1:
        return u.astype(np.uint16).reshape(-1, 1)
    if item.words == 2:
        if bits != 32:
            raise ValueError(f"{item.channel_id}: two-word item must be 32 bits, got {bits}")
        return np.stack([(u >> 16) & 0xFFFF, u & 0xFFFF], axis=1).astype(np.uint16)
    raise ValueError(f"{item.channel_id}: {item.words} words per item not supported")


def encode_item_words(item: Item, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(words uint16 (n, item.words), saturated bool (n,)) for a 1553 or PCM item."""
    counts, sat = counts_for(item, values)
    return words_from_counts(item, counts), sat


def reverse_label(label: int) -> int:
    """Octal label value -> the 8 label bits as they sit in bits 1-8 of the bus-order integer."""
    return int(f"{int(label) & 0xFF:08b}"[::-1], 2)


def _odd_parity_bit(w: np.ndarray) -> np.ndarray:
    x = w.copy()
    x ^= x >> 16
    x ^= x >> 8
    x ^= x >> 4
    x ^= x >> 2
    x ^= x >> 1
    ones_odd = x & 1
    return (1 - ones_odd).astype(np.uint64)  # set bit 32 when bits 1-31 have an even number of ones


def arinc429_words(
    label: int, sdi: int, item: Item, values: np.ndarray, validity: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """32-bit ARINC-429 words (uint32) for values and validity symbols; also the saturation mask."""
    counts, sat = counts_for(item, values)
    data = (counts & ((1 << 19) - 1)).astype(np.uint64)
    table = SSM_CODES[item.ssm_table or "ssm_bnr"]
    val = np.asarray(validity, dtype=object)
    ssm = np.array([table.get(s, table["FAILURE_WARNING"]) for s in val.tolist()], dtype=np.uint64).reshape(
        -1
    )
    w = (
        np.uint64(reverse_label(label))
        | (np.uint64(sdi & 0x3) << np.uint64(8))
        | (data << np.uint64(10))
        | (ssm << np.uint64(29))
    )
    w = w | (_odd_parity_bit(w) << np.uint64(31))
    return w.astype(np.uint32), sat
