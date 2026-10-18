"""Event jump for event-only (usage-mode) systems: bitwise identical to stepping, and actually jumping.

Samples: (a) mean renewal interval 2 s over 10 min (144,000 steps, ~300 renewals) so the per-step reference
interpreter stays cheap; (b) one tail-year (7.57e9 steps, ~2,900 renewals at a 3 h mean) with the jump only.
"""

from __future__ import annotations

import pytest

import phalanx.core.scheduler as sched
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.toy import build_usage_system, start_usage

N = 240 * 600  # 10 min
YEAR = 240 * 3600 * 24 * 365
REC = ["renewal.n_renewals", "renewal.last_interval", "counter.count"]


def _run(n=N, chunks=(N,), mode="block", **kw):
    s = build_usage_system(mean_interval_s=2.0, **kw)
    w = start_usage(s)
    tr = None
    for c in chunks:
        w, t = s.run(w, c, mode=mode, record=REC)
        tr = t if tr is None else tr.concat(t)
    return s, w, tr


@pytest.mark.integration
@pytest.mark.determinism
def test_event_jump_equals_stepping_bitwise():
    s_step, w_step, t_step = _run(mode="step")
    s_blk, w_blk, t_blk = _run(event_jump=False, block_len=1024)
    s_jmp, w_jmp, t_jmp = _run()
    s_chk, w_chk, t_chk = _run(chunks=(1, 50_000, 7, N - 50_008))
    assert s_jmp.execution()["event_jump"] and not s_blk.execution()["event_jump"]
    assert len(t_step.dispatched) > 500  # renewals + counter notifications + audits
    ref = snapshot(s_step, w_step)
    assert snapshot(s_blk, w_blk) == ref and snapshot(s_jmp, w_jmp) == ref and snapshot(s_chk, w_chk) == ref
    assert t_jmp.digest() == t_step.digest() == t_blk.digest() == t_chk.digest()
    assert s_jmp.config_hash == s_blk.config_hash  # the jump is an execution strategy, not configuration


@pytest.mark.integration
def test_event_jump_visits_only_dispatch_steps(monkeypatch):
    """The run loop wakes once per distinct dispatch step (plus the start), not once per block."""
    calls = []
    real = sched.System._dispatch

    def spy(self, w, trace):
        calls.append(w.k)
        return real(self, w, trace)

    monkeypatch.setattr(sched.System, "_dispatch", spy)
    _s, _w, tr = _run()
    wake_steps = sorted({k for k, _ in tr.dispatched})
    assert calls == wake_steps  # every wake-up dispatches; nothing else wakes the loop
    calls.clear()
    _run(event_jump=False, block_len=64)
    # without the jump the loop also wakes at block boundaries: ~N / 64 = 2,250 wake-ups vs ~300 dispatches
    assert set(wake_steps) < set(calls) and len(calls) > 5 * len(wake_steps)


@pytest.mark.integration
def test_one_tail_year_in_usage_mode_and_snapshot_mid_year():
    s = build_usage_system()
    w, tr = s.run(start_usage(s), YEAR // 2)
    snap = snapshot(s, w)
    s2 = build_usage_system()
    w_end, tr2 = s2.run(restore(s2, snap), YEAR - YEAR // 2)
    s_ref = build_usage_system()
    w_ref, tr_ref = s_ref.run(start_usage(s_ref), YEAR)
    assert snapshot(s2, w_end) == snapshot(s_ref, w_ref)
    n = int(w_ref.states["renewal"]["n"])
    assert 2_500 < n < 3_400  # ~8,760 h / 3 h
    assert int(w_ref.states["counter"]["count"]) == n  # each renewal notifies the counter in the same phase
    assert len(tr.dispatched) + len(tr2.dispatched) == len(tr_ref.dispatched)
