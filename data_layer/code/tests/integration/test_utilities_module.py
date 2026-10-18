"""M09 inside the kernel (§5.5 / AD-36): System runs in step and block mode bitwise, validation mode (purity,
schemas, finiteness) equals production, the compiled module equals the reference module through the scheduler,
events through System.inject, and A1 balances over a minimal scripted sortie.

Samples: 2,400 ticks (10 s) for the System equivalences; a 10-minute scripted sortie for A1 (stated below).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_utilities_support import DT, G0, inputs, module, run, utility_system

from phalanx.core.events import Event
from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L
from phalanx.utilities.hydraulics import hyd_volume_invariant
from phalanx.utilities.landing import heat_capacity

N = 2400


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("block_len", [1, 7, 1024])
def test_step_block_and_reference_agree_bitwise_through_the_scheduler(block_len):
    ref = utility_system(compiled=False)
    _, t_ref = ref.run(ref.start(), N, mode="step", record=ref.output_ports())
    s = utility_system(compiled=True, block_len=block_len)
    _, t = s.run(s.start(), N, mode="block", record=s.output_ports())
    assert t.digest() == t_ref.digest()
    seg = next(sg for sg in s.execution()["segments"] if "util" in sg["members"])
    assert seg["module_step_block"]


@pytest.mark.integration
def test_validation_mode_equals_production():
    """Validation mode passes read-only state/inputs, checks schemas, port dtypes/shapes/units and finiteness,
    and calls every step twice (purity). n = 480 ticks."""
    a = utility_system(validate=True)
    _, ta = a.run(a.start(), 480, mode="block", record=a.output_ports())
    b = utility_system()
    _, tb = b.run(b.start(), 480, mode="block", record=b.output_ports())
    assert ta.digest() == tb.digest()


@pytest.mark.integration
def test_events_through_inject_reach_the_module():
    s = utility_system()
    w = s.start()
    t_ev = 240 * 1_000_000_000 // 240  # 1 s
    w = s.inject(w, [Event(t_ev, "util.fault", "util", {"mode": "gen_fail"})])
    w, tr = s.run(w, 480, record=["util.gen_online"])
    g = tr.ports["util.gen_online"]
    assert g[200] == 1 and g[-1] == 0
    assert [e.kind for _, e in tr.dispatched] == ["util.fault"]


def _sortie_inputs():
    """TEST FIXTURE minimal sortie (10.5 min): 60 s taxi with brake snubs, 30 s take-off roll at max AB, 2 min
    climb, 4 min cruise with an FCS-activity burst, 2 min descent, 30 s landing roll with braking, 30 s
    taxi."""
    segs = []

    def seg(seconds, **kw):
        segs.append(inputs(int(seconds * 240), **kw))

    snub = np.where((np.arange(60 * 240) // 240) % 15 < 2, 3.0e4, 0.0)
    seg(
        60,
        n2f=0.68,
        p3=2.2e5,
        t3=420.0,
        wf=0.09,
        wow=(1, 1, 1),
        tas=8.0,
        alt=0.0,
        pbrk=np.stack([snub, snub], 1),
        wheel=(28.0, 28.0),
    )
    seg(
        30,
        n2f=1.0,
        p3=6.4e5,
        t3=713.0,
        wf=0.0,
        wf_ab=4.3,
        wow=(1, 1, 1),
        tas=np.linspace(0, 85, 30 * 240),
        alt=0.0,
        fspec=(0.9 * G0, 0.0, -G0),
        wheel=(250.0, 250.0),
    )
    seg(120, n2f=0.97, p3=6.4e5, t3=713.0, wf=1.0, tas=200.0, alt=3000.0, fspec=(0.5 * G0, 0.0, -0.9 * G0))
    k = np.arange(240 * 240)
    seg(240, n2f=0.9, p3=5.0e5, t3=600.0, wf=0.5, tas=220.0, alt=8000.0, demand=6e-4 * ((k // 240) % 20 == 0))
    seg(120, n2f=0.75, p3=2.8e5, t3=448.0, wf=0.2, tas=180.0, alt=3000.0, fspec=(-0.1 * G0, 0.0, -G0))
    v = np.linspace(75, 10, 30 * 240)
    pb = 0.5 * 0.4 * 8500.0 * 2.2 * v
    seg(
        30,
        n2f=0.68,
        p3=2.2e5,
        t3=420.0,
        wf=0.09,
        wow=(1, 1, 1),
        tas=v,
        alt=0.0,
        pbrk=np.stack([pb, pb], 1),
        wheel=np.stack([v / 0.284, v / 0.284], 1),
    )
    seg(30, n2f=0.68, p3=2.2e5, t3=420.0, wf=0.09, wow=(1, 1, 1), tas=8.0, alt=0.0, wheel=(28.0, 28.0))
    return {key: np.concatenate([s[key] for s in segs]) for key in segs[0]}


@pytest.mark.integration
def test_a1_balances_close_over_a_minimal_sortie():
    """A1: over a 10.5-minute scripted sortie (151,200 ticks)
    - fuel mass: initial - final = burned (exact to 1e-9 kg); burned = integral of wf + wf_ab (1e-9 relative);
    - hydraulic fluid volume invariant within 5 mL per system (explicit-Euler compliance error);
    - hydraulic heat: C_th dT = heat in - heat out (bookkeeping, 1e-9 relative);
    - brake energy: integral of af.brake_energy_rate = heat-sink energy + cooling (1e-9 relative);
    - battery charge: SOC change x capacity = integrated current (1e-6, SOC rounding);
    - ECS: bleed extracted = air delivered to subscribers = integral of util.bleed_extract (1e-9 relative)."""
    ps = load_m09_params()
    inp = _sortie_inputs()
    assert inp["tas"].shape[0] == 630 * 240
    m, st0 = module(UtilitiesConfig(soak_temp=303.15, batt_soc=0.8, drop_tanks=(True, True, False)))
    tv0 = m.truth_view(st0, p_amb=101325.0)
    st, out = run(m, st0, inp)
    f0, f = st0["f"], st["f"]
    # fuel
    burned = float(f[L.F_FUEL_BURN])
    assert float(f[L.F_FUEL_UNMET]) == 0.0
    assert burned == pytest.approx(float(np.sum(inp["wf"] + inp["wf_ab"]) * DT), rel=1e-9)
    assert float(
        np.sum(f0[L.F_FUEL_M : L.F_FUEL_M + 8]) - np.sum(f[L.F_FUEL_M : L.F_FUEL_M + 8])
    ) == pytest.approx(burned, abs=1e-9)
    # hydraulic fluid (both systems), with the ambient pressure of the final tick
    for h in range(2):
        inv = float(hyd_volume_invariant(f, m._p, h, float(inp["p_s"][-1]), 0.0, 0.0))
        inv0 = float(hyd_volume_invariant(f0, m._p, h, float(inp["p_s"][-1]), 0.0, 0.0))
        # the invariant uses the final-tick ambient pressure for both ends; accumulator gas sits at bay
        # pressure
        assert abs(inv - inv0) < 5e-6, h
        c_th = ps.value("hyd_v_total") * ps.value("hyd_rho") * ps.value("hyd_cp") + ps.value("hyd_c_metal")
        de = c_th * (float(f[L.F_HYD_T + h]) - float(f0[L.F_HYD_T + h]))
        assert de == pytest.approx(float(f[L.F_HYD_EIN + h] - f[L.F_HYD_EOUT + h]), rel=1e-9)
    assert tv0["hyd_level"][0] > 0
    # brakes
    for w in range(2):
        e_in = float(np.sum(inp["brake_energy_rate"][:, w]) * DT)
        assert float(f[L.F_BRK_EIN + w]) == pytest.approx(e_in, rel=1e-9)
        c = float(heat_capacity(m._p, 0.0))
        assert e_in == pytest.approx(
            c * (float(f[L.F_BRK_T + w]) - 303.15) + float(f[L.F_BRK_EOUT + w]), rel=1e-9
        )
    # battery
    cap = ps.value("batt_cap_ah")  # coulombs (SI)
    assert (0.8 - float(f[L.F_BATT_SOC])) * cap == pytest.approx(float(f[L.F_BATT_Q]), rel=1e-6, abs=1e-6)
    # ECS mass
    assert float(f[L.F_ECS_MBLEED]) == pytest.approx(float(f[L.F_ECS_MSUP]), rel=1e-12)
    assert float(f[L.F_ECS_MBLEED]) == pytest.approx(float(np.sum(out["bleed_extract"]) * DT), rel=1e-9)
    # sanity of the sortie: landed once, applications counted, everything finite
    assert m.truth_view(st)["landings"] == 1
    for v in out.values():
        assert np.all(np.isfinite(v))
