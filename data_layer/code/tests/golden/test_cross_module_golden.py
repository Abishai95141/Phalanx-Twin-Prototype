"""Engine objective tests C25, C27 and C28 (acceptance A8; f404_in20_engine_model.md Q12 (c) target table),
which need modules other than M07: W2.1c turns the former skip of ``test_engine_golden.py`` into real tests.

- **C25 oil debris** [TRANSFER: -400; Bennett et al. 1996 QFDA element wear rates, CF188 Fe mean 0.47 ug/h,
  2 sigma 1.68 ug/h (26 filters); JOAP SOAP Fe slopes 0.02-0.07 ppm/h normal, 1-11 ppm/h abnormal, N:TFG (c)
  #25] on M10's healthy-wear debris process (W2.5, A-W2.5-1), wear and spall laws and M11's triggered bearing
  failure.
- **C27 cold-start capability** [DIRECT: CAG 17/2015, HAL/DRDO Feb 2015: three consecutive starts at -15 degC,
  85 % battery after an 18-42 h soak] on M09's JFS with the fleet's M10 build health (the engine spool is the
  M09 start fixture: M07's sub-idle start is a structural PROXY, AD-46 / A-W1.3a-3, golden C20/C21 xfail).
- **C28 data-chain texture** [TRANSFER: -400 IECMS, Henry AGARD-CP-448 Tbl 1: resolution N 16 rpm, T 1 K,
  PS3 0.5 psia, P5 0.06 psia; aircraft 2 sigma XN1 154 rpm, XN2 138 rpm, PS3 1.2 psia, P5 0.14 psia, T5
  2.0 K, T1 1.3 K; engine-sensor 2 sigma in the test cell XN1 9.6 rpm, XN2 7.2 rpm, PS3 0.7 psia, P5 0.09
  psia, T5 0.6 K, T1 0.1 K] on M12 + the recording M13 at steady truth. A FADEC chain may quantise finer than
  the -400 IECMS (the note says so), so resolution and the aircraft 2 sigma are ceilings.

Tolerances: architecture section 14.2 (exact DIRECT, bands as published); never tighter than the source.
Samples (stated before running): C25 one engine, 20 healthy 1-h sorties then a scripted incipient spall
flown to failure (about 30 sorties); the healthy debris rate on a fleet of 1,000 engine serials over 100 EOT h
each (Bennett's statistics are across engines, one filter per engine; 1,000 makes the simulation's own
sampling error small against Bennett's 95 % CIs, which are the tolerance: n = 26 real filters); C27 one start
protocol per variant (3 starts); C28 one 20 s steady
recording (1,200 recorded samples per channel).
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.health import HealthConfig, HealthModule, SortieUsage, load_health_params, sensor_bias_channels
from phalanx.health.module import ENG_F, ENG_I

pytestmark = pytest.mark.golden
TESTS = Path(__file__).resolve().parents[1]
D = load_dictionary()
P10 = load_health_params()
SEC = 10**9
DAY = 86_400 * SEC
EOT_S = 3600.0  # engine operating time per sortie (1 h)


def _by_path(name: str, rel: str):
    """Load a TEST FIXTURE module by path (they are shared across test tiers this way)."""
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, TESTS / rel)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


class Sink(ModuleBase):  # TEST FIXTURE: records what a neighbouring module receives (module boundary)
    version, rate = "0", None

    def __init__(self, mid: str) -> None:
        super().__init__(mid, ParamSet("sink", {}))
        self.got: list[tuple[int, Event]] = []

    def init(self, params, keys):
        return {}

    def on_event(self, state, event, t):
        self.got.append((t, event))
        return state, []


# ------------------------------------------------------------------------------------------------ C25
def _usage(k: int) -> SortieUsage:
    return SortieUsage(
        sortie_id=f"KH2011-{k}",
        flight_time_s=EOT_S,
        eot_s=(EOT_S,),
        tamp_s=(300.0,),
        type1=(1.0,),
        type3=(3.0,),
        type4=(3.0,),
        eftc=(1.1,),
        src_h=(0.05,),
        ps3_full=(1.0,),
        ps3_partial=(3.0,),
        ab_lights=(2.0,),
        starts=(1.0,),
        landings=1.0,
    )


def _engine_world():
    """Real M10 -> real M11 (usage mode, scripted onsets only) -> sinks for M07 / M14 / M18."""
    sinks = {k: Sink(k) for k in ("engine", "monitoring", "maintenance")}
    m10 = HealthModule(
        "health", P10, config=HealthConfig(("IN20-0001",), sensor_bias_channels(D), fault_target="faults")
    )
    cfg = FaultConfig(
        load_catalogue(),
        load_graph(),
        {"health": "health", **{k: k for k in sinks}},
        ("IN20-0001",),
        sensor_bias_channels(D),
        realise_physics_edges=True,
        stochastic=False,
    )
    m11 = FaultInjector("faults", load_fault_params(), config=cfg)
    sysm = System(
        [m10, m11, *sinks.values()],
        [],
        rng=RngService(0xC25, StreamRegistry()),
        identity=KeyPath.of(scenario="C25", tail="KH2011"),
    )
    return sysm, sinks


def _fly(sysm, w, k0: int, n: int, extra=()):
    evs = [
        Event((k0 + j + 1) * DAY, "health.sortie", "health", _usage(k0 + j).to_payload()) for j in range(n)
    ]
    w = sysm.inject(w, [*extra, *evs])
    w, _ = sysm.run(w, ((k0 + n) * DAY) // (SEC // 240) + 2 - w.k)
    return w


def _eng(w, name: str) -> float:
    return float(w.states["health"]["eng_f"][0][ENG_F.index[name]])


@pytest.fixture(scope="module")
def healthy():
    sysm, sinks = _engine_world()
    w0 = sysm.start()
    w = _fly(sysm, w0, 0, 20)
    return sysm, sinks, w0, w


N_FLEET, FLEET_SORTIES, FLEET_EOT_H = 1000, 10, 10.0  # 100 EOT h per engine (the CF 100 h filter interval)
BENNETT_N, BENNETT_MEAN, BENNETT_2SIGMA = 26, 0.4747, 1.6813  # CF188 Fe, ug/h (Tbl I)


def bennett_cis() -> tuple[tuple[float, float], tuple[float, float]]:
    """95 % CIs of Bennett's own statistics (n = 26 filters): the mean (t) and 2 sigma (chi-square): the
    real-vs-real tolerance of C25 (architecture §14.2: never tighter than the source's own scatter)."""
    from scipy import stats

    s = BENNETT_2SIGMA / 2.0
    half = stats.t.ppf(0.975, BENNETT_N - 1) * s / np.sqrt(BENNETT_N)
    lo2 = BENNETT_2SIGMA * np.sqrt((BENNETT_N - 1) / stats.chi2.ppf(0.975, BENNETT_N - 1))
    hi2 = BENNETT_2SIGMA * np.sqrt((BENNETT_N - 1) / stats.chi2.ppf(0.025, BENNETT_N - 1))
    return (BENNETT_MEAN - half, BENNETT_MEAN + half), (float(lo2), float(hi2))


def test_c25_healthy_oil_debris_wear_rate():
    """Healthy QFDA Fe wear across a fleet (W2.5, A-W2.5-1): the per-engine filter-debris rate over 100 EOT h
    of 1,000 serials (engines whose bearing spall initiated are excluded, as Bennett's normal-wear statistics
    exclude faulty engines) has its mean inside Bennett's 95 % CI of the CF188 mean [0.135, 0.814] ug/h and
    its 2 sigma inside the CI of his 2 sigma [1.32, 2.32] ug/h. Measured (W2.5, root 0xC25F): 999 healthy
    engines, mean 0.485 ug/h, 2 sigma 1.78 ug/h (the 100 h within-engine scatter adds to the between-engine
    spread, as it does in filter data)."""
    ser = tuple(f"IN20-{k:04d}" for k in range(N_FLEET))
    m10 = HealthModule("health", P10, config=HealthConfig(ser, sensor_bias_channels(D)))
    sysm = System(
        [m10],
        [],
        rng=RngService(0xC25F, StreamRegistry()),
        identity=KeyPath.of(scenario="C25F", tail="KH2011"),
    )
    w0 = sysm.start()

    def usage(k: int) -> SortieUsage:
        def one(v: float) -> tuple[float, ...]:
            return (v,) * N_FLEET

        return SortieUsage(
            sortie_id=f"KH2011-F{k}",
            flight_time_s=FLEET_EOT_H * 3600.0,
            eot_s=one(FLEET_EOT_H * 3600.0),
            tamp_s=one(300.0),
            type1=one(1.0),
            type3=one(3.0),
            type4=one(3.0),
            eftc=one(1.1),
            src_h=one(0.05),
            ps3_full=one(1.0),
            ps3_partial=one(3.0),
            ab_lights=one(2.0),
            starts=one(1.0),
            landings=1.0,
        )

    evs = [
        Event((k + 1) * DAY, "health.sortie", "health", usage(k).to_payload()) for k in range(FLEET_SORTIES)
    ]
    w = sysm.inject(w0, evs)
    w, _ = sysm.run(w, (FLEET_SORTIES * DAY) // (SEC // 240) + 2 - w.k)
    f, i = w.states["health"]["eng_f"], w.states["health"]["eng_i"]
    healthy = i[:, ENG_I.index["spall_on"]] == 0
    rates = f[healthy, ENG_F.index["debris"]] - w0.states["health"]["eng_f"][healthy, ENG_F.index["debris"]]
    rates = rates * 1e9 / (FLEET_SORTIES * FLEET_EOT_H)  # kg -> ug per EOT hour
    (m_lo, m_hi), (s_lo, s_hi) = bennett_cis()
    assert healthy.sum() >= 0.99 * N_FLEET, int(healthy.sum())
    assert np.all(rates > 0.0)
    assert m_lo <= rates.mean() <= m_hi, rates.mean()
    assert s_lo <= 2.0 * rates.std(ddof=1) <= s_hi, 2.0 * rates.std(ddof=1)


def test_c25_normal_soap_fe_slope(healthy):
    """A healthy engine's oil Fe rises at the JOAP normal SOAP slope (0.02-0.07 ppm/h) and sheds no debris
    (no spall initiated in 20 h with the shipped Weibull life)."""
    _, _, w0, w = healthy
    slope_ppm_h = (_eng(w, "oil_fe") - _eng(w0, "oil_fe")) * 1e6 / 20.0
    assert 0.02 <= slope_ppm_h <= 0.07
    assert _eng(w, "spall_len") == 0.0


def test_c25_spalling_bearing_signature_and_m11_failure():
    """An incipient spall (M10's initiation size) grows with the shipped law: while it spalls past 2 mm the
    SOAP Fe slope sits in the JOAP abnormal band (1-11 ppm/h) and the debris rate is three orders of
    magnitude above the healthy QFDA 2 sigma; at the critical length M10 triggers M11's bearing failure,
    which reaches M07 (eng.fault_inject) and M18 (truth.fault) once."""
    sysm, sinks = _engine_world()
    w = sysm.start()
    l0 = float(P10.value("bearing_l0"))
    seed = Event(DAY // 2, "health.fault", "health", {"state": "eng:spall_len", "delta": l0, "op": "set"})
    k, slopes, dbr = 0, [], []
    while _eng(w, "spall_len") < float(P10.value("spall_critical")) and k < 60:
        fe0, d0, l_before = _eng(w, "oil_fe"), _eng(w, "debris"), _eng(w, "spall_len")
        w = _fly(sysm, w, k, 1, extra=(seed,) if k == 0 else ())
        k += 1
        if l_before >= 2.0e-3:
            slopes.append((_eng(w, "oil_fe") - fe0) * 1e6)  # ppm per 1-h sortie
            dbr.append((_eng(w, "debris") - d0) * 1e9)  # ug per hour
    assert k < 60 and slopes, (k, len(slopes))
    assert all(1.0 <= s <= 11.0 for s in slopes), slopes
    assert min(dbr) > 1000.0 * 1.68
    w = _fly(sysm, w, k, 1)  # the trigger and the onset settle
    modes = [
        str(np.asarray(e.payload["mode"])) for _, e in sinks["engine"].got if e.kind == "eng.fault_inject"
    ]
    assert modes.count("bearing_failure") == 1, modes
    truth = [e for _, e in sinks["maintenance"].got if e.kind == "truth.fault"]
    assert len(truth) == 1


# ------------------------------------------------------------------------------------------------ C27
def test_c27_cold_start_capability_with_the_fleet_build_health():
    """CAG 17/2015 / HAL-DRDO 2015 [DIRECT]: the modified (M2) GTSU-110 makes three consecutive starts at Leh
    at -15 degC on an 85 % battery after an overnight cold soak; the M1 could not. M09 runs with the
    health.utility of a fresh M10 fleet build (the JFS and battery states every tail starts with)."""
    us = _by_path("w21c_utilities_support", "unit/test_utilities_support.py")
    from phalanx.utilities.jfs import OUT_OK

    m10 = HealthModule("health", P10, config=HealthConfig(("IN20-0001",), sensor_bias_channels(D)))
    sysm = System([m10], [], rng=RngService(0xC27, StreamRegistry()), identity=KeyPath.of(scenario="C27"))
    h = m10.utility_vector(sysm.start().states["health"])
    leh = 3260.0  # m, ADA rig trials (N KQ1)
    m2 = us.start_protocol(variant=2, t_amb=258.15, alt=leh, soc=0.85, health=h)
    assert m2.outcomes == [OUT_OK] * 3 and m2.consecutive == 3
    m1 = us.start_protocol(variant=1, t_amb=257.15, alt=leh, soc=0.85, health=h)
    assert m1.consecutive < 3


# ------------------------------------------------------------------------------------------------ C28
N1_100, N2_100 = 13270.0, 16810.0  # rpm at 100 % (dictionary channel references)
#: channel -> (EU per Henry unit, IECMS resolution, aircraft 2 sigma, engine-sensor test-cell 2 sigma)
HENRY = {
    "ENG.N1.A": (100.0 / N1_100, 16.0, 154.0, 9.6),
    "ENG.N2.A": (100.0 / N2_100, 16.0, 138.0, 7.2),
    "ENG.T1.A": (1.0, 1.0, 1.3, 0.1),
    "ENG.T5.HARNESS_A": (1.0, 1.0, 2.0, 0.6),
    "ENG.PS3.A": (1.0, 0.5, 1.2, 0.7),
    "ENG.P5": (1.0, 0.06, 0.14, 0.09),
}


@pytest.fixture(scope="module")
def steady_recording():
    fx = _by_path("w16_acquisition_fixtures", "integration/test_acquisition_fixtures.py")
    from phalanx.acquisition import kernel as K
    from phalanx.acquisition.config import build_acquisition_config
    from phalanx.acquisition.record import AcquisitionRecorder, frames_from_trace
    from phalanx.sensors.config import build_sensor_config

    sens = build_sensor_config(D)
    acq = build_acquisition_config(D, sens.channels, sensor_channels=sens.channels)
    ident = KeyPath.of(scenario="C28", tail="KH2001", sortie="SRT0001")
    script = {"eng.n1": 1300.0, "eng.n2": 1700.0, "eng.t5": 900.0}  # steady truth (rad/s, K)
    system, rng, mods = fx.build_chain(D, sens, controllers=(), identity=ident, script=script)
    _, tr = system.run(system.start(), 4800, record=[*fx.sensor_ports(mods), "truth.phase"])
    s, x = frames_from_trace(sens, tr.ports, "sens")
    rec = AcquisitionRecorder(acq, rng.scope(ident))
    _, recs = rec.process(rec.init_state(), 0, s, x, tr.ports["truth.phase"])
    out = {}
    for c, cid in enumerate(acq.channels):
        if cid in HENRY:
            v = recs[cid].cat("value", np.float64)
            out[cid] = (v, float(acq.P[c, K.AP_SF]))
    assert set(out) == set(HENRY)
    return out


def test_c28_resolution_and_aircraft_precision_ceilings(steady_recording):
    """Recorded resolution no coarser than the -400 IECMS and the 2 sigma scatter at steady truth no wider
    than the IECMS aircraft chain's (both in Henry units)."""
    for cid, (v, lsb) in steady_recording.items():
        to_eu, res, ac2s, _ = HENRY[cid]
        assert lsb <= res * to_eu * (1 + 1e-9), (cid, lsb / to_eu)
        assert 2.0 * float(np.std(v)) <= ac2s * to_eu, (cid, 2.0 * float(np.std(v)) / to_eu)
        assert v.size >= 100 and math.isfinite(float(np.mean(v)))


@pytest.mark.xfail(
    strict=True,
    reason="C28 precision floor (Henry Tbl 1 engine-sensor 2 sigma in the test cell, TRANSFER -400): at "
    "steady truth the recorded 2 sigma is below the sensor-alone precision on N1 (5.4 vs 9.6 rpm), N2 "
    "(3.0-3.7 vs 7.2 rpm), PS3 (0.05-0.08 vs 0.7 psia), P5 (0.058 vs 0.09 psia) and T5 (0.0 vs 0.6 K: every "
    "sample quantises to one count); measured n = 1,200 samples per channel. Caveat: Henry's figures are "
    "snapshot repeatability, a wider measure than sample noise at fixed truth; W2.2 / W2.3 decide (texture "
    "calibration, AD-31/32)",
)
def test_c28_recorded_precision_not_below_the_engine_sensors(steady_recording):
    for cid, (v, _) in steady_recording.items():
        to_eu, _, _, sens2s = HENRY[cid]
        assert 2.0 * float(np.std(v)) >= sens2s * to_eu, (cid, 2.0 * float(np.std(v)) / to_eu)
