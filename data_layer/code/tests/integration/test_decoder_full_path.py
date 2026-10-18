"""The full data path end to end: CIR -> bus (M15) -> Ch10 (M16) -> download -> decoder (M17).

W1.7 acceptance: A4 (CIR -> Ch10 -> decode equals CIR within quantisation), A5 (identical schema on the fast
and full paths), A6 (re-download produces no duplicates through ParquetStore / ReplayStreamer), A8
(deterministic bytes), plus the t_sample proposal (A-W1.7-14), the DUPLICATE_POLL inference (A-W1.7-15) and
the time-base behaviour through a holdover (A-W1.7-17).

Sample (stated before running): one fixture sortie of 6 s covering every recorded-bus channel (~30,000
decoded records: every message type at least 6 times, AV50 messages 300 times), plus a 40 s sortie with
forced time-source outages for the holdover test. TEST FIXTURE CIR, not physics.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pytest
from test_bus_cir_fixture import EPOCH, IDENT, make_cir, rng_service

from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.ground.decoder import DecoderConfig, decode_recording
from phalanx.ground.fast_path import FastPathConfig, cir_to_param_samples
from phalanx.recorder.download import DownloadConfig
from phalanx.recorder.full_path import full_path_truth_labels, run_full_path
from phalanx.recorder.setup import EventDef
from phalanx.recorder.writer import RecorderConfig, RecordingEvent, unpopulated_pcm_words
from phalanx.streaming import ParquetStore, ReplayStreamer, canonical_order, parquet_bytes

C = load_contract("v0")
D = load_dictionary()
QF = C.quality_flags
T0 = EPOCH + 30 * 10**9
T1 = T0 + 6 * 10**9
FORCED = DownloadConfig.from_params(p_partial=1.0, p_duplicate=1.0)
EVENTS = (RecordingEvent("BIT-ENG-042", T0 + 2_500_000_000, "synthetic BIT event"),)
EVENT_DEFS = (EventDef("BIT-ENG-042", "FADEC BIT (synthetic test code)", "O"),)


def _run(cir, **kw):
    return run_full_path(
        cir,
        ident=IDENT,
        rng=rng_service(),
        t_start=T0,
        t_end=T1,
        fti_fitted=True,
        download=FORCED,
        events=EVENTS,
        event_defs=EVENT_DEFS,
        **kw,
    )


@pytest.fixture(scope="module")
def cir():
    return make_cir(None, T0 - 10**9, T1, invalid_every=11)


@pytest.fixture(scope="module")
def run(cir):
    return _run(cir)


@pytest.fixture(scope="module")
def joined(run, cir):
    """Decoded records of the complete delivery joined with M15/M16 truth (record_id) and the CIR rows."""
    res = run.decoded[1]
    s = res.samples
    tr = run.recording.truth
    ids = C.topics["param.samples"]
    from phalanx.ground.rid import record_ids

    truth_ids = record_ids(
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
    assert ids is not None
    pos = {bytes(r): i for i, r in enumerate(truth_ids.to_pylist())}
    order = np.array([pos[bytes(r)] for r in s.column("record_id").to_pylist()], dtype=np.int64)
    t = tr.take(pa.array(order))
    return s, t


def test_a4_every_record_matches_the_transmission_truth(run, joined):
    """Every transmitted item the setup record describes decodes, nothing else. The FTI words no producer
    populates are transmitted as spare frame slots (no data, ``cir_row`` -1) and not described (W2.2)."""
    s, t = joined
    tr = run.recording.truth
    spare = unpopulated_pcm_words(run.traffic)
    assert spare == ("FCS.FTP.FLAGS", "FCS.FTP.TEST_POINT")
    in_spare = pc.is_in(tr.column("param_id"), pa.array(spare))
    assert set(pc.filter(tr.column("cir_row"), in_spare).to_pylist()) == {-1}
    described = tr.filter(pc.invert(in_spare))
    assert s.num_rows == described.num_rows > 25_000
    assert s.column("param_id").equals(t.column("param_id"))  # the joined truth row is the same item
    assert run.decoded[1].report.bad_checksum == 0 and run.decoded[1].report.unknown_messages == 0


def test_a4_values_equal_cir_within_quantisation(cir, joined):
    """Exact equality on the recorder lattice. RT status words carry the RT address in bits 15-11 whatever the
    CIR value says (MIL-STD-1553B; M15 writes the ICD address), so the expectation applies it."""
    s, t = joined
    rows = t.column("cir_row").to_numpy()
    has = rows >= 0
    v_dec = s.column("value_eu").to_numpy()[has]
    v_cir = cir.table.column("value").to_numpy()[rows[has]].copy()
    pid = np.array(s.column("param_id").to_pylist(), dtype=object)[has]
    rtsw = np.array(s.column("rt_sa_word").to_pylist(), dtype=object)[has]
    status = np.char.startswith(pid.astype(str), "AV.RT.STATUS.")
    rt_addr = np.array([int(w[2:4]) if w else 0 for w in rtsw], dtype=np.int64)
    v_cir[status] = ((v_cir[status].astype(np.int64) & 0x7FF) | (rt_addr[status] << 11)).astype(np.float64)
    assert status.sum() > 1000
    assert np.array_equal(v_dec, v_cir)  # fixture values sit on the recorder lattice: exact
    assert has.mean() > 0.95


def test_a4_validity_mapping(cir, joined):
    """1553 validity bit -> dictionary code (BUS_INVALID, AD-45, dictionary 0.1.2); ARINC SSM keeps NCD/FT/FW;
    no data -> invalid."""
    s, t = joined
    rows = t.column("cir_row").to_numpy()
    val = np.array(s.column("validity").to_pylist(), dtype=object)
    bus = np.array(s.column("bus").to_pylist(), dtype=object)
    rt = np.array([x is not None for x in s.column("rt_sa_word").to_pylist()])
    cir_val = np.array(cir.table.column("validity").to_pylist(), dtype=object)
    has = rows >= 0
    src = np.where(has, cir_val[np.maximum(rows, 0)], "MISSING")
    on1553 = rt & has
    assert np.array_equal(val[on1553] == "NORMAL", src[on1553] == "NORMAL")
    assert set(val[on1553 & (src != "NORMAL")].tolist()) == {"BUS_INVALID"}
    assert (on1553 & (src != "NORMAL")).sum() > 100
    no_data_1553 = rt & ~has & ~np.char.startswith(np.array(s.column("param_id").to_pylist(), str), "AV.RT.")
    assert set(val[no_data_1553].tolist()) <= {"BUS_INVALID"}
    fti = bus == "FTI-PCM"
    assert fti.any() and set(val[fti].tolist()) == {"NORMAL"}


def test_a4_times_within_clock_model(run, cir, joined):
    s, t = joined
    t_rec = s.column("t_record").to_numpy()
    assert np.array_equal(t_rec, t.column("rtc").to_numpy() * 100)
    t_tag = t.column("t_tag").to_numpy()
    t_bus = s.column("t_bus").to_numpy()
    after_first_second = t_tag >= T0 + 10**9 + 10**8  # a crystal rate is measured from the 2nd time packet
    err = t_bus[after_first_second] - t_tag[after_first_second]
    assert np.abs(err).max() <= 1_000  # monitor latency known; crystal rate removed: sub-microsecond
    t_utc = s.column("t_utc").to_numpy()
    sigma = (
        float(abs(run.recording.clock.offset_ppm)) * 1e3
    )  # ns of sawtooth per second at the crystal offset
    assert np.abs(t_utc - t_tag).max() <= sigma + 2_000
    assert np.all(s.column("t_sample").to_numpy() <= t_bus)
    assert np.all(s.column("t_ingest").to_numpy() >= t_bus)


def test_t_sample_estimate_is_unbiased_and_bounded(cir, joined):
    """A-W1.7-14: t_sample = t_bus - nominal latency. Against the true acquisition instant (CIR t_sample,
    truth)
    the error of periodic same-LRU 1553 items is bounded by half an update period plus the processing-latency
    mismatch (none here: declared = simulated), and centred."""
    s, t = joined
    rows = t.column("cir_row").to_numpy()
    rt = np.array([x is not None for x in s.column("rt_sa_word").to_pylist()])
    pid = np.array(s.column("param_id").to_pylist(), dtype=object)
    sel = (rows >= 0) & rt & np.isin(pid, ["FCS.ELEVON.ROB.POS", "FCS.VOTED.NZ", "ENG.N2", "HYD.SYS1.P"])
    err = s.column("t_sample").to_numpy()[sel] - cir.table.column("t_sample").to_numpy()[rows[sel]]
    assert sel.sum() > 300
    assert np.abs(err).max() <= 12_500_000 + 1_000  # <= T_update/2 (DFCC FCS40: 25 ms)
    assert abs(float(np.mean(err))) <= 5_000_000
    naive = s.column("t_bus").to_numpy()[sel] - cir.table.column("t_sample").to_numpy()[rows[sel]]
    assert np.mean(np.abs(err)) < np.mean(np.abs(naive))  # better than t_sample = t_bus


def test_latency_model_none_sets_t_sample_to_t_bus(run):
    d = run.deliveries[1]
    res = decode_recording(
        d.data,
        dictionary=D,
        tail_no=d.tail_no,
        sortie_id=d.sortie_id,
        t_ingest=d.t_ingest,
        config=DecoderConfig.from_params(latency_model="none"),
    )
    assert np.array_equal(res.samples.column("t_sample").to_numpy(), res.samples.column("t_bus").to_numpy())


def test_duplicate_poll_inference_against_m15_truth(joined):
    """A-W1.7-15 precision/recall against M15 truth on the DFCC 40 Hz -> AV50 messages (20 % true dups)."""
    s, t = joined
    rt = np.array([x or "" for x in s.column("rt_sa_word").to_pylist()], dtype=object)
    dfcc = np.char.startswith(rt.astype(str), "RT01/SA01") | np.char.startswith(rt.astype(str), "RT01/SA02")
    pred = (s.column("quality_flags").to_numpy() & QF.mask("DUPLICATE_POLL")) != 0
    true = t.column("dup").to_numpy()
    p, tt = pred[dfcc], true[dfcc]
    assert tt.mean() == pytest.approx(0.2, abs=0.03)
    precision = (p & tt).sum() / max(p.sum(), 1)
    recall = (p & tt).sum() / max(tt.sum(), 1)
    assert precision >= 0.95 and recall >= 0.9, (precision, recall)
    assert not pred[~dfcc & np.char.startswith(rt.astype(str), "RT01/SA03")].any()  # 80 Hz -> 25: never


def test_a5_identical_schema_on_fast_and_full_paths(run, cir):
    full = run.decoded[1].samples
    fast = cir_to_param_samples(
        cir,
        FastPathConfig.from_dictionary(D, engine_serial=IDENT.engine_serial),
        t_ingest=run.deliveries[1].t_ingest,
    )
    schema = C.schemas["param.samples"]
    assert full.schema.equals(schema, check_metadata=True) and fast.schema.equals(schema, check_metadata=True)
    C.validate("param.samples", full)
    C.validate("param.samples", fast)
    assert set(full.column("provenance").to_pylist()) == {"full_path"}
    assert set(fast.column("provenance").to_pylist()) == {"direct"}
    assert not set(full.column("record_id").to_pylist()) & set(fast.column("record_id").to_pylist())

    def ident(tab):
        cols = [
            tab.column(k).to_pylist() for k in ("param_id", "source_lru", "lane", "units", "engine_serial")
        ]
        return {tuple(r[:3]): tuple(r[3:]) for r in zip(*cols, strict=True)}

    a, b = ident(full), ident(fast)
    shared = set(a) & set(b)
    assert len(shared) > 250 and all(a[k] == b[k] for k in shared)
    # every full-path value of a stream is one of that stream's fast-path values (it is a transmitted sample)
    for key in sorted(shared)[:40]:
        fv = set(pc.filter(full.column("value_eu"), pc.equal(full.column("param_id"), key[0])).to_pylist())
        sv = set(pc.filter(fast.column("value_eu"), pc.equal(fast.column("param_id"), key[0])).to_pylist())
        assert fv <= sv | {0.0}, key


def test_a6_redownload_no_duplicates(run, tmp_path):
    """Partial transfer + retry + repeat download: the store and the replay keep each record once."""
    assert [d.attempt for d in run.deliveries] == [0, 1, 2] and not run.deliveries[0].complete
    tabs = [r.samples for r in run.decoded]
    complete = tabs[1]
    store = ParquetStore.at(tmp_path / "store", C)
    for tab in tabs:
        store.write("param.samples", tab)
    got = store.read("param.samples", tail_no=IDENT.tail_no, sortie_id=IDENT.sortie_id)
    assert got.num_rows == complete.num_rows
    assert len(set(got.column("record_id").to_pylist())) == got.num_rows
    first_ids = set(tabs[0].column("record_id").to_pylist())
    assert 0 < len(first_ids) < complete.num_rows  # the interrupted transfer delivered a prefix
    flags = got.column("quality_flags").to_numpy()
    dupdl = (flags & QF.mask("DUPLICATE_DOWNLOAD")) != 0
    in_first = np.array([r in first_ids for r in got.column("record_id").to_pylist()])
    assert np.array_equal(dupdl, ~in_first)  # first delivered by a repeat download <=> flagged
    seen = []
    for item in ReplayStreamer(store, ["param.samples"]):
        if hasattr(item, "table"):
            seen += item.table.column("record_id").to_pylist()
    assert len(seen) == len(set(seen)) == complete.num_rows


def test_partial_download_decodes_like_the_complete_one(run):
    """Causal decoding: every record of the prefix delivery equals the complete delivery's record with the
    same record_id (except t_ingest and DUPLICATE_DOWNLOAD), so idempotent ingest never sees a conflict."""
    a, b = run.decoded[0].samples, run.decoded[1].samples
    pos = {bytes(r): i for i, r in enumerate(b.column("record_id").to_pylist())}
    idx = np.array([pos[bytes(r)] for r in a.column("record_id").to_pylist()])
    bb = b.take(pa.array(idx))
    for name in a.schema.names:
        if name in ("t_ingest", "quality_flags"):
            continue
        assert a.column(name).equals(bb.column(name)), name
    mask = np.uint32(~QF.mask("DUPLICATE_DOWNLOAD") & 0xFFFFFFFF)
    assert np.array_equal(
        a.column("quality_flags").to_numpy() & mask, bb.column("quality_flags").to_numpy() & mask
    )
    assert run.decoded[0].report.truncated


def test_full_path_truth_labels_link_to_decoded_records(run, cir):
    lab = full_path_truth_labels(run.recording, cir)
    C.validate("labels.truth", lab)
    assert lab.num_rows > 25_000
    rel = set(bytes(x) for x in lab.column("related_record_id").to_pylist())
    dec = set(bytes(x) for x in run.decoded[1].samples.column("record_id").to_pylist())
    assert rel <= dec
    assert C.topics["labels.truth"].restricted


def test_recording_events_round_trip(run):
    ev = run.decoded[1].events
    names = ev.column("event_id").to_pylist()
    assert names[0] == "REC_START" and "BIT-ENG-042" in names
    k = names.index("BIT-ENG-042")
    assert abs(ev.column("t_best")[k].as_py() - EVENTS[0].t_ns) <= 1_000
    truth = run.recording.events
    assert ev.column("number").to_pylist() == truth.column("number").to_pylist()
    assert ev.column("count").to_pylist() == truth.column("count").to_pylist()


def test_a8_deterministic_bytes_in_process(run, cir):
    again = _run(cir)
    assert again.recording.data == run.recording.data
    for x, y in zip(again.decoded, run.decoded, strict=True):
        assert x.samples.equals(y.samples)
    pa_bytes = parquet_bytes(canonical_order(C, "param.samples", run.decoded[1].samples))
    assert parquet_bytes(canonical_order(C, "param.samples", again.decoded[1].samples)) == pa_bytes


CHILD = r"""
import hashlib, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from test_decoder_full_path import _run, T0, T1
from test_bus_cir_fixture import make_cir
from phalanx.dictionary.contract import load_contract
from phalanx.streaming import canonical_order, parquet_bytes
r = _run(make_cir(None, T0 - 10**9, T1, invalid_every=11))
c = load_contract("v0")
print(hashlib.blake2b(r.recording.data).hexdigest())
print(hashlib.blake2b(parquet_bytes(canonical_order(c, "param.samples", r.decoded[1].samples))).hexdigest())
"""


def test_a8_deterministic_bytes_in_a_fresh_process(run):
    here = Path(__file__).resolve().parent
    src = here.parents[1] / "src"
    out = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, str(src), str(here)],
        capture_output=True,
        text=True,
        check=True,
        timeout=600,
    )
    c10, pq = out.stdout.split()
    assert c10 == hashlib.blake2b(run.recording.data).hexdigest()
    assert (
        pq
        == hashlib.blake2b(
            parquet_bytes(canonical_order(C, "param.samples", run.decoded[1].samples))
        ).hexdigest()
    )


def test_forks_share_data_path_timing_and_record_ids(run, cir):
    """CRN (I8): a fork of the sortie with different physics (here: every CIR value scaled) has the same bus
    timing, the same recorder clock and time packets, the same download times and the same record ids; only
    the values differ."""
    tab = cir.table
    other = tab.set_column(
        tab.schema.get_field_index("value"), "value", pa.array(np.floor(tab.column("value").to_numpy() * 0.5))
    )
    from phalanx.ground.cir import CirBatch

    fork = _run(CirBatch(cir.tail_no, cir.sortie_id, other))
    assert fork.recording.time_packets == run.recording.time_packets
    assert [d.t_ingest for d in fork.deliveries] == [d.t_ingest for d in run.deliveries]
    a, b = fork.decoded[1].samples, run.decoded[1].samples
    assert a.column("record_id").equals(b.column("record_id"))
    assert a.column("t_record").equals(b.column("t_record")) and a.column("t_sample").equals(
        b.column("t_sample")
    )
    assert not a.column("value_eu").equals(b.column("value_eu"))


def test_holdover_reconstruction():
    """Forced outages (rate 360/h, ~4 s): records in a holdover carry TIME_SOURCE_INTERNAL and
    DECODER_INTERPOLATED, and their t_bus stays within microseconds of the true tag."""
    t0, t1 = EPOCH + 100 * 10**9, EPOCH + 140 * 10**9
    chans = ["ENG.N2.V", "AD.AOA", "NAV.RADALT"]
    cir = make_cir(chans, t0 - 10**9, t1)
    rec_cfg = RecorderConfig.from_params(lock_loss_rate_per_h=360.0, outage_median_s=4.0, outage_sigma_ln=0.3)
    res = run_full_path(
        cir,
        ident=IDENT,
        rng=rng_service(),
        t_start=t0,
        t_end=t1,
        recorder=rec_cfg,
        download=DownloadConfig.from_params(p_partial=0.0, p_duplicate=0.0),
    )
    assert res.recording.outages, "the forced rate must produce at least one outage in 40 s"
    s = res.decoded[0].samples
    tr = res.recording.truth
    from phalanx.ground.rid import record_ids

    tid = record_ids(
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
    pos = {bytes(r): i for i, r in enumerate(tid.to_pylist())}
    t_tag = tr.column("t_tag").to_numpy()[[pos[bytes(r)] for r in s.column("record_id").to_pylist()]]
    fl = s.column("quality_flags").to_numpy()
    internal = (fl & QF.mask("TIME_SOURCE_INTERNAL")) != 0
    interp = (fl & QF.mask("DECODER_INTERPOLATED")) != 0
    assert internal.any() and np.array_equal(internal, interp)
    in_out = np.zeros(t_tag.size, dtype=bool)
    for o in res.recording.outages:
        in_out |= (t_tag >= o.start + 10**9) & (t_tag < o.end)  # well inside: governed by an internal packet
    assert internal[in_out].all()
    err = s.column("t_bus").to_numpy() - t_tag
    assert np.abs(err[internal]).max() <= 2_000  # carried on the crystal rate: microseconds
    utc_err = s.column("t_utc").to_numpy() - t_tag
    assert np.abs(utc_err[internal]).max() > np.abs(err[internal]).max()  # raw aircraft time drifted more
