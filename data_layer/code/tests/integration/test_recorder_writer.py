"""M16 recordings: IRIG 106 Ch10 structure rules and agreement of two independent parsers (W1.7 A3).

Sample (stated before running): one 30 s recording of 6 channels on both buses, both ARINC links and the FTI
stream: >300 packets on the busiest channel, so the 8-bit sequence number wraps at least once, and 3 node
index packets. TEST FIXTURE CIR.
"""

from __future__ import annotations

import io
import struct

import numpy as np
import pytest
from chapter10 import C10
from test_bus_cir_fixture import EPOCH, IDENT, make_cir, rng_service

from phalanx.bus.encoder import BusConfig, encode_bus
from phalanx.bus.icd import BusIcd
from phalanx.dictionary import load_dictionary
from phalanx.ground.decoder import reader as rd
from phalanx.recorder.writer import RecorderConfig, write_recording

D = load_dictionary()
ICD = BusIcd.from_dictionary(D)
T0 = EPOCH + 200 * 10**9
T1 = T0 + 30 * 10**9
CHANS = ["FCS.VOTED.NZ", "AD.AOA", "NAV.INS.PITCH", "ENG.N2.V", "CWS.MASTER", "NAV.RADALT", "AD.BOOM.ALPHA"]


@pytest.fixture(scope="module")
def rec():
    cir = make_cir(CHANS, T0 - 10**9, T1)
    rng = rng_service()
    tr = encode_bus(cir, ICD, BusConfig.from_params(), IDENT, rng, t0=T0, t1=T1, fti_fitted=True)
    return write_recording(tr, IDENT, rng, RecorderConfig.from_params(lock_loss_rate_per_h=0.0))


def test_file_order_rules(rec):
    p = rec.packets
    assert p.data_type[0] == 0x01 and p.channel_id[0] == 0  # setup record first (§10.5.1 a)
    dynamic = np.flatnonzero(p.data_type != 0x01)
    assert p.data_type[dynamic[0]] == 0x11  # the first dynamic packet is a time packet (§10.5.1 b)
    assert p.data_type[-1] == 0x03  # root index last (§10.6.7.4 a)
    tt = p.rtc[p.data_type == 0x11]
    assert np.all(np.diff(tt) <= 10_000_000 * (1 + 1e-4))  # time packets at >= 1 Hz
    assert np.all(p.offset == np.concatenate([[0], np.cumsum(p.length)[:-1]]))
    assert len(rec.data) == int(p.offset[-1] + p.length[-1])


def test_packets_hold_at_most_100_ms(rec):
    f = rd.read_file(rec.data)
    for chid in rec.channels.mil1553.values():
        pk = f.of_type(0x19, chid)
        m = rd.read_ms1553(f, pk)
        for k in range(len(pk)):
            ip = m.ipts[m.packet == k]
            assert ip.max() - ip.min() < 1_000_000
    for chid in rec.channels.arinc429.values():
        pk = f.of_type(0x38, chid)
        a = rd.read_arinc429(f, pk)
        for k in range(len(pk)):
            r = a.rtc[a.packet == k]
            assert r.max() - r.min() < 1_000_000 and r.min() == pk[k].rtc  # header time = first word


def test_sequence_numbers_wrap_and_count_cumulatively(rec):
    p = rec.packets
    busiest = np.bincount(p.channel_id).argmax()
    sel = p.channel_id == busiest
    assert sel.sum() > 256
    seq = p.seq[sel]
    assert np.array_equal(seq, np.arange(sel.sum()) % 256)
    assert np.array_equal(p.cum_seq[sel], np.arange(sel.sum()))


def test_index_packets_cover_every_time_and_event_packet(rec):
    f = rd.read_file(rec.data)
    root = f.packets[-1]
    body = f.body(root)
    n = struct.unpack_from("<I", body, 0)[0] & 0xFFFF
    entries = np.frombuffer(body, dtype="<u8", offset=4).reshape(-1, 2)
    assert entries.shape[0] == n + 1 and int(entries[-1, 1]) == root.offset  # root points at itself
    covered = set()
    for _ipts, off in entries[:-1].tolist():
        node = next(pk for pk in f.packets if pk.offset == off)
        assert node.data_type == 0x03
        nb = f.body(node)
        assert struct.unpack_from("<I", nb, 0)[0] >> 31 == 1  # node index
        rec5 = np.frombuffer(nb, dtype="<u4", offset=4).reshape(-1, 5)
        for e in rec5.tolist():
            target = next(pk for pk in f.packets if pk.offset == e[3] | (e[4] << 32))
            assert target.channel_id == (e[2] & 0xFFFF) and target.data_type == (e[2] >> 16) & 0xFF
            assert target.rtc == e[0] | (e[1] << 32)
            covered.add(target.offset)
    must = {pk.offset for pk in f.packets if pk.data_type in (0x11, 0x02)}
    assert must <= covered


def test_a3_two_independent_parsers_agree_on_the_whole_file(rec):
    """pyChapter10 and the M17 reader see the same packets, headers, 1553 messages, ARINC words and times."""
    ours = rd.read_file(rec.data)
    theirs = list(C10(io.BytesIO(rec.data)))
    assert len(theirs) == len(ours.packets) == rec.packets.offset.size
    for a, b in zip(ours.packets, theirs, strict=True):
        assert (a.channel_id, a.data_type, a.seq, a.rtc, a.packet_length, a.data_length) == (
            b.channel_id,
            b.data_type,
            b.sequence_number,
            b.rtc,
            b.packet_length,
            b.data_length,
        )
    for chid in rec.channels.mil1553.values():
        pk = ours.of_type(0x19, chid)
        m = rd.read_ms1553(ours, pk)
        tm = [x for b in theirs if b.channel_id == chid and b.data_type == 0x19 for x in b]
        assert [x.ipts for x in tm] == m.ipts.tolist()
        assert [x.gap_time for x in tm] == m.gap.tolist()
        assert b"".join(x.data for x in tm) == m.words.astype("<u2").tobytes()
    for chid in rec.channels.arinc429.values():
        a = rd.read_arinc429(ours, ours.of_type(0x38, chid))
        tw = [x for b in theirs if b.channel_id == chid and b.data_type == 0x38 for x in b]
        assert [int.from_bytes(x.data, "little") for x in tw] == a.word.tolist()
    t_ours = rd.read_time(ours)
    t_theirs = [b.time for b in theirs if b.data_type == 0x11]
    import datetime as dt

    assert [
        round((x - dt.datetime(1970, 1, 1)).total_seconds() * 1000) for x in t_theirs
    ] == t_ours.utc_ms.tolist()


def test_proxy_single_recording_has_no_sink_subsets(rec):
    """PROXY A-W1.7-11 exposed: AD.AOA belongs to the CDR at CDR4 (4 Hz) and ECMS10, yet the single
    bus-monitor
    recording carries it at its bus rate (AV25) and there is one RTC for all sinks: per-sink subsets, rates
    and
    clocks (AD-25) are not realised. This test fails once separate sink recordings exist."""
    sinks = {s["sink"]: s["group"] for s in D.channel("AD.AOA")["sinks"]}
    assert sinks.get("CDR") == "CDR4"
    f = rd.read_file(rec.data)
    m = rd.read_ms1553(f, f.of_type(0x19, rec.channels.mil1553["AV-MUX-2"]))
    cmd = m.words[m.word_start]
    sa3 = cmd == next(x for x in ICD.messages if x.msg_id == "AV-MUX-2/RT01/T/SA03").command_word
    rate = sa3.sum() / 30.0
    assert abs(rate - 25.0) < 0.5  # bus rate, not the CDR's 4 Hz
    assert len({pk.channel_id for pk in f.packets if pk.data_type == 0x11}) == 1  # one recorder clock
