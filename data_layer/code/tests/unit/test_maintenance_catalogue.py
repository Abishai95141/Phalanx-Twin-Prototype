"""M18 catalogue, code tables and typed configuration (provenance rules and derived quantities)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import yaml
from scipy.stats import lognorm, norm

from phalanx.maintenance.catalogue import (
    NUMERIC_COLUMNS,
    CatalogueError,
    load_catalogue,
    load_codes,
)
from phalanx.maintenance.config import fit_lognormal_to_bins, load_m18_config
from phalanx.maintenance.timebase import DAY_S

REPO = Path(__file__).resolve().parents[2]
CAT = REPO / "configs" / "tejas" / "params" / "M18" / "catalogue.yaml"
CODES = REPO / "configs" / "tejas" / "params" / "M18" / "codes.yaml"


@pytest.mark.unit
def test_catalogue_loads_with_synthetic_labels_and_unique_positions():
    cat = load_catalogue()
    assert cat.synthetic_label.startswith("SYNTHETIC")
    codes = [p.code for p in cat.positions]
    assert len(codes) == len(set(codes)) == 19
    assert all(c.part_no.startswith("SYN-") for c in cat.classes)
    # DIRECT anchors carried as per-cell evidence (CAG 17/2015, DDP AMAGB / chute)
    assert cat.cls("AMAGB").v("life_fh") == pytest.approx(750 * 3600)
    assert cat.cls("CHUTE").v("life_streams") == 45
    assert cat.cls("ENG").v("stock_per_ac") == pytest.approx(0.2)


@pytest.mark.unit
def test_catalogue_rejects_missing_evidence_and_unregistered_assumption(tmp_path):
    doc = yaml.safe_load(CAT.read_text())
    bad = dict(doc)
    bad["columns"] = dict(doc["columns"])
    bad["columns"]["ts_hours"] = {k: v for k, v in doc["columns"]["ts_hours"].items() if k != "evidence"}
    p = tmp_path / "c1.yaml"
    p.write_text(yaml.safe_dump(bad))
    with pytest.raises(CatalogueError, match="evidence"):
        load_catalogue(p)
    bad2 = dict(doc)
    bad2["columns"] = dict(doc["columns"])
    bad2["columns"]["rr_hours"] = {**doc["columns"]["rr_hours"], "assumption_id": "A-W1.8-999"}
    p2 = tmp_path / "c2.yaml"
    p2.write_text(yaml.safe_dump(bad2))
    with pytest.raises(CatalogueError, match="not registered"):
        load_catalogue(p2, repo_root=REPO)


@pytest.mark.unit
def test_catalogue_rejects_non_synthetic_part_numbers_and_bad_probabilities(tmp_path):
    doc = yaml.safe_load(CAT.read_text())
    doc["classes"]["ENG"]["part_no"] = "F404-REAL-PN"
    doc["classes"]["FADEC"]["p_isolate"] = 1.5
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(doc))
    with pytest.raises(CatalogueError) as e:
        load_catalogue(p)
    msg = str(e.value)
    assert "synthetic" in msg and "probability" in msg


@pytest.mark.unit
def test_with_values_changes_values_and_hash_only_where_asked():
    cat = load_catalogue()
    c2 = cat.with_values({"OBOGS": {"p_isolate": 1.0}})
    assert c2.cls("OBOGS").v("p_isolate") == 1.0
    assert c2.cls("ENG").values == cat.cls("ENG").values
    assert c2.hash != cat.hash
    assert c2.pos("OBOGS").cls is c2.cls("OBOGS")
    with pytest.raises(KeyError):
        cat.with_values({"OBOGS": {"not_a_column": 1.0}})
    assert set(NUMERIC_COLUMNS) == set(cat.cls("ENG").values)


@pytest.mark.unit
def test_code_tables_carry_meaning_and_transfer_and_reject_gaps(tmp_path):
    codes = load_codes()
    for name, table in codes.tables.items():
        for code, d in table.items():
            assert d["meaning"] and d["transfer"], (name, code)
    assert codes.servicing_order == ("SRV-L1", "SRV-L2-MINOR", "SRV-L2-MAJOR", "ROH")
    doc = yaml.safe_load(CODES.read_text())
    del doc["tables"]["malfunction"]["MAL-BIT"]["transfer"]
    p = tmp_path / "codes.yaml"
    p.write_text(yaml.safe_dump(doc))
    with pytest.raises(CatalogueError, match="transfer"):
        load_codes(p)


@pytest.mark.unit
def test_supply_fit_reproduces_cag_bins():
    """The wholesale lead-time log-normal is fitted to the CAG IL-76 AOG bins (conditional on the 4 reported
    bins, 61.9 % of demands: conflict noted in the README). The 2-parameter fit to 3 cumulative points matches
    each within 0.06."""
    cfg = load_m18_config()
    edges_d = [15.0, 30.0, 180.0]
    shares = [0.1083, 0.0341, 0.2518, 0.2249]
    target = np.cumsum(shares[:-1]) / sum(shares)
    dist = lognorm(s=cfg.lead_sigma, scale=math.exp(cfg.lead_mu))
    got = dist.cdf(np.array(edges_d) * DAY_S)
    assert np.max(np.abs(got - target)) < 0.06
    assert 80 < cfg.lead_median_days() < 120
    mu, sigma = fit_lognormal_to_bins([1.0, 2.0], [0.5, 0.25, 0.25])
    assert mu == pytest.approx(0.0, abs=1e-12)  # median at the 50 % edge
    assert sigma > 0


@pytest.mark.unit
def test_servicing_median_gives_the_cag_on_time_fraction():
    cfg = load_m18_config()
    # P(D <= prescribed) for D = prescribed * factor * exp(sigma Z)
    p = norm.cdf(-math.log(cfg.srv_median_factor) / cfg.srv_sigma)
    assert p == pytest.approx(0.34, abs=1e-12)


@pytest.mark.unit
def test_config_overrides_are_recorded_and_unknown_fields_rejected():
    cfg = load_m18_config()
    c2 = cfg.with_values(pod_borescope=1.0)
    assert c2.pod_borescope == 1.0 and dict(c2.overrides) == {"pod_borescope": 1.0}
    with pytest.raises(KeyError):
        cfg.with_values(not_a_field=1)
