"""AD-54 (coordinator decision, W2.2): the consumer-visible ``param.samples`` channel set is identical on the
fast path and the full path for the same sortie. The fast path emits only channels with a full-path transport
(recorded buses; the FTI PCM stream when FTI is fitted); LRU-internal lanes stay in the CIR.

The sortie: the W1.7 full-path fixture CIR (every recorded-bus channel) plus internal lanes the controllers
read (the FADEC N1/N2 lanes, transport ``internal``; the ADC-DFCC RS-422 static-pressure lanes), 2 s, run with
and without the FTI system fitted. n = 1 sortie per configuration (the channel set is deterministic). The
negative control shows the comparison catches the pre-AD-54 behaviour (no channel-set rule).
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc
import pytest
from test_bus_cir_fixture import EPOCH, IDENT, make_cir, rng_service

from phalanx.bus.icd import BusIcd
from phalanx.dictionary import load_dictionary
from phalanx.ground.cir import CirBatch
from phalanx.ground.fast_path import FTI_TRANSPORT, RECORDED_TRANSPORTS, FastPathConfig, cir_to_param_samples
from phalanx.recorder.full_path import run_full_path
from phalanx.recorder.writer import unpopulated_pcm_words

pytestmark = pytest.mark.integration
D = load_dictionary()
T0 = EPOCH + 30 * 10**9
T1 = T0 + 2 * 10**9
#: LRU-internal lanes added to the sortie (TEST FIXTURE: rows of a recorded channel relabelled to the lane's
#: contract identity; the values stay inside each lane's range check because only the stream identity matters)
INTERNAL = ("ENG.N1.A", "ENG.N2.B", "AD.PS.A")


def _channel_key(cid: str) -> tuple[str, str, str | None]:
    loc = D.contract_location(cid)
    return (loc["param_id"], loc["source_lru"], loc["lane"])


def sortie_cir() -> CirBatch:
    base = make_cir(None, T0 - 10**9, T1)
    tab = base.table
    donor = tab.filter(pc.equal(tab.column("param_id"), tab.column("param_id")[0]))
    parts = [tab]
    for cid in INTERNAL:
        p, lru, lane = _channel_key(cid)
        n = donor.num_rows
        extra = donor.set_column(donor.schema.get_field_index("param_id"), "param_id", pa.array([p] * n))
        extra = extra.set_column(
            extra.schema.get_field_index("source_lru"), "source_lru", pa.array([lru] * n)
        )
        lane_arr = pa.array([lane] * n, pa.string())
        extra = extra.set_column(extra.schema.get_field_index("lane"), "lane", lane_arr)
        parts.append(extra.cast(tab.schema))
    return CirBatch(base.tail_no, base.sortie_id, pa.concat_tables(parts))


def channel_set(tab: pa.Table) -> set[tuple[str, str, str | None]]:
    cols = [tab.column(k).to_pylist() for k in ("param_id", "source_lru", "lane")]
    return set(zip(*cols, strict=True))


def set_problems(fast: pa.Table, full: pa.Table) -> list[str]:
    a, b = channel_set(fast), channel_set(full)
    return [f"fast only: {sorted(a - b, key=str)[:8]}"] * bool(a - b) + [
        f"full only: {sorted(b - a, key=str)[:8]}"
    ] * bool(b - a)


@pytest.fixture(scope="module")
def cir():
    return sortie_cir()


#: the flight-test-panel words: not simulated (scope S-FTI), so no producer populates them
FTI_UNSOURCED = ("FCS.FTP.FLAGS", "FCS.FTP.TEST_POINT")


@pytest.mark.parametrize("fti_fitted", [False, True])
def test_fast_and_full_path_channel_sets_are_equal(cir, fti_fitted):
    """Equal channel sets with and without the FTI system fitted. FTI words no producer populates are spare
    frame slots: the recording's setup record does not describe them, so the full path emits no zero-fill
    records for them (W2.2 phase B; the phase-A tracked deviation is closed)."""
    full = run_full_path(cir, ident=IDENT, rng=rng_service(), t_start=T0, t_end=T1, fti_fitted=fti_fitted)
    full_samples = full.samples()
    cfg = FastPathConfig.from_dictionary(D, engine_serial=IDENT.engine_serial, fti_fitted=fti_fitted)
    fast = cir_to_param_samples(cir, cfg, t_ingest=max(d.t_ingest for d in full.deliveries))
    assert set_problems(fast, full_samples) == []
    assert not set(FTI_UNSOURCED) & set(full_samples.column("param_id").to_pylist())
    if fti_fitted:  # the slots stay in the fixed PCM frame; only their description (D and C groups) is absent
        setup = full.recording.setup_text
        assert not [c for c in FTI_UNSOURCED if f":{c};" in setup]
        assert unpopulated_pcm_words(full.traffic) == FTI_UNSOURCED
        frame = {it.channel_id for it in full.traffic.pcm.frame_def.items}
        assert set(FTI_UNSOURCED) <= frame
        populated = frame - set(FTI_UNSOURCED)
        assert populated and all(f":{c};" in setup for c in populated)
    internal = {_channel_key(c) for c in INTERNAL}
    assert internal <= channel_set(cir.table)  # they were in the sortie's CIR ...
    assert not internal & channel_set(fast)  # ... and stay out of param.samples on both paths
    fti = {_channel_key(c["channel_id"]) for c in D.channels() if c["transport"].get("type") == FTI_TRANSPORT}
    assert bool(fti & channel_set(fast)) is fti_fitted


def test_negative_control_without_the_channel_set_rule(cir):
    """Pre-AD-54 behaviour (a config without the rule) emits the internal lanes: the comparison catches it."""
    full = run_full_path(cir, ident=IDENT, rng=rng_service(), t_start=T0, t_end=T1)
    cfg = FastPathConfig.from_dictionary(D, engine_serial=IDENT.engine_serial)
    legacy = FastPathConfig(cfg.dict_version, cfg.dict_hash, cfg.units, cfg.engine_serial, cfg.channels, None)
    fast = cir_to_param_samples(cir, legacy, t_ingest=max(d.t_ingest for d in full.deliveries))
    problems = set_problems(fast, full.samples())
    assert problems and problems[0].startswith("fast only")


def test_negative_control_strict_round_trip_rejects_a_recording_with_spare_fti_slots(cir):
    """Without the spare-slot allowance (M01's strict round trip) the same recording is a layout mismatch,
    so the decoder's allowance is what admits it, and only for FTI PCM words."""
    from phalanx.dictionary.tmats import round_trip
    from phalanx.ground.decoder.setup import parse_tmats

    full = run_full_path(cir, ident=IDENT, rng=rng_service(), t_start=T0, t_end=T1, fti_fitted=True)
    flat = {k: v[0] for k, v in parse_tmats(full.recording.setup_text).items()}
    assert not round_trip(D.compiled.content, flat).ok
    assert round_trip(D.compiled.content, flat, allow_unpopulated_pcm=True).ok
    # a 1553 measurand the setup does not describe is never admitted (its D/C entries renamed away)
    broken = {k: ("NOT.A.CHANNEL" if v == "ENG.N1.V" else v) for k, v in flat.items()}
    assert not round_trip(D.compiled.content, broken, allow_unpopulated_pcm=True).ok


def test_recorded_transports_are_the_bus_encoder_items():
    """The fast path's transport rule equals the M15 bus ICD (the full path's carrier): no drift."""
    icd = BusIcd.from_dictionary(D)
    on_bus = {D.channel(it.channel_id)["transport"]["type"] for it in icd.items}
    assert on_bus == RECORDED_TRANSPORTS | {FTI_TRANSPORT}
    by_rule = {
        c["channel_id"]
        for c in D.channels()
        if c["transport"].get("type") in RECORDED_TRANSPORTS | {FTI_TRANSPORT}
    }
    assert by_rule == {it.channel_id for it in icd.items}
