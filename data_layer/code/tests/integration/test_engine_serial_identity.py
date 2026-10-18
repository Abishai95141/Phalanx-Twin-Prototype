"""Engine serial identity (coordinator cross-check, W2.1c): ``engine_serial`` is a contract linkage key,
so one format and one source of truth. The M02 scenario's installed engine serials (``IN20-<token>``) are
the source: M18 installs them (``FleetSpec.from_scenario``) and mints further engines in the same format,
and M10 / M11 / M14 are configured with them; every message and record that names the engine of a tail names
the same serial.

Tie checked in the real operations world of ``test_maintenance_protocol_runtime`` (M02 + M18 + M21 + sink
+ the M10 / M11 / M14 of one tail; 2 tails x 4 days, one seed, the same scripted orders and faults; n = 1 run
per arm): M18's installed engine per tail, M10's installed engine serial, M11's and M14's configured serial,
M02's ``usage.sortie_summary`` ``engine_serials``, every maint.records row (M18) of the monitored tail
that names an engine, and every events.* row (M14 obs.event) that names one (this world has no engine code,
so M14 rows are covered through its configured serial, which those rows carry). Negative control: the W1
wiring (M18 mints ``ENG-nnnnnn`` itself) is caught. Loader checks: a scenario serial outside the format,
a duplicate and mixed prefixes are rejected.
"""

from __future__ import annotations

import dataclasses

import pytest
from test_maintenance_protocol_runtime import FLEET, IDS, SERIAL, TAIL, run_world

from phalanx.health.protocol import read_payload
from phalanx.maintenance.world import ENGINE_CLASS, FleetSpec, MaintenanceWorld
from phalanx.scenario.config import ENGINE_SERIAL_PREFIX

pytestmark = pytest.mark.integration


def serial_mismatches(events, session) -> list[str]:
    """Every place the run names the engine of a tail, against the scenario's serial of that tail."""
    want = {t: s for sq in FLEET.squadrons for t, s in zip(sq.tails, sq.engine_serials, strict=True)}
    out: list[str] = []
    w = session.world
    m18: MaintenanceWorld = session.system.modules[IDS.m18]
    st = w.states[IDS.m18]
    eng = next(c.index for c in m18.cat.classes if c.code == ENGINE_CLASS)
    for ti, tail in enumerate(m18.fleet.tails):
        inst = [
            str(st["ser_no"][r])
            for r in range(st["ser_no"].shape[0])
            if int(st["ser_cls"][r]) == eng and int(st["ser_tail"][r]) == ti and int(st["ser_pos"][r]) >= 0
        ]
        if inst != [want[tail]]:
            out.append(f"M18 installed engine of {tail}: {inst} != {want[tail]}")
    minted = {str(st["ser_no"][r]) for r in range(st["ser_no"].shape[0]) if int(st["ser_cls"][r]) == eng}
    out += [
        f"M18 engine serial {s} is not {ENGINE_SERIAL_PREFIX}-<token>"
        for s in sorted(minted)
        if not s.startswith(f"{ENGINE_SERIAL_PREFIX}-")
    ]
    if [str(x) for x in w.states["m10"]["eng_serial"]] != [want[TAIL]]:
        out.append(f"M10 engine serial {list(w.states['m10']['eng_serial'])} != {want[TAIL]}")
    for mid in ("m11", "m14"):
        cfg = session.system.modules[mid].config.engine_serials
        if tuple(cfg) != (want[TAIL],):
            out.append(f"{mid} configured engine serials {cfg} != {want[TAIL]}")
    seen = {"summary": 0, "maint": 0, "events": 0}
    for e in events:
        if e.kind == "usage.sortie_summary":
            d = read_payload(e.payload)
            seen["summary"] += 1
            if list(d["engine_serials"]) != [want[str(d["tail_no"])]]:
                out.append(f"M02 summary {d['sortie_id']}: {d['engine_serials']}")
        elif e.kind in ("rec.maint.records", "obs.event"):
            row = read_payload(e.payload)["row"]
            tail, sn = row.get("tail_no"), row.get("engine_serial")
            if sn is None or tail not in want:
                continue
            seen["maint" if e.kind.startswith("rec.") else "events"] += 1
            if sn != want[tail] and not (e.kind.startswith("rec.") and sn in minted):
                out.append(f"{e.kind} {row.get('record_type', row.get('code', ''))} of {tail}: {sn}")
    # events.* rows name an engine only for engine codes (none in this world)
    if not (seen["summary"] and seen["maint"]):
        out.append(f"the run never named an engine in the summaries and the records: {seen}")
    return out


def _run(fleet_spec=None):
    box: list = []
    events = run_world(fleet_spec=fleet_spec, session=box)
    return events, box[0]


def test_one_engine_identity_across_m02_m18_m10_m11_m14():
    events, session = _run()
    assert serial_mismatches(events, session) == []
    assert SERIAL == f"{ENGINE_SERIAL_PREFIX}-{TAIL}"


def test_w1_wiring_is_caught():
    """Negative control: M18 minting its own ``ENG-nnnnnn`` serials (the W1 FleetSpec) breaks the tie."""
    w1 = FleetSpec(FLEET.tails(), ("SUL",), (0, 0))
    events, session = _run(w1)
    bad = serial_mismatches(events, session)
    assert any("M18 installed engine" in b for b in bad) and any("ENG-0" in b for b in bad), bad


def test_fleet_spec_rejects_a_second_format_or_duplicate_serials():
    with pytest.raises(ValueError, match="one format"):
        FleetSpec(
            ("A", "B"), ("SUL",), (0, 0), engine_serials=("IN20-A", "ENG-000001"), engine_serial_prefix="IN20"
        )
    with pytest.raises(ValueError, match="unique"):
        FleetSpec(
            ("A", "B"), ("SUL",), (0, 0), engine_serials=("IN20-A", "IN20-A"), engine_serial_prefix="IN20"
        )
    sq = FLEET.squadrons[0]
    mixed = dataclasses.replace(
        FLEET, squadrons=(dataclasses.replace(sq, engine_serials=("IN20-X", "F404-Y")),)
    )
    with pytest.raises(ValueError, match="one engine serial format"):
        FleetSpec.from_scenario(mixed)


def test_scenario_loader_enforces_the_format(tmp_path):
    from pathlib import Path

    from phalanx.scenario.config import load_fleet_scenario

    root = Path(__file__).resolve().parents[2] / "configs" / "scenarios"
    text = (root / "tejas_two_squadrons.yaml").read_text()
    (tmp_path / "bases.yaml").write_text((root / "bases.yaml").read_text())
    bad = text.replace(
        "    tails: [TJ101,", "    engine_serials: [ENG-1" + ", IN20-X" * 15 + "]\n    tails: [TJ101,", 1
    )
    (tmp_path / "s.yaml").write_text(bad)
    with pytest.raises(ValueError):
        load_fleet_scenario(tmp_path / "s.yaml")
