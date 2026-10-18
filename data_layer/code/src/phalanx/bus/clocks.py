"""Per-LRU oscillators: the clock domains of the data path (architecture §8, AD-06, AD-11, AD-35).

Every LRU unit runs on its own crystal: frame instants ``t_n = floor(phi + n * 1e9 / (f (1 + Delta)))`` ns
(:class:`phalanx.core.time.ClockDomain`, exact rational arithmetic). ``f`` is the LRU frame rate from the
dictionary (``lrus.yaml`` ``frame_hz``); ``Delta`` is a per-unit fractional frequency offset (an
installation property of the unit, constant across sorties, keyed by ``(scenario, serial)``); ``phi`` is the
power-on phase, fresh per sortie (keyed by ``(scenario, tail, sortie, sensor=<LRU>)``).

**One oscillator per LRU.** A sub-rate of an LRU (e.g. the DFCC transmit buffer at FCS40 inside its 80 Hz
frame) is phase-locked to the same crystal: its instants are every k-th frame tick, never an independent
clock. Two independent clocks for one crystal would create slips between an LRU's acquisition and its own
bus updates, which cannot happen physically.

**Who owns which crystal.** M13 (W1.6, A-W1.6-21) defines the acquisition clock domains of the LRUs it
acquires on (``phalanx.acquisition.config.acquisition_clock``: FADEC, DFCC, ADC, BHEEM_EU, ECFM_C, FTI_DAS).
For those LRUs the bus encoder must use the same domain: :func:`acquisition_oscillators` converts them to
:class:`LruOscillator` (sim-UTC phase = sortie epoch + M13 kernel phase), and ``encode_bus(...,
oscillators=...)`` / ``run_full_path(..., oscillators=...)`` take them. The keyed draws below
(:func:`lru_oscillator`) remain the oscillators of LRUs M13 does not acquire on (mission computer, INGPS,
OAC, ...) and of stand-alone tests. ``phalanx.bus.encoder.check_cir_on_oscillator`` checks at integration
(W2.2) that CIR ``t_sample`` values lie on the grid M15 uses.

Randomness (AD-37): only the declared streams in :data:`STREAMS`, addressed by draw index 0.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

from phalanx.core.rng import KeyPath, RngService, StreamDecl, Variate
from phalanx.core.time import NS_PER_S, ClockDomain, as_fraction

__all__ = [
    "STREAMS",
    "LruOscillator",
    "SortieIdentity",
    "acquisition_oscillators",
    "key_value",
    "lru_oscillator",
]

SUBSYSTEM = "bus"

STREAMS: tuple[StreamDecl, ...] = (
    StreamDecl(
        SUBSYSTEM,
        "osc_offset",
        ("scenario", "serial"),
        Variate.NORMAL,
        block_size=16,
        owner="M15",
        description="Per-LRU-unit oscillator fractional frequency offset (standard normal x sigma_ppm)",
    ),
    StreamDecl(
        SUBSYSTEM,
        "osc_phase",
        ("scenario", "tail", "sortie", "sensor"),
        Variate.UNIFORM,
        block_size=16,
        owner="M15",
        description="Per-LRU oscillator power-on phase, fraction of one frame (sensor = LRU name)",
    ),
    StreamDecl(
        SUBSYSTEM,
        "rt_response",
        ("scenario", "serial"),
        Variate.UNIFORM,
        block_size=16,
        owner="M15",
        description="Per-RT-unit MIL-STD-1553 response time, uniform inside the configured band",
    ),
)

_BAD = re.compile(r"[^A-Za-z0-9._:+\-]")


def key_value(text: str) -> str:
    """A core.rng identity value for free text: characters outside [A-Za-z0-9._:+-] become '-'."""
    out = _BAD.sub("-", text)
    if not out:
        raise ValueError("empty identity value")
    return out


@dataclass(frozen=True)
class SortieIdentity:
    """Identity of one recording: keys every data-path stream (AD-37) and the contract linkage fields.

    ``lru_serials`` maps an LRU name to the installed unit's serial number (sortie manifest
    ``lru_serials``); a missing LRU defaults to ``"<tail_no>:<LRU>"`` (the unit at that position of that
    tail), so oscillator offsets stay constant across sorties of a tail even without a serial table.
    """

    scenario: str
    tail_no: str
    sortie_id: str
    lru_serials: Mapping[str, str] | None = None
    recorder_serial: str | None = None
    engine_serial: str | None = None

    def serial_of(self, lru: str) -> str:
        s = (self.lru_serials or {}).get(lru)
        return key_value(s if s is not None else f"{self.tail_no}:{lru}")

    def recorder_unit(self) -> str:
        return key_value(self.recorder_serial or f"{self.tail_no}:RECORDER")

    def key(self, **extra: str | int) -> KeyPath:
        return KeyPath.of(
            scenario=key_value(self.scenario),
            tail=key_value(self.tail_no),
            sortie=key_value(self.sortie_id),
            **extra,
        )


@dataclass(frozen=True)
class LruOscillator:
    """One LRU unit's crystal: frame rate, fractional offset (ppm) and power-on phase (ns)."""

    lru: str
    frame_hz: Fraction
    offset_ppm: Fraction
    phase_ns: Fraction

    def tick_domain(self) -> ClockDomain:
        """The LRU frame clock (acquisition instants of LRU-framed channels)."""
        return ClockDomain(f"{self.lru}.frame", self.frame_hz, self.offset_ppm, self.phase_ns)

    def sub_domain(self, rate_hz: float | Fraction, slot: int = 0) -> ClockDomain:
        """A sub-rate phase-locked to the frame: every k-th tick, starting at tick ``slot``.

        Requires ``frame_hz / rate_hz`` to be an integer k (all dictionary producer groups divide their LRU
        frame). ``slot`` in ``[0, k)`` selects which tick of each k-cycle.
        """
        rate = as_fraction(rate_hz, "rate_hz")
        k = self.frame_hz / rate
        if k.denominator != 1 or k < 1:
            raise ValueError(
                f"{self.lru}: rate {rate} Hz is not an integer sub-multiple of {self.frame_hz} Hz"
            )
        if not 0 <= slot < k:
            raise ValueError(f"slot {slot} outside [0, {k})")
        tick = self.tick_domain()
        return ClockDomain(f"{self.lru}.sub{k}", rate, self.offset_ppm, self.phase_ns + slot * tick.period_ns)

    @property
    def period_ns(self) -> Fraction:
        return self.tick_domain().period_ns


def _offset_ppm(rng: RngService, ident: SortieIdentity, lru: str, sigma_ppm: float) -> Fraction:
    z = float(
        rng.stream(
            KeyPath.of(
                scenario=key_value(ident.scenario),
                serial=ident.serial_of(lru),
                subsystem=SUBSYSTEM,
                component="osc_offset",
            )
        ).draws(0, 1)[0]
    )
    # 1 ppb resolution keeps the rational small and the value exact across platforms
    return Fraction(int(np.rint(z * sigma_ppm * 1000.0)), 1000)


def _phase_ns(rng: RngService, ident: SortieIdentity, lru: str, frame_hz: Fraction) -> Fraction:
    u = float(
        rng.stream(ident.key(sensor=key_value(lru), subsystem=SUBSYSTEM, component="osc_phase")).draws(0, 1)[
            0
        ]
    )
    period = Fraction(NS_PER_S) / frame_hz
    return Fraction(int(u * float(period)))


def lru_oscillator(
    lru: str,
    frame_hz: float | Fraction,
    ident: SortieIdentity,
    rng: RngService,
    *,
    sigma_ppm: float,
    offset_override_ppm: Mapping[str, float] | None = None,
    phase_override_ns: Mapping[str, int] | None = None,
) -> LruOscillator:
    """The oscillator of LRU ``lru`` installed on ``ident.tail_no`` for sortie ``ident.sortie_id``.

    ``offset_override_ppm`` / ``phase_override_ns`` replace the keyed draws (tests and calibration only).
    """
    f = as_fraction(frame_hz, "frame_hz")
    if offset_override_ppm and lru in offset_override_ppm:
        off = as_fraction(offset_override_ppm[lru], "offset_ppm")
    else:
        off = _offset_ppm(rng, ident, lru, sigma_ppm)
    if phase_override_ns and lru in phase_override_ns:
        ph = as_fraction(phase_override_ns[lru], "phase_ns")
    else:
        ph = _phase_ns(rng, ident, lru, f)
    return LruOscillator(lru, f, off, ph)


def acquisition_oscillators(
    dictionary: Any,
    epoch_ns: int,
    *,
    platform: str = "tejas",
    config_root: Path | None = None,
) -> dict[str, LruOscillator]:
    """M13's acquisition clock domains (A-W1.6-21) as bus oscillators, keyed by LRU name.

    M13 times its samples in kernel time (ns from the sortie's truth origin) and writes CIR ``t_sample`` =
    ``epoch_ns`` + kernel time. The oscillator returned here has the same nominal rate (the LRU's dictionary
    ``frame_hz``), offset and phase ``epoch_ns + phase``; ``floor(epoch + x) = epoch + floor(x)`` for an
    integer epoch, so its frame ticks are exactly M13's acquisition instants of that LRU, and every M13
    sub-rate (same offset and phase, rate dividing the frame) falls on every k-th tick.

    Only LRUs that have an M13 clock set and a dictionary ``frame_hz`` are returned; the others keep the keyed
    draws of :func:`lru_oscillator`.
    """
    from phalanx.acquisition.config import acquisition_clock
    from phalanx.dictionary.params import load_params, params_dir
    from phalanx.dictionary.yamlio import load_yaml

    params = load_params("M13", platform=platform, config_root=config_root)
    acq_map = load_yaml(params_dir(platform, config_root) / "M13" / "acquisition_map.yaml")
    lrus = dictionary.content["lrus"]
    out: dict[str, LruOscillator] = {}
    for lru in sorted(acq_map.get("clocks") or {}):
        f = (lrus.get(lru) or {}).get("frame_hz")
        if f is None:
            continue
        dom = acquisition_clock(lru, f, params=params, acq_map=acq_map)
        out[lru] = LruOscillator(
            lru, as_fraction(f, "frame_hz"), dom.offset_ppm, dom.phase_ns + int(epoch_ns)
        )
    return out
