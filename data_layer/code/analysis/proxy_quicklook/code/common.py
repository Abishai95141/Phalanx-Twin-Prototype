"""W2.4a-1 MF1 joint reachability study: shared paths, data guard, the fixed flight sample and run identities.

Data hygiene (binding, W2.4a brief "W2.4a-1"):
- only Tail 687 archive-1 **CAL** flights (`analysis/settling_experiment/results/splits.csv`, set 687-CAL);
- synthetic runs are driven by recorded **inputs** only (PLA x4, ALT, MACH, TAT, PH, ATEN, N1C;
  `phalanx.proxy.inputs`); real engine outputs are read only to compute the CAL target statistics with the
  same estimators;
- nothing is fitted: configurations are points of declared sweep ranges;
- every path passes `guarded` (the proxy A3 guard plus a CAL-membership check) before it is opened; the MAT
  directory is an argument; files are parsed by `scipy.io.loadmat` through the M20 adapter, never executed.

Flight sample: the MF1-D fixed order (`analysis/mf1_lp_structure/results/flight_order.json`, drawn with
`phalanx.core.rng` from file names only, before any data was read). Prefixes of it are the samples, so the
MF1 targets are computed on the very flights MF1-D characterised.

Run identities (CRN, AD-37): scenario `mf1-reach`, tail `T687`, sortie = position of the flight in the
order. Every configuration of a sweep uses the same identity per flight, so the exogenous randomness
(disturbance factor draws, texture noise, freezes) is common across configurations: differences between
configurations are caused by the configuration, not by a new draw.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WP = HERE.parent  # analysis/proxy_quicklook
REPO = WP.parent.parent
SRC = REPO / "src"
MF1D_CODE = REPO / "analysis" / "mf1_lp_structure" / "code"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# MF1-D's estimators (spectral.py) are appended, so this study's own modules (common, report, ...) win over
# MF1-D's modules of the same names
if str(MF1D_CODE) not in sys.path:
    sys.path.append(str(MF1D_CODE))

from phalanx.core.rng import KeyPath  # noqa: E402
from phalanx.proxy.guard import check_path  # noqa: E402

RESULTS = WP / "results"
SPLITS_CSV = REPO / "analysis" / "settling_experiment" / "results" / "splits.csv"
MF1D_ORDER = REPO / "analysis" / "mf1_lp_structure" / "results" / "flight_order.json"
MF1D_SUMMARY = REPO / "analysis" / "mf1_lp_structure" / "results" / "summary.json"
CAL_SET = "687-CAL"
ROOT = 20261015  # the project's round-2 root seed (analysis/settling_experiment_round2/PREREGISTRATION.md §7)
SCENARIO = "mf1-reach"


class DataGuardError(PermissionError):
    """A path that this study must not read."""


def cal_flights() -> set[str]:
    with open(SPLITS_CSV, newline="") as fh:
        return {r["file"] for r in csv.DictReader(fh) if r["set"] == CAL_SET}


def flight_order() -> list[str]:
    """The MF1-D fixed order of the 152 CAL flights (a prefix of it is every sample here)."""
    with open(MF1D_ORDER) as fh:
        order = json.load(fh)["order"]
    cal = cal_flights()
    if set(order) != cal or len(order) != len(cal):
        raise DataGuardError("MF1-D order is not the 687-CAL population")
    return list(order)


def guarded(mat_dir: str | os.PathLike[str], fname: str) -> Path:
    """Path of one CAL MAT file, or DataGuardError (reserved archive, Tail 652, non-CAL file)."""
    md = os.fspath(mat_dir)
    if "652" in md:
        raise DataGuardError(f"Tail 652 is not used in W2.4a-1: {md}")
    if fname not in cal_flights():
        raise DataGuardError(f"{fname} is not a 687-CAL flight")
    p = check_path(Path(md) / fname)  # A3: refuses the reserved archive before anything is opened
    if p.resolve().parent != Path(md).resolve():
        raise DataGuardError(f"{p} is outside {md}")
    return p


def identity(order_index: int) -> KeyPath:
    return KeyPath.of(scenario=SCENARIO, tail="T687", sortie=int(order_index) + 1)


__all__ = [
    "MF1D_SUMMARY",
    "RESULTS",
    "ROOT",
    "WP",
    "DataGuardError",
    "flight_order",
    "guarded",
    "identity",
]
