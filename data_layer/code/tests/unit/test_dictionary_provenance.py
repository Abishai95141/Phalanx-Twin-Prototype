"""M01 provenance: 100 % evidence tags and sources, verified 'inv' claims, the assumption registry (W0.3 A1,
A7).

Sample: the full Tejas dictionary (189 parameters, 464 channels, 8,699 valued fields); negative tests mutate
one field of a deep copy (one is enough to show the check fires).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

from phalanx.core.module import EvidenceTag
from phalanx.dictionary import CompileError, compile_bundle, load_bundle
from phalanx.dictionary.generators import assumptions_markdown
from phalanx.dictionary.schema import PROV_FIELDS, rule_is_proxy, rule_needs_register
from phalanx.dictionary.textcheck import FIELD_COLUMNS

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"
ASSUMPTIONS_MD = REPO / "docs" / "assumptions.md"


@lru_cache(maxsize=1)
def _bundle():
    return load_bundle(CONFIG)


@lru_cache(maxsize=1)
def _content():
    return compile_bundle(_bundle().copy()).content


def _param(b, sub="engine.yaml", pid="ENG.N1"):
    return b.sources[sub]["parameters"][pid]


# ---- A1: 100 % coverage
# ----------------------------------------------------------------------------------------------
def test_every_parameter_has_tag_and_source():
    for pid, p in _content()["parameters"].items():
        ev = p["evidence"]
        assert ev["tag"].strip() and ev["source"].strip(), pid
        assert ev["classes"], pid


def test_provenance_coverage_is_100_percent():
    stats = _content()["stats"]
    assert stats["provenance_valued_fields"] > 8000
    assert stats["provenance_covered_fields"] == stats["provenance_valued_fields"]
    assert stats["provenance_coverage_pct"] == 100.0


def test_every_valued_field_has_a_resolvable_ref():
    """Independent of the compiler: walk every channel and resolve every ref to an evidence tag + source."""
    c = _content()
    n = 0
    for cid, ch in c["channels"].items():
        param = c["parameters"][ch["param_id"]]
        for f in PROV_FIELDS:
            top, _, sub = f.partition(".")
            value = ch[top].get(sub) if sub else ch.get(f)
            if value is None:
                continue
            ref = ch["prov"][f]
            n += 1
            if ref == "inv":
                assert param["inventory"] is not None, cid
                tag, source = param["evidence"]["core_tag"], param["evidence"]["source"]
            else:
                tag, source = c["rules"][ref]["tag"], c["rules"][ref]["source"]
            EvidenceTag.parse(tag)
            assert source.strip(), (cid, f)
        for s in ch["sinks"]:
            for ref in (s["prov"], s["group_prov"]):
                n += 1
                assert ref == "inv" or ref in c["rules"], (cid, s)
        for lim in ch["limits"]:
            n += 1
            assert lim["prov"] == "inv" or lim["prov"] in c["rules"], (cid, lim)
    assert n == c["stats"]["provenance_valued_fields"]  # independent count agrees with the compiler's


def test_all_tags_parse_with_core_evidence_tag():
    """Coordinator requirement: W1 builds ParamSets from dictionary entries, so every tag must parse."""
    c = _content()
    tags = [p["evidence"]["core_tag"] for p in c["parameters"].values()]
    tags += [v["evidence"]["tag"] for table in ("lrus", "sinks") for v in c[table].values()]
    tags += [r["tag"] for r in c["rules"].values()]
    tags += [v["evidence"]["tag"] for entries in c["constants"].values() for v in entries.values()]
    kinds = {EvidenceTag.parse(t).kind for t in tags}  # raises ContractError on any unparsable tag
    assert kinds <= {"DIRECT", "TRANSFER", "MEASURED", "ASSUMPTION"}
    assert len(tags) > 250


def test_core_tag_is_the_weakest_class_of_the_inventory_tag():
    order = ("DIRECT", "DIRECT-unnamed", "DIRECT-part", "MEASURED", "TRANSFER", "ASSUMPTION")
    for pid, p in _content()["parameters"].items():
        ev = p["evidence"]
        weakest = max(ev["classes"], key=order.index)
        assert EvidenceTag.parse(ev["core_tag"]).kind == weakest.split("-")[0], pid


# ---- A1 negatives ------------------------------------------------------------------------------------------
def test_missing_parameter_tag_fails():
    b = _bundle().copy()
    _param(b)["evidence"]["tag"] = ""
    with pytest.raises(CompileError):
        compile_bundle(b)


def test_missing_parameter_source_fails():
    b = _bundle().copy()
    _param(b)["evidence"]["source"] = " "
    with pytest.raises(CompileError, match="evidence tag and a source"):
        compile_bundle(b)


def test_unparsable_core_tag_fails():
    b = _bundle().copy()
    _param(b)["evidence"]["core_tag"] = "TRANSFER"  # no donor
    with pytest.raises(CompileError, match="core_tag"):
        compile_bundle(b)


def test_missing_field_provenance_fails():
    b = _bundle().copy()
    del _param(b)["channels"]["ENG.N1.V"]["prov"]["recorder_lsb"]
    with pytest.raises(CompileError, match="'recorder_lsb' has no provenance"):
        compile_bundle(b)


def test_unknown_rule_ref_fails():
    b = _bundle().copy()
    _param(b)["channels"]["ENG.N1.V"]["prov"]["range"] = "R-NOT-A-RULE"
    with pytest.raises(CompileError, match="unknown rule R-NOT-A-RULE"):
        compile_bundle(b)


def test_inv_claim_not_in_inventory_text_fails():
    b = _bundle().copy()
    ch = _param(b)["channels"]["ENG.N1.V"]
    ch["units"] = "rpm"
    ch["quantity"] = "rotational_speed"
    # an rpm channel takes no %N1 reference speed (validate._eu_reference_errors rejects one on it)
    b.tables["constants"]["sets"]["channel_reference"]["n1_100pct"]["eu_reference_for"] = ["ENG.N2"]
    b.tables["constants"]["sets"]["channel_reference"]["n2_100pct"].pop("eu_reference_for")
    ch["prov"]["units"] = "inv"  # 'rpm' is written in the row, so this is accepted ...
    compile_bundle(b)
    ch["native_step"] = 0.07  # ... but 0.07 is not written in native_resolution
    ch["prov"]["native_step"] = "inv"
    with pytest.raises(CompileError, match=r"native_step 0\.07 claimed from the inventory"):
        compile_bundle(b)


def test_inv_claim_on_assumption_marked_field_fails():
    b = _bundle().copy()
    ch = b.sources["engine.yaml"]["parameters"]["ENG.OIL_P"]["channels"]["ENG.OIL_P"]
    assert ch["prov"]["range"] == "R-INV-FIELD-ASSUMPTION"
    ch["prov"]["range"] = "inv"  # inventory range '0-200 [ASSUMPTION]'
    with pytest.raises(CompileError, match=r"marks it \[ASSUMPTION\]"):
        compile_bundle(b)


def test_inv_fields_marked_assumption_are_tagged():
    """No channel claims 'inv' for a value whose inventory column is marked [ASSUMPTION]."""
    c = _content()
    checked = 0
    for cid, ch in c["channels"].items():
        inv = c["parameters"][ch["param_id"]]["inventory"]["fields"]
        for f, ref in ch["prov"].items():
            if f in FIELD_COLUMNS and any("ASSUMPTION" in inv[col] for col in FIELD_COLUMNS[f]):
                checked += 1
                assert ref != "inv", (cid, f)
        if "ASSUMPTION" in inv["rate_group_record"] + inv["recorder_rate_hz"]:
            assert all(s["group_prov"] != "inv" for s in ch["sinks"]), cid
    assert checked > 100


def test_assumed_sinks_are_not_claimed_as_evidenced():
    c = _content()
    cols = {
        "COCKPIT": "sink_cockpit",
        "CDR": "sink_crash_recorder",
        "ECMS_HUMS": "sink_ecms_hums",
        "MPDRU": "sink_mpdru_maint_download",
        "FTI": "sink_fti_only",
    }
    for cid, ch in c["channels"].items():
        inv = c["parameters"][ch["param_id"]]["inventory"]["fields"]
        for s in ch["sinks"]:
            if s["sink"] in cols and s["prov"] in ("inv", "R-SINK-ASSUMED"):
                flag = inv[cols[s["sink"]]].strip()[:1]
                assert (s["basis"], flag) in (("evidenced", "Y"), ("assumed", "A")), (cid, s)


# ---- A7: assumption and PROXY registry ---------------------------------------------------------------------
def _w03_section() -> str:
    text = ASSUMPTIONS_MD.read_text(encoding="utf-8")
    start = text.index("## W0.3 Dictionary (M01)")
    end = text.index("\n## ", start + 10)
    return text[start:end]


def test_assumption_rules_registered():
    """docs/assumptions.md (W0.3 section) holds exactly the generated per-rule rows (IDs, affected params)."""
    section = _w03_section()
    rows = [line for line in section.splitlines() if line.startswith("| A-W0.3-")]
    expected = [
        line for line in assumptions_markdown(_content()).splitlines() if line.startswith("| A-W0.3-")
    ]
    assert rows == expected, (
        "regenerate with: python -I src/phalanx/dictionary/cli.py assumptions --config ..."
    )


def test_every_assumption_or_proxy_rule_in_use_has_a_row():
    c = _content()
    ids = set(re.findall(r"\| (A-W0\.3-\d+) \|", _w03_section()))
    used = {r for ch in c["channels"].values() for r in ch["prov"].values()} | {
        s["prov"] for ch in c["channels"].values() for s in ch["sinks"]
    }
    for rid, r in c["rules"].items():
        if rule_needs_register(r):
            assert r["assumption_id"] in ids, rid
            if rid in used:
                assert r["affects_params"], rid


def test_proxy_flag_matches_proxy_rules():
    c = _content()
    proxies = {rid for rid, r in c["rules"].items() if rule_is_proxy(r)}
    assert proxies == {"P-FTI-ALL", "P-DVR"}
    for cid, ch in c["channels"].items():
        cites = (
            set(ch["prov"].values())
            | {s["prov"] for s in ch["sinks"]}
            | {s["group_prov"] for s in ch["sinks"]}
        )
        assert ch["proxy"] == bool(cites & proxies), cid
    assert set(c["proxy_items"]) == {"FTI.ALL", "DVR.VIDEO"}


def test_proxy_flag_mismatch_fails():
    b = _bundle().copy()
    _param(b)["channels"]["ENG.N1.V"]["proxy"] = True
    with pytest.raises(CompileError, match="proxy flag"):
        compile_bundle(b)


def test_assumption_rule_without_registry_row_fails():
    b = _bundle().copy()
    del b.tables["rules"]["rules"]["R-LSB-BNR"]["assumption_id"]
    with pytest.raises(CompileError, match="without an assumption_id"):
        compile_bundle(b)


def test_proxy_rule_must_be_flagged():
    b = _bundle().copy()
    b.tables["rules"]["rules"]["P-DVR"]["proxy"] = False
    with pytest.raises(CompileError, match="P- rules"):
        compile_bundle(b)
