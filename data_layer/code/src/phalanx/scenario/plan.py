"""Sortie plans and usage summaries: the M02 hand-off (AD-28 layer 6) and the usage-mode output.

A :class:`SortiePlan` is the content of the ``scenario.sortie_plan`` event (W1_interfaces §2 M02): sortie id,
tail, configuration, base, mission type, pilot, ambient and the **phase segments**
``[(phase, t_start, targets: alt m, Mach, heading rad, Nz g, PLA rad and trim band, AB allowed, gear,
airbrake, ...)]``. It encodes to a flat event payload (NumPy arrays only) and back without loss.

Times: segment offsets are int64 ns from the sortie start (the PREFLIGHT start); ``t_start_utc_ns`` is the
sortie start in UTC (contract time, AD-38). Consumers place the plan on their kernel clock with the event's
``t_kernel0_ns`` (the kernel time of the sortie start in the receiving System).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# segment float columns
S_ALT, S_MACH, S_HDG, S_NZ, S_PLA, S_PLA_LO, S_PLA_HI, S_TAS = 0, 1, 2, 3, 4, 5, 6, 7
SEG_F_NAMES = ("alt_m", "mach", "heading_rad", "nz_g", "pla_rad", "pla_lo_rad", "pla_hi_rad", "tas_mps")
N_SEG_F = len(SEG_F_NAMES)
# segment int columns
S_PHASE, S_PRIM, S_AB_OK, S_GEAR, S_BRAKE, S_TURN = 0, 1, 2, 3, 4, 5
SEG_I_NAMES = ("phase", "primitive", "ab_allowed", "gear_down", "airbrake", "turn_dir")
N_SEG_I = len(SEG_I_NAMES)

# usage summary vector layout (SortieSummary.vector)
U_NAMES = (
    "flight_s",
    "eot_s",
    "irp_s",
    "ab_s",
    "ab_lights",
    "type1",
    "type3",
    "type4",
    "tac",
    "landings",
    "touch_and_goes",
    "starts",
    "nz_ge3",
    "nz_ge4",
    "nz_ge5",
    "nz_ge6",
    "nz_ge7",
    "nz_ge8",
    "fuel_kg",
    "night",
)


@dataclass(frozen=True)
class SortieSummary:
    """Usage-mode output for one sortie (or ground run): durations, cycles, counters (AD-28; R§4 gates).

    Counted from the plan's power-lever schedule with :mod:`phalanx.scenario.usage` (the same counter
    applies to a realised PLA history in telemetry mode)."""

    flight_s: float
    eot_s: float
    irp_s: float
    ab_s: float
    ab_lights: int
    type1: int
    type3: int
    type4: int
    tac: float
    landings: int
    touch_and_goes: int
    starts: int
    nz_exceed: tuple[int, int, int, int, int, int]  # peaks >= 3, 4, 5, 6, 7, 8 g
    fuel_kg: float
    night: bool
    phase_s: dict[int, float] = field(default_factory=dict)

    def vector(self) -> np.ndarray:
        return np.array(
            [
                self.flight_s,
                self.eot_s,
                self.irp_s,
                self.ab_s,
                self.ab_lights,
                self.type1,
                self.type3,
                self.type4,
                self.tac,
                self.landings,
                self.touch_and_goes,
                self.starts,
                *self.nz_exceed,
                self.fuel_kg,
                float(self.night),
            ],
            dtype=np.float64,
        )

    @classmethod
    def from_vector(cls, v: np.ndarray, phase_s: dict[int, float] | None = None) -> SortieSummary:
        v = np.asarray(v, dtype=np.float64)
        if v.shape != (len(U_NAMES),):
            raise ValueError("bad summary vector")
        return cls(
            float(v[0]),
            float(v[1]),
            float(v[2]),
            float(v[3]),
            int(v[4]),
            int(v[5]),
            int(v[6]),
            int(v[7]),
            float(v[8]),
            int(v[9]),
            int(v[10]),
            int(v[11]),
            tuple(int(x) for x in v[12:18]),  # type: ignore[arg-type]
            float(v[18]),
            bool(v[19]),
            dict(phase_s or {}),
        )


@dataclass(frozen=True)
class SortiePlan:
    sortie_id: str  # tail + date + take-off time (architecture §5.3)
    rng_key: str  # stable slot identity used as the RNG `sortie` key (CRN under swaps and delays)
    tail: str
    squadron: str
    base: int  # IMD station index of the base
    field_elev_m: float
    mission_type: int
    pilot_id: str
    night: bool
    t_start_utc_ns: int
    engine_serials: tuple[str, ...]
    drop_tanks: int
    fuel_kg: float
    t_off_ns: np.ndarray  # (nseg,) int64 offsets of segment starts from the sortie start
    seg_f: np.ndarray  # (nseg, N_SEG_F)
    seg_i: np.ndarray  # (nseg, N_SEG_I)
    t_end_off_ns: int  # end of the last segment (engine cut-off)
    ambient: np.ndarray  # environment.climatology.Ambient vector
    pilot_traits: np.ndarray  # scenario.pilots.TRAIT_NAMES
    summary: SortieSummary | None = None
    chute: bool = False  # brake chute streamed at the full-stop landing (A-W1.1-35)

    def __post_init__(self) -> None:
        n = np.asarray(self.t_off_ns).size
        for name, arr, cols in (("seg_f", self.seg_f, N_SEG_F), ("seg_i", self.seg_i, N_SEG_I)):
            if np.shape(arr) != (n, cols):
                raise ValueError(f"{name} must have shape ({n}, {cols})")
        if n == 0 or np.any(np.diff(self.t_off_ns) < 0) or self.t_end_off_ns < int(self.t_off_ns[-1]):
            raise ValueError("segments must be non-empty and time-ordered")

    @property
    def n_segments(self) -> int:
        return int(np.asarray(self.t_off_ns).size)

    def segment_durations_s(self) -> np.ndarray:
        ends = np.append(np.asarray(self.t_off_ns[1:], dtype=np.int64), self.t_end_off_ns)
        return (ends - np.asarray(self.t_off_ns, dtype=np.int64)) / 1e9

    def to_payload(self, t_kernel0_ns: int = 0) -> dict[str, object]:
        p: dict[str, object] = {
            "sortie_id": self.sortie_id,
            "rng_key": self.rng_key,
            "tail": self.tail,
            "squadron": self.squadron,
            "base": int(self.base),
            "field_elev_m": float(self.field_elev_m),
            "mission_type": int(self.mission_type),
            "pilot_id": self.pilot_id,
            "night": bool(self.night),
            "t_start_utc_ns": int(self.t_start_utc_ns),
            "t_kernel0_ns": int(t_kernel0_ns),
            "engine_serials": np.array(self.engine_serials),
            "drop_tanks": int(self.drop_tanks),
            "fuel_kg": float(self.fuel_kg),
            "t_off_ns": np.asarray(self.t_off_ns, dtype=np.int64),
            "seg_f": np.asarray(self.seg_f, dtype=np.float64),
            "seg_i": np.asarray(self.seg_i, dtype=np.int64),
            "t_end_off_ns": int(self.t_end_off_ns),
            "ambient": np.asarray(self.ambient, dtype=np.float64),
            "pilot_traits": np.asarray(self.pilot_traits, dtype=np.float64),
            "duration_s": float(self.t_end_off_ns) / 1e9,
        }
        if self.summary is not None:
            p["summary"] = self.summary.vector()
        p["chute"] = bool(self.chute)
        return p

    @classmethod
    def from_payload(cls, p) -> tuple[SortiePlan, int]:
        """(plan, t_kernel0_ns) from an event payload."""

        def s(k):
            return str(np.asarray(p[k]))

        summ = SortieSummary.from_vector(np.asarray(p["summary"])) if "summary" in p else None
        plan = cls(
            sortie_id=s("sortie_id"),
            rng_key=s("rng_key"),
            tail=s("tail"),
            squadron=s("squadron"),
            base=int(np.asarray(p["base"])),
            field_elev_m=float(np.asarray(p["field_elev_m"])),
            mission_type=int(np.asarray(p["mission_type"])),
            pilot_id=s("pilot_id"),
            night=bool(np.asarray(p["night"])),
            t_start_utc_ns=int(np.asarray(p["t_start_utc_ns"])),
            engine_serials=tuple(str(x) for x in np.atleast_1d(np.asarray(p["engine_serials"]))),
            drop_tanks=int(np.asarray(p["drop_tanks"])),
            fuel_kg=float(np.asarray(p["fuel_kg"])),
            t_off_ns=np.array(p["t_off_ns"], dtype=np.int64),
            seg_f=np.array(p["seg_f"], dtype=np.float64),
            seg_i=np.array(p["seg_i"], dtype=np.int64),
            t_end_off_ns=int(np.asarray(p["t_end_off_ns"])),
            ambient=np.array(p["ambient"], dtype=np.float64),
            pilot_traits=np.array(p["pilot_traits"], dtype=np.float64),
            summary=summ,
            chute=bool(np.asarray(p["chute"])) if "chute" in p else False,
        )
        return plan, int(np.asarray(p["t_kernel0_ns"]))

    def phase_at(self, t_off_ns: int) -> int:
        """Fine phase in force at an offset from the sortie start (POSTFLIGHT after the end)."""
        from .phases import POSTFLIGHT

        if t_off_ns >= self.t_end_off_ns:
            return POSTFLIGHT
        j = int(np.searchsorted(self.t_off_ns, t_off_ns, side="right") - 1)
        return int(self.seg_i[max(j, 0), S_PHASE])


__all__ = [
    "N_SEG_F",
    "N_SEG_I",
    "SEG_F_NAMES",
    "SEG_I_NAMES",
    "U_NAMES",
    "SortiePlan",
    "SortieSummary",
]
