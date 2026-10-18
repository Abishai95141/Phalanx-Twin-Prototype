"""``AvionicsSystem``: the M12 avionics sensor-system extension as one 240 Hz module (AD-51, AD-36).

Owns the computed avionics outputs (INS/GPS, standby AHRS, ADC computation, radar altimeter, SMS station
status) and the electrical supply path from ``util.bus_v``. Each subsystem is a compiled kernel over explicit
flat state (AD-22; NumPy reference = the kernel's ``py_func``); every random number comes from an
identity-keyed stream indexed by tick, power-on count, along-track cell or command count (AD-37), so a fork
from any snapshot continues bitwise and branches share their exogenous draws (CRN).

Outputs are the recorded channels (``rec_*``, SI or status words; ``ports.RECORDED``), their restricted truth
companions (``tru_*``), the radar-altimeter SSM and the LRU powered flags (for the M15 RT silence in phase B).
M13's recorder takes the ``rec_*`` values as ``external=`` channels (AD-42).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from phalanx.bus.clocks import key_value
from phalanx.core.events import Event
from phalanx.core.module import ContractError, Inputs, ModuleBase, Outputs, ParamSet, Port
from phalanx.core.rng import Keys, StreamDecl, Variate
from phalanx.core.sampling import max_samples_per_step, samples_for_steps
from phalanx.core.state import Field, State, StateSchema
from phalanx.core.time import RG_240, latest_truth_steps, truth_step_times_ns

from . import adc as A
from . import ahrs as H
from . import ins as N
from . import radalt as R
from . import sms as S
from .channels import (
    ADC_CHANNELS,
    ADC_VALID_CHANNELS,
    AHRS_CHANNELS,
    INS_CHANNELS,
    INS_STATUS_CHANNELS,
    NUMERIC,
    RADALT_CHANNEL,
    SMS_RELEASE_CHANNEL,
    SMS_STATION_CHANNELS,
    WORDS,
    rec_port,
    tru_port,
)
from .config import AvionicsConfig

SUBSYSTEM = "avionics"


def _decl(component: str, identity: tuple[str, ...], variate: Variate, description: str) -> StreamDecl:
    return StreamDecl(
        SUBSYSTEM, component, identity, variate, 4096, "phalanx.sensors.avionics (M12)", description
    )


UNIT_SORTIE = ("scenario", "tail", "serial", "sortie")
SENSOR_SORTIE = ("scenario", "tail", "sortie", "sensor")
STREAMS: tuple[StreamDecl, ...] = (
    _decl(
        "ins_on",
        UNIT_SORTIE,
        Variate.NORMAL,
        "INS turn-on gyro/accel biases and initial GPS error (9 per power-on)",
    ),
    _decl("ins_tick", SENSOR_SORTIE, Variate.NORMAL, "INS white noise and Gauss-Markov drives (15 per tick)"),
    _decl("ahrs_on", UNIT_SORTIE, Variate.NORMAL, "AHRS turn-on gyro/accel biases (6 per power-on)"),
    _decl(
        "ahrs_tick",
        SENSOR_SORTIE,
        Variate.NORMAL,
        "AHRS gyro white noise and Gauss-Markov drive (6 per tick)",
    ),
    _decl(
        "radalt_install",
        ("scenario", "serial"),
        Variate.NORMAL,
        "radar-altimeter unit scale and zero error (2)",
    ),
    _decl(
        "radalt_terrain", SENSOR_SORTIE, Variate.NORMAL, "terrain height process, one per along-track cell"
    ),
    _decl("sms_release", SENSOR_SORTIE, Variate.UNIFORM, "hung-store draw, one per release command"),
)

# truth input layout per subsystem (catalogue signals; bindings in ports.py)
TRUTH_PORTS: tuple[tuple[str, str, str, str, tuple[int, ...]], ...] = (
    # (port, catalogue signal, unit, dtype, shape)
    ("af_pos_geo", "af.pos_geo", "1", "<f8", (3,)),
    ("af_vel_ned", "af.vel_ned", "m/s", "<f8", (3,)),
    ("af_quat", "af.quat", "1", "<f8", (4,)),
    ("af_omega_body", "af.omega_body", "rad/s", "<f8", (3,)),
    ("af_f_spec_body", "af.f_spec_body", "m/s**2", "<f8", (3,)),
    ("af_hag", "af.hag", "m", "<f8", ()),
    ("af_wow", "af.wow", "1", "<i8", (3,)),
    ("af_mach", "af.mach", "1", "<f8", ()),
    ("af_tas", "af.tas", "m/s", "<f8", ()),
    ("af_alpha", "af.alpha", "rad", "<f8", ()),
    ("af_beta", "af.beta", "rad", "<f8", ()),
    ("af_qbar", "af.qbar", "Pa", "<f8", ()),
    ("env_p_s", "env.p_s", "Pa", "<f8", ()),
    ("env_t_s", "env.t_s", "K", "<f8", ()),
    ("util_probe_heat", "util.probe_heat", "1", "<i8", ()),
    ("pilot_gear_cmd", "pilot.gear_cmd", "1", "<i8", ()),
)
BUS_PORT = ("util_bus_v", "util.bus_v", "V", "<f8")
POWER_PORTS = ("powered_ingps", "powered_ahrs", "powered_radalt", "powered_sms")
#: the P0 altitude signal the FADEC reads (W2.2): the static pressure at the ADC's pressure altitude AD.HP,
#: i.e. the position-error-corrected static pressure, in Pa (``adc.static_pressure_at``; M08 binds
#: ``avio.<this>``)
P0_PORT = "p0_from_hp"
_HP = ADC_CHANNELS.index("AD.HP")


def lane_port(channel_id: str) -> str:
    """Lane input port of an ADC lane (the M13 / M05 convention): ``AD.PS.A`` -> ``lane_ad_ps_a``."""
    return "lane_" + channel_id.lower().replace(".", "_")


def input_ports(cfg: AvionicsConfig, n_buses: int) -> tuple[Port, ...]:
    ports = [Port(name, unit, dt, shape) for name, _sig, unit, dt, shape in TRUTH_PORTS]
    ports.append(Port(BUS_PORT[0], BUS_PORT[2], BUS_PORT[3], (n_buses,)))
    cap = max_samples_per_step(cfg.dfcc_clock)
    for cid in A.LANE_CHANNELS:
        ports.append(Port(lane_port(cid), _lane_unit(cid), "<f8", (cap,), cfg.dfcc_clock))
    return tuple(ports)


def _lane_unit(cid: str) -> str:
    if cid.startswith(("AD.PS.", "AD.PT.")):
        return "Pa"
    if cid == "AD.TAT":
        return "K"
    return "rad"


def input_bindings() -> dict[str, str]:
    b = {name: sig for name, sig, _u, _d, _s in TRUTH_PORTS}
    b[BUS_PORT[0]] = BUS_PORT[1]
    for cid in A.LANE_CHANNELS:
        b[lane_port(cid)] = f"lane.{cid}"
    return b


def output_ports(si_units: Mapping[str, str]) -> tuple[Port, ...]:
    ports = []
    for cid in NUMERIC:
        ports.append(Port(rec_port(cid), si_units[cid], "<f8", ()))
        ports.append(Port(tru_port(cid), si_units[cid], "<f8", ()))
    for cid in WORDS:
        ports.append(Port(rec_port(cid), "1", "<i8", ()))
    ports.append(Port("radalt_ssm", "1", "<i8", ()))
    ports.extend(Port(p, "1", "<i8", ()) for p in POWER_PORTS)
    ports.append(Port(P0_PORT, "Pa", "<f8", ()))
    return tuple(ports)


def _schema(platform: str) -> StateSchema:
    return StateSchema(
        f"sensors.avionics.{platform}",
        1,
        (
            Field("ins_f", "<f8", (N.N_F,)),
            Field("ins_i", "<i8", (N.N_I,)),
            Field("ahrs_f", "<f8", (H.N_F,)),
            Field("ahrs_i", "<i8", (H.N_I,)),
            Field("radalt_f", "<f8", (R.N_F,)),
            Field("radalt_i", "<i8", (R.N_I,)),
            Field("adc_f", "<f8", (A.N_F,)),
            Field("adc_i", "<i8", (A.N_I,)),
            Field("sms_i", "<i8", (S.N_I,)),
            Field("dfcc_next", "<i8", ()),
            Field("tick", "<i8", ()),
        ),
    )


class AvionicsSystem(ModuleBase):
    """M12 avionics extension (AD-51): INS/GPS, AHRS, ADC computation, radar altimeter, SMS; 240 Hz.

    Args:
        id: module id. config: ``build_avionics_config()``. dictionary: the M01 dictionary (SI units of the
        recorded channels, the store_station code count). lru_serials: installed unit serials (sortie manifest
        ``lru_serials``); a missing LRU is ``<tail>:<LRU>`` (as ``bus.clocks.SortieIdentity``).
        compiled: False runs the NumPy references through the scheduler.
    """

    version = "1.0.0"
    rate = RG_240
    streams = STREAMS

    def __init__(
        self,
        id: str,
        config: AvionicsConfig,
        dictionary: Any,
        *,
        params: ParamSet | None = None,
        lru_serials: Mapping[str, str] | None = None,
        compiled: bool = True,
        identity: Mapping[str, str | int] | None = None,
    ) -> None:
        from phalanx.utilities.layout import BUSES

        self.config = config
        units = {cid: dictionary.eu_conversion(cid).si_units for cid in NUMERIC}
        self.ports_in = input_ports(config, len(BUSES))
        self.ports_out = output_ports(units)
        self.state_schema = _schema(config.platform)
        super().__init__(id, params if params is not None else config.params, identity=identity)
        self._n_codes = len(dictionary.code_table("store_station")["codes"])
        self._serials = dict(lru_serials or {})
        self._bus_index = np.array(
            [config.bus[k] for k in ("INGPS", "AHRS", "RADALT", "SMS")], dtype=np.int64
        )
        self._ins = N.ins_kernel if compiled else N.ins_kernel.py_func
        self._ahrs = H.ahrs_kernel if compiled else H.ahrs_kernel.py_func
        self._radalt = R.radalt_kernel if compiled else R.radalt_kernel.py_func
        self._adc = A.adc_kernel if compiled else A.adc_kernel.py_func
        self._sms = S.sms_kernel if compiled else S.sms_kernel.py_func
        self._h_baro = A.pressure_altitude_array if compiled else A.pressure_altitude_array.py_func
        self._p0 = A.static_pressure_at_array if compiled else A.static_pressure_at_array.py_func
        self._cap = max_samples_per_step(config.dfcc_clock)

    # ------------------------------------------------------------------ identity
    def _serial(self, lru: str, keys: Keys | None = None) -> str:
        s = self._serials.get(lru)
        if s is not None:
            return key_value(s)
        k = keys if keys is not None else self.keys
        tail = k.identity.as_dict().get("tail", "TAIL")
        return key_value(f"{tail}:{lru}")

    # ------------------------------------------------------------------ state
    def init(self, params: ParamSet, keys: Keys) -> State:
        ins_f, ins_i = N.ins_initial_state()
        ahrs_f, ahrs_i = H.ahrs_initial_state()
        z = keys.stream(SUBSYSTEM, "radalt_install", serial=self._serial("RADALT", keys)).draws(0, 2)
        rad_f, rad_i = R.radalt_initial_state(
            self.config.radalt_scale_sigma * float(z[0]), self.config.radalt_offset_sigma * float(z[1])
        )
        adc_f, adc_i = A.adc_initial_state()
        return {
            "ins_f": ins_f,
            "ins_i": ins_i,
            "ahrs_f": ahrs_f,
            "ahrs_i": ahrs_i,
            "radalt_f": rad_f,
            "radalt_i": rad_i,
            "adc_f": adc_f,
            "adc_i": adc_i,
            "sms_i": S.sms_initial_state(),
            "dfcc_next": np.array(self.config.dfcc_clock.first_index_at_or_after(0), dtype=np.int64),
            "tick": np.array(0, dtype=np.int64),
        }

    def initial_outputs(self, state: State) -> Outputs:
        """Before the first step: held values from the state (zeros at sortie start; never NaN)."""
        out: Outputs = {}
        f = state["ins_f"]
        for k, cid in enumerate(INS_CHANNELS):
            out[rec_port(cid)] = np.array(f[N.F_HOLD + k])
            out[tru_port(cid)] = np.array(0.0)
        i = state["ins_i"]
        for k, cid in enumerate(INS_STATUS_CHANNELS):
            out[rec_port(cid)] = np.array(int(i[(N.I_HMODE, N.I_HFIX, N.I_HFOM)[k]]), dtype=np.int64)
        for k, cid in enumerate(AHRS_CHANNELS):
            out[rec_port(cid)] = np.array(state["ahrs_f"][H.F_HOLD + k])
            out[tru_port(cid)] = np.array(0.0)
        out[rec_port(RADALT_CHANNEL)] = np.array(state["radalt_f"][R.F_Y])
        out[tru_port(RADALT_CHANNEL)] = np.array(0.0)
        for k, cid in enumerate(ADC_CHANNELS):
            out[rec_port(cid)] = np.array(state["adc_f"][A.F_OUT + k])
            out[tru_port(cid)] = np.array(0.0)
        for k, cid in enumerate(ADC_VALID_CHANNELS):
            out[rec_port(cid)] = np.array(int(state["adc_i"][A.I_VALID + k]), dtype=np.int64)
        hp0 = np.array([state["adc_f"][A.F_OUT + _HP]], dtype=np.float64)
        out[P0_PORT] = np.array(self._p0(hp0, self.config.adc_p)[0])
        si = state["sms_i"]
        for k, cid in enumerate(SMS_STATION_CHANNELS):
            out[rec_port(cid)] = np.array(int(si[S.I_CODES + k]), dtype=np.int64)
        out[rec_port(SMS_RELEASE_CHANNEL)] = np.array(int(si[S.I_RELEASED]), dtype=np.int64)
        out["radalt_ssm"] = np.array(int(state["radalt_i"][R.I_SSM]), dtype=np.int64)
        for pname, pw in zip(
            POWER_PORTS,
            (
                state["ins_i"][N.I_POWERED],
                state["ahrs_i"][H.I_POWERED],
                state["radalt_i"][R.I_POWERED],
                si[S.I_POWERED],
            ),
            strict=True,
        ):
            out[pname] = np.array(int(pw), dtype=np.int64)
        return out

    # ------------------------------------------------------------------ stepping
    def _draw_block(self, component: str, start: int, count: int, **extra: str) -> np.ndarray:
        return np.asarray(self.stream(component, **extra).draws(start, count), dtype=np.float64)

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        cfg = self.config
        t = np.asarray(t, dtype=np.int64)
        L = int(t.size)
        t_end = truth_step_times_ns(latest_truth_steps(t) + 1)

        def col(name: str, shape: tuple[int, ...] = ()) -> np.ndarray:
            return np.asarray(inputs[name], dtype=np.float64).reshape((L, *shape))

        pos = col("af_pos_geo", (3,))
        vel = col("af_vel_ned", (3,))
        quat = col("af_quat", (4,))
        omg = col("af_omega_body", (3,))
        fsp = col("af_f_spec_body", (3,))
        vbus = np.asarray(inputs["util_bus_v"], dtype=np.float64).reshape(L, -1)
        wow = np.asarray(inputs["af_wow"], dtype=np.int64).reshape(L, -1)
        airborne = np.ascontiguousarray(np.all(wow == 0, axis=1).astype(np.int64))
        tick0 = int(state["tick"])
        new: dict[str, np.ndarray] = {}
        out: Outputs = {}

        # ---- INS/GPS
        h_baro = self._h_baro(np.ascontiguousarray(col("env_p_s")), cfg.adc_p)
        ins_truth = np.ascontiguousarray(np.concatenate([pos, vel, quat, omg, fsp, h_baro[:, None]], axis=1))
        n_on = L // 12 + 2  # power-ons that can occur in this block (each needs > hold-up below v_dropout)
        ins_serial = self._serial("INGPS")
        on0 = int(state["ins_i"][N.I_NPOWER])
        zon = self._draw_block("ins_on", on0 * N.N_ON_DRAWS, n_on * N.N_ON_DRAWS, serial=ins_serial)
        ztick = self._draw_block("ins_tick", tick0 * N.N_TICK_DRAWS, L * N.N_TICK_DRAWS, sensor="INGPS")
        f, i, o, st, tr = self._ins(
            state["ins_f"],
            state["ins_i"],
            cfg.ins_p,
            cfg.fom_bounds,
            ins_truth,
            np.ascontiguousarray(vbus[:, self._bus_index[0]]),
            airborne,
            ztick.reshape(L, N.N_TICK_DRAWS),
            zon.reshape(n_on, N.N_ON_DRAWS),
            dt,
            cfg.n_sub,
        )
        new["ins_f"], new["ins_i"] = f, i
        for k, cid in enumerate(INS_CHANNELS):
            out[rec_port(cid)] = np.ascontiguousarray(o[:, k])
            out[tru_port(cid)] = np.ascontiguousarray(tr[:, k])
        for k, cid in enumerate(INS_STATUS_CHANNELS):
            out[rec_port(cid)] = np.ascontiguousarray(st[:, k])
        out["powered_ingps"] = np.ascontiguousarray(st[:, 3])

        # ---- AHRS
        ahrs_truth = np.ascontiguousarray(np.concatenate([quat, omg, fsp], axis=1))
        on0 = int(state["ahrs_i"][H.I_NPOWER])
        zon = self._draw_block(
            "ahrs_on", on0 * H.N_ON_DRAWS, n_on * H.N_ON_DRAWS, serial=self._serial("AHRS")
        )
        ztick = self._draw_block("ahrs_tick", tick0 * H.N_TICK_DRAWS, L * H.N_TICK_DRAWS, sensor="AHRS")
        f, i, o, pw, tr = self._ahrs(
            state["ahrs_f"],
            state["ahrs_i"],
            cfg.ahrs_p,
            ahrs_truth,
            np.ascontiguousarray(vbus[:, self._bus_index[1]]),
            ztick.reshape(L, H.N_TICK_DRAWS),
            zon.reshape(n_on, H.N_ON_DRAWS),
            dt,
        )
        new["ahrs_f"], new["ahrs_i"] = f, i
        for k, cid in enumerate(AHRS_CHANNELS):
            out[rec_port(cid)] = np.ascontiguousarray(o[:, k])
            out[tru_port(cid)] = np.ascontiguousarray(tr[:, k])
        out["powered_ahrs"] = pw

        # ---- radar altimeter
        rad_truth = np.ascontiguousarray(np.concatenate([col("af_hag", (1,)), quat, vel[:, :2]], axis=1))
        cell0 = int(state["radalt_i"][R.I_CELL])
        k_cells = R.cells_needed(dt, L, float(cfg.radalt_p[R.P_CELL]))
        zcell = self._draw_block("radalt_terrain", cell0, k_cells, sensor="RADALT")
        f, i, o, ssm, pw, tr = self._radalt(
            state["radalt_f"],
            state["radalt_i"],
            cfg.radalt_p,
            rad_truth,
            np.ascontiguousarray(vbus[:, self._bus_index[2]]),
            zcell,
            dt,
        )
        new["radalt_f"], new["radalt_i"] = f, i
        out[rec_port(RADALT_CHANNEL)] = o
        out[tru_port(RADALT_CHANNEL)] = tr
        out["radalt_ssm"] = ssm
        out["powered_radalt"] = pw

        # ---- ADC computation on the DFCC frames of the digitised lanes
        ss = samples_for_steps(cfg.dfcc_clock, int(state["dfcc_next"]), t, t_end)
        if ss.times.size and int(ss.count.max(initial=0)) > self._cap:
            raise ContractError("more DFCC samples in one step than the lane buffer holds")
        has = np.ascontiguousarray((ss.count > 0).astype(np.int64))
        lanes = np.empty((L, A.N_LANES), dtype=np.float64)
        for c, cid in enumerate(A.LANE_CHANNELS):
            lanes[:, c] = np.asarray(inputs[lane_port(cid)], dtype=np.float64).reshape(L, self._cap)[:, 0]
        adc_truth = np.ascontiguousarray(
            np.stack(
                [
                    col("env_p_s"),
                    col("env_t_s"),
                    col("af_mach"),
                    col("af_tas"),
                    col("af_alpha"),
                    col("af_beta"),
                    col("af_qbar"),
                ],
                axis=1,
            )
        )
        heat = np.ascontiguousarray(np.asarray(inputs["util_probe_heat"], dtype=np.int64).reshape(L))
        gear = np.ascontiguousarray(np.asarray(inputs["pilot_gear_cmd"], dtype=np.int64).reshape(L))
        f, i, o, valid, tr = self._adc(
            state["adc_f"], state["adc_i"], cfg.adc_p, lanes, has, heat, gear, adc_truth, *cfg.adc_tables, dt
        )
        new["adc_f"], new["adc_i"] = f, i
        for k, cid in enumerate(ADC_CHANNELS):
            out[rec_port(cid)] = np.ascontiguousarray(o[:, k])
            out[tru_port(cid)] = np.ascontiguousarray(tr[:, k])
        for k, cid in enumerate(ADC_VALID_CHANNELS):
            out[rec_port(cid)] = np.ascontiguousarray(valid[:, k])
        out[P0_PORT] = self._p0(np.ascontiguousarray(o[:, _HP]), cfg.adc_p)
        new["dfcc_next"] = np.array(ss.next_index, dtype=np.int64)

        # ---- SMS (discrete; events change it between steps)
        si, codes, rel, pw = self._sms(
            state["sms_i"],
            np.ascontiguousarray(vbus[:, self._bus_index[3]]),
            dt,
            float(cfg.ins_p[N.P_V_DROP]),
            float(cfg.ins_p[N.P_HOLD]),
        )
        new["sms_i"] = si
        for k, cid in enumerate(SMS_STATION_CHANNELS):
            out[rec_port(cid)] = np.ascontiguousarray(codes[:, k])
        out[rec_port(SMS_RELEASE_CHANNEL)] = rel
        out["powered_sms"] = pw
        new["tick"] = np.array(tick0 + L, dtype=np.int64)
        return new, out

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        """Per-step execution is ``step_block`` with L = 1 (bitwise identical by construction)."""
        one = {k: np.asarray(v)[None, ...] for k, v in inputs.items()}
        new, out = self.step_block(state, one, np.array([t], np.int64), dt)
        return new, {k: np.array(v[0]) for k, v in out.items()}

    # ------------------------------------------------------------------ SMS events
    def on_event(self, state: State, event: Event, t: int) -> tuple[State, list[Event]]:
        if event.kind not in (S.LOAD_EVENT, S.RELEASE_EVENT):
            return super().on_event(state, event, t)
        new = {k: np.array(v, copy=True) for k, v in state.items()}
        payload = dict(event.payload)
        if event.kind == S.LOAD_EVENT:
            new["sms_i"] = S.apply_load(new["sms_i"], payload["stations"], self._n_codes)
        else:
            n = int(new["sms_i"][S.I_NCMD])
            u = float(self.stream("sms_release", sensor="SMS").draws(n, 1)[0])
            new["sms_i"] = S.apply_release(
                new["sms_i"], int(payload["station"]), str(payload["mode"]), u, self.config.sms_p_hung
            )
        return new, []
