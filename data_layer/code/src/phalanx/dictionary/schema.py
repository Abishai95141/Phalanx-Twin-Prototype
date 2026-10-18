"""Vocabularies and JSON Schemas for the M01 dictionary sources, tables and compiled channels.

The schemas validate *structure and types*; the semantic checks (units vs quantity, word fit, collisions,
orphans, provenance coverage) live in :mod:`phalanx.dictionary.validate`.
"""

from __future__ import annotations

import re
from typing import Any

from jsonschema import Draft202012Validator

__all__ = [
    "BASES",
    "ENCODINGS",
    "FORMAT_COMPILED",
    "FORMAT_SOURCE",
    "LIMIT_KINDS",
    "PRESSURE_REFS",
    "PROV_FIELDS",
    "QUANTITIES",
    "ROLES",
    "SIGNALS",
    "TAG_CLASSES",
    "TRANSPORTS",
    "core_tag_error",
    "parse_tag_classes",
    "rule_is_proxy",
    "rule_needs_register",
    "schema_errors",
]

FORMAT_SOURCE = "phalanx.dictionary.source/1"
FORMAT_COMPILED = "phalanx.dictionary/1"

#: quantity -> (reference unit for the dimensionality check, allowed engineering units)
QUANTITIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "angle": ("deg", ("deg", "rad")),
    "angular_rate": ("deg/s", ("deg/s", "rad/s")),
    "rotational_speed": ("rpm", ("rpm",)),
    "speed_percent": ("percent", ("percent",)),
    "position_percent": ("percent", ("percent",)),
    "command_percent": ("percent", ("percent",)),
    "level_percent": ("percent", ("percent",)),
    "wear_percent": ("percent", ("percent",)),
    "concentration": ("percent", ("percent", "ppm")),
    "temperature": ("degC", ("degC", "K", "degF")),
    "pressure": ("Pa", ("mbar", "bar", "psi", "kPa", "Pa", "pound_force/foot**2")),
    "mass_flow": ("kg/s", ("lb/hr", "kg/s", "kg/hr")),
    "mass": ("kg", ("kg", "lb")),
    "volume": ("L", ("L",)),
    "length": ("m", ("mm", "m", "in", "ft")),
    "altitude": ("ft", ("ft", "m")),
    "airspeed": ("knot", ("knot", "m/s")),
    "speed": ("m/s", ("ft/s", "m/s", "knot")),
    "vertical_speed": ("ft/min", ("ft/min", "ft/s", "m/s")),
    "specific_force": ("standard_gravity", ("standard_gravity", "ft/s**2", "m/s**2")),
    "force": ("N", ("lbf", "N")),
    "vibration_velocity": ("in/s", ("in/s", "mm/s")),
    "voltage": ("V", ("V",)),
    "current": ("A", ("A",)),
    "frequency": ("Hz", ("Hz",)),
    "charge": ("A*hour", ("A*hour",)),
    "energy": ("MJ", ("MJ", "kJ", "J")),
    "time": ("s", ("s", "hour")),
    "life_time": ("hour", ("hour",)),
    "life_count": ("count", ("count",)),
    "count": ("count", ("count",)),
    "mach": ("dimensionless", ("dimensionless",)),
    "strain": ("microstrain", ("microstrain",)),
    "discrete": ("dimensionless", ("dimensionless",)),
    "enum": ("dimensionless", ("dimensionless",)),
    "code": ("dimensionless", ("dimensionless",)),
    "text": ("dimensionless", ("dimensionless",)),
    "media": ("dimensionless", ("dimensionless",)),
}

SIGNALS = ("analog", "frequency", "discrete", "digital", "computed", "counter", "inspection", "media")
ROLES = ("single", "lane", "voted", "placeholder")
ENCODINGS = ("bnr", "ubnr", "bitfield", "enum", "code_word", "string", "float64", "int64_ticks", "none")
TRANSPORTS = (
    "mil1553",
    "mil1553_status",
    "mil1553_modecode",
    "arinc429",
    "rs422",
    "fti_pcm",
    "internal",
    "download",
    "maint_record",
    "recorder_time",
    "video",
    "placeholder",
)
LIMIT_KINDS = (
    "normal_band",
    "emergency_band",
    "starting_band",
    "operational_envelope",
    "steady_max",
    "transient_max",
    "warning_low",
    "warning_high",
    "nominal",
    "life",
)
PRESSURE_REFS = ("absolute", "differential", "gauge", "dynamic")
TAG_CLASSES = ("DIRECT", "DIRECT-part", "DIRECT-unnamed", "TRANSFER", "MEASURED", "ASSUMPTION")
BASES = ("evidenced", "assumed", "derived")

#  Channel fields that carry a value and therefore need a provenance entry (when not null). Sinks and limits
# carry
#: their provenance inline (one ref per sink / limit).
PROV_FIELDS = (
    "quantity",
    "units",
    "signal",
    "sensor_type",
    "source_lru",
    "acq_lru",
    "expansion",
    "range",
    "native_step",
    "converter_step",
    "recorder_lsb",
    "adc_bits",
    "encoding",
    "transport",
    "validity",
    "rates.acquisition",
    "rates.bus",
    "rates.producer",
    "calibration",
)

_TAG_RE = re.compile(r"DIRECT[- ]unnamed|DIRECT[- ]part|DIRECT|TRANSFER|MEASURED|ASSUMPTION")


def core_tag_error(text: str) -> str | None:
    """None if ``text`` parses with the core kernel's EvidenceTag (phalanx.core.module), else the error
    message."""
    from phalanx.core.module import ContractError, EvidenceTag

    try:
        EvidenceTag.parse(text)
    except ContractError as exc:
        return str(exc)
    return None


def rule_is_proxy(rule: Any) -> bool:
    """A rule that labels a simplification (PROXY flag, P- rules)."""
    return bool(rule.get("proxy"))


def rule_needs_register(rule: Any) -> bool:
    """ASSUMPTION and PROXY rules need a docs/assumptions.md row."""
    return rule["tag"].strip() == "ASSUMPTION" or rule_is_proxy(rule)


def parse_tag_classes(text: str) -> list[str]:
    """Evidence classes mentioned in a free-text tag, in order of first appearance (no duplicates)."""
    out: list[str] = []
    for m in _TAG_RE.finditer(text or ""):
        tok = m.group(0).replace(" ", "-")
        tok = {"DIRECT-unnamed": "DIRECT-unnamed", "DIRECT-part": "DIRECT-part"}.get(tok, tok)
        if tok not in out:
            out.append(tok)
    return out


# ------------------------------------------------------------------------------------------------------------
# JSON Schemas
# ------------------------------------------------------------------------------------------------------------
_ID = {"type": "string", "pattern": r"^[A-Z0-9][A-Za-z0-9_.\-]*$"}
_NUM = {"type": "number"}
_NUM_OR_NULL = {"type": ["number", "null"]}
_EVIDENCE = {
    "type": "object",
    "required": ["tag", "source"],
    "properties": {
        "tag": {"type": "string", "minLength": 1},
        "source": {"type": "string", "minLength": 1},
        "classes": {"type": "array", "items": {"enum": list(TAG_CLASSES)}},
        "primary": {"enum": list(TAG_CLASSES)},
        "core_tag": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}
_PROV_REF = {"type": "string", "pattern": r"^(inv|[RP]-[A-Z0-9][A-Z0-9\-]*)$"}

_FIELD = {
    "type": "object",
    "required": ["name", "lsb_bit", "width"],
    "properties": {
        "name": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_\-]*$"},
        "lsb_bit": {"type": "integer", "minimum": 0},
        "width": {"type": "integer", "minimum": 1},
    },
    "additionalProperties": False,
}

_ENCODING = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {"enum": list(ENCODINGS)},
        "word_bits": {"type": "integer", "minimum": 1, "maximum": 64},
        "words": {"type": "integer", "minimum": 1, "maximum": 4},
        "fields": {"type": "array", "items": _FIELD},
        "code_table": {"type": "string"},
        "format": {"type": "string"},
        "prefixes": {"type": "array", "items": {"type": "string"}},
        "tick_s": _NUM,
        "known_values": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

_TRANSPORT = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {"enum": list(TRANSPORTS)},
        "bus": {"type": "string"},
        "rt": {"type": "integer", "minimum": 0, "maximum": 31},
        "rt_lru": {"type": "string"},
        "tr": {"enum": ["T", "R"]},
        "sa": {"type": "integer", "minimum": 1, "maximum": 30},
        "word": {"type": "integer", "minimum": 1, "maximum": 32},
        "words": {"type": "integer", "minimum": 1, "maximum": 4},
        "message_words": {"type": "integer", "minimum": 1, "maximum": 32},
        "mode_code": {"type": "integer", "minimum": 0, "maximum": 31},
        "link": {"type": "string"},
        "label": {"type": "integer", "minimum": 0, "maximum": 255},
        "sdi": {"type": "integer", "minimum": 0, "maximum": 3},
        "stream": {"type": "string"},
        "lru": {"type": "string"},
        "unit": {"type": "string"},
        "product": {"type": "string"},
    },
    "additionalProperties": False,
}

_VALIDITY = {
    "type": "object",
    "required": ["method"],
    "properties": {
        "method": {"enum": ["none", "validity_word", "ssm", "rt_status", "frame_sync"]},
        "word": {"type": "integer", "minimum": 1, "maximum": 32},
        "bit": {"type": "integer", "minimum": 0, "maximum": 15},
        "table": {"type": "string"},
    },
    "additionalProperties": False,
}

_SINK = {
    "type": "object",
    "required": ["sink", "basis", "group", "prov", "group_prov"],
    "properties": {
        "sink": {"type": "string"},
        "basis": {"enum": list(BASES)},
        "group": {"type": ["string", "null"]},
        "consumer": {"type": "string"},
        "prov": _PROV_REF,
        "group_prov": _PROV_REF,
    },
    "additionalProperties": False,
}

_LIMIT = {
    "type": "object",
    "required": ["kind", "prov"],
    "properties": {
        "kind": {"enum": list(LIMIT_KINDS)},
        "low": _NUM,
        "high": _NUM,
        "value": _NUM,
        "prov": _PROV_REF,
    },
    "additionalProperties": False,
}

CHANNEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "measurand_id",
        "lane",
        "role",
        "name",
        "quantity",
        "units",
        "signal",
        "source_lru",
        "acq_lru",
        "range",
        "native_step",
        "recorder_lsb",
        "adc_bits",
        "encoding",
        "transport",
        "validity",
        "rates",
        "sinks",
        "calibration",
        "limits",
        "inputs",
        "proxy",
        "prov",
    ],
    "properties": {
        "measurand_id": _ID,
        "lane": {"type": "string", "pattern": r"^([A-Z0-9_\-]*)$"},
        "unit_id": {"type": "string"},
        "component": {"type": "string"},
        "role": {"enum": list(ROLES)},
        "name": {"type": "string", "minLength": 1},
        "quantity": {"enum": list(QUANTITIES)},
        "units": {"type": "string", "minLength": 1},
        "pressure_ref": {"enum": list(PRESSURE_REFS)},
        "signal": {"enum": list(SIGNALS)},
        "sensor_type": {"type": ["string", "null"]},
        "source_lru": {"type": "string"},
        "acq_lru": {"type": "string"},
        "range": {
            "type": ["object", "null"],
            "required": ["min", "max"],
            "properties": {"min": _NUM_OR_NULL, "max": _NUM_OR_NULL},
            "additionalProperties": False,
        },
        "native_step": {"type": ["number", "null"], "exclusiveMinimum": 0},
        # FADEC lanes: the FADEC converter step (rule R-FADEC-ADC), finer than native_step until M13 adopts it
        "converter_step": {"type": "number", "exclusiveMinimum": 0},
        "recorder_lsb": {"type": ["number", "null"], "exclusiveMinimum": 0},
        "adc_bits": {"type": ["integer", "null"], "minimum": 1, "maximum": 32},
        "encoding": _ENCODING,
        "transport": _TRANSPORT,
        "validity": _VALIDITY,
        "rates": {
            "type": "object",
            "required": ["acquisition", "bus", "producer"],
            "properties": {
                "acquisition": {"type": "string"},
                "bus": {"type": ["string", "null"]},
                "producer": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "sinks": {"type": "array", "items": _SINK},
        "calibration": {
            "type": ["object", "null"],
            "required": ["type", "coefficients", "date"],
            "properties": {
                "type": {"enum": ["polynomial"]},
                "coefficients": {"type": "array", "items": _NUM, "minItems": 2},
                "date": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "limits": {"type": "array", "items": _LIMIT},
        "inputs": {"type": "array", "items": {"type": "string"}},
        "proxy": {"type": "boolean"},
        "prov": {"type": "object", "additionalProperties": _PROV_REF},
        "inv_tokens": {"type": "object", "additionalProperties": {"type": "string"}},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

PARAM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name", "measurement_class", "evidence", "channels"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "inventory": {
            "type": "object",
            "required": ["row", "fields"],
            "properties": {
                "row": {"type": "integer", "minimum": 1},
                "fields": {"type": "object", "additionalProperties": {"type": "string"}},
                # inventory fields in which restricted-manual fragments were redacted (seeder, redact.py)
                "redacted": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            },
            "additionalProperties": False,
        },
        "measurement_class": {"type": "string"},
        "computed_by": {"type": ["string", "null"]},
        "evidence": _EVIDENCE,
        "notes": {"type": ["string", "null"]},
        "channels": {"type": "object", "minProperties": 1, "additionalProperties": CHANNEL_SCHEMA},
    },
    "additionalProperties": False,
}

SOURCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["format", "platform", "subsystem", "parameters"],
    "properties": {
        "format": {"const": FORMAT_SOURCE},
        "generated_by": {"type": "string"},
        "platform": {"type": "string"},
        "subsystem": {"type": "string", "pattern": r"^[a-z][a-z0-9_]*$"},
        "inventory_subsystems": {"type": "array", "items": {"type": "string"}},
        "parameters": {"type": "object", "additionalProperties": PARAM_SCHEMA},
    },
    "additionalProperties": False,
}

MANIFEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "format",
        "platform",
        "title",
        "dict_version",
        "release_date",
        "synthetic_icd",
        "synthetic_label",
        "tables",
        "sources_dir",
        "generators",
    ],
    "properties": {
        "format": {"const": "phalanx.dictionary.manifest/1"},
        "platform": {"type": "string", "pattern": r"^[a-z][a-z0-9_]*$"},
        "title": {"type": "string"},
        "dict_version": {"type": "string", "pattern": r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"},
        "release_date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "synthetic_icd": {"type": "boolean"},
        "synthetic_label": {"type": "string"},
        "tables": {
            "type": "object",
            "required": ["lrus", "buses", "rate_groups", "sinks", "code_tables", "rules", "constants"],
            "additionalProperties": {"type": "string"},
        },
        "sources_dir": {"type": "string"},
        "generators": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

_RULE = {
    "type": "object",
    "required": ["title", "statement", "tag", "source", "sweep", "affects"],
    "properties": {
        "title": {"type": "string"},
        "statement": {"type": "string"},
        "tag": {"type": "string", "minLength": 1},
        "basis": {"type": "string"},
        "source": {"type": "string", "minLength": 1},
        "sweep": {"type": "string"},
        "affects": {"type": "array", "items": {"type": "string"}},
        "exposing_test": {"type": "string"},
        "replacement": {"type": "string"},
        "assumption_id": {"type": "string", "pattern": r"^A-W0\.3-[0-9]+$"},
        "proxy": {"type": "boolean"},
    },
    "additionalProperties": False,
}

TABLE_SCHEMAS: dict[str, dict[str, Any]] = {
    "lrus": {
        "type": "object",
        "required": ["format", "lrus"],
        "properties": {
            "format": {"const": "phalanx.dictionary.lrus/1"},
            "lrus": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["name", "role", "units", "evidence"],
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "units": {"type": "integer", "minimum": 1},
                        "frame_hz": {"type": "number", "exclusiveMinimum": 0},
                        "frame_prov": _PROV_REF,
                        "evidence": _EVIDENCE,
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    },
    "rules": {
        "type": "object",
        "required": ["format", "rules"],
        "properties": {
            "format": {"const": "phalanx.dictionary.rules/1"},
            "rules": {
                "type": "object",
                "propertyNames": {"pattern": r"^[RP]-[A-Z0-9\-]+$"},
                "additionalProperties": _RULE,
            },
        },
        "additionalProperties": False,
    },
    "rate_groups": {
        "type": "object",
        "required": ["format", "groups"],
        "properties": {
            "format": {"const": "phalanx.dictionary.rate_groups/1"},
            "groups": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["kind", "stages", "domain", "prov"],
                    "properties": {
                        "kind": {
                            "enum": [
                                "periodic",
                                "lru_frame",
                                "event",
                                "sortie",
                                "inspection",
                                "display",
                                "media",
                            ]
                        },
                        "rate_hz": {"type": "number", "exclusiveMinimum": 0},
                        "band_hz": {"type": "array", "items": _NUM, "minItems": 2, "maxItems": 2},
                        "window_s": {"type": "array", "items": _NUM, "minItems": 2, "maxItems": 2},
                        "stages": {
                            "type": "array",
                            "items": {"enum": ["acquisition", "producer", "bus", "record"]},
                            "minItems": 1,
                        },
                        "domain": {"type": "string"},
                        "prov": _PROV_REF,
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    },
    "sinks": {
        "type": "object",
        "required": ["format", "sinks"],
        "properties": {
            "format": {"const": "phalanx.dictionary.sinks/1"},
            "sinks": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["name", "kind", "evidence"],
                    "properties": {
                        "name": {"type": "string"},
                        "kind": {
                            "enum": [
                                "display",
                                "recorder",
                                "download",
                                "test",
                                "consumer",
                                "record",
                                "ground",
                            ]
                        },
                        "default_group": {"type": "string"},
                        "default_group_engine": {"type": "string"},
                        "lru": {"type": "string"},
                        "evidence": _EVIDENCE,
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    },
    "buses": {
        "type": "object",
        "required": ["format", "synthetic", "label", "mil1553", "arinc429", "rs422", "fti_pcm"],
        "properties": {
            "format": {"const": "phalanx.dictionary.buses/1"},
            "synthetic": {"const": True},
            "label": {"type": "string", "pattern": "SYNTHETIC"},
            "mil1553": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["title", "bc", "monitors", "prov", "rts"],
                    "properties": {
                        "title": {"type": "string"},
                        "bc": {"type": "string"},
                        "monitors": {"type": "array", "items": {"type": "string"}},
                        "prov": _PROV_REF,
                        "rts": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "required": ["address", "prov"],
                                "properties": {
                                    "address": {"type": "integer", "minimum": 0, "maximum": 30},
                                    "mirrors": {"type": "array", "items": {"type": "integer"}},
                                    "prov": _PROV_REF,
                                },
                                "additionalProperties": False,
                            },
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "arinc429": {"type": "object", "additionalProperties": {"type": "object"}},
            "rs422": {"type": "object", "additionalProperties": {"type": "object"}},
            "fti_pcm": {"type": "object", "additionalProperties": {"type": "object"}},
            # recorder setup: recording events and index (TMATS R-1\EV, R-1\IDX; rule R-REC-SETUP)
            "recorder": {
                "type": "object",
                "required": ["id", "prov", "events", "index"],
                "properties": {
                    "id": {"type": "string", "pattern": r"^[A-Z0-9_-]{1,32}$"},
                    "prov": _PROV_REF,
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "description", "type"],
                            "properties": {
                                "id": {"type": "string", "pattern": r"^[A-Za-z0-9_.-]{1,32}$"},
                                "description": {"type": "string", "maxLength": 256},
                                "type": {"enum": ["E", "D", "L", "R", "O"]},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "event_priority": {"type": "integer", "minimum": 1},
                    "event_initial_capture": {"type": "boolean"},
                    "event_limit_count": {"type": "integer", "minimum": 0},
                    "index": {
                        "type": "object",
                        "required": ["type", "interval_s"],
                        "properties": {
                            "type": {"const": "time"},
                            "interval_s": {"type": "integer", "minimum": 1},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    },
    "code_tables": {
        "type": "object",
        "required": ["format", "tables"],
        "properties": {
            "format": {"const": "phalanx.dictionary.code_tables/1"},
            "tables": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["title", "synthetic", "prov"],
                    "properties": {
                        "title": {"type": "string"},
                        "synthetic": {"type": "boolean"},
                        "prov": _PROV_REF,
                    },
                },
            },
        },
        "additionalProperties": False,
    },
    "constants": {
        "type": "object",
        "required": ["format", "sets"],
        "properties": {
            "format": {"const": "phalanx.dictionary.constants/1"},
            "sets": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "propertyNames": {"pattern": r"^[a-z_][a-z0-9_]*$"},
                    "additionalProperties": {
                        "type": "object",
                        "required": ["value", "units", "description", "evidence"],
                        "properties": {
                            "value": _NUM,
                            "units": {"type": "string"},
                            "description": {"type": "string"},
                            "evidence": _EVIDENCE,
                            "sweep": {"type": "array", "items": _NUM, "minItems": 2, "maxItems": 2},
                            "prov": _PROV_REF,
                            "proxy": {"type": "boolean"},
                            # parameters whose % of rated speed channels convert to SI with this speed
                            "eu_reference_for": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        },
                        "additionalProperties": False,
                    },
                },
            },
        },
        "additionalProperties": False,
    },
}


def schema_errors(instance: Any, schema: dict[str, Any], where: str) -> list[str]:
    """All JSON-Schema violations of ``instance``, as sorted human-readable strings."""
    validator = Draft202012Validator(schema)
    out = []
    for err in validator.iter_errors(instance):
        path = "/".join(str(p) for p in err.absolute_path)
        out.append(f"{where}:{'/' + path if path else ''}: {err.message}")
    return sorted(out)
