"""W0.4 deliverable 2: JSON-Schema for manifests and orders; lossless Arrow <-> JSON document conversion."""

from __future__ import annotations

import copy

import jsonschema
import pytest

from phalanx.dictionary.contract import load_contract
from phalanx.dictionary.contract.examples import example_records
from phalanx.dictionary.contract.jsonschema_gen import dumps_doc, json_docs_to_table, table_to_json_docs

C = load_contract("v0")
JSON_TOPICS = [t for t in C.topic_names if C.topics[t].json_schema]


@pytest.mark.unit
def test_json_topics_are_manifests_and_orders():
    assert set(JSON_TOPICS) == {"sortie.manifest", "orders.commands", "orders.status"}


@pytest.mark.unit
@pytest.mark.parametrize("topic", JSON_TOPICS)
@pytest.mark.parametrize("audience", ["consumer", "full"])
def test_json_schema_is_valid_and_accepts_contract_records(topic, audience):
    schema = C.json_schema(topic, audience=audience)
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    table = example_records(C, topic, 4)
    docs = table_to_json_docs(C, topic, table, audience=audience)
    for d in docs:
        errs = [e.message for e in v.iter_errors(d)]
        assert not errs, errs
    assert ("root_seed" in schema["properties"]) == (topic == "sortie.manifest" and audience == "full")


@pytest.mark.unit
@pytest.mark.parametrize("topic", JSON_TOPICS)
def test_json_roundtrip_lossless(topic):
    table = example_records(C, topic, 4)
    docs = table_to_json_docs(C, topic, table, audience="full")
    back = json_docs_to_table(C, topic, docs, audience="full")
    assert back.equals(table, check_metadata=True)
    # canonical text is stable
    assert [dumps_doc(d) for d in docs] == [
        dumps_doc(d) for d in table_to_json_docs(C, topic, back, audience="full")
    ]


def _bad_docs(doc: dict, topic: str) -> dict[str, dict]:
    out = {}
    d = copy.deepcopy(doc)
    d.pop("record_id")
    out["missing field"] = d
    d = copy.deepcopy(doc)
    d["unexpected"] = 1
    out["extra field"] = d
    d = copy.deepcopy(doc)
    d["record_id"] = d["record_id"].upper()
    out["record_id not lower hex"] = d
    enum_field = {"orders.commands": "action", "orders.status": "status", "sortie.manifest": "provenance"}[
        topic
    ]
    d = copy.deepcopy(doc)
    d[enum_field] = "NOT_A_SYMBOL"
    out["enum outside table"] = d
    time_field = C.topics[topic].event_time
    d = copy.deepcopy(doc)
    d[time_field] = -1
    out["negative time"] = d
    d = copy.deepcopy(doc)
    d[time_field] = 1.5
    out["non-integer time"] = d
    return out


@pytest.mark.unit
@pytest.mark.parametrize("topic", JSON_TOPICS)
def test_json_schema_rejects_malformed_docs(topic):
    v = jsonschema.Draft202012Validator(C.json_schema(topic, audience="consumer"))
    doc = table_to_json_docs(C, topic, example_records(C, topic, 1), audience="consumer")[0]
    assert v.is_valid(doc)
    for why, bad in _bad_docs(doc, topic).items():
        assert not v.is_valid(bad), why
