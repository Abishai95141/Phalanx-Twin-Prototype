"""M05 carefree limiting on the negative side (W2.1a-2; A-W2.1-13) and the actuator flow fix behind the
full-aircraft departure.

Clean harness (M05 + M06 through the TEST FIXTURE harness, n = 1 trajectory per condition, 6 s): full forward
stick from trim at M0.3/3 km, M0.4/6 km, M0.6/5 km, M0.85/2 km (the most unstable corner) and M1.2/10 km:
- nz stays above -3.5 g minus a 0.5 g overshoot allowance and alpha above ``alpha_min`` (-10 deg): no
  departure;
- negative control: with the negative-AoA limiter removed (``alpha_min`` -86 deg), full forward stick at the
  two low-speed conditions pushes alpha past -30 deg (a departure into negative stall): the limiter is what
  holds the aircraft there.

Full aircraft (the integrated System: sensors, M13 lanes, DFCC, actuators on the M09 hydraulic supply, M06
with the TJ212 store loading; n = 1 world at 1,400 s of the first diverse gate sortie, cruise at M0.80 / 3.2
km): a scripted test pilot (TEST FIXTURE: the M04 stick outputs overridden at the module boundary of an
unfused System started from the fused run's world) pushes full forward stick (a) wings level and (b) in a
71 deg bank after a 2.7 g pull while rolling out. nz stays above -4 g, alpha above -10 deg, both hydraulic
systems above 200 bar. Before the actuator flow fix (crank arm missing in the demand, ~8x) both systems fell
to ~30 bar and the aircraft departed to -16.7 g.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from test_fcs_fixtures import Harness, nz_of

from phalanx.airframe.kernel import O_ALPHA
from phalanx.core.time import truth_step_times_ns
from phalanx.integration.flights import diverse_sorties
from phalanx.integration.sortie import SortieRunner
from phalanx.integration.system import SortieSpec, build_sortie_system

pytestmark = pytest.mark.integration
DEG = math.pi / 180.0
NZ_MIN = -3.5
ALPHA_MIN = -10.0
CONDITIONS = [(0.3, 3000.0), (0.4, 6000.0), (0.6, 5000.0), (0.85, 2000.0), (1.2, 10000.0)]


def _push(mach, alt, overrides=None):
    h = Harness(
        mach, alt, fcs_overrides=overrides or {}, stick=lambda t: (-1.0 if t > 0.5 else 0.0, 0.0, 0.0)
    )
    _of, oa = h.run(6.0)
    return oa[:, O_ALPHA] / DEG, nz_of(oa)


@pytest.mark.parametrize("mach, alt", CONDITIONS)
def test_full_forward_stick_is_carefree_on_the_harness(mach, alt):
    a, nz = _push(mach, alt)
    assert nz.min() >= NZ_MIN - 0.5, nz.min()
    assert a.min() >= ALPHA_MIN, a.min()


@pytest.mark.parametrize("mach, alt", CONDITIONS[:2])
def test_without_the_negative_aoa_limiter_the_push_departs(mach, alt):
    a, _nz = _push(mach, alt, {"alpha_min": -1.5})  # rad: no limit
    assert a.min() < -30.0, a.min()


@pytest.fixture(scope="module")
def cruise_world():
    plan = diverse_sorties(5)[0]
    spec = dict(plan=plan, scenario="gate", root=0xA5)
    ss = build_sortie_system(SortieSpec(**spec))
    r = SortieRunner(ss, check_invariants=False)
    st = r.begin()
    k0 = 1400 * 240
    while st.world.k < k0:
        st, _ = r.run(st, min(2400, k0 - st.world.k))
    return spec, st.world


def _scripted_push(spec, world, banked: bool):
    ss = build_sortie_system(SortieSpec(**spec, fused=False))
    pil = ss.modules["pilot"]
    real = pil.step_block
    t0 = int(truth_step_times_ns(np.array([world.k]))[0])

    def stick(s):
        if not banked:
            return (-1.0, 0.0) if 1.0 <= s < 4.0 else (0.0, 0.0)
        if s < 1.2:
            return 0.1, 0.3  # roll in
        if s < 4.5:
            return 0.25, 0.0  # ~2.7 g
        return (-1.0, -0.2) if s < 7.5 else (0.0, 0.0)  # full push while rolling out

    def scripted(state, inputs, t, dt):  # TEST FIXTURE: the pilot's stick outputs replaced by the script
        res = real(state, inputs, t, dt)
        out = dict(res[1])
        t = np.asarray(t, dtype=np.int64)
        sp = np.array(out["stick_pitch"], dtype=np.float64, copy=True).reshape(-1)
        sr = np.array(out["stick_roll"], dtype=np.float64, copy=True).reshape(-1)
        for j in range(t.size):
            sp[j], sr[j] = stick((int(t[j]) - t0) / 1e9)
        out["stick_pitch"] = sp.reshape(np.shape(res[1]["stick_pitch"]))
        out["stick_roll"] = sr.reshape(np.shape(res[1]["stick_roll"]))
        return (res[0], out, *res[2:])

    pil.step_block = scripted
    _w, tr = ss.system.run(world, 9 * 240, record=["af.alpha", "af.nz", "util.hyd_p"])
    return np.degrees(tr.ports["af.alpha"]), tr.ports["af.nz"], tr.ports["util.hyd_p"]


@pytest.mark.parametrize("banked", [False, True])
def test_full_forward_stick_in_the_full_aircraft_with_stores(cruise_world, banked):
    spec, world = cruise_world
    a, nz, hyd = _scripted_push(spec, world, banked)
    hyd_bar = hyd.min() / 1e5
    print(f"banked={banked}: alpha min {a.min():.1f} deg, nz min {nz.min():.2f} g, hyd min {hyd_bar:.0f} bar")
    assert nz.min() >= -4.0, nz.min()
    assert a.min() >= ALPHA_MIN, a.min()
    assert hyd.min() > 200e5, hyd.min() / 1e5
