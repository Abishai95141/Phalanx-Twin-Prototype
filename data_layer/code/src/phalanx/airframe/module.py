"""M06 Airframe module: the AD-22 kernel inside the §5.5 contract (``ModuleBase``).

``step`` is ``step_block`` with ``L = 1``; both call the same compiled kernel, so per-step and block execution
are bitwise identical by construction. ``compiled=False`` runs the NumPy reference (``py_func``).
"""

from __future__ import annotations

import numpy as np

from phalanx.core.events import Event
from phalanx.core.layout import StateLayout
from phalanx.core.module import ContractError, Inputs, ModuleBase, Outputs, ParamSet
from phalanx.core.state import State
from phalanx.core.time import RG_240

from .build import airframe_param_set, build_config
from .ic import AirframeIC, ic_params, initial_float_state
from .kernel import (
    AF_FAULT_MODES,
    F_FLT0,
    F_HGND,
    FLOAT_NAMES,
    I_NSUB,
    I_TICK,
    INT_NAMES,
    N_SURF,
    O_ALPHA,
    O_ALT,
    O_BETA,
    O_FX,
    O_HAG,
    O_LAT,
    O_MACH,
    O_NZ,
    O_PBL,
    O_QBAR,
    O_QN0,
    O_TAS,
    O_VN,
    O_WHL,
    O_WOW0,
    O_WX,
    U_BRAKE,
    U_CHUTE,
    U_HYDP,
    airframe_kernel,
    airframe_outputs,
    input_width,
    kernel_reference,
)
from .ports import ports

# v2 (AD-47): brakes and chute are inputs, no longer state; v3 (AD-48.4): af.fault_inject severities
LAYOUT = StateLayout("m06.airframe", 3, floats=FLOAT_NAMES, ints=INT_NAMES)
LAYOUT.f.check(**{name: k for k, name in enumerate(FLOAT_NAMES)})
LAYOUT.i.check(tick=I_TICK, n_sub_last=I_NSUB)
assert FLOAT_NAMES.index("h_ground") == F_HGND


def pack_inputs(inputs: Inputs, n: int, n_eng: int) -> np.ndarray:
    """Kernel input rows ``u[n, nu]`` from port arrays with a leading tick axis of length ``n``."""
    u = np.empty((n, input_width(n_eng)), dtype=np.float64)
    o = N_SURF + n_eng
    u[:, 0:N_SURF] = np.reshape(inputs["surf_pos"], (n, N_SURF))
    u[:, N_SURF:o] = np.reshape(inputs["thrust"], (n, n_eng))
    u[:, o] = np.reshape(inputs["mass"], (n,))
    u[:, o + 1 : o + 4] = np.reshape(inputs["cg"], (n, 3))
    u[:, o + 4 : o + 13] = np.reshape(inputs["inertia"], (n, 9))
    u[:, o + 13] = np.reshape(inputs["rho"], (n,))
    u[:, o + 14] = np.reshape(inputs["a_sound"], (n,))
    u[:, o + 15] = np.reshape(inputs["t_s"], (n,))
    u[:, o + 16 : o + 19] = np.reshape(inputs["wind_ned"], (n, 3))
    u[:, o + 19 : o + 22] = np.reshape(inputs["turb_vel_body"], (n, 3))
    u[:, o + 22 : o + 25] = np.reshape(inputs["turb_rate_body"], (n, 3))
    u[:, o + 25] = np.reshape(inputs["gear_cmd"], (n,))
    u[:, o + U_BRAKE : o + U_BRAKE + 2] = np.reshape(inputs["brake_cmd"], (n, 2))  # AD-47
    u[:, o + U_CHUTE] = np.reshape(inputs["chute_state"], (n,))
    u[:, o + U_HYDP : o + U_HYDP + 2] = np.reshape(inputs["hyd_p"], (n, 2))
    return u


def unpack_outputs(out: np.ndarray) -> Outputs:
    """Port arrays (leading tick axis) from kernel output rows."""
    return {
        "pos_geo": out[:, O_LAT : O_LAT + 3].copy(),
        "alt": out[:, O_ALT].copy(),
        "vel_ned": out[:, O_VN : O_VN + 3].copy(),
        "quat": out[:, O_QN0 : O_QN0 + 4].copy(),
        "omega_body": out[:, O_WX : O_WX + 3].copy(),
        "f_spec_body": out[:, O_FX : O_FX + 3].copy(),
        "alpha": out[:, O_ALPHA].copy(),
        "beta": out[:, O_BETA].copy(),
        "tas": out[:, O_TAS].copy(),
        "mach": out[:, O_MACH].copy(),
        "qbar": out[:, O_QBAR].copy(),
        "nz": out[:, O_NZ].copy(),
        "wow": out[:, O_WOW0 : O_WOW0 + 3].astype(np.int64),
        "wheel_speed": out[:, O_WHL : O_WHL + 2].copy(),
        "brake_energy_rate": out[:, O_PBL : O_PBL + 2].copy(),
        "hag": out[:, O_HAG].copy(),
    }


class Airframe(ModuleBase):
    """Quaternion 6-DOF rigid body on a rotating WGS-84 Earth with the Tejas-anchored aero and ground model.

    Brakes and chute are inputs (AD-47): ``pilot.brake_cmd`` (toe brakes L/R, 0..1) scales the brake
    torque the brake system's supply allows (``util.hyd_p`` of ``brake_hyd_system`` through
    ``brake_torque_gain`` up to ``brake_p_max``, capped at ``brake_torque_max``; A-W1.4-32), and
    ``util.chute_state`` = 1 (streamed) applies the chute drag, so M09's deploy limits and failures govern.
    The W1 test hooks ``af.brake`` / ``af.chute`` are retired. Events (``on_event``): ``af.ground_elevation``
    {h: runway height above the ellipsoid, m}; ``af.fault_inject`` (M11, AD-48.4, hidden) {tail, mode, param,
    instance, engine, clear, leg}: a ground-model state perturbation of the gear leg ``leg`` (0 nose, 1 left
    main, 2 right main; -1 all legs) with severity ``param`` (clipped to [0, 1]; ``clear`` restores 0). Modes
    (``kernel.AF_FAULT_MODES``): ``tyre_burst`` (the leg drops by r_roll - rim_radius, rolling coefficient
    + mu_rim, lateral and braking grip x grip_rim), ``strut_extension_failure`` (the ice-locked strut stays
    frozen_stroke compressed and k_frozen x stiffer), ``gear_collapse_on_touchdown`` (the leg folds when
    loaded: belly-contact properties at its attach point) and ``runway_excursion`` (unprepared ground:
    rolling + mu_soft, grip x grip_soft). An event for another tail is ignored.
    """

    version = "1.0.0"
    rate = RG_240
    state_schema = LAYOUT.schema

    def __init__(
        self,
        id: str,
        params: ParamSet,
        *,
        n_engines: int = 1,
        compiled: bool = True,
        identity=None,
    ) -> None:
        ins, outs, _ = ports(n_engines)
        self.ports_in = ins
        self.ports_out = outs
        super().__init__(id, params, identity=identity)
        self.cfg = build_config(params, n_engines)
        self._n_eng = n_engines
        self._mode = int(params.value("kernel_mode")) if "kernel_mode" in params else 0
        self._kernel = airframe_kernel if compiled else kernel_reference
        missing = [k for k in ("ic_lat", "ic_lon", "ic_h", "ic_u_ref") if k not in params]
        if missing:
            raise ContractError(f"{id}: ParamSet lacks initial-condition entries {missing} (use with_ic)")
        u_ref = np.asarray(params.value("ic_u_ref"), dtype=np.float64)
        if u_ref.shape != (input_width(n_engines),):
            raise ContractError(
                f"{id}: ic_u_ref has shape {u_ref.shape}, expected ({input_width(n_engines)},)"
            )
        self._u_ref = u_ref

    @classmethod
    def from_registry(
        cls, id: str, ic: AirframeIC, *, n_engines: int = 1, platform: str = "tejas", **kw
    ) -> Airframe:
        return cls(id, airframe_param_set(platform, extra=ic_params(ic)), n_engines=n_engines, **kw)

    # ------------------------------------------------------------------ contract
    def init(self, params: ParamSet, keys) -> State:
        c = self.cfg
        f = initial_float_state(
            float(params.value("ic_lat")),
            float(params.value("ic_lon")),
            float(params.value("ic_h")),
            np.asarray(params.value("ic_vel_ned")),
            np.asarray(params.value("ic_quat_nb")),
            np.asarray(params.value("ic_omega_nb")),
            float(params.value("ic_gear")),
            float(params.value("ic_h_ground")),
            c.dp,
        )
        return {"f": f, "i": np.zeros(len(INT_NAMES), dtype=np.int64)}

    def initial_outputs(self, state: State) -> Outputs:
        c = self.cfg
        row = airframe_outputs(
            state["f"], c.dp, c.ap, c.tab, c.gtab, c.ttab, self._u_ref, self._n_eng, self._mode
        )
        return {k: v[0] for k, v in unpack_outputs(row[None, :]).items()}

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        n = int(np.asarray(t).size)
        u = pack_inputs(inputs, n, self._n_eng)
        c = self.cfg
        f, i, out = self._kernel(
            state["f"], state["i"], c.dp, c.ap, c.tab, c.gtab, c.ttab, u, dt, self._n_eng, self._mode
        )
        return {"f": f, "i": i}, unpack_outputs(out)

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        one = {k: np.asarray(v)[None, ...] for k, v in inputs.items()}
        new, out = self.step_block(state, one, np.array([t], np.int64), dt)
        return new, {k: v[0] for k, v in out.items()}

    def on_event(self, state: State, event: Event, t: int):
        f = np.array(state["f"], copy=True)
        p = event.payload
        if event.kind == "af.ground_elevation":
            f[F_HGND] = float(p["h"])
        elif event.kind == "af.fault_inject":
            ident = dict(self._keys.identity.as_dict()) if self._keys is not None else {}
            ident.update(self.identity)
            tail = str(ident.get("tail", ""))
            if tail and str(np.asarray(p["tail"])) != tail:
                return state, []  # another tail's fault
            mode = str(np.asarray(p["mode"]))
            if mode not in AF_FAULT_MODES:
                raise ContractError(f"{self.id}: af.fault_inject mode {mode!r} not in {AF_FAULT_MODES}")
            leg = int(np.asarray(p["leg"]))
            if not -1 <= leg <= 2:
                raise ContractError(f"{self.id}: af.fault_inject leg {leg} not in -1 (all), 0, 1, 2")
            sev = 0.0 if bool(np.asarray(p["clear"])) else min(1.0, max(0.0, float(np.asarray(p["param"]))))
            m = AF_FAULT_MODES.index(mode)
            for g in range(3) if leg < 0 else (leg,):
                f[F_FLT0 + 3 * m + g] = sev
        else:
            return super().on_event(state, event, t)
        return {"f": f, "i": np.array(state["i"], copy=True)}, []
