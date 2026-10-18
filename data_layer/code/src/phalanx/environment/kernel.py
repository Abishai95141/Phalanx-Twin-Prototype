"""M03 environment kernel (AD-22): one ``@njit`` pass per block of 240 Hz ticks.

Per tick k (inputs are the airframe's previous-frame altitude, height above ground and airspeed, a documented
one-frame delay, plus the scenario phase):
1. atmosphere at the aircraft (geometric altitude -> geopotential; profile -> T, p, rho, a, q);
2. mean wind (profile wind, log-profile shear below 1000 ft AGL anchored at the 1000 ft value; z0 by phase);
3. continuous turbulence (time-varying Tustin forming filters) plus active 1-cosine gusts, body axes;
4. AD-32 process-disturbance bank (exact discretisation; unit and aircraft factors).

The NumPy reference is the same source uncompiled (``env_kernel.py_func``); per-step execution is a block of
length 1, so ``step`` == ``step_block`` bitwise by construction.
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

from .atmosphere import PR_WE, PR_WN, _lin, geopotential_altitude, moist_state
from .disturbances import bank_step
from .turbulence import FT, gust_1cos, shear_speed, turbulence_step

# --- parameter vector ---------------------------------------------------------------------------------
P_NAMES = (
    "b_span",
    "z0_cat_c",
    "z0_other",
    "v_min",
    "magnus_a",
    "magnus_b",
    "magnus_c",
)
(P_BSPAN, P_Z0C, P_Z0O, P_VMIN, P_MAG_A, P_MAG_B, P_MAG_C) = range(len(P_NAMES))

# --- float state ---------------------------------------------------------------------------------------
F_NAMES = ("field_elev", "w20_mean", "wind_dir_n", "wind_dir_e", "sigma_hi", "w20_turb", "l_hi")
(F_FIELD, F_W20M, F_WDN, F_WDE, F_SIGHI, F_W20T, F_LHI) = range(len(F_NAMES))
# --- int state -----------------------------------------------------------------------------------------
I_NAMES = ("tick", "n_prof", "turb_model", "profile_wind", "locked")
(I_TICK, I_NPROF, I_MODEL, I_PWIND, I_LOCKED) = range(len(I_NAMES))
# --- gust table columns --------------------------------------------------------------------------------
G_T0, G_AXIS, G_VM, G_D, G_X = 0, 1, 2, 3, 4
N_GUST_COLS = 5
NG = 8
# --- atmosphere output columns ------------------------------------------------------------------------
O_T, O_P, O_RHO, O_A, O_Q = 0, 1, 2, 3, 4


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def env_kernel(
    f,
    i,
    prof,
    turb,
    gusts,
    dist,
    p,
    consts,
    tustin_tab,
    cat_c,
    dims,
    offsets,
    phi,
    lq,
    cvec,
    gain,
    alt,
    hag,
    tas,
    phase,
    t_s,
    turb_noise,
    dist_noise,
    dt,
):
    """Advance len(alt) ticks. Pure: returns fresh (f, i, turb, gusts, dist) and per-tick outputs."""
    f = f.copy()
    i = i.copy()
    turb = turb.copy()
    gusts = gusts.copy()
    dist = dist.copy()
    n = alt.shape[0]
    nout = gain.shape[1]
    atm = np.empty((n, 5))
    wind = np.zeros((n, 3))
    tvel = np.empty((n, 3))
    trate = np.empty((n, 3))
    wout = np.empty((n, nout))
    magnus = np.empty(3)
    magnus[0] = p[P_MAG_A]
    magnus[1] = p[P_MAG_B]
    magnus[2] = p[P_MAG_C]
    scratch = np.empty((4, 4))
    g6 = np.empty(6)
    tmp = np.empty(8)
    o1 = np.empty(nout)
    nprof = i[I_NPROF]
    h1000 = 1000.0 * FT
    for k in range(n):
        z = alt[k]
        t, ps, rho, a, q, wn, we = moist_state(prof, nprof, z, consts, magnus)
        atm[k, O_T] = t
        atm[k, O_P] = ps
        atm[k, O_RHO] = rho
        atm[k, O_A] = a
        atm[k, O_Q] = q
        # --- mean wind with surface-layer shear
        h_agl = hag[k]  # height above the local ground (af.hag; M06 owns the terrain)
        ground = z - h_agl
        catc = False
        for c in range(cat_c.shape[0]):
            if phase[k] == cat_c[c]:
                catc = True
        z0 = p[P_Z0C] if catc else p[P_Z0O]
        if i[I_PWIND] == 1:
            if h_agl < h1000:
                hp = geopotential_altitude(ground + h1000, consts[3])
                wn = _lin(prof, PR_WN, nprof, hp)
                we = _lin(prof, PR_WE, nprof, hp)
                s = shear_speed(h_agl, 1.0, z0) / shear_speed(h1000, 1.0, z0)
                wn *= s
                we *= s
        else:
            w1000 = shear_speed(h1000, f[F_W20M], p[P_Z0O])
            sp = w1000
            if h_agl < h1000:
                sp = w1000 * shear_speed(h_agl, 1.0, z0) / shear_speed(h1000, 1.0, z0)
            wn = sp * f[F_WDN]
            we = sp * f[F_WDE]
        wind[k, 0] = wn
        wind[k, 1] = we
        # --- turbulence (body axes) + discrete gusts
        v = tas[k]
        if v < p[P_VMIN]:
            v = p[P_VMIN]
        turbulence_step(
            i[I_MODEL],
            turb,
            turb_noise[k],
            h_agl,
            v,
            f[F_SIGHI],
            f[F_W20T],
            f[F_LHI],
            p[P_BSPAN],
            dt,
            tustin_tab,
            scratch,
            g6,
        )
        for ax in range(3):
            tvel[k, ax] = g6[ax]
            trate[k, ax] = g6[3 + ax]
        tk = t_s[k]
        for gi in range(gusts.shape[0]):
            if gusts[gi, G_D] > 0.0 and tk >= gusts[gi, G_T0]:
                gusts[gi, G_X] += v * dt
                ax = int(gusts[gi, G_AXIS])
                tvel[k, ax] += gust_1cos(gusts[gi, G_X], gusts[gi, G_D], gusts[gi, G_VM])
        # --- AD-32 process disturbances
        bank_step(dist, dims, offsets, phi, lq, cvec, gain, dist_noise[k], tmp, o1)
        for j in range(nout):
            wout[k, j] = o1[j]
        i[I_TICK] += 1
    return f, i, turb, gusts, dist, atm, wind, tvel, trate, wout


def env_kernel_reference(*args):
    """NumPy reference: the same source uncompiled (identical to ``NUMBA_DISABLE_JIT=1``)."""
    return getattr(env_kernel, "py_func", env_kernel)(*args)


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def wind_unit(from_rad):
    """Unit vector (north, east) of the wind velocity for a wind blowing *from* ``from_rad``."""
    return -math.cos(from_rad), -math.sin(from_rad)
