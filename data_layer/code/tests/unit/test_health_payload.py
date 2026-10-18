"""AD-48.1 plain-key payload encoding (``phalanx.health.protocol.plain_payload`` / ``read_payload``).

Every catalogued key is a plain top-level payload key. Values the core event queue holds natively stay native;
any other value travels as canonical JSON text under its own key, named in the reserved ``json_keys`` key.
The round trip goes through a real ``core.events.Event`` (payload normalisation, canonical encode/decode), so
what is tested is what crosses a module boundary.

Sample: Hypothesis ``max_examples`` = 200 JSON documents (phalanx-check profile, derandomised), plus fixed
documents for each value class. Deterministic; no data.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.canonical import canonical_json
from phalanx.core.events import Event
from phalanx.health.protocol import (
    JSON_KEYS,
    RETIRED_DOC_KEY,
    PayloadError,
    jsonable,
    plain_payload,
    read_payload,
)

pytestmark = pytest.mark.unit


def through_event(doc):
    """plain_payload -> Event (normalised) -> canonical bytes -> decoded Event -> read_payload."""
    ev = Event(7, "ops.offer", "m02", plain_payload(doc), source="m18")
    back = Event.decode(ev.encode())
    assert back == ev
    return read_payload(back.payload), ev


SCALARS = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**63), max_value=2**63 - 1),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=12),
)
JSON = st.recursive(
    SCALARS,
    lambda inner: st.one_of(
        st.lists(inner, max_size=4), st.dictionaries(st.text(max_size=6), inner, max_size=4)
    ),
    max_leaves=12,
)
KEYS = st.from_regex(r"\A[a-z][a-z0-9_.\-]{0,9}\Z").filter(lambda k: k not in (JSON_KEYS, RETIRED_DOC_KEY))


@settings(max_examples=200)
@given(st.dictionaries(KEYS, JSON, max_size=6))
def test_round_trip_through_a_core_event_is_exact(doc):
    """read_payload(Event(plain_payload(doc))) == the JSON document, value types included (int stays int,
    float stays float, bool stays bool), for 200 generated documents."""
    got, _ = through_event(doc)
    assert got == jsonable(doc)
    assert json.dumps(got, sort_keys=True) == json.dumps(jsonable(doc), sort_keys=True)  # types, not just ==
    for k, v in jsonable(doc).items():
        assert type(got[k]) is type(v), (k, v, got[k])


def test_catalogued_keys_are_top_level_and_native_where_possible():
    """The M18 / M02 shapes: scalars and flat homogeneous lists stay native top-level keys; None, mappings,
    nested and mixed lists are JSON text listed in json_keys; no {"doc": ...} wrapper."""
    doc = {
        "tail_no": "KH2011",
        "sortie_id": "KH2011-20261015-0930",
        "t_takeoff": 3_600_000_000_000,
        "flight_hours": 0.8125,
        "aborted": False,
        "tails": ["KH2011", "KH2012"],
        "nz_exceed": [3, 1, 0],
        "empty": [],
        "restrict": {"KH2012": {"limit": "G", "value": 5.0, "until": None}},
        "reason": None,
        "mixed": [1, 2.5],
        "nested": [[1, 2], [3]],
        "arr": np.array([1.0, 2.0]),
    }
    _, ev = through_event(doc)
    pay = ev.payload
    assert "doc" not in pay
    assert set(pay) == set(doc) | {JSON_KEYS}
    assert sorted(np.asarray(pay[JSON_KEYS]).tolist()) == ["mixed", "nested", "reason", "restrict"]
    assert pay["tail_no"].dtype.kind == "U" and pay["t_takeoff"].dtype == np.int64
    assert pay["aborted"].dtype == np.bool_ and pay["flight_hours"].dtype == np.float64
    assert pay["tails"].dtype.kind == "U" and pay["nz_exceed"].dtype == np.int64
    got = read_payload(pay)
    assert got["restrict"] == {"KH2012": {"limit": "G", "value": 5.0, "until": None}}
    assert got["reason"] is None and got["mixed"] == [1, 2.5] and got["nested"] == [[1, 2], [3]]
    assert got["arr"] == [1.0, 2.0] and got["empty"] == []


def test_no_json_keys_when_every_value_is_native():
    pay = plain_payload({"tail": "T1", "pos": "ENG", "serial": "IN20-0001", "cls": "ENG"})
    assert JSON_KEYS not in pay and pay["tail"] == "T1"


def test_equal_documents_give_equal_events():
    """Determinism: key order and tuple-vs-list do not change the encoded event (canonical JSON text)."""
    a = {"z": {"b": 1, "a": [1, None]}, "a": (1, 2), "tail": "T"}
    b = {"tail": "T", "a": [1, 2], "z": {"a": [1, None], "b": 1}}
    ea = Event(0, "mx.action", "m10", plain_payload(a), source="m18")
    eb = Event(0, "mx.action", "m10", plain_payload(b), source="m18")
    assert ea.encode() == eb.encode()


def test_malformed_payloads_are_rejected():
    """Negative controls: the reserved key cannot be a document key; json_keys naming an absent key, a
    non-str key, or JSON text that does not parse all raise."""
    with pytest.raises(PayloadError):
        plain_payload({JSON_KEYS: ["x"]})
    with pytest.raises(PayloadError):
        plain_payload({1: "x"})  # type: ignore[dict-item]
    with pytest.raises(PayloadError):
        plain_payload({"tail no": "x"})  # not a plain key (core payload key rule)
    bad = Event(0, "mx.action", "m10", {"tail": "T", JSON_KEYS: ["row"]}, source="m18")
    with pytest.raises(PayloadError):
        read_payload(bad.payload)
    worse = Event(0, "mx.action", "m10", {"row": "{not json", JSON_KEYS: ["row"]}, source="m18")
    with pytest.raises(json.JSONDecodeError):
        read_payload(worse.payload)


def test_retired_doc_key_is_reserved():
    """plain_payload never produces the W1 {"doc": canonical JSON} wrapper: "doc" is a reserved key."""
    with pytest.raises(PayloadError):
        plain_payload({"doc": {"a": 1}})
    with pytest.raises(PayloadError):
        plain_payload({"tail": "T", "doc": "x"})
    assert canonical_json({"a": 1}).decode() == '{"a":1}'
