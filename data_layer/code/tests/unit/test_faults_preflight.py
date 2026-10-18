"""W2.5 deliverable 5 (W2.1c proposal 6, A-W2.1c-6): preflight start-failure modes are drawn at engine start.

M11 consumes ``ops.power_up`` (engine start of a committed sortie): the start-failure modes (JFS cold start,
hung start, hot start; ``maintenance.START_FAILURES``) are drawn then, with onsets at the power-up instant, so
``ops.start_failure`` reaches M02 before the take-off. The draw uses each mode's own generator of the sortie
stream, so the outcome equals what the take-off path draws (same instances, same severities) and no other
mode's draws move; the sortie start then skips the modes already drawn.

TEST FIXTURES: ``Recorder`` modules at the module boundary (``test_faults_module.build``). Samples: the
probabilities are forced to 1 (ParamSet.replace) so one sortie per test exercises the path deterministically;
the CRN check compares 20 sorties' full onset sets between the two paths.
"""

from __future__ import annotations

import numpy as np
import pytest
from test_faults_module import SEC, TARGETS, build, run_to

from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.faults import load_fault_params
from phalanx.faults.maintenance import START_FAILURES
from phalanx.health.protocol import plain_payload, read_payload

pytestmark = pytest.mark.unit
P = load_fault_params()
FORCED = P.replace(hung_start_p=1.0, hot_start_p=1.0, jfs_cold_fail_p=1.0)
T_UP, T_TO, T_LDG = 60 * SEC, 660 * SEC, 4260 * SEC
TAIL = "KH2011"


def _up(sid: str, t: int = T_UP, cold: int = 0, tail: str = TAIL) -> Event:
    doc = {"tail_no": tail, "sortie_id": sid, "engine_starts": 1, "cold_soak": cold}
    return Event(t, "ops.power_up", "faults", plain_payload(doc), source="m02")


def _takeoff(sid: str, t: int = T_TO) -> Event:
    doc = {
        "sortie_id": sid,
        "tail_no": TAIL,
        "t_takeoff": t,
        "t_landing": T_LDG,
        "ab_lights": 4,
        "engine_starts": 1,
        "landings": 1,
        "dust_index": 1.0,
    }
    return Event(t, "ops.takeoff", "faults", plain_payload(doc), source="m02")


def _onsets(f, w):
    st = w.states["faults"]
    return [
        (f.config.mode_ids[int(m)], int(t0), float(s))
        for m, t0, s in zip(st["inst_mode"], st["inst_t0"], st["inst_sev"], strict=True)
    ]


def _reports(recs):
    return [(t, read_payload(e.payload)) for t, e in recs["ops"].log if e.kind == "ops.start_failure"]


def test_power_up_draws_the_start_failures_before_take_off():
    sysm, f, _h, recs = build(fparams=FORCED, stochastic=True, targets=(*TARGETS, "ops"))
    w = run_to(sysm, sysm.inject(sysm.start(), [_up("KH2011-1", cold=1)]), T_UP + 2 * SEC)
    modes = {m for m, t0, _ in _onsets(f, w) if t0 == T_UP}
    assert modes == set(START_FAILURES)  # hung, hot and (cold-soaked) JFS start failure, all at engine start
    reps = _reports(recs)
    assert {r["mode"] for _, r in reps} == set(START_FAILURES)
    assert all(t < T_TO and r["sortie_id"] == "KH2011-1" and r["tail_no"] == TAIL for t, r in reps)
    # the take-off does not draw them again
    w = run_to(sysm, sysm.inject(w, [_takeoff("KH2011-1")]), T_TO + 2 * SEC)
    assert sum(m in START_FAILURES for m, _, _ in _onsets(f, w)) == len(START_FAILURES)


def test_no_cold_soak_no_jfs_cold_start_failure():
    sysm, f, _h, _recs = build(fparams=FORCED, stochastic=True)
    w = run_to(sysm, sysm.inject(sysm.start(), [_up("KH2011-1", cold=0)]), T_UP + 2 * SEC)
    assert "FM.SPS.JFS_COLD_START_FAIL" not in {m for m, _, _ in _onsets(f, w)}


def test_power_up_and_take_off_paths_draw_the_same_faults():
    """CRN: 20 sorties at the shipped probabilities. Power-up then take-off gives the same onset modes and
    severities as take-off alone; only the start failures move to the engine-start instant. Negative control:
    the counts of start failures are non-zero in at least one arm with forced probabilities (else the check
    would compare empty sets)."""
    for params in (P, FORCED):
        got = {}
        sysm, f, _h, _r = build(fparams=params, stochastic=True)  # one System; a fresh world per sortie
        for arm in ("power_up", "takeoff"):
            rows = []
            for k in range(20):
                sid = f"KH2011-{k}"
                evs = [_up(sid), _takeoff(sid)] if arm == "power_up" else [_takeoff(sid)]
                w = run_to(sysm, sysm.inject(sysm.start(), evs), T_LDG + 2 * SEC)  # every onset applied
                rows.append(sorted((m, round(s, 12)) for m, _, s in _onsets(f, w)))
            got[arm] = rows
        assert got["power_up"] == got["takeoff"]
        if params is FORCED:
            assert all(any(m in START_FAILURES for m, _ in r) for r in got["power_up"])


def test_power_up_protocol():
    sysm, f, _h, _recs = build(fparams=FORCED, stochastic=True)
    w = run_to(
        sysm, sysm.inject(sysm.start(), [_up("KH2011-1"), _up("KH2011-1", t=T_UP + SEC)]), T_UP + 3 * SEC
    )
    assert len(_onsets(f, w)) == 2  # hung and hot start once: a repeated power-up is a no-op
    w2 = run_to(sysm, sysm.inject(sysm.start(), [_up("KH2011-1", tail="KH9999")]), T_UP + 2 * SEC)
    assert _onsets(f, w2) == [] and str(w2.states["faults"]["pre_sortie"]) == ""  # another tail's
    w3 = run_to(sysm, sysm.inject(sysm.start(), [_takeoff("KH2011-1")]), T_TO + SEC)
    with pytest.raises(ContractError, match="power-up of"):
        run_to(sysm, sysm.inject(w3, [_up("KH2011-2", t=T_TO + 2 * SEC)]), T_TO + 3 * SEC)
    assert np.isfinite(T_LDG)
