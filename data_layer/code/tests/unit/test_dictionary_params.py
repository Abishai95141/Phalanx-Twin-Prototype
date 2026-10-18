"""Model-parameter registry (W1.0): per-module parameter files with enforced provenance."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.module import ParamSet
from phalanx.dictionary.params import ParamFileError, load_param_set, load_params, registry_hash

GOOD = """\
format: phalanx.params/1
module: MXX
sets:
  rotor:
    n2_ref:
      value: 16810
      units: rpm
      description: core reference speed
      evidence: {tag: "TRANSFER: F404-400", source: "report §1"}
    inertia_hp:
      value: 3.0
      units: kg*m**2
      description: HP spool inertia
      evidence: {tag: ASSUMPTION, source: "architecture M07 (I_HP ~3, tuned)"}
      sweep: [2.0, 4.0]
      assumption_id: A-TEST-1
    t_ref:
      value: 15.0
      units: degC
      description: reference temperature
      evidence: {tag: DIRECT, source: "ISA"}
    gains:
      value: [1.0, 2.0, 3.0]
      units: "1"
      description: a vector
      evidence: {tag: MEASURED, source: "analysis/x"}
    wc:
      table: {file: map.csv, column: Wc}
      units: kg/s
      description: corrected flow column
      evidence: {tag: "TRANSFER: pyCycle", source: "report §7"}
"""

ASSUMPTIONS = "| ID | x |\n|---|---|\n| A-TEST-1 | an assumption |\n"


def _setup(tmp_path: Path, text: str = GOOD, assumptions: str = ASSUMPTIONS) -> dict:
    cfg = tmp_path / "configs"
    d = cfg / "tejas" / "params"
    (d / "MXX").mkdir(parents=True)
    (d / "MXX.yaml").write_text(text, encoding="utf-8")
    (d / "MXX" / "map.csv").write_text("Nc,Wc\n0.9,60.0\n1.0,70.0\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "assumptions.md").write_text(assumptions, encoding="utf-8")
    return {"config_root": cfg, "repo_root": tmp_path}


@pytest.mark.unit
def test_loads_and_converts_to_si(tmp_path):
    kw = _setup(tmp_path)
    sets = load_params("MXX", **kw)
    ps = sets["rotor"]
    assert isinstance(ps, ParamSet)
    assert math.isclose(ps["n2_ref"].value, 16810 * 2 * math.pi / 60, rel_tol=1e-12)
    assert "radian / second" in ps["n2_ref"].unit or "1 / second" in ps["n2_ref"].unit
    assert math.isclose(ps["t_ref"].value, 288.15, rel_tol=1e-12)
    assert ps["inertia_hp"].tag.kind == "ASSUMPTION"
    assert np.array_equal(ps["gains"].value, [1.0, 2.0, 3.0])
    assert np.array_equal(ps["wc"].value, [60.0, 70.0])
    assert load_param_set("MXX", "rotor", **kw).hash == ps.hash


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutate, needle",
    [
        (
            lambda t: t.replace('evidence: {tag: DIRECT, source: "ISA"}', "evidence: {tag: DIRECT}"),
            "evidence",
        ),
        (lambda t: t.replace('source: "ISA"', 'source: ""'), "source"),
        (lambda t: t.replace("units: rpm", "units: furlongs_per_fortnightx"), "units"),
        (lambda t: t.replace("      sweep: [2.0, 4.0]\n", ""), "sweep"),
        (lambda t: t.replace("sweep: [2.0, 4.0]", "sweep: [3.5, 4.0]"), "outside sweep"),
        (lambda t: t.replace("      assumption_id: A-TEST-1\n", ""), "assumption_id"),
        (lambda t: t.replace("A-TEST-1", "A-TEST-9"), "not registered"),
        (
            lambda t: t.replace(
                "      description: a vector\n", "      description: a vector\n      colour: red\n"
            ),
            "unknown",
        ),
        (lambda t: t.replace("module: MXX", "module: MYY"), "module field"),
        (
            lambda t: t.replace("table: {file: map.csv, column: Wc}", "table: {file: nope.csv, column: Wc}"),
            "not found",
        ),
        (
            lambda t: t.replace("value: 15.0", "value: 15.0\n      table: {file: map.csv, column: Wc}"),
            "exactly one",
        ),
        (lambda t: t.replace("evidence: {tag: MEASURED", "evidence: {tag: GUESSED"), "tag"),
        (
            lambda t: (
                t.replace("proxy", "proxy")
                + "    p2:\n      value: 1\n      units: '1'\n      description: d\n"
                "      evidence: {tag: DIRECT, source: s}\n      proxy: true\n"
            ),
            "assumption_id",
        ),
    ],
)
def test_rejects_bad_entries(tmp_path, mutate, needle):
    kw = _setup(tmp_path, mutate(GOOD))
    with pytest.raises(ParamFileError) as ex:
        load_params("MXX", **kw)
    assert needle in str(ex.value), str(ex.value)


@pytest.mark.unit
def test_duplicate_yaml_keys_rejected(tmp_path):
    kw = _setup(tmp_path, GOOD.replace("    t_ref:", "    n2_ref:\n      value: 1\n    t_ref:", 1))
    with pytest.raises(Exception, match=r"(?i)duplicate"):
        load_params("MXX", **kw)


@pytest.mark.unit
def test_registry_hash_stable_and_sensitive(tmp_path):
    kw = _setup(tmp_path)
    h1 = registry_hash(config_root=kw["config_root"])
    assert h1 == registry_hash(config_root=kw["config_root"])
    p = kw["config_root"] / "tejas" / "params" / "MXX" / "map.csv"
    p.write_text(p.read_text().replace("70.0", "70.5"))
    assert registry_hash(config_root=kw["config_root"]) != h1


@pytest.mark.unit
def test_repo_param_files_all_valid(repo_root):
    """Every committed configs/<platform>/params/*.yaml loads cleanly against docs/assumptions.md."""
    for f in sorted((repo_root / "configs").glob("*/params/*.yaml")):
        sets = load_params(f.stem, platform=f.parent.parent.name)
        assert sets, f
