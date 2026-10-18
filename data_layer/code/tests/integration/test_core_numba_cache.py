"""Numba stale-cache guard: the hazard is real (negative control), the source-keyed cache directory and
the per-session test cache avoid it, and the manifest records the key.

Each subprocess compiles one tiny kernel (about 1 s); 4 subprocesses in total.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from phalanx.core.manifest import MANIFEST_VERSION, build_manifest
from phalanx.core.numba_cache import cache_key, numba_cache_dir, source_digest
from phalanx.core.toy import build_toy_system

LAYOUT_SRC = "A = {a}\nB = {b}\n"
KERNEL_SRC = textwrap.dedent(
    """
    import numpy as np
    from numba import njit
    from stalepkg.layout import A, B

    @njit(cache=True)
    def pick(v):
        return v[A] * 10.0 + v[B]
    """
)
RUN = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, {root!r})
    import numpy as np
    from stalepkg.kernel import pick
    print(pick(np.array([1.0, 2.0])))
    """
)


def _make_pkg(tmp: Path, a: int, b: int) -> Path:
    pkg = tmp / "stalepkg"
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "layout.py").write_text(LAYOUT_SRC.format(a=a, b=b))
    if not (pkg / "kernel.py").exists():
        (pkg / "kernel.py").write_text(KERNEL_SRC)
    return pkg


def _run(root: Path, cache_dir: Path) -> float:
    env = dict(os.environ, NUMBA_CACHE_DIR=str(cache_dir))
    r = subprocess.run(
        [sys.executable, "-I", "-B", "-c", RUN.format(root=str(root))],  # -B: no .pyc (mtime is 1 s coarse)
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return float(r.stdout.strip())


@pytest.mark.integration
def test_stale_cache_hazard_and_source_keyed_directory(tmp_path):
    pkg = _make_pkg(tmp_path, 0, 1)
    shared = tmp_path / "shared_cache"
    assert _run(tmp_path, shared) == 12.0  # v[0]*10 + v[1]
    key_before = cache_key(pkg)
    _make_pkg(tmp_path, 1, 0)  # swap the imported constants; kernel.py itself is untouched
    # negative control: the ordinary cache serves the stale compiled kernel (correct answer is 21.0)
    assert _run(tmp_path, shared) == 12.0
    # the guard: a cache directory keyed by the package source digest changes with the edit
    key_after = cache_key(pkg)
    assert key_after != key_before
    assert _run(tmp_path, numba_cache_dir(base=tmp_path / "keyed", root=pkg)) == 21.0


@pytest.mark.unit
def test_source_digest_is_content_based(tmp_path):
    pkg = _make_pkg(tmp_path, 0, 1)
    d1 = source_digest(pkg)
    (pkg / "extra.py").write_text("X = 1\n")
    d2 = source_digest(pkg)
    (pkg / "notes.txt").write_text("not a source")
    d3 = source_digest(pkg)
    assert d1 != d2 and d2 == d3 and len(d1) == 64
    assert numba_cache_dir(base=tmp_path, root=pkg).name == f"src-{d2[:16]}"


@pytest.mark.integration
def test_configure_numba_cache_before_and_after_kernel_import(tmp_path, repo_root):
    script = textwrap.dedent(
        """
        import sys, json
        sys.path.insert(0, {src!r})
        from pathlib import Path
        from phalanx.core.numba_cache import configure_numba_cache, numba_cache_status
        d = configure_numba_cache(Path({base!r}))
        import phalanx.core.example_kernel  # decorated after configuration: uses the keyed directory
        from numba.core import config
        try:
            configure_numba_cache(Path({base!r}))
            late = "no error"
        except RuntimeError as e:
            late = "refused"
        print(json.dumps({{"dir": str(d), "config": config.CACHE_DIR, "late": late, **numba_cache_status()}}))
        """
    ).format(src=str(repo_root / "src"), base=str(tmp_path))
    r = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, check=True)
    out = json.loads(r.stdout)
    assert out["config"] == out["dir"] and Path(out["dir"]).name == out["key"]
    assert out["configured"] is True and out["late"] == "refused"


@pytest.mark.unit
def test_test_session_uses_a_fresh_cache_dir():
    if os.environ.get("PHALANX_TEST_REUSE_NUMBA_CACHE") == "1":
        pytest.skip("cache reuse explicitly requested for a timing comparison")
    d = Path(os.environ["NUMBA_CACHE_DIR"])
    assert d.parent.name == ".pytest_cache" and d.name == f"numba-cache-{os.getpid()}"
    from numba.core import config

    assert config.CACHE_DIR == str(d)


@pytest.mark.unit
def test_manifest_records_the_numba_cache_key():
    m = build_manifest(build_toy_system(), git_commit="0" * 40, git_dirty=False)
    d = json.loads(m.to_json())
    assert d["manifest_version"] == MANIFEST_VERSION == 2
    assert d["numba_cache"]["key"] == cache_key() and d["numba_cache"]["source_digest"] == source_digest()
    assert d["numba_cache"]["configured"] is False  # tests use the per-session directory, not the keyed one
