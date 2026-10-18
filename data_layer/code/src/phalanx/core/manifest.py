"""Run manifest (architecture §15; report §14 "Manifests"; NASA-STD-7009B configuration-record practice).

Per run: git commit, config hash, dictionary hash, data hashes, library versions, backend, BitGenerator,
stream table, order-log hash, and the Numba cache key / package source digest (``numba_cache.py``).
Deterministic JSON (sorted keys, ASCII) and **no wall-clock time**: two manifests of the same run on the
same platform are byte-identical. The git commit is passed in, or read
with ``git rev-parse HEAD`` (plus a dirty flag from ``git status --porcelain``).
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .canonical import PERSON_MANIFEST, canonical_json, digest
from .events import QUEUE_FORMAT_VERSION
from .numba_cache import numba_cache_status
from .rng import BIT_GENERATOR, RNG_MAPPING_VERSION
from .scheduler import System
from .snapshot import SNAPSHOT_FORMAT
from .state import FORMAT_VERSION as STATE_FORMAT_VERSION

MANIFEST_VERSION = 2  # v2 (W0.2 follow-up): + numba_cache (source digest and cache key)
#: runtime libraries whose versions can change results (pinned in uv.lock)
LIBRARIES: tuple[str, ...] = (
    "numpy",
    "scipy",
    "pint",
    "numba",
    "llvmlite",
    "jax",
    "jaxlib",
    "pyarrow",
    "pyyaml",
    "jsonschema",
    "scikit-learn",
    "pychapter10",
)


def library_versions(names: tuple[str, ...] = LIBRARIES) -> dict[str, str]:
    out = {}
    for n in names:
        try:
            out[n] = importlib.metadata.version(n)
        except importlib.metadata.PackageNotFoundError:
            out[n] = "absent"
    return out


def read_git_commit(repo: str | Path) -> tuple[str, bool]:
    """(HEAD commit, dirty) for the checkout at ``repo``. Raises if git or the repo is unavailable."""
    repo = str(repo)
    head = subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", repo, "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return head, bool(status.strip())


@dataclass(frozen=True)
class RunManifest:
    git_commit: str
    git_dirty: bool | None
    config_hash: str
    dict_hash: str
    order_log_hash: str
    backend: str
    bit_generator: str
    rng: Mapping[str, Any]
    stream_table: tuple[Mapping[str, Any], ...]
    library_versions: Mapping[str, str]
    python: str
    platform: str
    execution: Mapping[str, Any]
    formats: Mapping[str, int]
    numba_cache: Mapping[str, Any] = field(default_factory=dict)
    data_hashes: Mapping[str, str] = field(default_factory=dict)
    extra: Mapping[str, Any] = field(default_factory=dict)
    manifest_version: int = MANIFEST_VERSION

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["stream_table"] = list(d["stream_table"])
        return d

    def to_json(self) -> str:
        """Deterministic, human-readable JSON (sorted keys, 2-space indent, ASCII, trailing newline)."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"

    @property
    def hash(self) -> str:
        return digest(canonical_json(self.to_dict()), PERSON_MANIFEST)


def build_manifest(
    system: System,
    *,
    git_commit: str | None = None,
    git_dirty: bool | None = None,
    repo: str | Path | None = None,
    backend: str = "numpy-reference",
    order_log_hash: str = "",
    data_hashes: Mapping[str, str] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> RunManifest:
    """Manifest for a run of ``system``. Give ``git_commit`` explicitly, or ``repo`` to read it from git."""
    if git_commit is None:
        if repo is None:
            raise ValueError("pass git_commit, or repo to read it with git rev-parse")
        git_commit, git_dirty = read_git_commit(repo)
    return RunManifest(
        git_commit=git_commit,
        git_dirty=git_dirty,
        config_hash=system.config_hash,
        dict_hash=system.dict_hash,
        order_log_hash=order_log_hash,
        backend=backend,
        bit_generator=BIT_GENERATOR,
        rng=system.rng.describe(),
        stream_table=tuple(system.rng.registry.table()),
        library_versions=library_versions(),
        python=platform.python_version(),
        platform=f"{platform.system()}-{platform.machine()}",
        execution=system.execution(),
        formats={
            "rng_mapping": RNG_MAPPING_VERSION,
            "state": STATE_FORMAT_VERSION,
            "event_queue": QUEUE_FORMAT_VERSION,
            "snapshot": SNAPSHOT_FORMAT,
            "manifest": MANIFEST_VERSION,
        },
        data_hashes=dict(sorted((data_hashes or {}).items())),
        numba_cache=numba_cache_status(),
        extra=dict(extra or {}),
    )


def write_manifest(manifest: RunManifest, path: str | Path) -> Path:
    p = Path(path)
    p.write_text(manifest.to_json(), encoding="ascii")
    return p
