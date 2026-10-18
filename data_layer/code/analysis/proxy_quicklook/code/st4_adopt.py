"""W2.4a-2 stage 4: write the identified disturbance bank into the proxy M03 configuration.

The bank of ``results/stage4/st4_fit.json`` (one setting) becomes the engine-group factors of
``configs/proxy_dashlink/params/M03/disturbance_factors.csv`` exactly as ``runner.bank_factors`` builds them
for the full-chain verification: per channel (fuel metering, combustor efficiency, inlet recovery, HP shaft
load, fan_face = LP shaft torque) one aircraft-common and one per-unit first-order OU factor with the
channel's correlation time, loadings SD x sqrt(common share) and SD x sqrt(1 - share), clipped to the
declared ranges; factor ids 101-110 (their own RNG streams). The hydraulic factors are kept. The W1
placeholder engine factors 1-7 and 10-11 are removed - including the bleed/PTO channel loadings of factors 1
and 7, which the identification does not cover (the verified runs ran without them).

Usage::

    $PY -I analysis/proxy_quicklook/code/st4_adopt.py <st4_fit.json> <setting tag>
"""

from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

from runner import bank_factors, base_config

from phalanx.environment.disturbances import ENGINE_CHANNELS
from phalanx.proxy.config import PLATFORM, config_root

COLS = ("l_fuel", "l_comb", "l_inlet", "l_shaft", "l_fan", "l_bleed")


def main(fit_json: str, tag: str) -> None:
    with open(fit_json) as fh:
        r = json.load(fh)["settings"][tag]
    bank = {c: {k: b[k] for k in ("sd", "rho", "tau")} for c, b in r["bank"].items()}
    factors = bank_factors(base_config(), bank)
    path = config_root() / PLATFORM / "params" / "M03" / "disturbance_factors.csv"
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
        header = list(rows[0])
    hyd = [row for row in rows if int(row["group"]) == 1]
    out = []
    for f in factors:
        if f.group == 1:
            continue
        row = {"fid": f.fid, "scope": f.scope, "group": f.group, "form": f.form, "tau_s": f"{f.tau_s:.6g}",
               "omega_rad_s": 0.0, "zeta": 0.0, "l_hyd": 0.0}  # fmt: skip
        for c, name in zip(COLS, ENGINE_CHANNELS, strict=True):
            row[c] = f"{f.loadings[ENGINE_CHANNELS.index(name)]:.6g}"
        out.append(row)
    out += hyd
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        w.writeheader()
        for row in out:
            w.writerow(row)
    print(f"wrote {len(out)} factors to {path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
