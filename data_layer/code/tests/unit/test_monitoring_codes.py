"""M14 code table (AD-48.5, dictionary 0.1.2): the dictionary's single ``bit_codes`` table joined with M14's
behaviour rows. SSS-NNN codes follow the M01 dictionary format (prefix, number block), legends use the 30 CWS
slots, exactly 4 voice warnings on 4 CWS voice channels, every identity field is the dictionary's, monitor
limits resolve in engineering units (dictionary limits or SI parameters converted with the dictionary), and
malformed behaviour tables are rejected (identity-level defects are the dictionary validator's,
``tests/unit/test_dictionary_*``)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from phalanx.dictionary import load_dictionary
from phalanx.monitoring import load_code_table, load_monitoring_params
from phalanx.monitoring.codes import CODES_PATH, CodeTableError

D = load_dictionary()
P = load_monitoring_params()


@pytest.mark.unit
def test_codes_follow_dictionary_format():
    t = load_code_table(D, P)
    fmt = D.code_table("bit_code_format")
    assert len(t.codes) >= 60
    for c in t.codes:
        prefix, num = c.code.split("-")
        assert prefix in fmt["prefixes"]
        assert 1 <= int(num) <= 899
        if c.mechanism == "EXCEEDANCE" and c.src == "cir":
            assert 500 <= int(num) <= 899
    legends = {c.legend for c in t.codes if c.legend}
    assert all(1 <= int(x[5:]) <= 30 for x in legends)
    assert sum(c.voice for c in t.codes) == 4
    assert {c.fault_list for c in t.codes} == {"PFL", "MFL"}
    assert all(c.legend is None for c in t.codes if c.fault_list == "MFL")
    assert all(0.0 < c.cnd < 1.0 for c in t.codes)


@pytest.mark.unit
def test_identity_is_the_dictionary_bit_codes_table():
    """Index, description, severity, list, mechanism, LRU, lane, source, legend and voice of every code are
    the dictionary's, in dictionary index order; ENG-509/510 (dictionary 0.1.2) take ENG-503's behaviour."""
    t = load_code_table(D, P)
    assert [c.code for c in t.codes] == list(D.bit_codes()) and len(t.codes) == 104
    for c in t.codes:
        r = D.bit_code(c.code)
        got = (
            c.index,
            c.desc,
            c.severity,
            c.fault_list,
            c.mechanism,
            c.lru,
            c.lane,
            c.src,
            c.legend,
            c.group,
        )
        want = (
            r["index"],
            r["desc"],
            r["sev"],
            r["list"],
            r["mech"],
            r["lru"],
            r.get("lane") or None,
            r["src"],
        )
        assert got == (*want, r.get("legend") or None, r["group"]), c.code
        assert c.voice_channel == (r.get("voice") or None)
        assert (c.monitor is None) == (r["src"] != "cir")
    by = t.by_code
    for new in ("ENG-509", "ENG-510"):
        assert (by[new].tech, by[new].suspects) == (by["ENG-503"].tech, by["ENG-503"].suspects)
    assert t.legacy["M08"]["ENG-506"] == "ENG-509"  # the dictionary's legacy map for a W1 M08


@pytest.mark.unit
def test_monitor_limits_resolve_in_eu():
    t = load_code_table(D, P).by_code
    assert t["ENG-701"].monitor.limit_eu == pytest.approx(830.0)  # dictionary steady_max, degC
    assert t["STR-701"].monitor.limit_eu == pytest.approx(8.0)  # operational envelope high, g
    assert t["STR-702"].monitor.limit_eu == pytest.approx(-3.5)
    assert t["ECM-702"].monitor.limit_eu == pytest.approx(20.0)  # psi from the SI parameter
    assert t["CWS-701"].monitor.limit_eu == pytest.approx(26.0)  # deg
    assert t["ENG-702"].monitor.limit_eu == pytest.approx(14199.0 / 13270.0 * 100.0)  # % N1 (14,199 rpm)
    assert t["CWS-702"].monitor.limit_eu == pytest.approx(200.0)  # ft
    assert t["ELE-702"].monitor.limit_eu == pytest.approx(22.0)  # normal band low, V
    assert t["ENG-701"].monitor.limit_id == "ENG.T5:steady_max"


def _load(tmp_path: Path, mutate):
    doc = yaml.safe_load(CODES_PATH.read_text(encoding="utf-8"))
    mutate(doc)
    p = tmp_path / "codes.yaml"
    p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return load_code_table(D, P, path=str(p))


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["codes"].update({"XXX-001": dict(d["codes"]["ENG-001"])}),  # not a dictionary code
        lambda d: d["codes"].update({"ENG-950": dict(d["codes"]["ENG-001"])}),  # not a dictionary code
        lambda d: d["codes"].pop("ENG-509"),  # a dictionary code without a behaviour row
        lambda d: d["codes"]["ENG-005"].update({"legend": "CWS-L01"}),  # identity belongs to the dictionary
        lambda d: d["codes"]["CWS-701"].update(
            {"voice": "CWS.VOICE.UC"}
        ),  # identity belongs to the dictionary
        lambda d: d["codes"]["ENG-001"].update({"tech": "quantum"}),  # unknown technology
        lambda d: d["codes"]["ENG-001"].update({"suspects": [["FADEC", 1.5]]}),  # confidence outside [0, 1]
        lambda d: d["codes"]["ENG-201"].update({"regime": "fuzzy"}),
        lambda d: d["codes"]["ENG-001"].update({"monitor": {"persist_s": 1.0, "clear_s": 1.0}}),  # not cir
        lambda d: d["codes"]["ENG-701"].pop("monitor"),  # a cir monitor without its timing
        lambda d: d["codes"]["ENG-701"]["monitor"].update({"channel": "ENG.T5"}),  # identity in the timing
        lambda d: d["codes"]["ENG-701"]["monitor"].update({"persist_s": -1.0}),
        lambda d: d["codes"]["ENG-201"].update({"sympathetic": [["ENG-999", 0.5, 0.0, 1.0]]}),
        lambda d: d.update({"format": "phalanx.m14_codes/1"}),  # the W1 identity-carrying format
    ],
)
def test_malformed_tables_rejected(tmp_path, mutate):
    with pytest.raises(CodeTableError):
        _load(tmp_path, mutate)


@pytest.mark.unit
def test_unmutated_copy_loads(tmp_path):
    """Positive control for the malformed cases: the same dump-and-reload path accepts the real table."""
    assert len(_load(tmp_path, lambda d: None).codes) == 104
