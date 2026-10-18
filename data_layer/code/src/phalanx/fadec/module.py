"""`Fadec`: the M08 module (architecture §6 M08) in the AD-22 layout inside the §5.5/AD-36 contract.

One instance controls `n_engines` engines (vectorised). It runs at 240 Hz (`rate = RG_240`) and executes the
FADEC frames of its own clock domain (60 Hz nominal, AD-39) that fall in [t_{k-1}, t_k) at truth step k, so
each
frame's commands apply from t_k (the first truth frame after the compute instant, architecture §8). Lane
inputs
are sample buffers `(capacity, n_engines)` following the convention in `ports.py` / `coupling.py`.

`step_block` calls the compiled kernel once per block; `step` is `step_block` with L = 1 (bitwise identical by
construction). With `event_target` set, the module emits fault/caution events on fault-bit transitions
(`emits_events = True`) from `step_block` too (`step_block_emits_events`, core block-mode events; W2.1b), so
the scheduler keeps running it in blocks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from phalanx.core.events import Event
from phalanx.core.module import ContractError, EventNotHandledError, Inputs, ModuleBase, Outputs, ParamSet
from phalanx.core.sampling import samples_for_steps
from phalanx.core.state import State
from phalanx.core.time import RG_240, latest_truth_step, truth_step_times_ns

from . import faults as _faults
from .codes import FAULT_BY_BIT, NS, recorded_words
from .kernel import fadec_block
from .layout import (
    F_A8_CMD,
    F_CVG_CMD,
    F_FVG_CMD,
    F_WF_CMD,
    G_LAST_FRAME_T,
    G_N_NEXT,
    I_FAULTS,
    NF,
    NG,
    NI,
    O_A8,
    O_AB_EN,
    O_CVG,
    O_FAULTS,
    O_FVG,
    O_IGN,
    O_LIMITER,
    O_SEL,
    O_VSTATE,
    O_WF,
    O_WF_AB,
    state_schema,
)
from .params import FadecConfig
from .ports import (
    DEFAULT_CLOCK,
    LANE_PORTS,
    LANE_SLOT,
    LANES_PER_SENSOR,
    N_LANE_SLOTS,
    RECORDED,
    RECORDED_SENSOR,
    capacity,
    ports,
)
from .reference import kernel_reference


class Fadec(ModuleBase):
    """M08 FADEC: signal validation + MIN/MAX control law + protection, vectorised over `n_engines`.

    Parameters
    ----------
    params: the merged M08 ParamSet (`load_fadec_params`).
    n_engines: engines controlled by this instance (Tejas 1, DASHlink proxy 2).
    clock: the FADEC oscillator (shared with the in-loop lane source, see `coupling.py`).
    autothrottle: add the proxy-mode autothrottle inputs and outer loop.
    initial_wf, initial_a8, initial_vg: commands published before the first frame (per engine; default: engine
        off, i.e. zero fuel and the PLA-0 nozzle floor). A mid-flight start passes the plant's trim values.
    event_target: module id of the BIT/monitoring consumer (M14). None = no events (fault bits stay in state).
    compiled: False runs the NumPy reference kernel (same source, identity decorator).
    p0_source: the signal bound to P0 (`ports.P0_AIR_DATA`, the Tejas default: the ADC static pressure; or
        `ports.P0_ENV`, the proxy default and TEST FIXTURE loops without an avionics module).
    """

    version = "1.0.0"
    rate = RG_240
    streams = ()

    def __init__(
        self,
        id: str,
        params: ParamSet,
        *,
        n_engines: int = 1,
        clock=DEFAULT_CLOCK,
        autothrottle: bool = False,
        initial_wf: Sequence[float] | None = None,
        initial_a8: Sequence[float] | None = None,
        initial_vg: Sequence[Sequence[float]] | None = None,
        lanes_per_sensor: tuple[int, ...] = LANES_PER_SENSOR,
        event_target: str | None = None,
        compiled: bool = True,
        identity: Mapping[str, str | int] | None = None,
        p0_source: str | None = None,
    ) -> None:
        self.n_engines = int(n_engines)
        self.clock = clock
        self.autothrottle = bool(autothrottle)
        self.ports_in, self.ports_out, self.bindings = ports(
            self.n_engines, autothrottle=autothrottle, clock=clock, p0_source=p0_source
        )
        self.state_schema = state_schema(self.n_engines)
        self.capacity = capacity(clock)
        self.event_target = event_target
        self.emits_events = event_target is not None
        # block-mode events (core "Events from step_block"): step_block returns the per-step fault events, so
        # the scheduler keeps running M08 in blocks (W2.1b; per-step execution was the W1.3b fallback)
        self.step_block_emits_events = self.emits_events
        super().__init__(id, params, identity=identity)
        self.config = FadecConfig.build(
            params, clock, autothrottle=autothrottle, lanes_per_sensor=lanes_per_sensor
        )
        self._kernel = fadec_block if compiled else kernel_reference()
        e = self.n_engines

        def per_engine(x, default, shape):
            a = np.full(shape, default, dtype=np.float64) if x is None else np.asarray(x, dtype=np.float64)
            if a.shape != shape:
                raise ContractError(f"{id}: initial value shape {a.shape} != {shape}")
            return a

        tb = self.config.tables
        self._wf0 = per_engine(initial_wf, 0.0, (e,))
        a8_idle = float(tb.a8_pla_y[0] * self.config.p[self._pidx("a8_scale")])
        self._a8_0 = per_engine(initial_a8, a8_idle, (e,))
        self._vg0 = per_engine(initial_vg, 0.0, (e, 2))
        if initial_vg is None:
            self._vg0[:, 0] = tb.fvg_y[0]
            self._vg0[:, 1] = tb.cvg_y[0]

    @staticmethod
    def _pidx(name: str) -> int:
        from .layout import P_LAYOUT

        return P_LAYOUT.index[name]

    # ------------------------------------------------------------------ contract
    def init(self, params: ParamSet, keys) -> State:
        e = self.n_engines
        f = np.zeros((e, NF), dtype=np.float64)
        i = np.zeros((e, NI), dtype=np.int64)
        f[:, F_WF_CMD] = self._wf0
        f[:, F_A8_CMD] = self._a8_0
        f[:, F_FVG_CMD] = self._vg0[:, 0]
        f[:, F_CVG_CMD] = self._vg0[:, 1]
        g = np.zeros(NG, dtype=np.int64)
        g[G_N_NEXT] = self.clock.first_index_at_or_after(0)
        return {"f": f, "i": i, "g": g}

    def on_event(self, state: State, event: Event, t: int) -> tuple[State, list[Event]]:
        """``fadec.fault_inject`` (M11, AD-48.4): a control-side fault applied to the state (``faults``)."""
        if event.kind != _faults.EVENT_KIND:
            raise EventNotHandledError(f"{self.id} handles only {_faults.EVENT_KIND!r} (got {event.kind!r})")
        from phalanx.health.protocol import read_payload  # AD-48.1 plain-key payloads

        new = {k: np.array(v, copy=True) for k, v in state.items()}
        pl = read_payload(event.payload)
        _faults.apply_fault(new["f"], pl, float(self.params.value("fault_a8_gain")), self.n_engines)
        return new, []

    def initial_outputs(self, state: State) -> Outputs:
        f = state["f"]
        e = self.n_engines
        return {
            "wf_cmd": np.array(f[:, F_WF_CMD], dtype=np.float64),
            "wf_ab_cmd": np.zeros(e),
            "a8_cmd": np.array(f[:, F_A8_CMD], dtype=np.float64),
            "vg_cmd": np.stack([f[:, F_FVG_CMD], f[:, F_CVG_CMD]], axis=1).astype(np.float64),
            "ignition": np.zeros(e, dtype=np.int64),
            "ab_enable": np.zeros(e, dtype=np.int64),
            "active_limiter": np.zeros(e, dtype=np.int64),
            "validation_state": np.zeros((e, NS), dtype=np.int64),
            # recorded channels before the first frame: nothing validated yet (values 0, words 0 except
            # FADEC_STATUS channel A in control)
            **self._recorded(
                np.zeros((e, NS)), np.zeros(e, np.int64), np.zeros(e, np.int64), np.zeros((e, NS), np.int64)
            ),
        }

    @staticmethod
    def _recorded(sel: np.ndarray, ign: np.ndarray, faults: np.ndarray, vstate: np.ndarray) -> Outputs:
        """RECORDED ports (AD-42) from the validated values [..., NS] and the int outputs [...]."""
        words = recorded_words(ign, faults, vstate)
        out: dict[str, np.ndarray] = {}
        for name, cid in RECORDED.items():
            if name in RECORDED_SENSOR:
                out[name] = np.array(sel[..., RECORDED_SENSOR[name]], dtype=np.float64)
            else:
                out[name] = words[cid]
        return out

    # ------------------------------------------------------------------ kernel I/O
    def frame_schedule(self, state: State, t: np.ndarray):
        """FADEC frames of the steps at times `t` (int64 ns, consecutive truth steps): [t_{k-1}, t_k) each."""
        t = np.asarray(t, dtype=np.int64)
        k0 = latest_truth_step(int(t[0]))
        ks = k0 + np.arange(t.size, dtype=np.int64)
        t_start = truth_step_times_ns(np.maximum(ks - 1, 0))
        t_start[ks == 0] = 0
        return samples_for_steps(self.clock, int(state["g"][G_N_NEXT]), t_start, t)

    def pack_lanes(self, inputs: Inputs, n_steps: int) -> np.ndarray:
        """Lane buffers -> kernel array [L, capacity, n_engines, 13] (SI; unused slots 0)."""
        cap, e = self.capacity, self.n_engines
        lanes = np.zeros((n_steps, cap, e, N_LANE_SLOTS), dtype=np.float64)
        for name, _cid, _unit in LANE_PORTS:  # (n, cap) for one engine, (n, cap, e) otherwise
            a = np.asarray(inputs[name], dtype=np.float64).reshape(n_steps, cap, e)
            lanes[:, :, :, LANE_SLOT[name]] = a
        return lanes

    def _exogenous(self, inputs: Inputs, n: int):
        e = self.n_engines
        pla = np.ascontiguousarray(np.asarray(inputs["pla"], dtype=np.float64).reshape(n, e))
        p0 = np.ascontiguousarray(np.asarray(inputs["p0"], dtype=np.float64).reshape(n))
        if self.autothrottle:
            at_eng = np.ascontiguousarray(np.asarray(inputs["at_engage"], dtype=np.int64).reshape(n))
            at_cmd = np.ascontiguousarray(np.asarray(inputs["at_n1_cmd"], dtype=np.float64).reshape(n, e))
        else:
            at_eng = np.zeros(n, dtype=np.int64)
            at_cmd = np.zeros((n, e), dtype=np.float64)
        return pla, p0, at_eng, at_cmd

    def _run(self, state: State, inputs: Inputs, t: np.ndarray):
        n = t.size
        sched = self.frame_schedule(state, t)
        if n and int(sched.count.max(initial=0)) > self.capacity:
            raise ContractError(f"{self.id}: {int(sched.count.max())} frames in one step exceed capacity")
        pla, p0, at_eng, at_cmd = self._exogenous(inputs, n)
        lanes = self.pack_lanes(inputs, n)
        c = self.config
        f, i, outf, outi = self._kernel(
            state["f"], state["i"], c.p, c.tables, c.cfg, c.dt, pla, p0, at_eng, at_cmd, lanes, sched.count
        )
        g = np.array(state["g"], dtype=np.int64, copy=True)
        g[G_N_NEXT] = sched.next_index
        if sched.times.size:
            g[G_LAST_FRAME_T] = int(sched.times[-1])
        return {"f": f, "i": i, "g": g}, outf, outi, sched

    @classmethod
    def _outputs(cls, outf: np.ndarray, outi: np.ndarray) -> Outputs:
        return {
            "wf_cmd": outf[:, :, O_WF].copy(),
            "wf_ab_cmd": outf[:, :, O_WF_AB].copy(),
            "a8_cmd": outf[:, :, O_A8].copy(),
            "vg_cmd": np.stack([outf[:, :, O_FVG], outf[:, :, O_CVG]], axis=2),
            "ignition": outi[:, :, O_IGN].copy(),
            "ab_enable": outi[:, :, O_AB_EN].copy(),
            "active_limiter": outi[:, :, O_LIMITER].copy(),
            "validation_state": outi[:, :, O_VSTATE : O_VSTATE + NS].copy(),
            **cls._recorded(
                outf[:, :, O_SEL : O_SEL + NS],
                outi[:, :, O_IGN],
                outi[:, :, O_FAULTS],
                outi[:, :, O_VSTATE : O_VSTATE + NS],
            ),
        }

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        t = np.asarray(t, dtype=np.int64)
        new, outf, outi, sched = self._run(state, inputs, t)
        out = self._outputs(outf, outi)
        if not self.emits_events:
            return new, out
        events: list[tuple[int, Event]] = []
        masks = outi[:, :, O_FAULTS]
        prev = np.concatenate([state["i"][None, :, I_FAULTS], masks[:-1]], axis=0)
        for k in np.flatnonzero(np.any(masks != prev, axis=1)):  # only the steps with a transition
            for ev in self.fault_events(prev[k], masks[k], int(t[k]), sched, int(k)):
                events.append((int(t[k]), ev))
        return new, out, events

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        """Per-step execution = `step_block` with L = 1 (events included when `event_target` is set)."""
        one = {k: np.asarray(v)[None, ...] for k, v in inputs.items()}
        res = self.step_block(state, one, np.array([t], np.int64), dt)
        out = {k: v[0] for k, v in res[1].items()}
        if not self.emits_events:
            return res[0], out
        return res[0], out, [ev for _, ev in res[2]]

    def fault_events(self, before: np.ndarray, after: np.ndarray, t: int, sched, k: int = -1) -> list[Event]:
        """Events for fault-bit transitions (A-W1.3b-14) at step `k` of `sched` (default: its last step):
        stamped at `t`, the instant and absolute index of that step's last frame in the payload."""
        if self.event_target is None:
            return []
        k = int(sched.count.size - 1 if k < 0 else k)
        cnt = int(sched.count[k])
        frame = int(sched.first_of_step[k]) + cnt - 1
        t_frame = int(sched.times[frame - int(sched.first)]) if cnt > 0 else int(t)
        out: list[Event] = []
        for e in range(self.n_engines):
            changed = int(before[e]) ^ int(after[e])
            if not changed:
                continue
            for bit in sorted(FAULT_BY_BIT):
                if not (changed >> bit) & 1:
                    continue
                fc = FAULT_BY_BIT[bit]
                out.append(
                    Event(
                        t_ns=int(t),
                        kind=fc.kind,
                        target=self.event_target,
                        payload={
                            "engine": e,
                            "code": fc.code,
                            "set": bool((int(after[e]) >> bit) & 1),
                            "sensor": fc.sensor,
                            "lane": fc.lane,
                            "description": fc.description,
                            "t_frame_ns": t_frame,
                            "frame": frame,
                        },
                        source=self.id,
                    )
                )
        return out


__all__ = ["Fadec"]
