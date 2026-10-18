"""``fadec.fault_inject`` (M11 -> M08, AD-48.4): control-side faults as state perturbations (I6).

The catalogued event carries ``{tail, mode, param, instance, engine, clear}``. The handler writes the fault
slice of the M08 float state (``layout`` fields ``flt_*``); the kernel reads it, so every observable
consequence comes from the closed loop (the label-leak audit relies on healthy and faulty runs sharing one
generation path):

- ``nozzle_loop_gain_margin``: the nozzle T5-loop gain rises by ``fault_a8_gain`` x param (the F100 AJ limit
  cycle of the catalogue: the loop loses its gain margin and oscillates against the actuator rate limit);
- ``fuel_schedule_bias``: the ratio-unit schedules (Wf/PS3 reference, accel/decel limits, feed-forward) are
  biased by +param (fraction; catalogue: take-off Wf/PS3 102-105 % instead of 89-92 %);
- ``fuel_overmetering``: the metering demand to the FMV carries a gain error +param (fraction; the law's
  command stays in the state, so the governor and the limiters close round it);
- ``pla_binding``: the throttle input stays at the PLA of the onset frame until the clear (intermittent
  binding).

``bleed_schedule_bias`` is catalogued against the FADEC, but M08 schedules no bleed: M07 realises it
(``phalanx.engine.faults``) and the catalogue retarget is a W2.1b proposal; M08 refuses it so the fault is
never silently dropped.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from phalanx.core.module import ContractError

from .layout import F_FLT_A8_GAIN, F_FLT_PLA_HOLD, F_FLT_PLA_VAL, F_FLT_RU_BIAS, F_FLT_WF_GAIN, F_PLA_PREV

EVENT_KIND = "fadec.fault_inject"
PAYLOAD = ("tail", "mode", "param", "instance", "engine", "clear")
MODES: tuple[str, ...] = ("fuel_overmetering", "fuel_schedule_bias", "nozzle_loop_gain_margin", "pla_binding")
#: catalogued against the FADEC but realised by M07 (proposed catalogue retarget to target ``engine``)
REALISED_BY_M07 = frozenset({"bleed_schedule_bias"})


def apply_fault(f: np.ndarray, payload: Mapping[str, Any], a8_gain: float, n_engines: int) -> None:
    """Apply one ``fadec.fault_inject`` payload to (a mutable copy of) the M08 float state ``f`` (E, NF)."""
    for k in PAYLOAD:
        if k not in payload:
            raise ContractError(f"{EVENT_KIND}: payload lacks {k!r} (catalogue keys {PAYLOAD})")
    mode = str(payload["mode"])
    if mode in REALISED_BY_M07:
        raise ContractError(
            f"{EVENT_KIND}: {mode!r} has no FADEC realisation (M08 schedules no bleed); M07 realises it as "
            "eng.fault_inject (W2.1b proposal: retarget the catalogue effect to target 'engine')"
        )
    if mode not in MODES:
        raise ContractError(f"{EVENT_KIND}: unknown FADEC fault mode {mode!r} (M08 realises {MODES})")
    e = int(payload["engine"])
    if not 0 <= e < n_engines:
        raise ContractError(f"{EVENT_KIND}: engine {e} outside 0..{n_engines - 1}")
    size = float(payload["param"])
    if not np.isfinite(size) or size < 0.0:
        raise ContractError(f"{EVENT_KIND}: param must be finite and >= 0, got {size}")
    on = not bool(payload["clear"])
    if mode == "nozzle_loop_gain_margin":
        f[e, F_FLT_A8_GAIN] = a8_gain * size if on else 0.0
    elif mode == "fuel_schedule_bias":
        f[e, F_FLT_RU_BIAS] = size if on else 0.0
    elif mode == "fuel_overmetering":
        f[e, F_FLT_WF_GAIN] = size if on else 0.0
    else:  # pla_binding: hold the PLA the FADEC read at its last frame
        f[e, F_FLT_PLA_HOLD] = 1.0 if on and size > 0.0 else 0.0
        f[e, F_FLT_PLA_VAL] = f[e, F_PLA_PREV] if on else 0.0


__all__ = ["EVENT_KIND", "MODES", "PAYLOAD", "REALISED_BY_M07", "apply_fault"]
