"""W0.X integration: M01 dictionary ↔ W0.4 contract ↔ W0.2 core, wired end to end (coordinator).

Covers what no single WP could test on its own:
  1. docs/contract/ is exactly what M01's build produces with the contract generator hooked in.
  2. A CIR batch built from *real* dictionary channels goes through the fast path → two-tree store → consumer
     replay. Every record carries the dictionary's version and hash; param_id, units, LRU and lane agree with
     `contract_location`; the consumer tree holds no truth values (leak audit); and the run is bitwise
     reproducible.
  3. Dictionary ParamSets are core ParamSets with stable hashes.
Sample: 2 real params (ENG.N2 on FADEC lanes A/B/V, ENG.T5), 40 samples per stream, 1 sortie. This is the
smallest set that covers a redundant multi-lane measurand, a single-channel measurand and a bus-transported
voted channel.
"""

from __future__ import annotations

import filecmp
import hashlib
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pytest

from phalanx.core.module import ParamSet
from phalanx.core.rng import KeyPath
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.ground import FastPathConfig, cir_to_param_samples
from phalanx.ground.cir import CIR_SCHEMA, CirBatch, key_path_text
from phalanx.ground.fast_path import cir_to_truth_labels
from phalanx.streaming import ParquetStore, ReplayStreamer, audit_consumer_tree

PARAMS = ("ENG.N2", "ENG.T5")
N = 40
EPOCH = 1_791_000_000 * 10**9  # simulated UTC ns (AD-38), arbitrary test epoch
TAIL, SORTIE = "KH-T01", "KH-T01-20261014-0900"


def _streams(d):
    out = []
    for pid in PARAMS:
        for ch in d.channels_for_param(pid):
            loc = d.contract_location(ch["channel_id"])
            rate = d.acquisition_rate_hz(ch["channel_id"])
            assert rate, f"{ch['channel_id']} has no acquisition rate"
            out.append((loc["param_id"], loc["source_lru"], loc["lane"], int(rate), loc["units"]))
    return out


def _cir(d) -> CirBatch:
    rows = []
    for s, (pid, lru, lane, rate, _u) in enumerate(_streams(d)):
        for k in range(N):
            t = EPOCH + (k * 10**9) // rate + 1_000_000 * (s + 1)
            rows.append(
                {
                    "param_id": pid,
                    "source_lru": lru,
                    "lane": lane,
                    "sample_index": k,
                    "t_true": t - 1_000_000,
                    "t_sample": t,
                    "value": 50.0 + k,
                    "truth_value": 50.0 + k + 0.375,
                    "validity": "NORMAL",
                    "quality_flags": 0,
                    "rng_key_path": key_path_text(
                        KeyPath.of(
                            scenario="w0x",
                            tail=TAIL,
                            sortie=SORTIE,
                            subsystem="acquisition",
                            sensor=f"{lru}.{pid}" + (f".{lane}" if lane else ""),
                            component="noise",
                        )
                    ),
                }
            )
    return CirBatch(TAIL, SORTIE, pa.Table.from_pylist(rows, schema=CIR_SCHEMA))


def _run(base: Path):
    d = load_dictionary()
    cfg = FastPathConfig(d.dict_version, d.dict_hash, d.units_map(), {p: "ENG-SN-0001" for p in PARAMS})
    batch = _cir(d)
    t_ingest = EPOCH + 4 * 3600 * 10**9
    samples = cir_to_param_samples(batch, cfg, t_ingest=t_ingest)
    labels = cir_to_truth_labels(batch, cfg)
    store = ParquetStore.at(base)
    paths = store.write("param.samples", samples)
    store.write("labels.truth", labels)  # restricted tree only
    return d, batch, samples, store, paths


@pytest.mark.integration
def test_contract_docs_match_fresh_build(tmp_path, repo_root):
    fresh = tmp_path / "contract_docs"
    subprocess.run(
        [sys.executable, "-I", str(repo_root / "tools/build_contract_docs.py"), str(fresh)],
        check=True,
        capture_output=True,
    )
    published = repo_root / "docs" / "contract"
    assert published.is_dir(), "run: python -I tools/build_contract_docs.py"
    cmp = filecmp.dircmp(published, fresh)

    def diffs(c, prefix=""):
        out = [f"{prefix}{n}" for n in c.left_only + c.right_only + c.diff_files + c.funny_files]
        for name, sub in c.subdirs.items():
            out += diffs(sub, f"{prefix}{name}/")
        return out

    # dircmp compares shallowly; confirm byte equality explicitly
    bad = diffs(cmp)
    for p in fresh.rglob("*"):
        if p.is_file():
            q = published / p.relative_to(fresh)
            if not q.is_file() or q.read_bytes() != p.read_bytes():
                bad.append(str(p.relative_to(fresh)))
    assert not bad, f"docs/contract drifted from a fresh build: {sorted(set(bad))}"
    assert (published / "contract" / "v0" / "contract.md").is_file()


@pytest.mark.integration
def test_real_dictionary_channels_through_fast_path_store_and_replay(tmp_path):
    d, batch, samples, store, _ = _run(tmp_path / "run")
    c = load_contract("v0")
    c.validate("param.samples", samples)
    # every record carries this dictionary's identity
    assert set(samples.column("dict_hash").to_pylist()) == {d.dict_hash}
    assert set(samples.column("dict_version").to_pylist()) == {d.dict_version}
    # identity and units agree with the dictionary's contract_location
    expected = {(p, lru, lane, u) for p, lru, lane, _r, u in _streams(d)}
    got = set(
        zip(
            samples.column("param_id").to_pylist(),
            samples.column("source_lru").to_pylist(),
            samples.column("lane").to_pylist(),
            samples.column("units").to_pylist(),
            strict=True,
        )
    )
    assert got == expected
    assert samples.num_rows == N * len(expected)
    # consumer replay returns exactly the written records, with no restricted fields
    replayed = [b for b in ReplayStreamer(store, ["param.samples"]) if hasattr(b, "table")]
    n_rep = sum(b.table.num_rows for b in replayed)
    assert n_rep == samples.num_rows
    for b in replayed:
        assert "truth_value" not in b.table.schema.names
    # leak audit: no truth value anywhere in the consumer tree
    truths = [float(x) for x in batch.table.column("truth_value").to_pylist()]
    findings = audit_consumer_tree(store.root, c, secrets=truths)
    assert findings == [], findings[:5]


@pytest.mark.integration
def test_wired_run_is_bitwise_reproducible(tmp_path):
    def digest(base):
        _, _, _, store, _ = _run(base)
        h = hashlib.blake2b()
        for p in sorted(Path(store.root).rglob("*")):
            if p.is_file():
                h.update(str(p.relative_to(store.root)).encode() + b"\0" + p.read_bytes())
        return h.hexdigest()

    assert digest(tmp_path / "a") == digest(tmp_path / "b")


@pytest.mark.integration
def test_dictionary_param_sets_are_core_param_sets():
    d = load_dictionary()
    for name in d.content["constants"]:
        ps = d.param_set(name)
        assert isinstance(ps, ParamSet)
        assert ps.hash == load_dictionary().param_set(name).hash
