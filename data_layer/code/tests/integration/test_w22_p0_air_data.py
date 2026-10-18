"""W2.2 (coordinator priority 2): M08's P0 comes from the aircraft air data, not from truth.

The F404 ECU's ambient-pressure input is an altitude signal (NASA CR-179568 Fig. 3, ECU inputs) [TRANSFER:
F404-400]. The Tejas FADEC therefore binds ``p0`` to ``avio.p0_from_hp``: the standard-atmosphere static
pressure at the avionics ADC's pressure altitude AD.HP, which is the ADC's position-error-corrected static
pressure (A-W1.3b-11 PROXY retired for Tejas). It is computed from the digitised DFCC/ADC lanes, never from
truth. The DASHlink proxy chain keeps the replayed ``env.p_s`` (no aircraft air data). The E1-MF conformance
gate resolves the binding in every Tejas configuration (tests/integration/test_interface_conformance.py).

Sample: the avionics fixture flight (level, Mach 0.61 at 3,000 m), 3 s = 720 truth frames, n = 1 run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.scheduler import Connection
from phalanx.dictionary import load_dictionary
from phalanx.fadec.coupling import fadec_input_connections
from phalanx.fadec.ports import P0_AIR_DATA, P0_ENV, ports
from phalanx.sensors.avionics import adc as A
from phalanx.sensors.avionics import ports as AP
from phalanx.sensors.avionics.config import build_avionics_config
from phalanx.sensors.avionics.module import P0_PORT

pytestmark = pytest.mark.integration
D = load_dictionary()


def _fixture():
    name = "w22_avionics_fixture"
    if name not in sys.modules:
        p = Path(__file__).resolve().parent / "test_w22_avionics_fixture.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


@pytest.fixture(scope="module")
def flight():
    fx = _fixture()
    n = 720
    truth = fx.default_truth(n)
    system, _, _ = fx.build_avionics_chain(D, truth)
    rec = [f"avio.{P0_PORT}", "avio.rec_ad_hp", "avio.rec_ad_ps_v"]
    _, tr = system.run(system.start(), n, record=rec, mode="block")
    return truth, tr.ports


def test_p0_binding_is_the_avionics_p0_altitude_signal():
    ins, _, bindings = ports(1)
    assert bindings["p0"] == P0_AIR_DATA == f"{AP.PREFIX}.{P0_PORT}"
    (p0,) = [p for p in ins if p.name == "p0"]
    _, outs, _ = AP.ports(1)
    (src,) = [p for p in outs if p.name == P0_PORT]
    assert (p0.unit, p0.dtype, p0.shape, p0.rate) == (src.unit, src.dtype, src.shape, src.rate)
    assert (p0.unit, p0.dtype, p0.shape, p0.rate) == ("Pa", "<f8", (), None)
    conns = fadec_input_connections("fadec", bindings, {"pilot": "m04", "avio": "avio"}, "acq_fadec")
    assert Connection(f"avio.{P0_PORT}", "fadec.p0") in conns
    assert ports(4, autothrottle=True)[2]["p0"] == P0_ENV  # the proxy chain: replayed static pressure


def test_p0_is_the_static_pressure_of_the_adc_pressure_altitude(flight):
    """Exactly the standard-atmosphere pressure at the published AD.HP, frame by frame; the inverse round trip
    with the ADC's own pressure altitude closes to 1e-6 m."""
    _truth, o = flight
    p0, hp = o[f"avio.{P0_PORT}"], o["avio.rec_ad_hp"]
    p = build_avionics_config().adc_p
    assert np.array_equal(p0, A.static_pressure_at_array(np.ascontiguousarray(hp), p))
    back = np.array([A.pressure_altitude(x, p) for x in p0[24:]])
    assert np.max(np.abs(back - hp[24:])) < 1e-6
    for h in (-300.0, 0.0, 5000.0, 11000.0, 15000.0):  # both ICAO layers
        assert A.pressure_altitude(A.static_pressure_at(h, p), p) == pytest.approx(h, abs=1e-6)


def test_p0_is_the_corrected_air_data_not_truth(flight):
    """What M08 now reads tracks the true static pressure to 0.1 % once the ADC has computed (after 0.1 s),
    far closer than the voted static port pressure AD.PS.V with its uncorrected position error, and it is a
    measurement (lane physics, quantisation, residual correction error), not the truth itself."""
    truth, o = flight
    ps = np.asarray(truth["env.p_s"])[24:]
    p0 = o[f"avio.{P0_PORT}"][24:]
    port = o["avio.rec_ad_ps_v"][24:]
    rel = np.abs(p0 / ps - 1.0)
    assert np.all(p0 > 0.0) and rel.max() < 1e-3
    assert rel.max() < 0.25 * np.abs(port / ps - 1.0).min()
    assert np.any(p0 != ps)
