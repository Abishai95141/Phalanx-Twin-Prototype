"""Phase sets stay consistent with the dictionary flight_phase table (dictionary 0.1.2 added codes 8-15)."""

from __future__ import annotations

import pytest

from phalanx.acquisition.config import AIRBORNE_PHASES
from phalanx.dictionary import load_dictionary

AIRBORNE = {"TAKEOFF", "CLIMB", "CRUISE", "APPROACH", "MISSION", "DESCENT", "PATTERN", "TOUCH_AND_GO"}


@pytest.mark.unit
def test_airborne_phases_cover_every_airborne_dictionary_phase():
    codes = load_dictionary().code_table("flight_phase")["codes"]
    names = {int(k): v for k, v in codes.items()}
    assert {names[c] for c in AIRBORNE_PHASES} == AIRBORNE


@pytest.mark.unit
def test_environment_category_c_includes_terminal_pattern_phases():
    from phalanx.environment.module import _cat_c_default
    from phalanx.scenario.phases import dictionary_phase_code

    cat_c = set(_cat_c_default())
    for n in ("TAKEOFF", "APPROACH", "ROLLOUT", "PATTERN", "TOUCH_AND_GO"):
        assert dictionary_phase_code(n) in cat_c, n


@pytest.mark.unit
def test_kernel_phase_range_covers_the_dictionary_table():
    """A phase code outside the kernel's range is silently read as UNKNOWN (the kernel clamps it to 0), so
    the range must cover every dictionary flight_phase code."""
    from phalanx.acquisition import kernel as K

    codes = load_dictionary().code_table("flight_phase")["codes"]
    assert max(int(k) for k in codes) < K.N_PHASE
