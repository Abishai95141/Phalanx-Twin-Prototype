"""W2.3a item 1 (A-W2.3-3): N2-governor gain-schedule margin vs the damping of the largest idle disturbance.

For each ``gov_ks_margin`` the M08 tables are re-derived from the worktree's M07 (``harmonise``; only
``gov_ks`` depends on the margin) and the W2.5 idle step is run on the M07 + M08 TEST FIXTURE loop
(``tests/engine_fadec_loop.py``): healthy no-load idle trim, M09's nominal idle loads (harm_bleed, harm_pto)
and each B7 deterioration (plus healthy and the build band) stepped in at t = 0, 30 s, no disturbance draws.
Reported per case: the first sag, overshoot = peak positive N2 error after the sag / |sag|, the
second-order-equivalent damping ratio zeta = -ln(OS) / sqrt(pi^2 + ln(OS)^2) and the time after which
|N2 error| stays below 0.2 %. Criterion (GM > 6 dB / PM > 45 deg of C-MAPSS40k's scheduled setpoint loops,
f404 notes Q4): OS < 23 % (zeta > 0.42) in every case. Then a 1 s, 3 % shaft-load kick at the integrated
aircraft's idle loads (35 kW, 0.54 kg/s): N2 deviation peak per 10 s.

Sample: 9 deterministic step runs x 30 s per margin (every B7 case, healthy, build) + 1 kick run x 40 s; the
margins 2.5, 4, 5, 6 bracket the criterion.

Usage: python -I gov_margin_sweep.py OUT.json [margins, default 2.5,4,5,6]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for sub in ("src", "tests", "tests/integration"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))


def main(argv: list[str]) -> None:
    import test_fadec_accel_margin as T

    import engine_fadec_loop as L
    from phalanx.engine.module import EngineModule
    from phalanx.fadec import load_fadec_params
    from phalanx.fadec.harmonise import config_from, harmonise

    margins = [float(v) for v in (argv[1] if len(argv) > 1 else "2.5,4,5,6").split(",")]
    eng = EngineModule("eng")
    out: dict = {"criterion": "overshoot < 0.23 (zeta > 0.42) for every case", "margins": {}}
    for m in margins:
        h = harmonise(eng.model, load_fadec_params().replace(gov_ks_margin=m))
        cfg = config_from(h, T.CFG)
        x, g = h.tables["gov_ks"][1]
        rows = {}
        for case, d in [("healthy", (0.0,) * 10), *T.b7_deltas().items()]:
            run, target = T._step_run(eng, cfg, d, secs=30)
            err = run.ch("n2") / L.N2R / (float(target.engine.x[1]) / L.N2R) - 1.0
            k = int(np.argmin(err))
            os_ = max(0.0, float(err[k:].max())) / abs(float(err[k]))
            lo = np.log(max(os_, 1e-6))
            out_band = np.flatnonzero(np.abs(err) > 2e-3)
            rows[case] = {
                "sag_pct": round(100 * float(err[k]), 3),
                "overshoot": round(os_, 3),
                "zeta": round(float(-lo / np.sqrt(np.pi**2 + lo**2)), 3),
                "settle_0p2pct_s": round(float(out_band[-1]) / 240.0, 2) if out_band.size else 0.0,
            }
        dev, _lim = T._kick_run(eng, cfg, T.INTEGRATED, secs=40)
        out["margins"][str(m)] = {
            "gain_at_idle_n2c_0p666": round(float(np.interp(0.666, x, g)), 3),
            "gain_max": round(float(g.max()), 3),
            "step": rows,
            "max_overshoot": max(r["overshoot"] for r in rows.values()),
            "integrated_kick_dev_pct_per_10s": [
                round(100 * float(dev[i : i + 2400].max()), 4) for i in (0, 2400, 4800, 7200)
            ],
        }
        print(m, json.dumps(out["margins"][str(m)]), flush=True)
    Path(argv[0]).write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
