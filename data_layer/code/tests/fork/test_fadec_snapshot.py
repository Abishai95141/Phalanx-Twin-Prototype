"""A6 (fork): M08 snapshot -> restore -> continue is bitwise identical to an uninterrupted run, with the
snapshot taken while validator persistence and heal counters are mid-count.

Chain: TEST FIXTURE scenario/plant/lanes + `Fadec` in a core `System` (`test_fadec_coupling._system`). An N2
lane-A disagreement (1 s, then heal) is injected; snapshots are taken (a) while the cross-channel persistence
counter is counting and (b) while the heal counter is counting. Each continues 600 steps (2.5 s) in a fresh
System from the snapshot bytes and is compared with the uninterrupted run (trace digest).
Sample size: 2 snapshot points x 600 continuation steps, deterministic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

import fadec_fixture as fx
from phalanx.core.snapshot import restore, snapshot
from phalanx.fadec.layout import I_XC_CNT, I_XC_FAIL, I_XC_GOOD

pytestmark = pytest.mark.fork
S_N2 = 1
K1 = 600
FAULT_AT = 480


def _coupling():
    name = "w13b_fadec_coupling"
    if name not in sys.modules:
        p = Path(__file__).resolve().parents[1] / "integration" / "test_fadec_coupling.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


RECORD = ["plant.x", "fadec.wf_cmd", "fadec.validation_state", "fadec.fault_code", "fadec.n2_v"]


def _run_to(syst, w, pred, limit=400):
    for _ in range(limit):
        if pred(w.states["fadec"]["i"][0]):
            return w
        w, _ = syst.run(w, 1, mode="step")
    raise AssertionError("snapshot condition never reached")


@pytest.mark.parametrize(
    "phase,pred",
    [
        ("persistence", lambda i: i[I_XC_CNT + S_N2] > 0 and i[I_XC_FAIL + S_N2] == 0),
        ("heal", lambda i: i[I_XC_FAIL + S_N2] == 1 and i[I_XC_GOOD + S_N2] > 0),
    ],
)
def test_snapshot_mid_count_restores_and_continues_bitwise(phase, pred):
    C = _coupling()
    n = 4 * 240 + K1 + 400
    sc = C._scenario(n, fault_at=FAULT_AT)
    x0 = fx.steady_state(60.0)
    syst = C._system(sc, x0)
    w, _ = syst.run(syst.start(), FAULT_AT - 4, mode="block")
    w = _run_to(syst, w, pred)
    i_snap = w.states["fadec"]["i"].copy()
    assert pred(i_snap[0])  # counters genuinely mid-count at the snapshot
    blob = snapshot(syst, w)
    _, ref = syst.run(w, K1, mode="block", record=RECORD)
    syst2 = C._system(sc, x0)
    w2 = restore(syst2, blob)
    assert np.array_equal(w2.states["fadec"]["i"], i_snap) and w2.k == w.k
    _, cont = syst2.run(w2, K1, mode="block", record=RECORD)
    assert cont.digest() == ref.digest()
    # the continuation does go through the counted transition (fail declared / healed)
    vs = ref.ports["fadec.validation_state"][:, 0, S_N2]
    assert len(set(vs.tolist())) > 1, phase
