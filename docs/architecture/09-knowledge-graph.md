# 09 · Knowledge graph: one curated graph for isolation, lineage, applicability and the assistant

The team proposed graph-based systems for fault isolation, component relationships and document applicability.
The research supports **one small, curated property graph** — and rejects the fashionable variants (GraphRAG,
GNNs, OWL ontologies) for our data.

## Where graphs add value — and where they don't

| Use | Value | Decision |
|---|---|---|
| Fault isolation (D-matrix, ambiguity groups, consolidation, test selection) | high — the industrial pattern (777 CMC, QSI TEAMS) is a graph + reasoner | **Build** ([04](04-condition-monitoring-and-diagnostics.md)) |
| Component lineage (serial ↔ tail ↔ position intervals, removals, shop findings, orders) | high — rogue units, RTOK chains, "what changed before this snag", life that travels with the serial | **Build now** (scoped per world on v0.9) |
| Symptom consolidation / inhibition (bus or power fault mutes dependent LRU codes) | high — cuts alert load in triage | **Build** ([07](07-triage-policy-decision-loop.md) D6) |
| Document applicability (which procedure applies to this tail/serial now) | valued by reviewers; thin data in v0.9 (no MODIFICATION records, only SW-BASE) | **Build a thin version** with ~20–40 synthetic procedures referenced in the records (`PHX-TASK-*`, `PHX-FIM-*`) |
| Assistant grounding | typed graph queries answer structured questions exactly | **Yes, via tools** ([10](10-assistant.md)) |
| Cannibalisation chains, cross-tail "follows the serial" | not demonstrable on v0.9 (one-tail worlds, no CANN records) | schema only until the shared-world fleet (W2.6) |
| GraphRAG / LightRAG community summarisation | our corpus is tiny and templated; questions are structured; GraphRAG-Bench (ICLR 2026) finds basic RAG comparable or better on fact retrieval, and global GraphRAG costs ≈ 330k tokens per query | **Reject** |
| GNN diagnosis | no labelled faults, unvalidated signatures, poor explainability | **Reject** |
| Causal discovery | structure is known by design; co-occurrence lift covers sympathetic codes | **Reject** |
| Full OWL ontologies (ISO 15926, ISO 14224, IOF) | prototype time sink | **Borrow vocabulary only** (ISO 14224 mode/mechanism/cause split; IOF/S5000F activity types; ATA Spec 2000 Ch. 11 removal/shop-finding semantics) |
| Copying the simulator's `graph.yaml`/`catalogue.yaml` | its cascade edges are rare mishap chains, and its coverage/rates/latencies are simulator truth | **Never** — encode only public architecture coupling |

## Schema

Every edge carries `valid_from`, `valid_to`, `t_ingest` and `source_record_id` (bitemporal, so as-of queries are
exact). Instance nodes are keyed by `(scope, natural_key)` — `scope` is the tail/world on the v0.9 preview.

**Engineering layer** (versioned by `dict_hash`; authored or derived from contract artefacts, never from simulator
configs):
- Nodes: `System` (15 subsystems + synthetic ATA chapter), `LRU` (30), `ItemClass` / `Position` (part classes,
  inferred positions), `SubItem` (suspect names such as `N1_PICKUP_A`), `Bus` (AV-MUX-1/2, ARINC links),
  `Channel` (measurand), `PhysState` (N2, AMAGB speed, hydraulic pressure, generator speed), `Code` (BIT /
  exceedance / caution), `Legend`, `FailureMode` (our FMECA rows), `Zone` (synthetic).
- Edges: `SubItem –PART_OF / AMBIGUOUS_WITH→ Position`; `LRU –ON_BUS{rt}→ Bus`; `LRU –PRODUCES→ Channel`;
  `Code –MONITORS→ Channel`; `Code –DISPLAYS_AS→ Legend`; `PhysState –DRIVES{shaft|hydraulic|electrical|data}→
  PhysState/Position` (coarse: N2 → AMAGB → hydraulic pumps, generator, JFS — public architecture);
  `FailureMode –OF→ Position`; `FailureMode –DETECTED_BY{p_prior, p_learned}→ Code` (the D-matrix / noisy-OR
  edges); `Code –SYMPATHETIC_OF{lift}→ Code` (learned); `Position –IN_ZONE→ Zone`.

**Instance layer:**
- Nodes: `Tail`, `Serial`, `Sortie`, `Event`, `Issue`, `Defect` (job), `Action`, `ShopFinding`, `Inspection`,
  `Order`, `ConfigState` (`sw_config_id`), `Modification`, `Procedure`, `ApplicExpr`.
- Edges: `Serial –INSTALLED_ON{position, interval}→ Tail`; `Tail –FLEW→ Sortie`; `Event –IN→ Sortie`;
  `Event –SUSPECTS{conf}→ SubItem` (as delivered); `Event –EVIDENCE_FOR→ Defect`; `Defect –REPEAT_OF→ Defect`;
  `Defect –RESOLVED_BY→ Action`; `Action –REMOVED / INSTALLED→ Serial`; `Serial –SHOP_RESULT→ ShopFinding`
  (via job_no + serial + time); `Action –PER→ Procedure` (from text); `Order –CAUSED→ Action`;
  `Tail –HAS_CONFIG{interval}→ ConfigState`; `Tail|Serial –EMBODIES{interval}→ Modification`;
  `Procedure –APPLIES_IF→ ApplicExpr`; `Tail –DONOR_FOR{job, linked_job}→ Tail` (schema only);
  `Defect –SIMILAR_TO{score}→ Defect` (materialised for case-based reasoning).

**What each consumer gets from this one graph:** isolation = engineering layer + instance evidence; lineage =
INSTALLED_ON / REMOVED / SHOP_RESULT; applicability = as-of HAS_CONFIG / EMBODIES / INSTALLED_ON evaluated against
APPLIES_IF; the 3D view = Position –IN_ZONE→ Zone + component registry mesh ids; the assistant = typed tool
queries over all of it.

## Document applicability (S1000D, thin)

S1000D models applicability with ACT (product attributes), CCT (conditions — mods, service bulletins) and PCT
(product instances with attribute values and condition states); data modules carry `<applic>` boolean expressions
evaluated against the PCT row, so applicability updates without reissuing content (S1000D Issue 7 is current;
configuration status accounting per MIL-HDBK-61B). Our formulation: an as-of **configuration snapshot** of the
tail (installed part numbers and serials, embodied mods, `sw_config_id`) plays the PCT role; each `Procedure`'s
`ApplicExpr` is a small JSON boolean expression evaluated against it. No rules engine, no full S1000D tables.

## Technology

| Option | Licence / status (Oct 2026) | Decision |
|---|---|---|
| **DuckDB node/edge tables** (system of record) + **NetworkX** (BSD-3) built in memory per as-of query | MIT / BSD-3; < 10k nodes; no server | **Adopt** |
| LadybugDB (MIT fork of Kùzu; embedded Cypher; v0.21, Oct 2026) | young project — pin the version, keep a tested export path to DuckDB | optional Cypher layer for the demo/assistant |
| DuckDB + DuckPGQ (SQL/PGQ) | self-declared research project | ad-hoc exploration only |
| Kùzu | **archived 2025-10-10** | do not start on it |
| Neo4j Community | GPL-3.0, JVM server | acceptable only if the team wants Bloom-style visuals and accepts a server in the handover |
| Memgraph | BSL 1.1 — Additional Use Grant forbids embedding/distributing to third parties | avoid (handover to MoD is distribution) |
| FalkorDB | SSPLv1, Redis dependency | avoid |
| Apache AGE | Apache-2.0, Postgres extension | only if we already ran Postgres |

## Key sources

- Mack et al., IEEE T-ASE 14(1) 2017 (777 CMC reference model + reasoner) — doi:10.1109/TASE.2016.2542186
- Deb, Pattipati et al., multi-signal flow graphs, IEEE AES Magazine 10(5) 1995; NASA/QSI TEAMS — https://spinoff.nasa.gov/node/10206
- IEEE 1232 (AI-ESTATE); Sheppard et al., IEEE Aerospace 2009 — https://www.cs.montana.edu/sheppard/pubs/aero-2009.pdf
- S1000D applicability — https://help.adobe.com/en_US/framemaker/s1000d/WS9ad62b8fb4f8a997-577b0a7d12e234e8c0d-8000.html ; S1000D Issue 7 — https://www.s-series.org/news-and-events/news/s1000d-issue-7-now-available-on-s1000dorg/
- S5000F — https://s-series.org/s5000f ; ATA Spec 2000 Ch. 11 — https://publications.airlines.org/products/spec-2000-reliability-data-collection-exchange-ch-11-revision-2023-1
- IOF Maintenance Reference Ontology — https://spec.industrialontologies.org/portal/release/202601/maintenance.html ; Woods et al., Semantic Web 15 (2024) — doi:10.3233/SW-233299
- Microsoft GraphRAG — https://arxiv.org/abs/2404.16130 ; Han et al., RAG vs GraphRAG — https://arxiv.org/abs/2502.11371 ; GraphRAG-Bench — https://arxiv.org/abs/2506.05690 ; Scaffidi et al., TGDK 3(2) 2025 — https://drops.dagstuhl.de/entities/document/10.4230/TGDK.3.2.3
- NetworkX — https://github.com/networkx/networkx ; LadybugDB — https://github.com/LadybugDB/ladybug ; Kùzu (archived) — https://github.com/kuzudb/kuzu ; DuckPGQ — https://github.com/cwida/duckpgq-extension
