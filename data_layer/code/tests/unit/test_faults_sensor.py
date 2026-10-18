"""The M11 -> M12 ``sensor_fault`` payload (AD-42): exactly ``{channel, mode, value, rate, duty, probe}``,
checked against M12's acceptance rules before it is sent; every sensor channel the catalogue or the graph
names is an M12 channel; the intermittent two-rate form converts to M12's (rate, duty)."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.dictionary import load_dictionary
from phalanx.faults import load_catalogue, load_graph
from phalanx.faults.catalogue import SENSOR_MODES
from phalanx.faults.sensor_faults import (
    SENSOR_FAULT_EVENT,
    SENSOR_FAULT_KEYS,
    SENSOR_FAULT_MODES,
    intermittent_rate_duty,
    sensor_fault_payload,
)
from phalanx.sensors.config import build_sensor_config
from phalanx.sensors.module import SENSOR_FAULT_EVENT as M12_EVENT

pytestmark = pytest.mark.unit


def test_event_kind_and_modes_are_m12s():
    from phalanx.sensors import kernel as K

    assert SENSOR_FAULT_EVENT == M12_EVENT
    m12_modes = (set(K.FAULT_MODES) - {"none"}) | {"slow", "probe_open", "probe_short", "clear"}
    assert set(SENSOR_FAULT_MODES) == m12_modes
    assert set(SENSOR_MODES) - {"*"} == m12_modes - {"clear"}


def test_payload_has_exactly_the_ad42_keys():
    for mode, kw in (
        ("bias", {"value": -2.0e5}),
        ("drift", {"value": 3.4e3}),
        ("stuck", {}),
        ("open", {}),
        ("short", {"value": 1.0e6}),
        ("intermittent", {"rate": 0.2, "duty": 0.1}),
        ("spikes", {"value": 50.0, "rate": 0.05}),
        ("slow", {"value": 5.0}),
        ("probe_open", {"probe": 2}),
        ("probe_short", {"probe": 0, "value": 644.15}),
        ("clear", {}),
    ):
        p = sensor_fault_payload("ENG.PS3.A", mode, **kw)
        assert tuple(p) == SENSOR_FAULT_KEYS
        assert p["mode"] == mode and isinstance(p["probe"], int)
        assert all(isinstance(p[k], float) for k in ("value", "rate", "duty"))


@pytest.mark.parametrize(
    ("mode", "kw"),
    [
        ("explode", {}),
        ("spikes", {"value": 1.0}),  # no rate
        ("intermittent", {"rate": 1.0, "duty": 1.0}),
        ("slow", {"value": 0.5}),
        ("probe_open", {}),  # no probe index
        ("bias", {"probe": 1}),  # probe index on a channel mode
        ("bias", {"value": float("nan")}),
    ],
)
def test_payloads_m12_would_reject_are_refused(mode, kw):
    with pytest.raises(ValueError):
        sensor_fault_payload("ENG.PS3.A", mode, **kw)


def test_intermittent_rate_duty_matches_m12_dwell_means():
    """M12: mean dwell normal = 2 (1 - duty) / rate, open = 2 duty / rate."""
    on, off = 0.05, 0.45
    rate, duty = intermittent_rate_duty(on, off)
    assert 2.0 * (1.0 - duty) / rate == pytest.approx(1.0 / on)
    assert 2.0 * duty / rate == pytest.approx(1.0 / off)
    with pytest.raises(ValueError):
        intermittent_rate_duty(0.0, 1.0)


def test_every_named_sensor_channel_is_an_m12_channel():
    """AD-42: sensor faults address M12 channels (its ``bias_index()``)."""
    m12 = set(build_sensor_config(load_dictionary()).bias_index())
    named = {
        str(e.fields["channel"])
        for m in load_catalogue().values()
        for e in m.effects
        if e.target == "sensors" and e.fields["channel"] != "*"
    }
    named |= {
        str(e["channel"]) for n in load_graph().nodes.values() for e in n.effects if e["target"] == "sensors"
    }
    assert named and named <= m12, sorted(named - m12)
    assert np.all([c.count(".") >= 1 for c in named])
