"""W0.4 A4 (property): record_id is collision-free on a corpus designed to expose an ignored or ambiguous
component, and the vectorised path is row-order and batch-composition independent.

Corpus size: a full grid of 4 tails x 3 sorties x 5 channels x 4 params x 25 seq x 3 msg = 18,000 distinct
keys, plus boundary-shifted string pairs. If any component were dropped from the hash input, or two components
were concatenated without a length prefix, the grid would contain colliding ids. Random 128-bit collisions are
negligible at this n (p ~ n^2 / 2^129 ~ 5e-31), so any collision is an implementation defect.
"""

from __future__ import annotations

import itertools

import numpy as np
import pyarrow as pa
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.dictionary.contract import load_contract
from phalanx.ground.rid import record_id, record_ids

C = load_contract("v0")
TOPIC = "param.samples"


@pytest.mark.property
def test_a4_grid_corpus_collision_free():
    tails, sorties = ["T1", "T2", "T11", "T12"], ["S1", "S2", "S12"]
    channels = ["direct:FADEC:A", "direct:FADEC:B", "direct:FADEC:", "1", "11"]
    params, seqs, msgs = ["N2", "N1", "N", "2N"], range(25), range(3)
    keys = list(itertools.product(tails, sorties, channels, params, seqs, msgs))
    n = len(keys)
    assert n == 18_000
    cols = {
        "provenance": "direct",
        "tail_no": pa.array([k[0] for k in keys]),
        "sortie_id": pa.array([k[1] for k in keys]),
        "channel_id": pa.array([k[2] for k in keys]),
        "param_id": pa.array([k[3] for k in keys]),
        "seq": np.array([k[4] for k in keys], dtype=np.uint64),
        "msg_index": np.array([k[5] for k in keys], dtype=np.uint64),
    }
    ids = record_ids(C, TOPIC, cols, n)
    assert len(set(ids.to_pylist())) == n
    # boundary shift between adjacent string components must not collide
    a = record_id(
        C,
        TOPIC,
        {
            "provenance": "direct",
            "tail_no": "T1",
            "sortie_id": "1S",
            "channel_id": "c",
            "param_id": "p",
            "seq": 0,
            "msg_index": 0,
        },
    )
    b = record_id(
        C,
        TOPIC,
        {
            "provenance": "direct",
            "tail_no": "T11",
            "sortie_id": "S",
            "channel_id": "c",
            "param_id": "p",
            "seq": 0,
            "msg_index": 0,
        },
    )
    assert a != b
    # provenance separates the fast path from the full path
    c = record_id(
        C,
        TOPIC,
        {
            "provenance": "full_path",
            "tail_no": "T1",
            "sortie_id": "1S",
            "channel_id": "c",
            "param_id": "p",
            "seq": 0,
            "msg_index": 0,
        },
    )
    assert c != a
    # a boundary shift that moves a tag byte ('S') across components: equal under any encoding that keeps the
    # type tag but drops the length prefix, so this pair exposes exactly that defect
    base = {"provenance": "direct", "channel_id": "c", "param_id": "p", "seq": 0, "msg_index": 0}
    assert record_id(C, TOPIC, {**base, "tail_no": "T1S", "sortie_id": "12"}) != record_id(
        C, TOPIC, {**base, "tail_no": "T1", "sortie_id": "S12"}
    )


# the alphabet includes the tag bytes (S, N, U) so tag/content confusion is reachable
_ident = st.text(alphabet="ASNU1:-.", min_size=0, max_size=4)
_key = st.tuples(_ident, _ident, _ident, _ident, st.integers(0, 2**64 - 1), st.integers(0, 3))


@pytest.mark.property
@settings(max_examples=60, deadline=None)
@given(st.lists(_key, min_size=1, max_size=40, unique=True), st.randoms(use_true_random=False))
def test_a4_distinct_keys_distinct_ids_and_order_independent(keys, rnd):
    n = len(keys)

    def cols(ks):
        return {
            "provenance": "direct",
            "tail_no": pa.array([k[0] for k in ks], pa.string()),
            "sortie_id": pa.array([k[1] for k in ks], pa.string()),
            "channel_id": pa.array([k[2] for k in ks], pa.string()),
            "param_id": pa.array([k[3] for k in ks], pa.string()),
            "seq": np.array([k[4] for k in ks], dtype=np.uint64),
            "msg_index": np.array([k[5] for k in ks], dtype=np.uint64),
        }

    ids = record_ids(C, TOPIC, cols(keys), n).to_pylist()
    assert len(set(ids)) == n
    perm = list(range(n))
    rnd.shuffle(perm)
    shuffled = record_ids(C, TOPIC, cols([keys[i] for i in perm]), n).to_pylist()
    assert shuffled == [ids[i] for i in perm]
    # each id depends only on its own key (not on the rest of the batch)
    k0 = keys[0]
    single = record_id(
        C,
        TOPIC,
        {
            "provenance": "direct",
            "tail_no": k0[0],
            "sortie_id": k0[1],
            "channel_id": k0[2],
            "param_id": k0[3],
            "seq": k0[4],
            "msg_index": k0[5],
        },
    )
    assert single == ids[0]
