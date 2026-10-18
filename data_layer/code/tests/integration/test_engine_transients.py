"""M07 transient structure (acceptance A5): slams, accel/decel asymmetry, fan-spool step, AB light-off, surge,
flame-out and relight.

The slams run in closed loop with the labelled TEST FIXTURE governor (``test_engine_fixtures.py``; the real
FADEC is W1.3b) using *symmetric* Wf/PS3 limits (accel 1.5 x, decel 1/1.5 x the steady ratio), so any
accel/decel asymmetry comes from the plant, not from the fixture. Samples: one slam pair (30 s); one open-loop
step; n = 40 keyed light-off draws (enough for a 0.75 coverage check with a +-0.07 binomial standard error);
single surge and flame-out scenarios.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.engine.layout import I_NSURGE, U_A8, U_MACH, U_PS, U_TS, U_WF, Y_NAMES, A
from phalanx.engine.module import STREAM_AB
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state


def _fixtures():
    path = Path(__file__).with_name("test_engine_fixtures.py")
    spec = importlib.util.spec_from_file_location("engine_fixtures_t", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["engine_fixtures_t"] = mod
    spec.loader.exec_module(mod)
    return mod


fx = _fixtures()
Y = fx.Y


@pytest.fixture(scope="module")
def sch():
    return fx.FixtureSchedules(fx.fixture_model())


def _rise(y: np.ndarray, lo: float, hi: float) -> tuple[float, float]:
    frac = (y - y[0]) / (y[-1] - y[0])
    a = int(np.argmax(frac >= lo))
    b = int(np.argmax(frac >= hi))
    return (b - a) / 240.0, b / 240.0


@pytest.fixture(scope="module")
def slam(sch):
    gov = fx.GovernorFixture(kp=2.0, ki=1.0, ru_acc=1.5, ru_dec=1.0 / 1.5)
    n = 240 * 30
    dem = np.full(n, 0.72)
    dem[240 : 240 * 16] = 1.0
    return fx.run_closed_loop(sch, gov, dem, n)


@pytest.mark.integration
def test_slam_time_scale_vs_tm4240(slam):
    """A5/C16: idle (72 % N2) -> MIL slam, N1 reaches 95 % of its rise in 3.5 s +-25 % (TM-4240 simple
    model: idle->MIL about 2.9 s rate-limited command + 0.6 s lag [TRANSFER: F404-400]); order of magnitude
    1-10 s required. Fixture accel schedule: W2.1/W2.3 recheck with the M08 accel schedule."""
    n1 = slam.y[240 : 240 * 16, 0, Y["n1"]]
    _, t95 = _rise(n1, 0.0, 0.95)
    assert 1.0 < t95 < 10.0
    assert 3.5 * 0.75 <= t95 <= 3.5 * 1.25, t95
    assert slam.y[:, 0, Y["stall_margin"]].min() > 0.0 and slam.state.i[0, I_NSURGE] == 0


@pytest.mark.integration
def test_decel_slower_than_accel(slam):
    """Behavioural structure (docs/behavioural_targets.md B3 ii: real N1 accel/decel 1.03/3.06 s): with
    symmetric fuel limits the plant decelerates the fan more slowly than it accelerates it (10-90 % times)."""
    n1 = slam.y[:, 0, Y["n1"]]
    up, _ = _rise(n1[240 : 240 * 16], 0.1, 0.9)
    dn, _ = _rise(-n1[240 * 16 :], 0.1, 0.9)
    assert dn > 1.3 * up, (up, dn)


@pytest.mark.integration
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 calibration: fan-spool small-step tau 0.47 s (this test's operating point, 92 % of MIL N2 "
    "on the fixture A8 schedule) vs 0.77 s +-25 % (C18); I_LP / LP spool dynamics are an A-W1.3a-7 "
    "assumption to be identified on transients (AD-34); C18 and C22 pull I_LP in opposite directions",
)
def test_fan_spool_small_step_time_constant(sch):
    """C18: open-loop 5 % fuel step near 90 % N1 (A8 fixed): N1 63 % time 0.77 s +-25 % (Merrington,
    AGARD-CP-448 paper 36 [TRANSFER: F404-400 test cell])."""
    m = sch.model
    u = design_inputs(m)
    u[U_A8] = sch.a8(0.92)
    ss = steady_state(m, u, x0=sch.x_at(0.92), target=("n2", 0.92 * sch.n2_des))
    uu, ui = input_block(240 * 8, 1, ss.u)
    uu[24:, :, U_WF] *= 1.05
    y = simulate(m, state_from_x(m, ss.x), uu, ui).y[24:, 0, Y["n1"]]
    tau = int(np.argmax((y - y[0]) / (y[-1] - y[0]) >= 0.632)) / 240.0
    assert 0.77 * 0.75 <= tau <= 0.77 * 1.25, tau


@pytest.fixture(scope="module")
def altitude_mil(sch):
    m = sch.model
    u = design_inputs(m)
    u[U_TS], u[U_PS], u[U_MACH] = 238.62, 37600.0, 0.6  # 25 kft ISA, M0.6
    ss = steady_state(m, u, target=("n1", m.design.stations["n1"]))
    assert ss.converged
    return ss


def _ab_run(m, ss, z: float, n: int = 240 * 8, off_at: int | None = None):
    en = np.zeros(n, np.int64)
    en[24:] = 1
    if off_at is not None:
        en[off_at:] = 0
    wfab = np.where(en == 1, 1.0, 0.0)
    # nozzle pre-opened with the AB request, as the FADEC does (max-AB/MIL area ratio of the design point)
    a8r = m.design.max_ab["a8"] / m.design.stations["a8"]
    a8 = np.where(en == 1, ss.u[U_A8] * a8r, ss.u[U_A8])
    u, ui = input_block(n, 1, ss.u, ab_enable=en, wf_ab_cmd=wfab, a8_cmd=a8)
    return simulate(m, state_from_x(m, ss.x), u, ui, z_ab=np.full((1, n + 1), z))


@pytest.mark.integration
def test_ab_lightoff_timing_band(sch, altitude_mil):
    """A5/C19: MIL -> max AB light-off at 25 kft M0.6 with n = 40 keyed draws (engine.ab_lightoff stream):
    at least 75 % within 0.7-2.7 s and the median within 1.0-2.0 s (F404-402 NAWCADPAX/RTR-2001/1: mostly
    0.7-2.7 s, slow lights > 6 s at high altitude/cold T1)."""
    rng = RngService(0xAB, StreamRegistry([STREAM_AB]))
    keys = rng.scope(KeyPath.of(scenario="w13a_a5", tail="T1", sortie=1))
    z = keys.stream("engine", "ab_lightoff", serial="E1").draws(0, 40)
    delays = []
    for zz in z:
        r = _ab_run(sch.model, altitude_mil, float(zz))
        delays.append((int(np.argmax(r.yi[:, 0, 0] == 2)) - 24) / 240.0)
    d = np.array(delays)
    assert np.mean((d >= 0.7) & (d <= 2.7)) >= 0.75, d
    assert 1.0 <= float(np.median(d)) <= 2.0


@pytest.mark.integration
def test_ab_state_machine_and_heat_release(sch, altitude_mil):
    """off -> lighting (pilot fuel, no heat, nozzle pre-opening) -> lit (thrust rises) -> off when enable
    drops; no stall through the light-off."""
    m = sch.model
    r = _ab_run(m, altitude_mil, 0.0, off_at=240 * 6)
    ab = r.yi[:, 0, 0]
    k_lit = int(np.argmax(ab == 2))
    assert ab[0] == 0 and ab[30] == 1 and k_lit > 30 and ab[-1] == 0
    fn = r.y[:, 0, Y["thrust"]]
    assert abs(fn[k_lit - 1] - fn[0]) < 0.05 * fn[0]  # unlit AB fuel adds no heat (nozzle opening: small)
    assert fn[k_lit + 240] > 1.2 * fn[0]  # lit: AB thrust
    assert r.state.i[0, I_NSURGE] == 0
    assert r.y[30, 0, Y["wf_ab"]] > 0.0  # fuel flows while lighting


@pytest.fixture(scope="module")
def part_power(sch):
    m = sch.model
    u = design_inputs(m)
    u[U_WF] *= 0.9
    ss = steady_state(m, u)
    assert ss.converged
    return ss


def _blockage(m, ss, mag: float, n: int = 240 * 3, dur: int = 96):
    h = np.zeros((n, 1, 10))
    h[24 : 24 + dur, 0, 5] = mag  # HPT flow-capacity blockage (fault perturbation)
    return simulate(m, state_from_x(m, ss.x), *input_block(n, 1, ss.u, health=h), record_aux=True)


@pytest.mark.integration
def test_surge_triggers_on_margin_loss_and_recovers(sch, part_power):
    """A5: a transient HPT flow blockage (-15 % for 0.4 s) drives the HPC margin below zero -> surge events;
    compressor discharge pressure collapses (below 40 % of the pre-surge value within 0.1 s) and the engine
    returns to its pre-fault state once the blockage clears (P3 within 2 % after 2.5 s), flame kept."""
    r = _blockage(sch.model, part_power, -0.15)
    p3 = r.y[:, 0, Y["bleed_p3"]]
    sm = r.aux[:, 0, A["sm_hpc"]]
    k0 = int(np.argmax(sm < 0.0))
    assert r.state.i[0, I_NSURGE] >= 1 and k0 > 24
    assert p3[k0 : k0 + 24].min() < 0.4 * p3[k0 - 1]
    assert abs(p3[-1] / p3[0] - 1.0) < 0.02
    assert r.yi[:, 0, 1].min() == 1 and np.all(np.isfinite(r.y))


@pytest.mark.integration
def test_no_surge_without_margin_loss(sch, part_power):
    """Negative control: a small blockage (-3 %) and +-5 % fuel steps keep the margin positive: no surge."""
    r = _blockage(sch.model, part_power, -0.03)
    assert r.state.i[0, I_NSURGE] == 0 and r.aux[:, 0, A["sm_hpc"]].min() > 0.0
    for k in (0.95, 1.05):
        u, ui = input_block(240 * 3, 1, part_power.u)
        u[24:, :, U_WF] *= k
        rr = simulate(sch.model, state_from_x(sch.model, part_power.x), u, ui)
        assert rr.state.i[0, I_NSURGE] == 0


@pytest.mark.integration
def test_lean_blowout_and_relight(sch, part_power):
    """Fuel cut -> lean blow-out (flame 0) after the persistence time; spool-down; fuel back with igniters on
    at mid speed -> relight after the ignition delay and recovery of N2."""
    m = sch.model
    n = 240 * 12
    wf = np.full(n, part_power.u[U_WF])
    wf[24 : 240 * 3] = 0.0
    ign = np.zeros(n, np.int64)
    ign[240 * 3 :] = 1
    u, ui = input_block(n, 1, part_power.u, wf_cmd=wf, ignition=ign)
    r = simulate(m, state_from_x(m, part_power.x), u, ui)
    flame = r.yi[:, 0, 1]
    k_out = int(np.argmax(flame == 0))
    assert 24 < k_out < 24 + 120  # within 0.5 s of the cut (FMV lag + transport delay + persistence)
    k_back = k_out + int(np.argmax(flame[k_out:] == 1))
    assert k_back > 240 * 3
    n2 = r.y[:, 0, Y["n2"]]
    assert n2[240 * 3] < 0.95 * n2[0]  # spooled down while unlit
    assert n2[-1] > 0.97 * n2[0]  # relit and recovered
    assert np.all(np.isfinite(r.y))


@pytest.mark.integration
def test_slam_outputs_never_nan_under_abuse(sch, part_power):
    """Robustness (I3 'no NaN at a port'): an unscheduled fuel dump (x3), nozzle slam to its limits and a
    25 deg VG mis-rig for 2 s give finite outputs (clamps and guards; the physics may stall or flame out)."""
    m = sch.model
    n = 480
    u, ui = input_block(n, 1, part_power.u)
    u[24:, :, U_WF] *= 3.0
    u[100:, :, U_A8] = 10.0
    u[200:, :, 4] += np.radians(25.0)
    r = simulate(m, state_from_x(m, part_power.x), u, ui, record_aux=True)
    assert np.all(np.isfinite(r.y)) and np.all(np.isfinite(r.state.f))
    assert Y_NAMES.index("n1") == 0
