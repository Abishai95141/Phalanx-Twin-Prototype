"""MF4c (E1-MF): content-level M14 A6 leak test. No consumer-facing M14 field carries M11 truth.

E1 found that W1.5 A6 could not fail: a mutant writing M11 truth into M14's `description` passed all 25 M14
tests, because A6 checked the schema (no restricted column) and never the *content* of the consumer columns.
M14 holds M11 truth only as the `monitor.lru_condition` payload (code, magnitude = catalogue magnitude x
severity, covered, instance) and its stored condition shift `t_h`; it must turn that into observations
(declared BIT codes, cautions) and nothing else.

1. **Content scan (real M11 -> real M14).** Two scripted faults with deliberately unusual severities run
   through the real injector into the real monitor over one sortie. Every cell of every consumer topic
   (`events.bit_faults`, `events.exceedances`, `events.cautions`, `usage.counters`; strings, nested lists and
   structs, floats) is scanned for the truth: fault-mode ids, names and failure-mechanism refs, fault ids,
   severities and condition magnitudes (as numbers and rendered to 2-6 decimals), and the names of the hidden
   payload fields.
2. **Differential (at the M14 boundary).** Conditions that differ only in hidden truth M14 must not report
   (the M11 instance number; a saturated condition magnitude) give identical consumer tables.

Each check is shown to fail on a planted leak (`test_scan_and_differential_catch_a_planted_leak`); the E1
mutant (truth in `description`) is run on an archived copy in the E1-MF report.

Sample: one 1 h sortie, two injected faults (scan); two pairs of one-condition sorties (differential).
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.health import sensor_bias_channels
from phalanx.monitoring import (
    MonitoringConfig,
    MonitoringModule,
    contract_tables,
    load_code_table,
    load_monitoring_params,
    lru_condition_payload,
)

pytestmark = pytest.mark.integration
D = load_dictionary()
P = load_monitoring_params()
CODES = load_code_table(D, P)
SEC = 10**9
H = 3600 * SEC
DAY = 24 * H
EPOCH = 1_800_000_000 * SEC
TAIL = "KH2011"
SID = f"{TAIL}-0"
#: scripted faults: (mode, severity) with severities no consumer value could equal by chance
FAULTS = (("FM.AV.LRU_FAILURE", 7.3519), ("FM.AD.HEATER_FAIL", 1.2347))
HIDDEN_KEYS = ("instance", "covered", "magnitude", "fault_id")  # names of hidden payload fields


def _monitor(root: int = 0xC0DE) -> MonitoringModule:
    cfg = MonitoringConfig.from_dictionary(D, CODES, ("IN20-0001",), regime="mature")
    return MonitoringModule("monitoring", P, config=cfg)


def _sortie_frame(t0: int) -> tuple[list[Event], list[Event]]:
    start = [Event(t0, "monitor.sortie_start", "monitoring", {"sortie_id": SID})]
    end = [
        Event(t0 + 3500 * SEC, "monitor.landing", "monitoring", {}),
        Event(
            t0 + H + 1,
            "monitor.sortie_end",
            "monitoring",
            {
                "flight_time_s": np.array(3250.0),
                "landings": np.array(1.0),
                "ab_lights": np.array([0.0]),
                "starts": np.array([1.0]),
            },
        ),
    ]
    return start, end


def _tables(m: MonitoringModule, st) -> dict[str, pa.Table]:
    return contract_tables(
        m, st, dictionary=D, tail_no=TAIL, epoch_utc_ns=EPOCH, t_ingest_utc_ns=EPOCH + DAY, sortie_id=SID
    )


@pytest.fixture(scope="module")
def m11_to_m14():
    """One sortie: real M11 injects FAULTS, its lru_condition events reach the real M14."""
    m = _monitor()
    f = FaultInjector(
        "faults",
        load_fault_params(),
        config=FaultConfig(
            load_catalogue(),
            load_graph(),
            {"monitoring": "monitoring"},
            ("IN20-0001",),
            sensor_bias_channels(D),
            realise_physics_edges=False,
            stochastic=False,
        ),
    )
    sysm = System(
        [f, m], [], rng=RngService(0xC0DE, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail=TAIL)
    )
    start, end = _sortie_frame(0)
    evs = [
        *start,
        Event(1, "faults.sortie_start", "faults", {"sortie_id": SID, "duration_s": 3600.0}),
        *(
            Event(
                (60 + 60 * j) * SEC,
                "faults.inject",
                "faults",
                {"mode": mode, "severity": sev, "covered": True},
            )
            for j, (mode, sev) in enumerate(FAULTS)
        ),
        *end,
        Event(H + 2, "faults.sortie_end", "faults", {"flight_time_s": 3600.0}),
    ]
    w, trace = sysm.run(sysm.inject(sysm.start(), evs), 240 * 3600 + 10)
    conditions = [e.payload for _, e in trace.dispatched if e.kind == "monitor.lru_condition"]
    return f, m, w, conditions


def _cells(tab: pa.Table):
    """(column, python value) of every leaf cell (lists and structs flattened)."""

    def leaves(v):
        if isinstance(v, dict):
            for x in v.values():
                yield from leaves(x)
        elif isinstance(v, list | tuple):
            for x in v:
                yield from leaves(x)
        else:
            yield v

    for name in tab.column_names:
        for v in tab.column(name).to_pylist():
            for leaf in leaves(v):
                yield name, leaf


def _renderings(x: float) -> set[str]:
    # 2 decimals at least: a 1-decimal rendering ('1.2') is too short to tell a leak from a version string
    return {repr(x), f"{x:g}", f"{x:.2f}", f"{x:.3f}", f"{x:.4f}", f"{x:.6f}", f"{x:.3e}"}


def leak_problems(tables: dict[str, pa.Table], strings: set[str], numbers: set[float]) -> list[str]:
    """Truth found in consumer cells: a truth string as a substring of a text cell, a truth number rendered
    in a text cell, or a float cell equal to a truth number (relative 1e-9)."""
    texts = {r for x in numbers for r in _renderings(x)}
    out = []
    for topic, tab in tables.items():
        for col, v in _cells(tab):
            if isinstance(v, str):
                low = v.lower()
                out += [f"{topic}.{col}: {v!r} contains {s!r}" for s in strings if s.lower() in low]
                out += [f"{topic}.{col}: {v!r} renders {r!r}" for r in texts if r in v]
            elif isinstance(v, float) and not isinstance(v, bool):
                out += [
                    f"{topic}.{col}: {v!r} == truth {x!r}"
                    for x in numbers
                    if np.isclose(v, x, rtol=1e-9, atol=0)
                ]
    return out


def _truth(f: FaultInjector, st, conditions) -> tuple[set[str], set[float]]:
    strings: set[str] = set(HIDDEN_KEYS)
    numbers: set[float] = set()
    for j, mi in enumerate(st["inst_mode"]):
        mode = f.config.catalogue[f.config.mode_ids[int(mi)]]
        strings |= {mode.id, mode.name, f.fault_id(j, mode), mode.id.split(".", 1)[1]}
        if getattr(mode, "nm_ref", None):
            strings.add(str(mode.nm_ref))
        numbers.add(float(st["inst_sev"][j]))
    numbers |= {float(c["magnitude"]) for c in conditions}
    return strings, numbers


def test_m14_consumer_topics_carry_no_m11_truth(m11_to_m14):
    """MF4c content scan: the injected conditions were observed (declared codes), and no consumer cell carries
    a fault mode, a fault id, a severity, a condition magnitude or a hidden field name."""
    f, m, w, conditions = m11_to_m14
    st = w.states["monitoring"]
    tabs = _tables(m, st)
    assert {round(float(c["magnitude"]), 4) for c in conditions} == {7.3519, round(8.0 * 1.2347, 4)}
    codes = {str(np.asarray(c["code"]).item()) for c in conditions}
    declared = set(tabs["events.bit_faults"].column("event_code").to_pylist())
    assert codes <= declared, (codes, declared)  # the leak scan below is not vacuous
    strings, numbers = _truth(f, w.states["faults"], conditions)
    assert {"FM.AV.LRU_FAILURE", "FM.AD.HEATER_FAIL", 7.3519} <= strings | numbers
    assert leak_problems(tabs, strings, numbers) == []


def _boundary_run(payloads: list[dict]) -> dict[str, pa.Table]:
    """M14 alone, one sortie, the given lru_condition payloads (as M11 sends them) at 60 s, 120 s, ..."""
    m = _monitor()
    sysm = System(
        [m], [], rng=RngService(0xC0DE, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail=TAIL)
    )
    start, end = _sortie_frame(0)
    evs = [*start]
    evs += [
        Event((60 + 60 * j) * SEC, "monitor.lru_condition", "monitoring", p) for j, p in enumerate(payloads)
    ]
    w, _ = sysm.run(sysm.inject(sysm.start(), [*evs, *end]), 240 * 3600 + 10)
    return _tables(m, w.states["monitoring"])


def _same(a: dict[str, pa.Table], b: dict[str, pa.Table]) -> list[str]:
    return [t for t in a if not a[t].equals(b[t])]


def test_hidden_condition_fields_do_not_reach_consumer_tables():
    """MF4c differential: the M11 instance number, and the size of a condition far beyond detection, change
    nothing a consumer sees (identical tables), while the condition itself is observed."""
    base = _boundary_run([lru_condition_payload("AVI-203", 30.0, instance=0)])
    assert "AVI-203" in base["events.bit_faults"].column("event_code").to_pylist()
    assert _same(base, _boundary_run([lru_condition_payload("AVI-203", 30.0, instance=7)])) == []
    assert _same(base, _boundary_run([lru_condition_payload("AVI-203", 45.0, instance=0)])) == []


def test_scan_and_differential_catch_a_planted_leak(m11_to_m14):
    """Negative control: the condition magnitude written into `description` (the E1 mutant's leak) is found by
    the scan; a description carrying the instance number breaks the differential."""
    f, m, w, conditions = m11_to_m14
    st = w.states["monitoring"]
    tabs = _tables(m, st)
    strings, numbers = _truth(f, w.states["faults"], conditions)
    bit = tabs["events.bit_faults"]
    j = bit.column_names.index("description")
    leaked = [f"{d} ({st['t_h'].max():.2f})" for d in bit.column("description").to_pylist()]
    bad = dict(tabs, **{"events.bit_faults": bit.set_column(j, "description", pa.array(leaked, pa.string()))})
    got = leak_problems(bad, strings, numbers)
    assert got and all("description" in g for g in got), got
    a = _boundary_run([lru_condition_payload("AVI-203", 30.0, instance=0)])
    b = _boundary_run([lru_condition_payload("AVI-203", 30.0, instance=7)])
    tag = [f"{d} #7" for d in b["events.bit_faults"].column("description").to_pylist()]
    b = dict(
        b,
        **{
            "events.bit_faults": b["events.bit_faults"].set_column(
                j, "description", pa.array(tag, pa.string())
            )
        },
    )
    assert _same(a, b) == ["events.bit_faults"]
