"""M04 airborne guidance (W2.1a-2, A-W2.1-12): one continuous lateral law, energy management in turns, and the
load-factor command rate limit.

The pilot is driven open loop with frozen aircraft states (a MISSION segment, wings level, level flight at
3,000 m) and its steady stick outputs are read after 1.5 s (the pilot delay and the neuromuscular lag have
settled; remnant off). n = 1 pilot (gain 1), deterministic.

- the commanded roll stick is a continuous, monotone function of the track error and saturates at the
  segment's bank limit (no turn/track switch: the old law stepped from acos(1/Nz) to k e at 0.15 rad);
- a turn primitive's bank limit relaxes with the energy state: slower than its target speed, a smaller
  saturated roll command and a smaller pull;
- a manoeuvre primitive slower than its target speed trades height: at its target altitude the pitch stick
  asks for less than 1 g (a descent), above h_safe only;
- the pitch stick moves at most nz_rate g/s (in stick units) after a step in the guidance demand.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import NS_PER_S, TRUTH_DT_S, TRUTH_HZ
from phalanx.pilot import kernel as K
from phalanx.pilot.module import PilotModule, load_pilot_config
from phalanx.scenario import phases as PH
from phalanx.scenario.plan import (
    N_SEG_F,
    N_SEG_I,
    S_ALT,
    S_HDG,
    S_MACH,
    S_NZ,
    S_PHASE,
    S_PLA,
    S_PLA_HI,
    S_PLA_LO,
    S_PRIM,
    S_TURN,
    SortiePlan,
)

pytestmark = pytest.mark.unit
CFG = load_pilot_config()
DEG = math.pi / 180
FIELD = 200.0
ALT = 3000.0
A_SOUND = 328.6  # ISA at 3,000 m
MACH = 0.8
V = MACH * A_SOUND


def _plan(*, turn: int, nz_t: float, prim: int, alt_t: float = ALT, hdg: float = 0.0) -> SortiePlan:
    seg_f = np.zeros((2, N_SEG_F))
    seg_i = np.zeros((2, N_SEG_I), np.int64)
    seg_f[:, S_ALT] = (FIELD, alt_t)
    seg_f[:, S_MACH] = MACH
    seg_f[:, S_HDG] = hdg
    seg_f[:, S_NZ] = (1.0, nz_t)
    seg_f[:, [S_PLA, S_PLA_LO, S_PLA_HI]] = 84.5 * DEG
    seg_i[:, S_PHASE] = PH.MISSION
    seg_i[1, S_PRIM] = prim
    seg_i[1, S_TURN] = turn
    traits = np.array([1, 1, 1, 1, 1.3, 0.36, 0.15, 1.0, 0.0])  # gain 1, remnant 0
    t_off = np.array([0, 1], dtype=np.int64) * NS_PER_S
    return SortiePlan(
        "T-1", "k", "T", "sq", 1, FIELD, 1, "PLT", False, 0, ("E",), 0, 2458.0,
        t_off, seg_f, seg_i, 600 * NS_PER_S, np.zeros(14), traits,
    )  # fmt: skip


def _steady(plan, *, track_deg=0.0, tas=V, seconds=1.5, cfg=CFG):
    """Stick outputs after ``seconds`` of a frozen state (level, wings level, ground track ``track_deg``)."""
    m = PilotModule("pilot", cfg, plan=plan)
    rng = RngService(7, StreamRegistry(m.streams))
    m.bind(rng.scope(KeyPath.of(scenario="u", tail="T", sortie="S")))
    st = m.init(m.params, m.keys)
    st["i"][K.I_STARTED] = 1
    n = round((1.0 + seconds) * TRUTH_HZ)
    chi = track_deg * DEG
    inputs = {
        "alt": np.full(n, ALT),
        "tas": np.full(n, tas),
        "mach": np.full(n, tas / A_SOUND),
        "vel_ned": np.tile([tas * math.cos(chi), tas * math.sin(chi), 0.0], (n, 1)),
        "quat": np.tile([math.cos(chi / 2), 0.0, 0.0, math.sin(chi / 2)], (n, 1)),
        "omega_body": np.zeros((n, 3)),
        "nz": np.ones(n),
        "wow": np.zeros((n, 3), np.int64),
        "n2": np.full((n, 1), 1.6e3),
    }
    t = (np.arange(n, dtype=np.int64) * NS_PER_S) // TRUTH_HZ
    res = m.step_block(st, inputs, t, TRUTH_DT_S)
    out = res[1]
    return np.asarray(out["stick_pitch"], dtype=float).ravel(), np.asarray(
        out["stick_roll"], dtype=float
    ).ravel()


def test_roll_command_is_continuous_and_saturates_at_the_turn_bank():
    plan = _plan(turn=1, nz_t=4.0, prim=11)
    errs = np.arange(0.0, 60.0, 2.0)
    sr = np.array([_steady(plan, track_deg=-e)[1][-1] for e in errs])  # target 0, track -e: turn right
    assert np.all(np.diff(sr) >= -1e-9)  # monotone in the error
    assert np.max(np.diff(sr)) < 0.08  # no step (the old law jumped ~0.3 at 8.6 deg)
    phi_lim = math.acos(1.0 / 4.0)
    p_full = CFG.vector[K.P_PFULL]
    sat = CFG.vector[K.P_KBANK] * phi_lim / p_full  # roll command at the bank limit from wings level
    assert sr[-1] == pytest.approx(sat, rel=0.02)


def test_turn_bank_limit_and_pull_relax_as_the_speed_decays():
    plan = _plan(turn=1, nz_t=4.0, prim=11)
    _sp_fast, sr_fast = _steady(plan, track_deg=-60.0, tas=V)
    _sp_slow, sr_slow = _steady(plan, track_deg=-60.0, tas=0.85 * V)
    assert sr_slow[-1] < sr_fast[-1]


def test_a_slow_manoeuvre_primitive_trades_height_for_speed():
    plan = _plan(turn=0, nz_t=1.0, prim=1)
    sp_on, _ = _steady(plan, tas=V)
    sp_slow, _ = _steady(plan, tas=0.8 * V)
    assert sp_on[-1] == pytest.approx(0.0, abs=0.01)  # on speed and height: 1 g
    assert sp_slow[-1] < -0.02  # below 1 g: a descent to regain speed


def test_pitch_stick_rate_is_limited():
    plan = _plan(turn=0, nz_t=1.0, prim=1, alt_t=ALT + 2000.0)  # a 2,000 m climb demand from level flight
    sp, _ = _steady(plan, seconds=1.0)
    rate = np.max(np.diff(sp)) * TRUTH_HZ  # stick units per second
    limit = CFG.vector[K.P_NZRATE] / min(CFG.vector[K.P_SNZP], CFG.vector[K.P_SNZN])  # stick scale per side
    assert sp[-1] > 0.05
    assert rate <= limit * 1.05, (rate, limit)
