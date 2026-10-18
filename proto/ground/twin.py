"""Twin state: one state per aircraft, per serial and for the fleet, rebuilt from the as-of store.

Everything is computed as of a time ``t`` from records ingested by ``t``; maintenance records resolve to their
latest ``record_version`` per (tail_no, record_type, record_key). Availability follows the definition used for
the film's readiness numbers: AVAILABILITY_STATE intervals between consecutive state records (by event time),
MC = FMC + PMCM + PMCS, shares of possessed time.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from interfaces import (
    DAY,
    NS,
    AlarmStat,
    Availability,
    FleetState,
    Installed,
    SerialHistoryEntry,
    SerialState,
    TailState,
)
from store import Store

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
WORLD_START = int(dt.datetime(2026, 1, 5, tzinfo=dt.UTC).timestamp()) * NS  # fleet worlds start 2026-01-05 00:00 UTC
MC_STATES = {"FMC", "PMCM", "PMCS"}
NMCM_STATES = {"NMCM_S", "NMCM_U"}
OPEN_STATUSES = {"OPEN", "IN_WORK", "DEFERRED", "AWAITING_PARTS", "AWAITING_MAINTENANCE"}
RR_TEXT = re.compile(r"REMOVED S/N (\S+?),? INSTALLED S/N (\S+?)\.")
_TRUNCATED = re.compile(r"^[A-Z]+-\d{1,5}$")


def serial_ok(sn: str | None) -> bool:
    """False for the data layer's deliberate record defects: redacted ("XXX") or truncated serials."""
    return bool(sn) and "XXX" not in sn and not _TRUNCATED.match(sn)
TYRE = "SYN-PN-TYRE"


def ist(t: int | None, fmt: str = "%d %b %H:%M") -> str | None:
    return None if t is None else dt.datetime.fromtimestamp(t / NS, IST).strftime(fmt)


def ist_day_06(t: int) -> int:
    """06:00 IST of the IST calendar day containing ``t``."""
    d = dt.datetime.fromtimestamp(t / NS, IST).date()
    return int(dt.datetime(d.year, d.month, d.day, 6, tzinfo=IST).timestamp()) * NS


def _availability_kind(state: str) -> Availability:
    if state in MC_STATES:
        return Availability.FMC if state == "FMC" else Availability.PMC
    if state in NMCM_STATES:
        return Availability.NMCM
    if state == "NMCS":
        return Availability.NMCS
    if state == "NMCD":
        return Availability.NMCD
    return Availability.UNKNOWN


@dataclass
class _Snapshot:
    """The as-of frames one twin build needs (read once per ``t``)."""

    t: int
    maint: pd.DataFrame  # latest version per (tail, record_type, record_key)
    bit: pd.DataFrame
    cautions: pd.DataFrame
    shop: pd.DataFrame


class Twin:
    def __init__(self, store: Store) -> None:
        self.store = store
        self._cache: dict[int, _Snapshot] = {}

    # ---- the as-of frames ------------------------------------------------------------------------------
    def snap(self, t: int) -> _Snapshot:
        if t not in self._cache:
            self._cache = {t: _Snapshot(
                t=t,
                maint=self.store.maint_latest(t),
                bit=self.store.df(t, "events.bit_faults"),
                cautions=self.store.df(t, "events.cautions"),
                shop=self.store.shop_findings(t),
            )}
        return self._cache[t]

    def invalidate(self) -> None:
        self._cache.clear()

    def tails(self, t: int) -> list[str]:
        m = self.snap(t).maint
        return sorted(m.tail_no.dropna().unique())

    # ---- availability ----------------------------------------------------------------------------------
    def _av(self, t: int) -> pd.DataFrame:
        m = self.snap(t).maint
        return m[m.record_type == "AVAILABILITY_STATE"].sort_values(["tail_no", "t_event", "record_key"])

    def state_at(self, t: int, x: int) -> dict[str, tuple[str, int]]:
        """Per tail: (availability state, start of the current state run) at time ``x`` ≤ t."""
        out = {}
        for tail, a in self._av(t).groupby("tail_no"):
            a = a[a.t_event <= x]
            if not len(a):
                continue
            states, times = list(a.availability_state), list(a.t_event)
            i = len(states) - 1
            while i > 0 and states[i - 1] == states[-1]:
                i -= 1
            out[tail] = (states[-1], int(times[i]))
        return out

    def occupancy(self, t: int, w0: int, w1: int) -> dict[str, float]:
        """Tail-days per availability state in [w0, w1] (summed over tails)."""
        tot: dict[str, float] = defaultdict(float)
        for _, a in self._av(t).groupby("tail_no"):
            times = list(a.t_event) + [w1]
            for i, s in enumerate(a.availability_state):
                s0, s1 = max(times[i], w0), min(times[i + 1], w1)
                if s1 > s0:
                    tot[s] += (s1 - s0) / DAY
        return dict(tot)

    @staticmethod
    def rates(o: dict[str, float]) -> dict[str, float]:
        p = sum(o.values())
        if p <= 0:
            return {"possessed": 0.0}
        mc = sum(o.get(s, 0.0) for s in MC_STATES)
        nmcm = sum(o.get(s, 0.0) for s in NMCM_STATES)
        return {
            "possessed": round(p, 1),
            "mc": round(mc / p, 4),
            "fmc": round(o.get("FMC", 0.0) / p, 4),
            "tnmcm": round(nmcm / p, 4),
            "tnmcs": round(o.get("NMCS", 0.0) / p, 4),
            "nmcd": round(o.get("NMCD", 0.0) / p, 4),
        }

    # ---- sorties, alarms, jobs -------------------------------------------------------------------------
    def sorties(self, t: int, tail: str | None = None) -> pd.DataFrame:
        m = self.snap(t).maint
        s = m[(m.record_type == "SORTIE") & m.sortie_id.notna()]
        if tail is not None:
            s = s[s.tail_no == tail]
        return s.sort_values("t_event")

    def alarms(self, t: int, tail: str) -> list[AlarmStat]:
        sn = self.snap(t)
        ev = pd.concat([sn.bit, sn.cautions], ignore_index=True) if len(sn.cautions) else sn.bit
        ev = ev[ev.tail_no == tail]
        sids = list(self.sorties(t, tail).sortie_id)
        out = []
        for code, g in ev.groupby("event_code"):
            fired = set(g.sortie_id)
            run = 0
            for sid in reversed(sids):
                if sid not in fired:
                    break
                run += 1
            sev = g.severity.mode().iat[0] if len(g) else ""
            out.append(AlarmStat(code=str(code), count=len(g), last_seen=int(g.t_occurrence.max()),
                                 consecutive_sorties=run, severity=str(sev)))
        return sorted(out, key=lambda a: (-a.consecutive_sorties, -a.count, a.code))

    def sorties_with_code(self, t: int, tail: str, code: str) -> tuple[int, int]:
        """(sorties on which ``code`` fired, sorties flown) as of ``t``."""
        sn = self.snap(t)
        ev = pd.concat([sn.bit, sn.cautions], ignore_index=True)
        fired = set(ev[(ev.tail_no == tail) & (ev.event_code == code)].sortie_id)
        sids = list(self.sorties(t, tail).sortie_id)
        return sum(s in fired for s in sids), len(sids)

    def jobs(self, t: int, tail: str | None = None) -> pd.DataFrame:
        """Defect jobs (latest version). The data layer's deliberate duplicate snag records ("<job>-D", left open
        forever) are not jobs and are dropped — the film's open-job counts included them."""
        m = self.snap(t).maint
        j = m[(m.record_type == "DEFECT_WO") & ~m.job_no.fillna("").str.endswith("-D")]
        return j if tail is None else j[j.tail_no == tail]

    # ---- configuration and serials ---------------------------------------------------------------------
    def component_life(self, t: int, tail: str | None = None) -> pd.DataFrame:
        """Every COMPONENT_LIFE record version ingested by ``t`` (installs and removals are separate keys)."""
        m = self.store.df(t, "maint.records", tail_no=tail)
        if not len(m):
            return m
        cl = m[m.record_type == "COMPONENT_LIFE"]
        return cl.sort_values(["record_version", "t_ingest"]).drop_duplicates(["tail_no", "record_key", "install_action", "job_no"], keep="last").sort_values("t_event")

    def rr_from_text(self, t: int, tail: str) -> list[dict]:
        """Remove/replace events stated in job text ("REMOVED S/N X, INSTALLED S/N Y."), latest job version."""
        m = self.snap(t).maint
        j = m[(m.tail_no == tail) & m.job_no.notna() & m.corrective_action_text.fillna("").str.contains("INSTALLED S/N")]
        out = []
        for r in j.itertuples():
            mt = RR_TEXT.search(r.corrective_action_text)
            if mt:
                out.append({"job_no": r.job_no, "removed": mt.group(1), "installed": mt.group(2),
                            "part_no": r.part_no, "t": int(r.t_close if pd.notna(r.t_close) else r.t_event)})
        return sorted(out, key=lambda x: x["t"])

    def config_events(self, t: int, tail: str) -> list[dict]:
        """Configuration changes of the tail, oldest first: the initial fit, then one event per remove/replace
        job. Job text ("REMOVED S/N X, INSTALLED S/N Y.") is complete; COMPONENT_LIFE records can be missing or
        late, so a job stated in text uses the text, and a job known only from records uses the records.
        ``inferred`` marks an install whose INSTALL record has not been ingested."""
        cl = self.component_life(t, tail)
        part_of = dict(zip(cl.serial_no, cl.part_no, strict=False))
        installs_on_record = set(cl[cl.install_action == "INSTALL"].job_no.dropna())
        events: list[dict] = []
        for r in cl[cl.job_no.isna() & (cl.install_action == "INSTALL")].itertuples():
            events.append({"t": int(r.t_event), "job_no": None, "part_no": r.part_no, "removed": None,
                           "installed": r.serial_no, "inferred": False})
        text_jobs = set()
        for rr in self.rr_from_text(t, tail):
            pn = part_of.get(rr["removed"]) or part_of.get(rr["installed"]) or rr["part_no"]
            text_jobs.add(rr["job_no"])
            removed, installed = rr["removed"], rr["installed"]
            # a corrupted serial on one side is repaired from the other source of the same job
            jcl = cl[(cl.job_no == rr["job_no"]) & (cl.part_no == pn)]
            if not serial_ok(installed):
                c = [x for x in jcl[jcl.install_action == "INSTALL"].serial_no if serial_ok(x)]
                installed = c[0] if len(c) == 1 else installed
            if not serial_ok(removed):
                c = [x for x in jcl[jcl.install_action == "REMOVE"].serial_no if serial_ok(x)]
                removed = c[0] if len(c) == 1 else removed
            events.append({"t": rr["t"], "job_no": rr["job_no"], "part_no": pn, "removed": removed,
                           "installed": installed, "inferred": rr["job_no"] not in installs_on_record})
        for job, g in cl[cl.job_no.notna()].groupby("job_no"):
            if job in text_jobs:
                continue
            for pn, gp in g.groupby("part_no"):
                rem = list(gp[gp.install_action == "REMOVE"].serial_no)
                ins = list(gp[gp.install_action == "INSTALL"].serial_no)
                for k in range(max(len(rem), len(ins))):
                    events.append({"t": int(gp.t_event.min()), "job_no": job, "part_no": pn,
                                   "removed": rem[k] if k < len(rem) else None,
                                   "installed": ins[k] if k < len(ins) else None, "inferred": False})
        return sorted(events, key=lambda e: (e["t"], e["job_no"] or ""))

    def installed(self, t: int, tail: str) -> list[Installed]:
        """Serials fitted now, one slot per position: a replacement takes the slot of the serial it replaced."""
        slots: dict[str, list[list]] = defaultdict(list)  # part -> [[serial, since, inferred], …] by slot
        for e in self.config_events(t, tail):
            pn, sl = e["part_no"], slots[e["part_no"]]
            idx = next((i for i, s in enumerate(sl) if s[0] == e["removed"]), None) if e["removed"] else None
            if idx is None and e["removed"]:  # the removed serial sat in a slot whose record was corrupted
                idx = next((i for i, s in enumerate(sl) if s[0] is not None and not serial_ok(s[0])), None)
            if e["installed"] is None:
                if idx is not None:
                    sl[idx] = [None, e["t"], False]
                continue
            if idx is None:
                idx = next((i for i, s in enumerate(sl) if s[0] is None), None)
            item = [e["installed"], e["t"], e["inferred"]]
            if idx is None:
                sl.append(item)
            else:
                sl[idx] = item
            slots[pn] = sl
        out = []
        for pn in sorted(slots, key=str):
            for i, (sn, since, inferred) in enumerate(slots[pn], start=1):
                if sn is not None:
                    out.append(Installed(position=f"{pn}#{i}", serial_no=str(sn), part_no=pn, since=since, inferred=inferred))
        return out

    def serial(self, t: int, tail: str, serial_no: str) -> SerialState:
        """Lineage of one serial on one tail world: each fit and removal, with the shop finding if ingested."""
        sf = self.snap(t).shop
        sf = sf[(sf.tail_no == tail) & (sf.serial_no == serial_no)]
        hist: list[SerialHistoryEntry] = []
        part = None
        for e in self.config_events(t, tail):
            if e["installed"] == serial_no:
                part = e["part_no"]
                hist.append(SerialHistoryEntry(tail, e["part_no"], e["t"], None, e["job_no"], None))
            elif e["removed"] == serial_no:
                part = e["part_no"]
                f = sf[sf.job_no == e["job_no"]].shop_finding
                finding = None if not len(f) else str(f.iat[-1])
                if hist and hist[-1].removed is None:
                    h = hist[-1]
                    hist[-1] = SerialHistoryEntry(tail, h.position, h.installed, e["t"], e["job_no"], finding)
                else:
                    hist.append(SerialHistoryEntry(tail, e["part_no"], None, e["t"], e["job_no"], finding))
        return SerialState(tail_no=tail, serial_no=serial_no, part_no=part, klass=part, history=tuple(hist),
                           hours_since_install=None, cycles_since_install=None, beliefs=())

    def removals(self, t: int, tail: str, part_no: str) -> int:
        """Removal events of ``part_no`` on the tail: jobs that removed it, known from the COMPONENT_LIFE REMOVE
        record or from the job text, counted once per job (the same definition as the engines' removal_events).
        The film counted REMOVE records only (28 for TJ107 pumps); two removals are known only from job text."""
        return len({e["job_no"] for e in self.config_events(t, tail) if e["part_no"] == part_no and e["removed"]})

    def tyre_landings(self, t: int, tail: str) -> int:
        """Landings since the latest tyre install on the tail."""
        cl = self.component_life(t, tail)
        inst = cl[(cl.part_no == TYRE) & (cl.install_action == "INSTALL")]
        s = self.sorties(t, tail)
        if len(inst):
            s = s[s.t_event > inst.t_event.max()]
        return int(s.landings.fillna(0).sum())

    # ---- tail and fleet --------------------------------------------------------------------------------
    def tail(self, t: int, tail: str) -> TailState:
        sn = self.snap(t)
        st = self.state_at(t, t).get(tail, ("UNKNOWN", None))
        s = self.sorties(t, tail)
        s30 = s[s.t_event > t - 30 * DAY]
        jobs = self.jobs(t, tail)
        open_jobs = jobs[jobs.status.isin(OPEN_STATUSES)]
        m = sn.maint
        dem = m[(m.tail_no == tail) & (m.record_type == "SUPPLY_DEMAND") & (m.status == "OPEN")]
        state = st[0]
        reason = {"NMCS": "part", "NMCD": "depot"}.get(state) or ("work" if state in NMCM_STATES else None)
        return TailState(
            tail_no=tail,
            base=(m[m.tail_no == tail].base.dropna().iat[-1] if m[m.tail_no == tail].base.notna().any() else None),
            as_of=t,
            snapshot_id=self.store.snapshot_id(t),
            last_ingest=self.store.last_ingest(t, tail),
            status=_availability_kind(state),
            status_since=st[1],
            down_reason=reason,
            sorties=len(s),
            flight_hours=round(float(s.flight_hours.fillna(0).sum()), 1),
            landings=int(s.landings.fillna(0).sum()),
            sorties_30d=len(s30),
            flight_hours_30d=round(float(s30.flight_hours.fillna(0).sum()), 1),
            installed=tuple(self.installed(t, tail)),
            open_jobs=tuple(sorted(open_jobs.job_no.dropna())),
            open_demands=tuple(sorted(dem.demand_no.dropna())),
            alarms=tuple(self.alarms(t, tail)),
            issue_ids=(),
        )

    def fleet(self, t: int, days_daily: int = 60) -> FleetState:
        tails = self.tails(t)
        o30 = self.occupancy(t, t - 30 * DAY, t)
        oall = self.occupancy(t, WORLD_START, t)
        daily = []
        for k in range(days_daily - 1, -1, -1):
            x = ist_day_06(t) - k * DAY
            st = self.state_at(t, x)
            cnt = defaultdict(int)
            for s, _ in st.values():
                cnt["mc" if s in MC_STATES else "nmcm" if s in NMCM_STATES else s.lower()] += 1
            daily.append((ist(x, "%d %b"), dict(cnt)))
        sn = self.snap(t)
        return FleetState(
            as_of=t,
            snapshot_id=self.store.snapshot_id(t),
            tails={tl: self.tail(t, tl) for tl in tails},
            kpis_30d=self.rates(o30),
            kpis_all=self.rates(oall),
            mc_daily=daily,
            funnel={"alert_rows": len(sn.bit) + len(sn.cautions)},
        )

    def fleet_row(self, t: int, ts: TailState) -> dict:
        """One Readiness fleet row in the ``PHX_DATA.fleet`` shape."""
        jobs = self.jobs(t, ts.tail_no)
        state = self.state_at(t, t).get(ts.tail_no, ("UNKNOWN", None))[0]
        last_sortie = self.sorties(t, ts.tail_no).t_event.max()
        return {
            "tail": ts.tail_no,
            "state": state,
            "since": ist(ts.status_since),
            "since_days": None if ts.status_since is None else round((t - ts.status_since) / DAY, 1),
            "open_jobs": len(ts.open_jobs),
            "deferred": int((jobs.status == "DEFERRED").sum()),
            "awp": int((jobs.status == "AWAITING_PARTS").sum()),
            "fh30": ts.flight_hours_30d,
            "sorties30": ts.sorties_30d,
            "fh_total": ts.flight_hours,
            "sorties": ts.sorties,
            "landings": ts.landings,
            "tyre_ldg": self.tyre_landings(t, ts.tail_no),
            "last_sortie": ist(None if pd.isna(last_sortie) else int(last_sortie)),
            "last_ingest": ist(ts.last_ingest),
        }
