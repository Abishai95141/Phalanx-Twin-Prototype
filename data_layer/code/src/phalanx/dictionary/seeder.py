"""Seeder: ``parameter_inventory.csv`` + seed overlay + platform tables -> per-subsystem YAML sources (M01).

The inventory (189 logical rows x 33 fields, research_notes) is free text. The seed overlay
(``configs/<platform>/dictionary/seed/overlay.yaml``) gives each row a structured interpretation: quantity,
unit, numeric range, quantisation, lane/unit/component expansion. The seeder:

0. redacts restricted-manual fragments from every inventory field before anything reads them
   (:mod:`.redact`, report Appendix A1): such values are never carried into a source file, the compiled
   dictionary or a generated artefact, and no field can cite them;
1. checks that the overlay covers exactly the inventory rows;
2. expands each row into physical channels (lanes, units, components; rules R-LANE-*, R-UNITS-*,
  R-COMPONENTS);
3. carries the row's evidence tag and source, and gives every channel field a provenance ref: ``inv`` when
  the value
   is written in the row (verified with :mod:`.textcheck`), otherwise a rule from ``tables/rules.yaml``;
4. assigns transports, rate groups and sinks from the inventory columns;
5. allocates the SYNTHETIC Phalanx ICD (1553 RT/SA/word, ARINC-429 labels, FTI PCM words; :mod:`.icd`);
6. returns one source document per subsystem.

Seeded source files carry ``generated_by: seeder``. Edit the overlay or the tables and re-run the seeder; do
not edit seeded files by hand (tests/unit/test_dictionary_seed.py checks they are in sync).
"""

from __future__ import annotations

import copy
import csv
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import icd
from .redact import redact_row
from .schema import FORMAT_SOURCE, parse_tag_classes
from .textcheck import (
    acq_group_for,
    bus_group_for,
    contains_number,
    marked_assumption,
    unit_justified,
)
from .yamlio import dump_yaml, load_yaml

__all__ = [
    "INVENTORY_FIELDS",
    "SUBSYSTEM_FILES",
    "SeedError",
    "core_tag_for",
    "read_inventory",
    "render_sources",
    "seed_sources",
    "write_sources",
]

INVENTORY_FIELDS = (
    "param_id",
    "subsystem",
    "name",
    "physical_quantity",
    "units",
    "origin_sensor_type",
    "origin_lru",
    "measurement_class",
    "computed_by",
    "range",
    "native_resolution",
    "recommended_quantization",
    "native_rate_hz",
    "bus",
    "bus_rate_hz",
    "recorder_rate_hz",
    "redundancy",
    "sink_cockpit",
    "sink_crash_recorder",
    "sink_ecms_hums",
    "sink_mpdru_maint_download",
    "sink_fti_only",
    "validity_status_flags",
    "physical_drivers",
    "related_params",
    "texture_mechanisms",
    "texture_ref",
    "rate_group_acquisition",
    "rate_group_bus",
    "rate_group_record",
    "evidence_tag",
    "source",
    "notes_conflicts",
)

#: inventory subsystem -> source file stem
SUBSYSTEM_FILES = {
    "Engine (F404-GE-IN20)": "engine",
    "Engine usage (ECMS)": "engine_usage",
    "Engine usage (ground)": "engine_usage",
    "Flight control (DFCC)": "flight_control",
    "Air data (ADC x4)": "air_data",
    "Navigation (INS/GPS, AHRS, radar altimeter)": "navigation",
    "Hydraulics (2 x 280 bar systems)": "hydraulics",
    "Fuel (ECFM-C)": "fuel",
    "Electrical power": "electrical",
    "ECS and life support": "ecs_life_support",
    "Landing gear, brakes, tyres, NWS, chute": "landing_gear",
    "Secondary power (AMAGB, PTO, JFS)": "secondary_power",
    "Fire protection / warnings": "fire",
    "Avionics status, warnings, recorder & metadata": "avionics_status",
    "Aircraft usage counters": "usage",
    "Ground inspection measurements (not on aircraft data path)": "ground_inspection",
}

SINK_COLUMNS = {
    "COCKPIT": "sink_cockpit",
    "CDR": "sink_crash_recorder",
    "ECMS_HUMS": "sink_ecms_hums",
    "MPDRU": "sink_mpdru_maint_download",
    "FTI": "sink_fti_only",
}

#: subsystem file -> utility EU that digitises and publishes it (rule R-ICD-UTILITY)
UTILITY_EU = {
    "hydraulics": "BHEEM_EU",
    "electrical": "BHEEM_EU",
    "secondary_power": "BHEEM_EU",
    "landing_gear": "BHEEM_EU",
    "fire": "BHEEM_EU",
    "fuel": "ECFM_C",
    "ecs_life_support": "ECFM_C",
}

#: inventory origin_lru prefix -> (LRU id or "@EU" for the subsystem's utility EU, provenance)
ORIGINS: tuple[tuple[str, str, str], ...] = (
    ("DFCC / utility EU", "DFCC", "R-ICD-DFCC"),
    ("DFCC", "DFCC", "inv"),
    ("quadruplex ADC", "ADC", "inv"),
    ("FADEC", "FADEC", "inv"),
    ("ECMS / FADEC", "ECMS", "R-ICD-FADEC"),
    ("engine sump / ECMS", "ECMS", "inv"),
    ("ECMS", "ECMS", "inv"),
    ("INGPS", "INGPS", "inv"),
    ("AHRS", "AHRS", "inv"),
    ("Radar altimeter", "RADALT", "inv"),
    ("utility EU", "@EU", "R-ICD-UTILITY"),
    ("ECFM-C", "ECFM_C", "inv"),
    ("5 kW DC GCU", "DC_GCU", "inv"),
    ("GCU", "GCU", "inv"),
    ("TRU", "TRU", "inv"),
    ("Battery display unit", "BDU", "inv"),
    ("Master box", "MASTER_BOX", "inv"),
    ("CPCS", "CPCS", "inv"),
    ("Hot-air leak detection control box", "HALD_CB", "inv"),
    ("OBOGS", "OBOGS", "inv"),
    ("BHEEM-EU / anti-skid unit", "ANTISKID", "inv"),
    ("BHEEM-EU", "BHEEM_EU", "inv"),
    ("NWS controller", "NWS_CTRL", "inv"),
    ("fire detection control unit", "FDCU", "inv"),
    ("OAC (BC role assumed)", "OAC", "R-INV-FIELD-ASSUMPTION"),
    ("OAC / each LRU", "OAC", "inv"),
    ("OAC / recorders", "OAC", "inv"),
    ("OAC / ground", "OAC", "inv"),
    ("OAC/utility EU/ground", "OAC", "R-INV-FIELD-ASSUMPTION"),
    ("each RT LRU", "@RT", "R-PER-RT"),
    ("each LRU", "@RT", "R-PER-RT"),
    ("CWS", "CWS", "inv"),
    ("cockpit -> OAC/ECMS", "OAC", "inv"),
    ("ground decoder / OAC", "GROUND", "inv"),
    ("fatigue meter / OAC function", "OAC", "R-INV-FIELD-ASSUMPTION"),
    ("FTI DAS", "FTI_DAS", "inv"),
    ("FTI", "FTI_DAS", "inv"),
    ("DVR", "DVR", "inv"),
    ("Flight Test Panel", "FTP", "inv"),
    ("SMS / OAC", "SMS", "inv"),
    ("ground (technician", "GROUND", "inv"),
    ("ground station", "GROUND", "inv"),
)

#: lane templates: (lanes, add voted output, expansion rule, consumer LRU of the lanes, lane transport)
TEMPLATES = {
    "fcs_quad_v": (("A", "B", "C", "D"), True, "R-LANE-FCS-QUAD", "DFCC", "internal"),
    "fcs_quad": (("A", "B", "C", "D"), False, "R-VOTED-SEPARATE", "DFCC", "internal"),
    "ad_quad_v": (("A", "B", "C", "D"), True, "R-LANE-AD-QUAD", "DFCC", "rs422"),
    "fadec_dual_v": (("A", "B"), True, "R-LANE-FADEC-DUAL", "FADEC", "internal"),
}
LANE_LABEL = {
    "fcs_quad_v": "DFCC lane",
    "fcs_quad": "DFCC lane",
    "ad_quad_v": "ADC lane",
    "fadec_dual_v": "FADEC lane",
    "actuators": "sensor core",
}

MIL1553_BUS_GROUPS = icd.BUS_GROUP_ORDER
RT_DIRECT = {"INGPS", "AHRS", "RADAR", "SMS"}
UTILITY_SOURCES = {
    "BHEEM_EU",
    "ECFM_C",
    "GCU",
    "DC_GCU",
    "TRU",
    "BDU",
    "MASTER_BOX",
    "CPCS",
    "HALD_CB",
    "OBOGS",
    "NWS_CTRL",
    "ANTISKID",
    "FDCU",
}
CHANNEL_KEY_ORDER = (
    "measurand_id",
    "lane",
    "unit_id",
    "component",
    "role",
    "name",
    "quantity",
    "units",
    "pressure_ref",
    "signal",
    "sensor_type",
    "source_lru",
    "acq_lru",
    "range",
    "native_step",
    "converter_step",
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
    "inv_tokens",
    "notes",
)


GENERATED_BY = "seeder (src/phalanx/dictionary/seeder.py); edit seed/overlay.yaml, not this file"


class SeedError(ValueError):
    """The inventory, the overlay or the tables are inconsistent; the message lists every problem."""


# ------------------------------------------------------------------------------------------------------------
# Inventory
# ------------------------------------------------------------------------------------------------------------
def read_inventory(path: str | Path) -> list[dict[str, str]]:
    """Read the inventory CSV and check its shape (33 fields, unique param_ids)."""
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != INVENTORY_FIELDS:
            raise SeedError(f"inventory header mismatch: {reader.fieldnames}")
        rows = [dict(r) for r in reader]
    ids = [r["param_id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise SeedError(f"duplicate param_id in inventory: {dupes}")
    return rows


#: evidence classes from strongest to weakest (core_tag takes the weakest class a row mentions)
TAG_STRENGTH = ("DIRECT", "DIRECT-unnamed", "DIRECT-part", "MEASURED", "TRANSFER", "ASSUMPTION")


def _donor(text: str) -> str:
    """The donor named after the first TRANSFER in an inventory tag ('' if none is written)."""
    i = text.find("TRANSFER")
    rest = text[i + len("TRANSFER") :].strip() if i >= 0 else ""
    if rest.startswith(":"):
        stops: tuple[str, ...] = (";", "(")
        rest = rest[1:].strip()
    elif rest.startswith("("):
        depth, out = 0, []
        for ch in rest:
            depth += (ch == "(") - (ch == ")")
            out.append(ch)
            if depth == 0:
                break
        stops, rest = (";",), "".join(out)[1:-1]
    else:
        stops = (";", "(", " + ")
    for stop in stops:
        rest = rest.split(stop, 1)[0]
    return rest.strip(" .,:")


def core_tag_for(tag_text: str, classes: list[str], donor: str | None = None) -> str:
    """A tag that parses with phalanx.core.module.EvidenceTag: the weakest class the inventory tag mentions
    (conservative), with the donor for TRANSFER (from the tag text, or the overlay's ``tag_donor``)."""
    weakest = max(classes, key=TAG_STRENGTH.index)
    if weakest != "TRANSFER":
        return weakest
    d = _donor(tag_text) or donor
    if not d:
        raise SeedError(f"TRANSFER tag {tag_text!r} names no donor; add tag_donor to the overlay")
    return f"TRANSFER: {d}"


def _resolve_origin(origin: str, subsystem: str) -> tuple[str, str]:
    for prefix, lru, prov in ORIGINS:
        if origin.startswith(prefix):
            if lru == "@EU":
                if subsystem not in UTILITY_EU:
                    raise SeedError(f"origin {origin!r}: no utility EU for subsystem {subsystem}")
                lru = UTILITY_EU[subsystem]
            if "[ASSUMPTION" in origin and prov == "inv":
                prov = "R-INV-FIELD-ASSUMPTION"
            return lru, prov
    raise SeedError(f"unmapped origin_lru {origin!r}")


# ------------------------------------------------------------------------------------------------------------
# Value helpers (each returns value, provenance ref and an optional literal token)
# ------------------------------------------------------------------------------------------------------------
def _vp(spec: Any) -> tuple[Any, str | None, str | None, dict[str, Any]]:
    """Split an overlay value spec into (value, rule-or-None, token-or-None, extras)."""
    if isinstance(spec, dict) and "v" in spec:
        extras = {k: v for k, v in spec.items() if k not in ("v", "p", "tok")}
        return spec["v"], spec.get("p"), spec.get("tok"), extras
    return spec, None, None, {}


class _Ctx:
    """Tables and accumulated errors for one seeding run."""

    def __init__(self, config_dir: Path):
        manifest = load_yaml(config_dir / "dictionary.yaml")
        self.manifest = manifest
        t = manifest["tables"]
        self.lrus = load_yaml(config_dir / t["lrus"])["lrus"]
        self.buses = load_yaml(config_dir / t["buses"])
        self.groups = load_yaml(config_dir / t["rate_groups"])["groups"]
        self.sinks = load_yaml(config_dir / t["sinks"])["sinks"]
        self.code_tables = load_yaml(config_dir / t["code_tables"])["tables"]
        self.rules = load_yaml(config_dir / t["rules"])["rules"]
        self.release_date = manifest["release_date"]
        self.errors: list[str] = []
        self.rt_of: dict[str, tuple[str, int]] = {}
        for bus, b in self.buses["mil1553"].items():
            for lru, rt in b["rts"].items():
                self.rt_of[lru] = (bus, rt["address"])

    def err(self, pid: str, msg: str) -> None:
        self.errors.append(f"{pid}: {msg}")

    def rule(self, pid: str, ref: str | None) -> str:
        if ref is None or ref in ("inv", "R-INV"):
            return "inv"
        if ref not in self.rules:
            self.err(pid, f"unknown rule {ref}")
        return ref


# ------------------------------------------------------------------------------------------------------------
# Seeding
# ------------------------------------------------------------------------------------------------------------
def seed_sources(inventory_csv: str | Path, config_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Seed the per-subsystem source documents. Raises SeedError listing every problem found."""
    config_dir = Path(config_dir)
    rows, redacted = [], {}
    for raw in read_inventory(inventory_csv):  # step 0: redact before any value is read
        row, fields = redact_row(raw)
        rows.append(row)
        if fields:
            redacted[row["param_id"]] = fields
    overlay = load_yaml(config_dir / "seed" / "overlay.yaml")["params"]
    ctx = _Ctx(config_dir)
    ids = [r["param_id"] for r in rows]
    missing = sorted(set(ids) - set(overlay))
    extra = sorted(set(overlay) - set(ids))
    if missing or extra:
        raise SeedError(f"overlay does not match the inventory: missing {missing}, extra {extra}")
    unmapped = sorted({r["subsystem"] for r in rows} - set(SUBSYSTEM_FILES))
    if unmapped:
        raise SeedError(f"unmapped inventory subsystems: {unmapped}")

    params: dict[str, tuple[str, dict[str, Any]]] = {}
    for i, row in enumerate(rows, start=1):
        sub = SUBSYSTEM_FILES[row["subsystem"]]
        spec = copy.deepcopy(overlay[row["param_id"]])
        params[row["param_id"]] = (sub, _seed_param(ctx, i, row, sub, spec, redacted.get(row["param_id"])))
    if ctx.errors:
        raise SeedError("seeding failed:\n  " + "\n  ".join(ctx.errors))
    _allocate_icd(ctx, [p for _, p in params.values()])
    if ctx.errors:
        raise SeedError("ICD allocation failed:\n  " + "\n  ".join(ctx.errors))

    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        sub, p = params[row["param_id"]]
        doc = out.setdefault(
            sub,
            {
                "format": FORMAT_SOURCE,
                "generated_by": GENERATED_BY,
                "platform": ctx.manifest["platform"],
                "subsystem": sub,
                "inventory_subsystems": [],
                "parameters": {},
            },
        )
        if row["subsystem"] not in doc["inventory_subsystems"]:
            doc["inventory_subsystems"].append(row["subsystem"])
        doc["parameters"][row["param_id"]] = p
    return out


def _seed_param(
    ctx: _Ctx,
    row_no: int,
    row: dict[str, str],
    sub: str,
    spec: dict[str, Any],
    redacted: list[str] | None = None,
) -> dict[str, Any]:
    pid = row["param_id"]
    inventory: dict[str, Any] = {"row": row_no, "fields": {k: row[k] for k in INVENTORY_FIELDS}}
    if redacted:
        inventory["redacted"] = list(redacted)
    classes = parse_tag_classes(row["evidence_tag"])
    if not classes:
        ctx.err(pid, f"evidence tag {row['evidence_tag']!r} names no evidence class")
    if not row["source"].strip():
        ctx.err(pid, "inventory row has no source")
    param: dict[str, Any] = {
        "name": row["name"],
        "inventory": inventory,
        "measurement_class": row["measurement_class"],
        "computed_by": row["computed_by"] or None,
        "evidence": {
            "tag": row["evidence_tag"],
            "source": row["source"],
            "classes": classes,
            "primary": classes[0] if classes else "ASSUMPTION",
            "core_tag": core_tag_for(row["evidence_tag"], classes, spec.get("tag_donor"))
            if classes
            else "ASSUMPTION",
        },
        "notes": row["notes_conflicts"] or None,
        "channels": {},
    }
    source_lru, source_prov = _resolve_origin(row["origin_lru"], sub)
    for ch_id, ch in _expand(ctx, row, sub, spec, source_lru, source_prov):
        if ch_id in param["channels"]:
            ctx.err(pid, f"duplicate channel id {ch_id}")
        param["channels"][ch_id] = {k: ch[k] for k in CHANNEL_KEY_ORDER if k in ch}
    return param


def _structure(ctx: _Ctx, row: dict[str, str], spec: dict[str, Any]) -> tuple[list, list, str, str | None]:
    """(units [(unit_id, prov)], components [dict], expansion prov, lane template)."""
    pid = row["param_id"]
    units: list[tuple[str | None, str]] = [(None, "inv")]
    expansion = "inv"
    template = spec.get("expand", "single")
    if "per_rt" in spec:
        units = [
            (lru, "R-PER-RT") for lru in sorted(ctx.rt_of, key=lambda x: (ctx.rt_of[x][0], ctx.rt_of[x][1]))
        ]
        expansion = "R-PER-RT"
    elif "units_list" in spec:
        ul = spec["units_list"]
        assumed = set(ul.get("p_assumed", {}).get("ids", []))
        units = [(u, ul["p_assumed"]["p"] if u in assumed else ul["p"]) for u in ul["ids"]]
        expansion = ul["p"]
    elif "actuators" in spec:
        units = [(u, spec["actuators"]["p"]) for u in spec["actuators"]["ids"]]
        expansion = spec["actuators"]["p"]
        template = "actuators"
    comps = spec.get("components") or [None]
    if spec.get("components"):
        expansion = expansion if expansion != "inv" else "R-COMPONENTS"
    if template not in ("single", "actuators", *TEMPLATES):
        ctx.err(pid, f"unknown expand template {template}")
    if template in TEMPLATES:
        expansion = TEMPLATES[template][2]
    if "expand_prov" in spec:
        expansion = spec["expand_prov"]
    return units, comps, ctx.rule(pid, expansion), template


def _expand(
    ctx: _Ctx, row: dict[str, str], sub: str, spec: dict[str, Any], source_lru: str, source_prov: str
):
    pid = row["param_id"]
    units, comps, expansion, template = _structure(ctx, row, spec)
    base = {k: v for k, v in spec.items() if k != "components"}
    for unit_id, unit_prov in units:
        for comp in comps:
            fs = dict(base)
            if comp is not None:
                fs.update(comp)
            comp_id = comp["id"] if comp is not None else None
            measurand = ".".join(x for x in (pid, unit_id, comp_id) if x)
            src = unit_id if source_lru == "@RT" else source_lru
            src_prov = source_prov
            if comp_id and "known_values" in fs and pid == "AV.SW_CONFIG":
                src = {"STORES": "SMS"}.get(comp_id, comp_id)
                src_prov = "inv"
            exp_prov = unit_prov if unit_id is not None and unit_prov != "inv" else expansion
            if template in TEMPLATES or template == "actuators":
                lanes = (
                    list(TEMPLATES[template][0])
                    if template in TEMPLATES
                    else list(spec["actuators"]["lanes"])
                )
                add_v = TEMPLATES[template][1] if template in TEMPLATES else True
                common = (ctx, row, sub, fs, measurand)
                where = (template, unit_id, comp_id, src, src_prov, exp_prov)
                lane_ids = []
                for ln in lanes:
                    cid = f"{measurand}.{ln}"
                    lane_ids.append(cid)
                    yield cid, _channel(*common, ln, "lane", *where, [])
                if add_v:
                    yield f"{measurand}.V", _channel(*common, "V", "voted", *where, lane_ids)
            else:
                role = "placeholder" if "placeholder" in fs else "single"
                where = (template, unit_id, comp_id, src, src_prov, exp_prov)
                yield (
                    measurand,
                    _channel(ctx, row, sub, fs, measurand, "", role, *where, list(fs.get("inputs", []))),
                )


def _channel(
    ctx: _Ctx,
    row: dict[str, str],
    sub: str,
    fs: dict[str, Any],
    measurand: str,
    lane: str,
    role: str,
    template: str,
    unit_id: str | None,
    comp_id: str | None,
    source_lru: str,
    source_prov: str,
    exp_prov: str,
    inputs: list[str],
) -> dict[str, Any]:
    cid = f"{measurand}.{lane}" if lane else measurand
    prov: dict[str, str] = {"expansion": exp_prov}
    tokens: dict[str, str] = {}
    notes: list[str] = []
    extra: dict[str, Any] = {}  # optional channel fields set by _numeric (converter_step)
    for key in ("units_note", "note"):
        if key in fs:
            notes.append(str(fs[key]))

    # --- kind of value --------------------------------------------------------------------------------------
    kind = "numeric"
    if "bits" in fs or "fields" in fs or fs.get("per_rt") == "mil1553_status":
        kind = "bitfield"
    elif "enum" in fs:
        kind = "enum"
    elif "code_list" in fs:
        kind = "code"
    elif fs.get("text"):
        kind = "text"
    elif "placeholder" in fs:
        kind = "placeholder"

    # --- quantity and units ---------------------------------------------------------------------------------
    if kind == "numeric":
        quantity = fs.get("quantity")
        if quantity is None:
            ctx.err(cid, "numeric channel without quantity")
            quantity = "count"
        units, uprov, utok, uextra = _vp(fs.get("units"))
        if units is None:
            ctx.err(cid, "numeric channel without units")
            units = "dimensionless"
        if uextra.get("note"):
            notes.append(str(uextra["note"]))
        if uprov is None:
            if not unit_justified(units, row["units"], utok):
                ctx.err(
                    cid, f"unit {units!r} (token {utok!r}) is not written in inventory units {row['units']!r}"
                )
            if utok:
                tokens["units"] = utok
            uprov = "inv"
    else:
        quantity = {
            "bitfield": "discrete",
            "enum": "enum",
            "code": "code",
            "text": "text",
            "placeholder": "media",
        }[kind]
        units = "dimensionless"
        uprov = "inv" if unit_justified(units, row["units"]) else "R-DISCRETE-PACK"
    prov["quantity"] = ctx.rule(cid, fs.get("quantity_prov", "inv"))  # a rule where the row is reinterpreted
    prov["units"] = ctx.rule(cid, uprov)

    signal, sig_rule, _, _ = _vp(fs.get("signal", "computed"))
    if role == "voted":
        signal, sig_rule = "computed", None
    prov["signal"] = ctx.rule(cid, sig_rule)  # a rule where the row's measurement class is reinterpreted

    sensor_type = row["origin_sensor_type"].strip()
    sensor_type = None if sensor_type in ("", "-") else sensor_type
    if sensor_type is not None:
        prov["sensor_type"] = "inv"

    # --- producer and clock domain --------------------------------------------------------------------------
    prov["source_lru"] = ctx.rule(cid, source_prov)
    acq_lru = fs.get("acq_lru")
    acq_prov = "inv"
    if role == "lane" and template in TEMPLATES:
        acq_lru = {"ad_quad_v": "ADC"}.get(template, TEMPLATES[template][3])
        acq_prov = TEMPLATES[template][2]
    elif role == "lane" and template == "actuators":
        acq_lru, acq_prov = "DFCC", exp_prov
    elif acq_lru is not None:
        acq_prov = "inv"
    elif "frame_hz" in ctx.lrus.get(source_lru, {}) or source_lru in ("GROUND", "FTI_DAS", "FTP", "DVR"):
        acq_lru = source_lru
    elif source_lru in UTILITY_SOURCES and sub in UTILITY_EU:
        acq_lru, acq_prov = UTILITY_EU[sub], "R-ICD-UTILITY"
    else:
        acq_lru = source_lru
    prov["acq_lru"] = ctx.rule(cid, acq_prov)

    # --- rate groups ----------------------------------------------------------------------------------------
    acq = acq_group_for(row["rate_group_acquisition"])
    acq_p = "R-INV-FIELD-ASSUMPTION" if "ASSUMPTION" in row["native_rate_hz"] else "inv"
    if fs.get("per_rt"):
        acq, acq_p = "LRU-INT", "R-PER-RT"
    if acq is None:
        ctx.err(cid, f"unmapped acquisition group {row['rate_group_acquisition']!r}")
        acq = "EVT"
    mapped = bus_group_for(row["rate_group_bus"])
    if mapped is None:
        ctx.err(cid, f"unmapped bus group {row['rate_group_bus']!r}")
        mapped = (None, None)
    bus_group, producer = mapped
    bus_p = "R-INV-FIELD-ASSUMPTION" if "ASSUMPTION" in row["bus_rate_hz"] + row["rate_group_bus"] else "inv"
    if "bus_override" in fs:
        bo = fs["bus_override"]
        bus_group, producer, bus_p = bo["group"], bo.get("producer"), bo["p"]

    # --- transport ------------------------------------------------------------------------------------------
    transport, tprov = _transport(
        ctx, cid, row, sub, fs, role, template, source_lru, unit_id, lane, acq, bus_group
    )
    if transport["type"] in ("internal", "rs422", "maint_record", "placeholder", "recorder_time"):
        bus_group, producer = None, None
    if transport["type"] == "download":
        bus_group, producer, bus_p = "SORTIE", None, "inv"
    if transport["type"] == "video":
        bus_group, producer = "VIDEO", None
    prov["transport"] = ctx.rule(cid, tprov)
    prov["rates.acquisition"] = ctx.rule(cid, acq_p)
    if bus_group is not None:
        prov["rates.bus"] = ctx.rule(cid, bus_p)
    if producer is not None:
        prov["rates.producer"] = ctx.rule(cid, bus_p)
    rates = {"acquisition": acq, "bus": bus_group, "producer": producer}

    # --- encoding, range, quantisation ----------------------------------------------------------------------
    rng, native, lsb, enc, adc_bits, cal = None, None, None, None, None, None
    if kind == "bitfield":
        enc, eprov = _bitfield(ctx, cid, row, fs, transport)
        prov["encoding"] = ctx.rule(cid, eprov)
        if fs.get("range") is not None:  # a discrete's span (0.1.3: ENG.AB_LIT 0/1, as the row writes it)
            rng = _discrete_range(ctx, cid, row, fs, prov, enc)
    elif kind == "enum":
        table = fs["enum"]
        if table not in ctx.code_tables:
            ctx.err(cid, f"unknown code table {table}")
        enc = {"type": "enum", "word_bits": 16, "words": 1, "code_table": table}
        prov["encoding"] = ctx.rule(cid, ctx.code_tables.get(table, {}).get("prov", "R-CODES-SYNTHETIC"))
    elif kind == "code":
        enc = {
            "type": "code_word",
            "word_bits": 16,
            "words": 1,
            "format": "SSS-NNN",
            "prefixes": list(fs["code_list"]["prefixes"]),
        }
        prov["encoding"] = "R-CODES-SYNTHETIC"
    elif kind == "text":
        enc = {"type": "string"}
        if fs.get("known_values"):
            enc["known_values"] = [str(v) for v in fs["known_values"]]
        prov["encoding"] = "inv"
    elif kind == "placeholder":
        enc = {"type": "none"}
        prov["encoding"] = ctx.rule(cid, fs["placeholder"])
    else:
        rng, native, lsb, enc, adc_bits, cal = _numeric(
            ctx,
            cid,
            row,
            fs,
            role,
            transport,
            prov,
            tokens,
            notes,
            fadec_lane=template == "fadec_dual_v",
            extra=extra,
        )

    # --- validity -------------------------------------------------------------------------------------------
    validity, vprov = _validity(transport, enc)
    prov["validity"] = ctx.rule(cid, vprov)

    # --- sinks ----------------------------------------------------------------------------------------------
    consumer = TEMPLATES[template][3] if template in TEMPLATES else acq_lru  # the voting/validating LRU
    sinks = _sinks(ctx, cid, row, sub, fs, role, consumer)

    # --- limits ---------------------------------------------------------------------------------------------
    limits = []
    for lim in fs.get("limits", []) if role != "lane" else []:
        p = lim.get("p")
        out = {"kind": lim["kind"]}
        for k in ("low", "high", "value"):
            if k in lim:
                out[k] = lim[k]
                if p is None and not _number_in_row(row, lim[k]):
                    ctx.err(cid, f"limit {lim['kind']} {k}={lim[k]} is not written in the inventory row")
        out["prov"] = ctx.rule(cid, p)
        limits.append(out)

    if role == "placeholder" or kind == "placeholder":
        role = "placeholder"
    proxy = any(str(v).startswith("P-") for v in prov.values()) or any(
        s["prov"].startswith("P-") or s["group_prov"].startswith("P-") for s in sinks
    )
    name = row["name"]
    if unit_id:
        name += f" [{unit_id}]"
    if comp_id:
        name += f" - {comp_id}"
    if role == "lane":
        name += f" ({LANE_LABEL.get(template, 'lane')} {lane})"
    elif role == "voted":
        name += " (voted/selected output)"
    ch: dict[str, Any] = {
        "measurand_id": measurand,
        "lane": lane,
        "role": role,
        "name": name,
        "quantity": quantity,
        "units": units,
        "signal": signal,
        "sensor_type": sensor_type,
        "source_lru": source_lru,
        "acq_lru": acq_lru,
        "range": rng,
        "native_step": native,
        "recorder_lsb": lsb,
        "adc_bits": adc_bits,
        "encoding": enc,
        "transport": transport,
        "validity": validity,
        "rates": rates,
        "sinks": sinks,
        "calibration": cal,
        "limits": limits,
        "inputs": inputs,
        "proxy": proxy,
        "prov": dict(sorted(prov.items())),
        "notes": notes,
    }
    for f, ref in ch["prov"].items():
        if ref == "inv" and marked_assumption(row, f):
            ch["prov"][f] = "R-INV-FIELD-ASSUMPTION"
    for snk in sinks:
        if snk["group_prov"] == "inv" and marked_assumption(row, "sink_group"):
            snk["group_prov"] = "R-INV-FIELD-ASSUMPTION"
    if unit_id:
        ch["unit_id"] = unit_id
    if comp_id:
        ch["component"] = comp_id
    if extra.get("converter_step") is not None:
        ch["converter_step"] = extra["converter_step"]
    if quantity == "pressure":
        ch["pressure_ref"] = fs.get("pressure_ref")
        if ch["pressure_ref"] is None:
            ctx.err(cid, "pressure channel without pressure_ref")
    if tokens:
        ch["inv_tokens"] = dict(sorted(tokens.items()))
    return ch


def _number_in_row(row: Mapping[str, str], value: float) -> bool:
    fields = (
        "range",
        "notes_conflicts",
        "texture_mechanisms",
        "name",
        "physical_drivers",
        "validity_status_flags",
    )
    return any(contains_number(row[f], value) for f in fields)


def _transport(ctx, cid, row, sub, fs, role, template, source_lru, unit_id, lane, acq, bus_group):
    """(transport dict without allocated addresses, provenance ref)."""
    if role == "lane":
        if template == "ad_quad_v":
            return {"type": "rs422", "link": "ADC-DFCC", "unit": lane}, "R-ICD-RS422"
        lru = TEMPLATES[template][3] if template in TEMPLATES else "DFCC"
        return {"type": "internal", "lru": lru}, TEMPLATES[template][
            2
        ] if template in TEMPLATES else "R-SINK-INTERNAL"
    if fs.get("transport") == "recorder_time":
        return {"type": "recorder_time"}, "R-TIME-RTC"
    if fs.get("placeholder") == "P-DVR":
        return {"type": "video"}, "P-DVR"
    if fs.get("placeholder"):
        return {"type": "placeholder"}, fs["placeholder"]
    per_rt = fs.get("per_rt")
    if per_rt in ("mil1553_status", "mil1553_modecode"):
        bus, rt = ctx.rt_of[unit_id]
        t = {"type": per_rt, "bus": bus, "rt": rt, "rt_lru": unit_id}
        if per_rt == "mil1553_modecode":
            t["mode_code"] = 19
        return t, "R-PER-RT"
    if fs.get("transport") == "internal":
        return {"type": "internal", "lru": source_lru}, "inv"
    if bus_group in MIL1553_BUS_GROUPS:
        if source_lru == "CWS":
            return {"type": "arinc429", "link": "CWS-OAC"}, "R-ICD-429"
        if source_lru == "RADALT":
            return {"type": "arinc429", "link": "RADALT-OAC"}, "R-ICD-429"
        if source_lru == "OAC":
            return {
                "type": "mil1553",
                "bus": "AV-MUX-2",
                "rt": 31,
                "rt_lru": "OAC",
                "tr": "R",
            }, "R-ICD-OAC-BCAST"
        if per_rt == "data":
            rt_lru, prov = unit_id, "R-PER-RT"
        elif source_lru in ("DFCC", "ADC", "FTP"):
            rt_lru, prov = "DFCC", "R-ICD-DFCC"
        elif source_lru in ("FADEC", "ECMS"):
            rt_lru, prov = "FADEC", "R-ICD-FADEC"
        elif source_lru in RT_DIRECT:
            rt_lru, prov = source_lru, "R-ICD-RT-MAP"
        elif source_lru in UTILITY_SOURCES and sub in UTILITY_EU:
            rt_lru, prov = UTILITY_EU[sub], "R-ICD-UTILITY"
        else:
            ctx.err(cid, f"no 1553 terminal for source LRU {source_lru}")
            rt_lru, prov = "OAC", "R-ICD-RT-MAP"
        bus, rt = ctx.rt_of[rt_lru]
        return {"type": "mil1553", "bus": bus, "rt": rt, "rt_lru": rt_lru, "tr": "T"}, prov
    if bus_group == "FTI":
        return {"type": "fti_pcm", "stream": "FTI-PCM"}, "R-ICD-FTI-PCM"
    if bus_group == "SORTIE":
        return {"type": "download", "product": "sortie_record"}, "inv"
    if bus_group == "VIDEO":
        return {"type": "video"}, "inv"
    if acq == "INSP":
        return {"type": "maint_record"}, "inv"
    return {"type": "internal", "lru": source_lru}, "inv"


def _bitfield(ctx, cid, row, fs, transport) -> tuple[dict[str, Any], str]:
    if fs.get("per_rt") == "mil1553_status":
        bits = ctx.code_tables["mil1553_status_word"]["bits"]
        fields = [
            {"name": n, "lsb_bit": int(b), "width": 1}
            for b, n in sorted(bits.items(), key=lambda x: int(x[0]))
        ]
        return {"type": "bitfield", "word_bits": 16, "words": 1, "fields": fields}, "R-VALIDITY"
    if "fields" in fs:
        fields = [dict(f) for f in fs["fields"]]
        prov = "R-PER-RT"
    else:
        names, p, tok, extra = _vp(fs["bits"])
        if names == "slots":
            lo, hi = extra["slots"]
            pattern = ctx.code_tables["cws_legends"]["slot_pattern"]
            names = [pattern.format(n=n) for n in range(lo, hi + 1)]
            p = "R-CODES-SYNTHETIC"
        if tok is not None and tok not in row["name"] + row["validity_status_flags"]:
            ctx.err(cid, f"bit-count token {tok!r} not in the inventory row")
        fields = [{"name": n, "lsb_bit": i, "width": 1} for i, n in enumerate(names)]
        prov = p or "R-DISCRETE-PACK"
    width = max(f["lsb_bit"] + f["width"] for f in fields)
    limit = {"arinc429": icd.ARINC429_BNR_BITS, "fti_pcm": icd.FTI_WORD_BITS}.get(transport["type"], 32)
    if width > limit:
        ctx.err(cid, f"{width} bits do not fit the {transport['type']} word")
    word_bits = 16 if width <= 16 else 32
    if transport["type"] in ("arinc429", "fti_pcm"):
        word_bits = limit
    return {
        "type": "bitfield",
        "word_bits": word_bits,
        "words": 1 if transport["type"] in ("arinc429", "fti_pcm") else max(1, math.ceil(word_bits / 16)),
        "fields": fields,
    }, prov


#: assumed FADEC converter resolution of the FADEC lane channels (rule R-FADEC-ADC; sweep 12-16 bits)
FADEC_LANE_ADC_BITS = 14


def _discrete_range(ctx, cid, row, fs, prov, enc):
    """The 0..max span of a bitfield discrete: written in the inventory row (or rule-cited) and inside the
    value its defined fields can carry."""
    rng_v, rng_p, _, _ = _vp(fs["range"])
    lo, hi = rng_v
    if rng_p is None:
        for v in (lo, hi):
            if v != 0 and not contains_number(row["range"], v):
                ctx.err(cid, f"range value {v} is not written in inventory range {row['range']!r}")
    top = sum(((1 << int(f["width"])) - 1) << int(f["lsb_bit"]) for f in enc["fields"])
    if lo != 0 or not 0 < hi <= top:
        ctx.err(cid, f"discrete range [{lo}, {hi}] must be [0, n] with n inside its fields (max {top})")
    prov["range"] = ctx.rule(cid, rng_p)
    return {"min": lo, "max": hi}


def _numeric(ctx, cid, row, fs, role, transport, prov, tokens, notes, *, fadec_lane=False, extra=None):
    extra = {} if extra is None else extra
    """Range, native step, recorder LSB, encoding, ADC bits and calibration of a numeric channel."""
    rng_v, rng_p, _, rextra = _vp(fs.get("range"))
    rng = None
    if rng_v is not None:
        lo, hi = rng_v
        rng = {"min": lo, "max": hi}
        if rextra.get("note"):
            notes.append(str(rextra["note"]))
        if rextra.get("band"):
            notes.append(f"full scale bracketing the inventory band {rextra['band']}")
        if rng_p is None:
            for v in (lo, hi):
                if v is not None and v != 0 and not contains_number(row["range"], v):
                    ctx.err(cid, f"range value {v} is not written in inventory range {row['range']!r}")
        elif rng_p == "R-INV" and hi is None and "cumulative" not in row["range"]:
            ctx.err(cid, "open-ended range claimed from the inventory but the row does not say 'cumulative'")
        prov["range"] = ctx.rule(cid, rng_p)
    finite = rng is not None and rng["min"] is not None and rng["max"] is not None

    # word width the LSB is computed for
    words_assert = fs.get("words")
    ttype = transport["type"]
    if ttype == "arinc429":
        bits_for_lsb = 19
    elif ttype == "fti_pcm":
        bits_for_lsb = icd.FTI_WORD_BITS
    elif words_assert == 2:
        bits_for_lsb = 32
    else:
        bits_for_lsb = 16

    lsb_spec = fs.get("lsb")
    lsb = None
    recorded = ttype in ("mil1553", "arinc429", "fti_pcm")
    bnr_native = None  # a BNR word that quantises the value before a non-word path (download, record)
    if lsb_spec == "bnr":
        if not finite:
            ctx.err(cid, "lsb: bnr needs a finite range")
        else:
            if ttype == "arinc429":
                lsb = 2.0 ** math.ceil(math.log2(max(abs(rng["min"]), abs(rng["max"])) / (2**18 - 1)))
            else:
                lsb = icd.bnr_lsb(rng["min"], rng["max"], bits_for_lsb)
            if recorded:
                prov["recorder_lsb"] = "R-LSB-BNR"
            else:
                # e.g. SPS.JFS.OIL_QTY: the utility EU digitises into the row's 16-bit BNR word, then the
                # value travels in a download record (float64, no recorder word), so the word sets the
                # native step
                bnr_native, lsb = lsb, None
    elif lsb_spec is not None:
        lsb, lp, ltok, _ = _vp(lsb_spec)
        q = row["recommended_quantization"]
        if lp in (None, "R-INV", "R-LSB-DASHLINK", "R-LSB-MSDC", "R-LSB-INVREC", "R-INV-FIELD-ASSUMPTION"):
            ok = (ltok in q) if ltok else contains_number(q, lsb)
            if not ok:
                ctx.err(cid, f"LSB {lsb} (token {ltok!r}) is not written in inventory quantisation {q!r}")
            if ltok:
                tokens["recorder_lsb"] = ltok
        if lp == "R-LSB-DASHLINK" and "DASHlink" not in q and "dashlink" not in row["texture_ref"]:
            ctx.err(cid, "R-LSB-DASHLINK cited but the row does not cite DASHlink")
        if lp == "R-LSB-MSDC" and "MSDC" not in q:
            ctx.err(cid, "R-LSB-MSDC cited but the row does not cite the MSDC")
        if lp == "R-INV-FIELD-ASSUMPTION" and "ASSUMPTION" not in q:
            ctx.err(cid, "R-INV-FIELD-ASSUMPTION cited but the quantisation field is not marked [ASSUMPTION]")
        if lp is None:
            ctx.err(cid, "recommended quantisation needs an explicit rule (R-LSB-*)")
        prov["recorder_lsb"] = ctx.rule(cid, lp)

    nat_spec = fs.get("native")
    native = None
    if nat_spec is not None:
        native, np_, ntok, _ = _vp(nat_spec)
        nr = " | ".join((row["native_resolution"], row["units"]))  # a resolution may be stated with the unit
        if np_ is None:
            ok = (ntok in nr) if ntok else contains_number(nr, native)
            if not ok:
                ctx.err(cid, f"native step {native} (token {ntok!r}) is not written in {nr!r}")
            if ntok:
                tokens["native_step"] = ntok
        prov["native_step"] = ctx.rule(cid, np_)
    elif bnr_native is not None:
        native = bnr_native
        prov["native_step"] = "R-LSB-BNR"
    elif lsb is not None:
        native = lsb
        prov["native_step"] = "R-NATIVE-EQ-LSB"

    enc: dict[str, Any]
    if ttype == "recorder_time":
        enc = {"type": "int64_ticks", "tick_s": lsb}
        prov["encoding"] = "R-TIME-RTC"
    elif recorded:
        if not finite or lsb is None:
            ctx.err(cid, "a recorded numeric channel needs a finite range and an LSB")
            enc = {"type": "none"}
        else:
            try:
                etype, wbits = icd.select_word(rng["min"], rng["max"], lsb, transport=ttype)
            except ValueError as exc:
                ctx.err(cid, str(exc))
                etype, wbits = "bnr", 32
            enc = {"type": etype, "word_bits": wbits, "words": max(1, math.ceil(wbits / 16))}
            if ttype in ("arinc429", "fti_pcm"):
                enc["words"] = 1
            if words_assert is not None and enc["words"] != words_assert:
                ctx.err(cid, f"word count {enc['words']} differs from the asserted {words_assert}")
        prov["encoding"] = (
            "R-ICD-FTI-PCM" if ttype == "fti_pcm" else ("R-ICD-429" if ttype == "arinc429" else "R-ICD-WORDS")
        )
    else:
        # not word-encoded on a recorded path (LRU-internal value, download record, maintenance record)
        enc = {"type": "float64"}
        prov["encoding"] = prov["transport"]

    if role == "lane":
        # lanes are not recorded: only the native (sensor/LRU) quantiser applies; they keep the native step
        lsb = None
        prov.pop("recorder_lsb", None)

    adc_bits = None
    signal = _vp(fs.get("signal", "computed"))[0]
    if role == "lane" and fadec_lane and finite:
        # FADEC lanes: the native step is the FADEC's own converter step (span / 2^14), finer than the
        # recorded word LSB (0.1.3; until 0.1.2 it was carried as converter_step while M13 still scaled its
        # lane noise by the native step - M13 now quantises at this step with its lane noise in EU) - rule
        # R-FADEC-ADC
        native = (rng["max"] - rng["min"]) / 2**FADEC_LANE_ADC_BITS
        prov["native_step"] = "R-FADEC-ADC"
        tokens.pop("native_step", None)
        if signal == "analog":
            adc_bits = FADEC_LANE_ADC_BITS
            prov["adc_bits"] = "R-FADEC-ADC"
    elif signal == "analog" and role in ("lane", "single") and finite and native:
        span = rng["max"] - rng["min"]
        adc_bits = max(12, math.ceil(math.log2(span / native)))
        prov["adc_bits"] = "R-ADC-BITS"

    cal = None
    if recorded and enc.get("type") in ("bnr", "ubnr") and lsb is not None:
        cal = {"type": "polynomial", "coefficients": [0.0, float(lsb)], "date": ctx.release_date}
        prov["calibration"] = "R-CAL-LINEAR"
    return rng, native, lsb, enc, adc_bits, cal


def _validity(transport: dict[str, Any], enc: dict[str, Any]) -> tuple[dict[str, Any], str]:
    t = transport["type"]
    if t == "mil1553":
        return {
            "method": "validity_word",
            "word": 1,
            "bit": 15,
        }, "R-ICD-WORDS"  # word/bit set by the allocator
    if t == "arinc429":
        return {
            "method": "ssm",
            "table": "ssm_dis" if enc.get("type") == "bitfield" else "ssm_bnr",
        }, "R-VALIDITY"
    if t in ("mil1553_status", "mil1553_modecode"):
        return {"method": "rt_status"}, "R-VALIDITY"
    if t == "fti_pcm":
        return {"method": "frame_sync"}, "R-ICD-FTI-PCM"
    return {"method": "none"}, "R-VALIDITY"


def _sinks(ctx, cid, row, sub, fs, role, consumer) -> list[dict[str, Any]]:
    if role == "lane":
        return [
            {
                "sink": "INTERNAL",
                "basis": "derived",
                "group": None,
                "consumer": consumer,
                "prov": "R-SINK-INTERNAL",
                "group_prov": "R-SINK-INTERNAL",
            }
        ]
    if "sinks_fix" in fs:
        out = []
        for sink, consumer in fs["sinks_fix"].items():
            group = ctx.sinks[sink].get("default_group")
            s = {
                "sink": sink,
                "basis": "derived",
                "group": group,
                "prov": "R-SINK-FIX",
                "group_prov": "R-SINK-FIX",
            }
            if consumer:
                s["consumer"] = consumer
            out.append(s)
        return out
    record = _record_tokens(row)
    engine = sub in ("engine", "engine_usage")
    out = []
    for sink, col in SINK_COLUMNS.items():
        flag = row[col].strip()
        if not flag or flag[0] not in "YA":
            continue
        basis, prov = ("evidenced", "inv") if flag[0] == "Y" else ("assumed", "R-SINK-ASSUMED")
        group, gprov = record.get(sink, (None, None))
        if group is None and "*" in record and sink != "COCKPIT":
            group, gprov = record["*"]
        if group is None:
            group = ctx.sinks[sink]["default_group"]
            if sink == "ECMS_HUMS" and engine:
                group = ctx.sinks[sink]["default_group_engine"]
            if sink == "MPDRU" and "SORTIE" in row["rate_group_record"]:
                group = "SORTIE"
            gprov = "R-REC-DEFAULT"
            if sink == "ECMS_HUMS" and "IECMS" in flag:
                # the flag names the IECMS 10 Hz list (altitude, Mach, AoA, T0) [TRANSFER: CF-18 IECMS]
                group, gprov = "ECMS10", ("inv" if contains_number(flag, 10) else "R-RATE-ECMS")
            elif sink == "ECMS_HUMS" and "Nz" in flag:
                group, gprov = "ECMS1", "R-RATE-ECMS"  # IECMS 1 Hz list includes Nz
        override = fs.get("record_override", {}).get(sink)
        if override:
            group, gprov = override["group"], override["p"]
        out.append(
            {"sink": sink, "basis": basis, "group": group, "prov": prov, "group_prov": ctx.rule(cid, gprov)}
        )
    for sink, (group, gprov) in sorted(record.items()):
        if sink not in SINK_COLUMNS and sink != "*":
            # sinks named only by the record column (the maintenance record of ground inspections)
            out.append(
                {"sink": sink, "basis": "evidenced", "group": group, "prov": "inv", "group_prov": gprov}
            )
    for sink, consumer in fs.get("sinks_add", {}).items():
        out.append(
            {
                "sink": sink,
                "basis": "derived",
                "group": None,
                "consumer": consumer,
                "prov": "R-SINK-INTERNAL",
                "group_prov": "R-SINK-INTERNAL",
            }
        )
    if not out:
        ctx.err(cid, "no sink (orphan) - add sinks_fix to the overlay with a rule")
    return out


_ATTITUDE_WORDS = ("PITCH", "ROLL", "HDG", "HEADING", "BODY_RATES", "ACCEL")


def _record_tokens(row: Mapping[str, str]) -> dict[str, tuple[str, str]]:
    """Inventory rate_group_record -> {sink or '*': (group, prov)}."""
    t = row["rate_group_record"].strip()
    table: dict[str, dict[str, tuple[str, str]]] = {
        "EVT (on change)": {"*": ("EVT", "inv")},
        "CDR16": {"CDR": ("CDR16", "inv")},
        "CDR4": {"CDR": ("CDR4", "inv")},
        "CDR1 + HUMS": {"CDR": ("CDR1", "inv"), "ECMS_HUMS": ("HUMS", "inv")},
        "SORTIE": {"*": ("SORTIE", "inv")},
        "ECMS10 + CDR4": {"ECMS_HUMS": ("ECMS10", "inv"), "CDR": ("CDR4", "inv")},
        "maintenance record": {"MAINT_RECORD": ("INSP", "inv")},
        "FTI DRU": {"FTI": ("FTI", "inv")},
        "SLOW1": {"CDR": ("CDR1", "inv"), "ECMS_HUMS": ("HUMS", "inv")},
        "none": {},
        "ECMS1 + CDR1": {"ECMS_HUMS": ("ECMS1", "inv"), "CDR": ("CDR1", "inv")},
        "ECMS1 (features); raw only FTI/test cell": {"ECMS_HUMS": ("ECMS1", "inv")},
        "ECMS take-off record": {"ECMS_HUMS": ("ECMS-TO", "inv")},
        "DVR media": {"MPDRU": ("VIDEO", "inv")},
    }
    if t == "CDR4-8":
        pid = row["param_id"]
        fast = any(w in pid for w in _ATTITUDE_WORDS)
        return {"CDR": ("CDR8" if fast else "CDR4", "R-REC-CDR48")}
    if t not in table:
        raise SeedError(f"{row['param_id']}: unmapped rate_group_record {t!r}")
    return table[t]


def _allocate_icd(ctx: _Ctx, params: list[dict[str, Any]]) -> None:
    """Fill in 1553 SA/word/validity bits, ARINC-429 labels and FTI words (rules R-ICD-*)."""
    chans = {cid: ch for p in params for cid, ch in p["channels"].items()}
    items = []
    l429 = []
    fti = []
    for cid, ch in chans.items():
        t = ch["transport"]
        if t["type"] == "mil1553":
            group = ch["rates"]["bus"]
            items.append(
                icd.Mil1553Item(cid, t["bus"], t["rt"], t["tr"], group, ch["encoding"].get("words", 1))
            )
        elif t["type"] == "arinc429":
            l429.append((cid, t["link"], ch["rates"]["bus"]))
        elif t["type"] == "fti_pcm":
            fti.append((cid, t["stream"]))
    try:
        alloc = icd.allocate_mil1553(items)
        labels = icd.allocate_arinc429(l429)
        words = icd.allocate_fti(fti)
    except ValueError as exc:
        ctx.errors.append(str(exc))
        return
    for cid, a in alloc.items():
        t = chans[cid]["transport"]
        t.update({"sa": a["sa"], "word": a["word"], "words": a["words"], "message_words": a["message_words"]})
        chans[cid]["validity"] = {
            "method": "validity_word",
            "word": a["validity_word"],
            "bit": a["validity_bit"],
        }
    for cid, a in labels.items():
        chans[cid]["transport"].update(a)
    for cid, a in words.items():
        chans[cid]["transport"].update(a)


# ------------------------------------------------------------------------------------------------------------
# Output
# ------------------------------------------------------------------------------------------------------------
def render_sources(sources: Mapping[str, dict[str, Any]]) -> dict[str, str]:
    """{file name: YAML text} for the seeded sources (deterministic)."""
    header = (
        "# GENERATED by the M01 seeder from research_notes/.../parameter_inventory.csv and "
        "configs/<platform>/dictionary/seed/overlay.yaml.\n"
        "# Do not edit by hand: edit the overlay or the tables and re-run the seeder.\n"
        "# The bus mapping is the SYNTHETIC Phalanx ICD, not the real Tejas ICD.\n"
    )
    return {f"{stem}.yaml": header + dump_yaml(doc) for stem, doc in sorted(sources.items())}


def write_sources(sources: Mapping[str, dict[str, Any]], out_dir: str | Path) -> list[Path]:
    """Write the rendered sources into ``out_dir``; returns the written paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in render_sources(sources).items():
        p = out / name
        p.write_text(text, encoding="utf-8")
        written.append(p)
    return written
