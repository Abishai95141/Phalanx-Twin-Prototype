"""A6 for M05: kernel == NumPy reference bitwise (in process and with NUMBA_DISABLE_JIT in a subprocess),
step == step_block, snapshot round-trip at a tick that is not a DFCC frame boundary, validation mode, events
through the scheduler.

Scenario: M0.6/5 km scripted inputs (stick doublet, roll input, a q-lane hard-over at tick 300, a channel
fault
event) for 600-2,400 ticks; n = 1 deterministic scenario per check.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from test_fcs_fixtures import SignalSource
from test_fcs_voting import L, base_inputs

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.time import TRUTH_DT_S, truth_step_times_ns
from phalanx.fcs.kernel import fcs_kernel, kernel_reference
from phalanx.fcs.layout import I_LFAIL, I_NNEXT, SIG_Q
from phalanx.fcs.module import Fcs, FcsIC, frame_schedule
from phalanx.fcs.ports import ports

SRC = Path(__file__).resolve().parents[2] / "src"


def _script(k: int) -> dict:
    t = k * TRUTH_DT_S
    d = {}
    for c in "abcd":
        d[L("stick_pitch", c)] = 0.3 if 0.5 < t < 1.5 else (-0.3 if 1.5 <= t < 2.5 else 0.0)
        d[L("stick_roll", c)] = 0.4 if 3.0 < t < 4.0 else 0.0
    if k >= 300:
        d[L("rsa_q", "b")] = 0.6
    return d


def _fcs(compiled=True):
    return Fcs.from_registry(
        "fcs", FcsIC(surf=np.zeros(13), alpha=0.05, mach=0.6, hp=5000.0, on_ground=False), compiled=compiled
    )


def _system(*, compiled=True, block_len=240, validate=False):
    ins, _, _ = ports(1)
    vals = {k: v[0] for k, v in base_inputs(1).items()}
    src = SignalSource("src", ins, vals, _script)
    fcs = _fcs(compiled)
    conns = [Connection(f"src.{p.name}", f"fcs.{p.name}") for p in ins]
    return System(
        [src, fcs],
        conns,
        rng=RngService(0x5EED, StreamRegistry()),
        identity=KeyPath.of(scenario="w12", tail="T1", sortie=1),
        block_len=block_len,
        validate=validate,
        purity_check=validate,
    )


def _rows(n):
    """Kernel inputs of the scripted scenario: (module, rows as Fcs._pack, frame flags, apply offsets)."""
    mod = _fcs()
    base = base_inputs(n)
    for k in range(n):
        for key, v in _script(k).items():
            base[key][k] = v
    st = mod.init(mod.params, None)
    fr, off, _ = frame_schedule(mod.cfg, int(st["i"][I_NNEXT]), truth_step_times_ns(np.arange(n)))
    return mod, mod._pack(base, n), fr, off


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("block_len", [1, 7, 240])
def test_step_and_block_execution_bitwise(block_len):
    ref = _system()
    _, t_ref = ref.run(ref.start(), 1200, mode="step", record=ref.output_ports())
    s = _system(block_len=block_len)
    _, t = s.run(s.start(), 1200, mode="block", record=s.output_ports())
    assert t.digest() == t_ref.digest()


@pytest.mark.integration
def test_compiled_kernel_equals_python_reference_in_process():
    mod, u, fr, off = _rows(600)
    c = mod.cfg
    st = mod.init(mod.params, None)
    args = (c.p, c.tab, u, fr, off, TRUTH_DT_S, c.tf, c.n_sub_act, c.crit_mask)
    f1, i1, o1 = fcs_kernel(st["f"], st["i"], *args)
    f2, i2, o2 = kernel_reference(st["f"], st["i"], *args)
    assert np.array_equal(o1, o2) and np.array_equal(f1, f2) and np.array_equal(i1, i2)
    assert i1[I_LFAIL + SIG_Q] != 0  # the hard-over lane was voted out, so the logic was exercised


_SUB = r"""
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import numpy as np
from test_fcs_module import _rows
from phalanx.core.time import TRUTH_DT_S
from phalanx.fcs.kernel import fcs_kernel
mod, u, fr, off = _rows(600)
c = mod.cfg
st = mod.init(mod.params, None)
f, i, o = fcs_kernel(st["f"], st["i"], c.p, c.tab, u, fr, off, TRUTH_DT_S, c.tf, c.n_sub_act, c.crit_mask)
np.save(sys.argv[3], np.concatenate([o.ravel(), f, i.astype(np.float64)]))
"""


@pytest.mark.integration
def test_compiled_kernel_equals_numba_disabled_reference(tmp_path):
    """The fully uncompiled reference (NUMBA_DISABLE_JIT=1: every helper in Python/NumPy) reproduces the
    compiled kernel bit for bit."""
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
    mod, u, fr, off = _rows(600)
    c = mod.cfg
    st = mod.init(mod.params, None)
    f, i, o = fcs_kernel(st["f"], st["i"], c.p, c.tab, u, fr, off, TRUTH_DT_S, c.tf, c.n_sub_act, c.crit_mask)
    mine = np.concatenate([o.ravel(), f, i.astype(np.float64)])
    assert np.array_equal(np.load(out), mine)


@pytest.mark.integration
@pytest.mark.fork
def test_snapshot_restore_mid_frame_continues_bitwise():
    """Snapshot at k = 1201 (not a multiple of the 3-tick DFCC frame, with a pending delayed command) and
    restore:
    the continuation equals the uninterrupted run."""
    s_ref = _system()
    w_ref, _ = s_ref.run(s_ref.start(), 2400)
    s1 = _system()
    w1, _ = s1.run(s1.start(), 1201)
    s2 = _system()
    w2, _ = s2.run(restore(s2, snapshot(s1, w1)), 1199)
    assert snapshot(s2, w2) == snapshot(s_ref, w_ref)


@pytest.mark.integration
def test_validation_mode_equals_production_and_events_dispatch():
    """Validation mode (read-only views, purity re-calls, unit/shape/NaN checks) gives the production result;
    a channel-fault event injected through the scheduler reaches on_event and changes the channel status."""
    ev = Event(round(1.0 * 1e9), "fcs.channel_fault", "fcs", {"channel": 3, "subsystem": 0, "active": True})
    traces = []
    for validate in (True, False):
        s = _system(validate=validate)
        w = s.inject(s.start(), [ev])
        _, t = s.run(w, 600, record=s.output_ports())
        traces.append(t)
    assert traces[0].digest() == traces[1].digest()
    st = traces[1].ports["fcs.channel_status"]
    assert st[0, 3] == 0 and st[-1, 3] != 0
