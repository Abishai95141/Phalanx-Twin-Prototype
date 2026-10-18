"""Spec -> human-readable Markdown summary of the contract (for owner review at the E0 freeze, and for
downstream teams). Deterministic: same spec -> same bytes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .model import FieldSpec, TopicSpec

if TYPE_CHECKING:
    from .model import Contract


def _esc(s: str) -> str:
    return " ".join(s.replace("|", "\\|").split())


def _type_label(f: FieldSpec) -> str:
    t = f.type
    if t.kind == "primitive" and t.name == "time_ns":
        return f"time_ns ({f.time_scale})"
    return t.render()


def _field_rows(fields: tuple[FieldSpec, ...], prefix: str = "") -> list[str]:
    rows = []
    for f in fields:
        flags = []
        if f.restricted:
            flags.append("**RESTRICTED**")
        if f.units:
            flags.append(f"units `{f.units}`")
        if f.pattern:
            flags.append(f"pattern `{f.pattern}`")
        if f.minimum is not None or f.maximum is not None:
            lo = "-inf" if f.minimum is None else f.minimum
            hi = "inf" if f.maximum is None else f.maximum
            flags.append(f"range [{lo}, {hi}]")
        extra = f" [{'; '.join(flags)}]" if flags else ""
        rows.append(
            f"| `{prefix}{f.name}` | `{_esc(_type_label(f))}` | {'yes' if f.nullable else 'no'} | "
            f"{_esc(f.description)}{_esc(extra)} | {_esc(f.basis)} |"
        )
        t = f.type
        if t.kind == "list" and t.item is not None and t.item.kind == "struct":
            rows.extend(_field_rows(t.item.fields, prefix=f"{prefix}{f.name}[]."))
        if t.kind == "struct":
            rows.extend(_field_rows(t.fields, prefix=f"{prefix}{f.name}."))
    return rows


def _partitioning(t: TopicSpec) -> str:
    return "/".join(("date", *t.partition_by))


def _topic_section(c: Contract, t: TopicSpec) -> list[str]:
    out = [f"### `{t.name}`{' (RESTRICTED)' if t.restricted else ''}", "", _esc(t.description), ""]
    out += [
        f"- **Basis:** {_esc(t.basis)}",
        f"- **Event time:** `{t.event_time}`; **ingest time:** `{t.ingest_time or 'none (not streamed)'}`",
        f"- **Partitioning:** `{_partitioning(t)}`",
        f"- **JSON-Schema:** {'yes' if t.json_schema else 'no'}; "
        f"**consumer-visible:** {'no' if t.restricted else 'yes'}",
        "- **record_id key:** " + ", ".join(f"`{k.name}` ({k.type}, {k.source})" for k in t.record_id_key),
    ]
    for k in t.record_id_key:
        if k.source == "path":
            out.append(f"  - `{k.name}`: {_esc(k.description)}")
    if t.checks:
        parts = []
        for ch in t.checks:
            if ch.check == "order":
                parts.append(f"`{ch.get('left')} {ch.get('op')} {ch.get('right')}` (where both non-null)")
            else:
                parts.append(
                    f"`{ch.get('field')}` required when `{ch.get('when_field')} == {ch.get('equals')}`"
                )
        out.append("- **Row invariants:** " + "; ".join(parts) + "; record_id unique per batch")
    out += ["", "| Field | Type | Null | Description | Basis |", "|---|---|---|---|---|"]
    out += _field_rows(t.fields)
    out.append("")
    return out


def _status_line(c: Contract) -> str:
    """Freeze state of this version (AD-41: the contract line was frozen by the owner at E0)."""
    rule = (
        "any change needs a semver bump, a migration note and a decision-register entry (architecture §12)."
    )
    if c.status == "frozen":
        return f"> Status: **frozen** by the owner (AD-41: a frozen version never changes); {rule}"
    return (
        f"> Status: **{c.status}**. An additive change to the frozen contract line (AD-41), binding once the "
        f"owner freezes it; frozen versions stay loadable by their exact semver. As for every version, {rule}"
    )


def render_markdown(c: Contract) -> str:
    lines = [
        f"# Phalanx ground-decoder contract {c.version} ({c.status.upper()})",
        "",
        "> Generated from `src/phalanx/dictionary/contract/spec/` by `phalanx.dictionary.contract.markdown`. "
        "Do not edit by hand.",
        _status_line(c),
        "",
        f"- **Contract:** `{c.name}` version `{c.version}`",
        f"- **Contract hash (blake2b-256 of the canonical spec):** `{c.hash}`",
        f"- **Schema hash (blake2b-256 of the generated Arrow schemas):** `{c.schema_hash}`",
        f"- **Topics:** {len(c.topics)}; **enumerations:** {len(c.enums)}; **flag sets:** {len(c.flag_sets)}",
        "",
        _esc(c.description),
        "",
        "## Conventions",
        "",
        f"- **Time** ({_esc(str(c.time.get('basis', '')))}): every time field is `{c.time['dtype']}` "
        f"`{c.time['unit']}`. Scales:",
    ]
    for k, v in c.time["scales"].items():
        lines.append(f"  - `{k}`: {_esc(v)}")
    rid = c.record_id_rules
    lines += [
        f"- **record_id** ({_esc(str(rid['basis']))}): {rid['algorithm']}, {rid['digest_bytes']} bytes, "
        f"person `{rid['person']}`. {_esc(rid['encoding'])} Representation: {_esc(rid['representation'])}",
        f"- **NaN:** {_esc(c.nan_policy)}",
        f"- **Restricted data:** {_esc(c.restriction_policy)}",
        "- **Nullability:** every field states it explicitly; a non-nullable field never holds null "
        "(validated, including nested list items and struct members).",
        "- **Evidence basis:** `ARCH §n` = mandated by the binding architecture; `TRANSFER: src` = taken "
        "from a public standard or donor practice; `ASSUMPTION: A-W0.4-n` = W0.4 choice, listed below for "
        "review.",
        "- **Formats (AD-13):** Arrow schemas are the source; Parquet on disk (partitioned by date / tail / "
        "sortie); Avro generated from Arrow for the v1.x Kafka adapter; manifests and orders also as JSON "
        "with JSON-Schema.",
        "",
        "## Topics",
        "",
        "| Topic | Event time | Ingest time | Partitioning | Visible to consumers | JSON-Schema |",
        "|---|---|---|---|---|---|",
    ]
    for name in c.topic_names:
        t = c.topics[name]
        lines.append(
            f"| `{name}` | `{t.event_time}` | `{t.ingest_time or '-'}` | `{_partitioning(t)}` | "
            f"{'no (restricted)' if t.restricted else 'yes'} | {'yes' if t.json_schema else 'no'} |"
        )
    lines += ["", "## Enumerations", ""]
    for e in c.enums.values():
        lines += [f"### `{e.name}`", "", f"{_esc(e.description)} *Basis:* {_esc(e.basis)}", ""]
        lines += ["| Symbol | Meaning |", "|---|---|"]
        lines += [f"| `{s.name}` | {_esc(s.description)} |" for s in e.symbols]
        lines.append("")
    lines += ["## Flag sets", ""]
    for fs in c.flag_sets.values():
        lines += [
            f"### `{fs.name}` (uint32 carrier, {fs.width} bits)",
            "",
            f"{_esc(fs.description)} *Basis:* {_esc(fs.basis)}",
            "",
            "| Bit | Mask | Flag | Scope | Meaning |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {f.bit} | `0x{1 << f.bit:08x}` | `{f.name}` | {f.scope} | {_esc(f.description)} |"
            for f in fs.flags
        ]
        lines += ["", f"Reserved mask (must be zero): `0x{fs.reserved_mask:08x}`", ""]
    lines += ["## Topic definitions", ""]
    for name in c.topic_names:
        lines += _topic_section(c, c.topics[name])
    lines += [
        "## Derived choices for owner review",
        "",
        "These are W0.4 decisions where no source decides. Each is registered in `docs/assumptions.md`.",
        "",
        "| ID | Statement |",
        "|---|---|",
    ]
    lines += [f"| {a.id} | {_esc(a.statement)} |" for a in c.assumptions]
    lines.append("")
    return "\n".join(lines)
