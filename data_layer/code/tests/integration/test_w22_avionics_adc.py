"""W2.2 M12 avionics: ADC computation on the digitised DFCC/ADC lanes (AD-51; A-W2.2-6, -7, -10).

Chain: fixture truth -> M12 SensorPhysics (the 21 ADC probe/vane/TAT channels) -> M13 LaneAcquisition (DFCC
lanes) -> AvionicsSystem, in a core System. The ADC sees only the digitised lanes (with the M12 transducer
physics and the M13 texture), never truth; truth enters the assertions only.

The accuracy checks are relative to the raw lanes, not tuned absolute bars: the computed outputs must remove
most of the probe errors that the same formulas without the corrections would keep (static-source position
error, vane local-flow bias, TAT recovery and heater error). The PROXY tests expose the documented
limitations (gear term placed at the ADC; DPA/DPB not simulated). Sample size: one sortie (fixed identity)
per scenario, 1-12 s at 240 Hz (80 Hz DFCC frames); deterministic.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.dictionary import load_dictionary
from phalanx.sensors.avionics import adc as A
from phalanx.sensors.avionics.config import build_avionics_config
from phalanx.sensors.avionics.ports import RECORDED


def _fixture():
    name = "w22_avionics_fixture"
    if name not in sys.modules:
        p = Path(__file__).resolve().parent / "test_w22_avionics_fixture.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


FX = _fixture()
D = load_dictionary()
CFG = build_avionics_config()
AP = CFG.adc_p
GAMMA = float(AP[A.P_GAMMA])
KU_AOA = float(AP[A.P_KU_AOA])
ALL_BITS = (1 << 10) - 1
VALID_PORTS = [f"avio.rec_{w.lower().replace('.', '_')}" for w in A.VALID_CHANNELS]


def run_chain(truth, n: int, *, bias=None, compiled: bool = True, mode: str = "block", extra=()):
    system, _, mods = FX.build_avionics_chain(D, truth, bias=bias, compiled=compiled)
    rec = [f"avio.{p.name}" for p in mods["avio"].ports_out] + list(extra)
    _, tr = system.run(system.start(), n, record=rec, mode=mode)
    return tr.ports


def err(o, cid: str, k: int = -1) -> float:
    p = cid.lower().replace(".", "_")
    return float(o[f"avio.rec_{p}"][k] - o[f"avio.tru_{p}"][k])


def val(o, cid: str, k: int = -1, which: str = "rec") -> float:
    return float(o[f"avio.{which}_{cid.lower().replace('.', '_')}"][k])


def last_sample(o, port: str) -> float:
    """Last digitised sample of an M13 lane buffer recorded over the run."""
    cnt = o[port + "_n"]
    k = int(np.flatnonzero(cnt > 0)[-1])
    return float(o[port][k, int(cnt[k]) - 1])


@pytest.mark.integration
def test_adc_removes_the_probe_errors_of_the_digitised_lanes():
    """Level flight, Mach 0.61 at 3,000 m, 3 s (TAT probe settled). 'Raw' = the same air-data formulas on the
    voted lanes without the corrections. The computed outputs keep < 10 % of the raw altitude and AoA errors,
    < 20 % of the raw Mach and CAS errors, less than the raw SAT error; HBARO = HP at the standard setting;
    HDOT ~ 0; every monitor bit set."""
    n = 720
    o = run_chain(FX.default_truth(n), n, extra=("acq_dfcc.lane_ad_tat", "acq_dfcc.lane_ad_tat_n"))
    ps_v, pt_v = val(o, "AD.PS.V"), val(o, "AD.PT.V")
    rho = FX.isa(3000.0)[2]
    raw_h_err = -(ps_v - val(o, "AD.PS.V", which="tru")) / (rho * 9.80665)
    assert abs(raw_h_err) > 20.0  # the static-source position error is large uncorrected
    assert abs(err(o, "AD.HP")) < 0.1 * abs(raw_h_err)
    m_t = val(o, "AD.MACH", which="tru")
    raw_m = A.mach_from_qc(pt_v - ps_v, ps_v, GAMMA)
    assert abs(err(o, "AD.MACH")) < 0.2 * abs(raw_m - m_t)
    a0 = math.sqrt(GAMMA * AP[A.P_RAIR] * AP[A.P_T0])
    raw_cas = a0 * A.mach_from_qc(pt_v - ps_v, AP[A.P_P0], GAMMA)
    assert abs(err(o, "AD.CAS")) < 0.2 * abs(raw_cas - val(o, "AD.CAS", which="tru"))
    raw_aoa = (val(o, "AD.AOA_VANE_L.V") + val(o, "AD.AOA_VANE_R.V")) / 2.0
    raw_aoa_err = raw_aoa - val(o, "AD.AOA", which="tru")
    assert abs(raw_aoa_err) > math.radians(0.5)  # vane local-flow (upwash) bias uncorrected
    assert abs(err(o, "AD.AOA")) < 0.1 * abs(raw_aoa_err)
    tat = last_sample(o, "acq_dfcc.lane_ad_tat")
    raw_sat = tat / (1.0 + 0.5 * (GAMMA - 1.0) * m_t * m_t)  # full recovery, heater ignored
    assert abs(err(o, "AD.SAT")) < abs(raw_sat - val(o, "AD.SAT", which="tru"))
    assert val(o, "AD.HBARO") == val(o, "AD.HP")  # standard altimeter setting (QNH 1013.25 hPa)
    assert abs(val(o, "AD.HDOT")) < 0.05
    for p in VALID_PORTS:
        assert np.all(o[p][240:] == ALL_BITS)


@pytest.mark.integration
def test_hdot_follows_a_climb_through_the_pneumatic_and_filter_lags():
    """A steady 10 m/s climb (static pressure following the ICAO atmosphere), 12 s: HDOT settles at the climb
    rate (5 %) after the static-line and filter lags (tau 1 s), and HP tracks the altitude."""
    n = 240 * 12
    truth = FX.default_truth(n)
    alt = 3000.0 + 10.0 * FX.frame_times(n)
    truth["env.p_s"] = np.array([FX.isa(h)[0] for h in alt])
    truth["env.t_s"] = np.array([FX.isa(h)[1] for h in alt])
    truth["env.rho"] = np.array([FX.isa(h)[2] for h in alt])
    o = run_chain(truth, n)
    assert val(o, "AD.HDOT") == pytest.approx(10.0, rel=0.05)
    assert val(o, "AD.HP") == pytest.approx(alt[-1], abs=20.0)


@pytest.mark.integration
def test_gear_term_is_absent_from_the_lanes_proxy():
    """PROXY A-W2.2-7 exposed. Gear handle down at t = 1 s (6 s transit), 10 s, against the gear-up run with
    the same draws: every M12 sensor output (hence every recorded lane and the DFCC's own air data) is bitwise
    identical, the gear effect exists only in the ADC outputs. There: at the end of the transit HP is off by
    the static-source increment gear_dk_ps qc / (rho g) (5 %) and the AoA by gear_dalpha_vane / (1 + ku)
    (local flow at the vane -> free-stream; 1e-4 rad, the last frame is 1/1440 short of full travel); once
    down and locked the AoA residual is gear_resid of that (1e-6 rad) and the HP residual 10-30 % (the
    position-error correction is evaluated at the
    gear-contaminated indicated Mach)."""
    n = 240 * 10
    up = FX.default_truth(n)
    down = dict(up)
    g = np.zeros(n, dtype=np.int64)
    g[240:] = 1
    down["pilot.gear_cmd"] = g
    _, _, mods = FX.build_avionics_chain(D, up)
    sens_ports = [f"sens.{p.name}" for p in mods["sens"].ports_out]
    o_up = run_chain(up, n, extra=sens_ports)
    o_dn = run_chain(down, n, extra=sens_ports)
    for p in sens_ports:
        assert np.array_equal(o_up[p], o_dn[p]), p  # the lanes do not see the undercarriage
    qc = val(o_up, "AD.PT.V", which="tru") - val(o_up, "AD.PS.V", which="tru")
    rho = FX.isa(3000.0)[2]
    k_end = 240 * 7 - 1  # last frame of the transit (gear position 6 s / 6 s)
    k_locked = 240 * 9
    d_hp = {k: val(o_dn, "AD.HP", k) - val(o_up, "AD.HP", k) for k in (k_end, k_locked)}
    d_aoa = {k: val(o_dn, "AD.AOA", k) - val(o_up, "AD.AOA", k) for k in (k_end, k_locked)}
    assert d_hp[k_end] == pytest.approx(-AP[A.P_GEAR_DK_PS] * qc / (rho * 9.80665), rel=0.05)
    assert d_aoa[k_end] == pytest.approx(AP[A.P_GEAR_DALPHA] / (1.0 + KU_AOA), abs=1e-4)
    assert d_aoa[k_locked] == pytest.approx(
        AP[A.P_GEAR_RESID] * AP[A.P_GEAR_DALPHA] / (1.0 + KU_AOA), abs=1e-6
    )
    assert 0.1 < d_hp[k_locked] / d_hp[k_end] < 0.3


@pytest.mark.integration
def test_lane_disagreement_clears_its_valid_bit_and_the_vote_rejects_it():
    """A +2,000 Pa bias on lane AD.PS.A (M12 health.sensor_bias input), 2 s: the PS bit of AD.VALID.A clears
    (|lane - vote| > thr_pressure), the other words stay all-valid, and HP moves by far less than the
    225 m the biased lane alone would imply (mid-value select)."""
    n = 480
    truth = FX.default_truth(n)
    _, _, mods = FX.build_avionics_chain(D, truth)
    cfg_s = mods["sens_cfg"]
    bias = np.zeros((n, cfg_s.n_ch))
    bias[:, list(cfg_s.channels).index("AD.PS.A")] = 2000.0
    o0 = run_chain(truth, n)
    o1 = run_chain(truth, n, bias=bias)
    assert np.all(o1[VALID_PORTS[0]][120:] == ALL_BITS & ~(1 << A.B_PS))
    for p in VALID_PORTS[1:]:
        assert np.all(o1[p][120:] == ALL_BITS)
    assert abs(val(o1, "AD.HP") - val(o0, "AD.HP")) < 5.0


@pytest.mark.integration
def test_dpa_dpb_bits_are_constant_proxy():
    """PROXY A-W2.2-10 exposed: AD.DPA / AD.DPB are not simulated, so no AD.DPA.V / AD.DPB.V channel is
    produced and the DPA / DPB bits of every AD.VALID word read valid even when every static-pressure lane is
    biased beyond the monitor threshold (their monitors have nothing to compare)."""
    assert not any(c.startswith(("AD.DPA", "AD.DPB")) for c in RECORDED.values())
    n = 480
    truth = FX.default_truth(n)
    _, _, mods = FX.build_avionics_chain(D, truth)
    cfg_s = mods["sens_cfg"]
    bias = np.zeros((n, cfg_s.n_ch))
    for j, c in enumerate("ABCD"):
        bias[:, list(cfg_s.channels).index(f"AD.PS.{c}")] = 1000.0 * (j + 1)
    o = run_chain(truth, n, bias=bias)
    for p in VALID_PORTS:
        w = o[p][120:]
        assert np.all((w >> A.B_DPA) & 1 == 1) and np.all((w >> A.B_DPB) & 1 == 1)
    assert any(np.any((o[p][120:] >> A.B_PS) & 1 == 0) for p in VALID_PORTS)  # PS monitors did trip


@pytest.mark.integration
def test_heater_state_drives_the_probe_and_the_adc_correction_together():
    """Since W2.2 M12's TAT probe reads its heater state from util.probe_heat, the flag the ADC corrects with:
    with the heaters off the digitised TAT lane loses the de-icing heater error (it reads colder by DHE, > 0
    and < the largest DHE table value) and the ADC applies no correction, so SAT stays as accurate as with the
    heaters on. (A failed heater with the flag on is the M11 heater-fault mode, G-PROBE-HEAT.) 12 s."""
    n = 240 * 12
    on = FX.default_truth(n)
    off = dict(on)
    off["util.probe_heat"] = np.zeros(n, dtype=np.int64)
    extra = ("acq_dfcc.lane_ad_tat", "acq_dfcc.lane_ad_tat_n")
    o_on, o_off = run_chain(on, n, extra=extra), run_chain(off, n, extra=extra)
    d_tat = last_sample(o_on, "acq_dfcc.lane_ad_tat") - last_sample(o_off, "acq_dfcc.lane_ad_tat")
    assert 0.0 < d_tat < float(np.max(CFG.adc_tables[9]))
    assert abs(err(o_off, "AD.SAT")) < 0.5 * d_tat and abs(err(o_on, "AD.SAT")) < 0.5 * d_tat


@pytest.mark.determinism
def test_chain_compiled_reference_block_and_step_are_bitwise_equal():
    """n = 240 frames (80 DFCC frames, a bank entry): the compiled chain equals the NumPy-reference chain and
    per-step execution equals block execution, bitwise, on every avionics output."""
    n = 240
    truth = FX.default_truth(n, bank_deg={(0.5, 3.0): 30.0})
    ref = run_chain(truth, n, compiled=False)
    for o in (run_chain(truth, n), run_chain(truth, n, mode="step")):
        for k in ref:
            assert np.array_equal(o[k], ref[k]), k
