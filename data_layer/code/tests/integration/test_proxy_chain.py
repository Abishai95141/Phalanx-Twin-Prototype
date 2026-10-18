"""W2.4a-1 proxy chain (no data): U4 wiring from the published bindings, fused loop == modules bitwise,
snapshot -> restore -> continue, governed replay, and the MF1 word-skew prototype flag.

Sample: deterministic synthetic recorded inputs (``phalanx.proxy.inputs.synthetic_inputs``; no DASHlink file,
no randomness in the inputs): a 20,000 ft / M 0.6 cruise condition with N1-command steps (A/T engaged) or
lever steps (manual). Windows of 4-30 s (960-7,200 truth steps): the smallest that contain a full step
response of the spools and several FADEC frames and ACMS samples. One 4-engine configuration (the proxy).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.rng import KeyPath
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.state import trees_equal
from phalanx.fadec.codes import L_GOV_N2
from phalanx.proxy.config import load_proxy_config
from phalanx.proxy.inputs import synthetic_inputs
from phalanx.proxy.run import simulate_flight
from phalanx.proxy.system import ORDER, _connections, build_proxy_system, wiring_problems

pytestmark = pytest.mark.integration
ID = KeyPath.of(scenario="proxy-chain-test", tail="T687", sortie=1)


@pytest.fixture(scope="module")
def cfg():
    return load_proxy_config()


def test_u4_chain_is_wired_from_bindings_alone(cfg):
    """Every input of every module is served by a producer port of identical shape/dtype/compatible unit;
    the recorded flight condition (af.mach/tas/alt, scenario.phase) comes from the replay producers."""
    rec = synthetic_inputs(4.0).replay_inputs()
    ps = build_proxy_system(cfg, rec, identity=ID, root=3)
    assert wiring_problems(ps.modules, ps.connections) == []
    src = {c.dst: c.src for c in ps.connections}
    assert src["eng.mach"] == "af.mach"
    assert src["acq.phase"] == "scenario.phase"
    assert tuple(ps.modules) == ORDER


def test_u4_negative_control_missing_replay_producer_is_reported(cfg):
    """Without the airframe replay producer the gate reports the unserved recorded flight condition."""
    rec = synthetic_inputs(4.0).replay_inputs()
    ps = build_proxy_system(cfg, rec, identity=ID, root=3)
    assert wiring_problems(ps.modules, _connections(ps.modules)) == []
    mods = {k: v for k, v in ps.modules.items() if k != "af"}
    probs = wiring_problems(mods, ps.connections)
    assert "eng.mach: producer port af.mach does not exist" in probs, probs


@pytest.mark.determinism
@pytest.mark.parametrize("block_len", [240, 1000])
def test_fused_loop_equals_modules_bitwise(cfg, block_len):
    """The compiled ProxyLoopGroup reproduces the module System exactly: every port of every step and the
    final state of every module (block lengths that do and do not align with the FADEC frame)."""
    rec = synthetic_inputs(5.0, steps=((1.0, 3.0),)).replay_inputs()
    res = {}
    for fused in (False, True):
        s = build_proxy_system(cfg, rec, identity=ID, root=5, fused=fused, block_len=block_len).system
        res[fused] = s.run(s.start(), 1200, mode="block", record=s.output_ports())
    (w0, t0), (w1, t1) = res[False], res[True]
    bad = [k for k in t0.ports if not np.array_equal(t0.ports[k], t1.ports[k])]
    assert bad == []
    assert all(trees_equal(w0.states[m], w1.states[m]) for m in w0.states)
    assert t0.digest() == t1.digest()


@pytest.mark.determinism
def test_snapshot_restore_continue_is_bitwise(cfg):
    """snapshot -> restore -> continue == an uninterrupted run (fused proxy System)."""
    rec = synthetic_inputs(8.0, steps=((2.0, 3.0),)).replay_inputs()
    s = build_proxy_system(cfg, rec, identity=ID, root=9, fused=True, block_len=480).system
    w_full, t_full = s.run(s.start(), 1920, mode="block", record=["eng.n1", "eng.wf", "acq.lane_eng_n1_a"])
    w_half, _ = s.run(s.start(), 960, mode="block")
    w_back = restore(s, snapshot(s, w_half))
    w_end, t_end = s.run(w_back, 960, mode="block", record=["eng.n1", "eng.wf", "acq.lane_eng_n1_a"])
    assert all(trees_equal(w_full.states[m], w_end.states[m]) for m in w_full.states)
    for k in ("eng.n1", "eng.wf"):
        assert np.array_equal(t_full.ports[k][960:], t_end.ports[k])


def test_governed_replay_tracks_the_n1_command(cfg):
    """A/T engaged cruise with +-2 % N1-command steps: the fuel stays on the N2 governor (no clamp or limiter
    in a normal replay, A-W2.4a-13) and the recorded N1 settles on the command, with the configured
    autothrottle gains (identified on 687-CAL, W2.4a-2 stage 5) and with the MF1 base gains. The tracking is a
    property of the deterministic loop, so the process-disturbance bank is off: the identified bank (stage 4)
    moves N1 by up to about 0.7 % over a few seconds (fast-band SD about 0.14 %), which this tolerance is not
    about; the bank's own behaviour is tested by the battery (stage 6) and the M03 PSD tests."""
    inp = synthetic_inputs(30.0, steps=((8.0, 2.0), (18.0, -2.0)))
    cfg = cfg.with_factors(tuple(f for f in cfg.env.factors if f.group != 0))
    sf = simulate_flight(cfg, inp, identity=ID, root=11)
    mf1 = simulate_flight(
        cfg,
        inp,
        identity=ID,
        root=11,
        fadec_params=cfg.fadec_params.replace(at_kp=0.3, at_ki=0.2, at_rate=0.1),
    )
    assert sf.limiter_share[L_GOV_N2] > 0.99, sf.limiter_share
    n1 = sf.record.outputs["N1"]
    cmd = inp.n1_cmd_pct[: n1.shape[1]]
    # after each step (8 s up, 18 s down): 16-18 s and 27-30 s. The first 8 s are the settle from the trim at
    # the lever's ground-reference demand (W2.4a-2, A-W2.4a-14), which starts about 1 % N1 below the command
    settled = np.r_[np.arange(64, 72), np.arange(108, 120)]
    assert np.max(np.abs(n1[:, settled] - cmd[settled])) < 0.6, np.abs(n1[:, settled] - cmd[settled]).max()
    n1b = mf1.record.outputs["N1"]
    assert np.max(np.abs(n1b[:, settled] - cmd[settled])) < 0.6, np.abs(n1b[:, settled] - cmd[settled]).max()
    # negative control: the W1 fixture A/T gains (0.05/0.02/0.05) do not reach the command within 6 s
    w1 = cfg.fadec_params.replace(at_kp=0.05, at_ki=0.02, at_rate=0.05)
    slow = simulate_flight(cfg, inp, identity=ID, root=11, fadec_params=w1)
    assert np.max(np.abs(slow.record.outputs["N1"][:, 64:72] - cmd[64:72])) > 0.6


def test_word_delay_prototype_shifts_only_the_delayed_family(cfg):
    """PROTOTYPE flag (MF1 caveat a): a 0.25 s word delay on N1 makes the recorded N1 the undelayed one a
    sample later (4 Hz), at sensor level exactly; other families are untouched."""
    inp = synthetic_inputs(12.0, steps=((3.0, 3.0),))
    a = simulate_flight(cfg, inp, identity=ID, root=13)
    b = simulate_flight(cfg, inp, identity=ID, root=13, word_delay_s={"N1": 0.25})
    sa, sb = a.sensor.outputs, b.sensor.outputs
    assert np.array_equal(sb["N1"][:, 1:], sa["N1"][:, :-1])
    for f in ("N2", "EGT", "FF"):
        assert np.array_equal(sb[f], sa[f])
        assert np.array_equal(b.record.outputs[f], a.record.outputs[f])
    assert a.world_digest == b.world_digest  # the plant run is the same; only the recording changes
    with pytest.raises(ValueError, match="family"):
        simulate_flight(cfg, inp, identity=ID, root=13, word_delay_s={"PLA": 0.1})
