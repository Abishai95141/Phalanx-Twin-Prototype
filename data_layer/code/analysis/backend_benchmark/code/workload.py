"""W0.6 benchmark workload: a two-spool engine mini-model in closed loop with an M08-like governor.

BENCHMARK WORKLOAD, NOT A PHYSICS DELIVERABLE. It reproduces the *computational structure* of the future
M07/M08/M03 hot loop (rotor ODEs on 2-D torque maps, actuator / volume / thermal lags with a flow-dependent time
constant, a metal-temperature state, MIN/MAX limiter selection at a slower rate group, sub-stepping, keyed per-unit
process disturbances). Parameter values are representative only; every value carries an evidence tag and the
build never reads them. Units are SI inside the model (rad/s, kg/s, Pa, K, N*m, s).

Layout (shared by every backend; integer indices are compile-time constants):
  P      float64[NP]      type-level parameters (index constants below)
  health float64[U, 2]    per-unit health scalars (AD-07 style): eta_hp (fuel/HPT effectiveness), eta_lp (fan/core match)
  X      float64[U, NX]   continuous + held state
  S      int64[U, NS]     integer state: truth-step index k (controller phase), selected limiter
  inputs float64[U, L, 3] PLA [deg], T2 [K], P2 [Pa] per truth step (exogenous; M03/M04/M06 in the build)
  noise  float64[U, L, 2] standard-normal innovations from keyed Philox blocks (rngblocks.py)
  out    float64[U, L, 6] N1, N2, Wf, PS3, T5, Tm after each step; sel int64[U, L]
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

# ---------------------------------------------------------------- time base (AD-11, AD-35)
TRUTH_HZ = 240
DT = 1.0 / TRUTH_HZ  # s; physics dt (truth instants are (k*10**9)//240 ns, AD-35)
NSUB = 4  # inner Heun sub-steps per truth step (>= 2 required by the brief)
H = DT / NSUB  # s
HH = 0.5 * H
CTRL_DIV = 4  # controller rate group: 240/4 = 60 Hz [TRANSFER: FADEC-INT 50-67 Hz, architecture section 8]
DTC = CTRL_DIV * DT
BLOCK = 2400  # steps per RNG / input block (10 s)

# ---------------------------------------------------------------- reference conditions
T0 = 288.15  # K, ISA sea level
P0 = 101325.0  # Pa

# ---------------------------------------------------------------- state / IO index constants
N1, N2, WF, PS3, T5, TM, XI, DF, DQ, WFC = range(10)
NX = 10
SK, SSEL = 0, 1
NS = 2
I_PLA, I_T2, I_P2 = 0, 1, 2
NOUT = 6
SEL_GOV, SEL_N1, SEL_T5, SEL_ACC, SEL_DEC, SEL_MIN = range(6)

# ---------------------------------------------------------------- parameter vector
# (name, value, unit, tag/source). Tags: RULES.md rule 3. None of these values is used by the build.
_TAU_C_F, _SIG_F = 0.3, 0.005  # AR(1) fuel-metering disturbance: corr. time [s], SD [-]
_TAU_C_Q, _SIG_Q = 1.0, 0.01  # AR(1) LP load-torque disturbance: corr. time [s], SD [fraction of QD_REF]
PARAMS: list[tuple[str, float, str, str]] = [
    ("I_LP", 3.5, "kg m2", "[ASSUMPTION] F100 scaled; research_notes f404_in20_engine_model.md Q6 (l.405)"),
    ("I_HP", 3.0, "kg m2", "[ASSUMPTION] F100 scaled; same source"),
    ("TAU_ACT", 0.05, "s", "[ASSUMPTION] fuel-metering servo lag; benchmark value"),
    ("TAU_V", 0.02, "s", "[ASSUMPTION] combustor volume lag; TP-1034 T3 lag 0.05 s order (notes Q6 l.399)"),
    ("TAU_G_REF", 0.81, "s", "[MEASURED: proxy] round-2 thermocouple tau_ref 0.81 s (AD-23)"),
    ("W_EXP", -0.5, "-", "[TRANSFER: AGARD] tau ~ W^-0.5 (AD-23; brief)"),
    ("TAU_M", 30.0, "s", "[ASSUMPTION] lumped hot-section metal tau 'tens of seconds' (notes Q6 l.406)"),
    ("K_CLR", 1.0, "N m/K", "[ASSUMPTION] heat-soak clearance torque loss; benchmark value"),
    ("KP", 7.5e-3, "kg/s per rad/s", "[ASSUMPTION] governor P gain (~3 rad/s loop bandwidth)"),
    ("KI", 9.4e-3, "kg/s per rad", "[ASSUMPTION] governor I gain (KP/0.8 s)"),
    ("K_N1", 1.0e-4, "kg/s per rad/s per tick", "[ASSUMPTION] N1 topping limiter gain"),
    ("K_T5", 2.0e-4, "kg/s per K per tick", "[ASSUMPTION] T5 limiter gain"),
    ("ACC_SCALE", 1.0, "-", "[ASSUMPTION] accel Wf/PS3 schedule multiplier"),
    ("DEC_SCALE", 1.0, "-", "[ASSUMPTION] decel Wf/PS3 schedule multiplier"),
    ("A_EXP", 0.73, "-", "[MEASURED: proxy] real EGT theta exponent 0.73 (architecture E17)"),
    ("QD_REF", 2000.0, "N m", "[ASSUMPTION] LP disturbance torque scale (AD-32; to be identified)"),
    ("PHI_F", math.exp(-DT / _TAU_C_F), "-", "[ASSUMPTION] AR(1) fuel-metering pole (tau_c 0.3 s)"),
    (
        "S_F",
        _SIG_F * math.sqrt(1.0 - math.exp(-2.0 * DT / _TAU_C_F)),
        "-",
        "[ASSUMPTION] innov. SD (sigma 0.5 %)",
    ),
    ("PHI_Q", math.exp(-DT / _TAU_C_Q), "-", "[ASSUMPTION] AR(1) LP-torque pole (tau_c 1 s)"),
    (
        "S_Q",
        _SIG_Q * math.sqrt(1.0 - math.exp(-2.0 * DT / _TAU_C_Q)),
        "-",
        "[ASSUMPTION] innov. SD (sigma 1 %)",
    ),
    (
        "OMEGA1_100",
        13270.0 * 2.0 * math.pi / 60.0,
        "rad/s",
        "[TRANSFER: -400] 100 % N1 13,270 rpm (arch. M07)",
    ),
    (
        "OMEGA2_100",
        16810.0 * 2.0 * math.pi / 60.0,
        "rad/s",
        "[TRANSFER: -400] 100 % N2 16,810 rpm (arch. M07)",
    ),
    ("N1MAX_C", 1.02, "-", "[ASSUMPTION] corrected N1 cap (the -400 cap is 104.4 %, report l.238)"),
    ("T5MAX", 1150.0, "K", "[ASSUMPTION] T5 limit; MIL T5 plateau ~1,089 K (notes l.326)"),
    ("WF_MIN", 0.04, "kg/s", "[ASSUMPTION] benchmark-only minimum fuel (not evidence)"),
    ("W_REF", 70.0, "kg/s", "[DIRECT] IN20 airflow 70 kg/s (notes l.34)"),
]
PNAMES = [p[0] for p in PARAMS]
NP = len(PARAMS)
P_I_LP, P_I_HP, P_TAU_ACT, P_TAU_V, P_TAU_G_REF, P_W_EXP, P_TAU_M, P_K_CLR = range(8)
P_KP, P_KI, P_K_N1, P_K_T5, P_ACC_SCALE, P_DEC_SCALE, P_A_EXP, P_QD_REF = range(8, 16)
P_PHI_F, P_S_F, P_PHI_Q, P_S_Q, P_OMEGA1_100, P_OMEGA2_100, P_N1MAX_C, P_T5MAX = range(16, 24)
P_WF_MIN, P_W_REF = 24, 25
assert NP == 26 and PNAMES[P_W_REF] == "W_REF" and PNAMES[P_PHI_F] == "PHI_F"


def default_params() -> np.ndarray:
    return np.array([p[1] for p in PARAMS], dtype=np.float64)


# ---------------------------------------------------------------- design lines (analytic; tables are sampled)
# [ASSUMPTION] benchmark shapes. Anchors: idle N2 ~68 % (T-50 idle 63-70 %, notes l.430); SLS MIL core Wf
# ~1.15 kg/s (IN20 8,700-9,500 lb/h, notes l.120); ground idle Wf ~0.11 kg/s
# (benchmark-only shape, not evidence);
# OPR 28 [DIRECT]; T5 ~682 K idle / ~1,089 K MIL (notes l.326); spool taus N1 0.9-1.3 s, fan small-step ~0.8 s
# (report l.264, notes l.405).
def wf_ss(n2):
    return 0.05 + 0.2 * (n2 - 0.6) + 1.02 * np.maximum(n2 - 0.6, 0.0) ** 2 / 0.16


def n1_ss(n2):
    return np.maximum(n2, 0.3) ** 1.2


def psr_line(n2):
    return 1.0 + 27.0 * (np.maximum(n2 - 0.35, 0.0) / 0.65) ** 2


def t5_line(n2):
    return 680.0 + 410.0 * (np.maximum(n2 - 0.6, 0.0) / 0.4) ** 1.3


def wc_line(n1):
    return 70.0 * np.maximum(n1, 0.05) ** 1.5


_A0 = 3.0 * (16810.0 * 2 * math.pi / 60) / (0.8 * 5.3)  # N m per kg/s: tau_N2 ~0.8 s at MIL
_B0 = 3.5 * (13270.0 * 2 * math.pi / 60) / 0.8  # N m per unit n1: tau_N1 ~0.8 s at MIL


def qhp_fn(n2, wf):
    return _A0 / n2**2 * (wf - wf_ss(n2))


def qlp_fn(n1, n2):
    return _B0 * (0.3 + 0.7 * n2) * (n1_ss(n2) - n1)


def t5c_fn(n2, wf):
    return np.maximum(t5_line(n2) + 350.0 * (wf - wf_ss(n2)) / (wf_ss(n2) + 0.1), 350.0)


# ---------------------------------------------------------------- tables (non-uniform breakpoints)
G_N2 = np.array([0.50, 0.58, 0.64, 0.68, 0.72, 0.76, 0.80, 0.84, 0.88, 0.92, 0.95, 0.98, 1.01, 1.05, 1.10])
G_N1 = np.array([0.30, 0.40, 0.48, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10])
G_WF = np.array([0.0, 0.03, 0.06, 0.10, 0.15, 0.22, 0.32, 0.45, 0.62, 0.82, 1.05, 1.30, 1.60, 2.0])
G_SCH = np.array([0.50, 0.60, 0.66, 0.72, 0.78, 0.84, 0.90, 0.96, 1.02, 1.10])
G_PLA = np.array([0.0, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 87.0, 100.0, 130.0])
N2DEM = np.array([0.66, 0.68, 0.70, 0.75, 0.80, 0.845, 0.885, 0.925, 0.965, 1.00, 1.015, 1.03])


class Tables(NamedTuple):
    """Lookup tables. *_x breakpoints, *_r = 1/diff(x) (precomputed once, shared by all backends), *_y / *_z values."""

    pla_x: np.ndarray
    pla_r: np.ndarray
    pla_y: np.ndarray
    acc_x: np.ndarray
    acc_r: np.ndarray
    acc_y: np.ndarray
    dec_x: np.ndarray
    dec_r: np.ndarray
    dec_y: np.ndarray
    psr_x: np.ndarray
    psr_r: np.ndarray
    psr_y: np.ndarray
    wc_x: np.ndarray
    wc_r: np.ndarray
    wc_y: np.ndarray
    qhp_x: np.ndarray
    qhp_rx: np.ndarray
    qhp_y: np.ndarray
    qhp_ry: np.ndarray
    qhp_z: np.ndarray
    qlp_x: np.ndarray
    qlp_rx: np.ndarray
    qlp_y: np.ndarray
    qlp_ry: np.ndarray
    qlp_z: np.ndarray
    t5_x: np.ndarray
    t5_rx: np.ndarray
    t5_y: np.ndarray
    t5_ry: np.ndarray
    t5_z: np.ndarray


def _r(x):
    return 1.0 / np.diff(x)


def make_tables() -> Tables:
    n2, wf = np.meshgrid(G_N2, G_WF, indexing="ij")
    n1, n2b = np.meshgrid(G_N1, G_N2, indexing="ij")
    sch = wf_ss(G_SCH) / (psr_line(G_SCH) * P0)
    f = lambda a: np.ascontiguousarray(a, dtype=np.float64)  # noqa: E731
    return Tables(
        f(G_PLA), f(_r(G_PLA)), f(N2DEM),
        f(G_SCH), f(_r(G_SCH)), f(1.6 * sch),
        f(G_SCH), f(_r(G_SCH)), f(0.45 * sch),
        f(G_N2), f(_r(G_N2)), f(psr_line(G_N2)),
        f(G_N1), f(_r(G_N1)), f(wc_line(G_N1)),
        f(G_N2), f(_r(G_N2)), f(G_WF), f(_r(G_WF)), f(qhp_fn(n2, wf)),
        f(G_N1), f(_r(G_N1)), f(G_N2), f(_r(G_N2)), f(qlp_fn(n1, n2b)),
        f(G_N2), f(_r(G_N2)), f(G_WF), f(_r(G_WF)), f(t5c_fn(n2, wf)),
    )  # fmt: skip


# ---------------------------------------------------------------- atmosphere and inlet (M03/M06 role)
def isa(alt_m, dT_isa):
    """USSA-76 troposphere + isothermal layer to 20 km (static T [K], p [Pa]); dT_isa shifts T only."""
    t_std = np.where(alt_m <= 11000.0, T0 - 0.0065 * alt_m, 216.65)
    p = np.where(
        alt_m <= 11000.0,
        P0 * (np.minimum(t_std, T0) / T0) ** 5.255877,
        22632.06 * np.exp(-(alt_m - 11000.0) / 6341.62),
    )
    return t_std + dT_isa, p


def inlet(alt_m, mach, dT_isa):
    ts, ps = isa(alt_m, dT_isa)
    f = 1.0 + 0.2 * mach**2
    return ts * f, ps * f**3.5  # T2, P2 (ideal recovery)


# ---------------------------------------------------------------- mission inputs (keyed, block-evaluable)
def _waypoints_sortie(g: np.random.Generator):
    """One sortie-hour: ground idle, take-off, climb, cruise, combat slams, descent, pattern, taxi."""
    t, pla, alt, mach = [0.0], [18.0], [0.0], [0.0]

    def go(dt_ramp, dwell, p, a, m):
        t.append(t[-1] + dt_ramp)
        pla.append(p)
        alt.append(a)
        mach.append(m)
        t.append(t[-1] + dwell)
        pla.append(p)
        alt.append(a)
        mach.append(m)

    go(0.1, 120.0, 18.0, 0.0, 0.0)  # ground idle
    go(1.0, 40.0, 87.0, 300.0, 0.45)  # take-off at MIL
    go(2.0, 360.0, 80.0, 8000.0, 0.8)  # climb
    for _ in range(12):  # cruise with small throttle trims
        go(1.0, float(g.uniform(40, 100)), float(g.uniform(55, 68)), 8000.0, 0.8)
    while t[-1] < 2600.0:  # combat: slams between flight idle and max
        p = float(g.choice([22.0, 60.0, 87.0, 110.0, 130.0]))
        rate = float(g.uniform(60.0, 150.0))
        go(abs(p - pla[-1]) / rate + 0.05, float(g.uniform(3.0, 20.0)), p, float(g.uniform(3000, 8000)),
           float(g.uniform(0.5, 0.9)))  # fmt: skip
    go(2.0, 500.0, 25.0, 1000.0, 0.45)  # descent
    while t[-1] < 3480.0:  # pattern
        go(1.0, float(g.uniform(10, 30)), float(g.uniform(45, 75)), 300.0, 0.3)
    go(2.0, 300.0, 18.0, 0.0, 0.0)  # landing, taxi
    return np.array(t), np.array(pla), np.array(alt), np.array(mach)


def _waypoints_combat(g: np.random.Generator, horizon_s: float):
    """Slams at a fixed flight condition drawn per unit (batch workload)."""
    a, m = float(g.uniform(0.0, 8000.0)), float(g.uniform(0.3, 0.9))
    t, pla = [0.0], [float(g.uniform(30.0, 70.0))]
    while t[-1] < horizon_s + 30.0:
        p = float(g.choice([22.0, 45.0, 60.0, 75.0, 87.0, 110.0, 130.0]))
        rate = float(g.uniform(60.0, 150.0))
        t.append(t[-1] + abs(p - pla[-1]) / rate + 0.05)
        pla.append(p)
        t.append(t[-1] + float(g.uniform(2.0, 12.0)))
        pla.append(p)
    n = len(t)
    return np.array(t), np.array(pla), np.full(n, a), np.full(n, m)


class Mission(NamedTuple):
    t: np.ndarray
    pla: np.ndarray
    alt: np.ndarray
    mach: np.ndarray
    dT_isa: float


def make_mission(gen: np.random.Generator, kind: str, horizon_s: float) -> Mission:
    dT = float(gen.uniform(-15.0, 35.0))  # [ASSUMPTION] base climate span -28..49.9 C (report l.289)
    if kind == "sortie":
        wp = _waypoints_sortie(gen)
    elif kind == "combat":
        wp = _waypoints_combat(gen, horizon_s)
    else:
        raise ValueError(kind)
    return Mission(*wp, dT)


def mission_inputs(m: Mission, k0: int, n: int) -> np.ndarray:
    """Inputs for truth steps k0..k0+n-1 (block-addressable: depends only on the step indices)."""
    tk = np.arange(k0, k0 + n, dtype=np.int64) / TRUTH_HZ
    pla = np.interp(tk, m.t, m.pla)
    alt = np.interp(tk, m.t, m.alt)
    mach = np.interp(tk, m.t, m.mach)
    t2, p2 = inlet(alt, mach, m.dT_isa)
    out = np.empty((n, 3))
    out[:, I_PLA], out[:, I_T2], out[:, I_P2] = pla, t2, p2
    return out


# ---------------------------------------------------------------- initial state (steady relations)
def initial_state(inp0: np.ndarray, health: np.ndarray, P: np.ndarray, tables: Tables):
    """Near-steady state for the first input row of each unit (computed in NumPy; shared by all backends).

    inp0 float64[U, 3]; health float64[U, 2]. Returns X float64[U, NX], S int64[U, NS].
    """
    U = inp0.shape[0]
    th = inp0[:, I_T2] / T0
    dl = inp0[:, I_P2] / P0
    sth = np.sqrt(th)
    n2 = np.interp(inp0[:, I_PLA], tables.pla_x, tables.pla_y)
    eta_hp, eta_lp = health[:, 0], health[:, 1]
    wfc_ = wf_ss(n2) / eta_hp
    X = np.zeros((U, NX))
    X[:, N2] = n2 * sth * P[P_OMEGA2_100]
    X[:, N1] = n1_ss(n2 * eta_lp) * sth * P[P_OMEGA1_100]
    X[:, WF] = wfc_ * dl * sth
    X[:, PS3] = inp0[:, I_P2] * psr_line(n2)
    X[:, T5] = th ** P[P_A_EXP] * t5c_fn(n2, wf_ss(n2))
    X[:, TM] = X[:, T5]
    X[:, XI] = X[:, WF]
    X[:, WFC] = X[:, WF]
    S = np.zeros((U, NS), dtype=np.int64)
    return X, S


def draw_health(gen: np.random.Generator) -> np.ndarray:
    """[ASSUMPTION] AD-07 proxy: fuel-efficiency delta SD 3.8 % (round-2 e-SD); fan/core match SD 0.5 %."""
    e = float(np.clip(gen.normal(0.0, 0.038), -0.1, 0.1))
    m = float(np.clip(gen.normal(0.0, 0.005), -0.02, 0.02))
    return np.array([1.0 + e, 1.0 + m])
