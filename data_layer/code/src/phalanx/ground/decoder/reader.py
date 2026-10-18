"""Minimal, independent IRIG 106 Chapter 10 reader (M17), written from IRIG 106-15 Ch10 §10.6.

It shares no code with the M16 writer or with pyChapter10: the A3 acceptance test compares this reader,
pyChapter10 and the writer's own packet table on the same files, including the public KC-135 sample
``sample.c10``. irig106lib (the C reference library) is not installed in the pinned environment, so this
module is the "second independent reader" the W1.7 brief asks for.

Robustness (the decoder must survive real downloads):

- a bad sync word or header checksum -> resynchronise on the next 0xEB25 and record the error;
- a packet that runs past the end of the data (interrupted transfer) -> stop, flag ``truncated``;
- a data-checksum mismatch -> the packet is returned with ``checksum_ok = False`` (the decoder drops it).

Typed decoders return NumPy arrays; the 1553 message walk (variable-length messages) is a compiled loop.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

import numpy as np
from numba import njit

__all__ = [
    "AnalogSamples",
    "Arinc429Words",
    "Ch10File",
    "DiscreteEvents",
    "EventEntries",
    "Ms1553Messages",
    "Packet",
    "PcmFrames",
    "TimeRecords",
    "read_analog",
    "read_arinc429",
    "read_discrete",
    "read_events",
    "read_file",
    "read_ms1553",
    "read_pcm_unpacked",
    "read_time",
]

SYNC_BYTES = b"\x25\xeb"
_HDR = struct.Struct("<HHIIBBBB6sH")


@dataclass(frozen=True)
class Packet:
    offset: int
    channel_id: int
    packet_length: int
    data_length: int
    version: int
    seq: int
    flags: int
    data_type: int
    rtc: int
    body_start: int  # file offset of the CSDW
    checksum_ok: bool

    @property
    def rtc_sync_error(self) -> bool:
        return bool(self.flags & 0x20)

    @property
    def secondary_header(self) -> bool:
        return bool(self.flags & 0x80)


@dataclass(frozen=True)
class Ch10File:
    data: bytes
    packets: tuple[Packet, ...]
    sync_errors: int
    truncated: bool
    errors: tuple[str, ...] = field(default_factory=tuple)

    def body(self, p: Packet) -> bytes:
        return self.data[p.body_start : p.body_start + p.data_length]

    def of_type(self, data_type: int, channel_id: int | None = None) -> tuple[Packet, ...]:
        return tuple(
            p
            for p in self.packets
            if p.data_type == data_type and (channel_id is None or p.channel_id == channel_id)
        )


def _checksum_ok(data: bytes, start: int, end_body: int, total_end: int, code: int) -> bool:
    if code == 0:
        return True
    width = {1: 1, 2: 2, 3: 4}[code]
    payload = data[start : total_end - width]
    stored = int.from_bytes(data[total_end - width : total_end], "little")
    dt = {1: np.uint8, 2: "<u2", 3: "<u4"}[code]
    if len(payload) % width:
        return False
    s = int(np.frombuffer(payload, dtype=dt).sum(dtype=np.uint64)) & ((1 << (8 * width)) - 1)
    return s == stored


def read_file(data: bytes) -> Ch10File:
    """All packets of a Ch10 byte stream, in file order."""
    pkts: list[Packet] = []
    errors: list[str] = []
    pos, n = 0, len(data)
    sync_err = 0
    truncated = False
    while pos + 24 <= n:
        if data[pos : pos + 2] != SYNC_BYTES:
            nxt = data.find(SYNC_BYTES, pos + 1)
            sync_err += 1
            if nxt < 0:
                break
            pos = nxt
            continue
        (_sync, ch, plen, dlen, ver, seq, flags, dtype, rtc6, hcs) = _HDR.unpack_from(data, pos)
        words = np.frombuffer(data[pos : pos + 22], dtype="<u2")
        if (int(words.sum(dtype=np.uint64)) & 0xFFFF) != hcs or plen < 24 or plen % 4:
            sync_err += 1
            errors.append(f"bad header at offset {pos}")
            nxt = data.find(SYNC_BYTES, pos + 1)
            if nxt < 0:
                break
            pos = nxt
            continue
        if pos + plen > n:
            truncated = True
            errors.append(f"packet at offset {pos} runs past the end of the data ({plen} B)")
            break
        body_start = pos + 24 + (12 if flags & 0x80 else 0)
        ok = _checksum_ok(data, body_start, body_start + dlen, pos + plen, flags & 0x3)
        pkts.append(
            Packet(
                pos, ch, plen, dlen, ver, seq, flags, dtype, int.from_bytes(rtc6, "little"), body_start, ok
            )
        )
        pos += plen
    if 0 < n - pos < 24 and not truncated:
        truncated = True
        errors.append(f"{n - pos} trailing bytes")
    return Ch10File(data, tuple(pkts), sync_err, truncated, tuple(errors))


# ------------------------------------------------------------------------------------------------ time F1
@dataclass(frozen=True)
class TimeRecords:
    rtc: np.ndarray  # int64
    utc_ms: (
        np.ndarray
    )  # int64 ms since 1970 (month/year format) or ms since Jan 1 of an unknown year (day format)
    fmt: np.ndarray
    src: np.ndarray
    day_format: np.ndarray  # bool: IRIG day-of-year format (no year)
    sync_error: np.ndarray  # bool (packet RTC sync error)


def _bcd(v: int, shift: int, width: int) -> int:
    return (v >> shift) & ((1 << width) - 1)


def _time_ms(words: tuple[int, ...], month_year: bool) -> tuple[int, bool]:
    import datetime as dt

    w1, w2, w3 = words[0], words[1], words[2]
    ms = 100 * _bcd(w1, 4, 4) + 10 * _bcd(w1, 0, 4)
    s = 10 * _bcd(w1, 12, 3) + _bcd(w1, 8, 4)
    mi = 10 * _bcd(w2, 4, 3) + _bcd(w2, 0, 4)
    h = 10 * _bcd(w2, 12, 2) + _bcd(w2, 8, 4)
    tod = ((h * 60 + mi) * 60 + s) * 1000 + ms
    if month_year:
        w4 = words[3]
        day = 10 * _bcd(w3, 4, 4) + _bcd(w3, 0, 4)
        month = 10 * _bcd(w3, 12, 1) + _bcd(w3, 8, 4)
        year = 1000 * _bcd(w4, 12, 2) + 100 * _bcd(w4, 8, 4) + 10 * _bcd(w4, 4, 4) + _bcd(w4, 0, 4)
        days = (dt.date(year, month, day) - dt.date(1970, 1, 1)).days
        return days * 86_400_000 + tod, False
    doy = 100 * _bcd(w3, 8, 2) + 10 * _bcd(w3, 4, 4) + _bcd(w3, 0, 4)
    return (doy - 1) * 86_400_000 + tod, True


def read_time(f: Ch10File) -> TimeRecords:
    rows = []
    for p in f.of_type(0x11):
        if not p.checksum_ok:
            continue
        b = f.body(p)
        csdw = struct.unpack_from("<I", b, 0)[0]
        month_year = bool((csdw >> 9) & 1)
        nwords = 4 if month_year else 3
        words = struct.unpack_from(f"<{nwords}H", b, 4)
        ms, day_fmt = _time_ms(words, month_year)
        rows.append((p.rtc, ms, (csdw >> 4) & 0xF, csdw & 0xF, day_fmt, p.rtc_sync_error))
    a = np.array(rows, dtype=np.int64).reshape(-1, 6)
    return TimeRecords(a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4].astype(bool), a[:, 5].astype(bool))


# ------------------------------------------------------------------------------------------------ 1553 F1
@dataclass(frozen=True)
class Ms1553Messages:
    """Every 1553 message of the selected packets, in file order."""

    packet: np.ndarray  # index into the packets list passed in
    msg_index: np.ndarray  # message index inside its packet
    ipts: np.ndarray  # int64 RTC
    bsw: np.ndarray
    gap: np.ndarray
    length: np.ndarray  # bytes
    word_start: np.ndarray  # index into words of the first word
    words: np.ndarray  # uint16, all messages concatenated
    ttb: np.ndarray  # per packet


@njit(cache=True)
def _walk_1553(buf, starts, counts, ends):  # pragma: no cover - compiled
    total = 0
    for k in range(starts.size):
        total += counts[k]
    pk = np.empty(total, np.int64)
    mi = np.empty(total, np.int64)
    ipts = np.empty(total, np.int64)
    bsw = np.empty(total, np.int64)
    gap = np.empty(total, np.int64)
    ln = np.empty(total, np.int64)
    off = np.empty(total, np.int64)
    j = 0
    for k in range(starts.size):
        pos = starts[k]
        for m in range(counts[k]):
            if pos + 14 > ends[k]:
                return pk[:j], mi[:j], ipts[:j], bsw[:j], gap[:j], ln[:j], off[:j], False
            t = np.int64(0)
            for b in range(6):
                t |= np.int64(buf[pos + b]) << np.int64(8 * b)
            pk[j] = k
            mi[j] = m
            ipts[j] = t
            bsw[j] = np.int64(buf[pos + 8]) | (np.int64(buf[pos + 9]) << 8)
            gap[j] = np.int64(buf[pos + 10]) | (np.int64(buf[pos + 11]) << 8)
            length = np.int64(buf[pos + 12]) | (np.int64(buf[pos + 13]) << 8)
            ln[j] = length
            off[j] = pos + 14
            pos += 14 + length + (length % 2)
            if pos > ends[k]:
                return pk[:j], mi[:j], ipts[:j], bsw[:j], gap[:j], ln[:j], off[:j], False
            j += 1
    return pk, mi, ipts, bsw, gap, ln, off, True


def read_ms1553(f: Ch10File, packets: tuple[Packet, ...]) -> Ms1553Messages:
    """Decode the messages of 1553 F1 ``packets`` (filter out packets with a bad data checksum first)."""
    buf = np.frombuffer(f.data, dtype=np.uint8)
    starts = np.array([p.body_start + 4 for p in packets], dtype=np.int64)
    ends = np.array([p.body_start + p.data_length for p in packets], dtype=np.int64)
    csdw = [struct.unpack_from("<I", f.data, p.body_start)[0] for p in packets]
    counts = np.array([c & 0xFFFFFF for c in csdw], dtype=np.int64)
    ttb = np.array([(c >> 30) & 0x3 for c in csdw], dtype=np.int64)
    if not packets:
        z = np.zeros(0, np.int64)
        return Ms1553Messages(z, z, z, z, z, z, z, np.zeros(0, np.uint16), z)
    pk, mi, ipts, bsw, gap, ln, off, ok = _walk_1553(buf, starts, counts, ends)
    if not ok:
        raise ValueError("malformed 1553 packet (message runs past the packet body)")
    nw = ln // 2
    idx = np.repeat(off, nw) + 2 * (
        np.arange(int(nw.sum()), dtype=np.int64) - np.repeat(np.cumsum(nw) - nw, nw)
    )
    words = (buf[idx].astype(np.uint16) | (buf[idx + 1].astype(np.uint16) << 8)).astype(np.uint16)
    word_start = np.cumsum(nw) - nw
    return Ms1553Messages(pk, mi, ipts, bsw, gap, ln, word_start.astype(np.int64), words, ttb)


# ------------------------------------------------------------------------------------------------ 429 F0
@dataclass(frozen=True)
class Arinc429Words:
    packet: np.ndarray
    msg_index: np.ndarray
    rtc: np.ndarray  # word start: packet RTC + cumulative gap times (0.1 us = 1 RTC tick)
    bus: np.ndarray
    high_speed: np.ndarray
    parity_error: np.ndarray
    word: np.ndarray  # uint32 bus order


def read_arinc429(f: Ch10File, packets: tuple[Packet, ...]) -> Arinc429Words:
    parts = []
    for k, p in enumerate(packets):
        b = f.body(p)
        n = struct.unpack_from("<I", b, 0)[0] & 0xFFFF
        a = np.frombuffer(b, dtype="<u4", count=2 * n, offset=4).reshape(n, 2)
        ids = a[:, 0].astype(np.int64)
        gaps = ids & 0xFFFFF
        parts.append(
            (
                np.full(n, k, np.int64),
                np.arange(n, dtype=np.int64),
                p.rtc + np.cumsum(gaps),
                ids >> 24,
                (ids >> 21) & 1,
                (ids >> 22) & 1,
                a[:, 1].astype(np.uint32),
            )
        )
    if not parts:
        z = np.zeros(0, np.int64)
        return Arinc429Words(z, z, z, z, z, z, np.zeros(0, np.uint32))
    cols = [np.concatenate([p[i] for p in parts]) for i in range(7)]
    return Arinc429Words(*cols)


# ------------------------------------------------------------------------------------------------ PCM F1
@dataclass(frozen=True)
class PcmFrames:
    packet: np.ndarray
    msg_index: np.ndarray
    ipts: np.ndarray
    words16: np.ndarray  # (n, k) uint16 per minor frame (unpacked mode)


def read_pcm_unpacked(f: Ch10File, packets: tuple[Packet, ...], frame_words: int) -> PcmFrames:
    """Unpacked, 16-bit aligned PCM F1 packets with an IPH per minor frame of ``frame_words`` 16-bit words."""
    parts = []
    for k, p in enumerate(packets):
        b = f.body(p)
        csdw = struct.unpack_from("<I", b, 0)[0]
        if not (csdw >> 30) & 1 or not (csdw >> 18) & 1 or (csdw >> 21) & 1:
            raise ValueError("only unpacked, 16-bit aligned PCM packets with IPH are supported")
        rec = 5 + frame_words
        nf = (len(b) - 4) // (2 * rec)
        a = np.frombuffer(b, dtype="<u2", count=nf * rec, offset=4).reshape(nf, rec).astype(np.int64)
        ipts = a[:, 0] | (a[:, 1] << 16) | (a[:, 2] << 32)
        parts.append(
            (np.full(nf, k, np.int64), np.arange(nf, dtype=np.int64), ipts, a[:, 5:].astype(np.uint16))
        )
    if not parts:
        z = np.zeros(0, np.int64)
        return PcmFrames(z, z, z, np.zeros((0, frame_words), np.uint16))
    return PcmFrames(*[np.concatenate([p[i] for p in parts]) for i in range(4)])


# ------------------------------------------------------------------------------------------------ events
@dataclass(frozen=True)
class EventEntries:
    rtc: np.ndarray
    number: np.ndarray
    count: np.ndarray
    occurred_recording: np.ndarray


def read_events(f: Ch10File) -> EventEntries:
    parts = []
    for p in f.of_type(0x02):
        if not p.checksum_ok:
            continue
        b = f.body(p)
        csdw = struct.unpack_from("<I", b, 0)[0]
        n = csdw & 0xFFF
        width = 5 if (csdw >> 31) & 1 else 3  # IPTS (2), optional IPDH (2), entry (1) long words
        a = np.frombuffer(b, dtype="<u4", count=width * n, offset=4).reshape(n, width).astype(np.int64)
        e = a[:, width - 1]
        parts.append((a[:, 0] | (a[:, 1] << 32), e & 0xFFF, (e >> 12) & 0xFFFF, (e >> 28) & 1))
    if not parts:
        z = np.zeros(0, np.int64)
        return EventEntries(z, z, z, z)
    return EventEntries(*[np.concatenate([p[i] for p in parts]) for i in range(4)])


# ---------------------------------------------------------------------------------------- discrete / analog
@dataclass(frozen=True)
class DiscreteEvents:
    rtc: np.ndarray
    states: np.ndarray  # uint32
    bits: np.ndarray  # LENGTH field per packet event (32 for 0)
    on_change: np.ndarray  # bool


def read_discrete(f: Ch10File, packets: tuple[Packet, ...]) -> DiscreteEvents:
    """Discrete F1 (§10.6.6.2): CSDW (LENGTH 7-3, MODE 2-0), then per event an IPTS and 32-bit states."""
    parts = []
    for p in packets:
        b = f.body(p)
        csdw = struct.unpack_from("<I", b, 0)[0]
        n = (len(b) - 4) // 12
        a = np.frombuffer(b, dtype="<u4", count=3 * n, offset=4).reshape(n, 3).astype(np.int64)
        length = (csdw >> 3) & 0x1F
        parts.append(
            (
                a[:, 0] | (a[:, 1] << 32),
                a[:, 2].astype(np.uint32),
                np.full(n, length or 32),
                np.full(n, (csdw & 1) == 0),
            )
        )
    if not parts:
        z = np.zeros(0, np.int64)
        return DiscreteEvents(z, np.zeros(0, np.uint32), z, np.zeros(0, bool))
    return DiscreteEvents(*[np.concatenate([p[i] for p in parts]) for i in range(4)])


@dataclass(frozen=True)
class AnalogSamples:
    rtc: np.ndarray  # packet time = first sample (§10.6.5.2: no IPH)
    subchannel: np.ndarray
    bits: np.ndarray
    samples: tuple[np.ndarray, ...]  # per packet


def read_analog(f: Ch10File, packets: tuple[Packet, ...]) -> AnalogSamples:
    """Analog F1 (§10.6.5.2), single subchannel with SAME = 1 and unpacked 16-bit samples only."""
    rtc, sub, bits, samples = [], [], [], []
    for p in packets:
        b = f.body(p)
        csdw = struct.unpack_from("<I", b, 0)[0]
        if not (csdw >> 28) & 1 or (csdw & 0x3) != 0b01:
            raise ValueError("only SAME, unpacked analog packets are supported")
        rtc.append(p.rtc)
        sub.append((csdw >> 8) & 0xFF)
        bits.append((csdw >> 2) & 0x3F)
        samples.append(np.frombuffer(b, dtype="<u2", offset=4).astype(np.uint16))
    return AnalogSamples(
        np.array(rtc, np.int64), np.array(sub, np.int64), np.array(bits, np.int64), tuple(samples)
    )
