"""M03 base climatology (IMD 1991-2020) loader and ambient sampler: transcription spot checks against the
research notes, the diurnal-cycle check against the IMD synoptic means, and pure-function properties.
Deterministic (no sample) except where stated."""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.core.rng import KeyPath, RngService, StreamDecl, StreamRegistry, Variate
from phalanx.environment.climatology import Ambient, ambient_at, draw_day, mean_temperature
from phalanx.environment.config import load_env_config

CFG = load_env_config()
CLIM, SP = CFG.climatology, CFG.sampler
MAG = tuple(float(x) for x in CFG.magnus)
COIMBATORE, NALIYA, BIKANER, JAISALMER, JODHPUR = 43321, 42631, 42165, 42328, 42339


@pytest.mark.unit
def test_transcription_matches_research_notes():
    """Values quoted in flight_profiles_and_usage.md Q6 and iaf_usage_and_validation_gap_closure.md Q1."""
    may = 4
    for sid, p12_hpa, db12_c in (
        (JODHPUR, 975.8, 39.8),
        (BIKANER, 974.3, 40.7),
        (NALIYA, 1001.9, 32.6),
        (COIMBATORE, 960.9, 31.3),
    ):
        st = CLIM.station(sid)
        assert st.p12[may] == pytest.approx(p12_hpa * 100, abs=1e-6)
        assert st.t12[may] == pytest.approx(db12_c + 273.15, abs=1e-9)
    assert CLIM.station(JAISALMER).p12[5] == pytest.approx(97040.0)
    assert sum(CLIM.station(COIMBATORE).thunder_days) == pytest.approx(45.6, abs=0.05)
    assert sum(CLIM.station(NALIYA).fog_days) == pytest.approx(14.9, abs=0.05)
    assert sum(CLIM.station(BIKANER).dust_days) == pytest.approx(7.6, abs=0.05)
    assert CLIM.station(COIMBATORE).height_m == pytest.approx(395.3)
    for st in CLIM.stations.values():
        assert np.allclose(st.dir03.sum(axis=1), 1.0) and np.all(st.t_hi_month >= st.t_max)
        assert np.all(st.t_lo_month <= st.t_min) and np.all(st.t_max > st.t_min)


@pytest.mark.unit
def test_diurnal_cycle_matches_imd_synoptic_means():
    """A-W1.1-6 check: the cosine cycle through the mean daily min/max reproduces the IMD 0300/1200 UTC
    dry-bulb means over 5 stations x 12 months (n = 120 comparisons): bias <= 1 K, RMS <= 1.5 K, max 3.5 K.
    The residual is the cosine-form error (the real evening decline is faster) and is reported."""
    err = []
    for st in CLIM.stations.values():
        for m in range(1, 13):
            err.append(mean_temperature(st, m, 3.0, SP) - st.t03[m - 1])
            err.append(mean_temperature(st, m, 12.0, SP) - st.t12[m - 1])
    err = np.array(err)
    assert abs(err.mean()) <= 1.0 and np.sqrt(np.mean(err**2)) <= 1.5 and np.abs(err).max() <= 3.5


def _gen(base, date, root=0x5A):
    reg = StreamRegistry(
        [StreamDecl("scenario", "weather", ("scenario", "base", "date"), Variate.GENERATOR, 1)]
    )
    rng = RngService(root, reg)
    return (
        rng.scope(KeyPath.of(scenario="clim", base=base, date=date))
        .stream("scenario", "weather")
        .generator(0)
    )


@pytest.mark.unit
def test_ambient_is_a_pure_function_of_day_and_time():
    st = CLIM.station(BIKANER)
    d1 = draw_day(st, 5, _gen(BIKANER, "2026-05-14"), SP)
    d2 = draw_day(st, 5, _gen(BIKANER, "2026-05-14"), SP)
    assert d1 == d2
    a = ambient_at(st, d1, 9.5, 0.0, SP, field_elev_m=229.0, magnus=MAG)
    b = ambient_at(st, d2, 9.5, 0.0, SP, field_elev_m=229.0, magnus=MAG)
    assert a == b and Ambient.from_vector(a.vector()) == a
    assert d1 != draw_day(st, 5, _gen(BIKANER, "2026-05-15"), SP)
    # afternoon warmer than early morning on the same day; vapour pressure never above saturation
    early = ambient_at(st, d1, 0.5, 0.0, SP, field_elev_m=229.0, magnus=MAG)
    assert a.t_station_k > early.t_station_k
    for amb in (a, early):
        tc = amb.t_station_k - 273.15
        assert amb.e_station_pa <= MAG[0] * math.exp(MAG[1] * tc / (tc + MAG[2])) + 1e-9
        assert 0.0 <= amb.wind_from_rad < 2 * math.pi and amb.wind_speed_mps >= 0.0


@pytest.mark.unit
def test_ambient_vector_rejects_bad_shape():
    with pytest.raises(ValueError):
        Ambient.from_vector(np.zeros(3))
