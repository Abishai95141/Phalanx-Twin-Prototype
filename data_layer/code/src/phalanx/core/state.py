"""Explicit module state: flat typed trees of NumPy arrays and their canonical, versioned byte encoding.

Architecture §5.5 (``get_state`` / ``set_state``: complete, versioned), invariant I2 (no hidden state),
§11.2 (snapshots are content-hashed). Backend-neutral by construction (AD-22 is open):

- A state is a **flat** ``dict[str, ndarray]`` (0-d arrays for scalars). A dict of arrays is a JAX pytree
  as-is, and a Numba kernel takes the arrays as arguments.
- Encoding: ``MAGIC | format u8 | header_len u32 LE | canonical-JSON header | little-endian C-order
  raw buffers`` in sorted field order. No pickle; no zip container (``np.savez`` bytes embed timestamps).
  The header carries the tree kind, schema name and version, and per field: name, dtype, shape, offset,
  nbytes. Raw bytes preserve every float bit pattern (NaN payloads, -0.0).
- Content hash: blake2b-256 of the encoded bytes (person ``phx.state.v1``).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from .canonical import PERSON_STATE, canonical_json, digest

State = dict[str, np.ndarray]

MAGIC = b"PHXT"
FORMAT_VERSION = 1
_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
# general tree keys (held-output trees use "module_id/port")
_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)*$")
_ALLOWED_KINDS = frozenset("biufcSU")


class StateError(ValueError):
    """A state tree does not match its schema, or bytes are not a valid encoding."""


def _wire_dtype(d: np.dtype) -> np.dtype:
    d = np.dtype(d)
    if d.byteorder == "|":
        return d
    return d.newbyteorder("<")


def canonical_dtype(dt: np.dtype | str | type) -> np.dtype:
    """Little-endian, non-object, non-structured dtype used on the wire (kinds b i u f c S U)."""
    d = np.dtype(dt)
    if d.kind not in _ALLOWED_KINDS or d.fields is not None or d.subdtype is not None:
        raise StateError(f"dtype {d!r} is not allowed in state (kinds {''.join(sorted(_ALLOWED_KINDS))})")
    return _wire_dtype(d)


@dataclass(frozen=True)
class Field:
    """One state field: name, dtype and shape (``None`` marks a variable-length dimension)."""

    name: str
    dtype: str
    shape: tuple[int | None, ...] = ()

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name):
            raise StateError(f"field name {self.name!r} must match {_NAME_RE.pattern}")
        object.__setattr__(self, "dtype", canonical_dtype(self.dtype).str)
        shape = tuple(self.shape)
        for s in shape:
            if s is not None and (not isinstance(s, int) or isinstance(s, bool) or s < 0):
                raise StateError(f"field {self.name}: bad dimension {s!r}")
        object.__setattr__(self, "shape", shape)

    def matches(self, a: np.ndarray) -> str | None:
        """Return a problem description, or None if ``a`` conforms."""
        if _wire_dtype(a.dtype).str != self.dtype:
            return f"{self.name}: dtype {a.dtype.str} != {self.dtype}"
        if a.ndim != len(self.shape) or any(
            s is not None and s != d for s, d in zip(self.shape, a.shape, strict=True)
        ):
            return f"{self.name}: shape {a.shape} != {self.shape}"
        return None


@dataclass(frozen=True)
class StateSchema:
    """Declared state layout of a module (or other stateful kernel object): name, version, fields."""

    name: str
    version: int
    fields: tuple[Field, ...]

    def __post_init__(self) -> None:
        names = [f.name for f in self.fields]
        if len(set(names)) != len(names):
            raise StateError(f"schema {self.name}: duplicate field names")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 0:
            raise StateError("schema version must be a non-negative int")
        object.__setattr__(self, "fields", tuple(sorted(self.fields, key=lambda f: f.name)))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def problems(self, tree: Mapping[str, Any]) -> list[str]:
        out: list[str] = []
        missing = sorted(set(self.names) - set(tree))
        extra = sorted(set(tree) - set(self.names))
        if missing:
            out.append(f"missing fields {missing}")
        if extra:
            out.append(f"undeclared fields {extra}")
        for f in self.fields:
            if f.name in tree:
                v = tree[f.name]
                if not isinstance(v, np.ndarray | np.generic) and not hasattr(v, "__array__"):
                    out.append(f"{f.name}: {type(v).__name__} is not an array (use 0-d arrays for scalars)")
                    continue
                p = f.matches(np.asarray(v))
                if p:
                    out.append(p)
        return out

    def validate(self, tree: Mapping[str, Any]) -> None:
        p = self.problems(tree)
        if p:
            raise StateError(f"state does not match schema {self.name} v{self.version}: " + "; ".join(p))

    def make(self, **values: Any) -> State:
        """Build a conforming state from Python/NumPy values (each cast to the declared dtype)."""
        tree = {
            f.name: np.array(values[f.name], dtype=np.dtype(f.dtype)) for f in self.fields if f.name in values
        }
        self.validate(tree)
        return tree

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "fields": [[f.name, f.dtype, [s if s is not None else -1 for s in f.shape]] for f in self.fields],
        }


def encode_tree(tree: Mapping[str, Any], *, kind: str, name: str, version: int) -> bytes:
    """Canonical bytes for a flat array tree (sorted keys, LE raw buffers, versioned header)."""
    entries = []
    payload = []
    offset = 0
    for key in sorted(tree):
        if not _KEY_RE.match(key):
            raise StateError(f"tree key {key!r} is not a valid key")
        a = np.asarray(tree[key])
        wd = canonical_dtype(a.dtype)
        buf = np.ascontiguousarray(a, dtype=wd).tobytes(order="C")
        entries.append([key, wd.str, list(a.shape), offset, len(buf)])
        payload.append(buf)
        offset += len(buf)
    header = canonical_json({"kind": kind, "name": name, "version": int(version), "fields": entries})
    return MAGIC + bytes([FORMAT_VERSION]) + len(header).to_bytes(4, "little") + header + b"".join(payload)


@dataclass(frozen=True)
class DecodedTree:
    kind: str
    name: str
    version: int
    tree: State


def decode_tree(data: bytes, *, kind: str | None = None) -> DecodedTree:
    """Inverse of :func:`encode_tree`; returns writable arrays that do not alias ``data``."""
    mv = memoryview(data)
    if bytes(mv[:4]) != MAGIC:
        raise StateError("bad magic: not a Phalanx state tree")
    if mv[4] != FORMAT_VERSION:
        raise StateError(f"unsupported state format version {mv[4]}")
    hlen = int.from_bytes(mv[5:9], "little")
    try:
        header = json.loads(bytes(mv[9 : 9 + hlen]).decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise StateError(f"corrupt header: {e}") from e
    if kind is not None and header["kind"] != kind:
        raise StateError(f"expected a {kind!r} tree, got {header['kind']!r}")
    base = 9 + hlen
    tree: State = {}
    end = base
    for key, dstr, shape, off, nb in header["fields"]:
        d = np.dtype(dstr)
        count = int(np.prod(shape)) if shape else 1
        if count * d.itemsize != nb:
            raise StateError(f"field {key}: size mismatch")
        a = np.frombuffer(mv[base + off : base + off + nb], dtype=d, count=count).reshape(shape).copy()
        tree[key] = a
        end = max(end, base + off + nb)
    if end != len(data):
        raise StateError("trailing or missing payload bytes")
    if encode_tree(tree, kind=header["kind"], name=header["name"], version=header["version"]) != bytes(data):
        raise StateError("bytes are not in canonical form")
    return DecodedTree(header["kind"], header["name"], int(header["version"]), tree)


def tree_digest(tree: Mapping[str, Any], *, kind: str = "tree", name: str = "", version: int = 0) -> str:
    return digest(encode_tree(tree, kind=kind, name=name, version=version), PERSON_STATE)


def trees_equal(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """Bitwise equality of two flat trees (dtype, shape and raw bytes; NaN-safe)."""
    if sorted(a) != sorted(b):
        return False
    for k in a:
        x, y = np.asarray(a[k]), np.asarray(b[k])
        if x.dtype != y.dtype or x.shape != y.shape:
            return False
        if np.ascontiguousarray(x).tobytes() != np.ascontiguousarray(y).tobytes():
            return False
    return True


def freeze(tree: Mapping[str, Any]) -> State:
    """Read-only views of every array (validation mode: in-place mutation of state then raises)."""
    out: State = {}
    for k, v in tree.items():
        a = np.asarray(v).view()
        a.flags.writeable = False
        out[k] = a
    return out


def copy_tree(tree: Mapping[str, Any]) -> State:
    return {k: np.array(v, copy=True) for k, v in tree.items()}


def fields_from_tree(tree: Mapping[str, Any], variable: Iterable[str] = ()) -> tuple[Field, ...]:
    """Helper: derive a schema field list from an example tree (``variable`` names get a None leading dim)."""
    var = set(variable)
    out = []
    for k in sorted(tree):
        a = np.asarray(tree[k])
        shape: tuple[int | None, ...] = tuple(a.shape)
        if k in var and shape:
            shape = (None, *shape[1:])
        out.append(Field(k, a.dtype.str, shape))
    return tuple(out)
