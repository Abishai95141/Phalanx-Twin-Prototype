"""Restricted ``labels.truth`` records of M10 (hidden states) and the shared label-table builder (M10, M11).

Truth never reaches a consumer topic (invariant I5): these tables go only to the restricted ``labels.truth``
topic of contract v0, whose consumer view is refused by the contract (``Contract.consumer_schema`` raises).
Every table is validated with ``load_contract("v0").validate`` before it is returned.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

import numpy as np
import pyarrow as pa

from phalanx.dictionary.yamlio import load_yaml
from phalanx.ground.rid import record_ids

from .layout import ACTUATORS, AIRFRAME_NAMES, ENGINE_AUX_NAMES, ENGINE_DELTAS, hidden_entries

__all__ = ["LABELS_TOPIC", "build_label_table", "health_labels", "hidden_state_catalogue"]

LABELS_TOPIC = "labels.truth"
_REPO = Path(__file__).resolve().parents[3]
CATALOGUE_PATH = _REPO / "configs" / "tejas" / "faults" / "hidden_states.yaml"


@lru_cache(maxsize=4)
def hidden_state_catalogue(path: str | None = None) -> Mapping[str, Mapping[str, object]]:
    """NM id -> {class, owner, process, slots} (states + extensions of ``hidden_states.yaml``)."""
    doc = load_yaml(Path(path) if path else CATALOGUE_PATH)
    if doc.get("format") != "phalanx.hidden_states/1":
        raise ValueError("hidden_states.yaml: bad format")
    out = dict(doc["states"])
    out.update(doc.get("extensions", {}))
    return out


def _bias_nm(channel_id: str) -> str:
    for prefix, nm in (
        ("ENG.", "NM.ENG.SENSOR_TRUTH"),
        ("FCS.", "NM.FCS.SENSOR_BIAS"),
        ("AD.", "NM.AD.TRANSDUCER_DRIFT"),
        ("FUEL.", "NM.FUEL.PROBE_DRIFT"),
    ):
        if channel_id.startswith(prefix):
            return nm
    return "NM.SENSOR_BIAS"


_DELTA_NM = {
    "fan_eta": "NM.ENG.FAN_HEALTH",
    "fan_flow": "NM.ENG.FAN_HEALTH",
    "hpc_eta": "NM.ENG.HPC_HEALTH",
    "hpc_flow": "NM.ENG.HPC_HEALTH",
    "hpt_eta": "NM.ENG.HPT_HEALTH",
    "hpt_flow": "NM.ENG.HPT_HEALTH",
    "lpt_eta": "NM.ENG.LPT_HEALTH",
    "lpt_flow": "NM.ENG.LPT_HEALTH",
    "comb_eta": "NM.ENG.FUEL_NOZZLE",
    "nozzle_area": "NM.ENG.NOZZLE_HW",
}
_LIFE_UNITS = {"eot_s": "s", "tamp_s": "s", "src_h": "h"}


def build_label_table(
    rows: Sequence[Mapping[str, object]],
    *,
    tail_no: str,
    dict_version: str,
    dict_hash: str,
    contract=None,
) -> pa.Table:
    """``labels.truth`` table from row dicts with keys label_kind, subject_id, sortie_id, serial_no, t_true,
    t_end, value, units, category, source_module (missing optional keys are null). Validated."""
    from phalanx.dictionary.contract import load_contract

    c = contract or load_contract("v0")
    n = len(rows)

    def col(k: str, t: pa.DataType) -> pa.Array:
        return pa.array([r.get(k) for r in rows], type=t)

    rid = record_ids(
        c,
        LABELS_TOPIC,
        {
            "label_kind": col("label_kind", pa.string()),
            "subject_id": col("subject_id", pa.string()),
            "tail_no": tail_no,
            "sortie_id": col("sortie_id", pa.string()),
            "serial_no": col("serial_no", pa.string()),
            "related_record_id": pa.nulls(n, pa.binary(16)),
            "t_true": np.array([int(r["t_true"]) for r in rows], np.int64),
        },
        n,
    )
    schema = c.schemas[LABELS_TOPIC]
    cols = {
        "record_id": rid,
        "dict_version": pa.array([dict_version] * n, pa.string()),
        "dict_hash": pa.array([dict_hash] * n, pa.string()),
        "label_kind": col("label_kind", pa.string()),
        "subject_id": col("subject_id", pa.string()),
        "tail_no": pa.array([tail_no] * n, pa.string()),
        "sortie_id": col("sortie_id", pa.string()),
        "serial_no": col("serial_no", pa.string()),
        "t_true": pa.array([int(r["t_true"]) for r in rows], pa.int64()),
        "t_end": pa.array([None if r.get("t_end") is None else int(r["t_end"]) for r in rows], pa.int64()),
        "value": pa.array(
            [None if r.get("value") is None else float(r["value"]) for r in rows], pa.float64()
        ),
        "units": col("units", pa.string()),
        "category": col("category", pa.string()),
        "related_record_id": pa.nulls(n, pa.binary(16)),
        "source_module": col("source_module", pa.string()),
    }
    table = pa.Table.from_arrays([cols[f.name] for f in schema], schema=schema)
    c.validate(LABELS_TOPIC, table)
    return table


def health_labels(
    module,
    state: Mapping[str, np.ndarray],
    *,
    t_utc_ns: int,
    tail_no: str,
    sortie_id: str | None,
    dict_version: str,
    dict_hash: str,
    contract=None,
) -> pa.Table:
    """Snapshot of every M10 hidden state as HIDDEN_STATE labels at simulated-UTC time ``t_utc_ns``.

    subject_id = ``<NM id>/<slot>`` (unique per serial and time); value in physical units (normalised port
    values times their reference); category = observability class (report §2).
    """
    cat = hidden_state_catalogue()
    rows: list[dict[str, object]] = []

    def add(nm: str, slot: str, serial: str, value: float, units: str) -> None:
        rows.append(
            {
                "label_kind": "HIDDEN_STATE",
                "subject_id": f"{nm}/{slot}",
                "sortie_id": sortie_id,
                "serial_no": serial,
                "t_true": t_utc_ns,
                "value": float(value),
                "units": units,
                "category": str(cat[nm]["class"]) if nm in cat else None,
                "source_module": "M10",
            }
        )

    deltas = module.engine_deltas(state)
    util = module.hidden_vector(state)
    entries = hidden_entries(module.n_engines)
    for e in range(module.n_engines):
        serial = str(state["eng_serial"][e])
        for j, d in enumerate(ENGINE_DELTAS):
            add(_DELTA_NM[d], d, serial, deltas[e, j], "1")
        for k, name in enumerate(ENGINE_AUX_NAMES):
            ent = entries[e * len(ENGINE_AUX_NAMES) + k]
            add(
                ent.nm_id,
                name,
                serial,
                util[e * len(ENGINE_AUX_NAMES) + k] * ent.reference,
                ent.reference_unit,
            )
        from .module import ENG_LIFE

        for k, name in enumerate(ENG_LIFE.names):
            add("LIFE.ENG", name, serial, state["eng_life"][e, k], _LIFE_UNITS.get(name, "count"))
    off = len(ENGINE_AUX_NAMES) * module.n_engines
    for j, name in enumerate(AIRFRAME_NAMES):
        ent = entries[off + j]
        add(ent.nm_id, name, str(state["comp_serial"][j]), util[off + j] * ent.reference, ent.reference_unit)
    for k, name in enumerate(ACTUATORS):
        add(
            "NM.HYD.ACTUATOR_LEAK",
            name,
            str(state["comp_serial"][len(AIRFRAME_NAMES) + k]),
            state["act"][k],
            "1",
        )
    bias = state["bias_inst"] + state["bias_drift"]
    for c, b in enumerate(module.config.bias_channels):
        add(_bias_nm(b.channel_id), b.channel_id, str(state["sensor_serial"][c]), bias[c], b.si_units)
    from .module import AIR_LIFE

    for k, name in enumerate(AIR_LIFE.names):
        add("LIFE.AIRFRAME", name, tail_no, state["air_life"][k], "s" if name.endswith("_s") else "count")
    return build_label_table(
        rows, tail_no=tail_no, dict_version=dict_version, dict_hash=dict_hash, contract=contract
    )
