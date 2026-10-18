"""A2 follow-up 2 (added after the ladder's texture-only rung, see README "A2"): identifiability split.

The six-parameter fit on texture-only data reached a lower cost than the truth (the identification model
omits the M13 lane texture inside the loop) and moved the weakly identified governor gains by 23-31 %
(Jacobian condition 22; the gain columns have the smallest norms). This run separates the two groups:

(a) plant and sensor parameters (i_lp, i_hp, tau_egt, tau_ff) with the governor gains held at their true
    values, A/T step flight (as `a2_selftest.py`), bank scale 0 and 0.25;
(b) the governor gains (gov_kp, gov_ki) alone with the plant at truth, on a **manual lever-step** flight (the
    A/T outer loop off, so the inner governor is excited directly), bank scale 0 and 0.25.

Criteria (stated before running): (a) within 5 % at scale 0 and 10 % at 0.25; (b) reported (no criterion: it
measures gain identifiability).

Usage: python -I a2_subset.py <out_json>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from a2_ladder import scaled_bank
from a2_selftest import BASE_AT, FACTOR, NAMES, STEPS
from common import SRC  # noqa: F401  (puts src on the path)

from phalanx.core.rng import KeyPath
from phalanx.proxy.config import load_proxy_config
from phalanx.proxy.ident import configure, fit_oe, nominal, prepare, record_array, transient_weights_of
from phalanx.proxy.inputs import synthetic_inputs
from phalanx.proxy.run import simulate_flight

PLANT = ("i_lp", "i_hp", "tau_egt", "tau_ff")
GAINS = ("gov_kp", "gov_ki")
LEVER_STEPS = ((10.0, 4.0), (30.0, -4.0), (50.0, 3.0), (70.0, -6.0), (95.0, 6.0))


def run(cfg, fp, inp, truth, names, scale):
    rec = inp.replay_inputs()
    prob = prepare(cfg, rec, fadec_params=fp)
    cfg_t, fp_t = configure(cfg, truth, fp)
    sf = simulate_flight(
        cfg_t.with_factors(scaled_bank(cfg, scale)), inp,
        identity=KeyPath.of(scenario="a2-selftest", tail="T687", sortie=1), root=2026, fadec_params=fp_t,
    )  # fmt: skip
    y = record_array(sf.record)
    w = transient_weights_of(rec)[: y.shape[0]]
    # the held parameters at truth in the model as well: configure the problem's vectors through `names` only
    th0 = nominal(prob, names)
    fixed = [k for k in NAMES if k not in names]
    prob_t = prepare(cfg_t, rec, fadec_params=fp_t) if fixed else prob
    fit = fit_oe(prob_t, y, names, th0, weights=w, max_iter=15)
    tv = np.array([truth[k] for k in names])
    return dict(zip(names, (fit.theta / tv).tolist(), strict=True)), fit.iterations


def main(out: str) -> None:
    cfg = load_proxy_config()
    fp = cfg.fadec_params.replace(**BASE_AT)
    at_inp = synthetic_inputs(120.0, steps=STEPS)
    th_all = nominal(prepare(cfg, at_inp.replay_inputs(), fadec_params=fp), NAMES)
    truth = {k: float(v * FACTOR[k]) for k, v in zip(NAMES, th_all, strict=True)}
    res: dict = {"truth": truth}
    lever_inp = synthetic_inputs(120.0, autothrottle=False, pla_deg=65.0, steps=LEVER_STEPS)
    for label, inp, names in (("a_plant_AT_steps", at_inp, PLANT), ("b_gains_lever_steps", lever_inp, GAINS)):
        for scale in (0.0, 0.25):
            ratio, it = run(cfg, fp, inp, truth, names, scale)
            res[f"{label}_scale{scale}"] = {"ratio_to_truth": ratio, "iterations": it}
            print(label, scale, {k: round(v, 3) for k, v in ratio.items()}, flush=True)
    a0 = res["a_plant_AT_steps_scale0.0"]["ratio_to_truth"].values()
    a1 = res["a_plant_AT_steps_scale0.25"]["ratio_to_truth"].values()
    res["pass"] = {"a_scale0_within_5pct": all(abs(r - 1) < 0.05 for r in a0),
                   "a_scale0.25_within_10pct": all(abs(r - 1) < 0.10 for r in a1)}  # fmt: skip
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1)
    print(res["pass"])


if __name__ == "__main__":
    main(sys.argv[1])
