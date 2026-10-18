"""M05 observation-layer interfaces (AD-42): DFCC frames on the shared DFCC acquisition clock, the
computation delay resolved in integer ns, recorded computed channels (``ports.RECORDED``), the af.wow
discrete path with stuck-switch faults.

Deterministic scenarios of 60-720 truth ticks (n = 1 per check); clock variants are fixed values.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest
from test_fcs_voting import L, base_inputs, make, run

from phalanx.acquisition.config import acquisition_clock
from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.core.sampling import samples_for_steps
from phalanx.core.time import ClockDomain, latest_truth_steps, truth_step_times_ns
from phalanx.fcs.build import build_fcs_config, fcs_param_set
from phalanx.fcs.layout import LAW_GROUND, LAW_SCHEDULED, LRU_CBIT_FAIL
from phalanx.fcs.module import frame_schedule
from phalanx.fcs.ports import NOT_MODELLED, REC_CHANNELS, RECORDED


@pytest.mark.integration
def test_dfcc_frames_on_the_acquisition_clock_with_8ms_delay():
    """Default configuration: the DFCC clock is M13's DFCC clock; frames on steps k = 0 mod 3 and the 8 ms
    delay lands on the second truth frame after the sample (8.33 ms; Patel et al. JOAST 58(4))."""
    cfg = build_fcs_config(fcs_param_set())
    assert cfg.clock == acquisition_clock("DFCC", 80)
    t = truth_step_times_ns(np.arange(720))
    fr, off, nxt = frame_schedule(cfg, 0, t)
    assert np.array_equal(np.flatnonzero(fr), np.arange(0, 720, 3))
    assert np.all(off[fr == 1] == 2) and nxt == 240


@pytest.mark.integration
@pytest.mark.parametrize("ppm, phase_ns", [(50, 3_100_000), (-80, 11_000_000), (0, 4_166_667)])
def test_frame_schedule_matches_m13_sampling_for_any_clock(ppm, phase_ns):
    """For an offset / phased DFCC clock the frames fall in exactly the steps where M13's sampling arithmetic
    (core.sampling.samples_for_steps) puts the samples, and each command applies at the first truth frame at
    or after t_sample + 8 ms; block and per-step schedules agree."""
    clk = ClockDomain("DFCC@80Hz", 80, ppm, phase_ns)
    cfg = build_fcs_config(fcs_param_set(), clock=clk)
    k = np.arange(2400)
    t = truth_step_times_ns(k)
    fr, off, nxt = frame_schedule(cfg, 0, t)
    ss = samples_for_steps(clk, 0, t, truth_step_times_ns(k + 1))
    assert np.array_equal(fr, ss.count) and nxt == ss.next_index
    apply = latest_truth_steps(ss.times + cfg.delay_ns - 1) + 1
    tk = truth_step_times_ns(apply)
    assert np.all(tk >= ss.times + cfg.delay_ns)
    assert np.all(truth_step_times_ns(apply - 1) < ss.times + cfg.delay_ns)
    assert np.array_equal(off[ss.step], apply - k[ss.step])
    n_next, fr1, off1 = 0, [], []
    for j in range(k.size):
        a, b, n_next = frame_schedule(cfg, n_next, t[j : j + 1])
        fr1.append(a[0])
        off1.append(b[0])
    assert np.array_equal(fr, fr1) and np.array_equal(off, off1) and n_next == nxt


@pytest.mark.integration
def test_lane_ports_declare_the_dfcc_frame_clock():
    """Conformance clock rule (AD-36 §8, AD-42; W2.1c retires the E1-MF tracked M05 exception): every DFCC
    lane input declares the DFCC acquisition clock its sample buffer is on, in the module-level ``ports()``
    and in an ``Fcs`` instance (the clock its frames run on), and it is each M13 lane producer's clock;
    non-lane inputs stay in the module's rate group. Negative control: the W1 declaration (rate None) and a
    foreign clock are both reported by the gate's clock rule. n = 88 lane ports (one configuration)."""
    from dataclasses import replace

    from test_interface_conformance import (
        CONFIGS,
        clock_problems,
        config_pubs,
        lane_producer_ports,
        producers,
    )

    from phalanx.fcs.module import Fcs
    from phalanx.fcs.ports import dfcc_clock, lane_inputs, ports

    ins, _, b = ports()
    lanes = [p for p in ins if b[p.name].startswith("lane.")]
    assert len(lanes) == len(lane_inputs()) == 88
    clock = dfcc_clock()
    assert clock == acquisition_clock("DFCC", 80) == Fcs.from_registry("fcs").cfg.clock
    assert all(p.rate == clock for p in lanes)
    assert all(p.rate is None for p in ins if not b[p.name].startswith("lane."))
    inst = {p.name: p for p in Fcs.from_registry("fcs").ports_in}
    assert all(inst[p.name].rate == clock for p in lanes)
    prods, _ = producers(config_pubs(CONFIGS["e1"]), lane_producer_ports(1))
    assert all(clock_problems(p, prods[b[p.name]]) == [] for p in lanes)
    probe = lanes[0]
    prod = prods[b[probe.name]]
    assert clock_problems(replace(probe, rate=None), prod), "a lane port without its clock must fail"
    assert clock_problems(replace(probe, rate=ClockDomain("DFCC@80Hz", 80, 50, 0)), prod)


@pytest.mark.unit
def test_clock_and_delay_validation():
    ps = fcs_param_set()
    with pytest.raises(ContractError):
        build_fcs_config(ps, clock=ClockDomain("x", 60))  # not the frame rate
    with pytest.raises(ContractError):
        build_fcs_config(ps.replace(compute_delay=0.0125), clock=ClockDomain("DFCC@80Hz", 80))
    assert build_fcs_config(ps).tf == float(Fraction(1, 80))


@pytest.mark.integration
def test_recorded_channels_track_the_dfcc_state():
    """Recorded words equal the catalogue outputs they duplicate (law, channel status); voted values equal the
    common lane value; elevon commands equal the applied commands; NOT_MODELLED and RECORDED partition the 56
    DFCC-computed dictionary channels."""
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(120)
    for c in "abcd":
        inp[L("rsa_q", c)][:] = 0.01
        inp[L("pos_elevon_lib", c)][:] = 0.02
    st, out = run(mod, st, inp)
    assert np.array_equal(out["rec_fcs_mode_law"], out["law_state"])
    for c, name in enumerate("abcd"):
        assert np.array_equal(out[f"rec_fcs_ch_status_{name}"], out["channel_status"][:, c])
    assert out["rec_fcs_voted_q"][-1] == 0.01 and out["rec_fcs_elevon_lib_pos_v"][-1] == 0.02
    assert out["rec_fcs_voted_de"][-1] == pytest.approx(0.005)
    assert out["rec_fcs_elevon_lob_cmd"][-1] == st["f"][mod_cmd(0)]
    assert out["rec_av_lru_bit_dfcc"][-1] == 0 and out["rec_fcs_mode_flags"].dtype == np.int64
    from phalanx.dictionary import load_dictionary

    d = load_dictionary()
    computed = {
        cid
        for cid in d.channel_ids()
        if d.channel(cid).get("signal") == "computed" and d.channel(cid).get("acq_lru") == "DFCC"
    }
    assert set(REC_CHANNELS) | set(NOT_MODELLED) == computed
    assert not set(REC_CHANNELS) & set(NOT_MODELLED) and len(RECORDED) == 48 and len(computed) == 56


def mod_cmd(s):
    from phalanx.fcs.layout import F_CMD

    return F_CMD + s


@pytest.mark.integration
def test_stuck_wow_switch_event_selects_ground_law_in_flight_and_clears():
    """fcs.wow_fault: both main-gear switches stuck on in flight -> GROUND law after the 2-frame persistence
    (the false-WoW cascade path through the event interface); clearing the faults returns to SCHEDULED; the
    nose switch alone does not select the ground law (main-gear logic)."""
    mod = make()
    st = mod.init(mod.params, None)
    for leg in (1, 2):
        ev = Event(0, "fcs.wow_fault", "fcs", {"leg": leg, "value": 1, "active": True})
        st, _ = mod.on_event(st, ev, 0)
    st, out = run(mod, st, base_inputs(30))
    assert out["law_state"][0] == LAW_SCHEDULED and out["law_state"][-1] == LAW_GROUND
    assert int(np.argmax(out["law_state"] == LAW_GROUND)) == 3  # second frame (n_wow = 2)
    for leg in (1, 2):
        ev = Event(0, "fcs.wow_fault", "fcs", {"leg": leg, "value": 1, "active": False})
        st, _ = mod.on_event(st, ev, 0)
    st, _ = mod.on_event(st, Event(0, "fcs.wow_fault", "fcs", {"leg": 0, "value": 1, "active": True}), 0)
    st, out = run(mod, st, base_inputs(30), 30)
    assert out["law_state"][-1] == LAW_SCHEDULED
    with pytest.raises(ContractError):
        mod.on_event(st, Event(0, "fcs.wow_fault", "fcs", {"leg": 3, "value": 1, "active": True}), 0)


@pytest.mark.integration
def test_lane_failure_sets_cbit_fail_in_lru_bit_word():
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(60)
    inp[L("rsa_p", "c")][:] = 1.0
    st, out = run(mod, st, inp)
    assert out["rec_av_lru_bit_dfcc"][0] == 0 and out["rec_av_lru_bit_dfcc"][-1] == LRU_CBIT_FAIL
