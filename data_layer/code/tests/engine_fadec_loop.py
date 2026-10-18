"""TEST FIXTURE harness: the REAL M07 engine kernel in closed loop with the REAL M08 FADEC kernel (W2.1b).

Only the lane source is a stand-in (labelled TEST FIXTURE; the M12/M13 role, which W2.1a wires in the
integrated loop): at the FADEC frame instants in [t_k, t_{k+1}) it interpolates the sensor outputs between the
end of step k-1 and the end of step k (A-W0.2-2), quantises them to the dictionary native step in EU with span
saturation and converts back to SI (`fadec_fixture.lane_values` semantics). The sensor dynamics mirror M12's
classes with M12's own parameters (`configs/tejas/params/M12.yaml`): T1 RTD and T25/T5 thermocouples are
first-order lags with tau = tau_ref (W2 / W_ref)^-n (A-W1.6-3/-4/-5), PS3 a first-order transducer lag, speeds
none; the UV flame detector reads 1 when the M07 afterburner state is LIT (the ENG.AB_LIT lane semantics of
the M12 `uv_flame_detector` class). First-order lags use M12's exact first-order-hold update.

Semantics are the System's (`phalanx.fadec.coupling`): M08 at step k processes the frames of [t_{k-1}, t_k)
from the lane buffers produced at step k-1 (delayed back-edge), M07 consumes M08's commands of step k on a
forward edge. Exogenous engine inputs (ambient, Mach, disturbances, bleed, PTO, fuel temperature, health) are
given per step. `kill[k, e] = 1` puts out the main-burner flame of engine e at the start of step k (the M07
flameout state perturbation, the `eng.fault_inject` mode `flameout`).

The loop is one `@njit(cache=False)` function (a caller of kernels in other files must not be cached: Numba's
cache does not track callees in other files; W1.2 / core README pitfall)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

import fadec_fixture as fx
from phalanx.dictionary.params import load_params
from phalanx.engine.kernel import engine_kernel
from phalanx.engine.layout import (
    AB_LIT,
    I_FLAME,
    NU,
    NUI,
    NY,
    NYI,
    U_A8,
    U_NAMES,
    U_PS,
    U_VG1,
    U_VG2,
    U_WF,
    U_WFAB,
    UI_ABEN,
    UI_IGN,
    Y_N1,
    Y_N2,
    Y_PS3,
    Y_T2,
    Y_T5,
    Y_T25,
    Y_W2,
)
from phalanx.engine.module import EngineModule
from phalanx.engine.sim import state_from_x
from phalanx.engine.steady import SteadyResult, TrimCondition
from phalanx.fadec import FadecConfig, load_fadec_params
from phalanx.fadec.kernel import fadec_block
from phalanx.fadec.layout import (
    F_A8_CMD,
    F_CVG_CMD,
    F_FVG_CMD,
    F_WF_CMD,
    NF,
    NI,
    NOF,
    NOI,
    O_A8,
    O_AB_EN,
    O_CVG,
    O_FVG,
    O_IGN,
    O_WF,
    O_WF_AB,
)
from phalanx.fadec.ports import capacity

_NOCACHE = {"cache": False, "fastmath": False, "error_model": "numpy", "nogil": True}
DT = 1.0 / 240.0
N1R = 13270.0 * 2.0 * np.pi / 60.0
N2R = 16810.0 * 2.0 * np.pi / 60.0
PSI = 6894.757293168361
LBH = 3600.0 / 0.45359237  # kg/s -> lb/h

# sensor-lag states per engine: T1 (RTD), T25 (TC), PS3 (transducer), T5 harness A, T5 harness B, and the
# previous truth inputs of each (first-order-hold update)
S_T1, S_T25, S_PS3, S_T5A, S_T5B = range(5)
NS_LAG = 5
# lag parameters: [tau, w_ref, n_exp, w_min_frac] per lag (n_exp = 0: constant tau)
_M12_SETS = ("rtd_inlet", "tc_t25", "ps3_transducer", "tc_t5", "tc_t5")


def m12_lag_params() -> np.ndarray:
    """(5, 4) [tau, w_ref, n_exp, w_min_frac] of the T1/T25/PS3/T5A/T5B lags from M12.yaml (M12's values)."""
    ps = load_params("M12")
    out = np.zeros((NS_LAG, 4))
    for k, name in enumerate(_M12_SETS):
        s = ps[name]
        out[k, 0] = float(s.value("tau"))
        if "w_ref" in s:
            out[k, 1] = float(s.value("w_ref"))
            out[k, 2] = float(s.value("n_exp"))
            out[k, 3] = float(s.value("w_min_frac"))
        else:
            out[k, 1], out[k, 2], out[k, 3] = 1.0, 0.0, 1.0
    return out


T1_DEICE = 0.2  # K, M12 rtd_inlet deice_bias (A-W1.6-3)


@njit(**_NOCACHE)
def _tau(lp, k, w2):
    r = w2 / lp[k, 1]
    if lp[k, 2] == 0.0:
        return lp[k, 0]
    if r < lp[k, 3]:
        r = lp[k, 3]
    return lp[k, 0] * np.exp(-lp[k, 2] * np.log(r))


@njit(**_NOCACHE)
def _foh(y, q0, q1, tau, h):
    """M12's exact first-order-hold step of a first-order lag (kernel.py, D_sensor)."""
    a = np.exp(-h / tau)
    return q1 + (y - q0) * a + (q0 - q1) * (tau / h) * (1.0 - a)


@njit(**_NOCACHE)
def _truth_row(y, t5b_off):
    """Truth inputs of the five lags from an M07 output row: T1, T25, PS3, T5 (A), T5 (B)."""
    out = np.empty(NS_LAG)
    out[S_T1] = y[Y_T2] + T1_DEICE
    out[S_T25] = y[Y_T25]
    out[S_PS3] = y[Y_PS3]
    out[S_T5A] = y[Y_T5]
    out[S_T5B] = y[Y_T5] + t5b_off
    return out


@njit(**_NOCACHE)
def _sensor_vec(y, lag, lit):
    """Fixture lane-source vector in `fadec_fixture` slot order (X_N1 .. X_T5TC_B; X_ABLIT for the UV
    detector)."""
    x = np.zeros(fx.NX)
    x[fx.X_N1] = y[Y_N1]
    x[fx.X_N2] = y[Y_N2]
    x[fx.X_T2] = lag[S_T1]
    x[fx.X_T25] = lag[S_T25]
    x[fx.X_PS3_OUT] = lag[S_PS3]
    x[fx.X_T5TC_A] = lag[S_T5A]
    x[fx.X_T5TC_B] = lag[S_T5B]
    x[fx.X_ABLIT] = lit
    return x


@njit(**_NOCACHE)
def _loop(f, i, p, tb, cfg, dtf, ef, ei, ebuf, ep, etb, edt, en_sub, en_delay, pla, at_eng, at_cmd, uext,
          kill, nfr, wts, lp, t5b_off, lane_bias, qs, qo, qstep, qlo, qhi, y0, yi0):  # fmt: skip
    n = pla.shape[0]
    n_eng = ef.shape[0]
    cap = wts.shape[1]
    lanes = np.zeros((1, cap, n_eng, 13))
    ys = np.empty((n, n_eng, NY))
    yis = np.empty((n, n_eng, NYI), dtype=np.int64)
    cmdf = np.empty((n, n_eng, NOF))
    cmdi = np.empty((n, n_eng, NOI), dtype=np.int64)
    lagv = np.empty((n_eng, NS_LAG))
    q0 = np.empty((n_eng, NS_LAG))
    xprev = np.empty((n_eng, fx.NX))
    yprev = y0.copy()
    for e in range(n_eng):
        tr = _truth_row(y0[e], t5b_off)
        for s in range(NS_LAG):
            lagv[e, s] = tr[s]
            q0[e, s] = tr[s]
        lit0 = 1.0 if yi0[e, 0] == AB_LIT else 0.0
        xprev[e] = _sensor_vec(y0[e], lagv[e], lit0)
    zab = np.zeros((n_eng, 2))
    zz = np.zeros(12)
    zi = np.zeros(12, dtype=np.int64)
    for k in range(n):
        cnt = np.zeros(1, dtype=np.int64)
        if k > 0:
            cnt[0] = nfr[k - 1]
        p0 = uext[k : k + 1, 0, U_PS].copy()
        f, i, of, oi = fadec_block(f, i, p, tb, cfg, dtf, pla[k : k + 1], p0, at_eng[k : k + 1],
                                   at_cmd[k : k + 1], lanes, cnt)  # fmt: skip
        cmdf[k] = of[0]
        cmdi[k] = oi[0]
        u = uext[k : k + 1].copy()
        ui = np.zeros((1, n_eng, NUI), dtype=np.int64)
        for e in range(n_eng):
            u[0, e, U_WF] = of[0, e, O_WF]
            u[0, e, U_WFAB] = of[0, e, O_WF_AB]
            u[0, e, U_A8] = of[0, e, O_A8]
            u[0, e, U_VG1] = of[0, e, O_FVG]
            u[0, e, U_VG2] = of[0, e, O_CVG]
            ui[0, e, UI_IGN] = oi[0, e, O_IGN]
            ui[0, e, UI_ABEN] = oi[0, e, O_AB_EN]
            if kill[k, e] == 1:
                ei[e, I_FLAME] = 0
        ef, ei, ebuf, y, yi, _ = engine_kernel(
            ef, ei, ebuf, ep, etb, u, ui, zab, edt, en_sub, en_delay, False
        )
        ys[k] = y[0]
        yis[k] = yi[0]
        xnew = np.empty((n_eng, fx.NX))
        for e in range(n_eng):
            tr = _truth_row(y[0, e], t5b_off)
            w2 = y[0, e, Y_W2]
            for s in range(NS_LAG):
                lagv[e, s] = _foh(lagv[e, s], q0[e, s], tr[s], _tau(lp, s, w2), DT)
                q0[e, s] = tr[s]
            lit = 1.0 if yi[0, e, 0] == AB_LIT else 0.0
            xnew[e] = _sensor_vec(y[0, e], lagv[e], lit)
        for s in range(nfr[k]):
            for e in range(n_eng):
                lanes[0, s, e] = fx.lane_values(xprev[e], xnew[e], wts[k, s], qs, qo, qstep, qlo, qhi, zz,
                                                lane_bias[e], zi, zz)  # fmt: skip
                lanes[0, s, e, 12] = xnew[e, fx.X_ABLIT]
        xprev = xnew
        yprev = y[0]
    _ = yprev
    return f, i, ef, ei, ebuf, ys, yis, cmdf, cmdi


@dataclass
class LoopRun:
    y: np.ndarray  # (n, e, NY) M07 outputs (values at the end of each step)
    yi: np.ndarray  # (n, e, NYI)
    cmdf: np.ndarray  # (n, e, NOF) M08 float outputs per step
    cmdi: np.ndarray  # (n, e, NOI)
    f: np.ndarray  # final M08 state
    i: np.ndarray
    eng: tuple  # final M07 state (f, i, buf)

    def ch(self, name: str, e: int = 0) -> np.ndarray:
        from phalanx.engine.layout import Y_NAMES

        return self.y[:, e, Y_NAMES.index(name)]


def isa(h_m: float) -> tuple[float, float]:
    """ISA static temperature [K] and pressure [Pa] at geopotential altitude h_m
    (troposphere/stratosphere)."""
    if h_m <= 11000.0:
        t = 288.15 - 0.0065 * h_m
        return t, 101325.0 * (t / 288.15) ** 5.255877
    return 216.65, 22632.06 * float(np.exp(-(h_m - 11000.0) / 6341.62))


def fadec_kwargs(cfg: FadecConfig, trim: SteadyResult, n_engines: int = 1) -> dict:
    """M08 initial commands from an M07 trim (W2.1 F1): what `Fadec(initial_wf=..., ...)` takes."""
    u = trim.u
    return {
        "initial_wf": np.full(n_engines, u[U_WF]),
        "initial_a8": np.full(n_engines, u[U_A8]),
        "initial_vg": np.tile([u[U_VG1], u[U_VG2]], (n_engines, 1)),
    }


def run(
    eng: EngineModule,
    trim: SteadyResult,
    pla_deg,
    *,
    n: int,
    cfg: FadecConfig | None = None,
    condition: TrimCondition | None = None,
    t_s=None,
    p_s=None,
    mach=None,
    w=None,
    kill=None,
    t5b_off: float = 0.0,
    lane_bias=None,
    n_engines: int = 1,
    fine_lanes: bool = False,
    cont: LoopRun | None = None,
    fadec_f: np.ndarray | None = None,
) -> LoopRun:
    """Closed loop for `n` steps from `trim` (engine state and M08 initial commands), PLA `pla_deg` (scalar or
    (n,)), ambient from `condition` unless per-step `t_s`/`p_s`/`mach` arrays are given, disturbances `w`
    (n, 5) or (n, e, 5). `fine_lanes` removes the native-step quantisation (idealised acquisition, for
    linear-stability measurements where a quantisation limit cycle would mask the decay). `cont` continues a
    previous run from its final M07/M08 states and outputs (the sensor lags restart in steady state at the
    seam); `fadec_f` replaces the M08 float state at the start (e.g. a fault-injected copy)."""
    cfg = FadecConfig.build(load_fadec_params()) if cfg is None else cfg
    condition = TrimCondition() if condition is None else condition
    m = eng.model
    base = condition.inputs(m)
    uext = np.broadcast_to(base, (n, n_engines, NU)).copy()
    if t_s is not None:
        uext[:, :, U_NAMES.index("t_s")] = np.asarray(t_s, float).reshape(n, 1)
        uext[:, :, U_NAMES.index("t_fuel")] = np.asarray(t_s, float).reshape(n, 1) + (
            base[U_NAMES.index("t_fuel")] - base[U_NAMES.index("t_s")]
        )
    if p_s is not None:
        uext[:, :, U_PS] = np.asarray(p_s, float).reshape(n, 1)
    if mach is not None:
        uext[:, :, U_NAMES.index("mach")] = np.asarray(mach, float).reshape(n, 1)
    if w is not None:
        lo = U_NAMES.index("w_fuel_metering")
        uext[:, :, lo : lo + 5] = np.broadcast_to(np.asarray(w, float).reshape(n, -1, 5), (n, n_engines, 5))
    st = state_from_x(m, trim.x, n_engines=n_engines, w_fm=trim.u[U_NAMES.index("w_fuel_metering")])
    f = np.zeros((n_engines, NF))
    i = np.zeros((n_engines, NI), dtype=np.int64)
    kw = fadec_kwargs(cfg, trim, n_engines)
    f[:, F_WF_CMD] = kw["initial_wf"]
    f[:, F_A8_CMD] = kw["initial_a8"]
    f[:, F_FVG_CMD] = kw["initial_vg"][:, 0]
    f[:, F_CVG_CMD] = kw["initial_vg"][:, 1]
    cap = capacity(cfg.clock)
    nfr, wts = fx.frame_table(cfg.clock, n, cap)
    qs, qo, qstep, qlo, qhi = fx.lane_quantiser()
    if fine_lanes:  # idealised acquisition (no native-step quantisation): linear-stability measurements
        qstep = np.full_like(qstep, 1e-9)
    pla = np.deg2rad(np.broadcast_to(np.asarray(pla_deg, float).reshape(-1, 1), (n, n_engines))).copy()
    kill = np.zeros((n, n_engines), np.int64) if kill is None else np.asarray(kill, np.int64).reshape(n, -1)
    lb = (
        np.zeros((n_engines, 12))
        if lane_bias is None
        else np.asarray(lane_bias, float).reshape(n_engines, 12)
    )
    y0 = np.zeros((n_engines, NY))
    yi0 = np.zeros((n_engines, NYI), dtype=np.int64)
    ef0, ei0, eb0 = st.f, st.i, st.buf
    if cont is None:
        eng0 = eng.from_trim(trim) if trim.converged else None
        if eng0 is None:
            raise RuntimeError("trim did not converge")
        st0 = eng0.init(eng0.params, None)
        y0[:] = st0["y"]
        yi0[:] = st0["yi"]
    else:
        f, i = cont.f.copy(), cont.i.copy()
        ef0, ei0, eb0 = (a.copy() for a in cont.eng)
        y0[:] = cont.y[-1]
        yi0[:] = cont.yi[-1]
    if fadec_f is not None:
        f = np.array(fadec_f, dtype=np.float64, copy=True)
    out = _loop(
        f, i, cfg.p, cfg.tables, cfg.cfg, cfg.dt, ef0, ei0, eb0, m.p, m.tables, m.dt, m.n_sub, m.n_delay,
        pla, np.zeros(n, np.int64), np.zeros((n, n_engines)), uext, kill, nfr, wts, m12_lag_params(),
        float(t5b_off), lb, qs, qo, qstep, qlo, qhi, y0, yi0,
    )  # fmt: skip
    f2, i2, ef, ei, eb, ys, yis, cmdf, cmdi = out
    return LoopRun(ys, yis, cmdf, cmdi, f2, i2, (ef, ei, eb))


__all__ = ["LBH", "N1R", "N2R", "PSI", "LoopRun", "fadec_kwargs", "isa", "m12_lag_params", "run"]
