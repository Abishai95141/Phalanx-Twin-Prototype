"""Strict YAML I/O, canonical JSON and content hashing for the parameter dictionary (M01).

Determinism rules (RULES.md rule 5, brief W0.3 §3):
- YAML mappings with duplicate keys are rejected (PyYAML silently keeps the last one otherwise).
- Canonical JSON is the core kernel's ``phalanx.core.canonical.canonical_json`` (sorted keys, compact, ASCII,
  no NaN/Inf) applied after a dictionary-side check of the JSON data model that also maps -0.0 to 0.0.
- The content hash is the core kernel's personalised blake2b (``phalanx.core.canonical.digest``) with the
  dictionary family person ``phx.dict.v1``. Builtin ``hash()`` is never used.
"""

from __future__ import annotations

import math
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from phalanx.core.canonical import canonical_json, digest

__all__ = [
    "PERSON_DICTIONARY",
    "DuplicateKeyError",
    "blake2b_hex",
    "canonical_json_bytes",
    "dump_yaml",
    "load_yaml",
    "load_yaml_text",
]


class DuplicateKeyError(ValueError):
    """A YAML mapping repeats a key."""


class _StrictLoader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):  # libyaml parser when present
    """SafeLoader that rejects duplicate mapping keys."""


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    seen: set[Any] = set()
    out: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            mark = key_node.start_mark
            raise DuplicateKeyError(
                f"duplicate key {key!r} at line {mark.line + 1}, column {mark.column + 1}"
            )
        seen.add(key)
        out[key] = loader.construct_object(value_node, deep=deep)
    return out


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


class _NoAliasDumper(yaml.SafeDumper):
    """SafeDumper that never emits anchors/aliases (shared objects are written out in full)."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


def _represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    """Double-quote strings with control or Unicode line-break characters.

    PyYAML would otherwise emit e.g. NEL (U+0085) unescaped in a single-quoted scalar, where the loader
    folds it into a space (found by the property test of the YAML round trip).
    """
    if any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return dumper.represent_str(data)


_NoAliasDumper.add_representer(str, _represent_str)


def load_yaml_text(text: str, *, origin: str = "<string>") -> Any:
    """Parse YAML text strictly (duplicate keys are an error)."""
    try:
        return yaml.load(text, Loader=_StrictLoader)
    except DuplicateKeyError as exc:
        raise DuplicateKeyError(f"{origin}: {exc}") from exc


def load_yaml(path: str | Path) -> Any:
    """Load a YAML file strictly."""
    p = Path(path)
    return load_yaml_text(p.read_text(encoding="utf-8"), origin=str(p))


def dump_yaml(obj: Any) -> str:
    """Deterministic YAML text: insertion order preserved, no aliases, unicode kept, wide lines."""
    return yaml.dump(
        obj,
        Dumper=_NoAliasDumper,
        sort_keys=False,
        allow_unicode=True,
        width=4096,
        default_flow_style=None,
    )


def _normalise(obj: Any, path: str = "$") -> Any:
    """Check the JSON data model and normalise -0.0; reject NaN/Inf, tuples become lists."""
    if obj is None or isinstance(obj, bool | str):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"{path}: non-finite float {obj!r} cannot be canonicalised")
        return 0.0 if obj == 0.0 else obj
    if isinstance(obj, list | tuple):
        return [_normalise(v, f"{path}[{i}]") for i, v in enumerate(obj)]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(f"{path}: mapping key {k!r} is not a string")
            out[k] = _normalise(v, f"{path}.{k}")
        return out
    raise TypeError(f"{path}: type {type(obj).__name__} is not part of the JSON data model")


#: blake2b personalisation for dictionary content hashes (domain separation, as in phalanx.core.canonical)
from phalanx.core.canonical import PERSON_DICTIONARY  # noqa: E402  (single registry of hash persons)


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonical JSON bytes (core kernel encoding) of a checked, -0.0-normalised JSON value."""
    return canonical_json(_normalise(obj))


def blake2b_hex(data: bytes, person: bytes = PERSON_DICTIONARY) -> str:
    """Personalised blake2b-256 hex digest (core kernel ``digest``)."""
    return digest(data, person)
