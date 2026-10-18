"""PROXY limitation test (A-W2.4a-11, W2.4a-2 stage 5; coordinator decision 2026-10-15): the recorded FF and
EGT words of the DASHlink proxy carry the slowness the CAL transients show as recorded-indication lags in
M12 (FF indication / damping path tau 1.53 s; EGT indication tau_ref 4.33 s with the thermocouple flux
law), not as fuel-control or gas-path dynamics. A real fuel-flow transducer does not respond in 1.5 s, so
the recorded FF of the proxy trails the true fuel flow by about that lag: this test makes the limitation
visible.

A commanded fuel step (A/T off, lever step at cruise, no process disturbances): the true fuel flow (M07, the
truth record) reaches 63 % of its step well before the recorded-path FF word (M12 output, no texture); the
recorded word equals a first-order lag of the truth with the configured time constant; the round-2 value
(0.218 s, the negative control) removes most of the delay. EGT: the word trails the true T5 by several
seconds at cruise airflow.

Sample: one 40 s synthetic flight (no data, no randomness in the compared quantities).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.rng import KeyPath
from phalanx.dictionary.params import load_param_set
from phalanx.proxy.config import PLATFORM, load_proxy_config
from phalanx.proxy.ident import configure
from phalanx.proxy.inputs import synthetic_inputs
from phalanx.proxy.run import simulate_flight

pytestmark = pytest.mark.integration
ID = KeyPath.of(scenario="proxy-word-lags", tail="T0", sortie=1)
T_STEP = 10.0
RATE = 4.0


@pytest.fixture(scope="module")
def cfg():
    c = load_proxy_config()
    return c.with_factors(tuple(f for f in c.env.factors if f.group != 0))


def _step_run(cfg, fp=None):
    inp = synthetic_inputs(40.0, autothrottle=False, pla_deg=60.0, steps=((T_STEP, 8.0),))
    return simulate_flight(cfg, inp, identity=ID, root=17, fadec_params=fp)


def _t63(y: np.ndarray) -> float:
    """Time [s] after the step at which y covers 63 % of its change (pre-step mean to the last 5 s mean)."""
    k0 = round(T_STEP * RATE)
    y0, y1 = y[k0 - 8 : k0].mean(), y[-20:].mean()
    frac = (y[k0:] - y0) / (y1 - y0)
    return float(np.flatnonzero(frac >= 0.632)[0]) / RATE


def _lag(x: np.ndarray, tau: float) -> np.ndarray:
    """First-order lag of a 4-Hz series (first-order-hold exact discretisation, as M12's lag1)."""
    h = 1.0 / RATE
    a = np.exp(-h / tau)
    y = np.empty_like(x)
    y[0] = x[0]
    for k in range(1, x.size):
        y[k] = x[k] + (y[k - 1] - x[k - 1]) * a + (x[k - 1] - x[k]) * (tau / h) * (1.0 - a)
    return y


def test_recorded_ff_trails_the_true_fuel_flow_by_the_identified_lag(cfg):
    tau_ff = float(load_param_set("M12", "ff_indication", platform=PLATFORM).value("tau"))
    assert tau_ff > 1.0  # the stage-5 identified value (PROXY); the round-2 value was 0.218 s
    sf = _step_run(cfg)
    wf = np.asarray(sf.truth.outputs["FF"])[0]
    ff = np.asarray(sf.sensor.outputs["FF"])[0]
    # a real fuel step [lb/h] (about 200 at 20,000 ft)
    assert wf[-20:].mean() - wf[: round(T_STEP * RATE)].mean() > 150.0
    delay = _t63(ff) - _t63(wf)
    assert tau_ff - 0.5 < delay < tau_ff + 0.5, (delay, tau_ff)
    # the recorded path is a first-order lag of the truth with the configured time constant
    model = _lag(wf, tau_ff)
    step = wf[-20:].mean() - wf[:40].mean()
    assert np.max(np.abs(ff - model)) < 0.05 * step
    # negative control: the round-2 MEASURED 0.218 s leaves almost no delay
    cfg_r2, fp = configure(cfg, {"tau_ff": 0.218})
    sf2 = _step_run(cfg_r2, fp)
    d2 = _t63(np.asarray(sf2.sensor.outputs["FF"])[0]) - _t63(np.asarray(sf2.truth.outputs["FF"])[0])
    assert d2 < 0.5, d2


def test_recorded_egt_trails_the_true_t5_by_seconds_at_cruise(cfg):
    sf = _step_run(cfg)
    t5 = np.asarray(sf.truth.outputs["EGT"])[0]
    egt = np.asarray(sf.sensor.outputs["EGT"])[0]
    delay = _t63(egt) - _t63(t5)
    # tau_ref 4.33 s at W_ref 112 kg/s scales as W^-0.5: about 6 s at cruise airflow
    assert 3.0 < delay < 10.0, delay
