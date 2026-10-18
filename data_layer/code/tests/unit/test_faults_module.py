"""M11 injector: faults reach their state owners only as perturbation events (I6), cascades follow the graph,
latent defects manifest after their latency, damage thresholds in M10 become faults, transient faults clear,
and FAULT labels are restricted and contract-valid.

TEST FIXTURES: ``Recorder`` modules stand in for M07/M08/M09/M05/M06/M12/M14 at the module boundary (they only
record the events they receive). Sample: 1 tail, scripted faults and ≤ 30 sorties per test."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError, ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.faults import (
    FaultConfig,
    FaultInjector,
    fault_labels,
    load_catalogue,
    load_fault_params,
    load_graph,
)
from phalanx.health import HealthConfig, HealthModule, SortieUsage, load_health_params, sensor_bias_channels

D = load_dictionary()
BC = sensor_bias_channels(D)
SEC = 10**9
DAY = 86_400 * SEC
TARGETS = ("engine", "fadec", "utilities", "fcs", "airframe", "sensors", "monitoring")


class Recorder(ModuleBase):  # TEST FIXTURE (module boundary): records received events
    version = "0.0.1"
    rate = None

    def __init__(self, id):
        super().__init__(id, ParamSet("rec", {}))
        self.log = []

    def init(self, params, keys):
        return {}

    def on_event(self, state, event, t):
        self.log.append((t, event))
        return state, []


def build(*, fparams=None, hparams=None, usage_mode=True, stochastic=False, targets=TARGETS):
    recs = {k: Recorder(k) for k in targets}
    h = HealthModule(
        "health", hparams or load_health_params(), config=HealthConfig(("IN20-0001",), BC, "faults")
    )
    cfg = FaultConfig(
        load_catalogue(),
        load_graph(),
        {"health": "health", **{k: k for k in targets}},
        ("IN20-0001",),
        BC,
        realise_physics_edges=usage_mode,
        stochastic=stochastic,
    )
    f = FaultInjector("faults", fparams or load_fault_params(), config=cfg)
    sysm = System(
        [h, f, *recs.values()],
        [],
        rng=RngService(0xFA17, StreamRegistry()),
        identity=KeyPath.of(scenario="S1", tail="KH2011"),
    )
    return sysm, f, h, recs


def run_to(sysm, w, t_ns):
    k = t_ns // (SEC // 240) + 2
    return sysm.run(w, max(1, k - w.k))[0]


def usage(k):
    return SortieUsage(
        sortie_id=f"KH2011-{k}",
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
    ).to_payload()


def sorties(n, *, t0=0):
    evs = []
    for k in range(n):
        t = t0 + k * DAY
        sid = f"KH2011-{k}"
        evs += [
            Event(
                t + 1,
                "faults.sortie_start",
                "faults",
                {"sortie_id": sid, "duration_s": 3600.0, "ab_lights": 4.0, "starts": 1.0},
            ),
            Event(t + 3600 * SEC, "health.sortie", "health", usage(k)),
            Event(t + 3600 * SEC + 1, "faults.sortie_end", "faults", {"flight_time_s": 3600.0}),
        ]
    return evs


@pytest.mark.unit
def test_fod_shock_applies_health_steps():
    sysm, _f, _h, recs = build()
    w = sysm.start()
    before = w.held["health.engine"][0].copy()
    w = sysm.inject(w, [Event(SEC, "faults.inject", "faults", {"mode": "FM.ENG.FOD_BIRD", "severity": 2.0})])
    w = run_to(sysm, w, 2 * SEC)
    p = load_fault_params()
    after = w.held["health.engine"][0]
    assert after[0] == pytest.approx(before[0] + 2.0 * p.value("fod_eta_step"))
    assert after[1] == pytest.approx(before[1] + 2.0 * p.value("fod_flow_step"))
    assert after[2] == pytest.approx(before[2] + 2.0 * p.value("fod_hpc_step"))
    eng = [e for _, e in recs["engine"].log]
    assert [str(e.payload["mode"]) for e in eng] == ["fod_imbalance"]
    assert int(w.states["faults"]["clock"][1]) == 1


@pytest.mark.unit
def test_triggered_blade_loss_cascade_in_usage_and_telemetry_modes():
    """A crack reaching its critical size in M10 triggers FM.ENG.BLADE_LOSS; in usage mode the AIB cascade is
    realised as events in order (stall < overtemp < flameout < generator failure); in telemetry mode the
    physics edges are left to the modules (only graph-edge nodes are emitted)."""
    hp = load_health_params().replace(crack_weibull_scale=3.0, crack_a0=0.005, crack_critical=0.004)
    for usage_mode in (True, False):
        sysm, f, _h, recs = build(hparams=hp, usage_mode=usage_mode)
        w = sysm.inject(sysm.start(), sorties(4))
        w = run_to(sysm, w, 4 * DAY)
        st = w.states["faults"]
        modes = [f.config.mode_ids[i] for i in st["inst_mode"]]
        assert "FM.ENG.BLADE_LOSS" in modes
        eng = [(t, str(e.payload["mode"])) for t, e in recs["engine"].log]
        util = [(t, str(e.payload["mode"])) for t, e in recs["utilities"].log]
        if usage_mode:
            t = {m: tt for tt, m in [*eng, *util]}
            assert (
                t["blade_loss"]
                <= t["stall"]
                < t["overtemp"]
                < t["flameout"]
                < t["gen_fail"]  # util.fault to M09 (AD-44); M09 brings the backup source on itself
            )
            mon = {str(e.payload["code"]) for _, e in recs["monitoring"].log}
            assert {"ENG-501", "ENG-701", "ENG-502", "ELE-401"} <= mon
        else:
            assert [m for _, m in eng] == ["blade_loss"]
            assert util == []


@pytest.mark.unit
def test_latent_defect_manifests_after_latency():
    """p = 1 per action and a 2-FH median latency: the defect is queued at the maintenance action and
    manifests at
    the first sortie after its latency elapsed (never before); p = 0 never injects."""
    fp = load_fault_params().replace(
        latent_p_engine=1.0, latent_latency_median=2.0 * 3600.0, latent_latency_sigma=1.0
    )
    sysm, f, _h, _recs = build(fparams=fp)
    w = sysm.inject(
        sysm.start(),
        [
            Event(SEC, "faults.maintenance", "faults", {"job": "J-1", "action": "engine_overhaul"}),
            *sorties(30, t0=DAY),
        ],
    )
    w = run_to(sysm, w, DAY + 2 * SEC)
    st = w.states["faults"]
    assert st["lat_mode"].size >= 1
    lat = dict(zip(st["lat_mode"].tolist(), st["lat_left_s"].tolist(), strict=True))
    w = run_to(sysm, w, 31 * DAY)
    st = w.states["faults"]
    got = {f.config.mode_ids[i]: int(t) for i, t in zip(st["inst_mode"], st["inst_t0"], strict=True)}
    for mi, left in lat.items():
        mid = f.config.mode_ids[mi]
        n_sorties = int(np.ceil(left / 3600.0))
        if n_sorties < 30:
            assert mid in got, mid
            assert got[mid] >= DAY + n_sorties * DAY  # after the sorties that consumed the latency
    fp0 = load_fault_params().replace(latent_p_engine=0.0)
    sysm, *_ = build(fparams=fp0)
    w = sysm.inject(
        sysm.start(),
        [Event(SEC, "faults.maintenance", "faults", {"job": "J-1", "action": "engine_overhaul"})],
    )
    w = run_to(sysm, w, 2 * SEC)
    assert w.states["faults"]["lat_mode"].size == 0


@pytest.mark.unit
def test_usage_detection_stand_in_only_when_covered():
    """A covered sensor fault produces the LRU condition of its first detection code (8 σ) in usage mode; an
    uncovered one (missed-detection pool) produces none; telemetry mode never emits the stand-in."""
    for covered, usage_mode, expect in ((True, True, 1), (False, True, 0), (True, False, 0)):
        sysm, _f, _h, recs = build(usage_mode=usage_mode)
        w = sysm.inject(
            sysm.start(),
            [Event(SEC, "faults.inject", "faults", {"mode": "FM.SNS.T5_OPEN", "covered": covered})],
        )
        w = run_to(sysm, w, 2 * SEC)
        mon = [e for _, e in recs["monitoring"].log]
        assert len(mon) == expect
        if expect:
            assert str(mon[0].payload["code"]) == "ENG-005" and float(mon[0].payload["magnitude"]) == 8.0
        sens = [e for _, e in recs["sensors"].log]
        assert len(sens) == 1 and sens[0].kind == "sensor_fault"
        assert str(sens[0].payload["mode"]) == "open"  # M12 reads the bottom of the range


@pytest.mark.unit
def test_usage_detection_stand_in_clears_with_its_instance():
    """W2.5 (B8-CHAIN1): the stand-in condition leaves M14 when its instance clears. A covered AB no-light
    (10 s, first code ENG-503) in usage mode: the condition at the onset, its clear at the instance's end;
    before the fix the condition stayed set and M14 kept declaring the code after the fault was gone."""
    sysm, _f, _h, recs = build(usage_mode=True)
    ev = Event(SEC, "faults.inject", "faults", {"mode": "FM.ENG.AB_NO_LIGHT", "covered": True})
    w = run_to(sysm, sysm.inject(sysm.start(), [ev]), 20 * SEC)
    mon = [(t, str(e.payload["code"]), bool(e.payload["clear"])) for t, e in recs["monitoring"].log]
    assert [(c, cl) for _, c, cl in mon] == [("ENG-503", False), ("ENG-503", True)]
    st = w.states["faults"]
    assert mon[1][0] - mon[0][0] == pytest.approx(st["inst_t1"][0] - st["inst_t0"][0], abs=SEC // 240 + 1)


@pytest.mark.unit
def test_transient_fault_clears_after_its_duration():
    sysm, _f, _h, recs = build()
    w = sysm.inject(sysm.start(), [Event(SEC, "faults.inject", "faults", {"mode": "FM.ENG.AB_NO_LIGHT"})])
    w = run_to(sysm, w, 20 * SEC)
    log = [(t, bool(e.payload["clear"])) for t, e in recs["engine"].log]
    assert [c for _, c in log] == [False, True]
    assert log[1][0] - log[0][0] == pytest.approx(10 * SEC, abs=SEC // 240 + 1)
    st = w.states["faults"]
    assert st["inst_t1"][0] - st["inst_t0"][0] == 10 * SEC


@pytest.mark.unit
def test_generic_sensor_fault_injection_and_errors():
    sysm, _f, _h, recs = build()
    w = sysm.inject(
        sysm.start(),
        [
            Event(
                SEC,
                "faults.inject",
                "faults",
                {
                    "mode": "FM.SNS.GENERIC",
                    "key": "HYD.SYS1.P",
                    "sensor_mode": "drift",
                    "magnitude": 0.1,
                    "rate": 0.01,
                },
            )
        ],
    )
    w = run_to(sysm, w, 12 * SEC)
    (t0, ev), (t1, hold) = recs["sensors"].log
    assert str(ev.payload["channel"]) == "HYD.SYS1.P" and str(ev.payload["mode"]) == "drift"
    assert float(ev.payload["value"]) == pytest.approx(0.01 * 350e5)  # SI drift rate (Pa/s)
    assert str(hold.payload["mode"]) == "bias" and float(hold.payload["value"]) == pytest.approx(0.1 * 350e5)
    assert t1 - t0 == 10 * SEC  # the drift reaches its bound (0.1 of span) after 10 s
    labels = fault_labels(
        _f,
        w.states["faults"],
        epoch_utc_ns=0,
        tail_no="KH2011",
        dict_version=D.dict_version,
        dict_hash=D.dict_hash,
    )
    assert labels.column("subject_id").to_pylist() == ["FM.SNS.GENERIC#0@HYD.SYS1.P"]
    w2 = sysm.inject(w, [Event(w.t_ns + 1, "faults.inject", "faults", {"mode": "FM.NOPE"})])
    with pytest.raises(ContractError):
        sysm.run(w2, 3)


@pytest.mark.unit
def test_fault_labels_restricted_and_valid():
    sysm, f, _h, _recs = build()
    w = sysm.inject(
        sysm.start(),
        [
            Event(SEC, "faults.inject", "faults", {"mode": "FM.ENG.FOD_BIRD", "severity": 1.5}),
            Event(SEC, "faults.inject", "faults", {"mode": "FM.ENG.FOD_BIRD", "severity": 0.5}),
            Event(2 * SEC, "faults.inject", "faults", {"mode": "FM.ENG.AB_NO_LIGHT"}),
        ],
    )
    w = run_to(sysm, w, 30 * SEC)
    tab = fault_labels(
        f,
        w.states["faults"],
        epoch_utc_ns=1_800_000_000 * SEC,
        tail_no="KH2011",
        dict_version=D.dict_version,
        dict_hash=D.dict_hash,
    )
    c = load_contract("v0")
    c.validate("labels.truth", tab)
    assert tab.num_rows == 3 and set(tab.column("label_kind").to_pylist()) == {"FAULT"}
    ends = tab.column("t_end").to_pylist()
    assert ends[0] is None and ends[2] == 1_800_000_000 * SEC + 12 * SEC
    assert tab.column("serial_no").to_pylist()[0] == "IN20-0001"
