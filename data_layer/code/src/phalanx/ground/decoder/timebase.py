"""RTC -> absolute time on the ground from the recording's time packets (M17; IRIG 106 §10.6.3).

Two times per recorder tag, with different meanings (contract ``param.samples``):

- **t_utc** -- what the aircraft time source said: the latest time packet at or before the tag, plus the RTC
  difference at the nominal 10 MHz (``T_g + (rtc - rtc_g) * 100 ns``, the RCC 123-16 §5.6 method). While the
  source is unlocked this is the recorder's free-running time (flag TIME_SOURCE_INTERNAL).
- **best time** (the decoder's reconstruction on the sim-UTC scale, used for ``t_bus`` and ``t_sample``) --
  the latest **externally locked** time packet k at or before the tag, plus the RTC difference scaled by the
  recorder crystal rate measured between the two latest locked packets (``rho_k``, true seconds per 1e7 RTC
  ticks): ``T_k + (rtc - R_k) * 100 ns * rho_k``. For a steady crystal this removes the crystal offset (the
  RCC sawtooth, <= 100 us per second by the Ch10 relative-time requirement) and carries time through a
  lock-loss holdover on the crystal rate measured before the loss.

**The time base is causal**: a tag's times depend only on time packets at or before it. A partial download
(a prefix of the file) and the later complete download therefore decode every shared record identically,
which idempotent ingest requires (``phalanx.streaming.dedup_by_record_id`` verifies that re-delivered
records are equal). Interpolating towards the *next* time packet would break this.

Flags (contract QualityFlags; ASSUMPTION A-W1.7-17):

- TIME_SOURCE_INTERNAL: the governing time packet reports an internal source (lock lost);
- DECODER_INTERPOLATED: the best time was reconstructed across a holdover (governing packet internal);
- CLOCK_SUSPECT: no locked packet yet; a holdover longer than ``holdover_tolerance``; a tag more than
  ``tail_tolerance`` after a locked packet with no later time packet (time packets missing); a crystal rate
  between locked packets off by more than ``rate_tolerance_ppm`` (a time jump while "locked"); an RTC sync
  error on the data packet; a time packet in IRIG day format (no year).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .reader import TimeRecords

__all__ = ["TimeBase", "TimeFlags"]

EXTERNAL = 0x1
NS_PER_TICK = 100


@dataclass(frozen=True)
class TimeFlags:
    internal: np.ndarray
    interpolated: np.ndarray
    suspect: np.ndarray


@dataclass(frozen=True)
class TimeBase:
    rtc: np.ndarray
    utc_ns: np.ndarray
    external: np.ndarray
    sync_error: np.ndarray
    day_format: np.ndarray
    rate_tolerance_ppm: float
    tail_tolerance_ticks: int
    holdover_tolerance_ticks: int

    @classmethod
    def from_records(
        cls,
        tr: TimeRecords,
        *,
        rate_tolerance_ppm: float,
        tail_tolerance_s: float,
        holdover_tolerance_s: float,
    ) -> TimeBase:
        order = np.argsort(tr.rtc, kind="stable")
        if tr.rtc.size == 0:
            raise ValueError("recording has no time packet: absolute time cannot be derived")
        return cls(
            rtc=tr.rtc[order],
            utc_ns=tr.utc_ms[order] * 1_000_000,
            external=tr.src[order] == EXTERNAL,
            sync_error=tr.sync_error[order],
            day_format=tr.day_format[order],
            rate_tolerance_ppm=float(rate_tolerance_ppm),
            tail_tolerance_ticks=int(tail_tolerance_s * 1e7),
            holdover_tolerance_ticks=int(holdover_tolerance_s * 1e7),
        )

    def raw_utc(self, rtc: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(t_utc ns, governed-by-internal-source, before-first-packet) for RTC tags."""
        r = np.asarray(rtc, dtype=np.int64)
        g = np.searchsorted(self.rtc, r, side="right") - 1
        before = g < 0
        gg = np.maximum(g, 0)
        t = self.utc_ns[gg] + (r - self.rtc[gg]) * NS_PER_TICK
        return t.astype(np.int64), ~self.external[gg], before

    def best(self, rtc: np.ndarray) -> tuple[np.ndarray, TimeFlags]:
        """Best sim-UTC estimate of RTC tags and the time-quality flags (causal; see module docstring)."""
        r = np.asarray(rtc, dtype=np.int64)
        t_raw, internal, before = self.raw_utc(r)
        ext = np.flatnonzero(self.external)
        if ext.size == 0:  # never locked: the aircraft time is all there is
            return t_raw, TimeFlags(internal, np.zeros(r.size, dtype=bool), np.ones(r.size, dtype=bool))
        ar, at = self.rtc[ext], self.utc_ns[ext]
        # crystal rate at each locked anchor, from the previous locked anchor (nominal at the first one)
        rho = np.ones(ext.size, dtype=np.float64)
        if ext.size >= 2:
            rho[1:] = (at[1:] - at[:-1]).astype(np.float64) / (
                (ar[1:] - ar[:-1]).astype(np.float64) * NS_PER_TICK
            )
        bad_rate = np.abs(rho - 1.0) > self.rate_tolerance_ppm * 1e-6
        k = np.searchsorted(ar, r, side="right") - 1  # latest locked anchor at or before the tag
        has = k >= 0
        kk = np.maximum(k, 0)
        dt = (r - ar[kk]).astype(np.float64) * NS_PER_TICK * rho[kk]
        out = np.where(has, at[kk] + np.rint(dt).astype(np.int64), t_raw)
        g = np.searchsorted(self.rtc, r, side="right") - 1  # governing time packet (any source)
        gg = np.maximum(g, 0)
        holdover = has & internal
        since = r - ar[kk]
        suspect = ~has | before | bad_rate[kk]
        suspect |= holdover & (since > self.holdover_tolerance_ticks)
        suspect |= ~holdover & has & ((r - self.rtc[gg]) > self.tail_tolerance_ticks)  # time packets missing
        suspect |= self.sync_error[gg] & (g >= 0)
        if self.day_format.any():
            suspect[:] = True
        return out.astype(np.int64), TimeFlags(internal, holdover, suspect)
