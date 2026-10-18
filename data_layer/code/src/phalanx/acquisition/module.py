"""M13 in-loop entry point: ``LaneAcquisition`` digitises controller sensor lanes inside the truth loop.

W1_interfaces.md §3: the DFCC and FADEC compute on what their acquisition produced. For each lane channel this
module emits a clock-domain sample buffer (``core.sampling``): the **SI value of the digitised reading**
(quantised in EU, then ``Dictionary.eu_to_si``), its acquisition instants, count and absolute sample index,
plus the acquisition-scope quality flags the hardware itself knows (sentinel, saturation, gating). Lanes bind
as ``lane.<channel_id>``; the port of lane ``ENG.N2.A`` is ``lane_eng_n2_a`` (and ``_t``, ``_n``, ``_first``,
``_q``).

The recording entry point (``record.AcquisitionRecorder``) runs the same ``AcquisitionCore`` with the same
streams, so ``eu_to_si(CIR value)`` equals the lane value at the same sample index, bitwise (acceptance A6).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from phalanx.core.module import ContractError, Inputs, ModuleBase, Outputs, ParamSet, Port
from phalanx.core.rng import Keys
from phalanx.core.sampling import max_samples_per_step, sample_ports
from phalanx.core.state import Field, State, StateSchema
from phalanx.core.time import RG_240, latest_truth_steps, truth_step_times_ns
from phalanx.sensors.config import SensorConfig, dictionary_id, engine_of, unit_group

from . import kernel as K
from .config import AcqConfig
from .core import STREAMS, AcquisitionCore

PHASE_PORT = "phase"
PHASE_SIGNAL = "scenario.phase"


def lane_port(channel_id: str) -> str:
    """Port name of a lane: ``ENG.N2.A`` -> ``lane_eng_n2_a``."""
    return "lane_" + channel_id.lower().replace(".", "_")


def _core_schema(name: str, cfg: AcqConfig) -> StateSchema:
    return StateSchema(
        name,
        1,
        (
            Field("af", "<f8", (cfg.n, K.N_AF)),
            Field("ai", "<i8", (cfg.n, K.N_AI)),
            Field("n_next", "<i8", (len(cfg.domains),)),
        ),
    )


class LaneAcquisition(ModuleBase):
    """M13 in-loop acquisition of controller lanes (one instance per controller clock domain set).

    Args:
        id, params: module id and a ParamSet for the config hash (e.g. ``load_param_set("M13", "noise_n2")``).
        sensors: the M12 ``SensorConfig`` whose outputs this module reads (``sens.s_<group>``).
        acq: ``build_acquisition_config(dictionary, lanes, sensor_channels=sensors.channels)``; every channel
            must be an M12 channel (lanes are physical sensors).
        dictionary: the M01 dictionary (EU -> SI of the lane values).
    """

    version = "1.0.0"
    rate = RG_240
    streams = STREAMS

    def __init__(
        self,
        id: str,
        params: ParamSet,
        sensors: SensorConfig,
        acq: AcqConfig,
        dictionary: Any,
        *,
        compiled: bool = True,
        identity: Mapping[str, str | int] | None = None,
    ) -> None:
        if any(s < 0 for s in acq.sensor_index):
            bad = [c for c, s in zip(acq.channels, acq.sensor_index, strict=True) if s < 0]
            raise ContractError(f"lanes must be M12 sensor channels; not measured by M12: {bad}")
        self.sensors = sensors
        self.acq = acq
        self._conv = tuple(dictionary.eu_conversion(dictionary_id(c)) for c in acq.channels)
        # where each lane's s_inst sits among M12's unit-group ports
        self._src: list[tuple[str, int]] = []
        groups_used: dict[str, tuple[int, ...]] = {}
        for si in acq.sensor_index:
            g = unit_group(sensors.si_units[si])
            members = sensors.groups[g]
            self._src.append((g, members.index(si)))
            groups_used[g] = members
        self._caps = [max_samples_per_step(d.clock) for d in acq.domains]
        ins = [
            Port(f"s_{g}", sensors.group_units[g], "<f8", (len(m),)) for g, m in sorted(groups_used.items())
        ]
        ins.append(Port(PHASE_PORT, "1", "<i8", ()))
        # U3 (W2.4a): the engine instances of one dictionary lane (``X:E1`` .. ``X:En``, n_engines > 1) form
        # one lane port of shape (capacity, n_engines), engine-ordered, as M08 expects; a plain channel keeps
        # the (capacity,) port (the Tejas configuration is unchanged)
        self._lanes: list[tuple[str, tuple[int, ...]]] = []
        by_lane: dict[str, list[tuple[int, int]]] = {}
        for c, cid in enumerate(acq.channels):
            by_lane.setdefault(dictionary_id(cid), []).append((engine_of(cid), c))
        for did, members in by_lane.items():
            engs = sorted(e for e, _ in members)
            per_engine = engs[0] >= 0
            if per_engine and engs != list(range(sensors.n_engines)):
                raise ContractError(
                    f"lane {did}: engine instances {engs} do not cover 0..{sensors.n_engines - 1}"
                )
            chans = tuple(c for _, c in sorted(members))
            doms = {int(acq.domain_of[c]) for c in chans}
            if len(doms) != 1:
                raise ContractError(f"lane {did}: engine instances on different clock domains")
            self._lanes.append((did, chans))
        outs: list[Port] = []
        for did, chans in self._lanes:
            c0 = chans[0]
            d = int(acq.domain_of[c0])
            name = lane_port(did)
            cap, clk, unit = self._caps[d], acq.domains[d].clock, self._conv[c0].si_units
            if engine_of(acq.channels[c0]) < 0:
                outs.extend(sample_ports(name, unit, cap, clk))
                outs.append(Port(f"{name}_q", "1", "<i8", (cap,)))
            else:
                e = len(chans)
                _vp, tp, npt, fp = sample_ports(name, unit, cap, clk)
                outs.extend((Port(name, unit, "<f8", (cap, e), clk), tp, npt, fp))
                outs.append(Port(f"{name}_q", "1", "<i8", (cap, e)))
        self.ports_in = tuple(ins)
        self.ports_out = tuple(outs)
        self.state_schema = _core_schema(f"acquisition.lanes.{id}", acq)
        super().__init__(id, params, identity=identity)
        self._kernel = K.acq_kernel if compiled else K.acq_kernel.py_func
        self.core = AcquisitionCore(acq, lambda comp, cid: self.stream(comp, sensor=cid))

    def bindings(self) -> dict[str, str]:
        """Input port -> catalogue signal (``sens.*`` are M12 outputs; phase from M02)."""
        b = {p.name: f"sens.{p.name}" for p in self.ports_in if p.name != PHASE_PORT}
        b[PHASE_PORT] = PHASE_SIGNAL
        return b

    def lane_bindings(self) -> dict[str, str]:
        """``lane.<channel_id>`` -> value port of this module (what a controller's lane input connects to)."""
        return {f"lane.{did}": lane_port(did) for did, _ in self._lanes}

    def init(self, params: ParamSet, keys: Keys) -> State:
        return self.core.init_state()

    def initial_outputs(self, state: State) -> Outputs:
        out: Outputs = {}
        for did, chans in self._lanes:
            d = int(self.acq.domain_of[chans[0]])
            cap = self._caps[d]
            name = lane_port(did)
            shape = (cap,) if engine_of(self.acq.channels[chans[0]]) < 0 else (cap, len(chans))
            out[name] = np.zeros(shape, dtype=np.float64)
            out[f"{name}_t"] = np.zeros(cap, dtype=np.int64)
            out[f"{name}_n"] = np.array(0, dtype=np.int64)
            out[f"{name}_first"] = np.array(int(state["n_next"][d]), dtype=np.int64)
            out[f"{name}_q"] = np.zeros(shape, dtype=np.int64)
        return out

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        acq = self.acq
        t = np.asarray(t, dtype=np.int64)
        n = t.size
        t_end = truth_step_times_ns(latest_truth_steps(t) + 1)
        S = np.empty((n, acq.n), dtype=np.float64)
        for c, (g, pos) in enumerate(self._src):
            S[:, c] = np.asarray(inputs[f"s_{g}"], dtype=np.float64).reshape(n, -1)[:, pos]
        X = np.zeros_like(S)  # lanes carry no truth (truth goes to CIR via the recorder only)
        phase = np.asarray(inputs[PHASE_PORT], dtype=np.int64).reshape(n)
        new, doms = self.core.process(dict(state), S, X, t, t_end, phase, kernel=self._kernel)
        per_ch: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
        for ds in doms:
            cap = self._caps[ds.domain]
            if ds.count.size and int(ds.count.max(initial=0)) > cap:
                raise ContractError(f"{self.id}: more samples in one step than capacity {cap}")
            for j, c in enumerate(ds.channels):
                si = self._conv[c].to_si(ds.value[:, j]) if ds.times.size else np.zeros(0)
                vals = np.zeros((n, cap), dtype=np.float64)
                ts = np.zeros((n, cap), dtype=np.int64)
                qs = np.zeros((n, cap), dtype=np.int64)
                vals[ds.step, ds.slot] = si
                ts[ds.step, ds.slot] = ds.times
                qs[ds.step, ds.slot] = ds.flags[:, j]
                per_ch[c] = (vals, ts, qs, ds.count.copy(), ds.first_of_step.copy())
        out: Outputs = {}
        for did, chans in self._lanes:
            name = lane_port(did)
            vals, ts, qs, cnt, first = per_ch[chans[0]]
            if engine_of(acq.channels[chans[0]]) >= 0:  # engine instances -> (n, capacity, n_engines)
                vals = np.stack([per_ch[c][0] for c in chans], axis=2)
                qs = np.stack([per_ch[c][2] for c in chans], axis=2)
            out[name] = vals
            out[f"{name}_t"] = ts
            out[f"{name}_n"] = cnt
            out[f"{name}_first"] = first
            out[f"{name}_q"] = qs
        return new, out

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        """Per-step execution is ``step_block`` with L = 1 (bitwise identical by construction)."""
        one = {k: np.asarray(v)[None, ...] for k, v in inputs.items()}
        new, out = self.step_block(state, one, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}


def lane_channels(dictionary: Any, sensors: SensorConfig, controller: str) -> tuple[str, ...]:
    """The M12 lane channels a controller acquires (``role == lane`` and ``acq_lru`` == ``controller``, or
    the ADC lanes for the DFCC). For the FADEC this also includes its single-channel engine sensors (T25,
    T5 harnesses, P5, oil, WFM), which the FADEC reads in-loop."""
    lrus = {"DFCC": ("DFCC", "ADC"), "FADEC": ("FADEC",)}.get(controller, (controller,))
    out = []
    for cid in sensors.channels:  # engine instances (U3) are lanes of their dictionary channel
        ch = dictionary.channel(dictionary_id(cid))
        if ch["acq_lru"] in lrus and ch["rates"]["acquisition"] in ("FCS80", "FADEC-INT"):
            out.append(cid)
    return tuple(out)
