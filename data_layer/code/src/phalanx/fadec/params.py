"""M08 configuration: parameter sets (`configs/<platform>/params/M08.yaml`) -> kernel vectors and tables.

`load_fadec_params(platform)` merges the M08 sets (`control`, `autothrottle`, `validator`, `monitors`) with
the
dictionary reference speeds (`channel_reference`: 100 % N1 = 13,270 rpm, 100 % N2 = 16,810 rpm) into one
ParamSet. `FadecConfig.build(params, clock, ...)` turns it into the AD-22 flat parameter vector `p`, the
`Tables`
NamedTuple and the integer config `cfg`. Times given in seconds become frame counts at the clock's nominal
rate
(exact rational rounding); speed thresholds given as fractions of 100 % are converted to rad/s.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np

from phalanx.core.module import Param, ParamSet
from phalanx.core.time import ClockDomain
from phalanx.dictionary.params import load_params

from .codes import NS
from .layout import C_LAYOUT, NC, NP_, P_LAYOUT, P_NAMES, Tables
from .ports import DEFAULT_CLOCK, LANES_PER_SENSOR

_SETS = ("control", "autothrottle", "validator", "monitors")
_SENSOR_KEYS = ("n1", "n2", "t1", "t25", "ps3", "t5")


def _reference_speeds() -> dict[str, Param]:
    from phalanx.dictionary import load_dictionary

    ps = load_dictionary().param_set("channel_reference")
    return {"n1_ref": ps["n1_100pct"], "n2_ref": ps["n2_100pct"]}


def load_fadec_params(
    platform: str = "tejas", *, config_root: Path | None = None, repo_root: Path | None = None
) -> ParamSet:
    """All M08 parameters of `platform` as one ParamSet (SI values, provenance) plus the reference speeds."""
    sets = load_params("M08", platform=platform, config_root=config_root, repo_root=repo_root)
    merged: dict[str, Param] = {}
    for name in _SETS:
        for k in sets[name]:
            if k in merged:
                raise ValueError(f"M08 parameter {k!r} appears in more than one set")
            merged[k] = sets[name][k]
    merged.update(_reference_speeds())
    return ParamSet(f"{platform}.M08", merged)


def _frames(seconds: float, f_nom: Fraction) -> int:
    """Seconds -> whole FADEC frames at the nominal rate (round half up; exact rational arithmetic)."""
    x = Fraction(seconds) * f_nom
    return int((x + Fraction(1, 2)) // 1)


def _arr(params: ParamSet, name: str) -> np.ndarray:
    a = np.ascontiguousarray(np.asarray(params.value(name), dtype=np.float64))
    if a.ndim != 1 or a.size < 2:
        raise ValueError(f"table {name} must be a 1-D array with >= 2 points")
    return a


@dataclass(frozen=True)
class FadecConfig:
    """Everything the kernel needs besides state: `p`, `tables`, `cfg` and the nominal frame period `dt`."""

    p: np.ndarray
    tables: Tables
    cfg: np.ndarray
    dt: float
    clock: ClockDomain

    @classmethod
    def build(
        cls,
        params: ParamSet,
        clock: ClockDomain = DEFAULT_CLOCK,
        *,
        autothrottle: bool = False,
        lanes_per_sensor: tuple[int, ...] = LANES_PER_SENSOR,
    ) -> FadecConfig:
        f_nom = Fraction(clock.f_nom_hz)
        dt = float(1 / f_nom)
        v = params.value
        n1r, n2r = float(v("n1_ref")), float(v("n2_ref"))
        derived = {
            "trim_alpha": dt / float(v("trim_tau")),
            "n2dot_alpha": dt / float(v("n2dot_tau")),
            # rate filters of the limiter anticipation (W2.1 entry gate 4): bound the high-frequency gain of
            # the lead path, kp * lead / tau, while keeping the anticipation of slow approaches
            "n1dot_alpha": dt / float(v("n1dot_tau")),
            "ps3dot_alpha": dt / float(v("ps3dot_tau")),
            # exact discrete first-order pole; tau = 0 means no filter
            "ps3_alpha": 1.0 if float(v("ps3_tau")) <= 0.0 else float(-np.expm1(-dt / float(v("ps3_tau")))),
        }
        vals = []
        for name in P_NAMES:
            x = derived[name] if name in derived else v(name)
            if isinstance(x, bool) or not isinstance(x, int | float):
                raise ValueError(f"kernel parameter {name!r} must be a real scalar")
            vals.append(float(x))
        p = np.array(vals, dtype=np.float64)
        assert p.size == NP_

        def speed_scale(key: str) -> float:
            return n1r if key == "n1" else (n2r if key == "n2" else 1.0)

        v_lo = np.array([float(v(f"range_lo_{k}")) * speed_scale(k) for k in _SENSOR_KEYS])
        v_hi = np.array([float(v(f"range_hi_{k}")) * speed_scale(k) for k in _SENSOR_KEYS])
        v_rate = np.array([float(v(f"rate_{k}")) * speed_scale(k) for k in _SENSOR_KEYS])
        v_xc = np.array([float(v(f"xc_tol_{k}")) * speed_scale(k) for k in _SENSOR_KEYS])
        v_safe = np.array([float(np.sign(float(v(f"safe_{k}")))) for k in _SENSOR_KEYS])
        if np.any(v_safe == 0.0):
            raise ValueError("safe_* directions must be +1 or -1")
        n1_x, n1_y = _arr(params, "obm_n1_n2_x"), _arr(params, "obm_n1_n2_y")
        if np.any(np.diff(n1_y) <= 0):
            raise ValueError("on-board N1c(N2c) relation must be strictly increasing (it is inverted)")
        tables = Tables(
            n2c_pla_x=_arr(params, "n2c_pla_x"),
            n2c_pla_y=_arr(params, "n2c_pla_y"),
            a8_pla_x=_arr(params, "a8_pla_x"),
            a8_pla_y=_arr(params, "a8_pla_y"),
            ru_x=_arr(params, "ru_ref_x"),
            ru_y=_arr(params, "ru_ref_y"),
            ruff_x=_arr(params, "ru_ff_x"),
            ruff_y=_arr(params, "ru_ff_y"),
            ab_ru_x=_arr(params, "ab_ru_x"),
            ab_ru_y=_arr(params, "ab_ru_y"),
            fvg_x=_arr(params, "fvg_x"),
            fvg_y=_arr(params, "fvg_y"),
            cvg_x=_arr(params, "cvg_x"),
            cvg_y=_arr(params, "cvg_y"),
            n1lim_x=_arr(params, "n1lim_t1_x"),
            n1lim_y=_arr(params, "n1lim_t1_y"),
            t5lim_x=_arr(params, "t5lim_t1_x"),
            t5lim_y=_arr(params, "t5lim_t1_y"),
            fo_x=_arr(params, "fo_t5_x"),
            fo_y=_arr(params, "fo_t5_y"),
            obm_n1_x=n1_x,
            obm_n1_y=n1_y,
            obm_n2_x=np.ascontiguousarray(n1_y.copy()),
            obm_n2_y=np.ascontiguousarray(n1_x.copy()),
            obm_pr3_x=_arr(params, "obm_pr3_x"),
            obm_pr3_y=_arr(params, "obm_pr3_y"),
            obm_t25_x=_arr(params, "obm_t25_x"),
            obm_t25_y=_arr(params, "obm_t25_y"),
            obm_t5_x=_arr(params, "obm_t5_x"),
            obm_t5_y=_arr(params, "obm_t5_y"),
            v_lo=np.ascontiguousarray(v_lo),
            v_hi=np.ascontiguousarray(v_hi),
            v_rate=np.ascontiguousarray(v_rate),
            v_xc=np.ascontiguousarray(v_xc),
            v_safe=np.ascontiguousarray(v_safe),
            # optional N2-governor gain schedule (W2.3a; absent = flat 1, e.g. the proxy sets): x 1.0 is
            # exact, so a configuration without it runs bitwise as before
            govk_x=_arr(params, "gov_ks_x") if "gov_ks_x" in params else np.array([0.0, 2.0]),
            govk_y=_arr(params, "gov_ks_y") if "gov_ks_y" in params else np.array([1.0, 1.0]),
        )
        for name, a in tables._asdict().items():
            if name.endswith("_x") and np.any(np.diff(a) <= 0):
                raise ValueError(f"table breakpoints {name} must be strictly increasing")
        persist = float(v("vm_persist_scale"))

        def scaled(n: int) -> int:
            return max(1, int(np.ceil(n * persist)))

        if len(lanes_per_sensor) != NS or any(n not in (1, 2) for n in lanes_per_sensor):
            raise ValueError("lanes_per_sensor must give 1 or 2 lanes for each of the 6 sensors")
        c = {
            "fuel_law": int(v("fuel_law")),
            "autothrottle": 1 if autothrottle else 0,
            "n_range": scaled(int(v("n_range"))),
            "n_rate": scaled(int(v("n_rate"))),
            "n_xc": scaled(int(v("n_xc"))),
            "heal": int(v("heal_frames")),
            "lane_heal": int(v("lane_heal_frames")),
            "n_an": scaled(_frames(float(v("an_persist")), f_nom)),
            "n_hold": _frames(float(v("hold_time")), f_nom),
            "max_subst": int(v("max_subst")),
            "skew": int(v("vm_skew_frames")),
            "wrap": int(v("vm_wrap")),
            "analytic": int(v("vm_analytic")),
            "hs_window": _frames(float(v("hs_window")), f_nom),
            "hs_timeout": _frames(float(v("hs_timeout")), f_nom),
            "fo_detect": max(1, _frames(float(v("fo_detect")), f_nom)),
            "fo_confirm": _frames(float(v("fo_confirm")), f_nom),
            "si_frames": _frames(float(v("si_time")), f_nom),
            "stall_hold": _frames(float(v("stall_hold")), f_nom),
            "ot_frames": _frames(float(v("ot_time")), f_nom),
            "os_frames": _frames(float(v("os_time")), f_nom),
            "ab_nolight": _frames(float(v("ab_nolight")), f_nom),
            "ab_max_retries": int(v("ab_max_retries")),
            "ab_retry": _frames(float(v("ab_retry")), f_nom),
            "ab_preopen": _frames(float(v("ab_preopen")), f_nom),
            "ab_blowout": max(1, _frames(float(v("ab_blowout")), f_nom)),
        }
        for s, n in enumerate(lanes_per_sensor):
            c[f"nl_{s}"] = int(n)
        c["anti_windup"] = int(v("anti_windup"))
        c["handoff"] = int(v("limiter_handoff"))
        c["edge_hold"] = int(v("edge_hold"))
        c["at_floor_lever"] = 0  # option (W2.4a-2 proxy A/T floor), set with with_cfg; 0 = the W1.3b law
        if not 0 <= c["edge_hold"] < 64:
            raise ValueError("edge_hold is a 6-bit sensor mask (N1, N2, T1, T25, PS3, T5)")
        if not 0 <= c["handoff"] < 32:
            raise ValueError("limiter_handoff is a 5-bit mask (N1, N2max, T5, PS3max, PS3min)")
        if c["fuel_law"] not in (0, 1):
            raise ValueError("fuel_law must be 0 (direct Wf) or 1 (ratio units)")
        cfg = np.array([c[name] for name in C_LAYOUT.names], dtype=np.int64)
        assert cfg.size == NC
        p.flags.writeable = False
        cfg.flags.writeable = False
        return cls(p=p, tables=tables, cfg=cfg, dt=dt, clock=clock)

    def with_p(self, **values: float) -> FadecConfig:
        """A copy with some kernel parameters changed by name (sweeps, calibration)."""
        p = self.p.copy()
        for k, x in values.items():
            p[P_LAYOUT.index[k]] = float(x)
        p.flags.writeable = False
        return FadecConfig(p=p, tables=self.tables, cfg=self.cfg, dt=self.dt, clock=self.clock)

    def with_cfg(self, **values: int) -> FadecConfig:
        """A copy with some integer config entries changed by name."""
        cfg = self.cfg.copy()
        for k, x in values.items():
            cfg[C_LAYOUT.index[k]] = int(x)
        cfg.flags.writeable = False
        return FadecConfig(p=self.p, tables=self.tables, cfg=cfg, dt=self.dt, clock=self.clock)


__all__ = ["FadecConfig", "load_fadec_params"]
