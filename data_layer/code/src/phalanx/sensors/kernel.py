"""M12 compiled kernel: sensor physics H_sensor, sensor dynamics D_sensor, installation bias, sensor faults.

Architecture §7 (normative chain, stages ``s_phys``, ``s_dyn``, ``s_inst``), AD-22 (Numba layout), AD-23
(sensor dynamics stage). One ``@njit`` function advances L truth frames of every configured sensor at once:

- **Elements** are the physical sensing elements that carry dynamics: a vane, one thermocouple probe, a
  pressure transducer and its pneumatic line, a flowmeter rotor, an RTD. Several channels may read one element
  (a vane read by four LVDT pick-offs), and one channel may average several (a T5 harness of four probes).
- **Channels** are dictionary measurement channels (``s_inst`` in SI). They add the installation bias from
  ``health.sensor_bias`` (AD-07, AD-26), an optional meter update hold, and the sensor-fault modes injected by
  M11 events (W1_interfaces §2 M11). A discrete channel (``IC_DISC``) ends in its LRU's input comparator: the
  output is 1 when the (biased, faulted) detector signal is at or above ``PC_TRIP``, else 0 (W2.2: the UV
  flame detector ENG.AB_LIT, source ``discrete`` on ``eng.ab_state``).

Numerics (all complex-step safe, AD-22/AD-34): first-order lags use the exact first-order-hold solution
``y1 = q1 + (y0 - q0) a + (q0 - q1)(tau/h)(1 - a)`` with ``a = exp(-h/tau)``; second-order elements use the
trapezoidal rule (A-stable) on ``n_sub`` sub-steps with the source linearly interpolated inside the frame.
Branches compare ``.real`` only; truth inputs are real, so physics tables are evaluated on real numbers and
the derivative-carrying quantities (states, dynamic parameters) only meet ``+ - * / exp log``.

The NumPy reference is the same source uncompiled (``m12_kernel.py_func``), as in ``core/example_kernel.py``.
"""

from __future__ import annotations

import numpy as np
from numba import njit

# ---- element source codes (H_sensor) -----------------------------------------------------------------------
SRC_LINEAR, SRC_TAT, SRC_PSTATIC, SRC_PTOTAL, SRC_VANE, SRC_AXIS3, SRC_FUEL, SRC_DISCRETE = (
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
)
SRC_NAMES = ("linear", "tat", "pstatic", "ptotal", "vane", "axis3", "fuel_gauge", "discrete")
# ---- element dynamics codes (D_sensor) ---------------------------------------------------------------------
DYN_NONE, DYN_LAG1, DYN_LAG1_FLUX, DYN_LAG1_PNEU, DYN_LAG2_EAS, DYN_LAG2 = 0, 1, 2, 3, 4, 5
DYN_NAMES = ("none", "lag1", "lag1_flux", "lag1_pneu", "lag2_eas", "lag2")
# flux variable of DYN_LAG1_FLUX: a mass-flow column, or the local mass flux rho * TAS
WK_COLUMN, WK_RHO_TAS = 0, 1

# ---- element int config columns ----------------------------------------------------------------------------
IE_SRC, IE_DYN, IE_C0, IE_CW, IE_WKIND, IE_TAB0, IE_TAB1, IE_HEAT = 0, 1, 2, 3, 4, 5, 6, 7
N_IE = 8  # IE_HEAT: truth column of the heater state (W2.2: util.probe_heat), -1 = the PE_HEATER constant
# ---- element float params ----------------------------------------------------------------------------------
(
    PE_GAIN,
    PE_OFFSET,
    PE_PATTERN,
    PE_TAU,
    PE_WREF,
    PE_NEXP,
    PE_WMINF,
    PE_KF,
    PE_ZETA,
    PE_WN,
    PE_KU,
    PE_KBEND,
    PE_AX,
    PE_AY,
    PE_AZ,
    PE_HEATER,
    PE_CAP,
    PE_ATT,
    PE_UNWET,
    PE_DEAD,
    PE_EASMIN,
    PE_LEVEL,
) = range(22)
N_PE = 22
# ---- element float state -----------------------------------------------------------------------------------
EF_Y, EF_YD, EF_QPREV, EF_SLOW, EF_SHORTV = range(5)
N_EF = 5
EI_MODE, EI_PRIMED = 0, 1  # element (probe) fault mode; primed flag (steady start done)
N_EI = 2
EMODE_OK, EMODE_OPEN, EMODE_SHORT = 0, 1, 2

# ---- channel int config columns ----------------------------------------------------------------------------
IC_EL0, IC_NEL, IC_HOLD_NS, IC_DISC = 0, 1, 2, 3
N_IC = 4
# ---- channel float params ----------------------------------------------------------------------------------
PC_GAIN, PC_OPEN, PC_TRIP = 0, 1, 2
N_PC = 3
# ---- channel float state -----------------------------------------------------------------------------------
CF_HOLD, CF_FVAL, CF_FRATE, CF_FT0, CF_STUCK, CF_DUTY, CF_LAST = range(7)
N_CF = 7
CI_MODE, CI_ISTATE, CI_HOLDIDX = 0, 1, 2
N_CI = 3
# channel fault modes (W1_interfaces §2 M11 sensor-fault modes)
(
    FM_NONE,
    FM_BIAS,
    FM_DRIFT,
    FM_STUCK,
    FM_OPEN,
    FM_SHORT,
    FM_INTERMITTENT,
    FM_SPIKES,
) = range(8)
FAULT_MODES = ("none", "bias", "drift", "stuck", "open", "short", "intermittent", "spikes")

# ---- global truth columns (index vector ``cols``; -1 when the input layout lacks the signal) -------------
COL_MACH, COL_TS, COL_PS, COL_RHO, COL_TAS, COL_NZ, COL_FX, COL_FY, COL_FZ = range(9)
N_COLS = 9

# ---- physical constants passed as a vector ``k`` -----------------------------------------------------------
K_P_SL, K_T_SL, K_RHO_SL, K_GAMMA, K_SUTH, K_G0 = range(6)
N_K = 6


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def interp_table(x, tx, ty, a, b):
    """Piecewise-linear table lookup on the slice [a, b) of (tx, ty), clamped at the ends. ``x`` is real."""
    if x <= tx[a]:
        return ty[a]
    if x >= tx[b - 1]:
        return ty[b - 1]
    lo = a
    hi = b - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if tx[mid] <= x:
            lo = mid
        else:
            hi = mid
    w = (x - tx[lo]) / (tx[hi] - tx[lo])
    return ty[lo] + w * (ty[hi] - ty[lo])


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def total_pressure(ps, mach, gamma):
    """Pitot total pressure [Pa]: isentropic subsonic; Rayleigh pitot (normal shock) for M >= 1 (real)."""
    g = gamma
    if mach < 1.0:
        return ps * (1.0 + 0.5 * (g - 1.0) * mach * mach) ** (g / (g - 1.0))
    m2 = mach * mach
    gp1 = g + 1.0
    a = (gp1 * gp1 * m2 / (4.0 * g * m2 - 2.0 * (g - 1.0))) ** (g / (g - 1.0))  # explicit square (R8)
    return ps * a * (1.0 - g + 2.0 * g * m2) / (g + 1.0)


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _source(src, ip, pe, row, cols, tx, ty, toff, k, ideal):
    """H_sensor of one element at one truth row (real). ``ideal`` returns the true measurand instead."""
    c0 = ip[IE_C0]
    if src == SRC_LINEAR:
        u = row[c0]
        if ideal:
            return pe[PE_GAIN] * u + pe[PE_OFFSET]
        return pe[PE_GAIN] * u + pe[PE_OFFSET] + pe[PE_PATTERN]
    if src == SRC_AXIS3:
        return pe[PE_AX] * row[c0] + pe[PE_AY] * row[c0 + 1] + pe[PE_AZ] * row[c0 + 2]
    if src == SRC_TAT:
        ts = row[cols[COL_TS]]
        m = row[cols[COL_MACH]]
        gam = k[K_GAMMA]
        if ideal:
            return ts * (1.0 + 0.5 * (gam - 1.0) * m * m)
        t0 = ip[IE_TAB0]
        r = interp_table(m, tx, ty, toff[t0], toff[t0 + 1])
        tr = ts * (1.0 + 0.5 * (gam - 1.0) * r * m * m)
        heated = pe[PE_HEATER].real > 0.5
        if ip[IE_HEAT] >= 0:  # the heater state from truth (util.probe_heat), not a constant
            heated = row[ip[IE_HEAT]] > 0.5
        if heated:
            z = m * row[cols[COL_RHO]] / k[K_RHO_SL]
            t1 = ip[IE_TAB1]
            tr = tr + interp_table(z, tx, ty, toff[t1], toff[t1 + 1])
        return tr
    if src == SRC_PSTATIC:
        # PROXY (A-W1.6-12): static-source position error as a Mach-only table k(M); no alpha, beta, gear or
        # fluctuating-pressure terms. Exposed by test_sensors_physics::test_position_error_is_mach_only_proxy.
        ps = row[cols[COL_PS]]
        if ideal:
            return ps
        m = row[cols[COL_MACH]]
        qc = total_pressure(ps, m, k[K_GAMMA]) - ps
        t0 = ip[IE_TAB0]
        return ps + interp_table(m, tx, ty, toff[t0], toff[t0 + 1]) * qc
    if src == SRC_PTOTAL:
        return total_pressure(row[cols[COL_PS]], row[cols[COL_MACH]], k[K_GAMMA])
    if src == SRC_VANE:
        a = row[c0]
        if ideal:
            return a
        m = row[cols[COL_MACH]]
        t0 = ip[IE_TAB0]
        out = (1.0 + pe[PE_KU]) * a + interp_table(m, tx, ty, toff[t0], toff[t0 + 1])
        if cols[COL_NZ] >= 0:
            out = out + pe[PE_KBEND] * (row[cols[COL_NZ]] - 1.0)
        return out
    if src == SRC_DISCRETE:
        # a physical on/off stimulus (e.g. afterburner flame radiance): 1 when the truth state code is at or
        # above the class level, else 0 (W2.2, PROXY A-W2.2-15 for the UV flame detector)
        on = 1.0 if row[c0] >= pe[PE_LEVEL].real else 0.0
        return pe[PE_GAIN] * on
    if src == SRC_FUEL:
        # PROXY (A-W1.6-17): capacitance gauging without tank geometry or probe layout; the fuel plane follows
        # the specific force, low tanks unwet under tilt, 2 % dead zone. Exposed by
        # tests/unit/test_sensors_physics.py::test_fuel_gauge_unwets_under_tilt_proxy.
        mass = row[c0]
        if ideal:
            return mass
        fx = row[cols[COL_FX]]
        fy = row[cols[COL_FY]]
        fz = row[cols[COL_FZ]]
        fmag = np.sqrt(fx * fx + fy * fy + fz * fz)
        st = 0.0  # sine of the fuel-plane tilt (specific force vs body -z)
        if fmag > 1e-9:
            st = np.sqrt(fx * fx + fy * fy) / fmag
        cap = pe[PE_CAP]
        fill = mass / cap
        read = mass + pe[PE_ATT] * cap * st
        f_unwet = pe[PE_UNWET] * st
        if fill.real < f_unwet.real:
            read = read * fill / f_unwet
        if fill.real < pe[PE_DEAD].real:
            read = 0.0 * read
        return read
    return 0.0


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _tau(dyn, ip, pe, row, cols, k):
    """Time constant [s] of a first-order element at this truth row (real schedule x possibly complex tau)."""
    if dyn == DYN_LAG1_FLUX:
        if ip[IE_WKIND] == WK_RHO_TAS:
            w = row[cols[COL_RHO]] * row[cols[COL_TAS]]
        else:
            w = row[ip[IE_CW]]
        r = w / pe[PE_WREF].real
        if r < pe[PE_WMINF].real:
            r = pe[PE_WMINF].real
        return pe[PE_TAU] * np.exp(-pe[PE_NEXP] * np.log(r))
    if dyn == DYN_LAG1_PNEU:
        t = row[cols[COL_TS]]
        tsl = k[K_T_SL]
        s = k[K_SUTH]
        mu_ratio = (t / tsl) ** 1.5 * (tsl + s) / (t + s)
        return pe[PE_TAU] * mu_ratio * k[K_P_SL] / row[cols[COL_PS]]
    return pe[PE_TAU]


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def m12_kernel(
    ef, ei, cf, ci, el_i, el_p, ch_i, ch_p, tx, ty, toff, cols, k, U, bias, t_ns, fault_u, dt, n_sub
):
    """Advance L = U.shape[0] truth frames. Pure: returns fresh (ef, ei, cf, ci, S[L, n_ch], X[L, n_ch]).

    Args:
        ef, ei: element float (n_el, N_EF) / int (n_el, N_EI) state; cf, ci: channel float / int state. el_i,
        el_p: element int config (n_el, N_IE) / float params (n_el, N_PE) (complex for complex step). ch_i,
        ch_p: channel int config (n_ch, N_IC) / float params (n_ch, N_PC). tx, ty, toff: concatenated real
        tables and their offsets. cols, k: global truth-column indices and physical constants. U: (L, n_u)
        real truth rows at the END of each frame (t_ns[j]); bias: (L, n_ch) installation bias [SI]. t_ns: (L,)
        int64 frame-end instants; fault_u: (L, n_ch) uniforms for stochastic faults (zeros if unused). dt:
        frame length [s]; n_sub: trapezoid sub-steps of second-order elements.

    ``S`` is the sensor output s_inst (SI), dtype of ``ef``; ``X`` the true measurand (real), for CIR truth.
    The first frame of an un-primed element (EF_QPREV is set from the source when ``ei`` priming flag says so)
    starts in steady state at that frame's truth (steady initial condition, A-W1.6-2).
    """
    ef = ef.copy()
    ei = ei.copy()
    cf = cf.copy()
    ci = ci.copy()
    n_el = ef.shape[0]
    n_ch = cf.shape[0]
    L = U.shape[0]
    S = np.empty((L, n_ch), dtype=ef.dtype)
    X = np.empty((L, n_ch), dtype=U.dtype)
    yval = np.empty(n_el, dtype=ef.dtype)
    for j in range(L):
        row = U[j]
        for e in range(n_el):
            ip = el_i[e]
            pe = el_p[e]
            src = ip[IE_SRC]
            dyn = ip[IE_DYN]
            q = _source(src, ip, pe, row, cols, tx, ty, toff, k, False)
            if ei[e, EI_PRIMED] == 0:  # not primed: steady state at this truth
                ef[e, EF_Y] = q
                ef[e, EF_YD] = 0.0 * ef[e, EF_Y]
                ef[e, EF_QPREV] = q
                ei[e, EI_PRIMED] = 1
            q0 = ef[e, EF_QPREV]
            y = ef[e, EF_Y]
            yd = ef[e, EF_YD]
            slow = ef[e, EF_SLOW]
            if dyn == DYN_NONE:
                y = q + 0.0 * y
            elif dyn == DYN_LAG1 or dyn == DYN_LAG1_FLUX or dyn == DYN_LAG1_PNEU:
                tau = _tau(dyn, ip, pe, row, cols, k) * slow
                a = np.exp(-dt / tau)
                y = q + (y - q0) * a + (q0 - q) * (tau / dt) * (1.0 - a)
            else:  # second order, trapezoid on n_sub sub-steps
                if dyn == DYN_LAG2_EAS:
                    eas = row[cols[COL_TAS]] * np.sqrt(row[cols[COL_RHO]] / k[K_RHO_SL])
                    if eas < pe[PE_EASMIN].real:
                        eas = pe[PE_EASMIN].real
                    wn = 2.0 * np.pi * pe[PE_KF] * eas / slow
                else:
                    wn = pe[PE_WN] / slow
                zeta = pe[PE_ZETA]
                h = dt / n_sub
                c = 0.5 * h * wn * wn
                d = 1.0 + h * zeta * wn
                det = d + 0.5 * h * c
                for s in range(n_sub):
                    ua = q0 + (q - q0) * (s / n_sub)
                    ub = q0 + (q - q0) * ((s + 1) / n_sub)
                    r0 = y + 0.5 * h * yd
                    r1 = -c * y + (1.0 - h * zeta * wn) * yd + c * (ua + ub)
                    y = (d * r0 + 0.5 * h * r1) / det
                    yd = (-c * r0 + r1) / det
            ef[e, EF_Y] = y
            ef[e, EF_YD] = yd
            ef[e, EF_QPREV] = q
            mode = ei[e, EI_MODE]
            if mode == EMODE_SHORT:
                yval[e] = ef[e, EF_SHORTV]
            else:
                yval[e] = y
        tsec = t_ns[j] / 1e9
        for c in range(n_ch):
            e0 = ch_i[c, IC_EL0]
            ne = ch_i[c, IC_NEL]
            gain = ch_p[c, PC_GAIN]
            v = 0.0 * ef[0, EF_Y]
            if ne == 1:
                if ei[e0, EI_MODE] == EMODE_OPEN:
                    v = ch_p[c, PC_OPEN] + 0.0 * v
                else:
                    v = gain * yval[e0]
            else:  # harness: parallel average of the probes that are not open (open probe excluded)
                acc = 0.0 * v
                cnt = 0
                for e in range(e0, e0 + ne):
                    if ei[e, EI_MODE] != EMODE_OPEN:
                        acc = acc + yval[e]
                        cnt += 1
                if cnt == 0:
                    v = ch_p[c, PC_OPEN] + 0.0 * v
                else:
                    v = gain * acc / cnt
            v = v + bias[j, c]
            hold_ns = ch_i[c, IC_HOLD_NS]
            if hold_ns > 0:  # meter update interval: output refreshed when its update counter advances
                idx = t_ns[j] // hold_ns
                if idx != ci[c, CI_HOLDIDX]:
                    ci[c, CI_HOLDIDX] = idx
                    cf[c, CF_HOLD] = v
                v = cf[c, CF_HOLD]
            mode = ci[c, CI_MODE]
            if mode == FM_BIAS:
                v = v + cf[c, CF_FVAL]
            elif mode == FM_DRIFT:
                v = v + cf[c, CF_FRATE] * (tsec - cf[c, CF_FT0])
            elif mode == FM_STUCK:
                v = cf[c, CF_STUCK] + 0.0 * v
            elif mode == FM_OPEN:
                v = ch_p[c, PC_OPEN] + 0.0 * v
            elif mode == FM_SHORT:
                v = cf[c, CF_FVAL] + 0.0 * v
            elif mode == FM_INTERMITTENT:
                # two-state Markov chain: rate = mean state changes per second; duty = long-run open fraction
                # (mean dwell normal 2 (1 - duty)/rate, open 2 duty/rate)
                rate = cf[c, CF_FRATE].real
                duty = cf[c, CF_DUTY].real
                if ci[c, CI_ISTATE] == 0:
                    p = 0.5 * rate * dt / (1.0 - duty)
                else:
                    p = 0.5 * rate * dt / duty
                if fault_u[j, c] < p:
                    ci[c, CI_ISTATE] = 1 - ci[c, CI_ISTATE]
                if ci[c, CI_ISTATE] == 1:
                    v = ch_p[c, PC_OPEN] + 0.0 * v
            elif mode == FM_SPIKES:
                if fault_u[j, c] < cf[c, CF_FRATE].real * dt:
                    v = v + cf[c, CF_FVAL]
            if ch_i[c, IC_DISC] == 1:  # discrete output: the LRU's input comparator on the detector signal
                v = (1.0 if v.real >= ch_p[c, PC_TRIP].real else 0.0) + 0.0 * v
            cf[c, CF_LAST] = v
            S[j, c] = v
            X[j, c] = _source(el_i[e0, IE_SRC], el_i[e0], el_p[e0].real, row, cols, tx, ty, toff, k, True)
    return ef, ei, cf, ci, S, X


def m12_reference(
    ef, ei, cf, ci, el_i, el_p, ch_i, ch_p, tx, ty, toff, cols, k, U, bias, t_ns, fault_u, dt, n_sub
):
    """NumPy reference: the same source, uncompiled (what ``NUMBA_DISABLE_JIT=1`` runs)."""
    return m12_kernel.py_func(
        ef, ei, cf, ci, el_i, el_p, ch_i, ch_p, tx, ty, toff, cols, k, U, bias, t_ns, fault_u, dt, n_sub
    )
