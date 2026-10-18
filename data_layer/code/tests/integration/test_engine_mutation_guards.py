"""M07 tests that pin wiring the W1.3a review's mutation run showed was unguarded (8 of 19 mutants survived).

Each test states the mutant class it kills. Samples: 2 s open-loop windows at 80 % of MIL fuel (fixed fuel, so
every disturbance acts through the plant alone), single-tick derivative evaluations, and short command steps.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.engine.design import build_engine_model, load_engine_params
from phalanx.engine.kernel import deriv_point, pressure_error
from phalanx.engine.layout import (
    NX,
    PI,
    U_A8,
    U_WF,
    W_ENGINE_NAMES,
    X_N1,
    X_N2,
    X_P5,
    X_P6,
    X_P21,
    X_P45,
    X_WFM,
    Y_NAMES,
    A,
)
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state


@pytest.fixture(scope="module")
def model():
    return build_engine_model()


@pytest.fixture(scope="module")
def part(model):
    ss = steady_state(model, design_inputs(model, wf_cmd=0.8 * model.design.stations["wf"]))
    assert ss.converged
    return ss


# expected sign of the 2 s response to a +0.5 % step in each w_engine channel, fixed fuel (open loop)
DIST_SIGNS = {
    "fuel_metering": {"wf": +1, "n2": +1, "n1": +1, "t5": +1},
    "combustor_eff": {"wf": 0, "n2": +1, "n1": +1, "t5": +1},
    "inlet_recovery": {"p2": +1, "w2": +1, "n2": -1, "t5": -1},
    "shaft_load": {"n2": -1, "n1": -1, "w2": -1, "t5": +1},
    "fan_face": {"w2": -1, "n1": +1},
}


@pytest.mark.integration
@pytest.mark.parametrize("channel", W_ENGINE_NAMES)
def test_disturbance_channel_signs(model, part, channel):
    """Kills sign flips of each process-disturbance channel (shaft_load and inlet_recovery survived): +0.5 %
    on one channel moves the outputs in the physical directions (more metered fuel or burner efficiency ->
    faster and hotter; more inlet recovery -> higher P2 and airflow, lower corrected fuel so lower N2 and T5;
    more HP shaft load -> slower and hotter; more fan-face distortion -> less airflow, unloaded fan so higher
    N1). Changes below 1e-4 relative count as zero."""
    st = state_from_x(model, part.x)
    n = 480
    base = simulate(model, st, *input_block(n, 1, part.u)).y[-1, 0]
    w = np.zeros((n, 1, len(W_ENGINE_NAMES)))
    w[:, 0, W_ENGINE_NAMES.index(channel)] = 0.005
    y = simulate(model, st, *input_block(n, 1, part.u, w_engine=w)).y[-1, 0]
    for k, sign in DIST_SIGNS[channel].items():
        j = Y_NAMES.index(k)
        rel = y[j] / base[j] - 1.0
        got = 0 if abs(rel) < 1e-4 else int(np.sign(rel))
        assert got == sign, (channel, k, rel)


@pytest.mark.integration
def test_stall_margin_port_is_min_of_fan_and_hpc(model, part):
    """Kills stall_margin = HPC-only (or fan-only): at MIL the HPC margin is the smaller, at 80 % fuel the fan
    margin is; the port equals the minimum at both."""
    for ss in (steady_state(model, design_inputs(model)), part):
        r = simulate(model, state_from_x(model, ss.x), *input_block(2, 1, ss.u), record_aux=True)
        a = r.aux[-1, 0]
        assert r.y[-1, 0, Y_NAMES.index("stall_margin")] == min(a[A["sm_fan"]], a[A["sm_hpc"]])
    mil = steady_state(model, design_inputs(model)).aux
    assert mil[A["sm_hpc"]] < mil[A["sm_fan"]] and part.aux[A["sm_fan"]] < part.aux[A["sm_hpc"]]


@pytest.mark.integration
def test_fuel_metering_valve_time_constant_and_transport_delay(model, part):
    """Pins the FMV first-order lag (tau_fmv) on the metered flow and the transport delay (n_delay ticks)
    between metering and the combustor: after a command step the metered flow reaches 63.2 % of the step at
    tau_fmv (within one tick), and the combustor flow (aux wf_line) does not move before n_delay ticks."""
    tau = model.p[PI["tau_fmv"]]
    n = 120
    wf = np.full(n, part.u[U_WF])
    wf[1:] *= 1.1
    r = simulate(model, state_from_x(model, part.x), *input_block(n, 1, part.u, wf_cmd=wf), record_aux=True)
    met = r.y[:, 0, Y_NAMES.index("wf")]
    frac = (met - met[0]) / (met[-1] - met[0])
    k63 = int(np.argmax(frac >= 1.0 - np.exp(-1.0)))
    assert abs((k63 - 1 + 1) * model.dt - tau) <= model.dt, (k63, tau)
    line = r.aux[:, 0, A["wf_line"]]
    first = int(np.argmax(np.abs(line - line[0]) > 0.0))
    assert first == 1 + model.n_delay, (first, model.n_delay)


@pytest.mark.integration
def test_n_delay_zero_path(part):
    """Exercises the n_delay = 0 branch (fuel_transport_delay 0) and kills a fuel-metering disturbance dropped
    on it (mutant M04): with a non-zero fuel_metering disturbance the combustor flow (aux wf_line) equals the
    disturbed metered flow in the same tick, the compiled kernel equals the pure-Python outer loop bitwise,
    and the step then moves the combustor exit temperature a full transport delay earlier than with the
    default model."""
    ps = load_engine_params().replace(fuel_transport_delay=0.0)
    m0 = build_engine_model(ps)
    assert m0.n_delay == 0
    n = 48
    wf = np.full(n, part.u[U_WF])
    wf[1:] *= 1.1
    w = np.zeros((n, 1, len(W_ENGINE_NAMES)))
    w[:, 0, W_ENGINE_NAMES.index("fuel_metering")] = 0.02 + 0.01 * np.sin(np.arange(n) / 3.0)
    u, ui = input_block(n, 1, part.u, wf_cmd=wf, w_engine=w)
    r = simulate(m0, state_from_x(m0, part.x), u, ui, record_aux=True)
    ref = simulate(m0, state_from_x(m0, part.x), u, ui, record_aux=True, compiled=False)
    assert np.array_equal(r.y, ref.y)
    met = r.y[:, 0, Y_NAMES.index("wf")]
    line = r.aux[:, 0, A["wf_line"]]
    wfm = r.state.f[0, X_WFM]  # end-of-window metered flow without the disturbance
    assert np.allclose(line, met, rtol=1e-12, atol=0.0)
    assert abs(met[-1] / wfm - 1.0 - w[-1, 0, 0]) < 1e-12 and abs(w[-1, 0, 0]) > 1e-3
    u, ui = input_block(n, 1, part.u, wf_cmd=wf)
    r = simulate(m0, state_from_x(m0, part.x), u, ui, record_aux=True)
    m10 = build_engine_model()
    r10 = simulate(m10, state_from_x(m10, part.x), u, ui, record_aux=True)
    t0, t10 = r.aux[:, 0, A["t41_ad"]], r10.aux[:, 0, A["t41_ad"]]
    k0 = int(np.argmax(np.abs(t0 - t0[0]) > 1e-9 * t0[0]))
    k10 = int(np.argmax(np.abs(t10 - t10[0]) > 1e-9 * t10[0]))
    assert k0 == 1 and k10 == 1 + m10.n_delay, (k0, k10)


@pytest.mark.integration
def test_nozzle_rate_limit_is_active(model, part):
    """Kills a removed or bypassed A8 slew limit: a step command from MIL A8 to 2 x MIL A8 makes the nozzle
    move at exactly the rate limit a8_rate during the slew (a 0.1 s first-order lag alone would be 5x
    faster at the start)."""
    n = 240
    a8_0 = part.u[U_A8]
    u, ui = input_block(n, 1, part.u, a8_cmd=np.r_[a8_0, np.full(n - 1, 2.0 * a8_0)])
    y = simulate(model, state_from_x(model, part.x), u, ui).y[:, 0, Y_NAMES.index("a8")]
    rate = np.diff(y) / model.dt
    lim = model.p[PI["a8_rate"]]
    assert rate.max() <= lim * (1.0 + 1e-9)
    assert np.sum(np.isclose(rate, lim, rtol=1e-6)) >= 10, (rate[:5], lim)
    unlimited = (2.0 * a8_0 - a8_0) / model.p[PI["tau_a8"]]
    assert unlimited > 3.0 * lim


@pytest.mark.integration
def test_volume_wiring(model, part):
    """Kills swapped volume constants (e.g. V45 used for V5): away from equilibrium, doubling V45 halves
    dP45/dt only and leaves dP5/dt and dP6/dt unchanged; doubling V5 halves dP5/dt only."""
    x = part.x.copy()
    x[X_P45] *= 1.01
    x[X_P5] *= 0.99
    x[X_P21] *= 1.005

    def dx_of(m):
        return deriv_point(x, 0, 1, 0, 0.0, part.u, m.p, m.tables, -1.0)[0]

    d0 = dx_of(model)
    for name, j in (("v45", X_P45), ("v5", X_P5), ("v6", X_P6), ("v21", X_P21)):
        d1 = dx_of(model.with_p(**{name: 2.0 * model.p[PI[name]]}))
        assert d1[j] == pytest.approx(0.5 * d0[j], rel=1e-12), name
        others = [k for k in (X_P21, X_P45, X_P5, X_P6) if k != j]
        assert np.array_equal(d1[others], d0[others]), name


@pytest.mark.integration
def test_stiffness_based_substep_count_is_active():
    """Kills a disabled stiffness-based sub-step count (mutant M20): with a small LPT-exit volume (V5 0.05
    m^3, the sweep end) at hot-day MIL the stiffest volume mode is about -2,800 1/s; the default numerics hold
    the equilibrium for 2 s (outputs within 1e-9), while n_sub 2 without the stiffness count leaves the
    explicit stability region and settles into a refinement-bounded numerical oscillation (> 1e-5)."""
    from phalanx.engine.layout import U_TS

    m = build_engine_model(load_engine_params().replace(v5=0.05))
    u = design_inputs(m)
    u[U_TS] = 318.15
    ss = steady_state(m, u)
    assert ss.converged
    dev = {}
    for lab, mm in (("default", m), ("stab_off", m.with_p(stab_hlam=1e9))):
        y = simulate(mm, state_from_x(mm, ss.x), *input_block(480, 1, ss.u)).y[:, 0, :]
        dev[lab] = float(np.max(np.abs(y - y[0]) / (np.abs(y[0]) + 1.0)))
    assert dev["default"] < 1e-9 and dev["stab_off"] > 1e-5, dev


@pytest.mark.unit
def test_refinement_error_covers_every_volume_pressure():
    """Kills a refinement error estimate that skips a pressure (P6 survived): a Heun-minus-Euler difference
    in any one of P21, P3, P45, P5, P6 registers; one in a non-pressure state (N1, N2, WFM) does not."""
    x = np.full(NX, 1000.0)
    hs = 1e-3
    for j in range(NX):
        dx = np.zeros(NX)
        dx2 = np.zeros(NX)
        dx2[j] = 100.0
        e = pressure_error(x, dx, dx2, hs)
        if X_P21 <= j <= X_P6:
            assert e == pytest.approx(0.5 * hs * 100.0 / 1000.0), j
        else:
            assert e == 0.0, j
    assert X_N1 < X_P21 and X_N2 < X_P21 and X_WFM > X_P6


@pytest.mark.integration
def test_lightoff_needs_ab_enable_and_draws_are_skipped_otherwise(model, part):
    """The module skips light-off draws in blocks without ab_enable; the kernel never starts an attempt
    without ab_enable even with AB fuel commanded (so the skipped draws are never read)."""
    n = 240
    u, ui = input_block(n, 1, part.u, wf_ab_cmd=0.5, a8_cmd=part.u[U_A8] * 1.5)
    z = np.full((1, n + 1), np.nan)  # any read of a draw would poison the run
    r = simulate(model, state_from_x(model, part.x), u, ui, z_ab=z)
    assert np.all(r.yi[:, 0, 0] == 0) and np.all(np.isfinite(r.y))
