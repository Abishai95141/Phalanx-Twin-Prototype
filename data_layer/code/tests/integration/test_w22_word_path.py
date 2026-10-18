"""W2.2 phase B part 1, item 1: the M13 word path (A-W2.2-12) and the LRU clock sets.

A status, discrete, enum or code word is the producer's integer. M13 acquires it without inventing anything:
the kernel's ``MODE_HOLD`` reads the word the producer published last (the value at the frame start, held
through the frame, never interpolated), with no quantiser (step 1, full scale = the word's bits), no noise,
deadband, freeze, gate, glitch or slip. It is read on the clock of its LRU's acquisition domain at the
dictionary acquisition rate, or at the bus refresh rate for an event-driven word (no periodic acquisition
rate). M15 then encodes it with the dictionary bitfield, enum or code-word layout and M17 decodes it.

The words: every dictionary word on a recorded transport (the 53 RECORDED words, plus the words whose
producers are later work: 1553 RT-status and bus-status words, per-LRU BIT and health words, and the
not-simulated discretes). Their values here are a TEST FIXTURE: each word steps through valid values of its
own encoding (defined bitfield bits, enum codes, valid code words) at seeded frames.

Sample: one 3 s block (720 truth frames) of every such word (n = 1 run; 3 s gives every 12.5 Hz word at least
37 reads and every word several value changes), through M13 -> CIR -> M15 -> M16 -> M17 with FTI fitted; the
compiled = reference and block-split checks use its first second (n = 240 frames).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pyarrow as pa
import pytest
from test_bus_cir_fixture import ROOT, registry

from phalanx.acquisition import kernel as K
from phalanx.acquisition.config import (
    acquisition_domain_lru,
    acquisition_rate,
    build_acquisition_config,
    clock_consistency_problems,
    is_word_channel,
)
from phalanx.acquisition.core import STREAMS as ACQ_STREAMS
from phalanx.acquisition.record import AcquisitionRecorder
from phalanx.bus.clocks import SortieIdentity, acquisition_oscillators
from phalanx.bus.encoder import STATUS_BUSY, STATUS_FLAG_MASK, STATUS_MESSAGE_ERROR, check_cir_on_oscillator
from phalanx.bus.icd import BusIcd
from phalanx.core.rng import RngService
from phalanx.core.time import truth_step_times_ns
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.ground.fast_path import FTI_TRANSPORT, RECORDED_TRANSPORTS
from phalanx.ground.rid import record_ids
from phalanx.recorder.full_path import run_full_path

pytestmark = pytest.mark.integration

C = load_contract("v0")
D = load_dictionary()
ICD = BusIcd.from_dictionary(D)
EPOCH = 1_790_000_000 * 10**9
IDENT = SortieIdentity(scenario="W22WORDS", tail_no="KH2001", sortie_id="KH2001-20261015-1000")
SECONDS = 3
L = 240 * SECONDS
CARRIED = RECORDED_TRANSPORTS | {FTI_TRANSPORT}
WORDS = tuple(
    c["channel_id"]
    for c in D.channels()
    if is_word_channel(D, c["channel_id"]) and c["transport"].get("type") in CARRIED
)


#: truth frames during which the DFCC's RT status word carries the subsystem flag (the second second)
SUBSYSTEM_WINDOW = (240, 480)
ST_SUBSYSTEM, ST_TERMINAL = 1 << 2, 1 << 0  # RT status word bits (dictionary bitfield AV.RT.STATUS.*)


def _rng() -> RngService:
    return RngService(ROOT, registry(*ACQ_STREAMS))


def _alphabet(cid: str, gen: np.random.Generator, n: int) -> np.ndarray:
    """``n`` valid values of the word's own encoding (TEST FIXTURE)."""
    ch = D.channel(cid)
    enc = ch["encoding"]
    if enc["type"] == "enum":
        codes = np.array(sorted(int(k) for k in D.content["code_tables"][enc["code_table"]]["codes"]))
        return gen.choice(codes, n).astype(np.float64)
    if enc["type"] == "code_word":
        scale = int(D.content["code_tables"]["bit_code_format"]["word_layout"]["eu_prefix_scale"])
        k = gen.integers(0, len(ICD.item(cid).prefixes), n)
        return (k * scale + gen.integers(0, 1000, n)).astype(np.float64)
    mask = 0
    for f in enc["fields"]:
        mask |= ((1 << int(f["width"])) - 1) << int(f["lsb_bit"])
    if ch["transport"]["type"] == "mil1553_status":
        # the RT address bits are the RT's, not the producer's. The flags that change how the RT's data is
        # handled stay clear here (BUSY / MESSAGE ERROR: the RT answers with its status word only, M15;
        # SUBSYSTEM / TERMINAL: the ground marks the RT's data BUS_INVALID, M17); the DFCC's subsystem flag is
        # exercised on its own window (SUBSYSTEM_WINDOW)
        mask &= STATUS_FLAG_MASK & ~(STATUS_BUSY | STATUS_MESSAGE_ERROR | ST_SUBSYSTEM | ST_TERMINAL)
    return (gen.integers(0, 1 << 32, n, dtype=np.int64) & mask).astype(np.float64)


def producer_words() -> dict[str, np.ndarray]:
    """Per word, its value at each truth-frame end (EU = SI for a word): steps at seeded frames (~1 in 40);
    the DFCC raises its RT subsystem flag for SUBSYSTEM_WINDOW only."""
    gen = np.random.Generator(np.random.PCG64(0x22_0D_5EED))  # TEST FIXTURE values, fixed literal seed
    out = {}
    for cid in WORDS:
        steps = np.cumsum(gen.random(L) < 1 / 40)
        out[cid] = _alphabet(cid, gen, int(steps[-1]) + 1)[steps]
    flag = np.zeros(L)
    flag[SUBSYSTEM_WINDOW[0] : SUBSYSTEM_WINDOW[1]] = ST_SUBSYSTEM
    out["AV.RT.STATUS.DFCC"] = flag
    return out


def record(acq, words, frames, *, compiled=True, blocks=None):
    rec = AcquisitionRecorder(acq, _rng().scope(IDENT.key()), compiled=compiled)
    state, recs, k0 = rec.init_state(), {}, 0
    for n in blocks or (frames,):
        ext = {c: (D.eu_to_si(c, w[k0 : k0 + n]),) * 2 for c, w in words.items()}
        state, recs = rec.process(state, k0, np.zeros((n, 0)), np.zeros((n, 0)), np.full(n, 5), ext, recs)
        k0 += n
    return rec, recs


def held(words: np.ndarray, t_kernel: np.ndarray) -> np.ndarray:
    """The value the producer published last at each kernel instant: frame j covers [t_j, t_{j+1}) and its
    published word is the one at t_j (frame j - 1's end; the first frame primes with its own value)."""
    bounds = truth_step_times_ns(np.arange(words.size + 1))
    j = np.searchsorted(bounds, t_kernel, side="right") - 1
    return words[np.maximum(j - 1, 0)]


@pytest.fixture(scope="module")
def words():
    return producer_words()


@pytest.fixture(scope="module")
def acq():
    return build_acquisition_config(D, WORDS)


@pytest.fixture(scope="module")
def recorded(acq, words):
    rec, recs = record(acq, words, L)
    return rec, recs, rec.to_cir(C, IDENT.tail_no, IDENT.sortie_id, recs, epoch_ns=EPOCH)


# ---- configuration -----------------------------------------------------------------------------------------
def test_the_word_set():
    """The 53 RECORDED words plus the status words of the RT-status, bus-status, per-LRU BIT/health and
    not-simulated discrete channels: every dictionary word a recorded transport carries."""
    kinds = {D.channel(c)["transport"]["type"] for c in WORDS}
    assert len(WORDS) == 124 and kinds == {
        "mil1553",
        "mil1553_status",
        "mil1553_modecode",
        "arinc429",
        "fti_pcm",
    }
    assert sum(c.startswith("AV.RT.STATUS.") for c in WORDS) == 8
    assert sum(c.startswith("AV.1553.BUS_STATUS.") for c in WORDS) == 3
    assert sum(c.startswith("AV.LRU.BIT.") for c in WORDS) == 8


def test_words_are_held_unquantised_and_untextured(acq):
    for c, cid in enumerate(acq.channels):
        enc = D.channel(cid)["encoding"]
        assert int(acq.Q[c, K.AQ_MODE]) == K.MODE_HOLD, cid
        assert acq.P[c, K.AP_QN] == 1.0 and acq.P[c, K.AP_SF] == 1.0 and acq.P[c, K.AP_OF] == 0.0, cid
        assert acq.sigma_eff_eu[c] == 0.0 and acq.P[c, K.AP_SIGMA] == 0.0, cid
        assert acq.P[c, K.AP_GLP] == acq.P[c, K.AP_FRZP] == acq.P[c, K.AP_DB] == 0.0, cid
        assert int(acq.Q[c, K.AQ_GATE]) == int(acq.Q[c, K.AQ_SLIP]) == 0, cid
        full = (1 << (int(enc["word_bits"]) * int(enc.get("words", 1)))) - 1
        if enc["type"] == "code_word":
            lay = D.content["code_tables"]["bit_code_format"]["word_layout"]
            full = (
                ((1 << lay["prefix_index"]["width"]) - 1) * lay["eu_prefix_scale"]
                + (1 << lay["number"]["width"])
                - 1
            )
        declared = D.channel(cid).get("range") or {}
        if (
            declared.get("max") is not None
        ):  # a declared span (ENG.AB_LIT 0/1, dictionary 0.1.3) bounds the codes
            full = int(declared["max"])
        assert (int(acq.Q[c, K.AQ_CMIN]), int(acq.Q[c, K.AQ_CMAX])) == (0, full), cid


def test_words_are_on_their_lru_clock_at_their_rate(acq):
    """Each word on its acquisition-domain LRU's clock set (the new INGPS, SMS, CWS, OAC, RADAR, ECMS ones
    included) at the dictionary acquisition rate, or the bus refresh rate for an event-driven word."""
    assert clock_consistency_problems(D, acq) == []
    event_driven = [c for c in WORDS if D.acquisition_rate_hz(c) is None]
    assert len(event_driven) >= 20
    for c, cid in enumerate(acq.channels):
        dom = acq.domains[int(acq.domain_of[c])]
        assert dom.lru == acquisition_domain_lru(D, cid)
        bus_hz = D.content["rate_groups"][D.channel(cid)["rates"]["bus"]]["rate_hz"]
        want = bus_hz if cid in event_driven else D.acquisition_rate_hz(cid)
        assert float(dom.clock.f_nom_hz) == acquisition_rate(D, cid) == want, cid
    assert {acq.domains[int(acq.domain_of[acq.index(c)])].lru for c in WORDS} >= {
        "INGPS",
        "SMS",
        "CWS",
        "OAC",
        "RADAR",
        "ECMS",
    }


# ---- M13 output --------------------------------------------------------------------------------------------
def test_cir_words_are_the_producers_held_words(recorded, words):
    """Exact: every acquired sample is the producer's last published word, validity NORMAL, no flags."""
    _rec, recs, cir = recorded
    for cid in WORDS:
        r = recs[cid]
        t = r.cat("t_sample", np.int64)
        v = r.cat("value", np.float64)
        assert v.size >= int(acquisition_rate(D, cid) * SECONDS) - 1, cid
        assert np.array_equal(v, held(words[cid], t)), cid
        assert np.array_equal(r.cat("truth", np.float64), v), cid
        assert not r.cat("flags", np.int64).any() and not r.cat("validity", np.int64).any(), cid
    assert set(cir.table.column("validity").to_pylist()) == {"NORMAL"}


def test_event_driven_words_on_the_bus_rate_grid(recorded):
    _rec, _recs, cir = recorded
    oscs = acquisition_oscillators(D, EPOCH)
    tab = cir.table
    for cid in WORDS:
        loc = D.contract_location(cid)
        sel = np.array(
            [
                p == loc["param_id"] and s == loc["source_lru"]
                for p, s in zip(
                    tab.column("param_id").to_pylist(), tab.column("source_lru").to_pylist(), strict=True
                )
            ]
        )
        t = tab.column("t_sample").to_numpy()[sel]
        osc = oscs[acquisition_domain_lru(D, cid)]
        assert check_cir_on_oscillator(t, osc, rate_hz=acquisition_rate(D, cid)), cid


def test_compiled_equals_reference_and_block_split(acq, words):
    """The NumPy reference (kernel py_func) and a three-block run equal the compiled single block, bitwise."""
    n = 240
    _r1, a = record(acq, words, n)
    _r2, b = record(acq, words, n, compiled=False)
    _r3, c = record(acq, words, n, blocks=(70, 1, 169))
    for cid in WORDS:
        for name in ("sample_index", "t_sample", "value", "flags", "validity"):
            x = a[cid].cat(name, np.float64)
            assert np.array_equal(x, b[cid].cat(name, np.float64)), (cid, name)
            assert np.array_equal(x, c[cid].cat(name, np.float64)), (cid, name)


def test_negative_control_interpolating_a_word_fabricates_values(acq, words):
    """The pre-W2.2 numeric acquisition (linear interpolation between frame values) applied to the same words
    reads values the producer never published; the hold does not."""
    Q = acq.Q.copy()
    Q[:, K.AQ_MODE] = K.MODE_POINT
    point = replace(acq, Q=Q)
    _rec, recs = record(point, words, L)
    fabricated = 0
    for cid in WORDS:
        v = recs[cid].cat("value", np.float64)
        fabricated += int(np.sum(~np.isin(v, words[cid])))
    assert fabricated > 50


# ---- through the full path ---------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def full(recorded):
    _rec, _recs, cir = recorded
    return run_full_path(
        cir,
        ident=IDENT,
        rng=_rng(),
        t_start=EPOCH + 10**9,
        t_end=EPOCH + SECONDS * 10**9,
        oscillators=acquisition_oscillators(D, EPOCH),
        fti_fitted=True,
    )


def _joined(full):
    """Decoded records of the complete delivery and the CIR row behind each (-1: no data)."""
    s = full.decoded[-1].samples
    tr = full.recording.truth
    ids = record_ids(
        C,
        "param.samples",
        {
            "provenance": "full_path",
            "tail_no": IDENT.tail_no,
            "sortie_id": IDENT.sortie_id,
            "channel_id": tr.column("channel_id"),
            "param_id": tr.column("param_id"),
            "seq": tr.column("seq"),
            "msg_index": tr.column("msg_index"),
        },
        tr.num_rows,
    )
    pos = {bytes(r): i for i, r in enumerate(ids.to_pylist())}
    order = np.array([pos[bytes(r)] for r in s.column("record_id").to_pylist()], dtype=np.int64)
    return s, tr.take(pa.array(order)).column("cir_row").to_numpy()


def test_words_survive_the_full_path_exactly(recorded, full):
    """Every word reaches param.samples on the full path, and each decoded value is the transmitted CIR word
    (RT status words with the ICD RT address in bits 15-11, which the RT, not the producer, writes)."""
    _rec, _recs, cir = recorded
    s, rows = _joined(full)
    has = rows >= 0
    keys = list(zip(*(s.column(c).to_pylist() for c in ("param_id", "source_lru", "lane")), strict=True))
    want = {(D.contract_location(c)["param_id"], D.contract_location(c)["source_lru"]) for c in WORDS}
    got = {(p, lru) for (p, lru, _), h in zip(keys, has.tolist(), strict=True) if h}
    assert want <= got, sorted(want - got)[:5]
    v_dec = s.column("value_eu").to_numpy()[has]
    v_cir = cir.table.column("value").to_numpy()[rows[has]]
    rt = {}
    for c in WORDS:
        t = D.channel(c)["transport"]
        if t["type"] == "mil1553_status":
            rt[D.contract_location(c)["param_id"], D.contract_location(c)["source_lru"]] = int(t["rt"]) << 11
    addr = np.array([rt.get((p, lru), 0) for (p, lru, _), h in zip(keys, has.tolist(), strict=True) if h])
    assert has.sum() > 3_000
    assert np.array_equal(v_dec, v_cir + addr)


def test_an_rt_subsystem_flag_on_the_bus_marks_that_rts_data(full):
    """The RT status word is live on the bus: while the DFCC's status word carries the subsystem flag, the
    ground marks every data record of the DFCC's messages BUS_INVALID (M17; the status-word record itself
    stays NORMAL and carries the flag); all other records with data are NORMAL.
    The flag reaches a poll through the DFCC's 80 Hz acquisition and the hold (<= 12.5 ms + one truth frame),
    so records within 25 ms of the window edges are not judged."""
    s, rows = _joined(full)
    has = rows >= 0
    dfcc = {
        D.contract_location(c["channel_id"])["param_id"]
        for c in D.channels()
        if c["transport"].get("rt_lru") == "DFCC"
        and c["transport"]["type"] in ("mil1553", "mil1553_modecode")
    }
    pid = np.array(s.column("param_id").to_pylist(), dtype=object)
    on_dfcc = np.isin(pid, sorted(dfcc))
    bad = np.array(s.column("validity").to_pylist(), dtype=object) == "BUS_INVALID"
    t = s.column("t_sample").to_numpy() - EPOCH
    w0, w1 = (int(x) for x in truth_step_times_ns(np.array(SUBSYSTEM_WINDOW)))
    edge = 25_000_000
    inside = (t >= w0 + edge) & (t < w1 - edge)
    outside = (t < w0 - edge) | (t >= w1 + edge)
    assert (has & on_dfcc & inside).sum() > 100 and (has & on_dfcc & outside).sum() > 100
    assert bad[has & on_dfcc & inside].all()
    assert not bad[has & on_dfcc & outside].any()
    assert not bad[has & ~on_dfcc].any()
