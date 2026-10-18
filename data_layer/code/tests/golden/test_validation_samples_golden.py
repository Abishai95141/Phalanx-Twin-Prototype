"""A5 golden: the selector reproduces the saved round-2 flight lists exactly (data-free: tracked files only).

Inputs (tracked, read-only): `analysis/settling_experiment/results/splits.csv` (round-1 splits) and the lists
the
round-2 runner saved before any analysis,
`analysis/settling_experiment_round2/results/holdout_652*/list_*.txt`.
"""

from __future__ import annotations

import csv

import pytest

from phalanx.validation.reference import load_round2_lists
from phalanx.validation.samples import select_flights, temporal_halves

pytestmark = pytest.mark.golden


@pytest.fixture(scope="module")
def r2(repo_root):
    res = repo_root / "analysis" / "settling_experiment_round2" / "results"
    with open(repo_root / "analysis" / "settling_experiment" / "results" / "splits.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return rows, load_round2_lists(res / "holdout_652"), load_round2_lists(res / "holdout_652_s20")


def test_full_holdout_partner_list(r2):
    """D_tail partner: 110 of the 229 round-1 687-TEST flights, root seed 20261015
    (run_holdout.holdout_lists)."""
    rows, full, _ = r2
    test = [r["file"] for r in rows if r["set"] == "687-TEST"]
    assert sorted(r["file"] for r in rows if r["set"] == "652") == full["holdout"]
    s = select_flights(
        test,
        len(full["holdout"]),
        entropy=20261015,
        purpose="D_tail partner",
        justification="equal flight counts per comparison (prereg section 2)",
    )
    assert list(s.flights) == full["partner"]


def test_s20_sample_batch_lists(r2):
    """The 20-flight sample batch: entropy [20261015, 99] (holdout) and [20261015, 98] (partner)."""
    _, full, s20 = r2
    h = select_flights(
        full["holdout"],
        20,
        entropy=[20261015, 99],
        purpose="sample batch",
        justification="20-flight sample batch before the full run (prereg section 7)",
    )
    p = select_flights(
        full["partner"], 20, entropy=[20261015, 98], purpose="sample batch", justification="equal counts"
    )
    assert list(h.flights) == s20["holdout"] and list(p.flights) == s20["partner"]


def test_temporal_halves_match_round2(r2):
    rows, full, s20 = r2
    date = {r["file"]: r["datestr"] for r in rows}
    for lists in (full, s20):
        early, late = temporal_halves(lists["holdout"], date)
        assert early == lists["early"] and late == lists["late"]
