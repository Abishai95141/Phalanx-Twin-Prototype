"""Proxy-mode replay adapter (architecture §14.3: "real recorded inputs (PLA, altitude, Mach, TAT) drive a
proxy engine dictionary"; §6 M02 Proxy: "replays the recorded DASHlink flight inputs instead of generating
them").

:class:`ReplayInputs` holds the recorded inputs of one flight on a uniform grid; :class:`ScenarioReplay`
serves
``scenario.epoch_utc_ns`` and ``scenario.phase`` from it (zero-order hold onto the 240 Hz truth frame).
``phalanx.pilot.PilotReplay`` serves PLA and the autothrottle state, and
``phalanx.environment.EnvironmentReplay`` the flight condition, from the same object.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from phalanx.core.module import ContractError, ModuleBase, ParamSet
from phalanx.core.state import Field, State, StateSchema
from phalanx.core.time import NS_PER_S, RG_240, TRUTH_HZ, truth_step_times_ns

from .ports import ports

DEG = np.pi / 180.0


@dataclass(frozen=True)
class ReplayInputs:
    """Recorded inputs of one flight (SI, except phase codes): ``n`` samples at ``rate_hz`` from ``t0_ns``.

    pla_rad (e, n); phase (n,) dictionary flight_phase codes (DASHlink PH codes in proxy mode);
    pressure_alt_m, mach, tat_k (n,); at_engage (n,) 0/1; at_n1_cmd (e, n) fraction of 100 % N1 (0 when
    the autothrottle is not engaged or not recorded).
    """

    t0_ns: int
    rate_hz: float
    epoch_utc_ns: int
    pla_rad: np.ndarray
    phase: np.ndarray
    pressure_alt_m: np.ndarray
    mach: np.ndarray
    tat_k: np.ndarray
    at_engage: np.ndarray
    at_n1_cmd: np.ndarray

    def __post_init__(self) -> None:
        pla = np.atleast_2d(np.asarray(self.pla_rad, dtype=np.float64))
        e, n = pla.shape
        for name in ("phase", "pressure_alt_m", "mach", "tat_k", "at_engage"):
            if np.shape(getattr(self, name)) != (n,):
                raise ContractError(f"{name} must have shape ({n},)")
        if np.shape(self.at_n1_cmd) != (e, n):
            raise ContractError(f"at_n1_cmd must have shape ({e}, {n})")
        if not self.rate_hz > 0 or n < 1:
            raise ContractError("rate_hz > 0 and at least one sample required")
        for name in ("pla_rad", "phase", "pressure_alt_m", "mach", "tat_k", "at_engage", "at_n1_cmd"):
            a = np.array(getattr(self, name), copy=True)
            if name == "pla_rad":
                a = np.atleast_2d(a).astype(np.float64)
            a.flags.writeable = False
            object.__setattr__(self, name, a)

    @property
    def n_engines(self) -> int:
        return int(self.pla_rad.shape[0])

    @property
    def n(self) -> int:
        return int(self.pla_rad.shape[1])

    def index(self, t_ns: np.ndarray) -> np.ndarray:
        """Sample index held at each truth instant (zero-order hold; clamped to the record)."""
        k = np.floor((np.asarray(t_ns, dtype=np.int64) - self.t0_ns) * self.rate_hz / NS_PER_S).astype(
            np.int64
        )
        return np.clip(k, 0, self.n - 1)

    @classmethod
    def from_flight_record(
        cls,
        rec,
        *,
        pressure_alt_m: np.ndarray,
        mach: np.ndarray,
        tat_k: np.ndarray,
        epoch_utc_ns: int = 0,
        at_engage: np.ndarray | None = None,
        at_n1_cmd_pct: np.ndarray | None = None,
    ) -> ReplayInputs:
        """From a ``phalanx.validation.FlightRecord``-like object (``pla`` deg (e, n), ``phase``, ``rate_hz``,
        ``t0_ns``) plus the flight-condition arrays the battery record does not carry."""
        pla = np.atleast_2d(np.asarray(rec.pla, dtype=np.float64))
        e, n = pla.shape
        return cls(
            t0_ns=int(rec.t0_ns),
            rate_hz=float(rec.rate_hz),
            epoch_utc_ns=int(epoch_utc_ns),
            pla_rad=pla * DEG,
            phase=np.asarray(rec.phase, dtype=np.int64),
            pressure_alt_m=np.asarray(pressure_alt_m, dtype=np.float64),
            mach=np.asarray(mach, dtype=np.float64),
            tat_k=np.asarray(tat_k, dtype=np.float64),
            at_engage=np.zeros(n, np.int64) if at_engage is None else np.asarray(at_engage, dtype=np.int64),
            at_n1_cmd=np.zeros((e, n)) if at_n1_cmd_pct is None else np.atleast_2d(at_n1_cmd_pct) / 100.0,
        )


class ScenarioReplay(ModuleBase):
    """Proxy-mode M02: held epoch and the recorded phase code (240 Hz, no randomness, no state)."""

    version = "1.0.0"
    rate = RG_240
    state_schema = StateSchema("scenario.replay", 1, (Field("tick", "<i8", ()),))

    def __init__(self, id: str, rec: ReplayInputs) -> None:
        _, self.ports_out, _ = ports()
        self.rec = rec
        super().__init__(id, ParamSet("scenario.replay", {}))

    def init(self, params, keys) -> State:
        return {"tick": np.array(0, dtype=np.int64)}

    def initial_outputs(self, state: State):
        return {
            "epoch_utc_ns": np.array(self.rec.epoch_utc_ns, dtype=np.int64),
            "phase": np.array(self.rec.phase[self.rec.index(np.array([0]))[0]], dtype=np.int64),
        }

    def step_block(self, state: State, inputs, t: np.ndarray, dt: float):
        n = int(t.size)
        t = np.asarray(t, dtype=np.int64)
        k = -((-t * TRUTH_HZ) // NS_PER_S)  # exact inverse of t_k = (k 1e9) // 240
        nxt = truth_step_times_ns(k + 1)  # outputs are the values at the end of the step
        return {"tick": np.array(int(state["tick"]) + n, dtype=np.int64)}, {
            "epoch_utc_ns": np.full(n, self.rec.epoch_utc_ns, dtype=np.int64),
            "phase": self.rec.phase[self.rec.index(nxt)].astype(np.int64),
        }

    def step(self, state: State, inputs, t: int, dt: float):
        new, out = self.step_block(state, inputs, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}


__all__ = ["ReplayInputs", "ScenarioReplay"]
