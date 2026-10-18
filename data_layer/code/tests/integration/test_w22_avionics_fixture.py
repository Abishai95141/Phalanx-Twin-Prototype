"""TEST FIXTURE (not a model, never imported by src/): kinematically consistent flight scripts for the
M12 avionics extension (W2.2) and a System builder for truth -> M12 (air-data subset) -> M13 DFCC lanes ->
avionics.

``flight`` builds level, constant-speed flight with scripted coordinated turns from the wind axes: track
``chi`` integrates ``g tan(mu) / V``, the body is the wind frame banked by ``mu`` and pitched up by the angle
of attack (``C_nb = Rz(chi) Rx(mu) Ry(alpha)``), the body rates are the quaternion's own derivative and the
body specific force is ``C_nb^T (a_n - g_n)``. Position, NED velocity, attitude, rates and specific force
therefore agree with each other (fixture self-tests below), so the INS and AHRS error models are driven by
consistent truth, as in a closed loop. ``ArrayTruth`` replays such a script (plus air-data, electrical and
discrete signals) as catalogue truth ports, one row per truth frame (value at the frame END). The avionics
tests load this module with ``load_fixture()``.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pytest

from phalanx.acquisition.config import build_acquisition_config
from phalanx.acquisition.core import STREAMS as ACQ_STREAMS
from phalanx.acquisition.module import LaneAcquisition, lane_channels
from phalanx.core.module import ModuleBase, Param, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import RG_240, latest_truth_step
from phalanx.dictionary.params import load_param_set
from phalanx.sensors.avionics.common import euler_with_error, quat_to_dcm
from phalanx.sensors.avionics.config import build_avionics_config
from phalanx.sensors.avionics.module import STREAMS as AVIO_STREAMS
from phalanx.sensors.avionics.module import AvionicsSystem, input_bindings
from phalanx.sensors.config import build_sensor_config
from phalanx.sensors.module import BIAS_PORT, SensorPhysics

G0 = 9.80665
R_EARTH = 6371008.8
DT = 1.0 / 240.0
IDENTITY = KeyPath.of(scenario="W22", tail="KH2001", sortie="SRT0001")
ROOT = 0x5EED_0022
#: M12 bus map order (phalanx.utilities.layout.BUSES): DC main, DC essential, DC emergency, AC main
BUS_NOMINAL = (28.0, 28.0, 28.0, 115.0)
#: M12 channels of the ADC (vanes, pressures, TAT): the DFCC/ADC lanes the avionics ADC computes on
ADC_SENSOR_CHANNELS = tuple(
    [f"AD.PS.{c}" for c in "ABCD"]
    + [f"AD.PT.{c}" for c in "ABCD"]
    + [f"AD.AOA_VANE_L.{c}" for c in "ABCD"]
    + [f"AD.AOA_VANE_R.{c}" for c in "ABCD"]
    + [f"AD.AOSS_VANE.{c}" for c in "ABCD"]
    + ["AD.TAT"]
)


def load_fixture():
    name = "w22_avionics_fixture"
    if name not in sys.modules:
        p = Path(__file__).resolve()
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


# ---- kinematics -------------------------------------------------------------------------------------------
def _qmul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Hamilton product of (n, 4) scalar-first quaternions (R(a b) = R(a) R(b))."""
    aw, ax, ay, az = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    bw, bx, by, bz = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
    return np.stack(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ],
        axis=1,
    )


def _axis_quat(angle: np.ndarray, axis: int) -> np.ndarray:
    q = np.zeros((angle.size, 4))
    q[:, 0] = np.cos(angle / 2)
    q[:, 1 + axis] = np.sin(angle / 2)
    return q


def dcm(q: np.ndarray) -> np.ndarray:
    """(n, 3, 3) body -> NED matrices of (n, 4) quaternions (the kernels' quat_to_dcm)."""
    out = np.empty((q.shape[0], 3, 3))
    c = np.empty(9)
    for k in range(q.shape[0]):
        quat_to_dcm(q[k, 0], q[k, 1], q[k, 2], q[k, 3], c)
        out[k] = c.reshape(3, 3)
    return out


def frame_times(n: int) -> np.ndarray:
    """Frame-end times [s] of truth frames 0..n-1 (the 240 Hz grid, AD-36)."""
    return (np.arange(1, n + 1) * 10**9 // 240) / 1e9


def flight(
    n: int,
    *,
    speed: float = 200.0,
    alt: float = 3000.0,
    alpha0: float = 0.04,
    lat0_deg: float = 13.0,
    lon0_deg: float = 77.6,
    track0_deg: float = 0.0,
    bank_deg: Mapping[tuple[float, float], float] | None = None,
    ramp_s: float = 2.0,
) -> dict[str, np.ndarray]:
    """Frame-end truth of ``n`` frames of level, constant-speed flight with coordinated turns.

    ``bank_deg``: {(t_start, t_end): bank} segments [s]; the bank ramps in and out over ``ramp_s``.
    ``speed=0`` is a stationary aircraft (no turns; attitude level at ``alpha0`` pitch, as on the ground).
    The angle of attack scales with the load factor (``alpha0 / cos(mu)``, lift = weight / cos(mu)).
    """
    t = frame_times(n)
    mu = np.zeros(n)
    for (a, b), bank in (bank_deg or {}).items():
        up = np.clip((t - a) / ramp_s, 0.0, 1.0)
        down = np.clip((b - t) / ramp_s, 0.0, 1.0)
        mu += np.radians(bank) * np.minimum(up, down)
    if speed == 0.0 and np.any(mu != 0.0):
        raise ValueError("a stationary aircraft cannot turn")
    chidot = np.zeros(n) if speed == 0.0 else G0 * np.tan(mu) / speed
    chi = np.radians(track0_deg) + np.concatenate(
        [[0.0], np.cumsum(0.5 * (chidot[1:] + chidot[:-1]) * np.diff(t))]
    )
    alpha = alpha0 / np.cos(mu)
    q = _qmul(_qmul(_axis_quat(chi, 2), _axis_quat(mu, 0)), _axis_quat(alpha, 1))
    # body rates: omega_b = 2 vec(q* qdot) (central differences on the 240 Hz grid)
    qdot = np.gradient(q, t, axis=0)
    qc = q * np.array([1.0, -1.0, -1.0, -1.0])
    omega = 2.0 * _qmul(qc, qdot)[:, 1:]
    vn, ve = speed * np.cos(chi), speed * np.sin(chi)
    an, ae = -speed * chidot * np.sin(chi), speed * chidot * np.cos(chi)
    f_n = np.stack([an, ae, np.full(n, -G0)], axis=1)
    fb = np.einsum("kji,kj->ki", dcm(q), f_n)  # C^T f_n
    rr = R_EARTH + alt
    lat = (
        np.radians(lat0_deg) + np.concatenate([[0.0], np.cumsum(0.5 * (vn[1:] + vn[:-1]) * np.diff(t))]) / rr
    )
    lon = (
        np.radians(lon0_deg)
        + np.concatenate(
            [[0.0], np.cumsum(0.5 * (ve[1:] + ve[:-1]) / np.cos(0.5 * (lat[1:] + lat[:-1])) * np.diff(t))]
        )
        / rr
    )
    return {
        "af.pos_geo": np.stack([lat, lon, np.full(n, alt)], axis=1),
        "af.vel_ned": np.stack([vn, ve, np.zeros(n)], axis=1),
        "af.quat": q,
        "af.omega_body": omega,
        "af.f_spec_body": fb,
        "af.alpha": alpha,
        "af.nz": -fb[:, 2] / G0,
        "_bank": mu,
        "_track": chi,
    }


def isa(alt: float) -> tuple[float, float, float]:
    """ICAO troposphere (static pressure Pa, temperature K, density kg/m^3) at ``alt`` m: fixture air-data."""
    ts = 288.15 - 0.0065 * alt
    ps = 101325.0 * (ts / 288.15) ** 5.255876
    return ps, ts, ps / (287.05287 * ts)


def default_truth(
    n: int, *, hag: float | None = None, on_ground: bool = False, **kw
) -> dict[str, np.ndarray]:
    """Every catalogue signal the avionics (and the M12 air-data subset) reads, as (n, ...) arrays."""
    fl = flight(n, **kw)
    alt = float(fl["af.pos_geo"][0, 2])
    speed = float(np.linalg.norm(fl["af.vel_ned"][0]))
    ps, ts, rho = isa(alt)
    a = math.sqrt(1.4 * 287.05287 * ts)
    truth = dict(fl)
    truth.update(
        {
            "af.hag": np.full(n, alt - 900.0 if hag is None else hag),
            "af.wow": np.full((n, 3), 1 if on_ground else 0, dtype=np.int64),
            "af.mach": np.full(n, speed / a),
            "af.tas": np.full(n, speed),
            "af.beta": np.zeros(n),
            "af.qbar": np.full(n, 0.5 * rho * speed * speed),
            "env.p_s": np.full(n, ps),
            "env.t_s": np.full(n, ts),
            "env.rho": np.full(n, rho),
            "util.bus_v": np.tile(BUS_NOMINAL, (n, 1)),
            "util.probe_heat": np.ones(n, dtype=np.int64),
            "pilot.gear_cmd": np.zeros(n, dtype=np.int64),
        }
    )
    return truth


def bus_dip(truth: dict[str, np.ndarray], bus: int, t0: float, t1: float, volts: float = 0.0) -> dict:
    """A copy of ``truth`` with bus ``bus`` at ``volts`` over frame-end times [t0, t1) (an interruption)."""
    out = dict(truth)
    v = np.array(truth["util.bus_v"], copy=True)
    t = frame_times(v.shape[0])
    v[(t >= t0) & (t < t1), bus] = volts
    out["util.bus_v"] = v
    return out


class ArrayTruth(ModuleBase):
    """TEST FIXTURE: replays (n, ...) arrays as catalogue truth ports (row k at the end of step k)."""

    version = "fixture"
    rate = RG_240

    def __init__(
        self, id: str, arrays: Mapping[str, np.ndarray], ports: list[tuple[str, str, str, str, tuple]]
    ):
        self.arrays = {k: np.asarray(v) for k, v in arrays.items()}
        self.spec = ports  # (port, signal, unit, dtype, shape)
        self.ports_out = tuple(Port(p, u, d, s) for p, _sig, u, d, s in ports)
        self.state_schema = StateSchema("fixture.array_truth", 1, (Field("k", "<i8", ()),))
        super().__init__(id, ParamSet("fixture", {"a": Param(1.0, "1", "ASSUMPTION", "TEST FIXTURE")}))

    def init(self, params, keys):
        return {"k": np.array(0, dtype=np.int64)}

    def _row(self, k: int) -> dict[str, np.ndarray]:
        out = {}
        for p, sig, _u, dt, shape in self.spec:
            a = self.arrays[sig]
            out[p] = np.asarray(a[min(k, a.shape[0] - 1)], dtype=dt).reshape(shape).copy()
        return out

    def initial_outputs(self, state):
        return self._row(0)

    def step(self, state, inputs, t, dt):
        k = latest_truth_step(t)
        return {"k": np.array(k + 1, dtype=np.int64)}, self._row(k)


# ---- direct (module-alone) runs ---------------------------------------------------------------------------
def make_module(
    *, compiled: bool = True, root: int = ROOT, identity: KeyPath = IDENTITY, **kw
) -> AvionicsSystem:
    """An AvionicsSystem bound to its own keys (the avionics streams in a fresh registry)."""
    from phalanx.dictionary import load_dictionary

    m = AvionicsSystem(
        "avio", kw.pop("config", None) or build_avionics_config(), load_dictionary(), compiled=compiled, **kw
    )
    m.bind(RngService(root, StreamRegistry(list(AVIO_STREAMS))).scope(identity))
    return m


def direct_inputs(module: AvionicsSystem, truth: Mapping[str, np.ndarray], k0: int, n: int, lanes=None):
    """Inputs of ``module.step_block`` for frames [k0, k0 + n) (lanes zero unless given: no ADC)."""
    b = input_bindings()
    out = {}
    for p in module.ports_in:
        sig = b[p.name]
        if sig.startswith("lane."):
            out[p.name] = (
                np.zeros((n, *p.shape))
                if lanes is None
                else np.asarray(lanes[p.name][k0 : k0 + n], np.float64)
            )
        else:
            out[p.name] = np.asarray(truth[sig][k0 : k0 + n], dtype=p.dtype)
    return out


def run_direct(
    module: AvionicsSystem, truth: Mapping[str, np.ndarray], n: int, *, block: int = 2400, state=None, k0=0
):
    """Run the module alone over frames [k0, k0 + n) in blocks; returns (state, {port: (n, ...) array})."""
    if state is None:
        state = module.init(module.params, module.keys)
    outs: dict[str, list[np.ndarray]] = {}
    for k in range(k0, k0 + n, block):
        m = min(block, k0 + n - k)
        t = np.arange(k, k + m, dtype=np.int64) * 10**9 // 240
        state, o = module.step_block(state, direct_inputs(module, truth, k, m), t, DT)
        for kk, v in o.items():
            outs.setdefault(kk, []).append(np.asarray(v))
    return state, {kk: np.concatenate(v) for kk, v in outs.items()}


# ---- truth -> M12 -> M13 -> avionics chain ----------------------------------------------------------------
def build_avionics_chain(
    d, truth: Mapping[str, np.ndarray], *, compiled: bool = True, validate: bool = False, bias=None
):
    """System [array truth -> M12 (ADC subset) -> M13 DFCC lanes -> avionics]; returns (system, rng, mods)."""
    sens_cfg = build_sensor_config(d, channels=ADC_SENSOR_CHANNELS)
    avio = AvionicsSystem("avio", build_avionics_config(), d, compiled=compiled)
    sens = SensorPhysics("sens", load_param_set("M12", "constants"), sens_cfg, compiled=compiled)
    lanes = lane_channels(d, sens_cfg, "DFCC")
    acq = build_acquisition_config(d, lanes, sensor_channels=sens_cfg.channels)
    lane_mod = LaneAcquisition(
        "acq_dfcc", load_param_set("M13", "noise_n2"), sens_cfg, acq, d, compiled=compiled
    )
    spec: dict[str, tuple] = {}
    for s in sens_cfg.inputs:
        spec[s.port] = (s.port, s.signal, s.unit, "<f8", s.shape)
    bnd = input_bindings()
    for p in avio.ports_in:
        sig = bnd[p.name]
        if not sig.startswith("lane."):
            spec[p.name] = (p.name, sig, p.unit, p.dtype, p.shape)
    arrays = dict(truth)
    n = next(iter(truth.values())).shape[0]
    arrays["health.sensor_bias"] = np.zeros((n, sens_cfg.n_ch)) if bias is None else bias
    arrays["scenario.phase"] = np.full(n, 5, dtype=np.int64)
    spec["bias"] = ("bias", "health.sensor_bias", "1", "<f8", (sens_cfg.n_ch,))
    spec["phase"] = ("phase", "scenario.phase", "1", "<i8", ())
    tmod = ArrayTruth("truth", arrays, list(spec.values()))
    conns = [Connection(f"truth.{s.port}", f"sens.{s.port}") for s in sens_cfg.inputs]
    conns.append(Connection("truth.bias", f"sens.{BIAS_PORT}"))
    for p in lane_mod.ports_in:
        src = "truth.phase" if p.name == "phase" else f"sens.{p.name}"
        conns.append(Connection(src, f"acq_dfcc.{p.name}"))
    for p in avio.ports_in:
        src = f"acq_dfcc.{p.name}" if bnd[p.name].startswith("lane.") else f"truth.{p.name}"
        conns.append(Connection(src, f"avio.{p.name}"))
    rng = RngService(ROOT, StreamRegistry([*ACQ_STREAMS, *AVIO_STREAMS]))
    mods = [tmod, sens, lane_mod, avio]
    system = System(mods, conns, rng=rng, identity=IDENTITY, validate=validate, purity_check=validate)
    return (
        system,
        rng,
        {"truth": tmod, "sens": sens, "acq_dfcc": lane_mod, "avio": avio, "sens_cfg": sens_cfg},
    )


# ---- fixture self-tests -----------------------------------------------------------------------------------
@pytest.mark.unit
def test_fixture_turn_is_coordinated_and_consistent():
    """n = 2,400 frames (10 s, one 30 deg turn): no side force, |f| = g / cos(mu), level flight has pitch =
    alpha, and the rates propagate the quaternion (q_{k+1} = q_k exp(omega dt / 2)) to 1e-9."""
    fl = flight(2400, bank_deg={(2.0, 8.0): 30.0})
    k = 1200  # mid-turn, 30 deg bank
    fb = fl["af.f_spec_body"][k]
    assert abs(fb[1]) < 1e-9
    assert np.linalg.norm(fb) == pytest.approx(G0 / math.cos(math.radians(30.0)), rel=1e-12)
    c = dcm(fl["af.quat"][[0]])[0].ravel()
    roll, pitch, yaw = euler_with_error(c, 0.0, 0.0, 0.0)
    assert (roll, pitch, yaw) == pytest.approx((0.0, 0.04, 0.0), abs=1e-12)
    q, w = fl["af.quat"], fl["af.omega_body"]
    for j in (600, 1200, 1900):
        h = 0.5 * (w[j] + w[j + 1]) * DT
        a = np.linalg.norm(h)
        dq = np.concatenate([[math.cos(a / 2)], math.sin(a / 2) * h / a])
        assert np.allclose(_qmul(q[[j]], dq[None])[0], q[j + 1], atol=1e-9)
    # the track turns at g tan(mu) / V
    chi, t = fl["_track"], frame_times(2400)
    assert (chi[1201] - chi[1199]) / (t[1201] - t[1199]) == pytest.approx(
        G0 * math.tan(math.radians(30.0)) / 200.0, rel=1e-9
    )


@pytest.mark.unit
def test_fixture_position_follows_velocity():
    """n = 2,400 frames: latitude advances by the integrated north velocity."""
    fl = flight(2400)
    dlat = fl["af.pos_geo"][-1, 0] - fl["af.pos_geo"][0, 0]
    assert dlat * (R_EARTH + 3000.0) == pytest.approx(
        200.0 * (frame_times(2400)[-1] - frame_times(2400)[0]), rel=1e-12
    )
