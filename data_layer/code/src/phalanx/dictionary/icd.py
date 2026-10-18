"""Synthetic Phalanx ICD: word sizing, deterministic bus-address allocation and the human-readable ICD stub.

**Everything here is SYNTHETIC.** The real Tejas ICD (bus allocation, RT/SA/word map, scaling, label set) is
not public (architecture §19). The conventions follow public standards and released analogues (rules R-ICD-*):

- MIL-STD-1553B: 16-bit data words, MSW first for multi-word quantities, SA 1-30, <= 32 words per message, RT
  31 = broadcast; one validity word per 16 data items at the start of each message (F/A-18C IAVAL style).
- ARINC-429: 32-bit words, label bits 1-8, SDI 9-10, data 11-29 (19-bit two's-complement BNR), SSM 30-31.
- FTI PCM: 12-bit words of one minor frame.

Allocation is a pure function of the channel set: messages are filled per (bus, RT, T/R) in rate-group order
(fastest first) and channel-ID order, so the same sources always produce the same addresses.
"""

from __future__ import annotations

import csv
import io
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "BUS_GROUP_ORDER",
    "Mil1553Item",
    "allocate_arinc429",
    "allocate_fti",
    "allocate_mil1553",
    "bnr_lsb",
    "fits_word",
    "icd_csv",
    "icd_markdown",
    "select_word",
]

#: Bus rate groups in allocation order (fastest first).
BUS_GROUP_ORDER = ("AV50", "AV25", "AV12.5", "AV6.25", "SLOW1")

WORD_CANDIDATES_1553 = ((16, "bnr"), (16, "ubnr"), (32, "bnr"))
ARINC429_BNR_BITS = 19  # data bits 11-28 + sign bit 29
FTI_WORD_BITS = 12
MESSAGE_MAX_WORDS = 32
FIRST_SYNTHETIC_LABEL = 0o100  # synthetic labels, not ARINC 429 Attachment 1 assignments


def _count_limits(encoding: str, word_bits: int) -> tuple[int, int]:
    if encoding == "bnr":
        return -(2 ** (word_bits - 1)), 2 ** (word_bits - 1) - 1
    if encoding == "ubnr":
        return 0, 2**word_bits - 1
    raise ValueError(f"not a numeric word encoding: {encoding}")


def fits_word(rmin: float, rmax: float, lsb: float, encoding: str, word_bits: int) -> bool:
    """True if [rmin, rmax] is representable with ``lsb`` in a ``word_bits`` BNR/UBNR word."""
    lo, hi = _count_limits(encoding, word_bits)
    eps = 1e-9
    return (rmin / lsb) >= lo - eps and (rmax / lsb) <= hi + eps


def bnr_lsb(rmin: float, rmax: float, word_bits: int) -> float:
    """Power-of-two LSB for an AS15532-style word covering [rmin, rmax] (rule R-LSB-BNR).

    Two's complement when rmin < 0 (counts -2**(n-1) .. 2**(n-1)-1, so the negative side holds one more count
    than the positive side), unsigned otherwise.
    """
    if rmin < 0:
        half = 2 ** (word_bits - 1)
        need = max(-rmin / half, max(rmax, 0.0) / (half - 1))
    else:
        span_counts = 2**word_bits - 1
        need = rmax / span_counts
    if need <= 0:
        raise ValueError("range must be non-degenerate")
    return 2.0 ** math.ceil(math.log2(need))


def select_word(rmin: float, rmax: float, lsb: float, *, transport: str) -> tuple[str, int]:
    """(encoding, word_bits) for a numeric quantity on ``transport`` (smallest word that fits)."""
    if transport == "arinc429":
        if fits_word(rmin, rmax, lsb, "bnr", ARINC429_BNR_BITS):
            return "bnr", ARINC429_BNR_BITS
        raise ValueError(f"range [{rmin}, {rmax}] with LSB {lsb} does not fit a 19-bit ARINC-429 BNR word")
    if transport == "fti_pcm":
        for enc in ("ubnr", "bnr") if rmin >= 0 else ("bnr",):
            if fits_word(rmin, rmax, lsb, enc, FTI_WORD_BITS):
                return enc, FTI_WORD_BITS
        raise ValueError(f"range [{rmin}, {rmax}] with LSB {lsb} does not fit a 12-bit PCM word")
    for bits, enc in WORD_CANDIDATES_1553:
        if enc == "ubnr" and rmin < 0:
            continue
        if fits_word(rmin, rmax, lsb, enc, bits):
            return enc, bits
    raise ValueError(f"range [{rmin}, {rmax}] with LSB {lsb} does not fit a 32-bit word")


@dataclass(frozen=True)
class Mil1553Item:
    """One data item to place in a 1553 message."""

    channel_id: str
    bus: str
    rt: int
    tr: str
    group: str
    words: int


def allocate_mil1553(items: Iterable[Mil1553Item]) -> dict[str, dict[str, int]]:
    """Assign SA, first word, message length and validity word/bit to every item.

    Returns ``{channel_id: {"sa", "word", "words", "message_words", "validity_word", "validity_bit"}}``.
    """
    by_terminal: dict[tuple[str, int, str], list[Mil1553Item]] = defaultdict(list)
    for it in items:
        if it.group not in BUS_GROUP_ORDER:
            raise ValueError(f"{it.channel_id}: bus group {it.group!r} is not a 1553 rate group")
        if not 1 <= it.words <= 2:
            raise ValueError(f"{it.channel_id}: {it.words} words per item is not supported")
        by_terminal[(it.bus, it.rt, it.tr)].append(it)
    out: dict[str, dict[str, int]] = {}
    for key in sorted(by_terminal):
        sa = 0
        ordered = sorted(by_terminal[key], key=lambda i: (BUS_GROUP_ORDER.index(i.group), i.channel_id))
        for group in BUS_GROUP_ORDER:
            members = [i for i in ordered if i.group == group]
            for message in _pack_messages(members):
                sa += 1
                if sa > 30:
                    raise ValueError(f"terminal {key} needs more than 30 subaddresses")
                n_valid = math.ceil(len(message) / 16)
                total = n_valid + sum(i.words for i in message)
                word = n_valid + 1
                for idx, it in enumerate(message):
                    out[it.channel_id] = {
                        "sa": sa,
                        "word": word,
                        "words": it.words,
                        "message_words": total,
                        "validity_word": 1 + idx // 16,
                        "validity_bit": 15 - idx % 16,
                    }
                    word += it.words
    return out


def _pack_messages(members: list[Mil1553Item]) -> list[list[Mil1553Item]]:
    messages: list[list[Mil1553Item]] = []
    current: list[Mil1553Item] = []
    for it in members:
        trial = [*current, it]
        if math.ceil(len(trial) / 16) + sum(i.words for i in trial) > MESSAGE_MAX_WORDS:
            messages.append(current)
            current = [it]
        else:
            current = trial
    if current:
        messages.append(current)
    return messages


def allocate_arinc429(items: Iterable[tuple[str, str, str]]) -> dict[str, dict[str, int]]:
    """Synthetic labels per link. ``items`` are (channel_id, link, group); returns {channel_id: {label,
    sdi}}."""
    by_link: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for cid, link, group in items:
        by_link[link].append((group, cid))
    out: dict[str, dict[str, int]] = {}
    for link in sorted(by_link):
        ordered = sorted(by_link[link], key=lambda g: (_group_rank(g[0]), g[1]))
        for k, (_, cid) in enumerate(ordered):
            label = FIRST_SYNTHETIC_LABEL + k
            if label > 0o377:
                raise ValueError(f"link {link} needs more than the synthetic label range")
            out[cid] = {"label": label, "sdi": 0}
    return out


def _group_rank(group: str) -> int:
    return BUS_GROUP_ORDER.index(group) if group in BUS_GROUP_ORDER else len(BUS_GROUP_ORDER)


def allocate_fti(items: Iterable[tuple[str, str]]) -> dict[str, dict[str, int]]:
    """Word slots in the synthetic FTI minor frame. ``items`` are (channel_id, stream)."""
    by_stream: dict[str, list[str]] = defaultdict(list)
    for cid, stream in items:
        by_stream[stream].append(cid)
    out: dict[str, dict[str, int]] = {}
    for stream in sorted(by_stream):
        for k, cid in enumerate(sorted(by_stream[stream]), start=1):
            out[cid] = {"word": k}
    return out


# ------------------------------------------------------------------------------------------------------------
# ICD stub generators (human-readable; labelled synthetic)
# ------------------------------------------------------------------------------------------------------------
ICD_COLUMNS = (
    "channel_id",
    "measurand_id",
    "lane",
    "transport",
    "bus_or_link",
    "rt",
    "rt_lru",
    "tr",
    "sa",
    "word",
    "words",
    "mode_code",
    "label_octal",
    "sdi",
    "encoding",
    "word_bits",
    "lsb",
    "units",
    "range_min",
    "range_max",
    "bits",
    "validity",
    "bus_group",
    "bus_rate_hz",
    "producer_group",
)

_BUS_TRANSPORTS = ("mil1553", "mil1553_status", "mil1553_modecode", "arinc429", "fti_pcm")


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v)
    return str(v)


def icd_rows(compiled: Mapping[str, Any]) -> list[dict[str, str]]:
    """One row per bus-carried channel, sorted by transport address."""
    groups = compiled["rate_groups"]
    rows = []
    for cid, ch in compiled["channels"].items():
        tr = ch["transport"]
        if tr["type"] not in _BUS_TRANSPORTS:
            continue
        enc = ch["encoding"]
        val = ch["validity"]
        validity = val["method"]
        if val["method"] == "validity_word":
            validity = f"validity_word w{val['word']} b{val['bit']}"
        elif val["method"] == "ssm":
            validity = f"ssm {val['table']}"
        bits = ";".join(f"{f['name']}@{f['lsb_bit']}+{f['width']}" for f in enc.get("fields", []))
        rng = ch["range"] or {}
        bus_group = ch["rates"]["bus"]
        rows.append(
            {
                "channel_id": cid,
                "measurand_id": ch["measurand_id"],
                "lane": ch["lane"],
                "transport": tr["type"],
                "bus_or_link": tr.get("bus") or tr.get("link") or tr.get("stream", ""),
                "rt": _fmt(tr.get("rt")),
                "rt_lru": _fmt(tr.get("rt_lru")),
                "tr": _fmt(tr.get("tr")),
                "sa": _fmt(tr.get("sa")),
                "word": _fmt(tr.get("word")),
                "words": _fmt(tr.get("words")),
                "mode_code": _fmt(tr.get("mode_code")),
                "label_octal": format(tr["label"], "03o") if "label" in tr else "",
                "sdi": _fmt(tr.get("sdi")),
                "encoding": enc["type"],
                "word_bits": _fmt(enc.get("word_bits")),
                "lsb": _fmt(ch["recorder_lsb"]),
                "units": ch["units"],
                "range_min": _fmt(rng.get("min")),
                "range_max": _fmt(rng.get("max")),
                "bits": bits,
                "validity": validity,
                "bus_group": _fmt(bus_group),
                "bus_rate_hz": _fmt(groups[bus_group].get("rate_hz")) if bus_group else "",
                "producer_group": _fmt(ch["rates"]["producer"]),
            }
        )

    def key(r: dict[str, str]) -> tuple:
        def num(s: str) -> int:
            return int(s) if s else -1

        return (
            r["transport"],
            r["bus_or_link"],
            num(r["rt"]),
            r["tr"],
            num(r["sa"]),
            num(r["word"]),
            r["label_octal"],
            r["channel_id"],
        )

    return sorted(rows, key=key)


def icd_csv(compiled: Mapping[str, Any]) -> str:
    """The synthetic ICD as CSV (first line is a SYNTHETIC banner comment)."""
    buf = io.StringIO()
    buf.write(f"# {compiled['synthetic_label']} | dict_version {compiled['dict_version']}\n")
    w = csv.DictWriter(buf, fieldnames=list(ICD_COLUMNS), lineterminator="\n")
    w.writeheader()
    for row in icd_rows(compiled):
        w.writerow(row)
    return buf.getvalue()


def icd_markdown(compiled: Mapping[str, Any]) -> str:
    """The synthetic ICD as Markdown: topology, then one table per bus/link."""
    rows = icd_rows(compiled)
    buses = compiled["buses"]
    lines = [
        f"# SYNTHETIC Phalanx ICD ({compiled['platform']}, dictionary {compiled['dict_version']})",
        "",
        f"> **{compiled['synthetic_label']}.** Generated from the M01 dictionary; do not edit by hand.",
        "",
        "## Topology",
        "",
        "| Bus / link | Type | Controller / transmitter | Terminals / receivers | Monitors |",
        "|---|---|---|---|---|",
    ]
    for name, b in sorted(buses["mil1553"].items()):
        rts = ", ".join(
            f"{lru} (RT {v['address']})" for lru, v in sorted(b["rts"].items(), key=lambda x: x[1]["address"])
        )
        lines.append(
            f"| {name} | MIL-STD-1553B | {b['bc']} | {rts or '-'} | {', '.join(b['monitors']) or '-'} |"
        )
    for name, b in sorted(buses["arinc429"].items()):
        lines.append(
            f"| {name} | ARINC-429 ({b['speed']}) | {b['transmitter']} | {', '.join(b['receivers'])} | - |"
        )
    for name, b in sorted(buses["rs422"].items()):
        lines.append(
            f"| {name} | RS-422 (not recorded) | {b['transmitter']} | {', '.join(b['receivers'])} | - |"
        )
    for name, b in sorted(buses["fti_pcm"].items()):
        lines.append(
            f"| {name} | PCM {b['word_bits']}-bit @ {b['minor_frame_hz']} Hz | {b['transmitter']} | - | - |"
        )
    by_link: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_link[f"{r['transport']} {r['bus_or_link']}"].append(r)
    for link in sorted(by_link):
        lines += ["", f"## {link}", ""]
        lines.append(
            "| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range "
            "| Validity | Group |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in by_link[link]:
            words = r["word"] + (f"+{int(r['words']) - 1}" if r["words"] not in ("", "1") else "")
            rng = f"{r['range_min']}..{r['range_max']}" if r["range_min"] or r["range_max"] else ""
            enc = f"{r['encoding']}{r['word_bits']}" + (f" [{r['bits']}]" if r["bits"] else "")
            lines.append(
                f"| {r['channel_id']} | {r['rt']} | {r['tr']} | {r['sa']} | {words or r['mode_code']} | "
                f"{r['label_octal']} | {enc} | {r['lsb']} | {r['units']} | {rng} | {r['validity']} "
                f"| {r['bus_group']} |"
            )
    return "\n".join(lines) + "\n"
