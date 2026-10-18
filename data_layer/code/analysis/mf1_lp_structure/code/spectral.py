"""MF1-D spectral estimators (pre-registered in ../PREREGISTRATION.md sections 4-5).

All quantities are computed on the **B1 fast-band signals** x_fast = x - lowpass(x)
(Butterworth-4, zero-phase, f_c 0.2 Hz, applied to the whole record:
`phalanx.validation.battery.filters.lowpass`), restricted to segments that lie wholly inside a class mask
(airborne rule: all four N1 > 25 %, optionally intersected with an A/T or flight-phase class).

Welch estimator (identical to `scipy.signal.csd(x, y, fs=4, window="hann", nperseg=512, noverlap=256,
detrend="linear")` on one contiguous run; verified in selftest.py):
- segment length 512 samples (128 s; bin width 4/512 = 0.0078125 Hz), periodic Hann window, hop 256 (50 %);
- segments are placed inside every contiguous run of the mask (start a, a+256, ... while start+512 <= end),
  and the periodograms of all segments of a flight (and class) are averaged; runs shorter than 512 samples add
  none;
- one-sided density scaling; convention G_ij = E[conj(X_i) X_j] (scipy), so a positive phase slope means the
  *first* channel lags; the equivalent delay tau = -dphi/domega is positive when the *second* channel lags
  (the B2 sign convention).

Sub-band aggregation: the 256 non-DC bins are summed in contiguous blocks of 8 (sub-band width 0.0625 Hz,
32 sub-bands; sub-band b covers bins 8b+1..8b+8). Quantities below use sub-band powers P_b (variance units,
density x bin width). Effective dof per sub-band: nu = 2 K / 1.0556 x 4.40 ~ 8.34 K (K segments; Welch 1967
Hann 50 % overlap factor; 4.40 equivalent independent bins in an 8-bin Hann average).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import detrend, get_window, sosfreqz

from phalanx.validation.battery.config import BUTTER_ORDER, FC_PRIMARY
from phalanx.validation.battery.filters import _sos  # same SOS as the B1 low-pass

FS = 4.0
NPERSEG = 512
HOP = 256
NBIN = 8  # bins per sub-band
NF = NPERSEG // 2 + 1
DF = FS / NPERSEG
WIN = get_window("hann", NPERSEG)  # periodic Hann (scipy's Welch default)
SCALE = 1.0 / (FS * float(np.sum(WIN**2)))
FREQS = np.arange(NF) * DF
NSUB = (NF - 1) // NBIN  # 32
SUB_LO = np.array([FREQS[NBIN * b + 1] - DF / 2 for b in range(NSUB)])
SUB_HI = np.array([FREQS[NBIN * b + NBIN] + DF / 2 for b in range(NSUB)])
SUB_FC = np.array([FREQS[NBIN * b + 1 : NBIN * b + NBIN + 1].mean() for b in range(NSUB)])
#: equivalent independent sub-band dof per segment (see module docstring)
NU_PER_SEGMENT = 2.0 / 1.0556 * 4.40
#: phase-slope (equivalent delay) fit band: sub-band centres within [0.2, 1.0] Hz
FIT_BAND = (0.2, 1.0)
FIT_SUBS = np.flatnonzero((SUB_FC >= FIT_BAND[0]) & (SUB_FC <= FIT_BAND[1]))
#: reporting bands (Hz) for band-limited coherence and phase
REPORT_BANDS: tuple[tuple[float, float], ...] = ((0.1875, 0.5), (0.5, 1.0), (1.0, 2.0))
#: empirical high-frequency floor band (Hz)
HF_BAND = (1.5, 1.95)


def fast_power_transfer() -> np.ndarray:
    """g(f) = (1 - |H_lp(f)|^2)^2 at the Welch bins: power transfer of the B1 fast-band operator
    x - lowpass(x) (sosfiltfilt magnitude |H_sos|^2; the fast operator is real, zero-phase 1 - |H_sos|^2)."""
    _, h = sosfreqz(_sos(BUTTER_ORDER, FC_PRIMARY, FS), worN=FREQS, fs=FS)
    return (1.0 - np.abs(h) ** 2) ** 2


G_FAST = fast_power_transfer()


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    m = np.r_[False, np.asarray(mask, bool), False].astype(np.int8)
    d = np.diff(m)
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist(), strict=True))


def segment_starts(mask: np.ndarray) -> list[int]:
    out: list[int] = []
    for a, b in runs(mask):
        s = a
        while s + NPERSEG <= b:
            out.append(s)
            s += HOP
    return out


def csd_matrix(X: np.ndarray, starts: list[int]) -> tuple[np.ndarray, int]:
    """Welch cross-spectral density matrix G (NF, p, p) [unit^2/Hz], one-sided, averaged over segments.

    G[f, i, j] = mean_s conj(F_i) F_j * scale (x2 for 0 < f < Nyquist). Returns (G, K)."""
    p = X.shape[0]
    K = len(starts)
    if K == 0:
        return np.zeros((NF, p, p), complex), 0
    idx = np.asarray(starts)[:, None] + np.arange(NPERSEG)[None, :]
    seg = X[:, idx]  # (p, K, N)
    seg = detrend(seg, axis=2, type="linear")
    F = np.fft.rfft(seg * WIN[None, None, :], axis=2)  # (p, K, NF)
    G = np.einsum("ikf,jkf->fij", F.conj(), F) * (SCALE / K)
    G[1:-1] *= 2.0
    return G, K


def subband(G: np.ndarray) -> np.ndarray:
    """Sub-band powers P (NSUB, p, p) [unit^2] = sum of density x DF over the 8 bins of each sub-band."""
    return np.stack([G[NBIN * b + 1 : NBIN * b + NBIN + 1].sum(0) * DF for b in range(NSUB)])


def white_subband_power(var: float | np.ndarray) -> np.ndarray:
    """Sub-band power of white noise of variance `var` (raw signal), after the B1 fast-band operator.

    One-sided white density 2 var / FS, times g(f), summed over the sub-band bins x DF. Shape (NSUB,) or
    (NSUB, len(var))."""
    dens = np.outer(G_FAST, np.atleast_1d(var)) * (2.0 / FS)  # (NF, c)
    out = np.stack([dens[NBIN * b + 1 : NBIN * b + NBIN + 1].sum(0) * DF for b in range(NSUB)])
    return out[:, 0] if np.ndim(var) == 0 else out


def hf_white_level(G: np.ndarray) -> np.ndarray:
    """Empirical white level (raw-signal variance equivalent) per channel from the median of
    G_ii(f) / g(f) over the HF band [1.5, 1.95] Hz: returns var_eq = level * FS / 2 (so that
    white_subband_power(var_eq) reproduces that level)."""
    m = (FREQS >= HF_BAND[0]) & (FREQS <= HF_BAND[1])
    dens = np.real(np.einsum("fii->fi", G[m])) / G_FAST[m][:, None]
    return np.median(dens, axis=0) * FS / 2.0


# ---------------------------------------------------------------- pair decomposition
@dataclass(frozen=True)
class PairResult:
    r_spec: float  # spectral reconstruction of the zero-lag fast-band correlation
    r_shape: float  # coherence 1, phase 0, observed amplitude spectra
    r_lag: float  # coherence 1 at the observed phase and gain: the brief's "lag-only ceiling"
    r_cohonly: float  # observed coherence, phase 0
    L_total: float
    L_dyn_A: float  # 1 - r_lag (ordering A, primary: "phase loss" incl. gain shape)
    L_phase_A: float  # r_shape - r_lag
    L_shape: float  # 1 - r_shape
    L_coh_A: float  # r_lag - r_spec
    L_coh_B: float  # r_shape - r_cohonly (ordering B)
    L_coh_S: float  # Shapley mean of A and B
    L_tex_A: float  # texture-attributable coherence loss, ordering A
    L_tex_B: float
    L_beyond_A: float  # L_coh_A - L_tex_A
    L_beyond_B: float
    CF_i: float  # coherent fraction of channel i's fast-band variance
    CF_j: float
    CFtex_i: float  # texture-implied ceiling of CF_i
    CFtex_j: float
    U_beyond_i: float  # fraction of i's power incoherent with j beyond texture (errors-in-variables)
    U_beyond_j: float
    Q_i: float  # texture variance fraction of channel i (fast band)
    Q_j: float
    r_tex_ceiling: float  # sqrt((1 - Q_i)(1 - Q_j))
    r_truth: float  # texture-de-attenuated r = r_spec / r_tex_ceiling
    tau_eq: float  # equivalent delay [s] from the phase slope over FIT_SUBS (+ = j lags i)
    tau_eq_se: float
    r_delay: float  # coherence 1 with a pure delay tau_eq at the observed amplitude spectra
    coh_bands: tuple[float, ...]  # power-weighted coherence in REPORT_BANDS
    phase_bands_deg: tuple[float, ...]  # phase of the summed cross-power in REPORT_BANDS [deg]

    @property
    def shares_A(self) -> dict[str, float]:
        L = self.L_total
        return {
            "dyn": self.L_dyn_A / L,
            "phase": self.L_phase_A / L,
            "shape": self.L_shape / L,
            "coh": self.L_coh_A / L,
            "tex": self.L_tex_A / L,
            "beyond": self.L_beyond_A / L,
        }

    @property
    def shares_S(self) -> dict[str, float]:
        L = self.L_total
        tex_s = 0.5 * (self.L_tex_A + self.L_tex_B)
        return {
            "dyn": (L - self.L_coh_S) / L,
            "coh": self.L_coh_S / L,
            "tex": tex_s / L,
            "beyond": (self.L_coh_S - tex_s) / L,
        }


def _safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1.0), 0.0)


TAU_GRID = np.round(np.arange(-3.0, 3.0001, 0.01), 2)


def unwrapped_phase(Pij: np.ndarray) -> np.ndarray:
    """Phase over FIT_SUBS, unwrapped robustly: a coarse delay tau0 maximises the cross-power-weighted
    alignment sum_b |P_b| cos(phi_b + omega_b tau0) over [-3, 3] s; the phase is then
    -omega tau0 + wrap(phi + omega tau0), which never propagates a 2 pi slip from a low-coherence sub-band."""
    sb = FIT_SUBS
    om = 2 * np.pi * SUB_FC[sb]
    phi = np.angle(Pij[sb])
    mag = np.abs(Pij[sb])
    score = np.cos(phi[None, :] + np.outer(TAU_GRID, om)) @ mag
    tau0 = float(TAU_GRID[int(np.argmax(score))])
    return -om * tau0 + np.angle(np.exp(1j * (phi + om * tau0)))


def equivalent_delay(Pij: np.ndarray, C: np.ndarray, K: int) -> tuple[float, float, np.ndarray]:
    """Weighted LS of the unwrapped phase on 2 pi f over FIT_SUBS, with intercept.

    Weights nu C / (1 - C) (inverse phase variance), C clipped to [0.01, 0.99].
    Returns (tau, se, phase_unwrapped).
    tau = -slope / (2 pi): positive when the second channel lags."""
    sb = FIT_SUBS
    ph = unwrapped_phase(Pij)
    c = np.clip(C[sb], 0.01, 0.99)
    w = max(K, 1) * NU_PER_SEGMENT * c / (1 - c)
    x = 2 * np.pi * SUB_FC[sb]
    A = np.column_stack([np.ones_like(x), x])
    W = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(A * W[:, None], ph * W, rcond=None)
    res = ph - A @ beta
    dof = max(len(sb) - 2, 1)
    s2 = float(np.sum(w * res**2) / dof)
    cov = s2 * np.linalg.inv((A * w[:, None]).T @ A)
    return float(-beta[1]), float(np.sqrt(cov[1, 1])), ph


def pair_decomposition(P: np.ndarray, T: np.ndarray, i: int, j: int, K: int) -> PairResult:
    """Decompose 1 - r for channels (i, j) from sub-band powers P (NSUB, p, p), texture powers T (NSUB, p)."""
    Pii = np.real(P[:, i, i])
    Pjj = np.real(P[:, j, j])
    Pij = P[:, i, j]
    Si, Sj = Pii.sum(), Pjj.sum()
    norm = np.sqrt(Si * Sj)
    C = _safe_div(np.abs(Pij) ** 2, Pii * Pjj)
    C = np.clip(C, 0.0, 1.0)
    phi = np.angle(Pij)
    w = np.sqrt(Pii * Pjj) / norm
    r_spec = float(np.real(Pij).sum() / norm)
    r_shape = float(w.sum())
    r_lag = float(np.sum(w * np.cos(phi)))
    r_coh = float(np.sum(w * np.sqrt(C)))
    Ti = np.minimum(T[:, i], Pii)
    Tj = np.minimum(T[:, j], Pjj)
    ctex = np.clip(1 - _safe_div(Ti, Pii), 0, 1) * np.clip(1 - _safe_div(Tj, Pjj), 0, 1)
    L_tex_A = float(np.sum(w * (1 - np.sqrt(ctex)) * np.cos(phi)))
    L_tex_B = float(np.sum(w * (1 - np.sqrt(ctex))))
    L_total = 1 - r_spec
    L_coh_A = r_lag - r_spec
    L_coh_B = r_shape - r_coh
    Qi = float(Ti.sum() / Si)
    Qj = float(Tj.sum() / Sj)
    ceil = float(np.sqrt(max(1 - Qi, 0) * max(1 - Qj, 0)))
    # beyond-texture incoherent power (errors in variables): true power minus the part explainable by the
    # other channel's true signal, |Pij|^2 / (Pjj - Tj)
    Tj_c = np.minimum(Tj, 0.95 * Pjj)
    Ti_c = np.minimum(Ti, 0.95 * Pii)
    Ub_i = float(np.sum(Pii - Ti_c - _safe_div(np.abs(Pij) ** 2, Pjj - Tj_c)) / Si)
    Ub_j = float(np.sum(Pjj - Tj_c - _safe_div(np.abs(Pij) ** 2, Pii - Ti_c)) / Sj)
    tau, se, _ = equivalent_delay(Pij, C, K)
    r_delay = float(np.sum(w * np.cos(2 * np.pi * SUB_FC * tau)))
    cb, pb = [], []
    for lo, hi in REPORT_BANDS:
        m = (SUB_FC >= lo) & (SUB_FC < hi)
        cb.append(float(np.sum(C[m] * w[m]) / max(np.sum(w[m]), 1e-300)))
        pb.append(float(np.degrees(np.angle(Pij[m].sum()))))
    return PairResult(
        r_spec=r_spec,
        r_shape=r_shape,
        r_lag=r_lag,
        r_cohonly=r_coh,
        L_total=L_total,
        L_dyn_A=1 - r_lag,
        L_phase_A=r_shape - r_lag,
        L_shape=1 - r_shape,
        L_coh_A=L_coh_A,
        L_coh_B=L_coh_B,
        L_coh_S=0.5 * (L_coh_A + L_coh_B),
        L_tex_A=L_tex_A,
        L_tex_B=L_tex_B,
        L_beyond_A=L_coh_A - L_tex_A,
        L_beyond_B=L_coh_B - L_tex_B,
        CF_i=float(np.sum(C * Pii) / Si),
        CF_j=float(np.sum(C * Pjj) / Sj),
        CFtex_i=float(np.sum(ctex * Pii) / Si),
        CFtex_j=float(np.sum(ctex * Pjj) / Sj),
        U_beyond_i=Ub_i,
        U_beyond_j=Ub_j,
        Q_i=Qi,
        Q_j=Qj,
        r_tex_ceiling=ceil,
        r_truth=r_spec / ceil if ceil > 0 else float("nan"),
        tau_eq=tau,
        tau_eq_se=se,
        r_delay=r_delay,
        coh_bands=tuple(cb),
        phase_bands_deg=tuple(pb),
    )


# ---------------------------------------------------------------- conditioning
def path_decomposition(P: np.ndarray, i: int, j: int, k: int) -> tuple[float, float]:
    """r(i, j) = r_via_k + r_partial_k: the part of the zero-lag fast-band correlation carried by components
    coherent with channel k, and the k-conditioned remainder. Returns (r_via_k, r_partial_k)."""
    Pii = np.real(P[:, i, i]).sum()
    Pjj = np.real(P[:, j, j]).sum()
    norm = np.sqrt(Pii * Pjj)
    Pkk = np.real(P[:, k, k])
    via = _safe_div(P[:, i, k] * P[:, k, j], Pkk)
    r_via = float(np.real(via).sum() / norm)
    r_part = float(np.real(P[:, i, j] - via).sum() / norm)
    return r_via, r_part


def partial_coherence(P: np.ndarray, i: int, j: int, k: int) -> tuple[float, float]:
    """Band-averaged partial coherence of (i, j) given k, weighted by i's and j's k-conditioned power.

    Returns (PCF_i, PCF_j): fraction of the k-conditioned power of i (resp. j) coherent with the
    k-conditioned j (resp. i)."""
    Pkk = np.real(P[:, k, k])
    Pij = P[:, i, j] - _safe_div(P[:, i, k] * P[:, k, j], Pkk)
    Pii = np.real(P[:, i, i]) - _safe_div(np.abs(P[:, i, k]) ** 2, Pkk)
    Pjj = np.real(P[:, j, j]) - _safe_div(np.abs(P[:, j, k]) ** 2, Pkk)
    Pii = np.maximum(Pii, 1e-300)
    Pjj = np.maximum(Pjj, 1e-300)
    g = np.clip(np.abs(Pij) ** 2 / (Pii * Pjj), 0, 1)
    return float(np.sum(g * Pii) / Pii.sum()), float(np.sum(g * Pjj) / Pjj.sum())


@dataclass(frozen=True)
class MultipleResult:
    MCF: float  # fraction of i's fast-band power linearly explained by the set S (multiple coherence)
    U_obs: float  # 1 - MCF
    U_tex: float  # part of U_obs attributable to texture (own + inputs), errors in variables
    U_beyond: float  # true i power not explainable by the true inputs, as a fraction of observed i power
    MC_ceiling: float  # texture-implied ceiling of MCF if i were exactly determined by S


def multiple_coherence(P: np.ndarray, T: np.ndarray, i: int, S: list[int]) -> MultipleResult:
    """Multiple coherence of channel i on the set S per sub-band, band-averaged by i's power, with the
    texture-implied ceiling (true spectral matrix = P - diag(T), cross-spectra unchanged)."""
    Pii = np.real(P[:, i, i])
    tot = Pii.sum()
    num = np.zeros(NSUB)
    pred = np.zeros(NSUB)
    for b in range(NSUB):
        Pss = P[b][np.ix_(S, S)]
        Psi = P[b][S, i]
        if Pii[b] <= 0:
            continue
        x = np.linalg.solve(Pss, Psi)
        num[b] = float(np.real(Psi.conj() @ x))
        Tc = np.minimum(T[b, S], 0.95 * np.real(np.diag(Pss)))
        Gt = Pss - np.diag(Tc)
        xt = np.linalg.solve(Gt, Psi)
        expl_true = float(np.real(Psi.conj() @ xt))
        Ti = min(T[b, i], 0.95 * Pii[b])
        pred[b] = min(expl_true + Ti, Pii[b] * 10)
    MCF = float(num.sum() / tot)
    true_resid = np.sum(Pii - pred) / tot  # true i power not explained by true inputs
    ceiling = float(np.sum(_safe_div(num, pred) * Pii) / tot)
    return MultipleResult(
        MCF=MCF,
        U_obs=1 - MCF,
        U_tex=(1 - MCF) - float(true_resid),
        U_beyond=float(true_resid),
        MC_ceiling=ceiling,
    )


def residual_cross(
    P: np.ndarray, T: np.ndarray, a: int, S1: list[int], c: int, S2: list[int]
) -> dict[str, float]:
    """Cross-engine coherence of the i-specific residuals e1 = x_a - h1 x_S1 and e2 = x_c - h2 x_S2
    (frequency-domain multiple regression per sub-band). Band average weighted by sqrt(P_e1 P_e2).

    Also returns the raw (a, c) coherence with the same weighting style, the residual power fractions and
    texture ratios, and the texture-corrected residual coherence."""
    coh = np.zeros(NSUB)
    craw = np.zeros(NSUB)
    pe1 = np.zeros(NSUB)
    pe2 = np.zeros(NSUB)
    te1 = np.zeros(NSUB)
    te2 = np.zeros(NSUB)
    for b in range(NSUB):
        M = P[b]
        h1 = np.linalg.solve(M[np.ix_(S1, S1)], M[S1, a])
        h2 = np.linalg.solve(M[np.ix_(S2, S2)], M[S2, c])
        A = [a, *S1]
        B = [c, *S2]
        al = np.r_[1.0, -h1]
        be = np.r_[1.0, -h2]
        p12 = al.conj() @ M[np.ix_(A, B)] @ be
        p11 = float(np.real(al.conj() @ M[np.ix_(A, A)] @ al))
        p22 = float(np.real(be.conj() @ M[np.ix_(B, B)] @ be))
        pe1[b], pe2[b] = p11, p22
        coh[b] = abs(p12) ** 2 / max(p11 * p22, 1e-300)
        craw[b] = abs(M[a, c]) ** 2 / max(float(np.real(M[a, a] * M[c, c])), 1e-300)
        te1[b] = T[b, a] + float(np.sum(np.abs(h1) ** 2 * T[b, S1]))
        te2[b] = T[b, c] + float(np.sum(np.abs(h2) ** 2 * T[b, S2]))
    wres = np.sqrt(pe1 * pe2)
    wraw = np.sqrt(np.real(P[:, a, a]) * np.real(P[:, c, c]))
    att = np.clip(1 - _safe_div(te1, pe1), 1e-3, 1) * np.clip(1 - _safe_div(te2, pe2), 1e-3, 1)
    return {
        "res_coh": float(np.sum(coh * wres) / wres.sum()),
        "res_coh_texcorr": float(np.sum(np.minimum(coh / att, 1.0) * wres) / wres.sum()),
        # common share of the residual variance under a symmetric one-common-factor model: |gamma|
        "res_common_share": float(np.sum(np.sqrt(coh) * wres) / wres.sum()),
        "res_common_share_texcorr": float(np.sum(np.minimum(np.sqrt(coh / att), 1.0) * wres) / wres.sum()),
        "raw_common_share": float(np.sum(np.sqrt(craw) * wraw) / wraw.sum()),
        "raw_coh": float(np.sum(craw * wraw) / wraw.sum()),
        "res_frac_1": float(pe1.sum() / np.real(P[:, a, a]).sum()),
        "res_frac_2": float(pe2.sum() / np.real(P[:, c, c]).sum()),
        "res_over_tex_1": float(pe1.sum() / max(te1.sum(), 1e-300)),
        "res_over_tex_2": float(pe2.sum() / max(te2.sum(), 1e-300)),
    }


def gain_phase(P: np.ndarray, i: int, j: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per sub-band coherence, H1 gain |P_ij| / P_ii and phase [rad] of channel j relative to i."""
    Pii = np.real(P[:, i, i])
    Pjj = np.real(P[:, j, j])
    Pij = P[:, i, j]
    C = np.clip(_safe_div(np.abs(Pij) ** 2, Pii * Pjj), 0, 1)
    return C, _safe_div(np.abs(Pij), Pii), np.angle(Pij)


def delay_lag_fit(Pij: np.ndarray, C: np.ndarray, K: int) -> dict[str, float]:
    """Descriptive: weighted grid fit of the unwrapped phase over FIT_SUBS by (i) pure delay, (ii) first-order
    lag, (iii) delay + lag, phi = -2 pi f tau_d - atan(2 pi f tau_l). Weights as `equivalent_delay`."""
    sb = FIT_SUBS
    ph = unwrapped_phase(Pij)
    c = np.clip(C[sb], 0.01, 0.99)
    w = max(K, 1) * NU_PER_SEGMENT * c / (1 - c)
    om = 2 * np.pi * SUB_FC[sb]
    td = np.round(np.arange(-2.0, 2.0001, 0.01), 2)
    tl = np.round(np.arange(0.0, 5.0001, 0.01), 2)
    best = (np.inf, 0.0, 0.0)
    lagpart = -np.arctan(np.outer(tl, om))  # (L, nb)
    for d in td:
        model = -om * d + lagpart
        sse = np.sum(w * (ph[None, :] - model) ** 2, axis=1)
        k = int(np.argmin(sse))
        if sse[k] < best[0]:
            best = (float(sse[k]), float(d), float(tl[k]))
    sse_d = np.sum(w * (ph[None, :] + np.outer(td, om)) ** 2, axis=1)
    kd = int(np.argmin(sse_d))
    sse_l = np.sum(w * (ph[None, :] - lagpart) ** 2, axis=1)
    kl = int(np.argmin(sse_l))
    return {
        "delay_only_tau": float(td[kd]),
        "delay_only_wsse": float(sse_d[kd]),
        "lag_only_tau": float(tl[kl]),
        "lag_only_wsse": float(sse_l[kl]),
        "delay_lag_tau_d": best[1],
        "delay_lag_tau_l": best[2],
        "delay_lag_wsse": best[0],
    }


# ---------------------------------------------------------------- DEVIATIONS.md D3 (added after verification)
def texture_first_decomposition(P: np.ndarray, T: np.ndarray, i: int, j: int) -> dict[str, float]:
    """Texture-first split of 1 - r (DEVIATIONS.md D3; sensitivity to the pre-registered ordering A).

    Independent texture adds power but no cross-power, so it is removed first and exactly:
    r_truth = sum Re P_ij / sqrt(sum(P_ii - T_ii) sum(P_jj - T_jj)) (texture clipped at 0.95 P per sub-band).
    The truth-level loss 1 - r_truth is then split on the texture-free spectra into a dynamic part
    1 - r_lag* (coherence 1 at the observed phase and the truth-level amplitude spectra) and an
    independent-variance part r_lag* - r_truth. Shares are fractions of the observed loss 1 - r:
    tex = (r_truth - r) / (1 - r), dyn = (1 - r_lag*) / (1 - r), beyond = (r_lag* - r_truth) / (1 - r).
    """
    Pii = np.real(P[:, i, i])
    Pjj = np.real(P[:, j, j])
    Pij = P[:, i, j]
    Ti = np.minimum(T[:, i], 0.95 * Pii)
    Tj = np.minimum(T[:, j], 0.95 * Pjj)
    r = float(np.real(Pij).sum() / np.sqrt(Pii.sum() * Pjj.sum()))
    Qi, Qj = Pii - Ti, Pjj - Tj
    norm = np.sqrt(Qi.sum() * Qj.sum())
    r_truth = float(np.real(Pij).sum() / norm)
    w = np.sqrt(Qi * Qj) / norm
    r_lag = float(np.sum(w * np.cos(np.angle(Pij))))
    L = 1 - r
    return {
        "r_truth": r_truth,
        "r_lag": r_lag,
        "r_shape": float(np.sum(w)),
        "s_tex": (r_truth - r) / L,
        "s_dyn": (1 - r_lag) / L,
        "s_beyond": (r_lag - r_truth) / L,
    }
