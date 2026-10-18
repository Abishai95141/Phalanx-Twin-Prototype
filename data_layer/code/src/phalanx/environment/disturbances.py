"""AD-32 per-unit process disturbances: a latent-factor bank of state-space shaping filters.

Why (architecture AD-32, P2; `docs/behavioural_targets.md`; round-2 REPORT §3.1, §8 H-a): deterministic,
input-driven engine physics moves engines and spools in lockstep (round-2 fast-band EGT_1-EGT_2 0.99 vs real
0.59; N1-N2 0.92 vs real 0.47). Real engines share inputs but carry their *own* disturbances, which enter the
dynamics (M07/M09/M05), not the sensors. The disturbance structure therefore needs:

- **aircraft-common** factors (one realisation per aircraft, shared by every unit): e.g. inlet flow/turbulence
  coupling, aircraft-level fuel-system and electrical/ECS load fluctuations;
- **unit-level** factors (one independent realisation per engine or hydraulic system) that may load several
  channels of the same unit (within-unit, cross-channel coherence < 1, e.g. fuel metering and shaft load);
- **unit-and-channel-specific** factors (a unit-scope factor loading one channel).

Model: every output channel j is a linear combination of independent factor *instances*,
``w_j(t) = sum_i G[i, j] y_i(t)``, where each instance ``y_i = C_i x_i`` is the output of a stable, linear,
time-invariant shaping filter ``dx = A x dt + B dW`` normalised to unit stationary variance. So
- the PSD of each channel is ``S_j(f) = sum_i G[i, j]^2 S_i(f)`` (configurable through filter forms and
  loadings), and
- the cross-spectrum of channels j, k is ``S_jk(f) = sum_i G[i, j] G[i, k] S_i(f)``; the coherence
  ``|S_jk|^2 / (S_jj S_kk)`` is configurable through which factors are shared (scope) and their PSD shapes,
  and is frequency dependent when shared and private factors have different spectra.

Discretisation is **exact** for the 240 Hz tick (Van Loan): ``x_{k+1} = Phi x_k + L e_k`` with
``Phi = exp(A dt)``, ``L L^T = Q_d = int_0^dt exp(A s) B B^T exp(A^T s) ds``, ``e_k ~ N(0, I)``. The
sampled process therefore has exactly the autocovariance of the continuous one at every lag. Initial
states are drawn from the stationary covariance (no warm-up transient).

Filter forms (each normalised so that Var(C x) = 1; the loading carries the physical scale):
- ``FORM_OU`` (1): first-order Gauss-Markov, correlation time tau; one-sided PSD 4 tau / (1 + (2 pi f tau)^2)
  per Hz.
- ``FORM_OU2`` (2): two cascaded OU stages with equal tau (-40 dB/decade roll-off).
- ``FORM_RESONANT`` (3): damped oscillator (omega_n, zeta): band-limited oscillatory content.

Randomness (AD-37; W1_interfaces §1): aircraft-scope instances are keyed (scenario, tail, sortie);
unit-scope instances (scenario, tail, serial, sortie) with the unit's serial, so each engine draws from its
own serial's stream (CRN across forks; a re-fitted engine brings its own stream). Draw index of instance i at
tick k is ``d_i (k + 1) .. d_i (k + 2) - 1`` (block ``0 .. d_i - 1`` is the stationary initial state).

Parameter values are tagged ASSUMPTION placeholders with sweeps (M03.yaml set ``disturbances``); W2.4
identifies PSDs and coherences on proxy CAL data by closed-loop prediction-error identification (round-2
REPORT §8 H-c).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit
from scipy import linalg

FORM_OU, FORM_OU2, FORM_RESONANT = 1, 2, 3
SCOPE_AIRCRAFT, SCOPE_UNIT = 0, 1
GROUP_ENGINE, GROUP_HYD = 0, 1
#: engine channels: the first five are the columns of env.w_engine (AD-46 added fan_face: fan-face
#: distortion on fan flow capacity and efficiency, the LP-spool-specific path), the sixth is
#: env.w_bleed_pto
ENGINE_CHANNELS = (
    "fuel_metering",
    "combustor_eff",
    "inlet_recovery",
    "shaft_load",
    "fan_face",
    "bleed_pto",
)
N_ENGINE_CHANNELS = len(ENGINE_CHANNELS)
N_W_ENGINE = 5  # columns of env.w_engine
DMAX = 4  # maximum filter state dimension


@dataclass(frozen=True)
class Factor:
    """One latent disturbance factor (see module docstring).

    ``loadings``: SD contributed to each channel of its group (engine: 5 values, dimensionless fractions;
    hydraulic: 1 value in m^3/s). ``fid`` names its RNG stream (``f<fid>``), so it must be stable.
    """

    fid: int
    scope: int
    group: int
    form: int
    tau_s: float = 0.0
    omega_rad_s: float = 0.0
    zeta: float = 0.0
    loadings: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.scope not in (SCOPE_AIRCRAFT, SCOPE_UNIT) or self.group not in (GROUP_ENGINE, GROUP_HYD):
            raise ValueError(f"factor {self.fid}: bad scope/group")
        want = N_ENGINE_CHANNELS if self.group == GROUP_ENGINE else 1
        if len(self.loadings) != want:
            raise ValueError(f"factor {self.fid}: {want} loadings expected, got {len(self.loadings)}")
        if self.form in (FORM_OU, FORM_OU2) and not self.tau_s > 0:
            raise ValueError(f"factor {self.fid}: tau_s must be > 0")
        if self.form == FORM_RESONANT and not (self.omega_rad_s > 0 and self.zeta > 0):
            raise ValueError(f"factor {self.fid}: resonant form needs omega > 0 and zeta > 0")
        if self.form not in (FORM_OU, FORM_OU2, FORM_RESONANT):
            raise ValueError(f"factor {self.fid}: unknown form {self.form}")

    @property
    def stream_name(self) -> str:
        return f"f{self.fid:02d}"


def continuous_ss(f: Factor) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(A, B, C) of the factor's shaping filter with Var(C x) = 1 at stationarity."""
    if f.form == FORM_OU:
        a = np.array([[-1.0 / f.tau_s]])
        b = np.array([[1.0]])
        c = np.array([1.0])
    elif f.form == FORM_OU2:
        a = np.array([[-1.0 / f.tau_s, 0.0], [1.0 / f.tau_s, -1.0 / f.tau_s]])
        b = np.array([[1.0], [0.0]])
        c = np.array([0.0, 1.0])
    else:
        w, z = f.omega_rad_s, f.zeta
        a = np.array([[0.0, 1.0], [-(w**2), -2.0 * z * w]])
        b = np.array([[0.0], [1.0]])
        c = np.array([1.0, 0.0])
    p = linalg.solve_continuous_lyapunov(a, -b @ b.T)
    var = float(c @ p @ c)
    return a, b / np.sqrt(var), c


def stationary_cov(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return linalg.solve_continuous_lyapunov(a, -b @ b.T)


def exact_discretisation(a: np.ndarray, b: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Van Loan: (Phi, Q_d) for dx = A x dt + B dW sampled every dt."""
    n = a.shape[0]
    m = np.zeros((2 * n, 2 * n))
    m[:n, :n] = -a
    m[:n, n:] = b @ b.T
    m[n:, n:] = a.T
    e = linalg.expm(m * dt)
    phi = e[n:, n:].T
    q = phi @ e[:n, n:]
    return phi, 0.5 * (q + q.T)


def psd_sqrt(q: np.ndarray) -> np.ndarray:
    """Symmetric square root factor L with L L^T = Q (robust to semi-definite Q)."""
    w, v = np.linalg.eigh(0.5 * (q + q.T))
    w = np.clip(w, 0.0, None)
    return v * np.sqrt(w)


@dataclass(frozen=True)
class Instance:
    factor: Factor
    unit: int  # -1 for aircraft scope
    stream: str  # stream component name


class DisturbanceBank:
    """All factor instances of one aircraft and the loading map onto the output vector.

    Output vector layout (J = 6 e + h): ``w_engine`` row-major (unit e, column c) for c < 5, then
    ``w_bleed_pto`` (e), then ``w_hyd`` (h).
    """

    def __init__(self, factors: tuple[Factor, ...], n_engines: int, n_hyd: int, dt: float) -> None:
        if n_engines < 1 or n_hyd < 0:
            raise ValueError("n_engines >= 1, n_hyd >= 0")
        ids = [f.fid for f in factors]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate factor ids")
        self.factors = tuple(sorted(factors, key=lambda f: f.fid))
        self.n_engines, self.n_hyd, self.dt = n_engines, n_hyd, dt
        self.n_out = N_ENGINE_CHANNELS * n_engines + n_hyd
        inst: list[Instance] = []
        for f in self.factors:
            n_units = n_engines if f.group == GROUP_ENGINE else n_hyd
            if f.scope == SCOPE_AIRCRAFT:
                inst.append(Instance(f, -1, f.stream_name))
            else:
                inst.extend(Instance(f, u, f.stream_name) for u in range(n_units))
        self.instances = tuple(inst)
        ni = len(inst)
        self.dims = np.zeros(ni, dtype=np.int64)
        self.phi = np.zeros((ni, DMAX, DMAX))
        self.lq = np.zeros((ni, DMAX, DMAX))
        self.linit = np.zeros((ni, DMAX, DMAX))
        self.cvec = np.zeros((ni, DMAX))
        self.gain = np.zeros((ni, self.n_out))
        self._cont: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for i, it in enumerate(inst):
            a, b, c = continuous_ss(it.factor)
            d = a.shape[0]
            phi, q = exact_discretisation(a, b, dt)
            self.dims[i] = d
            self.phi[i, :d, :d] = phi
            self.lq[i, :d, :d] = psd_sqrt(q)
            self.linit[i, :d, :d] = psd_sqrt(stationary_cov(a, b))
            self.cvec[i, :d] = c
            self._cont.append((a, b, c))
            for j in self._targets(it):
                self.gain[i, j] = self._loading(it, j)
        for arr in (self.dims, self.phi, self.lq, self.linit, self.cvec, self.gain):
            arr.flags.writeable = False
        self.state_size = int(self.dims.sum())
        self.offsets = np.concatenate([[0], np.cumsum(self.dims)[:-1]]).astype(np.int64)
        self.offsets.flags.writeable = False

    # ------------------------------------------------------------------ output map
    def out_index(self, group: int, unit: int, channel: int) -> int:
        e = self.n_engines
        if group == GROUP_HYD:
            return N_ENGINE_CHANNELS * e + unit
        if channel < N_W_ENGINE:
            return N_W_ENGINE * unit + channel
        return N_W_ENGINE * e + unit

    def _units(self, it: Instance) -> range:
        if it.unit >= 0:
            return range(it.unit, it.unit + 1)
        return range(self.n_engines if it.factor.group == GROUP_ENGINE else self.n_hyd)

    def _targets(self, it: Instance) -> list[int]:
        out = []
        nch = N_ENGINE_CHANNELS if it.factor.group == GROUP_ENGINE else 1
        for u in self._units(it):
            for ch in range(nch):
                if it.factor.loadings[ch] != 0.0:
                    out.append(self.out_index(it.factor.group, u, ch))
        return out

    def _loading(self, it: Instance, j: int) -> float:
        nch = N_ENGINE_CHANNELS if it.factor.group == GROUP_ENGINE else 1
        for u in self._units(it):
            for ch in range(nch):
                if self.out_index(it.factor.group, u, ch) == j:
                    return float(it.factor.loadings[ch])
        return 0.0

    def split(self, out: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(..., J) -> w_engine (..., e, 5), w_bleed_pto (..., e), w_hyd (..., h)."""
        e = self.n_engines
        lead = out.shape[:-1]
        nw = N_W_ENGINE
        w_eng = out[..., : nw * e].reshape(*lead, e, nw)
        w_bleed = out[..., nw * e : (nw + 1) * e]
        w_hyd = out[..., (nw + 1) * e :]
        return w_eng, w_bleed, w_hyd

    # ------------------------------------------------------------------ analytic spectra (tests, W2.4)
    def instance_psd(self, i: int, f_hz: np.ndarray) -> np.ndarray:
        """One-sided PSD (per Hz) of instance i's unit-variance output **as sampled** (exact discrete)."""
        d = int(self.dims[i])
        phi = self.phi[i, :d, :d]
        lq = self.lq[i, :d, :d]
        c = self.cvec[i, :d]
        out = np.empty(np.size(f_hz))
        for k, f in enumerate(np.atleast_1d(f_hz)):
            z = np.exp(2j * np.pi * f * self.dt)
            h = np.linalg.solve(z * np.eye(d) - phi, lq)
            g = c @ h
            out[k] = 2.0 * self.dt * float(np.real(g @ g.conj()))
        return out

    def cross_psd(self, j: int, k: int, f_hz: np.ndarray) -> np.ndarray:
        """One-sided (real) cross-spectrum between outputs j and k: sum_i G_ij G_ik S_i(f)."""
        s = np.zeros(np.size(f_hz))
        for i in range(len(self.instances)):
            g = self.gain[i, j] * self.gain[i, k]
            if g != 0.0:
                s += g * self.instance_psd(i, f_hz)
        return s

    def coherence(self, j: int, k: int, f_hz: np.ndarray) -> np.ndarray:
        """Target magnitude-squared coherence |S_jk|^2 / (S_jj S_kk) (A3 configured targets)."""
        sjk = self.cross_psd(j, k, f_hz)
        return sjk**2 / (self.cross_psd(j, j, f_hz) * self.cross_psd(k, k, f_hz))

    def variance(self, j: int) -> float:
        return float(np.sum(self.gain[:, j] ** 2))


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def bank_init(x, dims, offsets, linit, eps0):
    """Stationary initial states: x_i = Linit_i e_i (eps0 flat, laid out like x)."""
    for i in range(dims.shape[0]):
        d = dims[i]
        o = offsets[i]
        for r in range(d):
            acc = 0.0
            for c in range(d):
                acc += linit[i, r, c] * eps0[o + c]
            x[o + r] = acc


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def bank_step(x, dims, offsets, phi, lq, cvec, gain, eps, tmp, out):
    """x <- Phi x + L eps per instance (in place); out[j] = sum_i gain[i, j] (C_i x_i)."""
    nout = out.shape[0]
    for j in range(nout):
        out[j] = 0.0
    for i in range(dims.shape[0]):
        d = dims[i]
        o = offsets[i]
        for r in range(d):
            acc = 0.0
            for c in range(d):
                acc += phi[i, r, c] * x[o + c]
            for c in range(d):
                acc += lq[i, r, c] * eps[o + c]
            tmp[r] = acc
        y = 0.0
        for r in range(d):
            x[o + r] = tmp[r]
            y += cvec[i, r] * tmp[r]
        for j in range(nout):
            g = gain[i, j]
            if g != 0.0:
                out[j] += g * y


__all__ = [
    "DMAX",
    "ENGINE_CHANNELS",
    "FORM_OU",
    "FORM_OU2",
    "FORM_RESONANT",
    "GROUP_ENGINE",
    "GROUP_HYD",
    "SCOPE_AIRCRAFT",
    "SCOPE_UNIT",
    "DisturbanceBank",
    "Factor",
    "Instance",
    "bank_init",
    "bank_step",
    "continuous_ss",
    "exact_discretisation",
]
