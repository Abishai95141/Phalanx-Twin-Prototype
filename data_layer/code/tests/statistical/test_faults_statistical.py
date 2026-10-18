"""M11 stochastic onsets reproduce their parameters (event-rate tests with stated n and exact CIs):

- Poisson onsets (FOD/bird): count over n = 400 one-hour sorties vs Poisson(rate x ingestion x hours);
- per-event onsets (AB no-light): count over 400 sorties x 4 AB lights vs Binomial(1,600, p);
- two-state Markov intermittents: next-sortie recurrence ≈ 1 - p_off (RADC 14-21 % [TRANSFER]).

Rates are raised with ParamSet.replace so the expected counts are ~10^2 (power, not realism, is under test);
the CI is exact (scipy.stats), two-sided at 99 %."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph

SEC = 10**9
DAY = 86_400 * SEC
N = 400


def run(fp, root=0x57A7):
    cfg = FaultConfig(load_catalogue(), load_graph(), {}, ("IN20-0001",), (), stochastic=True)
    f = FaultInjector("faults", fp, config=cfg)
    sysm = System(
        [f], [], rng=RngService(root, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail="KH2011")
    )
    evs = []
    for k in range(N):
        t = k * DAY
        evs += [
            Event(
                t + 1,
                "faults.sortie_start",
                "faults",
                {"sortie_id": f"KH2011-{k}", "duration_s": 3600.0, "ab_lights": 4.0, "starts": 1.0},
            ),
            Event(t + 3600 * SEC + 1, "faults.sortie_end", "faults", {"flight_time_s": 3600.0}),
        ]
    w = sysm.inject(sysm.start(), evs)
    w, _ = sysm.run(w, N * 240 * 86_400 + 2)
    return f, w.states["faults"]


def count(f, st, mode):
    mi = f.mode_index(mode)
    return int(np.count_nonzero(st["inst_mode"] == mi)), st, mi


@pytest.mark.statistical
def test_poisson_onset_rate_matches_parameter():
    fp = load_fault_params().replace(bird_strike_rate=1.0 / 3600.0)  # 1 per hour x 0.25 ingestion
    f, st = run(fp)
    n, *_ = count(f, st, "FM.ENG.FOD_BIRD")
    lam = 1.0 * fp.value("engine_ingestion_fraction") * N
    lo, hi = stats.poisson.ppf(0.005, lam), stats.poisson.ppf(0.995, lam)
    assert lo <= n <= hi, (n, lam)


@pytest.mark.statistical
def test_per_event_onset_matches_binomial():
    fp = load_fault_params().replace(ab_no_light_p=0.05)
    f, st = run(fp)
    n, *_ = count(f, st, "FM.ENG.AB_NO_LIGHT")
    trials = 4 * N
    lo, hi = stats.binom.ppf(0.005, trials, 0.05), stats.binom.ppf(0.995, trials, 0.05)
    assert lo <= n <= hi, n


@pytest.mark.statistical
def test_markov_intermittent_recurrence():
    """With p_on raised to 0.3, the fraction of active sorties followed by an active sortie is
    1 - p_off = 0.17 (binomial 99 % CI over the observed active sorties)."""
    fp = load_fault_params().replace(intermittent_p_on=0.3)
    f, st = run(fp)
    mi = f.mode_index("FM.AV.INTERMITTENT_CONNECTOR")
    sel = st["inst_mode"] == mi
    sortie_idx = sorted(int(s.split("-")[1]) for s in st["inst_sortie"][sel])
    active = np.zeros(N, bool)
    active[sortie_idx] = True
    on = np.flatnonzero(active[:-1])
    stay = int(np.count_nonzero(active[on + 1]))
    p_stay = 1.0 - fp.value("intermittent_p_off")
    lo, hi = stats.binom.ppf(0.005, on.size, p_stay), stats.binom.ppf(0.995, on.size, p_stay)
    assert lo <= stay <= hi, (stay, on.size)
    pi = 0.3 / (0.3 + fp.value("intermittent_p_off"))
    assert active.mean() == pytest.approx(pi, abs=0.08)


@pytest.mark.statistical
def test_exogenous_draws_are_crn_across_forks():
    """CRN (A7, I8): the sortie-keyed fault draws of sortie k are identical whatever else happened before it
    (here: a scripted fault injected in one branch only)."""
    fp = load_fault_params().replace(bird_strike_rate=1.0 / 3600.0)
    cfg = FaultConfig(load_catalogue(), load_graph(), {}, ("IN20-0001",), (), stochastic=True)

    def branch(extra):
        f = FaultInjector("faults", fp, config=cfg)
        sysm = System(
            [f],
            [],
            rng=RngService(0x57A7, StreamRegistry()),
            identity=KeyPath.of(scenario="S1", tail="KH2011"),
        )
        evs = [*extra]
        for k in range(40):
            t = k * DAY
            evs += [
                Event(
                    t + 1, "faults.sortie_start", "faults", {"sortie_id": f"KH2011-{k}", "duration_s": 3600.0}
                ),
                Event(t + 3600 * SEC + 1, "faults.sortie_end", "faults", {"flight_time_s": 3600.0}),
            ]
        w = sysm.inject(sysm.start(), evs)
        w, _ = sysm.run(w, 40 * 240 * 86_400 + 2)
        st = w.states["faults"]
        mi = f.mode_index("FM.ENG.FOD_BIRD")
        sel = (st["inst_mode"] == mi) & (st["inst_sortie"] != "")
        return sorted(
            zip(
                st["inst_sortie"][sel].tolist(),
                st["inst_t0"][sel].tolist(),
                st["inst_sev"][sel].tolist(),
                strict=True,
            )
        )

    a = branch([])
    b = branch([Event(5 * DAY, "faults.inject", "faults", {"mode": "FM.ENG.HPC_DAMAGE"})])
    assert a == b and len(a) > 0
