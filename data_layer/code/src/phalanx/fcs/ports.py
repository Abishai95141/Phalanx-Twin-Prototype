"""M05 published ports (``W1_interfaces.md`` §1-§3, ``configs/interfaces/w1_ports.yaml`` key prefix ``fcs``).

**Sensor lanes** (AD-42, ``W1_interfaces.md`` §3). Every quad/dual sensor the DFCC computes on is an in-loop
lane of M13 (``phalanx.acquisition``): input port ``lane_port(cid)`` (e.g. ``lane_fcs_rsa_q_b``) bound
to ``lane.<channel_id>``, carrying the SI value of the digitised reading as a DFCC-clock sample buffer of
capacity 1 (80 Hz in a 240 Hz step). The DFCC frames on the same clock (``acquisition_clock("DFCC", 80)``), so
a frame falls in exactly the steps where M13 delivers a sample; the companion ``_t``/``_n``/``_first``/``_q``
ports are not bound (the shared clock fixes them). Each lane port declares that clock (:func:`dfcc_clock`, the
clock rule of the conformance gate; AD-36 §8, AD-42), as M08 does with ``fadec_clock()``. Lane conventions
(M12 side):

- ``FCS.RSA.{P,Q,R}``: body rates relative to inertial space, rad/s.
- ``FCS.ASA.NZ``: normal specific force at the ASA, positive **up** (= -f_z), m/s^2; ``FCS.ASA.NY`` positive
  right (= +f_y), m/s^2. ASA station ``x_asa`` = 1 m ahead of the CG reference (M05 design parameter).
- ``AD.AOA_VANE_{L,R}``, ``AD.AOSS_VANE``: local vane angles, rad (the DFCC applies the local-flow
  calibration); ``AD.PS``, ``AD.PT``: static and total pressure, Pa.
- ``FCS.STICK.{PITCH,ROLL}``, ``FCS.PEDAL``: inceptor positions as fractions of full travel (pull / right /
  right pedal positive).
- ``FCS.<surface>.POS``: surface position transducers (rad; airbrakes: stroke, m), lanes A-D on the elevons
  and rudder, A-B on slats and airbrakes.

``AD.TAT`` (single lane) is acquired by the DFCC/ADC but not used by the control laws (the TAS estimate of the
g-limiter uses the ISA temperature at the pressure altitude, A-W1.2-28).

**Discretes and plant-side inputs.** Weight-on-wheels is read from ``af.wow`` (proximity-switch discretes;
not an M12 lane: ``LG.WOW`` is a DFCC-transmitted discrete word); stuck-switch faults enter through the
``fcs.wow_fault`` event. Gear handle and airbrake switch from ``pilot.*``. The actuators are physical devices
loaded by the true aerodynamic hinge moments, so the actuator model (not the DFCC) reads ``af.alpha``,
``af.beta``, ``af.qbar`` (one-frame-delayed back-edges in W2.1), ``util.hyd_dp_avail`` and
``health.actuator``.

**Recorded LRU-computed channels** (AD-42): :data:`RECORDED` maps an output port to the dictionary channel it
supplies to the recorder (M13 ``external=``): voted values, commands, mode/status/BIT words, held at the last
DFCC frame (per truth step). Words are int64, dimensionless. :data:`NOT_MODELLED` lists the DFCC-acquired
computed channels this module does not produce, with the reason.

Surface order of every 13-vector (``surf_pos``, ``surf_rate``): elevon LO, LI, RI, RO; rudder; slats OB_L,
MB_L, IB_L, IB_R, MB_R, OB_R; airbrake L, R (:data:`SURFACE_CHANNELS` maps them to dictionary measurands).
"""

from __future__ import annotations

from functools import cache

from phalanx.acquisition.module import lane_port
from phalanx.core.module import Port
from phalanx.core.time import ClockDomain

PREFIX = "fcs"
N_SURF = 13
LANES = ("A", "B", "C", "D")
LANE_CAP = 1  # DFCC samples per 240 Hz step (80 Hz clock); checked against the clock in Fcs.__init__

SURFACE_CHANNELS = (
    "FCS.ELEVON.LOB",
    "FCS.ELEVON.LIB",
    "FCS.ELEVON.RIB",
    "FCS.ELEVON.ROB",
    "FCS.RUDDER",
    "FCS.SLAT.POS.OB_L",
    "FCS.SLAT.POS.MB_L",
    "FCS.SLAT.POS.IB_L",
    "FCS.SLAT.POS.IB_R",
    "FCS.SLAT.POS.MB_R",
    "FCS.SLAT.POS.OB_R",
    "FCS.AIRBRAKE.POS.L",
    "FCS.AIRBRAKE.POS.R",
)
# FCS.ACT.BIT unit names in fcs.surf_pos order
ACT_BIT_UNITS = (
    "ELEVON_LOB",
    "ELEVON_LIB",
    "ELEVON_RIB",
    "ELEVON_ROB",
    "RUDDER",
    "SLAT_OB_L",
    "SLAT_MB_L",
    "SLAT_IB_L",
    "SLAT_IB_R",
    "SLAT_MB_R",
    "SLAT_OB_R",
    "AIRBRAKE_L",
    "AIRBRAKE_R",
)


def _pos_measurand(s: int) -> str:
    m = SURFACE_CHANNELS[s]
    return m if ".POS." in m else f"{m}.POS"


# (stem, dictionary measurand, SI unit, installed lanes) of the voted signals, in kernel order
VOTED_SIGNALS: tuple[tuple[str, str, str, str], ...] = (
    ("rsa_p", "FCS.RSA.P", "rad/s", "ABCD"),
    ("rsa_q", "FCS.RSA.Q", "rad/s", "ABCD"),
    ("rsa_r", "FCS.RSA.R", "rad/s", "ABCD"),
    ("asa_nz", "FCS.ASA.NZ", "m/s**2", "ABCD"),
    ("asa_ny", "FCS.ASA.NY", "m/s**2", "ABCD"),
    ("aoa_l", "AD.AOA_VANE_L", "rad", "ABCD"),
    ("aoa_r", "AD.AOA_VANE_R", "rad", "ABCD"),
    ("aoss", "AD.AOSS_VANE", "rad", "ABCD"),
    ("ps", "AD.PS", "Pa", "ABCD"),
    ("pt", "AD.PT", "Pa", "ABCD"),
    ("stick_pitch", "FCS.STICK.PITCH", "1", "ABCD"),
    ("stick_roll", "FCS.STICK.ROLL", "1", "ABCD"),
    ("pedal", "FCS.PEDAL", "1", "ABCD"),
    *(
        (
            f"pos_{ACT_BIT_UNITS[s].lower()}",
            _pos_measurand(s),
            "m" if s >= 11 else "rad",
            "ABCD" if s < 5 else "AB",
        )
        for s in range(N_SURF)
    ),
)
N_SIG = len(VOTED_SIGNALS)
SIG_POS0 = 13  # first surface-position signal


def lane_mask(sig: int) -> int:
    """Bit mask (bit c = lane A..D) of the installed lanes of a voted signal."""
    return sum(1 << LANES.index(c) for c in VOTED_SIGNALS[sig][3])


def lane_inputs() -> list[tuple[int, int, str]]:
    """(signal index, lane index, dictionary channel id) of every lane input, in port order."""
    out = []
    for s, (_stem, meas, _unit, lanes) in enumerate(VOTED_SIGNALS):
        for c in lanes:
            out.append((s, LANES.index(c), f"{meas}.{c}"))
    return out


# ---- recorded LRU-computed channels (AD-42) ---------------------------------------------------------------
def rec_port(channel_id: str) -> str:
    """Output port of a recorded computed channel: ``FCS.VOTED.Q`` -> ``rec_fcs_voted_q``."""
    return "rec_" + channel_id.lower().replace(".", "_")


# (channel id, SI unit, dtype, source) in kernel output order; ``source`` is decoded by layout.REC_SOURCES
_REC: tuple[tuple[str, str, str], ...] = (
    *((f"{_pos_measurand(s)}.V", "m" if s >= 11 else "rad", "<f8") for s in range(N_SURF)),
    ("FCS.STICK.PITCH.V", "1", "<f8"),
    ("FCS.STICK.ROLL.V", "1", "<f8"),
    ("FCS.PEDAL.V", "1", "<f8"),
    ("FCS.RSA.P.V", "rad/s", "<f8"),
    ("FCS.RSA.R.V", "rad/s", "<f8"),
    ("FCS.ASA.NY.V", "m/s**2", "<f8"),
    ("FCS.VOTED.Q", "rad/s", "<f8"),
    ("FCS.VOTED.NZ", "m/s**2", "<f8"),
    ("FCS.VOTED.DE", "rad", "<f8"),
    *((f"{SURFACE_CHANNELS[s]}.CMD", "rad", "<f8") for s in range(5)),
    ("FCS.MODE.LAW", "1", "<i8"),
    ("FCS.MODE.FLAGS", "1", "<i8"),
    *((f"FCS.CH.STATUS.{c}", "1", "<i8") for c in LANES),
    *((f"FCS.ACT.BIT.{ACT_BIT_UNITS[s]}", "1", "<i8") for s in range(N_SURF)),
    ("FCS.AIRDATA_MISTRACK", "1", "<i8"),
    ("AV.LRU.BIT.DFCC", "1", "<i8"),
)
REC_CHANNELS: tuple[str, ...] = tuple(c for c, _, _ in _REC)
N_REC = len(_REC)
RECORDED: dict[str, str] = {rec_port(c): c for c in REC_CHANNELS}

NOT_MODELLED: dict[str, str] = {
    "FCS.KALMAN_ATT.PITCH": "no DFCC attitude estimator in the replica (PROXY A-W1.2-29); needs INS/AHRS "
    "inputs that have no owning module yet (AD-42 open item, W2.2)",
    "FCS.KALMAN_ATT.ROLL": "as FCS.KALMAN_ATT.PITCH",
    "FCS.BIT.LOG": "SSS-NNN fault-code log (string codes): an event stream built by M14 from the CH.STATUS / "
    "ACT.BIT / MODE words this module records",
    "AV.RT.STATUS.DFCC": "MIL-STD-1553 RT status word (RT address, message error, busy, flags): bus-level, "
    "owned by the M15 bus encoder",
    "AV.LRU.HEALTH.DFCC.LINK": "avionics LRU health failure codes; code values not defined in the "
    "dictionary (avionics health owner open, AD-42 W2.2)",
    "AV.LRU.HEALTH.DFCC.PORT": "as AV.LRU.HEALTH.DFCC.LINK",
    "AV.LRU.HEALTH.DFCC.MEMORY": "as AV.LRU.HEALTH.DFCC.LINK",
    "AV.SW_CONFIG.DFCC": "software configuration identifier (non-numeric configuration data, M18/M02)",
}


@cache
def dfcc_clock(platform: str = "tejas") -> ClockDomain:
    """The DFCC frame clock: M13's DFCC acquisition clock domain at M05's ``frame_rate`` (AD-42, A-W1.6-21).

    It is the clock of every DFCC lane M13 produces, and :func:`phalanx.fcs.build.build_fcs_config` frames the
    DFCC on the same domain by default, so the declaration and the computation agree (tested)."""
    from phalanx.acquisition.config import acquisition_clock
    from phalanx.dictionary.params import load_params

    sets = load_params("M05", platform=platform).values()
    rates = [s.value("frame_rate") for s in sets if "frame_rate" in s]
    if len(rates) != 1:
        raise ValueError(f"M05 params define frame_rate {len(rates)} times (expected once)")
    return acquisition_clock("DFCC", float(rates[0]), platform=platform)


def ports(
    n_engines: int = 1, *, clock: ClockDomain | None = None
) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """``n_engines`` does not change M05's ports (accepted for the uniform ``ports()`` signature). Lane
    inputs are DFCC-clock sample buffers on ``clock`` (default :func:`dfcc_clock`; an
    :class:`~phalanx.fcs.module.Fcs` instance passes the clock its frame schedule runs on)."""
    if n_engines < 1:
        raise ValueError("n_engines must be >= 1")
    clock = dfcc_clock() if clock is None else clock
    inputs: list[Port] = [
        Port("airbrake_cmd", "1", "<i8", ()),
        Port("gear_cmd", "1", "<i8", ()),
        Port("hyd_dp_avail", "Pa", "<f8", (2,)),
        Port("health_actuator", "1", "<f8", (N_SURF,)),
        Port("alpha", "rad"),
        Port("beta", "rad"),
        Port("qbar", "Pa"),
        Port("wow", "1", "<i8", (3,)),
    ]
    bindings = {
        "airbrake_cmd": "pilot.airbrake_cmd",
        "gear_cmd": "pilot.gear_cmd",
        "hyd_dp_avail": "util.hyd_dp_avail",
        "health_actuator": "health.actuator",
        "alpha": "af.alpha",
        "beta": "af.beta",
        "qbar": "af.qbar",
        "wow": "af.wow",
    }
    for s, _c, cid in lane_inputs():
        name = lane_port(cid)
        inputs.append(Port(name, VOTED_SIGNALS[s][2], "<f8", (LANE_CAP,), clock))
        bindings[name] = f"lane.{cid}"
    outputs = [
        Port("surf_pos", "rad", "<f8", (N_SURF,)),
        Port("surf_rate", "rad/s", "<f8", (N_SURF,)),
        Port("hyd_flow_demand", "m**3/s", "<f8", (2,)),
        Port("law_state", "1", "<i8", ()),
        Port("channel_status", "1", "<i8", (4,)),
    ]
    outputs += [Port(rec_port(c), unit, dt, ()) for c, unit, dt in _REC]
    return tuple(inputs), tuple(outputs), bindings


# Cross-module event protocol (AD-44, configs/interfaces/w1_events.yaml);
# checked by tests/integration/test_event_protocol.py
MODULE_IDS = ("M05",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "fcs.channel_fault": ("tail", "channel", "subsystem", "active"),
    "fcs.actuator_fault": ("tail", "surface", "mode", "active", "channel"),
    "fcs.wow_fault": ("tail", "leg", "value", "active"),
    "fcs.reset": ("tail",),
    "fcs.spin_mode": ("tail", "on"),
    "fcs.pbit_start": ("tail",),
    "fcs.mbit_start": ("tail",),
    "ops.power_up": ("tail_no", "sortie_id", "engine_starts", "cold_soak"),  # PBIT at the engine start (W2.5)
}
