"""M12 module: ``SensorPhysics`` (truth -> s_inst) inside the 240 Hz kernel (architecture §5.5, AD-36).

Inputs are the W1 truth ports named in the channel map (``eng.*``, ``af.*``, ``env.*``, ``util.*``, ``fcs.*``,
``pilot.*``) plus ``health.sensor_bias``; outputs are the sensor readings ``s_inst`` and the true measurands,
grouped by SI unit (``s_<group>``, ``x_<group>``; the index map of each group is ``config.groups[group]``).
M13 consumes them (in-loop at the controllers' clock domains, and for recording).

Sensor-fault modes arrive as M11 events (kind ``sensor_fault``) and change state only (I6: the generation path
is identical for healthy and faulty runs). Fault state and installation biases are hidden truth: they never
appear on an output port except through the reading they perturb.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from phalanx.core.events import Event
from phalanx.core.module import ContractError, Inputs, ModuleBase, Outputs, ParamSet, Port
from phalanx.core.rng import Keys, StreamDecl, Variate
from phalanx.core.state import Field, State, StateSchema
from phalanx.core.time import RG_240, latest_truth_steps, truth_step_times_ns

from . import kernel as K
from .config import SensorConfig

SENSOR_FAULT_EVENT = "sensor_fault"
BIAS_PORT = "health_sensor_bias"
BIAS_SIGNAL = "health.sensor_bias"
FAULT_STREAM = StreamDecl(
    "sensors",
    "fault",
    ("scenario", "tail", "sortie", "sensor"),
    Variate.UNIFORM,
    4096,
    "phalanx.sensors (M12)",
    "per-frame uniforms of stochastic sensor-fault modes (intermittent, spikes); index = absolute frame",
)
_STOCHASTIC = (K.FM_INTERMITTENT, K.FM_SPIKES)
_MODE = {n: i for i, n in enumerate(K.FAULT_MODES)}


def _schema(cfg: SensorConfig) -> StateSchema:
    return StateSchema(
        f"sensors.m12.{cfg.platform}",
        1,
        (
            Field("ef", "<f8", (cfg.n_el, K.N_EF)),
            Field("ei", "<i8", (cfg.n_el, K.N_EI)),
            Field("cf", "<f8", (cfg.n_ch, K.N_CF)),
            Field("ci", "<i8", (cfg.n_ch, K.N_CI)),
            Field("xl", "<f8", (cfg.n_ch,)),
            Field("tick", "<i8", ()),
        ),
    )


def output_ports(cfg: SensorConfig) -> tuple[Port, ...]:
    ports = []
    for g, idx in cfg.groups.items():
        u = cfg.group_units[g]
        ports.append(Port(f"s_{g}", u, "<f8", (len(idx),)))
        ports.append(Port(f"x_{g}", u, "<f8", (len(idx),)))
    return tuple(ports)


def input_ports(cfg: SensorConfig) -> tuple[Port, ...]:
    ports = [Port(s.port, s.unit, s.dtype, s.shape) for s in cfg.inputs]
    ports.append(Port(BIAS_PORT, "1", "<f8", (cfg.n_ch,)))
    return tuple(ports)


def input_bindings(cfg: SensorConfig) -> dict[str, str]:
    b = {s.port: s.signal for s in cfg.inputs}
    b[BIAS_PORT] = BIAS_SIGNAL
    return b


class SensorPhysics(ModuleBase):
    """M12: H_sensor, D_sensor, installation bias, sensor faults; 240 Hz, compiled kernel (AD-22).

    Args:
        id: module id; params: any ParamSet (the M12 ParamSets are folded into ``config``; pass
            ``load_param_set("M12", "constants")`` so the config hash covers them, or the config's own set).
        config: ``build_sensor_config(...)`` output. compiled: False runs the NumPy reference
        (``m12_kernel.py_func``) through the scheduler.
    """

    version = "1.0.0"
    rate = RG_240
    streams = (FAULT_STREAM,)

    def __init__(
        self,
        id: str,
        params: ParamSet,
        config: SensorConfig,
        *,
        compiled: bool = True,
        identity: Mapping[str, str | int] | None = None,
    ) -> None:
        self.config = config
        self.ports_in = input_ports(config)
        self.ports_out = output_ports(config)
        self.state_schema = _schema(config)
        super().__init__(id, params, identity=identity)
        self._kernel = K.m12_kernel if compiled else K.m12_kernel.py_func
        self._ports = [(s.port, s.size) for s in config.inputs]

    # ------------------------------------------------------------------ state
    def init(self, params: ParamSet, keys: Keys) -> State:
        cfg = self.config
        ef = np.zeros((cfg.n_el, K.N_EF), dtype=np.float64)
        ef[:, K.EF_SLOW] = 1.0
        ci = np.zeros((cfg.n_ch, K.N_CI), dtype=np.int64)
        ci[:, K.CI_HOLDIDX] = -1
        return {
            "ef": ef,
            "ei": np.zeros((cfg.n_el, K.N_EI), dtype=np.int64),
            "cf": np.zeros((cfg.n_ch, K.N_CF), dtype=np.float64),
            "ci": ci,
            "xl": np.zeros(cfg.n_ch, dtype=np.float64),
            "tick": np.array(0, dtype=np.int64),
        }

    def _group_out(self, s: np.ndarray, x: np.ndarray) -> Outputs:
        out: Outputs = {}
        for g, idx in self.config.groups.items():
            ii = np.asarray(idx, dtype=np.int64)
            out[f"s_{g}"] = np.ascontiguousarray(s[..., ii])
            out[f"x_{g}"] = np.ascontiguousarray(x[..., ii])
        return out

    def initial_outputs(self, state: State) -> Outputs:
        """Before the first step the sensors have not seen truth (A-W1.6-2): zeros, never NaN. M13 ignores the
        frame-0 values (it primes its interpolation from the first stepped frame)."""
        return self._group_out(np.array(state["cf"][:, K.CF_LAST]), np.array(state["xl"]))

    # ------------------------------------------------------------------ stepping
    def _truth_rows(self, inputs: Inputs, n: int) -> np.ndarray:
        cols = []
        for port, size in self._ports:
            a = np.asarray(inputs[port], dtype=np.float64)
            cols.append(a.reshape(n, size))
        return np.ascontiguousarray(np.concatenate(cols, axis=1))

    def fault_draws(self, state: State, n: int) -> np.ndarray:
        """Uniforms for channels with an active stochastic fault, indexed by absolute frame (zeros
        elsewhere)."""
        u = np.zeros((n, self.config.n_ch), dtype=np.float64)
        modes = state["ci"][:, K.CI_MODE]
        active = np.flatnonzero(np.isin(modes, _STOCHASTIC))
        tick0 = int(state["tick"])
        for c in active:
            u[:, c] = self.stream("fault", sensor=self.config.channels[c]).draws(tick0, n)
        return u

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        cfg = self.config
        n = int(np.asarray(t).size)
        U = self._truth_rows(inputs, n)
        bias = np.ascontiguousarray(np.asarray(inputs[BIAS_PORT], dtype=np.float64).reshape(n, cfg.n_ch))
        t_end = truth_step_times_ns(latest_truth_steps(np.asarray(t, dtype=np.int64)) + 1)
        fu = self.fault_draws(state, n)
        ef, ei, cf, ci, S, X = self._kernel(
            state["ef"],
            state["ei"],
            state["cf"],
            state["ci"],
            cfg.el_i,
            cfg.el_p,
            cfg.ch_i,
            cfg.ch_p,
            cfg.tx,
            cfg.ty,
            cfg.toff,
            cfg.cols,
            cfg.k,
            U,
            bias,
            t_end,
            fu,
            dt,
            cfg.n_sub,
        )
        new = {
            "ef": ef,
            "ei": ei,
            "cf": cf,
            "ci": ci,
            "xl": np.array(X[-1]),
            "tick": np.array(int(state["tick"]) + n, dtype=np.int64),
        }
        return new, self._group_out(S, X)

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        """Per-step execution is ``step_block`` with L = 1 (bitwise identical by construction)."""
        one = {k: np.asarray(v)[None, ...] for k, v in inputs.items()}
        new, out = self.step_block(state, one, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}

    # ------------------------------------------------------------------ sensor faults (M11 events)
    def on_event(self, state: State, event: Event, t: int) -> tuple[State, list[Event]]:
        if event.kind != SENSOR_FAULT_EVENT:
            return super().on_event(state, event, t)
        new = {k: np.array(v, copy=True) for k, v in state.items()}
        apply_sensor_fault(self.config, new, dict(event.payload), int(t))
        return new, []


def apply_sensor_fault(
    cfg: SensorConfig, state: dict[str, np.ndarray], payload: Mapping[str, Any], t_ns: int
) -> None:
    """Apply one ``sensor_fault`` payload to (a mutable copy of) the M12 state.

    Payload (W1.5 M11 -> M12 contract, proposed): ``channel`` (dictionary channel id), ``mode`` in
    ``bias | drift | stuck | open | short | intermittent | spikes | slow | probe_open | probe_short | clear``,
    ``value`` (SI: bias step, drift rate per second, short reading, spike amplitude, probe short reading; for
    ``slow`` the time-constant multiplier >= 1), ``rate`` (1/s: spike rate or intermittent switching rate),
    ``duty`` (intermittent long-run open fraction) and ``probe`` (harness probe index for probe modes).
    """
    payload = {k: (v.item() if isinstance(v, np.ndarray) and v.ndim == 0 else v) for k, v in payload.items()}
    cid = payload.get("channel")
    mode = payload.get("mode")
    if not isinstance(cid, str) or not isinstance(mode, str):
        raise ContractError(f"sensor_fault payload needs 'channel' and 'mode' strings, got {dict(payload)}")
    c = cfg.channel_index(cid)
    els = cfg.elements_of(cid)
    value = float(payload.get("value", 0.0))
    cf, ci, ef, ei = state["cf"], state["ci"], state["ef"], state["ei"]
    if not np.isfinite(value):
        raise ContractError("sensor_fault value must be finite")
    if mode == "clear":
        ci[c, K.CI_MODE] = K.FM_NONE
        ci[c, K.CI_ISTATE] = 0
        for e in els:
            ei[e, K.EI_MODE] = K.EMODE_OK
            ef[e, K.EF_SLOW] = 1.0
        return
    if mode == "slow":
        if value < 1.0:
            raise ContractError("slow-response multiplier must be >= 1")
        for e in els:
            ef[e, K.EF_SLOW] = value
        return
    if mode in ("probe_open", "probe_short"):
        p = int(payload.get("probe", -1))
        if not 0 <= p < len(els):
            raise ContractError(f"{cid}: probe index {p} outside 0..{len(els) - 1}")
        e = els[p]
        ei[e, K.EI_MODE] = K.EMODE_OPEN if mode == "probe_open" else K.EMODE_SHORT
        ef[e, K.EF_SHORTV] = value
        return
    if mode not in _MODE or mode == "none":
        raise ContractError(f"unknown sensor fault mode {mode!r}")
    m = _MODE[mode]
    ci[c, K.CI_MODE] = m
    ci[c, K.CI_ISTATE] = 0
    cf[c, K.CF_FVAL] = value
    cf[c, K.CF_FRATE] = value if m == K.FM_DRIFT else float(payload.get("rate", 0.0))
    if m in _STOCHASTIC and not cf[c, K.CF_FRATE] > 0.0:
        raise ContractError(f"{mode} fault needs rate > 0 (events per second)")
    cf[c, K.CF_FT0] = t_ns / 1e9
    cf[c, K.CF_STUCK] = cf[c, K.CF_LAST]
    duty = float(payload.get("duty", 0.5))
    if m == K.FM_INTERMITTENT and not 0.0 < duty < 1.0:
        raise ContractError("intermittent duty must be in (0, 1)")
    cf[c, K.CF_DUTY] = duty
