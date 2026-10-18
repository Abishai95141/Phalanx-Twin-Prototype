"""AD-42 wiring of M10 and M11 into M12 (the real ``phalanx.sensors`` module, on main since W1.6).

- ``health.sensor_bias`` follows M12's index map (``SensorConfig.bias_index()``) entry by entry, in SI: fed to
  M12's bias port, each entry shifts its own channel's reading by exactly its value.
- M11's ``sensor_fault`` events, captured from a running injector, are accepted by ``SensorPhysics.on_event``
  and change the reading as the catalogue specifies (bias, bounded drift -> bias hold, open, probe open,
  slow response, intermittent rate and duty, clear back to the healthy reading bit for bit).

TEST FIXTURES (module boundary): constant truth inputs to M12; a ``Recorder`` in place of M12 inside the M11
system, whose captured events are then delivered to the real M12. Sample: one tail, scripted faults, ≤ 600 s
of 240 Hz frames per case (the intermittent case: ≈ 1,200 state changes, see its docstring).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.core.time import truth_step_times_ns
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_param_set
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.faults.sensor_faults import SENSOR_FAULT_KEYS
from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels
from phalanx.health import ports as health_ports
from phalanx.sensors import ports as sensor_ports
from phalanx.sensors.config import build_sensor_config, unit_group
from phalanx.sensors.module import BIAS_PORT, FAULT_STREAM, SENSOR_FAULT_EVENT, SensorPhysics

pytestmark = pytest.mark.integration
D = load_dictionary()
SEC = 10**9
DT = 1.0 / 240.0
CH = ("ENG.PS3.A", "ENG.PS3.B", "ENG.T5.HARNESS_A", "ENG.OIL_P", "AD.PT.A", "ENG.N2.A", "HYD.SYS1.P")
TRUTH = {  # TEST FIXTURE: constant truth at a cruise point (SI)
    "eng.n2": 1500.0,
    "eng.ps3": 2.0e6,
    "eng.t5": 900.0,
    "eng.w2": 60.0,
    "eng.oil_p": 3.0e5,
    "env.p_s": 5.0e4,
    "util.hyd_p": 2.07e7,
    "af.mach": 0.6,
    "env.t_s": 250.0,
}
CFG = build_sensor_config(D, channels=CH)
BC = sensor_bias_channels(D, CFG)


class Recorder(ModuleBase):  # TEST FIXTURE (module boundary): records the events addressed to M12
    version = "0.0.1"
    rate = None

    def __init__(self, id):
        super().__init__(id, ParamSet("rec", {}))
        self.log: list[tuple[int, Event]] = []

    def init(self, params, keys):
        return {}

    def on_event(self, state, event, t):
        self.log.append((int(t), event))
        return state, []


def m12(cfg=CFG) -> SensorPhysics:
    mod = SensorPhysics("sens", load_param_set("M12", "constants"), cfg)
    mod.bind(
        RngService(0x15, StreamRegistry([FAULT_STREAM])).scope(
            KeyPath.of(scenario="S1", tail="KH2011", sortie="KH2011-0")
        )
    )
    return mod


def inputs(m: SensorPhysics, n: int, bias: np.ndarray) -> dict[str, np.ndarray]:
    out = {s.port: np.full((n, *s.shape), TRUTH[s.signal]) for s in m.config.inputs}
    out[BIAS_PORT] = np.broadcast_to(bias, (n, m.config.n_ch)).copy()
    return out


def drive(m: SensorPhysics, events, n_frames: int, bias=None) -> dict[str, np.ndarray]:
    """Run M12 over ``n_frames`` truth frames, delivering each captured (t, event) before the first frame
    starting at or after t. Returns the concatenated outputs."""
    bias = np.zeros(m.config.n_ch) if bias is None else np.asarray(bias, float)
    st = m.init(m.params, m.keys)
    times = truth_step_times_ns(np.arange(n_frames))
    pending = sorted(events, key=lambda te: te[0])
    k, outs = 0, []
    while k < n_frames:
        while pending and pending[0][0] <= times[k]:
            t, ev = pending.pop(0)
            st, extra = m.on_event(st, ev, int(t))
            assert extra == []
        nxt = n_frames if not pending else int(np.searchsorted(times, pending[0][0]))
        nxt = max(k + 1, min(n_frames, nxt))
        st, out = m.step_block(st, inputs(m, nxt - k, bias), times[k:nxt], DT)
        outs.append(out)
        k = nxt
    return {key: np.concatenate([o[key] for o in outs]) for key in outs[0]}


def reading(m: SensorPhysics, out, cid: str) -> np.ndarray:
    c = m.config.channel_index(cid)
    g = unit_group(m.config.si_units[c])
    return out[f"s_{g}"][:, m.config.groups[g].index(c)]


def m11_events(orders, until_s: float, *, bias_channels=BC) -> list[tuple[int, Event]]:
    """Run M11 with scripted orders; return the events it sent to M12 (captured at the module boundary)."""
    rec = Recorder("sens")
    cfg = FaultConfig(
        load_catalogue(),
        load_graph(),
        {"sensors": "sens"},
        ("IN20-0001",),
        bias_channels,
        realise_physics_edges=False,
        stochastic=False,
        strict=True,
    )
    f = FaultInjector("faults", load_fault_params(), config=cfg)
    sysm = System(
        [f, rec],
        [],
        rng=RngService(0xFA17, StreamRegistry()),
        identity=KeyPath.of(scenario="S1", tail="KH2011"),
    )
    w = sysm.inject(sysm.start(), orders)
    sysm.run(w, int(until_s * 240) + 2)
    for _, ev in rec.log:
        assert ev.kind == SENSOR_FAULT_EVENT and ev.target == "sens"
        assert set(ev.payload) == set(SENSOR_FAULT_KEYS)  # the event canonicalises key order
    return rec.log


def inject(t_s: float, mode: str, **kw) -> Event:
    return Event(round(t_s * SEC), "faults.inject", "faults", {"mode": mode, **kw})


def clear(t_s: float, instance: int) -> Event:
    return Event(round(t_s * SEC), "faults.clear", "faults", {"instance": instance})


def span(cid: str) -> float:
    return next(b for b in BC if b.channel_id == cid).span_si


# ---------------------------------------------------------------------------------------------- M10 -> M12
def test_health_sensor_bias_port_matches_m12_bias_port():
    h_out = {p.name: p for p in health_ports.ports(1, D)[1]}
    s_in = {p.name: p for p in sensor_ports.ports(1)[0]}
    assert h_out["sensor_bias"].shape == s_in[BIAS_PORT].shape == (build_sensor_config(D).n_ch,)
    assert sensor_ports.ports(1)[2][BIAS_PORT] == "health.sensor_bias"


def test_m10_bias_vector_shifts_each_m12_channel_by_its_own_entry():
    h = HealthModule("health", load_health_params(), config=HealthConfig(("IN20-0001",), BC, None))
    sysm = System(
        [h], [], rng=RngService(0x10, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail="KH2011")
    )
    bias = np.asarray(sysm.start().held["health.sensor_bias"], float)
    assert bias.shape == (CFG.n_ch,) and np.all(bias != 0.0)
    m = m12()
    base = drive(m, [], 480)
    biased = drive(m12(), [], 480, bias)
    for c, cid in enumerate(CFG.bias_index()):
        d = reading(m, biased, cid) - reading(m, base, cid)
        np.testing.assert_allclose(d, bias[c], rtol=1e-9, atol=1e-9 * span(cid), err_msg=cid)


# ---------------------------------------------------------------------------------------------- M11 -> M12
def test_every_catalogue_sensor_fault_is_accepted_by_m12_and_clears():
    """Each catalogue mode and graph node with a sensor effect, injected and cleared, on the full M12 map."""
    full = build_sensor_config(D)
    bc = sensor_bias_channels(D, full)
    modes = [m for m in load_catalogue().values() if any(e.target == "sensors" for e in m.effects)]
    modes = [m for m in modes if not any(e.fields.get("channel") == "*" for e in m.effects)]
    orders = []
    for j, m in enumerate(modes):
        orders += [inject(1.0 + j, m.id, severity=1.0), clear(2.0 + len(modes) + j, j)]
    log = m11_events(orders, 3.0 + 2 * len(modes), bias_channels=bc)
    n_eff = sum(sum(e.target == "sensors" for e in m.effects) for m in modes)
    assert len(log) == 2 * n_eff  # one onset and one clear per effect (no unbounded drift: hold below)
    mod = m12(full)
    st = mod.init(mod.params, mod.keys)
    for t, ev in log:
        st, _ = mod.on_event(st, ev, t)
    assert np.all(st["ci"][:, 0] == 0)  # every channel back to no fault (CI_MODE column)


def test_bias_open_and_clear_change_the_reading_as_specified():
    log = m11_events(
        [
            inject(1.0, "FM.SNS.PS3_VENTED", severity=0.5),  # instance 0: bias -0.6 x 0.5 of span
            inject(1.0, "FM.SNS.T5_OPEN"),  # instance 1: harness open
            clear(2.0, 0),
            clear(2.0, 1),
        ],
        3.0,
    )
    m = m12()
    base, out = drive(m, [], 960), drive(m12(), log, 960)
    k1, k2 = 240, 480  # frames at 1 s and 2 s
    ps3 = reading(m, out, "ENG.PS3.A") - reading(m, base, "ENG.PS3.A")
    np.testing.assert_allclose(ps3[k1 + 1 : k2], -0.3 * span("ENG.PS3.A"), rtol=1e-12)
    t5 = reading(m, out, "ENG.T5.HARNESS_A")
    lo = next(b for b in BC if b.channel_id == "ENG.T5.HARNESS_A").rails_si[0]
    assert np.allclose(t5[k1 + 1 : k2], lo, rtol=0.0, atol=1e-9)  # bottom of the range
    for cid in CH:  # after the clear: the healthy reading, bit for bit; before the onset too
        r, b = reading(m, out, cid), reading(m, base, cid)
        assert np.array_equal(r[: k1 - 1], b[: k1 - 1]) and np.array_equal(r[k2 + 1 :], b[k2 + 1 :]), cid


def test_bounded_drift_becomes_a_bias_hold_at_its_bound():
    """FM.SNS.PRESSURE_HIGH: drift 0.001 of span per second bounded at 0.3 x severity of span (A-W1.5-25)."""
    log = m11_events([inject(1.0, "FM.SNS.PRESSURE_HIGH", severity=1.0)], 400.0)
    assert [str(e.payload["mode"]) for _, e in log] == ["drift", "bias"]
    (t0, e0), (t1, e1) = log
    s = span("ENG.PS3.B")
    assert float(e0.payload["value"]) == pytest.approx(0.001 * s)
    assert float(e1.payload["value"]) == pytest.approx(0.3 * s)
    assert (t1 - t0) / SEC == pytest.approx(300.0, abs=1e-6)
    m = m12()
    n = 240 * 400
    d = reading(m, drive(m, log, n), "ENG.PS3.B") - reading(m, drive(m12(), [], n), "ENG.PS3.B")
    t = (np.arange(n) + 1) * DT  # frame-end times
    mid = (t > 2.0) & (t < 300.0)
    np.testing.assert_allclose(d[mid], 0.001 * s * (t[mid] - t0 / SEC), rtol=1e-6, atol=1e-6 * s)
    assert np.all(np.abs(d) <= 0.3 * s * (1 + 1e-9))
    np.testing.assert_allclose(d[t > 302.0], 0.3 * s, rtol=1e-12)


def test_probe_open_drops_one_probe_from_the_harness_average():
    log = m11_events(
        [inject(1.0, "FM.SNS.GENERIC", key="ENG.T5.HARNESS_A", sensor_mode="probe_open", probe=2.0)], 2.0
    )
    assert int(log[0][1].payload["probe"]) == 2
    m = m12()
    out = drive(m, log, 720)
    r = reading(m, out, "ENG.T5.HARNESS_A")
    assert r[-1] == pytest.approx(TRUTH["eng.t5"], abs=0.5)  # three probes still read the (uniform) T5


def test_slow_response_factor_lengthens_the_lag():
    """Slow response (factor 5, A-W1.5-25) on ENG.PS3.A, then a truth step: the faulted channel lags more."""
    log = m11_events([inject(0.5, "FM.SNS.GENERIC", key="ENG.PS3.A", sensor_mode="slow")], 1.0)
    assert float(log[0][1].payload["value"]) == pytest.approx(5.0)
    m = m12()
    st_f, st_h = m.init(m.params, m.keys), m.init(m.params, m.keys)
    st_f, _ = m.on_event(st_f, log[0][1], log[0][0])
    n = 240
    step = inputs(m, n, np.zeros(CFG.n_ch))
    step["eng_ps3"] = np.full((n, 1), 2.5e6)
    times = truth_step_times_ns(np.arange(240, 240 + n))
    for st in (st_f, st_h):  # settle at the old point first
        st.update(
            m.step_block(st, inputs(m, 240, np.zeros(CFG.n_ch)), truth_step_times_ns(np.arange(240)), DT)[0]
        )
    _, of = m.step_block(st_f, step, times, DT)
    _, oh = m.step_block(st_h, step, times, DT)
    gap_f = 2.5e6 - reading(m, of, "ENG.PS3.A")
    gap_h = 2.5e6 - reading(m, oh, "ENG.PS3.A")
    assert np.all(gap_f[5:60] > gap_h[5:60])


def test_intermittent_dropout_matches_rate_and_duty():
    """Generic intermittent on AD.PT.A with rate 2 /s and duty 0.2 for 600 s (≈ 1,200 state changes): the
    dropout fraction is 0.2 ± 0.05 (≈ 4 standard errors of a renewal process with ≈ 600 open episodes) and
    dropouts read the bottom of the range."""
    log = m11_events(
        [inject(0.0, "FM.SNS.GENERIC", key="AD.PT.A", sensor_mode="intermittent", rate=2.0, duty=0.2)], 1.0
    )
    p = log[0][1].payload
    assert float(p["rate"]) == 2.0 and float(p["duty"]) == 0.2
    m = m12()
    n = 240 * 600
    r = reading(m, drive(m, log, n), "AD.PT.A")
    lo = next(b for b in BC if b.channel_id == "AD.PT.A").rails_si[0]
    drop = np.isclose(r, lo, rtol=0.0, atol=1e-6)
    assert abs(drop.mean() - 0.2) < 0.05
    assert 600 < np.count_nonzero(np.diff(drop.astype(int))) < 1800
