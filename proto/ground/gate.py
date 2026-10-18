"""G0 release gate: a Parquet part enters the system only if it was written under an allowlisted contract.

Checks per file (schema metadata only; the data is not read here):
- the path is in a consumer tree — anything under a ``_restricted*`` directory is refused without opening it;
- ``phalanx.contract`` / ``phalanx.contract_version`` / ``phalanx.contract_hash`` match an allowlist entry;
- ``phalanx.audience`` is ``consumer`` and ``phalanx.topic`` matches the topic directory;
- every column the ground side needs for that topic is present (columns are read by name, never position).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ALLOWLIST = Path(__file__).with_name("contract_allowlist.yaml")


class RestrictedPathError(PermissionError):
    """Raised when anything in the ground side tries to touch a restricted tree."""


def read_schema(path: Path) -> pa.Schema:
    """Schema (with metadata) of a contract file: Arrow IPC (``.arrow``) or Parquet (``.parquet``)."""
    if str(path).endswith(".arrow"):
        with pa.memory_map(str(path)) as src:
            return pa.ipc.open_file(src).schema
    return pq.read_schema(path)


def read_table(path: Path) -> pa.Table:
    """The whole file, in native byte order. Parquet is read as a single file (no partition inference)."""
    if str(path).endswith(".arrow"):
        with pa.memory_map(str(path)) as src:
            return pa.ipc.open_file(src).read_all()
    return pq.ParquetFile(str(path)).read()


def assert_consumer_path(path: Path) -> None:
    if any(part.startswith("_restricted") for part in Path(path).parts):
        raise RestrictedPathError(f"refusing restricted path {path}")


@dataclass(frozen=True)
class GateResult:
    path: Path
    topic: str
    accepted: bool
    reason: str = ""
    ingest_time: str | None = None  # column name from the file's metadata
    event_time: str | None = None


class Gate:
    def __init__(self, allowlist: Path = ALLOWLIST) -> None:
        doc = yaml.safe_load(Path(allowlist).read_text())
        self.contracts = {(c["name"], str(c["version"]), c["hash"]) for c in doc["contracts"]}
        self.audience = doc["audience"]
        self.required = {t: tuple(cols) for t, cols in doc["topics"].items()}

    @property
    def topics(self) -> tuple[str, ...]:
        return tuple(self.required)

    def check(self, path: Path, topic: str) -> GateResult:
        assert_consumer_path(path)
        if topic not in self.required:
            return GateResult(path, topic, False, f"topic {topic} is not read by the ground side")
        try:
            schema = read_schema(path)
        except Exception as e:  # unreadable file: rejected, never half-read
            return GateResult(path, topic, False, f"unreadable: {e}")
        md = {k.decode(): v.decode() for k, v in (schema.metadata or {}).items()}
        key = (md.get("phalanx.contract"), md.get("phalanx.contract_version"), md.get("phalanx.contract_hash"))
        if key not in self.contracts:
            return GateResult(path, topic, False, f"contract {key[0]} {key[1]} hash {str(key[2])[:12]}… not allowlisted")
        if md.get("phalanx.audience") != self.audience:
            return GateResult(path, topic, False, f"audience {md.get('phalanx.audience')!r} is not {self.audience!r}")
        if md.get("phalanx.topic") != topic:
            return GateResult(path, topic, False, f"file says topic {md.get('phalanx.topic')!r}")
        missing = [c for c in self.required[topic] if c not in schema.names]
        if missing:
            return GateResult(path, topic, False, f"missing columns {missing}")
        return GateResult(path, topic, True, "", md.get("phalanx.ingest_time"), md.get("phalanx.event_time"))
