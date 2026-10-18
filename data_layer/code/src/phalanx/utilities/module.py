"""M09 ``Utilities`` module: the AD-22 kernel inside the §5.5 contract (ports, state, events, streams).

- ``rate`` = 240 Hz; ``step`` is ``step_block`` with L = 1, so per-step and block execution are bitwise
  identical by construction (AD-36). ``compiled=False`` runs the uncompiled reference (``kernel.py``).
- **Randomness** (AD-37): two declared streams keyed by (scenario, tail, sortie):
  ``util/jfs_ignition`` (one uniform per JFS start attempt, index = attempt number in state) and
  ``util/fire_extinguish`` (one uniform per extinguisher discharge, index = fire event number in state).
  Process disturbances come from M03 (``env.w_hyd``, ``env.w_bleed_pto``); M09 draws nothing else.
- **Events** (``on_event``; discrete commands, faults as state perturbations, configuration orders):

  | kind | payload | effect |
  |---|---|---|
  | ``util.jfs_start`` | - | start attempt (from OFF or COAST): crank, keyed ignition draw at light-off |
  | ``util.jfs_abort`` | - | abort the running start (outcome ABORT) |
  | ``util.chute_deploy`` | ``emergency`` 0/1 | stream the chute; checks TAS against 285/340 km/h |
  | ``util.chute_jettison`` | - | jettison a streamed chute |
  | ``util.fire_extinguish`` | - | discharge the bottle (once); keyed success draw |
  | ``util.fault`` | ``mode`` str | ``gen_fail``/``gen_restore``, ``bk_fail``/``bk_restore``,
  ``fire_onset``/``fire_out``, ``fire_loop_open``/``fire_loop_short``/``fire_loop_ok`` |
  | ``util.config`` | ``item`` str, ``value`` int | ``f1a_mod`` (0/1), ``jfs_variant`` (1/2) - configuration
  orders (M21) |
  | ``util.refuel`` | ``tank`` int, ``target_kg``, ``t_fuel`` | fill one tank up to the target (AD-49): stops
  at the tank volume at the mixed fuel temperature, never defuels, mixes the fuel temperature (audited) |
  | ``util.store_release`` | ``station`` int | release the store at a station |

- **Health** (``health.utility``) is a held input; hidden states never leave through ``util.*`` except the
  catalogued wear ports (brake/tyre wear are truth ports for M10/M18; never route them to CIR).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from phalanx.core.events import Event
from phalanx.core.module import ContractError, Inputs, ModuleBase, Outputs, ParamSet
from phalanx.core.rng import StreamDecl, Variate
from phalanx.core.state import State
from phalanx.core.time import RG_240

from . import layout as L
from .electrical import SRC_BACKUP, SRC_BATT, SRC_TRU, battery_ocv
from .fuel import fuel_density, mass_properties, pickup_wetness
from .hydraulics import hyd_volume_invariant
from .jfs import JFS_ACCEL, JFS_COAST, JFS_CRANK, JFS_ENGAGED, JFS_OFF, OUT_ABORT, OUT_OK
from .kernel import JFS_STATE_COAST_FAIL, kernel_reference, utilities_kernel
from .params import config_vector, load_m09_params, param_vector
from .ports import ports

SOURCE = "phalanx.utilities"


# Modification ids (M18 EMBODY_MODIFICATION `mod_id`) with an effect on M09 state (AD-44).
MOD_EFFECTS: dict[str, tuple[int, int]] = {
    "F1A_PICKUP_MOD": (L.I_F1A_MOD, 1),  # F1A pick-up modification (fuel stranding fix)
    "GTSU110_M2": (L.I_JFS_VARIANT, 2),  # GTSU-110 M2 starter variant
}


@dataclass(frozen=True)
class UtilitiesConfig:
    """Sortie initial conditions and installation configuration (scenario inputs from M02/M18, not
    parameters).

    ``fuel`` is kg per tank in ``layout.TANKS`` order (None = full internal tanks at the soak temperature,
    drop tanks full if fitted). Temperatures default to the soak temperature (cold-soak start, report §3
    edge).
    """

    soak_temp: float = 288.15
    p_amb: float = 101325.0
    fuel: tuple[float, ...] | None = None
    drop_tanks: tuple[bool, bool, bool] = (False, False, False)  # inboard L, inboard R, centreline
    stores: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0)  # non-fuel store mass per station, kg
    batt_soc: float = 1.0
    jfs_variant: int = 2
    f1a_mod: int = 1
    engine_running: bool = True
    brake_temp: tuple[float, float] | None = None
    jfs_oil_l: float | None = None

    def __post_init__(self) -> None:
        if self.jfs_variant not in (1, 2):
            raise ContractError("jfs_variant must be 1 (GTSU-110 M1) or 2 (M2)")
        if self.f1a_mod not in (0, 1):
            raise ContractError("f1a_mod must be 0 or 1")
        if len(self.stores) != L.N_STORE:
            raise ContractError(f"stores needs {L.N_STORE} station masses")
        if not 0.0 <= self.batt_soc <= 1.0:
            raise ContractError("batt_soc must be in [0, 1]")


def _tank_caps(p: np.ndarray) -> np.ndarray:
    return np.array([p[L.P_TANK + L.TC_CAP * L.N_TANKS + k] for k in range(L.N_TANKS)])


class Utilities(ModuleBase):
    """M09 utility systems (AMAGB/PTO, hydraulics, fuel, electrical, ECS, JFS, brakes/tyres/chute, fire)."""

    version = "1.0.0"
    rate = RG_240
    state_schema = L.STATE.schema
    emits_events = False
    streams = (
        StreamDecl(
            "util",
            "jfs_ignition",
            ("scenario", "tail", "sortie"),
            Variate.UNIFORM,
            64,
            SOURCE,
            "JFS light-off draw, one per start attempt (index = attempt number)",
        ),
        StreamDecl(
            "util",
            "fire_extinguish",
            ("scenario", "tail", "sortie"),
            Variate.UNIFORM,
            64,
            SOURCE,
            "extinguisher success draw, one per discharge (index = fire event number)",
        ),
    )

    def __init__(
        self,
        id: str,
        params: ParamSet | None = None,
        *,
        n_engines: int = 1,
        config: UtilitiesConfig | None = None,
        compiled: bool = True,
        identity: Mapping[str, str | int] | None = None,
    ) -> None:
        params = params if params is not None else load_m09_params()
        ins, outs, bindings = ports(n_engines)
        self.ports_in = ins
        self.ports_out = outs
        self.bindings = bindings
        super().__init__(id, params, identity=identity)
        self.n_engines = n_engines
        self._p = param_vector(params)
        self._cfg = config_vector(params, n_engines)
        self._config = config if config is not None else UtilitiesConfig()
        self._kernel = utilities_kernel if compiled else kernel_reference
        self._jfs_oil0_l = float(params.value("jfs_oil_qty0")) * 1000.0  # SI m^3 -> L
        self._check_config()

    # ------------------------------------------------------------------ configuration
    def _check_config(self) -> None:
        c = self._config
        if c.fuel is not None:
            if len(c.fuel) != L.N_TANKS:
                raise ContractError(f"fuel needs {L.N_TANKS} tank masses")
            caps = _tank_caps(self._p) * float(fuel_density(self._p, c.soak_temp))
            for k, (m, cap) in enumerate(zip(c.fuel, caps, strict=True)):
                if m < 0 or m > cap * (1 + 1e-9):
                    raise ContractError(f"fuel in {L.TANKS[k]} = {m} kg outside [0, {cap:.1f}]")
            for k, fitted in zip((L.T_DTL, L.T_DTR, L.T_DTC), c.drop_tanks, strict=True):
                if not fitted and c.fuel[k] > 0:
                    raise ContractError(f"fuel in {L.TANKS[k]} but the drop tank is not fitted")

    def _initial_fuel(self) -> np.ndarray:
        c = self._config
        if c.fuel is not None:
            return np.array(c.fuel, dtype=np.float64)
        caps = _tank_caps(self._p) * float(fuel_density(self._p, c.soak_temp))
        m = caps.copy()
        for k, fitted in zip((L.T_DTL, L.T_DTR, L.T_DTC), c.drop_tanks, strict=True):
            if not fitted:
                m[k] = 0.0
        return m

    # ------------------------------------------------------------------ contract
    def init(self, params: ParamSet, keys) -> State:
        c = self._config
        p = self._p
        ts = float(c.soak_temp)
        run = bool(c.engine_running)
        p_nom = float(p[L.P_HYD_P_NOM])
        vals: dict[str, float | int] = {n: 0.0 for n in L.F_NAMES}
        vals.update({n: 0 for n in L.I_NAMES})
        for h in range(L.N_HYD):
            vals[f"hyd_p_{h}"] = p_nom if run else 0.0
            vals[f"hyd_x_{h}"] = 0.05 if run else 1.0
            vals[f"hyd_t_{h}"] = ts
            vals[f"hyd_vres_{h}"] = float(p[L.P_HYD_RES_V]) * float(params.value("hyd_res_fill0"))
        vals["gb_t"] = ts
        for k, m in enumerate(self._initial_fuel()):
            vals[f"fuel_m_{k}"] = float(m)
        vals["fuel_t"] = ts
        vals["batt_soc"] = float(c.batt_soc)
        vals["batt_t"] = ts
        vals["batt_v"] = float(battery_ocv(p, c.batt_soc))
        vals["ecs_tcv"] = 0.1  # TCV near closed at start (hot bypass small; the integrator trims it)
        for n in ("ecs_tphx", "ecs_tcab", "ecs_tav", "jfs_egt", "jfs_oilt", "bay_t"):
            vals[n] = ts
        vals["ecs_pcab"] = float(c.p_amb)
        vals["jfs_oilq"] = (
            self._jfs_oil0_l if c.jfs_oil_l is None else float(c.jfs_oil_l)
        ) / 1000.0  # L -> m^3
        bt = c.brake_temp if c.brake_temp is not None else (ts, ts)
        for w in range(L.N_WHEEL):
            vals[f"brk_t_{w}"] = float(bt[w])
        stores = np.array(c.stores, dtype=np.float64)
        dt_dry = (float(p[L.P_DT_DRY_MASS_INBOARD]), float(p[L.P_DT_DRY_MASS_INBOARD]))
        if c.drop_tanks[0]:
            stores[0] += dt_dry[0]
        if c.drop_tanks[1]:
            stores[1] += dt_dry[1]
        if c.drop_tanks[2]:
            stores[4] += float(p[L.P_DT_DRY_MASS_CENTRE])
        for s in range(L.N_STORE):
            vals[f"store_m_{s}"] = float(stores[s])
        vals["gen_on"] = 1 if run else 0
        vals["bk_on"] = 1 if run else 0
        vals["ess_src"] = SRC_TRU if run else SRC_BATT
        vals["jfs_variant"] = int(c.jfs_variant)
        vals["f1a_mod"] = int(c.f1a_mod)
        vals["ext_charged"] = 1
        return L.STATE.pack(**vals)

    def initial_outputs(self, state: State) -> Outputs:
        """State-implied outputs at t0 (the first step replaces them; input-dependent ports are estimates)."""
        f, i, p = state["f"], state["i"], self._p
        ne = self.n_engines
        mp = np.empty(13)
        mass_properties(f, p, mp)
        src = int(i[L.I_ESS_SRC])
        v_tru, v_bk, v_b = float(p[L.P_TRU_V_NL]), float(p[L.P_BK_V_NL]), float(f[L.F_BATT_V])
        bus = np.zeros(L.N_BUS)  # order: DC main, DC essential, DC emergency, AC main
        if src == SRC_TRU:
            bus[[L.B_DCM, L.B_ESS, L.B_EMG]] = v_tru
            bus[L.B_AC] = float(p[L.P_AC_V_NOM])
        elif src == SRC_BACKUP:
            bus[[L.B_ESS, L.B_EMG]] = v_bk
        else:
            bus[L.B_EMG] = v_b
        running = int(i[L.I_GEN_ON]) == 1
        if running:
            bleed = np.full(ne, (float(p[L.P_ECS_M_SET]) + float(p[L.P_ECS_M_AUX])) / ne)
            dp = float(p[L.P_HYD_P_NOM] - p[L.P_HYD_P_RET])
            q_leak = float(p[L.P_HYD_Q_LEAK_INT] + (1 - p[L.P_HYD_ETA_V]) * p[L.P_HYD_Q_RATED])
            hyd = 2 * q_leak * dp / float(p[L.P_HYD_ETA_HM])
            dc = float(p[L.P_LOAD_DCM_GROUND] + p[L.P_LOAD_ESS] + p[L.P_LOAD_EMERG])
            gen = (float(p[L.P_LOAD_AC_GROUND]) + dc / float(p[L.P_TRU_EFF])) / float(p[L.P_GEN_EFF])
            pto = np.zeros(ne)
            pto[int(self._cfg[L.C_GEN_ENG])] = hyd + gen + float(p[L.P_GEN_NOLOAD])
        else:
            bleed = np.zeros(ne)
            pto = np.zeros(ne)
        pcab = float(f[L.F_ECS_PCAB])
        cap = float(p[L.P_BATT_CAP_AH])
        ah = cap - cap * (
            1.0 - float(f[L.F_BATT_SOC])
        )  # battery display at t0 (fade not known before a step)
        alt_exp = float(p[L.P_R_AIR] * p[L.P_ISA_LAPSE] / p[L.P_G0])
        cab_alt = float(p[L.P_ISA_T0] / p[L.P_ISA_LAPSE]) * (1.0 - (pcab / float(p[L.P_ISA_P0])) ** alt_exp)
        res_v = float(p[L.P_HYD_RES_V])
        return {
            "hyd_p": np.array(f[L.F_HYD_P : L.F_HYD_P + 2]),
            "hyd_dp_avail": np.maximum(np.array(f[L.F_HYD_P : L.F_HYD_P + 2]) - float(p[L.P_HYD_P_RET]), 0.0),
            "hyd_t": np.array(f[L.F_HYD_T : L.F_HYD_T + 2]),
            "bleed_extract": bleed,
            "pto_power": pto,
            "fuel_mass": np.array(f[L.F_FUEL_M : L.F_FUEL_M + L.N_TANKS]),
            "mass": np.array(mp[0]),
            "cg": mp[1:4].copy(),
            "inertia": mp[4:13].reshape(3, 3).copy(),
            "bus_v": np.array(bus),
            "gen_online": np.array(int(i[L.I_GEN_ON]), dtype=np.int64),
            "batt_soc": np.array(f[L.F_BATT_SOC]),
            "ecs_t": np.array(
                [f[L.F_ECS_TPHX], f[L.F_ECS_TPHX], f[L.F_ECS_TPHX], f[L.F_ECS_TCAB], f[L.F_ECS_TAV]]
            ),
            "ecs_p": np.full(L.N_ECS, pcab),
            "brake_t": np.array(f[L.F_BRK_T : L.F_BRK_T + 2]),
            "brake_wear": np.array(f[L.F_BRK_DW : L.F_BRK_DW + 2]),
            "tyre_wear": np.array(f[L.F_TYRE_DW : L.F_TYRE_DW + 2]),
            "jfs_state": np.array(self._jfs_state(i), dtype=np.int64),
            "chute_state": np.array(int(i[L.I_CHUTE]), dtype=np.int64),
            "fuel_inlet_t": np.full(ne, float(f[L.F_FUEL_T])),
            "brake_p": np.zeros(L.N_WHEEL),
            "hyd_res_level": np.clip(np.array(f[L.F_HYD_VRES : L.F_HYD_VRES + 2]) / res_v, 0.0, 1.0),
            "probe_heat": np.array(0, dtype=np.int64),
            "amagb_speed": np.array(0.0),
            "gen_out": np.array(1 - int(i[L.I_GEN_ON]), dtype=np.int64),
            "batt_ah": np.array(ah),
            "batt_low": np.array(int(ah < float(p[L.P_BATT_LOW_WARN_AH])), dtype=np.int64),
            "bk_bite": np.array(int(i[L.I_BK_FAULT]), dtype=np.int64),
            "cabin_alt": np.array(cab_alt),
        }

    @staticmethod
    def _jfs_state(i: np.ndarray) -> int:
        mode = int(i[L.I_JFS_MODE])
        if mode == JFS_COAST and int(i[L.I_JFS_OUTCOME]) != OUT_OK:
            return JFS_STATE_COAST_FAIL
        return mode

    # ------------------------------------------------------------------ stepping
    def pack_inputs(self, inputs: Inputs, n: int) -> np.ndarray:
        """Packed float64 input block u[n, NU_FIXED + 6 n_engines] in the layout.U_* / UE_* order."""
        ne = self.n_engines

        def col(name: str, width: int) -> np.ndarray:
            return np.asarray(inputs[name], dtype=np.float64).reshape(n, width)

        parts = [
            col("hyd_flow_demand", L.N_HYD),
            col("w_hyd", L.N_HYD),
            col("f_spec_body", 3),
            col("tas", 1),
            col("mach", 1),
            col("wow", L.N_GEAR),
            col("wheel_speed", L.N_WHEEL),
            col("brake_energy_rate", L.N_WHEEL),
            col("t_s", 1),
            col("p_s", 1),
            col("rho", 1),
            col("health_utility", L.N_HEALTH),
            col("n2", ne),
            col("bleed_p3", ne),
            col("bleed_t3", ne),
            col("wf", ne),
            col("wf_ab", ne),
            col("w_bleed_pto", ne),
        ]
        return np.ascontiguousarray(np.concatenate(parts, axis=1))

    def _ignition_draw(self, i: np.ndarray) -> float:
        a = int(i[L.I_JFS_ATTEMPT])
        if int(i[L.I_JFS_MODE]) == JFS_CRANK and int(i[L.I_JFS_DRAWN]) == 0 and a > 0:
            return float(self.stream("jfs_ignition").draws(a - 1, 1)[0])
        return 1.0

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        n = int(t.size)
        u = self.pack_inputs(inputs, n)
        f, i, out, outi = self._kernel(
            state["f"], state["i"], self._p, u, self._cfg, self._ignition_draw(state["i"]), dt
        )
        return {"f": f, "i": i}, self.unpack_outputs(out, outi)

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        """Per-step execution is step_block with L = 1 (bitwise identical by construction)."""
        one = {k: np.asarray(v)[None, ...] for k, v in inputs.items()}
        new, out = self.step_block(state, one, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}

    def unpack_outputs(self, out: np.ndarray, outi: np.ndarray) -> Outputs:
        ne = self.n_engines
        n = out.shape[0]
        base = L.NO_FIXED

        def sl(a: int, w: int) -> np.ndarray:
            return np.ascontiguousarray(out[:, a : a + w])

        return {
            "hyd_p": sl(L.O_HYD_P, 2),
            "hyd_dp_avail": sl(L.O_HYD_DP, 2),
            "hyd_t": sl(L.O_HYD_T, 2),
            "bleed_extract": sl(base + L.OE_BLEED * ne, ne),
            "pto_power": sl(base + L.OE_PTO * ne, ne),
            "fuel_mass": sl(L.O_FUEL_M, L.N_TANKS),
            "mass": np.ascontiguousarray(out[:, L.O_MASS]),
            "cg": sl(L.O_CG, 3),
            "inertia": sl(L.O_INERTIA, 9).reshape(n, 3, 3),
            "bus_v": sl(L.O_BUS_V, L.N_BUS),
            "gen_online": np.ascontiguousarray(outi[:, L.OI_GEN_ON]),
            "batt_soc": np.ascontiguousarray(out[:, L.O_BATT_SOC]),
            "ecs_t": sl(L.O_ECS_T, L.N_ECS),
            "ecs_p": sl(L.O_ECS_P, L.N_ECS),
            "brake_t": sl(L.O_BRK_T, 2),
            "brake_wear": sl(L.O_BRK_W, 2),
            "tyre_wear": sl(L.O_TYRE_W, 2),
            "jfs_state": np.ascontiguousarray(outi[:, L.OI_JFS]),
            "chute_state": np.ascontiguousarray(outi[:, L.OI_CHUTE]),
            "fuel_inlet_t": sl(base + L.OE_FUEL_IN * ne, ne),
            "brake_p": sl(L.O_BRK_P, 2),
            "hyd_res_level": sl(L.O_HYD_LVL, 2),
            "probe_heat": np.ascontiguousarray(outi[:, L.OI_PROBE_HEAT]),
            "amagb_speed": np.ascontiguousarray(out[:, L.O_AMAGB_W]),
            "gen_out": np.ascontiguousarray(outi[:, L.OI_GEN_OUT]),
            "batt_ah": np.ascontiguousarray(out[:, L.O_BATT_AH]),
            "batt_low": np.ascontiguousarray(outi[:, L.OI_BATT_LOW]),
            "bk_bite": np.ascontiguousarray(outi[:, L.OI_BK_BITE]),
            "cabin_alt": np.ascontiguousarray(out[:, L.O_CAB_ALT]),
        }

    # ------------------------------------------------------------------ events
    def on_event(self, state: State, event: Event, t: int) -> tuple[State, list[Event]]:
        f = np.array(state["f"], copy=True)
        i = np.array(state["i"], copy=True)
        p = self._p
        kind = event.kind
        pl = event.payload
        mode = int(i[L.I_JFS_MODE])
        if kind == "util.jfs_start":
            if mode in (JFS_OFF, JFS_COAST):
                i[L.I_JFS_MODE] = JFS_CRANK
                i[L.I_JFS_ATTEMPT] += 1
                i[L.I_JFS_DRAWN] = 0
                i[L.I_JFS_LIT] = 0
                i[L.I_JFS_OUTCOME] = 0
                f[L.F_JFS_TMODE] = 0.0
        elif kind == "util.jfs_abort":
            if mode in (JFS_CRANK, JFS_ACCEL, JFS_ENGAGED):
                i[L.I_JFS_OUTCOME] = OUT_ABORT
                i[L.I_JFS_MODE] = JFS_COAST
                i[L.I_JFS_LIT] = 0
                i[L.I_JFS_CONSEC] = 0
                i[L.I_JFS_FAIL] += 1
                f[L.F_JFS_TMODE] = 0.0
        elif kind == "util.chute_deploy":
            if int(i[L.I_CHUTE]) == 0:
                v = float(f[L.F_LAST_TAS])
                i[L.I_CHUTE_N] += 1
                if v > float(p[L.P_CHUTE_V_EMERG]):
                    i[L.I_CHUTE] = 3
                else:
                    i[L.I_CHUTE] = 1
                if v > float(p[L.P_CHUTE_V_NORMAL]):
                    i[L.I_CHUTE_OVER] += 1
        elif kind == "util.chute_jettison":
            if int(i[L.I_CHUTE]) == 1:
                i[L.I_CHUTE] = 2
        elif kind == "util.fire_extinguish":
            if int(i[L.I_EXT_CHARGED]) == 1:
                i[L.I_EXT_CHARGED] = 0
                u = float(self.stream("fire_extinguish").draws(int(i[L.I_FIRE_N]), 1)[0])
                i[L.I_FIRE_N] += 1
                if int(i[L.I_FIRE_ON]) == 1 and u < float(p[L.P_FIRE_P_EXT]):
                    i[L.I_FIRE_ON] = 0
        elif kind == "util.fault":
            self._fault(f, i, str(pl["mode"]))
        elif kind == "util.config":
            item, value = str(pl["item"]), int(pl["value"])
            if item == "f1a_mod" and value in (0, 1):
                i[L.I_F1A_MOD] = value
            elif item == "jfs_variant" and value in (1, 2):
                i[L.I_JFS_VARIANT] = value
            else:
                raise ContractError(f"util.config: unsupported item/value {item}={value}")
        elif kind == "mx.action":
            # AD-44: configuration changes arrive as M18 maintenance actions. Only embodied modifications
            # with a known effect on M09 change state; every other action (R/R, washes, ...) is a no-op here.
            if str(pl.get("action")) == "MOD":
                eff = MOD_EFFECTS.get(str(pl.get("mod_id")))
                if eff is not None:
                    i[eff[0]] = eff[1]
        elif kind == "util.refuel":
            self._refuel(f, p, pl)
        elif kind == "util.store_release":
            f[L.F_STORE_M + int(pl["station"])] = 0.0
        else:
            return super().on_event(state, event, t)
        return {"f": f, "i": i}, []

    def _refuel(self, f: np.ndarray, p: np.ndarray, pl: Mapping) -> None:
        """``util.refuel`` (AD-49 fill-to-target): fill tank ``tank`` up to ``target_kg`` with fuel at
        ``t_fuel`` [K]. The fill stops at the tank volume at the mixed fuel temperature (M09's density law),
        fuel above the target stays (no defuel), and the lumped fuel temperature mixes by heat capacity (the
        fuel plus the structure term of the fuel thermal model). A target in an unfitted drop tank is an
        error."""
        k, target, t_in = int(pl["tank"]), float(pl["target_kg"]), float(pl["t_fuel"])
        if not 0 <= k < L.N_TANKS:
            raise ContractError(f"util.refuel: tank index {k} outside 0..{L.N_TANKS - 1}")
        if not (np.isfinite(target) and target >= 0.0 and np.isfinite(t_in) and t_in > 0.0):
            raise ContractError(f"util.refuel: target {target} kg at {t_in} K is not a fuel load")
        fitted = dict(zip((L.T_DTL, L.T_DTR, L.T_DTC), self._config.drop_tanks, strict=True))
        if target > 0.0 and not fitted.get(k, True):
            raise ContractError(f"util.refuel: {L.TANKS[k]} is not fitted")
        m_k = float(f[L.F_FUEL_M + k])
        cp = float(p[L.P_FUEL_CP])
        c0 = float(np.sum(f[L.F_FUEL_M : L.F_FUEL_M + L.N_TANKS])) * cp + float(p[L.P_FUEL_C_STRUCT])
        t0 = float(f[L.F_FUEL_T])
        cap_v = float(_tank_caps(p)[k])
        if target <= m_k:
            return
        new = target
        for _ in range(3):  # the volume limit at the mixed temperature (a contraction: converged in 2)
            dm = new - m_k
            t_mix = (c0 * t0 + dm * cp * t_in) / (c0 + dm * cp)
            new = max(m_k, min(target, cap_v * float(fuel_density(p, t_mix))))
        dm = new - m_k
        if dm > 0.0:
            f[L.F_FUEL_M + k] = new
            f[L.F_FUEL_T] = (c0 * t0 + dm * cp * t_in) / (c0 + dm * cp)
            f[L.F_FUEL_REFUEL] += dm

    @staticmethod
    def _fault(f: np.ndarray, i: np.ndarray, mode: str) -> None:
        table = {
            "gen_fail": (L.I_GEN_FAULT, 1),
            "gen_restore": (L.I_GEN_FAULT, 0),
            "bk_fail": (L.I_BK_FAULT, 1),
            "bk_restore": (L.I_BK_FAULT, 0),
            "fire_onset": (L.I_FIRE_ON, 1),
            "fire_out": (L.I_FIRE_ON, 0),
            "fire_loop_ok": (L.I_FIRE_DET, 0),
            "fire_loop_open": (L.I_FIRE_DET, 1),
            "fire_loop_short": (L.I_FIRE_DET, 2),
        }
        if mode not in table:
            raise ContractError(f"util.fault: unknown mode {mode!r} (known: {sorted(table)})")
        idx, val = table[mode]
        i[idx] = val

    # ------------------------------------------------------------------ truth view (tests, proposed ports)
    def truth_view(self, state: State, health: np.ndarray | None = None, p_amb: float = 101325.0) -> dict:
        """Named SI truth quantities that have no catalogued port yet (see README 'Proposed interface')."""
        f, i, p = state["f"], state["i"], self._p
        hv = np.zeros(L.N_HEALTH) if health is None else np.asarray(health, dtype=np.float64)
        rho = float(fuel_density(p, f[L.F_FUEL_T]))
        s = float(f[L.F_SLOSH_S])
        f1a_mod = int(i[L.I_F1A_MOD])
        wet = [float(pickup_wetness(p, f[L.F_FUEL_M + k], k, s, rho, f1a_mod)) for k in range(L.N_TANKS)]
        res_v = float(p[L.P_HYD_RES_V])
        return {
            "hyd_level": [float(f[L.F_HYD_VRES + h]) / res_v for h in range(L.N_HYD)],
            "hyd_volume_invariant": [
                float(hyd_volume_invariant(f, p, h, p_amb, hv[L.H_PRECHARGE + h], 0.0))
                for h in range(L.N_HYD)
            ],
            "hyd_swash": [float(f[L.F_HYD_X + h]) for h in range(L.N_HYD)],
            "amagb_oil_t": float(f[L.F_GB_T]),
            "fuel_t": float(f[L.F_FUEL_T]),
            "fuel_density": rho,
            "fuel_slope": s,
            "fuel_pickup_wetness": wet,
            "feed_mass": float(f[L.F_FUEL_M + L.T_F1] + f[L.F_FUEL_M + L.T_F2]),
            "fuel_xfer_group": int(i[L.I_XFER_GRP]),
            "fuel_burn": float(f[L.F_FUEL_BURN]),
            "fuel_unmet": float(f[L.F_FUEL_UNMET]),
            "fuel_refuel": float(f[L.F_FUEL_REFUEL]),
            "batt_v": float(f[L.F_BATT_V]),
            "batt_t": float(f[L.F_BATT_T]),
            "batt_q": float(f[L.F_BATT_Q]),
            "batt_vp": float(f[L.F_BATT_VP]),
            "gen_fault": int(i[L.I_GEN_FAULT]),
            "bk_on": int(i[L.I_BK_ON]),
            "ess_src": int(i[L.I_ESS_SRC]),
            "xfer_left": int(i[L.I_XFER_LEFT]),
            "ecs_tcv": float(f[L.F_ECS_TCV]),
            "ecs_bleed_cum": float(f[L.F_ECS_MBLEED]),
            "ecs_supply_cum": float(f[L.F_ECS_MSUP]),
            "jfs_speed": float(f[L.F_JFS_N]),
            "jfs_speed_rad_s": float(f[L.F_JFS_N]) * float(p[L.P_JFS_RATED_SPEED]),
            "jfs_egt": float(f[L.F_JFS_EGT]),
            "jfs_oil_t": float(f[L.F_JFS_OILT]),
            "jfs_oil_l": float(f[L.F_JFS_OILQ]) * 1000.0,
            "jfs_mode": int(i[L.I_JFS_MODE]),
            "jfs_outcome": int(i[L.I_JFS_OUTCOME]),
            "jfs_attempts": int(i[L.I_JFS_ATTEMPT]),
            "jfs_consecutive": int(i[L.I_JFS_CONSEC]),
            "jfs_ok": int(i[L.I_JFS_OK]),
            "jfs_fail": int(i[L.I_JFS_FAIL]),
            "brake_applications": [int(i[L.I_BRK_APPS + w]) for w in range(L.N_WHEEL)],
            "brake_energy_in": [float(f[L.F_BRK_EIN + w]) for w in range(L.N_WHEEL)],
            "brake_heat_out": [float(f[L.F_BRK_EOUT + w]) for w in range(L.N_WHEEL)],
            "landings": int(i[L.I_LANDINGS]),
            "tyre_burst": [int(i[L.I_TYRE_BURST + w]) for w in range(L.N_WHEEL)],
            "chute_state": int(i[L.I_CHUTE]),
            "chute_streamings": int(i[L.I_CHUTE_N]),
            "chute_over_limit": int(i[L.I_CHUTE_OVER]),
            "fire_on": int(i[L.I_FIRE_ON]),
            "fire_warn": int(i[L.I_FIRE_WARN]),
            "bay_t": float(f[L.F_BAY_T]),
            "extinguisher_charged": int(i[L.I_EXT_CHARGED]),
        }

    def sortie_wear(self, state: State) -> dict[str, tuple[float, ...] | float]:
        """AD-48.6: this sortie's physical brake and tyre accrual (left, right main), the brake energy
        absorbed per wheel [J] and the touchdowns M09 counted - keyword arguments of
        :func:`phalanx.health.usage.usage_from_truth` (``SortieUsage`` fields), so M10 holds the hidden wear
        truth between sorties (``brake_wear_accrued`` / ``tyre_wear_accrued`` replace its surrogate)."""
        f, i = state["f"], state["i"]
        return {
            "brake_wear_accrued": (float(f[L.F_BRK_DW]), float(f[L.F_BRK_DW + 1])),
            "tyre_wear_accrued": (float(f[L.F_TYRE_DW]), float(f[L.F_TYRE_DW + 1])),
            "brake_energy_j": (float(f[L.F_BRK_EIN]), float(f[L.F_BRK_EIN + 1])),
            "landings": float(i[L.I_LANDINGS]),
        }

    def carry_over(self, state: State) -> UtilitiesConfig:
        """Initial conditions of the next sortie from this sortie's final state (fuel, battery, brakes, JFS
        oil, configuration). Thermal soak between sorties is the scenario's call (it sets ``soak_temp``)."""
        f, i, c = state["f"], state["i"], self._config
        return UtilitiesConfig(
            soak_temp=c.soak_temp,
            p_amb=c.p_amb,
            fuel=tuple(float(max(m, 0.0)) for m in f[L.F_FUEL_M : L.F_FUEL_M + L.N_TANKS]),
            drop_tanks=c.drop_tanks,
            stores=c.stores,
            batt_soc=float(np.clip(f[L.F_BATT_SOC], 0.0, 1.0)),
            jfs_variant=int(i[L.I_JFS_VARIANT]),
            f1a_mod=int(i[L.I_F1A_MOD]),
            engine_running=False,
            brake_temp=(float(f[L.F_BRK_T]), float(f[L.F_BRK_T + 1])),
            jfs_oil_l=float(f[L.F_JFS_OILQ]) * 1000.0,
        )
