"""W0.2 RNG service (AD-15, I8): key paths, registry (typo-forks), counter addressing, CRN ledger.

All cases are deterministic and small (block sizes 8-64, at most a few thousand draws).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.rng import (
    DrawLedger,
    KeyPath,
    RngError,
    RngService,
    StreamDecl,
    StreamRegistry,
    UndeclaredStreamError,
    Variate,
    component_words,
    crn_audit,
    generator_from_state_tree,
    generator_state_tree,
)

ROOT = 0x0123456789ABCDEFFEDCBA9876543210


def _reg(block=16):
    return StreamRegistry(
        [
            StreamDecl(
                "eng", "fuel_metering", ("scenario", "tail", "serial", "sortie"), Variate.NORMAL, block
            ),
            StreamDecl("eng", "install_bias", ("scenario", "serial"), Variate.NORMAL, block),
            StreamDecl("wx", "gust", ("scenario", "base", "date"), Variate.UNIFORM, block),
            StreamDecl("m18", "repair_time", ("scenario", "tail", "job"), Variate.GENERATOR),
            StreamDecl("bus", "raw_bits", ("scenario", "tail"), Variate.RAW, block),
        ]
    )


def _p(**kw):
    return KeyPath.of(**kw)


FM = dict(scenario="S1", tail="KH2011", serial="ESN-7", sortie=3, subsystem="eng", component="fuel_metering")


@pytest.mark.unit
def test_keypath_is_canonically_ordered_and_validated():
    a = KeyPath.of(component="c", tail="T1", subsystem="s", scenario="S")
    assert a.kinds == ("scenario", "tail", "subsystem", "component")
    assert a.canonical() == "scenario=s:S/tail=s:T1/subsystem=s:s/component=s:c"
    with pytest.raises(RngError):
        KeyPath((("tail", "T1"), ("scenario", "S")))  # out of order
    with pytest.raises(RngError):
        KeyPath((("tail", "T1"), ("tail", "T2")))  # duplicate kind
    for bad in ({"tail": "has space"}, {"tail": True}, {"tail": -1}, {"subsystem": "Eng"}, {"colour": "x"}):
        with pytest.raises(RngError):
            KeyPath.of(**bad)
    # typed values: int 5 and str "5" are different identities
    assert component_words("event", 5) != component_words("event", "5")
    assert len(a.words()) == 4 * len(a.parts)


@pytest.mark.unit
def test_fixed_width_words_avoid_numpy_spawn_key_ambiguity():
    """Negative control: NumPy alone maps spawn_key (2**32,) and (0, 1) to the same stream."""
    ss = np.random.SeedSequence
    assert np.array_equal(
        ss(5, spawn_key=(2**32,)).generate_state(4), ss(5, spawn_key=(0, 1)).generate_state(4)
    )
    # our components are always 4 words, so a big int value can never alias two small ones
    big = KeyPath.of(event=2**32).words()
    two = KeyPath.of(job=0, event=1).words()
    assert len(big) == 4 and len(two) == 8 and big != two[:4]


@pytest.mark.unit
def test_registry_rejects_undeclared_names_and_wrong_identity():
    rng = RngService(ROOT, _reg())
    with pytest.raises(UndeclaredStreamError, match="did you mean"):
        rng.stream(_p(**{**FM, "component": "fuel_meter"}))  # typo-fork prevented
    with pytest.raises(RngError, match="keyed by"):
        rng.stream(_p(scenario="S1", tail="KH2011", sortie=3, subsystem="eng", component="fuel_metering"))
    reg = _reg()
    with pytest.raises(RngError, match="conflicting"):
        reg.declare(StreamDecl("eng", "fuel_metering", ("scenario",), Variate.NORMAL, 16))
    reg.declare(
        StreamDecl("eng", "fuel_metering", ("scenario", "tail", "serial", "sortie"), Variate.NORMAL, 16)
    )
    with pytest.raises(RngError):
        StreamDecl("eng", "x", ("tail", "scenario"))  # identity out of canonical order
    with pytest.raises(RngError):
        RngService(2**128, reg)


@pytest.mark.unit
def test_counter_addressing_is_order_independent():
    rng = RngService(ROOT, _reg(block=8))
    s = rng.stream(_p(**FM))
    full = s.draws(0, 100)
    assert np.array_equal(full, np.concatenate([s.block(b) for b in range(13)])[:100])
    for start, count in [(0, 1), (7, 2), (8, 8), (13, 40), (99, 1), (5, 0)]:
        assert np.array_equal(s.draws(start, count), full[start : start + count])
    # a fresh service, touching the stream from the far end first, gives the same values
    s2 = RngService(ROOT, _reg(block=8)).stream(_p(**FM))
    assert np.array_equal(s2.draws(64, 36), full[64:])
    assert np.array_equal(s2.draws(0, 64), full[:64])
    pos, out = 0, []
    for n in (3, 0, 10, 1):
        d, pos = s2.take(pos, n)
        out.append(d)
    assert np.array_equal(np.concatenate(out), full[:14]) and pos == 14
    # blocks are read-only so the memo cannot be corrupted by a consumer
    with pytest.raises(ValueError):
        s.block(0)[0] = 1.0


@pytest.mark.unit
def test_streams_are_distinct_and_variates_typed():
    rng = RngService(ROOT, _reg())
    a = rng.draws(_p(**FM), 0, 16)
    b = rng.draws(_p(**{**FM, "serial": "ESN-8"}), 0, 16)
    c = RngService(0x1, _reg()).draws(_p(**FM), 0, 16)  # another root
    assert not np.array_equal(a, b) and not np.array_equal(a, c)
    u = rng.draws(_p(scenario="S1", base="Leh", date="2026-10-14", subsystem="wx", component="gust"), 0, 1000)
    assert u.dtype == np.float64 and 0.0 <= u.min() and u.max() < 1.0
    r = rng.draws(_p(scenario="S1", tail="T", subsystem="bus", component="raw_bits"), 0, 4)
    assert r.dtype == np.uint64
    job = _p(scenario="S1", tail="T", job=42, subsystem="m18", component="repair_time")
    g1, g2 = rng.generator(job, 0), rng.generator(job, 1)
    assert g1.lognormal(1.0, 0.5) != g2.lognormal(1.0, 0.5)
    assert rng.generator(job, 0).lognormal(1.0, 0.5) == rng.generator(job, 0).lognormal(1.0, 0.5)
    with pytest.raises(RngError):
        rng.draws(job, 0, 1)
    with pytest.raises(RngError):
        rng.generator(_p(**FM), 0)


@pytest.mark.unit
def test_keys_project_identity_onto_declared_kinds():
    """An install-bias stream keyed by (scenario, serial) is the same in every sortie and tail."""
    rng = RngService(ROOT, _reg())
    k1 = rng.scope(KeyPath.of(scenario="S1", tail="KH2011", sortie=3))
    k2 = rng.scope(KeyPath.of(scenario="S1", tail="KH2012", sortie=9))
    b1 = k1.stream("eng", "install_bias", serial="ESN-7").draws(0, 4)
    b2 = k2.stream("eng", "install_bias", serial="ESN-7").draws(0, 4)
    assert np.array_equal(b1, b2)
    f1 = k1.stream("eng", "fuel_metering", serial="ESN-7").draws(0, 4)
    f2 = k2.stream("eng", "fuel_metering", serial="ESN-7").draws(0, 4)
    assert not np.array_equal(f1, f2)
    with pytest.raises(RngError, match="needs identity"):
        k1.stream("eng", "install_bias")


@pytest.mark.unit
def test_ledger_and_crn_audit_detect_divergent_consumption():
    def consume(ledger, extra_index):
        rng = RngService(ROOT, _reg(), ledger=ledger)
        s = rng.stream(_p(**FM))
        s.draws(0, 10)
        s.draws(extra_index, 1)
        rng.generator(_p(scenario="S1", tail="T", job=1, subsystem="m18", component="repair_time"), 0)

    la, lb, lc = DrawLedger(), DrawLedger(), DrawLedger()
    consume(la, 20)
    consume(lb, 20)
    consume(lc, 21)
    ok = crn_audit(la, lb)
    assert ok.ok and len(ok.identical) == 2 and la.digest() == lb.digest()
    bad = crn_audit(la, lc)
    assert not bad.ok and bad.consumption_differs == (f"{_p(**FM)}#NORMAL",)
    # values at shared indices can only differ if the mapping differs (e.g. another root): audit sees it
    ld = DrawLedger()
    RngService(0x2, _reg(), ledger=ld).stream(_p(**FM)).draws(0, 10)
    le = DrawLedger()
    RngService(ROOT, _reg(), ledger=le).stream(_p(**FM)).draws(0, 10)
    assert crn_audit(ld, le).values_differ == (f"{_p(**FM)}#NORMAL",)


@pytest.mark.unit
def test_sequential_generator_state_round_trips():
    rng = RngService(ROOT, _reg())
    job = _p(scenario="S1", tail="T", job=7, subsystem="m18", component="repair_time")
    g = rng.generator(job, 0)
    g.standard_normal(5)
    g.integers(0, 10, 3)
    tree = generator_state_tree(g)
    g2 = generator_from_state_tree(tree)
    assert np.array_equal(g.standard_normal(7), g2.standard_normal(7))
    assert g.random() == g2.random()


@pytest.mark.unit
def test_describe_records_mapping_and_registry():
    d = RngService(ROOT, _reg()).describe()
    assert d["mapping_version"] == 1 and d["bit_generator"] == "Philox"
    assert d["root_hex"] == f"{ROOT:032x}"
    assert d["registry_digest"] == _reg().digest() != _reg(block=32).digest()
