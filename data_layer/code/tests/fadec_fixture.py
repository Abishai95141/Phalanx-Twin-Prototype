"""TEST FIXTURE for M08 (W1.3b): a labelled stand-in plant and in-loop lane source at the FADEC boundary.

**TEST FIXTURE - not a physics deliverable** (W1 common rules; A-W1.3b-15). It lives under `tests/`, is never
imported by `src/`, and its parameter values are arbitrary test values sized only so that the closed loop has
F404-like orders of magnitude. The real M07 (W1.3a), M12/M13 (W1.6) and M03 (W1.1) replace it in W2.1 through
the same ports (`phalanx.fadec.coupling`).

Plant (per engine, SI, corrected-parameter form; 4 Euler sub-steps per 240 Hz truth step):
- core: d n2c/dt = (n2c_ss(Wf_c) - n2c - k_load * w_load) / tau2 (tau2 up/down), Wf_c the corrected fuel with
  combustor-efficiency and damage factors; fan: first-order lag to n1c_ss(n2c) with an A8 effect;
- fuel metering: first-order lag to wf_cmd * (1 + w_fuel); PS3 = P2 * pr3(n2c) through a volume lag, times a
  scripted stall factor; P2 carries the inlet-recovery disturbance;
- T5 (gas): first-order lag to T2 * (t5r(n2c) + excess-fuel term) * A8 factor + AB term + damage term; a
  thermocouple lag per harness (the M12 role) gives the T5 lanes;
- AB light-off and main relight state machines driven by the FADEC ignition/AB commands, with scripted faults.

Process disturbances `w[e, 4] = [fuel_metering, combustor_eff, inlet_recovery, shaft_load]` enter the dynamics
(never the outputs), as `env.w_engine` will (AD-32).

Lane source (the M12/M13 in-loop role): at the FADEC frame instants in [t_k, t_{k+1}) it interpolates truth
between x_k and x_{k+1} (A-W0.2-2), adds optional lane noise/bias/forced values, quantises to the dictionary
native step in EU with span saturation, and converts back to SI (as M13 will with `eu_to_si`).

`closed_loop(...)` runs plant + lanes + the real M08 kernel in one compiled loop with exactly the System
semantics (M08 -> plant -> lanes, lanes -> M08 one frame delayed), so a System built from `FixturePlant`,
`FixtureLanes`, `FixtureScenario` and `Fadec` reproduces it bitwise (A7 test).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import numpy as np
from numba import njit

from phalanx.core.module import ModuleBase, Param, ParamSet, Port
from phalanx.core.sampling import samples_for_steps
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import RG_240, latest_truth_step, truth_interp_weights, truth_step_times_ns
from phalanx.fadec.codes import NS
from phalanx.fadec.coupling import lane_port_name
from phalanx.fadec.kernel import fadec_block
from phalanx.fadec.layout import F_SEL, NF, NI, NOF, NOI, O_FAULTS, O_LIMITER, O_WF
from phalanx.fadec.params import FadecConfig, load_fadec_params
from phalanx.fadec.ports import LANE_PORTS, LANE_SLOT, capacity, lane_shape

FIXTURE_SOURCE = "TEST FIXTURE (tests/fadec_fixture.py; A-W1.3b-15)"
FIXTURE_TABLES = Path(__file__).resolve().parent / "fadec_fixture_tables"
_DEG = np.pi / 180.0
_RU = 0.45359237 / 3600.0 / 6894.757293168361  # (kg/s)/Pa per (lb/h)/psi
_IN2 = 0.0254 * 0.0254


def _fixture_column(name: str, column: str) -> np.ndarray:
    import csv

    rows = list(csv.reader((FIXTURE_TABLES / f"{name}.csv").read_text(encoding="utf-8").splitlines()))
    j = rows[0].index(column)
    return np.array([float(r[j]) for r in rows[1:] if r])


def fixture_params(**overrides) -> ParamSet:
    """TEST FIXTURE: the M08 parameters with the **W1.3b fixture-matched schedules** this plant was built
    around (moved here from configs/tejas/params/M08 when W2.1b derived the production schedules from M07,
    A-W2.1b-1; AD-50: fixture-matched tables are circular and belong with the fixture). Everything else
    (gains, limits, validator and monitors) is the production M08.yaml. The W1.3b acceptance tests on this
    plant run on these; the real-M07 tests run on the production configuration."""
    ps = load_fadec_params()
    t = _fixture_column
    vals = {
        "n2c_pla_x": t("n2c_pla", "pla_deg") * _DEG,
        "n2c_pla_y": t("n2c_pla", "n2c25"),
        "ru_ref_x": t("ru_ref", "n2c"),
        "ru_ref_y": t("ru_ref", "ru_pph_psi") * _RU,
        "ru_ff_x": t("ru_ff", "n2c25"),
        "ru_ff_y": t("ru_ff", "ru_pph_psi") * _RU,
        "fvg_x": t("fvg_n1c", "n1c"),
        "fvg_y": t("fvg_n1c", "fvg_deg") * _DEG,
        "cvg_x": t("cvg_n2c", "n2c25"),
        "cvg_y": t("cvg_n2c", "cvg_deg") * _DEG,
        "obm_n1_n2_x": t("obm_n1_n2", "n2c"),
        "obm_n1_n2_y": t("obm_n1_n2", "n1c"),
        "obm_pr3_x": t("obm_pr3", "n2c"),
        "obm_pr3_y": t("obm_pr3", "ps3_over_p0"),
        "obm_t25_x": t("obm_t25", "n1c"),
        "obm_t25_y": t("obm_t25", "t25_over_t1"),
        "obm_t5_x": t("obm_t5", "n2c"),
        "obm_t5_y": t("obm_t5", "t5_over_t1"),
        "a8_scale": 1.087,
        "a8_min": 220.0 * _IN2,
        "a8_max": 540.0 * _IN2,
        # W2.3a: the production governor has a gain schedule derived from M07's installed line; the fixture
        # plant keeps none (flat 1)
        "gov_ks_x": t("gov_ks", "n2c"),
        "gov_ks_y": t("gov_ks", "gain"),
    }
    new = dict(ps.items())
    for k, v in vals.items():
        old = ps[k]
        new[k] = Param(v, old.unit, "ASSUMPTION", f"{FIXTURE_SOURCE}: W1.3b fixture-matched value", old.proxy)
    out = ParamSet(f"{ps.name}.fixture", new)
    return out.replace(**overrides) if overrides else out


def fixture_config(clock=None, **cfg_kw) -> FadecConfig:
    """TEST FIXTURE: `FadecConfig` of `fixture_params()` (the W1.3b schedules)."""
    return FadecConfig.build(fixture_params(), **({} if clock is None else {"clock": clock}), **cfg_kw)


_JIT = {"cache": True, "fastmath": False, "error_model": "numpy", "nogil": True}
#: callers of the M08 kernel are NOT cached: Numba's cache does not track callees in other files, so a cached
#: caller would keep running a stale copy of `fadec_block` after kernel.py changes (W2.1 fused groups beware)
_JIT_NOCACHE = {"cache": False, "fastmath": False, "error_model": "numpy", "nogil": True}

# ------------------------------------------------------------------ plant state / parameter layout
X_N1, X_N2, X_WF, X_PS3, X_T5, X_A8, X_WFAB, X_LIT, X_ABLIT, X_ABT, X_RLT = range(11)
X_FVG, X_CVG, X_PS3_OUT, X_T25, X_T2, X_T5TC_A, X_T5TC_B = range(11, 18)
NX = 18
(
    PP_N1R,
    PP_N2R,
    PP_WREF,
    PP_TAU2_UP,
    PP_TAU2_DN,
    PP_TAU1,
    PP_TAU_FMV,
    PP_TAU_V,
    PP_TAU5,
    PP_TAU_A8,
    PP_K_LOAD,
    PP_K_A8N1,
    PP_K_A8T5,
    PP_A8_NOM,
    PP_K_WX,
    PP_K_AB_T5,
    PP_WFAB_REF,
    PP_T_LIGHT,
    PP_T_RELIGHT,
    PP_N2C_WINDMILL,
    PP_K_DMG_T5,
    PP_TAU_VG,
    PP_N2C_LIGHT_MIN,
    PP_WF_LIGHT_MIN,
    PP_TAU_TC,
    PP_T5B_OFFSET,
) = range(26)
NPP = 26
NSUB = 4
DT = 1.0 / 240.0

# exogenous plant inputs per step: [t_amb, p_amb, mach] common; per engine: w[4], ps3_factor, eff_loss, kill,
# start_drive
E_W0, E_PS3F, E_EFF, E_KILL, E_START, E_T5ADD = 0, 4, 5, 6, 7, 8
NEX = 9


class PlantTables(NamedTuple):
    """Fixture maps (corrected, normalised): arbitrary test shapes."""

    wf_x: np.ndarray  # n2c -> corrected fuel fraction of MIL
    wf_y: np.ndarray
    n2_x: np.ndarray  # inverse
    n2_y: np.ndarray
    n1_x: np.ndarray  # n2c -> n1c
    n1_y: np.ndarray
    pr_x: np.ndarray  # n2c -> PS3 / P2
    pr_y: np.ndarray
    t5_x: np.ndarray  # n2c -> T5 / T2
    t5_y: np.ndarray
    t25_x: np.ndarray  # n1c -> T25 / T2
    t25_y: np.ndarray
    a8_x: np.ndarray  # n2c -> nominal (scheduled) nozzle area [m^2]; deviations act on N1 and T5
    a8_y: np.ndarray


def plant_tables() -> PlantTables:
    f = lambda a: np.ascontiguousarray(np.array(a, dtype=np.float64))  # noqa: E731
    n2 = [0.2, 0.3, 0.45, 0.6, 0.665, 0.8, 0.9, 1.0, 1.08]
    wf = [0.01, 0.03, 0.07, 0.12, 0.155, 0.34, 0.6, 1.0, 1.35]
    return PlantTables(
        f(n2),
        f(wf),
        f(wf),
        f(n2),
        f([0.2, 0.3, 0.5, 0.665, 0.8, 0.9, 0.97, 1.0, 1.08]),
        f([0.08, 0.15, 0.32, 0.48, 0.66, 0.83, 0.98, 1.02, 1.10]),
        f([0.2, 0.3, 0.5, 0.665, 0.8, 0.9, 1.0, 1.08]),
        f([1.05, 1.2, 3.0, 6.2, 11.5, 18.5, 28.0, 33.0]),
        f([0.2, 0.3, 0.5, 0.665, 0.8, 0.9, 1.0, 1.08]),
        # lit T5/T2 vs n2c: sub-idle lit T5 above the ground-idle point (2.37 x 288 K = 410 degC, CR-191195
        # Fig. 33) - F100 airstart FTIT 450-520 degC (CP-2298) - so a lit sub-idle engine reads above the 371
        # degC
        # harness floor, as the real FADEC's T5-based light-off/flameout logic presumes
        f([2.6, 2.6, 2.5, 2.37, 2.85, 3.3, 3.85, 4.1]),
        f([0.1, 0.5, 0.7, 0.9, 1.0, 1.1]),
        f([1.0, 1.08, 1.2, 1.45, 1.6, 1.7]),
        f([0.3, 0.665, 0.8, 0.9, 1.0, 1.08]),
        f([0.2805, 0.2805, 0.2105, 0.2105, 0.1753, 0.1753]),
    )


def plant_params(**over: float) -> np.ndarray:
    v = {
        "n1r": 13270.0 * 2.0 * np.pi / 60.0,
        "n2r": 16810.0 * 2.0 * np.pi / 60.0,
        "wref": 1.15,
        "tau2_up": 1.33,
        "tau2_dn": 1.79,
        "tau1": 0.8,
        "tau_fmv": 0.05,
        "tau_v": 0.02,
        "tau5": 0.3,
        "tau_a8": 0.1,
        "k_load": 0.3,
        "k_a8n1": 0.1,
        "k_a8t5": 0.25,
        "a8_nom": 0.2,
        "k_wx": 0.5,
        "k_ab_t5": 0.15,
        "wfab_ref": 2.5,
        "t_light": 0.6,
        "t_relight": 1.0,
        "n2c_windmill": 0.25,
        "k_dmg_t5": 1.5,
        "tau_vg": 0.1,
        "n2c_light_min": 0.12,
        "wf_light_min": 0.02,
        "tau_tc": 1.0,
        "t5b_offset": 3.0,
    }
    v.update(over)
    return np.array(list(v.values()), dtype=np.float64)


@njit(**_JIT)
def _lk(x, y, v):
    n = x.shape[0]
    vr = v.real
    if vr <= x[0]:
        return y[0] + 0.0 * v
    if vr >= x[n - 1]:
        return y[n - 1] + 0.0 * v
    i = 0
    while x[i + 1] < vr:
        i += 1
    return y[i] + (v - x[i]) / (x[i + 1] - x[i]) * (y[i + 1] - y[i])


@njit(**_JIT)
def plant_step(
    x, pp, pt, wf_cmd, wfab_cmd, a8_cmd, fvg_cmd, cvg_cmd, ign, ab_en, t_amb, p_amb, mach, ex, ab_fault
):
    """Advance one engine's fixture state by one truth step (pure; returns a new state row)."""
    y = x.copy()
    m2 = 1.0 + 0.2 * mach * mach
    t2 = t_amb * m2
    p2 = p_amb * m2 * m2 * m2 * np.sqrt(m2) * (1.0 + ex[2])
    th = t2 / 288.15
    de = p2 / 101325.0
    sth = np.sqrt(th)
    h = DT / NSUB
    for _ in range(NSUB):
        n2c = y[X_N2] / (sth * pp[PP_N2R])
        n1c = y[X_N1] / (sth * pp[PP_N1R])
        wfc = y[X_WF] * (1.0 + ex[1]) * (1.0 - ex[E_EFF]) / (de * sth) / pp[PP_WREF]
        if y[X_LIT].real > 0.5:
            n2ss = _lk(pt.n2_x, pt.n2_y, wfc)
        else:
            n2ss = pp[PP_N2C_WINDMILL] * mach + ex[E_START] + 0.0 * wfc
        d2 = n2ss - n2c - pp[PP_K_LOAD] * ex[3]
        tau2 = pp[PP_TAU2_UP] if d2.real > 0.0 else pp[PP_TAU2_DN]
        y[X_N2] = y[X_N2] + h * d2 / tau2 * sth * pp[PP_N2R]
        a8f = y[X_A8] / _lk(pt.a8_x, pt.a8_y, n2c) - 1.0
        if a8f.real > 0.3:
            a8f = 0.3 + 0.0 * a8f
        elif a8f.real < -0.3:
            a8f = -0.3 + 0.0 * a8f
        n1ss = _lk(pt.n1_x, pt.n1_y, n2c) * (1.0 + pp[PP_K_A8N1] * a8f)
        y[X_N1] = y[X_N1] + h * (n1ss * sth * pp[PP_N1R] - y[X_N1]) / pp[PP_TAU1]
        y[X_WF] = y[X_WF] + h * (wf_cmd * (1.0 + ex[0]) - y[X_WF]) / pp[PP_TAU_FMV]
        abfuel = 1.0 if ab_en == 1 else 0.0
        y[X_WFAB] = y[X_WFAB] + h * (wfab_cmd * abfuel - y[X_WFAB]) / pp[PP_TAU_FMV]
        y[X_PS3] = y[X_PS3] + h * (p2 * _lk(pt.pr_x, pt.pr_y, n2c) - y[X_PS3]) / pp[PP_TAU_V]
        if y[X_LIT].real > 0.5:
            excess = wfc - _lk(pt.wf_x, pt.wf_y, n2c)
            t5ss = t2 * (_lk(pt.t5_x, pt.t5_y, n2c) + pp[PP_K_WX] * excess) * (1.0 - pp[PP_K_A8T5] * a8f)
            t5ss = t5ss + t2 * pp[PP_K_AB_T5] * y[X_ABLIT] * y[X_WFAB] / pp[PP_WFAB_REF]
            t5ss = t5ss + t2 * pp[PP_K_DMG_T5] * ex[E_EFF] + ex[E_T5ADD]
        else:
            t5ss = t2 * 1.1 + 0.0 * y[X_T5]
        y[X_T5] = y[X_T5] + h * (t5ss - y[X_T5]) / pp[PP_TAU5]
        y[X_A8] = y[X_A8] + h * (a8_cmd - y[X_A8]) / pp[PP_TAU_A8]
        y[X_FVG] = y[X_FVG] + h * (fvg_cmd - y[X_FVG]) / pp[PP_TAU_VG]
        y[X_CVG] = y[X_CVG] + h * (cvg_cmd - y[X_CVG]) / pp[PP_TAU_VG]
        y[X_T5TC_A] = y[X_T5TC_A] + h * (y[X_T5] - y[X_T5TC_A]) / pp[PP_TAU_TC]
        y[X_T5TC_B] = y[X_T5TC_B] + h * (y[X_T5] + pp[PP_T5B_OFFSET] - y[X_T5TC_B]) / pp[PP_TAU_TC]
    # discrete states (once per truth step)
    if ex[E_KILL].real > 0.5:
        y[X_LIT] = 0.0 * y[X_LIT]
        y[X_RLT] = 0.0 * y[X_RLT]
    elif y[X_LIT].real < 0.5:
        n2c = y[X_N2] / (sth * pp[PP_N2R])
        if (
            (ign & 1) == 1
            and y[X_WF].real > pp[PP_WF_LIGHT_MIN].real
            and n2c.real > pp[PP_N2C_LIGHT_MIN].real
        ):
            y[X_RLT] = y[X_RLT] + DT
            if y[X_RLT].real >= pp[PP_T_RELIGHT].real:
                y[X_LIT] = 1.0 + 0.0 * y[X_LIT]
                y[X_RLT] = 0.0 * y[X_RLT]
        else:
            y[X_RLT] = 0.0 * y[X_RLT]
    if ab_en == 1 and wfab_cmd.real > 0.0 and ab_fault == 0 and y[X_LIT].real > 0.5:
        if y[X_ABLIT].real < 0.5:
            y[X_ABT] = y[X_ABT] + DT
            if y[X_ABT].real >= pp[PP_T_LIGHT].real:
                y[X_ABLIT] = 1.0 + 0.0 * y[X_ABLIT]
    else:
        y[X_ABLIT] = 0.0 * y[X_ABLIT]
        y[X_ABT] = 0.0 * y[X_ABT]
    y[X_PS3_OUT] = y[X_PS3] * ex[E_PS3F]
    n1c = y[X_N1] / (sth * pp[PP_N1R])
    y[X_T25] = t2 * _lk(pt.t25_x, pt.t25_y, n1c)
    y[X_T2] = t2 + 0.0 * y[X_T2]
    return y


@njit(**_JIT)
def lane_values(xp, xn, w, qs, qo, qstep, qlo, qhi, noise, bias, fmask, fval):
    """One frame's lane vector [13] (SI): interpolate x_k -> x_{k+1} at weight w, perturb, quantise in EU."""
    out = np.zeros(13, dtype=xn.dtype)
    src = (X_N1, X_N1, X_N2, X_N2, X_T2, X_T2, X_T25, X_T25, X_PS3_OUT, X_PS3_OUT, X_T5TC_A, X_T5TC_B)
    for s in range(12):
        j = src[s]
        v = xp[j] + w * (xn[j] - xp[j]) + bias[s]
        if fmask[s] == 1:
            v = fval[s] + 0.0 * v
        eu = (v - qo[s]) / qs[s] + noise[s]
        q = np.floor(eu.real / qstep[s] + 0.5) * qstep[s]
        eu = eu + (q - eu.real)  # quantised (the real part lands on the lattice; derivatives pass through)
        if eu.real < qlo[s]:
            eu = qlo[s] + 0.0 * eu
        if eu.real > qhi[s]:
            eu = qhi[s] + 0.0 * eu
        out[s] = eu * qs[s] + qo[s]
    out[12] = xp[X_ABLIT]
    return out


def lane_quantiser():
    """(scale, offset, step, lo, hi) per lane slot from the dictionary (EU <-> SI, native step, span)."""
    from phalanx.dictionary import load_dictionary

    d = load_dictionary()
    qs, qo, qstep, qlo, qhi = (
        np.ones(12),
        np.zeros(12),
        np.full(12, 1e-12),
        np.full(12, -1e30),
        np.full(12, 1e30),
    )
    for name, cid, _unit in LANE_PORTS:
        k = LANE_SLOT[name]
        if k >= 12:
            continue
        conv = d.eu_conversion(cid)
        ch = d.channel(cid)
        qs[k], qo[k] = conv.scale, conv.offset
        qstep[k] = float(ch["native_step"])
        qlo[k], qhi[k] = float(ch["range"]["min"]), float(ch["range"]["max"])
    # slot 7 (T25 lane B) is unused: copy slot 6 so it stays finite
    qs[7], qo[7], qstep[7], qlo[7], qhi[7] = qs[6], qo[6], qstep[6], qlo[6], qhi[6]
    return tuple(np.ascontiguousarray(a) for a in (qs, qo, qstep, qlo, qhi))


@njit(**_JIT_NOCACHE)
def _closed_loop(
    f,
    i,
    p,
    tb,
    cfg,
    dtf,
    x0,
    pp,
    pt,
    pla,
    t_amb,
    p_amb,
    mach,
    ex,
    ab_fault,
    at_eng,
    at_cmd,
    nfr,
    wts,
    lane_noise,
    lane_bias,
    fmask,
    fval,
    qs,
    qo,
    qstep,
    qlo,
    qhi,
):
    """Fused fixture loop (M08 -> plant -> lanes; lanes reach M08 one step later). See module docstring."""
    n = pla.shape[0]
    n_eng = x0.shape[0]
    cap = wts.shape[1]
    x = x0.copy()
    lanes = np.zeros((1, cap, n_eng, 13), dtype=x0.dtype)
    xs = np.empty((n + 1, n_eng, NX), dtype=x0.dtype)
    xs[0] = x
    cmdf = np.empty((n, n_eng, NOF), dtype=x0.dtype)
    cmdi = np.empty((n, n_eng, NOI), dtype=np.int64)
    sel = np.empty((n, n_eng, NS), dtype=x0.dtype)
    lanes_in = np.zeros((n, cap, n_eng, 13), dtype=x0.dtype)
    nfr_in = np.zeros(n, dtype=np.int64)
    for k in range(n):
        cnt = np.zeros(1, dtype=np.int64)
        if k > 0:
            cnt[0] = nfr[k - 1]
        nfr_in[k] = cnt[0]
        lanes_in[k] = lanes[0]
        f, i, of, oi = fadec_block(
            f,
            i,
            p,
            tb,
            cfg,
            dtf,
            pla[k : k + 1],
            p_amb[k : k + 1],
            at_eng[k : k + 1],
            at_cmd[k : k + 1],
            lanes,
            cnt,
        )
        cmdf[k] = of[0]
        cmdi[k] = oi[0]
        for e in range(n_eng):
            for s in range(NS):
                sel[k, e, s] = f[e, F_SEL + s]
        xn = np.empty_like(x)
        for e in range(n_eng):
            xn[e] = plant_step(
                x[e],
                pp,
                pt,
                of[0, e, 0],
                of[0, e, 1],
                of[0, e, 2],
                of[0, e, 3],
                of[0, e, 4],
                oi[0, e, 0],
                oi[0, e, 1],
                t_amb[k],
                p_amb[k],
                mach[k],
                ex[k, e],
                ab_fault[e],
            )
        for s in range(nfr[k]):
            for e in range(n_eng):
                lanes[0, s, e] = lane_values(
                    x[e],
                    xn[e],
                    wts[k, s],
                    qs,
                    qo,
                    qstep,
                    qlo,
                    qhi,
                    lane_noise[k, s, e],
                    lane_bias[k, e],
                    fmask[k, e],
                    fval[k, e],
                )
        x = xn
        xs[k + 1] = x
    return f, i, xs, cmdf, cmdi, sel, lanes_in, nfr_in


def frame_table(clock, n_steps: int, capacity_: int):
    """Frames of the FADEC clock in [t_k, t_{k+1}) for k < n_steps: counts [n] and weights [n, cap]."""
    ks = np.arange(n_steps + 1, dtype=np.int64)
    t = truth_step_times_ns(ks)
    ss = samples_for_steps(clock, clock.first_index_at_or_after(0), t[:-1], t[1:])
    wts = np.zeros((n_steps, capacity_), dtype=np.float64)
    if ss.times.size:
        _, w = truth_interp_weights(ss.times)
        wts[ss.step, ss.slot] = w
    return ss.count.astype(np.int64), wts


@dataclass
class Scenario:
    """Exogenous inputs of a fixture run (arrays per truth step; e = n_engines)."""

    n_steps: int
    n_engines: int = 1
    pla_deg: np.ndarray | None = None  # [n, e]
    t_amb: np.ndarray | None = None  # [n] K
    p_amb: np.ndarray | None = None  # [n] Pa
    mach: np.ndarray | None = None  # [n]
    w: np.ndarray | None = None  # [n, e, 4] process disturbances
    ps3_factor: np.ndarray | None = None  # [n, e]
    eff_loss: np.ndarray | None = None  # [n, e]
    kill: np.ndarray | None = None  # [n, e]
    start_drive: np.ndarray | None = None  # [n, e]
    t5_add: np.ndarray | None = None  # [n, e] K, scripted gas-T5 offset (stagnation)
    ab_fault: np.ndarray | None = None  # [e] int
    at_engage: np.ndarray | None = None  # [n] int
    at_n1_cmd: np.ndarray | None = None  # [n, e]
    lane_noise_eu: np.ndarray | None = None  # [n, cap, e, 12] EU noise added before quantisation
    lane_bias: np.ndarray | None = None  # [n, e, 12] SI bias
    force_mask: np.ndarray | None = None  # [n, e, 12] int
    force_val: np.ndarray | None = None  # [n, e, 12] SI value
    extra: dict = field(default_factory=dict)

    def filled(self, cap: int) -> Scenario:
        n, e = self.n_steps, self.n_engines

        def z(a, shape, val=0.0, dtype=np.float64):
            return np.ascontiguousarray(
                np.full(shape, val, dtype=dtype) if a is None else np.asarray(a, dtype=dtype)
            )

        return Scenario(
            n,
            e,
            z(self.pla_deg, (n, e), 60.0),
            z(self.t_amb, (n,), 288.15),
            z(self.p_amb, (n,), 101325.0),
            z(self.mach, (n,), 0.0),
            z(self.w, (n, e, 4)),
            z(self.ps3_factor, (n, e), 1.0),
            z(self.eff_loss, (n, e)),
            z(self.kill, (n, e)),
            z(self.start_drive, (n, e)),
            z(self.t5_add, (n, e)),
            z(self.ab_fault, (e,), 0, np.int64),
            z(self.at_engage, (n,), 0, np.int64),
            z(self.at_n1_cmd, (n, e)),
            z(self.lane_noise_eu, (n, cap, e, 12)),
            z(self.lane_bias, (n, e, 12)),
            z(self.force_mask, (n, e, 12), 0, np.int64),
            z(self.force_val, (n, e, 12)),
            dict(self.extra),
        )

    def exo(self) -> np.ndarray:
        n, e = self.n_steps, self.n_engines
        ex = np.zeros((n, e, NEX))
        ex[:, :, 0:4] = self.w
        ex[:, :, E_PS3F] = self.ps3_factor
        ex[:, :, E_EFF] = self.eff_loss
        ex[:, :, E_KILL] = self.kill
        ex[:, :, E_START] = self.start_drive
        ex[:, :, E_T5ADD] = self.t5_add
        return np.ascontiguousarray(ex)


def steady_state(pla_deg: float, *, t_amb=288.15, p_amb=101325.0, mach=0.0, n_engines=1, n2c=None, pp=None):
    """A lit fixture state near equilibrium at a given corrected N2 (default: the PLA schedule's demand)."""
    pp = plant_params() if pp is None else pp
    pt = plant_tables()
    cfg = fixture_config()
    tb = cfg.tables
    a8 = float(np.interp(np.deg2rad(pla_deg), tb.a8_pla_x, tb.a8_pla_y)) * cfg.p[_pidx("a8_scale")]
    a8f = 0.0  # the scheduled nozzle is the fixture's nominal (deviations from it act on N1 and T5)
    if n2c is None:  # plant corrected speed whose N2/sqrt(theta25) equals the scheduled demand (bisection)
        dem = min(
            float(np.interp(np.deg2rad(pla_deg), tb.n2c_pla_x, tb.n2c_pla_y)), 0.765
        )  # N1-limited at IRP

        def c25(z):
            n1z = float(np.interp(z, pt.n1_x, pt.n1_y)) * (1 + pp[PP_K_A8N1] * a8f)
            return z / np.sqrt(float(np.interp(n1z, pt.t25_x, pt.t25_y)))

        lo, hi = 0.3, 1.08
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if c25(mid) < dem else (lo, mid)
        n2c = 0.5 * (lo + hi)
    m2 = 1.0 + 0.2 * mach * mach
    t2 = t_amb * m2
    p2 = p_amb * m2**3.5
    sth = np.sqrt(t2 / 288.15)
    de = p2 / 101325.0
    wfc = float(np.interp(n2c, pt.wf_x, pt.wf_y))
    n1c = float(np.interp(n2c, pt.n1_x, pt.n1_y)) * (1 + pp[PP_K_A8N1] * a8f)
    x = np.zeros(NX)
    x[X_N2] = n2c * sth * pp[PP_N2R]
    x[X_N1] = n1c * sth * pp[PP_N1R]
    x[X_WF] = wfc * pp[PP_WREF] * de * sth
    x[X_PS3] = p2 * float(np.interp(n2c, pt.pr_x, pt.pr_y))
    x[X_PS3_OUT] = x[X_PS3]
    x[X_T5] = t2 * float(np.interp(n2c, pt.t5_x, pt.t5_y)) * (1 - pp[PP_K_A8T5] * a8f)
    x[X_T5TC_A] = x[X_T5]
    x[X_T5TC_B] = x[X_T5] + pp[PP_T5B_OFFSET]
    x[X_A8] = a8
    x[X_LIT] = 1.0
    x[X_T25] = t2 * float(np.interp(n1c, pt.t25_x, pt.t25_y))
    x[X_T2] = t2
    x[X_FVG] = float(np.interp(n1c, tb.fvg_x, tb.fvg_y))
    x[X_CVG] = float(np.interp(n2c, tb.cvg_x, tb.cvg_y))
    return np.tile(x, (n_engines, 1))


def _pidx(name: str) -> int:
    from phalanx.fadec.layout import P_LAYOUT

    return P_LAYOUT.index[name]


@dataclass
class LoopResult:
    xs: np.ndarray  # [n+1, e, NX] plant truth (x_0 .. x_n)
    cmdf: np.ndarray  # [n, e, NOF] M08 float outputs per step
    cmdi: np.ndarray  # [n, e, NOI] M08 int outputs per step
    sel: np.ndarray  # [n, e, NS] validated values used by the law
    f: np.ndarray  # final M08 state
    i: np.ndarray
    lanes: np.ndarray  # [n, cap, e, 13] lane buffers as M08 received them at each step
    nfr: np.ndarray  # [n] frames M08 processed at each step
    f0: np.ndarray  # initial M08 state
    i0: np.ndarray

    @property
    def wf_cmd(self):
        return self.cmdf[:, :, O_WF]

    @property
    def limiter(self):
        return self.cmdi[:, :, O_LIMITER]

    @property
    def faults(self):
        return self.cmdi[:, :, O_FAULTS]


def initial_fadec_state(cfg: FadecConfig, x0: np.ndarray):
    """M08 state for a run that starts at plant state x0 (commands = the plant's current actuator values)."""
    e = x0.shape[0]
    from phalanx.fadec.layout import F_A8_CMD, F_CVG_CMD, F_FVG_CMD, F_WF_CMD

    f = np.zeros((e, NF), dtype=np.float64)
    i = np.zeros((e, NI), dtype=np.int64)
    f[:, F_WF_CMD] = x0[:, X_WF]
    f[:, F_A8_CMD] = x0[:, X_A8]
    f[:, F_FVG_CMD] = x0[:, X_FVG]
    f[:, F_CVG_CMD] = x0[:, X_CVG]
    return f, i


def closed_loop(
    sc: Scenario,
    *,
    cfg: FadecConfig | None = None,
    x0: np.ndarray | None = None,
    pp: np.ndarray | None = None,
    state: tuple[np.ndarray, np.ndarray] | None = None,
    dtype=np.float64,
    p_override: np.ndarray | None = None,
    pt: PlantTables | None = None,
    fine_lanes: bool = False,
) -> LoopResult:
    """Run the fused fixture loop for `sc` (see module docstring)."""
    cfg = fixture_config() if cfg is None else cfg
    cap = capacity(cfg.clock)
    s = sc.filled(cap)
    pp = plant_params() if pp is None else pp
    if x0 is None:
        x0 = steady_state(float(s.pla_deg[0, 0]), t_amb=float(s.t_amb[0]), p_amb=float(s.p_amb[0]),
                          mach=float(s.mach[0]), n_engines=s.n_engines, pp=pp)  # fmt: skip
    f, i = initial_fadec_state(cfg, x0) if state is None else state
    nfr, wts = frame_table(cfg.clock, s.n_steps, cap)
    qs, qo, qstep, qlo, qhi = lane_quantiser()
    if (
        fine_lanes
    ):  # idealised acquisition: no native-step quantisation (isolates the controller's own response)
        qstep = np.full_like(qstep, 1e-9)
    p = cfg.p if p_override is None else p_override
    f = f.astype(dtype)
    x0 = x0.astype(dtype)
    p = p.astype(np.result_type(p.dtype, dtype))
    pla = np.ascontiguousarray(np.deg2rad(s.pla_deg)).astype(dtype)
    f2, i2, xs, cmdf, cmdi, sel, lanes_in, nfr_in = _closed_loop(
        f, i, p, cfg.tables, cfg.cfg, cfg.dt, x0, pp.astype(dtype), plant_tables() if pt is None else pt,
        pla, s.t_amb.astype(dtype), s.p_amb.astype(dtype), s.mach.astype(dtype), s.exo().astype(dtype),
        s.ab_fault, s.at_engage, s.at_n1_cmd.astype(dtype), nfr, wts,
        s.lane_noise_eu.astype(dtype), s.lane_bias.astype(dtype), s.force_mask, s.force_val.astype(dtype),
        qs, qo, qstep, qlo, qhi,
    )  # fmt: skip
    return LoopResult(xs, cmdf, cmdi, sel, f2, i2, lanes_in, nfr_in, f.copy(), i.copy())


# ------------------------------------------------------------------ B2 estimator and helpers
def b2_lag(ff: np.ndarray, n2: np.ndarray, rate_hz: float, max_lag_s: float = 10.0) -> float:
    """Pre-registered B2 estimator (round 2, `phalanx.validation.battery.stats._lag`): lag [s] of the peak
    cross-correlation of first differences of z-scored FF and N2; positive = N2 lags FF."""
    from phalanx.validation.battery.stats import _lag

    return float(_lag(np.diff(ff), np.diff(n2), round(max_lag_s * rate_hz), rate_hz))


def first_order(x: np.ndarray, tau: float, dt: float) -> np.ndarray:
    """Discrete first-order lag (exact ZOH pole) - a fixture FF meter (M12 role, tau_FFs 0.218 s proxy);
    tau <= 0 is an ideal meter."""
    if tau <= 0.0:
        return np.array(x, copy=True)
    a = np.exp(-dt / tau)
    y = np.empty_like(x)
    y[0] = x[0]
    for k in range(1, x.size):
        y[k] = a * y[k - 1] + (1 - a) * x[k]
    return y


# ------------------------------------------------------------------ System wrappers (A7: same semantics)
def _fixture_params(name: str) -> ParamSet:
    return ParamSet(name, {"fixture": Param(1.0, "1", "ASSUMPTION", FIXTURE_SOURCE)})


class FixtureScenario(ModuleBase):
    """TEST FIXTURE: exogenous inputs of a `Scenario` as ports (PLA, P0, A/T, plant exogenous)."""

    version = "0.0.0"
    rate = RG_240

    def __init__(self, id: str, sc: Scenario, cap: int, *, autothrottle: bool = False):
        e = sc.n_engines
        self.ports_out = (
            Port("pla", "rad", "<f8", (e,)),
            Port("p0", "Pa", "<f8", ()),
            Port("t_amb", "K", "<f8", ()),
            Port("mach", "1", "<f8", ()),
            Port("ex", "1", "<f8", (e, NEX)),
            Port("at_engage", "1", "<i8", ()),
            Port("at_n1_cmd", "1", "<f8", (e,)),
        )
        self.state_schema = StateSchema("fixture.scenario", 1, (Field("k", "<i8", ()),))
        super().__init__(id, _fixture_params("fixture.scenario"))
        self.sc = sc.filled(cap)
        self._ex = self.sc.exo()
        self._pla = np.deg2rad(self.sc.pla_deg)

    def init(self, params, keys):
        return {"k": np.array(0, dtype=np.int64)}

    def _row(self, k):
        s = self.sc
        return {
            "pla": self._pla[k].copy(),
            "p0": np.array(s.p_amb[k]),
            "t_amb": np.array(s.t_amb[k]),
            "mach": np.array(s.mach[k]),
            "ex": self._ex[k].copy(),
            "at_engage": np.array(s.at_engage[k], dtype=np.int64),
            "at_n1_cmd": s.at_n1_cmd[k].copy(),
        }

    def initial_outputs(self, state):
        return self._row(0)

    def step(self, state, inputs, t, dt):
        k = latest_truth_step(int(t))
        return {"k": np.array(k + 1, dtype=np.int64)}, self._row(k)


class FixturePlant(ModuleBase):
    """TEST FIXTURE plant (see module docstring), consuming the catalogue `fadec.*` commands."""

    version = "0.0.0"
    rate = RG_240

    def __init__(self, id: str, x0: np.ndarray, *, ab_fault=None, pp=None):
        e = x0.shape[0]
        self.ports_in = (
            Port("wf_cmd", "kg/s", "<f8", (e,)),
            Port("wf_ab_cmd", "kg/s", "<f8", (e,)),
            Port("a8_cmd", "m**2", "<f8", (e,)),
            Port("vg_cmd", "rad", "<f8", (e, 2)),
            Port("ignition", "1", "<i8", (e,)),
            Port("ab_enable", "1", "<i8", (e,)),
            Port("t_amb", "K", "<f8", ()),
            Port("p_amb", "Pa", "<f8", ()),
            Port("mach", "1", "<f8", ()),
            Port("ex", "1", "<f8", (e, NEX)),
        )
        self.ports_out = (Port("x", "1", "<f8", (e, NX)),)  # TEST FIXTURE: mixed-unit truth vector
        self.state_schema = StateSchema("fixture.plant", 1, (Field("x", "<f8", (e, NX)),))
        #: catalogue bindings of the command inputs (what the real M07 declares in its ports.py)
        self.bindings = {
            n: f"fadec.{n}" for n in ("wf_cmd", "wf_ab_cmd", "a8_cmd", "vg_cmd", "ignition", "ab_enable")
        }
        super().__init__(id, _fixture_params("fixture.plant"))
        self._x0 = np.array(x0, dtype=np.float64)
        self._ab_fault = np.zeros(e, np.int64) if ab_fault is None else np.asarray(ab_fault, np.int64)
        self._pp = plant_params() if pp is None else pp
        self._pt = plant_tables()

    def init(self, params, keys):
        return {"x": self._x0.copy()}

    def initial_outputs(self, state):
        return {"x": state["x"].copy()}

    def step(self, state, inputs, t, dt):
        x = state["x"]
        xn = np.empty_like(x)
        for e in range(x.shape[0]):
            xn[e] = plant_step(
                x[e],
                self._pp,
                self._pt,
                float(inputs["wf_cmd"][e]),
                float(inputs["wf_ab_cmd"][e]),
                float(inputs["a8_cmd"][e]),
                float(inputs["vg_cmd"][e, 0]),
                float(inputs["vg_cmd"][e, 1]),
                int(inputs["ignition"][e]),
                int(inputs["ab_enable"][e]),
                float(inputs["t_amb"]),
                float(inputs["p_amb"]),
                float(inputs["mach"]),
                np.ascontiguousarray(inputs["ex"][e]),
                int(self._ab_fault[e]),
            )
        return {"x": xn}, {"x": xn.copy()}


class FixtureLanes(ModuleBase):
    """TEST FIXTURE in-loop lane source: frames of the FADEC clock in [t_k, t_{k+1}) from x_k (delayed edge)
    and
    x_{k+1}; outputs the lane buffers M08 reads at step k+1 (delayed back-edge)."""

    version = "0.0.0"
    rate = RG_240

    def __init__(self, id: str, clock, n_engines: int, sc: Scenario):
        e = n_engines
        cap = capacity(clock)
        self.ports_in = (Port("x_now", "1", "<f8", (e, NX)), Port("x_prev", "1", "<f8", (e, NX)))
        # M13's port names and buffer shapes (`lane_<id>`, (cap,) for one engine), so the fixture is a drop-in
        # stand-in for `acquisition.LaneAcquisition`
        self.shape = lane_shape(e, clock)
        self.names = {name: lane_port_name(cid) for name, cid, _u in LANE_PORTS}
        self.ports_out = tuple(
            Port(self.names[name], unit, "<f8", self.shape, clock) for name, _c, unit in LANE_PORTS
        )
        self.state_schema = StateSchema("fixture.lanes", 1, (Field("n_next", "<i8", ()),))
        super().__init__(id, _fixture_params("fixture.lanes"))
        self.clock, self.cap, self.e = clock, cap, e
        self.sc = sc.filled(cap)
        self.q = lane_quantiser()

    def init(self, params, keys):
        return {"n_next": np.array(self.clock.first_index_at_or_after(0), dtype=np.int64)}

    def initial_outputs(self, state):
        return {self.names[name]: np.zeros(self.shape) for name, _c, _u in LANE_PORTS}

    def step(self, state, inputs, t, dt):
        k = latest_truth_step(int(t))
        t0, t1 = truth_step_times_ns(np.array([k, k + 1], dtype=np.int64))
        ss = samples_for_steps(self.clock, int(state["n_next"]), np.array([t0]), np.array([t1]))
        out = {name: np.zeros((self.cap, self.e)) for name, _c, _u in LANE_PORTS}  # reshaped on return
        if ss.times.size:
            _, w = truth_interp_weights(ss.times)
            s = self.sc
            for slot in range(ss.times.size):
                for e in range(self.e):
                    v = lane_values(
                        np.ascontiguousarray(inputs["x_prev"][e]),
                        np.ascontiguousarray(inputs["x_now"][e]),
                        float(w[slot]),
                        *self.q,
                        s.lane_noise_eu[k, slot, e],
                        s.lane_bias[k, e],
                        s.force_mask[k, e],
                        s.force_val[k, e],
                    )
                    for name, _c, _u in LANE_PORTS:
                        out[name][slot, e] = v[LANE_SLOT[name]]
        shaped = {self.names[name]: v.reshape(self.shape) for name, v in out.items()}
        return {"n_next": np.array(ss.next_index, dtype=np.int64)}, shaped


__all__ = [
    "FIXTURE_SOURCE",
    "FixtureLanes",
    "FixturePlant",
    "FixtureScenario",
    "FrameDriver",
    "LoopResult",
    "Scenario",
    "ar1_disturbance",
    "b2_lag",
    "closed_loop",
    "first_order",
    "fixture_config",
    "fixture_params",
    "frame_table",
    "has_code",
    "lanes_from_state",
    "leadlag",
    "steady_state",
]


# ------------------------------------------------------------------ open-loop frame driver (unit tests)
def lanes_from_state(x: np.ndarray, *, quantise: bool = True) -> np.ndarray:
    """Lane vector [13] (SI) of a fixture plant state row `x` (both lanes of each sensor equal)."""
    qs, qo, qstep, qlo, qhi = lane_quantiser()
    if not quantise:
        qstep = np.full_like(qstep, 1e-9)
    z = np.zeros(12)
    return lane_values(x, x, 0.0, qs, qo, qstep, qlo, qhi, z, z, np.zeros(12, np.int64), z)


class FrameDriver:
    """Drives the compiled M08 kernel one FADEC frame per call with scripted lanes (TEST FIXTURE helper)."""

    def __init__(
        self, cfg: FadecConfig | None = None, *, n_engines: int = 1, wf0: float = 0.0, a8_0: float = 0.2
    ):
        from phalanx.fadec.layout import F_A8_CMD, F_WF_CMD

        self.cfg = fixture_config() if cfg is None else cfg
        self.f = np.zeros((n_engines, NF))
        self.i = np.zeros((n_engines, NI), dtype=np.int64)
        self.f[:, F_WF_CMD] = wf0
        self.f[:, F_A8_CMD] = a8_0
        self.e = n_engines
        self.outf: np.ndarray | None = None
        self.outi: np.ndarray | None = None

    def frame(
        self, lanes: np.ndarray, *, pla_deg: float = 60.0, p0: float = 101325.0, at_engage=0, at_cmd=0.0
    ):
        c = self.cfg
        ln = np.zeros((1, 1, self.e, 13))
        ln[0, 0, :, :] = lanes
        self.f, self.i, self.outf, self.outi = fadec_block(
            self.f,
            self.i,
            c.p,
            c.tables,
            c.cfg,
            c.dt,
            np.full((1, self.e), np.deg2rad(pla_deg)),
            np.array([p0]),
            np.array([at_engage], dtype=np.int64),
            np.full((1, self.e), float(at_cmd)),
            ln,
            np.ones(1, dtype=np.int64),
        )
        return self

    # convenience views (engine 0)
    def fi(self, idx: int) -> float:
        return float(self.f[0, idx])

    def ii(self, idx: int) -> int:
        return int(self.i[0, idx])

    @property
    def wf(self) -> float:
        return float(self.outf[0, 0, O_WF])

    @property
    def limiter(self) -> int:
        return int(self.outi[0, 0, O_LIMITER])

    @property
    def faults(self) -> int:
        return int(self.outi[0, 0, O_FAULTS])

    def vstate(self, s: int) -> int:
        from phalanx.fadec.layout import O_VSTATE

        return int(self.outi[0, 0, O_VSTATE + s])

    def sel(self, s: int) -> float:
        return float(self.f[0, F_SEL + s])


def has_code(mask: int, code: str) -> bool:
    from phalanx.fadec.codes import active_codes

    return code in active_codes(mask)


# ------------------------------------------------------------------ keyed process disturbances (M03 role)
DISTURBANCE_STREAM = "fixture_dist"


def ar1_disturbance(
    n: int, tau_s: float, sd: float, *, sortie: int = 1, serial: str = "E1", channel: int = 0
):
    """AR(1) process disturbance [n] from an identity-keyed stream (AD-37 style; TEST FIXTURE stand-in
    for M03's `env.w_engine` column `channel`): exact discrete pole exp(-dt/tau), stationary SD `sd`."""
    from phalanx.core.rng import KeyPath, RngService, StreamDecl, StreamRegistry, Variate

    reg = StreamRegistry(
        [
            StreamDecl(
                DISTURBANCE_STREAM, f"w{channel}", ("scenario", "tail", "serial", "sortie"), Variate.NORMAL,
                4096, "tests/fadec_fixture.py", "fixture process disturbance",
            )
        ]
    )  # fmt: skip
    keys = RngService(0x1B3B, reg).scope(KeyPath.of(scenario="w13b", tail="T1", serial=serial, sortie=sortie))
    e = keys.stream(DISTURBANCE_STREAM, f"w{channel}").draws(0, n)
    phi = float(np.exp(-DT / tau_s))
    return _ar1(e * sd * np.sqrt(1.0 - phi * phi), phi)


@njit(**_JIT)
def _ar1(innov, phi):
    out = np.empty_like(innov)
    a = 0.0
    for k in range(innov.shape[0]):
        a = phi * a + innov[k]
        out[k] = a
    return out


def leadlag(r: LoopResult, *, e: int = 0, ff_meter_tau: float = 0.218, skip_s: float = 20.0):
    """(truth lag at 20 Hz, B2 lag at 4 Hz with a fixture FF meter) of FF -> N2 in s; negative = FF lags N2.

    Truth: actual metered Wf vs N2 at 20 Hz (12-step decimation). B2: the pre-registered round-2 estimator on
    4 Hz samples of an FF-meter-lagged Wf (tau_FFs 0.218 s, the M12 role) and N2.
    """
    n2 = r.xs[1:, e, X_N2]
    wf = r.xs[1:, e, X_WF]
    k0 = int(skip_s * 240)
    l20 = b2_lag(wf[k0::12], n2[k0::12], 20.0)
    ffm = first_order(wf, ff_meter_tau, DT)
    l4 = b2_lag(ffm[k0::60], n2[k0::60], 4.0)
    return l20, l4


def fast_band_r(
    r: LoopResult, *, e: int = 0, ff_meter_tau: float = 0.218, rate_hz: float = 4.0, skip_s: float = 20.0
):
    """B1 fast-band (> 0.2 Hz) correlations r(N1,FF), r(N2,FF), r(N1,N2) at `rate_hz` on an FF-meter-lagged Wf
    (pre-registered split: `phalanx.validation.battery.filters.lowpass`, fc 0.2 Hz). Real 652 targets: N1-FF
    +0.65, N2-FF +0.67, N1-N2 +0.47 (docs/behavioural_targets.md)."""
    from phalanx.validation.battery.filters import lowpass

    k0 = int(skip_s * 240)
    dec = round(240 / rate_hz)
    ff = first_order(r.xs[1:, e, X_WF], ff_meter_tau, DT)[k0::dec]
    n1 = r.xs[1:, e, X_N1][k0::dec]
    n2 = r.xs[1:, e, X_N2][k0::dec]

    def fast(x):
        return x - lowpass(x, rate_hz, 0.2)

    f1, f2, ff_ = fast(n1), fast(n2), fast(ff)
    return (
        float(np.corrcoef(f1, ff_)[0, 1]),
        float(np.corrcoef(f2, ff_)[0, 1]),
        float(np.corrcoef(f1, f2)[0, 1]),
    )
