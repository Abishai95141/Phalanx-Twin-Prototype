"""A6 smoke and the exposing tests of the W2.1a assumptions (A-W2.1-1 ... A-W2.1-6).

Sample: gate plan order (``phalanx.integration.plans.gate_sorties``).

make check (first gate sortie, n = 1):
- the first 30 s from post-start idle run end to end through the runner with the physical invariants checked,
  the event validator on, the recorder and the M14 feed: no exception, no violation; the post-start idle is
  steady (A-W2.1-2/3: N2 inside the released 63-70 % ground-idle band, flame lit, fuel never cut, PLA at the
  detent from t = 0);
- M14's outbox records are identical with 0.5 s and 1 s CIR chunks (A-W2.1-4), 10 s;
- the sortie lifecycle is M02's ``ops.takeoff`` / ``ops.sortie_done`` (AD-48.2, W2.1c), 1 s.

slow:
- A6: one sortie end to end, then 5 sorties across mission types (the first sortie of each mission type in the
  gate sample), each from post-start idle to engine cut-off with every invariant held. **Strict xfails on
  ``SortieAborted``** with the measured mechanism (``A6_REASON``, reported to the coordinator).
- the AB take-off keeps the lit afterburner: M08 reads M13's AB_LIT lane (the W2.2 producer that closed the
  A-W2.1-1 boundary hold) and declares no AB no-light.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.integration.flights import diverse_sorties, fly
from phalanx.integration.plans import gate_sorties
from phalanx.integration.sortie import SortieAborted, SortieRunner
from phalanx.integration.system import SortieSpec, build_sortie_system

pytestmark = pytest.mark.integration
N2_100 = 16810.0 * 2.0 * np.pi / 60.0
A6_REASON = (
    "W2.1a measured (gate sorties, after the W2.2 merge and the W2.1a take-off and primitive fixes): no "
    "sortie completes. The run-up, take-off, climb-out, cruise and the first mission segments fly (TJ212 "
    "ground attack to 2,200 s), but a 4 g MIL turn primitive overshoots its heading and reverses at 15 deg "
    "alpha into a departure (M04 guidance branch transitions, A-W2.1-10; M05/M06 departure resistance: no "
    "negative-AoA limiter, a -3.5 g push in a bank diverged to -15.7 g); on TJ213, TJ109 and TJ115 the "
    "idle-to-MIL acceleration at take-off runs down on M08's acceleration schedule (Wf/PS3 only ~1-3 % above "
    "the steady-state line at ground idle, stall margin 0.03; N2 64 -> 33 %, ENG-506) and the take-off is "
    "held until the 300 s phase_hold abort (M07/M08, W2.1b)"
)


def _spec(plan=None, **kw):
    return SortieSpec(plan=plan or gate_sorties()[0], scenario="gate", root=0xA5, **kw)


def test_first_30_s_of_a_sortie_and_steady_post_start_idle():
    ss = build_sortie_system(_spec())
    r = SortieRunner(ss, validate_events=True, record=["fadec.wf_cmd", "eng.flame_state", "pilot.pla"])
    st = r.begin()
    st, outs = r.run(st, 30 * 240)
    assert r.validator.violations == []
    n2 = np.concatenate([c.trace.ports["eng.n2"][:, 0] for c in outs]) / N2_100 * 100.0
    assert 63.0 <= n2.min() and n2.max() <= 70.0, (n2.min(), n2.max())
    assert np.all(np.concatenate([c.trace.ports["eng.flame_state"] for c in outs]) == 1)
    assert np.all(np.concatenate([c.trace.ports["fadec.wf_cmd"] for c in outs]) > 0.0)
    pla = np.concatenate([c.trace.ports["pilot.pla"][:, 0] for c in outs])
    assert np.all(pla == ss.pla_idle), "the pilot's hand leaves the ground-idle detent"
    assert len(r.m14_channels) > 0 and int(np.asarray(st.world.states["monitor"]["o_kind"]).size) >= 0


def _outbox(chunk: int, seconds: float):
    ss = build_sortie_system(_spec())
    r = SortieRunner(ss, chunk_steps=chunk)
    st = r.begin()
    st, _ = r.run(st, round(seconds * 240))
    ms = st.world.states["monitor"]
    return {k: np.asarray(v) for k, v in ms.items() if k.startswith("o_")}, st


def test_m14_records_are_chunk_invariant():
    """A-W2.1-4: the CIR feed cadence changes when M14 sees the data, not what it records (10 s)."""
    a, _ = _outbox(240, 10.0)
    b, _ = _outbox(120, 10.0)
    assert a.keys() == b.keys()
    for k in a:
        assert a[k].tobytes() == b[k].tobytes(), k


def test_sortie_lifecycle_is_m02s_ops_takeoff_and_sortie_done():
    """AD-48.2 (W2.1c) with the W2.1a take-off fix (A-W2.1-9): M02 runs in segment-source mode, so after the
    bootstrap nothing of the lifecycle is pre-scheduled on plan clock times: ``ops.takeoff`` comes from M02 at
    the ``pilot.segment`` that leaves the take-off (tests/integration/test_integration_takeoff.py) and
    ``ops.sortie_done`` at the end of the flown plan; the runner injected only M14's power-up hook (M14
    powered from t = 0; M11's sortie not open before take-off: one start path, 1 s)."""
    ss = build_sortie_system(_spec())
    assert ss.modules["scenario"].segment_source == "pilot"
    r = SortieRunner(ss)
    st = r.begin()
    st, _ = r.run(st, 240)
    pend = st.world.queue.pending()
    assert not [e for e in pend if e.kind in ("ops.takeoff", "ops.sortie_done")]
    assert not any(e.kind.startswith("faults.sortie") for e in pend)
    assert int(np.asarray(st.world.states["monitor"]["clock"])[2]) == 1
    assert int(np.asarray(st.world.states["faults"]["sortie_open"])) == 0


def _fly(plan):
    f = fly(plan)  # shared with the A5/A10 checks (phalanx.integration.flights)
    print(
        f"{f.sortie_id} ({f.mission_type}): flown {f.flown_s:.0f} s, lift-off "
        f"{f.liftoff_s if f.liftoff_s is None else round(f.liftoff_s)} s, abort "
        f"{None if f.abort is None else (f.abort.kind, f.abort_phase, str(f.abort))}"
    )
    assert f.violations == []
    if f.abort is not None:
        raise f.abort
    u = f.realised
    assert u.landings >= 1 and u.flight_time_s > 0
    return u


@pytest.mark.slow
@pytest.mark.xfail(strict=True, raises=SortieAborted, reason=A6_REASON)
def test_a6_one_sortie_end_to_end():
    _fly(diverse_sorties()[0])


@pytest.mark.slow
@pytest.mark.xfail(strict=True, raises=SortieAborted, reason=A6_REASON)
def test_a6_five_sorties_across_mission_types():
    picked = diverse_sorties(5)
    assert len({p.mission_type for p in picked}) >= 3
    aborts = []
    for p in picked:
        try:
            _fly(p)
        except SortieAborted as e:
            aborts.append(e)
    if aborts:
        raise aborts[0]


@pytest.mark.slow
def test_ab_take_off_keeps_the_lit_afterburner():
    """The AB take-off with the W2.2 ENG.AB_LIT producer (M12 UV flame detector -> M13 FADEC lane; replaces
    the A-W2.1-1 boundary hold): from the run-up window of the first gate sortie (AB take-off, drop tanks),
    72 s; M07 lights the afterburner in the TAKEOFF segment and it stays lit to the end of the window, M08
    declares no AB no-light (ENG-505, which it declared about 1 s after every light-off on the hold) and the
    thrust rises above MIL (measured before the producer: ~28 kN with the nozzle open; now 75.9 kN)."""
    from phalanx.engine.layout import AB_LIT

    ss = build_sortie_system(_spec(start_phase="RUNUP"))
    r = SortieRunner(ss, check_invariants=False, record=["eng.ab_state", "eng.thrust"])
    st = r.begin()
    st, outs = r.run(st, 72 * 240)
    ab = np.concatenate([c.trace.ports["eng.ab_state"][:, 0] for c in outs])
    thrust = np.concatenate([c.trace.ports["eng.thrust"][:, 0] for c in outs])
    codes = [
        str(np.asarray(e.payload["code"]))
        for c in outs
        for _k, e in c.trace.dispatched
        if e.kind == "fadec.fault" and bool(np.asarray(e.payload["set"]))
    ]
    lit = np.flatnonzero(ab == AB_LIT)
    assert lit.size, "M07 never lit the afterburner in the window"
    print(f"AB lit at {lit[0] / 240:.1f} s, thrust after light-off {thrust[lit[0] :].max() / 1e3:.1f} kN")
    assert np.all(ab[lit[0] :] == AB_LIT)
    assert "ENG-505" not in codes, codes
    assert thrust[lit[0] :].max() > 60e3
