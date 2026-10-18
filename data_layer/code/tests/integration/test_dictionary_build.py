"""Build pipeline: compile -> dictionary.<ver>.json -> generators, the extra-generator hook, committed
artefacts.

Sample: one build of the Tejas dictionary into a temporary directory (the generators are deterministic, so one
build plus a byte comparison with the committed artefacts answers "are they current").
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest

from phalanx.dictionary import (
    Dictionary,
    build,
    read_compiled,
    register_generator,
    resolve_generator,
    run_generators,
)
from phalanx.dictionary.generators import BUILTIN_GENERATORS
from phalanx.dictionary.yamlio import dump_yaml, load_yaml

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"
GENERATED = REPO / "src" / "phalanx" / "dictionary" / "generated"
COMMITTED = ("tmats.txt", "icd.csv", "icd.md", "parameters.md", "assumptions_w0.3.md")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("dict_build")
    d, written = build(CONFIG, out)
    return d, written, out


def test_build_writes_dictionary_and_artefacts(built):
    d, written, out = built
    assert set(written) == {"dictionary", *BUILTIN_GENERATORS}
    path = out / f"dictionary.{d.dict_version}.json"
    assert written["dictionary"] == [path]
    assert read_compiled(path).dict_hash == d.dict_hash
    for name in (*COMMITTED, "tmats_setup_record.c10"):
        assert (out / name).is_file(), name


def test_setup_record_file_parses_with_pychapter10(built):
    from chapter10 import C10

    _, _, out = built
    pkts = list(C10(io.BytesIO((out / "tmats_setup_record.c10").read_bytes())))
    assert [p.data_type for p in pkts] == [0x01]


def test_committed_generated_artefacts_are_current(built):
    """src/phalanx/dictionary/generated/ is regenerated output; it must match a fresh build byte for byte."""
    _, _, out = built
    for name in COMMITTED:
        assert (GENERATED / name).read_bytes() == (out / name).read_bytes(), f"{name}: re-run cli.py build"


def test_extra_generator_hook_receives_the_dictionary(tmp_path):
    seen = {}

    def contract_stub(d: Dictionary, out: Path) -> list[Path]:
        seen["hash"] = d.dict_hash
        p = out / "contract_probe.txt"
        p.write_text(f"{d.dict_version} {len(d.units_map())}\n")
        return [p]

    d, written = build(CONFIG, tmp_path, extra_generators={"contract": contract_stub})
    assert seen["hash"] == d.dict_hash
    assert written["contract"] == [tmp_path / "contract_probe.txt"]


def test_manifest_import_string_generator(tmp_path):
    cfg = tmp_path / "dictionary"
    shutil.copytree(CONFIG, cfg)
    manifest = load_yaml(cfg / "dictionary.yaml")
    manifest["generators"] = ["icd", "phalanx.dictionary.generators:_gen_param_table"]
    (cfg / "dictionary.yaml").write_text(dump_yaml(manifest), encoding="utf-8")
    _, written = build(cfg, tmp_path / "out")
    assert set(written) == {"dictionary", "icd", "phalanx.dictionary.generators:_gen_param_table"}


def test_registered_generator_and_import_safety(tmp_path, built):
    d, _, _ = built
    register_generator("probe", lambda dd, out: [])
    assert run_generators(d, tmp_path, ["probe"]) == {"probe": []}
    with pytest.raises(ValueError, match="phalanx package"):
        resolve_generator("os:system")
    with pytest.raises(KeyError):
        resolve_generator("not-a-generator")
    with pytest.raises(ValueError, match="built-in"):
        register_generator("tmats", lambda dd, out: [])


def test_contract_v0_adapter_through_the_manifest_hook(tmp_path, built):
    """The W0.4 contract generator runs through the import-string hook and binds the dictionary identity."""
    import json

    d, _, _ = built
    spec = "phalanx.dictionary.generators:contract_v0_generator"
    written = run_generators(d, tmp_path, [spec])[spec]
    names = {p.name for p in written}
    assert "contract.md" in names and "dictionary_binding.json" in names
    binding = json.loads((tmp_path / "contract" / "v0" / "dictionary_binding.json").read_text())
    assert binding["dict_version"] == d.dict_version and binding["dict_hash"] == d.dict_hash
    assert binding["units"] == d.units_map()
