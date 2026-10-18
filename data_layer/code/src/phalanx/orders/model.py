"""The order record (architecture §11.1, contract topic ``orders.commands``) and its per-action parameter
schemas.

``Order`` is the typed form of one ``orders.commands`` row. Times are contract times (simulated UTC ns,
AD-38); the gateway converts them to kernel time. ``parameters`` is a JSON object whose schema depends on the
action: the contract leaves per-action schemas to M21 (A-W0.4-14), and they are defined here (JSON-Schema
draft 2020-12) [ASSUMPTION A-W1.8-19: parameter names and shapes].
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import jsonschema

from phalanx.dictionary.contract import Contract
from phalanx.maintenance.records import ORDERS_COMMANDS, rid_hex, rows_to_table

SERVICING_TYPES = ["SRV-L1", "SRV-L2-MINOR", "SRV-L2-MAJOR", "ROH"]
_STR = {"type": "string", "minLength": 1}
_POS_NUM = {"type": "number", "exclusiveMinimum": 0}

ACTION_SCHEMAS: dict[str, dict[str, Any]] = {
    "INSPECT": {
        "properties": {"type": {"enum": ["BORESCOPE", "NDT", "CONDITIONAL"]}, "position": _STR},
        "required": ["type"],
    },
    "TROUBLESHOOT": {
        "properties": {"code": _STR, "position": _STR},
        "anyOf": [{"required": ["code"]}, {"required": ["position"]}],
    },
    "REMOVE_REPLACE": {"properties": {"position": _STR, "install_serial": _STR}, "required": ["position"]},
    "WASH_SERVICE": {
        "properties": {"type": {"enum": ["ENGINE_WASH", "OIL", "HYDRAULIC", "TYRES"]}},
        "required": ["type"],
    },
    "DEFER": {
        "properties": {"job_no": _STR, "limits": _STR, "expiry_hours": _POS_NUM},
        "required": ["job_no", "limits", "expiry_hours"],
    },
    "CANNIBALISE": {
        "properties": {"job_no": _STR, "donor_tail_no": _STR},
        "required": ["job_no", "donor_tail_no"],
    },
    "REQUISITION_SPARES": {
        "properties": {"part_no": _STR, "quantity": {"type": "integer", "minimum": 1}},
        "required": ["part_no", "quantity"],
    },
    "EXPEDITE_SPARES": {"properties": {"demand_no": _STR}, "required": ["demand_no"]},
    "TRANSFER_STOCK": {
        "properties": {
            "part_no": _STR,
            "quantity": {"type": "integer", "minimum": 1},
            "from_base": _STR,
            "to_base": _STR,
        },
        "required": ["part_no", "quantity", "from_base", "to_base"],
    },
    "GROUND": {"properties": {"reason": _STR}, "required": ["reason"]},
    "RELEASE": {"properties": {"reason": _STR}},
    "BRING_FORWARD_SERVICING": {
        "properties": {"servicing": {"enum": SERVICING_TYPES}},
        "required": ["servicing"],
    },
    "DEFER_SERVICING": {
        "properties": {
            "servicing": {"enum": SERVICING_TYPES},
            "extend_hours": _POS_NUM,
            "extend_days": _POS_NUM,
        },
        "required": ["servicing"],
        "anyOf": [{"required": ["extend_hours"]}, {"required": ["extend_days"]}],
    },
    "ASSIGN_SORTIE": {
        "properties": {
            "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
            "sorties": {"type": "integer", "minimum": 0},
            "mission_type": _STR,
        },
        "required": ["date", "sorties"],
    },
    "RESTRICT_USAGE": {
        "properties": {
            "limit": {"enum": ["AB", "G", "NONE"]},
            "value": {"type": "number"},
            "until_days": _POS_NUM,
        },
        "required": ["limit"],
    },
    "EMBODY_MODIFICATION": {"properties": {"mod_id": _STR}, "required": ["mod_id"]},
    "LOAD_SOFTWARE": {"properties": {"sw_config_id": _STR, "lru": _STR}, "required": ["sw_config_id"]},
    "CHANGE_MONITORING_CONFIG": {
        "properties": {
            "filter_codes_add": {"type": "array", "items": _STR},
            "filter_codes_remove": {"type": "array", "items": _STR},
        },
        "anyOf": [{"required": ["filter_codes_add"]}, {"required": ["filter_codes_remove"]}],
    },
}
#: actions that may target a whole base (every tail held there) instead of one tail
FLEET_ACTIONS = frozenset(
    {"GROUND", "RELEASE", "EMBODY_MODIFICATION", "LOAD_SOFTWARE", "CHANGE_MONITORING_CONFIG"}
)
#: actions that act on stock or supply, not on a tail
SUPPLY_ACTIONS = frozenset({"REQUISITION_SPARES", "EXPEDITE_SPARES", "TRANSFER_STOCK"})


def parameter_schema(action: str) -> dict[str, Any]:
    body = ACTION_SCHEMAS[action]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        **body,
    }


class OrderError(ValueError):
    pass


@dataclass(frozen=True)
class Order:
    """One order (contract times in simulated UTC ns)."""

    order_id: str
    issuer_id: str
    issuer_kind: str
    t_issued: int
    t_effective: int
    action: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    priority: str = "ROUTINE"
    target_tail_no: str | None = None
    target_base: str | None = None
    target_lru: str | None = None
    target_serial: str | None = None
    evidence: Sequence[bytes] = ()
    policy_version: str | None = None

    def evidence_hex(self) -> list[str]:
        return [bytes(r).hex() for r in self.evidence]


def check_parameters(order: Order) -> list[str]:
    """Per-action parameter and target checks (empty list = valid)."""
    errs: list[str] = []
    if order.action not in ACTION_SCHEMAS:
        return [f"unknown action {order.action!r}"]
    v = jsonschema.Draft202012Validator(parameter_schema(order.action))
    for e in sorted(v.iter_errors(dict(order.parameters)), key=lambda e: list(e.path)):
        errs.append(f"parameters: {e.message}")
    if order.action in SUPPLY_ACTIONS:
        if order.action == "REQUISITION_SPARES" and not order.target_base:
            errs.append("REQUISITION_SPARES needs target_base")
    elif order.action in FLEET_ACTIONS:
        if not (order.target_tail_no or order.target_base):
            errs.append(f"{order.action} needs target_tail_no or target_base")
    elif not order.target_tail_no:
        errs.append(f"{order.action} needs target_tail_no")
    if order.t_effective < order.t_issued:
        errs.append("t_effective must be >= t_issued")
    return errs


def order_row(order: Order, contract: Contract, *, dict_version: str | None, dict_hash: str | None) -> dict:
    """The orders.commands row (JSON-document form)."""
    row = dict.fromkeys(contract.topics[ORDERS_COMMANDS].field_names)
    row.update(
        record_id=rid_hex(contract, ORDERS_COMMANDS, {"order_id": order.order_id}),
        dict_version=dict_version,
        dict_hash=dict_hash,
        order_id=order.order_id,
        issuer_id=order.issuer_id,
        issuer_kind=order.issuer_kind,
        policy_version=order.policy_version,
        t_issued=int(order.t_issued),
        t_effective=int(order.t_effective),
        target_tail_no=order.target_tail_no,
        target_base=order.target_base,
        target_lru=order.target_lru,
        target_serial=order.target_serial,
        action=order.action,
        parameters=dict(order.parameters),
        priority=order.priority,
        evidence=order.evidence_hex(),
    )
    return row


def contract_errors(
    order: Order, contract: Contract, *, dict_version: str | None = None, dict_hash: str | None = None
) -> list[str]:
    """Contract-schema validation of the orders.commands row (an invalid row never enters the world)."""
    try:
        rows_to_table(
            contract,
            ORDERS_COMMANDS,
            [order_row(order, contract, dict_version=dict_version, dict_hash=dict_hash)],
        )
    except Exception as e:  # ContractViolation, ArrowInvalid, TypeError, KeyError on malformed values
        return [f"contract: {e}"]
    return []


def validate_order(
    order: Order, contract: Contract, *, dict_version: str | None = None, dict_hash: str | None = None
) -> list[str]:
    """Contract-schema validation of the command row plus the per-action checks."""
    return contract_errors(
        order, contract, dict_version=dict_version, dict_hash=dict_hash
    ) + check_parameters(order)


def order_from_row(row: Mapping[str, Any]) -> Order:
    return Order(
        order_id=row["order_id"],
        issuer_id=row["issuer_id"],
        issuer_kind=row["issuer_kind"],
        t_issued=int(row["t_issued"]),
        t_effective=int(row["t_effective"]),
        action=row["action"],
        parameters=dict(row["parameters"] or {}),
        priority=row["priority"],
        target_tail_no=row["target_tail_no"],
        target_base=row["target_base"],
        target_lru=row["target_lru"],
        target_serial=row["target_serial"],
        evidence=tuple(bytes.fromhex(h) for h in row["evidence"] or ()),
        policy_version=row["policy_version"],
    )
