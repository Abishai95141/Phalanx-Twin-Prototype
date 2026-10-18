"""Typed M18 configuration built from the parameter registry (configs/tejas/params/M18.yaml + M18/*.yaml).

Every number comes from the registry with its evidence tag (RULES.md rule 3); this module only converts units
to whole seconds and derives the two fitted quantities:

- the wholesale supply lead-time log-normal, fitted by least squares on the probit scale to the CAG IL-76 AOG
  timeliness bins (conditional on the four reported bins, which hold 61.9 % of the demands; the unaccounted
  38.1 % and the effect of the conditional choice are logged in A-W1.8-10);
- the servicing-duration median from the on-time fraction: P(D <= prescribed) = on_time (CAG 24/2017).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
from scipy.stats import norm

from phalanx.core.module import ParamSet
from phalanx.dictionary.params import load_params

from .catalogue import Catalogue, CodeTables, load_catalogue, load_codes
from .timebase import DAY_S, to_s

PRIORITIES = ("AOG", "MCM", "PHU")


def merged_param_set(module: str, sets: dict[str, ParamSet]) -> ParamSet:
    """One ParamSet with ``<set>__<param>`` names (a module takes a single hashed ParamSet)."""
    from phalanx.core.module import ParamSet as PS

    params = {}
    for sname in sorted(sets):
        for pname, p in sets[sname].items():
            params[f"{sname}__{pname}"] = p
    return PS(f"tejas.{module}", params)


def fit_lognormal_to_bins(upper_edges_s: list[float], shares: list[float]) -> tuple[float, float]:
    """(mu, sigma) of ln T fitted to cumulative bin shares (conditional on the reported bins) by least squares
    on the probit scale. The last share is the open-ended bin above the last edge."""
    if len(shares) != len(upper_edges_s) + 1:
        raise ValueError("need one more share than edges (the open upper bin)")
    tot = float(sum(shares))
    cum = np.cumsum(np.asarray(shares[:-1], dtype=np.float64)) / tot
    z = norm.ppf(cum)
    x = np.log(np.asarray(upper_edges_s, dtype=np.float64))
    zb, xb = z.mean(), x.mean()
    sigma = float(((z - zb) * (x - xb)).sum() / ((z - zb) ** 2).sum())
    mu = float(xb - sigma * zb)
    return mu, sigma


@dataclass(frozen=True)
class DefectRates:
    cann_underreport: float
    missing_part_record: float
    wrong_form: float
    recon_lag_fraction: float
    recon_lag_mean_s: int
    text_noise_rate: float
    xxx_serial: float
    duplicate_snag: float
    unfilled_logbook: float
    underreported_tail: float

    def disabled(self) -> DefectRates:
        return DefectRates(0.0, 0.0, 0.0, 0.0, self.recon_lag_mean_s, 0.0, 0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class M18Config:
    tz_offset_s: int
    shift_start_s: int
    shift_end_s: int
    teams: int
    crew: int
    slots: int
    bin_width_s: int
    sortie_entry_delay_s: int
    debrief_delay_s: int
    hms_review_delay_s: int
    check_s: int
    dur_sigma: float
    monitor_flights: int
    p_replace_unconfirmed: float
    lead_mu: float  # ln(seconds)
    lead_sigma: float
    tejas_supply_factor: float
    priority_mult: tuple[float, float, float]
    issue_delay_s: int
    expedite_factor: float
    transfer_s: int
    p_condemn: float
    srv_interval_fh_s: tuple[int, ...]
    srv_interval_s: tuple[int, ...]
    srv_duration_s: tuple[int, ...]
    srv_median_factor: float
    srv_sigma: float
    srv_pod: tuple[float, ...]
    pod_borescope: float
    pod_ndt: float
    pod_conditional: float
    inspection_s: int
    p_out_of_limits: float
    cann_min_awp_s: int
    cann_extra_mh_h: float
    mod_s: int
    sw_s: int
    wash_s: int
    mh_cost: float
    expedite_premium: float
    defects: DefectRates
    catalogue: Catalogue = field(repr=False)
    codes: CodeTables = field(repr=False)
    params: ParamSet = field(repr=False)
    overrides: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def n_servicing(self) -> int:
        return len(self.srv_interval_fh_s)

    def lead_median_days(self) -> float:
        return math.exp(self.lead_mu) / DAY_S

    def with_catalogue_values(self, changes: Mapping[str, Mapping[str, float]]) -> M18Config:
        """A copy with some catalogue class values replaced (sweeps, deterministic tests)."""
        return replace(self, catalogue=self.catalogue.with_values(changes))

    def with_values(self, **values: Any) -> M18Config:
        """A copy with some scalar fields replaced (e.g. ``pod_borescope=1.0`` in a test or a sweep). The
        module's parameter hash records the change through ``cfg_overrides``."""
        unknown = sorted(set(values) - set(self.__dataclass_fields__))
        if unknown:
            raise KeyError(f"unknown M18Config fields {unknown}")
        return replace(self, **values, overrides={**dict(self.overrides), **values})


def load_m18_config(platform: str = "tejas", **kw) -> M18Config:
    sets = load_params("M18", platform=platform, **kw)

    def v(s: str, p: str):
        return sets[s].value(p)

    edges = [float(x) for x in np.asarray(v("supply", "aog_bin_upper_days"))]
    shares = [float(x) for x in np.asarray(v("supply", "aog_bin_share"))]
    mu, sigma = fit_lognormal_to_bins(edges, shares)
    on_time = float(v("servicing", "on_time_fraction"))
    srv_sigma = float(v("servicing", "overrun_sigma"))
    d = sets["defects"]
    defects = DefectRates(
        cann_underreport=float(d.value("cann_underreport")),
        missing_part_record=float(d.value("missing_part_record")),
        wrong_form=float(d.value("wrong_form")),
        recon_lag_fraction=float(d.value("recon_lag_fraction")),
        recon_lag_mean_s=to_s(d.value("recon_lag_mean")),
        text_noise_rate=float(d.value("text_noise_rate")),
        xxx_serial=float(d.value("xxx_serial")),
        duplicate_snag=float(d.value("duplicate_snag")),
        unfilled_logbook=float(d.value("unfilled_logbook")),
        underreported_tail=float(d.value("underreported_tail")),
    )
    pm = [float(x) for x in np.asarray(v("supply", "priority_mult"))]
    return M18Config(
        tz_offset_s=to_s(v("org", "tz_offset")),
        shift_start_s=to_s(v("org", "shift_start")),
        shift_end_s=to_s(v("org", "shift_end")),
        teams=int(v("org", "teams_per_base")),
        crew=int(v("org", "crew_size")),
        slots=int(v("org", "servicing_slots")),
        bin_width_s=to_s(v("org", "bin_width")),
        sortie_entry_delay_s=to_s(v("timing", "sortie_entry_delay")),
        debrief_delay_s=to_s(v("timing", "debrief_delay")),
        hms_review_delay_s=to_s(v("timing", "hms_review_delay")),
        check_s=to_s(v("timing", "check_hours")),
        dur_sigma=float(v("timing", "duration_sigma")),
        monitor_flights=int(v("troubleshoot", "monitor_flights")),
        p_replace_unconfirmed=float(v("troubleshoot", "p_replace_unconfirmed")),
        lead_mu=mu,
        lead_sigma=sigma,
        tejas_supply_factor=float(v("supply", "tejas_supply_factor")),
        priority_mult=(pm[0], pm[1], pm[2]),
        issue_delay_s=to_s(v("supply", "issue_delay")),
        expedite_factor=float(v("supply", "expedite_factor")),
        transfer_s=to_s(v("supply", "transfer_days")),
        p_condemn=float(v("shop", "p_condemn")),
        srv_interval_fh_s=tuple(to_s(x) for x in np.asarray(v("servicing", "interval_fh"))),
        srv_interval_s=tuple(to_s(x) for x in np.asarray(v("servicing", "interval_days"))),
        srv_duration_s=tuple(to_s(x) for x in np.asarray(v("servicing", "duration_days"))),
        srv_median_factor=math.exp(-srv_sigma * float(norm.ppf(on_time))),
        srv_sigma=srv_sigma,
        srv_pod=tuple(float(x) for x in np.asarray(v("servicing", "pod"))),
        pod_borescope=float(v("inspection", "pod_borescope")),
        pod_ndt=float(v("inspection", "pod_ndt")),
        pod_conditional=float(v("inspection", "pod_conditional")),
        inspection_s=to_s(v("inspection", "inspection_hours")),
        p_out_of_limits=float(v("inspection", "p_out_of_limits")),
        cann_min_awp_s=to_s(v("cann", "min_awp_hours")),
        cann_extra_mh_h=float(v("cann", "extra_mh")) / 3600.0,
        mod_s=to_s(v("mods", "mod_hours")),
        sw_s=to_s(v("mods", "sw_load_hours")),
        wash_s=to_s(v("mods", "wash_hours")),
        mh_cost=float(v("cost", "mh_cost")),
        expedite_premium=float(v("cost", "expedite_premium")),
        defects=defects,
        catalogue=load_catalogue(),
        codes=load_codes(),
        params=merged_param_set("M18", sets),
    )
