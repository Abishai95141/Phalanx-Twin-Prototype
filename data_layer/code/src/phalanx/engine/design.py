"""M07 design point (cycle closure) and model assembly: parameters -> flat kernel vector + tables.

The design point is SLS ISA, dry air, uninstalled, at 100 % N1/N2 and the maximum-dry (MIL) gas generator
(architecture §6 M07: "design point closed to IN20 ratings"). It is computed station by station with the
**same** thermodynamic and map functions the kernel uses, so the kernel's steady state at the design inputs
*is* this point (A1/A3 tests). From it the map scalers (pyCycle convention), the bypass and core duct flow
coefficients, the HPC-exit area (PS3) and the design references are derived. The maximum-afterburner point
keeps the same gas generator and solves the AB fuel flow for the DIRECT 84 kN rating; the nozzle area
follows from the flow.

Everything here is deterministic NumPy/compiled arithmetic (no randomness, no I/O beyond the parameter
loader).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from phalanx.core.module import Param, ParamSet
from phalanx.core.time import TRUTH_HZ
from phalanx.dictionary.params import load_params

from .kernel import P_STD, RPM_PER_RADS, T_STD, EngineTables
from .layout import DERIVED_P, P_NAMES, PI
from .maps import (
    compressor_map_from_columns,
    flow_function,
    interp1,
    turbine_lookup,
    turbine_map_from_columns,
    turbine_unchoke,
)
from .thermo import (
    basis_coefficients,
    compress,
    expand,
    gamma_of,
    gas_r,
    h_cp,
    phi_cp,
    species_table_to_coeffs,
    t_from_h,
    t_from_phi,
)

MODULE = "M07"
SLS_T = 288.15
SLS_P = 101325.0
# ParamSet entries that map 1:1 onto kernel parameters (name in YAML -> kernel name)
_DIRECT_P = {
    "dp_core_duct": "dp_core_duct",
    "dp_burner": "dp_burner",
    "dp_ab_dry": "dp_ab_dry",
    "k_rayleigh": "k_rayleigh",
    "eta_burner": "eta_burner",
    "lhv": "lhv",
    "eta_ab": "eta_ab",
    "eta_mech": "eta_mech",
    "f_rot": "f_rot",
    "cfg": "cfg",
    "cd8": "cd8",
    "pr_choke_hpt": "pr_choke_hpt",
    "pr_choke_lpt": "pr_choke_lpt",
    "gamma_turb_eq": "gamma_turb_eq",
    "stall_slope": "stall_slope",
    "p_acc_design": "p_acc_des",
    "mil_e_5008b_a": "mil_e_5008b_a",
    "mil_e_5008b_b": "mil_e_5008b_b",
    "v21": "v21",
    "v3": "v3",
    "v45": "v45",
    "v5": "v5",
    "v6": "v6",
    "i_lp": "i_lp",
    "i_hp": "i_hp",
    "tau_comb": "tau_comb",
    "tau_fmv": "tau_fmv",
    "tau_a8": "tau_a8",
    "tau_vg": "tau_vg",
    "vg_rate": "vg_rate",
    "vg_min": "vg_min",
    "vg_max": "vg_max",
    "tau_wfab": "tau_wfab",
    "k_w_fvg": "k_w_fvg",
    "k_e_fvg": "k_e_fvg",
    "k_w_cvg": "k_w_cvg",
    "k_e_cvg": "k_e_cvg",
    "vg_dev_sat": "vg_dev_sat",
    "c_metal": "c_metal",
    "ha_metal": "ha_metal",
    "tau_case": "tau_case",
    "c_case": "c_case",
    "g_clr_case": "g_clr_case",
    "g_clr_metal": "g_clr_metal",
    "g_clr_speed": "g_clr_speed",
    "k_eta_clr": "k_eta_clr",
    "sm_trigger": "sm_trigger",
    "surge_c_min": "surge_c_min",
    "surge_t_rec": "surge_t_rec",
    "surge_eff": "surge_eff",
    "ab_t_ref": "ab_t_ref",
    "ab_p_ref": "ab_p_ref",
    "ab_n_p": "ab_n_p",
    "ab_b_t": "ab_b_t",
    "ab_t1_ref": "ab_t1_ref",
    "ab_sigma": "ab_sigma",
    "wfab_min": "wfab_min",
    "far_lbo_ref": "far_lbo_ref",
    "p_lbo_ref": "p_lbo_ref",
    "n_lbo": "n_lbo",
    "t_lbo": "t_lbo",
    "far_light_min": "far_light_min",
    "p3_light_min": "p3_light_min",
    "t_ign": "t_ign",
    "wf_min_flame": "wf_min_flame",
    "c_oil": "c_oil",
    "q_oil_ref": "q_oil_ref",
    "ua_oil_air": "ua_oil_air",
    "ua_oil_fuel": "ua_oil_fuel",
    "dt_fuel_sink": "dt_fuel_sink",
    "p_oil_reg": "p_oil_reg",
    "n2_oil_k": "n2_oil_k",
    "oil_visc_k": "oil_visc_k",
    "t_oil_ref": "t_oil_ref",
    "vib_k_n1": "vib_k_n1",
    "vib_k_n2": "vib_k_n2",
    "vib_k_bb": "vib_k_bb",
    "vib_exp": "vib_exp",
    "int_tol": "int_tol",
    "stab_hlam": "stab_hlam",
    "k_eta_fan_face": "k_eta_fan_face",
    "n_sub_max": "n_sub_max",
}
assert set(_DIRECT_P.values()) | set(DERIVED_P) == set(P_NAMES), sorted(
    set(P_NAMES) ^ (set(_DIRECT_P.values()) | set(DERIVED_P))
)


def load_engine_params(platform: str = "tejas", **kw: Any) -> ParamSet:
    """All M07 parameter sets merged into one ParamSet (names are unique across sets)."""
    sets = load_params(MODULE, platform=platform, **kw)
    merged: dict[str, Param] = {}
    for sname in sorted(sets):
        for k, prm in sets[sname].items():
            if k in merged:
                raise ValueError(f"M07 parameter {k!r} defined in more than one set")
            merged[k] = prm
    return ParamSet(f"{platform}.{MODULE}", merged)


def _v(ps: ParamSet, name: str) -> float:
    return float(ps.value(name))


def build_tables(ps: ParamSet) -> EngineTables:
    cols = ("species_id", "range_id", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "b1", "b2", "molar_mass")
    table = {c: np.asarray(ps.value(f"thermo_{c}"), float) for c in cols}
    # molar mass was converted to SI (kg/mol) by the loader; species_table_to_coeffs expects g/mol
    table["molar_mass"] = table["molar_mass"] * 1e3
    a, mm = species_table_to_coeffs(table)
    B = basis_coefficients(a, mm)
    fan = compressor_map_from_columns(*(ps.value(f"fan_map_{c}") for c in ("nc", "rline", "wc", "pr", "eff")))
    hpc = compressor_map_from_columns(*(ps.value(f"hpc_map_{c}") for c in ("nc", "rline", "wc", "pr", "eff")))
    hpt = turbine_map_from_columns(*(ps.value(f"hpt_map_{c}") for c in ("np", "pr", "wp", "eff")))
    lpt = turbine_map_from_columns(*(ps.value(f"lpt_map_{c}") for c in ("np", "pr", "wp", "eff")))
    arr = lambda k: np.ascontiguousarray(np.asarray(ps.value(k), float))  # noqa: E731
    tabs = EngineTables(
        thermo=np.ascontiguousarray(B),
        fan_nc=fan.nc, fan_wc=fan.wc, fan_pr=fan.pr, fan_eff=fan.eff,
        hpc_nc=hpc.nc, hpc_wc=hpc.wc, hpc_pr=hpc.pr, hpc_eff=hpc.eff,
        hpt_np=hpt.np_, hpt_pr=hpt.pr, hpt_wp=hpt.wp, hpt_eff=hpt.eff,
        lpt_np=lpt.np_, lpt_pr=lpt.pr, lpt_wp=lpt.wp, lpt_eff=lpt.eff,
        fvg_x=arr("fvg_ref_n1c"), fvg_y=arr("fvg_ref_angle"),
        cvg_x=arr("cvg_ref_n2c"), cvg_y=arr("cvg_ref_angle"),
    )  # fmt: skip
    for t in tabs:
        t.flags.writeable = False
    return tabs


def _map_point(nc_ax, rl_ax, tab, nc, rl) -> float:
    i = int(np.flatnonzero(np.isclose(nc_ax, nc))[0])
    j = int(np.flatnonzero(np.isclose(rl_ax, rl))[0])
    return float(tab[i, j])


def _solve_pr_for_work(t_in, dh_target, eta, f, w, B, lo=1.01, hi=12.0) -> float:
    """Expansion pressure ratio delivering dh_target (bisection on log PR,
    then secant polish; deterministic)."""
    a, b = math.log(lo), math.log(hi)
    for _ in range(80):
        m = 0.5 * (a + b)
        if expand(t_in, math.exp(m), eta, f, w, B)[1] < dh_target:
            a = m
        else:
            b = m
    return math.exp(0.5 * (a + b))


@dataclass(frozen=True)
class DesignPoint:
    """Design-point stations (SI) and derived quantities; ``derived`` holds the kernel parameter values."""

    stations: dict[str, float]
    derived: dict[str, float]
    max_ab: dict[str, float]
    vg_ref: tuple[float, float]
    checks: dict[str, float] = field(default_factory=dict)


def design_point(ps: ParamSet, tabs: EngineTables) -> DesignPoint:
    B = tabs.thermo
    w = 0.0  # ISA standard day: dry air
    w2 = _v(ps, "w2_design")
    opr = _v(ps, "opr_design")
    fpr = _v(ps, "fpr_design")
    bpr = _v(ps, "bpr_design")
    t4 = _v(ps, "t4_design")
    n1 = _v(ps, "n1_100pct")  # rad/s (loader converted rpm); the design MIL point runs at 100 % N1
    n2 = _v(ps, "n2_100pct") * _v(ps, "n2_mil_frac")  # MIL at about 95 % N2 (AD-46, A-W1.3a-20)
    dp_cd, dp_b, dp_ab = (_v(ps, k) for k in ("dp_core_duct", "dp_burner", "dp_ab_dry"))
    dp_byp, m_byp, dp_mix = (_v(ps, k) for k in ("dp_bypass_duct", "m_bypass_mixer", "dp_mixer"))
    eta_f, eta_c, eta_ht, eta_lt = (
        _v(ps, k) for k in ("eta_fan_design", "eta_hpc_design", "eta_hpt_design", "eta_lpt_design")
    )
    f_ngv, f_rot = _v(ps, "f_ngv"), _v(ps, "f_rot")
    eta_b, lhv, eta_m = _v(ps, "eta_burner"), _v(ps, "lhv"), _v(ps, "eta_mech")
    p_acc = _v(ps, "p_acc_design")
    # ---- cold section
    t2, p2 = SLS_T, SLS_P
    p21 = p2 * fpr
    t21, dh_fan = compress(t2, fpr, eta_f, 0.0, w, B)
    p25 = p21 * (1.0 - dp_cd)
    p3 = opr * p2
    cpr = p3 / p25
    t25 = t21
    t3, dh_hpc = compress(t25, cpr, eta_c, 0.0, w, B)
    w25 = w2 / (1.0 + bpr)
    w13 = w2 - w25
    wrot = f_rot * w25
    wngv = f_ngv * w25
    wcomb = w25 - wrot - wngv
    p4 = p3 * (1.0 - dp_b)
    h3, _ = h_cp(t3, 0.0, w, B)
    # ---- combustor: fuel for T4 (fixed point on the products' enthalpy; converges in a few iterations)
    wf = wcomb * 0.025
    for _ in range(60):
        h4, _ = h_cp(t4, wf / wcomb, w, B)
        wf = wcomb * (h4 - h3) / (eta_b * lhv - h4)
    f4 = wf / wcomb
    w41 = wcomb + wf + wngv
    w_air41 = w41 - wf
    f41 = wf / w_air41
    h41 = (w_air41 * h3 + eta_b * wf * lhv) / w41
    t41 = float(t_from_h(h41, f41, w, B, t4))
    # ---- HP spool balance -> HPT expansion
    pw_hpc = w25 * dh_hpc
    pw_hpt = (pw_hpc + p_acc) / eta_m
    pr_hpt = _solve_pr_for_work(t41, pw_hpt / w41, eta_ht, f41, w, B)
    t45a, dh_hpt = expand(t41, pr_hpt, eta_ht, f41, w, B)
    p45 = p4 / pr_hpt
    h45a, _ = h_cp(t45a, f41, w, B)
    w45 = w41 + wrot
    h45 = (w41 * h45a + wrot * h3) / w45
    f45 = wf / (w_air41 + wrot)
    t45 = float(t_from_h(h45, f45, w, B, t45a))
    # ---- LP spool balance -> LPT expansion
    pw_fan = w2 * dh_fan
    pr_lpt = _solve_pr_for_work(t45, pw_fan / (eta_m * w45), eta_lt, f45, w, B)
    t5, dh_lpt = expand(t45, pr_lpt, eta_lt, f45, w, B)
    p5 = p45 / pr_lpt
    # ---- lumped mixer (static-pressure match): the V6 state is the mixer static pressure; the core stream
    # reaches it from P5 and the bypass stream from P21 through their duct losses and dynamic heads
    r_air = float(gas_r(0.0, w, B))
    p16 = p21 * (1.0 - dp_byp)
    g13 = float(gamma_of(t21, 0.0, w, B))
    p6 = p16 / (1.0 + 0.5 * (g13 - 1.0) * m_byp * m_byp) ** (g13 / (g13 - 1.0))
    g5 = float(gamma_of(t5, f45, w, B))
    if p5 <= p6:
        raise ValueError(f"cycle does not close: core exit total {p5:.0f} Pa <= mixer static {p6:.0f} Pa")
    m_core = math.sqrt(2.0 / (g5 - 1.0) * ((p5 / p6) ** ((g5 - 1.0) / g5) - 1.0))
    dp13 = p21 - p6
    eps13 = _v(ps, "eps13_frac") * dp13
    rho21 = p21 / (r_air * t21)
    k13 = w13 * (dp13 * dp13 + eps13 * eps13) ** 0.25 / (dp13 * math.sqrt(rho21))
    dp5 = p5 - p6
    eps5 = _v(ps, "eps13_frac") * dp5
    rho5 = p5 / (float(gas_r(f45, w, B)) * t5)
    k5 = w45 * (dp5 * dp5 + eps5 * eps5) ** 0.25 / (dp5 * math.sqrt(rho5))
    # ---- mixer and dry nozzle
    w6 = w45 + w13
    h5, _ = h_cp(t5, f45, w, B)
    h21, _ = h_cp(t21, 0.0, w, B)
    h6 = (w45 * h5 + w13 * h21) / w6
    w45_dry = w45 / (1.0 + f45 + w)
    w6_dry = w45_dry + w13 / (1.0 + w)
    f6 = f45 * w45_dry / w6_dry
    t6 = float(t_from_h(h6, f6, w, B, (w45 * t5 + w13 * t21) / w6))
    p6t = (w45 * p5 + w13 * p16) / w6 * (1.0 - dp_mix)
    p7 = p6t * (1.0 - dp_ab)
    cfg, cd8 = _v(ps, "cfg"), _v(ps, "cd8")

    def nozzle(t7, f7, p7_, w8):
        r7 = float(gas_r(f7, w, B))
        g7 = float(gamma_of(t7, f7, w, B))
        pr8 = p7_ / SLS_P
        a8e = w8 * math.sqrt(r7 * t7) / (p7_ * float(flow_function(pr8, g7)))
        phi7, _ = phi_cp(t7, f7, w, B)
        t9 = float(t_from_phi(phi7 - r7 * math.log(pr8), f7, w, B, t7 * pr8 ** (-(g7 - 1) / g7)))
        h7, _ = h_cp(t7, f7, w, B)
        h9, _ = h_cp(t9, f7, w, B)
        return a8e / cd8, cfg * w8 * math.sqrt(2.0 * (h7 - h9))

    a8_dry, fn_dry = nozzle(t6, f6, p7, w6)
    # ---- map scalers (pyCycle convention)
    fan_ncd, fan_rld = _v(ps, "fan_ncmap_design"), _v(ps, "fan_rline_design")
    hpc_ncd, hpc_rld = _v(ps, "hpc_ncmap_design"), _v(ps, "hpc_rline_design")
    tnp, tpr = _v(ps, "turb_npmap_design"), _v(ps, "turb_prmap_design")
    fan_ax = np.unique(np.asarray(ps.value("fan_map_rline"), float))
    hpc_ax = np.unique(np.asarray(ps.value("hpc_map_rline"), float))
    n1_rpm = n1 * RPM_PER_RADS
    n2_rpm = n2 * RPM_PER_RADS
    n1c_des = n1_rpm / math.sqrt(t2 / T_STD)
    n2c_des = n2_rpm / math.sqrt(t25 / T_STD)
    w2c = w2 * math.sqrt(t2 / T_STD) / (p2 / P_STD)
    w25c = w25 * math.sqrt(t25 / T_STD) / (p25 / P_STD)
    der: dict[str, float] = {}
    der["s_nc_fan"] = n1c_des / fan_ncd
    der["s_pr_fan"] = (fpr - 1.0) / (_map_point(tabs.fan_nc, fan_ax, tabs.fan_pr, fan_ncd, fan_rld) - 1.0)
    der["s_wc_fan"] = w2c / _map_point(tabs.fan_nc, fan_ax, tabs.fan_wc, fan_ncd, fan_rld)
    der["s_eff_fan"] = eta_f / _map_point(tabs.fan_nc, fan_ax, tabs.fan_eff, fan_ncd, fan_rld)
    der["s_nc_hpc"] = n2c_des / hpc_ncd
    der["s_pr_hpc"] = (cpr - 1.0) / (_map_point(tabs.hpc_nc, hpc_ax, tabs.hpc_pr, hpc_ncd, hpc_rld) - 1.0)
    der["s_wc_hpc"] = w25c / _map_point(tabs.hpc_nc, hpc_ax, tabs.hpc_wc, hpc_ncd, hpc_rld)
    der["s_eff_hpc"] = eta_c / _map_point(tabs.hpc_nc, hpc_ax, tabs.hpc_eff, hpc_ncd, hpc_rld)
    g_eq = _v(ps, "gamma_turb_eq")
    for name, n_rpm, tin, pin, pr, wt, eta, prch in (
        ("hpt", n2_rpm, t41, p4, pr_hpt, w41, eta_ht, _v(ps, "pr_choke_hpt")),
        ("lpt", n1_rpm, t45, p45, pr_lpt, w45, eta_lt, _v(ps, "pr_choke_lpt")),
    ):
        m_np, m_pr, m_wp, m_eff = (
            (tabs.hpt_np, tabs.hpt_pr, tabs.hpt_wp, tabs.hpt_eff)
            if name == "hpt"
            else (tabs.lpt_np, tabs.lpt_pr, tabs.lpt_wp, tabs.lpt_eff)
        )
        wp_map, eff_map = turbine_lookup(tnp, tpr, m_np, m_pr, m_wp, m_eff)
        gam = float(turbine_unchoke(pr, prch, g_eq))
        der[f"s_np_{name}"] = n_rpm / math.sqrt(tin) / tnp
        der[f"s_pr_{name}"] = (pr - 1.0) / (tpr - 1.0)
        der[f"s_wp_{name}"] = wt * math.sqrt(tin) / pin / (float(wp_map) * gam)
        der[f"s_eff_{name}"] = eta / float(eff_map)
    # ---- design references
    g3 = float(gamma_of(t3, 0.0, w, B))
    m3 = _v(ps, "m3_design")
    q_frac = 1.0 - (1.0 + 0.5 * (g3 - 1.0) * m3 * m3) ** (-g3 / (g3 - 1.0))
    der["a3_eff"] = w25 * math.sqrt(r_air * t3 / (2.0 * q_frac)) / p3
    der["k13"] = k13
    der["eps13"] = eps13
    der["c_ngv"] = f_ngv / (1.0 - f_ngv - f_rot)
    der["n1_des"] = n1
    der["n2_des"] = n2
    der["n1c_des_rpm"] = n1c_des
    der["n2c_des_rpm"] = n2c_des
    der["w2_des"] = w2
    der["w41_des"] = w41
    der["wc3_des"] = w25 * math.sqrt(t3) / p3
    der["wc6_des"] = w6 * math.sqrt(t6) / p6
    der["wf_des"] = wf
    der["tm_ref"] = 0.5 * (t41 + t45a)
    der["tc_ref"] = t3 + _v(ps, "c_case") * (t41 - t3)
    der["k5"] = k5
    der["f_stoich"] = _stoich_far(ps)
    der["eps5"] = eps5
    der["a8_min"] = _v(ps, "a8_min_ratio") * a8_dry
    der["a8_max"] = _v(ps, "a8_max_ratio") * a8_dry
    der["a8_rate"] = _v(ps, "a8_rate_ratio") * a8_dry
    der["r6_mix"] = p6t / p6 - 1.0
    assert set(der) == set(DERIVED_P), sorted(set(der) ^ set(DERIVED_P))
    # ---- maximum afterburner: same gas generator, AB fuel for the DIRECT max thrust, A8 from the flow
    fn_target = _v(ps, "thrust_max_ab")
    eta_ab, k_ray = _v(ps, "eta_ab"), _v(ps, "k_rayleigh")

    def ab_point(wfab):
        w7 = w6 + wfab
        h7 = (w6 * h6 + eta_ab * wfab * lhv) / w7
        f7 = f6 + wfab / w6_dry
        t7 = float(t_from_h(h7, f7, w, B, t6 + eta_ab * wfab * lhv / (w7 * 1250.0)))
        p7_ = p6t * (1.0 - dp_ab - k_ray * (t7 / t6 - 1.0))
        a8, fn = nozzle(t7, f7, p7_, w7)
        return fn, a8, t7, f7, p7_

    lo, hi = 0.0, 6.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if ab_point(mid)[0] < fn_target:
            lo = mid
        else:
            hi = mid
    wfab_max = 0.5 * (lo + hi)
    fn_ab, a8_ab, t7_ab, f7_ab, p7_ab = ab_point(wfab_max)
    # AB fuel-air ratio on the air left after core combustion (TM-100159 definition)
    f_st = _stoich_far(ps)
    air_left = w6_dry * (1.0 - f6 / f_st)
    vg_ref = (
        float(interp1(tabs.fvg_x, tabs.fvg_y, 1.0)),
        float(interp1(tabs.cvg_x, tabs.cvg_y, 1.0)),
    )
    stations = {
        "t2": t2, "p2": p2, "w2": w2, "t21": t21, "p21": p21, "t25": t25, "p25": p25, "w25": w25, "t3": t3,
        "p3": p3, "cpr": cpr, "fpr": fpr, "wf": wf, "t4": t4, "far4": f4, "p4": p4, "w41": w41, "t41": t41,
        "pr_hpt": pr_hpt, "t45a": t45a, "t45": t45, "p45": p45, "w45": w45, "pr_lpt": pr_lpt, "t5": t5,
        "p5": p5,
        "p6": p6, "p6t": p6t, "p16": p16, "m_core_mixer": m_core, "t6": t6, "w13": w13, "bpr": w13 / w25,
        "dp_bypass_frac": dp13 / p21, "p7": p7,
        "a8": a8_dry, "fn_dry": fn_dry, "w8": w6, "pw_fan": pw_fan, "pw_hpc": pw_hpc, "pw_hpt": w41 * dh_hpt,
        "pw_lpt": w45 * dh_lpt, "n1": n1, "n2": n2, "n1_100": _v(ps, "n1_100pct"),
        "n2_100": _v(ps, "n2_100pct"), "sfc_dry": wf / fn_dry,
    }  # fmt: skip
    max_ab = {
        "wf_ab": wfab_max, "fn": fn_ab, "a8": a8_ab, "t7": t7_ab, "f7": f7_ab, "p7": p7_ab,
        "thrust_ratio": fn_ab / fn_dry, "far_ab_available_air": wfab_max / air_left,
        "sfc": (wf + wfab_max) / fn_ab, "f_stoich": f_st,
    }  # fmt: skip
    return DesignPoint(stations=stations, derived=der, max_ab=max_ab, vg_ref=vg_ref)


def _stoich_far(ps: ParamSet) -> float:
    """Stoichiometric fuel/dry-air mass ratio of C12H23 with the species molar masses of the thermo table."""
    from .thermo import AIR_MOLE_FRACTIONS, FUEL_C, FUEL_H

    sid = np.asarray(ps.value("thermo_species_id"), float).astype(int)
    mm_all = np.asarray(ps.value("thermo_molar_mass"), float)  # kg/mol
    mm = np.zeros(5)
    mm[sid] = mm_all
    n2, o2, ar, co2, h2o = mm
    x = np.asarray(AIR_MOLE_FRACTIONS, float)
    x = x / x.sum()
    mass = x * np.array([n2, o2, ar, co2])
    y_o2 = mass[1] / mass.sum()
    m_fuel = FUEL_C * (co2 - o2) + FUEL_H / 2.0 * (h2o - o2 / 2.0)
    o2_per_fuel = (FUEL_C + FUEL_H / 4.0) * o2 / m_fuel
    return float(y_o2 / o2_per_fuel)


@dataclass(frozen=True)
class EngineModel:
    """Everything the kernel needs: flat parameter vector, tables, integer configuration, design point."""

    params: ParamSet
    p: np.ndarray
    tables: EngineTables
    design: DesignPoint
    n_sub: int
    n_delay: int
    dt: float

    def with_p(self, **values: float) -> EngineModel:
        """A copy with some kernel parameters replaced by index (calibration/sweep convenience)."""
        p = self.p.copy()
        for k, v in values.items():
            p[PI[k]] = v
        p.flags.writeable = False
        return EngineModel(self.params, p, self.tables, self.design, self.n_sub, self.n_delay, self.dt)


def build_engine_model(ps: ParamSet | None = None, *, n_sub: int | None = None) -> EngineModel:
    """Assemble the M07 model from a ParamSet (default: the Tejas registry): design point -> kernel vector."""
    ps = ps if ps is not None else load_engine_params()
    tabs = build_tables(ps)
    dp = design_point(ps, tabs)
    vals: dict[str, float] = {}
    for yname, kname in _DIRECT_P.items():
        vals[kname] = _v(ps, yname)
    vals.update(dp.derived)
    p = np.array([vals[n] for n in P_NAMES], dtype=np.float64)
    p.flags.writeable = False
    ns = int(ps.value("n_sub")) if n_sub is None else int(n_sub)
    n_delay = round(_v(ps, "fuel_transport_delay") * TRUTH_HZ)
    return EngineModel(ps, p, tabs, dp, ns, n_delay, 1.0 / TRUTH_HZ)
