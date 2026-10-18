"""M07 published ports (W1_interfaces.md §2 M07; catalogue ``configs/interfaces/w1_ports.yaml``).

Every engine-side port carries a leading ``e`` (n_engines) axis; aircraft-level inlet conditions are scalars
shared by the engines. Units are SI (AD-36). ``bindings`` maps each input port to the catalogue signal it
reads (W2.1 builds the wiring from it).

Semantics worth knowing at integration:
- ``wf`` is the metered main fuel flow downstream of the metering valve, including the fuel-metering process
  disturbance (what a flowmeter sees); the combustor receives it after the transport delay.
- ``t5`` is the LPT-exit (T56 plane) total temperature truth; M12 models the harness.
- ``ps3`` is the HPC-exit static pressure; ``bleed_p3``/``bleed_t3`` are the stage-7 customer-bleed port total
  conditions (HPC exit).
- ``vib_src`` bands: [N1 1/rev, N2 1/rev, broadband] acceleration amplitudes (m/s^2).
- ``stall_margin`` is min(fan, HPC) constant-speed margin to the map stall line, (PR_stall/PR - 1).
- ``ab_state``: 0 off, 1 lighting (pilot fuel, igniters), 2 lit. ``flame_state``: main burner 0 out, 1 lit.
- ``w_engine`` columns (AD-32, AD-46; A-W1.3a-15), dimensionless fractional perturbations that act on the
  dynamics: ``fuel_metering`` multiplies the metered main fuel flow; ``combustor_eff`` the main-burner
  efficiency; ``inlet_recovery`` P2; ``shaft_load`` the HP-spool HPC + accessory load torque (1 % is about
  200 kW at MIL); ``fan_face`` (fan-face distortion, > 0 = more distortion) lowers the fan flow capacity by
  that fraction and the fan efficiency by ``k_eta_fan_face`` times it.
- ``pto_power`` (W) is power taken off the HP spool through the AMAGB; **negative = starter drive** (M09
  JFS). M07 converts it to torque as ``T = P / (N2 + 1 rad/s)``, the M09 start-drive convention
  (``P = min(P_avail, T_peak (w + w_floor))``), so a starter can turn a stopped spool.
- ``fuel_inlet_t`` (K): engine fuel inlet temperature from M09, the fuel-oil cooler sink of the oil model.
- ``health`` columns: [fan_eta, fan_flow, hpc_eta, hpc_flow, hpt_eta, hpt_flow, lpt_eta, lpt_flow, comb_eta,
  nozzle_area] fractional deltas (0 = nominal build).
"""

from __future__ import annotations

from phalanx.core.module import Port

from .layout import N_HEALTH, N_VIB_BANDS, N_W_ENGINE

PREFIX = "eng"

# output port name -> unit (catalogue order); vib_src and the int ports are handled separately
_FLOAT_OUTPUTS = (
    ("n1", "rad/s"),
    ("n2", "rad/s"),
    ("t2", "K"),
    ("t25", "K"),
    ("t3", "K"),
    ("t5", "K"),
    ("p2", "Pa"),
    ("ps3", "Pa"),
    ("p5", "Pa"),
    ("wf", "kg/s"),
    ("wf_ab", "kg/s"),
    ("a8", "m**2"),
    ("vg_igv", "rad"),
    ("vg_vsv", "rad"),
    ("w2", "kg/s"),
    ("thrust", "N"),
    ("oil_t", "K"),
    ("oil_p", "Pa"),
)
_TAIL_FLOAT_OUTPUTS = (("stall_margin", "1"), ("bleed_p3", "Pa"), ("bleed_t3", "K"))
INT_OUTPUTS = ("ab_state", "flame_state")

BINDINGS = {
    "wf_cmd": "fadec.wf_cmd",
    "wf_ab_cmd": "fadec.wf_ab_cmd",
    "a8_cmd": "fadec.a8_cmd",
    "vg_cmd": "fadec.vg_cmd",
    "ignition": "fadec.ignition",
    "ab_enable": "fadec.ab_enable",
    "t_s": "env.t_s",
    "p_s": "env.p_s",
    "q_spec": "env.q_spec",
    "mach": "af.mach",
    "w_engine": "env.w_engine",
    "bleed_extract": "util.bleed_extract",
    "pto_power": "util.pto_power",
    "fuel_inlet_t": "util.fuel_inlet_t",
    "health": "health.engine",
}


# Cross-module event protocol (AD-44, configs/interfaces/w1_events.yaml): M07 consumes the physical fault
# injection of M11 (AD-48.4; handler ``EngineModule.on_event``, realisation ``phalanx.engine.faults``)
MODULE_IDS = ("M07",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "eng.fault_inject": ("tail", "mode", "param", "instance", "engine", "clear"),
}


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings) for ``n_engines`` engines."""
    if n_engines < 1:
        raise ValueError("n_engines must be >= 1")
    e = (n_engines,)
    outs = [Port(n, u, "<f8", e) for n, u in _FLOAT_OUTPUTS]
    outs.append(Port("vib_src", "m/s**2", "<f8", (n_engines, N_VIB_BANDS)))
    outs += [Port(n, u, "<f8", e) for n, u in _TAIL_FLOAT_OUTPUTS]
    outs += [Port(n, "1", "<i8", e) for n in INT_OUTPUTS]
    ins = (
        Port("wf_cmd", "kg/s", "<f8", e),
        Port("wf_ab_cmd", "kg/s", "<f8", e),
        Port("a8_cmd", "m**2", "<f8", e),
        Port("vg_cmd", "rad", "<f8", (n_engines, 2)),
        Port("ignition", "1", "<i8", e),
        Port("ab_enable", "1", "<i8", e),
        Port("t_s", "K"),
        Port("p_s", "Pa"),
        Port("q_spec", "1"),
        Port("mach", "1"),
        Port("w_engine", "1", "<f8", (n_engines, N_W_ENGINE)),
        Port("bleed_extract", "kg/s", "<f8", e),
        Port("pto_power", "W", "<f8", e),
        Port("fuel_inlet_t", "K", "<f8", e),
        Port("health", "1", "<f8", (n_engines, N_HEALTH)),
    )
    return ins, tuple(outs), dict(BINDINGS)
