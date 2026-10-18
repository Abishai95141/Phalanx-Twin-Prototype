"""A7: G0 trivial-cue audit hook on M13's pipeline-only metadata, healthy vs synthetic-fault runs (I6, AD-40).

Healthy and faulty versions of the same sortie (same identity, same keyed noise) run through the identical
generation path (TEST FIXTURE truth -> M12 -> recording M13 -> CIR); faults enter only as M11-style events
that perturb M12 state. The binding pipeline-only metadata of every recorded channel (sample count,
count/rate, dtype, NaN presence, float32 representability, record frames and seconds;
``validation.guards.g0``) must sit at chance: ``g0_audit`` (one-sided, AD-40) PASSES. Negative control: a
deliberately leaky pipeline that drops the faulted channel's samples while the fault is active FAILS.

n = 12 paired sorties x 10 s (2,400 frames) per group: enough for the negative control to give AUC 1.0 with a
CI lower bound far above 0.5 (500 bootstrap resamples); the healthy/faulty metadata are identical by
construction, so n does not limit the PASS side.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.acquisition import kernel as K
from phalanx.acquisition.config import build_acquisition_config
from phalanx.acquisition.record import AcquisitionRecorder, frames_from_trace
from phalanx.core.events import Event
from phalanx.core.rng import KeyPath
from phalanx.core.time import truth_step_time_ns
from phalanx.dictionary import load_dictionary
from phalanx.sensors.config import build_sensor_config
from phalanx.sensors.module import SENSOR_FAULT_EVENT
from phalanx.validation.guards import g0_audit, metadata_features

pytestmark = pytest.mark.integration
N_PAIRS, N_FRAMES = 12, 2400
FAULTS = (
    {"channel": "ENG.N1.A", "mode": "stuck"},
    {"channel": "ENG.N2.B", "mode": "bias", "value": 2.0},
    {"channel": "ENG.T5.HARNESS_A", "mode": "probe_short", "probe": 1, "value": 650.0},
    {"channel": "ENG.PS3.A", "mode": "intermittent", "rate": 2.0, "duty": 0.3},
)


def load_fixture():
    name = "w16_acquisition_fixtures"
    if name not in sys.modules:
        p = Path(__file__).resolve().parents[1] / "integration" / "test_acquisition_fixtures.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


FX = load_fixture()


def _sortie(d, sens, acq, i, faulty):
    ident = KeyPath.of(scenario="W16G0", tail="KH2001", sortie=f"SRT{i:04d}")
    system, rng, mods = FX.build_chain(d, sens, controllers=(), identity=ident)
    w = system.start()
    if faulty:
        f = FAULTS[i % len(FAULTS)]
        w = system.inject(w, [Event(truth_step_time_ns(600), SENSOR_FAULT_EVENT, "sens", f)])
    _, tr = system.run(w, N_FRAMES, record=[*FX.sensor_ports(mods), "truth.phase"])
    S, X = frames_from_trace(sens, tr.ports, "sens")
    rec = AcquisitionRecorder(acq, rng.scope(ident))
    _, recs = rec.process(rec.init_state(), 0, S, X, tr.ports["truth.phase"])
    return recs


def _features(acq, recs, drop=None):
    chans, lsb = {}, {}
    for c, cid in enumerate(acq.channels):
        v = recs[cid].cat("value", np.float64)
        if drop is not None and cid == drop[0]:
            v = v[drop[1]]
        rate = float(acq.domains[int(acq.domain_of[c])].clock.f_nom_hz)
        chans[cid] = (v, rate)
        lsb[cid] = float(acq.P[c, K.AP_SF])
    return metadata_features(chans, N_FRAMES, N_FRAMES // 240, lsb=lsb)


@pytest.fixture(scope="module")
def runs():
    d = load_dictionary()
    sens = build_sensor_config(d)
    acq = build_acquisition_config(d, sens.channels, sensor_channels=sens.channels)
    healthy = [_sortie(d, sens, acq, i, False) for i in range(N_PAIRS)]
    faulty = [_sortie(d, sens, acq, i, True) for i in range(N_PAIRS)]
    return acq, healthy, faulty


def test_faults_change_values_but_not_pipeline_metadata(runs):
    acq, healthy, faulty = runs
    changed = sum(
        not np.array_equal(h[c].cat("value", np.float64), f[c].cat("value", np.float64))
        for h, f in zip(healthy, faulty, strict=True)
        for c in ("ENG.N1.A", "ENG.N2.B", "ENG.T5.HARNESS_A", "ENG.PS3.A")
    )
    assert changed >= N_PAIRS  # every faulty sortie differs in the faulted channel
    XA = np.vstack([_features(acq, h)[0] for h in healthy])
    XB = np.vstack([_features(acq, f)[0] for f in faulty])
    names = _features(acq, healthy[0])[1]
    res = g0_audit(XA, XB, names, paired=True, seed=16, n_boot=500)
    assert res.passed, res.classifiers


def test_g0_catches_a_leaky_pipeline(runs):
    """Negative control: dropping the faulted channel's samples during the fault (a pipeline cue) FAILS G0."""
    acq, healthy, faulty = runs
    names = _features(acq, healthy[0])[1]
    XA = np.vstack([_features(acq, h)[0] for h in healthy])
    rows = []
    for i, f in enumerate(faulty):
        cid = FAULTS[i % len(FAULTS)]["channel"]
        t = f[cid].cat("t_sample", np.int64)
        keep = t < truth_step_time_ns(600)
        rows.append(_features(acq, f, drop=(cid, keep))[0])
    res = g0_audit(XA, np.vstack(rows), names, paired=True, seed=16, n_boot=500)
    assert not res.passed
