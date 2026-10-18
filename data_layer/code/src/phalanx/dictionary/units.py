"""Unit checking for dictionary channels with pint (architecture I3; brief W0.3 A4).

A channel's unit must (1) parse in pint, (2) have the dimensionality of its declared quantity, and (3) be one
of the quantity's allowed engineering units. Step (3) is what separates, for example, an angle (deg) from a
percentage or a count, which pint treats as equally dimensionless.
"""

from __future__ import annotations

from functools import lru_cache

import pint

from .schema import QUANTITIES

__all__ = ["check_unit", "registry", "to_si_factor"]


@lru_cache(maxsize=1)
def registry() -> pint.UnitRegistry:
    """The process-wide pint registry (constructed once; read-only use)."""
    return pint.UnitRegistry()


@lru_cache(maxsize=512)
def _unit(text: str) -> pint.Unit:
    return registry().Unit(text)


def check_unit(quantity: str, units: str) -> list[str]:
    """Problems with ``units`` for ``quantity`` (empty list = OK)."""
    if quantity not in QUANTITIES:
        return [f"unknown quantity {quantity!r}"]
    ref, allowed = QUANTITIES[quantity]
    try:
        u = _unit(units)
    except Exception as exc:  # pint raises several unrelated exception types for bad input
        return [f"unit {units!r} does not parse in pint ({type(exc).__name__}: {exc})"]
    errors = []
    if u.dimensionality != _unit(ref).dimensionality:
        errors.append(
            f"unit {units!r} has dimensionality {dict(u.dimensionality)} but quantity {quantity!r} needs "
            f"{dict(_unit(ref).dimensionality)}"
        )
    if not any(u == _unit(a) for a in allowed):
        errors.append(
            f"unit {units!r} is not an allowed unit for quantity {quantity!r} (allowed: {list(allowed)})"
        )
    return errors


def to_si_factor(units: str) -> float | None:
    """Multiplicative factor from ``units`` to SI base units, or None for offset units (degC, degF)."""
    u = _unit(units)
    q = registry().Quantity(1.0, u)
    try:
        return float(q.to_base_units().magnitude)
    except pint.errors.OffsetUnitCalculusError:
        return None
