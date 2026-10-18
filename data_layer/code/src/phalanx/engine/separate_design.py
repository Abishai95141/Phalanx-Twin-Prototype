"""Design point (cycle closure) and model assembly of the ``separate_fixed`` topology (AD-43, DASHlink proxy).

The design point is SLS ISA, dry air, uninstalled, at the proxy's takeoff-class rating. It is computed station
by station with the **same** thermodynamic, map and nozzle functions the ``separate.py`` kernel uses, so the
kernel's steady state at the design inputs *is* this point (A1 equilibrium test).

**Anchors** ([MEASURED] round-2 frozen M-A on 687-CAL, `analysis/settling_experiment_round2/results/frozen/S/
ma_readable.json`; an existing result, not a new fit): the design point runs at the top knot of the measured
corrected-speed relation (``n1_design_frac``/``n2_design_frac``) and reproduces the measured corrected fuel
flow
(``wf_design_anchor``) and corrected EGT (``egt_design_anchor``) at that speed. With every other cycle choice
fixed (BPR, FPR, OPR, efficiencies, cooling: ASSUMPTION, swept), T4 is the unique value that gives the
EGT-station temperature (T5, A-W2.4a-4), and the airflow scales the fuel flow exactly linearly (the cycle is
per unit mass flow). The nozzle areas, map scalers and design references follow, as in ``design.py``.

**Rotor inertias** are set from rotor energy times (``h_lp_s``, ``h_hp_s`` = stored kinetic energy at design /
design spool power, ASSUMPTION, swept): I = 2 H P / omega^2. Percent-speed dynamics depend only on I
omega_ref^2,
so the (not public) 100 % rpm references have no behavioural effect (tested).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from phalanx.core.module import Param, ParamSet
from phalanx.core.time import TRUTH_HZ
from phalanx.dictionary.params import load_params

from .design import DesignPoint, EngineModel, _map_point, _solve_pr_for_work, _stoich_far, build_tables
from .kernel import P_STD, RPM_PER_RADS, T_STD
from .layout import DERIVED_P
from .maps import flow_function, interp1, turbine_lookup, turbine_unchoke
from .separate import SF_P_NAMES, SF_PI, TOPOLOGY
from .thermo import compress, expand, gamma_of, gas_r, h_cp, phi_cp, t_from_h, t_from_phi

MODULE = "M07"
SLS_T = 288.15
SLS_P = 101325.0

#: parameter-file name -> kernel name for the parameters the separate-flow kernel reads directly
SF_DIRECT = {
    "dp_core_duct": "dp_core_duct",
    "dp_burner": "dp_burner",
    "eta_burner": "eta_burner",
    "lhv": "lhv",
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
    "tau_comb": "tau_comb",
    "tau_fmv": "tau_fmv",
    "tau_vg": "tau_vg",
    "vg_rate": "vg_rate",
    "vg_min": "vg_min",
    "vg_max": "vg_max",
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
    "cd18": "cd18",
    "dp_bypass_duct": "dp_bypass_duct",
    "gear_ratio": "gear_ratio",
    "eta_gearbox": "eta_gearbox",
    "p6_relax_tau": "p6_relax_tau",
    "fan_face_flow_share": "fan_face_flow_share",
    "fan_wc_mod_a": "fan_wc_mod_a",
    "fan_wc_mod_k": "fan_wc_mod_k",
    "fan_eff_mod_a": "fan_eff_mod_a",
    "fan_eff_mod_k": "fan_eff_mod_k",
    "hpc_wc_mod_a": "hpc_wc_mod_a",
    "hpc_wc_mod_k": "hpc_wc_mod_k",
    "hpc_eff_mod_a": "hpc_eff_mod_a",
    "hpc_eff_mod_k": "hpc_eff_mod_k",
    "rni_exp": "rni_exp",
    "fan_nc_mod_a": "fan_nc_mod_a",
    "fan_nc_mod_k": "fan_nc_mod_k",
    "hpc_nc_mod_a": "hpc_nc_mod_a",
    "hpc_nc_mod_k": "hpc_nc_mod_k",
    "gp_lag_tau": "gp_lag_tau",
    "gp_lag_kappa": "gp_lag_kappa",
}
#: base-layout slots the separate-flow kernel never reads (mixer, afterburner, nozzle actuator): fixed neutral
#: values so the vector is complete; they carry no physics and are not parameters of this topology
SF_UNUSED = {
    "k13": 1.0,
    "eps13": 1.0,
    "k5": 1.0,
    "eps5": 1.0,
    "wc6_des": 1.0,
    "r6_mix": 0.0,
    "dp_ab_dry": 0.0,
    "k_rayleigh": 0.0,
    "eta_ab": 0.0,
    "v6": 1.0,
    "tau_a8": 1.0,
    "tau_wfab": 0.1,
    "ab_t_ref": 1.0,
    "ab_p_ref": 1.0,
    "ab_n_p": 0.0,
    "ab_b_t": 0.0,
    "ab_t1_ref": 288.15,
    "ab_sigma": 0.0,
    "wfab_min": 1.0e9,
}


def load_proxy_engine_params(platform: str = "proxy_dashlink", **kw) -> ParamSet:
    """All M07 parameter sets of the proxy platform merged into one ParamSet (names unique across sets)."""
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


def _nozzle(pt: float, tt: float, f: float, war: float, ps0: float, w: float, cfg: float, cd: float, B):
    """(geometric area, gross thrust, exit-to-ambient pressure ratio) of a fixed convergent nozzle passing
    ``w``
    (the ``separate.nozzle_flow`` convention)."""
    r = float(gas_r(f, war, B))
    g = float(gamma_of(tt, f, war, B))
    pr = pt / ps0
    if pr <= 1.0 + 1e-6:
        raise ValueError(f"cycle does not close: nozzle total/ambient pressure ratio {pr:.4f} <= 1")
    area = w * math.sqrt(r * tt) / (pt * float(flow_function(pr, g))) / cd
    phi_t, _ = phi_cp(tt, f, war, B)
    t9 = float(t_from_phi(phi_t - r * math.log(pr), f, war, B, tt * pr ** (-(g - 1) / g)))
    ht, _ = h_cp(tt, f, war, B)
    h9, _ = h_cp(t9, f, war, B)
    return area, cfg * w * math.sqrt(2.0 * (float(ht) - float(h9))), pr


def _cycle(ps: ParamSet, tabs, t4: float, w2: float) -> dict[str, float]:
    """Station values of the separate-flow cycle at SLS ISA for a given T4 and inlet airflow."""
    B = tabs.thermo
    w = 0.0
    opr, fpr, bpr = _v(ps, "opr_design"), _v(ps, "fpr_design"), _v(ps, "bpr_design")
    dp_cd, dp_b, dp_byp = _v(ps, "dp_core_duct"), _v(ps, "dp_burner"), _v(ps, "dp_bypass_duct")
    eta_f, eta_c, eta_ht, eta_lt = (
        _v(ps, k) for k in ("eta_fan_design", "eta_hpc_design", "eta_hpt_design", "eta_lpt_design")
    )
    f_ngv, f_rot = _v(ps, "f_ngv"), _v(ps, "f_rot")
    eta_b, lhv, eta_m, eta_gb = _v(ps, "eta_burner"), _v(ps, "lhv"), _v(ps, "eta_mech"), _v(ps, "eta_gearbox")
    p_acc = _v(ps, "p_acc_design")
    t2, p2 = SLS_T, SLS_P
    p21 = p2 * fpr
    t21, dh_fan = compress(t2, fpr, eta_f, 0.0, w, B)
    p25 = p21 * (1.0 - dp_cd)
    p3 = opr * p2
    cpr = p3 / p25
    t25 = float(t21)
    t3, dh_hpc = compress(t25, cpr, eta_c, 0.0, w, B)
    w25 = w2 / (1.0 + bpr)
    w13 = w2 - w25
    wrot = f_rot * w25
    wngv = f_ngv * w25
    wcomb = w25 - wrot - wngv
    p4 = p3 * (1.0 - dp_b)
    h3, _ = h_cp(t3, 0.0, w, B)
    wf = wcomb * 0.02
    for _ in range(60):
        h4, _ = h_cp(t4, wf / wcomb, w, B)
        wf = wcomb * (h4 - h3) / (eta_b * lhv - h4)
    w41 = wcomb + wf + wngv
    w_air41 = w41 - wf
    f41 = wf / w_air41
    h41 = (w_air41 * h3 + eta_b * wf * lhv) / w41
    t41 = float(t_from_h(h41, f41, w, B, t4))
    pw_hpc = w25 * float(dh_hpc)
    pw_hpt = (pw_hpc + p_acc) / eta_m
    pr_hpt = _solve_pr_for_work(t41, pw_hpt / w41, eta_ht, f41, w, B)
    t45a, dh_hpt = expand(t41, pr_hpt, eta_ht, f41, w, B)
    p45 = p4 / pr_hpt
    h45a, _ = h_cp(t45a, f41, w, B)
    w45 = w41 + wrot
    h45 = (w41 * h45a + wrot * h3) / w45
    f45 = wf / (w_air41 + wrot)
    t45 = float(t_from_h(h45, f45, w, B, t45a))
    pw_fan = w2 * float(dh_fan)
    pr_lpt = _solve_pr_for_work(t45, pw_fan / (eta_m * eta_gb * w45), eta_lt, f45, w, B)
    t5, dh_lpt = expand(t45, pr_lpt, eta_lt, f45, w, B)
    p5 = p45 / pr_lpt
    return {
        "t2": t2, "p2": p2, "w2": w2, "t21": float(t21), "p21": p21, "t25": t25, "p25": p25, "w25": w25,
        "w13": w13, "t3": float(t3), "p3": p3, "cpr": cpr, "fpr": fpr, "wf": float(wf), "t4": t4, "p4": p4,
        "w41": float(w41), "t41": t41, "pr_hpt": pr_hpt, "t45a": float(t45a), "t45": t45, "p45": p45,
        "w45": float(w45), "pr_lpt": pr_lpt, "t5": float(t5), "p5": p5, "f45": float(f45), "f41": float(f41),
        "pw_fan": pw_fan, "pw_hpc": pw_hpc, "pw_hpt": float(w41 * dh_hpt), "pw_lpt": float(w45 * dh_lpt),
        "p13": p21 * (1.0 - dp_byp), "wcomb": float(wcomb),
    }  # fmt: skip


def design_point_sf(ps: ParamSet, tabs) -> DesignPoint:
    """Separate-flow design closure (module docstring): T4 from the EGT anchor, airflow from the fuel
    anchor."""
    B = tabs.thermo
    w = 0.0
    t5_target = _v(ps, "egt_design_anchor")
    wf_target = _v(ps, "wf_design_anchor")
    # Fixed point on (T4, W2): T4 by bisection on the EGT-station anchor at the current airflow (T5 depends on
    # the airflow only through the fixed accessory power), then the airflow rescaled to the fuel anchor (the
    # fuel flow is linear in the airflow at fixed T4 apart from the same small term). Deterministic; converges
    # to machine precision in a few passes.
    w2 = 100.0
    t4 = 1500.0
    for _ in range(30):
        lo, hi = 900.0, 2200.0
        for _ in range(100):
            mid = 0.5 * (lo + hi)
            if _cycle(ps, tabs, mid, w2)["t5"] < t5_target:
                lo = mid
            else:
                hi = mid
        t4 = 0.5 * (lo + hi)
        w2_new = w2 * wf_target / _cycle(ps, tabs, t4, w2)["wf"]
        done = abs(w2_new - w2) <= 1e-12 * w2
        w2 = w2_new
        if done:
            break
    st = _cycle(ps, tabs, t4, w2)
    # ---- nozzles (fixed areas from the design flows)
    cfg, cd8, cd18 = _v(ps, "cfg"), _v(ps, "cd8"), _v(ps, "cd18")
    a8, fg8, npr8 = _nozzle(st["p5"], st["t5"], st["f45"], w, SLS_P, st["w45"], cfg, cd8, B)
    a18, fg18, npr18 = _nozzle(st["p13"], st["t21"], 0.0, w, SLS_P, st["w13"], cfg, cd18, B)
    # ---- design speeds (fraction of the 100 % references, the measured top-knot relation)
    n1 = _v(ps, "n1_100pct") * _v(ps, "n1_design_frac")  # fan, rad/s
    n2 = _v(ps, "n2_100pct") * _v(ps, "n2_design_frac")
    gear = _v(ps, "gear_ratio")
    n1_rpm, n2_rpm, nlpt_rpm = n1 * RPM_PER_RADS, n2 * RPM_PER_RADS, gear * n1 * RPM_PER_RADS
    t2, p2, t25, p25 = st["t2"], st["p2"], st["t25"], st["p25"]
    n1c_des = n1_rpm / math.sqrt(t2 / T_STD)
    n2c_des = n2_rpm / math.sqrt(t25 / T_STD)
    w2c = w2 * math.sqrt(t2 / T_STD) / (p2 / P_STD)
    w25c = st["w25"] * math.sqrt(t25 / T_STD) / (p25 / P_STD)
    fan_ncd, fan_rld = _v(ps, "fan_ncmap_design"), _v(ps, "fan_rline_design")
    hpc_ncd, hpc_rld = _v(ps, "hpc_ncmap_design"), _v(ps, "hpc_rline_design")
    tnp, tpr = _v(ps, "turb_npmap_design"), _v(ps, "turb_prmap_design")
    fan_ax = np.unique(np.asarray(ps.value("fan_map_rline"), float))
    hpc_ax = np.unique(np.asarray(ps.value("hpc_map_rline"), float))
    der: dict[str, float] = {}
    fpr, cpr = st["fpr"], st["cpr"]
    der["s_nc_fan"] = n1c_des / fan_ncd
    der["s_pr_fan"] = (fpr - 1.0) / (_map_point(tabs.fan_nc, fan_ax, tabs.fan_pr, fan_ncd, fan_rld) - 1.0)
    der["s_wc_fan"] = w2c / _map_point(tabs.fan_nc, fan_ax, tabs.fan_wc, fan_ncd, fan_rld)
    der["s_eff_fan"] = _v(ps, "eta_fan_design") / _map_point(
        tabs.fan_nc, fan_ax, tabs.fan_eff, fan_ncd, fan_rld
    )
    der["s_nc_hpc"] = n2c_des / hpc_ncd
    der["s_pr_hpc"] = (cpr - 1.0) / (_map_point(tabs.hpc_nc, hpc_ax, tabs.hpc_pr, hpc_ncd, hpc_rld) - 1.0)
    der["s_wc_hpc"] = w25c / _map_point(tabs.hpc_nc, hpc_ax, tabs.hpc_wc, hpc_ncd, hpc_rld)
    der["s_eff_hpc"] = _v(ps, "eta_hpc_design") / _map_point(
        tabs.hpc_nc, hpc_ax, tabs.hpc_eff, hpc_ncd, hpc_rld
    )
    g_eq = _v(ps, "gamma_turb_eq")
    for name, n_rpm, tin, pin, pr, wt, eta, prch in (
        ("hpt", n2_rpm, st["t41"], st["p4"], st["pr_hpt"], st["w41"], _v(ps, "eta_hpt_design"),
         _v(ps, "pr_choke_hpt")),
        ("lpt", nlpt_rpm, st["t45"], st["p45"], st["pr_lpt"], st["w45"], _v(ps, "eta_lpt_design"),
         _v(ps, "pr_choke_lpt")),
    ):  # fmt: skip
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
    r_air = float(gas_r(0.0, w, B))
    t3, p3 = st["t3"], st["p3"]
    g3 = float(gamma_of(t3, 0.0, w, B))
    m3 = _v(ps, "m3_design")
    q_frac = 1.0 - (1.0 + 0.5 * (g3 - 1.0) * m3 * m3) ** (-g3 / (g3 - 1.0))
    der["a3_eff"] = st["w25"] * math.sqrt(r_air * t3 / (2.0 * q_frac)) / p3
    f_ngv, f_rot = _v(ps, "f_ngv"), _v(ps, "f_rot")
    der["c_ngv"] = f_ngv / (1.0 - f_ngv - f_rot)
    der["n1_des"] = n1
    der["n2_des"] = n2
    der["n1c_des_rpm"] = n1c_des
    der["n2c_des_rpm"] = n2c_des
    der["w2_des"] = w2
    der["w41_des"] = st["w41"]
    der["wc3_des"] = st["w25"] * math.sqrt(t3) / p3
    der["wf_des"] = st["wf"]
    der["tm_ref"] = 0.5 * (st["t41"] + st["t45a"])
    der["tc_ref"] = t3 + _v(ps, "c_case") * (st["t41"] - t3)
    der["f_stoich"] = _stoich_far(ps)
    der["a8_min"] = a8
    der["a8_max"] = a8
    der["a8_rate"] = 0.0
    for k in ("k13", "eps13", "k5", "eps5", "wc6_des", "r6_mix"):
        der[k] = SF_UNUSED[k]
    assert set(der) == set(DERIVED_P), sorted(set(der) ^ set(DERIVED_P))
    der["a18"] = a18
    der["wc21_des"] = w2 * math.sqrt(st["t21"]) / st["p21"]
    # rotor inertias from the rotor energy times (I = 2 H P / omega^2), LP reflected to the fan shaft
    der["i_lp"] = 2.0 * _v(ps, "h_lp_s") * st["pw_fan"] / (n1 * n1)
    der["i_hp"] = 2.0 * _v(ps, "h_hp_s") * st["pw_hpc"] / (n2 * n2)
    vg_ref = (
        float(interp1(tabs.fvg_x, tabs.fvg_y, 1.0)),
        float(interp1(tabs.cvg_x, tabs.cvg_y, 1.0)),
    )
    stations = {
        **{k: v for k, v in st.items() if k not in ("f41",)},
        "p6": SLS_P,
        "a8": a8,
        "a18": a18,
        "npr8": npr8,
        "npr18": npr18,
        "fn_dry": fg8 + fg18,
        "fg_core": fg8,
        "fg_bypass": fg18,
        "bpr": st["w13"] / st["w25"],
        "n1": n1,
        "n2": n2,
        "n1_100": _v(ps, "n1_100pct"),
        "n2_100": _v(ps, "n2_100pct"),
        "sfc_dry": st["wf"] / (fg8 + fg18),
        "w8": st["w45"],
    }
    checks = {"t5_anchor_err": st["t5"] - t5_target, "wf_anchor_err": st["wf"] - wf_target}
    return DesignPoint(stations=stations, derived=der, max_ab={}, vg_ref=vg_ref, checks=checks)


@dataclass(frozen=True)
class SeparateFixedModel(EngineModel):
    """``EngineModel`` of the separate_fixed topology (parameter vector ``separate.SF_P_NAMES``)."""

    topology: str = TOPOLOGY

    def with_p(self, **values: float) -> SeparateFixedModel:
        """A copy with some kernel parameters replaced by name (``SF_P_NAMES``; sweeps, calibration)."""
        p = self.p.copy()
        for k, v in values.items():
            p[SF_PI[k]] = v
        p.flags.writeable = False
        return replace(self, p=p)


def build_separate_model(ps: ParamSet | None = None, *, n_sub: int | None = None) -> SeparateFixedModel:
    """Assemble the separate_fixed M07 model from a ParamSet (default: the proxy_dashlink registry)."""
    ps = ps if ps is not None else load_proxy_engine_params()
    tabs = build_tables(ps)
    dp = design_point_sf(ps, tabs)
    vals: dict[str, float] = {}
    for yname, kname in SF_DIRECT.items():
        vals[kname] = _v(ps, yname)
    for k, v in SF_UNUSED.items():
        vals.setdefault(k, v)
    vals.update(dp.derived)
    missing = [n for n in SF_P_NAMES if n not in vals]
    if missing:
        raise ValueError(f"separate_fixed parameters missing: {missing}")
    p = np.array([vals[n] for n in SF_P_NAMES], dtype=np.float64)
    p.flags.writeable = False
    ns = int(ps.value("n_sub")) if n_sub is None else int(n_sub)
    n_delay = round(_v(ps, "fuel_transport_delay") * TRUTH_HZ)
    return SeparateFixedModel(ps, p, tabs, dp, ns, n_delay, 1.0 / TRUTH_HZ)


__all__ = [
    "SF_DIRECT",
    "SF_UNUSED",
    "SeparateFixedModel",
    "build_separate_model",
    "design_point_sf",
    "load_proxy_engine_params",
]
