"""W2.4a-1 proxy configuration (configs/proxy_dashlink): derived M08 tables, the documented ratio-unit dip,
the ACMS clock convention, the DASHlink double quantiser and the proxy dictionary pin.

No data: the configuration files and the round-2 frozen M-A relations (an existing result) only.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from phalanx.acquisition.kernel import AP_OF, AP_ON, AP_QN, AP_SF, AQ_CMAX, AQ_CMIN, AQ_HASREC, quantise_code
from phalanx.dictionary import load_dictionary
from phalanx.proxy.config import PLATFORM, config_root, load_proxy_config
from phalanx.proxy.schedules import derive_tables, operating_line, write_tables

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "analysis" / "settling_experiment_round2" / "results" / "frozen" / "S" / "ma_readable.json"
M08_DIR = config_root() / PLATFORM / "params" / "M08"
#: compiled proxy dictionary hash (configs/proxy_dashlink/dictionary, v0.1.0): a change must be deliberate
DICT_HASH = "237f723526dc57e09e743cf6c9093062143cc0d8431f501ac2516ec0d7b9e29c"


@pytest.fixture(scope="module")
def cfg():
    return load_proxy_config()


def test_derived_m08_tables_are_regenerated_exactly(cfg, tmp_path):
    """The committed ru_ref/ru_ff/n2c_pla/cvg CSVs are exactly what `derive_tables` computes from the proxy
    M07 and the round-2 frozen M-A (AD-50 harmonisation; A-W2.4a-14): they cannot drift from the plant."""
    write_tables(derive_tables(cfg.engine, FROZEN), tmp_path)
    for name in ("ru_ref.csv", "ru_ff.csv", "n2c_pla.csv", "cvg_n2c.csv"):
        assert (tmp_path / name).read_text() == (M08_DIR / name).read_text(), name


def test_ratio_unit_line_dip_is_reported(cfg):
    """Known limitation (A-W2.4a-14): with the generic maps the steady Wf/PS3 line is non-monotone in
    corrected core speed (a dip between ~55 % and ~79 %). If a map change removes it, update the assumption
    row."""
    ol = operating_line(cfg.engine)
    o = np.argsort(ol.n2c25)
    x, ru = ol.n2c25[o], ol.ru[o]
    band = (x > 0.5) & (x < 0.85)
    lo = int(np.argmin(np.where(band, ru, np.inf)))
    assert 0.6 < x[lo] < 0.82
    assert ru[lo] < ru[band][0] - 0.5  # a real dip, not noise
    assert np.any(np.diff(ru[band]) < 0) and np.any(np.diff(ru[band]) > 0)


def test_acms_clock_is_the_replay_time_base(cfg):
    """A-W2.4a-12: the recorded words are sampled on a 4 Hz ACMS clock with 0 ppm offset and phase 0, so
    sample j of the record is at j x 250 ms, the instant of input sample j."""
    doms = cfg.recording.domains
    assert len(doms) == 1
    clk = doms[0].clock
    assert float(clk.f_nom_hz) == 4.0 and float(clk.offset_ppm) == 0.0 and int(clk.phase_ns) == 0
    t = clk.sample_times_ns(0, 9)
    assert np.array_equal(np.asarray(t), np.arange(9) * 250_000_000)


@pytest.mark.parametrize(("fam", "modulo", "never"), [("N1", 32, {3, 8, 12, 17, 21, 26, 31}),
                                                      ("N2", 32, {3, 8, 12, 17, 21, 26, 31}),
                                                      ("EGT", 8, {1, 4, 7})])  # fmt: skip
def test_double_quantiser_reproduces_the_never_used_residues(cfg, fam, modulo, never):
    """The DASHlink double quantiser (native grid with its MEASURED offset, then the recorder lattice) leaves
    exactly the never-used recorder-code residues observed in the data (round-2 REPORT §3.5, MEASURED)."""
    did = {"N1": "ENG.N1.REC", "N2": "ENG.N2.REC", "EGT": "ENG.T5.REC"}[fam]
    c = cfg.recording.channels.index(f"{did}:E1")
    p, q = cfg.recording.P[c], cfg.recording.Q[c]
    lo, hi = (20.0, 100.0) if fam != "EGT" else (300.0, 700.0)
    codes = {
        int(quantise_code(x, p[AP_QN], p[AP_ON], p[AP_SF], p[AP_OF], q[AQ_HASREC], q[AQ_CMIN], q[AQ_CMAX])[0])
        for x in np.linspace(lo, hi, 200_001)
    }
    used = {k % modulo for k in codes}
    assert used == set(range(modulo)) - never, sorted(used)
    # negative control: a native grid shifted by half a recorder LSB leaves a different residue set unused
    on_shift = p[AP_ON] + 0.5 * p[AP_SF]
    codes0 = {
        int(quantise_code(x, p[AP_QN], on_shift, p[AP_SF], p[AP_OF], q[AQ_HASREC], q[AQ_CMIN], q[AQ_CMAX])[0])
        for x in np.linspace(lo, hi, 200_001)
    }
    assert {k % modulo for k in codes0} != used


def test_proxy_dictionary_is_pinned():
    d = load_dictionary(platform=PLATFORM)
    assert d.dict_hash == DICT_HASH
    manifest = json.dumps(sorted(c["channel_id"] for c in d.channels()))
    assert "ENG.N1.REC" in manifest and "ENG.FF.REC" in manifest
