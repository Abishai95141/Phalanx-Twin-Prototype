# Phalanx data layer — our understanding

These docs record how the team's **Phalanx data layer** (a separate repo) works, from the point of view of
this repo, which builds the downstream PdM and fleet-availability solution for the "Air Power" fleet-availability problem statement. They summarise and
cross-check the data-layer context kit; the kit remains the source of truth.

- **Source kit:** `/Users/abishaikc/Downloads/phalanx_solution_context/` (snapshot 2026-10-15; source commit
  `972d46fd…`; contract `phalanx.ground_decoder_contract` 0.1.0 frozen, hash `18d7627b…cc4e`; dictionary
  `tejas` 0.1.2, hash `a8b02cab…17ce`).
- **Kit entry points:** `README.md` (consumer guide), `contract/contract.md`, `reference/architecture.md`,
  `reference/assumptions.md`, `modules/*.md`, `dictionary/`, `examples/`.

## In one paragraph

Phalanx simulates a virtual fleet of HAL Tejas Mk1A-class aircraft with F404-IN20 engines (2 squadrons × 16
tails at Sulur and Nal), from 240 Hz physics with hidden per-serial health and injected faults, through sensors,
MIL-STD-1553B/ARINC-429 buses and per-sortie IRIG 106 Ch10 recordings, to a ground decoder that writes a frozen
**data contract** of 9 Parquet topics (samples, BIT/exceedance/caution events, usage counters, sortie
manifests, maintenance records, orders and order status). Our solution reads that contract strictly "as of"
ingest time, acts on the fleet only through typed **orders** applied at daily 08:00 IST epochs, and proves
impact with **what-if forks** that use common random numbers. Hidden truth (`labels.truth`) exists only for
offline scoring. Everything (ICD, codes, part numbers) is synthetic; the integrated end-to-end simulation does
not exist yet (examples are format-only).

## Documents

| # | Doc | Read it for |
|---|---|---|
| 01 | [Overview and boundary](01-overview-and-boundary.md) | what the layer is, the three interfaces (contract, orders, forks), modules, fast vs full path, usage vs telemetry mode, fleet, status and milestones |
| 02 | [Contract topics](02-contract-topics.md) | the 9 topics, `record_id`, identities and linkage (ER diagram), storage layout, versioning |
| 03 | [Time and quality](03-time-and-quality.md) | six timestamps, clock domains, **information discipline (`t_ingest`)**, validity, quality flags, sentinels, dedup |
| 04 | [Dictionary and signals](04-dictionary-and-signals.md) | param/measurand/channel ids, units, LRUs, buses, rates, code tables, limits, PdM-relevant channel shortlist |
| 05 | [Events, usage, maintenance](05-events-usage-maintenance.md) | BIT model and false alarms, counters/LUIs, 11 maintenance record types, event chains, supply, SCIR availability, data defects |
| 06 | [Orders, forks, closed loop](06-orders-forks-closed-loop.md) | 18 order actions + parameters, authority, gateway checks, lifecycle, reference policies, what-if API and KPIs |
| 07 | [Truth, health, faults](07-truth-health-faults.md) | hidden states, degradation processes, fault catalogue, `labels.truth` and what can be scored |
| 08 | [Assumptions and limits](08-assumptions-and-limits.md) | key registry numbers, status-quo policy parameters, PROXY items, validation status, known contradictions |
| 09 | [Implications and open questions](09-implications-and-open-questions.md) | PS → data-layer mapping, 20-point consumer checklist, opportunities, questions for the data-layer team |
| 10 | [Worked example](10-worked-example.md) | one sortie end to end (BIT → defect → order → CND close → availability), verified storage/ID facts, gotchas |
| 11 | [Preview dataset v0.9](11-preview-v0.9.md) | **the data we build on now**: contract 0.2.0 / dictionary 0.1.3 changes, profiled contents, cross-world ID collisions, what can be demonstrated now vs later |

> **Version note:** docs 01–10 were written from the context kit (contract 0.1.0, dictionary 0.1.2). The
> preview moved to contract **0.2.0** (additive: `param.samples.recording_id` and `sink`) and dictionary
> **0.1.3**; everything else in 01–10 still holds. Doc 11 is authoritative for the preview.

## Suggested reading order

New to the project: 01 → 09 → 10 → 02 → 03. Building ingestion: 02, 03, 04, 10. Building models: 05, 07, 04,
08. Building decision/optimisation: 06, 05, 08.
