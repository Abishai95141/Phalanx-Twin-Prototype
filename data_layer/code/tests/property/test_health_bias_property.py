"""Acceptance A3 (AD-26, report §2 TM-4551): sensor bias and component deterioration are separate latent
processes with separate truth. Perturbing either one (its parameters, a fault, a maintenance action) never
changes the other's truth trajectory, bitwise. Plus the installation-bias SD per sensor class.

Sample: 1 tail, 5 sorties per example (enough for every process to move); 8 hypothesis examples per
property."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.health import HealthConfig, HealthModule, SortieUsage, load_health_params, sensor_bias_channels

DAY = 86_400 * 10**9
DET = ("eng_f", "eng_i", "eng_life", "air", "air_aux", "air_age", "act")
BIAS = ("bias_inst", "bias_drift")
D = load_dictionary()
P = load_health_params()
BC = sensor_bias_channels(D)


def run(params, extra_events=()):
    m = HealthModule("health", params, config=HealthConfig(("IN20-0001",), BC))
    sysm = System(
        [m], [], rng=RngService(0xB1A5, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail="KH2011")
    )
    evs = []
    for k in range(5):
        u = SortieUsage(
            sortie_id=f"KH2011-{k}",
            flight_time_s=3600.0,
            eot_s=(4500.0,),
            tamp_s=(600.0,),
            type1=(1.0,),
            type3=(5.0,),
            type4=(5.0,),
            eftc=(1.2,),
            src_h=(0.05,),
            ps3_full=(0.0,),
            ps3_partial=(1.0,),
            ab_lights=(4.0,),
            starts=(1.0,),
            dust=2.0,
        )
        evs.append(Event((k + 1) * DAY, "health.sortie", "health", u.to_payload()))
    w = sysm.inject(sysm.start(), [*evs, *extra_events])
    w, _ = sysm.run(w, 240 * 86_400 * 6)
    return w.states["health"]


BASE = run(P)


def same(a, b, fields):
    return all(np.array_equal(a[f], b[f]) for f in fields)


@pytest.mark.property
@settings(max_examples=8, deadline=None)
@given(
    frac=st.floats(0.0005, 0.01),
    dt=st.floats(0.0, 3.2e-4),
    do=st.floats(0.0, 1.6e-4),
    t5=st.floats(0.5, 10.0),
)
def test_bias_parameters_never_change_deterioration_truth(frac, dt, do, t5):
    p = P.replace(
        bias_frac_span=frac, drift_frac_span_temp=dt / 60.0, drift_frac_span_other=do / 60.0, bias_t5_k=t5
    )
    s = run(p)
    assert same(s, BASE, DET)
    assert not same(s, BASE, BIAS)  # negative control: the bias truth did change


@pytest.mark.property
@settings(max_examples=8, deadline=None)
@given(
    ero=st.floats(1e-6, 1e-4),
    foul=st.floats(5e-6 / 3600, 1e-4 / 3600),
    sev=st.floats(1.5, 2.0),
    act=st.floats(1e-6, 1e-4),
)
def test_deterioration_parameters_never_change_bias_truth(ero, foul, sev, act):
    p = P.replace(erosion_rate_hpc=ero, fouling_drift=foul, severity_s=sev, act_leak_rate=act / 3600.0)
    s = run(p)
    assert same(s, BASE, BIAS)
    assert not same(s, BASE, DET)  # negative control


@pytest.mark.property
def test_faults_and_maintenance_stay_on_their_own_side():
    """A deterioration fault leaves bias truth bitwise unchanged; a sensor replacement leaves deterioration
    truth
    bitwise unchanged (and does change the bias)."""
    fault = Event(2 * DAY + 5, "health.fault", "health", {"state": "eng:fod_fan_eta", "delta": -0.03})
    s = run(P, [fault])
    assert same(s, BASE, BIAS) and not same(s, BASE, DET)
    rep = Event(
        2 * DAY + 5,
        "health.maintenance",
        "health",
        {"action": "replace_sensor", "target": "ENG.T5.HARNESS_A", "serial": "TC-9"},
    )
    s = run(P, [rep])
    assert same(s, BASE, DET) and not same(s, BASE, BIAS)


@pytest.mark.property
def test_bias_sd_by_class():
    """Installation bias SD per class (n = 2,000 sensor serials per class; SD of a normal sample has relative
    SE 1/sqrt(2n) ≈ 1.6 %, tolerance 5 %): N2 lanes 0.11 % of rated speed (AD-07), T5 harness 3.0 K (AD-07),
    others 0.25 % of span (A-W1.5-12)."""
    m = HealthModule("health", P, config=HealthConfig(("IN20-0001",), BC))
    System(
        [m], [], rng=RngService(0xB1A5, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail="KH2011")
    )
    ids = [b.channel_id for b in BC]
    for ch, expect in (
        ("ENG.N2.A", 0.0011 * 16810 * 2 * np.pi / 60),
        ("ENG.T5.HARNESS_A", 3.0),
        ("HYD.SYS1.P", 0.0025 * 350e5),
    ):
        c = ids.index(ch)
        x = np.array([m._install_bias(f"S{k}", c) for k in range(2000)])
        assert x.std() == pytest.approx(expect, rel=0.05), ch
        assert abs(x.mean()) < 3 * expect / np.sqrt(x.size), ch
