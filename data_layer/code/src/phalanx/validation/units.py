"""Unit equivalence for the battery's unit check (pint; registry shared with `phalanx.core.units`).

The battery never converts units (AD-40): a record's declared unit must be **equivalent** to the configured
one, i.e. the same unit under another spelling (``lb/hr`` = ``lb/h`` = ``pound / hour``, ``%`` = ``percent``,
``degree`` = ``deg``). Units that are merely dimensionally compatible are rejected, because their values
differ: ``kg/s`` vs ``lb/h`` (factor 7,937), ``K`` vs ``degC`` (offset 273.15), ``rad`` vs ``deg``,
``percent`` vs ``dimensionless`` (factor 100).

Rule: two units are equivalent iff 1 and 0 of each map to the same SI base quantity, with identical base-unit
containers (radian is kept as a base unit, as in `phalanx.core.units`, so ``rad`` is not ``dimensionless``)
and equal magnitudes to 1e-12 relative.
"""

from __future__ import annotations

from functools import lru_cache

from phalanx.core.units import ureg

__all__ = ["UnitSpellingError", "units_equivalent"]


class UnitSpellingError(ValueError):
    """A unit string that pint cannot parse."""


@lru_cache(maxsize=1024)
def _base(text: str) -> tuple[tuple[tuple[str, float], ...], float, float]:
    u = ureg()
    try:
        one = u.Quantity(1.0, text).to_base_units()
        zero = u.Quantity(0.0, text).to_base_units()
    except Exception as e:  # pint raises several unrelated exception types for bad input
        raise UnitSpellingError(f"unit {text!r} does not parse in pint: {e}") from e
    container = tuple(sorted((str(k), float(v)) for k, v in dict(one.units._units).items()))
    return container, float(one.magnitude), float(zero.magnitude)


def units_equivalent(a: str, b: str) -> bool:
    """True iff ``a`` and ``b`` denote the same unit (same base units, factor 1, same offset)."""
    if a == b:
        return True
    ca, one_a, zero_a = _base(a)
    cb, one_b, zero_b = _base(b)
    if ca != cb:
        return False
    tol = 1e-12 * max(abs(one_a), abs(one_b))
    return abs(one_a - one_b) <= tol and abs(zero_a - zero_b) <= max(tol, 1e-12)
