"""Proxy-mode replay adapter (M02): FlightRecord-like arrays -> ReplayInputs -> ScenarioReplay phase/epoch."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.scenario.replay import ReplayInputs, ScenarioReplay
from phalanx.validation.flightdata import FlightRecord


def _record(n=40, rate=4.0):
    pla = np.vstack([np.linspace(20, 80, n), np.linspace(21, 81, n)])
    phase = np.repeat(np.array([1, 2, 3, 4, 5]), n // 5)
    return FlightRecord(
        flight_id="F1",
        rate_hz=rate,
        outputs={"N1": np.zeros((2, n))},
        pla=pla,
        theta=np.ones(n),
        delta=np.ones(n),
        phase=phase,
        t0_ns=0,
    )


@pytest.mark.unit
def test_replay_inputs_from_flight_record_and_zero_order_hold():
    rec = _record()
    n = rec.n
    ri = ReplayInputs.from_flight_record(
        rec,
        pressure_alt_m=np.linspace(0, 3000, n),
        mach=np.full(n, 0.5),
        tat_k=np.full(n, 280.0),
        epoch_utc_ns=7 * 10**18,
        at_engage=np.ones(n, np.int64),
        at_n1_cmd_pct=np.full((2, n), 85.0),
    )
    assert ri.n_engines == 2 and ri.n == n
    assert ri.pla_rad[0, 0] == pytest.approx(20 * np.pi / 180)
    assert np.allclose(ri.at_n1_cmd, 0.85)
    # zero-order hold: sample k covers [k/4 s, (k+1)/4 s)
    assert list(ri.index(np.array([0, 249_999_999, 250_000_000, 10**12]))) == [0, 0, 1, n - 1]
    with pytest.raises(ContractError):
        ReplayInputs(
            0,
            4.0,
            0,
            np.zeros((1, 3)),
            np.zeros(2),
            np.zeros(3),
            np.zeros(3),
            np.zeros(3),
            np.zeros(3),
            np.zeros((1, 3)),
        )


@pytest.mark.unit
def test_scenario_replay_serves_recorded_phase_and_epoch():
    rec = _record()
    ri = ReplayInputs.from_flight_record(
        rec,
        pressure_alt_m=np.zeros(rec.n),
        mach=np.zeros(rec.n),
        tat_k=np.full(rec.n, 288.0),
        epoch_utc_ns=123,
    )
    m = ScenarioReplay("scen", ri)
    s = System([m], [], rng=RngService(1, StreamRegistry()), identity=KeyPath.of(scenario="rp"))
    _, tr = s.run(s.start(), 240 * 10, record=s.output_ports())
    ph = tr.ports["scen.phase"]
    assert set(np.unique(ph).tolist()) == {1, 2, 3, 4, 5}
    k = np.arange(ph.size)
    expect = rec.phase[np.clip(((k + 1) * 10**9 // 240) * 4 // 10**9, 0, rec.n - 1)]
    assert np.array_equal(ph, expect)
    assert np.all(tr.ports["scen.epoch_utc_ns"] == 123)
