"""Compiler: YAML sources + platform tables -> canonical, versioned, blake2b-hashed ``dictionary.<ver>.json``
(M01).

``compile_dictionary(config_dir)`` is a pure function of the files under ``config_dir`` (no wall clock, no
environment, no file paths in the output): the same sources give the same bytes and the same hash, in this
process and in a fresh one (brief W0.3 A2). The hash is blake2b-256 over the canonical JSON of the content
*without* the ``dict_hash`` field; the written file carries the hash alongside the content.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import (
    FORMAT_COMPILED,
    MANIFEST_SCHEMA,
    PROV_FIELDS,
    SOURCE_SCHEMA,
    TABLE_SCHEMAS,
    parse_tag_classes,
    rule_is_proxy,
    rule_needs_register,
    schema_errors,
)
from .validate import affected_params, channel_rule_refs, validate_all
from .yamlio import blake2b_hex, canonical_json_bytes, load_yaml

__all__ = [
    "CompileError",
    "CompiledDictionary",
    "SourceBundle",
    "compile_bundle",
    "compile_dictionary",
    "load_bundle",
    "read_compiled",
    "write_compiled",
]


class CompileError(ValueError):
    """Compilation failed; ``errors`` lists every problem (the message shows the first 200)."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        head = "\n  ".join(self.errors[:200])
        more = f"\n  ... and {len(self.errors) - 200} more" if len(self.errors) > 200 else ""
        super().__init__(f"dictionary compilation failed with {len(self.errors)} error(s):\n  {head}{more}")


@dataclass
class SourceBundle:
    """Everything the compiler reads: the manifest, the tables and the per-subsystem sources (by file
    name)."""

    manifest: dict[str, Any]
    tables: dict[str, Any]
    sources: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> SourceBundle:
        return SourceBundle(
            copy.deepcopy(self.manifest), copy.deepcopy(self.tables), copy.deepcopy(self.sources)
        )


@dataclass(frozen=True)
class CompiledDictionary:
    """Compiled content, its canonical bytes and its blake2b-256 hash."""

    content: dict[str, Any]
    canonical: bytes
    dict_hash: str

    @property
    def dict_version(self) -> str:
        return self.content["dict_version"]

    @property
    def platform(self) -> str:
        return self.content["platform"]

    def to_bytes(self) -> bytes:
        """File bytes: canonical JSON of the content plus ``dict_hash``."""
        return canonical_json_bytes({**self.content, "dict_hash": self.dict_hash})


def load_bundle(config_dir: str | Path) -> SourceBundle:
    """Read the manifest, its tables and every ``sources/*.yaml`` of a platform dictionary directory."""
    root = Path(config_dir)
    manifest = load_yaml(root / "dictionary.yaml")
    if not isinstance(manifest, dict) or "tables" not in manifest:
        raise CompileError([f"{root / 'dictionary.yaml'}: not a dictionary manifest"])
    tables = {name: load_yaml(root / rel) for name, rel in sorted(manifest["tables"].items())}
    src_dir = root / manifest.get("sources_dir", "sources")
    sources = {p.name: load_yaml(p) for p in sorted(src_dir.glob("*.yaml"))}
    return SourceBundle(manifest=manifest, tables=tables, sources=sources)


def compile_dictionary(config_dir: str | Path) -> CompiledDictionary:
    """Compile a platform dictionary directory. Raises CompileError listing every problem."""
    return compile_bundle(load_bundle(config_dir))


def compile_bundle(bundle: SourceBundle) -> CompiledDictionary:
    """Compile an in-memory bundle (used by tests to show that broken sources fail)."""
    errors = _non_string_keys(bundle.manifest, "dictionary.yaml")
    errors += [
        e for name, tab in sorted(bundle.tables.items()) for e in _non_string_keys(tab, f"table {name}")
    ]
    errors += [e for name, doc in sorted(bundle.sources.items()) for e in _non_string_keys(doc, name)]
    if errors:
        raise CompileError(errors)
    errors = schema_errors(bundle.manifest, MANIFEST_SCHEMA, "dictionary.yaml")
    for name, schema in TABLE_SCHEMAS.items():
        if name not in bundle.tables:
            errors.append(f"table {name} missing")
            continue
        errors += schema_errors(bundle.tables[name], schema, f"table {name}")
    if not bundle.sources:
        errors.append("no source files")
    for fname, doc in sorted(bundle.sources.items()):
        errors += schema_errors(doc, SOURCE_SCHEMA, fname)
    if errors:
        raise CompileError(errors)

    params: dict[str, dict[str, Any]] = {}
    subsystem_of: dict[str, str] = {}
    channel_owner: dict[str, str] = {}
    for fname, doc in sorted(bundle.sources.items()):
        if doc["platform"] != bundle.manifest["platform"]:
            errors.append(f"{fname}: platform {doc['platform']} differs from the manifest")
        for pid, p in doc["parameters"].items():
            if pid in params:
                errors.append(f"{fname}: parameter {pid} also defined in another source file")
                continue
            params[pid] = p
            subsystem_of[pid] = doc["subsystem"]
            for cid in p["channels"]:
                if cid in channel_owner:
                    errors.append(f"{fname}: channel {cid} also defined by {channel_owner[cid]}")
                channel_owner[cid] = pid
    errors += validate_all(params, bundle.tables, bundle.manifest)
    if errors:
        raise CompileError(sorted(set(errors)))

    content = _assemble(bundle, params, subsystem_of)
    canonical = canonical_json_bytes(content)
    return CompiledDictionary(
        content=json.loads(canonical), canonical=canonical, dict_hash=blake2b_hex(canonical)
    )


def _non_string_keys(obj: Any, where: str) -> list[str]:
    """Mapping keys that are not strings (YAML turns 0: into an int; JSON keys must be strings)."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                out.append(f"{where}: mapping key {k!r} is not a string (quote it in YAML)")
            out += _non_string_keys(v, f"{where}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _non_string_keys(v, f"{where}[{i}]")
    return out


def _assemble(bundle: SourceBundle, params: dict[str, Any], subsystem_of: dict[str, str]) -> dict[str, Any]:
    t = bundle.tables
    m = bundle.manifest
    channels: dict[str, Any] = {}
    parameters: dict[str, Any] = {}
    for pid in sorted(params):
        p = params[pid]
        parameters[pid] = {
            "name": p["name"],
            "subsystem": subsystem_of[pid],
            "inventory": p.get("inventory"),
            "measurement_class": p["measurement_class"],
            "computed_by": p.get("computed_by"),
            "evidence": {
                **p["evidence"],
                "classes": p["evidence"].get("classes") or parse_tag_classes(p["evidence"]["tag"]),
            },
            "notes": p.get("notes"),
            "channel_ids": list(p["channels"]),
        }
        for cid, ch in p["channels"].items():
            channels[cid] = {**ch, "channel_id": cid, "param_id": pid, "subsystem": subsystem_of[pid]}

    constants_by_rule: dict[str, list[str]] = {}
    for set_name, entries in sorted(t["constants"]["sets"].items()):
        for cname, c in sorted(entries.items()):
            if c.get("prov"):
                constants_by_rule.setdefault(c["prov"], []).append(f"{set_name}.{cname}")
    rules = {}
    for rid, r in sorted(t["rules"]["rules"].items()):
        rules[rid] = {**r, "affects_params": affected_params(params, t, rid)}
    assumption_register = [
        {
            "rule": rid,
            "assumption_id": r["assumption_id"],
            "tag": r["tag"],
            "proxy": rule_is_proxy(r),
            "title": r["title"],
            "affects_params": r["affects_params"],
            "affects_constants": constants_by_rule.get(rid, []),
        }
        for rid, r in rules.items()
        if rule_needs_register(r)
    ]
    assumption_register.sort(key=lambda a: int(a["assumption_id"].rsplit("-", 1)[1]))
    return {
        "format": FORMAT_COMPILED,
        "platform": m["platform"],
        "title": m["title"],
        "dict_version": m["dict_version"],
        "release_date": m["release_date"],
        "synthetic_icd": m["synthetic_icd"],
        "synthetic_label": m["synthetic_label"],
        "generators": list(m["generators"]),
        "lrus": t["lrus"]["lrus"],
        "buses": {k: v for k, v in t["buses"].items() if k != "format"},
        "rate_groups": t["rate_groups"]["groups"],
        "sinks": t["sinks"]["sinks"],
        "code_tables": t["code_tables"]["tables"],
        "constants": t["constants"]["sets"],
        "rules": rules,
        "assumption_register": assumption_register,
        "parameters": parameters,
        "channels": dict(sorted(channels.items())),
        "proxy_items": sorted(cid for cid, ch in channels.items() if ch["proxy"]),
        "stats": _stats(parameters, channels, t),
    }


def _stats(parameters: dict[str, Any], channels: dict[str, Any], tables: dict[str, Any]) -> dict[str, Any]:
    valued = 0
    covered = 0
    for ch in channels.values():
        for f in PROV_FIELDS:
            top, _, sub = f.partition(".")
            v = ch[top].get(sub) if sub else ch.get(f)
            if v is not None:
                valued += 1
                covered += f in ch["prov"]
        valued += 2 * len(ch["sinks"]) + len(ch["limits"])
        covered += sum(("prov" in s) + ("group_prov" in s) for s in ch["sinks"])
        covered += sum("prov" in lim for lim in ch["limits"])
    assumption_rules = {rid for rid, r in tables["rules"]["rules"].items() if rule_needs_register(r)}
    with_assumption = sum(
        1
        for cid, ch in channels.items()
        if channel_rule_refs(ch, parameters_lookup(parameters, ch["param_id"]), tables) & assumption_rules
    )
    return {
        "parameters": len(parameters),
        "channels": len(channels),
        "channels_by_role": dict(sorted(Counter(c["role"] for c in channels.values()).items())),
        "channels_by_transport": dict(
            sorted(Counter(c["transport"]["type"] for c in channels.values()).items())
        ),
        "channels_by_subsystem": dict(sorted(Counter(c["subsystem"] for c in channels.values()).items())),
        "recorded_channels": sum(
            c["transport"]["type"] in ("mil1553", "arinc429", "fti_pcm") for c in channels.values()
        ),
        "parameters_by_primary_tag": dict(
            sorted(Counter(p["evidence"]["primary"] for p in parameters.values()).items())
        ),
        "provenance_valued_fields": valued,
        "provenance_covered_fields": covered,
        "provenance_coverage_pct": round(100.0 * covered / valued, 6) if valued else 100.0,
        "channels_depending_on_assumption_or_proxy": with_assumption,
        "proxy_channels": sum(c["proxy"] for c in channels.values()),
    }


def parameters_lookup(parameters: dict[str, Any], pid: str) -> dict[str, Any]:
    """The compiled parameter record (evidence classes are what channel_rule_refs needs)."""
    return parameters[pid]


def write_compiled(compiled: CompiledDictionary, out_dir: str | Path) -> Path:
    """Write ``dictionary.<ver>.json`` into ``out_dir`` and return its path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"dictionary.{compiled.dict_version}.json"
    path.write_bytes(compiled.to_bytes())
    return path


def read_compiled(path: str | Path) -> CompiledDictionary:
    """Read a compiled dictionary file and verify its hash."""
    data = json.loads(Path(path).read_bytes())
    stored = data.pop("dict_hash", None)
    if data.get("format") != FORMAT_COMPILED:
        raise CompileError([f"{path}: not a compiled dictionary (format {data.get('format')!r})"])
    canonical = canonical_json_bytes(data)
    actual = blake2b_hex(canonical)
    if stored != actual:
        raise CompileError([f"{path}: dict_hash {stored} does not match the content hash {actual}"])
    return CompiledDictionary(content=data, canonical=canonical, dict_hash=actual)
