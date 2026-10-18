"""A6 for M06: kernel == NumPy reference bitwise (in process and NUMBA_DISABLE_JIT subprocess), step ==
step_block, snapshot round-trip, validation mode, events, initial outputs, two-engine (proxy) configuration.

Scenario: M1.4/11 km trim (statically stable, so open-loop runs stay bounded) with scripted elevon/rudder
inputs and turbulence for 600-2,400 ticks; n = 1 deterministic scenario per check.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from test_fcs_fixtures import SignalSource

from phalanx.airframe.analysis import HYD_P_NOMINAL, Condition, make_ic, reference_mass_properties, trim
from phalanx.airframe.build import airframe_param_set, build_config
from phalanx.airframe.kernel import F_HGND, airframe_kernel, kernel_reference
from phalanx.airframe.module import Airframe, unpack_outputs
from phalanx.airframe.ports import ports
from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.time import TRUTH_DT_S

SRC = Path(__file__).resolve().parents[2] / "src"
PS = airframe_param_set()
CFG = build_config(PS, 1)
M0, CG0, J0 = reference_mass_properties(PS)
COND = Condition(11000.0, 1.4, M0, CG0, J0)
TRIM = trim(CFG, COND, guess=(0.03, 0.0, 5e4))
IC = make_ic(CFG, COND, TRIM, h_ground=0.0)


def _values():
    u = TRIM.u
    o = 14
    return {
        "surf_pos": u[0:13],
        "thrust": u[13:14],
        "mass": u[o],
        "cg": u[o + 1 : o + 4],
        "inertia": u[o + 4 : o + 13].reshape(3, 3),
        "rho": u[o + 13],
        "a_sound": u[o + 14],
        "t_s": u[o + 15],
        "wind_ned": np.zeros(3),
        "turb_vel_body": np.zeros(3),
        "turb_rate_body": np.zeros(3),
        "gear_cmd": 0,
        "brake_cmd": np.zeros(2),  # AD-47 inputs: brakes off, chute stowed, nominal hydraulics
        "chute_state": 0,
        "hyd_p": np.full(2, HYD_P_NOMINAL),
    }


def _script(k: int) -> dict:
    t = k * TRUTH_DT_S
    s = TRIM.u[0:13].copy()
    if 0.5 < t < 1.5:
        s[0:4] += 0.02
        s[4] = 0.03
    return {"surf_pos": s, "turb_vel_body": np.array([0.0, 1.0 * np.sin(3 * t), 0.5 * np.cos(2 * t)])}


def _system(*, compiled=True, block_len=240, validate=False):
    ins, _, _ = ports(1)
    src = SignalSource("src", ins, _values(), _script)
    af = Airframe.from_registry("af", IC, compiled=compiled)
    return System(
        [src, af],
        [Connection(f"src.{p.name}", f"af.{p.name}") for p in ins],
        rng=RngService(0xA1F, StreamRegistry()),
        identity=KeyPath.of(scenario="w12", tail="T1", sortie=1),
        block_len=block_len,
        validate=validate,
        purity_check=validate,
    )


def _rows(n):
    u = np.repeat(TRIM.u[None, :], n, axis=0)
    for k in range(n):
        d = _script(k)
        u[k, 0:13] = d["surf_pos"]
        u[k, 14 + 19 : 14 + 22] = d["turb_vel_body"]
    return u


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("block_len", [1, 7, 240])
def test_step_and_block_execution_bitwise(block_len):
    ref = _system()
    _, t_ref = ref.run(ref.start(), 600, mode="step", record=ref.output_ports())
    s = _system(block_len=block_len)
    _, t = s.run(s.start(), 600, mode="block", record=s.output_ports())
    assert t.digest() == t_ref.digest()


@pytest.mark.integration
def test_compiled_kernel_equals_python_reference_in_process():
    u = _rows(480)
    i0 = np.zeros(2, np.int64)
    a = airframe_kernel(TRIM.f, i0, CFG.dp, CFG.ap, CFG.tab, CFG.gtab, CFG.ttab, u, TRUTH_DT_S, 1, 0)
    b = kernel_reference(TRIM.f, i0, CFG.dp, CFG.ap, CFG.tab, CFG.gtab, CFG.ttab, u, TRUTH_DT_S, 1, 0)
    for x, y in zip(a, b, strict=True):
        assert np.array_equal(x, y)


_SUB = r"""
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import numpy as np
from test_airframe_module import CFG, TRIM, _rows
from phalanx.airframe.kernel import airframe_kernel
from phalanx.core.time import TRUTH_DT_S
f, i, o = airframe_kernel(TRIM.f, np.zeros(2, np.int64), CFG.dp, CFG.ap, CFG.tab, CFG.gtab, CFG.ttab,
_rows(600), TRUTH_DT_S, 1, 0)
np.save(sys.argv[3], np.concatenate([o.ravel(), f, i.astype(np.float64)]))
"""


@pytest.mark.integration
def test_compiled_kernel_equals_numba_disabled_reference(tmp_path):
    """NUMBA_DISABLE_JIT=1 (every helper uncompiled) reproduces the compiled kernel bit for bit (600
    ticks)."""
    out = tmp_path / "ref.npy"
    env = dict(os.environ, NUMBA_DISABLE_JIT="1")
    r = subprocess.run(
        [sys.executable, "-I", "-c", _SUB, str(SRC), str(Path(__file__).parent), str(out)],
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert r.returncode == 0, r.stderr[-3000:]
    f, i, o = airframe_kernel(
        TRIM.f,
        np.zeros(2, np.int64),
        CFG.dp,
        CFG.ap,
        CFG.tab,
        CFG.gtab,
        CFG.ttab,
        _rows(600),
        TRUTH_DT_S,
        1,
        0,
    )
    assert np.array_equal(np.load(out), np.concatenate([o.ravel(), f, i.astype(np.float64)]))


@pytest.mark.integration
@pytest.mark.fork
def test_snapshot_restore_continues_bitwise():
    s_ref = _system()
    w_ref, _ = s_ref.run(s_ref.start(), 2400)
    s1 = _system()
    w1, _ = s1.run(s1.start(), 1201)
    s2 = _system()
    w2, _ = s2.run(restore(s2, snapshot(s1, w1)), 1199)
    assert snapshot(s2, w2) == snapshot(s_ref, w_ref)


@pytest.mark.integration
def test_validation_mode_equals_production_and_initial_outputs():
    """Validation mode reproduces production; initial outputs are the trimmed state's outputs (nz ~ 1, alpha =
    trim alpha, Mach 1.4) and equal a zero-length evaluation of the kernel output stage."""
    traces = []
    for validate in (True, False):
        s = _system(validate=validate)
        _, t = s.run(s.start(), 240, record=s.output_ports())
        traces.append(t)
    assert traces[0].digest() == traces[1].digest()
    af = Airframe.from_registry("af", IC)
    io = af.initial_outputs(af.init(af.params, None))
    assert abs(io["alpha"] - TRIM.alpha) < 1e-9 and abs(io["mach"] - 1.4) < 1e-9
    assert abs(io["nz"] - 1.0) < 0.01 and io["wow"].dtype == np.int64
    assert abs(io["alt"] - 11000.0) < 1e-6


@pytest.mark.integration
def test_events_ground_elevation_and_retired_brake_chute_hooks():
    """``af.ground_elevation`` sets the local ground height; the W1 test hooks ``af.brake`` / ``af.chute`` are
    retired (AD-47: brakes and chute are the ``pilot.brake_cmd`` / ``util.chute_state`` ports), so M06 no
    longer handles them."""
    from phalanx.core.module import EventNotHandledError

    af = Airframe.from_registry("af", IC)
    st = af.init(af.params, None)
    brake = Event(0, "af.brake", "af", {"left": 0.5, "right": 1.0})
    for ev in (brake, Event(0, "af.chute", "af", {"state": 1})):
        with pytest.raises(EventNotHandledError):
            af.on_event(st, ev, 0)
    st, _ = af.on_event(st, Event(0, "af.ground_elevation", "af", {"h": 3256.0}), 0)
    assert st["f"][F_HGND] == 3256.0
    io = af.initial_outputs(st)  # af.hag = CG height above the local ground elevation (radar-altitude truth)
    assert io["hag"] == pytest.approx(io["alt"] - 3256.0, abs=1e-9)


@pytest.mark.integration
def test_two_engine_proxy_configuration():
    """n_engines = 2 (proxy mode): ports carry (2,) thrust; thrust geometry with one row per engine is
    required;
    equal thrust on two symmetric engines gives the same motion as the single-engine total (yaw-free)."""
    with pytest.raises(ContractError):
        build_config(PS, 2)  # the Tejas file has one engine row
    ps2 = PS.replace(
        thrust_points=np.array([[-5.0, -0.6, 0.0], [-5.0, 0.6, 0.0]]),
        thrust_axes=np.array([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]),
    )
    cfg2 = build_config(ps2, 2)
    u1 = TRIM.u
    u2 = np.concatenate([u1[0:13], [u1[13] / 2, u1[13] / 2], u1[14:]])
    _, _, o1 = airframe_kernel(
        TRIM.f,
        np.zeros(2, np.int64),
        CFG.dp,
        CFG.ap,
        CFG.tab,
        CFG.gtab,
        CFG.ttab,
        u1[None, :].repeat(240, 0),
        TRUTH_DT_S,
        1,
        0,
    )
    _, _, o2 = airframe_kernel(
        TRIM.f,
        np.zeros(2, np.int64),
        cfg2.dp,
        cfg2.ap,
        cfg2.tab,
        cfg2.gtab,
        cfg2.ttab,
        u2[None, :].repeat(240, 0),
        TRUTH_DT_S,
        2,
        0,
    )
    assert np.allclose(o1, o2, rtol=0, atol=1e-9)
    u2[13], u2[14] = u1[13] * 0.6, u1[13] * 0.4  # asymmetric thrust -> yaw
    _, _, o3 = airframe_kernel(
        TRIM.f,
        np.zeros(2, np.int64),
        cfg2.dp,
        cfg2.ap,
        cfg2.tab,
        cfg2.gtab,
        cfg2.ttab,
        u2[None, :].repeat(240, 0),
        TRUTH_DT_S,
        2,
        0,
    )
    assert unpack_outputs(o3)["omega_body"][-1, 2] > 1e-4  # more thrust on the left engine -> nose right
    ins, _outs, _ = ports(2)
    assert next(p for p in ins if p.name == "thrust").shape == (2,)
