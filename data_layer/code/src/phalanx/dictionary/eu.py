"""Engineering-unit <-> SI conversion for dictionary channels (for M13 and the other W1 modules).

Truth and sensor physics run in coherent SI (core invariant I3). Channels report engineering units (EU): ft,
knot, psi, degC, %N1 and so on. Each numeric channel converts with one affine map

    si = eu * scale + offset          eu = (si - offset) / scale

whose SI unit is fixed by the channel's quantity (:data:`SI_UNITS`). ``scale`` and ``offset`` come from
pint (offsets only for degC/degF -> K), except for % of rated speed: ``ENG.N1``/``ENG.N2`` convert through
the ``channel_reference`` constant that names them in ``eu_reference_for`` (100 % = 13,270 / 16,810 rpm),
so %N1 <-> rad/s. Discrete, enum and code values are dimensionless codes and convert with the identity.
Text and media channels, and a % of rated speed channel with no reference speed, have no numeric SI form
and raise :class:`EUConversionError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from .units import registry

__all__ = ["SI_UNITS", "EUConversion", "EUConversionError", "build_conversions"]


class EUConversionError(ValueError):
    """A channel has no numeric SI form (text, media, or % of rated speed without a reference speed)."""


#: dictionary quantity -> coherent SI unit of the truth value (None: no numeric SI form)
SI_UNITS: dict[str, str | None] = {
    "angle": "rad",
    "angular_rate": "rad/s",
    "rotational_speed": "rad/s",
    "speed_percent": "rad/s",  # through the reference speed
    "position_percent": "1",
    "command_percent": "1",
    "level_percent": "1",
    "wear_percent": "1",
    "concentration": "1",
    "temperature": "K",
    "pressure": "Pa",
    "mass_flow": "kg/s",
    "mass": "kg",
    "volume": "m**3",
    "length": "m",
    "altitude": "m",
    "airspeed": "m/s",
    "speed": "m/s",
    "vertical_speed": "m/s",
    "specific_force": "m/s**2",
    "force": "N",
    "vibration_velocity": "m/s",
    "voltage": "V",
    "current": "A",
    "frequency": "Hz",
    "charge": "C",
    "energy": "J",
    "time": "s",
    "life_time": "s",
    "life_count": "1",
    "count": "1",
    "mach": "1",
    "strain": "1",
    "discrete": "1",
    "enum": "1",
    "code": "1",
    "text": None,
    "media": None,
}
_IDENTITY = frozenset({"discrete", "enum", "code"})


@dataclass(frozen=True)
class EUConversion:
    """The affine EU <-> SI map of one channel: ``si = eu * scale + offset``."""

    channel_id: str
    eu_units: str
    si_units: str
    scale: float
    offset: float = 0.0
    reference: str | None = None  # "set.name" of the reference-speed constant (% of rated speed only)

    def to_si(self, values: Any) -> Any:
        """EU -> SI on scalars or arrays (float64; shape preserved)."""
        return np.asarray(values, dtype=np.float64) * self.scale + self.offset

    def to_eu(self, values: Any) -> Any:
        """SI -> EU on scalars or arrays (float64; shape preserved). Exact inverse of :meth:`to_si` up to
        float rounding."""
        return (np.asarray(values, dtype=np.float64) - self.offset) / self.scale


def _affine(eu_units: str, si_units: str) -> tuple[float, float]:
    ureg = registry()
    offset = float(ureg.Quantity(0.0, eu_units).to(si_units).magnitude)
    if offset != 0.0:  # degC, degF: offset units; the scale is that of the matching delta unit
        return float(ureg.Quantity(1.0, f"delta_{eu_units}").to(si_units).magnitude), offset
    return float(ureg.Quantity(1.0, eu_units).to(si_units).magnitude), 0.0


def build_conversions(content: Mapping[str, Any]) -> dict[str, EUConversion | EUConversionError]:
    """{channel_id: EUConversion, or the EUConversionError to raise} for every channel of a compiled
    dictionary."""
    ureg = registry()
    refs: dict[str, tuple[str, float]] = {}  # param_id -> (constant path, rad/s at 100 %)
    for set_name, entries in content["constants"].items():
        for cname, c in entries.items():
            for pid in c.get("eu_reference_for") or ():
                rad_s = float(ureg.Quantity(c["value"], c["units"]).to("rad/s").magnitude)
                refs[pid] = (f"{set_name}.{cname}", rad_s)
    out: dict[str, EUConversion | EUConversionError] = {}
    for cid, ch in content["channels"].items():
        q, units = ch["quantity"], ch["units"]
        si = SI_UNITS.get(q)
        if si is None:
            out[cid] = EUConversionError(f"{cid}: quantity {q!r} has no numeric SI form")
        elif q in _IDENTITY:
            out[cid] = EUConversion(cid, units, si, 1.0)
        elif q == "speed_percent":
            ref = refs.get(ch["param_id"])
            if ref is None:
                out[cid] = EUConversionError(
                    f"{cid}: % of rated speed with no reference speed (no constants entry names "
                    f"{ch['param_id']} in eu_reference_for; the rated speed is not public)"
                )
            else:
                out[cid] = EUConversion(cid, units, si, ref[1] / 100.0, 0.0, ref[0])
        else:
            scale, offset = _affine(units, si)
            out[cid] = EUConversion(cid, units, si, scale, offset)
    return out
