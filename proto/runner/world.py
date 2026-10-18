"""Fleet side: the 8 preview tail worlds stepped together, publishing contract Parquet day by day.

Each tail is the preview builder's own usage-mode world (``build_preview._fleet_world``) with the same scenario
key, root seed, M14 regime and data-quality defect injector as the published v0.9 fleet, so the history up to
any time reproduces the preview row for row. The station routine (``ScheduledPolicy``) decides at every
08:00 IST epoch, exactly as in the builder; orders from our system are submitted in the same batch, after the
routine's, through the data layer's own gateway (which rejects orders citing evidence not yet ingested).

What leaves the runner is only what the builder would publish: the consumer tree (observation set as of the
publish time, earliest ingest kept), usage counters per sortie at the ingest time of its SORTIE record, and the
restricted truth (``labels.truth``) in a separate tree that the ground side never reads.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from ipcstore import store_class
from datalayer import (
    DAY,
    KIND_COUNTER,
    LABELS,
    NS,
    OBS_TOPICS,
    TAILS,
    DefectInjector,
    MirrorSession,
    Order,
    ParquetStore,
    PolicyContext,
    ScheduledPolicy,
    bp,
    contract_tables,
    load_m18_config,
    rows_to_table,
)

#: scenario length of each tail world (2026-01-05 + 400 d): room to step well past the 180-day preview
DEFAULT_DAYS = 400


def fleet_store(run_dir: Path) -> ParquetStore:
    """Consumer tree ``<run>/fleet``; restricted truth in ``<run>/_restricted_labels/fleet`` (never nested).
    Files are Arrow IPC by default (``ipcstore``: Parquet is unreliable on big-endian IBM Z)."""
    return store_class()(run_dir / "fleet", bp._contract(), restricted_root=run_dir / "_restricted_labels" / "fleet")


class TailRunner:
    """One tail world, its live session and the station routine."""

    def __init__(self, tail: str, days: int = DEFAULT_DAYS, *, root: int | None = None) -> None:
        self.tail = tail
        self.builder = b = bp._fleet_world(TAILS.index(tail), days)
        if not hasattr(b, "scenario"):  # the preview World lacks the WorldBuilder ``scenario`` field
            b.scenario = b._ops.scenario
        self.contract = bp._contract()
        self.m18_cfg = load_m18_config()
        self.root = bp.FLEET_ROOT if root is None else int(root)
        self.session = MirrorSession(b, self.root, defects=self.defects(self.root))
        self.policy = ScheduledPolicy()
        self.routine_orders = 0
        self.labels_written = 0
        self.counter_sorties: set[str] = set()
        self.late_counter_rows = 0

    def fork_service(self):
        if getattr(self, "_fs", None) is None:
            from datalayer import MirrorForkService

            self._fs = MirrorForkService(self.builder, self.m18_cfg, defects_factory=self.defects)
        return self._fs

    def defects(self, root: int) -> DefectInjector:
        b = self.builder
        return DefectInjector(
            self.m18_cfg.defects,
            root=root,
            scenario=bp.FLEET_SCENARIO,
            contract=self.contract,
            dict_version=b.dict_version,
            dict_hash=b.dict_hash,
        )

    @property
    def epoch_utc(self) -> int:
        return self.builder.epoch_utc_ns

    @property
    def t_utc(self) -> int:
        return self.session.t_utc

    def advance(self, t_utc: int, orders: Mapping[int, Sequence[Order]] | None = None) -> list[dict[str, Any]]:
        """Run the closed loop until every event at or before ``t_utc`` is processed (the session stops at
        ``t_utc`` + 1 s). The routine decides at each 08:00 IST epoch on the way; ``orders[epoch_utc]`` are
        submitted with it. Returns the gateway verdicts of our orders."""
        orders = dict(orders or {})
        s, b = self.session, self.builder
        k_end = t_utc - self.epoch_utc + NS
        verdicts: list[dict[str, Any]] = []
        # the builder starts deciding at the first epoch after kernel 0 (``epochs(1 ns, …)``)
        for e in b.calendar.epochs(max(s.t, 1), k_end):
            s.run_until(e)
            ctx = PolicyContext(
                t_utc=s.t_utc,
                catalogue=self.m18_cfg.catalogue,
                cann_min_awp_s=self.m18_cfg.cann_min_awp_s,
                tz_offset_s=self.m18_cfg.tz_offset_s,
            )
            routine = list(self.policy.decide(s.obs, ctx))
            ours = list(orders.pop(s.t_utc, ()))
            if routine or ours:
                res = s.submit(routine + ours)
                self.routine_orders += len(routine)
                verdicts += [
                    {
                        "order_id": r.order_id,
                        "verdict": r.verdict,
                        "reason": r.reason,
                        "t_apply_utc": None if r.t_apply is None else self.epoch_utc + r.t_apply,
                    }
                    for r in res[len(routine) :]
                ]
        s.run_until(k_end)
        if orders:
            raise ValueError(f"{self.tail}: orders for times that are not epochs in this step: {sorted(orders)}")
        return verdicts

    def publish(self, store: ParquetStore, t_from: int | None, t_to: int) -> dict[str, Any]:
        """Write every consumer row first ingested in (``t_from``, ``t_to``] (everything up to ``t_to`` when
        ``t_from`` is None), the usage counters of sorties whose SORTIE record arrived by ``t_to``, and new
        truth rows to the restricted tree."""
        if self.session.t_utc <= t_to:
            raise ValueError("publish only what the session has fully processed")
        c, s, b = self.contract, self.session, self.builder
        out: dict[str, Any] = {"files": []}
        maint = None
        for topic in OBS_TOPICS:
            tab = s.obs.as_of(t_to, topic)
            if topic == "maint.records":
                maint = tab
            if t_from is not None and tab.num_rows:
                tab = tab.filter(pc.greater(tab.column(c.topics[topic].ingest_time), pa.scalar(t_from, pa.int64())))
            if tab.num_rows:
                out["files"] += store.write(topic, tab.cast(c.schemas[topic]))
            out[topic] = tab.num_rows
        # usage counters stay in M14's outbox in usage mode; the builder emits them per sortie at the ingest
        # instant of that sortie's first SORTIE record (sorties without paperwork are not published)
        assert maint is not None
        sortie_ingest: dict[str, int] = {}
        if maint.num_rows:
            sub = maint.filter(pc.equal(maint.column("record_type"), "SORTIE"))
            for sid, ti in zip(sub.column("sortie_id").to_pylist(), sub.column("t_ingest").to_pylist(), strict=True):
                if sid:
                    sortie_ingest[sid] = min(sortie_ingest.get(sid, ti), ti)
        mon_state = s.world.states["m14"]
        mon = s.system.modules["m14"] if hasattr(s.system, "modules") else None
        kinds = np.asarray(mon_state["o_kind"])
        with_counters = sorted({str(x) for x in np.asarray(mon_state["o_sortie"])[kinds == KIND_COUNTER]})
        tabs = []
        for sid in with_counters:
            if sid in self.counter_sorties or sid not in sortie_ingest:
                continue
            tab = contract_tables(
                mon,
                mon_state,
                dictionary=b.dictionary,
                tail_no=b.tail,
                epoch_utc_ns=b.epoch_utc_ns,
                t_ingest_utc_ns=sortie_ingest[sid],
                sortie_id=sid,
            )["usage.counters"]
            if t_from is not None and sortie_ingest[sid] <= t_from:
                self.late_counter_rows += tab.num_rows  # would break the window; counted, still published
            tabs.append(tab)
            self.counter_sorties.add(sid)
        if tabs:
            tab = pa.concat_tables(tabs)
            out["files"] += store.write("usage.counters", tab)
            out["usage.counters"] = tab.num_rows
        else:
            out["usage.counters"] = 0
        labels = s.log.rows(LABELS)
        new = labels[self.labels_written :]
        if new:
            store.write(LABELS, rows_to_table(c, LABELS, new))
        self.labels_written = len(labels)
        out["labels.truth (restricted)"] = len(new)
        out["late_counter_rows"] = self.late_counter_rows
        return out


class Fleet:
    """The 8 tail worlds in lockstep, publishing into one run directory."""

    def __init__(self, run_dir: Path, days: int = DEFAULT_DAYS, tails: Sequence[str] = TAILS) -> None:
        self.run_dir = Path(run_dir)
        self.store = fleet_store(self.run_dir)
        w = time.perf_counter()
        self.tails = {t: TailRunner(t, days) for t in tails}
        self.build_s = round(time.perf_counter() - w, 2)
        self.t_published: int | None = None

    def step(
        self, t_to: int, orders_by_tail: Mapping[str, Mapping[int, Sequence[Order]]] | None = None
    ) -> dict[str, Any]:
        """Advance every tail to ``t_to`` (inclusive), then publish what was ingested since the last publish."""
        orders_by_tail = orders_by_tail or {}
        unknown = set(orders_by_tail) - set(self.tails)
        if unknown:
            raise ValueError(f"orders for unknown tails {sorted(unknown)}")
        doc: dict[str, Any] = {"t_from": self.t_published, "t_to": t_to, "tails": {}}
        w0 = time.perf_counter()
        for tail, tr in self.tails.items():
            w = time.perf_counter()
            verdicts = tr.advance(t_to, orders_by_tail.get(tail))
            adv = time.perf_counter() - w
            pub = tr.publish(self.store, self.t_published, t_to)
            doc["tails"][tail] = {
                "verdicts": verdicts,
                "rows": {k: v for k, v in pub.items() if k != "files"},
                "files": [str(p.relative_to(self.run_dir)) for p in pub["files"]],
                "advance_s": round(adv, 2),
                "publish_s": round(time.perf_counter() - w - adv, 2),
            }
        doc["wall_s"] = round(time.perf_counter() - w0, 2)
        self.t_published = t_to
        return doc

    def day_ahead(self) -> int:
        """The next publish time one day after the last one."""
        if self.t_published is None:
            raise ValueError("nothing published yet")
        return self.t_published + DAY
