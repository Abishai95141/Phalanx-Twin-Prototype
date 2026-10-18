"""A5: the fused M09 kernel is bitwise equal to its uncompiled reference (py_func, and the fully uncompiled
NUMBA_DISABLE_JIT=1 run in a subprocess), block length is a runtime value, and the hydraulics, fuel and
thermal paths are complex-step safe (complex-step derivative == central finite difference).

Samples: 2,400 ticks (10 s) of a scripted profile exercising every subsystem; 480 ticks for derivatives.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

UNIT = Path(__file__).resolve().parents[1] / "unit"
sys.path.insert(0, str(UNIT))
from test_utilities_support import G0, N2_100, inputs  # noqa: E402

from phalanx.utilities import Utilities, UtilitiesConfig, config_vector, load_m09_params, param_vector  # noqa: E402
from phalanx.utilities import layout as L  # noqa: E402
from phalanx.utilities.jfs import JFS_CRANK  # noqa: E402
from phalanx.utilities.kernel import kernel_reference, utilities_kernel  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DT = 1 / 240


def profile(n: int = 2400) -> dict[str, np.ndarray]:
    """TEST FIXTURE profile: N2 swing, hydraulic bursts, pitch/acceleration cycle, a braked ground segment,
    a health vector with non-zero entries, and the JFS cranking (set in the state below)."""
    k = np.arange(n)
    s = k * DT
    n2f = 0.8 + 0.15 * np.sin(2 * np.pi * s / 7.0)
    h = np.zeros(L.N_HEALTH)
    h[[L.H_PUMP_LEAK, L.H_FILTER, L.H_HX_FOUL, L.H_BRAKE_WEAR, L.H_TYRE_WEAR]] = (0.2, 0.3, 0.2, 0.4, 0.3)
    inp = inputs(
        n,
        n2f=n2f,
        p3=2.8e5 + 3.6e5 * (n2f - 0.75) / 0.22,
        t3=450.0 + 265.0 * (n2f - 0.75) / 0.22,
        wf=0.4 + 2.5 * (np.sin(2 * np.pi * s / 5.0) > 0.7),
        demand=6e-4 * (np.sin(2 * np.pi * s / 1.3) > 0.5),
        fspec=np.stack(
            [3.0 * np.sin(2 * np.pi * s / 3.0), 0.5 * np.cos(s), -G0 * (1 + 0.3 * np.sin(s))], axis=1
        ),
        tas=np.where(s < 5.0, 60.0 - 10.0 * s, 150.0),
        mach=0.3,
        health=h,
        alt=2000.0,
        wow=np.where(s[:, None] < 5.0, 1, 0) * np.ones((1, 3)),
        pbrk=np.where(s[:, None] < 5.0, 2e5, 0.0) * np.ones((1, 2)),
        wheel=np.where(s[:, None] < 4.0, 150.0, 0.0) * np.ones((1, 2)),
    )
    return inp


def _setup(dtype=np.float64):
    ps = load_m09_params()
    m = Utilities("util", ps, config=UtilitiesConfig(drop_tanks=(True, True, True), batt_soc=0.7))
    st = m.init(ps, None)
    st["i"][L.I_JFS_MODE] = JFS_CRANK  # exercise the starter-motor/battery path too
    st["i"][L.I_JFS_ATTEMPT] = 1
    u = m.pack_inputs(profile(), 2400)
    return m, st, param_vector(ps), config_vector(ps, 1), u


def _digest(*arrays) -> str:
    h = hashlib.blake2b(digest_size=16)
    for a in arrays:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


@pytest.mark.integration
@pytest.mark.determinism
def test_compiled_kernel_equals_reference_bitwise_and_chunking():
    _m, st, p, cfg, u = _setup()
    f1, i1, o1, oi1 = utilities_kernel(st["f"], st["i"], p, u, cfg, 0.3, DT)
    f2, i2, o2, oi2 = kernel_reference(st["f"], st["i"], p, u, cfg, 0.3, DT)
    assert (
        np.array_equal(f1, f2)
        and np.array_equal(i1, i2)
        and np.array_equal(o1, o2)
        and np.array_equal(oi1, oi2)
    )
    assert np.all(np.isfinite(o1))
    for chunk in (1, 7, 1000):
        f, i, outs = st["f"], st["i"], []
        for j in range(0, u.shape[0], chunk):
            f, i, o, _ = utilities_kernel(f, i, p, u[j : j + chunk], cfg, 0.3, DT)
            outs.append(o)
        assert np.array_equal(np.concatenate(outs), o1), chunk
    assert np.array_equal(st["i"][L.I_TICK], 0)  # inputs untouched (pure)


SCRIPT = "\n".join(
    [
        "import sys",
        "sys.path.insert(0, sys.argv[1])",
        "sys.path.insert(0, sys.argv[2])",
        "from test_utilities_kernel_profile import run_digest",
        "print(run_digest())",
    ]
)


@pytest.mark.integration
@pytest.mark.determinism
def test_fully_uncompiled_run_is_bitwise_equal(tmp_path):
    """NUMBA_DISABLE_JIT=1 (every leaf in Python/NumPy) gives the compiled run's digest bitwise (fresh
    process)."""
    helper = tmp_path / "test_utilities_kernel_profile.py"
    helper.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(UNIT)!r})\n"
        f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n"
        "from test_utilities_kernel import _setup, _digest\n"
        "from phalanx.utilities.kernel import utilities_kernel\n"
        "def run_digest():\n"
        "    _m, st, p, cfg, u = _setup()\n"
        "    f, i, o, oi = utilities_kernel(st['f'], st['i'], p, u, cfg, 0.3, 1 / 240)\n"
        "    return _digest(f, i, o, oi)\n",
        encoding="utf-8",
    )
    _m, st, p, cfg, u = _setup()
    expect = _digest(*utilities_kernel(st["f"], st["i"], p, u, cfg, 0.3, DT))
    env = dict(os.environ, NUMBA_DISABLE_JIT="1")
    res = subprocess.run(
        [sys.executable, "-I", "-c", SCRIPT, str(REPO / "src"), str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == expect


PARAMS_CS = (
    ("hyd_q_rated", "hyd_p"),
    ("hyd_beta", "hyd_p"),
    ("hyd_q_leak_int", "hyd_p"),
    ("hyd_acc_pre", "hyd_p"),
    ("hyd_hx_ua", "hyd_t"),
    ("hyd_c_metal", "hyd_t"),
    ("fuel_ua_skin", "fuel_t"),
    ("fuel_cp", "fuel_t"),
    ("hyd_dp_band", "hyd_p"),
    ("ecs_phx_ua", "ecs_phx"),
    ("brk_cp", "brk_t"),
    ("batt_r0", "batt_soc"),
)


def _observe(f, o, what):
    return {
        "hyd_p": o[-1, L.O_HYD_P],
        "hyd_t": o[-1, L.O_HYD_T],
        "fuel_t": f[L.F_FUEL_T],
        "fuel_f2": f[L.F_FUEL_M + L.T_F2],
        "ecs_phx": o[-1, L.O_ECS_T + L.E_PHX],
        "brk_t": o[-1, L.O_BRK_T],
        "batt_soc": f[L.F_BATT_SOC],
    }[what]


@pytest.mark.integration
@pytest.mark.parametrize("name,what", PARAMS_CS)
def test_complex_step_matches_central_difference(name, what):
    """AD-34: the same kernel source on complex128 gives d(output)/d(parameter); compared with a central
    finite difference to 5e-5 relative (12 parameters across hydraulics, fuel, ECS, brakes, battery). The FD
    step is 1e-4 relative: several outputs are ~300 K with derivatives ~1e-6, so smaller FD steps are
    round-off dominated while the complex step (h = 1e-30) is exact to machine precision."""
    _m, st, p, cfg, u = _setup()
    u = u[:480]
    j = L.P_NAMES.index(name)
    h = 1e-30
    pc = p.astype(np.complex128)
    pc[j] += 1j * h
    fc, _, oc, _ = utilities_kernel(st["f"].astype(np.complex128), st["i"], pc, u, cfg, 0.3, DT)
    d_cs = _observe(fc, oc, what).imag / h
    eps = 1e-4 * abs(p[j])
    pp, pm = p.copy(), p.copy()
    pp[j] += eps
    pm[j] -= eps
    fp, _, op, _ = utilities_kernel(st["f"], st["i"], pp, u, cfg, 0.3, DT)
    fm, _, om, _ = utilities_kernel(st["f"], st["i"], pm, u, cfg, 0.3, DT)
    d_fd = (_observe(fp, op, what) - _observe(fm, om, what)) / (2 * eps)
    f0, _, o0, _ = utilities_kernel(st["f"], st["i"], p, u, cfg, 0.3, DT)
    assert _observe(fc, oc, what).real == _observe(f0, o0, what)  # real part is the float run, bitwise
    assert d_cs != 0.0
    assert abs(d_cs - d_fd) <= 5e-5 * abs(d_cs) + 1e-12, (d_cs, d_fd)


@pytest.mark.integration
def test_proxy_mode_two_engines_runs_and_splits_the_pto_load():
    """n_engines = 2 (proxy readiness): pumps mapped to engines 0 and 1 by parameters, not code."""
    ps = load_m09_params().replace(hyd_pump_engine=np.array([0.0, 1.0]))
    m = Utilities("util", ps, n_engines=2)
    st = m.init(ps, None)
    inp = inputs(240, ne=2, n2f=0.9, demand=5e-4)
    st, out = m.step_block(st, inp, np.arange(240, dtype=np.int64), DT)
    assert out["pto_power"].shape == (240, 2) and out["bleed_extract"].shape == (240, 2)
    assert (
        out["pto_power"][-1, 1] > 0.0 and out["pto_power"][-1, 0] > out["pto_power"][-1, 1]
    )  # gen on engine 0
    assert np.allclose(out["bleed_extract"][-1, 0], out["bleed_extract"][-1, 1])
    assert N2_100 > 0
