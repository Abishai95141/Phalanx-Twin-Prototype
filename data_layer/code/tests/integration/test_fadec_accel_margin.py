"""W2.3a item 1 (AD-55 item 6): M08's ground-idle acceleration margin on the real M07 (W2.5 DEVIATIONS D3).

The W2.5 bench found that M08's accel Wf/PS3 schedule (``acc_k`` x a reference line derived from the *no-load*
nominal engine) left only 3-20 % margin at ground idle once M09's idle loads (about 22 kW PTO, 0.5 kg/s bleed)
and B7-level deterioration were present, and that below idle the margin vanished: the reference (the W1.3b
shape) falls as N2 falls while the loaded engine's steady Wf/PS3 rises, so a sag of a few points rolled the
engine back to WF_MIN with T5 rising. The fix (A-W2.3-1, ``phalanx.fadec.harmonise``) derives the reference,
accel/decel and feed-forward lines from the **installed** engine (nominal customer extraction) and continues
the reference on M07's installed steady line below idle down to ``harm_line_min_n2c``.

Checks:
1. **Structural margin.** On the installed steady line from ``harm_line_min_n2c`` to above idle (grid 0.01 in
   N2/sqrt(theta1), SLS ISA, idle nozzle floor, VG on schedule) the accel limit ``acc_k`` x reference exceeds
   the steady Wf/PS3 of the loaded engine with each B7 deterioration (F1-F7, the W2.5 set and magnitudes,
   through M10's health mapping) and with a worst-case build (every efficiency and flow 1 % low, the AD-07
   build-delta band) by at least 1/0.88: a serviceable fuel control at the low end of the CF-18 band (accel
   ratio units 88-100 % of nominal, Muir et al. AGARD-CP-448 p7 [TRANSFER: F404-400]) keeps acceleration
   authority. Negative control: the former no-load derivation fails the same check (margin below 1 below
   idle).
2. **Dynamic recovery.** M07 + M08 closed loop (``tests/engine_fadec_loop.py``) from the healthy no-load idle
   trim with M09's idle loads and each deterioration stepped in at t = 0 (the pre-registered W2.5 bench
   start): N2 recovers to the loaded idle governor point, the governor is back in control and WF_MIN is never
   selected after the first second; the recovery is damped: overshoot below 23 % of the initial sag (damping
   ratio above 0.42, the GM > 6 dB / PM > 45 deg design rule of C-MAPSS40k's scheduled setpoint loops, f404
   notes Q4; A-W2.3-3). Negative control: with the no-load tables at least one case rolls back.
3. **Integrated-aircraft loads** (coordinator, W2.1a TJ213: after ~800 s at ground idle M09's PTO had grown to
   32.5 kW and the idle-to-MIL take-off slam rolled N2 back from 64 % to 33 % with T5 rising, ENG-506). The
   loads ``INTEGRATED`` are the maxima of the 1 s means over the idle segment of that sortie (gate sortie 2,
   root 0xA5; ``analysis/calibration_w23/results/integrated_takeoff_*.json``): PTO 34.9 kW, bleed 0.538 kg/s.
   (a) the structural check of 1. at these loads; (b) **idle governor stability**: a 1 s, 3 % shaft-load kick
   at loaded ground idle decays (A-W2.3-3 gain schedule; negative control: without the schedule the
   oscillation does not decay, the sortie's 2.6 % peak-to-peak idle wander); (c) **idle-to-IRP slam** from a
   sagged idle (a 5 % shaft-load kick for the 3 s before the slam, the low swing the sortie slammed from) with
   each deterioration: no roll-back, WF_MIN never selected, N1 reaches 100 %. Negative control: the no-load
   tables roll the HPC-erosion engine (F3) back onto WF_MIN (ENG-506 reproduced).

Sample: structural 8 engine states x 13 grid speeds x 2 load sets (deterministic trims); dynamic 8 states x
20 s, 9 slams x 25 s and 3 kicks x 60 s, each a deterministic closed loop (no disturbance draws), plus the
negative-control runs. The smallest set that covers every B7 deterioration of the priority set, the build
band and the two load levels.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pytest

import engine_fadec_loop as L
from phalanx.dictionary.params import load_params
from phalanx.engine.layout import AUX_NAMES, U_WF
from phalanx.engine.module import EngineModule
from phalanx.engine.steady import TrimCondition, trim
from phalanx.fadec import FadecConfig, load_fadec_params
from phalanx.fadec.codes import L_GOV_N2, L_WFMIN
from phalanx.fadec.harmonise import config_from, harmonise
from phalanx.fadec.layout import O_LIMITER, P_LAYOUT
from phalanx.fadec.trim import operating_point

pytestmark = pytest.mark.integration
A_PS3 = AUX_NAMES.index("ps3")
MFC_LOW = 0.88  # serviceable fuel-control accel ratio units, low end of 88-100 % of nominal (Muir, CF-18)
CFG = FadecConfig.build(load_fadec_params())
PS = load_fadec_params()
LOADS = {"bleed": float(PS.value("harm_bleed")), "pto": float(PS.value("harm_pto"))}
#: idle extraction measured in the integrated aircraft (TJ213 gate sortie; maxima of 1 s means, ~750 s idle)
INTEGRATED = {"bleed": 0.54, "pto": 35.0e3}
LOAD_SETS = {"harmonisation": LOADS, "integrated": INTEGRATED}


def b7_deltas() -> dict[str, tuple[float, ...]]:
    """health.engine deltas of the W2.5 B7 deterioration set F1-F7 through M10's mapping (fouling: flow =
    fouling_flow_ratio x efficiency; erosion: flow = erosion_flow_ratio_<c> x efficiency; HPT abnormal loss as
    HPT erosion) plus a worst-case build (all efficiencies and flows -1 %, the AD-07 build band)."""
    m10 = load_params("M10")
    v = {k: float(m10[s].value(k)) for s in m10 for k in m10[s] if "flow_ratio" in k}
    ff = v["fouling_flow_ratio"]
    out = {
        "F1": (-0.02, -ff * 0.02, 0, 0, 0, 0, 0, 0, 0, 0),
        "F2": (0, 0, -0.02, -ff * 0.02, 0, 0, 0, 0, 0, 0),
        "F3": (0, 0, -0.05, -v["erosion_flow_ratio_hpc"] * 0.05, 0, 0, 0, 0, 0, 0),
        "F4": (0, 0, 0, 0, -0.026, -v["erosion_flow_ratio_hpt"] * 0.026, 0, 0, 0, 0),
        "F5": (0, 0, 0, 0, 0, 0, -0.008, -v["erosion_flow_ratio_lpt"] * 0.008, 0, 0),
        "F6": (0, 0, 0, 0, -0.03, -v["erosion_flow_ratio_hpt"] * 0.03, 0, 0, 0, 0),
        "F7": (0, 0, -0.05, 0, 0, 0, 0, 0, 0, 0),
        "build": (-0.01, -0.01, -0.01, -0.01, -0.01, -0.01, -0.01, -0.01, -0.01, 0.0),
    }
    return {k: tuple(float(x) for x in d) for k, d in out.items()}


@pytest.fixture(scope="module")
def eng():
    return EngineModule("eng")


@lru_cache(maxsize=2)
def _no_load_config() -> FadecConfig:
    """The former derivation: no-load design condition and no sub-idle line (the W1.3b shape below idle)."""
    ps = load_fadec_params().replace(harm_bleed=0.0, harm_pto=0.0, harm_line_min_n2c=0.70)
    return config_from(harmonise(EngineModule("eng").model, ps), CFG)


def _margins(model, cfg: FadecConfig, health, loads=None) -> np.ndarray:
    """acc_k x reference / steady Wf/PS3 of the engine with ``loads`` (default the harmonisation loads) and
    ``health`` on the N2c grid."""
    p = {k: float(cfg.p[i]) for k, i in P_LAYOUT.index.items()}
    a8 = float(np.interp(p["pla_gi"], cfg.tables.a8_pla_x, cfg.tables.a8_pla_y)) * p["a8_scale"]
    cond = TrimCondition(health=health, **(LOADS if loads is None else loads))
    grid = np.round(np.arange(float(PS.value("harm_line_min_n2c")), 0.6751, 0.01), 4)
    out, x = [], None
    for g in grid[::-1]:
        r = trim(model, cond, ("n2", g * p["n2_ref"]), a8=a8, x0=x)
        assert r.converged, g
        x = r.x
        ru = r.u[U_WF] / r.aux[A_PS3]
        out.append(p["acc_k"] * float(np.interp(g, cfg.tables.ru_x, cfg.tables.ru_y)) / ru)
    return np.array(out[::-1])


@pytest.mark.parametrize("loads", list(LOAD_SETS))
@pytest.mark.parametrize("case", list(b7_deltas()))
def test_accel_schedule_covers_the_loaded_deteriorated_steady_line(eng, case, loads, record_property):
    m = _margins(eng.model, CFG, b7_deltas()[case], LOAD_SETS[loads])
    record_property("min_margin", round(float(m.min()), 4))
    assert m.min() >= 1.0 / MFC_LOW, (case, loads, np.round(m, 3))


def test_accel_margin_negative_control_the_no_load_line_does_not(eng):
    """The former no-load derivation: below idle the accel limit falls under the loaded requirement of the
    HPC-erosion engine (F3), so the check above fails on it."""
    m = _margins(eng.model, _no_load_config(), b7_deltas()["F3"])
    assert m.min() < 1.0, np.round(m, 3)


def _step_run(eng, cfg: FadecConfig, health, secs: int = 20):
    """Healthy no-load idle trim; loads and ``health`` stepped in at t = 0 (the W2.5 pre-registered start)."""
    gi = float(np.rad2deg(cfg.p[P_LAYOUT.index["pla_gi"]]))
    start = operating_point(eng.model, cfg, gi, TrimCondition())
    cond = TrimCondition(health=health, **LOADS)
    run = L.run(eng, start.engine, gi, n=secs * 240, condition=cond, cfg=cfg)
    target = operating_point(eng.model, cfg, gi, cond)
    return run, target


OVERSHOOT_MAX = 0.23  # damping ratio 0.42 (second-order equivalent): PM > 45 deg


@pytest.mark.parametrize("case", list(b7_deltas()))
def test_idle_load_and_deterioration_step_recovers(eng, case, record_property):
    run, target = _step_run(eng, CFG, b7_deltas()[case])
    n2 = run.ch("n2") / L.N2R
    n2_tgt = float(target.engine.x[1]) / L.N2R
    lim = run.cmdi[:, 0, O_LIMITER] & 15
    err = n2 / n2_tgt - 1.0
    k = int(np.argmin(err))
    overshoot = max(0.0, float(err[k:].max())) / abs(float(err[k]))
    record_property("sag_pct", round(100 * float(err[k]), 3))
    record_property("overshoot", round(overshoot, 3))
    assert overshoot < OVERSHOOT_MAX, (case, overshoot)
    assert abs(n2[-480:].mean() / n2_tgt - 1.0) < 2e-3, (case, n2[-480:].mean(), n2_tgt)
    assert not np.any(lim[240:] == L_WFMIN), case
    assert np.all(lim[-480:] == L_GOV_N2), (case, set(lim[-480:].tolist()))
    assert n2.min() > 0.95 * n2_tgt, (case, n2.min(), n2_tgt)


def test_idle_step_negative_control_the_no_load_tables_roll_back(eng):
    """With the no-load tables at least one of the same steps rolls back below idle (W2.5 D3 reproduced)."""
    cfg = _no_load_config()
    rolled = []
    for case, h in b7_deltas().items():
        run, target = _step_run(eng, cfg, h)
        n2_end = float(run.ch("n2")[-480:].mean()) / L.N2R
        if n2_end < 0.95 * float(target.engine.x[1]) / L.N2R:
            rolled.append(case)
    assert rolled, "no case rolled back with the no-load tables"


def _flat_schedule(cfg: FadecConfig) -> FadecConfig:
    """``cfg`` without the N2-governor gain schedule (multiplier 1 everywhere: AD-57's Kp and Ki)."""
    tb = cfg.tables._replace(govk_x=np.array([0.0, 2.0]), govk_y=np.array([1.0, 1.0]))
    return FadecConfig(p=cfg.p, tables=tb, cfg=cfg.cfg, dt=cfg.dt, clock=cfg.clock)


def _kick_run(eng, cfg: FadecConfig, loads, secs: int = 60):
    """Loaded ground idle (M08 operating point); a 1 s, 3 % shaft-load pulse at t = 1 s. Returns the N2
    deviation from the pre-kick value (fraction of 100 %) and the M08 regulator after the kick."""
    gi = float(np.rad2deg(cfg.p[P_LAYOUT.index["pla_gi"]]))
    cond = TrimCondition(**loads)
    op = operating_point(eng.model, cfg, gi, cond)
    n = secs * 240
    w = np.zeros((n, 5))
    w[240:480, 3] = 0.03
    run = L.run(eng, op.engine, gi, n=n, condition=cond, cfg=cfg, w=w)
    n2 = run.ch("n2") / L.N2R
    return np.abs(n2 - n2[239]), run.cmdi[480:, 0, O_LIMITER] & 15


@pytest.mark.parametrize("loads", list(LOAD_SETS))
def test_idle_governor_kick_decays(eng, loads, record_property):
    """3b: after a 1 s, 3 % shaft-load kick at loaded ground idle the N2 deviation in the last 10 s of 60 s is
    below a fifth of its first-10 s peak (measured 0.04 at the harmonisation loads, 0.01 at the integrated
    loads) and below 0.05 % N2 (measured 0.012 % and 0.004 %); the N2 governor stays in control."""
    dev, lim = _kick_run(eng, CFG, LOAD_SETS[loads])
    first, last = float(dev[:2400].max()), float(dev[-2400:].max())
    record_property("dev_first_10s_pct", round(100 * first, 4))
    record_property("dev_last_10s_pct", round(100 * last, 4))
    assert last < 0.2 * first and last < 5e-4, (loads, first, last)
    assert np.all(lim == L_GOV_N2), set(lim.tolist())


def test_idle_governor_kick_negative_control_without_the_gain_schedule(eng):
    """3b negative control: with gain multiplier 1 (AD-57's Kp alone) the same kick at the integrated loads
    does not decay (last-10 s deviation above half the first-10 s peak; measured 0.88): the installed engine's
    steady Wf/PS3 falls as N2 rises at ground idle and the ratio-unit loop is barely damped."""
    dev, _lim = _kick_run(eng, _flat_schedule(CFG), INTEGRATED)
    first, last = float(dev[:2400].max()), float(dev[-2400:].max())
    assert last > 0.5 * first, (first, last)


SLAM_KICK = 0.05  # shaft-load fraction for the 3 s before the slam: the sagged idle the sortie slammed from


def _slam_run(eng, cfg: FadecConfig, health, loads=INTEGRATED):
    """Loaded idle (M08 operating point with ``health``), a 5 % shaft-load kick from 2 s to 5 s, PLA 18 -> 87
    at 5 s, 25 s in all. Returns N2, N1 (fractions of 100 %), the M08 regulator and the idle N2 before the
    kick."""
    gi = float(np.rad2deg(cfg.p[P_LAYOUT.index["pla_gi"]]))
    irp = float(np.rad2deg(cfg.p[P_LAYOUT.index["pla_irp"]]))
    cond = TrimCondition(health=health, **loads)
    op = operating_point(eng.model, cfg, gi, cond)
    n = 25 * 240
    pla = np.full(n, gi)
    pla[5 * 240 :] = irp
    w = np.zeros((n, 5))
    w[2 * 240 : 5 * 240, 3] = SLAM_KICK
    run = L.run(eng, op.engine, pla, n=n, condition=cond, cfg=cfg, w=w)
    n2, n1 = run.ch("n2") / L.N2R, run.ch("n1") / L.N1R
    return n2, n1, run.cmdi[:, 0, O_LIMITER] & 15, float(n2[2 * 240 - 1])


@pytest.mark.parametrize("case", ["healthy", *b7_deltas()])
def test_idle_to_irp_slam_at_the_integrated_loads_does_not_roll_back(eng, case, record_property):
    """3c: from the sagged loaded idle the slam to IRP never takes N2 below 97 % of the idle value, never
    selects WF_MIN, and N1 reaches 100 % (the N1 limit region) within the 20 s after the slam. (Slam timing
    is item 3 of W2.3a, C17; only the absence of a roll-back is asserted here.)"""
    health = (0.0,) * 10 if case == "healthy" else b7_deltas()[case]
    n2, n1, lim, n2_idle = _slam_run(eng, CFG, health)
    after = slice(5 * 240, None)
    k = np.flatnonzero(n1[after] >= 1.0)
    record_property("n2_min_after_slam_over_idle", round(float(n2[after].min() / n2_idle), 4))
    record_property("t_n1_100pct_s", round(float(k[0]) / 240.0, 2) if k.size else None)
    assert n2[after].min() >= 0.97 * n2_idle, (case, n2[after].min(), n2_idle)
    assert not np.any(lim[after] == L_WFMIN), case
    assert k.size and n1[-240:].mean() >= 1.0, (case, n1[-240:].mean())


def test_idle_to_irp_slam_negative_control_the_no_load_tables_roll_back(eng):
    """3c negative control: with the no-load tables the HPC-erosion engine (F3) slammed from the same sagged
    idle rolls back onto WF_MIN (N2 at the end below 60 % of the idle value; measured 52 %, 34 % N2): the
    integrated-aircraft ENG-506."""
    n2, _n1, lim, n2_idle = _slam_run(eng, _no_load_config(), b7_deltas()["F3"])
    assert np.any(lim[5 * 240 :] == L_WFMIN)
    assert n2[-240:].mean() < 0.6 * n2_idle, (n2[-240:].mean(), n2_idle)
