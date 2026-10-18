"""The battery's input structure: one flight of recorder-level channels at the analysis rate.

`FlightRecord` is the contract between producers (the DASHlink loader in `phalanx.validation.dashlink`, the
proxy-mode outputs of W2.4, a future reader of the ground-decoder contract) and the behavioural battery.

Values are **decoded engineering values** (contract `value_eu`, architecture §12), not internal SI states:
the round-2 estimators were pre-registered on recorder units (airborne rule N1 > 25 %, recorder LSBs,
EGT in degC), so the battery checks the declared units against its configuration instead of converting.
Every array is on one uniform grid at `rate_hz`; sample k sits at `t0_ns + (k * 10**9) // rate` ns when the
rate divides 1 s (AD-35 int64 ns time base).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np

__all__ = ["DASHLINK_UNITS", "FlightRecord"]

#: Units of the DASHlink proxy configuration (round 2). N1/N2 are percent of rated speed.
DASHLINK_UNITS: Mapping[str, str] = MappingProxyType(
    {
        "N1": "percent",
        "N2": "percent",
        "EGT": "degC",
        "FF": "lb/h",
        "PLA": "deg",
        "theta": "dimensionless",
        "delta": "dimensionless",
    }
)


def _as_2d(name: str, a: np.ndarray) -> np.ndarray:
    a = np.array(a, dtype=np.float64, copy=True)
    if a.ndim != 2:
        raise ValueError(f"{name}: expected shape (n_units, n), got {a.shape}")
    if not np.all(np.isfinite(a)):
        raise ValueError(f"{name}: non-finite values (the contract uses sentinels + validity, never NaN)")
    a.setflags(write=False)
    return a


def _as_1d(name: str, a: np.ndarray, dtype: type) -> np.ndarray:
    a = np.array(a, dtype=dtype, copy=True)
    if a.ndim != 1:
        raise ValueError(f"{name}: expected shape (n,), got {a.shape}")
    if dtype is np.float64 and not np.all(np.isfinite(a)):
        raise ValueError(f"{name}: non-finite values")
    a.setflags(write=False)
    return a


@dataclass(frozen=True, eq=False)
class FlightRecord:
    """One flight for the behavioural battery (read-only arrays, validated on construction).

    Attributes:
        flight_id: stable identity of the flight (e.g. the DASHlink file stem or a `sortie_id`).
        rate_hz: analysis rate in Hz (4.0 for the DASHlink engine words).
        outputs: family -> array (n_units, n) of recorded values, e.g. ``{"N1": ..., "N2": ..., "EGT": ...,
            "FF": ...}``; row k is engine position k+1.
        pla: (n_units, n) power-lever angle per engine position [deg] (the input that defines throttle steps).
        theta: (n,) inlet total-temperature ratio (TAT + 273.15) / 288.15 [dimensionless].
        delta: (n,) inlet total-pressure ratio [dimensionless].
        phase: (n,) integer flight-phase code (DASHlink PH 1..7 in proxy mode).
        units: unit string per family and per input (``PLA``, ``theta``, ``delta``).
        t0_ns: time of sample 0 in int64 nanoseconds (AD-35).
        meta: free-form provenance strings (tail, source, date, generator version, ...).
    """

    flight_id: str
    rate_hz: float
    outputs: Mapping[str, np.ndarray]
    pla: np.ndarray
    theta: np.ndarray
    delta: np.ndarray
    phase: np.ndarray
    units: Mapping[str, str] = field(default_factory=lambda: DASHLINK_UNITS)
    t0_ns: int = 0
    meta: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (self.rate_hz > 0):
            raise ValueError(f"rate_hz must be > 0, got {self.rate_hz}")
        outs = {k: _as_2d(f"outputs[{k}]", v) for k, v in self.outputs.items()}
        if not outs:
            raise ValueError("outputs is empty")
        shapes = {v.shape for v in outs.values()}
        if len(shapes) != 1:
            raise ValueError(f"all output families must share one shape, got {shapes}")
        (n_units, n) = shapes.pop()
        pla = _as_2d("pla", self.pla)
        if pla.shape != (n_units, n):
            raise ValueError(f"pla shape {pla.shape} != outputs shape {(n_units, n)}")
        theta = _as_1d("theta", self.theta, np.float64)
        delta = _as_1d("delta", self.delta, np.float64)
        phase = _as_1d("phase", self.phase, np.int64)
        for nm, a in (("theta", theta), ("delta", delta), ("phase", phase)):
            if a.size != n:
                raise ValueError(f"{nm} has {a.size} samples, outputs have {n}")
        object.__setattr__(self, "outputs", MappingProxyType(outs))
        object.__setattr__(self, "pla", pla)
        object.__setattr__(self, "theta", theta)
        object.__setattr__(self, "delta", delta)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "units", MappingProxyType(dict(self.units)))
        object.__setattr__(self, "meta", MappingProxyType(dict(self.meta)))
        object.__setattr__(self, "t0_ns", int(self.t0_ns))

    @property
    def n(self) -> int:
        """Number of samples per channel."""
        return int(next(iter(self.outputs.values())).shape[1])

    @property
    def n_units(self) -> int:
        """Number of engine positions (rows of every output array)."""
        return int(next(iter(self.outputs.values())).shape[0])

    def __reduce__(self):
        # mapping proxies are not picklable; rebuild from plain dicts (used by process-parallel statistics)
        return (
            FlightRecord,
            (
                self.flight_id,
                self.rate_hz,
                dict(self.outputs),
                self.pla,
                self.theta,
                self.delta,
                self.phase,
                dict(self.units),
                self.t0_ns,
                dict(self.meta),
            ),
        )

    def replace_outputs(self, outputs: Mapping[str, np.ndarray], **meta: str) -> FlightRecord:
        """A copy with new output arrays and the same inputs (used to build synthetic or control versions)."""
        m = dict(self.meta)
        m.update(meta)
        return FlightRecord(
            flight_id=self.flight_id,
            rate_hz=self.rate_hz,
            outputs=outputs,
            pla=self.pla,
            theta=self.theta,
            delta=self.delta,
            phase=self.phase,
            units=self.units,
            t0_ns=self.t0_ns,
            meta=m,
        )
