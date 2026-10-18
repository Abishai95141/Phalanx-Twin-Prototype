"""Download simulator (M16; A-W1.7-10)."""

from __future__ import annotations

import numpy as np

from phalanx.bus.clocks import SortieIdentity
from phalanx.core.rng import RngService, StreamRegistry
from phalanx.recorder.download import DownloadConfig, simulate_download
from phalanx.recorder.writer import STREAMS

DATA = bytes(range(256)) * 40
T_END = 1_790_000_000 * 10**9


def _rng(root=11):
    return RngService(root, StreamRegistry(STREAMS))


def _ident(k=0):
    return SortieIdentity("SCN", "KH2003", f"KH2003-S{k}")


def test_complete_download_after_the_minimum_delay():
    cfg = DownloadConfig.from_params(p_partial=0.0, p_duplicate=0.0)
    d = simulate_download(DATA, T_END, _ident(), _rng(), cfg)
    assert len(d) == 1 and d[0].complete and d[0].data == DATA and d[0].attempt == 0
    assert d[0].t_ingest >= T_END + cfg.delay_min_ns


def test_partial_transfer_is_a_prefix_then_a_full_retry():
    cfg = DownloadConfig.from_params(p_partial=1.0, p_duplicate=0.0)
    d = simulate_download(DATA, T_END, _ident(), _rng(), cfg)
    assert [x.attempt for x in d] == [0, 1] and [x.complete for x in d] == [False, True]
    assert DATA.startswith(d[0].data) and len(d[0].data) < len(DATA) and d[1].data == DATA
    assert d[1].t_ingest > d[0].t_ingest


def test_repeat_download_delivers_the_same_bytes_later():
    cfg = DownloadConfig.from_params(p_partial=1.0, p_duplicate=1.0)
    d = simulate_download(DATA, T_END, _ident(), _rng(), cfg)
    assert [x.attempt for x in d] == [0, 1, 2] and d[2].data == d[1].data == DATA
    assert d[0].t_ingest < d[1].t_ingest < d[2].t_ingest


def test_download_is_deterministic_and_keyed_by_sortie():
    cfg = DownloadConfig.from_params()
    assert simulate_download(DATA, T_END, _ident(), _rng(), cfg) == simulate_download(
        DATA, T_END, _ident(), _rng(), cfg
    )
    t = [simulate_download(DATA, T_END, _ident(k), _rng(), cfg)[0].t_ingest for k in range(5)]
    assert len(set(t)) == 5


def test_delay_distribution_matches_the_configured_lognormal():
    """n = 400 sorties: median delay within 12 % of 2 h (lognormal sigma 0.8 -> SE of the median ~5 %)."""
    cfg = DownloadConfig.from_params(p_partial=0.0, p_duplicate=0.0)
    rng = _rng()
    delays = (
        np.array(
            [simulate_download(DATA, T_END, _ident(k), rng, cfg)[0].t_ingest - T_END for k in range(400)]
        )
        / 3.6e12
    )
    assert abs(np.median(delays) / 2.0 - 1) < 0.12
    assert delays.min() * 3600 >= cfg.delay_min_ns / 1e9 - 1e-9
