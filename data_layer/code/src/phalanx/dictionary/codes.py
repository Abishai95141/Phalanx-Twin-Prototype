"""The unified synthetic BIT/fault/exceedance code table and the fault-code word layout (dictionary 0.1.2).

``code_tables.bit_codes`` is the single SSS-NNN code table of every module (AD-48 item 5; AD-19
synthetic): M14's 102 codes in M14's order (so a code's position, its index, is unchanged) plus
ENG-509/ENG-510, with groups, severities, fault lists, the CWS legend/voice mapping and monitor limit ids.
``legacy`` maps earlier module code lists onto it (M08's unmerged list reused numbers with other meanings).

``code_tables.bit_code_format.word_layout`` is the 16-bit word of a ``code_word`` channel (rule R-CODE-WORD,
from A-W1.7-6): prefix index ``k`` (position in the channel's ``prefixes``) in bits 15-10, ``NNN`` in bits
9-0; the EU value is ``k * 1000 + NNN``; 0 means no active code.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "BLOCKS",
    "MECHANISMS",
    "SEVERITIES",
    "SOURCES",
    "bit_code_errors",
    "code_from_eu",
    "code_to_eu",
    "eu_from_word",
    "word_from_eu",
]

SEVERITIES = ("ADVISORY", "CAUTION", "WARNING")
LISTS = ("PFL", "MFL")
MECHANISMS = ("PBIT", "CBIT", "MBIT", "IBIT", "EXCEEDANCE", "PILOT")
SOURCES = ("internal", "external", "cir")
#: number blocks of bit_code_format (role -> inclusive range)
BLOCKS = {
    "sensor": (1, 99),
    "actuator": (100, 199),
    "processor": (200, 299),
    "interface": (300, 399),
    "power": (400, 499),
    "function": (500, 699),
    "exceedance": (700, 899),
}
_KEYS = {"index", "desc", "sev", "list", "mech", "lru", "lane", "src", "legend", "voice", "monitor"}
_MON_KEYS = {"channel", "limit", "sense", "gate"}


def _limit_ids(ch: Mapping[str, Any]) -> set[str]:
    out: set[str] = set()
    for lim in ch.get("limits", ()):
        k = lim["kind"]
        for side in ("high", "low"):
            if side in lim:
                out |= {k, f"{k}_{side}"}
    return out


def bit_code_errors(code_tables: Mapping[str, Any], channels: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Problems with ``bit_codes`` (format, blocks, enums, legends, voice channels, monitors, legacy maps) and
    with the code-word layout of ``bit_code_format``."""
    errs: list[str] = []
    fmt = code_tables.get("bit_code_format", {})
    errs += _layout_errors(fmt.get("word_layout"))
    table = code_tables.get("bit_codes")
    if table is None:
        return errs
    pattern = re.compile(fmt.get("pattern", r"^[A-Z]{3}-[0-9]{3}$"))
    prefixes = fmt.get("prefixes", {})
    slots = int(code_tables.get("cws_legends", {}).get("slots", 0))
    groups = table.get("groups", {})
    module_limits = table.get("module_limits", {})
    indices = sorted(c.get("index", -1) for c in table["codes"].values())
    if indices != list(range(len(indices))):
        errs.append(
            "bit_codes: index values must be 0..n-1, each once (the index is the code's stable position)"
        )
    for code, c in table["codes"].items():
        w = f"bit_codes {code}"
        if not pattern.match(code):
            errs.append(f"{w}: does not match {pattern.pattern}")
            continue
        prefix, num = code.split("-")
        n = int(num)
        if prefix not in prefixes:
            errs.append(f"{w}: prefix {prefix} is not a bit_code_format prefix")
        if prefix not in groups:
            errs.append(f"{w}: no group for prefix {prefix}")
        if not 1 <= n <= 899:
            errs.append(f"{w}: number {n} outside 001-899 (900-999 reserved)")
        if set(c) - _KEYS:
            errs.append(f"{w}: unknown keys {sorted(set(c) - _KEYS)}")
        for key, allowed in (("sev", SEVERITIES), ("list", LISTS), ("mech", MECHANISMS), ("src", SOURCES)):
            if c.get(key) not in allowed:
                errs.append(f"{w}: {key} {c.get(key)!r} not in {allowed}")
        lo_x, hi_x = BLOCKS["exceedance"]
        lo_f, hi_f = BLOCKS["function"]
        if (
            c.get("mech") == "EXCEEDANCE"
            and c.get("src") == "cir"
            and not (lo_x <= n <= hi_x or lo_f <= n <= hi_f)
        ):
            errs.append(f"{w}: a limit monitor must be in block 700-899 (or a 500-699 function monitor)")
        legend = c.get("legend")
        if legend is not None:
            m = re.match(r"^CWS-L(\d{2})$", str(legend))
            if not m or not 1 <= int(m.group(1)) <= slots:
                errs.append(f"{w}: legend {legend!r} is not one of the {slots} CWS slots")
            if c.get("list") != "PFL":
                errs.append(f"{w}: only PFL codes carry a CWS legend")
        voice = c.get("voice", False)
        if voice is True or (voice and not str(voice).startswith("CWS.VOICE.")):
            errs.append(f"{w}: voice must name a CWS.VOICE.* channel or be false")
        elif voice and (voice not in channels or channels[voice].get("acq_lru") != "CWS"):
            errs.append(f"{w}: voice channel {voice} is not a CWS channel of the dictionary")
        mon = c.get("monitor")
        if c.get("src") == "cir" and not mon:
            errs.append(f"{w}: cir codes need a monitor")
        if mon:
            if set(mon) - _MON_KEYS or not {"channel", "limit", "sense"} <= set(mon):
                errs.append(f"{w}: monitor keys must be channel, limit, sense[, gate]")
            elif mon["channel"] not in channels:
                errs.append(f"{w}: monitor channel {mon['channel']} is not a dictionary channel")
            elif (
                mon["limit"] not in _limit_ids(channels[mon["channel"]]) and mon["limit"] not in module_limits
            ):
                errs.append(
                    f"{w}: limit id {mon['limit']} is neither a channel limit nor a module_limits entry"
                )
            if mon.get("sense") not in ("high", "low"):
                errs.append(f"{w}: monitor sense must be high or low")
    for name, leg in table.get("legacy", {}).items():
        targets = list(leg["codes"].values())
        for old, new in leg["codes"].items():
            if not pattern.match(old):
                errs.append(f"bit_codes legacy {name}: {old} is not an SSS-NNN code")
            if new not in table["codes"]:
                errs.append(f"bit_codes legacy {name}: {old} -> {new}, which is not in the table")
        dup = sorted({t for t in targets if targets.count(t) > 1})
        if dup:
            errs.append(
                f"bit_codes legacy {name}: several old codes map to {dup} (the map must be one-to-one)"
            )
    return errs


def _layout_errors(layout: Mapping[str, Any] | None) -> list[str]:
    if layout is None:
        return []
    errs = []
    bits = int(layout["word_bits"])
    k, nnn = layout["prefix_index"], layout["number"]
    used_k = set(range(k["lsb_bit"], k["lsb_bit"] + k["width"]))
    used_n = set(range(nnn["lsb_bit"], nnn["lsb_bit"] + nnn["width"]))
    if used_k & used_n or max(used_k | used_n) >= bits:
        errs.append("bit_code_format.word_layout: fields overlap or exceed the word")
    if 2 ** nnn["width"] <= 999:
        errs.append("bit_code_format.word_layout: the number field cannot hold 999")
    if int(layout["eu_prefix_scale"]) <= 999:
        errs.append("bit_code_format.word_layout: eu_prefix_scale must exceed 999")
    return errs


def code_to_eu(code: str, prefixes: Sequence[str], scale: int = 1000) -> int:
    """EU value ``k * scale + NNN`` of an SSS-NNN code on a channel with ``prefixes``."""
    prefix, num = code.split("-")
    return list(prefixes).index(prefix) * scale + int(num)


def code_from_eu(value: int, prefixes: Sequence[str], scale: int = 1000) -> str | None:
    """SSS-NNN code of an EU value (None for 0, no active code)."""
    v = int(value)
    if v == 0:
        return None
    k, n = divmod(v, scale)
    if not 0 <= k < len(prefixes) or not 1 <= n <= 999:
        raise ValueError(f"EU value {v} is not a code of prefixes {list(prefixes)}")
    return f"{prefixes[k]}-{n:03d}"


def word_from_eu(value: int, layout: Mapping[str, Any]) -> int:
    """16-bit code word of an EU value (``k << 10 | NNN`` for the 0.1.2 layout)."""
    k, n = divmod(int(value), int(layout["eu_prefix_scale"]))
    pk, pn = layout["prefix_index"], layout["number"]
    if not (0 <= k < 2 ** pk["width"] and 0 <= n < 2 ** pn["width"]):
        raise ValueError(f"EU value {value} does not fit the code word")
    return (k << pk["lsb_bit"]) | (n << pn["lsb_bit"])


def eu_from_word(word: int, layout: Mapping[str, Any]) -> int:
    """EU value of a 16-bit code word."""
    pk, pn = layout["prefix_index"], layout["number"]
    k = (int(word) >> pk["lsb_bit"]) & (2 ** pk["width"] - 1)
    n = (int(word) >> pn["lsb_bit"]) & (2 ** pn["width"] - 1)
    return k * int(layout["eu_prefix_scale"]) + n
