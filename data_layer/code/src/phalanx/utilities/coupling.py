"""The report §3 coupling map, as data (A2): one row per edge M09 implements, with its expected sign.

The table lives in ``configs/<platform>/params/M09/coupling_signs.csv`` (columns: edge_id, source, driver,
driven, sign, mechanism, scope). ``sign`` is ``+`` (driven moves with the driver), ``-`` (against) or ``0``
(held within tolerance). ``scope`` is ``M09`` (both ends inside M09) or ``M09-side`` (M09 owns the
response tested here; the other half of the edge belongs to a neighbour and is tested at W2.1). Every row
has a probe in ``tests/integration/test_utilities_coupling.py``; a row without a probe fails the test.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from phalanx.dictionary.params import params_dir

COLUMNS = ("edge_id", "source", "driver", "driven", "sign", "mechanism", "scope")
SIGNS = ("+", "-", "0")
SCOPES = ("M09", "M09-side")


@dataclass(frozen=True)
class CouplingEdge:
    edge_id: str
    source: str
    driver: str
    driven: str
    sign: str
    mechanism: str
    scope: str


def load_coupling_table(platform: str = "tejas", config_root: Path | None = None) -> tuple[CouplingEdge, ...]:
    path = params_dir(platform, config_root) / "M09" / "coupling_signs.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    edges = []
    seen = set()
    for r in rows:
        if tuple(r) != COLUMNS:
            raise ValueError(f"{path.name}: columns must be {COLUMNS}, got {tuple(r)}")
        e = CouplingEdge(**{k: r[k].strip() for k in COLUMNS})
        if e.sign not in SIGNS or e.scope not in SCOPES or not e.edge_id or e.edge_id in seen:
            raise ValueError(f"{path.name}: bad row {r}")
        seen.add(e.edge_id)
        edges.append(e)
    return tuple(edges)
