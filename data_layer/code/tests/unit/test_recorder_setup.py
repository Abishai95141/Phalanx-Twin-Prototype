"""The recording's setup record = the dictionary TMATS with the dictionary's recorder setup (A-W0.3-44).

W1.7 overlaid the recorder event/index attributes on the dictionary TMATS (A-W1.7-12); the dictionary 0.1.2
migration (W2.2) generates them in M01 and M16 uses that text verbatim (``writer.setup_record``).
"""

from __future__ import annotations

import pytest

from phalanx.dictionary import load_dictionary
from phalanx.dictionary.tmats import generate_tmats, parse_tmats_bytes, round_trip, tmats_packet_bytes
from phalanx.recorder.setup import EventDef, recorder_channels
from phalanx.recorder.writer import RECORDER_EVENT_ROLES, index_interval_s, recorder_events, setup_record

D = load_dictionary()
BASE = generate_tmats(D.compiled.content)


def test_setup_record_changes_only_event_and_index_attributes():
    text = setup_record(D, (EventDef("BIT-ENG-042", "FADEC BIT; lane A", "O"),))
    base_lines = BASE.splitlines()
    new_lines = text.splitlines()
    removed = [ln for ln in base_lines if ln not in new_lines]
    added = [ln for ln in new_lines if ln not in base_lines]
    assert removed == ["R-1\\EV\\E:F;", "R-1\\IDX\\E:F;"]
    assert all(ln.startswith(("R-1\\EV\\", "R-1\\IDX\\")) for ln in added)
    assert "R-1\\EV\\N:4;" in added and "R-1\\EV\\D-4:FADEC BIT, lane A;" not in added  # ";" never in data
    assert (
        "R-1\\EV\\D-4:FADEC BIT  lane A;" in added
        and "R-1\\EV\\ID-4:BIT-ENG-042;" in added
        and f"R-1\\IDX\\ITV:{index_interval_s(D) * 1_000_000};" in added
    )


def test_setup_record_is_the_dictionary_recording_tmats():
    """One source of truth: M16 adds nothing to what M01 generates (A-W0.3-44)."""
    assert setup_record(D) == generate_tmats(D.compiled.content, recording=True)
    ev = EventDef("BIT-ENG-042", "FADEC BIT (synthetic test code)", "O")
    assert setup_record(D, (ev,)) == generate_tmats(
        D.compiled.content,
        recording=True,
        extra_events=[{"id": ev.event_id, "description": ev.description, "type": ev.kind}],
    )


def test_recorder_events_and_index_come_from_the_dictionary():
    rec = D.recorder_setup()
    assert [(e.event_id, e.description, e.kind) for e in recorder_events(D)] == [
        (e["id"], e["description"], e["type"]) for e in rec["events"]
    ]
    assert set(RECORDER_EVENT_ROLES) <= {e.event_id for e in recorder_events(D)}
    assert index_interval_s(D) == int(rec["index"]["interval_s"])


def test_setup_record_still_parses_and_round_trips_the_dictionary():
    attrs = parse_tmats_bytes(tmats_packet_bytes(setup_record(D)))  # pyChapter10 parses it
    assert attrs["R-1\\EV\\E"] == "T" and attrs["R-1\\IDX\\E"] == "T"
    rt = round_trip(D.compiled.content, attrs)
    assert rt.ok, (rt.missing[:3], rt.extra[:3], rt.location_mismatches[:3])


def test_recorder_channels_come_from_the_r_group():
    ch = recorder_channels(BASE)
    assert ch.time == 1
    assert ch.mil1553 == {"AV-MUX-1": 2, "AV-MUX-2": 3, "WPN-MUX": 4}
    assert ch.arinc429 == {"CWS-OAC": 5, "RADALT-OAC": 6} and ch.pcm == {"FTI-PCM": 7}
    assert ch.max_id == 7


def test_bad_event_definitions_are_rejected():
    with pytest.raises(ValueError):
        EventDef("X" * 33, "too long")
    with pytest.raises(ValueError):
        EventDef("A;B", "terminator in id")
    with pytest.raises(ValueError, match="duplicate recording event ids"):
        setup_record(D, (EventDef("REC_START", "clashes with the recorder's own event", "R"),))


def test_a_dictionary_without_a_writer_role_is_rejected():
    """Negative control: the writer refuses a recorder setup that lacks one of the events it emits."""

    class _NoLockEvents:
        def recording_events(self):
            return tuple(e for e in D.recording_events() if e["id"] != "TIME_LOCK_LOST")

    with pytest.raises(ValueError, match="TIME_LOCK_LOST"):
        recorder_events(_NoLockEvents())
