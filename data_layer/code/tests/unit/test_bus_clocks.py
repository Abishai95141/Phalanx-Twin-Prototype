"""LRU oscillators (M15 clock domains; architecture §8, AD-37 keyed draws)."""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest

from phalanx.bus.clocks import STREAMS, SortieIdentity, key_value, lru_oscillator
from phalanx.core.rng import RngService, StreamRegistry

ROOT = 0x0123_4567_89AB_CDEF_0011_2233_4455_6677
ID = SortieIdentity("SCN", "KH2001", "KH2001-S1")


def _rng():
    return RngService(ROOT, StreamRegistry(STREAMS))


def test_sub_rate_is_phase_locked_to_the_frame():
    """A producer sub-rate (DFCC FCS40 in its 80 Hz frame, A-W1.7-5) is every 2nd frame tick, exactly."""
    o = lru_oscillator("DFCC", 80, ID, _rng(), sigma_ppm=20)
    frame = o.tick_domain().sample_times_ns(0, 2000)
    sub = o.sub_domain(40, 0).sample_times_ns(0, 1000)
    assert np.array_equal(sub, frame[0::2])
    sub1 = o.sub_domain(40, 1).sample_times_ns(0, 1000)
    assert np.array_equal(sub1, frame[1::2])
    with pytest.raises(ValueError):
        o.sub_domain(30, 0)  # 80/30 is not an integer


def test_offsets_are_unit_properties_and_phases_are_per_sortie():
    rng = _rng()
    a = lru_oscillator("FADEC", 60, ID, rng, sigma_ppm=20)
    b = lru_oscillator("FADEC", 60, SortieIdentity("SCN", "KH2001", "KH2001-S2"), rng, sigma_ppm=20)
    assert a.offset_ppm == b.offset_ppm  # same installed unit -> same crystal offset across sorties
    assert a.phase_ns != b.phase_ns  # power-on phase is fresh per sortie
    c = lru_oscillator(
        "FADEC", 60, SortieIdentity("SCN", "KH2001", "KH2001-S1", {"FADEC": "SN-0042"}), rng, sigma_ppm=20
    )
    assert c.offset_ppm != a.offset_ppm  # a different serial is a different crystal
    assert 0 <= a.phase_ns < Fraction(10**9, 60)


def test_offsets_scale_with_sigma_and_are_deterministic():
    r1, r2 = _rng(), _rng()
    a = lru_oscillator("OAC", 50, ID, r1, sigma_ppm=20)
    b = lru_oscillator("OAC", 50, ID, r2, sigma_ppm=20)
    c = lru_oscillator("OAC", 50, ID, r2, sigma_ppm=40)
    assert a == b
    assert abs(float(c.offset_ppm) - 2 * float(a.offset_ppm)) <= 0.002


def test_offset_distribution_matches_sigma():
    """n = 400 unit serials: sample SD within 15 % of sigma (chi-square 99 % band, n=400: +-9 %)."""
    rng = _rng()
    offs = [
        float(
            lru_oscillator(
                "SMS", 50, SortieIdentity("SCN", "T", "S", {"SMS": f"SN{k}"}), rng, sigma_ppm=20
            ).offset_ppm
        )
        for k in range(400)
    ]
    assert abs(np.std(offs) / 20 - 1) < 0.15
    assert abs(np.mean(offs)) < 3 * 20 / np.sqrt(400)


def test_overrides_and_key_values():
    o = lru_oscillator(
        "ECFM_C",
        40,
        ID,
        _rng(),
        sigma_ppm=20,
        offset_override_ppm={"ECFM_C": 12.5},
        phase_override_ns={"ECFM_C": 1000},
    )
    assert o.offset_ppm == Fraction(25, 2) and o.phase_ns == 1000
    assert key_value("BHEEM_EU") == "BHEEM_EU" and key_value("A/B C") == "A-B-C"
    assert ID.serial_of("BHEEM_EU") == "KH2001:BHEEM_EU"
