"""Phase 1-A: release gate, as-of store, twin state and event log against the film's 22 Jun values.

Runs on the Mac (preview Parquet) and on the LinuxONE server (preview IPC copy, PHX_PREVIEW_FLEET):
    python -m pytest proto/tests/test_phase1a.py -q
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import pyarrow as pa
import pytest

PROTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROTO / "ground"))

from gate import Gate, RestrictedPathError, read_schema, read_table  # noqa: E402
from lel import EventLog  # noqa: E402
from store import PREVIEW_FLEET, Root, Store  # noqa: E402
from twin import IST, MC_STATES, Twin  # noqa: E402

T = int(dt.datetime(2026, 6, 22, 6, tzinfo=IST).timestamp()) * 10**9
G = json.loads((PROTO / "tests" / "golden_0622.json").read_text())


@pytest.fixture(scope="module")
def store() -> Store:
    return Store.for_preview()


@pytest.fixture(scope="module")
def twin(store: Store) -> Twin:
    return Twin(store)


def test_store_counts(store: Store) -> None:
    assert not store.rejected
    assert store.as_of(T, "maint.records").num_rows == G["maint_rows"]
    assert store.as_of(T, "events.bit_faults").num_rows == G["bit"]
    assert store.as_of(T, "events.cautions").num_rows == G["cautions"]
    assert store.as_of(T, "usage.counters").num_rows == G["counters"]


def test_as_of_never_returns_future_rows(store: Store) -> None:
    for topic in ("maint.records", "events.bit_faults", "usage.counters"):
        d = store.df(T, topic)
        assert int(d[store.ingest_col[topic]].max()) <= T


def test_colliding_record_ids_stay_apart(store: Store) -> None:
    d = store.df(T, "maint.records")
    d = d[d.tail_no.notna()]
    per_id = d.groupby("rid").tail_no.nunique()
    assert (per_id > 1).sum() > 0  # the preview's 8 worlds reuse record ids …
    assert len(d) == len(d.drop_duplicates(["tail_no", "rid"]))  # … and scoped dedupe keeps each world's row


def test_shop_findings_linked_as_of(store: Store) -> None:
    sf = store.shop_findings(T)
    assert len(sf) == G["shop"]["rows"]
    assert int(sf.linked.sum()) == G["shop"]["linked_asof"]
    assert set(sf[sf.linked].shop_finding) == {"RTOK"}


def test_readiness_kpis(twin: Twin) -> None:
    fs = twin.fleet(T)
    for k, v in G["kpis_d30"].items():
        assert fs.kpis_30d[k] == pytest.approx(v, abs=5e-4)
    for k, v in G["kpis_all"].items():
        assert fs.kpis_all[k] == pytest.approx(v, abs=5e-4)
    assert fs.funnel["alert_rows"] == G["alert_rows"]
    states = [twin.state_at(T, T)[t][0] for t in fs.tails]
    assert sum(s in MC_STATES for s in states) == 6


def test_fleet_rows_equal_film(twin: Twin) -> None:
    fs = twin.fleet(T)
    ours = {r["tail"]: r for r in (twin.fleet_row(T, ts) for ts in fs.tails.values())}
    over = G.get("fleet_overrides", {})  # documented differences from the film (see fleet_overrides_note)
    for film in G["fleet"]:
        mine = ours[film["tail"]]
        for k, v in {**film, **over.get(film["tail"], {})}.items():
            assert mine[k] == (pytest.approx(v) if isinstance(v, float) else v), (film["tail"], k)


def test_tj107(twin: Twin) -> None:
    g = G["tj107"]
    ts = twin.tail(T, "TJ107")
    assert (ts.sorties, ts.flight_hours, ts.landings) == (g["sorties"], g["fh"], g["landings"])
    assert twin.sorties_with_code(T, "TJ107", "HYD-101") == (g["hyd101_sorties"], g["sorties"])
    assert twin.removals(T, "TJ107", "SYN-PN-HYDP") == g["pump_removals"]
    hyd = next(a for a in ts.alarms if a.code == "HYD-101")
    assert hyd.consecutive_sorties == g["hyd101_consecutive"]
    pumps = {i.position: [i.serial_no, i.inferred] for i in ts.installed if i.part_no == "SYN-PN-HYDP"}
    assert pumps == g["pumps"]


def _copy_one(store: Store, tmp: Path) -> tuple[Path, Path]:
    src = store.files["orders.commands"][0][0]
    root = tmp / "fleet"
    dst = root / "orders.commands" / src.name
    dst.parent.mkdir(parents=True)
    shutil.copy(src, dst)
    return root, dst


def test_gate_rejects_wrong_contract_hash(store: Store, tmp_path: Path) -> None:
    root, dst = _copy_one(store, tmp_path)
    t = read_table(dst)
    md = dict(t.schema.metadata)
    md[b"phalanx.contract_hash"] = b"0" * 64
    bad = root / "orders.commands" / ("part-00000000000000000001-bad." + dst.suffix.lstrip("."))
    t = t.replace_schema_metadata(md)
    if dst.suffix == ".arrow":
        with pa.OSFile(str(bad), "wb") as sink, pa.ipc.new_file(sink, t.schema) as w:
            w.write_table(t)
    else:
        import pyarrow.parquet as pq

        pq.write_table(t, bad)
    assert read_schema(bad).metadata[b"phalanx.contract_hash"] == b"0" * 64
    res = Gate().check(bad, "orders.commands")
    assert not res.accepted and "not allowlisted" in res.reason
    s = Store([Root(root)])
    assert len(s.rejected) == 1 and s.as_of(2**62, "orders.commands").num_rows > 0


def test_restricted_paths_refused(tmp_path: Path) -> None:
    with pytest.raises(RestrictedPathError):
        Store([Root(PREVIEW_FLEET.parent / "_restricted_labels" / "fleet")])


def test_event_log_chain(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "lel.sqlite")
    for i in range(3):
        log.append("SNAPSHOT_SEALED", "epoch:test", {"i": i, "rid": bytes([i]) * 4}, T)
    assert log.verify()["ok"] and log.verify()["events"] == 3
    log.db.execute("UPDATE events SET payload_json = '{\"i\":99}' WHERE seq = 2")
    v = log.verify()
    assert not v["ok"] and v["broken_at"] == 2


def test_ground_never_imports_the_data_layer() -> None:
    for py in (PROTO / "ground").rglob("*.py"):
        if ".venv" in py.parts:
            continue
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for n in names:
                assert not n.startswith(("phalanx", "eval", "proto.eval")), f"{py}: imports {n}"
