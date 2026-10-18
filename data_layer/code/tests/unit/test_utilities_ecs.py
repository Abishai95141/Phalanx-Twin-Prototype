"""M09 ECS: bleed extraction vs bleed pressure (HAL fighter range), PHX rating anchor, cabin pressure
schedule, cockpit temperature control, and the exposing test of the single-expansion ACM PROXY (A-W1.4-24).

Samples: 3-300 s per case (stated per test).
"""

from __future__ import annotations

import numpy as np
import pytest
from test_utilities_support import inputs, isa, module, run

from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L

PS = load_m09_params()
PSI = 6894.757


def _hal_bleed(n2f: float) -> tuple[float, float]:
    """HAL fighter ECS (Heliyon 2022, TRANSFER): 75 -> 97 % rpm gives 2.8 -> 6.4 bar and 175 -> 440 degC
    (linear interpolation used as the TEST FIXTURE stand-in for M07's eng.bleed_p3/t3)."""
    x = np.clip((n2f - 0.75) / 0.22, 0.0, 1.0)
    return 2.8e5 + x * 3.6e5, 448.15 + x * 265.0


@pytest.mark.unit
def test_bleed_flow_follows_pressure_then_saturates():
    """At 75 % rpm (2.8 bar) the venturi limits the extraction below the set flow; from ~80 % the flow-control
    valve holds the set flow; extraction never exceeds set + aux and stays within the F404 customer-bleed
    range 0.7-4.2 lb/s (0.32-1.9 kg/s, TM-104247, TRANSFER). n = 3 s per point."""
    flows = []
    for n2f in (0.75, 0.80, 0.90, 0.97):
        p3, t3 = _hal_bleed(n2f)
        m, st = module(UtilitiesConfig())
        st, out = run(m, st, inputs(3 * 240, n2f=n2f, p3=p3, t3=t3, alt=3000.0))
        flows.append(float(out["bleed_extract"][-1, 0]))
        assert out["ecs_p"][-1, L.E_BLEED] == pytest.approx(p3)
        assert out["ecs_t"][-1, L.E_BLEED] == pytest.approx(t3)
    m_set, aux = PS.value("ecs_m_set"), PS.value("ecs_m_aux")
    assert flows[0] < m_set + aux - 0.02
    assert flows[1] < flows[2] or flows[1] == pytest.approx(flows[2])
    assert flows[2] == pytest.approx(m_set + aux) and flows[3] == pytest.approx(m_set + aux)
    assert all(0.32 <= q <= 1.9 for q in flows)


@pytest.mark.unit
def test_bleed_flow_responds_to_the_process_disturbance():
    p3, t3 = _hal_bleed(0.95)
    m, st = module(UtilitiesConfig())
    base = run(m, st, inputs(240, p3=p3, t3=t3))[1]["bleed_extract"][-1, 0]
    up = run(m, st, inputs(240, p3=p3, t3=t3, w_bp=0.05))[1]["bleed_extract"][-1, 0]
    assert up == pytest.approx(base + 0.05 * PS.value("ecs_m_set"))


@pytest.mark.unit
def test_phx_meets_the_hal_rating_point():
    """HAL primary heat exchanger [DIRECT-part]: hot side 0.575 kg/s, inlet <= 578 degC, outlet < 170 degC.
    With the rated hot flow and a 578 degC inlet at M0.8 sea level (ISA) the PHX outlet is below 170 degC; at
    the same condition 90 % fouling raises it (fouling edge). n = 30 s (duct lag settled)."""
    ps = PS.replace(ecs_m_set=0.575)
    outs = []
    for foul in (0.0, 0.9):
        h = np.zeros(L.N_HEALTH)
        h[L.H_HX_FOUL] = foul
        m, st = module(UtilitiesConfig(), ps)
        st, out = run(m, st, inputs(30 * 240, p3=1.2e6, t3=851.15, alt=0.0, tas=272.0, mach=0.8, health=h))
        outs.append(float(out["ecs_t"][-1, L.E_PHX]))
    assert outs[0] < 443.15
    assert outs[1] > outs[0] + 10.0


@pytest.mark.unit
def test_cabin_pressure_schedule():
    """Fighter schedule (Webb & Pilmanis; MIL-E-18927E, TRANSFER): unpressurised below 8,000 ft, isobaric
    75.26 kPa cabin up to the 5 psi differential, then 5 psi above ambient; rate <= 0.2 psi/s. n = 60 s per
    alt."""
    for alt in (1000.0, 4500.0, 12000.0):
        _, p_amb, _ = isa(alt)
        m, st = module(UtilitiesConfig(p_amb=p_amb))
        p3, t3 = _hal_bleed(0.95)
        st, out = run(m, st, inputs(60 * 240, p3=max(p3, p_amb * 3), t3=t3, alt=alt))
        pc = out["ecs_p"][:, L.E_CAB]
        iso, dp_max = PS.value("ecs_p_cab_iso"), PS.value("ecs_dp_max")
        target = p_amb if p_amb >= iso else min(iso, p_amb + dp_max)
        assert iso == pytest.approx(75.26e3) and dp_max == pytest.approx(5 * PSI, rel=1e-6)
        assert pc[-1] == pytest.approx(target, rel=2e-3), alt
        assert np.max(np.abs(np.diff(pc))) * 240 <= PS.value("ecs_dpdt_max") * (1 + 1e-9)


@pytest.mark.unit
def test_canopy_leak_limits_cabin_differential():
    """A large canopy-seal leak (health) lets the cabin pressure sag below schedule at altitude
    (NM.ECS.CANOPY_SEAL)."""
    _, p_amb, _ = isa(12000.0)
    p3, t3 = _hal_bleed(0.95)
    vals = []
    for leak in (0.0, 3.0):
        h = np.zeros(L.N_HEALTH)
        h[L.H_CAB_LEAK] = leak
        m, st = module(UtilitiesConfig(p_amb=p_amb))
        st, out = run(m, st, inputs(60 * 240, p3=p3, t3=t3, alt=12000.0, health=h))
        vals.append(float(out["ecs_p"][-1, L.E_CAB]))
    assert vals[1] < vals[0] - 1000.0


@pytest.mark.unit
def test_tcv_drives_cockpit_toward_set_point():
    """The integrating TCV moves the cockpit toward 22 degC from a hot soak (Jaisalmer-like 315 K) in cruise;
    the valve is rate limited to its 8 s full stroke. n = 600 s."""
    p3, t3 = _hal_bleed(0.9)
    m, st = module(UtilitiesConfig(soak_temp=315.15))
    st, out = run(m, st, inputs(600 * 240, p3=p3, t3=t3, alt=6000.0))
    t_cab = out["ecs_t"][:, L.E_CAB]
    assert abs(t_cab[-1] - PS.value("ecs_t_set")) < abs(t_cab[0] - PS.value("ecs_t_set"))
    assert abs(t_cab[-1] - PS.value("ecs_t_set")) < 5.0


@pytest.mark.unit
def test_acm_proxy_has_no_bootstrap_gain():
    """PROXY A-W1.4-24 exposing test: the turbine-outlet temperature is exactly a single isentropic expansion
    from the PHX outlet (PHX-outlet pressure -> cabin pressure). A bootstrap ACM would compress first (higher
    turbine inlet pressure, lower outlet temperature); this model cannot show that gain."""
    p3, t3 = _hal_bleed(0.9)
    m, st = module(UtilitiesConfig())
    st, out = run(m, st, inputs(240, p3=p3, t3=t3, alt=6000.0))
    g = PS.value("gamma_air")
    t_phx, p_phx = out["ecs_t"][-1, L.E_PHX], out["ecs_p"][-1, L.E_PHX]
    p_cab_prev = float(st["f"][L.F_ECS_PCAB])  # within one tick of the cabin pressure used
    expect = t_phx * (1 - PS.value("ecs_eta_t") * (1 - (p_cab_prev / p_phx) ** ((g - 1) / g)))
    assert out["ecs_t"][-1, L.E_TURB] == pytest.approx(expect, rel=1e-3)


@pytest.mark.unit
def test_cabin_altitude_channel_is_the_isa_inverse():
    """Recorded ECS.CABIN_P.CABIN_ALT (CPCS-computed): ISA altitude of the cabin pressure; the isobaric 75.26
    kPa cabin reads 8,000 ft (2,438 m) and an unpressurised cabin at ambient reads the ambient pressure
    altitude."""
    for alt in (1000.0, 6000.0):
        _, p_amb, _ = isa(alt)
        m, st = module(UtilitiesConfig(p_amb=p_amb))
        p3, t3 = _hal_bleed(0.95)
        st, out = run(m, st, inputs(60 * 240, p3=max(p3, 3 * p_amb), t3=t3, alt=alt))
        expect = 2438.4 if alt == 6000.0 else 1000.0
        assert out["cabin_alt"][-1] == pytest.approx(expect, abs=3.0), alt
