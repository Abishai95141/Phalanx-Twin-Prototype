"""CIR -> bus traffic: MIL-STD-1553B transactions, ARINC-429 words and FTI PCM frames (architecture §6 M15).

Mechanism (architecture §8; report §13 "t_bus = LRU compute latency + wait for the BC's next poll"):

1. Each RT LRU updates the transmit buffer of a message at its own buffer-update instants ``u_j``: every
   k-th tick of its oscillator (``clocks.LruOscillator``), k = frame / update rate. The data written at
   ``u_j`` are the latest CIR samples acquired at or before ``u_j`` (``u_j - relay latency`` for items an
   RT relays from another LRU, e.g. ADC words relayed by the DFCC over RS-422), and the write completes
   ``L_proc`` later: ``w_j = u_j + L_proc``.
2. The BC polls the message at ``p_k`` (``schedule.BcSchedule`` on the BC oscillator). The RT answers with
   the buffer of the latest write ``w_j <= p_k``.
3. **Duplicates and skips come only from this schedule mismatch** (AD-06): a poll that sees the same write
   as the previous poll is a duplicate; a write no poll sees is skipped. There is no independent dropout
   process and no slip sentinel on digital words (architecture §7; refuted P4, E3).

Words follow the synthetic ICD (``words``): validity words first (bit set = item not NORMAL or no data;
dictionary code table ``mil1553_validity_bit``), then item words in word order. The status word carries the
RT address and the flag bits of the RT's ``AV.RT.STATUS.<LRU>`` CIR stream (zero flags when the stream is
absent). An RT whose LRU has no CIR stream at all does not answer (response timeout, command word only).

ARINC-429 labels are sent by their transmitter once per transmit cycle (the label's rate group, on the
transmitter's crystal), back to back with a 4-bit-time gap (ARINC 429). FTI PCM minor frames are sent at the
FTI DAS frame rate (test aircraft only).

Outputs carry **truth** (CIR row of every transmitted item, buffer-update index, duplicate flag): it is
restricted data, used for tests, statistics and full-path truth labels, never by the ground decoder.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING

import numpy as np
import pyarrow.compute as pc

from phalanx.core.rng import KeyPath, RngService
from phalanx.core.time import ClockDomain

from .clocks import SUBSYSTEM, LruOscillator, SortieIdentity, key_value, lru_oscillator
from .icd import BusIcd, Item, Label429, Message1553, PcmFrameDef
from .schedule import GAP_TO_DEAD_NS, WORD_NS, BcSchedule, build_schedule
from .words import arinc429_words, encode_item_words

if TYPE_CHECKING:
    import pyarrow as pa

    from phalanx.ground.cir import CirBatch

__all__ = [
    "BusConfig",
    "BusTraffic",
    "BusTransactions",
    "CirStream",
    "LinkWords",
    "PcmFrames",
    "check_cir_on_oscillator",
    "cir_streams",
    "encode_bus",
]

STATUS_FLAG_MASK = 0x07FF  # bits 10..0 of the status word (bits 15..11 are the RT address)
STATUS_BUSY = 1 << 3
STATUS_MESSAGE_ERROR = 1 << 10
EVENT_GROUPS = frozenset({"EVT", "SORTIE", "INSP"})


@dataclass(frozen=True)
class BusConfig:
    """M15 parameters (``configs/<platform>/params/M15.yaml``, SI units converted to ns where integer)."""

    sigma_ppm: float
    rt_response_ns: tuple[int, int]
    gap_ns: int
    frame_start_ns: int
    processing_latency_ns: int
    relay_latency_ns: int
    arinc_gap_bits: int
    arinc_high_bps: float
    arinc_low_bps: float
    offset_override_ppm: Mapping[str, float] = field(default_factory=dict)
    phase_override_ns: Mapping[str, int] = field(default_factory=dict)

    @classmethod
    def from_params(cls, platform: str = "tejas", **overrides: object) -> BusConfig:
        from phalanx.dictionary.params import load_params

        p = load_params("M15", platform=platform)
        c = p["clocks"]
        b = p["mil1553"]
        a = p["arinc429"]
        cfg = cls(
            sigma_ppm=float(c.value("lru_offset_sigma")) * 1e6,
            rt_response_ns=(
                round(b.value("rt_response_min") * 1e9),
                round(b.value("rt_response_max") * 1e9),
            ),
            gap_ns=round(b.value("intermessage_gap") * 1e9),
            frame_start_ns=round(b.value("minor_frame_start") * 1e9),
            processing_latency_ns=round(c.value("processing_latency") * 1e9),
            relay_latency_ns=round(c.value("relay_latency") * 1e9),
            arinc_gap_bits=int(a.value("word_gap_bits")),
            arinc_high_bps=float(a.value("high_speed_rate")),
            arinc_low_bps=float(a.value("low_speed_rate")),
        )
        return cls(**{**cfg.__dict__, **overrides}) if overrides else cfg


@dataclass(frozen=True)
class CirStream:
    """One CIR acquisition stream, sorted by t_sample (rows refer to the CIR table)."""

    t: np.ndarray
    value: np.ndarray
    normal: np.ndarray  # bool: validity == NORMAL
    validity: np.ndarray  # object (str)
    row: np.ndarray


def cir_streams(icd: BusIcd, table: pa.Table) -> dict[str, CirStream]:
    """Group a CIR table into streams keyed by dictionary channel_id (bus-carried channels only).

    Rows of streams that are not dictionary channels raise; dictionary channels that are not on a recorded
    bus (internal, RS-422, download...) are ignored here.
    """
    d = icd.dictionary
    ident: dict[tuple[str, str, str | None], str] = {}
    for ch in d.channels():
        loc = d.contract_location(ch["channel_id"])
        ident[(loc["param_id"], loc["source_lru"], loc["lane"])] = ch["channel_id"]
    on_bus = {it.channel_id for it in icd.items}
    n = table.num_rows
    # stream code per row from dictionary-encoded columns (no per-row Python)
    code = np.zeros(n, dtype=np.int64)
    uniq: list[list] = []
    for name in ("param_id", "source_lru", "lane"):
        enc = pc.dictionary_encode(table.column(name).combine_chunks(), null_encoding="encode")
        uniq.append(enc.dictionary.to_pylist())
        code = code * (len(enc.dictionary) + 1) + enc.indices.to_numpy(zero_copy_only=False).astype(np.int64)
    combos, inv = np.unique(code, return_inverse=True)
    inv = np.asarray(inv).reshape(-1)
    keys = []
    for cv in combos.tolist():
        parts = []
        for u in reversed(uniq):
            cv, r = divmod(cv, len(u) + 1)
            parts.append(u[r])
        keys.append(tuple(reversed(parts)))
    unknown = sorted({k for k in keys if k not in ident}, key=lambda k: (k[0], k[1], k[2] or ""))
    if unknown:
        raise ValueError(f"bus encoder: CIR streams are not dictionary channels: {unknown[:10]}")
    t = table.column("t_sample").to_numpy()
    v = table.column("value").to_numpy()
    venc = pc.dictionary_encode(table.column("validity").combine_chunks())
    vsym = np.array(venc.dictionary.to_pylist(), dtype=object)
    vcode = venc.indices.to_numpy(zero_copy_only=False)
    order_all = np.lexsort((t, inv))
    starts = np.searchsorted(inv[order_all], np.arange(len(keys) + 1))
    out: dict[str, CirStream] = {}
    for k, key in sorted(enumerate(keys), key=lambda kv: ident[kv[1]]):
        cid = ident[key]
        if cid not in on_bus:
            continue
        order = order_all[starts[k] : starts[k + 1]]
        val = vsym[vcode[order]]
        out[cid] = CirStream(
            t=t[order].astype(np.int64),
            value=v[order].astype(np.float64),
            normal=val == "NORMAL",
            validity=val,
            row=order.astype(np.int64),
        )
    return out


@dataclass(frozen=True)
class BusTransactions:
    """All recorded transactions of one 1553 bus, in time order.

    ``words[word_offsets[i]:word_offsets[i+1]]`` are the words of transaction i in bus order (command,
    status if any, data). ``timeout[i]``: the RT did not answer (command word only).
    """

    bus: str
    schedule: BcSchedule
    msg: np.ndarray  # int64, index into schedule.messages
    poll: np.ndarray  # int64, absolute minor-frame index of the poll
    t_cmd: np.ndarray  # int64 ns: first bit of the command word
    t_end: np.ndarray  # int64 ns: last bit of the last word
    response_ns: np.ndarray  # int64 (0 for broadcast / timeout)
    timeout: np.ndarray  # bool
    word_offsets: np.ndarray  # int64 (n+1,)
    words: np.ndarray  # uint16
    update: np.ndarray  # int64: buffer-update index read by the poll (-1: none) -- truth
    # per transmitted item (truth): transaction row, item index, CIR row (-1: no data), duplicate flag
    item_txn: np.ndarray
    item_idx: np.ndarray
    item_row: np.ndarray
    item_dup: np.ndarray

    def __len__(self) -> int:
        return int(self.msg.size)


@dataclass(frozen=True)
class LinkWords:
    """ARINC-429 words of one link, in time order (t_start = first bit of the word)."""

    link: str
    high_speed: bool
    labels: tuple[Label429, ...]
    label: np.ndarray  # int64 index into labels
    t_start: np.ndarray
    word: np.ndarray  # uint32, bus order
    row: np.ndarray  # CIR row (-1: no data) -- truth
    cycle: np.ndarray  # transmit-cycle index -- truth


@dataclass(frozen=True)
class PcmFrames:
    """FTI PCM minor frames (t_start = first sync bit)."""

    frame_def: PcmFrameDef
    frame: np.ndarray  # int64 minor-frame index
    t_start: np.ndarray
    words: np.ndarray  # uint16 (n, n_words) 12-bit data words
    rows: np.ndarray  # int64 (n, n_items) CIR rows (-1: no data) -- truth
    bit_ns: float  # nominal bit time


@dataclass(frozen=True)
class BusTraffic:
    """Everything M15 put on the recorded buses and links during ``[t0, t1)``."""

    t0: int
    t1: int
    icd: BusIcd
    buses: tuple[BusTransactions, ...]
    links: tuple[LinkWords, ...]
    pcm: PcmFrames | None
    oscillators: Mapping[str, LruOscillator]
    rt_response_ns: Mapping[tuple[str, int], int]


# ------------------------------------------------------------------------------------------------ helpers
def _instants(domain: ClockDomain, t_lo: int, t_hi: int) -> tuple[int, np.ndarray]:
    """(first index, instants) of ``domain`` in ``[t_lo, t_hi)``."""
    n0, n1 = domain.indices_in(max(int(t_lo), 0), int(t_hi))
    return n0, domain.sample_times_ns(n0, n1 - n0)


def _update_domain(osc: LruOscillator, rate_hz: float) -> ClockDomain:
    k = osc.frame_hz / Fraction(rate_hz).limit_denominator(10**6)
    if k.denominator == 1:
        return osc.sub_domain(Fraction(rate_hz).limit_denominator(10**6), 0)
    # a non-integer ratio: same crystal (same offset and phase), own divider -> phase-locked, not a subset
    return ClockDomain(
        f"{osc.lru}.{rate_hz}", Fraction(rate_hz).limit_denominator(10**6), osc.offset_ppm, osc.phase_ns
    )


def _latest(t: np.ndarray, at: np.ndarray) -> np.ndarray:
    """Index of the latest t <= at (-1 if none)."""
    return np.searchsorted(t, at, side="right") - 1


def _rt_response(rng: RngService, ident: SortieIdentity, lru: str, lo: int, hi: int) -> int:
    u = float(
        rng.stream(
            KeyPath.of(
                scenario=key_value(ident.scenario),
                serial=ident.serial_of(lru),
                subsystem=SUBSYSTEM,
                component="rt_response",
            )
        ).draws(0, 1)[0]
    )
    return int(lo + np.floor(u * (hi - lo + 1)))


# ------------------------------------------------------------------------------------------------ encoder
def encode_bus(
    cir: CirBatch | pa.Table,
    icd: BusIcd,
    config: BusConfig,
    ident: SortieIdentity,
    rng: RngService,
    *,
    t0: int,
    t1: int,
    fti_fitted: bool = False,
    oscillators: Mapping[str, LruOscillator] | None = None,
) -> BusTraffic:
    """Put a CIR batch on the recorded buses during ``[t0, t1)`` (sim-UTC ns).

    Pure function of (CIR, dictionary, config, identity, root seed): the timing (oscillators, schedule,
    response times) depends only on identity-keyed draws, so forks of a sortie share it (CRN, I8).

    ``oscillators`` gives the crystal of an LRU explicitly (LRU name -> oscillator); at integration these are
    M13's acquisition clocks (``clocks.acquisition_oscillators``, A-W1.6-21), so an LRU's bus updates and its
    acquisitions share one crystal. LRUs not listed use the keyed draws (``clocks.lru_oscillator``).
    """
    table = cir.table if hasattr(cir, "table") else cir
    streams = cir_streams(icd, table)
    d = icd.dictionary
    content = d.content
    lrus = content["lrus"]
    group_hz = {g: v.get("rate_hz") for g, v in content["rate_groups"].items()}

    osc_cache: dict[str, LruOscillator] = {}

    def osc(lru: str) -> LruOscillator:
        if lru not in osc_cache:
            f = lrus[lru].get("frame_hz")
            if f is None:
                raise ValueError(f"LRU {lru} has no frame_hz in the dictionary")
            if oscillators and lru in oscillators:
                given = oscillators[lru]
                if given.lru != lru or given.frame_hz != Fraction(f).limit_denominator(10**6):
                    raise ValueError(f"oscillator for {lru} disagrees with the dictionary frame rate {f} Hz")
                osc_cache[lru] = given
                return given
            osc_cache[lru] = lru_oscillator(
                lru,
                f,
                ident,
                rng,
                sigma_ppm=config.sigma_ppm,
                offset_override_ppm=config.offset_override_ppm,
                phase_override_ns=config.phase_override_ns,
            )
        return osc_cache[lru]

    present: set[str] = set()
    for m in icd.messages:
        if any(it.channel_id in streams for it in m.items):
            present.add(m.rt_lru)
    lo, hi = config.rt_response_ns
    responses: dict[tuple[str, int], int] = {}
    buses = []
    for bus in icd.bus_names:
        msgs = icd.messages_on(bus)
        if not msgs:
            continue
        bc = icd.bus_controller(bus)
        resp = {}
        for m in msgs:
            if m.has_status and m.rt not in resp:
                resp[m.rt] = _rt_response(rng, ident, m.rt_lru, lo, hi)
                responses[(bus, m.rt)] = resp[m.rt]
        sched = build_schedule(
            icd,
            bus,
            minor_hz=group_hz["AV50"],
            group_hz=group_hz,
            response_ns=resp,
            gap_ns=config.gap_ns,
            frame_start_ns=config.frame_start_ns,
        )
        buses.append(_encode_one_bus(sched, streams, osc, osc(bc), present, config, t0, t1))
    links = []
    for link in icd.link_names:
        lbs = icd.labels_on(link)
        if lbs and any(lb.item.channel_id in streams for lb in lbs):
            links.append(_encode_link(link, lbs, streams, osc(lbs[0].transmitter), config, group_hz, t0, t1))
    pcm = None
    if fti_fitted and icd.pcm is not None:
        pcm = _encode_pcm(icd.pcm, streams, osc(icd.pcm.transmitter), t0, t1)
    return BusTraffic(int(t0), int(t1), icd, tuple(buses), tuple(links), pcm, dict(osc_cache), responses)


def _item_values(
    items: tuple[Item, ...],
    streams: Mapping[str, CirStream],
    rt_lru: str,
    upd_t: np.ndarray,
    relay_ns: int,
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    """Per item: CIR rows, NORMAL flags and values at buffer-update instants ``upd_t``."""
    rows, normal, vals = [], [], []
    for it in items:
        s = streams.get(it.channel_id)
        if s is None or upd_t.size == 0:
            rows.append(np.full(upd_t.size, -1, dtype=np.int64))
            normal.append(np.zeros(upd_t.size, dtype=bool))
            vals.append(np.zeros(upd_t.size, dtype=np.float64))
            continue
        cutoff = upd_t - (relay_ns if it.source_lru != rt_lru else 0)
        k = _latest(s.t, cutoff)
        ok = k >= 0
        kk = np.where(ok, k, 0)
        rows.append(np.where(ok, s.row[kk], -1))
        normal.append(ok & s.normal[kk])
        vals.append(np.where(ok, s.value[kk], 0.0))
    return rows, normal, vals


def _encode_one_bus(
    sched: BcSchedule,
    streams: Mapping[str, CirStream],
    osc,
    bc_osc: LruOscillator,
    present: set[str],
    cfg: BusConfig,
    t0: int,
    t1: int,
) -> BusTransactions:
    minor = bc_osc.tick_domain()
    if minor.f_nom_hz != sched.minor_hz:
        raise ValueError(f"{sched.bus}: BC frame {minor.f_nom_hz} Hz != minor frame {sched.minor_hz} Hz")
    max_off = int(sched.offset_ns.max(initial=0)) + int(sched.duration_ns.max(initial=0))
    m0, frame_t = _instants(minor, t0 - max_off - 1, t1)
    frame_idx = m0 + np.arange(frame_t.size, dtype=np.int64)
    pieces = []
    for i, m in enumerate(sched.messages):
        rows_sel = sched.msg == i
        fmod = sched.frame_mod[rows_sel]
        offs = sched.offset_ns[rows_sel]
        # polls: frames whose index mod hyper matches one of this message's slots
        lut = np.full(sched.hyper, -1, dtype=np.int64)
        lut[fmod] = offs
        off = lut[frame_idx % sched.hyper]
        sel = off >= 0
        p = frame_t[sel] + off[sel]
        fr = frame_idx[sel]
        keep = (p >= t0) & (p < t1)
        p, fr = p[keep], fr[keep]
        pieces.append(_message_polls(i, m, p, fr, sched, streams, osc, present, cfg))
    # merge in time order
    order_key = np.concatenate([pc["t_cmd"] for pc in pieces]) if pieces else np.zeros(0, np.int64)
    msg_all = np.concatenate([pc["msg"] for pc in pieces]) if pieces else np.zeros(0, np.int64)
    order = np.lexsort((msg_all, order_key))
    cat = {
        k: np.concatenate([pc[k] for pc in pieces])
        for k in ("msg", "poll", "t_cmd", "t_end", "resp", "timeout", "update", "nwords")
    }
    for k in cat:
        cat[k] = cat[k][order]
    # words: ragged per piece -> reorder
    piece_words = [pc["words"] for pc in pieces]
    piece_nw = [pc["nwords"] for pc in pieces]
    flat = np.concatenate([w for w in piece_words]) if piece_words else np.zeros(0, np.uint16)
    nw_all = np.concatenate(piece_nw) if piece_nw else np.zeros(0, np.int64)
    src_off = np.concatenate([[0], np.cumsum(nw_all)]).astype(np.int64)
    nw_sorted = nw_all[order]
    dst_off = np.concatenate([[0], np.cumsum(nw_sorted)]).astype(np.int64)
    idx = np.repeat(src_off[:-1][order], nw_sorted) + (
        np.arange(int(dst_off[-1]), dtype=np.int64) - np.repeat(dst_off[:-1], nw_sorted)
    )
    words = flat[idx]
    # item truth: remap transaction rows
    inv = np.empty_like(order)
    inv[order] = np.arange(order.size)
    base = np.concatenate([[0], np.cumsum([pc["msg"].size for pc in pieces])]).astype(np.int64)
    it_txn = np.concatenate([inv[base[j] + pc["item_txn"]] for j, pc in enumerate(pieces)])
    it_idx = np.concatenate([pc["item_idx"] for pc in pieces])
    it_row = np.concatenate([pc["item_row"] for pc in pieces])
    it_dup = np.concatenate([pc["item_dup"] for pc in pieces])
    io = np.lexsort((it_idx, it_txn))
    return BusTransactions(
        bus=sched.bus,
        schedule=sched,
        msg=cat["msg"],
        poll=cat["poll"],
        t_cmd=cat["t_cmd"],
        t_end=cat["t_end"],
        response_ns=cat["resp"],
        timeout=cat["timeout"].astype(bool),
        word_offsets=dst_off,
        words=words.astype(np.uint16),
        update=cat["update"],
        item_txn=it_txn[io],
        item_idx=it_idx[io],
        item_row=it_row[io],
        item_dup=it_dup[io].astype(bool),
    )


def _status_flags(streams: Mapping[str, CirStream], lru: str, at: np.ndarray) -> np.ndarray:
    s = streams.get(f"AV.RT.STATUS.{lru}")
    if s is None or at.size == 0:
        return np.zeros(at.size, dtype=np.int64)
    k = _latest(s.t, at)
    v = np.where(k >= 0, s.value[np.maximum(k, 0)], 0.0)
    return np.rint(v).astype(np.int64) & STATUS_FLAG_MASK


def _message_polls(
    i: int,
    m: Message1553,
    p: np.ndarray,
    frames: np.ndarray,
    sched: BcSchedule,
    streams: Mapping[str, CirStream],
    osc,
    present: set[str],
    cfg: BusConfig,
) -> dict[str, np.ndarray]:
    n = p.size
    resp = int(sched.response_ns[i])
    is_bc = m.kind == "broadcast"
    answers = is_bc or (m.rt_lru in present)
    out: dict[str, np.ndarray] = {
        "msg": np.full(n, i, np.int64),
        "poll": frames.astype(np.int64),
        "t_cmd": p.astype(np.int64),
    }
    cmd = np.full(n, m.command_word, dtype=np.uint16)
    empty_items = {
        "item_txn": np.zeros(0, np.int64),
        "item_idx": np.zeros(0, np.int64),
        "item_row": np.zeros(0, np.int64),
        "item_dup": np.zeros(0, bool),
    }
    if not answers:
        # response timeout: the monitor records the command word only (Ch10 block status TM)
        out.update(
            t_end=p + WORD_NS,
            resp=np.zeros(n, np.int64),
            timeout=np.ones(n, np.int64),
            update=np.full(n, -1, np.int64),
            nwords=np.ones(n, np.int64),
            words=cmd,
            **empty_items,
        )
        return out
    status = None
    if m.has_status:
        flags = _status_flags(streams, m.rt_lru, p)
        status = ((m.rt << 11) | flags).astype(np.uint16)
    if m.kind == "mc_status":
        busy = np.zeros(n, dtype=bool)
        data = np.zeros((n, 0), dtype=np.uint16)
        update = np.full(n, -1, np.int64)
        rows = [_status_rows(streams, m.items[0], p)]
        dup = [np.zeros(n, dtype=bool)]
    else:
        o = osc(m.rt_lru)
        ud = _update_domain(o, m.update_hz)
        span = int(np.ceil(1e9 / m.update_hz)) * 2 + cfg.processing_latency_ns
        p_lo = int(p.min()) if p.size else 0
        p_hi = int(p.max()) if p.size else 0
        j0, ut = _instants(ud, p_lo - span, p_hi + 1)
        wt = ut + cfg.processing_latency_ns
        jl = _latest(wt, p)
        has = jl >= 0
        update = np.where(has, j0 + jl, -1).astype(np.int64)
        u_at = np.where(has, ut[np.maximum(jl, 0)], np.iinfo(np.int64).min // 2)
        rows, normal, vals = _item_values(m.items, streams, m.rt_lru, u_at, cfg.relay_latency_ns)
        rows = [np.where(has, r, -1) for r in rows]
        normal = [nm & has for nm in normal]
        prev = np.concatenate([[-2], update[:-1]])
        dup_poll = (update == prev) & has
        dup = []
        for it in m.items:
            periodic = it.acq_group not in EVENT_GROUPS
            dup.append(dup_poll & periodic)
        data = np.zeros((n, m.data_words), dtype=np.uint16)
        nv = m.n_validity_words
        for k_it, it in enumerate(m.items):
            w, _sat = encode_item_words(it, vals[k_it])
            w = np.where(rows[k_it][:, None] >= 0, w, 0)
            c0 = int(it.first_word) - 1
            data[:, c0 : c0 + it.words] = w
            if nv:
                bit = np.where(normal[k_it], 0, 1).astype(np.uint16) << np.uint16(int(it.validity_bit))
                data[:, int(it.validity_word) - 1] |= bit
        busy = np.zeros(n, dtype=bool)
        if status is not None:
            busy = (status.astype(np.int64) & (STATUS_BUSY | STATUS_MESSAGE_ERROR)) != 0
    # assemble wire words
    cols = [cmd[:, None]]
    if status is not None:
        cols.append(status[:, None])
    width = 1 + (1 if status is not None else 0) + data.shape[1]
    mat = np.concatenate([*cols, data], axis=1) if data.shape[1] else np.concatenate(cols, axis=1)
    nwords = np.where(busy, 1 + (1 if status is not None else 0), width).astype(np.int64)
    words = mat.reshape(-1)[_ragged_index(width, nwords)]
    if is_bc:
        t_end = p + WORD_NS * nwords
    else:
        t_end = p + WORD_NS * nwords + (resp - GAP_TO_DEAD_NS)
    out.update(
        t_end=t_end.astype(np.int64),
        resp=np.full(n, resp if m.has_status else 0, np.int64),
        timeout=np.zeros(n, np.int64),
        update=update,
        nwords=nwords,
        words=words.astype(np.uint16),
    )
    # item truth (only items whose words were sent)
    sent = ~busy
    txn = np.flatnonzero(sent)
    k_items = len(m.items)
    out["item_txn"] = np.repeat(txn, k_items)
    out["item_idx"] = np.tile(np.arange(k_items, dtype=np.int64), txn.size)
    out["item_row"] = np.stack(rows, axis=1)[txn].reshape(-1) if k_items else np.zeros(0, np.int64)
    out["item_dup"] = np.stack(dup, axis=1)[txn].reshape(-1) if k_items else np.zeros(0, bool)
    return out


def _status_rows(streams: Mapping[str, CirStream], item: Item, p: np.ndarray) -> np.ndarray:
    s = streams.get(item.channel_id)
    if s is None:
        return np.full(p.size, -1, np.int64)
    k = _latest(s.t, p)
    return np.where(k >= 0, s.row[np.maximum(k, 0)], -1)


def _ragged_index(width: int, nwords: np.ndarray) -> np.ndarray:
    """Flat indices of the first nwords[i] columns of each row of an (n, width) matrix."""
    n = nwords.size
    starts = np.arange(n, dtype=np.int64) * width
    total = int(nwords.sum())
    off = np.concatenate([[0], np.cumsum(nwords)])[:-1]
    return np.repeat(starts, nwords) + (np.arange(total, dtype=np.int64) - np.repeat(off, nwords))


def _encode_link(
    link: str,
    labels: tuple[Label429, ...],
    streams: Mapping[str, CirStream],
    o: LruOscillator,
    cfg: BusConfig,
    group_hz: Mapping[str, float],
    t0: int,
    t1: int,
) -> LinkWords:
    high = labels[0].high_speed
    bps = cfg.arinc_high_bps if high else cfg.arinc_low_bps
    word_slot_ns = (32 + cfg.arinc_gap_bits) * 1e9 / bps
    rates = sorted({group_hz[lb.group] for lb in labels}, reverse=True)
    lab_i, t_s, words, rows, cyc = [], [], [], [], []
    # each rate group is one transmit cycle on the transmitter's crystal; labels go out back to back
    for rate in rates:
        grp = [k for k, lb in enumerate(labels) if group_hz[lb.group] == rate]
        dom = _update_domain(o, rate)
        c0, ct = _instants(dom, t0 - cfg.processing_latency_ns - 1, t1)
        for pos, k in enumerate(grp):
            lb = labels[k]
            ts = ct + cfg.processing_latency_ns + round(pos * word_slot_ns)
            keep = (ts >= t0) & (ts < t1)
            s = streams.get(lb.item.channel_id)
            if s is None:  # transmitter alive, no data for this label: No Computed Data, zero data field
                ok = np.zeros(ct.size, dtype=bool)
                vals = np.zeros(ct.size, dtype=np.float64)
                val = np.full(ct.size, "NO_COMPUTED_DATA", dtype=object)
                row = np.full(ct.size, -1, dtype=np.int64)
            else:
                kk = _latest(s.t, ct)
                ok = kk >= 0
                vals = np.where(ok, s.value[np.maximum(kk, 0)], 0.0)
                val = np.where(ok, s.validity[np.maximum(kk, 0)], "NO_COMPUTED_DATA")
                row = np.where(ok, s.row[np.maximum(kk, 0)], -1)
            w, _sat = arinc429_words(lb.label, lb.sdi, lb.item, vals, val)
            lab_i.append(np.full(int(keep.sum()), k, np.int64))
            t_s.append(ts[keep])
            words.append(w[keep])
            rows.append(row[keep])
            cyc.append((c0 + np.arange(ct.size, dtype=np.int64))[keep])
    if not t_s:
        z = np.zeros(0, np.int64)
        return LinkWords(link, high, labels, z, z, np.zeros(0, np.uint32), z, z)
    t_all = np.concatenate(t_s)
    lab_all = np.concatenate(lab_i)
    order = np.lexsort((lab_all, t_all))
    return LinkWords(
        link=link,
        high_speed=high,
        labels=labels,
        label=lab_all[order],
        t_start=t_all[order].astype(np.int64),
        word=np.concatenate(words)[order].astype(np.uint32),
        row=np.concatenate(rows)[order].astype(np.int64),
        cycle=np.concatenate(cyc)[order].astype(np.int64),
    )


def _encode_pcm(
    fd: PcmFrameDef, streams: Mapping[str, CirStream], o: LruOscillator, t0: int, t1: int
) -> PcmFrames:
    dom = _update_domain(o, fd.minor_frame_hz)
    f0, ft = _instants(dom, t0, t1)
    n = ft.size
    words = np.zeros((n, fd.n_words), dtype=np.uint16)
    rows = np.full((n, len(fd.items)), -1, dtype=np.int64)
    for j, it in enumerate(fd.items):
        s = streams.get(it.channel_id)
        if s is None or n == 0:
            continue
        k = _latest(s.t, ft)
        ok = k >= 0
        vals = np.where(ok, s.value[np.maximum(k, 0)], 0.0)
        w, _sat = encode_item_words(it, vals)
        words[:, int(it.first_word) - 1] = np.where(ok, w[:, 0], 0)
        rows[:, j] = np.where(ok, s.row[np.maximum(k, 0)], -1)
    bit_ns = 1e9 / (fd.frame_bits * fd.minor_frame_hz)
    return PcmFrames(fd, f0 + np.arange(n, dtype=np.int64), ft.astype(np.int64), words, rows, bit_ns)


def check_cir_on_oscillator(
    stream_t: np.ndarray,
    osc: LruOscillator,
    *,
    rate_hz: float | Fraction | None = None,
    tol_ns: int = 0,
) -> bool:
    """True when every CIR t_sample of a stream lies on its LRU crystal (integration check, W2.2).

    ``rate_hz`` None: the LRU frame grid. Otherwise the crystal at the stream's acquisition rate (same offset
    and phase; every k-th frame tick when the rate divides the frame rate). A sample counts as on the grid
    when it is at most ``tol_ns`` after the latest grid instant at or before it.
    """
    if rate_hz is None:
        dom = osc.tick_domain()
    else:
        rate = Fraction(rate_hz).limit_denominator(10**6)
        dom = ClockDomain(f"{osc.lru}@{rate}", rate, osc.offset_ppm, osc.phase_ns)
    t = np.asarray(stream_t, dtype=np.int64)
    if t.size == 0:
        return True
    n0 = max(dom.index_at_or_before(int(t.min())), 0)
    n1 = dom.index_at_or_before(int(t.max())) + 1
    if n1 <= n0:
        return False
    grid = dom.sample_times_ns(n0, n1 - n0)
    k = np.searchsorted(grid, t, side="right") - 1
    ok = k >= 0
    return bool(np.all(ok) and np.all(t - grid[np.maximum(k, 0)] <= tol_ns))
