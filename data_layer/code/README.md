# Phalanx

Problem statement (Ministry of Defence / Defence Services Staff College):
*Air Power – Predictive Maintenance & Fleet Availability*.

The first deliverable is **not** the predictive-maintenance AI. It is a realistic aircraft
data-generation and data-streaming layer: a virtual aircraft whose physical and operational state
produces observations (sensor, bus and recorder data, BIT/fault events, maintenance records) that
resemble what a real aircraft generates.

> We are not generating random numbers that look like aircraft data. We are building a virtual
> aircraft whose physical and operational state produces observations that resemble the data a
> real aircraft would generate.

## Status

**Research phase complete.** Target: a "Tejas-class" virtual fighter — HAL Tejas Mk1A with the
GE F404-GE-IN20 modelled as a "composite F404". Implementation has not started.

| Where | What |
|---|---|
| [`reports/Virtual fighter telemetry layer research.md`](<reports/Virtual fighter telemetry layer research.md>) | The research report. It answers the 14 research questions and includes the decision register, prioritised gaps and next steps. **Start here.** |
| [`research_notes/Virtual fighter telemetry layer research/`](<research_notes/Virtual fighter telemetry layer research/>) | 22 evidence-tagged research notes behind the report |
| `research_notes/.../parameter_inventory.csv` | 189-parameter observable inventory (seed for the versioned parameter dictionary; a synthetic ICD, not the real Tejas ICD) |
| `research_notes/.../not_measured_states.csv` | 50 maintenance-relevant hidden states, the signals that partially reveal each one, and the inspection that confirms it |
| [`analysis/dashlink_texture/`](analysis/dashlink_texture/) | Reproducible measurement of real recorder-data texture on NASA DASHlink Tail 687 (scripts, pinned requirements, summary results) |

## Evidence conventions

Every claim in the notes and report is tagged:

| Tag | Meaning |
|---|---|
| `[DIRECT]` | About the Tejas, the F404-IN20 or the IAF itself |
| `[TRANSFER: x]` | Taken from platform or standard *x*, with the reason it transfers and its limits |
| `[MEASURED]` | Computed by Phalanx from real (non-fighter) data |
| `[ASSUMPTION]` | Engineering judgement, with a validation route |

Only officially released, unclassified material is used as evidence.

## Not in the repository

The `research_sources/` directory (≈2.5 GB of downloaded papers, reports, standards and the DASHlink
archive) is git-ignored for size and copyright reasons. Every source is cited by URL in the notes.
Documents with distribution limitations are quarantined locally and are not cited.
