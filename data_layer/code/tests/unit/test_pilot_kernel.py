"""M04 kernel units: pilot throttle slew/lag/delay (A-W1.1-43), inceptor scaling (A-W1.1-41), plan loading
from
the event payload, and the proxy-mode replay pass-through (autothrottle hooks)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import NS_PER_S, TRUTH_DT_S, TRUTH_HZ
from phalanx.pilot import kernel as K
from phalanx.pilot.module import PLAN_EVENT, PilotModule, PilotReplay, load_pilot_config
from phalanx.scenario import phases as PH
from phalanx.scenario.plan import N_SEG_F, N_SEG_I, S_PHASE, S_PLA, S_PLA_HI, S_PLA_LO, SortiePlan
from phalanx.scenario.replay import ReplayInputs

CFG = load_pilot_config()
DEG = math.pi / 180


def ground_plan(pla_steps_deg, seg_s=2.0, tau=0.15):
    n = len(pla_steps_deg)
    seg_f = np.zeros((n, N_SEG_F))
    seg_i = np.zeros((n, N_SEG_I), np.int64)
    for j, v in enumerate(pla_steps_deg):
        seg_f[j, [S_PLA, S_PLA_LO, S_PLA_HI]] = v * DEG
        seg_i[j, S_PHASE] = PH.RUNUP
    traits = np.array([1, 1, 1, 1, 1.3, 0.36, tau, 1.0, 0.0])
    return SortiePlan(
        "T-1", "k", "T", "sq", 1, 0.0, 0, "PLT", False, 0, ("E",), 0, 2458.0,
        (np.arange(n) * seg_s * NS_PER_S).astype(np.int64), seg_f, seg_i, int(n * seg_s * NS_PER_S),
        np.zeros(14), traits,
    )  # fmt: skip


def bound(module):
    rng = RngService(7, StreamRegistry(module.streams))
    module.bind(rng.scope(KeyPath.of(scenario="u", tail="T", sortie="S")))
    return module


def inputs(n, n_eng=1):
    q = np.tile([1.0, 0, 0, 0], (n, 1))
    return {
        "alt": np.zeros(n),
        "tas": np.zeros(n),
        "mach": np.zeros(n),
        "vel_ned": np.zeros((n, 3)),
        "quat": q,
        "omega_body": np.zeros((n, 3)),
        "nz": np.ones(n),
        "wow": np.ones((n, 3), np.int64),
        "n2": np.full((n, n_eng), 1.0e4),
    }


@pytest.mark.unit
def test_pla_slew_and_band():
    """A slam from ground idle to max AB: the pilot's throttle starts after the pilot delay, follows the
    hand lag and never exceeds the 200 deg/s slew; it settles on the commanded PLA."""
    plan = ground_plan([18.0, 130.0], seg_s=2.0, tau=0.15)
    m = bound(PilotModule("pilot", CFG, plan=plan))
    st = m.init(m.params, m.keys)
    n = 4 * TRUTH_HZ
    t = (np.arange(n, dtype=np.int64) * NS_PER_S) // TRUTH_HZ
    st, out = m.step_block(st, inputs(n), t, TRUTH_DT_S)
    pla = out["pla"][:, 0] / DEG
    step = np.diff(pla)
    assert np.max(np.abs(step)) <= CFG.vector[K.P_SLEW] / DEG * TRUTH_DT_S + 1e-9
    k_slam = 2 * TRUTH_HZ
    delay = round(0.15 * TRUTH_HZ)
    assert np.all(pla[k_slam : k_slam + delay - 1] == pytest.approx(18.0, abs=1e-9))  # pilot delay
    assert pla[-1] == pytest.approx(130.0, abs=1e-6)
    assert np.array_equal(out["ab_select"][:, 0] == 1, pla >= 94.0)


@pytest.mark.unit
def test_plan_event_loads_the_plan_on_the_kernel_clock():
    plan = ground_plan([18.0, 87.0])
    m = bound(PilotModule("pilot", CFG))
    st = m.init(m.params, m.keys)
    assert int(st["i"][K.I_NSEG]) == 0
    ev = Event(0, PLAN_EVENT, "pilot", plan.to_payload(t_kernel0_ns=3 * NS_PER_S))
    st2, emitted = m.on_event(st, ev, 0)
    assert emitted == [] and int(st2["i"][K.I_NSEG]) == 2
    assert np.array_equal(st2["plan_t"], plan.t_off_ns + 3 * NS_PER_S)
    assert int(st2["i"][K.I_TEND]) == 3 * NS_PER_S + plan.t_end_off_ns
    assert int(st2["i"][K.I_NDELAY]) == round(0.15 * TRUTH_HZ)


@pytest.mark.unit
def test_inceptor_scaling_constants():
    v = CFG.vector
    assert 1.0 + v[K.P_SNZP] == pytest.approx(8.0) and 1.0 - v[K.P_SNZN] == pytest.approx(-3.5)
    assert v[K.P_PFULL] == pytest.approx(200 * DEG)
    assert v[K.P_N2100] == pytest.approx(16810 * 2 * math.pi / 60)


@pytest.mark.unit
def test_replay_passes_autothrottle_and_pla_through():
    n = 8
    rec = ReplayInputs(
        t0_ns=0,
        rate_hz=4.0,
        epoch_utc_ns=0,
        pla_rad=np.vstack([np.linspace(0.1, 0.8, n), np.linspace(0.2, 0.9, n)]),
        phase=np.array([1, 2, 3, 4, 5, 5, 6, 7]),
        pressure_alt_m=np.zeros(n),
        mach=np.zeros(n),
        tat_k=np.full(n, 288.0),
        at_engage=np.array([0, 0, 0, 1, 1, 1, 0, 0]),
        at_n1_cmd=np.full((2, n), 0.85),
    )
    m = PilotReplay("pilot", rec)
    t = (np.arange(2 * TRUTH_HZ, dtype=np.int64) * NS_PER_S) // TRUTH_HZ
    _, out = m.step_block(m.init(m.params, None), {}, t, TRUTH_DT_S)
    assert out["pla"].shape == (t.size, 2) and out["at_n1_cmd"].shape == (t.size, 2)
    k = 3 * TRUTH_HZ // 4 + 5  # inside sample 3 (A/T engaged)
    assert int(out["at_engage"][k]) == 1 and out["pla"][k, 1] == pytest.approx(rec.pla_rad[1, 3])
    assert int(out["gear_cmd"][0]) == 1 and int(out["gear_cmd"][k]) == 0
