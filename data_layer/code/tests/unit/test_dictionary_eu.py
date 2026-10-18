"""EU <-> SI conversion API for M13: Dictionary.eu_to_si / si_to_eu / eu_conversion (E0 fix 4).

Sample: every channel of the Tejas dictionary (464): the requirement is coverage of every unit class, and the
whole dictionary is small. Expected factors are written out independently of pint (exact definitions: 1 ft =
0.3048 m, 1 lb = 0.45359237 kg, g0 = 9.80665 m/s^2, 1 in = 0.0254 m, 1 kn = 1852/3600 m/s).
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.units import parse_unit
from phalanx.dictionary import CompileError, Dictionary, EUConversionError, compile_bundle, load_bundle

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"

LB = 0.45359237
G0 = 9.80665
RPM = 2 * math.pi / 60
#: (quantity, EU) -> (SI unit, scale, offset): si = eu * scale + offset
EXPECTED = {
    ("airspeed", "knot"): ("m/s", 1852 / 3600, 0.0),
    ("altitude", "ft"): ("m", 0.3048, 0.0),
    ("angle", "deg"): ("rad", math.pi / 180, 0.0),
    ("angular_rate", "deg/s"): ("rad/s", math.pi / 180, 0.0),
    ("charge", "A*hour"): ("C", 3600.0, 0.0),
    ("code", "dimensionless"): ("1", 1.0, 0.0),
    ("command_percent", "percent"): ("1", 0.01, 0.0),
    ("concentration", "percent"): ("1", 0.01, 0.0),
    ("concentration", "ppm"): ("1", 1e-6, 0.0),
    ("count", "count"): ("1", 1.0, 0.0),
    ("current", "A"): ("A", 1.0, 0.0),
    ("discrete", "dimensionless"): ("1", 1.0, 0.0),
    ("energy", "MJ"): ("J", 1e6, 0.0),
    ("enum", "dimensionless"): ("1", 1.0, 0.0),
    ("force", "lbf"): ("N", LB * G0, 0.0),
    ("frequency", "Hz"): ("Hz", 1.0, 0.0),
    ("length", "mm"): ("m", 1e-3, 0.0),
    ("level_percent", "percent"): ("1", 0.01, 0.0),
    ("life_count", "count"): ("1", 1.0, 0.0),
    ("life_time", "hour"): ("s", 3600.0, 0.0),
    ("mach", "dimensionless"): ("1", 1.0, 0.0),
    ("mass", "kg"): ("kg", 1.0, 0.0),
    ("mass_flow", "lb/hr"): ("kg/s", LB / 3600, 0.0),
    ("position_percent", "percent"): ("1", 0.01, 0.0),
    ("pressure", "bar"): ("Pa", 1e5, 0.0),
    ("pressure", "kPa"): ("Pa", 1e3, 0.0),
    ("pressure", "mbar"): ("Pa", 100.0, 0.0),
    ("pressure", "pound_force/foot**2"): ("Pa", LB * G0 / 0.3048**2, 0.0),
    ("pressure", "psi"): ("Pa", LB * G0 / 0.0254**2, 0.0),
    ("rotational_speed", "rpm"): ("rad/s", RPM, 0.0),
    ("specific_force", "standard_gravity"): ("m/s**2", G0, 0.0),
    ("speed", "ft/s"): ("m/s", 0.3048, 0.0),
    ("strain", "microstrain"): ("1", 1e-6, 0.0),
    ("temperature", "degC"): ("K", 1.0, 273.15),
    ("temperature", "degF"): ("K", 5 / 9, 273.15 - 32 * 5 / 9),
    ("time", "s"): ("s", 1.0, 0.0),
    ("vertical_speed", "ft/min"): ("m/s", 0.3048 / 60, 0.0),
    ("vibration_velocity", "in/s"): ("m/s", 0.0254, 0.0),
    ("voltage", "V"): ("V", 1.0, 0.0),
    ("volume", "L"): ("m**3", 1e-3, 0.0),
    ("wear_percent", "percent"): ("1", 0.01, 0.0),
}
#: % of rated speed: the reference speeds of constants.yaml channel_reference (100 % = rpm)
PERCENT_RATED = {"ENG.N1": 13270.0, "ENG.N2": 16810.0, "SPS.JFS.SPEED": 60000.0}
NO_SI = {("text", "dimensionless"), ("media", "dimensionless")}


@lru_cache(maxsize=1)
def _d() -> Dictionary:
    return Dictionary(compile_bundle(load_bundle(CONFIG)))


def _expected(ch):
    key = (ch["quantity"], ch["units"])
    if key == ("speed_percent", "percent"):
        rpm = PERCENT_RATED.get(ch["param_id"])
        return None if rpm is None else ("rad/s", rpm * RPM / 100, 0.0)
    return EXPECTED.get(key)


def test_every_unit_class_in_the_dictionary_is_covered():
    """A new (quantity, unit) class fails here until its conversion is added and checked."""
    classes = {(ch["quantity"], ch["units"]) for ch in _d().channels()}
    assert classes <= set(EXPECTED) | NO_SI | {("speed_percent", "percent")}
    assert set(EXPECTED) <= classes, "stale expected classes"


def test_conversion_factors_match_independent_definitions():
    d = _d()
    checked = 0
    for ch in d.channels():
        exp = _expected(ch)
        if exp is None:
            continue
        conv = d.eu_conversion(ch["channel_id"])
        assert conv.si_units == exp[0], ch["channel_id"]
        assert math.isclose(conv.scale, exp[1], rel_tol=1e-12), (ch["channel_id"], conv.scale, exp[1])
        assert math.isclose(conv.offset, exp[2], rel_tol=1e-12, abs_tol=0.0), ch["channel_id"]
        assert parse_unit(conv.si_units)  # coherent SI (core invariant I3)
        checked += 1
    assert checked == 464 - 13  # all but 11 text + 2 media channels


def _span(ch):
    rng = ch["range"]
    if rng and rng["min"] is not None and rng["max"] is not None:
        return float(rng["min"]), float(rng["max"])
    return -1000.0, 1000.0


def test_round_trip_on_arrays_is_exact_within_float_tolerance():
    d = _d()
    for ch in d.channels():
        if _expected(ch) is None:
            continue
        cid = ch["channel_id"]
        lo, hi = _span(ch)
        eu = np.linspace(lo, hi, 64).reshape(4, 16)
        si = d.eu_to_si(cid, eu)
        assert si.shape == eu.shape and si.dtype == np.float64
        back = d.si_to_eu(cid, si)
        tol = 1e-12 * max(abs(lo), abs(hi), 1.0)
        assert np.max(np.abs(back - eu)) <= tol, cid
        conv = d.eu_conversion(cid)
        again = d.eu_to_si(cid, back)
        assert np.max(np.abs(again - si)) <= 1e-12 * max(np.max(np.abs(si)), abs(conv.offset), 1.0), cid


@settings(max_examples=300, derandomize=True, deadline=None)
@given(st.integers(0, 10_000), st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False))
def test_round_trip_property(pick, value):
    d = _d()
    numeric = [ch["channel_id"] for ch in d.channels() if _expected(ch) is not None]
    cid = numeric[pick % len(numeric)]
    back = d.si_to_eu(cid, d.eu_to_si(cid, value))
    assert math.isclose(float(back), value, rel_tol=1e-12, abs_tol=1e-9)


def test_known_points():
    d = _d()
    assert float(d.eu_to_si("AD.HP", 1000.0)) == pytest.approx(304.8, rel=1e-15)
    assert float(d.si_to_eu("AD.HP", 304.8)) == pytest.approx(1000.0, rel=1e-15)
    assert float(d.eu_to_si("ENG.N1.V", 100.0)) == pytest.approx(13270 * RPM, rel=1e-15)
    assert float(d.eu_to_si("ENG.N2.A", 50.0)) == pytest.approx(16810 * RPM / 2, rel=1e-15)
    assert float(d.eu_to_si("AD.SAT", 0.0)) == 273.15
    assert float(d.eu_to_si("AV.LRU.HEALTH.DFCC.TEMP", 212.0)) == pytest.approx(373.15, rel=1e-14)
    assert float(d.eu_to_si("ENG.WFM", 3600.0)) == pytest.approx(LB, rel=1e-15)
    assert float(d.si_to_eu("ENG.WFM", LB)) == pytest.approx(3600.0, rel=1e-15)
    assert float(d.eu_to_si("FCS.VOTED.NZ", 1.0)) == G0
    assert float(d.eu_to_si("AD.AOA", 180.0)) == pytest.approx(math.pi, rel=1e-15)
    assert float(d.eu_to_si("ENG.A8.V", 50.0)) == 0.5
    assert d.eu_conversion("ENG.N1.V").reference == "channel_reference.n1_100pct"


def test_scalars_lists_and_shapes():
    d = _d()
    s = d.eu_to_si("AD.HP", 1)
    assert isinstance(s, np.floating) and np.ndim(s) == 0
    assert d.eu_to_si("AD.HP", [1, 2, 3]).shape == (3,)
    cube = np.arange(24, dtype=np.int32).reshape(2, 3, 4)
    out = d.si_to_eu("ECS.CABIN_P.PRESS", cube)
    assert out.shape == (2, 3, 4) and out.dtype == np.float64
    assert np.array_equal(d.eu_to_si("FCS.MODE.LAW", [0, 1, 2]), [0.0, 1.0, 2.0])  # codes unchanged


def test_channels_without_a_numeric_si_form_raise():
    d = _d()
    for cid in ("AV.SW_CONFIG.DFCC", "DVR.VIDEO", "FTI.ALL"):
        with pytest.raises(EUConversionError, match="no numeric SI form"):
            d.eu_to_si(cid, 1.0)
    with pytest.raises(KeyError):
        d.eu_conversion("ENG.N9")


def test_percent_speed_without_a_reference_raises():
    """A % of rated speed channel whose parameter no constant references cannot be converted."""
    b = load_bundle(CONFIG)
    b.tables["constants"]["sets"]["channel_reference"]["jfs_rated_speed"].pop("eu_reference_for")
    d = Dictionary(compile_bundle(b))
    with pytest.raises(EUConversionError, match="no reference speed"):
        d.si_to_eu("SPS.JFS.SPEED", 1.0)


def test_jfs_reference_equals_the_m09_parameter():
    """One source of truth (0.1.2): 100 % SPS.JFS.SPEED is M09's jfs_rated_speed (A-W1.4-26)."""
    from phalanx.dictionary.params import load_params

    d = _d()
    m09 = load_params("M09")["jfs"]
    ref = d.param_set("channel_reference")
    assert ref.value("jfs_rated_speed") == pytest.approx(m09.value("jfs_rated_speed"), rel=1e-15)  # SI rad/s
    c = d.constants("channel_reference")["jfs_rated_speed"]
    assert (c["value"], c["units"]) == (60000, "rpm") and c["sweep"] == (40000, 80000)
    assert float(d.eu_to_si("SPS.JFS.SPEED", 100.0)) == pytest.approx(m09.value("jfs_rated_speed"), rel=1e-15)


def test_eu_reference_must_point_at_percent_speed_channels():
    b = load_bundle(CONFIG)
    b.tables["constants"]["sets"]["channel_reference"]["amagb_rated_speed"]["eu_reference_for"] = ["AD.HP"]
    with pytest.raises(CompileError, match=r"AD\.HP is altitude, not speed_percent"):
        compile_bundle(b)
    b = load_bundle(CONFIG)
    b.tables["constants"]["sets"]["channel_reference"]["amagb_rated_speed"]["eu_reference_for"] = ["ENG.N1"]
    with pytest.raises(CompileError, match=r"ENG\.N1\.V: two EU reference speeds"):
        compile_bundle(b)
