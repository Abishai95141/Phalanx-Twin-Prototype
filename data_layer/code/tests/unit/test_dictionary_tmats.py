"""TMATS stub: parses with pyChapter10 and round-trips the channel list and locations (W0.3 A5).

Parser: pyChapter10 (``chapter10``, installed): the stub is wrapped in a Chapter 10 Computer-Generated Format
1 (setup record) packet, serialised to bytes, re-read with ``chapter10.C10`` and decoded with ``ComputerF1``.
Sample: the complete stub for the Tejas dictionary (294 recorded measurands, ~6,700 attribute lines).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

from phalanx.dictionary import compile_bundle, load_bundle
from phalanx.dictionary.tmats import (
    TMATS_CSDW_VERSION,
    generate_tmats,
    parse_tmats_bytes,
    recorded_channel_ids,
    round_trip,
    tmats_packet_bytes,
)

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"


@lru_cache(maxsize=1)
def _content():
    return compile_bundle(load_bundle(CONFIG)).content


@lru_cache(maxsize=1)
def _text():
    return generate_tmats(_content())


@lru_cache(maxsize=1)
def _attrs():
    return parse_tmats_bytes(tmats_packet_bytes(_text()))


def test_tmats_parses_with_pychapter10():
    import io

    from chapter10 import C10

    packets = list(C10(io.BytesIO(tmats_packet_bytes(_text()))))
    assert len(packets) == 1
    pkt = packets[0]
    assert pkt.data_type == 0x01 and pkt.channel_id == 0 and pkt.version == TMATS_CSDW_VERSION
    assert pkt["G\\106"][b"G\\106"] == b"07"
    assert len(_attrs()) > 6000


def test_tmats_round_trips_channel_list():
    rt = round_trip(_content(), _attrs())
    assert rt.missing == () and rt.extra == () and rt.location_mismatches == ()
    assert rt.ok
    assert len(rt.found) == len(recorded_channel_ids(_content())) == 294


def test_every_line_is_well_formed_ascii():
    for line in _text().splitlines():
        assert line.isascii()
        assert re.fullmatch(r"[A-Z](-\d+)?\\[^:;]+:[^;]*;", line), line


def test_tmats_is_labelled_synthetic_and_names_the_dictionary():
    a = _attrs()
    assert a["G\\PN"] == "PHALANX-TEJAS-SYNTHETIC"
    text = _text()
    assert "SYNTHETIC Phalanx ICD" in text
    assert f"dictionary tejas {_content()['dict_version']}" in text


def test_tmats_is_deterministic():
    assert generate_tmats(_content()) == _text()
    assert tmats_packet_bytes(_text()) == tmats_packet_bytes(generate_tmats(_content()))


def test_recorder_channels_cover_all_recorded_links():
    a = _attrs()
    cdt = {v for k, v in a.items() if re.match(r"R-1\\CDT-\d+$", k)}
    assert cdt == {"TIMEIN", "1553IN", "429IN", "PCMIN"}
    links = {v for k, v in a.items() if re.match(r"R-1\\CDLN-\d+$", k)}
    assert links == {"AV-MUX-1", "AV-MUX-2", "WPN-MUX", "CWS-OAC", "RADALT-OAC", "FTI-PCM"}
    assert int(a["R-1\\N"]) == 7


def test_c_group_conversion_matches_lsb_and_range():
    a = _attrs()
    c = _content()
    index = {v: re.match(r"C-(\d+)", k).group(1) for k, v in a.items() if re.match(r"C-\d+\\DCN$", k)}
    ch = c["channels"]["ENG.N1.V"]
    k = index["ENG.N1.V"]
    assert float(a[f"C-{k}\\CO-1"]) == ch["recorder_lsb"]
    assert float(a[f"C-{k}\\MOT1"]) == ch["range"]["max"]
    assert a[f"C-{k}\\MN3"] == "%"
    assert a[f"C-{k}\\BFM"] == "TWO"


# ---- negatives: the round trip detects damage --------------------------------------------------------------
def test_dropped_measurand_is_detected():
    text = re.sub(r"^C-1\\DCN:[^;]*;\n", "", _text(), count=1, flags=re.M)
    rt = round_trip(_content(), parse_tmats_bytes(tmats_packet_bytes(text)))
    assert not rt.ok and len(rt.missing) == 1


def test_moved_word_is_detected():
    text = re.sub(
        r"^(B-2\\MWN-1-1-1-1):(\d+);",
        lambda m: f"{m.group(1)}:{int(m.group(2)) + 7};",
        _text(),
        count=1,
        flags=re.M,
    )
    rt = round_trip(_content(), parse_tmats_bytes(tmats_packet_bytes(text)))
    assert not rt.ok and rt.location_mismatches


def test_wrong_gain_is_detected():
    a = dict(_attrs())
    key = next(k for k in a if re.match(r"C-\d+\\CO-1$", k))
    a[key] = repr(float(a[key]) * 2)
    rt = round_trip(_content(), a)
    assert not rt.ok and any("CO-1" in m for m in rt.location_mismatches)


def test_malformed_line_is_rejected():
    with pytest.raises(ValueError, match="malformed TMATS line"):
        parse_tmats_bytes(tmats_packet_bytes(_text() + "B-9\\BROKEN LINE WITHOUT TERMINATOR\n"))


def test_wrong_csdw_version_is_rejected():
    from chapter10.computer import ComputerF1

    pkt = ComputerF1(channel_id=0, data_type=0x01, header_version=1, version=12, data=b"G\\PN:X;\n")
    with pytest.raises(ValueError, match="CSDW version"):
        parse_tmats_bytes(bytes(pkt))


def test_stream_without_tmats_is_rejected():
    with pytest.raises(ValueError, match="no TMATS"):
        parse_tmats_bytes(b"")


# ---- recorder setup in the TMATS (dictionary 0.1.2, R-REC-SETUP; W1.7 proposal) ----------------------------
def test_recording_attributes_equal_the_m16_overlay():
    """The dictionary's R-1\\EV / R-1\\IDX lines are what M16 writes, with and without caller-declared
    events. W2.2 migrated M16 onto them (its W1.7 overlay is gone);
    ``tests/integration/test_w22_datapath_migrations.py`` pins the recording bytes across that change."""
    from phalanx.dictionary import load_dictionary
    from phalanx.recorder.setup import EventDef
    from phalanx.recorder.writer import index_interval_s, recorder_events, setup_record

    c = _content()
    d = load_dictionary()
    assert setup_record(d) == generate_tmats(c, recording=True)
    extra = EventDef("BIT-ENG-042", "FADEC BIT (synthetic test code)", "O")
    ours = generate_tmats(
        c,
        recording=True,
        extra_events=[{"id": extra.event_id, "description": extra.description, "type": "O"}],
    )
    assert setup_record(d, (extra,)) == ours
    # one source of truth for the event list and the index interval
    rec = c["buses"]["recorder"]
    assert [(e.event_id, e.description, e.kind) for e in recorder_events(d)] == [
        (e["id"], e["description"], e["type"]) for e in rec["events"]
    ]
    assert rec["index"]["interval_s"] == index_interval_s(d)


def test_recording_tmats_parses_and_keeps_the_channel_list():
    attrs = parse_tmats_bytes(tmats_packet_bytes(generate_tmats(_content(), recording=True)))
    assert attrs["R-1\\EV\\E"] == "T" and attrs["R-1\\EV\\N"] == "3" and attrs["R-1\\IDX\\E"] == "T"
    assert attrs["R-1\\IDX\\ITV"] == str(10 * 1_000_000)
    assert round_trip(_content(), attrs).ok


def test_recording_options_are_checked():
    with pytest.raises(ValueError, match="need recording=True"):
        generate_tmats(_content(), extra_events=[{"id": "X", "description": "x", "type": "O"}])
    with pytest.raises(ValueError, match="duplicate recording event ids"):
        generate_tmats(
            _content(), recording=True, extra_events=[{"id": "REC_START", "description": "x", "type": "R"}]
        )
