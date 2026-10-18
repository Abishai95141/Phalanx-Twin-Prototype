"""M14 outbox -> contract v0 topics ``events.bit_faults``, ``events.exceedances``, ``events.cautions`` and
``usage.counters`` (architecture §12; frozen contract v0, AD-41). Every table is built against the generated
schema and validated with ``load_contract("v0").validate`` before it is returned (acceptance A6).

Fast-path conventions (same as ``phalanx.ground.fast_path`` for samples, A-W0.4-3/4): ``provenance = direct``;
record_id channel ``direct:<source_lru>``, ``seq`` = occurrence index of (source_lru, event_code) within the
sortie in t_occurrence order, ``msg_index`` = 0; ``t_utc`` = event time (**PROXY A-W1.5-44**: a perfectly
locked time source. W1.7 built no event path, so the replacement is W2.2's M14 ``events.*`` full-path route:
events recorded by M16 and decoded by M17, whose ``t_utc`` comes from the recorder time base);
``t_record``, ``ch10_event_number`` and ``raw_bit_word`` are null. ``t_ingest`` is the
sortie's download instant supplied by the caller. ``detection_far_per_fh`` is the nominal (specified) rate,
never the simulated true rate (AD-38).

M14 never writes truth: no field below is derived from hidden states, fault labels or truth values.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pyarrow as pa

from phalanx.ground.rid import record_ids

from .codes import MECHANISMS
from .module import COUNTERS, KIND_BIT, KIND_CAUTION, KIND_COUNTER, KIND_EXCEED, VALIDITY

__all__ = ["EVENT_TOPICS", "contract_tables"]

EVENT_TOPICS = {
    KIND_BIT: "events.bit_faults",
    KIND_EXCEED: "events.exceedances",
    KIND_CAUTION: "events.cautions",
}
COUNTER_TOPIC = "usage.counters"
PROVENANCE = "direct"
_ENGINE_GROUPS = ("ENGINE", "ENGINE_MONITORING")


def _occurrence_seq(
    sorties: Sequence[str], lrus: Sequence[str], codes: Sequence[str], t: np.ndarray
) -> np.ndarray:
    """Occurrence index of (sortie, source_lru, event_code) in t order (ties by input order)."""
    order = np.lexsort((np.arange(t.size), t))
    seq = np.zeros(t.size, np.int64)
    counts: dict[tuple[str, str, str], int] = {}
    for j in order:
        k = (sorties[j], lrus[j], codes[j])
        seq[j] = counts.get(k, 0)
        counts[k] = seq[j] + 1
    return seq


def contract_tables(
    module,
    state,
    *,
    dictionary,
    tail_no: str,
    epoch_utc_ns: int,
    t_ingest_utc_ns: int,
    sortie_id: str | None = None,
    contract=None,
) -> dict[str, pa.Table]:
    """The four consumer topics from the outbox records (of ``sortie_id`` if given; ground events otherwise
    included only when ``sortie_id`` is None). Kernel times map to simulated UTC by ``epoch_utc_ns``."""
    from phalanx.dictionary.contract import load_contract

    c = contract or load_contract("v0")
    p = module.params
    codes = module.config.codes.codes
    n_tests = max(1, sum(1 for x in codes if x.src == "internal"))
    far_bit = float(p.value("spec_far_aircraft")) * 3600.0 / n_tests
    far_ehm = float(p.value("spec_far_ehm")) * 3600.0
    pre = round(float(p.value("snapshot_pre_s")) * 1e9)
    post = round(float(p.value("snapshot_post_s")) * 1e9)
    kind = np.asarray(state["o_kind"])
    sel_s = np.ones(kind.size, bool) if sortie_id is None else (np.asarray(state["o_sortie"]) == sortie_id)
    out: dict[str, pa.Table] = {}
    eng_serial = module.config.engine_serials[0] if module.config.engine_serials else None
    for k, topic in EVENT_TOPICS.items():
        idx = np.flatnonzero((kind == k) & sel_s)
        out[topic] = _event_table(
            c,
            topic,
            module,
            state,
            idx,
            dictionary,
            tail_no,
            epoch_utc_ns,
            t_ingest_utc_ns,
            far_bit,
            far_ehm,
            pre,
            post,
            eng_serial,
        )
    idx = np.flatnonzero((kind == KIND_COUNTER) & sel_s)
    out[COUNTER_TOPIC] = _counter_table(
        c, module, state, idx, dictionary, tail_no, epoch_utc_ns, t_ingest_utc_ns
    )
    return out


def _event_table(
    c,
    topic,
    module,
    state,
    idx,
    dictionary,
    tail_no,
    epoch,
    t_ingest,
    far_bit,
    far_ehm,
    pre,
    post,
    eng_serial,
):
    codes = module.config.codes.codes
    n = idx.size
    recs = [codes[int(state["o_code"][j])] for j in idx]
    sortie = [str(state["o_sortie"][j]) or None for j in idx]
    lru = [r.lru for r in recs]
    ev = [r.code for r in recs]
    t_occ = epoch + np.asarray(state["o_t"])[idx].astype(np.int64)
    seq = _occurrence_seq([s or "" for s in sortie], lru, ev, t_occ)
    rid = record_ids(
        c,
        topic,
        {
            "provenance": PROVENANCE,
            "tail_no": tail_no,
            "sortie_id": pa.array(sortie, pa.string()),
            "channel_id": pa.array([f"direct:{x}" for x in lru], pa.string()),
            "event_code": pa.array(ev, pa.string()),
            "seq": seq.astype(np.uint64),
            "msg_index": 0,
        },
        n,
    )
    ecms = np.array([r.mechanism == "EXCEEDANCE" or r.lru in ("ECMS", "FADEC") for r in recs], bool)
    t_end_raw = np.asarray(state["o_t_end"])[idx]
    cols: dict[str, pa.Array] = {
        "record_id": rid,
        "dict_version": pa.array([dictionary.dict_version] * n, pa.string()),
        "dict_hash": pa.array([dictionary.dict_hash] * n, pa.string()),
        "event_id": pa.array(
            [f"{tail_no}:{s or 'GROUND'}:{e}:{q}" for s, e, q in zip(sortie, ev, seq, strict=True)],
            pa.string(),
        ),
        "tail_no": pa.array([tail_no] * n, pa.string()),
        "sortie_id": pa.array(sortie, pa.string()),
        "engine_serial": pa.array(
            [eng_serial if r.group in _ENGINE_GROUPS else None for r in recs], pa.string()
        ),
        "source_lru": pa.array(lru, pa.string()),
        "event_code": pa.array(ev, pa.string()),
        "event_group": pa.array([r.group for r in recs], pa.string()),
        "severity": pa.array([r.severity for r in recs], pa.string()),
        "description": pa.array([r.desc for r in recs], pa.string()),
        "confirmed_status": pa.array(["UNCONFIRMED"] * n, pa.string()),
        "detection_mechanism": pa.array([MECHANISMS[int(state["o_mech"][j])] for j in idx], pa.string()),
        "detection_far_per_fh": pa.array(
            [far_ehm if (r.mechanism == "EXCEEDANCE" or r.regime == "ehm") else far_bit for r in recs],
            pa.float64(),
        ),
        "fault_list": pa.array([r.fault_list for r in recs], pa.string()),
        "latched": pa.array([bool(state["o_latched"][j]) for j in idx], pa.bool_()),
        "persistence_count": pa.array([int(state["o_persist"][j]) for j in idx], pa.uint32()),
        "suspect_lrus": pa.array(
            [[{"lru": s, "isolation_confidence": conf} for s, conf in r.suspects] for r in recs],
            c.schemas[topic].field("suspect_lrus").type,
        ),
        "snapshot_t_start": pa.array(
            [int(t - pre) if e else None for t, e in zip(t_occ, ecms, strict=True)], pa.int64()
        ),
        "snapshot_t_end": pa.array(
            [int(t + post) if e else None for t, e in zip(t_occ, ecms, strict=True)], pa.int64()
        ),
        "ch10_event_number": pa.nulls(n, pa.uint32()),
        "t_occurrence": pa.array(t_occ, pa.int64()),
        "t_record": pa.nulls(n, pa.int64()),
        "t_utc": pa.array(t_occ, pa.int64()),  # PROXY A-W1.5-44: perfect time lock (W2.2 full path)
        "t_ingest": pa.array([int(t_ingest)] * n, pa.int64()),
        "quality_flags": pa.array([0] * n, pa.uint32()),
        "provenance": pa.array([PROVENANCE] * n, pa.string()),
        "lane": pa.array([str(state["o_lane"][j]) or None for j in idx], pa.string()),
        "raw_bit_word": pa.nulls(n, pa.int64()),
    }
    if topic == "events.exceedances":
        mons = [r.monitor for r in recs]
        cols["param_id"] = pa.array(
            [
                dictionary.contract_location(m.channel)["param_id"] if m else r.code
                for m, r in zip(mons, recs, strict=True)
            ],
            pa.string(),
        )
        cols["limit_id"] = pa.array(
            [m.limit_id if m else f"{r.code}:test" for m, r in zip(mons, recs, strict=True)], pa.string()
        )
        cols["limit_value"] = pa.array([float(state["o_limit"][j]) for j in idx], pa.float64())
        cols["peak_value"] = pa.array([float(state["o_value"][j]) for j in idx], pa.float64())
        cols["units"] = pa.array([m.units if m else "1" for m in mons], pa.string())
        cols["t_end"] = pa.array([epoch + int(x) if x >= 0 else None for x in t_end_raw], pa.int64())
    if topic == "events.cautions":
        cols["legend"] = pa.array([r.legend or "CWS-VOICE" for r in recs], pa.string())
        cols["displayed"] = pa.array([r.displayed for r in recs], pa.bool_())
        cols["voice_warning"] = pa.array([r.voice for r in recs], pa.bool_())
        cols["t_cleared"] = pa.array([epoch + int(x) if x >= 0 else None for x in t_end_raw], pa.int64())
    schema = c.schemas[topic]
    table = pa.Table.from_arrays([cols[f.name] for f in schema], schema=schema)
    c.validate(topic, table)
    return table


def _counter_table(c, module, state, idx, dictionary, tail_no, epoch, t_ingest):
    n = idx.size
    units_map = dictionary.units_map()
    pids = [COUNTERS[int(state["o_code"][j])][0] for j in idx]
    srcs = [COUNTERS[int(state["o_code"][j])][1] for j in idx]
    eng = [int(state["o_engine"][j]) for j in idx]
    serials = module.config.engine_serials
    engine_serial = [serials[e] if e >= 0 else None for e in eng]
    item = [module.config.chute_serial or None if pid == "USAGE.CHUTE_STREAMINGS" else None for pid in pids]
    sortie = [str(state["o_sortie"][j]) or None for j in idx]
    t_upd = epoch + np.asarray(state["o_t"])[idx].astype(np.int64)
    seq = np.asarray(state["o_seq"])[idx].astype(np.uint64)
    rid = record_ids(
        c,
        COUNTER_TOPIC,
        {
            "provenance": PROVENANCE,
            "tail_no": tail_no,
            "sortie_id": pa.array(sortie, pa.string()),
            "engine_serial": pa.array(engine_serial, pa.string()),
            "item_serial": pa.array(item, pa.string()),
            "param_id": pa.array(pids, pa.string()),
            "update_seq": seq,
        },
        n,
    )
    cols = {
        "record_id": rid,
        "dict_version": pa.array([dictionary.dict_version] * n, pa.string()),
        "dict_hash": pa.array([dictionary.dict_hash] * n, pa.string()),
        "param_id": pa.array(pids, pa.string()),
        "tail_no": pa.array([tail_no] * n, pa.string()),
        "sortie_id": pa.array(sortie, pa.string()),
        "engine_serial": pa.array(engine_serial, pa.string()),
        "item_serial": pa.array(item, pa.string()),
        "source_lru": pa.array(srcs, pa.string()),
        "update_seq": pa.array(seq.astype(np.uint32), pa.uint32()),
        "value_eu": pa.array([float(state["o_value"][j]) for j in idx], pa.float64()),
        "increment_eu": pa.array([float(state["o_incr"][j]) for j in idx], pa.float64()),
        "units": pa.array([units_map[pid] for pid in pids], pa.string()),
        "t_update": pa.array(t_upd, pa.int64()),
        "t_record": pa.nulls(n, pa.int64()),
        "t_utc": pa.array(t_upd, pa.int64()),  # PROXY A-W1.5-44: perfect time lock (W2.2 full path)
        "t_ingest": pa.array([int(t_ingest)] * n, pa.int64()),
        "validity": pa.array([VALIDITY[int(state["o_validity"][j])] for j in idx], pa.string()),
        "quality_flags": pa.array([0] * n, pa.uint32()),
        "provenance": pa.array([PROVENANCE] * n, pa.string()),
    }
    schema = c.schemas[COUNTER_TOPIC]
    table = pa.Table.from_arrays([cols[f.name] for f in schema], schema=schema)
    c.validate(COUNTER_TOPIC, table)
    return table
