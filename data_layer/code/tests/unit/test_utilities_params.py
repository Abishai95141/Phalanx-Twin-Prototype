"""M09 parameters: provenance completeness, layout consistency, cross-checks against the dictionary and DIRECT
anchors, and the guards that keep platform specifics in parameter files (_w1_common.md §2)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.module import ContractError
from phalanx.dictionary import load_dictionary
from phalanx.utilities import config_vector, load_m09_params, param_vector
from phalanx.utilities import layout as L
from phalanx.utilities.params import power_quality_bands, transfer_ticks

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ps():
    return load_m09_params()


@pytest.mark.unit
def test_every_kernel_parameter_is_in_the_yaml_with_provenance(ps):
    for name in L.P_NAMES:
        assert name in ps, name
        p = ps[name]
        assert p.source.strip() and str(p.tag), name
    for col in L.TANK_COLS:
        assert np.asarray(ps.value(f"tank_{col}")).shape == (L.N_TANKS,)
    for col in L.STORE_COLS:
        assert np.asarray(ps.value(f"store_{col}")).shape == (L.N_STORE,)
    vec = param_vector(ps)
    assert vec.size == L.NP_TOTAL and not vec.flags.writeable and np.all(np.isfinite(vec))


@pytest.mark.unit
def test_every_assumption_is_registered_with_a_sweep_and_proxies_are_flagged(ps):
    text = (REPO / "docs" / "assumptions.md").read_text(encoding="utf-8")
    section = text.split("## W1.4 Utilities (M09)")[1].split("\n## ")[0]
    ids = set(re.findall(r"^\| (A-W1\.4-\d+) \|", section, flags=re.M))
    yaml = (REPO / "configs" / "tejas" / "params" / "M09.yaml").read_text(encoding="utf-8")
    used = set(re.findall(r"assumption_id: (A-W1\.4-\d+)", yaml))
    assert used <= ids, f"unregistered assumption ids {sorted(used - ids)}"
    # PROXY rows of the register are flagged on the parameters that carry them
    proxy_rows = set(re.findall(r"^\| (A-W1\.4-\d+) \| [^|]*\| PROXY \|", section, flags=re.M))
    assert proxy_rows == {"A-W1.4-15", "A-W1.4-24"}
    assert {"ecs_eta_t", "slosh_omega", "slosh_zeta"} <= set(ps.proxies())


@pytest.mark.unit
def test_shared_constants_match_the_dictionary(ps):
    """PTO rated speed and 100 % N2 duplicate dictionary constants: guard against drift."""
    d = load_dictionary()
    cr = d.param_set("channel_reference")
    assert ps.value("pto_rated_speed") == pytest.approx(cr.value("amagb_rated_speed"), rel=1e-12)
    assert ps.value("n2_100pct") == pytest.approx(cr.value("n2_100pct"), rel=1e-12)


@pytest.mark.unit
def test_tank_table_closes_on_the_direct_internal_fuel_and_reference_loading(ps):
    caps = np.asarray(ps.value("tank_cap"))  # m^3
    internal = caps[[L.T_F1, L.T_F1A, L.T_F2, L.T_WL, L.T_WR]].sum()
    assert internal == pytest.approx(ps.value("fuel_internal_volume"), rel=1e-12)  # 3,060 L [DIRECT]
    assert internal * ps.value("fuel_rho_15") == pytest.approx(
        ps.value("fuel_internal"), rel=1e-3
    )  # 2,458 kg
    # drop-tank capacities are the DIRECT 1,200 / 1,200 / 800 L
    assert caps[[L.T_DTL, L.T_DTR, L.T_DTC]] * 1000 == pytest.approx([1200.0, 1200.0, 800.0])
    # reference loading (fuselage tanks) carries m_ref - m_oe within 1 kg
    fus = caps[[L.T_F1, L.T_F1A, L.T_F2]].sum() * ps.value("fuel_rho_15")
    assert fus == pytest.approx(ps.value("mp_m_ref") - ps.value("mp_m_oe"), abs=1.0)


@pytest.mark.unit
def test_config_vector_and_transfer_ticks(ps):
    c1 = config_vector(ps, 1)
    assert c1[L.C_NE] == 1 and c1[L.C_PUMP_ENG0] == 0 and c1[L.C_PUMP_ENG1] == 0
    assert c1[L.C_XFER_TICKS] * 1e3 / 240 <= 50.0  # MIL-STD-704F §5.1
    c2 = config_vector(ps, 2)
    assert c2[L.C_NE] == 2 and c2[L.C_GEN_ENG] == 0
    with pytest.raises(ContractError):
        transfer_ticks(ps.replace(elec_transfer_time=0.06))
    with pytest.raises(ContractError):
        config_vector(ps.replace(hyd_pump_engine=np.array([0.5, 0.0])), 1)


@pytest.mark.unit
def test_power_quality_bands_are_the_704f_values(ps):
    b = power_quality_bands(ps)
    assert (b["dc_normal_lo"], b["dc_normal_hi"], b["dc_emerg_lo"], b["dc_start_lo"]) == (
        22.0,
        29.0,
        16.0,
        12.0,
    )
    assert (b["ac_normal_lo"], b["ac_normal_hi"], b["ac_f_lo"], b["ac_f_hi"]) == (108.0, 118.0, 393.0, 407.0)


@pytest.mark.unit
def test_no_restricted_appendix_a1_quantities_are_parameters():
    """Report App. A1 lists F-16 JFS timings, F-16 tyre/brake-energy limits and F/A-18 AMAD/fuel-hot limits as
    restricted: no M09 parameter may claim them as a source (negative control: the guard sees a planted
    one)."""
    yaml = (REPO / "configs" / "tejas" / "params" / "M09.yaml").read_text(encoding="utf-8")
    banned = re.compile(r"F-16 JFS tim|F-16 tyre|F-16 brake-energy|AMAD limit|fuel-hot threshold", re.I)
    sources = re.findall(r"source: \"([^\"]*)\"", yaml)
    bad = [s for s in sources if banned.search(s) and "not used" not in s and "restricted" not in s.lower()]
    assert not bad, bad
    planted = 'source: "F-16 JFS timings from the flight manual"'
    assert banned.search(re.findall(r"source: \"([^\"]*)\"", planted)[0])


@pytest.mark.unit
def test_every_w14_assumption_names_an_existing_exposing_test():
    """Each W1.4 register row names its exposing test; the test function (or coupling edge) must exist."""
    text = (REPO / "docs" / "assumptions.md").read_text(encoding="utf-8")
    section = text.split("## W1.4 Utilities (M09)")[1].split("\n## ")[0]
    rows = re.findall(r"^\| A-W1\.4-\d+ \|.*$", section, flags=re.M)
    assert len(rows) >= 31
    coupling = (REPO / "configs/tejas/params/M09/coupling_signs.csv").read_text(encoding="utf-8")
    edges = {row.split(",")[0] for row in coupling.splitlines()[1:]}
    for line in rows:
        if line.rstrip().endswith("| retired |"):
            continue
        named = re.findall(r"(test_utilities_\w+\.py)::(\w+)", line)
        edge_refs = re.findall(r"edge ([A-Z0-9][A-Za-z0-9-]*)", line)
        assert named or edge_refs, line[:20]
        for fname, test in named:
            hits = list(REPO.glob(f"tests/*/{fname}"))
            assert hits, fname
            assert f"def {test}(" in hits[0].read_text(encoding="utf-8"), (fname, test)
        for edge in edge_refs:
            assert any(e.startswith(edge) for e in edges), edge
