"""M09 electrical network (A4): source transfer <= 50 ms on generator underspeed, MIL-STD-704F band
classification, battery charge/discharge and the charge balance (A1 charge).

Samples: spool-down 40 s; steady cases 5-60 s (stated per test).
"""

from __future__ import annotations

import numpy as np
import pytest
from test_utilities_support import DT, event, inputs, module, run

from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L
from phalanx.utilities.electrical import (
    PQ_EMERGENCY,
    PQ_NORMAL,
    PQ_OUT,
    PQ_STARTING,
    PQ_TRANSFER,
    SRC_BACKUP,
    SRC_BATT,
    SRC_TRU,
    classify_ac400,
    classify_dc28,
)
from phalanx.utilities.params import power_quality_bands

PS = load_m09_params()
BANDS = power_quality_bands(PS)


def _gaps(v: np.ndarray) -> list[int]:
    """Lengths (ticks) of runs of zero voltage."""
    runs, n = [], 0
    for x in v:
        if x == 0.0:
            n += 1
        elif n:
            runs.append(n)
            n = 0
    if n:
        runs.append(n)
    return runs


@pytest.mark.unit
def test_spool_down_transfer_within_50ms():
    """A4: N2 spools down from 70 % to 0 in 20 s (flameout-like) with gear up. The main generator drops at its
    underspeed, the essential/emergency buses transfer to the 5 kW DC backup and then to the battery; each
    transfer interrupts them for <= 50 ms (704F §5.1) and never longer. n = 40 s."""
    n = 40 * 240
    n2f = np.clip(0.7 - 0.035 * np.arange(n) * DT, 0.0, None)
    m, st = module(UtilitiesConfig())
    st, out = run(m, st, inputs(n, n2f=n2f, p3=1.5e5, t3=400.0, wf=0.0))
    gen = out["gen_online"]
    assert gen[0] == 1 and gen[-1] == 0
    k_drop = int(np.argmax(gen == 0))
    assert n2f[k_drop] < PS.value("gen_dropout") <= n2f[k_drop - 1]
    gaps_emg = _gaps(out["bus_v"][:, L.B_EMG])
    assert len(gaps_emg) == 2  # main -> backup, backup -> battery
    assert max(gaps_emg) * DT <= 0.050 + 1e-12
    gaps_ess = _gaps(out["bus_v"][:, L.B_ESS])
    assert len(gaps_ess) == 2 and gaps_ess[0] * DT <= 0.050 + 1e-12  # one transfer, then shed on the battery
    assert out["bus_v"][-1, L.B_ESS] == 0.0
    # AC main and DC main are shed with the generator (and stay shed)
    assert np.all(out["bus_v"][k_drop:, L.B_AC] == 0.0) and np.all(out["bus_v"][k_drop:, L.B_DCM] == 0.0)
    # end state: emergency bus on the battery inside the 704F emergency band; essential shed
    assert m.truth_view(st)["ess_src"] == SRC_BATT
    v_emg = out["bus_v"][-1, L.B_EMG]
    assert classify_dc28(v_emg, BANDS, emergency=True) in (PQ_NORMAL, PQ_EMERGENCY)
    assert out["bus_v"][-1, L.B_ESS] == 0.0


@pytest.mark.unit
def test_generator_fault_event_transfers_to_backup_once():
    m, st = module(UtilitiesConfig())
    st, out0 = run(m, st, inputs(240))
    st, _ = m.on_event(st, event("util.fault", mode="gen_fail"), 0)
    st, out = run(m, st, inputs(240), k0=240)
    assert out0["gen_online"][-1] == 1 and np.all(out["gen_online"] == 0)
    assert m.truth_view(st)["ess_src"] == SRC_BACKUP
    gaps = _gaps(out["bus_v"][:, L.B_ESS])
    assert gaps == [int(np.ceil(PS.value("elec_transfer_time") * 240 - 1e-9))]
    st, _ = m.on_event(st, event("util.fault", mode="gen_restore"), 0)
    st, out2 = run(m, st, inputs(240), k0=480)
    assert out2["gen_online"][-1] == 1 and m.truth_view(st)["ess_src"] == SRC_TRU
    with pytest.raises(Exception):  # noqa: B017 - ContractError subclass
        m.on_event(st, event("util.fault", mode="no_such_mode"), 0)


@pytest.mark.unit
def test_bus_voltages_in_704f_normal_band():
    """Generator online, ground and airborne load sets: AC 108-118 V rms at 400 Hz, DC 22-29 V. n = 5 s
    each."""
    for wow in ((1, 1, 1), (0, 0, 0)):
        m, st = module(UtilitiesConfig())
        st, out = run(m, st, inputs(5 * 240, wow=wow, tas=0.0 if wow[0] else 200.0))
        v = out["bus_v"][-1]
        assert classify_ac400(v[L.B_AC], 400.0, BANDS) == PQ_NORMAL
        for b in (L.B_DCM, L.B_ESS, L.B_EMG):
            assert classify_dc28(v[b], BANDS) == PQ_NORMAL


@pytest.mark.unit
def test_704f_classification_band_edges():
    """MIL-STD-704F Table IV / §5.3.2.3-4 / Table I edges, including negative controls just outside."""
    assert classify_dc28(22.0, BANDS) == PQ_NORMAL and classify_dc28(29.0, BANDS) == PQ_NORMAL
    assert classify_dc28(21.99, BANDS) == PQ_OUT and classify_dc28(29.01, BANDS) == PQ_OUT
    assert classify_dc28(16.0, BANDS, emergency=True) == PQ_EMERGENCY
    assert classify_dc28(15.99, BANDS, emergency=True) == PQ_OUT
    assert classify_dc28(12.0, BANDS, starting=True) == PQ_STARTING
    assert classify_dc28(11.99, BANDS, starting=True) == PQ_OUT
    assert classify_dc28(0.0, BANDS, transfer=True) == PQ_TRANSFER
    assert (
        classify_ac400(108.0, 393.0, BANDS) == PQ_NORMAL and classify_ac400(118.0, 407.0, BANDS) == PQ_NORMAL
    )
    assert classify_ac400(107.9, 400.0, BANDS) == PQ_OUT and classify_ac400(115.0, 408.0, BANDS) == PQ_OUT


@pytest.mark.unit
def test_battery_charge_balance_and_charging():
    """A1 charge: the battery's SOC change equals the integrated current; on the generator the battery charges
    at <= 50 A (DIRECT-part) and SOC rises; on the battery alone it discharges. n = 60 s each."""
    cap = PS.value("batt_cap_ah")  # coulombs (SI)
    m, st0 = module(UtilitiesConfig(batt_soc=0.6))
    st, _ = run(m, st0, inputs(60 * 240))
    q = float(st["f"][L.F_BATT_Q])
    assert q < 0.0 and float(st["f"][L.F_BATT_SOC]) > 0.6  # charging
    assert -q / 60.0 <= PS.value("batt_i_charge") + 1e-9
    # SOC accumulates small increments in a variable near 0.6, so the two sums differ by rounding only (~1e-7)
    assert (float(st["f"][L.F_BATT_SOC]) - 0.6) * cap == pytest.approx(-q, rel=1e-6)
    m, st0 = module(UtilitiesConfig(batt_soc=0.9, engine_running=False))
    st, out = run(m, st0, inputs(60 * 240, n2f=0.0, p3=1.0e5, t3=288.0, wf=0.0, wow=(1, 1, 1), tas=0.0))
    q = float(st["f"][L.F_BATT_Q])
    assert q > 0.0 and (0.9 - float(st["f"][L.F_BATT_SOC])) * cap == pytest.approx(q, rel=1e-6)
    assert (
        out["gen_online"][-1] == 0
        and classify_dc28(out["bus_v"][-1, L.B_EMG], BANDS, emergency=True) != PQ_OUT
    )


@pytest.mark.unit
def test_cold_battery_has_higher_resistance_and_lower_cranking_voltage():
    """Cold soak raises the battery resistance: under the same starter load the terminal voltage is lower."""
    from phalanx.utilities.electrical import battery_r
    from phalanx.utilities.params import param_vector

    p = param_vector(PS)
    assert battery_r(p, 0.03, 253.15) > battery_r(p, 0.03, 288.15) > battery_r(p, 0.03, 313.15)


@pytest.mark.unit
def test_probe_heaters_and_recorded_electrical_channels():
    """util.probe_heat: on with the generator whenever airborne, on the ground only when cold. Recorded
    LRU-computed channels (ports.RECORDED): GEN OUT = not online; the battery display (BDU) integrates from
    the 45 Ah full mark, so fade is invisible to it, and the 30 Ah low warning trips below it; the backup
    GCU BITE latches its fault."""
    m, st = module(UtilitiesConfig())
    air = run(m, st, inputs(24, wow=(0, 0, 0)))[1]
    gnd_warm = run(m, st, inputs(24, wow=(1, 1, 1), tas=0.0, mach=0.0, t_s=300.0, alt=0.0))[1]
    gnd_cold = run(m, st, inputs(24, wow=(1, 1, 1), tas=0.0, mach=0.0, t_s=265.0, alt=0.0))[1]
    assert (air["probe_heat"][-1], gnd_warm["probe_heat"][-1], gnd_cold["probe_heat"][-1]) == (1, 0, 1)
    assert air["gen_out"][-1] == 1 - air["gen_online"][-1] == 0
    cap = PS.value("batt_cap_ah")
    h = np.zeros(L.N_HEALTH)
    h[L.H_BATT_FADE] = 0.3
    for soc, fade, low in ((0.9, 0.0, 0), (0.6, 0.0, 1), (0.6, 0.3, 0)):
        hh = h * (fade / 0.3)
        m, st = module(UtilitiesConfig(batt_soc=soc, engine_running=False))
        out = run(m, st, inputs(1, n2f=0.0, p3=1e5, t3=288.0, wf=0.0, wow=(1, 1, 1), tas=0.0, health=hh))[1]
        soc1 = float(out["batt_soc"][-1])
        assert out["batt_ah"][-1] == pytest.approx(cap - cap * (1 - fade) * (1 - soc1), rel=1e-12)
        assert out["batt_low"][-1] == low, (soc, fade)
    m, st = module(UtilitiesConfig())
    st, _ = m.on_event(st, event("util.fault", mode="bk_fail"), 0)
    assert run(m, st, inputs(1))[1]["bk_bite"][-1] == 1
