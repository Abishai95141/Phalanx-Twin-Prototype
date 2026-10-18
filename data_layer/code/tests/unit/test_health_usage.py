"""LUI / TAC / Nz counting on synthetic cycles (acceptance A2 "life-counter accrual matches the LUI/TAC
definitions"; A5 "LUI counting on synthetic cycles"), compiled kernel == reference, chunk invariance, and the
noise dead-band lesson (CF-18: noise inflated partial N2 counts 8x; dead-band ≥ 2x noise suppresses it).

Synthetic flights are piecewise-linear N2 histories at 10 Hz with known numbers of each cycle type (n = 1
flight
per test; the definitions are deterministic, so one flight per pattern answers the question)."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.health.usage import (
    LuiGates,
    SortieUsage,
    lui_finalize,
    lui_init,
    lui_kernel,
    lui_kernel_reference,
    lui_readout,
    nz_counter_kernel,
    tac,
    usage_from_truth,
)

GATES = LuiGates(
    n2_run=45.0,
    n2_off=20.0,
    n2_idle=55.0,
    n2_low=75.0,
    n2_cruise=88.0,
    n2_irp=95.0,
    pla_irp=87.0,
    ps3_max=425.0,
    t5_ref=830.0,
    t5_doubling=15.0,
    t5_full_swing=800.0,
    eftc_exponent=3.0,
    t5_deadband=10.0,
    dt_max_s=2.0,
    dt_gap_s=1.0,
)


def flight(points, rate=10.0):
    """(t_ns, n2, ps3, t5, pla) for a piecewise-linear N2 profile [(t_s, n2_pct), ...]."""
    xs = np.array([p[0] for p in points], float)
    ys = np.array([p[1] for p in points], float)
    t = np.arange(0.0, xs[-1], 1.0 / rate)
    n2 = np.interp(t, xs, ys)
    ps3 = n2 / 100.0 * 390.0
    t5 = 15.0 + n2 / 100.0 * 780.0
    pla = np.where(n2 >= 96.0, 100.0, 40.0)
    return (t * 1e9).astype(np.int64), n2, ps3, t5, pla


def count(fl, gates=GATES, finalize=True):
    t, n2, ps3, t5, pla = fl
    f, i, s = lui_init()
    f, i, s = lui_kernel(f, i, s, gates.vector(), t, n2, ps3, t5, pla, np.ones(t.size, bool))
    if finalize:
        f, i, s = lui_finalize(f, i, s, gates.vector())
    return lui_readout(f), i


# idle 63 % -> IRP 98 % -> idle 70 % -> IRP -> cruise 85 % -> IRP -> idle -> off
PROFILE = [
    (0, 0),
    (60, 63),
    (120, 98),
    (300, 98),
    (360, 70),
    (400, 70),
    (460, 98),
    (600, 98),
    (660, 85),
    (900, 85),
    (960, 98),
    (1200, 98),
    (1300, 63),
    (1400, 63),
    (1460, 0),
    (1500, 0),
]


@pytest.mark.unit
def test_lui_counts_on_synthetic_cycles():
    """One run: Type I = 1 (first off -> IRP -> idle), Type III = 1 (idle -> IRP -> idle), Type IV = 1
    (cruise -> IRP), one partial PS3 cycle (peak 90 % of PS3_max); EOT = time N2 ≥ 55 %; TAMP = time PLA ≥
    87°."""
    r, i = count(flight(PROFILE))
    assert (r["type1"], r["type3"], r["type4"]) == (1.0, 1.0, 1.0)
    assert (r["ps3_full"], r["ps3_partial"]) == (0.0, 1.0)
    # N2 crosses 55 % at 52.38 s rising and at 1407.62 s falling (exact on the 0.1 s grid ± 0.1 s)
    assert r["eot_s"] == pytest.approx(1407.62 - 52.38, abs=0.2)
    _t, n2, *_ = flight(PROFILE)
    assert r["tamp_s"] == pytest.approx(0.1 * np.count_nonzero(n2 >= 96.0), abs=0.2)
    assert tac(r["type1"], r["type3"], r["type4"]) == pytest.approx(1 + 1 / 4 + 1 / 40)
    assert i[10] == 0  # no data gap


@pytest.mark.unit
def test_type_counts_scale_with_excursions():
    """k idle -> IRP -> idle excursions in one run: Type I = 1, Type III = k - 1; two runs: Type I = 2."""
    pts = [(0, 0), (60, 63)]
    t0 = 60
    for _ in range(5):
        pts += [(t0 + 60, 98), (t0 + 120, 98), (t0 + 180, 65)]
        t0 += 180
    pts += [(t0 + 60, 0), (t0 + 100, 0)]
    r, _ = count(flight(pts))
    assert (r["type1"], r["type3"]) == (1.0, 4.0)
    two = [*pts, (t0 + 160, 63), (t0 + 220, 98), (t0 + 280, 65), (t0 + 340, 0), (t0 + 360, 0)]
    r2, _ = count(flight(two))
    assert (r2["type1"], r2["type3"]) == (2.0, 4.0)


@pytest.mark.unit
def test_full_ps3_cycle_and_src_reference():
    """A PS3 peak ≥ 95 % of PS3_max closed below 50 % is a full PS3 cycle; one hour at the T5 reference
    accrues one stress-rupture hour (SRC), doubling for every t5_doubling K above it."""
    t = (np.arange(0, 3600, 0.5) * 1e9).astype(np.int64)
    n = t.size
    ps3 = np.concatenate([np.linspace(100, 410, n // 2), np.linspace(410, 100, n - n // 2)])
    f, i, s = lui_init()
    for t5, expect in ((830.0, 1.0), (845.0, 2.0)):
        f, i, s = lui_init()
        f, i, s = lui_kernel(
            f,
            i,
            s,
            GATES.vector(),
            t,
            np.full(n, 90.0),
            ps3,
            np.full(n, t5),
            np.full(n, 40.0),
            np.ones(n, bool),
        )
        r = lui_readout(f)
        assert r["src_h"] == pytest.approx(expect, rel=1e-3)
        assert (r["ps3_full"], r["ps3_partial"]) == (1.0, 0.0)


@pytest.mark.unit
def test_eftc_counts_full_thermal_cycle_once():
    """Cold start -> T5 swing of the full reference -> cold is one equivalent full thermal cycle (rainflow
    residue counted at the end of flight); small dead-band wiggles do not count."""
    t = (np.arange(0, 2000, 0.1) * 1e9).astype(np.int64)
    t5 = np.interp(np.arange(0, 2000, 0.1), [0, 100, 1900, 2000], [15.0, 815.0, 815.0, 15.0])
    t5 = t5 + 3.0 * np.sin(np.arange(t.size) * 0.7)  # below the 10 K dead-band
    n = t.size
    f, i, s = lui_init()
    f, i, s = lui_kernel(
        f,
        i,
        s,
        GATES.vector(),
        t,
        np.full(n, 90.0),
        np.full(n, 200.0),
        t5,
        np.full(n, 40.0),
        np.ones(n, bool),
    )
    f, i, s = lui_finalize(f, i, s, GATES.vector())
    assert lui_readout(f)["eftc"] == pytest.approx(1.0, abs=0.06)


@pytest.mark.unit
def test_compiled_kernel_equals_reference_bitwise_and_chunks():
    """AD-22: compiled == py_func reference bitwise; one block == the same flight in 7 chunks."""
    t, n2, ps3, t5, pla = flight(PROFILE)
    v = np.ones(t.size, bool)
    g = GATES.vector()
    a = lui_kernel(*lui_init(), g, t, n2, ps3, t5, pla, v)
    b = lui_kernel_reference(*lui_init(), g, t, n2, ps3, t5, pla, v)
    for x, y in zip(a, b, strict=True):
        assert np.array_equal(x, y)
    st = lui_init()
    for idx in np.array_split(np.arange(t.size), 7):
        st = lui_kernel(*st, g, t[idx], n2[idx], ps3[idx], t5[idx], pla[idx], v[idx])
    for x, y in zip(st, a, strict=True):
        assert np.array_equal(x, y)


@pytest.mark.unit
def test_deadband_suppresses_noise_inflation():
    """CF-18 lesson (Muir et al., AGARD-CP-448 p. 7-3): N2 noise inflated partial counts 8x on one engine.
    With gates 20 points apart, noise of σ = 0.3 % N2 adds no counts; gates squeezed to a 0.2 % band
    (narrower than 2x the noise) inflate Type III counts."""
    g = np.random.Generator(np.random.Philox(np.random.SeedSequence(7, spawn_key=(1,))))
    t, n2, ps3, t5, pla = flight([(0, 0), (60, 63), (120, 92), (3000, 92), (3060, 63), (3120, 0), (3150, 0)])
    noisy = n2 + 0.3 * g.standard_normal(n2.size)
    r_clean, _ = count((t, n2, ps3, t5, pla))
    r_noisy, _ = count((t, noisy, ps3, t5, pla))
    assert (r_noisy["type1"], r_noisy["type3"]) == (r_clean["type1"], r_clean["type3"]) == (0.0, 0.0)
    tight = LuiGates(**{**GATES.__dict__, "n2_low": 91.8, "n2_cruise": 91.9, "n2_irp": 92.0})
    r_tight_clean, _ = count((t, n2, ps3, t5, pla), tight)
    r_tight_noisy, _ = count((t, noisy, ps3, t5, pla), tight)
    assert r_tight_noisy["type3"] >= 8 * max(1.0, r_tight_clean["type3"])


@pytest.mark.unit
def test_invalid_samples_and_gaps_set_the_data_gap_flag():
    t, n2, ps3, t5, pla = flight(PROFILE)
    valid = np.ones(t.size, bool)
    valid[100] = False
    f, i, s = lui_init()
    _, i, _ = lui_kernel(f, i, s, GATES.vector(), t, n2, ps3, t5, pla, valid)
    assert i[10] == 1
    f, i, s = lui_init()
    keep = np.r_[0:500, 520 : t.size]  # a 2 s hole
    _, i, _ = lui_kernel(
        f, i, s, GATES.vector(), t[keep], n2[keep], ps3[keep], t5[keep], pla[keep], valid[keep] | True
    )
    assert i[10] == 1


@pytest.mark.unit
def test_nz_level_crossings():
    """Level crossings count once per excursion and re-arm through 1 g; negative levels count downward."""
    levels = np.array([-1.0, 0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    nz = np.array([1.0, 2.5, 3.2, 1.5, 3.1, 0.9, 4.2, 0.5, -1.2, 1.0, 7.5, 1.0])
    c, _armed = nz_counter_kernel(np.zeros(8), np.ones(8, np.int64), levels, 1.0, nz)
    # 2 g: 2.5, (3.1 not re-armed since 1.5 > 1), 4.2, 7.5 -> 3; 3 g: 3.2, 4.2, 7.5 -> 3
    assert list(c) == [1.0, 1.0, 3.0, 3.0, 2.0, 1.0, 1.0, 1.0]
    c2, _ = nz_counter_kernel(np.zeros(8), np.ones(8, np.int64), levels, 1.0, nz[:6])
    c3, _ = nz_counter_kernel(c2, _, levels, 1.0, nz[6:])
    assert np.array_equal(c3, c)


@pytest.mark.unit
def test_usage_from_truth_and_payload_round_trip():
    t, n2, ps3, t5, pla = flight(PROFILE)
    u = usage_from_truth("S-1", t, n2, ps3, t5, pla, GATES, nz=np.array([1.0, 3.5, 1.0]), dust=2.0)
    assert u.type1 == (1.0,) and u.type3 == (1.0,) and u.dust == 2.0
    assert u.nz_counts[3] == 1.0
    back = SortieUsage.from_payload(u.to_payload())
    assert back == u
    with pytest.raises(ValueError):
        SortieUsage(
            sortie_id="x",
            flight_time_s=1.0,
            eot_s=(1.0,),
            tamp_s=(1.0, 2.0),
            type1=(0.0,),
            type3=(0.0,),
            type4=(0.0,),
            eftc=(0.0,),
            src_h=(0.0,),
            ps3_full=(0.0,),
            ps3_partial=(0.0,),
            ab_lights=(0.0,),
            starts=(0.0,),
        )
