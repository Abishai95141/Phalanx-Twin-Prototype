"""Design drift guard (A-W1.2-22): the committed M05 gain tables are the output of ``fcs.design`` on the
committed M06 aero and M05 design settings. Any change to the aero tables, the mass properties or the design
settings that is not followed by a regeneration (``python -I -c "...design import main; main([...])"``) fails
here.

Deterministic subset (re-running the full 144-point design takes ~8 min): n = 3 schedule points spanning the
q-integral, blended-free transonic and Nz-integral regimes, plus the gear-up fixed-gain set.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from phalanx.airframe.build import airframe_param_set, build_config
from phalanx.fcs.build import fcs_param_set, settings_from_params
from phalanx.fcs.design import GAIN_COLUMNS, design_point

M05 = Path(__file__).resolve().parents[2] / "configs" / "tejas" / "params" / "M05"
POINTS = [(0.4, 2000.0), (0.85, 4000.0), (1.2, 10000.0)]


def _rows(name):
    with open(M05 / name, encoding="utf-8") as fh:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(fh)]


@pytest.mark.integration
def test_committed_gains_equal_the_design_output():
    fps = fcs_param_set()
    s = settings_from_params(fps)
    aps = airframe_param_set()
    cfg = build_config(aps, 1)
    afeas = float(fps.value("alpha_feasible"))
    table = {(r["mach"], r["alt"]): r for r in _rows("gains.csv")}
    for mach, alt in POINTS:
        gains, m, w_sp, ok = design_point(cfg, aps, mach, alt, s, alpha_feasible=afeas)
        row = table[(mach, alt)]
        assert ok and row["feasible"] == 1.0
        for k in GAIN_COLUMNS:
            assert gains[k] == pytest.approx(row[k], rel=1e-9, abs=1e-12), (mach, alt, k)
        assert w_sp == row["w_sp"] and m.gm_db == pytest.approx(row["gm_db"], rel=1e-9)
    up = next(r for r in _rows("fixed_gains.csv") if r["gear"] == 0.0)
    gains, _m, _w, ok = design_point(
        cfg,
        aps,
        float(fps.value("fixed_up_mach")),
        float(fps.value("fixed_up_alt")),
        s,
        gear=0.0,
        force_w=0.0,
    )
    assert ok
    for k in GAIN_COLUMNS:
        assert gains[k] == pytest.approx(up[k], rel=1e-9, abs=1e-12), k
