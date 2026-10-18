"""M08 ports, bindings, EU<->SI conversions and parameter configuration (W1.3b; A7 interface side, A6 config).

No sampled data: structural checks over the published port set (n_engines 1 and 2) and the parameter file.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.module import ContractError
from phalanx.core.time import ClockDomain
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.yamlio import load_yaml
from phalanx.fadec import Fadec, FadecConfig, load_fadec_params
from phalanx.fadec.codes import (
    B_FLAMEOUT,
    B_N2_OVERSPEED,
    B_OVERTEMP,
    B_STALL,
    FAULT_CODES,
    IGN_AB,
    IGN_MAIN,
    NS,
    SENSORS,
    V_SUBSTITUTED,
    active_codes,
    code_word,
    decode_active_limiter,
    recorded_words,
)
from phalanx.fadec.layout import C_LAYOUT, LOOP_GAINS, P_LAYOUT, P_NAMES
from phalanx.fadec.ports import (
    DEFAULT_CLOCK,
    LANE_PORTS,
    LANE_SLOT,
    OUTPUT_NAMES,
    PREFIX,
    RECORDED,
    RECORDED_MISSING,
    capacity,
    ports,
)

pytestmark = pytest.mark.unit
REPO = Path(__file__).resolve().parents[2]
CAT = load_yaml(REPO / "configs" / "interfaces" / "w1_ports.yaml")


@pytest.mark.parametrize("n_engines", [1, 2])
@pytest.mark.parametrize("autothrottle", [False, True])
def test_outputs_and_truth_bindings_match_the_catalogue(n_engines, autothrottle):
    ins, outs, bindings = ports(n_engines, autothrottle=autothrottle)
    cat = CAT["modules"]["M08"]["out"]
    assert PREFIX == "fadec"
    cat_outs = [p for p in outs if p.name not in RECORDED]
    assert {f"{PREFIX}.{p.name}" for p in cat_outs} == set(cat)  # the catalogue + RECORDED, no variants
    assert [p.name for p in outs if p.name in RECORDED] == list(RECORDED)
    for p in outs:
        if p.name in RECORDED:
            assert p.shape == (n_engines,)
            continue
        spec = cat[f"{PREFIX}.{p.name}"]
        assert np.dtype(p.dtype).name == spec["dtype"]
        assert len(p.shape) == len(spec["shape"]) and p.shape[0] == n_engines
    assert dict(zip([p.name for p in outs], [p.shape for p in outs], strict=True))["validation_state"] == (
        n_engines,
        NS,
    )
    assert set(bindings) == {p.name for p in ins}  # every input is bound
    all_sig = {k: v for m in CAT["modules"].values() for k, v in m["out"].items()}
    for p in ins:
        sig = bindings[p.name]
        if sig.startswith("lane."):
            continue
        if sig.startswith("avio."):  # an observation-layer avionics output (W2.2: the P0 altitude signal)
            from phalanx.sensors.avionics.ports import ports as avionics_ports

            src = {q.name: q for q in avionics_ports(n_engines)[1]}[sig.split(".", 1)[1]]
            assert (src.unit, src.dtype, src.shape, src.rate) == (p.unit, p.dtype, p.shape, p.rate)
            continue
        spec = all_sig[sig]
        assert np.dtype(p.dtype).name == spec["dtype"] and len(p.shape) == len(spec["shape"])
        if autothrottle is False:
            assert not spec.get("proxy_only", False)


def test_lane_bindings_resolve_to_dictionary_channels_with_matching_si_units():
    d = load_dictionary()
    ins, _, bindings = ports(2)
    lane_ins = [p for p in ins if bindings[p.name].startswith("lane.")]
    assert len(lane_ins) == len(LANE_PORTS) == 12
    for p in lane_ins:
        cid = bindings[p.name].split(".", 1)[1]
        conv = d.eu_conversion(cid)
        assert d.channel(cid)["acq_lru"] == "FADEC"
        u = d.channel(cid)
        assert u is not None
        from phalanx.core.units import units_compatible

        assert units_compatible(p.unit, "1" if conv.si_units in ("", "1") else conv.si_units)
        assert p.shape == (capacity(), 2)


def test_single_engine_lane_ports_are_exactly_m13_lane_buffers_on_the_shared_clock():
    """AD-42: M08 binds `lane.<channel_id>` to M13's `LaneAcquisition` value ports - same unit, shape and
    clock domain (M08's default clock *is* M13's FADEC acquisition clock). Every lane, ENG.AB_LIT included
    since W2.2 (the M12 UV flame detector through the M13 word path)."""
    from phalanx.acquisition.config import acquisition_clock
    from phalanx.acquisition.ports import lane_modules

    assert DEFAULT_CLOCK == acquisition_clock("FADEC", 60.0)
    m13 = lane_modules(1)["FADEC"]
    m13_out = {p.name: p for p in m13.ports_out}
    m13_lanes = m13.lane_bindings()
    ins, _, bindings = ports(1)
    missing = []
    for p in ins:
        sig = bindings[p.name]
        if not sig.startswith("lane."):
            continue
        if sig not in m13_lanes:
            missing.append(sig)
            continue
        q = m13_out[m13_lanes[sig]]
        assert (p.unit, p.dtype, p.shape, p.rate) == (q.unit, q.dtype, q.shape, q.rate), sig
    assert missing == []


def test_recorded_channels_cover_the_fadec_computed_dictionary_channels():
    d = load_dictionary()
    want = {
        "ENG.N1.V", "ENG.N2.V", "ENG.PS3.V", "ENG.T1.V", "ENG.PLA.V", "ENG.A8.V", "ENG.T5", "ENG.IGN",
        "ENG.FLAMEOUT", "ENG.LIMIT_FLAGS", "ENG.FADEC_STATUS", "ENG.FAULT_CODES",
    }  # fmt: skip
    assert set(RECORDED.values()) | set(RECORDED_MISSING) == want
    assert not set(RECORDED.values()) & set(RECORDED_MISSING)
    for cid in want:
        assert d.channel(cid)["signal"] == "computed"


def test_recorded_words_follow_the_dictionary_bit_layouts():
    faults = np.array([0, 1 << B_FLAMEOUT, (1 << B_OVERTEMP) | (1 << B_N2_OVERSPEED) | (1 << B_STALL) | 1])
    ign = np.array([IGN_AB, IGN_MAIN, 0])
    vs = np.zeros((3, NS), np.int64)
    vs[2, 4] = V_SUBSTITUTED
    w = recorded_words(ign, faults, vs)
    assert list(w["ENG.IGN"]) == [0, 1, 0]  # AB igniter alone is not IGNITION_ON
    assert list(w["ENG.FLAMEOUT"]) == [0, 0b11, 0]  # detected + auto-relight igniters on
    assert list(w["ENG.LIMIT_FLAGS"]) == [0, 0, 0b110]  # N2 overspeed bit 1, T5 over-temp bit 2
    assert list(w["ENG.FADEC_STATUS"]) == [1, 1, 1 | 16]  # channel A in control; substitution active
    # code word: exceedance (7xx) before function (5xx) before sensor (0xx) codes; 0 = none (unified codes:
    # flameout ENG-502, stall ENG-501, N1 lane A ENG-001; test_fadec_codes.py ties them to the dictionary)
    assert list(w["ENG.FAULT_CODES"]) == [0, 502, 701]
    assert int(code_word(1 << B_STALL | 1)) == 501 and int(code_word(1)) == 1


def test_p0_is_the_air_data_on_tejas_and_the_replayed_static_pressure_in_proxy_mode():
    """W2.2 (A-W1.3b-11 PROXY retired for Tejas): the Tejas FADEC reads P0 from the avionics ADC's voted,
    corrected static pressure (AD.PS.V); the proxy chain (A/T mode, no aircraft air data) keeps the replayed
    env.p_s; nothing else is a truth binding."""
    _, _, tejas = ports(1)
    assert {k: v for k, v in tejas.items() if not v.startswith("lane.")} == {
        "pla": "pilot.pla",
        "p0": "avio.p0_from_hp",
    }
    _, _, proxy = ports(1, autothrottle=True)
    assert {k: v for k, v in proxy.items() if not v.startswith("lane.")} == {
        "pla": "pilot.pla",
        "p0": "env.p_s",
        "at_engage": "pilot.at_engage",
        "at_n1_cmd": "pilot.at_n1_cmd",
    }
    assert ports(2, p0_source="env.p_s")[2]["p0"] == "env.p_s"
    with pytest.raises(ValueError, match="p0_source"):
        ports(1, p0_source="env.t_s")


def test_capacity_follows_the_clock():
    assert capacity(ClockDomain("FADEC", 60)) == 1
    assert capacity(ClockDomain("FADEC", 67, offset_ppm=900)) == 1
    assert capacity(ClockDomain("FAST", 300)) == 2  # a clock faster than the truth step needs 2 slots


def test_module_ports_equal_published_ports_and_reject_bad_initial_values():
    params = load_fadec_params()
    m = Fadec("fadec", params, n_engines=2, autothrottle=True)
    ins, outs, bindings = ports(2, autothrottle=True)
    assert m.ports_in == ins and m.ports_out == outs and m.bindings == bindings
    assert tuple(p.name for p in m.ports_out[: len(OUTPUT_NAMES)]) == OUTPUT_NAMES
    with pytest.raises(ContractError):
        Fadec("fadec", params, n_engines=2, initial_wf=[0.1])


def test_thresholds_are_the_dictionary_eu_values_converted_to_si():
    """Explicit EU->SI check (coordinator rule): validator spans equal the dictionary conversions."""
    d = load_dictionary()
    cfg = FadecConfig.build(load_fadec_params())
    tb = cfg.tables
    assert tb.v_hi[0] == pytest.approx(float(d.eu_to_si("ENG.N1.A", 115.0)), rel=1e-12)
    assert tb.v_hi[1] == pytest.approx(float(d.eu_to_si("ENG.N2.A", 110.0)), rel=1e-12)
    assert tb.v_lo[2] == pytest.approx(float(d.eu_to_si("ENG.T1.A", -54.0)), rel=1e-12)
    assert tb.v_hi[3] == pytest.approx(float(d.eu_to_si("ENG.T25", 280.0)), rel=1e-12)
    assert tb.v_hi[4] == pytest.approx(float(d.eu_to_si("ENG.PS3.A", 500.0)), rel=1e-12)
    assert tb.v_hi[5] == pytest.approx(float(d.eu_to_si("ENG.T5.HARNESS_A", 871.0)), rel=1e-12)
    # and back: SI -> EU of the PS3 maximum limiter is the YAML value (476 psia)
    p = cfg.p
    assert float(d.si_to_eu("ENG.PS3.A", p[P_LAYOUT.index["ps3_max"]])) == pytest.approx(476.0, rel=1e-12)
    assert float(d.si_to_eu("ENG.PLA.A", p[P_LAYOUT.index["pla_irp"]])) == pytest.approx(87.0, rel=1e-12)


def test_parameter_vector_and_config_are_complete_and_in_si():
    params = load_fadec_params()
    cfg = FadecConfig.build(params)
    assert set(LOOP_GAINS) <= set(P_NAMES)
    assert cfg.p.size == len(P_NAMES) and not cfg.p.flags.writeable
    pi = P_LAYOUT.index
    assert cfg.p[pi["pla_irp"]] == pytest.approx(np.deg2rad(87.0))
    assert cfg.p[pi["wf_min"]] == pytest.approx(115.0 / 3600.0)
    assert cfg.p[pi["n2_ref"]] == pytest.approx(16810 * 2 * np.pi / 60)
    assert cfg.dt == pytest.approx(1 / 60)
    ci = C_LAYOUT.index
    assert cfg.cfg[ci["hs_window"]] == 60 and cfg.cfg[ci["hs_timeout"]] == 2100
    assert cfg.cfg[ci["ab_nolight"]] == 150 and cfg.cfg[ci["n_an"]] == 30 and cfg.cfg[ci["n_hold"]] == 6
    # every parameter carries provenance; ASSUMPTION entries were sweep-checked by the loader
    for k in params:
        assert params[k].source.strip()
    # at a 50 Hz FADEC the same seconds give other frame counts
    c50 = FadecConfig.build(params, ClockDomain("FADEC", 50))
    assert c50.cfg[ci["hs_window"]] == 50 and c50.cfg[ci["ab_nolight"]] == 125
    assert c50.dt == pytest.approx(float(Fraction(1, 50)))


def test_persistence_failure_mode_scales_the_counts():
    params = load_fadec_params()
    nominal = FadecConfig.build(params)
    slow = FadecConfig.build(params.replace(vm_persist_scale=10.0))
    ci = C_LAYOUT.index
    for k in ("n_range", "n_rate", "n_xc", "n_an"):
        assert slow.cfg[ci[k]] == 10 * nominal.cfg[ci[k]]


def test_config_rejects_bad_tables_and_laws():
    params = load_fadec_params()
    x = np.array(params.value("ru_ref_x"))
    with pytest.raises(ValueError, match="strictly increasing"):
        FadecConfig.build(params.replace(ru_ref_x=x[::-1].copy()))
    with pytest.raises(ValueError, match="fuel_law"):
        FadecConfig.build(params.replace(fuel_law=2))
    with pytest.raises(ValueError, match="lanes_per_sensor"):
        FadecConfig.build(params, lanes_per_sensor=(2, 2, 2, 3, 2, 2))


def test_code_tables_are_consistent():
    assert len(SENSORS) == NS == 6
    codes = [f.code for f in FAULT_CODES]
    assert len(set(codes)) == len(codes)
    assert all(c.startswith("ENG-") and len(c) == 7 for c in codes)
    assert active_codes(0) == [] and active_codes(1 << 1) == ["ENG-003"]
    assert decode_active_limiter(2 + 16) == ("N1_ISOCHRONOUS", True)
    assert LANE_SLOT["ab_lit"] == 12
    assert sorted(LANE_SLOT.values())[:11] == [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11]


def test_declared_events_are_what_the_module_emits():
    """AD-44 declaration (the kinds are an interface change request, not yet in w1_events.yaml): every fault
    bit maps to a declared kind and the emitted payload carries exactly the declared keys."""
    from phalanx.fadec.module import Fadec as _F
    from phalanx.fadec.ports import EVENTS_OUT, MODULE_IDS

    assert MODULE_IDS == ("M08",)
    assert {f.kind for f in FAULT_CODES} <= set(EVENTS_OUT)
    m = _F("fadec", load_fadec_params(), event_target="bit")

    class _Sched:  # one step with one frame (absolute index 4) at 123 ns (core.sampling.StepSamples fields)
        first = 4
        times = np.array([123], dtype=np.int64)
        next_index = 5
        count = np.array([1], dtype=np.int64)
        first_of_step = np.array([4], dtype=np.int64)

    evs = m.fault_events(np.array([0]), np.array([(1 << 1) | (1 << 32)]), 1000, _Sched())
    assert {e.kind for e in evs} == {"fadec.fault", "fadec.caution"}
    for e in evs:
        assert set(e.payload) == set(EVENTS_OUT[e.kind])
        assert e.payload["frame"] == 4 and e.payload["t_frame_ns"] == 123


def test_ports_submodule_is_not_shadowed_by_a_reexport():
    """W2.1 F6 (E1 report §5): after `import phalanx.fadec`, `phalanx.fadec.ports` is the submodule (the
    package used to re-export the `ports()` function under the submodule's name, shadowing it), and the
    catalogue accessor is `phalanx.fadec.ports.ports(n_engines)` like every other package. The stale "NOT YET
    CATALOGUED" comment is gone (the kinds are catalogued in configs/interfaces/w1_events.yaml)."""
    import importlib
    import inspect

    import phalanx.fadec as pkg

    assert inspect.ismodule(pkg.ports)
    assert pkg.ports is importlib.import_module("phalanx.fadec.ports")
    _ins, outs, bindings = pkg.ports.ports(1)
    assert pkg.PREFIX == pkg.ports.PREFIX == "fadec"
    assert bindings["pla"] == "pilot.pla" and outs[0].name == "wf_cmd"
    assert "NOT YET CATALOGUED" not in inspect.getsource(pkg.ports)
