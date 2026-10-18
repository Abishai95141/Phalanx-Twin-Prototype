"""W2.4a-2 stage 5, plant re-run: stage 2 of ``st5_ident.py`` (plant inertias and word lags on the A/T
windows) with the committed governor gains (2, 1 1/s) instead of stage 1's manual-window estimate, which
failed the Jacobian step-consistency check (A-W2.4a-20: relative difference 4.1 for gov_kp, 0.54 for
gov_ki between FD steps 1e-4 and 4e-4 - the accel / decel schedules switch inside the approach windows),
so it is not adopted. The autothrottle gains are stage 0's.

Usage::

    $PY -I analysis/proxy_quicklook/code/st5_plant_rerun.py <mat_dir> <ident.json> <out> [workers] [iters]
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

from st5_ident import AT, PLANT, stage


def main(mat_dir: str, ident_json: str, out: str, workers: int = 5, max_iter: int = 6) -> None:
    with open(ident_json) as fh:
        r = json.load(fh)
    held = dict(r["nominal"])
    held.update(dict(zip(AT, r["stage0"]["free"]["theta"], strict=True)))
    res = {"held": held, "segments": r["kept"]["at"]}
    res["stage2"] = stage(
        mat_dir, r["kept"]["at"], PLANT, held, [0, 1, 2, 3], workers, max_iter, "2 plant", prior=True
    )
    res["identified_free"] = {**held, **dict(zip(PLANT, res["stage2"]["free"]["theta"], strict=True))}
    res["identified_prior"] = {**held, **dict(zip(PLANT, res["stage2"]["prior"]["theta"], strict=True))}
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], *(int(x) for x in sys.argv[4:6]))
