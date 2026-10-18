"""W2.2 phase B part 1, item 2: M12 sensors on M09 truth that had none (A-W2.2-16), and the TAT heater state.

- BRK.PRESS.L/R read ``util.brake_p`` (gauge) through the hydraulic pressure transducer class;
- HYD.SYS1/2.LEVEL.LEVEL read ``util.hyd_res_level`` (the bootstrap-reservoir piston position);
- ENG.FUEL_INLET_T reads ``util.fuel_inlet_t`` through an immersion RTD;
- the ECS channels read the M09 points of ``util.ecs_t`` / ``util.ecs_p`` (absolute) through duct and
  compartment RTDs and absolute pressure transducers;
- the TAT probe's de-icing heater error follows ``util.probe_heat`` (it was a constant "on").

Sample: constant and step truth at 240 Hz, n = 1 deterministic run per check (10 frames for the identities,
up to 24,000 frames = 100 s for the slowest step response).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.acquisition import kernel as AK
from phalanx.acquisition.config import acquisition_domain_lru, build_acquisition_config
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import truth_step_times_ns
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_param_set, load_params
from phalanx.sensors.config import build_sensor_config, unit_group
from phalanx.sensors.module import BIAS_PORT, FAULT_STREAM, SensorPhysics
from phalanx.utilities.layout import ECS_POINTS

pytestmark = pytest.mark.integration
D = load_dictionary()
M12 = load_params("M12")
DT = 1.0 / 240.0
#: channel -> (truth signal, index, class): the item-2 channel map entries
ITEM2 = {
    "BRK.PRESS.L": ("util.brake_p", 0, "hyd_pressure"),
    "BRK.PRESS.R": ("util.brake_p", 1, "hyd_pressure"),
    "HYD.SYS1.LEVEL.LEVEL": ("util.hyd_res_level", 0, "reservoir_level"),
    "HYD.SYS2.LEVEL.LEVEL": ("util.hyd_res_level", 1, "reservoir_level"),
    "ENG.FUEL_INLET_T": ("util.fuel_inlet_t", 0, "fuel_inlet_rtd"),
    "ECS.BLEED_T.PHX_IN": ("util.ecs_t", ECS_POINTS.index("BLEED"), "ecs_duct_rtd"),
    "ECS.BLEED_T.PHX_OUT": ("util.ecs_t", ECS_POINTS.index("PHX_OUT"), "ecs_duct_rtd"),
    "ECS.COCKPIT_T.ACM_OUT": ("util.ecs_t", ECS_POINTS.index("TURBINE_OUT"), "ecs_duct_rtd"),
    "ECS.COCKPIT_T.COCKPIT": ("util.ecs_t", ECS_POINTS.index("COCKPIT"), "ecs_compartment_rtd"),
    "ECS.AVIONICS_T.TEMP": ("util.ecs_t", ECS_POINTS.index("AVIONICS_BAY"), "ecs_compartment_rtd"),
    "ECS.BLEED_P": ("util.ecs_p", ECS_POINTS.index("BLEED"), "ecs_pressure"),
    "ECS.CABIN_P.PRESS": ("util.ecs_p", ECS_POINTS.index("COCKPIT"), "ecs_pressure"),
}
#: TEST FIXTURE truth: values inside each channel's range (SI)
TRUTH = {
    "util.brake_p": np.array([4.1e6, 3.7e6]),
    "util.hyd_res_level": np.array([0.83, 0.79]),
    "util.fuel_inlet_t": np.array([301.4]),
    "util.ecs_t": np.array([620.0, 420.0, 268.0, 296.0, 305.0]),
    "util.ecs_p": np.array([4.2e5, 3.1e5, 1.6e5, 7.0e4, 7.2e4]),
}


def make(*channels):
    cfg = build_sensor_config(D, channels=channels)
    m = SensorPhysics("sens", load_param_set("M12", "constants"), cfg)
    m.bind(
        RngService(0x22, StreamRegistry([FAULT_STREAM])).scope(
            KeyPath.of(scenario="W22I2", tail="T", sortie="S")
        )
    )
    return m


def run(m, values, L):
    st = m.init(m.params, m.keys)
    inputs = {}
    for s in m.config.inputs:
        v = np.asarray(values.get(s.signal, 0.0), dtype=np.float64)
        inputs[s.port] = np.broadcast_to(
            v.reshape((L, *s.shape)) if v.size == L * s.size else v, (L, *s.shape)
        )
    inputs[BIAS_PORT] = np.zeros((L, m.config.n_ch))
    _, out = m.step_block(st, inputs, truth_step_times_ns(np.arange(L, dtype=np.int64)), DT)
    return out


def chan(m, out, cid, kind="s"):
    c = m.config.channel_index(cid)
    g = unit_group(m.config.si_units[c])
    return out[f"{kind}_{g}"][..., m.config.groups[g].index(c)]


def test_the_channel_map_entries():
    cfg = build_sensor_config(D)
    for cid, (sig, idx, cls) in ITEM2.items():
        c = cfg.channel_index(cid)
        assert cfg.classes[c] == cls, cid
        e = cfg.elements_of(cid)[0]
        (inp,) = [s for s in cfg.inputs if s.signal == sig]
        assert int(cfg.el_i[e, 2]) == inp.col0 + idx, cid  # IE_C0: the M09 point the channel reads
    assert cfg.n_ch == 145  # 132 (W1.6) + ENG.AB_LIT + the 12 item-2 sensors


def test_each_channel_reads_its_m09_truth():
    """Constant truth (steady start, A-W1.6-2): every reading equals its truth point exactly, in SI, and the
    truth label is the same point (no bias)."""
    m = make(*ITEM2)
    out = run(m, TRUTH, 10)
    for cid, (sig, idx, _cls) in ITEM2.items():
        want = TRUTH[sig][idx]
        assert np.array_equal(chan(m, out, cid), np.full(10, want)), cid
        assert np.array_equal(chan(m, out, cid, "x"), np.full(10, want)), cid
        lo, hi = (D.eu_to_si(cid, D.channel(cid)["range"][k]) for k in ("min", "max"))
        assert lo <= want <= hi, cid


@pytest.mark.parametrize(
    ("cid", "pset"),
    [
        ("BRK.PRESS.L", "hyd_pressure"),
        ("ENG.FUEL_INLET_T", "fuel_inlet_rtd"),
        ("ECS.BLEED_T.PHX_IN", "ecs_duct_rtd"),
        ("ECS.COCKPIT_T.COCKPIT", "ecs_compartment_rtd"),
        ("ECS.BLEED_P", "ecs_pressure"),
    ],
)
def test_first_order_response_has_the_class_time_constant(cid, pset):
    """Step of the truth point: the 63.2 % crossing is tau + DT/2 after the ramp starts (to a frame); the
    reservoir level transmitter has no lag."""
    tau = float(M12[pset].value("tau"))
    sig, idx, _ = ITEM2[cid]
    L = int(3 * tau / DT) + 20
    lo = TRUTH[sig].copy()
    hi = lo.copy()
    hi[idx] = lo[idx] * 1.1
    v = np.tile(lo, (L, 1))
    v[1:] = hi
    m = make(cid)
    y = chan(m, run(m, {sig: v}, L), cid)[1:]
    f = (y - lo[idx]) / (hi[idx] - lo[idx])
    j = int(np.argmax(f >= 1 - np.exp(-1)))
    t = (j + (1 - np.exp(-1) - f[j - 1]) / (f[j] - f[j - 1])) * DT - 0.5 * DT
    assert t == pytest.approx(tau, abs=DT)
    m = make("HYD.SYS1.LEVEL.LEVEL")
    v = np.tile(TRUTH["util.hyd_res_level"], (4, 1))
    v[2:, 0] = 0.5
    assert np.array_equal(chan(m, run(m, {"util.hyd_res_level": v}, 4), "HYD.SYS1.LEVEL.LEVEL"), v[:, 0])


def test_tat_heater_error_follows_util_probe_heat():
    """The de-icing heater error (DHE) is present while util.probe_heat is 1 and absent while it is 0, and a
    switch mid-run moves the reading through the probe lag (n = 2 x 4,800 frames)."""
    air = {"env.p_s": 50000.0, "env.t_s": 250.0, "af.mach": 0.8, "env.rho": 0.7, "af.tas": 250.0}
    ps = M12["tat_probe"]
    r = np.interp(0.8, np.asarray(ps.value("rec_mach")), np.asarray(ps.value("recovery")))
    dhe = np.interp(0.8 * 0.7 / 1.225, np.asarray(ps.value("dhe_z")), np.asarray(ps.value("dhe")))
    rec = 250.0 * (1 + 0.2 * r * 0.64)
    m = make("AD.TAT")
    on = chan(m, run(m, {**air, "util.probe_heat": 1.0}, 4800), "AD.TAT")
    off = chan(m, run(m, {**air, "util.probe_heat": 0.0}, 4800), "AD.TAT")
    assert on[-1] == pytest.approx(rec + dhe, abs=1e-9) and off[-1] == pytest.approx(rec, abs=1e-9)
    heat = np.ones(4800)
    heat[2400:] = 0.0
    sw = chan(m, run(m, {**air, "util.probe_heat": heat}, 4800), "AD.TAT")
    assert sw[2399] == pytest.approx(rec + dhe, abs=1e-9) and sw[-1] == pytest.approx(
        rec, abs=1e-3
    )  # 10 s, ~7 tau
    assert rec < sw[2401] < rec + dhe  # through the probe lag, not a jump


def test_m13_acquires_them_on_their_lru_clocks():
    """BHEEM-EU (brakes, reservoir level), ECFM-C (ECS) and FADEC (fuel inlet) acquisition with the default
    noise inside its ceiling; analog slip on the BHEEM-EU and ECFM-C converters (A-W1.6-24), none on the
    FADEC's."""
    sens = build_sensor_config(D)
    acq = build_acquisition_config(D, tuple(ITEM2), sensor_channels=sens.channels)
    want = {"BRK": "BHEEM_EU", "HYD": "BHEEM_EU", "ECS": "ECFM_C", "ENG": "FADEC"}
    for c, cid in enumerate(acq.channels):
        lru = acq.domains[int(acq.domain_of[c])].lru
        assert lru == acquisition_domain_lru(D, cid) == want[cid.split(".")[0]], cid
        assert acq.sigma_eff_eu[c] <= acq.ceiling_eu[c] and int(acq.Q[c, AK.AQ_MODE]) == AK.MODE_POINT
        assert int(acq.Q[c, AK.AQ_SLIP]) == int(lru != "FADEC"), cid
