"""Unit tests of the battery input structure, its configuration check and the DASHlink adapter guards."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.validation.battery import BatteryConfig
from phalanx.validation.dashlink import corrections, delta_static, flight_date, load_mat, load_record
from phalanx.validation.flightdata import DASHLINK_UNITS, FlightRecord

pytestmark = pytest.mark.unit


def _rec(n: int = 50, **kw) -> FlightRecord:
    args = {
        "flight_id": "f",
        "rate_hz": 4.0,
        "outputs": {f: np.full((4, n), 50.0) for f in ("N1", "N2", "EGT", "FF")},
        "pla": np.full((4, n), 40.0),
        "theta": np.ones(n),
        "delta": np.ones(n),
        "phase": np.full(n, 5),
        "units": DASHLINK_UNITS,
    }
    args.update(kw)
    return FlightRecord(**args)


def test_record_is_validated_and_read_only():
    r = _rec()
    assert r.n == 50 and r.n_units == 4
    with pytest.raises(ValueError):
        r.outputs["N1"][0, 0] = 1.0
    with pytest.raises(TypeError):
        r.outputs["N9"] = np.zeros((4, 50))  # type: ignore[index]
    with pytest.raises(ValueError, match="non-finite"):
        _rec(outputs={f: np.full((4, 50), np.nan) for f in ("N1", "N2", "EGT", "FF")})
    with pytest.raises(ValueError, match="shape"):
        _rec(pla=np.zeros((4, 49)))
    with pytest.raises(ValueError, match="samples"):
        _rec(phase=np.zeros(49))


def test_replace_outputs_keeps_inputs_and_copies():
    r = _rec()
    src = {f: np.full((4, 50), 60.0) for f in r.outputs}
    s = r.replace_outputs(src, control="x")
    src["N1"][0, 0] = -1.0
    assert s.outputs["N1"][0, 0] == 60.0  # defensive copy
    np.testing.assert_array_equal(s.pla, r.pla)
    assert s.meta["control"] == "x" and s.flight_id == r.flight_id


def test_config_rejects_mismatched_records():
    cfg = BatteryConfig()
    cfg.check(_rec())
    with pytest.raises(ValueError, match="unit"):
        cfg.check(_rec(units={**DASHLINK_UNITS, "EGT": "K"}))
    with pytest.raises(ValueError, match="rate"):
        cfg.check(_rec(rate_hz=8.0))
    with pytest.raises(ValueError, match="missing"):
        cfg.check(_rec(outputs={f: np.full((4, 50), 50.0) for f in ("N1", "N2", "EGT")}))
    with pytest.raises(ValueError, match="positions"):
        cfg.check(
            _rec(
                outputs={f: np.full((2, 50), 50.0) for f in ("N1", "N2", "EGT", "FF")}, pla=np.zeros((2, 50))
            )
        )
    assert cfg.channel_names[:2] == ("N1_1", "N1_2") and len(cfg.pair_names) == 120


def test_kelvin_offset_follows_declared_unit():
    assert BatteryConfig().kelvin_offset == 273.15
    assert BatteryConfig(units={**DASHLINK_UNITS, "EGT": "K"}).kelvin_offset == 0.0
    with pytest.raises(ValueError):
        _ = BatteryConfig(units={**DASHLINK_UNITS, "EGT": "degF"}).kelvin_offset


def test_reserved_archive2_is_refused_before_any_read(tmp_path):
    """Tail 687 archive 2 is reserved for the AD-33 gate: the adapter refuses raw2/ paths without opening
    them."""
    p = tmp_path / "dashlink_tail687" / "raw2" / "mat" / "687200109141013.mat"
    with pytest.raises(PermissionError, match="reserved"):
        load_mat(p)
    with pytest.raises(PermissionError, match="reserved"):
        load_record(p)


def test_isa_corrections():
    assert delta_static(np.array([0.0]))[0] == pytest.approx(1.0)
    assert delta_static(np.array([36089.0]))[0] == pytest.approx(0.2234, abs=1e-3)  # ISA tropopause
    th, de = corrections(np.array([0.0]), np.array([0.0]), np.array([15.0]))
    assert th[0] == pytest.approx(1.0) and de[0] == pytest.approx(1.0)
    assert flight_date("652200306260654.mat") == "2003-06-26T06:54"
    assert flight_date("notaflight.mat") is None
