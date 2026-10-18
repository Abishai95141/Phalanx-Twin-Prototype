"""W0.4 A1: every architecture §12 topic and field is present, with the right types and nullability.

The §12 tables are parsed straight from docs/architecture.md, so an architecture change that the contract does
not follow fails here. Types and nullability of the canonical sample record are pinned explicitly.
"""

from __future__ import annotations

import re

import pyarrow as pa
import pytest

from phalanx.dictionary.contract import load_contract

C = load_contract("v0")


def _section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


@pytest.fixture(scope="module")
def sec12(repo_root) -> str:
    text = (repo_root / "docs/architecture.md").read_text(encoding="utf-8")
    return _section(text, "## 12. Data contract", "## 13.")


def _first_col_ticks(block: str) -> list[str]:
    out = []
    for line in block.splitlines():
        if line.startswith("| `"):
            out += re.findall(r"`([^`]+)`", line.split("|")[1])
    return out


def _row_content(block: str, field: str) -> str:
    for line in block.splitlines():
        if line.startswith(f"| `{field}`"):
            return line.split("|")[2].strip()
    raise AssertionError(f"§12 row {field} not found")


@pytest.mark.unit
def test_a1_topics_match_architecture_section_12(sec12):
    topics_block = _section(sec12, "**Topics**", "**Canonical sample record:**")
    arch_topics = set(_first_col_ticks(topics_block))
    assert arch_topics == {
        "param.samples",
        "events.bit_faults",
        "events.exceedances",
        "events.cautions",
        "usage.counters",
        "sortie.manifest",
        "maint.records",
        "orders.commands",
        "orders.status",
        "labels.truth",
    }
    # §12 lists orders.commands since AD-38 (the §11.1 order record; report §13 names that topic)
    assert set(C.topics) == arch_topics
    assert C.topics["labels.truth"].restricted
    assert not any(C.topics[t].restricted for t in C.topics if t != "labels.truth")


@pytest.mark.unit
def test_a1_canonical_sample_record_fields_match_section_12(sec12):
    block = _section(sec12, "**Canonical sample record:**", "**Event record:**")
    arch_fields = set(_first_col_ticks(block))
    assert "t_true" not in arch_fields  # §12 lists t_true only in parentheses (CIR and labels only)
    assert "`t_true` only in CIR and labels" in block
    names = set(C.schemas["param.samples"].names)
    assert arch_fields <= names, arch_fields - names
    assert "t_true" not in names
    assert "t_true" in C.schemas["labels.truth"].names
    # nothing in param.samples beyond §12 (contract 0.2.0's recording_id and sink are in §12 since AD-56)
    assert names == arch_fields


# Pinned: name -> (arrow type, nullable). Order is the contract order.
PARAM_SAMPLES = [
    ("record_id", pa.binary(16), False),
    ("dict_version", pa.string(), False),
    ("dict_hash", pa.string(), False),
    ("param_id", pa.string(), False),
    ("tail_no", pa.string(), False),
    ("sortie_id", pa.string(), False),
    ("engine_serial", pa.string(), True),
    ("source_lru", pa.string(), False),
    ("lane", pa.string(), True),
    ("bus", pa.string(), True),
    ("rt_sa_word", pa.string(), True),
    ("label_sdi", pa.string(), True),
    ("t_sample", pa.int64(), False),
    ("t_bus", pa.int64(), True),
    ("t_record", pa.int64(), True),
    ("t_utc", pa.int64(), True),
    ("t_ingest", pa.int64(), False),
    ("value_eu", pa.float64(), False),
    ("raw_counts", pa.int64(), True),
    ("units", pa.string(), False),
    ("validity", pa.string(), False),
    ("quality_flags", pa.uint32(), False),
    ("provenance", pa.string(), False),
    # contract 0.2.0 (W2.2, additive, A-W0.4-22): appended after the 0.1.0 fields
    ("recording_id", pa.string(), True),
    ("sink", pa.string(), True),
]


@pytest.mark.unit
def test_a1_param_samples_types_and_nullability():
    s = C.schemas["param.samples"]
    got = [(f.name, f.type, f.nullable) for f in s]
    assert [g[0] for g in got] == [p[0] for p in PARAM_SAMPLES]
    for (name, t, nl), (_, gt, gnl) in zip(PARAM_SAMPLES, got, strict=True):
        assert gt.equals(t), (name, gt, t)
        assert gnl == nl, name
    md = s.field("validity").metadata
    assert md[b"phalanx.enum"] == b"Validity"
    assert s.field("quality_flags").metadata[b"phalanx.flags"] == b"QualityFlags"
    assert s.metadata[b"phalanx.event_time"] == b"t_sample"
    assert s.metadata[b"phalanx.ingest_time"] == b"t_ingest"


@pytest.mark.unit
def test_a1_validity_enum_matches_section_12(sec12):
    block = _section(sec12, "**Canonical sample record:**", "**Event record:**")
    symbols = [s.strip() for s in _row_content(block, "validity").split(",")]
    assert C.enums["Validity"].names == tuple(symbols)
    assert C.enums["Provenance"].names == ("full_path", "direct")


GOLDEN_QUALITY_BITS = {
    "SENTINEL": 0,
    "GATED": 1,
    "HELD_STALE": 2,
    "DUPLICATE_POLL": 3,
    "SUBSTITUTED": 4,
    "VOTED_OUT": 5,
    "OUT_OF_RANGE": 6,
    "CLOCK_SUSPECT": 7,
    "TIME_SOURCE_INTERNAL": 8,
    "DUPLICATE_DOWNLOAD": 9,
    "DECODER_INTERPOLATED": 10,
}


@pytest.mark.unit
def test_a1_quality_flags_match_section_12_with_stable_bits(sec12):
    block = _section(sec12, "**Canonical sample record:**", "**Event record:**")
    names = [s.strip() for s in _row_content(block, "quality_flags").split(",")]
    qf = C.quality_flags
    assert [f.name for f in qf.flags] == names  # §12 order == bit order
    assert {f.name: f.bit for f in qf.flags} == GOLDEN_QUALITY_BITS  # stable bit positions (pinned)
    assert qf.width == 32 and qf.reserved_mask == 0xFFFFF800
    assert qf.mask("SENTINEL", "DECODER_INTERPOLATED") == 0b100_0000_0001


@pytest.mark.unit
def test_a1_time_fields_are_int64_ns_everywhere():
    for topic, s in C.schemas.items():
        for f in C.topics[topic].fields:
            if f.name.startswith("t_") or f.name.endswith(("_t_start", "_t_end")):
                af = s.field(f.name)
                assert af.type == pa.int64(), (topic, f.name)
                assert af.metadata[b"phalanx.time_unit"] == b"ns", (topic, f.name)
                assert af.metadata[b"phalanx.time_scale"] in (b"sim_utc", b"recorder_rtc", b"duration")
        # t_true only in labels (CIR is not a contract topic)
        assert ("t_true" in s.names) == (topic == "labels.truth")


@pytest.mark.unit
def test_a1_event_record_fields_match_section_12(sec12):
    block = _section(sec12, "**Event record:**", "**Formats (AD-13):**")
    assert "PBIT/CBIT/MBIT/IBIT/exceedance/pilot" in block
    assert C.enums["DetectionMechanism"].names == ("PBIT", "CBIT", "MBIT", "IBIT", "EXCEEDANCE", "PILOT")
    assert C.enums["FaultList"].names == ("PFL", "MFL")
    suspect = pa.list_(
        pa.field(
            "element",
            pa.struct(
                [
                    pa.field("lru", pa.string(), nullable=False),
                    pa.field("isolation_confidence", pa.float64(), nullable=False),
                ]
            ),
            nullable=False,
        )
    )
    required = {
        # S5000F Event: id, occurrence time, group, severity, description, confirmed status
        "event_id": (pa.string(), False),
        "t_occurrence": (pa.int64(), False),
        "event_group": (pa.string(), False),
        "severity": (pa.string(), False),
        "description": (pa.string(), True),
        "confirmed_status": (pa.string(), False),
        # DetectionMechanism with its false-alarm rate
        "detection_mechanism": (pa.string(), False),
        "detection_far_per_fh": (pa.float64(), True),
        # PFL/MFL level, latch state, persistence count
        "fault_list": (pa.string(), True),
        "latched": (pa.bool_(), False),
        "persistence_count": (pa.uint32(), True),
        # suspect-LRU list with isolation confidence
        "suspect_lrus": (suspect, False),
        # snapshot window pointer
        "snapshot_t_start": (pa.int64(), True),
        "snapshot_t_end": (pa.int64(), True),
        # dictionary on every record, linkage, ingest
        "dict_hash": (pa.string(), False),
        "tail_no": (pa.string(), False),
        "t_ingest": (pa.int64(), False),
    }
    for topic in ("events.bit_faults", "events.exceedances", "events.cautions"):
        s = C.schemas[topic]
        for name, (t, nl) in required.items():
            assert s.field(name).type.equals(t), (topic, name, s.field(name).type)
            assert s.field(name).nullable == nl, (topic, name)


@pytest.mark.unit
def test_a1_order_record_and_status_match_section_11_1(repo_root):
    text = (repo_root / "docs/architecture.md").read_text(encoding="utf-8")
    sec = _section(text, "### 11.1 Orders (M21)", "### 11.2")
    s = C.schemas["orders.commands"]
    for name in (
        "order_id",
        "issuer_id",
        "issuer_kind",
        "policy_version",
        "t_issued",
        "t_effective",
        "action",
    ):
        assert name in s.names
    for name in (
        "target_tail_no",
        "target_base",
        "target_lru",
        "target_serial",
    ):  # target (tail, base, LRU, serial)
        assert name in s.names
    assert s.field("parameters").metadata[b"phalanx.format"] == b"json_object"
    assert s.field("evidence").type.equals(pa.list_(pa.field("element", pa.binary(16), nullable=False)))
    # every action bullet of §11.1 is covered
    vocab = _section(sec, "- **Action vocabulary:**", "- **Semantics:**")
    bullets = [b for b in vocab.splitlines() if b.strip().startswith("- ")][1:]
    assert len(bullets) == 14
    assert len(C.enums["OrderAction"].names) == 18  # 4 bullets name two actions ("ground or release", ...)
    # status lifecycle "accepted, queued, in work, completed, rejected"
    assert "accepted, queued, in work, completed, rejected" in sec
    assert C.enums["OrderStatus"].names == ("ACCEPTED", "QUEUED", "IN_WORK", "COMPLETED", "REJECTED")
    assert "reason" in C.schemas["orders.status"].names


@pytest.mark.unit
def test_a1_maint_records_cover_section_10(repo_root):
    text = (repo_root / "docs/architecture.md").read_text(encoding="utf-8")
    sec = _section(text, "**Record architecture.**", "**Linkage keys:**")
    rows = [ln for ln in sec.splitlines() if ln.startswith("| ") and not ln.startswith(("| Record", "|---"))]
    assert len(rows) == len(C.enums["MaintRecordType"].names) == 11
    s = C.schemas["maint.records"]
    # linkage keys: tail; sortie ID; job number; component triplet; demand number; engine serial;
    # sw_config_id;
    # telemetry record_id
    for name in (
        "tail_no",
        "sortie_id",
        "job_no",
        "part_no",
        "serial_no",
        "maker",
        "demand_no",
        "engine_serial",
    ):
        assert name in s.names
    assert "sw_config_id" in s.names and "evidence_record_ids" in s.names


@pytest.mark.unit
def test_a1_manifest_usage_and_labels():
    m = C.schemas["sortie.manifest"]
    for name in ("tail_no", "engine_serials", "lru_serials", "sw_config_id", "mission_type", "dict_version"):
        assert name in m.names
    for name in ("root_seed", "code_commit", "rng_stream_table"):
        assert name in m.names
    # seeds are restricted: absent from the consumer view (I5), present in the full view
    cm = C.consumer_schema("sortie.manifest")
    assert "root_seed" not in cm.names and "rng_stream_table" not in cm.names
    assert "code_commit" in cm.names
    u = C.schemas["usage.counters"]
    for name in ("param_id", "value_eu", "units", "t_update", "t_ingest", "engine_serial"):
        assert name in u.names
    with pytest.raises(PermissionError):
        C.consumer_schema("labels.truth")


@pytest.mark.unit
def test_a1_every_field_documented_and_tagged():
    for t in C.topics.values():
        for f in t.fields:
            assert f.description and f.basis, (t.name, f.name)
            md = C.schemas[t.name].field(f.name).metadata
            assert md[b"phalanx.basis"] and md[b"phalanx.description"]


@pytest.mark.unit
def test_a1_spec_assumptions_registered_in_assumptions_md(repo_root):
    text = (repo_root / "docs/assumptions.md").read_text(encoding="utf-8")
    w04 = _section(text, "## W0.4", "## W0.5")
    registered = set(re.findall(r"^\| (A-W0\.4-\d+) \|", w04, flags=re.M))
    spec_ids = {a.id for a in C.assumptions}
    assert spec_ids <= registered, sorted(spec_ids - registered)
