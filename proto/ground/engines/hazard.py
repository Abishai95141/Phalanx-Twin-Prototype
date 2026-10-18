"""Removal risk per item class from simulated fleet history (training worlds) — DEVELOPMENT.md §2.5 row ``hazard``.

Data: ``maint.records`` of the training worlds read through the as-of store (``Source.TRAIN``, one root per world
seed). Each installation spell of a serial (``COMPONENT_LIFE`` INSTALL → REMOVE, or still fitted at the end) is one
observation:

- exposure = item operating hours between install and removal (``item_hours`` difference; the tail's SORTIE
  flight hours over the spell when either value is missing);
- event = the removal's shop finding confirmed a fault: CONFIRMED (base repair) or BCM (confirmed, beyond base
  capability), linked to the removal by job + serial + time; removals for hard-time expiry (job ``MAL-HT``),
  RTOK findings, unlinked findings and spells still fitted are censored.

Models (``HazardModel.kind``), all on every class at once with a ridge penalty on the class effects (partial pooling
to the fleet):

- ``class_exp`` — class-exposure baseline: confirmed-fault removals per flight hour of the class;
- ``age`` — Weibull accelerated-failure-time (lifelines ``WeibullAFTFitter``) on time since install, class in scale
  and shape;
- ``landmark`` — Weibull AFT on residual life at landmark ages (every 10 FH), with the spell covariates known at that
  age: age since install, class alarms in the last 10 FH (alarms whose suspects name the class's LRU), alarm rate
  since install, earlier RTOK removals of the serial on the tail, inferred-install flag.

``proto/eval/hazard_backtest.py`` picks the challenger on a validation seed and promotes it over the class-exposure
baseline only if it beats it on the held-out seed; ``hazard_model.json`` holds the champion. Classes with fewer than
10 events report ``INSUFFICIENT_EVIDENCE`` (``Belief.value`` None).

Output: ``removal_risk_30d`` = P(confirmed-fault removal within the next 30 days of flying | fitted for ``age`` FH),
with an 80 % interval from parameter draws, ``n`` = events of the class, ``Source.TRAIN`` — "Simulated fleet
history". Synthetic data: this shows the pipeline, not real reliability.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from interfaces import DAY, SOURCE_LABEL, Belief, Finding, Source, Tier
from twin import RR_TEXT, serial_ok

MODEL_ID = "hazard"
MODEL_VERSION = "0.2.0"
LABEL = SOURCE_LABEL[Source.TRAIN]
MIN_EVENTS = 10
PENALIZER = 0.1
EVENT_FINDINGS = ("CONFIRMED", "BCM")
HARD_TIME = "MAL-HT"
HORIZON_DAYS = 30
LANDMARK_STEP = 10.0
#: alarm suspect-LRU names (events.*.suspect_lrus) → item class (catalogue)
LRU_CLASS = {"HYD_PUMP": "HYDP", "FADEC": "FADEC", "ADC": "ADC", "RADAR": "RADAR", "INGPS": "INGPS", "JFS": "JFS",
             "AMAGB": "AMAGB", "DFCC": "DFCC", "BRAKE_CONTROL": "BCU", "BRAKE_VALVE": "BRAKE"}


def klass(part_no: str | None) -> str | None:
    """``SYN-PN-ENG-F404`` → ``ENG``; ``SYN-PN-HYDP`` → ``HYDP``."""
    if not part_no or not isinstance(part_no, str):
        return None
    p = part_no.removeprefix("SYN-PN-")
    return p.split("-")[0]


# ---- data ----------------------------------------------------------------------------------------------------
def link_findings(m: pd.DataFrame, cl: pd.DataFrame | None = None) -> pd.DataFrame:
    """SHOP_FINDING rows with the tail of the removal they belong to: same job + serial, the latest REMOVE at or
    before the finding (ties across tails broken by equal item hours; a redacted serial on the finding is matched by
    job + part + item hours); still ambiguous or unmatched → ``tail_no`` null."""
    sf = m[m.record_type == "SHOP_FINDING"].copy()
    if cl is None:
        cl = _repair_serials(m[(m.record_type == "COMPONENT_LIFE") & m.tail_no.notna()], m)
    rem = cl[(cl.install_action == "REMOVE") & cl.tail_no.notna()]
    idx = rem.groupby(["job_no", "serial_no"]).groups
    by_job = rem.groupby(["job_no", "part_no"]).groups
    tails, t_rem, serials = [], [], []
    for r in sf.itertuples():
        sn = r.serial_no
        if serial_ok(sn):
            c = rem.loc[idx[(r.job_no, sn)]] if (r.job_no, sn) in idx else rem.iloc[:0]
        else:  # redacted serial on the finding: same job + part, matched on the unit's item hours
            c = rem.loc[by_job[(r.job_no, r.part_no)]] if (r.job_no, r.part_no) in by_job else rem.iloc[:0]
            hrs = r.item_hours if r.item_hours is not None and not pd.isna(r.item_hours) else None
            c = c[(c.item_hours - float(hrs)).abs() < 1e-6] if hrs is not None else c.iloc[:0]
            if c.serial_no.nunique() == 1:
                sn = c.serial_no.iloc[0]
        serials.append(sn)
        c = c[c.t_event <= r.t_event]
        if len(c):
            last = c[c.t_event == c.t_event.max()]
            if last.tail_no.nunique() > 1 and r.item_hours is not None and not pd.isna(r.item_hours):
                # the same scheduled job on several tails at one instant: the unit keeps its hours in the shop
                same = last[(last.item_hours - float(r.item_hours)).abs() < 1e-6]
                last = same if len(same) else last
            ts = sorted(last.tail_no.unique())
            tails.append(ts[0] if len(ts) == 1 else None)
            t_rem.append(int(last.t_event.iloc[0]) if len(ts) == 1 else None)
        else:
            tails.append(None)
            t_rem.append(None)
    sf["tail_no"] = tails
    sf["t_remove"] = t_rem
    sf["serial_no"] = serials
    # one finding per (tail, serial, removal): earliest ingest
    sf = sf.sort_values("t_ingest", kind="mergesort").drop_duplicates(["tail_no", "serial_no", "job_no", "rid"])
    return sf


def _repair_serials(cl: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    """COMPONENT_LIFE rows with a redacted or truncated serial (deliberate record defects): take the engine serial,
    else the job's "REMOVED S/N …, INSTALLED S/N …" narrative; REMOVE rows still unresolved take the only open
    spell of that part on the tail (resolved in ``build_spells``)."""
    cl = cl.copy()
    cl["serial_repaired"] = False
    bad = ~cl.serial_no.map(serial_ok)
    if not bad.any():
        return cl
    txt = m[m.corrective_action_text.notna() & m.tail_no.notna()]
    rr: dict[tuple[str, str], tuple[str, str]] = {}
    for r in txt.itertuples():
        mm = RR_TEXT.search(r.corrective_action_text)
        if mm and r.job_no:
            rr[(r.tail_no, r.job_no)] = (mm.group(1), mm.group(2))
    for i in cl.index[bad]:
        r = cl.loc[i]
        new = None
        if isinstance(r.engine_serial, str) and serial_ok(r.engine_serial):
            new = r.engine_serial
        elif (r.tail_no, r.job_no) in rr:
            rem, ins = rr[(r.tail_no, r.job_no)]
            new = rem if r.install_action == "REMOVE" else ins
            new = new if serial_ok(new) else None
        if new:
            cl.at[i, "serial_no"] = new
            cl.at[i, "serial_repaired"] = True
    return cl


def _alarm_times(store, t: int, *, source: Source, world_seed: int | None) -> dict[tuple[str, str], np.ndarray]:
    """Occurrence times of BIT faults and cautions per (tail, class), for alarms that name an LRU of the class
    among their suspects."""
    out: dict[tuple[str, str], list[int]] = {}
    for topic in ("events.bit_faults", "events.cautions"):
        d = store.df(t, topic, source=source, world_seed=world_seed)
        if not len(d):
            continue
        for tail, sus, to in zip(d.tail_no, d.suspect_lrus, d.t_occurrence, strict=True):
            if tail is None or sus is None:
                continue
            seen = set()
            for x in sus:
                k = LRU_CLASS.get(x.get("lru") if isinstance(x, dict) else str(x))
                if k and k not in seen:
                    seen.add(k)
                    out.setdefault((tail, k), []).append(int(to))
    return {k: np.sort(np.array(v, dtype="int64")) for k, v in out.items()}


def build_spells(store, t: int, *, source: Source = Source.TRAIN, world_seed: int | None = None) -> pd.DataFrame:
    """Installation spells of every serial in one world (``world_seed``) as of ``t``, with the spell covariates:
    ``inferred_install`` (install record's serial was redacted and recovered), ``prior_rtok`` (earlier spells of the
    serial on this tail that ended RTOK) and ``alarm_fh`` (flight hours since install at each class alarm)."""
    m = store.df(t, "maint.records", source=source, world_seed=world_seed)
    if not len(m):
        return pd.DataFrame()
    cl = m[(m.record_type == "COMPONENT_LIFE") & m.tail_no.notna()].sort_values(["t_event", "record_version"],
                                                                                 kind="mergesort")
    jobs = (m[(m.record_type == "DEFECT_WO") & m.tail_no.notna()]
            .sort_values(["record_version", "t_ingest"], kind="mergesort")
            .drop_duplicates(["tail_no", "job_no"], keep="last")
            .set_index(["tail_no", "job_no"]).malfunction_code)
    cl = _repair_serials(cl, m)
    sf = link_findings(m, cl)
    sf = sf[sf.tail_no.notna()]
    sf_idx = {(r.tail_no, r.serial_no, r.job_no): r.shop_finding for r in sf.itertuples()}
    so = m[(m.record_type == "SORTIE") & m.tail_no.notna()].sort_values("record_version").drop_duplicates(
        ["tail_no", "sortie_id"], keep="last").sort_values("t_open")
    fh = {k: (g.t_open.to_numpy(dtype="float64"), g.flight_hours.fillna(0).to_numpy()) for k, g in so.groupby("tail_no")}
    t_end = int(m.t_ingest.max()) if t >= 2**62 else int(t)
    alarms = _alarm_times(store, t, source=source, world_seed=world_seed)

    def flown(tail: str, a: int, b: int) -> float:
        if tail not in fh:
            return 0.0
        to, h = fh[tail]
        return float(h[(to >= a) & (to < b)].sum())

    rows = []
    open_: dict[tuple[str, str], dict] = {}
    for r in cl.itertuples():
        k = (r.tail_no, r.serial_no)
        if r.install_action == "INSTALL":
            open_[k] = {"t_install": int(r.t_event), "h_install": r.item_hours, "part_no": r.part_no,
                        "inferred_install": bool(r.serial_repaired)}
        elif r.install_action == "REMOVE":
            if k not in open_ and not serial_ok(r.serial_no):  # unresolved: the only open spell of that part
                cand = [kk for kk, v in open_.items() if kk[0] == r.tail_no and v["part_no"] == r.part_no]
                if len(cand) != 1:
                    continue
                k = cand[0]
            if k not in open_:
                continue
            s = open_.pop(k)
            mal = jobs.get((r.tail_no, r.job_no)) if r.job_no else None
            finding = sf_idx.get((r.tail_no, r.serial_no, r.job_no))
            hard = mal == HARD_TIME
            ev = int(finding in EVENT_FINDINGS and not hard)
            rows.append({**s, "tail_no": r.tail_no, "serial_no": k[1], "t_remove": int(r.t_event),
                         "h_remove": r.item_hours, "job_no": r.job_no, "malfunction_code": mal,
                         "finding": finding, "hard_time": hard, "event": ev,
                         "censor": None if ev else ("hard_time" if hard else ("rtok" if finding == "RTOK" else
                                                    ("no_finding" if finding is None else str(finding))))})
    for (tail, ser), s in open_.items():
        rows.append({**s, "tail_no": tail, "serial_no": ser, "t_remove": None, "h_remove": None, "job_no": None,
                     "malfunction_code": None, "finding": None, "hard_time": False, "event": 0, "censor": "fitted"})
    sp = pd.DataFrame(rows)
    if not len(sp):
        return sp
    sp["klass"] = sp.part_no.map(klass)
    sp["world_seed"] = world_seed
    exp, afh = [], []
    for r in sp.itertuples():
        b = r.t_remove if r.t_remove is not None and not pd.isna(r.t_remove) else t_end
        d = None
        if r.h_remove is not None and not pd.isna(r.h_remove) and r.h_install is not None and not pd.isna(r.h_install):
            d = float(r.h_remove) - float(r.h_install)
        if d is None or d < 0:
            d = flown(r.tail_no, int(r.t_install), int(b))
        exp.append(max(d, 0.0))
        # class alarms during the spell, placed on the spell's flight-hour clock (tail sorties since install)
        at = alarms.get((r.tail_no, r.klass))
        if at is None or r.tail_no not in fh:
            afh.append([])
            continue
        at = at[(at >= r.t_install) & (at < b)]
        to, h = fh[r.tail_no]
        sel = to >= r.t_install
        cum_t, cum_h = to[sel], np.cumsum(h[sel])
        # flight hours flown before each alarm (sorties that took off before it, incl. the one it happened in)
        i = np.searchsorted(cum_t, at, side="right")
        afh.append([float(cum_h[j - 1]) if j > 0 else 0.0 for j in i])
    sp["exposure_fh"] = exp
    sp["alarm_fh"] = afh
    sp = sp.sort_values(["tail_no", "serial_no", "t_install"], kind="mergesort")
    sp["prior_rtok"] = sp.groupby(["tail_no", "serial_no"]).censor.transform(
        lambda c: (c == "rtok").astype(int).cumsum().shift(fill_value=0))
    return sp.reset_index(drop=True)


def covariates(alarm_fh, age: float, prior_rtok: int, inferred: bool) -> dict[str, float]:
    """Landmark covariates of one spell at ``age`` FH (only what is known by then)."""
    a = np.asarray(alarm_fh, dtype=float)
    a = a[a <= age]
    return {
        "age_fh": float(age),
        "alarms_last10": float(np.log1p(np.sum(a > age - 10.0))),
        "alarm_rate": float(len(a) / max(age, 10.0)),
        "prior_rtok": float(min(prior_rtok, 5)),
        "inferred_install": float(bool(inferred)),
    }


def landmark_rows(sp: pd.DataFrame, step: float = LANDMARK_STEP) -> pd.DataFrame:
    """One row per spell and landmark age a (every ``step`` FH while fitted): residual life, event, covariates."""
    rows = []
    for r in sp.itertuples():
        a = 0.0
        while a < r.exposure_fh:
            rows.append({"klass": r.klass, "world_seed": r.world_seed, "tail_no": r.tail_no, "serial_no": r.serial_no,
                         "resid_fh": r.exposure_fh - a, "event": int(r.event),
                         **covariates(r.alarm_fh, a, r.prior_rtok, r.inferred_install)})
            a += step
    return pd.DataFrame(rows)


def count_findings(store, t: int, *, world_seed: int, source: Source = Source.TRAIN) -> pd.DataFrame:
    """SHOP_FINDING rows (linked to a tail where possible) with class, finding and the job's malfunction code."""
    m = store.df(t, "maint.records", source=source, world_seed=world_seed)
    sf = link_findings(m)
    jobs = (m[(m.record_type == "DEFECT_WO") & m.tail_no.notna()]
            .sort_values(["record_version", "t_ingest"], kind="mergesort")
            .drop_duplicates(["tail_no", "job_no"], keep="last")[["tail_no", "job_no", "malfunction_code"]])
    sf = sf.drop(columns=["malfunction_code"]).merge(jobs, on=["tail_no", "job_no"], how="left")
    sf["klass"] = sf.part_no.map(klass)
    sf["world_seed"] = world_seed
    return sf


# ---- model ---------------------------------------------------------------------------------------------------
KINDS = {
    "class_exp": "class-exposure baseline (events / flight hours per class)",
    "age": "Weibull AFT on age, partially pooled",
    "landmark": "landmark Weibull AFT with spell covariates, partially pooled",
}


@dataclass
class HazardModel:
    classes: list[str]
    events: dict[str, int]
    spells: dict[str, int]
    exposure_fh: dict[str, float]
    params: dict[str, float]  # "lambda_:<cov>" / "rho_:<cov>"; empty for class_exp
    cov: list[list[float]]
    param_order: list[str]
    penalizer: float
    train_seeds: list[int]
    meta: dict = field(default_factory=dict)
    kind: str = "age"
    covariates: list[str] = field(default_factory=list)
    champion_note: str = ""

    # ---- fitting
    @classmethod
    def fit(cls, spells: pd.DataFrame, *, kind: str = "age", penalizer: float = PENALIZER,
            train_seeds: list[int] | None = None, class_shape: bool = True):
        """``kind``: ``class_exp`` | ``age`` | ``landmark`` (see ``KINDS``). ``class_shape``: the class indicators also
        enter the Weibull shape (ridge-pooled like the scale)."""
        sp = spells[spells.klass.notna() & (spells.exposure_fh > 0)].copy()
        classes = sorted(sp.klass.unique())
        base = dict(
            classes=classes,
            events={k: int(g.event.sum()) for k, g in sp.groupby("klass")},
            spells={k: int(len(g)) for k, g in sp.groupby("klass")},
            exposure_fh={k: round(float(g.exposure_fh.sum()), 1) for k, g in sp.groupby("klass")},
            penalizer=penalizer, train_seeds=list(train_seeds or []), kind=kind,
        )
        if kind == "class_exp":
            return cls(params={}, cov=[], param_order=[], meta={"n": int(len(sp))}, **base)
        from lifelines import WeibullAFTFitter

        if kind == "age":
            df, dur, covs = sp[["exposure_fh", "event"]].reset_index(drop=True), "exposure_fh", []
            xk = sp.klass
        else:
            lm = landmark_rows(sp)
            covs = ["age_fh", "alarms_last10", "alarm_rate", "prior_rtok", "inferred_install"]
            covs = [c for c in covs if lm[c].std() > 0]
            df, dur = lm[["resid_fh", "event", *covs]].reset_index(drop=True), "resid_fh"
            xk = lm.klass
        x = pd.get_dummies(xk, prefix="c", dtype=float).reset_index(drop=True)
        df = pd.concat([df, x], axis=1)
        f = WeibullAFTFitter(penalizer=penalizer)
        anc = pd.concat([x], axis=1) if class_shape else False
        f.fit(df, duration_col=dur, event_col="event", ancillary=anc)
        order = [f"{a}:{b}" for a, b in f.params_.index]
        return cls(params={o: float(v) for o, v in zip(order, f.params_.to_numpy(), strict=True)},
                   cov=f.variance_matrix_.to_numpy().tolist(), param_order=order, covariates=covs,
                   meta={"log_likelihood": float(f.log_likelihood_), "n": int(len(df)), "class_shape": class_shape},
                   **base)

    # ---- prediction
    def _lam_rho(self, k: str, p: np.ndarray, x: dict[str, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
        idx = {o: i for i, o in enumerate(self.param_order)}
        lin = p[:, idx["lambda_:Intercept"]]
        if f"lambda_:c_{k}" in idx:
            lin = lin + p[:, idx[f"lambda_:c_{k}"]]
        for c in self.covariates:
            lin = lin + p[:, idx[f"lambda_:{c}"]] * float((x or {}).get(c, 0.0))
        rlin = p[:, idx["rho_:Intercept"]]
        if f"rho_:c_{k}" in idx:
            rlin = rlin + p[:, idx[f"rho_:c_{k}"]]
        return np.exp(lin), np.exp(rlin)

    def sufficient(self, k: str) -> bool:
        return self.events.get(k, 0) >= MIN_EVENTS

    def rate(self, k: str) -> float:
        return self.events.get(k, 0) / max(self.exposure_fh.get(k, 0.0), 1e-9)

    def risk(self, k: str, age_fh: float, horizon_fh: float, x: dict[str, float] | None = None, *,
             draws: int = 0, seed: int = 0):
        """P(confirmed-fault removal in (age, age + horizon] | fitted at age, covariates x). With ``draws``:
        (point, lo10, hi90)."""
        h = max(horizon_fh, 0.0)
        if self.kind == "class_exp":
            r0 = 1.0 - math.exp(-self.rate(k) * h)
            if not draws:
                return r0
            g = np.random.default_rng(seed)
            rs = g.gamma(self.events.get(k, 0) + 0.5, 1.0 / max(self.exposure_fh.get(k, 0.0), 1e-9), size=draws)
            r = 1.0 - np.exp(-rs * h)
            return r0, float(np.quantile(r, 0.10)), float(np.quantile(r, 0.90))
        p0 = np.array([[self.params[o] for o in self.param_order]])
        if draws:
            g = np.random.default_rng(seed)
            p = np.vstack([p0, g.multivariate_normal(p0[0], np.array(self.cov), size=draws, method="svd")])
        else:
            p = p0
        if self.kind == "landmark":
            lam, rho = self._lam_rho(k, p, x or covariates([], age_fh, 0, False))
            r = 1.0 - np.exp(-((h / lam) ** rho))
        else:
            lam, rho = self._lam_rho(k, p)
            a, b = max(age_fh, 0.0), max(age_fh, 0.0) + h
            r = 1.0 - np.exp(-((b / lam) ** rho) + (a / lam) ** rho)
        if not draws:
            return float(r[0])
        return float(r[0]), float(np.quantile(r[1:], 0.10)), float(np.quantile(r[1:], 0.90))

    def belief(self, k: str, age_fh: float, horizon_fh: float, x: dict[str, float] | None = None) -> Belief:
        n = self.events.get(k, 0)
        common = dict(model_id=MODEL_ID, model_version=f"{MODEL_VERSION} {self.kind}", source=Source.TRAIN)
        if not self.sufficient(k):
            return Belief("removal_risk_30d", None, None, None, n,
                          note=f"INSUFFICIENT_EVIDENCE: {n} confirmed-fault removals of class {k} in the "
                               f"training worlds (< {MIN_EVENTS}); {LABEL}", **common)
        v, lo, hi = self.risk(k, age_fh, horizon_fh, x, draws=400, seed=len(k) * 7919 + int(age_fh))
        return Belief("removal_risk_30d", v, lo, hi, n,
                      note=f"{LABEL}; champion: {KINDS[self.kind]}"
                           + (f" ({self.champion_note})" if self.champion_note else "")
                           + f"; age {age_fh:.1f} FH, next {horizon_fh:.1f} FH; 80 % interval", **common)

    # ---- persistence
    def to_json(self, path: Path) -> None:
        Path(path).write_text(json.dumps({"model_id": MODEL_ID, "model_version": MODEL_VERSION,
                                          "source_label": LABEL, **self.__dict__}, indent=1) + "\n")

    @classmethod
    def from_json(cls, path: Path) -> HazardModel:
        d = json.loads(Path(path).read_text())
        for k in ("model_id", "model_version", "source_label"):
            d.pop(k, None)
        return cls(**d)


# ---- live use ------------------------------------------------------------------------------------------------
def assess(store, t: int, model: HazardModel, *, source: Source = Source.FLEET) -> list[Finding]:
    """Removal risk over the next 30 days of flying for every serial fitted at ``t`` (live fleet)."""
    out: list[Finding] = []
    sp = build_spells(store, t, source=source)
    if not len(sp):
        return out
    fitted = sp[sp.censor == "fitted"]
    so = store.maint_latest(t, ["SORTIE"], source=source)
    for r in fitted.sort_values(["tail_no", "klass", "serial_no"]).itertuples():
        s = so[(so.tail_no == r.tail_no) & (so.t_open >= t - HORIZON_DAYS * DAY) & (so.t_open < t)]
        horizon = float(s.flight_hours.fillna(0).sum())  # next 30 days flown like the last 30
        x = covariates(r.alarm_fh, float(r.exposure_fh), int(r.prior_rtok), bool(r.inferred_install))
        b = model.belief(r.klass, float(r.exposure_fh), horizon, x)
        reason = (f"{r.klass} {r.serial_no} on {r.tail_no}: "
                  + ("insufficient simulated history for this class" if b.value is None else
                     f"{100 * b.value:.1f} % risk of a confirmed-fault removal in the next {horizon:.0f} FH")
                  + f" — {LABEL}.")
        out.append(Finding(MODEL_ID, Tier.PRED, r.tail_no, r.serial_no, (b,), (), reason))
    return out
