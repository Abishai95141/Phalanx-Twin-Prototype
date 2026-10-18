"""Worked example of the AD-22 kernel layout inside the module contract (a reference for W1 authors).

**Reference example for the kernel layout, not a physics deliverable** (parameters are tagged
``[ASSUMPTION]``, source "W0.2 kernel-layout example"). It shows, in one small module:

1. **State** as one float64 vector ``f`` and one int64 vector ``i`` with module-level name -> index
   constants (``X, V, U_CMD``; ``TICK, N_GOV``), declared through :class:`StateLayout` so the usual
   ``StateSchema`` / ``get_state`` / ``set_state`` / snapshot path is unchanged.
2. **Parameters** as one flat, read-only float64 vector (``P_*`` constants) built from the ParamSet by
   :class:`ParamLayout`; calibration perturbs entries by index. Integer configuration (sub-steps, the
   internal sub-rate divisor) is passed as plain int arguments, never baked in as calibrated globals.
3. **One ``@njit`` kernel** ``_kernel(f, i, p, u_ext[L], noise[L], dt, n_sub, gov_div) -> (f, i,
   out[L, 3])``: ``fastmath`` off, ``cache=True``, ``error_model="numpy"``, ``nogil=True``; block length L is
   a runtime value; locals are scalars; inputs are never mutated (fresh copies are returned).
4. **step == step_block with L = 1** (AD-22), so per-step and block execution are bitwise identical by
   construction.
5. **NumPy reference = the same source uncompiled** (``_kernel.py_func``; also what ``NUMBA_DISABLE_JIT=1``
   runs). ``ExampleOscillator(..., compiled=False)`` runs the reference through the scheduler; the tests
   show it is bitwise equal to the compiled kernel.
6. **Keyed noise fed as an input array**: draws for ticks ``[tick, tick + L)`` of a declared stream
   (AD-37); the absolute tick index lives in the int state.
7. **Phase of an internal sub-rate**: the force command is updated every ``gov_div`` = 3 ticks (80 Hz)
   inside this 240 Hz module, with the phase taken from the int-state counter ``TICK``, so a snapshot at
   any step continues exactly (W0.6 D5). The *module's own* rate group (``rate``) is owned by the
   scheduler, which derives it from the absolute step ``k`` saved in every snapshot.
8. **Complex-step safe** (AD-34): no comparisons, ``abs``, ``min``/``max`` or int casts on values that
   carry derivatives; output arrays take the state dtype, so the same kernel runs on complex128 for
   Jacobians.
"""

from __future__ import annotations

import numpy as np
from numba import njit

from .layout import ParamLayout, StateLayout
from .module import Inputs, ModuleBase, Outputs, Param, ParamSet, Port
from .rng import StreamDecl, Variate
from .state import State, StateSchema
from .time import RG_240

# --- state layout: float64 vector f and int64 vector i, with name -> index constants -------------------
X, V, U_CMD = 0, 1, 2
TICK, N_GOV = 0, 1
LAYOUT = StateLayout("core.example.oscillator", 1, floats=("x", "v", "u_cmd"), ints=("tick", "n_gov"))
LAYOUT.f.check(x=X, v=V, u_cmd=U_CMD)
LAYOUT.i.check(tick=TICK, n_gov=N_GOV)

# --- flat parameter vector --------------------------------------------------------------------------------
P_M, P_C, P_K, P_SIG, P_KP, P_KD = 0, 1, 2, 3, 4, 5
PARAMS = ParamLayout(("mass", "damping", "stiffness", "sigma_force", "kp", "kd"))
PARAMS.check(mass=P_M, damping=P_C, stiffness=P_K, sigma_force=P_SIG, kp=P_KP, kd=P_KD)

N_SUB = 4  # integration sub-steps per 240 Hz tick
GOV_DIV = 3  # internal governor sub-rate: every 3rd tick = 80 Hz
EXAMPLE_SOURCE = "W0.2 kernel-layout example (not a physics deliverable)"


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _kernel(f, i, p, u_ext, noise, dt, n_sub, gov_div):
    """Advance L = len(u_ext) ticks. Pure: returns new f, i and out[L, 3] = (x, v, u_cmd) per tick."""
    f = f.copy()
    i = i.copy()
    n = u_ext.shape[0]
    out = np.empty((n, 3), dtype=f.dtype)
    x = f[X]
    v = f[V]
    u = f[U_CMD]
    tick = i[TICK]
    n_gov = i[N_GOV]
    m = p[P_M]
    c = p[P_C]
    k = p[P_K]
    sig = p[P_SIG]
    kp = p[P_KP]
    kd = p[P_KD]
    h = dt / n_sub
    for j in range(n):
        if tick % gov_div == 0:  # internal sub-rate phase from the int state
            u = -(kp * x + kd * v)
            n_gov += 1
        force = sig * noise[j] + u_ext[j] + u
        for _ in range(n_sub):
            a = (force - c * v - k * x) / m
            v = v + h * a
            x = x + h * v
        tick += 1
        out[j, 0] = x
        out[j, 1] = v
        out[j, 2] = u
    f[X] = x
    f[V] = v
    f[U_CMD] = u
    i[TICK] = tick
    i[N_GOV] = n_gov
    return f, i, out


def kernel_reference(f, i, p, u_ext, noise, dt, n_sub, gov_div):
    """The NumPy reference: the same source, uncompiled (identical to ``NUMBA_DISABLE_JIT=1``)."""
    return _kernel.py_func(f, i, p, u_ext, noise, dt, n_sub, gov_div)


def example_params(**overrides) -> ParamSet:
    vals = {
        "mass": (2.0, "kg"),
        "damping": (0.6, "kg/s"),
        "stiffness": (30.0, "kg/s**2"),
        "sigma_force": (5.0, "N"),
        "kp": (12.0, "kg/s**2"),
        "kd": (1.5, "kg/s"),
        "x0": (0.1, "m"),
        "v0": (0.0, "m/s"),
    }
    for k, v in overrides.items():
        vals[k] = (v, vals[k][1])
    return ParamSet(
        "core.example", {k: Param(v, u, "ASSUMPTION", EXAMPLE_SOURCE) for k, (v, u) in vals.items()}
    )


class ExampleOscillator(ModuleBase):
    """Spring-mass-damper with an internal 80 Hz PD governor, in the AD-22 layout (see module docstring)."""

    version = "1.0.0"
    rate = RG_240
    ports_in = (Port("u_ext", "N"),)
    ports_out = (Port("x", "m"), Port("v", "m/s"), Port("u_cmd", "N"))
    state_schema = LAYOUT.schema
    streams = (
        StreamDecl(
            "core_example",
            "disturbance",
            ("scenario", "tail", "sortie"),
            Variate.NORMAL,
            4096,
            "core.example_kernel",
            "per-tick process disturbance (layout example)",
        ),
    )

    def __init__(self, id: str, params: ParamSet, *, compiled: bool = True, **kw) -> None:
        super().__init__(id, params, **kw)
        self._p = PARAMS.vector(params)
        self._kernel = _kernel if compiled else kernel_reference

    def init(self, params: ParamSet, keys) -> State:
        x0, v0 = float(params.value("x0")), float(params.value("v0"))
        return LAYOUT.pack(x=x0, v=v0, u_cmd=0.0, tick=0, n_gov=0)

    def initial_outputs(self, state: State) -> Outputs:
        f = state["f"]
        return {"x": np.array(f[X]), "v": np.array(f[V]), "u_cmd": np.array(f[U_CMD])}

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        n = t.size
        tick0 = int(state["i"][TICK])
        noise = self.stream("disturbance").draws(tick0, n)  # keyed block, indexed by the int-state tick
        u_ext = np.ascontiguousarray(inputs["u_ext"], dtype=np.float64)
        f, i, out = self._kernel(state["f"], state["i"], self._p, u_ext, noise, dt, N_SUB, GOV_DIV)
        return {"f": f, "i": i}, {"x": out[:, 0].copy(), "v": out[:, 1].copy(), "u_cmd": out[:, 2].copy()}

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        """Per-step execution is step_block with L = 1 (bitwise identical by construction)."""
        one = {"u_ext": np.asarray(inputs["u_ext"], dtype=np.float64).reshape(1)}
        new, out = self.step_block(state, one, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}


class ExampleStepCommand(ModuleBase):
    """A deterministic external force command (a step at ``t_on``) to drive the example's input port."""

    version = "1.0.0"
    rate = RG_240
    ports_out = (Port("u", "N"),)
    state_schema = StateSchema("core.example.command", 1, ())

    def __init__(self, id: str, *, amplitude: float = 3.0, t_on_ns: int = 2_000_000_000) -> None:
        ps = ParamSet(
            "core.example.command",
            {
                "amplitude": Param(amplitude, "N", "ASSUMPTION", EXAMPLE_SOURCE),
                "t_on": Param(t_on_ns, "ns", "ASSUMPTION", EXAMPLE_SOURCE),
            },
        )
        super().__init__(id, ps)
        self._amp, self._t_on = float(amplitude), int(t_on_ns)

    def init(self, params: ParamSet, keys) -> State:
        return {}

    def initial_outputs(self, state: State) -> Outputs:
        return {"u": np.array(0.0)}

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        return {}, {"u": np.where(t >= self._t_on, self._amp, 0.0)}

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        return {}, {"u": np.array(self._amp if t >= self._t_on else 0.0)}
