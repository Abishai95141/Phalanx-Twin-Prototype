"""W1.1 A6 (AAR): per-pilot closure speed 2-3.5 kt with SD ~0.7 kt (NFTC/ADA DSJ 70(2): 1.71-4.3 kt over 12
contacts, clear pilot effect), drawn per contact from the pilot's distribution [A-W1.1-44], and keyed so the
same sortie gives the same closures.

Sample (stated before running): 20 pilots x 60 contacts (one 60-min tanker segment each). Per-pilot mean
within 5 SE of the pilot's trait mean (SE = 0.7 kt / sqrt(60) = 0.09 kt); pooled within-pilot SD within
+/- 10 % of 0.7 kt (SE of an SD from 1,180 dof ~ 2 %); every pilot mean inside [2.0, 3.5] kt +/- 5 SE.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.rng import KeyPath, RngService, StreamDecl, StreamRegistry, Variate
from phalanx.pilot.kernel import P_AARP
from phalanx.pilot.module import aar_closures, load_pilot_config
from phalanx.scenario.config import P_TANKER, load_scenario_params
from phalanx.scenario.pilots import T_AAR_MEAN, T_AAR_SD, draw_traits
from phalanx.scenario.plan import N_SEG_F, N_SEG_I, S_PRIM, SortiePlan

KT = 1852.0 / 3600.0
PCFG = load_pilot_config()
P = load_scenario_params()
REG = StreamRegistry(
    [
        StreamDecl("pilot", "aar", ("scenario", "tail", "sortie"), Variate.NORMAL, 64),
        StreamDecl("scenario", "pilot", ("scenario", "serial"), Variate.GENERATOR, 1),
    ]
)
RNG = RngService(0xAA2, REG)


def tanker_plan(traits, minutes=60):
    seg_i = np.zeros((1, N_SEG_I), np.int64)
    seg_i[0, S_PRIM] = P_TANKER
    return SortiePlan(
        "T-1", "k", "T", "sq", 1, 0.0, 8, "PLT", False, 0, ("E",), 0, 2458.0,
        np.array([0], np.int64), np.zeros((1, N_SEG_F)), seg_i, minutes * 60 * 10**9, np.zeros(14), traits,
    )  # fmt: skip


@pytest.mark.statistical
def test_aar_closure_per_pilot():
    means, sds = [], []
    for k in range(20):
        g = (
            RNG.scope(KeyPath.of(scenario="aar", serial=f"PLT-x-{k:02d}"))
            .stream("scenario", "pilot")
            .generator(0)
        )
        tr = draw_traits(g, P)
        plan = tanker_plan(tr)
        stream = RNG.scope(KeyPath.of(scenario="aar", tail="T", sortie=f"S{k}")).stream("pilot", "aar")
        off, cl = aar_closures(plan, stream, float(PCFG.vector[P_AARP]), PCFG.aar_closure_max)
        assert off.tolist() == [0] and cl.size == 60
        assert np.all((cl > 0) & (cl <= 10 * KT + 1e-12))
        se = tr[T_AAR_SD] / np.sqrt(cl.size)
        assert abs(cl.mean() - tr[T_AAR_MEAN]) <= 5 * se
        assert 2.0 * KT - 5 * se <= cl.mean() <= 3.5 * KT + 5 * se
        means.append(cl.mean())
        sds.append(cl.std(ddof=1))
    pooled = float(np.sqrt(np.mean(np.square(sds))))
    assert abs(pooled / (0.7 * KT) - 1) <= 0.10, pooled / KT
    assert np.ptp(means) > 0.5 * KT  # a clear pilot effect across pilots
    # keyed: the same sortie gives the same closures
    stream = RNG.scope(KeyPath.of(scenario="aar", tail="T", sortie="S0")).stream("pilot", "aar")
    a = aar_closures(tanker_plan(tr), stream, 60.0, PCFG.aar_closure_max)[1]
    b = aar_closures(tanker_plan(tr), stream, 60.0, PCFG.aar_closure_max)[1]
    assert np.array_equal(a, b)
