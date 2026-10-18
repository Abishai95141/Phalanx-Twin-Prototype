"""Generate the data-free golden fixture: the ORIGINAL round-2 estimator code run on control flights.

Run once, read-only, in the round-2 environment (it imports the pre-registered code from `analysis/`):

    /Users/abishaikc/Phalanx/.venv-settling/bin/python -I \
        src/phalanx/validation/golden/make_round2_golden.py src/phalanx/validation/golden

Outputs (committed, small): `round2_golden.npz` (arrays) and `round2_golden.json` (structure, verdicts, input
hashes, environment). `tests/golden/test_validation_battery_golden.py` regenerates the same control flights in
the build environment, checks their SHA-256 against the fixture, and compares the port with these outputs.

Side effects of importing the round-2 modules: they create cache directories under
`<checkout>/research_sources/`
(git-ignored). Nothing under `analysis/` is written.
"""

from __future__ import annotations

import io
import json
import platform
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "analysis" / "settling_experiment_round2" / "src"))

import battery as BT  # noqa: E402  (round-2, read-only)
import battery_eval as BE  # noqa: E402
import features as FT  # noqa: E402  (round-1, via r2common's sys.path)
import r2common as R  # noqa: E402
import s04_stats as S4  # noqa: E402
import s07_gate0 as G0OLD  # noqa: E402
import scipy  # noqa: E402
import sklearn  # noqa: E402

from phalanx.validation.testing import (  # noqa: E402
    PARTNER_TAIL,
    REFERENCE_TAIL,
    STANDIN_AFFINE,
    STANDIN_LSB,
    STANDIN_SENTINELS,
    control_flight,
    delay_family,
    fixture_sha256,
    g0_control_matrices,
    gate0_standin,
)

N_PER_GROUP = 4
N_BOOT = 100
G0_ROWS = 40


def groups() -> dict[str, list]:
    """Control-flight groups: holdout and partner (another toy tail), and three paired arms (a replicate of
    the
    same tail, the other tail on the same inputs, and the holdout with FF delayed by 2 s: an exact array
    shift)."""
    H = [control_flight(i, REFERENCE_TAIL, "real") for i in range(N_PER_GROUP)]
    return {
        "holdout": H,
        "partner": [control_flight(100 + i, PARTNER_TAIL, "real") for i in range(N_PER_GROUP)],
        "arm_replicate": [control_flight(i, REFERENCE_TAIL, "replicate") for i in range(N_PER_GROUP)],
        "arm_partner_tail": [control_flight(i, PARTNER_TAIL, "sim") for i in range(N_PER_GROUP)],
        "arm_ff_delay": [delay_family(r, "FF", 2.0) for r in H],
    }


def old_stats(rec) -> dict[str, np.ndarray]:
    """Round-2 `s04_stats.job` on an in-memory flight, round-tripped through npz exactly as round 2 did."""
    Y = {f: np.asarray(rec.outputs[f]) for f in R.FAM}
    d = {
        "n": rec.n,
        "PLA": np.asarray(rec.pla),
        "theta": np.asarray(rec.theta),
        "delta": np.asarray(rec.delta),
        "PH": np.asarray(rec.phase),
    }
    st = BT.flight_stats(Y, d)
    z = {"air_frac": np.array(st["air_frac"])}
    for k in ("b1_slow", "b1_fast", "b1h_slow", "b1h_fast", "b2", "b3_coh", "b3_lgain", "b4", "b6"):
        if st[k] is not None:
            z[k] = np.asarray(st[k], float)
    z["b3_steps"] = np.array([(S4.RESP[g], S4.DIRS[dr], t) for g, dr, t in st["b3_steps"]], float).reshape(
        -1, 3
    )
    if st["b5"] is not None:
        mf, me = st["b5"]
        for k, v in mf.items():
            z[f"b5_ff_{k}"] = np.asarray(v, float)
        for k, v in me.items():
            z[f"b5_egt_{k}"] = np.asarray(v, float)
    z.update(S4.g1_counts({f: Y[f] for f in R.FAM}))
    buf = io.BytesIO()
    np.savez(buf, **z)
    buf.seek(0)
    with np.load(buf, allow_pickle=False) as zz:
        return {k: zz[k] for k in zz.files}


class _P:
    """Minimal stand-in for round-1 `dlio.Param` (raw, x, rate) to call `features.gate0`."""

    def __init__(self, raw: np.ndarray, rate: float) -> None:
        self.raw = raw
        self.x = raw.astype(float)
        self.rate = rate


class _Pipe:
    """Minimal stand-in for round-1 `pipeline.Pipe` holding the stand-in tables of
    `phalanx.validation.testing`."""

    def __init__(self) -> None:
        self.sent = STANDIN_SENTINELS
        self.lsb = STANDIN_LSB
        self.lattice = {k: {"a": a, "b": b} for k, (a, b) in STANDIN_AFFINE.items()}

    def sentinel_mask(self, name, x):
        from pipeline import Pipe

        return Pipe.sentinel_mask(self, name, x)

    def lattice_frac(self, name, v):
        from pipeline import Pipe

        return Pipe.lattice_frac(self, name, v)


def gate0_file(rec, dtype: str) -> dict:
    """Round-1 `load_flight`-like dict of the shared G0 stand-in (`testing.gate0_standin`)."""
    ch, frames, rec_s = gate0_standin(rec, dtype)
    F = {name: _P(raw, rate) for name, (raw, rate) in ch.items()}
    F["FRMC"] = _P(np.arange(frames, dtype=np.float32), 0.25)
    F["PH"] = _P(np.zeros(rec_s, np.float32), 1.0)
    return F


def main(out_dir: str) -> None:
    out = Path(out_dir)
    G = groups()
    arrays: dict[str, np.ndarray] = {}
    meta: dict[str, object] = {
        "generator": "src/phalanx/validation/golden/make_round2_golden.py",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "sklearn": sklearn.__version__,
        },
        "n_per_group": N_PER_GROUP,
        "n_boot": N_BOOT,
        "bootstrap_seed": R.ROOT_SEED,
        "inputs_sha256": {g: [fixture_sha256(r) for r in recs] for g, recs in G.items()},
    }
    S = {g: [old_stats(r) for r in recs] for g, recs in G.items()}
    for g, lst in S.items():
        for i, z in enumerate(lst):
            for k, v in z.items():
                arrays[f"stats/{g}/{i}/{k}"] = v
    # battery with the round-2 protocol order: tail, temp, then arms (paired, "holdout" draws)
    boot = BE.Bootstrap(R.ROOT_SEED, nb=N_BOOT)
    SH, SP = S["holdout"], S["partner"]
    early, late = [0, 1], [2, 3]
    tail = BE.compare(SP, SH, "partner", "holdout", False, boot, real_is_B=True)
    temp = BE.compare(
        [SH[i] for i in late], [SH[i] for i in early], "late", "early", False, boot, real_is_B=True
    )
    meta["early"], meta["late"] = early, late
    battery: dict[str, object] = {"D_tail": {}, "D_temp": {}, "arms": {}}
    for name, cmp in (("D_tail", tail), ("D_temp", temp)):
        for t, v in cmp.items():
            battery[name][t] = float(v["D"])
            arrays[f"boot/{name}/{t}"] = np.asarray(v["boot"], float)
    for arm in ("arm_replicate", "arm_partner_tail", "arm_ff_delay"):
        sim = BE.compare(S[arm], SH, "holdout", "holdout", True, boot)
        ver = BE.verdicts(sim, tail, temp)
        battery["arms"][arm] = {
            "D_sim": {t: float(v["D"]) for t, v in sim.items()},
            "verdicts": ver,
            "group": BE.group_values(S[arm]),
            "G1": BE.g1(S[arm], SH),
        }
        for t, v in sim.items():
            arrays[f"boot/{arm}/{t}"] = np.asarray(v["boot"], float)
    meta["battery"] = battery
    meta["groups"] = {"holdout": BE.group_values(SH), "partner": BE.group_values(SP)}
    # G0: metadata vectors of recorded-file stand-ins and the audit on synthetic metadata matrices
    pipe = _Pipe()
    for i, rec in enumerate(G["holdout"][:2]):
        for dt in ("float32", "float64"):
            g0 = FT.gate0(gate0_file(rec, dt), pipe)
            arrays[f"g0file/{i}/{dt}"] = np.array([v for _, _, v in g0], np.float64)
            meta["g0_feature_names"] = [nm for _, nm, _ in g0]
    M = g0_control_matrices(G0_ROWS)
    names = [str(x) for x in M["names"]]
    for k in ("null_A", "null_B", "sep_A", "sep_B"):
        arrays[f"g0matrix/{k}"] = M[k]
    meta["g0_matrix_names"] = names
    meta["g0_audit"] = {
        "identical": G0OLD.evaluate(M["null_A"], M["null_A"].copy(), True, names, 11, sub=True),
        "null": G0OLD.evaluate(M["null_A"], M["null_B"], True, names, 11, sub=True),
        "separable": G0OLD.evaluate(M["sep_A"], M["sep_B"], True, names, 11, sub=True),
    }
    np.savez_compressed(out / "round2_golden.npz", **arrays)
    with open(out / "round2_golden.json", "w") as fh:
        json.dump(meta, fh, indent=1, default=float, sort_keys=True)
        fh.write("\n")
    print("wrote", out / "round2_golden.npz", len(arrays), "arrays;", out / "round2_golden.json")


if __name__ == "__main__":
    main(sys.argv[1])
