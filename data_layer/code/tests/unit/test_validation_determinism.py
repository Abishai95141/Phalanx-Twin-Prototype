"""A6: the validation package has no global RNG, wall-clock reads, builtin hash or seed arithmetic.

The static audit runs on `src/` in `make check`; this test pins it to the validation package so a regression
is
attributed to M20, and checks that a full battery run leaves the global RNGs untouched (the autouse fixture in
`tests/conftest.py` asserts that after every test) and is bitwise repeatable.
"""

from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pytest

from phalanx.validation.battery import Bootstrap, flight_stats, run_battery
from phalanx.validation.testing import PARTNER_TAIL, REFERENCE_TAIL, control_flight

pytestmark = [pytest.mark.unit, pytest.mark.determinism]


def test_static_audit_clean_on_validation_package(repo_root):
    r = subprocess.run(
        [
            sys.executable,
            "-I",
            str(repo_root / "tools/audit_static.py"),
            str(repo_root / "src/phalanx/validation"),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout
    assert " 0 errors" in r.stdout


def test_battery_run_is_bitwise_repeatable():
    H = [flight_stats(control_flight(i, REFERENCE_TAIL, "real")) for i in range(2)]
    P = [flight_stats(control_flight(100 + i, PARTNER_TAIL, "real")) for i in range(2)]
    reps = [
        run_battery(H, P, [0], [1], {"same": H}, Bootstrap(np.random.SeedSequence(3, spawn_key=(1,)), 30))
        for _ in range(2)
    ]
    for t, d in reps[0].d_tail.items():
        assert np.array_equal(d.boot, reps[1].d_tail[t].boot, equal_nan=True)
    a, b = (json.dumps(r.to_dict(), default=float, sort_keys=True) for r in reps)
    assert a == b
