"""AD-28 six-layer mission generator (architecture §6 M02; report §4 "Generate sortie instances
hierarchically and check them against fleet statistics").

1. **Calendar** (:meth:`Planner.plan_day`): flying days, waves (day, night, surge), weather cancels from the
   IMD day draws, slot-by-slot fly decisions at the planned rate, tail rotation, availability, ground runs.
2. **Sortie** (:meth:`Planner.build_sortie`): mission type from the squadron-role mix (tail affinity),
   flight time (lognormal, mission multiplier, drop tanks), configuration, base and ambient at take-off.
3. **Phase grammar**: fixed opening (pre-flight -> start -> idle -> taxi -> run-up -> take-off -> climb),
   transit, mission block, transit, descent, pattern with touch-and-go loops, approach, landing, taxi,
   optional hot refuel, cooldown and shutdown.
4. **Manoeuvres**: semi-Markov primitives inside the envelope (Nz <= 8 g or the restriction, Mach <= 1.6,
   ceiling 15 km), with a plan-level fuel budget (PROXY A-W1.1-27) that truncates the block at bingo.
5. **Pilot traits**: per-pilot latent multipliers (:mod:`.pilots`).
6. **Hand-off**: a :class:`~.plan.SortiePlan` with its usage summary (:mod:`.usage`).

Randomness (AD-37), all GENERATOR streams owned by M02 and declared by :class:`ScenarioModule`:

| Stream | Identity | Unit index -> use |
|---|---|---|
| ``scenario.weather`` | scenario, base, date | 0: IMD day draws (shared by every squadron at the base) |
| ``scenario.day`` | scenario, base, date | squadron ordinal: night wave, wave cancels, tail rotation |
| ``scenario.slot`` | scenario, sortie (slot key) | 0 fly/sortie draws, 1 manoeuvres, 2 grammar durations |
| ``scenario.pilot`` | scenario, serial (pilot id) | 0: traits |
| ``scenario.tail`` | scenario, tail | 0: tail affinity |
| ``scenario.ground_run`` | scenario, tail, date | 0: ground-run decision |

Slot keys (``<squadron>-<yyyymmdd>-w<wave>-s<slot>``) do not depend on which tail flies, on availability or
on orders, so forks share the exogenous future of every slot (CRN; architecture §11.2).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np

from phalanx.core.rng import Keys
from phalanx.environment.climatology import A_DUST, Ambient, DayWeather, ambient_at, draw_day
from phalanx.environment.config import EnvConfig

from . import phases as P
from .config import (
    AAR,
    ENGINE_SERIAL_PREFIX,
    P_CRUISE,
    P_TANKER,
    ROLE_OCU,
    Base,
    FleetScenario,
    ScenarioParams,
    Squadron,
)
from .pilots import T_AB, T_COOLDOWN, T_G, T_THROTTLE, draw_tail_affinity, draw_traits, pilot_ids
from .plan import (
    N_SEG_F,
    N_SEG_I,
    S_AB_OK,
    S_ALT,
    S_BRAKE,
    S_GEAR,
    S_HDG,
    S_MACH,
    S_NZ,
    S_PHASE,
    S_PLA,
    S_PLA_HI,
    S_PLA_LO,
    S_PRIM,
    S_TURN,
    SortiePlan,
    SortieSummary,
)
from .usage import Thresholds, count_usage

RAD2DEG = 180.0 / math.pi
NS = 1_000_000_000
NZ_LEVELS = (3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
PATTERN_AGL_M = 450.0
GROUND_RUN = 0  # mission type of a maintenance ground run
#: **PROXY (A-W1.1-27, plan-level fuel estimator)**: isothermal scale height of the plan-level pressure ratio
#: p/p0 = exp(-h / H), H = R T0 / g0 = (8314.32 / 28.9644) x 288.15 / 9.80665 = 8434.5 m [TRANSFER: USSA-76
#: sea-level constants, configs/tejas/params/M03.yaml set `atmosphere`]. Not the USSA-76 profile: p/p0 is
#: high by +5 % at 6 km, +21 % at 11 km and +42 % at 15 km, so the plan's fuel cost (and the bingo cap) is
#: conservative at altitude. Used only to cap the mission block and AB time; truth fuel burn is M07/M09's.
#: Exposed by the A-W1.1-27 route (W2.1: plan-level fuel vs M07/M09 burn on the same sorties).
ISOTHERMAL_SCALE_HEIGHT_M = 8434.5


@dataclass
class Overrides:
    """Order effects (M21 -> M02) in force at planning time. Keys: tail, squadron id or slot key."""

    unavailable: set[str] = field(default_factory=set)
    no_ab: set[str] = field(default_factory=set)  # tails, or "*"
    g_limit: dict[str, float] = field(default_factory=dict)  # tail or "*" -> g
    rate_scale: dict[str, float] = field(default_factory=dict)  # squadron -> multiplier
    tail_swap: dict[str, str] = field(default_factory=dict)  # slot key -> tail
    mission: dict[str, int] = field(default_factory=dict)  # slot key -> mission type
    mix: dict[str, np.ndarray] = field(default_factory=dict)  # squadron -> mission mix weights

    def restricted_no_ab(self, tail: str) -> bool:
        return tail in self.no_ab or "*" in self.no_ab

    def g_cap(self, tail: str, default: float) -> float:
        caps = [default]
        for k in (tail, "*"):
            if k in self.g_limit:
                caps.append(self.g_limit[k])
        return min(caps)


@dataclass(frozen=True)
class Slot:
    key: str
    squadron: Squadron
    date: dt.date
    wave: int
    slot: int
    t_takeoff_utc_s: float  # planned take-off (wave time)
    night: bool
    surge: bool
    tail: str
    engine_serial: str
    pilot_id: str


@dataclass(frozen=True)
class GroundRunSpec:
    tail: str
    engine_serial: str
    squadron: Squadron
    date: dt.date
    t_start_utc_s: float


def _utc_s(d: dt.date, hour: float) -> float:
    return dt.datetime(d.year, d.month, d.day, tzinfo=dt.UTC).timestamp() + hour * 3600.0


def slot_key(sq: str, d: dt.date, wave: int, slot: int) -> str:
    return f"{sq}-{d:%Y%m%d}-w{wave}-s{slot:02d}"


def sortie_id(tail: str, t_takeoff_utc_s: float) -> str:
    """Architecture §5.3: sortie_id = tail + date + take-off time."""
    t = dt.datetime.fromtimestamp(t_takeoff_utc_s, tz=dt.UTC)
    return f"{tail}-{t:%Y%m%dT%H%M}"


def exposure(p: ScenarioParams, plan: SortiePlan) -> tuple[float, float]:
    """(exposure hours, dust level) of a plan [A-W1.1-33/34]: engine-running time on the ground or in segments
    below ``exposure_agl_m`` above the field, and the day's dust level (1 on an IMD dust day, else
    ``dust_clear_level``). Pure in (params, plan), so sortie mode and fleet mode share it (W2.1c, AD-48.2:
    ``ops.takeoff`` carries the dust index in both)."""
    ph = plan.seg_i[:, S_PHASE]
    dur = plan.segment_durations_s()
    running = (ph != P.PREFLIGHT) & (ph != P.POSTFLIGHT)
    low = (plan.seg_f[:, S_ALT] - plan.field_elev_m) < p.exposure_agl_m
    ground = ~np.isin(ph, sorted(P.AIRBORNE))
    exp_h = float(dur[running & (low | ground)].sum()) / 3600.0
    dust = 1.0 if bool(plan.ambient[A_DUST]) else p.dust_clear_level
    return exp_h, dust


def airborne_window_ns(plan: SortiePlan) -> tuple[int, int]:
    """(take-off, landing) offsets from the sortie start, ns: the start of the first airborne segment and the
    start of the last landing segment (both the start offset when the plan never flies, e.g. a ground run)."""
    ph = plan.seg_i[:, S_PHASE]
    offs = np.asarray(plan.t_off_ns, dtype=np.int64)
    air = np.flatnonzero(np.isin(ph, sorted(P.AIRBORNE)))
    ldg = np.flatnonzero(ph == P.LANDING)
    t_to = int(offs[air[0]]) if air.size else 0
    t_ldg = int(offs[ldg[-1]]) if ldg.size else t_to
    return t_to, t_ldg


class Planner:
    """Pure planning functions over (params, environment config, fleet, keys). No mutable state."""

    def __init__(self, p: ScenarioParams, env: EnvConfig, fleet: FleetScenario, keys: Keys) -> None:
        self.p, self.env, self.fleet, self.keys = p, env, fleet, keys
        self.th = Thresholds(
            off_hi=p.count_off_hi * RAD2DEG,
            idle_hi=p.count_idle_hi * RAD2DEG,
            irp=p.pla_irp * RAD2DEG,
            ab=p.pla_min_ab * RAD2DEG,
            hyst=p.count_hyst * RAD2DEG,
        )
        self._pilots = {sq.sid: pilot_ids(sq.sid, len(sq.tails), p) for sq in fleet.squadrons}

    def level_band(self, pla: float, lo: float, hi: float) -> tuple[float, float, float]:
        """(feed-forward, low, high) PLA clipped inside the usage level of the feed-forward (OFF / IDLE /
        CRUISE / MAX of :mod:`.usage`) **with its hysteresis margins**, so speed trims can never create or
        remove a counted cycle: the realised PLA history counts the same cycles as the plan (W2.1
        consistency; tests/statistical/test_pilot_tracking.py). MAX-level segments fly fixed power."""
        p = self.p
        eps = 0.5 / RAD2DEG
        if pla >= p.pla_irp or pla < p.count_off_hi:
            return pla, pla, pla
        if pla > p.count_idle_hi:
            blo, bhi = p.count_idle_hi + p.count_hyst, p.pla_irp - p.count_hyst - eps
        else:
            blo, bhi = p.count_off_hi + p.count_hyst, p.count_idle_hi - p.count_hyst
        ff = min(max(pla, blo), bhi)
        return ff, min(max(lo, blo), ff), max(min(hi, bhi), ff)

    # ------------------------------------------------------------------ streams
    def _gen(self, component: str, unit: int = 0, **ident) -> np.random.Generator:
        return self.keys.stream("scenario", component, **ident).generator(unit)

    def day_weather(self, sq: Squadron, d: dt.date) -> DayWeather:
        st = self.env.climatology.station(sq.base.imd_index)
        return draw_day(
            st, d.month, self._gen("weather", base=sq.base.imd_index, date=d.isoformat()), self.env.sampler
        )

    def traits(self, pilot_id: str) -> np.ndarray:
        return draw_traits(self._gen("pilot", serial=pilot_id), self.p)

    def tail_affinity(self, tail: str) -> float:
        return draw_tail_affinity(self._gen("tail", tail=tail), self.p)

    def ambient(self, sq: Squadron, day: DayWeather, t_utc_s: float) -> Ambient:
        st = self.env.climatology.station(sq.base.imd_index)
        hour = (t_utc_s % 86400.0) / 3600.0
        return ambient_at(
            st,
            day,
            hour,
            t_utc_s,
            self.env.sampler,
            field_elev_m=sq.base.field_elev_m,
            magnus=tuple(float(x) for x in self.env.magnus),
        )

    # ------------------------------------------------------------------ layer 1: calendar
    def is_flying_day(self, d: dt.date) -> bool:
        return self.fleet.is_surge(d) or bool(self.p.flying_weekdays[d.weekday()])

    def plan_day(self, d: dt.date, ov: Overrides | None = None) -> tuple[list[Slot], list[GroundRunSpec]]:
        ov = ov or Overrides()
        slots: list[Slot] = []
        runs: list[GroundRunSpec] = []
        if not self.is_flying_day(d):
            return slots, runs
        surge = self.fleet.is_surge(d)
        p = self.p
        for ordinal, sq in enumerate(self.fleet.squadrons):
            g = self._gen("day", ordinal, base=sq.base.imd_index, date=d.isoformat())
            night = bool(g.random() < p.night_wave_prob) and not surge
            hours = list(p.surge_wave_hours if surge else p.day_wave_hours)
            if night:
                hours.append(p.night_wave_hour)
            wx = self.day_weather(sq, d)
            cancel_u = g.random(len(p.surge_wave_hours) + len(p.day_wave_hours) + 1)
            order = g.permutation(len(sq.tails))
            rate = (p.surge_rate if surge else p.peace_rate) * ov.rate_scale.get(sq.sid, 1.0)
            p_slot = min(1.0, rate / len(hours))
            avail = [sq.tails[k] for k in order if sq.tails[k] not in ov.unavailable]
            for w, hour in enumerate(hours):
                is_night = hour >= p.night_wave_hour - 1e-9  # waves at or after the night-wave hour
                pc = 0.0
                if wx.fog and hour < 6.0:
                    pc = max(pc, p.cancel_fog)
                if wx.thunder and hour >= 6.0:
                    pc = max(pc, p.cancel_thunder)
                if wx.dust:
                    pc = max(pc, p.cancel_dust)
                if wx.precip:
                    pc = max(pc, p.cancel_precip)
                if cancel_u[w] < pc:
                    continue
                t_to = _utc_s(d, hour)
                keys = [slot_key(sq.sid, d, w, s) for s in range(len(sq.tails))]
                swapped = {ov.tail_swap[k] for k in keys if k in ov.tail_swap}
                # slot s is flown by the s-th tail of the day's rotation (independent of the other slots' fly
                # decisions, so a rate order does not move tails between slots); a swapped-in tail is removed
                # from the rotation so it is not double-booked in the wave
                rotation = [t for t in avail if t not in swapped]
                for s, key in enumerate(keys):
                    g0 = self._gen("slot", 0, sortie=key)
                    if not g0.random() < p_slot:
                        continue
                    if key in ov.tail_swap:
                        tail = ov.tail_swap[key]
                    elif s < len(rotation):
                        tail = rotation[s]
                    else:
                        continue
                    if tail in ov.unavailable:
                        continue
                    pil = self._pilots[sq.sid]
                    pilot = pil[int(g0.integers(0, len(pil)))]
                    serial = (
                        sq.engine_serials[sq.tails.index(tail)]
                        if tail in sq.tails
                        else f"{ENGINE_SERIAL_PREFIX}-{tail}"
                    )
                    slots.append(Slot(key, sq, d, w, s, t_to, is_night, surge, tail, serial, pilot))
            for k, tail in enumerate(sq.tails):
                if tail in ov.unavailable:
                    continue
                gr = self._gen("ground_run", tail=tail, date=d.isoformat())
                if gr.random() < p.ground_run_day_prob:
                    runs.append(GroundRunSpec(tail, sq.engine_serials[k], sq, d, _utc_s(d, 2.5)))
        return slots, runs

    # ------------------------------------------------------------------ layers 2-6: one sortie
    def _layer2(self, slot: Slot, ov: Overrides) -> tuple[int, int, float, int, int, float, float, float]:
        """Layer 2 draws of a slot (unit 0 of its ``slot`` stream): mission, airborne duration, drop tanks,
        touch-and-goes and the take-off/run-up/heading uniforms. Shared by :meth:`build_sortie` and
        :meth:`planned_flight_s`, so the flying task and the flown sortie use the same draws."""
        p, sq, mt = self.p, slot.squadron, self.p.missions
        g0 = self._gen("slot", 0, sortie=slot.key)
        g0.random()  # the fly decision (layer 1) consumed the first draw of unit 0
        g0.integers(0, len(self._pilots[sq.sid]))  # and the pilot draw
        u_mis = g0.random()
        if slot.key in ov.mission:
            mission = int(ov.mission[slot.key])
        else:
            w = (mt.ocu_mix if sq.role == ROLE_OCU else mt.ops_mix).copy()
            if sq.sid in ov.mix:
                w = np.asarray(ov.mix[sq.sid], dtype=float).copy()
            aff = self.tail_affinity(slot.tail)
            w = w * np.where(mt.high_activity == 1, aff, 1.0)
            mission = int(mt.mid[int(np.searchsorted(np.cumsum(w), u_mis * w.sum(), side="right"))])
        mr = mt.row(mission)
        z_dur, u_drop, u_shift, u_to, u_run, u_hdg = g0.standard_normal(), *g0.random(5)
        n_tg = int(g0.poisson(mt.tg_mean[mr]))
        drop = 2 if u_drop < mt.drop_prob[mr] else 0
        flight_s = p.duration_median_s * mt.dur_mult[mr] * math.exp(p.duration_sig * z_dur)
        if drop or mission == AAR:
            lo, hi = p.drop_tank_shift_s
            flight_s += lo + (hi - lo) * u_shift
        flight_s = float(np.clip(flight_s, 15 * 60, 150 * 60))
        return mission, mr, flight_s, drop, n_tg, float(u_to), float(u_run), float(u_hdg)

    def planned_flight_s(self, slot: Slot, ov: Overrides | None = None) -> float:
        """Planned airborne time of a slot (layer 2 only; no plan is built): the flying-task unit."""
        return self._layer2(slot, ov or Overrides())[2]

    def make_slot(
        self, sq: Squadron, d: dt.date, wave: int, s: int, t_to: float, night: bool, surge: bool, tail: str
    ) -> Slot:
        """A slot outside the day's rotation (an assigned sortie, ASSIGN_SORTIE): same key scheme and pilot
        draw as :meth:`plan_day` (unit 0 of the slot stream: fly-decision draw, then the pilot)."""
        key = slot_key(sq.sid, d, wave, s)
        g0 = self._gen("slot", 0, sortie=key)
        g0.random()  # the fly-decision draw (an assigned slot always flies)
        pil = self._pilots[sq.sid]
        pilot = pil[int(g0.integers(0, len(pil)))]
        serial = (
            sq.engine_serials[sq.tails.index(tail)] if tail in sq.tails else f"{ENGINE_SERIAL_PREFIX}-{tail}"
        )
        return Slot(key, sq, d, wave, s, t_to, night, surge, tail, serial, pilot)

    def usage_drivers(self, plan: SortiePlan, base: Base) -> dict[str, float | int]:
        """Plan-level usage drivers for health (``usage.sortie_summary``; faults_and_degradation.md §9(c) item
        2): time at temperature (time at or above IRP, AB included), AB time, peak Nz, chute streamings, and
        dust / salt exposure indices in exposure-hours: engine-running time on the ground or in segments below
        ``exposure_agl_m`` above the field [A-W1.1-33], times the day's dust level (1 on an IMD dust day, else
        ``dust_clear_level``) or the base salt level [A-W1.1-34]. Chute: the plan's decision
        (:meth:`chute_decision`, A-W1.1-35)."""
        p, sm = self.p, plan.summary
        if sm is None:
            raise ValueError("plan has no usage summary")
        ph = plan.seg_i[:, S_PHASE]
        exp_h, dust = exposure(p, plan)
        air = np.isin(ph, sorted(P.AIRBORNE))
        max_nz = max(1.0, float(plan.seg_f[air, S_NZ].max())) if air.any() else 1.0
        return {
            "time_at_temp_s": float(sm.irp_s),
            "ab_time_s": float(sm.ab_s),
            "max_nz": max_nz,
            "chute_streamed": int(plan.chute),
            "dust_index": exp_h * dust,
            "salt_index": exp_h * float(base.salt_level),
            "exposure_h": exp_h,
        }

    def build_sortie(self, slot: Slot, ov: Overrides | None = None) -> SortiePlan:
        ov = ov or Overrides()
        p = self.p
        sq = slot.squadron
        g1 = self._gen("slot", 1, sortie=slot.key)
        g2 = self._gen("slot", 2, sortie=slot.key)
        tr = self.traits(slot.pilot_id)
        mt = p.missions
        # --- layer 2: mission, duration, configuration, ambient
        mission, mr, flight_s, drop, n_tg, u_to, u_run, u_hdg = self._layer2(slot, ov)
        wx = self.day_weather(sq, slot.date)
        amb = self.ambient(sq, wx, slot.t_takeoff_utc_s)
        no_ab = ov.restricted_no_ab(slot.tail)
        g_cap = ov.g_cap(slot.tail, p.nz_max)
        p_to_ab = mt.to_ab_prob[mr] * tr[T_AB] + (0.3 if drop else 0.0)
        p_to_ab += 0.2 if amb.t_station_k > p.hot_day_k else 0.0
        to_ab = (u_to < min(1.0, p_to_ab)) and not no_ab
        runup = u_run < p.runup_prob
        fuel0 = p.internal_fuel_kg + drop * p.drop_tank_kg
        # --- layer 3: phase grammar (durations from unit 2)
        segs: list[
            tuple
        ] = []  # (phase, prim, dur_s, alt, mach, hdg, nz, pla, lo, hi, ab_ok, gear, brake, turn)
        fe = sq.base.field_elev_m
        gi, fi, irp = p.pla_gi, p.pla_fi, p.pla_irp
        cl, ch = p.cruise_band

        def ln(med, sig=0.3):
            return float(med * math.exp(sig * g2.standard_normal()))

        def add(
            phase,
            dur,
            *,
            pla,
            lo=None,
            hi=None,
            alt=fe,
            mach=0.0,
            hdg=0.0,
            nz=1.0,
            prim=0,
            ab=0,
            gear=1,
            brake=0,
            turn=0,
        ):
            pla, blo, bhi = self.level_band(pla, pla if lo is None else lo, pla if hi is None else hi)
            segs.append(
                (
                    phase,
                    prim,
                    float(dur),
                    alt,
                    mach,
                    hdg,
                    nz,
                    pla,
                    blo,
                    bhi,
                    ab,
                    gear,
                    brake,
                    turn,
                )
            )

        add(P.PREFLIGHT, ln(p.preflight_med_s), pla=0.0)
        add(P.ENGINE_START, p.start_s, pla=gi)
        add(P.GROUND_IDLE, ln(p.ground_idle_med_s, 0.4), pla=gi)
        add(P.TAXI_OUT, ln(p.taxi_out_med_s, p.taxi_sig), pla=gi)
        if runup:  # the check against the brakes at part power (W2.1a take-off fix, A-W2.1-8)
            add(P.RUNUP, p.runup_s, pla=p.pla_runup)
            add(P.TAXI_OUT, 20.0, pla=gi)
        to_pla = p.pla_max_ab if to_ab else irp
        add(
            P.TAKEOFF,
            p.takeoff_roll_ab_s if to_ab else p.takeoff_roll_mil_s,
            pla=to_pla,
            ab=int(to_ab),
            mach=0.25,
        )
        heading = 2.0 * math.pi * u_hdg
        alt_t = fe + mt.transit_alt[mr]
        climb_s = max(30.0, (alt_t - fe) / p.climb_rate)
        add(P.CLIMB, climb_s, pla=irp, alt=alt_t, mach=0.7, hdg=heading, gear=0)
        transit_s = ln(mt.transit_s[mr], 0.3)
        descent_s = max(30.0, (alt_t - fe - PATTERN_AGL_M) / p.descent_rate)
        pattern_s = ln(p.pattern_med_s, 0.3)
        tg_s = n_tg * p.tg_cycle_s
        approach_s = p.approach_s
        fixed_air = climb_s + 2 * transit_s + descent_s + pattern_s + tg_s + approach_s
        block_s = flight_s - fixed_air
        if block_s < 120.0:  # short sortie: shrink transits first
            transit_s = max(60.0, transit_s - (120.0 - block_s) / 2)
            block_s = max(
                120.0, flight_s - (climb_s + 2 * transit_s + descent_s + pattern_s + tg_s + approach_s)
            )
        add(P.TRANSIT, transit_s, pla=p.cruise_pla, lo=cl, hi=ch, alt=alt_t, mach=0.8, hdg=heading, gear=0)
        # --- layer 4: mission block (unit 1), with the plan-level fuel budget
        fuel_used = self._fuel(segs)
        reserve_after = self._fuel_cost(p.cruise_pla, alt_t, transit_s) + self._fuel_cost(
            fi, alt_t, descent_s
        )
        reserve_after += self._fuel_cost(p.cruise_pla, fe + PATTERN_AGL_M, pattern_s + tg_s + approach_s)
        reserve_after += self._fuel_cost(gi, fe, 900.0) + p.reserve_kg
        block, heading, fuel_block = self._mission_block(
            g1, mission, block_s, alt_t, heading, fe, tr, no_ab, g_cap, fuel0 - fuel_used - reserve_after
        )
        segs.extend(block)
        add(
            P.TRANSIT,
            transit_s,
            pla=p.cruise_pla,
            lo=cl,
            hi=ch,
            alt=alt_t,
            mach=0.8,
            hdg=(heading + math.pi) % (2 * math.pi),
            gear=0,
        )
        add(
            P.DESCENT,
            descent_s,
            pla=fi + 2.0 / RAD2DEG,
            lo=fi,
            hi=p.count_idle_hi,
            alt=fe + PATTERN_AGL_M,
            mach=0.6,
            gear=0,
            brake=1,
        )
        add(
            P.PATTERN,
            pattern_s,
            pla=p.cruise_pla - 2.0 / RAD2DEG,
            lo=cl,
            hi=ch,
            alt=fe + PATTERN_AGL_M,
            mach=0.45,
            gear=0,
        )
        for _ in range(n_tg):
            add(P.APPROACH, 60.0, pla=70.0 / RAD2DEG, lo=cl, hi=ch, alt=fe, mach=0.24, gear=1)
            add(P.TOUCH_AND_GO, 15.0, pla=irp, alt=fe + 50.0, mach=0.25, gear=1)
            add(
                P.PATTERN,
                max(30.0, p.tg_cycle_s - 75.0),
                pla=p.cruise_pla - 2.0 / RAD2DEG,
                lo=cl,
                hi=ch,
                alt=fe + PATTERN_AGL_M,
                mach=0.45,
                gear=0,
            )
        add(P.APPROACH, approach_s, pla=70.0 / RAD2DEG, lo=cl, hi=ch, alt=fe, mach=0.24, gear=1)
        add(P.LANDING, p.landing_s, pla=gi, alt=fe, gear=1, brake=1)
        add(P.TAXI_IN, ln(p.taxi_in_med_s, p.taxi_sig), pla=gi)
        if slot.surge and g2.random() < p.hot_refuel_prob_surge:
            add(P.HOT_REFUEL, ln(p.hot_refuel_s, 0.2), pla=gi)
        add(P.SHUTDOWN, ln(p.cooldown_med_s * tr[T_COOLDOWN], 0.3), pla=gi)
        t_pre = segs[0][2]
        t_takeoff_off = sum(s[2] for s in segs[: [s[0] for s in segs].index(P.TAKEOFF)])
        t_start_utc = slot.t_takeoff_utc_s - t_takeoff_off
        plan = self._assemble(
            segs,
            sortie_id=sortie_id(slot.tail, slot.t_takeoff_utc_s),
            rng_key=slot.key,
            tail=slot.tail,
            sq=sq,
            mission=mission,
            pilot=slot.pilot_id,
            night=slot.night,
            t_start_utc_s=t_start_utc,
            serial=slot.engine_serial,
            drop=drop,
            fuel=fuel0,
            amb=amb,
            traits=tr,
        )
        del t_pre, fuel_block
        return dataclasses.replace(plan, chute=self.chute_decision(plan))

    def chute_decision(self, plan: SortiePlan) -> bool:
        """Brake chute streamed at the sortie's full-stop landing: probability ``chute_prob`` [A-W1.1-35], one
        draw from the sortie's ``usage`` stream (M04 deploys it; the usage summary counts it)."""
        sm = plan.summary
        full_stop = 0 if sm is None else sm.landings - sm.touch_and_goes
        u = float(self._gen("usage", sortie=plan.rng_key).random())
        return bool(full_stop > 0 and u < self.p.chute_prob)

    def build_ground_run(self, gr: GroundRunSpec) -> SortiePlan:
        """Maintenance ground run (Chalmers 2014: avg 4.6 min engine time): start, idle, MIL check, idle."""
        p = self.p
        fe = gr.squadron.base.field_elev_m
        segs: list[tuple] = []
        mil_s = 30.0
        idle_total = max(30.0, p.ground_run_s - p.start_s - mil_s)
        for phase, dur, pla in (
            (P.ENGINE_START, p.start_s, p.pla_gi),
            (P.GROUND_RUN, 0.6 * idle_total, p.pla_gi),
            (P.GROUND_RUN, mil_s, p.pla_irp),
            (P.GROUND_RUN, 0.4 * idle_total, p.pla_gi),
        ):
            segs.append((phase, 0, dur, fe, 0.0, 0.0, 1.0, pla, pla, pla, 0, 1, 0, 0))
        wx = self.day_weather(gr.squadron, gr.date)
        amb = self.ambient(gr.squadron, wx, gr.t_start_utc_s)
        return self._assemble(
            segs,
            sortie_id=f"{gr.tail}-{gr.date:%Y%m%d}-GR",
            rng_key=f"{gr.squadron.sid}-{gr.date:%Y%m%d}-gr-{gr.tail}",
            tail=gr.tail,
            sq=gr.squadron,
            mission=GROUND_RUN,
            pilot="",
            night=False,
            t_start_utc_s=gr.t_start_utc_s,
            serial=gr.engine_serial,
            drop=0,
            fuel=p.internal_fuel_kg,
            amb=amb,
            traits=np.zeros(9),
        )

    # ------------------------------------------------------------------ internals
    def _fuel_cost(self, pla: float, alt_m: float, dur_s: float) -> float:
        p = self.p
        wf = float(np.interp(pla, p.fuel_pla, p.fuel_wf))
        delta = math.exp(-alt_m / ISOTHERMAL_SCALE_HEIGHT_M) if alt_m > 0 else 1.0  # PROXY, see the constant
        return wf * delta * dur_s

    def _fuel(self, segs) -> float:
        return sum(self._fuel_cost(s[7], s[3], s[2]) for s in segs)

    def _mission_block(self, g, mission, block_s, alt0, heading, fe, tr, no_ab, g_cap, fuel_avail):
        p = self.p
        pr = p.primitives
        mt = p.missions
        mr = mt.row(mission)
        base_w = np.asarray(mt.mix[mr], dtype=float) * np.where(pr.power_active == 1, tr[T_THROTTLE], 1.0)
        p_ab = min(1.0, mt.ab_prob[mr] * tr[T_AB])
        low_level = mt.block_alt[mr] < 1000.0
        alt = fe + mt.block_alt[mr]
        alt_min = fe + (150.0 if low_level else 1500.0)
        out: list[tuple] = []
        t = 0.0
        fuel = 0.0
        cur = -1
        while t < block_s - 1.0:
            w = base_w.copy()
            if cur >= 0:
                w[cur] = 0.0
            if w.sum() <= 0:
                w = np.where(pr.pid == P_CRUISE, 1.0, 0.0)
            k = int(np.searchsorted(np.cumsum(w), g.random() * w.sum(), side="right"))
            k = min(k, w.size - 1)
            z = g.standard_normal(2)
            u = g.random(2)
            dwell = float(min(pr.dwell_med[k] * math.exp(pr.dwell_sig[k] * z[0]), block_s - t))
            dwell = max(dwell, min(3.0, block_s - t))
            use_ab = bool(pr.ab_capable[k]) and (u[0] < p_ab or pr.pid[k] == 14) and not no_ab
            pla = pr.pla_ab[k] if use_ab else pr.pla[k]
            nz = float(np.clip(1.0 + (pr.nz[k] + pr.nz_sd[k] * z[1] - 1.0) * tr[T_G], 0.5, g_cap))
            alt = float(np.clip(alt + pr.vz[k] * dwell, alt_min, min(p.ceiling_m, fe + 12000.0)))
            if pr.turn[k]:
                heading = (heading + (1 if u[1] < 0.5 else -1) * (0.5 + u[1]) * math.pi) % (2 * math.pi)
            cost = self._fuel_cost(pla, alt, dwell)
            if fuel + cost > fuel_avail and t > 60.0:
                break  # bingo: return with the planned reserve (PROXY fuel budget)
            fuel += cost
            mach = min(float(pr.mach[k]), p.mach_max)
            prim = int(pr.pid[k])
            pla, lo, hi = self.level_band(pla, pr.pla_lo[k], pr.pla_hi[k])
            if prim == P_TANKER and not mission == AAR:
                prim = P_CRUISE
            out.append(
                (
                    P.MISSION,
                    prim,
                    dwell,
                    alt,
                    mach,
                    heading,
                    nz,
                    pla,
                    lo,
                    hi,
                    int(use_ab),
                    0,
                    0,
                    int(pr.turn[k]),
                )
            )
            t += dwell
            cur = k
        return out, heading, fuel

    def _assemble(
        self,
        segs,
        *,
        sortie_id,
        rng_key,
        tail,
        sq,
        mission,
        pilot,
        night,
        t_start_utc_s,
        serial,
        drop,
        fuel,
        amb,
        traits,
    ):
        n = len(segs)
        dur_ns = np.array([round(s[2] * NS) for s in segs], dtype=np.int64)
        t_off = np.concatenate([[0], np.cumsum(dur_ns)[:-1]]).astype(np.int64)
        seg_f = np.zeros((n, N_SEG_F))
        seg_i = np.zeros((n, N_SEG_I), dtype=np.int64)
        for j, s in enumerate(segs):
            phase, prim, _dur, alt, mach, hdg, nz, pla, lo, hi, ab, gear, brake, turn = s
            seg_f[j, S_ALT] = alt
            seg_f[j, S_MACH] = mach
            seg_f[j, S_HDG] = hdg
            seg_f[j, S_NZ] = nz
            seg_f[j, S_PLA] = pla
            seg_f[j, S_PLA_LO] = lo
            seg_f[j, S_PLA_HI] = hi
            seg_i[j, S_PHASE] = phase
            seg_i[j, S_PRIM] = prim
            seg_i[j, S_AB_OK] = ab
            seg_i[j, S_GEAR] = gear
            seg_i[j, S_BRAKE] = brake
            seg_i[j, S_TURN] = turn
        t_end = int(t_off[-1] + dur_ns[-1])
        summary = self.summarise(seg_f, seg_i, t_off, t_end, night=night, fuel_kg=self._fuel(segs))
        return SortiePlan(
            sortie_id=sortie_id,
            rng_key=rng_key,
            tail=tail,
            squadron=sq.sid,
            base=sq.base.imd_index,
            field_elev_m=sq.base.field_elev_m,
            mission_type=mission,
            pilot_id=pilot,
            night=night,
            t_start_utc_ns=round(t_start_utc_s) * NS,
            engine_serials=(serial,),
            drop_tanks=drop,
            fuel_kg=fuel,
            t_off_ns=t_off,
            seg_f=seg_f,
            seg_i=seg_i,
            t_end_off_ns=t_end,
            ambient=amb.vector(),
            pilot_traits=np.asarray(traits, dtype=float),
            summary=summary,
        )

    def pla_schedule(self, seg_f, seg_i, t_off, t_end, dt_s: float = 0.25) -> np.ndarray:
        """Planned PLA history (deg) sampled every dt_s from sortie start to cut-off (0 after the end)."""
        n = math.ceil(t_end / NS / dt_s) + 1
        t = np.arange(n) * dt_s * NS
        j = np.clip(np.searchsorted(t_off, t, side="right") - 1, 0, len(t_off) - 1)
        pla = seg_f[j, S_PLA] * RAD2DEG
        pla[t >= t_end] = 0.0
        return pla

    def summarise(self, seg_f, seg_i, t_off, t_end, *, night: bool, fuel_kg: float) -> SortieSummary:
        dt_s = 0.25
        pla = self.pla_schedule(seg_f, seg_i, t_off, t_end, dt_s)
        uc = count_usage(pla, dt_s, self.th)
        ends = np.append(t_off[1:], t_end)
        dur = (ends - t_off) / NS
        phases = seg_i[:, S_PHASE]
        phase_s: dict[int, float] = {}
        for ph, d in zip(phases.tolist(), dur.tolist(), strict=True):
            phase_s[ph] = phase_s.get(ph, 0.0) + d
        flight = float(sum(d for ph, d in phase_s.items() if ph in P.AIRBORNE or ph == P.TOUCH_AND_GO))
        engine = phases != P.PREFLIGHT
        eot = float(dur[engine].sum())
        tg = int(np.count_nonzero(phases == P.TOUCH_AND_GO))
        landings = int(np.count_nonzero(phases == P.LANDING)) + tg
        mission = phases == P.MISSION
        prim_pid = seg_i[:, S_PRIM]
        peaks = self.p.primitives.peaks
        nz_counts = []
        for lev in NZ_LEVELS:
            c = 0
            for j in np.flatnonzero(mission & (seg_f[:, S_NZ] >= lev)):
                c += int(peaks[self.p.primitives.row(int(prim_pid[j]))]) if prim_pid[j] > 0 else 0
            nz_counts.append(c)
        return SortieSummary(
            flight_s=flight,
            eot_s=eot,
            irp_s=uc.irp_s,
            ab_s=uc.ab_s,
            ab_lights=uc.ab_lights,
            type1=uc.type1,
            type3=uc.type3,
            type4=uc.type4,
            tac=uc.tac,
            landings=landings,
            touch_and_goes=tg,
            starts=int(np.count_nonzero(phases == P.ENGINE_START)),
            nz_exceed=tuple(nz_counts),  # type: ignore[arg-type]
            fuel_kg=float(fuel_kg),
            night=bool(night),
            phase_s=phase_s,
        )

    # ------------------------------------------------------------------ usage mode
    def plans_between(self, d0: dt.date, n_days: int, ov: Overrides | None = None) -> list[SortiePlan]:
        """All sortie and ground-run plans of ``n_days`` from ``d0`` (usage mode; time-ordered)."""
        out: list[SortiePlan] = []
        for k in range(n_days):
            d = d0 + dt.timedelta(days=k)
            slots, runs = self.plan_day(d, ov)
            out.extend(self.build_ground_run(r) for r in runs)
            out.extend(self.build_sortie(s, ov) for s in slots)
        out.sort(key=lambda pl: (pl.t_start_utc_ns, pl.rng_key))
        return out


__all__ = [
    "GROUND_RUN",
    "ISOTHERMAL_SCALE_HEIGHT_M",
    "GroundRunSpec",
    "Overrides",
    "Planner",
    "Slot",
    "slot_key",
    "sortie_id",
]
