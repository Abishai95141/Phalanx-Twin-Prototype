"""Operations-layer time: working calendars, decision epochs, canonical document state (W1.8)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.canonical import canonical_json
from phalanx.maintenance.docstate import Cow, decode_doc, encode_doc, encode_doc_reference
from phalanx.maintenance.timebase import DAY_S, NS, WorkCalendar, bin_start, check_whole_second
from phalanx.orders.epochs import DecisionCalendar

EPOCH = 1_790_035_200 * NS  # 2026-09-22 00:00:00 UTC = 05:30 IST
IST = 19_800
WC = WorkCalendar(EPOCH, IST, 6 * 3600, 22 * 3600)


@pytest.mark.unit
def test_add_work_pauses_overnight_and_counts_only_working_seconds():
    # kernel 0 = 05:30 IST: no work until 06:00 IST (30 min later); 1 h of work ends at 07:00 IST
    t_end = WC.add_work(0, 3600)
    assert (t_end // NS) == 30 * 60 + 3600
    # 20 h of work spans a night: 16 h day 1 (06-22), 4 h day 2 (06-10)
    t20 = WC.add_work(0, 20 * 3600)
    assert WC.local_s(t20) % DAY_S == 10 * 3600
    assert WC.working_seconds(0, t20) == 20 * 3600
    cont = WorkCalendar(EPOCH, IST, 0, DAY_S)
    assert cont.add_work(123 * NS, 50) == 173 * NS


@pytest.mark.property
@settings(max_examples=60, deadline=None)
@given(t=st.integers(0, 400 * DAY_S), a=st.integers(0, 3 * DAY_S), b=st.integers(0, 3 * DAY_S))
def test_add_work_is_additive_and_inverse_of_working_seconds(t, a, b):
    t0 = t * NS
    assert WC.add_work(WC.add_work(t0, a), b) == WC.add_work(t0, a + b) or a == 0 or b == 0
    end = WC.add_work(t0, a)
    assert WC.working_seconds(t0, end) == a
    assert end >= t0


@pytest.mark.property
@settings(max_examples=80, deadline=None)
@given(
    t=st.integers(0, 60 * DAY_S),
    times=st.lists(st.integers(0, DAY_S - 1), min_size=1, max_size=3, unique=True),
)
def test_next_epoch_is_the_first_epoch_at_or_after(t, times):
    cal = DecisionCalendar(EPOCH, IST, tuple(sorted(times)))
    t0 = t * NS
    e = cal.next_epoch(t0)
    assert e >= t0 and cal.is_epoch(e)
    loc = (EPOCH + e) // NS + IST
    assert loc % DAY_S in times
    assert all(not cal.is_epoch(x * NS) for x in range(t, e // NS) if (x - t) < 3)  # nothing just before it
    assert cal.epochs(t0, e) == []


@pytest.mark.unit
def test_whole_second_rule_and_bins():
    with pytest.raises(ValueError):
        check_whole_second(5)
    with pytest.raises(ValueError):
        WorkCalendar(EPOCH + 1, IST, 0, DAY_S)
    w = 900 * NS
    assert bin_start(EPOCH + 1, w) % w == 0 and bin_start(EPOCH + 1, w) <= EPOCH + 1


json_values = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(-(2**53), 2**53)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=8),
    lambda c: st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=6), c, max_size=4),
    max_leaves=20,
)


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(doc=json_values)
def test_encode_doc_equals_core_canonical_json_and_round_trips(doc):
    a = encode_doc(doc)
    assert a.tobytes() == canonical_json(doc) == encode_doc_reference(doc).tobytes()
    assert decode_doc(a) == json.loads(canonical_json(doc).decode())


@pytest.mark.unit
def test_cow_never_mutates_its_input():
    state = {"x": np.arange(3), "d": encode_doc({"a": [1]})}
    for v in state.values():
        v.flags.writeable = False
    c = Cow(state)
    c.w("x")[0] = 99
    c.doc("d")["a"].append(2)
    c.touch("d")
    new = c.commit()
    assert state["x"][0] == 0 and decode_doc(state["d"]) == {"a": [1]}
    assert new["x"][0] == 99 and decode_doc(new["d"]) == {"a": [1, 2]}
    with pytest.raises(TypeError):
        encode_doc({"a": np.int64(1)})  # NumPy scalars are rejected, never silently converted
