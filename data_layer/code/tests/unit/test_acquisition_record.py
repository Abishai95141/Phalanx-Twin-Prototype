"""M13 recording entry point -> CIR (acceptance A5; AD-38; A-W0.4-21; A-W1.6-32)."""

from __future__ import annotations

import numpy as np
import pyarrow.compute as pc
import pytest

from phalanx.acquisition.config import build_acquisition_config
from phalanx.acquisition.core import STREAMS
from phalanx.acquisition.record import AcquisitionRecorder
from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.ground.cir import parse_key_path, validate_cir
from phalanx.ground.fast_path import FastPathConfig, cir_to_param_samples, cir_to_truth_labels
from phalanx.sensors.config import build_sensor_config

pytestmark = pytest.mark.unit
IDENT = KeyPath.of(scenario="W16", tail="KH2001", sortie="SRT0001")
EPOCH = 1_790_000_000_000_000_000


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


@pytest.fixture(scope="module")
def recorded(d):
    """All 132 Tejas sensor channels plus two computed channels, 2 s of steady truth with sinusoids."""
    sens = build_sensor_config(d)
    computed = ("ENG.T5", "ENG.N2.V")
    acq = build_acquisition_config(d, sens.channels + computed, sensor_channels=sens.channels)
    rec = AcquisitionRecorder(acq, RngService(0x16, StreamRegistry(list(STREAMS))).scope(IDENT))
    L = 480
    lo = np.array([d.eu_to_si(c, d.channel(c)["range"]["min"]) for c in sens.channels])
    hi = np.array([d.eu_to_si(c, d.channel(c)["range"]["max"]) for c in sens.channels])
    t = np.arange(L)[:, None] / 240.0
    S = lo + (hi - lo) * (0.5 + 0.1 * np.sin(2 * t + np.arange(lo.size)))
    X = S + 0.001 * (hi - lo)  # truth differs from the reading (sensor error), so leaks would show
    t5 = np.full(L, 900.0)
    n2v = d.eu_to_si("ENG.N2.V", 95.0 + np.sin(t[:, 0]))
    ext = {"ENG.T5": (t5, t5), "ENG.N2.V": (n2v, n2v)}
    _st, recs = rec.process(rec.init_state(), 0, S, X, np.full(L, 5), ext)
    cir = rec.to_cir(load_contract("v0"), "KH2001", "SRT0001", recs, epoch_ns=EPOCH)
    return sens, acq, rec, recs, cir


def test_cir_validates_against_the_schema(recorded):
    _sens, acq, _rec, _recs, cir = recorded
    validate_cir(load_contract("v0"), cir.table)
    assert cir.table.num_rows > 10_000
    assert set(pc.unique(cir.table.column("param_id")).to_pylist()) == {
        loc["param_id"] for loc in acq.location
    }


def test_values_are_dictionary_eu_on_the_lattice(d, recorded):
    """CIR values are in the dictionary EU (AD-38) on the channel's lattice; truth only in truth_value."""
    _sens, acq, _rec, recs, _cir = recorded
    for cid, r in recs.items():
        ch = d.channel(cid)
        step = ch["recorder_lsb"] if ch["recorder_lsb"] is not None else ch["native_step"]
        step = 1.0 if step is None else step  # a discrete word (W2.2 word path): integer codes
        v = r.cat("value", np.float64)
        np.testing.assert_allclose(v / step, np.rint(v / step), atol=1e-6)
        assert np.all((v >= ch["range"]["min"] - 1e-9) & (v <= ch["range"]["max"] + 1e-9))
    units = d.units_map()
    for loc in acq.location:
        assert units[loc["param_id"]] == loc["units"]


def test_truth_goes_only_to_the_restricted_labels(d, recorded):
    """The fast path drops truth from param.samples and routes it to restricted labels.truth (I5)."""
    _sens, _acq, _rec, _recs, cir = recorded
    cfg = FastPathConfig.from_dictionary(d, engine_serial="E404-IN20-0001")
    samples = cir_to_param_samples(cir, cfg, t_ingest=EPOCH + 10**13)
    assert "truth_value" not in samples.schema.names and "t_true" not in samples.schema.names
    labels = cir_to_truth_labels(cir, cfg)
    # AD-54 (W2.2): only channels with a full-path transport reach param.samples; their samples are labelled
    keys = zip(*(cir.table.column(k).to_pylist() for k in ("param_id", "source_lru", "lane")), strict=True)
    visible = sum(1 for k in keys if k in cfg.visible)
    assert samples.num_rows == visible and labels.num_rows == visible
    assert "A" not in set(samples.column("lane").to_pylist())  # the FADEC internal lanes stay in the CIR


def test_sample_index_time_and_key_path(recorded):
    """sample_index is the absolute acquisition index, t_sample = epoch + LRU instant (t_true = t_sample),
    and rng_key_path is the channel's own noise stream (AD-37)."""
    _sens, acq, rec, recs, cir = recorded
    r = recs["ENG.N2.A"]
    idx, t = r.cat("sample_index", np.int64), r.cat("t_sample", np.int64)
    assert np.all(np.diff(idx) == 1) and np.all(np.diff(t) > 0)
    dom = acq.domains[int(acq.domain_of[acq.index("ENG.N2.A")])]
    np.testing.assert_array_equal(t, dom.clock.sample_times_ns(int(idx[0]), idx.size))
    tab = cir.table
    kp = parse_key_path(rec.noise_key_path("ENG.N2.A"))
    assert kp.get("sensor") == "ENG.N2.A" and kp.get("component") == "noise" and kp.get("sortie") == "SRT0001"
    assert np.all(tab.column("t_true").to_numpy() == tab.column("t_sample").to_numpy())
    assert tab.column("t_sample").to_numpy().min() >= EPOCH


def test_computed_channel_recording(d, recorded):
    """LRU-computed channels (FADEC T5 average, voted N2) are recorded from the supplied value: lattice,
    no sensor noise, NORMAL validity (A-W1.6-32)."""
    _sens, acq, _rec, recs, _cir = recorded
    assert acq.sensor_index[acq.index("ENG.T5")] == -1
    v = recs["ENG.T5"].cat("value", np.float64)
    np.testing.assert_array_equal(v, np.full(v.size, round(626.85 / 0.5) * 0.5))
    n2v = recs["ENG.N2.V"].cat("value", np.float64)
    tr = recs["ENG.N2.V"].cat("truth", np.float64)
    assert np.max(np.abs(n2v - tr)) <= 0.03125 / 2 + 1e-9  # quantisation only


def test_missing_computed_value_is_an_error(d):
    sens = build_sensor_config(d, channels=("ENG.N2.A",))
    acq = build_acquisition_config(d, ("ENG.N2.A", "ENG.N2.V"), sensor_channels=sens.channels)
    rec = AcquisitionRecorder(acq, RngService(1, StreamRegistry(list(STREAMS))).scope(IDENT))
    S = np.full((24, 1), 1700.0)
    with pytest.raises(ContractError, match="externally supplied"):
        rec.process(rec.init_state(), 0, S, S, np.full(24, 5))
