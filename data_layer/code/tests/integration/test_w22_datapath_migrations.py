"""W2.2 item 3: the dictionary 0.1.2 migrations on the data path (M16, M15/M17, M13).

- **M16** writes the M01 TMATS with the dictionary's recorder setup (``generate_tmats(recording=True)``,
  A-W0.3-44) instead of overlaying ``R-1\\EV`` / ``R-1\\IDX`` itself (A-W1.7-12 replaced).
- **M15/M17** read the code-word layout from ``bit_code_format.word_layout`` (A-W0.3-43; A-W1.7-6 replaced),
  each independently (the decoder never imports the encoder's layout).
- **M13** quantises the FADEC lanes at the FADEC converter step with the lane noise in EU. Dictionary 0.1.2
  carried that step as ``converter_step``; 0.1.3 made it the lanes' ``native_step`` (R-FADEC-ADC) and M13's
  lane quantiser, noise and ceilings did not move (tested against a 0.1.2 view of the dictionary).

The migration note promises the recording bytes do not change. The goldens below were captured from the W1.7
full-path fixture **before** any W2.2 edit (main edcb6f4): the .c10 bytes, the setup record, and a digest of
the decoded records' contract-0.1.0 columns. The records digest must also survive contract 0.2.0 (additive:
same record ids and values).

W2.2 phase B then changed the recording on purpose: with FTI fitted, the FTI words no producer populates are
spare frame slots the setup record does not describe, so the ground emits no zero-fill records for them. The
pre-W2.2 goldens are checked on a TEST VIEW of the writer that describes every FTI word
(``describe_all_pcm``), and the phase-B recording is derived from that view: same packets after the setup
record, same records minus exactly the spare slots' zero fill.

Sample: the W1.7 fixture sortie (6 s, every recorded-bus channel; 45,908 decoded records with every FTI word
described, 45,140 without the spare slots), run once per writer view (n = 2 runs): the smallest run that
carries every message type, every code-word channel (ENG.FAULT_CODES, FCS.BIT.LOG: 150 records with prefix
indices 0 and 1) and the recorder events.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from contextlib import contextmanager

import numpy as np
import pytest
from test_bus_cir_fixture import make_cir
from test_decoder_full_path import T0, T1, _run

from phalanx.acquisition.config import build_acquisition_config
from phalanx.bus.icd import BusIcd, CodeWordLayout
from phalanx.bus.words import encode_item_words
from phalanx.core.module import ContractError
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_params
from phalanx.ground.decoder.setup import parse_tmats
from phalanx.ground.decoder.words import Conversion, code_layout, eu_from_counts
from phalanx.recorder import writer
from phalanx.sensors.config import build_sensor_config

D = load_dictionary()
#: pre-W2.2 golden of the .c10 bytes (dictionary 0.1.2); dictionary 0.1.3 changes only the setup record's
#: release line (G\\COM ... 0.1.3) and adds the 0/1 measurement range (C-group MOT1/MOT2) of the discrete
#: ENG.AB_LIT (the UV flame detector, W2.2), so the bytes are re-pinned below and the setup text is checked
#: against the old golden through a 0.1.2 view (``as_012``)
GOLDEN_C10_012 = (
    "0f59fbcd8365b2eb6451780288145933f23ecb42bc03fb95a3594cf8a364f966"
    "3736034beed7b9ae0f53f63c007fa6e5d7c4fc72fba523939212594a78ce325e"
)
GOLDEN_C10 = (
    "4824894d4b6e235d32170092bae28d2d5b5cc082157d5e58895fffa42644b4ee"
    "fcd716408f93561b387186d641457e7864e6c961e31ec59af46504568d0f0a55"
)
RELEASE_LINE = "G\\COM:dictionary tejas {};"


def as_012(text: str) -> str:
    """The setup text as dictionary 0.1.2 wrote it: its release line, and no range lines for ENG.AB_LIT."""
    t = text.replace(RELEASE_LINE.format(D.dict_version), RELEASE_LINE.format("0.1.2"))
    k = re.search(r"^C-(\d+)\\DCN:ENG\.AB_LIT;$", t, flags=re.M).group(1)
    drop = re.compile(rf"^C-{k}\\MOT[12]:[^;]*;$")
    lines = t.splitlines(keepends=True)
    kept = [ln for ln in lines if not drop.match(ln.rstrip("\r\n"))]
    assert len(lines) - len(kept) == 2
    return "".join(kept)


GOLDEN_SETUP = (
    "19ee8cbc75ff306443e32f100e818e8e4ecf0022e93e740bec39e08deb8baf57"
    "f553ef27269cc7bb68e0fab15fd5459eb49cf989600f35f07ee7137d9bda51c0"
)
GOLDEN_RECORDS = (
    "2056a79c2b851d4fea28f433377bd4fcaf6c6e6d34954f829d2010fd85adbc01"
    "2dfada508c513fb39fbc6b5940095131231a161dae3955abc024ecfe6eba8e9e"
)
#: W2.2 phase B: the decoded records of the fixture with the spare FTI slots undescribed (derived below from
#: the pre-W2.2 golden: the same records minus the spare slots' zero fill)
GOLDEN_RECORDS_B = (
    "f22da4d6fa38a05ff265d51838c8df8e413a65d43ab0894b3056ca4141ffeec8"
    "8171e2fcf3251dfba90cf1bdb9aca622af985577204631be54ee095ebe1fd88f"
)
#: FTI PCM words no producer populates (flight-test panel; not simulated, scope S-FTI)
SPARE = ("FCS.FTP.FLAGS", "FCS.FTP.TEST_POINT")
RECORD_COLUMNS = (
    "record_id",
    "param_id",
    "value_eu",
    "raw_counts",
    "validity",
    "quality_flags",
    "t_sample",
    "t_record",
)
FADEC_CONVERTER_LANES = tuple(f"ENG.{m}.{x}" for m in ("PLA", "A8", "N1", "N2", "PS3", "T1") for x in "AB")


def records_digest(samples) -> str:
    h = hashlib.blake2b()
    for name in RECORD_COLUMNS:
        h.update(name.encode())
        h.update(repr(samples.column(name).to_pylist()).encode())
    return h.hexdigest()


@contextmanager
def describe_all_pcm():
    """TEST VIEW of the pre-phase-B writer: every FTI PCM word described in the setup record (M16's spare-slot
    finder substituted by "none")."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(writer, "unpopulated_pcm_words", lambda traffic: ())
        yield


def _fixture_cir():
    return make_cir(None, T0 - 10**9, T1, invalid_every=11)


@pytest.fixture(scope="module")
def run():
    return _run(_fixture_cir())


@pytest.fixture(scope="module")
def run_all_described():
    with describe_all_pcm():
        return _run(_fixture_cir())


def _described(setup_text: str) -> set[str]:
    """Channels the setup record describes: D-group measurands and C-group data conversions."""
    a = parse_tmats(setup_text)
    return {v[0] for k, v in a.items() if "\\MN-" in k or k.endswith("\\DCN")}


#: Ch10 data types whose packets depend on the setup record: the setup record (TMATS) itself and the recording
#: index packets, whose entries are file offsets (they move by the setup record's change in size)
SETUP_DEPENDENT = (0x01, 0x03)


def _packets(data: bytes) -> list[tuple[int, bytes]]:
    """(data type, packet bytes) in file order (Ch10 header: packet length bytes 4-7, data type byte 15)."""
    out, o = [], 0
    while o < len(data):
        n = int.from_bytes(data[o + 4 : o + 8], "little")
        out.append((data[o + 15], data[o : o + n]))
        o += n
    return out


# ---- M16 + M15/M17: byte-identical recording -------------------------------------------------------------
@pytest.mark.integration
def test_recording_bytes_and_decoded_records_unchanged_by_the_migrations(run_all_described):
    """With every FTI word described (the pre-phase-B writer view) the setup record equals the pre-W2.2 golden
    except the dictionary release line (0.1.3, W2.2 phase B); the .c10 bytes are re-pinned for that line; the
    decoded records are unchanged."""
    run = run_all_described
    text = run.recording.setup_text
    assert RELEASE_LINE.format(D.dict_version) in text and D.dict_version == "0.1.3"
    assert hashlib.blake2b(as_012(text).encode()).hexdigest() == GOLDEN_SETUP
    assert hashlib.blake2b(run.recording.data).hexdigest() == GOLDEN_C10
    s = run.decoded[1].samples
    assert s.num_rows == 45_908
    assert records_digest(s) == GOLDEN_RECORDS


@pytest.mark.integration
def test_spare_fti_slots_remove_only_their_zero_fill(run_all_described, run):
    """W2.2 phase B against the golden view: the setup record stops describing exactly the spare FTI words;
    every data and time packet is byte-identical (the index packets keep their size; their file offsets
    move with the setup record); the decoded records are the golden ones minus exactly the spare slots'
    records, all of them zero fill."""
    old, new = run_all_described, run
    assert writer.unpopulated_pcm_words(new.traffic) == SPARE
    assert _described(old.recording.setup_text) - _described(new.recording.setup_text) == set(SPARE)
    assert _described(new.recording.setup_text) < _described(old.recording.setup_text)
    pa, pb = _packets(old.recording.data), _packets(new.recording.data)
    assert [t for t, _ in pa] == [t for t, _ in pb]
    assert [p for t, p in pa if t not in SETUP_DEPENDENT] == [p for t, p in pb if t not in SETUP_DEPENDENT]
    assert [len(p) for t, p in pa if t == 0x03] == [len(p) for t, p in pb if t == 0x03]
    a, b = old.decoded[1].samples, new.decoded[1].samples
    spare = np.isin(np.array(a.column("param_id").to_pylist(), dtype=object), SPARE)
    assert spare.sum() == a.num_rows - b.num_rows == 768  # 2 words x 384 frames (64 Hz x 6 s)
    assert set(np.asarray(a.column("raw_counts").to_pylist())[spare].tolist()) == {0}
    assert records_digest(a.filter(~spare)) == records_digest(b) == GOLDEN_RECORDS_B


@pytest.mark.integration
def test_the_fixture_exercises_the_code_word_layout(run):
    """The golden would not notice a layout change unless code words with k > 0 are recorded."""
    s = run.decoded[1].samples
    pid = np.array(s.column("param_id").to_pylist(), dtype=object)
    v = s.column("value_eu").to_numpy()[np.isin(pid, ["ENG.FAULT_CODES", "FCS.BIT.LOG"])]
    assert v.size >= 100 and np.any(v >= 1000) and np.any((v > 0) & (v < 1000))


@pytest.mark.unit
def test_code_table_names_are_strings():
    """Dictionary 0.1.3: every enum code name is a string (ins_mode code 0 was the YAML 1.1 boolean false
    until 0.1.3, from an unquoted OFF); the bit-code catalogue's records are mappings by design."""
    bad = []
    for name, table in D.content["code_tables"].items():
        codes = table.get("codes") if hasattr(table, "get") else None
        if not codes or name == "bit_codes":
            continue
        bad += [(name, k, v) for k, v in codes.items() if not isinstance(k, str) or not isinstance(v, str)]
    assert bad == []
    assert D.content["code_tables"]["ins_mode"]["codes"]["0"] == "OFF"


# ---- M15/M17 code-word layout from the dictionary ------------------------------------------------------
@pytest.mark.unit
def test_code_word_layout_is_the_dictionarys():
    lay = D.content["code_tables"]["bit_code_format"]["word_layout"]
    item = BusIcd.from_dictionary(D).item("ENG.FAULT_CODES")
    assert item.code_layout == CodeWordLayout.from_dictionary(D)
    assert item.code_layout.k_lsb == lay["prefix_index"]["lsb_bit"] and item.code_layout.scale == 1000
    assert code_layout(D) == (
        lay["prefix_index"]["lsb_bit"],
        lay["prefix_index"]["width"],
        lay["number"]["lsb_bit"],
        lay["number"]["width"],
        lay["eu_prefix_scale"],
    )
    # the dictionary's own codec agrees with M15 and M17 on every value M15 can carry
    v = np.array([0, 1, 42, 999, 1000, 1042, 1999], dtype=np.float64)
    words, bad = encode_item_words(item, v)
    assert not bad.any()
    assert words[:, 0].tolist() == [D.code_word_bits(int(x)) for x in v]
    dec, _ = eu_from_counts(
        words[:, 0].astype(np.int64), Conversion("CODE", 16, 0.0, 1.0, 0, code=code_layout(D))
    )
    assert np.array_equal(dec, v)


@pytest.mark.unit
def test_a_different_layout_moves_the_bits_and_is_read_back_only_by_its_own_decoder():
    """Negative control: neither side hides a constant layout. A variant layout (k in bits 12-15) changes the
    words; a decoder on the same variant round-trips them, a decoder on the dictionary layout does not."""
    item = BusIcd.from_dictionary(D).item("ENG.FAULT_CODES")
    variant = CodeWordLayout(word_bits=16, k_lsb=12, k_width=4, n_lsb=0, n_width=10, scale=1000)
    moved = dataclasses.replace(item, code_layout=variant)
    v = np.array([1042.0, 1999.0, 7.0])
    w_dict, _ = encode_item_words(item, v)
    w_var, bad = encode_item_words(moved, v)
    assert not bad.any() and w_var[:, 0].tolist() == [(1 << 12) | 42, (1 << 12) | 999, 7]
    assert w_var[:, 0].tolist() != w_dict[:, 0].tolist()
    ok, _ = eu_from_counts(
        w_var[:, 0].astype(np.int64), Conversion("CODE", 16, 0, 1, 0, code=(12, 4, 0, 10, 1000))
    )
    assert np.array_equal(ok, v)
    wrong, _ = eu_from_counts(
        w_var[:, 0].astype(np.int64), Conversion("CODE", 16, 0, 1, 0, code=code_layout(D))
    )
    assert not np.array_equal(wrong, v)
    with pytest.raises(ValueError, match="layout"):
        encode_item_words(dataclasses.replace(item, code_layout=None), v)
    with pytest.raises(ValueError, match="layout"):
        eu_from_counts(w_var[:, 0].astype(np.int64), Conversion("CODE", 16, 0, 1, 0))


# ---- M13: FADEC lanes at the converter step, noise in EU -----------------------------------------------
@pytest.fixture(scope="module")
def lanes_acq():
    sens = build_sensor_config(D)
    return build_acquisition_config(D, FADEC_CONVERTER_LANES, sensor_channels=sens.channels)


@pytest.mark.unit
def test_fadec_lanes_quantise_at_the_converter_step(lanes_acq):
    from phalanx.acquisition import kernel as K

    for c, cid in enumerate(lanes_acq.channels):
        ch = D.channel(cid)
        assert ch["recorder_lsb"] is None  # internal lanes: the converter grid is the final grid
        assert ch["prov"]["native_step"] == "R-FADEC-ADC" and "converter_step" not in ch  # 0.1.3
        assert lanes_acq.P[c, K.AP_QN] == lanes_acq.P[c, K.AP_SF] == float(ch["native_step"])
        assert float(ch["native_step"]) < _word_step(cid)


@pytest.mark.unit
def test_lane_noise_in_eu_equals_the_w16_level(lanes_acq):
    """The migration changes the quantiser, not the noise: each lane's EU sigma equals what W1.6 configured
    (sigma_steps x native step: N1 0.61, N2 0.16, the rest noise_default's 0.144 steps)."""
    from phalanx.acquisition import kernel as K

    w16_steps = {"N1": 0.61, "N2": 0.16, "PLA": 0.144, "A8": 0.144, "PS3": 0.144, "T1": 0.144}
    for c, cid in enumerate(lanes_acq.channels):
        expect = w16_steps[cid.split(".")[1]] * _word_step(cid)  # W1.6: steps of the recorded-word step
        assert lanes_acq.P[c, K.AP_SIGMA] == pytest.approx(expect, rel=1e-12, abs=0.0), cid
        assert lanes_acq.sigma_eff_eu[c] <= lanes_acq.ceiling_eu[c]


def _word_step(cid: str) -> float:
    """Recorded-word step of a FADEC lane: the recorder LSB of its voted word (the 0.1.2 native step)."""
    return float(D.channel(f"{D.channel(cid)['measurand_id']}.V")["recorder_lsb"])


class _As012:
    """The dictionary as 0.1.2 published the FADEC lanes (TEST FIXTURE view): ``converter_step`` = the
    converter step, ``native_step`` = the recorded-word step."""

    def __init__(self, d):
        self._d = d

    def channel(self, cid):
        ch = dict(self._d.channel(cid))
        if (ch.get("prov") or {}).get("native_step") == "R-FADEC-ADC":
            ch["converter_step"] = ch["native_step"]
            ch["native_step"] = _word_step(cid)
        return ch

    def __getattr__(self, name):
        return getattr(self._d, name)


@pytest.mark.unit
def test_lane_quantiser_and_noise_did_not_move_from_0_1_2_to_0_1_3(lanes_acq):
    from phalanx.acquisition import kernel as K

    sens = build_sensor_config(D)
    old = build_acquisition_config(_As012(D), FADEC_CONVERTER_LANES, sensor_channels=sens.channels)
    for k in (K.AP_SIGMA, K.AP_QN, K.AP_SF):
        np.testing.assert_array_equal(old.P[:, k], lanes_acq.P[:, k])
    np.testing.assert_array_equal(old.ceiling_eu, lanes_acq.ceiling_eu)


@pytest.mark.unit
def test_a_converter_step_lane_with_noise_in_steps_is_refused():
    """Negative control (0.1.2 view, a dictionary carrying converter_step): noise in steps on a converter-step
    channel would have changed silently when the step moved into native_step."""
    sens = build_sensor_config(D)
    p = load_params("M13")
    p["noise_fadec_ps3"] = p["noise_default"]  # sigma_steps only
    with pytest.raises(ContractError, match="noise in EU"):
        build_acquisition_config(_As012(D), ("ENG.PS3.A",), sensor_channels=sens.channels, params=p)
    p = load_params("M13")
    p["ceiling_fadec_ps3"] = p["ceiling_default"]
    with pytest.raises(ContractError, match="ceiling in EU"):
        build_acquisition_config(_As012(D), ("ENG.PS3.A",), sensor_channels=sens.channels, params=p)
