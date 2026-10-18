"""Fused, compiled proxy closed loop: M08 -> M07 -> M12 -> M13 lanes (-> M08, one-frame back-edge) (W2.4a).

The scheduler runs a loop that contains a delayed back-edge step by step through Python (about 1.5 ms per
truth step for 4 engines here; E1 F2). :class:`ProxyLoopGroup` is a ``core.scheduler.FusedGroup`` over the
members ``fadec, eng, sens, acq``: one ``@njit`` function advances a whole block, calling the members' own
compiled kernels (``fadec.kernel.fadec_block``, ``engine.separate.engine_kernel_sf``,
``sensors.kernel.m12_kernel``, ``acquisition.kernel.acq_kernel``) with L = 1 per truth step in the System's
order and with the System's semantics (the FADEC lanes at step k are the M13 samples of step k - 1; M13 lanes
carry no truth). Everything that does not depend on the loop (the FADEC frame schedule, the lane sample
schedule, the keyed noise draws by absolute sample index, the exogenous inputs) is computed before the block.
``tests/integration/test_proxy_loop.py`` proves the fused System bitwise equal to the unfused one (outputs and
states, step and block modes).

The caller (``core.scheduler.System``) passes the external inputs; the group returns every member output port,
so traces, snapshots and the recorder work exactly as with the modules (AD-36). Compiled with ``cache=False``
(it calls kernels from other files: the build rule for fused callers, carry-forward W1.2).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numba import njit

from phalanx.acquisition import kernel as AK
from phalanx.acquisition.module import lane_port
from phalanx.core.sampling import samples_for_steps
from phalanx.core.time import truth_step_times_ns
from phalanx.engine.layout import (
    NU,
    NUI,
    NY,
    NYI,
    U_A8,
    U_BLEED,
    U_H0,
    U_MACH,
    U_PS,
    U_PTO,
    U_Q,
    U_TFUEL,
    U_TS,
    U_VG1,
    U_VG2,
    U_WF,
    U_WFAB,
    U_WFM_D,
    UI_ABEN,
    UI_IGN,
    Y_NAMES,
)
from phalanx.engine.module import _ports_from
from phalanx.engine.separate import engine_kernel_sf
from phalanx.fadec.kernel import fadec_block
from phalanx.fadec.layout import (
    G_LAST_FRAME_T,
    G_N_NEXT,
    NOF,
    NOI,
    O_A8,
    O_AB_EN,
    O_CVG,
    O_FVG,
    O_IGN,
    O_WF,
    O_WF_AB,
)
from phalanx.fadec.ports import LANE_PORTS, LANE_SLOT, N_LANE_SLOTS
from phalanx.sensors.config import dictionary_id, engine_of
from phalanx.sensors.kernel import m12_kernel

MEMBERS = ("fadec", "eng", "sens", "acq")
# the compiled core writes these layout positions by number: pin them (a layout change must fail loudly here)
assert (U_WF, U_WFAB, U_A8, U_VG1, U_VG2) == (0, 1, 2, 3, 4) and (UI_IGN, UI_ABEN) == (0, 1)
assert (O_WF, O_WF_AB, O_A8, O_FVG, O_CVG) == (0, 1, 2, 3, 4) and (O_IGN, O_AB_EN) == (0, 1)
assert NOF == 11 and NOI == 10 and NY == 24 and NYI == 2
_ENG_SIGNAL_Y = {f"eng.{n}": Y_NAMES.index(n) for n in Y_NAMES}


@njit(cache=False, fastmath=False, error_model="numpy", nogil=True)
def _loop_core(
    f8, i8, p8, tb8, cfg8, dt8, pla, p0, at_eng, at_cmd, nfr, lanes_ab, lanes0,
    f7, i7, b7, p7, tb7, uex, uiex, zab, dt7, nsub7, ndel7,
    ef, ei, cf, ci, el_i, el_p, ch_i, ch_p, tx, ty, toff, cols, kvec, bias, t_end, fu, dt12, nsub12,
    u_sig, u_eng,
    af, ai, P, Q, regime, airborne, lane_sens, t_start, s_times, s_w, s_off, s_cnt, phase, z, ud, coll,
    lane_eng, lane_slot, scale, offset,
):  # fmt: skip
    """Advance L truth steps of the proxy loop (pure; see the module docstring).

    Returns new states and per-step raw outputs: outf (L, E, NOF), outi (L, E, NOI), y (L, E, NY), yi (L, E,
    NYI), S, X (L, n_ch), lane samples val/flag (n_s, n_lane) in the block's sample order, and the lane buffer
    of the last step (cap, E, 13).
    """
    L = nfr.shape[0]
    E = f8.shape[0]
    cap = lanes0.shape[0]
    n_ch = cf.shape[0]
    n_u = u_sig.shape[0]
    n_lane = lane_sens.shape[0]
    n_s_total = s_times.shape[0]
    ny = 24
    outf = np.empty((L, E, 11), dtype=np.float64)
    outi = np.empty((L, E, 10), dtype=np.int64)
    Y = np.empty((L, E, ny), dtype=np.float64)
    YI = np.empty((L, E, 2), dtype=np.int64)
    S_all = np.empty((L, n_ch), dtype=np.float64)
    X_all = np.empty((L, n_ch), dtype=np.float64)
    v_all = np.zeros((n_s_total, n_lane), dtype=np.float64)
    q_all = np.zeros((n_s_total, n_lane), dtype=np.int64)
    lanes = np.zeros((1, cap, E, 13), dtype=np.float64)
    for s in range(cap):
        for e in range(E):
            for j in range(13):
                lanes[0, s, e, j] = lanes0[s, e, j]
    U = np.empty((1, n_u), dtype=np.float64)
    S_lane = np.empty((1, n_lane), dtype=np.float64)
    X_lane = np.zeros((1, n_lane), dtype=np.float64)
    step0 = np.zeros(cap, dtype=np.int64)
    for k in range(L):
        # ---- M08 (frames of [t_{k-1}, t_k), lanes = the M13 samples of step k - 1)
        for s in range(cap):
            for e in range(E):
                lanes[0, s, e, 12] = lanes_ab[k, s, e]
        f8, i8, of, oi = fadec_block(
            f8, i8, p8, tb8, cfg8, dt8, pla[k : k + 1], p0[k : k + 1], at_eng[k : k + 1], at_cmd[k : k + 1],
            lanes, nfr[k : k + 1],
        )  # fmt: skip
        for e in range(E):
            for j in range(of.shape[2]):
                outf[k, e, j] = of[0, e, j]
            for j in range(oi.shape[2]):
                outi[k, e, j] = oi[0, e, j]
        # ---- M07 (commands of this step, exogenous inputs)
        u = uex[k : k + 1].copy()
        ui = uiex[k : k + 1].copy()
        for e in range(E):
            u[0, e, 0] = of[0, e, 0]  # U_WF
            u[0, e, 1] = of[0, e, 1]  # U_WFAB
            u[0, e, 2] = of[0, e, 2]  # U_A8
            u[0, e, 3] = of[0, e, 3]  # U_VG1 (FVG)
            u[0, e, 4] = of[0, e, 4]  # U_VG2 (CVG)
            ui[0, e, 0] = oi[0, e, 0]  # UI_IGN
            ui[0, e, 1] = oi[0, e, 1]  # UI_ABEN
        f7, i7, b7, y, yi, _aux = engine_kernel_sf(f7, i7, b7, p7, tb7, u, ui, zab, dt7, nsub7, ndel7, False)
        for e in range(E):
            for j in range(ny):
                Y[k, e, j] = y[0, e, j]
            YI[k, e, 0] = yi[0, e, 0]
            YI[k, e, 1] = yi[0, e, 1]
        # ---- M12 (truth rows from the engine outputs of this step)
        for c in range(n_u):
            U[0, c] = y[0, u_eng[c], u_sig[c]]
        ef, ei, cf, ci, S, X = m12_kernel(
            ef, ei, cf, ci, el_i, el_p, ch_i, ch_p, tx, ty, toff, cols, kvec, U, bias[k : k + 1],
            t_end[k : k + 1], fu[k : k + 1], dt12, nsub12,
        )  # fmt: skip
        for c in range(n_ch):
            S_all[k, c] = S[0, c]
            X_all[k, c] = X[0, c]
        # ---- M13 lanes (samples of [t_k, t_{k+1}))
        for j in range(n_lane):
            S_lane[0, j] = S[0, lane_sens[j]]
        a = s_off[k]
        b = a + s_cnt[k]
        af, ai, _code, val, _tru, flg, _vld = AK.acq_kernel(
            af, ai, P, Q, regime, airborne, S_lane, X_lane, t_start[k : k + 1], t_end[k : k + 1],
            s_times[a:b], step0[: b - a], s_w[a:b], phase[k : k + 1], z[a:b], ud[a:b], coll[a:b],
        )  # fmt: skip
        for s in range(cap):
            for e in range(E):
                for j in range(12):
                    lanes[0, s, e, j] = 0.0
        for r in range(b - a):
            for j in range(n_lane):
                v_all[a + r, j] = val[r, j]
                q_all[a + r, j] = flg[r, j]
                if lane_slot[j] >= 0:
                    lanes[0, r, lane_eng[j], lane_slot[j]] = val[r, j] * scale[j] + offset[j]
    return f8, i8, f7, i7, b7, ef, ei, cf, ci, af, ai, outf, outi, Y, YI, S_all, X_all, v_all, q_all


class ProxyLoopGroup:
    """``FusedGroup`` over ``fadec, eng, sens, acq`` of a proxy System
    (``proxy.system.build_proxy_system``)."""

    id = "proxy_loop"
    members = MEMBERS
    emits_events = False

    def __init__(self, mods: Mapping[str, object]) -> None:
        self.fad = mods["fadec"]
        self.eng = mods["eng"]
        self.sens = mods["sens"]
        self.acq = mods["acq"]
        if self.fad.emits_events:
            raise ValueError("the fused proxy loop runs M08 without fault events (event_target None)")
        sc = self.sens.config
        acq = self.acq.acq
        if len(acq.domains) != 1:
            raise ValueError("the fused proxy loop expects one lane clock domain")
        self.dom = acq.domains[0]
        self.e = self.fad.n_engines
        # M12 truth columns <- engine outputs (signal, engine)
        u_sig, u_eng = [], []
        for spec in sc.inputs:
            yidx = _ENG_SIGNAL_Y.get(spec.signal)
            if yidx is None:
                raise ValueError(
                    f"the fused proxy loop feeds M12 from M07 only; {spec.signal} is not an eng port"
                )
            for j in range(spec.size):
                u_sig.append(yidx)
                u_eng.append(j)
        self.u_sig = np.asarray(u_sig, dtype=np.int64)
        self.u_eng = np.asarray(u_eng, dtype=np.int64)
        # lane channel -> (M12 index, engine, M08 lane slot, EU->SI)
        slot_of = {cid: LANE_SLOT[name] for name, cid, _u in LANE_PORTS}
        self.lane_sens = np.asarray(acq.sensor_index, dtype=np.int64)
        self.lane_eng = np.asarray([max(engine_of(c), 0) for c in acq.channels], dtype=np.int64)
        self.lane_slot = np.asarray([slot_of.get(dictionary_id(c), -1) for c in acq.channels], dtype=np.int64)
        self.scale = np.asarray([cv.scale for cv in self.acq._conv], dtype=np.float64)
        self.offset = np.asarray([cv.offset for cv in self.acq._conv], dtype=np.float64)
        self.cap_acq = self.acq._caps[0]
        self.cap_fad = self.fad.capacity
        if self.cap_acq != self.cap_fad:
            raise ValueError("lane capacity differs between M13 and M08")
        self._lane_groups = list(self.acq._lanes)

    # ------------------------------------------------------------------------------------------ helpers
    def _ext(self, ext: Mapping[str, np.ndarray], n: int):
        e = self.e
        g = lambda k: np.asarray(ext[k])  # noqa: E731
        pla = np.ascontiguousarray(g("fadec.pla").reshape(n, e), dtype=np.float64)
        p0 = np.ascontiguousarray(g("fadec.p0").reshape(n), dtype=np.float64)
        at_eng = np.ascontiguousarray(g("fadec.at_engage").reshape(n), dtype=np.int64)
        at_cmd = np.ascontiguousarray(g("fadec.at_n1_cmd").reshape(n, e), dtype=np.float64)
        ab = np.ascontiguousarray(g("fadec.ab_lit").reshape(n, self.cap_fad, e), dtype=np.float64)
        uex = np.zeros((n, e, NU))
        for col, name in ((U_TS, "t_s"), (U_PS, "p_s"), (U_Q, "q_spec"), (U_MACH, "mach")):
            uex[:, :, col] = g(f"eng.{name}").reshape(n, 1)
        uex[:, :, U_WFM_D : U_WFM_D + 5] = g("eng.w_engine")
        uex[:, :, U_BLEED] = g("eng.bleed_extract")
        uex[:, :, U_PTO] = g("eng.pto_power")
        uex[:, :, U_TFUEL] = g("eng.fuel_inlet_t")
        uex[:, :, U_H0 : U_H0 + 10] = g("eng.health")
        uiex = np.zeros((n, e, NUI), dtype=np.int64)
        bias = np.ascontiguousarray(g("sens.health_sensor_bias").reshape(n, self.sens.config.n_ch))
        phase = np.ascontiguousarray(g("acq.phase").reshape(n), dtype=np.int64)
        return pla, p0, at_eng, at_cmd, ab, uex, uiex, bias, phase

    def _lanes0(self, held0: Mapping[str, np.ndarray]) -> np.ndarray:
        """Lane buffer seen by M08 at the first step of the block: the M13 lane ports held at block start."""
        lanes = np.zeros((self.cap_fad, self.e, N_LANE_SLOTS))
        for name, cid, _u in LANE_PORTS:
            if cid == "ENG.AB_LIT":
                continue
            v = np.asarray(held0[f"acq.{lane_port(cid)}"], dtype=np.float64).reshape(self.cap_fad, self.e)
            lanes[:, :, LANE_SLOT[name]] = v
        return lanes

    # ------------------------------------------------------------------------------------------ FusedGroup
    def step_block(self, states, ext, held0, k, dt_truth):
        ks = np.asarray(k, dtype=np.int64)
        n = int(ks.size)
        t = truth_step_times_ns(ks)
        t_end = truth_step_times_ns(ks + 1)
        pla, p0, at_eng, at_cmd, ab, uex, uiex, bias, phase = self._ext(ext, n)
        sf, se, ss, sa = states["fadec"], states["eng"], states["sens"], states["acq"]
        # M08 frame schedule ([t_{k-1}, t_k) per step) and M13 lane samples ([t_k, t_{k+1}) per step)
        sched = self.fad.frame_schedule(sf, t)
        nfr = np.ascontiguousarray(sched.count, dtype=np.int64)
        smp = samples_for_steps(self.dom.clock, int(sa["n_next"][0]), t, t_end)
        n_s = int(smp.times.size)
        chans = self.dom.channels
        z, ud = self.acq.core._draws(chans, smp.first, n_s)
        w = (smp.times - t[smp.step]).astype(np.float64) / (t_end[smp.step] - t[smp.step]).astype(np.float64)
        s_off = np.ascontiguousarray(np.cumsum(smp.count) - smp.count, dtype=np.int64)
        coll = np.zeros((n_s, len(chans)), dtype=np.int64)
        acfg = self.acq.acq
        idx = np.asarray(chans, dtype=np.int64)
        m = self.eng.model
        fc = self.fad.config
        scfg = self.sens.config
        fu = np.zeros((n, scfg.n_ch))
        (f8, i8, f7, i7, b7, ef, ei, cf, ci, af, ai, outf, outi, Y, YI, S, X, v_all, q_all) = _loop_core(
            sf["f"], sf["i"], fc.p, fc.tables, fc.cfg, fc.dt, pla, p0, at_eng, at_cmd, nfr, ab,
            self._lanes0(held0),
            se["f"], se["i"], se["buf"], m.p, m.tables, uex, uiex, np.zeros((self.e, 2)), m.dt, m.n_sub,
            m.n_delay,
            ss["ef"], ss["ei"], ss["cf"], ss["ci"], scfg.el_i, scfg.el_p, scfg.ch_i, scfg.ch_p, scfg.tx,
            scfg.ty, scfg.toff, scfg.cols, scfg.k, bias, t_end, fu, dt_truth, scfg.n_sub,
            self.u_sig, self.u_eng,
            np.ascontiguousarray(sa["af"][idx]), np.ascontiguousarray(sa["ai"][idx]),
            np.ascontiguousarray(acfg.P[idx]), np.ascontiguousarray(acfg.Q[idx]),
            np.ascontiguousarray(acfg.regime[idx]), acfg.airborne,
            np.ascontiguousarray(self.lane_sens[idx]), t, smp.times, w, s_off,
            np.ascontiguousarray(smp.count),
            phase, np.ascontiguousarray(z), np.ascontiguousarray(ud), coll,
            np.ascontiguousarray(self.lane_eng[idx]), np.ascontiguousarray(self.lane_slot[idx]),
            np.ascontiguousarray(self.scale[idx]), np.ascontiguousarray(self.offset[idx]),
        )  # fmt: skip
        # ---- states
        g = np.array(sf["g"], dtype=np.int64, copy=True)
        g[G_N_NEXT] = sched.next_index
        if sched.times.size:
            g[G_LAST_FRAME_T] = int(sched.times[-1])
        af_all = np.array(sa["af"], copy=True)
        ai_all = np.array(sa["ai"], copy=True)
        af_all[idx] = af
        ai_all[idx] = ai
        new = {
            "fadec": {"f": f8, "i": i8, "g": g},
            # fm: per-mode engine-fault sizes (W2.1b eng.fault_inject); events change it, blocks carry it
            "eng": {
                "f": f7, "i": i7, "buf": b7, "y": Y[-1].copy(), "yi": YI[-1].copy(), "fm": np.array(se["fm"]),
            },
            "sens": {
                "ef": ef, "ei": ei, "cf": cf, "ci": ci, "xl": np.array(X[-1]),
                "tick": np.array(int(ss["tick"]) + n, dtype=np.int64),
            },
            "acq": {"af": af_all, "ai": ai_all, "n_next": np.array([smp.next_index], dtype=np.int64)},
        }  # fmt: skip
        # ---- outputs (the members' port semantics)
        outs: dict[str, np.ndarray] = {}
        for kname, v in self.fad._outputs(outf, outi).items():
            outs[f"fadec.{kname}"] = v
        for kname, v in _ports_from(Y, YI, None).items():
            outs[f"eng.{kname}"] = v
        for kname, v in self.sens._group_out(S, X).items():
            outs[f"sens.{kname}"] = v
        cap = self.cap_acq
        pos = {c: j for j, c in enumerate(chans)}
        for did, members in self._lane_groups:
            name = lane_port(did)
            vals = np.zeros((n, cap, len(members)))
            qs = np.zeros((n, cap, len(members)), dtype=np.int64)
            for jj, c in enumerate(members):
                col = pos[c]
                vals[smp.step, smp.slot, jj] = v_all[:, col] * self.scale[c] + self.offset[c]
                qs[smp.step, smp.slot, jj] = q_all[:, col]
            ts = np.zeros((n, cap), dtype=np.int64)
            ts[smp.step, smp.slot] = smp.times
            if engine_of(acfg.channels[members[0]]) < 0:
                vals, qs = vals[:, :, 0], qs[:, :, 0]
            outs[f"acq.{name}"] = vals
            outs[f"acq.{name}_t"] = ts
            outs[f"acq.{name}_n"] = smp.count.copy()
            outs[f"acq.{name}_first"] = smp.first_of_step.copy()
            outs[f"acq.{name}_q"] = qs
        return new, outs


__all__ = ["MEMBERS", "ProxyLoopGroup"]
