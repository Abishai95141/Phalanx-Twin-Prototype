"""Typed M21 configuration (configs/tejas/params/M21.yaml) and the M22 comparison defaults (M22.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from phalanx.core.module import ParamSet
from phalanx.dictionary.params import load_params
from phalanx.maintenance.config import merged_param_set
from phalanx.maintenance.timebase import to_s

from .epochs import DecisionCalendar


@dataclass(frozen=True)
class M21Config:
    decision_times_s: tuple[int, ...]
    params: ParamSet = field(repr=False)

    def calendar(self, epoch_utc_ns: int, tz_offset_s: int) -> DecisionCalendar:
        return DecisionCalendar(int(epoch_utc_ns), int(tz_offset_s), self.decision_times_s)


def load_m21_config(platform: str = "tejas", **kw) -> M21Config:
    sets = load_params("M21", platform=platform, **kw)
    times = tuple(sorted({to_s(x) for x in np.atleast_1d(sets["epochs"].value("decision_times_local"))}))
    return M21Config(decision_times_s=times, params=merged_param_set("M21", sets))


@dataclass(frozen=True)
class M22Config:
    ci_level: float
    min_pairs: int
    params: ParamSet = field(repr=False)


def load_m22_config(platform: str = "tejas", **kw) -> M22Config:
    sets = load_params("M22", platform=platform, **kw)
    c = sets["compare"]
    return M22Config(
        ci_level=float(c.value("ci_level")),
        min_pairs=int(c.value("min_pairs")),
        params=merged_param_set("M22", sets),
    )
