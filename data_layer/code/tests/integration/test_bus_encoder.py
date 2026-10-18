"""M15 bus encoder behaviour against its mechanism (architecture §8; report §13 t_bus model).

Sample sizes: 2-4 s windows (100-200 polls per AV50 message), enough for every update/poll phase relation of
the 40/50/80 Hz clocks to occur; each test states what it checks.
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
from test_bus_cir_fixture import EPOCH, IDENT, make_cir, rng_service

from phalanx.bus.encoder import BusConfig, encode_bus
from phalanx.bus.icd import BusIcd
from phalanx.dictionary import load_dictionary
from phalanx.ground.cir import CirBatch

D = load_dictionary()
ICD = BusIcd.from_dictionary(D)
CFG = BusConfig.from_params()
T0 = EPOCH + 20 * 10**9


def _encode(cir, t0=T0, t1=T0 + 2 * 10**9, cfg=CFG):
    return encode_bus(cir, ICD, cfg, IDENT, rng_service(), t0=t0, t1=t1)


def _bus(tr, name):
    return next(b for b in tr.buses if b.bus == name)


def _msg_items(bt, msg_id):
    i = next(k for k, m in enumerate(bt.schedule.messages) if m.msg_id == msg_id)
    txn = np.flatnonzero(bt.msg == i)
    sel = np.isin(bt.item_txn, txn)
    return i, txn, sel


def test_latency_and_age_follow_the_clock_model():
    """DFCC SA1 (FCS40 buffer, AV50 poll): every item value read at poll p was acquired at u with
    L_proc <= p - u < L_proc + T_update (T_update = 25 ms on the DFCC crystal)."""
    chans = [it.channel_id for m in ICD.messages if m.msg_id == "AV-MUX-2/RT01/T/SA01" for it in m.items]
    cir = make_cir(chans, T0 - 10**9, T0 + 3 * 10**9)
    bt = _bus(_encode(cir), "AV-MUX-2")
    _, _, sel = _msg_items(bt, "AV-MUX-2/RT01/T/SA01")
    rows = bt.item_row[sel]
    ok = rows >= 0
    t_cmd = bt.t_cmd[bt.item_txn[sel]][ok]
    t_s = cir.table.column("t_sample").to_numpy()[rows[ok]]
    age = t_cmd - t_s
    lp = CFG.processing_latency_ns
    assert ok.mean() > 0.95
    assert age.min() >= lp
    assert age.max() < lp + 25_000_000 * (1 + 1e-4)
    # the age spreads over (nearly) the whole update period: polls are asynchronous to the producer
    assert age.max() - age.min() > 0.8 * 25_000_000


def test_relayed_items_use_the_relay_latency():
    """ADC words relayed by the DFCC (SA3): acquired at or before u - L_relay on the ADC crystal."""
    chans = [it.channel_id for m in ICD.messages if m.msg_id == "AV-MUX-2/RT01/T/SA03" for it in m.items]
    cir = make_cir(chans, T0 - 10**9, T0 + 3 * 10**9)
    bt = _bus(_encode(cir), "AV-MUX-2")
    _, _, sel = _msg_items(bt, "AV-MUX-2/RT01/T/SA03")
    rows = bt.item_row[sel]
    ok = rows >= 0
    age = bt.t_cmd[bt.item_txn[sel]][ok] - cir.table.column("t_sample").to_numpy()[rows[ok]]
    lo = CFG.processing_latency_ns + CFG.relay_latency_ns
    hi = lo + 12_500_000 + 12_500_000  # DFCC 80 Hz buffer update + ADC 80 Hz acquisition period
    assert age.min() >= lo and age.max() < hi * (1 + 1e-4)


def test_absent_rt_does_not_answer():
    """No FADEC stream in the CIR: every FADEC poll is a response timeout (command word only, no items)."""
    cir = make_cir(["AD.AOA"], T0 - 10**9, T0 + 2 * 10**9)
    bt = _bus(_encode(cir), "AV-MUX-2")
    fadec = [k for k, m in enumerate(bt.schedule.messages) if m.rt_lru == "FADEC"]
    txn = np.flatnonzero(np.isin(bt.msg, fadec))
    assert txn.size > 0 and bt.timeout[txn].all()
    assert np.all(np.diff(bt.word_offsets)[txn] == 1)
    assert not np.isin(bt.item_txn, txn).any()
    dfcc = [k for k, m in enumerate(bt.schedule.messages) if m.rt_lru == "DFCC"]
    assert not bt.timeout[np.isin(bt.msg, dfcc)].any()  # the DFCC relays the ADC data: it answers


def test_missing_items_and_invalid_samples_set_the_validity_bit():
    """Items with no data and samples that are not NORMAL go out with their validity bit set and zero data."""
    m = next(m for m in ICD.messages if m.msg_id == "AV-MUX-2/RT05/T/SA01")
    present = m.items[0]
    cir = make_cir([present.channel_id], T0 - 10**9, T0 + 2 * 10**9, invalid_every=7)
    bt = _bus(_encode(cir), "AV-MUX-2")
    _, txn, _ = _msg_items(bt, m.msg_id)
    words = np.stack([bt.words[bt.word_offsets[t] : bt.word_offsets[t + 1]] for t in txn])
    vword = words[:, 2]  # cmd, status, validity word 1
    data = words[:, 2:]
    for it in m.items[1:]:
        assert np.all((vword >> it.validity_bit) & 1 == 1), it.channel_id
        assert np.all(data[:, it.first_word - 1 : it.first_word - 1 + it.words] == 0)
    rows = bt.item_row[np.isin(bt.item_txn, txn) & (bt.item_idx == 0)]
    val = np.array(cir.table.column("validity").to_pylist(), dtype=object)[rows]
    bit = (vword >> present.validity_bit) & 1
    assert np.array_equal(bit == 1, val != "NORMAL")
    assert (val != "NORMAL").any() and (val == "NORMAL").any()


def test_busy_rt_answers_with_status_only():
    """BUSY in the RT status word: the RT sends its status word and no data (MIL-STD-1553B)."""
    m = next(m for m in ICD.messages if m.msg_id == "AV-MUX-2/RT05/T/SA01")
    base = make_cir([m.items[0].channel_id, "AV.RT.STATUS.FADEC"], T0 - 10**9, T0 + 2 * 10**9)
    tab = base.table
    is_status = pc.equal(tab.column("param_id"), "AV.RT.STATUS.FADEC")
    v = np.where(is_status.to_numpy(zero_copy_only=False), float(1 << 3), tab.column("value").to_numpy())
    tab = tab.set_column(tab.schema.get_field_index("value"), "value", pa.array(v))
    bt = _bus(_encode(CirBatch(base.tail_no, base.sortie_id, tab)), "AV-MUX-2")
    _, txn, sel = _msg_items(bt, m.msg_id)
    assert np.all(np.diff(bt.word_offsets)[txn] == 2)
    status = bt.words[bt.word_offsets[txn] + 1]
    assert np.all(status == (5 << 11) | (1 << 3))
    assert not sel.any()  # no item words were sent


def test_duplicates_are_exactly_repeated_buffer_updates():
    """item_dup marks a poll that read the same buffer write as the previous poll of that message."""
    m = next(m for m in ICD.messages if m.msg_id == "AV-MUX-2/RT01/T/SA01")
    cir = make_cir([it.channel_id for it in m.items], T0 - 10**9, T0 + 4 * 10**9)
    bt = _bus(_encode(cir, t1=T0 + 4 * 10**9), "AV-MUX-2")
    _, txn, sel = _msg_items(bt, m.msg_id)
    upd = bt.update[txn]
    dup_txn = np.r_[False, upd[1:] == upd[:-1]]
    first_item = sel & (bt.item_idx == 0)
    assert (upd >= 0).all() and np.array_equal(bt.item_dup[first_item], dup_txn)
    # 40 Hz producer polled at 50 Hz: one poll in five repeats the previous buffer
    assert abs(dup_txn.mean() - 0.2) < 0.02


def test_timing_is_independent_of_values_crn():
    """Forks share data-path timing: other CIR values, same identity -> identical polls, updates, times."""
    chans = ["ENG.N2.V", "AD.AOA", "HYD.SYS1.P"]
    a = make_cir(chans, T0 - 10**9, T0 + 2 * 10**9)
    tab = a.table
    tab2 = tab.set_column(
        tab.schema.get_field_index("value"), "value", pa.array(tab.column("value").to_numpy() * 0.5)
    )
    b = CirBatch(a.tail_no, a.sortie_id, tab2)
    ta, tb = _encode(a), _encode(b)
    for x, y in zip(ta.buses, tb.buses, strict=True):
        assert np.array_equal(x.t_cmd, y.t_cmd) and np.array_equal(x.update, y.update)
        assert np.array_equal(x.word_offsets, y.word_offsets)
    assert any(not np.array_equal(x.words, y.words) for x, y in zip(ta.buses, tb.buses, strict=True))


def test_arinc429_words_go_out_back_to_back_per_cycle():
    """CWS labels (low speed, AV12.5): one word per label per 80 ms cycle, 36 bit times apart (12.5 kb/s)."""
    chans = [lb.item.channel_id for lb in ICD.labels if lb.link == "CWS-OAC"]
    cir = make_cir(chans, T0 - 10**9, T0 + 2 * 10**9)
    lw = next(x for x in _encode(cir).links if x.link == "CWS-OAC")
    per_cycle = np.bincount(lw.cycle - lw.cycle.min())
    assert set(per_cycle[1:-1].tolist()) == {len(chans)}
    first = lw.t_start[lw.cycle == lw.cycle[len(chans) * 2]]
    assert np.allclose(np.diff(first), 36 / 12_500 * 1e9, atol=1)
