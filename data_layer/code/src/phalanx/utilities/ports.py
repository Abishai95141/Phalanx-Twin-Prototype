"""M09 published ports (W1_interfaces.md §2 "M09 Utilities"; catalogue configs/interfaces/w1_ports.yaml).

``ports(n_engines)`` returns ``(inputs, outputs, bindings)``. Outputs are exactly the catalogued ``util.*``
signals. ``bindings`` maps every input port to the catalogue signal it reads. Index maps behind the symbolic
dimensions (tanks ``k``, buses, ECS points, gear legs, ``health.utility`` entries) are in ``layout.py`` and
the README.

``RECORDED`` (AD-42) lists the LRU-computed recorded channels M09 supplies to the recorder (M13
``external=``): extra output ports, in SI, computed by the utility LRUs from M09 truth. Gauged fuel
quantities and totals are not here: the gauge is M12's (AD-42).
"""

from __future__ import annotations

from phalanx.core.module import Port

from .layout import HEALTH_INDEX, N_BUS, N_ECS, N_GEAR, N_HYD, N_TANKS, N_WHEEL

PREFIX = "util"

#: output port -> dictionary channel_id of the LRU-computed recorded channel it supplies (AD-42)
RECORDED = {
    "amagb_speed": "SPS.AMAGB.SPEED",  # utility EU: AMAGB input speed from N2 and the PTO ratio (rad/s)
    "gen_out": "ELEC.GEN.OUT",  # GCU: generator off-line discrete
    "batt_ah": "ELEC.BATT.AH",  # battery display unit: integrated charge from the full mark (C)
    "batt_low": "ELEC.BATT.LOW",  # battery display unit: below the 30 Ah warning level
    "bk_bite": "ELEC.BACKUP.STATUS.BITE",  # 5 kW DC generator GCU BITE: fault latched
    "cabin_alt": "ECS.CABIN_P.CABIN_ALT",  # CPCS: cabin altitude from cabin pressure (ISA, m)
}


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """M09 input and output ports for ``n_engines`` engines (Tejas: 1; proxy mode: 2)."""
    if n_engines < 1:
        raise ValueError("n_engines must be >= 1")
    e = n_engines
    nu = len(HEALTH_INDEX)
    spec_in = (
        ("n2", "rad/s", "<f8", (e,), "eng.n2"),
        ("bleed_p3", "Pa", "<f8", (e,), "eng.bleed_p3"),
        ("bleed_t3", "K", "<f8", (e,), "eng.bleed_t3"),
        ("wf", "kg/s", "<f8", (e,), "eng.wf"),
        ("wf_ab", "kg/s", "<f8", (e,), "eng.wf_ab"),
        ("hyd_flow_demand", "m**3/s", "<f8", (N_HYD,), "fcs.hyd_flow_demand"),
        ("f_spec_body", "m/s**2", "<f8", (3,), "af.f_spec_body"),
        ("tas", "m/s", "<f8", (), "af.tas"),
        ("mach", "1", "<f8", (), "af.mach"),
        ("wow", "1", "<i8", (N_GEAR,), "af.wow"),
        ("wheel_speed", "rad/s", "<f8", (N_WHEEL,), "af.wheel_speed"),
        ("brake_energy_rate", "W", "<f8", (N_WHEEL,), "af.brake_energy_rate"),
        ("t_s", "K", "<f8", (), "env.t_s"),
        ("p_s", "Pa", "<f8", (), "env.p_s"),
        ("rho", "kg/m**3", "<f8", (), "env.rho"),
        ("w_hyd", "m**3/s", "<f8", (N_HYD,), "env.w_hyd"),
        ("w_bleed_pto", "1", "<f8", (e,), "env.w_bleed_pto"),
        ("health_utility", "1", "<f8", (nu,), "health.utility"),
    )
    inputs = tuple(Port(n, u, d, s) for n, u, d, s, _ in spec_in)
    bindings = {n: sig for n, _, _, _, sig in spec_in}
    outputs = (
        Port("hyd_p", "Pa", "<f8", (N_HYD,)),
        Port("hyd_dp_avail", "Pa", "<f8", (N_HYD,)),
        Port("hyd_t", "K", "<f8", (N_HYD,)),
        Port("bleed_extract", "kg/s", "<f8", (e,)),
        Port("pto_power", "W", "<f8", (e,)),
        Port("fuel_mass", "kg", "<f8", (N_TANKS,)),
        Port("mass", "kg", "<f8", ()),
        Port("cg", "m", "<f8", (3,)),
        Port("inertia", "kg*m**2", "<f8", (3, 3)),
        Port("bus_v", "V", "<f8", (N_BUS,)),
        Port("gen_online", "1", "<i8", ()),
        Port("batt_soc", "1", "<f8", ()),
        Port("ecs_t", "K", "<f8", (N_ECS,)),
        Port("ecs_p", "Pa", "<f8", (N_ECS,)),
        Port("brake_t", "K", "<f8", (N_WHEEL,)),
        Port("brake_wear", "1", "<f8", (N_WHEEL,)),
        Port("tyre_wear", "1", "<f8", (N_WHEEL,)),
        Port("jfs_state", "1", "<i8", ()),
        Port("chute_state", "1", "<i8", ()),  # AD-47: 0 stowed, 1 streamed, 2 jettisoned, 3 failed
        Port("fuel_inlet_t", "K", "<f8", (e,)),
        Port("brake_p", "Pa", "<f8", (N_WHEEL,)),
        Port("hyd_res_level", "1", "<f8", (N_HYD,)),
        Port("probe_heat", "1", "<i8", ()),
        # RECORDED (LRU-computed channels; not catalogued truth signals)
        Port("amagb_speed", "rad/s", "<f8", ()),
        Port("gen_out", "1", "<i8", ()),
        Port("batt_ah", "C", "<f8", ()),
        Port("batt_low", "1", "<i8", ()),
        Port("bk_bite", "1", "<i8", ()),
        Port("cabin_alt", "m", "<f8", ()),
    )
    return inputs, outputs, bindings


# Cross-module event protocol (AD-44, configs/interfaces/w1_events.yaml);
# checked by tests/integration/test_event_protocol.py
MODULE_IDS = ("M09",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "util.jfs_start": ("tail",),
    "util.jfs_abort": ("tail",),
    "util.chute_deploy": ("tail", "emergency"),
    "util.chute_jettison": ("tail",),
    "util.fire_extinguish": ("tail",),
    "util.store_release": ("tail", "station"),
    "util.refuel": ("tail", "tank", "target_kg", "t_fuel"),
    "util.fault": ("tail", "mode"),
    "mx.action": ("tail", "action", "mod_id"),
}
