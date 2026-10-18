"""M09 parameters (configs/<platform>/params/M09.yaml) -> one ParamSet -> the flat kernel vector (AD-22).

Every value carries units, evidence tag and source in the YAML (loader: ``phalanx.dictionary.params``).
``load_m09_params`` merges the YAML sets into one ``ParamSet`` (names are unique across sets).
``param_vector`` lays the scalars out in ``layout.P_NAMES`` order, then the tank table and the store-station
table. ``config_vector`` builds the integer installation configuration (engine mapping of the AMAGB pads,
hydraulic sub-steps, transfer-interruption ticks).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from phalanx.core.module import ContractError, ParamSet
from phalanx.core.time import TRUTH_HZ
from phalanx.dictionary.params import load_params

from .layout import (
    C_BRK_SYS,
    C_GEN_ENG,
    C_JFS_ENG,
    C_NE,
    C_NSUB,
    C_PUMP_ENG0,
    C_PUMP_ENG1,
    C_XFER_TICKS,
    N_STORE,
    N_TANKS,
    NC,
    NP_TOTAL,
    PARAMS,
    STORE_COLS,
    TANK_COLS,
)

MAX_TRANSFER_S = 0.050  # MIL-STD-704F §5.1: bus/source transfer interruption at most 50 ms


def load_m09_params(platform: str = "tejas", config_root: Path | None = None) -> ParamSet:
    """All M09 parameter sets merged into one ParamSet (SI values, evidence tags, PROXY flags)."""
    sets = load_params("M09", platform=platform, config_root=config_root)
    merged = {}
    for sname in sorted(sets):
        for k in sets[sname]:
            if k in merged:
                raise ContractError(f"M09 parameter {k!r} defined in more than one set")
            merged[k] = sets[sname][k]
    return ParamSet(f"{platform}.M09", merged)


def _array(ps: ParamSet, name: str, n: int) -> np.ndarray:
    v = np.asarray(ps.value(name), dtype=np.float64)
    if v.shape != (n,):
        raise ContractError(f"M09 parameter {name!r} must have {n} entries, got shape {v.shape}")
    return v


def param_vector(ps: ParamSet) -> np.ndarray:
    """Flat read-only float64 kernel parameter vector: scalars, tank table (column blocks), store table."""
    parts = [PARAMS.vector(ps)]
    parts += [_array(ps, f"tank_{c}", N_TANKS) for c in TANK_COLS]
    parts += [_array(ps, f"store_{c}", N_STORE) for c in STORE_COLS]
    vec = np.concatenate(parts)
    if vec.size != NP_TOTAL:
        raise ContractError(f"M09 parameter vector has {vec.size} entries, layout expects {NP_TOTAL}")
    vec.flags.writeable = False
    return vec


def transfer_ticks(ps: ParamSet) -> int:
    """Essential-bus transfer interruption in truth ticks (rounded up; must stay within 704F's 50 ms)."""
    t = float(ps.value("elec_transfer_time"))
    if not 0.0 < t <= MAX_TRANSFER_S:
        raise ContractError(f"elec_transfer_time {t} s outside (0, {MAX_TRANSFER_S}] s (MIL-STD-704F §5.1)")
    n = int(np.ceil(t * TRUTH_HZ - 1e-9))
    if n / TRUTH_HZ > MAX_TRANSFER_S + 1e-12:
        raise ContractError(f"{n} ticks exceed the 50 ms transfer limit")
    return n


def config_vector(ps: ParamSet, n_engines: int) -> np.ndarray:
    """Integer installation configuration for the kernel (engine indices are clipped to n_engines - 1)."""
    cfg = np.zeros(NC, dtype=np.int64)
    pumps = np.asarray(ps.value("hyd_pump_engine"), dtype=np.float64)
    if pumps.shape != (2,) or np.any(pumps != np.round(pumps)) or np.any(pumps < 0):
        raise ContractError("hyd_pump_engine must be two non-negative integers")
    cfg[C_NE] = n_engines
    cfg[C_PUMP_ENG0] = min(int(pumps[0]), n_engines - 1)
    cfg[C_PUMP_ENG1] = min(int(pumps[1]), n_engines - 1)
    cfg[C_GEN_ENG] = min(int(ps.value("gen_engine")), n_engines - 1)
    cfg[C_JFS_ENG] = min(int(ps.value("jfs_engine")), n_engines - 1)
    nsub = int(ps.value("hyd_nsub"))
    if nsub < 1:
        raise ContractError("hyd_nsub must be >= 1")
    cfg[C_NSUB] = nsub
    cfg[C_XFER_TICKS] = transfer_ticks(ps)
    brk = int(ps.value("brk_hyd_system"))
    if brk not in (0, 1):
        raise ContractError("brk_hyd_system must be 0 or 1")
    cfg[C_BRK_SYS] = brk
    cfg.flags.writeable = False
    return cfg


def power_quality_bands(ps: ParamSet) -> dict[str, float]:
    """MIL-STD-704F classification limits (V, Hz) from the ``power_quality`` set."""
    keys = (
        "dc_normal_lo",
        "dc_normal_hi",
        "dc_emerg_lo",
        "dc_start_lo",
        "ac_normal_lo",
        "ac_normal_hi",
        "ac_f_lo",
        "ac_f_hi",
    )
    return {k: float(ps.value(f"pq_{k}")) for k in keys}
