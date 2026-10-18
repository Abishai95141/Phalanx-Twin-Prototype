"""Copy-on-write access to an operations-layer module state (pure ``on_event`` handlers).

Operations-layer state (M18, M21) is a flat dict of NumPy arrays (core contract) of two kinds:

- **columnar tables** (serials, tails): fixed-dtype arrays, variable leading dimension;
- **documents**: small nested structures (open jobs, demands, truth faults, order registry) stored as
  canonical JSON bytes in a ``uint8[None]`` array (sorted keys, ASCII, no NaN; floats round-trip exactly
  through repr).

Both are explicit, complete and canonically encoded, so ``get_state``/``set_state`` round-trip bit for bit and
snapshots are content-hashable (I2, AD-36). Handlers never mutate their input: :class:`Cow` copies an array
the first time it is written and re-encodes only the documents that were touched.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import numpy as np

from phalanx.core.canonical import canonical_json

State = dict[str, np.ndarray]


def encode_doc(obj: Any) -> np.ndarray:
    """Canonical JSON bytes of a document made of JSON-native values only (dict with str keys, list, str, int,
    float, bool, None). Same bytes as ``core.canonical.canonical_json`` for such values (tested), via the C
    encoder; anything else (e.g. a NumPy scalar) raises TypeError instead of being silently converted."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return np.frombuffer(text.encode("ascii"), dtype=np.uint8).copy()


def encode_doc_reference(obj: Any) -> np.ndarray:
    """Reference encoding through ``core.canonical`` (slower; used by the equivalence test)."""
    return np.frombuffer(canonical_json(obj), dtype=np.uint8).copy()


def decode_doc(arr: np.ndarray) -> Any:
    return json.loads(np.asarray(arr, dtype=np.uint8).tobytes().decode("ascii"))


class Cow:
    """Copy-on-write view of a module state for one handler call."""

    def __init__(self, state: Mapping[str, np.ndarray]):
        self._s = state
        self._new: dict[str, np.ndarray] = {}
        self._docs: dict[str, Any] = {}
        self._dirty: set[str] = set()

    # arrays
    def a(self, name: str) -> np.ndarray:
        """Read-only access (do not write to the result)."""
        v = self._new.get(name)
        return self._s[name] if v is None else v

    def w(self, name: str) -> np.ndarray:
        """Writable copy (made once per handler call)."""
        v = self._new.get(name)
        if v is None:
            v = np.array(self._s[name], copy=True)
            self._new[name] = v
        return v

    def put(self, name: str, value: np.ndarray) -> None:
        self._new[name] = value

    # documents
    def doc(self, name: str) -> Any:
        """Decoded document (a fresh object; call :meth:`touch` after changing it)."""
        if name not in self._docs:
            self._docs[name] = decode_doc(self._s[name])
        return self._docs[name]

    def touch(self, name: str) -> None:
        self.doc(name)
        self._dirty.add(name)

    def commit(self) -> State:
        out = dict(self._s)
        out.update(self._new)
        for name in sorted(self._dirty):
            out[name] = encode_doc(self._docs[name])
        return out
