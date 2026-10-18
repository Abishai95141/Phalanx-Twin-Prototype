# 02 · The digital twin: what it rigorously is, and what it is not

The team's framing is "a full-fledged solution with a digital twin". The research supports that framing — if
"twin" is defined precisely and claimed honestly. This doc fixes the definition every other doc uses.

## Definition

> **Phalanx Twin** is a predictive, decision-support digital twin of a (simulated) Tejas Mk1A-class fleet. It
> is a set of probabilistic information constructs — the **digital state** — that mirrors each aircraft's
> as-maintained configuration, usage, condition evidence, per-serial health and work/availability state. It is
> updated only from contract records ingested by the as-of time, synchronised **per sortie download and per
> daily decision epoch**. It informs — and, within the authority the data layer allows, issues — maintenance
> and logistics orders whose fleet-level value is quantified by paired what-if simulation.

Adapted from AIAA/AIA *Digital Twin: Definition & Value* (2020) — "a set of virtual information constructs that
mimics the structure, context and behavior of an individual/unique physical asset, or a group of physical
assets, is dynamically updated with data from its physical twin throughout its life cycle and informs decisions
that realize value" — and from NASEM *Foundational Research Gaps and Future Directions for Digital Twins* (2024),
which requires predictive capability, bidirectional interaction and **uncertainty quantification as an integral
part** of the twin.

## The four things in the picture (and only one of them is "the world")

| Layer | What it is | Grieves term | Built from |
|---|---|---|---|
| **World** (not our twin) | The Phalanx simulator: stands in for the physical fleet; its hidden state (true health, fault schedule) is `labels.truth` | the physical asset | — (we only observe it through the contract) |
| **Asset twin** | One per tail **and one per serial** (health follows the serial): configuration graph (which serial is in which inferred position at t), usage/life clocks, condition evidence, health posterior with uncertainty, open work, availability state | Digital Twin Instance | contract topics, as of t |
| **Fleet twin** | Aggregate of asset twins + shared context: SCIR availability, part-class reliability and NFF rates, spares pipeline, plan | Digital Twin Aggregate | asset twins + supply records |
| **Simulation twin** | The data layer's fork service run in **belief mode** with *our* posterior plugged in as the `BeliefPosterior`, comparing order sets with CRN-paired KPI deltas | — | fleet twin snapshot + candidate orders |

The probabilistic-graphical-model framing of Kapteyn, Pretorius & Willcox (*Nature Computational Science*,
2021) maps one-to-one onto our system and is the vocabulary we use with judges:

| PGM node | In Phalanx |
|---|---|
| Physical state S | simulator truth (hidden health, faults) — scoring only |
| Observed data O | contract topics read as of `t_ingest ≤ t` |
| **Digital state D** | **our** per-serial health posterior + as-maintained configuration + usage + work state |
| Control U | `orders.commands` (18 actions; AGENT or HUMAN issuer) |
| Quantities of interest Q | risk/remaining life per serial, NMC drivers, spares need |
| Reward R | fleet KPIs (MC/FMC, NMCS/NMCM, AOG days, man-hours, cannibalisation) from forks |

**Testing our twin against a simulated world is legitimate**: it is what the simulation literature calls a
*perfect-model experiment* (Marquardt, Cleophas & Morgan, WSC 2021), and it gives us the VVUQ that NASEM calls
essential — we score D against S offline, using `labels.truth` only in the evaluation harness.

## Twin state (the one state everything reads)

Per epoch, the twin state is materialised as versioned tables keyed by (`scope`, entity, `as_of`):

| Facet | Contents | Produced by |
|---|---|---|
| Configuration | serial ↔ position ↔ tail intervals, `sw_config_id`, mods, inferred positions | entity resolution ([03](03-data-foundation.md)) |
| Usage & life | per-serial usage clocks (EOT, TAC, LUIs, landings, Nz crossings), servicing due-dates, hard-time margins | counters + records |
| Condition evidence | BIT/caution/exceedance episodes, parameter-residual trends, inspections, shop findings | monitoring ([04](04-condition-monitoring-and-diagnostics.md)) |
| Health belief | P(removal/failure by cause within H), remaining-life quantiles, P(defect is NFF), engine health indices (later) — each with uncertainty and model version | prediction ([05](05-prediction.md)) |
| Work & availability | open/deferred/AWP jobs, SCIR state and NMC driver, open demands | records |
| Data quality | flags (inferred positions, repaired serials, sentinel share, aborted sortie, preview maturity) | foundation |

Every consumer — the 3D view, the component panel, triage, the planner, forks, the assistant — reads this
state through the same `as_of` API. That is what makes the system cohesive: there is no second source of truth.

## Synchronisation and integration level (stated, not implied)

- **Physical → digital: automatic, sortie-synchronous.** A sortie's data arrives at its download `t_ingest`
  (hours after landing; ≈ 18.6 h for TJ212 in the preview); the twin is recomputed for the 08:00 IST epoch. It is
  **not real-time** — fighter data does not stream in peacetime, and ISO 23247/ISO/IEC 30173 both ask that the
  synchronisation rate be stated explicitly. The UI shows per-tail "as of" and "last ingest".
- **Digital → physical: through orders.** Automatic only for actions the authority matrix allows an AGENT to
  issue *and* that our policy lifecycle has promoted to "exception" mode (see [07](07-triage-policy-decision-loop.md));
  everything else is decision support with human approval. In Kritzinger et al.'s (2018) terms we are a **twin
  for AGENT-authority actions and a shadow for HUMAN-only actions** — which is exactly right for an
  airworthiness-adjacent system.
- **Indolence is fatal** (Marquardt et al.): the twin must be revalidated when the world changes — new data
  release, contract/dictionary version, modification, software load. Those are explicit change-points in
  [08](08-learning-and-assurance.md).

## Maturity (honest)

| Ladder | Our level | Why |
|---|---|---|
| Descriptive → informative → predictive → comprehensive → autonomous | **Comprehensive** (what-if via belief forks) | predictive + what-if simulation with data assimilation |
| Arup (2019) metrics | Autonomy 2–3, Intelligence 3, Learning 3 (supervised), **Fidelity 1–2** | fidelity bounded by the data layer's NASA-STD-7009B Level 2 ceiling against proxy data, which v0.9 does not yet reach |

## Claims we can and cannot make

**Can (once built):** automated sortie-synchronous synchronisation; probabilistic per-serial state with explicit
uncertainty; diagnostics, prognostics and prescriptive recommendations; what-if evaluation of decisions; a
closed loop through typed orders with human authority for designated actions; offline validation against hidden
truth; contract-level readiness for real data (the contract is designed so real ECMS/HUMS extracts decode into
it unchanged).

**Cannot:** a multiphysics or structural twin of the Glaessgen & Stargel (2012) kind; real-time; validated
accuracy (B1–B9 not passed; availability uncalibrated); real geometry or internal layout; per-location fatigue
(Nz counters are per tail, not per location); cross-tail serial lineage on v0.9 (per-tail worlds); real Tejas or
IAF data; "autonomous".

## The 3D view's role (detail in [11](11-ui-ux.md))

Industry health-monitoring products (Airbus Skywise Health Monitoring, Lufthansa Technik AVIATAR, GE, Rolls-Royce)
are overwhelmingly 2D; HCI evidence (St. John et al. 2001; Tory et al. 2006; Cockburn & McKenzie 2002; Munzner's
"no unjustified 3D") says 3D helps with *where* and *what is near*, and hurts precise comparison; combined 2D+3D
displays do best. So in Phalanx Twin the 3D aircraft is a **spatial index and lens over the twin state** — every
colour, badge and line is computed from the twin at the as-of time, clicking any mesh opens the same panel as
searching for it, and all numbers live in linked 2D panels. It must pass the acceptance tests in [11](11-ui-ux.md).

## Key sources

- AIAA & AIA, *Digital Twin: Definition & Value* (2020) — https://www.aia-aerospace.org/wp-content/uploads/Digital-Twin-Institute-Position-Paper-December-2020-1.pdf
- NASEM, *Foundational Research Gaps and Future Directions for Digital Twins* (2024) — https://www.nationalacademies.org/read/26894/chapter/4
- Glaessgen & Stargel, AIAA 2012-1818 — https://ntrs.nasa.gov/citations/20120008178
- Kapteyn, Pretorius & Willcox (2021) — https://doi.org/10.1038/s43588-021-00069-0
- Kritzinger et al., IFAC-PapersOnLine (2018) — doi:10.1016/j.ifacol.2018.08.474
- Marquardt, Cleophas & Morgan, WSC 2021 — https://www.informs-sim.org/wsc21papers/233.pdf
- Grieves & Vickers (DTP/DTI/DTA) — https://diginomica.com/grieves-and-vickers-history-digital-twins
- Arup, *Digital Twin: Towards a Meaningful Framework* (2019) — https://arup.com/globalassets/downloads/insights/digital-twin-towards-a-meaningful-framework.pdf
- AFRL Airframe Digital Twin / ASIP (MIL-STD-1530) — https://www.afgrow.net/applications/DTDHandbook/sections/page1_2.aspx
- GAO-20-316 (F-35 ALIS data integrity lesson) — https://www.gao.gov/products/gao-20-316
