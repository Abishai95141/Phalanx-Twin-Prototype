"""Generate the boundary golden fixture: the ORIGINAL round-1/round-2 code on inputs placed on its thresholds.

Run once, read-only, in the round-2 environment:

    /Users/abishaikc/Phalanx/.venv-settling/bin/python -I \
        src/phalanx/validation/golden/make_round2_boundaries.py src/phalanx/validation/golden

Outputs: `round2_boundaries.npz` (arrays) and `round2_boundaries.json` (structure, hashes, scalar outputs),
read by
`tests/golden/test_validation_boundaries_golden.py`. Inputs come from `phalanx.validation.boundary_fixtures`
(bit-reproducible). Covered: per-flight statistics on the threshold flights, `transients.find_steps` on the
PLA
traces, the B3 (ii) cell minimum and the 2-flight minimum of `battery_eval.stat_value`,
`battery_eval.decision`,
`battery_eval.NB`, the round-1 `learn` models / folds / bootstrap, `features.gate0` on the G0 boundary
stand-in,
and `r2common` `_clean_mach`, `corrections`, `delta_static` and `load` on a small DASHlink-layout MAT file.
"""

from __future__ import annotations

import json
import platform
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "analysis" / "settling_experiment_round2" / "src"))

import battery_eval as BE  # noqa: E402  (round-2, read-only)
import features as FT  # noqa: E402  (round-1)
import learn as LN  # noqa: E402  (round-1)
import r2common as R  # noqa: E402
import scipy  # noqa: E402
from make_round2_golden import _P, _Pipe, old_stats  # noqa: E402
from transients import find_steps  # noqa: E402  (analysis/dashlink_texture, read-only)

from phalanx.validation.boundary_fixtures import (  # noqa: E402
    BOUNDARY_FLIGHTS,
    DECISION_PATTERNS,
    STEP_GROUPS,
    adapter_inputs,
    boundary_flight,
    gate0_boundary_channels,
    mach_trace,
    pla_traces,
    write_mat,
)
from phalanx.validation.testing import fixture_sha256  # noqa: E402

TESTS = ["B1_fast", "B1_slow", "B1h_fast", "B1h_slow", "B2", "B3i", "B3ii", "B4", "B5i", "B5ii", "B6"]
TEST_NAMES = ("B1", "B2", "B3", "B4", "B5", "B6")


def _jsonable(v):
    if v is None or isinstance(v, (str, bool, np.bool_)):
        return bool(v) if isinstance(v, np.bool_) else v
    if isinstance(v, (np.floating, float)):
        return float(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, np.ndarray):
        return [_jsonable(x) for x in v.tolist()]
    return repr(v)


def main(out_dir: str) -> None:
    out = Path(out_dir)
    arrays: dict[str, np.ndarray] = {}
    meta: dict[str, object] = {
        "generator": "src/phalanx/validation/golden/make_round2_boundaries.py",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
    }
    # per-flight statistics on the threshold flights
    stats = {}
    meta["inputs_sha256"] = {}
    for name in BOUNDARY_FLIGHTS:
        rec = boundary_flight(name)
        meta["inputs_sha256"][name] = fixture_sha256(rec)
        stats[name] = old_stats(rec)
        for k, v in stats[name].items():
            arrays[f"stats/{name}/{k}"] = v
    # find_steps on the PLA traces
    for name, pla in pla_traces().items():
        arrays[f"steps/{name}"] = np.array([(j, pm, qm) for j, pm, qm in find_steps(pla)], float).reshape(
            -1, 3
        )
    # evaluation layer: B3 (ii) cell minimum, 2-flight minimum, decision rule, resample count
    groups = {
        g: [{"b3_steps": np.array(rows, float).reshape(-1, 3), "air_frac": np.array(1.0)} for rows in fl]
        for g, fl in STEP_GROUPS.items()
    }
    meta["b3ii"] = {
        "A_vs_B": BE.stat_value("B3ii", groups["A"], groups["B"]),
        "B_vs_A": BE.stat_value("B3ii", groups["B"], groups["A"]),
        "tau_A": BE.group_values(groups["A"])["B3ii_median_tau"],
        "tau_B": BE.group_values(groups["B"])["B3ii_median_tau"],
    }
    one = ([stats["air600"]], [stats["run2400"]])
    two = ([stats["air600"], stats["ph40"]], [stats["run2400"], stats["n1_edge"]])
    meta["min_flights"] = {
        "one": {t: BE.stat_value(t, *one) for t in TESTS},
        "two": {t: BE.stat_value(t, *two) for t in TESTS},
    }
    meta["decision"] = {
        name: BE.decision({t: {"verdict": v} for t, v in zip(TEST_NAMES, vs, strict=True)}, g0)
        for name, (vs, g0) in DECISION_PATTERNS.items()
    }
    meta["NB"] = BE.NB
    # round-1 learn: model hyper-parameters, folds, bootstrap index sets
    lr = LN.make_model("lr").get_params(deep=True)
    gb = LN.make_model("gb", 0).get_params()
    meta["learn"] = {
        "K": LN.K,
        "REPEATS": LN.REPEATS,
        "lr": {k: _jsonable(v) for k, v in lr.items() if isinstance(v, (int, float, str, bool, type(None)))},
        "gb": {k: _jsonable(v) for k, v in gb.items() if k != "random_state"},
    }
    groups_rows = np.repeat(np.arange(13), 2)
    for r, fl in enumerate(LN.folds(groups_rows, 11)):
        arrays[f"learn/fold_of/{r}"] = np.sum([k * te for k, (_, te) in enumerate(fl)], axis=0).astype(
            np.int64
        )
    y = np.r_[np.zeros(9, int), np.ones(9, int)]
    pid = np.r_[np.arange(9), np.arange(9)]
    arrays["learn/boot_paired"] = np.array(LN.boot_indices(y, pid, 7, 3), np.int64)
    arrays["learn/boot_unpaired"] = np.array(LN.boot_indices(y, None, 7, 3), np.int64)
    # G0 metadata on the boundary stand-in
    ch, frames, rec_s = gate0_boundary_channels()
    F = {name: _P(raw, rate) for name, (raw, rate) in ch.items()}
    F["FRMC"] = _P(np.arange(frames, dtype=np.float32), 0.25)
    F["PH"] = _P(np.zeros(rec_s, np.float32), 1.0)
    g0 = FT.gate0(F, _Pipe())
    arrays["g0/boundary"] = np.array([v for _, _, v in g0], np.float64)
    meta["g0_names"] = [nm for _, nm, _ in g0]
    # DASHlink adapter (r2common)
    a = adapter_inputs()
    arrays["adapter/clean_mach"] = R._clean_mach(mach_trace())
    th, de = R.corrections(a["alt"], a["mach"], a["tat"])
    arrays["adapter/theta"], arrays["adapter/delta"] = th, de
    arrays["adapter/delta_static"] = R.delta_static(a["alt"])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "652209901010000.mat"
        write_mat(p)
        d = R.load(str(p))
    meta["adapter_load"] = {"fid": d["fid"], "n": d["n"]}
    for k in ("PLA", "theta", "delta", "PH", "ALT", "MACH", "TAT"):
        arrays[f"adapter/load/{k}"] = np.asarray(d[k])
    for f in R.FAM:
        arrays[f"adapter/load/Y/{f}"] = np.asarray(d["Y"][f])
    np.savez_compressed(out / "round2_boundaries.npz", **arrays)
    with open(out / "round2_boundaries.json", "w") as fh:
        json.dump(_jsonable(meta), fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("wrote", out / "round2_boundaries.npz", len(arrays), "arrays")


if __name__ == "__main__":
    main(sys.argv[1])
