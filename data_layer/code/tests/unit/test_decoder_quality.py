"""Decoder quality inferences (M17): SENTINEL (A-W1.7-16); DecoderConfig loads; setup binding refuses a
foreign dictionary."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.dictionary import load_dictionary
from phalanx.dictionary.tmats import generate_tmats
from phalanx.ground.decoder import DecoderConfig, SetupMismatch, setup_from_tmats
from phalanx.ground.decoder.decode import _sentinels

D = load_dictionary()
CFG = DecoderConfig.from_params()


def test_isolated_bottom_of_scale_is_a_sentinel():
    """A jump of > 10 LSB into the bottom of scale on an analog channel is a SENTINEL; the samples that
    stay at the bottom after it are not re-flagged."""
    cid = "HYD.SYS1.P"  # analog, range min 0
    ch = D.channel(cid)
    assert ch["signal"] == "analog" and ch["range"]["min"] == 0
    lsb = ch["recorder_lsb"]
    v = np.array([3000.0, 3001.0, 0.0, 3002.0, 3003.0, 0.0, 0.0, 0.0, 3004.0]) * lsb
    flags = _sentinels(D, np.full(v.size, cid, dtype=object), v, np.arange(v.size) * 25_000_000, CFG)
    assert flags.tolist() == [False, False, True, False, False, True, False, False, False]


def test_sentinel_needs_an_analog_channel_and_a_jump():
    """Negative controls: a computed channel's zero, a gradual approach to zero (steps <= 10 LSB) and a low
    value that is not the bottom of scale are not sentinels."""
    comp = next(
        c["channel_id"]
        for c in D.channels()
        if c["signal"] == "computed"
        and c["encoding"]["type"] == "bnr"
        and c["range"]
        and c["range"]["min"] == 0
    )
    v = np.array([500.0, 501.0, 0.0, 502.0])
    assert not _sentinels(D, np.full(4, comp, dtype=object), v, np.arange(4), CFG).any()
    cid = "HYD.SYS1.P"
    lsb = D.channel(cid)["recorder_lsb"]
    v2 = np.array([40.0, 30.0, 20.0, 10.0, 0.0, 0.0]) * lsb
    assert not _sentinels(D, np.full(6, cid, dtype=object), v2, np.arange(6), CFG).any()
    v3 = np.array([3000.0, 1.0, 3000.0]) * lsb
    assert not _sentinels(D, np.full(3, cid, dtype=object), v3, np.arange(3), CFG).any()


def test_decoder_config_loads_declared_values():
    assert CFG.processing_latency_ns == 8_000_000 and CFG.relay_latency_ns == 1_000_000
    assert CFG.monitor_latency_ns == 1_000 and CFG.rate_tolerance_ppm == pytest.approx(100.0)
    assert CFG.latency_model == "nominal"


def test_setup_binding_refuses_a_recording_from_another_dictionary():
    """BEA failure mode: decoding with the wrong frame layout. A different dictionary version or a moved
    measurand location is refused."""
    text = generate_tmats(D.compiled.content)
    setup_from_tmats(text, D)  # the right dictionary is accepted
    with pytest.raises(SetupMismatch, match="not written against"):
        setup_from_tmats(text.replace(f"dictionary tejas {D.dict_version}", "dictionary tejas 9.9.9"), D)
    moved = text.replace("B-2\\MWN-1-1-1-1:3;", "B-2\\MWN-1-1-1-1:4;", 1)
    assert moved != text
    with pytest.raises(SetupMismatch, match="layout differs"):
        setup_from_tmats(moved, D)
