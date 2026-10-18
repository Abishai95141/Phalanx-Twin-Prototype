"""Ch10 packet encoders (M16) checked by two independent parsers: pyChapter10 and the M17 reader (A3 part).

Each packet type the recorder writes (TMATS, time, 1553, ARINC-429, PCM, recording event, index, analog,
discrete) is built here from hand-chosen field values and parsed back by both readers; golden BCD time words
come from IRIG 106-15 Figure 10-21 arithmetic.
"""

from __future__ import annotations

import io
import struct
from datetime import datetime

import numpy as np
import pytest
from chapter10 import C10

from phalanx.ground.decoder import reader as rd
from phalanx.recorder import ch10


def _pc10(data: bytes):
    return list(C10(io.BytesIO(data)))


def _ours(data: bytes) -> rd.Ch10File:
    f = rd.read_file(data)
    assert not f.truncated and f.sync_errors == 0
    return f


@pytest.mark.parametrize("checksum", [0, 1, 2, 3])
def test_header_length_alignment_and_checksums(checksum):
    body = struct.pack("<I", 7) + bytes(range(13))  # odd body length forces filler
    pk = ch10.packet(5, 0x00, 300, 0x0123456789AB, body, checksum=checksum)
    assert len(pk) % 4 == 0
    sync, chid, plen, dlen, ver, seq, flags, dtype = struct.unpack_from("<HHIIBBBB", pk)
    assert (sync, chid, plen, dlen, ver, seq, flags & 3, dtype) == (
        0xEB25,
        5,
        len(pk),
        17,
        3,
        300 & 0xFF,
        checksum,
        0,
    )
    assert int.from_bytes(pk[16:22], "little") == 0x0123456789AB
    hsum = sum(struct.unpack_from("<11H", pk)) & 0xFFFF
    assert struct.unpack_from("<H", pk, 22)[0] == hsum
    f = _ours(pk)
    assert f.packets[0].checksum_ok and f.packets[0].rtc == 0x0123456789AB
    p = _pc10(pk)[0]  # pyChapter10 validates the header checksum
    assert p.packet_length == len(pk) and p.data_length == 17 and p.sequence_number == 300 & 0xFF
    bad = bytearray(pk)
    bad[24 + 6] ^= 0xFF
    assert rd.read_file(bytes(bad)).packets[0].checksum_ok == (checksum == 0)


def test_golden_time_words_and_both_parsers():
    """2026-09-21 09:07:43.120 UTC -> BCD words of Figure 10-21; both parsers recover the instant."""
    utc_ms = (
        int((datetime(2026, 9, 21) - datetime(1970, 1, 1)).total_seconds()) * 1000
        + ((9 * 60 + 7) * 60 + 43) * 1000
        + 120
    )
    w = ch10.bcd_time_words(utc_ms)
    assert w == (0x4312, 0x0907, 0x0921, 0x2026)
    pk = ch10.packet(1, ch10.DT_TIME_F1, 0, 10_000, ch10.time_body(utc_ms, fmt=0, src=1), checksum=2)
    tr = rd.read_time(_ours(pk))
    assert tr.utc_ms.tolist() == [utc_ms] and tr.src.tolist() == [1] and tr.fmt.tolist() == [0]
    p = _pc10(pk)[0]
    assert p.time == datetime(2026, 9, 21, 9, 7, 43, 120000)
    assert p.time_source == 1 and p.time_format == 0 and p.date_format == 1 and p.leap == 0


def test_ms1553_packet_both_parsers():
    words = np.array([0x2C4F, 0x2800, 0x0001, 0xFFFF, 0x1234, 0x0C20, 0x0800], dtype=np.uint16)
    offs = np.array([0, 5, 7], dtype=np.int64)  # message 0: cmd, status, 3 data; message 1: cmd, status
    ipts = np.array([1_000_000, 1_000_500], dtype=np.uint64)
    body = ch10.ms1553_body(
        0, ipts, np.array([0, 1 << 9], np.uint16), np.array([62, 0], np.uint16), words, offs
    )
    pk = ch10.packet(3, ch10.DT_MS1553_F1, 7, 1_000_000, body)
    f = _ours(pk)
    m = rd.read_ms1553(f, f.packets)
    assert (
        m.ipts.tolist() == [1_000_000, 1_000_500] and m.bsw.tolist() == [0, 512] and m.gap.tolist() == [62, 0]
    )
    assert m.length.tolist() == [10, 4] and m.words.tolist() == words.tolist() and m.ttb.tolist() == [0]
    p = _pc10(pk)[0]
    msgs = list(p)
    assert p.count == 2 and p.time_tag_bits == 0
    assert [x.ipts for x in msgs] == [1_000_000, 1_000_500]
    assert [x.timeout for x in msgs] == [0, 1] and [x.gap_time for x in msgs] == [62, 0]
    assert b"".join(x.data for x in msgs) == words.astype("<u2").tobytes()


def test_arinc429_packet_both_parsers():
    w = np.array([0xE001119D, 0x12345678, 0x0], dtype=np.uint32)
    gaps = np.array([0, 3600, 400000], dtype=np.int64)
    pk = ch10.packet(
        6,
        ch10.DT_ARINC429_F0,
        0,
        2_000_000,
        ch10.arinc429_body(np.zeros(3, np.uint32), np.array([1, 1, 0]), gaps, w),
    )
    f = _ours(pk)
    a = rd.read_arinc429(f, f.packets)
    assert a.word.tolist() == w.tolist() and a.rtc.tolist() == (2_000_000 + np.cumsum(gaps)).tolist()
    assert a.high_speed.tolist() == [1, 1, 0]
    msgs = list(_pc10(pk)[0])
    assert [m.gap_time for m in msgs] == gaps.tolist()
    assert [m.bus_speed for m in msgs] == [1, 1, 0]
    assert [int.from_bytes(m.data, "little") for m in msgs] == w.tolist()


def test_pcm_unpacked_packet_header_and_frames():
    frames = np.array([[0xFAF, 0x320, 1, 2, 3], [0xFAF, 0x320, 4, 5, 6]], dtype=np.uint16)
    pk = ch10.packet(7, ch10.DT_PCM_F1, 0, 5000, ch10.pcm_unpacked_body(np.array([5000, 5200]), frames))
    f = _ours(pk)
    fr = rd.read_pcm_unpacked(f, f.packets, 5)
    assert fr.ipts.tolist() == [5000, 5200] and np.array_equal(fr.words16, frames)
    csdw = struct.unpack_from("<I", pk, 24)[0]
    # IRIG 106-15 Figure 10-15: R(31) IPH(30) MA(29) MI(28) LOCKST(27-24) MODE(23-18: unpacked = bit 18)
    assert csdw == (1 << 30) | (1 << 29) | (1 << 28) | (0xF << 24) | (1 << 18)
    p = _pc10(pk)[0]  # pyChapter10 reads the packet (header, checksum, mode bits) ...
    assert (p.iph, p.unpacked, p.packed, p.throughput, p.alignment) == (1, 1, 0, 0, 0)
    # ... but its CSDW layout is one bit off the standard text for the lock-status/indicator fields (it writes
    # IPH at bit 31): a known pyChapter10 1.1.19 deviation, reported in the W1.7 report; we follow
    # the standard.
    from chapter10.pcm import PCMF1

    own = PCMF1(
        channel_id=7,
        data_type=9,
        iph=1,
        unpacked=1,
        minor_frame_status=3,
        major_frame_status=3,
        minor_frame_indicator=1,
        major_frame_indicator=1,
    )
    assert struct.unpack_from("<I", bytes(own), 24)[0] != csdw


def test_event_and_index_packets_both_parsers():
    ev = ch10.packet(
        8, ch10.DT_COMPUTER_F2, 0, 77, ch10.event_body(np.array([77, 99]), np.array([0, 2]), np.array([0, 5]))
    )
    f = _ours(ev)
    e = rd.read_events(f)
    assert e.rtc.tolist() == [77, 99] and e.number.tolist() == [0, 2] and e.count.tolist() == [0, 5]
    # IRIG 106-15 Figure 10-40: EO bit 28, event count bits 27-12, event number bits 11-0
    assert struct.unpack_from("<I", ev, 24 + 4 + 8 + 12)[0] == (1 << 28) | (5 << 12) | 2
    p = _pc10(ev)[0]
    msgs = list(p)
    assert p.count == 2 and [m.ipts for m in msgs] == [
        77,
        99,
    ]  # pyChapter10 agrees on count and time tags ...
    # ... but packs the entry word differently from Figure 10-40 (a pyChapter10 1.1.19 deviation, reported).
    from chapter10.computer import ComputerF2

    own = ComputerF2(channel_id=8, data_type=2)
    own.append(own.Message(ipts=99, number=2, count=5, occurrence=1))
    own.count = 1
    assert struct.unpack_from("<I", bytes(own), 24 + 4 + 8)[0] != (1 << 28) | (5 << 12) | 2
    node = ch10.packet(
        9,
        ch10.DT_COMPUTER_F3,
        0,
        10,
        ch10.index_node_body(
            np.array([10, 20]), np.array([1, 8]), np.array([0x11, 0x02]), np.array([100, 200])
        ),
    )
    n = _pc10(node)[0]
    assert n.index_type == 1 and [(m.ipts, m.channel_id, m.data_type, m.offset) for m in n] == [
        (10, 1, 0x11, 100),
        (20, 8, 0x02, 200),
    ]
    root = ch10.packet(
        9, ch10.DT_COMPUTER_F3, 1, 30, ch10.index_root_body(np.array([10]), np.array([400]), 30, 999)
    )
    r = _pc10(root)[0]
    assert r.index_type == 0 and [(m.ipts, m.offset) for m in r] == [(10, 400)]
    # Table 10-33: the root packet ends with its own entry (IPTS, then the root index offset)
    body_end = 24 + struct.unpack_from("<I", root, 8)[0]
    assert struct.unpack_from("<QQ", root, body_end - 16) == (30, 999)
    # pyChapter10 1.1.19 reads root_offset at data_length - 8 from the start of the *packet* (it omits the
    # 24-byte
    # header), so its value is not the root offset: a pyChapter10 deviation, reported in the W1.7 report.
    assert r.root_offset != 999


def test_analog_and_discrete_packets_both_parsers():
    samples = np.array([0, 1, 4095, 2048], dtype=np.uint16)
    an = ch10.packet(10, ch10.DT_ANALOG_F1, 0, 123, ch10.analog_body(samples, bits=12, subchannel=1))
    a = rd.read_analog(_ours(an), _ours(an).packets)
    assert a.bits.tolist() == [12] and a.samples[0].tolist() == samples.tolist()
    p = _pc10(an)[0]
    assert p.length == 12 and p.same == 1 and p.subchannel == 1
    di = ch10.packet(
        11, ch10.DT_DISCRETE_F1, 0, 50, ch10.discrete_body(np.array([50, 60]), np.array([0b101, 0xFFFFFFFF]))
    )
    f = _ours(di)
    dd = rd.read_discrete(f, f.packets)
    assert (
        dd.rtc.tolist() == [50, 60] and dd.states.tolist() == [5, 0xFFFFFFFF] and dd.bits.tolist() == [32, 32]
    )
    msgs = list(_pc10(di)[0])
    assert [m.ipts for m in msgs] == [50, 60] and [int.from_bytes(m.data, "little") for m in msgs] == [
        5,
        2**32 - 1,
    ]


def test_tmats_packet_both_parsers():
    pk = ch10.packet(0, ch10.DT_COMPUTER_F1, 0, 0, ch10.tmats_body("G\\PN:X;\nR-1\\ID:Y;\n"), checksum=2)
    p = _pc10(pk)[0]
    assert p.version == 7 and p["G"] and p.data.endswith(b"R-1\\ID:Y;\n")
    assert _ours(pk).body(_ours(pk).packets[0])[4:].decode() == "G\\PN:X;\nR-1\\ID:Y;\n"


def test_writer_rejects_bad_fields():
    with pytest.raises(ValueError):
        ch10.packet(1 << 16, 0, 0, 0, b"\0\0\0\0")
    with pytest.raises(ValueError):
        ch10.packet(1, 0, 0, 1 << 48, b"\0\0\0\0")
    with pytest.raises(ValueError):
        ch10.packet(1, 0x19, 0, 0, b"\0" * ch10.MAX_PACKET_BYTES)
