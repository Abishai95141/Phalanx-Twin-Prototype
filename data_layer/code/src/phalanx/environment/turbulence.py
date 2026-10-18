"""Continuous turbulence (von Kármán / Dryden forming filters), 1-cosine gusts and log-profile wind shear.

Evidence (research_notes/.../modelling_methodology.md §1; report §7 row 4):
- MIL-F-8785C / MIL-HDBK-1797 forming filters as implemented by the MathWorks Dryden and von Kármán blocks
  [DIRECT via MathWorks]: band-limited white noise through forming filters; von Kármán filters are rational
  approximations of the irrational spectra; frozen-turbulence assumption.
- Low altitude (< 1000 ft): L_w = h, L_u = L_v = h / (0.177 + 0.000823 h)^1.2, sigma_w = 0.1 W20,
  sigma_u = sigma_v = sigma_w / (0.177 + 0.000823 h)^0.4 (h in ft). Medium/high (> 2000 ft): isotropic,
  one scale length, sigma from the intensity class; linear interpolation in between.
- von Kármán for production runs, Dryden for cheap tests; own RNG stream (report §7).
- 1-cosine discrete gust and the MIL-F-8785C log-profile shear u(h) = W20 ln(h/z0) / ln(20/z0),
  3 ft < h < 1000 ft, z0 = 0.15 ft in Category C phases (take-off, approach, landing), 2.0 ft otherwise.

Conventions: MIL-F-8785C scale lengths (L_v, L_w as in the spec, not MIL-HDBK-1797's 2L), one-sided PSD in
temporal angular frequency w (rad/s) with variance = integral_0^inf Phi(w) dw. The filters H(s) satisfy
|H(jw)|^2 = Phi(w) when driven by white noise of intensity pi (two-sided), i.e. per-sample variance
pi / dt at the 240 Hz truth rate.

Discretisation: each filter is converted every tick by the bilinear (Tustin) transform with the current
airspeed and scale lengths (time-varying coefficients, Direct Form II transposed states). The rational
von Kármán forms deviate from the irrational spectra by a few percent up to L w / V ~ 10 (tested, A2).
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

FT = 0.3048  # m per ft (exact)
MODEL_DRYDEN, MODEL_VON_KARMAN = 0, 1
CLASS_NONE, CLASS_LIGHT, CLASS_MODERATE, CLASS_SEVERE = 0, 1, 2, 3

# Tustin expansion tables: coefficient k of (1 - x)^i (1 + x)^(n - i), x = z^-1, for n = 1, 2, 3
_TUSTIN = np.zeros((4, 4, 4))
_TUSTIN[1, 0, :2] = (1, 1)
_TUSTIN[1, 1, :2] = (1, -1)
_TUSTIN[2, 0, :3] = (1, 2, 1)
_TUSTIN[2, 1, :3] = (1, 0, -1)
_TUSTIN[2, 2, :3] = (1, -2, 1)
_TUSTIN[3, 0, :4] = (1, 3, 3, 1)
_TUSTIN[3, 1, :4] = (1, 1, -1, -1)
_TUSTIN[3, 2, :4] = (1, -1, -1, 1)
_TUSTIN[3, 3, :4] = (1, -3, 3, -1)
TUSTIN_TABLE = _TUSTIN
TUSTIN_TABLE.flags.writeable = False

# DF2T state slots in the turbulence state vector
TS_U, TS_V, TS_W, TS_P, TS_Q, TS_R = 0, 2, 5, 8, 9, 10
N_TURB_STATE = 11


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def scales(h_agl_m, sigma_hi, w20, l_hi_m):
    """MIL-F-8785C intensities and scale lengths (SI) at height h above ground.

    Returns (sigma_u, sigma_v, sigma_w, L_u, L_v, L_w). h is clamped to >= 10 ft.
    """
    h_ft = h_agl_m / FT
    if h_ft < 10.0:
        h_ft = 10.0
    if h_ft <= 1000.0:
        k = 0.177 + 0.000823 * h_ft
        sw = 0.1 * w20
        su = sw / k**0.4
        lw = h_ft * FT
        lu = h_ft / k**1.2 * FT
        return su, su, sw, lu, lu, lw
    if h_ft >= 2000.0:
        return sigma_hi, sigma_hi, sigma_hi, l_hi_m, l_hi_m, l_hi_m
    # linear interpolation between the 1000 ft low-altitude values and the 2000 ft high-altitude values
    a = (h_ft - 1000.0) / 1000.0
    sw0 = 0.1 * w20  # at 1000 ft: k = 1, so sigma_u = sigma_v = sigma_w and L = 1000 ft
    l0 = 1000.0 * FT
    s = sw0 + a * (sigma_hi - sw0)
    ll = l0 + a * (l_hi_m - l0)
    return s, s, s, ll, ll, ll


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def tustin(b, a, n, dt, tab, bd, ad):
    """Bilinear transform of H(s) = sum b_i s^i / sum a_i s^i (order n <= 3) into bd, ad (ad[0] = 1)."""
    kk = 2.0 / dt
    for k in range(4):
        bd[k] = 0.0
        ad[k] = 0.0
    p = 1.0
    for i in range(n + 1):
        for k in range(n + 1):
            bd[k] += b[i] * p * tab[n, i, k]
            ad[k] += a[i] * p * tab[n, i, k]
        p *= kk
    a0 = ad[0]
    for k in range(n + 1):
        bd[k] /= a0
        ad[k] /= a0


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def df2t(x, z, base, n, bd, ad):
    """One Direct Form II transposed step of order n; states z[base : base + n]."""
    y = bd[0] * x + z[base]
    for k in range(n - 1):
        z[base + k] = bd[k + 1] * x - ad[k + 1] * y + z[base + k + 1]
    z[base + n - 1] = bd[n] * x - ad[n] * y
    return y


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def filter_coeffs(model, axis, sigma, length, v, b_span, sigma_w, l_w, b, a):
    """Continuous TF coefficients (ascending powers of s) of one forming filter; returns its order.

    axis 0 u, 1 v, 2 w, 3 p (roll gust; uses sigma_w and L_w), 4 q-from-w, 5 r-from-v.
    """
    for k in range(4):
        b[k] = 0.0
        a[k] = 0.0
    if axis == 3:
        b[0] = sigma_w * math.sqrt(0.8 / v) * (math.pi / (4.0 * b_span)) ** (1.0 / 6.0) / l_w ** (1.0 / 3.0)
        a[0] = 1.0
        a[1] = 4.0 * b_span / (math.pi * v)
        return 1
    if axis == 4:
        b[1] = 1.0 / v
        a[0] = 1.0
        a[1] = 4.0 * b_span / (math.pi * v)
        return 1
    if axis == 5:
        b[1] = -1.0 / v
        a[0] = 1.0
        a[1] = 3.0 * b_span / (math.pi * v)
        return 1
    tl = length / v
    if axis == 0:
        g = sigma * math.sqrt(2.0 * length / (math.pi * v))
        if model == MODEL_DRYDEN:
            b[0] = g
            a[0] = 1.0
            a[1] = tl
            return 1
        b[0] = g
        b[1] = g * 0.25 * tl
        a[0] = 1.0
        a[1] = 1.357 * tl
        a[2] = 0.1987 * tl * tl
        return 2
    g = sigma * math.sqrt(length / (math.pi * v))
    if model == MODEL_DRYDEN:
        b[0] = g
        b[1] = g * math.sqrt(3.0) * tl
        a[0] = 1.0
        a[1] = 2.0 * tl
        a[2] = tl * tl
        return 2
    b[0] = g
    b[1] = g * 2.7478 * tl
    b[2] = g * 0.3398 * tl * tl
    a[0] = 1.0
    a[1] = 2.9958 * tl
    a[2] = 1.9754 * tl * tl
    a[3] = 0.1539 * tl * tl * tl
    return 3


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def turbulence_step(model, z, noise4, h_agl, v, sigma_hi, w20, l_hi, b_span, dt, tab, scratch, out6):
    """Advance the six gust filters one tick; writes (u, v, w, p, q, r) gusts into out6.

    ``noise4``: four standard normals (u, v, w, p driving noises); scaled here to intensity pi.
    ``scratch``: a (4, 4) work array (no per-tick allocation).
    """
    su, sv, sw, lu, lv, lw = scales(h_agl, sigma_hi, w20, l_hi)
    b = scratch[0]
    a = scratch[1]
    bd = scratch[2]
    ad = scratch[3]
    amp = math.sqrt(math.pi / dt)
    n = filter_coeffs(model, 0, su, lu, v, b_span, sw, lw, b, a)
    tustin(b, a, n, dt, tab, bd, ad)
    ug = df2t(amp * noise4[0], z, TS_U, n, bd, ad)
    n = filter_coeffs(model, 1, sv, lv, v, b_span, sw, lw, b, a)
    tustin(b, a, n, dt, tab, bd, ad)
    vg = df2t(amp * noise4[1], z, TS_V, n, bd, ad)
    n = filter_coeffs(model, 2, sw, lw, v, b_span, sw, lw, b, a)
    tustin(b, a, n, dt, tab, bd, ad)
    wg = df2t(amp * noise4[2], z, TS_W, n, bd, ad)
    n = filter_coeffs(model, 3, sw, lw, v, b_span, sw, lw, b, a)
    tustin(b, a, n, dt, tab, bd, ad)
    pg = df2t(amp * noise4[3], z, TS_P, n, bd, ad)
    n = filter_coeffs(model, 4, sw, lw, v, b_span, sw, lw, b, a)
    tustin(b, a, n, dt, tab, bd, ad)
    qg = df2t(wg, z, TS_Q, n, bd, ad)
    n = filter_coeffs(model, 5, sv, lv, v, b_span, sw, lw, b, a)
    tustin(b, a, n, dt, tab, bd, ad)
    rg = df2t(vg, z, TS_R, n, bd, ad)
    out6[0] = ug
    out6[1] = vg
    out6[2] = wg
    out6[3] = pg
    out6[4] = qg
    out6[5] = rg


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def shear_speed(h_agl_m, w20, z0_m):
    """MIL-F-8785C log-profile wind speed at height h (valid 3 ft..1000 ft; clamped outside)."""
    h = h_agl_m
    if h < 3.0 * FT:
        h = 3.0 * FT
    if h > 1000.0 * FT:
        h = 1000.0 * FT
    return w20 * math.log(h / z0_m) / math.log(20.0 * FT / z0_m)


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def gust_1cos(x_m, d_m, vm):
    """Full 1-cosine gust over 2 d: v = vm/2 (1 - cos(pi x / d)) for 0 <= x <= 2 d, else 0.

    (MIL-F-8785C defines the ramp to vm over d; a gust that returns to zero is the ramp up and back down.)
    """
    if x_m < 0.0 or x_m > 2.0 * d_m:
        return 0.0
    return 0.5 * vm * (1.0 - math.cos(math.pi * x_m / d_m))


# ----------------------------------------------------------------------------- analytic spectra (NumPy)


def psd_analytic(model: int, axis: int, sigma: float, length: float, v: float, w: np.ndarray) -> np.ndarray:
    """One-sided PSD Phi(w) (units^2 per rad/s) of the u (0), v (1) or w (2) gust: the irrational
    von Kármán spectrum (model 1) or the Dryden spectrum (model 0), MIL-F-8785C conventions."""
    w = np.asarray(w, dtype=float)
    if model == MODEL_DRYDEN:
        x = length * w / v
        if axis == 0:
            return sigma**2 * 2 * length / (np.pi * v) / (1 + x**2)
        return sigma**2 * length / (np.pi * v) * (1 + 3 * x**2) / (1 + x**2) ** 2
    x = 1.339 * length * w / v
    if axis == 0:
        return sigma**2 * 2 * length / (np.pi * v) / (1 + x**2) ** (5 / 6)
    return sigma**2 * length / (np.pi * v) * (1 + 8 / 3 * x**2) / (1 + x**2) ** (11 / 6)


def psd_filter(
    model: int, axis: int, sigma: float, length: float, v: float, w: np.ndarray, b_span: float = 8.2
) -> np.ndarray:
    """|H(jw)|^2 of the implemented continuous forming filter (axes 0-3)."""
    b = np.zeros(4)
    a = np.zeros(4)
    n = filter_coeffs(model, axis, sigma, length, v, b_span, sigma, length, b, a)
    s = 1j * np.asarray(w, dtype=float)
    num = sum(b[i] * s**i for i in range(n + 1))
    den = sum(a[i] * s**i for i in range(n + 1))
    return np.abs(num / den) ** 2


def psd_filter_discrete(
    model: int, axis: int, sigma: float, length: float, v: float, f_hz: np.ndarray, dt: float, b_span=8.2
) -> np.ndarray:
    """One-sided PSD in units^2/Hz of the Tustin-discretised filter driven as in the kernel
    (per-sample variance pi/dt): P(f) = 2 pi |H_d(e^{j 2 pi f dt})|^2."""
    b = np.zeros(4)
    a = np.zeros(4)
    bd = np.zeros(4)
    ad = np.zeros(4)
    n = filter_coeffs(model, axis, sigma, length, v, b_span, sigma, length, b, a)
    tustin(b, a, n, dt, TUSTIN_TABLE, bd, ad)
    zi = np.exp(-2j * np.pi * np.asarray(f_hz, dtype=float) * dt)
    num = sum(bd[k] * zi**k for k in range(n + 1))
    den = sum(ad[k] * zi**k for k in range(n + 1))
    return 2 * np.pi * np.abs(num / den) ** 2


__all__ = [
    "CLASS_LIGHT",
    "CLASS_MODERATE",
    "CLASS_NONE",
    "CLASS_SEVERE",
    "FT",
    "MODEL_DRYDEN",
    "MODEL_VON_KARMAN",
    "N_TURB_STATE",
    "TUSTIN_TABLE",
    "filter_coeffs",
    "gust_1cos",
    "psd_analytic",
    "psd_filter",
    "psd_filter_discrete",
    "scales",
    "shear_speed",
    "turbulence_step",
    "tustin",
]
