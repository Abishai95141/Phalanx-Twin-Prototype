"""W0.2 run manifest (architecture §15): deterministic JSON, required fields, no wall clock."""

from __future__ import annotations

import json
import re

import pytest

from phalanx.core.manifest import build_manifest, read_git_commit, write_manifest
from phalanx.core.toy import build_toy_system

REQUIRED = {
    "git_commit",
    "config_hash",
    "dict_hash",
    "data_hashes",
    "library_versions",
    "backend",
    "bit_generator",
    "stream_table",
    "order_log_hash",
    "rng",
    "formats",
    "numba_cache",
}


@pytest.mark.unit
def test_manifest_is_deterministic_and_complete(tmp_path):
    s = build_toy_system(controlled=True)
    m1 = build_manifest(s, git_commit="0" * 40, git_dirty=False, data_hashes={"b": "2", "a": "1"})
    m2 = build_manifest(
        build_toy_system(controlled=True),
        git_commit="0" * 40,
        git_dirty=False,
        data_hashes={"a": "1", "b": "2"},
    )
    assert m1.to_json() == m2.to_json() and m1.hash == m2.hash
    d = json.loads(m1.to_json())
    assert REQUIRED <= set(d)
    assert d["bit_generator"] == "Philox" and d["library_versions"]["numpy"]
    assert [r["component"] for r in d["stream_table"]] == ["measurement_noise", "process_force"]
    assert list(d) == sorted(d)  # sorted keys
    text = m1.to_json()
    assert not re.search(r"\"(time|date|timestamp|created|now)[a-z_]*\"\s*:", text)  # no wall-clock keys
    p = write_manifest(m1, tmp_path / "manifest.json")
    assert p.read_text() == text
    m3 = build_manifest(build_toy_system(), git_commit="0" * 40, git_dirty=False)
    assert m3.hash != m1.hash  # a different configuration is visible in the manifest


@pytest.mark.unit
def test_git_commit_is_read_from_the_checkout(repo_root):
    commit, dirty = read_git_commit(repo_root)
    assert re.fullmatch(r"[0-9a-f]{40}", commit) and isinstance(dirty, bool)
    m = build_manifest(build_toy_system(), repo=repo_root)
    assert m.git_commit == commit
    with pytest.raises(ValueError):
        build_manifest(build_toy_system())
