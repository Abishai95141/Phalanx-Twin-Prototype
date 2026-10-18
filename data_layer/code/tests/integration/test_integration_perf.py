"""A9: performance of the telemetry truth loop for one tail (``phalanx.integration.perf``).

Floor (owner scope change, coordinator AD-55; replaces the >= 50x / 83 us target): **>= 5x real time for the
whole Tejas aircraft in telemetry mode**, <= 833 us per 240 Hz step, judged on the ``SortieRunner`` (truth
loop, recorder, M14 feed, realised usage) in process CPU time (the wall clock on a CPU shared with other jobs
includes waiting for a core; both are printed with the load average).

Sample: the first gate sortie, 20 s into the window (post-start idle, n = 1 tail); best of 5 (2 for the
system rows).

Assertions (slow):
- the whole aircraft meets the 5x floor (runner CPU time per step <= 833 us);
- the fused in-loop lane path (E1 F2) is needed for it: the same sortie on the per-step segment path (no
  fused group) misses the floor; fusing makes ``System.run`` at least 10x cheaper per step.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from phalanx.integration.perf import FLOOR_US, RUNNER_KEY, UNFUSED_KEY, measure
from phalanx.integration.plans import gate_sorties
from phalanx.integration.system import SortieSpec, build_sortie_system

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture(scope="module")
def table():
    spec = SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5)
    tab = measure(build_sortie_system(spec), unfused=build_sortie_system(replace(spec, fused=False)))
    print("\n" + tab.render())
    return tab


def test_whole_aircraft_meets_the_5x_real_time_floor(table):
    assert table.system_cpu[RUNNER_KEY] <= FLOOR_US, table.render()


def test_fused_lane_path_is_needed_for_the_floor(table):
    fused = table.system_cpu["System.run (block mode, 10 s)"]
    per_step = table.system_cpu[UNFUSED_KEY]
    print(f"fused speed-up of System.run (CPU): {per_step / fused:.1f}x")
    assert per_step > FLOOR_US, table.render()
    assert per_step >= 10.0 * fused, table.render()
