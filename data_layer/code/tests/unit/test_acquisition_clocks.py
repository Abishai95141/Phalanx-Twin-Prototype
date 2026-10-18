"""M13 acquisition clock domains (A-W1.6-21; architecture §8, AD-35, AD-39)."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from phalanx.acquisition.config import (
    acquisition_clock,
    acquisition_domain_lru,
    build_acquisition_config,
    clock_consistency_problems,
)
from phalanx.core.module import ContractError
from phalanx.core.time import truth_step_times_ns
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_params

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


def domain(d, cid):
    acq = build_acquisition_config(d, (cid,), sensor_channels=(cid,))
    return acq.domains[0]


def test_dfcc_samples_on_truth_frames(d):
    """DFCC (and ADC) acquisition at 80 Hz is the exact rate group k = 0 mod 3 (architecture §8)."""
    for cid in ("FCS.RSA.Q.A", "AD.PS.A"):
        clk = domain(d, cid).clock
        t = clk.sample_times_ns(0, 2400)
        np.testing.assert_array_equal(t, truth_step_times_ns(np.arange(0, 7200, 3)))


def test_fadec_domain_drifts_against_truth(d):
    """FADEC: 60 Hz nominal + 50 ppm, phase 3.1 ms: the sample count over 1,000 s is 60,000 (1 + 50e-6) +- 1
    and the instants are not tied to truth frames."""
    m13 = load_params("M13")
    clk = domain(d, "ENG.N2.A").clock
    n0, n1 = clk.indices_in(0, 1_000 * 10**9)
    assert abs((n1 - n0) - 60_000 * (1 + 50e-6)) <= 1
    assert clk.sample_time_ns(0) == round(float(m13["clock_fadec"].value("phase")) * 1e9)
    t = clk.sample_times_ns(0, 600)
    frames = set(truth_step_times_ns(np.arange(0, 2400)).tolist())
    assert sum(int(x) in frames for x in t) < 10


def test_one_oscillator_per_lru_across_rates(d):
    """The utility EU's 40 Hz, 10 Hz and 200 Hz acquisitions share one oscillator offset (one crystal)."""
    offs = {domain(d, c).clock.offset_ppm for c in ("BRK.PRESS.L", "HYD.SYS1.T", "HYD.SYS1.P")}
    assert len(offs) == 1


def test_every_tejas_acquiring_lru_has_a_clock(d):
    """All acquisition-domain LRUs of the M12 channels have a clock set (no silent default)."""
    from phalanx.sensors.config import build_sensor_config

    sens = build_sensor_config(d)
    acq = build_acquisition_config(d, sens.channels, sensor_channels=sens.channels)
    assert {dm.lru for dm in acq.domains} == {acquisition_domain_lru(d, c) for c in sens.channels}


def m13_streams(d):
    """Every channel M13 can acquire in the Tejas configuration: a numeric periodic channel (native step,
    range, rate) whose dictionary acquisition domain has an M13 clock set. M12 sensors read s_inst; the rest
    are LRU-computed channels recorded from supplied values."""
    from phalanx.dictionary.params import params_dir
    from phalanx.dictionary.yamlio import load_yaml

    clocks = load_yaml(params_dir("tejas") / "M13" / "acquisition_map.yaml")["clocks"]
    out = []
    for ch in d.channels():
        cid, rng = ch["channel_id"], ch.get("range") or {}
        if ch.get("native_step") is None or rng.get("min") is None or rng.get("max") is None:
            continue
        if d.acquisition_rate_hz(cid) is None:
            continue
        try:
            d.eu_conversion(cid)
        except ValueError:  # no numeric SI form yet (SPS.JFS.SPEED: rated speed not public)
            continue
        try:
            owner = acquisition_domain_lru(d, cid)
        except ContractError:  # e.g. HF vibration front end: not an LRU clock
            continue
        if owner in clocks:
            out.append(cid)
    return tuple(out)


def test_every_m13_stream_is_on_its_dictionary_acquisition_domain(d):
    """W1.6 follow-up: for every M13 stream (278 channels: 144 numeric M12 sensors + 134 computed/other, incl.
    SPS.JFS.SPEED, convertible since dictionary 0.1.2, and the 28 numeric channels on the LRU clock sets W2.2
    phase B added: 22 INS/GPS, AHRS and radar-altimeter outputs, 4 LRU temperatures, SYS.TIME.UTC and
    ENG.THRUST_EST) the clock domain and rate equal the dictionary's acquisition domain (rate-group domain
    LRU, else the owning LRU) and acquisition rate. ENG.WFAB (acq_lru FADEC, rate group FTI) is on the FTI_DAS
    crystal at 64 Hz, shared with the FTI boom channels. Words (no native step) are W2.2's word path
    (tests/integration/test_w22_word_path.py)."""
    from phalanx.sensors.config import build_sensor_config

    sens = build_sensor_config(d)
    streams = m13_streams(d)
    numeric = {c for c in sens.channels if d.channel(c)["native_step"] is not None}  # ENG.AB_LIT: a word
    assert len(streams) == 278 and numeric <= set(streams) and len(numeric) == len(sens.channels) - 1
    acq = build_acquisition_config(d, streams, sensor_channels=sens.channels)
    assert clock_consistency_problems(d, acq) == []
    wfab = acq.domains[int(acq.domain_of[acq.index("ENG.WFAB")])]
    boom = acq.domains[int(acq.domain_of[acq.index("AD.BOOM.PS")])]
    assert wfab.lru == "FTI_DAS" and wfab.clock == acquisition_clock("FTI_DAS", 64.0) and wfab is boom
    for cid in streams:
        dom = acq.domains[int(acq.domain_of[acq.index(cid)])]
        assert float(dom.clock.f_nom_hz) == d.acquisition_rate_hz(cid), cid


def test_clock_consistency_negative_control(d):
    """The check catches the pre-fix wiring: ENG.WFAB on the FADEC crystal at 64 Hz (its acq_lru), and the
    builder refuses a configuration that disagrees with the dictionary."""
    acq = build_acquisition_config(d, ("ENG.WFAB", "ENG.N2.A"), sensor_channels=("ENG.WFAB", "ENG.N2.A"))
    di = int(acq.domain_of[acq.index("ENG.WFAB")])
    bad_dom = replace(acq.domains[di], lru="FADEC", clock=acquisition_clock("FADEC", 64.0))
    bad = replace(acq, domains=tuple(bad_dom if i == di else dm for i, dm in enumerate(acq.domains)))
    problems = clock_consistency_problems(d, bad)
    assert len(problems) == 1 and problems[0].startswith("ENG.WFAB:") and "FTI_DAS" in problems[0]
    wrong_rate = replace(acq.domains[di], clock=acquisition_clock("FTI_DAS", 60.0))
    bad2 = replace(acq, domains=tuple(wrong_rate if i == di else dm for i, dm in enumerate(acq.domains)))
    assert [p.split(":")[0] for p in clock_consistency_problems(d, bad2)] == ["ENG.WFAB"]


def test_controllers_can_share_the_acquisition_clock(d):
    """M08/M05/M15 obtain the ClockDomain M13 samples on (compute instants = acquisition instants)."""

    assert acquisition_clock("FADEC", 60.0) == domain(d, "ENG.N2.A").clock
    assert acquisition_clock("DFCC", 80.0) == domain(d, "FCS.RSA.Q.A").clock
