"""Dev-time converter: pyCycle map / thermo source files -> the M07 parameter CSV tables.

Provenance tool, not used at run time. The pyCycle files (Apache-2.0, OpenMDAO/pyCycle commit
``ee7e16126a7a54b5fe35292c53b7eb4e9572620b``) are **downloaded data, treated as untrusted**: this module
parses them as text with :func:`ast.parse` / :func:`ast.literal_eval` and never imports or executes them.

Reproduce the committed tables (paths are arguments, nothing is read from data directories implicitly)::

    python -I -m phalanx.engine._mapgen <dir with axi5.py, HPC_map.py, HPT_map.py, LPT_map.py, janaf.py> \
        configs/tejas/params/M07

Output CSVs (one header row, numeric columns only, long format):

- ``fan_map_axi5.csv``  (nc, rline, wc, pr, eff): AXI5 compressor map, alpha = 0 slice (VG on schedule).
- ``hpc_map_hbtf.csv``  (nc, rline, wc, pr, eff): HBTF HPC map, alpha = 0 slice.
- ``hpt_map_hbtf.csv``  (np, pr, wp, eff): HBTF HPT map, alpha = 1 slice.
- ``lpt_map_hbtf.csv``  (np, pr, wp, eff): HBTF LPT map, alpha = 1 slice.
- ``nasa9_species.csv`` (species_id, range_id, a1..a7, b1, b2, molar_mass): NASA 9-coefficient polynomials for
  N2, O2, Ar, CO2, H2O (ids 0..4), ranges 200-1000 K (0) and 1000-6000 K (1).
"""

from __future__ import annotations

import ast
import csv
import sys
from pathlib import Path

import numpy as np

PYCYCLE_COMMIT = "ee7e16126a7a54b5fe35292c53b7eb4e9572620b"
SPECIES = ("N2", "O2", "Ar", "CO2", "H2O")


def _assignments(text: str) -> dict[str, object]:
    """Literal values of ``X.attr = np.array(<literal>)`` / ``X.attr = <literal>`` statements (no
    execution)."""
    out: dict[str, object] = {}
    for node in ast.parse(text).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        tgt = node.targets[0]
        if not isinstance(tgt, ast.Attribute):
            continue
        val = node.value
        if isinstance(val, ast.Call) and getattr(val.func, "attr", "") == "array" and val.args:
            val = val.args[0]
        try:
            out[tgt.attr] = ast.literal_eval(val)
        except ValueError:
            continue
    return out


def compressor_rows(text: str, alpha_index: int = 0) -> list[list[float]]:
    a = _assignments(text)
    nc = np.asarray(a["NcMap"], float)
    rl = np.asarray(a["RlineMap"], float)
    wc = np.asarray(a["WcMap"], float)[alpha_index]
    pr = np.asarray(a["PRmap"], float)[alpha_index]
    ef = np.asarray(a["effMap"], float)[alpha_index]
    assert wc.shape == pr.shape == ef.shape == (nc.size, rl.size)
    return [[nc[i], rl[j], wc[i, j], pr[i, j], ef[i, j]] for i in range(nc.size) for j in range(rl.size)]


def turbine_rows(text: str, alpha_index: int = 0) -> list[list[float]]:
    a = _assignments(text)
    npm = np.asarray(a["NpMap"], float)
    pr = np.asarray(a["PRmap"], float)
    wp = np.asarray(a["WpMap"], float)[alpha_index]
    ef = np.asarray(a["effMap"], float)[alpha_index]
    assert wp.shape == ef.shape == (npm.size, pr.size)
    return [[npm[i], pr[j], wp[i, j], ef[i, j]] for i in range(npm.size) for j in range(pr.size)]


def janaf_rows(text: str) -> list[list[float]]:
    """NASA-9 coefficients for the five frozen-composition species,
    parsed from janaf.py's OrderedDict literal."""
    tree = ast.parse(text)
    products = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "products":
            products = node.value
    if not isinstance(products, ast.Call) or not products.args:
        raise ValueError("unexpected janaf.py structure: products must be OrderedDict([...])")
    pairs = products.args[0]  # OrderedDict([ (name, {...}), ... ])
    data: dict[str, dict] = {}
    for elt in pairs.elts:
        name = ast.literal_eval(elt.elts[0])
        d = elt.elts[1]
        entry = {}
        for k, v in zip(d.keys, d.values, strict=True):
            key = ast.literal_eval(k)
            if key in ("coeffs", "wt"):
                entry[key] = ast.literal_eval(v)
        data[name] = entry
    rows = []
    for sid, sp in enumerate(SPECIES):
        c = data[sp]["coeffs"]
        for rid in (0, 1):
            rows.append([sid, rid, *[float(x) for x in c[rid]], float(data[sp]["wt"])])
    return rows


def _write(path: Path, header: list[str], rows: list[list[float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([repr(float(x)) for x in r])


def main(src_dir: str, out_dir: str) -> None:
    s, o = Path(src_dir), Path(out_dir)
    o.mkdir(parents=True, exist_ok=True)
    rd = lambda n: (s / n).read_text(encoding="utf-8")  # noqa: E731
    _write(o / "fan_map_axi5.csv", ["nc", "rline", "wc", "pr", "eff"], compressor_rows(rd("axi5.py"), 0))
    _write(o / "hpc_map_hbtf.csv", ["nc", "rline", "wc", "pr", "eff"], compressor_rows(rd("HPC_map.py"), 0))
    _write(o / "hpt_map_hbtf.csv", ["np", "pr", "wp", "eff"], turbine_rows(rd("HPT_map.py"), 0))
    _write(o / "lpt_map_hbtf.csv", ["np", "pr", "wp", "eff"], turbine_rows(rd("LPT_map.py"), 0))
    hdr = ["species_id", "range_id", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "b1", "b2", "molar_mass"]
    _write(o / "nasa9_species.csv", hdr, janaf_rows(rd("janaf.py")))


if __name__ == "__main__":  # pragma: no cover - dev tool
    main(sys.argv[1], sys.argv[2])
