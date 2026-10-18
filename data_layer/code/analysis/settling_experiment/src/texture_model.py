"""Residual-texture model, ablation ladder L0..L6, L6' and the T2 unit-structure construction.

The generator works on one real flight: it takes the truth (low-pass of the cleaned real channel, arm T1)
or the 4-engine common truth plus fleet-prior unit biases (arm T2), adds the texture of the requested
level and returns the new channel-group arrays in the file's original dtype. All parameters come from
results/model_params_<fc>.json, which s04_fit.py estimates on 687-CAL only.

Levels (cumulative; see PREREGISTRATION.md section 3 and README "Model specification"):
  L0  truth + iid Gaussian, sigma per (channel, regime); no lattice.
  L1  + recording lattice y = Q(truth + e), no artificial dither.
  L2  + coloured component: AR(1) per channel; for the 4-engine families the variance is split into a
      family common-mode AR(1) and independent AR(1) parts (component 2 of the notes). The coloured
      components live in the residual band: each AR(1) series is passed through the same zero-phase
      (1 - low-pass) filter that defines the residual, so the texture adds nothing below f_c and
      low-pass(synthetic) stays equal to the truth.
  L3  + regime-dependent variance multipliers: power-setting bins (own-engine N1 truth; CAS for VRTG)
      within each regime, and a log-normal multiplier per regime segment (flight-to-flight intensity).
  L4  + heavy-tail scale mixture of the AR innovations.
  L5  + validity gating (y = 0 below the channel's lowest valid reading), glitch words, episodic freezes.
  L6  + missingness from clock-domain slip (VRTG, analog path): theta_k = frac(phi0 + k Delta),
      sentinel with probability p when |theta| <= width/2. Digital channels unchanged (P4 refuted).
  L6p (= L6') L5 + the old periodic Gilbert-Elliott missingness (bad state every Np samples, duration
      from the CAL burst-duration distribution, p_bad / p_good), independent of any clock model.
"""
import numpy as np
from scipy.signal import lfilter

import config as C
from pipeline import all_runs, lowpass

N1_EDGES = [10.0, 40.0, 60.0, 75.0, 85.0, 92.0]       # power-setting bins (own-engine N1 truth, %)
CAS_EDGES = [30.0, 100.0, 160.0, 220.0, 280.0]          # VRTG intensity bins (kt)
NONNEG = set(C.ENG)                                      # engine channels never read negative values
LEVEL_HAS = {
    "L0": set(), "L1": {"lat"}, "L2": {"lat", "ar"}, "L3": {"lat", "ar", "het"},
    "L4": {"lat", "ar", "het", "tail"}, "L5": {"lat", "ar", "het", "tail", "l5"},
    "L6": {"lat", "ar", "het", "tail", "l5", "slip"}, "L6p": {"lat", "ar", "het", "tail", "l5", "ge"},
}
CAL_LEVEL = {"L0": "L0", "L1": "L1", "L2": "L2", "L3": "L3", "L4": "L4", "L5": "L4", "L6": "L4", "L6p": "L4"}


def family(ch):
    return ch.split("_")[0] if ch != C.VRTG else C.VRTG


def engine(ch):
    return int(ch.split("_")[1]) if ch != C.VRTG else 0


def ar1(z, phi, rng, rate=None, fc=None):
    if phi > 0:
        zi = [phi * rng.standard_normal()]
        z, _ = lfilter([np.sqrt(1 - phi ** 2)], [1.0, -phi], z, zi=zi)
    if fc is not None:
        z = z - lowpass(z, rate, fc)
    return z


def mixture(z, p, k, rng):
    if p <= 0 or k <= 1:
        return z
    B = rng.random(z.size) < p
    return z * np.where(B, k, 1.0) / np.sqrt(1 - p + p * k * k)


def per_sample(lab_s, rate, n):
    idx = np.minimum(np.arange(n) // int(round(rate)), lab_s.size - 1)
    return idx


class Generator:
    def __init__(self, pipe, params):
        self.pipe = pipe
        self.P = params            # one fc key: {"levels": {L: {...}}, "fixed": {...}}

    # ----------------------------------------------------------------- helpers
    def _seg_mult(self, lab, fid, key, seg_sd):
        """Per-second log-normal multiplier, one draw per contiguous regime run."""
        rng = C.rng_for(fid, key, "segmult")
        m = np.ones(lab.size)
        for code, a, b in all_runs(lab):
            s = seg_sd.get(str(code), 0.0)
            m[a:b] = np.exp(s * rng.standard_normal() - 0.5 * s * s)
        return m

    @staticmethod
    def _bins(v, edges):
        return np.searchsorted(edges, v, side="right")

    # ----------------------------------------------------------------- main
    def generate(self, ctx, level, fid, arm="T1", bias=None):
        """ctx: dict with lab (per s), cas (per s), and per channel {'x','xc','truth','rate','dtype','n'}.
        Returns {channel: array in the original dtype}."""
        has = LEVEL_HAS[level]
        lp = self.P["levels"][CAL_LEVEL[level]]
        fx = self.P["fixed"]
        lab, cas = ctx["lab"], ctx["cas"]
        out = {}
        base = {}
        # --- arm T2: common truth + unit bias for running engines
        for ch in C.GROUP:
            base[ch] = ctx[ch]["truth"].copy()
        if arm == "T2":
            for f in C.FAMILIES:
                tr = np.vstack([ctx[f"{f}_{k}"]["truth"] for k in range(1, 5)])
                n2 = np.vstack([ctx[f"N2_{k}"]["truth"] for k in range(1, 5)])
                w = np.clip((n2 - 30.0) / 15.0, 0, 1)                 # running weight (N2 30 -> 45 %)
                ws = w.sum(0)
                common = np.where(ws > 0, (tr * w).sum(0) / np.maximum(ws, 1e-9), tr.mean(0))
                for k in range(1, 5):
                    ch = f"{f}_{k}"
                    b = bias[ch](common) if bias is not None else 0.0
                    base[ch] = w[k - 1] * (common + b) + (1 - w[k - 1]) * tr[k - 1]
        # --- shared per-second quantities
        n1_truth = {k: base[f"N1_{k}"] for k in range(1, 5)}
        cm = {}
        if "ar" in has:
            for f in C.FAMILIES:
                n = ctx[f"{f}_1"]["n"]
                rng = C.rng_for(fid, f, "cm")
                z = rng.standard_normal(n)
                if "tail" in has:
                    p, k = lp["tail_cm"][f]
                    z = mixture(z, p, k, C.rng_for(fid, f, "cm_tail"))
                cm[f] = ar1(z, lp["phi_cm"][f], C.rng_for(fid, f, "cm_init"), 4.0, self.P["fc"]["ENG"])
        segm = {}
        if "het" in has:
            for key in C.FAMILIES + [C.VRTG]:
                segm[key] = self._seg_mult(lab, fid, key, lp["seg_sd"][key])
        for ch in C.GROUP:
            c = ctx[ch]
            n, rate = c["n"], c["rate"]
            idx = per_sample(lab, rate, n)
            reg = lab[idx]
            f = family(ch)
            z = C.rng_for(fid, ch, "z").standard_normal(n)
            s_ind = np.array([lp["sigma"][ch][str(r)] for r in range(7)])[reg]
            if "ar" in has:
                if "tail" in has:
                    p, k = lp["tail"][ch]
                    z = mixture(z, p, k, C.rng_for(fid, ch, "tail"))
                u = ar1(z, lp["phi_ind"][ch], C.rng_for(fid, ch, "ar_init"), rate,
                        self.P["fc"]["VRTG" if ch == C.VRTG else "ENG"])
            else:
                u = z
            if "het" in has:
                if ch == C.VRTG:
                    b = self._bins(cas[idx], CAS_EDGES)
                else:
                    b = self._bins(n1_truth[engine(ch)][:n], N1_EDGES)
                M = np.array(lp["pow_mult"][ch])          # (7 regimes, n bins)
                s_ind = s_ind * M[reg, b] * segm[f][idx]
            e = s_ind * u
            if "ar" in has and ch != C.VRTG:
                s_cm = np.array([lp["cm_scale"][f][str(r)] for r in range(7)])[reg]
                if "het" in has:
                    bm = self._bins(np.mean([n1_truth[k][:n] for k in range(1, 5)], 0), N1_EDGES)
                    Mc = np.array(lp["pow_mult_cm"][f])
                    s_cm = s_cm * Mc[reg, bm] * segm[f][idx]
                e = e + s_cm * cm[f][:n]
            y = base[ch][:n] + e
            if "lat" in has:
                y = self.pipe.quantize(ch, y)
            if "l5" in has:
                y = self._l5(ch, y, base[ch][:n], ctx, fid, reg)
            if "slip" in has and ch == C.VRTG:
                y = self._slip(ch, y, fid, fx)
            if "ge" in has and ch == C.VRTG:
                y = self._ge(ch, y, fid, fx, rate)
            out[ch] = self._cast(ch, y, c["dtype"])
        return out

    # ----------------------------------------------------------------- L5
    def _l5(self, ch, y, truth, ctx, fid, reg):
        fx = self.P["fixed"]
        g = fx["gate"].get(ch)
        if g is not None:
            # Gate-0 fix (DEVIATIONS.md C4): "below the lowest valid reading" means below it by more than
            # half a step; a truth equal to that reading (up to filter round-off) is not gated.
            y = np.where(truth < g - 0.5 * self.pipe.step(ch), 0.0, y)
        if ch in NONNEG:
            y = np.maximum(y, 0.0)
        rate = ctx[ch]["rate"]
        n = y.size
        # glitch words
        gl = fx["glitch"].get(ch)
        if gl and gl["rate_per_h"] > 0:
            rng = C.rng_for(fid, ch, "glitch")
            m = rng.poisson(gl["rate_per_h"] * n / rate / 3600)
            if m:
                y = y.copy()
                y[rng.integers(0, n, m)] = gl["value"]
        # episodic freezes (airborne)
        fr = fx["freeze"].get(ch)
        if fr and fr["rate_per_air_h"] > 0 and fr["durations_s"]:
            air = np.flatnonzero(np.isin(reg, [C.REGIME_CODE[r] for r in ("climb", "cruise", "descent", "approach")]))
            if air.size:
                rng = C.rng_for(fid, ch, "freeze")
                m = rng.poisson(fr["rate_per_air_h"] * air.size / rate / 3600)
                y = y.copy()
                for _ in range(m):
                    a = int(air[rng.integers(0, air.size)])
                    d = int(round(fr["durations_s"][rng.integers(0, len(fr["durations_s"]))] * rate))
                    y[a:a + d] = y[a]
        return y

    # ----------------------------------------------------------------- L6 / L6'
    def _slip(self, ch, y, fid, fx):
        par = fx["slip"][ch]
        rng = C.rng_for(fid, ch, "slip")
        d = float(rng.choice(par["delta_ppm"])) * 1e-6
        phi0 = rng.random()
        k = np.arange(y.size)
        th = (phi0 + k * d) % 1.0
        th = np.minimum(th, 1.0 - th)                       # distance to the update instant (phase units)
        hit = (th <= par["width_phase"] / 2) & (rng.random(y.size) < par["p_in"])
        y = y.copy()
        y[hit] = par["sentinel"]
        return y

    def _ge(self, ch, y, fid, fx, rate):
        par = fx["ge"][ch]
        rng = C.rng_for(fid, ch, "ge")
        n = y.size
        Np = int(par["Np"])
        bad = np.zeros(n, bool)
        start = int(rng.integers(0, Np))
        for s in range(start - Np, n, Np):
            d = int(round(float(rng.choice(par["dur_s"])) * rate))
            a = max(s, 0)
            bad[a:max(min(s + d, n), a)] = True
        u = rng.random(n)
        hit = np.where(bad, u < par["p_bad"], u < par["p_good"])
        y = y.copy()
        y[hit] = par["sentinel"]
        return y

    # ----------------------------------------------------------------- dtype
    @staticmethod
    def _cast(ch, y, dtype):
        dt = np.dtype(dtype)
        if dt.kind in "ui":
            info = np.iinfo(dt)
            return np.clip(np.rint(y), info.min, info.max).astype(dt)
        if dt == np.float32:
            return y.astype(np.float32)
        # real files hold float32-representable values stored as float64
        return y.astype(np.float32).astype(np.float64)
