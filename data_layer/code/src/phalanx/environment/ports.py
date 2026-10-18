"""M03 published ports (docs/build_briefs/W1_interfaces.md §2 M03; configs/interfaces/w1_ports.yaml)."""

from __future__ import annotations

from phalanx.core.module import Port

PREFIX = "env"
N_HYD = 2  # Tejas: two 280 bar hydraulic systems (W1_interfaces M05: fcs.hyd_flow_demand (h=2,))


def ports(
    n_engines: int = 1, n_hyd: int = N_HYD
) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings). Inputs from the airframe are one-frame delayed (back-edges, W2.1)."""
    if n_engines < 1 or n_hyd < 0:
        raise ValueError("n_engines >= 1 and n_hyd >= 0")
    inputs = (
        Port("alt", "m"),  # geometric altitude above MSL (af.alt; see README on the catalogue wording)
        Port("hag", "m"),  # height above the local ground (af.hag): shear and low-altitude turbulence
        Port("tas", "m/s"),
        Port("phase", "1", "<i8"),
    )
    outputs = (
        Port("t_s", "K"),
        Port("p_s", "Pa"),
        Port("rho", "kg/m**3"),
        Port("a_sound", "m/s"),
        Port("q_spec", "1"),
        Port("wind_ned", "m/s", "<f8", (3,)),
        Port("turb_vel_body", "m/s", "<f8", (3,)),
        Port("turb_rate_body", "rad/s", "<f8", (3,)),
        Port("w_engine", "1", "<f8", (n_engines, 5)),
        Port("w_bleed_pto", "1", "<f8", (n_engines,)),
        Port("w_hyd", "m**3/s", "<f8", (n_hyd,)),
    )
    bindings = {"alt": "af.alt", "hag": "af.hag", "tas": "af.tas", "phase": "scenario.phase"}
    return inputs, outputs, bindings


def replay_ports(n_engines: int = 1, n_hyd: int = N_HYD) -> tuple[tuple[Port, ...], tuple[Port, ...]]:
    """Proxy-mode replay module: same outputs, no inputs (flight condition comes from the record)."""
    _, outs, _ = ports(n_engines, n_hyd)
    return (), outs
