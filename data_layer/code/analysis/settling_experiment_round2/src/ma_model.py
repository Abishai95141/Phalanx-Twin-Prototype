"""M-A: proxy engine model (physics-structured grey box), PREREGISTRATION.md section 3.

One instance per engine position k = 1..4. Every instance shares the engine-TYPE maps and dynamics and carries
its own unit offsets (additive, on the output of each steady map; sum-to-zero over the four positions, so the
type maps describe the average engine). Inputs per instance: PLA_k and the flight condition (ALT, MACH, TAT);
inlet corrections theta = T_t2/288.15 (from TAT) and delta = p_t2/p_SL (ISA static pressure from ALT, ram
recovery from MACH).

Causal chain at 4 Hz (dt = 0.25 s), every stage driven by the SIMULATED upstream signal (output error):
  1. fuel control  Wd = f_P(PLA) + cM (M - 0.5) + cD ln(delta) + cT (theta - 1) + a_f,k        [lb/h, corrected]
                   Wc[i] = Wc[i-1] + clip(alpha_f (Wd[i] - Wc[i-1]), -R_dn dt, +R_up dt)          (asym. rate limits)
  2. core          N2c_ss = g(Wc) + a_g,k ;  N2c lag, tau_2u if rising else tau_2d
  3. fan           N1c_ss = h(N2c) + a_h,k ;  N1c lag tau_1
  4. EGT           T_ss = theta^a (k_W(Wc) + k_N(N1c) + a_k,k)  [K] ;  EGT = lag(T_ss, tau_T) - 273.15
  physical outputs: FF = Wc delta sqrt(theta), N2 = N2c sqrt(theta), N1 = N1c sqrt(theta)
Steady maps f_P, g, h, k_W, k_N: monotone (non-decreasing) PCHIP splines with K <= 8 knots at fixed CAL quantiles of
their (measured, corrected) input, knot values parametrised as first value + non-negative increments; linear
extrapolation with the end slopes (monotone everywhere). alpha = 1 - exp(-dt / tau).
Fitting: staged output-error least squares (scipy least_squares, trf, bounds), stage s simulating from the
inputs through the already-fitted upstream stages: FF -> N2 -> N1 -> EGT. The loss ignores the first 60 s of
every running segment (state initialised at the steady value of the map, start transients not modelled).
No black-box ML (decision D4).
"""
import json
import os
import time

import numpy as np
from numba import njit
from scipy.interpolate import PchipInterpolator
from scipy.optimize import least_squares

import r2common as R

DT = R.DT
BURN_S = 60.0
SCALE = {"FF": 100.0, "N2": 1.0, "N1": 1.0, "EGT": 10.0}     # residual scales (numerical conditioning only)


# ------------------------------------------------------------------ recursions
@njit(cache=True, error_model="numpy", nogil=True)
def _rate_lag(u, start, alpha, rup, rdn):
    n = u.size
    out = np.empty(n)
    x = u[0]
    for i in range(n):
        if start[i]:
            x = u[i]
        else:
            d = alpha * (u[i] - x)
            if d > rup:
                d = rup
            elif d < -rdn:
                d = -rdn
            x = x + d
        out[i] = x
    return out


@njit(cache=True, error_model="numpy", nogil=True)
def _asym_lag(u, start, a_up, a_dn):
    n = u.size
    out = np.empty(n)
    x = u[0]
    for i in range(n):
        if start[i]:
            x = u[i]
        else:
            if u[i] > x:
                x = x + a_up * (u[i] - x)
            else:
                x = x + a_dn * (u[i] - x)
        out[i] = x
    return out


def alpha(tau):
    return 1.0 - np.exp(-DT / max(tau, 1e-3))


# ------------------------------------------------------------------ monotone maps
def pchip_slopes(x, v):
    """Fritsch-Carlson knot derivatives, identical to scipy.interpolate.PchipInterpolator._find_derivatives."""
    h = np.diff(x)
    m = np.diff(v) / h
    K = x.size
    d = np.zeros(K)
    if K == 2:
        return np.array([m[0], m[0]])
    smk = np.sign(m)
    cond = (smk[1:] != smk[:-1]) | (m[1:] == 0) | (m[:-1] == 0)
    w1 = 2 * h[1:] + h[:-1]
    w2 = h[1:] + 2 * h[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        whmean = (w1 / m[:-1] + w2 / m[1:]) / (w1 + w2)
    inner = np.where(cond, 0.0, 1.0 / np.where(cond, 1.0, whmean))
    d[1:-1] = inner

    def edge(h0, h1, m0, m1):
        dd = ((2 * h0 + h1) * m0 - h0 * m1) / (h0 + h1)
        if np.sign(dd) != np.sign(m0):
            dd = 0.0
        elif (np.sign(m0) != np.sign(m1)) and (abs(dd) > 3 * abs(m0)):
            dd = 3 * m0
        return dd
    d[0] = edge(h[0], h[1], m[0], m[1])
    d[-1] = edge(h[-1], h[-2], m[-1], m[-2])
    return d


@njit(cache=True, error_model="numpy", nogil=True)
def _pchip_eval(x, v, d, z):
    K = x.size
    n = z.size
    out = np.empty(n)
    for i in range(n):
        zi = z[i]
        if zi <= x[0]:
            out[i] = v[0] + d[0] * (zi - x[0])
        elif zi >= x[K - 1]:
            out[i] = v[K - 1] + d[K - 1] * (zi - x[K - 1])
        else:
            lo, hi = 0, K - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if x[mid] <= zi:
                    lo = mid
                else:
                    hi = mid
            h = x[lo + 1] - x[lo]
            t = (zi - x[lo]) / h
            t2 = t * t
            t3 = t2 * t
            out[i] = (v[lo] * (2 * t3 - 3 * t2 + 1) + h * d[lo] * (t3 - 2 * t2 + t)
                      + v[lo + 1] * (-2 * t3 + 3 * t2) + h * d[lo + 1] * (t3 - t2))
    return out


class MonoMap:
    """Monotone PCHIP through (knots, first value + cumulative non-negative increments); linear extrapolation with
    the end slopes (monotone everywhere). Evaluated by a numba kernel identical to scipy's PCHIP."""

    def __init__(self, knots):
        self.x = np.asarray(knots, float)
        self.K = self.x.size

    def values(self, p):
        return p[0] + np.r_[0.0, np.cumsum(p[1:self.K])]

    def __call__(self, p, z):
        v = self.values(p)
        if np.all(np.diff(v) == 0):
            return np.full(np.shape(z), v[0])
        d = pchip_slopes(self.x, v)
        return _pchip_eval(self.x, v, d, np.ascontiguousarray(z, dtype=np.float64))

    def scipy_eval(self, p, z):
        """Reference implementation (scipy) used by the self-test."""
        v = self.values(p)
        f = PchipInterpolator(self.x, v, extrapolate=False)
        dd = f.derivative()
        s0, s1 = float(dd(self.x[0])), float(dd(self.x[-1]))
        zc = np.clip(z, self.x[0], self.x[-1])
        return f(zc) + s0 * np.minimum(z - self.x[0], 0) + s1 * np.maximum(z - self.x[-1], 0)

    @staticmethod
    def init_from(knots, z, y):
        """Initial knot values: binned medians of y around each knot, made monotone (running max)."""
        x = np.asarray(knots, float)
        edges = np.r_[-np.inf, 0.5 * (x[1:] + x[:-1]), np.inf]
        v = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (z >= a) & (z < b)
            v.append(np.median(y[m]) if m.sum() > 20 else np.nan)
        v = np.array(v, float)
        ok = np.isfinite(v)
        v = np.interp(np.arange(x.size), np.flatnonzero(ok), v[ok])
        v = np.maximum.accumulate(v)
        return np.r_[v[0], np.maximum(np.diff(v), 0.0)]


def knot_rule(z, K, rule):
    """Fixed knot positions from the CAL distribution of the map input: 'mix' = mean of quantile and evenly spaced
    positions between the 0.5 and 99.5 percentiles; 'log' = evenly spaced in log (fuel-flow axis)."""
    lo, hi = np.percentile(z, [0.5, 99.5])
    if rule == "log":
        return np.exp(np.linspace(np.log(max(lo, 1.0)), np.log(hi), K))
    return np.sort(0.5 * knots_at_quantiles(z, K) + 0.5 * np.linspace(lo, hi, K))


def knots_at_quantiles(z, K, lo=0.5, hi=99.5):
    q = np.percentile(z, np.linspace(lo, hi, K))
    q = np.unique(np.round(q, 6))
    if q.size < K:                     # degenerate distributions: spread evenly
        q = np.linspace(np.percentile(z, lo), np.percentile(z, hi), K)
    return q


# ------------------------------------------------------------------ data assembly
def running_mask_cal(d):
    """CAL fitting mask (outputs may be used on CAL): engine k running = N2_k > 40 % and PH in 2..7."""
    ph_ok = np.isin(d["PH"], [2, 3, 4, 5, 6, 7])
    return (d["Y"]["N2"] > 40.0) & ph_ok[None, :]


def running_mask_inputs(d):
    """Synthesis mask (inputs only, PREREGISTRATION section 6.4): engine running when PH in 2..7."""
    ph_ok = np.isin(d["PH"], [2, 3, 4, 5, 6, 7])
    return np.repeat(ph_ok[None, :], 4, 0)


def segments(mask_row, min_len):
    m = np.r_[False, mask_row, False].astype(int)
    dd = np.diff(m)
    return [(a, b) for a, b in zip(np.flatnonzero(dd == 1), np.flatnonzero(dd == -1)) if b - a >= min_len]


class Batch:
    """Concatenation of running segments over flights and engine positions."""

    def __init__(self, flights, masks, with_outputs=True, min_len_s=120.0, burn_s=BURN_S):
        cols = {k: [] for k in ("PLA", "M", "lnd", "th", "eng", "start", "w", "fi", "idx")}
        ys = {f: [] for f in R.FAM}
        self.seg = []
        for fi, (d, mk) in enumerate(zip(flights, masks)):
            for k in range(4):
                for a, b in segments(mk[k], int(min_len_s * R.RATE)):
                    L = b - a
                    cols["PLA"].append(d["PLA"][k, a:b])
                    cols["M"].append(d["MACH"][a:b])
                    cols["lnd"].append(np.log(d["delta"][a:b]))
                    cols["th"].append(d["theta"][a:b])
                    cols["eng"].append(np.full(L, k, np.int64))
                    st = np.zeros(L, bool)
                    st[0] = True
                    cols["start"].append(st)
                    w = np.ones(L)
                    w[:int(burn_s * R.RATE)] = 0.0
                    cols["w"].append(w)
                    cols["fi"].append(np.full(L, fi, np.int64))
                    cols["idx"].append(np.arange(a, b))
                    self.seg.append((fi, k, a, b))
                    if with_outputs:
                        for f in R.FAM:
                            ys[f].append(d["Y"][f][k, a:b])
        for k, v in cols.items():
            setattr(self, k, np.concatenate(v) if v else np.zeros(0))
        self.start = self.start.astype(bool)
        self.sqth = np.sqrt(self.th)
        self.delta = np.exp(self.lnd)
        self.Y = {f: np.concatenate(ys[f]) for f in R.FAM} if with_outputs else None
        self.n = self.PLA.size

    def corrected_measured(self, a_exp=0.6):
        Y = self.Y
        return {"Wc": Y["FF"] / (self.delta * self.sqth), "N2c": Y["N2"] / self.sqth, "N1c": Y["N1"] / self.sqth,
                "Tc": (Y["EGT"] + R.T0K) / self.th ** a_exp}


# ------------------------------------------------------------------ model
@njit(cache=True, error_model="numpy", nogil=True)
def _var_lag(u, start, a):
    """First-order lag with a per-sample smoothing factor a[i] (flow-dependent sensor time constant)."""
    n = u.size
    out = np.empty(n)
    x = u[0]
    for i in range(n):
        if start[i]:
            x = u[i]
        else:
            x = x + a[i] * (u[i] - x)
        out[i] = x
    return out


@njit(cache=True, error_model="numpy", nogil=True)
def _pchip1(x, v, d, zi):
    K = x.size
    if zi <= x[0]:
        return v[0] + d[0] * (zi - x[0])
    if zi >= x[K - 1]:
        return v[K - 1] + d[K - 1] * (zi - x[K - 1])
    lo, hi = 0, K - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if x[mid] <= zi:
            lo = mid
        else:
            hi = mid
    h = x[lo + 1] - x[lo]
    t = (zi - x[lo]) / h
    t2 = t * t
    t3 = t2 * t
    return (v[lo] * (2 * t3 - 3 * t2 + 1) + h * d[lo] * (t3 - 2 * t2 + t)
            + v[lo + 1] * (-2 * t3 + 3 * t2) + h * d[lo + 1] * (t3 - t2))


@njit(cache=True, error_model="numpy", nogil=True)
def _pchip_h(x, v, d, zi, lo):
    """PCHIP value at zi, searching from the previous interval lo (signals vary slowly). Returns (value, lo)."""
    K = x.size
    if zi <= x[0]:
        return v[0] + d[0] * (zi - x[0]), 0
    if zi >= x[K - 1]:
        return v[K - 1] + d[K - 1] * (zi - x[K - 1]), K - 2
    while lo > 0 and zi < x[lo]:
        lo -= 1
    while lo < K - 2 and zi >= x[lo + 1]:
        lo += 1
    h = x[lo + 1] - x[lo]
    t = (zi - x[lo]) / h
    t2 = t * t
    t3 = t2 * t
    return (v[lo] * (2 * t3 - 3 * t2 + 1) + h * d[lo] * (t3 - 2 * t2 + t)
            + v[lo + 1] * (-2 * t3 + 3 * t2) + h * d[lo + 1] * (t3 - t2)), lo


@njit(cache=True, error_model="numpy", nogil=True)
def _k_ffn2(PLA, M, lnd, th, sqth, delta, eng, start, fx, fv, fd, gx, gv, gd, cM, cD, cT, af, rup, rdn,
            offF, offN2, health, sensor, a_s, a2u, a2d, keep):
    """Outputs only at samples with keep[i] (compact arrays, in order); keep = all True for full outputs."""
    n = PLA.size
    nk = 0
    for i in range(n):
        if keep[i]:
            nk += 1
    wc_o = np.empty(nk)
    ff_o = np.empty(nk)
    n2c_o = np.empty(nk)
    n2_o = np.empty(nk)
    j = 0
    x = 0.0
    ffs = 0.0
    n2 = 0.0
    lf = 0
    lg = 0
    for i in range(n):
        e = eng[i]
        fval, lf = _pchip_h(fx, fv, fd, PLA[i], lf)
        base = fval + cM * (M[i] - 0.5) + cD * lnd[i] + cT * (th[i] - 1.0)
        if health:
            wd = base * (1.0 + offF[e])
        else:
            wd = base + offF[e]
        if start[i]:
            x = wd
        else:
            dd = af * (wd - x)
            if dd > rup:
                dd = rup
            elif dd < -rdn:
                dd = -rdn
            x = x + dd
        wc = x if x > 0.0 else 0.0
        fft = wc * delta[i] * sqth[i]
        if sensor:
            if start[i]:
                ffs = fft
            else:
                ffs = ffs + a_s * (fft - ffs)
        else:
            ffs = fft
        if health:
            u, lg = _pchip_h(gx, gv, gd, wc / (1.0 + offF[e]), lg)
        else:
            u, lg = _pchip_h(gx, gv, gd, wc, lg)
            u = u + offN2[e]
        if start[i]:
            n2 = u
        elif u > n2:
            n2 = n2 + a2u * (u - n2)
        else:
            n2 = n2 + a2d * (u - n2)
        if keep[i]:
            wc_o[j] = wc
            ff_o[j] = ffs
            n2c_o[j] = n2
            n2_o[j] = n2 * sqth[i] + (offN2[e] if health else 0.0)
            j += 1
    return wc_o, ff_o, n2c_o, n2_o


@njit(cache=True, error_model="numpy", nogil=True)
def _k_n1(n2c, eng, start, hx, hv, hd, off, a1, keep):
    n = n2c.size
    nk = 0
    for i in range(n):
        if keep[i]:
            nk += 1
    out = np.empty(nk)
    x = 0.0
    lh = 0
    j = 0
    for i in range(n):
        u, lh = _pchip_h(hx, hv, hd, n2c[i], lh)
        u = u + off[eng[i]]
        if start[i]:
            x = u
        else:
            x = x + a1 * (u - x)
        if keep[i]:
            out[j] = x
            j += 1
    return out


@njit(cache=True, error_model="numpy", nogil=True)
def _k_egt(wc, n1c, th, sqth, delta, eng, start, wx, wv, wd, nx, nv, nd, a_exp, off, health, sensor, aT, tau_tc_ref,
           w_exp, dt, t0k, keep):
    n = wc.size
    nk = 0
    for i in range(n):
        if keep[i]:
            nk += 1
    out = np.empty(nk)
    j = 0
    tg = 0.0
    tm = 0.0
    lw = 0
    ln = 0
    for i in range(n):
        cw, lw = _pchip_h(wx, wv, wd, wc[i], lw)
        cn, ln = _pchip_h(nx, nv, nd, n1c[i], ln)
        core = cw + cn
        if not health:
            core = core + off[eng[i]]
        tss = th[i] ** a_exp * core
        if start[i]:
            tg = tss
        else:
            tg = tg + aT * (tss - tg)
        if sensor:
            n1 = n1c[i] if n1c[i] > 1.0 else 1.0
            wrel = delta[i] / sqth[i] * (n1 / 90.0)
            if wrel < 0.05:
                wrel = 0.05
            tau = tau_tc_ref * wrel ** w_exp
            a = 1.0 - np.exp(-dt / tau)
            if start[i]:
                tm = tg
            else:
                tm = tm + a * (tg - tm)
        else:
            tm = tg
        if keep[i]:
            out[j] = tm - t0k + (off[eng[i]] if health else 0.0)
            j += 1
    return out


N_THREADS = int(os.environ.get("R2_THREADS", "4"))
FTOL = 1e-6          # convergence: relative cost change per accepted step (scipy trf ftol); status > 0 = converged


def _threaded_jac(fun, lo, hi, rel_step=1e-4):
    """Forward-difference Jacobian (scipy's 2-point rule: h = rel_step * max(1, |x|), stepping backwards at an
    upper bound), columns evaluated in parallel threads (the numba kernels release the GIL)."""
    from concurrent.futures import ThreadPoolExecutor

    def jac(x, *args):
        f0 = fun(x)
        h = rel_step * np.maximum(1.0, np.abs(x))
        h = np.where(x + h > hi, -h, h)

        J = np.empty((f0.size, x.size))                  # preallocated (peak memory: one m x n array)

        def col(j):
            xj = x.copy()
            xj[j] = x[j] + h[j]
            J[:, j] = (fun(xj) - f0) / h[j]
        with ThreadPoolExecutor(N_THREADS) as ex:
            list(ex.map(col, range(x.size)))
        return J
    return jac


VARIANTS = {
    # P: as pre-registered (section 3): additive unit offsets on the output of each steady map; no sensor stage.
    "P": {"sensor": False, "offsets": "output"},
    # S: amendments A6 + A7: sensor-dynamics stage (FF first-order lag; EGT thermocouple lag tau ~ W^-0.5)
    #    between M-A truth and M-B, and unit variation as component-health deltas + sensor installation biases.
    "S": {"sensor": True, "offsets": "health"},
}
W_EXP = -0.5            # thermocouple time-constant exponent on gas mass flow (AGARD; amendment A6)


class MA:
    """Stages (fitted in this order, each by output-error least squares through the simulated upstream signals):
      FFN2  fuel control + core, fitted JOINTLY on measured FF and N2 (makes a sensor lag on FF identifiable)
      N1    fan
      EGT   EGT map, thermal lag (+ thermocouple lag in variant S)
    Unit variation (per position, sum-to-zero over the four positions):
      variant P: a_f (lb/h on the corrected fuel demand), a_g (% on g), a_h (% on h), a_k (K on k)  [pre-registered]
      variant S: e (fractional fuel-efficiency delta: demand x (1+e), core sees Wc/(1+e)), m (fan/core match, %
                 on h), b_N2 (% N2 sensor bias), b_EGT (degC EGT sensor bias)  [amendment A7]
    """
    STAGES = ("FFN2", "N1", "EGT")

    def __init__(self, K=8, variant="P"):
        self.K = K
        self.variant = variant
        self.V = VARIANTS[variant]
        self.knots = {}
        self.p = {}
        self.info = {}

    # ---------------------------------------------------------------- layout
    def layout(self, stage):
        K = self.K
        if stage == "FFN2":
            L = [("f", K), ("cM", 1), ("cD", 1), ("cT", 1), ("ltau_f", 1), ("lRup", 1), ("lRdn", 1), ("offF", 3),
                 ("g", K), ("ltau_2u", 1), ("ltau_2d", 1), ("offN2", 3)]
            if self.V["sensor"]:
                L.append(("ltau_FFs", 1))
            return L
        if stage == "N1":
            return [("h", K), ("ltau_1", 1), ("offN1", 3)]
        if stage == "EGT":
            L = [("kW", K), ("kN", K - 1), ("a", 1), ("ltau_T", 1), ("offE", 3)]
            if self.V["sensor"]:
                L.append(("ltau_TC", 1))
            return L
        raise ValueError(stage)

    def unpack(self, stage, p):
        out, i = {}, 0
        for name, L in self.layout(stage):
            out[name] = p[i:i + L]
            i += L
        return out

    INC_MAX = {"f": 2500.0, "g": 60.0, "h": 80.0, "kW": 600.0, "kN": 300.0}

    def bounds(self, stage):
        lo, hi = [], []
        for name, L in self.layout(stage):
            if name in ("f", "g", "h", "kW"):
                lo += [-np.inf] + [0.0] * (L - 1)
                hi += [np.inf] + [self.INC_MAX[name]] * (L - 1)
            elif name == "kN":
                lo += [0.0] * L
                hi += [self.INC_MAX[name]] * L
            elif name == "a":
                lo += [0.0]
                hi += [1.5]
            elif name.startswith("ltau"):
                lo += [np.log(0.1)]
                hi += [np.log(30.0)]
            elif name.startswith("lR"):
                lo += [np.log(10.0)]
                hi += [np.log(1e6)]
            elif name == "offF" and self.V["offsets"] == "health":
                lo += [-0.3] * L
                hi += [0.3] * L
            else:
                lo += [-np.inf] * L
                hi += [np.inf] * L
        return np.array(lo), np.array(hi)

    @staticmethod
    def expand(off3):
        return np.r_[off3, -np.sum(off3)]

    def unit(self, B, override=None):
        """Per-sample unit parameters {offF, offN2, offN1, offE} (override: {name: 4-vector})."""
        out = {}
        for st, names in (("FFN2", ("offF", "offN2")), ("N1", ("offN1",)), ("EGT", ("offE",))):
            q = self.unpack(st, self.p[st]) if st in self.p else None
            for nm in names:
                v = override[nm] if override is not None else self.expand(q[nm])
                out[nm] = np.asarray(v)[B.eng]
        return out

    # ---------------------------------------------------------------- simulation
    def _ref_sim_ffn2(self, B, p, u=None):
        """Returns (Wc_true, FF_measured_physical, N2c_true, N2_measured_physical)."""
        q = self.unpack("FFN2", p)
        offF = u["offF"] if u is not None else self.expand(q["offF"])[B.eng]
        offN2 = u["offN2"] if u is not None else self.expand(q["offN2"])[B.eng]
        base = MonoMap(self.knots["f"])(q["f"], B.PLA) + q["cM"][0] * (B.M - 0.5) + q["cD"][0] * B.lnd \
            + q["cT"][0] * (B.th - 1.0)
        health = self.V["offsets"] == "health"
        wd = base * (1.0 + offF) if health else base + offF
        wc = np.maximum(_rate_lag(wd, B.start, alpha(np.exp(q["ltau_f"][0])), np.exp(q["lRup"][0]) * DT,
                                  np.exp(q["lRdn"][0]) * DT), 0.0)
        ff_true = wc * B.delta * B.sqth
        if self.V["sensor"]:
            a = alpha(np.exp(q["ltau_FFs"][0]))
            ff_meas = _asym_lag(ff_true, B.start, a, a)
        else:
            ff_meas = ff_true
        gmap = MonoMap(self.knots["g"])
        if health:
            n2ss = gmap(q["g"], wc / (1.0 + offF))
        else:
            n2ss = gmap(q["g"], wc) + offN2
        n2c = _asym_lag(n2ss, B.start, alpha(np.exp(q["ltau_2u"][0])), alpha(np.exp(q["ltau_2d"][0])))
        n2_meas = n2c * B.sqth + (offN2 if health else 0.0)
        return wc, ff_meas, n2c, n2_meas

    def _ref_sim_n1(self, B, p, n2c, u=None):
        q = self.unpack("N1", p)
        off = u["offN1"] if u is not None else self.expand(q["offN1"])[B.eng]
        a = alpha(np.exp(q["ltau_1"][0]))
        return _asym_lag(MonoMap(self.knots["h"])(q["h"], n2c) + off, B.start, a, a)

    def _ref_sim_egt(self, B, p, wc, n1c, u=None):
        """Returns measured EGT (degC)."""
        q = self.unpack("EGT", p)
        off = u["offE"] if u is not None else self.expand(q["offE"])[B.eng]
        kn = MonoMap(self.knots["kN"])(np.r_[0.0, q["kN"]], n1c)
        core = MonoMap(self.knots["kW"])(q["kW"], wc) + kn
        health = self.V["offsets"] == "health"
        tss = B.th ** q["a"][0] * (core if health else core + off)
        a = alpha(np.exp(q["ltau_T"][0]))
        tg = _asym_lag(tss, B.start, a, a)
        if self.V["sensor"]:
            wrel = np.maximum(B.delta / B.sqth * (np.maximum(n1c, 1.0) / 90.0), 0.05)
            tau = np.exp(q["ltau_TC"][0]) * wrel ** W_EXP
            tg = _var_lag(tg, B.start, 1.0 - np.exp(-DT / tau))
        return tg - R.T0K + (off if health else 0.0)

    # ---- fused numba kernels (identical to the _ref_ numpy implementations; checked in t01_selftest.py)
    def _maparrs(self, name, pv):
        m = MonoMap(self.knots[name])
        v = m.values(pv)
        d = pchip_slopes(m.x, v) if not np.all(np.diff(v) == 0) else np.zeros_like(v)
        return m.x, v, d

    def _off4(self, stage, nm, p, u):
        if u is not None:
            return np.asarray(u[nm + "_4"], float)
        return self.expand(self.unpack(stage, p)[nm])

    @staticmethod
    def _keep(B, keep):
        if keep is None:
            if getattr(B, "_allkeep", None) is None or B._allkeep.size != B.n:
                B._allkeep = np.ones(B.n, bool)
            return B._allkeep
        return keep

    def sim_ffn2(self, B, p, u=None, keep=None):
        q = self.unpack("FFN2", p)
        fx, fv, fd = self._maparrs("f", q["f"])
        gx, gv, gd = self._maparrs("g", q["g"])
        a_s = alpha(np.exp(q["ltau_FFs"][0])) if self.V["sensor"] else 0.0
        return _k_ffn2(B.PLA, B.M, B.lnd, B.th, B.sqth, B.delta, B.eng, B.start, fx, fv, fd, gx, gv, gd,
                       float(q["cM"][0]), float(q["cD"][0]), float(q["cT"][0]), alpha(np.exp(q["ltau_f"][0])),
                       float(np.exp(q["lRup"][0]) * DT), float(np.exp(q["lRdn"][0]) * DT),
                       self._off4("FFN2", "offF", p, u), self._off4("FFN2", "offN2", p, u),
                       self.V["offsets"] == "health", self.V["sensor"], a_s,
                       alpha(np.exp(q["ltau_2u"][0])), alpha(np.exp(q["ltau_2d"][0])), self._keep(B, keep))

    def sim_n1(self, B, p, n2c, u=None, keep=None):
        q = self.unpack("N1", p)
        hx, hv, hd = self._maparrs("h", q["h"])
        return _k_n1(n2c, B.eng, B.start, hx, hv, hd, self._off4("N1", "offN1", p, u), alpha(np.exp(q["ltau_1"][0])),
                     self._keep(B, keep))

    def sim_egt(self, B, p, wc, n1c, u=None, keep=None):
        q = self.unpack("EGT", p)
        wx, wv, wd = self._maparrs("kW", q["kW"])
        m = MonoMap(self.knots["kN"])
        nv = m.values(np.r_[0.0, q["kN"]])
        nd = pchip_slopes(m.x, nv) if not np.all(np.diff(nv) == 0) else np.zeros_like(nv)
        tau_ref = float(np.exp(q["ltau_TC"][0])) if self.V["sensor"] else 1.0
        return _k_egt(wc, n1c, B.th, B.sqth, B.delta, B.eng, B.start, wx, wv, wd, m.x, nv, nd, float(q["a"][0]),
                      self._off4("EGT", "offE", p, u), self.V["offsets"] == "health", self.V["sensor"],
                      alpha(np.exp(q["ltau_T"][0])), tau_ref, W_EXP, DT, R.T0K, self._keep(B, keep))

    def simulate(self, B, override=None):
        u = {k + "_4": np.asarray(v, float) for k, v in override.items()} if override is not None else None
        wc, ff, n2c, n2 = self.sim_ffn2(B, self.p["FFN2"], u)
        n1c = self.sim_n1(B, self.p["N1"], n2c, u)
        egt = self.sim_egt(B, self.p["EGT"], wc, n1c, u)
        return {"FF": ff, "N2": n2, "N1": n1c * B.sqth, "EGT": egt, "Wc": wc, "N2c": n2c, "N1c": n1c}

    # ---------------------------------------------------------------- fitting
    def _warm(self, init, stage, p0):
        """Warm start: maps of the init model evaluated at THIS model's knots (values -> first value + non-negative
        increments, capped), every other named parameter copied when present in the init model's layout; unit
        parameters copied only when the variants match. Returns p0 unchanged where nothing can be copied."""
        if init is None or stage not in init.p:
            return p0
        q0 = self.unpack(stage, p0)
        qi = init.unpack(stage, init.p[stage])
        out = []
        for name, L in self.layout(stage):
            v = q0[name]
            if name in ("f", "g", "h", "kW") and name in init.knots:
                y = MonoMap(init.knots[name])(qi[name], self.knots[name])
                y = np.maximum.accumulate(y)
                inc = np.minimum(np.diff(y), self.INC_MAX[name] * 0.999)
                v = np.r_[y[0], np.maximum(inc, 1e-9)]
            elif name == "kN" and "kN" in init.knots:
                y = MonoMap(init.knots["kN"])(np.r_[0.0, qi["kN"]], self.knots["kN"])
                y = np.maximum.accumulate(y - y[0])
                v = np.maximum(np.minimum(np.diff(y), self.INC_MAX["kN"] * 0.999), 1e-9)
                # the constant k_N(x_1) moves into k_W's first value (additive split of k is arbitrary)
            elif name.startswith("off"):
                if init.variant == self.variant and name in qi:
                    v = qi[name]
            elif name in qi and qi[name].size == L:
                v = qi[name]
            out.append(np.asarray(v, float))
        p = np.concatenate(out)
        if stage == "EGT" and "kN" in init.knots:
            yN = MonoMap(init.knots["kN"])(np.r_[0.0, qi["kN"]], self.knots["kN"][:1])[0]
            p[0] += yN
        return p

    def fit(self, B, stride=4, max_nfev=100, log=print, init=None):
        cm = B.corrected_measured()
        sel = np.flatnonzero(B.w > 0)[::stride]
        t0 = time.time()
        health = self.V["offsets"] == "health"
        self.knots["f"] = knot_rule(B.PLA[sel], self.K, "mix")
        self.knots["g"] = knot_rule(cm["Wc"][sel], self.K, "log")
        pf = MonoMap.init_from(self.knots["f"], B.PLA[sel], cm["Wc"][sel])
        pg = MonoMap.init_from(self.knots["g"], cm["Wc"][sel], cm["N2c"][sel])
        p0 = np.r_[pf, 0.0, 0.0, 0.0, np.log(0.5), np.log(5000.0), np.log(5000.0), np.zeros(3),
                   pg, np.log(1.0), np.log(2.0), np.zeros(3)]
        if self.V["sensor"]:
            p0 = np.r_[p0, np.log(0.5)]
        p0 = self._warm(init, "FFN2", p0)

        keep = np.zeros(B.n, bool)
        keep[sel] = True
        yff, yn2, sq = B.Y["FF"][sel], B.Y["N2"][sel], B.sqth[sel]

        def fun_ffn2(p):
            _, ff, _, n2 = self.sim_ffn2(B, p, keep=keep)
            return np.r_[(ff - yff) / SCALE["FF"], (n2 - yn2) / SCALE["N2"]]
        self.p["FFN2"] = self._ls("FFN2", p0, fun_ffn2, max_nfev, log, ("FF", "N2"))
        log(f"  M-A[{self.variant}] stage FFN2 done {time.time() - t0:.0f}s")
        wc, _, n2c, _ = self.sim_ffn2(B, self.p["FFN2"])
        self.knots["h"] = knot_rule(cm["N2c"][sel], self.K, "mix")
        p0 = np.r_[MonoMap.init_from(self.knots["h"], cm["N2c"][sel], cm["N1c"][sel]), np.log(1.0), np.zeros(3)]
        p0 = self._warm(init, "N1", p0)
        yn1 = B.Y["N1"][sel]
        self.p["N1"] = self._ls("N1", p0, lambda p: (self.sim_n1(B, p, n2c, keep=keep) * sq - yn1) / SCALE["N1"],
                                max_nfev, log, ("N1",))
        log(f"  M-A[{self.variant}] stage N1 done {time.time() - t0:.0f}s")
        n1c = self.sim_n1(B, self.p["N1"], n2c)
        self.knots["kW"] = knot_rule(cm["Wc"][sel], self.K, "log")
        self.knots["kN"] = knot_rule(cm["N1c"][sel], self.K, "mix")
        pk = MonoMap.init_from(self.knots["kW"], cm["Wc"][sel], cm["Tc"][sel])
        p0 = np.r_[pk, np.full(self.K - 1, 0.5), 0.6, np.log(1.0), np.zeros(3)]
        if self.V["sensor"]:
            p0 = np.r_[p0, np.log(1.0)]
        p0 = self._warm(init, "EGT", p0)
        yegt = B.Y["EGT"][sel]
        self.p["EGT"] = self._ls("EGT", p0, lambda p: (self.sim_egt(B, p, wc, n1c, keep=keep) - yegt) / SCALE["EGT"],
                                 max_nfev, log, ("EGT",))
        log(f"  M-A[{self.variant}] stage EGT done {time.time() - t0:.0f}s")
        return self

    def _ls(self, stage, p0, fun, max_nfev, log, outs):
        lo, hi = self.bounds(stage)
        lo_in = np.where(np.isfinite(lo), lo + 1e-6 * (1 + np.abs(np.where(np.isfinite(lo), lo, 0))), -np.inf)
        hi_in = np.where(np.isfinite(hi), hi - 1e-6 * (1 + np.abs(np.where(np.isfinite(hi), hi, 0))), np.inf)
        p0 = np.minimum(np.maximum(p0, lo_in), hi_in)
        t0 = time.time()
        cost0 = 0.5 * float(np.sum(fun(p0) ** 2))
        r = least_squares(fun, p0, bounds=(lo, hi), method="trf", x_scale="jac", max_nfev=max_nfev,
                          jac=_threaded_jac(fun, lo, hi), tr_solver="lsmr", ftol=FTOL, xtol=1e-8, gtol=1e-8)
        res, J = r.fun, r.jac
        m, k = J.shape
        s2 = float(res @ res / max(m - k, 1))
        rr = res - res.mean()
        rho = float(np.dot(rr[:-1], rr[1:]) / max(np.dot(rr, rr), 1e-300))
        infl = (1 + rho) / max(1 - rho, 1e-3)
        try:
            se = np.sqrt(np.maximum(np.diag(np.linalg.pinv(J.T @ J) * s2 * infl), 0))
        except np.linalg.LinAlgError:
            se = np.full(k, np.nan)
        nper = m // len(outs)
        per = {o: {"rms": float(np.sqrt(np.mean(res[i * nper:(i + 1) * nper] ** 2)) * SCALE[o]),
                   "bias": float(np.mean(res[i * nper:(i + 1) * nper]) * SCALE[o])} for i, o in enumerate(outs)}
        self.info[stage] = {"cost": float(r.cost), "cost_initial": cost0, "seconds": time.time() - t0,
                            "converged": bool(r.status > 0), "ftol": FTOL, "njev": int(r.njev),
                            "per_output": per, "nfev": int(r.nfev), "status": int(r.status),
                            "m": int(m), "lag1_rho": rho, "ar_inflation": infl, "se_naive_ar_inflated": se.tolist(),
                            "at_bound": [nm for (nm, _), x, l, h in zip(self._flat_names(stage), r.x, lo, hi)
                                         if (np.isfinite(l) and x <= l + 1e-6 * (1 + abs(l))) or
                                         (np.isfinite(h) and x >= h - 1e-6 * (1 + abs(h)))]}
        log(f"    {stage}: " + ", ".join(f"{o} rms {v['rms']:.4g} bias {v['bias']:.3g}" for o, v in per.items())
            + f" (nfev {r.nfev}, njev {r.njev}, status {r.status} {'converged' if r.status > 0 else 'NOT CONVERGED'}, "
              f"cost {cost0:.4g} -> {r.cost:.4g}, {time.time() - t0:.0f}s)")
        return r.x

    def _flat_names(self, stage):
        out = []
        for name, L in self.layout(stage):
            out += [(f"{name}[{i}]" if L > 1 else name, i) for i in range(L)]
        return out

    # ---------------------------------------------------------------- unit variation / fleet prior
    UNIT_NAMES = ("offF", "offN2", "offN1", "offE")
    UNIT_STAGE = {"offF": "FFN2", "offN2": "FFN2", "offN1": "N1", "offE": "EGT"}

    def cal_offsets(self):
        return {nm: self.expand(self.unpack(self.UNIT_STAGE[nm], self.p[self.UNIT_STAGE[nm]])[nm]) for nm in self.UNIT_NAMES}

    def prior_sd(self):
        """Fleet prior: SD (ddof 1) over the four CAL-fitted positions of each unit parameter."""
        return {nm: float(np.std(v, ddof=1)) for nm, v in self.cal_offsets().items()}

    def draw_offsets(self, key):
        sd = self.prior_sd()
        out = {}
        for nm in self.UNIT_NAMES:
            z = R.rng_for("fleet_prior_unit", key, nm).normal(0.0, sd[nm], 4)
            out[nm] = z - z.mean()
        return out

    # ---------------------------------------------------------------- serialisation
    def to_json(self):
        return {"K": self.K, "variant": self.variant, "knots": {k: v.tolist() for k, v in self.knots.items()},
                "p": {k: v.tolist() for k, v in self.p.items()}, "layout": {s: self.layout(s) for s in self.STAGES},
                "info": self.info}

    @classmethod
    def from_json(cls, js):
        m = cls(js["K"], js.get("variant", "P"))
        m.knots = {k: np.array(v) for k, v in js["knots"].items()}
        m.p = {k: np.array(v) for k, v in js["p"].items()}
        m.info = js.get("info", {})
        return m

    def readable(self):
        unit_desc = {"output": {"offF": "a_f lb/h (corrected demand)", "offN2": "a_g %N2c", "offN1": "a_h %N1c",
                                "offE": "a_k K (inside theta^a)"},
                     "health": {"offF": "e fuel-efficiency delta (fraction)", "offN2": "b_N2 sensor bias %",
                                "offN1": "m fan/core match %N1c", "offE": "b_EGT sensor bias degC"}}[self.V["offsets"]]
        out = {"variant": self.variant, "unit_parameters": {}}
        for s in self.STAGES:
            q = self.unpack(s, self.p[s])
            se = self.info.get(s, {}).get("se_naive_ar_inflated")
            d = {}
            for name, v in q.items():
                if name.startswith("ltau"):
                    d[name[1:] + "_s"] = float(np.exp(v[0]))
                elif name.startswith("lR"):
                    d[name[1:] + "_lbh_per_s"] = float(np.exp(v[0]))
                elif name in ("f", "g", "h", "kW"):
                    d[name + "_knots_x"] = self.knots[name].tolist()
                    d[name + "_knots_y"] = MonoMap(self.knots[name]).values(v).tolist()
                elif name == "kN":
                    d["kN_knots_x"] = self.knots["kN"].tolist()
                    d["kN_knots_y"] = MonoMap(self.knots["kN"]).values(np.r_[0.0, v]).tolist()
                elif name.startswith("off"):
                    out["unit_parameters"][name] = {"meaning": unit_desc[name], "pos1to4": self.expand(v).tolist()}
                else:
                    d[name] = float(v[0])
            d["se_naive_ar_inflated_flat"] = dict(zip([n for n, _ in self._flat_names(s)], se)) if se else None
            d["at_bound"] = self.info.get(s, {}).get("at_bound")
            d["fit"] = self.info.get(s, {}).get("per_output")
            out[s] = d
        out["fleet_prior_sd"] = self.prior_sd()
        return out


def save(model, path):
    with open(path, "w") as fh:
        json.dump(model.to_json(), fh, indent=1)


def load(path):
    with open(path) as fh:
        return MA.from_json(json.load(fh))
