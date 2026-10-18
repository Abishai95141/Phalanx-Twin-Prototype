"""The one place the runner touches the Phalanx data layer (preview v0.9 code, read-only).

Run through ``run.sh``, which puts ``$PHX_DATALAYER_CODE/src`` on ``PYTHONPATH`` and keeps Python and numba
from writing caches into the source tree. Nothing here edits a data-layer module.

``MirrorSession`` is the documented addition from ``video/tools/forks/phx_forks.py``: it publishes the
``events.*`` rows that M14 downloads into the session's observation set, as the preview builder did for the
consumer ``fleet/events.*`` trees, so the order gateway can check evidence that cites BIT events.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import os
from pathlib import Path
from typing import Any

CODE = Path(os.environ.get("PHX_DATALAYER_CODE", "/Users/abishaikc/Downloads/phalanx_data_layer_preview/code"))
PREVIEW_FLEET = CODE.parent / "data" / "v0.9" / "fleet"

_spec = importlib.util.spec_from_file_location("phx_build_preview", CODE / "tools" / "build_preview.py")
bp = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(bp)

from phalanx.fork.belief import SurvivalPosterior  # noqa: E402
from phalanx.fork.service import BranchSpec, ForkService  # noqa: E402
from phalanx.fork.session import OpsSession, SessionSnapshot  # noqa: E402
from phalanx.health.protocol import read_payload  # noqa: E402
from phalanx.maintenance import load_m18_config  # noqa: E402
from phalanx.maintenance.defects import DefectInjector  # noqa: E402
from phalanx.maintenance.records import rows_to_table  # noqa: E402
from phalanx.monitoring.contract_out import contract_tables  # noqa: E402
from phalanx.monitoring.module import KIND_COUNTER  # noqa: E402
from phalanx.orders.gateway import SubmitResult  # noqa: E402
from phalanx.orders.model import Order  # noqa: E402
from phalanx.orders.policies import PolicyContext, ScheduledPolicy  # noqa: E402
from phalanx.streaming.parquet_store import ParquetStore  # noqa: E402

NS = 10**9
DAY = 86_400 * NS
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
TAILS = tuple(f"TJ1{i:02d}" for i in range(1, 9))  # the preview's 8 fleet worlds, TJ101 … TJ108
#: consumer topics the runner publishes from the observation set
OBS_TOPICS = (
    "maint.records",
    "orders.commands",
    "orders.status",
    "events.bit_faults",
    "events.exceedances",
    "events.cautions",
)
LABELS = "labels.truth"

__all__ = [
    "CODE",
    "DAY",
    "IST",
    "KIND_COUNTER",
    "LABELS",
    "NS",
    "OBS_TOPICS",
    "PREVIEW_FLEET",
    "TAILS",
    "DefectInjector",
    "BranchSpec",
    "ForkService",
    "MirrorForkService",
    "SurvivalPosterior",
    "MirrorSession",
    "Order",
    "OpsSession",
    "ParquetStore",
    "PolicyContext",
    "ScheduledPolicy",
    "SessionSnapshot",
    "SubmitResult",
    "bp",
    "contract_tables",
    "fmt_ist",
    "ist_ns",
    "load_m18_config",
    "rows_to_table",
]


def ist_ns(y: int, m: int, d: int, h: int = 0, mi: int = 0, s: int = 0) -> int:
    return int(dt.datetime(y, m, d, h, mi, s, tzinfo=IST).timestamp()) * NS


def fmt_ist(t_utc_ns: int) -> str:
    return dt.datetime.fromtimestamp(t_utc_ns / NS, IST).strftime("%Y-%m-%d %H:%M:%S IST")


class MirrorSession(OpsSession):
    """``OpsSession`` that also publishes M14's ``obs.event`` downloads (``events.*`` rows, at their ingest
    time) into the observation set."""

    def _collect(self, trace) -> None:  # type: ignore[override]
        by_topic: dict[str, list[dict[str, Any]]] = {}
        for _, ev in trace.dispatched:
            if ev.kind == "obs.event":
                doc = read_payload(ev.payload)
                by_topic.setdefault(doc["topic"], []).append(doc["row"])
        super()._collect(trace)
        if self.obs is not None:
            for topic in sorted(by_topic):
                self.obs.append(topic, rows_to_table(self.contract, topic, by_topic[topic]))


class MirrorForkService(ForkService):
    """``ForkService`` whose branches are ``MirrorSession``s (otherwise identical to ``ForkService.fork``)."""

    def fork(self, snap: SessionSnapshot, spec, *, ledger=None) -> OpsSession:  # type: ignore[override]
        root = self.root_for(snap, spec)
        defects = self.defects_factory(snap.root) if self.defects_factory else None
        s = MirrorSession.restore(self.builder, snap, root=root, defects=defects, ledger=ledger)
        if spec.mode == "belief":
            spec.belief.apply(s, particle=spec.member)
        return s
