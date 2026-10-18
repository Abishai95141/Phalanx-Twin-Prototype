"""M07 as a core module (``ModuleBase``, AD-36): ports, state schema, keyed stream, step / step_block.

State per instance (``n_engines`` engines, one aircraft):

- ``f`` (E, NF) float64: continuous states + discrete-process timers (``layout.F_NAMES``);
- ``i`` (E, NI) int64: tick, AB state, flame, surge, counters, delay-buffer position (``layout.I_NAMES``);
- ``buf`` (E, D) float64: fuel transport-delay line (metered flow of the last D ticks);
- ``fm`` (E, N_MODES) float64: active engine-fault sizes per mode (``faults.MODES``; 0 = inactive), written by
  the ``eng.fault_inject`` handler, which also recomputes the effective perturbation slice of ``f``
  (``layout.FLT_NAMES``) that the kernel reads (AD-48.4: faults change state only);
- ``y`` (E, NY) / ``yi`` (E, NYI): the last outputs (so ``initial_outputs`` and held ports restore exactly).

Randomness: one declared stream, ``engine.ab_lightoff`` keyed (scenario, tail, serial, sortie); the draw for a
light-off attempt is indexed by the engine's attempt counter in the int state (AD-37: absolute index in state,
CRN across forks). Process disturbances come from M03 through ``env.w_engine``; M07 draws nothing else.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from phalanx.core.events import Event
from phalanx.core.module import ContractError, EventNotHandledError, Inputs, ModuleBase, Outputs
from phalanx.core.rng import StreamDecl, Variate
from phalanx.core.state import Field, State, StateSchema
from phalanx.core.time import RG_240, TRUTH_DT_S

from .design import EngineModel, build_engine_model
from .faults import EVENT_KIND, N_MODES, apply_fault, fault_constants
from .layout import (
    AUX_NAMES,
    I_NAB,
    N_HEALTH,
    N_W_ENGINE,
    NF,
    NI,
    NU,
    NUI,
    NY,
    NYI,
    U_A8,
    U_BLEED,
    U_H0,
    U_MACH,
    U_PS,
    U_PTO,
    U_Q,
    U_TFUEL,
    U_TS,
    U_VG1,
    U_VG2,
    U_WF,
    U_WFAB,
    U_WFM_D,
    UI_ABEN,
    UI_IGN,
    X_NAMES,
    Y_NAMES,
    YI_AB,
    YI_FLAME,
)
from .ports import _FLOAT_OUTPUTS, _TAIL_FLOAT_OUTPUTS, ports
from .sim import state_from_x
from .steady import SteadyResult, TrimCondition, design_inputs, steady_state
from .steady import trim as steady_trim
from .topology import MIXED_AB, kernel_functions, topology_of

STREAM_AB = StreamDecl(
    "engine",
    "ab_lightoff",
    ("scenario", "tail", "serial", "sortie"),
    Variate.NORMAL,
    256,
    "phalanx.engine",
    "per-attempt log-normal scatter of the afterburner light-off delay (A-W1.3a-10)",
)
_Y_INDEX = {n: Y_NAMES.index(n) for n, _ in (*_FLOAT_OUTPUTS, *_TAIL_FLOAT_OUTPUTS)}
_VIB = [Y_NAMES.index(n) for n in ("vib_n1", "vib_n2", "vib_bb")]


class EngineModule(ModuleBase):
    """F404-IN20 truth model for ``n_engines`` engines of one aircraft (240 Hz, sub-stepped kernel)."""

    version = "1.0.0"
    rate = RG_240
    streams = (STREAM_AB,)
    emits_events = False

    def __init__(
        self,
        id: str = "eng",
        model: EngineModel | None = None,
        *,
        n_engines: int = 1,
        serials: Sequence[str | int] | None = None,
        compiled: bool = True,
        init_x: np.ndarray | None = None,
        init_u: np.ndarray | None = None,
        identity=None,
    ) -> None:
        self.model = model if model is not None else build_engine_model()
        self.n_engines = int(n_engines)
        self.serials = tuple(serials) if serials is not None else tuple(f"E{k + 1}" for k in range(n_engines))
        if len(self.serials) != self.n_engines:
            raise ValueError("one serial per engine")
        ins, outs, self.bindings = ports(self.n_engines)
        self.ports_in, self.ports_out = ins, outs
        nd = max(self.model.n_delay, 1)
        self.state_schema = StateSchema(
            "engine.m07",
            3,  # 2: discrete-process timers count ticks; 3: fault perturbation slice in f + per-mode sizes fm
            (
                Field("f", "<f8", (self.n_engines, NF)),
                Field("i", "<i8", (self.n_engines, NI)),
                Field("buf", "<f8", (self.n_engines, nd)),
                Field("y", "<f8", (self.n_engines, NY)),
                Field("yi", "<i8", (self.n_engines, NYI)),
                Field("fm", "<f8", (self.n_engines, N_MODES)),
            ),
        )
        super().__init__(id, self.model.params, identity=identity)
        engine_kernel, self._deriv_point = kernel_functions(self.model)  # topology hook (AD-43)
        self._fault_c: dict[str, float] | None = None  # eng.fault_inject magnitudes (mixed_ab), on first use
        self._compiled = bool(compiled)
        self._kernel = engine_kernel if compiled else engine_kernel.py_func
        self._init_u = design_inputs(self.model) if init_u is None else np.asarray(init_u, float)
        if init_x is None:
            ss = steady_state(self.model, self._init_u)
            if not ss.converged:
                raise RuntimeError("M07 initial steady state did not converge")
            self._init_x, self._init_u = ss.x, ss.u
        else:
            self._init_x = np.asarray(init_x, float)

    # ------------------------------------------------------------------ trim (W2.1 F1)
    def trim(
        self,
        condition: TrimCondition,
        target: tuple[str, float],
        *,
        a8: float | None = None,
        vg=None,
        x0: np.ndarray | None = None,
    ) -> SteadyResult:
        """A consistent ``(x, u)`` of this engine model at ``condition``: the equilibrium of the dynamics with
        the fuel flow freed to meet ``target`` (``steady.trim``; e.g. ("n2", rad/s), ("n2c", rpm), ("n1",
        rad/s)), nozzle command ``a8`` (default the design MIL throat) and VG on the reference schedule
        unless ``vg`` is given. ``result.u`` holds the commands (``wf_cmd``, ``a8_cmd``, VG) a controller
        must publish for the engine to stay there; ``result.converged`` must be checked. Use ``from_trim`` to
        start a run there (sortie telemetry starts from post-start idle, AD-46)."""
        return steady_trim(self.model, condition, target, a8=a8, vg=vg, x0=x0)

    def from_trim(self, trim: SteadyResult, *, id: str | None = None) -> EngineModule:
        """A module of the same model, engines and serials whose initial state is ``trim`` (every engine)."""
        if not trim.converged:
            raise RuntimeError("M07: refusing to start from a trim that did not converge")
        return EngineModule(
            self.id if id is None else id,
            self.model,
            n_engines=self.n_engines,
            serials=self.serials,
            compiled=self._compiled,
            init_x=trim.x,
            init_u=trim.u,
            identity=self.identity,
        )

    # ------------------------------------------------------------------ contract
    def init(self, params, keys) -> State:
        st = state_from_x(self.model, self._init_x, n_engines=self.n_engines, w_fm=self._init_u[U_WFM_D])
        dx, aux = self._deriv_point(
            self._init_x, 0, 1, 0, 0.0, self._init_u, self.model.p, self.model.tables, -1.0
        )
        _ = dx
        y = np.zeros((self.n_engines, NY))
        y[:] = _outputs_from(self._init_x, aux, self._init_u)
        yi = np.zeros((self.n_engines, NYI), dtype=np.int64)
        yi[:, YI_FLAME] = 1
        fm = np.zeros((self.n_engines, N_MODES))
        return {"f": st.f, "i": st.i, "buf": st.buf, "y": y, "yi": yi, "fm": fm}

    def on_event(self, state: State, event: Event, t: int) -> tuple[State, list[Event]]:
        """``eng.fault_inject`` (M11, AD-48.4): a physical engine fault applied to the state (``faults``)."""
        if event.kind != EVENT_KIND:
            raise EventNotHandledError(f"{self.id} handles only {EVENT_KIND!r} (got {event.kind!r})")
        if topology_of(self.model) != MIXED_AB:
            raise ContractError(
                f"{self.id}: {EVENT_KIND} is realised by the Tejas mixed_ab kernel only (topology "
                f"{topology_of(self.model)!r} has no fault perturbation slice)"
            )
        if self._fault_c is None:
            self._fault_c = fault_constants(self.model.params, self.model.design)
        from phalanx.health.protocol import read_payload  # AD-48.1 plain-key payloads

        new = {k: np.array(v, copy=True) for k, v in state.items()}
        apply_fault(new, read_payload(event.payload), self._fault_c, self.n_engines)
        return new, []

    def initial_outputs(self, state: State) -> Outputs:
        return _ports_from(state["y"][None], state["yi"][None], 0)

    def _pack(self, inputs: Inputs, n: int) -> tuple[np.ndarray, np.ndarray]:
        e = self.n_engines
        u = np.zeros((n, e, NU))
        u[:, :, U_WF] = inputs["wf_cmd"]
        u[:, :, U_WFAB] = inputs["wf_ab_cmd"]
        u[:, :, U_A8] = inputs["a8_cmd"]
        vg = np.asarray(inputs["vg_cmd"], float)
        u[:, :, U_VG1] = vg[..., 0]
        u[:, :, U_VG2] = vg[..., 1]
        for col, name in ((U_TS, "t_s"), (U_PS, "p_s"), (U_Q, "q_spec"), (U_MACH, "mach")):
            u[:, :, col] = np.asarray(inputs[name], float).reshape(n, 1)
        u[:, :, U_WFM_D : U_WFM_D + N_W_ENGINE] = inputs["w_engine"]
        u[:, :, U_BLEED] = inputs["bleed_extract"]
        u[:, :, U_PTO] = inputs["pto_power"]
        u[:, :, U_TFUEL] = inputs["fuel_inlet_t"]
        u[:, :, U_H0 : U_H0 + N_HEALTH] = inputs["health"]
        ui = np.zeros((n, e, NUI), dtype=np.int64)
        ui[:, :, UI_IGN] = inputs["ignition"]
        ui[:, :, UI_ABEN] = inputs["ab_enable"]
        return u, ui

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        n = int(np.asarray(t).size)
        if abs(dt - TRUTH_DT_S) > 1e-15:
            raise ValueError("M07 runs in the 240 Hz rate group")
        u, ui = self._pack(inputs, n)
        # light-off draws are consumed only on an AB attempt, which needs ab_enable: blocks without it skip
        # the draw (bitwise identical: the zeros are never read; the draw index lives in the int state)
        z = np.zeros((self.n_engines, n + 1))
        aben = ui[:, :, UI_ABEN]
        for e, ser in enumerate(self.serials):
            if aben[:, e].any():
                z[e] = self.stream("ab_lightoff", serial=ser).draws(int(state["i"][e, I_NAB]), n + 1)
        m = self.model
        f, i, buf, y, yi, _ = self._kernel(
            state["f"], state["i"], state["buf"], m.p, m.tables, u, ui, z, m.dt, m.n_sub, m.n_delay, False
        )
        new = {"f": f, "i": i, "buf": buf, "y": y[-1].copy(), "yi": yi[-1].copy(), "fm": state["fm"]}
        return new, _ports_from(y, yi, None)

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        """Per-step execution is step_block with L = 1 (bitwise identical by construction)."""
        one = {k: np.asarray(v)[None] for k, v in inputs.items()}
        new, out = self.step_block(state, one, np.array([t], np.int64), dt)
        return new, {k: v[0] for k, v in out.items()}


def _outputs_from(x: np.ndarray, aux: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Output row (layout.Y_NAMES) from a state and its diagnostics (initial outputs)."""
    A = {n: j for j, n in enumerate(AUX_NAMES)}
    X = {n: j for j, n in enumerate(X_NAMES)}
    y = np.zeros(NY)
    src = {
        "n1": x[X["n1"]], "n2": x[X["n2"]], "t2": aux[A["t2"]], "t25": aux[A["t25"]], "t3": aux[A["t3"]],
        "t5": aux[A["t5"]], "p2": aux[A["p2"]], "ps3": aux[A["ps3"]], "p5": aux[A["p5"]],
        "wf": x[X["wfm"]] * (1.0 + u[U_WFM_D]), "wf_ab": max(x[X["wfab"]], 0.0), "a8": x[X["a8"]],
        "vg_igv": x[X["vg1"]], "vg_vsv": x[X["vg2"]], "w2": aux[A["w2"]], "thrust": aux[A["fn"]],
        "oil_t": x[X["toil"]], "oil_p": aux[A["oil_p"]], "vib_n1": aux[A["vib_n1"]],
        "vib_n2": aux[A["vib_n2"]],
        "vib_bb": aux[A["vib_bb"]], "stall_margin": min(aux[A["sm_fan"]], aux[A["sm_hpc"]]),
        "bleed_p3": x[X["p3"]], "bleed_t3": aux[A["t3"]],
    }  # fmt: skip
    for n, v in src.items():
        y[Y_NAMES.index(n)] = v
    return y


def _ports_from(y: np.ndarray, yi: np.ndarray, k: int | None) -> Outputs:
    """Port dict from kernel outputs (L, E, ·); ``k`` selects one tick (initial outputs) else the block."""
    if k is not None:
        y, yi = y[k : k + 1], yi[k : k + 1]
    # one transposed copy (NY, L, E): every float port is a contiguous view of it (y is fresh per call)
    yt = np.ascontiguousarray(y.transpose(2, 0, 1))
    yit = np.ascontiguousarray(yi.transpose(2, 0, 1))
    out: Outputs = {n: yt[j] for n, j in _Y_INDEX.items()}
    out["vib_src"] = y[:, :, _VIB]  # fancy index: a fresh contiguous (L, E, 3) array
    out["ab_state"] = yit[YI_AB]
    out["flame_state"] = yit[YI_FLAME]
    if k is not None:
        out = {n: v[0] for n, v in out.items()}
    return out
