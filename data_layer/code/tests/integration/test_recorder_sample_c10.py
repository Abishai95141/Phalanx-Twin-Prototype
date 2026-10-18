"""The public Ch10 sample (KC-135 operational check recording, pyChapter10 tests/sample.c10, BSD licence):
conformance of our reader and writer conventions (W1.7 A3), real-file decoding (A7), and the measurements that
back the TRANSFER parameters in M15.yaml / M16.yaml.

Data: read-only, outside the repo (``PHALANX_CH10_SAMPLE``, default the research_sources copy). The file is
the
first 1 MiB of the published sample, so its last packet is cut: both readers must stop cleanly there.
n = every packet of the file (99 complete packets, 448 1553 responses): the whole public sample.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pytest
from chapter10 import C10

from phalanx.dictionary import load_dictionary
from phalanx.ground.decoder import DecoderConfig, DecoderError, decode_recording
from phalanx.ground.decoder import reader as rd
from phalanx.ground.decoder.timebase import TimeBase

pytestmark = pytest.mark.data

DEFAULT = "/Users/abishaikc/Phalanx/research_sources/data_pathway/pychapter10_samples/sample.c10"


@pytest.fixture(scope="module")
def sample() -> bytes:
    p = Path(os.environ.get("PHALANX_CH10_SAMPLE", DEFAULT))
    if not p.is_file():
        pytest.skip("public Ch10 sample not available offline")
    return p.read_bytes()


def test_a3_our_reader_agrees_with_pychapter10_on_the_public_sample(sample):
    ours = rd.read_file(sample)
    theirs = list(C10(io.BytesIO(sample)))
    assert len(ours.packets) == len(theirs) == 99
    assert ours.truncated  # the 1 MiB copy cuts the last packet
    for a, b in zip(ours.packets, theirs, strict=True):
        assert (a.channel_id, a.data_type, a.seq, a.rtc, a.packet_length, a.data_length) == (
            b.channel_id,
            b.data_type,
            b.sequence_number,
            b.rtc,
            b.packet_length,
            b.data_length,
        )
        assert a.checksum_ok
    for chid in sorted({p.channel_id for p in ours.packets if p.data_type == 0x19}):
        m = rd.read_ms1553(ours, ours.of_type(0x19, chid))
        tm = [x for b in theirs if b.channel_id == chid and b.data_type == 0x19 for x in b]
        assert [x.ipts for x in tm] == m.ipts.tolist()
        assert b"".join(x.data for x in tm) == m.words.astype("<u2").tobytes()
    for chid in sorted({p.channel_id for p in ours.packets if p.data_type == 0x38}):
        a = rd.read_arinc429(ours, ours.of_type(0x38, chid))
        tw = [x for b in theirs if b.channel_id == chid and b.data_type == 0x38 for x in b]
        assert [int.from_bytes(x.data, "little") for x in tw] == a.word.tolist()
        assert [x.bus for x in tw] == a.bus.tolist()


def test_a3_writer_conventions_match_the_public_sample(sample):
    """Header layout and the conventions our writer chose are those of the real recorder: 1553 time-tag
    bits 01
    (first bit of the command word; raw CSDW 0x40nnnnnn -- pyChapter10 1.1.19 misreads this field as 0),
    32-bit data checksums on 1553 and ARINC-429 packets, 16-bit on the setup record and time packets, data
    type
    version 3 (RCC 106-07) on 1553 and time packets."""
    f = rd.read_file(sample)
    by_type = {}
    for p in f.packets:
        by_type.setdefault(p.data_type, set()).add((p.flags & 3, p.version))
    assert by_type[0x19] == {(3, 3)} and by_type[0x38] == {(3, 2)} and by_type[0x11] == {(2, 3)}
    assert by_type[0x01] == {(2, 3)}
    m = rd.read_ms1553(f, f.of_type(0x19))
    assert set(m.ttb.tolist()) == {1}
    assert {b.time_tag_bits for b in C10(io.BytesIO(sample)) if b.data_type == 0x19} == {0}  # pyChapter10
    from phalanx.recorder.writer import RecorderConfig

    assert RecorderConfig.from_params().ttb == 1


def test_kc135_sample_response_times_back_the_m15_band(sample):
    """M15.yaml rt_response_min/max (5.7/6.3 us) and intermessage_gap (28 us) are these measurements
    (TTB 01: the time tag is the first command bit, so a gap = next tag - end of the previous message)."""
    f = rd.read_file(sample)
    m = rd.read_ms1553(f, f.of_type(0x19))
    g1 = (m.gap & 0xFF) / 10.0
    has_status = g1 > 0
    assert int(has_status.sum()) == 448
    assert np.percentile(g1[has_status], 5) == pytest.approx(5.7, abs=0.05)
    assert np.percentile(g1[has_status], 95) == pytest.approx(6.3, abs=0.05)
    nw = m.length // 2
    end = m.ipts + (20 * nw + np.where(has_status, g1 - 2.0, 0.0)) * 10  # RTC ticks; dead time = GAP1 - 2 us
    same = (m.packet[1:] == m.packet[:-1]) & ((m.bsw[:-1] >> 9) & 1 == 0)
    img = (m.ipts[1:] - end[:-1])[same] / 10.0
    img = img[(img > 0) & (img < 200)]
    assert np.median(img) == pytest.approx(28.2, abs=0.5)


def test_a7_real_sample_decodes_at_bus_level(sample):
    """A7: a real recording decodes: packets, 1553 messages, ARINC words and an absolute time base from its
    IRIG-B time packet (day-of-year format -> flagged CLOCK_SUSPECT: no year in the code)."""
    f = rd.read_file(sample)
    tr = rd.read_time(f)
    assert tr.rtc.size == 1 and tr.day_format.all() and tr.src.tolist() == [1]  # IRIG-B, external
    tb = TimeBase.from_records(tr, rate_tolerance_ppm=100, tail_tolerance_s=2, holdover_tolerance_s=300)
    m = rd.read_ms1553(f, f.of_type(0x19))
    t, fl = tb.best(m.ipts)
    assert m.ipts.size > 400 and fl.suspect.all()
    span = (t.max() - t.min()) / 1e9
    assert 0.2 < span < 1.0  # the 1 MiB copy of the published sample spans ~0.3 s of bus traffic
    assert rd.read_arinc429(f, f.of_type(0x38)).word.size > 1000


def test_a7_param_decoding_refuses_a_recording_of_another_platform(sample):
    """The KC-135 setup record names no Phalanx dictionary: decoding it into param.samples with the Tejas
    dictionary would mean the wrong frame layout (BEA failure mode), so the decoder refuses."""
    with pytest.raises(DecoderError, match="not written against"):
        decode_recording(
            sample,
            dictionary=load_dictionary(),
            tail_no="KC135",
            sortie_id="SAMPLE",
            t_ingest=2**62,
            config=DecoderConfig.from_params(),
        )
