"""A2 (W2.4a): the identification machinery recovers known parameters on a synthetic proxy flight, before any
real data is used. No data file is read.

Ground truth: the proxy configuration with six identification parameters moved off their nominal values
(inside the declared ranges): LP and HP rotor inertias (H_LP 0.6 -> 0.84 s, H_HP 0.3 -> 0.24 s), governor
gains (Kp 2.0 -> 2.6, Ki 1.0 -> 0.7 1/s), EGT word thermocouple tau_ref (0.81 -> 1.10 s) and FF meter tau
(0.218 -> 0.30 s).

"Measured" data: the full proxy chain (fused System) with the committed M03 disturbance bank active and the
M13 DASHlink texture (quantisation, lattice, noise, freezes): `phalanx.proxy.run.simulate_flight`, identity
`a2-selftest/T687/1`, on deterministic synthetic inputs (cruise, 20,000 ft, M 0.6, A/T engaged, five
N1-command steps of 2-4 % over 120 s).

Estimators (`phalanx.proxy.ident`):
1. indirect transient-weighted output error (closed loop from the commands), all six parameters, from the
   nominal values;
2. direct method (plant driven by the measured FF word) for the plant parameters (inertias, EGT tau), to show
   the closed-loop bias the indirect method avoids;
3. disturbance spectra of the OE residuals: cross-engine residual coherence for the committed bank, and for
   two control banks (aircraft-common factors only / per-unit factors only) whose answer is known in sign.

Sample: one 120 s synthetic flight (28,800 truth steps, 480 ACMS samples per engine x 4 engines): the
smallest window with several accel and decel steps for every dynamic parameter. Pass criteria (stated before
running): every OE estimate within 10 % of its true value (inertias, gains, taus); common-only coherence > 0.8
and unit-only coherence < 0.2 in the N2 residuals.

Usage: python -I a2_selftest.py <out_json>
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from common import SRC  # noqa: F401  (puts src on the path)

from phalanx.core.rng import KeyPath
from phalanx.proxy.config import load_proxy_config
from phalanx.proxy.ident import (
    configure,
    fit_direct,
    fit_oe,
    nominal,
    prepare,
    record_array,
    residual_spectra,
    simulate,
    transient_weights_of,
)
from phalanx.proxy.inputs import synthetic_inputs
from phalanx.proxy.run import simulate_flight

NAMES = ("i_lp", "i_hp", "gov_kp", "gov_ki", "tau_egt", "tau_ff")
FACTOR = {
    "i_lp": 1.4,
    "i_hp": 0.8,
    "gov_kp": 1.3,
    "gov_ki": 0.7,
    "tau_egt": 1.10 / 0.81,
    "tau_ff": 0.30 / 0.218,
}
STEPS = ((10.0, 3.0), (30.0, -3.0), (50.0, 2.0), (70.0, -4.0), (95.0, 4.0))
BASE_AT = {"at_kp": 0.3, "at_ki": 0.2, "at_rate": 0.1}


def data(cfg, fp, theta, seconds=120.0, factors=None, sortie=1):
    cfg_t, fp_t = configure(cfg, theta, fp)
    if factors is not None:
        cfg_t = cfg_t.with_factors(factors)
    inp = synthetic_inputs(seconds, steps=STEPS)
    sf = simulate_flight(
        cfg_t, inp, identity=KeyPath.of(scenario="a2-selftest", tail="T687", sortie=sortie), root=2026,
        fadec_params=fp_t,
    )  # fmt: skip
    return inp, sf


def main(out: str) -> None:
    t0 = time.time()
    cfg = load_proxy_config()
    fp = cfg.fadec_params.replace(**BASE_AT)
    inp = synthetic_inputs(120.0, steps=STEPS)
    prob = prepare(cfg, inp.replay_inputs(), fadec_params=fp)
    th0 = nominal(prob, NAMES)
    truth = {k: float(v * FACTOR[k]) for k, v in zip(NAMES, th0, strict=True)}
    _inp, sf = data(cfg, fp, truth)
    y = record_array(sf.record)
    w = transient_weights_of(inp.replay_inputs())[: y.shape[0]]
    res: dict = {
        "n_samples": int(y.shape[0]),
        "truth": truth,
        "nominal": dict(zip(NAMES, th0.tolist(), strict=True)),
    }
    # 1. indirect OE, all six
    fit = fit_oe(prob, y, NAMES, th0, weights=w, max_iter=15)
    res["oe"] = {
        "theta": dict(zip(NAMES, fit.theta.tolist(), strict=True)),
        "ratio_to_truth": {k: float(v / truth[k]) for k, v in zip(NAMES, fit.theta, strict=True)},
        "se": dict(zip(NAMES, fit.se.tolist(), strict=True)),
        "cost0": fit.cost0, "cost": fit.cost, "iterations": fit.iterations,
    }  # fmt: skip
    print("OE", res["oe"]["ratio_to_truth"], fit.cost0, "->", fit.cost, flush=True)
    # 2. direct method on the plant parameters
    pn = ("i_lp", "i_hp", "tau_egt")
    th0p = nominal(prob, pn)
    fd = fit_direct(prob, y, pn, th0p, weights=w, max_iter=15)
    res["direct"] = {
        "theta": dict(zip(pn, fd.theta.tolist(), strict=True)),
        "ratio_to_truth": {k: float(v / truth[k]) for k, v in zip(pn, fd.theta, strict=True)},
        "cost0": fd.cost0, "cost": fd.cost, "iterations": fd.iterations,
    }  # fmt: skip
    print("direct", res["direct"]["ratio_to_truth"], flush=True)
    # 3. residual spectra: committed bank, common-only and unit-only control banks
    resid = y[: prob.n_samples] - simulate(prob, NAMES, fit.theta)[: y.shape[0]]
    spec = residual_spectra(resid)
    res["residual_coherence_committed"] = dict(
        zip(("N1", "N2", "EGT", "FF"), spec["cross_engine_coherence"].tolist(), strict=True)
    )
    bank = cfg.env.factors
    for label, keep in (("common_only", 0), ("unit_only", 1)):
        fs = tuple(f for f in bank if f.group != 0 or f.scope == keep)
        _i, sfc = data(cfg, fp, truth, factors=fs, sortie=2)
        yc = record_array(sfc.record)
        rc = yc[: prob.n_samples] - simulate(prob, NAMES, np.array([truth[k] for k in NAMES]))[: yc.shape[0]]
        coh = residual_spectra(rc)["cross_engine_coherence"]
        res[f"residual_coherence_{label}"] = dict(zip(("N1", "N2", "EGT", "FF"), coh.tolist(), strict=True))
        print(label, res[f"residual_coherence_{label}"], flush=True)
    ok_oe = all(abs(r - 1.0) < 0.10 for r in res["oe"]["ratio_to_truth"].values())
    ok_coh = (
        res["residual_coherence_common_only"]["N2"] > 0.8 and res["residual_coherence_unit_only"]["N2"] < 0.2
    )
    res["pass"] = {"oe_within_10pct": ok_oe, "coherence_controls": ok_coh}
    res["seconds"] = round(time.time() - t0, 1)
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1)
    print("PASS" if ok_oe and ok_coh else "FAIL", res["pass"], res["seconds"], "s")


if __name__ == "__main__":
    main(sys.argv[1])
