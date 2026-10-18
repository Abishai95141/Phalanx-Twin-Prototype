"""``sortie.manifest`` from the sortie runner (contract v0 topic with no other producer; coordinator item).

Sample: the first gate sortie, 10 s from post-start idle with the recorder, the M14 feed and the sortie close
(n = 1 sortie), plus the second gate sortie at its window start for the one-record-per-sortie check (n = 2).

- the record is schema-valid: the contract validator on the producer view (restricted fields present) and
  the generated JSON-Schema (Draft 2020-12) on the consumer documents (restricted fields absent);
- one record per sortie: one row, record_id from (tail_no, sortie_id): two sorties give two distinct ids that
  validate as one batch; the ``direct`` and ``full_path`` variants of one sortie share it (idempotent);
- linkage: ``param.samples`` built by the fast path from the same CIR and M14's ``events.*`` /
  ``usage.counters`` carry the manifest's tail_no, sortie_id, dict_version and dict_hash; their engine serials
  are the manifest's; every sample time lies in [t_start, t_end] and t_ingest >= every sample time;
- identity: ``config_hash`` is the System's (AD-48.8: serials and per-tail configuration; that a changed
  serial changes it is ``test_integration_system::test_config_hash_covers_serials_and_tail_configuration``);
  ``run_manifest_hash`` is the run manifest's, which carries the Numba cache key; the RESTRICTED
  root seed and the RNG stream table are present, sorted and unique; parked: no take-off, no landing;
- deterministic: the same state gives byte-identical records.
"""

from __future__ import annotations

import jsonschema
import pyarrow as pa
import pytest

from phalanx.core.numba_cache import cache_key
from phalanx.dictionary.contract import load_contract
from phalanx.dictionary.contract.jsonschema_gen import table_to_json_docs
from phalanx.ground.fast_path import FastPathConfig, cir_to_param_samples
from phalanx.integration.manifest import TOPIC, build_run_manifest
from phalanx.integration.plans import gate_sorties
from phalanx.integration.sortie import SortieRunner
from phalanx.integration.system import SortieSpec, build_sortie_system
from phalanx.monitoring.contract_out import contract_tables

pytestmark = pytest.mark.integration
SECONDS = 10
C = load_contract("v0")


def _spec(plan):
    return SortieSpec(plan=plan, scenario="gate", root=0xA5)


@pytest.fixture(scope="module")
def run():
    ss = build_sortie_system(_spec(gate_sorties()[0]))
    r = SortieRunner(ss, keep_cir=True)
    st = r.begin()
    st, outs = r.run(st, SECONDS * 240)
    st = r.close(st)
    rm = build_run_manifest(r, st)
    return ss, r, st, outs, rm, r.manifest(st, run_manifest=rm)


def test_manifest_is_schema_valid(run):
    *_, m = run
    assert m.num_rows == 1
    C.validate(TOPIC, m)  # producer view (restricted fields present)
    docs = table_to_json_docs(C, TOPIC, m, audience="consumer")
    v = jsonschema.Draft202012Validator(C.json_schema(TOPIC, audience="consumer"))
    errors = [e.message for d in docs for e in v.iter_errors(d)]
    assert errors == []
    assert "root_seed" not in docs[0] and "rng_stream_table" not in docs[0]


def test_one_record_per_sortie(run):
    _ss, r, st, _outs, rm, m = run
    full = r.manifest(st, run_manifest=rm, provenance="full_path")
    assert full.column("record_id").to_pylist() == m.column("record_id").to_pylist()
    assert full.column("provenance").to_pylist() == ["full_path"]
    ss2 = build_sortie_system(_spec(gate_sorties()[1]))
    r2 = SortieRunner(ss2)
    st2, _ = r2.run(r2.begin(), 240)
    m2 = r2.manifest(st2, run_manifest=build_run_manifest(r2, st2))
    assert m2.column("sortie_id").to_pylist() != m.column("sortie_id").to_pylist()
    both = pa.concat_tables([m, m2])
    C.validate(TOPIC, both)  # record_id unique within the batch
    assert len(set(both.column("record_id").to_pylist())) == 2


def test_linkage_keys_match_samples_and_events(run):
    ss, _r, st, outs, _rm, m = run
    row = m.to_pylist()[0]
    keys = {k: row[k] for k in ("tail_no", "sortie_id", "dict_version", "dict_hash")}
    serials = {e["serial"] for e in row["engine_serials"]}
    assert serials == set(ss.window.engine_serials)
    cfg = FastPathConfig.from_dictionary(ss.dictionary, engine_serial=ss.window.engine_serials[0])
    n_samples = 0
    for c in outs:
        ps = cir_to_param_samples(c.cir, cfg, t_ingest=row["t_ingest"])
        n_samples += ps.num_rows
        for k, v in keys.items():
            assert set(ps.column(k).to_pylist()) <= {v}, k
        assert set(ps.column("engine_serial").drop_null().to_pylist()) <= serials
        t = ps.column("t_sample").to_numpy()
        assert t.min() >= row["t_start"] and t.max() <= row["t_end"] <= row["t_ingest"]
    assert n_samples > 1000
    tabs = contract_tables(
        ss.modules["monitor"],
        st.world.states["monitor"],
        dictionary=ss.dictionary,
        tail_no=ss.window.tail,
        epoch_utc_ns=ss.epoch_utc_ns,
        t_ingest_utc_ns=row["t_ingest"],
        sortie_id=ss.window.sortie_id,
    )
    n_events = 0
    for topic, tab in tabs.items():
        n_events += tab.num_rows
        for k, v in keys.items():
            if k in tab.column_names:
                assert set(tab.column(k).drop_null().to_pylist()) <= {v}, (topic, k)
        if "engine_serial" in tab.column_names:
            assert set(tab.column("engine_serial").drop_null().to_pylist()) <= serials, topic
    assert n_events > 0, {t: x.num_rows for t, x in tabs.items()}


def test_identity_provenance_and_restricted_fields(run):
    ss, r, st, _outs, rm, m = run
    row = m.to_pylist()[0]
    assert row["config_hash"] == ss.system.config_hash
    assert row["run_manifest_hash"] == rm.hash and rm.numba_cache["key"] == cache_key()
    assert row["code_commit"] == rm.git_commit and row["contract_version"] == C.version
    assert row["root_seed"] == f"{0xA5:032x}"
    paths = [x["key_path"] for x in row["rng_stream_table"]]
    assert paths and paths == sorted(set(paths))
    assert row["t_takeoff"] is None and row["t_landing"] is None  # parked at idle
    assert row["t_end"] - row["t_start"] >= SECONDS * 1_000_000_000
    assert row["mission_type"] and row["sw_config_id"] == "SW-BASE" and row["lru_serials"] == []
    assert r.manifest(st, run_manifest=rm).equals(m)  # deterministic
