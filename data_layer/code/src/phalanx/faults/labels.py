"""Restricted ``labels.truth`` FAULT records of M11 (the fault schedule; architecture §12, I5).

One label per fault instance (contract v0 field meanings): subject_id = the fault id
``<fault-mode id>#<instance>`` (``@<key>`` appended for a keyed instance: the sensor channel of a scripted
sensor fault or the M10 trigger), t_true = onset (simulated UTC), t_end = clear time (null while active or for
permanent state changes), value = severity, category = the fault mode id, serial_no = the engine serial for
engine modes (null otherwise).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pyarrow as pa

from phalanx.health.labels import build_label_table

__all__ = ["fault_labels"]


def fault_labels(
    module,
    state: Mapping[str, np.ndarray],
    *,
    epoch_utc_ns: int,
    tail_no: str,
    dict_version: str,
    dict_hash: str,
    contract=None,
) -> pa.Table:
    """FAULT labels of every instance in ``state`` (validated against contract v0 ``labels.truth``)."""
    rows = []
    serials = module.config.engine_serials
    for j in range(state["inst_mode"].size):
        mode = module.config.catalogue[module.config.mode_ids[int(state["inst_mode"][j])]]
        key = str(state["inst_key"][j])
        engine = int(state["inst_engine"][j])
        serial = serials[engine] if mode.subsystem == "engine" and engine < len(serials) else None
        t1 = int(state["inst_t1"][j])
        rows.append(
            {
                "label_kind": "FAULT",
                "subject_id": f"{mode.id}#{j}" + (f"@{key}" if key else ""),  # unique per run
                "sortie_id": str(state["inst_sortie"][j]) or None,
                "serial_no": serial,
                "t_true": epoch_utc_ns + int(state["inst_t0"][j]),
                "t_end": epoch_utc_ns + t1 if t1 >= 0 else None,
                "value": float(state["inst_sev"][j]),
                "units": "1",
                "category": mode.id,
                "source_module": "M11",
            }
        )
    return build_label_table(
        rows, tail_no=tail_no, dict_version=dict_version, dict_hash=dict_hash, contract=contract
    )
