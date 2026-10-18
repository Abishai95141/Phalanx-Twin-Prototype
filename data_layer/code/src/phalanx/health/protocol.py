"""Cross-module event protocol helpers (AD-44, AD-48.1; ``configs/interfaces/w1_events.yaml``).

**Encoding (AD-48.1).** Every catalogued key is a **plain top-level payload key**. :func:`plain_payload` turns
a document into a core event payload: a value the event queue holds natively (str, bool, int, float, a flat
list of one scalar type, a numeric or string array) is stored as itself; any other value (None, a mapping, a
nested or mixed list) is stored as its canonical JSON text, and its key is listed in the reserved key
:data:`JSON_KEYS` so that :func:`read_payload` restores it exactly. Inbound events are read by
:func:`read_payload`. The W1 ``{"doc": <canonical JSON>}`` encoding of the operations layer is retired: the
key ``doc`` is reserved and :func:`read_payload` rejects it. The operations layer (M18, M21) requires
whole-second event times (A-W1.8-14, :func:`ceil_second`).

**Positions.** M18 tracks units by installed position (``configs/tejas/params/M18/catalogue.yaml``,
SYNTHETIC). :data:`POSITION_STATES` maps each position to the M10 hidden states that leave with the unit, and
to the M14 LRU whose test offsets belong to the unit (A-W1.5-19). :data:`LATENT_ACTIONS` maps an M18
maintenance action to the M11 latent-defect action vocabulary of ``configs/tejas/faults/catalogue.yaml``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

import numpy as np

from phalanx.core.canonical import canonical_json

__all__ = [
    "JSON_KEYS",
    "LATENT_ACTIONS",
    "NS",
    "POSITION_STATES",
    "RETIRED_DOC_KEY",
    "SERVICE_ACTIONS",
    "PayloadError",
    "ceil_second",
    "jsonable",
    "plain_payload",
    "read_payload",
]

NS = 1_000_000_000

#: M18 position -> what leaves with the unit:
#: ``engine:<e>`` the whole engine e; ``eng:<e>:<field>`` one engine field; ``air:<name>`` an airframe item;
#: ``lru:<name>`` the M14 LRU (its test offsets are drawn per unit serial). SYNTHETIC map (A-W1.5-19).
POSITION_STATES: Mapping[str, tuple[str, ...]] = {
    "ENG": ("engine:0",),
    "FADEC": ("eng:0:aux_fadec_hw", "lru:FADEC"),
    "JFS": ("air:jfs_health", "air:jfs_drag"),
    "AMAGB": ("air:amagb_wear",),
    "HYDP1": ("air:hyd1_pump_wear", "air:hyd1_compensator", "air:hyd1_ext_leak"),
    "HYDP2": ("air:hyd2_pump_wear", "air:hyd2_compensator", "air:hyd2_ext_leak"),
    "GEN": ("air:gen_health",),
    "DFCC": ("lru:DFCC",),
    "ADC": ("lru:ADC",),
    "INGPS": ("lru:INGPS",),
    "RADAR": ("lru:RADAR",),
    "FQGS": ("air:fuel_probe_drift", "lru:ECFM_C"),
    "OBOGS": ("air:lss_obogs_sieve",),
    "BCU": (),
    "BRK_L": ("air:brake_wear_l",),
    "BRK_R": ("air:brake_wear_r",),
    "TYR_L": ("air:tyre_wear_l", "air:tyre_p_loss_l"),
    "TYR_R": ("air:tyre_wear_r", "air:tyre_p_loss_r"),
    "CHUTE": ("air:chute_life",),
}

#: (M18 action, position or "*") -> M11 latent-defect action (catalogue ``onset.actions``)
LATENT_ACTIONS: Mapping[tuple[str, str], str] = {
    ("RR", "ENG"): "engine_install",
    ("RR", "AMAGB"): "amagb_maintenance",
    ("HYDRAULIC", "*"): "hyd_servicing",
    ("SWLOAD", "*"): "software_load",
}

#: M18 servicing action -> M10 ``service`` targets
SERVICE_ACTIONS: Mapping[str, tuple[str, ...]] = {
    "OIL": ("engine_oil",),
    "HYDRAULIC": ("hyd_fluid", "hyd_filters", "accumulators"),
    "TYRES": ("tyres", "struts"),
}


def ceil_second(t_ns: int) -> int:
    """The first whole second at or after ``t_ns`` (operations-layer events are whole seconds)."""
    return -(-int(t_ns) // NS) * NS


def jsonable(v: Any) -> Any:
    """Plain JSON value: numpy scalars and arrays to Python, bytes to hex."""
    if isinstance(v, np.ndarray):
        return jsonable(v.tolist())
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, bytes):
        return v.hex()
    if isinstance(v, Mapping):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [jsonable(x) for x in v]
    return v


#: reserved payload key: the sorted names of the keys whose values are canonical JSON text (AD-48.1)
JSON_KEYS = "json_keys"
#: reserved: the key of the retired W1 wrapper (a payload carrying it is the ``{"doc": <JSON>}`` encoding)
RETIRED_DOC_KEY = "doc"
#: a top-level payload key (core event payloads are flat array trees; ``phalanx.core.state`` key rule)
_KEY = re.compile(r"^[A-Za-z0-9_.\-]+$")
_INT64 = (-(2**63), 2**63 - 1)


class PayloadError(ValueError):
    """A payload that does not follow the AD-48.1 plain-key encoding."""


def _native(v: Any) -> bool:
    """True if the event payload holds ``v`` natively and :func:`jsonable` gives it back unchanged in type."""
    if isinstance(v, np.ndarray):
        return v.dtype.kind in "biufU"
    if isinstance(v, bool | np.bool_ | str | float | np.floating):
        return True
    if isinstance(v, int | np.integer):
        return _INT64[0] <= int(v) <= _INT64[1]
    if isinstance(v, list | tuple):
        kinds = set()
        for x in v:
            if isinstance(x, bool | np.bool_):
                kinds.add("b")
            elif isinstance(x, int | np.integer) and _INT64[0] <= int(x) <= _INT64[1]:
                kinds.add("i")
            elif isinstance(x, float | np.floating):
                kinds.add("f")
            elif isinstance(x, str):
                kinds.add("U")
            else:
                return False
        return len(kinds) <= 1
    return False


def plain_payload(doc: Mapping[str, Any]) -> dict[str, Any]:
    """AD-48.1: ``doc`` as plain top-level payload keys (module docstring). ``read_payload(Event(...,
    plain_payload(doc)).payload) == jsonable(doc)`` for every JSON document (tuples come back as lists)."""
    out: dict[str, Any] = {}
    js: list[str] = []
    for k, v in doc.items():
        if not isinstance(k, str) or not _KEY.match(k):
            raise PayloadError(f"payload key {k!r} is not a plain key ([A-Za-z0-9_.-]+)")
        if k in (JSON_KEYS, RETIRED_DOC_KEY):
            raise PayloadError(f"{k!r} is a reserved payload key (AD-48.1)")
        if _native(v):
            out[k] = list(v) if isinstance(v, tuple) else v
        else:
            out[k] = canonical_json(jsonable(v)).decode()
            js.append(k)
    if js:
        out[JSON_KEYS] = sorted(js)
    return out


def read_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """An inbound payload as plain Python values (the inverse of :func:`plain_payload`).

    Keys listed in :data:`JSON_KEYS` are decoded from their JSON text; every other value is unwrapped from its
    array. A payload carrying :data:`RETIRED_DOC_KEY` (the W1 ``{"doc": <JSON>}`` encoding, retired by
    AD-48.1) raises :class:`PayloadError`: a consumer reads plain keys only."""
    if RETIRED_DOC_KEY in payload:
        raise PayloadError("retired {'doc': <JSON>} payload encoding (AD-48.1: plain top-level keys)")
    js = payload.get(JSON_KEYS)
    names = set() if js is None else {str(x) for x in np.atleast_1d(np.asarray(js)).tolist()}
    missing = names - set(payload)
    if missing:
        raise PayloadError(f"{JSON_KEYS} names absent keys {sorted(missing)}")
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if k == JSON_KEYS:
            continue
        if k in names:
            text = v.item() if isinstance(v, np.ndarray) else v
            out[str(k)] = json.loads(str(text))
        else:
            out[str(k)] = jsonable(v)
    return out
