"""AD-44 protocol with the real neighbours on main: M10/M11/M14 inside an M18 operations session, and M11's
``sensor_fault`` events into M12.

- M18's start configuration (``cfg.install`` per position) reaches M10, which tells M11 the installed serials;
  a scripted fault in M11 becomes ``truth.fault`` (+ ``truth.incident``) handled by M18's own handlers: M18
  records the fault against the serial it installed and opens the incident defect.
- A transient fault's ``truth.fault_clear`` deactivates it in M18.
- A usage-mode ``usage.sortie_summary`` to M10 runs the sortie in M14, whose download sends ``obs.event`` rows
  that M18 turns into a defect job (a PBIT failure forced by an LRU condition).
- A code masked by ``mx.monitoring`` is evaluated but not recorded.
- M11's ``sensor_fault`` events (catalogue and scripted) are accepted by ``SensorPhysics.on_event``.

TEST FIXTURES: the M18 configuration is the W1.8 "quiet" one (no periodic servicing or life limits) so only
the injected mechanisms act; one tail. Sample: one sortie or one scripted fault per test (deterministic)."""

from __future__ import annotations

import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_param_set
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.fork.builder import OpsOnlyBuilder
from phalanx.fork.session import OpsSession
from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels
from phalanx.health.protocol import plain_payload
from phalanx.maintenance.config import load_m18_config
from phalanx.maintenance.docstate import decode_doc
from phalanx.maintenance.world import FleetSpec, OpsTargets
from phalanx.monitoring import (
    MonitoringConfig,
    MonitoringModule,
    load_code_table,
    load_monitoring_params,
    lru_condition_payload,
)
from phalanx.monitoring.module import KIND_BIT
from phalanx.sensors.config import build_sensor_config
from phalanx.sensors.module import FAULT_STREAM, SENSOR_FAULT_EVENT, SensorPhysics

pytestmark = pytest.mark.integration
D = load_dictionary()
CODES = load_code_table(D, load_monitoring_params())
NS = 10**9
H = 3600 * NS
DAY = 24 * H
EPOCH = 1_790_035_200 * NS  # a whole second (M18 operations-layer times)
TAIL = "T01"


def quiet_cfg():  # TEST FIXTURE: the W1.8 quiet configuration (tests/unit/test_maintenance_world.py)
    cfg = load_m18_config()
    k = cfg.n_servicing
    big = 10**9
    cfg = cfg.with_values(srv_interval_fh_s=(big,) * k, srv_interval_s=(big,) * k)
    no_life = {
        c.code: {"life_fh": 0.0, "life_landings": 0.0, "life_streams": 0.0, "life_years": 0.0}
        for c in cfg.catalogue.classes
    }
    return cfg.with_catalogue_values(no_life)


def m10():
    cfg = HealthConfig(("IN20-0001",), sensor_bias_channels(D), "m11", monitor_target="m14", tail_no=TAIL)
    return HealthModule("m10", load_health_params(), config=cfg, identity={"tail": TAIL})


def m11(targets=None):
    cfg = FaultConfig(
        load_catalogue(),
        load_graph(),
        targets or {"health": "m10", "monitoring": "m14", "maintenance": "m18"},
        ("IN20-0001",),
        sensor_bias_channels(D),
        realise_physics_edges=True,
        stochastic=False,
        tail_no=TAIL,
    )
    return FaultInjector("m11", load_fault_params(), config=cfg, identity={"tail": TAIL})


def m14():
    cfg = MonitoringConfig.from_dictionary(
        D, CODES, ("IN20-0001",), regime="mature", tail_no=TAIL, epoch_utc_ns=EPOCH, obs_target="m18"
    )
    return MonitoringModule("m14", load_monitoring_params(), config=cfg, identity={"tail": TAIL})


@pytest.fixture
def ops():
    b = OpsOnlyBuilder(
        FleetSpec((TAIL,), ("SUL",), (0,)),
        EPOCH,
        m18_cfg=quiet_cfg(),
        targets=OpsTargets(m21="m21", sink="sink", health="m10", monitoring="m14"),
        extra=(m10, m11, m14),
    )
    s = OpsSession(b, 0x5EED)
    s.run_until(H)
    return s


def doc_event(t, kind, doc, target):
    """An operations event in the AD-48.1 plain-key encoding."""
    return Event(int(t), kind, target, plain_payload(doc), source="test")


def m18_doc(s, name):
    return decode_doc(s.world.states["m18"][name])


def serial_at(s, pos):
    cat = s.builder.m18_cfg.catalogue
    r = int(s.world.states["m18"]["tail_inst"][0, cat.pos(pos).index])
    return str(s.world.states["m18"]["ser_no"][r])


def test_start_configuration_reaches_m10_and_m11(ops):
    st10, st11 = ops.world.states["m10"], ops.world.states["m11"]
    from phalanx.health.module import POSITIONS

    for pos in ("ENG", "HYDP1", "FADEC", "TYR_L"):
        k = POSITIONS.index(pos)
        assert str(st10["pos_serial"][k]) == serial_at(ops, pos) == str(st11["pos_serial"][k])
    assert str(st10["eng_serial"][0]) == serial_at(ops, "ENG").replace("_", "-")


def test_truth_faults_drive_m18(ops):
    t = DAY
    ops.world = ops.system.inject(
        ops.world,
        [
            Event(t, "faults.inject", "m11", {"mode": "FM.ENG.FOD_BIRD", "severity": 1.0, "covered": True}),
            Event(t, "faults.inject", "m11", {"mode": "FM.ENG.AB_NO_LIGHT", "covered": True}),
        ],
    )
    ops.run_until(t + H)
    faults = m18_doc(ops, "doc_faults")
    bird, ab = f"{TAIL}:FM.ENG.FOD_BIRD#0", f"{TAIL}:FM.ENG.AB_NO_LIGHT#1"
    assert set(faults) == {bird, ab}
    assert faults[bird]["serial"] == serial_at(ops, "ENG") and faults[bird]["pos"] == "ENG"
    assert faults[bird]["symptom"] == "both" and faults[bird]["active"]  # covered, in-flight consequence
    assert faults[ab]["active"] is False  # transient: truth.fault_clear after its duration
    jobs = m18_doc(ops, "doc_jobs")["open"].values()
    assert any(j["tail"] == TAIL and j.get("source") == "incident" for j in jobs)  # bird-strike incident


def test_obs_events_reach_m18_at_download(ops):
    t0 = DAY
    ops.world = ops.system.inject(
        ops.world,
        [
            Event(t0, "monitor.lru_condition", "m14", lru_condition_payload("FCS-201", 12.0)),
            doc_event(
                t0 + H,
                "usage.sortie_summary",
                {
                    "sortie_id": f"{TAIL}-1",
                    "tail_no": TAIL,
                    "flight_hours": 1.0,
                    "engine_cycles": 2.5,
                    "engine_starts": 1,
                    "landings": 1,
                    "time_at_temp_s": 600.0,
                    "max_nz": 4.0,
                    "ab_time_s": 120.0,
                    "dust_index": 1.0,
                    "salt_index": 1.0,
                },
                "m10",
            ),
        ],
    )
    ops.run_until(t0 + 4 * H)
    st14 = ops.world.states["m14"]
    i = CODES.index("FCS-201")
    assert int(((st14["o_kind"] == KIND_BIT) & (st14["o_code"] == i)).sum()) == 1  # PBIT at power-up
    assert int(st14["obs_sent"]) == int(st14["o_kind"].size)  # downloaded
    jobs = list(m18_doc(ops, "doc_jobs")["open"].values())
    assert any(j.get("code") == "FCS-201" for j in jobs), [j.get("code") for j in jobs]


def test_masked_code_is_not_recorded():
    m = m14()
    sysm = System([m], [], rng=RngService(1, StreamRegistry()), identity=KeyPath.of(scenario="S1"))
    i = CODES.index("FCS-201")

    def sortie(w, k, extra):
        t = k * DAY
        ev = [
            *extra(t),
            Event(t + 1, "monitor.lru_condition", "m14", lru_condition_payload("FCS-201", 12.0)),
            Event(t + 2, "monitor.sortie_start", "m14", {"sortie_id": f"{TAIL}-{k}"}),
            Event(t + H, "monitor.sortie_end", "m14", {"flight_time_s": 3600.0}),
        ]
        w = sysm.inject(w, ev)
        return sysm.run(w, (t + H) // (NS // 240) + 2 - w.k)[0]

    def masked(t):
        return [doc_event(t, "mx.monitoring", {"tail": TAIL, "filter_codes_add": ["FCS-201"]}, "m14")]

    def unmasked(t):
        return [doc_event(t, "mx.monitoring", {"tail": TAIL, "filter_codes_remove": ["FCS-201"]}, "m14")]

    w = sortie(sysm.start(), 0, masked)
    st = w.states["m14"]
    assert int(st["x_mask"][i]) == 1 and not ((st["o_kind"] == KIND_BIT) & (st["o_code"] == i)).any()
    w = sortie(w, 1, unmasked)
    st = w.states["m14"]
    assert ((st["o_kind"] == KIND_BIT) & (st["o_code"] == i)).any()


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


def test_sensor_fault_events_drive_m12():
    rec = Recorder("sens")
    f = m11({"sensors": "sens"})
    sysm = System([f, rec], [], rng=RngService(2, StreamRegistry()), identity=KeyPath.of(scenario="S1"))
    orders = [
        Event(NS, "faults.inject", "m11", {"mode": "FM.SNS.PS3_VENTED", "severity": 1.0}),
        Event(NS, "faults.inject", "m11", {"mode": "FM.SNS.T5_OPEN"}),
        Event(
            NS,
            "faults.inject",
            "m11",
            {"mode": "FM.SNS.GENERIC", "key": "ENG.T5.HARNESS_B", "sensor_mode": "probe_short", "probe": 1.0},
        ),
    ]
    sysm.run(sysm.inject(sysm.start(), orders), 480)
    assert [e.kind for _, e in rec.log] == [SENSOR_FAULT_EVENT] * 3
    cfg = build_sensor_config(D)
    s12 = SensorPhysics("sens", load_param_set("M12", "constants"), cfg)
    s12.bind(
        RngService(3, StreamRegistry([FAULT_STREAM])).scope(KeyPath.of(scenario="S1", tail=TAIL, sortie="S"))
    )
    st = s12.init(s12.params, s12.keys)
    for t, ev in rec.log:
        st, out = s12.on_event(st, ev, t)
        assert out == []
    from phalanx.sensors import kernel as K

    modes = {
        cid: int(st["ci"][cfg.channel_index(cid), K.CI_MODE]) for cid in ("ENG.PS3.A", "ENG.T5.HARNESS_A")
    }
    assert modes == {"ENG.PS3.A": K.FM_BIAS, "ENG.T5.HARNESS_A": K.FM_OPEN}
    e = cfg.elements_of("ENG.T5.HARNESS_B")[1]
    assert int(st["ei"][e, K.EI_MODE]) == K.EMODE_SHORT
