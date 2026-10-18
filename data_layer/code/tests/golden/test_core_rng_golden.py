"""W0.2 A11: golden RNG test. Pins the key-path -> draws mapping (RNG_MAPPING_VERSION 1).

If this test fails, every stream in every dataset changed: bump ``RNG_MAPPING_VERSION``, write a migration
note and a decision-register entry; never just update the literals.

The values were recorded on darwin-arm64 with NumPy 2.5.4 (uv.lock). Words, uniform and raw draws are
platform-independent integer/IEEE results; the normal draws use NumPy's ziggurat (NEP 19: stream
compatibility of distribution methods is not guaranteed across NumPy feature releases).
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from phalanx.core.rng import RNG_MAPPING_VERSION, KeyPath, RngService, StreamDecl, StreamRegistry, Variate

ROOT = 0x0123456789ABCDEFFEDCBA9876543210
ID = ("scenario", "tail")

WORDS = (
    397119151, 1310173507, 2469511119, 2482021541,
    1456664457, 2858808950, 2443559671, 3131551057,
    247431552, 101290920, 3639938752, 1093984669,
    922228363, 2724594274, 1058185171, 2171348284,
)  # fmt: skip
NORMAL_0_10 = [
    "0x1.a394ef5000fa2p+0", "-0x1.ebdb6eeaa8a8dp-2", "0x1.241fd118f5ff8p+1", "0x1.171c9e35c35d7p-5",
    "-0x1.e86028f09b047p-1", "-0x1.204fb56ef6001p+0", "0x1.9f2b1e086b9bbp+0", "0x1.7d4de4c6ac87ap-2",
    "-0x1.8d8c7f13cc109p-3", "-0x1.e25a62036c604p-3",
]  # fmt: skip
UNIFORM_0_4 = ["0x1.69314a2c922bdp-1", "0x1.fc0cc0aecc6c0p-7", "0x1.94b881ecd6a37p-1", "0x1.a0abd3db969d5p-1"]
RAW_0_4 = [0x81EF553CA7993A2B, 0xBF94BD6478F223C4, 0x2F9129D044109B3E, 0xF7DD19BBEC950362]
GEN3_NORMAL_3 = ["-0x1.27bf50ed9a24fp-2", "0x1.c35065e2e9727p-1", "-0x1.185cff14db7c1p-2"]


def _rng():
    reg = StreamRegistry(
        [
            StreamDecl("core_test", "golden", ID, Variate.NORMAL, 8),
            StreamDecl("core_test", "golden_u", ID, Variate.UNIFORM, 8),
            StreamDecl("core_test", "golden_raw", ID, Variate.RAW, 8),
            StreamDecl("core_test", "golden_gen", ID, Variate.GENERATOR),
        ]
    )
    return RngService(ROOT, reg)


def _p(component):
    return KeyPath.of(scenario="golden", tail="T0", subsystem="core_test", component=component)


@pytest.mark.golden
def test_mapping_version():
    assert RNG_MAPPING_VERSION == 1


@pytest.mark.golden
def test_key_words_pinned_and_rederived_from_the_documented_rule():
    assert _p("golden").words() == WORDS
    # independent re-derivation of mapping step 2: blake2b-128(kind 0x1F type 0x1F value), phx.rngkey.v1
    words = []
    for kind, value in [
        ("scenario", "golden"),
        ("tail", "T0"),
        ("subsystem", "core_test"),
        ("component", "golden"),
    ]:
        d = hashlib.blake2b(
            f"{kind}\x1fs\x1f{value}".encode(), digest_size=16, person=b"phx.rngkey.v1"
        ).digest()
        words += [int.from_bytes(d[i : i + 4], "little") for i in range(0, 16, 4)]
    assert tuple(words) == WORDS


@pytest.mark.golden
def test_first_draws_pinned():
    rng = _rng()
    assert [x.hex() for x in rng.draws(_p("golden"), 0, 10).tolist()] == NORMAL_0_10  # spans blocks 0 and 1
    assert [x.hex() for x in rng.draws(_p("golden_u"), 0, 4).tolist()] == UNIFORM_0_4
    assert rng.draws(_p("golden_raw"), 0, 4).tolist() == RAW_0_4
    assert [x.hex() for x in rng.generator(_p("golden_gen"), 3).standard_normal(3).tolist()] == GEN3_NORMAL_3


@pytest.mark.golden
def test_block_rederived_from_seedsequence_rule():
    """Mapping steps 3-4: block b = Philox(SeedSequence(root, spawn_key=words + (tag, lo, hi)))."""
    ss = np.random.SeedSequence(entropy=ROOT, spawn_key=(*WORDS, int(Variate.NORMAL), 1, 0))
    block1 = np.random.Generator(np.random.Philox(ss)).standard_normal(8)
    assert [x.hex() for x in block1[:2].tolist()] == NORMAL_0_10[8:10]
    assert _rng().stream(_p("golden")).spawn_key(1) == (*WORDS, 1, 1, 0)
