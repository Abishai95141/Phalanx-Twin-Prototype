"""A8 fork properties of M12 + M13: snapshot round trip and common random numbers per sensor stream (I2, I8).

Chain: TEST FIXTURE truth -> M12 -> M13 in-loop lanes (FADEC + DFCC). n = 1,201 frames before the snapshot
(not a multiple of the 3-frame DFCC or the FADEC period, so mid-frame clock and AR(1) state are exercised) and
600 after.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import DrawLedger, crn_audit
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.time import truth_step_time_ns
from phalanx.dictionary import load_dictionary
from phalanx.sensors.config import build_sensor_config
from phalanx.sensors.module import SENSOR_FAULT_EVENT

pytestmark = pytest.mark.fork
K0, K1 = 1201, 600


def load_fixture():
    name = "w16_acquisition_fixtures"
    if name not in sys.modules:
        p = Path(__file__).resolve().parents[1] / "integration" / "test_acquisition_fixtures.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


FX = load_fixture()


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


@pytest.fixture(scope="module")
def sens(d):
    return build_sensor_config(d)


def _ports(mods):
    out = FX.sensor_ports(mods)
    for m in mods.values():
        if m.id.startswith("acq_"):
            out += FX.lane_record_ports(m)
    return out


def test_snapshot_restore_continues_bitwise(d, sens):
    system, _, mods = FX.build_chain(d, sens)
    w, _ = system.run(system.start(), K0)
    blob = snapshot(system, w)
    _, ref = system.run(w, K1, record=_ports(mods))
    system2, _, mods2 = FX.build_chain(d, sens)
    w2 = restore(system2, blob)
    _, cont = system2.run(w2, K1, record=_ports(mods2))
    assert cont.digest() == ref.digest()


def _branch(d, sens, blob, events, ledger):
    system, _, mods = FX.build_chain(d, sens, ledger=ledger)
    w = restore(system, blob)
    if events:
        w = system.inject(w, events)
    _, tr = system.run(w, K1, record=_ports(mods))
    return tr


@pytest.fixture(scope="module")
def blob(d, sens):
    system, _, _ = FX.build_chain(d, sens)
    w, _ = system.run(system.start(), K0)
    return snapshot(system, w)


def test_crn_noise_is_identical_across_a_fault_fork(d, sens, blob):
    """A deterministic sensor fault (bias on N2 lane B) in one branch: every M13 noise/event draw is identical
    in both branches (crn_audit ok), only the faulted lane's values differ, every other lane is
    bit-identical."""
    la, lb = DrawLedger(), DrawLedger()
    ev = [
        Event(
            truth_step_time_ns(K0 + 100),
            SENSOR_FAULT_EVENT,
            "sens",
            {"channel": "ENG.N2.B", "mode": "bias", "value": 3.0},
        )
    ]
    ta = _branch(d, sens, blob, [], la)
    tb = _branch(d, sens, blob, ev, lb)
    rep = crn_audit(la, lb)
    assert rep.ok, rep.diverged()
    assert any("acquisition" in p for p in rep.identical)
    differing = sorted(p for p in ta.ports if not np.array_equal(ta.ports[p], tb.ports[p]))
    assert "acq_fadec.lane_eng_n2_b" in differing
    assert all("n2_b" in p or p.startswith("sens.") for p in differing), differing
    na = FX.lane_samples(ta.ports, "acq_fadec", "ENG.N2.B")
    nb = FX.lane_samples(tb.ports, "acq_fadec", "ENG.N2.B")
    assert set(na) == set(nb)


def test_stochastic_fault_draws_only_from_its_own_stream(d, sens, blob):
    """An intermittent fault consumes draws from M12's fault stream of that sensor only (it appears only in
    the faulted branch); all M13 streams stay identical, so the exogenous noise future is shared (I8)."""
    la, lb = DrawLedger(), DrawLedger()
    ev = [
        Event(
            truth_step_time_ns(K0 + 50),
            SENSOR_FAULT_EVENT,
            "sens",
            {"channel": "ENG.PS3.A", "mode": "intermittent", "rate": 2.0, "duty": 0.3},
        )
    ]
    _branch(d, sens, blob, [], la)
    _branch(d, sens, blob, ev, lb)
    rep = crn_audit(la, lb)
    assert not rep.consumption_differs and not rep.values_differ and not rep.only_in_a
    assert (
        len(rep.only_in_b) == 1 and "sensor=s:ENG.PS3.A" in rep.only_in_b[0] and "fault" in rep.only_in_b[0]
    )


def test_adding_lanes_leaves_other_lanes_unchanged(d, sens):
    """Streams are keyed by sensor identity: acquiring an extra controller's lanes does not change the FADEC
    lanes' values (no draw-order coupling)."""
    s1, _, m1 = FX.build_chain(d, sens, controllers=("FADEC",))
    s2, _, m2 = FX.build_chain(d, sens, controllers=("FADEC", "DFCC"))
    _, t1 = s1.run(s1.start(), 480, record=FX.lane_record_ports(m1["acq_fadec"]))
    _, t2 = s2.run(s2.start(), 480, record=FX.lane_record_ports(m2["acq_fadec"]))
    for p, v in t1.ports.items():
        np.testing.assert_array_equal(v, t2.ports[p])
