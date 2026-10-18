"""What-if KPIs (architecture §11.2): computed from the **truth** record log of a branch, never asserted.

- ``mc`` / ``fmc``: NAMP SCIR mission-capable / fully-mission-capable fraction of equipment-in-service time.
- ``nmcs`` / ``nmcm`` / ``nmcd``: fraction of EIS time in NMCS, NMCM (S+U) and NMCD.
- ``flying_task``: flown / tasked flight hours (scenario ``kpi.plan`` events): IAF flying-task achievement.
- ``aog_days``: aircraft-days in NMCS (grounded awaiting parts).
- ``cann_rate``: cannibalisations per 100 sorties (TO 00-20-2 App L CANN rate).
- ``man_hours``: man-hours booked on jobs closed in the window.
- ``cost``: relative proxy: new spares + depot repairs (0.3 x unit cost) + man-hours + expedite premiums.
- ``in_flight_failures``: defects first reported from the air (when-discovered in flight or abort).

Availability is reconstructed from AVAILABILITY_STATE records (latest version per bin; a state persists until
the next record) and clipped to the window, so it is exactly the SCIR arithmetic over the emitted bins.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from phalanx.maintenance import scir
from phalanx.maintenance.catalogue import Catalogue
from phalanx.maintenance.config import M18Config
from phalanx.maintenance.timebase import DAY_S, NS

from .session import RecordLog

DEPOT_REPAIR_COST_FRACTION = 0.3  # [ASSUMPTION A-W1.8-11] cost proxy only


@dataclass(frozen=True)
class Kpis:
    mc: float
    fmc: float
    nmcs: float
    nmcm: float
    nmcd: float
    flying_task: float
    flown_fh: float
    sorties: int
    aog_days: float
    cann_rate: float
    cann: int
    man_hours: float
    cost: float
    in_flight_failures: int

    def as_dict(self) -> dict[str, float]:
        return {k: float(v) for k, v in asdict(self).items()}


def availability_series(log: RecordLog) -> dict[str, list[tuple[int, int]]]:
    """Per tail: [(bin_start_abs_ns, state code)] from AVAILABILITY_STATE records (latest version per bin)."""
    best: dict[tuple[str, int], tuple[int, int]] = {}
    for r in log.rows("maint.records"):
        if r["record_type"] != "AVAILABILITY_STATE":
            continue
        key = (r["tail_no"], int(r["t_event"]))
        v = int(r["record_version"])
        if key not in best or v > best[key][0]:
            best[key] = (v, scir.RANK[r["availability_state"]])
    out: dict[str, list[tuple[int, int]]] = {}
    for (tail, b), (_, s) in sorted(best.items()):
        out.setdefault(tail, []).append((b, s))
    return out


def occupancy_window(series: Sequence[tuple[int, int]], t0: int, t1: int) -> list[int]:
    """ns per state in [t0, t1) for a persist-until-next-record series."""
    occ = [0] * len(scir.STATES)
    if t1 <= t0:
        return occ
    cur = scir.FMC  # before the first record (fleet start): fully mission capable
    i0 = 0
    for i, (b, s) in enumerate(series):
        if b > t0:
            break
        cur, i0 = s, i + 1
    t = t0
    for b, s in series[i0:]:
        if b >= t1:
            break
        occ[cur] += b - t
        t, cur = b, s
    occ[cur] += t1 - t
    return occ


def compute_kpis(
    log: RecordLog,
    cfg: M18Config,
    *,
    t0_utc: int,
    t1_utc: int,
    tails: Sequence[str],
) -> Kpis:
    cat: Catalogue = cfg.catalogue
    unit_cost = {c.part_no: c.v("unit_cost") for c in cat.classes}
    ser = availability_series(log)
    per_tail = [occupancy_window(ser.get(t, []), t0_utc, t1_utc) for t in tails]
    av = scir.kpis_from_occupancy(per_tail)
    nmcm = av.fraction("NMCM_S") + av.fraction("NMCM_U")
    sorties = [
        r
        for r in log.rows("maint.records")
        if r["record_type"] == "SORTIE" and t0_utc <= int(r["t_event"]) < t1_utc
    ]
    flown = sum(float(r["flight_hours"]) for r in sorties)
    planned = sum(float(p["planned_fh"]) for p in log.rows("kpi.plan") if t0_utc <= int(p["t_utc"]) < t1_utc)
    cann = sum(  # one recipient-side record per cannibalisation (the donor side is a job with versions)
        1
        for r in log.rows("maint.records")
        if r["record_type"] == "CANNIBALISATION"
        and r["donor_tail_no"] != r["tail_no"]
        and t0_utc <= int(r["t_event"]) < t1_utc
    )
    mh = 0.0
    cost = 0.0
    in_flight = 0
    rows = log.rows("maint.records")
    hints = log.hints("maint.records")
    for r, h in zip(rows, hints, strict=True):
        te = int(r["t_event"])
        if not t0_utc <= te < t1_utc:
            continue
        rt = r["record_type"]
        if r["status"] == "CLOSED" and rt in (
            "DEFECT_WO",
            "INSPECTION",
            "EXCEEDANCE_INSPECTION",
            "MODIFICATION",
            "CANNIBALISATION",
        ):
            mh += float(r["man_hours"] or 0.0)
        if rt == "SUPPLY_DEMAND" and r["status"] == "CLOSED":
            c = unit_cost.get(r["part_no"], 0.0)
            cost += c * (1.0 + (cfg.expedite_premium if (h or {}).get("expedited") else 0.0))
        if rt == "SHOP_FINDING" and (h or {}).get("level") == "depot":
            cost += DEPOT_REPAIR_COST_FRACTION * unit_cost.get(r["part_no"], 0.0)
        if (
            rt == "DEFECT_WO"
            and int(r["record_version"]) == 0
            and r["when_discovered"] in ("WD-AIR", "WD-ABT")
        ):
            in_flight += 1
    cost += mh * cfg.mh_cost
    return Kpis(
        mc=av.mc,
        fmc=av.fmc,
        nmcs=av.fraction("NMCS"),
        nmcm=nmcm,
        nmcd=av.fraction("NMCD"),
        flying_task=(flown / planned) if planned > 0 else 0.0,
        flown_fh=flown,
        sorties=len(sorties),
        aog_days=av.occupancy[scir.NMCS] / (DAY_S * NS),
        cann_rate=100.0 * cann / len(sorties) if sorties else 0.0,
        cann=cann,
        man_hours=mh,
        cost=cost,
        in_flight_failures=in_flight,
    )


def kpi_names() -> tuple[str, ...]:
    return tuple(Kpis.__dataclass_fields__)


def kpi_delta(a: Mapping[str, float], b: Mapping[str, float]) -> dict[str, float]:
    return {k: float(a[k]) - float(b[k]) for k in a}
