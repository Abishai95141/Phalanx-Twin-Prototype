"""CBIT / PBIT / MBIT hooks (A-W1.2-27) and actuator BIT words: the event-emission points M14 consumes.

Open loop on the M05 module with scripted lanes (helpers from test_fcs_voting); n = 1 scenario per case.
"""

from __future__ import annotations

import numpy as np
import pytest
from test_fcs_voting import base_inputs, make, run

from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.fcs.layout import (
    BIT_FAIL,
    BIT_PASS,
    BIT_RUNNING,
    CH_DROPOUT,
    I_ACTBIT,
    I_CBIT,
    I_MBIT,
    I_PBIT,
    LAW_GROUND,
    SUBSYSTEMS,
)


def _ground():
    mod = make(on_ground=True, mach=0.0, h=0.0, alpha=0.0)
    return mod, mod.init(mod.params, None)


def _ground_inputs(n):
    return base_inputs(n, mach=0.0, h=0.0, alpha=0.0, wow=6)


@pytest.mark.integration
def test_pbit_passes_on_a_healthy_aircraft_and_takes_its_duration():
    """PBIT on the ground: RUNNING for pbit_time (60 s = 4,800 frames), then PASS; ground law throughout."""
    mod, st = _ground()
    st, _ = mod.on_event(st, Event(0, "fcs.pbit_start", "fcs"), 0)
    assert st["i"][I_PBIT] == BIT_RUNNING
    st, out = run(mod, st, _ground_inputs(240 * 59))
    assert st["i"][I_PBIT] == BIT_RUNNING
    st, out = run(mod, st, _ground_inputs(240 * 2), 240 * 59)
    assert st["i"][I_PBIT] == BIT_PASS
    assert np.all(out["law_state"] == LAW_GROUND)


@pytest.mark.integration
def test_pbit_finds_a_latent_non_critical_fault_cbit_misses_until_persistent():
    """A non-critical subsystem fault (1553 interface, channel B) injected before PBIT: PBIT FAILs and latches
    the
    subsystem bit without persistence; the channel is not dropped (non-critical)."""
    mod, st = _ground()
    ev = Event(
        0,
        "fcs.channel_fault",
        "fcs",
        {"channel": 1, "subsystem": SUBSYSTEMS.index("MIL1553"), "active": True},
    )
    st, _ = mod.on_event(st, ev, 0)
    st, _ = mod.on_event(st, Event(0, "fcs.pbit_start", "fcs"), 0)
    st, out = run(mod, st, _ground_inputs(240 * 61))
    assert st["i"][I_PBIT] == BIT_FAIL
    assert st["i"][I_CBIT + 1] & (1 << SUBSYSTEMS.index("MIL1553"))
    assert out["channel_status"][-1, 1] == 0


@pytest.mark.integration
def test_mbit_requires_weight_on_wheels_and_aborts_airborne():
    """MBIT/PBIT are ground tests: refused in flight (ContractError), aborted (FAIL) if WoW is lost
    mid-test."""
    mod = make(on_ground=False)
    st = mod.init(mod.params, None)
    with pytest.raises(ContractError):
        mod.on_event(st, Event(0, "fcs.mbit_start", "fcs"), 0)
    mod, st = _ground()
    st, _ = mod.on_event(st, Event(0, "fcs.mbit_start", "fcs"), 0)
    st, _ = run(mod, st, _ground_inputs(240))
    assert st["i"][I_MBIT] == BIT_RUNNING
    st, _ = run(mod, st, base_inputs(240, mach=0.3, h=0.0, alpha=0.1, wow=0), 240)
    assert st["i"][I_MBIT] == BIT_FAIL


@pytest.mark.integration
def test_servo_coil_fault_latches_actuator_bit_word():
    """A servo-coil channel C fault on the rudder actuator sets FCS.ACT.BIT bit SERVO_FAIL_C after the CBIT
    persistence (3 frames); the surface keeps flying on the other coils (no jam); clearing + reset clears
    it."""
    mod = make()
    st = mod.init(mod.params, None)
    ev = Event(0, "fcs.actuator_fault", "fcs", {"surface": 4, "mode": "servo", "channel": 2, "active": True})
    st, _ = mod.on_event(st, ev, 0)
    st, _ = run(mod, st, base_inputs(6))
    assert st["i"][I_ACTBIT + 4] == 0  # 2 frames < persistence
    st, _ = run(mod, st, base_inputs(6), 6)
    assert st["i"][I_ACTBIT + 4] == 0b0100
    clear = Event(
        0, "fcs.actuator_fault", "fcs", {"surface": 4, "mode": "servo", "channel": 2, "active": False}
    )
    st, _ = mod.on_event(st, clear, 0)
    st, _ = mod.on_event(st, Event(0, "fcs.reset", "fcs"), 0)
    assert st["i"][I_ACTBIT + 4] == 0


@pytest.mark.integration
def test_transient_critical_fault_gives_latched_dropout_only():
    """A one-frame PSU glitch on channel A: DROPOUT (latched until reset) without FAILED (no persistence) -
    the
    'channel dropout once in flight, reset immediately' pattern (RTO-MP-SCI-162)."""
    mod = make()
    st = mod.init(mod.params, None)
    psu = SUBSYSTEMS.index("PSU")
    st, _ = mod.on_event(
        st, Event(0, "fcs.channel_fault", "fcs", {"channel": 0, "subsystem": psu, "active": True}), 0
    )
    st, _ = run(mod, st, base_inputs(3))
    st, _ = mod.on_event(
        st, Event(0, "fcs.channel_fault", "fcs", {"channel": 0, "subsystem": psu, "active": False}), 0
    )
    st, out = run(mod, st, base_inputs(30), 3)
    assert out["channel_status"][-1, 0] == CH_DROPOUT
    st, _ = mod.on_event(st, Event(0, "fcs.reset", "fcs"), 0)
    st, out = run(mod, st, base_inputs(3), 33)
    assert not out["channel_status"][-1, 0] & CH_DROPOUT


@pytest.mark.integration
def test_event_payload_validation():
    mod = make()
    st = mod.init(mod.params, None)
    with pytest.raises(ContractError):
        mod.on_event(
            st, Event(0, "fcs.channel_fault", "fcs", {"channel": 4, "subsystem": 0, "active": True}), 0
        )
    with pytest.raises(ContractError):
        mod.on_event(
            st, Event(0, "fcs.actuator_fault", "fcs", {"surface": 0, "mode": "melt", "active": True}), 0
        )
