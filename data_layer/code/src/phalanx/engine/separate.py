"""M07 topology option ``separate_fixed`` (AD-43): separate-flow, high-bypass, fixed-nozzle, non-afterburning
two-spool turbofan, for the DASHlink proxy (four-engine regional jet; architecture §14.3, AD-33, AD-43).

**Same component method as ``mixed_ab``** (AD-43 "same method structure"): the 0-D component-level model
(the same inlet, fan/HPC compressor maps, combustor, HPT/LPT turbine maps, humid-air thermodynamics and map
scaling of ``kernel.py``), the same stochastic dynamic shell (inter-component volume pressures, two rotor
ODEs, combustor energy-storage lag, actuators, heat soak, tip clearance, oil), the same process-disturbance
inputs entering the dynamics (``env.w_engine``, AD-32/AD-46) and the same discrete processes (lean
blow-out/relight, surge event model). What changes is the topology, which drives the bypass/core dynamics and
the EGT-N1 coupling (AD-43):

    inlet -> fan -> V21 (fan exit + bypass duct) -> {HPC, fixed bypass nozzle A18}
    HPC -> V3 (HPC exit + combustor) -> HPT (NGV-choked W41, T41 lag) -> V45 -> LPT -> V5 (LPT exit duct)
    -> fixed core nozzle A8

- **Two nozzles, no mixer, no afterburner, fixed nozzles.** Each stream expands through its own fixed
  convergent nozzle (isentropic flow function, unchoked or choked; fully expanded gross thrust with the same
  ``cfg`` convention as ``mixed_ab``, A-W1.3a-19). The mixer volume state ``p6`` has no physical role here: it
  relaxes to the ambient static pressure (1 s) so the steady solver's Jacobian stays nonsingular; the AB fuel
  state decays to zero; the nozzle-area state is fixed (its derivative is zero, the command is ignored).
- **LP spool with a fan gearbox.** ``x[n1]`` is the **fan** speed (the measured N1). The LP turbine turns at
  ``gear_ratio * n1``; the turbine power reaches the fan through the gearbox efficiency ``eta_gearbox``; the
  inertia ``i_lp`` is the whole LP spool **reflected to the fan shaft** (I_fan + G^2 I_LPT). A direct-drive
  fan is ``gear_ratio = 1``, ``eta_gearbox = 1``.
- **No separate booster (LP compressor) component** (PROXY A-W2.4a-3): the core stream sees the fan pressure
  ratio, and any booster pressure rise is lumped into the HPC map at design, so the core-side LP pressure rise
  does not vary with N1 separately from the fan. The exposing test compares the steady N1c(N2c) operating line
  with the round-2 [MEASURED] DASHlink relation.

The parameter vector is the ``mixed_ab`` layout (``layout.P_NAMES``) followed by ``SF_EXTRA``; the mixer
coefficients of the base layout (k13, eps13, k5, eps5, r6_mix, wc6_des) are unused here. State, input,
output and diagnostics layouts are unchanged, so ``EngineModule``, ``sim`` and ``steady`` drive this kernel
through ``topology.kernel_functions``. Numerics are those of ``kernel._tick`` (Heun sub-steps, stiffness-based
count, error-controlled refinement); complex-step safe (comparisons on ``.real``; no abs/min/max on
derivative-carrying values); the NumPy reference is the same source uncompiled (``py_func``), bitwise.
"""

from __future__ import annotations

import numpy as np
from numba import njit

from .kernel import (
    _JIT,
    N_FLOOR,
    P_FLOOR,
    P_STD,
    RPM_PER_RADS,
    T_CEIL,
    T_FLOOR,
    T_STD,
    _vg_dev,
    combustor_exit_temperature,
    inlet,
    pressure_error,
)
from .layout import (
    A_ABHEAT,
    A_BEYOND,
    A_BPR,
    A_CLEAR,
    A_ETAFAN,
    A_ETAHPC,
    A_ETAHPT,
    A_ETALPT,
    A_FAR4,
    A_FG,
    A_FN,
    A_LAM,
    A_N1C,
    A_N2C,
    A_OILP,
    A_P2,
    A_P4,
    A_P5,
    A_P7,
    A_P25,
    A_PRFAN,
    A_PRHPC,
    A_PRHPT,
    A_PRLPT,
    A_PS3,
    A_PWEXT,
    A_PWFAN,
    A_PWHPC,
    A_PWHPT,
    A_PWLPT,
    A_QSOAK,
    A_SMFAN,
    A_SMHPC,
    A_T2,
    A_T3,
    A_T4,
    A_T5,
    A_T6,
    A_T7,
    A_T21,
    A_T25,
    A_T41AD,
    A_T45,
    A_V0,
    A_VIB0,
    A_VIB1,
    A_VIB2,
    A_W2,
    A_W2C,
    A_W5MIX,
    A_W8,
    A_W13,
    A_W25,
    A_W41,
    A_WBLEED,
    A_WFL,
    A_WLPT,
    A_WROT,
    AB_OFF,
    F_FLAME_TIMER,
    F_SURGE_TIMER,
    I_AB,
    I_BUFPOS,
    I_FLAME,
    I_NSURGE,
    I_SURGE,
    I_TICK,
    INL_P2,
    INL_PS,
    INL_T2,
    INL_V0,
    INL_WAR,
    INL_WFL,
    NAUX,
    NINL,
    NP,
    NX,
    NY,
    NYI,
    P_A3,
    P_CCASE,
    P_CD8,
    P_CFG,
    P_CMET,
    P_CNGV,
    P_COIL,
    P_DPB,
    P_DPCD,
    P_ETAB,
    P_ETAM,
    P_FARLBO,
    P_FARLIGHT,
    P_FROT,
    P_FST,
    P_GCLR_C,
    P_GCLR_M,
    P_GCLR_W,
    P_GTURB,
    P_HAMET,
    P_IHP,
    P_ILP,
    P_INTTOL,
    P_KECVG,
    P_KEFF,
    P_KEFVG,
    P_KETACLR,
    P_KWCVG,
    P_KWFVG,
    P_LHV,
    P_N1CDES,
    P_N1DES,
    P_N2CDES,
    P_N2DES,
    P_N2OILK,
    P_NAMES,
    P_NLBO,
    P_NSUBMAX,
    P_OILVISC,
    P_P3LIGHT,
    P_PACC,
    P_PLBO,
    P_POILREG,
    P_PRCH_HPT,
    P_PRCH_LPT,
    P_QOIL,
    P_SEFF_FAN,
    P_SEFF_HPC,
    P_SEFF_HPT,
    P_SEFF_LPT,
    P_SMTRIG,
    P_SNC_FAN,
    P_SNC_HPC,
    P_SNP_HPT,
    P_SNP_LPT,
    P_SPR_FAN,
    P_SPR_HPC,
    P_SPR_HPT,
    P_SPR_LPT,
    P_STAB,
    P_STALL_SLOPE,
    P_SURGE_CMIN,
    P_SURGE_EFF,
    P_SURGE_TREC,
    P_SWC_FAN,
    P_SWC_HPC,
    P_SWP_HPT,
    P_SWP_LPT,
    P_TAUCASE,
    P_TAUCOMB,
    P_TAUFMV,
    P_TAUVG,
    P_TAUWFAB,
    P_TCREF,
    P_TIGN,
    P_TLBO,
    P_TMREF,
    P_TOILREF,
    P_UAOIL_AIR,
    P_UAOIL_FUEL,
    P_V3,
    P_V5,
    P_V21,
    P_V45,
    P_VGMAX,
    P_VGMIN,
    P_VGRATE,
    P_VGSAT,
    P_VIBEXP,
    P_VIBK1,
    P_VIBK2,
    P_VIBK3,
    P_W2DES,
    P_W41DES,
    P_WC3DES,
    P_WFDES,
    P_WFMINFL,
    PTO_W_FLOOR,
    U_BLEED,
    U_H0,
    U_MACH,
    U_PS,
    U_PTO,
    U_Q,
    U_TFUEL,
    U_TS,
    U_VG1,
    U_WCE,
    U_WF,
    U_WFF,
    U_WFM_D,
    U_WIR,
    U_WSL,
    UI_IGN,
    X_A8,
    X_N1,
    X_N2,
    X_P3,
    X_P5,
    X_P6,
    X_P21,
    X_P45,
    X_T41,
    X_TC,
    X_TM,
    X_TOIL,
    X_VG1,
    X_WFAB,
    X_WFM,
    Y_A8,
    Y_BLP3,
    Y_BLT3,
    Y_FN,
    Y_N1,
    Y_N2,
    Y_OILP,
    Y_OILT,
    Y_P2,
    Y_P5,
    Y_PS3,
    Y_SM,
    Y_T2,
    Y_T3,
    Y_T5,
    Y_T25,
    Y_VG1,
    Y_VG2,
    Y_VIB0,
    Y_VIB1,
    Y_VIB2,
    Y_W2,
    Y_WF,
    Y_WFAB,
    YI_AB,
    YI_FLAME,
)
from .maps import compressor_lookup, flow_function, interp1, turbine_lookup, turbine_unchoke
from .thermo import compress, expand, gamma_of, gas_r, h_cp, phi_cp, t_from_h, t_from_phi

TOPOLOGY = "separate_fixed"
#: parameters of the separate-flow topology appended to ``layout.P_NAMES``
SF_EXTRA = (
    "a18",  # bypass (fan) nozzle geometric throat area, m^2 (derived at design)
    "cd18",  # bypass nozzle discharge coefficient
    "dp_bypass_duct",  # bypass-duct total-pressure loss, fraction of P21
    "gear_ratio",  # LP-turbine speed / fan speed (1 = direct drive)
    "eta_gearbox",  # fan gearbox efficiency (1 = direct drive)
    "p6_relax_tau",  # s, relaxation of the unused mixer-volume state to ambient (numerical, no physics)
    "wc21_des",  # fan-exit corrected flow W2 sqrt(T21) / P21 at design (duct losses scale with its square)
    # PROTOTYPE (MF1, not adopted; A-W2.4a-18): share of the fan_face disturbance that acts on the fan flow
    # capacity. 1 = AD-46 as specified (flow capacity and efficiency); 0 = efficiency only, i.e. a pure LP
    # shaft-torque path (AD-46's "second LP-specific path"). The default 1 leaves the kernel bitwise
    # unchanged.
    "fan_face_flow_share",
    # Off-design map modifiers (W2.4a-2 steady identification on 687-CAL; A-W2.4a-21): the corrected flow and
    # the efficiency of the fan and HPC maps are multiplied below design corrected speed by
    # 1 + a (1 - Nc/Nc_des)^k (1 at and above design, so the design point and its anchors are unchanged).
    # a = 0 leaves the kernel bitwise unchanged.
    "fan_wc_mod_a",
    "fan_wc_mod_k",
    "fan_eff_mod_a",
    "fan_eff_mod_k",
    "hpc_wc_mod_a",
    "hpc_wc_mod_k",
    "hpc_eff_mod_a",
    "hpc_eff_mod_k",
    # Reynolds-number effect (W2.4a-2; the TP-1034 F100 model method): the loss (1 - eta) of every component
    # grows by RNI^-n when the inlet Reynolds-number index RNI = delta2 theta2^-1.2 is below 1 (SLS ISA = 1,
    # so the design point is unchanged). n = 0 leaves the kernel bitwise unchanged.
    "rni_exp",
    # Off-design speed-line modifiers (W2.4a-2; A-W2.4a-21): the fan and HPC maps are read at the corrected
    # speed Nc (1 + a (1 - Nc/Nc_des)^k) below design (the low-pressure-ratio fan and core compressor of the
    # proxy behave at part speed like the scaled generic map at a higher speed line), so flow, pressure ratio,
    # efficiency and the stall line move together. a = 0 leaves the kernel bitwise unchanged.
    "fan_nc_mod_a",
    "fan_nc_mod_k",
    "hpc_nc_mod_a",
    "hpc_nc_mod_k",
    # PROTOTYPE (W2.4a-2 stage 3, A-W2.4a-23; not adopted): gas-path thermal storage between the LPT exit and
    # the T5 station (exhaust duct, struts, probe rakes). A heat-storage node X follows the LPT-exit gas
    # temperature with time constant tau (dX/dt = (T5 - X) / tau) and the station sees T5 - kappa (T5 - X): a
    # lag-lead from the gas to the station (a pure first-order lag at kappa = 1), unity at steady state, no
    # effect on the cycle (the storage is downstream of the LPT). It uses the separate-flow topology's unused
    # mixer-volume state slot (no layout change). tau = 0 (default) leaves the kernel bitwise unchanged.
    "gp_lag_tau",
    "gp_lag_kappa",
)
SF_P_NAMES = (*P_NAMES, *SF_EXTRA)
SF_PI = {n: j for j, n in enumerate(SF_P_NAMES)}
P_A18, P_CD18, P_DPBYP, P_GEAR, P_ETAGB, P_P6TAU, P_WC21DES, P_FFSHARE = range(NP, NP + 8)
P_FWA, P_FWK, P_FEA, P_FEK, P_CWA, P_CWK, P_CEA, P_CEK = range(NP + 8, NP + 16)
P_RNI = NP + 16
P_FNA, P_FNK, P_CNA, P_CNK = range(NP + 17, NP + 21)
P_GPTAU, P_GPK = NP + 21, NP + 22
NP_SF = len(SF_P_NAMES)
assert SF_PI["a18"] == P_A18 and SF_PI["p6_relax_tau"] == P_P6TAU and SF_PI["hpc_eff_mod_k"] == P_CEK
assert SF_PI["rni_exp"] == P_RNI and SF_PI["hpc_nc_mod_k"] == P_CNK and SF_PI["gp_lag_kappa"] == P_GPK


@njit(**_JIT)
def map_modifier(frac, a, k):
    """Off-design map modifier ``1 + a (1 - frac)^k`` below design corrected speed (frac < 1), 1 at and above
    it. Complex-safe (the branch is on the real part); a = 0 returns exactly 1."""
    lo = 1.0 - frac
    if lo.real <= 0.0:
        return 1.0 + 0.0 * lo
    return 1.0 + a * lo**k


@njit(**_JIT)
def nozzle_flow(pt, tt, f, war, ps0, area, cd, cfg, B):
    """Fixed convergent nozzle: (mass flow, fully expanded gross thrust, d ln W / d pt at fixed ps0 [real]).

    W = cd A pt psi(pt/ps0, gamma) / sqrt(R tt); Fg = cfg W sqrt(2 (h_t - h_9)) with T9 isentropic to ps0
    (the ``mixed_ab`` nozzle convention, A-W1.3a-19). The slope is the stiffness input of the volume upstream.
    """
    r = gas_r(f, war, B)
    g = gamma_of(tt, f, war, B)
    pr = pt / ps0
    if pr.real < 1.0 + 1e-9:
        pr = 1.0 + 1e-9 + 0.0 * pr
    psi = flow_function(pr, g)
    w = area * cd * pt * psi / np.sqrt(r * tt)
    phi_t, _ = phi_cp(tt, f, war, B)
    t9 = t_from_phi(phi_t - r * np.log(pr), f, war, B, tt * pr ** (-(g - 1.0) / g))
    ht, _ = h_cp(tt, f, war, B)
    h9, _ = h_cp(t9, f, war, B)
    dh = ht - h9
    if dh.real < 0.0:
        dh = 0.0 * dh
    fg = cfg * w * np.sqrt(2.0 * dh)
    # stiffness slope on real parts: d ln W / d pt = 1/pt + (d ln psi / d PR) / ps0 (0 when choked)
    gr = g.real
    prr = pr.real
    prc = ((gr + 1.0) * 0.5) ** (gr / (gr - 1.0))
    dlnpsi = 0.0
    if prr < prc:
        x = 1.0 / prr
        a = 2.0 / gr
        b = (gr + 1.0) / gr
        psi2 = 2.0 * gr / (gr - 1.0) * (x**a - x**b)
        if psi2 < 1e-12:
            psi2 = 1e-12
        dlnpsi = x * x * gr / (gr - 1.0) * (b * x ** (b - 1.0) - a * x ** (a - 1.0)) / psi2
    slope = 1.0 / pt.real + dlnpsi / ps0.real
    return w, fg, slope


@njit(**_JIT)
def deriv_sf(x, ab_state, flame, surge, surge_timer, inl, ue, p, tb, dx, aux):
    """Continuous dynamics of one separate-flow engine; fills ``aux`` (same layout as ``kernel.deriv``).

    ``ab_state`` is accepted for signature parity and ignored (no afterburner)."""
    B = tb.thermo
    # ---- guarded states (numerical floors on the real part; inactive in normal operation)
    n1 = x[X_N1]
    if n1.real < N_FLOOR:
        n1 = N_FLOOR + 0.0 * n1
    n2 = x[X_N2]
    if n2.real < N_FLOOR:
        n2 = N_FLOOR + 0.0 * n2
    p21 = x[X_P21]
    if p21.real < P_FLOOR:
        p21 = P_FLOOR + 0.0 * p21
    p3 = x[X_P3]
    if p3.real < P_FLOOR:
        p3 = P_FLOOR + 0.0 * p3
    p45 = x[X_P45]
    if p45.real < P_FLOOR:
        p45 = P_FLOOR + 0.0 * p45
    p5 = x[X_P5]
    if p5.real < P_FLOOR:
        p5 = P_FLOOR + 0.0 * p5
    t41 = x[X_T41]
    if t41.real < T_FLOOR:
        t41 = T_FLOOR + 0.0 * t41
    if t41.real > T_CEIL:
        t41 = T_CEIL + 0.0 * t41
    t2 = inl[INL_T2]
    p2 = inl[INL_P2]
    war = inl[INL_WAR]
    ps0 = inl[INL_PS]
    z0 = 0.0 * war
    h = ue[U_H0:]
    # ---- fan (whole fan flow on one map; core and bypass streams leave at the same fan PR, PROXY A-W2.4a-3)
    th2 = t2 / T_STD
    n1c = n1 * RPM_PER_RADS / np.sqrt(th2)
    n1c_frac = n1c / p[P_N1CDES]
    pr_fan = p21 / p2
    # Reynolds-number index at the engine inlet and the loss growth factor (1 at RNI >= 1 or n = 0)
    rni = (p2 / P_STD) * th2 ** (-1.2)
    rfac = 1.0 + 0.0 * rni
    if rni.real < 1.0:
        rfac = rni ** (-p[P_RNI])
    wcm, em, prst, _ = compressor_lookup(
        n1c / p[P_SNC_FAN] * map_modifier(n1c_frac, p[P_FNA], p[P_FNK]),
        (pr_fan - 1.0) / p[P_SPR_FAN] + 1.0,
        tb.fan_nc,
        tb.fan_wc,
        tb.fan_pr,
        tb.fan_eff,
        p[P_STALL_SLOPE],
    )
    dvg1 = _vg_dev(x[X_VG1] - interp1(tb.fvg_x, tb.fvg_y, n1c_frac), p[P_VGSAT])
    # fan-face distortion process disturbance (AD-46, the LP-spool-specific path), as in mixed_ab
    wff = ue[U_WFF]
    w2c = (
        wcm
        * p[P_SWC_FAN]
        * map_modifier(n1c_frac, p[P_FWA], p[P_FWK])
        * (1.0 - p[P_KWFVG] * dvg1)
        * (1.0 + h[1])
        * (1.0 - p[P_FFSHARE] * wff)
    )
    eta_fan = (
        em
        * p[P_SEFF_FAN]
        * map_modifier(n1c_frac, p[P_FEA], p[P_FEK])
        * (1.0 - p[P_KEFVG] * dvg1 * dvg1)
        * (1.0 + h[0])
        * (1.0 - p[P_KEFF] * wff)
    )
    eta_fan = eta_fan - (1.0 - eta_fan) * (rfac - 1.0)
    w2 = w2c * (p2 / P_STD) / np.sqrt(th2)
    cs = 1.0 + 0.0 * w2
    if surge == 1:
        frac = surge_timer / p[P_SURGE_TREC]
        if frac.real > 1.0:
            frac = 1.0 + 0.0 * frac
        cs = p[P_SURGE_CMIN] + (1.0 - p[P_SURGE_CMIN]) * frac * frac
        w2 = w2 * cs
    t21, dh_fan = compress(t2, pr_fan, eta_fan, z0, war, B)
    sm_fan = (1.0 + (prst - 1.0) * p[P_SPR_FAN]) / pr_fan - 1.0
    pw_fan = w2 * dh_fan
    # ---- duct losses scale with the dynamic head: (fan-exit corrected flow / design)^2 (both streams)
    q21 = w2 * np.sqrt(t21) / p21 / p[P_WC21DES]
    q21sq = q21 * q21
    # ---- HPC
    p25 = p21 * (1.0 - p[P_DPCD] * q21sq)
    t25 = t21
    th25 = t25 / T_STD
    n2c = n2 * RPM_PER_RADS / np.sqrt(th25)
    n2c_frac = n2c / p[P_N2CDES]
    pr_hpc = p3 / p25
    wcm2, em2, prst2, beyond = compressor_lookup(
        n2c / p[P_SNC_HPC] * map_modifier(n2c_frac, p[P_CNA], p[P_CNK]),
        (pr_hpc - 1.0) / p[P_SPR_HPC] + 1.0,
        tb.hpc_nc,
        tb.hpc_wc,
        tb.hpc_pr,
        tb.hpc_eff,
        p[P_STALL_SLOPE],
    )
    dvg2 = _vg_dev(x[X_VG1 + 1] - interp1(tb.cvg_x, tb.cvg_y, n2c_frac), p[P_VGSAT])
    w25c = (
        wcm2
        * p[P_SWC_HPC]
        * map_modifier(n2c_frac, p[P_CWA], p[P_CWK])
        * (1.0 - p[P_KWCVG] * dvg2)
        * (1.0 + h[3])
    )
    eta_hpc = (
        em2
        * p[P_SEFF_HPC]
        * map_modifier(n2c_frac, p[P_CEA], p[P_CEK])
        * (1.0 - p[P_KECVG] * dvg2 * dvg2)
        * (1.0 + h[2])
    )
    eta_hpc = eta_hpc - (1.0 - eta_hpc) * (rfac - 1.0)
    w25 = w25c * (p25 / P_STD) / np.sqrt(th25)
    if surge == 1:
        w25 = w25 * cs
        eta_hpc = eta_hpc * (1.0 - (1.0 - p[P_SURGE_EFF]) * (1.0 - cs) / (1.0 - p[P_SURGE_CMIN]))
    t3, dh_hpc = compress(t25, pr_hpc, eta_hpc, z0, war, B)
    sm_hpc = (1.0 + (prst2 - 1.0) * p[P_SPR_HPC]) / pr_hpc - 1.0
    pw_hpc = w25 * dh_hpc
    h3, _ = h_cp(t3, z0, war, B)
    r_air = gas_r(z0, war, B)
    # ---- bypass stream: duct loss, fixed bypass nozzle (health nozzle_area acts on the core nozzle only)
    p13 = p21 * (1.0 - p[P_DPBYP] * q21sq)
    w13, fg13, sl13 = nozzle_flow(p13, t21, z0, war, ps0, p[P_A18], p[P_CD18], p[P_CFG], B)
    # ---- bleeds and cooling
    wbl = ue[U_BLEED]
    if wbl.real < 0.0:
        wbl = 0.0 * wbl
    if wbl.real > 0.15 * w25.real:
        wbl = 0.15 * w25
    wrot = p[P_FROT] * w25
    # ---- combustor + HPT (NGV-choked flow sets W41 from the T41 state)
    wc3 = w25 * np.sqrt(t3) / p3
    q3 = wc3 / p[P_WC3DES]
    p4 = p3 * (1.0 - p[P_DPB] * q3 * q3)
    n2rpm = n2 * RPM_PER_RADS
    pr_hpt = p4 / p45
    wp_m, eh_m = turbine_lookup(
        n2rpm / np.sqrt(t41) / p[P_SNP_HPT],
        (pr_hpt - 1.0) / p[P_SPR_HPT] + 1.0,
        tb.hpt_np,
        tb.hpt_pr,
        tb.hpt_wp,
        tb.hpt_eff,
    )
    w41 = (
        wp_m
        * p[P_SWP_HPT]
        * turbine_unchoke(pr_hpt, p[P_PRCH_HPT], p[P_GTURB])
        * (1.0 + h[5])
        * p4
        / np.sqrt(t41)
    )
    wf_c = inl[INL_WFL]
    if wf_c.real < 0.0:
        wf_c = 0.0 * wf_c
    w_air41 = w41 - wf_c
    if w_air41.real < 1e-3:
        w_air41 = 1e-3 + 0.0 * w_air41
    w_comb = w_air41 / (1.0 + p[P_CNGV])
    lit = 1.0 if flame == 1 else 0.0
    wf_b = wf_c
    wf_st = p[P_FST] * w_comb / (1.0 + war)
    if wf_b.real > wf_st.real:
        wf_b = wf_st
    f41 = lit * wf_b * (1.0 + war) / w_air41
    far4 = wf_c * (1.0 + war) / w_comb
    eta_b = p[P_ETAB] * (1.0 + h[8]) * (1.0 + ue[U_WCE]) * lit
    h41_ad = (w_air41 * h3 + eta_b * wf_b * p[P_LHV]) / w41
    t41_ad = t_from_h(h41_ad, f41, war, B, t41)
    clear = (
        p[P_GCLR_C] * (x[X_TC] - p[P_TCREF])
        - p[P_GCLR_M] * (x[X_TM] - p[P_TMREF])
        - p[P_GCLR_W] * (n2 * n2 - p[P_N2DES] * p[P_N2DES]) / (p[P_N2DES] * p[P_N2DES])
    )
    eta_hpt = eh_m * p[P_SEFF_HPT] * (1.0 + h[4]) * (1.0 - p[P_KETACLR] * clear)
    eta_hpt = eta_hpt - (1.0 - eta_hpt) * (rfac - 1.0)
    t45a, dh_hpt = expand(t41, pr_hpt, eta_hpt, f41, war, B)
    pw_hpt = w41 * dh_hpt
    t_gas = 0.5 * (t41 + t45a)
    wr = w41 / p[P_W41DES]
    if wr.real < 1e-3:
        wr = 1e-3 + 0.0 * wr
    ha = p[P_HAMET] * wr**0.8
    q_soak = ha * (t_gas - x[X_TM])
    w45 = w41 + wrot
    h45a, _ = h_cp(t45a, f41, war, B)
    h45 = (w41 * h45a + wrot * h3 - q_soak) / w45
    f45 = lit * wf_b * (1.0 + war) / (w_air41 + wrot)
    t45 = t_from_h(h45, f45, war, B, t45a)
    # ---- LPT (turns at gear_ratio * fan speed) discharging into the LPT-exit duct volume V5
    pr_lpt = p45 / p5
    nlpt_rpm = p[P_GEAR] * n1 * RPM_PER_RADS
    wp_l, el_m = turbine_lookup(
        nlpt_rpm / np.sqrt(t45) / p[P_SNP_LPT],
        (pr_lpt - 1.0) / p[P_SPR_LPT] + 1.0,
        tb.lpt_np,
        tb.lpt_pr,
        tb.lpt_wp,
        tb.lpt_eff,
    )
    wlpt = (
        wp_l
        * p[P_SWP_LPT]
        * turbine_unchoke(pr_lpt, p[P_PRCH_LPT], p[P_GTURB])
        * (1.0 + h[7])
        * p45
        / np.sqrt(t45)
    )
    eta_lpt = el_m * p[P_SEFF_LPT] * (1.0 + h[6])
    eta_lpt = eta_lpt - (1.0 - eta_lpt) * (rfac - 1.0)
    t5, dh_lpt = expand(t45, pr_lpt, eta_lpt, f45, war, B)
    pw_lpt = wlpt * dh_lpt
    # ---- core stream: fixed core nozzle fed from V5 (the A8 state is the fixed core nozzle area)
    r5 = gas_r(f45, war, B)
    a8e = x[X_A8] * (1.0 + h[9])
    w8, fg8, sl8 = nozzle_flow(p5, t5, f45, war, ps0, a8e, p[P_CD8], p[P_CFG], B)
    v0 = inl[INL_V0]
    fg = fg13 + fg8
    fn = fg - w2 * v0
    # ---- volume (mass) dynamics, quasi-steady volume temperatures (A-W1.3a-6)
    dx[X_P21] = r_air * t21 / p[P_V21] * (w2 - w25 - w13)
    dx[X_P3] = r_air * t3 / p[P_V3] * (w25 + wf_c - wbl - wrot - w41)
    dx[X_P45] = gas_r(f45, war, B) * t45 / p[P_V45] * (w41 + wrot - wlpt)
    dx[X_P5] = r5 * t5 / p[P_V5] * (wlpt - w8)
    # unused mixer-volume state: relaxes to ambient static pressure (numerical regularity only), or, with the
    # PROTOTYPE gas-path thermal lag on (tau > 0), the heat-storage node between the LPT exit and T5 station
    t5_station = t5
    if p[P_GPTAU].real > 0.0:
        dx[X_P6] = (t5 - x[X_P6]) / p[P_GPTAU]
        t5_station = t5 - p[P_GPK] * (t5 - x[X_P6])
    else:
        dx[X_P6] = (ps0 - x[X_P6]) / p[P_P6TAU]
    dx[X_T41] = (t41_ad - t41) / p[P_TAUCOMB]
    # ---- rotor dynamics. LP: turbine power through the fan gearbox; i_lp is reflected to the fan shaft.
    # HP: shaft-load disturbance on the HPC + accessory torque (AD-32) and PTO, as in mixed_ab.
    n2r = n2 / p[P_N2DES]
    pw_acc = p[P_PACC] * n2r * n2r
    q_pto = ue[U_PTO] / (n2 + PTO_W_FLOOR)
    pw_ext = pw_acc + q_pto * n2
    dx[X_N1] = (p[P_ETAM] * p[P_ETAGB] * pw_lpt - pw_fan) / (p[P_ILP] * n1)
    dx[X_N2] = ((p[P_ETAM] * pw_hpt - (pw_hpc + pw_acc) * (1.0 + ue[U_WSL])) / n2 - q_pto) / p[P_IHP]
    # ---- actuators: fuel metering valve and VG as in mixed_ab; fixed nozzle; no AB fuel
    wf_cmd = ue[U_WF]
    if wf_cmd.real < 0.0:
        wf_cmd = 0.0 * wf_cmd
    dx[X_WFM] = (wf_cmd - x[X_WFM]) / p[P_TAUFMV]
    dx[X_A8] = 0.0 * x[X_A8]
    for jj in range(2):
        vt = ue[U_VG1 + jj]
        if vt.real < p[P_VGMIN].real:
            vt = p[P_VGMIN] + 0.0 * vt
        if vt.real > p[P_VGMAX].real:
            vt = p[P_VGMAX] + 0.0 * vt
        rv = (vt - x[X_VG1 + jj]) / p[P_TAUVG]
        if rv.real > p[P_VGRATE].real:
            rv = p[P_VGRATE] + 0.0 * rv
        if rv.real < -p[P_VGRATE].real:
            rv = -p[P_VGRATE] + 0.0 * rv
        dx[X_VG1 + jj] = rv
    dx[X_WFAB] = (0.0 - x[X_WFAB]) / p[P_TAUWFAB]
    # ---- metal temperatures
    dx[X_TM] = q_soak / p[P_CMET]
    tc_t = t3 + p[P_CCASE] * (t41 - t3)
    dx[X_TC] = (tc_t - x[X_TC]) / p[P_TAUCASE]
    # ---- lube oil (lumped node; fuel-oil cooler effectiveness rises with fuel flow)
    wfr = wf_c / p[P_WFDES]
    if wfr.real < 1e-6:
        wfr = 1e-6 + 0.0 * wfr
    ua = p[P_UAOIL_AIR] + p[P_UAOIL_FUEL] * wfr**0.8
    n2o = n2 / p[P_N2DES]
    q_oil = p[P_QOIL] * n2o * n2o
    t_sink = ue[U_TFUEL]
    dx[X_TOIL] = (q_oil - ua * (x[X_TOIL] - t_sink)) / p[P_COIL]
    oil_p = (
        p[P_POILREG]
        * (1.0 - np.exp(-(n2 / p[P_N2DES]) / p[P_N2OILK]))
        * (p[P_TOILREF] / x[X_TOIL]) ** p[P_OILVISC]
    )
    # ---- diagnostics (mixed_ab layout; the mixer/AB slots carry the core-nozzle stream)
    aux[A_T2] = t2
    aux[A_P2] = p2
    aux[A_W2] = w2
    aux[A_W2C] = w2c
    aux[A_N1C] = n1c
    aux[A_T21] = t21
    aux[A_PRFAN] = pr_fan
    aux[A_ETAFAN] = eta_fan
    aux[A_SMFAN] = sm_fan
    aux[A_PWFAN] = pw_fan
    aux[A_T25] = t25
    aux[A_P25] = p25
    aux[A_W25] = w25
    aux[A_N2C] = n2c
    aux[A_PRHPC] = pr_hpc
    aux[A_ETAHPC] = eta_hpc
    aux[A_SMHPC] = sm_hpc
    aux[A_BEYOND] = beyond
    aux[A_T3] = t3
    g3 = w25 / p[P_A3]
    aux[A_PS3] = p3 - g3 * g3 * r_air * t3 / (2.0 * p3)
    aux[A_PWHPC] = pw_hpc
    aux[A_WBLEED] = wbl
    aux[A_WROT] = wrot
    aux[A_P4] = p4
    aux[A_W41] = w41
    aux[A_T4] = t41_ad
    aux[A_FAR4] = far4
    aux[A_T41AD] = t41_ad
    aux[A_PRHPT] = pr_hpt
    aux[A_ETAHPT] = eta_hpt
    aux[A_PWHPT] = pw_hpt
    aux[A_T45] = t45
    aux[A_WLPT] = wlpt
    aux[A_PRLPT] = pr_lpt
    aux[A_ETALPT] = eta_lpt
    aux[A_PWLPT] = pw_lpt
    aux[A_T5] = t5_station
    aux[A_P5] = p5
    aux[A_W13] = w13
    aux[A_W5MIX] = w8
    aux[A_BPR] = w13 / w25
    aux[A_T6] = t5
    aux[A_T7] = t5
    aux[A_P7] = p5
    aux[A_W8] = w8
    aux[A_FG] = fg
    aux[A_FN] = fn
    aux[A_WFL] = wf_c
    aux[A_QSOAK] = q_soak
    aux[A_CLEAR] = clear
    aux[A_OILP] = oil_p
    aux[A_VIB0] = p[P_VIBK1] * (n1 / p[P_N1DES]) ** p[P_VIBEXP]
    aux[A_VIB1] = p[P_VIBK2] * (n2 / p[P_N2DES]) ** p[P_VIBEXP]
    aux[A_VIB2] = p[P_VIBK3] * w2 / p[P_W2DES]
    aux[A_V0] = v0
    aux[A_PWEXT] = pw_ext
    aux[A_ABHEAT] = 0.0 * w2
    # stiffness estimate of the volume-pressure modes (1/s, real parts only; drives the sub-step count):
    # V21 empties into the HPC (slope ~ W/p) and the bypass nozzle (exact flow-function slope); V5 into the
    # core nozzle; V3 and V45 into choked turbines (slope ~ W/p), as in mixed_ab
    lam21 = r_air.real * t21.real / p[P_V21].real * (abs(w25.real) / p21.real + abs(w13.real) * sl13)
    lam5 = r5.real * t5.real / p[P_V5].real * (abs(wlpt.real) / p5.real + abs(w8.real) * sl8)
    lam3 = r_air.real * t3.real / p[P_V3].real * abs(w41.real) / p3.real
    lam45 = gas_r(f45, war, B).real * t45.real / p[P_V45].real * abs(wlpt.real) / p45.real
    lam = lam21
    if lam5 > lam:
        lam = lam5
    if lam3 > lam:
        lam = lam3
    if lam45 > lam:
        lam = lam45
    aux[A_LAM] = lam


@njit(**_JIT)
def _eval_sf(x, ab, flame, surge, st, inl, ue, p, tb, dx, aux, n_delay):
    if n_delay == 0:
        inl[INL_WFL] = x[X_WFM] * (1.0 + ue[U_WFM_D])
    deriv_sf(x, ab, flame, surge, st, inl, ue, p, tb, dx, aux)


@njit(**_JIT)
def _tick_sf(fe, ie, bufe, p, tb, ue, uie, dt, n_sub, n_delay, x, xt, dx, dx0, dx2, aux, inl, ye, yie):
    """Advance one separate-flow engine by one 240 Hz tick (``kernel._tick`` numerics; no afterburner)."""
    inlet(ue[U_TS], ue[U_PS], ue[U_Q], ue[U_MACH], ue[U_WIR], p, tb, inl)
    if n_delay > 0:
        inl[INL_WFL] = bufe[ie[I_BUFPOS]]
    ab = AB_OFF
    flame = ie[I_FLAME]
    surge = ie[I_SURGE]
    k_surge = fe[F_SURGE_TIMER].real
    st = 0.0 * fe[F_SURGE_TIMER] + k_surge * dt
    st0 = st
    n_max = int(p[P_NSUBMAX].real)
    for j in range(NX):
        x[j] = fe[j]
    _eval_sf(x, ab, flame, surge, st0, inl, ue, p, tb, dx0, aux, n_delay)
    n_try = n_sub
    n_stab = int(np.ceil(dt * aux[A_LAM].real / p[P_STAB].real))
    if n_stab > n_try:
        n_try = n_stab
    if n_try > n_max:
        n_try = n_max
    tol = p[P_INTTOL].real
    while True:
        for j in range(NX):
            x[j] = fe[j]
        hs = dt / n_try
        err = 0.0
        for _s in range(n_try):
            st = st0 + (_s * hs if surge == 1 else 0.0)
            if _s == 0:
                for j in range(NX):
                    dx[j] = dx0[j]
            else:
                _eval_sf(x, ab, flame, surge, st, inl, ue, p, tb, dx, aux, n_delay)
            for j in range(NX):
                xt[j] = x[j] + hs * dx[j]
            _eval_sf(xt, ab, flame, surge, st + 0.5 * hs, inl, ue, p, tb, dx2, aux, n_delay)
            e = pressure_error(x, dx, dx2, hs)
            if e > err:
                err = e
            for j in range(NX):
                x[j] = x[j] + 0.5 * hs * (dx[j] + dx2[j])
        if err <= tol or 2 * n_try > n_max:
            break
        n_try = 2 * n_try
    for j in range(NX):
        fe[j] = x[j]
    if surge == 1:
        k_surge = k_surge + 1.0
        st = st0 + dt
    _eval_sf(x, ab, flame, surge, st, inl, ue, p, tb, dx, aux, n_delay)
    wf_meas = x[X_WFM] * (1.0 + ue[U_WFM_D])
    ye[Y_N1] = x[X_N1]
    ye[Y_N2] = x[X_N2]
    ye[Y_T2] = aux[A_T2]
    ye[Y_T25] = aux[A_T25]
    ye[Y_T3] = aux[A_T3]
    ye[Y_T5] = aux[A_T5]
    ye[Y_P2] = aux[A_P2]
    ye[Y_PS3] = aux[A_PS3]
    ye[Y_P5] = aux[A_P5]
    ye[Y_WF] = wf_meas
    ye[Y_WFAB] = 0.0 * wf_meas
    ye[Y_A8] = x[X_A8]
    ye[Y_VG1] = x[X_VG1]
    ye[Y_VG2] = x[X_VG1 + 1]
    ye[Y_W2] = aux[A_W2]
    ye[Y_FN] = aux[A_FN]
    ye[Y_OILT] = x[X_TOIL]
    ye[Y_OILP] = aux[A_OILP]
    ye[Y_VIB0] = aux[A_VIB0]
    ye[Y_VIB1] = aux[A_VIB1]
    ye[Y_VIB2] = aux[A_VIB2]
    sm = aux[A_SMHPC]
    if aux[A_SMFAN].real < sm.real:
        sm = aux[A_SMFAN]
    ye[Y_SM] = sm
    ye[Y_BLP3] = x[X_P3]
    ye[Y_BLT3] = aux[A_T3]
    aux[A_T4] = combustor_exit_temperature(aux, flame, inl, ue, p, tb)
    # ---- discrete processes on the end-of-tick state (take effect from the next tick); no afterburner
    far_lbo = p[P_FARLBO] * (p[P_PLBO] / x[X_P3]) ** p[P_NLBO]
    if flame == 1:
        lean_out = aux[A_FAR4].real < far_lbo.real or aux[A_WFL].real < p[P_WFMINFL].real
        if lean_out:
            fe[F_FLAME_TIMER] = fe[F_FLAME_TIMER] + 1.0
            if fe[F_FLAME_TIMER].real >= np.floor(p[P_TLBO].real / dt + 0.5):
                flame = 0
                fe[F_FLAME_TIMER] = 0.0 * fe[F_FLAME_TIMER]
        else:
            fe[F_FLAME_TIMER] = 0.0 * fe[F_FLAME_TIMER]
    else:
        light_ok = (
            uie[UI_IGN] == 1 and aux[A_FAR4].real >= p[P_FARLIGHT].real and x[X_P3].real >= p[P_P3LIGHT].real
        )
        if light_ok:
            fe[F_FLAME_TIMER] = fe[F_FLAME_TIMER] + 1.0
            if fe[F_FLAME_TIMER].real >= np.floor(p[P_TIGN].real / dt + 0.5):
                flame = 1
        else:
            fe[F_FLAME_TIMER] = 0.0 * fe[F_FLAME_TIMER]
    if surge == 0:
        if aux[A_SMHPC].real < p[P_SMTRIG].real or aux[A_SMFAN].real < p[P_SMTRIG].real:
            surge = 1
            k_surge = 0.0
            ie[I_NSURGE] = ie[I_NSURGE] + 1
    elif k_surge >= np.floor(p[P_SURGE_TREC].real / dt + 0.5):
        surge = 0
    fe[F_SURGE_TIMER] = 0.0 * fe[F_SURGE_TIMER] + k_surge
    ie[I_AB] = ab
    ie[I_FLAME] = flame
    ie[I_SURGE] = surge
    if n_delay > 0:
        bufe[ie[I_BUFPOS]] = wf_meas
        ie[I_BUFPOS] = (ie[I_BUFPOS] + 1) % n_delay
    ie[I_TICK] = ie[I_TICK] + 1
    yie[YI_AB] = ab
    yie[YI_FLAME] = flame


@njit(**_JIT)
def engine_kernel_sf(f, i, buf, p, tb, u, ui, z_ab, dt, n_sub, n_delay, record_aux):
    """``kernel.engine_kernel`` for the separate_fixed topology (same signature; ``z_ab`` is unused)."""
    f = f.copy()
    i = i.copy()
    buf = buf.copy()
    n_eng = f.shape[0]
    n_t = u.shape[0]
    y = np.empty((n_t, n_eng, NY), dtype=f.dtype)
    yi = np.empty((n_t, n_eng, NYI), dtype=np.int64)
    n_aux_t = n_t if record_aux else 1
    yaux = np.zeros((n_aux_t, n_eng, NAUX), dtype=f.dtype)
    x = np.empty(NX, dtype=f.dtype)
    xt = np.empty(NX, dtype=f.dtype)
    dx = np.empty(NX, dtype=f.dtype)
    dx0 = np.empty(NX, dtype=f.dtype)
    dx2 = np.empty(NX, dtype=f.dtype)
    aux = np.empty(NAUX, dtype=f.dtype)
    inl = np.empty(NINL, dtype=f.dtype)
    for e in range(n_eng):
        for k in range(n_t):
            _tick_sf(f[e], i[e], buf[e], p, tb, u[k, e], ui[k, e], dt, n_sub, n_delay,
                     x, xt, dx, dx0, dx2, aux, inl, y[k, e], yi[k, e])  # fmt: skip
            if record_aux:
                for j in range(NAUX):
                    yaux[k, e, j] = aux[j]
    return f, i, buf, y, yi, yaux


@njit(**_JIT)
def deriv_point_sf(x, ab, flame, surge, surge_timer, u_row, p, tb, wf_line):
    """dx/dt and diagnostics at one state (steady solver / linearisation entry point; ``kernel.deriv_point``
    semantics)."""
    inl = np.empty(NINL, dtype=x.dtype)
    dx = np.empty(NX, dtype=x.dtype)
    aux = np.empty(NAUX, dtype=x.dtype)
    inlet(u_row[U_TS], u_row[U_PS], u_row[U_Q], u_row[U_MACH], u_row[U_WIR], p, tb, inl)
    if wf_line.real < 0.0:
        inl[INL_WFL] = x[X_WFM] * (1.0 + u_row[U_WFM_D])
    else:
        inl[INL_WFL] = wf_line
    deriv_sf(x, ab, flame, surge, surge_timer, inl, u_row, p, tb, dx, aux)
    aux[A_T4] = combustor_exit_temperature(aux, flame, inl, u_row, p, tb)
    return dx, aux
