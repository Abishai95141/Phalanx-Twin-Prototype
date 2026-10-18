"""Independent Ch10 reader robustness and cumulative sequence counting (M17; AD-38)."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.ground.decoder import cumulative_sequence
from phalanx.ground.decoder import reader as rd
from phalanx.recorder import ch10


def _file(n_data: int = 300) -> bytes:
    """TMATS + time + n_data 1553 packets on channel 3 (sequence numbers wrap after 255)."""
    parts = [
        ch10.packet(0, 1, 0, 0, ch10.tmats_body("G\\PN:T;\n"), checksum=2),
        ch10.packet(1, 0x11, 0, 0, ch10.time_body(1_790_000_000_000, fmt=0, src=1), checksum=2),
    ]
    for k in range(n_data):
        words = np.array([0x0C20 + (k % 3), 0x0800, k & 0xFFFF], dtype=np.uint16)
        body = ch10.ms1553_body(
            0,
            np.array([1000 + 10 * k]),
            np.zeros(1, np.uint16),
            np.zeros(1, np.uint16),
            words,
            np.array([0, 3]),
        )
        parts.append(ch10.packet(3, 0x19, k & 0xFF, 1000 + 10 * k, body))
    return b"".join(parts)


def test_clean_file_reads_completely():
    f = rd.read_file(_file())
    assert len(f.packets) == 302 and f.sync_errors == 0 and not f.truncated
    assert all(p.checksum_ok for p in f.packets)
    seq = [p.seq for p in f.packets if p.channel_id == 3]
    assert seq[255] == 255 and seq[256] == 0  # 8-bit wrap
    cum = cumulative_sequence(
        np.array([p.channel_id for p in f.packets]), np.array([p.seq for p in f.packets])
    )
    assert cum[2:].tolist() == list(range(300))


def test_corrupt_packet_is_dropped_but_later_counts_do_not_move():
    data = bytearray(_file())
    f0 = rd.read_file(bytes(data))
    victim = f0.packets[100]
    data[victim.body_start + 6] ^= 0x5A  # flip bits inside a data word
    f = rd.read_file(bytes(data))
    assert len(f.packets) == len(f0.packets) and not f.packets[100].checksum_ok
    cum = cumulative_sequence(
        np.array([p.channel_id for p in f.packets]), np.array([p.seq for p in f.packets])
    )
    assert cum[2:].tolist() == list(range(300))


def test_lost_packet_still_advances_the_cumulative_count():
    f0 = rd.read_file(_file())
    keep = [p for k, p in enumerate(f0.packets) if k != 150]  # packet 148 of channel 3 lost in transfer
    data = b"".join(f0.data[p.offset : p.offset + p.packet_length] for p in keep)
    f = rd.read_file(data)
    cum = cumulative_sequence(
        np.array([p.channel_id for p in f.packets]), np.array([p.seq for p in f.packets])
    )
    assert cum[2:].tolist() == [*range(148), *range(149, 300)]  # ids after the gap are unchanged


def test_truncated_transfer_and_garbage_prefix():
    data = _file()
    f = rd.read_file(data[: len(data) - 7])
    assert f.truncated and len(f.packets) == 301
    g = rd.read_file(b"\x00\x25\x99garbage" + data)
    assert g.sync_errors >= 1 and len(g.packets) == 302 and g.packets[0].data_type == 1
    bad_body = bytearray(data)
    bad_body[30] ^= 0xFF  # a byte of the setup-record body: its 16-bit data checksum fails
    assert not rd.read_file(bytes(bad_body)).packets[0].checksum_ok
    bad_header = bytearray(data)
    bad_header[4] ^= 0x01  # packet-length field: the header checksum fails -> resynchronise on the next sync
    h = rd.read_file(bytes(bad_header))
    assert h.sync_errors >= 1 and len(h.packets) == 301 and h.packets[0].data_type == 0x11


@settings(max_examples=100, deadline=None)
@given(st.lists(st.integers(min_value=1, max_value=255), min_size=1, max_size=60), st.integers(0, 255))
def test_cumulative_sequence_unwraps_any_gap_pattern(steps, start):
    """Property: the cumulative count advances by each gap (mod 256, gaps 1..255) and never decreases."""
    seq8 = (start + np.concatenate([[0], np.cumsum(steps)])) % 256
    cum = cumulative_sequence(np.full(seq8.size, 7), seq8)
    assert cum[0] == start
    assert np.array_equal(np.diff(cum), np.array(steps))
