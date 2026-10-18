"""Event sourcing of the orders channel (architecture §11.1, AD-16): a run is f(seed, config, dictionary,
order log).

The order log is the world's ``order_log``: every ``order.submit`` event the gateway injected (with its
verdict, so replay needs no observation store). :func:`dump_order_log` / :func:`load_order_log` give a
canonical byte form; :func:`replay` re-injects the events at their times into a fresh session and must
reproduce the live session bit for bit (A4; tested).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from phalanx.core.canonical import length_prefixed
from phalanx.core.events import Event, event_log_digest

ORDER_KIND = "order.submit"


def orders_in(world_log: Sequence[Event]) -> list[Event]:
    """The order log proper: the gateway's ``order.submit`` injections (a world's ``order_log`` also holds the
    builder's initial events, which every fresh session injects itself)."""
    return [e for e in world_log if e.kind == ORDER_KIND]


def dump_order_log(events: Sequence[Event]) -> bytes:
    return b"PHXORD1" + length_prefixed([e.encode() for e in orders_in(events)])


def load_order_log(data: bytes) -> list[Event]:
    if data[:7] != b"PHXORD1":
        raise ValueError("not a Phalanx order log")
    out, pos = [], 7
    while pos < len(data):
        n = int.from_bytes(data[pos : pos + 8], "little")
        out.append(Event.decode(data[pos + 8 : pos + 8 + n]))
        pos += 8 + n
    return out


def order_log_hash(events: Sequence[Event]) -> str:
    return event_log_digest(orders_in(events))


def replay(session: Any, events: Sequence[Event], until: int) -> Any:
    """Inject the logged orders into a fresh ``session`` at their times, then run to ``until`` (kernel ns)."""
    for ev in sorted(orders_in(events), key=lambda e: (e.t_ns, e.seq)):
        session.run_until(ev.t_ns)
        session.world = session.system.inject(
            session.world, [Event(ev.t_ns, ev.kind, ev.target, dict(ev.payload), ev.priority, -1, ev.source)]
        )
    session.run_until(until)
    return session
