"""Fast path: CIR -> contract ``param.samples`` (``provenance = direct``), architecture §4 and AD-12.

The output schema is the generated contract schema itself, so it is identical to what the full path (W1.7)
emits; every batch is validated against it before it is returned (A7).

Rules for what the fast path cannot know (A-W0.4-3/4/5):

- ``t_bus``, ``t_record``, ``raw_counts``, ``bus``, ``rt_sa_word``, ``label_sdi``: null. No bus or recorder
  model runs on this path, and inventing latencies would be a shallow proxy.
- ``t_utc = t_sample``. **PROXY**: a perfectly locked time source. The full path replaces it with M16's time
  packets (lock loss -> TIME_SOURCE_INTERNAL). Exposed by ``test_fast_path_time_and_null_rules``.
- ``t_ingest``: the caller supplies the sortie's download instant; it must be >= every t_sample.
- ``recording_id``, ``sink`` (contract 0.2.0): null; the fast path has no on-board recording.
- record_id components: ``channel_id = "direct:<source_lru>:<lane or empty>"``, ``seq = sample_index``,
  ``msg_index = 0``.
- quality flags pass through; the CIR may only carry acquisition-scope flags, so the fast path never sets bus,
  recorder or ground flags.
- dictionary check (when the config comes from :meth:`FastPathConfig.from_dictionary`): every CIR stream
  ``(param_id, source_lru, lane)`` must be a dictionary channel, or the batch is rejected; a value outside the
  channel's dictionary range is **flagged** ``OUT_OF_RANGE`` (kept, not dropped or clipped). Saturation is
  M13's job; this is the decoder-side quality flag.
- ``truth_value`` and ``t_true`` are dropped; :func:`cir_to_truth_labels` routes them to the restricted
  ``labels.truth`` topic.
- **Channel set (AD-54, coordinator decision W2.2):** the consumer-visible ``param.samples`` channel set is
  identical on both paths, so the fast path emits only channels the full path can carry: a recorded-bus
  transport (``RECORDED_TRANSPORTS``: MIL-STD-1553 data, status and mode-code words, ARINC-429) and, when the
  FTI system is fitted, the FTI PCM stream (as ``run_full_path(fti_fitted=...)``). LRU-internal lanes
  (transport ``internal``, the ADC-DFCC RS-422 links) and channels delivered by other topics stay in the CIR
  and internal diagnostics; their truth labels are not emitted either (no sample to label). A hand-built
  config (``visible=None``) applies no channel-set rule (interface tests only).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from phalanx.dictionary.contract import Contract, load_contract

from .cir import CirBatch
from .rid import record_ids

if TYPE_CHECKING:
    from phalanx.dictionary import Dictionary

#: (param_id, source_lru, lane) -> (range min, range max); None (or None bounds) = no declared range
ChannelKey = tuple[str, str, str | None]
ChannelRange = tuple[float | None, float | None] | None
ENGINE_SUBSYSTEMS = frozenset({"engine", "engine_usage"})

TOPIC = "param.samples"
LABELS_TOPIC = "labels.truth"
FAST_PATH_CHANNEL_PREFIX = "direct"
PROVENANCE = "direct"
#: dictionary transports carried by the on-board recording (M15 bus encoder -> M16 -> M17), AD-54
RECORDED_TRANSPORTS = frozenset({"mil1553", "mil1553_status", "mil1553_modecode", "arinc429"})
#: the FTI PCM stream: recorded only when the FTI system is fitted
FTI_TRANSPORT = "fti_pcm"


@dataclass(frozen=True)
class FastPathConfig:
    """Dictionary-derived inputs of the fast path (wired to M01 at integration, W0.X).

    Build it with :meth:`from_dictionary` in production: that carries the dictionary's channel set and ranges,
    so unknown channels are rejected and out-of-range values flagged. A hand-built config (``channels=None``)
    checks only that every param_id has units; it is meant for interface tests.

    Attributes:
        dict_version, dict_hash: the M01 dictionary the CIR was produced against.
        units: ``param_id -> engineering unit`` from the dictionary (every CIR param must be present).
        engine_serial: ``param_id -> engine serial`` for engine parameters (from the sortie configuration);
            parameters not listed get a null engine_serial.
        channels: ``(param_id, source_lru, lane) -> (min, max) | None``: the dictionary's channels and ranges.
        visible: the channels ``param.samples`` may carry (AD-54: those with a full-path transport); None
            applies no channel-set rule.
    """

    dict_version: str
    dict_hash: str
    units: Mapping[str, str]
    engine_serial: Mapping[str, str] = field(default_factory=dict)
    channels: Mapping[ChannelKey, ChannelRange] | None = None
    visible: frozenset[ChannelKey] | None = None

    @classmethod
    def from_dictionary(
        cls,
        d: Dictionary,
        *,
        engine_serial: str | Mapping[str, str] | None = None,
        fti_fitted: bool = False,
    ) -> FastPathConfig:
        """Config bound to a compiled M01 dictionary.

        Channel identity is ``Dictionary.contract_location`` (param_id = measurand, source_lru = acquiring
        LRU, lane or None) and the range is the channel's dictionary ``range`` (``min``/``max``; channels
        without a declared range are not range-checked).

        Args:
            engine_serial: a single serial applied to every engine measurand (subsystems ``engine`` and
                ``engine_usage``; the Tejas is single-engine), or an explicit ``param_id -> serial`` map.
            fti_fitted: the sortie's aircraft carries the FTI system (its PCM channels are then recorded and
                visible, as on the full path).
        """
        channels: dict[ChannelKey, ChannelRange] = {}
        visible: set[ChannelKey] = set()
        transports = RECORDED_TRANSPORTS | ({FTI_TRANSPORT} if fti_fitted else set())
        engine_params: set[str] = set()
        for ch in d.channels():
            loc = d.contract_location(ch["channel_id"])
            key = (loc["param_id"], loc["source_lru"], loc["lane"])
            if key in channels:
                raise ValueError(f"dictionary has two channels with contract identity {key}")
            rng = ch.get("range")
            channels[key] = None if not rng else (rng.get("min"), rng.get("max"))
            if (ch.get("transport") or {}).get("type") in transports:
                visible.add(key)
            if ch.get("subsystem") in ENGINE_SUBSYSTEMS:
                engine_params.add(loc["param_id"])
        if engine_serial is None:
            serials: dict[str, str] = {}
        elif isinstance(engine_serial, str):
            serials = {p: engine_serial for p in sorted(engine_params)}
        else:
            serials = dict(engine_serial)
        return cls(d.dict_version, d.dict_hash, d.units_map(), serials, channels, frozenset(visible))


def fast_path_channel_ids(
    source_lru: pa.ChunkedArray | pa.Array, lane: pa.ChunkedArray | pa.Array
) -> pa.Array:
    """``direct:<source_lru>:<lane or empty>`` per row. Unambiguous because neither part may contain ':' and a
    lane is never the empty string (CIR patterns)."""
    lane_s = pc.fill_null(lane, "")
    prefix = pa.scalar(f"{FAST_PATH_CHANNEL_PREFIX}:")
    out = pc.binary_join_element_wise(prefix, source_lru, pa.scalar(":"), lane_s, "")
    return out.combine_chunks() if isinstance(out, pa.ChunkedArray) else out


def _map_strings(keys: pa.ChunkedArray, mapping: Mapping[str, str], *, required: bool, what: str) -> pa.Array:
    enc = pc.dictionary_encode(keys.combine_chunks())
    uniques = enc.dictionary.to_pylist()
    missing = [u for u in uniques if u not in mapping]
    if required and missing:
        raise KeyError(f"fast path: no {what} for param_id(s) {missing[:10]}")
    mapped = pa.array([mapping.get(u) for u in uniques], pa.string())
    return mapped.take(enc.indices)


def cir_to_param_samples(
    batch: CirBatch,
    config: FastPathConfig,
    *,
    t_ingest: int,
    contract: Contract | None = None,
) -> pa.Table:
    """Convert a CIR batch to a validated ``param.samples`` table (provenance ``direct``).

    Args:
        batch: one (tail, sortie) CIR batch; validated here.
        config: dictionary version/hash, units and engine-serial maps.
        t_ingest: ground arrival time of the sortie's data (int ns, sim UTC); must be >= max t_sample.
        contract: contract to emit against (default: the built-in v0).

    Raises:
        CirViolation, ContractViolation, KeyError, ValueError.
    """
    c = contract or load_contract("v0")
    batch.validate(c)
    tab = batch.table
    n = tab.num_rows
    if isinstance(t_ingest, bool) or not isinstance(t_ingest, int | np.integer):
        raise TypeError("t_ingest must be an int (ns)")
    t_ingest = int(t_ingest)
    if n and t_ingest < pc.max(tab.column("t_sample")).as_py():
        raise ValueError(
            "t_ingest precedes a sample's t_sample: data cannot reach the ground before it exists"
        )
    schema = c.schemas[TOPIC]
    flags = tab.column("quality_flags").combine_chunks()
    if config.channels is not None:
        flags = _check_channels(c, tab, config.channels, flags)
    if config.visible is not None:  # AD-54: only channels with a full-path transport
        keep = _visible_mask(tab, config.visible)
        tab = tab.filter(keep)
        flags = flags.filter(keep)
        n = tab.num_rows

    channel = fast_path_channel_ids(tab.column("source_lru"), tab.column("lane"))
    rid = record_ids(
        c,
        TOPIC,
        {
            "provenance": PROVENANCE,
            "tail_no": batch.tail_no,
            "sortie_id": batch.sortie_id,
            "channel_id": channel,
            "param_id": tab.column("param_id"),
            "seq": tab.column("sample_index"),
            "msg_index": 0,
        },
        n,
    )

    def const(v: object, t: pa.DataType) -> pa.Array:
        return pa.array([v] * n, type=t) if v is not None else pa.nulls(n, type=t)

    cols = {
        "record_id": rid,
        "dict_version": const(config.dict_version, pa.string()),
        "dict_hash": const(config.dict_hash, pa.string()),
        "param_id": tab.column("param_id"),
        "tail_no": const(batch.tail_no, pa.string()),
        "sortie_id": const(batch.sortie_id, pa.string()),
        "engine_serial": _map_strings(
            tab.column("param_id"), config.engine_serial, required=False, what="engine serial"
        ),
        "source_lru": tab.column("source_lru"),
        "lane": tab.column("lane"),
        "bus": pa.nulls(n, pa.string()),
        "rt_sa_word": pa.nulls(n, pa.string()),
        "label_sdi": pa.nulls(n, pa.string()),
        "t_sample": tab.column("t_sample"),
        "t_bus": pa.nulls(n, pa.int64()),
        "t_record": pa.nulls(n, pa.int64()),
        "t_utc": tab.column("t_sample"),  # PROXY (A-W0.4-4): perfect time-source lock
        "t_ingest": const(t_ingest, pa.int64()),
        "value_eu": tab.column("value"),
        "raw_counts": pa.nulls(n, pa.int64()),
        "units": _map_strings(tab.column("param_id"), config.units, required=True, what="units"),
        "validity": tab.column("validity"),
        "quality_flags": flags,
        "provenance": const(PROVENANCE, pa.string()),
        # contract 0.2.0 (A-W0.4-22): no on-board recording on the fast path
        "recording_id": pa.nulls(n, pa.string()),
        "sink": pa.nulls(n, pa.string()),
    }
    arrays = [cols[f.name] for f in schema]  # a 0.1.0 contract simply takes fewer columns
    arrays = [a.combine_chunks() if isinstance(a, pa.ChunkedArray) else a for a in arrays]
    out = pa.Table.from_arrays(arrays, schema=schema)
    c.validate(TOPIC, out)
    return out


def _check_channels(
    c: Contract, tab: pa.Table, channels: Mapping[ChannelKey, ChannelRange], flags: pa.Array
) -> pa.Array:
    """Reject streams that are not dictionary channels; OR OUT_OF_RANGE into rows outside the range."""
    params = tab.column("param_id").to_pylist()
    lrus = tab.column("source_lru").to_pylist()
    lanes = tab.column("lane").to_pylist()
    keys = list(zip(params, lrus, lanes, strict=True))
    unknown = sorted({k for k in keys if k not in channels}, key=lambda k: (k[0], k[1], k[2] or ""))
    if unknown:
        raise ValueError(f"fast path: CIR streams are not dictionary channels: {unknown[:10]}")
    lo = np.array([_bound(channels[k], 0, -np.inf) for k in keys], dtype=np.float64)
    hi = np.array([_bound(channels[k], 1, np.inf) for k in keys], dtype=np.float64)
    v = tab.column("value").to_numpy()
    out = (v < lo) | (v > hi)
    if not out.any():
        return flags
    bit = np.uint32(c.quality_flags.mask("OUT_OF_RANGE"))
    f = flags.to_numpy(zero_copy_only=False).astype(np.uint32)
    f[out] |= bit
    return pa.array(f, pa.uint32())


def _visible_mask(tab: pa.Table, visible: frozenset[ChannelKey]) -> pa.Array:
    """Rows whose stream ``(param_id, source_lru, lane)`` is in ``visible`` (AD-54)."""
    keys = zip(
        tab.column("param_id").to_pylist(),
        tab.column("source_lru").to_pylist(),
        tab.column("lane").to_pylist(),
        strict=True,
    )
    return pa.array([k in visible for k in keys], pa.bool_())


def _bound(r: ChannelRange, i: int, default: float) -> float:
    if r is None or r[i] is None:
        return default
    return float(r[i])


def cir_to_truth_labels(
    batch: CirBatch,
    config: FastPathConfig,
    *,
    contract: Contract | None = None,
    source_module: str = "M13",
) -> pa.Table:
    """Route CIR truth values to the RESTRICTED ``labels.truth`` topic (label_kind TRUTH_SAMPLE).

    One label per CIR row with a non-null truth_value; ``related_record_id`` is the fast-path record_id of the
    sample it labels.
    """
    c = contract or load_contract("v0")
    batch.validate(c)
    tab = batch.table
    keep = pc.is_valid(tab.column("truth_value"))
    if config.visible is not None:  # AD-54: label only samples param.samples carries
        keep = pc.and_(keep, _visible_mask(tab, config.visible))
    tab = tab.filter(keep)
    n = tab.num_rows
    sample_ids = record_ids(
        c,
        TOPIC,
        {
            "provenance": PROVENANCE,
            "tail_no": batch.tail_no,
            "sortie_id": batch.sortie_id,
            "channel_id": fast_path_channel_ids(tab.column("source_lru"), tab.column("lane")),
            "param_id": tab.column("param_id"),
            "seq": tab.column("sample_index"),
            "msg_index": 0,
        },
        n,
    )
    schema = c.schemas[LABELS_TOPIC]
    rid = record_ids(
        c,
        LABELS_TOPIC,
        {
            "label_kind": "TRUTH_SAMPLE",
            "subject_id": tab.column("param_id"),
            "tail_no": batch.tail_no,
            "sortie_id": batch.sortie_id,
            "serial_no": None,
            # one truth label per labelled sample: the sample's record_id makes lanes sampled at the same
            # t_true distinct
            "related_record_id": sample_ids,
            "t_true": tab.column("t_true"),
        },
        n,
    )

    def const(v: object, t: pa.DataType) -> pa.Array:
        return pa.array([v] * n, type=t) if v is not None else pa.nulls(n, type=t)

    cols = {
        "record_id": rid,
        "dict_version": const(config.dict_version, pa.string()),
        "dict_hash": const(config.dict_hash, pa.string()),
        "label_kind": const("TRUTH_SAMPLE", pa.string()),
        "subject_id": tab.column("param_id"),
        "tail_no": const(batch.tail_no, pa.string()),
        "sortie_id": const(batch.sortie_id, pa.string()),
        "serial_no": pa.nulls(n, pa.string()),
        "t_true": tab.column("t_true"),
        "t_end": pa.nulls(n, pa.int64()),
        "value": tab.column("truth_value"),
        "units": _map_strings(tab.column("param_id"), config.units, required=True, what="units"),
        "category": pa.nulls(n, pa.string()),
        "related_record_id": sample_ids,
        "source_module": const(source_module, pa.string()),
    }
    arrays = [cols[f.name] for f in schema]
    arrays = [a.combine_chunks() if isinstance(a, pa.ChunkedArray) else a for a in arrays]
    out = pa.Table.from_arrays(arrays, schema=schema)
    c.validate(LABELS_TOPIC, out)
    return out
