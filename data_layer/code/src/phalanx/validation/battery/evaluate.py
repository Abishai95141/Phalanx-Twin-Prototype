"""Group distances, joint flight bootstrap, verdicts and the decision rule (port of round-2
`battery_eval.py`).

A *group* is a list of per-flight `FlightStats` aligned with a flight list (None = flight missing). A
*comparison* is (group A, group B, paired?). Bootstrap draws are made per underlying flight list (the draw
key), so every comparison that involves the same flights (e.g. the real holdout in D_sim and in D_tail) uses
the same resample: the distribution of D_sim - D_tail is a joint bootstrap (DEVIATIONS.md D4).

Distances (smaller = better; pre-registration section 4):
  B1_fast (primary), B1_slow, B1h_fast / B1h_slow (0.5 Hz sensitivity): mean |median_A - median_B| over pairs
  B2: mean |delta flight-median lag| over the (pair, engine) cells
  B3i: mean |delta ln gain| + mean |delta coherence| over (engine, pair, band) cells (flight medians)
  B3ii: mean |ln(tau_A / tau_B)| over (N1, FF, EGT) x (accel, decel) cells (pooled-step medians, >= 3 steps)
  B4: mean |delta median log F| over the 12 directed pairs
  B5i: |scatter_A - scatter_B| / scatter_real; B5ii: |a_A - a_B|
  B6: mean |delta| / real per-phase IQR
Verdict (section 5): PASS if D_sim <= D_tail; FAIL if the one-sided 95 % bootstrap lower bound of
D_sim - D_tail is > 0; otherwise INCONCLUSIVE; STRICT PASS when D_sim <= D_temp. Multi-part tests (B3, B5)
pass iff every part passes and fail iff any part fails (DEVIATIONS.md D1).
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from phalanx.core.rng import KeyPath, RngService, StreamDecl, Variate
from phalanx.validation.battery.config import (
    A_GRID,
    N_BOOT,
    STEP_DIRS,
    STEP_MIN_PER_CELL,
    STEP_RESP,
    TESTS,
    VERDICT_TESTS,
)
from phalanx.validation.battery.stats import B5Moments, FlightStats

__all__ = [
    "BOOTSTRAP_STREAM",
    "ROUND2_ROOT_SEED",
    "Bootstrap",
    "Comparison",
    "Distance",
    "PartResult",
    "TestResult",
    "b5_group",
    "b6_distance",
    "choose_better_arm",
    "compare",
    "decision",
    "group_values",
    "n_with",
    "stat_value",
    "summarise",
    "verdicts",
]

#: Round-2 bootstrap root seed (pre-registration section 7).
# `Bootstrap(np.random.SeedSequence(ROUND2_ROOT_SEED))`
#: reproduces round-2's `np.random.default_rng(20261015)` draws exactly.
ROUND2_ROOT_SEED = 20261015
LN10 = np.log(10.0)
_KEY = {
    "B1_fast": "b1_fast",
    "B1_slow": "b1_slow",
    "B1h_fast": "b1h_fast",
    "B1h_slow": "b1h_slow",
    "B2": "b2",
    "B4": "b4",
    "B6": "b6",
}
_NEEDS = {**_KEY, "B3i": "b3_coh", "B3ii": "b3_steps", "B5i": "b5_ff", "B5ii": "b5_ff"}

Group = Sequence[FlightStats | None]


def _has(s: FlightStats | None, k: str) -> bool:
    return s is not None and s.has(k)


def _med_abs(A: np.ndarray, Bm: np.ndarray) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN cells (e.g. missing bands) stay NaN
        return float(np.nanmean(np.abs(np.nanmedian(A, 0) - np.nanmedian(Bm, 0))))


# ---------------------------------------------------------------- B5 / B6 group statistics
def _seqsum(values: Iterable[Any]) -> Any:
    """Plain left-to-right sum. Not the builtin `sum`: since Python 3.12 it uses compensated (Neumaier)
    summation for floats, while round 2 summed numpy 0-d arrays with plain `+`; the two differ at ~1e-11."""
    it = iter(values)
    acc = next(it)
    for v in it:
        acc = acc + v
    return acc


def b5_group(mlist: Sequence[tuple[B5Moments, B5Moments]]) -> tuple[float, float]:
    """(relative RMS scatter of corrected FF, fitted EGT exponent a) from per-flight moments."""
    XtX = _seqsum(m[0].XtX for m in mlist)
    Xty = _seqsum(m[0].Xty for m in mlist)
    yy = _seqsum(m[0].yy for m in mlist)
    sy = _seqsum(m[0].sy for m in mlist)
    n = _seqsum(m[0].n for m in mlist)
    beta = np.linalg.solve(XtX, Xty)
    rss = max(yy - beta @ Xty, 0.0)
    scatter = np.sqrt(rss / n) / (sy / n)
    XtX = _seqsum(m[1].XtX for m in mlist)
    Xty = _seqsum(m[1].Xty for m in mlist)
    yy = _seqsum(m[1].yy for m in mlist)
    sy = _seqsum(m[1].sy for m in mlist)
    n = _seqsum(m[1].n for m in mlist)
    Xinv = np.linalg.inv(XtX)
    rel = []
    for j in range(A_GRID.size):
        b = Xinv @ Xty[j]
        r = max(yy[j] - b @ Xty[j], 0.0)
        rel.append(np.sqrt(r / n) / (sy[j] / n))
    a = float(A_GRID[int(np.argmin(rel))])
    return float(scatter), a


def b6_distance(A: np.ndarray, Bm: np.ndarray, real: np.ndarray | None = None) -> float:
    """A, Bm: (n_flights, phases, channels, 3). D = mean |median_A - median_B| / real per-phase IQR."""
    real = Bm if real is None else real
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # phases missing in every flight stay NaN
        gA, gB = np.nanmedian(A, 0), np.nanmedian(Bm, 0)
        iqr = np.nanmedian(real[..., 1], 0)
        den = np.where(iqr > 0, iqr, np.nan)[..., None]
        v = np.abs(gA - gB) / den
        return float(np.nanmean(v))


def _b5m(s: FlightStats) -> tuple[B5Moments, B5Moments]:
    assert s.b5_ff is not None and s.b5_egt is not None
    return s.b5_ff, s.b5_egt


def _taus(S: Group) -> np.ndarray:
    st = [s.b3_steps for s in S if s is not None and s.b3_steps is not None]
    st = np.vstack(st) if st else np.zeros((0, 3))
    out = []
    for r in range(len(STEP_RESP)):
        for d in range(len(STEP_DIRS)):
            v = st[(st[:, 0] == r) & (st[:, 1] == d), 2]
            out.append(np.median(v) if v.size >= STEP_MIN_PER_CELL else np.nan)
    return np.array(out)


def stat_value(test: str, SA: Group, SB: Group, real_is_B: bool = True) -> float:
    """Distance for one test part between two groups (already restricted / resampled). NaN if < 2 flights."""
    if test in _KEY and test != "B6":
        k = _KEY[test]
        A = np.array([s.get(k) for s in SA if _has(s, k)])
        Bm = np.array([s.get(k) for s in SB if _has(s, k)])
        if len(A) < 2 or len(Bm) < 2:
            return np.nan
        return _med_abs(A, Bm)
    if test == "B6":
        A = np.array([s.b6 for s in SA if _has(s, "b6")])
        Bm = np.array([s.b6 for s in SB if _has(s, "b6")])
        if len(A) < 2 or len(Bm) < 2:
            return np.nan
        return b6_distance(A, Bm, real=Bm if real_is_B else A)
    if test == "B3i":
        cA = np.array([s.b3_coh for s in SA if _has(s, "b3_coh")])
        cB = np.array([s.b3_coh for s in SB if _has(s, "b3_coh")])
        gA = np.array([s.b3_lgain for s in SA if _has(s, "b3_lgain")]) * LN10
        gB = np.array([s.b3_lgain for s in SB if _has(s, "b3_lgain")]) * LN10
        if len(cA) < 2 or len(cB) < 2:
            return np.nan
        return _med_abs(gA, gB) + _med_abs(cA, cB)
    if test == "B3ii":
        tA, tB = _taus(SA), _taus(SB)
        with np.errstate(invalid="ignore", divide="ignore"):
            v = np.abs(np.log(tA / tB))
        return float(np.nanmean(v)) if np.isfinite(v).any() else np.nan
    if test in ("B5i", "B5ii"):
        MA_ = [_b5m(s) for s in SA if s is not None and s.b5_ff is not None]
        MB_ = [_b5m(s) for s in SB if s is not None and s.b5_ff is not None]
        if len(MA_) < 2 or len(MB_) < 2:
            return np.nan
        sa, aa = b5_group(MA_)
        sb, ab = b5_group(MB_)
        if test == "B5i":
            real = sb if real_is_B else sa
            return float(abs(sa - sb) / real)
        return float(abs(aa - ab))
    raise ValueError(test)


def n_with(test: str, S: Group) -> int:
    """Number of flights of a group that carry the statistic behind a test part."""
    k = _NEEDS[test]
    return int(sum(_has(s, k) for s in S))


def group_values(S: Group) -> dict[str, object]:
    """Descriptive group values (round-2 report tables): B5 scatter and exponent, lags, taus, medians."""
    out: dict[str, object] = {}
    M = [_b5m(s) for s in S if s is not None and s.b5_ff is not None]
    if len(M) >= 2:
        out["B5_scatter"], out["B5_a"] = b5_group(M)
    b2 = np.array([s.b2 for s in S if _has(s, "b2")])
    if len(b2):
        out["B2_median_lags"] = np.median(b2, 0).tolist()
    b1 = np.array([s.b1_fast for s in S if _has(s, "b1_fast")])
    if len(b1):
        out["B1_fast_median"] = np.median(b1, 0).tolist()
    b1s = np.array([s.b1_slow for s in S if _has(s, "b1_slow")])
    if len(b1s):
        out["B1_slow_median"] = np.median(b1s, 0).tolist()
    st = [s.b3_steps for s in S if s is not None and s.b3_steps is not None]
    st = np.vstack(st) if st else np.zeros((0, 3))
    taus: dict[str, float | None] = {}
    for r, g in enumerate(STEP_RESP):
        for di, d in enumerate(STEP_DIRS):
            m = (st[:, 0] == r) & (st[:, 1] == di)
            taus[f"{g}_{d}"] = float(np.median(st[m, 2])) if np.sum(m) >= STEP_MIN_PER_CELL else None
    out["B3ii_median_tau"] = taus
    out["B3ii_n_steps"] = int(st.shape[0])
    b4 = np.array([s.b4 for s in S if _has(s, "b4")])
    if len(b4):
        out["B4_median_logF"] = np.nanmedian(b4, 0).tolist()
    out["air_frac_median"] = float(np.median([s.air_frac for s in S if s is not None]))
    out["n_flights"] = int(sum(s is not None for s in S))
    return out


# ---------------------------------------------------------------- bootstrap
#: Declared stream of the battery bootstrap in build runs (add it to the run's StreamRegistry).
BOOTSTRAP_STREAM = StreamDecl(
    subsystem="validation",
    component="bootstrap",
    identity=("scenario",),
    variate=Variate.GENERATOR,
    block_size=1,
    owner="M20 validation harness (W0.5)",
    description="flight-bootstrap resamples of one battery run; one generator per run index in a campaign",
)


class Bootstrap:
    """Flight-bootstrap index sets per draw key, shared across comparisons (joint bootstrap).

    Draws for a key are generated on first request, in request order, so the order of `compare` calls is part
    of the protocol: round 2 asks for "partner", "holdout", "late", "early", then reuses "holdout" for every
    paired D_sim. Construct with:
    - `Bootstrap.from_service(rng, scenario, nb)` in build runs (`phalanx.core.rng`, stream BOOTSTRAP_STREAM);
    - `Bootstrap(np.random.SeedSequence(20261015), nb)` to reproduce round 2 exactly (PCG64, its rule).
    """

    def __init__(self, seed_seq: np.random.SeedSequence, nb: int = N_BOOT) -> None:
        self._init(
            np.random.Generator(np.random.PCG64(seed_seq)),
            nb,
            {
                "mode": "round2_compat",
                "bit_generator": "PCG64",
                "entropy": _jsonable(seed_seq.entropy),
                "spawn_key": [int(k) for k in seed_seq.spawn_key],
            },
        )

    def _init(self, gen: np.random.Generator, nb: int, source: dict[str, object]) -> None:
        self._rng = gen
        self.nb = int(nb)
        self.draws: dict[str, list[np.ndarray]] = {}
        self.source = source

    @classmethod
    def from_service(cls, rng: RngService, scenario: str, nb: int = N_BOOT, index: int = 0) -> Bootstrap:
        """Bootstrap from the declared `validation.bootstrap` stream of a build run (identity-keyed)."""
        path = KeyPath.of(
            scenario=scenario, subsystem=BOOTSTRAP_STREAM.subsystem, component=BOOTSTRAP_STREAM.component
        )
        self = cls.__new__(cls)
        self._init(
            rng.generator(path, index),
            nb,
            {"mode": "phalanx.core.rng", **rng.describe(), "path": path.canonical(), "index": int(index)},
        )
        return self

    def get(self, key: str, n: int) -> list[np.ndarray]:
        if key not in self.draws:
            self.draws[key] = [self._rng.integers(0, n, n) for _ in range(self.nb)]
        draws = self.draws[key]
        if draws and draws[0].size != n:
            raise ValueError(f"draw key {key!r} was created for {draws[0].size} flights, asked for {n}")
        return draws


@dataclass(frozen=True, eq=False)
class Distance:
    """Point distance and its flight-bootstrap distribution for one test part."""

    D: float
    boot: np.ndarray = field(repr=False)
    n_a: int = 0
    n_b: int = 0

    @property
    def ci95(self) -> tuple[float, float]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN bootstrap -> NaN CI
            return (float(np.nanpercentile(self.boot, 2.5)), float(np.nanpercentile(self.boot, 97.5)))


Comparison = dict[str, Distance]


def compare(
    SA: Group,
    SB: Group,
    keyA: str,
    keyB: str,
    paired: bool,
    boot: Bootstrap,
    tests: Sequence[str] = TESTS,
    real_is_B: bool = True,
) -> Comparison:
    """Point distances and bootstrap distributions for every test part. SA/SB aligned with their flight lists.

    Paired comparisons (two versions of the same flights) use only flights where both versions exist and
    resample flight pairs; unpaired comparisons resample each group with its own draw key.
    """
    if paired and len(SA) != len(SB):
        raise ValueError("paired comparison needs aligned groups of equal length")
    dA = boot.get(keyA, len(SA))
    dB = dA if paired else boot.get(keyB, len(SB))
    out: Comparison = {}
    for t in tests:
        if paired:
            ok = [i for i in range(len(SA)) if SA[i] is not None and SB[i] is not None]
            A0, B0 = [SA[i] for i in ok], [SB[i] for i in ok]
        else:
            A0, B0 = list(SA), list(SB)
        d0 = stat_value(t, A0, B0, real_is_B)
        bs = np.empty(boot.nb)
        for b in range(boot.nb):
            ia, ib = dA[b], dB[b]
            if paired:
                sel = [i for i in ia if SA[i] is not None and SB[i] is not None]
                bs[b] = stat_value(t, [SA[i] for i in sel], [SB[i] for i in sel], real_is_B)
            else:
                bs[b] = stat_value(t, [SA[i] for i in ia], [SB[i] for i in ib], real_is_B)
        out[t] = Distance(D=d0, boot=bs, n_a=n_with(t, A0), n_b=n_with(t, B0))
    return out


# ---------------------------------------------------------------- verdicts
@dataclass(frozen=True)
class PartResult:
    """Verdict of one distance part against the real-vs-real bars."""

    part: str
    D_sim: float
    D_tail: float
    D_temp: float | None
    lb95_one_sided_Dsim_minus_Dtail: float
    verdict: str
    strict_pass: bool | None
    D_sim_ci95: tuple[float, float]
    D_tail_ci95: tuple[float, float]
    n_flights: Mapping[str, int]


@dataclass(frozen=True)
class TestResult:
    """Verdict of one battery test (B1..B6); multi-part tests combine their parts (DEVIATIONS.md D1)."""

    __test__ = False  # not a pytest test class

    test: str
    verdict: str
    strict_pass: bool | None
    parts: Mapping[str, PartResult]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def verdicts(sim: Comparison, tail: Comparison, temp: Comparison | None = None) -> dict[str, TestResult]:
    """Per-test verdicts from `compare` outputs made with one Bootstrap object (joint distribution)."""
    res: dict[str, TestResult] = {}
    for test, parts in VERDICT_TESTS.items():
        pv: dict[str, PartResult] = {}
        for p in parts:
            ds, dt = sim[p].D, tail[p].D
            diff = sim[p].boot - tail[p].boot
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN difference -> NaN bound
                lb = float(np.nanpercentile(diff, 5))
            if np.isfinite(ds) and np.isfinite(dt) and ds <= dt:
                v = "PASS"
            elif lb > 0:
                v = "FAIL"
            else:
                v = "INCONCLUSIVE"
            strict = None
            if temp is not None and np.isfinite(temp[p].D):
                strict = bool(ds <= temp[p].D)
            n = {"sim": sim[p].n_a, "real": sim[p].n_b, "tail_partner": tail[p].n_a, "tail_real": tail[p].n_b}
            if temp is not None:
                n.update(temp_late=temp[p].n_a, temp_early=temp[p].n_b)
            pv[p] = PartResult(
                part=p,
                D_sim=ds,
                D_tail=dt,
                D_temp=(temp[p].D if temp is not None else None),
                lb95_one_sided_Dsim_minus_Dtail=lb,
                verdict=v,
                strict_pass=strict,
                D_sim_ci95=sim[p].ci95,
                D_tail_ci95=tail[p].ci95,
                n_flights=n,
            )
        vs = [pv[p].verdict for p in parts]
        if all(v == "PASS" for v in vs):
            overall = "PASS"
        elif any(v == "FAIL" for v in vs):
            overall = "FAIL"
        else:
            overall = "INCONCLUSIVE"
        sp = [pv[p].strict_pass for p in parts]
        strict_all = all(sp) if all(s is not None for s in sp) else None
        res[test] = TestResult(test=test, verdict=overall, strict_pass=strict_all, parts=pv)
    return res


def decision(ver: Mapping[str, TestResult], g0_pass: bool) -> dict[str, object]:
    """Pre-registered overall decision (section 5) for one arm."""
    n_pass = sum(v.verdict == "PASS" for v in ver.values())
    fails = [t for t, v in ver.items() if v.verdict == "FAIL"]
    if not g0_pass:
        return {"decision": "REWORK (G0 failed)", "n_pass": n_pass, "fails": fails}
    if not fails and n_pass >= 4:
        return {"decision": "GO", "n_pass": n_pass, "fails": fails}
    if fails:
        return {
            "decision": "GO WITH FIXES or REWORK (depends on module attribution of the FAILs; see report)",
            "n_pass": n_pass,
            "fails": fails,
        }
    return {"decision": "NOT GO (fewer than 4 PASS, no FAIL)", "n_pass": n_pass, "fails": fails}


def choose_better_arm(arms: Mapping[str, Mapping[str, TestResult]]) -> list[tuple[str, int, int, float]]:
    """Rank arms as round 2 (`run_holdout.choose`): more PASS, then fewer FAIL, then smaller mean
    D_sim/D_tail.

    Returns [(arm, n_pass, n_fail, mean ratio)] best first.
    """
    cands = []
    for arm, ver in arms.items():
        npass = sum(x.verdict == "PASS" for x in ver.values())
        nfail = sum(x.verdict == "FAIL" for x in ver.values())
        ratio = float(
            np.nanmean(
                [
                    p.D_sim / p.D_tail
                    for x in ver.values()
                    for p in x.parts.values()
                    if p.D_tail and np.isfinite(p.D_tail) and p.D_tail > 0
                ]
            )
        )
        cands.append((-npass, nfail, ratio, arm))
    cands.sort()
    return [(c[3], -c[0], c[1], c[2]) for c in cands]


def summarise(cmp: Comparison) -> dict[str, dict[str, object]]:
    """{part: {"D", "ci95", "n_a", "n_b"}} for a comparison (JSON-ready)."""
    return {t: {"D": v.D, "ci95": list(v.ci95), "n_a": v.n_a, "n_b": v.n_b} for t, v in cmp.items()}


def _jsonable(x: object) -> object:
    if isinstance(x, np.ndarray):
        return [int(v) for v in x.tolist()]
    if isinstance(x, (list, tuple)):
        return [int(v) for v in x]
    return int(x) if isinstance(x, (int, np.integer)) else x
