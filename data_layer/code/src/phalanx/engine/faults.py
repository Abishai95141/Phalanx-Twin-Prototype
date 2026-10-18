"""``eng.fault_inject`` (M11 -> M07, AD-48.4): physical engine faults as state perturbations (I6).

The catalogued event carries ``{tail, mode, param, instance, engine, clear}``: ``mode`` names the physical
fault, ``param`` its size (the catalogue's ``param`` times the instance severity, M11) and ``clear`` its end.
The handler never touches an output: it changes the M07 state only, and every observable consequence comes
from the dynamics (the generation path is identical for healthy and faulty runs; the label-leak audit relies
on it).

Two kinds of effect:

- **Persistent perturbations** (vibration sources, extra spool loads, stall-margin debits, a fuel-flow cap,
  extra bleed, start faults below run speed, a nozzle leak, an oil leak, lube-cooling loss, an afterburner
  that cannot light): the per-mode sizes are held in the module state ``fm`` (engine x mode) and the effective
  perturbation slice of the kernel float state (``layout.FLT_NAMES``) is recomputed from all active modes
  after every event, so a ``clear`` removes exactly that mode's contribution.
- **One-shot events** applied to the state at onset: a main-burner flameout (flame out), a pop or quick-fill
  stall (surge triggered), an afterburner blowout (AB out); blade loss and fan-blade liberation also trigger a
  surge.

Magnitudes are M07 parameters (``configs/tejas/params/M07.yaml`` set ``faults``, A-W2.1b-4), each tagged with
the catalogue signature it reproduces. Health deltas of the same fault (component efficiency/flow) arrive
separately through ``health.engine`` (M10), as the catalogue lists them.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from phalanx.core.module import ContractError, ParamSet

from .layout import (
    AB_LIT,
    AB_OFF,
    F_FLT0,
    F_SURGE_TIMER,
    FLT_AB_BLOCK,
    FLT_BLEED,
    FLT_BLEED_FRAC,
    FLT_COMB,
    FLT_NAMES,
    FLT_NOZ_LEAK,
    FLT_OIL_CRIT,
    FLT_OIL_LEVEL,
    FLT_OIL_RATE,
    FLT_OIL_SEIZE,
    FLT_RUN_N2,
    FLT_SM,
    FLT_SM_N2,
    FLT_TQ_HP,
    FLT_TQ_LP,
    FLT_UA_LOSS,
    FLT_VIB1,
    FLT_VIB2,
    FLT_VIBBB,
    FLT_WF_BIAS,
    FLT_WF_CAP,
    I_AB,
    I_FLAME,
    I_NSURGE,
    I_SURGE,
    NFLT,
)

EVENT_KIND = "eng.fault_inject"
PAYLOAD = ("tail", "mode", "param", "instance", "engine", "clear")
#: every engine mode of the M11 fault catalogue (configs/tejas/faults/catalogue.yaml, target engine), plus
#: ``bleed_schedule_bias`` (catalogued against the FADEC; M08 has no bleed schedule, so M07 realises it)
MODES: tuple[str, ...] = (
    "ab_no_light",
    "ab_rumble_blowout",
    "bearing_failure",
    "blade_loss",
    "bleed_leak",
    "bleed_schedule_bias",
    "fan_blade_liberation",
    "flameout",
    "fod_imbalance",
    "fuel_restriction",
    "hot_start",
    "hung_start",
    "liner_burn_through",
    "lube_cooling_loss",
    "oil_quantity_low",
    "pop_stall",
    "quickfill_stall",
)
N_MODES = len(MODES)
MODE_INDEX = {m: k for k, m in enumerate(MODES)}
#: modes whose whole effect is applied at onset (their ``clear`` has nothing to remove)
ONE_SHOT = frozenset({"flameout", "pop_stall", "quickfill_stall", "ab_rumble_blowout"})
#: modes that also trigger a surge at onset
SURGE_AT_ONSET = frozenset({"pop_stall", "quickfill_stall", "blade_loss", "fan_blade_liberation"})
#: fault-magnitude parameters (M07.yaml set ``faults``)
PARAM_NAMES: tuple[str, ...] = (
    "fault_vib_fod",
    "fault_vib_blade",
    "fault_vib_fan_lib",
    "fault_vib_bearing",
    "fault_tq_bearing",
    "fault_sm_bearing",
    "fault_bearing_n2",
    "fault_tq_blade",
    "fault_sm_blade",
    "fault_tq_fan_lib",
    "fault_fuel_cap",
    "fault_comb_hung",
    "fault_wf_hot",
    "fault_run_n2",
    "fault_noz_leak",
    "fault_oil_deplete",
    "fault_oil_crit",
    "fault_oil_seize",
)


def fault_constants(params: ParamSet, design: Any) -> dict[str, float]:
    """The fault magnitudes (SI) plus the design references they scale (MIL fuel flow, 100 % N2)."""
    c = {k: float(params.value(k)) for k in PARAM_NAMES}
    c["wf_des"] = float(design.stations["wf"])
    c["n2_100"] = float(design.stations["n2_100"])
    return c


def effective(fm: np.ndarray, c: Mapping[str, float]) -> np.ndarray:
    """Effective perturbation slice (E, NFLT) from the per-mode sizes ``fm`` (E, N_MODES); oil level excluded
    (it is a state the kernel integrates; the caller keeps it)."""
    out = np.zeros((fm.shape[0], NFLT))
    for e in range(fm.shape[0]):
        m = {name: float(fm[e, k]) for k, name in enumerate(MODES)}
        f = out[e]
        f[FLT_VIB1] = (
            c["fault_vib_fod"] * m["fod_imbalance"] + c["fault_vib_fan_lib"] * m["fan_blade_liberation"]
        )
        f[FLT_VIB2] = c["fault_vib_blade"] * m["blade_loss"]
        f[FLT_VIBBB] = c["fault_vib_bearing"] * m["bearing_failure"]
        f[FLT_TQ_LP] = c["fault_tq_fan_lib"] * m["fan_blade_liberation"]
        f[FLT_TQ_HP] = c["fault_tq_bearing"] * m["bearing_failure"] + c["fault_tq_blade"] * m["blade_loss"]
        # stall-margin debit: a blade loss debits at every speed, a failed bearing above its speed threshold
        if m["blade_loss"] > 0.0:
            f[FLT_SM] = c["fault_sm_blade"] * m["blade_loss"]
            f[FLT_SM_N2] = 0.0
        elif m["bearing_failure"] > 0.0:
            f[FLT_SM] = c["fault_sm_bearing"] * m["bearing_failure"]
            f[FLT_SM_N2] = c["fault_bearing_n2"] * c["n2_100"]
        if m["fuel_restriction"] > 0.0:
            # a larger param closes the valve further (cap shrinks with the size)
            f[FLT_WF_CAP] = c["fault_fuel_cap"] * c["wf_des"] / m["fuel_restriction"]
        f[FLT_BLEED] = m["bleed_leak"]  # kg/s (catalogue: param in kg/s)
        f[FLT_BLEED_FRAC] = m["bleed_schedule_bias"]  # fraction of core flow
        f[FLT_AB_BLOCK] = 1.0 if m["ab_no_light"] > 0.0 else 0.0
        f[FLT_COMB] = min(c["fault_comb_hung"] * m["hung_start"], 0.95)
        f[FLT_WF_BIAS] = c["fault_wf_hot"] * m["hot_start"]
        f[FLT_RUN_N2] = (
            c["fault_run_n2"] * c["n2_100"] if (m["hung_start"] > 0.0 or m["hot_start"] > 0.0) else 0.0
        )
        f[FLT_NOZ_LEAK] = c["fault_noz_leak"] * m["liner_burn_through"]
        if m["oil_quantity_low"] > 0.0:
            f[FLT_OIL_RATE] = m["oil_quantity_low"] / c["fault_oil_deplete"]
        f[FLT_OIL_CRIT] = c["fault_oil_crit"] if m["oil_quantity_low"] > 0.0 else 0.0
        f[FLT_OIL_SEIZE] = c["fault_oil_seize"] if m["oil_quantity_low"] > 0.0 else 0.0
        f[FLT_UA_LOSS] = min(max(m["lube_cooling_loss"], 0.0), 0.95)
    return out


def apply_fault(
    state: dict[str, np.ndarray], payload: Mapping[str, Any], consts: Mapping[str, float], n_engines: int
) -> None:
    """Apply one ``eng.fault_inject`` payload to (a mutable copy of) the M07 state (``f``, ``i``, ``fm``)."""
    for k in PAYLOAD:
        if k not in payload:
            raise ContractError(f"{EVENT_KIND}: payload lacks {k!r} (catalogue keys {PAYLOAD})")
    mode = str(payload["mode"])
    if mode not in MODE_INDEX:
        raise ContractError(f"{EVENT_KIND}: unknown engine fault mode {mode!r} (M07 realises {MODES})")
    e = int(payload["engine"])
    if not 0 <= e < n_engines:
        raise ContractError(f"{EVENT_KIND}: engine {e} outside 0..{n_engines - 1}")
    size = float(payload["param"])
    if not np.isfinite(size) or size < 0.0:
        raise ContractError(f"{EVENT_KIND}: param must be finite and >= 0, got {size}")
    clear = bool(payload["clear"])
    f, i, fm = state["f"], state["i"], state["fm"]
    if not clear:
        if mode == "flameout":
            i[e, I_FLAME] = 0
        if mode in SURGE_AT_ONSET and i[e, I_SURGE] == 0:
            i[e, I_SURGE] = 1
            f[e, F_SURGE_TIMER] = 0.0
            i[e, I_NSURGE] += 1
        if mode == "ab_rumble_blowout" and i[e, I_AB] == AB_LIT:
            i[e, I_AB] = AB_OFF
    if mode not in ONE_SHOT:
        fm[e, MODE_INDEX[mode]] = 0.0 if clear else size
        level = f[:, F_FLT0 + FLT_OIL_LEVEL].copy()
        f[:, F_FLT0 : F_FLT0 + NFLT] = effective(fm, consts)
        f[:, F_FLT0 + FLT_OIL_LEVEL] = level


__all__ = [
    "EVENT_KIND",
    "MODES",
    "N_MODES",
    "ONE_SHOT",
    "PARAM_NAMES",
    "PAYLOAD",
    "apply_fault",
    "effective",
    "fault_constants",
]
_ = FLT_NAMES
