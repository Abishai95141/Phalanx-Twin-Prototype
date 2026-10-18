"""Identity-keyed, counter-addressable random streams (AD-15, architecture §11.2 and §15, invariant I8).

Evidence: report §14 "Reproducibility" and "Closing the loop" (one 128-bit root per release; streams
spawned by a fixed key path via SeedSequence spawn keys or Philox, never seed arithmetic; exogenous
randomness keyed by *identity*, not draw order, so forks share the exogenous future); NumPy parallel-RNG
guidance and NEP 19 [TRANSFER: numerical computing, research_notes/.../modelling_methodology.md §RNG];
Random123 counter-based generators [TRANSFER: HPC, Salmon et al. SC11].

**The mapping below is part of the reproducibility contract (``RNG_MAPPING_VERSION``).** Changing any
step changes every draw and must bump the version; ``tests/golden/test_core_rng_golden.py`` pins it.

1. A :class:`KeyPath` is an ordered tuple of typed identity components ``(kind, value)``. Kinds come from
   the fixed vocabulary :data:`KIND_ORDER` and must appear in that order, each at most once.
2. Each component maps to exactly **four uint32 words**: the 16-byte blake2b digest (person
   ``phx.rngkey.v1``) of the UTF-8 bytes ``kind 0x1F type 0x1F value`` (type ``s`` for str, ``i`` for
   int), read little-endian. Fixed width matters: NumPy splits a large spawn-key int into a variable
   number of words, so ``spawn_key=(2**32,)`` and ``(0, 1)`` collide; fixed-width words cannot.
3. A draw unit is addressed by ``(path, tag, index)`` with ``tag`` the variate code (normal=1,
   uniform=2, raw=3, generator=4) and ``index`` a uint64 split into (lo, hi) words. Its generator is
   ``Generator(Philox(SeedSequence(entropy=root, spawn_key=path_words + (tag, lo, hi))))`` with the root
   a 128-bit int (NumPy pads it to the 4-word pool before appending the spawn key).
4. Block ``b`` of a stream is ``block_size`` draws of the declared variate from unit ``(path, tag, b)``.
   Draw ``i`` of the stream is element ``i % block_size`` of block ``i // block_size``. Any draw is
   therefore addressable directly from ``i``, independent of what was drawn before, by whom, or in which
   order streams were created (A5, I8).

Variates use NumPy's ``standard_normal`` (ziggurat), ``random`` and ``random_raw``. NEP 19 guarantees only
``random``/``integers``/``bytes`` across NumPy feature releases, so NumPy is pinned (uv.lock) and the
golden test catches a change.
"""

from __future__ import annotations

import difflib
import enum
import hashlib
import re
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .canonical import PERSON_LEDGER, PERSON_RNG_KEY, canonical_json, digest

RNG_MAPPING_VERSION = 1
BIT_GENERATOR = "Philox"
ROOT_BITS = 128

#: ordered identity vocabulary (architecture §5.3, §15; report §14). Extending it with a new kind does not
#: change existing paths (encoding uses kind names); reordering existing kinds is a breaking change.
KIND_ORDER: tuple[str, ...] = (
    "scenario",
    "base",
    "tail",
    "serial",
    "date",
    "sortie",
    "job",
    "order",
    "subsystem",
    "sensor",
    "component",
    "event",
)
_RANK = {k: i for i, k in enumerate(KIND_ORDER)}
#: kinds whose values are declared stream names (registry namespace) rather than identity data
NAME_KINDS = frozenset({"subsystem", "component"})
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VALUE_RE = re.compile(r"^[A-Za-z0-9._:+\-]+$")


class RngError(ValueError):
    pass


class UndeclaredStreamError(RngError, KeyError):
    """A key path names a (subsystem, component) the registry does not declare (prevents typo-forks)."""

    def __str__(self) -> str:  # KeyError would repr() the message
        return str(self.args[0]) if self.args else ""


class Variate(enum.IntEnum):
    """What a stream produces; the integer is the spawn-key tag (part of the mapping)."""

    NORMAL = 1  # float64 standard normal (ziggurat)
    UNIFORM = 2  # float64 in [0, 1)
    RAW = 3  # uint64 raw Philox output
    GENERATOR = 4  # a fresh numpy Generator per index (event-style draws)


def _check_value(kind: str, value: str | int) -> str | int:
    if kind not in _RANK:
        raise RngError(f"unknown key kind {kind!r}; vocabulary is {KIND_ORDER}")
    if isinstance(value, bool):
        raise RngError(f"{kind}: bool is not a valid identity value")
    if isinstance(value, np.integer):
        value = int(value)
    if isinstance(value, int):
        if value < 0:
            raise RngError(f"{kind}: integer identity values must be >= 0")
        if kind in NAME_KINDS:
            raise RngError(f"{kind}: stream names must be str")
        return value
    if isinstance(value, str):
        rx = _NAME_RE if kind in NAME_KINDS else _VALUE_RE
        if not rx.match(value):
            raise RngError(f"{kind}={value!r} must match {rx.pattern}")
        return value
    raise RngError(f"{kind}: identity values must be str or int, got {type(value).__name__}")


def component_words(kind: str, value: str | int) -> tuple[int, int, int, int]:
    """The four uint32 spawn-key words of one key-path component (mapping step 2)."""
    value = _check_value(kind, value)
    typ = "i" if isinstance(value, int) else "s"
    raw = f"{kind}\x1f{typ}\x1f{value}".encode()
    d = hashlib.blake2b(raw, digest_size=16, person=PERSON_RNG_KEY).digest()
    return tuple(int.from_bytes(d[4 * i : 4 * i + 4], "little") for i in range(4))  # type: ignore[return-value]


@dataclass(frozen=True)
class KeyPath:
    """Ordered typed identity components, e.g. ``KeyPath.of(scenario="S1", tail="KH2011", sortie=3)``."""

    parts: tuple[tuple[str, str | int], ...] = ()

    def __post_init__(self) -> None:
        checked = []
        last = -1
        for kind, value in self.parts:
            v = _check_value(kind, value)
            r = _RANK[kind]
            if r <= last:
                raise RngError(
                    f"key kinds must be unique and in canonical order {KIND_ORDER}; got {self.kinds}"
                )
            last = r
            checked.append((kind, v))
        object.__setattr__(self, "parts", tuple(checked))

    @classmethod
    def of(cls, **components: str | int) -> KeyPath:
        unknown = sorted(set(components) - set(_RANK))
        if unknown:
            raise RngError(f"unknown key kinds {unknown}; vocabulary is {KIND_ORDER}")
        return cls(tuple(sorted(components.items(), key=lambda kv: _RANK[kv[0]])))

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(k for k, _ in self.parts)

    def as_dict(self) -> dict[str, str | int]:
        return dict(self.parts)

    def get(self, kind: str) -> str | int | None:
        return self.as_dict().get(kind)

    def extend(self, **components: str | int) -> KeyPath:
        mine = self.as_dict()
        dup = sorted(set(mine) & set(components))
        if dup:
            raise RngError(f"key kinds {dup} already set in {self}")
        return KeyPath.of(**mine, **components)

    def project(self, kinds: Iterable[str]) -> KeyPath:
        """The sub-path with only ``kinds`` (all must be present)."""
        mine = self.as_dict()
        want = list(kinds)
        missing = [k for k in want if k not in mine]
        if missing:
            raise RngError(f"identity {self} lacks required kinds {missing}")
        return KeyPath.of(**{k: mine[k] for k in want})

    def identity(self) -> KeyPath:
        return KeyPath(tuple(p for p in self.parts if p[0] not in NAME_KINDS))

    def words(self) -> tuple[int, ...]:
        out: list[int] = []
        for kind, value in self.parts:
            out.extend(component_words(kind, value))
        return tuple(out)

    def canonical(self) -> str:
        return "/".join(f"{k}={'i' if isinstance(v, int) else 's'}:{v}" for k, v in self.parts)

    def __str__(self) -> str:
        return self.canonical()


@dataclass(frozen=True)
class StreamDecl:
    """A declared stream template: names (subsystem, component), required identity kinds, variate.

    ``identity`` lists exactly which identity kinds key the stream (in canonical order). A stream keyed by
    ("scenario", "serial") is the same in every sortie; one keyed by ("scenario", "tail", "sortie") is
    fresh per sortie. ``block_size`` is part of the mapping for that stream.
    """

    subsystem: str
    component: str
    identity: tuple[str, ...]
    variate: Variate = Variate.NORMAL
    block_size: int = 4096
    owner: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        for n in (self.subsystem, self.component):
            if not _NAME_RE.match(n):
                raise RngError(f"stream name {n!r} must match {_NAME_RE.pattern}")
        ident = tuple(self.identity)
        bad = [k for k in ident if k not in _RANK or k in NAME_KINDS]
        if bad:
            raise RngError(f"invalid identity kinds {bad}")
        if list(ident) != sorted(ident, key=lambda k: _RANK[k]) or len(set(ident)) != len(ident):
            raise RngError(f"identity kinds must be unique and in canonical order: {ident}")
        object.__setattr__(self, "identity", ident)
        object.__setattr__(self, "variate", Variate(self.variate))
        if not isinstance(self.block_size, int) or isinstance(self.block_size, bool) or self.block_size < 1:
            raise RngError("block_size must be a positive int")

    @property
    def key(self) -> tuple[str, str]:
        return (self.subsystem, self.component)

    def describe(self) -> dict[str, Any]:
        return {
            "subsystem": self.subsystem,
            "component": self.component,
            "identity": list(self.identity),
            "variate": self.variate.name.lower(),
            "block_size": self.block_size,
            "owner": self.owner,
            "description": self.description,
        }


class StreamRegistry:
    """The declared stream namespace. Undeclared (subsystem, component) names are errors."""

    def __init__(self, decls: Iterable[StreamDecl] = ()) -> None:
        self._decls: dict[tuple[str, str], StreamDecl] = {}
        for d in decls:
            self.declare(d)

    def declare(self, decl: StreamDecl) -> StreamDecl:
        old = self._decls.get(decl.key)
        if old is not None and old != decl:
            raise RngError(f"conflicting declarations for stream {decl.key}: {old} vs {decl}")
        self._decls[decl.key] = decl
        return decl

    def lookup(self, subsystem: str, component: str) -> StreamDecl:
        try:
            return self._decls[(subsystem, component)]
        except KeyError:
            names = [f"{s}.{c}" for s, c in sorted(self._decls)]
            near = difflib.get_close_matches(f"{subsystem}.{component}", names, n=3)
            raise UndeclaredStreamError(
                f"stream {subsystem}.{component} is not declared"
                + (f" (did you mean {near}?)" if near else "")
            ) from None

    def validate_path(self, path: KeyPath) -> StreamDecl:
        d = path.as_dict()
        if "subsystem" not in d or "component" not in d:
            raise RngError(f"key path {path} must name a subsystem and a component")
        decl = self.lookup(str(d["subsystem"]), str(d["component"]))
        ident = path.identity().kinds
        if ident != decl.identity:
            raise RngError(
                f"stream {decl.subsystem}.{decl.component} is keyed by {decl.identity}, got {ident}"
            )
        return decl

    def __contains__(self, key: tuple[str, str]) -> bool:
        return key in self._decls

    def __iter__(self):
        return iter(sorted(self._decls.values(), key=lambda d: d.key))

    def __len__(self) -> int:
        return len(self._decls)

    def table(self) -> list[dict[str, Any]]:
        return [d.describe() for d in self]

    def digest(self) -> str:
        return digest(
            canonical_json({"mapping": RNG_MAPPING_VERSION, "streams": self.table()}), PERSON_RNG_KEY
        )


def _check_root(root: int) -> int:
    if isinstance(root, bool) or not isinstance(root, int):
        raise RngError("root entropy must be an int")
    if not (0 <= root < 2**ROOT_BITS):
        raise RngError("root entropy must be a 128-bit non-negative integer")
    return root


def _unit_generator(root: int, prefix: tuple[int, ...], tag: int, index: int) -> np.random.Generator:
    if isinstance(index, bool) or index < 0 or index >= 2**64:
        raise RngError(f"draw-unit index {index} outside [0, 2**64)")
    index = int(index)
    ss = np.random.SeedSequence(entropy=root, spawn_key=(*prefix, tag, index & 0xFFFFFFFF, index >> 32))
    return np.random.Generator(np.random.Philox(ss))


@dataclass
class DrawLedger:
    """Validation-mode record of every draw handed out (for the CRN audit). A pure observer."""

    entries: list[tuple[str, str, int, int, bytes]] = field(default_factory=list)

    def record(self, path: KeyPath, variate: Variate, start: int, values: np.ndarray | None) -> None:
        if values is None:
            self.entries.append((path.canonical(), variate.name, int(start), 0, b""))
        else:
            v = np.ascontiguousarray(values)
            self.entries.append((path.canonical(), variate.name, int(start), int(v.size), v.tobytes()))

    def consumed(self) -> dict[str, dict[int, bytes]]:
        """Per path: absolute draw index -> value bytes (generator units: index -> b'')."""
        out: dict[str, dict[int, bytes]] = {}
        for path, variate, start, count, raw in self.entries:
            m = out.setdefault(f"{path}#{variate}", {})
            if count == 0:
                m[start] = b""
                continue
            item = len(raw) // count
            for j in range(count):
                m[start + j] = raw[j * item : (j + 1) * item]
        return out

    def digest(self) -> str:
        c = self.consumed()
        payload = canonical_json({p: sorted(c[p]) for p in sorted(c)})
        vals = b"".join(c[p][i] for p in sorted(c) for i in sorted(c[p]))
        return digest(payload + vals, PERSON_LEDGER)


@dataclass(frozen=True)
class CrnReport:
    identical: tuple[str, ...]
    consumption_differs: tuple[str, ...]
    values_differ: tuple[str, ...]
    only_in_a: tuple[str, ...]
    only_in_b: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (self.consumption_differs or self.values_differ or self.only_in_a or self.only_in_b)

    def diverged(self) -> tuple[str, ...]:
        return tuple(
            sorted({*self.consumption_differs, *self.values_differ, *self.only_in_a, *self.only_in_b})
        )


def crn_audit(a: DrawLedger, b: DrawLedger) -> CrnReport:
    """Compare the exogenous draws consumed by two branches, stream by stream (I8).

    A stream passes when both branches consumed exactly the same draw indices and saw identical values.
    "consumption differs" exposes modules whose draw *indices* depend on branch-dependent state.
    """
    ca, cb = a.consumed(), b.consumed()
    ident, cons, vals = [], [], []
    for p in sorted(set(ca) & set(cb)):
        if set(ca[p]) != set(cb[p]):
            cons.append(p)
        elif any(ca[p][i] != cb[p][i] for i in ca[p]):
            vals.append(p)
        else:
            ident.append(p)
    return CrnReport(
        tuple(ident),
        tuple(cons),
        tuple(vals),
        tuple(sorted(set(ca) - set(cb))),
        tuple(sorted(set(cb) - set(ca))),
    )


class Stream:
    """A validated stream: counter-addressable draws for one key path (pure function of root and path)."""

    def __init__(self, service: RngService, path: KeyPath, decl: StreamDecl) -> None:
        self.service = service
        self.path = path
        self.decl = decl
        self._prefix = path.words()
        self._cache: OrderedDict[int, np.ndarray] = OrderedDict()

    @property
    def variate(self) -> Variate:
        return self.decl.variate

    @property
    def block_size(self) -> int:
        return self.decl.block_size

    def spawn_key(self, index: int) -> tuple[int, ...]:
        return (*self._prefix, int(self.variate), int(index) & 0xFFFFFFFF, int(index) >> 32)

    def _require_block_variate(self) -> None:
        if self.variate == Variate.GENERATOR:
            raise RngError(f"stream {self.path} is a GENERATOR stream; use generator(index)")

    def _block(self, b: int) -> np.ndarray:
        hit = self._cache.get(b)
        if hit is not None:
            self._cache.move_to_end(b)
            return hit
        g = _unit_generator(self.service.root, self._prefix, int(self.variate), b)
        n = self.block_size
        if self.variate == Variate.NORMAL:
            arr = g.standard_normal(n)
        elif self.variate == Variate.UNIFORM:
            arr = g.random(n)
        else:
            arr = g.bit_generator.random_raw(n).astype(np.uint64, copy=False)
        arr.flags.writeable = False
        self._cache[b] = arr
        if len(self._cache) > self.service.cache_blocks:
            self._cache.popitem(last=False)
        return arr

    def block(self, b: int) -> np.ndarray:
        """Block ``b`` (read-only), independent of anything drawn before."""
        self._require_block_variate()
        arr = self._block(int(b))
        if self.service.ledger is not None:
            self.service.ledger.record(self.path, self.variate, int(b) * self.block_size, arr)
        return arr

    def draws(self, start: int, count: int) -> np.ndarray:
        """Draws ``start .. start+count-1`` of the stream (a new array)."""
        self._require_block_variate()
        if start < 0 or count < 0:
            raise RngError("start and count must be >= 0")
        bs = self.block_size
        dtype = np.uint64 if self.variate == Variate.RAW else np.float64
        out = np.empty(count, dtype=dtype)
        pos = 0
        while pos < count:
            i = start + pos
            b, off = divmod(i, bs)
            m = min(bs - off, count - pos)
            out[pos : pos + m] = self._block(b)[off : off + m]
            pos += m
        if self.service.ledger is not None:
            self.service.ledger.record(self.path, self.variate, start, out)
        return out

    def take(self, position: int, count: int) -> tuple[np.ndarray, int]:
        """Sequential use with an explicit cursor (store ``position`` in module state)."""
        return self.draws(position, count), position + count

    def generator(self, index: int = 0) -> np.random.Generator:
        """A fresh Generator for unit ``index`` (GENERATOR streams), e.g. one per event or job."""
        if self.variate != Variate.GENERATOR:
            raise RngError(f"stream {self.path} is {self.variate.name}; generator() needs a GENERATOR stream")
        if self.service.ledger is not None:
            self.service.ledger.record(self.path, self.variate, int(index), None)
        return _unit_generator(self.service.root, self._prefix, int(Variate.GENERATOR), int(index))


class RngService:
    """Root entropy + registry -> validated streams. Holds no draw state (only a pure memo cache)."""

    def __init__(
        self, root: int, registry: StreamRegistry, *, ledger: DrawLedger | None = None, cache_blocks: int = 8
    ) -> None:
        self.root = _check_root(root)
        self.registry = registry
        self.ledger = ledger
        self.cache_blocks = cache_blocks
        self._streams: dict[KeyPath, Stream] = {}

    @property
    def root_hex(self) -> str:
        return f"{self.root:032x}"

    def stream(self, path: KeyPath) -> Stream:
        s = self._streams.get(path)
        if s is None:
            decl = self.registry.validate_path(path)
            s = Stream(self, path, decl)
            self._streams[path] = s
        return s

    def generator(self, path: KeyPath, index: int = 0) -> np.random.Generator:
        """``stream(key_path) -> Generator`` of the brief: unit ``index`` of a GENERATOR stream."""
        return self.stream(path).generator(index)

    def block(self, path: KeyPath, block_index: int) -> np.ndarray:
        return self.stream(path).block(block_index)

    def draws(self, path: KeyPath, start: int, count: int) -> np.ndarray:
        return self.stream(path).draws(start, count)

    def scope(self, identity: KeyPath) -> Keys:
        return Keys(self, identity)

    def describe(self) -> dict[str, Any]:
        return {
            "mapping_version": RNG_MAPPING_VERSION,
            "bit_generator": BIT_GENERATOR,
            "root_hex": self.root_hex,
            "registry_digest": self.registry.digest(),
            "numpy": np.__version__,
        }


class Keys:
    """Identity-scoped stream factory handed to a module (``init(params, keys)``).

    ``stream(subsystem, component, **extra)`` keys the stream by the declared identity kinds only,
    projected from this scope's identity plus ``extra`` (e.g. the currently installed ``serial``).
    """

    def __init__(self, service: RngService, identity: KeyPath) -> None:
        if any(k in NAME_KINDS for k in identity.kinds):
            raise RngError("a Keys scope holds identity only (no subsystem/component)")
        self.service = service
        self.identity = identity

    def stream(self, subsystem: str, component: str, **extra: str | int) -> Stream:
        decl = self.service.registry.lookup(subsystem, component)
        ident = self.identity.as_dict()
        ident.update({k: v for k, v in extra.items()})
        missing = [k for k in decl.identity if k not in ident]
        if missing:
            raise RngError(f"stream {subsystem}.{component} needs identity {missing} (have {sorted(ident)})")
        path = KeyPath.of(**{k: ident[k] for k in decl.identity}, subsystem=subsystem, component=component)
        return self.service.stream(path)

    def child(self, **components: str | int) -> Keys:
        return Keys(self.service, self.identity.extend(**components))


# ------------------------------------------------------------------------- sequential Generator state codec


def generator_state_tree(gen: np.random.Generator) -> dict[str, np.ndarray]:
    """Exact state (counter position) of a Philox Generator as a flat array tree (for module state)."""
    st = gen.bit_generator.state
    if st["bit_generator"] != "Philox":
        raise RngError("only Philox generators are supported")
    return {
        "philox_counter": np.asarray(st["state"]["counter"], dtype=np.uint64).copy(),
        "philox_key": np.asarray(st["state"]["key"], dtype=np.uint64).copy(),
        "philox_buffer": np.asarray(st["buffer"], dtype=np.uint64).copy(),
        "philox_buffer_pos": np.array(st["buffer_pos"], dtype=np.int64),
        "philox_has_uint32": np.array(st["has_uint32"], dtype=np.int64),
        "philox_uinteger": np.array(st["uinteger"], dtype=np.uint64),
    }


def generator_from_state_tree(tree: Mapping[str, np.ndarray]) -> np.random.Generator:
    bg = np.random.Philox(0)
    bg.state = {
        "bit_generator": "Philox",
        "state": {"counter": np.array(tree["philox_counter"]), "key": np.array(tree["philox_key"])},
        "buffer": np.array(tree["philox_buffer"]),
        "buffer_pos": int(tree["philox_buffer_pos"]),
        "has_uint32": int(tree["philox_has_uint32"]),
        "uinteger": int(tree["philox_uinteger"]),
    }
    return np.random.Generator(bg)
