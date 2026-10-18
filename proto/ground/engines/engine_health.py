"""Engine health from the generated engine trend (overlay v0.1) — DEVELOPMENT.md §2.5 row ``engine_health``.

Input: overlay ``param.samples`` takeoff snapshots (ENG.T5 EGT, ENG.T1 inlet temperature) read through the as-of
store (``t_ingest ≤ t``, deduplicated, SENTINEL / non-NORMAL masked); SORTIE records for engine flight hours
(EFH) and engine serial; INSPECTION / WASH records (CLOSED) as known change points.

Method, per engine serial (keyed ``tail_no`` + ``engine_serial``; health follows the serial):

1. Snapshot: median of the valid takeoff samples; samples at the top of the EGT scale are dropped (unflagged
   saturation glitch), and a snapshot identical to the previous one on every channel is dropped (frozen).
2. Corrected EGT = (EGT + 273.15) / θ^0.5 − 273.15, θ = (T1 + 273.15) / 288.15; margin = 830 °C − corrected EGT
   (830 °C = dictionary ``ENG.T5`` steady max).
3. Kalman filter, local linear trend in EFH: state (margin level, slope per EFH). A wash inflates the level
   variance (known change point, so the recovery is not an alarm).
4. One-sided CUSUM on standardised innovations (margin falling faster than predicted): step alert at h = 5,
   k = 0.5; innovations beyond 5 σ are held as outliers unless the next one confirms them.
5. Days to limit: Monte Carlo over the (level, slope) posterior, EFH to margin 0 converted at the engine's
   flying rate over the last 30 days; the 10th percentile is reported.

Every output is a ``Belief`` with ``Source.OVERLAY`` — "Generated engine trend (overlay v0.1)": it shows that
the pipeline finds what was planted in generated data, not that it would detect real engine faults.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from interfaces import DAY, NS, SOURCE_LABEL, Belief, Finding, Source, Tier

MODEL_ID = "engine_health"
MODEL_VERSION = "0.1.0"
LABEL = SOURCE_LABEL[Source.OVERLAY]
REDLINE_C = 830.0
EGT_TOP = 871.0  # top of the ENG.T5 range: saturated, not a measurement
TAKEOFF_WINDOW_NS = 60 * NS

# filter and detector settings: set by hand before any evaluation run; not tuned on the evaluated data
R_MEAS = 5.0  # snapshot measurement variance, degC^2
Q_LEVEL = 0.05  # level random walk per EFH, degC^2
Q_SLOPE = 2e-4  # slope random walk per EFH, (degC/EFH)^2
SLOPE0, P_SLOPE0 = -0.2, 0.1**2
P_LEVEL0 = 25.0
WASH_VAR = 36.0  # level variance added at a wash (known change point)
CUSUM_K, CUSUM_H = 0.5, 5.0
OUTLIER_Z = 5.0
TREND_ALERT_DAYS = 90.0  # alert when the 10th-percentile days to limit falls below this
MARGIN_ALERT_C = 10.0  # alert when the filtered margin falls below this
DAYS_CAP = 3650.0
N_DRAWS = 4000


@dataclass
class Step:
    """Filter output after one snapshot (as of that snapshot's ingest)."""

    tail_no: str
    engine_serial: str
    sortie_id: str
    t_open: int
    t_ingest: int
    efh: float
    margin_obs: float | None
    level: float
    slope: float
    p: np.ndarray
    z: float | None
    cusum: float
    step_alert: bool
    trend_alert: bool
    days_p10: float
    used: bool
    note: str = ""
    evidence: tuple[bytes, ...] = field(default=())


def snapshots(store, t: int, *, source: Source = Source.OVERLAY, world_seed: int | None = None) -> pd.DataFrame:
    """One row per (tail_no, sortie_id) takeoff snapshot ingested by ``t``: EGT, T1, corrected margin, EFH."""
    ps = store.df(t, "param.samples", source=source, world_seed=world_seed)
    if not len(ps):
        return pd.DataFrame()
    ps = ps[ps.param_id.isin(["ENG.T5", "ENG.T1", "ENG.N2", "ENG.WFM"])]
    first = ps.groupby(["tail_no", "sortie_id"]).t_sample.transform("min")
    to = ps[ps.t_sample <= first + TAKEOFF_WINDOW_NS].copy()
    to.loc[(to.param_id == "ENG.T5") & (to.value_eu >= EGT_TOP), "value_eu"] = np.nan
    med = to.pivot_table(index=["tail_no", "sortie_id", "engine_serial"], columns="param_id", values="value_eu",
                         aggfunc="median")
    ev = to.groupby(["tail_no", "sortie_id"]).record_id.agg(lambda s: tuple(bytes(x) for x in s))
    ing = to.groupby(["tail_no", "sortie_id"]).t_ingest.min()
    snap = med.reset_index()
    snap["evidence"] = [ev.get((a, b), ()) for a, b in zip(snap.tail_no, snap.sortie_id, strict=True)]
    snap["t_ingest"] = [int(ing[(a, b)]) for a, b in zip(snap.tail_no, snap.sortie_id, strict=True)]
    for c in ("ENG.T5", "ENG.T1", "ENG.N2", "ENG.WFM"):
        if c not in snap:
            snap[c] = np.nan
    th = (snap["ENG.T1"] + 273.15) / 288.15
    snap["margin_obs"] = REDLINE_C - ((snap["ENG.T5"] + 273.15) / np.sqrt(th) - 273.15)
    # engine flight hours and takeoff time from the SORTIE records
    so = store.maint_latest(t, ["SORTIE"], source=Source.FLEET if source == Source.OVERLAY else source,
                            world_seed=world_seed)
    so = so[["tail_no", "sortie_id", "engine_serial", "flight_hours", "t_open"]].dropna(subset=["t_open"])
    so = so.sort_values(["tail_no", "engine_serial", "t_open"], kind="mergesort")
    so["efh_before"] = so.groupby(["tail_no", "engine_serial"]).flight_hours.transform(
        lambda s: s.fillna(0).cumsum().shift(fill_value=0.0))
    snap = snap.merge(so.drop(columns=["engine_serial"]), on=["tail_no", "sortie_id"], how="inner")
    return snap.sort_values(["tail_no", "engine_serial", "t_open"], kind="mergesort").reset_index(drop=True)


def _washes(store, t: int, *, world_seed: int | None, source: Source) -> dict[str, list[int]]:
    src = Source.FLEET if source == Source.OVERLAY else source
    m = store.maint_latest(t, ["INSPECTION"], source=src, world_seed=world_seed)
    if not len(m):
        return {}
    w = m[(m.inspection_type == "WASH") & (m.status == "CLOSED") & m.t_close.notna()]
    return {k: sorted(int(x) for x in g.t_close) for k, g in w.groupby("tail_no")}


def _sorties_efh(store, t: int, *, world_seed: int | None, source: Source) -> pd.DataFrame:
    src = Source.FLEET if source == Source.OVERLAY else source
    so = store.maint_latest(t, ["SORTIE"], source=src, world_seed=world_seed)
    return so[["tail_no", "engine_serial", "flight_hours", "t_open"]].dropna(subset=["t_open"])


def _seed(*parts: str) -> int:
    """Deterministic Monte Carlo seed (builtin ``hash`` is salted per process)."""
    return int.from_bytes(hashlib.blake2b("|".join(parts).encode(), digest_size=8).digest(), "little")


def _days_p10(level: float, slope: float, p: np.ndarray, efh_per_day: float, seed: int) -> float:
    g = np.random.default_rng(seed)
    try:
        d = g.multivariate_normal([level, slope], p, size=N_DRAWS, method="cholesky")
    except np.linalg.LinAlgError:
        d = g.multivariate_normal([level, slope], p + np.eye(2) * 1e-9, size=N_DRAWS)
    lv, sl = d[:, 0], d[:, 1]
    efh = np.where(lv <= 0, 0.0, np.where(sl < 0, lv / np.maximum(-sl, 1e-9), np.inf))
    days = efh / max(efh_per_day, 1e-6)
    return float(min(np.quantile(days, 0.10), DAYS_CAP))


def track(snaps: pd.DataFrame, washes: dict[str, list[int]], sorties: pd.DataFrame) -> list[Step]:
    """Run the filter over every engine's snapshots in takeoff order."""
    out: list[Step] = []
    for (tail, ser), g in snaps.groupby(["tail_no", "engine_serial"], sort=True):
        so = sorties[(sorties.tail_no == tail) & (sorties.engine_serial == ser)]
        x = p = None
        prev_efh, prev_t, cusum, pend = 0.0, None, 0.0, None
        prev_vals = None
        for r in g.itertuples(index=False):
            row = r._asdict()
            vals = tuple(row.get(k) for k in row if k.startswith("ENG"))
            frozen = prev_vals is not None and all(
                (a == b) or (pd.isna(a) and pd.isna(b)) for a, b in zip(vals, prev_vals, strict=True))
            prev_vals = vals
            z_obs = row["margin_obs"]
            efh = float(row["efh_before"])
            note = ""
            # 30-day flying rate of this engine as of this takeoff
            win = so[(so.t_open < row["t_open"]) & (so.t_open >= row["t_open"] - 30 * DAY)]
            rate = float(win.flight_hours.fillna(0).sum()) / 30.0
            if rate <= 0:
                past = so[so.t_open < row["t_open"]]
                span = max((row["t_open"] - past.t_open.min()) / DAY, 1.0) if len(past) else 1.0
                rate = float(past.flight_hours.fillna(0).sum()) / span if len(past) else 0.3
            if x is None:
                if pd.isna(z_obs) or frozen:
                    continue
                x = np.array([z_obs, SLOPE0])
                p = np.diag([P_LEVEL0, P_SLOPE0])
                prev_efh, prev_t = efh, row["t_open"]
                out.append(Step(tail, ser, row["sortie_id"], int(row["t_open"]), int(row["t_ingest"]), efh, z_obs,
                                x[0], x[1], p.copy(), None, 0.0, False, False,
                                _days_p10(x[0], x[1], p, rate, _seed(tail, ser, row["sortie_id"])),
                                True, "initialised", row["evidence"]))
                continue
            d = max(efh - prev_efh, 0.0)
            f = np.array([[1.0, d], [0.0, 1.0]])
            q = np.array([[Q_LEVEL * d + Q_SLOPE * d**3 / 3, Q_SLOPE * d**2 / 2], [Q_SLOPE * d**2 / 2, Q_SLOPE * d]])
            x = f @ x
            p = f @ p @ f.T + q
            if any(prev_t < tw <= row["t_open"] for tw in washes.get(tail, ())):
                p[0, 0] += WASH_VAR
                note = "wash (known change point)"
                cusum = 0.0
            prev_efh, prev_t = efh, row["t_open"]
            z = None
            used = False
            step_alert = False
            if frozen:
                note = (note + "; " if note else "") + "frozen snapshot dropped"
            elif pd.isna(z_obs):
                note = (note + "; " if note else "") + "no valid EGT/T1 sample"
            else:
                s = p[0, 0] + R_MEAS
                nu = z_obs - x[0]
                z = nu / math.sqrt(s)
                accept = abs(z) <= OUTLIER_Z
                if not accept and pend is not None and np.sign(pend) == np.sign(z):
                    accept = True  # two outliers in the same direction: a real step
                    note = (note + "; " if note else "") + "confirmed step"
                if accept:
                    pend = None
                    k = p[:, 0] / s
                    x = x + k * nu
                    p = p - np.outer(k, p[0, :])
                    used = True
                    cusum = max(0.0, cusum - z - CUSUM_K)
                    if cusum > CUSUM_H:
                        step_alert = True
                        cusum = 0.0
                        p[1, 1] += 0.05**2  # let the slope adapt after a detected change
                        p[0, 0] += 9.0
                else:
                    pend = z
                    note = (note + "; " if note else "") + "outlier held"
            days = _days_p10(x[0], x[1], p, rate, _seed(tail, ser, row["sortie_id"]))
            trend_alert = days < TREND_ALERT_DAYS or x[0] < MARGIN_ALERT_C
            out.append(Step(tail, ser, row["sortie_id"], int(row["t_open"]), int(row["t_ingest"]), efh, z_obs,
                            float(x[0]), float(x[1]), p.copy(), z, cusum, step_alert, trend_alert, days, used, note,
                            row["evidence"]))
    return out


def run_tracks(store, t: int, *, source: Source = Source.OVERLAY, world_seed: int | None = None) -> list[Step]:
    snaps = snapshots(store, t, source=source, world_seed=world_seed)
    if not len(snaps):
        return []
    snaps = snaps.rename(columns={c: c.replace(".", "_") for c in snaps.columns if c.startswith("ENG.")})
    return track(snaps, _washes(store, t, world_seed=world_seed, source=source),
                 _sorties_efh(store, t, world_seed=world_seed, source=source))


def _beliefs(s: Step, last_step_alert: Step | None) -> tuple[Belief, ...]:
    sd = math.sqrt(max(s.p[0, 0], 0.0))
    sl_sd = math.sqrt(max(s.p[1, 1], 0.0))
    common = dict(model_id=MODEL_ID, model_version=MODEL_VERSION, source=Source.OVERLAY)
    return (
        Belief("egt_margin_c", s.level, s.level - 1.2816 * sd, s.level + 1.2816 * sd, None,
               note=f"{LABEL}; filtered takeoff EGT margin to 830 °C, 80 % interval", **common),
        Belief("egt_margin_trend_c_per_10efh", 10 * s.slope, 10 * (s.slope - 1.2816 * sl_sd),
               10 * (s.slope + 1.2816 * sl_sd), None, note=f"{LABEL}; 80 % interval", **common),
        Belief("days_to_margin_limit_p10", s.days_p10, None, None, None,
               note=f"{LABEL}; 10th percentile, capped at {DAYS_CAP:.0f} d, at the engine's 30-day flying rate",
               **common),
        Belief("egt_step_alert", 1.0 if last_step_alert is not None else 0.0, None, None, None,
               note=f"{LABEL}; " + (f"CUSUM step alert at sortie {last_step_alert.sortie_id}" if last_step_alert
                                    else "no CUSUM step alert"), **common),
        Belief("egt_trend_alert", 1.0 if s.trend_alert else 0.0, None, None, None,
               note=f"{LABEL}; days to limit p10 < {TREND_ALERT_DAYS:.0f} or margin < {MARGIN_ALERT_C:.0f} °C",
               **common),
    )


def assess(store, t: int, *, source: Source = Source.OVERLAY, world_seed: int | None = None) -> list[Finding]:
    """One PRED finding per engine serial with overlay data ingested by ``t`` (its latest state)."""
    steps = run_tracks(store, t, source=source, world_seed=world_seed)
    out: list[Finding] = []
    by: dict[tuple[str, str], list[Step]] = {}
    for s in steps:
        by.setdefault((s.tail_no, s.engine_serial), []).append(s)
    for (tail, ser), ss in sorted(by.items()):
        last = ss[-1]
        n = sum(1 for s in ss if s.used)
        alerts = [s for s in ss if s.step_alert]
        bel = tuple(Belief(b.name, b.value, b.lo, b.hi, n, b.model_id, b.model_version, b.source, b.note)
                    for b in _beliefs(last, alerts[-1] if alerts else None))
        reason = (f"Engine {ser} on {tail}: EGT margin {last.level:.1f} °C, trend {10 * last.slope:+.2f} °C per "
                  f"10 EFH, days to limit (p10) {last.days_p10:.0f}"
                  + ("; step alert" if alerts else "") + f" — {LABEL}.")
        out.append(Finding(MODEL_ID, Tier.PRED, tail, ser, bel, tuple(last.evidence), reason))
    return out
