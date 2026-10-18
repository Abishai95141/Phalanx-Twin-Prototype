"""The recording's setup record: event types and the recorder channel list (M16).

The setup record is the M01 TMATS with the dictionary's recorder setup (``generate_tmats(recording=True)``:
recording events and the time-based index, rule R-REC-SETUP, A-W0.3-44), plus the caller's event types
(``writer.setup_record``). The dictionary stays the single source of truth for the channel, bus, measurand and
conversion description (G, R channel list, B, P, D, C groups) **and** for the recorder attributes
(``R-1\\EV``, ``R-1\\IDX``; IRIG 106 §10.6.7.3: "Index packets will be enabled if recording event packets are
enabled"; TMATS Table 9-3 R-x\\EV, R-x\\IDX).

History: W1.7 overlaid ``R-1\\EV`` / ``R-1\\IDX`` on the dictionary TMATS here (``compose_setup_record``,
A-W1.7-12). Dictionary 0.1.2 generates byte-identical lines, so the W2.2 migration removed the overlay
(``tests/unit/test_w22_datapath_migrations.py`` pins the recording bytes across the change).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "EventDef",
    "RecorderChannels",
    "recorder_channels",
]

_ATTR = re.compile(r"^([^:]+):(.*);$")


@dataclass(frozen=True)
class EventDef:
    """One recording-event type of the setup record (TMATS R-x\\EV-n)."""

    event_id: str  # <= 32 characters
    description: str
    kind: str = "O"  # E external, D measurement discrete, L measurement limit, R recorder, O other

    def __post_init__(self) -> None:
        if not self.event_id or len(self.event_id) > 32 or ";" in self.event_id or ":" in self.event_id:
            raise ValueError(f"bad TMATS event id {self.event_id!r}")
        if self.kind not in ("E", "D", "L", "R", "O"):
            raise ValueError(f"bad event type {self.kind!r}")


@dataclass(frozen=True)
class RecorderChannels:
    """Channel IDs of the recorder data sources, read from the dictionary TMATS R-1 group."""

    time: int
    mil1553: dict[str, int]
    arinc429: dict[str, int]
    pcm: dict[str, int]

    @property
    def max_id(self) -> int:
        return max([self.time, *self.mil1553.values(), *self.arinc429.values(), *self.pcm.values()])


def _attrs(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _ATTR.match(line.strip())
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out


def recorder_channels(tmats_text: str) -> RecorderChannels:
    a = _attrs(tmats_text)
    n = int(a["R-1\\N"])
    time_id, m1553, a429, pcm = None, {}, {}, {}
    for k in range(1, n + 1):
        cid = int(a[f"R-1\\TK1-{k}"])
        cdt = a[f"R-1\\CDT-{k}"]
        name = a[f"R-1\\DSI-{k}"]
        if cdt == "TIMEIN":
            time_id = cid
        elif cdt == "1553IN":
            m1553[name] = cid
        elif cdt == "429IN":
            a429[name] = cid
        elif cdt == "PCMIN":
            pcm[name] = cid
    if time_id is None:
        raise ValueError("setup record has no time channel")
    return RecorderChannels(time_id, m1553, a429, pcm)
