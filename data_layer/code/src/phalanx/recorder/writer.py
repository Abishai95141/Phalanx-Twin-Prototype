"""Recorder writer: one IRIG 106 Ch10 recording per sortie (architecture §6 M16, AD-24, AD-38).

File layout (IRIG 106-15 Ch10 §10.5.1, §10.6):

1. the setup record (Computer-Generated F1, channel 0): the M01 TMATS with the dictionary's recorder setup
   (recording events and time index, rule R-REC-SETUP, A-W0.3-44) plus the caller's event types
   (``setup_record``; dictionary 0.1.2 migration, W2.2: M16 no longer overlays these attributes itself);
2. the first dynamic packet is a time packet; time packets follow at every time-code mark (>= 1 Hz);
3. data packets per recorder channel (1553 F1 per bus, ARINC-429 F0 per link, PCM F1 for FTI), each holding
   at most 100 ms of data (§10.6.1 d) and committed when its 100 ms timer expires; packets are written in
   commit order;
4. recording events (Computer-Generated F2) for recorder events (start, time-source lock lost/regained)
   and caller events (e.g. M14 BIT/caution events), on their own channel;
5. node index packets (Computer-Generated F3) with an entry for every time and event packet, and a root
   index packet as the last packet (§10.6.7.4).

**Sequence numbers** are 8 bits per channel and wrap (§10.6.1.1 f). The ground decoder counts packets
cumulatively per channel (AD-38); the truth table here uses the same cumulative count.

**Time tags.** A 1553 message's IPTS is the RTC at the bit named by the CSDW time-tag bits (default 01,
"first bit of the first word", i.e. the command word, as in every 1553 packet of the public KC-135 sample)
plus the bus-monitor latency; an ARINC-429 word is tagged at its first bit (via the packet time and gap
times); a PCM minor frame at its first sync bit.

**PROXY (A-W1.7-11): one recording per sortie for all sinks.** The CDR, ECMS log, HUMS DAU and OAC
maintenance log are not yet separate recordings with their own subsets, rates and clocks (AD-25): this file is
the bus-monitor capture of every recorded bus and link. ``test_recorder_writer.py::
test_proxy_single_recording_has_no_sink_subsets`` exposes the limitation. Replacement needs a recording/sink
field in the contract (t_record has a per-recording origin) and per-sink setup records from M01.

Outputs carry restricted **truth** (clock, outages, the CIR row behind every recorded item); the ground
decoder never reads it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

import numpy as np
import pyarrow as pa

from phalanx.bus.clocks import SortieIdentity, key_value
from phalanx.bus.encoder import BusTraffic
from phalanx.bus.icd import FTI_SYNC_WORD
from phalanx.bus.schedule import WORD_NS
from phalanx.core.rng import KeyPath, RngService, StreamDecl, Variate
from phalanx.dictionary.tmats import generate_tmats
from phalanx.ground.rid import check_recording_identity

from . import ch10
from .setup import EventDef, RecorderChannels, recorder_channels
from .timesource import (
    IRIG_B,
    RecorderClock,
    TimePacket,
    lock_loss_episodes,
    time_packets,
)

__all__ = [
    "RECORDER_EVENT_ROLES",
    "STREAMS",
    "TRUTH_SCHEMA",
    "PacketTable",
    "RecorderConfig",
    "Recording",
    "RecordingEvent",
    "index_interval_s",
    "recorder_events",
    "setup_record",
    "write_recording",
]

SUBSYSTEM = "recorder"
STREAMS: tuple[StreamDecl, ...] = (
    StreamDecl(
        SUBSYSTEM,
        "rtc_offset",
        ("scenario", "serial"),
        Variate.NORMAL,
        block_size=16,
        owner="M16",
        description="Recorder crystal fractional frequency offset (standard normal x sigma_ppm)",
    ),
    StreamDecl(
        SUBSYSTEM,
        "rtc_start",
        ("scenario", "tail", "sortie"),
        Variate.RAW,
        block_size=16,
        owner="M16",
        description="Arbitrary initial RTC count of the recording",
    ),
    StreamDecl(
        SUBSYSTEM,
        "lock_loss",
        ("scenario", "tail", "sortie"),
        Variate.UNIFORM,
        block_size=256,
        owner="M16",
        description="Time-source lock-loss episodes (2 draws per episode)",
    ),
    StreamDecl(
        SUBSYSTEM,
        "download",
        ("scenario", "tail", "sortie"),
        Variate.UNIFORM,
        block_size=16,
        owner="M16",
        description="Download outcome and delay draws (download.py)",
    ),
)

#: The recorder-event roles the writer emits. Their definitions (description, TMATS type, event number) are
#: the dictionary's recorder setup (``Dictionary.recording_events()``, rule R-REC-SETUP, A-W0.3-44): one
#: source of truth for the setup record and the event packets (dictionary 0.1.2 migration, W2.2).
REC_START_ID = "REC_START"
LOCK_LOST_ID = "TIME_LOCK_LOST"
LOCK_REGAINED_ID = "TIME_LOCK_REGAINED"
RECORDER_EVENT_ROLES = (REC_START_ID, LOCK_LOST_ID, LOCK_REGAINED_ID)

TTB_LAST_BIT_LAST_WORD = 0
TTB_FIRST_BIT_FIRST_WORD = 1
TTB_LAST_BIT_COMMAND = 2
BSW_TIMEOUT = 1 << 9

TRUTH_SCHEMA = pa.schema(
    [
        pa.field("channel_id", pa.string(), nullable=False),  # Ch10 channel ID, decimal (record_id component)
        pa.field("seq", pa.uint64(), nullable=False),  # cumulative packet count of the channel
        pa.field("msg_index", pa.uint64(), nullable=False),  # message / word / frame index in the packet
        pa.field("param_id", pa.string(), nullable=False),
        pa.field("cir_row", pa.int64(), nullable=False),  # CIR row behind the value (-1: no data)
        pa.field("t_tag", pa.int64(), nullable=False),  # true sim-UTC instant of the Ch10 time-tag bit
        pa.field("rtc", pa.int64(), nullable=False),  # IPTS (RTC ticks)
        pa.field(
            "dup", pa.bool_(), nullable=False
        ),  # duplicate poll (same buffer update as the previous poll)
    ],
    metadata={"phalanx.restricted": "true", "phalanx.description": "W1.7 transmission truth (RESTRICTED)"},
)


@dataclass(frozen=True)
class RecorderConfig:
    """M16 parameters (``configs/<platform>/params/M16.yaml``)."""

    rtc_offset_sigma_ppm: float
    lock_loss_rate_per_h: float
    outage_median_s: float
    outage_sigma_ln: float
    monitor_latency_ns: int
    ttb: int = TTB_FIRST_BIT_FIRST_WORD
    packet_span_ticks: int = 1_000_000  # 100 ms at 10 MHz (§10.6.1 d)
    rtc_start_bits: int = 40

    @classmethod
    def from_params(cls, platform: str = "tejas", **overrides: object) -> RecorderConfig:
        from phalanx.dictionary.params import load_params

        p = load_params("M16", platform=platform)
        r = p["recorder"]
        t = p["time_source"]
        cfg = cls(
            rtc_offset_sigma_ppm=float(r.value("rtc_offset_sigma")) * 1e6,
            lock_loss_rate_per_h=float(t.value("lock_loss_rate")) * 3600.0,
            outage_median_s=float(t.value("outage_median")),
            outage_sigma_ln=float(t.value("outage_sigma_ln")),
            monitor_latency_ns=round(r.value("monitor_latency") * 1e9),
            ttb=int(r.value("time_tag_bits")),
            packet_span_ticks=round(r.value("packet_span") * 1e7),
        )
        return cls(**{**cfg.__dict__, **overrides}) if overrides else cfg


@dataclass(frozen=True)
class RecordingEvent:
    """An event to record (TMATS event id, sim-UTC instant)."""

    event_id: str
    t_ns: int
    description: str = ""
    kind: str = "O"


@dataclass(frozen=True)
class PacketTable:
    """Every packet of the file in file order."""

    offset: np.ndarray
    length: np.ndarray
    channel_id: np.ndarray
    data_type: np.ndarray
    seq: np.ndarray  # 8-bit header value
    cum_seq: np.ndarray  # cumulative count within the channel
    rtc: np.ndarray


@dataclass(frozen=True)
class Recording:
    """A written recording plus restricted truth about how it was produced."""

    data: bytes
    setup_text: str
    channels: RecorderChannels
    t_start: int
    t_end: int
    clock: RecorderClock  # truth
    outages: tuple  # truth
    time_packets: tuple[TimePacket, ...]
    packets: PacketTable
    event_defs: tuple[EventDef, ...]
    events: pa.Table  # truth: event_id, number, count, t_ns, rtc
    truth: pa.Table  # TRUTH_SCHEMA
    #: contract 0.2.0 (A-W0.4-22): the recording's identity within its sortie and its dictionary sink (AD-25);
    #: both None for the single unattributed bus-monitor capture (PROXY A-W1.7-11)
    recording_id: str | None = None
    sink: str | None = None


# ------------------------------------------------------------------------------------------------ setup
def recorder_events(dictionary) -> tuple[EventDef, ...]:
    """The recorder's own event types in TMATS order (event number = position), from the dictionary's
    recorder setup (``Dictionary.recording_events()``, A-W0.3-44). Every role the writer emits must be
    declared there."""
    evs = tuple(EventDef(e["id"], e["description"], e["type"]) for e in dictionary.recording_events())
    missing = [r for r in RECORDER_EVENT_ROLES if r not in {e.event_id for e in evs}]
    if missing:
        raise ValueError(f"the dictionary recorder setup lacks the recorder events {missing}")
    return evs


def index_interval_s(dictionary) -> int:
    """Time-based recording index interval [s]: one node index packet per this many time packets, from the
    dictionary's recorder setup (``recorder_setup()["index"]``, A-W0.3-44; the TMATS ``ITV`` says the
    same)."""
    idx = dictionary.recorder_setup()["index"]
    if idx.get("type") != "time" or int(idx["interval_s"]) < 1:
        raise ValueError(f"unsupported recorder index setup {dict(idx)}")
    return int(idx["interval_s"])


def setup_record(
    dictionary, event_defs: Sequence[EventDef] = (), *, pcm_unpopulated: Sequence[str] = ()
) -> str:
    """The recording's setup record: the M01 TMATS with the dictionary's recorder setup (recording events and
    time index, ``generate_tmats(recording=True)``) and ``event_defs`` after the recorder's own events.
    ``pcm_unpopulated``: FTI PCM words no producer populated in this recording; they are not described, so the
    ground emits no zero-fill records for them (W2.2, the AD-54 deviation closed)."""
    extra = [{"id": e.event_id, "description": e.description, "type": e.kind} for e in event_defs]
    return generate_tmats(
        dictionary.compiled.content,
        recording=True,
        extra_events=extra,
        pcm_unpopulated=tuple(pcm_unpopulated),
    )


def unpopulated_pcm_words(traffic: BusTraffic) -> tuple[str, ...]:
    """FTI PCM items with no CIR source anywhere in the recording (all frame rows -1): spare slots."""
    if traffic.pcm is None:
        return ()
    rows = traffic.pcm.rows
    items = traffic.pcm.frame_def.items
    return tuple(sorted(it.channel_id for j, it in enumerate(items) if not bool(np.any(rows[:, j] >= 0))))


# ------------------------------------------------------------------------------------------------ helpers
def _windows(rtc: np.ndarray, span: int) -> list[tuple[int, int]]:
    """Greedy packet windows: each starts at the first unplaced item and holds items < start + span."""
    out = []
    i, n = 0, int(rtc.size)
    while i < n:
        j = int(np.searchsorted(rtc, rtc[i] + span, side="left"))
        j = max(j, i + 1)
        out.append((i, j))
        i = j
    return out


@dataclass
class _Pending:
    close: int
    rank: int
    channel: int
    data_type: int
    rtc: int
    body: bytes
    checksum: int
    kind: str  # data | time | event
    truth: tuple | None = None  # (truth row slice, msg_index array) to stamp with seq


def _clock(rng: RngService, ident: SortieIdentity, cfg: RecorderConfig, t_ref: int) -> RecorderClock:
    z = float(
        rng.stream(
            KeyPath.of(
                scenario=key_value(ident.scenario),
                serial=ident.recorder_unit(),
                subsystem=SUBSYSTEM,
                component="rtc_offset",
            )
        ).draws(0, 1)[0]
    )
    off = Fraction(int(np.rint(z * cfg.rtc_offset_sigma_ppm * 1000.0)), 1000)
    raw = int(rng.stream(ident.key(subsystem=SUBSYSTEM, component="rtc_start")).draws(0, 1)[0])
    rtc0 = raw & ((1 << cfg.rtc_start_bits) - 1)
    return RecorderClock(rtc0=rtc0, t_ref=int(t_ref), offset_ppm=off)


# ------------------------------------------------------------------------------------------------ writer
def write_recording(
    traffic: BusTraffic,
    ident: SortieIdentity,
    rng: RngService,
    cfg: RecorderConfig,
    *,
    events: Sequence[RecordingEvent] = (),
    event_defs: Sequence[EventDef] = (),
    recording_id: str | None = None,
    sink: str | None = None,
) -> Recording:
    """Write the Ch10 recording of ``traffic`` (its window must start on a whole second, see ``timesource``).

    ``event_defs`` declares caller event types in addition to the recorder's own (order = event numbers after
    the recorder events); every ``events[i].event_id`` must be declared. ``recording_id`` / ``sink`` name the
    recording within its sortie (contract 0.2.0, A-W0.4-22; both None for the single bus-monitor capture).
    They label the recording for the ground (the download carries them); the file bytes do not depend on them.
    """
    check_recording_identity(recording_id, sink)
    t0, t1 = traffic.t0, traffic.t1
    d = traffic.icd.dictionary
    defs = (*recorder_events(d), *event_defs)
    number = {e.event_id: k for k, e in enumerate(defs)}
    for e in events:
        if e.event_id not in number:
            raise ValueError(f"event {e.event_id!r} is not declared in event_defs")
    setup = setup_record(d, event_defs, pcm_unpopulated=unpopulated_pcm_words(traffic))
    interval = index_interval_s(d)
    chans = recorder_channels(setup)
    events_ch, index_ch = chans.max_id + 1, chans.max_id + 2
    clock = _clock(rng, ident, cfg, t0)
    outages = lock_loss_episodes(
        rng,
        ident.key(subsystem=SUBSYSTEM, component="lock_loss"),
        t0 + 10**9,
        t1,
        rate_per_h=cfg.lock_loss_rate_per_h,
        median_s=cfg.outage_median_s,
        sigma_ln=cfg.outage_sigma_ln,
    )
    tps = time_packets(clock, t0, t1, outages)
    pending: list[_Pending] = []
    truth_parts: list[dict[str, np.ndarray]] = []
    span = cfg.packet_span_ticks

    # ---- time packets
    for tp in tps:
        body = ch10.time_body(tp.utc_ms, fmt=IRIG_B, src=tp.src)
        pending.append(_Pending(tp.rtc, 1, chans.time, ch10.DT_TIME_F1, tp.rtc, body, 2, "time"))

    # ---- 1553 buses
    for bt in traffic.buses:
        cid = chans.mil1553[bt.bus]
        if len(bt) == 0:
            continue
        if cfg.ttb == TTB_LAST_BIT_LAST_WORD:
            tag = bt.t_end
        elif cfg.ttb == TTB_FIRST_BIT_FIRST_WORD:
            tag = bt.t_cmd
        else:
            tag = bt.t_cmd + WORD_NS
        ipts = clock.rtc(tag + cfg.monitor_latency_ns)
        bsw = np.where(bt.timeout, BSW_TIMEOUT, 0).astype(np.uint16)
        gap = np.clip(np.rint(bt.response_ns / 100.0), 0, 255).astype(np.uint16)
        item_param = np.array(
            [m.items[k].param_id for m in bt.schedule.messages for k in range(len(m.items))], dtype=object
        )
        item_base = np.concatenate([[0], np.cumsum([len(m.items) for m in bt.schedule.messages])])
        txn_of_item = bt.item_txn
        for a, b in _windows(ipts, span):
            body = ch10.ms1553_body(
                cfg.ttb, ipts[a:b], bsw[a:b], gap[a:b], bt.words, bt.word_offsets[a : b + 1]
            )
            close = int(ipts[a]) + span if b < ipts.size else int(ipts[b - 1]) + 1
            lo, hi = np.searchsorted(txn_of_item, [a, b])
            sl = slice(int(lo), int(hi))
            tr = {
                "param_id": item_param[item_base[bt.msg[txn_of_item[sl]]] + bt.item_idx[sl]],
                "msg_index": (txn_of_item[sl] - a).astype(np.uint64),
                "cir_row": bt.item_row[sl],
                "t_tag": tag[txn_of_item[sl]],
                "rtc": ipts[txn_of_item[sl]],
                "dup": bt.item_dup[sl],
            }
            pending.append(
                _Pending(close, 2, cid, ch10.DT_MS1553_F1, int(ipts[a]), body, 3, "data", (cid, tr))
            )

    # ---- ARINC-429 links
    for lw in traffic.links:
        cid = chans.arinc429[lw.link]
        if lw.t_start.size == 0:
            continue
        rt = clock.rtc(lw.t_start + cfg.monitor_latency_ns)  # first data bit of each word (§10.6.8)
        for a, b in _windows(rt, span):
            gaps = np.concatenate([[0], np.diff(rt[a:b])])
            body = ch10.arinc429_body(
                np.zeros(b - a, np.uint32), np.full(b - a, lw.high_speed), gaps, lw.word[a:b]
            )
            close = int(rt[a]) + span if b < rt.size else int(rt[b - 1]) + 1
            tr = {
                "param_id": np.array(
                    [lw.labels[k].item.param_id for k in lw.label[a:b].tolist()], dtype=object
                ),
                "msg_index": np.arange(b - a, dtype=np.uint64),
                "cir_row": lw.row[a:b],
                "t_tag": lw.t_start[a:b],
                "rtc": rt[a:b],
                "dup": np.zeros(b - a, dtype=bool),
            }
            pending.append(
                _Pending(close, 2, cid, ch10.DT_ARINC429_F0, int(rt[a]), body, 3, "data", (cid, tr))
            )

    # ---- FTI PCM (test aircraft only)
    if traffic.pcm is not None and traffic.pcm.frame.size:
        pf = traffic.pcm
        cid = chans.pcm[pf.frame_def.stream]
        rt = clock.rtc(pf.t_start + cfg.monitor_latency_ns)  # first bit of each minor frame (§10.6.2.2 g)
        sync = np.array([(FTI_SYNC_WORD >> 12) & 0xFFF, FTI_SYNC_WORD & 0xFFF], dtype=np.uint16)
        frames16 = np.concatenate([np.tile(sync, (pf.frame.size, 1)), pf.words & 0x0FFF], axis=1)
        params = [it.param_id for it in pf.frame_def.items]
        for a, b in _windows(rt, span):
            body = ch10.pcm_unpacked_body(rt[a:b], frames16[a:b])
            close = int(rt[a]) + span if b < rt.size else int(rt[b - 1]) + 1
            nf, ni = b - a, len(params)
            tr = {
                "param_id": np.tile(np.array(params, dtype=object), nf),
                "msg_index": np.repeat(np.arange(nf, dtype=np.uint64), ni),
                "cir_row": pf.rows[a:b].reshape(-1),
                "t_tag": np.repeat(pf.t_start[a:b], ni),
                "rtc": np.repeat(rt[a:b], ni),
                "dup": np.zeros(nf * ni, dtype=bool),
            }
            pending.append(_Pending(close, 2, cid, ch10.DT_PCM_F1, int(rt[a]), body, 3, "data", (cid, tr)))

    # ---- recording events: recorder start, lock lost / regained, caller events
    ev_list = [(t0, REC_START_ID)]
    for o in outages:
        ev_list.append((o.start, LOCK_LOST_ID))
        if o.end < t1:
            ev_list.append((o.end, LOCK_REGAINED_ID))
    ev_list += [(int(e.t_ns), e.event_id) for e in events if t0 <= int(e.t_ns) < t1]
    ev_list.sort(key=lambda x: (x[0], number[x[1]]))
    ev_t = np.array([x[0] for x in ev_list], dtype=np.int64)
    ev_num = np.array([number[x[1]] for x in ev_list], dtype=np.int64)
    ev_cnt = np.zeros(ev_num.size, dtype=np.int64)
    seen: dict[int, int] = {}
    for k, nmb in enumerate(ev_num.tolist()):
        ev_cnt[k] = seen.get(nmb, 0) & 0xFFFF
        seen[nmb] = seen.get(nmb, 0) + 1
    ev_rtc = clock.rtc(ev_t)
    for a, b in _windows(ev_rtc, span):
        body = ch10.event_body(ev_rtc[a:b], ev_num[a:b], ev_cnt[a:b])
        close = int(ev_rtc[a]) + span
        pending.append(_Pending(close, 3, events_ch, ch10.DT_COMPUTER_F2, int(ev_rtc[a]), body, 3, "event"))

    # ---- file assembly in commit order, with node/root index packets
    pending.sort(key=lambda p: (p.close, p.rank, p.channel))
    parts: list[bytes] = []
    meta: list[tuple[int, int, int, int, int, int]] = []  # offset, length, channel, type, seq8, rtc
    seq_ctr: dict[int, int] = {}
    offset = 0

    def emit(channel: int, data_type: int, rtc: int, body: bytes, checksum: int) -> tuple[int, int]:
        nonlocal offset
        cum = seq_ctr.get(channel, 0)
        seq_ctr[channel] = cum + 1
        pk = ch10.packet(channel, data_type, cum & 0xFF, rtc, body, checksum=checksum)
        parts.append(pk)
        meta.append((offset, len(pk), channel, data_type, cum & 0xFF, rtc))
        start = offset
        offset += len(pk)
        return start, cum

    emit(0, ch10.DT_COMPUTER_F1, clock.rtc_at(t0), ch10.tmats_body(setup), 2)
    index_entries: list[tuple[int, int, int, int]] = []  # rtc, channel, type, offset
    node_packets: list[tuple[int, int]] = []  # rtc, offset
    n_time = 0
    for p in pending:
        start, cum = emit(p.channel, p.data_type, p.rtc, p.body, p.checksum)
        if p.truth is not None:
            cid, tr = p.truth
            truth_parts.append(
                {
                    **tr,
                    "channel_id": np.full(tr["msg_index"].size, str(cid), dtype=object),
                    "seq": np.full(tr["msg_index"].size, cum, dtype=np.uint64),
                }
            )
        if p.kind in ("time", "event"):
            index_entries.append((p.rtc, p.channel, p.data_type, start))
        if p.kind == "time":
            n_time += 1
            if n_time % interval == 0:
                e = np.array(index_entries, dtype=np.int64)
                node_start, _ = emit(
                    index_ch,
                    ch10.DT_COMPUTER_F3,
                    p.rtc,
                    ch10.index_node_body(e[:, 0], e[:, 1], e[:, 2], e[:, 3]),
                    3,
                )
                node_packets.append((p.rtc, node_start))
                index_entries = []
    last_rtc = int(meta[-1][5])
    if index_entries:
        e = np.array(index_entries, dtype=np.int64)
        node_start, _ = emit(
            index_ch,
            ch10.DT_COMPUTER_F3,
            last_rtc,
            ch10.index_node_body(e[:, 0], e[:, 1], e[:, 2], e[:, 3]),
            3,
        )
        node_packets.append((last_rtc, node_start))
    npk = np.array(node_packets, dtype=np.int64).reshape(-1, 2)
    root_body = ch10.index_root_body(npk[:, 0], npk[:, 1], last_rtc, offset)
    emit(index_ch, ch10.DT_COMPUTER_F3, last_rtc, root_body, 3)

    data = b"".join(parts)
    m = np.array(meta, dtype=np.int64)
    cum = np.zeros(m.shape[0], dtype=np.int64)
    ctr: dict[int, int] = {}
    for k, ch in enumerate(m[:, 2].tolist()):
        cum[k] = ctr.get(ch, 0)
        ctr[ch] = cum[k] + 1
    table = PacketTable(m[:, 0], m[:, 1], m[:, 2], m[:, 3], m[:, 4], cum, m[:, 5])
    if truth_parts:
        cols = {f.name: np.concatenate([tp[f.name] for tp in truth_parts]) for f in TRUTH_SCHEMA}
        truth = pa.Table.from_pydict(
            {k: pa.array(v, type=TRUTH_SCHEMA.field(k).type) for k, v in cols.items()}, schema=TRUTH_SCHEMA
        )
    else:
        truth = TRUTH_SCHEMA.empty_table()
    ev_table = pa.table(
        {
            "event_id": pa.array([defs[k].event_id for k in ev_num.tolist()], pa.string()),
            "number": pa.array(ev_num, pa.int64()),
            "count": pa.array(ev_cnt, pa.int64()),
            "t_ns": pa.array(ev_t, pa.int64()),
            "rtc": pa.array(ev_rtc, pa.int64()),
        }
    )
    return Recording(
        data,
        setup,
        chans,
        t0,
        t1,
        clock,
        outages,
        tps,
        table,
        tuple(defs),
        ev_table,
        truth,
        recording_id,
        sink,
    )
