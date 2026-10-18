"""Seeder: parameter_inventory.csv (189 rows x 33 fields) -> per-subsystem YAML sources (W0.3 A6).

Sample: the whole inventory (189 rows) - the acceptance criterion is coverage of every row, so nothing smaller
answers it. Negative tests use a one-row change in a temporary copy of the overlay or the inventory.
"""

from __future__ import annotations

import csv
import re
import shutil
from collections import Counter
from functools import lru_cache
from pathlib import Path

import pytest

from phalanx.dictionary import compile_bundle, load_bundle
from phalanx.dictionary.redact import REDACTION_PLACEHOLDER, split_fragments
from phalanx.dictionary.seeder import (
    SeedError,
    core_tag_for,
    read_inventory,
    render_sources,
    seed_sources,
)
from phalanx.dictionary.yamlio import dump_yaml, load_yaml

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"
INVENTORY = REPO / "research_notes" / "Virtual fighter telemetry layer research" / "parameter_inventory.csv"

# Physical channel count of the Tejas dictionary (unchanged from v0.1.0 to v0.1.2; reported to the
# coordinator). A change here is an ICD change.
EXPECTED_CHANNELS = 464
EXPECTED_BY_ROLE = {"lane": 108, "placeholder": 2, "single": 322, "voted": 32}


@lru_cache(maxsize=1)
def _seeded():
    return seed_sources(INVENTORY, CONFIG)


@lru_cache(maxsize=1)
def _content():
    return compile_bundle(load_bundle(CONFIG)).content


def test_inventory_shape():
    rows = read_inventory(INVENTORY)
    assert len(rows) == 189
    assert len(rows[0]) == 33
    assert len({r["param_id"] for r in rows}) == 189


# Inventory fields holding a restricted-manual value (report Appendix A1), found by scanning all 189 rows for
# restricted-source markers. The seeder redacts exactly these; a new one in a future inventory fails here.
EXPECTED_REDACTIONS = {
    ("ENG.T5", "notes_conflicts"),
    ("ENG.OIL_P", "notes_conflicts"),
    ("ENG.FUEL_INLET_T", "notes_conflicts"),
}
# independent of redact.RESTRICTED_MARKER on purpose: what the inventory uses to mark these fragments
_MARKED = re.compile(r"restricted|NATOPS|Hellenic", re.IGNORECASE)


def _carried_except_redactions(raw: str, seeded: str) -> bool:
    """``seeded`` equals ``raw`` except that whole restricted-marked fragments became the placeholder."""
    a, b = split_fragments(raw), split_fragments(seeded)
    if len(a) != len(b):
        return False
    for fa, fb in zip(a, b, strict=True):
        if fa == fb and not _MARKED.search(fa):
            continue
        if not (_MARKED.search(fa) and fb.strip() == REDACTION_PLACEHOLDER):
            return False
        if fa[: len(fa) - len(fa.lstrip())] + REDACTION_PLACEHOLDER + fa[len(fa.rstrip()) :] != fb:
            return False
    return True


def test_seeder_covers_all_189_inventory_rows():
    """All 33 fields of every row are carried verbatim, except the restricted-source fragments (Appendix A1),
    which are replaced whole by the placeholder - and nothing else differs."""
    rows = read_inventory(INVENTORY)
    seeded = {pid: p for doc in _seeded().values() for pid, p in doc["parameters"].items()}
    assert set(seeded) == {r["param_id"] for r in rows}
    redacted = set()
    for i, r in enumerate(rows, start=1):
        p = seeded[r["param_id"]]
        assert p["inventory"]["row"] == i
        fields = p["inventory"]["fields"]
        assert list(fields) == list(r)
        for k, raw in r.items():
            if fields[k] != raw:
                assert _carried_except_redactions(raw, fields[k]), (r["param_id"], k)
                redacted.add((r["param_id"], k))
            else:
                assert not _MARKED.search(raw), f"{r['param_id']}.{k}: restricted fragment carried verbatim"
        assert p["inventory"].get("redacted", []) == [k for k in r if (r["param_id"], k) in redacted]
        assert p["notes"] == (fields["notes_conflicts"] or None)
        assert p["evidence"]["tag"] == r["evidence_tag"] and p["evidence"]["source"] == r["source"]
        assert p["channels"], r["param_id"]
    assert redacted == EXPECTED_REDACTIONS


def test_seeder_redacts_a_planted_restricted_fragment(tmp_path):
    """Negative control: a restricted-source fragment planted in another row (fake value) never reaches the
    seeded source, while the row's other fragments are kept."""
    rows = read_inventory(INVENTORY)
    target = next(r for r in rows if r["param_id"] == "ENG.N1")
    planted = "planted Hellenic AF manual figure 123.4 degC"
    target["notes_conflicts"] = (
        target["notes_conflicts"] + "; " if target["notes_conflicts"] else ""
    ) + planted
    target["name"] = target["name"] + "; NATOPS 9876 psi band"
    inv = tmp_path / "parameter_inventory.csv"
    with inv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    seeded = {pid: p for doc in seed_sources(inv, CONFIG).values() for pid, p in doc["parameters"].items()}
    text = dump_yaml(seeded["ENG.N1"])
    for leak in ("123.4", "Hellenic", "9876", "NATOPS"):
        assert leak not in text, leak
    assert seeded["ENG.N1"]["inventory"]["redacted"] == ["name", "notes_conflicts"]
    assert seeded["ENG.N1"]["name"].endswith(REDACTION_PLACEHOLDER)


def test_physical_channel_count():
    """The reported physical channel count, and its breakdown (sensor lanes match the research-note
    estimate)."""
    c = _content()
    assert c["stats"]["channels"] == EXPECTED_CHANNELS
    assert c["stats"]["channels_by_role"] == EXPECTED_BY_ROLE
    lanes = Counter(ch["param_id"] for ch in c["channels"].values() if ch["role"] == "lane")
    # tejas_avionics_and_parameter_inventory.md Q4: 12 RSA, 8 ASA, 12 pilot-command, 16 ADC transducer, 12
    # vane
    # LVDT, ~20 primary-surface channels (the 8 T5 probes are averaged in 2 harnesses: rule R-T5-HARNESS).
    assert sum(lanes[p] for p in ("FCS.RSA.P", "FCS.RSA.Q", "FCS.RSA.R")) == 12
    assert sum(lanes[p] for p in ("FCS.ASA.NZ", "FCS.ASA.NY")) == 8
    assert sum(lanes[p] for p in ("FCS.STICK.PITCH", "FCS.STICK.ROLL", "FCS.PEDAL")) == 12
    assert sum(lanes[p] for p in ("AD.PS", "AD.PT", "AD.DPA", "AD.DPB")) == 16
    assert sum(lanes[p] for p in ("AD.AOA_VANE_L", "AD.AOA_VANE_R", "AD.AOSS_VANE")) == 12
    assert sum(v for p, v in lanes.items() if p.startswith(("FCS.ELEVON", "FCS.RUDDER"))) == 20


def test_committed_sources_are_seeder_output():
    """Seeded files are never hand-edited: re-seeding reproduces them byte for byte."""
    rendered = render_sources(_seeded())
    committed = {p.name: p.read_text(encoding="utf-8") for p in (CONFIG / "sources").glob("*.yaml")}
    seeded_files = {n for n, t in committed.items() if "generated_by: seeder" in t}
    assert seeded_files == set(rendered)
    for name, text in rendered.items():
        assert committed[name] == text, f"{name} is stale: re-run cli.py seed"


def test_seeding_is_deterministic():
    again = seed_sources(INVENTORY, CONFIG)
    assert render_sources(again) == render_sources(_seeded())


def test_proxy_placeholders_flagged():
    c = _content()
    for cid in ("FTI.ALL", "DVR.VIDEO"):
        ch = c["channels"][cid]
        assert ch["proxy"] and ch["role"] == "placeholder", cid
    assert all(not ch["proxy"] for cid, ch in c["channels"].items() if cid not in ("FTI.ALL", "DVR.VIDEO"))


def test_lanes_feed_their_voted_output():
    c = _content()
    for cid, ch in c["channels"].items():
        if ch["role"] == "voted":
            assert ch["inputs"] and all(c["channels"][i]["role"] == "lane" for i in ch["inputs"]), cid
            assert all(c["channels"][i]["measurand_id"] == ch["measurand_id"] for i in ch["inputs"]), cid
        if ch["role"] == "lane":
            assert [s["sink"] for s in ch["sinks"]] == ["INTERNAL"], cid
            assert ch["transport"]["type"] in ("internal", "rs422"), cid


@pytest.mark.parametrize(
    ("tag", "classes", "donor", "expected"),
    [
        ("DIRECT (Tejas)", ["DIRECT"], None, "DIRECT"),
        (
            "TRANSFER: F404-400 (sensors, limits); DIRECT: Tejas ECMS",
            ["TRANSFER", "DIRECT"],
            None,
            "TRANSFER: F404-400",
        ),
        (
            "TRANSFER (HARV, F/A-18C words) + DIRECT (uplock design)",
            ["TRANSFER", "DIRECT"],
            None,
            "TRANSFER: HARV, F/A-18C words",
        ),
        (
            "DIRECT (280 bar); sensor ASSUMPTION; TRANSFER HARV",
            ["DIRECT", "ASSUMPTION", "TRANSFER"],
            None,
            "ASSUMPTION",
        ),
        ("TRANSFER", ["TRANSFER"], "USN NAMP", "TRANSFER: USN NAMP"),
    ],
)
def test_core_tag_for(tag, classes, donor, expected):
    assert core_tag_for(tag, classes, donor) == expected


def test_bare_transfer_without_donor_fails():
    with pytest.raises(SeedError, match="names no donor"):
        core_tag_for("TRANSFER", ["TRANSFER"])


# ---- negatives: the seeder refuses values the inventory does not state -------------------------------------
def _overlay_copy(tmp_path: Path) -> tuple[Path, dict]:
    cfg = tmp_path / "dictionary"
    shutil.copytree(CONFIG, cfg)
    return cfg, load_yaml(cfg / "seed" / "overlay.yaml")


def test_overlay_value_not_in_inventory_fails(tmp_path):
    cfg, ov = _overlay_copy(tmp_path)
    ov["params"]["ENG.N1"]["range"] = [0, 120]  # inventory says 0-115 %
    (cfg / "seed" / "overlay.yaml").write_text(dump_yaml(ov), encoding="utf-8")
    with pytest.raises(SeedError, match="range value 120 is not written"):
        seed_sources(INVENTORY, cfg)


def test_lsb_rule_must_match_its_source(tmp_path):
    cfg, ov = _overlay_copy(tmp_path)
    ov["params"]["ENG.T1"]["lsb"] = {"v": 1.0, "p": "R-LSB-DASHLINK"}  # the row cites the MSDC, not DASHlink
    (cfg / "seed" / "overlay.yaml").write_text(dump_yaml(ov), encoding="utf-8")
    with pytest.raises(SeedError, match="R-LSB-DASHLINK cited but the row does not cite DASHlink"):
        seed_sources(INVENTORY, cfg)


def test_missing_overlay_row_fails(tmp_path):
    cfg, ov = _overlay_copy(tmp_path)
    del ov["params"]["MX.SOAP"]
    (cfg / "seed" / "overlay.yaml").write_text(dump_yaml(ov), encoding="utf-8")
    with pytest.raises(SeedError, match=r"missing \['MX\.SOAP'\]"):
        seed_sources(INVENTORY, cfg)


def test_orphan_row_fails(tmp_path):
    cfg, ov = _overlay_copy(tmp_path)
    ov["params"]["SYS.PHASE"].pop("sinks_fix")  # the inventory gives SYS.PHASE no sink
    (cfg / "seed" / "overlay.yaml").write_text(dump_yaml(ov), encoding="utf-8")
    with pytest.raises(SeedError, match="no sink"):
        seed_sources(INVENTORY, cfg)
