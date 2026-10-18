"""Readiness cards, twin lenses and workbench test orders (SHAPES.md: PHX_DATA.fleet[].card, PHX_TWIN, PHX_WB),
and the component registry they rest on.

    python -m pytest proto/tests/test_triage_twin.py -q
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys
from pathlib import Path

import pytest
import yaml

PROTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROTO / "ground"))

import triage
from interfaces import NS, SOURCE_LABEL
from store import Store
from twin import Twin
from twinview import registry

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
T = int(dt.datetime(2026, 6, 22, 6, 0, tzinfo=IST).timestamp()) * NS
LENSES = ["status", "evidence", "false_alarm", "life", "removal_risk", "engine_margin"]


@pytest.fixture(scope="module")
def world():
    store = Store.for_preview()
    return store, Twin(store)


def test_registry_matches_the_screens_and_the_catalogue():
    reg = registry()
    js = (PROTO / "web" / "assets" / "twin3d.js").read_text()
    comps = set(re.findall(r"^\s{2}([A-Z][A-Z0-9_]+):\s*\{ label", js, re.MULTILINE))
    zones = set(re.findall(r"^\s{4}([A-Z][A-Z0-9_]+):\s*\{ x:", (PROTO / "web" / "assets" / "aircraft.js").read_text(), re.MULTILINE))
    assert set(reg.nodes) <= comps
    assert {v["zone"] for v in reg.nodes.values() if v["zone"]} <= zones
    cat = Path(os.environ.get("PHX_DATALAYER_CODE", "/Users/abishaikc/Downloads/phalanx_data_layer_preview/code"))
    cat = cat / "configs" / "tejas" / "params" / "M18" / "catalogue.yaml"
    if not cat.exists():
        pytest.skip("data-layer catalogue not present")
    want = {(c["part_no"], k + 1, p) for c in yaml.safe_load(cat.read_text())["classes"].values() for k, p in enumerate(c["positions"])}
    mine = {(p["part_no"], p["slot"], p["position"]) for v in (*reg.nodes.values(), *reg.unplaced.values()) for p in v["parts"]}
    assert mine == want


def test_board_codes_map_to_nodes(world):
    store, twin = world
    from engines.common import context

    ctx = context(store, twin, T)
    reg = registry()
    for code, zones in {"HYD-101": ["HYD_PUMP"], "LGB-501": ["MLG_L", "MLG_R"], "SPS-501": ["JFS"], "ENG-201": ["FADEC"],
                        "AVI-203": ["INGPS"], "ADC-002": ["ADC"]}.items():
        assert reg.zones_of_code(ctx, code) == zones, code


def test_readiness_cards(world):
    c = triage.readiness_cards(*world, T)
    assert set(c) == {f"TJ10{k}" for k in range(1, 9)}
    assert c["TJ101"] == {"headline": "At depot for overhaul", "detail": "In depot 26 days", "tone": "nmcd", "zones": []}
    assert (c["TJ103"]["headline"], c["TJ103"]["detail"]) == ("Gear unsafe warning", "Twice in four days")
    assert c["TJ103"]["zones"] == [{"zone": "MLG_L", "tone": "p1"}, {"zone": "MLG_R", "tone": "p1"}]
    assert (c["TJ104"]["headline"], c["TJ104"]["detail"]) == ("Flying normally", "Two defects deferred")
    assert (c["TJ105"]["headline"], c["TJ105"]["detail"]) == ("Tyre change due", "Next landing is 8 of 8")
    assert c["TJ107"] == {"headline": "Hydraulic alarm that never clears", "detail": "34 flights in a row · 30 pump removals found nothing",
                          "zones": [{"zone": "HYD_PUMP", "tone": "accent"}]}
    assert c["TJ108"] == {"headline": "Waiting for a brake chute", "detail": "Grounded 80 days", "tone": "nmcs",
                          "zones": [{"zone": "CHUTE", "tone": "nmcs"}]}


def test_twin_view_tj107(world):
    v = triage.twin_view(*world, T, "TJ107")
    assert [x["id"] for x in v["lenses"]] == LENSES
    assert all(x["source"] in SOURCE_LABEL.values() and x["legend"] for x in v["lenses"])
    assert (v["lens"], v["selected"]) == ("evidence", "HYD_PUMP")
    ev = v["lenses"][1]
    assert ev["reporter"] == "BHEEM_EU" and ev["paint"] == {"BHEEM_EU": "reporter", "HYD_PUMP": "suspect", "AMAGB": "suspect2"}
    assert [a["weight"] for a in ev["arcs"]] == [0.8, 0.2]
    p = v["panels"]["HYD_PUMP"]
    assert p["serial"] == "HYDP-000010" and p["inferred"] is True  # film: install record not yet ingested
    assert p["projection"]["kv"][0]["v"] == "0.986" and p["projection"]["kv"][1]["v"] == "33 / 33 RTOK"
    assert [x["label"] for x in p["assessment"]["verdict"] if x.get("on")] == ["Indication path"]
    assert {i["order_id"] for i in p["recommended"]["items"]} == {
        "phx:P-DEC-01:1.4.0:20260622T0800:TJ107:TROUBLESHOOT:748653aa6bcf4544",
        "phx:P-DEC-01:1.4.0:20260622T0800:TJ107:CHANGE_MONITORING_CONFIG:6c744e071d8445f0"}
    assert v["insight"]["title"] == "The alarm stayed with the aircraft through 30 pump removals."
    assert len(v["strip"]["sorties"]) == 61 and sum(x[1] for x in v["strip"]["sorties"]) == 59
    assert v["strip"]["t0"] == "2026-01-05" and v["strip"]["T"] == 168.25


def test_twin_view_every_tail(world):
    for tail in (f"TJ10{k}" for k in range(1, 9)):
        v = triage.twin_view(*world, T, tail)
        assert [x["id"] for x in v["lenses"]] == LENSES, tail
        rr = v["lenses"][4]
        assert rr["source"] == SOURCE_LABEL[next(s for s in SOURCE_LABEL if s.value == "train")]
    assert triage.twin_view(*world, T, "TJ999") is None
    assert triage.twin_view(*world, T, "TJ105")["insight"] is None  # SPS-501 is recurring, not standing


def test_workbench_test_orders(world):
    w = triage.workbench(*world, T, "TJ107-HYD-101")
    assert [x["order"] for x in w["tests"]] == [
        {"action": "TROUBLESHOOT", "parameters": {"code": "HYD-101"}},
        {"action": "TROUBLESHOOT", "parameters": {"position": "AMAGB"}},
        {"action": "REMOVE_REPLACE", "parameters": {"position": "HYDP1"}},
    ]
    positions = {p["position"] for v in (*registry().nodes.values(), *registry().unplaced.values()) for p in v["parts"]}
    for iid in ("TJ103-LGB-501", "TJ106-LGB-501", "TJ105-SPS-501", "TJ102-HYD-101", "TJ102-HYD-001"):
        for x in triage.workbench(*world, T, iid)["tests"]:
            o = x["order"]
            assert o["action"] in ("TROUBLESHOOT", "REMOVE_REPLACE")
            assert ("code" in o["parameters"]) or o["parameters"].get("position") in positions


def test_removal_risk_lens_and_pump_panels(world):
    """S3's hazard model (when its training worlds are built): champion line in the legend, risk rows in the panels."""
    v = triage.twin_view(*world, T, "TJ107")
    rr = v["lenses"][4]
    texts = [x["text"] for x in rr["legend"]]
    if any("not built yet" in x or "not importable" in x for x in texts):
        pytest.skip("hazard model not available here")
    assert any("champion: Weibull AFT on age" in x for x in texts)
    assert any("INSUFFICIENT_EVIDENCE" in x for x in texts)
    assert {t["node"] for t in rr["tags"]} <= {"HYD_PUMP", "HYD_PUMP2"}  # only the fitted class (HYDP)
    for node in ("HYD_PUMP", "HYD_PUMP2"):
        row = next(r for r in v["panels"][node]["projection"]["kv"] if r["k"].startswith("Removal risk"))
        assert row["source"] == "Simulated fleet history" and row["ci"].startswith("[") and 0 <= float(row["v"]) <= 1
