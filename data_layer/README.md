# Phalanx data layer: self-contained preview (v0.9, 2026-10-15)

This folder holds the code that generates the data and a preview dataset, so you can work with the data layer
without the development repository.

| Folder | What it is |
|---|---|
| `code/` | The full data-layer code (development snapshot `fda9f98`). This is main `0476ed9` plus two fix branches that are not yet gated (the M05 actuator fix, the negative-AoA limiter and the M04 guidance redesign; the engine idle acceleration margin), plus the preview generator `tools/build_preview.py` |
| `data/v0.9/` | The preview dataset (3.4 GB). 3,536 files, all checked against `MANIFEST.json` sha256 after copying |

**The data is described in detail in** `code/docs/previews/v0.9_README.md`: every file, its row counts, the seeds,
how to read it, and 13 stated limitations.

**Contract:** `code/docs/contract/` (contract 0.2.0, frozen; Arrow, Avro and JSON-Schema schemas;
`MIGRATION.md`).

## Data

| Folder | Contents |
|---|---|
| `telemetry/` | 6 sorties: `param.samples` (163 M rows), `events.*`, `sortie.manifest` |
| `telemetry_full_path/` and `ch10/` | A 600 s window through bus, recorder and ground decoder, plus the IRIG 106 Ch10 file |
| `fleet/` | 8 tails × 180 days: `maint.records` (including availability states), `orders.*`, `events.*`, `usage.counters` |
| `_restricted_labels/` | Truth labels, **for evaluation only**. A real fleet never has these; never use them as model inputs |
| `_runs/` | The outcome of each run (completed or aborted, with the reason) |

**Reading a file:**
```python
import pyarrow.parquet as pq
t = pq.read_table("data/v0.9/telemetry/param.samples/...")
```

## Regenerating, or running the tests

You need Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
cd code && uv sync && make check
```

```bash
cd code && uv run python -I tools/build_preview.py --help
```

The run is deterministic: the same seeds give byte-identical files.

## Main limitations (full list in the data README)

- **Sorties:** only **1 of 6 completes**. The others crash in low-energy descents or circuits; their data up to the
  abort is kept.
- **Behaviour:** realism against real flights is **not yet validated**. Fan–core and EGT timing, and some engine
  fault signatures, are still being calibrated.
- **Fleet:** availability is uncalibrated, and the fleet worlds contain few persistent faults.
- **Telemetry folder:** it has no `usage.counters` rows yet, because of an end-of-sortie timing issue.
- **ICD and code tables:** synthetic; they are not the real Tejas ICD. The credibility ceiling is NASA-STD-7009B
  Level 2.

**Keep this folder private.** `code/research_notes/` and `code/reports/` contain internal evidence annotations
that must be purged before any public release.
