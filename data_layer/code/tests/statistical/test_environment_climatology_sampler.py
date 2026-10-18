"""M03 ambient sampler vs the IMD statistics it is built from (A-W1.1-5, A-W1.1-7, A-W1.1-8).

Sample (stated before running): 5 stations x 12 months x 30 days x R = 20 replicate years (36,000 sampled
days), each day keyed by (scenario, base, date) like M02's weather stream.
- Monthly extremes: the mean (over replicates) of the monthly maximum of daily T_max must match the IMD
  "mean monthly highest" within 5 SE + 0.3 K (SE from the replicate spread; 0.3 K for the 2.04 factor's
  approximation of E[max of 28-31 normals]); same for the lowest minimum.
- Phenomenon days: sampled days per month vs IMD days, binomial 5-SE band (n = 600 days per station-month).
- Station pressure and vapour pressure: sample means at 0300/1200 UTC within 5 SE of the IMD means (the
  vapour pressure mean is biased upward by exp(sd^2/2) of the log-normal anomaly, ~1.1 %, and capped at
  saturation; checked to 3 %).
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from phalanx.core.rng import KeyPath, RngService, StreamDecl, StreamRegistry, Variate
from phalanx.environment.climatology import ambient_at, draw_day
from phalanx.environment.config import load_env_config

CFG = load_env_config()
CLIM, SP = CFG.climatology, CFG.sampler
MAG = tuple(float(x) for x in CFG.magnus)
R = 20
REG = StreamRegistry([StreamDecl("scenario", "weather", ("scenario", "base", "date"), Variate.GENERATOR, 1)])
RNG = RngService(0xC11, REG)


def _days(year, month):
    d = dt.date(year, month, 1)
    out = []
    while d.month == month and len(out) < 30:
        out.append(d)
        d += dt.timedelta(days=1)
    return out


@pytest.fixture(scope="module")
def samples():
    res = {}
    for sid, st in CLIM.stations.items():
        for m in range(1, 13):
            tmax_rep, tmin_rep, fog, thunder, p03, p12, e12 = [], [], 0, 0, [], [], []
            for r in range(R):
                tx, tn = [], []
                for d in _days(2001 + r, m):
                    g = (
                        RNG.scope(KeyPath.of(scenario="clim", base=sid, date=d.isoformat()))
                        .stream("scenario", "weather")
                        .generator(0)
                    )
                    day = draw_day(st, m, g, SP)
                    tx.append(
                        ambient_at(
                            st, day, SP.hour_tmax_utc, 0.0, SP, field_elev_m=0.0, magnus=MAG
                        ).t_station_k
                    )
                    tn.append(
                        ambient_at(
                            st, day, SP.hour_tmin_utc, 0.0, SP, field_elev_m=0.0, magnus=MAG
                        ).t_station_k
                    )
                    a3 = ambient_at(st, day, 3.0, 0.0, SP, field_elev_m=0.0, magnus=MAG)
                    a12 = ambient_at(st, day, 12.0, 0.0, SP, field_elev_m=0.0, magnus=MAG)
                    p03.append(a3.p_station_pa)
                    p12.append(a12.p_station_pa)
                    e12.append(a12.e_station_pa)
                    fog += day.fog
                    thunder += day.thunder
                tmax_rep.append(max(tx))
                tmin_rep.append(min(tn))
            res[(sid, m)] = dict(
                tmax=np.array(tmax_rep),
                tmin=np.array(tmin_rep),
                fog=fog,
                thunder=thunder,
                p03=np.array(p03),
                p12=np.array(p12),
                e12=np.array(e12),
            )
    return res


@pytest.mark.statistical
def test_monthly_extremes_reproduced(samples):
    bad = []
    for (sid, m), s in samples.items():
        st = CLIM.station(sid)
        for arr, ref in ((s["tmax"], st.t_hi_month[m - 1]), (s["tmin"], st.t_lo_month[m - 1])):
            se = arr.std(ddof=1) / np.sqrt(arr.size)
            if abs(arr.mean() - ref) > 5 * se + 0.3:
                bad.append((sid, m, arr.mean() - ref, se))
    assert bad == []


@pytest.mark.statistical
def test_phenomenon_day_frequencies(samples):
    bad = []
    for (sid, m), s in samples.items():
        st = CLIM.station(sid)
        n = 30 * R
        for name, k in (("fog", s["fog"]), ("thunder", s["thunder"])):
            p = st.phenomenon_probability(m, name)
            se = np.sqrt(max(p * (1 - p), 1e-4) / n)
            if abs(k / n - p) > 5 * se:
                bad.append((sid, m, name, k / n, p))
    assert bad == []


@pytest.mark.statistical
def test_pressure_and_vapour_means(samples):
    bad = []
    for (sid, m), s in samples.items():
        st = CLIM.station(sid)
        for arr, ref in ((s["p03"], st.p03[m - 1]), (s["p12"], st.p12[m - 1])):
            if abs(arr.mean() - ref) > 5 * arr.std(ddof=1) / np.sqrt(arr.size):
                bad.append((sid, m, "p", arr.mean() - ref))
        if (
            abs(s["e12"].mean() / st.vp12[m - 1] - 1)
            > 0.03 + 5 * s["e12"].std(ddof=1) / np.sqrt(s["e12"].size) / st.vp12[m - 1]
        ):
            bad.append((sid, m, "e", s["e12"].mean() / st.vp12[m - 1]))
    assert bad == []
