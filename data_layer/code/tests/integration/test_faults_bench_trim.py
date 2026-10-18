"""The W2.5 ground-run bench start condition (analysis/faults_b7b8/DEVIATIONS.md D3; assumption A-W2.5-3).

The pre-registered bench started every run from M08's healthy no-load trim and stepped the run's own health
(M10 build deltas plus a fault set at t = 0) and M09's idle loads (about 21 kW PTO, 0.5 kg/s bleed) in at
t = 0. D3 starts each run trimmed at its own initial engine inputs (``bench.initial_condition``).

1. With the D3 start an HPT-deteriorated engine (FM.ENG.HPT_DETERIORATION, ``eng:abn_hpt`` 0.03) holds ground
   idle on the N2 governor.
2. The finding D3 worked around (strict xfail until W2.3a): from the pre-registered start the same engine
   rolled back below idle on the accel Wf/PS3 schedule (``acc_k`` x the no-load reference line) and then the
   minimum-fuel clamp, where a real engine with this deterioration recovers from an idle load step. Since
   W2.3a (A-W2.3-1: M08's lines derived from the installed engine, the reference continued on its steady
   line below idle) it recovers; the test is now a regression guard
   (``tests/integration/test_fadec_accel_margin.py`` covers the whole B7 set and the integrated-aircraft
   loads).

Sample: n = 1 identity (deterministic; B7-ENG ran 5 pairs x 7 faults both ways, results/b7_engine*.json)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]
CODE = Path(__file__).resolve().parents[2] / "analysis" / "faults_b7b8" / "code"
N2_REF = 16810.0 * 2.0 * np.pi / 60.0
ACCEL, WFMIN = 6, 9


def _bench():
    if "w25_bench" not in sys.modules:
        sys.path.insert(0, str(CODE))
        spec = importlib.util.spec_from_file_location("w25_bench", CODE / "bench.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["w25_bench"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["w25_bench"]


def _run(trim_at_start: bool):
    from phalanx.core.events import Event

    B = _bench()
    gr = B.GroundRun(duration_s=20.0, pla=((0.0, 18.0),))
    ident = B.bench_identity("B7ENG", "E0", "P0")
    fault = {"state": "eng:abn_hpt", "delta": 0.03, "op": "set"}
    ev = [Event(0, "health.fault", "health", fault, source="t")]
    r = B.run_bench(gr, ident, ev, trim_at_start=trim_at_start, record_channels=False)
    n2 = r.ports["eng.n2"].reshape(r.n_steps, -1)[:, 0] / N2_REF
    lim = r.ports["fadec.active_limiter"].reshape(r.n_steps, -1)[:, 0].astype(np.int64) & 15
    return n2, lim


def test_d3_start_holds_a_deteriorated_engine_at_ground_idle():
    n2, lim = _run(True)
    assert n2.min() >= 0.98 * n2[0], (n2[0], n2.min())
    assert not np.isin(lim[240:], (ACCEL, WFMIN)).any()  # after the first second: the governor holds it


def test_engine_recovers_from_an_idle_load_and_deterioration_step():
    n2, lim = _run(False)
    assert n2[-240:].mean() >= 0.95 * n2[0], (n2[0], n2[-240:].mean())
    assert not np.isin(lim[240:], (WFMIN,)).any()  # no roll-back onto the minimum-fuel clamp
