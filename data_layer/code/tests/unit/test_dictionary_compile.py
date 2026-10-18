"""M01 compiler: determinism, hashing, versioning and strict input handling (brief W0.3 A2).

Sample: the full Tejas dictionary (189 parameters, 464 channels) is the object under test; it is
configuration, not data, and compiling it takes < 1 s, so every test uses it whole. Negative tests mutate a
deep copy of the loaded bundle.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from phalanx.dictionary import (
    CompileError,
    DictionaryVersionError,
    compile_bundle,
    compile_dictionary,
    load_bundle,
    load_dictionary,
    read_compiled,
    write_compiled,
)
from phalanx.dictionary.yamlio import (
    DuplicateKeyError,
    blake2b_hex,
    canonical_json_bytes,
    load_yaml,
    load_yaml_text,
)

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"


@lru_cache(maxsize=1)
def _bundle():
    return load_bundle(CONFIG)


@lru_cache(maxsize=1)
def _compiled():
    return compile_bundle(_bundle().copy())


def _first_channel(bundle):
    src = bundle.sources["engine.yaml"]
    return src["parameters"]["ENG.N1"]["channels"]["ENG.N1.V"]


# ---- A2: hash stability ------------------------------------------------------------------------------------
@pytest.mark.determinism
def test_compile_twice_same_bytes_and_hash():
    a = compile_bundle(_bundle().copy())
    b = compile_dictionary(CONFIG)
    assert a.canonical == b.canonical
    assert a.dict_hash == b.dict_hash
    assert a.to_bytes() == b.to_bytes()


@pytest.mark.determinism
def test_hash_stable_in_fresh_processes():
    """Two fresh interpreters (-I: random str-hash seeds, no env) reproduce the in-process hash."""
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from phalanx.dictionary import compile_dictionary;"
        "print(compile_dictionary(sys.argv[2]).dict_hash)"
    )
    hashes = set()
    for _ in range(2):
        out = subprocess.run(
            [sys.executable, "-I", "-c", code, str(REPO / "src"), str(CONFIG)],
            capture_output=True,
            text=True,
            check=True,
        )
        hashes.add(out.stdout.strip())
    assert hashes == {_compiled().dict_hash}


def test_hash_is_blake2b_of_canonical_content():
    c = _compiled()
    assert c.dict_hash == blake2b_hex(canonical_json_bytes(c.content))
    assert len(c.dict_hash) == 64
    assert "dict_hash" not in c.content


_EDITS = st.sampled_from(["channel_name", "param_notes", "rule_statement", "lru_name", "release_date", "lsb"])


@settings(max_examples=12, deadline=None, derandomize=True, suppress_health_check=[HealthCheck.too_slow])
@given(edit=_EDITS, suffix=st.text(alphabet="abcxyz", min_size=1, max_size=3))
def test_any_source_edit_changes_the_hash(edit, suffix):
    b = _bundle().copy()
    if edit == "channel_name":
        ch = _first_channel(b)
        ch["name"] = ch["name"] + suffix
    elif edit == "param_notes":
        p = b.sources["engine.yaml"]["parameters"]["ENG.N1"]
        p["notes"] = (p["notes"] or "") + suffix
    elif edit == "rule_statement":
        r = b.tables["rules"]["rules"]["R-LSB-BNR"]
        r["statement"] += suffix
    elif edit == "lru_name":
        b.tables["lrus"]["lrus"]["FADEC"]["name"] += suffix
    elif edit == "release_date":
        b.manifest["release_date"] = "2026-10-1" + str(len(suffix))
    elif edit == "lsb":
        ch = _first_channel(b)  # an LSB that still fits the word, with the matching calibration gain
        ch["recorder_lsb"] = ch["calibration"]["coefficients"][1] = 0.03125 * 2 ** len(suffix)
    assert compile_bundle(b).dict_hash != _compiled().dict_hash


def test_inv_claims_are_checked_so_an_unsupported_edit_fails():
    """Editing a value that claims inventory provenance to a number the inventory does not state is
    rejected."""
    b = _bundle().copy()
    _first_channel(b)["range"]["max"] = 114  # inventory says 0-115 %
    with pytest.raises(CompileError, match="range value 114"):
        compile_bundle(b)


def test_key_order_in_sources_does_not_change_the_hash():
    b = _bundle().copy()
    params = b.sources["fire.yaml"]["parameters"]
    for pid in list(params):
        params[pid] = dict(reversed(list(params[pid].items())))
    b.sources = dict(reversed(list(b.sources.items())))
    assert compile_bundle(b).dict_hash == _compiled().dict_hash


# ---- versions and releases ---------------------------------------------------------------------------------
def test_current_version_is_released_with_this_hash():
    """A content change without a version bump and a releases.yaml entry fails here."""
    c = _compiled()
    releases = load_yaml(CONFIG / "releases.yaml")["releases"]
    assert c.dict_version in releases, f"record dictionary {c.dict_version} in releases.yaml"
    assert releases[c.dict_version]["dict_hash"] == c.dict_hash, (
        "sources changed: bump dict_version and release"
    )
    d = load_dictionary(c.dict_version)
    assert d.dict_hash == c.dict_hash


def test_wrong_version_is_rejected():
    with pytest.raises(DictionaryVersionError):
        load_dictionary("99.0.0")


def test_bad_semver_rejected_by_schema():
    b = _bundle().copy()
    b.manifest["dict_version"] = "0.1"
    with pytest.raises(CompileError, match="dict_version"):
        compile_bundle(b)


def test_write_read_round_trip(tmp_path):
    c = _compiled()
    path = write_compiled(c, tmp_path)
    assert path.name == f"dictionary.{c.dict_version}.json"
    back = read_compiled(path)
    assert back.dict_hash == c.dict_hash and back.content == c.content
    d = load_dictionary(path)
    assert d.dict_hash == c.dict_hash


def test_tampered_compiled_file_is_rejected(tmp_path):
    path = write_compiled(_compiled(), tmp_path)
    data = json.loads(path.read_bytes())
    data["channels"]["ENG.N1.V"]["recorder_lsb"] = 0.0625
    path.write_text(json.dumps(data))
    with pytest.raises(CompileError, match="does not match"):
        read_compiled(path)


# ---- strict inputs -----------------------------------------------------------------------------------------
def test_duplicate_yaml_keys_are_rejected():
    with pytest.raises(DuplicateKeyError, match="duplicate key 'x'"):
        load_yaml_text("a: 1\nb:\n  x: 1\n  x: 2\n")


def test_non_string_keys_are_rejected():
    b = _bundle().copy()
    b.tables["code_tables"]["tables"]["ssm_bnr"]["codes"] = {0: "FAILURE_WARNING"}
    with pytest.raises(CompileError, match="not a string"):
        compile_bundle(b)


def test_canonical_json_rejects_nan_and_normalises_negative_zero():
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json_bytes({"x": float("nan")})
    assert canonical_json_bytes({"a": -0.0, "b": [1, 2.5]}) == b'{"a":0.0,"b":[1,2.5]}'


def test_unknown_field_rejected_by_schema():
    b = _bundle().copy()
    _first_channel(b)["recorder_lbs"] = 1.0  # typo
    with pytest.raises(CompileError, match="recorder_lbs"):
        compile_bundle(b)


def test_synthetic_label_is_required():
    b = _bundle().copy()
    b.manifest["synthetic_label"] = "Phalanx ICD"
    with pytest.raises(CompileError, match="SYNTHETIC"):
        compile_bundle(b)
    b2 = _bundle().copy()
    b2.tables["buses"]["synthetic"] = False
    with pytest.raises(CompileError):
        compile_bundle(b2)


def test_code_tables_marked_synthetic():
    """Every Phalanx-invented code table says so (AD-19; RULES.md rule 6); standard tables do not."""
    tables = _compiled().content["code_tables"]
    synthetic = {k for k, t in tables.items() if t["synthetic"]}
    assert {
        "bit_code_format",
        "bit_codes",
        "cws_legends",
        "fcs_law",
        "gps_fix",
        "ins_mode",
        "store_station",
    } <= synthetic
    assert {"ssm_bnr", "ssm_dis", "mil1553_status_word", "flight_phase"}.isdisjoint(synthetic)
    # flight_phase mixes DASHlink codes 0-7 with synthetic fighter phases 8-15, which it lists (0.1.2, AD-49)
    fp = tables["flight_phase"]
    assert fp["synthetic_codes"] == [str(c) for c in range(8, 16)] and "R-CODES-SYNTHETIC" in fp["extra_prov"]
    assert "SYNTHETIC" in _compiled().content["synthetic_label"]


def test_dictionary_012_code_table_changes():
    """0.1.2 batch: 1553 validity bit -> BUS_INVALID (AD-45), FCS law GROUND (AD-47), fighter phases
    (AD-49)."""
    t = _compiled().content["code_tables"]
    assert t["mil1553_validity_bit"]["codes"] == {"0": "NORMAL", "1": "BUS_INVALID"}
    assert t["fcs_law"]["codes"]["3"] == "GROUND"
    names = [
        "ENGINE_START",
        "MISSION",
        "DESCENT",
        "PATTERN",
        "TOUCH_AND_GO",
        "SHUTDOWN",
        "GROUND_RUN",
        "HOT_REFUEL",
    ]
    assert [t["flight_phase"]["codes"][str(c)] for c in range(8, 16)] == names
    assert len(set(t["flight_phase"]["codes"].values())) == 16  # one code per name


def test_bundle_copy_is_deep():
    b = _bundle().copy()
    _first_channel(b)["name"] = "changed"
    assert _first_channel(_bundle())["name"] != "changed"
    assert copy.deepcopy(_bundle().manifest) == _bundle().manifest
