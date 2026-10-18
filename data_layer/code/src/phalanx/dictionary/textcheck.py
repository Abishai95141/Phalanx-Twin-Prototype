"""Checks that a value claimed as verbatim-from-inventory (provenance ``inv``) really appears in the
inventory text.

This is the anti-fabrication guard of the dictionary (RULES.md rule 3, "never invent a parameter value"): a
number or unit can carry the provenance ``inv`` only if the inventory row literally contains it, or a recorded
literal token (``inv_tokens``) that it converts from (for example ``2 mg`` -> 0.002 g). Anything else must
cite a rule.
"""

from __future__ import annotations

import math
import re

__all__ = [
    "ACQ_GROUPS",
    "BUS_GROUPS",
    "FIELD_COLUMNS",
    "UNIT_TOKENS",
    "acq_group_for",
    "bus_group_for",
    "contains_number",
    "marked_assumption",
    "numbers_in",
    "unit_justified",
]

_NUM_RE = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    """Absolute values of the numbers written in ``text`` (thousands separators allowed)."""
    out = []
    for m in _NUM_RE.finditer(text or ""):
        tok = m.group(0).replace(",", "")
        try:
            out.append(abs(float(tok)))
        except ValueError:
            continue
    return out


def contains_number(text: str, value: float) -> bool:
    """True if ``|value|`` is written in ``text`` (relative tolerance 1e-9)."""
    v = abs(float(value))
    return any(math.isclose(v, n, rel_tol=1e-9, abs_tol=1e-12) for n in numbers_in(text))


#: pint unit string -> inventory unit spellings that justify it
UNIT_TOKENS: dict[str, tuple[str, ...]] = {
    "deg": ("deg",),
    "deg/s": ("deg/s",),
    "degC": ("degC",),
    "degF": ("degF",),
    "psi": ("psia", "psid", "psi"),
    "lb/hr": ("lb/h",),
    "percent": ("%",),
    "in/s": ("in/s",),
    "mbar": ("mbar",),
    "ft": ("ft",),
    "knot": ("kt",),
    "ft/min": ("ft/min",),
    "pound_force/foot**2": ("psf",),
    "ft/s": ("ft/s",),
    "standard_gravity": ("g",),
    "rpm": ("rpm",),
    "bar": ("bar",),
    "kg": ("kg",),
    "V": ("V",),
    "Hz": ("Hz",),
    "A": ("A",),
    "A*hour": ("Ah",),
    "count": ("count",),
    "hour": ("h",),
    "L": ("L",),
    "kPa": ("kPa",),
    "mm": ("mm",),
    "lbf": ("lbf",),
    "microstrain": ("microstrain",),
    "ppm": ("ppm",),
    "MJ": ("MJ",),
    "s": ("s",),
}
_DIMLESS_TOKENS = (
    "0/1",
    "bits",
    "bit-packed",
    "enum",
    "code",
    "codes",
    "records",
    "strings",
    "grade",
    "x4",
    "units",
)


def _has_token(text: str, token: str) -> bool:
    pattern = r"(?<![A-Za-z0-9/])" + re.escape(token) + r"(?![A-Za-z0-9/])"
    return re.search(pattern, text or "") is not None


def unit_justified(units: str, inventory_units: str, token: str | None = None) -> bool:
    """True if the inventory unit text justifies ``units`` (or the recorded literal ``token``)."""
    text = inventory_units or ""
    if token is not None:
        return token in text
    if units == "dimensionless":
        return text.strip() in ("", "-") or any(_has_token(text, t) for t in _DIMLESS_TOKENS)
    return any(_has_token(text, t) for t in UNIT_TOKENS.get(units, ()))


#: inventory rate_group_acquisition text -> acquisition group
ACQ_GROUPS: dict[str, str] = {
    "FCS80": "FCS80",
    "FCS80 (into DFCC via RS-422)": "FCS80",
    "FADEC-INT (50-67 Hz)": "FADEC-INT",
    "LRU-INT": "LRU-INT",
    "LRU-INT (1-10 Hz)": "LRU-INT-SLOW",
    "LRU-INT (INS 100-2000 Hz)": "LRU-INT-INS",
    "LRU-INT (model 200-500 Hz)": "LRU-INT-MODEL",
    "EVT (edge-detected in owning LRU)": "EVT",
    "EVT": "EVT",
    "SORTIE": "SORTIE",
    "INSP (ground)": "INSP",
    "FTI (64-800 Hz)": "FTI",
    "HF (2.5-10 kHz raw)": "HF",
    "ECMS10": "ECMS10",
    "video": "VIDEO",
}

#: inventory rate_group_bus text -> (bus group, producer update group)
BUS_GROUPS: dict[str, tuple[str | None, str | None]] = {
    "AV50 poll of DFCC buffer updated at FCS40": ("AV50", "FCS40"),
    "AV50": ("AV50", None),
    "AV25": ("AV25", None),
    "AV25 (+ FCS40 status)": ("AV25", None),
    "AV12.5": ("AV12.5", None),
    "AV6.25": ("AV6.25", None),
    "SLOW1": ("SLOW1", None),
    "SLOW1 (features)": ("SLOW1", None),
    "EVT (carried in AV12.5 status words)": ("AV12.5", None),
    "FCS40": ("AV50", "FCS40"),
    "FTI PCM / telemetry": ("FTI", None),
    "download": ("SORTIE", None),
    "none": (None, None),
    "none (FADEC->CDR path assumed)": (None, None),
    "video": ("VIDEO", None),
}


def acq_group_for(inventory_text: str) -> str | None:
    return ACQ_GROUPS.get((inventory_text or "").strip())


def bus_group_for(inventory_text: str) -> tuple[str | None, str | None] | None:
    return BUS_GROUPS.get((inventory_text or "").strip())


#: provenance field -> inventory columns its value is read from (an 'inv' claim on a field whose column
#: text is marked ASSUMPTION must cite R-INV-FIELD-ASSUMPTION instead)
FIELD_COLUMNS: dict[str, tuple[str, ...]] = {
    "quantity": ("physical_quantity",),
    "units": ("units",),
    "signal": ("measurement_class",),
    "sensor_type": ("origin_sensor_type",),
    "source_lru": ("origin_lru",),
    "acq_lru": ("origin_lru",),
    "expansion": ("redundancy",),
    "range": ("range",),
    "native_step": ("native_resolution",),
    "recorder_lsb": ("recommended_quantization",),
    "rates.acquisition": ("rate_group_acquisition", "native_rate_hz"),
    "rates.bus": ("rate_group_bus", "bus_rate_hz"),
    "rates.producer": ("rate_group_bus", "bus_rate_hz"),
    "sink_group": ("rate_group_record", "recorder_rate_hz"),
}


def marked_assumption(inventory: dict[str, str] | object, field: str) -> bool:
    """True if the inventory columns behind ``field`` mark their text as an ASSUMPTION."""
    cols = FIELD_COLUMNS.get(field, ())
    return any("ASSUMPTION" in inventory[c] for c in cols)  # type: ignore[index]
