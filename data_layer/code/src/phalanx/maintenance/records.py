"""Contract rows for the operations layer (maint.records, orders.*, labels.truth) and their Arrow tables.

Rows are built as JSON documents (record_id and record_id lists as lower-case hex, json_object as a dict)
whose field set is taken from the frozen contract spec (never hand-written, W1_interfaces §4). ``record_id``
follows the contract rule (A-W0.4-2) through :func:`phalanx.ground.rid.record_id`. Tables are built and
validated with the contract's own JSON <-> Arrow mapping, so every batch that leaves M18/M21 is checked (A6).

The record version rule for maint.records: ``record_key`` is the natural identity (job number, demand number,
serial number, ...); every status change emits a new ``record_version`` (A-W0.4-13).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Any

import pyarrow as pa

from phalanx.dictionary.contract import Contract, load_contract
from phalanx.dictionary.contract.jsonschema_gen import json_docs_to_table
from phalanx.ground.rid import record_id

MAINT = "maint.records"
ORDERS_COMMANDS = "orders.commands"
ORDERS_STATUS = "orders.status"
LABELS = "labels.truth"


@lru_cache(maxsize=4)
def contract_v0() -> Contract:
    return load_contract("v0")


def _blank(contract: Contract, topic: str) -> dict[str, Any]:
    return dict.fromkeys(contract.topics[topic].field_names)


def rid_hex(contract: Contract, topic: str, values: Mapping[str, Any]) -> str:
    return record_id(contract, topic, values).hex()


def maint_row(
    contract: Contract,
    *,
    dict_version: str,
    dict_hash: str,
    record_type: str,
    record_key: str,
    record_version: int,
    t_event: int,
    t_ingest: int,
    **fields: Any,
) -> dict[str, Any]:
    """One maint.records row (JSON document form). Unknown field names raise."""
    row = _blank(contract, MAINT)
    unknown = sorted(set(fields) - set(row))
    if unknown:
        raise KeyError(f"maint.records has no fields {unknown}")
    row.update(fields)
    row.update(
        dict_version=dict_version,
        dict_hash=dict_hash,
        record_type=record_type,
        record_key=record_key,
        record_version=int(record_version),
        t_event=int(t_event),
        t_ingest=int(t_ingest),
        provenance="direct",
    )
    if row["evidence_record_ids"] is None:
        row["evidence_record_ids"] = []
    row["record_id"] = rid_hex(
        contract,
        MAINT,
        {"record_type": record_type, "record_key": record_key, "record_version": int(record_version)},
    )
    return row


def orders_status_row(
    contract: Contract,
    *,
    dict_version: str,
    dict_hash: str,
    order_id: str,
    status_seq: int,
    status: str,
    t_status: int,
    reason: str | None = None,
    result_record_ids: Iterable[str] = (),
) -> dict[str, Any]:
    row = _blank(contract, ORDERS_STATUS)
    row.update(
        dict_version=dict_version,
        dict_hash=dict_hash,
        order_id=order_id,
        status_seq=int(status_seq),
        status=status,
        reason=reason,
        t_status=int(t_status),
        result_record_ids=list(result_record_ids),
    )
    row["record_id"] = rid_hex(contract, ORDERS_STATUS, {"order_id": order_id, "status_seq": int(status_seq)})
    return row


def label_row(
    contract: Contract,
    *,
    dict_version: str,
    dict_hash: str,
    label_kind: str,
    subject_id: str,
    t_true: int,
    source_module: str,
    tail_no: str | None = None,
    sortie_id: str | None = None,
    serial_no: str | None = None,
    related_record_id: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    row = _blank(contract, LABELS)
    unknown = sorted(set(fields) - set(row))
    if unknown:
        raise KeyError(f"labels.truth has no fields {unknown}")
    row.update(fields)
    row.update(
        dict_version=dict_version,
        dict_hash=dict_hash,
        label_kind=label_kind,
        subject_id=subject_id,
        t_true=int(t_true),
        source_module=source_module,
        tail_no=tail_no,
        sortie_id=sortie_id,
        serial_no=serial_no,
        related_record_id=related_record_id,
    )
    row["record_id"] = rid_hex(
        contract,
        LABELS,
        {
            "label_kind": label_kind,
            "subject_id": subject_id,
            "tail_no": tail_no,
            "sortie_id": sortie_id,
            "serial_no": serial_no,
            "related_record_id": None if related_record_id is None else bytes.fromhex(related_record_id),
            "t_true": int(t_true),
        },
    )
    return row


def rows_to_table(contract: Contract, topic: str, rows: Iterable[Mapping[str, Any]]) -> pa.Table:
    """JSON-document rows -> validated Arrow table with the full contract schema of ``topic``."""
    table = json_docs_to_table(contract, topic, list(rows), audience="full")
    contract.validate(topic, table)
    return table
