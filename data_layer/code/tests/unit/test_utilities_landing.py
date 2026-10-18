"""M09 brakes, tyres, chute and fire (A3: RTO at 50/70/90 % brake wear; wear anchors; brake-software chain;
chute limits; physical fire detection).

TEST FIXTURE ground runs: constant deceleration stops with the brake share of the kinetic energy delivered as
af.brake_energy_rate (M06 owns the real ground model). Samples per test stated in the docstring.
"""

from __future__ import annotations

import numpy as np
import pytest
from test_utilities_support import DT, event, inputs, module, run

from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L
from phalanx.utilities.landing import heat_capacity
from phalanx.utilities.params import param_vector

PS = load_m09_params()
P = param_vector(PS)
R_TYRE = PS.value("tyre_r")


def _stop(mass, v0, decel, brake_share, wear, *, skid=False, cool_s=60.0, apps=1, touchdown=False):
    """TEST FIXTURE: a braked ground run from v0 at constant deceleration (brakes absorb ``brake_share``
    of the deceleration force, split evenly, in ``apps`` equal applications), then ``cool_s`` s parked."""
    h = np.zeros(L.N_HEALTH)
    h[L.H_BRAKE_WEAR : L.H_BRAKE_WEAR + 2] = wear
    t_stop = v0 / decel
    n = round(t_stop * 240)
    v = np.maximum(v0 - decel * np.arange(n) * DT, 0.0)
    on = np.ones(n, dtype=bool)
    if apps > 1:
        seg = n // apps  # brake on for the first 80 % of each of the ``apps`` equal segments
        on = (np.arange(n) % seg) < 0.8 * seg
    pw = 0.5 * brake_share * mass * decel * v * on
    wheel = np.zeros(n) if skid else v / R_TYRE
    m, st = module(UtilitiesConfig(soak_temp=288.15))
    if touchdown:  # one airborne tick before the run so the WoW rising edge counts as a landing
        st, _ = run(m, st, inputs(1, wow=(0, 0, 0), tas=v0, health=h))
    st, out = run(
        m,
        st,
        inputs(
            n,
            wow=(1, 1, 1),
            tas=v,
            pbrk=np.stack([pw, pw], axis=1),
            wheel=np.stack([wheel, wheel], axis=1),
            health=h,
            alt=0.0,
            wf=0.1,
        ),
    )
    st, cool = run(m, st, inputs(int(cool_s * 240), wow=(1, 1, 1), tas=0.0, health=h, alt=0.0, wf=0.1))
    return m, st, np.concatenate([out["brake_t"], cool["brake_t"]]), pw, cool


@pytest.mark.unit
def test_rto_test_points_at_50_70_90_wear():
    """ADA RTO trials in the 13.5 t configuration with naturally worn brakes at 50, 70 and 90 % [DIRECT]: the
    heat sink absorbs the stop at every wear point below its capability limit, and the peak temperature rises
    with wear (less carbon mass). RTO from 75 m/s at 3 m/s^2, brakes take 85 %. n = 25 s stop + 60 s each."""
    peaks = []
    limit = PS.value("brk_t_rto_limit")
    for wear in (0.5, 0.7, 0.9):
        _m, st, t_hist, pw, _ = _stop(13500.0, 75.0, 3.0, 0.85, wear)
        peaks.append(float(t_hist.max()))
        e_in = float(st["f"][L.F_BRK_EIN])
        assert e_in == pytest.approx(np.sum(pw) * DT, rel=1e-12)
        # energy balance per heat sink (A1 energy): absorbed = stored + cooled
        c = float(heat_capacity(P, wear))
        stored = c * (float(st["f"][L.F_BRK_T]) - 288.15)
        assert e_in == pytest.approx(stored + float(st["f"][L.F_BRK_EOUT]), rel=1e-9)
    assert peaks[0] < peaks[1] < peaks[2] < limit


@pytest.mark.unit
def test_typical_landing_wear_matches_1400_landing_life():
    """A 9 t landing at 75 m/s, chute + aero decelerating, brakes taking 35 % of 2 m/s^2 in four applications:
    carbon wear per landing ~1/1,400 (F-15 carbon brakes 1,400 landings, TRANSFER) within a factor 1.5, and
    the tyre wear per landing implies 4-12 landings (F-16 main tyres, TRANSFER). n = 37.5 s run + 10 s."""
    m, st, _, _, cool = _stop(9000.0, 75.0, 2.0, 0.35, 0.3, apps=4, cool_s=10.0, touchdown=True)
    tv = m.truth_view(st)
    assert tv["brake_applications"] == [4, 4] and tv["landings"] == 1
    dw = float(st["f"][L.F_BRK_DW])
    assert 1 / (1400 * 1.5) < dw < 1.5 / 1400
    tyre = float(st["f"][L.F_TYRE_DW])
    assert 4 <= 1.0 / tyre <= 12
    assert cool["brake_wear"][-1, 0] == pytest.approx(0.3 + dw)


@pytest.mark.unit
def test_locked_wheel_skid_bursts_tyre():
    """Brake-software event chain (Feb 2026, DIRECT): with anti-skid lost the wheels lock; the skid wears
    through the tyre within the stop and the burst is latched. Same stop with rolling wheels: no burst. n = 25
    s each."""
    m, st, _, _, _ = _stop(9000.0, 60.0, 2.5, 0.8, 0.3, skid=True, cool_s=1.0)
    assert m.truth_view(st)["tyre_burst"] == [1, 1]
    m, st, _, _, _ = _stop(9000.0, 60.0, 2.5, 0.8, 0.3, skid=False, cool_s=1.0)
    assert m.truth_view(st)["tyre_burst"] == [0, 0]


@pytest.mark.unit
def test_hot_brakes_carry_over_between_sorties():
    """Short turnaround: carry_over() keeps the heat-sink temperature (temperatures ratchet, Boeing AERO)."""
    m, st, _, _, _ = _stop(13500.0, 75.0, 3.0, 0.85, 0.5, cool_s=300.0)
    nxt = m.carry_over(st)
    assert nxt.brake_temp[0] == pytest.approx(float(st["f"][L.F_BRK_T])) and nxt.brake_temp[0] > 400.0


@pytest.mark.unit
def test_chute_deploy_limits_and_streaming_count():
    """DDP brake parachute [DIRECT]: deploy <= 285 km/h normal, <= 340 km/h emergency; above 340 km/h the
    canopy fails; every streaming counts toward the 45-streaming life."""
    for v_kmh, state, over in ((250.0, 1, 0), (300.0, 1, 1), (360.0, 3, 1)):
        m, st = module(UtilitiesConfig())
        st, _ = run(m, st, inputs(2, wow=(1, 1, 1), tas=v_kmh / 3.6, alt=0.0))
        st, _ = m.on_event(st, event("util.chute_deploy", emergency=1), 0)
        tv = m.truth_view(st)
        assert (tv["chute_state"], tv["chute_streamings"], tv["chute_over_limit"]) == (state, 1, over), v_kmh
    st, _ = m.on_event(st, event("util.chute_jettison"), 0)
    assert m.truth_view(st)["chute_state"] == 3  # a failed canopy is not 'jettisoned'


@pytest.mark.unit
def test_fire_in_flight_can_go_undetected():
    """A 50 kW bay fire: on the ground (little ventilation) the loop alarms; in fast flight the ram
    ventilation carries the heat away and the loop never reaches its alarm temperature (historic ~50 %
    undetected fires, TRANSFER). A shorted loop alarms without fire. The extinguisher discharges once. n = 60
    s per case."""
    res = {}
    for name, kw in (
        ("ground", {"tas": 0.0, "wow": (1, 1, 1), "alt": 0.0}),
        ("flight", {"tas": 250.0, "alt": 0.0}),
    ):
        m, st = module(UtilitiesConfig())
        st, _ = m.on_event(st, event("util.fault", mode="fire_onset"), 0)
        st, _ = run(m, st, inputs(60 * 240, t3=600.0, **kw))
        res[name] = m.truth_view(st)["fire_warn"]
    assert res == {"ground": 1, "flight": 0}
    m, st = module(UtilitiesConfig())
    st, _ = m.on_event(st, event("util.fault", mode="fire_loop_short"), 0)
    st, _ = run(m, st, inputs(10))
    assert m.truth_view(st)["fire_warn"] == 1 and m.truth_view(st)["fire_on"] == 0
    st, _ = m.on_event(st, event("util.fault", mode="fire_onset"), 0)
    st, _ = m.on_event(st, event("util.fire_extinguish"), 0)
    tv = m.truth_view(st)
    assert tv["extinguisher_charged"] == 0
    u = float(m.stream("fire_extinguish").draws(0, 1)[0])
    assert tv["fire_on"] == (0 if u < PS.value("fire_p_ext") else 1)
    st2, _ = m.on_event(st, event("util.fire_extinguish"), 0)  # empty bottle: nothing changes
    assert np.array_equal(st2["i"], st["i"])


@pytest.mark.unit
def test_brake_pressure_follows_torque_and_supply():
    """util.brake_p (A-W1.4-32): the pressure behind the brake torque P / (w + w_floor), so a harder stop
    needs more pressure; a locked (skidding) wheel holds at least the tyre-friction pressure; the pressure
    never exceeds the metered maximum or the supplying hydraulic system (SYS2): with SYS2 depressurised
    (engine off, pump stopped) the brakes get nothing. n = 2 s per case."""
    gain = PS.value("brk_torque_gain")

    def brake(pw, wheel, n2f=0.95, demand=0.0):
        m, st = module(UtilitiesConfig(soak_temp=288.15, engine_running=n2f > 0.1))
        st, out = run(
            m,
            st,
            inputs(
                480,
                n2f=n2f,
                demand=demand,
                wow=(1, 1, 1),
                tas=40.0,
                alt=0.0,
                pbrk=(pw, pw),
                wheel=(wheel, wheel),
            ),
        )
        return out["brake_p"][-1], out["hyd_p"][-1]

    soft, _ = brake(2e5, 140.0)
    hard, _ = brake(6e5, 140.0)
    assert hard[0] > soft[0] > 0.0
    assert soft[0] == pytest.approx(2e5 / ((140.0 + PS.value("jfs_w_floor")) * gain), rel=1e-9)
    locked, _ = brake(0.0, 0.0)  # wheel stopped at 40 m/s rolling speed: skid
    assert locked[0] > 0.0
    capped, _ = brake(5e7, 1.0)  # absurd torque request: capped at the metered maximum
    assert capped[0] == pytest.approx(PS.value("brk_p_max"))
    dead, hyd = brake(6e5, 140.0, n2f=0.0)
    assert hyd[1] < PS.value("hyd_p_nom") and dead[0] <= max(hyd[1], 0.0) + 1e-6
