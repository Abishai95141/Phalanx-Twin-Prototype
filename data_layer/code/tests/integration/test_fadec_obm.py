"""AD-50: the analytical check must not fire on a healthy engine that merely differs from the on-board model.

The on-board model tables (`obm_*`) and the ratio-unit schedules are fixture-matched (A-W1.3b-7), so agreement
with the W1 fixture plant is circular. Here a healthy TEST FIXTURE plant whose steady maps differ in SHAPE
from
the model's (PS3/P2 -30 % at and below idle, unchanged at high power; T5/T2 +10 %; N1c(N2c) -5 %) runs a PLA
sweep: 30 s at PLA 85 (the adaptive trims settle on the high-power mismatch), a chop to 20 deg, then a slow
ramp back to 85 deg (the reviewer's M07 failure case was a chop). With the default configuration (analytical
check off until an M07-derived on-board model exists) no analytical failure and no substitution may occur; the
negative control (check switched on) shows the mismatch raises false analytical failures, i.e. the default is
what keeps them out. A constant-ratio mismatch alone would be absorbed by the multiplicative trims.

Sample size: one deterministic 90 s run (21,600 truth steps) per configuration.
"""

from __future__ import annotations

import numpy as np
import pytest

import fadec_fixture as fx
from phalanx.fadec import FadecConfig
from phalanx.fadec.codes import V_SUBSTITUTED, active_codes

pytestmark = pytest.mark.integration
N = 90 * 240


def _mismatched_tables():
    pt = fx.plant_tables()
    shape = np.interp(pt.pr_x, [0.665, 0.9], [0.7, 1.0])  # -30 % at and below idle, 0 at high power
    return pt._replace(
        pr_y=np.ascontiguousarray(pt.pr_y * shape),
        t5_y=np.ascontiguousarray(pt.t5_y * 1.1),
        n1_y=np.ascontiguousarray(pt.n1_y * 0.95),
    )


def _sweep(cfg):
    t = np.arange(N) / 240.0
    pla = np.interp(t, [0.0, 30.0, 31.0, 50.0, 80.0, 90.0], [85.0, 85.0, 20.0, 20.0, 85.0, 85.0])[:, None]
    pt = _mismatched_tables()
    sc = fx.Scenario(N, 1, pla_deg=pla)
    x0 = fx.steady_state(84.0)
    return fx.closed_loop(sc, cfg=cfg, x0=x0, pt=pt)


def _analytic_codes(r):
    return {c for m in r.faults[:, 0] for c in active_codes(int(m)) if c.startswith("ENG-04")}


def test_default_config_raises_no_analytical_failure_on_a_healthy_mismatched_engine():
    r = _sweep(FadecConfig.build(fx.fixture_params()))
    assert not _analytic_codes(r)
    assert not (r.cmdi[:, 0, 3:9] == V_SUBSTITUTED).any()


def test_negative_control_the_fixture_matched_model_would_raise_false_failures():
    r = _sweep(FadecConfig.build(fx.fixture_params()).with_cfg(analytic=1))
    assert _analytic_codes(r), "the mismatch is too small to test the default"
