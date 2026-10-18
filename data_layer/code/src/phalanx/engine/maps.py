"""Scaled component maps for M07: compressor (Nc, PR) -> (Wc, eta, stall PR) and turbine (Np, PR) -> (Wp,
eta).

Evidence: generic NPSS-derived maps from pyCycle (Apache-2.0, commit ``ee7e161``): AXI5 (multistage axial
compressor; pyCycle's mixed-flow example uses it as the fan), HBTF HPC, HBTF HPT and HBTF LPT
[TRANSFER: pyCycle generic maps, scaled to the IN20 design point]. No dimensional F404 map is public
(f404_in20_engine_model.md Q11), so map *shape* is an assumption (A-W1.3a-2); calibration (W2.3) modifies it.

Scaling (pyCycle convention): ``Nc = s_Nc * NcMap``, ``PR - 1 = s_PR (PRmap - 1)``, ``Wc = s_Wc WcMap``,
``eta = s_eta effMap``; the scalars are solved at the design point (``design.py``).

Compressor lookup in a volume-dynamics model: the pressure ratio is known (from the volume pressures) and the
flow is wanted. Along the speed line interpolated at ``Nc`` (piecewise linear in Nc and Rline, so Jacobians
change at grid lines), PR(Rline) is inverted exactly within a cell on the **stable branch** (from the PR
peak towards choke). Beyond the peak the flow falls exponentially with rising PR (statically stable
extension; the surge model of the kernel triggers before that, on the map stall line). Beyond the choke end
the last segment is extrapolated. Below the lowest speed line the fan laws extrapolate (W ~ N,
PR - 1 ~ N^2): **PROXY** for the sub-idle regime (A-W1.3a-3); the same similarity extension is used above
the top speed line (over-speed).

All functions are ``@njit``, scalar, complex-step safe (index searches on ``.real``; interpolation is
analytic).
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numba import njit

_JIT = {"cache": True, "fastmath": False, "error_model": "numpy", "nogil": True}


class CompressorMap(NamedTuple):
    nc: np.ndarray  # (nN,) map corrected speed (fraction of map design)
    rl: np.ndarray  # (nR,) Rline values
    wc: np.ndarray  # (nN, nR) map corrected flow
    pr: np.ndarray  # (nN, nR) map pressure ratio
    eff: np.ndarray  # (nN, nR) map isentropic efficiency


class TurbineMap(NamedTuple):
    np_: np.ndarray  # (nP,) map corrected speed parameter
    pr: np.ndarray  # (nPR,) map pressure ratio
    wp: np.ndarray  # (nP, nPR) map flow parameter
    eff: np.ndarray  # (nP, nPR) map isentropic efficiency


def compressor_map_from_columns(nc, rline, wc, pr, eff) -> CompressorMap:
    nc, rline, wc, pr, eff = (np.asarray(x, float) for x in (nc, rline, wc, pr, eff))
    ax_n = np.unique(nc)
    ax_r = np.unique(rline)
    shape = (ax_n.size, ax_r.size)
    if nc.size != ax_n.size * ax_r.size:
        raise ValueError("compressor map columns are not a full (Nc, Rline) grid")
    order = np.lexsort((rline, nc))
    return CompressorMap(
        ax_n.copy(),
        ax_r.copy(),
        wc[order].reshape(shape).copy(),
        pr[order].reshape(shape).copy(),
        eff[order].reshape(shape).copy(),
    )


def turbine_map_from_columns(npar, pr, wp, eff) -> TurbineMap:
    npar, pr, wp, eff = (np.asarray(x, float) for x in (npar, pr, wp, eff))
    ax_n = np.unique(npar)
    ax_p = np.unique(pr)
    shape = (ax_n.size, ax_p.size)
    if npar.size != ax_n.size * ax_p.size:
        raise ValueError("turbine map columns are not a full (Np, PR) grid")
    order = np.lexsort((pr, npar))
    return TurbineMap(
        ax_n.copy(), ax_p.copy(), wp[order].reshape(shape).copy(), eff[order].reshape(shape).copy()
    )


@njit(**_JIT)
def _bracket(ax, x):
    """Index i with ax[i] <= x.real < ax[i+1], clamped to [0, n-2] (search on the real part only)."""
    n = ax.size
    xr = x.real
    if xr <= ax[0]:
        return 0
    if xr >= ax[n - 2]:
        return n - 2
    lo = 0
    hi = n - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ax[mid] <= xr:
            lo = mid
        else:
            hi = mid
    return lo


@njit(**_JIT)
def compressor_lookup(ncm, prm, m_nc, m_wc, m_pr, m_eff, stall_slope):
    """Operating point on a compressor map.

    ncm: map corrected speed; prm: map pressure ratio (target). Returns (wc_map, eff_map, pr_stall_map,
    beyond)
    where ``beyond`` > 0 measures how far (in map PR) the target lies above the stable-branch peak.
    """
    nr = m_wc.shape[1]
    # speed-line weights: value_j = ws * (a0 v[i0, j] + a1 v[i1, j]); PR_j - 1 = ps * (...)
    if ncm.real < m_nc[0]:
        i0 = 0
        i1 = 0
        a1 = 0.0 * ncm
        s = ncm / m_nc[0]
        ws = s
        ps = s * s
    elif ncm.real > m_nc[m_nc.size - 1]:
        # above the top speed line: fan-law similarity from the top line (no two-line extrapolation)
        i0 = m_nc.size - 1
        i1 = i0
        a1 = 0.0 * ncm
        s = ncm / m_nc[i0]
        ws = s
        ps = s * s
    else:
        i0 = _bracket(m_nc, ncm)
        i1 = i0 + 1
        a1 = (ncm - m_nc[i0]) / (m_nc[i1] - m_nc[i0])
        ws = 1.0 + 0.0 * ncm
        ps = 1.0 + 0.0 * ncm
    a0 = 1.0 - a1
    # pass 1: stable-branch peak index (max PR on the interpolated line)
    jpk = 0
    prpk = 1.0 + ps * (a0 * m_pr[i0, 0] + a1 * m_pr[i1, 0] - 1.0)
    for j in range(1, nr):
        prj = 1.0 + ps * (a0 * m_pr[i0, j] + a1 * m_pr[i1, j] - 1.0)
        if prj.real > prpk.real:
            prpk = prj
            jpk = j
    pr_stall = 1.0 + ps * (a0 * m_pr[i0, 0] + a1 * m_pr[i1, 0] - 1.0)
    wpk = ws * (a0 * m_wc[i0, jpk] + a1 * m_wc[i1, jpk])
    epk = a0 * m_eff[i0, jpk] + a1 * m_eff[i1, jpk]
    if prm.real >= prpk.real:
        # statically stable extension beyond the peak: flow falls with rising PR (surge flagged elsewhere)
        beyond = prm - prpk
        # smooth, positive fall-off (linear slope stall_slope at the peak, never reverses)
        wc = wpk * np.exp(-stall_slope * beyond / (prpk - 1.0))
        return wc, epk, pr_stall, beyond
    beyond = 0.0 * prm
    # pass 2: segment on the stable branch containing prm (PR decreasing with j)
    jseg = nr - 2
    for j in range(jpk, nr - 1):
        prn = 1.0 + ps * (a0 * m_pr[i0, j + 1] + a1 * m_pr[i1, j + 1] - 1.0)
        if prn.real <= prm.real:
            jseg = j
            break
    pra = 1.0 + ps * (a0 * m_pr[i0, jseg] + a1 * m_pr[i1, jseg] - 1.0)
    prb = 1.0 + ps * (a0 * m_pr[i0, jseg + 1] + a1 * m_pr[i1, jseg + 1] - 1.0)
    wa = ws * (a0 * m_wc[i0, jseg] + a1 * m_wc[i1, jseg])
    wb = ws * (a0 * m_wc[i0, jseg + 1] + a1 * m_wc[i1, jseg + 1])
    ea = a0 * m_eff[i0, jseg] + a1 * m_eff[i1, jseg]
    eb = a0 * m_eff[i0, jseg + 1] + a1 * m_eff[i1, jseg + 1]
    den = pra - prb
    if den.real < 1e-9:
        den = den + 1e-9
    t = (pra - prm) / den
    return wa + t * (wb - wa), ea + t * (eb - ea), pr_stall, beyond


@njit(**_JIT)
def turbine_lookup(npm, prm, m_np, m_pr, m_wp, m_eff):
    """Bilinear (Np, PR) lookup, both axes clamped to the table range (flat continuation outside)."""
    x = npm
    if x.real < m_np[0]:
        x = m_np[0] + 0.0 * npm
    elif x.real > m_np[m_np.size - 1]:
        x = m_np[m_np.size - 1] + 0.0 * npm
    y = prm
    if y.real < m_pr[0]:
        y = m_pr[0] + 0.0 * prm
    elif y.real > m_pr[m_pr.size - 1]:
        y = m_pr[m_pr.size - 1] + 0.0 * prm
    i = _bracket(m_np, x)
    j = _bracket(m_pr, y)
    u = (x - m_np[i]) / (m_np[i + 1] - m_np[i])
    v = (y - m_pr[j]) / (m_pr[j + 1] - m_pr[j])
    w00 = (1.0 - u) * (1.0 - v)
    w10 = u * (1.0 - v)
    w01 = (1.0 - u) * v
    w11 = u * v
    wp = w00 * m_wp[i, j] + w10 * m_wp[i + 1, j] + w01 * m_wp[i, j + 1] + w11 * m_wp[i + 1, j + 1]
    ef = w00 * m_eff[i, j] + w10 * m_eff[i + 1, j] + w01 * m_eff[i, j + 1] + w11 * m_eff[i + 1, j + 1]
    return wp, ef


@njit(**_JIT)
def interp1(ax, vals, x):
    """Piecewise-linear interpolation with flat continuation outside the table (complex-step safe)."""
    n = ax.size
    if x.real <= ax[0]:
        return vals[0] + 0.0 * x
    if x.real >= ax[n - 1]:
        return vals[n - 1] + 0.0 * x
    i = _bracket(ax, x)
    t = (x - ax[i]) / (ax[i + 1] - ax[i])
    return vals[i] + t * (vals[i + 1] - vals[i])


@njit(**_JIT)
def flow_function(pr, g):
    """Isentropic mass-flow function psi(PR, gamma) with PR = P_total / P_static_exit >= 1.

    W = A * Pt * psi / sqrt(R Tt). Choked (constant) above the critical pressure ratio; C1-continuous there.
    """
    p = pr
    if p.real < 1.0 + 1e-9:
        p = 1.0 + 1e-9 + 0.0 * pr
    prc = ((g + 1.0) * 0.5) ** (g / (g - 1.0))
    if p.real >= prc.real:
        return np.sqrt(g) * (2.0 / (g + 1.0)) ** ((g + 1.0) / (2.0 * (g - 1.0)))
    x = 1.0 / p
    return np.sqrt(2.0 * g / (g - 1.0) * (x ** (2.0 / g) - x ** ((g + 1.0) / g)))


@njit(**_JIT)
def turbine_unchoke(pr, pr_choke, g):
    """Turbine flow-capacity factor in (0,
    1]: an equivalent nozzle whose critical pressure ratio is mapped onto
    the turbine choking pressure ratio ``pr_choke`` (PR_eff = PR^k). 1 when choked."""
    prc = ((g + 1.0) * 0.5) ** (g / (g - 1.0))
    k = np.log(prc) / np.log(pr_choke)
    p = pr
    if p.real < 1.0 + 1e-9:
        p = 1.0 + 1e-9 + 0.0 * pr
    return flow_function(p**k, g) / flow_function(prc * 2.0, g)
