"""M02 usage counting (A-W1.1-28): hand-counted PLA histories, hysteresis, and invariants (property tests)."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.scenario.usage import CRUISE, IDLE, MAX, OFF, count_usage, levels, rainflow_cycles


def _hist(*segments):
    """PLA (deg) history from (value, n_samples) pairs."""
    return np.concatenate([np.full(n, float(v)) for v, n in segments])


@pytest.mark.unit
def test_start_max_stop_is_one_type_i():
    u = count_usage(_hist((0, 4), (18, 10), (87, 10), (31, 10), (0, 4)), 1.0)
    assert (u.type1, u.type3, u.type4, u.ab_lights) == (1, 0, 0, 0)
    assert u.irp_s == 10.0 and u.tac == 1.0


@pytest.mark.unit
def test_idle_max_idle_inside_a_flight_is_type_iii():
    # start, takeoff (MAX), idle descent, MAX again, idle, shutdown
    u = count_usage(_hist((0, 2), (18, 5), (130, 5), (33, 5), (87, 5), (31, 5), (0, 2)), 1.0)
    assert (u.type1, u.type3, u.type4) == (1, 1, 0)
    assert u.ab_lights == 1 and u.ab_s == 5.0 and u.irp_s == 10.0
    assert u.tac == pytest.approx(1.25)


@pytest.mark.unit
def test_cruise_max_cruise_is_type_iv_and_tac_formula():
    u = count_usage(
        _hist((0, 2), (18, 5), (87, 5), (72, 5), (87, 5), (72, 5), (100, 3), (72, 5), (31, 5), (0, 2)), 1.0
    )
    assert (u.type1, u.type3, u.type4) == (1, 0, 2)
    assert u.tac == pytest.approx(1 + 2 / 40)
    assert u.ab_lights == 1


@pytest.mark.unit
def test_hysteresis_suppresses_chatter_at_the_idle_boundary():
    """PLA dithering +/- 1 deg around the 37 deg idle bound never creates a level change."""
    chatter = np.tile([36.5, 37.5], 50)
    lev = levels(np.concatenate([[31.0], chatter, [31.0]]))
    assert set(lev.tolist()) == {IDLE}
    # an AB dither just below and above 94 deg counts one light only
    u = count_usage(_hist((0, 1), (18, 2), (95, 1), (93, 1), (95, 1), (93, 1), (0, 1)), 1.0)
    assert u.ab_lights == 1


@pytest.mark.unit
def test_rainflow_on_level_sequences():
    assert sorted(rainflow_cycles(np.array([OFF, IDLE, MAX, IDLE, MAX, IDLE, OFF]))) == [
        (OFF, MAX),
        (IDLE, MAX),
    ]
    assert sorted(rainflow_cycles(np.array([OFF, MAX, CRUISE, MAX, OFF]))) == [(OFF, MAX), (CRUISE, MAX)]
    assert rainflow_cycles(np.array([OFF, IDLE, OFF])) == [(OFF, IDLE)]
    assert rainflow_cycles(np.array([])) == []


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(
    st.lists(
        st.tuples(st.sampled_from([18.0, 31.0, 50.0, 72.0, 87.0, 100.0, 130.0]), st.integers(1, 6)),
        min_size=1,
        max_size=30,
    )
)
def test_counting_invariants(segments):
    """For any start -> ... -> shutdown history: exactly one Type I iff MAX was reached; cycles of each type
    never exceed the number of MAX excursions; TAC follows its formula; AB time <= IRP time."""
    pla = _hist((0, 2), *segments, (0, 2))
    u = count_usage(pla, 0.5)
    lev = levels(pla)
    excursions = int(np.count_nonzero((lev[1:] == MAX) & (lev[:-1] != MAX)))
    assert u.type1 == (1 if excursions else 0)
    assert u.type1 + u.type3 + u.type4 == excursions
    assert u.tac == pytest.approx(u.type1 + u.type3 / 4 + u.type4 / 40)
    assert u.ab_s <= u.irp_s + 1e-12 and u.ab_lights <= excursions + int(np.count_nonzero(pla >= 94))
