"""M02 configuration: model parameters (``configs/<platform>/params/M02.yaml``) and scenario/fleet
configuration (``configs/scenarios/*.yaml``)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from phalanx.core.module import ParamSet
from phalanx.dictionary.params import load_params
from phalanx.dictionary.yamlio import load_yaml
from phalanx.environment.config import merged_paramset

_REPO = Path(__file__).resolve().parents[3]
DEG = np.pi / 180.0

# mission type codes (missions.csv mid)
GH, INST_NAV, FORMATION, BFM, ACM, GROUND_ATTACK, COMPOSITE, AAR, NAV_TRANSIT, AIR_TEST = range(1, 11)
MISSION_NAMES = {
    GH: "GH",
    INST_NAV: "INST_NAV",
    FORMATION: "FORMATION",
    BFM: "BFM",
    ACM: "ACM_INTERCEPT",
    GROUND_ATTACK: "GROUND_ATTACK",
    COMPOSITE: "COMPOSITE",
    AAR: "AAR",
    NAV_TRANSIT: "NAV_TRANSIT",
    AIR_TEST: "AIR_TEST",
}
ROLE_OCU, ROLE_OPS = 0, 1
#: engine serial format ``<prefix>-<token>`` (SYNTHETIC, A-W1.1-32): the scenario's installed engine
#: serials are the fleet's single source of engine identity (M18 installs them, M10 / M11 / M14 are
#: configured with them; W2.1c); the default token is the tail number
ENGINE_SERIAL_PREFIX = "IN20"
# primitive ids (primitives.csv pid)
P_CRUISE, P_CLIMB, P_DESCENT, P_TURN, P_BREAK, P_SUSTAINED, P_PULLOUT, P_REVERSAL = 1, 2, 3, 4, 5, 6, 7, 8
P_VERTICAL, P_DIVE, P_WEAVE, P_FORMATION, P_TANKER, P_DASH, P_IDLE, P_AEROBATIC, P_INSTR = (
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
)


@dataclass(frozen=True)
class PrimitiveTable:
    """Manoeuvre-primitive library (AD-28 layer 4), one row per primitive (SI: PLA in rad)."""

    pid: np.ndarray
    pla: np.ndarray
    pla_lo: np.ndarray
    pla_hi: np.ndarray
    ab_capable: np.ndarray
    pla_ab: np.ndarray
    nz: np.ndarray
    nz_sd: np.ndarray
    peaks: np.ndarray
    dwell_med: np.ndarray
    dwell_sig: np.ndarray
    vz: np.ndarray
    mach: np.ndarray
    turn: np.ndarray
    power_active: np.ndarray

    def row(self, pid: int) -> int:
        return int(np.flatnonzero(self.pid == pid)[0])


@dataclass(frozen=True)
class MissionTable:
    mid: np.ndarray
    ocu_mix: np.ndarray
    ops_mix: np.ndarray
    dur_mult: np.ndarray
    drop_prob: np.ndarray
    transit_alt: np.ndarray
    block_alt: np.ndarray
    transit_s: np.ndarray
    tg_mean: np.ndarray
    ab_prob: np.ndarray
    to_ab_prob: np.ndarray
    high_activity: np.ndarray
    mix: np.ndarray  # (n_missions, n_primitives) weights, rows by mission order, columns by primitive order

    def row(self, mid: int) -> int:
        return int(np.flatnonzero(self.mid == mid)[0])


@dataclass(frozen=True)
class ScenarioParams:
    # calendar (layer 1)
    peace_rate: float
    surge_rate: float
    day_wave_hours: tuple[float, ...]
    night_wave_hour: float
    night_wave_prob: float
    surge_wave_hours: tuple[float, ...]
    flying_weekdays: tuple[int, ...]
    ground_run_day_prob: float
    ground_run_s: float
    cancel_fog: float
    cancel_thunder: float
    cancel_dust: float
    cancel_precip: float
    pilots_per_aircraft: float
    hot_refuel_prob_surge: float
    # sortie (layer 2)
    duration_median_s: float
    duration_sig: float
    drop_tank_shift_s: tuple[float, float]
    takeoff_roll_ab_s: float
    takeoff_roll_mil_s: float
    hot_day_k: float
    # grammar (layer 3)
    preflight_med_s: float
    start_s: float
    ground_idle_med_s: float
    taxi_out_med_s: float
    taxi_sig: float
    runup_prob: float
    runup_s: float
    cold_soak_k: float
    taxi_in_med_s: float
    cooldown_med_s: float
    pattern_med_s: float
    approach_s: float
    landing_s: float
    tg_cycle_s: float
    climb_rate: float
    descent_rate: float
    cruise_pla: float
    cruise_band: tuple[float, float]
    hot_refuel_s: float
    # pilots (layer 5) and tails
    trait_sd: dict[str, float]
    aar_mean_range: tuple[float, float]
    aar_sd: float
    tau_range: tuple[float, float]
    remnant_med: float
    tail_affinity_sd: float
    # fuel PROXY, envelope, PLA map
    fuel_pla: np.ndarray
    fuel_wf: np.ndarray
    internal_fuel_kg: float
    drop_tank_kg: float
    reserve_kg: float
    nz_max: float
    mach_max: float
    ceiling_m: float
    pla_gi: float
    pla_fi: float
    pla_irp: float
    pla_runup: float
    pla_min_ab: float
    pla_max_ab: float
    count_off_hi: float
    count_idle_hi: float
    count_hyst: float
    exposure_agl_m: float
    dust_clear_level: float
    chute_prob: float
    primitives: PrimitiveTable
    missions: MissionTable
    params: ParamSet = field(repr=False)

    def with_(self, **changes) -> ScenarioParams:
        return replace(self, **changes)


def _tuple(v) -> tuple[float, ...]:
    return tuple(float(x) for x in np.atleast_1d(np.asarray(v, dtype=float)))


def load_scenario_params(platform: str = "tejas", config_root: Path | None = None) -> ScenarioParams:
    sets = load_params("M02", platform=platform, config_root=config_root)
    ud = sets["usage_drivers"].value
    c, s, g, pl, f, pt, mi = (
        sets["calendar"].value,
        sets["sortie"].value,
        sets["grammar"].value,
        sets["pilots"].value,
        sets["fuel_envelope"].value,
        sets["primitives"].value,
        sets["missions"].value,
    )

    def arr(fn, name, dtype=float):
        return np.asarray(fn(name), dtype=dtype)

    prims = PrimitiveTable(
        pid=arr(pt, "pid", np.int64),
        pla=arr(pt, "pla"),
        pla_lo=arr(pt, "pla_lo"),
        pla_hi=arr(pt, "pla_hi"),
        ab_capable=arr(pt, "ab_capable", np.int64),
        pla_ab=arr(pt, "pla_ab"),
        nz=arr(pt, "nz"),
        nz_sd=arr(pt, "nz_sd"),
        peaks=arr(pt, "peaks", np.int64),
        dwell_med=arr(pt, "dwell_med"),
        dwell_sig=arr(pt, "dwell_sig"),
        vz=arr(pt, "vz"),
        mach=arr(pt, "mach"),
        turn=arr(pt, "turn", np.int64),
        power_active=arr(pt, "power_active", np.int64),
    )
    mix_cols = [arr(mi, f"mix_m{k:02d}") for k in range(1, 11)]
    missions = MissionTable(
        mid=arr(mi, "mid", np.int64),
        ocu_mix=arr(mi, "ocu_mix"),
        ops_mix=arr(mi, "ops_mix"),
        dur_mult=arr(mi, "dur_mult"),
        drop_prob=arr(mi, "drop_prob"),
        transit_alt=arr(mi, "transit_alt"),
        block_alt=arr(mi, "block_alt"),
        transit_s=arr(mi, "transit_s"),
        tg_mean=arr(mi, "tg_mean"),
        ab_prob=arr(mi, "ab_prob"),
        to_ab_prob=arr(mi, "to_ab_prob"),
        high_activity=arr(mi, "high_activity", np.int64),
        mix=np.stack(mix_cols, axis=0),
    )
    return ScenarioParams(
        peace_rate=float(c("peace_rate")),
        surge_rate=float(c("surge_rate")),
        day_wave_hours=tuple(x / 3600 for x in _tuple(c("day_wave_hours"))),
        night_wave_hour=float(c("night_wave_hour")) / 3600,
        night_wave_prob=float(c("night_wave_prob")),
        surge_wave_hours=tuple(x / 3600 for x in _tuple(c("surge_wave_hours"))),
        flying_weekdays=tuple(int(x) for x in _tuple(c("flying_weekdays"))),
        ground_run_day_prob=float(c("ground_run_day_prob")),
        ground_run_s=float(c("ground_run_duration")),
        cancel_fog=float(c("cancel_fog")),
        cancel_thunder=float(c("cancel_thunder")),
        cancel_dust=float(c("cancel_dust")),
        cancel_precip=float(c("cancel_precip")),
        pilots_per_aircraft=float(c("pilots_per_aircraft")),
        hot_refuel_prob_surge=float(c("hot_refuel_prob_surge")),
        duration_median_s=float(s("duration_median")),
        duration_sig=float(s("duration_sig")),
        drop_tank_shift_s=_tuple(s("drop_tank_shift")),  # type: ignore[arg-type]
        takeoff_roll_ab_s=float(s("takeoff_roll_ab")),
        takeoff_roll_mil_s=float(s("takeoff_roll_mil")),
        hot_day_k=float(s("hot_day_temperature")),
        preflight_med_s=float(g("preflight")),
        start_s=float(g("engine_start")),
        ground_idle_med_s=float(g("ground_idle")),
        taxi_out_med_s=float(g("taxi_out")),
        taxi_sig=float(g("taxi_sig")),
        runup_prob=float(g("runup_prob")),
        runup_s=float(g("runup")),
        cold_soak_k=float(g("cold_soak_temperature")),
        taxi_in_med_s=float(g("taxi_in")),
        cooldown_med_s=float(g("cooldown")),
        pattern_med_s=float(g("pattern")),
        approach_s=float(g("approach")),
        landing_s=float(g("landing")),
        tg_cycle_s=float(g("touch_and_go_cycle")),
        climb_rate=float(g("climb_rate")),
        descent_rate=float(g("descent_rate")),
        cruise_pla=float(g("cruise_pla")),
        cruise_band=_tuple(g("cruise_band")),  # type: ignore[arg-type]
        hot_refuel_s=float(g("hot_refuel")),
        trait_sd={
            "throttle": float(pl("throttle_sd")),
            "g": float(pl("g_sd")),
            "ab": float(pl("ab_sd")),
            "cooldown": float(pl("cooldown_sd")),
            "gain": float(pl("crossover_gain_sd")),
            "remnant": float(pl("remnant_sd")),
        },
        aar_mean_range=_tuple(pl("aar_mean_range")),  # type: ignore[arg-type]
        aar_sd=float(pl("aar_sd")),
        tau_range=_tuple(pl("tau_range")),  # type: ignore[arg-type]
        remnant_med=float(pl("remnant_median")),
        tail_affinity_sd=float(pl("tail_affinity_sd")),
        fuel_pla=arr(f, "fuel_pla_points"),
        fuel_wf=arr(f, "fuel_wf_points"),
        internal_fuel_kg=float(f("internal_fuel")),
        drop_tank_kg=float(f("drop_tank_fuel")),
        reserve_kg=float(f("landing_reserve")),
        nz_max=float(f("nz_max")),
        mach_max=float(f("mach_max")),
        ceiling_m=float(f("ceiling")),
        pla_gi=float(f("pla_ground_idle")),
        pla_fi=float(f("pla_flight_idle")),
        pla_irp=float(f("pla_irp")),
        pla_runup=float(f("pla_runup")),
        pla_min_ab=float(f("pla_min_ab")),
        pla_max_ab=float(f("pla_max_ab")),
        count_off_hi=float(f("count_off_hi")),
        count_idle_hi=float(f("count_idle_hi")),
        count_hyst=float(f("count_hyst")),
        exposure_agl_m=float(ud("exposure_agl")),
        dust_clear_level=float(ud("dust_clear_level")),
        chute_prob=float(ud("chute_prob")),
        primitives=prims,
        missions=missions,
        params=merged_paramset(f"{platform}.M02", sets),
    )


# ------------------------------------------------------------------------------------------- fleet config


@dataclass(frozen=True)
class Base:
    name: str
    imd_index: int
    field_elev_m: float
    salt_level: float = 0.0  # usage driver salt_index: 1 coastal, 0 inland [ASSUMPTION A-W1.1-34]


@dataclass(frozen=True)
class Squadron:
    sid: str  # lower-case identifier (used in RNG stream names and sortie keys)
    role: int  # ROLE_OCU / ROLE_OPS
    base: Base
    tails: tuple[str, ...]
    engine_serials: tuple[str, ...]  # installed engine per tail (same order; Tejas: one per tail)


@dataclass(frozen=True)
class FleetScenario:
    name: str
    start: dt.date
    days: int
    squadrons: tuple[Squadron, ...]
    surge: tuple[tuple[dt.date, dt.date], ...] = ()
    #: scenario supply disruptions sent to M18 (``m18.disruption``): (class code, lead-time factor, first day,
    #: last day inclusive)
    disruptions: tuple[tuple[str, float, dt.date, dt.date], ...] = ()

    @property
    def epoch_utc_ns(self) -> int:
        return (
            int(dt.datetime(self.start.year, self.start.month, self.start.day, tzinfo=dt.UTC).timestamp())
            * 10**9
        )

    def tails(self) -> tuple[str, ...]:
        return tuple(t for sq in self.squadrons for t in sq.tails)

    def is_surge(self, d: dt.date) -> bool:
        return any(a <= d <= b for a, b in self.surge)


def load_bases(path: Path | None = None) -> dict[str, Base]:
    doc = load_yaml(path or _REPO / "configs" / "scenarios" / "bases.yaml")
    return {
        name: Base(name, int(b["imd_index"]), float(b["field_elev_m"]), float(b.get("salt_level", 0.0)))
        for name, b in sorted(doc["bases"].items())
    }


def load_fleet_scenario(path: Path) -> FleetScenario:
    """A fleet scenario YAML (format ``phalanx.scenario/1``; see configs/scenarios/README.md)."""
    doc = load_yaml(path)
    if doc.get("format") != "phalanx.scenario/1":
        raise ValueError(f"{path}: format must be phalanx.scenario/1")
    bases = load_bases(Path(path).parent / "bases.yaml")
    sqs = []
    for sq in doc["squadrons"]:
        tails = tuple(str(t) for t in sq["tails"])
        default = [f"{ENGINE_SERIAL_PREFIX}-{t}" for t in tails]
        serials = tuple(str(s) for s in sq.get("engine_serials", default))
        if len(serials) != len(tails):
            raise ValueError(f"squadron {sq['id']}: one engine serial per tail")
        head = f"{ENGINE_SERIAL_PREFIX}-"
        bad = [s for s in serials if not s.startswith(head) or s == head]
        if bad:
            raise ValueError(f"squadron {sq['id']}: engine serials {bad} are not {head}<token>")
        role = {"OCU": ROLE_OCU, "OPS": ROLE_OPS}[sq["role"]]
        sqs.append(Squadron(str(sq["id"]), role, bases[sq["base"]], tails, serials))
    surge = tuple(
        (dt.date.fromisoformat(str(a)), dt.date.fromisoformat(str(b))) for a, b in doc.get("surge", [])
    )
    disruptions = tuple(
        (
            str(x["cls"]),
            float(x["factor"]),
            dt.date.fromisoformat(str(x["start"])),
            dt.date.fromisoformat(str(x["end"])),
        )
        for x in doc.get("supply_disruptions", [])
    )
    all_serials = [s for sq in sqs for s in sq.engine_serials]
    if len(set(all_serials)) != len(all_serials):
        raise ValueError(f"{path}: engine serials must be unique across the fleet")
    return FleetScenario(
        name=str(doc["name"]),
        start=dt.date.fromisoformat(str(doc["start"])),
        days=int(doc["days"]),
        squadrons=tuple(sqs),
        surge=surge,
        disruptions=disruptions,
    )


__all__ = [
    "MISSION_NAMES",
    "ROLE_OCU",
    "ROLE_OPS",
    "Base",
    "FleetScenario",
    "MissionTable",
    "PrimitiveTable",
    "ScenarioParams",
    "Squadron",
    "load_bases",
    "load_fleet_scenario",
    "load_scenario_params",
]
