"""INS/GPS (INGPS) error-state kernel: navigation-grade strapdown INS loosely coupled to GPS (AD-51, P3).

The INS output is the truth plus a **structured error state**, never truth plus independent noise:

- **IMU errors** (body axes): gyro and accelerometer turn-on biases drawn at each power-on (keyed by unit
  serial and sortie), first-order Gauss-Markov in-run biases, white angle-random-walk and accelerometer noise
  (``M12_AVIONICS.yaml`` ``ins``; TRANSFER: navigation-grade RLG/quartz, DRDO RINS).
- **Navigation error dynamics** (psi-angle form, NED; A-W2.2-2):
  ``psi' = -C (b_g + w_g)`` (attitude error), ``dv' = -psi x f_n + C (b_a + w_a) + Schuler`` (the specific
  force couples attitude errors into velocity: manoeuvres excite the errors), ``dp' = dv``; Schuler terms
  ``-g/R dp_N``, ``-g/R dp_E``, ``+2 g/R dp_D``.
- **GPS aiding** as a steady-state loosely coupled filter: the position error is pulled toward a slowly
  varying Gauss-Markov GPS position error (time constant ``aid_pos_tau``) and the velocity error toward a
  small, faster GPS (Doppler) velocity error (``aid_vel_tau``); tilt converges to its unobservable equilibrium
  (accelerometer bias / g) with ``tilt_tau``; heading is corrected only under horizontal specific force
  (rate ``(|f_h|/g)^2 / heading_tau``), so it drifts with the gyro bias in straight flight.
- **Unaided** (no GPS fix): the horizontal channels run free (Schuler-bounded drift, ~1 nm/h class); the
  vertical channel is damped by a critically damped second-order baro-inertial loop (``baro_tau``) on the
  ICAO pressure altitude of the true static pressure, so its error follows the non-standard-atmosphere
  altitude error instead of diverging with the free-inertial ``+2 g/R`` term.
- **Alignment** at power-on from the turn-on biases: level error = accelerometer bias / g, heading error =
  east gyro bias / (Omega cos lat) (gyrocompassing).
- **Outputs**: position, velocity, attitude from the computed attitude ``(I - [psi x]) C``; body rates through
  narrow-band (TRANSFER: F/A-18 TM-110216, 15.9 rad/s) and wide-band 2nd-order filters; accelerations (body
  specific force) through the TM-110216 34.6 rad/s filter (A-W2.2-3).
- **Electrical supply** (AD-51, A-W2.2-1): from ``util.bus_v``; an in-flight power loss latches the
  **frozen** state: outputs and status words hold their pre-loss values, i.e. navigation invalid **without a
  flag** (F-16 EGI AIB). On the ground a power cycle re-aligns (INS_MODE ALIGN) and draws fresh turn-on
  errors.

Draws (identity-keyed, AD-37): per tick ``N_TICK_DRAWS`` standard normals (index = tick), per power-on
``N_ON_DRAWS`` standard normals (index = power-on count). Euler integration of the error states at the truth
step is adequate: every error time constant is >= seconds (Schuler 84 min).
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

from .common import NJ, P_LOST, P_RESTORED, body_to_nav, euler_with_error, gm_coeffs, lag2_step, power_step

# ---- parameter vector -----------------------------------------------------------------------------------
(
    P_BG_SIG,
    P_BG_GM_SIG,
    P_BG_GM_TAU,
    P_ARW,
    P_BA_SIG,
    P_BA_GM_SIG,
    P_BA_GM_TAU,
    P_ACC_NOISE,
    P_GPS_SIG_H,
    P_GPS_SIG_V,
    P_GPS_TAU,
    P_GPS_VSIG,
    P_GPS_VTAU,
    P_AID_POS_TAU,
    P_AID_VEL_TAU,
    P_BARO_TAU,
    P_TILT_TAU,
    P_HDG_TAU,
    P_T_ALIGN,
    P_T_REACQ,
    P_CEP_RATE,
    P_NB_WN,
    P_NB_ZETA,
    P_WB_WN,
    P_WB_ZETA,
    P_ACC_WN,
    P_ACC_ZETA,
    P_G0,
    P_R_EARTH,
    P_OMEGA,
    P_V_DROP,
    P_HOLD,
) = range(32)
N_P = 32
N_FOM = 8  # FOM bounds (codes 1..8; 9 above the last)

# ---- float state -----------------------------------------------------------------------------------------
F_PSI, F_DV, F_DP, F_BG0, F_BGM, F_BA0, F_BAM, F_EGPS, F_EVGPS = 0, 3, 6, 9, 12, 15, 18, 21, 24
F_NB = 27  # (y, yd) x 3
F_WB = 33
F_ACC = 39
F_UNB = 45  # previous filter inputs (3 each): nb, wb, acc
F_UWB = 48
F_UACC = 51
F_HOLD = 54  # held numeric outputs (N_OUT)
N_OUT = 18
F_TUNAIDED = F_HOLD + N_OUT  # seconds since the last aided epoch
N_F = F_TUNAIDED + 1
# ---- int state -------------------------------------------------------------------------------------------
I_TICK, I_POWERED, I_LOW_NS, I_NPOWER, I_FROZEN, I_MODE, I_FIX, I_PRIMED = 0, 1, 2, 3, 4, 5, 6, 7
I_ALIGN_LEFT, I_REACQ_LEFT, I_FOM, I_HMODE, I_HFIX, I_HFOM = 8, 9, 10, 11, 12, 13
N_I = 14

# numeric output columns (SI): lat, lon (rad), alt (m), vn, ve, vd (m/s), hdg, pitch, roll (rad),
# ax, ay, az (m/s^2), p_nb, q_nb, r_nb, p_wb, q_wb, r_wb (rad/s)
OUT_NAMES = (
    "lat",
    "lon",
    "alt",
    "vn",
    "ve",
    "vd",
    "hdg",
    "pitch",
    "roll",
    "ax",
    "ay",
    "az",
    "p_nb",
    "q_nb",
    "r_nb",
    "p_wb",
    "q_wb",
    "r_wb",
)
# ins_mode codes (dictionary code table ins_mode, synthetic) and gps_fix codes
MODE_OFF, MODE_ALIGN, MODE_HYBRID, MODE_INERTIAL = 0, 1, 2, 3
FIX_NONE, FIX_3D = 0, 2
# draws
#: ARW xyz, accel white xyz, gyro GM drive xyz, accel GM drive xyz, GPS position GM drive NED, GPS velocity
#: GM drive NED
N_TICK_DRAWS = 18
N_ON_DRAWS = 9  # gyro turn-on xyz, accel turn-on xyz, GPS initial error NED


@njit(**NJ)
def _power_on(f, p, zon, row):
    """Draw the turn-on IMU errors of power-on ``row`` (row of ``zon``) and reset the velocity error; the
    position error starts at the GPS error (the INS is initialised from GPS)."""
    if row >= zon.shape[0]:
        raise ValueError("INS power-on draws exhausted (more power cycles in the block than supplied)")
    for a in range(3):
        f[F_BG0 + a] = p[P_BG_SIG] * zon[row, a]
        f[F_BA0 + a] = p[P_BA_SIG] * zon[row, 3 + a]
        f[F_BGM + a] = 0.0
        f[F_BAM + a] = 0.0
        f[F_DV + a] = 0.0
    f[F_EGPS + 0] = p[P_GPS_SIG_H] * zon[row, 6]
    f[F_EGPS + 1] = p[P_GPS_SIG_H] * zon[row, 7]
    f[F_EGPS + 2] = p[P_GPS_SIG_V] * zon[row, 8]
    for a in range(3):
        f[F_DP + a] = f[F_EGPS + a]
        f[F_EVGPS + a] = 0.0
    f[F_TUNAIDED] = 0.0


@njit(**NJ)
def _align_attitude(f, p, c, lat):
    """Alignment attitude errors from the current turn-on biases in the NED frame at the aligned attitude."""
    dan = np.empty(3)
    dwn = np.empty(3)
    body_to_nav(c, f[F_BA0], f[F_BA0 + 1], f[F_BA0 + 2], dan)
    body_to_nav(c, f[F_BG0], f[F_BG0 + 1], f[F_BG0 + 2], dwn)
    g = p[P_G0]
    f[F_PSI + 0] = dan[1] / g  # level: f_hat_E = 0
    f[F_PSI + 1] = -dan[0] / g  # level: f_hat_N = 0
    clat = math.cos(lat)
    if clat < 0.05:
        clat = 0.05  # gyrocompassing degrades near the poles (not a Tejas case)
    f[F_PSI + 2] = dwn[1] / (p[P_OMEGA] * clat)


@njit(**NJ)
def ins_kernel(f, i, p, fom_bounds, truth, vbus, airborne, ztick, zon, dt, n_sub):
    """Advance L = truth.shape[0] truth frames of the INS/GPS. Pure: returns (f, i, out[L, 18], status[L, 4],
    tru[L, 18]).

    Args:
        truth: (L, 17) frame-end truth [lat, lon, alt, vn, ve, vd, qw, qx, qy, qz, p, q, r, fx, fy, fz,
        h_baro] (SI; h_baro = ICAO pressure altitude of the true static pressure: the baro-inertial
        reference).
        vbus: (L,) supply voltage; airborne: (L,) int (no weight on wheels).
        ztick: (L, N_TICK_DRAWS) standard normals of ticks [tick, tick + L); zon: (K, N_ON_DRAWS) standard
        normals of power-ons [n_power, n_power + K).
    status columns: ins_mode, gps_fix, fom, powered.
    """
    f = f.copy()
    i = i.copy()
    L = truth.shape[0]
    out = np.empty((L, N_OUT))
    tru = np.empty((L, N_OUT))
    status = np.empty((L, 4), dtype=np.int64)
    c = np.empty(9)
    fn = np.empty(3)
    dwn = np.empty(3)
    dan = np.empty(3)
    dt_ns = int(np.rint(dt * 1e9))
    hold_ns = int(np.rint(p[P_HOLD] * 1e9))
    on0 = i[I_NPOWER]
    phg, sqg = gm_coeffs(dt, p[P_BG_GM_TAU])
    pha, sqa = gm_coeffs(dt, p[P_BA_GM_TAU])
    php, sqp = gm_coeffs(dt, p[P_GPS_TAU])
    phv, sqv = gm_coeffs(dt, p[P_GPS_VTAU])
    kp = 1.0 / p[P_AID_POS_TAU]
    kv = 1.0 / p[P_AID_VEL_TAU]
    kb1 = 2.0 / p[P_BARO_TAU]
    kb2 = 1.0 / (p[P_BARO_TAU] * p[P_BARO_TAU]) + 2.0 * p[P_G0] / p[P_R_EARTH]
    sq_dt = math.sqrt(dt)
    g = p[P_G0]
    R = p[P_R_EARTH]
    for j in range(L):
        row = truth[j]
        qn = math.sqrt(row[6] * row[6] + row[7] * row[7] + row[8] * row[8] + row[9] * row[9])
        quat_w = row[6] / qn
        quat_x = row[7] / qn
        quat_y = row[8] / qn
        quat_z = row[9] / qn
        # body -> NED (inline; quat_to_dcm semantics)
        ww = quat_w * quat_w
        xx = quat_x * quat_x
        yy = quat_y * quat_y
        zz = quat_z * quat_z
        c[0] = ww + xx - yy - zz
        c[1] = 2.0 * (quat_x * quat_y - quat_w * quat_z)
        c[2] = 2.0 * (quat_x * quat_z + quat_w * quat_y)
        c[3] = 2.0 * (quat_x * quat_y + quat_w * quat_z)
        c[4] = ww - xx + yy - zz
        c[5] = 2.0 * (quat_y * quat_z - quat_w * quat_x)
        c[6] = 2.0 * (quat_x * quat_z - quat_w * quat_y)
        c[7] = 2.0 * (quat_y * quat_z + quat_w * quat_x)
        c[8] = ww - xx - yy + zz
        lat = row[0]
        # ---- supply
        low, pw, tr = power_step(vbus[j], i[I_LOW_NS], i[I_POWERED], dt_ns, p[P_V_DROP], hold_ns)
        i[I_LOW_NS] = low
        i[I_POWERED] = pw
        if tr == P_LOST and airborne[j] == 1:
            i[I_FROZEN] = 1  # in flight: the solution is lost; outputs and status words freeze, unflagged
        if tr == P_RESTORED:
            i[I_NPOWER] += 1
            _power_on(f, p, zon, i[I_NPOWER] - on0)
            if airborne[j] == 0 and i[I_FROZEN] == 0:
                i[I_MODE] = MODE_ALIGN
                i[I_ALIGN_LEFT] = int(np.rint(p[P_T_ALIGN] / dt))
            i[I_FIX] = FIX_NONE
            i[I_REACQ_LEFT] = int(np.rint(p[P_T_REACQ] / dt))
        if i[I_PRIMED] == 0:  # sortie start: aligned on the ground before taxi (A-W2.2-4)
            _power_on(f, p, zon, i[I_NPOWER] - on0)
            _align_attitude(f, p, c, lat)
            for a in range(3):  # output filters start in steady state at the first frame's input
                f[F_NB + 2 * a] = row[10 + a] + f[F_BG0 + a]
                f[F_WB + 2 * a] = row[10 + a] + f[F_BG0 + a]
                f[F_ACC + 2 * a] = row[13 + a] + f[F_BA0 + a]
                f[F_NB + 2 * a + 1] = 0.0
                f[F_WB + 2 * a + 1] = 0.0
                f[F_ACC + 2 * a + 1] = 0.0
                f[F_UNB + a] = f[F_NB + 2 * a]
                f[F_UWB + a] = f[F_WB + 2 * a]
                f[F_UACC + a] = f[F_ACC + 2 * a]
            i[I_PRIMED] = 1
        # ---- IMU errors this tick (body)
        z = ztick[j]
        bgx = f[F_BG0] + f[F_BGM]
        bgy = f[F_BG0 + 1] + f[F_BGM + 1]
        bgz = f[F_BG0 + 2] + f[F_BGM + 2]
        bax = f[F_BA0] + f[F_BAM]
        bay = f[F_BA0 + 1] + f[F_BAM + 1]
        baz = f[F_BA0 + 2] + f[F_BAM + 2]
        sw = p[P_ARW] / sq_dt
        sa = p[P_ACC_NOISE] / sq_dt
        wgx = bgx + sw * z[0]
        wgy = bgy + sw * z[1]
        wgz = bgz + sw * z[2]
        wax = bax + sa * z[3]
        way = bay + sa * z[4]
        waz = baz + sa * z[5]
        for a in range(3):
            f[F_BGM + a] = phg * f[F_BGM + a] + p[P_BG_GM_SIG] * sqg * z[6 + a]
            f[F_BAM + a] = pha * f[F_BAM + a] + p[P_BA_GM_SIG] * sqa * z[9 + a]
        f[F_EGPS + 0] = php * f[F_EGPS + 0] + p[P_GPS_SIG_H] * sqp * z[12]
        f[F_EGPS + 1] = php * f[F_EGPS + 1] + p[P_GPS_SIG_H] * sqp * z[13]
        f[F_EGPS + 2] = php * f[F_EGPS + 2] + p[P_GPS_SIG_V] * sqp * z[14]
        for a in range(3):
            f[F_EVGPS + a] = phv * f[F_EVGPS + a] + p[P_GPS_VSIG] * sqv * z[15 + a]
        # ---- mode logic
        if i[I_ALIGN_LEFT] > 0:
            i[I_ALIGN_LEFT] -= 1
            if i[I_ALIGN_LEFT] == 0:
                _align_attitude(f, p, c, lat)
                i[I_MODE] = MODE_HYBRID
        if i[I_REACQ_LEFT] > 0:
            i[I_REACQ_LEFT] -= 1
            if i[I_REACQ_LEFT] == 0:
                i[I_FIX] = FIX_3D
        aided = i[I_FIX] == FIX_3D and i[I_POWERED] == 1
        if i[I_MODE] != MODE_ALIGN and i[I_POWERED] == 1:
            i[I_MODE] = MODE_HYBRID if aided else MODE_INERTIAL
        # ---- error dynamics (psi-angle, NED), Euler step
        body_to_nav(c, row[13], row[14], row[15], fn)
        body_to_nav(c, wgx, wgy, wgz, dwn)
        body_to_nav(c, wax, way, waz, dan)
        pn = f[F_PSI]
        pe = f[F_PSI + 1]
        pdn = f[F_PSI + 2]
        dpn = -dwn[0]
        dpe = -dwn[1]
        dpd = -dwn[2]
        # -psi x f + da (specific-force coupling)
        avn = -(pe * fn[2] - pdn * fn[1]) + dan[0]
        ave = -(pdn * fn[0] - pn * fn[2]) + dan[1]
        avd = -(pn * fn[1] - pe * fn[0]) + dan[2]
        avn = avn - g / R * f[F_DP]
        ave = ave - g / R * f[F_DP + 1]
        avd = avd + 2.0 * g / R * f[F_DP + 2]
        rpn = f[F_DV]
        rpe = f[F_DV + 1]
        rpd = f[F_DV + 2]
        if aided:
            # loosely coupled steady-state loops: position toward the GPS position error, velocity toward the
            # GPS (Doppler) velocity error
            avn = avn - kv * (f[F_DV] - f[F_EVGPS])
            ave = ave - kv * (f[F_DV + 1] - f[F_EVGPS + 1])
            avd = avd - kv * (f[F_DV + 2] - f[F_EVGPS + 2])
            rpn = rpn - kp * (f[F_DP] - f[F_EGPS])
            rpe = rpe - kp * (f[F_DP + 1] - f[F_EGPS + 1])
            rpd = rpd - kp * (f[F_DP + 2] - f[F_EGPS + 2])
            # tilt toward its unobservable equilibrium (f_hat horizontal = 0), heading under horizontal force
            dpn = dpn - (pn - dan[1] / g) / p[P_TILT_TAU]
            dpe = dpe - (pe + dan[0] / g) / p[P_TILT_TAU]
            fh2 = (fn[0] * fn[0] + fn[1] * fn[1]) / (g * g)
            dpd = dpd - fh2 * pdn / p[P_HDG_TAU]
            f[F_TUNAIDED] = 0.0
        else:
            # unaided: second-order baro-inertial vertical loop on the pressure altitude (column 16), which
            # damps the unstable free-inertial vertical channel (+2 g / R); its error is h_baro - h (up)
            ebd = row[2] - row[16]
            rpd = rpd - kb1 * (f[F_DP + 2] - ebd)
            avd = avd - kb2 * (f[F_DP + 2] - ebd)
            f[F_TUNAIDED] = f[F_TUNAIDED] + dt
        f[F_PSI] = pn + dt * dpn
        f[F_PSI + 1] = pe + dt * dpe
        f[F_PSI + 2] = pdn + dt * dpd
        f[F_DV] = f[F_DV] + dt * avn
        f[F_DV + 1] = f[F_DV + 1] + dt * ave
        f[F_DV + 2] = f[F_DV + 2] + dt * avd
        f[F_DP] = f[F_DP] + dt * rpn
        f[F_DP + 1] = f[F_DP + 1] + dt * rpe
        f[F_DP + 2] = f[F_DP + 2] + dt * rpd
        # ---- output filters (body rates NB/WB, accelerations)
        ubody = (row[10] + wgx, row[11] + wgy, row[12] + wgz)
        abody = (row[13] + wax, row[14] + way, row[15] + waz)
        for a in range(3):
            y, yd = lag2_step(
                f[F_NB + 2 * a],
                f[F_NB + 2 * a + 1],
                f[F_UNB + a],
                ubody[a],
                p[P_NB_WN],
                p[P_NB_ZETA],
                dt,
                n_sub,
            )
            f[F_NB + 2 * a] = y
            f[F_NB + 2 * a + 1] = yd
            y, yd = lag2_step(
                f[F_WB + 2 * a],
                f[F_WB + 2 * a + 1],
                f[F_UWB + a],
                ubody[a],
                p[P_WB_WN],
                p[P_WB_ZETA],
                dt,
                n_sub,
            )
            f[F_WB + 2 * a] = y
            f[F_WB + 2 * a + 1] = yd
            y, yd = lag2_step(
                f[F_ACC + 2 * a],
                f[F_ACC + 2 * a + 1],
                f[F_UACC + a],
                abody[a],
                p[P_ACC_WN],
                p[P_ACC_ZETA],
                dt,
                n_sub,
            )
            f[F_ACC + 2 * a] = y
            f[F_ACC + 2 * a + 1] = yd
            f[F_UNB + a] = ubody[a]
            f[F_UWB + a] = ubody[a]
            f[F_UACC + a] = abody[a]
        # ---- truth outputs (restricted; CIR truth_value)
        roll_t, pitch_t, yaw_t = euler_with_error(c, 0.0, 0.0, 0.0)
        tru[j, 0] = row[0]
        tru[j, 1] = row[1]
        tru[j, 2] = row[2]
        tru[j, 3] = row[3]
        tru[j, 4] = row[4]
        tru[j, 5] = row[5]
        tru[j, 6] = yaw_t
        tru[j, 7] = pitch_t
        tru[j, 8] = roll_t
        tru[j, 9] = row[13]
        tru[j, 10] = row[14]
        tru[j, 11] = row[15]
        for a in range(3):
            tru[j, 12 + a] = row[10 + a]
            tru[j, 15 + a] = row[10 + a]
        # ---- figure of merit (the INS's own error estimate: aided GPS sigma, else growing at the CEP rate)
        sig = p[P_GPS_SIG_H] * 1.1774 + p[P_CEP_RATE] * f[F_TUNAIDED]
        fom = 1
        for b in range(N_FOM):
            if sig > fom_bounds[b]:
                fom = b + 2
        i[I_FOM] = fom
        # ---- outputs: live solution, or held (unpowered / frozen in flight / aligning)
        live = i[I_POWERED] == 1 and i[I_FROZEN] == 0 and i[I_MODE] != MODE_ALIGN
        if live:
            rr = R + row[2]
            roll, pitch, yaw = euler_with_error(c, f[F_PSI], f[F_PSI + 1], f[F_PSI + 2])
            f[F_HOLD + 0] = row[0] + f[F_DP] / rr
            f[F_HOLD + 1] = row[1] + f[F_DP + 1] / (rr * math.cos(row[0]))
            f[F_HOLD + 2] = row[2] - f[F_DP + 2]
            f[F_HOLD + 3] = row[3] + f[F_DV]
            f[F_HOLD + 4] = row[4] + f[F_DV + 1]
            f[F_HOLD + 5] = row[5] + f[F_DV + 2]
            f[F_HOLD + 6] = yaw
            f[F_HOLD + 7] = pitch
            f[F_HOLD + 8] = roll
            for a in range(3):
                f[F_HOLD + 9 + a] = f[F_ACC + 2 * a]
                f[F_HOLD + 12 + a] = f[F_NB + 2 * a]
                f[F_HOLD + 15 + a] = f[F_WB + 2 * a]
        if i[I_FROZEN] == 0 and i[I_POWERED] == 1:
            i[I_HMODE] = i[I_MODE]
            i[I_HFIX] = i[I_FIX]
            i[I_HFOM] = i[I_FOM]
        for k in range(N_OUT):
            out[j, k] = f[F_HOLD + k]
        status[j, 0] = i[I_HMODE]
        status[j, 1] = i[I_HFIX]
        status[j, 2] = i[I_HFOM]
        status[j, 3] = i[I_POWERED]
        i[I_TICK] += 1
    return f, i, out, status, tru


def ins_reference(f, i, p, fom_bounds, truth, vbus, airborne, ztick, zon, dt, n_sub):
    """NumPy reference: the same source uncompiled."""
    return ins_kernel.py_func(f, i, p, fom_bounds, truth, vbus, airborne, ztick, zon, dt, n_sub)


def ins_initial_state() -> tuple[np.ndarray, np.ndarray]:
    f = np.zeros(N_F)
    i = np.zeros(N_I, dtype=np.int64)
    i[I_POWERED] = 1
    i[I_MODE] = MODE_HYBRID
    i[I_FIX] = FIX_3D
    i[I_HMODE] = MODE_HYBRID
    i[I_HFIX] = FIX_3D
    i[I_FOM] = 1
    i[I_HFOM] = 1
    return f, i
