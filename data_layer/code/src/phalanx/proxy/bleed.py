"""Customer bleed and power off-take of the proxy engines from the recorded DASHlink discretes (U4 boundary).

DASHlink records the bleed and anti-ice **states** but no flows: ``BLV`` (bleed-air valves, one bit per
engine), ``PACK`` (air-conditioning packs, one bit per pack), ``EAI`` (engine anti-ice, one bit per engine),
``WAI_1`` (inner-wing de-ice) and ``TAI`` (tail anti-ice). The proxy turns them into a bleed flow per engine
(``util.bleed_extract``, kg/s, extracted at HPC exit by M07):

- each running pack draws ``w_pack`` in flight and ``w_pack_ground`` on the ground (ACMS phase PH 2, taxi:
  the record shows the valve states, not the source or the pack flow schedule, and the identified ground
  draw is far smaller), shared equally by the engines whose bleed valve is open;
- wing and tail anti-ice draw ``w_wai`` together, shared likewise;
- each engine with its engine anti-ice on draws ``w_eai`` from that engine (its own valve, independent of the
  customer bleed valve).

Bit k of ``BLV``/``EAI`` is engine k + 1: [MEASURED] for ``EAI`` (each bit switches on with the start of its
engine, 25 of 25 single-bit events on 10 CAL flights, ``analysis/proxy_quicklook`` stage 1); the same
convention is an [ASSUMPTION] for ``BLV`` (its bits open within seconds of each other in the climb, so no
event separates them). The flows and the constant power off-take per engine (``util.pto_power``, generator
and hydraulic pumps; the N2^2 accessory load stays inside M07) are identified on 687-CAL steady points
(W2.4a-2 stage 1; ``configs/proxy_dashlink/params/M09.yaml``). PROXY: real customer bleed ports are
intermediate HP stages; the identified flows are HPC-exit-equivalent (A-W2.4a-22).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from phalanx.core.module import ParamSet


@dataclass(frozen=True)
class BleedParams:
    w_pack: float  # kg/s per running pack in flight
    w_eai: float  # kg/s per engine with engine anti-ice on
    w_wai: float  # kg/s wing + tail anti-ice
    pto_w: float  # W per engine, constant
    w_pack_ground: float = 0.0  # kg/s per running pack on the ground (PH 2)

    @classmethod
    def from_params(cls, ps: ParamSet) -> BleedParams:
        return cls(*(float(ps.value(k)) for k in ("w_pack", "w_eai", "w_wai", "pto_power", "w_pack_ground")))

    @classmethod
    def off(cls) -> BleedParams:
        return cls(0.0, 0.0, 0.0, 0.0, 0.0)


def _bits(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, np.int64)
    return sum(((x >> k) & 1) for k in range(8))


def engine_bleed(
    blv: np.ndarray,
    pack: np.ndarray,
    eai: np.ndarray,
    wai: np.ndarray,
    p: BleedParams,
    n_engines: int = 4,
    ground: np.ndarray | None = None,
) -> np.ndarray:
    """Bleed flow per engine [kg/s], shape (n_engines, n), from the recorded discretes (n,) each; ``ground``
    (n,) bool selects the ground pack draw (None = in flight throughout)."""
    blv = np.asarray(blv, np.int64)
    eai = np.asarray(eai, np.int64)
    n_open = _bits(blv)
    w_pack = p.w_pack if ground is None else np.where(np.asarray(ground, bool), p.w_pack_ground, p.w_pack)
    demand = _bits(pack) * w_pack + (np.asarray(wai) > 0) * p.w_wai
    share = np.where(n_open > 0, demand / np.maximum(n_open, 1), 0.0)
    out = np.empty((n_engines, blv.size))
    for k in range(n_engines):
        out[k] = ((blv >> k) & 1) * share + ((eai >> k) & 1) * p.w_eai
    return out


__all__ = ["BleedParams", "engine_bleed"]
