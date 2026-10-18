"""M06 ground model (A-W1.2-10, -11, -13): static equilibrium on the gear, braking energy, the no-skid brake
PROXY, gear transit and the WoW retraction interlock, brake-chute drag.

Deterministic runs of the delivered kernel at 240 Hz (durations stated per test, n = 1 run each). For the
energy checks the atmosphere is a near-vacuum fixture and rolling friction is 0, so the brakes are the only
dissipation after the struts settle.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.airframe.analysis import (
    Condition,
    input_row,
    isa,
    make_ic,
    reference_mass_properties,
    trim,
)
from phalanx.airframe.build import airframe_param_set, build_config
from phalanx.airframe.geodesy import euler_to_quat, gravity_ecef
from phalanx.airframe.ic import initial_float_state
from phalanx.airframe.kernel import (
    D_A,
    D_GM,
    D_J2,
    D_OM,
    F_GEAR,
    F_RX,
    N_I,
    N_SURF,
    O_ALPHA,
    O_BETA,
    O_FX,
    O_HAG,
    O_NZ,
    O_PBL,
    O_QBAR,
    O_VN,
    O_WHL,
    O_WOW0,
    U_BRAKE,
    U_CHUTE,
    airframe_kernel,
    airframe_outputs,
)
from phalanx.core.time import TRUTH_DT_S

PS = airframe_param_set()
M, CG, J = reference_mass_properties(PS)
LAT, LON = math.radians(13.0), math.radians(77.6)
G0 = 9.80665


def _vacuum(h):
    return 1e-12, 340.0, 288.15, 101325.0


class Ground:
    """Kernel driver on a level runway at h_ground = 0 with a fixed input row."""

    def __init__(self, *, v=0.0, h=1.75, gear=1.0, gear_cmd=1, atmosphere=isa, **overrides):
        self.cfg = build_config(PS.replace(**overrides) if overrides else PS, 1)
        self.u = input_row(1, np.zeros(13), 0.0, M, CG, J, 0.0, atmosphere=atmosphere, gear_cmd=gear_cmd)
        q = np.asarray(euler_to_quat(0.0, 0.0, 0.0))
        self.f = initial_float_state(
            LAT, LON, h, np.array([v, 0.0, 0.0]), q, np.zeros(3), gear, 0.0, self.cfg.dp
        )
        self.i = np.zeros(N_I, dtype=np.int64)

    def run(self, n: int) -> np.ndarray:
        c = self.cfg
        u = np.tile(self.u, (n, 1))
        self.f, self.i, out = airframe_kernel(
            self.f, self.i, c.dp, c.ap, c.tab, c.gtab, c.ttab, u, TRUTH_DT_S, 1, 0
        )
        return out


@pytest.mark.integration
def test_static_equilibrium_on_the_gear():
    """At rest on the runway for 5 s: the struts settle (speed < 1 mm/s), all three WoW switches are made, the
    gear carries the weight: the specific force is the local effective gravity (J2 + centrifugal at 13 deg N,
    nz = |g_eff| / g0 = 0.9976, within 1e-5) and the CG height is below the uncompressed 1.85 m."""
    g = Ground()
    out = g.run(1200)
    end = out[-1]
    assert np.linalg.norm(end[O_VN : O_VN + 3]) < 1e-3
    assert np.all(end[O_WOW0 : O_WOW0 + 3] == 1.0)
    dp = g.cfg.dp
    gx, gy, gz = gravity_ecef(g.f[F_RX], g.f[F_RX + 1], g.f[F_RX + 2], dp[D_GM], dp[D_A], dp[D_J2], dp[D_OM])
    assert np.linalg.norm(end[O_FX : O_FX + 3]) == pytest.approx(
        math.sqrt(gx * gx + gy * gy + gz * gz), rel=1e-5
    )
    assert end[O_NZ] == pytest.approx(0.9976, abs=2e-4)
    assert 1.5 < end[O_HAG] < 1.85


def _braking_run():
    g = Ground(v=30.0, atmosphere=_vacuum, mu_roll=0.0)
    settle = g.run(240)  # 1 s rolling without brakes: struts settle, no dissipation left
    g.u[N_SURF + 1 + U_BRAKE : N_SURF + 1 + U_BRAKE + 2] = 1.0  # pilot.brake_cmd full (AD-47 input)
    out = g.run(1200)  # 5 s full brakes
    return settle, out, g


@pytest.mark.integration
def test_braking_energy_equals_kinetic_energy_loss():
    """Full braking from 30 m/s for 5 s with no aero and no rolling friction: the brake energy (integral of
    af.brake_energy_rate, both mains) equals the kinetic-energy loss within 1.5 % (strut and pitch
    transients take the rest)."""
    settle, out, _ = _braking_run()
    v0 = np.linalg.norm(settle[-1, O_VN : O_VN + 3])
    v1 = np.linalg.norm(out[-1, O_VN : O_VN + 3])
    d_ke = 0.5 * M * (v0 * v0 - v1 * v1)
    e_brake = float(np.sum(out[:, O_PBL : O_PBL + 2]) * TRUTH_DT_S)
    assert v1 < 0.7 * v0
    assert e_brake == pytest.approx(d_ke, rel=0.015)


@pytest.mark.integration
def test_no_skid_proxy_limits():
    """PROXY exposure (A-W1.2-10): the brake force is capped at mu_brake_max * N, so the deceleration never
    exceeds mu_max g (5 % allowance for strut load transients) and the wheels never lock: wheel speed x
    rolling radius tracks ground speed within 5 % throughout (a real anti-skid cycles the wheel slip; tyre
    skid wear cannot arise from this model)."""
    _, out, _g = _braking_run()
    mu_max = float(PS.value("mu_brake_max"))
    r = float(PS.value("r_roll"))
    decel = -out[:, O_FX] / G0
    assert decel.max() <= 1.05 * mu_max, decel.max()
    v = np.linalg.norm(out[:, O_VN : O_VN + 3], axis=1)
    mov = v > 2.0
    for side in range(2):
        assert np.all(np.abs(out[mov, O_WHL + side] * r - v[mov]) < 0.05 * v[mov])


@pytest.mark.integration
def test_gear_transit_and_interlock():
    """Gear extension takes 6 s (half-way at 3 s); airborne retraction runs back; with weight on wheels a
    retraction command is inhibited (A-W1.2-11)."""
    g = Ground(h=3000.0, gear=0.0, gear_cmd=1)
    g.run(720)
    assert g.f[F_GEAR] == pytest.approx(0.5, abs=1.0 / 1440)
    g.run(721)
    assert g.f[F_GEAR] == 1.0  # clipped at down-and-locked
    g.u = input_row(1, np.zeros(13), 0.0, M, CG, J, 0.0, gear_cmd=0)
    g.run(240)
    assert g.f[F_GEAR] == pytest.approx(1.0 - 1.0 / 6.0, abs=1.0 / 1440)
    gnd = Ground(gear_cmd=0)
    gnd.run(480)
    assert gnd.f[F_GEAR] == 1.0


@pytest.mark.integration
def test_chute_drag():
    """A deployed brake chute adds drag qbar x CdS along -v_air at the reference point (A-W1.2-13): the
    specific-force change equals -qbar CdS / m along the air-relative velocity (M0.25 / 1 km trim, one
    evaluation)."""
    cfg = build_config(PS, 1)
    cond = Condition(1000.0, 0.25, M, CG, J)
    tr = trim(cfg, cond, guess=(0.2, 0.0, 3e4))
    ic = make_ic(cfg, cond, tr, h_ground=0.0)
    f = initial_float_state(
        ic.lat, ic.lon, ic.h, np.asarray(ic.vel_ned), np.asarray(ic.quat_nb), np.zeros(3), 0.0, 0.0, cfg.dp
    )
    args = (cfg.dp, cfg.ap, cfg.tab, cfg.gtab, cfg.ttab, tr.u, 1, 0)
    o0 = airframe_outputs(f, *args)
    u1 = tr.u.copy()
    u1[N_SURF + 1 + U_CHUTE] = 1.0  # util.chute_state = 1, streamed (AD-47 input)
    o1 = airframe_outputs(f, cfg.dp, cfg.ap, cfg.tab, cfg.gtab, cfg.ttab, u1, 1, 0)
    a, b = o0[O_ALPHA], o0[O_BETA]
    unit = np.array([math.cos(a) * math.cos(b), math.sin(b), math.sin(a) * math.cos(b)])
    cds = float(PS.value("chute_cds"))
    expected = -o0[O_QBAR] * cds / M * unit
    assert np.allclose(o1[O_FX : O_FX + 3] - o0[O_FX : O_FX + 3], expected, rtol=1e-9, atol=1e-12)
    assert cds == pytest.approx(10.2)
