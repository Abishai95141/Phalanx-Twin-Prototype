"""M10 module behaviour: per-sortie advance of every process by its usage driver, rub-in, spall and crack
progression and their failure triggers, life fractions, maintenance (wash, overhaul, replacement, service),
the event-only contract and the restricted labels.

Sample: 1 tail, 1-200 sorties per test (the smallest number that reaches each mechanism's regime; stated per
test). Health is advanced in usage mode (``health.sortie`` events) through the core scheduler."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError, EventNotHandledError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.health import (
    AIRFRAME_NAMES,
    ENGINE_DELTAS,
    UTIL_TRIGGERS,
    HealthConfig,
    HealthModule,
    SortieUsage,
    health_labels,
    hidden_index,
    load_health_params,
    sensor_bias_channels,
)
from phalanx.health.module import ENG_F, ENG_I, ENG_LIFE

DAY = 86_400 * 10**9


@pytest.fixture(scope="module")
def dic():
    return load_dictionary()


@pytest.fixture(scope="module")
def params():
    return load_health_params()


def usage(
    sid: str, *, eot=4500.0, tamp=600.0, fh=3600.0, dust=1.0, landings=1.0, ab=4.0, t1=1.0, t3=5.0, **kw
):
    return SortieUsage(
        sortie_id=sid,
        flight_time_s=fh,
        eot_s=(eot,),
        tamp_s=(tamp,),
        type1=(t1,),
        type3=(t3,),
        type4=(5.0,),
        eftc=(1.2,),
        src_h=(0.05,),
        ps3_full=(0.0,),
        ps3_partial=(1.0,),
        ab_lights=(ab,),
        starts=(1.0,),
        landings=landings,
        dust=dust,
        **kw,
    )


def build(dic, params, *, root=0x5EED, fault_target=None, extra=()):
    m = HealthModule(
        "health", params, config=HealthConfig(("IN20-0001",), sensor_bias_channels(dic), fault_target)
    )
    sysm = System(
        [m, *extra],
        [],
        rng=RngService(root, StreamRegistry()),
        identity=KeyPath.of(scenario="S1", tail="KH2011"),
    )
    return m, sysm


def fly(sysm, w, n, *, t0=0, step=DAY, **kw):
    evs = [
        Event(
            t0 + (k + 1) * step,
            "health.sortie",
            "health",
            usage(f"KH2011-{t0 // DAY + k}", **kw).to_payload(),
        )
        for k in range(n)
    ]
    w = sysm.inject(w, evs)
    k_end = (t0 + n * step) // (10**9 // 240) + 2
    w, _ = sysm.run(w, k_end - w.k)
    return w


@pytest.mark.unit
def test_event_only_contract_and_outputs(dic, params):
    m, sysm = build(dic, params)
    assert m.rate is None and m.ports_in == ()
    w = sysm.start()
    assert w.held["health.engine"].shape == (1, len(ENGINE_DELTAS))
    assert w.held["health.sensor_bias"].shape == (len(sensor_bias_channels(dic)),)
    # a new build is not perfect: N-CMAPSS initial loss U(0, 1 %) on every delta, with the physical sign
    d = w.held["health.engine"][0]
    assert np.all(np.abs(d) <= 0.01) and np.any(d != 0)
    assert d[ENGINE_DELTAS.index("fan_eta")] <= 0 and d[ENGINE_DELTAS.index("hpt_flow")] >= 0
    with pytest.raises(EventNotHandledError):
        sysm.run(sysm.inject(w, [Event(1, "health.bogus", "health")]), 3)


@pytest.mark.unit
def test_rub_in_step_then_exponential(dic, params):
    """Flight 1 after a build adds the c0 step; by ~200 flights rub-in nears c0 + c1 (n = 200 sorties)."""
    _m, sysm = build(dic, params)
    w = fly(sysm, sysm.start(), 1)
    f = w.states["health"]["eng_f"][0]
    assert f[ENG_F.index["rubin"]] == pytest.approx(0.010 + 0.005 * (1 - np.exp(-1 / 67.0)))
    w = fly(sysm, w, 199, t0=DAY)
    f = w.states["health"]["eng_f"][0]
    assert f[ENG_F.index["rubin"]] == pytest.approx(0.015, rel=0.04)


@pytest.mark.unit
def test_degradation_is_monotone_and_erosion_scales_with_dust(dic, params):
    """Erosion only grows; a dustier base erodes faster in expectation (same streams, so the comparison is
    paired; n = 40 sorties each)."""
    _m, sysm = build(dic, params)
    w = sysm.start()
    prev = None
    for k in range(4):
        w = fly(sysm, w, 10, t0=k * 10 * DAY)
        e = w.states["health"]["eng_f"][0][
            [ENG_F.index[n] for n in ("ero_fan", "ero_hpc", "ero_hpt", "ero_lpt")]
        ]
        if prev is not None:
            assert np.all(e >= prev)
        prev = e
    _, s2 = build(dic, params)
    w2 = fly(s2, s2.start(), 40, dust=3.0)
    e2 = w2.states["health"]["eng_f"][0][
        [ENG_F.index[n] for n in ("ero_fan", "ero_hpc", "ero_hpt", "ero_lpt")]
    ]
    assert e2.sum() > prev.sum()


@pytest.mark.unit
def test_spall_initiates_grows_and_sheds_debris(dic, params):
    """Bearing spall: nothing before the per-serial Weibull initiation life, then exponential growth with
    debris ∝ growth and oil Fe rising; the failure threshold emits faults.trigger once (I6 causal path).
    The initiation life is set short with ParamSet.replace so 30 sorties suffice."""
    p = params.replace(bearing_weibull_scale=10.0 * 3600.0, spall_critical=0.003)
    sink = _Sink("faults")
    _m, sysm = build(dic, p, fault_target="faults", extra=(sink,))
    w = sysm.start()
    life = w.states["health"]["eng_f"][0][ENG_F.index["spall_life"]]
    w = fly(sysm, w, 30)
    st = w.states["health"]
    f = st["eng_f"][0]
    assert st["eng_life"][0][ENG_LIFE.index["eot_s"]] >= life
    assert st["eng_i"][0][ENG_I.index["spall_on"]] == 1
    assert f[ENG_F.index["spall_len"]] > p.value("bearing_l0")
    grown = f[ENG_F.index["spall_len"]] - p.value("bearing_l0")
    spall_debris = f[ENG_F.index["debris"]] - f[ENG_F.index["debris_wear"]]  # healthy wear: W2.5 (C25)
    assert spall_debris == pytest.approx(p.value("bearing_debris_per_length") * grown, rel=1e-9)
    assert f[ENG_F.index["oil_fe"]] > p.value("oil_fe_slope") * 30 * 4500.0
    triggers = [e for _, e in sink.received if e.kind == "faults.trigger"]
    assert [str(e.payload["trigger"]) for e in triggers] == ["eng:spall_len"]


class _Sink(HealthModule.__mro__[1]):  # TEST FIXTURE: an event-only module that records what it receives
    version = "0.0.1"
    rate = None

    def __init__(self, id):
        from phalanx.core.module import ParamSet

        super().__init__(id, ParamSet("sink", {}))
        self.received = []

    def init(self, params, keys):
        return {}

    def on_event(self, state, event, t):
        self.received.append((t, event))
        return state, []


@pytest.mark.unit
def test_components_advance_by_their_drivers(dic, params):
    """Landing-driven states move with landings, calendar states with days, flight-hour states with FH; a
    sortie with no landing leaves landing-driven wear unchanged (n = 10 sorties)."""
    _m, sysm = build(dic, params)
    w = fly(sysm, sysm.start(), 10, landings=0.0)
    ui = hidden_index(1)
    u0 = _m.hidden_vector(w.states["health"])
    for name in ("tyre_wear_l", "brake_wear_l", "strut_service_l"):
        assert u0[ui[name]] == 0.0, name
    assert u0[ui["tyre_p_loss_l"]] > 0.0  # calendar leak since the first sortie
    assert u0[ui["chute_life"]] == 0.0
    w = fly(sysm, w, 10, t0=10 * DAY, landings=1.0, chute_streamings=1.0)
    u1 = _m.hidden_vector(w.states["health"])
    assert u1[ui["tyre_wear_l"]] > 0.0 or u1[ui["tyre_wear_r"]] > 0.0
    assert u1[ui["chute_life"]] == pytest.approx(10 / 45)
    assert u1[ui["str_fatigue"]] == 0.0  # no Nz crossings reported


@pytest.mark.unit
def test_pump_incubation_then_growth(dic, params):
    """Hydraulic pump wear stays flat through the per-serial incubation (~150 d), then grows linearly to the
    limit in ~198 d; reaching the limit triggers the pump-failure fault once (n = 400 daily sorties)."""
    sink = _Sink("faults")
    m, sysm = build(dic, params, fault_target="faults", extra=(sink,))
    w = sysm.start()
    onset_d = w.states["health"]["air_aux"][AIRFRAME_NAMES.index("hyd1_pump_wear")] / 86400.0
    w = fly(sysm, w, 100)
    ui = hidden_index(1)
    if onset_d > 101:
        assert m.hidden_vector(w.states["health"])[ui["hyd1_pump_wear"]] == 0.0
    w = fly(sysm, w, 300, t0=100 * DAY)
    assert m.hidden_vector(w.states["health"])[ui["hyd1_pump_wear"]] == 1.0
    trig = [str(e.payload["trigger"]) for _, e in sink.received if e.kind == "faults.trigger"]
    assert trig.count("util:hyd1_pump_wear") == 1 and set(UTIL_TRIGGERS) >= {t[5:] for t in trig}


@pytest.mark.unit
def test_life_fractions_track_usage(dic, params):
    """Disk LCF fraction = TAC / LCF limit and creep fraction = SRC hours / creep limit (n = 20 sorties)."""
    _m, sysm = build(dic, params)
    w = fly(sysm, sysm.start(), 20)
    ui = hidden_index(1)
    tac_per = 1 + 5 / 4 + 5 / 40
    u = _m.hidden_vector(w.states["health"])
    assert u[ui["eng1_disk_lcf"]] == pytest.approx(20 * tac_per / params.value("lcf_limit_tac"))
    assert u[ui["eng1_blade_creep"]] == pytest.approx(20 * 0.05 * 3600.0 / params.value("creep_limit_src_h"))
    assert w.states["health"]["eng_life"][0][ENG_LIFE.index["tac"]] == pytest.approx(20 * tac_per)


@pytest.mark.unit
def test_maintenance_actions(dic, params):
    _m, sysm = build(dic, params)
    w = fly(sysm, sysm.start(), 20, dust=4.0)
    st = w.states["health"]
    foul = st["eng_f"][0][ENG_F.index["foul_hpc"]]
    assert foul > 0
    t = w.t_ns + 1
    w = sysm.inject(w, [Event(t, "health.maintenance", "health", {"action": "wash"})])
    w, _ = sysm.run(w, 2)
    assert w.states["health"]["eng_f"][0][ENG_F.index["foul_hpc"]] == pytest.approx(
        foul * (1 - params.value("wash_rho"))
    )
    ero = w.states["health"]["eng_f"][0][ENG_F.index["ero_hpc"]]
    w = sysm.inject(
        w, [Event(w.t_ns + 1, "health.maintenance", "health", {"action": "overhaul_module", "target": "hpc"})]
    )
    w, _ = sysm.run(w, 2)
    f = w.states["health"]["eng_f"][0]
    assert f[ENG_F.index["ero_hpc"]] == pytest.approx(ero * params.value("overhaul_residue"))
    assert f[ENG_F.index["rubin"]] == 0.0 and w.states["health"]["eng_i"][0][ENG_I.index["since_build"]] == 0
    old = w.held["health.engine"].copy()
    w = sysm.inject(
        w,
        [
            Event(
                w.t_ns + 1,
                "health.maintenance",
                "health",
                {"action": "replace_engine", "serial": "IN20-0002"},
            )
        ],
    )
    w, _ = sysm.run(w, 2)
    st = w.states["health"]
    assert str(st["eng_serial"][0]) == "IN20-0002"
    assert st["eng_life"][0].sum() == 0.0 and not np.array_equal(w.held["health.engine"], old)
    ch = sensor_bias_channels(load_dictionary())[0].channel_id
    b0 = st["bias_inst"][0]
    w = sysm.inject(
        w,
        [
            Event(
                w.t_ns + 1,
                "health.maintenance",
                "health",
                {"action": "replace_sensor", "target": ch, "serial": "NEW-1"},
            )
        ],
    )
    w, _ = sysm.run(w, 2)
    assert w.states["health"]["bias_inst"][0] != b0 and w.states["health"]["bias_drift"][0] == 0.0
    w = sysm.inject(
        w, [Event(w.t_ns + 1, "health.maintenance", "health", {"action": "service", "target": "tyres"})]
    )
    w, _ = sysm.run(w, 2)
    assert _m.hidden_vector(w.states["health"])[hidden_index(1)["tyre_p_loss_l"]] == 0.0
    w2 = sysm.inject(w, [Event(w.t_ns + 1, "health.maintenance", "health", {"action": "teleport"})])
    with pytest.raises(ContractError):
        sysm.run(w2, 2)


@pytest.mark.unit
def test_health_fault_events_apply_signed_deltas(dic, params):
    _m, sysm = build(dic, params)
    w = sysm.start()
    before = w.held["health.engine"][0].copy()
    evs = [
        Event(
            10,
            "health.fault",
            "health",
            {"state": "eng:fod_fan_eta", "engine": 0, "delta": -0.02, "op": "add"},
        ),
        Event(11, "health.fault", "health", {"state": "util:hyd1_contamination", "delta": 0.7, "op": "set"}),
        Event(12, "health.fault", "health", {"state": "act:rudder", "delta": 0.2}),
    ]
    w, _ = sysm.run(sysm.inject(w, evs), 3)
    after = w.held["health.engine"][0]
    assert after[0] == pytest.approx(before[0] - 0.02)
    assert _m.hidden_vector(w.states["health"])[hidden_index(1)["hyd1_contamination"]] == 0.7
    assert w.held["health.actuator"][4] == pytest.approx(0.2)
    w2 = sysm.inject(w, [Event(w.t_ns + 1, "health.fault", "health", {"state": "eng:nope", "delta": 1.0})])
    with pytest.raises(ContractError):
        sysm.run(w2, 2)


@pytest.mark.unit
def test_labels_are_restricted_and_validate(dic, params):
    from phalanx.dictionary.contract import load_contract

    m, sysm = build(dic, params)
    w = fly(sysm, sysm.start(), 3)
    tab = health_labels(
        m,
        w.states["health"],
        t_utc_ns=1_800_000_000 * 10**9,
        tail_no="KH2011",
        sortie_id="KH2011-2",
        dict_version=dic.dict_version,
        dict_hash=dic.dict_hash,
    )
    c = load_contract("v0")
    c.validate("labels.truth", tab)
    assert set(tab.column("label_kind").to_pylist()) == {"HIDDEN_STATE"}
    subj = tab.column("subject_id").to_pylist()
    assert len(subj) == len(set(subj))
    assert any(s.startswith("NM.ENG.SENSOR_TRUTH/") for s in subj) and any(
        s.startswith("NM.ENG.HPC_HEALTH/") for s in subj
    )
    with pytest.raises(PermissionError):
        c.consumer_schema("labels.truth")
