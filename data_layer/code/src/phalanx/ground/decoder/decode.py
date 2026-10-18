"""Ground decoder: Ch10 recording -> contract ``param.samples`` with ``provenance = full_path`` (arch §6 M17).

The output is validated against the **same** Arrow schema as the fast path (``load_contract("v0")``, AD-12,
A5). The decoder is a pure function of (recording bytes, dictionary, linkage keys, delivery time, decoder
parameters): it never sees CIR, truth or simulator state, so it decodes a real Ch10 file the same way.

**Record identity (AD-38).** ``record_id`` = blake2b over (``full_path``, tail, sortie, Ch10 channel ID,
param_id, seq, msg_index) where ``seq`` is the channel's **cumulative** packet count, unwrapped from the 8-bit
header sequence number (a lost or corrupt packet still advances it, so later record ids do not move), and
``msg_index`` the message (1553), word (ARINC-429) or minor frame (PCM) index inside the packet. Contract
0.2.0 (A-W0.4-22): a delivery that names its on-board recording (``recording_id``, ``sink``: the ground
station knows which recorder file it downloaded, as it knows the tail and sortie) qualifies the channel
component as ``<recording_id>:<channel ID>`` and fills the two columns; without one (the single bus-monitor
capture of the W1.7 full path, PROXY A-W1.7-11) both are null and every record id is the 0.1.0 one.

**The six times** (architecture §8; the W1.7 answer to the open ``t_sample`` question, ASSUMPTION A-W1.7-14):

- ``t_record`` = the message's Ch10 time tag (IPTS) x 100 ns (recorder clock, per-recording origin);
- ``t_utc`` = the aircraft time source's time of that tag (``timebase.TimeBase.raw_utc``);
- ``t_bus`` = the decoder's best sim-UTC estimate of the Ch10-defined bit (``TimeBase.best`` minus the
  nominal bus-monitor latency);
- ``t_sample`` = the decoder's estimate of the acquisition instant: ``t_bus`` minus the **nominal** latency
  from acquisition to that bit, built only from what a ground station knows -- the message timing on the wire
  (time-tag bit, word count, recorded response time), the ICD update rate of the producing RT
  (dictionary), and
  declared nominal processing/relay latencies (M17 parameters): ``L = D_tag + L_proc + T_update/2`` (+
  ``L_relay + T_acq/2`` for relayed items). ``latency_model = "none"`` sets ``t_sample = t_bus``. The true
  acquisition instant is CIR/labels-only truth; a decoder of a real recording cannot know it.
- ``t_ingest`` = the delivery's arrival time.

Quality flags set here (bus/recorder/ground scope, plus one acquisition-scope inference):
OUT_OF_RANGE (decoded value outside the dictionary range, as on the fast path), DUPLICATE_POLL (A-W1.7-15),
SENTINEL (A-W1.7-16), TIME_SOURCE_INTERNAL / DECODER_INTERPOLATED / CLOCK_SUSPECT (``timebase``,
A-W1.7-17), DUPLICATE_DOWNLOAD (a repeat delivery of the sortie).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pyarrow as pa

from phalanx.dictionary.contract import Contract, load_contract
from phalanx.ground.fast_path import FastPathConfig
from phalanx.ground.rid import check_recording_identity, full_path_channel_id, record_ids

from .reader import (
    Ch10File,
    Packet,
    read_arinc429,
    read_events,
    read_file,
    read_ms1553,
    read_pcm_unpacked,
    read_time,
)
from .setup import DecoderSetup, SetupMismatch, parse_tmats, setup_from_tmats
from .timebase import TimeBase
from .words import Conversion, a429_fields, code_layout, eu_from_counts, join_words, odd_parity_ok

__all__ = [
    "PROVENANCE",
    "DecodeReport",
    "DecodeResult",
    "DecoderConfig",
    "DecoderError",
    "cumulative_sequence",
    "decode_recording",
]

TOPIC = "param.samples"
PROVENANCE = "full_path"
WORD_NS = 20_000
GAP_TO_DEAD_NS = 2_000
BSW_ERRORS = (1 << 12) | (1 << 10) | (1 << 5) | (1 << 4) | (1 << 3)  # ME, FE, LE, SE, WE (IRIG 106 Fig 10-24)
BSW_TIMEOUT = 1 << 9
ST_TERMINAL_FLAG, ST_SUBSYSTEM_FLAG, ST_BUSY, ST_MESSAGE_ERROR = 1 << 0, 1 << 2, 1 << 3, 1 << 10
EVENT_GROUPS = frozenset({"EVT", "SORTIE", "INSP"})
_C_DCN = re.compile(r"^C-(\d+)\\DCN$")


class DecoderError(ValueError):
    """The recording cannot be decoded (no setup record, wrong dictionary, no time packet...)."""


@dataclass(frozen=True)
class DecoderConfig:
    """M17 parameters (``configs/<platform>/params/M17.yaml``)."""

    processing_latency_ns: int
    relay_latency_ns: int
    monitor_latency_ns: int
    rate_tolerance_ppm: float
    tail_tolerance_s: float
    holdover_tolerance_s: float
    dup_tolerance: float
    sentinel_min_lsb: float
    latency_model: str = "nominal"

    @classmethod
    def from_params(cls, platform: str = "tejas", **overrides: object) -> DecoderConfig:
        from phalanx.dictionary.params import load_params

        p = load_params("M17", platform=platform)
        t = p["timing"]
        q = p["quality"]
        cfg = cls(
            processing_latency_ns=round(t.value("nominal_processing_latency") * 1e9),
            relay_latency_ns=round(t.value("nominal_relay_latency") * 1e9),
            monitor_latency_ns=round(t.value("nominal_monitor_latency") * 1e9),
            rate_tolerance_ppm=float(q.value("rtc_rate_tolerance")) * 1e6,
            tail_tolerance_s=float(q.value("time_tail_tolerance")),
            holdover_tolerance_s=float(q.value("holdover_tolerance")),
            dup_tolerance=float(q.value("duplicate_rate_tolerance")),
            sentinel_min_lsb=float(q.value("sentinel_min_lsb")),
        )
        return cls(**{**cfg.__dict__, **overrides}) if overrides else cfg


@dataclass(frozen=True)
class DecodeReport:
    packets: int
    bad_checksum: int
    sync_errors: int
    truncated: bool
    unknown_messages: int
    timeouts: int
    records: int


@dataclass(frozen=True)
class DecodeResult:
    samples: pa.Table  # contract param.samples (validated)
    events: pa.Table  # decoded recording events (event_id, number, count, rtc, t_utc, t_best)
    report: DecodeReport


def cumulative_sequence(channel: np.ndarray, seq8: np.ndarray) -> np.ndarray:
    """Cumulative packet count per channel in file order, unwrapped from the 8-bit sequence (AD-38).

    The first packet of a channel counts from its own sequence number; each later packet advances by
    ``(seq - previous) mod 256`` (0 counts as a full wrap), so a lost packet still advances the count.
    """
    out = np.zeros(seq8.size, dtype=np.int64)
    last: dict[int, tuple[int, int]] = {}
    for k, (ch, s) in enumerate(zip(channel.tolist(), seq8.tolist(), strict=True)):
        if ch not in last:
            cum = int(s)
        else:
            prev_s, prev_cum = last[ch]
            step = (int(s) - prev_s) % 256
            cum = prev_cum + (step if step else 256)
        out[k] = cum
        last[ch] = (int(s), cum)
    return out


# ------------------------------------------------------------------------------------------------ catalogue
@dataclass(frozen=True)
class _ItemDef:
    channel_id: str
    param_id: str
    conv: Conversion
    words: tuple[int, ...]  # data-word numbers (1-based); () for a status word
    validity_word: int | None
    validity_bit: int | None
    ssm_codes: Mapping[int, str] | None
    acq_lru: str
    acq_period_ns: float
    periodic: bool


def _c_groups(a: Mapping[str, list[str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for k, v in a.items():
        m = _C_DCN.match(k)
        if m:
            c = f"C-{m.group(1)}"
            out[v[0]] = {
                "BFM": a.get(f"{c}\\BFM", ["OTH"])[0],
                "DCT": a.get(f"{c}\\DCT", ["NON"])[0],
                "CO": a.get(f"{c}\\CO", ["0"])[0],
                "CO-1": a.get(f"{c}\\CO-1", ["1"])[0],
            }
    return out


def _item_def(
    d: Any, cid: str, words: tuple[int, ...], cg: Mapping[str, str], mask: int, bits: int
) -> _ItemDef:
    ch = d.channel(cid)
    enc = ch["encoding"]
    if enc["type"] == "code_word":
        conv = Conversion("CODE", bits, 0.0, 1.0, 0, code=code_layout(d))
    elif cg.get("DCT") == "COE" and cg.get("BFM") in ("TWO", "UNS"):
        conv = Conversion(cg["BFM"], bits, float(cg["CO"]), float(cg["CO-1"]), 0)
    else:
        conv = Conversion("DIS", bits, 0.0, 1.0, mask)
    val = ch["validity"]
    ssm = None
    if val["method"] == "ssm":
        ssm = {int(k): v for k, v in d.code_table(val["table"])["codes"].items()}
    acq = ch["rates"]["acquisition"]
    g = d.content["rate_groups"][acq]
    hz = d.lru(ch["acq_lru"]).get("frame_hz") if g["kind"] == "lru_frame" else g.get("rate_hz")
    return _ItemDef(
        channel_id=cid,
        param_id=ch["measurand_id"],
        conv=conv,
        words=words,
        validity_word=val.get("word") if val["method"] == "validity_word" else None,
        validity_bit=val.get("bit") if val["method"] == "validity_word" else None,
        ssm_codes=ssm,
        acq_lru=ch["acq_lru"],
        acq_period_ns=(1e9 / float(hz)) if hz else 0.0,
        periodic=acq not in EVENT_GROUPS and g["kind"] in ("periodic", "lru_frame"),
    )


def _mask(v: str) -> int:
    return 0 if v == "FW" else int(v, 2)


def _update_period_ns(d: Any, rt_lru: str, items: list[_ItemDef]) -> float:
    """ICD transmit-buffer update period: the producer group if declared, else the RT LRU frame."""
    groups = d.content["rate_groups"]
    prods = {d.channel(it.channel_id)["rates"].get("producer") for it in items} - {None}
    if prods:
        return 1e9 / float(groups[sorted(prods)[0]]["rate_hz"])
    hz = d.lru(rt_lru).get("frame_hz")
    return 1e9 / float(hz) if hz else 0.0


class _Rows:
    """Column accumulator for decoded records; strings are kept as small integer codes (no per-row Python)."""

    def __init__(self) -> None:
        self.cols: dict[str, list[np.ndarray]] = {}
        self.items: list[str] = []  # dictionary channel ids, by item code
        self._item_ix: dict[str, int] = {}
        self.vsyms: list[str] = []  # validity symbols, by validity code
        self._v_ix: dict[str, int] = {}

    def add(self, *, item: str, channel_id: int, validity: Any, **kw: Any) -> None:
        n = int(np.asarray(kw["seq"]).size)
        if item not in self._item_ix:
            self._item_ix[item] = len(self.items)
            self.items.append(item)
        v = np.broadcast_to(np.asarray(validity, dtype=object), (n,)).astype(str)
        u, inv = np.unique(v, return_inverse=True)
        for s in u.tolist():
            if s not in self._v_ix:
                self._v_ix[s] = len(self.vsyms)
                self.vsyms.append(s)
        vmap = np.array([self._v_ix[s] for s in u.tolist()], dtype=np.int64)
        self.cols.setdefault("item", []).append(np.full(n, self._item_ix[item], dtype=np.int64))
        self.cols.setdefault("chid", []).append(np.full(n, int(channel_id), dtype=np.int64))
        self.cols.setdefault("vcode", []).append(
            vmap[np.asarray(inv).reshape(-1)] if n else np.zeros(0, np.int64)
        )
        for k, val in kw.items():
            self.cols.setdefault(k, []).append(np.asarray(val))


@dataclass(frozen=True)
class _Ctx:
    d: Any
    setup: DecoderSetup
    tmats: Mapping[str, list[str]]
    cgroups: Mapping[str, Mapping[str, str]]
    tb: TimeBase
    config: DecoderConfig


# ------------------------------------------------------------------------------------------------ decoder
def decode_recording(
    data: bytes,
    *,
    dictionary: Any,
    tail_no: str,
    sortie_id: str,
    t_ingest: int,
    attempt: int = 0,
    engine_serial: str | Mapping[str, str] | None = None,
    config: DecoderConfig,
    contract: Contract | None = None,
    recording_id: str | None = None,
    sink: str | None = None,
) -> DecodeResult:
    """Decode one delivered recording to a validated ``param.samples`` table (see module docstring).

    ``recording_id`` / ``sink``: the delivery's on-board recording (contract 0.2.0); both None or both set.
    """
    check_recording_identity(recording_id, sink)
    c = contract or load_contract("v0")
    d = dictionary
    f = read_file(data)
    if not f.packets or f.packets[0].data_type != 0x01 or not f.packets[0].checksum_ok:
        raise DecoderError("the recording does not start with a valid setup record (TMATS)")
    text = f.body(f.packets[0])[4:].decode("ascii")
    try:
        setup = setup_from_tmats(text, d)
    except SetupMismatch as e:
        raise DecoderError(str(e)) from e
    tmats = parse_tmats(text)
    try:
        tb = TimeBase.from_records(
            read_time(f),
            rate_tolerance_ppm=config.rate_tolerance_ppm,
            tail_tolerance_s=config.tail_tolerance_s,
            holdover_tolerance_s=config.holdover_tolerance_s,
        )
    except ValueError as e:
        raise DecoderError(str(e)) from e
    ctx = _Ctx(d, setup, tmats, _c_groups(tmats), tb, config)
    pk_ch = np.array([p.channel_id for p in f.packets], dtype=np.int64)
    pk_seq = np.array([p.seq for p in f.packets], dtype=np.int64)
    cum = cumulative_sequence(pk_ch, pk_seq)
    rows = _Rows()
    unknown = timeouts = 0
    bus_group = {
        v[0]: k[: -len("\\DLN")] for k, v in tmats.items() if k.startswith("B-") and k.endswith("\\DLN")
    }
    for chid, (link, cdt) in sorted(setup.channels.items()):
        sel = [k for k, p in enumerate(f.packets) if p.channel_id == chid and p.checksum_ok]
        if not sel:
            continue
        pk = tuple(f.packets[k] for k in sel)
        pcum = cum[np.array(sel, dtype=np.int64)]
        sync_err = np.array([p.rtc_sync_error for p in pk], dtype=bool)
        if cdt == "1553IN":
            u, t = _decode_1553(ctx, f, pk, pcum, sync_err, link, bus_group.get(link), chid, rows)
            unknown += u
            timeouts += t
        elif cdt == "429IN":
            unknown += _decode_429(ctx, f, pk, pcum, sync_err, link, chid, rows)
        elif cdt == "PCMIN":
            _decode_pcm(ctx, f, pk, pcum, sync_err, link, chid, rows)
    fp = FastPathConfig.from_dictionary(d, engine_serial=engine_serial)
    table = _assemble(
        c,
        d,
        rows,
        fp,
        tail_no=tail_no,
        sortie_id=sortie_id,
        t_ingest=int(t_ingest),
        attempt=int(attempt),
        config=config,
        recording_id=recording_id,
        sink=sink,
    )
    ev = read_events(f)
    t_ev_raw, _, _ = tb.raw_utc(ev.rtc)
    t_ev_best, _ = tb.best(ev.rtc)
    names = [setup.events[k] if 0 <= k < len(setup.events) else f"#{k}" for k in ev.number.tolist()]
    events = pa.table(
        {
            "event_id": pa.array(names, pa.string()),
            "number": ev.number,
            "count": ev.count,
            "rtc": ev.rtc,
            "t_utc": t_ev_raw,
            "t_best": t_ev_best,
        }
    )
    report = DecodeReport(
        packets=len(f.packets),
        bad_checksum=sum(1 for p in f.packets if not p.checksum_ok),
        sync_errors=f.sync_errors,
        truncated=f.truncated,
        unknown_messages=unknown,
        timeouts=timeouts,
        records=table.num_rows,
    )
    return DecodeResult(table, events, report)


def _times(ctx: _Ctx, rtc: np.ndarray, sync_err: np.ndarray):
    t_utc, internal, _before = ctx.tb.raw_utc(rtc)
    best, fl = ctx.tb.best(rtc)
    t_bus = best - ctx.config.monitor_latency_ns
    return t_utc, t_bus, internal, fl.interpolated, fl.suspect | sync_err


def _tmats_msg_number(
    tmats: Mapping[str, list[str]], bgroup: str | None, rt: int, tr: int, sa: int, wc: int
) -> int:
    if bgroup is None:
        return 0
    n = int(tmats.get(f"{bgroup}\\NMS\\N-1", ["0"])[0])
    for m in range(1, n + 1):
        if (
            int(tmats[f"{bgroup}\\TRA-1-{m}"][0], 2) == rt
            and int(tmats[f"{bgroup}\\TRM-1-{m}"][0]) == tr
            and int(tmats[f"{bgroup}\\STA-1-{m}"][0], 2) == sa
            and int(tmats[f"{bgroup}\\DWC-1-{m}"][0], 2) == wc
        ):
            return m
    return 0


def _decode_1553(
    ctx: _Ctx,
    f: Ch10File,
    pk: tuple[Packet, ...],
    pcum: np.ndarray,
    sync_err: np.ndarray,
    link: str,
    bgroup: str | None,
    chid: int,
    rows: _Rows,
) -> tuple[int, int]:
    d, cfg = ctx.d, ctx.config
    msgs = read_ms1553(f, pk)
    if msgs.ipts.size == 0:
        return 0, 0
    nw = msgs.length // 2
    first = msgs.words[msgs.word_start].astype(np.int64)
    key = first  # the command word identifies the message type: RT | T/R | SA | word count or mode code
    timeout = (msgs.bsw & BSW_TIMEOUT) != 0
    bsw_bad = (msgs.bsw & BSW_ERRORS) != 0
    ttb = msgs.ttb[msgs.packet]
    t_utc, t_bus, internal, interp, suspect = _times(ctx, msgs.ipts, sync_err[msgs.packet])
    validity_code = d.code_table("mil1553_validity_bit")["codes"]
    unknown = 0
    for cmd in np.unique(key).tolist():
        rt, tr, sa, wc = cmd >> 11, (cmd >> 10) & 1, (cmd >> 5) & 31, cmd & 31
        sel = np.flatnonzero((key == cmd) & ~timeout)
        mdef = ctx.setup.messages.get((link, rt, tr, sa, wc))
        if mdef is None:
            unknown += int(sel.size)
            continue
        if sel.size == 0:
            continue
        broadcast = rt == 31 and tr == 0
        has_status = not broadcast
        mc_status = mdef.mode_code and wc == 2
        n_data = 0 if mc_status else (1 if mdef.mode_code else (wc if wc else 32))
        expected = 1 + (1 if has_status else 0) + n_data
        status = (
            msgs.words[msgs.word_start[sel] + 1].astype(np.int64)
            if has_status
            else np.zeros(sel.size, np.int64)
        )
        complete = nw[sel] >= expected
        bus_invalid = bsw_bad[sel] | ((status & (ST_SUBSYSTEM_FLAG | ST_TERMINAL_FLAG)) != 0)
        status_only = (status & (ST_BUSY | ST_MESSAGE_ERROR)) != 0
        dstart = msgs.word_start[sel] + (2 if has_status else 1)
        msg_no = _tmats_msg_number(ctx.tmats, bgroup, rt, tr, sa, wc)
        items = []
        for p, (cid, wnums, mt) in enumerate(mdef.measurands, start=1):
            m = _mask(ctx.tmats.get(f"{bgroup}\\MBM-1-{msg_no}-{p}-1", ["FW"])[0]) if bgroup else 0
            bits = 16 * len(wnums) if mt != "S" else 16
            items.append(_item_def(d, cid, wnums if mt != "S" else (), ctx.cgroups.get(cid, {}), m, bits))
        rt_lru = (
            d.content["buses"]["mil1553"][link]["bc"]
            if broadcast
            else d.channel(items[0].channel_id)["transport"]["rt_lru"]
        )
        # time from the start of the command word to the time-tagged bit (TTB), from the message as recorded
        dur = WORD_NS * nw[sel] + ((msgs.gap[sel] & 0xFF) * 100 - GAP_TO_DEAD_NS if has_status else 0)
        d_tag = np.where(ttb[sel] == 0, dur, np.where(ttb[sel] == 2, WORD_NS, 0)).astype(np.float64)
        t_upd = _update_period_ns(d, rt_lru, items)
        bus_hz = d.content["rate_groups"][d.channel(items[0].channel_id)["rates"]["bus"]]["rate_hz"]
        dup = (
            np.zeros(sel.size, dtype=bool)
            if mc_status
            else _duplicate_polls(msgs, sel, nw, t_upd, 1e9 / float(bus_hz), items, cfg)
        )
        for it in items:
            if not it.words:  # RT status word (mode code 2 response)
                raw = status
                ok = complete
                validity = np.where(bsw_bad[sel], "BUS_INVALID", "NORMAL").astype(object)
                frame_hz = d.lru(rt_lru).get("frame_hz")
                lat = d_tag + (0.5e9 / float(frame_hz) if frame_hz else 0.0)
                it_dup = np.zeros(sel.size, dtype=bool)
            else:
                ok = complete & ~status_only
                wn = np.array(it.words, dtype=np.int64)
                at = (dstart[:, None] + wn[None, :] - 1).clip(0, msgs.words.size - 1)
                raw = join_words(msgs.words[at])
                vbit = np.zeros(sel.size, dtype=np.int64)
                if it.validity_word is not None:
                    vw = msgs.words[(dstart + it.validity_word - 1).clip(0, msgs.words.size - 1)].astype(
                        np.int64
                    )
                    vbit = (vw >> int(it.validity_bit)) & 1
                validity = np.where(vbit == 1, validity_code["1"], validity_code["0"]).astype(object)
                validity = np.where(bus_invalid, "BUS_INVALID", validity).astype(object)
                lat = d_tag + cfg.processing_latency_ns + 0.5 * t_upd
                if it.acq_lru != rt_lru:
                    lat = lat + cfg.relay_latency_ns + 0.5 * it.acq_period_ns
                it_dup = dup & it.periodic
            value, counts = eu_from_counts(raw, it.conv)
            keep = np.flatnonzero(ok)
            if keep.size == 0:
                continue
            idx = sel[keep]
            shift = np.rint(lat[keep]).astype(np.int64) if cfg.latency_model == "nominal" else 0
            rows.add(
                channel_id=chid,
                item=it.channel_id,
                seq=pcum[msgs.packet[idx]],
                msg_index=msgs.msg_index[idx],
                rtc=msgs.ipts[idx],
                t_utc=t_utc[idx],
                t_bus=t_bus[idx],
                t_sample=t_bus[idx] - shift,
                value=value[keep],
                raw=counts[keep],
                validity=validity[keep],
                dup=it_dup[keep],
                internal=internal[idx],
                interp=interp[idx],
                suspect=suspect[idx],
            )
    return unknown, int(timeout.sum())


def _duplicate_polls(
    msgs,
    sel: np.ndarray,
    nw: np.ndarray,
    t_upd: float,
    t_poll: float,
    items: list[_ItemDef],
    cfg: DecoderConfig,
) -> np.ndarray:
    """A-W1.7-15: a poll is a DUPLICATE_POLL when its words (status and data) equal the previous poll's and
    it is at most the ``max_run``-th poll of the run of identical polls, where ``max_run`` is the number of
    polls one producer update can serve (ICD update and poll periods). A longer run is static data, so its
    later polls are not flagged. Causal: only earlier polls are looked at (prefix-stable decoding)."""
    n = sel.size
    out = np.zeros(n, dtype=bool)
    if n < 2 or t_upd <= 0 or t_poll <= 0 or not any(it.periodic for it in items):
        return out
    max_run = math.ceil(t_upd / t_poll * (1.0 + cfg.dup_tolerance))
    if max_run < 2:
        return out
    starts = msgs.word_start[sel] + 1
    lens = nw[sel] - 1
    width = int(lens.max())
    if width <= 0:
        return out
    cols = np.arange(width)
    mat = np.where(
        cols[None, :] < lens[:, None],
        msgs.words[(starts[:, None] + cols[None, :]).clip(0, msgs.words.size - 1)],
        0,
    )
    same = np.zeros(n, dtype=bool)
    same[1:] = np.all(mat[1:] == mat[:-1], axis=1) & (lens[1:] == lens[:-1])
    run_start = np.flatnonzero(~same)
    pos = np.arange(n) - run_start[np.cumsum(~same) - 1] + 1  # 1-based position inside the identical run
    return same & (pos <= max_run)


def _decode_429(ctx: _Ctx, f: Ch10File, pk, pcum, sync_err, link: str, chid: int, rows: _Rows) -> int:
    cfg = ctx.config
    w = read_arinc429(f, pk)
    if w.word.size == 0:
        return 0
    lab, sdi, data, ssm = a429_fields(w.word)
    parity = odd_parity_ok(w.word)
    t_utc, t_bus, internal, interp, suspect = _times(ctx, w.rtc, sync_err[w.packet])
    unknown = 0
    keys = lab * 4 + sdi
    for kv in np.unique(keys).tolist():
        cid = ctx.setup.labels.get((link, kv // 4, kv % 4))
        sel = np.flatnonzero(keys == kv)
        if cid is None:
            unknown += int(sel.size)
            continue
        it = _item_def(ctx.d, cid, (), ctx.cgroups.get(cid, {}), (1 << 19) - 1, 19)
        value, _counts = eu_from_counts(data[sel], it.conv)
        validity = np.array(
            [it.ssm_codes.get(int(x), "FAILURE_WARNING") for x in ssm[sel].tolist()], dtype=object
        )
        validity = np.where(parity[sel], validity, "BUS_INVALID").astype(object)
        lat = (
            round(cfg.processing_latency_ns + 0.5 * it.acq_period_ns) if cfg.latency_model == "nominal" else 0
        )
        rows.add(
            channel_id=chid,
            item=cid,
            seq=pcum[w.packet[sel]],
            msg_index=w.msg_index[sel],
            rtc=w.rtc[sel],
            t_utc=t_utc[sel],
            t_bus=t_bus[sel],
            t_sample=t_bus[sel] - lat,
            value=value,
            raw=w.word[sel].astype(np.int64),
            validity=validity,
            dup=np.zeros(sel.size, dtype=bool),
            internal=internal[sel],
            interp=interp[sel],
            suspect=suspect[sel],
        )
    return unknown


def _decode_pcm(ctx: _Ctx, f: Ch10File, pk, pcum, sync_err, link: str, chid: int, rows: _Rows) -> None:
    n_words = ctx.setup.pcm_frame_words.get(link, 0)
    fr = read_pcm_unpacked(f, pk, n_words + 2)  # two padded sync halves + data words
    if fr.ipts.size == 0:
        return
    t_utc, t_bus, internal, interp, suspect = _times(ctx, fr.ipts, sync_err[fr.packet])
    masks = {}
    for k, v in ctx.tmats.items():
        if re.match(r"^D-\d+\\MN-1-\d+$", k):
            masks[v[0]] = _mask(ctx.tmats.get(k.replace("\\MN-1-", "\\MFM-1-"), ["FW"])[0])
    n = fr.ipts.size
    for word, cid in ctx.setup.pcm_words.get(link, ()):
        it = _item_def(ctx.d, cid, (word,), ctx.cgroups.get(cid, {}), masks.get(cid, 0), 12)
        raw = fr.words16[:, 1 + word].astype(np.int64) & 0xFFF
        value, counts = eu_from_counts(raw, it.conv)
        rows.add(
            channel_id=chid,
            item=cid,
            seq=pcum[fr.packet],
            msg_index=fr.msg_index,
            rtc=fr.ipts,
            t_utc=t_utc,
            t_bus=t_bus,
            t_sample=t_bus.copy(),  # FTI words are sampled at the minor-frame tick that starts the frame
            value=value,
            raw=counts,
            validity="NORMAL",
            dup=np.zeros(n, dtype=bool),
            internal=internal,
            interp=interp,
            suspect=suspect,
        )


def _sentinels(
    d: Any,
    item: np.ndarray,
    value: np.ndarray,
    t: np.ndarray,
    cfg: DecoderConfig,
    names: list[str] | None = None,
) -> np.ndarray:
    """A-W1.7-16: an analog channel's bottom-of-scale value (dictionary range minimum) reached by a jump of
    more than ``sentinel_min_lsb`` LSB from the previous sample of the stream is a slip-window SENTINEL.

    One-sided (causal) version of the DASHlink rule "isolated from both neighbours": decoded records must not
    depend on later data, so a partial download and the complete one decode identically (idempotent ingest).
    Known false positive: a genuine signal that saturates at the bottom of scale in one large step.

    ``item`` holds dictionary channel ids, or integer codes into ``names`` when ``names`` is given.
    """
    if names is None:
        uniq, codes = np.unique(np.asarray(item, dtype=object).astype(str), return_inverse=True)
        names = uniq.tolist()
    else:
        codes = item
    codes = np.asarray(codes, dtype=np.int64).reshape(-1)
    out = np.zeros(codes.size, dtype=bool)
    k = len(names)
    eligible = np.zeros(k, dtype=bool)
    bottom_v = np.zeros(k)
    lsb = np.ones(k)
    for j, cid in enumerate(names):
        ch = d.channel(cid)
        rng = ch.get("range") or {}
        if (
            ch.get("signal") == "analog"
            and ch["encoding"]["type"] in ("bnr", "ubnr")
            and rng.get("min") is not None
        ):
            eligible[j] = True
            bottom_v[j] = float(rng["min"])
            lsb[j] = float(ch["recorder_lsb"])
    if codes.size < 2 or not eligible.any():
        return out
    o = np.lexsort((t, codes))  # by stream, then time; stable (ties keep record order)
    c = codes[o]
    v = np.asarray(value, dtype=np.float64)[o]
    q = lsb[c]
    bottom = np.abs(v - bottom_v[c]) <= 0.5 * q
    jump = np.zeros(v.size, dtype=bool)
    jump[1:] = (c[1:] == c[:-1]) & (np.abs(v[1:] - v[:-1]) > cfg.sentinel_min_lsb * q[1:]) & ~bottom[:-1]
    out[o] = bottom & jump & eligible[c]
    return out


def _const(s: str | None, n: int) -> pa.Array:
    return pa.repeat(pa.scalar(s, pa.string()), n)


def _take(values: list[Any], codes: np.ndarray) -> pa.Array:
    return pa.array(values, pa.string()).take(pa.array(codes, pa.int64()))


def _assemble(
    c: Contract,
    d: Any,
    rows: _Rows,
    fp: FastPathConfig,
    *,
    tail_no: str,
    sortie_id: str,
    t_ingest: int,
    attempt: int,
    config: DecoderConfig,
    recording_id: str | None = None,
    sink: str | None = None,
) -> pa.Table:
    schema = c.schemas[TOPIC]
    if not rows.cols:
        return schema.empty_table()
    col = {k: np.concatenate(v) for k, v in rows.cols.items()}
    item = col["item"].astype(np.int64)
    n = item.size
    qf = c.quality_flags
    # per-item lookups (a few hundred), then broadcast by item code
    locs = [d.contract_location(cid) for cid in rows.items]
    params = [d.channel(cid)["measurand_id"] for cid in rows.items]
    lo_i = np.full(len(rows.items), -np.inf)
    hi_i = np.full(len(rows.items), np.inf)
    for j, loc in enumerate(locs):
        r = (fp.channels or {}).get((loc["param_id"], loc["source_lru"], loc["lane"]))
        if r is not None:
            lo_i[j] = -np.inf if r[0] is None else float(r[0])
            hi_i[j] = np.inf if r[1] is None else float(r[1])
    v = col["value"].astype(np.float64)
    flags = np.zeros(n, dtype=np.uint32)
    flags[(v < lo_i[item]) | (v > hi_i[item])] |= qf.mask("OUT_OF_RANGE")
    flags[col["dup"].astype(bool)] |= qf.mask("DUPLICATE_POLL")
    flags[col["internal"].astype(bool)] |= qf.mask("TIME_SOURCE_INTERNAL")
    flags[col["interp"].astype(bool)] |= qf.mask("DECODER_INTERPOLATED")
    suspect = col["suspect"].astype(bool)
    # data cannot reach the ground before it exists, nor predate 1970: such a time base is wrong
    t_s, t_b, t_u = col["t_sample"], col["t_bus"], col["t_utc"]
    suspect |= (t_s > t_ingest) | (t_b > t_ingest) | (t_u > t_ingest) | (t_s < 0) | (t_b < 0) | (t_u < 0)
    t_b = np.clip(t_b, 0, t_ingest)
    t_s = np.minimum(np.clip(t_s, 0, t_ingest), t_b)
    t_u = np.clip(t_u, 0, t_ingest)
    flags[suspect] |= qf.mask("CLOCK_SUSPECT")
    flags[_sentinels(d, item, v, t_b, config, names=rows.items)] |= qf.mask("SENTINEL")
    if attempt > 0:
        flags |= np.uint32(qf.mask("DUPLICATE_DOWNLOAD"))
    chids, chcode = np.unique(col["chid"].astype(np.int64), return_inverse=True)
    channel_id = _take(
        [full_path_channel_id(x, recording_id) for x in chids.tolist()],
        np.asarray(chcode, dtype=np.int64).reshape(-1),
    )
    param_id = _take(params, item)
    rid = record_ids(
        c,
        TOPIC,
        {
            "provenance": PROVENANCE,
            "tail_no": tail_no,
            "sortie_id": sortie_id,
            "channel_id": channel_id,
            "param_id": param_id,
            "seq": col["seq"].astype(np.uint64),
            "msg_index": col["msg_index"].astype(np.uint64),
        },
        n,
    )
    arrays = {
        "record_id": rid,
        "dict_version": _const(fp.dict_version, n),
        "dict_hash": _const(fp.dict_hash, n),
        "param_id": param_id,
        "tail_no": _const(tail_no, n),
        "sortie_id": _const(sortie_id, n),
        "engine_serial": _take([fp.engine_serial.get(p) for p in params], item),
        "source_lru": _take([loc["source_lru"] for loc in locs], item),
        "lane": _take([loc["lane"] for loc in locs], item),
        "bus": _take([loc["bus"] for loc in locs], item),
        "rt_sa_word": _take([loc["rt_sa_word"] for loc in locs], item),
        "label_sdi": _take([loc["label_sdi"] for loc in locs], item),
        "t_sample": pa.array(t_s.astype(np.int64), pa.int64()),
        "t_bus": pa.array(t_b.astype(np.int64), pa.int64()),
        "t_record": pa.array((col["rtc"].astype(np.int64) * 100), pa.int64()),
        "t_utc": pa.array(t_u.astype(np.int64), pa.int64()),
        "t_ingest": pa.array(np.full(n, t_ingest, dtype=np.int64), pa.int64()),
        "value_eu": pa.array(v, pa.float64()),
        "raw_counts": pa.array(col["raw"].astype(np.int64), pa.int64()),
        "units": _take([fp.units[p] for p in params], item),
        "validity": _take(rows.vsyms, col["vcode"].astype(np.int64)),
        "quality_flags": pa.array(flags, pa.uint32()),
        "provenance": _const(PROVENANCE, n),
        "recording_id": _const(recording_id, n),  # contract 0.2.0 (A-W0.4-22)
        "sink": _const(sink, n),
    }
    table = pa.Table.from_arrays([arrays[fld.name] for fld in schema], schema=schema)
    c.validate(TOPIC, table)
    return table
