"""Interface cohesion for M12/M13 (the W1 port-catalogue rules applied to the observation layer).

``tests/integration/test_interface_conformance.py`` covers the truth-layer modules M02-M10. This applies the
same checks to W1.6: every M12 input is bound to a catalogued signal with an equivalent unit, the same dtype
and rank (n_engines 1 and 2); every M13 in-loop input reads an M12 output with the same unit and shape; every
lane a controller may bind (``lane.<channel_id>``) exists in the dictionary and carries the channel's SI unit.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.acquisition import ports as aports
from phalanx.core.units import ureg
from phalanx.dictionary import load_dictionary
from phalanx.sensors import ports as sports
from phalanx.sensors.config import load_catalogue

pytestmark = pytest.mark.integration


def _equiv(u1: str, u2: str) -> bool:
    reg = ureg()
    a = reg.Quantity(1.0, "dimensionless" if u1 in ("1", "") else u1).to_base_units()
    b = reg.Quantity(1.0, "dimensionless" if u2 in ("1", "") else u2).to_base_units()
    return a.dimensionality == b.dimensionality and bool(np.isclose(a.magnitude, b.magnitude))


@pytest.mark.parametrize("n_engines", [1, 2])
def test_m12_inputs_match_catalogue(n_engines):
    cat = load_catalogue()
    ins, outs, bindings = sports.ports(n_engines)
    assert sports.PREFIX == "sens"
    assert {p.name for p in ins} == set(bindings)
    for p in ins:
        spec = cat[bindings[p.name]]
        assert _equiv(p.unit, spec["unit"]), p.name
        assert np.dtype(p.dtype).name == spec["dtype"], p.name
        assert len(p.shape) == len(spec["shape"]), p.name
        for c, s in zip(spec["shape"], p.shape, strict=True):
            if c == "e":
                assert s == n_engines
            elif isinstance(c, int):
                assert s == c
    assert all(p.name.startswith(("s_", "x_")) for p in outs)


@pytest.mark.parametrize("n_engines", [1, 2])
def test_m13_inputs_read_m12_outputs(n_engines):
    _, s_outs, _ = sports.ports(n_engines)
    by_name = {f"sens.{p.name}": p for p in s_outs}
    ins, _outs, bindings = aports.ports(n_engines)
    for p in ins:
        src = bindings[p.name]
        if src == "scenario.phase":
            spec = load_catalogue()[src]
            assert np.dtype(p.dtype).name == spec["dtype"] and p.shape == ()
            continue
        assert src in by_name, src
        assert by_name[src].unit == p.unit and by_name[src].shape == p.shape


def test_lane_ports_carry_the_channel_si_unit():
    """lane.<channel_id> -> a value port whose unit is eu_conversion(channel).si_units (W1_interfaces §1)."""
    d = load_dictionary()
    _, outs, _ = aports.ports()
    out = {p.name: p for p in outs}
    lanes = aports.lane_bindings()
    assert len(lanes) > 100
    for lane, (_mid, port) in lanes.items():
        cid = lane.split(".", 1)[1]
        assert _equiv(out[port].unit, d.eu_conversion(cid).si_units), lane
        assert out[f"{port}_t"].unit == "ns" and out[f"{port}_n"].shape == ()
    for cid in ("ENG.N2.A", "ENG.N1.B", "ENG.PS3.A", "ENG.T5.HARNESS_A", "FCS.RSA.Q.C", "AD.PS.D"):
        assert f"lane.{cid}" in lanes
