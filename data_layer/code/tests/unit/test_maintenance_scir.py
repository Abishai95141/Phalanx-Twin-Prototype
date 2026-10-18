"""SCIR availability arithmetic (architecture §10, AD-20; NAMP 4790.2E §9.2) - A1."""

from __future__ import annotations

import pytest

from phalanx.maintenance import scir
from phalanx.maintenance.scir import (
    FMC,
    NMCD,
    NMCM_S,
    NMCM_U,
    NMCS,
    PMCM,
    PMCS,
    TailFlags,
    bin_states,
    instantaneous_state,
    kpis_from_occupancy,
    occupancy,
)

H = 3600


@pytest.mark.unit
def test_precedence_is_namp_order():
    # NAMP: NMCD > NMCS > NMCM-U > NMCM-S > PMCS > PMCM (> FMC)
    order = [NMCD, NMCS, NMCM_U, NMCM_S, PMCS, PMCM, FMC]
    assert order == sorted(order, reverse=True)
    assert scir.STATES[NMCD] == "NMCD" and scir.STATES[FMC] == "FMC"


@pytest.mark.unit
def test_instantaneous_state_takes_the_highest_degraded_flag():
    assert instantaneous_state(TailFlags()) == FMC
    assert instantaneous_state(TailFlags(partial_open=True)) == PMCM
    assert instantaneous_state(TailFlags(partial_open=True, partial_awp=True)) == PMCS
    assert instantaneous_state(TailFlags(grounding_scheduled=True, partial_awp=True)) == NMCM_S
    assert instantaneous_state(TailFlags(grounding_unscheduled=True, grounding_scheduled=True)) == NMCM_U
    assert instantaneous_state(TailFlags(grounding_awp=True, grounding_unscheduled=True)) == NMCS
    assert instantaneous_state(TailFlags(at_depot=True, grounding_awp=True)) == NMCD


@pytest.mark.unit
def test_namp_worked_example():
    """NAMP §9.2 worked example: 12 aircraft in April, EIS 7,680 h, MC 62.5 %, FMC 30.0 %."""
    eis = 7680 * H
    nmc = int(0.375 * eis)
    pmc = int((0.625 - 0.30) * eis)
    occ = [0] * len(scir.STATES)
    occ[FMC] = eis - nmc - pmc
    occ[PMCM] = pmc
    occ[NMCM_U] = nmc
    k = kpis_from_occupancy([occ])
    assert k.mc == pytest.approx(0.625) and k.fmc == pytest.approx(0.30)


@pytest.mark.unit
def test_bins_take_the_worst_state_of_the_bin_and_carry_state_forward():
    w = 900
    changes = [(100, NMCM_U), (950, FMC), (2000, PMCM), (2010, FMC), (2700, NMCS)]
    b = bin_states(changes, 0, 3600, w)
    assert b == [(0, NMCM_U), (900, NMCM_U), (1800, PMCM), (2700, NMCS)]
    # carried state persists across empty bins; a change exactly at a boundary belongs to that bin
    b2 = bin_states([(0, NMCS), (1800, FMC)], 0, 3600, w)
    assert b2 == [(0, NMCS), (900, NMCS), (1800, NMCS), (2700, FMC)]
    occ = occupancy(b, w)
    assert sum(occ) == 3600 and occ[NMCM_U] == 1800
