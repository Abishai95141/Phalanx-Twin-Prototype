"""Process assignment of every non-gas-path hidden state (architecture §9.2 "process family per mechanism").

Each ``health.utility`` / ``health.actuator`` state is advanced once per sortie by one process family with one
usage driver and an optional environment multiplier. Rates live in ``configs/tejas/params/M10.yaml``; the
structure (which family, which driver) is the architecture's mechanism table, so it lives here as code.

Drivers (from :class:`~phalanx.health.usage.SortieUsage` and the event clock):

| Driver | Meaning | Unit |
|---|---|---|
| ``fh`` | flight time | s |
| ``eot`` | engine operating time of engine e (engine auxiliaries) | s |
| ``eot_sum`` | engine operating time summed over engines (AMAGB, generator, fuel pump) | s |
| ``days`` | calendar time since the previous sortie event | s |
| ``flights`` | 1 per sortie | count |
| ``landings``, ``gear_cycles``, ``jfs_starts``, ``chute_streamings`` | per sortie | count |
| ``ab_lights`` | AB lights of engine e | count |
| ``brake_l`` / ``brake_r`` | brake energy / reference stop energy (else ``landings``) | reference stops |

Environment multipliers: ``dust``; ``humidity``; ``salt_humidity`` (product); ``contam1`` / ``contam2``
(1 + (factor - 1) x hydraulic contamination, Pall x4); ``cold`` (JFS cold-soak factor).
"""

from __future__ import annotations

from dataclasses import dataclass

from .layout import ACTUATORS


@dataclass(frozen=True)
class Proc:
    """Process assignment of one state.

    family: ``fault`` (no wear process; faults and maintenance only), ``gamma`` (monotone wear, CV at full
    life = component_cv), ``wiener`` (reflecting at 0, drift ∝
    environment), ``wiener_signed`` (zero-drift random walk), ``incubation`` (flat then linear to the limit),
    ``linear`` (deterministic rate, capped at 1), ``counter`` (count / life), ``solder`` (Coffin-Manson per
    flight), ``nz_miner`` (Miner sum over Nz level crossings).
    """

    state: str
    family: str
    driver: str
    rate: str = ""
    sigma: str = ""
    env: str = ""


def _hyd(h: int) -> tuple[Proc, ...]:
    return (
        Proc(f"hyd{h}_pump_wear", "incubation", "days", env=f"contam{h}"),
        Proc(f"hyd{h}_compensator", "wiener_signed", "fh", sigma="hyd_compensator_sigma"),
        Proc(f"hyd{h}_precharge_loss", "gamma", "days", rate="hyd_precharge_rate"),
        Proc(f"hyd{h}_filter_loading", "gamma", "fh", rate="hyd_filter_rate", env=f"contam{h}"),
        Proc(f"hyd{h}_contamination", "wiener", "fh", rate="hyd_contam_drift", sigma="hyd_contam_sigma"),
        Proc(f"hyd{h}_hose_fitting", "gamma", "fh", rate="hyd_hose_rate"),
    )


#: airframe/utility processes, in health.utility order of the airframe block (checked by a test)
AIRFRAME_PROCS: tuple[Proc, ...] = (
    Proc("amagb_wear", "gamma", "eot_sum", rate="amagb_wear_rate"),
    Proc("jfs_health", "gamma", "jfs_starts", rate="jfs_health_rate", env="cold"),
    Proc("batt_fade", "gamma", "days", rate="batt_fade_rate"),
    Proc("gen_health", "gamma", "eot_sum", rate="gen_health_rate"),
    Proc("wiring", "gamma", "fh", rate="wiring_rate", env="humidity"),
    Proc("avionics_solder", "solder", "flights"),
    *(p for h in (1, 2) for p in _hyd(h)[:1]),
    *(p for h in (1, 2) for p in _hyd(h)[1:2]),
    *(p for h in (1, 2) for p in _hyd(h)[2:3]),
    *(p for h in (1, 2) for p in _hyd(h)[3:4]),
    *(p for h in (1, 2) for p in _hyd(h)[4:5]),
    *(p for h in (1, 2) for p in _hyd(h)[5:6]),
    *(Proc(f"act_friction_{a}", "gamma", "fh", rate="act_friction_rate") for a in ACTUATORS),
    Proc("ad_vane_friction_aoa_l", "gamma", "fh", rate="ad_vane_rate"),
    Proc("ad_vane_friction_aoa_r", "gamma", "fh", rate="ad_vane_rate"),
    Proc("ad_vane_friction_aoss", "gamma", "fh", rate="ad_vane_rate"),
    Proc("ad_heater", "gamma", "fh", rate="ad_heater_rate"),
    Proc("fuel_pump_wear", "gamma", "eot_sum", rate="fuel_pump_rate"),
    Proc("fuel_probe_drift", "wiener_signed", "fh", sigma="fuel_probe_sigma"),
    Proc("ecs_hx_fouling", "wiener", "days", rate="ecs_hx_rate", sigma="ecs_hx_sigma", env="dust"),
    Proc("ecs_acm_wear", "gamma", "fh", rate="ecs_acm_rate"),
    Proc("ecs_canopy_seal", "gamma", "fh", rate="ecs_canopy_rate"),
    Proc("lss_obogs_sieve", "gamma", "fh", rate="lss_obogs_rate"),
    Proc("brake_wear_l", "gamma", "brake_l", rate="brake_wear_rate"),
    Proc("brake_wear_r", "gamma", "brake_r", rate="brake_wear_rate"),
    Proc("tyre_wear_l", "gamma", "landings", rate="tyre_wear_rate"),
    Proc("tyre_wear_r", "gamma", "landings", rate="tyre_wear_rate"),
    Proc("tyre_wear_n", "gamma", "landings", rate="tyre_wear_rate_nose"),
    Proc("tyre_p_loss_l", "linear", "days", rate="tyre_leak_rate"),
    Proc("tyre_p_loss_r", "linear", "days", rate="tyre_leak_rate"),
    Proc("tyre_p_loss_n", "linear", "days", rate="tyre_leak_rate"),
    Proc("strut_service_l", "gamma", "landings", rate="strut_rate"),
    Proc("strut_service_r", "gamma", "landings", rate="strut_rate"),
    Proc("strut_service_n", "gamma", "landings", rate="strut_rate"),
    Proc("lock_spring_l", "gamma", "gear_cycles", rate="lock_spring_rate"),
    Proc("lock_spring_r", "gamma", "gear_cycles", rate="lock_spring_rate"),
    Proc("lock_spring_n", "gamma", "gear_cycles", rate="lock_spring_rate"),
    Proc("chute_life", "counter", "chute_streamings", rate="chute_life_streamings"),
    Proc("str_fatigue", "nz_miner", "flights"),
    Proc("str_composite", "gamma", "fh", rate="str_composite_rate"),
    Proc(
        "str_corrosion",
        "wiener",
        "days",
        rate="str_corrosion_rate",
        sigma="str_corrosion_sigma",
        env="salt_humidity",
    ),
    # for the M09 interface (W1.4 HEALTH_INDEX): servo/actuator internal leakage grows with contamination
    # (Pall: servo null leak 3 -> > 20 %); external leaks appear only through faults (fitting/FOHE cracks)
    Proc("hyd1_sys_leak", "gamma", "fh", rate="hyd_sys_leak_rate", env="contam1"),
    Proc("hyd2_sys_leak", "gamma", "fh", rate="hyd_sys_leak_rate", env="contam2"),
    Proc("hyd1_ext_leak", "fault", "fh"),
    Proc("hyd2_ext_leak", "fault", "fh"),
    Proc("jfs_drag", "gamma", "jfs_starts", rate="jfs_drag_rate", env="cold"),
)

#: generic per-engine auxiliary processes (the mechanical ones are advanced by the engine model in module.py)
ENGINE_AUX_PROCS: tuple[Proc, ...] = (
    Proc("vg_offset", "wiener_signed", "eot", sigma="vg_sigma"),
    Proc("ab_spraybar", "gamma", "ab_lights", rate="ab_spraybar_rate"),
    Proc("seal_wear", "gamma", "eot", rate="seal_wear_rate"),
    Proc("fadec_hw", "gamma", "flights", rate="fadec_hw_rate"),
    Proc("nozzle_hw", "gamma", "eot", rate="nozzle_hw_rate"),
)

#: hidden states with no M10 process (owned by another module's dynamics); listed in the catalogue
OWNED_ELSEWHERE: dict[str, str] = {"NM.LG.BRAKE_TEMP": "M09 (brake heat-sink thermal state, util.brake_t)"}
