"""W0.4 deliverable 8: toy end-to-end. A small EXAMPLE CIR batch -> fast path -> Parquet -> replay, bitwise
stable across runs and across a fresh interpreter.

Sample: 2 tails x 1 sortie x 3 streams x 40 samples (240 records) plus their truth labels and manifests. Two
sorties is the minimum that shows burst interleaving; 40 samples per stream spans several 10 Hz / 50 Hz ticks
of every stream. The digest covers every stored file and every replayed batch (Arrow IPC bytes).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pytest

E = 1_791_000_000 * 10**9
H = 3600 * 10**9


def run_e2e(root: Path) -> dict:
    from phalanx.dictionary.contract import load_contract
    from phalanx.dictionary.contract.examples import example_records
    from phalanx.ground import FastPathConfig, cir_to_param_samples, cir_to_truth_labels
    from phalanx.ground.examples import example_cir_batch, example_units
    from phalanx.streaming import ObservationView, ParquetStore, ReplayBatch, ReplayStreamer, Watermark

    c = load_contract("v0")
    cfg = FastPathConfig("0.1.0", "ab" * 32, example_units(), {"ENG.N2": "E1", "ENG.EGT": "E1"})
    store = ParquetStore.at(root, c)
    for tail, sortie, ingest in (("T001", "T001-S1", E + 5 * H), ("T002", "T002-S1", E + 3 * H)):
        batch = example_cir_batch(tail, sortie, E, 40)
        store.write("param.samples", cir_to_param_samples(batch, cfg, t_ingest=ingest), date="2026-10-03")
        store.write("labels.truth", cir_to_truth_labels(batch, cfg), date="2026-10-03")
    store.write("sortie.manifest", example_records(c, "sortie.manifest", 2))
    h = hashlib.blake2b()
    files = sorted(p for p in root.rglob("*.parquet"))
    for p in files:
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    file_digest = h.hexdigest()
    h = hashlib.blake2b()
    n_batches = n_marks = n_rows = 0
    for item in ReplayStreamer(store):
        if isinstance(item, ReplayBatch):
            n_batches += 1
            n_rows += item.table.num_rows
            sink = pa.BufferOutputStream()
            with pa.ipc.new_stream(sink, item.table.schema) as w:
                w.write_table(item.table)
            h.update(item.topic.encode() + item.t_ingest.to_bytes(8, "little"))
            h.update(sink.getvalue().to_pybytes())
        elif isinstance(item, Watermark):
            n_marks += 1
            h.update(f"{item.tail_no}/{item.sortie_id}/{item.t_ingest}/{item.event_time}".encode())
    view = ObservationView(store)
    return {
        "files": len(files),
        "file_digest": file_digest,
        "replay_digest": h.hexdigest(),
        "batches": n_batches,
        "watermarks": n_marks,
        "rows": n_rows,
        "as_of_4h": view.as_of(E + 4 * H, "param.samples").num_rows,
        "as_of_6h": view.as_of(E + 6 * H, "param.samples").num_rows,
    }


@pytest.mark.integration
@pytest.mark.determinism
def test_toy_end_to_end_bitwise_stable(tmp_path, repo_root):
    a = run_e2e(tmp_path / "a")
    b = run_e2e(tmp_path / "b")
    assert a == b
    # consumer tree: samples x2 sorties, manifests x2; restricted tree: labels x2, manifest seed parts x2
    assert a["files"] == 2 + 2 + 2 + 2
    assert a["rows"] == 240 + 2  # param.samples + manifests (labels are restricted: not streamed)
    assert a["batches"] == 4 and a["watermarks"] == 4
    assert (a["as_of_4h"], a["as_of_6h"]) == (120, 240)  # T002 arrives at +3 h, T001 at +5 h
    code = (
        "import sys, json; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2]);"
        "from pathlib import Path; import test_streaming_toy_e2e as m;"
        "print(json.dumps(m.run_e2e(Path(sys.argv[3]))))"
    )
    out = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(repo_root / "src"),
            str(Path(__file__).parent),
            str(tmp_path / "c"),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert json.loads(out) == a
