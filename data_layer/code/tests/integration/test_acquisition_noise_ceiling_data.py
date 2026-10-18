"""A3 noise ceiling on real flights (W0.5 finding; data, slow).

Question: is M13's configured idiosyncratic noise small enough not to wash out the fast-band structure the
battery measures (B1, B3 (i), B4), while +-1 LSB of independent noise is not?

Design (stated before running):
- Holdout: the round-2 sample batch ``holdout_652_s20`` (n = 20 Tail 652 flights), partner 20 Tail 687
archive-1
  flights, early/late halves as stored: the minimal batch on which the battery's verdicts are known
  (W0.5 test_a3_real_data_controls uses the same batch and found +-1 LSB FAILs B1).
- Arm ``m13_idiosyncratic``: each real flight plus M13's AR(1) noise generator at the MEASURED idiosyncratic
  level of each channel (round-2 M-B ``frozen/S/mb.json``: sigma, phi per engine position), re-quantised on
  the recorder lattice. The real data already contain that noise, so the arm carries ~2x the idiosyncratic
  variance: a conservative stress of the configured ceiling.
- Arm ``noise_1lsb``: the W0.5 negative control (+-1 LSB uniform dither, re-quantised).
- Pass criterion for the ceiling: the idiosyncratic arm draws no FAIL on B1, B3 and B4; the +-1 LSB arm FAILs
  all three (reproducing the W0.5 finding). 2,000 bootstrap resamples, round-2 seed (verdict rule of the
  pre-registration, AD-30).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from phalanx.acquisition import kernel as K
from phalanx.acquisition.core import EVENT_STREAM, NOISE_STREAM
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.validation import dashlink as D
from phalanx.validation.battery import ROUND2_ROOT_SEED, Bootstrap, flight_stats_many, run_battery
from phalanx.validation.reference import load_round2_lists
from phalanx.validation.testing import LSB, dither_requantise

pytestmark = [pytest.mark.data, pytest.mark.slow, pytest.mark.integration]
REPO = Path(__file__).resolve().parents[2]
MB = REPO / "analysis" / "settling_experiment_round2" / "results" / "frozen" / "S" / "mb.json"
S20 = REPO / "analysis" / "settling_experiment_round2" / "results" / "holdout_652_s20"


def m13_noise(sigma: float, phi: float, n: int, keys, sensor: str) -> np.ndarray:
    """M13's own noise path (acq_kernel) on a fine native grid, so the output is the AR(1) noise itself."""
    if sigma == 0.0:
        return np.zeros(n)
    z = keys.stream("acquisition", "noise", sensor=sensor).draws(0, n).reshape(n, 1)
    u = np.ones((n, 1, K.N_U))
    P = np.zeros((1, K.N_AP))
    P[0, [K.AP_SCALE, K.AP_QN, K.AP_SF]] = (1.0, 1e-12, 1e-12)
    P[0, K.AP_SIGMA], P[0, K.AP_PHI], P[0, K.AP_SQ] = sigma, phi, math.sqrt(1 - phi * phi)
    Q = np.zeros((1, K.N_AQ), dtype=np.int64)
    Q[0, K.AQ_CMIN], Q[0, K.AQ_CMAX] = -(10**17), 10**17
    t = np.arange(n, dtype=np.int64) * 250_000_000
    out = K.acq_kernel(
        np.zeros((1, K.N_AF)),
        np.zeros((1, K.N_AI), dtype=np.int64),
        P,
        Q,
        np.ones((1, K.N_PHASE)),
        np.zeros(K.N_PHASE, dtype=np.int64),
        np.zeros((n, 1)),
        np.zeros((n, 1)),
        t,
        t + 250_000_000,
        t,
        np.arange(n, dtype=np.int64),
        np.zeros(n),
        np.full(n, 5, dtype=np.int64),
        z,
        u,
        np.zeros((n, 1), dtype=np.int64),
    )
    return out[3][:, 0]


def idiosyncratic_arm(rec, mb, rng):
    keys = rng.scope(KeyPath.of(scenario="W16_ceiling", tail="652", sortie=rec.flight_id.replace(".mat", "")))
    outs = {}
    for f, X in rec.outputs.items():
        X = np.array(X, float)
        Y = np.empty_like(X)
        for k in range(X.shape[0]):
            nz = mb["noise"][f"{f}_{k + 1}"]
            e = m13_noise(nz["sigma"], nz["phi"], X.shape[1], keys, f"{f}_{k + 1}")
            Y[k] = LSB[f] * np.rint((X[k] + e) / LSB[f])
        outs[f] = Y
    return rec.replace_outputs(outs, control="m13_idiosyncratic")


def test_configured_noise_does_not_wash_out_the_fast_band(dashlink_652_dir, dashlink_687_dir):
    if not (S20 / "list_holdout.txt").is_file():
        pytest.skip("round-2 sample-batch lists not available")
    lists = load_round2_lists(S20)
    mb = json.loads(MB.read_text())
    H = [D.load_record(dashlink_652_dir / f) for f in lists["holdout"]]
    P = [D.load_record(dashlink_687_dir / f) for f in lists["partner"]]
    rng = RngService(20261016, StreamRegistry([NOISE_STREAM, EVENT_STREAM]))
    arms = {
        "m13_idiosyncratic": flight_stats_many([idiosyncratic_arm(r, mb, rng) for r in H]),
        "noise_1lsb": flight_stats_many([dither_requantise(r) for r in H]),
    }
    i = {f: k for k, f in enumerate(lists["holdout"])}
    early, late = [i[f] for f in lists["early"]], [i[f] for f in lists["late"]]
    rep = run_battery(
        flight_stats_many(H),
        flight_stats_many(P),
        early,
        late,
        arms,
        Bootstrap(np.random.SeedSequence(ROUND2_ROOT_SEED)),
    )
    v = {a: {t: x.verdict for t, x in r.verdicts.items()} for a, r in rep.arms.items()}
    summary = {
        a: {
            t: (x.verdict, {p: round(float(q.D_sim), 4) for p, q in x.parts.items()})
            for t, x in r.verdicts.items()
        }
        for a, r in rep.arms.items()
    }
    summary["bars_D_tail"] = {t: v["D"] for t, v in rep.to_dict()["D_tail"].items()}
    print(json.dumps(summary, indent=1, default=str))  # evidence for the W1.6 report
    for t in ("B1", "B3", "B4"):
        assert v["m13_idiosyncratic"][t] != "FAIL", (t, summary["m13_idiosyncratic"][t])
        assert v["noise_1lsb"][t] == "FAIL", (t, summary["noise_1lsb"][t])
