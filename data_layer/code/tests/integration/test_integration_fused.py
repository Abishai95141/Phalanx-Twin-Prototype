"""A4: the fused truth-loop kernel equals the per-step scheduler path, bitwise (AD-36, AD-22).

Sample: the first flying sortie of the gate plan (n = 1), from post-start idle. The per-step reference is the
core scheduler's interpreter (``mode="step"``) on the unfused System, which calls each module's own ``step``.
Compared over 1,440 truth steps (6 s, including M08 ``fadec.fault`` events that cut fused blocks): every
output port of every module (bytes), every module state, the dispatch log and the trace digest, for fused
block lengths 1, 7 and 1,024. Negative controls show the comparison can fail: a gather-table entry of M06
pointed at a neighbouring bus element, and the M03 time step changed by one ulp, both break bitwise equality.

The slow test repeats the comparison over the take-off window of the sortie (run-up to lift-off; 3,600 steps).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.state import trees_equal
from phalanx.integration.plans import gate_sorties
from phalanx.integration.system import SortieSpec, build_sortie_system

pytestmark = pytest.mark.integration
N_TAKEOFF = 72 * 240
N = 1440


def _run(ss, n, mode, world=None):
    w = world if world is not None else ss.system.inject(ss.start(), ss.bootstrap_events())
    return ss.system.run(w, n, mode=mode, record=ss.system.output_ports())


def _bytes_equal(a: np.ndarray, b: np.ndarray) -> bool:
    a, b = np.ascontiguousarray(a), np.ascontiguousarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def _compare(ta, tb, wa, wb) -> list[str]:
    bad = [r for r in tb.ports if not _bytes_equal(ta.ports[r], tb.ports[r])]
    bad += [f"state:{m}" for m in wb.states if not trees_equal(wa.states[m], wb.states[m])]
    if [(k, e.encode()) for k, e in ta.dispatched] != [(k, e.encode()) for k, e in tb.dispatched]:
        bad.append("dispatch log")
    return bad


@pytest.fixture(scope="module")
def reference():
    ss = build_sortie_system(SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5, fused=False))
    w, tr = _run(ss, N, "step")
    return ss, w, tr


@pytest.fixture(scope="module")
def fused_ss():
    return {
        bl: build_sortie_system(
            SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5, fused=True, block_len=bl)
        )
        for bl in (1, 7, 1024)
    }


@pytest.mark.parametrize("block_len", [1, 7, 1024])
def test_fused_block_equals_per_step_bitwise(reference, fused_ss, block_len):
    ss_ref, w_ref, tr_ref = reference
    ss = fused_ss[block_len]
    assert ss.system.config_hash == ss_ref.system.config_hash  # the fused group is execution, not semantics
    assert [g["fused"] for g in ss.system.execution()["segments"] if g["fused"]] == ["truth_loop"]
    w, tr = _run(ss, N, "block")
    assert _compare(tr, tr_ref, w, w_ref) == []
    assert tr.digest() == tr_ref.digest()
    # since the W2.1c/W2.2 merge M08 declares nothing in this idle window (the earlier ENG-013/023/053
    # toggling is gone); the block cuts on events emitted inside the fused group are covered by the slow
    # run-up and take-off test below (M04's pilot.segment at each flown segment change)


def test_negative_controls_break_bitwise_equality(reference, fused_ss):
    """A wrong gather entry (M06 surface input read from the neighbouring bus element) and a 1-ulp change of
    the truth time step each break the equality: the comparison above can fail."""
    ss_ref = reference[0]
    n = 480
    w0 = ss_ref.system.inject(ss_ref.start(), ss_ref.bootstrap_events())
    w_r, t_r = ss_ref.system.run(w0, n, mode="step", record=ss_ref.system.output_ports())
    ss = fused_ss[1024]
    g = next(seg.fused for seg in ss.system._segments if seg.fused is not None)
    orig_g06 = g.g06
    try:
        codes, idx = (np.array(x, copy=True) for x in orig_g06)
        j = int(np.flatnonzero(codes == 0)[0])  # first current-bus float input of M06
        idx[j] += 1
        g.g06 = (codes, idx)
        w, tr = _run(ss, n, "block")
        assert _compare(tr, t_r, w, w_r) != []
    finally:
        g.g06 = orig_g06
    real = g.step_block

    def nudged(states, ext, held0, k, dt):
        return real(states, ext, held0, k, np.nextafter(dt, 1.0))

    try:
        g.step_block = nudged  # instance attribute: what the scheduler calls for this segment
        w, tr = _run(ss, n, "block")
        assert _compare(tr, t_r, w, w_r) != []
    finally:
        del g.step_block
    w, tr = _run(ss, n, "block")
    assert _compare(tr, t_r, w, w_r) == []


@pytest.mark.slow
def test_fused_equals_per_step_through_the_runup_and_takeoff_roll():
    """72 s (17,280 steps) from the RUNUP segment (window start at the run-up, engine at idle): the run-up
    transient, the line-up and the AB take-off roll, fused (block 1,024) vs per step; the window contains
    events emitted inside the fused group (M04's ``pilot.segment`` at the run-up -> line-up -> take-off
    changes, A-W2.1-9), so the block-cut path is exercised."""
    spec = dict(plan=gate_sorties()[0], scenario="gate", root=0xA5, start_phase="RUNUP")
    ref = build_sortie_system(SortieSpec(**spec, fused=False))
    fus = build_sortie_system(SortieSpec(**spec, fused=True))
    wr, tr_r = _run(ref, N_TAKEOFF, "step")
    wf, tr_f = _run(fus, N_TAKEOFF, "block")
    assert _compare(tr_f, tr_r, wf, wr) == []
    assert sum(e.kind == "pilot.segment" for _, e in tr_r.dispatched) >= 2
