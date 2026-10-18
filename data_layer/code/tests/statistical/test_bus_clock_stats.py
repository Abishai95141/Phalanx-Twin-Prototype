"""W1.7 acceptance A2: duplicate, skip and skew statistics of the bus follow the clock model, and the
slip-window
period is 1/(f * dDelta) (architecture §8, AD-06).

The predictions are analytic consequences of the oscillator model, computed independently of the encoder:

- a producer updating at f_u polled at f_p (f_u < f_p) repeats a buffer in a fraction 1 - f_u/f_p of polls;
- a producer faster than the poll loses a fraction 1 - f_p/f_u of its buffer writes (skips);
- a 2:1 producer/poll pair skips exactly every other write, except once per slip-window period
  1/(f_u * dDelta), when the relative phase crosses an update instant (dDelta = relative crystal offset);
- the age of a value at the poll lies in [L_proc, L_proc + T_update) (skew = latency + poll wait, report §13).

Sample sizes (stated before running): dup/skip/skew use 20 s (1,000 AV50 polls; the 40/50 Hz pattern repeats
every 0.1 s, so 200 full cycles); the slip test uses 420 s at dDelta = 100 ppm (expected period 100 s, so 4
slips: enough to measure three intervals, each predicted exactly up to the ns flooring of the clocks).
TEST FIXTURE CIR (built inline on the LRU oscillators), not physics.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.bus.clocks import STREAMS, SortieIdentity, lru_oscillator
from phalanx.bus.encoder import BusConfig, encode_bus
from phalanx.bus.icd import BusIcd
from phalanx.core.rng import RngService, StreamRegistry
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.ground.cir import StreamSamples, cir_from_streams

pytestmark = pytest.mark.statistical

D = load_dictionary()
ICD = BusIcd.from_dictionary(D)
ID = SortieIdentity("STATS", "KH2002", "KH2002-S1")
ROOT = 0x2468_ACE0_1357_9BDF_0F0F_F0F0_1234_5678
EPOCH = 1_790_100_000 * 10**9


def _cir(channels, t0, t1, cfg):
    rng = RngService(ROOT, StreamRegistry(STREAMS))
    streams = []
    for cid in channels:
        ch = D.channel(cid)
        lru = ch["acq_lru"]
        o = lru_oscillator(
            lru,
            D.lru(lru)["frame_hz"],
            ID,
            rng,
            sigma_ppm=cfg.sigma_ppm,
            offset_override_ppm=cfg.offset_override_ppm,
            phase_override_ns=cfg.phase_override_ns,
        )
        dom = o.tick_domain()
        n0, n1 = dom.indices_in(t0, t1)
        t = dom.sample_times_ns(n0, n1 - n0)
        lsb = ch["recorder_lsb"]
        v = lsb * np.rint(np.sin(np.arange(n0, n1) * 0.013) * 500)  # TEST FIXTURE: a value change every tick
        loc = D.contract_location(cid)
        streams.append(
            StreamSamples(loc["param_id"], loc["source_lru"], loc["lane"], np.arange(n0, n1), t, v)
        )
    return cir_from_streams(load_contract("v0"), ID.tail_no, ID.sortie_id, streams)


def _encode(channels, seconds, cfg):
    t0 = EPOCH + 10**9
    cir = _cir(channels, t0 - 10**9, t0 + seconds * 10**9, cfg)
    tr = encode_bus(
        cir, ICD, cfg, ID, RngService(ROOT, StreamRegistry(STREAMS)), t0=t0, t1=t0 + seconds * 10**9
    )
    return cir, tr


def _message(tr, msg_id):
    for bt in tr.buses:
        for k, m in enumerate(bt.schedule.messages):
            if m.msg_id == msg_id:
                return bt, np.flatnonzero(bt.msg == k)
    raise KeyError(msg_id)


def test_duplicate_fraction_matches_update_to_poll_ratio():
    """DFCC SA1: buffer at 40 Hz (FCS40), polled at 50 Hz -> 1 - 40/50 = 20 % duplicate polls."""
    cfg = BusConfig.from_params()
    _, tr = _encode(["FCS.VOTED.NZ"], 20, cfg)
    bt, txn = _message(tr, "AV-MUX-2/RT01/T/SA01")
    upd = bt.update[txn]
    dup = np.mean(upd[1:] == upd[:-1])
    assert txn.size == 1000
    assert abs(dup - 0.2) <= 2 / txn.size  # deterministic pattern: at most one partial cycle at each end


def test_skip_fraction_matches_poll_to_update_ratio():
    """DFCC SA3 relays ADC data: buffer at the DFCC 80 Hz frame, polled at 25 Hz -> 1 - 25/80 of the writes
    are never read."""
    cfg = BusConfig.from_params()
    _, tr = _encode(["AD.AOA"], 20, cfg)
    bt, txn = _message(tr, "AV-MUX-2/RT01/T/SA03")
    upd = bt.update[txn]
    writes = int(upd[-1] - upd[0])
    read = np.unique(upd).size - 1
    skipped = 1 - read / writes
    assert abs(skipped - (1 - 25 / 80)) < 0.01
    assert np.all(np.diff(upd) >= 3) and np.all(np.diff(upd) <= 4)  # 80/25 = 3.2 writes per poll


def test_skew_is_latency_plus_poll_wait():
    """Age of the value at the poll lies in [L_proc, L_proc + 25 ms); for the 40/50 Hz pair the poll phase
    visits five slots 5 ms apart, so the mean age is L_proc + 10 ms + (phase mod 5 ms), in [L+10, L+15) ms."""
    cfg = BusConfig.from_params()
    sa1 = next(m for m in ICD.messages if m.msg_id == "AV-MUX-2/RT01/T/SA01")
    cir, tr = _encode([next(it.channel_id for it in sa1.items if it.encoding == "bnr")], 20, cfg)
    bt, txn = _message(tr, "AV-MUX-2/RT01/T/SA01")
    sel = np.isin(bt.item_txn, txn) & (bt.item_row >= 0)
    age = bt.t_cmd[bt.item_txn[sel]] - cir.table.column("t_sample").to_numpy()[bt.item_row[sel]]
    lp = cfg.processing_latency_ns
    assert age.min() >= lp and age.max() < lp + 25_000_000 * (1 + 1e-4)
    assert lp + 10e6 - 1e3 <= age.mean() < lp + 15e6 + 1e3


def test_slip_window_period_is_one_over_f_delta():
    """INGPS updates at 100 Hz, polled at 50 Hz; INGPS +60 ppm, OAC (BC) -40 ppm: relative offset
    dDelta = (1+60e-6)/(1-40e-6) - 1 ~ 100.004 ppm, so a 3-write poll interval (one extra skip) recurs every
    1/(100 Hz * dDelta) ~ 99.996 s."""
    cfg = BusConfig.from_params(offset_override_ppm={"INGPS": 60, "OAC": -40})
    _, tr = _encode(["NAV.INS.PITCH"], 420, cfg)
    bt, txn = _message(tr, "AV-MUX-1/RT10/T/SA01")
    step = np.diff(bt.update[txn])
    assert set(np.unique(step).tolist()) == {2, 3}
    slips = bt.t_cmd[txn][1:][step == 3]
    assert slips.size >= 4
    d_rel = (1 + 60e-6) / (1 - 40e-6) - 1
    expected = 1.0 / (100.0 * d_rel)
    intervals = np.diff(slips) / 1e9
    assert np.allclose(intervals, expected, rtol=2e-4, atol=0.04)  # one AV50 poll (20 ms) of quantisation


def test_no_slips_without_relative_offset():
    """Negative control: equal crystals (INGPS and OAC both +25 ppm) never slip in 420 s."""
    cfg = BusConfig.from_params(offset_override_ppm={"INGPS": 25, "OAC": 25})
    _, tr = _encode(["NAV.INS.PITCH"], 420, cfg)
    bt, txn = _message(tr, "AV-MUX-1/RT10/T/SA01")
    assert set(np.unique(np.diff(bt.update[txn])).tolist()) == {2}
