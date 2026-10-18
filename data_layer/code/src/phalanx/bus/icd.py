"""Bus model of the SYNTHETIC Phalanx ICD, built from the M01 dictionary (architecture §6 M15, AD-39).

Everything here is derived from :class:`phalanx.dictionary.Dictionary`; nothing about the bus layout is
hard-coded. The ICD is SYNTHETIC (rules R-ICD-*, `docs/assumptions.md` W0.3): it is never the real Tejas ICD.

What the dictionary gives, and how it maps to transactions on the wire:

- **MIL-STD-1553B data messages** (transport ``mil1553``): one message per ``(bus, rt, t/r, sa)``. Data words
  are numbered from 1 (dictionary and TMATS convention); the first ``ceil(items / 16)`` words are validity
  words (F/A-18C IAVAL style, rule R-ICD-WORDS). RT-to-BC messages (``T``) are "command, status, data";
  BC-to-broadcast messages (RT 31, ``R``) are "command, data" with no status word (MIL-STD-1553B §4.3.3.6).
- **RT status words** (``mil1553_status``): read by the BC with mode code 2 "transmit status word" (TMATS
  describes them that way, ``phalanx.dictionary.tmats``): "command, status".
- **BIT words** (``mil1553_modecode``, mode code 19 "transmit BIT word"): "command, status, data word".
- **ARINC-429 labels** (``arinc429``): one 32-bit word per label, transmitted by the link's transmitter.
- **FTI PCM** (``fti_pcm``): one synthetic minor frame (24-bit sync + 12-bit words) on the FTI DAS clock.

The rate group of a transaction is the dictionary ``rates.bus`` group of its items (every item of a 1553
message shares one group by construction of the allocation, ``dictionary.icd.allocate_mil1553``; this
module checks it). The transmit-buffer update rate of a message is the dictionary ``rates.producer`` group
when its items declare one (e.g. DFCC FCS40, rule R-ICD-DFCC), otherwise the RT LRU's frame rate
(``lrus.yaml`` ``frame_hz``, rule R-RATE-LRU).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from phalanx.dictionary import Dictionary

__all__ = [
    "BUS_GROUPS",
    "BusIcd",
    "CodeWordLayout",
    "Item",
    "Label429",
    "Message1553",
    "PcmFrameDef",
]

#: 1553 bus rate groups in schedule priority order (fastest first), as in the dictionary allocation.
BUS_GROUPS = ("AV50", "AV25", "AV12.5", "AV6.25", "SLOW1")
BROADCAST_RT = 31
MODE_CODE_SA = 31
MC_TRANSMIT_STATUS = 2
MC_TRANSMIT_BIT_WORD = 19
NUMERIC_ENCODINGS = ("bnr", "ubnr")
WORD_ENCODINGS = ("bnr", "ubnr", "bitfield", "enum", "code_word")
#: 24-bit minor-frame sync (FAF320), the IRIG 106 recommended pattern used by the dictionary TMATS (P group).
FTI_SYNC_WORD = 0xFAF320


@dataclass(frozen=True)
class CodeWordLayout:
    """The 16-bit word of a ``code_word`` channel (synthetic SSS-NNN codes): prefix index ``k`` and number
    ``NNN`` bit fields and the EU form ``k * scale + NNN`` (0 = no active code).

    Read from the dictionary (``code_tables.bit_code_format.word_layout``, rule R-CODE-WORD, A-W0.3-43; the
    W1.7 constant layout A-W1.7-6 moved there in dictionary 0.1.2, W2.2 migration). Never a code constant.
    """

    word_bits: int
    k_lsb: int
    k_width: int
    n_lsb: int
    n_width: int
    scale: int

    @classmethod
    def from_dictionary(cls, d: Dictionary) -> CodeWordLayout:
        lay = d.content["code_tables"]["bit_code_format"]["word_layout"]
        return cls(
            word_bits=int(lay["word_bits"]),
            k_lsb=int(lay["prefix_index"]["lsb_bit"]),
            k_width=int(lay["prefix_index"]["width"]),
            n_lsb=int(lay["number"]["lsb_bit"]),
            n_width=int(lay["number"]["width"]),
            scale=int(lay["eu_prefix_scale"]),
        )


@dataclass(frozen=True)
class Item:
    """One dictionary channel carried in a bus word (or two words, MSW first).

    ``first_word`` is the 1-based data-word index inside its message (1553) or minor frame (PCM); ``None`` for
    ARINC-429 (the whole word) and for status words.
    """

    channel_id: str
    param_id: str  # contract param_id = dictionary measurand_id
    source_lru: str  # contract source_lru = dictionary acq_lru (the clock domain that acquired it)
    lane: str | None
    encoding: str  # bnr | ubnr | bitfield | enum | code_word
    word_bits: int  # 16 or 32 (1553), 19 (ARINC-429), 12 (FTI PCM)
    words: int
    first_word: int | None
    lsb: float | None
    cal: tuple[float, float] | None  # (c0, c1): EU = c0 + c1 * counts (rule R-CAL-LINEAR)
    range_min: float | None
    range_max: float | None
    field_mask: int  # bits used by a bitfield (unused bits are transmitted as zero, MIL-STD-1553B §4.3.2)
    prefixes: tuple[str, ...]  # code_word prefixes (SSS-NNN)
    validity_word: int | None  # 1-based validity word (1553 messages)
    validity_bit: int | None
    ssm_table: str | None  # ARINC-429 SSM table name
    signal: str
    producer_group: str | None
    acq_group: str
    code_layout: CodeWordLayout | None = None  # code_word channels only (dictionary word layout)


@dataclass(frozen=True)
class Message1553:
    """One 1553 transaction type of the BC schedule."""

    msg_id: str
    bus: str
    rt: int
    tr: str  # "T" (RT transmits) or "R" (RT receives; BC-to-broadcast here)
    sa: int  # 1..30 data, 31 mode code
    kind: str  # data | broadcast | mc_status | mc_bit
    mode_code: int | None
    data_words: int  # data words on the wire (validity + item words; 1 for mode code 19; 0 for mode code 2)
    group: str
    rt_lru: str  # the LRU behind the RT address (OAC for broadcasts: the BC transmits)
    update_hz: float  # transmit-buffer update rate (producer group or RT LRU frame)
    items: tuple[Item, ...]

    @property
    def has_status(self) -> bool:
        return self.kind != "broadcast"

    @property
    def command_word(self) -> int:
        """MIL-STD-1553B command word: RT(5) | T/R(1) | SA(5) | word count / mode code(5)."""
        wc = self.mode_code if self.mode_code is not None else self.data_words % 32
        return (self.rt << 11) | ((1 if self.tr == "T" else 0) << 10) | (self.sa << 5) | wc

    @property
    def wire_words(self) -> int:
        """Words on the bus: command + status (if any) + data."""
        return 1 + (1 if self.has_status else 0) + self.data_words

    @property
    def n_validity_words(self) -> int:
        return math.ceil(len(self.items) / 16) if self.kind in ("data", "broadcast") else 0


@dataclass(frozen=True)
class Label429:
    """One ARINC-429 label on a link."""

    link: str
    label: int
    sdi: int
    group: str
    transmitter: str
    high_speed: bool
    item: Item


@dataclass(frozen=True)
class PcmFrameDef:
    """The synthetic FTI PCM minor frame (rule R-ICD-FTI-PCM)."""

    stream: str
    transmitter: str
    word_bits: int
    minor_frame_hz: float
    sync_bits: int
    items: tuple[Item, ...]  # sorted by word position (1-based)

    @property
    def n_words(self) -> int:
        return max((it.first_word or 0) for it in self.items) if self.items else 0

    @property
    def frame_bits(self) -> int:
        return self.sync_bits + self.word_bits * self.n_words


def _cal(ch: Mapping[str, Any]) -> tuple[float, float] | None:
    cal = ch.get("calibration")
    if not cal:
        return None
    co = list(cal["coefficients"])
    if len(co) != 2:
        raise ValueError(f"{ch['channel_id']}: only linear counts->EU calibrations are supported, got {co}")
    return float(co[0]), float(co[1])


def _item(
    ch: Mapping[str, Any], *, first_word: int | None, words: int, code_layout: CodeWordLayout | None = None
) -> Item:
    enc = ch["encoding"]
    if enc["type"] == "code_word" and code_layout is None:
        raise ValueError(f"{ch['channel_id']}: a code_word item needs the dictionary code-word layout")
    rng = ch.get("range") or {}
    fields = enc.get("fields") or ()
    mask = 0
    for f in fields:
        mask |= ((1 << int(f["width"])) - 1) << int(f["lsb_bit"])
    val = ch["validity"]
    lsb = ch.get("recorder_lsb")
    return Item(
        channel_id=ch["channel_id"],
        param_id=ch["measurand_id"],
        source_lru=ch["acq_lru"],
        lane=ch["lane"] or None,
        encoding=enc["type"],
        word_bits=int(enc.get("word_bits") or 16),
        words=int(words),
        first_word=first_word,
        lsb=None if lsb is None else float(lsb),
        cal=_cal(ch),
        range_min=None if rng.get("min") is None else float(rng["min"]),
        range_max=None if rng.get("max") is None else float(rng["max"]),
        field_mask=mask,
        prefixes=tuple(enc.get("prefixes") or ()),
        validity_word=val.get("word") if val["method"] == "validity_word" else None,
        validity_bit=val.get("bit") if val["method"] == "validity_word" else None,
        ssm_table=val.get("table") if val["method"] == "ssm" else None,
        signal=ch.get("signal") or "computed",
        producer_group=ch["rates"].get("producer"),
        acq_group=ch["rates"]["acquisition"],
        code_layout=code_layout if enc["type"] == "code_word" else None,
    )


class BusIcd:
    """All bus transactions of one dictionary, in deterministic order.

    Build with :meth:`from_dictionary`. ``messages`` are sorted by (bus, group priority, rt, t/r, sa, kind);
    ``labels`` by (link, label, sdi); ``pcm`` holds the FTI frame (or None).
    """

    def __init__(
        self,
        dictionary: Dictionary,
        messages: tuple[Message1553, ...],
        labels: tuple[Label429, ...],
        pcm: PcmFrameDef | None,
        buses: Mapping[str, Mapping[str, Any]],
    ):
        self.dictionary = dictionary
        self.messages = messages
        self.labels = labels
        self.pcm = pcm
        self.buses = buses

    # ---- construction --------------------------------------------------------------------------------------
    @classmethod
    def from_dictionary(cls, d: Dictionary) -> BusIcd:
        content = d.content
        lrus = content["lrus"]
        groups = content["rate_groups"]
        buses = content["buses"]

        def group_hz(g: str | None) -> float | None:
            return None if g is None else groups[g].get("rate_hz")

        cw = CodeWordLayout.from_dictionary(d)

        data: dict[tuple[str, int, str, int], list[Mapping[str, Any]]] = defaultdict(list)
        status: dict[tuple[str, int], Mapping[str, Any]] = {}
        bitw: dict[tuple[str, int], Mapping[str, Any]] = {}
        labels: list[Label429] = []
        pcm_items: dict[str, list[Item]] = defaultdict(list)
        for ch in d.channels():
            t = ch["transport"]
            if t["type"] == "mil1553":
                data[(t["bus"], t["rt"], t["tr"], t["sa"])].append(ch)
            elif t["type"] == "mil1553_status":
                status[(t["bus"], t["rt"])] = ch
            elif t["type"] == "mil1553_modecode":
                if t["mode_code"] != MC_TRANSMIT_BIT_WORD:
                    raise ValueError(f"{ch['channel_id']}: unsupported mode code {t['mode_code']}")
                bitw[(t["bus"], t["rt"])] = ch
            elif t["type"] == "arinc429":
                link = buses["arinc429"][t["link"]]
                if not link.get("recorded"):
                    continue
                labels.append(
                    Label429(
                        link=t["link"],
                        label=int(t["label"]),
                        sdi=int(t["sdi"]),
                        group=ch["rates"]["bus"],
                        transmitter=link["transmitter"],
                        high_speed=link["speed"] == "high",
                        item=_item(ch, first_word=None, words=1, code_layout=cw),
                    )
                )
            elif t["type"] == "fti_pcm":
                pcm_items[t["stream"]].append(_item(ch, first_word=int(t["word"]), words=1, code_layout=cw))

        messages: list[Message1553] = []
        for (bus, rt, tr, sa), chans in data.items():
            chans = sorted(chans, key=lambda c: c["transport"]["word"])
            grp = {c["rates"]["bus"] for c in chans}
            if len(grp) != 1:
                raise ValueError(f"{bus} RT{rt} {tr} SA{sa}: items in several bus groups {sorted(grp)}")
            group = grp.pop()
            mw = {c["transport"]["message_words"] for c in chans}
            if len(mw) != 1:
                raise ValueError(f"{bus} RT{rt} SA{sa}: inconsistent message_words {mw}")
            rt_lru = chans[0]["transport"]["rt_lru"]
            prods = {c["rates"].get("producer") for c in chans} - {None}
            if len(prods) > 1:
                raise ValueError(f"{bus} RT{rt} SA{sa}: several producer groups {sorted(prods)}")
            update = group_hz(prods.pop()) if prods else lrus[rt_lru].get("frame_hz")
            if update is None:
                raise ValueError(f"{bus} RT{rt} SA{sa}: no update rate for {rt_lru}")
            items = tuple(
                _item(
                    c,
                    first_word=int(c["transport"]["word"]),
                    words=int(c["transport"]["words"]),
                    code_layout=cw,
                )
                for c in chans
            )
            kind = "broadcast" if (rt == BROADCAST_RT and tr == "R") else "data"
            if kind == "data" and tr != "T":
                raise ValueError(f"{bus} RT{rt} SA{sa}: only RT-to-BC and broadcast messages are modelled")
            messages.append(
                Message1553(
                    msg_id=f"{bus}/RT{rt:02d}/{tr}/SA{sa:02d}",
                    bus=bus,
                    rt=rt,
                    tr=tr,
                    sa=sa,
                    kind=kind,
                    mode_code=None,
                    data_words=int(mw.pop()),
                    group=group,
                    rt_lru=rt_lru if kind == "data" else buses["mil1553"][bus]["bc"],
                    update_hz=float(update),
                    items=items,
                )
            )
        for (bus, rt), ch in status.items():
            lru = ch["transport"]["rt_lru"]
            messages.append(
                Message1553(
                    msg_id=f"{bus}/RT{rt:02d}/T/MC{MC_TRANSMIT_STATUS:02d}",
                    bus=bus,
                    rt=rt,
                    tr="T",
                    sa=MODE_CODE_SA,
                    kind="mc_status",
                    mode_code=MC_TRANSMIT_STATUS,
                    data_words=0,
                    group=ch["rates"]["bus"],
                    rt_lru=lru,
                    update_hz=float(lrus[lru]["frame_hz"]),
                    items=(_item(ch, first_word=None, words=1, code_layout=cw),),
                )
            )
        for (bus, rt), ch in bitw.items():
            lru = ch["transport"]["rt_lru"]
            messages.append(
                Message1553(
                    msg_id=f"{bus}/RT{rt:02d}/T/MC{MC_TRANSMIT_BIT_WORD:02d}",
                    bus=bus,
                    rt=rt,
                    tr="T",
                    sa=MODE_CODE_SA,
                    kind="mc_bit",
                    mode_code=MC_TRANSMIT_BIT_WORD,
                    data_words=1,
                    group=ch["rates"]["bus"],
                    rt_lru=lru,
                    update_hz=float(lrus[lru]["frame_hz"]),
                    items=(_item(ch, first_word=1, words=1, code_layout=cw),),
                )
            )
        kind_rank = {"data": 0, "broadcast": 1, "mc_status": 2, "mc_bit": 3}
        messages.sort(key=lambda m: (m.bus, BUS_GROUPS.index(m.group), m.rt, m.tr, m.sa, kind_rank[m.kind]))
        labels.sort(key=lambda lb: (lb.link, lb.label, lb.sdi))
        pcm = None
        recorded_pcm = sorted(k for k, v in buses["fti_pcm"].items() if v.get("recorded"))
        if len(recorded_pcm) > 1:
            raise ValueError(f"only one FTI PCM stream is supported, dictionary has {recorded_pcm}")
        for stream in recorded_pcm:
            b = buses["fti_pcm"][stream]
            items = tuple(sorted(pcm_items.get(stream, []), key=lambda it: it.first_word or 0))
            pcm = PcmFrameDef(
                stream=stream,
                transmitter=b["transmitter"],
                word_bits=int(b["word_bits"]),
                minor_frame_hz=float(b["minor_frame_hz"]),
                sync_bits=24,
                items=items,
            )
        return cls(d, tuple(messages), tuple(labels), pcm, buses)

    # ---- lookups -------------------------------------------------------------------------------------------
    @cached_property
    def bus_names(self) -> tuple[str, ...]:
        """Recorded 1553 buses (sorted), including buses without traffic."""
        return tuple(sorted(self.buses["mil1553"]))

    @cached_property
    def link_names(self) -> tuple[str, ...]:
        return tuple(sorted(k for k, v in self.buses["arinc429"].items() if v.get("recorded")))

    def messages_on(self, bus: str) -> tuple[Message1553, ...]:
        return tuple(m for m in self.messages if m.bus == bus)

    def labels_on(self, link: str) -> tuple[Label429, ...]:
        return tuple(lb for lb in self.labels if lb.link == link)

    def bus_controller(self, bus: str) -> str:
        return self.buses["mil1553"][bus]["bc"]

    def rt_address(self, bus: str, lru: str) -> int | None:
        rts = self.buses["mil1553"][bus]["rts"]
        return None if lru not in rts else int(rts[lru]["address"])

    @cached_property
    def items(self) -> tuple[Item, ...]:
        """Every bus-carried item, in transaction order."""
        out: list[Item] = []
        for m in self.messages:
            out.extend(m.items)
        out.extend(lb.item for lb in self.labels)
        if self.pcm is not None:
            out.extend(self.pcm.items)
        return tuple(out)

    def item(self, channel_id: str) -> Item:
        for it in self.items:
            if it.channel_id == channel_id:
                return it
        raise KeyError(f"{channel_id} is not carried on a recorded bus")
