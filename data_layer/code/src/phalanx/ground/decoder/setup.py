"""What the decoder learns from the recording's setup record (TMATS, IRIG 106 Ch9), bound to the dictionary.

The ground decoder reads bus locations from the **recording's own TMATS** (B groups: RT, T/R, subaddress or
mode code, measurand word numbers; P/D groups: PCM word slots; R group: channel IDs; R-x\\EV: recording
events), not from the encoder's code. Encodings, validity layout and contract identity come from the M01
dictionary the TMATS names.

**Dictionary binding check (the BEA "wrong frame layout" failure, report §5).** The recording must have been
written against the dictionary the decoder is given: the TMATS ``G\\COM`` dictionary line must name the same
platform and version, and every recorded measurand's location and conversion must round-trip
(``phalanx.dictionary.tmats.round_trip``). A mismatch raises :class:`SetupMismatch` instead of decoding with
the wrong layout.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "BusMessageDef",
    "DecoderSetup",
    "SetupMismatch",
    "parse_tmats",
    "setup_from_tmats",
]

_LINE = re.compile(r"^([^:]+):(.*);$")


class SetupMismatch(ValueError):
    """The recording's setup record does not match the dictionary given to the decoder."""


def parse_tmats(text: str) -> dict[str, list[str]]:
    """``CODE:DATA;`` attributes -> list of values (G\\COM may repeat)."""
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        m = _LINE.match(line.strip())
        if m:
            out.setdefault(m.group(1), []).append(m.group(2))
    return out


@dataclass(frozen=True)
class BusMessageDef:
    """A recorded 1553 message type: key = (rt, transmit?, sa, word count or mode code)."""

    bus: str
    rt: int
    transmit: bool
    sa: int
    wc_or_mode: int
    mode_code: bool
    measurands: tuple[
        tuple[str, tuple[int, ...], str], ...
    ]  # (channel_id, data-word numbers 1-based, type D/S)


@dataclass(frozen=True)
class DecoderSetup:
    channels: Mapping[int, tuple[str, str]]  # Ch10 channel id -> (data link name, CDT)
    time_channel: int
    messages: Mapping[tuple[str, int, int, int, int], BusMessageDef]  # (bus, rt, T(1)/R(0), sa, wc|mode)
    labels: Mapping[tuple[str, int, int], str]  # (link, label, sdi) -> channel_id
    pcm_words: Mapping[str, tuple[tuple[int, str], ...]]  # stream -> ((word, channel_id), ...)
    pcm_frame_words: Mapping[str, int]  # stream -> data words per minor frame (excluding sync)
    events: tuple[str, ...]  # recording event ids by event number
    ch10_revision: str


def _first(a: Mapping[str, list[str]], k: str, default: str | None = None) -> str:
    v = a.get(k)
    if not v:
        if default is None:
            raise SetupMismatch(f"setup record lacks {k}")
        return default
    return v[0]


def setup_from_tmats(text: str, dictionary: Any) -> DecoderSetup:
    """Parse the recording's TMATS and check it against ``dictionary`` (see module docstring)."""
    from phalanx.dictionary.tmats import round_trip

    a = parse_tmats(text)
    want = f"dictionary {dictionary.platform} {dictionary.dict_version}"
    if want not in a.get("G\\COM", []):
        raise SetupMismatch(f"recording was not written against {want} (G\\COM = {a.get('G\\COM')})")
    flat = {k: v[0] for k, v in a.items()}
    # FTI PCM words no producer populated are not described by the recording (spare slots, W2.2)
    rt_check = round_trip(dictionary.compiled.content, flat, allow_unpopulated_pcm=True)
    if not rt_check.ok:
        detail = (
            list(rt_check.missing[:3]) + list(rt_check.extra[:3]) + list(rt_check.location_mismatches[:3])
        )
        raise SetupMismatch(f"recording layout differs from the dictionary: {detail}")
    n = int(_first(a, "R-1\\N"))
    channels: dict[int, tuple[str, str]] = {}
    time_ch = None
    for k in range(1, n + 1):
        cid = int(_first(a, f"R-1\\TK1-{k}"))
        cdt = _first(a, f"R-1\\CDT-{k}")
        channels[cid] = (_first(a, f"R-1\\DSI-{k}"), cdt)
        if cdt == "TIMEIN":
            time_ch = cid
    if time_ch is None:
        raise SetupMismatch("no time channel in the setup record")
    messages: dict[tuple[str, int, int, int, int], BusMessageDef] = {}
    labels: dict[tuple[str, int, int], str] = {}
    groups = sorted({int(m.group(1)) for k in a if (m := re.match(r"^B-(\d+)\\DLN$", k))})
    for x in groups:
        b = f"B-{x}"
        link = _first(a, f"{b}\\DLN")
        bt = _first(a, f"{b}\\BT-1")
        for msg in range(1, int(_first(a, f"{b}\\NMS\\N-1", "0")) + 1):
            if bt == "A429":
                lab = int(_first(a, f"{b}\\LBL-1-{msg}"), 2)
                sdi = int(_first(a, f"{b}\\SDI-1-{msg}"))
                labels[(link, lab, sdi)] = _first(a, f"{b}\\MN-1-{msg}-1")
                continue
            rt = int(_first(a, f"{b}\\TRA-1-{msg}"), 2)
            sa = int(_first(a, f"{b}\\STA-1-{msg}"), 2)
            trm = int(_first(a, f"{b}\\TRM-1-{msg}"))
            dwc = int(_first(a, f"{b}\\DWC-1-{msg}"), 2)
            meas = []
            for p in range(1, int(_first(a, f"{b}\\MN\\N-1-{msg}", "0")) + 1):
                cid = _first(a, f"{b}\\MN-1-{msg}-{p}")
                nloc = int(_first(a, f"{b}\\NML\\N-1-{msg}-{p}"))
                wn = tuple(int(_first(a, f"{b}\\MWN-1-{msg}-{p}-{e}")) for e in range(1, nloc + 1))
                meas.append((cid, wn, _first(a, f"{b}\\MT-1-{msg}-{p}")))
            mode = sa in (0, 31)
            key = (link, rt, trm, sa, dwc)
            messages[key] = BusMessageDef(link, rt, bool(trm), sa, dwc, mode, tuple(meas))
    pcm_words: dict[str, tuple[tuple[int, str], ...]] = {}
    pcm_n: dict[str, int] = {}
    for x in sorted({int(m.group(1)) for k in a if (m := re.match(r"^D-(\d+)\\DLN$", k))}):
        stream = _first(a, f"D-{x}\\DLN")
        items = []
        for k in range(1, int(_first(a, f"D-{x}\\MN\\N-1", "0")) + 1):
            items.append((int(_first(a, f"D-{x}\\MF-1-{k}")), _first(a, f"D-{x}\\MN-1-{k}")))
        pcm_words[stream] = tuple(sorted(items))
    for x in sorted({int(m.group(1)) for k in a if (m := re.match(r"^P-(\d+)\\DLN$", k))}):
        stream = _first(a, f"P-{x}\\DLN")
        pcm_n[stream] = int(_first(a, f"P-{x}\\MF1")) - 1  # MF1 counts the sync as one word
    events: list[str] = []
    if _first(a, "R-1\\EV\\E", "F") == "T":
        for k in range(1, int(_first(a, "R-1\\EV\\N", "0")) + 1):
            events.append(_first(a, f"R-1\\EV\\ID-{k}"))
    return DecoderSetup(
        channels, time_ch, messages, labels, pcm_words, pcm_n, tuple(events), _first(a, "G\\106", "")
    )
