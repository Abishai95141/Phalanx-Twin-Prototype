"""Fast path bound to the real M01 dictionary (E0 verifier item 2): unknown channels are rejected; values
outside the channel's dictionary range are flagged OUT_OF_RANGE (kept, not dropped or clipped).

Sample: real Tejas recorded channels ENG.N2.V (range 0-110 %), ENG.A8.V and ENG.N1.V on FADEC (AV-MUX-2), 4
samples per stream (n = 12): the smallest batch with three measurands of one LRU. AD-54 (W2.2): the fast path
emits only channels with a full-path transport, so the FADEC internal lanes (ENG.N2.A/B, ENG.N1.A) are
accepted as dictionary channels but not emitted (``test_internal_lanes_are_accepted_but_not_emitted``).
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc
import pytest

from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.ground import CirBatch, FastPathConfig, cir_to_param_samples
from phalanx.ground.examples import example_cir_batch

C = load_contract("v0")
D = load_dictionary()
E = 1_791_000_000 * 10**9
INGEST = E + 3600 * 10**9
OOR = C.quality_flags.mask("OUT_OF_RANGE")
SENTINEL = C.quality_flags.mask("SENTINEL")
STREAMS = (
    ("ENG.N2", "FADEC", "V", 50, "percent"),
    ("ENG.A8", "FADEC", "V", 50, "percent"),
    ("ENG.N1", "FADEC", "V", 50, "percent"),
)
INTERNAL_LANES = (
    ("ENG.N2", "FADEC", "A", 50, "percent"),
    ("ENG.N2", "FADEC", "B", 50, "percent"),
    ("ENG.N1", "FADEC", "A", 50, "percent"),
)


@pytest.fixture(scope="module")
def cfg() -> FastPathConfig:
    return FastPathConfig.from_dictionary(D, engine_serial="E404-IN20-0001")


def _batch(streams=STREAMS) -> CirBatch:
    return example_cir_batch("T001", "T001-S1", E, 4, streams=streams)


def _with(batch: CirBatch, name: str, row: int, value) -> CirBatch:
    t = batch.table
    i = t.schema.get_field_index(name)
    vals = t.column(name).to_pylist()
    vals[row] = value
    return CirBatch(
        batch.tail_no,
        batch.sortie_id,
        t.set_column(i, t.schema.field(i), pa.array(vals, t.schema.field(i).type)),
    )


@pytest.mark.unit
def test_config_from_dictionary(cfg):
    assert (cfg.dict_version, cfg.dict_hash) == (D.dict_version, D.dict_hash)
    assert cfg.units == D.units_map()
    assert cfg.channels[("ENG.N2", "FADEC", "A")] == (0, 110)
    assert len(cfg.channels) == sum(1 for _ in D.channels())
    assert cfg.engine_serial["ENG.N2"] == "E404-IN20-0001"
    # engine measurands and per-engine usage counters (LUIs, TAC) get the serial; nothing else does
    assert all(p.startswith(("ENG.", "LUI.", "USAGE.TAC")) for p in cfg.engine_serial)
    assert "LUI.TYPE3" in cfg.engine_serial and not any(
        p.startswith(("AD.", "FCS.")) for p in cfg.engine_serial
    )
    explicit = FastPathConfig.from_dictionary(D, engine_serial={"ENG.N2": "X"})
    assert dict(explicit.engine_serial) == {"ENG.N2": "X"}


@pytest.mark.unit
def test_internal_lanes_are_accepted_but_not_emitted(cfg):
    """AD-54: LRU-internal lanes are dictionary channels (no rejection) without a full-path transport, so the
    fast path drops them from param.samples (and their truth labels); the recorded words stay."""
    from phalanx.ground import cir_to_truth_labels

    both = example_cir_batch("T001", "T001-S1", E, 4, streams=STREAMS + INTERNAL_LANES)
    out = cir_to_param_samples(both, cfg, t_ingest=INGEST)
    assert out.num_rows == 12 and set(out.column("lane").to_pylist()) == {"V"}
    assert cir_to_truth_labels(both, cfg).num_rows <= 12
    assert all(k not in cfg.visible for k in (s[:3] for s in INTERNAL_LANES))
    assert all(k in cfg.channels for k in (s[:3] for s in INTERNAL_LANES))


@pytest.mark.unit
def test_dictionary_channels_pass_unflagged(cfg):
    out = cir_to_param_samples(_batch(), cfg, t_ingest=INGEST)
    C.validate("param.samples", out)
    assert out.num_rows == 12
    assert not pc.any(pc.not_equal(out.column("quality_flags"), 0)).as_py()
    assert set(out.column("units").to_pylist()) == {"percent"}
    assert set(out.column("engine_serial").to_pylist()) == {"E404-IN20-0001"}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("why", "streams"),
    [
        ("lane not in the dictionary", (("ENG.N2", "FADEC", "Z", 50, "percent"),)),
        ("wrong LRU for the measurand", (("ENG.N2", "DFCC", "A", 50, "percent"),)),
        ("lane missing on a redundant channel", (("ENG.N2", "FADEC", None, 50, "percent"),)),
        ("unknown measurand", (("ENG.NOPE", "FADEC", "A", 50, "percent"),)),
    ],
)
def test_channels_not_in_the_dictionary_are_rejected(cfg, why, streams):
    with pytest.raises((ValueError, KeyError), match=r"not dictionary channels|no units"):
        cir_to_param_samples(_batch(streams), cfg, t_ingest=INGEST)


@pytest.mark.unit
@pytest.mark.parametrize(("row", "value"), [(1, 1e6), (2, -5.0), (3, 110.0 + 1e-9)])
def test_out_of_range_values_are_flagged_not_dropped(cfg, row, value):
    out = cir_to_param_samples(_with(_batch(), "value", row, value), cfg, t_ingest=INGEST)
    assert out.num_rows == 12  # kept
    flags = out.column("quality_flags").to_pylist()
    vals = out.column("value_eu").to_pylist()
    i = vals.index(value)  # the value is carried unchanged (no clipping)
    assert flags[i] == OOR
    assert all(f == 0 for j, f in enumerate(flags) if j != i)
    assert out.column("validity").to_pylist()[i] == "NORMAL"  # a decoder-side quality flag, not a validity


@pytest.mark.unit
def test_boundaries_are_in_range_and_flags_are_ored(cfg):
    b = _with(_with(_batch(), "value", 0, 0.0), "value", 1, 110.0)  # both bounds are inside the range
    out = cir_to_param_samples(b, cfg, t_ingest=INGEST)
    assert not pc.any(pc.not_equal(out.column("quality_flags"), 0)).as_py()
    b = _with(_with(_batch(), "value", 1, 500.0), "quality_flags", 1, SENTINEL)
    out = cir_to_param_samples(b, cfg, t_ingest=INGEST)
    assert sorted(out.column("quality_flags").to_pylist())[-1] == SENTINEL | OOR


@pytest.mark.unit
def test_channels_without_a_dictionary_range_are_not_range_checked(cfg):
    ch = next(ch for ch in D.channels() if not ch["range"] and ch["lane"] in ("A", "") and ch["units"])
    loc = D.contract_location(ch["channel_id"])
    stream = ((loc["param_id"], loc["source_lru"], loc["lane"], 10, loc["units"]),)
    out = cir_to_param_samples(_with(_batch(stream), "value", 0, 1e12), cfg, t_ingest=INGEST)
    assert out.column("quality_flags").to_pylist() == [0, 0, 0, 0]
