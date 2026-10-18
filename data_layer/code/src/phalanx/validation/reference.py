"""Readers for the round-2 reference artefacts, for golden regression of the ported battery.

- per-flight statistics written by round-2 `s04_stats.py` (`<stats_dir>/<label>/<flight>.npz`, arrays only,
  loaded with `allow_pickle=False`);
- flight lists and `battery.json` under `analysis/settling_experiment_round2/results/holdout_*/`.

Nothing here computes a statistic; it only translates stored round-2 outputs into the port's types.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from phalanx.validation.battery.stats import B5Moments, FlightStats

__all__ = [
    "ROUND2_LABELS",
    "flight_stats_from_round2_npz",
    "load_round2_battery",
    "load_round2_lists",
    "load_round2_stats",
]

#: Arm labels of round-2 `run_holdout.labels()`, in its order.
ROUND2_LABELS: tuple[str, ...] = (
    *(f"{v}_{arm}_{off}" for v in ("S", "P") for arm in ("R2a", "R2b") for off in ("prior", "cal")),
    "R1ref",
)

_ARRAYS = ("b1_slow", "b1_fast", "b1h_slow", "b1h_fast", "b2", "b3_coh", "b3_lgain", "b4", "b6")
_MOM = ("XtX", "Xty", "yy", "sy", "n")


def _moments(z: Mapping[str, np.ndarray], prefix: str) -> B5Moments | None:
    if f"{prefix}_n" not in z:
        return None
    d = {k: z[f"{prefix}_{k}"] for k in _MOM}
    yy = d["yy"] if np.ndim(d["yy"]) else float(d["yy"])
    sy = d["sy"] if np.ndim(d["sy"]) else float(d["sy"])
    return B5Moments(XtX=d["XtX"], Xty=d["Xty"], yy=yy, sy=sy, n=float(d["n"]))


def flight_stats_from_round2_npz(z: Mapping[str, np.ndarray], flight_id: str) -> FlightStats:
    """Translate one round-2 `s04_stats.py` npz (absent key = statistic not computable) into `FlightStats`."""
    kw: dict[str, object] = {k: (np.asarray(z[k], float) if k in z else None) for k in _ARRAYS}
    steps = np.asarray(z["b3_steps"], float).reshape(-1, 3) if "b3_steps" in z else np.zeros((0, 3))
    return FlightStats(
        flight_id=flight_id,
        air_frac=float(z["air_frac"]),
        b3_steps=steps,
        b5_ff=_moments(z, "b5_ff"),
        b5_egt=_moments(z, "b5_egt"),
        **kw,  # type: ignore[arg-type]
    )


def load_round2_stats(
    stats_dir: str | os.PathLike[str], label: str, files: Sequence[str]
) -> list[FlightStats | None]:
    """Stored per-flight stats of one group, aligned with `files` (None when a file is missing)."""
    out: list[FlightStats | None] = []
    for f in files:
        p = Path(stats_dir) / label / f.replace(".mat", ".npz")
        if not p.exists():
            out.append(None)
            continue
        with np.load(p, allow_pickle=False) as z:
            out.append(flight_stats_from_round2_npz({k: z[k] for k in z.files}, f.replace(".mat", "")))
    return out


def load_round2_lists(results_dir: str | os.PathLike[str]) -> dict[str, list[str]]:
    """{holdout, partner, early, late} flight lists saved by the round-2 runner (saved before any
    analysis)."""
    out = {}
    for k in ("holdout", "partner", "early", "late"):
        with open(Path(results_dir) / f"list_{k}.txt") as fh:
            out[k] = [ln.strip() for ln in fh if ln.strip()]
    return out


def load_round2_battery(results_dir: str | os.PathLike[str]) -> dict[str, object]:
    """The stored round-2 `battery.json` of one holdout run."""
    with open(Path(results_dir) / "battery.json") as fh:
        return json.load(fh)
