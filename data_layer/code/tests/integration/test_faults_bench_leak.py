"""The W2.5 ground-run bench and the paired pipeline invariance on real modules (slow; the full campaign is
``analysis/faults_b7b8/code/leak_campaign.py``).

One identity, three runs of 10 s (PLA 18 -> 60 deg at 3 s): healthy twice (the bench is deterministic: bitwise
identical recordings), and with HPC fouling set in M10 at t = 0 (FM.ENG.FOULING). The fault reaches the
engine channels through M10 -> health.engine -> M07 -> M12 (their acquisition inputs change) and nothing
else differs: the paired invariance finds no problem. Negative control: one recorded sample of an unaffected
channel moved by one LSB (a changed noise path) is found.

Sample: n = 1 pair (deterministic; the statistical audit is the campaign's)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.validation.guards import RecordedRun, paired_invariance

pytestmark = [pytest.mark.integration, pytest.mark.slow]
CODE = Path(__file__).resolve().parents[2] / "analysis" / "faults_b7b8" / "code"


def _bench():
    if "w25_bench" not in sys.modules:
        sys.path.insert(0, str(CODE))
        spec = importlib.util.spec_from_file_location("w25_bench", CODE / "bench.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["w25_bench"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["w25_bench"]


def _rec(r) -> RecordedRun:
    return RecordedRun(
        run_id="x",
        value=r.value,
        rate_hz=r.rate_hz,
        n_frames=r.n_steps,
        validity=r.validity,
        flags=r.flags,
        t_sample=r.t_sample,
        input_digest=r.input_digest,
    )


def test_bench_is_deterministic_and_a_physical_fault_leaves_no_pipeline_trace():
    B = _bench()
    gr = B.GroundRun(duration_s=10.0, pla=((0.0, 18.0), (3.0, 60.0)))
    ident = B.bench_identity("W25T", "KH2011", "S1")
    h1, h2 = (_rec(B.run_bench(gr, ident)) for _ in range(2))
    assert paired_invariance(h1, h2) == []
    assert all(np.array_equal(h1.value[c], h2.value[c]) for c in h1.channels)
    fault = [Event(0, "health.fault", "health", {"state": "eng:foul_hpc", "delta": 0.02, "op": "set"})]
    f = _rec(B.run_bench(gr, ident, fault))
    affected = {c for c in h1.channels if h1.input_digest[c] != f.input_digest[c]}
    assert {"ENG.N1.A", "ENG.T5.HARNESS_A", "ENG.WFM", "ENG.PS3.A"} <= affected
    assert paired_invariance(h1, f) == []
    target = next(c for c in f.channels if c not in affected and np.asarray(f.value[c]).size > 2)
    v = dict(f.value)
    a = np.array(v[target], copy=True)
    a[a.size // 2] += 1e-3
    v[target] = a
    nc = RecordedRun(**{**f.__dict__, "value": v})
    assert any(target in p for p in paired_invariance(h1, nc))
