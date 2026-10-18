"""G1 quantiser residue fidelity (diagnostic guard; port of round-2 `s04_stats.g1_counts` +
`battery_eval.g1`).

On airborne samples, each recorded value is turned into its recorder code round(x / LSB) and counted by
residue modulo a period: 32 for N1/N2 (25 native 0.04 % steps per 32 codes of 0.03125 %), 8 for EGT
(5 native 0.8 degC steps per 8 codes of 0.5 degC) and 8 for FF (single lattice). The distance is the total
variation between the pooled residue histograms of the synthetic and real groups. A double quantiser
(native step, then recorder lattice; AD-05) reproduces the never-used residues; a single lattice does not
(round 2: 0.01-0.02 vs 0.19-0.27).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from phalanx.validation.battery.config import BatteryConfig
from phalanx.validation.battery.stats import airborne_mask
from phalanx.validation.flightdata import FlightRecord

__all__ = ["G1_PERIOD", "g1_counts", "g1_distance"]

#: Residue periods per family [codes] (round-2 `s04_stats.G1_P`; [MEASURED] native-step diagnostic on
# 687-CAL).
G1_PERIOD: Mapping[str, int] = {"N1": 32, "N2": 32, "EGT": 8, "FF": 8}

Counts = Mapping[str, np.ndarray]


def g1_counts(
    rec: FlightRecord, cfg: BatteryConfig | None = None, periods: Mapping[str, int] = G1_PERIOD
) -> dict[str, np.ndarray]:
    """Residue-usage counts per family: array (n_units, period) of int64, airborne samples only."""
    cfg = cfg or BatteryConfig()
    cfg.check(rec)
    Y = {f: np.asarray(rec.outputs[f], float) for f in cfg.families}
    air = airborne_mask(Y, cfg)
    out = {}
    for f in cfg.families:
        P = periods[f]
        rows = []
        for k in range(cfg.n_units):
            c = np.rint(Y[f][k][air] / cfg.lsb_rec[f]).astype(np.int64)
            rows.append(np.bincount(c % P, minlength=P))
        out[f] = np.array(rows, np.int64)
    return out


def g1_distance(
    syn: Sequence[Counts | None],
    real: Sequence[Counts | None],
    families: Sequence[str] = ("N1", "N2", "EGT", "FF"),
) -> dict[str, dict[str, object]]:
    """Total-variation distance between the pooled residue histograms of two groups, per family."""
    out: dict[str, dict[str, object]] = {}
    for f in families:
        A = [s[f].sum(0) for s in syn if s is not None and f in s]
        B = [s[f].sum(0) for s in real if s is not None and f in s]
        if not A or not B:
            raise ValueError(f"G1 needs residue counts of {f} in both groups")
        a, b = sum(A), sum(B)
        pa, pb = a / max(a.sum(), 1), b / max(b.sum(), 1)
        out[f] = {
            "tv_distance": float(0.5 * np.abs(pa - pb).sum()),
            "residues_syn": pa.round(4).tolist(),
            "residues_real": pb.round(4).tolist(),
            "n_flights": {"syn": len(A), "real": len(B)},
        }
    return out
