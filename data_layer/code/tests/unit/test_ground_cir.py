"""W0.4 deliverable 3: the CIR definition and its validation (negative tests show each rule bites).

Sample: the EXAMPLE batch of 3 streams x 6 samples (n = 18), the smallest that has a redundant pair (lanes
A/B) and a simplex stream, so per-stream rules are exercised across streams.
"""

from __future__ import annotations

import pyarrow as pa
import pytest

from phalanx.dictionary.contract import load_contract
from phalanx.ground import CIR_SCHEMA, CirBatch, CirViolation, assign_sample_index, validate_cir
from phalanx.ground.examples import example_cir_batch

C = load_contract("v0")
EPOCH = 1_791_000_000 * 10**9


def _batch() -> CirBatch:
    return example_cir_batch("T001", "T001-S1", EPOCH, 6)


def _set(table: pa.Table, name: str, values: list) -> pa.Table:
    i = table.schema.get_field_index(name)
    return table.set_column(i, table.schema.field(i), pa.array(values, type=table.schema.field(i).type))


@pytest.mark.unit
def test_cir_schema_columns_and_restricted_truth():
    assert CIR_SCHEMA.names == [
        "param_id",
        "source_lru",
        "lane",
        "sample_index",
        "t_true",
        "t_sample",
        "value",
        "truth_value",
        "validity",
        "quality_flags",
        "rng_key_path",
    ]
    assert CIR_SCHEMA.field("truth_value").metadata[b"phalanx.restricted"] == b"true"
    assert CIR_SCHEMA.field("t_sample").metadata[b"phalanx.time_unit"] == b"ns"
    b = _batch()
    b.validate(C)  # positive control
    assert b.table.num_rows == 18


def _first(t: pa.Table, name: str, v) -> pa.Table:
    return _set(t, name, [v, *t.column(name).to_pylist()[1:]])


def _reverse_times(t: pa.Table) -> pa.Table:
    t = _set(t, "t_sample", list(reversed(t.column("t_sample").to_pylist())))
    return _set(t, "t_true", list(reversed(t.column("t_true").to_pylist())))


QF = C.quality_flags
CASES = {
    "NaN value": (lambda t: _first(t, "value", float("nan")), "value: 1 NaN"),
    "NaN truth": (lambda t: _first(t, "truth_value", float("nan")), "truth_value: 1 NaN"),
    "t_true after t_sample": (
        lambda t: _set(t, "t_true", [v + 1 for v in t.column("t_sample").to_pylist()]),
        "t_true > t_sample",
    ),
    "duplicate sample_index": (
        lambda t: _set(t, "sample_index", [0] * t.num_rows),
        "sample_index not unique",
    ),
    "time not increasing": (_reverse_times, "not strictly increasing"),
    "ground flag in CIR": (
        lambda t: _first(t, "quality_flags", QF.mask("DUPLICATE_DOWNLOAD")),
        "acquisition scope",
    ),
    "bus flag in CIR": (lambda t: _first(t, "quality_flags", QF.mask("DUPLICATE_POLL")), "acquisition scope"),
    "reserved flag in CIR": (lambda t: _first(t, "quality_flags", 1 << 31), "acquisition scope"),
    "colon in LRU": (lambda t: _first(t, "source_lru", "FA:DEC"), "source_lru: 1 value(s)"),
    "empty lane": (lambda t: _first(t, "lane", ""), "lane: 1 value(s)"),
    "bad validity": (lambda t: _first(t, "validity", "GOOD"), "validity: values outside"),
    "null in non-null": (lambda t: _first(t, "param_id", None), "param_id: 1 null"),
    "negative time": (lambda t: _first(t, "t_true", -1), "times must be >= 0"),
    "missing column": (lambda t: t.drop_columns(["rng_key_path"]), "columns"),
    "key path not a KeyPath": (lambda t: _first(t, "rng_key_path", "example/T001/N2"), "rng_key_path"),
    "key path kinds out of order": (
        lambda t: _first(t, "rng_key_path", "tail=s:T001/scenario=s:S1"),
        "rng_key_path",
    ),
    "key path unknown kind": (lambda t: _first(t, "rng_key_path", "planet=s:X"), "rng_key_path"),
    "key path non-canonical int": (
        lambda t: _first(t, "rng_key_path", "scenario=s:S1/sortie=i:007"),
        "canonical",
    ),
}


@pytest.mark.unit
@pytest.mark.parametrize("case", sorted(CASES))
def test_cir_violations_rejected(case):
    mutate, expect = CASES[case]
    with pytest.raises(CirViolation) as ei:
        validate_cir(C, mutate(_batch().table))
    assert any(expect in e for e in ei.value.errors), ei.value.errors


@pytest.mark.unit
def test_cir_acquisition_flags_allowed():
    t = _batch().table
    allowed = C.quality_flags.mask(
        "SENTINEL", "GATED", "HELD_STALE", "SUBSTITUTED", "VOTED_OUT", "OUT_OF_RANGE"
    )
    validate_cir(C, _set(t, "quality_flags", [allowed] * t.num_rows))


@pytest.mark.unit
def test_cir_batch_identity_checked():
    with pytest.raises(CirViolation):
        CirBatch("T/1", "S1", _batch().table).validate(C)


@pytest.mark.unit
def test_assign_sample_index_ranks_within_stream():
    t = _batch().table
    shuffled = t.take(pa.array([17, 3, 9, 0, 12, 5, 1, 16, 8, 2, 14, 6, 4, 11, 15, 7, 10, 13]))
    zeroed = _set(shuffled, "sample_index", [0] * shuffled.num_rows)
    fixed = assign_sample_index(zeroed)
    validate_cir(C, fixed)
    assert fixed.column("sample_index").to_pylist() == shuffled.column("sample_index").to_pylist()


@pytest.mark.unit
def test_cir_rng_key_path_carries_a_core_keypath():
    """rng_key_path is KeyPath.canonical() (AD-37) and round-trips exactly; null is allowed."""
    from phalanx.core.rng import KeyPath
    from phalanx.ground.cir import key_path_text, parse_key_path

    kp = KeyPath.of(scenario="S1", tail="T001", sortie=3, subsystem="acquisition", sensor="FADEC.ENG.N2.A")
    text = key_path_text(kp)
    assert text == "scenario=s:S1/tail=s:T001/sortie=i:3/subsystem=s:acquisition/sensor=s:FADEC.ENG.N2.A"
    assert parse_key_path(text) == kp
    t = _batch().table
    for v in set(t.column("rng_key_path").to_pylist()):
        assert key_path_text(parse_key_path(v)) == v
    validate_cir(C, _set(t, "rng_key_path", [text] * t.num_rows))
    validate_cir(C, _set(t, "rng_key_path", [None] * t.num_rows))


# ---- builder for M13: per-stream sampled outputs -> CIR (E0 verifier item 5) -----------------------------
def _streams():
    import numpy as np

    from phalanx.core.rng import KeyPath
    from phalanx.ground import StreamSamples

    a = StreamSamples(  # 5 samples, truth everywhere, t_true defaults to t_sample
        "ENG.N2",
        "FADEC",
        "A",
        sample_index=np.arange(5),
        t_sample=EPOCH + np.arange(5) * 20_000_000,
        value=np.array([90.0, 90.1, 90.2, 90.3, 90.4]),
        truth_value=np.array([90.01, 90.11, 90.21, 90.31, 90.41]),
        rng_key_path=KeyPath.of(scenario="S1", tail="T001", sensor="FADEC.ENG.N2.A"),
    )
    b = StreamSamples(  # 3 samples, truth missing on one (mask, not NaN), per-sample validity and flags
        "ENG.EGT",
        "ECMS",
        None,
        sample_index=np.array([7, 8, 9]),
        t_sample=EPOCH + np.array([7, 8, 9]) * 100_000_000,
        value=np.array([650.0, 651.0, 652.0]),
        t_true=EPOCH + np.array([7, 8, 9]) * 100_000_000 - 12_500_000,
        truth_value=np.array([649.9, 0.0, 651.9]),
        truth_present=np.array([True, False, True]),
        validity=np.array(["NORMAL", "NO_COMPUTED_DATA", "NORMAL"]),
        quality_flags=np.array([0, C.quality_flags.mask("HELD_STALE"), 0]),
    )
    return a, b


@pytest.mark.unit
def test_cir_from_streams_builds_a_valid_batch_with_explicit_counts():
    from phalanx.ground import cir_from_streams

    a, b = _streams()
    batch = cir_from_streams(C, "T001", "T001-S1", [a, b])
    t = batch.table
    assert t.num_rows == 8  # 5 + 3: each stream keeps its own count, no padding
    rows = t.to_pylist()
    assert all(r["t_true"] == r["t_sample"] for r in rows[:5])  # default rule: truth at the LRU tick
    assert rows[5]["t_true"] == rows[5]["t_sample"] - 12_500_000  # explicit earlier physics instant
    assert [r["truth_value"] for r in rows[5:]] == [649.9, None, 651.9]  # null, never NaN
    assert [r["validity"] for r in rows[5:]] == ["NORMAL", "NO_COMPUTED_DATA", "NORMAL"]
    assert rows[0]["rng_key_path"] == "scenario=s:S1/tail=s:T001/sensor=s:FADEC.ENG.N2.A"
    assert rows[5]["rng_key_path"] is None and rows[5]["lane"] is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "why",
    [
        "count mismatch",
        "NaN value",
        "t_true after t_sample",
        "mask without truth",
        "negative index",
        "ground flag",
    ],
)
def test_cir_from_streams_rejects_bad_streams(why):
    import dataclasses

    import numpy as np

    from phalanx.ground import cir_from_streams

    a, b = _streams()
    bad = {
        "count mismatch": dataclasses.replace(a, value=np.array([1.0, 2.0])),
        "NaN value": dataclasses.replace(a, value=np.array([1.0, np.nan, 3.0, 4.0, 5.0])),
        "t_true after t_sample": dataclasses.replace(a, t_true=a.t_sample + 1),
        "mask without truth": dataclasses.replace(a, truth_value=None, truth_present=np.ones(5, dtype=bool)),
        "negative index": dataclasses.replace(a, sample_index=np.array([-1, 0, 1, 2, 3])),
        "ground flag": dataclasses.replace(a, quality_flags=C.quality_flags.mask("DUPLICATE_DOWNLOAD")),
    }[why]
    with pytest.raises(CirViolation):
        cir_from_streams(C, "T001", "T001-S1", [bad, b])


@pytest.mark.unit
def test_truth_at_samples_interpolates_on_the_ad35_grid():
    from fractions import Fraction

    import numpy as np

    from phalanx.ground import truth_at_samples

    k0 = 100
    x = 3.0 * np.arange(k0, k0 + 500)  # truth = 3 * k (linear in the step index)
    t = EPOCH + np.array([(k0 * 10**9) // 240, 425_000_000, 1_000_000_000, 1_234_567_891])
    got = truth_at_samples(t, x, epoch_ns=EPOCH, k0=k0)
    exact = [float(Fraction(3 * 240 * int(ti - EPOCH), 10**9)) for ti in t]
    assert got[0] == 3.0 * k0  # exactly on a truth step: w == 0
    # step instants are floored to ns, so the interpolant differs from 3*240*t by < 3*240 ns-equivalents
    assert np.allclose(got[1:], exact[1:], rtol=0, atol=3 * 240 * 1e-9)
    with pytest.raises(ValueError):
        truth_at_samples(np.array([EPOCH]), x, epoch_ns=EPOCH, k0=k0)  # before the series
    last = EPOCH + ((k0 + 499) * 10**9) // 240
    assert truth_at_samples(np.array([last]), x, epoch_ns=EPOCH, k0=k0)[0] == 3.0 * (k0 + 499)
    with pytest.raises(ValueError):
        truth_at_samples(np.array([last + 1]), x, epoch_ns=EPOCH, k0=k0)  # would need x[k+1]


@pytest.mark.unit
def test_cir_from_streams_feeds_the_fast_path():
    from phalanx.ground import FastPathConfig, cir_from_streams, cir_to_param_samples

    a, b = _streams()
    batch = cir_from_streams(C, "T001", "T001-S1", [a, b])
    cfg = FastPathConfig("0.1.0", "ab" * 32, {"ENG.N2": "percent", "ENG.EGT": "degC"})
    out = cir_to_param_samples(batch, cfg, t_ingest=EPOCH + 3600 * 10**9)
    C.validate("param.samples", out)
    assert out.num_rows == 8
