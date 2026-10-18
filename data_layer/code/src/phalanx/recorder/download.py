"""Download simulator: the per-sortie batch transfer of a recording to the ground (architecture §6 M16, §8).

The aircraft-to-ground boundary is a post-flight batch download, hours later (report §5, §13;
data_pathway_and_formats.md Q5). A delivery is the bytes that reached the ground plus its arrival time
``t_ingest``; the ground decoder (M17) turns each delivery into contract records.

Outcomes per sortie (draws 0..3 of the UNIFORM stream ``recorder.download`` keyed by
(scenario, tail, sortie); delays from the same stream via the lognormal inverse CDF), ASSUMPTION
A-W1.7-10:

- **complete**: one delivery of the whole file at ``t_end + max(delay_min, LN(delay_median, sigma))``;
- **partial then retry** (probability ``p_partial``): the first transfer stops after a fraction of the bytes
  (a prefix; the decoder drops the incomplete last packet), and a retry later delivers the whole file;
- **repeat download** (probability ``p_duplicate``): the complete file is delivered again later.

Records delivered again carry the same ``record_id`` (it depends only on the recording, AD-38), so idempotent
ingest keeps one copy; the decoder marks every record of a repeat delivery DUPLICATE_DOWNLOAD (ground scope).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from phalanx.bus.clocks import SortieIdentity
from phalanx.core.rng import RngService

from .writer import SUBSYSTEM

__all__ = ["Delivery", "DownloadConfig", "simulate_download"]

_NS_PER_H = 3600 * 10**9


@dataclass(frozen=True)
class DownloadConfig:
    delay_median_h: float
    delay_sigma_ln: float
    delay_min_ns: int
    p_partial: float
    p_duplicate: float
    retry_median_h: float

    @classmethod
    def from_params(cls, platform: str = "tejas", **overrides: object) -> DownloadConfig:
        from phalanx.dictionary.params import load_params

        p = load_params("M16", platform=platform)["download"]
        cfg = cls(
            delay_median_h=float(p.value("delay_median")) / 3600.0,
            delay_sigma_ln=float(p.value("delay_sigma_ln")),
            delay_min_ns=round(p.value("delay_min") * 1e9),
            p_partial=float(p.value("p_partial")),
            p_duplicate=float(p.value("p_duplicate")),
            retry_median_h=float(p.value("retry_median")) / 3600.0,
        )
        return cls(**{**cfg.__dict__, **overrides}) if overrides else cfg


@dataclass(frozen=True)
class Delivery:
    """Bytes of one recording that reached the ground at ``t_ingest`` (sim-UTC ns).

    ``attempt`` 0 is the first delivery of the sortie; ``attempt > 0`` is a retry or repeat download.
    ``complete`` is False for an interrupted transfer (a prefix of the file).
    """

    tail_no: str
    sortie_id: str
    attempt: int
    t_ingest: int
    data: bytes
    complete: bool
    #: the downloaded recording's identity (contract 0.2.0, A-W0.4-22): the ground station knows which
    #: recorder file it downloaded, as it knows the tail and the sortie; None for the single bus-monitor
    #: capture
    recording_id: str | None = None
    sink: str | None = None


def _lognormal_ns(u: float, median_h: float, sigma: float) -> int:
    z = statistics.NormalDist().inv_cdf(min(max(u, 1e-12), 1 - 1e-12))
    return int(median_h * math.exp(sigma * z) * _NS_PER_H)


def simulate_download(
    data: bytes,
    t_end: int,
    ident: SortieIdentity,
    rng: RngService,
    cfg: DownloadConfig,
    *,
    recording_id: str | None = None,
    sink: str | None = None,
) -> tuple[Delivery, ...]:
    """Deliveries of one recording (``data``) whose sortie ended at ``t_end`` (sim-UTC ns).

    The outcome draws are keyed by the sortie, so every recording of a sortie (one per sink, contract 0.2.0)
    shares the post-flight download session's timing; ``recording_id`` / ``sink`` label the deliveries.
    """
    u = rng.stream(ident.key(subsystem=SUBSYSTEM, component="download")).draws(0, 6)
    first = int(t_end) + max(
        cfg.delay_min_ns, _lognormal_ns(float(u[0]), cfg.delay_median_h, cfg.delay_sigma_ln)
    )
    out: list[Delivery] = []
    t = first
    rid = {"recording_id": recording_id, "sink": sink}
    if float(u[1]) < cfg.p_partial:
        cut = max(1, int(len(data) * float(u[2])))
        out.append(Delivery(ident.tail_no, ident.sortie_id, 0, t, data[:cut], False, **rid))
        t += max(1, _lognormal_ns(float(u[3]), cfg.retry_median_h, cfg.delay_sigma_ln))
    out.append(Delivery(ident.tail_no, ident.sortie_id, len(out), t, data, True, **rid))
    if float(u[4]) < cfg.p_duplicate:
        t += max(1, _lognormal_ns(float(u[5]), cfg.retry_median_h, cfg.delay_sigma_ln))
        out.append(Delivery(ident.tail_no, ident.sortie_id, len(out), t, data, True, **rid))
    return tuple(out)
