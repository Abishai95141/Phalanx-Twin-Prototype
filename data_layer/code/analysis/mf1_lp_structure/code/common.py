"""MF1-D shared constants, data guard and deterministic random sources (see ../PREREGISTRATION.md).

Data hygiene (binding, brief `docs/build_briefs/MF1_lp_structure_diagnostic.md`):
- only Tail 687 archive-1 CAL flights (set ``687-CAL`` of `analysis/settling_experiment/results/splits.csv`);
- the MAT directory is passed in as an argument (read-only, absolute path); files are parsed with
  `scipy.io.loadmat` through `phalanx.validation.dashlink`, nothing in them is executed;
- `guard_path` refuses any path whose string contains ``raw2`` (Tail 687 archive 2 is reserved for the AD-33
  gate), any path outside the declared MAT directory and any file that is not a 687-CAL flight.

Random sources: `phalanx.core.rng` (AD-15), root 20261015 (the project's round-2 root), campaign key
``mf1-diag``; streams `validation.flight_sample` (flight order) and `validation.bootstrap` (flight bootstrap).
No global RNG, no seed arithmetic.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WP = HERE.parent  # analysis/mf1_lp_structure
REPO = WP.parent.parent  # worktree root
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phalanx.core.rng import KeyPath, RngService, StreamRegistry  # noqa: E402
from phalanx.validation.battery.evaluate import BOOTSTRAP_STREAM  # noqa: E402
from phalanx.validation.samples import SAMPLE_STREAM  # noqa: E402

ROOT_SEED = (
    20261015  # project round-2 root (analysis/settling_experiment_round2/PREREGISTRATION.md section 7)
)
CAMPAIGN = "mf1-diag"
SPLITS_CSV = REPO / "analysis" / "settling_experiment" / "results" / "splits.csv"
RESULTS = WP / "results"
CAL_SET = "687-CAL"


class DataGuardError(PermissionError):
    """A path that this work package must not read."""


def cal_flights(splits_csv: Path = SPLITS_CSV) -> list[str]:
    """Sorted 687-CAL file names from the round-1 split (152 flights)."""
    with open(splits_csv, newline="") as fh:
        rows = list(csv.DictReader(fh))
    return sorted(r["file"] for r in rows if r["set"] == CAL_SET)


def guard_path(path: str | os.PathLike[str], mat_dir: str | os.PathLike[str], allowed: set[str]) -> Path:
    """Return the resolved path if it may be read, else raise DataGuardError.

    Refuses: any path string containing 'raw2' (reserved archive 2), anything outside `mat_dir`, any file
    name not in `allowed` (the 687-CAL set), and any MAT directory string containing 'raw2' or '652'.
    """
    s = os.fspath(path)
    md = os.fspath(mat_dir)
    if "raw2" in s or "raw2" in md:
        raise DataGuardError(f"{s}: Tail 687 archive 2 (raw2) is reserved for the AD-33 gate; refusing")
    if "652" in md or "tail652" in s:
        raise DataGuardError(f"{s}: Tail 652 must not be read by MF1-D")
    p = Path(s).resolve()
    mdir = Path(md).resolve()
    if "raw2" in str(p) or p.parent != mdir:
        raise DataGuardError(f"{p}: not directly inside the declared MAT directory {mdir}")
    if p.name not in allowed:
        raise DataGuardError(f"{p.name}: not a 687-CAL flight; refusing (687-TEST and others are excluded)")
    return p


def rng_service() -> RngService:
    return RngService(ROOT_SEED, StreamRegistry([SAMPLE_STREAM, BOOTSTRAP_STREAM]))


def order_generator():
    """Generator of the flight-order permutation (stream validation.flight_sample, scenario mf1-diag)."""
    rng = rng_service()
    path = KeyPath.of(scenario=CAMPAIGN, subsystem=SAMPLE_STREAM.subsystem, component=SAMPLE_STREAM.component)
    return rng.generator(path, 0), {"mode": "phalanx.core.rng", **rng.describe(), "path": path.canonical()}


def selftest_generator(index: int):
    """Generator for synthetic self-test signals only (stream validation.flight_sample, scenario
    mf1-diag.selftest); never used on flight data."""
    rng = rng_service()
    path = KeyPath.of(
        scenario=CAMPAIGN + ".selftest",
        subsystem=SAMPLE_STREAM.subsystem,
        component=SAMPLE_STREAM.component,
    )
    return rng.generator(path, int(index))


def bootstrap_generator(index: int):
    """Generator for flight-bootstrap index sets (stream validation.bootstrap, scenario mf1-diag).

    `index` identifies the flight set: it is the number of flights n of the analysed prefix, so every
    statistic computed on the same prefix shares one joint bootstrap.
    """
    rng = rng_service()
    path = KeyPath.of(
        scenario=CAMPAIGN, subsystem=BOOTSTRAP_STREAM.subsystem, component=BOOTSTRAP_STREAM.component
    )
    return rng.generator(path, int(index)), {
        "mode": "phalanx.core.rng",
        **rng.describe(),
        "path": path.canonical(),
        "index": int(index),
    }
