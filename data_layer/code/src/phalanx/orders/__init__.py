"""M21 Orders and decision interface (architecture §6 M21, §11.1).

Public API (see README.md): :class:`~phalanx.orders.model.Order` and the per-action parameter schemas;
:class:`~phalanx.orders.gateway.OrderGateway`; :class:`~phalanx.orders.module.OrdersModule` (in-simulation
registry) and :class:`~phalanx.orders.module.RecordSink`; :class:`~phalanx.orders.epochs.DecisionCalendar`;
authority and airworthiness rules; reference policies (:mod:`~phalanx.orders.policies`); order-log replay
(:mod:`~phalanx.orders.replay`).
"""

from .epochs import DecisionCalendar
from .gateway import OrderGateway, SubmitResult
from .model import ACTION_SCHEMAS, Order, check_parameters, order_row, validate_order
from .module import OrdersModule, RecordSink
from .policies import (
    ConditionBasedPolicy,
    PolicyContext,
    ScheduledPolicy,
    StatusQuoPolicy,
    fleet_view_from_records,
)
from .rules import Authority, TechLogFacts, airworthiness, load_authority

__all__ = [
    "ACTION_SCHEMAS",
    "Authority",
    "ConditionBasedPolicy",
    "DecisionCalendar",
    "Order",
    "OrderGateway",
    "OrdersModule",
    "PolicyContext",
    "RecordSink",
    "ScheduledPolicy",
    "StatusQuoPolicy",
    "SubmitResult",
    "TechLogFacts",
    "airworthiness",
    "check_parameters",
    "fleet_view_from_records",
    "load_authority",
    "order_row",
    "validate_order",
]
