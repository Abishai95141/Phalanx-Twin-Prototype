"""A2: fuel, mass and energy balances on the integrated loop (invariant I7).

- **Fuel:** fuel burned = integral of (``eng.wf`` + ``eng.wf_ab``) = -delta sum ``util.fuel_mass``.
  M09 consumes the engine's metered flow of the same step (forward edge M07 -> M09), so the two agree to
  rounding: relative tolerance 1e-9 of the burn.
- **Mass:** delta ``util.mass`` = delta sum ``util.fuel_mass`` (no store release in these windows), tolerance
  1e-9 kg per kg burned.
- **Energy** (per unit mass, Earth-fixed frame): E = |v|^2 / 2 + g_eff h. With the specific force f (aero,
  thrust, ground, chute; ``af.f_spec_body`` rotated to NED by ``af.quat``) dE/dt = f . v (Coriolis does no
  work). g_eff is |f| at rest at the window start (static equilibrium: J2 + centrifugal, nz 0.9976 at 13 N).
  The trapezoid integral of f . v over the 240 Hz outputs must match delta E within 0.5 % of the integral of
  |f . v| (the outputs are end-of-step samples of an RK4 integration; the residual is the quadrature error and
  the latitude/altitude variation of g_eff, both small over a ground roll), plus an absolute floor of
  2e-4 J/kg for the parked window, whose throughput is only ~6e-3 J/kg (strut settling; measured mismatch
  7.7e-5 J/kg).

Sample (n = 1 plan, the first gate sortie): make check, 30 s at post-start idle (parked, brakes held); slow,
the run-up window (``start_phase="RUNUP"``): the run-up check against the brakes (~90 % N2, A-W2.1-8), the
line-up and the AB take-off roll, 80 s (60 s held the aircraft on the brakes for most of the window once the
run-up stopped creeping: too little energy throughput). A whole sortie is not yet possible (A6: the
aircraft does not complete a sortie; reported).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.integration.plans import gate_sorties
from phalanx.integration.system import SortieSpec, build_sortie_system

pytestmark = pytest.mark.integration
E_FLOOR = 2e-4  # J/kg, absolute floor of the energy balance (module docstring)
PORTS = [
    "eng.wf",
    "eng.wf_ab",
    "util.fuel_mass",
    "util.mass",
    "af.f_spec_body",
    "af.quat",
    "af.vel_ned",
    "af.alt",
]


def _run(seconds: float, **kw):
    ss = build_sortie_system(SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5, **kw))
    w0 = ss.system.inject(ss.start(), ss.bootstrap_events())
    _, tr = ss.system.run(w0, round(seconds * 240), record=PORTS)
    return w0, tr


def _rot(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Body -> NED rotation of v by the scalar-first unit quaternions q (row-wise)."""
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    r = np.empty((q.shape[0], 3, 3))
    r[:, 0, 0] = w * w + x * x - y * y - z * z
    r[:, 0, 1] = 2 * (x * y - w * z)
    r[:, 0, 2] = 2 * (x * z + w * y)
    r[:, 1, 0] = 2 * (x * y + w * z)
    r[:, 1, 1] = w * w - x * x + y * y - z * z
    r[:, 1, 2] = 2 * (y * z - w * x)
    r[:, 2, 0] = 2 * (x * z - w * y)
    r[:, 2, 1] = 2 * (y * z + w * x)
    r[:, 2, 2] = w * w - x * x - y * y + z * z
    return np.einsum("nij,nj->ni", r, v)


def _balances(w0, tr):
    P = tr.ports
    dt = 1.0 / 240.0
    burn = float(np.sum(P["eng.wf"] + P["eng.wf_ab"]) * dt)
    fuel0 = float(np.sum(w0.held["util.fuel_mass"]))
    fuel = np.sum(P["util.fuel_mass"], axis=1)
    dfuel = fuel0 - float(fuel[-1])
    dmass = float(w0.held["util.mass"]) - float(P["util.mass"][-1])
    v = np.vstack([np.asarray(w0.held["af.vel_ned"])[None], P["af.vel_ned"]])
    h = np.concatenate([[float(w0.held["af.alt"])], P["af.alt"]])
    q = np.vstack([np.asarray(w0.held["af.quat"])[None], P["af.quat"]])
    fb = np.vstack([np.asarray(w0.held["af.f_spec_body"])[None], P["af.f_spec_body"]])
    f = _rot(q, fb)
    g_eff = float(np.linalg.norm(w0.held["af.f_spec_body"]))
    e = 0.5 * np.sum(v * v, axis=1) + g_eff * h
    p = np.sum(f * v, axis=1)
    work = float(np.sum(0.5 * (p[1:] + p[:-1])) * dt)
    gross = float(np.sum(0.5 * (np.abs(p[1:]) + np.abs(p[:-1]))) * dt)
    return burn, dfuel, dmass, float(e[-1] - e[0]), work, gross


def test_fuel_mass_energy_balances_at_idle():
    w0, tr = _run(30.0)
    burn, dfuel, dmass, de, work, gross = _balances(w0, tr)
    assert burn > 1.0  # ~0.07 kg/s at ground idle
    assert abs(burn - dfuel) <= 1e-9 * burn, (burn, dfuel)
    assert abs(dmass - dfuel) <= 1e-9 * max(dfuel, 1.0), (dmass, dfuel)
    assert abs(de - work) <= 0.005 * gross + E_FLOOR, (de, work, gross)


@pytest.mark.slow
def test_fuel_mass_energy_balances_through_runup_and_takeoff_roll():
    w0, tr = _run(80.0, start_phase="RUNUP")
    burn, dfuel, dmass, de, work, gross = _balances(w0, tr)
    print(
        f"burn {burn:.3f} kg, dfuel {dfuel:.3f} kg, dE {de:.1f} J/kg, work {work:.1f} J/kg, "
        f"|work| {gross:.1f}"
    )
    assert burn > 20.0
    assert abs(burn - dfuel) <= 1e-9 * burn
    assert abs(dmass - dfuel) <= 1e-9 * dfuel
    assert de > 1000.0  # the roll gained kinetic energy
    assert abs(de - work) <= 0.005 * gross + E_FLOOR
