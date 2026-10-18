"""M14 consumes M08's ``fadec.fault`` / ``fadec.caution`` (AD-44; AD-48.5 one code table): FADEC codes are
dictionary ``bit_codes`` (M08 emits the unified table since W2.1b; the W1 ``fadec_codes="M08"`` legacy-map
setting is gone) recorded as BIT records and CWS cautions at the FADEC frame instant; a clear closes the
caution; the FADEC's limit cautions (``src: cir``) are left to M14's ECMS monitors; a code that is not an
external FADEC code is an error.

TEST FIXTURE: payloads in M08's shape. n = 1 sortie per configuration (deterministic)."""

from __future__ import annotations

import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.monitoring import MonitoringConfig, MonitoringModule, load_code_table, load_monitoring_params
from phalanx.monitoring.module import KIND_BIT, KIND_CAUTION

pytestmark = pytest.mark.unit
D = load_dictionary()
P = load_monitoring_params()
CODES = load_code_table(D, P)
SEC = 10**9


def fadec(t, code, set_, *, kind="fadec.fault", lane="", sensor="", t_frame=None):
    pay = {
        "engine": 0,
        "code": code,
        "set": set_,
        "sensor": sensor,
        "lane": lane,
        "description": "SYNTHETIC",
        "t_frame_ns": t if t_frame is None else t_frame,
        "frame": t // (SEC // 60),
    }
    return Event(t, kind, "m14", pay)


def build(**kw):
    m = MonitoringModule(
        "m14", P, config=MonitoringConfig.from_dictionary(D, CODES, ("E1",), regime="mature", **kw)
    )
    sysm = System([m], [], rng=RngService(3, StreamRegistry()), identity=KeyPath.of(scenario="S", tail="T1"))
    return m, sysm


def records(st, code):
    i = CODES.index(code)
    return [
        (int(k), int(t), int(te))
        for k, c, t, te in zip(st["o_kind"], st["o_code"], st["o_t"], st["o_t_end"], strict=True)
        if int(c) == i
    ]


def test_fadec_events_build_bit_and_caution_records():
    _m, sysm = build()
    # dictionary codes: T5 lane A, flameout (WARNING, L05), T5 limit caution (src cir)
    t5, flameout, limit = "ENG-005", "ENG-502", "ENG-701"
    ev = [
        Event(0, "monitor.sortie_start", "m14", {"sortie_id": "T1-0"}),
        fadec(10 * SEC, t5, True, lane="A", sensor="T5", t_frame=10 * SEC - 5_000_000),  # T5 lane A
        fadec(20 * SEC, flameout, True, kind="fadec.caution"),  # flameout -> ENG-502 (WARNING, L05)
        fadec(25 * SEC, flameout, False, kind="fadec.caution"),
        fadec(30 * SEC, limit, True, kind="fadec.caution"),  # T5 limit: recorded by M14's ECMS monitor
    ]
    w = sysm.inject(sysm.start(), ev)
    w, _ = sysm.run(w, 31 * 240 + 2)
    st = w.states["m14"]
    t5 = records(st, "ENG-005")
    assert (KIND_BIT, 10 * SEC - 5_000_000, -1) in t5  # at the FADEC frame instant
    assert any(k == KIND_CAUTION for k, _, _ in t5)
    fo = records(st, "ENG-502")
    assert (KIND_CAUTION, 20 * SEC, 25 * SEC) in fo  # caution closed by the clear
    assert records(st, "ENG-701") == []  # not re-recorded from the FADEC
    j5 = next(i for i, c in enumerate(st["o_code"]) if c == CODES.index("ENG-005"))
    assert str(st["o_lane"][j5]) == "A"
    bad = sysm.inject(w, [fadec(w.t_ns + SEC, "ENG-999", True)])
    with pytest.raises(ContractError):
        sysm.run(bad, 241)


def test_legacy_map_targets_are_fadec_reported_or_ecms_codes():
    """Every M08 W1 code maps to an external FADEC code, or to an ECMS limit monitor (not re-recorded)."""
    by = CODES.by_code
    m08 = CODES.legacy["M08"]
    assert m08 and all(
        (by[v].lru == "FADEC" and by[v].src == "external") or by[v].src == "cir" for v in m08.values()
    )
    assert {k for k, v in m08.items() if by[v].src == "cir"} == {"ENG-701", "ENG-702", "ENG-703"}


@pytest.mark.parametrize(
    "code",
    [
        "ENG-999",  # not a dictionary code
        "FCS-201",  # a dictionary code the FADEC does not report (DFCC internal)
        "ENG-201",  # FADEC processor self-test: M14's internal test, not a FADEC report
    ],
)
def test_codes_the_fadec_cannot_report_are_contract_errors(code):
    _m, sysm = build()
    w = sysm.inject(sysm.start(), [Event(0, "monitor.sortie_start", "m14", {"sortie_id": "T1-0"})])
    with pytest.raises(ContractError):
        sysm.run(sysm.inject(w, [fadec(SEC, code, True)]), 241)


def test_every_code_the_real_m08_emits_is_accepted():
    """W2.1b re-key: every code M08 can emit (``phalanx.fadec.codes.FAULT_CODES``) is an external FADEC code
    or
    an ECMS limit caution (``src: cir``) of M14's table, so no legacy translation is needed."""
    from phalanx.fadec.codes import FAULT_CODES

    by = CODES.by_code
    for fc in FAULT_CODES:
        c = by[fc.code]
        assert (c.lru == "FADEC" and c.src == "external") or c.src == "cir", (fc.code, c.lru, c.src)
