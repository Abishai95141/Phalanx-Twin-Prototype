"""W0.2 A6 with a compiled kernel: a Numba ``step_block`` over explicit array state is bitwise identical
to the pure-Python per-step reference (the backend-neutral contract works with a compiled backend).

Sample: N = 2,400 steps; block lengths 1, 7 and 1,024. This is a contract check, not the AD-22 benchmark
(W0.6 owns that). Fastmath stays off; a change of Numba/LLVM defaults that fused multiply-adds would fail it.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.toy import ToySpringDamper, build_toy_system

numba = pytest.importorskip("numba")

N = 2400


@numba.njit(cache=False)
def _truth_kernel(x, v, k_s, m, c, sig, u, w, dt, n_sub):
    n = w.size
    xs = np.empty(n)
    vs = np.empty(n)
    h = dt / n_sub
    for i in range(n):
        f = sig * w[i] + u[i]
        for _ in range(n_sub):
            a = (f - c * v - k_s * x) / m
            v = v + h * a
            x = x + h * v
        xs[i] = x
        vs[i] = v
    return xs, vs


class NumbaTruth(ToySpringDamper):
    """The toy truth with a Numba-compiled step_block (same arithmetic as ``_advance``)."""

    version = "1.0.0-numba"

    def step_block(self, state, inputs, t, dt):
        n = t.size
        j0 = int(state["tick"])
        w = self.stream("process_force").draws(j0, n)
        u = np.ascontiguousarray(inputs["u"], dtype=np.float64) if self.controlled else np.zeros(n)
        x0, v0, k_s = float(state["x"]), float(state["v"]), float(state["stiffness"])
        xs, vs = _truth_kernel(x0, v0, k_s, self._m, self._c, self._sig, u, w, dt, self._nsub)
        new = {
            "x": np.array(xs[-1]),
            "v": np.array(vs[-1]),
            "stiffness": state["stiffness"].copy(),
            "tick": np.array(j0 + n),
        }
        return new, {"x": xs, "v": vs}


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("block_len", [1, 7, 1024])
def test_numba_step_block_matches_python_reference(block_len):
    ref = build_toy_system(monitored=True)
    _, tr_ref = ref.run(ref.start(), N, mode="step", record=ref.output_ports())
    s = build_toy_system(monitored=True, truth_cls=NumbaTruth, block_len=block_len)
    seg = next(sg for sg in s.execution()["segments"] if sg["members"] == ["truth"])
    assert seg["module_step_block"]
    _, tr = s.run(s.start(), N, mode="block", record=s.output_ports())
    for port in ("truth.x", "truth.v", "sensor.y", "counter.count"):
        assert np.array_equal(tr.ports[port], tr_ref.ports[port]), port
    assert tr.digest() == tr_ref.digest()
