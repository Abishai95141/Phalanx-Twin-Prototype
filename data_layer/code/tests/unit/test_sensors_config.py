"""M12 configuration: the channel map and parameters against the dictionary and the W1 port catalogue."""

from __future__ import annotations

import copy

import pytest

from phalanx.core.module import ContractError
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_params, params_dir
from phalanx.dictionary.yamlio import load_yaml
from phalanx.sensors import kernel as K
from phalanx.sensors.config import build_sensor_config, load_catalogue

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


@pytest.fixture(scope="module")
def cmap():
    return load_yaml(params_dir("tejas") / "M12" / "channel_map.yaml")


@pytest.fixture(scope="module")
def cfg(d):
    return build_sensor_config(d)


def test_tejas_config_covers_the_brief_sensor_classes(cfg):
    """Every sensor class the W1.6 brief lists is configured: T5 2 x 4 harness, eddy-current N1, alternator
    N2, pressure transducers, LVDT/RVDT, RTD, vanes (2nd order), pitot-static with position error and
    pneumatic lag, TAT, capacitance gauging, flowmeter."""
    want = {
        "tc_t5",
        "shaft_speed",
        "ps3_transducer",
        "lvdt",
        "rtd_inlet",
        "vane_aoa",
        "vane_aoss",
        "static_pressure",
        "total_pressure",
        "tat_probe",
        "fuel_gauge",
        "fuel_flowmeter_main",
        "rate_gyro",
        "accelerometer",
    }
    assert want <= set(cfg.classes)
    for h in ("ENG.T5.HARNESS_A", "ENG.T5.HARNESS_B"):
        assert len(cfg.elements_of(h)) == 4
    vane_elements = {cfg.elements_of(f"AD.AOA_VANE_L.{x}").start for x in "ABCD"}
    assert len(vane_elements) == 1  # one physical vane, four pick-offs
    dyn = {
        cfg.classes[c]: int(cfg.el_i[cfg.elements_of(ch).start, K.IE_DYN])
        for c, ch in enumerate(cfg.channels)
    }
    assert dyn["tc_t5"] == K.DYN_LAG1_FLUX and dyn["vane_aoa"] == K.DYN_LAG2_EAS
    assert dyn["static_pressure"] == K.DYN_LAG1_PNEU and dyn["fuel_flowmeter_main"] == K.DYN_LAG1


def test_reading_units_match_dictionary(d, cfg):
    """The SI unit of every reading is the dictionary channel's eu_conversion SI unit (M13 converts with
    it)."""
    for cid, si in zip(cfg.channels, cfg.si_units, strict=True):
        assert d.eu_conversion(cid).si_units == si
        assert d.channel(cid)["role"] in ("lane", "single")


def test_inputs_are_catalogue_signals(cfg):
    cat = load_catalogue()
    for s in cfg.inputs:
        assert s.signal in cat
        assert s.unit == cat[s.signal]["unit"]
        assert s.port == s.signal.replace(".", "_")


@pytest.mark.parametrize(
    ("edit", "err"),
    [
        (lambda m: m["channels"]["ENG.N1.A"].update(input="eng.t5"), ContractError),  # wrong quantity
        (lambda m: m["channels"]["ENG.N1.A"].update(input="eng.nope"), ContractError),  # unknown signal
        (lambda m: m["channels"]["ENG.N1.A"].update(index=3), ContractError),  # index outside (e,)
        (
            lambda m: m["channels"].update({"ENG.NOPE.A": {"class": "shaft_speed", "input": "eng.n1"}}),
            KeyError,
        ),
        (lambda m: m["channels"]["FCS.RSA.P.A"].pop("axis"), ContractError),
        (lambda m: m["channels"]["ENG.N1.A"].update({"class": "nope"}), ContractError),
        (lambda m: m["classes"]["oil_pressure"]["map"].update(tau="no_such_param"), ContractError),
    ],
)
def test_bad_maps_are_rejected(d, cmap, edit, err):
    m = copy.deepcopy(dict(cmap))
    m["channels"] = {k: dict(v) for k, v in m["channels"].items()}
    m["classes"] = {
        k: {kk: (dict(vv) if isinstance(vv, dict) else vv) for kk, vv in v.items()}
        for k, v in m["classes"].items()
    }
    edit(m)
    with pytest.raises(err):
        build_sensor_config(d, channel_map=m)


def test_nonpositive_time_constant_rejected(d):
    p = load_params("M12")
    p["oil_pressure"] = p["oil_pressure"].replace(tau=0.0)
    with pytest.raises(ContractError):
        build_sensor_config(d, params=p, channels=("ENG.OIL_P",))


def test_index_notes_are_flagged(cmap):
    """A-W1.6-16: channels whose truth index map belongs to another module carry an index_note (first of each
    group), so W2.1 can find every assumed map."""
    noted = {spec["input"] for spec in cmap["channels"].values() if "index_note" in spec}
    assert {"util.fuel_mass", "util.bus_v", "fcs.surf_pos"} <= noted


def test_n_engines_shapes(d):
    """Engine-side inputs are vectorised over n_engines (W1 rule); the Tejas map reads engine index 0."""
    c2 = build_sensor_config(d, n_engines=2)
    assert next(s for s in c2.inputs if s.signal == "eng.n1").shape == (2,)
