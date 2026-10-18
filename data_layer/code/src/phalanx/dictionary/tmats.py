"""TMATS (IRIG 106 Chapter 9) stub generated from the dictionary, and its pyChapter10 round trip (brief W0.3
A5).

The stub describes the SYNTHETIC Phalanx recorder setup: one storage data source (R-1) with a time channel,
the recorded MIL-STD-1553 buses, the ARINC-429 links and the FTI PCM stream; B groups give every 1553/429
message and measurand location; P/D groups give the FTI PCM frame; one C group per recorded measurand gives
units, binary format, range (MOT1/MOT2), limits (MOT3-6), sample rate and the linear counts-to-EU polynomial.

Attribute names and value codes follow RCC 106-07 Chapter 9 (Tables 9-3, 9-5, 9-6, 9-7, 9-10; local copy
``research_sources/data_pathway/ch9_trmc_113019518.txt``): TRA/STA/DWC/LBL/BID are binary strings, bit masks
are binary strings with the left-most bit first transmitted, ``FW`` = full word. The C group's CRT date format
is MM-DD-YYYY-HH-MI-SS. Conformance against an independent Ch10 parser and the public sample files is M16's
acceptance (W1.7); this module guarantees that pyChapter10 parses the setup record and that the channel list
round-trips.

Parser used: ``chapter10.computer.ComputerF1`` (pyChapter10's TMATS setup-record packet), whose
``__getitem__`` returns the ``CODE:DATA;`` attributes that start with a given prefix.
"""

from __future__ import annotations

import io
import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "TMATS_CSDW_VERSION",
    "RoundTrip",
    "generate_tmats",
    "parse_tmats_bytes",
    "recorded_channel_ids",
    "recording_attributes",
    "round_trip",
    "tmats_packet_bytes",
]

#: pyChapter10 CSDW version code for IRIG 106-07 (7 = 2007)
TMATS_CSDW_VERSION = 7
IRIG106_REVISION = "07"
FTI_SYNC_PATTERN = "111110101111001100100000"  # FAF320, IRIG 106 recommended 24-bit pattern
_RECORDED = ("mil1553", "mil1553_status", "mil1553_modecode", "arinc429", "fti_pcm")

#: pint unit -> short TMATS engineering-unit label (C-d\MN3, 16 characters max)
EU_LABELS = {
    "deg": "deg",
    "deg/s": "deg/s",
    "percent": "%",
    "degC": "degC",
    "degF": "degF",
    "psi": "psi",
    "mbar": "mbar",
    "bar": "bar",
    "kPa": "kPa",
    "lb/hr": "lb/h",
    "in/s": "in/s",
    "ft": "ft",
    "knot": "kt",
    "ft/min": "ft/min",
    "pound_force/foot**2": "psf",
    "ft/s": "ft/s",
    "standard_gravity": "g",
    "rpm": "rpm",
    "kg": "kg",
    "V": "V",
    "A": "A",
    "Hz": "Hz",
    "A*hour": "Ah",
    "count": "count",
    "hour": "h",
    "L": "L",
    "mm": "mm",
    "lbf": "lbf",
    "microstrain": "ustrain",
    "ppm": "ppm",
    "MJ": "MJ",
    "s": "s",
    "dimensionless": "none",
}


def _clean(text: Any, limit: int | None = None) -> str:
    """TMATS-safe ASCII value: no ';' (terminator), no line breaks, optional length limit."""
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[\r\n]+", " ", s).replace(";", ",").strip()
    return s[:limit] if limit else s


def _bin(value: int, width: int) -> str:
    return format(value, f"0{width}b")


def _mask(word_bits: int, fields: list[Mapping[str, int]] | None) -> str:
    """Binary bit mask, left-most bit = MSB = first bit transmitted; 'FW' for a full word."""
    if not fields:
        return "FW"
    used = set()
    for f in fields:
        used |= set(range(f["lsb_bit"], f["lsb_bit"] + f["width"]))
    return "".join("1" if (word_bits - 1 - i) in used else "0" for i in range(word_bits))


def _date(release_date: str) -> tuple[str, str]:
    y, m, d = release_date.split("-")
    return f"{m}-{d}-{y}", f"{m}-{d}-{y}-00-00-00"


def recorded_channel_ids(compiled: Mapping[str, Any]) -> list[str]:
    """Channels that the Ch10 recording carries (and the TMATS stub must describe)."""
    return sorted(cid for cid, ch in compiled["channels"].items() if ch["transport"]["type"] in _RECORDED)


def _event_text(text: Any, limit: int) -> str:
    """Event id/description as the recorder writes them (no ';' / line breaks, ':' -> '-', ASCII, cut)."""
    s = re.sub(r"[\r\n;]+", " ", str(text)).replace(":", "-").strip()
    return s.encode("ascii", "ignore").decode("ascii")[:limit]


def recording_attributes(
    compiled: Mapping[str, Any], extra_events: Sequence[Mapping[str, str]] = ()
) -> tuple[list[str], list[str]]:
    """(R-1\\EV lines, R-1\\IDX lines) of the dictionary's recorder setup (``buses.recorder``, rule
    R-REC-SETUP).

    Events: the dictionary's recorder events, then ``extra_events`` ({id, description, type}) in order; event
    number n = position + 1. Index: time-based, ``interval_s`` per entry (TMATS ITV in microseconds).
    """
    rec = compiled["buses"]["recorder"]
    events = [*rec["events"], *extra_events]
    ids = [e["id"] for e in events]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate recording event ids")
    if len(events) > 4096:
        raise ValueError("Ch10 supports at most 4,096 recording event types")
    ic = "T" if rec.get("event_initial_capture", False) else "F"
    ev = ["R-1\\EV\\E:T;", f"R-1\\EV\\N:{len(events)};"]
    for n, e in enumerate(events, start=1):
        ev += [
            f"R-1\\EV\\ID-{n}:{_event_text(e['id'], 32)};",
            f"R-1\\EV\\D-{n}:{_event_text(e['description'], 256)};",
            f"R-1\\EV\\T-{n}:{e['type']};",
            f"R-1\\EV\\P-{n}:{int(rec.get('event_priority', 1))};",
            f"R-1\\EV\\IC-{n}:{ic};",
            f"R-1\\EV\\LC-{n}:{int(rec.get('event_limit_count', 65_535))};",
        ]
    idx = [
        "R-1\\IDX\\E:T;",
        "R-1\\IDX\\IT:T;",
        f"R-1\\IDX\\ITV:{int(rec['index']['interval_s']) * 1_000_000};",
    ]
    return ev, idx


def generate_tmats(
    compiled: Mapping[str, Any],
    *,
    recording: bool = False,
    extra_events: Sequence[Mapping[str, str]] = (),
    pcm_unpopulated: Collection[str] = (),
) -> str:
    """TMATS text (``CODE:DATA;`` lines, CRLF-free) for the synthetic recorder setup.

    ``pcm_unpopulated``: FTI PCM channels that no producer populates in this recording (W2.2): their frame
    words stay in the PCM frame (spare slots; the frame format is fixed) but have no measurement definition
    (D group) or data conversion (C group), so a ground decoder emits no records for them.

    ``recording=True`` emits the recorder setup of the dictionary (``R-1\\EV`` events and the ``R-1\\IDX``
    time index, rule R-REC-SETUP; plus ``extra_events``) in place of ``R-1\\EV\\E:F`` / ``R-1\\IDX\\E:F``. The
    published TMATS uses it; the default stays ``False`` until M16 stops overlaying these lines itself (W2.1).
    """
    if extra_events and not recording:
        raise ValueError("extra_events need recording=True")
    unpopulated = frozenset(pcm_unpopulated)
    bad = sorted(
        c
        for c in unpopulated
        if compiled["channels"].get(c, {}).get("transport", {}).get("type") != "fti_pcm"
    )
    if bad:
        raise ValueError(f"pcm_unpopulated names channels that are not FTI PCM words: {bad[:5]}")
    ch_all = compiled["channels"]
    groups = compiled["rate_groups"]
    buses = compiled["buses"]
    od, crt = _date(compiled["release_date"])
    out: list[str] = []

    def a(code: str, value: Any) -> None:
        out.append(f"{code}:{_clean(value)};")

    # ---- G group -------------------------------------------------------------------------------------------
    a("G\\PN", f"PHALANX-{compiled['platform'].upper()}-SYNTHETIC")
    a("G\\TA", "PHALANX VIRTUAL FLEET")
    a("G\\106", IRIG106_REVISION)
    a("G\\OD", od)
    a("G\\DSI\\N", 1)
    a("G\\DSI-1", buses.get("recorder", {}).get("id", "PHALANX-REC"))
    a("G\\DST-1", "STO")
    a("G\\SC", "U")
    a("G\\COM", compiled["synthetic_label"])
    a("G\\COM", f"dictionary {compiled['platform']} {compiled['dict_version']}")

    # ---- recorder channels (R group) -----------------------------------------------------------------------
    rec_1553 = sorted(buses["mil1553"])
    rec_429 = sorted(k for k, v in buses["arinc429"].items() if v.get("recorded"))
    rec_pcm = sorted(k for k, v in buses["fti_pcm"].items() if v.get("recorded"))
    r_channels = [("TIME", "TIMEIN")]
    r_channels += [(b, "1553IN") for b in rec_1553]
    r_channels += [(b, "429IN") for b in rec_429]
    r_channels += [(b, "PCMIN") for b in rec_pcm]
    a("R-1\\ID", buses.get("recorder", {}).get("id", "PHALANX-REC"))
    a("R-1\\N", len(r_channels))
    if recording:
        ev_lines, idx_lines = recording_attributes(compiled, extra_events)
        out.extend(ev_lines)
        out.extend(idx_lines)
    else:
        a("R-1\\EV\\E", "F")
        a("R-1\\IDX\\E", "F")
    for n, (link, cdt) in enumerate(r_channels, start=1):
        a(f"R-1\\DSI-{n}", link)
        a(f"R-1\\TK1-{n}", n)
        a(f"R-1\\CHE-{n}", "T")
        a(f"R-1\\CDT-{n}", cdt)
        if cdt == "TIMEIN":
            a(f"R-1\\TTF-{n}", 1)
            a(f"R-1\\TFMT-{n}", "B")
            a(f"R-1\\TSRC-{n}", "E")
            continue
        a(f"R-1\\CDLN-{n}", link)
        if cdt == "1553IN":
            a(f"R-1\\BTF-{n}", 1)
        elif cdt == "429IN":
            a(f"R-1\\ABTF-{n}", 0)
            a(f"R-1\\NAS\\N-{n}", 1)
            a(f"R-1\\ASN-{n}-1", 1)
            a(f"R-1\\ANM-{n}-1", link)
        elif cdt == "PCMIN":
            a(f"R-1\\PDTF-{n}", 1)

    # ---- B groups: 1553 buses ------------------------------------------------------------------------------
    by_bus: dict[str, dict[tuple, list[tuple[str, Mapping[str, Any]]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for cid, ch in sorted(ch_all.items()):
        t = ch["transport"]
        if t["type"] == "mil1553":
            by_bus[t["bus"]][(t["rt"], t["tr"], t["sa"], "data")].append((cid, ch))
        elif t["type"] == "mil1553_status":
            by_bus[t["bus"]][(t["rt"], "T", 31, "mc2")].append((cid, ch))
        elif t["type"] == "mil1553_modecode":
            by_bus[t["bus"]][(t["rt"], "T", 31, f"mc{t['mode_code']}")].append((cid, ch))
    x = 0
    for bus in rec_1553:
        x += 1
        b = f"B-{x}"
        a(f"{b}\\DLN", bus)
        a(f"{b}\\NBS\\N", 1)
        a(f"{b}\\BID-1", _bin(x, 8))
        a(f"{b}\\BNA-1", bus)
        a(f"{b}\\BT-1", "1553")
        msgs = sorted(by_bus.get(bus, {}).items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3]))
        a(f"{b}\\NMS\\N-1", len(msgs))
        for n, ((rt, tr, sa, kind), items) in enumerate(msgs, start=1):
            ch0 = items[0][1]
            t0 = ch0["transport"]
            rt_lru = t0["rt_lru"]
            a(f"{b}\\MID-1-{n}", n)
            if kind == "data":
                a(f"{b}\\MNA-1-{n}", f"{rt_lru}-SA{sa}-{tr}")
                a(f"{b}\\TRN-1-{n}", rt_lru if rt != 31 else "BROADCAST")
                a(f"{b}\\TRA-1-{n}", _bin(rt, 5))
                a(f"{b}\\STA-1-{n}", _bin(sa, 5))
                a(f"{b}\\TRM-1-{n}", 1 if tr == "T" else 0)
                a(f"{b}\\DWC-1-{n}", _bin(t0["message_words"] % 32, 5))
            else:
                mode_code = int(kind[2:])
                a(f"{b}\\MNA-1-{n}", f"{rt_lru}-MODECODE{mode_code}")
                a(f"{b}\\TRN-1-{n}", rt_lru)
                a(f"{b}\\TRA-1-{n}", _bin(rt, 5))
                a(f"{b}\\STA-1-{n}", _bin(31, 5))
                a(f"{b}\\TRM-1-{n}", 1)
                a(f"{b}\\DWC-1-{n}", _bin(mode_code, 5))
                a(f"{b}\\MCD-1-{n}", "TRANSMIT STATUS WORD" if mode_code == 2 else "TRANSMIT BIT WORD")
            a(f"{b}\\MN\\N-1-{n}", len(items))
            for p, (cid, ch) in enumerate(items, start=1):
                t = ch["transport"]
                enc = ch["encoding"]
                a(f"{b}\\MN-1-{n}-{p}", cid)
                if kind == "mc2":
                    a(f"{b}\\MT-1-{n}-{p}", "S")
                    a(f"{b}\\NML\\N-1-{n}-{p}", 1)
                    a(f"{b}\\MWN-1-{n}-{p}-1", 0)
                    a(f"{b}\\MBM-1-{n}-{p}-1", "FW")
                    continue
                a(f"{b}\\MT-1-{n}-{p}", "D")
                words = t.get("words", 1)
                first = t.get("word", 1)
                a(f"{b}\\NML\\N-1-{n}-{p}", words)
                for e in range(1, words + 1):
                    a(f"{b}\\MWN-1-{n}-{p}-{e}", first + e - 1)
                    a(f"{b}\\MBM-1-{n}-{p}-{e}", _mask(16, enc.get("fields")) if words == 1 else "FW")
                    a(f"{b}\\MTO-1-{n}-{p}-{e}", "MSB")
                    a(f"{b}\\MFP-1-{n}-{p}-{e}", e)

    # ---- B groups: ARINC-429 links -------------------------------------------------------------------------
    by_link: dict[str, list[tuple[str, Mapping[str, Any]]]] = defaultdict(list)
    for cid, ch in sorted(ch_all.items()):
        if ch["transport"]["type"] == "arinc429":
            by_link[ch["transport"]["link"]].append((cid, ch))
    for link in rec_429:
        x += 1
        b = f"B-{x}"
        a(f"{b}\\DLN", link)
        a(f"{b}\\NBS\\N", 1)
        a(f"{b}\\BID-1", _bin(x, 8))
        a(f"{b}\\BNA-1", link)
        a(f"{b}\\BT-1", "A429")
        items = sorted(by_link.get(link, []), key=lambda it: it[1]["transport"]["label"])
        a(f"{b}\\NMS\\N-1", len(items))
        for n, (cid, ch) in enumerate(items, start=1):
            t = ch["transport"]
            a(f"{b}\\MID-1-{n}", n)
            a(f"{b}\\MNA-1-{n}", f"{link}-LBL{t['label']:03o}")
            a(f"{b}\\LBL-1-{n}", _bin(t["label"], 8))
            a(f"{b}\\SDI-1-{n}", t["sdi"])
            a(f"{b}\\MN\\N-1-{n}", 1)
            a(f"{b}\\MN-1-{n}-1", cid)
            a(f"{b}\\MT-1-{n}-1", "D")
            a(f"{b}\\NML\\N-1-{n}-1", 1)
            a(f"{b}\\MWN-1-{n}-1-1", 1)
            a(f"{b}\\MBM-1-{n}-1-1", "0" * 10 + "1" * 19 + "0" * 3)  # bits 11-29 of the 32-bit word
            a(f"{b}\\MTO-1-{n}-1-1", "LSB")

    # ---- P and D groups: FTI PCM ---------------------------------------------------------------------------
    for d, stream in enumerate(rec_pcm, start=1):
        s = buses["fti_pcm"][stream]
        items = sorted(
            (
                (cid, ch)
                for cid, ch in ch_all.items()
                if ch["transport"]["type"] == "fti_pcm" and ch["transport"]["stream"] == stream
            ),
            key=lambda it: it[1]["transport"]["word"],
        )
        n_words = len(items) + 1  # + sync word
        bits = len(FTI_SYNC_PATTERN) + s["word_bits"] * len(items)
        listed = [(cid, ch) for cid, ch in items if cid not in unpopulated]
        p = f"P-{d}"
        a(f"{p}\\DLN", stream)
        a(f"{p}\\D1", "NRZ-L")
        a(f"{p}\\D2", bits * s["minor_frame_hz"])
        a(f"{p}\\D3", "U")
        a(f"{p}\\D4", "N")
        a(f"{p}\\TF", "ONE")
        a(f"{p}\\F1", s["word_bits"])
        a(f"{p}\\F2", "M")
        a(f"{p}\\F3", "NO")
        a(f"{p}\\MF\\N", 1)
        a(f"{p}\\MF1", n_words)
        a(f"{p}\\MF2", bits)
        a(f"{p}\\MF3", "FPT")
        a(f"{p}\\MF4", len(FTI_SYNC_PATTERN))
        a(f"{p}\\MF5", FTI_SYNC_PATTERN)
        q = f"D-{d}"
        a(f"{q}\\DLN", stream)
        a(f"{q}\\ML\\N", 1)
        a(f"{q}\\MLN-1", f"{stream}-LIST")
        a(f"{q}\\MN\\N-1", len(listed))
        for n, (cid, ch) in enumerate(listed, start=1):
            a(f"{q}\\MN-1-{n}", cid)
            a(f"{q}\\MN3-1-{n}", "M")
            a(f"{q}\\LT-1-{n}", "MF")
            a(f"{q}\\MF-1-{n}", ch["transport"]["word"])
            a(f"{q}\\MFM-1-{n}", _mask(s["word_bits"], ch["encoding"].get("fields")))

    # ---- C groups: data conversion per recorded measurand --------------------------------------------------
    described = [cid for cid in recorded_channel_ids(compiled) if cid not in unpopulated]
    for k, cid in enumerate(described, start=1):
        ch = ch_all[cid]
        c = f"C-{k}"
        enc = ch["encoding"]
        a(f"{c}\\DCN", cid)
        a(f"{c}\\MN1", _clean(ch["name"], 64))
        if ch.get("sensor_type"):
            a(f"{c}\\TRD1", _clean(ch["sensor_type"], 32))
        a(f"{c}\\TRD4", "U")
        a(f"{c}\\MN3", EU_LABELS.get(ch["units"], _clean(ch["units"], 16)))
        a(f"{c}\\MN4", "PCM" if ch["transport"]["type"] == "fti_pcm" else "OTH")
        bfm = {"bnr": "TWO", "ubnr": "UNS"}.get(enc["type"], "OTH")
        a(f"{c}\\BFM", bfm)
        rng = ch["range"]
        if rng and rng["min"] is not None and rng["max"] is not None:
            a(f"{c}\\MOT1", repr(float(rng["max"])))
            a(f"{c}\\MOT2", repr(float(rng["min"])))
        for lim in ch["limits"]:
            code = {"steady_max": "MOT3", "warning_low": "MOT6"}.get(lim["kind"])
            if code and ("high" in lim or "low" in lim):
                a(f"{c}\\{code}", repr(float(lim.get("high", lim.get("low")))))
        bus_group = ch["rates"]["bus"]
        rate = groups.get(bus_group, {}).get("rate_hz") if bus_group else None
        if rate:
            a(f"{c}\\SR", repr(float(rate)))
        a(f"{c}\\CRT", crt)
        if enc["type"] in ("bnr", "ubnr") and ch["calibration"]:
            co = ch["calibration"]["coefficients"]
            a(f"{c}\\DCT", "COE")
            a(f"{c}\\CO\\N", len(co) - 1)
            a(f"{c}\\CO1", "N")
            a(f"{c}\\CO", repr(float(co[0])))
            for i, v in enumerate(co[1:], start=1):
                a(f"{c}\\CO-{i}", repr(float(v)))
        elif enc["type"] in ("bitfield", "enum", "code_word"):
            a(f"{c}\\DCT", "DIS")
            fields = enc.get("fields") or []
            if fields:
                a(f"{c}\\COM", "bits " + ",".join(f"{f['name']}@{f['lsb_bit']}" for f in fields))
            elif enc.get("code_table"):
                a(f"{c}\\COM", f"code table {enc['code_table']}")
            elif enc.get("format"):
                a(f"{c}\\COM", f"code format {enc['format']} prefixes {','.join(enc.get('prefixes', []))}")
        else:
            a(f"{c}\\DCT", "NON")
    return "\n".join(out) + "\n"


def tmats_packet_bytes(text: str, *, channel_id: int = 0) -> bytes:
    """A Chapter 10 Computer-Generated Format 1 (TMATS setup record) packet carrying ``text``."""
    from chapter10.computer import ComputerF1

    pkt = ComputerF1(
        channel_id=channel_id,
        data_type=0x01,
        header_version=1,
        sequence_number=0,
        rtc=0,
        version=TMATS_CSDW_VERSION,
        configuration_change=0,
        format=0,
        data=text.encode("ascii"),
    )
    return bytes(pkt)


def parse_tmats_bytes(packet_bytes: bytes) -> dict[str, str]:
    """Parse a Chapter 10 byte stream with pyChapter10 and return the TMATS attributes of its setup record.

    Raises ValueError if the stream holds no TMATS packet or a malformed attribute line.
    """
    from chapter10 import C10

    for pkt in C10(io.BytesIO(packet_bytes)):
        if pkt.data_type == 0x01:
            if pkt.version != TMATS_CSDW_VERSION:
                raise ValueError(f"TMATS CSDW version {pkt.version}, expected {TMATS_CSDW_VERSION}")
            for line in pkt.data.splitlines():
                s = line.strip()
                if s and (b":" not in s or not s.endswith(b";")):
                    raise ValueError(f"malformed TMATS line {s[:80]!r}")
            raw = pkt[""]
            return {k.decode("ascii"): v.decode("ascii") for k, v in raw.items()}
    raise ValueError("no TMATS setup record in the Chapter 10 stream")


@dataclass(frozen=True)
class RoundTrip:
    """Outcome of the TMATS round trip; ``ok`` when the channel lists and locations agree."""

    expected: tuple[str, ...]
    found: tuple[str, ...]
    location_mismatches: tuple[str, ...]

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.expected) - set(self.found)))

    @property
    def extra(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.found) - set(self.expected)))

    @property
    def ok(self) -> bool:
        return (
            not self.missing
            and not self.extra
            and not self.location_mismatches
            and len(self.found) == len(set(self.found))
        )


def _bus_locations(attrs: Mapping[str, str]) -> dict[str, tuple]:
    """measurand -> (data link, kind, address tuple) recovered from the parsed B groups."""
    out: dict[str, tuple] = {}
    groups = sorted({m.group(1) for k in attrs if (m := re.match(r"^B-(\d+)\\DLN$", k))}, key=int)
    for x in groups:
        b = f"B-{x}"
        link = attrs[f"{b}\\DLN"]
        bt = attrs.get(f"{b}\\BT-1")
        n_msgs = int(attrs.get(f"{b}\\NMS\\N-1", "0"))
        for n in range(1, n_msgs + 1):
            n_meas = int(attrs.get(f"{b}\\MN\\N-1-{n}", "0"))
            for p in range(1, n_meas + 1):
                name = attrs[f"{b}\\MN-1-{n}-{p}"]
                if bt == "A429":
                    out[name] = (link, "429", int(attrs[f"{b}\\LBL-1-{n}"], 2), attrs[f"{b}\\SDI-1-{n}"])
                    continue
                rt = int(attrs[f"{b}\\TRA-1-{n}"], 2)
                sa = int(attrs[f"{b}\\STA-1-{n}"], 2)
                trm = attrs[f"{b}\\TRM-1-{n}"]
                n_loc = int(attrs[f"{b}\\NML\\N-1-{n}-{p}"])
                words = tuple(int(attrs[f"{b}\\MWN-1-{n}-{p}-{e}"]) for e in range(1, n_loc + 1))
                mt = attrs[f"{b}\\MT-1-{n}-{p}"]
                if sa == 31:
                    mode = int(attrs[f"{b}\\DWC-1-{n}"], 2)
                    out[name] = (link, "status" if mt == "S" else f"modecode{mode}", rt)
                else:
                    out[name] = (link, "1553", rt, "T" if trm == "1" else "R", sa, words)
    return out


def _pcm_locations(attrs: Mapping[str, str]) -> dict[str, tuple]:
    out: dict[str, tuple] = {}
    groups = sorted({m.group(1) for k in attrs if (m := re.match(r"^D-(\d+)\\DLN$", k))}, key=int)
    for d in groups:
        link = attrs[f"D-{d}\\DLN"]
        for n in range(1, int(attrs.get(f"D-{d}\\MN\\N-1", "0")) + 1):
            out[attrs[f"D-{d}\\MN-1-{n}"]] = (link, "pcm", int(attrs[f"D-{d}\\MF-1-{n}"]))
    return out


def _expected_location(ch: Mapping[str, Any]) -> tuple:
    t = ch["transport"]
    if t["type"] == "mil1553":
        words = tuple(range(t["word"], t["word"] + t["words"]))
        return (t["bus"], "1553", t["rt"], t["tr"], t["sa"], words)
    if t["type"] == "mil1553_status":
        return (t["bus"], "status", t["rt"])
    if t["type"] == "mil1553_modecode":
        return (t["bus"], f"modecode{t['mode_code']}", t["rt"])
    if t["type"] == "arinc429":
        return (t["link"], "429", t["label"], str(t["sdi"]))
    if t["type"] == "fti_pcm":
        return (t["stream"], "pcm", t["word"])
    raise ValueError(f"not a recorded transport: {t['type']}")


def round_trip(
    compiled: Mapping[str, Any], attrs: Mapping[str, str], *, allow_unpopulated_pcm: bool = False
) -> RoundTrip:
    """Compare the parsed TMATS attributes with the dictionary: channel list (C groups) and locations (B/D
    groups). ``allow_unpopulated_pcm``: an FTI PCM channel that the recording describes in neither its C nor
    its D groups is a spare frame slot of this recording (``generate_tmats(pcm_unpopulated=...)``), not a
    mismatch."""
    found = tuple(
        v for k, v in sorted(attrs.items(), key=lambda kv: _c_index(kv[0])) if re.match(r"^C-\d+\\DCN$", k)
    )
    locs = {**_bus_locations(attrs), **_pcm_locations(attrs)}
    spare = set()
    if allow_unpopulated_pcm:
        spare = {
            cid
            for cid, ch in compiled["channels"].items()
            if ch["transport"]["type"] == "fti_pcm" and cid not in locs and cid not in found
        }
    expected = tuple(c for c in recorded_channel_ids(compiled) if c not in spare)
    mismatches = []
    for cid in expected:
        exp = _expected_location(compiled["channels"][cid])
        got = locs.get(cid)
        if got != exp:
            mismatches.append(f"{cid}: TMATS location {got} != dictionary {exp}")
    lsb_mismatch = _check_conversions(compiled, attrs)
    return RoundTrip(expected=expected, found=found, location_mismatches=tuple(mismatches + lsb_mismatch))


def _c_index(key: str) -> int:
    m = re.match(r"^C-(\d+)\\", key)
    return int(m.group(1)) if m else -1


def _check_conversions(compiled: Mapping[str, Any], attrs: Mapping[str, str]) -> list[str]:
    """The C-group polynomial gain equals the dictionary LSB for every BNR/UBNR measurand."""
    out = []
    index = {v: re.match(r"^C-(\d+)", k).group(1) for k, v in attrs.items() if re.match(r"^C-\d+\\DCN$", k)}
    for cid, k in index.items():
        ch = compiled["channels"].get(cid)
        if ch is None or ch["encoding"]["type"] not in ("bnr", "ubnr"):
            continue
        gain = attrs.get(f"C-{k}\\CO-1")
        if gain is None or not math.isclose(float(gain), ch["recorder_lsb"], rel_tol=1e-12):
            out.append(f"{cid}: TMATS CO-1 {gain} != recorder LSB {ch['recorder_lsb']}")
    return out
