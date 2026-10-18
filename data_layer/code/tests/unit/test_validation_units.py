"""The battery's unit check is pint equivalence: same unit under any spelling passes; compatible-but-different
units fail (the battery never converts, AD-40)."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.validation.battery import BatteryConfig
from phalanx.validation.flightdata import DASHLINK_UNITS, FlightRecord
from phalanx.validation.units import UnitSpellingError, units_equivalent

pytestmark = pytest.mark.unit

EQUIVALENT = [
    ("lb/hr", "lb/h"),  # the W0.3 dictionary spelling vs the battery default
    ("pound / hour", "lb/h"),
    ("%", "percent"),
    ("degree", "deg"),
    ("degree_Celsius", "degC"),
    ("kelvin", "K"),
    ("dimensionless", ""),
]
NOT_EQUIVALENT = [
    ("kg/s", "lb/h"),  # same dimensionality, factor 7,937
    ("kg/hr", "lb/hr"),  # same dimensionality, factor 2.2
    ("K", "degC"),  # same dimensionality, offset 273.15
    ("degF", "degC"),
    ("rad", "deg"),  # factor 57.3
    ("percent", "dimensionless"),  # factor 100
    ("rad", "dimensionless"),  # pint calls rad dimensionless; kept apart as in phalanx.core.units
    ("rpm", "percent"),  # different quantity
    ("m", "lb/h"),  # incompatible dimensions
]


@pytest.mark.parametrize(("a", "b"), EQUIVALENT)
def test_equivalent_spellings_pass(a, b):
    assert units_equivalent(a, b) and units_equivalent(b, a)


@pytest.mark.parametrize(("a", "b"), NOT_EQUIVALENT)
def test_compatible_or_different_units_fail(a, b):
    assert not units_equivalent(a, b) and not units_equivalent(b, a)


def test_unparseable_unit_is_an_error():
    with pytest.raises(UnitSpellingError):
        units_equivalent("lb/fortnightz", "lb/h")


def _rec(units: dict[str, str]) -> FlightRecord:
    n = 50
    return FlightRecord(
        flight_id="f",
        rate_hz=4.0,
        outputs={f: np.full((4, n), 50.0) for f in ("N1", "N2", "EGT", "FF")},
        pla=np.full((4, n), 40.0),
        theta=np.ones(n),
        delta=np.ones(n),
        phase=np.full(n, 5),
        units=units,
    )


def test_config_accepts_dictionary_spellings_and_rejects_conversions():
    cfg = BatteryConfig()
    dictionary_spelling = {**DASHLINK_UNITS, "FF": "lb/hr", "N1": "%", "PLA": "degree"}
    cfg.check(_rec(dictionary_spelling))  # equivalent: accepted
    for k, bad in (("FF", "kg/s"), ("EGT", "K"), ("N1", "dimensionless"), ("PLA", "rad")):
        with pytest.raises(ValueError, match="never converts"):
            cfg.check(_rec({**DASHLINK_UNITS, k: bad}))
    with pytest.raises(ValueError, match="never converts"):
        cfg.check(_rec({k: v for k, v in DASHLINK_UNITS.items() if k != "theta"}))  # missing unit


def test_kelvin_offset_follows_equivalent_units():
    assert BatteryConfig(units={**DASHLINK_UNITS, "EGT": "degree_Celsius"}).kelvin_offset == 273.15
    assert BatteryConfig(units={**DASHLINK_UNITS, "EGT": "kelvin"}).kelvin_offset == 0.0
    with pytest.raises(ValueError):
        _ = BatteryConfig(units={**DASHLINK_UNITS, "EGT": "degF"}).kelvin_offset
