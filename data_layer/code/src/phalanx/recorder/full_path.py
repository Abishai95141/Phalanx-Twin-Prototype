"""The full data path in one call: CIR -> bus (M15) -> Ch10 (M16) -> download (M16) -> decoder (M17).

This is the entry point W2.2 wires after a sortie's telemetry run (architecture §4 "full path", AD-12). Every
stage is a pure function of its inputs and identity-keyed draws (AD-37), so the same CIR, identity and root
seed give the same recording bytes and the same decoded Parquet (A8), and forks of a sortie share the
data-path
timing (CRN, I8).

``full_path_truth_labels`` links each full-path record to the CIR truth behind it (restricted
``labels.truth``,
TRUTH_SAMPLE), the full-path counterpart of ``phalanx.ground.fast_path.cir_to_truth_labels``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from phalanx.bus.clocks import LruOscillator, SortieIdentity
from phalanx.bus.encoder import BusConfig, BusTraffic, encode_bus
from phalanx.bus.icd import BusIcd
from phalanx.core.rng import RngService
from phalanx.dictionary.contract import Contract, load_contract
from phalanx.ground.cir import CirBatch
from phalanx.ground.decoder import DecoderConfig, DecodeResult, decode_recording
from phalanx.ground.rid import full_path_channel_id, record_ids

from .download import Delivery, DownloadConfig, simulate_download
from .setup import EventDef
from .writer import RecorderConfig, Recording, RecordingEvent, write_recording

__all__ = ["FullPathResult", "full_path_truth_labels", "recording_window", "run_full_path"]

_NS = 1_000_000_000


@dataclass(frozen=True)
class FullPathResult:
    traffic: BusTraffic  # truth-bearing (restricted)
    recording: Recording  # bytes + restricted truth
    deliveries: tuple[Delivery, ...]
    decoded: tuple[DecodeResult, ...]  # one per delivery, same order

    def samples(self) -> pa.Table:
        """Every delivery's ``param.samples`` concatenated (re-delivered records appear again; idempotent
        ingest, ``phalanx.streaming``, keeps the earliest)."""
        return pa.concat_tables([r.samples for r in self.decoded])


def recording_window(t_start: int, t_end: int) -> tuple[int, int]:
    """The recorder starts at the first time-source mark (whole second) at or after ``t_start``."""
    t0 = -(-int(t_start) // _NS) * _NS
    if t0 >= int(t_end):
        raise ValueError("the window holds no whole second: nothing would be recorded")
    return t0, int(t_end)


def run_full_path(
    cir: CirBatch,
    *,
    ident: SortieIdentity,
    rng: RngService,
    t_start: int,
    t_end: int,
    dictionary: Any = None,
    events: Sequence[RecordingEvent] = (),
    event_defs: Sequence[EventDef] = (),
    fti_fitted: bool = False,
    bus: BusConfig | None = None,
    recorder: RecorderConfig | None = None,
    download: DownloadConfig | None = None,
    decoder: DecoderConfig | None = None,
    contract: Contract | None = None,
    oscillators: Mapping[str, LruOscillator] | None = None,
    recording_id: str | None = None,
    sink: str | None = None,
) -> FullPathResult:
    """Run M15 -> M16 -> download -> M17 on one sortie's CIR over ``[t_start, t_end)`` (sim-UTC ns).

    ``oscillators``: LRU crystals shared with acquisition; at integration pass
    ``phalanx.bus.clocks.acquisition_oscillators(dictionary, epoch_ns)`` (M13 clock domains, A-W1.6-21).
    ``recording_id`` / ``sink``: the recording's identity (contract 0.2.0, A-W0.4-22); both None (default) for
    the single bus-monitor capture, whose records keep their 0.1.0 ids.
    """
    from phalanx.dictionary import load_dictionary

    d = dictionary or load_dictionary()
    c = contract or load_contract("v0")
    if cir.tail_no != ident.tail_no or cir.sortie_id != ident.sortie_id:
        raise ValueError("CIR batch and sortie identity disagree on tail/sortie")
    t0, t1 = recording_window(t_start, t_end)
    icd = BusIcd.from_dictionary(d)
    traffic = encode_bus(
        cir,
        icd,
        bus or BusConfig.from_params(),
        ident,
        rng,
        t0=t0,
        t1=t1,
        fti_fitted=fti_fitted,
        oscillators=oscillators,
    )
    rec = write_recording(
        traffic,
        ident,
        rng,
        recorder or RecorderConfig.from_params(),
        events=events,
        event_defs=event_defs,
        recording_id=recording_id,
        sink=sink,
    )
    deliveries = simulate_download(
        rec.data,
        t1,
        ident,
        rng,
        download or DownloadConfig.from_params(),
        recording_id=rec.recording_id,
        sink=rec.sink,
    )
    dcfg = decoder or DecoderConfig.from_params()
    decoded = tuple(
        decode_recording(
            dl.data,
            dictionary=d,
            tail_no=dl.tail_no,
            sortie_id=dl.sortie_id,
            t_ingest=dl.t_ingest,
            attempt=dl.attempt,
            engine_serial=ident.engine_serial,
            config=dcfg,
            contract=c,
            recording_id=dl.recording_id,
            sink=dl.sink,
        )
        for dl in deliveries
    )
    return FullPathResult(traffic, rec, deliveries, decoded)


def full_path_truth_labels(
    rec: Recording, cir: CirBatch, *, contract: Contract | None = None, dictionary: Any = None
) -> pa.Table:
    """RESTRICTED ``labels.truth`` (TRUTH_SAMPLE) for every recorded item with CIR data behind it.

    ``related_record_id`` is the full-path record_id of the decoded sample; ``t_true``/``value`` are the CIR
    truth instant and truth value of the acquisition that was transmitted.
    """
    from phalanx.dictionary import load_dictionary

    c = contract or load_contract("v0")
    d = dictionary or load_dictionary()
    tr = rec.truth
    rows = tr.column("cir_row").to_numpy()
    keep = rows >= 0
    cir_truth = cir.table.column("truth_value")
    has_truth = np.zeros(rows.size, dtype=bool)
    if keep.any():
        has_truth[keep] = pc.is_valid(cir_truth.take(pa.array(rows[keep]))).to_numpy(zero_copy_only=False)
    sel = np.flatnonzero(keep & has_truth)
    t = tr.take(pa.array(sel))
    r = rows[sel]
    n = sel.size
    chan = t.column("channel_id")
    if rec.recording_id is not None:  # contract 0.2.0 channel component of an identified recording
        chan = pa.array([full_path_channel_id(x, rec.recording_id) for x in chan.to_pylist()], pa.string())
    sample_ids = record_ids(
        c,
        "param.samples",
        {
            "provenance": "full_path",
            "tail_no": cir.tail_no,
            "sortie_id": cir.sortie_id,
            "channel_id": chan,
            "param_id": t.column("param_id"),
            "seq": t.column("seq"),
            "msg_index": t.column("msg_index"),
        },
        n,
    )
    t_true = cir.table.column("t_true").take(pa.array(r))
    rid = record_ids(
        c,
        "labels.truth",
        {
            "label_kind": "TRUTH_SAMPLE",
            "subject_id": t.column("param_id"),
            "tail_no": cir.tail_no,
            "sortie_id": cir.sortie_id,
            "serial_no": None,
            "related_record_id": sample_ids,
            "t_true": t_true,
        },
        n,
    )
    units = d.units_map()
    schema = c.schemas["labels.truth"]
    cols = {
        "record_id": rid,
        "dict_version": pa.array([d.dict_version] * n, pa.string()),
        "dict_hash": pa.array([d.dict_hash] * n, pa.string()),
        "label_kind": pa.array(["TRUTH_SAMPLE"] * n, pa.string()),
        "subject_id": t.column("param_id"),
        "tail_no": pa.array([cir.tail_no] * n, pa.string()),
        "sortie_id": pa.array([cir.sortie_id] * n, pa.string()),
        "serial_no": pa.nulls(n, pa.string()),
        "t_true": t_true,
        "t_end": pa.nulls(n, pa.int64()),
        "value": cir_truth.take(pa.array(r)),
        "units": pa.array([units[p] for p in t.column("param_id").to_pylist()], pa.string()),
        "category": pa.nulls(n, pa.string()),
        "related_record_id": sample_ids,
        "source_module": pa.array(["M16"] * n, pa.string()),
    }
    arrays = [cols[f.name] for f in schema]
    arrays = [a.combine_chunks() if isinstance(a, pa.ChunkedArray) else a for a in arrays]
    out = pa.Table.from_arrays(arrays, schema=schema)
    c.validate("labels.truth", out)
    return out
