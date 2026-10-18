"""A2 defect rates: post-truth data-quality defects occur at their configured rates, are decided per record
identity (independent of batching: CRN across forks) and are listed in the manifest.

Sample size: n = 6,000 synthetic records per family. For a rate p the 99.9 % binomial interval half-width is
3.29 * sqrt(p (1 - p) / n): 0.009 at p = 0.05 and 0.019 at p = 0.3, tight enough to catch a wrong rate or a
rate applied to the wrong record family, and cheap (< 2 s).
"""

from __future__ import annotations

import math

import pytest

from phalanx.maintenance.config import DefectRates
from phalanx.maintenance.defects import DefectInjector
from phalanx.maintenance.records import contract_v0, maint_row

NS = 1_000_000_000
EPOCH = 1_790_035_200 * NS
C = contract_v0()
N = 6000
RATES = DefectRates(
    cann_underreport=0.25,
    missing_part_record=0.05,
    wrong_form=0.02,
    recon_lag_fraction=0.3,
    recon_lag_mean_s=14 * 86_400,
    text_noise_rate=0.03,
    xxx_serial=0.02,
    duplicate_snag=0.03,
    unfilled_logbook=0.5,
    underreported_tail=0.0,
)


def _rows(rtype, n, **extra):
    out = []
    for i in range(n):
        f = dict(
            tail_no="T01",
            serial_no=f"S-{i:05d}",
            discrepancy_text="ENG OIL PRESS FLUCTUATES IN AB CAUTION ON",
        )
        f.update(extra)
        if rtype == "COMPONENT_LIFE":
            f["install_action"] = "INSTALL"
        out.append(
            maint_row(
                C,
                dict_version="0.1.1",
                dict_hash="ab" * 16,
                record_type=rtype,
                record_key=f"K-{i:05d}",
                record_version=0,
                t_event=EPOCH + i * NS,
                t_ingest=EPOCH + i * NS,
                **f,
            )
        )
    return out


def _within(k, n, p):
    half = 3.29 * math.sqrt(p * (1 - p) / n)
    return abs(k / n - p) <= half


def _inj():
    return DefectInjector(
        RATES, root=0xD0D0, scenario="dq", contract=C, dict_version="0.1.1", dict_hash="ab" * 16
    )


@pytest.mark.statistical
def test_component_record_defect_rates_match_targets():
    rows = _rows("COMPONENT_LIFE", N)
    hints = [{"depot_returned": i % 2 == 0} for i in range(N)]
    obs, man = _inj().apply(rows, hints)
    sub = [m["subject_id"] for m in man]
    assert _within(sub.count("DQ.MISSING_PART_RECORD"), N, RATES.missing_part_record)
    kept = N - sub.count("DQ.MISSING_PART_RECORD")
    assert len(obs) == kept
    assert _within(sub.count("DQ.RECON_LAG"), kept, RATES.recon_lag_fraction)
    depot_kept = sum(
        1
        for r, h in zip(rows, hints, strict=True)
        if h["depot_returned"] and r["record_id"] in {o["record_id"] for o in obs}
    )
    assert _within(sub.count("DQ.UNFILLED_LOGBOOK"), depot_kept, RATES.unfilled_logbook)
    assert _within(sub.count("DQ.XXX_SERIAL"), kept, RATES.xxx_serial)
    lags = [m["value"] for m in man if m["subject_id"] == "DQ.RECON_LAG"]
    mean_days = sum(lags) / len(lags)
    assert abs(mean_days - 14.0) < 14.0 * 3.29 / math.sqrt(len(lags))  # exponential mean 14 d
    assert all(o["t_ingest"] >= o["t_event"] for o in obs)


@pytest.mark.statistical
def test_snag_defects_wrong_form_duplicates_and_text_noise():
    rows = _rows("DEFECT_WO", N)
    obs, man = _inj().apply(rows, None)
    sub = [m["subject_id"] for m in man]
    assert _within(sub.count("DQ.WRONG_FORM"), N, RATES.wrong_form)
    assert _within(sub.count("DQ.DUPLICATE_SNAG"), N, RATES.duplicate_snag)
    assert len(obs) == N + sub.count("DQ.DUPLICATE_SNAG")
    tokens = N * 8  # 8 tokens per synthetic discrepancy text
    changed = sum(m["value"] for m in man if m["subject_id"] == "DQ.TEXT_NOISE")
    assert _within(int(changed), tokens, RATES.text_noise_rate)
    assert sub.count("DQ.MISSING_PART_RECORD") == 0  # applied to its own family only


@pytest.mark.statistical
def test_cann_underreporting_drops_whole_actions_and_defects_are_batch_independent():
    rows = []
    for i in range(N // 2):
        job = f"SUL-26265-{i:04d}"
        rows += _rows("CANNIBALISATION", 1, linked_job_no=f"CN-{job}")
        rows[-1].update(record_key=f"{job}-CN")
        rows += _rows("CANNIBALISATION", 1, linked_job_no=job)
        rows[-1].update(record_key=f"CN-{job}")
    for r in rows:
        r["record_id"] = maint_row(
            C,
            dict_version="0.1.1",
            dict_hash="ab" * 16,
            record_type=r["record_type"],
            record_key=r["record_key"],
            record_version=0,
            t_event=r["t_event"],
            t_ingest=r["t_ingest"],
        )["record_id"]
    inj = _inj()
    obs, man = inj.apply(rows, None)
    dropped = {m["related_record_id"] for m in man if m["subject_id"] == "DQ.CANN_UNDERREPORT"}
    assert len(dropped) % 2 == 0 and _within(len(dropped) // 2, N // 2, RATES.cann_underreport)
    # one batch or many: identical decisions (identity-keyed, so forks see the same defects)
    obs2 = []
    for k in range(0, len(rows), 37):
        obs2 += inj.apply(rows[k : k + 37], None)[0]
    assert obs2 == obs
    off, man0 = DefectInjector(
        RATES.disabled(), root=1, scenario="dq", contract=C, dict_version="0.1.1", dict_hash="ab" * 16
    ).apply(rows, None)
    assert man0 == [] and off == rows
