"""Canonical byte encodings and content hashes used across the kernel.

Rules (RULES.md rule 5; architecture §15):
- Content hashes are blake2b with an explicit ``person`` string per object family (domain separation),
  never the builtin ``hash()`` (process-salted).
- JSON that is hashed or written to manifests is canonical: sorted keys, no whitespace, ASCII only, no NaN.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

# blake2b personalisation strings (<= 16 bytes). Changing any of these changes every hash of that family.
PERSON_STATE = b"phx.state.v1"
PERSON_PARAMS = b"phx.params.v1"
PERSON_SNAPSHOT = b"phx.snapshot.v1"
PERSON_CONFIG = b"phx.config.v1"
PERSON_EVENTS = b"phx.events.v1"
PERSON_RNG_KEY = b"phx.rngkey.v1"
PERSON_TRACE = b"phx.trace.v1"
PERSON_MANIFEST = b"phx.manifest.v1"
PERSON_LEDGER = b"phx.ledger.v1"
PERSON_DICTIONARY = b"phx.dict.v1"  # M01 dictionary content hash (W0.3; registered at W0.X)


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes: sorted keys, compact separators, ASCII, NaN/inf rejected."""
    return json.dumps(
        _normalise(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _normalise(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        out = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(f"canonical JSON keys must be str, got {type(k).__name__}")
            out[k] = _normalise(v)
        return out
    if isinstance(obj, str | bytes):
        if isinstance(obj, bytes):
            raise TypeError("bytes are not JSON; hex-encode them first")
        return obj
    if isinstance(obj, Sequence):
        return [_normalise(v) for v in obj]
    if isinstance(obj, bool) or obj is None or isinstance(obj, int | float):
        return obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, set | frozenset):
        raise TypeError("sets have no canonical order; pass a sorted list")
    raise TypeError(f"not canonically JSON-encodable: {type(obj).__name__}")


def digest(data: bytes, person: bytes, size: int = 32) -> str:
    """blake2b hex digest with domain separation."""
    return hashlib.blake2b(data, digest_size=size, person=person).hexdigest()


def digest_bytes(data: bytes, person: bytes, size: int = 32) -> bytes:
    return hashlib.blake2b(data, digest_size=size, person=person).digest()


def length_prefixed(parts: Sequence[bytes]) -> bytes:
    """Unambiguous concatenation: each part prefixed by its 8-byte little-endian length."""
    return b"".join(len(p).to_bytes(8, "little") + p for p in parts)
