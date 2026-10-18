"""A10: first integrated behaviour glance (development only, **not a gate**; W2.1 brief).

Fast-band (> 0.2 Hz) correlations N1-N2, N2-FF, N1-EGT, N1-FF and the lead-lag order FF->N2, FF->N1, N2->N1,
FF->EGT, N1->EGT on the integrated Tejas loop, with the registered round-2 estimators
(``phalanx.validation.battery.stats.b1_stats`` / ``b2_stats``, one engine position, 4 Hz, airborne rule
N1 > 25 %), compared **structurally** with ``docs/behavioural_targets.md`` (Tejas mode is held to signs,
orderings and coherence < 1, not to the proxy magnitudes).

Sample: the 5 mission-type-diverse gate sorties (``phalanx.integration.flights.diverse_sorties``, n = 5), each
over its flown portion from post-start idle to the window end or the physical-invariant abort (the A6
blockers: the flown portion is ground idle, taxi, run-up, take-off and about a minute of flight; the phase mix
is printed). Two views: truth ports sampled at 4 Hz, and the recorded channels (ENG.N1.V, ENG.N2.V, ENG.T5,
ENG.WFM) as the 4 Hz sample-and-hold of the M13 CIR. Medians over the 5 sorties.

The only assertions are that the statistics are computable on every sortie (n stated); the structural
comparison is printed for the W2.1 report and the W2.3/W2.4 work, never used as a pass/fail bar here.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.dictionary import load_dictionary
from phalanx.integration.flights import diverse_sorties, fly
from phalanx.validation.battery.config import LAG_PAIRS, BatteryConfig
from phalanx.validation.battery.stats import b1_stats, b2_stats

pytestmark = [pytest.mark.statistical, pytest.mark.slow]
N_SORTIES = 5
CFG = BatteryConfig(n_units=1)
#: behavioural_targets.md (real Tail 652 medians) and the structural expectation for Tejas mode
B1_TARGET = {"N1~N2": 0.47, "N1~EGT": 0.56, "N1~FF": 0.65, "N2~FF": 0.67}
B2_TARGET = {"FF>N2": -0.50, "FF>N1": 0.00, "N2>N1": +0.50, "FF>EGT": +0.75, "N1>EGT": None}
STRUCTURE = {
    "N1~N2": lambda r: 0.0 < r < 0.9,  # coupled but not lockstep (round-2 open loop: 0.92)
    "N1~EGT": lambda r: r > 0.0,
    "N1~FF": lambda r: r > 0.0,
    "N2~FF": lambda r: r > 0.0,
    "FF>N2": lambda x: x < 0.0,  # fuel responds to speed error: closed-loop governing (AD-31)
    "N2>N1": lambda x: x > 0.0,  # the fan follows the core
    "FF>EGT": lambda x: x > 0.0,  # gas-path and thermocouple lag
}


def _series(f, view: str) -> dict[str, np.ndarray]:
    if view == "truth":
        ref = load_dictionary().param_set("channel_reference")
        n1_100, n2_100 = float(ref.value("n1_100pct")), float(ref.value("n2_100pct"))
        T = f.truth
        return {
            "N1": T["eng.n1"] / n1_100 * 100.0,
            "N2": T["eng.n2"] / n2_100 * 100.0,
            "EGT": T["eng.t5"] - 273.15,
            "FF": T["eng.wf"] * 3600.0 / 0.45359237,
        }
    R = f.recorded
    return {"N1": R["ENG.N1.V"], "N2": R["ENG.N2.V"], "EGT": R["ENG.T5"], "FF": R["ENG.WFM"]}


def _stats(Y: dict[str, np.ndarray]):
    ok = np.all([np.isfinite(v) for v in Y.values()], axis=0)
    Yc = {k: v[ok][None, :] for k, v in Y.items()}
    r = b1_stats(Yc, CFG)
    lags = b2_stats(Yc, CFG)
    names = CFG.pair_names
    fast = None if r is None else {n.replace("_1", ""): float(x) for n, x in zip(names, r[1], strict=True)}
    lag = None if lags is None else {f"{a}>{b}": float(x) for (a, b), x in zip(LAG_PAIRS, lags, strict=True)}
    return fast, lag, int(ok.sum())


@pytest.fixture(scope="module")
def flights():
    return [fly(p) for p in diverse_sorties(N_SORTIES)]


@pytest.mark.parametrize("view", ["truth", "recorded"])
def test_behaviour_glance(flights, view):
    rows_b1: dict[str, list[float]] = {}
    rows_b2: dict[str, list[float]] = {}
    lines = []
    for f in flights:
        fast, lag, n = _stats(_series(f, view))
        ph, cnt = np.unique(f.phase, return_counts=True)
        names = load_dictionary().code_table("flight_phase")["codes"]
        mix = ", ".join(f"{names[str(int(a))]} {c / f.phase.size:.0%}" for a, c in zip(ph, cnt, strict=True))
        lines.append(
            f"  {f.sortie_id} {f.mission_type}: {n} samples at 4 Hz ({n / 4:.0f} s); phase mix {mix}"
        )
        assert fast is not None and lag is not None, (f.sortie_id, view, n)
        for k in B1_TARGET:
            rows_b1.setdefault(k, []).append(fast[k])
        for k in B2_TARGET:
            rows_b2.setdefault(k, []).append(lag[k])
    print(f"\nA10 behaviour glance ({view}), n = {len(flights)} sorties (development only, not a gate)")
    print("\n".join(lines))
    print(f"  {'pair':8s} {'median':>7s} {'range':>17s} {'real 652':>9s}  structure")
    for k, v in {**rows_b1, **rows_b2}.items():
        med = float(np.median(v))
        tgt = {**B1_TARGET, **B2_TARGET}[k]
        chk = STRUCTURE.get(k)
        verdict = "-" if chk is None else ("matches" if chk(med) else "DIFFERS")
        tgt_s = "-" if tgt is None else f"{tgt:+.2f}"
        print(f"  {k:8s} {med:+7.2f} [{min(v):+7.2f}, {max(v):+7.2f}] {tgt_s:>9s}  {verdict}")
    assert len(flights) == N_SORTIES
