"""AD-22 kernel layout worked example (core/example_kernel.py): compiled == NumPy reference bitwise,
step == step_block, snapshot at a non-multiple of the internal sub-rate, complex-step derivative.

Samples: 2,400 ticks (10 s) for equality checks; block lengths 1/7/1024; 240 ticks for the derivative.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.example_kernel import (
    GOV_DIV,
    LAYOUT,
    N_SUB,
    P_K,
    PARAMS,
    TICK,
    ExampleOscillator,
    ExampleStepCommand,
    X,
    _kernel,
    example_params,
    kernel_reference,
)
from phalanx.core.layout import ParamLayout, StateLayout
from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.time import TRUTH_DT_S

N = 2400


def _system(compiled=True, block_len=1024, validate=False):
    osc = ExampleOscillator("osc", example_params(), compiled=compiled)
    cmd = ExampleStepCommand("cmd")
    return System(
        [cmd, osc],
        [Connection("cmd.u", "osc.u_ext")],
        rng=RngService(0xA22, StreamRegistry()),
        identity=KeyPath.of(scenario="layout", tail="T1", sortie=1),
        block_len=block_len,
        validate=validate,
        purity_check=validate,
    )


def _inputs(n=N):
    g = np.random.Generator(np.random.Philox(22))  # fixed test input, not a simulation stream
    return g.standard_normal(n), np.linspace(0.0, 3.0, n)


@pytest.mark.integration
def test_compiled_kernel_equals_numpy_reference_bitwise():
    st = LAYOUT.pack(x=0.1, v=0.0, u_cmd=0.0, tick=0, n_gov=0)
    p = PARAMS.vector(example_params())
    noise, u = _inputs()
    f1, i1, o1 = _kernel(st["f"], st["i"], p, u, noise, TRUTH_DT_S, N_SUB, GOV_DIV)
    f2, i2, o2 = kernel_reference(st["f"], st["i"], p, u, noise, TRUTH_DT_S, N_SUB, GOV_DIV)
    assert np.array_equal(o1, o2) and np.array_equal(f1, f2) and np.array_equal(i1, i2)
    assert i1[TICK] == N and np.array_equal(st["i"], [0, 0])  # inputs untouched (pure)
    # chunked calls (block length is a runtime value) reproduce the single call
    for chunk in (1, 7, 1000):
        f, i, outs = st["f"], st["i"], []
        for j in range(0, N, chunk):
            f, i, o = _kernel(f, i, p, u[j : j + chunk], noise[j : j + chunk], TRUTH_DT_S, N_SUB, GOV_DIV)
            outs.append(o)
        assert np.array_equal(np.concatenate(outs), o1), chunk


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("block_len", [1, 7, 1024])
def test_module_compiled_reference_step_and_block_all_agree(block_len):
    ref = _system(compiled=False)
    _, t_ref = ref.run(ref.start(), N, mode="step", record=ref.output_ports())
    s = _system(compiled=True, block_len=block_len)
    _w, t = s.run(s.start(), N, mode="block", record=s.output_ports())
    assert t.digest() == t_ref.digest()
    seg = next(sg for sg in s.execution()["segments"] if sg["members"] == ["osc"])
    assert seg["module_step_block"]
    u_cmd = t.ports["osc.u_cmd"]
    changes = np.flatnonzero(np.diff(u_cmd)) + 1
    assert set((changes % GOV_DIV).tolist()) == {0}  # internal 80 Hz governor, phase from int-state TICK


@pytest.mark.integration
def test_snapshot_mid_sub_rate_and_validation_mode():
    """Snapshot at k = 1201 (not a multiple of the internal sub-rate) continues bitwise."""
    s_ref = _system()
    w_ref, _ = s_ref.run(s_ref.start(), N)
    s1 = _system(validate=True)
    w1, _ = s1.run(s1.start(), 1201)
    s2 = _system()
    w2, _ = s2.run(restore(s2, snapshot(s1, w1)), N - 1201)
    assert snapshot(s2, w2) == snapshot(s_ref, w_ref)


@pytest.mark.integration
def test_complex_step_derivative_matches_central_difference():
    """AD-34 pattern: the same kernel source on complex128 gives d x_L / d stiffness."""
    st = LAYOUT.pack(x=0.1, v=0.0, u_cmd=0.0, tick=0, n_gov=0)
    p = np.array(PARAMS.vector(example_params()))
    noise, u = _inputs(240)
    h = 1e-30
    pc = p.astype(np.complex128)
    pc[P_K] += 1j * h
    fc, _, _ = _kernel(st["f"].astype(np.complex128), st["i"], pc, u, noise, TRUTH_DT_S, N_SUB, GOV_DIV)
    d_cs = fc[X].imag / h
    eps = 1e-6 * p[P_K]
    pp, pm = p.copy(), p.copy()
    pp[P_K] += eps
    pm[P_K] -= eps
    fp, _, _ = _kernel(st["f"], st["i"], pp, u, noise, TRUTH_DT_S, N_SUB, GOV_DIV)
    fm, _, _ = _kernel(st["f"], st["i"], pm, u, noise, TRUTH_DT_S, N_SUB, GOV_DIV)
    d_fd = (fp[X] - fm[X]) / (2 * eps)
    assert d_cs != 0.0 and abs(d_cs - d_fd) <= 1e-6 * abs(d_cs)
    assert fc[X].real == _kernel(st["f"], st["i"], p, u, noise, TRUTH_DT_S, N_SUB, GOV_DIV)[0][X]


@pytest.mark.unit
def test_layout_guards():
    with pytest.raises(ContractError):
        StateLayout("s", 1, ("a", "a"), ())
    with pytest.raises(ContractError):
        StateLayout("s", 1, ("a",), ("a",))
    lay = StateLayout("s", 1, ("a", "b"), ("n",))
    with pytest.raises(ContractError, match="missing"):
        lay.pack(a=1.0, n=0)
    st = lay.pack(a=1.0, b=2.0, n=3)
    assert lay.unpack(st) == {"a": 1.0, "b": 2.0, "n": 3} and st["f"].dtype == np.float64
    with pytest.raises(ContractError):
        lay.f.check(a=1, b=0)  # constants drifted from the names
    with pytest.raises(ContractError):
        ParamLayout(("nope",)).vector(example_params())
    assert PARAMS.vector(example_params()).flags.writeable is False
