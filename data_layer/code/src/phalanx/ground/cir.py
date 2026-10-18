"""Canonical Internal Representation (CIR): what the observation layer (M13/M14) hands to the data path.

Architecture §4 (observation layer output), §20 (glossary), report §5. The CIR is columnar (an Arrow table,
struct of arrays), one row per acquired sample, for one (tail, sortie). It is *internal*: it carries the truth
value and ``t_true``, which never leave through the contract (they go to the restricted ``labels.truth``
only).

Columns (all times int64 ns on the simulated UTC calendar, A-W0.4-1):

==============  =========  ====  ==========================================================================
column          type       null  meaning
==============  =========  ====  ==========================================================================
param_id        string     no    dictionary key (M01)
source_lru      string     no    acquiring LRU (pattern ``^[A-Za-z0-9][A-Za-z0-9_.-]*$``, no colon)
lane            string     yes   redundancy lane (pattern ``^[A-Za-z0-9]+$``); null if not redundant
sample_index    uint64     no    index of this sample in its (param_id, source_lru, lane) acquisition stream
                                 within the sortie; strictly increasing with t_sample (A-W0.4-3)
t_true          int64 ns   no    physics instant of the truth value; t_true <= t_sample
t_sample        int64 ns   no    LRU acquisition instant (its drifting oscillator)
value           float64    no    acquired value in the dictionary EU of param_id (A-W0.4-6); never NaN
truth_value     float64    yes   RESTRICTED truth value in the same EU; never NaN
validity        string     no    contract Validity symbol
quality_flags   uint32     no    contract QualityFlags; only acquisition-scope bits may be set here
rng_key_path    string     yes   ``phalanx.core.rng.KeyPath.canonical()`` of the sample's noise stream
                                 (e.g. ``scenario=s:S1/tail=s:T001/sortie=s:S1/sensor=s:N2.A``); validated
                                 by a round trip through ``KeyPath`` (AD-37); see :func:`key_path_text`
==============  =========  ====  ==========================================================================

The identity of the batch (tail_no, sortie_id) is held once on :class:`CirBatch`, not per row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from phalanx.core.rng import KeyPath, RngError

if TYPE_CHECKING:
    from phalanx.dictionary.contract import Contract

CIR_VERSION = "0.1.0"
LRU_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
LANE_PATTERN = r"^[A-Za-z0-9]+$"
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class CirViolation(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = tuple(errors)
        super().__init__("CIR violation(s):\n  - " + "\n  - ".join(errors[:50]))


def key_path_text(key_path: KeyPath) -> str:
    """The CIR ``rng_key_path`` text of a core.rng key path (its canonical form, AD-37)."""
    return key_path.canonical()


def parse_key_path(text: str) -> KeyPath:
    """Inverse of :func:`key_path_text`. Raises ValueError unless ``text`` is exactly a canonical key path."""
    parts: list[tuple[str, str | int]] = []
    for comp in text.split("/"):
        kind, eq, rest = comp.partition("=")
        typ, colon, value = rest.partition(":")
        if not eq or not colon or typ not in ("s", "i") or not kind:
            raise ValueError(f"not a canonical key path component: {comp!r}")
        if typ == "i":
            if not value.isdigit():
                raise ValueError(f"integer component {comp!r} is not a non-negative integer")
            parts.append((kind, int(value)))
        else:
            parts.append((kind, value))
    try:
        kp = KeyPath(tuple(parts))
    except (RngError, KeyError) as e:
        raise ValueError(f"invalid key path {text!r}: {e}") from e
    if kp.canonical() != text:
        raise ValueError(f"key path text {text!r} is not canonical (expected {kp.canonical()!r})")
    return kp


def _md(desc: str, **kv: str) -> dict[str, str]:
    return {"phalanx.description": desc, **{f"phalanx.{k}": v for k, v in kv.items()}}


def cir_schema() -> pa.Schema:
    """The CIR Arrow schema (version :data:`CIR_VERSION`)."""
    t = {"time_unit": "ns", "time_scale": "sim_utc"}
    return pa.schema(
        [
            pa.field("param_id", pa.string(), nullable=False, metadata=_md("Dictionary key (M01).")),
            pa.field(
                "source_lru", pa.string(), nullable=False, metadata=_md("Acquiring LRU.", pattern=LRU_PATTERN)
            ),
            pa.field(
                "lane", pa.string(), nullable=True, metadata=_md("Redundancy lane.", pattern=LANE_PATTERN)
            ),
            pa.field(
                "sample_index",
                pa.uint64(),
                nullable=False,
                metadata=_md(
                    "Per-stream acquisition index within the sortie; strictly increasing with t_sample."
                ),
            ),
            pa.field(
                "t_true", pa.int64(), nullable=False, metadata=_md("Physics instant of the truth value.", **t)
            ),
            pa.field("t_sample", pa.int64(), nullable=False, metadata=_md("LRU acquisition instant.", **t)),
            pa.field("value", pa.float64(), nullable=False, metadata=_md("Acquired value, dictionary EU.")),
            pa.field(
                "truth_value",
                pa.float64(),
                nullable=True,
                metadata=_md("Truth value, dictionary EU. RESTRICTED.", restricted="true"),
            ),
            pa.field(
                "validity",
                pa.string(),
                nullable=False,
                metadata=_md("Contract Validity symbol.", enum="Validity"),
            ),
            pa.field(
                "quality_flags",
                pa.uint32(),
                nullable=False,
                metadata=_md("Contract QualityFlags (acquisition scope only).", flags="QualityFlags"),
            ),
            pa.field(
                "rng_key_path",
                pa.string(),
                nullable=True,
                metadata=_md("Canonical text of the core.rng KeyPath of the noise stream (AD-37)."),
            ),
        ],
        metadata={"phalanx.cir_version": CIR_VERSION},
    )


CIR_SCHEMA = cir_schema()


def _stream_codes(table: pa.Table) -> np.ndarray:
    """Integer code per row identifying its (param_id, source_lru, lane) stream."""
    key = np.zeros(table.num_rows, dtype=np.int64)
    for name in ("param_id", "source_lru", "lane"):
        enc = pc.dictionary_encode(table.column(name).combine_chunks(), null_encoding="encode")
        key = key * (len(enc.dictionary) + 1) + enc.indices.to_numpy(zero_copy_only=False).astype(np.int64)
    return np.unique(key, return_inverse=True)[1].reshape(-1)


def validate_cir(contract: Contract, table: pa.Table) -> None:
    """Validate a CIR table; raise :class:`CirViolation` listing every problem."""
    errors: list[str] = []
    if table.schema.names != CIR_SCHEMA.names:
        raise CirViolation([f"columns {table.schema.names} != CIR columns {CIR_SCHEMA.names}"])
    for e, g in zip(CIR_SCHEMA, table.schema, strict=True):
        if not e.type.equals(g.type) or e.nullable != g.nullable:
            errors.append(
                f"{e.name}: {g.type} nullable={g.nullable}, expected {e.type} nullable={e.nullable}"
            )
    if errors:
        raise CirViolation(errors)
    for f in CIR_SCHEMA:
        if not f.nullable and table.column(f.name).null_count:
            errors.append(f"{f.name}: {table.column(f.name).null_count} null(s) in a non-nullable column")
    if table.num_rows == 0:
        if errors:
            raise CirViolation(errors)
        return
    for name, pat in (("source_lru", LRU_PATTERN), ("lane", LANE_PATTERN), ("param_id", r"^\S+$")):
        ok = pc.match_substring_regex(table.column(name), pat)
        n = int(pc.sum(pc.invert(ok)).as_py() or 0)
        if n:
            errors.append(f"{name}: {n} value(s) do not match {pat}")
    for name in ("value", "truth_value"):
        n = int(pc.sum(pc.invert(pc.is_finite(table.column(name)))).as_py() or 0)
        if n:
            errors.append(f"{name}: {n} NaN/inf value(s)")
    ok = pc.is_in(table.column("validity"), value_set=pa.array(contract.validity.names))
    if not pc.all(ok).as_py():
        errors.append(f"validity: values outside {contract.validity.names}")
    qf = contract.quality_flags
    not_allowed = ((1 << qf.width) - 1) & ~qf.scope_mask("acquisition")
    hit = pc.bit_wise_and(table.column("quality_flags"), pa.scalar(not_allowed, pa.uint32()))
    if pc.any(pc.not_equal(hit, pa.scalar(0, pa.uint32()))).as_py():
        errors.append(
            "quality_flags: bus/recorder/ground or reserved bits set in CIR (acquisition scope only)"
        )
    for text in pc.unique(pc.drop_null(table.column("rng_key_path"))).to_pylist():
        try:
            parse_key_path(text)
        except ValueError as e:
            errors.append(f"rng_key_path: {e}")
    t_true = table.column("t_true").to_numpy()
    t_sample = table.column("t_sample").to_numpy()
    if t_true.min() < 0 or t_sample.min() < 0:
        errors.append("times must be >= 0")
    if np.any(t_true > t_sample):
        errors.append(f"t_true > t_sample in {int(np.sum(t_true > t_sample))} row(s)")
    stream = _stream_codes(table)
    idx = table.column("sample_index").to_numpy()
    order = np.lexsort((idx, stream))
    s, i, ts = stream[order], idx[order], t_sample[order]
    same = s[1:] == s[:-1]
    if np.any(same & (i[1:] == i[:-1])):
        errors.append("sample_index not unique within a (param_id, source_lru, lane) stream")
    if np.any(same & (ts[1:] <= ts[:-1])):
        errors.append("t_sample not strictly increasing with sample_index within a stream")
    if errors:
        raise CirViolation(errors)


def assign_sample_index(table: pa.Table) -> pa.Table:
    """Return ``table`` with ``sample_index`` set to each row's rank by t_sample within its stream.

    Use only on a *whole-sortie* CIR table (the index is relative to the sortie's first sample of the stream);
    producers that emit blocks should carry their acquisition tick index instead.
    """
    stream = _stream_codes(table)
    t = table.column("t_sample").to_numpy()
    order = np.lexsort((t, stream))
    s = stream[order]
    starts = np.r_[0, np.flatnonzero(s[1:] != s[:-1]) + 1]
    run_start = np.repeat(starts, np.diff(np.r_[starts, len(s)]))
    rank = np.empty(len(s), dtype=np.uint64)
    rank[order] = (np.arange(len(s)) - run_start).astype(np.uint64)
    i = table.schema.get_field_index("sample_index")
    return table.set_column(i, table.schema.field(i), pa.array(rank, pa.uint64()))


@dataclass(frozen=True)
class CirBatch:
    """A validated CIR table for one (tail, sortie)."""

    tail_no: str
    sortie_id: str
    table: pa.Table

    def validate(self, contract: Contract) -> None:
        import re

        errors = []
        for name in ("tail_no", "sortie_id"):
            v = getattr(self, name)
            if not isinstance(v, str) or not re.match(ID_PATTERN, v):
                errors.append(f"{name}={v!r} does not match {ID_PATTERN}")
        if errors:
            raise CirViolation(errors)
        validate_cir(contract, self.table)


# ---- builder for the observation layer (M13) ---------------------------------------------------------------
@dataclass(frozen=True)
class StreamSamples:
    """Sampled outputs of one acquisition stream ``(param_id, source_lru, lane)`` for
    :func:`cir_from_streams`.

    Every per-sample array has exactly ``n = len(sample_index)`` entries (explicit counts; streams have their
    own lengths, nothing is NaN-padded to a common length). Times are int64 ns on the simulated UTC calendar.

    ``t_true`` rule (A-W0.4-21): leave it ``None`` and it defaults to ``t_sample``. When the truth value is
    the 240 Hz truth interpolated at the LRU tick (:func:`truth_at_samples`), it *is* the truth at that
    instant, and sensor lag or dynamics are measurement error (``value - truth``), not a different truth
    instant. Give an earlier ``t_true`` only when the sensor or LRU model explicitly reports the physics
    instant its value refers to (e.g. an LRU publishing a value computed on an earlier frame). ``t_true`` is
    never after ``t_sample``.

    Attributes:
        sample_index: per-stream acquisition tick indices (non-negative ints, strictly increasing).
        t_sample: LRU acquisition instants.
        value: acquired values in the dictionary EU (no NaN).
        t_true: physics instants of the truth values (default: ``t_sample``).
        truth_value: truth values in the same EU, or None (no truth for this stream).
        truth_present: bool mask, False where a sample has no truth (stored as null; no NaN padding).
        validity: one Validity symbol for all samples, or one per sample.
        quality_flags: one acquisition-scope flag word for all samples, or one per sample.
        rng_key_path: the noise stream's ``KeyPath`` (or its canonical text), or None.
    """

    param_id: str
    source_lru: str
    lane: str | None
    sample_index: np.ndarray
    t_sample: np.ndarray
    value: np.ndarray
    t_true: np.ndarray | None = None
    truth_value: np.ndarray | None = None
    truth_present: np.ndarray | None = None
    validity: str | np.ndarray = "NORMAL"
    quality_flags: int | np.ndarray = 0
    rng_key_path: KeyPath | str | None = None


def _per_sample(name: str, v: object, n: int, dtype: object) -> np.ndarray:
    a = np.asarray(v)
    if a.ndim == 0:
        return np.full(n, a.item(), dtype=dtype)
    if a.shape != (n,):
        raise CirViolation([f"{name}: shape {a.shape} != ({n},) (explicit per-sample count)"])
    return a.astype(dtype, copy=False)


def cir_from_streams(
    contract: Contract, tail_no: str, sortie_id: str, streams: list[StreamSamples] | tuple[StreamSamples, ...]
) -> CirBatch:
    """Build and validate a :class:`CirBatch` from per-stream sampled outputs (stream, then sample order).

    Raises:
        CirViolation: on a count mismatch or any CIR rule (NaN, t_true > t_sample, flag scope, ...).
    """
    cols: dict[str, list] = {f.name: [] for f in CIR_SCHEMA}
    for s in streams:
        idx = np.asarray(s.sample_index)
        if idx.ndim != 1 or not np.issubdtype(idx.dtype, np.integer) or (idx.size and idx.min() < 0):
            raise CirViolation([f"{s.param_id}: sample_index must be a 1-D array of non-negative ints"])
        n = idx.shape[0]
        t_sample = _per_sample("t_sample", s.t_sample, n, np.int64)
        t_true = t_sample if s.t_true is None else _per_sample("t_true", s.t_true, n, np.int64)
        value = _per_sample("value", s.value, n, np.float64)
        if s.truth_value is None:
            if s.truth_present is not None:
                raise CirViolation([f"{s.param_id}: truth_present given without truth_value"])
            truth: list = [None] * n
        else:
            tv = _per_sample("truth_value", s.truth_value, n, np.float64)
            present = (
                np.ones(n, dtype=bool)
                if s.truth_present is None
                else _per_sample("truth_present", s.truth_present, n, bool)
            )
            truth = [float(x) if p else None for x, p in zip(tv.tolist(), present.tolist(), strict=True)]
        key = s.rng_key_path.canonical() if isinstance(s.rng_key_path, KeyPath) else s.rng_key_path
        cols["param_id"] += [s.param_id] * n
        cols["source_lru"] += [s.source_lru] * n
        cols["lane"] += [s.lane] * n
        cols["sample_index"] += idx.astype(np.uint64).tolist()
        cols["t_true"] += t_true.tolist()
        cols["t_sample"] += t_sample.tolist()
        cols["value"] += value.tolist()
        cols["truth_value"] += truth
        cols["validity"] += _per_sample("validity", s.validity, n, object).tolist()
        cols["quality_flags"] += _per_sample("quality_flags", s.quality_flags, n, np.int64).tolist()
        cols["rng_key_path"] += [key] * n
    table = pa.Table.from_pydict(cols, schema=CIR_SCHEMA)
    batch = CirBatch(tail_no, sortie_id, table)
    batch.validate(contract)
    return batch


def truth_at_samples(t_sample: np.ndarray, truth: np.ndarray, *, epoch_ns: int, k0: int = 0) -> np.ndarray:
    """Truth linearly interpolated at LRU ticks (A-W0.4-21; core.time AD-35 weights).

    Args:
        t_sample: acquisition instants (sim UTC ns).
        truth: truth values on the 240 Hz grid; ``truth[j]`` is the value at kernel step ``k0 + j``.
        epoch_ns: sim-UTC instant of kernel step 0 (contract time = epoch + kernel time).

    The result at ``t`` is ``x_k + w (x_{k+1} - x_k)`` with ``(k, w) = truth_interp_weights(t - epoch)``;
    ``w`` is exactly 0 on a truth step, which then needs no ``x_{k+1}``.
    """
    from phalanx.core.time import truth_interp_weights

    x = np.asarray(truth, dtype=np.float64)
    k, w = truth_interp_weights(np.asarray(t_sample, dtype=np.int64) - np.int64(epoch_ns))
    j = k - k0
    needs_next = w != 0.0
    if j.size and (j.min() < 0 or j.max() >= x.size or (needs_next & (j + 1 >= x.size)).any()):
        raise ValueError("t_sample outside the truth series")
    nxt = np.where(needs_next, j + 1, j)
    return x[j] + w * (x[nxt] - x[j])
