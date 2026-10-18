"""PREVIEW v0.9 builder (``tools/build_preview.py``): the saved sample, the per-file contract validation, the
consumer/restricted separation and the download-instant rule.

These are fast checks of the tool itself (no sortie is flown; n = 0 sorties). The dataset's own checks
(every file validated, leak audit, determinism by regeneration) run in the tool and are recorded in
``docs/previews/v0.9_MANIFEST.json``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from phalanx.dictionary.contract import load_contract
from phalanx.dictionary.contract.examples import example_records
from phalanx.streaming.parquet_store import ParquetStore

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
C = load_contract("v0")


def _tool():
    spec = importlib.util.spec_from_file_location("build_preview", ROOT / "tools" / "build_preview.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _tool()


def test_sample_is_minimal_diverse_and_saved():
    """5-20 sorties on distinct tails, at least 5 mission types, the full-path sortie among them; the fleet is
    8 tails x 90-180 days (the brief's bounds)."""
    from phalanx.integration.plans import gate_sorties

    n = len(T.TELEMETRY_SORTIES)
    assert 5 <= n <= 20
    plans = {p.sortie_id: p for p in gate_sorties(days=T.PLAN_DAYS)}
    assert set(T.TELEMETRY_SORTIES) <= set(plans)
    assert len({plans[s].tail for s in T.TELEMETRY_SORTIES}) == n
    assert len({int(plans[s].mission_type) for s in T.TELEMETRY_SORTIES}) >= 5
    assert T.FULL_PATH_SORTIE in T.TELEMETRY_SORTIES
    assert T.FLEET_TAILS == 8 and 90 <= T.FLEET_DAYS <= 180
    assert T.TELEMETRY_ROOT == 0xA5 and T.TELEMETRY_SCENARIO == "gate"  # the gate plan's identity


def _store(tmp_path: Path) -> ParquetStore:
    return ParquetStore(tmp_path / "tree", C, restricted_root=tmp_path / "_restricted_labels" / "tree")


def test_validate_tree_accepts_store_output_and_counts_rows(tmp_path):
    s = _store(tmp_path)
    s.write("events.bit_faults", example_records(C, "events.bit_faults", 3))
    s.write("sortie.manifest", example_records(C, "sortie.manifest", 2))
    s.write("labels.truth", example_records(C, "labels.truth", 4))
    got = T.validate_tree(tmp_path / "tree", restricted=False)
    assert got["events.bit_faults"]["rows"] == 3 and got["sortie.manifest"]["rows"] == 2
    assert "labels.truth" not in got  # truth never reaches the consumer tree
    res = T.validate_tree(tmp_path / "_restricted_labels" / "tree", restricted=True)
    assert res["labels.truth"]["rows"] == 4 and res["sortie.manifest"]["rows"] == 2


def test_validate_tree_rejects_restricted_data_in_a_consumer_tree(tmp_path):
    """Negative controls: a labels.truth file planted in the consumer tree, and a consumer file carrying the
    restricted manifest columns."""
    d = tmp_path / "tree" / "labels.truth" / "date=2026-01-05"
    d.mkdir(parents=True)
    pq.write_table(example_records(C, "labels.truth", 2), d / "part-0.parquet")
    with pytest.raises(PermissionError):
        T.validate_tree(tmp_path / "tree", restricted=False)
    d2 = tmp_path / "tree2" / "sortie.manifest" / "date=2026-01-05"
    d2.mkdir(parents=True)
    pq.write_table(example_records(C, "sortie.manifest", 1), d2 / "part-0.parquet")  # full schema
    with pytest.raises(ValueError, match="consumer schema"):
        T.validate_tree(tmp_path / "tree2", restricted=False)


def test_validate_tree_runs_the_contract_validator(tmp_path):
    """A consumer-schema file whose rows break a contract invariant (duplicate record_id) is rejected."""
    t = example_records(C, "events.bit_faults", 2)
    rid = t.column("record_id")[0]
    t = t.set_column(0, t.schema.field("record_id"), pa.array([rid.as_py()] * 2, t.schema.field(0).type))
    d = tmp_path / "tree" / "events.bit_faults" / "date=2026-01-05"
    d.mkdir(parents=True)
    pq.write_table(t.cast(C.consumer_schema("events.bit_faults")), d / "part-0.parquet")
    with pytest.raises(Exception, match="record_id"):
        T.validate_tree(tmp_path / "tree", restricted=False)


def test_download_ingest_is_keyed_and_after_the_recorder_stop():
    """t_ingest comes from M16's download model (first complete delivery), keyed by the sortie identity:
    deterministic, after t_end, and different for another sortie."""
    from phalanx.bus.clocks import SortieIdentity

    a = SortieIdentity(scenario="gate", tail_no="TJ201", sortie_id="TJ201-20260106T0300")
    b = SortieIdentity(scenario="gate", tail_no="TJ212", sortie_id="TJ212-20260105T0300")
    t_end = 1_767_667_869_994_790_139
    t1, d1 = T._download_ingest(a, t_end)
    t2, _ = T._download_ingest(a, t_end)
    t3, _ = T._download_ingest(b, t_end)
    assert t1 == t2 > t_end and t3 != t1
    assert any(x["complete"] and x["t_ingest"] == t1 for x in d1)
