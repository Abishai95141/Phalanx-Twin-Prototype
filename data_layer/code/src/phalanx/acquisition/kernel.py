"""M13 compiled acquisition kernel: sampling, noise, double quantiser and artefacts (architecture §7).

For one clock domain (an acquiring LRU on its own oscillator) and a block of truth frames, every sample
instant ``t_n`` in ``[t_start[j], t_end[j])`` is processed per channel in this order (normative, §7):

1. **Sample the sensor output** ``s_inst`` (SI, from M12): linear interpolation between the frame values
   (A-W0.2-2), or, for frequency/pulse sensors (``MODE_COUNT``), the exact average of the piecewise-linear
   signal over the acquisition interval ``[t_{n-1}, t_n]`` (period counting by the LRU, A-W1.6-29), or, for
   status / discrete / code words (``MODE_HOLD``, W2.2), the word the producer published last (the value
   at the frame start, held through the frame: a word is never interpolated), in EU.
2. **Deadband / backlash** of the transducer linkage (EU, hysteresis width ``db``).
3. **Idiosyncratic noise** ``n_indep``: unit AR(1) ``e = phi e + sqrt(1 - phi^2) z``, with ``z`` a keyed
   standard normal scaled by ``k_tail`` with probability ``p_tail`` (heavy-tail mixture), times
   ``sigma * m[phase]`` (regime multiplier). Independent per channel; never coupled (AD-04).
4. **Double quantiser** (AD-05): native step ``m = rint((x - o_n)/q_n)``, then the recorder lattice
   ``c = rint((q_n m + o_n)/L)`` (or the native grid alone when the channel has no recorder word);
   **saturation** clamps the final code to the range (``OUT_OF_RANGE`` flag).
5. **Validity gating**: a reading below ``gate`` is replaced by the code of 0 with ``NO_COMPUTED_DATA`` +
   ``GATED`` (the LRU's own validity logic).
6. **Episodic freeze** (transmitter freeze; undetected, so no flag): Poisson start per airborne sample, the
   code held for ``d_min + Exp(d_mean)`` samples.
7. **Glitch word** (all-ones = top of scale; undetected, no flag).
8. **Slip window** (analog paths only, AD-06): a read inside the collision window of the converter's update
   (``coll``) returns the bottom-of-scale sentinel with probability ``p_in`` (``SENTINEL`` flag). No
   independent dropout process exists anywhere.

All randomness arrives as keyed draws indexed by the absolute sample index (``z[n]``, ``u[n, 0..4]``), so the
noise of sample n never depends on block length, on other channels or on which entry point (in-loop or
recording) processes it. The NumPy reference is ``acq_kernel.py_func``.
"""

from __future__ import annotations

import numpy as np
from numba import njit

MODE_POINT, MODE_COUNT, MODE_HOLD = 0, 1, 2
# ---- float params (n_ch, N_AP) -----------------------------------------------------------------------------
(
    AP_SCALE,
    AP_OFF,
    AP_QN,
    AP_ON,
    AP_SF,
    AP_OF,
    AP_SIGMA,
    AP_PHI,
    AP_SQ,
    AP_TAILP,
    AP_TAILK,
    AP_GATE,
    AP_DB,
    AP_FRZP,
    AP_FRZMIN,
    AP_FRZMEAN,
    AP_GLP,
    AP_PIN,
) = range(18)
N_AP = 18
# ---- int params (n_ch, N_AQ) -------------------------------------------------------------------------------
AQ_MODE, AQ_HASREC, AQ_CMIN, AQ_CMAX, AQ_GATE, AQ_SLIP, AQ_C0 = range(7)
N_AQ = 7
# ---- float state (n_ch, N_AF) ------------------------------------------------------------------------------
AF_E, AF_YB, AF_J, AF_XC, AF_PS, AF_PX = range(6)
N_AF = 6
# ---- int state (n_ch, N_AI) --------------------------------------------------------------------------------
AI_PRIMED, AI_FRZLEFT, AI_FRZCODE, AI_LASTCODE, AI_HASLAST, AI_TLAST, AI_TCUR = range(7)
N_AI = 7
# ---- uniform draw slots per sample -------------------------------------------------------------------------
U_TAIL, U_FRZ, U_FRZDUR, U_GLITCH, U_SLIP = range(5)
N_U = 5
# ---- contract encodings (QualityFlags bit positions, Validity symbols) -------------------------------------
FLAG_SENTINEL = 1 << 0
FLAG_GATED = 1 << 1
FLAG_HELD_STALE = 1 << 2
FLAG_OUT_OF_RANGE = 1 << 6
VALIDITY_SYMBOLS = ("NORMAL", "NO_COMPUTED_DATA", "FUNCTIONAL_TEST", "FAILURE_WARNING", "BUS_INVALID")
V_NORMAL, V_NCD = 0, 1
N_PHASE = 16  # dictionary flight_phase codes 0-15 (0.1.2 added synthetic fighter phases 8-15)


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def quantise_code(x, qn, on, sf, of, hasrec, cmin, cmax):
    """Double quantiser + saturation on one EU value: returns (code, saturated). value = code * sf + of."""
    m = np.rint((x - on) / qn)
    xn = qn * m + on
    if hasrec == 1:
        c = np.rint((xn - of) / sf)
    else:
        c = m
    sat = 0
    if c < cmin:
        c = cmin
        sat = 1
    elif c > cmax:
        c = cmax
        sat = 1
    return np.int64(c), sat


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def acq_kernel(f, i, P, Q, regime, airborne, S, X, t_start, t_end, t_s, step, w, phase, z, u, coll):
    """Acquire one domain block. Pure: returns (f, i, code, value_eu, truth_eu, flags, validity).

    Args:
        f, i: per-channel float (n, N_AF) / int (n, N_AI) acquisition state.
        P, Q: per-channel float / int parameters; regime: (n, 8) noise multipliers by phase code;
            airborne: (8,) int, 1 for phase codes in which freezes may start.
        S, X: (L, n) sensor output s_inst and true measurand at the frame ENDS t_end[j] (SI).
        t_start, t_end: (L,) frame bounds [ns]; t_s, step, w: (n_s,) sample instants, frame of each sample,
        and
            interpolation weight (t_s - t_start)/(t_end - t_start) (exactly ``truth_interp_weights``).
        phase: (L,) phase code per frame; z: (n_s, n) keyed normals; u: (n_s, n, N_U) keyed uniforms;
        coll: (n_s, n) int, 1 when the read falls in a converter collision window (analog slip).
    """
    f = f.copy()
    i = i.copy()
    n = f.shape[0]
    L = S.shape[0]
    ns = t_s.shape[0]
    code = np.zeros((ns, n), dtype=np.int64)
    val = np.zeros((ns, n), dtype=np.float64)
    tru = np.zeros((ns, n), dtype=np.float64)
    flg = np.zeros((ns, n), dtype=np.int64)
    vld = np.zeros((ns, n), dtype=np.int64)
    for c in range(n):
        p = P[c]
        q = Q[c]
        scale = p[AP_SCALE]
        off = p[AP_OFF]
        s_ptr = 0
        for j in range(L):
            x1 = S[j, c]
            h1 = X[j, c]
            if i[c, AI_PRIMED] == 0:  # first frame ever seen: steady start (A-W1.6-2)
                f[c, AF_PS] = x1
                f[c, AF_PX] = h1
                f[c, AF_XC] = x1
                i[c, AI_TCUR] = t_start[j]
                i[c, AI_PRIMED] = 1
            x0 = f[c, AF_PS]
            h0 = f[c, AF_PX]
            ph = phase[j]
            if ph < 0 or ph >= N_PHASE:
                ph = 0
            while s_ptr < ns and step[s_ptr] == j:
                k = s_ptr
                s_ptr += 1
                ww = w[k]
                if q[AQ_MODE] == MODE_HOLD:  # a word: the producer's last published value, never interpolated
                    xs = x0
                    hs = h0
                else:
                    xs = x0 + ww * (x1 - x0)
                    hs = h0 + ww * (h1 - h0)
                # 1. sample (point or interval average for counting sensors)
                xm = xs
                if q[AQ_MODE] == MODE_COUNT:
                    dtc = (t_s[k] - i[c, AI_TCUR]) / 1e9
                    jint = f[c, AF_J] + dtc * 0.5 * (f[c, AF_XC] + xs)
                    span = (t_s[k] - i[c, AI_TLAST]) / 1e9
                    if i[c, AI_HASLAST] == 1 and span > 0.0:
                        xm = jint / span
                    f[c, AF_J] = 0.0
                    f[c, AF_XC] = xs
                    i[c, AI_TCUR] = t_s[k]
                x = (xm - off) / scale
                # 2. deadband / backlash
                db = p[AP_DB]
                if db > 0.0:
                    if i[c, AI_HASLAST] == 0:
                        f[c, AF_YB] = x
                    yb = f[c, AF_YB]
                    if x - yb > 0.5 * db:
                        yb = x - 0.5 * db
                    elif x - yb < -0.5 * db:
                        yb = x + 0.5 * db
                    f[c, AF_YB] = yb
                    x = yb
                # 3. idiosyncratic noise (unit AR(1), regime multiplier, heavy-tail mixture)
                sig = p[AP_SIGMA]
                if sig > 0.0:
                    zz = z[k, c]
                    if u[k, c, U_TAIL] < p[AP_TAILP]:
                        zz = zz * p[AP_TAILK]
                    e = p[AP_PHI] * f[c, AF_E] + p[AP_SQ] * zz
                    f[c, AF_E] = e
                    x = x + sig * regime[c, ph] * e
                # 4. double quantiser + saturation
                cd, sat = quantise_code(
                    x, p[AP_QN], p[AP_ON], p[AP_SF], p[AP_OF], q[AQ_HASREC], q[AQ_CMIN], q[AQ_CMAX]
                )
                fl = 0
                vv = V_NORMAL
                if sat == 1:
                    fl = fl | FLAG_OUT_OF_RANGE
                # 5. validity gating (LRU logic, on the measured value)
                if q[AQ_GATE] == 1 and cd * p[AP_SF] + p[AP_OF] < p[AP_GATE]:
                    cd = q[AQ_C0]
                    fl = fl | FLAG_GATED
                    vv = V_NCD
                # 6. episodic freeze (undetected: no flag)
                if i[c, AI_FRZLEFT] > 0:
                    cd = i[c, AI_FRZCODE]
                    i[c, AI_FRZLEFT] -= 1
                elif airborne[ph] == 1 and p[AP_FRZP] > 0.0 and u[k, c, U_FRZ] < p[AP_FRZP]:
                    held = cd
                    if i[c, AI_HASLAST] == 1:
                        held = i[c, AI_LASTCODE]
                    dur = p[AP_FRZMIN] - np.log(1.0 - u[k, c, U_FRZDUR]) * p[AP_FRZMEAN]
                    i[c, AI_FRZLEFT] = np.int64(np.rint(dur)) - 1
                    i[c, AI_FRZCODE] = held
                    cd = held
                i[c, AI_LASTCODE] = cd
                # 7. glitch word (top of scale; undetected)
                if p[AP_GLP] > 0.0 and u[k, c, U_GLITCH] < p[AP_GLP]:
                    cd = q[AQ_CMAX]
                # 8. analog slip-window sentinel (bottom of scale)
                if q[AQ_SLIP] == 1 and coll[k, c] == 1 and u[k, c, U_SLIP] < p[AP_PIN]:
                    cd = q[AQ_CMIN]
                    fl = fl | FLAG_SENTINEL
                code[k, c] = cd
                val[k, c] = cd * p[AP_SF] + p[AP_OF]
                tru[k, c] = (hs - off) / scale
                flg[k, c] = fl
                vld[k, c] = vv
                i[c, AI_HASLAST] = 1
                i[c, AI_TLAST] = t_s[k]
            # close the frame: count integral up to t_end
            if q[AQ_MODE] == MODE_COUNT:
                dtc = (t_end[j] - i[c, AI_TCUR]) / 1e9
                f[c, AF_J] = f[c, AF_J] + dtc * 0.5 * (f[c, AF_XC] + x1)
                f[c, AF_XC] = x1
                i[c, AI_TCUR] = t_end[j]
            f[c, AF_PS] = x1
            f[c, AF_PX] = h1
    return f, i, code, val, tru, flg, vld


def acq_reference(f, i, P, Q, regime, airborne, S, X, t_start, t_end, t_s, step, w, phase, z, u, coll):
    """NumPy reference: the same source, uncompiled."""
    return acq_kernel.py_func(
        f, i, P, Q, regime, airborne, S, X, t_start, t_end, t_s, step, w, phase, z, u, coll
    )
