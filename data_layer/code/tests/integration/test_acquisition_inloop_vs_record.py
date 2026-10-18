"""A6 + A8 end to end: the value a controller saw is the value recorded, bitwise, through the core scheduler.

Chain (TEST FIXTURE truth -> M12 -> M13 in-loop lanes for the FADEC and the DFCC) runs in a core ``System``;
M12's outputs are traced and fed to the recording entry point, which builds CIR. For every lane sample:
``Dictionary.eu_to_si(CIR value) == lane value`` and the instants match. Also: block mode == step mode,
compiled == NumPy reference, validation mode (read-only state, purity, units, no NaN) passes.
n = 1,200 truth frames (5 s): 300 FADEC samples and 400 DFCC samples per lane, 110 lanes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.acquisition.config import build_acquisition_config
from phalanx.acquisition.record import AcquisitionRecorder, frames_from_trace
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.sensors.config import build_sensor_config

pytestmark = pytest.mark.integration
N = 1200


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


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


@pytest.fixture(scope="module")
def sens(d):
    return build_sensor_config(d)


def _record_ports(mods):
    ports = [*FX.sensor_ports(mods), "truth.phase"]
    for m in mods.values():
        if m.id.startswith("acq_"):
            ports += FX.lane_record_ports(m)
    return ports


@pytest.fixture(scope="module")
def block_run(d, sens):
    system, rng, mods = FX.build_chain(d, sens)
    w = system.start()
    _w2, tr = system.run(w, N, mode="block", record=_record_ports(mods))
    return system, rng, mods, tr


def test_controller_saw_equals_recorded(d, sens, block_run):
    """A6 (W1_interfaces §3): same kernel, same keyed draw index -> eu_to_si(CIR value) == lane value."""
    _system, rng, mods, tr = block_run
    S, X = frames_from_trace(sens, tr.ports, "sens")
    lanes = [c for m in mods.values() if m.id.startswith("acq_") for c in m.acq.channels]
    acq = build_acquisition_config(d, tuple(lanes), sensor_channels=sens.channels)
    rec = AcquisitionRecorder(acq, rng.scope(FX.IDENTITY))
    _st, recs = rec.process(rec.init_state(), 0, S, X, tr.ports["truth.phase"])
    cir = rec.to_cir(load_contract("v0"), "KH2001", "SRT0001", recs, epoch_ns=0)
    assert cir.table.num_rows > 40_000
    n_checked = 0
    for m in mods.values():
        if not m.id.startswith("acq_"):
            continue
        for cid in m.acq.channels:
            seen = FX.lane_samples(tr.ports, m.id, cid)
            r = recs[cid]
            idx = r.cat("sample_index", np.int64)
            si = d.eu_to_si(cid, r.cat("value", np.float64))
            ts = r.cat("t_sample", np.int64)
            assert set(seen) == set(idx.tolist()), cid
            for i_, v_, t_ in zip(idx.tolist(), si.tolist(), ts.tolist(), strict=True):
                assert seen[i_][0] == v_, (cid, i_)  # bitwise (float ==)
                assert seen[i_][1] == t_
                n_checked += 1
    assert n_checked > 40_000


def test_step_mode_equals_block_mode(d, sens, block_run):
    """A8 through the scheduler: per-step execution of M12 and M13 equals block execution bitwise."""
    _system, _rng, _mods, tr = block_run
    system2, _, mods2 = FX.build_chain(d, sens)
    _, tr2 = system2.run(system2.start(), N, mode="step", record=_record_ports(mods2))
    assert tr2.digest() == tr.digest()


def test_reference_kernels_equal_compiled_through_the_scheduler(d, sens, block_run):
    """A8: the whole chain with the NumPy reference kernels gives the identical trace (n = 240 frames)."""
    _system, _rng, _mods, tr = block_run
    sysr, _, modsr = FX.build_chain(d, sens, compiled=False)
    _, trr = sysr.run(sysr.start(), 240, mode="block", record=_record_ports(modsr))
    for p, v in trr.ports.items():
        np.testing.assert_array_equal(v, tr.ports[p][:240], err_msg=p)


def test_validation_mode_runs_clean(d, sens):
    """Validation mode: read-only state and inputs, purity (every call twice), port units/dtypes/shapes and no
    NaN/inf at any port boundary (n = 120 frames)."""
    system, _, mods = FX.build_chain(d, sens, validate=True)
    _w, tr = system.run(system.start(), 120, mode="block", record=FX.sensor_ports(mods))
    for v in tr.ports.values():
        assert np.all(np.isfinite(v))
