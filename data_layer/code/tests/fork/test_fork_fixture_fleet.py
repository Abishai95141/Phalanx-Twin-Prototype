"""TEST FIXTURE (W1.8): a usage-mode fleet that drives the operations layer (M18, M21, M22) in Wave 1.

It stands in for M02 (flying programme), M10/M11 (per-serial failure processes, induced defects, wash
recovery) and M14 (BIT, exceedance and caution events) until W2.6 wires the real modules. It lives under
``tests/`` and is never imported by ``src/`` (W1 common rules). Its parameter values are fixture choices
(``FIXTURE_SOURCE``) made only to exercise the operations layer at a plausible order of magnitude; no
calibration claim rests on them.

The fixture follows the operations event protocol (``src/phalanx/maintenance/README.md``), so W2.6 can replace
it module by module. Its randomness is identity-keyed (CRN): failure thresholds per (scenario, serial, life
number), sortie draws per (scenario, tail, date), false alarms and exceedances per (scenario, tail, sortie).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.rng import DrawLedger, StreamDecl, Variate
from phalanx.core.scheduler import System
from phalanx.core.state import Field, State, StateSchema
from phalanx.dictionary.contract import Contract
from phalanx.fork.builder import OpsIds, OpsOnlyBuilder
from phalanx.ground.rid import record_id
from phalanx.health.protocol import plain_payload, read_payload
from phalanx.maintenance.config import M18Config, load_m18_config
from phalanx.maintenance.docstate import Cow, encode_doc
from phalanx.maintenance.records import contract_v0
from phalanx.maintenance.timebase import DAY_S, NS
from phalanx.maintenance.world import FleetSpec, InternalPolicy, OpsTargets

FIXTURE_SOURCE = "W1.8 TEST FIXTURE (not a model deliverable)"
H = 3600 * NS
DAY = DAY_S * NS
EPOCH = 1_790_035_200 * NS  # 2026-09-22 00:00 UTC = 05:30 IST; a whole second


@dataclass(frozen=True)
class FixtureParams:
    """Fixture choices (not evidence): see module docstring."""

    flying_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4)
    plan_time_s: int = 7 * 3600
    first_takeoff_s: int = 9 * 3600
    turnaround_s: int = 2 * 3600
    sorties_per_day: tuple[int, int] = (1, 2)
    dur_median_s: float = 50 * 60.0
    dur_sigma: float = 0.389  # P5-P95 ~ 25-90 min (report §4)
    download_delay_s: int = 1800
    # Weibull (shape, scale in FH) of time to failure per class; and how a failure shows itself
    weibull: Mapping[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "ENG": (2.0, 600.0),
            "FADEC": (1.0, 900.0),
            "JFS": (1.2, 400.0),
            "AMAGB": (2.0, 900.0),
            "HYDP": (1.5, 700.0),
            "GEN": (1.2, 700.0),
            "DFCC": (1.0, 2000.0),
            "ADC": (1.0, 1200.0),
            "INGPS": (1.0, 900.0),
            "RADAR": (1.0, 250.0),
            "FQGS": (1.0, 1500.0),
            "OBOGS": (1.0, 900.0),
            "BCU": (1.0, 2000.0),
            "BRAKE": (3.0, 5000.0),
            "TYRE": (1.0, 200.0),
            "CHUTE": (1.0, 1500.0),
        }
    )
    symptom: Mapping[str, str] = field(
        default_factory=lambda: {
            "ENG": "both",
            "FADEC": "bit",
            "JFS": "preflight",
            "AMAGB": "latent",
            "HYDP": "both",
            "GEN": "both",
            "DFCC": "bit",
            "ADC": "bit",
            "INGPS": "pilot",
            "RADAR": "pilot",
            "FQGS": "pilot",
            "OBOGS": "pilot",
            "BCU": "bit",
            "BRAKE": "latent",
            "TYRE": "preflight",
            "CHUTE": "preflight",
        }
    )
    bit_code: Mapping[str, str] = field(
        default_factory=lambda: {
            "ENG": "ENG-510",
            "FADEC": "ENG-201",
            "HYDP": "HYD-120",
            "GEN": "ELE-410",
            "DFCC": "FCS-210",
            "ADC": "ADC-010",
            "BCU": "LGB-210",
            "AMAGB": "SPS-520",
            "JFS": "SPS-110",
        }
    )
    p_detect_bit: float = 0.9
    fa_per_fh: float = 0.08
    fa_codes: tuple[str, ...] = ("AVI-520", "FCS-210", "ENG-201", "NAV-310", "ADC-010", "HYD-120")
    p_exceed_per_sortie: float = 0.02
    latent_escalation_fh: float = 30.0
    p_gauging_premod: float = 0.01
    gauging_mod: str = "MOD-FQGS-PICKUP"
    bad_brake_sw: str = "SW-BRK-X"
    p_brake_incident: float = 0.05
    p_induced: float = 0.01
    induced_latency_days: tuple[float, float] = (1.0, 30.0)
    fouling_per_fh: float = 0.002
    wash_rho: float = 0.7


FIX_STATE = StateSchema("fixture.doc", 1, (Field("doc", "|u1", (None,)),))


def _doc_event(
    t: int,
    kind: str,
    target: str | None,
    doc: Mapping[str, Any],
    *,
    priority: int = 0,
    source: str = "fixture",
) -> Event | None:
    if target is None:
        return None
    return Event(int(t), kind, target, plain_payload(doc), priority=priority, source=source)  # AD-48.1


def _local(t: int) -> datetime:
    return datetime.fromtimestamp((EPOCH + t) // NS + 19800, tz=UTC)


class FixtureScenario(ModuleBase):
    """TEST FIXTURE M02: flying programme, launches and landings; honours ASSIGN_SORTIE / RESTRICT_USAGE."""

    version = "1.0.0"
    rate = None
    state_schema = FIX_STATE
    streams = (
        StreamDecl(
            "fx_m02",
            "sortie",
            ("scenario", "tail", "date"),
            Variate.GENERATOR,
            owner="TEST FIXTURE",
            description="sortie count and durations per tail and date",
        ),
    )

    def __init__(
        self,
        id: str,
        tails: tuple[str, ...],
        p: FixtureParams,
        *,
        m18: str,
        health: str,
        sink: str,
        horizon_days: int,
    ) -> None:
        super().__init__(id, ParamSet("fixture.m02", {}))
        self.tails, self.p, self.m18, self.health, self.sink = tails, p, m18, health, sink
        self.horizon_days = horizon_days

    def init(self, params, keys) -> State:
        return {"doc": encode_doc({"day": 0, "active": {}, "assign": {}, "restrict": {}})}

    def initial_outputs(self, state):
        return {}

    def _next_plan(self, t: int) -> int:
        loc = (EPOCH + t) // NS + 19800
        day = loc // DAY_S
        cand = day * DAY_S + self.p.plan_time_s
        if cand <= loc:
            cand += DAY_S
        return (cand - 19800) * NS - EPOCH

    def on_event(self, state, event, t):
        cow = Cow(state)
        doc = cow.doc("doc")
        d = read_payload(event.payload)
        out: list[Event | None] = []
        now = event.t_ns
        if event.kind == "m02.plan":
            day = _local(now)
            if day.weekday() in self.p.flying_weekdays:
                out.append(
                    _doc_event(
                        now,
                        "ops.offer_request",
                        self.m18,
                        {"day": day.strftime("%Y-%m-%d"), "reply_to": self.id},
                    )
                )
                planned = len(self.tails) * sum(self.p.sorties_per_day) / 2.0
                out.append(
                    _doc_event(
                        now,
                        "kpi.plan",
                        self.sink,
                        {
                            "t_utc": EPOCH + now,
                            "date": day.strftime("%Y-%m-%d"),
                            "planned_sorties": planned,
                            "planned_fh": planned * self.p.dur_median_s / 3600.0,
                        },
                    )
                )
            nxt = self._next_plan(now)
            if nxt < self.horizon_days * DAY:
                out.append(_doc_event(nxt, "m02.plan", self.id, {}))
        elif event.kind == "ops.offer":
            date = d["day"]
            loc_midnight = (
                int(datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()) - 19800
            ) * NS - EPOCH
            for tn in d["tails"]:
                g = self.stream("sortie", tail=tn, date=date).generator(0)
                n = int(g.integers(self.p.sorties_per_day[0], self.p.sorties_per_day[1] + 1))
                n = int(doc["assign"].get(f"{tn}|{date}", n))
                t_to = loc_midnight + self.p.first_takeoff_s * NS
                crew = f"P{int(g.integers(24)):02d}"
                for _ in range(n):
                    dur = round(self.p.dur_median_s * math.exp(self.p.dur_sigma * float(g.standard_normal())))
                    sid = f"{tn}-{date.replace('-', '')}-{_local(t_to).strftime('%H%M')}"
                    out.append(
                        _doc_event(
                            t_to,
                            "m02.launch",
                            self.id,
                            {
                                "sortie_id": sid,
                                "tail_no": tn,
                                "t_takeoff": t_to,
                                "dur_s": dur,
                                "date": date,
                                "crew_id": crew,
                            },
                        )
                    )
                    t_to += (dur + self.p.turnaround_s) * NS
        elif event.kind == "m02.launch":
            doc["active"][d["sortie_id"]] = d
            cow.touch("doc")
            out.append(_doc_event(now, "ops.launch", self.m18, {**d, "reply_to": self.id}))
            out.append(_doc_event(now, "fx.launch", self.health, d))
            out.append(_doc_event(now + d["dur_s"] * NS, "m02.land", self.id, d))
        elif event.kind in ("ops.launch_denied", "fx.start_failed"):
            if doc["active"].pop(d["sortie_id"], None) is not None:
                cow.touch("doc")
                out.append(_doc_event(now, "fx.aborted", self.health, d))
                if event.kind == "fx.start_failed":
                    out.append(
                        _doc_event(
                            now,
                            "ops.ground_abort",
                            self.m18,
                            {"tail_no": d["tail_no"], "sortie_id": d["sortie_id"]},
                        )
                    )
        elif event.kind == "m02.land":
            s = doc["active"].pop(d["sortie_id"], None)
            if s is not None:
                cow.touch("doc")
                land = {
                    "sortie_id": s["sortie_id"],
                    "tail_no": s["tail_no"],
                    "t_takeoff": s["t_takeoff"],
                    "t_landing": now,
                    "flight_hours": s["dur_s"] / 3600.0,
                    "landings": 1,
                    "engine_cycles": round(2.5 * s["dur_s"] / 3600.0, 3),
                    "engine_starts": 1,
                    "chute_streamed": 1,
                    "mission_type": "RESTRICTED" if doc["restrict"].get(s["tail_no"]) else "TRAINING",
                    "crew_id": s["crew_id"],
                    "aborted": False,  # catalogued key (AD-44); consumers read it (AD-48.1)
                }
                out.append(_doc_event(now, "ops.sortie_done", self.m18, land))
                out.append(_doc_event(now, "fx.sortie_done", self.health, land))
        elif event.kind == "ops.assign":
            doc["assign"][f"{d['tail_no']}|{d['date']}"] = int(d["sorties"])
            cow.touch("doc")
        elif event.kind == "ops.restrict":
            doc["restrict"][d["tail_no"]] = d["limit"] != "NONE"
            cow.touch("doc")
        else:
            return super().on_event(state, event, t)
        return cow.commit(), [e for e in out if e is not None]


class FixtureHealth(ModuleBase):
    """TEST FIXTURE M10/M11/M14: per-serial failure thresholds, BIT/exceedance/caution events, chains 6-8."""

    version = "1.0.0"
    rate = None
    state_schema = FIX_STATE
    streams = (
        StreamDecl(
            "fx_m10",
            "life",
            ("scenario", "serial"),
            Variate.GENERATOR,
            owner="TEST FIXTURE",
            description="failure threshold per serial life number",
        ),
        StreamDecl(
            "fx_m14",
            "sortie",
            ("scenario", "tail", "sortie"),
            Variate.GENERATOR,
            owner="TEST FIXTURE",
            description="false alarms, exceedances, detection and incidents per sortie",
        ),
        StreamDecl(
            "fx_m10",
            "induced",
            ("scenario", "serial"),
            Variate.GENERATOR,
            owner="TEST FIXTURE",
            description="maintenance-induced defect per serial install",
        ),
    )

    def __init__(
        self,
        id: str,
        p: FixtureParams,
        cat,
        *,
        m18: str,
        m02: str,
        sink: str,
        contract: Contract,
        dict_version: str,
        dict_hash: str,
    ) -> None:
        super().__init__(id, ParamSet("fixture.m10", {}))
        self.p, self.cat, self.m18, self.m02, self.sink, self.contract = p, cat, m18, m02, sink, contract
        self.dv, self.dh = dict_version, dict_hash

    def init(self, params, keys) -> State:
        return {
            "doc": encode_doc(
                {"inst": {}, "ser": {}, "faults": {}, "nf": 0, "sw": {}, "mods": {}, "foul": {}, "flying": {}}
            )
        }

    def initial_outputs(self, state):
        return {}

    # BeliefTarget protocol (phalanx.fork.belief): identities and priors only; draws come from the posterior
    def belief_items(self, state) -> list[str]:
        doc = json.loads(np.asarray(state["doc"]).tobytes().decode("ascii"))
        return sorted(set(doc["inst"].values()))

    def belief_prior(self, state, serial: str):
        doc = json.loads(np.asarray(state["doc"]).tobytes().decode("ascii"))
        k, lam = self.p.weibull[doc["ser"][serial]["cls"]]
        return "weibull", {"shape": k, "scale_h": lam}

    def with_belief(self, state, draws, keep_faults):
        cow = Cow(state)
        doc = cow.doc("doc")
        for sn, d in sorted(draws.items()):
            s = doc["ser"][sn]
            s["u"], s["th"] = float(d["u_s"]), float(d["th_s"])
        for _sn, s in sorted(doc["ser"].items()):
            if s["fault"] is not None and s["fault"] not in keep_faults:
                doc["faults"].pop(s["fault"], None)
                s["fault"] = None
        cow.touch("doc")
        return cow.commit()

    def _threshold(self, sn: str, cls: str, life: int) -> float:
        k, lam = self.p.weibull[cls]
        u = float(self.stream("life", serial=sn).generator(life).random())
        return lam * (-math.log(1.0 - u)) ** (1.0 / k) * 3600.0

    def _serial(self, doc: dict, sn: str, cls: str, *, initial: bool) -> dict:
        s = doc["ser"].get(sn)
        if s is None:
            th = self._threshold(sn, cls, 0)
            age = 0.0
            if initial:  # steady-state fleet: an installed item is part-way through its life
                age = float(self.stream("life", serial=sn).generator(10_000).random()) * th
            s = {"cls": cls, "life": 0, "u": age, "th": th, "fault": None, "n_inst": 0}
            doc["ser"][sn] = s
        return s

    def _event_row(
        self,
        topic: str,
        tn: str,
        sortie: str,
        code: str,
        occ: int,
        t_occ: int,
        t_ing: int,
        extra: Mapping[str, Any],
    ) -> dict[str, Any]:
        row = dict.fromkeys(self.contract.topics[topic].field_names)
        src = "ECMS" if code[:3] in ("ENG", "SPS") else "HUMS_DAU"
        row.update(
            dict_version=self.dv,
            dict_hash=self.dh,
            event_id=f"{sortie}:{code}:{occ}",
            tail_no=tn,
            sortie_id=sortie,
            source_lru=src,
            event_code=code,
            event_group=code[:3],
            severity="CAUTION",
            description=f"SYNTHETIC {code}",
            confirmed_status="UNCONFIRMED",
            detection_mechanism="CBIT" if topic == "events.bit_faults" else "EXCEEDANCE",
            detection_far_per_fh=0.05,
            fault_list="MFL",
            latched=True,
            persistence_count=4,
            suspect_lrus=[],
            t_occurrence=EPOCH + t_occ,
            t_utc=EPOCH + t_occ,
            t_ingest=EPOCH + t_ing,
            quality_flags=0,
            provenance="direct",
        )
        row.update(extra)
        row["record_id"] = record_id(
            self.contract,
            topic,
            {
                "provenance": "direct",
                "tail_no": tn,
                "sortie_id": sortie,
                "channel_id": f"direct:{src}",
                "event_code": code,
                "seq": occ,
                "msg_index": 0,
            },
        ).hex()
        return row

    def _emit_obs(self, out, topic, row, t_ing) -> None:
        out.append(_doc_event(t_ing, f"rec.{topic}", self.sink, {"row": row}))
        out.append(_doc_event(t_ing, "obs.event", self.m18, {"topic": topic, "row": row}))

    def _fault(self, out, doc, now, tn, pos, sn, cls, *, symptom=None, mode="wear") -> None:
        doc["nf"] = int(doc["nf"]) + 1
        fid = f"F{doc['nf']:06d}-{sn}"
        sym = symptom or self.p.symptom[cls]
        doc["faults"][fid] = {
            "tail": tn,
            "pos": pos,
            "serial": sn,
            "cls": cls,
            "sym": sym,
            "t": now,
            "u_esc": None,
        }
        doc["ser"][sn]["fault"] = fid
        out.append(
            _doc_event(
                now,
                "truth.fault",
                self.m18,
                {
                    "fault_id": fid,
                    "tail": tn,
                    "pos": pos,
                    "serial": sn,
                    "mode": mode,
                    "symptom": "pilot" if sym == "both" else sym,
                    "grounding": self.cat.cls(cls).grounding,
                },
            )
        )

    def on_event(self, state, event, t):
        cow = Cow(state)
        doc = cow.doc("doc")
        d = read_payload(event.payload)
        out: list[Event | None] = []
        now = event.t_ns
        k = event.kind
        if k == "cfg.install":
            s = self._serial(doc, d["serial"], d["cls"], initial=now == 0)
            doc["inst"][f"{d['tail']}|{d['pos']}"] = d["serial"]
            s["n_inst"] = int(s["n_inst"]) + 1
            if (
                now > 0
                and float(self.stream("induced", serial=d["serial"]).generator(int(s["n_inst"])).random())
                < self.p.p_induced
            ):
                lat = (
                    self.p.induced_latency_days[0]
                    + (self.p.induced_latency_days[1] - self.p.induced_latency_days[0]) * 0.5
                )
                out.append(
                    _doc_event(
                        now + int(lat * DAY),
                        "fx.induced",
                        self.id,
                        {"tail": d["tail"], "pos": d["pos"], "serial": d["serial"]},
                    )
                )
        elif k == "cfg.remove":
            doc["inst"].pop(f"{d['tail']}|{d['pos']}", None)
        elif k == "fx.induced":
            if (
                doc["inst"].get(f"{d['tail']}|{d['pos']}") == d["serial"]
                and doc["ser"][d["serial"]]["fault"] is None
            ):
                self._fault(
                    out,
                    doc,
                    now,
                    d["tail"],
                    d["pos"],
                    d["serial"],
                    doc["ser"][d["serial"]]["cls"],
                    symptom="pilot",
                    mode="induced",
                )
        elif k == "mx.repaired":
            s = doc["ser"].get(d["serial"])
            if s is not None:
                s["life"] = int(s["life"]) + 1
                s["u"], s["fault"] = 0.0, None
                s["th"] = self._threshold(d["serial"], s["cls"], int(s["life"]))
        elif k == "mx.action":
            if d.get("action") == "ENGINE_WASH":
                doc["foul"][d["tail"]] = float(doc["foul"].get(d["tail"], 0.0)) * (1.0 - self.p.wash_rho)
            elif d.get("action") == "SWLOAD":
                doc["sw"][d["tail"]] = d["sw_config_id"]
            elif d.get("action") == "MOD":
                doc["mods"][d["tail"]] = sorted({*doc["mods"].get(d["tail"], []), d["mod_id"]})
        elif k == "fx.launch":
            tn = d["tail_no"]
            doc["flying"][tn] = d["sortie_id"]
            jfs = doc["inst"].get(f"{tn}|JFS")
            if (
                jfs is not None and doc["ser"][jfs]["fault"] is not None
            ):  # chain 6: start failure on a bad JFS
                out.append(_doc_event(now, "fx.start_failed", self.m02, d))
                inc = {"tail": tn, "kind": "start_failure", "positions": ["JFS"]}  # all catalogued keys
                out.append(_doc_event(now, "truth.incident", self.m18, inc))
            else:
                for key, sn in sorted(doc["inst"].items()):
                    tail, pos = key.split("|")
                    if tail != tn:
                        continue
                    s = doc["ser"][sn]
                    if s["fault"] is None and float(s["u"]) + d["dur_s"] >= float(s["th"]):
                        dt = max(1, int(float(s["th"]) - float(s["u"])))
                        out.append(
                            _doc_event(
                                now + dt * NS,
                                "fx.onset",
                                self.id,
                                {"tail": tn, "pos": pos, "serial": sn, "sortie_id": d["sortie_id"]},
                            )
                        )
        elif k == "fx.onset":
            s = doc["ser"].get(d["serial"])
            if (
                s is not None
                and s["fault"] is None
                and doc["flying"].get(d["tail"]) == d["sortie_id"]
                and doc["inst"].get(f"{d['tail']}|{d['pos']}") == d["serial"]
            ):
                self._fault(out, doc, now, d["tail"], d["pos"], d["serial"], s["cls"])
        elif k == "fx.sortie_done":
            doc["flying"].pop(d["tail_no"], None)
            self._after_sortie(out, doc, d, now)
        elif k == "fx.aborted":
            if doc["flying"].get(d["tail_no"]) == d["sortie_id"]:
                doc["flying"].pop(d["tail_no"])
        else:
            return super().on_event(state, event, t)
        cow.touch("doc")
        return cow.commit(), [e for e in out if e is not None]

    def _after_sortie(self, out, doc, d, now) -> None:
        tn, sid = d["tail_no"], d["sortie_id"]
        fh_s = float(d["flight_hours"]) * 3600.0
        g = self.stream("sortie", tail=tn, sortie=sid).generator(0)
        t_ing = now + self.p.download_delay_s * NS
        occ = 0
        for key, sn in sorted(doc["inst"].items()):
            tail, pos = key.split("|")
            if tail != tn:
                continue
            s = doc["ser"][sn]
            s["u"] = float(s["u"]) + fh_s
            fid = s["fault"]
            if fid is None:
                continue
            f = doc["faults"][fid]
            cls = s["cls"]
            if (
                f["sym"] in ("bit", "both")
                and cls in self.p.bit_code
                and float(g.random()) < self.p.p_detect_bit
            ):
                lru = self.cat.cls(cls).lru
                row = self._event_row(
                    "events.bit_faults",
                    tn,
                    sid,
                    self.p.bit_code[cls],
                    occ,
                    now,
                    t_ing,
                    {"suspect_lrus": [{"lru": lru, "isolation_confidence": 0.7}] if lru else []},
                )
                occ += 1
                self._emit_obs(out, "events.bit_faults", row, t_ing)
            if f["sym"] == "latent":  # undetected latent faults escalate to an in-flight symptom
                f["u_esc"] = float(f["u_esc"] or 0.0) + fh_s
                if f["u_esc"] >= self.p.latent_escalation_fh * 3600.0:
                    f["sym"] = "pilot"
                    out.append(_doc_event(now, "truth.fault_clear", self.m18, {"fault_id": fid}))
                    s["fault"] = None
                    self._fault(out, doc, now, tn, pos, sn, cls, symptom="pilot", mode="escalated")
        n_fa = int(g.poisson(self.p.fa_per_fh * fh_s / 3600.0))
        for i in range(n_fa):
            code = self.p.fa_codes[int(g.integers(len(self.p.fa_codes)))]
            row = self._event_row("events.bit_faults", tn, sid, code, occ + i, now, t_ing, {})
            self._emit_obs(out, "events.bit_faults", row, t_ing)
        foul = float(doc["foul"].get(tn, 0.0)) + self.p.fouling_per_fh * fh_s / 3600.0
        doc["foul"][tn] = foul
        if float(g.random()) < self.p.p_exceed_per_sortie * (1.0 + 10.0 * foul) * (
            0.5 if d.get("mission_type") == "RESTRICTED" else 1.0
        ):
            row = self._event_row(
                "events.exceedances",
                tn,
                sid,
                "ECM-710",
                0,
                now,
                t_ing,
                {
                    "detection_mechanism": "EXCEEDANCE",
                    "param_id": "ENG.T5",
                    "limit_id": "LIM.ENG.T5.SYN",
                    "limit_value": 830.0,
                    "peak_value": 845.0,
                    "units": "degC",
                    "t_end": EPOCH + now,
                },
            )
            self._emit_obs(out, "events.exceedances", row, t_ing)
        if self.p.gauging_mod not in doc["mods"].get(tn, []) and float(g.random()) < self.p.p_gauging_premod:
            row = self._event_row(
                "events.cautions",
                tn,
                sid,
                "FUE-010",
                0,
                now,
                t_ing,
                {
                    "detection_mechanism": "CBIT",
                    "legend": "CWS-L07",
                    "displayed": True,
                    "voice_warning": False,
                    "t_cleared": EPOCH + now,
                    "fault_list": "PFL",
                },
            )  # chain 8: false low-fuel caution
            self._emit_obs(out, "events.cautions", row, t_ing)
        if doc["sw"].get(tn) == self.p.bad_brake_sw and float(g.random()) < self.p.p_brake_incident:
            out.append(
                _doc_event(
                    now,
                    "truth.incident",
                    self.m18,
                    {"tail": tn, "kind": "excursion", "positions": ["TYR_L", "TYR_R", "BRK_L", "BRK_R"]},
                )
            )


@dataclass
class FixtureFleetBuilder:
    """WorldBuilder for the fixture fleet (fixture M02 + M10/M11/M14 + real M18/M21/sink)."""

    n_tails: int = 4
    horizon_days: int = 60
    scenario: str = "fx"
    p: FixtureParams = field(default_factory=FixtureParams)
    m18_cfg: M18Config | None = None
    internal: InternalPolicy = field(default_factory=InternalPolicy)
    epoch_utc_ns: int = EPOCH
    ids: OpsIds = field(default_factory=OpsIds)

    def __post_init__(self) -> None:
        self.m18_cfg = self.m18_cfg or load_m18_config()
        self.tails = tuple(f"KH{2001 + i}" for i in range(self.n_tails))
        self.fleet = FleetSpec(self.tails, ("SUL",), tuple(0 for _ in self.tails))
        targets = OpsTargets(
            m21=self.ids.m21, sink=self.ids.sink, scenario="m02", health="m10", monitoring=None
        )
        contract = contract_v0()
        self._ops = OpsOnlyBuilder(
            self.fleet,
            self.epoch_utc_ns,
            scenario=self.scenario,
            m18_cfg=self.m18_cfg,
            internal=self.internal,
            targets=targets,
            ids=self.ids,
            extra=(
                lambda: FixtureScenario(
                    "m02",
                    self.tails,
                    self.p,
                    m18=self.ids.m18,
                    health="m10",
                    sink=self.ids.sink,
                    horizon_days=self.horizon_days,
                ),
                lambda: FixtureHealth(
                    "m10",
                    self.p,
                    self.m18_cfg.catalogue,
                    m18=self.ids.m18,
                    m02="m02",
                    sink=self.ids.sink,
                    contract=contract,
                    dict_version=self._ops.dict_version,
                    dict_hash=self._ops.dict_hash,
                ),
            ),
        )
        self.calendar = self._ops.calendar
        self.dict_version, self.dict_hash = self._ops.dict_version, self._ops.dict_hash

    def build(self, root: int, *, ledger: DrawLedger | None = None) -> System:
        return self._ops.build(root, ledger=ledger)

    def initial_events(self) -> list[Event]:
        first_plan = FixtureScenario(
            "tmp", self.tails, self.p, m18="m18", health="m10", sink="sink", horizon_days=self.horizon_days
        )._next_plan(0)
        return [
            *self._ops.initial_events(),
            Event(first_plan, "m02.plan", "m02", {}, source="session"),  # AD-48.1: no doc wrapper
        ]


# ------------------------------------------------------------------------------------------------ fixture
# self-tests


@pytest.mark.fork
def test_fixture_fleet_runs_and_emits_every_record_family():
    """Smoke (n = 1 run, 4 tails x 30 days): the fixture drives sorties, faults, BIT events and
    maintenance."""
    from phalanx.fork.session import OpsSession

    b = FixtureFleetBuilder(n_tails=4, horizon_days=30)
    s = OpsSession(b, 0xA11CE)
    s.run_until(30 * DAY)
    types = {r["record_type"] for r in s.records("maint.records")}
    assert {"SORTIE", "DEFECT_WO", "COMPONENT_LIFE", "AVAILABILITY_STATE", "TECH_LOG", "INSPECTION"} <= types
    assert s.records("events.bit_faults"), "the fixture M14 should have emitted BIT events"
    assert s.records("kpi.plan")
