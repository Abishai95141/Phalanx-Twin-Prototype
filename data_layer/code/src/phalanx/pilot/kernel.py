"""M04 pilot kernel (AD-22): deterministic guidance + crossover-type stochastic overlay, one ``@njit`` pass
per
block of 240 Hz ticks.

Per tick (aircraft inputs are previous-frame states):
1. **Plan lookup**: the segment in force (monotone pointer in the int state). Segments follow the plan's
   durations on a plan clock that **physical events** gate (W2.1a take-off fix): the take-off roll ends only
   at a confirmed lift-off (all gear off the ground for ``t_liftoff``) and the landing roll starts only at a
   confirmed touchdown (main gear on the ground for ``t_touchdown``), earlier or later than planned; the plan
   clock shifts by the difference (``shift`` in the int state), so every later segment keeps its planned
   duration. The segment in force per tick is an output (the module reports changes as ``pilot.segment``).
2. **Deterministic guidance** [ASSUMPTION A-W1.1-40]:
   - ground: PLA to the segment's feed-forward (cut-off until N2 reaches 20 % during the start
     [TRANSFER: T-50]);
   - take-off: feed-forward power; above the rotation speed, on the ground, the pilot tracks a reference
     attitude rising at ``q_rotate`` to ``theta_rotate`` with aft stick (attitude and rate errors, at most
     ``stick_rotate``; the M05 ground law links stick to elevon; ASSUMPTION A-W2.1-9); airborne, the
     rotation attitude through the load-factor law;
   - airborne: altitude -> vertical-speed -> flight-path angle -> load factor (with bank compensation);
     track -> bank -> roll rate; manoeuvring primitives command their target Nz (sustained turns at
     bank = acos(1/Nz), pull-ups for the first half of the dwell up to ``gamma_pull``); speed error -> PLA
     trim inside the segment's band around the feed-forward (PI, anti-windup); airbrake on overspeed or plan
     flag;
   - AAR contacts: the commanded closure speed (pilot trait, A-W1.1-44) is added during each closing run.
3. **Crossover-type overlay** [A-W1.1-42, A-W1.1-43]: the guidance commands pass through the pilot's
   effective delay (ring buffer, 0.1-0.2 s per pilot), a first-order neuromuscular lag, plus first-order
   remnant noise (airborne sticks; PLA only inside a trim band); the throttle is slew-limited (hand speed).
4. **Inceptor scaling** [A-W1.1-41]: Nz command -> normalised stick pitch (+7 g / -4.5 g full scale), roll
   rate -> normalised stick roll (200 deg/s full scale).
5. **Toe brakes** (``pilot.brake_cmd``, AD-47) [A-W1.1-47]: held (1) when parked, starting, at ground idle,
   in the run-up, hot refuel, shut-down and ground runs; on taxi proportional to the ground speed above
   the taxi speed; on the landing roll the same law, capped, once the ground speed is below the brake-on
   speed (aerobraking above it); released in the take-off roll and airborne.
6. **Spin recognition** [A-W1.1-47]: angle of attack (body velocity from the attitude, still air) and
   yaw rate beyond the recognition thresholds for ``t_spin`` latch the spin flag (the pilot selects the
   FCS spin-recovery mode); below the recovery thresholds for ``t_spin`` clear it. The module sends the
   flag changes as ``fcs.spin_mode`` (module.py).

The NumPy reference is the same source uncompiled (``pilot_kernel.py_func``); ``step`` is ``step_block``
with one tick, so they agree bitwise by construction.
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

from phalanx.scenario import phases as PH
from phalanx.scenario.config import P_TANKER
from phalanx.scenario.plan import (
    S_ALT,
    S_BRAKE,
    S_GEAR,
    S_HDG,
    S_MACH,
    S_NZ,
    S_PHASE,
    S_PLA,
    S_PLA_HI,
    S_PLA_LO,
    S_PRIM,
    S_TURN,
)

# --- parameter vector ----------------------------------------------------------------------------------
P_NAMES = (
    "k_alt",
    "vz_up_max",
    "vz_down_max",
    "k_gamma",
    "k_track",
    "bank_max",
    "k_bank",
    "k_speed",
    "k_speed_i",
    "v_rotate",
    "theta_rotate",
    "k_theta",
    "n2_start_frac",
    "overspeed_brake",
    "stick_nz_pos",
    "stick_nz_neg",
    "roll_rate_full",
    "nm_tau_stick",
    "nm_tau_throttle",
    "pla_slew",
    "remnant_corner",
    "aar_contact_period",
    "aar_closing_time",
    "pla_ground_idle",
    "pla_min_ab",
    "speed_margin",
    "n2_100",
    "g0",
    "v_taxi",
    "k_wheel_brake",
    "brake_land_max",
    "v_brake_on",
    "alpha_spin",
    "r_spin",
    "alpha_rec",
    "r_rec",
    "t_spin",
    "stick_rotate",
    "k_rot_theta",
    "t_liftoff",
    "t_touchdown",
    "q_rotate",
    "k_rot_q",
    "h_gear_up",
    "gamma_min",
    "h_safe",
    "h_turn",
    "bank_departure",
    "gamma_pull",
    "nz_push_min",
    "nz_rate",
    "gamma_trade",
)
(
    P_KALT,
    P_VZUP,
    P_VZDN,
    P_KGAM,
    P_KTRK,
    P_BANK,
    P_KBANK,
    P_KV,
    P_KVI,
    P_VROT,
    P_THROT,
    P_KTH,
    P_N2ST,
    P_OVSP,
    P_SNZP,
    P_SNZN,
    P_PFULL,
    P_TNM,
    P_TTHR,
    P_SLEW,
    P_RCORN,
    P_AARP,
    P_AARC,
    P_GI,
    P_MINAB,
    P_SPMARG,
    P_N2100,
    P_G0,
    P_VTAXI,
    P_KWB,
    P_WBLAND,
    P_VBON,
    P_ASPIN,
    P_RSPIN,
    P_AREC,
    P_RREC,
    P_TSPIN,
    P_STROT,
    P_KROTT,
    P_TLO,
    P_TTD,
    P_QROT,
    P_KROTQ,
    P_HGEAR,
    P_GMIN,
    P_HSAFE,
    P_HTURN,
    P_BANKDEP,
    P_GPULL,
    P_NZPUSH,
    P_NZRATE,
    P_GTRADE,
) = range(len(P_NAMES))

# --- state ---------------------------------------------------------------------------------------------
F_NAMES = (
    "pla_out",
    "pla_nm",
    "sp_nm",
    "sr_nm",
    "rem_p",
    "rem_r",
    "rem_t",
    "v_int",
    "gain",
    "rem_sd",
    "theta_ref",
    "nz_cmd",
)
(F_PLA, F_PLANM, F_SPNM, F_SRNM, F_REMP, F_REMR, F_REMT, F_VINT, F_GAIN, F_REMSD, F_SPROT, F_NZC) = range(
    len(F_NAMES)
)
I_NAMES = (
    "tick",
    "seg",
    "nseg",
    "started",
    "n_delay",
    "ptr",
    "t_end",
    "spin",
    "spin_cnt",
    "spin_sent",
    "shift",
    "air_cnt",
    "gnd_cnt",
    "seg_rep",
    "chute",
)
(
    I_TICK,
    I_SEG,
    I_NSEG,
    I_STARTED,
    I_NDELAY,
    I_PTR,
    I_TEND,
    I_SPIN,
    I_SPINCNT,
    I_SPINSENT,
    I_SHIFT,
    I_AIRCNT,
    I_GNDCNT,
    I_SEGREP,
    I_CHUTE,
) = range(len(I_NAMES))
#: airborne fine phases from which a confirmed touchdown starts the landing roll early
PH_AIR = np.array([PH.CLIMB, PH.TRANSIT, PH.MISSION, PH.DESCENT, PH.PATTERN, PH.APPROACH], dtype=np.int64)
#: phases with the toe brakes held (parked, start, idle, run-up against the brakes, refuel, shut-down)
PH_HOLD = np.array(
    [
        PH.PREFLIGHT,
        PH.ENGINE_START,
        PH.GROUND_IDLE,
        PH.RUNUP,
        PH.HOT_REFUEL,
        PH.SHUTDOWN,
        PH.POSTFLIGHT,
        PH.GROUND_RUN,
    ],
    dtype=np.int64,
)

PH_GROUND = np.array(
    [
        PH.PREFLIGHT,
        PH.ENGINE_START,
        PH.GROUND_IDLE,
        PH.TAXI_OUT,
        PH.RUNUP,
        PH.TAXI_IN,
        PH.HOT_REFUEL,
        PH.SHUTDOWN,
        PH.POSTFLIGHT,
        PH.GROUND_RUN,
        PH.LANDING,
    ],
    dtype=np.int64,
)
O_SP, O_SR, O_PED = 0, 1, 2
D_GEAR, D_BRAKE = 0, 1


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _clip(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def pilot_kernel(
    f,
    i,
    buf,
    plan_t,
    plan_f,
    plan_i,
    aar_off,
    aar,
    p,
    alt,
    tas,
    mach,
    vel,
    quat,
    omega,
    nz,
    wow,
    n2,
    t,
    noise,
    dt,
    n_eng,
    ground_phases,
):
    """Advance len(t) ticks. Pure: returns fresh (f, i, buf) and per-tick outputs
    (sticks (L, 3), pla (L, n_eng), discretes (L, 2), ab (L, n_eng), toe brakes (L, 2), segment in force (L,):
    -1 before the plan, the segment count after its end)."""
    f = f.copy()
    i = i.copy()
    buf = buf.copy()
    n = t.shape[0]
    nb = buf.shape[1]
    sticks = np.zeros((n, 3))
    pla_out = np.empty((n, n_eng))
    disc = np.zeros((n, 2), dtype=np.int64)
    ab = np.zeros((n, n_eng), dtype=np.int64)
    wbrake = np.zeros((n, 2))
    seg_out = np.empty(n, dtype=np.int64)
    n_spin = round(p[P_TSPIN] / dt)
    n_lo = round(p[P_TLO] / dt)
    n_td = round(p[P_TTD] / dt)
    dt_ns = round(dt * 1e9)
    a_nm = 1.0 - math.exp(-dt / p[P_TNM])
    a_thr = 1.0 - math.exp(-dt / p[P_TTHR])
    a_rem = math.exp(-p[P_RCORN] * dt)
    b_rem = math.sqrt(1.0 - a_rem * a_rem)
    g = p[P_G0]
    nseg = i[I_NSEG]
    for k in range(n):
        tk = t[k]
        # physical events: all gear off the ground / main gear on the ground, with persistence
        if wow[k, 0] == 0 and wow[k, 1] == 0 and wow[k, 2] == 0:
            i[I_AIRCNT] += 1
        else:
            i[I_AIRCNT] = 0
        if wow[k, 1] != 0 or wow[k, 2] != 0:
            i[I_GNDCNT] += 1
        else:
            i[I_GNDCNT] = 0
        lifted = i[I_AIRCNT] >= n_lo
        landed = i[I_GNDCNT] >= n_td
        tp = tk - i[I_SHIFT]  # plan clock
        active = nseg > 0 and tp >= plan_t[0] and tp < i[I_TEND]
        sp_g = 0.0
        sr_g = 0.0
        pla_g = 0.0
        lo = 0.0
        hi = 0.0
        gear = 1
        brake = 0
        airborne = False
        wb = 1.0  # parked outside the plan
        if active:
            seg = i[I_SEG]
            while seg < nseg - 1:
                ph_c = plan_i[seg, S_PHASE]
                ph_n = plan_i[seg + 1, S_PHASE]
                due = tp >= plan_t[seg + 1]
                # a boundary passed more than one tick ago is a catch-up (plan loaded, or the clock jumped,
                # mid-plan): the plan's own timing applies, the physical gates only to live transitions
                live = tp - plan_t[seg + 1] <= dt_ns
                gate = 0  # 0 none, 1 open (advance now), 2 closed (hold)
                if ph_c == PH.TAKEOFF and ph_n != PH.TAKEOFF:
                    # the take-off ends when safely airborne: confirmed lift-off, climbing, and h_gear_up
                    # above the field (the pilot then selects the gear up: next segment)
                    ok = lifted and vel[k, 2] < 0.0 and alt[k] - plan_f[seg, S_ALT] >= p[P_HGEAR]
                    gate = 1 if ok else 2
                else:
                    air_c = False
                    for c in range(PH_AIR.shape[0]):
                        if ph_c == PH_AIR[c]:
                            air_c = True
                    if air_c and ph_n == PH.LANDING:  # the landing roll starts at the confirmed touchdown
                        gate = 1 if landed else 2
                if gate == 1 and (live or not due):  # early or on time: the flown plan moves to this tick
                    i[I_SHIFT] = tk - plan_t[seg + 1]
                    tp = plan_t[seg + 1]
                    seg += 1
                    continue
                if gate == 2 and (live or not due):
                    if due:  # hold the segment: the plan clock waits
                        i[I_SHIFT] = tk - plan_t[seg + 1] + 1
                        tp = plan_t[seg + 1] - 1
                    break
                if not due:
                    break
                seg += 1
            i[I_SEG] = seg
            seg_out[k] = seg
            phase = plan_i[seg, S_PHASE]
            ff = plan_f[seg, S_PLA]
            lo = plan_f[seg, S_PLA_LO]
            hi = plan_f[seg, S_PLA_HI]
            gear = plan_i[seg, S_GEAR]
            brake = plan_i[seg, S_BRAKE]
            elapsed = (tp - plan_t[seg]) / 1e9
            seg_len = ((plan_t[seg + 1] if seg < nseg - 1 else i[I_TEND]) - plan_t[seg]) / 1e9
            is_ground = False
            for c in range(ground_phases.shape[0]):
                if phase == ground_phases[c]:
                    is_ground = True
            gs = math.sqrt(vel[k, 0] * vel[k, 0] + vel[k, 1] * vel[k, 1])
            wb = 0.0
            for c in range(PH_HOLD.shape[0]):
                if phase == PH_HOLD[c]:
                    wb = 1.0
            if phase == PH.TAXI_OUT or phase == PH.TAXI_IN:
                wb = _clip(p[P_KWB] * (gs - p[P_VTAXI]), 0.0, 1.0)
            elif phase == PH.LANDING and gs < p[P_VBON]:
                wb = _clip(p[P_KWB] * (gs - p[P_VTAXI]), 0.0, p[P_WBLAND])
            if phase == PH.ENGINE_START:
                if i[I_STARTED] == 0:
                    for e in range(n_eng):
                        if n2[k, e] >= p[P_N2ST] * p[P_N2100]:
                            i[I_STARTED] = 1
                pla_g = p[P_GI] if i[I_STARTED] == 1 else 0.0
                lo = pla_g
                hi = pla_g
            elif is_ground:
                f[F_NZC] = 1.0
                if phase != PH.PREFLIGHT and phase != PH.POSTFLIGHT:
                    i[I_STARTED] = 1
                pla_g = ff
                lo = ff
                hi = ff
            else:
                # attitude and path from the previous frame (quaternion body -> NED, scalar first)
                q0 = quat[k, 0]
                q1 = quat[k, 1]
                q2 = quat[k, 2]
                q3 = quat[k, 3]
                phi = math.atan2(2.0 * (q0 * q1 + q2 * q3), 1.0 - 2.0 * (q1 * q1 + q2 * q2))
                s_th = _clip(2.0 * (q0 * q2 - q3 * q1), -1.0, 1.0)
                theta = math.asin(s_th)
                vn = vel[k, 0]
                ve = vel[k, 1]
                vd = vel[k, 2]
                vh = math.sqrt(vn * vn + ve * ve)
                gam = math.atan2(-vd, vh)
                chi = math.atan2(ve, vn)
                # spin recognition: AoA from the body-axis velocity (R(q)^T v, still air) and yaw rate
                u_b = (
                    (1.0 - 2.0 * (q2 * q2 + q3 * q3)) * vn
                    + 2.0 * (q1 * q2 + q0 * q3) * ve
                    + 2.0 * (q1 * q3 - q0 * q2) * vd
                )
                w_b = (
                    2.0 * (q1 * q3 + q0 * q2) * vn
                    + 2.0 * (q2 * q3 - q0 * q1) * ve
                    + (1.0 - 2.0 * (q1 * q1 + q2 * q2)) * vd
                )
                aoa = math.atan2(w_b, u_b)
                r_abs = abs(omega[k, 2])
                if i[I_SPIN] == 0:
                    cond = aoa > p[P_ASPIN] and r_abs > p[P_RSPIN]
                else:
                    cond = aoa < p[P_AREC] and r_abs < p[P_RREC]
                i[I_SPINCNT] = i[I_SPINCNT] + 1 if cond else 0
                if i[I_SPINCNT] >= n_spin:
                    i[I_SPIN] = 1 - i[I_SPIN]
                    i[I_SPINCNT] = 0
                v = tas[k] if tas[k] > 30.0 else 30.0
                gain = f[F_GAIN]
                direct = False
                sp_dir = 0.0
                if phase == PH.TAKEOFF:
                    nz_cmd = 1.0
                    rotating = False
                    if tas[k] >= p[P_VROT]:
                        if wow[k, 1] != 0 or wow[k, 2] != 0:  # on the ground: the stick is the elevon
                            # the pilot rotates along a reference attitude rising at q_rotate to theta_rotate
                            # (attitude-and-rate tracking, aft stick at most stick_rotate)
                            direct = True
                            rotating = True
                            q_ref = p[P_QROT] if f[F_SPROT] < p[P_THROT] else 0.0
                            f[F_SPROT] = min(f[F_SPROT] + p[P_QROT] * dt, p[P_THROT])
                            sp_dir = _clip(
                                p[P_KROTT] * (f[F_SPROT] - theta) + p[P_KROTQ] * (q_ref - omega[k, 1]),
                                0.0,
                                p[P_STROT],
                            )
                        else:
                            nz_cmd = _clip(1.0 + gain * p[P_KTH] * (p[P_THROT] - theta), 0.5, 3.0)
                    if not rotating:
                        f[F_SPROT] = 0.0
                    phi_cmd = 0.0
                    pla_g = ff
                    lo = ff
                    hi = ff
                else:
                    airborne = True
                    alt_t = plan_f[seg, S_ALT]
                    a_est = tas[k] / mach[k] if mach[k] > 0.05 else 340.0
                    v_t = plan_f[seg, S_MACH] * a_est
                    vz = _clip(gain * p[P_KALT] * (alt_t - alt[k]), -p[P_VZDN], p[P_VZUP])
                    # energy state: 1 at or above the target speed, falling linearly to 0 at (1 - m) V_t
                    frac_e = _clip(1.0 - (v_t - tas[k]) / (p[P_SPMARG] * v_t), 0.0, 1.0)
                    h_fld = alt[k] - plan_f[0, S_ALT]
                    # energy guard: trade climb for speed below the target speed (level at V <= (1 - m) V_t)
                    if vz > 0.0 and tas[k] < v_t:
                        vz = vz * frac_e
                        # near the field the guard keeps a minimum climb gradient (no level-off at low height
                        # after the take-off, W2.1a): below h_safe above the departure field
                        if h_fld < p[P_HSAFE]:
                            vz_min = v * math.sin(p[P_GMIN])
                            if vz < vz_min:
                                vz = vz_min
                    gam_cmd = math.asin(_clip(vz / v, -0.6, 0.6))
                    # manoeuvre primitives trade height for speed when the energy decays (W2.1a-2, A-W2.1-12):
                    # a descent of up to gamma_trade at (1 - m) V_t, never within h_safe of the field
                    if plan_i[seg, S_PRIM] != 0 and frac_e < 1.0 and h_fld > p[P_HSAFE]:
                        gam_tr = -p[P_GTRADE] * (1.0 - frac_e)
                        if gam_cmd > gam_tr:
                            gam_cmd = gam_tr
                    e_psi = _wrap(plan_f[seg, S_HDG] - chi)
                    nz_t = plan_f[seg, S_NZ]
                    cphi = math.cos(phi)
                    if cphi < 0.2:
                        cphi = 0.2
                    # vertical: flight-path law with bank compensation (a level turn at bank phi pulls
                    # 1/cos phi)
                    nz_cmd = (math.cos(gam) + v * gain * p[P_KGAM] * (gam_cmd - gam) / g) / cphi
                    # lateral (W2.1a-2, A-W2.1-12): one continuous law for turns and track holding: track
                    # error -> turn-rate command (gain k_track), bounded by the turn rate of the segment's
                    # bank limit -> coordinated bank atan(V psi_dot / g). A turn primitive's bank limit is
                    # that of its target Nz, relaxed with the energy state (sustained turn: the pilot eases
                    # the turn as the speed decays, to a 30 deg floor); otherwise bank_max. The roll-out
                    # begins when the track error falls below psi_dot_max / k_track: no switch, no step.
                    if plan_i[seg, S_TURN] == 1 and nz_t > 1.2:
                        n_turn = 1.0 + (nz_t - 1.0) * frac_e
                        phi_lim = math.acos(1.0 / n_turn) if n_turn > 1.0 else 0.0
                        if phi_lim < p[P_BANKDEP]:
                            phi_lim = p[P_BANKDEP]
                    else:
                        phi_lim = p[P_BANK]
                    psi_dot_max = g * math.tan(phi_lim) / v
                    psi_dot = _clip(gain * p[P_KTRK] * e_psi, -psi_dot_max, psi_dot_max)
                    phi_cmd = math.atan(v * psi_dot / g)
                    # no-turn primitives with a target Nz (W2.1a, A-W2.1-10): a dive (target altitude
                    # below the previous segment's) dives on the flight-path law and pulls its Nz as the
                    # pull-out, from the pull-out height above the target until level; any other pulls
                    # up for the first half of the dwell, up to gamma_pull. (A turn primitive past its
                    # heading, an unbounded pull and a pull-up at the start of an idle-power dive each
                    # zoomed the aircraft into a stall.)
                    if plan_i[seg, S_TURN] == 0 and nz_t >= 2.0:
                        dive = seg > 0 and plan_f[seg, S_ALT] < plan_f[seg - 1, S_ALT] - 1.0
                        if dive:
                            if gam < 0.0:
                                h_po = v * v * (1.0 - math.cos(gam)) / (g * (nz_t - 1.0))
                                if alt[k] - alt_t <= h_po:
                                    nz_cmd = nz_t
                        elif elapsed < 0.5 * seg_len and gam < p[P_GPULL]:
                            nz_cmd = nz_t
                    if phase == PH.CLIMB:
                        # departure (W2.1a, A-W2.1-9): wings level below h_turn above the departure field, the
                        # departure bank limit below h_safe; the heading turn waits for the height
                        h_dep = alt[k] - plan_f[0, S_ALT]
                        if h_dep < p[P_HTURN]:
                            phi_cmd = 0.0
                        elif h_dep < p[P_HSAFE]:
                            phi_cmd = _clip(phi_cmd, -p[P_BANKDEP], p[P_BANKDEP])
                    # path corrections push at most to nz_push_min (an unload, W2.1a, A-W2.1-10): the bank-
                    # compensated flight-path law asked for full forward stick (-3.5 g) in a 69 deg bank when
                    # a turn primitive gave way to a 2,500 m descent
                    if nz_cmd < p[P_NZPUSH]:
                        nz_cmd = p[P_NZPUSH]
                    # speed: Mach target (+ AAR closing run) -> PLA trim inside the band
                    if plan_i[seg, S_PRIM] == P_TANKER:
                        c = int(elapsed // p[P_AARP])
                        idx = aar_off[seg] + c
                        if idx < aar.shape[0] and elapsed - c * p[P_AARP] < p[P_AARC]:
                            v_t += aar[idx]
                    e_v = v_t - tas[k]
                    if hi > lo:
                        trial = ff + p[P_KV] * e_v + f[F_VINT]
                        if (trial < hi or e_v < 0.0) and (trial > lo or e_v > 0.0):
                            f[F_VINT] += p[P_KVI] * e_v * dt
                        pla_g = _clip(ff + p[P_KV] * e_v + f[F_VINT], lo, hi)
                    else:
                        f[F_VINT] = 0.0
                        pla_g = ff
                    if tas[k] - v_t > p[P_OVSP]:
                        brake = 1
                nz_cmd = _clip(nz_cmd, 1.0 - p[P_SNZN], 1.0 + p[P_SNZP])
                # the commanded load factor moves at most nz_rate g/s (W2.1a-2, A-W2.1-12): law changes (a
                # pull-up reaching its climb angle, a turn ending, a segment change) give a ramp, not a step
                if direct:
                    f[F_NZC] = 1.0
                else:
                    dn = p[P_NZRATE] * dt
                    nz_cmd = _clip(nz_cmd, f[F_NZC] - dn, f[F_NZC] + dn)
                    f[F_NZC] = nz_cmd
                p_cmd = _clip(gain * p[P_KBANK] * (phi_cmd - phi), -p[P_PFULL], p[P_PFULL])
                sr_g = p_cmd / p[P_PFULL]
                if direct:
                    sp_g = sp_dir
                elif nz_cmd >= 1.0:
                    sp_g = (nz_cmd - 1.0) / p[P_SNZP]
                else:
                    sp_g = (nz_cmd - 1.0) / p[P_SNZN]
        # --- crossover overlay: delay, neuromuscular lag, remnant
        ptr = i[I_PTR]
        buf[0, ptr] = sp_g
        buf[1, ptr] = sr_g
        buf[2, ptr] = pla_g
        rd = (ptr - i[I_NDELAY]) % nb
        i[I_PTR] = (ptr + 1) % nb
        f[F_SPNM] += a_nm * (buf[0, rd] - f[F_SPNM])
        f[F_SRNM] += a_nm * (buf[1, rd] - f[F_SRNM])
        f[F_PLANM] += a_thr * (buf[2, rd] - f[F_PLANM])
        if abs(buf[2, rd] - f[F_PLANM]) < 1e-6:  # the hand reaches the detent (no asymptotic residue)
            f[F_PLANM] = buf[2, rd]
        sd = f[F_REMSD]
        f[F_REMP] = a_rem * f[F_REMP] + b_rem * sd * noise[k, 0]
        f[F_REMR] = a_rem * f[F_REMR] + b_rem * sd * noise[k, 1]
        f[F_REMT] = a_rem * f[F_REMT] + b_rem * sd * noise[k, 2]
        sp = f[F_SPNM]
        sr = f[F_SRNM]
        target = f[F_PLANM]
        if airborne:
            sp += f[F_REMP]
            sr += f[F_REMR]
            if hi > lo:
                target = _clip(target + 0.5 * (hi - lo) * f[F_REMT], lo, hi)
        step = _clip(target - f[F_PLA], -p[P_SLEW] * dt, p[P_SLEW] * dt)
        f[F_PLA] += step
        sticks[k, O_SP] = _clip(sp, -1.0, 1.0)
        sticks[k, O_SR] = _clip(sr, -1.0, 1.0)
        for e in range(n_eng):
            pla_out[k, e] = f[F_PLA]
            ab[k, e] = 1 if f[F_PLA] >= p[P_MINAB] else 0
        disc[k, D_GEAR] = gear
        disc[k, D_BRAKE] = brake
        wbrake[k, 0] = wb
        wbrake[k, 1] = wb
        if not active:
            seg_out[k] = -1 if (nseg == 0 or tp < plan_t[0]) else nseg
        i[I_SEGREP] = seg_out[k]
        i[I_TICK] += 1
    return f, i, buf, sticks, pla_out, disc, ab, wbrake, seg_out


def pilot_kernel_reference(*args):
    """NumPy reference: the same source uncompiled (identical to ``NUMBA_DISABLE_JIT=1``)."""
    return getattr(pilot_kernel, "py_func", pilot_kernel)(*args)


__all__ = ["F_NAMES", "I_NAMES", "PH_AIR", "PH_GROUND", "P_NAMES", "pilot_kernel", "pilot_kernel_reference"]
