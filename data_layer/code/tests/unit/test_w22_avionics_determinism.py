"""W2.2 M12 avionics: determinism, state and forkability (RULES.md rule 5; AD-22, AD-36, AD-37).

One AvionicsSystem driven directly over a scenario that exercises every subsystem: a coordinated turn, low
altitude (radar altimeter tracking, terrain cells advancing), digitised ADC lanes, an SMS load and release,
and supply interruptions on every bus (in-flight INS freeze, AHRS restart, radar-altimeter dropout):

- compiled kernels == NumPy references (``py_func``), bitwise;
- per-step execution == block execution, and any block partition gives the same result, bitwise;
- snapshot (get_state bytes) -> restore -> continue == the uninterrupted run, bitwise;
- CRN: branches with different futures share their exogenous draws (sensor error states); identity keys
  separate units (tail / serial) and sorties;
- the scheduler's purity check passes on the full chain (no hidden state).

Sample: one sortie, 1,200 frames (5 s; 400 DFCC frames, every power transition); deterministic.
"""

from __future__ import annotations

import importlib.util
import itertools
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath
from phalanx.dictionary import load_dictionary
from phalanx.sensors.avionics import adc as A
from phalanx.sensors.avionics import ahrs as H
from phalanx.sensors.avionics import ins as N
from phalanx.sensors.avionics import radalt as R
from phalanx.sensors.avionics import sms as S
from phalanx.sensors.avionics.config import build_avionics_config
from phalanx.sensors.avionics.module import lane_port


def _fixture():
    name = "w22_avionics_fixture"
    if name not in sys.modules:
        p = Path(__file__).resolve().parents[1] / "integration" / "test_w22_avionics_fixture.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


FX = _fixture()
CFG = build_avionics_config()
N_FRAMES = 1200
LOAD = [3, 1, 1, 2, 0, 2, 1, 1, 3]


def scenario(n: int = N_FRAMES, bank: float = 30.0) -> dict:
    """Turn at low altitude with an interruption on each bus (INS bus in flight -> freeze)."""
    truth = FX.default_truth(n, hag=300.0, bank_deg={(0.5, 4.0): bank})
    v = np.array(truth["util.bus_v"], copy=True)
    v[300:330, CFG.bus["RADALT"]] = 0.0  # 125 ms: radar altimeter (and SMS) drop out and return
    v[500:520, CFG.bus["AHRS"]] = 0.0  # AHRS restart (fresh turn-on draw)
    v[700:760, CFG.bus["INGPS"]] = 0.0  # INS/GPS in flight: frozen
    truth["util.bus_v"] = v
    return truth


def truth_lanes(module, truth: dict) -> dict:
    """Digitised-lane stand-ins at the module boundary: every lane of a quad at the physical value (one sample
    per DFCC frame slot; the ADC reads slot 0 when its own DFCC schedule has a sample)."""
    n = truth["env.p_s"].shape[0]
    ps, ts, mach = truth["env.p_s"], truth["env.t_s"], truth["af.mach"]
    g = float(CFG.adc_p[A.P_GAMMA])
    pt = np.array([A.total_pressure(ps[k], mach[k], g) for k in range(n)])
    tat = ts * (1.0 + 0.5 * (g - 1.0) * mach * mach)
    value = {"AD.PS": ps, "AD.PT": pt, "AD.AOA_VANE_L": truth["af.alpha"], "AD.AOA_VANE_R": truth["af.alpha"]}
    value["AD.AOSS_VANE"] = truth["af.beta"]
    cap = next(p for p in module.ports_in if p.name == lane_port("AD.TAT")).shape[0]
    out = {}
    for cid in A.LANE_CHANNELS:
        src = tat if cid == "AD.TAT" else value[cid.rsplit(".", 1)[0]]
        out[lane_port(cid)] = np.repeat(np.asarray(src, np.float64)[:, None], cap, axis=1)
    return out


E_FRAME = (
    120  # mission loading and one release, applied between frames 119 and 120 (events act between steps)
)


def _events(module, state, k: int):
    t = k * 10**9 // 240
    state, _ = module.on_event(state, Event(t, S.LOAD_EVENT, "avio", {"stations": LOAD}), t)
    state, _ = module.on_event(state, Event(t, S.RELEASE_EVENT, "avio", {"station": 2, "mode": "release"}), t)
    return state


def run(module, truth, k0: int, n: int, state, *, block: int = 600, lanes=None, step: bool = False):
    """Frames [k0, k0 + n) in blocks of ``block`` (cut at E_FRAME, where the SMS events are applied)."""
    outs: dict[str, list] = {}
    lanes = truth_lanes(module, truth) if lanes is None else lanes
    cuts = sorted({k0, k0 + n} | ({E_FRAME} if k0 < E_FRAME < k0 + n else set()))
    for a, b in itertools.pairwise(cuts):
        if a == E_FRAME:
            state = _events(module, state, a)
        for k in range(a, b, block):
            m = min(block, b - k)
            inp = FX.direct_inputs(module, truth, k, m, lanes=lanes)
            t = np.arange(k, k + m, dtype=np.int64) * 10**9 // 240
            if step:
                for j in range(m):
                    state, o = module.step(state, {q: v[j] for q, v in inp.items()}, int(t[j]), FX.DT)
                    for q, v in o.items():
                        outs.setdefault(q, []).append(np.asarray(v)[None])
            else:
                state, o = module.step_block(state, inp, t, FX.DT)
                for q, v in o.items():
                    outs.setdefault(q, []).append(np.asarray(v))
    return state, {q: np.concatenate(v) for q, v in outs.items()}


def same(a: dict, b: dict) -> list[str]:
    """Names of entries that differ bitwise (empty = identical)."""
    assert a.keys() == b.keys()
    return [k for k in a if not np.array_equal(np.asarray(a[k]), np.asarray(b[k]))]


@pytest.fixture(scope="module")
def baseline():
    m = FX.make_module(config=CFG)
    truth = scenario()
    s, o = run(m, truth, 0, N_FRAMES, m.init(m.params, m.keys), block=100)
    return m, truth, s, o


@pytest.mark.determinism
def test_scenario_exercises_every_subsystem(baseline):
    _, _, s, o = baseline
    assert int(s["ins_i"][N.I_FROZEN]) == 1 and int(s["ahrs_i"][H.I_NPOWER]) == 1
    assert int(s["radalt_i"][R.I_CELL]) > 0 and np.all(o["radalt_ssm"] == R.SSM_NORMAL)
    assert int(s["sms_i"][S.I_NCMD]) == 1 and int(s["sms_i"][S.I_RELEASED]) in (0, 2)
    assert np.all(np.isfinite(o["rec_ad_hp"])) and np.any(np.diff(o["rec_ad_aoa"]) != 0.0)  # ADC on the lanes
    assert {int(x) for x in o["powered_radalt"]} == {0, 1}


@pytest.mark.determinism
def test_compiled_equals_reference_bitwise(baseline):
    _m, truth, s, o = baseline
    ref = FX.make_module(config=CFG, compiled=False)
    s2, o2 = run(ref, truth, 0, N_FRAMES, ref.init(ref.params, ref.keys), block=100)
    assert same(o, o2) == [] and same(s, s2) == []


@pytest.mark.determinism
def test_step_equals_block_and_partition_invariance(baseline):
    m, truth, s, o = baseline
    s1, o1 = run(m, truth, 0, N_FRAMES, m.init(m.params, m.keys), block=100, step=True)
    s2, o2 = run(m, truth, 0, N_FRAMES, m.init(m.params, m.keys), block=1200 // 7 + 1)
    assert same(o, o1) == [] and same(s, s1) == []
    assert same(o, o2) == [] and same(s, s2) == []


@pytest.mark.determinism
def test_snapshot_restore_continue_is_bitwise(baseline):
    m, truth, s, o = baseline
    for cut in (300, 715):  # during the radar-altimeter dropout; inside the INS hold-up window
        s_cut, o_a = run(m, truth, 0, cut, m.init(m.params, m.keys), block=100)
        blob = m.get_state(s_cut)
        m2 = FX.make_module(config=CFG)
        s_end, o_b = run(m2, truth, cut, N_FRAMES - cut, m2.set_state(blob), block=100)
        assert same(s, s_end) == []
        assert same(o, {k: np.concatenate([o_a[k], o_b[k]]) for k in o}) == []


@pytest.mark.determinism
def test_forks_share_exogenous_draws_and_identities_separate_them(baseline):
    """Fork at frame 200: a 60 deg bank future vs the 30 deg baseline future. The sensor error states driven
    only by the identity-keyed draws (IMU biases, GPS errors, AHRS biases, radar-altimeter installation) are
    identical; the outputs differ. Another tail gives other draws; another sortie of the same unit keeps the
    radar altimeter's installation errors (keyed by serial)."""
    m, truth, _s, _o = baseline
    s200, _ = run(m, truth, 0, 200, m.init(m.params, m.keys), block=100)
    other = scenario(bank=60.0)
    sb, ob = run(m, other, 200, N_FRAMES - 200, s200, block=100)
    sa, oa = run(m, truth, 200, N_FRAMES - 200, s200, block=100)
    for f, ks in (
        ("ins_f", (N.F_BG0, N.F_BGM, N.F_BA0, N.F_BAM, N.F_EGPS, N.F_EVGPS)),
        ("ahrs_f", (H.F_BG0, H.F_BGM, H.F_BA0)),
    ):
        for k in ks:
            assert np.array_equal(sa[f][k : k + 3], sb[f][k : k + 3]), (f, k)
    assert np.array_equal(
        sa["radalt_f"][R.F_SCALE : R.F_OFFSET + 1], sb["radalt_f"][R.F_SCALE : R.F_OFFSET + 1]
    )
    assert not np.array_equal(oa["rec_nav_ins_roll"], ob["rec_nav_ins_roll"])

    def init_state(**ident):
        mm = FX.make_module(config=CFG, identity=KeyPath.of(scenario="W22", **ident))
        st, _ = run(mm, truth, 0, 2, mm.init(mm.params, mm.keys), block=2)
        return st

    a = init_state(tail="KH2001", sortie="SRT0001")
    b = init_state(tail="KH2002", sortie="SRT0001")
    c = init_state(tail="KH2001", sortie="SRT0002")
    assert not np.array_equal(a["ins_f"][N.F_BG0 : N.F_BG0 + 3], b["ins_f"][N.F_BG0 : N.F_BG0 + 3])
    assert not np.array_equal(a["ins_f"][N.F_BG0 : N.F_BG0 + 3], c["ins_f"][N.F_BG0 : N.F_BG0 + 3])
    assert np.array_equal(
        a["radalt_f"][R.F_SCALE : R.F_OFFSET + 1], c["radalt_f"][R.F_SCALE : R.F_OFFSET + 1]
    )
    assert not np.array_equal(
        a["radalt_f"][R.F_SCALE : R.F_OFFSET + 1], b["radalt_f"][R.F_SCALE : R.F_OFFSET + 1]
    )


@pytest.mark.determinism
def test_chain_purity_check_passes():
    """The scheduler's validation and purity check (inputs not mutated, outputs a pure function of state and
    inputs) on the truth -> M12 -> M13 -> avionics chain, 48 frames."""
    d = load_dictionary()
    truth = FX.default_truth(48)
    system, _, _mods = FX.build_avionics_chain(d, truth, validate=True)
    _, tr = system.run(system.start(), 48, record=["avio.rec_ad_hp", "avio.rec_nav_ins_lat"])
    assert np.all(np.isfinite(tr.ports["avio.rec_ad_hp"]))
    assert math.isfinite(float(tr.ports["avio.rec_nav_ins_lat"][-1]))
