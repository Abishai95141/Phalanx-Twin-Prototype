"""Avionics configuration: ``M12_AVIONICS.yaml`` (+ the M12 air-data tables the ADC corrects with) -> kernel
vectors, the channel maps and the DFCC acquisition clock.

Nothing here invents a number: every kernel parameter is read from ``M12_AVIONICS.yaml`` (provenance per
entry) or, for the ADC's nominal correction tables, from the M12 parameter sets of the sensors the ADC reads
(``static_pressure``, ``vane_aoa``, ``vane_aoss``, ``tat_probe``): the ADC corrects with the calibration of
the installed probes (A-W2.2-6). Bus indices are checked against M09's published bus map.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from phalanx.core.module import ContractError, Param, ParamSet
from phalanx.core.time import ClockDomain
from phalanx.dictionary.params import load_params

from . import adc as A
from . import ahrs as H
from . import ins as N
from . import radalt as R

MODULE = "M12_AVIONICS"
#: LRU order of the power blocks and their M12_AVIONICS.yaml bus parameter
POWER_LRUS = ("INGPS", "AHRS", "RADALT", "SMS")
_BUS_PARAM = {"INGPS": "bus_ingps", "AHRS": "bus_ahrs", "RADALT": "bus_radalt", "SMS": "bus_sms"}
N_STATIONS = 9


@dataclass(frozen=True)
class AvionicsConfig:
    """Flat kernel vectors (read-only) and maps of the avionics extension."""

    platform: str
    ins_p: np.ndarray
    fom_bounds: np.ndarray
    ahrs_p: np.ndarray
    radalt_p: np.ndarray
    radalt_scale_sigma: float
    radalt_offset_sigma: float
    adc_p: np.ndarray
    adc_tables: tuple[np.ndarray, ...]  # pe_m, pe_k, vb_m, vb_b, sb_m, sb_b, rc_m, rc_r, dh_z, dh_e
    bus: Mapping[str, int]
    sms_p_hung: float
    n_sub: int
    dfcc_clock: ClockDomain
    params: ParamSet  # one ParamSet covering every number above (module config hash)


def _vec(ps: ParamSet, names: tuple[str, ...]) -> np.ndarray:
    out = np.array([float(ps.value(n)) for n in names], dtype=np.float64)
    out.flags.writeable = False
    return out


def _ro(a) -> np.ndarray:
    v = np.array(a, dtype=np.float64)
    v.flags.writeable = False
    return v


def build_avionics_config(
    *,
    platform: str = "tejas",
    params: Mapping[str, ParamSet] | None = None,
    m12_params: Mapping[str, ParamSet] | None = None,
    config_root: Path | None = None,
) -> AvionicsConfig:
    """Build the avionics configuration (``params`` / ``m12_params`` override the files: tests, sweeps)."""
    from phalanx.acquisition.config import acquisition_clock
    from phalanx.utilities.layout import BUSES

    p = (
        dict(params)
        if params is not None
        else load_params(MODULE, platform=platform, config_root=config_root)
    )
    m12 = (
        dict(m12_params)
        if m12_params is not None
        else load_params("M12", platform=platform, config_root=config_root)
    )
    k, pw, ins, ahrs, adc, rad = p["constants"], p["power"], p["ins"], p["ahrs"], p["adc"], p["radalt"]
    power = (float(pw.value("v_dropout")), float(pw.value("t_holdup")))
    ins_p = np.array(
        [
            ins.value("gyro_bias_sigma"),
            ins.value("gyro_gm_sigma"),
            ins.value("gyro_gm_tau"),
            ins.value("gyro_arw"),
            ins.value("accel_bias_sigma"),
            ins.value("accel_gm_sigma"),
            ins.value("accel_gm_tau"),
            ins.value("accel_noise"),
            ins.value("gps_sigma_h"),
            float(ins.value("gps_sigma_h")) * float(ins.value("gps_sigma_v_ratio")),
            ins.value("gps_tau"),
            ins.value("gps_vel_sigma"),
            ins.value("gps_vel_tau"),
            ins.value("aid_pos_tau"),
            ins.value("aid_vel_tau"),
            ins.value("baro_tau"),
            ins.value("tilt_tau"),
            ins.value("heading_tau"),
            ins.value("t_align"),
            ins.value("t_gps_reacq"),
            ins.value("cep_rate"),
            ins.value("nb_wn"),
            ins.value("nb_zeta"),
            ins.value("wb_wn"),
            ins.value("wb_zeta"),
            ins.value("acc_wn"),
            ins.value("acc_zeta"),
            k.value("g0"),
            k.value("earth_radius"),
            k.value("earth_rate"),
            *power,
        ],
        dtype=np.float64,
    )
    if ins_p.size != N.N_P:
        raise ContractError("INS parameter vector layout drifted from ins.N_P")
    fom = np.asarray(ins.value("fom_bounds"), dtype=np.float64)
    if fom.shape != (N.N_FOM,) or np.any(np.diff(fom) <= 0):
        raise ContractError(f"ins.fom_bounds must be {N.N_FOM} increasing values")
    ahrs_p = np.array(
        [
            ahrs.value("gyro_bias_sigma"),
            ahrs.value("gyro_gm_sigma"),
            ahrs.value("gyro_gm_tau"),
            ahrs.value("gyro_arw"),
            ahrs.value("accel_bias_sigma"),
            ahrs.value("erect_tau"),
            ahrs.value("erect_cut_g"),
            ahrs.value("erect_cut_rate"),
            ahrs.value("slave_tau"),
            ahrs.value("mag_declination"),
            ahrs.value("mag_dev_b"),
            ahrs.value("mag_dev_c"),
            k.value("g0"),
            *power,
        ],
        dtype=np.float64,
    )
    if ahrs_p.size != H.N_P:
        raise ContractError("AHRS parameter vector layout drifted from ahrs.N_P")
    radalt_p = np.array(
        [
            rad.value("h_max"),
            rad.value("beam_half"),
            rad.value("track_max_tilt"),
            rad.value("terrain_sigma"),
            rad.value("terrain_length"),
            rad.value("terrain_cell"),
            rad.value("track_tau"),
            *power,
        ],
        dtype=np.float64,
    )
    if radalt_p.size != R.N_P:
        raise ContractError("radar-altimeter parameter vector layout drifted from radalt.N_P")
    dfcc = acquisition_clock("DFCC", 80.0, platform=platform, config_root=config_root)
    adc_p = np.array(
        [
            adc.value("gear_dk_ps"),
            adc.value("gear_dalpha_vane"),
            adc.value("gear_resid"),
            adc.value("gear_transit"),
            adc.value("hdot_tau"),
            adc.value("qnh"),
            adc.value("thr_pressure"),
            adc.value("thr_vane"),
            adc.value("tat_min"),
            k.value("p0"),
            k.value("t0"),
            k.value("lapse"),
            k.value("h_trop"),
            k.value("r_air"),
            k.value("gamma"),
            k.value("g0"),
            k.value("rho0"),
            m12["vane_aoa"].value("ku"),
            m12["vane_aoss"].value("ku"),
            1.0 / float(dfcc.f_nom_hz),
        ],
        dtype=np.float64,
    )
    if adc_p.size != A.N_P:
        raise ContractError("ADC parameter vector layout drifted from adc.N_P")
    sp, va, vs, tp = m12["static_pressure"], m12["vane_aoa"], m12["vane_aoss"], m12["tat_probe"]
    tables = tuple(
        _ro(t.value(n))
        for t, n in (
            (sp, "pe_mach"),
            (sp, "pe_k"),
            (va, "bias_mach"),
            (va, "bias"),
            (vs, "bias_mach"),
            (vs, "bias"),
            (tp, "rec_mach"),
            (tp, "recovery"),
            (tp, "dhe_z"),
            (tp, "dhe"),
        )
    )
    for x, y in zip(tables[0::2], tables[1::2], strict=True):
        if x.ndim != 1 or x.shape != y.shape or x.size < 2 or np.any(np.diff(x) <= 0):
            raise ContractError("ADC correction tables must be 1-D, equal length, increasing x")
    bus = {lru: int(pw.value(_BUS_PARAM[lru])) for lru in POWER_LRUS}
    for lru, b in bus.items():
        if not 0 <= b < len(BUSES):
            raise ContractError(f"{lru}: bus index {b} outside M09's bus map {BUSES}")
    n_sub = int(m12["constants"].value("n_sub"))
    merged: dict[str, Param] = {}
    for sname, ps in sorted(p.items()):
        for pname in ps:
            merged[f"{sname}__{pname}"] = ps[pname]
    for sname in ("static_pressure", "vane_aoa", "vane_aoss", "tat_probe"):
        for pname in m12[sname]:
            merged[f"m12__{sname}__{pname}"] = m12[sname][pname]
    for a in (ins_p, ahrs_p, radalt_p, adc_p):
        a.flags.writeable = False
    fom.flags.writeable = False
    return AvionicsConfig(
        platform=platform,
        ins_p=ins_p,
        fom_bounds=fom,
        ahrs_p=ahrs_p,
        radalt_p=radalt_p,
        radalt_scale_sigma=float(rad.value("scale_sigma")),
        radalt_offset_sigma=float(rad.value("offset_sigma")),
        adc_p=adc_p,
        adc_tables=tables,
        bus=bus,
        sms_p_hung=float(p["sms"].value("p_hung")),
        n_sub=n_sub,
        dfcc_clock=dfcc,
        params=ParamSet(f"{platform}.{MODULE}", merged),
    )
