"""Base climatology for Indian air bases and the per-sortie ambient sampler (architecture §6 M03; R§3, R§4).

Evidence [DIRECT]: IMD Climatological Tables of Observatories in India 1991-2020 (station tables; local copy
research_sources/flight_profiles/IMD_Climatological_Tables_1991-2020.pdf, transcribed to
configs/tejas/params/M03/imd_climatology_1991_2020.csv): monthly station-level pressure, dry/wet bulb and
relative humidity / vapour pressure at 0300 and 1200 UTC, mean daily max/min, mean monthly highest/lowest,
mean wind speed, wind-direction frequencies at 0300/1200 UTC and the number of days with precipitation
>= 0.3 mm, hail, thunder, fog, dust storm and squall. Stations: Coimbatore (Sulur; 45/18 Sqn), Naliya
(18 Sqn), Bikaner (Nal; Mk1A), Jaisalmer and Jodhpur
(research_notes/.../iaf_usage_and_validation_gap_closure.md
Q1; flight_profiles_and_usage.md Q6).

The table gives means and mean extremes, not daily distributions. The sampler therefore adds (all tagged
[ASSUMPTION] in M03.yaml with sweeps and exposing tests):
- A-W1.1-5: a Gaussian day-to-day anomaly whose SD is inferred from the mean monthly extreme: the expected
  maximum of ~30 daily values is ~2.04 SD above the mean, so SD_hi = (T_hi_month - T_max) / 2.04 (and
  SD_lo from the minima); one standard-normal anomaly per (base, date) drives both;
- A-W1.1-6: an asymmetric-cosine diurnal cycle between the day's minimum (near sunrise) and maximum (mid
  afternoon); the 0300/1200 UTC dry-bulb means are an independent check (test);
- A-W1.1-7: station pressure, vapour pressure and wind direction follow the 0300/1200 UTC anchors
  (linear in time of day, cyclic), with a Gaussian day anomaly on pressure and a log-normal one on vapour
  pressure; wind speed is Rayleigh with the monthly mean speed, a calm fraction from the direction table;
- A-W1.1-8: weather-phenomenon days are independent Bernoulli draws per (base, date) with probability
  (days with the phenomenon) / (days in the month).

Randomness: one GENERATOR-stream unit per (scenario, base, date) owned by the caller (M02 plans the day and
puts the ambient into the sortie plan; usage mode never runs M03). Draws happen in a fixed order, so the
result is a pure function of (base, date, time of day) and the stream identity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from phalanx.core.module import ParamSet

#: IMD wind-direction categories (from), radians clockwise from true north; index 8 = calm
DIR_FROM_RAD = np.deg2rad(np.arange(8) * 45.0)
DIR_NAMES = ("n", "ne", "e", "se", "s", "sw", "w", "nw", "calm")
_MONTH_DAYS = (31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
HOUR_03, HOUR_12 = 3.0, 12.0

# Ambient payload layout (flat float vector; SI)
A_BASE, A_FIELD_ELEV, A_STN_HEIGHT, A_T_STN, A_P_STN, A_E_STN = 0, 1, 2, 3, 4, 5
A_WIND_SPEED, A_WIND_FROM, A_TURB_CLASS, A_T_UTC_S, A_THUNDER, A_FOG, A_DUST, A_PPT = (
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
)
N_AMBIENT = 14


@dataclass(frozen=True)
class StationClimatology:
    """One IMD station, 12 months (index 0 = January). SI units (Pa, K, m/s); day counts per month."""

    imd_index: int
    lat_deg: float
    lon_deg: float
    height_m: float
    p03: np.ndarray
    p12: np.ndarray
    t03: np.ndarray
    t12: np.ndarray
    t_max: np.ndarray
    t_min: np.ndarray
    t_hi_month: np.ndarray
    t_lo_month: np.ndarray
    vp03: np.ndarray
    vp12: np.ndarray
    wind: np.ndarray
    ppt_days: np.ndarray
    thunder_days: np.ndarray
    fog_days: np.ndarray
    dust_days: np.ndarray
    squall_days: np.ndarray
    dir03: np.ndarray  # (12, 9) fractions summing to ~1
    dir12: np.ndarray

    def phenomenon_probability(self, month: int, name: str) -> float:
        days = getattr(self, f"{name}_days")[month - 1]
        return float(min(1.0, days / _MONTH_DAYS[month - 1]))


@dataclass(frozen=True)
class SamplerParams:
    """Ambient-sampler assumptions (M03.yaml set ``climatology``)."""

    extreme_sd_factor: float = 2.04  # E[max of ~30 iid normals] / SD
    hour_tmin_utc: float = 0.5  # ~06:00 IST
    hour_tmax_utc: float = 9.0  # ~14:30 IST
    p_day_sd: float = 200.0  # Pa
    lne_day_sd: float = 0.15
    turb_probs: tuple[float, float, float, float] = (0.55, 0.35, 0.09, 0.01)
    turb_probs_thunder: tuple[float, float, float, float] = (0.2, 0.4, 0.3, 0.1)
    w10_to_w20: float = 0.823  # ln(20 ft / z0) / ln(10 m / z0), z0 = 2 ft (log profile)

    @classmethod
    def from_paramset(cls, ps: ParamSet) -> SamplerParams:
        v = ps.value
        return cls(
            extreme_sd_factor=float(v("extreme_sd_factor")),
            hour_tmin_utc=float(v("hour_tmin_utc")) / 3600.0,
            hour_tmax_utc=float(v("hour_tmax_utc")) / 3600.0,
            p_day_sd=float(v("p_day_sd")),
            lne_day_sd=float(v("lne_day_sd")),
            turb_probs=tuple(float(x) for x in v("turb_class_probs")),  # type: ignore[arg-type]
            turb_probs_thunder=tuple(float(x) for x in v("turb_class_probs_thunder")),  # type: ignore[arg-type]
            w10_to_w20=float(v("w10_to_w20")),
        )


@dataclass(frozen=True)
class Climatology:
    stations: dict[int, StationClimatology] = field(default_factory=dict)

    def station(self, imd_index: int) -> StationClimatology:
        try:
            return self.stations[int(imd_index)]
        except KeyError:
            raise KeyError(f"no IMD station {imd_index}; have {sorted(self.stations)}") from None

    @classmethod
    def from_paramset(cls, ps: ParamSet) -> Climatology:
        """Build from the M03 ``climatology`` set (columns of the transcribed IMD CSV, already SI)."""
        v = ps.value
        idx = np.asarray(v("imd_index"), dtype=np.int64)
        month = np.asarray(v("month"), dtype=np.int64)
        meta_idx = np.asarray(v("station_index"), dtype=np.int64)
        out = {}
        for k, sid in enumerate(meta_idx.tolist()):
            rows = np.flatnonzero(idx == sid)
            order = rows[np.argsort(month[rows])]
            if not np.array_equal(month[order], np.arange(1, 13)):
                raise ValueError(f"station {sid}: need 12 months")

            def col(name, order=order):
                return np.asarray(v(name), dtype=np.float64)[order]

            dir03 = np.stack([col(f"dir03_{d}") for d in DIR_NAMES], axis=1)
            dir12 = np.stack([col(f"dir12_{d}") for d in DIR_NAMES], axis=1)
            out[sid] = StationClimatology(
                imd_index=sid,
                lat_deg=float(np.asarray(v("station_lat"))[k]) * 180.0 / math.pi,
                lon_deg=float(np.asarray(v("station_lon"))[k]) * 180.0 / math.pi,
                height_m=float(np.asarray(v("station_height"))[k]),
                p03=col("p_stn_03"),
                p12=col("p_stn_12"),
                t03=col("t_db_03"),
                t12=col("t_db_12"),
                t_max=col("t_max"),
                t_min=col("t_min"),
                t_hi_month=col("t_hi_month"),
                t_lo_month=col("t_lo_month"),
                vp03=col("vp_03"),
                vp12=col("vp_12"),
                wind=col("wind"),
                ppt_days=col("ppt_days"),
                thunder_days=col("thunder_days"),
                fog_days=col("fog_days"),
                dust_days=col("dust_days"),
                squall_days=col("squall_days"),
                dir03=dir03 / dir03.sum(axis=1, keepdims=True),
                dir12=dir12 / dir12.sum(axis=1, keepdims=True),
            )
        return cls(out)


def diurnal_fraction(hour_utc: float, h_min: float, h_max: float) -> float:
    """Position in [0, 1] between the day's minimum (0) and maximum (1): an asymmetric cosine, rising over
    (h_min, h_max) and falling over the remaining 24 h [ASSUMPTION A-W1.1-6]."""
    rise = (h_max - h_min) % 24.0
    s = (hour_utc - h_min) % 24.0
    if s <= rise:
        return 0.5 * (1.0 - math.cos(math.pi * s / rise))
    return 0.5 * (1.0 + math.cos(math.pi * (s - rise) / (24.0 - rise)))


def _anchor_weight(hour_utc: float) -> float:
    """Weight of the 1200 UTC anchor for a cyclic linear interpolation 03 -> 12 -> 03 (+24)."""
    s = (hour_utc - HOUR_03) % 24.0
    if s <= HOUR_12 - HOUR_03:
        return s / (HOUR_12 - HOUR_03)
    return 1.0 - (s - (HOUR_12 - HOUR_03)) / (24.0 - (HOUR_12 - HOUR_03))


def mean_temperature(st: StationClimatology, month: int, hour_utc: float, sp: SamplerParams) -> float:
    m = month - 1
    frac = diurnal_fraction(hour_utc, sp.hour_tmin_utc, sp.hour_tmax_utc)
    return float(st.t_min[m] + frac * (st.t_max[m] - st.t_min[m]))


@dataclass(frozen=True)
class Ambient:
    """Per-sortie ambient conditions (what M02 puts in the sortie plan and M03 builds its profile from)."""

    base: int  # IMD station index of the base
    field_elev_m: float
    station_height_m: float
    t_station_k: float
    p_station_pa: float
    e_station_pa: float
    wind_speed_mps: float  # W20 equivalent
    wind_from_rad: float
    turb_class: int
    t_utc_s: float
    thunder: bool = False
    fog: bool = False
    dust: bool = False
    precip: bool = False

    def vector(self) -> np.ndarray:
        v = np.zeros(N_AMBIENT)
        v[A_BASE] = self.base
        v[A_FIELD_ELEV] = self.field_elev_m
        v[A_STN_HEIGHT] = self.station_height_m
        v[A_T_STN] = self.t_station_k
        v[A_P_STN] = self.p_station_pa
        v[A_E_STN] = self.e_station_pa
        v[A_WIND_SPEED] = self.wind_speed_mps
        v[A_WIND_FROM] = self.wind_from_rad
        v[A_TURB_CLASS] = self.turb_class
        v[A_T_UTC_S] = self.t_utc_s
        v[A_THUNDER] = float(self.thunder)
        v[A_FOG] = float(self.fog)
        v[A_DUST] = float(self.dust)
        v[A_PPT] = float(self.precip)
        return v

    @classmethod
    def from_vector(cls, v: np.ndarray) -> Ambient:
        v = np.asarray(v, dtype=np.float64)
        if v.shape != (N_AMBIENT,):
            raise ValueError(f"ambient vector must have shape ({N_AMBIENT},)")
        return cls(
            base=int(v[A_BASE]),
            field_elev_m=float(v[A_FIELD_ELEV]),
            station_height_m=float(v[A_STN_HEIGHT]),
            t_station_k=float(v[A_T_STN]),
            p_station_pa=float(v[A_P_STN]),
            e_station_pa=float(v[A_E_STN]),
            wind_speed_mps=float(v[A_WIND_SPEED]),
            wind_from_rad=float(v[A_WIND_FROM]),
            turb_class=int(v[A_TURB_CLASS]),
            t_utc_s=float(v[A_T_UTC_S]),
            thunder=bool(v[A_THUNDER]),
            fog=bool(v[A_FOG]),
            dust=bool(v[A_DUST]),
            precip=bool(v[A_PPT]),
        )


@dataclass(frozen=True)
class DayWeather:
    """The day-level draws for one (base, date): anomalies and phenomenon flags."""

    month: int
    z_temp: float
    dp: float
    dlne: float
    thunder: bool
    fog: bool
    dust: bool
    precip: bool
    squall: bool
    wind_u: float  # uniform draws reused for the wind of any time that day
    wind_dir_u: float
    wind_jitter_u: float
    turb_u: float


def draw_day(st: StationClimatology, month: int, gen: np.random.Generator, sp: SamplerParams) -> DayWeather:
    """All day-level draws for (base, date), in a fixed order (CRN: same unit -> same day)."""
    z = gen.standard_normal(3)
    u = gen.random(9)
    m = month
    return DayWeather(
        month=m,
        z_temp=float(z[0]),
        dp=float(z[1]) * sp.p_day_sd,
        dlne=float(z[2]) * sp.lne_day_sd,
        thunder=bool(u[0] < st.phenomenon_probability(m, "thunder")),
        fog=bool(u[1] < st.phenomenon_probability(m, "fog")),
        dust=bool(u[2] < st.phenomenon_probability(m, "dust")),
        precip=bool(u[3] < st.phenomenon_probability(m, "ppt")),
        squall=bool(u[4] < st.phenomenon_probability(m, "squall")),
        wind_u=float(u[5]),
        wind_dir_u=float(u[6]),
        wind_jitter_u=float(u[7]),
        turb_u=float(u[8]),
    )


def ambient_at(
    st: StationClimatology,
    day: DayWeather,
    hour_utc: float,
    t_utc_s: float,
    sp: SamplerParams,
    *,
    field_elev_m: float,
    magnus: tuple[float, float, float],
) -> Ambient:
    """Ambient at a time of day from the day's draws (pure function)."""
    m = day.month - 1
    sd_hi = max(0.0, (st.t_hi_month[m] - st.t_max[m]) / sp.extreme_sd_factor)
    sd_lo = max(0.0, (st.t_min[m] - st.t_lo_month[m]) / sp.extreme_sd_factor)
    tmax = st.t_max[m] + day.z_temp * sd_hi
    tmin = st.t_min[m] + day.z_temp * sd_lo
    frac = diurnal_fraction(hour_utc, sp.hour_tmin_utc, sp.hour_tmax_utc)
    t = float(tmin + frac * (tmax - tmin))
    w12 = _anchor_weight(hour_utc)
    p = float((1 - w12) * st.p03[m] + w12 * st.p12[m] + day.dp)
    e_mean = (1 - w12) * st.vp03[m] + w12 * st.vp12[m]
    e = float(e_mean * math.exp(day.dlne))
    tc = t - 273.15
    es = magnus[0] * math.exp(magnus[1] * tc / (tc + magnus[2]))
    e = min(e, es)
    dirs = st.dir12[m] if w12 >= 0.5 else st.dir03[m]
    cat = int(np.searchsorted(np.cumsum(dirs), day.wind_dir_u * float(np.sum(dirs)), side="right"))
    cat = min(cat, 8)
    if cat == 8:
        speed, wfrom = 0.0, 0.0
    else:
        calm = dirs[8]
        mean_moving = st.wind[m] / max(1e-9, 1.0 - calm)  # IMD mean includes calm days
        # Rayleigh with mean mu: sigma = mu / sqrt(pi/2); inverse CDF of u
        sig = mean_moving / math.sqrt(math.pi / 2.0)
        speed = sp.w10_to_w20 * sig * math.sqrt(-2.0 * math.log(max(1e-300, 1.0 - day.wind_u)))
        wfrom = float((DIR_FROM_RAD[cat] + (day.wind_jitter_u - 0.5) * math.pi / 4.0) % (2.0 * math.pi))
    probs = np.asarray(sp.turb_probs_thunder if day.thunder else sp.turb_probs)
    turb = min(int(np.searchsorted(np.cumsum(probs), day.turb_u * float(probs.sum()), side="right")), 3)
    return Ambient(
        base=st.imd_index,
        field_elev_m=float(field_elev_m),
        station_height_m=st.height_m,
        t_station_k=t,
        p_station_pa=p,
        e_station_pa=e,
        wind_speed_mps=float(speed),
        wind_from_rad=wfrom,
        turb_class=turb,
        t_utc_s=float(t_utc_s),
        thunder=day.thunder,
        fog=day.fog,
        dust=day.dust,
        precip=day.precip,
    )


__all__ = [
    "N_AMBIENT",
    "Ambient",
    "Climatology",
    "DayWeather",
    "SamplerParams",
    "StationClimatology",
    "ambient_at",
    "diurnal_fraction",
    "draw_day",
    "mean_temperature",
]
