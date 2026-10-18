"""A2 follow-up (added after run 1, see README "A2"): the residual cross-engine coherence controls, rerun with
the corrected estimator (`ident.residual_spectra` now refuses fewer than 8 Welch segments; run 1 used 2
segments of 256 samples on 480 samples, which biases the coherence of independent residuals to about 0.5).

Same ground truth, inputs and identities as `a2_selftest.py`; residuals against the deterministic model at the
true parameters (so only the disturbance response remains). Criteria unchanged from run 1: N2 residual
coherence > 0.8 for the aircraft-common-only bank and < 0.2 for the per-unit-only bank; the committed bank is
reported.

Usage: python -I a2_coherence.py <out_json>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from a2_selftest import BASE_AT, FACTOR, NAMES, STEPS, data
from common import SRC  # noqa: F401  (puts src on the path)

from phalanx.proxy.config import load_proxy_config
from phalanx.proxy.ident import nominal, prepare, record_array, residual_spectra, simulate
from phalanx.proxy.inputs import synthetic_inputs


def main(out: str) -> None:
    cfg = load_proxy_config()
    fp = cfg.fadec_params.replace(**BASE_AT)
    inp = synthetic_inputs(120.0, steps=STEPS)
    prob = prepare(cfg, inp.replay_inputs(), fadec_params=fp)
    th0 = nominal(prob, NAMES)
    truth = {k: float(v * FACTOR[k]) for k, v in zip(NAMES, th0, strict=True)}
    model = simulate(prob, NAMES, np.array([truth[k] for k in NAMES]))
    bank = cfg.env.factors
    res: dict = {}
    for label, keep, sortie in (("committed", None, 1), ("common_only", 0, 2), ("unit_only", 1, 2)):
        fs = bank if keep is None else tuple(f for f in bank if f.group != 0 or f.scope == keep)
        _i, sf = data(cfg, fp, truth, factors=fs, sortie=sortie)
        y = record_array(sf.record)
        n = min(len(y), len(model))
        spec = residual_spectra(y[:n] - model[:n])
        coh = spec["cross_engine_coherence"].tolist()
        res[label] = {
            "coherence": dict(zip(("N1", "N2", "EGT", "FF"), coh, strict=True)),
            "nperseg": int(spec["nperseg"]),
            "segments": int(spec["segments"]),
        }
        print(label, res[label], flush=True)
    res["pass"] = {
        "common_only_N2_gt_0.8": res["common_only"]["coherence"]["N2"] > 0.8,
        "unit_only_N2_lt_0.2": res["unit_only"]["coherence"]["N2"] < 0.2,
    }
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1)
    print(res["pass"])


if __name__ == "__main__":
    main(sys.argv[1])
