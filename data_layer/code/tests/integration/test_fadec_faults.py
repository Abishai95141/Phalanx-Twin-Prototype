"""``fadec.fault_inject`` (M11 -> M08, AD-48.4): control-side faults are M08 state perturbations whose effect
comes out of the closed loop on the REAL M07 (A-W2.1b-5).

Closed loop: `tests/engine_fadec_loop.py` (real M07 + real M08 kernels, TEST FIXTURE lanes). Each check
compares a faulted continuation with the healthy continuation from the same seam (n = 2-6 s at 240 Hz per run,
SLS ISA unless stated), so the difference is the fault alone.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import engine_fadec_loop as L
from phalanx.core.events import Event
from phalanx.core.module import ContractError, EventNotHandledError
from phalanx.dictionary.yamlio import load_yaml
from phalanx.engine.module import EngineModule
from phalanx.engine.steady import TrimCondition
from phalanx.fadec import FadecConfig, load_fadec_params
from phalanx.fadec import faults as F
from phalanx.fadec.layout import F_FLT_A8_GAIN, F_FLT_PLA_HOLD, F_FLT_RU_BIAS, F_FLT_WF_GAIN, O_A8, O_WF
from phalanx.fadec.module import Fadec
from phalanx.fadec.ports import EVENTS_IN, EVENTS_OUT, MODULE_IDS
from phalanx.fadec.trim import operating_point

pytestmark = pytest.mark.integration
CAT = load_yaml(Path(__file__).resolve().parents[2] / "configs" / "interfaces" / "w1_events.yaml")["events"]
PARAMS = load_fadec_params()
CFG = FadecConfig.build(PARAMS)
A8_GAIN = float(PARAMS.value("fault_a8_gain"))


@pytest.fixture(scope="module")
def eng():
    return EngineModule("eng")


def _payload(mode, param=1.0, *, engine=0, clear=False):
    return {"tail": "T1", "mode": mode, "param": param, "instance": 3, "engine": engine, "clear": clear}


def _faulted(f, mode, param=1.0, **kw):
    g = np.array(f, copy=True)
    F.apply_fault(g, _payload(mode, param, **kw), A8_GAIN, g.shape[0])
    return g


def test_protocol_declaration_matches_the_catalogue():
    assert MODULE_IDS == ("M08",) and set(EVENTS_OUT) == {"fadec.fault", "fadec.caution"}
    spec = CAT[F.EVENT_KIND]
    assert "M08" in spec["consumers"] and spec["producer"] == "M11"
    assert tuple(spec["payload"]) == EVENTS_IN[F.EVENT_KIND] == F.PAYLOAD


def test_every_catalogued_fadec_mode_is_realised_or_explicitly_routed():
    cat = load_yaml(Path(__file__).resolve().parents[2] / "configs" / "tejas" / "faults" / "catalogue.yaml")
    modes = {
        eff["mode"]
        for spec in cat["modes"].values()
        for eff in spec.get("effects", []) or []
        if isinstance(eff, dict) and eff.get("target") == "fadec"
    }
    assert modes, "no fadec modes in the catalogue"
    assert modes <= set(F.MODES) | F.REALISED_BY_M07, sorted(modes - set(F.MODES) - F.REALISED_BY_M07)


def test_module_handler_validates_and_changes_state_only():
    m = Fadec("fadec", PARAMS)
    s0 = m.init(m.params, None)
    snap = {k: v.copy() for k, v in s0.items()}
    s1, out = m.on_event(s0, Event(0, F.EVENT_KIND, "fadec", _payload("fuel_schedule_bias", 0.04)), 0)
    assert out == [] and s1["f"][0, F_FLT_RU_BIAS] == 0.04
    for k in s0:
        assert np.array_equal(s0[k], snap[k]), k
    assert np.array_equal(s1["i"], s0["i"]) and np.array_equal(s1["g"], s0["g"])
    s2, _ = m.on_event(
        s1, Event(0, F.EVENT_KIND, "fadec", _payload("fuel_schedule_bias", 0.04, clear=True)), 0
    )
    assert np.array_equal(s2["f"], s0["f"])
    for key, val, msg in (("mode", "warp", "unknown"), ("engine", 2, "outside"), ("param", np.nan, "finite")):
        with pytest.raises(ContractError, match=msg):
            m.on_event(s0, Event(0, F.EVENT_KIND, "fadec", {**_payload("pla_binding"), key: val}), 0)
    with pytest.raises(ContractError, match="M07 realises"):
        m.on_event(s0, Event(0, F.EVENT_KIND, "fadec", _payload("bleed_schedule_bias", 0.02)), 0)
    with pytest.raises(ContractError, match="lacks 'clear'"):
        pl = _payload("pla_binding")
        del pl["clear"]
        m.on_event(s0, Event(0, F.EVENT_KIND, "fadec", pl), 0)
    with pytest.raises(EventNotHandledError):
        m.on_event(s0, Event(0, "eng.fault_inject", "fadec", _payload("flameout")), 0)


def _seam(eng, pla, *, cond=None, n=480):
    cond = TrimCondition() if cond is None else cond
    op = operating_point(eng.model, CFG, min(pla, 86.0), cond)
    return op, L.run(eng, op.engine, pla, n=n, condition=cond, cfg=CFG)


def test_inject_then_clear_is_bitwise_the_healthy_continuation(eng):
    op, r0 = _seam(eng, 70.0)
    g = _faulted(_faulted(r0.f, "fuel_overmetering", 0.15), "fuel_overmetering", 0.15, clear=True)
    a = L.run(eng, op.engine, 70.0, n=240, cfg=CFG, cont=r0)
    b = L.run(eng, op.engine, 70.0, n=240, cfg=CFG, cont=r0, fadec_f=g)
    assert np.array_equal(a.y, b.y) and np.array_equal(a.cmdf, b.cmdf)


def test_fuel_overmetering_is_closed_round_by_the_governor(eng):
    """+15 % metering error at PLA 70: the delivered fuel steps up, the core accelerates uncommanded, then the
    (weak, AD-50) governor pulls its own command down and N2 returns towards the schedule."""
    op, r0 = _seam(eng, 70.0)
    n = 8 * 240
    h = L.run(eng, op.engine, 70.0, n=n, cfg=CFG, cont=r0)
    f = L.run(eng, op.engine, 70.0, n=n, cfg=CFG, cont=r0, fadec_f=_faulted(r0.f, "fuel_overmetering", 0.15))
    assert f.cmdf[2, 0, O_WF] / h.cmdf[2, 0, O_WF] == pytest.approx(1.15, rel=0.01)  # FMV demand at onset
    n2h, n2f = h.ch("n2"), f.ch("n2")
    k_pk = int(np.argmax(n2f))
    assert n2f[k_pk] > 1.02 * n2h[k_pk] and k_pk < 4 * 240  # uncommanded acceleration
    # the governor takes it back slowly (gov_ki, AD-50 weak governing): over a quarter within 8 s here
    assert n2f[-1] < n2f[k_pk] - 0.25 * (n2f[k_pk] - n2h[-1])
    wf_f = f.cmdf[:, 0, O_WF]
    assert wf_f[-1] < 0.95 * wf_f.max()  # by pulling its own command down


def test_fuel_schedule_bias_runs_the_acceleration_richer(eng):
    """+4 % ratio-unit bias: a slam from PLA 30 to 87 runs on a richer accel schedule (more fuel, earlier
    N2)."""
    op, r0 = _seam(eng, 30.0)
    n = 4 * 240
    h = L.run(eng, op.engine, 87.0, n=n, cfg=CFG, cont=r0)
    f = L.run(eng, op.engine, 87.0, n=n, cfg=CFG, cont=r0, fadec_f=_faulted(r0.f, "fuel_schedule_bias", 0.04))
    w_h, w_f = h.cmdf[:240, 0, O_WF], f.cmdf[:240, 0, O_WF]
    assert np.median(w_f / w_h) > 1.02
    target = 0.9 * h.ch("n2")[-1]
    assert np.argmax(f.ch("n2") > target) < np.argmax(h.ch("n2") > target)


def test_pla_binding_holds_the_throttle(eng):
    op, r0 = _seam(eng, 70.0)
    n = 3 * 240
    h = L.run(eng, op.engine, 40.0, n=n, cfg=CFG, cont=r0)
    g = _faulted(r0.f, "pla_binding")
    assert g[0, F_FLT_PLA_HOLD] == 1.0
    f = L.run(eng, op.engine, 40.0, n=n, cfg=CFG, cont=r0, fadec_f=g)
    assert h.ch("n2")[-1] < 0.97 * r0.ch("n2")[-1]  # healthy: the core decelerates to the PLA 40 schedule
    assert abs(f.ch("n2")[-1] / r0.ch("n2")[-1] - 1.0) < 0.005  # bound: stays at PLA 70


def test_nozzle_loop_gain_fault_makes_the_t5_loop_oscillate(eng):
    """In afterburner (the nozzle T5 loop in control, SLS PLA 110) a nozzle_loop_gain_margin fault turns the
    A8
    command into a sustained oscillation of about +/-0.15 ft2 (catalogue: AJ limit cycle, not flagged)."""
    op, r0 = _seam(eng, 110.0, n=8 * 240)
    assert r0.yi[-1, 0, 0] == 2  # AB lit
    n = 8 * 240
    h = L.run(eng, op.engine, 110.0, n=n, cfg=CFG, cont=r0)
    g = _faulted(r0.f, "nozzle_loop_gain_margin", 1.0)
    assert g[0, F_FLT_A8_GAIN] == A8_GAIN
    f = L.run(eng, op.engine, 110.0, n=n, cfg=CFG, cont=r0, fadec_f=g)
    tail = slice(4 * 240, None)
    in2 = 1.0 / 0.00064516
    a8h, a8f = h.cmdf[tail, 0, O_A8] * in2, f.cmdf[tail, 0, O_A8] * in2
    assert np.ptp(a8f) > 20.0 and np.ptp(a8f) > 5.0 * np.ptp(a8h), (np.ptp(a8h), np.ptp(a8f))
    assert F_FLT_WF_GAIN != F_FLT_RU_BIAS  # distinct fault fields (layout sanity)
