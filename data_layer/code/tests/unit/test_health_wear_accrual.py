"""AD-48.6 (W2.1c): brake and tyre wear have one owner per tier.

- **Telemetry mode:** M09 accrues the main brakes' and tyres' physical wear in the sortie (application count,
  energy, oxidation, touchdown scrub, braking slip, skid); at sortie end ``Utilities.sortie_wear`` hands the
  accrual to M10 (``SortieUsage.brake_wear_accrued`` / ``tyre_wear_accrued``), which adds it to the hidden
  state instead of drawing its per-landing surrogate. The next sortie's M09 starts from M10's
  ``health.utility`` - the same wear, carried over exactly.
- **Usage mode:** M10's per-landing gamma surrogate is calibrated to M09: at M09's reference landing (9 t,
  75 m/s, four brake applications, ``brake_energy_ref`` absorbed per wheel) M09's accrual equals M10's mean
  per-landing rates (brake 1/1,400, tyre 1/8; both TRANSFER anchors already shared by the two modules).

The brake driver counts reference stops (energy / ``brake_energy_ref``); W1 multiplied it by the landings
again (landings^2 per sortie in usage mode) - the negative control below fails on that formula.

TEST FIXTURE ground runs (``test_utilities_support``): a constant-deceleration stop whose brake power is
scaled so each wheel absorbs ``brake_energy_ref`` (M06 owns the real ground model; M06 + M09 landings are
W2.1a's integration). n = 1 reference landing (37.5 s + 10 s parked) per test; M10 runs 1 sortie per arm.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from test_utilities_support import DT, inputs, module, run

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.health import (
    AIRFRAME_NAMES,
    HealthConfig,
    HealthModule,
    SortieUsage,
    load_health_params,
    sensor_bias_channels,
)
from phalanx.health.protocol import plain_payload, read_payload
from phalanx.health.usage import summary_payload, usage_from_summary
from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L

pytestmark = pytest.mark.unit
PS9 = load_m09_params()
PS10 = load_health_params()
E_REF = float(PS10.value("brake_energy_ref"))  # J per wheel (SI after loading)
SEC = 10**9
STEP = SEC // 240


def _fuel_for(mass: float) -> tuple[float, ...]:
    """TEST FIXTURE: internal tank masses (filled in tank order) that put M09's aircraft at ``mass`` [kg]."""
    m0, st0 = module(UtilitiesConfig(soak_temp=288.15, fuel=(0.0,) * L.N_TANKS))
    _, o = run(m0, st0, inputs(1, wow=(1, 1, 1), tas=0.0, alt=0.0))
    full = module(UtilitiesConfig(soak_temp=288.15))[1]["f"][L.F_FUEL_M : L.F_FUEL_M + L.N_TANKS]
    rest, fuel = mass - float(o["mass"][0]), []
    for cap in full:
        fuel.append(min(rest, float(cap)))
        rest -= fuel[-1]
    assert rest < 1e-9
    return tuple(fuel)


def reference_landing(health: np.ndarray, *, mass=9000.0, v0=75.0, decel=2.0, e_wheel=E_REF, apps=4):
    """TEST FIXTURE: M09's reference landing - M09's aircraft at ``mass`` (the tyre law's reference mass by
    default), one touchdown at ``v0``, a constant-deceleration stop braked in ``apps`` applications (on for
    the first 80 % of each equal segment), the brake power scaled so each wheel absorbs ``e_wheel``, rolling
    wheels, then 10 s parked. Returns (module, state, outputs)."""
    n = round(v0 / decel * 240)
    v = np.maximum(v0 - decel * np.arange(n) * DT, 0.0)
    on = (np.arange(n) % (n // apps)) < 0.8 * (n // apps)
    shape = v * on
    pw = shape * (e_wheel / (float(np.sum(shape)) * DT))
    m, st = module(UtilitiesConfig(soak_temp=288.15, fuel=_fuel_for(mass)))
    st, _ = run(m, st, inputs(1, wow=(0, 0, 0), tas=v0, health=health))  # airborne tick: WoW edge = landing
    wheel = v / float(PS9.value("tyre_r"))
    blk = inputs(
        n,
        wow=(1, 1, 1),
        tas=v,
        pbrk=np.stack([pw, pw], axis=1),
        wheel=np.stack([wheel, wheel], axis=1),
        health=health,
        alt=0.0,
        wf=0.1,
    )
    st, out = run(m, st, blk, 1)
    st, cool = run(m, st, inputs(2400, wow=(1, 1, 1), tas=0.0, health=health, alt=0.0, wf=0.1), 1 + n)
    return m, st, {k: np.concatenate([out[k], cool[k]]) for k in ("brake_wear", "tyre_wear")}


def m10(root=0x5EED):
    dic = load_dictionary()
    m = HealthModule("health", PS10, config=HealthConfig(("IN20-0001",), sensor_bias_channels(dic), None))
    sysm = System(
        [m], [], rng=RngService(root, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail="T1")
    )
    return m, sysm


def sortie(u: SortieUsage, *, root=0x5EED):
    """One M10 sortie (``health.sortie``) from a fresh build; returns (module, state before, state after)."""
    m, sysm = m10(root)
    w0 = sysm.start()
    w = sysm.inject(w0, [Event(SEC, "health.sortie", "health", u.to_payload())])
    w, _ = sysm.run(w, SEC // STEP + 2 - w.k)
    return m, w0.states["health"], w.states["health"]


def usage(sid="T1-1", **kw) -> SortieUsage:
    return SortieUsage(
        sortie_id=sid,
        flight_time_s=3600.0,
        eot_s=(4500.0,),
        tamp_s=(600.0,),
        type1=(1.0,),
        type3=(5.0,),
        type4=(5.0,),
        eftc=(1.2,),
        src_h=(0.05,),
        ps3_full=(0.0,),
        ps3_partial=(1.0,),
        ab_lights=(4.0,),
        starts=(1.0,),
        **kw,
    )


def _air(state, name):
    return float(state["air"][AIRFRAME_NAMES.index(name)])


def test_m10_surrogate_is_calibrated_to_the_m09_reference_landing():
    """At the reference landing M09 counts one landing and four applications per wheel, absorbs
    ``brake_energy_ref`` per wheel without oxidation, and its accrual equals M10's mean per-landing rates
    within 2 % (brake 7.14e-4 = 1/1,400; tyre 0.125)."""
    h = np.zeros(L.N_HEALTH)
    h[L.H_BRAKE_WEAR : L.H_BRAKE_WEAR + 2] = 0.3
    m9, st, _ = reference_landing(h)
    tv = m9.truth_view(st)
    assert tv["landings"] == 1 and tv["brake_applications"] == [4, 4]
    wear = m9.sortie_wear(st)
    assert wear["landings"] == 1.0
    assert wear["brake_energy_j"] == pytest.approx((E_REF, E_REF), rel=1e-9)
    assert float(np.max(st["f"][L.F_BRK_T : L.F_BRK_T + 2])) < float(PS9.value("brk_t_ox"))  # no oxidation
    for w in range(2):
        assert wear["brake_wear_accrued"][w] == pytest.approx(float(PS10.value("brake_wear_rate")), rel=0.02)
        assert wear["tyre_wear_accrued"][w] == pytest.approx(float(PS10.value("tyre_wear_rate")), rel=0.02)


def test_telemetry_accrual_replaces_the_surrogate_and_carries_over_exactly():
    """M09 starts from M10's ``health.utility``; M10 adds M09's accrual; the next sortie's
    ``health.utility`` is exactly M09's end-of-sortie wear (no second draw on top). The nose tyre (not
    modelled in M09) keeps the surrogate."""
    mod, sysm = m10()
    h0 = mod.utility_vector(sysm.start().states["health"])
    m9, st9, out9 = reference_landing(h0)
    wear = m9.sortie_wear(st9)
    u = usage(**wear)
    m, before, after = sortie(u)
    h1 = m.utility_vector(after)
    for w, side in enumerate("lr"):
        assert _air(after, f"brake_wear_{side}") - _air(before, f"brake_wear_{side}") == pytest.approx(
            wear["brake_wear_accrued"][w], rel=1e-12
        )
        assert h1[L.H_BRAKE_WEAR + w] == pytest.approx(out9["brake_wear"][-1, w], rel=1e-12)
        assert h1[L.H_TYRE_WEAR + w] == pytest.approx(out9["tyre_wear"][-1, w], rel=1e-12)
    assert _air(after, "tyre_wear_n") > _air(before, "tyre_wear_n")  # surrogate, one landing


def test_accrual_leaves_every_other_process_and_stream_untouched():
    """CRN: the accrual replaces only the four main brake / tyre states; every other airframe state, the
    actuators and the engines advance bitwise as without it (each process keeps its own generator)."""
    wear = {"brake_wear_accrued": (1e-3, 2e-3), "tyre_wear_accrued": (0.1, 0.2)}
    _, _, a = sortie(usage(landings=1.0, brake_energy_j=(E_REF, E_REF), **wear))
    _, _, b = sortie(usage(landings=1.0, brake_energy_j=(E_REF, E_REF)))
    own = [AIRFRAME_NAMES.index(n) for n in ("brake_wear_l", "brake_wear_r", "tyre_wear_l", "tyre_wear_r")]
    keep = np.ones(len(AIRFRAME_NAMES), bool)
    keep[own] = False
    assert np.array_equal(a["air"][keep], b["air"][keep])
    for k in a:
        if k != "air":
            assert np.array_equal(np.asarray(a[k]), np.asarray(b[k])), k
    assert not np.array_equal(a["air"][own], b["air"][own])


def test_brake_driver_counts_reference_stops_not_landings_squared():
    """Usage mode: a two-landing summary carries 2 x ``brake_energy_ref`` per wheel, i.e. two reference stops.
    Its brake wear is bitwise that of the same sortie with no energy reported (driver = landings = 2); the W1
    formula (landings x energy / ref = 4) fails this (negative control, see the W2.1c report)."""
    d = {"sortie_id": "T1-1", "tail_no": "T1", "flight_hours": 1.0, "landings": 2.0, "engine_starts": 1.0}
    u_sum = usage_from_summary(d, PS10, 1)
    assert u_sum.brake_energy_j == pytest.approx((2 * E_REF, 2 * E_REF))
    _, _, a = sortie(u_sum)
    _, _, b = sortie(dataclasses.replace(u_sum, brake_energy_j=(0.0, 0.0)))
    for side in "lr":
        assert _air(a, f"brake_wear_{side}") == _air(b, f"brake_wear_{side}") > 0.0


def test_accrual_travels_through_the_summary_payload():
    """Telemetry mode closes the sortie with ``usage.sortie_summary`` carrying the full usage (plain keys,
    AD-48.1): the accrual round-trips exactly; a usage without accrual round-trips as usage mode."""
    u = usage(landings=1.0, brake_energy_j=(4.0e6, 3.0e6), brake_wear_accrued=(7e-4, 6e-4))
    for x in (u, usage(landings=1.0)):
        back = usage_from_summary(read_payload(plain_payload(summary_payload(x, "T1"))), PS10, 1)
        assert back == x


@pytest.mark.parametrize("bad", [(1e-3,), (1e-3, 2e-3, 3e-3), (-1e-3, 0.0)])
def test_accrual_must_be_two_non_negative_main_wheel_values(bad):
    with pytest.raises(ValueError, match="brake_wear_accrued"):
        usage(brake_wear_accrued=bad)


def test_no_landing_no_accrual():
    """A sortie that never touches down (airborne only): M09 reports no landing and zero accrual."""
    m9, st = module(UtilitiesConfig(soak_temp=288.15))
    st, _ = run(m9, st, inputs(240))
    wear = m9.sortie_wear(st)
    assert wear["landings"] == 0.0
    assert wear["brake_wear_accrued"] == (0.0, 0.0) and wear["tyre_wear_accrued"] == (0.0, 0.0)
