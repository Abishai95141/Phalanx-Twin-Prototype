"""Battery configuration and pre-registered estimator constants (B1-B6).

Every constant below is copied from the round-2 pre-registration and its estimator code and must not be
changed without a new pre-registration (RULES.md rule 4):
- `analysis/settling_experiment_round2/PREREGISTRATION.md` section 4 (tests), section 5 (bars and rules);
- `analysis/settling_experiment_round2/DEVIATIONS.md` D1-D4 (estimator clarifications fixed before the
freeze);
- `analysis/settling_experiment_round2/src/battery.py`, `battery_eval.py` (the estimators themselves);
- `analysis/correlation_check/corr_check.py` (B1, bit-for-bit identical to round-2 `b1_stats`).

`BatteryConfig` holds the platform- and unit-dependent values. Its defaults are the DASHlink proxy
configuration used in round 2 (4-Hz engine words of a four-engine airliner).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np

from phalanx.validation.flightdata import DASHLINK_UNITS, FlightRecord
from phalanx.validation.units import units_equivalent

__all__ = [
    "A_GRID",
    "B3_BANDS",
    "B3_PAIRS",
    "B4_PAIRS",
    "FC_PRIMARY",
    "FC_SENSITIVITY",
    "LAG_PAIRS",
    "N_BOOT",
    "STEP_CELLS",
    "TESTS",
    "VAR_CH",
    "VERDICT_TESTS",
    "BatteryConfig",
]

# ---------------------------------------------------------------- pre-registered estimator constants
#: B1 slow/fast split: Butterworth-4 zero-phase low-pass cut-off [Hz]; 0.5 Hz is the reported sensitivity.
FC_PRIMARY = 0.2
FC_SENSITIVITY = 0.5
BUTTER_ORDER = 4
#: B1/B2/B6 minimum number of airborne samples per flight (2.5 min at 4 Hz), as corr_check.py.
MIN_AIR_SAMPLES = 600
#: B2 lead-lag pairs (cause, effect); positive lag = second channel lags. Search window +-10 s.
LAG_PAIRS: tuple[tuple[str, str], ...] = (
    ("FF", "N2"),
    ("FF", "N1"),
    ("N2", "N1"),
    ("FF", "EGT"),
    ("N1", "EGT"),
)
LAG_MAX_S = 10.0
#: B3 (i) pairs, bands [Hz], Welch segment length and minimum airborne run [s].
B3_PAIRS: tuple[tuple[str, str], ...] = (("PLA", "FF"), ("FF", "N2"), ("FF", "N1"), ("FF", "EGT"))
B3_BANDS: tuple[tuple[float, float], ...] = ((0.01, 0.05), (0.05, 0.2), (0.2, 1.0))
B3_NPERSEG = 512
B3_MIN_RUN_S = 600.0
#: B3 (ii) step responses and directions (round-1 transients.py detector, FOPDT fit).
STEP_RESP: tuple[str, ...] = ("N1", "FF", "EGT")
STEP_DIRS: tuple[str, ...] = ("accel", "decel")
STEP_CELLS: tuple[tuple[str, str], ...] = tuple((g, d) for g in STEP_RESP for d in STEP_DIRS)
STEP_MIN_DPLA_DEG = 5.0
STEP_MIN_D_LSB = 5.0
STEP_R2_MIN = 0.9
STEP_PRE_S = 5.0
STEP_POST_S = 30.0
STEP_MIN_PER_CELL = 3
#: B4 VAR order, minimum airborne segment [s], channel order and unit (engine 1 = index 0).
VAR_ORDER = 8
VAR_MIN_SEGMENT_S = 120.0
VAR_CH: tuple[str, ...] = ("FF", "N2", "N1", "EGT")
VAR_UNIT = 0
B4_PAIRS: tuple[str, ...] = tuple(f"{c}->{e}" for e in VAR_CH for c in VAR_CH if c != e)
#: B5 (ii) EGT temperature-exponent grid (0..1.2 step 0.01) and minimum decimated samples.
A_GRID = np.round(np.arange(0.0, 1.2001, 0.01), 2)
A_GRID.setflags(write=False)
B5_MIN_SAMPLES = 150
#: B6 phases with fewer airborne samples than this are missing for that flight.
B6_MIN_SAMPLES = 40
#: Flight-bootstrap resamples (pre-registration section 4; round-2 `battery_eval.NB`).
N_BOOT = 2000

#: Distance parts and the verdict grouping (DEVIATIONS.md D1: multi-part tests pass iff every part passes).
TESTS: tuple[str, ...] = (
    "B1_fast",
    "B1_slow",
    "B1h_fast",
    "B1h_slow",
    "B2",
    "B3i",
    "B3ii",
    "B4",
    "B5i",
    "B5ii",
    "B6",
)
VERDICT_TESTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "B1": ("B1_fast",),
        "B2": ("B2",),
        "B3": ("B3i", "B3ii"),
        "B4": ("B4",),
        "B5": ("B5i", "B5ii"),
        "B6": ("B6",),
    }
)

_DASHLINK_LSB = MappingProxyType({"N1": 0.03125, "N2": 0.03125, "EGT": 0.5, "FF": 8.0})
_KELVIN_OFFSET: tuple[tuple[str, float], ...] = (("degC", 273.15), ("K", 0.0))


@dataclass(frozen=True, eq=False)
class BatteryConfig:
    """Platform- and unit-dependent battery settings. Defaults: DASHlink proxy configuration (round 2).

    Attributes:
        rate_hz: analysis rate [Hz]. [MEASURED] DASHlink engine words are 4 Hz.
        families: output families, in B1 channel order (family-major, then engine position).
        n_units: engine positions. Round 2: 4.
        units: required unit per family and input. A record's unit must be pint-equivalent (same unit,
            any spelling, e.g. lb/hr = lb/h); dimensionally compatible but different units are rejected,
            because the battery never converts (AD-40).
        airborne_n1_min: airborne rule, all N1 above this [percent]. Round-2 pre-registration section 4.
        lsb_rec: recorder LSB per family, used by B3 (ii) to skip steps smaller than 5 LSB.
            [MEASURED] DASHlink (round-2 r2common.LSB_REC).
        phase_codes: B6 phase codes (DASHlink PH 1..7).
    """

    rate_hz: float = 4.0
    families: tuple[str, ...] = ("N1", "N2", "EGT", "FF")
    n_units: int = 4
    units: Mapping[str, str] = field(default_factory=lambda: DASHLINK_UNITS)
    airborne_n1_min: float = 25.0
    lsb_rec: Mapping[str, float] = field(default_factory=lambda: _DASHLINK_LSB)
    phase_codes: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7)

    @property
    def n_channels(self) -> int:
        return len(self.families) * self.n_units

    @property
    def channel_names(self) -> tuple[str, ...]:
        """B1 channel order, e.g. N1_1..N1_4, N2_1..N2_4, EGT_1..EGT_4, FF_1..FF_4."""
        return tuple(f"{f}_{k + 1}" for f in self.families for k in range(self.n_units))

    @property
    def pair_names(self) -> tuple[str, ...]:
        """Names of the upper-triangle channel pairs (B1), in np.triu_indices order."""
        ch = self.channel_names
        iu = np.triu_indices(len(ch), 1)
        return tuple(f"{ch[i]}~{ch[k]}" for i, k in zip(*iu, strict=True))

    @property
    def lag_samples(self) -> int:
        """B2 search half-width in samples (+-10 s; 40 at 4 Hz)."""
        return round(LAG_MAX_S * self.rate_hz)

    @property
    def kelvin_offset(self) -> float:
        """Offset that turns the declared EGT unit into kelvin (B5 ii)."""
        u = self.units.get("EGT", "")
        for ref, off in _KELVIN_OFFSET:
            if units_equivalent(u, ref):
                return off
        raise ValueError(f"EGT unit {u!r} is not supported by B5 (degC or K)")

    def __reduce__(self):
        return (
            BatteryConfig,
            (
                self.rate_hz,
                self.families,
                self.n_units,
                dict(self.units),
                self.airborne_n1_min,
                dict(self.lsb_rec),
                self.phase_codes,
            ),
        )

    def check(self, rec: FlightRecord) -> None:
        """Raise ValueError if a record does not match this configuration (families, units, shape, rate)."""
        if rec.rate_hz != self.rate_hz:
            raise ValueError(f"{rec.flight_id}: rate {rec.rate_hz} Hz != battery rate {self.rate_hz} Hz")
        missing = [f for f in self.families if f not in rec.outputs]
        if missing:
            raise ValueError(f"{rec.flight_id}: missing output families {missing}")
        if rec.n_units != self.n_units:
            raise ValueError(
                f"{rec.flight_id}: {rec.n_units} engine positions, battery expects {self.n_units}"
            )
        for k, u in self.units.items():
            got = rec.units.get(k)
            if got is None or not units_equivalent(got, u):
                raise ValueError(
                    f"{rec.flight_id}: unit of {k} is {got!r}, battery expects {u!r} (or an equivalent "
                    "spelling; the battery never converts)"
                )
        if "N1" not in self.families:
            raise ValueError("the airborne rule needs the N1 family")
