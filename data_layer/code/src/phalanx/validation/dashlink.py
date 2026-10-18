"""DASHlink proxy-data adapter: MAT file -> `FlightRecord` (port of round-1 `dlio.load_flight` + round-2
`r2common.load`).

Data files are untrusted data: they are only parsed with `scipy.io.loadmat` (MAT v5), nothing in them is
executed. Paths are always passed in by the caller (read-only). **Tail 687 archive 2 (`raw2/`) is reserved**
for the AD-33 gate; `load_record` refuses any path containing a `raw2` component unless the caller passes
`allow_reserved=True`, which only the pre-registered gate run may do.

4-Hz alignment (round-2 rules, DEVIATIONS.md B2):
- n = min(size of N1_1..N1_4, PLA_1, ALT, MACH);
- TAT (1 Hz) linearly interpolated to the 4-Hz grid; PH and WOW (1 Hz) held;
- MACH = 0 is the channel's in-flight sentinel: isolated zeros whose 2-s neighbourhood median is above 0.15
  are interpolated, ground zeros are kept;
- theta = (TAT + 273.15) / 288.15; delta = delta_s(ALT) (1 + 0.2 M^2)^3.5 (ISA, full ram recovery).
"""

from __future__ import annotations

import csv
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.io as sio
from numpy.lib.stride_tricks import sliding_window_view

from phalanx.validation.flightdata import DASHLINK_UNITS, FlightRecord
from phalanx.validation.guards.g0 import metadata_features

__all__ = [
    "FNAME_RE",
    "GATE0_CHANNELS",
    "Param",
    "corrections",
    "delta_static",
    "flight_date",
    "gate0_metadata",
    "load_lsb",
    "load_mat",
    "load_record",
    "load_sentinels",
    "load_vrtg_affine",
    "raw_channels",
]

FAM = ("N1", "N2", "EGT", "FF")
RATE = 4.0
T0K = 273.15
#: Channels of the round-1/2 G0 metadata vector (round-1 `config.GROUP`): 16 engine words + VRTG.
GATE0_CHANNELS: tuple[str, ...] = (*(f"{f}_{k}" for f in FAM for k in (1, 2, 3, 4)), "VRTG")
FNAME_RE = re.compile(r"^(\d{3})(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(_1)?\.mat$")


@dataclass(frozen=True, eq=False)
class Param:
    """One recorded parameter of a DASHlink MAT file: raw array (original dtype), float copy and rate [Hz]."""

    name: str
    raw: np.ndarray
    x: np.ndarray
    rate: float
    units: str


def _check_not_reserved(path: str | os.PathLike[str], allow_reserved: bool) -> None:
    if not allow_reserved and "raw2" in Path(path).parts:
        raise PermissionError(
            f"{path}: Tail 687 archive 2 is reserved for the AD-33 gate and must not be read"
        )


def load_mat(path: str | os.PathLike[str], *, allow_reserved: bool = False) -> dict[str, Param]:
    """Parse a DASHlink MAT file into {name: Param} (port of round-1 `dlio.load_flight`)."""
    _check_not_reserved(path, allow_reserved)
    m = sio.loadmat(os.fspath(path), squeeze_me=True, struct_as_record=False)
    out: dict[str, Param] = {}
    for k, v in m.items():
        if k.startswith("__"):
            continue
        if hasattr(v, "_fieldnames") and "data" in v._fieldnames:
            raw = np.atleast_1d(np.asarray(v.data))
            u = getattr(v, "Units", "")
            out[k] = Param(
                name=k,
                raw=raw,
                x=raw.astype(float),
                rate=float(getattr(v, "Rate", np.nan)),
                units=u if isinstance(u, str) else "",
            )
    return out


def delta_static(alt_ft: np.ndarray) -> np.ndarray:
    """ISA static pressure ratio for pressure altitude [ft] (troposphere and lower stratosphere)."""
    h = np.asarray(alt_ft, float)
    tropo = (1.0 - 6.87559e-6 * np.minimum(h, 36089.0)) ** 5.2559
    strat = np.exp(-4.80634e-5 * np.maximum(h - 36089.0, 0.0))
    return tropo * strat


def corrections(alt_ft: np.ndarray, mach: np.ndarray, tat_c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(theta, delta) inlet total-temperature and total-pressure ratios (round-2 DEVIATIONS.md B2)."""
    theta = (np.asarray(tat_c, float) + T0K) / 288.15
    delta = delta_static(alt_ft) * (1.0 + 0.2 * np.asarray(mach, float) ** 2) ** 3.5
    return theta, delta


def _clean_mach(m: np.ndarray) -> np.ndarray:
    m = m.astype(float).copy()
    z = m == 0
    if z.any():
        k = 9
        pad = np.r_[np.full(k, m[0]), m, np.full(k, m[-1])]
        nb = np.median(sliding_window_view(pad, 2 * k + 1), axis=1)
        bad = z & (nb > 0.15)
        if bad.any() and (~bad).any():
            i = np.arange(m.size)
            m[bad] = np.interp(i[bad], i[~bad], m[~bad])
    return m


def flight_date(fname: str) -> str | None:
    """ISO-like date string 'YYYY-MM-DDTHH:MM' from a DASHlink file name, None if it does not match."""
    mm = FNAME_RE.match(os.path.basename(fname))
    if not mm:
        return None
    _, y, mo, d, h, mi, _ = mm.groups()
    return f"{y}-{mo}-{d}T{h}:{mi}"


def load_record(path: str | os.PathLike[str], *, allow_reserved: bool = False) -> FlightRecord:
    """Load one DASHlink flight as a 4-Hz `FlightRecord` (engine outputs + inputs), round-2 alignment
    rules."""
    F = load_mat(path, allow_reserved=allow_reserved)
    n = min(F[f"N1_{k}"].x.size for k in (1, 2, 3, 4))
    n = min(n, F["PLA_1"].x.size, F["ALT"].x.size, F["MACH"].x.size)
    t4 = np.arange(n) * (1.0 / RATE)
    tat1 = F["TAT"].x.astype(float)
    tat = np.interp(t4, np.arange(tat1.size) / F["TAT"].rate, tat1)
    ph = F["PH"].x.astype(int)
    ph4 = ph[np.minimum((t4 * F["PH"].rate).astype(int), ph.size - 1)]
    alt = F["ALT"].x[:n].astype(float)
    mach = _clean_mach(F["MACH"].x[:n])
    th, de = corrections(alt, mach, tat)
    fname = os.path.basename(os.fspath(path))
    return FlightRecord(
        flight_id=fname.replace(".mat", ""),
        rate_hz=RATE,
        outputs={f: np.vstack([F[f"{f}_{k}"].x[:n].astype(float) for k in (1, 2, 3, 4)]) for f in FAM},
        pla=np.vstack([F[f"PLA_{k}"].x[:n].astype(float) for k in (1, 2, 3, 4)]),
        theta=th,
        delta=de,
        phase=ph4,
        units=DASHLINK_UNITS,
        meta={"source": "DASHlink MAT", "file": fname, "date": flight_date(fname) or ""},
    )


def load_sentinels(
    table_csv: str | os.PathLike[str], min_iso_per_hour: float = 0.1
) -> dict[str, list[float]]:
    """Sentinel values per parameter from `analysis/dashlink_texture/results/dropouts_sentinels.csv`
    (port of round-1 `common.load_sentinels`; [MEASURED] on Tail 687)."""
    s: dict[str, list[float]] = {}
    with open(table_csv, newline="") as fh:
        for r in csv.DictReader(fh):
            if float(r["isolated_per_record_hour"]) >= min_iso_per_hour:
                s.setdefault(r["param"], []).append(float(r["value"]))
    return s


def raw_channels(F: Mapping[str, Param], names: Sequence[str]) -> dict[str, tuple[np.ndarray, float]]:
    """{name: (raw array with its recorded dtype, rate [Hz])} for the G0 metadata audit."""
    return {nm: (F[nm].raw.ravel(), F[nm].rate) for nm in names}


def load_lsb(param_table_csv: str | os.PathLike[str]) -> dict[str, float]:
    """Recorder LSB per parameter (`lsb_mode` column of `analysis/dashlink_texture/results/param_table.csv`;
    port of round-1 `common.load_lsb`; [MEASURED] on Tail 687)."""
    t: dict[str, float] = {}
    with open(param_table_csv, newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                t[r["param"]] = float(r["lsb_mode"])
            except ValueError:
                t[r["param"]] = np.nan
    return t


def load_vrtg_affine(model_params_json: str | os.PathLike[str]) -> dict[str, tuple[float, float]]:
    """VRTG affine lattice (a, b) from round-1 `model_params_primary.json` (`fixed.lattice`; [MEASURED]
    687-CAL)."""
    import json

    with open(model_params_json) as fh:
        lat = json.load(fh)["fixed"]["lattice"]
    return {k: (float(v["a"]), float(v["b"])) for k, v in lat.items()}


def gate0_metadata(
    path: str | os.PathLike[str],
    *,
    lsb: Mapping[str, float],
    sentinels: Mapping[str, Sequence[float]],
    affine: Mapping[str, tuple[float, float]],
    allow_reserved: bool = False,
) -> tuple[np.ndarray, list[str]]:
    """G0 metadata vector of one DASHlink MAT file (round-1 `features.gate0` layout: record frames and
    seconds,
    then the GATE0_CHANNELS block)."""
    F = load_mat(path, allow_reserved=allow_reserved)
    return metadata_features(
        raw_channels(F, GATE0_CHANNELS),
        F["FRMC"].x.size,
        F["PH"].x.size,
        lsb={ch: lsb[ch] for ch in GATE0_CHANNELS},
        sentinels=sentinels,
        affine=affine,
    )
