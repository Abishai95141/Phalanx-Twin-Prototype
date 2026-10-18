"""TEST FIXTURE: deterministic CIR batches for the W1.7 data-path tests (M15/M16/M17).

TEST FIXTURE, not physics. Values are smooth deterministic signals on the dictionary recorder lattice, not
M12/M13
output. What the fixture does get right is the *timing contract* the data path relies on: every stream is
acquired on its acquiring LRU's oscillator from ``phalanx.bus.clocks.lru_oscillator`` (the same keyed draws as
M15), as M13 must do at integration (W2.2). Event-group channels (EVT) emit a sample only
when the value changes.

Imported by sibling test modules (``from test_bus_cir_fixture import ...``); the tests below check the fixture
itself (CIR validity, oscillator alignment), so a broken fixture fails loudly instead of hiding bugs.
"""

from __future__ import annotations

from collections.abc import Iterable
from fractions import Fraction

import numpy as np
import pytest

from phalanx.bus.clocks import STREAMS as BUS_STREAMS
from phalanx.bus.clocks import SortieIdentity, lru_oscillator
from phalanx.bus.encoder import BusConfig, check_cir_on_oscillator
from phalanx.bus.icd import BusIcd
from phalanx.core.rng import RngService, StreamRegistry
from phalanx.core.time import ClockDomain
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.ground.cir import CirBatch, StreamSamples, cir_from_streams

ROOT = 0x5EED_0F_A11_DA7A_9A7  # fixed 128-bit test root (a literal, not seed arithmetic)
EPOCH = 1_790_000_000 * 10**9  # sim-UTC epoch of the fixture sorties (2026-09-21)
IDENT = SortieIdentity(scenario="W17TEST", tail_no="KH2001", sortie_id="KH2001-20260921-0900")


def registry(*extra) -> StreamRegistry:
    from phalanx.recorder.writer import STREAMS as REC_STREAMS

    return StreamRegistry([*BUS_STREAMS, *REC_STREAMS, *extra])


def rng_service(root: int = ROOT) -> RngService:
    return RngService(root, registry())


def acquisition_domain(d, ch, osc) -> ClockDomain | None:
    """Acquisition clock of a channel on its LRU crystal (TEST FIXTURE rule; M13 owns the real one)."""
    groups = d.content["rate_groups"]
    g = ch["rates"]["acquisition"]
    kind = groups[g]["kind"]
    if kind == "lru_frame":
        return osc.tick_domain()
    if g == "HF":  # vibration features are produced at 1 Hz from the raw stream (rule R-RATE-HF)
        rate = Fraction(1)
    elif g == "EVT":
        return osc.tick_domain()
    elif kind == "periodic":
        rate = Fraction(groups[g]["rate_hz"]).limit_denominator(1000)
    else:
        return None
    k = osc.frame_hz / rate
    if k.denominator == 1:
        return osc.sub_domain(rate, 0)
    return ClockDomain(f"{osc.lru}.{rate}", rate, osc.offset_ppm, osc.phase_ns)


def _signal(item, t_s: np.ndarray, k: int) -> np.ndarray:
    """Smooth deterministic value on the item's lattice (TEST FIXTURE)."""
    if item.encoding in ("bnr", "ubnr"):
        lo = item.range_min if item.range_min is not None else 0.0
        hi = item.range_max if item.range_max is not None else lo + 100.0
        mid, amp = 0.5 * (lo + hi), 0.35 * (hi - lo)
        period = 3.0 + (k % 7)
        x = (
            mid
            + amp * np.sin(2 * np.pi * t_s / period + 0.37 * k)
            + 0.01 * amp * np.sin(2 * np.pi * t_s * 7.3)
        )
        c0, c1 = item.cal
        return c0 + c1 * np.rint((x - c0) / c1)
    if item.channel_id.startswith(("AV.RT.STATUS.", "AV.LRU.BIT.")):
        return np.zeros(t_s.size)  # healthy RT status and BIT words (tests set flags explicitly)
    if item.encoding == "bitfield":
        step = np.floor(t_s / (0.5 + 0.1 * (k % 5))).astype(np.int64)
        return ((step * 2654435761 + k) & item.field_mask).astype(np.float64)
    if item.encoding == "enum":
        return (np.floor(t_s / 2.0).astype(np.int64) % 4).astype(np.float64)
    if item.encoding == "code_word":
        step = np.floor(t_s / 3.0).astype(np.int64)
        return ((step % max(len(item.prefixes), 1)) * 1000 + (step % 997)).astype(np.float64)
    raise ValueError(item.encoding)


def make_cir(
    channels: Iterable[str] | None,
    t_start: int,
    t_end: int,
    *,
    ident: SortieIdentity = IDENT,
    rng: RngService | None = None,
    config: BusConfig | None = None,
    invalid_every: int = 0,
) -> CirBatch:
    """CIR for ``channels`` (dictionary channel ids on recorded buses; None = all) over ``[t_start, t_end)``.

    ``invalid_every`` > 0 marks every n-th sample of numeric streams NO_COMPUTED_DATA (validity tests).
    """
    d = load_dictionary()
    icd = BusIcd.from_dictionary(d)
    rng = rng or rng_service()
    cfg = config or BusConfig.from_params()
    items = {it.channel_id: it for it in icd.items}
    wanted = sorted(items) if channels is None else list(channels)
    lrus = d.content["lrus"]
    streams = []
    for k, cid in enumerate(wanted):
        ch = d.channel(cid)
        it = items[cid]
        lru = ch["acq_lru"]
        if lrus[lru].get("frame_hz") is None:
            continue
        osc = lru_oscillator(
            lru,
            lrus[lru]["frame_hz"],
            ident,
            rng,
            sigma_ppm=cfg.sigma_ppm,
            offset_override_ppm=cfg.offset_override_ppm,
            phase_override_ns=cfg.phase_override_ns,
        )
        dom = acquisition_domain(d, ch, osc)
        if dom is None:
            continue
        n0, n1 = dom.indices_in(t_start, t_end)
        t = dom.sample_times_ns(n0, n1 - n0)
        idx = np.arange(n0, n1, dtype=np.int64)
        v = _signal(it, (t - EPOCH) / 1e9, k)
        if ch["rates"]["acquisition"] == "EVT":
            keep = np.r_[True, v[1:] != v[:-1]]
            t, idx, v = t[keep], idx[keep], v[keep]
        validity = np.full(t.size, "NORMAL", dtype=object)
        if invalid_every and it.encoding in ("bnr", "ubnr"):
            validity[(idx % invalid_every) == 3] = "NO_COMPUTED_DATA"
        loc = d.contract_location(cid)
        streams.append(
            StreamSamples(
                param_id=loc["param_id"],
                source_lru=loc["source_lru"],
                lane=loc["lane"],
                sample_index=idx,
                t_sample=t,
                value=v,
                truth_value=v,
                validity=validity,
            )
        )
    return cir_from_streams(load_contract("v0"), ident.tail_no, ident.sortie_id, streams)


# ---- tests of the fixture itself ------------------------------------------------------------------------
def test_fixture_cir_validates_and_sits_on_lru_oscillators():
    """n = 2 s of 6 channels from 5 LRUs: enough ticks per stream to check the grid (>= 20 samples each)."""
    chans = ["ENG.N2.V", "AD.AOA", "HYD.SYS1.P", "NAV.INS.PITCH", "FCS.VOTED.NZ", "NAV.RADALT"]
    t0 = EPOCH + 10**9
    cir = make_cir(chans, t0, t0 + 2 * 10**9)
    cir.validate(load_contract("v0"))
    d = load_dictionary()
    cfg = BusConfig.from_params()
    rng = rng_service()
    tab = cir.table
    for cid in chans:
        ch = d.channel(cid)
        loc = d.contract_location(cid)
        sel = np.array(
            [
                p == loc["param_id"] and s == loc["source_lru"]
                for p, s in zip(
                    tab.column("param_id").to_pylist(), tab.column("source_lru").to_pylist(), strict=True
                )
            ]
        )
        t = tab.column("t_sample").to_numpy()[sel]
        assert t.size >= 20, cid
        lru = ch["acq_lru"]
        osc = lru_oscillator(lru, d.lru(lru)["frame_hz"], IDENT, rng, sigma_ppm=cfg.sigma_ppm)
        if d.content["rate_groups"][ch["rates"]["acquisition"]]["kind"] == "lru_frame":
            assert check_cir_on_oscillator(t, osc), cid


def test_fixture_values_are_on_the_recorder_lattice():
    cir = make_cir(["ENG.N2.V", "AD.AOA"], EPOCH, EPOCH + 10**9)
    d = load_dictionary()
    tab = cir.table
    for pid, cid in (("ENG.N2", "ENG.N2.V"), ("AD.AOA", "AD.AOA")):
        lsb = d.channel(cid)["recorder_lsb"]
        v = np.array(
            [
                x
                for p, x in zip(
                    tab.column("param_id").to_pylist(), tab.column("value").to_pylist(), strict=True
                )
                if p == pid
            ]
        )
        assert v.size > 10
        assert np.allclose(v / lsb, np.rint(v / lsb), atol=1e-9)


@pytest.mark.parametrize("n", [3])
def test_fixture_is_deterministic(n):
    a = make_cir(["ENG.N2.V"], EPOCH, EPOCH + n * 10**8)
    b = make_cir(["ENG.N2.V"], EPOCH, EPOCH + n * 10**8)
    assert a.table.equals(b.table)
