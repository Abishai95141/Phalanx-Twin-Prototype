"""KPI behaviour and A7 determinism of operations runs.

- A larger spares scale raises availability on the same exogenous future (CRN, same root): n = 1 pair, the
  effect is large (no spares vs 3x scale), so one pair answers it.
- Determinism (I1): two in-process runs and one fresh interpreter give the same record digest (n = 3 runs).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from test_fork_fixture_fleet import DAY, EPOCH, FixtureFleetBuilder

from phalanx.fork.kpi import compute_kpis
from phalanx.fork.session import OpsSession
from phalanx.maintenance.config import load_m18_config

ROOT = 0xD37


def _kpis(cfg, days=90):
    b = FixtureFleetBuilder(n_tails=5, horizon_days=days, m18_cfg=cfg)
    s = OpsSession(b, ROOT)
    s.run_until(days * DAY)
    return compute_kpis(s.log, b.m18_cfg, t0_utc=EPOCH, t1_utc=EPOCH + days * DAY, tails=b.tails), s


@pytest.mark.fork
def test_more_spares_raise_availability_on_the_same_future():
    base = load_m18_config()
    none = base.with_catalogue_values({c.code: {"stock_per_ac": 0.0} for c in base.catalogue.classes})
    rich = base.with_catalogue_values(
        {c.code: {"stock_per_ac": 3.0 * c.v("stock_per_ac") + 0.4} for c in base.catalogue.classes}
    )
    k_none, _ = _kpis(none)
    k_rich, _ = _kpis(rich)
    assert k_rich.mc > k_none.mc and k_rich.nmcs < k_none.nmcs
    assert k_rich.cann <= k_none.cann


_SCRIPT = """
import sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from test_fork_fixture_fleet import DAY, FixtureFleetBuilder
from phalanx.fork.session import OpsSession
b = FixtureFleetBuilder(n_tails=3, horizon_days=30)
s = OpsSession(b, int(sys.argv[3]))
s.run_until(30 * DAY)
print(s.log.digest)
"""


@pytest.mark.fork
@pytest.mark.determinism
def test_runs_are_bitwise_deterministic_in_process_and_in_a_fresh_interpreter():
    digests = []
    for _ in range(2):
        b = FixtureFleetBuilder(n_tails=3, horizon_days=30)
        s = OpsSession(b, ROOT)
        s.run_until(30 * DAY)
        digests.append(s.log.digest)
    here = Path(__file__).resolve()
    src = str(here.parents[2] / "src")
    out = subprocess.run(
        [sys.executable, "-I", "-c", _SCRIPT, src, str(here.parent), str(ROOT)],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    digests.append(out.stdout.strip())
    assert digests[0] == digests[1] == digests[2]
    b = FixtureFleetBuilder(n_tails=3, horizon_days=30)
    other = OpsSession(b, 0xD38)  # another root: the comparison above can fail
    other.run_until(30 * DAY)
    assert other.log.digest != digests[0]
