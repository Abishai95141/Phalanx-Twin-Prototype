"""Data-quality defects injected **after** truth, with a restricted manifest (architecture §10; report §12).

The maintenance-records truth (every row M18 emits) stays in the restricted record log; consumers see the
*observed* rows produced here. Every decision is a pure function of (root, scenario, record identity) through
an identity-keyed stream (AD-37), so the same record gets the same defect in every batch and in every fork
(CRN), and the manifest lets evaluators measure recovery from bad records (report §12).

Defects (applies to -> effect; evidence):

- ``CANN_UNDERREPORT``: a cannibalisation action (all its records) -> not reported; GAO-02-86 (up to 50 %).
- ``MISSING_PART_RECORD``: COMPONENT_LIFE -> missing; GAO-20-316 (81 % at one F-35 site).
- ``WRONG_FORM``: DEFECT_WO / INSPECTION / EXCEEDANCE_INSPECTION -> filed under another record type;
  UK SI Hawk XX204.
- ``RECON_LAG``: SHOP_FINDING / SUPPLY_DEMAND / COMPONENT_LIFE -> entered late (exponential, mean 14 d);
  Hagan & Slack.
- ``TEXT_NOISE``: free text -> misspellings, dropped letters, variant abbreviations; MaintNet, NAMP typos.
- ``XXX_SERIAL``: records with a serial -> serial recorded as 'XXX'; NAMP / OOMA default.
- ``DUPLICATE_SNAG``: DEFECT_WO first version -> entered twice under a new job number; TO 00-20-1 §5.4.1.1.
- ``UNFILLED_LOGBOOK``: INSTALL of a depot-returned unit -> item hours and cycles empty; CAG 24/2017.
- ``UNDERREPORTED_TAIL``: a tail's AVAILABILITY_STATE records -> not reported; CAG 24/2017 (12 of 14).

Rates are M18.yaml ``defects`` parameters [ASSUMPTION A-W1.8-12].
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from phalanx.core.rng import KeyPath, RngService, Stream, StreamDecl, StreamRegistry, Variate
from phalanx.dictionary.contract import Contract

from .config import DefectRates
from .records import MAINT, label_row, rid_hex
from .timebase import NS, to_s

DEFECT_DECL = StreamDecl(
    "m18",
    "defects",
    ("scenario", "event"),
    Variate.GENERATOR,
    owner="M18",
    description="post-truth data-quality defect decisions per record identity",
)
WRONG_FORM_SWAP = {"DEFECT_WO": "INSPECTION", "INSPECTION": "DEFECT_WO", "EXCEEDANCE_INSPECTION": "DEFECT_WO"}
LAG_TYPES = frozenset({"SHOP_FINDING", "SUPPLY_DEMAND", "COMPONENT_LIFE"})
VARIANTS = {
    "REMOVED": "REMVD",
    "REPLACED": "REPLCD",
    "INSTALLED": "INSTLD",
    "CHECK": "CHK",
    "CHECKED": "CHKD",
    "AND": "&",
    "INSPECTION": "INSP",
    "GOOD": "GD",
    "ENGINE": "ENG",
    "HYDRAULIC": "HYD",
    "OPS": "OPNS",
}
# per-record uniform slots
U_CANN, U_MISSING, U_FORM, U_LAG, U_LAGX, U_TEXT, U_XXX, U_DUP, U_LOGBOOK, U_DUP_DELAY = range(10)


class DefectInjector:
    def __init__(
        self,
        rates: DefectRates,
        *,
        root: int,
        scenario: str,
        contract: Contract,
        dict_version: str,
        dict_hash: str,
    ) -> None:
        self.rates = rates
        self.contract = contract
        self.scenario = scenario
        self.dv, self.dh = dict_version, dict_hash
        self.service = RngService(int(root), StreamRegistry([DEFECT_DECL]))

    def _gen(self, identity: str) -> np.random.Generator:
        path = KeyPath.of(scenario=self.scenario, event=identity, subsystem="m18", component="defects")
        return Stream(self.service, path, DEFECT_DECL).generator(0)

    def _u(self, identity: str) -> np.ndarray:
        return self._gen(identity).random(16)

    def _label(self, defect: str, row: Mapping[str, Any], *, value: float | None = None) -> dict[str, Any]:
        return label_row(
            self.contract,
            dict_version=self.dv,
            dict_hash=self.dh,
            label_kind="DEFECT",
            subject_id=f"DQ.{defect}",
            t_true=int(row["t_event"]),
            source_module="M18",
            tail_no=row.get("tail_no"),
            sortie_id=row.get("sortie_id"),
            serial_no=row.get("serial_no"),
            related_record_id=row["record_id"],
            category=defect,
            value=value,
            units="1" if value is not None else None,
        )

    def _noise(self, text: str, g: np.random.Generator) -> tuple[str, int]:
        out, n = [], 0
        for tok in text.split(" "):
            if tok and float(g.random()) < self.rates.text_noise_rate:
                n += 1
                mode = int(g.integers(3))
                if mode == 0 and tok.upper() in VARIANTS:
                    tok = VARIANTS[tok.upper()]
                elif mode == 1 and len(tok) > 3:
                    i = int(g.integers(len(tok) - 1))
                    tok = tok[:i] + tok[i + 1] + tok[i] + tok[i + 2 :]
                elif len(tok) > 2:
                    i = int(g.integers(1, len(tok)))
                    tok = tok[:i] + tok[i + 1 :]
            out.append(tok)
        return " ".join(out), n

    def apply(
        self, rows: Sequence[Mapping[str, Any]], hints: Sequence[Mapping[str, Any] | None] | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """(observed rows, manifest label rows) for a batch of truth maint.records rows."""
        r_ = self.rates
        observed: list[dict[str, Any]] = []
        manifest: list[dict[str, Any]] = []
        hints = hints if hints is not None else [None] * len(rows)
        for truth, hint in zip(rows, hints, strict=True):
            row = copy.deepcopy(dict(truth))
            rt = row["record_type"]
            u = self._u(row["record_id"])
            if rt == "AVAILABILITY_STATE" and row.get("tail_no"):
                if float(self._u(f"tail:{row['tail_no']}")[0]) < r_.underreported_tail:
                    manifest.append(self._label("UNDERREPORTED_TAIL", row))
                    continue
            if rt == "CANNIBALISATION":
                key = (
                    row["record_key"]
                    if row["record_key"].endswith("-CN")
                    else f"{row.get('linked_job_no')}-CN"
                )
                if float(self._u(f"cann:{key}")[0]) < r_.cann_underreport:
                    manifest.append(self._label("CANN_UNDERREPORT", row))
                    continue
            if rt == "COMPONENT_LIFE" and u[U_MISSING] < r_.missing_part_record:
                manifest.append(self._label("MISSING_PART_RECORD", row))
                continue
            if (
                rt == "COMPONENT_LIFE"
                and row.get("install_action") == "INSTALL"
                and (hint or {}).get("depot_returned")
                and u[U_LOGBOOK] < r_.unfilled_logbook
            ):
                row["item_hours"], row["item_cycles"] = None, None
                manifest.append(self._label("UNFILLED_LOGBOOK", row))
            if rt in LAG_TYPES and u[U_LAG] < r_.recon_lag_fraction:
                lag_s = to_s(-math.log(1.0 - float(u[U_LAGX])) * r_.recon_lag_mean_s)
                row["t_ingest"] = int(row["t_ingest"]) + lag_s * NS
                manifest.append(self._label("RECON_LAG", row, value=lag_s / 86400.0))
            if r_.text_noise_rate > 0:
                g = self._gen(f"text:{row['record_id']}")
                total = 0
                for f in ("discrepancy_text", "corrective_action_text"):
                    if row.get(f):
                        row[f], n = self._noise(row[f], g)
                        total += n
                if total:
                    manifest.append(self._label("TEXT_NOISE", row, value=float(total)))
            if row.get("serial_no") and u[U_XXX] < r_.xxx_serial:
                row["serial_no"] = "XXX"
                manifest.append(self._label("XXX_SERIAL", row))
            if rt in WRONG_FORM_SWAP and u[U_FORM] < r_.wrong_form:
                row["record_type"] = WRONG_FORM_SWAP[rt]
                row["record_id"] = rid_hex(
                    self.contract,
                    MAINT,
                    {
                        "record_type": row["record_type"],
                        "record_key": row["record_key"],
                        "record_version": int(row["record_version"]),
                    },
                )
                manifest.append(self._label("WRONG_FORM", row))  # related = the mis-filed (observed) record
            observed.append(row)
            if rt == "DEFECT_WO" and int(row["record_version"]) == 0 and u[U_DUP] < r_.duplicate_snag:
                dup = copy.deepcopy(row)
                dup["record_key"] = f"{row['record_key']}-D"
                dup["job_no"] = dup["record_key"]
                delay = (300 + int(float(u[U_DUP_DELAY]) * 3300)) * NS
                dup["t_event"] = int(row["t_event"]) + delay
                dup["t_open"] = dup["t_event"] if dup.get("t_open") is not None else None
                dup["t_ingest"] = max(int(row["t_ingest"]), dup["t_event"])
                dup["record_id"] = rid_hex(
                    self.contract,
                    MAINT,
                    {"record_type": dup["record_type"], "record_key": dup["record_key"], "record_version": 0},
                )
                observed.append(dup)
                manifest.append(self._label("DUPLICATE_SNAG", {**row, "record_id": dup["record_id"]}))
        return observed, manifest
