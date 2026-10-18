"""B7-LG M09 side (PREREGISTRATION.md §3): the real M09 module driven through the reference landing roll.

The reference landing is the one M10's usage-mode surrogate is calibrated to (W2.1c, A-W2.1c-5; M10
``brake_energy_ref`` 3.96 MJ per wheel): a 9 t aircraft at 75 m/s touchdown decelerating at 2 m/s^2, brakes
absorbing 35 % of the deceleration force in four applications (the M09 W1.4 typical landing). BENCH BOUNDARY:
the landing kinematics (wheel speed, brake power, weight on wheels) are prescribed, as M06 would produce them;
M09's heat sink, wear and tyre models are the real ones.

Outputs: brake and tyre wear per landing (-> life), the brake energy per wheel (vs 3.96 MJ), and the peak
heat-sink temperature after the reference stop at wear 0.1 and 0.9 (TFG (c) #33: per-stop temperature rises
as the carbon mass falls).

Usage: python -I landing.py OUT_DIR
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phalanx.core.rng import KeyPath, RngService, StreamRegistry  # noqa: E402
from phalanx.core.time import TRUTH_DT_S  # noqa: E402
from phalanx.utilities import UtilitiesConfig, load_m09_params  # noqa: E402
from phalanx.utilities import layout as L  # noqa: E402
from phalanx.utilities.module import Utilities  # noqa: E402

G0 = 9.80665
N2_100 = 16810.0 * 2.0 * np.pi / 60.0
PS = load_m09_params()
R_TYRE = float(PS.value("tyre_r"))
MASS, V0, DECEL, SHARE, APPS = 9000.0, 75.0, 2.0, 0.35, 4


def _inputs(n: int, *, wow, tas, pbrk, wheel, health) -> dict[str, np.ndarray]:
    def col(v, w):
        a = np.asarray(v, np.float64)
        return np.tile(a, (n, 1)) if a.ndim == 1 and a.size == w else np.broadcast_to(a, (n, w)).copy()

    return {
        "n2": np.full((n, 1), 0.70 * N2_100),
        "bleed_p3": np.full((n, 1), 3.0e5),
        "bleed_t3": np.full((n, 1), 500.0),
        "wf": np.full((n, 1), 0.1),
        "wf_ab": np.zeros((n, 1)),
        "hyd_flow_demand": np.zeros((n, 2)),
        "f_spec_body": col([0.0, 0.0, -G0], 3),
        "tas": np.broadcast_to(np.asarray(tas, np.float64), (n,)).copy(),
        "mach": np.broadcast_to(np.asarray(tas, np.float64) / 340.3, (n,)).copy(),
        "wow": col(np.asarray(wow, np.float64), 3).astype(np.int64),
        "wheel_speed": col(np.asarray(wheel, np.float64), 2) if np.ndim(wheel) == 1 else np.asarray(wheel),
        "brake_energy_rate": np.asarray(pbrk, np.float64) if np.ndim(pbrk) == 2 else col(pbrk, 2),
        "t_s": np.full(n, 288.15),
        "p_s": np.full(n, 101325.0),
        "rho": np.full(n, 1.225),
        "w_hyd": np.zeros((n, 2)),
        "w_bleed_pto": np.zeros((n, 1)),
        "health_utility": np.tile(health, (n, 1)),
    }


def reference_landing(wear: float, cool_s: float = 60.0) -> dict:
    m = Utilities("util", PS, n_engines=1, config=UtilitiesConfig(soak_temp=288.15))
    m.bind(RngService(0xB71A, StreamRegistry(m.streams)).scope(KeyPath.of(scenario="B7LG", tail="T1", sortie=1)))
    st = m.init(PS, None)
    h = np.zeros(L.N_HEALTH)
    h[L.H_BRAKE_WEAR : L.H_BRAKE_WEAR + 2] = wear
    n = round(V0 / DECEL / TRUTH_DT_S)
    v = np.maximum(V0 - DECEL * np.arange(n) * TRUTH_DT_S, 0.0)
    seg = n // APPS
    on = (np.arange(n) % seg) < 0.8 * seg
    pw = 0.5 * SHARE * MASS * DECEL * v * on
    k = 0
    # one airborne tick so the touchdown counts as a landing
    st, _ = m.step_block(st, _inputs(1, wow=(0, 0, 0), tas=V0, pbrk=(0.0, 0.0), wheel=(0.0, 0.0), health=h),
                         np.arange(k, k + 1, dtype=np.int64), TRUTH_DT_S)
    k += 1
    inp = _inputs(n, wow=(1, 1, 1), tas=v, pbrk=np.stack([pw, pw], 1), wheel=np.stack([v / R_TYRE] * 2, 1),
                  health=h)
    st, out = m.step_block(st, inp, np.arange(k, k + n, dtype=np.int64), TRUTH_DT_S)
    k += n
    nc = int(cool_s / TRUTH_DT_S)
    st, cool = m.step_block(st, _inputs(nc, wow=(1, 1, 1), tas=0.0, pbrk=(0.0, 0.0), wheel=(0.0, 0.0), health=h),
                            np.arange(k, k + nc, dtype=np.int64), TRUTH_DT_S)
    t_hist = np.concatenate([out["brake_t"], cool["brake_t"]])
    wear_acc = m.sortie_wear(st)
    return {
        "wear": wear,
        "brake_energy_per_wheel_j": float(np.sum(pw) * TRUTH_DT_S),
        "brake_wear_per_landing": float(st["f"][L.F_BRK_DW]),
        "tyre_wear_per_landing": float(st["f"][L.F_TYRE_DW]),
        "peak_brake_t_k": float(t_hist.max()),
        "sortie_wear": {k2: [float(x) for x in np.atleast_1d(v2)] for k2, v2 in wear_acc.items()},
    }


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    res = {"low_wear": reference_landing(0.1), "high_wear": reference_landing(0.9)}
    low = res["low_wear"]
    res["brake_life_landings"] = 1.0 / low["brake_wear_per_landing"]
    res["tyre_life_landings"] = 1.0 / low["tyre_wear_per_landing"]
    (out / "b7_landing.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
