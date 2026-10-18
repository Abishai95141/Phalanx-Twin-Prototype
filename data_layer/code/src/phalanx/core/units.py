"""Units at module boundaries (invariant I3; report §14: pint at module boundaries in validation mode,
stripped to float64 SI arrays in hot loops).

- Every port and parameter declares a unit string that pint parses. It must be **coherent SI** (converts to
  SI base units with factor exactly 1, no offset): ``m``, ``m/s``, ``N``, ``Pa``, ``K``, ``kg/s``,
  ``rad/s``, ``1``. Not ``ft``, ``degC``, ``bar``, ``percent`` or ``deg``.
- The one exception is AD-35 time: ``ns`` is allowed on **integer** ports and parameters (int64 ns ticks).
- Two units are compatible iff their SI base-unit containers are equal. Radians are kept as a base unit
  (pint treats them as dimensionless), so ``rad/s`` and ``Hz`` are *not* interchangeable: angular vs
  cyclic frequency is a classic factor-2*pi defect.
- The registry is built lazily once (``pint.UnitRegistry`` is immutable configuration, not RNG or time).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Any

import numpy as np


class UnitError(ValueError):
    """A unit string is not parseable, or is not coherent SI."""


class UnitMismatchError(UnitError):
    """Values with incompatible units met at a port boundary."""


@lru_cache(maxsize=1)
def ureg():
    import pint

    return pint.UnitRegistry()


@dataclass(frozen=True)
class SIUnit:
    text: str
    base: tuple[tuple[str, str], ...]  # sorted (base unit name, exponent as exact fraction string)
    is_ns: bool = False

    def compatible(self, other: SIUnit) -> bool:
        return self.base == other.base and self.is_ns == other.is_ns


def _base_container(units: Any) -> tuple[tuple[str, str], ...]:
    items = []
    for name, exp in dict(units._units).items():
        fr = Fraction(exp).limit_denominator(1000)
        if fr != 0:
            items.append((str(name), str(fr)))
    return tuple(sorted(items))


@lru_cache(maxsize=4096)
def parse_unit(text: str) -> SIUnit:
    """Parse and check a declared unit string (coherent SI, or ``ns`` for integer time)."""
    if not isinstance(text, str):
        raise UnitError(f"unit must be a str, got {type(text).__name__}")
    u = ureg()
    try:
        unit = u.Unit(text)
        q = (1 * unit).to_base_units()
    except Exception as e:  # pint raises several error types
        raise UnitError(f"unit {text!r} does not parse: {e}") from e
    if text.strip() == "ns":
        return SIUnit(text, _base_container(q.units), is_ns=True)
    if float(q.magnitude) != 1.0:
        raise UnitError(
            f"unit {text!r} is not coherent SI (1 {text} = {q.magnitude} {q.units}); convert first"
        )
    return SIUnit(text, _base_container(q.units))


def check_unit_for_dtype(text: str, dtype: np.dtype) -> SIUnit:
    si = parse_unit(text)
    if si.is_ns and np.dtype(dtype).kind not in "iu":
        raise UnitError("'ns' is reserved for integer time (AD-35); float times are seconds ('s')")
    return si


def units_compatible(a: str, b: str) -> bool:
    return parse_unit(a).compatible(parse_unit(b))


def strip_quantity(value: Any, unit: str, where: str) -> Any:
    """Validation-mode boundary check: a pint Quantity must carry exactly ``unit`` (SI-compatible, factor 1).

    Returns the bare magnitude. Non-Quantity values are returned unchanged (they are SI by contract).
    """
    if not hasattr(value, "units") or not hasattr(value, "magnitude"):
        return value
    want = parse_unit(unit)
    try:
        got_q = (1 * value.units).to_base_units()
        got = SIUnit(str(value.units), _base_container(got_q.units), is_ns=str(value.units) == "nanosecond")
        factor = float(got_q.magnitude)
    except Exception as e:
        raise UnitMismatchError(f"{where}: cannot interpret units {value.units!r}: {e}") from e
    if not want.compatible(got) or (factor != 1.0 and not want.is_ns):
        raise UnitMismatchError(f"{where}: value in {value.units!s} but the port declares {unit!r}")
    return value.magnitude
