"""M04 published ports (W1_interfaces.md §2 M04; configs/interfaces/w1_ports.yaml)."""

from __future__ import annotations

from phalanx.core.module import Port

PREFIX = "pilot"
MODULE_IDS = ("M04",)

#: produced cross-module events (AD-44; configs/interfaces/w1_events.yaml): M04 -> M09, flat payloads,
#: scheduled from the sortie plan or the start check / fire-warning hook (module.py docstring)
EVENTS_OUT: dict[str, tuple[str, ...]] = {
    "util.jfs_start": ("tail",),
    "util.jfs_abort": ("tail",),
    "util.chute_deploy": ("tail", "emergency"),
    "util.chute_jettison": ("tail",),
    "util.fire_extinguish": ("tail",),
    "util.store_release": ("tail", "station"),
    # M04 -> M05 (AD-47): FCS reset after a caution (pilot.fcs_caution hook), spin-recovery mode select
    "fcs.reset": ("tail",),
    "fcs.spin_mode": ("tail", "on"),
    # M04 -> M02 (W2.1a take-off fix, A-W2.1-9): the segment in force changed (physically gated progression)
    "pilot.segment": ("tail", "segment", "fine"),
}
EVENTS_IN: dict[str, tuple[str, ...]] = {}


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings). All inputs are previous-frame aircraft states (one-frame delayed
    back-edges in the Gauss-Seidel order environment -> guidance -> FCS -> engine -> airframe)."""
    if n_engines < 1:
        raise ValueError("n_engines >= 1")
    e = n_engines
    inputs = (
        Port("alt", "m"),
        Port("tas", "m/s"),
        Port("mach", "1"),
        Port("vel_ned", "m/s", "<f8", (3,)),
        Port("quat", "1", "<f8", (4,)),
        Port("omega_body", "rad/s", "<f8", (3,)),
        Port("nz", "1"),
        Port("wow", "1", "<i8", (3,)),
        Port("n2", "rad/s", "<f8", (e,)),
    )
    outputs = (
        Port("stick_pitch", "1"),
        Port("stick_roll", "1"),
        Port("pedal", "1"),
        Port("pla", "rad", "<f8", (e,)),
        Port("gear_cmd", "1", "<i8"),
        Port("airbrake_cmd", "1", "<i8"),
        Port("ab_select", "1", "<i8", (e,)),
        Port("brake_cmd", "1", "<f8", (2,)),  # toe brakes L/R 0..1 (AD-47)
        Port("at_engage", "1", "<i8"),
        Port("at_n1_cmd", "1", "<f8", (e,)),
    )
    bindings = {
        "alt": "af.alt",
        "tas": "af.tas",
        "mach": "af.mach",
        "vel_ned": "af.vel_ned",
        "quat": "af.quat",
        "omega_body": "af.omega_body",
        "nz": "af.nz",
        "wow": "af.wow",
        "n2": "eng.n2",
    }
    return inputs, outputs, bindings


def replay_ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...]]:
    _, outs, _ = ports(n_engines)
    return (), outs
