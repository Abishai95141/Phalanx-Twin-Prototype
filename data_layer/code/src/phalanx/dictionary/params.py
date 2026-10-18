"""Model-parameter registry: per-module parameter files with provenance (architecture P4, §5.5, §15).

The parameter dictionary (M01) holds channel semantics. Model parameters (gains, maps, time constants, rates)
live in **one file per module**, so parallel work packages never edit a shared file:

    configs/<platform>/params/<MODULE>.yaml        e.g. configs/tejas/params/M07.yaml
    configs/<platform>/params/<MODULE>/<file>.csv  numeric tables referenced by `table:` entries

File format (`phalanx.params/1`):

    format: phalanx.params/1
    module: M07
    sets:
      <set_name>:
        <param_name>:
          value: 1.5 | [..] | [[..], ..]       # exactly one of value / table
          table: {file: fan_map.csv, column: Wc} # numeric CSV with a header row
          units: "kg/s"                        # pint string; "1" for dimensionless
          description: "..."
          evidence: {tag: "TRANSFER: F404-400", source: "report §7; research_notes/..."}
          proxy: false                         # true needs assumption_id
          sweep: [lo, hi]                      # required for ASSUMPTION; scalars need lo <= value <= hi
          assumption_id: A-W1.3a-4             # ASSUMPTION/PROXY; registered in docs/assumptions.md

Values are converted to coherent SI base units when loaded (`Param.unit` is SI). Temperatures in degC/degF
are absolute temperatures. Use `delta_degC` for differences. Unknown keys, duplicate YAML keys, a missing
tag/source, unparsable units and an ASSUMPTION without a sweep are all errors (RULES.md rules 2-3).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from phalanx.core.canonical import PERSON_PARAMS, canonical_json, digest
from phalanx.core.module import EvidenceTag, Param, ParamSet
from phalanx.core.units import ureg

from .yamlio import load_yaml

FORMAT = "phalanx.params/1"
_ENTRY_KEYS = {"value", "table", "units", "description", "evidence", "proxy", "sweep", "assumption_id"}
_REPO = Path(__file__).resolve().parents[3]


class ParamFileError(ValueError):
    """A parameter file violates the registry rules. `.errors` lists every problem found."""

    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


def params_dir(platform: str = "tejas", config_root: Path | None = None) -> Path:
    return (config_root or _REPO / "configs") / platform / "params"


def _read_table(path: Path, column: str) -> np.ndarray:
    text = path.read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or column not in rows[0]:
        raise ValueError(f"{path.name}: no column {column!r} (header {rows[0] if rows else []})")
    i = rows[0].index(column)
    return np.array([float(r[i]) for r in rows[1:] if r], dtype=np.float64)


def _to_si(value: Any, units: str) -> tuple[Any, str]:
    reg = ureg()
    arr = np.asarray(value, dtype=np.float64) if not np.isscalar(value) else value
    q = reg.Quantity(arr, units).to_base_units()
    mag = q.magnitude
    if isinstance(mag, np.ndarray):
        out: Any = mag.astype(np.float64)
    elif isinstance(value, int) and not isinstance(value, bool) and float(mag).is_integer():
        out = int(mag)
    else:
        out = float(mag)
    unit = str(q.units)
    return out, ("1" if unit in ("", "dimensionless") else unit)


def _known_assumption_ids(repo_root: Path) -> set[str]:
    p = repo_root / "docs" / "assumptions.md"
    if not p.is_file():
        return set()
    ids = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("| A-"):
            ids.add(line.split("|")[1].strip())
    return ids


def _check_entry(where: str, e: Any, file_dir: Path, ids: set[str] | None) -> list[str]:
    errs: list[str] = []
    if not isinstance(e, Mapping):
        return [f"{where}: entry must be a mapping"]
    extra = set(e) - _ENTRY_KEYS
    if extra:
        errs.append(f"{where}: unknown keys {sorted(extra)}")
    if ("value" in e) == ("table" in e):
        errs.append(f"{where}: exactly one of value / table is required")
    if "table" in e:
        t = e["table"]
        if not isinstance(t, Mapping) or set(t) != {"file", "column"}:
            errs.append(f"{where}: table must be {{file, column}}")
        elif not (file_dir / t["file"]).is_file():
            errs.append(f"{where}: table file {t['file']} not found")
    for k in ("units", "description"):
        if not isinstance(e.get(k), str) or not e.get(k, "").strip():
            errs.append(f"{where}: {k} is required")
    ev = e.get("evidence")
    tag = None
    if not isinstance(ev, Mapping) or set(ev) != {"tag", "source"}:
        errs.append(f"{where}: evidence must be {{tag, source}}")
    else:
        try:
            tag = EvidenceTag.parse(ev["tag"])
        except Exception as x:
            errs.append(f"{where}: unparsable evidence tag {ev.get('tag')!r}: {x}")
        if not isinstance(ev.get("source"), str) or not ev["source"].strip():
            errs.append(f"{where}: evidence.source is required")
    if isinstance(e.get("units"), str):
        try:
            ureg().Unit(e["units"])
        except Exception as x:
            errs.append(f"{where}: unparsable units {e['units']!r}: {x}")
    is_assumption = tag is not None and tag.kind == "ASSUMPTION"
    proxy = bool(e.get("proxy", False))
    if is_assumption:
        sw = e.get("sweep")
        if not (isinstance(sw, list) and len(sw) == 2 and all(isinstance(x, int | float) for x in sw)):
            errs.append(f"{where}: ASSUMPTION requires sweep: [lo, hi]")
        elif sw[0] > sw[1]:
            errs.append(f"{where}: sweep lo > hi")
        elif isinstance(e.get("value"), int | float) and not (sw[0] <= e["value"] <= sw[1]):
            errs.append(f"{where}: value {e['value']} outside sweep {sw}")
    if is_assumption or proxy:
        aid = e.get("assumption_id")
        if not isinstance(aid, str) or not aid.startswith("A-"):
            errs.append(f"{where}: ASSUMPTION/PROXY entries need assumption_id (A-...)")
        elif ids is not None and aid not in ids:
            errs.append(f"{where}: assumption_id {aid} is not registered in docs/assumptions.md")
    return errs


def load_params(
    module: str,
    *,
    platform: str = "tejas",
    config_root: Path | None = None,
    repo_root: Path | None = None,
    check_assumption_ids: bool = True,
) -> dict[str, ParamSet]:
    """All parameter sets of ``module`` as core ``ParamSet``s (SI values, parsed tags, PROXY flags)."""
    path = params_dir(platform, config_root) / f"{module}.yaml"
    doc = load_yaml(path)
    ids = _known_assumption_ids(repo_root or _REPO) if check_assumption_ids else None
    errs: list[str] = []
    if not isinstance(doc, Mapping) or doc.get("format") != FORMAT:
        raise ParamFileError([f"{path.name}: format must be {FORMAT}"])
    if doc.get("module") != module:
        errs.append(f"{path.name}: module field {doc.get('module')!r} != file name {module!r}")
    if set(doc) - {"format", "module", "sets"}:
        errs.append(f"{path.name}: unknown top-level keys {sorted(set(doc) - {'format', 'module', 'sets'})}")
    sets = doc.get("sets")
    if not isinstance(sets, Mapping) or not sets:
        errs.append(f"{path.name}: sets must be a non-empty mapping")
        raise ParamFileError(errs)
    file_dir = path.parent / module
    for sname, entries in sets.items():
        if not isinstance(entries, Mapping) or not entries:
            errs.append(f"{path.name}:{sname}: a set must be a non-empty mapping")
            continue
        for pname, e in entries.items():
            errs += _check_entry(f"{path.name}:{sname}.{pname}", e, file_dir, ids)
    if errs:
        raise ParamFileError(errs)
    out: dict[str, ParamSet] = {}
    for sname, entries in sets.items():
        params = {}
        for pname, e in entries.items():
            raw = (
                _read_table(file_dir / e["table"]["file"], e["table"]["column"])
                if "table" in e
                else e["value"]
            )
            value, unit = _to_si(raw, e["units"])
            params[pname] = Param(
                value=value,
                unit=unit,
                tag=e["evidence"]["tag"],
                source=e["evidence"]["source"],
                proxy=bool(e.get("proxy", False)),
                note=f"{e['description']} [{module} {sname}; given in {e['units']}]",
            )
        out[sname] = ParamSet(f"{platform}.{module}.{sname}", params)
    return out


def load_param_set(module: str, set_name: str, **kw: Any) -> ParamSet:
    sets = load_params(module, **kw)
    if set_name not in sets:
        raise KeyError(f"{module}: no parameter set {set_name!r} (have {sorted(sets)})")
    return sets[set_name]


def registry_hash(platform: str = "tejas", config_root: Path | None = None) -> str:
    """Content hash of every parameter file and table of ``platform`` (recorded in run manifests)."""
    d = params_dir(platform, config_root)
    parts = []
    if d.is_dir():
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix in (".yaml", ".csv"):
                parts.append(
                    {"path": p.relative_to(d).as_posix(), "sha": digest(p.read_bytes(), PERSON_PARAMS)}
                )
    return digest(canonical_json({"platform": platform, "files": parts}), PERSON_PARAMS)
