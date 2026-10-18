"""M18: the discrete-event maintenance, logistics and records world (architecture §6 M18, §10; AD-19, AD-20).

An event-only core module (``rate = None``; usage mode runs it with the kernel's event jump). It owns the
maintenance organisation's state for a fleet at one or more bases:

- configuration: which serial is installed in which position of which tail, with recorded life (hours, cycles,
  landings, streamings, calendar);
- work orders ("snags") from pilot write-ups, BIT/HMS codes, inspections, exceedances, incidents and orders,
  with troubleshooting that can misdiagnose (NFF/RTOK), defer-and-monitor for BIT-only codes, and repair by
  R/R;
- supply: base stock with an authorised level, AOG/MCM/PHU requisitions with CAG-calibrated lead times,
  base-shop and depot repair loops, cannibalisation, stock transfers;
- scheduled servicing (first/second line, depot R&O) with overrunning durations and inspection detection
  probabilities; hard-time retirement; modifications and software loads;
- manpower (teams within shift windows) and hangar slots;
- availability computed from job states, SCIR-style in 15-minute bins (never asserted).

Every state change produces the §10 records (``maint.records`` rows, emitted as ``rec.maint.records`` events
to the record sink); executed orders report their lifecycle to M21. Hidden truth (actual faults) is used only
to decide *outcomes* (does the ground check reproduce, is the removed unit really bad); decisions use tech-log
knowledge only.

Event protocol (W2.6 wiring; payloads are plain top-level keys, AD-48.1): see README "Event protocol".
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from phalanx.core.canonical import canonical_json
from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, Param, ParamSet
from phalanx.core.rng import StreamDecl, Variate
from phalanx.core.state import Field, State, StateSchema
from phalanx.health.protocol import plain_payload, read_payload
from phalanx.orders.epochs import PRIO_REVIEW, DecisionCalendar
from phalanx.orders.rules import TechLogFacts, airworthiness

from . import scir
from .config import M18Config
from .docstate import Cow, encode_doc
from .records import MAINT, contract_v0, maint_row
from .rules import AwpJob, FleetView, TailView, cann_plan
from .timebase import DAY_S, NS, WorkCalendar, bin_start, check_whole_second, to_s

#: the engine item class (catalogue code): installed serials come from the scenario when configured (W2.1c)
ENGINE_CLASS = "ENG"

# serial locations
LOC_INSTALLED, LOC_STOCK, LOC_SHOP, LOC_DEPOT, LOC_TRANSIT, LOC_GONE = 0, 1, 2, 3, 4, 5
# occurrence slots of the per-tail execution stream
SLOT_TS, SLOT_RR, SLOT_CHECK, SLOT_INSP, SLOT_SRV, SLOT_OUT, SLOT_WORK, SLOT_CANN = 1, 2, 3, 4, 5, 6, 7, 8
OPEN, IN_WORK, AWP, AWM, DEFERRED, CLOSED = (
    "OPEN",
    "IN_WORK",
    "AWAITING_PARTS",
    "AWAITING_MAINTENANCE",
    "DEFERRED",
    "CLOSED",
)
SRV_INSPECTION_TYPES = ("SRV-L1", "SRV-L2-MINOR", "SRV-L2-MAJOR", "ROH")
ROH = 3

STATE_SCHEMA = StateSchema(
    "maint.world",
    1,
    (
        Field("t_last", "<i8"),
        Field("ser_no", "<U48", (None,)),
        Field("ser_cls", "<i4", (None,)),
        Field("ser_loc", "<i1", (None,)),
        Field("ser_tail", "<i4", (None,)),
        Field("ser_pos", "<i4", (None,)),
        Field("ser_base", "<i4", (None,)),
        Field("ser_t_ready", "<i8", (None,)),
        Field("ser_tsn", "<i8", (None,)),
        Field("ser_tso", "<i8", (None,)),
        Field("ser_csn", "<f8", (None,)),
        Field("ser_ldg", "<i8", (None,)),
        Field("ser_strm", "<i8", (None,)),
        Field("ser_t_life0", "<i8", (None,)),
        Field("ser_faults", "<i4", (None,)),
        Field("ser_visits", "<i4", (None,)),
        Field("ser_rtok", "<i4", (None,)),
        Field("ser_moves", "<i4", (None,)),
        Field("ser_alloc", "<U40", (None,)),
        Field("ser_depot", "<i1", (None,)),
        Field("tail_inst", "<i4", (None, None)),
        Field("tail_flying", "<i1", (None,)),
        Field("tail_hold", "<i1", (None,)),
        Field("tail_depot", "<i1", (None,)),
        Field("tail_fh", "<i8", (None,)),
        Field("tail_ldg", "<i8", (None,)),
        Field("tail_sorties", "<i8", (None,)),
        Field("srv_fh", "<i8", (None, None)),
        Field("srv_last", "<i8", (None, None)),
        Field("srv_ext_fh", "<i8", (None, None)),
        Field("srv_ext_s", "<i8", (None, None)),
        Field("av_cur", "<i1", (None,)),
        Field("av_bin", "<i8", (None,)),
        Field("av_worst", "<i1", (None,)),
        Field("av_emit", "<i1", (None,)),
        Field("av_ver", "<i4", (None,)),
        Field("av_tick", "<i8", (None,)),
        Field("av_nmc_since", "<i8", (None,)),
        Field("tl_ver", "<i4", (None,)),
        Field("doc_jobs", "|u1", (None,)),
        Field("doc_supply", "|u1", (None,)),
        Field("doc_faults", "|u1", (None,)),
        Field("doc_tails", "|u1", (None,)),
        Field("doc_res", "|u1", (None,)),
        Field("doc_occ", "|u1", (None,)),
        Field("doc_meta", "|u1", (None,)),
    ),
)


@dataclass(frozen=True)
class FleetSpec:
    """The fleet M18 maintains: tails, bases, the base of each tail, the initial software configuration."""

    tails: tuple[str, ...]
    bases: tuple[str, ...]
    tail_base: tuple[int, ...]
    sw_config_id: str = "SW-BASE"
    #: the installed engine serial of each tail - the scenario's (M02) engine identity, the single source of
    #: truth that M10 / M11 / M14 are configured with (W2.1c); empty = M18 mints them (W1 ``ENG-nnnnnn``)
    engine_serials: tuple[str, ...] = ()
    #: prefix of the engine serials M18 mints (spares, new procurement): the scenario's ``<prefix>-<token>``
    #: format; empty = the class code (W1)
    engine_serial_prefix: str = ""

    def __post_init__(self) -> None:
        if len(self.tails) != len(self.tail_base) or not self.tails:
            raise ValueError("one base index per tail")
        if len(set(self.tails)) != len(self.tails) or len(set(self.bases)) != len(self.bases):
            raise ValueError("tail and base names must be unique")
        if any(not 0 <= b < len(self.bases) for b in self.tail_base):
            raise ValueError("tail_base out of range")
        es, pre = self.engine_serials, self.engine_serial_prefix
        if es and (len(es) != len(self.tails) or len(set(es)) != len(es)):
            raise ValueError("engine_serials: one unique installed engine serial per tail")
        if es and not pre:
            raise ValueError("engine_serials need engine_serial_prefix (one serial format for every engine)")
        if pre and any(not s.startswith(f"{pre}-") or s == f"{pre}-" for s in es):
            raise ValueError(f"engine serials must read {pre}-<token> (one format)")

    def describe(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "tails": list(self.tails),
            "bases": list(self.bases),
            "tail_base": list(self.tail_base),
            "sw": self.sw_config_id,
        }
        if self.engine_serials:  # W2.1c (absent = the W1 description, unchanged config hash)
            d["engine_serials"] = list(self.engine_serials)
        if self.engine_serial_prefix:
            d["engine_serial_prefix"] = self.engine_serial_prefix
        return d

    @classmethod
    def from_scenario(
        cls, scenario, *, bases: Mapping[str, str] | None = None, sw_config_id: str = "SW-BASE"
    ) -> FleetSpec:
        """The fleet of an M02 ``FleetScenario``: its tails, the bases of their squadrons (``bases`` renames
        a scenario base, e.g. ``{"sulur": "SUL"}``) and its installed engine serials - the scenario is the
        single source of engine identity; M18 mints more engines in the same ``<prefix>-<token>`` format."""
        names: list[str] = []
        tail_base: list[int] = []
        tails: list[str] = []
        serials: list[str] = []
        for sq in scenario.squadrons:
            name = (bases or {}).get(sq.base.name, sq.base.name)
            if name not in names:
                names.append(name)
            tails += list(sq.tails)
            tail_base += [names.index(name)] * len(sq.tails)
            serials += list(sq.engine_serials)
        prefixes = sorted({s.split("-", 1)[0] for s in serials})
        if len(prefixes) != 1:
            raise ValueError(f"one fleet, one engine serial format <prefix>-<token>: prefixes {prefixes}")
        return cls(tuple(tails), tuple(names), tuple(tail_base), sw_config_id, tuple(serials), prefixes[0])


@dataclass(frozen=True)
class OpsTargets:
    """Module ids of the neighbours M18 exchanges events with (None = absent)."""

    m21: str | None = "m21"
    sink: str = "sink"
    scenario: str | None = None
    health: str | None = None
    monitoring: str | None = None


@dataclass(frozen=True)
class InternalPolicy:
    """Status-quo decisions M18 takes itself (open loop). Set ``cann=False`` when a policy issues CANN
    orders."""

    cann: bool = True


@dataclass
class _Ctx:
    m: MaintenanceWorld
    cow: Cow
    t: int
    out: list[Event] = field(default_factory=list)

    @property
    def jobs(self) -> dict[str, Any]:
        return self.cow.doc("doc_jobs")


def _pl(event: Event) -> dict[str, Any]:
    """An inbound event as plain values (AD-48.1, :func:`phalanx.health.protocol.read_payload`)."""
    return read_payload(event.payload)


class MaintenanceWorld(ModuleBase):
    version = "1.0.0"
    rate = None
    ports_in = ()
    ports_out = ()
    state_schema = STATE_SCHEMA
    streams = (
        StreamDecl(
            "m18",
            "tail_exec",
            ("scenario", "tail"),
            Variate.GENERATOR,
            owner="M18",
            description="maintenance execution draws per tail, indexed by (local day, slot, occurrence)",
        ),
        StreamDecl(
            "m18",
            "serial_shop",
            ("scenario", "serial"),
            Variate.GENERATOR,
            owner="M18",
            description="bench/shop/depot outcome per serial, indexed by shop visit number",
        ),
        StreamDecl(
            "m18",
            "supply",
            ("scenario", "base"),
            Variate.GENERATOR,
            owner="M18",
            description="wholesale lead time per base, indexed by (local day, class, occurrence)",
        ),
        StreamDecl(
            "m18",
            "init_serial",
            ("scenario", "serial"),
            Variate.GENERATOR,
            owner="M18",
            description="initial recorded life of a serial",
        ),
        StreamDecl(
            "m18",
            "init_tail",
            ("scenario", "tail"),
            Variate.GENERATOR,
            owner="M18",
            description="initial servicing phase of a tail",
        ),
    )

    def __init__(
        self,
        id: str,
        cfg: M18Config,
        fleet: FleetSpec,
        *,
        epoch_utc_ns: int,
        calendar: DecisionCalendar,
        dict_version: str,
        dict_hash: str,
        targets: OpsTargets | None = None,
        internal: InternalPolicy | None = None,
    ) -> None:
        targets = targets or OpsTargets()
        internal = internal or InternalPolicy()
        cfg_note = "M18 configuration (content hash / canonical JSON; synthetic catalogue AD-19)"
        extra = {
            "cfg_catalogue_hash": Param(
                cfg.catalogue.hash, "1", "ASSUMPTION", "configs/tejas/params/M18/catalogue.yaml"
            ),
            "cfg_codes_hash": Param(cfg.codes.hash, "1", "ASSUMPTION", "configs/tejas/params/M18/codes.yaml"),
            "cfg_fleet": Param(canonical_json(fleet.describe()).decode(), "1", "ASSUMPTION", cfg_note),
            "cfg_epoch_utc": Param(
                int(epoch_utc_ns), "ns", "ASSUMPTION", "run epoch (M02 scenario.epoch_utc_ns)"
            ),
            "cfg_calendar": Param(
                canonical_json(list(calendar.times_of_day_s)).decode(),
                "1",
                "ASSUMPTION",
                "M21 decision calendar",
            ),
            "cfg_targets": Param(
                canonical_json(
                    {k: getattr(targets, k) for k in ("m21", "sink", "scenario", "health", "monitoring")}
                ).decode(),
                "1",
                "ASSUMPTION",
                cfg_note,
            ),
            "cfg_internal": Param(
                canonical_json({"cann": internal.cann}).decode(), "1", "ASSUMPTION", cfg_note
            ),
            "cfg_dict": Param(
                f"{dict_version}:{dict_hash}", "1", "DIRECT", "M01 dictionary version and hash"
            ),
            "cfg_overrides": Param(
                canonical_json({k: cfg.overrides[k] for k in sorted(cfg.overrides)}).decode(),
                "1",
                "ASSUMPTION",
                "run-time overrides of M18.yaml values (sweeps, tests); empty in a default run",
            ),
        }
        params = ParamSet(cfg.params.name, {**dict(cfg.params), **extra})
        super().__init__(id, params)
        check_whole_second(epoch_utc_ns, "run epoch")
        self.cfg = cfg
        self.fleet = fleet
        self.cat = cfg.catalogue
        self.codes = cfg.codes
        self.epoch = int(epoch_utc_ns)
        self.calendar = calendar
        self.work = WorkCalendar(self.epoch, cfg.tz_offset_s, cfg.shift_start_s, cfg.shift_end_s)
        self.targets = targets
        self.internal = internal
        self.dict_version = dict_version
        self.dict_hash = dict_hash
        self.contract = contract_v0()
        self.tidx = {t: i for i, t in enumerate(fleet.tails)}
        self.bidx = {b: i for i, b in enumerate(fleet.bases)}
        self.n_pos = len(self.cat.positions)
        n_eng = sum(1 for p in self.cat.positions if p.cls.code == ENGINE_CLASS)
        if fleet.engine_serials and n_eng != 1:
            raise ValueError(f"engine_serials name one engine per tail; the catalogue has {n_eng} positions")
        self.pos_cls = np.array([p.cls.index for p in self.cat.positions], dtype=np.int32)
        self.cls_by_pn = {c.part_no: c for c in self.cat.classes}
        self.bin_ns = cfg.bin_width_s * NS
        self._handlers = {
            "m18.start": self._h_start,
            "ops.offer_request": self._h_offer_request,
            "ops.launch": self._h_launch,
            "ops.ground_abort": self._h_ground_abort,
            "ops.sortie_done": self._h_sortie_done,
            "m18.sortie_entry": self._h_sortie_entry,
            "m18.writeup": self._h_writeup,
            "obs.event": self._h_obs_event,
            "m18.obsjob": self._h_obsjob,
            "truth.fault": self._h_truth_fault,
            "truth.fault_clear": self._h_truth_fault_clear,
            "truth.incident": self._h_truth_incident,
            "order.exec": self._h_order_exec,
            "m18.review": self._h_review,
            "m18.job": self._h_job,
            "m18.avtick": self._h_avtick,
            "m18.supply": self._h_supply,
            "m18.shop": self._h_shop,
            "m18.transit": self._h_transit,
            "m18.defer_expiry": self._h_defer_expiry,
            "m18.disruption": self._h_disruption,
        }

    # ================================================================================================ init
    def init(self, params: ParamSet, keys) -> State:
        cat, cfg, fleet = self.cat, self.cfg, self.fleet
        nt, npos = len(fleet.tails), self.n_pos
        rows: dict[str, list] = {
            k: [] for k in ("no", "cls", "loc", "tail", "pos", "base", "tsn", "csn", "ldg", "strm", "life0")
        }
        seq: dict[str, int] = {c.code: 0 for c in cat.classes}
        used = set(fleet.engine_serials)

        def new_serial(cls_code: str) -> str:
            while True:  # the scenario's engine serials are taken (W2.1c)
                seq[cls_code] += 1
                sn = f"{self._serial_head(cls_code)}-{seq[cls_code]:06d}"
                if sn not in used:
                    used.add(sn)
                    return sn

        inst = np.full((nt, npos), -1, dtype=np.int32)
        for ti in range(nt):
            for p in cat.positions:
                if p.cls.code == ENGINE_CLASS and fleet.engine_serials:
                    sn = fleet.engine_serials[ti]  # the scenario's installed engine (W2.1c)
                else:
                    sn = new_serial(p.cls.code)
                tsn, csn, ldg, strm, life0 = self._initial_life(sn, p.cls.code)
                inst[ti, p.index] = len(rows["no"])
                for k, v in (
                    ("no", sn),
                    ("cls", p.cls.index),
                    ("loc", LOC_INSTALLED),
                    ("tail", ti),
                    ("pos", p.index),
                    ("base", fleet.tail_base[ti]),
                    ("tsn", tsn),
                    ("csn", csn),
                    ("ldg", ldg),
                    ("strm", strm),
                    ("life0", life0),
                ):
                    rows[k].append(v)
        for bi in range(len(fleet.bases)):
            n_at_base = sum(1 for b in fleet.tail_base if b == bi)
            for c in cat.classes:
                n_spare = math.ceil(c.v("stock_per_ac") * n_at_base - 1e-9)
                for _ in range(n_spare):
                    sn = new_serial(c.code)
                    tsn, csn, ldg, strm, life0 = self._initial_life(sn, c.code)
                    for k, v in (
                        ("no", sn),
                        ("cls", c.index),
                        ("loc", LOC_STOCK),
                        ("tail", -1),
                        ("pos", -1),
                        ("base", bi),
                        ("tsn", tsn),
                        ("csn", csn),
                        ("ldg", ldg),
                        ("strm", strm),
                        ("life0", life0),
                    ):
                        rows[k].append(v)
        n = len(rows["no"])
        k = cfg.n_servicing
        srv_fh = np.zeros((nt, k), dtype=np.int64)
        srv_last = np.zeros((nt, k), dtype=np.int64)
        for ti, tn in enumerate(fleet.tails):
            g = self.stream("init_tail", tail=tn).generator(0)
            u = g.random(k)
            for kk in range(k):  # fleet in steady state: uniform phase within each interval
                srv_fh[ti, kk] = int(u[kk] * cfg.srv_interval_fh_s[kk])
                srv_last[ti, kk] = -int(u[kk] * cfg.srv_interval_s[kk]) * NS
        tails_doc = {
            tn: {"sw": fleet.sw_config_id, "mods": [], "limits": [], "filters": [], "restrict": {}}
            for tn in fleet.tails
        }
        meta = {"ser_seq": seq, "job_seq": {}, "dem_seq": {}, "started": False, "review_next": -1}
        return {
            "t_last": np.array(0, dtype=np.int64),
            "ser_no": np.array(rows["no"], dtype="<U48"),
            "ser_cls": np.array(rows["cls"], dtype=np.int32),
            "ser_loc": np.array(rows["loc"], dtype=np.int8),
            "ser_tail": np.array(rows["tail"], dtype=np.int32),
            "ser_pos": np.array(rows["pos"], dtype=np.int32),
            "ser_base": np.array(rows["base"], dtype=np.int32),
            "ser_t_ready": np.full(n, -1, dtype=np.int64),
            "ser_tsn": np.array(rows["tsn"], dtype=np.int64),
            "ser_tso": np.array(rows["tsn"], dtype=np.int64),
            "ser_csn": np.array(rows["csn"], dtype=np.float64),
            "ser_ldg": np.array(rows["ldg"], dtype=np.int64),
            "ser_strm": np.array(rows["strm"], dtype=np.int64),
            "ser_t_life0": np.array(rows["life0"], dtype=np.int64),
            "ser_faults": np.zeros(n, dtype=np.int32),
            "ser_visits": np.zeros(n, dtype=np.int32),
            "ser_rtok": np.zeros(n, dtype=np.int32),
            "ser_moves": np.zeros(n, dtype=np.int32),
            "ser_alloc": np.full(n, "", dtype="<U40"),
            "ser_depot": np.zeros(n, dtype=np.int8),
            "tail_inst": inst,
            "tail_flying": np.zeros(nt, dtype=np.int8),
            "tail_hold": np.zeros(nt, dtype=np.int8),
            "tail_depot": np.zeros(nt, dtype=np.int8),
            "tail_fh": np.zeros(nt, dtype=np.int64),
            "tail_ldg": np.zeros(nt, dtype=np.int64),
            "tail_sorties": np.zeros(nt, dtype=np.int64),
            "srv_fh": srv_fh,
            "srv_last": srv_last,
            "srv_ext_fh": np.zeros((nt, k), dtype=np.int64),
            "srv_ext_s": np.zeros((nt, k), dtype=np.int64),
            "av_cur": np.zeros(nt, dtype=np.int8),
            "av_bin": np.full(nt, -1, dtype=np.int64),
            "av_worst": np.zeros(nt, dtype=np.int8),
            "av_emit": np.full(nt, -1, dtype=np.int8),
            "av_ver": np.full(nt, -1, dtype=np.int32),
            "av_tick": np.full(nt, -1, dtype=np.int64),
            "av_nmc_since": np.full(nt, -1, dtype=np.int64),
            "tl_ver": np.full(nt, -1, dtype=np.int32),
            "doc_jobs": encode_doc({"open": {}, "awm": []}),
            "doc_supply": encode_doc({"demands": {}, "disruptions": []}),
            "doc_faults": encode_doc({}),
            "doc_tails": encode_doc(tails_doc),
            "doc_res": encode_doc(
                {
                    "busy": {b: [] for b in fleet.bases},
                    "slots": {b: [] for b in fleet.bases},
                    "slotq": {b: [] for b in fleet.bases},
                }
            ),
            "doc_occ": encode_doc({}),
            "doc_meta": encode_doc(meta),
        }

    def _initial_life(self, sn: str, cls_code: str) -> tuple[int, float, int, int, int]:
        """Initial recorded life of a serial: a steady-state fleet has items at uniform fractions of their
        limits [ASSUMPTION A-W1.8-20]; items without a limit start at a uniform age in [0, 1000] h."""
        c = self.cat.cls(cls_code)
        g = self.stream("init_serial", serial=sn).generator(0)
        u = g.random(4)
        life_fh = c.v("life_fh")
        tsn = int(u[0] * (life_fh if life_fh > 0 else 1000.0 * 3600.0))
        ldg_lim = c.v("life_landings")
        ldg = int(u[1] * ldg_lim) if ldg_lim > 0 else int(u[1] * 1000)
        strm_lim = c.v("life_streams")
        strm = int(u[2] * strm_lim) if strm_lim > 0 else 0
        yrs = c.v("life_years")
        life0 = -int(u[3] * yrs) * NS if yrs > 0 else 0
        csn = float(tsn) / 3600.0 * 2.5 if c.code == "ENG" else 0.0
        return tsn, csn, ldg, strm, life0

    def initial_outputs(self, state: State) -> dict[str, np.ndarray]:
        return {}

    # ================================================================================================
    # dispatch
    def on_event(self, state: State, event: Event, t: int):
        h = self._handlers.get(event.kind)
        if h is None:
            return super().on_event(state, event, t)
        now = check_whole_second(event.t_ns, f"{event.kind} time")
        ctx = _Ctx(self, Cow(state), now)
        h(ctx, _pl(event))
        ctx.cow.put("t_last", np.array(max(int(ctx.cow.a("t_last")), now), dtype=np.int64))
        return ctx.cow.commit(), ctx.out

    # ------------------------------------------------------------------------------------------------ helpers
    def abs_ns(self, t: int) -> int:
        return self.epoch + t

    def _emit(
        self,
        ctx: _Ctx,
        kind: str,
        target: str | None,
        doc: Mapping[str, Any],
        *,
        t: int | None = None,
        priority: int = 0,
    ) -> None:
        if target is None:
            return
        tt = ctx.t if t is None else max(int(t), ctx.t)
        ctx.out.append(Event(tt, kind, target, plain_payload(doc), priority=priority, source=self.id))

    def _self(self, ctx: _Ctx, kind: str, doc: Mapping[str, Any], t: int, priority: int = 0) -> None:
        self._emit(ctx, kind, self.id, doc, t=t, priority=priority)

    def _local_date(self, t: int) -> datetime:
        return datetime.fromtimestamp(self.work.local_s(t), tz=UTC)

    def _day(self, t: int) -> int:
        return self.work.local_day(t)

    def _occ(self, ctx: _Ctx, scope: str, slot: int) -> int:
        doc = ctx.cow.doc("doc_occ")
        day = self._day(ctx.t)
        e = doc.get(scope)
        if e is None or e["day"] != day:
            e = {"day": day, "k": {}}
            doc[scope] = e
        k = int(e["k"].get(str(slot), 0))
        e["k"][str(slot)] = k + 1
        ctx.cow.touch("doc_occ")
        if k >= 4096 or slot >= 64:
            raise OverflowError("occurrence index out of range")
        return (day * 64 + slot) * 4096 + k

    def _tail_gen(self, ctx: _Ctx, ti: int, slot: int) -> np.random.Generator:
        tn = self.fleet.tails[ti]
        return self.stream("tail_exec", tail=tn).generator(self._occ(ctx, f"t:{tn}", slot))

    def _lognormal_s(self, g: np.random.Generator, median_s: float, sigma: float, floor_s: int = 60) -> int:
        return max(floor_s, to_s(median_s * math.exp(sigma * float(g.standard_normal()))))

    def _rec(
        self,
        ctx: _Ctx,
        rtype: str,
        key: str,
        version: int,
        *,
        t_event: int | None = None,
        hints: Mapping[str, Any] | None = None,
        order_id: str | None = None,
        **fields: Any,
    ) -> str:
        te = ctx.t if t_event is None else int(t_event)
        for f in ("t_open", "t_close"):
            if fields.get(f) is not None:
                fields[f] = self.abs_ns(int(fields[f]))
        row = maint_row(
            self.contract,
            dict_version=self.dict_version,
            dict_hash=self.dict_hash,
            record_type=rtype,
            record_key=key,
            record_version=version,
            t_event=self.abs_ns(te),
            t_ingest=self.abs_ns(max(ctx.t, te)),
            order_id=order_id,
            **fields,
        )
        doc = {"row": row}
        if hints:
            doc["hints"] = dict(hints)
        self._emit(ctx, f"rec.{MAINT}", self.targets.sink, doc)
        if order_id is not None:
            e = ctx.cow.doc("doc_meta").get("orders", {}).get(order_id)
            if e is not None:
                e["recs"].append(row["record_id"])
                ctx.cow.touch("doc_meta")
        return row["record_id"]

    def _ord(self, ctx: _Ctx, order_id: str) -> dict:
        """Execution bookkeeping of one order: open jobs/demands, records produced, last status sent."""
        meta = ctx.cow.doc("doc_meta")
        e = meta.setdefault("orders", {}).setdefault(order_id, {"open": 0, "recs": [], "last": None})
        ctx.cow.touch("doc_meta")
        return e

    def _order_progress(
        self, ctx: _Ctx, order_id: str | None, status: str, reason: str | None = None
    ) -> None:
        """Report an order's lifecycle to M21: QUEUED / IN_WORK once each, COMPLETED when its last job or
        demand finishes, REJECTED with a reason. Results carry every record the execution produced."""
        if order_id is None or self.targets.m21 is None:
            return
        e = self._ord(ctx, order_id)
        if status == "COMPLETED" and int(e["open"]) > 0:
            return
        if status == e["last"]:
            return
        if e["last"] == "IN_WORK" and status == "QUEUED":
            return
        e["last"] = status
        rids = list(e["recs"])
        if status in ("COMPLETED", "REJECTED"):
            del ctx.cow.doc("doc_meta")["orders"][order_id]
        self._emit(
            ctx,
            "order.progress",
            self.targets.m21,
            {"order_id": order_id, "status": status, "reason": reason, "result_record_ids": rids},
        )

    def _tech(self, ctx: _Ctx, n: int, prefix: str = "TECH") -> str:
        return f"{prefix}-{n:03d}"

    # ------------------------------------------------------------------------------------------------
    # identity
    def _job_no(self, ctx: _Ctx, base: str, prefix: str = "") -> str:
        meta = ctx.cow.doc("doc_meta")
        d = self._local_date(ctx.t)
        key = f"{base}|{d.strftime('%y%j')}"
        n = int(meta["job_seq"].get(key, 0)) + 1
        meta["job_seq"] = {k: v for k, v in meta["job_seq"].items() if k.split("|")[1] >= d.strftime("%y%j")}
        meta["job_seq"][key] = n
        ctx.cow.touch("doc_meta")
        return f"{prefix}{base}-{d.strftime('%y%j')}-{n:04d}"

    def _demand_no(self, ctx: _Ctx, base: str) -> str:
        meta = ctx.cow.doc("doc_meta")
        d = self._local_date(ctx.t)
        key = f"{base}|{d.strftime('%y%j')}"
        n = int(meta["dem_seq"].get(key, 0)) + 1
        meta["dem_seq"] = {k: v for k, v in meta["dem_seq"].items() if k.split("|")[1] >= d.strftime("%y%j")}
        meta["dem_seq"][key] = n
        ctx.cow.touch("doc_meta")
        return f"D-{base}-{d.strftime('%y%j')}-{n:04d}"

    def _serial_head(self, cls_code: str) -> str:
        """The prefix of the serials M18 mints for ``cls_code``: engines take the scenario's engine serial
        prefix when it is configured (one engine serial format, W2.1c); every other class its class code."""
        if cls_code == ENGINE_CLASS and self.fleet.engine_serial_prefix:
            return self.fleet.engine_serial_prefix
        return cls_code

    def _new_serial(self, ctx: _Ctx, cls_index: int, base: int, *, loc: int) -> int:
        c = self.cat.classes[cls_index]
        meta = ctx.cow.doc("doc_meta")
        taken = set(ctx.cow.a("ser_no").tolist())
        n = int(meta["ser_seq"][c.code])
        while True:
            n += 1
            sn = f"{self._serial_head(c.code)}-{n:06d}"
            if sn not in taken:
                break
        meta["ser_seq"][c.code] = n
        ctx.cow.touch("doc_meta")
        cols = {
            "ser_no": np.array([sn], dtype="<U48"),
            "ser_cls": np.array([cls_index], dtype=np.int32),
            "ser_loc": np.array([loc], dtype=np.int8),
            "ser_tail": np.array([-1], dtype=np.int32),
            "ser_pos": np.array([-1], dtype=np.int32),
            "ser_base": np.array([base], dtype=np.int32),
            "ser_t_ready": np.array([-1], dtype=np.int64),
            "ser_tsn": np.array([0], dtype=np.int64),
            "ser_tso": np.array([0], dtype=np.int64),
            "ser_csn": np.array([0.0], dtype=np.float64),
            "ser_ldg": np.array([0], dtype=np.int64),
            "ser_strm": np.array([0], dtype=np.int64),
            "ser_t_life0": np.array([ctx.t], dtype=np.int64),
            "ser_faults": np.array([0], dtype=np.int32),
            "ser_visits": np.array([0], dtype=np.int32),
            "ser_rtok": np.array([0], dtype=np.int32),
            "ser_moves": np.array([0], dtype=np.int32),
            "ser_alloc": np.array([""], dtype="<U40"),
            "ser_depot": np.array([0], dtype=np.int8),
        }
        row = int(ctx.cow.a("ser_no").shape[0])
        for name, v in cols.items():
            ctx.cow.put(name, np.concatenate([ctx.cow.a(name), v]))
        return row

    def _serial_row(self, ctx: _Ctx, sn: str) -> int:
        hits = np.flatnonzero(ctx.cow.a("ser_no") == sn)
        return int(hits[0]) if hits.size else -1

    # ------------------------------------------------------------------------------------------------ tail
    # facts
    def _tail_jobs(self, ctx: _Ctx, ti: int) -> list[dict]:
        tn = self.fleet.tails[ti]
        return [j for j in ctx.jobs["open"].values() if j["tail"] == tn]

    def _flags(self, ctx: _Ctx, ti: int) -> scir.TailFlags:
        g_awp = g_uns = g_sch = p_awp = p_open = False
        for j in self._tail_jobs(ctx, ti):
            if j["step"] == "monitor":  # deferred-and-monitored BIT code: administrative, no capability loss
                continue
            st = j["status"]
            if j["grounding"]:
                if st == AWP:
                    g_awp = True
                elif j["scheduled"]:
                    g_sch = True
                else:
                    g_uns = True
            else:
                if st == AWP:
                    p_awp = True
                else:
                    p_open = True
        if int(ctx.cow.a("tail_hold")[ti]):
            g_uns = True
        return scir.TailFlags(
            at_depot=bool(ctx.cow.a("tail_depot")[ti]),
            grounding_awp=g_awp,
            grounding_unscheduled=g_uns,
            grounding_scheduled=g_sch,
            partial_awp=p_awp,
            partial_open=p_open,
        )

    def _mission_capable(self, ctx: _Ctx, ti: int) -> bool:
        return int(ctx.cow.a("av_cur")[ti]) in scir.MC_CODES

    def _limits_text(self, ctx: _Ctx, ti: int) -> str:
        tn = self.fleet.tails[ti]
        td = ctx.cow.doc("doc_tails")[tn]
        parts = []
        if int(ctx.cow.a("tail_hold")[ti]):
            parts.append("GROUNDED BY ORDER")
        down = sorted(j["job_no"] for j in self._tail_jobs(ctx, ti) if j["grounding"])
        if down:
            parts.append("U/S: " + " ".join(down))
        deferred = sorted(j["job_no"] for j in self._tail_jobs(ctx, ti) if j["status"] == DEFERRED)
        if deferred:
            parts.append("DEFERRED: " + " ".join(deferred))
        parts += [f"LIMIT: {x}" for x in td["limits"]]
        return "; ".join(parts) if parts else "SERVICEABLE"

    def _refresh(self, ctx: _Ctx, ti: int) -> None:
        """Recompute the tail's instantaneous state; on change update the 15-min binning and the tech log."""
        new = scir.instantaneous_state(self._flags(ctx, ti))
        cur = int(ctx.cow.a("av_cur")[ti])
        tn = self.fleet.tails[ti]
        td = ctx.cow.doc("doc_tails")[tn]
        text = self._limits_text(ctx, ti)
        if new != cur:
            self._avail_change(ctx, ti, new)
        if new != cur or td.get("tl_text") != text or int(ctx.cow.a("tl_ver")[ti]) < 0:
            td["tl_text"] = text
            ctx.cow.touch("doc_tails")
            v = int(ctx.cow.a("tl_ver")[ti]) + 1
            ctx.cow.w("tl_ver")[ti] = v
            self._rec(
                ctx,
                "TECH_LOG",
                f"TL-{tn}",
                v,
                tail_no=tn,
                base=self.fleet.bases[self.fleet.tail_base[ti]],
                limitations_text=text,
                availability_state=scir.STATES[new],
                sw_config_id=td["sw"],
            )

    def _avail_change(self, ctx: _Ctx, ti: int, new: int) -> None:
        """Incremental SCIR binning (same rule as scir.bin_states, tested): bin = max(carried, entered)."""
        t_abs = self.abs_ns(ctx.t)
        b = bin_start(t_abs, self.bin_ns)
        cur = int(ctx.cow.a("av_cur")[ti])
        if int(ctx.cow.a("av_bin")[ti]) != b:
            ctx.cow.w("av_bin")[ti] = b
            ctx.cow.w("av_worst")[ti] = cur
            ctx.cow.w("av_ver")[ti] = -1
        worst = scir.worse(int(ctx.cow.a("av_worst")[ti]), new)
        ctx.cow.w("av_worst")[ti] = worst
        ctx.cow.w("av_cur")[ti] = new
        since = int(ctx.cow.a("av_nmc_since")[ti])
        if new in scir.NMC_CODES and since < 0:
            ctx.cow.w("av_nmc_since")[ti] = t_abs
        elif new in scir.MC_CODES:
            ctx.cow.w("av_nmc_since")[ti] = -1
        self._av_publish(ctx, ti, b)
        if worst != new:
            nb = b + self.bin_ns
            if int(ctx.cow.a("av_tick")[ti]) != nb:
                ctx.cow.w("av_tick")[ti] = nb
                self._self(ctx, "m18.avtick", {"tail": ti, "bin": nb}, nb - self.epoch)

    def _av_publish(self, ctx: _Ctx, ti: int, b: int) -> None:
        worst = int(ctx.cow.a("av_worst")[ti])
        if worst == int(ctx.cow.a("av_emit")[ti]):
            return
        v = int(ctx.cow.a("av_ver")[ti]) + 1
        ctx.cow.w("av_ver")[ti] = v
        ctx.cow.w("av_emit")[ti] = worst
        tn = self.fleet.tails[ti]
        self._rec(
            ctx,
            "AVAILABILITY_STATE",
            f"AV-{tn}-{b // NS}",
            v,
            t_event=b - self.epoch,
            tail_no=tn,
            base=self.fleet.bases[self.fleet.tail_base[ti]],
            availability_state=scir.STATES[worst],
        )

    def _h_avtick(self, ctx: _Ctx, d: dict) -> None:
        ti, b = int(d["tail"]), int(d["bin"])
        if int(ctx.cow.a("av_tick")[ti]) != b:
            return
        ctx.cow.w("av_tick")[ti] = -1
        if int(ctx.cow.a("av_bin")[ti]) != b:
            ctx.cow.w("av_bin")[ti] = b
            ctx.cow.w("av_worst")[ti] = int(ctx.cow.a("av_cur")[ti])
            ctx.cow.w("av_ver")[ti] = -1
            self._av_publish(ctx, ti, b)

    # ================================================================================================ start
    def _h_start(self, ctx: _Ctx, d: dict) -> None:
        meta = ctx.cow.doc("doc_meta")
        if meta["started"]:
            return
        meta["started"] = True
        ctx.cow.touch("doc_meta")
        no = ctx.cow.a("ser_no")
        for ti, tn in enumerate(self.fleet.tails):
            for p in self.cat.positions:
                r = int(ctx.cow.a("tail_inst")[ti, p.index])
                self._life_record(ctx, r, "INSTALL", ti, job_no=None)
                self._emit(
                    ctx,
                    "cfg.install",
                    self.targets.health,
                    {"tail": tn, "pos": p.code, "serial": str(no[r]), "cls": p.cls.code},
                )
            # initial availability record and tech log
            ctx.cow.w("av_bin")[ti] = bin_start(self.abs_ns(ctx.t), self.bin_ns)
            self._av_publish(ctx, ti, int(ctx.cow.a("av_bin")[ti]))
            self._refresh(ctx, ti)
        self._schedule_review(ctx)

    def _schedule_review(self, ctx: _Ctx) -> None:
        meta = ctx.cow.doc("doc_meta")
        nxt = self.calendar.next_epoch(ctx.t + NS)
        if meta.get("review_next") != nxt:
            meta["review_next"] = nxt
            ctx.cow.touch("doc_meta")
            self._self(ctx, "m18.review", {"t": nxt}, nxt, priority=PRIO_REVIEW)

    def _life_record(
        self,
        ctx: _Ctx,
        r: int,
        action: str,
        ti: int,
        *,
        job_no: str | None,
        order_id: str | None = None,
        at: str = "",
    ) -> str:
        c = self.cat.classes[int(ctx.cow.a("ser_cls")[r])]
        mv = int(ctx.cow.a("ser_moves")[r])
        ctx.cow.w("ser_moves")[r] = mv + 1
        sn = str(ctx.cow.a("ser_no")[r])
        hints = {"depot_returned": bool(ctx.cow.a("ser_depot")[r])} if action == "INSTALL" else None
        return self._rec(
            ctx,
            "COMPONENT_LIFE",
            sn,
            mv,
            hints=hints,
            order_id=order_id,
            tail_no=self.fleet.tails[ti],
            base=self.fleet.bases[self.fleet.tail_base[ti]],
            job_no=job_no,
            part_no=c.part_no,
            serial_no=sn,
            maker=c.maker,
            engine_serial=sn if c.code == "ENG" else None,
            install_action=action,
            item_hours=float(ctx.cow.a("ser_tsn")[r]) / 3600.0,
            item_cycles=float(ctx.cow.a("ser_csn")[r]) if c.code == "ENG" else float(ctx.cow.a("ser_ldg")[r]),
            system_code=c.system,
            limitations_text=at or None,
        )

    # ================================================================================================ sorties
    def _h_offer_request(self, ctx: _Ctx, d: dict) -> None:
        tails = []
        for ti, tn in enumerate(self.fleet.tails):
            if (
                self._mission_capable(ctx, ti)
                and not int(ctx.cow.a("tail_flying")[ti])
                and not int(ctx.cow.a("tail_hold")[ti])
                and not self._busy_on(ctx, ti)
            ):
                tails.append(tn)
        td = ctx.cow.doc("doc_tails")
        restrict = {tn: td[tn]["restrict"] for tn in tails if td[tn]["restrict"]}
        self._emit(
            ctx,
            "ops.offer",
            d["reply_to"] or self.targets.scenario,
            {"day": d["day"], "tails": tails, "restrict": restrict},
        )

    def _busy_on(self, ctx: _Ctx, ti: int) -> bool:
        return any(j["status"] == IN_WORK for j in self._tail_jobs(ctx, ti))

    def _h_launch(self, ctx: _Ctx, d: dict) -> None:
        ti = self.tidx[d["tail_no"]]
        reason = None
        if int(ctx.cow.a("tail_flying")[ti]):
            reason = "already flying"
        elif int(ctx.cow.a("tail_hold")[ti]):
            reason = "grounded by order"
        elif not self._mission_capable(ctx, ti):
            reason = "not mission capable"
        elif self._busy_on(ctx, ti):
            reason = "maintenance in work"
        if reason is not None:
            self._emit(
                ctx,
                "ops.launch_denied",
                d["reply_to"] or self.targets.scenario,
                {"sortie_id": d["sortie_id"], "tail_no": d["tail_no"], "reason": reason},
            )
            return
        ctx.cow.w("tail_flying")[ti] = 1

    def _h_ground_abort(self, ctx: _Ctx, d: dict) -> None:
        ti = self.tidx[d["tail_no"]]
        ctx.cow.w("tail_flying")[ti] = 0
        self._dispatch(ctx, self.fleet.tail_base[ti])

    def _fault_at(self, ctx: _Ctx, f: Mapping[str, Any]) -> tuple[int, int] | None:
        """Where the faulty serial is installed now (tail index, position) or None: a fault travels with its
        serial (a bench-missed unit returned to stock carries its fault to the next aircraft)."""
        r = self._serial_row(ctx, f["serial"])
        if r < 0 or int(ctx.cow.a("ser_loc")[r]) != LOC_INSTALLED:
            return None
        return int(ctx.cow.a("ser_tail")[r]), int(ctx.cow.a("ser_pos")[r])

    def _h_sortie_done(self, ctx: _Ctx, d: dict) -> None:
        ti = self.tidx[d["tail_no"]]
        ctx.cow.w("tail_flying")[ti] = 0
        self._self(ctx, "m18.sortie_entry", d, ctx.t + self.cfg.sortie_entry_delay_s * NS)
        faults = ctx.cow.doc("doc_faults")
        tn = self.fleet.tails[ti]
        due = sorted(
            fid
            for fid, f in faults.items()
            if f["active"]
            and not f["reported"]
            and f["symptom"] in ("pilot", "both", "preflight")
            and int(f["t_onset"]) <= ctx.t
            and (self._fault_at(ctx, f) or (-1, -1))[0] == ti
        )
        if due:
            for fid in due:
                faults[fid]["reported"] = True
            ctx.cow.touch("doc_faults")
            self._self(
                ctx,
                "m18.writeup",
                {"tail": tn, "faults": due, "sortie_id": d["sortie_id"], "aborted": bool(d["aborted"])},
                ctx.t + self.cfg.debrief_delay_s * NS,
            )
        self._dispatch(ctx, self.fleet.tail_base[ti])

    def _h_sortie_entry(self, ctx: _Ctx, d: dict) -> None:
        ti = self.tidx[d["tail_no"]]
        tn = self.fleet.tails[ti]
        fh_s = to_s(float(d["flight_hours"]) * 3600.0)
        landings = int(d["landings"])
        cycles = float(d["engine_cycles"])
        starts = int(d["engine_starts"])
        streams = int(d["chute_streamed"])
        inst = ctx.cow.a("tail_inst")[ti]
        eng_row = int(inst[self.cat.pos("ENG").index]) if "ENG" in self.cat.pos_by_code else -1
        self._rec(
            ctx,
            "SORTIE",
            d["sortie_id"],
            0,
            t_event=int(d["t_landing"]),
            tail_no=tn,
            base=self.fleet.bases[self.fleet.tail_base[ti]],
            sortie_id=d["sortie_id"],
            engine_serial=str(ctx.cow.a("ser_no")[eng_row]) if eng_row >= 0 else None,
            sw_config_id=ctx.cow.doc("doc_tails")[tn]["sw"],
            mission_type=d.get("mission_type"),
            crew_id=d.get("crew_id"),
            flight_hours=fh_s / 3600.0,
            landings=landings,
            engine_cycles=cycles,
            engine_starts=starts,
            t_open=int(d["t_takeoff"]),
            t_close=int(d["t_landing"]),
        )
        for name, inc in (("tail_fh", fh_s), ("tail_ldg", landings), ("tail_sorties", 1)):
            ctx.cow.w(name)[ti] += inc
        ctx.cow.w("srv_fh")[ti, :] += fh_s
        rows = inst[inst >= 0]
        if rows.size:
            ctx.cow.w("ser_tsn")[rows] += fh_s
            ctx.cow.w("ser_tso")[rows] += fh_s
            for r in rows.tolist():
                code = self.cat.classes[int(ctx.cow.a("ser_cls")[r])].code
                if code == "ENG":
                    ctx.cow.w("ser_csn")[r] += cycles
                if code in ("BRAKE", "TYRE"):
                    ctx.cow.w("ser_ldg")[r] += landings
                if code == "CHUTE":
                    ctx.cow.w("ser_strm")[r] += streams
        # deferred-and-monitored BIT jobs count flights (F-35 HRC workflow)
        for j in sorted(self._tail_jobs(ctx, ti), key=lambda j: j["job_no"]):
            if j["step"] == "monitor":
                j["monitor_left"] = int(j["monitor_left"]) - 1
                ctx.cow.touch("doc_jobs")
                if j["monitor_left"] <= 0:
                    j["at"], j["mal"] = "AT-ADM", "MAL-FAL"
                    j["ca_text"] = self._text("corrective", "admin", n=self.cfg.monitor_flights)
                    self._close_job(ctx, j)

    # ================================================================================================
    # discovery
    def _text(self, group: str, key: str, **kw: Any) -> str:
        tmpl = self.codes.texts[group][key]
        return tmpl.format_map(_Default(kw))

    def _symptom(self, pos_index: int) -> str:
        return self.codes.texts["symptoms"].get(self.cat.positions[pos_index].cls.ambiguity, "DEFECTIVE")

    def _new_job(
        self,
        ctx: _Ctx,
        ti: int,
        *,
        kind: str,
        rtype: str,
        source: str,
        wd: str,
        tm: str,
        grounding: bool,
        scheduled: bool,
        suspects: list[int] | None = None,
        target: int | None = None,
        code: str | None = None,
        evidence: list[str] | None = None,
        text: str = "",
        order_id: str | None = None,
        mal: str = "MAL-FAIL",
        extra: Mapping[str, Any] | None = None,
        prefix: str = "",
    ) -> dict:
        tn = self.fleet.tails[ti]
        base = self.fleet.bases[self.fleet.tail_base[ti]]
        job_no = self._job_no(ctx, base, prefix)
        top = target if target is not None else (suspects[0] if suspects else None)
        part_no = self.cat.positions[top].cls.part_no if top is not None else None
        system = self.cat.positions[top].cls.system if top is not None else None
        job = {
            "job_no": job_no,
            "tail": tn,
            "ti": ti,
            "base": base,
            "kind": kind,
            "rtype": rtype,
            "source": source,
            "wd": wd,
            "tm": tm,
            "grounding": bool(grounding),
            "scheduled": bool(scheduled),
            "suspects": list(suspects or ([] if target is None else [target])),
            "target": target,
            "code": code,
            "evidence": list(evidence or []),
            "status": OPEN,
            "step": "new",
            "version": -1,
            "t_open": ctx.t,
            "t_awp": -1,
            "tok": 0,
            "order_id": order_id,
            "mh": 0.0,
            "part_no": part_no,
            "system": system,
            "disc": text,
            "ca_text": None,
            "at": None,
            "mal": mal,
            "spare": -1,
            "demand": None,
            "removed": None,
            "installed": None,
            "children": [],
            "parent": None,
            "monitor_left": 0,
            "inspection_type": None,
            "linked": None,
            "donor": None,
            "corrected_by": None,
            "inspected_by": None,
        }
        if extra:
            job.update(extra)
        ctx.jobs["open"][job_no] = job
        ctx.cow.touch("doc_jobs")
        if order_id is not None:
            self._ord(ctx, order_id)["open"] += 1
        self._publish_job(ctx, job)
        return job

    def _publish_job(self, ctx: _Ctx, job: dict, *, t_close: int | None = None) -> str:
        job["version"] = int(job["version"]) + 1
        ctx.cow.touch("doc_jobs")
        int(job["ti"])
        r_removed = job.get("removed")
        sn = None
        if job.get("installed") is not None:
            sn = job["installed"]
        elif r_removed is not None:
            sn = r_removed
        fields: dict[str, Any] = dict(
            status=job["status"],
            tail_no=job["tail"],
            base=job["base"],
            job_no=job["job_no"],
            linked_job_no=job.get("linked"),
            demand_no=job.get("demand"),
            part_no=job.get("part_no"),
            serial_no=sn,
            evidence_record_ids=list(job["evidence"]),
            when_discovered=job["wd"],
            system_code=job.get("system"),
            malfunction_code=job.get("mal"),
            action_taken_code=job.get("at"),
            type_maint_code=job["tm"],
            discrepancy_text=job.get("disc") or None,
            corrective_action_text=job.get("ca_text"),
            man_hours=round(float(job["mh"]), 3),
            t_open=int(job["t_open"]),
            t_close=t_close,
            inspection_type=job.get("inspection_type"),
            corrected_by=job.get("corrected_by"),
            inspected_by=job.get("inspected_by"),
            donor_tail_no=job.get("donor"),
            sw_config_id=ctx.cow.doc("doc_tails")[job["tail"]]["sw"]
            if job["rtype"] == "MODIFICATION"
            else None,
            compliance_status=job.get("compliance") if job["rtype"] == "MODIFICATION" else None,
        )
        if job["part_no"] is not None:
            c = self.cls_by_pn[job["part_no"]]
            fields["maker"] = c.maker
            if c.code == "ENG" and sn is not None:
                fields["engine_serial"] = sn
        return self._rec(
            ctx,
            job["rtype"],
            job["job_no"],
            int(job["version"]),
            order_id=job.get("order_id"),
            hints={"grounding": job["grounding"], "kind": job["kind"]},
            **fields,
        )

    def _h_writeup(self, ctx: _Ctx, d: dict) -> None:
        ti = self.tidx[d["tail"]]
        faults = ctx.cow.doc("doc_faults")
        for fid in d["faults"]:
            f = faults.get(fid)
            loc = None if f is None else self._fault_at(ctx, f)
            if f is None or not f["active"] or loc is None or loc[0] != ti:
                continue
            pos = loc[1]
            group = list(self.cat.ambiguity_group(pos))
            existing = self._match_job(ctx, ti, group, None)
            wd = "WD-ABT" if d.get("aborted") else "WD-AIR"
            if existing is not None:
                self._escalate(ctx, existing, repeat=True)
                continue
            item = self.cat.positions[group[0]].cls.name.upper()
            job = self._new_job(
                ctx,
                ti,
                kind="defect",
                rtype="DEFECT_WO",
                source="pilot",
                wd=wd,
                tm="TM-UNS",
                grounding=bool(f["grounding"]) or any(self.cat.positions[p].cls.grounding for p in group),
                scheduled=False,
                suspects=group,
                text=self._text("discrepancy", "pilot", item=item, symptom=self._symptom(pos)),
            )
            self._request_team(ctx, job)
        self._refresh(ctx, ti)

    def _match_job(self, ctx: _Ctx, ti: int, positions: list[int], code: str | None) -> dict | None:
        """An open defect on the tail for the same code or overlapping suspects (avoid duplicate snags)."""
        ps = set(positions)
        for j in sorted(self._tail_jobs(ctx, ti), key=lambda j: j["job_no"]):
            if j["kind"] != "defect" or j["status"] == CLOSED:
                continue
            if (code is not None and j.get("code") == code) or ps & set(j["suspects"]):
                return j
        return None

    def _escalate(self, ctx: _Ctx, job: dict, *, repeat: bool, evidence: list[str] | None = None) -> None:
        if evidence:
            job["evidence"] = sorted(set(job["evidence"]) | set(evidence))
        if job["step"] == "monitor":  # recurrence of a deferred-and-monitored code -> troubleshoot now
            job["step"] = "new"
            job["status"] = OPEN
            job["disc"] = self._text(
                "discrepancy",
                "bit_repeat",
                code=job.get("code") or "",
                item=self.cat.positions[job["suspects"][0]].cls.name.upper(),
            )
            ctx.cow.touch("doc_jobs")
            self._publish_job(ctx, job)
            self._request_team(ctx, job)
        elif evidence:
            ctx.cow.touch("doc_jobs")
            self._publish_job(ctx, job)

    def _h_obs_event(self, ctx: _Ctx, d: dict) -> None:
        self._self(ctx, "m18.obsjob", d, ctx.t + self.cfg.hms_review_delay_s * NS)

    def _suspect_positions(self, row: Mapping[str, Any]) -> list[int]:
        out: list[int] = []
        for s in row.get("suspect_lrus") or []:
            for p in self.cat.positions_for_lru(s["lru"]):
                if p not in out:
                    out.append(p)
        if not out:
            prefix = str(row.get("event_code", ""))[:3]
            system = {"ECM": "ENG"}.get(prefix, prefix)
            out = list(self.cat.positions_for_system(system))
        return out

    def _h_obsjob(self, ctx: _Ctx, d: dict) -> None:
        topic, row = d["topic"], d["row"]
        tn = row.get("tail_no")
        if tn not in self.tidx:
            return
        ti = self.tidx[tn]
        code = str(row.get("event_code"))
        if code in ctx.cow.doc("doc_tails")[tn]["filters"]:
            return
        rid = row["record_id"]
        if topic == "events.exceedances":
            self._exceedance_job(ctx, ti, row)
            self._refresh(ctx, ti)
            return
        if topic == "events.cautions" and not row.get("displayed", False):
            return
        positions = self._suspect_positions(row)
        if not positions:
            return
        existing = self._match_job(ctx, ti, positions, code)
        if existing is not None:
            self._escalate(ctx, existing, repeat=True, evidence=[rid])
            self._refresh(ctx, ti)
            return
        grounding = (
            any(self.cat.positions[p].cls.grounding for p in positions[:1])
            and row.get("severity") != "ADVISORY"
        )
        pilot = topic == "events.cautions"
        item = self.cat.positions[positions[0]].cls.name.upper()
        job = self._new_job(
            ctx,
            ti,
            kind="defect",
            rtype="DEFECT_WO",
            source="pilot" if pilot else "bit",
            wd="WD-DBF" if pilot else "WD-HMS",
            tm="TM-UNS",
            grounding=grounding,
            scheduled=False,
            suspects=positions,
            code=code,
            evidence=[rid],
            mal="MAL-BIT",
            text=(
                self._text("discrepancy", "pilot", item=item, symptom=self._symptom(positions[0]))
                if pilot
                else self._text("discrepancy", "bit", code=code, item=item)
            ),
        )
        if not grounding and not pilot:
            job["status"], job["step"], job["monitor_left"] = DEFERRED, "monitor", self.cfg.monitor_flights
            job["at"] = "AT-DEF"
            ctx.cow.touch("doc_jobs")
            self._publish_job(ctx, job)
        else:
            self._request_team(ctx, job)
        self._refresh(ctx, ti)

    def _exceedance_job(self, ctx: _Ctx, ti: int, row: Mapping[str, Any]) -> None:
        code = str(row.get("event_code"))
        engine = code[:3] in ("ENG", "ECM") or str(row.get("param_id", "")).startswith(("ENG", "LUI"))
        itype = "COND-ENGINE" if engine else "COND-STRUCT"
        targets = [self.cat.pos("ENG").index] if engine else []
        job = self._new_job(
            ctx,
            ti,
            kind="cond",
            rtype="EXCEEDANCE_INSPECTION",
            source="exceedance",
            wd="WD-CND",
            tm="TM-SPI",
            grounding=True,
            scheduled=False,
            suspects=targets,
            code=code,
            evidence=[row["record_id"]],
            mal="MAL-OT" if engine else "MAL-OG",
            text=self._text("discrepancy", "exceedance", code=code),
            extra={"inspection_type": itype},
        )
        job["part_no"] = self.cat.positions[targets[0]].cls.part_no if targets else None
        self._request_team(ctx, job)

    # ================================================================================================ truth
    def _h_truth_fault(self, ctx: _Ctx, d: dict) -> None:
        faults = ctx.cow.doc("doc_faults")
        fid = d["fault_id"]
        if fid in faults:
            return
        r = self._serial_row(ctx, d["serial"])
        faults[fid] = {
            "tail": d["tail"],
            "pos": d["pos"],
            "serial": d["serial"],
            "mode": d["mode"],
            "symptom": d["symptom"],
            "grounding": bool(d["grounding"]),
            "t_onset": ctx.t,
            "active": True,
            "reported": False,
        }
        ctx.cow.touch("doc_faults")
        if r >= 0:
            ctx.cow.w("ser_faults")[r] += 1
        loc = self._fault_at(ctx, faults[fid])
        if faults[fid]["symptom"] == "preflight" and loc is not None:
            ti = loc[0]
            if not int(ctx.cow.a("tail_flying")[ti]):
                faults[fid]["reported"] = True
                self._self(
                    ctx,
                    "m18.writeup",
                    {"tail": self.fleet.tails[ti], "faults": [fid], "sortie_id": None, "aborted": False},
                    ctx.t,
                )

    def _h_truth_fault_clear(self, ctx: _Ctx, d: dict) -> None:
        faults = ctx.cow.doc("doc_faults")
        f = faults.get(d["fault_id"])
        if f is None or not f["active"]:
            return
        f["active"] = False
        ctx.cow.touch("doc_faults")
        r = self._serial_row(ctx, f["serial"])
        if r >= 0 and int(ctx.cow.a("ser_faults")[r]) > 0:
            ctx.cow.w("ser_faults")[r] -= 1

    def _h_truth_incident(self, ctx: _Ctx, d: dict) -> None:
        ti = self.tidx[d["tail"]]
        kind = d["kind"]
        if kind == "start_failure":
            group = list(self.cat.ambiguity_group(self.cat.pos("JFS").index))
            job = self._new_job(
                ctx,
                ti,
                kind="defect",
                rtype="DEFECT_WO",
                source="preflight",
                wd="WD-PRE",
                tm="TM-UNS",
                grounding=True,
                scheduled=False,
                suspects=group,
                mal="MAL-STR",
                text=self._text("discrepancy", "start_failure", item="JFS"),
            )
            self._request_team(ctx, job)
        else:
            for pcode in d["positions"]:
                p = self.cat.pos(pcode).index
                item = self.cat.positions[p].cls.name.upper()
                job = self._new_job(
                    ctx,
                    ti,
                    kind="defect",
                    rtype="DEFECT_WO",
                    source="incident",
                    wd="WD-ABT",
                    tm="TM-UNS",
                    grounding=True,
                    scheduled=False,
                    target=p,
                    mal="MAL-DMG",
                    text=self._text("discrepancy", "incident", item=item),
                )
                self._request_team(ctx, job)
        self._refresh(ctx, ti)

    # ================================================================================================ teams
    def _base_name(self, job: dict) -> str:
        return job["base"]

    def _request_team(self, ctx: _Ctx, job: dict) -> None:
        if job["status"] == CLOSED:
            return
        res = ctx.cow.doc("doc_res")
        base = job["base"]
        if job["job_no"] in res["busy"][base]:
            self._start_work(ctx, job)
            return
        ti = int(job["ti"])
        if (
            len(res["busy"][base]) < self.cfg.teams
            and not int(ctx.cow.a("tail_flying")[ti])
            and not int(ctx.cow.a("tail_depot")[ti])
        ):
            res["busy"][base].append(job["job_no"])
            ctx.cow.touch("doc_res")
            self._start_work(ctx, job)
        else:
            awm = ctx.jobs["awm"]
            if job["job_no"] not in awm:
                awm.append(job["job_no"])
                ctx.cow.touch("doc_jobs")
            if job["status"] != AWM:
                job["status"] = AWM
                self._publish_job(ctx, job)

    def _release_team(self, ctx: _Ctx, job: dict) -> None:
        res = ctx.cow.doc("doc_res")
        base = job["base"]
        if job["job_no"] in res["busy"][base]:
            res["busy"][base].remove(job["job_no"])
            ctx.cow.touch("doc_res")
        self._dispatch(ctx, self.bidx[base])

    def _dispatch(self, ctx: _Ctx, bi: int) -> None:
        base = self.fleet.bases[bi]
        res = ctx.cow.doc("doc_res")
        jobs = ctx.jobs
        while len(res["busy"][base]) < self.cfg.teams:
            cand = []
            for jn in jobs["awm"]:
                j = jobs["open"].get(jn)
                if j is None or j["base"] != base:
                    continue
                ti = int(j["ti"])
                if int(ctx.cow.a("tail_flying")[ti]) or int(ctx.cow.a("tail_depot")[ti]):
                    continue
                cand.append((0 if j["grounding"] else 1, int(j["t_open"]), jn))
            if not cand:
                return
            _, _, jn = min(cand)
            jobs["awm"].remove(jn)
            ctx.cow.touch("doc_jobs")
            res["busy"][base].append(jn)
            ctx.cow.touch("doc_res")
            self._start_work(ctx, jobs["open"][jn])

    # ================================================================================================ job
    # engine
    def _schedule_step(
        self, ctx: _Ctx, job: dict, step: str, work_s: int, *, calendar_time: bool = False, mh: bool = True
    ) -> None:
        job["step"] = step
        job["tok"] = int(job["tok"]) + 1
        t_end = ctx.t + work_s * NS if calendar_time else self.work.add_work(ctx.t, work_s)
        if mh:
            job["mh"] = float(job["mh"]) + (work_s / 3600.0) * self.cfg.crew
        ctx.cow.touch("doc_jobs")
        self._self(ctx, "m18.job", {"job_no": job["job_no"], "tok": job["tok"], "step": step}, t_end)

    def _start_work(self, ctx: _Ctx, job: dict) -> None:
        ti = int(job["ti"])
        kind = job["kind"]
        if job["status"] != IN_WORK:
            job["status"] = IN_WORK
            if job.get("order_id"):
                self._order_progress(ctx, job["order_id"], "IN_WORK")
            self._publish_job(ctx, job)
        cls = self.cat.positions[job["suspects"][0]].cls if job["suspects"] else None
        sig = self.cfg.dur_sigma
        if job.get("spare", -1) >= 0 and job["step"] in ("await_part", "new", "issue", "rr_ready"):
            c = self.cat.positions[int(job["target"])].cls
            g = self._tail_gen(ctx, ti, SLOT_RR)
            self._schedule_step(ctx, job, "rr", self._lognormal_s(g, c.v("rr_hours"), sig))
        elif kind == "defect" and job["target"] is None:
            g = self._tail_gen(ctx, ti, SLOT_TS)
            self._schedule_step(
                ctx, job, "ts", self._lognormal_s(g, cls.v("ts_hours") if cls else 3600.0, sig)
            )
        elif kind == "defect":
            self._need_part(ctx, job, int(job["target"]))
        elif kind in ("cond", "inspect"):
            g = self._tail_gen(ctx, ti, SLOT_INSP)
            self._schedule_step(ctx, job, "insp", self._lognormal_s(g, self.cfg.inspection_s, sig))
        elif kind == "cann":
            c = self.cat.classes[int(job["cann_cls"])]
            g = self._tail_gen(ctx, ti, SLOT_CANN)
            self._schedule_step(ctx, job, "cann", self._lognormal_s(g, 2.0 * c.v("rr_hours"), sig))
            job["mh"] = float(job["mh"]) + self.cfg.cann_extra_mh_h
        elif kind in ("mod", "sw", "wash", "service"):
            median = {
                "mod": self.cfg.mod_s,
                "sw": self.cfg.sw_s,
                "wash": self.cfg.wash_s,
                "service": self.cfg.wash_s,
            }[kind]
            g = self._tail_gen(ctx, ti, SLOT_WORK)
            self._schedule_step(ctx, job, kind, self._lognormal_s(g, median, sig))
        else:
            raise AssertionError(f"cannot start job kind {kind}")

    def _h_job(self, ctx: _Ctx, d: dict) -> None:
        job = ctx.jobs["open"].get(d["job_no"])
        if job is None or int(job["tok"]) != int(d["tok"]) or job["step"] != d["step"]:
            return
        step = d["step"]
        ti = int(job["ti"])
        if step == "ts":
            self._ts_outcome(ctx, job)
        elif step == "issue":
            self._start_work(ctx, job)
        elif step == "rr":
            self._do_rr(ctx, job)
        elif step == "check":
            job["corrected_by"] = job.get("corrected_by") or self._tech(ctx, 1 + int(job["tok"]) % 40)
            job["inspected_by"] = self._tech(ctx, 1 + (int(job["tok"]) + 7) % 12, "INSP")
            self._close_job(ctx, job)
        elif step == "insp":
            self._insp_outcome(ctx, job)
        elif step == "cann":
            self._do_cann(ctx, job)
        elif step in ("mod", "sw", "wash", "service"):
            self._work_done(ctx, job)
        elif step == "srv":
            self._srv_end(ctx, job)
        self._refresh(ctx, ti)

    # ------------------------------------------------------------------------------------------------ defects
    def _active_faults_at(self, ctx: _Ctx, ti: int, positions: list[int]) -> list[tuple[int, str]]:
        """(position, fault_id) of active truth faults on serials installed at ``positions`` (hidden
        truth)."""
        out = []
        for fid, f in sorted(ctx.cow.doc("doc_faults").items()):
            if not f["active"]:
                continue
            loc = self._fault_at(ctx, f)
            if loc is not None and loc[0] == ti and loc[1] in positions:
                out.append((loc[1], fid))
        return out

    def _ts_outcome(self, ctx: _Ctx, job: dict) -> None:
        ti = int(job["ti"])
        cands = list(job["suspects"])
        group = sorted({q for p in cands for q in self.cat.ambiguity_group(p)})
        real = self._active_faults_at(ctx, ti, group)
        g = self._tail_gen(ctx, ti, SLOT_OUT)
        u = g.random(3)
        job["at"] = "AT-TS"
        if real:
            p_true = real[0][0]
            c = self.cat.positions[p_true].cls
            if u[0] < c.v("p_ground_repro"):
                if u[1] < c.v("p_isolate") or len(group) == 1:
                    target = p_true
                else:
                    others = [q for q in group if q != p_true]
                    target = others[int(u[2] * len(others)) % len(others)]
                self._set_target(ctx, job, target)
                self._need_part(ctx, job, target)
                return
        # nothing reproduced on the ground
        if job["grounding"] and u[1] < self.cfg.p_replace_unconfirmed:
            target = cands[0]
            self._set_target(ctx, job, target)
            self._need_part(ctx, job, target)
            return
        job["at"], job["mal"] = "AT-CND", "MAL-NDF"
        item = self.cat.positions[cands[0]].cls.name.upper() if cands else "SYSTEM"
        job["ca_text"] = self._text(
            "corrective", "cnd", item=item, task=f"PHX-FIM-{job.get('system') or 'GEN'}"
        )
        self._schedule_step(ctx, job, "check", self.cfg.check_s)

    def _set_target(self, ctx: _Ctx, job: dict, target: int) -> None:
        """Troubleshooting isolated an item: the work order gets a new record version when it changes."""
        changed = job.get("part_no") != self.cat.positions[target].cls.part_no
        job["target"] = target
        job["part_no"] = self.cat.positions[target].cls.part_no
        job["system"] = self.cat.positions[target].cls.system
        ctx.cow.touch("doc_jobs")
        if changed:
            self._publish_job(ctx, job)

    def _stock_rows(self, ctx: _Ctx, bi: int, cls_index: int) -> np.ndarray:
        a = ctx.cow
        m = (
            (a.a("ser_loc") == LOC_STOCK)
            & (a.a("ser_base") == bi)
            & (a.a("ser_cls") == cls_index)
            & (a.a("ser_alloc") == "")
        )
        return np.flatnonzero(m)

    def _need_part(self, ctx: _Ctx, job: dict, target: int) -> None:
        bi = self.bidx[job["base"]]
        c = self.cat.positions[target].cls
        rows = self._stock_rows(ctx, bi, c.index)
        if rows.size:
            r = int(rows[0])
            ctx.cow.w("ser_alloc")[r] = job["job_no"]
            job["spare"] = r
            self._schedule_step(ctx, job, "issue", self.cfg.issue_delay_s, calendar_time=True, mh=False)
            return
        if job.get("demand") is None:
            self._raise_demand(ctx, job, c.index, "AOG" if job["grounding"] else "MCM")
        job["status"], job["step"], job["t_awp"] = AWP, "await_part", ctx.t
        ctx.cow.touch("doc_jobs")
        self._publish_job(ctx, job)
        if job.get("order_id"):
            self._order_progress(ctx, job["order_id"], "QUEUED")
        self._release_team(ctx, job)

    def _raise_demand(
        self,
        ctx: _Ctx,
        job: dict | None,
        cls_index: int,
        priority: str,
        *,
        base: str | None = None,
        order_id: str | None = None,
    ) -> str:
        base = base or job["base"]
        c = self.cat.classes[cls_index]
        dn = self._demand_no(ctx, base)
        g = self.stream("supply", base=base).generator(self._occ(ctx, f"b:{base}", 8 + cls_index))
        z = float(g.standard_normal())
        lead = math.exp(self.cfg.lead_mu + self.cfg.lead_sigma * z)
        lead *= (
            self.cfg.tejas_supply_factor
            * c.v("lead_mult")
            * self.cfg.priority_mult[("AOG", "MCM", "PHU").index(priority)]
        )
        lead *= self._disruption(ctx, c.code)
        eta = ctx.t + max(3600, to_s(lead)) * NS
        dem = {
            "demand_no": dn,
            "base": base,
            "cls": cls_index,
            "priority": priority,
            "job": job["job_no"] if job else None,
            "t_open": ctx.t,
            "eta": eta,
            "tok": 0,
            "version": -1,
            "expedited": False,
            "order_id": order_id,
        }
        ctx.cow.doc("doc_supply")["demands"][dn] = dem
        ctx.cow.touch("doc_supply")
        if order_id is not None:
            self._ord(ctx, order_id)["open"] += 1
        if job is not None:
            job["demand"] = dn
        self._publish_demand(ctx, dem, "OPEN")
        self._self(ctx, "m18.supply", {"demand_no": dn, "tok": 0}, eta)
        return dn

    def _replenish(self, ctx: _Ctx, cls_index: int, base: str) -> None:
        """One-for-one replenishment of a consumed or condemned unit (base-stock policy) at routine priority
        [PROXY A-W1.8-17]."""
        self._raise_demand(ctx, None, cls_index, "MCM", base=base)

    def _disruption(self, ctx: _Ctx, cls_code: str) -> float:
        f = 1.0
        for dsr in ctx.cow.doc("doc_supply")["disruptions"]:
            if dsr["cls"] in (cls_code, "*") and int(dsr["t0"]) <= ctx.t < int(dsr["t1"]):
                f *= float(dsr["factor"])
        return f

    def _h_disruption(self, ctx: _Ctx, d: dict) -> None:
        """Tejas supply-chain layer: a lead-time factor for a class over [t0, t1) (e.g. engine supply
        delay)."""
        ctx.cow.doc("doc_supply")["disruptions"].append(
            {"cls": d["cls"], "factor": float(d["factor"]), "t0": int(d["t0"]), "t1": int(d["t1"])}
        )
        ctx.cow.touch("doc_supply")

    def _publish_demand(self, ctx: _Ctx, dem: dict, status: str, *, t_close: int | None = None) -> str:
        dem["version"] = int(dem["version"]) + 1
        ctx.cow.touch("doc_supply")
        c = self.cat.classes[int(dem["cls"])]
        tn = None
        if dem.get("job"):
            j = ctx.jobs["open"].get(dem["job"])
            tn = j["tail"] if j else None
        return self._rec(
            ctx,
            "SUPPLY_DEMAND",
            dem["demand_no"],
            int(dem["version"]),
            order_id=dem.get("order_id"),
            hints={"expedited": bool(dem.get("expedited"))},
            status=status,
            tail_no=tn,
            base=dem["base"],
            job_no=dem.get("job"),
            demand_no=dem["demand_no"],
            part_no=c.part_no,
            maker=c.maker,
            priority=dem["priority"],
            quantity=1,
            system_code=c.system,
            t_open=int(dem["t_open"]),
            t_close=t_close,
        )

    def _h_supply(self, ctx: _Ctx, d: dict) -> None:
        dems = ctx.cow.doc("doc_supply")["demands"]
        dem = dems.get(d["demand_no"])
        if dem is None or int(dem["tok"]) != int(d["tok"]):
            return
        bi = self.bidx[dem["base"]]
        r = self._new_serial(ctx, int(dem["cls"]), bi, loc=LOC_STOCK)
        del dems[d["demand_no"]]
        self._publish_demand(ctx, dem, "CLOSED", t_close=ctx.t)
        oid = dem.get("order_id")
        if oid and oid in ctx.cow.doc("doc_meta").get("orders", {}):
            self._ord(ctx, oid)["open"] -= 1
            self._order_progress(ctx, oid, "COMPLETED")
        self._stock_arrived(ctx, r)

    def _stock_arrived(self, ctx: _Ctx, r: int, *, keep_surplus: bool = False) -> None:
        """A serviceable unit entered base stock: fill the oldest backorder (AOG first); else keep or return
        surplus above the authorised level to the wholesale pool [ASSUMPTION A-W1.8-17]."""
        bi = int(ctx.cow.a("ser_base")[r])
        ci = int(ctx.cow.a("ser_cls")[r])
        base = self.fleet.bases[bi]
        waiting = [
            (0 if j["grounding"] else 1, int(j["t_awp"]), j["job_no"])
            for j in ctx.jobs["open"].values()
            if j["base"] == base
            and j["status"] == AWP
            and j["step"] == "await_part"
            and j["target"] is not None
            and self.cat.positions[int(j["target"])].cls.index == ci
        ]
        if waiting:
            _, _, jn = min(waiting)
            job = ctx.jobs["open"][jn]
            ctx.cow.w("ser_alloc")[r] = jn
            job["spare"] = r
            job["step"] = "rr_ready"
            ctx.cow.touch("doc_jobs")
            self._request_team(ctx, job)
            self._refresh(ctx, int(job["ti"]))
            return
        authorised = math.ceil(
            self.cat.classes[ci].v("stock_per_ac") * sum(1 for b in self.fleet.tail_base if b == bi) - 1e-9
        )
        if not keep_surplus and self._stock_rows(ctx, bi, ci).size > authorised:
            ctx.cow.w("ser_loc")[r] = LOC_GONE

    # ------------------------------------------------------------------------------------------------ R/R
    def _do_rr(self, ctx: _Ctx, job: dict) -> None:
        ti = int(job["ti"])
        p = int(job["target"])
        new = int(job["spare"])
        old = int(ctx.cow.a("tail_inst")[ti, p])
        tn = self.fleet.tails[ti]
        if old >= 0:
            self._remove(ctx, old, ti, p, job)
        self._install(ctx, new, ti, p, job)
        c = self.cat.positions[p].cls
        sn_off = job.get("removed") or "N/A"
        sn_on = str(ctx.cow.a("ser_no")[new])
        job["installed"] = sn_on
        if job["at"] in (None, "AT-TS"):
            job["at"] = "AT-RR"
        job["ca_text"] = job.get("ca_text") or self._text(
            "corrective", "rr", item=c.name.upper(), task=f"PHX-TASK-{c.code}", sn_off=sn_off, sn_on=sn_on
        )
        self._emit(
            ctx,
            "mx.action",
            self.targets.health,
            {
                "tail": tn,
                "pos": self.cat.positions[p].code,
                "action": "RR",
                "serial": sn_on,
                "job_no": job["job_no"],
            },
        )
        g = self._tail_gen(ctx, ti, SLOT_CHECK)
        self._schedule_step(ctx, job, "check", self._lognormal_s(g, self.cfg.check_s, self.cfg.dur_sigma))

    def _remove(self, ctx: _Ctx, r: int, ti: int, p: int, job: dict, *, to: str = "auto") -> None:
        self._life_record(ctx, r, "REMOVE", ti, job_no=job["job_no"], order_id=job.get("order_id"))
        ctx.cow.w("tail_inst")[ti, p] = -1
        ctx.cow.w("ser_tail")[r] = -1
        ctx.cow.w("ser_pos")[r] = -1
        sn = str(ctx.cow.a("ser_no")[r])
        job["removed"] = sn
        self._emit(
            ctx,
            "cfg.remove",
            self.targets.health,
            {"tail": self.fleet.tails[ti], "pos": self.cat.positions[p].code, "serial": sn},
        )
        if to == "held":
            ctx.cow.w("ser_loc")[r] = LOC_STOCK
            return
        self._to_repair(ctx, r, job, expired=job.get("mal") == "MAL-HT")

    def _install(self, ctx: _Ctx, r: int, ti: int, p: int, job: dict) -> None:
        ctx.cow.w("tail_inst")[ti, p] = r
        ctx.cow.w("ser_loc")[r] = LOC_INSTALLED
        ctx.cow.w("ser_tail")[r] = ti
        ctx.cow.w("ser_pos")[r] = p
        ctx.cow.w("ser_base")[r] = self.fleet.tail_base[ti]
        ctx.cow.w("ser_alloc")[r] = ""
        self._life_record(ctx, r, "INSTALL", ti, job_no=job["job_no"], order_id=job.get("order_id"))
        ctx.cow.w("ser_depot")[r] = 0
        self._emit(
            ctx,
            "cfg.install",
            self.targets.health,
            {
                "tail": self.fleet.tails[ti],
                "pos": self.cat.positions[p].code,
                "serial": str(ctx.cow.a("ser_no")[r]),
                "cls": self.cat.positions[p].cls.code,
            },
        )

    def _to_repair(self, ctx: _Ctx, r: int, job: dict | None, *, expired: bool) -> None:
        c = self.cat.classes[int(ctx.cow.a("ser_cls")[r])]
        if c.consumable:
            ctx.cow.w("ser_loc")[r] = LOC_GONE
            self._replenish(ctx, c.index, self.fleet.bases[int(ctx.cow.a("ser_base")[r])])
            return
        visit = int(ctx.cow.a("ser_visits")[r]) + 1
        ctx.cow.w("ser_visits")[r] = visit
        sn = str(ctx.cow.a("ser_no")[r])
        g = self.stream("serial_shop", serial=sn).generator(visit)
        u = g.random(3)
        z = g.standard_normal(2)
        faulty = int(ctx.cow.a("ser_faults")[r]) > 0
        if expired:
            finding, level = "CONFIRMED", "depot"
        elif faulty and u[0] >= c.v("p_bench_miss"):
            finding = "CONFIRMED"
            level = "depot" if (c.repair_level == "D" or u[1] < c.v("p_bcm")) else "base"
        else:
            finding, level = "RTOK", "base"
        days = c.v("depot_days") if level == "depot" else c.v("shop_days")
        tat = self._lognormal_s_z(days, 0.5, float(z[0] if level == "base" else z[1]))
        ctx.cow.w("ser_loc")[r] = LOC_DEPOT if level == "depot" else LOC_SHOP
        ready = ctx.t + tat * NS
        ctx.cow.w("ser_t_ready")[r] = ready
        condemn = level == "depot" and u[2] < self.cfg.p_condemn
        self._self(
            ctx,
            "m18.shop",
            {
                "row": r,
                "serial": sn,
                "visit": visit,
                "finding": finding,
                "level": level,
                "job_no": job["job_no"] if job else None,
                "condemn": bool(condemn),
                "expired": bool(expired),
            },
            ready,
        )

    def _lognormal_s_z(self, median_s: float, sigma: float, z: float) -> int:
        return max(3600, to_s(median_s * math.exp(sigma * z)))

    def _h_shop(self, ctx: _Ctx, d: dict) -> None:
        r = int(d["row"])
        if str(ctx.cow.a("ser_no")[r]) != d["serial"] or int(ctx.cow.a("ser_visits")[r]) != int(d["visit"]):
            return
        c = self.cat.classes[int(ctx.cow.a("ser_cls")[r])]
        bi = int(ctx.cow.a("ser_base")[r])
        finding = (
            "BCM"
            if (d["finding"] == "CONFIRMED" and d["level"] == "depot" and not d.get("expired"))
            else d["finding"]
        )
        at = {"CONFIRMED": "AT-REP", "RTOK": "AT-BCS", "BCM": "AT-BCM"}[finding]
        self._rec(
            ctx,
            "SHOP_FINDING",
            f"SF-{d['serial']}-{d['visit']}",
            0,
            base=self.fleet.bases[bi],
            job_no=d.get("job_no"),
            part_no=c.part_no,
            serial_no=d["serial"],
            maker=c.maker,
            engine_serial=d["serial"] if c.code == "ENG" else None,
            shop_finding=finding,
            action_taken_code=at,
            when_discovered="WD-SHP",
            system_code=c.system,
            type_maint_code="TM-DEP" if d["level"] == "depot" else "TM-UNS",
            item_hours=float(ctx.cow.a("ser_tsn")[r]) / 3600.0,
            hints={"level": d["level"], "unit_cost": c.v("unit_cost"), "condemn": bool(d.get("condemn"))},
        )
        if d.get("condemn"):
            ctx.cow.w("ser_loc")[r] = LOC_GONE
            self._replenish(ctx, c.index, self.fleet.bases[bi])
            return
        if d["finding"] == "CONFIRMED":
            # repaired or overhauled: truth faults on the unit are cleared
            faults = ctx.cow.doc("doc_faults")
            for fid in sorted(faults):
                if faults[fid]["serial"] == d["serial"] and faults[fid]["active"]:
                    faults[fid]["active"] = False
                    ctx.cow.touch("doc_faults")
            ctx.cow.w("ser_faults")[r] = 0
            if d["level"] == "depot":
                ctx.cow.w("ser_tso")[r] = 0
                ctx.cow.w("ser_depot")[r] = 1
                if d.get("expired"):
                    ctx.cow.w("ser_ldg")[r] = 0
                    ctx.cow.w("ser_strm")[r] = 0
                    ctx.cow.w("ser_t_life0")[r] = ctx.t
            self._emit(ctx, "mx.repaired", self.targets.health, {"serial": d["serial"], "level": d["level"]})
        else:
            ctx.cow.w("ser_rtok")[r] += 1
        ctx.cow.w("ser_loc")[r] = LOC_STOCK
        ctx.cow.w("ser_t_ready")[r] = -1
        self._stock_arrived(ctx, r)

    def _h_transit(self, ctx: _Ctx, d: dict) -> None:
        r = int(d["row"])
        if str(ctx.cow.a("ser_no")[r]) != d["serial"] or int(ctx.cow.a("ser_loc")[r]) != LOC_TRANSIT:
            return
        ctx.cow.w("ser_loc")[r] = LOC_STOCK
        ctx.cow.w("ser_base")[r] = self.bidx[d["to_base"]]
        ctx.cow.w("ser_t_ready")[r] = -1
        self._stock_arrived(ctx, r, keep_surplus=True)  # a deliberate transfer raises the receiving stock

    # ------------------------------------------------------------------------------------------------ closing
    def _close_job(self, ctx: _Ctx, job: dict) -> None:
        job["status"] = CLOSED
        job["step"] = "closed"
        job["tok"] = int(job["tok"]) + 1
        ctx.jobs["open"].pop(job["job_no"], None)
        if job["job_no"] in ctx.jobs["awm"]:
            ctx.jobs["awm"].remove(job["job_no"])
        ctx.cow.touch("doc_jobs")
        self._publish_job(ctx, job, t_close=ctx.t)
        # a fault the job did not remove is still there: the pilot will write it up again (repeat/recurring)
        faults = ctx.cow.doc("doc_faults")
        for _fid, f in sorted(faults.items()):
            if f["active"] and f["reported"]:
                loc = self._fault_at(ctx, f)
                if (
                    loc is not None
                    and loc[0] == int(job["ti"])
                    and (loc[1] in job["suspects"] or loc[1] == job.get("target"))
                ):
                    f["reported"] = False
                    ctx.cow.touch("doc_faults")
        oid = job.get("order_id")
        if oid and oid in ctx.cow.doc("doc_meta").get("orders", {}):
            self._ord(ctx, oid)["open"] -= 1
            self._order_progress(ctx, oid, "COMPLETED")
        res = ctx.cow.doc("doc_res")
        if job["job_no"] in res["busy"][job["base"]]:
            self._release_team(ctx, job)
        if job.get("parent"):
            parent = ctx.jobs["open"].get(job["parent"])
            if parent is not None and parent["step"] == "srv_wait_fix":
                self._srv_end(ctx, parent)
        self._refresh(ctx, int(job["ti"]))

    # ------------------------------------------------------------------------------------------------
    # inspections
    def _uncovered_faults(self, ctx: _Ctx, ti: int, positions: list[int]) -> list[tuple[int, str]]:
        covered = {int(j["target"]) for j in self._tail_jobs(ctx, ti) if j.get("target") is not None}
        covered |= {p for j in self._tail_jobs(ctx, ti) if j["kind"] == "defect" for p in j["suspects"]}
        return [(p, fid) for p, fid in self._active_faults_at(ctx, ti, positions) if p not in covered]

    def _insp_outcome(self, ctx: _Ctx, job: dict) -> None:
        ti = int(job["ti"])
        itype = job.get("inspection_type")
        pod = {"BORESCOPE": self.cfg.pod_borescope, "NDT": self.cfg.pod_ndt}.get(
            itype, self.cfg.pod_conditional
        )
        g = self._tail_gen(ctx, ti, SLOT_OUT)
        found = []
        for p, _fid in self._uncovered_faults(ctx, ti, list(job["suspects"])):
            if g.random() < pod:
                found.append(p)
        if job["kind"] == "cond" and not found and job["suspects"] and g.random() < self.cfg.p_out_of_limits:
            found.append(int(job["suspects"][0]))
        task = itype or "INSPECTION"
        linked = []
        for p in sorted(set(found)):
            c = self.cat.positions[p].cls
            fix = self._new_job(
                ctx,
                ti,
                kind="defect",
                rtype="DEFECT_WO",
                source="inspection",
                wd="WD-CND",  # conditional or special (order) inspection; servicing finds use WD-SCH
                tm="TM-SPI",
                grounding=True,
                scheduled=job["kind"] != "cond",
                target=p,
                mal="MAL-INS",
                text=self._text(
                    "discrepancy", "inspection", item=c.name.upper(), symptom="OUT OF LIMITS", task=task
                ),
                order_id=None,
                evidence=list(job["evidence"]),
            )
            fix["linked"] = job["job_no"]
            linked.append(fix["job_no"])
            self._request_team(ctx, fix)
        job["at"] = "AT-INSP"
        job["linked"] = linked[0] if linked else None
        job["ca_text"] = (
            self._text(
                "corrective",
                "inspect_found",
                task=task,
                item=self.cat.positions[found[0]].cls.name.upper(),
                linked=linked[0],
            )
            if linked
            else self._text("corrective", "inspect_ok", task=task)
        )
        self._close_job(ctx, job)

    # ------------------------------------------------------------------------------------------------
    # servicing
    def _servicing_job(self, ctx: _Ctx, ti: int, k: int, *, order_id: str | None = None) -> dict | None:
        for j in self._tail_jobs(ctx, ti):
            if j["kind"] == "srv":
                return None
        itype = self.codes.servicing_order[k]
        job = self._new_job(
            ctx,
            ti,
            kind="srv",
            rtype="INSPECTION",
            source="schedule",
            wd="WD-SCH",
            tm="TM-DEP" if k == ROH else "TM-SCH",
            grounding=True,
            scheduled=True,
            mal="MAL-NONE",
            text=f"{itype} DUE.",
            order_id=order_id,
            extra={"inspection_type": itype, "srv_k": k},
        )
        job["part_no"] = None
        if k == ROH:
            self._start_srv(ctx, job)
        else:
            res = ctx.cow.doc("doc_res")
            if len(res["slots"][job["base"]]) < self.cfg.slots and not int(ctx.cow.a("tail_flying")[ti]):
                self._start_srv(ctx, job)
            else:
                res["slotq"][job["base"]].append(job["job_no"])
                ctx.cow.touch("doc_res")
                job["status"] = AWM
                self._publish_job(ctx, job)
        return job

    def _start_srv(self, ctx: _Ctx, job: dict) -> None:
        ti = int(job["ti"])
        k = int(job["srv_k"])
        res = ctx.cow.doc("doc_res")
        if k != ROH:
            res["slots"][job["base"]].append(job["job_no"])
            ctx.cow.touch("doc_res")
        else:
            ctx.cow.w("tail_depot")[ti] = 1
        job["status"] = IN_WORK
        g = self._tail_gen(ctx, ti, SLOT_SRV)
        dur = (
            self.cfg.srv_duration_s[k]
            * self.cfg.srv_median_factor
            * math.exp(self.cfg.srv_sigma * float(g.standard_normal()))
        )
        self._publish_job(ctx, job)
        if job.get("order_id"):
            self._order_progress(ctx, job["order_id"], "IN_WORK")
        self._schedule_step(ctx, job, "srv", max(3600, to_s(dur)), calendar_time=True, mh=False)
        job["t_srv0"] = ctx.t
        # look phase: inspect the items this servicing covers
        itype = job["inspection_type"]
        positions = [p.index for p in self.cat.positions if itype in p.cls.inspectable_by]
        pod = self.cfg.srv_pod[k]
        for p, _fid in self._uncovered_faults(ctx, ti, positions):
            if g.random() < pod:
                c = self.cat.positions[p].cls
                fix = self._new_job(
                    ctx,
                    ti,
                    kind="defect",
                    rtype="DEFECT_WO",
                    source="inspection",
                    wd="WD-SCH",
                    tm="TM-SCH",
                    grounding=True,
                    scheduled=True,
                    target=p,
                    mal="MAL-INS",
                    text=self._text(
                        "discrepancy", "inspection", item=c.name.upper(), symptom="DEFECTIVE", task=itype
                    ),
                )
                fix["parent"] = job["job_no"]
                fix["linked"] = job["job_no"]
                job["children"].append(fix["job_no"])
                ctx.cow.touch("doc_jobs")
                if k != ROH:
                    self._request_team(ctx, fix)
                else:
                    fix["status"], fix["step"] = IN_WORK, "depot"
                    # at depot the fix is part of the R&O package (no base team)
        self._refresh(ctx, ti)

    def _srv_end(self, ctx: _Ctx, job: dict) -> None:
        ti = int(job["ti"])
        k = int(job["srv_k"])
        open_children = [c for c in job["children"] if c in ctx.jobs["open"]]
        if k == ROH:
            for cj in open_children:  # depot fixes complete with the R&O
                child = ctx.jobs["open"][cj]
                p = int(child["target"])
                r = int(ctx.cow.a("tail_inst")[ti, p])
                if r >= 0:
                    self._clear_serial_faults(ctx, r)
                child["at"], child["ca_text"] = "AT-REP", "REPAIRED AT DEPOT DURING R&O."
                self._close_job(ctx, child)
            open_children = []
        if open_children:
            job["step"] = "srv_wait_fix"
            ctx.cow.touch("doc_jobs")
            return
        for kk in range(k + 1):
            ctx.cow.w("srv_fh")[ti, kk] = 0
            ctx.cow.w("srv_last")[ti, kk] = ctx.t
            ctx.cow.w("srv_ext_fh")[ti, kk] = 0
            ctx.cow.w("srv_ext_s")[ti, kk] = 0
        res = ctx.cow.doc("doc_res")
        if job["job_no"] in res["slots"][job["base"]]:
            res["slots"][job["base"]].remove(job["job_no"])
            ctx.cow.touch("doc_res")
        if k == ROH:
            ctx.cow.w("tail_depot")[ti] = 0
        if k != ROH:  # depot R&O man-hours are HAL's, not the squadron's
            job["mh"] = (
                float(job["mh"])
                + self.work.working_seconds(int(job["t_srv0"]), ctx.t) / 3600.0 * self.cfg.crew
            )
        job["at"] = "AT-SVC"
        job["ca_text"] = self._text("corrective", "service", task=job["inspection_type"])
        self._close_job(ctx, job)
        self._next_slot(ctx, job["base"])
        self._dispatch(ctx, self.fleet.tail_base[ti])

    def _clear_serial_faults(self, ctx: _Ctx, r: int) -> None:
        sn = str(ctx.cow.a("ser_no")[r])
        faults = ctx.cow.doc("doc_faults")
        for fid in sorted(faults):
            if faults[fid]["serial"] == sn and faults[fid]["active"]:
                faults[fid]["active"] = False
                ctx.cow.touch("doc_faults")
        ctx.cow.w("ser_faults")[r] = 0
        self._emit(ctx, "mx.repaired", self.targets.health, {"serial": sn, "level": "depot"})

    def _next_slot(self, ctx: _Ctx, base: str) -> None:
        res = ctx.cow.doc("doc_res")
        while len(res["slots"][base]) < self.cfg.slots and res["slotq"][base]:
            startable = [
                jn
                for jn in res["slotq"][base]
                if jn in ctx.jobs["open"]
                and not int(ctx.cow.a("tail_flying")[int(ctx.jobs["open"][jn]["ti"])])
            ]
            if not startable:
                return
            jn = startable[0]
            res["slotq"][base].remove(jn)
            ctx.cow.touch("doc_res")
            self._start_srv(ctx, ctx.jobs["open"][jn])

    # ------------------------------------------------------------------------------------------------ CANN
    def fleet_view(self, ctx: _Ctx) -> FleetView:
        """Tech-log knowledge for the status-quo rules (no hidden truth)."""
        tails = {}
        cls_pn = [c.part_no for c in self.cat.classes]
        for ti, tn in enumerate(self.fleet.tails):
            inst = ctx.cow.a("tail_inst")[ti]
            counts: dict[str, int] = {}
            for p, r in enumerate(inst.tolist()):
                if r >= 0:
                    pn = cls_pn[int(self.pos_cls[p])]
                    counts[pn] = counts.get(pn, 0) + 1
            open_pn = frozenset(
                j["part_no"]
                for j in self._tail_jobs(ctx, ti)
                if j["part_no"] and j["kind"] in ("defect", "cond")
            )
            tails[tn] = TailView(
                tail_no=tn,
                base=self.fleet.bases[self.fleet.tail_base[ti]],
                state=int(ctx.cow.a("av_cur")[ti]),
                nmc_since=int(ctx.cow.a("av_nmc_since")[ti]),
                installed=counts,
                open_part_nos=open_pn,
            )
        awp = [
            AwpJob(j["job_no"], j["tail"], j["base"], j["part_no"], self.abs_ns(int(j["t_awp"])))
            for j in ctx.jobs["open"].values()
            if j["status"] == AWP and j["grounding"] and j["kind"] == "defect" and j["part_no"]
        ]
        return FleetView(self.abs_ns(ctx.t), tails, sorted(awp, key=lambda a: a.job_no))

    def _cann(
        self, ctx: _Ctx, recipient_job_no: str, donor_tail: str, *, order_id: str | None = None
    ) -> str | None:
        """Start a cannibalisation; returns a rejection reason or None."""
        job = ctx.jobs["open"].get(recipient_job_no)
        if job is None or job["status"] != AWP or job.get("target") is None:
            return f"job {recipient_job_no} is not awaiting parts"
        if donor_tail not in self.tidx or donor_tail == job["tail"]:
            return f"invalid donor {donor_tail}"
        di = self.tidx[donor_tail]
        if self.fleet.tail_base[di] != self.bidx[job["base"]]:
            return "donor at another base"
        if int(ctx.cow.a("tail_flying")[di]) or int(ctx.cow.a("tail_depot")[di]):
            return "donor not available"
        ci = self.cat.positions[int(job["target"])].cls.index
        pn = self.cat.classes[ci].part_no
        if any(j["part_no"] == pn for j in self._tail_jobs(ctx, di) if j["kind"] in ("defect", "cond")):
            return "donor item has an open defect"
        dpos = [
            p
            for p in range(self.n_pos)
            if int(self.pos_cls[p]) == ci and int(ctx.cow.a("tail_inst")[di, p]) >= 0
        ]
        if not dpos:
            return "donor has no such item installed"
        dp = dpos[0]
        cj = self._new_job(
            ctx,
            di,
            kind="cann",
            rtype="CANNIBALISATION",
            source="cann",
            wd="WD-ANL" if order_id else "WD-SCH",
            tm="TM-UNS",
            grounding=True,
            scheduled=False,
            target=dp,
            mal="MAL-CN",
            order_id=order_id,
            text=f"CANN {self.cat.classes[ci].name.upper()} FOR {job['tail']} ({job['job_no']}).",
            extra={"cann_cls": ci, "recipient": job["job_no"], "donor": donor_tail},
            prefix="CN-",
        )
        cj["linked"] = job["job_no"]
        job["linked"] = cj["job_no"]
        job["status"], job["step"] = IN_WORK, "cann_wait"
        ctx.cow.touch("doc_jobs")
        self._publish_job(ctx, job)
        if order_id is not None:
            self._order_progress(ctx, order_id, "QUEUED")
        self._request_team(ctx, cj)
        self._refresh(ctx, di)
        self._refresh(ctx, int(job["ti"]))
        return None

    def _do_cann(self, ctx: _Ctx, cj: dict) -> None:
        di = int(cj["ti"])
        dp = int(cj["target"])
        job = ctx.jobs["open"].get(cj["recipient"])
        r = int(ctx.cow.a("tail_inst")[di, dp])
        if job is None or r < 0:
            cj["at"], cj["ca_text"] = "AT-CNR", "CANN CANCELLED."
            self._close_job(ctx, cj)
            return
        ti = int(job["ti"])
        sn = str(ctx.cow.a("ser_no")[r])
        # remove from donor (held for the recipient)
        self._remove(ctx, r, di, dp, cj, to="held")
        ctx.cow.w("ser_alloc")[r] = job["job_no"]
        ctx.cow.w("ser_base")[r] = self.fleet.tail_base[ti]
        cj["at"] = "AT-CNR"
        cj["ca_text"] = self._text(
            "corrective",
            "cann_out",
            item=self.cat.positions[dp].cls.name.upper(),
            sn_off=sn,
            recipient=job["tail"],
        )
        # the donor now waits for the part: it takes over the recipient's demand
        back = self._new_job(
            ctx,
            di,
            kind="defect",
            rtype="DEFECT_WO",
            source="cann",
            wd="WD-ANL",
            tm="TM-UNS",
            grounding=True,
            scheduled=False,
            target=dp,
            mal="MAL-CN",
            text=f"REPLACE {self.cat.positions[dp].cls.name.upper()} CANNIBALIZED FOR {job['tail']}.",
        )
        back["linked"] = cj["job_no"]
        dn = job.get("demand")
        if dn is not None and dn in ctx.cow.doc("doc_supply")["demands"]:
            dem = ctx.cow.doc("doc_supply")["demands"][dn]
            dem["job"] = back["job_no"]
            back["demand"] = dn
            job["demand"] = None
            ctx.cow.touch("doc_supply")
            self._publish_demand(ctx, dem, "OPEN")
        back["status"], back["step"], back["t_awp"] = AWP, "await_part", ctx.t
        ctx.cow.touch("doc_jobs")
        self._publish_job(ctx, back)
        self._rec(
            ctx,
            "CANNIBALISATION",
            f"{job['job_no']}-CN",
            0,
            tail_no=job["tail"],
            base=job["base"],
            job_no=job["job_no"],
            linked_job_no=cj["job_no"],
            donor_tail_no=cj["tail"],
            part_no=job["part_no"],
            serial_no=sn,
            action_taken_code="AT-CNI",
            malfunction_code="MAL-CN",
            type_maint_code="TM-UNS",
            corrective_action_text=self._text(
                "corrective",
                "cann_in",
                item=self.cat.positions[dp].cls.name.upper(),
                sn_on=sn,
                donor=cj["tail"],
            ),
            order_id=cj.get("order_id"),
            t_open=int(cj["t_open"]),
            t_close=ctx.t,
        )
        self._close_job(ctx, cj)
        # install into the recipient (removes its failed unit), then ops check
        job["spare"] = r
        job["donor"] = cj["tail"]
        self._do_rr(ctx, job)
        job["at"] = "AT-CNI"
        ctx.cow.touch("doc_jobs")
        self._refresh(ctx, di)

    # ------------------------------------------------------------------------------------------------ review
    def _h_review(self, ctx: _Ctx, d: dict) -> None:
        meta = ctx.cow.doc("doc_meta")
        if int(meta.get("review_next", -1)) != ctx.t:
            return
        if self.internal.cann:
            for jn, donor in cann_plan(self.fleet_view(ctx), self.cfg.cann_min_awp_s * NS):
                self._cann(ctx, jn, donor)
        for ti in range(len(self.fleet.tails)):
            if int(ctx.cow.a("tail_flying")[ti]) or int(ctx.cow.a("tail_depot")[ti]):
                continue
            self._servicing_due(ctx, ti)
            self._hard_time_due(ctx, ti)
            self._refresh(ctx, ti)
        self._schedule_review(ctx)

    def servicing_due(
        self, srv_fh: np.ndarray, srv_last: np.ndarray, ext_fh: np.ndarray, ext_s: np.ndarray, t: int
    ) -> int:
        """Highest servicing type due (-1 none): FH or calendar, whichever comes first (plus approved
        extensions)."""
        due = -1
        for k in range(self.cfg.n_servicing):
            if (
                srv_fh[k] >= self.cfg.srv_interval_fh_s[k] + ext_fh[k]
                or t - srv_last[k] >= (self.cfg.srv_interval_s[k] + ext_s[k]) * NS
            ):
                due = k
        return due

    def _servicing_due(self, ctx: _Ctx, ti: int) -> None:
        k = self.servicing_due(
            ctx.cow.a("srv_fh")[ti],
            ctx.cow.a("srv_last")[ti],
            ctx.cow.a("srv_ext_fh")[ti],
            ctx.cow.a("srv_ext_s")[ti],
            ctx.t,
        )
        if k >= 0:
            self._servicing_job(ctx, ti, k)

    def life_expired(self, ctx: _Ctx, r: int) -> str | None:
        c = self.cat.classes[int(ctx.cow.a("ser_cls")[r])]
        if c.v("life_fh") > 0 and int(ctx.cow.a("ser_tso")[r]) >= c.v("life_fh"):
            return f"{c.v('life_fh') / 3600:.0f} FH"
        if c.v("life_landings") > 0 and int(ctx.cow.a("ser_ldg")[r]) >= c.v("life_landings"):
            return f"{c.v('life_landings'):.0f} LDG"
        if c.v("life_streams") > 0 and int(ctx.cow.a("ser_strm")[r]) >= c.v("life_streams"):
            return f"{c.v('life_streams'):.0f} STREAMINGS"
        if c.v("life_years") > 0 and ctx.t - int(ctx.cow.a("ser_t_life0")[r]) >= c.v("life_years") * NS:
            return f"{c.v('life_years') / (365.25 * DAY_S):.0f} YR"
        return None

    def _hard_time_due(self, ctx: _Ctx, ti: int) -> None:
        busy = {int(j["target"]) for j in self._tail_jobs(ctx, ti) if j.get("target") is not None}
        for p in range(self.n_pos):
            r = int(ctx.cow.a("tail_inst")[ti, p])
            if r < 0 or p in busy:
                continue
            lim = self.life_expired(ctx, r)
            if lim is None:
                continue
            c = self.cat.positions[p].cls
            job = self._new_job(
                ctx,
                ti,
                kind="defect",
                rtype="DEFECT_WO",
                source="hard_time",
                wd="WD-SCH",
                tm="TM-SCH",
                grounding=True,
                scheduled=True,
                target=p,
                mal="MAL-HT",
                text=self._text("discrepancy", "hard_time", item=c.name.upper(), limit=lim),
            )
            self._request_team(ctx, job)

    # ================================================================================================ orders
    def _facts(self, ctx: _Ctx, ti: int) -> TechLogFacts:
        return TechLogFacts(
            tail_no=self.fleet.tails[ti],
            mission_capable=self._mission_capable(ctx, ti),
            open_grounding_jobs=tuple(
                sorted(j["job_no"] for j in self._tail_jobs(ctx, ti) if j["grounding"])
            ),
            on_hold=bool(ctx.cow.a("tail_hold")[ti]),
        )

    def _tails_of(self, row: Mapping[str, Any]) -> list[int]:
        if row.get("target_tail_no"):
            return [self.tidx[row["target_tail_no"]]] if row["target_tail_no"] in self.tidx else []
        if row.get("target_base") in self.bidx:
            bi = self.bidx[row["target_base"]]
            return [i for i, b in enumerate(self.fleet.tail_base) if b == bi]
        return []

    def _h_order_exec(self, ctx: _Ctx, d: dict) -> None:
        row = d["order"]
        oid = row["order_id"]
        action = row["action"]
        prm = row.get("parameters") or {}
        handler = getattr(self, f"_o_{action.lower()}", None)
        reason: str | None
        if handler is None:
            reason = f"action {action} not supported by M18"
        else:
            reason = handler(ctx, row, prm)
        if reason is not None:
            self._order_progress(ctx, oid, "REJECTED", reason)
        for ti in range(len(self.fleet.tails)):
            self._refresh(ctx, ti)

    def _tail_or_reject(self, row) -> tuple[int | None, str | None]:
        tn = row.get("target_tail_no")
        if tn not in self.tidx:
            return None, f"unknown tail {tn}"
        return self.tidx[tn], None

    def _order_job(self, ctx, row, ti, **kw) -> dict:
        job = self._new_job(ctx, ti, order_id=row["order_id"], **kw)
        self._order_progress(ctx, row["order_id"], "QUEUED")
        return job

    def _pos_or_none(self, code: str | None) -> int | None:
        if code is None or code not in self.cat.pos_by_code:
            return None
        return self.cat.pos(code).index

    def _o_inspect(self, ctx, row, prm) -> str | None:
        ti, err = self._tail_or_reject(row)
        if err:
            return err
        itype = {"BORESCOPE": "BORESCOPE", "NDT": "NDT", "CONDITIONAL": "COND-ENGINE"}[prm["type"]]
        if prm.get("position") is not None:
            p = self._pos_or_none(prm["position"])
            if p is None:
                return f"unknown position {prm['position']}"
            targets = [p]
        else:
            targets = [p.index for p in self.cat.positions if itype in p.cls.inspectable_by] or [
                self.cat.pos("ENG").index
            ]
        job = self._order_job(
            ctx,
            row,
            ti,
            kind="inspect",
            rtype="INSPECTION",
            source="order",
            wd="WD-ANL",
            tm="TM-PRD",
            grounding=True,
            scheduled=True,
            suspects=targets,
            mal="MAL-NONE",
            text=self._text("discrepancy", "order", action=itype, order=row["order_id"]),
            extra={"inspection_type": itype},
        )
        job["part_no"] = None
        self._request_team(ctx, job)
        return None

    def _o_troubleshoot(self, ctx, row, prm) -> str | None:
        ti, err = self._tail_or_reject(row)
        if err:
            return err
        if prm.get("position") is not None:
            p = self._pos_or_none(prm["position"])
            if p is None:
                return f"unknown position {prm['position']}"
            suspects = list(self.cat.ambiguity_group(p))
        else:
            suspects = self._suspect_positions({"event_code": prm["code"]})
        existing = self._match_job(ctx, ti, suspects, prm.get("code"))
        if existing is not None and existing["step"] == "monitor":
            existing["order_id"] = row["order_id"]
            self._ord(ctx, row["order_id"])["open"] += 1
            self._order_progress(ctx, row["order_id"], "QUEUED")
            self._escalate(ctx, existing, repeat=False)
            return None
        job = self._order_job(
            ctx,
            row,
            ti,
            kind="defect",
            rtype="DEFECT_WO",
            source="order",
            wd="WD-ANL",
            tm="TM-PRD",
            grounding=any(self.cat.positions[p].cls.grounding for p in suspects[:1]),
            scheduled=False,
            suspects=suspects,
            code=prm.get("code"),
            mal="MAL-BIT",
            text=self._text("discrepancy", "order", action="TROUBLESHOOT", order=row["order_id"]),
        )
        self._request_team(ctx, job)
        return None

    def _o_remove_replace(self, ctx, row, prm) -> str | None:
        ti, err = self._tail_or_reject(row)
        if err:
            return err
        p = self._pos_or_none(prm["position"])
        if p is None:
            return f"unknown position {prm['position']}"
        if any(j.get("target") == p for j in self._tail_jobs(ctx, ti)):
            return "position already has an open job"
        job = self._order_job(
            ctx,
            row,
            ti,
            kind="defect",
            rtype="DEFECT_WO",
            source="order",
            wd="WD-ANL",
            tm="TM-PRD",
            grounding=True,
            scheduled=True,
            target=p,
            mal="MAL-NONE",
            text=self._text("discrepancy", "order", action="R/R", order=row["order_id"]),
        )
        if prm.get("install_serial"):
            r = self._serial_row(ctx, prm["install_serial"])
            if (
                r < 0
                or int(ctx.cow.a("ser_loc")[r]) != LOC_STOCK
                or str(ctx.cow.a("ser_alloc")[r])
                or int(ctx.cow.a("ser_cls")[r]) != self.cat.positions[p].cls.index
                or int(ctx.cow.a("ser_base")[r]) != self.fleet.tail_base[ti]
            ):
                ctx.jobs["open"].pop(job["job_no"])
                ctx.cow.touch("doc_jobs")
                job["status"] = CLOSED
                self._publish_job(ctx, job, t_close=ctx.t)
                return f"serial {prm['install_serial']} is not a serviceable unallocated spare at the base"
            ctx.cow.w("ser_alloc")[r] = job["job_no"]
            job["spare"] = r
            job["step"] = "rr_ready"
        self._request_team(ctx, job)
        return None

    def _o_wash_service(self, ctx, row, prm) -> str | None:
        ti, err = self._tail_or_reject(row)
        if err:
            return err
        kind = "wash" if prm["type"] == "ENGINE_WASH" else "service"
        job = self._order_job(
            ctx,
            row,
            ti,
            kind=kind,
            rtype="INSPECTION",
            source="order",
            wd="WD-ANL",
            tm="TM-SVC",
            grounding=True,
            scheduled=True,
            mal="MAL-NONE",
            suspects=[self.cat.pos("ENG").index] if kind == "wash" else [],
            text=self._text("discrepancy", "order", action=prm["type"], order=row["order_id"]),
            extra={"inspection_type": "WASH" if kind == "wash" else "SERVICING", "svc": prm["type"]},
        )
        job["part_no"] = None
        self._request_team(ctx, job)
        return None

    def _work_done(self, ctx: _Ctx, job: dict) -> None:
        ti = int(job["ti"])
        tn = self.fleet.tails[ti]
        kind = job["kind"]
        if kind in ("wash", "service"):
            self._emit(
                ctx,
                "mx.action",
                self.targets.health,
                {
                    "tail": tn,
                    "pos": "ENG" if kind == "wash" else None,
                    "action": job.get("svc", "WASH"),
                    "job_no": job["job_no"],
                },
            )
            job["at"], job["ca_text"] = (
                "AT-SVC",
                self._text("corrective", "service", task=job["inspection_type"]),
            )
        elif kind == "mod":
            td = ctx.cow.doc("doc_tails")[tn]
            if job["mod_id"] not in td["mods"]:
                td["mods"] = sorted([*td["mods"], job["mod_id"]])
                ctx.cow.touch("doc_tails")
            job["compliance"] = "COMPLIED"
            job["at"], job["ca_text"] = "AT-MOD", self._text("corrective", "mod", task=job["mod_id"])
            self._emit(
                ctx,
                "mx.action",
                self.targets.health,
                {"tail": tn, "action": "MOD", "mod_id": job["mod_id"], "job_no": job["job_no"]},
            )
        elif kind == "sw":
            td = ctx.cow.doc("doc_tails")[tn]
            td["sw"] = job["sw_id"]
            ctx.cow.touch("doc_tails")
            job["compliance"] = "COMPLIED"
            job["at"], job["ca_text"] = "AT-SW", self._text("corrective", "sw", sw=job["sw_id"])
            for target in (self.targets.health, self.targets.monitoring):
                self._emit(
                    ctx,
                    "mx.action",
                    target,
                    {"tail": tn, "action": "SWLOAD", "sw_config_id": job["sw_id"], "job_no": job["job_no"]},
                )
        job["corrected_by"] = self._tech(ctx, 1 + int(job["tok"]) % 40)
        self._close_job(ctx, job)

    def _o_defer(self, ctx, row, prm) -> str | None:
        job = ctx.jobs["open"].get(prm["job_no"])
        if job is None:
            return f"no open job {prm['job_no']}"
        if job["grounding"]:
            return "a grounding defect cannot be deferred"
        if job["status"] == IN_WORK:
            return "job is in work"
        if job["job_no"] in ctx.jobs["awm"]:
            ctx.jobs["awm"].remove(job["job_no"])
        job["status"], job["step"], job["at"] = DEFERRED, "deferred", "AT-DEF"
        job["tok"] = int(job["tok"]) + 1
        job["order_id"] = row["order_id"]
        job["ca_text"] = self._text("corrective", "deferred", order=row["order_id"], limits=prm["limits"])
        ctx.cow.touch("doc_jobs")
        self._publish_job(ctx, job)
        td = ctx.cow.doc("doc_tails")[job["tail"]]
        td["limits"] = sorted({*td["limits"], prm["limits"]})
        ctx.cow.touch("doc_tails")
        self._self(
            ctx,
            "m18.defer_expiry",
            {"job_no": job["job_no"], "tok": job["tok"], "limits": prm["limits"]},
            ctx.t + to_s(float(prm["expiry_hours"]) * 3600.0) * NS,
        )
        self._order_progress(ctx, row["order_id"], "COMPLETED")
        return None

    def _h_defer_expiry(self, ctx: _Ctx, d: dict) -> None:
        job = ctx.jobs["open"].get(d["job_no"])
        if job is None or int(job["tok"]) != int(d["tok"]) or job["status"] != DEFERRED:
            return
        td = ctx.cow.doc("doc_tails")[job["tail"]]
        td["limits"] = [x for x in td["limits"] if x != d["limits"]]
        ctx.cow.touch("doc_tails")
        job["status"], job["step"], job["order_id"] = OPEN, "new", None
        self._publish_job(ctx, job)
        self._request_team(ctx, job)
        self._refresh(ctx, int(job["ti"]))

    def _o_cannibalise(self, ctx, row, prm) -> str | None:
        return self._cann(ctx, prm["job_no"], prm["donor_tail_no"], order_id=row["order_id"])

    def _class_by_pn(self, pn: str):
        return self.cls_by_pn.get(pn)

    def _o_requisition_spares(self, ctx, row, prm) -> str | None:
        c = self._class_by_pn(prm["part_no"])
        if c is None or row.get("target_base") not in self.bidx:
            return "unknown part number or base"
        prio = row["priority"] if row["priority"] in ("AOG", "MCM", "PHU") else "PHU"
        for _ in range(int(prm["quantity"])):
            self._raise_demand(ctx, None, c.index, prio, base=row["target_base"], order_id=row["order_id"])
        self._order_progress(ctx, row["order_id"], "QUEUED")
        return None

    def _o_expedite_spares(self, ctx, row, prm) -> str | None:
        dems = ctx.cow.doc("doc_supply")["demands"]
        dem = dems.get(prm["demand_no"])
        if dem is None:
            return f"no open demand {prm['demand_no']}"
        if dem["expedited"]:
            return "already expedited"
        remain = max(0, int(dem["eta"]) - ctx.t)
        dem["eta"] = ctx.t + (to_s(remain / NS * self.cfg.expedite_factor)) * NS
        dem["expedited"] = True
        dem["tok"] = int(dem["tok"]) + 1
        ctx.cow.touch("doc_supply")
        self._ord(ctx, row["order_id"])
        rid = self._publish_demand(ctx, dem, "OPEN")
        self._ord(ctx, row["order_id"])["recs"].append(rid)
        self._self(ctx, "m18.supply", {"demand_no": dem["demand_no"], "tok": dem["tok"]}, int(dem["eta"]))
        self._order_progress(ctx, row["order_id"], "COMPLETED")
        return None

    def _o_transfer_stock(self, ctx, row, prm) -> str | None:
        c = self._class_by_pn(prm["part_no"])
        if c is None or prm["from_base"] not in self.bidx or prm["to_base"] not in self.bidx:
            return "unknown part number or base"
        rows = self._stock_rows(ctx, self.bidx[prm["from_base"]], c.index)
        if rows.size < int(prm["quantity"]):
            return f"only {rows.size} serviceable in stock at {prm['from_base']}"
        for r in rows[: int(prm["quantity"])].tolist():
            ctx.cow.w("ser_loc")[r] = LOC_TRANSIT
            ctx.cow.w("ser_t_ready")[r] = ctx.t + self.cfg.transfer_s * NS
            self._self(
                ctx,
                "m18.transit",
                {"row": r, "serial": str(ctx.cow.a("ser_no")[r]), "to_base": prm["to_base"]},
                ctx.t + self.cfg.transfer_s * NS,
            )
        self._order_progress(ctx, row["order_id"], "COMPLETED")
        return None

    def _o_ground(self, ctx, row, prm) -> str | None:
        tails = self._tails_of(row)
        if not tails:
            return "no target tail"
        for ti in tails:
            ctx.cow.w("tail_hold")[ti] = 1
            td = ctx.cow.doc("doc_tails")[self.fleet.tails[ti]]
            td["hold_order"] = row["order_id"]
            ctx.cow.touch("doc_tails")
            self._refresh(ctx, ti)
        self._order_progress(ctx, row["order_id"], "COMPLETED")
        return None

    def _o_release(self, ctx, row, prm) -> str | None:
        tails = self._tails_of(row)
        if not tails:
            return "no target tail"
        reasons = []
        for ti in tails:
            r = airworthiness("RELEASE", self._facts(ctx, ti), prm)
            if r is not None:
                reasons.append(f"{self.fleet.tails[ti]}: {r}")
                continue
            ctx.cow.w("tail_hold")[ti] = 0
            self._refresh(ctx, ti)
        if reasons and len(reasons) == len(tails):
            return "; ".join(reasons)
        self._order_progress(ctx, row["order_id"], "COMPLETED", "; ".join(reasons) or None)
        return None

    def _o_bring_forward_servicing(self, ctx, row, prm) -> str | None:
        ti, err = self._tail_or_reject(row)
        if err:
            return err
        k = self.codes.servicing_order.index(prm["servicing"])
        job = self._servicing_job(ctx, ti, k, order_id=row["order_id"])
        if job is None:
            return "a servicing is already in progress"
        self._order_progress(ctx, row["order_id"], "QUEUED")
        return None

    def _o_defer_servicing(self, ctx, row, prm) -> str | None:
        ti, err = self._tail_or_reject(row)
        if err:
            return err
        k = self.codes.servicing_order.index(prm["servicing"])
        frac = 0.2 if prm.get("max_fraction") is None else float(prm["max_fraction"])
        if prm.get("extend_hours"):
            ext = to_s(float(prm["extend_hours"]) * 3600.0)
            if ext > frac * self.cfg.srv_interval_fh_s[k]:
                return f"extension exceeds {frac:.0%} of the interval"
            ctx.cow.w("srv_ext_fh")[ti, k] += ext
        if prm.get("extend_days"):
            ext = to_s(float(prm["extend_days"]) * DAY_S)
            if ext > frac * self.cfg.srv_interval_s[k]:
                return f"extension exceeds {frac:.0%} of the interval"
            ctx.cow.w("srv_ext_s")[ti, k] += ext
        self._order_progress(ctx, row["order_id"], "COMPLETED")
        return None

    def _o_assign_sortie(self, ctx, row, prm) -> str | None:
        ti, err = self._tail_or_reject(row)
        if err:
            return err
        r = airworthiness("ASSIGN_SORTIE", self._facts(ctx, ti), prm)
        if r is not None:
            return r
        if self.targets.scenario is None:
            return "no scenario module to assign sorties"
        self._emit(
            ctx,
            "ops.assign",
            self.targets.scenario,
            {"tail_no": row["target_tail_no"], **prm, "order_id": row["order_id"]},
        )
        self._order_progress(ctx, row["order_id"], "COMPLETED")
        return None

    def _o_restrict_usage(self, ctx, row, prm) -> str | None:
        ti, err = self._tail_or_reject(row)
        if err:
            return err
        tn = self.fleet.tails[ti]
        td = ctx.cow.doc("doc_tails")[tn]
        if prm["limit"] == "NONE":
            td["restrict"] = {}
        else:
            td["restrict"] = {
                "limit": prm["limit"],
                "value": prm.get("value"),
                "until": None
                if prm.get("until_days") is None
                else ctx.t + to_s(float(prm["until_days"]) * DAY_S) * NS,
            }
        ctx.cow.touch("doc_tails")
        self._emit(ctx, "ops.restrict", self.targets.scenario, {"tail_no": tn, **prm})
        self._order_progress(ctx, row["order_id"], "COMPLETED")
        return None

    def _o_embody_modification(self, ctx, row, prm) -> str | None:
        tails = self._tails_of(row)
        if not tails:
            return "no target tail"
        for ti in tails:
            if prm["mod_id"] in ctx.cow.doc("doc_tails")[self.fleet.tails[ti]]["mods"]:
                continue
            job = self._new_job(
                ctx,
                ti,
                kind="mod",
                rtype="MODIFICATION",
                source="order",
                wd="WD-ANL",
                tm="TM-MOD",
                grounding=True,
                scheduled=True,
                mal="MAL-NONE",
                order_id=row["order_id"],
                text=self._text(
                    "discrepancy", "order", action=f"EMBODY {prm['mod_id']}", order=row["order_id"]
                ),
                extra={"mod_id": prm["mod_id"], "compliance": "ISSUED"},
            )
            job["part_no"] = None
            self._request_team(ctx, job)
        self._order_progress(ctx, row["order_id"], "QUEUED")
        return None

    def _o_load_software(self, ctx, row, prm) -> str | None:
        tails = self._tails_of(row)
        if not tails:
            return "no target tail"
        for ti in tails:
            job = self._new_job(
                ctx,
                ti,
                kind="sw",
                rtype="MODIFICATION",
                source="order",
                wd="WD-ANL",
                tm="TM-MOD",
                grounding=True,
                scheduled=True,
                mal="MAL-NONE",
                order_id=row["order_id"],
                text=self._text(
                    "discrepancy", "order", action=f"LOAD {prm['sw_config_id']}", order=row["order_id"]
                ),
                extra={"sw_id": prm["sw_config_id"], "compliance": "ISSUED"},
            )
            job["part_no"] = None
            self._request_team(ctx, job)
        self._order_progress(ctx, row["order_id"], "QUEUED")
        return None

    # ================================================================================================ belief
    # forks
    def belief_known_faults(self, state: State) -> set[str]:
        """Truth faults the maintenance organisation knows about: written up, or on a position under an open
        defect (the rest are what a belief fork must not assume, M22)."""
        ctx = _Ctx(self, Cow(state), int(state["t_last"]))
        keep: set[str] = set()
        for fid, f in sorted(ctx.cow.doc("doc_faults").items()):
            if not f["active"]:
                continue
            loc = self._fault_at(ctx, f)
            if f["reported"]:
                keep.add(fid)
            elif loc is not None and any(
                j["kind"] in ("defect", "cond") and (loc[1] in j["suspects"] or loc[1] == j.get("target"))
                for j in self._tail_jobs(ctx, loc[0])
            ):
                keep.add(fid)
        return keep

    def belief_clear_unknown(self, state: State, keep: set[str]) -> State:
        """A belief-world copy of the state with every active truth fault outside ``keep`` removed."""
        ctx = _Ctx(self, Cow(state), int(state["t_last"]))
        faults = ctx.cow.doc("doc_faults")
        for fid in sorted(faults):
            f = faults[fid]
            if f["active"] and fid not in keep:
                f["active"] = False
                r = self._serial_row(ctx, f["serial"])
                if r >= 0 and int(ctx.cow.a("ser_faults")[r]) > 0:
                    ctx.cow.w("ser_faults")[r] -= 1
                ctx.cow.touch("doc_faults")
        return ctx.cow.commit()

    def _o_change_monitoring_config(self, ctx, row, prm) -> str | None:
        tails = self._tails_of(row)
        if not tails:
            return "no target tail"
        for ti in tails:
            td = ctx.cow.doc("doc_tails")[self.fleet.tails[ti]]
            f = set(td["filters"]) | set(prm.get("filter_codes_add") or [])
            f -= set(prm.get("filter_codes_remove") or [])
            td["filters"] = sorted(f)
            ctx.cow.touch("doc_tails")
            self._emit(ctx, "mx.monitoring", self.targets.monitoring, {"tail": self.fleet.tails[ti], **prm})
        self._order_progress(ctx, row["order_id"], "COMPLETED")
        return None


class _Default(dict):
    def __missing__(self, key: str) -> str:
        return ""
