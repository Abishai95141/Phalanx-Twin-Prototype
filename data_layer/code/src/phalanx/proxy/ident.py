"""Proxy identification machinery (W2.4a, AD-34), self-tested on synthetic proxy flights (A2) before any real
data is used. W2.4a-1 builds and self-tests it; W2.4a-2 applies it to 687-CAL after the MF1 decision.

**Model.** The deterministic closed loop of the proxy chain without texture and without process
disturbances: M08 (governor, A/T loop) <-> M07 ``separate_fixed`` -> M12 (sensor dynamics) with the FADEC
lanes fed by the M12 outputs at the lane sample instants (no M13 lane quantisation or noise), driven by the
recorded inputs (lever, A/T state and N1 command, flight condition). The exogenous rows come from the same
replay producers as a proxy run (``build_proxy_system`` with an empty disturbance bank); the compiled core
calls the same kernels as the proxy loop (``fadec_block``, ``engine_kernel_sf``, ``m12_kernel``).

**Jacobians: central finite differences in log-parameters (DEVIATION from AD-22's complex step, reported).**
M08 and M07 are complex-step safe, and M12 is complex-step safe in its *own* parameters, but M12's sources
take real truth rows only (``sensors.kernel.interp_table``, ``total_pressure`` and the ``_tau`` flux floor
compare the truth value), so a complex perturbation cannot pass from M07 through M12 inside the closed
loop. Making those comparison sites use the real part (bitwise unchanged for real rows) is an M12 change
outside W2.4a's paths, proposed to the coordinator. Until then the Jacobian is a central difference with
relative step ``FD_STEP`` on log-parameters; the self-test checks it against a second step size (W0.6 M5:
differences fail on limiter switches, so identification windows must stay in governed regimes).

**Outputs.** The four recorded words per engine at the ACMS instants (sensor level, EU): N1 %, N2 %, EGT degC
(thermocouple word), FF lb/h (meter word).

**Parameters** (``PARAMS``): rotor inertias ``i_lp``/``i_hp`` (M07), governor gains ``gov_kp``/``gov_ki``
and the proxy autothrottle outer loop ``at_kp``/``at_ki``/``at_rate`` (M08), EGT word thermocouple time
constant ``tau_egt`` and FF meter time constant ``tau_ff`` (M12).

**Estimators.**
- :func:`fit_oe`: transient-weighted output error (AD-34: weights from ``engine.ident.transient_weights`` on
  the driving command, accel and decel windows separately), Levenberg-Marquardt on log-parameters
  (difference Jacobians, above); returns the estimate, the Gauss-Newton covariance from the residual scale,
  and the iteration log. The closed-loop simulation from the external commands is the **indirect** method
  (round-2 REPORT §8 H-c 2): it is consistent under process disturbances, which the residual absorbs.
- :func:`fit_direct`: the **direct** method for comparison: the plant (M07 + M12) driven by the *measured*
  fuel flow, fitted to N1/N2/EGT. Under closed-loop operation the measured fuel is correlated with the
  process disturbances, so the direct estimate is biased; the self-test shows it.
- :func:`residual_spectra`: per-engine fast-band residual PSD (Welch) and the cross-engine coherence of the
  residuals: the disturbance bank's per-unit vs aircraft-common split (AD-32) as seen through the plant.

Nothing here reads data; the caller passes records. No randomness.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from numba import njit

from phalanx.core.rng import KeyPath
from phalanx.core.sampling import samples_for_steps
from phalanx.core.time import truth_step_times_ns
from phalanx.engine.separate import SF_PI, engine_kernel_sf
from phalanx.fadec.kernel import fadec_block
from phalanx.fadec.params import P_LAYOUT
from phalanx.scenario.replay import ReplayInputs
from phalanx.sensors.kernel import PE_TAU, m12_kernel

from .config import RECORDED, ProxyConfig
from .loop import ProxyLoopGroup
from .system import build_proxy_system

#: identifiable parameters -> (owner, kernel name or recorded family whose word element carries tau)
PARAMS = {
    "i_lp": ("eng", "i_lp"),
    "i_hp": ("eng", "i_hp"),
    "gov_kp": ("fadec", "gov_kp"),
    "gov_ki": ("fadec", "gov_ki"),
    "at_kp": ("fadec", "at_kp"),
    "at_ki": ("fadec", "at_ki"),
    "at_rate": ("fadec", "at_rate"),
    "tau_egt": ("sens", "EGT"),
    "tau_ff": ("sens", "FF"),
}
FAMILIES = ("N1", "N2", "EGT", "FF")


@njit(cache=False, fastmath=False, error_model="numpy", nogil=True)
def _ident_core(
    f8, i8, p8, tb8, cfg8, dt8, pla, p0, at_eng, at_cmd, nfr, lanes0,
    f7, i7, b7, p7, tb7, uex, uiex, zab, dt7, nsub7, ndel7,
    ef, ei, cf, ci, el_i, el_p, ch_i, ch_p, tx, ty, toff, cols, kvec, bias, t_end, fu, dt12, nsub12,
    u_sig, u_eng, lane_sens, lane_eng, lane_slot, s_cnt, out_cols,
):  # fmt: skip
    """L truth steps of the deterministic closed loop; all float arrays share one dtype (float64, or
    complex128). Returns the M12 outputs of ``out_cols`` per step (L, n_out) and M08's
    actuator commands (L, E, 5: wf, wf_ab, a8, vg1, vg2). Lanes at step k are the M12 outputs of step k - 1 at
    the lane samples of that step."""
    L = nfr.shape[0]
    E = f8.shape[0]
    cap = lanes0.shape[0]
    n_u = u_sig.shape[0]
    n_lane = lane_sens.shape[0]
    n_out = out_cols.shape[0]
    out = np.zeros((L, n_out), dtype=p7.dtype)
    ucmd = np.zeros((L, E, 5), dtype=p7.dtype)
    lanes = np.zeros((1, cap, E, 13), dtype=p7.dtype)
    for s in range(cap):
        for e in range(E):
            for j in range(13):
                lanes[0, s, e, j] = lanes0[s, e, j]
    U = np.zeros((1, n_u), dtype=p7.dtype)
    for k in range(L):
        f8, i8, of, oi = fadec_block(
            f8, i8, p8, tb8, cfg8, dt8, pla[k : k + 1], p0[k : k + 1], at_eng[k : k + 1], at_cmd[k : k + 1],
            lanes, nfr[k : k + 1],
        )  # fmt: skip
        u = uex[k : k + 1].copy()
        ui = uiex[k : k + 1].copy()
        for e in range(E):
            for j in range(5):
                u[0, e, j] = of[0, e, j]
                ucmd[k, e, j] = of[0, e, j]
            ui[0, e, 0] = oi[0, e, 0]
            ui[0, e, 1] = oi[0, e, 1]
        f7, i7, b7, y, _yi, _aux = engine_kernel_sf(f7, i7, b7, p7, tb7, u, ui, zab, dt7, nsub7, ndel7, False)
        for c in range(n_u):
            U[0, c] = y[0, u_eng[c], u_sig[c]]
        ef, ei, cf, ci, S, _X = m12_kernel(
            ef, ei, cf, ci, el_i, el_p, ch_i, ch_p, tx, ty, toff, cols, kvec, U, bias[k : k + 1],
            t_end[k : k + 1], fu[k : k + 1], dt12, nsub12,
        )  # fmt: skip
        for j in range(n_out):
            out[k, j] = S[0, out_cols[j]]
        for s in range(cap):
            for e in range(E):
                for j in range(12):
                    lanes[0, s, e, j] = 0.0
        for r in range(s_cnt[k]):
            for j in range(n_lane):
                if lane_slot[j] >= 0:
                    lanes[0, r, lane_eng[j], lane_slot[j]] = S[0, lane_sens[j]]
    return out, ucmd


@njit(cache=False, fastmath=False, error_model="numpy", nogil=True)
def _plant_core(
    f7, i7, b7, p7, tb7, uex, uiex, zab, dt7, nsub7, ndel7, ucmd,
    ef, ei, cf, ci, el_i, el_p, ch_i, ch_p, tx, ty, toff, cols, kvec, bias, t_end, fu, dt12, nsub12,
    u_sig, u_eng, out_cols,
):  # fmt: skip
    """The open-loop plant (M07 + M12) driven by given actuator commands ``ucmd`` (L, E, 5): the direct
    method's model."""
    L = ucmd.shape[0]
    E = ucmd.shape[1]
    n_u = u_sig.shape[0]
    n_out = out_cols.shape[0]
    out = np.zeros((L, n_out), dtype=p7.dtype)
    U = np.zeros((1, n_u), dtype=p7.dtype)
    for k in range(L):
        u = uex[k : k + 1].copy()
        for e in range(E):
            for j in range(5):
                u[0, e, j] = ucmd[k, e, j]
        f7, i7, b7, y, _yi, _aux = engine_kernel_sf(
            f7, i7, b7, p7, tb7, u, uiex[k : k + 1], zab, dt7, nsub7, ndel7, False
        )
        for c in range(n_u):
            U[0, c] = y[0, u_eng[c], u_sig[c]]
        ef, ei, cf, ci, S, _X = m12_kernel(
            ef, ei, cf, ci, el_i, el_p, ch_i, ch_p, tx, ty, toff, cols, kvec, U, bias[k : k + 1],
            t_end[k : k + 1], fu[k : k + 1], dt12, nsub12,
        )  # fmt: skip
        for j in range(n_out):
            out[k, j] = S[0, out_cols[j]]
    return out


@dataclass
class IdentProblem:
    """One window prepared for identification (everything but the parameters)."""

    cfg: ProxyConfig
    rec: ReplayInputs
    n_steps: int
    args: dict = field(repr=False)
    out_cols: np.ndarray = field(repr=False)  # M12 columns of the recorded words, (family, engine) order
    conv: list = field(repr=False)  # EU conversions of out_cols
    s_step: np.ndarray = field(repr=False)  # ACMS sample -> truth step whose frame end follows it
    s_w: np.ndarray = field(repr=False)  # interpolation weight between the frame ends around the sample
    tau_cols: dict = field(repr=False)  # family -> element rows of its recorded word (M12 el_p)
    n_engines: int = 4

    @property
    def n_samples(self) -> int:
        return int(self.s_step.size)


def prepare(
    cfg: ProxyConfig,
    rec: ReplayInputs,
    *,
    fadec_params=None,
    bleed_kgs: np.ndarray | None = None,
    pto_w: float | None = None,
) -> IdentProblem:
    """Deterministic exogenous rows of a window: the proxy System's replay producers with an empty disturbance
    bank, run once; schedules of the FADEC frames, lane samples and ACMS samples; initial (trim) states. The
    customer bleed (``bleed_kgs``, (n_engines, n); None = none) and the off-take (default: the
    configuration's, as ``run.simulate_flight``) are part of the exogenous rows."""
    cfg0 = cfg.with_factors(())
    ps = build_proxy_system(
        cfg0,
        rec,
        identity=KeyPath.of(scenario="ident", tail="T0", sortie=1),
        root=0,
        fadec_params=fadec_params,
        bleed_kgs=bleed_kgs,
        pto_w=cfg.bleed.pto_w if pto_w is None else float(pto_w),
    )
    grp = ProxyLoopGroup(ps.modules)
    n = round(rec.n * 240 / rec.rate_hz)
    want = {c.dst: c.src for c in ps.connections if c.dst.split(".")[0] in ("fadec", "eng", "sens", "acq")}
    ext_keys = [k for k in want if not want[k].startswith(("fadec.", "eng.", "sens.", "acq."))]
    syst = ps.system
    world = syst.start()
    _w, trace = syst.run(world, n, mode="block", record=sorted({want[k] for k in ext_keys}))
    ext = {k: trace.ports[want[k]] for k in ext_keys}
    pla, p0, at_eng, at_cmd, _ab, uex, uiex, bias, _phase = grp._ext(ext, n)
    ks = np.arange(n, dtype=np.int64)
    t = truth_step_times_ns(ks)
    t_end = truth_step_times_ns(ks + 1)
    fad, eng, sens = ps.modules["fadec"], ps.modules["eng"], ps.modules["sens"]
    sf, se, ss = world.states["fadec"], world.states["eng"], world.states["sens"]
    nfr = np.ascontiguousarray(fad.frame_schedule(sf, t).count, dtype=np.int64)
    lane_smp = samples_for_steps(grp.dom.clock, int(world.states["acq"]["n_next"][0]), t, t_end)
    idx = np.asarray(grp.dom.channels, dtype=np.int64)
    lanes0 = grp._lanes0({k: v for k, v in world.held.items()})
    m, fc, scfg = eng.model, fad.config, sens.config
    # recorded words (family, engine) -> M12 columns
    out_cols, conv = [], []
    tau_cols: dict[str, list[int]] = {f: [] for f in FAMILIES}
    for fam in FAMILIES:
        did = next(k for k, v in RECORDED.items() if v == fam)
        for e in range(cfg.n_engines):
            c = scfg.channels.index(f"{did}:E{e + 1}")
            out_cols.append(c)
            conv.append(cfg.dictionary.eu_conversion(did))
            el0, nel = int(scfg.ch_i[c, 0]), int(scfg.ch_i[c, 1])
            tau_cols[fam].extend(range(el0, el0 + nel))
    acms = cfg.recording.domains[0].clock
    smp = samples_for_steps(acms, 0, t, t_end)
    s_w = (smp.times - t[smp.step]).astype(np.float64) / (t_end[smp.step] - t[smp.step]).astype(np.float64)
    args = dict(
        f8=sf["f"], i8=sf["i"], p8=fc.p, tb8=fc.tables, cfg8=fc.cfg, dt8=fc.dt, pla=pla, p0=p0, at_eng=at_eng,
        at_cmd=at_cmd, nfr=nfr, lanes0=lanes0, f7=se["f"], i7=se["i"], b7=se["buf"], p7=m.p, tb7=m.tables,
        uex=uex, uiex=uiex, zab=np.zeros((cfg.n_engines, 2)), dt7=m.dt, nsub7=m.n_sub, ndel7=m.n_delay,
        ef=ss["ef"], ei=ss["ei"], cf=ss["cf"], ci=ss["ci"], el_i=scfg.el_i, el_p=scfg.el_p, ch_i=scfg.ch_i,
        ch_p=scfg.ch_p, tx=scfg.tx, ty=scfg.ty, toff=scfg.toff, cols=scfg.cols, kvec=scfg.k, bias=bias,
        t_end=t_end, fu=np.zeros((n, scfg.n_ch)), dt12=1.0 / 240.0, nsub12=scfg.n_sub,
        u_sig=grp.u_sig, u_eng=grp.u_eng, lane_sens=np.ascontiguousarray(grp.lane_sens[idx]),
        lane_eng=np.ascontiguousarray(grp.lane_eng[idx]), lane_slot=np.ascontiguousarray(grp.lane_slot[idx]),
        s_cnt=np.ascontiguousarray(lane_smp.count, dtype=np.int64),
    )  # fmt: skip
    return IdentProblem(
        cfg=cfg,
        rec=rec,
        n_steps=n,
        args=args,
        out_cols=np.asarray(out_cols, dtype=np.int64),
        conv=conv,
        s_step=np.asarray(smp.step, dtype=np.int64),
        s_w=s_w,
        tau_cols={f: sorted(set(v)) for f, v in tau_cols.items()},
        n_engines=cfg.n_engines,
    )


def nominal(prob: IdentProblem, names: Sequence[str]) -> np.ndarray:
    """The configuration's values of the named parameters."""
    a = prob.args
    out = []
    for nm in names:
        owner, key = PARAMS[nm]
        if owner == "eng":
            out.append(float(a["p7"][SF_PI[key]]))
        elif owner == "fadec":
            out.append(float(a["p8"][P_LAYOUT.index[key]]))
        else:
            out.append(float(a["el_p"][prob.tau_cols[key][0], PE_TAU]))
    return np.asarray(out)


_FLOAT_STATE = (
    "f8",
    "p8",
    "pla",
    "p0",
    "at_cmd",
    "lanes0",
    "f7",
    "b7",
    "p7",
    "uex",
    "ef",
    "cf",
    "el_p",
    "bias",
)


def simulate(prob: IdentProblem, names: Sequence[str] = (), theta: Sequence[float] = ()) -> np.ndarray:
    """Recorded-word outputs (n_samples, n_engines, 4 families) [EU] for parameters ``names = theta``."""
    theta = np.asarray(theta, dtype=np.float64)
    dt = np.float64
    a = dict(prob.args)
    for k in _FLOAT_STATE:
        a[k] = np.array(a[k], dtype=dt, copy=True)
    for nm, v in zip(names, theta, strict=True):
        owner, key = PARAMS[nm]
        if owner == "eng":
            a["p7"][SF_PI[key]] = v
        elif owner == "fadec":
            a["p8"][P_LAYOUT.index[key]] = v
        else:
            for r in prob.tau_cols[key]:
                a["el_p"][r, PE_TAU] = v
    out, _u = _ident_core(**a, out_cols=prob.out_cols)
    return _to_words(prob, out)


def _to_words(prob: IdentProblem, out: np.ndarray) -> np.ndarray:
    """Per-step M12 outputs (L, n_out) -> the words at the ACMS instants (linear interpolation between the
    frame ends around each sample, M13's rule), EU, (n_samples, E, 4)."""
    j = prob.s_step
    hi = out[np.minimum(j, out.shape[0] - 1)]
    lo = out[np.maximum(j - 1, 0)]
    w = prob.s_w[:, None]
    v = lo + w * (hi - lo)
    eu = np.empty_like(v)
    for c, cv in enumerate(prob.conv):
        eu[:, c] = (v[:, c] - cv.offset) / cv.scale
    E = prob.n_engines
    return eu.reshape(-1, len(FAMILIES), E).transpose(0, 2, 1)


def record_array(rec, n: int | None = None) -> np.ndarray:
    """(n, E, 4) EU array of a FlightRecord in this module's family order (N1, N2, EGT, FF)."""
    a = np.stack([np.asarray(rec.outputs[f], float) for f in FAMILIES], axis=-1).transpose(1, 0, 2)
    return a if n is None else a[:n]


@dataclass(frozen=True)
class Fit:
    names: tuple[str, ...]
    theta: np.ndarray
    se: np.ndarray  # Gauss-Newton standard errors (residual-scaled), same units as theta
    cost: float
    cost0: float
    iterations: int
    log: tuple[tuple[float, ...], ...]


def _residuals(prob, names, theta, y, w, scales):
    sim = simulate(prob, names, theta)
    n = min(sim.shape[0], y.shape[0])
    r = (sim[:n] - y[:n]) / scales[None, None, :] * np.sqrt(w[:n])[:, None, None]
    return r.reshape(-1)


def fit_oe(
    prob: IdentProblem,
    y_meas: np.ndarray,
    names: Sequence[str],
    theta0: Sequence[float],
    *,
    weights: np.ndarray | None = None,
    scales: Sequence[float] = (0.05, 0.05, 1.0, 8.0),
    max_iter: int = 12,
    tol: float = 1e-4,
    noise_ar: int = 0,
    n_outer: int = 3,
) -> Fit:
    """Transient-weighted output-error fit of the closed loop from the external commands (indirect method):
    Levenberg-Marquardt in log-parameters with difference Jacobians. ``scales``: residual scale per family
    (about the word texture: N1/N2 0.05 %, EGT 1 degC, FF 8 lb/h).

    ``noise_ar > 0`` turns the output error into a **prediction error with an innovations model**: the
    residual of each (engine, word) is modelled as AR(``noise_ar``) coloured process noise, estimated by least
    squares on the current residual and held fixed while the parameters are refitted on the whitened residual
    (iterative prefiltering, ``n_outer`` rounds). Coloured disturbance power then no longer dominates the
    transient information, which reduces the variance of the estimate."""
    names = tuple(names)
    sc = np.asarray(scales, float)
    w = np.ones(y_meas.shape[0]) if weights is None else np.asarray(weights, float)
    if noise_ar <= 0:

        def resid(th):
            return _residuals(prob, names, th, y_meas, w, sc)

        return _lm(resid, np.asarray(theta0, float), max_iter, tol, names)
    th = np.asarray(theta0, float)
    shape = (-1, prob.n_engines, len(FAMILIES))
    fit = None
    for _ in range(n_outer):
        raw = _residuals(prob, names, th, y_meas, np.ones_like(w), sc).reshape(shape)
        ar = _ar_fit(raw, noise_ar)

        def resid(t, ar=ar):
            r = _residuals(prob, names, t, y_meas, np.ones_like(w), sc).reshape(shape)
            return (_ar_whiten(r, ar) * np.sqrt(w[: r.shape[0]])[:, None, None]).reshape(-1)

        fit = _lm(resid, th, max_iter, tol, names)
        th = fit.theta
    return fit


def _ar_fit(r: np.ndarray, p: int) -> np.ndarray:
    """AR(p) coefficients (E, F, p) of each residual series by least squares."""
    n, E, F = r.shape
    out = np.zeros((E, F, p))
    for e in range(E):
        for f in range(F):
            x = r[:, e, f]
            X = np.column_stack([x[p - k - 1 : n - k - 1] for k in range(p)])
            out[e, f] = np.linalg.lstsq(X, x[p:], rcond=None)[0]
    return out


def _ar_whiten(r: np.ndarray, ar: np.ndarray) -> np.ndarray:
    """Innovations e_t = r_t - sum_k a_k r_(t-k) (the first p samples dropped)."""
    p = ar.shape[2]
    e = r[p:].copy()
    for k in range(p):
        e -= ar[None, :, :, k] * r[p - k - 1 : r.shape[0] - k - 1]
    return np.concatenate([np.zeros((p, *r.shape[1:])), e], axis=0)


#: minimum Welch segments for a cross-engine coherence estimate: with K segments the coherence of independent
#: signals is biased up to about 1/K (A2 run 1 used 2 segments and read 0.5 for independent residuals)
MIN_SEGMENTS = 8


def residual_spectra(
    resid: np.ndarray, rate_hz: float = 4.0, nperseg: int | None = None
) -> dict[str, np.ndarray]:
    """Per-engine residual PSD (Welch, 50 % overlap) per family and the mean cross-engine coherence of the
    residuals over the fast band (0.2-1 Hz), from residuals (n, E, 4) [EU]. ``nperseg`` defaults to the
    largest power of two giving at least ``MIN_SEGMENTS`` segments (at most 256); fewer segments is refused,
    because the coherence of independent signals is then biased towards 1/K."""
    from scipy.signal import coherence, welch

    n, E, F = resid.shape
    if nperseg is None:
        nperseg = 256
        while nperseg > 16 and (n - nperseg) // (nperseg // 2) + 1 < MIN_SEGMENTS:
            nperseg //= 2
    k = (n - nperseg) // (nperseg // 2) + 1
    if k < MIN_SEGMENTS:
        raise ValueError(f"{n} samples give {k} Welch segments of {nperseg} (< {MIN_SEGMENTS}): too short")
    f, _ = welch(resid[:, 0, 0], fs=rate_hz, nperseg=nperseg)
    psd = np.zeros((E, F, f.size))
    for e in range(E):
        for c in range(F):
            psd[e, c] = welch(resid[:, e, c], fs=rate_hz, nperseg=nperseg, detrend="linear")[1]
    band = (f >= 0.2) & (f <= 1.0)
    coh = np.zeros(F)
    for c in range(F):
        vals = []
        for i in range(E):
            for j in range(i + 1, E):
                _f, C = coherence(
                    resid[:, i, c], resid[:, j, c], fs=rate_hz, nperseg=nperseg, detrend="linear"
                )
                vals.append(float(np.mean(C[band])))
        coh[c] = float(np.mean(vals))
    return {"freq": f, "psd": psd, "cross_engine_coherence": coh, "nperseg": nperseg, "segments": k}


def transient_weights_of(rec: ReplayInputs, **kw) -> np.ndarray:
    """AD-34 weights (n,) on the ACMS grid from the driving command: the A/T N1 command where engaged, else
    the lever (both scaled to percent-like units), via ``engine.ident.transient_weights``."""
    from phalanx.engine.ident import transient_weights

    drive = np.where(rec.at_engage == 1, rec.at_n1_cmd[0] * 100.0, np.degrees(rec.pla_rad[0]))
    opts = {"threshold": 0.5, "window_s": 6.0, "rate_window_s": 1.0, "w_accel": 5.0, "w_decel": 5.0, **kw}
    return transient_weights(drive, 1.0 / rec.rate_hz, **opts)


__all__ = [
    "FD_STEP",
    "PARAMS",
    "Fit",
    "IdentProblem",
    "configure",
    "fit_direct",
    "fit_oe",
    "jacobian",
    "nominal",
    "prepare",
    "record_array",
    "residual_spectra",
    "simulate",
    "transient_weights_of",
]


def ucmd_nominal(prob: IdentProblem) -> np.ndarray:
    """M08's actuator commands (L, E, 5) of the nominal deterministic closed loop."""
    return _ident_core(**prob.args, out_cols=prob.out_cols)[1]


def _plant_words(prob: IdentProblem, names, theta, ucmd) -> np.ndarray:
    theta = np.asarray(theta, dtype=np.float64)
    dt = np.float64
    a = prob.args
    p7 = np.array(a["p7"], dtype=dt, copy=True)
    el_p = np.array(a["el_p"], dtype=dt, copy=True)
    for nm, v in zip(names, theta, strict=True):
        owner, key = PARAMS[nm]
        if owner == "eng":
            p7[SF_PI[key]] = v
        elif owner == "sens":
            for r in prob.tau_cols[key]:
                el_p[r, PE_TAU] = v
        else:
            raise ValueError(f"{nm}: the direct (open-loop plant) method has no controller parameters")
    out = _plant_core(
        np.array(a["f7"], dtype=dt), a["i7"], np.array(a["b7"], dtype=dt), p7, a["tb7"],
        np.array(a["uex"], dtype=dt), a["uiex"], a["zab"], a["dt7"], a["nsub7"], a["ndel7"],
        np.asarray(ucmd, dtype=dt), np.array(a["ef"], dtype=dt), a["ei"], np.array(a["cf"], dtype=dt),
        a["ci"],
        a["el_i"], el_p, a["ch_i"], a["ch_p"], a["tx"], a["ty"], a["toff"], a["cols"], a["kvec"],
        np.array(a["bias"], dtype=dt), a["t_end"], a["fu"], a["dt12"], a["nsub12"], a["u_sig"], a["u_eng"],
        prob.out_cols,
    )  # fmt: skip
    return _to_words(prob, out)


def fit_direct(
    prob: IdentProblem,
    y_meas: np.ndarray,
    names: Sequence[str],
    theta0: Sequence[float],
    *,
    weights: np.ndarray | None = None,
    scales: Sequence[float] = (0.05, 0.05, 1.0, 8.0),
    max_iter: int = 12,
    tol: float = 1e-4,
) -> Fit:
    """Direct method (for comparison with the indirect closed-loop OE): the plant driven by the *measured*
    fuel flow (the FF word, held between samples, converted to kg/s; the other actuator commands from the
    nominal closed loop), fitted to N1, N2 and EGT. Under closed-loop operation with process disturbances
    the measured fuel is correlated with the disturbance, which biases this estimate (round-2 §8 H-c 2)."""
    names = tuple(names)
    sc = np.asarray(scales, float)
    w = np.ones(y_meas.shape[0]) if weights is None else np.asarray(weights, float)
    ucmd = np.array(ucmd_nominal(prob), dtype=np.float64)
    ff = y_meas[:, :, 3] * 0.45359237 / 3600.0  # lb/h -> kg/s
    step_sample = np.searchsorted(prob.s_step, np.arange(prob.n_steps), side="right") - 1
    ucmd[:, :, 0] = ff[np.clip(step_sample, 0, ff.shape[0] - 1)]
    fam = np.array([0, 1, 2])  # N1, N2, EGT (the fuel is the input)

    def resid(th):
        sim = _plant_words(prob, names, th, ucmd)
        n = min(sim.shape[0], y_meas.shape[0])
        r = (sim[:n][:, :, fam] - y_meas[:n][:, :, fam]) / sc[fam][None, None, :]
        return (r * np.sqrt(w[:n])[:, None, None]).reshape(-1)

    return _lm(resid, np.asarray(theta0, float), max_iter, tol, names)


def _lm(resid, th, max_iter, tol, names) -> Fit:
    """Levenberg-Marquardt in log-parameters with central-difference Jacobians of ``resid``."""
    r = resid(th)
    cost0 = cost = float(r @ r)
    lam, log, it = 1e-2, [(*th, cost)], 0
    for it in range(1, max_iter + 1):  # noqa: B007
        J = _jac(resid, th)
        g, H = J.T @ r, J.T @ J
        while True:
            step = np.linalg.solve(H + lam * np.diag(np.diag(H)), -g)
            cand = th * np.exp(np.clip(step, -0.7, 0.7))
            rc = resid(cand)
            cc = float(rc @ rc)
            if cc < cost:
                lam = max(lam / 3.0, 1e-6)
                break
            lam *= 10.0
            if lam > 1e8:
                cand, rc, cc = th, r, cost
                break
        rel = (cost - cc) / max(cost, 1e-300)
        th, r, cost = cand, rc, cc
        log.append((*th, cost))
        if rel < tol and np.max(np.abs(step)) < 1e-3:
            break
    J = _jac(resid, th)
    dof = max(r.size - th.size, 1)
    cov_log = np.linalg.pinv(J.T @ J) * cost / dof
    se = th * np.sqrt(np.clip(np.diag(cov_log), 0, None))
    return Fit(tuple(names), th, se, cost, cost0, it, tuple(log))


#: relative (log-parameter) step of the central-difference Jacobian
FD_STEP = 1e-4


def _jac(resid, th, h: float = FD_STEP) -> np.ndarray:
    """d resid / d log(theta) by central differences (see the module docstring for why not complex step)."""
    cols = []
    for j in range(th.size):
        tp, tm = th.copy(), th.copy()
        tp[j] = th[j] * np.exp(h)
        tm[j] = th[j] * np.exp(-h)
        cols.append((resid(tp) - resid(tm)) / (2.0 * h))
    return np.stack(cols, axis=1)


def jacobian(prob: IdentProblem, names: Sequence[str], theta: Sequence[float], y_meas: np.ndarray,
             weights: np.ndarray | None = None, scales: Sequence[float] = (0.05, 0.05, 1.0, 8.0),
             h: float = FD_STEP) -> np.ndarray:  # fmt: skip
    """The OE residual Jacobian d r / d log(theta) (for the self-test's step-size check)."""
    sc = np.asarray(scales, float)
    w = np.ones(y_meas.shape[0]) if weights is None else np.asarray(weights, float)
    return _jac(lambda th: _residuals(prob, tuple(names), th, y_meas, w, sc), np.asarray(theta, float), h)


def configure(cfg: ProxyConfig, theta: dict[str, float], fadec_params=None) -> tuple[ProxyConfig, object]:
    """A proxy configuration and M08 parameter set with the named identification parameters set: the
    self-test's ground truth for synthetic data generated with the full chain (disturbances and texture)."""
    from dataclasses import replace as _replace

    eng = {k: float(v) for k, v in theta.items() if PARAMS[k][0] == "eng"}
    fad = {k: float(v) for k, v in theta.items() if PARAMS[k][0] == "fadec"}
    sens = {PARAMS[k][1]: float(v) for k, v in theta.items() if PARAMS[k][0] == "sens"}
    if eng:
        cfg = cfg.with_engine(**eng)
    if sens:
        scfg = cfg.sensors
        el_p = np.array(scfg.el_p, copy=True)
        for fam, tau in sens.items():
            did = next(k for k, v in RECORDED.items() if v == fam)
            for e in range(cfg.n_engines):
                c = scfg.channels.index(f"{did}:E{e + 1}")
                el0, nel = int(scfg.ch_i[c, 0]), int(scfg.ch_i[c, 1])
                el_p[el0 : el0 + nel, PE_TAU] = tau
        el_p.flags.writeable = False
        cfg = _replace(cfg, sensors=_replace(scfg, el_p=el_p))
    fp = fadec_params if fadec_params is not None else cfg.fadec_params
    if fad:
        fp = fp.replace(**fad)
    return cfg, fp
