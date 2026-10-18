"""Hidden-state catalogue (architecture §5.2): all 50 states of not_measured_states.csv are catalogued with an
observability class, an owner and a process; every slot exists in the M10 index maps and every M10 state
belongs
to a catalogued hidden state (both directions)."""

from __future__ import annotations

import csv

import pytest

from phalanx.dictionary import load_dictionary
from phalanx.health.components import AIRFRAME_PROCS, ENGINE_AUX_PROCS, OWNED_ELSEWHERE
from phalanx.health.labels import hidden_state_catalogue
from phalanx.health.layout import (
    ACTUATORS,
    AIRFRAME_NAMES,
    ENGINE_AUX_NAMES,
    ENGINE_DELTAS,
    excluded_bias_channels,
    hidden_entries,
    sensor_bias_channels,
    utility_entries,
)

CSV = "research_notes/Virtual fighter telemetry layer research/not_measured_states.csv"


@pytest.fixture(scope="module")
def csv_ids(repo_root):
    with open(repo_root / CSV, encoding="utf-8") as fh:
        return [r["state_id"] for r in csv.DictReader(fh)]


@pytest.mark.unit
def test_catalogue_covers_all_50_hidden_states(csv_ids):
    cat = hidden_state_catalogue()
    assert len(csv_ids) == 50
    missing = sorted(set(csv_ids) - set(cat))
    assert not missing, missing
    classes = {"model_observable", "usage_inferred", "late_symptom", "ground_inspection"}
    for sid in csv_ids:
        assert cat[sid]["class"] in classes, sid
        assert cat[sid]["process"], sid
        assert cat[sid]["owner"] in {"engine_serial", "component_serial", "sensor_serial", "tail", "M09"}, sid


@pytest.mark.unit
def test_every_slot_exists_in_the_index_maps():
    cat = hidden_state_catalogue()
    util = {u.name for u in hidden_entries(1)}
    for sid, entry in cat.items():
        for slot in entry["slots"]:
            port, _, name = slot.partition(":")
            name = name.replace("{e}", "1")
            if port == "health.engine":
                assert name in ENGINE_DELTAS, (sid, slot)
            elif port == "m10":
                if name.endswith("*"):
                    assert any(u.startswith(name[:-1]) for u in util), (sid, slot)
                else:
                    assert name in util, (sid, slot)
            elif port == "health.actuator":
                assert name == "*"
            elif port == "health.sensor_bias":
                assert name.endswith("*")
            else:
                pytest.fail(f"{sid}: unknown port {port}")


@pytest.mark.unit
def test_every_m10_state_belongs_to_a_catalogued_hidden_state(csv_ids):
    cat = hidden_state_catalogue()
    for u in hidden_entries(2):
        assert u.nm_id in cat, u
        assert u.nm_id in csv_ids, u
    assert set(OWNED_ELSEWHERE) <= set(csv_ids)
    assert [p.state for p in AIRFRAME_PROCS] and {p.state for p in AIRFRAME_PROCS} == set(AIRFRAME_NAMES)
    assert {p.state for p in ENGINE_AUX_PROCS} <= set(ENGINE_AUX_NAMES)
    assert len(ACTUATORS) == 13


@pytest.mark.unit
def test_utility_port_is_m09_health_index():
    """health.utility exports exactly M09's HEALTH_INDEX (coordinator decision, W1.4), each entry from a
    catalogued M10 hidden state."""
    from phalanx.utilities.layout import HEALTH_INDEX

    assert (
        tuple(u.name for u in utility_entries(1)) == HEALTH_INDEX == tuple(u.name for u in utility_entries(2))
    )
    cat = hidden_state_catalogue()
    assert all(u.nm_id in cat for u in utility_entries(1))


@pytest.mark.unit
def test_hidden_inventory_is_engine_major_and_scales_with_engines():
    one, two = hidden_entries(1), hidden_entries(2)
    assert len(two) - len(one) == len(ENGINE_AUX_NAMES)
    assert one[0].name == "eng1_vg_offset" and two[len(ENGINE_AUX_NAMES)].name == "eng2_vg_offset"
    assert all(u.reference > 0 for u in two)


@pytest.mark.unit
def test_sensor_bias_index_map_is_m12_channel_order_in_si():
    """AD-42: the ``health.sensor_bias`` index map is M12's ``SensorConfig.bias_index()``, entry by entry, in
    each channel's SI unit (the unit M12 adds the bias in)."""
    from phalanx.sensors.config import build_sensor_config

    d = load_dictionary()
    cfg = build_sensor_config(d)
    chans = sensor_bias_channels(d)
    ids = tuple(b.channel_id for b in chans)
    assert ids == cfg.bias_index()
    assert tuple(b.si_units for b in chans) == cfg.si_units
    assert "ENG.T5.HARNESS_A" in ids and "ENG.N2.A" in ids and "AD.PS.A" in ids
    assert "ENG.T5" not in ids  # computed (averaged) channel: no installation bias of its own
    assert "ENG.N2.V" not in ids  # voted output
    excluded = excluded_bias_channels(d)  # physical sensors M12 does not model yet: no bias consumer
    assert "SPS.JFS.SPEED" in excluded and not set(excluded) & set(ids)
    for b in chans:
        assert b.span_si > 0, b
        lo, hi = b.rails_si
        assert hi > lo
    sub = build_sensor_config(d, channels=("ENG.PS3.A", "ENG.N2.A"))
    assert tuple(b.channel_id for b in sensor_bias_channels(d, sub)) == sub.bias_index()
