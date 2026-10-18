"""The one acquisition path shared by both M13 entry points (in-loop lanes and recording).

``AcquisitionCore.process`` takes a block of contiguous truth frames of sensor outputs (SI, frame ends) and
returns, per clock domain, every sample that falls in ``[t_start[0], t_end[-1])`` with its absolute sample
index, instant, integer code, EU value, EU truth, quality flags and validity. The in-loop module and the
recorder both call it with the same configuration, the same keyed streams (indexed by absolute sample number)
and the same state layout, so a channel's value at an acquisition instant is the same in both paths, bitwise
(A6).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from phalanx.core.rng import Stream, StreamDecl, Variate
from phalanx.core.sampling import samples_for_steps

from . import kernel as K
from .config import AcqConfig, DomainSpec

NOISE_STREAM = StreamDecl(
    "acquisition",
    "noise",
    ("scenario", "tail", "sortie", "sensor"),
    Variate.NORMAL,
    4096,
    "phalanx.acquisition (M13)",
    "idiosyncratic sensor noise; one standard normal per acquisition sample (index = absolute sample number)",
)
EVENT_STREAM = StreamDecl(
    "acquisition",
    "events",
    ("scenario", "tail", "sortie", "sensor"),
    Variate.UNIFORM,
    4096,
    "phalanx.acquisition (M13)",
    "per-sample uniforms: tail mixture, freeze start, freeze duration, glitch, slip (index = 5 n + slot)",
)
STREAMS = (NOISE_STREAM, EVENT_STREAM)

StreamFn = Callable[[str, str], Stream]  # (component, channel_id) -> Stream


@dataclass(frozen=True)
class DomainSamples:
    """Samples of one domain in one block. Per-sample arrays are (n_s,) or (n_s, n_channels_of_domain)."""

    domain: int
    channels: tuple[int, ...]
    first: int
    times: np.ndarray
    step: np.ndarray
    slot: np.ndarray
    count: np.ndarray
    first_of_step: np.ndarray
    code: np.ndarray
    value: np.ndarray
    truth: np.ndarray
    flags: np.ndarray
    validity: np.ndarray

    @property
    def sample_index(self) -> np.ndarray:
        return self.first + np.arange(self.times.size, dtype=np.int64)


def collision_mask(dom: DomainSpec, times: np.ndarray, slot_phase_ns: np.ndarray) -> np.ndarray:
    """(n_s, n_ch) int: 1 where a read at ``times`` lies within +-w/2 of its channel's converter update.

    Exact integer arithmetic on the two ``ClockDomain`` oscillators (the converter and the reader), so slip
    windows recur with period 1/(f Delta) and are phase-related across channels by their slot phases (AD-06).
    """
    n_s, n_c = times.size, slot_phase_ns.size
    out = np.zeros((n_s, n_c), dtype=np.int64)
    if dom.slip is None or n_s == 0:
        return out
    conv = dom.slip.converter
    pmax = int(slot_phase_ns.max(initial=0))
    m0 = max(0, conv.index_at_or_before(int(times[0]) - pmax) - 1)
    m1 = conv.first_index_at_or_after(int(times[-1])) + 2
    upd = conv.sample_times_ns(m0, m1 - m0)
    for j in range(n_c):
        a = upd + slot_phase_ns[j]
        idx = np.searchsorted(a, times, side="left")
        right = a[np.minimum(idx, a.size - 1)]
        left = a[np.maximum(idx - 1, 0)]
        d_right = np.where(idx < a.size, right - times, np.iinfo(np.int64).max // 4)
        d_left = np.where(idx > 0, times - left, np.iinfo(np.int64).max // 4)
        d = np.minimum(np.abs(d_right), np.abs(d_left))
        out[:, j] = (2 * d <= dom.slip.window_ns).astype(np.int64)
    return out


class AcquisitionCore:
    """Acquisition of ``cfg.channels`` from contiguous frame blocks (stateless; state is passed in and
    out)."""

    def __init__(self, cfg: AcqConfig, stream_fn: StreamFn) -> None:
        self.cfg = cfg
        self._stream_fn = stream_fn
        self._use_noise = cfg.P[:, K.AP_SIGMA] > 0.0
        self._use_u = (
            ((cfg.P[:, K.AP_SIGMA] > 0.0) & (cfg.P[:, K.AP_TAILP] > 0.0))
            | (cfg.P[:, K.AP_FRZP] > 0.0)
            | (cfg.P[:, K.AP_GLP] > 0.0)
            | (cfg.Q[:, K.AQ_SLIP] == 1)
        )

    def init_state(self) -> dict[str, np.ndarray]:
        cfg = self.cfg
        return {
            "af": np.zeros((cfg.n, K.N_AF), dtype=np.float64),
            "ai": np.zeros((cfg.n, K.N_AI), dtype=np.int64),
            "n_next": np.array([d.clock.first_index_at_or_after(0) for d in cfg.domains], dtype=np.int64),
        }

    def stream(self, component: str, c: int) -> Stream:
        return self._stream_fn(component, self.cfg.channels[c])

    def _draws(self, chans: tuple[int, ...], first: int, n_s: int) -> tuple[np.ndarray, np.ndarray]:
        z = np.zeros((n_s, len(chans)), dtype=np.float64)
        u = np.ones((n_s, len(chans), K.N_U), dtype=np.float64)  # 1.0 never triggers a "< p" event
        if n_s == 0:
            return z, u
        for j, c in enumerate(chans):
            if self._use_noise[c]:
                z[:, j] = self.stream("noise", c).draws(first, n_s)
            if self._use_u[c]:
                u[:, j, :] = self.stream("events", c).draws(K.N_U * first, K.N_U * n_s).reshape(n_s, K.N_U)
        return z, u

    def process(
        self,
        state: dict[str, np.ndarray],
        S: np.ndarray,
        X: np.ndarray,
        t_start: np.ndarray,
        t_end: np.ndarray,
        phase: np.ndarray,
        *,
        kernel: Callable = K.acq_kernel,
    ) -> tuple[dict[str, np.ndarray], list[DomainSamples]]:
        """Acquire one block. ``S``/``X``: (L, n) sensor output / truth (SI) at the frame ends, columns in
        ``cfg.channels`` order. Returns the new state and the samples of every domain."""
        cfg = self.cfg
        t_start = np.asarray(t_start, dtype=np.int64)
        t_end = np.asarray(t_end, dtype=np.int64)
        phase = np.ascontiguousarray(np.asarray(phase, dtype=np.int64).reshape(t_start.size))
        af = state["af"].copy()
        ai = state["ai"].copy()
        n_next = state["n_next"].copy()
        out: list[DomainSamples] = []
        for di, dom in enumerate(cfg.domains):
            ch = dom.channels
            ss = samples_for_steps(dom.clock, int(n_next[di]), t_start, t_end)
            n_next[di] = ss.next_index
            n_s = ss.times.size
            w = (ss.times - t_start[ss.step]).astype(np.float64) / (t_end[ss.step] - t_start[ss.step]).astype(
                np.float64
            )
            z, u = self._draws(ch, ss.first, n_s)
            coll = collision_mask(dom, ss.times, cfg.slot_phase_ns[list(ch)])
            idx = np.asarray(ch, dtype=np.int64)
            f2, i2, code, val, tru, flg, vld = kernel(
                np.ascontiguousarray(af[idx]),
                np.ascontiguousarray(ai[idx]),
                np.ascontiguousarray(cfg.P[idx]),
                np.ascontiguousarray(cfg.Q[idx]),
                np.ascontiguousarray(cfg.regime[idx]),
                cfg.airborne,
                np.ascontiguousarray(S[:, idx], dtype=np.float64),
                np.ascontiguousarray(X[:, idx], dtype=np.float64),
                t_start,
                t_end,
                ss.times,
                ss.step,
                w,
                phase,
                z,
                u,
                coll,
            )
            af[idx] = f2
            ai[idx] = i2
            out.append(
                DomainSamples(
                    di,
                    ch,
                    ss.first,
                    ss.times,
                    ss.step,
                    ss.slot,
                    ss.count,
                    ss.first_of_step,
                    code,
                    val,
                    tru,
                    flg,
                    vld,
                )
            )
        return {"af": af, "ai": ai, "n_next": n_next}, out
