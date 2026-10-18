"""Fused truth-loop kernel (W2.1 deliverable 2; AD-22, AD-36): the whole continuous loop in one compiled pass.

The back-edges af -> env and M13 lanes -> M08 make every continuous module of the telemetry System one loop
segment. Run by the core scheduler, that segment falls back to the per-step interpreter (one Python ``step``
per module per truth step; measured ~16 ms/step warm). :class:`TruthLoopGroup` is its ``FusedGroup``: one
``@njit(cache=False)`` loop over the block that calls **the modules' own compiled kernels** with ``L = 1`` per
truth step, in the System's Gauss-Seidel order, exactly as the per-step path does. It must equal that path
bitwise (acceptance A4; ``tests/integration/test_integration_fused.py``).

How it stays a faithful copy of the per-step path, not a re-implementation:

- **Wiring from the System's connections.** A signal bus holds every member output consumed inside the loop
  and every input fed from outside the group (``ext_inputs``). Delayed edges read the bus as it was at the
  start of the step, other edges the current bus: the scheduler's ``delayed`` semantics.
- **Packing derived from the modules' code.** The kernel-input layout of each module (which bus element
  goes to which kernel input element) is obtained by calling the module's own packing code (``pack_inputs``,
  ``_pack``, ``pack_lanes``, ``_truth_rows``, ...) once on probe inputs whose elements carry unique ids. The
  output side likewise probes the modules' own unpack code (``unpack_outputs``, ``_ports_from``, ``_outputs``,
  ``_group_out``) with id-valued raw outputs.
- **Exogenous inputs from the modules' own methods.** Keyed noise and clock schedules are absolute-index
  functions of state and time (AD-37), so they are drawn per block with the modules' methods (``_noise``,
  ``fault_draws``, ``frame_schedule``, ``AcquisitionCore._draws``...) and sliced per step.
- **Outputs and states afterwards from the modules' code** where it is a function (``unpack_outputs``,
  ``_ports_from``, ``_outputs``, ``_group_out``, ``recorded_words``); the few inline post-processing lines of
  M03/M04/M05/M13 ``step_block`` are mirrored here and covered by the bitwise test.

M08 fault/caution events are produced as ``Fadec.step`` produces them (``Fadec.fault_events`` on each step's
fault-bit transition, with that step's frame schedule) and returned with their emission time, so the core's
block-cut rule keeps dispatch identical to stepping.

``cache=False`` (carry-forward: a cached caller is not invalidated when a callee in another file changes).
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from numba import njit

from phalanx.core.module import ContractError
from phalanx.core.sampling import samples_for_steps
from phalanx.core.scheduler import Connection
from phalanx.core.time import NS_PER_S, latest_truth_steps, truth_step_times_ns

_JIT = {"cache": False, "fastmath": False, "error_model": "numpy", "nogil": True}

# bus source codes of a gather entry
SRC_F, SRC_F0, SRC_I, SRC_I0, SRC_ZERO = 0, 1, 2, 3, 4


# ============================================================================================ compiled
# helpers
@njit(**_JIT)
def _gather_f(code, idx, fb, fb0, ib, ib0, out):
    for k in range(code.shape[0]):
        c = code[k]
        if c == SRC_F:
            out[k] = fb[idx[k]]
        elif c == SRC_F0:
            out[k] = fb0[idx[k]]
        elif c == SRC_I:
            out[k] = ib[idx[k]]
        elif c == SRC_I0:
            out[k] = ib0[idx[k]]
        else:
            out[k] = 0.0


@njit(**_JIT)
def _gather_i(code, idx, ib, ib0, out):
    for k in range(code.shape[0]):
        c = code[k]
        if c == SRC_I:
            out[k] = ib[idx[k]]
        elif c == SRC_I0:
            out[k] = ib0[idx[k]]
        else:
            out[k] = 0


@njit(**_JIT)
def _scatter(raw, src, dst, to_int, fb, ib):
    """Bus element ``dst[k]`` <- ``raw[src[k]]`` (float bus, or int bus by truncation like ``astype``)."""
    for k in range(src.shape[0]):
        v = raw[src[k]]
        if to_int[k] == 1:
            ib[dst[k]] = np.int64(v)
        else:
            fb[dst[k]] = v


@njit(**_JIT)
def _scatter_int(raw, src, dst, fb, ib, to_float):
    for k in range(src.shape[0]):
        v = raw[src[k]]
        if to_float[k] == 1:
            fb[dst[k]] = v
        else:
            ib[dst[k]] = v


# The compiled kernels are imported where the loop is built (they are module attributes; numba resolves them
# as globals of this module at compile time).
from phalanx.acquisition.kernel import acq_kernel  # noqa: E402
from phalanx.airframe.kernel import airframe_kernel  # noqa: E402
from phalanx.engine.kernel import engine_kernel  # noqa: E402
from phalanx.environment.kernel import env_kernel  # noqa: E402
from phalanx.fadec.kernel import fadec_block  # noqa: E402
from phalanx.fcs.kernel import fcs_kernel  # noqa: E402
from phalanx.fcs.layout import I_NNEXT as FCS_I_NNEXT  # noqa: E402
from phalanx.pilot.kernel import pilot_kernel  # noqa: E402
from phalanx.sensors.avionics.adc import adc_kernel, static_pressure_at_array  # noqa: E402
from phalanx.sensors.kernel import m12_kernel  # noqa: E402
from phalanx.utilities.kernel import utilities_kernel  # noqa: E402
from phalanx.utilities.layout import I_JFS_ATTEMPT, I_JFS_DRAWN, I_JFS_MODE  # noqa: E402

_JFS_CRANK = 1  # utilities.jfs JFS_CRANK (checked at import below)


@njit(**_JIT)
def _truth_loop(
    n,
    t,
    dt,
    fb,
    ib,
    ext_f_src,
    ext_f_dst,
    ext_i_src,
    ext_i_dst,
    ext_f,
    ext_i,
    # --- M03 environment
    s03,
    c03,
    g03,
    x03,
    sc03,
    # --- M04 pilot
    s04,
    c04,
    g04,
    x04,
    sc04,
    # --- M08 FADEC
    s08,
    c08,
    g08,
    x08,
    sc08,
    # --- M07 engine
    s07,
    c07,
    g07,
    x07,
    sc07,
    # --- M06 airframe
    s06,
    c06,
    g06,
    sc06,
    # --- M09 utilities
    s09,
    c09,
    g09,
    x09,
    sc09,
    # --- M12 sensors
    s12,
    c12,
    g12,
    x12,
    sc12,
    # --- M13 lanes (FADEC, DFCC)
    s13a,
    s13b,
    g13,
    doms,
    # --- M05 FCS
    s05,
    c05,
    g05,
    x05,
    sc05,
    # --- M12 avionics: the ADC's P0 altitude signal (M08 p0, W2.2), the rest of avio after the loop
    sav,
    cav,
    gav,
    xav,
):
    # ------------------------------------------------------------------ unpack state / config / tables
    f03, i03, prof03, turb03, gusts03, dist03 = s03
    p03, consts03, tustin03, catc03, dims03, offs03, phi03, lq03, cvec03, gain03, nout03 = c03
    ts03, turbn03, distn03 = x03
    f04, i04, buf04, plant04, planf04, plani04, aaroff04, aar04 = s04
    p04, ne04, phg04 = c04
    noise04 = x04
    f08, i08 = s08
    p08, tb08, cfg08, dt08, cap08, ne08 = c08
    nfr08, ateng08, atcmd08 = x08
    f07, i07, buf07 = s07
    p07, tb07, dt07, nsub07, ndel07, ne07 = c07
    z07, nab0_07 = x07
    f06, i06 = s06
    dp06, ap06, tab06, gtab06, ttab06, ne06, mode06 = c06
    f09, i09 = s09
    p09, cfg09 = c09
    ign09, have_ign09 = x09
    ef12, ei12, cf12, ci12 = s12
    eli12, elp12, chi12, chp12, tx12, ty12, toff12, cols12, k12, nsub12 = c12
    tend12, fu12 = x12
    af13a, ai13a, _nn13a = s13a
    af13b, ai13b, _nn13b = s13b
    f05, i05 = s05
    p05, tab05, tf05, nsa05, crit05 = c05
    fr05, off05, nnext05 = x05
    fav, iav = sav
    pav, pe_m, pe_k, vb_m, vb_b, sb_m, sb_b, rc_m, rc_r, dh_z, dh_e, hpcol_av, p0slot_av, nl_av = cav
    has_av = xav
    # ------------------------------------------------------------------ working arrays
    nb_f = fb.shape[0]
    nb_i = ib.shape[0]
    fb0 = np.empty(nb_f)
    ib0 = np.empty(nb_i, dtype=np.int64)
    alt03 = np.empty(1)
    hag03 = np.empty(1)
    tas03 = np.empty(1)
    ph03 = np.empty(1, dtype=np.int64)
    a04 = np.empty(g04[0].shape[0])
    u08_pla = np.empty(ne08)
    u08_p0 = np.empty(1)
    u08_l = np.empty(cap08 * ne08 * 13)
    u07 = np.empty(g07[0].shape[0])
    ui07 = np.empty(g07[2].shape[0], dtype=np.int64)
    u06 = np.empty(g06[0].shape[0])
    u09 = np.empty(g09[0].shape[0])
    u12 = np.empty(g12[0].shape[0])
    b12 = np.empty(g12[2].shape[0])
    s13 = np.empty(g13[0].shape[0])
    ph13 = np.empty(1, dtype=np.int64)
    u05 = np.empty(g05[0].shape[0])
    uav = np.empty(gav[0].shape[0])
    iav_in = np.empty(gav[2].shape[0], dtype=np.int64)
    lanes_av = np.empty((1, nl_av))
    truth_av = np.empty((1, 7))
    heat_av = np.empty(1, dtype=np.int64)
    gear_av = np.empty(1, dtype=np.int64)
    hp_av = np.empty(1)
    h_p0 = np.empty(n)
    # outputs history (raw kernel outputs per step)
    h03_atm = np.empty((n, 5))
    h03_wind = np.empty((n, 3))
    h03_tv = np.empty((n, 3))
    h03_tr = np.empty((n, 3))
    h03_w = np.empty((n, nout03))
    h04_st = np.empty((n, 3))
    h04_pla = np.empty((n, ne04))
    h04_d = np.empty((n, 2), dtype=np.int64)
    h04_ab = np.empty((n, ne04), dtype=np.int64)
    h04_wb = np.empty((n, 2))
    h04_seg = np.empty(n, dtype=np.int64)
    wow04 = np.empty((1, 3), dtype=np.int64)
    nof08 = sc08[3]
    noi08 = sc08[4]
    h08_f = np.empty((n, ne08, nof08))
    h08_i = np.empty((n, ne08, noi08), dtype=np.int64)
    ny07 = sc07[3]
    nyi07 = sc07[4]
    h07_y = np.empty((n, ne07, ny07))
    h07_yi = np.empty((n, ne07, nyi07), dtype=np.int64)
    h06 = np.empty((n, sc06[3]))
    h09 = np.empty((n, sc09[3]))
    h09_i = np.empty((n, sc09[4]), dtype=np.int64)
    nch12 = sc12[3]
    h12_s = np.empty((n, nch12))
    h12_x = np.empty((n, nch12))
    h05 = np.empty((n, sc05[3]))
    status = 0  # 0 ok; 1 = M09 ignition draw needed but not precomputed; 2 = M07 light-off draws exhausted
    # per-domain sample outputs (M13): concatenated over the block, per domain
    for j in range(n):
        tj = t[j : j + 1]
        for q in range(nb_f):
            fb0[q] = fb[q]
        for q in range(nb_i):
            ib0[q] = ib[q]
        for q in range(ext_f_src.shape[0]):
            fb[ext_f_dst[q]] = ext_f[j, ext_f_src[q]]
        for q in range(ext_i_src.shape[0]):
            ib[ext_i_dst[q]] = ext_i[j, ext_i_src[q]]
        # -------------------------------------------------------------- M03 environment
        _gather_f(g03[0], g03[1], fb, fb0, ib, ib0, alt03)
        _gather_f(g03[2], g03[3], fb, fb0, ib, ib0, hag03)
        _gather_f(g03[4], g03[5], fb, fb0, ib, ib0, tas03)
        _gather_i(g03[6], g03[7], ib, ib0, ph03)
        f03, i03, turb03, gusts03, dist03, atm, wind, tvel, trate, wout = env_kernel(
            f03,
            i03,
            prof03,
            turb03,
            gusts03,
            dist03,
            p03,
            consts03,
            tustin03,
            catc03,
            dims03,
            offs03,
            phi03,
            lq03,
            cvec03,
            gain03,
            alt03,
            hag03,
            tas03,
            ph03,
            ts03[j : j + 1],
            turbn03[j : j + 1],
            distn03[j : j + 1],
            dt,
        )
        for q in range(5):
            h03_atm[j, q] = atm[0, q]
        for q in range(3):
            h03_wind[j, q] = wind[0, q]
            h03_tv[j, q] = tvel[0, q]
            h03_tr[j, q] = trate[0, q]
        for q in range(nout03):
            h03_w[j, q] = wout[0, q]
        _scatter(h03_atm[j], sc03[0], sc03[1], sc03[2], fb, ib)
        _scatter(h03_wind[j], sc03[3], sc03[4], sc03[5], fb, ib)
        _scatter(h03_tv[j], sc03[6], sc03[7], sc03[8], fb, ib)
        _scatter(h03_tr[j], sc03[9], sc03[10], sc03[11], fb, ib)
        _scatter(h03_w[j], sc03[12], sc03[13], sc03[14], fb, ib)
        # -------------------------------------------------------------- M04 pilot
        _gather_f(g04[0], g04[1], fb, fb0, ib, ib0, a04)
        o = 0
        alt04 = a04[o : o + 1].copy()
        o += 1
        tas04 = a04[o : o + 1].copy()
        o += 1
        mach04 = a04[o : o + 1].copy()
        o += 1
        vel04 = a04[o : o + 3].copy().reshape((1, 3))
        o += 3
        quat04 = a04[o : o + 4].copy().reshape((1, 4))
        o += 4
        om04 = a04[o : o + 3].copy().reshape((1, 3))
        o += 3
        nz04 = a04[o : o + 1].copy()
        o += 1
        for q in range(3):
            wow04[0, q] = np.int64(a04[o + q])
        o += 3
        n2_04 = a04[o : o + ne04].copy().reshape((1, ne04))
        f04, i04, buf04, sticks, pla, disc, ab, wb, seg04 = pilot_kernel(
            f04,
            i04,
            buf04,
            plant04,
            planf04,
            plani04,
            aaroff04,
            aar04,
            p04,
            alt04,
            tas04,
            mach04,
            vel04,
            quat04,
            om04,
            nz04,
            wow04,
            n2_04,
            tj,
            noise04[j : j + 1],
            dt,
            ne04,
            phg04,
        )
        for q in range(3):
            h04_st[j, q] = sticks[0, q]
        for q in range(ne04):
            h04_pla[j, q] = pla[0, q]
            h04_ab[j, q] = ab[0, q]
        for q in range(2):
            h04_d[j, q] = disc[0, q]
            h04_wb[j, q] = wb[0, q]
        h04_seg[j] = seg04[0]
        _scatter(h04_st[j], sc04[0], sc04[1], sc04[2], fb, ib)
        _scatter(h04_pla[j], sc04[3], sc04[4], sc04[5], fb, ib)
        _scatter_int(h04_d[j], sc04[6], sc04[7], fb, ib, sc04[8])
        _scatter_int(h04_ab[j], sc04[9], sc04[10], fb, ib, sc04[11])
        _scatter(h04_wb[j], sc04[12], sc04[13], sc04[14], fb, ib)
        # -------------------------------------------------------------- M08 FADEC
        _gather_f(g08[0], g08[1], fb, fb0, ib, ib0, u08_pla)
        _gather_f(g08[2], g08[3], fb, fb0, ib, ib0, u08_p0)
        _gather_f(g08[4], g08[5], fb, fb0, ib, ib0, u08_l)
        f08, i08, outf08, outi08 = fadec_block(
            f08,
            i08,
            p08,
            tb08,
            cfg08,
            dt08,
            u08_pla.copy().reshape((1, ne08)),
            u08_p0.copy(),
            ateng08[j : j + 1],
            atcmd08[j : j + 1],
            u08_l.copy().reshape((1, cap08, ne08, 13)),
            nfr08[j : j + 1],
        )
        for e in range(ne08):
            for q in range(nof08):
                h08_f[j, e, q] = outf08[0, e, q]
            for q in range(noi08):
                h08_i[j, e, q] = outi08[0, e, q]
        _scatter(h08_f[j].ravel(), sc08[0], sc08[1], sc08[2], fb, ib)
        _scatter_int(h08_i[j].ravel(), sc08[5], sc08[6], fb, ib, sc08[7])
        # -------------------------------------------------------------- M07 engine
        _gather_f(g07[0], g07[1], fb, fb0, ib, ib0, u07)
        _gather_i(g07[2], g07[3], ib, ib0, ui07)
        uu07 = u07.copy().reshape((1, ne07, u07.shape[0] // ne07))
        uui07 = ui07.copy().reshape((1, ne07, ui07.shape[0] // ne07))
        z = np.zeros((ne07, 2))
        for e in range(ne07):
            if uui07[0, e, g07[4]] != 0:  # ab_enable: the module draws for this step
                a = i07[e, g07[5]] - nab0_07[e]
                if a + 2 > z07.shape[1]:
                    status = 2
                else:
                    z[e, 0] = z07[e, a]
                    z[e, 1] = z07[e, a + 1]
        f07, i07, buf07, y, yi, _aux = engine_kernel(
            f07, i07, buf07, p07, tb07, uu07, uui07, z, dt07, nsub07, ndel07, False
        )
        for e in range(ne07):
            for q in range(ny07):
                h07_y[j, e, q] = y[0, e, q]
            for q in range(nyi07):
                h07_yi[j, e, q] = yi[0, e, q]
        _scatter(h07_y[j].ravel(), sc07[0], sc07[1], sc07[2], fb, ib)
        _scatter_int(h07_yi[j].ravel(), sc07[5], sc07[6], fb, ib, sc07[7])
        # -------------------------------------------------------------- M06 airframe
        _gather_f(g06[0], g06[1], fb, fb0, ib, ib0, u06)
        f06, i06, out06 = airframe_kernel(
            f06,
            i06,
            dp06,
            ap06,
            tab06,
            gtab06,
            ttab06,
            u06.copy().reshape((1, u06.shape[0])),
            dt,
            ne06,
            mode06,
        )
        for q in range(sc06[3]):
            h06[j, q] = out06[0, q]
        _scatter(h06[j], sc06[0], sc06[1], sc06[2], fb, ib)
        # -------------------------------------------------------------- M09 utilities
        _gather_f(g09[0], g09[1], fb, fb0, ib, ib0, u09)
        crank = i09[I_JFS_MODE] == _JFS_CRANK and i09[I_JFS_DRAWN] == 0 and i09[I_JFS_ATTEMPT] > 0
        u_ign = 1.0
        if crank:
            if have_ign09 == 1:
                u_ign = ign09
            else:
                status = 1
        f09, i09, out09, outi09 = utilities_kernel(
            f09, i09, p09, u09.copy().reshape((1, u09.shape[0])), cfg09, u_ign, dt
        )
        for q in range(sc09[3]):
            h09[j, q] = out09[0, q]
        for q in range(sc09[4]):
            h09_i[j, q] = outi09[0, q]
        _scatter(h09[j], sc09[0], sc09[1], sc09[2], fb, ib)
        _scatter_int(h09_i[j], sc09[5], sc09[6], fb, ib, sc09[7])
        # -------------------------------------------------------------- M12 sensors
        _gather_f(g12[0], g12[1], fb, fb0, ib, ib0, u12)
        _gather_f(g12[2], g12[3], fb, fb0, ib, ib0, b12)
        ef12, ei12, cf12, ci12, S, X = m12_kernel(
            ef12,
            ei12,
            cf12,
            ci12,
            eli12,
            elp12,
            chi12,
            chp12,
            tx12,
            ty12,
            toff12,
            cols12,
            k12,
            u12.copy().reshape((1, u12.shape[0])),
            b12.copy().reshape((1, b12.shape[0])),
            tend12[j : j + 1],
            fu12[j : j + 1],
            dt,
            nsub12,
        )
        for q in range(nch12):
            h12_s[j, q] = S[0, q]
            h12_x[j, q] = X[0, q]
        _scatter(h12_s[j], sc12[0], sc12[1], sc12[2], fb, ib)
        # -------------------------------------------------------------- M13 in-loop lanes
        _gather_f(g13[0], g13[1], fb, fb0, ib, ib0, s13)
        _gather_i(g13[2], g13[3], ib, ib0, ph13)
        for d in range(len(doms)):
            dm = doms[d]
            mod = dm[0]
            chans = dm[1]
            s_col = dm[2]
            P = dm[3]
            Q = dm[4]
            reg = dm[5]
            airb = dm[6]
            times = dm[7]
            w = dm[8]
            zz = dm[9]
            uu = dm[10]
            coll = dm[11]
            sb = dm[12]
            lane_dst = dm[13]
            cap = dm[14]
            scale = dm[15]
            offset = dm[16]
            h_code = dm[17]
            h_val = dm[18]
            h_tru = dm[19]
            h_flg = dm[20]
            h_vld = dm[21]
            t_start = dm[22]
            t_end = dm[23]
            nc = chans.shape[0]
            if mod == 0:
                af = af13a
                ai = ai13a
            else:
                af = af13b
                ai = ai13b
            fsub = np.empty((nc, af.shape[1]))
            isub = np.empty((nc, ai.shape[1]), dtype=np.int64)
            Sd = np.empty((1, nc))
            for c in range(nc):
                for q in range(af.shape[1]):
                    fsub[c, q] = af[chans[c], q]
                for q in range(ai.shape[1]):
                    isub[c, q] = ai[chans[c], q]
                Sd[0, c] = s13[s_col[c]]
            Xd = np.zeros((1, nc))
            s0 = sb[j]
            s1 = sb[j + 1]
            ns = s1 - s0
            f2, i2, code, val, tru, flg, vld = acq_kernel(
                fsub,
                isub,
                P,
                Q,
                reg,
                airb,
                Sd,
                Xd,
                t_start[j : j + 1],
                t_end[j : j + 1],
                times[s0:s1],
                np.zeros(ns, dtype=np.int64),
                w[s0:s1],
                ph13,
                zz[s0:s1],
                uu[s0:s1],
                coll[s0:s1],
            )
            for c in range(nc):
                for q in range(af.shape[1]):
                    af[chans[c], q] = f2[c, q]
                for q in range(ai.shape[1]):
                    ai[chans[c], q] = i2[c, q]
            for s in range(ns):
                for c in range(nc):
                    h_code[s0 + s, c] = code[s, c]
                    h_val[s0 + s, c] = val[s, c]
                    h_tru[s0 + s, c] = tru[s, c]
                    h_flg[s0 + s, c] = flg[s, c]
                    h_vld[s0 + s, c] = vld[s, c]
            # in-loop lane values consumed by the controllers: SI of the digitised reading, slots >= n are 0
            for c in range(nc):
                dst = lane_dst[c]
                if dst < 0:
                    continue
                for sl in range(cap):
                    fb[dst + sl] = 0.0
                for s in range(ns):
                    fb[dst + s] = val[s, c] * scale[c] + offset[c]
        # -------------------------------------------------------------- M05 FCS
        _gather_f(g05[0], g05[1], fb, fb0, ib, ib0, u05)
        f05, i05, out05 = fcs_kernel(
            f05,
            i05,
            p05,
            tab05,
            u05.copy().reshape((1, u05.shape[0])),
            fr05[j : j + 1],
            off05[j : j + 1],
            dt,
            tf05,
            nsa05,
            crit05,
        )
        i05[FCS_I_NNEXT] = nnext05[j]
        for q in range(sc05[3]):
            h05[j, q] = out05[0, q]
        _scatter(h05[j], sc05[0], sc05[1], sc05[2], fb, ib)
        # -------------------------------------------------------------- M12 avionics ADC (P0 for M08)
        _gather_f(gav[0], gav[1], fb, fb0, ib, ib0, uav)
        _gather_i(gav[2], gav[3], ib, ib0, iav_in)
        for c in range(nl_av):
            lanes_av[0, c] = uav[c]
        for q in range(7):
            truth_av[0, q] = uav[nl_av + q]
        heat_av[0] = iav_in[0]
        gear_av[0] = iav_in[1]
        fav, iav, o_av, _v_av, _t_av = adc_kernel(
            fav,
            iav,
            pav,
            lanes_av,
            has_av[j : j + 1],
            heat_av,
            gear_av,
            truth_av,
            pe_m,
            pe_k,
            vb_m,
            vb_b,
            sb_m,
            sb_b,
            rc_m,
            rc_r,
            dh_z,
            dh_e,
            dt,
        )
        hp_av[0] = o_av[0, hpcol_av]
        p0v = static_pressure_at_array(hp_av, pav)
        h_p0[j] = p0v[0]
        if p0slot_av >= 0:
            fb[p0slot_av] = p0v[0]
    return (
        status,
        (f03, i03, turb03, gusts03, dist03),
        (f04, i04, buf04),
        (f08, i08),
        (f07, i07, buf07),
        (f06, i06),
        (f09, i09),
        (ef12, ei12, cf12, ci12),
        (af13a, ai13a, af13b, ai13b),
        (f05, i05),
        (fav, iav, h_p0),
        (h03_atm, h03_wind, h03_tv, h03_tr, h03_w),
        (h04_st, h04_pla, h04_d, h04_ab, h04_wb, h04_seg),
        (h08_f, h08_i),
        (h07_y, h07_yi),
        h06,
        (h09, h09_i),
        (h12_s, h12_x),
        h05,
    )


# ============================================================================================ Python side
class _Bus:
    """Slots of the signal bus: consumed outputs and external inputs, float and int separately."""

    def __init__(self) -> None:
        self.f: dict[str, tuple[int, tuple[int, ...]]] = {}
        self.i: dict[str, tuple[int, tuple[int, ...]]] = {}
        self.nf = 0
        self.ni = 0

    def add(self, key: str, dtype: str, shape: tuple[int, ...]) -> None:
        size = int(np.prod(shape, dtype=np.int64)) if shape else 1
        if np.dtype(dtype).kind == "f":
            if key not in self.f:
                self.f[key] = (self.nf, tuple(shape))
                self.nf += size
        else:
            if key not in self.i:
                self.i[key] = (self.ni, tuple(shape))
                self.ni += size

    def slot(self, key: str) -> tuple[str, int, int, tuple[int, ...]]:
        if key in self.f:
            o, s = self.f[key]
            return "f", o, int(np.prod(s, dtype=np.int64)) if s else 1, s
        o, s = self.i[key]
        return "i", o, int(np.prod(s, dtype=np.int64)) if s else 1, s


def _as_tab(codes: list[int], idxs: list[int]) -> tuple[np.ndarray, np.ndarray]:
    return np.asarray(codes, dtype=np.int64), np.asarray(idxs, dtype=np.int64)


class TruthLoopGroup:
    """``FusedGroup`` of the continuous telemetry loop (module docstring)."""

    id = "truth_loop"
    emits_events = True

    def __init__(self, modules: Mapping[str, Any], members: Sequence[str], connections: Sequence[Connection]):
        self.members = tuple(members)
        expected = (
            "env",
            "pilot",
            "fadec",
            "eng",
            "af",
            "util",
            "sens",
            "acq_fadec",
            "acq_dfcc",
            "fcs",
            "avio",
        )
        if self.members != expected:
            raise ContractError(
                f"TruthLoopGroup is written for the member order {expected}, got {self.members}"
            )
        self.m = {mid: modules[mid] for mid in self.members}
        # the compiled loop calls the mixed_ab M07 kernel and copies one plain lane per channel: the Tejas
        # configuration (AD-43 topology option; W2.4a U3 engine-instance lanes are proxy mode, unfused)
        from phalanx.engine.topology import MIXED_AB, topology_of
        from phalanx.sensors.config import engine_of

        if topology_of(self.m["eng"].model) != MIXED_AB:
            raise ContractError("TruthLoopGroup is written for the mixed_ab (Tejas) M07 topology")
        inst = [c for mid in ("acq_fadec", "acq_dfcc") for c in self.m[mid].acq.channels if engine_of(c) >= 0]
        if inst:
            raise ContractError(f"TruthLoopGroup copies plain lanes only; engine-instance lanes {inst[:3]}")
        mset = set(self.members)
        self._edges: dict[str, dict[str, tuple[str, bool]]] = {mid: {} for mid in self.members}
        for c in connections:
            dm, dp = c.dst.rsplit(".", 1)
            if dm in mset:
                self._edges[dm][dp] = (c.src, bool(c.delayed))
        for mid in self.members:
            names = {p.name for p in self.m[mid].ports_in}
            if set(self._edges[mid]) != names:
                raise ContractError(
                    f"{mid}: connections do not cover its inputs {sorted(names - set(self._edges[mid]))}"
                )
        self._build_bus()
        self._build_tables()

    # ------------------------------------------------------------------------------------------ bus
    def _port(self, ref: str):
        mid, name = ref.rsplit(".", 1)
        mod = self.m.get(mid)
        if mod is None:
            return None
        return next(p for p in mod.ports_out if p.name == name)

    def _build_bus(self) -> None:
        bus = _Bus()
        self.ext: list[str] = []  # "member.port" fed from outside the group
        for mid in self.members:
            ins = {p.name: p for p in self.m[mid].ports_in}
            for port, (src, _delayed) in sorted(self._edges[mid].items()):
                sp = self._port(src)
                if sp is None:  # external: a slot keyed by the destination
                    key = f"{mid}.{port}"
                    bus.add(key, ins[port].dtype, ins[port].shape)
                    self.ext.append(key)
                else:
                    bus.add(src, sp.dtype, sp.shape)
        # lane value ports of the in-loop consumers are written by the M13 section
        self.bus = bus
        f_src, f_dst, i_src, i_dst = [], [], [], []
        self._ext_f_cols: list[tuple[str, int, int]] = []  # (key, ext column offset, size)
        self._ext_i_cols: list[tuple[str, int, int]] = []
        cf = ci = 0
        for key in self.ext:
            kind, off, size, _ = bus.slot(key)
            if kind == "f":
                self._ext_f_cols.append((key, cf, size))
                f_src += list(range(cf, cf + size))
                f_dst += list(range(off, off + size))
                cf += size
            else:
                self._ext_i_cols.append((key, ci, size))
                i_src += list(range(ci, ci + size))
                i_dst += list(range(off, off + size))
                ci += size
        self._ext_tabs = tuple(np.asarray(x, dtype=np.int64) for x in (f_src, f_dst, i_src, i_dst))
        self._n_ext_f, self._n_ext_i = cf, ci

    def _source_tab(self, mid: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        """Input port -> (codes, idxs) per element (bus source of each element)."""
        out = {}
        for p in self.m[mid].ports_in:
            src, delayed = self._edges[mid][p.name]
            key = src if self._port(src) is not None else f"{mid}.{p.name}"
            kind, off, size, _ = self.bus.slot(key)
            if self._port(src) is None:
                delayed = False  # the scheduler applies external delays before the block
            code = (SRC_F0 if delayed else SRC_F) if kind == "f" else (SRC_I0 if delayed else SRC_I)
            out[p.name] = _as_tab([code] * size, list(range(off, off + size)))
        return out

    def _probe_inputs(self, mid: str) -> tuple[dict[str, np.ndarray], dict[int, tuple[int, int]]]:
        """Inputs of ``mid`` for one step with unique ids (1-based) and id -> (code, bus index)."""
        src = self._source_tab(mid)
        inputs: dict[str, np.ndarray] = {}
        ids: dict[int, tuple[int, int]] = {}
        nxt = 1
        for p in self.m[mid].ports_in:
            codes, idxs = src[p.name]
            size = codes.size
            vals = np.arange(nxt, nxt + size, dtype=np.int64)
            for k in range(size):
                ids[nxt + k] = (int(codes[k]), int(idxs[k]))
            nxt += size
            arr = vals.reshape((1, *p.shape)) if p.shape else vals.reshape((1,))
            inputs[p.name] = arr.astype(np.dtype(p.dtype))
        return inputs, ids

    @staticmethod
    def _tab_from(packed: np.ndarray, ids: Mapping[int, tuple[int, int]]) -> tuple[np.ndarray, np.ndarray]:
        codes, idxs = [], []
        for v in np.asarray(packed).ravel():
            iv = int(v)
            if iv == 0:
                codes.append(SRC_ZERO)
                idxs.append(0)
            else:
                if iv != v or iv not in ids:
                    raise ContractError(f"packing probe produced a non-id value {v!r}")
                c, i = ids[iv]
                codes.append(c)
                idxs.append(i)
        return _as_tab(codes, idxs)

    def _scatter_tab(
        self, mid: str, ports: Mapping[str, np.ndarray], raw_ids: int, *, from_int: bool = False
    ):
        """(src, dst, flag) arrays for the consumed ports of ``mid`` from probe outputs (values = raw element
        id + 1, 0 = not a copy). ``flag`` = 1: to the int bus (float raw) / to the float bus (int raw)."""
        src, dst, flag = [], [], []
        for p in self.m[mid].ports_out:
            key = f"{mid}.{p.name}"
            if key not in self.bus.f and key not in self.bus.i:
                continue  # not consumed inside the loop
            if p.name not in ports:
                continue
            vals = np.asarray(ports[p.name]).ravel()
            kind, off, size, _ = self.bus.slot(key)
            if vals.size != size:
                raise ContractError(f"{key}: probe size {vals.size} != {size}")
            for k, v in enumerate(vals):
                iv = int(v)
                if iv < 1 or iv > raw_ids or iv != v:
                    raise ContractError(
                        f"{key}: output element {k} is not a copy of one raw element (probe {v})"
                    )
                src.append(iv - 1)
                dst.append(off + k)
                if from_int:
                    flag.append(1 if kind == "f" else 0)
                else:
                    flag.append(1 if kind == "i" else 0)
        return tuple(np.asarray(x, dtype=np.int64) for x in (src, dst, flag))

    def _consumed_any(self, mid: str, raw_names: Sequence[str], probe_out: Mapping[str, np.ndarray]) -> None:
        """Every consumed port of ``mid`` must be covered by ``probe_out`` (else the loop would feed stale
        data)."""
        for p in self.m[mid].ports_out:
            key = f"{mid}.{p.name}"
            if (key in self.bus.f or key in self.bus.i) and p.name not in probe_out:
                raise ContractError(
                    f"{key} is consumed in the loop but not produced by the {raw_names} scatter"
                )

    # ------------------------------------------------------------------------------------------ tables
    def _build_tables(self) -> None:
        from phalanx.acquisition.module import lane_port
        from phalanx.airframe.module import unpack_outputs as af_unpack
        from phalanx.engine.layout import I_NAB as ENG_I_NAB
        from phalanx.engine.layout import NY, NYI, UI_ABEN
        from phalanx.engine.module import _ports_from
        from phalanx.environment import kernel as EK
        from phalanx.fadec.layout import NOF, NOI
        from phalanx.fcs.layout import N_OUT as FCS_N_OUT
        from phalanx.fcs.layout import O_CHST, O_FLOW, O_LAW, O_POS, O_RATE, O_REC
        from phalanx.pilot import kernel as PK
        from phalanx.utilities.jfs import JFS_CRANK

        if JFS_CRANK != _JFS_CRANK:
            raise ContractError("utilities JFS_CRANK changed: update fused._JFS_CRANK")
        m = self.m
        # ---- M03
        src = self._source_tab("env")
        self.g03 = (*src["alt"], *src["hag"], *src["tas"], *src["phase"])
        env = m["env"]
        nout = int(env.bank.n_out)
        cols = {"t_s": EK.O_T, "p_s": EK.O_P, "rho": EK.O_RHO, "a_sound": EK.O_A, "q_spec": EK.O_Q}
        atm_ports = {k: np.array([c + 1]) for k, c in cols.items()}
        we, wbl, wh = env.bank.split(np.arange(1, nout + 1, dtype=np.float64)[None, :])
        self.sc03 = (
            *self._scatter_tab("env", atm_ports, 5),
            *self._scatter_tab("env", {"wind_ned": np.arange(1, 4)}, 3),
            *self._scatter_tab("env", {"turb_vel_body": np.arange(1, 4)}, 3),
            *self._scatter_tab("env", {"turb_rate_body": np.arange(1, 4)}, 3),
            *self._scatter_tab("env", {"w_engine": we[0], "w_bleed_pto": wbl[0], "w_hyd": wh[0]}, nout),
        )
        self._consumed_any(
            "env",
            ["atm", "wind", "turb", "wout"],
            {
                **atm_ports,
                "wind_ned": 1,
                "turb_vel_body": 1,
                "turb_rate_body": 1,
                "w_engine": 1,
                "w_bleed_pto": 1,
                "w_hyd": 1,
            },
        )
        self._nout03 = nout
        # ---- M04 (inputs in the kernel-call order of PilotModule.step_block)
        src = self._source_tab("pilot")
        cs, ix = [], []
        for name in ("alt", "tas", "mach", "vel_ned", "quat", "omega_body", "nz", "wow", "n2"):
            cs += list(src[name][0])
            ix += list(src[name][1])
        self.g04 = _as_tab(cs, ix)
        ne = m["pilot"].n_engines
        self.sc04 = (
            *self._scatter_tab(
                "pilot",
                {"stick_pitch": [PK.O_SP + 1], "stick_roll": [PK.O_SR + 1], "pedal": [PK.O_PED + 1]},
                3,
            ),
            *self._scatter_tab("pilot", {"pla": np.arange(1, ne + 1)}, ne),
            *self._scatter_tab(
                "pilot", {"gear_cmd": [PK.D_GEAR + 1], "airbrake_cmd": [PK.D_BRAKE + 1]}, 2, from_int=True
            ),
            *self._scatter_tab("pilot", {"ab_select": np.arange(1, ne + 1)}, ne, from_int=True),
            *self._scatter_tab("pilot", {"brake_cmd": np.arange(1, 3)}, 2),
        )
        self._consumed_any(
            "pilot",
            ["pilot"],
            {
                k: 1
                for k in (
                    "stick_pitch",
                    "stick_roll",
                    "pedal",
                    "pla",
                    "gear_cmd",
                    "airbrake_cmd",
                    "ab_select",
                    "brake_cmd",
                )
            },
        )
        # ---- M08
        fad = m["fadec"]
        inputs, ids = self._probe_inputs("fadec")
        pla, p0, _at_e, _at_c = fad._exogenous(inputs, 1)
        lanes = fad.pack_lanes(inputs, 1)
        self.g08 = (*self._tab_from(pla, ids), *self._tab_from(p0, ids), *self._tab_from(lanes, ids))
        e8 = fad.n_engines
        nf8 = e8 * NOF
        outf = np.arange(1, nf8 + 1, dtype=np.float64).reshape(1, e8, NOF)
        outi = np.arange(1, e8 * NOI + 1, dtype=np.int64).reshape(1, e8, NOI)
        ports_f = {
            k: v
            for k, v in fad._outputs(outf, np.zeros_like(outi)).items()
            if np.asarray(v).dtype.kind == "f"
        }
        ports_i = {
            k: v
            for k, v in fad._outputs(np.zeros_like(outf), outi).items()
            if np.asarray(v).dtype.kind != "f"
        }
        self.sc08 = (
            *self._scatter_tab(
                "fadec", {k: ports_f[k] for k in ("wf_cmd", "wf_ab_cmd", "a8_cmd", "vg_cmd")}, nf8
            ),
            NOF,
            NOI,
            *self._scatter_tab(
                "fadec",
                {k: ports_i[k] for k in ("ignition", "ab_enable", "active_limiter")},
                e8 * NOI,
                from_int=True,
            ),
        )
        self._consumed_any(
            "fadec",
            ["outf", "outi"],
            {
                k: 1
                for k in (
                    "wf_cmd",
                    "wf_ab_cmd",
                    "a8_cmd",
                    "vg_cmd",
                    "ignition",
                    "ab_enable",
                    "active_limiter",
                )
            },
        )
        self._cap08 = int(fad.capacity)
        # ---- M07
        eng = m["eng"]
        inputs, ids = self._probe_inputs("eng")
        u, ui = eng._pack(inputs, 1)
        cu, iu = self._tab_from(u, ids)
        cui, iui = self._tab_from(ui, ids)
        if np.any((cui == SRC_F) | (cui == SRC_F0)):
            raise ContractError("M07 int kernel input fed from a float port")
        self.g07 = (cu, iu, cui, iui, UI_ABEN, ENG_I_NAB)
        e7 = eng.n_engines
        y = np.arange(1, e7 * NY + 1, dtype=np.float64).reshape(1, e7, NY)
        yi = np.arange(1, e7 * NYI + 1, dtype=np.int64).reshape(1, e7, NYI)
        pf = _ports_from(y, np.zeros_like(yi), None)
        pi = _ports_from(np.zeros_like(y), yi, None)
        fports = {k: v for k, v in pf.items() if np.asarray(v).dtype.kind == "f"}
        iports = {k: v for k, v in pi.items() if np.asarray(v).dtype.kind != "f"}
        self.sc07 = (
            *self._scatter_tab("eng", fports, e7 * NY),
            NY,
            NYI,
            *self._scatter_tab("eng", iports, e7 * NYI, from_int=True),
        )
        self._consumed_any("eng", ["y", "yi"], {**fports, **iports})
        # ---- M06
        af = m["af"]
        inputs, ids = self._probe_inputs("af")
        from phalanx.airframe.module import pack_inputs as af_pack

        self.g06 = self._tab_from(af_pack(inputs, 1, af._n_eng), ids)
        from phalanx.airframe.kernel import N_OUT as AF_N_OUT

        ports = af_unpack(np.arange(1, AF_N_OUT + 1, dtype=np.float64)[None, :])
        self.sc06 = (*self._scatter_tab("af", ports, AF_N_OUT), AF_N_OUT)
        self._consumed_any("af", ["out"], ports)
        # ---- M09
        ut = m["util"]
        inputs, ids = self._probe_inputs("util")
        self.g09 = self._tab_from(ut.pack_inputs(inputs, 1), ids)
        no, noi = self._util_widths(ut)
        pf = ut.unpack_outputs(np.arange(1, no + 1, dtype=np.float64)[None, :], np.zeros((1, noi), np.int64))
        pi = ut.unpack_outputs(np.zeros((1, no)), np.arange(1, noi + 1, dtype=np.int64)[None, :])
        fports = {k: v for k, v in pf.items() if np.asarray(v).dtype.kind == "f"}
        iports = {k: v for k, v in pi.items() if np.asarray(v).dtype.kind != "f"}
        self.sc09 = (
            *self._scatter_tab("util", fports, no),
            no,
            noi,
            *self._scatter_tab("util", iports, noi, from_int=True),
        )
        self._consumed_any("util", ["out", "outi"], {**fports, **iports})
        # ---- M12
        se = m["sens"]
        inputs, ids = self._probe_inputs("sens")
        from phalanx.sensors.module import BIAS_PORT

        U = se._truth_rows(inputs, 1)
        bias = np.asarray(inputs[BIAS_PORT]).reshape(1, se.config.n_ch)
        self.g12 = (*self._tab_from(U, ids), *self._tab_from(bias, ids))
        nch = se.config.n_ch
        ports = se._group_out(np.arange(1, nch + 1, dtype=np.float64)[None, :], np.zeros((1, nch)))
        sports = {k: v for k, v in ports.items() if k.startswith("s_")}
        self.sc12 = (*self._scatter_tab("sens", sports, nch), nch)
        self._consumed_any("sens", ["S"], {**sports, **{k: 1 for k in ports if k.startswith("x_")}})
        for p in se.ports_out:  # X (truth) is never consumed inside the loop
            if p.name.startswith("x_") and (f"sens.{p.name}" in self.bus.f):
                raise ContractError(f"sens.{p.name} (truth) consumed inside the loop")
        # ---- M13 (both lane modules share the M12 source columns and the phase)
        la, lb = m["acq_fadec"], m["acq_dfcc"]
        srcs, phase_tab = {}, None
        for lm in (la, lb):
            st = self._source_tab(lm.id)
            for p in lm.ports_in:
                if p.name == "phase":
                    phase_tab = st[p.name]
                else:
                    srcs[p.name] = st[p.name]
        names = sorted(srcs)
        cs, ix, col_of = [], [], {}
        for nm in names:
            col_of[nm] = len(cs)
            cs += list(srcs[nm][0])
            ix += list(srcs[nm][1])
        self.g13 = (*_as_tab(cs, ix), *phase_tab)
        self._lane_static = []
        for k, lm in enumerate((la, lb)):
            acq = lm.acq
            for di, dom in enumerate(acq.domains):
                ch = np.asarray(dom.channels, dtype=np.int64)
                s_col = np.array([col_of[f"s_{lm._src[c][0]}"] + lm._src[c][1] for c in ch], dtype=np.int64)
                lane_dst = []
                for c in ch:
                    key = f"{lm.id}.{lane_port(acq.channels[c])}"
                    lane_dst.append(self.bus.f[key][0] if key in self.bus.f else -1)
                scale = np.array([lm._conv[c].scale for c in ch], dtype=np.float64)
                offset = np.array([lm._conv[c].offset for c in ch], dtype=np.float64)
                self._lane_static.append(
                    (
                        k,
                        di,
                        ch,
                        s_col,
                        np.ascontiguousarray(acq.P[ch]),
                        np.ascontiguousarray(acq.Q[ch]),
                        np.ascontiguousarray(acq.regime[ch]),
                        np.asarray(lane_dst, dtype=np.int64),
                        int(lm._caps[di]),
                        scale,
                        offset,
                    )
                )
        # ---- M05
        fcs = m["fcs"]
        inputs, ids = self._probe_inputs("fcs")
        self.g05 = self._tab_from(fcs._pack(inputs, 1), ids)
        out = np.arange(1, FCS_N_OUT + 1, dtype=np.float64)[None, :]
        ports = self._fcs_ports(fcs, out)
        self.sc05 = (*self._scatter_tab("fcs", ports, FCS_N_OUT), FCS_N_OUT)
        self._consumed_any("fcs", ["out"], ports)
        self._fcs_cols = (O_POS, O_RATE, O_FLOW, O_LAW, O_CHST, O_REC)
        # ---- M12 avionics: the ADC inputs of the in-loop P0 (first slot of each ADC lane, as the module)
        from phalanx.sensors.avionics import adc as AD
        from phalanx.sensors.avionics.module import _HP, P0_PORT

        av = m["avio"]
        st = self._source_tab("avio")
        fc, fi = [], []
        for name in [lane_port(c) for c in AD.LANE_CHANNELS] + [
            "env_p_s",
            "env_t_s",
            "af_mach",
            "af_tas",
            "af_alpha",
            "af_beta",
            "af_qbar",
        ]:
            codes, idxs = st[name]
            fc.append(int(codes[0]))
            fi.append(int(idxs[0]))
        ic, ii = [], []
        for name in ("util_probe_heat", "pilot_gear_cmd"):
            codes, idxs = st[name]
            if int(codes[0]) not in (SRC_I, SRC_I0):
                raise ContractError(f"avio.{name}: expected an integer bus source")
            ic.append(int(codes[0]))
            ii.append(int(idxs[0]))
        self.gav = (*_as_tab(fc, fi), *_as_tab(ic, ii))
        key = f"avio.{P0_PORT}"
        if key in self.bus.i:
            raise ContractError(f"{key} on the integer bus")
        p0slot = self.bus.f[key][0] if key in self.bus.f else -1
        cfg = av.config
        self.cav = (cfg.adc_p, *cfg.adc_tables, int(_HP), int(p0slot), int(AD.N_LANES))
        for p in av.ports_out:  # only P0 feeds the loop; the other avionics outputs are recorder-only
            if p.name != P0_PORT and (f"avio.{p.name}" in self.bus.f or f"avio.{p.name}" in self.bus.i):
                raise ContractError(f"avio.{p.name} is consumed inside the loop (only {P0_PORT} is fused)")

    @staticmethod
    def _util_widths(ut) -> tuple[int, int]:
        """Raw output widths of the M09 kernel (``utilities_kernel``: NO_FIXED + NOE * n_engines, NOI)."""
        from phalanx.utilities import layout as UL

        return int(UL.NO_FIXED + UL.NOE * ut.n_engines), int(UL.NOI)

    @staticmethod
    def _fcs_ports(fcs, out: np.ndarray) -> dict[str, np.ndarray]:
        """Mirror of ``Fcs.step_block``'s output dict from the raw kernel output rows."""
        from phalanx.fcs.layout import O_CHST, O_FLOW, O_LAW, O_POS, O_RATE, O_REC
        from phalanx.fcs.ports import N_SURF

        res = {
            "surf_pos": out[:, O_POS : O_POS + N_SURF].copy(),
            "surf_rate": out[:, O_RATE : O_RATE + N_SURF].copy(),
            "hyd_flow_demand": out[:, O_FLOW : O_FLOW + 2].copy(),
            "law_state": out[:, O_LAW].astype(np.int64),
            "channel_status": out[:, O_CHST : O_CHST + 4].astype(np.int64),
        }
        for k, name, dtype in fcs._rec:
            res[name] = out[:, O_REC + k].astype(dtype)
        return res

    # ------------------------------------------------------------------------------------------ the block
    def step_block(self, states, ext_inputs, held0, k, dt_truth):
        from phalanx.acquisition.core import collision_mask
        from phalanx.engine.layout import I_NAB
        from phalanx.environment import kernel as EK
        from phalanx.environment.turbulence import TUSTIN_TABLE
        from phalanx.fadec.layout import I_FAULTS, O_FAULTS
        from phalanx.fcs.module import frame_schedule
        from phalanx.pilot import kernel as PK

        m = self.m
        ks = np.asarray(k, dtype=np.int64)
        n = int(ks.size)
        t = truth_step_times_ns(ks)
        t_end = truth_step_times_ns(latest_truth_steps(t) + 1)
        # ---------------------------------------------------------------- bus initial values and external
        # rows
        fb = np.zeros(self.bus.nf)
        ib = np.zeros(self.bus.ni, dtype=np.int64)
        for key, (off, shape) in self.bus.f.items():
            if key in self.ext:
                continue
            fb[off : off + max(1, int(np.prod(shape)))] = np.asarray(held0[key], dtype=np.float64).ravel()
        for key, (off, shape) in self.bus.i.items():
            if key in self.ext:
                continue
            ib[off : off + max(1, int(np.prod(shape)))] = np.asarray(held0[key], dtype=np.int64).ravel()
        ext_f = np.zeros((n, self._n_ext_f))
        for key, c0, size in self._ext_f_cols:
            ext_f[:, c0 : c0 + size] = np.asarray(ext_inputs[key], dtype=np.float64).reshape(n, size)
        ext_i = np.zeros((n, self._n_ext_i), dtype=np.int64)
        for key, c0, size in self._ext_i_cols:
            ext_i[:, c0 : c0 + size] = np.asarray(ext_inputs[key], dtype=np.int64).reshape(n, size)
        # ---------------------------------------------------------------- per-member state, config, exogenous
        st = {mid: states[mid] for mid in self.members}
        env = m["env"]
        se = st["env"]
        turbn, distn = env._noise(int(se["i"][EK.I_TICK]), n)
        b = env.bank
        s03 = (se["f"], se["i"], se["prof"], se["turb"], se["gusts"], se["dist"])
        c03 = (
            env._p,
            env._consts,
            TUSTIN_TABLE,
            env._cat_c,
            b.dims,
            b.offsets,
            b.phi,
            b.lq,
            b.cvec,
            b.gain,
            self._nout03,
        )
        x03 = (t / NS_PER_S, turbn, distn)
        pil = m["pilot"]
        sp = st["pilot"]
        tick0 = int(sp["i"][PK.I_TICK])
        noise04 = pil.stream("remnant").draws(3 * tick0, 3 * n).reshape(n, 3)
        s04 = (
            sp["f"],
            sp["i"],
            sp["buf"],
            sp["plan_t"],
            sp["plan_f"],
            sp["plan_i"],
            sp["aar_off"],
            sp["aar"],
        )
        c04 = (pil.cfg.vector, pil.n_engines, PK.PH_GROUND)
        fad = m["fadec"]
        sf = st["fadec"]
        sched08 = fad.frame_schedule(sf, t)
        if n and int(sched08.count.max(initial=0)) > fad.capacity:
            raise ContractError(f"{fad.id}: frames in one step exceed capacity")
        c = fad.config
        s08 = (sf["f"], sf["i"])
        c08 = (c.p, c.tables, c.cfg, c.dt, self._cap08, fad.n_engines)
        if fad.autothrottle:
            raise ContractError(
                "TruthLoopGroup: the autothrottle configuration is proxy mode (not in this group)"
            )
        x08 = (sched08.count.astype(np.int64), np.zeros(n, dtype=np.int64), np.zeros((n, fad.n_engines)))
        eng = m["eng"]
        sg = st["eng"]
        mdl = eng.model
        nab0 = np.array([int(sg["i"][e, I_NAB]) for e in range(eng.n_engines)], dtype=np.int64)
        z07 = np.zeros((eng.n_engines, n + 1))
        for e, ser in enumerate(eng.serials):
            z07[e] = eng.stream("ab_lightoff", serial=ser).draws(int(nab0[e]), n + 1)
        s07 = (sg["f"], sg["i"], sg["buf"])
        c07 = (mdl.p, mdl.tables, mdl.dt, mdl.n_sub, mdl.n_delay, eng.n_engines)
        x07 = (z07, nab0)
        if abs(dt_truth - mdl.dt) > 1e-15:
            raise ContractError("M07 runs in the 240 Hz rate group")
        af = m["af"]
        sa = st["af"]
        cfa = af.cfg
        s06 = (sa["f"], sa["i"])
        c06 = (cfa.dp, cfa.ap, cfa.tab, cfa.gtab, cfa.ttab, af._n_eng, af._mode)
        ut = m["util"]
        su = st["util"]
        ign = ut._ignition_draw(su["i"])
        from phalanx.utilities import layout as UL

        crank0 = (
            int(su["i"][UL.I_JFS_MODE]) == _JFS_CRANK
            and int(su["i"][UL.I_JFS_DRAWN]) == 0
            and int(su["i"][UL.I_JFS_ATTEMPT]) > 0
        )
        s09 = (su["f"], su["i"])
        c09 = (ut._p, ut._cfg)
        x09 = (float(ign), 1 if crank0 else 0)
        sen = m["sens"]
        ss = st["sens"]
        cfg = sen.config
        s12 = (ss["ef"], ss["ei"], ss["cf"], ss["ci"])
        c12 = (cfg.el_i, cfg.el_p, cfg.ch_i, cfg.ch_p, cfg.tx, cfg.ty, cfg.toff, cfg.cols, cfg.k, cfg.n_sub)
        x12 = (t_end, sen.fault_draws(ss, n))
        # M13 domains: schedule, weights, keyed draws, collision masks for the whole block (module methods)
        doms = []
        dom_meta = []
        lane_states = []
        for lm in (m["acq_fadec"], m["acq_dfcc"]):
            sl = st[lm.id]
            lane_states.append((sl["af"].copy(), sl["ai"].copy(), sl["n_next"].copy()))
        for k_mod, di, ch, s_col, P, Q, reg, lane_dst, cap, scale, offset in self._lane_static:
            lm = (m["acq_fadec"], m["acq_dfcc"])[k_mod]
            acq = lm.acq
            dom = acq.domains[di]
            nn = int(lane_states[k_mod][2][di])
            ssd = samples_for_steps(dom.clock, nn, t, t_end)
            times = ssd.times
            w = (times - t[ssd.step]).astype(np.float64) / (t_end[ssd.step] - t[ssd.step]).astype(np.float64)
            z, u = lm.core._draws(tuple(int(x) for x in ch), ssd.first, times.size)
            coll = collision_mask(dom, times, acq.slot_phase_ns[list(ch)])
            sb = np.zeros(n + 1, dtype=np.int64)
            sb[1:] = np.cumsum(ssd.count)
            ns, nc = times.size, ch.size
            h = (
                np.zeros((ns, nc), dtype=np.int64),
                np.zeros((ns, nc)),
                np.zeros((ns, nc)),
                np.zeros((ns, nc), dtype=np.int64),
                np.zeros((ns, nc), dtype=np.int64),
            )
            doms.append(
                (
                    k_mod,
                    ch,
                    s_col,
                    P,
                    Q,
                    reg,
                    acq.airborne,
                    times,
                    w,
                    np.ascontiguousarray(z),
                    np.ascontiguousarray(u),
                    np.ascontiguousarray(coll),
                    sb,
                    lane_dst,
                    cap,
                    scale,
                    offset,
                    *h,
                    t,
                    t_end,
                )
            )
            dom_meta.append((k_mod, di, ssd))
        s13a = lane_states[0]
        s13b = lane_states[1]
        fcs = m["fcs"]
        sc = st["fcs"]
        from phalanx.fcs.layout import I_NNEXT

        fr, off, _nn = frame_schedule(fcs.cfg, int(sc["i"][I_NNEXT]), t)
        # n_next after each step: the per-step path stores it after every step
        nnext = np.empty(n, dtype=np.int64)
        nn = int(sc["i"][I_NNEXT])
        ssf = samples_for_steps(fcs.cfg.clock, nn, t, t_end)
        nnext[:] = ssf.first_of_step + ssf.count
        s05 = (sc["f"], sc["i"])
        c05 = (fcs.cfg.p, fcs.cfg.tab, fcs.cfg.tf, fcs.cfg.n_sub_act, fcs.cfg.crit_mask)
        x05 = (fr, off, nnext)
        av = m["avio"]
        sav_ = st["avio"]
        ssa = samples_for_steps(av.config.dfcc_clock, int(sav_["dfcc_next"]), t, t_end)
        has_av = np.ascontiguousarray((ssa.count > 0).astype(np.int64))
        s_av = (np.asarray(sav_["adc_f"], dtype=np.float64), np.asarray(sav_["adc_i"], dtype=np.int64))
        res = _truth_loop(
            n,
            t,
            float(dt_truth),
            fb,
            ib,
            *self._ext_tabs,
            ext_f,
            ext_i,
            s03,
            c03,
            self.g03,
            x03,
            self.sc03,
            s04,
            c04,
            self.g04,
            noise04,
            self.sc04,
            s08,
            c08,
            self.g08,
            x08,
            self.sc08,
            s07,
            c07,
            self.g07,
            x07,
            self.sc07,
            s06,
            c06,
            self.g06,
            self.sc06,
            s09,
            c09,
            self.g09,
            x09,
            self.sc09,
            s12,
            c12,
            self.g12,
            x12,
            self.sc12,
            s13a,
            s13b,
            self.g13,
            tuple(doms),
            s05,
            c05,
            self.g05,
            x05,
            self.sc05,
            s_av,
            self.cav,
            self.gav,
            has_av,
        )
        (status, r03, r04, r08, r07, r06, r09, r12, r13, r05, rav, h03, h04, h08, h07, h06, h09, h12, h05) = (
            res
        )
        if status != 0:
            raise FusedFallback(status)
        # ---------------------------------------------------------------- new states (as each module's step)
        new: dict[str, Any] = {}
        new["env"] = {
            "f": r03[0],
            "i": r03[1],
            "prof": se["prof"],
            "turb": r03[2],
            "gusts": r03[3],
            "dist": r03[4],
            "amb": se["amb"],
        }
        np_ = dict(sp)
        np_.update({"f": r04[0], "i": r04[1], "buf": r04[2]})
        new["pilot"] = np_
        g = np.array(sf["g"], dtype=np.int64, copy=True)
        from phalanx.fadec.layout import G_LAST_FRAME_T, G_N_NEXT

        g[G_N_NEXT] = sched08.next_index
        if sched08.times.size:
            g[G_LAST_FRAME_T] = int(sched08.times[-1])
        new["fadec"] = {**st["fadec"], "f": r08[0], "i": r08[1], "g": g}
        y_h, yi_h = h07
        new["eng"] = {
            **st["eng"],  # event-written state (W2.1b fault sizes ``fm``) passes through the steps unchanged
            "f": r07[0],
            "i": r07[1],
            "buf": r07[2],
            "y": y_h[-1].copy(),
            "yi": yi_h[-1].copy(),
        }
        new["af"] = {**st["af"], "f": r06[0], "i": r06[1]}
        new["util"] = {**st["util"], "f": r09[0], "i": r09[1]}
        s_h, x_h = h12
        new["sens"] = {
            "ef": r12[0],
            "ei": r12[1],
            "cf": r12[2],
            "ci": r12[3],
            "xl": np.array(x_h[-1]),
            "tick": np.array(int(ss["tick"]) + n, dtype=np.int64),
        }
        afa, aia, afb, aib = r13
        nn_a = lane_states[0][2].copy()
        nn_b = lane_states[1][2].copy()
        for k_mod, di, ssd in dom_meta:
            (nn_a if k_mod == 0 else nn_b)[di] = ssd.next_index
        new["acq_fadec"] = {"af": afa, "ai": aia, "n_next": nn_a}
        new["acq_dfcc"] = {"af": afb, "ai": aib, "n_next": nn_b}
        new["fcs"] = {**st["fcs"], "f": r05[0], "i": r05[1]}
        # ---------------------------------------------------------------- outputs (module code where it
        # exists)
        outs: dict[str, np.ndarray] = {}

        def put(mid: str, ports: Mapping[str, np.ndarray]) -> None:
            for p in m[mid].ports_out:
                outs[f"{mid}.{p.name}"] = np.ascontiguousarray(ports[p.name])

        atm, wind, tv, tr, wout = h03
        from phalanx.environment import kernel as EK

        we, wbl, wh = env.bank.split(wout)
        put(
            "env",
            {
                "t_s": atm[:, EK.O_T].copy(),
                "p_s": atm[:, EK.O_P].copy(),
                "rho": atm[:, EK.O_RHO].copy(),
                "a_sound": atm[:, EK.O_A].copy(),
                "q_spec": atm[:, EK.O_Q].copy(),
                "wind_ned": wind,
                "turb_vel_body": tv,
                "turb_rate_body": tr,
                "w_engine": np.ascontiguousarray(we),
                "w_bleed_pto": np.ascontiguousarray(wbl),
                "w_hyd": np.ascontiguousarray(wh),
            },
        )
        sticks, pla, disc, ab, wb, seg04 = h04
        e4 = pil.n_engines
        put(
            "pilot",
            {
                "stick_pitch": sticks[:, PK.O_SP].copy(),
                "stick_roll": sticks[:, PK.O_SR].copy(),
                "pedal": sticks[:, PK.O_PED].copy(),
                "pla": pla,
                "gear_cmd": disc[:, PK.D_GEAR].copy(),
                "airbrake_cmd": disc[:, PK.D_BRAKE].copy(),
                "ab_select": ab,
                "brake_cmd": wb,
                "at_engage": np.zeros(n, dtype=np.int64),
                "at_n1_cmd": np.zeros((n, e4)),
            },
        )
        outf, outi = h08
        put("fadec", fad._outputs(outf, outi))
        from phalanx.engine.module import _ports_from

        put("eng", _ports_from(y_h, yi_h, None))
        from phalanx.airframe.module import unpack_outputs as af_unpack

        put("af", af_unpack(h06))
        put("util", ut.unpack_outputs(*h09))
        put("sens", sen._group_out(s_h, x_h))
        for lm in (m["acq_fadec"], m["acq_dfcc"]):
            put(
                lm.id,
                self._lane_outputs(
                    lm,
                    n,
                    [
                        d
                        for d, meta in zip(doms, dom_meta, strict=True)
                        if meta[0] == (0 if lm.id == "acq_fadec" else 1)
                    ],
                    [meta for meta in dom_meta if meta[0] == (0 if lm.id == "acq_fadec" else 1)],
                ),
            )
        put("fcs", self._fcs_ports(fcs, h05))
        # M12 avionics: the module's own block step on the loop's outputs (all its inputs are forward edges
        # from members); its P0 and ADC state must equal the in-loop ADC's, bit for bit
        av_in = {}
        for p in av.ports_in:
            src, delayed = self._edges["avio"][p.name]
            if delayed or src not in outs:
                raise ContractError(
                    f"avio.{p.name} <- {src}: the fused avionics step expects a member output"
                )
            av_in[p.name] = outs[src]
        new_av, out_av = av.step_block(st["avio"], av_in, np.asarray(t, dtype=np.int64), float(dt_truth))
        from phalanx.sensors.avionics.module import P0_PORT

        if not (
            np.array_equal(np.asarray(out_av[P0_PORT]), rav[2])
            and np.array_equal(np.asarray(new_av["adc_f"]), rav[0])
            and np.array_equal(np.asarray(new_av["adc_i"]), rav[1])
        ):
            raise ContractError("fused ADC P0 differs from the avionics module's block step")
        new["avio"] = new_av
        put("avio", out_av)
        # ---------------------------------------------------------------- M08 events, as Fadec.step emits
        # them
        events = []
        if pil.emits_events:  # M04 segment changes (and the post-take-off utility events), as PilotModule
            events += [(t_e, pil.id, ev) for t_e, ev in pil.segment_events(sp, seg04, np.asarray(t))]
        if fad.emits_events:  # as Fadec.step_block (W2.1b: the block's frame schedule and the step index)
            masks = outi[:, :, O_FAULTS]
            prev = np.concatenate([np.asarray(sf["i"])[None, :, I_FAULTS], masks[:-1]], axis=0)
            for j in np.flatnonzero(np.any(masks != prev, axis=1)):
                for ev in fad.fault_events(prev[j], masks[j], int(t[j]), sched08, int(j)):
                    events.append((int(t[j]), fad.id, ev))
        return new, outs, events

    @staticmethod
    def _lane_outputs(lm, n: int, doms: list, metas: list) -> dict[str, np.ndarray]:
        """Mirror of ``LaneAcquisition.step_block``'s lane buffers from the block's domain samples."""
        from phalanx.acquisition.module import lane_port

        acq = lm.acq
        out: dict[str, np.ndarray] = {}
        for d, (_k, di, ssd) in zip(doms, metas, strict=True):
            cap = lm._caps[di]
            ch = d[1]
            h_val, h_flg = d[18], d[20]
            if ssd.count.size and int(ssd.count.max(initial=0)) > cap:
                raise ContractError(f"{lm.id}: more samples in one step than capacity {cap}")
            for j, c in enumerate(ch):
                name = lane_port(acq.channels[c])
                si = lm._conv[c].to_si(h_val[:, j]) if ssd.times.size else np.zeros(0)
                vals = np.zeros((n, cap), dtype=np.float64)
                ts = np.zeros((n, cap), dtype=np.int64)
                qs = np.zeros((n, cap), dtype=np.int64)
                vals[ssd.step, ssd.slot] = si
                ts[ssd.step, ssd.slot] = ssd.times
                qs[ssd.step, ssd.slot] = h_flg[:, j]
                out[name] = vals
                out[f"{name}_t"] = ts
                out[f"{name}_n"] = ssd.count.copy()
                out[f"{name}_first"] = ssd.first_of_step.copy()
                out[f"{name}_q"] = qs
        return out

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "members": list(self.members), "bus_f": self.bus.nf, "bus_i": self.bus.ni}


class FusedFallback(RuntimeError):
    """The fused block met a case its precomputation does not cover (status 1: a JFS ignition draw that was
    not due at the block start; 2: more AB light-off attempts than precomputed draws). Never silently
    wrong."""


_ = (copy,)
