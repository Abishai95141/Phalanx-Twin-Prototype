"""A2 follow-up (added after run 1, see README "A2"): signal-to-disturbance ladder for the six-parameter
self-test. Same ground truth, inputs, identity and estimator as `a2_selftest.py`; the disturbance bank of the
synthetic "measured" flight is scaled by 0 (texture only) and 0.25 (run 1 used 1.0). It separates estimator
correctness (consistency as the disturbance vanishes) from identifiability at the committed placeholder level.

Criteria (stated before running): scale 0: all six within 5 % of truth; scale 0.25: within 10 %. Each fit is
also repeated as a prediction-error fit with an AR(2) innovations model (`fit_oe(noise_ar=2)`) at scale 0.25.

Usage: python -I a2_ladder.py <out_json>
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from a2_selftest import BASE_AT, FACTOR, NAMES, STEPS, data
from common import SRC  # noqa: F401  (puts src on the path)

from phalanx.proxy.config import load_proxy_config
from phalanx.proxy.ident import fit_oe, nominal, prepare, record_array, transient_weights_of
from phalanx.proxy.inputs import synthetic_inputs


def scaled_bank(cfg, s: float):
    out = []
    for f in cfg.env.factors:
        if f.group != 0:
            out.append(f)
        elif s > 0:
            out.append(replace(f, loadings=tuple(x * s for x in f.loadings)))
    return tuple(out)


def main(out: str) -> None:
    t0 = time.time()
    cfg = load_proxy_config()
    fp = cfg.fadec_params.replace(**BASE_AT)
    inp = synthetic_inputs(120.0, steps=STEPS)
    rec = inp.replay_inputs()
    prob = prepare(cfg, rec, fadec_params=fp)
    th0 = nominal(prob, NAMES)
    truth = {k: float(v * FACTOR[k]) for k, v in zip(NAMES, th0, strict=True)}
    tv = np.array([truth[k] for k in NAMES])
    w = transient_weights_of(rec)
    res: dict = {"truth": truth, "runs": {}}
    for scale, ar in ((0.0, 0), (0.25, 0), (0.25, 2)):
        _i, sf = data(cfg, fp, truth, factors=scaled_bank(cfg, scale))
        y = record_array(sf.record)
        fit = fit_oe(prob, y, NAMES, th0, weights=w[: y.shape[0]], max_iter=15, noise_ar=ar)
        ratio = fit.theta / tv
        key = f"scale{scale}_ar{ar}"
        res["runs"][key] = {
            "ratio_to_truth": dict(zip(NAMES, ratio.tolist(), strict=True)),
            "se_rel": dict(zip(NAMES, (fit.se / tv).tolist(), strict=True)),
            "cost0": fit.cost0, "cost": fit.cost, "iterations": fit.iterations,
        }  # fmt: skip
        print(key, np.round(ratio, 3), flush=True)
    r0 = res["runs"]["scale0.0_ar0"]["ratio_to_truth"].values()
    r1 = res["runs"]["scale0.25_ar0"]["ratio_to_truth"].values()
    res["pass"] = {
        "scale0_within_5pct": all(abs(r - 1) < 0.05 for r in r0),
        "scale0.25_within_10pct": all(abs(r - 1) < 0.10 for r in r1),
    }
    res["seconds"] = round(time.time() - t0, 1)
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1)
    print(res["pass"], res["seconds"], "s")


if __name__ == "__main__":
    main(sys.argv[1])
