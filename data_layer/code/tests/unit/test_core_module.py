"""W0.2 module contract: ports and SI units (A8 / I3), provenance-tagged ParamSets (I4), state codec.

Tiny hand-written modules; each run is 1-20 steps (enough to cross a port boundary several times).
"""

from __future__ import annotations

import numpy as np
import pytest

import phalanx.core.scheduler as sched
from phalanx.core.module import ContractError, EvidenceTag, ModuleBase, Param, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.state import Field, StateError, StateSchema
from phalanx.core.units import UnitError, UnitMismatchError, parse_unit, units_compatible, ureg

SRC = "W0.2 unit test"


def _ps(name="p", **vals):
    return ParamSet(name, {k: Param(v, u, "ASSUMPTION", SRC) for k, (v, u) in vals.items()})


class Src(ModuleBase):
    version = "1"
    state_schema = StateSchema("src", 1, (Field("n", "<i8"),))

    def __init__(self, id, unit="m", quantity_unit=None):
        self.ports_out = (Port("y", unit),)
        self._qu = quantity_unit
        super().__init__(id, _ps())

    def init(self, params, keys):
        return self.state_schema.make(n=0)

    def initial_outputs(self, state):
        return {"y": np.array(0.0)}

    def step(self, state, inputs, t, dt):
        n = int(state["n"]) + 1
        y = np.array(float(n))
        if self._qu is not None:
            y = ureg().Quantity(y, self._qu)
        return {"n": np.array(n)}, {"y": y}


class Dst(ModuleBase):
    version = "1"
    state_schema = StateSchema("dst", 1, (Field("acc", "<f8"),))

    def __init__(self, id, unit="m"):
        self.ports_in = (Port("u", unit),)
        super().__init__(id, _ps())

    def init(self, params, keys):
        return self.state_schema.make(acc=0.0)

    def initial_outputs(self, state):
        return {}

    def step(self, state, inputs, t, dt):
        return {"acc": np.array(float(state["acc"]) + float(inputs["u"]))}, {}


def _system(src, dst, validate):
    rng = RngService(1, StreamRegistry())
    return System(
        [src, dst], [Connection("a.y", "b.u")], rng=rng, identity=KeyPath.of(scenario="u"), validate=validate
    )


@pytest.mark.unit
@pytest.mark.parametrize("unit", ["ft", "degC", "bar", "percent", "deg", "km", "lbf"])
def test_non_si_units_are_rejected_on_ports(unit):
    with pytest.raises(ContractError):
        Port("x", unit)


@pytest.mark.unit
def test_si_parsing_and_compatibility():
    for u in ["m", "m/s", "N", "kg*m/s**2", "Pa", "K", "kg/s", "rad/s", "1", "W", "J/kg"]:
        parse_unit(u)
    assert units_compatible("N", "kg*m/s**2")
    assert units_compatible("Pa", "N/m**2")
    assert not units_compatible("rad/s", "Hz")  # angular vs cyclic frequency: a 2*pi defect
    assert not units_compatible("m", "m/s")
    assert not units_compatible("s", "ns")
    Port("t", "ns", "<i8")
    with pytest.raises(ContractError):
        Port("t", "ns", "<f8")  # AD-35: ns only for integer time
    with pytest.raises(UnitError):
        parse_unit("not_a_unit")


@pytest.mark.unit
@pytest.mark.parametrize("dst_unit", ["m/s", "1", "kg"])
def test_unit_mismatch_caught_when_wiring(dst_unit):
    with pytest.raises(UnitMismatchError):
        _system(Src("a", "m"), Dst("b", dst_unit), validate=False)
    with pytest.raises(UnitMismatchError):
        _system(Src("a", "rad/s"), Dst("b", "Hz"), validate=False)


@pytest.mark.unit
def test_runtime_quantity_with_wrong_unit_caught_in_validation_mode():
    s = _system(Src("a", "m", quantity_unit="mm"), Dst("b", "m"), validate=True)
    w = s.start()
    with pytest.raises(UnitMismatchError, match=r"a\.y"):
        s.run(w, 3, mode="step")
    ok = _system(Src("a", "m", quantity_unit="m"), Dst("b", "m"), validate=True)
    w2, _ = ok.run(ok.start(), 3, mode="step")
    assert float(w2.states["b"]["acc"]) == 1.0 + 2.0 + 3.0  # magnitudes stripped to SI floats


@pytest.mark.unit
def test_production_mode_has_no_unit_check_cost(monkeypatch):
    """Production mode never calls the unit machinery per step (validation mode does, every step)."""
    calls = []

    def spy(value, unit, where):
        calls.append(where)
        return value

    monkeypatch.setattr(sched, "strip_quantity", spy)
    for mode in ("step", "block"):
        s = _system(Src("a", "m"), Dst("b", "m"), validate=False)
        s.run(s.start(), 20, mode=mode)
    assert calls == []
    s = _system(Src("a", "m"), Dst("b", "m"), validate=True)
    s.run(s.start(), 20, mode="step")
    assert len(calls) == 21  # 1 initial output + 20 steps


@pytest.mark.unit
def test_evidence_tags_accept_the_dictionary_forms():
    cases = {
        "DIRECT": ("DIRECT", ""),
        "DIRECT-unnamed": ("DIRECT", "unnamed"),
        "DIRECT-part": ("DIRECT", "part"),
        "[TRANSFER: F404-400]": ("TRANSFER", "F404-400"),
        "TRANSFER: RM12": ("TRANSFER", "RM12"),
        "MEASURED": ("MEASURED", ""),
        "[ASSUMPTION]": ("ASSUMPTION", ""),
    }
    for text, (k, q) in cases.items():
        t = EvidenceTag.parse(text)
        assert (t.kind, t.qualifier) == (k, q)
        assert EvidenceTag.parse(str(t)) == t
    for bad in ("GUESS", "TRANSFER:", "direct", ""):
        with pytest.raises(ContractError):
            EvidenceTag.parse(bad)


@pytest.mark.unit
def test_paramset_hash_is_content_based_and_provenance_is_mandatory():
    a = ParamSet(
        "eng", {"tau": Param(0.23, "s", "MEASURED", "round-2 A6"), "n": Param(4, "1", "ASSUMPTION", "x")}
    )
    b = ParamSet(
        "eng", {"n": Param(4, "1", "ASSUMPTION", "x"), "tau": Param(0.23, "s", "MEASURED", "round-2 A6")}
    )
    assert a.hash == b.hash and a == b
    assert a.replace(tau=0.24).hash != a.hash
    assert ParamSet("eng", {**a, "tau": Param(0.23, "s", "ASSUMPTION", "round-2 A6")}).hash != a.hash
    assert ParamSet("eng", {**a, "tau": Param(0.23, "s", "MEASURED", "other")}).hash != a.hash
    assert ParamSet("eng", {**a, "n": Param(4.0, "1", "ASSUMPTION", "x")}).hash != a.hash  # int vs float
    tbl = ParamSet("t", {"map": Param(np.arange(6.0).reshape(2, 3), "1", "TRANSFER: pyCycle", "R§7")})
    assert tbl.value("map").flags.writeable is False
    with pytest.raises(ContractError):
        Param(1.0, "m", "ASSUMPTION", "")  # no source
    with pytest.raises(ContractError):
        Param(1.0, "ft", "ASSUMPTION", "s")  # non-SI
    with pytest.raises(ContractError):
        Param(1.0, "m", "GUESS", "s")
    assert ParamSet("p", {"x": Param(1.0, "m", "ASSUMPTION", "s", proxy=True)}).proxies() == ["x"]


@pytest.mark.unit
def test_module_state_codec_and_contract_checks():
    m = Src("a")
    st = m.init(m.params, None)
    b = m.get_state(st)
    assert m.set_state(b)["n"] == 0
    other = Dst("b")
    with pytest.raises(StateError, match="expects"):
        other.set_state(b)
    with pytest.raises(StateError):
        m.get_state({"n": np.array(1.5)})  # wrong dtype never serialises
    with pytest.raises(ContractError):
        Src("bad id")
    with pytest.raises(ContractError, match="not bound"):
        _ = m.keys
