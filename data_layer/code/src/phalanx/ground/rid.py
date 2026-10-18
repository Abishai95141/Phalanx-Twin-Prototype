"""Deterministic record identifiers (architecture §12 ``record_id``; A-W0.4-2).

    record_id = blake2b(digest_size=16, person=b"phalanx.rid.v0")(
        enc_str(topic) || enc(c_1) || ... || enc(c_k))

where ``c_1..c_k`` are the topic's ``record_id_key`` components in spec order (str/rid first, then integers)
and

    enc_str(s)   = b"S" + uint32_le(len(utf8(s))) + utf8(s)
    enc_rid(r)   = b"R" + r                   (a 16-byte record_id, e.g. the record a label refers to)
    enc_str(None)= enc_rid(None) = b"N"
    enc_u64(v)   = b"U" + uint64_le(v)        (0 <= v < 2**64)
    enc_i64(v)   = b"I" + int64_le(v)         (-2**63 <= v < 2**63)

The encoding is typed and length-prefixed, hence injective: two records share an id only on a blake2b
collision. 128 bits keeps the birthday bound negligible at fleet scale (1e10 records: p ~ 1e-19). Builtin
``hash()`` is never used (it is salted per process).

Performance: the vectorised path hashes the per-stream string prefix once and copies that hasher state per
row (about 0.7 us per record on the build machine). A compiled implementation may replace it later; the golden
values in ``tests/unit/test_ground_record_id.py`` pin the definition.
"""

from __future__ import annotations

import hashlib
import re
import struct
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

if TYPE_CHECKING:
    from phalanx.dictionary.contract import Contract

RID_PERSON = b"phalanx.rid.v0"
RID_DIGEST_SIZE = 16
RECORD_ID_TYPE = pa.binary(RID_DIGEST_SIZE)

_U32 = struct.Struct("<I")
_U64 = struct.Struct("<Q")
_I64 = struct.Struct("<q")


def enc_str(s: str | None) -> bytes:
    if s is None:
        return b"N"
    if not isinstance(s, str):
        raise TypeError(f"string component expected, got {type(s).__name__}")
    b = s.encode("utf-8")
    return b"S" + _U32.pack(len(b)) + b


def enc_rid(r: bytes | None) -> bytes:
    if r is None:
        return b"N"
    if not isinstance(r, bytes | bytearray) or len(r) != RID_DIGEST_SIZE:
        raise ValueError("record_id component must be 16 bytes")
    return b"R" + bytes(r)


def enc_u64(v: int) -> bytes:
    if isinstance(v, bool) or not isinstance(v, int | np.integer) or not 0 <= int(v) < 2**64:
        raise ValueError(f"u64 component out of range: {v!r}")
    return b"U" + _U64.pack(int(v))


def enc_i64(v: int) -> bytes:
    if isinstance(v, bool) or not isinstance(v, int | np.integer) or not -(2**63) <= int(v) < 2**63:
        raise ValueError(f"i64 component out of range: {v!r}")
    return b"I" + _I64.pack(int(v))


def encode_key(topic: str, typed_components: Sequence[tuple[str, Any]]) -> bytes:
    """Canonical byte string for (topic, components); ``typed_components`` = [(type, value), ...]."""
    parts = [enc_str(topic)]
    for typ, v in typed_components:
        if typ == "str":
            parts.append(enc_str(v))
        elif typ == "rid":
            parts.append(enc_rid(v))
        elif typ == "u64":
            parts.append(enc_u64(v))
        elif typ == "i64":
            parts.append(enc_i64(v))
        else:
            raise ValueError(f"unknown component type {typ!r}")
    return b"".join(parts)


def _hasher(data: bytes = b"") -> Any:
    return hashlib.blake2b(data, digest_size=RID_DIGEST_SIZE, person=RID_PERSON)


def record_id(contract: Contract, topic: str, values: Mapping[str, Any]) -> bytes:
    """Scalar reference implementation: the 16-byte record_id of one record of ``topic``.

    ``values`` maps every ``record_id_key`` component name (column or path component) to its value.
    """
    key = contract.topics[topic].record_id_key
    missing = [c.name for c in key if c.name not in values]
    if missing:
        raise KeyError(f"{topic}: missing record_id components {missing}")
    return _hasher(encode_key(topic, [(c.type, values[c.name]) for c in key])).digest()


def to_hex(rid: bytes) -> str:
    if len(rid) != RID_DIGEST_SIZE:
        raise ValueError("record_id must be 16 bytes")
    return rid.hex()


def from_hex(s: str) -> bytes:
    if len(s) != 2 * RID_DIGEST_SIZE or s.lower() != s:
        raise ValueError("record_id hex must be 32 lower-case hex characters")
    return bytes.fromhex(s)


# ---- full-path recording identity (contract 0.2.0, A-W0.4-22) ------------------------------------------
#: key-safe recording id and sink patterns of contract 0.2.0 param.samples (no ':' in either)
RECORDING_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
SINK_PATTERN = r"^[A-Z][A-Z0-9_]*$"


def check_recording_identity(recording_id: str | None, sink: str | None) -> None:
    """Contract 0.2.0 rule: ``recording_id`` and ``sink`` are both null (fast path, or a single unattributed
    bus-monitor capture) or both set, and each matches its key-safe pattern."""
    if (recording_id is None) != (sink is None):
        raise ValueError("recording_id and sink must be both null or both set (contract 0.2.0, A-W0.4-22)")
    if recording_id is not None:
        if not isinstance(recording_id, str) or not re.match(RECORDING_ID_PATTERN, recording_id):
            raise ValueError(f"recording_id {recording_id!r} does not match {RECORDING_ID_PATTERN}")
        if not isinstance(sink, str) or not re.match(SINK_PATTERN, sink):
            raise ValueError(f"sink {sink!r} does not match {SINK_PATTERN}")


def full_path_channel_id(ch10_channel: int | str, recording_id: str | None) -> str:
    """The ``channel_id`` record_id component of a full-path record (contract 0.2.0, A-W0.4-22): the decimal
    Ch10 channel ID, qualified as ``<recording_id>:<channel ID>`` when the record's recording is identified.
    A null recording_id keeps the 0.1.0 form, so 0.1.0 record ids are unchanged."""
    ch = str(int(ch10_channel))
    return ch if recording_id is None else f"{recording_id}:{ch}"


# ---- vectorised --------------------------------------------------------------------------------------------
def _as_prefix_codes(v: Any, n: int, typ: str) -> tuple[np.ndarray, list[Any]]:
    """Dictionary codes and unique values of a str or rid component (scalar values broadcast)."""
    if v is None or isinstance(v, str | bytes):
        return np.zeros(n, dtype=np.int64), [v]
    arrow_t = pa.string() if typ == "str" else RECORD_ID_TYPE
    arr = v if isinstance(v, pa.Array | pa.ChunkedArray) else pa.array(v, type=arrow_t)
    if isinstance(arr, pa.ChunkedArray):
        arr = arr.combine_chunks()
    if len(arr) != n:
        raise ValueError(f"component length {len(arr)} != {n}")
    if typ == "str" and not pa.types.is_string(arr.type):
        raise TypeError(f"string component expected, got {arr.type}")
    if typ == "rid" and not arr.type.equals(RECORD_ID_TYPE):
        raise TypeError(f"record_id component expected, got {arr.type}")
    enc = pc.dictionary_encode(arr, null_encoding="encode")
    return enc.indices.to_numpy(zero_copy_only=False).astype(np.int64), enc.dictionary.to_pylist()


def _enc_prefix(typ: str, v: Any) -> bytes:
    return enc_str(v) if typ == "str" else enc_rid(v)


def _as_int_array(v: Any, n: int, typ: str) -> np.ndarray:
    if isinstance(v, int | np.integer) and not isinstance(v, bool):
        a = np.full(n, int(v), dtype=np.uint64 if typ == "u64" else np.int64)
        if typ == "u64" and int(v) < 0:
            raise ValueError("u64 component must be >= 0")
        return a
    if isinstance(v, pa.ChunkedArray):
        v = v.combine_chunks()
    if isinstance(v, pa.Array):
        if v.null_count:
            raise ValueError("integer record_id components must not be null")
        v = v.to_numpy(zero_copy_only=False)
    a = np.asarray(v)
    if a.shape != (n,) or not np.issubdtype(a.dtype, np.integer):
        raise ValueError(f"integer component must be an integer array of length {n}")
    if typ == "u64":
        if np.issubdtype(a.dtype, np.signedinteger) and a.size and a.min() < 0:
            raise ValueError("u64 component must be >= 0")
        return a.astype(np.uint64)
    if np.issubdtype(a.dtype, np.unsignedinteger) and a.size and a.max() >= 2**63:
        raise ValueError("i64 component out of range")
    return a.astype(np.int64)


def record_ids(contract: Contract, topic: str, columns: Mapping[str, Any], n: int) -> pa.FixedSizeBinaryArray:
    """Vectorised record_ids for ``n`` records of ``topic`` (identical to :func:`record_id` row by row).

    Args:
        columns: component name -> a scalar (broadcast) or an array-like of length ``n`` (``pa.Array`` /
            sequence of ``str | None`` for string components; integer ``np.ndarray`` / ``pa.Array`` for
            integer components).
    """
    key = contract.topics[topic].record_id_key
    missing = [c.name for c in key if c.name not in columns]
    if missing:
        raise KeyError(f"{topic}: missing record_id components {missing}")
    if n == 0:
        return pa.array([], type=RECORD_ID_TYPE)
    str_comps = [c for c in key if c.type in ("str", "rid")]
    int_comps = [c for c in key if c.type in ("u64", "i64")]

    # group rows by the tuple of str/rid components -> one hasher prefix per group
    codes, uniques = [], []
    for c in str_comps:
        cd, un = _as_prefix_codes(columns[c.name], n, c.type)
        codes.append(cd)
        uniques.append(un)
    if codes:
        radix = 1
        for un in uniques:
            radix *= max(len(un), 1)
        if radix < 2**62:
            gkey = np.zeros(n, dtype=np.int64)
            for cd, un in zip(codes, uniques, strict=True):
                gkey = gkey * len(un) + cd
            gvals, group = np.unique(gkey, return_inverse=True)
            combos = []
            for gv in gvals.tolist():
                idx = []
                for un in reversed(uniques):
                    gv, r = divmod(gv, len(un))
                    idx.append(r)
                combos.append(tuple(reversed(idx)))
        else:  # pragma: no cover - only for astronomically many distinct strings
            stacked = np.stack(codes, axis=0)
            gvals2, group = np.unique(stacked, axis=1, return_inverse=True)
            combos = [tuple(int(x) for x in gvals2[:, j]) for j in range(gvals2.shape[1])]
        group = np.asarray(group).reshape(-1)
        prefixes = []
        for combo in combos:
            p = enc_str(topic) + b"".join(
                _enc_prefix(str_comps[i].type, uniques[i][j]) for i, j in enumerate(combo)
            )
            prefixes.append(_hasher(p))
    else:
        group = np.zeros(n, dtype=np.int64)
        prefixes = [_hasher(enc_str(topic))]

    out = bytearray(RID_DIGEST_SIZE * n)
    if not int_comps:
        digests = [h.digest() for h in prefixes]
        for i, g in enumerate(group.tolist()):
            out[16 * i : 16 * i + 16] = digests[g]
    else:
        dtype = []
        for j, c in enumerate(int_comps):
            dtype += [(f"t{j}", "u1"), (f"v{j}", "<u8" if c.type == "u64" else "<i8")]
        rec = np.empty(n, dtype=np.dtype(dtype))
        for j, c in enumerate(int_comps):
            rec[f"t{j}"] = ord("U") if c.type == "u64" else ord("I")
            rec[f"v{j}"] = _as_int_array(columns[c.name], n, c.type)
        width = rec.dtype.itemsize
        assert width == 9 * len(int_comps)
        raw = memoryview(rec.tobytes())
        for i, g in enumerate(group.tolist()):
            h = prefixes[g].copy()
            h.update(raw[width * i : width * (i + 1)])
            out[16 * i : 16 * i + 16] = h.digest()
    return pa.Array.from_buffers(RECORD_ID_TYPE, n, [None, pa.py_buffer(bytes(out))])
