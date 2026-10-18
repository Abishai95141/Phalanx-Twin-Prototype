"""Proxy-mode configuration (W2.4a, architecture §14.3): the build's engine-side chain in the DASHlink setup.

``load_proxy_config`` assembles, from ``configs/proxy_dashlink/`` only (plus the standard USSA-76 atmosphere
of the Tejas M03 set):

- M07: the ``separate_fixed`` topology model (AD-43), 4 engines;
- M08: governor structure with the autothrottle outer loop (proxy schedules, A-W2.4a-13/14), its FADEC clock;
- M03: the AD-32/AD-46 disturbance bank (incl. ``fan_face``) on the replay flight condition;
- M12: per-engine sensor instances (U3) for the M08 lanes and the recorded DASHlink words;
- M13: the controller lanes (FADEC clock) and the DASHlink recording (double quantiser, lattice, ACMS clock);
- M09 boundary: customer bleed per pack/anti-ice and the power off-take per engine (``proxy.bleed``), applied
  from the recorded bleed/air-conditioning/anti-ice discretes;
- the demand pre-map (``proxy.demand``): the MEASURED Mach, delta and theta terms of the fuel-control law fed
  through M08's lever input (effective lever).

Overrides (``engine``, ``fadec_p``, ``factors``, ``k_eta_fan_face`` ...) exist for the MF1 sweeps; they change
parameter values only, never structure. The steady plant levels (M07 off-design map modifiers, M09 bleed and
off-take) are identified on 687-CAL steady points (W2.4a-2 stage 1, ``analysis/proxy_quicklook``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from phalanx.acquisition.config import AcqConfig, acquisition_clock, build_acquisition_config
from phalanx.acquisition.module import lane_channels
from phalanx.core.module import Param, ParamSet
from phalanx.core.time import ClockDomain
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_param_set, load_params
from phalanx.engine.separate_design import SeparateFixedModel, build_separate_model
from phalanx.environment.config import EnvConfig, factors_from_paramset, load_env_config
from phalanx.environment.disturbances import Factor
from phalanx.fadec.params import FadecConfig
from phalanx.sensors.config import SensorConfig, build_sensor_config

from .bleed import BleedParams
from .demand import DemandPremap

#: no customer bleed and no off-take (the default of a configuration built without the M09 boundary set)
NO_BLEED = BleedParams.off()

PLATFORM = "proxy_dashlink"
N_ENGINES = 4
SERIALS = ("E1", "E2", "E3", "E4")
FADEC_RATE_HZ = 60.0
_FADEC_SETS = ("control", "autothrottle", "validator", "monitors")
#: the recorded DASHlink engine words (proxy dictionary) and their battery families
RECORDED = {"ENG.N1.REC": "N1", "ENG.N2.REC": "N2", "ENG.T5.REC": "EGT", "ENG.FF.REC": "FF"}


def load_proxy_fadec_params(dictionary=None) -> ParamSet:
    """All M08 proxy parameters as one ParamSet (``fadec.params.load_fadec_params`` convention) with the proxy
    dictionary's reference speeds."""
    d = dictionary if dictionary is not None else load_dictionary(platform=PLATFORM)
    sets = load_params("M08", platform=PLATFORM)
    merged: dict[str, Param] = {}
    for name in _FADEC_SETS:
        for k in sets[name]:
            if k in merged:
                raise ValueError(f"M08 parameter {k!r} appears in more than one set")
            merged[k] = sets[name][k]
    ref = d.param_set("channel_reference")
    merged["n1_ref"] = ref["n1_100pct"]
    merged["n2_ref"] = ref["n2_100pct"]
    return ParamSet(f"{PLATFORM}.M08", merged)


def load_proxy_env_config() -> EnvConfig:
    """Standard atmosphere/turbulence sets (USSA-76, TRANSFER: standard) with the proxy disturbance
    factors."""
    sets = load_params("M03", platform=PLATFORM)
    return load_env_config("tejas").with_factors(factors_from_paramset(sets["disturbances"]))


@dataclass(frozen=True)
class ProxyConfig:
    """Everything a proxy run needs (immutable)."""

    dictionary: object
    engine: SeparateFixedModel
    fadec_params: ParamSet
    fadec: FadecConfig
    clock: ClockDomain
    env: EnvConfig
    sensors: SensorConfig
    lanes: AcqConfig
    recording: AcqConfig
    m12_params: ParamSet
    m13_params: ParamSet
    n_engines: int = N_ENGINES
    serials: tuple[str, ...] = SERIALS
    #: customer bleed and power off-take from the recorded discretes (``proxy.bleed``; M09 boundary set)
    bleed: BleedParams = NO_BLEED
    #: the MEASURED flight-condition terms of the fuel-control law fed through M08's lever input
    #: (``proxy.demand``; M08 ``demand_premap`` set); None = the PLA-only table demand
    premap: DemandPremap | None = None

    @property
    def lane_channels(self) -> tuple[str, ...]:
        return self.lanes.channels

    @property
    def recorded_channels(self) -> tuple[str, ...]:
        return self.recording.channels

    def with_factors(self, factors: Sequence[Factor]) -> ProxyConfig:
        return replace(self, env=self.env.with_factors(tuple(factors)))

    def with_engine(self, **p: float) -> ProxyConfig:
        return replace(self, engine=self.engine.with_p(**p))

    def with_fadec(self, **p: float) -> ProxyConfig:
        return replace(self, fadec=self.fadec.with_p(**p))


def load_proxy_config(*, engine: SeparateFixedModel | None = None, n_engines: int = N_ENGINES) -> ProxyConfig:
    """Assemble the proxy configuration (see the module docstring)."""
    d = load_dictionary(platform=PLATFORM)
    model = engine if engine is not None else build_separate_model()
    fp = load_proxy_fadec_params(d)
    clock = acquisition_clock("FADEC", FADEC_RATE_HZ, platform=PLATFORM)
    premap = DemandPremap.from_params(load_param_set("M08", "demand_premap", platform=PLATFORM))
    fcfg = FadecConfig.build(fp, clock, autothrottle=True)
    if premap.at_floor:  # M08 option: the A/T demand floored at the fed (idle-stop) lever's demand
        fcfg = fcfg.with_cfg(at_floor_lever=1)
    sens = build_sensor_config(d, platform=PLATFORM, n_engines=n_engines)
    lanes = build_acquisition_config(
        d, lane_channels(d, sens, "FADEC"), sensor_channels=sens.channels, platform=PLATFORM
    )
    rec_ids = tuple(c for c in sens.channels if c.split(":", 1)[0] in RECORDED)
    rec = build_acquisition_config(d, rec_ids, sensor_channels=sens.channels, platform=PLATFORM)
    return ProxyConfig(
        dictionary=d,
        engine=model,
        fadec_params=fp,
        fadec=fcfg,
        clock=clock,
        env=load_proxy_env_config(),
        sensors=sens,
        lanes=lanes,
        recording=rec,
        m12_params=load_param_set("M12", "constants", platform=PLATFORM),
        m13_params=load_param_set("M13", "noise_n1_rec", platform=PLATFORM),
        n_engines=n_engines,
        serials=tuple(f"E{k + 1}" for k in range(n_engines)),
        bleed=BleedParams.from_params(load_param_set("M09", "boundary", platform=PLATFORM)),
        premap=premap,
    )


def factor_table(cfg: ProxyConfig) -> np.ndarray:
    """The disturbance factors as a (n_factors, 13) table (fid, scope, group, form, tau, omega, zeta, 6
    loadings) for reporting."""
    rows = []
    for f in cfg.env.factors:
        ld = list(f.loadings) + [0.0] * (6 - len(f.loadings))
        rows.append([f.fid, f.scope, f.group, f.form, f.tau_s, f.omega_rad_s, f.zeta, *ld])
    return np.asarray(rows, dtype=float)


def config_root() -> Path:
    """``configs/`` of this checkout (the proxy files live under ``configs/proxy_dashlink``)."""
    return Path(__file__).resolve().parents[3] / "configs"


__all__ = [
    "N_ENGINES",
    "PLATFORM",
    "RECORDED",
    "SERIALS",
    "ProxyConfig",
    "config_root",
    "factor_table",
    "load_proxy_config",
    "load_proxy_env_config",
    "load_proxy_fadec_params",
]
