"""The fault catalogue as data covers both research catalogues (faults_and_degradation §9(b): 38 rows;
texture_and_fault_gap_closure synthesis (c): 41 rows), references only existing hidden states, graph nodes,
parameters and M14 codes, and applies faults only as physical state perturbations (no observation targets)."""

from __future__ import annotations

import csv

import pytest

from phalanx.dictionary import load_dictionary
from phalanx.faults import load_catalogue, load_fault_params, load_graph
from phalanx.faults.catalogue import CatalogueError, parse_catalogue
from phalanx.monitoring import load_code_table, load_monitoring_params

CAT = load_catalogue()


@pytest.mark.unit
def test_catalogue_covers_both_research_catalogues():
    refs = {r for m in CAT.values() for r in m.refs}
    want = {f"FD#{i}" for i in range(1, 39)} | {f"TFG#{i}" for i in range(1, 42)}
    assert want - refs == set()
    assert refs - want == set()  # no reference to a row that does not exist


@pytest.mark.unit
def test_references_resolve(repo_root):
    with open(
        repo_root / "research_notes/Virtual fighter telemetry layer research/not_measured_states.csv",
        encoding="utf-8",
    ) as fh:
        nm = {r["state_id"] for r in csv.DictReader(fh)}
    g = load_graph()
    params = load_fault_params()
    codes = load_code_table(load_dictionary(), load_monitoring_params()).by_code
    for m in CAT.values():
        if m.nm_ref:
            assert m.nm_ref in nm, m.id
        if m.graph_root:
            assert m.graph_root in g.nodes, m.id
        for c in m.codes:
            assert c in codes, (m.id, c)
        for k in ("rate", "scale", "probability", "p_on", "p_off"):
            v = m.onset.get(k)
            if isinstance(v, str):
                assert v in params, (m.id, v)
        for e in m.effects:
            if e.target == "monitoring" and not str(e.fields["code"]).endswith("*"):
                assert e.fields["code"] in codes, (m.id, e.fields["code"])
    for node in g.nodes.values():
        for e in node.effects:
            if e["target"] == "monitoring":
                assert e["code"] in codes, (node.id, e["code"])


@pytest.mark.unit
def test_faults_are_state_perturbations_only():
    """I6: every effect targets a state owner (health, sensors, LRU conditions, physics modules); no mode
    writes an observation, a code or a contract record directly. Gradual mechanisms are left to M10."""
    for m in CAT.values():
        if m.cls in ("degradation", "physics"):
            assert not m.effects and not m.injectable, m.id
        else:
            assert m.injectable, m.id
            assert m.effects or m.graph_root, m.id
        for e in m.effects:
            assert e.target in (
                "health",
                "sensors",
                "monitoring",
                "engine",
                "fadec",
                "utilities",
                "fcs",
                "airframe",
            )
            assert "record" not in e.fields and "event_code" not in e.fields


@pytest.mark.unit
def test_tejas_specific_events_present():
    """Architecture §9.2: JFS cold start failure, gauging artefact, brake-software defect -> tyre burst, FCS
    channel dropout."""
    for mid in (
        "FM.SPS.JFS_COLD_START_FAIL",
        "FM.FUEL.GAUGING_ARTEFACT",
        "FM.LG.BRAKE_SW_CONFIG",
        "FM.FCS.CHANNEL_DROPOUT",
    ):
        assert mid in CAT


@pytest.mark.unit
def test_bad_modes_are_rejected():
    base = {
        "name": "x",
        "subsystem": "engine",
        "class": "shock",
        "onset": {"process": "scripted"},
        "evidence": {"tag": "ASSUMPTION", "source": "test"},
        "effects": [{"target": "health", "state": "eng:extra_fan_eta", "delta": -0.01}],
        "validation": {"status": "unvalidated", "reason": "unvalidated (AD-55): test"},
    }
    fmt = "phalanx.fault_catalogue/2"
    assert parse_catalogue({"format": fmt, "modes": {"FM.X": base}})
    for mutate in (
        {"class": "magic"},
        {"onset": {"process": "whenever"}},
        {"effects": [{"target": "contract", "record": 1}]},
        {"effects": [{"target": "sensors", "channel": "ENG.T5", "mode": "explode"}]},
        {"evidence": {"tag": "DIRECT: B-2", "source": "x"}},
        {"class": "shock", "onset": {"process": "m10"}},
        {"validation": {"status": "validated"}},
        {"validation": {"status": "validated", "checks": ["C26"], "evidence": "x"}},
        {"validation": {"status": "validated", "checks": ["B7-X"], "evidence": " "}},
        {"validation": {"status": "unvalidated", "reason": "not in the set"}},
        {"validation": {"status": "maybe", "reason": "unvalidated (AD-55): x"}},
    ):
        with pytest.raises(CatalogueError):
            parse_catalogue({"format": fmt, "modes": {"FM.X": {**base, **mutate}}})
    no_status = {k: v for k, v in base.items() if k != "validation"}
    with pytest.raises(CatalogueError):
        parse_catalogue({"format": fmt, "modes": {"FM.X": no_status}})
    with pytest.raises(CatalogueError):
        parse_catalogue({"format": "phalanx.fault_catalogue/1", "modes": {"FM.X": base}})
