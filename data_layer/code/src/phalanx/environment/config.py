"""M03 configuration: parameter sets from ``configs/<platform>/params/M03.yaml`` as typed objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from phalanx.core.module import Param, ParamSet
from phalanx.dictionary.params import load_params

from .atmosphere import Constants, UssaLayers, magnus_vector
from .climatology import Climatology, SamplerParams
from .disturbances import Factor
from .turbulence import CLASS_LIGHT, CLASS_MODERATE, CLASS_NONE, CLASS_SEVERE, MODEL_DRYDEN


@dataclass(frozen=True)
class TurbulenceConfig:
    model: int
    b_span: float
    l_hi_dryden: float
    l_hi_von_karman: float
    sigma_hi: tuple[float, float, float, float]  # by class (none = 0)
    w20: tuple[float, float, float, float]
    v_min: float
    z0_cat_c: float
    z0_other: float
    gust_rate: float  # 1/s
    gust_amp_sd: float
    gust_length: tuple[float, float]

    @property
    def l_hi(self) -> float:
        return self.l_hi_dryden if self.model == MODEL_DRYDEN else self.l_hi_von_karman


@dataclass(frozen=True)
class EnvConfig:
    constants: Constants
    layers: UssaLayers
    magnus: np.ndarray
    vapour_scale_height: float
    climatology: Climatology
    sampler: SamplerParams
    turbulence: TurbulenceConfig
    factors: tuple[Factor, ...]
    params: ParamSet  # merged, for hashing / provenance

    def with_turbulence(self, **changes) -> EnvConfig:
        from dataclasses import replace

        return replace(self, turbulence=replace(self.turbulence, **changes))

    def with_factors(self, factors: tuple[Factor, ...]) -> EnvConfig:
        from dataclasses import replace

        return replace(self, factors=tuple(factors))


def merged_paramset(name: str, sets: dict[str, ParamSet]) -> ParamSet:
    out: dict[str, Param] = {}
    for sname in sorted(sets):
        for k, p in sets[sname].items():
            out[f"{sname}__{k}"] = p
    return ParamSet(name, out)


def factors_from_paramset(ps: ParamSet) -> tuple[Factor, ...]:
    v = ps.value
    fid = np.asarray(v("factor_id"), dtype=float)
    cols = [
        np.asarray(v(n), dtype=float)
        for n in (
            "load_fuel_metering",
            "load_combustor_eff",
            "load_inlet_recovery",
            "load_shaft_load",
            "load_fan_face",
            "load_bleed_pto",
        )
    ]
    hyd = np.asarray(v("load_hyd"), dtype=float)
    out = []
    for k in range(fid.size):
        group = int(np.asarray(v("factor_group"))[k])
        loads = tuple(float(c[k]) for c in cols) if group == 0 else (float(hyd[k]),)
        out.append(
            Factor(
                fid=int(fid[k]),
                scope=int(np.asarray(v("factor_scope"))[k]),
                group=group,
                form=int(np.asarray(v("factor_form"))[k]),
                tau_s=float(np.asarray(v("factor_tau"))[k]),
                omega_rad_s=float(np.asarray(v("factor_omega"))[k]),
                zeta=float(np.asarray(v("factor_zeta"))[k]),
                loadings=loads,
            )
        )
    return tuple(out)


def load_env_config(platform: str = "tejas", config_root: Path | None = None) -> EnvConfig:
    sets = load_params("M03", platform=platform, config_root=config_root)
    a = sets["atmosphere"].value
    consts = Constants(
        r_star=float(a("r_star")),
        m0=float(a("m0")),
        g0=float(a("g0")),
        r0=float(a("r0")),
        gamma=float(a("gamma")),
        m_water=float(a("m_water")),
    )
    layers = UssaLayers(
        h_base=np.asarray(a("ussa_h_base"), dtype=float),
        lapse=np.asarray(a("ussa_lapse"), dtype=float),
        t0=float(a("ussa_t0")),
        p0=float(a("ussa_p0")),
    )
    t = sets["turbulence"].value
    sig = (0.0, float(t("sigma_hi_light")), float(t("sigma_hi_moderate")), float(t("sigma_hi_severe")))
    w20 = (0.0, float(t("w20_light")), float(t("w20_moderate")), float(t("w20_severe")))
    assert (CLASS_NONE, CLASS_LIGHT, CLASS_MODERATE, CLASS_SEVERE) == (0, 1, 2, 3)
    gl = np.asarray(t("gust_length"), dtype=float)
    turb = TurbulenceConfig(
        model=int(t("model")),
        b_span=float(t("b_span")),
        l_hi_dryden=float(t("l_hi_dryden")),
        l_hi_von_karman=float(t("l_hi_von_karman")),
        sigma_hi=sig,
        w20=w20,
        v_min=float(t("v_min")),
        z0_cat_c=float(t("z0_cat_c")),
        z0_other=float(t("z0_other")),
        gust_rate=float(t("gust_rate")),
        gust_amp_sd=float(t("gust_amp_sd")),
        gust_length=(float(gl[0]), float(gl[1])),
    )
    return EnvConfig(
        constants=consts,
        layers=layers,
        magnus=magnus_vector(float(a("magnus_a")), float(a("magnus_b")), float(a("magnus_c"))),
        vapour_scale_height=float(a("vapour_scale_height")),
        climatology=Climatology.from_paramset(sets["climatology"]),
        sampler=SamplerParams.from_paramset(sets["climatology"]),
        turbulence=turb,
        factors=factors_from_paramset(sets["disturbances"]),
        params=merged_paramset(f"{platform}.M03", sets),
    )
