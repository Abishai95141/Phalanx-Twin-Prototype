"""Policies (DEVELOPMENT §2.7, architecture 07 Part B): four layers, higher always wins.

1. ``invariants`` — hard constraints in Python (authority, no automatic grounding, evidence ingested by the
   decision time, one open order per (tail, action, target), servicing extension cap).
2–3. ``engine.Policies`` — the decision tables in ``P-*.jdm.json``, evaluated with zen-engine, traced and
   versioned from their bytes; ``rules`` maps triage facts to their inputs and builds ``CandidateOrder``s.
4. ``prefs.yaml`` — bounded preferences (``engine.prefs()``).

Order ids: ``ids.candidate_order_id(candidate, t)`` (DEVELOPMENT §2.9).
"""

from policies.engine import Evaluation, Policies, policies, prefs
from policies.ids import candidate_order_id, epoch_of, order_id
from policies.invariants import authority_of, check, human_only, issue_violations
from policies.rules import priority

__all__ = ["Evaluation", "Policies", "authority_of", "candidate_order_id", "check", "epoch_of", "human_only",
           "issue_violations", "order_id", "policies", "prefs", "priority"]
