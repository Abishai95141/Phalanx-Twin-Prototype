"""IRIG 106 Chapter 10 packet encoders (M16), written from IRIG 106-15 Ch10 §10.6 (public standard;
local copy ``research_sources/data_pathway/ch10_trmc_113019632.txt``) and checked against two independent
parsers (pyChapter10 and ``phalanx.ground.decoder.reader``).

Byte-level conventions (all little-endian, §10.6.1):

- **Header** (24 B): sync 0xEB25, channel ID, packet length (multiple of 4), data length (CSDW + IPHs +
  data, without filler and checksum), data type version, 8-bit sequence number, packet flags, data type,
  48-bit RTC, header checksum = 16-bit sum of the first eleven header words.
- **Flags**: bit 7 secondary header (never used), bit 6 IPTS source (0 = RTC), bit 5 RTC sync error,
  bit 4 data overflow, bits 3-2 secondary time format, bits 1-0 data checksum (0 none, 1 8-bit, 2 16-bit,
  3 32-bit).
- **Trailer**: filler (0x00) to keep packets 32-bit aligned, then the optional data checksum: the arithmetic
  sum of the body bytes/words/long words (CSDW through filler), truncated to its width (§10.6.1.4).
- **Data type version** 0x03 = RCC 106-07, matching the setup record (TMATS ``G\\106:07``, CSDW CH10VER 7).

Every function returns ``bytes`` and is a pure function of its arguments (deterministic, A8).
"""

from __future__ import annotations

import struct

import numpy as np

__all__ = [
    "DATA_TYPE_VERSION",
    "DT_ANALOG_F1",
    "DT_ARINC429_F0",
    "DT_COMPUTER_F1",
    "DT_COMPUTER_F2",
    "DT_COMPUTER_F3",
    "DT_DISCRETE_F1",
    "DT_MS1553_F1",
    "DT_PCM_F1",
    "DT_TIME_F1",
    "MAX_PACKET_BYTES",
    "SYNC",
    "analog_body",
    "arinc429_body",
    "bcd_time_words",
    "discrete_body",
    "event_body",
    "header_checksum",
    "index_node_body",
    "index_root_body",
    "ms1553_body",
    "packet",
    "pcm_unpacked_body",
    "time_body",
    "tmats_body",
]

SYNC = 0xEB25
DATA_TYPE_VERSION = 0x03  # RCC 106-07
MAX_PACKET_BYTES = 524_288
CH10VER_106_07 = 0x07

DT_COMPUTER_F1 = 0x01  # setup record (TMATS)
DT_COMPUTER_F2 = 0x02  # recording events
DT_COMPUTER_F3 = 0x03  # recording index
DT_PCM_F1 = 0x09
DT_TIME_F1 = 0x11
DT_MS1553_F1 = 0x19
DT_ANALOG_F1 = 0x21
DT_DISCRETE_F1 = 0x29
DT_ARINC429_F0 = 0x38

_HDR = struct.Struct("<HHIIBBBB")
_CHECKSUM_BYTES = {0: 0, 1: 1, 2: 2, 3: 4}


def header_checksum(head22: bytes) -> int:
    """16-bit arithmetic sum of the first eleven 16-bit header words (§10.6.1.1 j)."""
    return int(np.frombuffer(head22, dtype="<u2").sum(dtype=np.uint64)) & 0xFFFF


def _rtc48(rtc: int) -> bytes:
    if not 0 <= int(rtc) < 1 << 48:
        raise ValueError(f"RTC {rtc} outside 48 bits")
    return int(rtc).to_bytes(6, "little")


def packet(
    channel_id: int,
    data_type: int,
    sequence: int,
    rtc: int,
    body: bytes,
    *,
    checksum: int = 3,
    rtc_sync_error: bool = False,
    overflow: bool = False,
    version: int = DATA_TYPE_VERSION,
) -> bytes:
    """One complete packet: header + body (CSDW onward) + filler + data checksum."""
    if not 0 <= channel_id <= 0xFFFF:
        raise ValueError("channel ID outside 16 bits")
    if checksum not in _CHECKSUM_BYTES:
        raise ValueError("checksum code must be 0..3")
    cks = _CHECKSUM_BYTES[checksum]
    data_len = len(body)
    pad = (-(data_len + cks)) % 4
    padded = body + b"\x00" * pad
    trailer = b""
    if checksum == 1:
        trailer = struct.pack("<B", int(np.frombuffer(padded, dtype=np.uint8).sum(dtype=np.uint64)) & 0xFF)
    elif checksum == 2:
        if len(padded) % 2:
            raise ValueError("16-bit checksum needs an even body length")
        trailer = struct.pack("<H", int(np.frombuffer(padded, dtype="<u2").sum(dtype=np.uint64)) & 0xFFFF)
    elif checksum == 3:
        if len(padded) % 4:
            raise ValueError("32-bit checksum needs a body length multiple of 4")
        trailer = struct.pack("<I", int(np.frombuffer(padded, dtype="<u4").sum(dtype=np.uint64)) & 0xFFFFFFFF)
    total = 24 + len(padded) + len(trailer)
    if total % 4:
        raise AssertionError("packet length not 32-bit aligned")
    if total > MAX_PACKET_BYTES and data_type != DT_COMPUTER_F1:
        raise ValueError(f"packet of {total} B exceeds {MAX_PACKET_BYTES} B")
    flags = (0x20 if rtc_sync_error else 0) | (0x10 if overflow else 0) | (checksum & 0x3)
    head = _HDR.pack(SYNC, channel_id, total, data_len, version, sequence & 0xFF, flags, data_type)
    head += _rtc48(rtc)
    head += struct.pack("<H", header_checksum(head))
    return head + padded + trailer


# ------------------------------------------------------------------------------------------------ bodies
def tmats_body(text: str, *, srcc: bool = False) -> bytes:
    """Computer-Generated F1 (setup record, ASCII TMATS) body: CSDW (FRMT 0, SRCC, CH10VER) + text."""
    csdw = (int(srcc) << 8) | CH10VER_106_07
    return struct.pack("<I", csdw) + text.encode("ascii")


def bcd_time_words(utc_ms: int) -> tuple[int, int, int, int]:
    """Time F1 body words, day-month-year format (§10.6.3.2 Figure 10-21), 10 ms resolution.

    ``utc_ms`` = milliseconds since 1970-01-01T00:00Z (POSIX, no leap seconds); the 10 ms digit is truncated.
    """
    import datetime as dt

    if utc_ms < 0:
        raise ValueError("time before 1970")
    day, ms_of_day = divmod(int(utc_ms), 86_400_000)
    date = dt.date(1970, 1, 1) + dt.timedelta(days=day)
    h, rem = divmod(ms_of_day, 3_600_000)
    mi, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    w1 = ((s // 10) << 12) | ((s % 10) << 8) | ((ms // 100) << 4) | ((ms // 10) % 10)
    w2 = ((h // 10) << 12) | ((h % 10) << 8) | ((mi // 10) << 4) | (mi % 10)
    w3 = ((date.month // 10) << 12) | ((date.month % 10) << 8) | ((date.day // 10) << 4) | (date.day % 10)
    y = date.year
    w4 = ((y // 1000) << 12) | (((y // 100) % 10) << 8) | (((y // 10) % 10) << 4) | (y % 10)
    return w1, w2, w3, w4


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def time_body(utc_ms: int, *, fmt: int, src: int) -> bytes:
    """Time F1 body: CSDW (DATE: month/year format + leap bit, FMT, SRC) + four BCD words."""
    import datetime as dt

    year = (dt.date(1970, 1, 1) + dt.timedelta(days=int(utc_ms) // 86_400_000)).year
    date_bits = 0b10 | (1 if _leap(year) else 0)  # bit 9 = month/year format, bit 8 = leap year
    csdw = (date_bits << 8) | ((fmt & 0xF) << 4) | (src & 0xF)
    return struct.pack("<I", csdw) + struct.pack("<4H", *bcd_time_words(utc_ms))


def ms1553_body(
    ttb: int,
    ipts: np.ndarray,
    bsw: np.ndarray,
    gap: np.ndarray,
    words: np.ndarray,
    word_offsets: np.ndarray,
) -> bytes:
    """MIL-STD-1553 F1 body (§10.6.4.2): CSDW (TTB, message count) + per message IPTS, IPDH, words.

    ``words[word_offsets[i]:word_offsets[i+1]]`` are message i's words in bus order. Vectorised.
    """
    n = int(ipts.size)
    nw = np.diff(word_offsets).astype(np.int64)
    msg_bytes = 14 + 2 * nw
    off = np.concatenate([[0], np.cumsum(msg_bytes)]).astype(np.int64)
    out = np.zeros(int(off[-1]), dtype=np.uint8)
    ip = np.asarray(ipts, dtype=np.uint64)
    for b in range(8):
        out[off[:-1] + b] = ((ip >> np.uint64(8 * b)) & np.uint64(0xFF)).astype(np.uint8)
    for k, arr in enumerate((bsw, gap, (2 * nw).astype(np.uint16))):
        a = np.asarray(arr, dtype=np.uint16)
        out[off[:-1] + 8 + 2 * k] = (a & 0xFF).astype(np.uint8)
        out[off[:-1] + 9 + 2 * k] = (a >> 8).astype(np.uint8)
    w = np.asarray(words, dtype=np.uint16)[int(word_offsets[0]) : int(word_offsets[-1])]
    base = np.repeat(off[:-1] + 14, nw) + 2 * (
        np.arange(w.size, dtype=np.int64) - np.repeat(np.concatenate([[0], np.cumsum(nw)])[:-1], nw)
    )
    out[base] = (w & 0xFF).astype(np.uint8)
    out[base + 1] = (w >> 8).astype(np.uint8)
    csdw = ((ttb & 0x3) << 30) | (n & 0xFFFFFF)
    return struct.pack("<I", csdw) + out.tobytes()


def arinc429_body(
    bus: np.ndarray, high_speed: np.ndarray, gap_tenths: np.ndarray, words: np.ndarray
) -> bytes:
    """ARINC-429 F0 body (§10.6.8.1): CSDW (word count) + per word ID word (bus, BS, gap) and data word."""
    n = int(words.size)
    ids = (
        (np.asarray(bus, dtype=np.uint32) & 0xFF) << 24
        | (np.asarray(high_speed, dtype=np.uint32) & 1) << 21
        | (np.asarray(gap_tenths, dtype=np.uint32) & 0xFFFFF)
    )
    pairs = np.empty(2 * n, dtype="<u4")
    pairs[0::2] = ids
    pairs[1::2] = np.asarray(words, dtype=np.uint32)
    return struct.pack("<I", n & 0xFFFF) + pairs.tobytes()


def pcm_unpacked_body(ipts: np.ndarray, frames16: np.ndarray, *, lock_status: int = 0xF) -> bytes:
    """PCM F1 body, unpacked mode, 16-bit alignment, IPH per minor frame (§10.6.2.2).

    ``frames16`` is (n, k) uint16: each minor frame's words, each already right-aligned with high-order pad
    (sync halves first). CSDW: IPH = 1, MA = MI = 1 (one minor frame per major frame), LOCKST = lock_status,
    MODE = unpacked (bit 18).
    """
    n, k = frames16.shape
    rec = np.zeros((n, 5 + k), dtype="<u2")
    ip = np.asarray(ipts, dtype=np.uint64)
    for j in range(4):
        rec[:, j] = ((ip >> np.uint64(16 * j)) & np.uint64(0xFFFF)).astype(np.uint16)
    rec[:, 4] = (lock_status & 0xF) << 12
    rec[:, 5:] = frames16
    csdw = (1 << 30) | (1 << 29) | (1 << 28) | ((lock_status & 0xF) << 24) | (1 << 18)
    return struct.pack("<I", csdw) + rec.tobytes()


def event_body(
    ipts: np.ndarray, number: np.ndarray, count: np.ndarray, *, occurred_recording: bool = True
) -> bytes:
    """Computer-Generated F2 (recording event) body (§10.6.7.3): CSDW (no IPDH, entry count) + entries."""
    n = int(ipts.size)
    rec = np.zeros((n, 3), dtype="<u4")
    ip = np.asarray(ipts, dtype=np.uint64)
    rec[:, 0] = (ip & np.uint64(0xFFFFFFFF)).astype(np.uint32)
    rec[:, 1] = (ip >> np.uint64(32)).astype(np.uint32)
    rec[:, 2] = (
        (np.uint32(1 if occurred_recording else 0) << 28)
        | ((np.asarray(count, dtype=np.uint32) & 0xFFFF) << 12)
        | (np.asarray(number, dtype=np.uint32) & 0xFFF)
    )
    return struct.pack("<I", n & 0xFFF) + rec.tobytes()


def index_node_body(
    ipts: np.ndarray, channel_id: np.ndarray, data_type: np.ndarray, offset: np.ndarray
) -> bytes:
    """Computer-Generated F3 node index body (§10.6.7.4 f): IT = 1, no file size, no IPDH."""
    n = int(ipts.size)
    rec = np.zeros((n, 5), dtype="<u4")
    ip = np.asarray(ipts, dtype=np.uint64)
    of = np.asarray(offset, dtype=np.uint64)
    rec[:, 0] = (ip & np.uint64(0xFFFFFFFF)).astype(np.uint32)
    rec[:, 1] = (ip >> np.uint64(32)).astype(np.uint32)
    rec[:, 2] = (np.asarray(data_type, dtype=np.uint32) & 0xFF) << 16 | (
        np.asarray(channel_id, dtype=np.uint32)
    )
    rec[:, 3] = (of & np.uint64(0xFFFFFFFF)).astype(np.uint32)
    rec[:, 4] = (of >> np.uint64(32)).astype(np.uint32)
    csdw = (1 << 31) | (n & 0xFFFF)
    return struct.pack("<I", csdw) + rec.tobytes()


def index_root_body(ipts: np.ndarray, offset: np.ndarray, root_ipts: int, root_offset: int) -> bytes:
    """Computer-Generated F3 root index body (§10.6.7.4 e): node offsets, then the root's own entry."""
    ip = np.concatenate([np.asarray(ipts, dtype=np.uint64), np.array([root_ipts], dtype=np.uint64)])
    of = np.concatenate([np.asarray(offset, dtype=np.uint64), np.array([root_offset], dtype=np.uint64)])
    rec = np.zeros((ip.size, 4), dtype="<u4")
    rec[:, 0] = (ip & np.uint64(0xFFFFFFFF)).astype(np.uint32)
    rec[:, 1] = (ip >> np.uint64(32)).astype(np.uint32)
    rec[:, 2] = (of & np.uint64(0xFFFFFFFF)).astype(np.uint32)
    rec[:, 3] = (of >> np.uint64(32)).astype(np.uint32)
    csdw = int(np.asarray(ipts).size) & 0xFFFF  # IT = 0 (root); entry count excludes the root's own entry
    return struct.pack("<I", csdw) + rec.tobytes()


def analog_body(
    samples: np.ndarray, *, bits: int, subchannel: int = 1, totchan: int = 1, factor: int = 0
) -> bytes:
    """Analog F1 body (§10.6.5.2): one subchannel, unpacked 16-bit samples (MODE 0b01, LSB padded)."""
    if not 1 <= bits <= 16:
        raise ValueError("this writer supports 1..16-bit analog samples")
    csdw = (1 << 28) | ((factor & 0xF) << 24) | ((totchan & 0xFF) << 16) | ((subchannel & 0xFF) << 8)
    csdw |= ((bits & 0x3F) << 2) | 0b01
    return struct.pack("<I", csdw) + np.asarray(samples, dtype="<u2").tobytes()


def discrete_body(ipts: np.ndarray, states: np.ndarray, *, bits: int = 32, on_change: bool = True) -> bytes:
    """Discrete F1 body (§10.6.6.2): CSDW (LENGTH, MODE) + per event IPTS and 32-bit states."""
    n = int(ipts.size)
    rec = np.zeros((n, 3), dtype="<u4")
    ip = np.asarray(ipts, dtype=np.uint64)
    rec[:, 0] = (ip & np.uint64(0xFFFFFFFF)).astype(np.uint32)
    rec[:, 1] = (ip >> np.uint64(32)).astype(np.uint32)
    rec[:, 2] = np.asarray(states, dtype=np.uint32)
    csdw = ((bits % 32) << 3) | (0 if on_change else 1)
    return struct.pack("<I", csdw) + rec.tobytes()
