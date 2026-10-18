"""Shared pieces of the engines: the per-epoch context, model ids, Beta-Binomial helpers and Finding builders.

The context is everything the engines read at one snapshot ``t``, read once from the as-of store:

- alert occurrences: BIT and caution rows of the same ``event_id`` on a tail are one occurrence (architecture 07,
  D2); each keeps every record id it was built from;
- defect jobs: latest record version per (tail, job), with the alert codes any version cites as evidence; the data
  layer's injected duplicate snags (job ``<no>-D`` next to job ``<no>`` on the same tail) are dropped;
- sorties per tail, all maintenance record versions, and shop findings linked to their world.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from interfaces import DAY, NS, Belief, Finding, Source, Tier
from scipy.stats import beta as beta_dist

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
HERE = Path(__file__).resolve().parent
PARAMS = yaml.safe_load((HERE / "params.yaml").read_text())

#: model id and version of every engine output (registered on the event log by S1)
MODELS: dict[str, tuple[str, str]] = {
    "episodes": ("phx.episodes", "1.0.0"),
    "cnd": ("phx.cnd.beta-binomial", "1.0.0"),
    "cnd_challenger": ("phx.cnd.logreg", "1.0.0"),
    "isolation": ("phx.isolation.noisy-or", "1.0.0"),
    "similar": ("phx.similar.graph", "1.0.0"),
    "leadtime": ("phx.leadtime.km-lognormal", "1.0.0"),
    "life": ("phx.life.usage", "1.0.0"),
    "drift": ("phx.drift.poisson-glr", "1.0.0"),
    "triage": ("phx.triage", "1.0.0"),
}

NO_FAULT_ACTIONS = ("AT-CND", "AT-ADM")
CONFIRMED_FINDINGS = ("CONFIRMED", "BCM")
POWER_CODES = tuple(PARAMS["episodes"]["power_codes"])
SEV_RANK = {"ADVISORY": 1, "CAUTION": 2, "WARNING": 3}
PROC = re.compile(r"PHX-(?:FIM|TASK)-[A-Z0-9]+")


# ---- missing values -------------------------------------------------------------------------------------
# A missing value comes back as None (pandas 2) or NaN (pandas 3, a float). Every text, list or number field the
# engines regex, iterate or convert goes through one of these.
def text(x) -> str:
    return x if isinstance(x, str) else ""


def seq(x) -> list:
    """A list-valued field (evidence ids, suspect LRUs) as a list; missing → []."""
    return [] if x is None or isinstance(x, float | str | bytes) else list(x)


def num(x, default: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(v) else v


def serial(x) -> str | None:
    """A serial from the twin's configuration events, or None when missing."""
    return x if isinstance(x, str) and x else None


# ---- time ------------------------------------------------------------------------------------------------
def ist(t: int | None, fmt: str = "%d %b %H:%M") -> str | None:
    return None if t is None or pd.isna(t) else dt.datetime.fromtimestamp(int(t) / NS, IST).strftime(fmt)


def days(ns: float) -> float:
    return float(ns) / DAY


# ---- Beta-Binomial ---------------------------------------------------------------------------------------
def jeffreys(k: int, n: int) -> tuple[float, float, float]:
    """Posterior mean and equal-tailed 95 % interval of Beta(k + ½, n − k + ½)."""
    a, b = k + 0.5, n - k + 0.5
    return a / (a + b), float(beta_dist.ppf(0.025, a, b)), float(beta_dist.ppf(0.975, a, b))


def shrunk(k: int, n: int, fleet_rate: float, strength: float) -> tuple[float, float, float]:
    """Jeffreys prior plus ``strength`` pseudo-observations at the fleet rate: Beta(k + ½ + s·f, n − k + ½ + s·(1 − f)).
    Mean and equal-tailed 95 % interval."""
    a = k + 0.5 + strength * fleet_rate
    b = n - k + 0.5 + strength * (1.0 - fleet_rate)
    return a / (a + b), float(beta_dist.ppf(0.025, a, b)), float(beta_dist.ppf(0.975, a, b))


# ---- outputs ---------------------------------------------------------------------------------------------
def belief(model: str, name: str, value: float | None, lo: float | None = None, hi: float | None = None,
           n: int | None = None, note: str = "", source: Source = Source.FLEET) -> Belief:
    mid, ver = MODELS[model]
    r = (lambda x: None if x is None else round(float(x), 6))
    return Belief(name=name, value=r(value), lo=r(lo), hi=r(hi), n=None if n is None else int(n), model_id=mid,
                  model_version=ver, source=source, note=note)


def finding(engine: str, tier: Tier, tail_no: str | None, subject: str, beliefs, evidence, reason: str) -> Finding:
    ev = tuple(sorted({bytes(e) for e in evidence}))
    return Finding(engine=engine, tier=tier, tail_no=tail_no, subject=subject, beliefs=tuple(beliefs), evidence=ev,
                   reason=reason)


def rid_bytes(hex_ids) -> list[bytes]:
    return [bytes.fromhex(h) for h in hex_ids]


# ---- the per-epoch context -------------------------------------------------------------------------------
@dataclass
class Context:
    store: object
    twin: object
    t: int
    _memo: dict = field(default_factory=dict)

    # raw as-of frames
    @cached_property
    def bit(self) -> pd.DataFrame:
        return self.twin.snap(self.t).bit

    @cached_property
    def cautions(self) -> pd.DataFrame:
        return self.twin.snap(self.t).cautions

    @cached_property
    def latest(self) -> pd.DataFrame:
        """Latest record version per (tail, record type, record key); rows with a tail only."""
        return self.twin.snap(self.t).maint

    @cached_property
    def maint_all(self) -> pd.DataFrame:
        """Every maintenance record version ingested by t (incl. rows without a tail)."""
        return self.store.df(self.t, "maint.records")

    @cached_property
    def shop(self) -> pd.DataFrame:
        sf = self.twin.snap(self.t).shop
        return sf[sf.linked] if len(sf) else sf

    @cached_property
    def tails(self) -> list[str]:
        return self.twin.tails(self.t)

    # alert occurrences (D2)
    @cached_property
    def occ(self) -> pd.DataFrame:
        """One row per alert occurrence: BIT and caution rows sharing (tail, event_id) are merged. Columns:
        tail_no, event_id, sortie_id, event_code, severity, fault_list, source_lru, suspect_lrus, description,
        latched, persistence_count, t_occurrence, t_ingest (earliest of the pair), rids (record ids, hex),
        kinds ('BIT', 'CAUTION' or both)."""
        cols = ["tail_no", "event_id", "sortie_id", "event_code", "severity", "fault_list", "source_lru",
                "suspect_lrus", "description", "detection_mechanism", "latched", "persistence_count",
                "t_occurrence", "t_ingest", "rid"]
        parts = []
        for kind, df in (("BIT", self.bit), ("CAUTION", self.cautions)):
            if len(df):
                parts.append(df[cols].assign(kind=kind))
        if not parts:
            return pd.DataFrame(columns=cols + ["rids", "kinds"])
        # BIT first: an occurrence's primary record id (``rid``) is its BIT record when it has one
        a = pd.concat(parts, ignore_index=True).sort_values(["kind", "t_ingest"], kind="mergesort")
        a["event_id"] = a.event_id.map(
            lambda b: None if b is None or isinstance(b, float) else (b if isinstance(b, str) else bytes(b).hex()))
        a["event_id"] = a.event_id.fillna(a.rid)
        g = a.groupby(["tail_no", "event_id"], sort=False)
        first = g.head(1).set_index(["tail_no", "event_id"])
        agg = g.agg(rids=("rid", tuple), kinds=("kind", lambda k: "+".join(sorted(set(k)))),
                    t_ingest=("t_ingest", "min"), t_occurrence=("t_occurrence", "min"))
        out = first.drop(columns=["t_ingest", "t_occurrence", "kind"]).join(agg).reset_index()
        return out.sort_values(["t_ingest", "tail_no", "event_id"], kind="mergesort").reset_index(drop=True)

    @cached_property
    def code_of_rid(self) -> dict[tuple[str, str], str]:
        """(tail, record id hex) → alert code, for BIT and caution records."""
        out = {}
        for df in (self.bit, self.cautions):
            if len(df):
                out.update({(t, r): c for t, r, c in zip(df.tail_no, df.rid, df.event_code, strict=True)})
        return out

    @cached_property
    def ingest_of_rid(self) -> dict[tuple[str, str], int]:
        """(tail, record id hex) → t_ingest for every alert and maintenance record ingested by t."""
        out = {}
        for df in (self.bit, self.cautions, self.maint_all):
            if len(df):
                d = df[df.tail_no.notna()]
                out.update({(a, b): int(c) for a, b, c in zip(d.tail_no, d.rid, d.t_ingest, strict=True)})
        return out

    # defect jobs
    @cached_property
    def jobs(self) -> pd.DataFrame:
        """Latest version per (tail, job) of DEFECT_WO, duplicate snags dropped, with ``codes`` (frozenset of alert
        codes any version cites), ``first_ingest`` (ingest of version 0), ``evidence`` (all cited record ids, hex)
        and ``procs`` (PHX-FIM / PHX-TASK references in the corrective-action text)."""
        allv = self.maint_all
        dw = allv[(allv.record_type == "DEFECT_WO") & allv.tail_no.notna() & allv.job_no.notna()]
        latest = self.latest[self.latest.record_type == "DEFECT_WO"].copy()
        base = set(zip(latest.tail_no, latest.job_no, strict=True))
        dup = [str(j).endswith("-D") and (t, str(j)[:-2]) in base for t, j in zip(latest.tail_no, latest.job_no, strict=True)]
        latest = latest[~np.array(dup, dtype=bool)]
        c_of = self.code_of_rid
        codes, evid, first = {}, {}, {}
        for (tail, job), g in dw.groupby(["tail_no", "job_no"], sort=False):
            cs, ev = set(), []
            for lst in g.evidence_record_ids:
                for b in seq(lst):
                    h = bytes(b).hex()
                    ev.append(h)
                    c = c_of.get((tail, h))
                    if c:
                        cs.add(c)
            codes[(tail, job)] = frozenset(cs)
            evid[(tail, job)] = tuple(dict.fromkeys(ev))
            first[(tail, job)] = int(g.t_ingest.min())
        keys = list(zip(latest.tail_no, latest.job_no, strict=True))
        latest["codes"] = [codes.get(k, frozenset()) for k in keys]
        latest["evidence"] = [evid.get(k, ()) for k in keys]
        latest["first_ingest"] = [first.get(k) for k in keys]
        latest["procs"] = [tuple(PROC.findall(text(x))) for x in latest.corrective_action_text]
        return latest.reset_index(drop=True)

    def code_jobs(self, code: str, tail: str | None = None) -> pd.DataFrame:
        key = ("code_jobs", code, tail)
        if key not in self._memo:
            j = self.jobs
            m = j.codes.map(lambda c: code in c)
            if tail is not None:
                m &= j.tail_no == tail
            self._memo[key] = j[m]
        return self._memo[key]

    @cached_property
    def removals(self) -> pd.DataFrame:
        """COMPONENT_LIFE REMOVE records (latest version per key and job) with a tail."""
        allv = self.maint_all
        cl = allv[(allv.record_type == "COMPONENT_LIFE") & (allv.install_action == "REMOVE") & allv.tail_no.notna()]
        cl = cl.sort_values(["record_version", "t_ingest"], kind="mergesort")
        return cl.drop_duplicates(["tail_no", "record_key", "job_no"], keep="last").reset_index(drop=True)

    def job_findings(self, tail: str, job_no: str) -> pd.DataFrame:
        sf = self.shop
        return sf[(sf.tail_no == tail) & (sf.job_no == job_no)] if len(sf) else sf

    def removal_events(self, tail: str, part_no: str | None) -> list[dict]:
        """Removals of a part from the tail: one per job that removed it, known from COMPONENT_LIFE records or from
        the job text (the twin's configuration events; records can lag the text). The one definition of "removals"
        on every screen."""
        key = ("removal_events", tail, part_no)
        if key not in self._memo:
            seen, out = set(), []
            for e in self.twin.config_events(self.t, tail):
                if e["part_no"] == part_no and serial(e["removed"]) and e["job_no"] not in seen:
                    seen.add(e["job_no"])
                    out.append(e)
            self._memo[key] = out
        return self._memo[key]

    def sorties(self, tail: str) -> pd.DataFrame:
        key = ("sorties", tail)
        if key not in self._memo:
            self._memo[key] = self.twin.sorties(self.t, tail)
        return self._memo[key]

    @cached_property
    def availability(self) -> pd.DataFrame:
        av = self.latest[self.latest.record_type == "AVAILABILITY_STATE"]
        return av.sort_values(["tail_no", "t_event", "record_key"], kind="mergesort")

    @cached_property
    def state_now(self) -> dict[str, tuple[str, int]]:
        return self.twin.state_at(self.t, self.t)

    @cached_property
    def tech_log(self) -> dict[str, pd.Series]:
        """Latest TECH_LOG record per tail."""
        tl = self.latest[self.latest.record_type == "TECH_LOG"].sort_values("t_event", kind="mergesort")
        return {t: g.iloc[-1] for t, g in tl.groupby("tail_no")}

    def unserviceable_jobs(self, tail: str) -> list[str]:
        """Jobs the latest tech log lists as U/S (aircraft unserviceable) on the tail."""
        r = self.tech_log.get(tail)
        if r is None:
            return []
        out = []
        for part in text(r.limitations_text).split(";"):
            part = part.strip()
            if part.startswith("U/S:"):
                out += part[4:].split()
        return out

    def non_mc_days(self, tail: str, t0: int, t1: int) -> float:
        """Days the tail was not mission capable within [t0, t1]."""
        a = self.availability[self.availability.tail_no == tail]
        times, states = list(a.t_event), list(a.availability_state)
        tot = 0.0
        for i, s in enumerate(states):
            if s in ("FMC", "PMCM", "PMCS"):
                continue
            e = times[i + 1] if i + 1 < len(times) else self.t
            lo, hi = max(times[i], t0), min(e, t1)
            if hi > lo:
                tot += (hi - lo) / DAY
        return tot

    def fired_sorties(self, tail: str, code: str) -> set:
        o = self.occ
        return set(o[(o.tail_no == tail) & (o.event_code == code)].sortie_id)

    def consecutive(self, tail: str, code: str) -> int:
        """Trailing sorties of the tail on which the code fired."""
        fired, run = self.fired_sorties(tail, code), 0
        for sid in reversed(list(self.sorties(tail).sortie_id)):
            if sid not in fired:
                break
            run += 1
        return run


_CTX: dict[tuple, Context] = {}


def context(store, twin, t: int) -> Context:
    """The shared context for (store, twin, t); rebuilt when the store has loaded new files."""
    key = (id(store), id(twin), int(t), len(getattr(store, "seen", ())))
    if key not in _CTX:
        _CTX.clear()
        _CTX[key] = Context(store, twin, int(t))
    return _CTX[key]


def median_mh(jobs: pd.DataFrame) -> tuple[float | None, int]:
    x = jobs.man_hours.dropna().astype(float)
    x = x[x > 0]
    return (round(float(x.median()), 1), len(x)) if len(x) else (None, 0)


def top_proc(jobs: pd.DataFrame, prefix: str) -> str | None:
    c = Counter(p for ps in jobs.procs for p in ps if p.startswith(prefix))
    return c.most_common(1)[0][0] if c else None
