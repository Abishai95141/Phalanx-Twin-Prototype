"""CWS words: M14's recorded LRU-computed channels (AD-42: CWS legends belong to M14).

The CWS electronic unit packs the active legends into ARINC-429 bitfield words that the recorder logs on
change (dictionary channels ``CWS.LEGEND.A/B``, ``CWS.MASTER``, ``CWS.VOICE.*``; ``acq_lru: CWS``,
``signal: computed``). Bit positions come from each channel's dictionary encoding (SYNTHETIC ICD, AD-39):

- legend ``CWS-Lnn`` -> its field in ``CWS.LEGEND.A`` (L01-L15) or ``CWS.LEGEND.B`` (L16-L30);
- ``CWS.MASTER``: ``MASTER_WARNING`` while any displayed WARNING legend is active, ``MASTER_CAUTION`` while
  any displayed CAUTION legend is active (ADVISORY legends light no master);
- ``CWS.VOICE.*``: ``VOICE_WARNING_ACTIVE`` while the code that names that channel (``voice:`` in the code
  table) is active.

A code is active while M14 holds a caution for it (a declared internal test, a limit monitor or a
controller report not yet cleared). ASSUMPTION A-W1.5-41: the legend list and caution logic are not public;
the pilot's master reset is not modelled, so a MASTER bit stays set while its legend is active.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

__all__ = ["CWS_PORTS", "CwsMap", "build_cws_map"]

#: output port name -> dictionary channel (M14 ``RECORDED``)
CWS_PORTS: Mapping[str, str] = {
    "cws_legend_a": "CWS.LEGEND.A",
    "cws_legend_b": "CWS.LEGEND.B",
    "cws_master": "CWS.MASTER",
    "cws_voice_aoa": "CWS.VOICE.AOA",
    "cws_voice_canopy": "CWS.VOICE.CANOPY",
    "cws_voice_low_alt": "CWS.VOICE.LOW_ALT",
    "cws_voice_uc": "CWS.VOICE.UC",
}
_MASTER = {"WARNING": "MASTER_WARNING", "CAUTION": "MASTER_CAUTION"}


@dataclass(frozen=True)
class CwsMap:
    """``bits[c, p]``: the bits code ``c`` sets in port ``p`` (``ports`` order) while it is active."""

    ports: tuple[str, ...]
    bits: np.ndarray  # (n_codes, n_ports) int64

    def words(self, active: np.ndarray) -> dict[str, np.ndarray]:
        """Port -> 0-d int64 word for a boolean (n_codes,) activity vector."""
        w = np.bitwise_or.reduce(self.bits[np.asarray(active, bool)], axis=0, initial=0)
        return {p: np.array(int(w[i]), np.int64) for i, p in enumerate(self.ports)}

    def series(self, active: np.ndarray) -> dict[str, np.ndarray]:
        """Port -> (L,) int64 words for an (L, n_codes) boolean activity matrix."""
        a = np.asarray(active, bool)
        out = np.zeros((a.shape[0], len(self.ports)), np.int64)
        for c in np.flatnonzero(a.any(axis=0)):
            out[a[:, c]] |= self.bits[c]
        return {p: out[:, i] for i, p in enumerate(self.ports)}


def _fields(dictionary, cid: str) -> dict[str, int]:
    enc = dictionary.channel(cid).get("encoding") or {}
    if enc.get("type") != "bitfield":
        raise ValueError(f"{cid}: CWS channel encoding must be a bitfield, got {enc.get('type')!r}")
    return {str(f["name"]): 1 << int(f["lsb_bit"]) for f in enc["fields"]}


def build_cws_map(dictionary, codes) -> CwsMap:
    """The CWS bit map of ``codes`` (an M14 ``CodeTable``) from the dictionary encodings.

    Raises ValueError if the dictionary's CWS channels and ``CWS_PORTS`` differ, a legend has no field, or a
    voice channel is named by other than exactly one code.
    """
    cws = sorted(c["channel_id"] for c in dictionary.channels() if c.get("acq_lru") == "CWS")
    if cws != sorted(CWS_PORTS.values()):
        raise ValueError(f"dictionary CWS channels {cws} != M14 CWS ports {sorted(CWS_PORTS.values())}")
    ports = tuple(CWS_PORTS)
    pidx = {CWS_PORTS[p]: i for i, p in enumerate(ports)}
    fields = {cid: _fields(dictionary, cid) for cid in CWS_PORTS.values()}
    legend_at = {
        name: (cid, bit) for cid in ("CWS.LEGEND.A", "CWS.LEGEND.B") for name, bit in fields[cid].items()
    }
    bits = np.zeros((len(codes.codes), len(ports)), np.int64)
    voiced: dict[str, str] = {}
    for c in codes.codes:
        if c.legend is not None and c.displayed:
            if c.legend not in legend_at:
                raise ValueError(f"{c.code}: legend {c.legend} has no field in the CWS legend words")
            cid, bit = legend_at[c.legend]
            bits[c.index, pidx[cid]] |= bit
            if c.severity in _MASTER:
                bits[c.index, pidx["CWS.MASTER"]] |= fields["CWS.MASTER"][_MASTER[c.severity]]
        if c.voice_channel is not None:
            if c.voice_channel in voiced:
                raise ValueError(f"{c.voice_channel} named by {voiced[c.voice_channel]} and {c.code}")
            voiced[c.voice_channel] = c.code
            bits[c.index, pidx[c.voice_channel]] |= fields[c.voice_channel]["VOICE_WARNING_ACTIVE"]
    missing = sorted(v for v in CWS_PORTS.values() if v.startswith("CWS.VOICE.") and v not in voiced)
    if missing:
        raise ValueError(f"no code drives the voice channels {missing}")
    return CwsMap(ports, bits)
