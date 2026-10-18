"""World snapshot I/O (architecture §11.2; M22 builds copy-on-write forks on top of these primitives).

A snapshot is self-describing, versioned and content-hashed. It holds everything a run needs to continue
bit-for-bit from step ``k`` (I1, I2, A3):

- every module's state (``get_state`` bytes, in Gauss-Seidel order);
- the held port values (outputs as of the end of step k-1: needed by one-frame-delayed edges, rate-group
  zero-order holds and feed-through outputs, which are *not* in general a function of module state);
- the event queue (pending events and the next insertion sequence number);
- the order log injected so far;
- RNG identity: mapping version, BitGenerator, root entropy, stream-registry digest, NumPy version.
  (Stream "counters" are absolute draw indices kept in module state: draws are addressed by index.)
- config hash, dictionary hash, order-log hash, parent snapshot id.

Layout: ``b"PHXSNAP1"`` + length-prefixed parts ``[header JSON, held tree, queue, order log,
module states...]``. ``snapshot_id`` = blake2b-256 of the bytes (person ``phx.snapshot.v1``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .canonical import PERSON_SNAPSHOT, PERSON_STATE, canonical_json, digest, length_prefixed
from .events import Event, EventQueue, event_log_digest
from .scheduler import System, World
from .state import decode_tree, encode_tree

SNAPSHOT_MAGIC = b"PHXSNAP1"
SNAPSHOT_FORMAT = 1


class SnapshotError(ValueError):
    pass


def _split_parts(data: bytes, pos: int) -> list[bytes]:
    parts = []
    while pos < len(data):
        n = int.from_bytes(data[pos : pos + 8], "little")
        if pos + 8 + n > len(data):
            raise SnapshotError("truncated snapshot")
        parts.append(data[pos + 8 : pos + 8 + n])
        pos += 8 + n
    return parts


def snapshot(system: System, world: World, *, parent: str = "") -> bytes:
    """Serialise ``world`` (a boundary before step ``world.k``) to canonical, content-hashable bytes."""
    held_tree = {"/".join(name.rsplit(".", 1)): v for name, v in world.held.items()}
    held = encode_tree(held_tree, kind="held_outputs", name="held", version=1)
    queue = world.queue.get_state()
    olog = length_prefixed([e.encode() for e in world.order_log])
    mods = []
    blobs = []
    for mid in system.order:
        m = system.modules[mid]
        b = m.get_state(world.states[mid])
        blobs.append(b)
        mods.append(
            {
                "id": mid,
                "version": m.version,
                "schema": m.state_schema.name,
                "schema_version": m.state_schema.version,
                "digest": digest(b, PERSON_STATE),
            }
        )
    header = {
        "format": SNAPSHOT_FORMAT,
        "k": world.k,
        "t_ns": world.t_ns,
        "config_hash": system.config_hash,
        "dict_hash": system.dict_hash,
        "rng": system.rng.describe(),
        "modules": mods,
        "held_digest": digest(held, PERSON_STATE),
        "queue_digest": world.queue.digest(),
        "order_log_hash": event_log_digest(world.order_log),
        "n_orders": len(world.order_log),
        "parent": parent,
    }
    return SNAPSHOT_MAGIC + length_prefixed([canonical_json(header), held, queue, olog, *blobs])


def snapshot_id(data: bytes) -> str:
    return digest(data, PERSON_SNAPSHOT)


@dataclass(frozen=True)
class SnapshotInfo:
    """Parsed snapshot (no System needed): header plus the raw parts."""

    header: dict[str, Any]
    held: bytes
    queue: bytes
    order_log: bytes
    module_states: dict[str, bytes]
    id: str

    @property
    def k(self) -> int:
        return int(self.header["k"])


def read_snapshot(data: bytes) -> SnapshotInfo:
    if data[: len(SNAPSHOT_MAGIC)] != SNAPSHOT_MAGIC:
        raise SnapshotError("not a Phalanx world snapshot")
    parts = _split_parts(data, len(SNAPSHOT_MAGIC))
    if len(parts) < 4:
        raise SnapshotError("snapshot is missing parts")
    header = json.loads(parts[0].decode("ascii"))
    if header.get("format") != SNAPSHOT_FORMAT:
        raise SnapshotError(f"unsupported snapshot format {header.get('format')}")
    mods = header["modules"]
    if len(parts) != 4 + len(mods):
        raise SnapshotError("module count does not match the header")
    states = {}
    for meta, blob in zip(mods, parts[4:], strict=True):
        if digest(blob, PERSON_STATE) != meta["digest"]:
            raise SnapshotError(f"module {meta['id']}: state digest mismatch (corrupt snapshot)")
        states[meta["id"]] = blob
    if digest(parts[1], PERSON_STATE) != header["held_digest"]:
        raise SnapshotError("held-output digest mismatch")
    return SnapshotInfo(header, parts[1], parts[2], parts[3], states, snapshot_id(data))


def restore(system: System, data: bytes, *, strict: bool = True) -> World:
    """Rebuild the world in ``data`` for ``system`` (fresh module objects are fine).

    ``strict`` (default) requires the same config hash, dictionary hash and RNG identity (mapping, root,
    registry, NumPy version): anything else would not continue bit-for-bit. Non-strict restore (e.g. an
    ensemble fork with a new root, or a fork with changed parameters) is M22's decision and is explicit.
    """
    info = read_snapshot(data)
    h = info.header
    rng_now = system.rng.describe()
    if strict:
        if h["config_hash"] != system.config_hash:
            raise SnapshotError("config hash differs from the restoring system")
        if h["dict_hash"] != system.dict_hash:
            raise SnapshotError("dictionary hash differs")
        if h["rng"] != rng_now:
            raise SnapshotError(f"RNG identity differs: snapshot {h['rng']} vs system {rng_now}")
    ids = [m["id"] for m in h["modules"]]
    if ids != list(system.order):
        raise SnapshotError(f"module order {ids} != system order {list(system.order)}")
    states = {}
    for meta in h["modules"]:
        m = system.modules[meta["id"]]
        if (meta["schema"], meta["schema_version"]) != (m.state_schema.name, m.state_schema.version):
            raise SnapshotError(f"{m.id}: schema {meta['schema']} v{meta['schema_version']} not restorable")
        states[m.id] = m.set_state(info.module_states[m.id])
    held_tree = decode_tree(info.held, kind="held_outputs").tree
    held = {".".join(name.rsplit("/", 1)): v for name, v in held_tree.items()}
    if sorted(held) != sorted(system.output_ports()):
        raise SnapshotError("held outputs do not match the system's output ports")
    queue = EventQueue.from_state(info.queue)
    order_log = tuple(Event.decode(p) for p in _split_parts(info.order_log, 0))
    if event_log_digest(order_log) != h["order_log_hash"]:
        raise SnapshotError("order-log hash mismatch")
    return World(int(h["k"]), states, held, queue, order_log)
