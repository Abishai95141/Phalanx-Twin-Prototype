"""BC schedule (M15, W1.7 acceptance A2: bus loading <= 50 %; every message at its rate group)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.bus.icd import BusIcd
from phalanx.bus.schedule import GAP_TO_DEAD_NS, WORD_NS, build_schedule, message_duration_ns
from phalanx.dictionary import load_dictionary

D = load_dictionary()
ICD = BusIcd.from_dictionary(D)
GROUP_HZ = {g: v.get("rate_hz") for g, v in D.content["rate_groups"].items()}


def _sched(bus: str, response: int = 6_300, gap: int = 28_000, start: int = 0):
    resp = {m.rt: response for m in ICD.messages_on(bus)}
    return build_schedule(
        ICD,
        bus,
        minor_hz=GROUP_HZ["AV50"],
        group_hz=GROUP_HZ,
        response_ns=resp,
        gap_ns=gap,
        frame_start_ns=start,
    )


@pytest.mark.parametrize("bus", ["AV-MUX-1", "AV-MUX-2"])
def test_a2_bus_loading_at_most_half(bus):
    """Worst case inside the RT response band (12 us) and the recorded gap still loads <= 50 %."""
    s = _sched(bus, response=12_000)
    assert 0.0 < s.loading() <= 0.5
    assert s.peak_frame_loading() <= 0.5


@pytest.mark.parametrize("bus", ["AV-MUX-1", "AV-MUX-2"])
def test_every_message_is_polled_at_its_group_rate(bus):
    s = _sched(bus)
    assert s.hyper == math.lcm(*[int(x) for x in s.divisor])  # AV-MUX-2: lcm(1, 2, 4, 8, 50) = 200 = 4 s
    assert bus != "AV-MUX-2" or s.hyper == 200
    for i, m in enumerate(s.messages):
        polls = int((s.msg == i).sum())
        assert polls == s.hyper // int(s.divisor[i])
        frames = s.frame_mod[s.msg == i]
        assert np.all(frames % int(s.divisor[i]) == int(s.phase[i]))
        assert GROUP_HZ["AV50"] / s.divisor[i] == GROUP_HZ[m.group]


def test_messages_in_a_frame_are_back_to_back_without_overlap():
    s = _sched("AV-MUX-2")
    for f in range(s.hyper):
        sel = np.flatnonzero(s.frame_mod == f)
        off = s.offset_ns[sel]
        dur = s.duration_ns[s.msg[sel]]
        assert np.all(np.diff(off) == dur[:-1] + s.gap_ns)
        assert off[-1] + dur[-1] < 1e9 / GROUP_HZ["AV50"]


def test_durations_follow_1553_word_timing():
    m = next(m for m in ICD.messages if m.msg_id == "AV-MUX-2/RT05/T/SA02")
    assert message_duration_ns(m, 6_000) == WORD_NS * (2 + 15) + 6_000 - GAP_TO_DEAD_NS
    b = next(m for m in ICD.messages if m.kind == "broadcast")
    assert message_duration_ns(b, 6_000) == WORD_NS * (1 + b.data_words)


def test_schedule_is_deterministic_and_balances_subrates():
    a, b = _sched("AV-MUX-2"), _sched("AV-MUX-2")
    assert np.array_equal(a.msg, b.msg) and np.array_equal(a.offset_ns, b.offset_ns)
    busy = a.frame_busy_ns()
    # sub-rate messages spread out: the busiest frame is far below "all messages in one frame"
    all_in_one = int((a.duration_ns + a.gap_ns).sum())
    assert busy.max() < 0.5 * all_in_one


def test_overloaded_schedule_is_rejected():
    """Negative control: a gap that cannot fit the AV50 messages in a 20 ms frame is an error."""
    with pytest.raises(ValueError, match="overflows"):
        _sched("AV-MUX-2", gap=5_000_000)
