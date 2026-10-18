"""Identity-keyed, counter-addressable RNG blocks (AD-15), backend-independent.

Mirrors the W0.2 kernel API `block(key_path, block_index, size)` so the benchmark tests the pattern the build will
use: NumPy SeedSequence(entropy=root, spawn_key=digest(key path) + (block_index,)) -> Philox -> standard_normal.
A block depends only on (root, key path, block index), never on what was drawn before (CRN; forks; snapshots
store only the block index and the offset inside the block).

The component -> integer mapping here (blake2b-64 of the canonical UTF-8 repr -> two uint32 words) is local to
the benchmark; W0.2 owns the build's pinned mapping.
"""

from __future__ import annotations

import hashlib

import numpy as np

ROOT_SEED = 0x5048414C414E585F57303620424E4348  # 128-bit benchmark root ("PHALANX_W06 BNCH")


def _words(component) -> tuple[int, int]:
    d = hashlib.blake2b(repr(component).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(d[:4], "little"), int.from_bytes(d[4:], "little")


def spawn_key(key_path: tuple) -> tuple[int, ...]:
    out: list[int] = []
    for c in key_path:
        out.extend(_words(c))
    return tuple(out)


def generator(key_path: tuple, block_index: int | None = None) -> np.random.Generator:
    sk = spawn_key(key_path) + (() if block_index is None else (int(block_index),))
    return np.random.Generator(np.random.Philox(np.random.SeedSequence(ROOT_SEED, spawn_key=sk)))


def normal_block(key_path: tuple, block_index: int, shape) -> np.ndarray:
    """Standard normals of a keyed block (float64, C order)."""
    return generator(key_path, block_index).standard_normal(shape)


def unit_key(unit: int, sortie: str = "S0001") -> tuple:
    return ("bench", f"tail{unit:04d}", f"eng{unit:04d}", sortie)


def disturbance_key(unit: int) -> tuple:
    return (*unit_key(unit), "M03.process_disturbance", "engine")


def noise_for(units: list[int] | range, k0: int, n: int, block: int) -> np.ndarray:
    """Innovations float64[U, n, 2] for truth steps k0..k0+n-1, assembled from keyed blocks of `block` steps."""
    out = np.empty((len(units), n, 2))
    for ui, u in enumerate(units):
        key = disturbance_key(u)
        k = k0
        while k < k0 + n:
            b, off = divmod(k, block)
            take = min(block - off, k0 + n - k)
            out[ui, k - k0 : k - k0 + take] = normal_block(key, b, (block, 2))[off : off + take]
            k += take
    return out
