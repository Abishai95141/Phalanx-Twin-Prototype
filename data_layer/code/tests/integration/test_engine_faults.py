"""``eng.fault_inject`` (M11 -> M07, AD-48.4): engine faults are state perturbations with their catalogue
signature direction, a ``clear`` removes them, and the healthy path is untouched (A-W2.1b-4).

Open loop at the M07 design point (SLS, MIL fuel and nozzle held; no disturbance), one or two engines,
n = 480 ticks (2 s) per run unless a mode needs longer (oil leak and lube-cooling loss: 4,800 ticks at an
accelerated rate). Every comparison is faulted vs healthy from the same state with identical inputs, so
the difference is the fault alone. Start faults act below run speed only; their effect is checked on the
kernel derivative at a sub-run-speed state (the open-loop design point is above run speed, where the run
must be bitwise unchanged).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError, EventNotHandledError
from phalanx.core.rng import KeyPath, Keys, RngService, StreamRegistry
from phalanx.dictionary.yamlio import load_yaml
from phalanx.engine import faults as F
from phalanx.engine.design import build_engine_model
from phalanx.engine.kernel import deriv, inlet
from phalanx.engine.layout import (
    A_T41AD,
    AB_LIT,
    AB_OFF,
    F_FLT0,
    FLT_OIL_LEVEL,
    I_AB,
    I_FLAME,
    I_NSURGE,
    INL_WFL,
    NAUX,
    NFLT,
    NINL,
    NX,
    U_MACH,
    U_NAMES,
    U_PS,
    U_Q,
    U_TS,
    U_WFM_D,
    U_WIR,
    X_N2,
    X_T41,
    X_WFM,
)
from phalanx.engine.module import EngineModule
from phalanx.engine.ports import EVENTS_IN, EVENTS_OUT, MODULE_IDS
from phalanx.engine.steady import TrimCondition

pytestmark = pytest.mark.integration
DT = 1.0 / 240.0
CAT = load_yaml(Path(__file__).resolve().parents[2] / "configs" / "interfaces" / "w1_events.yaml")["events"]


@pytest.fixture(scope="module")
def model():
    return build_engine_model()


def _bound(eng: EngineModule) -> EngineModule:
    """Bind the module's keyed streams (the AB light-off draw) as a System would."""
    eng.bind(
        Keys(RngService(0x21B, StreamRegistry(eng.streams)), KeyPath.of(scenario="w21b", tail="T1", sortie=1))
    )
    return eng


@pytest.fixture(scope="module")
def eng1(model):
    return _bound(EngineModule("eng", model))


@pytest.fixture(scope="module")
def eng2(model):
    return _bound(EngineModule("eng", model, n_engines=2))


def _inputs(eng: EngineModule, n: int, *, ab: int = 0) -> dict[str, np.ndarray]:
    """Constant inputs at the module's initial (design) point; ``ab`` = 1 requests the afterburner."""
    e, u = eng.n_engines, eng._init_u
    return {
        "wf_cmd": np.full((n, e), u[0]),
        "wf_ab_cmd": np.full((n, e), 0.6 * ab),
        "a8_cmd": np.full((n, e), u[2]),
        "vg_cmd": np.broadcast_to(u[3:5], (n, e, 2)).copy(),
        "ignition": np.zeros((n, e), np.int64),
        "ab_enable": np.full((n, e), ab, np.int64),
        "t_s": np.full(n, 288.15),
        "p_s": np.full(n, 101325.0),
        "q_spec": np.zeros(n),
        "mach": np.zeros(n),
        "w_engine": np.zeros((n, e, 5)),
        "bleed_extract": np.zeros((n, e)),
        "pto_power": np.zeros((n, e)),
        "fuel_inlet_t": np.full((n, e), u[U_NAMES.index("t_fuel")]),
        "health": np.zeros((n, e, 10)),
    }


def _run(eng, state, n, *, ab=0):
    return eng.step_block(state, _inputs(eng, n, ab=ab), np.arange(n, dtype=np.int64), DT)


def _ev(mode, param=1.0, *, engine=0, clear=False):
    return Event(
        0, F.EVENT_KIND, "eng",
        {"tail": "T1", "mode": mode, "param": param, "instance": 7, "engine": engine, "clear": clear},
        source="faults",
    )  # fmt: skip


def _inject(eng, state, *args, **kw):
    new, out = eng.on_event(state, _ev(*args, **kw), 0)
    assert out == []
    return new


def _pair(eng, mode, n=480, param=1.0, *, ab=0, warm=0):
    s0 = eng.init(eng.params, None)
    if warm:
        s0, _ = _run(eng, s0, warm, ab=ab)
    sh, yh = _run(eng, s0, n, ab=ab)
    sf, yf = _run(eng, _inject(eng, s0, mode, param), n, ab=ab)
    return (sh, yh), (sf, yf)


def test_protocol_declaration_matches_the_catalogue():
    """M07 declares the catalogued consumer side of eng.fault_inject (AD-44 convention), nothing else."""
    assert MODULE_IDS == ("M07",) and EVENTS_OUT == {}
    spec = CAT[F.EVENT_KIND]
    assert "M07" in spec["consumers"] and spec["producer"] == "M11"
    assert set(EVENTS_IN) == {F.EVENT_KIND}
    assert tuple(spec["payload"]) == EVENTS_IN[F.EVENT_KIND] == F.PAYLOAD


def test_every_catalogued_engine_mode_is_realised():
    """Every engine-target mode of the M11 catalogue is one of M07's modes (no silent drop)."""
    cat = load_yaml(Path(__file__).resolve().parents[2] / "configs" / "tejas" / "faults" / "catalogue.yaml")
    modes = set()
    for spec in cat["modes"].values():
        for eff in spec.get("effects", []) or []:
            if isinstance(eff, dict) and eff.get("target") == "engine":
                modes.add(eff["mode"])
    assert modes, "no engine modes found in the catalogue"
    assert modes <= set(F.MODES), sorted(modes - set(F.MODES))


def test_payload_is_validated(eng1):
    s = eng1.init(eng1.params, None)
    bad = {"tail": "T1", "mode": "fod_imbalance", "param": 1.0, "instance": 0, "engine": 0, "clear": False}
    for k in F.PAYLOAD:
        pl = {kk: v for kk, v in bad.items() if kk != k}
        with pytest.raises(ContractError, match=k):
            eng1.on_event(s, Event(0, F.EVENT_KIND, "eng", pl), 0)
    for key, val, msg in (
        ("mode", "warp_core_breach", "unknown"),
        ("engine", 1, "outside"),
        ("param", -1.0, ">="),
    ):
        with pytest.raises(ContractError, match=msg):
            eng1.on_event(s, Event(0, F.EVENT_KIND, "eng", {**bad, key: val}), 0)
    with pytest.raises(EventNotHandledError):
        eng1.on_event(s, Event(0, "fadec.fault_inject", "eng", bad), 0)


def test_handler_changes_state_only_and_does_not_mutate_its_input(eng1):
    s0 = eng1.init(eng1.params, None)
    snap = {k: v.copy() for k, v in s0.items()}
    s1 = _inject(eng1, s0, "fod_imbalance")
    for k in s0:
        assert np.array_equal(s0[k], snap[k]), k  # input state untouched
    for k in ("i", "buf", "y", "yi"):
        assert np.array_equal(s1[k], s0[k]), k  # outputs change only through the dynamics (next step)
    assert s1["fm"][0, F.MODES.index("fod_imbalance")] == 1.0


def test_inject_then_clear_restores_the_healthy_run_bitwise(eng1):
    """A persistent mode cleared before any step leaves the run bitwise identical to the healthy one."""
    s0 = eng1.init(eng1.params, None)
    for mode in sorted(set(F.MODES) - F.ONE_SHOT - {"oil_quantity_low"}):
        s = _inject(eng1, _inject(eng1, s0, mode, 0.8), mode, 0.8, clear=True)
        assert np.array_equal(s["f"], s0["f"]) and np.array_equal(s["fm"], s0["fm"]), mode
    _, yh = _run(eng1, s0, 240)
    s = _inject(eng1, _inject(eng1, s0, "bearing_failure"), "bearing_failure", clear=True)
    _, yc = _run(eng1, s, 240)
    for k in yh:
        assert np.array_equal(yh[k], yc[k]), k


def test_vibration_modes_raise_their_own_band(eng1):
    """FOD/fan liberation: N1 1/rev; blade loss: N2 1/rev; bearing: broadband (vib_src bands [N1, N2, bb])."""
    for mode, band in (
        ("fod_imbalance", 0),
        ("blade_loss", 1),
        ("bearing_failure", 2),
        ("fan_blade_liberation", 0),
    ):
        (_, yh), (_, yf) = _pair(eng1, mode, n=48)
        ratio = yf["vib_src"][-1, 0] / yh["vib_src"][-1, 0]
        assert ratio[band] > 1.5, (mode, ratio)
    (_, yh), (_, yf) = _pair(eng1, "fod_imbalance", n=48)
    r = yf["vib_src"][-1, 0] / yh["vib_src"][-1, 0]
    assert abs(r[1] - 1.0) < 1e-3 and abs(r[2] - 1.0) < 1e-3, r  # FOD alone leaves the other bands


def test_stall_modes_surge_and_bearing_failure_repeats_above_85_percent(eng1):
    for mode in ("pop_stall", "quickfill_stall", "blade_loss", "fan_blade_liberation"):
        (sh, _), (sf, _) = _pair(eng1, mode, n=240)
        assert sh["i"][0, I_NSURGE] == 0 and sf["i"][0, I_NSURGE] >= 1, mode
    # bearing failure at MIL (N2 above 85 %): repeat stalls. (Open loop at MIL fuel the W1.3a PROXY surge
    # model then over-speeds the core, since nothing cuts fuel; the N2 direction is checked below 85 %.)
    (sh, _), (sf, _) = _pair(eng1, "bearing_failure", n=960)
    assert sh["i"][0, I_NSURGE] == 0 and sf["i"][0, I_NSURGE] >= 2


def test_bearing_failure_below_its_stall_speed_loads_the_core(model):
    """At 80 % N2 (below the 85 % stall threshold): no stall; the extra HP load pulls N2 down at fixed fuel
    and raises T5 (catalogue: RPM down with FTIT up)."""
    base = EngineModule("eng", model)
    tr = base.trim(
        TrimCondition(t_s=288.15, p_s=101325.0, mach=0.0), ("n2", 0.80 * model.design.stations["n2_100"])
    )
    assert tr.converged
    eng = base.from_trim(tr)
    (_, yh), (sf, yf) = _pair(eng, "bearing_failure", n=960)
    assert sf["i"][0, I_NSURGE] == 0
    assert yf["n2"][-1, 0] < 0.995 * yh["n2"][-1, 0]
    assert yf["t5"][-1, 0] > yh["t5"][-1, 0]


def test_one_shot_flameout_and_ab_blowout(eng1):
    s0 = eng1.init(eng1.params, None)
    assert _inject(eng1, s0, "flameout")["i"][0, I_FLAME] == 0
    (_, yh), (_, yf) = _pair(eng1, "flameout", n=240)
    assert yh["flame_state"][-1, 0] == 1 and yf["flame_state"][0, 0] == 0
    assert yf["n2"][-1, 0] < 0.98 * yh["n2"][-1, 0]  # no ignition commanded: the core runs down
    # AB blowout: light the AB first (healthy run to AB_LIT), then blow it out
    s, _ = _run(eng1, eng1.init(eng1.params, None), 1200, ab=1)
    assert s["i"][0, I_AB] == AB_LIT
    s2 = _inject(eng1, s, "ab_rumble_blowout")
    assert s2["i"][0, I_AB] == AB_OFF
    # fm keeps nothing for a one-shot mode
    assert not s2["fm"].any()


def test_ab_no_light_blocks_the_light_off(eng1):
    (_, yh), (_, yf) = _pair(eng1, "ab_no_light", n=1200, ab=1)
    assert yh["ab_state"].max() == AB_LIT
    assert yf["ab_state"].max() < AB_LIT


def test_fuel_restriction_caps_metered_fuel(eng1, model):
    (_, yh), (_, yf) = _pair(eng1, "fuel_restriction", n=960)
    cap = model.params.value("fault_fuel_cap") * model.design.stations["wf"]
    assert yf["wf"][-1, 0] <= cap * (1 + 1e-6) < yh["wf"][-1, 0]
    assert yf["n2"][-1, 0] < yh["n2"][-1, 0]


@pytest.mark.parametrize(
    "mode,param", [("bleed_leak", 0.45), ("bleed_schedule_bias", 0.02), ("liner_burn_through", 1.0)]
)
def test_thrust_loss_modes(eng1, mode, param):
    """Extra bleed and a nozzle leak lose thrust at fixed fuel and throat (catalogue: thrust down)."""
    (_, yh), (_, yf) = _pair(eng1, mode, n=480, param=param)
    assert yf["thrust"][-1, 0] < 0.995 * yh["thrust"][-1, 0], mode


def test_oil_leak_drops_pressure_and_cooling_loss_heats_oil(eng1):
    n = 4800  # 20 s; leak sized so the charge crosses the critical level inside the run
    (_, yh), (sf, yf) = _pair(eng1, "oil_quantity_low", n=n, param=30.0)
    lvl = sf["f"][0, F_FLT0 + FLT_OIL_LEVEL]
    assert lvl < 0.5
    assert yf["oil_p"][-1, 0] < 0.9 * yh["oil_p"][-1, 0]
    (_, yh), (_, yf) = _pair(eng1, "lube_cooling_loss", n=n, param=0.5)
    assert yf["oil_t"][-1, 0] > yh["oil_t"][-1, 0] + 0.5


def _t41_and_n2dot(model, u, x, flt):
    """Kernel derivative at state ``x`` with fault slice ``flt``: (adiabatic T41, dT41/dt)."""
    p, tb = model.p, model.tables
    inl = np.empty(NINL)
    inlet(u[U_TS], u[U_PS], u[U_Q], u[U_MACH], u[U_WIR], p, tb, inl)
    inl[INL_WFL] = x[X_WFM] * (1.0 + u[U_WFM_D])
    dx, aux = np.empty(NX), np.empty(NAUX)
    deriv(x, 0, 1, 0, 0.0, inl, u, p, tb, dx, aux, flt)
    return aux[A_T41AD], dx[X_T41]


def test_start_faults_act_below_run_speed_only(eng1, model):
    s0 = eng1.init(eng1.params, None)
    # above run speed (open-loop design point): hung/hot start leave the run bitwise unchanged
    for mode in ("hung_start", "hot_start"):
        (_, yh), (_, yf) = _pair(eng1, mode, n=120)
        for k in yh:
            assert np.array_equal(yh[k], yf[k]), (mode, k)
    # below run speed: hung start burns less (cooler, weaker acceleration), hot start over-fuels (hotter)
    x = s0["f"][0, :NX].copy()
    x[X_N2] = 0.5 * model.design.stations["n2_100"]
    healthy = np.zeros(NFLT)
    healthy[FLT_OIL_LEVEL] = 1.0
    t_h, nd_h = _t41_and_n2dot(model, eng1._init_u, x, healthy)
    for mode, sign in (("hung_start", -1.0), ("hot_start", 1.0)):
        s = _inject(eng1, s0, mode)
        flt = s["f"][0, F_FLT0:].copy()
        t_f, nd_f = _t41_and_n2dot(model, eng1._init_u, x, flt)
        assert sign * (t_f - t_h) > 1.0, (mode, t_h, t_f)
        assert sign * (nd_f - nd_h) > 0.0, (mode, nd_h, nd_f)


def test_fault_targets_one_engine_and_survives_snapshot(eng2):
    s0 = eng2.init(eng2.params, None)
    s1 = _inject(eng2, s0, "fod_imbalance", engine=1)
    _, y = _run(eng2, s1, 48)
    v = y["vib_src"][-1]
    assert v[1, 0] > 1.5 * v[0, 0] and s1["fm"][0].sum() == 0.0  # engine 2 only
    # snapshot with the fault active -> restore -> continue == uninterrupted
    sa, _ = _run(eng2, s1, 100)
    sb = eng2.set_state(eng2.get_state(sa))
    _, ya = _run(eng2, sa, 100)
    _, yb = _run(eng2, sb, 100)
    for k in ya:
        assert np.array_equal(ya[k], yb[k]), k
