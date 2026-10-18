"""Fixed, deterministic order of all 687-CAL flights (written before any flight data is read).

The analysis always uses a *prefix* of this order: the first 5 flights for the verification stage, then the
first n flights given by the pre-registered n rule (PREREGISTRATION.md section 7). Prefixes are nested, so
scaling up never re-draws earlier flights.

Only file names from `analysis/settling_experiment/results/splits.csv` are used here; no MAT file is opened.

Usage: python -I select_flights.py <out_json>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir

import numpy as np
from common import SPLITS_CSV, cal_flights, order_generator

from phalanx.validation.samples import population_sha256


def main(out_json: str) -> None:
    cal = cal_flights()
    gen, source = order_generator()
    order = [str(x) for x in gen.permutation(np.asarray(cal))]
    assert sorted(order) == cal and len(order) == 152
    doc = {
        "purpose": "MF1-D flight order: verify on order[:5]; scale on order[:n] (n rule, prereg s7)",
        "population": "687-CAL (analysis/settling_experiment/results/splits.csv)",
        "splits_csv": str(SPLITS_CSV.relative_to(SPLITS_CSV.parents[3])),
        "population_size": len(cal),
        "population_sha256": population_sha256(cal),
        "rule": "gen.permutation(sorted(population)); prefixes are the samples",
        "source": source,
        "order": order,
    }
    with open(out_json, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(json.dumps({k: v for k, v in doc.items() if k != "order"}, indent=1))
    print("first 5:", order[:5])


if __name__ == "__main__":
    main(sys.argv[1])
