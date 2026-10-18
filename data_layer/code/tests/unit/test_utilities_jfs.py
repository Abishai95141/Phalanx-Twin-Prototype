"""GTSU-110 JFS start model (A3: JFS cold/altitude start behaviour; report §3 edge 'battery SOC, OAT, altitude
-> JFS start success'; CAG 17/2015; HAL/IDR Feb 2015; DRDO rig to Khardung La).

Each case runs the TEST FIXTURE start protocol (engine spool with I_HP = 3 kg m^2, light-off at 20 % N2,
start commands 120 s apart, engine shut down 20 s after reaching idle; tests/unit/test_utilities_support.py).
Samples: 1 or 3 starts per case; deterministic (keyed ignition draws, fixed root).
"""

from __future__ import annotations

import numpy as np
import pytest
from test_utilities_support import N2_100, event, ground_inputs, isa, module, start_protocol

from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L
from phalanx.utilities.jfs import JFS_CRANK, JFS_ENGAGED, OUT_ABORT, OUT_HUNG, OUT_OK, OUT_SLOW_CRANK

PS = load_m09_params()
LEH = 3260.0  # m (ADA rig trials at Leh, N KQ1)


@pytest.mark.unit
def test_ada_cold_start_anchor():
    """HAL/IDR Feb 2015 [DIRECT]: three consecutive starts at Leh at -15 degC with an 85 % battery (M2 /
    modified schedule) succeed. CAG 17/2015 [DIRECT]: the M1 could not prove three consecutive starts at Leh
    in January (below -16 degC). Calibration anchor of A-W1.4-27."""
    m2 = start_protocol(variant=2, t_amb=258.15, alt=LEH, soc=0.85)
    assert m2.outcomes == [OUT_OK] * 3 and m2.consecutive == 3
    m1 = start_protocol(variant=1, t_amb=257.15, alt=LEH, soc=0.85)
    assert m1.consecutive < 3 and any(o != OUT_OK for o in m1.outcomes)


@pytest.mark.unit
def test_both_variants_start_at_sea_level_in_the_t50_time_scale():
    """ISA sea level, full battery: one start each; time from command to starter cut-out 15-40 s (T-50
    F404-102: light-off ~27 s, idle ~40 s, TRANSFER)."""
    for variant in (1, 2):
        r = start_protocol(variant=variant, t_amb=288.15, alt=0.0, soc=1.0, n_starts=1)
        assert r.outcomes == [OUT_OK] and 15.0 <= r.times[0] <= 40.0


@pytest.mark.unit
def test_m2_starts_at_5_6_km_and_fails_above_the_demonstrated_altitude():
    """DRDO/HAL: start capability shown at 5.6 km (rig, modified schedule) [DIRECT]; the model starts there
    and not at 6.5 km (altitude lowers JFS power, report §3)."""
    ok = start_protocol(variant=2, t_amb=isa(5600.0)[0], alt=5600.0, soc=1.0, n_starts=1)
    assert ok.outcomes == [OUT_OK]
    hi = start_protocol(variant=2, t_amb=isa(6500.0)[0], alt=6500.0, soc=1.0, n_starts=1)
    assert hi.outcomes != [OUT_OK]


@pytest.mark.unit
def test_jfs_start_slower_when_cold_high_or_low_soc():
    """Report §3 edge signs: lower SOC, colder soak and higher altitude each lengthen the start (M2, one
    start)."""
    t_soc = [
        start_protocol(variant=2, t_amb=258.15, alt=LEH, soc=s, n_starts=1).times[0] for s in (0.85, 0.2)
    ]
    assert t_soc[1] > t_soc[0]
    t_alt = [
        start_protocol(variant=2, t_amb=isa(a)[0], alt=a, soc=1.0, n_starts=1).times[0] for a in (0.0, 3260.0)
    ]
    assert t_alt[1] > t_alt[0]
    t_cold = [
        start_protocol(variant=2, t_amb=t, alt=LEH, soc=0.85, n_starts=1).times[0] for t in (263.15, 248.15)
    ]
    assert t_cold[1] > t_cold[0]


@pytest.mark.unit
def test_cold_partly_charged_battery_fails_to_crank():
    """-30 degC at Leh with a 50 % battery: the cold, partly discharged battery cannot crank the JFS to
    light-off (slow-crank failure), the 'stringent case' of DRDO's statement; at 85 % it starts."""
    bad = start_protocol(variant=2, t_amb=243.15, alt=LEH, soc=0.5, n_starts=1)
    assert bad.outcomes == [OUT_SLOW_CRANK]


@pytest.mark.unit
def test_m1_cold_failure_is_a_hung_start_and_m1_burns_more_oil():
    m1 = start_protocol(variant=1, t_amb=257.15, alt=LEH, soc=0.85, n_starts=1)
    assert m1.outcomes == [OUT_HUNG]
    oil = {}
    for v in (1, 2):
        m, st = module(UtilitiesConfig(jfs_variant=v, engine_running=False))
        q0 = float(st["f"][L.F_JFS_OILQ])
        st, _ = m.on_event(st, event("util.jfs_start"), 0)
        for k in range(30 * 240):
            st, _ = m.step_block(st, ground_inputs(0.0, 288.15, 101325.0), np.array([k], np.int64), 1 / 240)
            if int(st["i"][L.I_JFS_LIT]) == 1:
                break
        oil[v] = q0 - float(st["f"][L.F_JFS_OILQ])
    assert oil[1] > oil[2] > 0.0


@pytest.mark.unit
def test_jfs_drives_the_engine_through_the_pto_within_its_ratings():
    """While engaged, util.pto_power is negative (power into the engine) and bounded by the 410 N m PTO peak
    torque (DIRECT) and the 110 kW rating (DIRECT) times the density lapse."""
    m, st = module(UtilitiesConfig(engine_running=False))
    st, _ = m.on_event(st, event("util.jfs_start"), 0)
    seen = []
    w = 0.1 * N2_100
    for k in range(25 * 240):
        engaged = int(st["i"][L.I_JFS_MODE]) == JFS_ENGAGED  # engaged for the whole tick
        st, out = m.step_block(st, ground_inputs(w, 288.15, 101325.0), np.array([k], np.int64), 1 / 240)
        if engaged and int(st["i"][L.I_JFS_MODE]) == JFS_ENGAGED:
            seen.append(float(out["pto_power"][0, 0]))
    assert seen and max(seen) < 0.0
    lim = min(PS.value("pto_torque_peak") * (w + PS.value("jfs_w_floor")), PS.value("jfs_p_rated"))
    assert -min(seen) <= lim + 1e-6


@pytest.mark.unit
def test_abort_and_restart_and_ignition_draw_index():
    """util.jfs_abort ends a start (outcome ABORT, consecutive reset); a new start increments the attempt
    index and the ignition draw for attempt a is the stream's draw a-1 (keyed by scenario, tail, sortie)."""
    m, st = module(UtilitiesConfig(engine_running=False))
    st, _ = m.on_event(st, event("util.jfs_start"), 0)
    assert int(st["i"][L.I_JFS_MODE]) == JFS_CRANK and int(st["i"][L.I_JFS_ATTEMPT]) == 1
    st, _ = m.on_event(st, event("util.jfs_abort"), 0)
    assert int(st["i"][L.I_JFS_OUTCOME]) == OUT_ABORT and int(st["i"][L.I_JFS_CONSEC]) == 0
    st, _ = m.on_event(st, event("util.jfs_start"), 0)
    assert int(st["i"][L.I_JFS_ATTEMPT]) == 2
    expect = float(m.stream("jfs_ignition").draws(1, 1)[0])
    assert m._ignition_draw(st["i"]) == expect
    # a different sortie has a different, independent draw for the same attempt (identity keying)
    m_b, _ = module(UtilitiesConfig(engine_running=False))
    from test_utilities_support import bind

    from phalanx.utilities import Utilities

    other = bind(Utilities("util", PS, config=UtilitiesConfig(engine_running=False)), sortie=2)
    assert float(other.stream("jfs_ignition").draws(1, 1)[0]) != expect
    assert float(m_b.stream("jfs_ignition").draws(1, 1)[0]) == expect
