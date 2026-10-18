"""M18 item catalogue and synthetic code tables (AD-19; configs/tejas/params/M18/{catalogue,codes}.yaml).

The catalogue lists the maintainable item classes (part-number classes), their installed positions on every
tail and the per-class numbers M18 needs (troubleshooting and R/R times, isolation accuracy, shop behaviour,
life limits, initial spares, supply multipliers, relative cost). Every numeric column carries units and
evidence; ASSUMPTION columns carry a relative sweep and a registered assumption_id; a class can override the
evidence of one cell (e.g. the AMAGB 750 h life is DIRECT). Everything here is SYNTHETIC (part numbers,
makers, codes): it is never presented as the real Tejas IPC or IAF code tables (RULES.md rule 6).

Values are converted to SI on load (hours/days/years -> seconds as float).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from phalanx.core.canonical import PERSON_PARAMS, canonical_json, digest
from phalanx.core.module import EvidenceTag
from phalanx.core.units import ureg
from phalanx.dictionary.params import _known_assumption_ids, params_dir
from phalanx.dictionary.yamlio import load_yaml

CATALOGUE_FORMAT = "phalanx.m18.catalogue/1"
CODES_FORMAT = "phalanx.m18.codes/1"
NUMERIC_COLUMNS = (
    "ts_hours",
    "rr_hours",
    "p_isolate",
    "p_ground_repro",
    "p_bench_miss",
    "p_bcm",
    "shop_days",
    "depot_days",
    "stock_per_ac",
    "life_fh",
    "life_landings",
    "life_streams",
    "life_years",
    "lead_mult",
    "unit_cost",
)
STRING_KEYS = ("name", "part_no", "maker", "system", "ambiguity", "repair_level", "mesm")
PROBABILITY_COLUMNS = ("p_isolate", "p_ground_repro", "p_bench_miss", "p_bcm")


class CatalogueError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class ItemClass:
    """One part-number class. Numeric values in SI (seconds for times, counts as float)."""

    code: str
    index: int
    name: str
    part_no: str
    maker: str
    system: str
    lru: str | None
    positions: tuple[str, ...]
    grounding: bool  # MESM 'G' -> a defect grounds the aircraft (NMC); 'P' -> partial (PMC)
    ambiguity: str
    repair_level: str  # I (base shop), D (depot), C (consumable)
    consumable: bool
    inspectable_by: tuple[str, ...]
    values: Mapping[str, float]

    def v(self, column: str) -> float:
        return float(self.values[column])


@dataclass(frozen=True)
class Position:
    code: str
    index: int
    cls: ItemClass


@dataclass(frozen=True)
class Catalogue:
    classes: tuple[ItemClass, ...]
    positions: tuple[Position, ...]
    columns: Mapping[str, Mapping[str, Any]]
    synthetic_label: str
    hash: str
    by_code: Mapping[str, ItemClass] = field(default_factory=dict)
    pos_by_code: Mapping[str, Position] = field(default_factory=dict)

    def cls(self, code: str) -> ItemClass:
        return self.by_code[code]

    def pos(self, code: str) -> Position:
        return self.pos_by_code[code]

    def positions_for_lru(self, lru: str) -> tuple[int, ...]:
        return tuple(p.index for p in self.positions if p.cls.lru == lru)

    def positions_for_system(self, system: str) -> tuple[int, ...]:
        return tuple(p.index for p in self.positions if p.cls.system == system)

    def ambiguity_group(self, pos_index: int) -> tuple[int, ...]:
        g = self.positions[pos_index].cls.ambiguity
        return tuple(p.index for p in self.positions if p.cls.ambiguity == g)

    def with_values(self, changes: Mapping[str, Mapping[str, float]]) -> Catalogue:
        """A copy with some class values replaced (SI units), e.g. for a sweep or a deterministic test.

        The content hash changes with the values, so a System built from it has a different config hash.
        """
        unknown = sorted(set(changes) - set(self.by_code))
        if unknown:
            raise KeyError(f"unknown classes {unknown}")
        classes = []
        for c in self.classes:
            ch = dict(changes.get(c.code, {}))
            bad = sorted(set(ch) - set(NUMERIC_COLUMNS))
            if bad:
                raise KeyError(f"{c.code}: unknown columns {bad}")
            classes.append(
                ItemClass(
                    **{**c.__dict__, "values": {**dict(c.values), **{k: float(v) for k, v in ch.items()}}}
                )
            )
        positions = tuple(Position(p.code, p.index, classes[p.cls.index]) for p in self.positions)
        h = digest(
            canonical_json({"base": self.hash, "changes": {k: dict(v) for k, v in sorted(changes.items())}}),
            PERSON_PARAMS,
        )
        return Catalogue(
            classes=tuple(classes),
            positions=positions,
            columns=self.columns,
            synthetic_label=self.synthetic_label,
            hash=h,
            by_code={c.code: c for c in classes},
            pos_by_code={p.code: p for p in positions},
        )


@dataclass(frozen=True)
class CodeTables:
    tables: Mapping[str, Mapping[str, Mapping[str, str]]]
    texts: Mapping[str, Mapping[str, str]]
    servicing_order: tuple[str, ...]
    synthetic_label: str
    hash: str

    def check(self, table: str, code: str) -> str:
        if code not in self.tables[table]:
            raise KeyError(f"{code!r} is not in synthetic code table {table!r}")
        return code


def _si(value: float, units: str) -> float:
    q = ureg().Quantity(float(value), "dimensionless" if units in ("1", "") else units).to_base_units()
    return float(q.magnitude)


def _check_evidence(where: str, ev: Any) -> list[str]:
    errs = []
    if not isinstance(ev, Mapping) or set(ev) != {"tag", "source"}:
        return [f"{where}: evidence must be {{tag, source}}"]
    try:
        EvidenceTag.parse(ev["tag"])
    except Exception as x:
        errs.append(f"{where}: bad evidence tag: {x}")
    if not isinstance(ev.get("source"), str) or not ev["source"].strip():
        errs.append(f"{where}: evidence.source is required")
    return errs


def load_catalogue(
    path: Path | None = None, *, repo_root: Path | None = None, check_assumption_ids: bool = True
) -> Catalogue:
    path = path or params_dir() / "M18" / "catalogue.yaml"
    doc = load_yaml(path)
    errs: list[str] = []
    if not isinstance(doc, Mapping) or doc.get("format") != CATALOGUE_FORMAT:
        raise CatalogueError([f"{path.name}: format must be {CATALOGUE_FORMAT}"])
    ids = (
        _known_assumption_ids(repo_root or Path(__file__).resolve().parents[3])
        if check_assumption_ids
        else None
    )
    cols = doc.get("columns") or {}
    for c in NUMERIC_COLUMNS:
        spec = cols.get(c)
        if not isinstance(spec, Mapping):
            errs.append(f"column {c}: declaration missing")
            continue
        for k in ("units", "description"):
            if not isinstance(spec.get(k), str) or not spec[k].strip():
                errs.append(f"column {c}: {k} required")
        errs += _check_evidence(f"column {c}", spec.get("evidence"))
        try:
            tag = EvidenceTag.parse(spec["evidence"]["tag"])
        except Exception:
            continue
        if tag.kind == "ASSUMPTION":
            sw = spec.get("sweep")
            if not (isinstance(sw, list) and len(sw) == 2 and sw[0] <= sw[1]):
                errs.append(f"column {c}: ASSUMPTION needs a relative sweep [lo, hi]")
            aid = spec.get("assumption_id")
            if not isinstance(aid, str) or not aid.startswith("A-"):
                errs.append(f"column {c}: ASSUMPTION needs an assumption_id")
            elif ids is not None and aid not in ids:
                errs.append(f"column {c}: assumption_id {aid} not registered in docs/assumptions.md")
    unknown_cols = set(cols) - set(NUMERIC_COLUMNS)
    if unknown_cols:
        errs.append(f"unknown columns {sorted(unknown_cols)}")
    classes: list[ItemClass] = []
    positions: list[Position] = []
    raw = doc.get("classes") or {}
    seen_pos: set[str] = set()
    for i, (code, e) in enumerate(raw.items()):
        where = f"class {code}"
        for k in STRING_KEYS:
            if not isinstance(e.get(k), str) or not e[k].strip():
                errs.append(f"{where}: {k} required")
        if e.get("mesm") not in ("G", "P"):
            errs.append(f"{where}: mesm must be G or P")
        if e.get("repair_level") not in ("I", "D", "C"):
            errs.append(f"{where}: repair_level must be I, D or C")
        if not e.get("part_no", "").startswith("SYN-"):
            errs.append(f"{where}: part_no must be labelled synthetic (SYN-...)")
        vals: dict[str, float] = {}
        for c in NUMERIC_COLUMNS:
            v = e.get(c)
            if isinstance(v, bool) or not isinstance(v, int | float):
                errs.append(f"{where}: numeric {c} required")
                continue
            if v < 0:
                errs.append(f"{where}: {c} must be >= 0")
            if c in PROBABILITY_COLUMNS and v > 1:
                errs.append(f"{where}: {c} must be a probability")
            if c in cols and isinstance(cols[c], Mapping) and isinstance(cols[c].get("units"), str):
                vals[c] = _si(v, cols[c]["units"])
        for c, ev in (e.get("evidence") or {}).items():
            if c not in NUMERIC_COLUMNS:
                errs.append(f"{where}: evidence override for unknown column {c}")
            errs += _check_evidence(f"{where}.{c}", ev)
        pos = tuple(e.get("positions") or ())
        if not pos:
            errs.append(f"{where}: positions required")
        dup = seen_pos & set(pos)
        if dup:
            errs.append(f"{where}: positions {sorted(dup)} already used")
        seen_pos |= set(pos)
        cls = ItemClass(
            code=code,
            index=i,
            name=str(e.get("name", "")),
            part_no=str(e.get("part_no", "")),
            maker=str(e.get("maker", "")),
            system=str(e.get("system", "")),
            lru=e.get("lru"),
            positions=pos,
            grounding=e.get("mesm") == "G",
            ambiguity=str(e.get("ambiguity", "")),
            repair_level=str(e.get("repair_level", "")),
            consumable=bool(e.get("consumable", False)),
            inspectable_by=tuple(e.get("inspectable_by") or ()),
            values=vals,
        )
        classes.append(cls)
        for p in pos:
            positions.append(Position(p, len(positions), cls))
    if errs:
        raise CatalogueError(errs)
    h = digest(canonical_json(doc), PERSON_PARAMS)
    return Catalogue(
        classes=tuple(classes),
        positions=tuple(positions),
        columns=cols,
        synthetic_label=str(doc.get("synthetic_label", "")),
        hash=h,
        by_code={c.code: c for c in classes},
        pos_by_code={p.code: p for p in positions},
    )


def load_codes(path: Path | None = None) -> CodeTables:
    path = path or params_dir() / "M18" / "codes.yaml"
    doc = load_yaml(path)
    errs: list[str] = []
    if not isinstance(doc, Mapping) or doc.get("format") != CODES_FORMAT:
        raise CatalogueError([f"{path.name}: format must be {CODES_FORMAT}"])
    errs += _check_evidence("codes", doc.get("evidence"))
    tables = doc.get("tables") or {}
    for need in ("when_discovered", "type_maint", "action_taken", "malfunction", "inspection_type"):
        if need not in tables:
            errs.append(f"code table {need} missing")
    for name, t in tables.items():
        if name == "servicing_schedule":
            continue
        for code, d in t.items():
            if not isinstance(d, Mapping) or not d.get("meaning") or not d.get("transfer"):
                errs.append(f"{name}.{code}: meaning and transfer required")
    order = tuple(tables.get("servicing_schedule", {}).get("order", ()))
    for s in order:
        if s not in tables.get("inspection_type", {}):
            errs.append(f"servicing type {s} is not an inspection_type code")
    if errs:
        raise CatalogueError(errs)
    return CodeTables(
        tables={k: v for k, v in tables.items() if k != "servicing_schedule"},
        texts=doc.get("texts") or {},
        servicing_order=order,
        synthetic_label=str(doc.get("synthetic_label", "")),
        hash=digest(canonical_json(doc), PERSON_PARAMS),
    )
