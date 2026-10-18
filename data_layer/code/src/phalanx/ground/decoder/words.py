"""Bus word -> engineering value decoders (M17), independent of the M15 encoders.

The location of a measurand comes from the recording's TMATS; the counts-to-EU conversion from its C group
(``BFM`` TWO = two's complement, UNS = unsigned; polynomial ``CO``, ``CO-1``); discrete layouts from the TMATS
bit mask; the validity mapping from the dictionary code tables (``mil1553_validity_bit``, ``ssm_bnr``,
``ssm_dis``). The synthetic ``SSS-NNN`` code-word layout comes from the dictionary's
``bit_code_format.word_layout`` (rule R-CODE-WORD, A-W0.3-43; 0.1.2: k in bits 15-10, NNN in bits 9-0 ->
``k * 1000 + NNN``), read by the decoder itself, never shared with the M15 encoder (W2.2 migration of the
W1.7 constant layout A-W1.7-6).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "Conversion",
    "a429_fields",
    "code_layout",
    "eu_from_counts",
    "join_words",
    "label_of",
    "odd_parity_ok",
    "signed",
]


@dataclass(frozen=True)
class Conversion:
    """How one measurand's raw word(s) become an engineering value."""

    kind: str  # TWO | UNS | DIS | CODE
    bits: int
    c0: float
    c1: float
    mask: int  # DIS: used bits (0 = full word)
    #: CODE: (k lsb, k width, NNN lsb, NNN width, EU prefix scale) of the dictionary code-word layout
    code: tuple[int, int, int, int, int] | None = None


def code_layout(dictionary) -> tuple[int, int, int, int, int]:
    """The dictionary's code-word layout as ``Conversion.code`` (``bit_code_format.word_layout``)."""
    lay = dictionary.content["code_tables"]["bit_code_format"]["word_layout"]
    k, n = lay["prefix_index"], lay["number"]
    return (
        int(k["lsb_bit"]),
        int(k["width"]),
        int(n["lsb_bit"]),
        int(n["width"]),
        int(lay["eu_prefix_scale"]),
    )


def join_words(words: np.ndarray) -> np.ndarray:
    """(n, k) uint16 words, most-significant first -> unsigned int64 (k <= 3)."""
    w = np.asarray(words, dtype=np.int64)
    out = np.zeros(w.shape[0], dtype=np.int64)
    for j in range(w.shape[1]):
        out = (out << 16) | w[:, j]
    return out


def signed(u: np.ndarray, bits: int) -> np.ndarray:
    u = np.asarray(u, dtype=np.int64) & ((1 << bits) - 1)
    return np.where(u >= (1 << (bits - 1)), u - (1 << bits), u)


def eu_from_counts(raw: np.ndarray, conv: Conversion) -> tuple[np.ndarray, np.ndarray]:
    """(engineering values float64, raw counts int64) from unsigned raw word values."""
    u = np.asarray(raw, dtype=np.int64)
    if conv.kind == "TWO":
        c = signed(u, conv.bits)
        return conv.c0 + conv.c1 * c.astype(np.float64), c
    if conv.kind == "UNS":
        c = u & ((1 << conv.bits) - 1)
        return conv.c0 + conv.c1 * c.astype(np.float64), c
    if conv.kind == "DIS":
        c = u & (conv.mask if conv.mask else (1 << conv.bits) - 1)
        return c.astype(np.float64), c
    if conv.kind == "CODE":
        if conv.code is None:
            raise ValueError("CODE conversion without the dictionary code-word layout")
        k_lsb, k_w, n_lsb, n_w, scale = conv.code
        k, nnn = (u >> k_lsb) & ((1 << k_w) - 1), (u >> n_lsb) & ((1 << n_w) - 1)
        return (k * scale + nnn).astype(np.float64), u
    raise ValueError(f"unknown conversion kind {conv.kind}")


def label_of(word: np.ndarray) -> np.ndarray:
    """Octal label of ARINC-429 words (bits 1-8 go out MSB first, so they are reversed in the integer)."""
    b = np.asarray(word, dtype=np.int64) & 0xFF
    out = np.zeros_like(b)
    for i in range(8):
        out |= ((b >> i) & 1) << (7 - i)
    return out


def a429_fields(word: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(label, sdi, 19-bit data field, ssm) of ARINC-429 words."""
    w = np.asarray(word, dtype=np.int64)
    return label_of(w), (w >> 8) & 0x3, (w >> 10) & 0x7FFFF, (w >> 29) & 0x3


def odd_parity_ok(word: np.ndarray) -> np.ndarray:
    w = np.asarray(word, dtype=np.int64) & 0xFFFFFFFF
    ones = np.zeros(w.shape, dtype=np.int64)
    for i in range(32):
        ones += (w >> i) & 1
    return (ones % 2) == 1
