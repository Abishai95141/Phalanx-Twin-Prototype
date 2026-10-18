"""Index maps of the M10 held ports (W1_interfaces.md §2 "M10 Health"; architecture §5.2, §9.1).

Every hidden state that leaves M10 is dimensionless on a port (core ports are SI; these are fractions or
normalised values). Each index of ``health.utility`` and ``health.actuator`` carries a documented
reference so a consumer converts to physical units as ``physical = value * reference`` (e.g. bearing spall
length in metres = value * 0.010 m). ``health.sensor_bias`` is the exception the catalogue documents: one
entry per M12 sensor channel in M12's order (``SensorConfig.bias_index()``, AD-42), in that channel's SI
unit (``sensor_bias_channels``).

The 50 hidden states of ``not_measured_states.csv`` map onto these vectors (``configs/tejas/faults/
hidden_states.yaml`` is the catalogue; ``tests/unit/test_health_catalogue.py`` checks the mapping is
complete).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

#: health.engine columns (W1_interfaces.md; fractional deltas, 0 = nominal build)
ENGINE_DELTAS: tuple[str, ...] = (
    "fan_eta",
    "fan_flow",
    "hpc_eta",
    "hpc_flow",
    "hpt_eta",
    "hpt_flow",
    "lpt_eta",
    "lpt_flow",
    "comb_eta",
    "nozzle_area",
)
FAN_ETA, FAN_FLOW, HPC_ETA, HPC_FLOW, HPT_ETA, HPT_FLOW, LPT_ETA, LPT_FLOW, COMB_ETA, NOZZLE_AREA = range(10)

#: health.actuator order = fcs.surf_pos order (W1_interfaces.md M05)
ACTUATORS: tuple[str, ...] = (
    "elevon_lo",
    "elevon_li",
    "elevon_ri",
    "elevon_ro",
    "rudder",
    "slat_1",
    "slat_2",
    "slat_3",
    "slat_4",
    "slat_5",
    "slat_6",
    "airbrake_l",
    "airbrake_r",
)


@dataclass(frozen=True)
class UtilityEntry:
    """One ``health.utility`` index: name, owning hidden state, reference value and its unit, meaning."""

    name: str
    nm_id: str
    reference: float
    reference_unit: str
    meaning: str


# Per-engine auxiliary states: name template with {e} = engine position 1..n.
_ENGINE_AUX: tuple[tuple[str, str, float, str, str], ...] = (
    ("eng{e}_vg_offset", "NM.ENG.VG_ACTUATION", 0.017453292519943295, "rad", "VG schedule error / 1 deg"),
    ("eng{e}_ab_spraybar", "NM.ENG.AB_SPRAYBAR", 1.0, "1", "AB spray-bar degradation fraction"),
    ("eng{e}_bearing_spall", "NM.ENG.BEARING_SPALL", 0.010, "m", "main-shaft bearing spall length / 10 mm"),
    ("eng{e}_oil_debris", "NM.ENG.BEARING_SPALL", 1.0e-3, "kg", "cumulative oil debris mass / 1 g"),
    ("eng{e}_seal_wear", "NM.ENG.SEAL_WEAR", 9.861111111111111e-08, "m**3/s", "oil leak rate / 0.355 L/h"),
    ("eng{e}_oil_fe", "NM.ENG.OIL_CONDITION", 1.5e-05, "1", "oil Fe mass fraction / 15 ppm"),
    ("eng{e}_blade_crack", "NM.ENG.BLADE_CRACK", 0.010, "m", "HPC/fan blade crack length / 10 mm"),
    ("eng{e}_disk_lcf", "NM.ENG.DISK_LIFE", 1.0, "1", "disk LCF life fraction consumed (Miner)"),
    ("eng{e}_blade_creep", "NM.ENG.BLADE_CREEP", 1.0, "1", "HPT blade creep life fraction consumed"),
    ("eng{e}_tip_clearance", "NM.ENG.TIP_CLEARANCE", 1.0, "1", "rub-in TSFC-equivalent clearance loss"),
    ("eng{e}_fadec_hw", "NM.ENG.FADEC_HW", 1.0, "1", "FADEC electronics aging fraction"),
    ("eng{e}_nozzle_hw", "NM.ENG.NOZZLE_HW", 1.0, "1", "nozzle flap/seal/liner wear fraction"),
    ("eng{e}_fuel_nozzle", "NM.ENG.FUEL_NOZZLE", 1.0, "1", "fuel-nozzle coking fraction"),
)

_AIRFRAME: tuple[tuple[str, str, float, str, str], ...] = (
    ("amagb_wear", "NM.SPS.AMAGB_WEAR", 1.0, "1", "AMAGB gear/bearing wear fraction"),
    ("jfs_health", "NM.SPS.JFS_HEALTH", 1.0, "1", "JFS start-power margin loss fraction"),
    ("batt_fade", "NM.SPS.BATT_SOH", 1.0, "1", "battery capacity fade fraction (EOL 0.30)"),
    ("gen_health", "NM.ELEC.GEN_HEALTH", 1.0, "1", "generator bearing/diode degradation fraction"),
    ("wiring", "NM.ELEC.WIRING", 1.0, "1", "wiring/connector degradation fraction"),
    ("avionics_solder", "NM.AV.SOLDER_FATIGUE", 1.0, "1", "solder-joint fatigue Miner fraction"),
    ("hyd1_pump_wear", "NM.HYD.PUMP_EFF", 1.0, "1", "HYD1 pump volumetric-efficiency loss fraction"),
    ("hyd2_pump_wear", "NM.HYD.PUMP_EFF", 1.0, "1", "HYD2 pump volumetric-efficiency loss fraction"),
    ("hyd1_compensator", "NM.HYD.COMPENSATOR", 1.0, "1", "HYD1 compensator set-point drift fraction"),
    ("hyd2_compensator", "NM.HYD.COMPENSATOR", 1.0, "1", "HYD2 compensator set-point drift fraction"),
    ("hyd1_precharge_loss", "NM.HYD.ACCUM_PRECHARGE", 1.0, "1", "HYD1 accumulator precharge loss fraction"),
    ("hyd2_precharge_loss", "NM.HYD.ACCUM_PRECHARGE", 1.0, "1", "HYD2 accumulator precharge loss fraction"),
    ("hyd1_filter_loading", "NM.HYD.FILTER_LOADING", 1.0, "1", "HYD1 filter loading fraction of capacity"),
    ("hyd2_filter_loading", "NM.HYD.FILTER_LOADING", 1.0, "1", "HYD2 filter loading fraction of capacity"),
    ("hyd1_contamination", "NM.HYD.FLUID_CONTAM", 1.0, "1", "HYD1 contamination / class limit"),
    ("hyd2_contamination", "NM.HYD.FLUID_CONTAM", 1.0, "1", "HYD2 contamination / class limit"),
    ("hyd1_hose_fitting", "NM.HYD.HOSE_FITTING", 1.0, "1", "HYD1 hose/fitting fatigue fraction"),
    ("hyd2_hose_fitting", "NM.HYD.HOSE_FITTING", 1.0, "1", "HYD2 hose/fitting fatigue fraction"),
    *(
        (f"act_friction_{a}", "NM.FCS.ACTUATOR_FRICTION", 1.0, "1", f"{a} actuator friction growth fraction")
        for a in ACTUATORS
    ),
    ("ad_vane_friction_aoa_l", "NM.AD.VANE_FRICTION", 1.0, "1", "left AoA vane friction growth fraction"),
    ("ad_vane_friction_aoa_r", "NM.AD.VANE_FRICTION", 1.0, "1", "right AoA vane friction growth fraction"),
    ("ad_vane_friction_aoss", "NM.AD.VANE_FRICTION", 1.0, "1", "AoSS vane friction growth fraction"),
    ("ad_heater", "NM.AD.HEATER_ELEMENT", 1.0, "1", "probe/vane heater degradation fraction"),
    ("fuel_pump_wear", "NM.FUEL.PUMP_WEAR", 1.0, "1", "boost/transfer pump wear fraction"),
    ("fuel_probe_drift", "NM.FUEL.PROBE_DRIFT", 1.0, "1", "gauged-quantity bias, fraction of quantity"),
    ("ecs_hx_fouling", "NM.ECS.HX_FOULING", 1.0, "1", "ECS heat-exchanger fouling (effectiveness loss)"),
    ("ecs_acm_wear", "NM.ECS.ACM_WEAR", 1.0, "1", "ACM bearing wear fraction"),
    ("ecs_canopy_seal", "NM.ECS.CANOPY_SEAL", 1.0, "1", "canopy-seal leak growth fraction"),
    ("lss_obogs_sieve", "NM.LSS.OBOGS_SIEVE", 1.0, "1", "OBOGS sieve degradation fraction"),
    ("brake_wear_l", "NM.LG.BRAKE_WEAR", 1.0, "1", "left brake heat-sink wear fraction"),
    ("brake_wear_r", "NM.LG.BRAKE_WEAR", 1.0, "1", "right brake heat-sink wear fraction"),
    ("tyre_wear_l", "NM.LG.TYRE", 1.0, "1", "left main tyre tread wear fraction"),
    ("tyre_wear_r", "NM.LG.TYRE", 1.0, "1", "right main tyre tread wear fraction"),
    ("tyre_wear_n", "NM.LG.TYRE", 1.0, "1", "nose tyre tread wear fraction"),
    ("tyre_p_loss_l", "NM.LG.TYRE", 1.0, "1", "left main tyre pressure loss fraction since service"),
    ("tyre_p_loss_r", "NM.LG.TYRE", 1.0, "1", "right main tyre pressure loss fraction since service"),
    ("tyre_p_loss_n", "NM.LG.TYRE", 1.0, "1", "nose tyre pressure loss fraction since service"),
    ("strut_service_l", "NM.LG.STRUT_SERVICE", 1.0, "1", "left main strut gas/oil loss fraction"),
    ("strut_service_r", "NM.LG.STRUT_SERVICE", 1.0, "1", "right main strut gas/oil loss fraction"),
    ("strut_service_n", "NM.LG.STRUT_SERVICE", 1.0, "1", "nose strut gas/oil loss fraction"),
    ("lock_spring_l", "NM.LG.LOCK_SPRING", 1.0, "1", "left main lock-spring relaxation fraction"),
    ("lock_spring_r", "NM.LG.LOCK_SPRING", 1.0, "1", "right main lock-spring relaxation fraction"),
    ("lock_spring_n", "NM.LG.LOCK_SPRING", 1.0, "1", "nose lock-spring relaxation fraction"),
    ("chute_life", "NM.LG.CHUTE", 1.0, "1", "brake-chute life fraction (streamings / life)"),
    ("str_fatigue", "NM.STR.FATIGUE", 1.0, "1", "structural fatigue damage, Miner fraction"),
    ("str_composite", "NM.STR.COMPOSITE", 1.0, "1", "composite delamination area fraction"),
    ("str_corrosion", "NM.STR.CORROSION_WATER", 1.0, "1", "corrosion / water-ingress fraction"),
    # appended for the M09 interface (W1.4 HEALTH_INDEX); appended so earlier per-state draws are unchanged
    ("hyd1_sys_leak", "NM.HYD.ACTUATOR_LEAK", 1.0, "1", "HYD1 excess internal (servo) leakage conductance"),
    ("hyd2_sys_leak", "NM.HYD.ACTUATOR_LEAK", 1.0, "1", "HYD2 excess internal (servo) leakage conductance"),
    ("hyd1_ext_leak", "NM.HYD.HOSE_FITTING", 1.0, "1", "HYD1 external leak conductance / rated pump flow"),
    ("hyd2_ext_leak", "NM.HYD.HOSE_FITTING", 1.0, "1", "HYD2 external leak conductance / rated pump flow"),
    ("jfs_drag", "NM.SPS.JFS_HEALTH", 1.0, "1", "JFS spool drag excess, fraction"),
)


@lru_cache(maxsize=8)
def hidden_entries(n_engines: int = 1) -> tuple[UtilityEntry, ...]:
    """The M10 hidden-state inventory beyond the engine deltas and actuators: per-engine auxiliaries first
    (engine-major), then the airframe block. Labels report every entry; ``health.utility`` exports the subset
    M09 consumes (:func:`utility_entries`)."""
    if n_engines < 1:
        raise ValueError("n_engines must be >= 1")
    out = [
        UtilityEntry(name.format(e=e), nm, ref, unit, meaning)
        for e in range(1, n_engines + 1)
        for (name, nm, ref, unit, meaning) in _ENGINE_AUX
    ]
    out += [UtilityEntry(*row) for row in _AIRFRAME]
    names = [u.name for u in out]
    if len(set(names)) != len(names):
        raise AssertionError("duplicate utility names")
    return tuple(out)


def hidden_index(n_engines: int = 1) -> dict[str, int]:
    """name -> index of the hidden-state inventory (:func:`hidden_entries`)."""
    return {u.name: i for i, u in enumerate(hidden_entries(n_engines))}


#: clip of exported loss fractions M09 requires in [0, 1)
FRAC_MAX = 0.999
#: ``health.utility`` entry -> (M10 airframe state, scale parameter or "", upper clip or None). The entries
#: and their order are M09's ``phalanx.utilities.layout.HEALTH_INDEX`` (W1.4, adopted by the coordinator);
#: scales convert an M10 wear fraction (1 = the replacement limit) into M09's physical meaning (A-W1.5-28).
UTILITY_SOURCES: dict[str, tuple[str, str, float | None]] = {
    **{f"hyd_pump_leak_{h}": (f"hyd{h + 1}_pump_wear", "pump_leak_at_limit", None) for h in (0, 1)},
    **{f"hyd_sys_leak_{h}": (f"hyd{h + 1}_sys_leak", "", None) for h in (0, 1)},
    **{f"hyd_ext_leak_{h}": (f"hyd{h + 1}_ext_leak", "", None) for h in (0, 1)},
    **{f"hyd_comp_drift_{h}": (f"hyd{h + 1}_compensator", "", None) for h in (0, 1)},
    **{f"hyd_filter_load_{h}": (f"hyd{h + 1}_filter_loading", "", FRAC_MAX) for h in (0, 1)},
    **{f"hyd_precharge_loss_{h}": (f"hyd{h + 1}_precharge_loss", "", FRAC_MAX) for h in (0, 1)},
    "ecs_hx_fouling": ("ecs_hx_fouling", "", 1.0),
    "ecs_cabin_leak": ("ecs_canopy_seal", "", None),
    "batt_fade": ("batt_fade", "", FRAC_MAX),
    "jfs_power_loss": ("jfs_health", "", FRAC_MAX),
    "jfs_drag_excess": ("jfs_drag", "", None),
    "amagb_wear": ("amagb_wear", "amagb_loss_at_limit", None),
    "brake_wear_0": ("brake_wear_l", "", 1.0),
    "brake_wear_1": ("brake_wear_r", "", 1.0),
    "tyre_wear_0": ("tyre_wear_l", "", 1.0),
    "tyre_wear_1": ("tyre_wear_r", "", 1.0),
    "fuel_xfer_loss": ("fuel_pump_wear", "xfer_loss_at_limit", FRAC_MAX),
}


@lru_cache(maxsize=8)
def utility_entries(n_engines: int = 1) -> tuple[UtilityEntry, ...]:
    """The ``health.utility`` port index map: M09's ``HEALTH_INDEX`` (23 dimensionless entries, the same for
    any engine count), each with the M10 hidden state it is computed from."""
    from phalanx.utilities.layout import HEALTH_INDEX

    if set(HEALTH_INDEX) != set(UTILITY_SOURCES):
        raise AssertionError("health.utility sources do not match M09's HEALTH_INDEX")
    nm = {row[0]: row[1] for row in _AIRFRAME}
    out = []
    for name in HEALTH_INDEX:
        src, scale, clip = UTILITY_SOURCES[name]
        how = f"M10 {src}" + (f" x {scale}" if scale else "") + (f", clipped to {clip}" if clip else "")
        out.append(UtilityEntry(name, nm[src], 1.0, "1", how))
    return tuple(out)


def utility_index(n_engines: int = 1) -> dict[str, int]:
    """name -> index of ``health.utility``."""
    return {u.name: i for i, u in enumerate(utility_entries(n_engines))}


N_ENGINE_AUX = len(_ENGINE_AUX)
ENGINE_AUX_NAMES: tuple[str, ...] = tuple(n.replace("eng{e}_", "") for n, *_ in _ENGINE_AUX)


def engine_aux_slice(e: int) -> slice:
    """Slice of the hidden-state inventory holding engine ``e``'s (0-based) auxiliary states."""
    return slice(e * N_ENGINE_AUX, (e + 1) * N_ENGINE_AUX)


AIRFRAME_NAMES: tuple[str, ...] = tuple(r[0] for r in _AIRFRAME)


# ------------------------------------------------------------------------------------- sensor-bias channels
@dataclass(frozen=True)
class BiasChannel:
    """One ``health.sensor_bias`` entry: a physical sensor channel and the SI unit of its bias."""

    channel_id: str
    si_units: str
    quantity: str
    eu_units: str
    eu_span: float  # full-scale span in EU (range max - range min)
    eu_scale: float  # si = eu * scale + offset  (bias scales with ``scale`` only)
    eu_min: float = 0.0
    eu_offset: float = 0.0

    @property
    def span_si(self) -> float:
        return self.eu_span * self.eu_scale

    @property
    def rails_si(self) -> tuple[float, float]:
        """(low, high) range ends in SI (open/short sensor-fault rails)."""
        lo = self.eu_min * self.eu_scale + self.eu_offset
        return lo, lo + self.span_si


#: Physical sensor channels of the dictionary (single or lane readings of analog or frequency sensors). Only
#: those M12 models carry a bias (see :func:`excluded_bias_channels`).
BIAS_ROLES = frozenset({"single", "lane"})
BIAS_SIGNALS = frozenset({"analog", "frequency"})


def sensor_bias_channels(dictionary, sensor_config=None) -> tuple[BiasChannel, ...]:
    """The ``health.sensor_bias`` index map (AD-42): M12's channel order, ``SensorConfig.bias_index()``.

    Entry ``i`` is the installation bias + aging of channel ``bias_index()[i]`` in that channel's SI unit (the
    unit M12 adds it in). ``sensor_config`` defaults to ``build_sensor_config(dictionary)``; pass the M12
    configuration of the run when it is built on a channel subset.
    """
    if sensor_config is None:
        from phalanx.sensors.config import build_sensor_config

        key = dictionary.dict_hash
        hit = _BIAS_CACHE.get(key)
        if hit is not None:
            return hit
        sensor_config = build_sensor_config(dictionary)
    else:
        key = None
    out = tuple(_bias_channel(dictionary, cid) for cid in sensor_config.bias_index())
    for b, u in zip(out, sensor_config.si_units, strict=True):
        if b.si_units != u:
            raise ValueError(f"{b.channel_id}: dictionary SI unit {b.si_units!r} != M12 unit {u!r}")
    if key is not None:
        _BIAS_CACHE[key] = out
    return out


def excluded_bias_channels(dictionary) -> tuple[str, ...]:
    """Physical sensor channels of the dictionary that M12 does not model, so they carry no bias (sorted).

    They join the index map when M12 models them (sensors README, "Known limitations")."""
    have = {b.channel_id for b in sensor_bias_channels(dictionary)}
    return tuple(
        sorted(
            c["channel_id"]
            for c in dictionary.channels()
            if c["role"] in BIAS_ROLES and c["signal"] in BIAS_SIGNALS and c["channel_id"] not in have
        )
    )


_BIAS_CACHE: dict[str, tuple[BiasChannel, ...]] = {}


def _bias_channel(dictionary, cid: str) -> BiasChannel:
    # an engine instance of an engine-indexed channel (M12 at n_engines > 1, ``ENG.N1.A:E2``) carries the
    # dictionary channel's units and range (W2.4a-1 U3)
    from phalanx.sensors.config import dictionary_id

    did = dictionary_id(cid)
    c = dictionary.channel(did)
    conv = dictionary.eu_conversion(did)
    rng = c.get("range") or {}
    lo, hi = rng.get("min"), rng.get("max")
    span = float(hi - lo) if lo is not None and hi is not None else 0.0
    return BiasChannel(
        cid,
        conv.si_units,
        c["quantity"],
        c["units"],
        span,
        float(conv.scale),
        float(lo) if lo is not None else 0.0,
        float(conv.offset),
    )


def check_names(names: Sequence[str]) -> None:
    if len(set(names)) != len(names):
        raise ValueError("duplicate names")
