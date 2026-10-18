# Golden check at 22 Jun 2026 06:00 IST — engines, triage, policies (lane S2)

What the S2 code computes on the preview v0.9 consumer tree against the film's values (DEVELOPMENT.md §5.1, §5.3),
and every difference with its reason. Tests: `proto/tests/test_engines_golden.py`, `test_triage_golden.py`,
`test_triage_policies.py` (44 tests, run on the LinuxONE server). Nothing here was tuned to match the film.

## Matches

| Area | Film | Ours |
|---|---|---|
| Alerts → issues | 1,192 alert rows (921 BIT + 271 cautions) → 326 issues → 33 open | same; all 271 cautions share an `event_id` with a BIT row, so 921 occurrences (D2) |
| D6 inhibition | removed none | none |
| TJ107 HYD-101 | 59 of 61 sorties, 34 consecutive, 792.3 man-hours | same |
| Pumps benched | 33 of 33 RTOK | same (shop findings linked to HYD-101 jobs) |
| CND champion | base rate stays; held-out Brier 0.1008 vs logistic 0.1072, n 449 / 139 | identical |
| Isolation TJ107 | indication path 0.56, gearbox drive 0.44, pump < 0.0001 | same |
| Next test | indication-path isolation 7.3 man-h, best in 19 of 24; drive check 8.3 (5 of 24); pump R/R 18.7 | same, man-hours from the jobs' PHX-FIM / PHX-TASK references |
| Similar case | TJ102 HYD-101, 24 flights since 9 Apr | top case, same numbers |
| Lead time | closed n 127, median 4.6 d, p90 38.3 d; KM median 5.8, p90 91.6; AFT tyre AOG 4.7 d, chute AOG 27.9 d | identical |
| Tyre | TJ105 7 of 8 landings, 0.87 ldg/d | same; quantity 2 |
| Drift | fleet GLR 1.08, week of 18 May, p 0.625, no alert | identical |
| Policy versions | P-DEC-01/1.4.0+jdm.c9b849a8e719 … | identical (files copied byte for byte) |
| Board | P1 TJ103, TJ106 LGB-501 · P2 TJ107 HYD-101 (policy floor), TJ108 chute · P3 TJ105 SPS-501, TJ105 tyre · P4 group | all seven, same bands |
| Order ids | the 7 ids of the 22 Jun epoch | all 7 reproduced exactly from rules (evidence windows, parameters, quantity) |

## Differences and reasons

**Engines**

1. **HYD-101 job count and P(confirmed).** Film: 107 jobs (71 CND, 35 removed, 1 troubleshot), P(confirmed) 0.005
   [0.000, 0.023]. Ours: 121 jobs, 120 closed (85 could-not-duplicate, 35 removed), 118 with a known outcome →
   0 confirmed, **0.004 [0.000, 0.021]**. The film's 107 came from a shared CSV that its own export
   (`export_decision_flow.py` caveats) could not reproduce; keying jobs by (tail, job) as RULES.md rule 4 requires
   gives 122; one of those is a duplicate snag (below); the troubleshoot job is still IN_WORK; two removals have no
   bench finding yet and are left out until it arrives.
2. **P(RTOK if removed) 0.986 [0.93, 1.00]** (film 0.985). Same 33 of 33; ours adds the §2.5 shrinkage (2 pseudo-
   observations at the fleet RTOK rate, 80 of 80) to the Jeffreys prior. Plain Jeffreys gives 0.985.
3. **Duplicate snags.** The data layer injects duplicate DEFECT_WO records (`<job>-D`, `defects.py`); engines drop
   a `-D` job when its base job exists on the same tail. TJ107 has 63 HYD-101 jobs, not 64 (the duplicate has 0
   man-hours). *The twin's `open_jobs` still counts them* (S1).
4. **TJ107 pump removals: 30** (film 28). One definition on every screen (board, decision card, twin panel,
   insight, workbench and twin strips): a *removal event* is a job that removed the part from the tail, known from
   its COMPONENT_LIFE REMOVE record **or** from the job text ("REMOVED S/N …"), counted once per job — the twin's
   configuration events (`Context.removal_events`). The film counted REMOVE records only (28); two removals are
   known only from job text: `sulur-26061-0002` (remove-and-replace, 3 Mar) and `sulur-26156-0002` (the troubleshoot
   job still in work, 10 Jun). As remove-and-replace *jobs* citing HYD-101 there are 29 (the C&D job breakdown says
   "29 remove-and-replace"). Isolation uses the 27 benched pumps removed from TJ107 itself (the film used the
   fleet's 29 pump findings); the posterior is the same to two decimals. Worst case for the pump over the 30
   (detection × leak) settings is 0.0002, not "< 0.0001 in every setting".
5. **No-fault rate fed to P-DEC-01:** 0.709 (85 of 120, shrunk) vs the film's 0.6636 (71 of 107). Same row (r3).
6. **TJ107 tyre 0 of 8** (film 3): a tyre change on 19 Jun is stated in job text but its install record is not yet
   ingested; life counts from the latest change in the twin's configuration events (job text + records). Known
   limit: when only some positions were changed last, the older positions' usage is not seen (follow-up: per-
   position life in the twin). Per-serial tracking was tried and rejected: corrupted serial records leave removals
   unmatched and show stale tyres 50–100 landings past their limit.

**Triage**

7. **Two more decisions (9, not 7).**
   - **TJ102 HYD-001 → P2.** Its job `sulur-26013-0004` has been deferred (IN_WORK, action AT-DEF) since 13 Jan and
     the code fired on the last 5 flights, so P-DEC-01 r3 raises it to P2 (TROUBLESHOOT) and D8 proposes a nuisance
     review (HUMAN CHANGE_MONITORING_CONFIG). The film evaluated P-DEC-01 only for its hand-picked items.
   - **TJ102 HYD-101 → P3.** Recurring (4 sorties in 10 days), fired on the last flight, C3 × U1 → P3 with the
     lookup's TROUBLESHOOT. The film showed TJ102 only as the similar case. It ranks last-but-one in P3.
   Three more candidate orders follow (two TROUBLESHOOT, one HUMAN CHANGE_MONITORING_CONFIG).
8. **Urgency of alert issues.** §2.6's state rules give "recurring and recovered → U1": TJ103 / TJ106 LGB-501 U1
   (film U3, "2nd WARNING in 4 d"), TJ107 HYD-101 U1 (film U0), recurring advisories U1 (film U0). No band changes:
   LGB-501 is gated, TJ107 is raised by the P-DEC-01 floor (C3 × U1 = P3 → P2), advisories are C1 → P4.
9. **P4 group of 14** (film 13): adds TJ107 AVI-202 — AVI-202 is no-fault dominated (rate ≥ 0.6, the P-DEC-01 r4
   threshold) while the film's code list was typed by hand.
10. **Order within bands** by expected NMC-days avoided: P2 TJ108 chute (27.9) before TJ107 HYD-101; P3 tyre, TJ102
    HYD-101, TJ105 SPS-501. The film listed TJ107 first in P2.
11. **Gate readings.** G1 = a WARNING code recurring (≥ 2 sorties in 10 days); PFL alone does not gate (every
    caution is PFL, so SPS-501 and HYD-101 would all be P1). G2 = an open *unscheduled* defect listed U/S in the tech
    log (TJ108's chute job is a scheduled hard-time replacement awaiting parts → a supply issue, P2) or an open
    exceedance inspection (none in the preview). G3 = a life limit passed by more than the station's own hard-time
    changes go: in the fleet history the HI-TIME tyre change comes between 8 and 14 landings (95th percentile 4
    past the limit, 246 changes; chutes 0, 15 changes), so a tyre 1–4 landings past its limit with no change on
    record yet is the station's normal practice, shown at P3 (C2 × U3 by the lead-time margin) with that sentence,
    not gated to P1. An item one use from its limit is C2 (effects.yaml). The count is the twin's (landings since the
    latest recorded change; `twin.tyre_landings`), checked on 23 Jun of the go/no-go run.

**Policies**

12. **P-ORG-02 rationale** is the table's `NO_NMC_DONOR_EXPEDITE` (the film's board text said
    `AOG_NO_DONOR_EXPEDITE`). Donor NMC is false while cannibalisation needs the W2.6 multi-aircraft release
    (`prefs.yaml: cannibalisation_enabled: false`).
13. **P-SPR-01 is a new decision table** (the film had only its id as metadata): reorder a life-limited spare when
    the days to the limit are fewer than the lead-time median. Version `P-SPR-01/1.0.0+jdm.9918a6372573` (film
    metadata `c5a91d08`); the order id uses only the semver, so it is unchanged.
14. **D8 nuisance review and the lookup default** are Python rules next to the tables (rule P-DEC-01, rows "D8" and
    "AP", as the film's ids have them), not rows in the film's P-DEC-01 file, whose bytes are kept unchanged.

## Seen on the live run (`proto/runs/gonogo`, station routine only)

- 22 Jun 06:00: the same board, the same 10 candidate orders and ids as on the preview tree.
- 23 Jun 06:00: TJ104, TJ105 and TJ106 tyres show 10, 10 and 9 landings since their last recorded change, with no
  tyre job ingested, so gate G3 puts them at P1. With the data layer's reconciliation lag this can also mean the
  change happened and is not on record yet; the board says both. Order ids change from day to day because the
  evidence windows move (content-addressed, as intended).
