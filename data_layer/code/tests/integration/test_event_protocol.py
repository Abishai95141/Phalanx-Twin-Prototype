"""Cross-module event protocol gate (AD-44): event kinds that cross module boundaries match the catalogue.

Catalogue: configs/interfaces/w1_events.yaml. Convention: a package producing or consuming cross-module events
declares, in its `ports.py`, `MODULE_IDS` (e.g. ("M18",)) and
`EVENTS_OUT` / `EVENTS_IN` = {kind: tuple(payload keys)}.
For each declaring package, the test checks:
  - every declared kind is catalogued;
  - the package's module is the catalogued producer (OUT) or one of the consumers (IN);
  - the declared payload covers every required key (extra keys are allowed);
  - every catalogued kind the module produces is declared in EVENTS_OUT (no silent omissions).
Packages that do not declare events are skipped. The E1 gate requires M02, M10, M11, M12, M14, M18 and M21 to
declare.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from phalanx.dictionary.yamlio import load_yaml

CAT = load_yaml(Path(__file__).resolve().parents[2] / "configs" / "interfaces" / "w1_events.yaml")["events"]
PKGS = {
    "scenario": ("M02",),
    "health": ("M10",),
    "faults": ("M11",),
    "fadec": ("M08",),
    "fcs": ("M05",),
    "airframe": ("M06",),
    "pilot": ("M04",),
    "utilities": ("M09",),
    "sensors": ("M12",),
    "sensors.avionics": ("M12",),  # W2.2: nested ports.py (its SMS events are proposed, EVENTS_IN_PROPOSED)
    "monitoring": ("M14",),
    "maintenance": ("M18",),
    "orders": ("M21",),
}


def protocol_problems(module_ids, events_out: dict, events_in: dict) -> list[str]:
    problems = []
    for kind, keys in events_out.items():
        spec = CAT.get(kind)
        if spec is None:
            problems.append(f"EVENTS_OUT {kind!r} is not a catalogued cross-module event")
            continue
        if spec["producer"] not in module_ids:
            problems.append(
                f"EVENTS_OUT {kind!r}: catalogued producer is {spec['producer']}, not {module_ids}"
            )
        missing = set(spec["payload"]) - set(keys)
        if missing:
            problems.append(f"EVENTS_OUT {kind!r}: payload lacks {sorted(missing)}")
    for kind, keys in events_in.items():
        spec = CAT.get(kind)
        if spec is None:
            problems.append(f"EVENTS_IN {kind!r} is not a catalogued cross-module event")
            continue
        if not set(module_ids) & set(spec["consumers"]):
            problems.append(
                f"EVENTS_IN {kind!r}: {module_ids} is not a catalogued consumer {spec['consumers']}"
            )
        missing = set(spec["payload"]) - set(keys)
        if missing:
            problems.append(f"EVENTS_IN {kind!r}: handler does not read {sorted(missing)}")
    for kind, spec in CAT.items():
        if spec["producer"] in module_ids and kind not in events_out and not spec.get("planned"):
            problems.append(f"catalogued event {kind!r} is produced by {spec['producer']} but not declared")
    return problems


@pytest.mark.integration
@pytest.mark.parametrize("pkg", sorted(PKGS))
def test_module_event_declarations_match_protocol(pkg):
    try:
        m = importlib.import_module(f"phalanx.{pkg}.ports")
    except ModuleNotFoundError:
        pytest.skip(f"{pkg} has no ports.py yet")
    if not hasattr(m, "EVENTS_OUT") and not hasattr(m, "EVENTS_IN"):
        pytest.skip(f"{pkg} declares no cross-module events yet")
    ids = tuple(getattr(m, "MODULE_IDS", PKGS[pkg]))
    problems = protocol_problems(ids, dict(getattr(m, "EVENTS_OUT", {})), dict(getattr(m, "EVENTS_IN", {})))
    assert not problems, "\n".join(problems)


@pytest.mark.unit
def test_protocol_check_catches_mismatches():
    """Negative control: wrong producer, missing payload key, uncatalogued kind, undeclared produced event."""
    good_out = {k: tuple(v["payload"]) for k, v in CAT.items() if v["producer"] == "M18"}
    good_in = {k: tuple(v["payload"]) for k, v in CAT.items() if "M18" in v["consumers"]}
    assert protocol_problems(("M18",), good_out, good_in) == []
    bad_out = dict(good_out)
    bad_out.pop("cfg.install")  # silent omission
    bad_out["mx.repaired"] = ("serial",)  # missing 'level'
    bad_out["truth.fault"] = tuple(CAT["truth.fault"]["payload"])  # M18 is not its producer
    bad_out["mx.private_thing"] = ()  # uncatalogued
    msgs = "\n".join(protocol_problems(("M18",), bad_out, good_in))
    for needle in (
        "'cfg.install' is produced",
        "lacks ['level']",
        "catalogued producer is M11",
        "mx.private_thing",
    ):
        assert needle in msgs, msgs


@pytest.mark.unit
def test_catalogue_well_formed():
    mods = {f"M{i:02d}" for i in range(1, 23)}
    for kind, spec in CAT.items():
        assert set(spec) <= {"producer", "consumers", "payload", "hidden", "planned"}, kind
        assert all(isinstance(k, str) for k in spec["payload"]), (
            f"{kind}: non-string payload key (YAML bool?)"
        )
        assert spec["producer"] in mods and set(spec["consumers"]) <= mods, kind
        assert spec["payload"] and len(set(spec["payload"])) == len(spec["payload"]), kind
