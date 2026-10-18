"""M14 monitoring and BIT module (architecture §6 M14, §9.4; W1_interfaces.md §4).

Event-only module (``rate = None``) that consumes observations and emits contract records:

- **CIR** (M13 output, engineering units) arrives in time-ordered chunks as ``monitor.observe`` events
  (:func:`phalanx.monitoring.cir_chunk_payload`). Limit monitors (exceedances, cautions, voice warnings), the
  ECMS LUI counters, the Nz level-crossing counters and the take-off record trigger run on it. A flight
  processed in one chunk or many gives identical records (chunk invariance, tested).
- **Lane / LRU fault reports** of the FADEC, DFCC and utility controllers (``monitor.bit_report``) become BIT
  records and CWS cautions (codes with ``src: external``).
- **Internal LRU self-tests** (codes with ``src: internal``; in usage mode every code) run here on the
  coloured, heavy-tailed test statistic of :mod:`phalanx.monitoring.logic`; their mean moves only through
  ``monitor.lru_condition`` events from M11 (a physical LRU condition), so healthy and faulty runs share one
  path (I6). False alarms, missed detections, persistence across flights, sympathetic codes and software-load
  bursts all emerge from that statistic and the code table.

Outputs leave through an **outbox** in the module state (records with kernel times), converted to contract v0
tables by :func:`phalanx.monitoring.contract_out.contract_tables` at download and acknowledged with
``monitor.ack``. M14 never reads truth: its inputs are CIR values, controller reports and LRU conditions.
The CWS words (legends, master, voice) are held outputs, recorded as LRU-computed channels (AD-42,
``phalanx.monitoring.ports.RECORDED``); :func:`cws_words_at` gives their exact edge times.

Events: ``monitor.sortie_start``, ``monitor.observe``, ``monitor.bit_report``, ``monitor.lru_condition``,
``monitor.landing``, ``monitor.sortie_end``, ``monitor.usage_summary``, ``monitor.usage_sortie`` (a whole
usage-mode sortie, forwarded by M10), ``monitor.sw_load``, ``monitor.lru_replace``, ``monitor.ibit``,
``monitor.ack``, ``monitor.download`` (internal).

Cross-module (AD-44): ``mx.action`` from M18 (``SWLOAD`` = software-load burst; ``RR`` of an LRU position =
new unit offsets), ``mx.monitoring`` from M18 (CHANGE_MONITORING_CONFIG: masked codes are still evaluated but
no longer recorded), and ``obs.event`` to M18 (``obs_target``): each ``events.*`` row of a sortie, at its
download ``t_ingest`` = sortie end + ``download_delay`` (whole seconds, M18 encoding).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from phalanx.core.events import Event
from phalanx.core.module import ContractError, ModuleBase, Outputs, ParamSet, Port
from phalanx.core.rng import StreamDecl, Variate
from phalanx.core.state import Field, State, StateSchema
from phalanx.health.module import serial_value
from phalanx.health.protocol import POSITION_STATES, ceil_second, jsonable, plain_payload, read_payload
from phalanx.health.usage import (
    LUI_FLOATS,
    LUI_INTS,
    RF_CAP,
    LuiGates,
    SortieUsage,
    lui_finalize,
    lui_init,
    lui_kernel,
    nz_counter_kernel,
)

from .codes import MECHANISMS, Code, CodeTable
from .cws import CwsMap, build_cws_map
from .logic import BIT_INTS, LIM_INTS, MODE_M_OF_N, bit_test_kernel, limit_kernel

__all__ = [
    "COUNTERS",
    "LUI_REPORTED",
    "VALIDITY",
    "MonitoringConfig",
    "MonitoringModule",
    "cws_words_at",
    "pilot_alert",
]

VALIDITY = ("NORMAL", "NO_COMPUTED_DATA", "FUNCTIONAL_TEST", "FAILURE_WARNING", "BUS_INVALID")


def pilot_alert(code: Code) -> str | None:
    """AD-49: the M04 reaction hook a cockpit alert of ``code`` raises when its CWS record opens - the
    engine fire warning (FIR group, a CWS legend) -> ``pilot.fire_warning``; a flight-control pilot-fault-list
    caution (FCS group, PFL, a CWS legend) -> ``pilot.fcs_caution``; anything else -> None (no catalogued
    reaction)."""
    if code.legend is None:
        return None
    prefix = code.code.split("-")[0]
    if prefix == "FIR":
        return "pilot.fire_warning"
    if prefix == "FCS" and code.fault_list == "PFL":
        return "pilot.fcs_caution"
    return None


KIND_BIT, KIND_EXCEED, KIND_CAUTION, KIND_COUNTER, KIND_TAKEOFF = range(5)
#: open-record pointer whose record was already drained by ``monitor.ack`` (the caution is still active)
DRAINED = -2
B_DECL = BIT_INTS.index("declared")
# : the 8 GE LUIs as reported (EOT and TAMP in hours, SRC in equivalent hours) + Type IV (ECMS internal, for
# TAC)
LUI_REPORTED: tuple[tuple[str, str], ...] = (
    ("LUI.TYPE1", "type1"),
    ("LUI.TYPE3", "type3"),
    ("LUI.EFTC", "eftc"),
    ("LUI.SRC", "src_h"),
    ("LUI.TAMP", "tamp_s"),
    ("LUI.PS3_FULL", "ps3_full"),
    ("LUI.PS3_PART", "ps3_partial"),
    ("LUI.EOT", "eot_s"),
)
#: usage.counters param_ids: (param_id, source LRU, per-engine?)
COUNTERS: tuple[tuple[str, str, bool], ...] = (
    *((p, "ECMS", True) for p, _ in LUI_REPORTED),
    ("USAGE.TAC", "GROUND", True),
    ("USAGE.FLIGHT_HOURS", "OAC", False),
    ("USAGE.LANDINGS", "OAC", False),
    ("USAGE.GEAR_CYCLES", "OAC", False),
    ("USAGE.AB_LIGHTS", "OAC", True),
    ("USAGE.ENGINE_STARTS.GROUND_STARTS", "OAC", True),
    ("USAGE.ENGINE_STARTS.AIR_RELIGHTS", "OAC", True),
    ("USAGE.JFS_STARTS.ATTEMPTS", "OAC", False),
    ("USAGE.JFS_STARTS.SUCCESSES", "OAC", False),
    ("USAGE.JFS_STARTS.CONSECUTIVE", "OAC", False),
    ("USAGE.CHUTE_STREAMINGS", "OAC", False),
    ("USAGE.BRAKE_APPLICATIONS.COUNT", "OAC", False),
    ("USAGE.BRAKE_APPLICATIONS.ENERGY", "OAC", False),
    ("USAGE.G_EXCEEDANCE.OVER_G", "OAC", False),
    ("USAGE.G_EXCEEDANCE.OVER_AOA", "OAC", False),
    ("USAGE.G_EXCEEDANCE.OVERSPEED", "OAC", False),
    ("USAGE.AMAGB_HOURS", "OAC", False),
    *((f"STRUCT.NZ_COUNTERS.L{k}", "OAC", False) for k in range(1, 9)),
)
_CI = {p: i for i, (p, _, _) in enumerate(COUNTERS)}
_ID = "<U64"
_LF = {n: i for i, n in enumerate(LUI_FLOATS)}
_GAP = LUI_INTS.index("gap")


@dataclass(frozen=True)
class MonitoringConfig:
    """Instance configuration (built from the dictionary by :meth:`from_dictionary`).

    channels: the M14 channel table (CIR ``channel_id``s it consumes), sorted; ``monitor.observe`` payloads
        carry indices into it. rates: acquisition rate [Hz] per channel (0 = event-driven).
    lui_channels: per engine (N2, PS3, T5, PLA) channel ids (EU: percent, psi, degC, deg).
    usage_mode: every code runs as an internal test (no CIR, no controller physics) - see A-W1.5-26.
    regime: "immature" or "mature" threshold regime of the internal tests.
    cws: the CWS bit map (:mod:`phalanx.monitoring.cws`); with it M14 publishes the CWS words as held
        outputs (``RECORDED`` in ``phalanx.monitoring.ports``, AD-42).
    """

    codes: CodeTable
    channels: tuple[str, ...]
    rates: Mapping[str, float]
    engine_serials: tuple[str, ...]
    lui_channels: tuple[tuple[str, str, str, str], ...]
    nz_channel: str = "FCS.VOTED.NZ"
    wow_channel: str = "LG.WOW"
    n2_gate_channel: str = "ENG.N2.V"
    lru_serials: Mapping[str, str] = field(default_factory=dict)
    usage_mode: bool = False
    regime: str = "immature"
    chute_serial: str = ""
    initial_counters: Mapping[str, float] = field(default_factory=dict)
    cws: CwsMap | None = None
    tail_no: str = ""  # contract / M18 tail name (default: the run identity's tail)
    epoch_utc_ns: int = 0  # kernel time 0 in simulated UTC (whole second for M18)
    obs_target: str | None = None  # M18 module id: obs.event rows at download
    dictionary: Any = None  # the M01 dictionary (contract rows for obs.event)
    pilot_target: str | None = None  # M04 module id: pilot.fire_warning / pilot.fcs_caution (AD-49)

    @classmethod
    def from_dictionary(
        cls, dictionary, codes: CodeTable, engine_serials: Sequence[str], **kw
    ) -> MonitoringConfig:
        lui = (("ENG.N2.V", "ENG.PS3.V", "ENG.T5", "ENG.PLA.V"),) * len(engine_serials)
        chans = {c.monitor.channel for c in codes.codes if c.monitor is not None}
        chans |= {x for t in lui for x in t}
        chans |= {
            kw.get("nz_channel", "FCS.VOTED.NZ"),
            kw.get("wow_channel", "LG.WOW"),
            kw.get("n2_gate_channel", "ENG.N2.V"),
        }
        rates = {}
        for ch in chans:
            dictionary.channel(ch)  # KeyError if unknown
            try:
                rates[ch] = float(dictionary.acquisition_rate_hz(ch) or 0.0)
            except Exception:
                rates[ch] = 0.0
        kw.setdefault("cws", build_cws_map(dictionary, codes))
        kw.setdefault("dictionary", dictionary)
        return cls(codes, tuple(sorted(chans)), rates, tuple(engine_serials), lui, **kw)


def _p(params: ParamSet, name: str) -> float:
    return float(params.value(name))


class MonitoringModule(ModuleBase):
    """M14 (see module docstring). ``params``: merged ParamSet of ``configs/tejas/params/M14.yaml``."""

    version = "1.0.0"
    rate = None
    ports_in = ()
    ports_out = ()
    streams = (
        StreamDecl(
            "monitoring",
            "test_noise",
            ("scenario", "tail", "sortie", "sensor"),
            Variate.NORMAL,
            1024,
            "M14",
            "BIT test statistic innovations per code (sensor = code), indexed by test-sample number",
        ),
        StreamDecl(
            "monitoring",
            "test_tail",
            ("scenario", "tail", "sortie", "sensor"),
            Variate.UNIFORM,
            1024,
            "M14",
            "heavy-tail mixture selector per test sample",
        ),
        StreamDecl(
            "monitoring",
            "pbit_noise",
            ("scenario", "tail", "sortie", "sensor"),
            Variate.NORMAL,
            64,
            "M14",
            "PBIT pass innovations per code",
        ),
        StreamDecl(
            "monitoring",
            "pbit_tail",
            ("scenario", "tail", "sortie", "sensor"),
            Variate.UNIFORM,
            64,
            "M14",
            "PBIT heavy-tail selector",
        ),
        StreamDecl(
            "monitoring",
            "ground_noise",
            ("scenario", "tail", "job", "sensor"),
            Variate.NORMAL,
            64,
            "M14",
            "IBIT/MBIT pass innovations per maintenance job",
        ),
        StreamDecl(
            "monitoring",
            "ground_tail",
            ("scenario", "tail", "job", "sensor"),
            Variate.UNIFORM,
            64,
            "M14",
            "IBIT/MBIT heavy-tail selector",
        ),
        StreamDecl(
            "monitoring",
            "flight_offset",
            ("scenario", "tail", "sortie"),
            Variate.NORMAL,
            256,
            "M14",
            "per-sortie environmental offset of every test statistic, indexed by code",
        ),
        StreamDecl(
            "monitoring",
            "unit_offset",
            ("scenario", "serial"),
            Variate.GENERATOR,
            owner="M14",
            description="per LRU serial: offset of each of its test statistics (generator = code index)",
        ),
        StreamDecl(
            "monitoring",
            "cascade",
            ("scenario", "tail", "sortie"),
            Variate.GENERATOR,
            owner="M14",
            description="sympathetic-code draws, generator index = declaration number",
        ),
    )

    def __init__(self, id: str, params: ParamSet, *, config: MonitoringConfig, **kw) -> None:
        self.config = config
        nc = len(config.codes.codes)
        self._mon = [c for c in config.codes.codes if c.monitor is not None]
        self._mon_code = np.array([c.index for c in self._mon], np.int64)
        if config.cws is not None:
            self.ports_out = tuple(Port(p, "1", "<i8", ()) for p in config.cws.ports)
        self._ch_index = {c: i for i, c in enumerate(config.channels)}
        ne = len(config.engine_serials)
        if len(config.lui_channels) != ne:
            raise ContractError("one LUI channel tuple per engine is required")
        nm = len(self._mon)
        nch = len(config.channels)
        self._per_engine = {pid: pe for pid, _, pe in COUNTERS}
        self._slots: dict[tuple[str, int], int] = {}
        for pid, _, pe in COUNTERS:
            for e in range(ne) if pe else (-1,):
                self._slots[(pid, e)] = len(self._slots)
        self.state_schema = StateSchema(
            "monitoring.m14",
            3,
            (
                Field(
                    "clock", "<i8", (6,)
                ),  # n_sorties, t_sortie_start, in_sortie, airborne, n_decl, takeoff_done
                Field("sortie_id", _ID, ()),
                Field("burst_left", "<i8", ()),
                Field("t_z", "<f8", (nc,)),
                Field("t_ist", "<i8", (nc, len(BIT_INTS))),
                Field("t_next", "<i8", (nc,)),
                Field("t_unit", "<f8", (nc,)),
                Field("t_flight", "<f8", (nc,)),
                Field("t_h", "<f8", (nc,)),
                Field("t_cau", "<i8", (nc,)),
                Field("x_open", "<i8", (nc,)),
                Field("x_mask", "<i8", (nc,)),
                Field("obs_sent", "<i8", ()),
                Field("m_peak", "<f8", (nm,)),
                Field("m_ist", "<i8", (nm, len(LIM_INTS))),
                Field("m_open", "<i8", (nm,)),
                Field("m_cau", "<i8", (nm,)),
                Field("hold_v", "<f8", (nch,)),
                Field("hold_t", "<i8", (nch,)),
                Field("hold_ok", "<i8", (nch,)),
                Field("lui_f", "<f8", (ne, len(LUI_FLOATS))),
                Field("lui_i", "<i8", (ne, len(LUI_INTS))),
                Field("lui_stack", "<f8", (ne, RF_CAP)),
                Field("lui_seq", "<i8", ()),
                Field("nz_counts", "<f8", (8,)),
                Field("nz_armed", "<i8", (8,)),
                Field("exc_counts", "<i8", (3,)),
                Field("cum", "<f8", (len(self._slots),)),
                Field("cum0", "<f8", (len(self._slots),)),
                Field("lru_serial", _ID, (len(self._lrus(config)),)),
                *(
                    Field(n, dt, (None,))
                    for n, dt in (
                        ("o_kind", "<i8"),
                        ("o_code", "<i8"),
                        ("o_t", "<i8"),
                        ("o_t_end", "<i8"),
                        ("o_sortie", _ID),
                        ("o_persist", "<i8"),
                        ("o_latched", "<i8"),
                        ("o_mech", "<i8"),
                        ("o_value", "<f8"),
                        ("o_limit", "<f8"),
                        ("o_incr", "<f8"),
                        ("o_engine", "<i8"),
                        ("o_validity", "<i8"),
                        ("o_seq", "<i8"),
                        ("o_lane", "<U8"),
                    )
                ),
            ),
        )
        super().__init__(id, params, **kw)
        g = self.params
        self._gates = LuiGates(
            n2_run=_p(g, "n2_run_pct") * 100.0,
            n2_off=_p(g, "n2_off_pct") * 100.0,
            n2_idle=_p(g, "n2_idle_pct") * 100.0,
            n2_low=_p(g, "n2_low_pct") * 100.0,
            n2_cruise=_p(g, "n2_cruise_pct") * 100.0,
            n2_irp=_p(g, "n2_irp_pct") * 100.0,
            pla_irp=math.degrees(_p(g, "pla_irp_deg")),
            ps3_max=_p(g, "ps3_max_psi") / 6894.757293168361,
            t5_ref=_p(g, "t5_ref_degc") - 273.15,
            t5_doubling=_p(g, "t5_doubling_k"),
            t5_full_swing=_p(g, "t5_full_swing_k"),
            eftc_exponent=_p(g, "eftc_exponent"),
            t5_deadband=_p(g, "t5_deadband_k"),
            dt_max_s=_p(g, "lui_dt_max_s"),
            dt_gap_s=_p(g, "lui_dt_gap_s"),
        ).vector()
        self._nz_levels = np.asarray(self.params.value("nz_levels_g"), np.float64)
        if self._nz_levels.shape != (8,):
            raise ContractError("nz_levels_g must have 8 levels")

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _lrus(config: MonitoringConfig) -> tuple[str, ...]:
        return tuple(sorted({c.lru for c in config.codes.codes}))

    def _regime(self, code_regime: str) -> tuple[float, int, int]:
        """(threshold k, m, n) of a code's test."""
        p = self.params
        if code_regime == "ehm" or self.config.regime == "mature":
            return _p(p, "mat_k"), int(_p(p, "mat_m")), int(_p(p, "mat_n"))
        return _p(p, "imm_k"), int(_p(p, "imm_m")), int(_p(p, "imm_n"))

    def _is_test(self, c) -> bool:
        return self.config.usage_mode or c.src == "internal"

    def _code_regime(self, c) -> str:
        if self.config.usage_mode and c.src == "cir":
            return "ehm"
        return c.regime

    @staticmethod
    def _copy(state: State) -> dict[str, np.ndarray]:
        return {k: np.array(v, copy=True) for k, v in state.items()}

    # ------------------------------------------------------------------ init / outputs
    def init(self, params: ParamSet, keys) -> State:
        ident = keys.identity.as_dict()
        tail = serial_value(str(ident.get("tail", "TAIL")))
        nc = len(self.config.codes.codes)
        nm = len(self._mon)
        nch = len(self.config.channels)
        ne = len(self.config.engine_serials)
        lrus = self._lrus(self.config)
        serials = [serial_value(self.config.lru_serials.get(lru, f"{tail}.{lru}.0")) for lru in lrus]
        st: dict[str, np.ndarray] = {
            "clock": np.array([0, -1, 0, 0, 0, 0], np.int64),
            "sortie_id": np.array("", _ID),
            "burst_left": np.array(0, np.int64),
            "t_z": np.zeros(nc),
            "t_ist": np.zeros((nc, len(BIT_INTS)), np.int64),
            "t_next": np.zeros(nc, np.int64),
            "t_unit": np.zeros(nc),
            "t_flight": np.zeros(nc),
            "t_h": np.zeros(nc),
            "t_cau": np.full(nc, -1, np.int64),
            "x_open": np.zeros(nc, np.int64),
            "x_mask": np.zeros(nc, np.int64),
            "obs_sent": np.array(0, np.int64),
            "m_peak": np.zeros(nm),
            "m_ist": np.zeros((nm, len(LIM_INTS)), np.int64),
            "m_open": np.full(nm, -1, np.int64),
            "m_cau": np.full(nm, -1, np.int64),
            "hold_v": np.zeros(nch),
            "hold_t": np.full(nch, -1, np.int64),
            "hold_ok": np.zeros(nch, np.int64),
            "lui_f": np.zeros((ne, len(LUI_FLOATS))),
            "lui_i": np.zeros((ne, len(LUI_INTS)), np.int64),
            "lui_stack": np.zeros((ne, RF_CAP)),
            "lui_seq": np.array(0, np.int64),
            "nz_counts": np.zeros(8),
            "nz_armed": np.ones(8, np.int64),
            "exc_counts": np.zeros(3, np.int64),
            "cum": self._initial_cum(),
            "cum0": self._initial_cum(),
            "lru_serial": np.array(serials, _ID),
            **self._empty_outbox(),
        }
        for lru in lrus:
            self._draw_unit_offsets(st, lru)
        return st

    def _initial_cum(self) -> np.ndarray:
        """Cumulative counters at t0 (``config.initial_counters`` keyed "<param_id>#<engine or -1>")."""
        cum = np.zeros(len(self._slots))
        for key, v in self.config.initial_counters.items():
            pid, _, e = key.partition("#")
            cum[self._slots[(pid, int(e))]] = float(v)
        return cum

    @staticmethod
    def _empty_outbox() -> dict[str, np.ndarray]:
        return {
            "o_kind": np.zeros(0, np.int64),
            "o_code": np.zeros(0, np.int64),
            "o_t": np.zeros(0, np.int64),
            "o_t_end": np.zeros(0, np.int64),
            "o_sortie": np.zeros(0, _ID),
            "o_persist": np.zeros(0, np.int64),
            "o_latched": np.zeros(0, np.int64),
            "o_mech": np.zeros(0, np.int64),
            "o_value": np.zeros(0),
            "o_limit": np.zeros(0),
            "o_incr": np.zeros(0),
            "o_engine": np.zeros(0, np.int64),
            "o_validity": np.zeros(0, np.int64),
            "o_seq": np.zeros(0, np.int64),
            "o_lane": np.zeros(0, "<U8"),
        }

    def initial_outputs(self, state: State) -> Outputs:
        """The CWS words (held between events; see :func:`cws_words_at` for exact edge times)."""
        if self.config.cws is None:
            return {}
        return self.config.cws.words(self.cws_active(state))

    def cws_active(self, state: State) -> np.ndarray:
        """Codes whose caution is active: a declared internal test, an open limit monitor or an uncleared
        controller report (explicit state, independent of the outbox and its acknowledgement)."""
        act = (np.asarray(state["t_cau"]) != -1) | (np.asarray(state["x_open"]) > 0)
        act[self._mon_code[np.asarray(state["m_cau"]) != -1]] = True
        return act

    def _draw_unit_offsets(self, st: dict[str, np.ndarray], lru: str) -> None:
        lrus = self._lrus(self.config)
        serial = str(st["lru_serial"][lrus.index(lru)])
        s = self.stream("unit_offset", serial=serial)
        sd_bit = _p(self.params, "unit_offset_sd")
        sd_ehm = _p(self.params, "ehm_unit_offset_sd")  # gas-path residuals are per-engine baseline corrected
        for c in self.config.codes.codes:
            if c.lru == lru:
                sd = sd_ehm if self._code_regime(c) == "ehm" else sd_bit
                st["t_unit"][c.index] = sd * float(s.generator(c.index).standard_normal())

    # ------------------------------------------------------------------ outbox
    @staticmethod
    def _append(st: dict[str, np.ndarray], **rec) -> int:
        defaults = {
            "o_kind": 0,
            "o_code": 0,
            "o_t": 0,
            "o_t_end": -1,
            "o_sortie": "",
            "o_persist": 0,
            "o_latched": 0,
            "o_mech": 0,
            "o_value": 0.0,
            "o_limit": 0.0,
            "o_incr": 0.0,
            "o_engine": -1,
            "o_validity": 0,
            "o_seq": 0,
            "o_lane": "",
        }
        defaults.update(rec)
        for k, v in defaults.items():
            st[k] = np.append(st[k], np.array(v, dtype=st[k].dtype))
        return int(st["o_kind"].size - 1)

    def _declare(
        self,
        st,
        code,
        t: int,
        *,
        persist: int,
        mech: str | None = None,
        lane: str = "",
        sortie: str | None = None,
    ) -> tuple[int, int]:
        """A BIT or exceedance declaration of ``code`` at kernel time ``t`` (+ caution, sympathetic codes).
        A code masked by ``mx.monitoring`` is not recorded: returns (-1, -1)."""
        if int(st["x_mask"][code.index]):
            return -1, -1
        sid = str(st["sortie_id"]) if sortie is None else sortie
        kind = KIND_EXCEED if code.monitor is not None and code.mechanism == "EXCEEDANCE" else KIND_BIT
        mech_i = MECHANISMS.index(mech or code.mechanism)
        idx = self._append(
            st,
            o_kind=kind,
            o_code=code.index,
            o_t=t,
            o_sortie=sid,
            o_persist=persist,
            o_latched=1,
            o_mech=mech_i,
            o_lane=lane or (code.lane or ""),
        )
        cau = -1
        if code.legend is not None or code.voice:
            cau = self._append(
                st,
                o_kind=KIND_CAUTION,
                o_code=code.index,
                o_t=t,
                o_sortie=sid,
                o_persist=persist,
                o_mech=mech_i,
                o_lane=lane or (code.lane or ""),
            )
        st["clock"][4] += 1
        if code.sympathetic and sortie is None:
            g = self.stream("cascade", sortie=sid).generator(int(st["clock"][4]))
            scale = _p(self.params, "sympathetic_scale")
            for sym, p, lo, hi in code.sympathetic:
                u = float(g.random())
                d = lo + float(g.random()) * (hi - lo)
                if u < p * scale:
                    sc = self.config.codes.by_code[sym]
                    self._append(
                        st,
                        o_kind=KIND_BIT,
                        o_code=sc.index,
                        o_t=t + round(d * 1e9),
                        o_sortie=sid,
                        o_persist=0,
                        o_latched=1,
                        o_mech=MECHANISMS.index(sc.mechanism),
                        o_lane=sc.lane or "",
                    )
        return idx, cau

    # ------------------------------------------------------------------ events
    def on_event(self, state: State, event: Event, t: int):
        st, out = self._on_event(state, event, t)
        if self.config.pilot_target is not None and st is not state:
            out = [*out, *self._pilot_alerts(state, st, t)]
        return st, out

    def _pilot_alerts(self, before: State, after: State, t: int) -> list[Event]:
        """AD-49: ``pilot.fire_warning`` / ``pilot.fcs_caution`` {tail, code} to M04 for every CWS record this
        event opened whose code has a pilot reaction (:func:`pilot_alert`), at the record time (not before the
        event that produced it: M14 is event-driven, so the alert is as late as the observation that raised
        it)."""
        codes = self.config.codes.codes
        tail = self.config.tail_no or str(self.keys.identity.as_dict().get("tail", ""))
        out: list[Event] = []
        for j in range(int(before["o_kind"].size), int(after["o_kind"].size)):
            if int(after["o_kind"][j]) != KIND_CAUTION:
                continue
            code = codes[int(after["o_code"][j])]
            kind = pilot_alert(code)
            if kind is not None:
                t_al = max(t, int(after["o_t"][j]))
                pay = {"tail": tail, "code": code.code}
                out.append(Event(t_al, kind, self.config.pilot_target, pay, source=self.id))
        return out

    def _on_event(self, state: State, event: Event, t: int):
        k = event.kind
        p = event.payload
        handlers = {
            "monitor.sortie_start": self._sortie_start,
            "monitor.observe": self._observe,
            "monitor.bit_report": self._bit_report,
            "monitor.lru_condition": self._lru_condition,
            "monitor.landing": self._landing,
            "monitor.sortie_end": self._sortie_end,
            "monitor.usage_summary": self._usage_summary,
            "monitor.sw_load": self._sw_load,
            "monitor.lru_replace": self._lru_replace,
            "monitor.ibit": self._ibit,
            "monitor.ack": self._ack,
            "monitor.usage_sortie": self._usage_sortie,
        }
        if k in ("fadec.fault", "fadec.caution"):
            return self._fadec(self._copy(state), read_payload(p), t), []
        if k in ("mx.action", "mx.monitoring"):
            d = read_payload(p)
            tail = self.config.tail_no or str(self.keys.identity.as_dict().get("tail", ""))
            if "tail" not in d:  # AD-48.1: the catalogued key is read, never guessed
                raise ContractError(f"{self.id}: {k} payload lacks its catalogued key 'tail'")
            if str(d["tail"]) != tail:
                return state, []  # a fleet-level event for another tail (one M14 per tail)
            st = self._copy(state)
            return (self._mx_action(st, d, t) if k == "mx.action" else self._mx_monitoring(st, d, t)), []
        if k == "monitor.download":
            return self._download(state, t)
        if k in ("ops.power_up", "ops.takeoff", "ops.sortie_done"):  # AD-48.2: the sortie lifecycle from M02
            d = read_payload(p)
            tail = self.config.tail_no or str(self.keys.identity.as_dict().get("tail", ""))
            if str(d["tail_no"]) != tail:
                return state, []  # another tail's sortie (one M14 per tail)
            if k == "ops.power_up":
                return self._ops_power_up(self._copy(state), d, t), []
            if k == "ops.takeoff":
                return self._ops_takeoff(self._copy(state), d, t), []
            return self._ops_sortie_done(self._copy(state), d, t)
        h = handlers.get(k)
        if h is None:
            return super().on_event(state, event, t)
        st = h(self._copy(state), p, t)
        out: list[Event] = []
        if k in ("monitor.sortie_end", "monitor.usage_sortie") and self.config.obs_target:
            t_dl = ceil_second(t + round(_p(self.params, "download_delay") * 1e9))
            out.append(Event(t_dl, "monitor.download", self.id, {}, source=self.id))
        return st, out

    # --- AD-44 boundary
    def _ops_power_up(self, st, d, t: int):
        """``ops.power_up`` (W2.5, catalogued; M02 emission planned for W2.1a): power-up at engine start. PBIT
        runs now (one pass of every testable code) and CBIT from now on, on the ground as in the air (report
        §9: PBIT at power-up). A repeated power-up of the powered sortie is a no-op; a power-up of another
        sortie while one is powered is a protocol error (the previous sortie never shut down)."""
        sid = serial_value(str(d["sortie_id"]))
        if int(st["clock"][2]):
            if str(st["sortie_id"]) == sid:
                return st
            raise ContractError(
                f"{self.id}: ops.power_up of {sid!r} while sortie {str(st['sortie_id'])!r} is powered"
            )
        return self._sortie_start(st, {"sortie_id": sid}, t)

    def _ops_takeoff(self, st, d, t: int):
        """``ops.takeoff`` (AD-48.2): the sortie's identity for this monitor. Powered up already
        (``ops.power_up`` at engine start, or another power-up hook): keep it; the powered sortie must be this
        one. Not powered: power up now, so PBIT runs at take-off (**PROXY A-W2.1c-4**, until M02 emits
        ``ops.power_up``: the real PBIT is at engine start, minutes earlier)."""
        if int(st["clock"][2]):
            sid = serial_value(str(d["sortie_id"]))
            if str(st["sortie_id"]) != sid:
                raise ContractError(
                    f"{self.id}: take-off of {sid!r} while sortie {str(st['sortie_id'])!r} is powered"
                )
            return st
        return self._sortie_start(st, {"sortie_id": d["sortie_id"]}, t)

    def _ops_sortie_done(self, st, d, t: int):
        """``ops.sortie_done`` (AD-48.2): shut-down - final LUI write, OAC counters, power down, and the
        download to M18 after ``download_delay``. The discrete counts come from the sortie-done document
        (**PROXY A-W2.1c-4**: tech-log quantities, not counted from recorded discretes; counts it lacks
        write no record). A sortie this monitor never started is a wiring error (configure ops.takeoff /
        ops.sortie_done or M10's usage-mode forwarding, not a mix)."""
        if not int(st["clock"][2]):
            raise ContractError(f"{self.id}: ops.sortie_done for {d['sortie_id']!r}, which M14 never started")
        ne = len(self.config.engine_serials)
        counts = {
            "flight_time_s": float(d["flight_hours"]) * 3600.0,
            "landings": float(d["landings"]),
            "gear_cycles": float(d["landings"]),
            "starts": np.full(ne, float(d["engine_starts"])),
            "chute_streamings": float(d["chute_streamed"]),
        }
        self._advance_tests(st, t)
        self._lui_update(st, t, final=True)
        self._oac_counters(st, counts, t, present_only=True)
        st = self._power_down(st)
        out: list[Event] = []
        if self.config.obs_target:
            t_dl = ceil_second(t + round(_p(self.params, "download_delay") * 1e9))
            out.append(Event(t_dl, "monitor.download", self.id, {}, source=self.id))
        return st, out

    def _usage_sortie(self, st, p, t: int):
        """A whole usage-mode sortie (forwarded by M10 from ``usage.sortie_summary``): power-up at
        ``t_start``, the tests over the flight, the usage summary and shut-down at ``t_end``."""
        t0, t1 = int(p["t_start"]), int(p["t_end"])
        u = {k: v for k, v in p.items() if k not in ("t_start", "t_end")}
        st = self._sortie_start(st, {"sortie_id": u["sortie_id"]}, t0)
        self._advance_tests(st, t1)
        st = self._usage_summary(st, u, t1)  # LUIs and OAC counters of the sortie
        return self._power_down(st)

    def _fadec(self, st, d, t: int):
        """``fadec.fault`` / ``fadec.caution`` (M08, AD-44): the FADEC's own code - a dictionary ``bit_codes``
        code (AD-48.5; M08 emits the unified table since W2.1b) - set or cleared at its frame instant. A FADEC
        limit caution on a code M14's ECMS monitors itself from the recorded data (``src: cir``, ENG-701..703)
        is not re-recorded; a code that is not an external FADEC code of the table is a contract error."""
        code = str(d["code"])
        c = self.config.codes.by_code.get(code)
        if c is None:
            raise ContractError(f"{self.id}: FADEC code {code!r} is not a dictionary bit_code")
        if c.src == "cir":  # a limit caution M14's ECMS monitors record from the recorded data
            return st
        if c.src != "external" or c.lru != "FADEC":
            raise ContractError(f"{self.id}: {code!r} is not a FADEC-reported code ({c.lru}, {c.src})")
        dst = code
        t_f = int(d["t_frame_ns"])
        t_occ = min(t, t_f) if t_f >= 0 else t
        payload = {
            "code": dst,
            "lane": str(d["lane"] or ""),
            "persistence": 0,
            "cleared": not bool(d["set"]),
        }
        return self._bit_report(st, payload, t_occ)

    def _mx_action(self, st, d, t: int):
        action, pos = str(d.get("action", "")), str(d.get("pos") or "")
        if action == "SWLOAD":
            return self._sw_load(st, d, t)
        if action == "RR" and d.get("serial"):
            lrus = self._lrus(self.config)
            for item in POSITION_STATES.get(pos, ()):
                if item.startswith("lru:") and item[4:] in lrus:
                    st = self._lru_replace(st, {"lru": item[4:], "serial": str(d["serial"])}, t)
        return st

    def _mx_monitoring(self, st, d, t: int):
        by_code = self.config.codes.by_code
        for code in d.get("filter_codes_add") or []:
            if code in by_code:
                st["x_mask"][by_code[code].index] = 1
        for code in d.get("filter_codes_remove") or []:
            if code in by_code:
                st["x_mask"][by_code[code].index] = 0
        return st

    def _download(self, state: State, t: int):
        """``obs.event`` to M18 for every ``events.*`` record not yet sent (rows at ingest time ``t``)."""
        from .contract_out import contract_tables

        st = self._copy(state)
        n0, n = int(st["obs_sent"]), int(st["o_kind"].size)
        st["obs_sent"] = np.array(n, np.int64)
        if self.config.obs_target is None or n0 >= n or self.config.dictionary is None:
            return st, []
        view = dict(state)
        for k in self._empty_outbox():
            view[k] = np.asarray(state[k])[n0:]
        tail = self.config.tail_no or str(self.keys.identity.as_dict().get("tail", ""))
        tabs = contract_tables(
            self,
            view,
            dictionary=self.config.dictionary,
            tail_no=tail,
            epoch_utc_ns=self.config.epoch_utc_ns,
            t_ingest_utc_ns=self.config.epoch_utc_ns + t,
        )
        out: list[Event] = []
        for topic in ("events.bit_faults", "events.exceedances", "events.cautions"):
            for row in tabs[topic].to_pylist():
                doc = {"topic": topic, "row": jsonable(row)}
                out.append(Event(t, "obs.event", self.config.obs_target, plain_payload(doc), source=self.id))
        return st, out

    # --- sortie lifecycle
    def _sortie_start(self, st, p, t: int):
        sid = serial_value(str(np.asarray(p["sortie_id"]).item()))
        st["sortie_id"] = np.array(sid, _ID)
        st["clock"][1] = t
        st["clock"][2] = 1
        st["clock"][3] = 0
        st["clock"][5] = 0
        nc = len(self.config.codes.codes)
        st["t_flight"] = _p(self.params, "flight_offset_sd") * self.stream("flight_offset", sortie=sid).draws(
            0, nc
        )
        st["t_ist"][:] = 0
        st["t_next"][:] = 0
        st["t_z"][:] = 0.0
        st["t_cau"][:] = -1
        st["x_open"][:] = 0  # power-up: controllers re-report faults still present
        st["lui_seq"] = np.array(0, np.int64)
        st["cum0"] = st["cum"].copy()
        st["nz_counts"][:] = 0.0
        st["nz_armed"][:] = 1
        st["exc_counts"][:] = 0
        ne = len(self.config.engine_serials)
        for e in range(ne):
            f, i, s = lui_init()
            st["lui_f"][e], st["lui_i"][e], st["lui_stack"][e] = f, i, s
        # PBIT at power-up: one pass of every testable code
        npb = int(_p(self.params, "pbit_samples"))
        for c in self.config.codes.codes:
            if not self._is_test(c):
                continue
            k, m, n = self._regime(self._code_regime(c))
            nr = self.stream("pbit_noise", sortie=sid, sensor=c.code).draws(0, npb)
            ur = self.stream("pbit_tail", sortie=sid, sensor=c.code).draws(0, npb)
            mu = st["t_unit"][c.index] + st["t_flight"][c.index] + st["t_h"][c.index]
            _, _, fd, _, _ = self._kernel(
                0.0, np.zeros(len(BIT_INTS), np.int64), mu, nr, ur, k - self._burst_dk(st), m, n
            )
            if fd >= 0:
                _, cau = self._declare(st, c, t, persist=int(fd) + 1, mech="PBIT")
                st["t_ist"][c.index][B_DECL] = 1  # latched until CBIT passes n_clear times
                st["t_cau"][c.index] = cau
        return st

    def _burst_dk(self, st) -> float:
        left = int(st["burst_left"])
        if left <= 0:
            return 0.0
        return _p(self.params, "burst_dk") * left / max(1.0, _p(self.params, "burst_flights"))

    def _kernel(self, z, ist, mu, nr, ur, thr, m, n):
        p = self.params
        return bit_test_kernel(
            z,
            ist,
            mu,
            nr,
            ur,
            phi=_p(p, "test_phi"),
            p_mix=_p(p, "test_p_mix"),
            k_mix=_p(p, "test_k_mix"),
            thr=thr,
            mode=MODE_M_OF_N,
            m=m,
            n=n,
            n_clear=int(_p(p, "n_clear")),
        )

    def _advance_tests(self, st, t_to: int) -> None:
        """Evaluate every internal test on its grid up to (excluding) kernel time ``t_to``."""
        if int(st["clock"][2]) == 0:
            return
        t0 = int(st["clock"][1])
        rate = _p(self.params, "test_rate")  # per second (SI)
        n_to = math.floor((t_to - t0) * 1e-9 * rate)
        sid = str(st["sortie_id"])
        dk = self._burst_dk(st)
        for c in self.config.codes.codes:
            if not self._is_test(c):
                continue
            j0 = int(st["t_next"][c.index])
            if n_to <= j0:
                continue
            L = n_to - j0
            nr = self.stream("test_noise", sortie=sid, sensor=c.code).draws(j0, L)
            ur = self.stream("test_tail", sortie=sid, sensor=c.code).draws(j0, L)
            k, m, n = self._regime(self._code_regime(c))
            mu = st["t_unit"][c.index] + st["t_flight"][c.index] + st["t_h"][c.index]
            was_decl = int(st["t_ist"][c.index][3])
            z, ist, fd, fc, _ = self._kernel(
                st["t_z"][c.index], st["t_ist"][c.index], mu, nr, ur, k - dk, m, n
            )
            st["t_z"][c.index] = z
            st["t_ist"][c.index] = ist
            st["t_next"][c.index] = n_to
            if fd >= 0 and not was_decl:
                td = t0 + round((j0 + fd) / rate * 1e9)
                _, cau = self._declare(st, c, td, persist=n)
                st["t_cau"][c.index] = cau
            if fc >= 0 and st["t_cau"][c.index] != -1:
                r = int(st["t_cau"][c.index])
                if r >= 0:  # not yet drained by monitor.ack
                    st["o_t_end"][r] = t0 + round((j0 + fc) / rate * 1e9)
                st["t_cau"][c.index] = -1

    def _sortie_end(self, st, p, t: int):
        self._advance_tests(st, t)
        self._lui_update(st, t, final=True)
        self._oac_counters(st, p, t)
        return self._power_down(st)

    @staticmethod
    def _power_down(st):
        st["clock"][2] = 0
        if int(st["burst_left"]) > 0:
            st["burst_left"] = np.array(int(st["burst_left"]) - 1, np.int64)
        st["clock"][0] += 1
        return st

    def _landing(self, st, p, t: int):
        self._advance_tests(st, t)
        if int(st["lui_seq"]) == 0:
            self._lui_update(st, t, final=False)
        return st

    # --- reports from controllers and conditions from M11
    def _bit_report(self, st, p, t: int):
        self._advance_tests(st, t)
        code = self.config.codes.by_code.get(str(np.asarray(p["code"]).item()))
        if code is None:
            raise ContractError(f"{self.id}: unknown code {np.asarray(p['code']).item()!r}")
        lane = str(np.asarray(p.get("lane", np.array(""))).item())
        if bool(p.get("cleared", np.array(False))):
            for j in np.flatnonzero(
                (st["o_kind"] == KIND_CAUTION) & (st["o_code"] == code.index) & (st["o_t_end"] < 0)
            ):
                st["o_t_end"][j] = t
            st["x_open"][code.index] = 0
            return st
        _, cau = self._declare(st, code, t, persist=int(p.get("persistence", np.array(0))), lane=lane)
        if cau >= 0:
            st["x_open"][code.index] += 1
        return st

    def _lru_condition(self, st, p, t: int):
        self._advance_tests(st, t)
        code = self.config.codes.by_code.get(str(np.asarray(p["code"]).item()))
        if code is None:
            return st  # a condition on an LRU this table does not monitor: unobserved
        if bool(p.get("clear", np.array(False))):
            st["t_h"][code.index] = 0.0
        elif bool(p.get("covered", np.array(True))):
            st["t_h"][code.index] = float(p["magnitude"])
        return st

    def _sw_load(self, st, p, t: int):
        st["burst_left"] = np.array(int(_p(self.params, "burst_flights")), np.int64)
        return st

    def _lru_replace(self, st, p, t: int):
        lru = str(np.asarray(p["lru"]).item())
        lrus = self._lrus(self.config)
        if lru not in lrus:
            raise ContractError(f"{self.id}: unknown LRU {lru!r}")
        st["lru_serial"][lrus.index(lru)] = serial_value(str(np.asarray(p["serial"]).item()))
        self._draw_unit_offsets(st, lru)
        for c in self.config.codes.codes:
            if c.lru == lru:
                st["t_h"][c.index] = 0.0  # the faulty unit left with its condition
        return st

    def _ibit(self, st, p, t: int):
        """Ground IBIT/MBIT (weight on wheels): one pass of the selected LRU's tests (sortie_id null)."""
        job = serial_value(str(np.asarray(p["job"]).item()))
        lru = str(np.asarray(p.get("lru", np.array(""))).item())
        mech = str(np.asarray(p.get("kind", np.array("IBIT"))).item())
        if mech not in ("IBIT", "MBIT"):
            raise ContractError("monitor.ibit kind must be IBIT or MBIT")
        npb = int(_p(self.params, "pbit_samples"))
        for c in self.config.codes.codes:
            if c.src != "internal" or (lru and c.lru != lru):
                continue
            k, m, n = self._regime(c.regime)
            nr = self.stream("ground_noise", job=job, sensor=c.code).draws(0, npb)
            ur = self.stream("ground_tail", job=job, sensor=c.code).draws(0, npb)
            mu = st["t_unit"][c.index] + st["t_h"][c.index]
            _, _, fd, _, _ = self._kernel(0.0, np.zeros(len(BIT_INTS), np.int64), mu, nr, ur, k, m, n)
            if fd >= 0:
                self._declare(st, c, t, persist=int(fd) + 1, mech=mech, sortie="")
        return st

    def _ack(self, st, p, t: int):
        n = int(p["n"])
        if not 0 <= n <= st["o_kind"].size:
            raise ContractError("monitor.ack: n out of range")
        st["obs_sent"] = np.array(max(0, int(st["obs_sent"]) - n), np.int64)
        for k in self._empty_outbox():
            st[k] = st[k][n:]
        # open-record pointers move with the outbox; a drained open record stays active (DRAINED)
        for name in ("t_cau", "m_open", "m_cau"):
            a = st[name]
            st[name] = np.where(a >= n, a - n, np.where(a >= 0, DRAINED, a))
        return st

    # ------------------------------------------------------------------ CIR processing
    def _observe(self, st, p, t: int):
        ch = np.asarray(p["ch"], np.int64)
        ts = np.asarray(p["t"], np.int64)
        vs = np.asarray(p["v"], np.float64)
        ok = np.asarray(p["validity"], np.int64) == 0
        if ts.size == 0:
            return st
        order = np.lexsort((ch, ts))
        ch, ts, vs, ok = ch[order], ts[order], vs[order], ok[order]
        if ts.size and int(st["hold_t"].max()) > int(ts[0]):
            raise ContractError(f"{self.id}: CIR chunks must be time-ordered")
        self._advance_tests(st, int(ts[-1]) + 1)
        # limit monitors (per channel, with gates evaluated on held gate-channel values)
        for mi, code in enumerate(self._mon):
            mon = code.monitor
            ci = self._ch_index[mon.channel]
            sel = ch == ci
            if not np.any(sel):
                continue
            tt, vv, valid = ts[sel], vs[sel], ok[sel]
            if mon.gate:
                valid = valid & self._gate(st, ch, ts, vs, ok, tt, mon.gate)
            rate = float(self.config.rates.get(mon.channel, 0.0))
            min_p = int(_p(self.params, "exceed_persist_samples"))
            n_p = max(min_p, math.ceil(mon.persist_s * rate)) if rate > 0 else 1
            n_c = max(1, math.ceil(mon.clear_s * rate)) if rate > 0 else 1
            hyst = abs(mon.limit_eu) * _p(self.params, "exceed_hyst_frac")
            peak, ist, dec, clr, pks = limit_kernel(
                st["m_peak"][mi],
                st["m_ist"][mi],
                tt,
                vv,
                valid,
                limit=mon.limit_eu,
                sense=mon.sense,
                hyst=hyst,
                n_persist=n_p,
                n_clear=n_c,
            )
            st["m_peak"][mi] = peak
            st["m_ist"][mi] = ist
            for j in dec:
                rec, cau = self._declare(st, code, int(tt[j]), persist=n_p)
                if rec >= 0:
                    st["o_limit"][rec] = mon.limit_eu
                st["m_open"][mi] = rec
                st["m_cau"][mi] = cau
                self._count_exceedance(st, code)
            for j, pk in zip(clr, pks, strict=True):
                for name in ("m_open", "m_cau"):
                    r = int(st[name][mi])
                    if r >= 0:
                        st["o_t_end"][r] = int(tt[j])
                        st["o_value"][r] = pk
                    st[name][mi] = -1
            if int(st["m_open"][mi]) >= 0:  # running peak of an open exceedance
                st["o_value"][int(st["m_open"][mi])] = float(peak) * mon.sense
        self._lui_observe(st, ch, ts, vs, ok)
        self._nz_observe(st, ch, ts, vs, ok)
        self._wow_observe(st, ch, ts, vs, ok)
        # hold the latest value of every channel
        for ci in np.unique(ch):
            sel = np.flatnonzero(ch == ci)
            j = sel[-1]
            st["hold_v"][ci] = vs[j]
            st["hold_t"][ci] = ts[j]
            st["hold_ok"][ci] = int(ok[j])
        return st

    def _held_series(self, st, ch, ts, vs, ok, name: str, at: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Value and validity of channel ``name`` at times ``at`` (latest sample at or before them)."""
        ci = self._ch_index[name]
        sel = ch == ci
        gt, gv, gok = ts[sel], vs[sel], ok[sel]
        idx = np.searchsorted(gt, at, side="right") - 1
        have_prev = int(st["hold_t"][ci]) >= 0
        v = np.where(idx >= 0, gv[np.maximum(idx, 0)] if gv.size else 0.0, st["hold_v"][ci])
        good = np.where(
            idx >= 0, gok[np.maximum(idx, 0)] if gok.size else False, bool(st["hold_ok"][ci]) and have_prev
        )
        return np.asarray(v, np.float64), np.asarray(good, bool)

    def _gate(self, st, ch, ts, vs, ok, at, gate: str) -> np.ndarray:
        if gate == "engine_running":
            v, good = self._held_series(st, ch, ts, vs, ok, self.config.n2_gate_channel, at)
            return good & (v >= _p(self.params, "engine_running_n2") * 100.0)
        if gate == "airborne":
            v, good = self._held_series(st, ch, ts, vs, ok, self.config.wow_channel, at)
            return good & (v < 0.5)
        raise ContractError(f"unknown monitor gate {gate!r}")

    def _count_exceedance(self, st, code) -> None:
        idx = {"STR-701": 0, "STR-702": 0, "CWS-701": 1, "STR-703": 2}.get(code.code)
        if idx is not None:
            st["exc_counts"][idx] += 1

    def _lui_observe(self, st, ch, ts, vs, ok) -> None:
        for e, (n2c, ps3c, t5c, plac) in enumerate(self.config.lui_channels):
            sel = ch == self._ch_index[n2c]
            if not np.any(sel):
                continue
            at = ts[sel]
            n2, n2ok = vs[sel], ok[sel]
            ps3, ok3 = self._held_series(st, ch, ts, vs, ok, ps3c, at)
            t5, ok5 = self._held_series(st, ch, ts, vs, ok, t5c, at)
            pla, okp = self._held_series(st, ch, ts, vs, ok, plac, at)
            valid = n2ok & ok3 & ok5 & okp
            f, i, s = lui_kernel(
                st["lui_f"][e], st["lui_i"][e], st["lui_stack"][e], self._gates, at, n2, ps3, t5, pla, valid
            )
            st["lui_f"][e], st["lui_i"][e], st["lui_stack"][e] = f, i, s

    def _nz_observe(self, st, ch, ts, vs, ok) -> None:
        ci = self._ch_index.get(self.config.nz_channel)
        if ci is None:
            return
        sel = (ch == ci) & ok
        if not np.any(sel):
            return
        c, a = nz_counter_kernel(
            st["nz_counts"], st["nz_armed"], self._nz_levels, _p(self.params, "nz_rearm_g"), vs[sel]
        )
        st["nz_counts"], st["nz_armed"] = c, a

    def _wow_observe(self, st, ch, ts, vs, ok) -> None:
        """Airborne state and the take-off record trigger (PLA at IRP or above on the ground)."""
        ci = self._ch_index.get(self.config.wow_channel)
        if ci is None:
            return
        sel = (ch == ci) & ok
        for v in vs[sel]:
            st["clock"][3] = 1 if v < 0.5 else 0
        if int(st["clock"][5]) == 0 and self.config.lui_channels:
            plac = self.config.lui_channels[0][3]
            sp = (ch == self._ch_index[plac]) & ok
            if np.any(sp):
                at = ts[sp]
                wow, good = self._held_series(st, ch, ts, vs, ok, self.config.wow_channel, at)
                hit = np.flatnonzero(
                    good & (wow >= 0.5) & (vs[sp] >= math.degrees(_p(self.params, "pla_irp_deg")))
                )
                if hit.size:
                    t_to = int(at[hit[0]])
                    self._append(
                        st,
                        o_kind=KIND_TAKEOFF,
                        o_t=t_to,
                        o_t_end=t_to + round(_p(self.params, "takeoff_record_s") * 1e9),
                        o_sortie=str(st["sortie_id"]),
                    )
                    st["clock"][5] = 1

    # ------------------------------------------------------------------ counters
    def _slot(self, pid: str, e: int) -> int:
        return self._slots[(pid, e if self._per_engine[pid] else -1)]

    def _add_counter(
        self, st, pid: str, e: int, inc: float, t: int, sid: str, *, validity: int = 0, seq: int = 0
    ) -> None:
        s = self._slot(pid, e)
        st["cum"][s] += inc
        self._append(
            st,
            o_kind=KIND_COUNTER,
            o_code=_CI[pid],
            o_t=t,
            o_sortie=sid,
            o_value=float(st["cum"][s]),
            o_incr=float(inc),
            o_engine=e if self._per_engine[pid] else -1,
            o_validity=validity,
            o_seq=seq,
        )

    def _write_luis(self, st, e: int, totals: Sequence[float], t: int, seq: int, sid: str, gap: bool) -> None:
        """Cumulative LUI records of engine ``e``: cumulative at sortie start + this sortie's running totals
        (written twice per flight, so the second update's increment is the change since the first)."""
        for k, (pid, _) in enumerate(LUI_REPORTED):
            s = self._slot(pid, e)
            new = float(st["cum0"][s]) + float(totals[k])
            self._add_counter(
                st, pid, e, new - float(st["cum"][s]), t, sid, validity=1 if gap else 0, seq=seq
            )

    def _lui_totals(self, f: np.ndarray) -> list[float]:
        vals = [float(f[_LF[k]]) for _, k in LUI_REPORTED]
        vals[4] /= 3600.0  # TAMP [h]
        vals[7] /= 3600.0  # EOT [h]
        return vals

    def _lui_update(self, st, t: int, *, final: bool) -> None:
        """Write the 8 LUIs per engine serial - twice per flight: at landing and at shutdown (A-W1.5-35)."""
        seq = int(st["lui_seq"])
        sid = str(st["sortie_id"])
        for e in range(len(self.config.engine_serials)):
            f, i, s = st["lui_f"][e], st["lui_i"][e], st["lui_stack"][e]
            if final:
                f, i, s = lui_finalize(f, i, s, self._gates)
                st["lui_f"][e], st["lui_i"][e], st["lui_stack"][e] = f, i, s
            self._write_luis(st, e, self._lui_totals(f), t, seq, sid, gap=bool(i[_GAP]))
        st["lui_seq"] = np.array(seq + 1, np.int64)

    def _oac_counters(self, st, p, t: int, *, present_only: bool = False) -> None:
        """Per-sortie OAC usage counters, Nz level crossings and the ground TAC (with the TAC cross-check).

        ``present_only`` (the ``ops.sortie_done`` path, AD-48.2): a discrete count absent from ``p`` writes no
        counter record (rather than a false zero); counters M14 derives from its own observation (Nz levels,
        g/AoA/speed exceedances, AMAGB hours, TAC) are always written."""
        sid = str(st["sortie_id"])
        ne = len(self.config.engine_serials)

        def per_engine(name: str) -> np.ndarray:
            v = np.asarray(p.get(name, np.zeros(ne)), np.float64)
            return np.broadcast_to(v, (ne,)) if v.ndim == 0 else v

        def scalar(name: str) -> float:
            return float(np.sum(np.asarray(p.get(name, np.array(0.0)), np.float64)))

        fh = scalar("flight_time_s") / 3600.0
        eot_h = float(np.max(st["lui_f"][:, _LF["eot_s"]])) / 3600.0 if ne else 0.0
        aircraft = (
            ("USAGE.FLIGHT_HOURS", fh),
            ("USAGE.LANDINGS", scalar("landings")),
            ("USAGE.GEAR_CYCLES", scalar("gear_cycles")),
            ("USAGE.JFS_STARTS.ATTEMPTS", scalar("jfs_attempts")),
            ("USAGE.JFS_STARTS.SUCCESSES", scalar("jfs_successes")),
            ("USAGE.JFS_STARTS.CONSECUTIVE", scalar("jfs_consecutive")),
            ("USAGE.CHUTE_STREAMINGS", scalar("chute_streamings")),
            ("USAGE.BRAKE_APPLICATIONS.COUNT", scalar("brake_count")),
            ("USAGE.BRAKE_APPLICATIONS.ENERGY", scalar("brake_energy_j") / 1.0e6),
            ("USAGE.G_EXCEEDANCE.OVER_G", float(st["exc_counts"][0])),
            ("USAGE.G_EXCEEDANCE.OVER_AOA", float(st["exc_counts"][1])),
            ("USAGE.G_EXCEEDANCE.OVERSPEED", float(st["exc_counts"][2])),
            ("USAGE.AMAGB_HOURS", eot_h),
            *((f"STRUCT.NZ_COUNTERS.L{k + 1}", float(st["nz_counts"][k])) for k in range(8)),
        )
        source = {
            "USAGE.FLIGHT_HOURS": "flight_time_s",
            "USAGE.LANDINGS": "landings",
            "USAGE.GEAR_CYCLES": "gear_cycles",
            "USAGE.JFS_STARTS.ATTEMPTS": "jfs_attempts",
            "USAGE.JFS_STARTS.SUCCESSES": "jfs_successes",
            "USAGE.JFS_STARTS.CONSECUTIVE": "jfs_consecutive",
            "USAGE.CHUTE_STREAMINGS": "chute_streamings",
            "USAGE.BRAKE_APPLICATIONS.COUNT": "brake_count",
            "USAGE.BRAKE_APPLICATIONS.ENERGY": "brake_energy_j",
        }

        def written(pid: str) -> bool:
            return not present_only or pid not in source or source[pid] in p

        for pid, inc in aircraft:
            if written(pid):
                self._add_counter(st, pid, -1, inc, t, sid)
        ab, starts, relights = per_engine("ab_lights"), per_engine("starts"), per_engine("air_relights")
        lo, hi = _p(self.params, "tac_min_per_fh") * 3600.0, _p(self.params, "tac_max_per_fh") * 3600.0
        for e in range(ne):
            for pid, name, v in (
                ("USAGE.AB_LIGHTS", "ab_lights", ab),
                ("USAGE.ENGINE_STARTS.GROUND_STARTS", "starts", starts),
                ("USAGE.ENGINE_STARTS.AIR_RELIGHTS", "air_relights", relights),
            ):
                if not present_only or name in p:
                    self._add_counter(st, pid, e, float(v[e]), t, sid)
            # ground TAC from this sortie's ECMS counts, cross-checked against the per-hour TAC band
            f = st["lui_f"][e]
            dtac = f[_LF["type1"]] + f[_LF["type3"]] / 4.0 + f[_LF["type4"]] / 40.0
            gap = bool(st["lui_i"][e][_GAP])
            plausible = fh <= 0.0 or lo * fh <= dtac <= hi * fh
            validity = 1 if gap else (0 if plausible else 3)  # NO_COMPUTED_DATA / NORMAL / FAILURE_WARNING
            self._add_counter(st, "USAGE.TAC", e, float(dtac), t, sid, validity=validity)

    def _usage_summary(self, st, p, t: int):
        """Usage mode: the ECMS LUIs and OAC counters of a sortie from its usage summary (no CIR)."""
        u = SortieUsage.from_payload(p)
        sid = str(st["sortie_id"]) or serial_value(u.sortie_id)
        st["sortie_id"] = np.array(sid, _ID)
        st["cum0"] = st["cum"].copy()
        for e in range(len(self.config.engine_serials)):
            fe = np.zeros(len(LUI_FLOATS))
            for name in (
                "type1",
                "type3",
                "type4",
                "eftc",
                "src_h",
                "ps3_full",
                "ps3_partial",
                "eot_s",
                "tamp_s",
            ):
                fe[_LF[name]] = getattr(u, name)[e]
            st["lui_f"][e] = fe
            st["lui_i"][e] = 0
            self._write_luis(st, e, self._lui_totals(fe), t, 0, sid, gap=False)
        st["nz_counts"] = np.asarray(u.nz_counts, np.float64)
        payload = {
            "flight_time_s": np.array(u.flight_time_s),
            "landings": np.array(u.landings),
            "gear_cycles": np.array(u.gear_cycles),
            "ab_lights": np.asarray(u.ab_lights),
            "starts": np.asarray(u.starts),
            "chute_streamings": np.array(u.chute_streamings),
            "jfs_attempts": np.array(u.jfs_starts),
            "jfs_successes": np.array(u.jfs_starts),
            "brake_count": np.array(u.landings),
            "brake_energy_j": np.array(float(sum(u.brake_energy_j))),
        }
        self._oac_counters(st, payload, t)
        st["lui_seq"] = np.array(1, np.int64)
        return st

    # ------------------------------------------------------------------ read-out
    def outbox_size(self, state: State) -> int:
        return int(state["o_kind"].size)

    def takeoff_records(self, state: State) -> list[tuple[str, int, int]]:
        """ECMS take-off records (sortie, start, end; kernel ns). Contract v0 has no topic or pointer row for
        them (A-W1.5-40); event snapshot windows are carried as ``snapshot_t_start`` / ``snapshot_t_end``."""
        sel = np.flatnonzero(state["o_kind"] == KIND_TAKEOFF)
        return [(str(state["o_sortie"][j]), int(state["o_t"][j]), int(state["o_t_end"][j])) for j in sel]


def cws_words_at(module: MonitoringModule, state: State, t_ns: np.ndarray) -> dict[str, np.ndarray]:
    """CWS words at kernel times ``t_ns`` from the caution records in the outbox (exact edge times).

    The held outputs change when M14 handles an event; with CIR delivered in chunks that is later than the
    sample that opened or closed a caution. The recorder's ``external=`` supply (AD-42) can use this instead:
    call it before ``monitor.ack`` drains the records of the frames concerned. Ground (IBIT/MBIT) cautions,
    which have no sortie, are excluded, as they are from the held words.
    """
    cws = module.config.cws
    if cws is None:
        raise ContractError(f"{module.id}: no CWS map configured")
    t = np.asarray(t_ns, np.int64).reshape(-1)
    sel = np.flatnonzero(
        (np.asarray(state["o_kind"]) == KIND_CAUTION) & (np.asarray(state["o_sortie"]) != "")
    )
    act = np.zeros((t.size, len(module.config.codes.codes)), bool)
    for j in sel:
        t1 = int(state["o_t_end"][j])
        on = (t >= int(state["o_t"][j])) & ((t1 < 0) | (t < t1))
        act[on, int(state["o_code"][j])] = True
    return cws.series(act)
