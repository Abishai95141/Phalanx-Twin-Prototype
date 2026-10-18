"""A6: compiled kernel == NumPy reference bitwise, step_block == repeated step, complex-step-safe loop gains.

- The compiled `fadec_block` and the reference (same source, identity decorator) are replayed on the recorded
  lane buffers of an eventful closed-loop run (PLA steps, an AB that never lights - no-lights, retries,
  lockout - and a lane failure with heal) and must agree bitwise in state and outputs.
- `Fadec.step_block` over L steps equals L calls of `Fadec.step` bitwise (2 engines, a 67 Hz offset clock that
  puts 0 or 1 frames in a step, autothrottle engaged half-way).
- Loop gains are complex-step safe: d(J)/d(gain) by complex step (h = 1e-30) equals the central finite
  difference to 1e-3 relative, and the real part of the complex run is bitwise the real run (no branch
  depends on an imaginary part). J = mean N2 over the last 1 s + 100 x mean Wf over the last 2 s.

Sample sizes: 8 s replay (1,920 steps); 600 steps of step_block vs step; 6-8 s closed-loop runs per gain
(idealised lanes, `fine_lanes=True`, so the FD is not dominated by quantisation steps).
"""

from __future__ import annotations

import numpy as np
import pytest

import fadec_fixture as fx
from phalanx.core.time import ClockDomain, truth_step_times_ns
from phalanx.fadec import Fadec, FadecConfig
from phalanx.fadec.kernel import fadec_block
from phalanx.fadec.layout import P_LAYOUT
from phalanx.fadec.ports import LANE_PORTS, LANE_SLOT
from phalanx.fadec.reference import kernel_reference

pytestmark = pytest.mark.integration


def _eventful():
    n = 8 * 240
    t = np.arange(n) / 240.0
    pla = np.where(t < 2.0, 84.0, np.where(t < 3.0, 90.0, 110.0))[:, None]
    fm = np.zeros((n, 1, 12), np.int64)
    fv = np.zeros((n, 1, 12))
    fm[600:840, 0, 8] = 1  # PS3 lane A stuck at 0 for 1 s, then heals
    sc = fx.Scenario(n, 1, pla_deg=pla, ab_fault=np.array([1]), force_mask=fm, force_val=fv)
    return sc, fx.closed_loop(sc, x0=fx.steady_state(84.0))


def test_compiled_kernel_equals_the_numpy_reference_bitwise_on_eventful_inputs():
    sc, r = _eventful()
    codes = {int(m) for m in r.faults[:, 0]}
    assert len(codes) > 3  # eventful: several distinct fault words occurred
    cfg = FadecConfig.build(fx.fixture_params())
    s = sc.filled(r.lanes.shape[1])
    args = (
        cfg.p, cfg.tables, cfg.cfg, cfg.dt,
        np.ascontiguousarray(np.deg2rad(s.pla_deg)), s.p_amb, s.at_engage, s.at_n1_cmd, r.lanes, r.nfr,
    )  # fmt: skip
    a = fadec_block(r.f0, r.i0, *args)
    b = kernel_reference()(r.f0, r.i0, *args)
    for x, y in zip(a, b, strict=True):
        assert x.dtype == y.dtype and np.array_equal(x, y)
    assert np.array_equal(a[2], r.cmdf) and np.array_equal(a[3], r.cmdi)  # == the closed loop's own outputs


def test_step_block_equals_repeated_step_two_engines_offset_clock():
    clock = ClockDomain("FADEC", 67, offset_ppm=900, phase_ns=5_000_000)
    x0 = fx.steady_state(70.0, n_engines=2)
    kw = dict(
        n_engines=2, clock=clock, autothrottle=True, initial_wf=x0[:, fx.X_WF], initial_a8=x0[:, fx.X_A8]
    )
    a = Fadec("fadec", fx.fixture_params(), **kw)
    b = Fadec("fadec", fx.fixture_params(), **kw)
    L = 600
    g = np.random.Generator(np.random.Philox(key=[0x13B, 7]))
    base = np.stack([fx.lanes_from_state(x0[e]) for e in range(2)], axis=0)  # [e, 13]
    cap = a.capacity
    inputs = {
        "pla": np.tile(np.deg2rad([70.0, 72.0]), (L, 1)),
        "p0": np.full(L, 101325.0),
        "at_engage": (np.arange(L) >= L // 2).astype(np.int64),
        "at_n1_cmd": np.full((L, 2), 0.9),
    }
    for name, _cid, _u in LANE_PORTS:
        v = base[:, LANE_SLOT[name]]
        noise = 1.0 + 0.002 * g.standard_normal((L, cap, 2))
        inputs[name] = v[None, None, :] * noise
    t = truth_step_times_ns(np.arange(1, L + 1))
    sa, oa = a.step_block(a.init(a.params, None), inputs, t, 1 / 240)
    sb = b.init(b.params, None)
    rows = []
    for k in range(L):
        sb, ob = b.step(sb, {n: v[k] for n, v in inputs.items()}, int(t[k]), 1 / 240)
        rows.append(ob)
    for key in sa:
        assert np.array_equal(sa[key], sb[key]), key
    for name in oa:
        assert np.array_equal(oa[name], np.stack([r[name] for r in rows])), name
    assert np.unique(np.diff(np.flatnonzero(a.frame_schedule(a.init(a.params, None), t).count))).size > 1


_PART = dict(pla0=60.0, pla1=66.0, t_amb=288.15)
_SLAM = dict(pla0=45.0, pla1=75.0, t_amb=288.15)  # error beyond the 2 % dead zone: the large-signal path
_IRP = dict(pla0=84.0, pla1=90.0, t_amb=288.15)
_HOT = dict(pla0=84.0, pla1=90.0, t_amb=313.15)


def _J(r):
    return r.xs[-240:, 0, fx.X_N2].mean() + 100.0 * r.wf_cmd[-480:, 0].mean()


def _run(case, p_override=None, dtype=np.float64):
    n = (6 if case is _PART else 8) * 240
    pla = np.full((n, 1), case["pla0"])
    pla[240:, 0] = case["pla1"]
    sc = fx.Scenario(n, 1, pla_deg=pla, t_amb=np.full(n, case["t_amb"]))
    x0 = fx.steady_state(case["pla0"], t_amb=case["t_amb"])
    return fx.closed_loop(sc, x0=x0, dtype=dtype, p_override=p_override, fine_lanes=True)


@pytest.mark.parametrize(
    "gain,case",
    [
        ("gov_kp", _PART),
        ("gov_ki", _PART),
        ("gov_kff", _PART),
        ("gov_kl", _SLAM),
        ("n1_kp", _IRP),
        ("n1_ki", _IRP),
        ("a8_kp", _HOT),
    ],
)
def test_loop_gains_are_complex_step_safe(gain, case):
    p = FadecConfig.build(fx.fixture_params()).p
    j = P_LAYOUT.index[gain]
    pc = p.astype(np.complex128)
    h = 1e-30
    pc[j] += 1j * h
    rc = _run(case, pc, np.complex128)
    d_cs = float(np.imag(_J(rc)) / h)
    dp = 1e-5 * max(abs(p[j]), 1e-3)
    pp, pm = p.copy(), p.copy()
    pp[j] += dp
    pm[j] -= dp
    d_fd = (_J(_run(case, pp)) - _J(_run(case, pm))) / (2 * dp)
    assert abs(d_fd) > 1e-6, (gain, d_fd)  # the gain acts in this regime
    assert abs(d_cs - d_fd) <= 1e-3 * abs(d_fd), (gain, d_cs, d_fd)
    r = _run(case)
    assert np.array_equal(np.real(rc.xs), r.xs) and np.array_equal(np.real(rc.cmdf), r.cmdf)
    assert np.array_equal(rc.cmdi, r.cmdi)
