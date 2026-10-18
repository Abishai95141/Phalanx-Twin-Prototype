"""M12 sensor-fault modes from M11 events (W1_interfaces §2 M11; architecture §7: faults act at s_inst).

Each mode is checked against its definition; stochastic modes (intermittent, spikes) against their rate with a
stated n. Faults are state perturbations only (I6): the generation path does not change, other channels are
bit-identical, and truth labels never see the fault.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import truth_step_times_ns
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_param_set
from phalanx.sensors.config import build_sensor_config, unit_group
from phalanx.sensors.module import BIAS_PORT, FAULT_STREAM, SENSOR_FAULT_EVENT, SensorPhysics

pytestmark = pytest.mark.unit
DT = 1.0 / 240.0
CH = ("ENG.N2.A", "ENG.N2.B", "ENG.OIL_P", "ENG.PS3.A")


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


@pytest.fixture
def m(d):
    cfg = build_sensor_config(d, channels=CH)
    mod = SensorPhysics("sens", load_param_set("M12", "constants"), cfg)
    mod.bind(
        RngService(0x16, StreamRegistry([FAULT_STREAM])).scope(
            KeyPath.of(scenario="T", tail="T1", sortie="S1")
        )
    )
    return mod


def ramp_inputs(m, k0, L):
    t = (np.arange(k0, k0 + L) + 1) * DT
    vals = {"eng.n2": 1700.0 + 10.0 * t, "eng.oil_p": 3e5 + 1e3 * t, "eng.ps3": 2e6}
    out = {}
    for s in m.config.inputs:
        v = np.broadcast_to(np.asarray(vals[s.signal], dtype=np.float64), (L,))
        out[s.port] = v.reshape(L, 1) * np.ones((L, *s.shape))
    out[BIAS_PORT] = np.zeros((L, m.config.n_ch))
    return out


def run(m, st, k0, L):
    return m.step_block(st, ramp_inputs(m, k0, L), truth_step_times_ns(np.arange(k0, k0 + L)), DT)


def val(m, out, cid, kind="s"):
    c = m.config.channel_index(cid)
    g = unit_group(m.config.si_units[c])
    return out[f"{kind}_{g}"][:, m.config.groups[g].index(c)]


def inject(m, st, k, payload):
    t = int(truth_step_times_ns(np.array([k]))[0])
    st, ev = m.on_event(st, Event(t, SENSOR_FAULT_EVENT, "sens", payload), t)
    assert ev == []
    return st


def baseline(m, L=480):
    st = m.init(m.params, m.keys)
    st, _ = run(m, st, 0, 240)
    st, b = run(m, st, 240, L)
    return b


def faulted(m, payload, L=480):
    st = m.init(m.params, m.keys)
    st, _ = run(m, st, 0, 240)
    st = inject(m, st, 240, payload)
    st, b = run(m, st, 240, L)
    return b


def assert_others_untouched(m, base, out, cid):
    for c in CH:
        if c != cid:
            np.testing.assert_array_equal(val(m, out, c), val(m, base, c))
        np.testing.assert_array_equal(val(m, out, c, "x"), val(m, base, c, "x"))


def test_bias_step(m):
    base, out = baseline(m), faulted(m, {"channel": "ENG.N2.B", "mode": "bias", "value": 3.0})
    np.testing.assert_allclose(val(m, out, "ENG.N2.B") - val(m, base, "ENG.N2.B"), 3.0, rtol=1e-12)
    assert_others_untouched(m, base, out, "ENG.N2.B")


def test_drift_grows_linearly_from_onset(m):
    base, out = baseline(m), faulted(m, {"channel": "ENG.N2.B", "mode": "drift", "value": 0.5})
    t_since = (np.arange(240, 720) + 1) * DT - 240 * DT
    np.testing.assert_allclose(
        val(m, out, "ENG.N2.B") - val(m, base, "ENG.N2.B"), 0.5 * t_since, rtol=1e-6, atol=1e-9
    )
    assert_others_untouched(m, base, out, "ENG.N2.B")


def test_stuck_holds_the_value_at_onset(m):
    st = m.init(m.params, m.keys)
    st, first = run(m, st, 0, 240)
    st = inject(m, st, 240, {"channel": "ENG.OIL_P", "mode": "stuck"})
    _, out = run(m, st, 240, 480)
    base = baseline(m)
    assert np.all(val(m, out, "ENG.OIL_P") == val(m, first, "ENG.OIL_P")[-1])
    assert np.ptp(val(m, base, "ENG.OIL_P")) > 0
    assert_others_untouched(m, base, out, "ENG.OIL_P")


def test_open_reads_bottom_of_scale_and_short_reads_value(d, m):
    base = baseline(m)
    out = faulted(m, {"channel": "ENG.PS3.A", "mode": "open"})
    lo = d.eu_to_si("ENG.PS3.A", d.channel("ENG.PS3.A")["range"]["min"])
    assert np.all(val(m, out, "ENG.PS3.A") == lo)
    out = faulted(m, {"channel": "ENG.PS3.A", "mode": "short", "value": 1.0e5})
    assert np.all(val(m, out, "ENG.PS3.A") == 1.0e5)
    assert_others_untouched(m, base, out, "ENG.PS3.A")


def test_intermittent_duty_matches_payload(d, m):
    """Two-state Markov open/normal chain: switching rate 4/s, duty 0.3. Over n = 24,000 frames (100 s, ~400
    switches) the open fraction is 0.3 +- 0.08 (the CI half-width of a 400-switch alternating renewal)."""
    out = faulted(m, {"channel": "ENG.PS3.A", "mode": "intermittent", "rate": 4.0, "duty": 0.3}, 24000)
    lo = d.eu_to_si("ENG.PS3.A", d.channel("ENG.PS3.A")["range"]["min"])
    is_open = val(m, out, "ENG.PS3.A") == lo
    assert abs(is_open.mean() - 0.3) < 0.08
    switches = int(np.sum(np.diff(is_open.astype(int)) != 0))
    assert 300 < switches < 500


def test_spikes_occur_at_the_payload_rate(m):
    """Poisson spikes, 1 per second, amplitude 50 kPa: n = 24,000 frames gives 100 expected, 3-sigma band
    70-130; each spike is exactly the amplitude on top of the clean reading."""
    base = baseline(m, 24000)
    out = faulted(m, {"channel": "ENG.OIL_P", "mode": "spikes", "value": 5.0e4, "rate": 1.0}, 24000)
    diff = val(m, out, "ENG.OIL_P") - val(m, base, "ENG.OIL_P")
    hits = np.flatnonzero(diff != 0)
    assert 70 <= hits.size <= 130
    np.testing.assert_allclose(diff[hits], 5.0e4)


def test_slow_response_multiplies_the_time_constant(m):
    """Slow response x4 on the oil-pressure transmitter (tau 1 s -> 4 s): after a ramp the steady lag
    r * tau grows four-fold (n = 7,200 frames to settle)."""
    base, out = baseline(m, 7200), faulted(m, {"channel": "ENG.OIL_P", "mode": "slow", "value": 4.0}, 7200)
    lag0 = (val(m, base, "ENG.OIL_P", "x") - val(m, base, "ENG.OIL_P"))[-1]
    lag1 = (val(m, out, "ENG.OIL_P", "x") - val(m, out, "ENG.OIL_P"))[-1]
    assert lag0 == pytest.approx(1e3 * 1.0, rel=1e-3)
    assert lag1 == pytest.approx(4 * lag0, rel=1e-2)


def test_clear_restores_normal_operation(m):
    st = m.init(m.params, m.keys)
    st, _ = run(m, st, 0, 240)
    st = inject(m, st, 240, {"channel": "ENG.N2.A", "mode": "bias", "value": 5.0})
    st = inject(m, st, 240, {"channel": "ENG.N2.A", "mode": "clear"})
    st, out = run(m, st, 240, 10)
    np.testing.assert_array_equal(val(m, out, "ENG.N2.A"), val(m, out, "ENG.N2.B"))


@pytest.mark.parametrize(
    "payload",
    [
        {"channel": "ENG.N2.A"},
        {"channel": "NOPE", "mode": "bias", "value": 1.0},
        {"channel": "ENG.N2.A", "mode": "melt"},
        {"channel": "ENG.N2.A", "mode": "slow", "value": 0.5},
        {"channel": "ENG.N2.A", "mode": "intermittent", "rate": 1.0, "duty": 1.5},
        {"channel": "ENG.N2.A", "mode": "spikes", "value": 1.0},
        {"channel": "ENG.N2.A", "mode": "probe_open", "probe": 2},
    ],
)
def test_invalid_payloads_are_rejected(m, payload):
    st = m.init(m.params, m.keys)
    with pytest.raises((ContractError, KeyError)):
        m.on_event(st, Event(0, SENSOR_FAULT_EVENT, "sens", payload), 0)


def test_stochastic_fault_draws_are_keyed_and_block_independent(m):
    """Fault draws are indexed by absolute frame: one block of 480 frames equals 480 single-frame steps."""
    st = m.init(m.params, m.keys)
    st, _ = run(m, st, 0, 240)
    st = inject(m, st, 240, {"channel": "ENG.OIL_P", "mode": "spikes", "value": 1e4, "rate": 20.0})
    _, block = run(m, st, 240, 480)
    s2 = st
    per = []
    for k in range(240, 720):
        s2, o = run(m, s2, k, 1)
        per.append(val(m, o, "ENG.OIL_P")[0])
    np.testing.assert_array_equal(np.array(per), val(m, block, "ENG.OIL_P"))
