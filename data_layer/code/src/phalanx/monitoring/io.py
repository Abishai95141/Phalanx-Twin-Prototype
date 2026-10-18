"""Payload builders for M14 events (the observation-side interface W2.1 wires).

``monitor.observe`` carries a time-ordered chunk of CIR rows restricted to the channels M14 consumes, as flat
arrays (event payloads are NumPy trees): ``ch`` (index into ``MonitoringConfig.channels``), ``t`` (kernel ns,
i.e. CIR ``t_sample`` minus the run epoch), ``v`` (engineering value), ``validity`` (index into
``VALIDITY``). Restricted CIR columns (``truth_value``, ``t_true``) are never read.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from .module import VALIDITY

__all__ = ["bit_report_payload", "cir_chunk_payload", "lru_condition_payload", "sortie_end_payload"]

_FORBIDDEN = ("truth_value", "t_true")


def cir_chunk_payload(config, cir: pa.Table, *, epoch_utc_ns: int) -> dict[str, np.ndarray]:
    """``monitor.observe`` payload from a CIR table (``phalanx.ground.cir.CIR_SCHEMA`` columns)."""
    cols = [n for n in cir.column_names if n not in _FORBIDDEN]
    tab = cir.select(cols)
    lane = pc.fill_null(tab.column("lane"), "")
    pid = tab.column("param_id").to_pylist()
    lanes = lane.to_pylist()
    chan = [p + ("." + ln if ln else "") for p, ln in zip(pid, lanes, strict=True)]
    index = {c: i for i, c in enumerate(config.channels)}
    keep = np.array([c in index for c in chan], bool)
    ch = np.array([index[c] for c, k in zip(chan, keep, strict=True) if k], np.int64)
    t = tab.column("t_sample").to_numpy()[keep].astype(np.int64) - int(epoch_utc_ns)
    v = tab.column("value").to_numpy()[keep].astype(np.float64)
    vmap = {s: i for i, s in enumerate(VALIDITY)}
    val = np.array(
        [vmap[s] for s, k in zip(tab.column("validity").to_pylist(), keep, strict=True) if k], np.int64
    )
    order = np.lexsort((ch, t))
    return {"ch": ch[order], "t": t[order], "v": v[order], "validity": val[order]}


def bit_report_payload(
    code: str, *, lane: str = "", persistence: int = 0, cleared: bool = False
) -> dict[str, object]:
    """``monitor.bit_report`` payload (sent by M08/M05/M09 when their own logic declares or clears a code)."""
    return {"code": code, "lane": lane, "persistence": int(persistence), "cleared": bool(cleared)}


def lru_condition_payload(
    code: str, magnitude: float, *, covered: bool = True, instance: int = 0, clear: bool = False
) -> dict[str, object]:
    """``monitor.lru_condition`` payload (sent by M11): shift of the code's test statistic in σ units."""
    return {
        "code": code,
        "magnitude": float(magnitude),
        "covered": bool(covered),
        "instance": int(instance),
        "clear": bool(clear),
    }


def sortie_end_payload(counts: Mapping[str, float | np.ndarray]) -> dict[str, np.ndarray]:
    """``monitor.sortie_end`` payload: the OAC discrete counts of the sortie (flight_time_s, landings,
    gear_cycles, ab_lights[e], starts[e], air_relights[e], jfs_attempts, jfs_successes, jfs_consecutive,
    chute_streamings, brake_count, brake_energy_j)."""
    return {k: np.asarray(v, np.float64) for k, v in counts.items()}
