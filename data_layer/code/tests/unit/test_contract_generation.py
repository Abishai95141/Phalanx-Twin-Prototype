"""W0.4 A2: schema generation is deterministic, the contract hash is stable, and any spec edit changes it.

Also: the loader is strict (negative tests: each malformed spec is rejected), and the checked-in generated
artefacts never drift from the spec.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from phalanx.dictionary.contract import (
    ContractNotFound,
    ContractSpecError,
    load_contract,
    load_spec_dir,
)
from phalanx.dictionary.contract.loader import SPEC_ROOT

# Golden identity of contract 0.1.0. If this fails, the contract changed: after the E0 freeze that needs a
# semver bump, a migration note and a decision-register entry (architecture §12) before these constants are
# updated.
GOLDEN_VERSION = "0.1.0"
GOLDEN_HASH = "18d7627ba6f0f9b694c1978bd4c6cad65f62fea8fd4e8fcb537801c8cf57cc4e"
GOLDEN_SCHEMA_HASH = "5bd2b54c5e0fac10279d3a1fb81ba6ef27fbba401c63bb3dc86a38e43d3cbd31"


@pytest.fixture
def spec_copy(tmp_path) -> Path:
    dst = tmp_path / "v0"
    shutil.copytree(SPEC_ROOT / "v0", dst)
    return dst


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"edit anchor not found in {path.name}: {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


@pytest.mark.unit
@pytest.mark.determinism
def test_a2_generation_deterministic_in_process():
    a = load_spec_dir(SPEC_ROOT / "v0")
    b = load_spec_dir(SPEC_ROOT / "v0")
    assert a is not b
    assert a.hash == b.hash and a.schema_hash == b.schema_hash
    assert a.canonical_spec == b.canonical_spec
    for t in a.topic_names:
        assert a.schemas[t].equals(b.schemas[t], check_metadata=True)
        assert a.schemas[t].serialize().to_pybytes() == b.schemas[t].serialize().to_pybytes()
        assert a.avro_schema(t) == b.avro_schema(t)


@pytest.mark.unit
@pytest.mark.determinism
def test_a2_hash_stable_in_fresh_subprocess(repo_root):
    c = load_contract("v0")
    code = (
        "import sys, hashlib; sys.path.insert(0, sys.argv[1]);"
        "from phalanx.dictionary.contract import load_contract; c = load_contract('v0');"
        "b = b''.join(c.schemas[t].serialize().to_pybytes() for t in c.topic_names);"
        "print(c.hash, c.schema_hash, hashlib.blake2b(b).hexdigest())"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", code, str(repo_root / "src")], capture_output=True, text=True, check=True
    ).stdout.split()
    import hashlib

    h = hashlib.blake2b(b"".join(c.schemas[t].serialize().to_pybytes() for t in c.topic_names)).hexdigest()
    assert out == [c.hash, c.schema_hash, h]


@pytest.mark.unit
@pytest.mark.golden
def test_a2_golden_contract_identity():
    """0.1.0 is frozen and archived verbatim (spec/v0.1.0); it keeps its identity forever (AD-41)."""
    c = load_contract(GOLDEN_VERSION)
    assert c.version == GOLDEN_VERSION
    assert c.hash == GOLDEN_HASH, f"contract hash changed: {c.hash}"
    assert c.schema_hash == GOLDEN_SCHEMA_HASH, f"schema hash changed: {c.schema_hash}"


# Golden identity of the current minor version of the v0 line (W2.2: 0.2.0, additive; frozen, AD-56).
GOLDEN_CURRENT_VERSION = "0.2.0"
GOLDEN_CURRENT_HASH = "a4396f1d5482ce7816354ed7c9b040179d3c1467a7ca6e75b21fd71e1a904566"
GOLDEN_CURRENT_SCHEMA_HASH = "e8313f4817131f2e5f62babb74c96a495ca407e7306af0c5da3ad8cfde13e7b1"


@pytest.mark.unit
@pytest.mark.golden
def test_a2_golden_current_contract_identity():
    c = load_contract("v0")
    assert c.version == GOLDEN_CURRENT_VERSION
    assert c.hash == GOLDEN_CURRENT_HASH, f"contract hash changed: {c.hash}"
    assert c.schema_hash == GOLDEN_CURRENT_SCHEMA_HASH, f"schema hash changed: {c.schema_hash}"


@pytest.mark.unit
def test_a2_comment_and_whitespace_edits_keep_the_hash(spec_copy):
    base = load_spec_dir(spec_copy)
    f = spec_copy / "topics/param.samples.yaml"
    f.write_text("# an extra comment\n" + f.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    assert load_spec_dir(spec_copy).hash == base.hash


@pytest.mark.unit
@pytest.mark.parametrize(
    ("file", "old", "new", "schema_changes"),
    [
        # a description edit is a semantic edit of the contract text
        ("topics/param.samples.yaml", "Parameter-dictionary key (M01).", "Dictionary key.", True),
        # a nullability flip
        (
            "topics/param.samples.yaml",
            "  - name: raw_counts\n    type: int64\n    nullable: true",
            "  - name: raw_counts\n    type: int64\n    nullable: false",
            True,
        ),
        # an enum symbol rename
        ("contract.yaml", "{name: BUS_INVALID,", "{name: BUS_INVALID_X,", True),
        # an assumption statement (part of the spec, not of any schema)
        ("contract.yaml", "Avro mapping: int8/int16", "Avro mapping (edited): int8/int16", False),
    ],
)
def test_a2_spec_edit_changes_hash(spec_copy, file, old, new, schema_changes):
    base = load_spec_dir(spec_copy)
    _edit(spec_copy / file, old, new)
    edited = load_spec_dir(spec_copy)
    assert edited.hash != base.hash
    # schema metadata embeds the contract hash, so the schema hash always moves with it
    assert edited.schema_hash != base.schema_hash
    changed = any(
        not edited.schemas[t].remove_metadata().equals(base.schemas[t].remove_metadata())
        or any(ef.metadata != bf.metadata for ef, bf in zip(edited.schemas[t], base.schemas[t], strict=True))
        for t in base.topic_names
    )
    assert changed == schema_changes


@pytest.mark.unit
def test_a2_load_by_line_and_semver():
    """The line ``v0`` is its current minor version; every archived version loads by its exact semver."""
    assert load_contract("v0") is load_contract(GOLDEN_CURRENT_VERSION)
    assert load_contract("0.1.0") is not load_contract("v0") and load_contract("0.1.0").version == "0.1.0"
    with pytest.raises(ContractNotFound):
        load_contract("9.9.9")


BAD_EDITS = [
    (
        "duplicate YAML key",
        "topics/param.samples.yaml",
        "event_time: t_sample",
        "event_time: t_sample\nevent_time: t_sample",
    ),
    (
        "missing nullability",
        "topics/param.samples.yaml",
        "    type: int64\n    nullable: true\n",
        "    type: int64\n",
    ),
    ("unknown type", "topics/param.samples.yaml", "type: float64", "type: float32"),
    (
        "unknown key",
        "topics/param.samples.yaml",
        "json_schema: false",
        "json_schema: false\njson_schma: true",
    ),
    ("unregistered assumption", "topics/param.samples.yaml", "ASSUMPTION: A-W0.4-5", "ASSUMPTION: A-W0.4-99"),
    (
        "untagged basis",
        "topics/param.samples.yaml",
        'basis: "ARCH §12"\nrestricted',
        'basis: "because"\nrestricted',
    ),
    (
        "int before str in record_id_key",
        "topics/orders.status.yaml",
        "  - {name: order_id, type: str, source: column}\n  - {name: status_seq, type: u64, source: column}",
        "  - {name: status_seq, type: u64, source: column}\n  - {name: order_id, type: str, source: column}",
    ),
    (
        "event_time not a time field",
        "topics/param.samples.yaml",
        "event_time: t_sample",
        "event_time: value_eu",
    ),
    ("unknown enum", "topics/param.samples.yaml", "type: enum:Validity", "type: enum:Validty"),
    (
        "unanchored pattern",
        "topics/param.samples.yaml",
        'pattern: "^[A-Za-z0-9]+$"',
        'pattern: "[A-Za-z0-9]+"',
    ),
    (
        "path component without rule",
        "topics/orders.status.yaml",
        "  - {name: status_seq, type: u64, source: column}",
        "  - {name: status_seq2, type: u64, source: path}",
    ),
    ("duplicate flag bit", "contract.yaml", "{bit: 1, name: GATED", "{bit: 0, name: GATED"),
    ("bad semver", "contract.yaml", "version: 0.2.0", "version: 0.2"),
]


@pytest.mark.unit
@pytest.mark.parametrize(("why", "file", "old", "new"), BAD_EDITS, ids=[b[0] for b in BAD_EDITS])
def test_a2_malformed_spec_rejected(spec_copy, why, file, old, new):
    _edit(spec_copy / file, old, new)
    with pytest.raises(ContractSpecError):
        load_spec_dir(spec_copy)


@pytest.mark.unit
def test_generated_artefacts_match_the_spec():
    """The checked-in generated/ files equal a fresh generation (no silent drift)."""
    from phalanx.dictionary.contract.generate import GENERATED_ROOT, artefacts

    files = artefacts("v0")
    root = GENERATED_ROOT / "v0"
    on_disk = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    assert on_disk == set(files)
    for rel, text in files.items():
        assert (root / rel).read_text(encoding="utf-8") == text, f"{rel} drifted; run generate.py"


@pytest.mark.unit
def test_published_arrow_schemas_round_trip(repo_root):
    """The Arrow artefacts decode to exactly the contract schemas (full and consumer views, metadata
    included), the text dumps are untruncated, and docs/contract carries the same bytes."""
    from phalanx.dictionary.contract.generate import artefacts, read_arrow_schema

    c = load_contract("v0")
    files = artefacts("v0")
    published = repo_root / "docs/contract/contract/v0"
    for t in c.topic_names:
        full = read_arrow_schema(files[f"arrow/{t}.schema.b64"])
        assert full.equals(c.schemas[t], check_metadata=True)
        dump = files[f"arrow/{t}.schema.txt"]
        assert "omitted" not in dump and all(f"{name}:" in dump for name in c.schemas[t].names)
        if c.topics[t].restricted:
            assert f"arrow/{t}.consumer.schema.b64" not in files
        else:
            consumer = read_arrow_schema(files[f"arrow/{t}.consumer.schema.b64"])
            assert consumer.equals(c.consumer_schema(t), check_metadata=True)
        for rel in (f"arrow/{t}.schema.b64", f"arrow/{t}.schema.txt"):
            assert (published / rel).read_text(encoding="utf-8") == files[rel], f"docs/contract/{rel} drifted"
    assert artefacts("v0") == files  # deterministic


# Frozen contract versions (owner-approved, AD-41). A frozen version's hash can never change. Any spec change
# needs a semver bump, a new entry here, a migration note and a decision-register entry (RULES.md rule 6).
FROZEN_VERSIONS = {
    "0.1.0": "18d7627ba6f0f9b694c1978bd4c6cad65f62fea8fd4e8fcb537801c8cf57cc4e",
    "0.2.0": "a4396f1d5482ce7816354ed7c9b040179d3c1467a7ca6e75b21fd71e1a904566",  # AD-56 (owner freeze)
}


@pytest.mark.unit
def test_frozen_versions_are_immutable():
    """Every spec directory (the current line and the archived versions) is checked; every registered frozen
    version must still be present, frozen and unchanged (W2.2: 0.1.0 moved to spec/v0.1.0 verbatim)."""
    from phalanx.dictionary.contract.loader import available_versions

    seen = {}
    for dirname in available_versions():
        c = load_contract(dirname)
        assert c.status in ("draft", "frozen")
        seen[c.version] = c
        if c.status == "frozen":
            assert c.version in FROZEN_VERSIONS, (
                f"frozen contract {c.version} is not registered in FROZEN_VERSIONS"
            )
            assert c.hash == FROZEN_VERSIONS[c.version], (
                f"contract {c.version} is frozen; its content changed (hash {c.hash[:12]}...). "
                "Bump the version, add a migration note and a decision-register entry."
            )
    for version, h in FROZEN_VERSIONS.items():
        assert version in seen and seen[version].status == "frozen" and seen[version].hash == h, version
