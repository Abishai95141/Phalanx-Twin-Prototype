"""W1.1 A1 (second half): MIL-HDBK-310 climatic-extreme profiles reproduced.

Data-pending (A-W1.1-15): the MIL-HDBK-310 tables (public, distribution A) are not in the evidence base; the
research notes cite only the MathWorks implementation (modelling_methodology.md §1, Gaps: "full texts were
not read directly"). The design-day mechanism (table altitude = pressure altitude, JSSG-2007A Fig. 5 note 4)
is built and tested in tests/unit/test_environment_atmosphere.py. This test is the golden reproduction and
expects a transcription at configs/tejas/params/M03/mil_hdbk_310_profiles.csv with columns
``profile, pressure_alt_m, t_k`` (profile codes: 1 hot 1 %, 2 hot 10 %, 3 cold 1 %, 4 cold 10 %, ...).
It fails until the coordinator adds the tables (XPASS then flags removal of the mark).
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from phalanx.environment.atmosphere import design_day_profile, geometric_altitude, moist_state
from phalanx.environment.config import load_env_config

TABLE = (
    Path(__file__).resolve().parents[2] / "configs" / "tejas" / "params" / "M03" / "mil_hdbk_310_profiles.csv"
)


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    raises=FileNotFoundError,
    reason="data pending (A-W1.1-15): the MIL-HDBK-310 tables (public, distribution A) are not in the "
    "evidence base, so the transcription file is absent. Data owner: the coordinator (obtains the handbook "
    "into research_sources and commits configs/tejas/params/M03/mil_hdbk_310_profiles.csv); any other "
    "failure is a real error, not this xfail",
)
def test_mil_hdbk_310_profiles_reproduced():
    cfg = load_env_config()
    rows = list(csv.DictReader(TABLE.open(encoding="utf-8")))
    profiles = sorted({int(r["profile"]) for r in rows})
    assert len(profiles) >= 4
    for code in profiles:
        sel = [r for r in rows if int(r["profile"]) == code]
        hp = np.array([float(r["pressure_alt_m"]) for r in sel])
        t = np.array([float(r["t_k"]) for r in sel])
        prof, n = design_day_profile(hp, t, cfg.layers, cfg.constants)
        for k in range(n):
            z = geometric_altitude(prof[0, k], cfg.constants.r0)
            tt, *_ = moist_state(prof, n, z, cfg.constants.vector(), cfg.magnus)
            assert tt == pytest.approx(t[k], abs=1e-6)
