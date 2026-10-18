"""M06 published ports (``W1_interfaces.md`` §2, ``configs/interfaces/w1_ports.yaml`` key prefix ``af``).

Conventions on the outputs (also in ``airframe/README.md``):

- ``pos_geo`` = (geodetic latitude rad, longitude rad, height above the WGS-84 ellipsoid m): mixed units,
  so the port unit is ``"1"`` as catalogued; ``alt`` = the same height in m (geoid undulation ignored,
  A-W1.2-2).
- ``vel_ned`` = velocity relative to the Earth, NED axes. ``quat`` = body -> NED quaternion (scalar first).
- ``omega_body`` = body angular rate relative to inertial space (what the RSA gyros measure), body axes.
- ``f_spec_body`` = specific force at the CG (aero + thrust + ground + chute) / mass, body axes (what an
  accelerometer at the CG measures). ``nz = -f_spec_body[2] / g0`` (positive up; 1 in level flight).
- ``alpha``, ``beta``, ``tas``, ``mach``, ``qbar`` from the air-relative velocity (wind and turbulence
  removed).
- ``wow`` (nose, left main, right main) = 1 when the strut compression exceeds the switch threshold.
- ``wheel_speed`` (left, right main), ``brake_energy_rate`` (left, right main) = power absorbed by each brake.
- ``hag`` = height of the CG above the local ground elevation (``af.ground_elevation`` event), m: the radar
  altitude truth (M12 applies the antenna lever arm and attitude; AD-42 catalogue addition).

Inputs bind to catalogued signals only. ``gear_cmd`` reads ``pilot.gear_cmd`` (undercarriage handle): an
additive binding not listed among the M06 inputs in ``W1_interfaces.md`` §2 (reported to the coordinator).
"""

from __future__ import annotations

from phalanx.core.module import Port

PREFIX = "af"
N_SURF = 13


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    if n_engines < 1:
        raise ValueError("n_engines must be >= 1")
    inputs = (
        Port("surf_pos", "rad", "<f8", (N_SURF,)),
        Port("thrust", "N", "<f8", (n_engines,)),
        Port("mass", "kg"),
        Port("cg", "m", "<f8", (3,)),
        Port("inertia", "kg*m**2", "<f8", (3, 3)),
        Port("rho", "kg/m**3"),
        Port("a_sound", "m/s"),
        Port("t_s", "K"),
        Port("wind_ned", "m/s", "<f8", (3,)),
        Port("turb_vel_body", "m/s", "<f8", (3,)),
        Port("turb_rate_body", "rad/s", "<f8", (3,)),
        Port("gear_cmd", "1", "<i8", ()),
        Port("brake_cmd", "1", "<f8", (2,)),  # AD-47: toe brakes L/R 0..1
        Port("chute_state", "1", "<i8", ()),  # AD-47: M09 chute state (1 = streamed)
        Port("hyd_p", "Pa", "<f8", (2,)),  # AD-47: brake supply (gauge; system brake_hyd_system)
    )
    bindings = {
        "surf_pos": "fcs.surf_pos",
        "thrust": "eng.thrust",
        "mass": "util.mass",
        "cg": "util.cg",
        "inertia": "util.inertia",
        "rho": "env.rho",
        "a_sound": "env.a_sound",
        "t_s": "env.t_s",
        "wind_ned": "env.wind_ned",
        "turb_vel_body": "env.turb_vel_body",
        "turb_rate_body": "env.turb_rate_body",
        "gear_cmd": "pilot.gear_cmd",
        "brake_cmd": "pilot.brake_cmd",
        "chute_state": "util.chute_state",
        "hyd_p": "util.hyd_p",
    }
    outputs = (
        Port("pos_geo", "1", "<f8", (3,)),
        Port("alt", "m"),
        Port("vel_ned", "m/s", "<f8", (3,)),
        Port("quat", "1", "<f8", (4,)),
        Port("omega_body", "rad/s", "<f8", (3,)),
        Port("f_spec_body", "m/s**2", "<f8", (3,)),
        Port("alpha", "rad"),
        Port("beta", "rad"),
        Port("tas", "m/s"),
        Port("mach", "1"),
        Port("qbar", "Pa"),
        Port("nz", "1"),
        Port("wow", "1", "<i8", (3,)),
        Port("wheel_speed", "rad/s", "<f8", (2,)),
        Port("brake_energy_rate", "W", "<f8", (2,)),
        Port("hag", "m"),
    )
    return inputs, outputs, bindings


#: the recorded flight condition a proxy-mode replay serves in place of the airframe (W2.4a U4)
REPLAY_OUTPUTS = ("alt", "tas", "mach")


def replay_ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...]]:
    """Proxy-mode replay (architecture §14.3; W2.4a U4, ``phalanx.proxy.replay.AirframeReplay``): the airframe
    is not simulated, and only the recorded flight condition ``alt``, ``tas`` and ``mach`` is served from the
    DASHlink record. A **partial** publication: the other ``af`` signals stay a labelled boundary of the
    proxy chain."""
    _, outs, _ = ports(n_engines)
    return (), tuple(q for q in outs if q.name in REPLAY_OUTPUTS)


# Cross-module event protocol (AD-44, configs/interfaces/w1_events.yaml);
# checked by tests/integration/test_event_protocol.py. AD-47 (W2.1c): brakes and chute are the ports
# `pilot.brake_cmd` and `util.chute_state` (the W1 `af.brake` / `af.chute` test hooks are retired).
MODULE_IDS = ("M06",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "af.ground_elevation": ("tail", "h"),
    # AD-48.4: M11's physical fault injection, a ground-model state perturbation per gear leg (module.py)
    "af.fault_inject": ("tail", "mode", "param", "instance", "engine", "clear", "leg"),
}
