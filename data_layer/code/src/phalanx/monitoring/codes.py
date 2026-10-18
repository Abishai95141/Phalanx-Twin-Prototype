"""M14 code table: the M01 dictionary's single SYNTHETIC BIT code table joined with M14's behaviour rows
(``configs/tejas/params/M14/codes.yaml``; dictionary 0.1.2, W2.1c).

Identity and meaning of every code - its index, description, severity, fault list, mechanism, source
LRU, lane, source (internal / external / cir), CWS legend and voice channel, limit-monitor channel / limit /
sense / gate and event group - come from the dictionary (``Dictionary.bit_codes()`` / ``bit_code(c)``; table
``bit_codes``, format ``bit_code_format``, both validated by M01). M14's behaviour rows add what only the
monitor knows: LRU technology (CND/NFF propensity), whether the code reaches the cockpit, isolation suspects,
the threshold regime of an internal test, sympathetic codes and the persistence / clear times of a limit
monitor. Every dictionary code needs exactly one behaviour row and every row must be a dictionary code.

Exceedance monitors resolve their limit either from the dictionary channel limits (``steady_max``,
``warning_low``, ``normal_band_low``, ``operational_envelope_high`` / ``_low``) or from an M14 parameter
(SI), converted to the channel's engineering unit with ``Dictionary.si_to_eu`` because the CIR carries EU
values (AD-38).

FADEC-reported codes (``fadec.fault`` / ``fadec.caution``) are dictionary codes; ``CodeTable.legacy`` carries
the dictionary's legacy maps (``legacy["M08"]``: M08's W1 code list -> dictionary code) for a producer that is
not yet re-keyed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from phalanx.core.module import ParamSet
from phalanx.dictionary.yamlio import load_yaml

__all__ = ["MECHANISMS", "Code", "CodeTable", "Monitor", "load_code_table"]

MECHANISMS = ("PBIT", "CBIT", "MBIT", "IBIT", "EXCEEDANCE", "PILOT")
_REPO = Path(__file__).resolve().parents[3]
CODES_PATH = _REPO / "configs" / "tejas" / "params" / "M14" / "codes.yaml"
FORMAT = "phalanx.m14_codes/2"
#: M14 behaviour keys of a code row (identity is the dictionary's)
BEHAVIOUR_KEYS = frozenset({"tech", "displayed", "suspects", "regime", "sympathetic", "monitor"})


class CodeTableError(ValueError):
    pass


@dataclass(frozen=True)
class Monitor:
    """Limit monitor on a recorded channel (engineering units)."""

    channel: str
    limit_name: str
    limit_eu: float
    sense: float  # +1 high limit, -1 low limit
    persist_s: float
    clear_s: float
    gate: str  # "", "engine_running", "airborne"
    units: str

    @property
    def limit_id(self) -> str:
        return f"{self.channel}:{self.limit_name}"


@dataclass(frozen=True)
class Code:
    code: str
    index: int
    group: str
    desc: str
    severity: str
    fault_list: str
    mechanism: str
    lru: str
    lane: str | None
    src: str
    tech: str
    legend: str | None
    voice: bool
    displayed: bool
    suspects: tuple[tuple[str, float], ...]
    regime: str
    sympathetic: tuple[tuple[str, float, float, float], ...]
    cnd: float
    monitor: Monitor | None
    voice_channel: str | None = None  # the CWS.VOICE.* channel a voice warning drives (``voice:``)


@dataclass(frozen=True)
class CodeTable:
    codes: tuple[Code, ...]
    groups: Mapping[str, str]
    #: the dictionary's legacy code maps {producer list: {legacy code: dictionary code}} (``"M08"``: the W1
    #: FADEC list), for a producer that does not emit dictionary codes yet
    legacy: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    @property
    def by_code(self) -> dict[str, Code]:
        return {c.code: c for c in self.codes}

    def index(self, code: str) -> int:
        for c in self.codes:
            if c.code == code:
                return c.index
        raise KeyError(f"unknown code {code!r}")


def _limit_eu(dictionary, channel: str, name: str, params: ParamSet) -> float:
    ch = dictionary.channel(channel)
    if name in params:
        return float(dictionary.si_to_eu(channel, float(params.value(name))))
    for lim in ch["limits"]:
        kind = lim["kind"]
        if name == kind and "high" in lim:
            return float(lim["high"])
        if name == kind and "low" in lim:
            return float(lim["low"])
        if name == f"{kind}_high" and "high" in lim:
            return float(lim["high"])
        if name == f"{kind}_low" and "low" in lim:
            return float(lim["low"])
    raise CodeTableError(f"{channel}: limit {name!r} is neither a dictionary limit nor an M14 parameter")


def load_code_table(dictionary, params: ParamSet, path: str | None = None) -> CodeTable:
    """The code table: the dictionary's ``bit_codes`` (identity) joined with M14's behaviour rows, monitor
    limits resolved with ``params``."""
    return _load(dictionary.dict_hash, str(path or CODES_PATH), dictionary, params)


_CACHE: dict[tuple[str, str, str], CodeTable] = {}


def _monitor(code: str, idn: Mapping, b: Mapping, dictionary, params: ParamSet) -> Monitor | None:
    md, bm = idn.get("monitor"), b.get("monitor")
    if idn["src"] != "cir":
        if bm:
            raise CodeTableError(f"{code}: monitor timing on a code that is not a cir limit monitor")
        return None
    if not md or not bm or {"persist_s", "clear_s"} - set(bm) or set(bm) - {"persist_s", "clear_s"}:
        raise CodeTableError(
            f"{code}: a cir code needs the dictionary monitor and exactly persist_s / clear_s here"
        )
    ch = md["channel"]
    try:
        units = str(dictionary.channel(ch)["units"])
    except KeyError as x:
        raise CodeTableError(f"{code}: monitor channel {ch!r} not in the dictionary") from x
    lim = _limit_eu(dictionary, ch, md["limit"], params)
    if not math.isfinite(lim):
        raise CodeTableError(f"{code}: non-finite limit")
    persist, clear = float(bm["persist_s"]), float(bm["clear_s"])
    if not (persist >= 0.0 and clear >= 0.0):
        raise CodeTableError(f"{code}: persistence and clear times must be >= 0")
    sense = 1.0 if md["sense"] == "high" else -1.0
    return Monitor(ch, md["limit"], lim, sense, persist, clear, str(md.get("gate", "")), units)


def _load(dict_hash: str, path: str, dictionary, params: ParamSet) -> CodeTable:
    key = (dict_hash, path, params.hash)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    doc = load_yaml(Path(path))
    if doc.get("format") != FORMAT:
        raise CodeTableError(
            f"codes.yaml: format must be {FORMAT} (behaviour rows over the dictionary bit_codes)"
        )
    table = dictionary.code_table("bit_codes")
    groups = dict(table["groups"])
    cnd_by_tech = dict(doc["cnd_by_tech"])
    rows = dict(doc["codes"])
    order = dictionary.bit_codes()
    missing = [c for c in order if c not in rows]
    unknown = sorted(set(rows) - set(order))
    if missing or unknown:
        raise CodeTableError(
            f"one behaviour row per dictionary bit_code: missing {missing}, unknown {unknown}"
        )
    codes: list[Code] = []
    for code in order:
        idn = dictionary.bit_code(code)
        b = dict(rows[code] or {})
        extra = set(b) - BEHAVIOUR_KEYS
        if extra:
            raise CodeTableError(
                f"{code}: {sorted(extra)} are not behaviour keys (identity is the dictionary's)"
            )
        tech = b.get("tech")
        if tech not in cnd_by_tech:
            raise CodeTableError(f"{code}: unknown technology {tech!r}")
        suspects = tuple((str(s[0]), float(s[1])) for s in b.get("suspects", []))
        if any(not 0.0 <= conf <= 1.0 for _, conf in suspects):
            raise CodeTableError(f"{code}: isolation confidence outside [0, 1]")
        regime = str(b.get("regime", "bit"))
        if regime not in ("bit", "ehm"):
            raise CodeTableError(f"{code}: regime must be bit or ehm")
        voice = idn.get("voice") or None
        codes.append(
            Code(
                code,
                int(idn["index"]),
                groups[code.split("-")[0]],
                str(idn["desc"]),
                str(idn["sev"]),
                str(idn["list"]),
                str(idn["mech"]),
                str(idn["lru"]),
                idn.get("lane") or None,
                str(idn["src"]),
                str(tech),
                idn.get("legend") or None,
                bool(voice),
                bool(b.get("displayed", True)),
                suspects,
                regime,
                tuple((str(s[0]), float(s[1]), float(s[2]), float(s[3])) for s in b.get("sympathetic", [])),
                float(cnd_by_tech[tech]),
                _monitor(code, idn, b, dictionary, params),
                str(voice) if voice else None,
            )
        )
    if [c.index for c in codes] != list(range(len(codes))):
        raise CodeTableError("dictionary bit_codes indices are not 0..n-1 in index order")
    names = {c.code for c in codes}
    for c in codes:
        for s in c.sympathetic:
            if s[0] not in names:
                raise CodeTableError(f"{c.code}: sympathetic code {s[0]} unknown")
    voiced = [c for c in codes if c.voice]
    if len(voiced) != 4 or len({c.voice_channel for c in voiced}) != 4:
        raise CodeTableError(f"the CWS has 4 voice warnings on 4 channels, the table declares {len(voiced)}")
    legacy = {k: dict(v["codes"]) for k, v in dict(table.get("legacy") or {}).items()}
    out = CodeTable(tuple(codes), groups, legacy)
    _CACHE[key] = out
    return out
