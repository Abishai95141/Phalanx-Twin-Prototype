"""M07 engineering objective tests C1-C28 (acceptance A8; report §10, f404_in20_engine_model.md Q12 (c)).

Tolerances (architecture §14.2): +-3 % steady state, +-25 % transient timing, exact DIRECT ratings, correct
fault-signature signs; never tighter than real repeatability. Targets are [TRANSFER: F404-400/-402/-102/RM12]
shapes scaled to the IN20 unless DIRECT. No tuning at test points: every parameter comes from M07.yaml.

Status per target (the report lists them):
- PASS now: C1 (design closure and kernel max-AB steady state), C8, C14, C15, C19 (test_engine_transients),
  C24, C26 signs (test_engine_signs), C16 slam time with the fixture accel schedule (test_engine_transients),
  MIL N2 anchor (95 %, AD-46);
- calibration-pending (W2.3), ``xfail(strict=True)`` with the measured value in the reason: C2, C3, C4, C5,
  C6, C10, C17, C18 (test_engine_transients), C22, C26 magnitudes, -400 method check, the released
  idle/MIL test-cell anchors (idle N1/FF/T5/thrust, MIL FF);
- test-design defect, ``xfail(strict=True)`` with the measured value, resolved by a W2.1 rewrite: C11 (a
  steady point compared with a transient snapshot);
- structural PROXY limits (AD-46), ``xfail(strict=True)``, replaced by a model change, not by calibration:
  C20/C21 (sub-idle start: A-W1.3a-3), C23 (surge post-stall: A-W1.3a-9);
- not testable at M07 module level (skip; W2.1 turns them into real tests): C7, C9, C13 (need M06 in the
  loop); C12 runs with M08 in the loop (``tests/golden/test_engine_fadec_golden.py``, W2.1b); C25 (M10/M11
  wear), C27 (M09 JFS) and C28 (M13 texture) are real tests in ``tests/golden/test_cross_module_golden.py``
  (W2.1c).

Percent speeds are of the 100 % references (13,270 / 16,810 rpm); the design MIL point runs at 95.2 % N2.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.engine.design import build_engine_model, load_engine_params
from phalanx.engine.layout import AB_LIT, I_NSURGE, U_A8, U_BLEED, U_H0, U_TS, U_VG2, U_WF, U_WFAB, Y_NAMES, A
from phalanx.engine.maps import interp1
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state

LBF = 4.448222
PSI = 6894.757


def _fixtures():
    path = Path(__file__).resolve().parents[1] / "integration" / "test_engine_fixtures.py"
    spec = importlib.util.spec_from_file_location("engine_fixtures_g", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["engine_fixtures_g"] = mod
    spec.loader.exec_module(mod)
    return mod


fx = _fixtures()


@pytest.fixture(scope="module")
def m():
    return fx.fixture_model()


@pytest.fixture(scope="module")
def sch(m):
    return fx.FixtureSchedules(m)


def _frac(m, n2_pct: float) -> float:
    """Fixture N2-demand fraction (of the design MIL N2) for a percent of the 100 % N2 reference."""
    st = m.design.stations
    return n2_pct / 100.0 * st["n2_100"] / st["n2"]


def _on_line(m, sch, f, **over):
    u = design_inputs(m)
    u[U_A8] = sch.a8(f)
    for k, v in over.items():
        u[k] = v
    r = steady_state(m, u, x0=sch.x_at(f), target=("n2", f * sch.n2_des))
    assert r.converged
    return r


# ----------------------------------------------------------------------------------------------- C1, C2


@pytest.mark.golden
def test_c1_in20_ratings(m):
    """C1 [DIRECT, GE data sheet]: 84 kN max AB, 70 kg/s, OPR 28 at SLS ISA, exactly."""
    st = m.design.stations
    assert abs(m.design.max_ab["fn"] - 84_000.0) < 0.084
    assert st["w2"] == 70.0 and abs(st["p3"] / st["p2"] - 28.0) < 1e-12


@pytest.mark.golden
def test_c1_kernel_reproduces_ratings(m):
    """C1, non-tautological: the dynamic kernel's own steady states (not the design calculation) at the design
    dry and max-AB inputs give 70 kg/s, OPR 28 and 84 kN to 1e-5 (NEWTON_T 2 consistency level)."""
    d = m.design
    dry = steady_state(m, design_inputs(m))
    assert dry.converged
    assert abs(dry.aux[A["w2"]] / 70.0 - 1.0) < 1e-5
    assert abs(dry.x[3] / dry.aux[A["p2"]] / 28.0 - 1.0) < 1e-5
    u = design_inputs(m)
    u[U_WFAB], u[U_A8] = d.max_ab["wf_ab"], d.max_ab["a8"]
    ab = steady_state(m, u, x0=dry.x, ab_state=AB_LIT)
    assert ab.converged
    assert abs(ab.aux[A["fn"]] / 84_000.0 - 1.0) < 1e-5, ab.aux[A["fn"]]


# ----------------------------------------------------------------------------------------- idle/MIL anchors
LBH = 3600.0 / 0.45359237  # (kg/s) -> lb/h


@pytest.fixture(scope="module")
def idle_point(m, sch):
    """SLS ISA steady state at the released ground-idle N2 (65.2 % of 16,810 rpm) on the fixture A8 schedule
    (1.8 x MIL A8 at idle, -400 shape)."""
    return _on_line(m, sch, _frac(m, 65.2))


@pytest.mark.golden
def test_mil_n2_anchor(m):
    """AD-46 anchor [TRANSFER: F404-400/F1D2 USAF IERA test cell, MIL N2 15,994 rpm = 95.2 %]: the design MIL
    point runs at 94-97 % N2 (IN20 inference band, iaf_usage_and_validation_gap_closure.md Q3)."""
    st = m.design.stations
    assert 0.94 <= st["n2"] / st["n2_100"] <= 0.97


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 part-power matching (map modifiers): at the released idle N2 (65.2 %) the model has N1 "
    "35.9 % (38.9), Wf 457 lb/h (650-750), T5 556 K (682) and thrust 0.97 kN (2.8)",
)
def test_idle_anchors(m, idle_point):
    """Released ground-idle anchors [TRANSFER: F404-400/F1D2 USAF IERA test cell Tbl 4-71 and CR-191195; IN20
    fuel band by inference, report ground-operations table]: at 65.2 % N2: N1 38.9 % (+-10 %), Wf 650-750
    lb/h, T5 682 K (+-5 %), thrust 2.8 kN (+-25 %)."""
    st = m.design.stations
    r = idle_point
    n1_pct = r.x[0] / st["n1_100"] * 100.0
    got = {"n1_pct": n1_pct, "wf_lbh": r.u[U_WF] * LBH, "t5": r.aux[A["t5"]], "fn_kn": r.aux[A["fn"]] / 1e3}
    assert abs(got["n1_pct"] / 38.9 - 1.0) <= 0.10, got
    assert 650.0 <= got["wf_lbh"] <= 750.0, got
    assert abs(got["t5"] / 682.0 - 1.0) <= 0.05, got
    assert abs(got["fn_kn"] / 2.8 - 1.0) <= 0.25, got


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 (cycle losses and SFC, with C2): the design MIL fuel flow is 10,570 lb/h vs the IN20 band "
    "8,300-8,600 lb/h scaled from the -400 test cell (7,739 lb/h)",
)
def test_mil_fuel_flow_anchor(m):
    """Released MIL anchor [TRANSFER: F404-400 USAF IERA test cell 7,739 lb/h, scaled to the IN20 SLS
    8,300-8,600 lb/h, iaf_usage_and_validation_gap_closure.md Q3 inferences]."""
    wf = m.design.stations["wf"] * LBH
    assert 8300.0 <= wf <= 8600.0, wf


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 calibration: dry SLS thrust 58.7 kN vs 54 kN +-3 % (AGG + closure "
    "54-57 kN); fan-to-nozzle total-pressure losses look optimistic (dry NPR 4.2 vs closure 3.5-3.8)",
)
def test_c2_dry_thrust(m):
    """C2 [ASSUMPTION, Wikipedia/FI + note Q1 closure]: dry (MIL) SLS thrust about 54 kN, +-3 %."""
    assert abs(m.design.stations["fn_dry"] / 54_000.0 - 1.0) <= 0.03


# ----------------------------------------------------------------------------------------------- C3-C6

C3_REF = ((65.0, 61.5), (75.0, 75.0), (80.0, 87.0), (90.0, 114.0), (95.0, 129.5), (100.0, 145.0))  # %, lb/s


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 calibration (map modifiers, A-W1.3a-2): corrected airflow vs N1c "
    "is within 1 % above 88 % N1c but 5-9 % low at 70-82 % N1c",
)
def test_c3_corrected_airflow_vs_n1c(m, sch):
    """C3 [TRANSFER: F404-400, CR-198052 Fig. 2 correlation line, x1.05 to the IN20 = normalised shape]:
    Wc/Wc(100 %) vs N1c within +-3 % at the reference speeds."""
    pts = []
    for f in sch.n2_grid:
        r = _on_line(m, sch, f)
        pts.append((r.aux[A["n1c"]] / 13270.0 * 100.0, r.aux[A["w2c"]] / 70.0))
    pts = np.array(sorted(pts))
    for n1c, w in C3_REF:
        if pts[0, 0] <= n1c <= pts[-1, 0]:
            model = np.interp(n1c, pts[:, 0], pts[:, 1])
            assert abs(model / (w / 145.0) - 1.0) <= 0.03, (n1c, model, w / 145.0)


C4_REF = ((1.60, 61.2), (2.00, 80.0), (2.67, 109.3), (3.00, 121.8), (3.40, 138.4))  # PS21/PT2, lb/s


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 calibration: PS21/PT2 vs corrected flow deviates -7.5/-9.0/-7.6/-4.9/+3.5 % at the five "
    "CR-198052 points (flow/146 = 0.42/0.55/0.75/0.83/0.95; worst 9.0 % vs +-3 %): the fan-exit static ratio "
    "follows the generic AXI5 operating line, not the -400 table; PS21 is estimated at a fan-exit Mach 0.46 "
    "(pyCycle)",
)
def test_c4_fan_static_pressure_ratio_vs_flow(m, sch):
    """C4 [TRANSFER: F404-400 CR-198052 Tbl 5]: PS21/PT2 vs corrected flow (normalised by 146 lb/s), +-3 %.
    PS21 from P21 with the fan-exit Mach fixed by the design Mach 0.4578 (pyCycle example) via continuity."""
    from phalanx.engine.thermo import gamma_of

    g = float(gamma_of(m.design.stations["t21"], 0.0, 0.0, m.tables.thermo))
    m_des = 0.4578
    rows = []
    for f in sch.n2_grid:
        r = _on_line(m, sch, f)
        a = r.aux
        # corrected flow per area scales with M (1 + (g-1)/2 M^2)^(-(g+1)/(2(g-1))): solve M from the ratio
        q_des = m_des * (1 + 0.5 * (g - 1) * m_des**2) ** (-(g + 1) / (2 * (g - 1)))
        wq = (a[A["w2"]] * np.sqrt(a[A["t21"]]) / r.x[2]) / (
            70.0 * np.sqrt(m.design.stations["t21"]) / m.design.stations["p21"]
        )
        target = q_des * wq
        mach = np.linspace(0.01, 0.99, 2000)
        qm = mach * (1 + 0.5 * (g - 1) * mach**2) ** (-(g + 1) / (2 * (g - 1)))
        mm = float(np.interp(target, qm, mach))
        ps21 = r.x[2] * (1 + 0.5 * (g - 1) * mm**2) ** (-g / (g - 1))
        rows.append((a[A["w2c"]] / 70.0, ps21 / a[A["p2"]]))
    rows = np.array(sorted(rows))
    for ratio, w in C4_REF:
        wn = w / 146.0
        if rows[0, 0] <= wn <= rows[-1, 0]:
            assert abs(np.interp(wn, rows[:, 0], rows[:, 1]) / ratio - 1.0) <= 0.03, (wn, ratio)


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.1/W2.3: MIL nozzle conditions vs altitude need the M08 IRP control "
    "(N1 = f(T1), A8 holding T5); with fixed A8 and N1 the mixed T8 is not altitude-invariant: 1,011/1,015/"
    "987/962 K at 3.85/12.3/22.3/32.3 kft, spread 5.35 % of the mean vs <= 1 %",
)
def test_c5_mil_t8_altitude_invariant(m):
    """C5 [TRANSFER: F404-400, TM-4538 Tbl 2]: at MIL the mixed nozzle temperature is constant with altitude
    (935-939 K for the -400); here: T8 at 3.85/12.3/22.3/32.3 kft MIL within +-1 % of each other."""
    from phalanx.engine.layout import U_MACH, U_PS

    t8 = []
    for alt_ft, mach in ((3850, 0.32), (12324, 0.68), (22331, 0.77), (32307, 0.89)):
        t_s, p_s = _isa(alt_ft * 0.3048)
        u = design_inputs(m)
        u[U_TS], u[U_PS], u[U_MACH] = t_s, p_s, mach
        r = steady_state(m, u, target=("n1", m.design.stations["n1"]))
        t8.append(r.aux[A["t6"]])
    t8 = np.array(t8)
    assert (t8.max() - t8.min()) / t8.mean() <= 0.01, t8


def _isa(h: float) -> tuple[float, float]:
    """US Standard Atmosphere 1976 troposphere/tropopause (test helper; M03 owns the atmosphere)."""
    if h <= 11000.0:
        t = 288.15 - 0.0065 * h
        return t, 101325.0 * (t / 288.15) ** 5.255877
    p11 = 101325.0 * (216.65 / 288.15) ** 5.255877
    return 216.65, p11 * np.exp(-9.80665 * (h - 11000.0) / (287.0528 * 216.65))


C6_REF = ((91.3, 2.055, 4979.0), (100.7, 2.330, 6122.0), (110.1, 2.610, 7326.0), (120.6, 2.720, 8718.0))


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 calibration: ground part-power NPR/FG ratios vs nozzle flow differ "
    "from the -400 HARV table (dry fan-to-nozzle losses, A-W1.3a-1/19; A8 schedule is M08's): at W8/W8_MIL "
    "0.76/0.84/0.91 NPR is -30.4/-22.4/-11.1 % and FG -14.3/-8.2/-1.2 % relative to the table shape (+-3 %)",
)
def test_c6_ground_part_power_shape(m, sch):
    """C6 [TRANSFER: F404-400 TM-4538 Tbl 4]: NPR and FG relative to MIL vs nozzle flow relative to MIL,
    +-3 % (shape transfer)."""
    rows = []
    for f in sch.n2_grid:
        r = _on_line(m, sch, f)
        rows.append((r.aux[A["w8"]], r.aux[A["p7"]] / 101325.0, r.aux[A["fg"]]))
    rows = np.array(sorted(rows))
    w_mil, npr_mil, fg_mil = rows[-1]
    for w8, npr, fg in C6_REF:
        wn = w8 / 120.6 * w_mil
        assert abs(np.interp(wn, rows[:, 0], rows[:, 1]) / npr_mil / (npr / 2.720) - 1.0) <= 0.03
        assert abs(np.interp(wn, rows[:, 0], rows[:, 2]) / fg_mil / (fg / 8718.0) - 1.0) <= 0.03


@pytest.mark.golden
@pytest.mark.skip(
    reason="C7/C9/C13 need the M06 drag/ram model in the loop or a digitised envelope table (W2.1a/W2.3); "
    "C12 runs with M08 in the loop in tests/golden/test_engine_fadec_golden.py (W2.1b)"
)
def test_c7_c9_c13_flight_points():
    pass


# ----------------------------------------------------------------------------------------------- C8, C10


@pytest.mark.golden
def test_c8_ab_thrust_ratio_at_high_ab_fuel_air(m):
    """C8 [TRANSFER: F404-400 TM-100159 Fig. 8]: AB thrust ratio 1.50-1.55 at AB f/a 0.062-0.066 (f/a on the
    air left after core combustion). SLS, gas generator held at the design N1 by the nozzle area; +-3 %."""
    d = m.design
    w6_dry = d.stations["w8"] - d.stations["wf"]
    air_left = w6_dry * (1.0 - d.stations["wf"] / w6_dry / d.max_ab["f_stoich"])
    u = design_inputs(m)
    u[U_WFAB] = 0.064 * air_left
    best = None
    for a8r in np.linspace(1.4, 1.8, 41):
        u[U_A8] = d.stations["a8"] * a8r
        r = steady_state(m, u, ab_state=AB_LIT)
        if r.converged and (best is None or abs(r.x[0] - d.stations["n1"]) < best[0]):
            best = (abs(r.x[0] - d.stations["n1"]), r.aux[A["fn"]] / d.stations["fn_dry"])
    assert best is not None and best[0] < 0.005 * d.stations["n1"]
    assert 1.50 * 0.97 <= best[1] <= 1.55 * 1.03, best


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.1/W2.3: 1 % bleed at MIL costs 0.3 % thrust with N1 held (-1.3 % "
    "with fuel held) vs 2 % for the -400 under its T5-limited IRP control (M08)",
)
def test_c10_bleed_thrust_sensitivity(m):
    """C10 [TRANSFER: F404-400 TM-104247]: 1 % more customer bleed at MIL costs about 2 % thrust (+-25 %)."""
    u = design_inputs(m)
    r0 = steady_state(m, u, target=("n1", m.design.stations["n1"]))
    u[U_BLEED] = 0.01 * m.design.stations["w25"]
    r1 = steady_state(m, u, target=("n1", m.design.stations["n1"]))
    loss = -(r1.aux[A["fn"]] / r0.aux[A["fn"]] - 1.0) * 100.0
    assert 2.0 * 0.75 <= loss <= 2.0 * 1.25, loss


# ---------------------------------------------------------------------------------------- C11, C14, C15


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="TEST-DESIGN DEFECT (E1 verifier §3; not calibration): Henry's aircraft target is a snapshot "
    "of an IECMS take-off record (slam acceleration, nozzle closed), but this test evaluates a steady point, "
    "so no calibration can close it. Measured, steady IN20 at the same N2 (88.8 % of its MIL N2): N1 +7.6 %, "
    "T5 -10.0 %, PS3 +23.1 %, P5 +5.6 % (+-3 %). Resolved in W2.1 by a transient-vs-transient check: the "
    "snapshot at N2 14,204 rpm during a VEN-closed slam under the M08 take-off and accel logic at T1 296.1 K",
)
def test_c11_takeoff_snapshot(m, sch):
    """C11 [TRANSFER: F404-400 aircraft, Henry AGARD-CP-448 paper 37 Tbl 1]: T1 296.1 K, N2 14,204 rpm ->
    N1 10,560 rpm, T5 871 K, PS3 137.9 psia, P5 24.7 psia, each +-3 %.

    Henry's aircraft targets come from IECMS take-off records inside the nozzle-closed window of a slam
    acceleration (paper 37, 'Data capture window' and Table 1), i.e. a transient state. A steady point at the
    same N2 is not like with like (during a slam the fuel flow is set by the accel schedule, the rotors are
    accelerating and the nozzle is held closed, none of which holds on the steady line), so this comparison
    is reclassified as a test-design defect and kept as a strict xfail diagnostic until W2.1 can run the
    transient with the M08 take-off logic (the W1 fixture governor's ratio-unit limit is not the -400 MFC
    max-fuel schedule, so a fixture slam would only move the defect). The T5 target is 871.0 K on the page
    image of Table 1; two research notes transcribe it as 971.0 K (an OCR error, E1-HY report)."""
    u = design_inputs(m)
    u[U_TS] = 296.1
    f = 14204.0 * 2 * np.pi / 60.0 / sch.n2_des
    u[U_A8] = sch.a8(f)
    r = steady_state(m, u, x0=sch.x_at(f), target=("n2", f * sch.n2_des))
    got = (r.x[0] * 60 / (2 * np.pi), r.aux[A["t5"]], r.aux[A["ps3"]] / PSI, r.aux[A["p5"]] / PSI)
    for g, t in zip(got, (10560.0, 871.0, 137.9, 24.7), strict=True):
        assert abs(g / t - 1.0) <= 0.03, (got,)


@pytest.mark.golden
def test_c14_mil_t5_in_closure_band(m):
    """C14: SLS MIL T5 within the IN20 closure band 1,130-1,160 K [ASSUMPTION, note Q1] and above the -400
    test-cell MIL plateau (about 1,089 K, CR-191195 Fig. 33) by less than 100 K (hotter IN20 turbine)."""
    t5 = m.design.stations["t5"]
    assert 1130.0 <= t5 <= 1160.0
    assert 0.0 < t5 - 1088.7 < 100.0


@pytest.mark.golden
def test_c15_reference_fvg_schedule(m):
    """C15 [TRANSFER: F404-400 CR-198052 Fig. 31]: M07's reference FVG schedule passes through the digitised
    band mid-points (<= 73 % N1c 47.5-52.5 deg; 80 % 36-40; 90 % 16.5-20; 95 % 8-12; 100 % -1..2 deg) and the
    CVG ends match CR-191195 Fig. 33 (idle 48-52 deg; high power 1-14 deg). Guards the parameter file."""
    tb = m.tables
    fvg = lambda f: np.degrees(interp1(tb.fvg_x, tb.fvg_y, f))  # noqa: E731
    for f, lo, hi in (
        (0.70, 47.5, 52.5),
        (0.80, 36.0, 40.0),
        (0.90, 16.5, 20.0),
        (0.95, 8.0, 12.0),
        (1.0, -1, 2),
    ):
        assert lo <= fvg(f) <= hi, f
    cvg = lambda f: np.degrees(interp1(tb.cvg_x, tb.cvg_y, f))  # noqa: E731
    assert 48.0 <= cvg(0.70) <= 52.0 and 1.0 <= cvg(1.0) <= 14.0


# ----------------------------------------------------------------------------------------------- C17, C20-C23


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.1/W2.3: take-off transient indices need the M08 take-off logic (VEN "
    "closed ~1 s and held ~4 s, max-fuel schedule above 50 deg/s throttle rate): with the fixture governor "
    "PS3 reaches 95 % of its plateau in 3.33 s vs 4-5 s",
)
def test_c17_takeoff_indices(m, sch):
    """C17 [TRANSFER: F404-400 Henry/Muir]: from ground idle, N1 accelerates over the nozzle-closed window in
    0.75-1.25 s and PS3 reaches its plateau in 4-5 s (fixture governor without take-off logic)."""
    gov = fx.GovernorFixture(kp=2.0, ki=1.0, ru_acc=1.5, ru_dec=1.0 / 1.5)
    n = 240 * 10
    r = fx.run_closed_loop(sch, gov, np.full(n, 1.0), n, x0=sch.x_at(0.72), a8_override=sch.a8_mil)
    ps3 = r.y[:, 0, Y_NAMES.index("ps3")]
    t_plateau = int(np.argmax(ps3 >= 0.95 * ps3[-1])) / 240.0
    assert 4.0 <= t_plateau <= 5.0, t_plateau


def _start_from_rest(m, fuel_kg_s: float = 0.05, t_end_s: float = 60.0):
    """Ground start from rest with the M09 start-drive convention (TEST FIXTURE sequencer and fuel schedule).

    Physical initial state: all volumes at ambient pressure, gas and metal at ambient temperature, no fuel,
    nozzle open (1.8 x MIL A8), VG on the reference schedule, N1 1 % and N2 2 % (kernel floors). The JFS
    drive is P = min(P_rated, T_peak (N2 + w_floor)) x gearbox efficiency, delivered as negative pto_power
    (values from configs/tejas/params/M09.yaml, W1.4); cut out at jfs_n2_cutout of 100 % N2. Fuel on with
    ignition at 20 % N2 (KSAS 2006 Fig. 2)."""
    from phalanx.dictionary.params import load_params
    from phalanx.engine.layout import U_PTO, X_NAMES
    from phalanx.engine.steady import design_state, vg_reference

    st = m.design.stations
    m09 = load_params("M09")
    t_peak, gb = m09["amagb"].value("pto_torque_peak"), m09["amagb"].value("gb_eff")
    w_floor, p_rated = m09["jfs"].value("jfs_w_floor"), m09["jfs"].value("jfs_p_rated")
    cutout = m09["jfs"].value("jfs_n2_cutout")
    xi = {n: j for j, n in enumerate(X_NAMES)}
    x = design_state(m).copy()
    x[xi["n1"]], x[xi["n2"]] = 0.01 * st["n1_100"], 0.02 * st["n2_100"]
    for k in ("p21", "p3", "p45", "p5", "p6"):
        x[xi[k]] = 101325.0
    x[xi["t41"]] = x[xi["tm"]] = x[xi["tc"]] = x[xi["toil"]] = 288.15
    x[xi["wfm"]] = x[xi["wfab"]] = 0.0
    x[xi["a8"]] = 1.8 * st["a8"]
    x[xi["vg1"]], x[xi["vg2"]] = vg_reference(m, 0.0, 0.0)
    u0 = design_inputs(m, wf_cmd=0.0)
    u0[U_A8] = 1.8 * st["a8"]
    state = state_from_x(m, x, flame=0)
    chunk, n2, t5, flame = 24, [], [], []
    starter, fuel_on, t_fuel = True, False, None
    for _ in range(int(t_end_s * 240 / chunk)):
        w2 = state.f[0, 1]
        pw = min(p_rated, t_peak * (w2 + w_floor)) * gb if starter else 0.0
        v1, v2 = vg_reference(m, state.f[0, 0] / st["n1"], w2 / st["n2"])
        u, ui = input_block(chunk, 1, u0, wf_cmd=fuel_kg_s if fuel_on else 0.0, vg_igv_cmd=v1, vg_vsv_cmd=v2,
                            ignition=np.full(chunk, int(fuel_on), np.int64))  # fmt: skip
        u[:, :, U_PTO] = -pw
        r = simulate(m, state, u, ui)
        state = r.state
        n2.extend(r.y[:, 0, 1] / st["n2_100"])
        t5.extend(r.y[:, 0, Y_NAMES.index("t5")])
        flame.extend(r.yi[:, 0, 1])
        if not fuel_on and n2[-1] >= 0.20:
            fuel_on, t_fuel = True, len(n2) / 240.0
        if n2[-1] >= cutout:
            starter = False
    return np.asarray(n2), np.asarray(t5), np.asarray(flame), t_fuel


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="structural PROXY limit (AD-46, A-W1.3a-3; not calibration): the sub-idle regime is "
    "map-similarity extrapolation. From rest with the M09 start drive the engine is at 20 % N2 after 2.7 s "
    "(KSAS about 7 s), lights 0.55 s after fuel-on, then hangs at 61 % N2 (idle 63 %) with a 1,500 K T5 peak "
    "(assumed <= 1,023 K). Replacement: a sub-idle map extension calibrated on the T-50 start and airstart "
    "tables",
)
def test_c20_c21_start_and_airstart(m):
    """C20/C21 [TRANSFER: F404-GE-102, KSAS 2006 Fig. 2; EGT peak ASSUMPTION note Q7]: fuel-on at about 20 %
    N2, starter cut-out at 55 % N2, idle (63 % N2) about 18.5 s after fuel-on (+-25 %), start T5 peak
    <= 1,023 K. Until this passes, sortie telemetry starts from post-start idle (AD-46)."""
    n2, t5, _, t_fuel = _start_from_rest(m)
    assert t_fuel is not None and n2.max() >= 0.63, n2.max()
    t_idle = int(np.argmax(n2 >= 0.63)) / 240.0 - t_fuel
    assert abs(t_idle / 18.5 - 1.0) <= 0.25, t_idle
    assert t5.max() <= 1023.0, t5.max()


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="PROXY A-W1.3a-3 / W2.3: flame-out rundown from 80 % NH: NH +1 s 69.9 % (64), +15 s 33.0 % (48); "
    "NL +5 s 23.5 % (19), +15 s 10.2 % (9); PS3 +1 s 0.36 of its value (0.17); the RM12 case also lost "
    "compressor work to bird damage",
)
def test_c22_flameout_rundown(m, sch):
    """C22 [TRANSFER: RM12 SHK RM 2019:02 Fig. 18]: from NH 80 %: NH about 64 % at +1 s, 48 % at +15 s;
    NL about 19 % at +5 s, 9 % at +15 s; PS3 to about 0.17 of its value within 1 s (each +-25 %)."""
    r0 = _on_line(m, sch, _frac(m, 80.0))
    n = 240 * 16
    wf = np.full(n, r0.u[U_WF])
    wf[24:] = 0.0
    y = simulate(m, state_from_x(m, r0.x), *input_block(n, 1, r0.u, wf_cmd=wf)).y[:, 0]
    nh = y[:, 1] / m.design.stations["n2_100"] * 100.0
    nl = y[:, 0] / m.design.stations["n1_100"] * 100.0
    ps3 = y[:, Y_NAMES.index("ps3")]
    checks = ((nh[264], 64.0), (nh[24 + 3600], 48.0), (nl[24 + 1200], 19.0), (nl[24 + 3600], 9.0),
              (ps3[264] / ps3[0], 0.17))  # fmt: skip
    for g, t in checks:
        assert abs(g / t - 1.0) <= 0.25, checks


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="structural PROXY limit (AD-46, A-W1.3a-9; not calibration): the surge event model has no "
    "post-stall dynamics; CDP collapses to about 0.26 of its pre-surge value vs 0.12 (HARV 85 -> 10 psia). "
    "Replacement: a lumped Greitzer-type post-stall model (B parameter, plenum and duct inertance)",
)
def test_c23_surge_collapse_and_recovery(m):
    """C23 [TRANSFER: F404-400 HARV TM-1999-206572]: CDP 85 -> 10 psia (ratio 0.12 +-25 %) and recovery within
    about 0.2 s (+-25 %) after an isolated surge."""
    u = design_inputs(m)
    u[U_WF] *= 0.9
    ss = steady_state(m, u)
    n = 240 * 2
    h = np.zeros((n, 1, 10))
    h[24:60, 0, 5] = -0.15
    r = simulate(m, state_from_x(m, ss.x), *input_block(n, 1, ss.u, health=h))
    assert r.state.i[0, I_NSURGE] >= 1
    p3 = r.y[:, 0, Y_NAMES.index("bleed_p3")]
    assert abs(p3.min() / p3[0] / 0.12 - 1.0) <= 0.25


# ----------------------------------------------------------------------------------------------- C24, C26


@pytest.mark.golden
def test_c24_vibration_levels(m, sch):
    """C24 [TRANSFER: F404-400 DSTO-TN-0530]: mid-frame overall velocity about 0.34-0.42 in/s avg at MIL and
    0.04-0.16 at ground idle; accepted within +-25 % of those bands. (The band split is A-W1.3a-14.)"""
    out = {}
    idle = _frac(m, 65.2)  # released ground-idle N2 (F404-400 test cell)
    for f in (1.0, idle):
        r = _on_line(m, sch, f)
        a = r.aux
        f1, f2 = r.x[0] / (2 * np.pi), r.x[1] / (2 * np.pi)
        v = np.sqrt((a[A["vib_n1"]] / (2 * np.pi * f1)) ** 2 + (a[A["vib_n2"]] / (2 * np.pi * f2)) ** 2
                    + (a[A["vib_bb"]] / (2 * np.pi * 500.0)) ** 2)  # fmt: skip
        out[f] = v / 0.0254 * 2.0 / np.pi  # in/s average
    assert 0.34 * 0.75 <= out[1.0] <= 0.42 * 1.25, out
    assert 0.04 * 0.75 <= out[idle] <= 0.16 * 1.25, out


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 calibration: fault-signature magnitudes (signs pass in test_engine_signs): -5 % HPC "
    "efficiency gives Wfm +10.5 % (9.6) and Fg +6.5 % (6.0) but PS3/P1 only +3.9 % (9.6; Muir NRC model)",
)
def test_c26_fault_signature_magnitudes(m):
    """C26 [TRANSFER: F404-400 Muir et al. Figs. 17-18, NRC model]: -5 % HPC efficiency -> Wfm vs N2 +9.6 %,
    PS3/P1 vs N2 +9.6 %, Fg vs N2 +6.0 %; 6 deg CVG -> Wfm vs N2 +11.1 %, PS3/P1 +8.1 %, Fg +11.7 %
    (+-25 %)."""
    spec = importlib.util.spec_from_file_location("engine_signs_g", Path(__file__).resolve().parents[1]
                                                  / "integration" / "test_engine_signs.py")  # fmt: skip
    sg = importlib.util.module_from_spec(spec)
    sys.modules["engine_signs_g"] = sg
    spec.loader.exec_module(sg)
    base = sg.operating_line(m)
    h = np.zeros(10)
    h[2] = -0.05
    d1 = sg.operating_line(m, h)
    d2 = sg.operating_line(m, dvg=(0.0, -np.radians(6.0)))
    for d, ref in ((d1, (0.096, 0.096, 0.060)), (d2, (0.111, 0.081, 0.117))):
        got = (sg.shift(base, d, "Wfm", "N2"), sg.shift(base, d, "PS3", "N2"), sg.shift(base, d, "Fg", "N2"))
        for g, t in zip(got, ref, strict=True):
            assert abs(g / t - 1.0) <= 0.25, (got, ref)


# ----------------------------------------------------------------------------------------------- method check


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3: the same cycle code configured with the -400 table (FPR 4.1, CPR 6.0, "
    "BPR 0.34, 64.4 kg/s, TIT 1,663 K) gives 10,930 lbf / SFC 0.756 vs 10,600 lbf / 0.78 (+3.1 %, "
    "-3.1 %): just outside +-3 %, consistent with the optimistic losses of C2",
)
def test_minus400_method_check():
    """Method validation [TRANSFER: F404-400 ARL-AERO-PROP-TM-426 Fig. 3]: the closure machinery applied to
    the -400 cycle table reproduces its MIL thrust 10,600 lbf and SFC 0.78 lb/h/lbf within +-3 %."""
    ps = load_engine_params().replace(
        w2_design=64.4, opr_design=25.0, fpr_design=4.1, bpr_design=0.34, t4_design=1663.0,
        thrust_max_ab=16000.0 * LBF,
    )  # fmt: skip
    st = build_engine_model(ps).design.stations
    assert abs(st["fn_dry"] / (10600.0 * LBF) - 1.0) <= 0.03
    sfc = st["sfc_dry"] * 3600.0 * 9.80665
    assert abs(sfc / 0.78 - 1.0) <= 0.03


_ = (U_H0, U_VG2)
