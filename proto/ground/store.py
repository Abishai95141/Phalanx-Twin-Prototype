"""The as-of store: the only read path of the ground side.

Consumer Parquet trees (the live run's ``fleet/``, the engine ``overlay/``, training worlds, or the published
preview) are scanned file by file through the G0 gate and loaded once into in-memory tables (pyarrow → pandas),
one per topic, tagged with their source. ``refresh()`` picks up the files a runner step adds. (DuckDB was the
plan; it has no IBM Z / s390x build and the data is small, so plain pyarrow and pandas do the work.)

``as_of(t, topic)`` returns the rows with ingest time ≤ t, deduplicated by the scoped key
(``tail_no`` — ``target_tail_no`` for orders — plus ``record_id``) keeping the earliest ingest. Rows without a
tail (SHOP_FINDING) are not deduplicated here: their ids collide across the preview's worlds, so they are linked
to a world first (``shop_findings``). SENTINEL-flagged and non-NORMAL values are masked to null; OUT_OF_RANGE
values are kept.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa

from gate import Gate, GateResult, assert_consumer_path, read_table
from interfaces import Source

PREVIEW_FLEET = Path(os.environ.get("PHX_PREVIEW_FLEET", "/Users/abishaikc/Downloads/phalanx_data_layer_preview/data/v0.9/fleet"))
SENTINEL = 0x001  # quality_flags bit 0 (data layer doc 03)
#: value columns masked when the row is SENTINEL-flagged or its validity is not NORMAL
MASKED = {"usage.counters": ("value_eu", "increment_eu"), "param.samples": ("value_eu", "raw_counts")}
TAIL_KEY = {"orders.commands": "target_tail_no", "orders.status": None}
_PART = re.compile(r"part-(\d{20})-[0-9a-f]+\.(parquet|arrow)$")


@dataclass(frozen=True)
class Root:
    path: Path
    source: Source = Source.FLEET
    world_seed: int | None = None


def _plain(tab: pa.Table) -> pa.Table:
    """Fixed-size binary ids become plain binary so pandas holds them as ``bytes``."""
    cols = []
    for f, col in zip(tab.schema, tab.columns, strict=True):
        if pa.types.is_fixed_size_binary(f.type):
            col = col.cast(pa.binary())
        elif pa.types.is_list(f.type) and pa.types.is_fixed_size_binary(f.type.value_type):
            col = col.cast(pa.list_(pa.binary()))
        cols.append(col)
    return pa.table(cols, names=tab.schema.names)


class Store:
    def __init__(self, roots: Iterable[Root], gate: Gate | None = None) -> None:
        self.roots = list(roots)
        for r in self.roots:
            assert_consumer_path(r.path)
        self.gate = gate or Gate()
        self.seen: set[Path] = set()
        self.files: dict[str, list[tuple[Path, Root, int]]] = {}  # topic -> (path, root, min ingest)
        self.rejected: list[GateResult] = []
        self.ingest_col: dict[str, str] = {}
        self.event_col: dict[str, str] = {}
        self._pieces: dict[str, list[pd.DataFrame]] = {}
        self._frames: dict[str, pd.DataFrame] = {}
        self.refresh()

    # ---- construction helpers -------------------------------------------------------------------------
    @classmethod
    def for_run(cls, run_dir: Path) -> Store:
        # the overlay tree may appear later (generated with each runner step); refresh() picks it up then
        return cls([Root(Path(run_dir) / "fleet", Source.FLEET), Root(Path(run_dir) / "overlay", Source.OVERLAY)])

    @classmethod
    def for_preview(cls) -> Store:
        return cls([Root(PREVIEW_FLEET, Source.FLEET)])

    # ---- loading ---------------------------------------------------------------------------------------
    def refresh(self) -> dict[str, int]:
        """Gate and load every part file not seen before. Returns new rows loaded per topic."""
        loaded: dict[str, int] = {}
        for root in self.roots:
            if not root.path.is_dir():
                continue
            for topic in self.gate.topics:
                tdir = root.path / topic
                if not tdir.is_dir():
                    continue
                for p in sorted([*tdir.rglob("part-*.parquet"), *tdir.rglob("part-*.arrow")]):
                    if p in self.seen:
                        continue
                    self.seen.add(p)
                    res = self.gate.check(p, topic)
                    if not res.accepted:
                        self.rejected.append(res)
                        continue
                    self.ingest_col.setdefault(topic, res.ingest_time or "t_ingest")
                    self.event_col.setdefault(topic, res.event_time or self.ingest_col[topic])
                    m = _PART.search(p.name)
                    self.files.setdefault(topic, []).append((p, root, int(m.group(1)) if m else 0))
                    df = _plain(read_table(p)).to_pandas()
                    df["_source"] = root.source.value
                    df["_seed"] = root.world_seed
                    df["_file"] = str(p)
                    self._pieces.setdefault(topic, []).append(df)
                    self._frames.pop(topic, None)
                    loaded[topic] = loaded.get(topic, 0) + len(df)
        return loaded

    def _frame(self, topic: str) -> pd.DataFrame:
        if topic not in self._frames:
            pieces = self._pieces.get(topic, [])
            self._frames[topic] = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
            self._pieces[topic] = [self._frames[topic]] if pieces else []
        return self._frames[topic]

    def has(self, topic: str) -> bool:
        return topic in self.files

    # ---- the read path ---------------------------------------------------------------------------------
    def df(
        self,
        t: int,
        topic: str,
        *,
        tail_no: str | None = None,
        source: Source = Source.FLEET,
        world_seed: int | None = None,
    ) -> pd.DataFrame:
        """Rows of ``topic`` ingested at or before ``t`` (UTC ns) as pandas, with ``rid`` (record id hex)."""
        if not self.has(topic):
            return pd.DataFrame()
        f, ing = self._frame(topic), self.ingest_col[topic]
        tail = TAIL_KEY.get(topic, "tail_no")
        keep = (f[ing] <= int(t)) & (f["_source"] == source.value)
        if world_seed is not None:
            keep &= f["_seed"] == int(world_seed)
        if tail_no is not None and tail:
            keep &= f[tail] == tail_no
        v = f[keep].sort_values([ing, "_file"], kind="mergesort")
        key = ["_source", "_seed", tail, "record_id"] if tail else ["_source", "_seed", "record_id"]
        if tail:
            no_tail = v[tail].isna()
            v = pd.concat([v[~no_tail].drop_duplicates(key, keep="first"), v[no_tail]])
        else:
            v = v.drop_duplicates(key, keep="first")
        for col in MASKED.get(topic, ()):
            if col in v:
                bad = ((v["quality_flags"].fillna(0).astype("int64") & SENTINEL) != 0) | (v["validity"] != "NORMAL")
                v = v.assign(**{col: v[col].where(~bad)})
        v = v.sort_values([self.event_col[topic], ing], kind="mergesort").drop(columns=["_file"])
        v = v.reset_index(drop=True)
        v["rid"] = v["record_id"].map(lambda b: bytes(b).hex())
        return v

    def as_of(self, t: int, topic: str, **kw) -> pa.Table:
        """``df`` as a pyarrow table (without the helper ``rid`` column)."""
        d = self.df(t, topic, **kw)
        return pa.Table.from_pandas(d.drop(columns=["rid"]), preserve_index=False) if len(d.columns) else pa.table({})

    def maint_latest(self, t: int, record_types: Sequence[str] | None = None, **kw) -> pd.DataFrame:
        """Latest ``record_version`` per (tail_no, record_type, record_key) among maint rows ingested by ``t``."""
        df = self.df(t, "maint.records", **kw)
        if not len(df):
            return df
        if record_types is not None:
            df = df[df.record_type.isin(list(record_types))]
        df = df[df.tail_no.notna()]
        df = df.sort_values(["record_version", "t_ingest"], kind="mergesort")
        return df.drop_duplicates(["tail_no", "record_type", "record_key"], keep="last").reset_index(drop=True)

    def shop_findings(self, t: int, **kw) -> pd.DataFrame:
        """SHOP_FINDING rows ingested by ``t``, each linked to its world (``tail_no``) by job + serial: the world
        whose COMPONENT_LIFE REMOVE of that serial on that job happened before the finding. Rows matching no
        world or several stay unlinked (``tail_no`` null). Deduplicated by (world, record id)."""
        m = self.df(t, "maint.records", **kw)
        if not len(m):
            return m
        sf = m[m.record_type == "SHOP_FINDING"].copy()
        rem = m[(m.record_type == "COMPONENT_LIFE") & (m.install_action == "REMOVE") & m.tail_no.notna()]
        rem_idx = rem.groupby(["job_no", "serial_no"]).groups
        worlds = []
        for r in sf.itertuples():
            key = (r.job_no, r.serial_no)
            if key in rem_idx:
                c = rem.loc[rem_idx[key]]
                w = sorted(c[c.t_event <= r.t_event].tail_no.unique())
                worlds.append(w[0] if len(w) == 1 else None)
            else:
                worlds.append(None)
        sf["tail_no"] = worlds
        sf["linked"] = sf.tail_no.notna()
        sf = sf.sort_values("t_ingest", kind="mergesort").drop_duplicates(["tail_no", "rid"])
        return sf.reset_index(drop=True)

    def snapshot_id(self, t: int, source: Source = Source.FLEET) -> str:
        """Content hash of the accepted part files holding rows ingested by ``t`` (file names embed a digest
        of their bytes), plus ``t`` itself."""
        h = hashlib.blake2b(digest_size=32)
        h.update(f"{source.value}|{int(t)}".encode())
        rel = sorted(
            f"{topic}/{p.relative_to(root.path)}"
            for topic, entries in self.files.items()
            for p, root, t_min in entries
            if root.source == source and t_min <= t
        )
        for r in rel:
            h.update(r.encode())
        return h.hexdigest()

    def last_ingest(self, t: int, tail_no: str) -> int | None:
        """Latest ingest time ≤ t of any record of the tail (maintenance and events)."""
        best = None
        for topic in ("maint.records", "events.bit_faults", "events.cautions"):
            if not self.has(topic):
                continue
            f, ing = self._frame(topic), self.ingest_col[topic]
            s = f.loc[(f[ing] <= int(t)) & (f["tail_no"] == tail_no) & (f["_source"] == "fleet"), ing]
            if len(s) and (best is None or int(s.max()) > best):
                best = int(s.max())
        return best
