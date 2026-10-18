"""Shared test configuration.

Runtime guard (invariant I2, no global RNG): every test fails if it consumed the global NumPy legacy RNG
or the stdlib `random` RNG. All randomness must come from identity-keyed streams (phalanx.core.rng).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Numba stale-cache guard (core README "Numba cache"; coordinator-authorised W0.2 follow-up). Numba's on-disk
# cache does not notice edits to constants imported from other modules, so every test session compiles
# from the current sources into its own fresh cache directory, set before anything imports numba.
# PHALANX_TEST_REUSE_NUMBA_CACHE=1 skips this (timing comparisons only; never in `make check`).
# Worker processes spawned by a test (multiprocessing re-imports this file) inherit the session's directory.
_NUMBA_TEST_CACHE: Path | None = None
_OWNER = "PHALANX_NUMBA_TEST_CACHE_OWNER"
if os.environ.get("PHALANX_TEST_REUSE_NUMBA_CACHE") != "1" and _OWNER not in os.environ:
    _NUMBA_TEST_CACHE = REPO_ROOT / ".pytest_cache" / f"numba-cache-{os.getpid()}"
    shutil.rmtree(_NUMBA_TEST_CACHE, ignore_errors=True)
    _NUMBA_TEST_CACHE.mkdir(parents=True)
    os.environ["NUMBA_CACHE_DIR"] = str(_NUMBA_TEST_CACHE)
    os.environ[_OWNER] = str(os.getpid())
    if "numba" in sys.modules:  # imported by a plugin before this conftest: update the live config too
        from numba.core import config as _numba_config

        _numba_config.CACHE_DIR = str(_NUMBA_TEST_CACHE)

import random  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from hypothesis import settings as _hypothesis_settings  # noqa: E402

# Hypothesis policy (E1-MF, MF4b; tests/README.md "Property tests"). `make check` runs every property test on
# the deterministic profile: examples derived from the test itself (derandomize; no example database, so no
# run depends on an earlier one) and no wall-clock deadline. A test's own @settings override only the fields
# it names. Exploration runs (`PHALANX_HYPOTHESIS_PROFILE=phalanx-explore`) draw fresh random examples; every
# counterexample found is pinned with @example (as `.xfail(raises=...)` while it is a known, owned failure).
_hypothesis_settings.register_profile("phalanx-check", derandomize=True, deadline=None, print_blob=True)
_hypothesis_settings.register_profile("phalanx-explore", derandomize=False, deadline=None, print_blob=True)
_HYPOTHESIS_PROFILE = os.environ.get("PHALANX_HYPOTHESIS_PROFILE", "phalanx-check")
_hypothesis_settings.load_profile(_HYPOTHESIS_PROFILE)
if _HYPOTHESIS_PROFILE == "phalanx-check":
    # Hypothesis also mixes literals mined from every imported non-test module of the repository into what
    # it generates (`providers._get_local_constants`), so a derandomized test's examples depend on which
    # modules a run happened to import: E1-MF saw the M08 limiter property pass alone and fail in a larger
    # selection, on the same seed. The deterministic profile turns that pool off; examples are then a function
    # of the test (and the pinned Hypothesis version) only. Fail loudly if the internal hook moves.
    from hypothesis.internal.conjecture import providers as _hypothesis_providers
    from hypothesis.internal.constants_ast import Constants as _HypothesisConstants

    if not hasattr(_hypothesis_providers, "_get_local_constants"):
        raise RuntimeError("Hypothesis internals changed: revisit the phalanx-check profile (conftest.py)")
    _NO_LOCAL_CONSTANTS = _HypothesisConstants()
    _hypothesis_providers._get_local_constants = lambda: _NO_LOCAL_CONSTANTS


def pytest_sessionfinish(session, exitstatus):
    if _NUMBA_TEST_CACHE is not None:
        shutil.rmtree(_NUMBA_TEST_CACHE, ignore_errors=True)
        os.environ.pop(_OWNER, None)


@pytest.fixture(autouse=True)
def _no_global_rng_consumption():
    np_state = np.random.get_state(legacy=False)
    py_state = random.getstate()
    yield
    after = np.random.get_state(legacy=False)
    same = np.array_equal(after["state"]["key"], np_state["state"]["key"]) and (
        after["state"]["pos"] == np_state["state"]["pos"]
    )
    assert same, "test consumed the global NumPy RNG (use phalanx.core.rng)"
    assert random.getstate() == py_state, "test consumed the stdlib random RNG (use phalanx.core.rng)"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


def _data_dir(env: str, default: str) -> Path | None:
    p = Path(os.environ.get(env, default))
    return p if p.is_dir() else None


@pytest.fixture(scope="session")
def dashlink_687_dir() -> Path:
    """Tail 687 archive 1 MAT files (read-only). Archive 2 is RESERVED and must never be read by tests."""
    p = _data_dir(
        "PHALANX_DASHLINK_687",
        "/Users/abishaikc/Phalanx/research_sources/datasets/dashlink_tail687/raw/mat",
    )
    if p is None:
        pytest.skip("DASHlink Tail 687 archive 1 not available")
    return p


@pytest.fixture(scope="session")
def dashlink_652_dir() -> Path:
    """Tail 652 archive 8 MAT files (read-only, outside the repo)."""
    p = _data_dir("PHALANX_DASHLINK_652", "/Users/abishaikc/phalanx/data/raw/dashlink_tail652/extracted")
    if p is None:
        pytest.skip("DASHlink Tail 652 not available")
    return p
