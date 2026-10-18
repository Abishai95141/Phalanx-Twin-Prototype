"""U4 (W2.4a): proxy-mode replay producers for the signals no proxy module produces (E1 verifier report
§4 U4).

In proxy mode the airframe (M06) and utilities (M09) do not run, yet M07 binds ``af.mach`` and ``util.*`` /
``health.engine``, M12 binds ``health.sensor_bias`` (and, in the Tejas map, ``af.tas``/``af.alt``), and M13
binds ``scenario.phase``. These producers serve them from the recorded DASHlink inputs (``ReplayInputs``), so
the proxy ``System`` is wired purely from the published bindings (``phalanx.proxy.system``):

- :class:`AirframeReplay` (prefix ``af``): ``mach`` (recorded, sentinel-cleaned), ``tas`` = M a(T_s) with the
  static temperature from the recorded TAT and Mach (unit recovery, as ``EnvironmentReplay``), ``alt`` = the
  recorded pressure altitude (ISA: geometric = pressure altitude) (A-W2.4a-15);
- :class:`ProxyBoundary` (prefixes ``util``, ``health``): ``bleed_extract`` = the customer bleed per
  engine from the recorded bleed/air-conditioning/anti-ice discretes (``phalanx.proxy.bleed``, W2.4a-2; 0
  when none is given), ``pto_power`` = the identified constant off-take per engine (0 when none is given;
  the N2^2 accessory load is inside M07), ``fuel_inlet_t`` = T_s + 15 K (the M07 fuel-sink convention),
  ``health.engine`` 0 (nominal build), ``health.sensor_bias`` 0 (A-W2.4a-15).
- ``scenario.phase`` / ``scenario.epoch_utc_ns`` come from ``phalanx.scenario.replay.ScenarioReplay``
  (DASHlink PH codes are the dictionary ``flight_phase`` codes 0-7).

All are deterministic functions of the record (no state but a tick counter, no randomness); outputs at step
k are the values held at the end of the step (``t_{k+1}``), as ``ScenarioReplay`` and ``PilotReplay``.
"""

from __future__ import annotations

import numpy as np

from phalanx.airframe.ports import replay_ports as airframe_replay_ports
from phalanx.core.module import ModuleBase, ParamSet, Port
from phalanx.core.state import Field, State, StateSchema
from phalanx.core.time import NS_PER_S, RG_240, TRUTH_HZ, truth_step_times_ns
from phalanx.scenario.replay import ReplayInputs

GAMMA = 1.4
R_AIR = 287.05287  # J/(kg K), dry air (USSA-76 R*/M0)
DT_FUEL_SINK = 15.0  # K, M07 default fuel-inlet temperature above ambient (configs/*/params/M07.yaml)
N_HEALTH = 10


def _index_end(rec: ReplayInputs, t: np.ndarray) -> np.ndarray:
    t = np.asarray(t, dtype=np.int64)
    k = -((-t * TRUTH_HZ) // NS_PER_S)
    return rec.index(truth_step_times_ns(k + 1))


def static_temperature(tat_k: np.ndarray, mach: np.ndarray) -> np.ndarray:
    """T_s = TAT / (1 + (gamma - 1)/2 M^2) (unit recovery factor, as ``EnvironmentReplay``)."""
    return np.asarray(tat_k, float) / (1.0 + 0.5 * (GAMMA - 1.0) * np.asarray(mach, float) ** 2)


class _ReplayBase(ModuleBase):
    version = "1.0.0"
    rate = RG_240

    def __init__(self, id: str, rec: ReplayInputs) -> None:
        self.rec = rec
        self.state_schema = StateSchema(
            f"proxy.{type(self).__name__.lower()}", 1, (Field("tick", "<i8", ()),)
        )
        super().__init__(id, ParamSet(f"proxy.{type(self).__name__.lower()}", {}))

    def init(self, params, keys) -> State:
        return {"tick": np.array(0, dtype=np.int64)}

    def _at(self, j: np.ndarray) -> dict[str, np.ndarray]:  # pragma: no cover - abstract
        raise NotImplementedError

    def initial_outputs(self, state: State):
        out = self._at(self.rec.index(np.array([0], np.int64)))
        return {k: np.array(v[0]) for k, v in out.items()}

    def step_block(self, state: State, inputs, t: np.ndarray, dt: float):
        n = int(np.asarray(t).size)
        return {"tick": np.array(int(state["tick"]) + n, dtype=np.int64)}, self._at(_index_end(self.rec, t))

    def step(self, state: State, inputs, t: int, dt: float):
        new, out = self.step_block(state, {}, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}


class AirframeReplay(_ReplayBase):
    """Proxy-mode producer of ``af.mach``, ``af.tas`` and ``af.alt`` from the recorded flight condition."""

    def __init__(self, id: str, rec: ReplayInputs) -> None:
        self.ports_in, self.ports_out = airframe_replay_ports(rec.n_engines)
        super().__init__(id, rec)

    def _at(self, j: np.ndarray) -> dict[str, np.ndarray]:
        mach = self.rec.mach[j].astype(np.float64)
        ts = static_temperature(self.rec.tat_k[j], mach)
        return {
            "mach": mach,
            "tas": mach * np.sqrt(GAMMA * R_AIR * ts),
            "alt": self.rec.pressure_alt_m[j].astype(np.float64),
        }


class ProxyBoundary(_ReplayBase):
    """Proxy-mode producer of the M09/M10 signals the engine side binds (labelled constants, A-W2.4a-15)."""

    def __init__(
        self,
        id: str,
        rec: ReplayInputs,
        n_channels: int,
        *,
        bleed_kgs: np.ndarray | None = None,
        pto_w: float = 0.0,
    ) -> None:
        e = rec.n_engines
        self.n_channels = int(n_channels)
        #: (n_engines, n samples of the record) customer bleed [kg/s]; None = no bleed
        self.bleed_kgs = None if bleed_kgs is None else np.asarray(bleed_kgs, dtype=np.float64)
        if self.bleed_kgs is not None and self.bleed_kgs.shape != (e, rec.n):
            raise ValueError(f"bleed_kgs shape {self.bleed_kgs.shape} != {(e, rec.n)}")
        self.pto_w = float(pto_w)
        self.ports_in = ()
        self.ports_out = (
            Port("bleed_extract", "kg/s", "<f8", (e,)),
            Port("pto_power", "W", "<f8", (e,)),
            Port("fuel_inlet_t", "K", "<f8", (e,)),
            Port("engine", "1", "<f8", (e, N_HEALTH)),
            Port("sensor_bias", "1", "<f8", (self.n_channels,)),
        )
        super().__init__(id, rec)

    def _at(self, j: np.ndarray) -> dict[str, np.ndarray]:
        n, e = j.size, self.rec.n_engines
        ts = static_temperature(self.rec.tat_k[j], self.rec.mach[j])
        return {
            "bleed_extract": np.zeros((n, e)) if self.bleed_kgs is None else self.bleed_kgs[:, j].T.copy(),
            "pto_power": np.full((n, e), self.pto_w),
            "fuel_inlet_t": np.repeat((ts + DT_FUEL_SINK)[:, None], e, axis=1),
            "engine": np.zeros((n, e, N_HEALTH)),
            "sensor_bias": np.zeros((n, self.n_channels)),
        }


class NoAfterburnerLane(ModuleBase):
    """The FADEC AB flame-detector lane (``lane.ENG.AB_LIT``) of a non-afterburning proxy engine (AD-43):
    there is no afterburner, so the lane reads 0 (unlit) on every frame. A buffer of M08's lane shape on its
    clock. (In the Tejas configuration this lane still has no in-loop producer: tracked W2.1 item.)"""

    version = "1.0.0"
    rate = RG_240

    def __init__(self, id: str, n_engines: int, clock) -> None:
        from phalanx.acquisition.module import lane_port
        from phalanx.fadec.ports import lane_shape

        self.shape = lane_shape(n_engines, clock)
        self.port = lane_port("ENG.AB_LIT")
        self.ports_in = ()
        self.ports_out = (Port(self.port, "1", "<f8", self.shape, clock),)
        self.state_schema = StateSchema("proxy.no_ab_lane", 1, ())
        super().__init__(id, ParamSet("proxy.no_ab_lane", {}))

    def init(self, params, keys) -> State:
        return {}

    def initial_outputs(self, state: State):
        return {self.port: np.zeros(self.shape)}

    def step_block(self, state: State, inputs, t: np.ndarray, dt: float):
        n = int(np.asarray(t).size)
        return {}, {self.port: np.zeros((n, *self.shape))}

    def step(self, state: State, inputs, t: int, dt: float):
        return {}, {self.port: np.zeros(self.shape)}


#: catalogue prefix -> proxy producer module id (the replay serves the airframe/utility/health prefixes)
PRODUCER_IDS = {
    "scenario": "scenario",
    "env": "env",
    "pilot": "pilot",
    "af": "af",
    "util": "boundary",
    "health": "boundary",
    "fadec": "fadec",
    "eng": "eng",
    "sens": "sens",
}

__all__ = ["PRODUCER_IDS", "AirframeReplay", "NoAfterburnerLane", "ProxyBoundary", "static_temperature"]
