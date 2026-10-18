"""M13 -> M15/M16/M17 integration: one crystal per LRU across acquisition and bus (A-W1.6-21, W1.7).

W1.6 (M13, merged first) owns the acquisition clock domains of the LRUs it acquires on and requires M15 to use
them. ``phalanx.bus.clocks.acquisition_oscillators`` converts them to bus oscillators. These tests run **real
M13 output** (``AcquisitionRecorder`` on 3 s of steady M12-shaped frames, all 132 sensor channels plus two
computed channels; n = 3 s is the smallest window giving every stream down to 1 Hz at least three samples)
through the full path and check:

- every M13 CIR instant lies on the M15 oscillator of its LRU (``check_cir_on_oscillator``), and the keyed
  draws M15 uses stand-alone do **not** (negative control: wiring the wrong crystal is detected);
- every M13 channel the synthetic ICD carries decodes, and the decoded value equals the transmitted CIR value
  on the bus word's lattice (A4 on M13 output rather than the test fixture).
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pytest
from test_bus_cir_fixture import ROOT, registry

from phalanx.acquisition.config import acquisition_clock, acquisition_domain_lru, build_acquisition_config
from phalanx.acquisition.core import STREAMS as ACQ_STREAMS
from phalanx.acquisition.record import AcquisitionRecorder
from phalanx.bus.clocks import SortieIdentity, acquisition_oscillators, lru_oscillator
from phalanx.bus.encoder import BusConfig, check_cir_on_oscillator
from phalanx.bus.icd import BusIcd
from phalanx.core.module import ContractError
from phalanx.core.rng import RngService
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.ground.rid import record_ids
from phalanx.recorder.full_path import run_full_path
from phalanx.sensors.config import build_sensor_config

pytestmark = pytest.mark.integration

C = load_contract("v0")
D = load_dictionary()
EPOCH = 1_790_000_000 * 10**9
IDENT = SortieIdentity(scenario="W17M13", tail_no="KH2001", sortie_id="KH2001-20260921-1000")
SECONDS = 3


def _rng() -> RngService:
    return RngService(ROOT, registry(*ACQ_STREAMS))


@pytest.fixture(scope="module")
def m13_cir():
    sens = build_sensor_config(D)
    computed = ("ENG.T5", "ENG.N2.V")
    acq = build_acquisition_config(D, sens.channels + computed, sensor_channels=sens.channels)
    rec = AcquisitionRecorder(acq, _rng().scope(IDENT.key()))
    L = 240 * SECONDS
    lo = np.array([D.eu_to_si(c, D.channel(c)["range"]["min"]) for c in sens.channels])
    hi = np.array([D.eu_to_si(c, D.channel(c)["range"]["max"]) for c in sens.channels])
    t = np.arange(L)[:, None] / 240.0
    S = lo + (hi - lo) * (0.5 + 0.1 * np.sin(2 * t + np.arange(lo.size)))
    X = S + 0.001 * (hi - lo)
    t5 = np.full(L, 900.0)
    n2v = D.eu_to_si("ENG.N2.V", 95.0 + np.sin(t[:, 0]))
    _st, recs = rec.process(
        rec.init_state(), 0, S, X, np.full(L, 5), {"ENG.T5": (t5, t5), "ENG.N2.V": (n2v, n2v)}
    )
    return rec.to_cir(C, IDENT.tail_no, IDENT.sortie_id, recs, epoch_ns=EPOCH)


@pytest.fixture(scope="module")
def oscs():
    return acquisition_oscillators(D, EPOCH)


def _streams(cir):
    """(source_lru, t_sample, stream key, acquisition rate or None for the LRU frame) per CIR row."""
    tab = cir.table
    lru = np.array(tab.column("source_lru").to_pylist(), dtype=object)
    t = tab.column("t_sample").to_numpy()
    cols = (tab.column(c).to_pylist() for c in ("param_id", "source_lru", "lane"))
    key = np.array([f"{p}|{s}|{ln}" for p, s, ln in zip(*cols, strict=True)], dtype=object)
    groups = D.content["rate_groups"]
    rate = {}
    for ch in D.channels():
        loc = D.contract_location(ch["channel_id"])
        g = groups[ch["rates"]["acquisition"]]
        rate[f"{loc['param_id']}|{loc['source_lru']}|{loc['lane']}"] = (
            None if g["kind"] == "lru_frame" else g.get("rate_hz")
        )
    return lru, t, key, rate


def test_adapter_reproduces_the_m13_clock_domains(oscs):
    """Frame ticks of the adapted oscillator = epoch + M13 acquisition instants, bitwise (n = 2,000 ticks).
    W2.2 phase B added the avionics and digital LRU clock sets (INGPS, AHRS, RADALT, SMS, CWS, OAC, RADAR,
    ECMS)."""
    assert set(oscs) == {"ADC", "BHEEM_EU", "DFCC", "ECFM_C", "FADEC", "FTI_DAS"} | {
        "INGPS",
        "AHRS",
        "RADALT",
        "SMS",
        "CWS",
        "OAC",
        "RADAR",
        "ECMS",
    }
    for lru, osc in oscs.items():
        f = D.lru(lru)["frame_hz"]
        m13 = acquisition_clock(lru, f)
        ours = osc.tick_domain().sample_times_ns(0, 2000)
        assert np.array_equal(ours, EPOCH + m13.sample_times_ns(0, 2000)), lru


def test_every_m13_instant_is_on_the_m15_crystal(m13_cir, oscs):
    """Each stream on the crystal of its dictionary acquisition domain (the rate group's domain LRU, else the
    owning LRU; W1.6 follow-up: ENG.WFAB is FADEC-produced but FTI-acquired, so it is on FTI_DAS) at its
    dictionary acquisition rate (frame or rate group)."""
    _lru, t, key, rate = _streams(m13_cir)
    owner = {}
    for ch in D.channels():
        loc = D.contract_location(ch["channel_id"])
        try:
            owner[f"{loc['param_id']}|{loc['source_lru']}|{loc['lane']}"] = acquisition_domain_lru(
                D, ch["channel_id"]
            )
        except ContractError:  # rate groups with no LRU clock domain (e.g. HF) are not M13 streams
            pass
    checked = 0
    for k in sorted(set(key.tolist())):
        sel = key == k
        lr = owner[k]
        assert lr in oscs, f"M13 acquired {k} on {lr}, which has no M13 clock set"
        assert check_cir_on_oscillator(t[sel], oscs[lr], rate_hz=rate[k]), k
        checked += 1
    assert checked >= 134


def test_keyed_draws_are_not_the_m13_crystal(m13_cir):
    """Negative control: the stand-alone keyed FADEC oscillator does not carry M13's FADEC instants."""
    lru, t, key, _rate = _streams(m13_cir)
    cfg = BusConfig.from_params()
    keyed = lru_oscillator("FADEC", D.lru("FADEC")["frame_hz"], IDENT, _rng(), sigma_ppm=cfg.sigma_ppm)
    framed = (lru == "FADEC") & np.array([k.startswith("ENG.N2|") for k in key.tolist()])
    assert framed.sum() >= 100
    assert not check_cir_on_oscillator(t[framed], keyed)


def test_m13_output_round_trips_through_the_full_path(m13_cir, oscs):
    res = run_full_path(
        m13_cir,
        ident=IDENT,
        rng=_rng(),
        t_start=EPOCH + 10**9,
        t_end=EPOCH + SECONDS * 10**9,
        oscillators=oscs,
        fti_fitted=True,
    )
    full = res.decoded[-1].samples
    assert full.schema.equals(C.schemas["param.samples"], check_metadata=True)
    tr = res.recording.truth
    ids = record_ids(
        C,
        "param.samples",
        {
            "provenance": "full_path",
            "tail_no": IDENT.tail_no,
            "sortie_id": IDENT.sortie_id,
            "channel_id": tr.column("channel_id"),
            "param_id": tr.column("param_id"),
            "seq": tr.column("seq"),
            "msg_index": tr.column("msg_index"),
        },
        tr.num_rows,
    )
    pos = {bytes(r): i for i, r in enumerate(ids.to_pylist())}
    order = np.array([pos[bytes(r)] for r in full.column("record_id").to_pylist()], dtype=np.int64)
    t = tr.take(pa.array(order))
    rows = t.column("cir_row").to_numpy()
    has = rows >= 0
    # every M13 stream the ICD carries reaches the ground with CIR data behind it (lane channels A-D are
    # DFCC/FADEC-internal; the voted .V words come from the controllers, so only two of those are in this CIR)
    icd = BusIcd.from_dictionary(D)
    carried = {(it.param_id, it.source_lru, it.lane) for it in icd.items}
    cols = ("param_id", "source_lru", "lane")
    m13 = set(zip(*(m13_cir.table.column(c).to_pylist() for c in cols), strict=True))
    got = {
        k
        for k, h in zip(
            zip(*(full.column(c).to_pylist() for c in cols), strict=True), has.tolist(), strict=True
        )
        if h
    }
    expect = m13 & carried
    assert len(expect) >= 30 and expect <= got, sorted(expect - got)
    assert {k[1] for k in expect} >= {"FADEC", "FTI_DAS"}
    # decoded value = transmitted CIR value on the bus word's lattice
    items = {(it.param_id, it.source_lru, it.lane): it for it in icd.items}
    ident = zip(*(full.column(c).to_pylist() for c in ("param_id", "source_lru", "lane")), strict=True)
    keys = [k for k, h in zip(ident, has.tolist(), strict=True) if h]
    v_dec = full.column("value_eu").to_numpy()[has]
    v_cir = m13_cir.table.column("value").to_numpy()[rows[has]]
    lsb = np.array([abs(items[k].cal[1]) if items[k].encoding in ("bnr", "ubnr") else 0.0 for k in keys])
    assert has.sum() > 1_000
    err = np.abs(v_dec - v_cir)
    assert np.all(err <= 0.5 * lsb + 1e-9 * np.maximum(np.abs(v_cir), 1.0))
    assert np.mean(err == 0) > 0.99  # M13 values sit on the recorder lattice = the bus word lattice
