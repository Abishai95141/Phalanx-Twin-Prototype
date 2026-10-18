"""From triage facts to policy evaluations and candidate orders.

Each issue's facts (``triage.Facts``) are mapped to the inputs of the decision tables that apply to its kind:

- alert issues: P-DEC-01 (recurring deferred BIT code) and P-ORG-01 (deferral limits); the D8 nuisance review
  (standing alarm with repeated could-not-duplicate closes → HUMAN-only CHANGE_MONITORING_CONFIG draft, architecture
  07); and, when no row fires but the C × U lookup banded the issue P1–P3, the lookup's default TROUBLESHOOT
  (rule P-DEC-01, row "AP", as the film's board did);
- supply issues (aircraft waiting for a part): P-ORG-02 (cannibalise only from an NMC donor, else expedite);
- life issues (item at its limit): P-SPR-01 (reorder a life-limited spare when its lead time exceeds the time to
  the limit).

Every candidate is AGENT or HUMAN per the authority matrix and starts in consent mode.
"""

from __future__ import annotations

from interfaces import CandidateOrder

from policies.engine import Evaluation, Policies
from policies.invariants import authority_of

PRIORITY = {"EXPEDITE_SPARES": "AOG", "REQUISITION_SPARES": "MCM"}


def priority(c: CandidateOrder) -> str:
    """``orders.commands.priority`` for a candidate (CandidateOrder has no field for it yet)."""
    return PRIORITY.get(c.action, "ROUTINE")


def evaluate(pol: Policies, f, prefs) -> dict[str, Evaluation]:
    out: dict[str, Evaluation] = {}
    if f.kind == "alert":
        out["P-DEC-01"] = pol.evaluate("P-DEC-01", {
            "severity": f.severity, "job": {"status": f.job_status}, "occ_10d": f.occ_10d,
            "consec_flights": f.consec, "corroborated": bool(f.corroborated),
            "code": {"nofault_rate": round(float(f.nofault_rate), 4)}})
        out["P-ORG-01"] = pol.evaluate("P-ORG-01", {
            "defect": {"grounding": bool(f.grounding)}, "severity": f.severity, "fault_list": f.fault_list,
            "mission_essential": f.fault_list == "PFL"})
    elif f.kind == "supply":
        out["P-ORG-02"] = pol.evaluate("P-ORG-02", {
            "donor": {"nmc": bool(f.donor_nmc)}, "job": {"awp_days": round(float(f.down_days), 1)},
            "policy": {"awp_min_days": prefs["awp_min_days"]}})
    elif f.kind == "life":
        out["P-SPR-01"] = pol.evaluate("P-SPR-01", {
            "life": {"left": f.life_left, "days_to_limit": f.ttf_days if f.ttf_days is not None else 1e9},
            "lead": {"median_d": f.lead_days if f.lead_days is not None else 0.0}})
    return out


def floor(evals: dict[str, Evaluation]) -> tuple[str | None, str | None]:
    """(band, "policy row") a decision-table row asks for; it can raise the lookup band, never lower it."""
    e = evals.get("P-DEC-01")
    if e is not None and e.rec.get("action") not in (None, "NONE"):
        return e.rec.get("band"), f"P-DEC-01 {e.row}"
    return None, None


def nuisance(f, prefs) -> bool:
    """D8 standing alarm: fired on ≥ standing_flights consecutive flights with ≥ nuisance_min_cnd prior
    could-not-duplicate closes of the same code on the tail."""
    return f.kind == "alert" and f.consec >= prefs["standing_flights"] and f.prior_cnd >= prefs["nuisance_min_cnd"]


def _order(pol: Policies, f, rule: str, row: str, action: str, params, rationale: str, tail, base, evidence) -> CandidateOrder:
    return CandidateOrder(issue_id=f.issue_id, rule=rule, row=row, policy_version=pol.version[rule], action=action,
                          parameters=params, target_tail_no=tail, target_base=base, authority=authority_of(action),
                          mode="consent", evidence=tuple(bytes.fromhex(x) for x in evidence), rationale=rationale)


def candidates(pol: Policies, f, evals: dict[str, Evaluation], band: str | None, prefs) -> list[CandidateOrder]:
    out: list[CandidateOrder] = []
    if band is None or band == "P4":
        return out
    if f.kind == "alert":
        e = evals["P-DEC-01"]
        act = e.rec.get("action")
        if act == "TROUBLESHOOT":
            out.append(_order(pol, f, "P-DEC-01", e.row, act, {"code": f.code}, e.rec.get("rationale_id"),
                              f.tail_no, None, f.evidence))
        elif act in (None, "NONE"):
            out.append(_order(pol, f, "P-DEC-01", "AP", "TROUBLESHOOT", {"code": f.code}, f"AP_C{f.C}_U{f.U}",
                              f.tail_no, None, f.evidence))
        if nuisance(f, prefs):
            out.append(_order(pol, f, "P-DEC-01", "D8", "CHANGE_MONITORING_CONFIG", {"filter_codes_add": [f.code]},
                              "STANDING_NUISANCE_REVIEW", f.tail_no, None, f.evidence))
    elif f.kind == "supply":
        e = evals["P-ORG-02"]
        act = e.rec.get("action")
        if act == "EXPEDITE_SPARES":
            out.append(_order(pol, f, "P-ORG-02", e.row, act, {"demand_no": f.demand_no}, e.rec.get("rationale_id"),
                              f.tail_no, f.base, f.evidence))
        elif act == "CANNIBALISE":
            out.append(_order(pol, f, "P-ORG-02", e.row, act, {"donor_tail_no": f.donor_tail, "part_no": f.part_no},
                              e.rec.get("rationale_id"), f.tail_no, f.base, f.evidence))
    elif f.kind == "life":
        e = evals["P-SPR-01"]
        if e.rec.get("action") == "REQUISITION_SPARES":
            out.append(_order(pol, f, "P-SPR-01", e.row, "REQUISITION_SPARES",
                              {"part_no": f.part_no, "quantity": int(f.quantity)}, e.rec.get("rationale_id"),
                              None, f.base, f.evidence))
    return out
