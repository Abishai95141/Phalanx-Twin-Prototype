"""M01 semantic validation: units, ranges vs ADC bits and words, rate groups, producers, orphans (W0.3 A3,
A4).

Sample: the full Tejas dictionary; each negative test breaks one channel of a deep copy and asserts the
specific error, so every check is shown to fire (a check that cannot fail is a defect).
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import pytest

from phalanx.dictionary import CompileError, compile_bundle, load_bundle
from phalanx.dictionary.icd import fits_word
from phalanx.dictionary.schema import QUANTITIES
from phalanx.dictionary.units import check_unit

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"


@lru_cache(maxsize=1)
def _bundle():
    return load_bundle(CONFIG)


@lru_cache(maxsize=1)
def _content():
    return compile_bundle(_bundle().copy()).content


def _ch(b, sub, pid, cid):
    return b.sources[sub]["parameters"][pid]["channels"][cid]


def _fails(b, pattern):
    with pytest.raises(CompileError, match=pattern):
        compile_bundle(b)


# ---- A4: units ---------------------------------------------------------------------------------------------
def test_units_parse_and_match_quantity():
    for cid, ch in _content()["channels"].items():
        assert check_unit(ch["quantity"], ch["units"]) == [], cid
        assert (ch["quantity"] == "pressure") == ("pressure_ref" in ch), cid


@pytest.mark.parametrize(
    ("quantity", "units", "ok"),
    [
        ("temperature", "degC", True),
        ("pressure", "psi", True),
        ("angle", "deg", True),
        ("angle", "percent", False),  # dimensionless but not an angle unit
        ("pressure", "degC", False),  # wrong dimensionality
        ("specific_force", "g", False),  # pint 'g' is gram
        ("mass_flow", "lb/hr", True),
        ("voltage", "volts per fortnight", False),  # does not parse
    ],
)
def test_check_unit_table(quantity, units, ok):
    assert (check_unit(quantity, units) == []) is ok


def test_unparsable_unit_fails():
    b = _bundle().copy()
    ch = _ch(b, "engine.yaml", "ENG.T1", "ENG.T1.V")
    ch["units"] = "degrees-celsius-ish"
    ch["prov"]["units"] = "R-UNIT-CHOICE"
    _fails(b, "does not parse in pint")


def test_unit_quantity_mismatch_fails():
    b = _bundle().copy()
    ch = _ch(b, "engine.yaml", "ENG.PS3", "ENG.PS3.V")
    ch["units"] = "degC"
    ch["prov"]["units"] = "R-UNIT-CHOICE"
    _fails(b, "dimensionality")


def test_pressure_needs_reference():
    b = _bundle().copy()
    del _ch(b, "engine.yaml", "ENG.PS3", "ENG.PS3.V")["pressure_ref"]
    _fails(b, "pressure_ref")


def test_every_quantity_has_a_reference_unit_that_parses():
    for q, (ref, allowed) in QUANTITIES.items():
        assert check_unit(q, ref) == [] or ref not in allowed, q
        for a in allowed:
            assert check_unit(q, a) == [], (q, a)


# ---- A4: range, LSB, ADC bits, word fit --------------------------------------------------------------------
def test_range_lsb_word_consistency():
    n = 0
    for cid, ch in _content()["channels"].items():
        enc = ch["encoding"]
        if enc["type"] in ("bnr", "ubnr"):
            n += 1
            r = ch["range"]
            assert r["min"] < r["max"], cid
            assert fits_word(r["min"], r["max"], ch["recorder_lsb"], enc["type"], enc["word_bits"]), cid
            assert ch["calibration"]["coefficients"] == [0.0, ch["recorder_lsb"]], cid
    assert n > 150


def test_adc_bits_vs_native_step():
    n = 0
    for cid, ch in _content()["channels"].items():
        if ch["adc_bits"] is not None:
            n += 1
            span = ch["range"]["max"] - ch["range"]["min"]
            assert span / ch["native_step"] <= 2 ** ch["adc_bits"] * (1 + 1e-9), cid
            assert ch["adc_bits"] >= 12 and ch["signal"] == "analog", cid
            step = ch.get("converter_step", ch["native_step"])  # FADEC lanes: the converter (R-FADEC-ADC)
            assert ch["adc_bits"] == max(12, math.ceil(math.log2(span / step))), cid
    assert n > 100


def test_range_overflowing_the_word_fails():
    b = _bundle().copy()
    ch = _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.V")
    ch["recorder_lsb"] = ch["calibration"]["coefficients"][1] = 0.001  # 115 / 0.001 > 32767
    _fails(b, "does not fit a 16-bit")


def test_adc_bits_too_few_fails():
    b = _bundle().copy()
    ch = _ch(b, "engine.yaml", "ENG.PS3", "ENG.PS3.A")
    ch["adc_bits"] = 8  # 500 psi / 0.5 psi = 1000 steps > 256
    _fails(b, "needs more than 8 ADC bits")


def test_calibration_gain_must_equal_lsb():
    b = _bundle().copy()
    _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.V")["calibration"]["coefficients"][1] = 0.0625
    _fails(b, "calibration gain")


def test_inverted_range_fails():
    b = _bundle().copy()
    ch = _ch(b, "engine.yaml", "ENG.T1", "ENG.T1.V")
    ch["range"] = {"min": 149, "max": -54}
    _fails(b, "is not below max")


def test_overlapping_bitfield_fails():
    b = _bundle().copy()
    ch = _ch(b, "engine.yaml", "ENG.FLAMEOUT", "ENG.FLAMEOUT")
    ch["encoding"]["fields"][1]["lsb_bit"] = 0
    _fails(b, "overlaps")


# ---- A4: rate groups ---------------------------------------------------------------------------------------
def test_rate_groups_exist_and_serve_their_stage():
    c = _content()
    groups = c["rate_groups"]
    for cid, ch in c["channels"].items():
        for stage in ("acquisition", "bus", "producer"):
            g = ch["rates"][stage]
            if g is not None:
                assert stage in groups[g]["stages"], (cid, stage, g)
        for s in ch["sinks"]:
            if s["group"] is not None:
                assert "record" in groups[s["group"]]["stages"], (cid, s)


def test_unknown_rate_group_fails():
    b = _bundle().copy()
    _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.V")["rates"]["bus"] = "AV33"
    _fails(b, "unknown bus rate group AV33")


def test_rate_group_in_wrong_stage_fails():
    b = _bundle().copy()
    ch = _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.V")
    ch["rates"]["acquisition"] = "CDR4"
    ch["prov"]["rates.acquisition"] = "R-RATE-CDR"
    _fails(b, "does not serve the acquisition stage")


def test_nominal_rate_outside_band_fails():
    b = _bundle().copy()
    b.tables["rate_groups"]["groups"]["FADEC-INT"]["rate_hz"] = 80
    _fails(b, "outside its band")


# ---- A3: producers and orphans -----------------------------------------------------------------------------
def test_every_channel_has_producer():
    c = _content()
    for cid, ch in c["channels"].items():
        assert ch["source_lru"] in c["lrus"] and ch["acq_lru"] in c["lrus"], cid


def test_no_orphan_channels():
    c = _content()
    for cid, ch in c["channels"].items():
        assert ch["sinks"], cid
        for s in ch["sinks"]:
            if s["sink"] == "INTERNAL":
                assert s["consumer"] in c["lrus"], cid
            else:
                assert s["group"] is not None, cid


def test_orphan_channel_fails():
    b = _bundle().copy()
    _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.V")["sinks"] = []
    _fails(b, "orphan channel")


def test_unknown_producer_fails():
    b = _bundle().copy()
    _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.V")["source_lru"] = "FLUX_CAPACITOR"
    _fails(b, "unknown source_lru FLUX_CAPACITOR")


def test_internal_sink_needs_consumer():
    b = _bundle().copy()
    del _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.A")["sinks"][0]["consumer"]
    _fails(b, "INTERNAL sink without a known consumer")


def test_voted_output_inputs_must_exist():
    b = _bundle().copy()
    _ch(b, "engine.yaml", "ENG.N1", "ENG.N1.V")["inputs"] = ["ENG.N1.Z"]
    _fails(b, "input ENG.N1.Z is not a channel")


# ---- constants provenance (E0 fix 3) -----------------------------------------------------------------------
def _with_constant(entry):
    b = _bundle().copy()
    b.tables["constants"]["sets"]["probe_set"] = {"probe_value": entry}
    return b


_ASSUMED = {
    "value": 1.5,
    "units": "s",
    "description": "probe constant",
    "evidence": {"tag": "ASSUMPTION", "source": "test"},
}


def test_assumption_constant_without_sweep_or_rule_fails():
    _fails(
        _with_constant(dict(_ASSUMED)), r"probe_set\.probe_value: ASSUMPTION constant without a sweep range"
    )
    _fails(_with_constant(dict(_ASSUMED)), r"probe_set\.probe_value: ASSUMPTION constant without a prov rule")


def test_assumption_constant_sweep_must_bracket_value():
    entry = {**_ASSUMED, "sweep": [2.0, 3.0], "prov": "R-LSB-BNR"}
    _fails(_with_constant(entry), r"sweep \[2\.0, 3\.0\] does not bracket the value 1\.5")


def test_assumption_constant_needs_an_assumption_rule_with_a_row():
    for prov in ("R-COMPONENTS", "inv"):  # a DIRECT rule / the inventory give no assumptions.md row
        entry = {**_ASSUMED, "sweep": [1.0, 2.0], "prov": prov}
        _fails(_with_constant(entry), rf"prov {prov} is not an ASSUMPTION/PROXY rule with an assumption_id")


def test_proxy_constant_needs_a_p_rule():
    entry = {**_ASSUMED, "evidence": {"tag": "DIRECT", "source": "t"}, "proxy": True}
    entry.update(sweep=[1.0, 2.0], prov="R-LSB-BNR")
    _fails(_with_constant(entry), r"PROXY constant must cite a P- rule, not R-LSB-BNR")


def test_well_formed_assumption_constant_compiles_and_is_registered():
    entry = {**_ASSUMED, "sweep": [1.0, 2.0], "prov": "R-LSB-BNR"}
    c = compile_bundle(_with_constant(entry)).content
    row = next(a for a in c["assumption_register"] if a["rule"] == "R-LSB-BNR")
    assert row["affects_constants"] == ["probe_set.probe_value"]


def test_shipped_constants_pass_the_provenance_rule():
    """Every shipped constant has a source; any ASSUMPTION one has a sweep and a registered rule."""
    c = _content()
    for set_name, entries in c["constants"].items():
        for cname, e in entries.items():
            assert e["evidence"]["source"].strip(), (set_name, cname)
            if "ASSUMPTION" in e["evidence"]["tag"]:
                assert e["sweep"][0] <= e["value"] <= e["sweep"][1]
                assert c["rules"][e["prov"]]["assumption_id"]


# ---- rule families justify only their own fields (E0 fix 2) ------------------------------------------------
def test_range_rule_cannot_justify_an_lsb_or_a_unit():
    b = _bundle().copy()
    ch = _ch(b, "fuel.yaml", "FUEL.TOTAL", "FUEL.TOTAL.TOTAL")
    ch["prov"]["recorder_lsb"] = "R-RANGE-NOTPUBLIC"
    _fails(b, r"FUEL\.TOTAL\.TOTAL: rule R-RANGE-NOTPUBLIC cannot justify field 'recorder_lsb'")
    b = _bundle().copy()
    _ch(b, "fuel.yaml", "FUEL.TOTAL", "FUEL.TOTAL.TOTAL")["prov"]["units"] = "R-RANGE-FUEL-TOTAL"
    _fails(b, r"rule R-RANGE-FUEL-TOTAL cannot justify field 'units'")


def test_bnr_lsb_rule_needs_a_bnr_word():
    b = _bundle().copy()
    ch = _ch(b, "secondary_power.yaml", "SPS.JFS.OIL_QTY", "SPS.JFS.OIL_QTY")
    assert ch["encoding"]["type"] == "float64" and ch["recorder_lsb"] is None
    ch["recorder_lsb"] = ch["native_step"]
    ch["prov"]["recorder_lsb"] = "R-LSB-BNR"
    _fails(b, r"SPS\.JFS\.OIL_QTY: recorder LSB cites R-LSB-BNR but the channel is not a BNR word")


def test_e0_provenance_slips_are_fixed():
    c = _content()
    ch = c["channels"]
    total = ch["FUEL.TOTAL.TOTAL"]
    assert total["prov"]["range"] == "R-RANGE-FUEL-TOTAL" and total["range"] == {"min": 0, "max": 6000}
    assert c["rules"]["R-RANGE-FUEL-TOTAL"]["tag"] == "ASSUMPTION"
    fom = ch["NAV.GPS.STATUS.FOM"]
    assert fom["encoding"]["type"] == "enum" and fom["encoding"]["code_table"] == "gps_fom"
    assert fom["recorder_lsb"] is None and fom["prov"]["units"] == "inv"
    assert c["code_tables"]["gps_fom"]["synthetic"] is True
    oil = ch["SPS.JFS.OIL_QTY"]
    assert oil["recorder_lsb"] is None and "recorder_lsb" not in oil["prov"]
    assert oil["native_step"] == 2.0**-9 and oil["prov"]["native_step"] == "R-LSB-BNR"
    cabin = ch["ECS.CABIN_P.CABIN_ALT"]
    assert cabin["encoding"] == {"type": "bnr", "word_bits": 16, "words": 1}
    assert cabin["recorder_lsb"] == 2.0  # 16-bit two's complement over -2,000..60,000 ft
    # R-LSB-BNR's sweep reaches the MSW-only LSB of two-word quantities (NAV.INS.ALT: 2^-15 ft x 65536 = 2 ft)
    assert "x1-x65536" in c["rules"]["R-LSB-BNR"]["sweep"]
    assert ch["NAV.INS.ALT"]["recorder_lsb"] * 65536 == 2.0


# ---- dictionary 0.1.2 batch --------------------------------------------------------------------------------
def test_fadec_lanes_carry_the_fadec_converter_step():
    """FADEC lanes (0.1.3): native_step = the FADEC converter step span / 2^14 (R-FADEC-ADC), finer than the
    recorded word LSB over the whole 12-16 bit sweep; M13 quantises the lanes there with its lane noise in EU
    (W2.2). No Tejas channel carries a separate converter_step any more (the field stays in the schema)."""
    c = _content()
    lanes = [ch for ch in c["channels"].values() if ch["role"] == "lane" and ch["acq_lru"] == "FADEC"]
    assert len(lanes) == 12  # A8, N1, N2, PLA, PS3, T1 x lanes A/B
    for ch in lanes:
        span = ch["range"]["max"] - ch["range"]["min"]
        word_lsb = c["channels"][f"{ch['measurand_id']}.V"]["recorder_lsb"]
        assert ch["native_step"] == span / 2**14 and ch["prov"]["native_step"] == "R-FADEC-ADC"
        if ch["signal"] == "analog":
            assert ch["adc_bits"] == 14 and ch["prov"]["adc_bits"] == "R-FADEC-ADC"
        assert span / 2**12 < word_lsb, ch["channel_id"]  # finer than the bus word even at 12 bits
    assert sum("converter_step" in ch for ch in c["channels"].values()) == 0


def test_converter_step_must_be_finer_than_the_native_step():
    b = _bundle().copy()
    ch = _ch(b, "engine.yaml", "ENG.PS3", "ENG.PS3.A")
    ch["converter_step"] = 1.0  # coarser than the native step (the 0.0305 psi FADEC converter step)
    _fails(b, r"ENG\.PS3\.A: converter_step needs a finite lane channel and must not exceed its native step")


def test_e0b_ad_port_pressures():
    """AD.DPA/DPB: the DIRECT 35-1500 mbar transducer range is kept, read as absolute port pressure."""
    c = _content()
    chans = [ch for ch in c["channels"].values() if ch["param_id"] in ("AD.DPA", "AD.DPB")]
    assert len(chans) == 10  # 4 ADC lanes + V, twice
    for ch in chans:
        assert ch["pressure_ref"] == "absolute" and ch["range"] == {"min": 35, "max": 1500}
        assert ch["prov"]["quantity"] == "R-AD-PORT-PRESSURE" and ch["prov"]["range"] == "inv"
    assert c["rules"]["R-AD-PORT-PRESSURE"]["tag"] == "ASSUMPTION"
