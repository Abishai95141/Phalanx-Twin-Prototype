"""M09 invariants under hypothesis-generated conditions: fuel mass conservation, pressure monotone in demand,
mass properties physically valid, free-surface geometry bounded and monotone, state codec round-trip.

Samples: 25-40 examples per property, short runs (<= 2 s of truth each).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_utilities_support import G0, inputs, module, run

from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L
from phalanx.utilities.fuel import depth_at, section_area, surface_intercept

PS = load_m09_params()
CAP = np.asarray(PS.value("tank_cap")) * PS.value("fuel_rho_15")
FAST = settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@pytest.mark.property
@FAST
@given(
    fills=st.lists(st.floats(0.0, 1.0), min_size=8, max_size=8),
    wf=st.floats(0.0, 5.0),
    fx=st.floats(-1.0, 1.5),
    nz=st.floats(-0.5, 3.0),
)
def test_fuel_mass_is_conserved(fills, wf, fx, nz):
    fuel = tuple(float(f * c) for f, c in zip(fills, CAP, strict=True))
    m, s0 = module(UtilitiesConfig(fuel=fuel, drop_tanks=(True, True, True), soak_temp=288.15))
    s1, _ = run(m, s0, inputs(240, wf=wf, fspec=(fx * G0, 0.0, -nz * G0)))
    f0, f1 = s0["f"], s1["f"]
    total0 = float(np.sum(f0[L.F_FUEL_M : L.F_FUEL_M + 8]))
    total1 = float(np.sum(f1[L.F_FUEL_M : L.F_FUEL_M + 8]))
    burned, unmet = float(f1[L.F_FUEL_BURN]), float(f1[L.F_FUEL_UNMET])
    assert total0 - total1 == pytest.approx(burned, abs=1e-9)
    assert burned + unmet == pytest.approx(wf, rel=1e-9, abs=1e-12)
    assert np.all(f1[L.F_FUEL_M : L.F_FUEL_M + 8] >= 0.0)


@pytest.mark.property
@FAST
@given(n2f=st.floats(0.6, 1.05), d1=st.floats(0.0, 1.4), d2=st.floats(0.0, 1.4))
def test_pressure_is_non_increasing_in_demand(n2f, d1, d2):
    lo, hi = sorted((d1, d2))
    q = PS.value("hyd_q_rated")
    p = []
    for d in (lo, hi):
        m, s = module(UtilitiesConfig(soak_temp=300.0))
        _, out = run(m, s, inputs(480, n2f=n2f, demand=d * q))
        p.append(float(out["hyd_p"][-1, 0]))
    assert p[1] <= p[0] + 1e-6


@pytest.mark.property
@FAST
@given(
    fills=st.lists(st.floats(0.0, 1.0), min_size=8, max_size=8),
    stores=st.lists(st.floats(0.0, 1000.0), min_size=5, max_size=5),
)
def test_mass_properties_are_physical(fills, stores):
    fuel = tuple(float(f * c) for f, c in zip(fills, CAP, strict=True))
    m, s = module(
        UtilitiesConfig(fuel=fuel, drop_tanks=(True, True, True), stores=tuple(stores), soak_temp=288.15)
    )
    out = m.initial_outputs(s)
    dt_dry = 2 * PS.value("dt_dry_mass_inboard") + PS.value("dt_dry_mass_centre")
    assert float(out["mass"]) == pytest.approx(
        PS.value("mp_m_oe") + sum(fuel) + sum(stores) + dt_dry, rel=1e-12
    )
    j = out["inertia"]
    ev = np.linalg.eigvalsh(j)
    assert np.allclose(j, j.T) and ev[0] > 0 and ev[0] + ev[1] >= ev[2] * (1 - 1e-12)
    assert np.all(np.abs(out["cg"]) < 1.0)


@pytest.mark.property
@settings(max_examples=40, deadline=None)
@given(fill=st.floats(0.0, 1.0), s=st.floats(-4.0, 4.0), frac=st.floats(0.0, 1.0))
def test_free_surface_geometry_bounds(fill, s, frac):
    length, height, cap, rho = 1.4, 0.75, 1.131, 803.0
    m = fill * cap * rho
    h = depth_at(m, rho, cap, length, height, s, frac)
    assert 0.0 <= h <= height
    a = fill * length * height
    c = surface_intercept(a, abs(s), length, height)
    assert section_area(c, abs(s), length, height) == pytest.approx(a, abs=1e-9)
    assert section_area(c + 0.01, abs(s), length, height) >= section_area(c, abs(s), length, height)


@pytest.mark.property
@FAST
@given(seed=st.integers(0, 2**32 - 1))
def test_state_codec_round_trips(seed):
    g = np.random.Generator(np.random.Philox(seed))  # test data, not a simulation stream
    m, s = module(UtilitiesConfig())
    s = {"f": g.normal(size=L.NF) * 1e3, "i": g.integers(-5, 5, size=L.NI).astype(np.int64)}
    back = m.set_state(m.get_state(s))
    assert np.array_equal(back["f"], s["f"]) and np.array_equal(back["i"], s["i"])
