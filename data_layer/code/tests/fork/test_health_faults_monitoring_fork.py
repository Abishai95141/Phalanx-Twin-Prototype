"""Acceptance A7 (I1, I2, I8): M10 + M11 + M14 together are deterministic; a snapshot taken mid-sortie (BIT
latches, persistence counters, AR states, open exceedances, the latent-defect queue and the M10 hidden states
in flight) restores and continues bit-for-bit; forks from that snapshot share every exogenous draw (CRN audit)
even when one branch receives maintenance orders.

Sample: 1 tail, 4 sorties of 10 min with CIR chunks (10 Hz) and stochastic faults at raised rates, so faults,
BIT records, exceedances and counters all occur; snapshot inside sortie 2 between two CIR chunks."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.rng import DrawLedger, KeyPath, RngService, StreamRegistry, crn_audit
from phalanx.core.scheduler import System
from phalanx.core.snapshot import read_snapshot, restore, snapshot
from phalanx.dictionary import load_dictionary
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.health import HealthConfig, HealthModule, SortieUsage, load_health_params, sensor_bias_channels
from phalanx.monitoring import MonitoringConfig, MonitoringModule, load_code_table, load_monitoring_params

D = load_dictionary()
BC = sensor_bias_channels(D)
MP = load_monitoring_params()
CODES = load_code_table(D, MP)
SEC = 10**9
DAY = 86_400 * SEC
N_S = 4
DUR = 600.0


class Sink(ModuleBase):  # TEST FIXTURE: stands in for M07/M09/M12 at the module boundary (ignores its events)
    version = "0.0.1"
    rate = None

    def __init__(self, id):
        super().__init__(id, ParamSet("sink", {}))

    def init(self, params, keys):
        return {}

    def on_event(self, state, event, t):
        return state, []


def build(ledger=None):
    h = HealthModule("health", load_health_params(), config=HealthConfig(("IN20-0001",), BC, "faults"))
    fp = load_fault_params().replace(
        lru_failure_rate=6.0 / 3600.0, bird_strike_rate=6.0 / 3600.0, sensor_fault_rate=5e-2 / 3600.0
    )
    sinks = [Sink(n) for n in ("engine", "fadec", "utilities", "fcs", "airframe", "sensors")]
    f = FaultInjector(
        "faults",
        fp,
        config=FaultConfig(
            load_catalogue(),
            load_graph(),
            {"health": "health", "monitoring": "monitoring", **{s.id: s.id for s in sinks}},
            ("IN20-0001",),
            BC,
            realise_physics_edges=True,
            stochastic=True,
        ),
    )
    m = MonitoringModule(
        "monitoring", MP, config=MonitoringConfig.from_dictionary(D, CODES, ("IN20-0001",), regime="immature")
    )
    return System(
        [h, f, m, *sinks],
        [],
        rng=RngService(0xF0F0_1234, StreamRegistry(), ledger=ledger),
        identity=KeyPath.of(scenario="S1", tail="KH2011"),
    )


def chunk(k, part, cfg_channels):
    t = np.arange(0.0, DUR, 0.1)
    n2 = np.interp(t, [0, 30, 60, 300, 330, 560, 590, DUR], [0, 65, 97, 97, 70, 70, 0, 0])
    sel = slice(0, t.size // 2) if part == 0 else slice(t.size // 2, t.size)
    series = {
        "ENG.N2.V": n2,
        "ENG.PS3.V": n2 / 100 * 380,
        "ENG.T5": 15 + n2 / 100 * 780 + 60.0 * (np.abs(t - 200) < 3),
        "ENG.PLA.V": np.where(n2 > 96, 100.0, 40.0),
        "LG.WOW": np.where((t > 70) & (t < 550), 0.0, 1.0),
    }
    ch, tt, vv = [], [], []
    for name, v in series.items():
        ch.append(np.full(t[sel].size, cfg_channels.index(name)))
        tt.append(k * DAY + (t[sel] * 1e9).astype(np.int64))
        vv.append(v[sel])
    ch, tt, vv = np.concatenate(ch), np.concatenate(tt), np.concatenate(vv)
    o = np.lexsort((ch, tt))
    return {"ch": ch[o], "t": tt[o], "v": vv[o], "validity": np.zeros(o.size, np.int64)}


def events():
    chans = MonitoringConfig.from_dictionary(D, CODES, ("IN20-0001",)).channels
    evs = []
    for k in range(N_S):
        t0 = k * DAY
        sid = f"KH2011-{k}"
        evs += [
            Event(
                t0 + 1,
                "faults.sortie_start",
                "faults",
                {"sortie_id": sid, "duration_s": DUR, "ab_lights": 2.0, "starts": 1.0},
            ),
            Event(t0 + 2, "monitor.sortie_start", "monitoring", {"sortie_id": sid}),
            Event(t0 + 3, "monitor.observe", "monitoring", chunk(k, 0, chans)),
            Event(t0 + 400 * SEC, "monitor.observe", "monitoring", chunk(k, 1, chans)),
            Event(t0 + 560 * SEC, "monitor.landing", "monitoring", {}),
            Event(
                t0 + int(DUR) * SEC + 1,
                "health.sortie",
                "health",
                SortieUsage(
                    sortie_id=sid,
                    flight_time_s=480.0,
                    eot_s=(DUR,),
                    tamp_s=(240.0,),
                    type1=(1.0,),
                    type3=(0.0,),
                    type4=(0.0,),
                    eftc=(1.0,),
                    src_h=(0.01,),
                    ps3_full=(0.0,),
                    ps3_partial=(1.0,),
                    ab_lights=(2.0,),
                    starts=(1.0,),
                ).to_payload(),
            ),
            Event(t0 + int(DUR) * SEC + 2, "faults.sortie_end", "faults", {"flight_time_s": 480.0}),
            Event(
                t0 + int(DUR) * SEC + 3,
                "monitor.sortie_end",
                "monitoring",
                {"flight_time_s": np.array(480.0)},
            ),
        ]
    return evs


K_END = (N_S - 1) * 240 * 86_400 + int(DUR) * 240 + 10
K_SNAP = 240 * 86_400 + 300 * 240  # sortie 1, between its two CIR chunks


@pytest.fixture(scope="module")
def reference():
    s = build()
    w, _ = s.run(s.inject(s.start(), events()), K_END)
    return s, w


@pytest.mark.fork
def test_deterministic_rerun(reference):
    s, w = reference
    s2 = build()
    w2, _ = s2.run(s2.inject(s2.start(), events()), K_END)
    assert snapshot(s2, w2) == snapshot(s, w)
    st = w.states
    assert st["faults"]["inst_mode"].size > 0  # faults happened
    assert np.any(st["monitoring"]["o_kind"] == 0) and np.any(st["monitoring"]["o_kind"] == 1)


@pytest.mark.fork
def test_snapshot_mid_sortie_restores_and_continues_bitwise(reference):
    s_ref, w_ref = reference
    s1 = build()
    w1, _ = s1.run(s1.inject(s1.start(), events()), K_SNAP)
    m = w1.states["monitoring"]
    assert int(m["clock"][2]) == 1  # in a sortie
    assert np.any(m["t_ist"] != 0) and np.any(m["hold_t"] >= 0)  # latches / persistence / held values live
    snap = snapshot(s1, w1)
    assert len(read_snapshot(snap).queue) > 0
    s2 = build()
    w2 = restore(s2, snap)
    assert snapshot(s2, w2) == snap
    w3, _ = s2.run(w2, K_END - K_SNAP)
    assert snapshot(s2, w3) == snapshot(s_ref, w_ref)


@pytest.mark.fork
def test_forks_share_exogenous_draws(reference):
    """Branch B gets maintenance orders at the fork (wash, a maintenance action that may queue a latent
    defect, an IBIT); the exogenous draws both branches consume are identical (CRN audit), and the
    sortie-keyed faults
    of the later sorties are the same in both branches."""
    s0 = build()
    w0, _ = s0.run(s0.inject(s0.start(), events()), K_SNAP)
    snap = snapshot(s0, w0)
    t_fork = w0.t_ns + 1
    orders = [
        Event(t_fork, "health.maintenance", "health", {"action": "wash"}),
        Event(t_fork, "faults.maintenance", "faults", {"job": "J-42", "action": "engine_overhaul"}),
        Event(t_fork, "monitor.ibit", "monitoring", {"job": "J-42", "kind": "MBIT"}),
    ]
    out = []
    for o in ((), orders):
        led = DrawLedger()
        s = build(ledger=led)
        w = restore(s, snap)
        if o:
            w = s.inject(w, list(o))
        w, _ = s.run(w, K_END - K_SNAP)
        out.append((led, w))
    rep = crn_audit(out[0][0], out[1][0])
    assert not rep.consumption_differs and not rep.values_differ, rep.diverged()
    assert any("job=s:J-42" in p for p in rep.only_in_b)  # the order's own draws exist only in branch B
    assert len(rep.identical) > 20

    def sortie_faults(w):
        st = w.states["faults"]
        sel = np.isin(st["inst_sortie"], ["KH2011-2", "KH2011-3"])
        return sorted(
            zip(
                st["inst_mode"][sel].tolist(),
                st["inst_t0"][sel].tolist(),
                st["inst_sev"][sel].tolist(),
                strict=True,
            )
        )

    a, b = sortie_faults(out[0][1]), sortie_faults(out[1][1])
    latent = {i for i, m in enumerate(load_catalogue().values()) if m.process == "latent"}
    assert [x for x in a if x[0] not in latent] == [x for x in b if x[0] not in latent]
