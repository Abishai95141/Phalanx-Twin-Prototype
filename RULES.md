# Phalanx Twin — working rules

**IBM Z Datathon entry** by **Team Dilijens** (theme: real-time AI for critical decisions), on the problem statement **"Air Power – Predictive Maintenance & Fleet Availability"**
(Ministry of Defence / Defence Services Staff College).
live prototype: https://148.100.99.205/

This repo builds the **downstream PdM + fleet-availability solution, "Phalanx Twin"**, and runs it end to end on
**IBM LinuxONE (IBM Z, s390x)**. It sits on top of the team's separate **Phalanx data layer** — a deterministic,
forkable simulator of a virtual Tejas Mk1A-class / F404-IN20 fleet.

**Platform framing (keep it in every README, doc, deck and screen text):** IBM Z / LinuxONE is the platform the
system is designed for, not just where it happens to run. Lead with why it fits a defence availability system
(availability, cryptography and audit, confidential computing, one consolidated system of record next to the data,
on-chip AI) and with what we proved on LinuxONE; mark platform features we do not use yet (Secure Execution, Crypto
Express, Telum AI accelerator, Maximo on Z) as roadmap; quote IBM's figures as IBM's claims with the source.
The full story and sources: `docs/ibmz/README.md`.

## Read first

- `docs/ibmz/README.md` — **Phalanx Twin on IBM Z and LinuxONE**: why IBM Z, what runs and was measured on
  LinuxONE, the s390x porting work, how each IBM Z capability strengthens each layer, roadmap, sources.

- `docs/architecture/README.md` — the solution architecture (what we build, why, and how it fits together);
  `docs/architecture/13-decision-register.md` — every decision with alternatives and revisit triggers.
- `docs/data-layer/README.md` — index of our understanding of the data layer;
  `docs/data-layer/11-preview-v0.9.md` — the dataset we build on now.
- **Preview data we build on (v0.9):** `data_layer/` in this repository.

## Non-negotiable rules when consuming the data layer

1. **Build only against the frozen contract** (`phalanx.ground_decoder_contract` **0.2.0**, hash `a4396f1d…`;
   dictionary tejas 0.1.3). Reject files whose schema metadata carries a different contract hash; read columns
   by name. Treat dictionary version/hash as part of every record.
2. **Information discipline:** any feature, label join, prediction or order at time t uses only records with
   `t_ingest ≤ t`. Never use event time alone. Orders citing un-ingested evidence are rejected.
3. **Never read `_restricted_labels/` or `labels.truth`** (or use oracle forks) in the system under test —
   evaluation harness only.
4. **Dedupe by `record_id`** (keep earliest `t_ingest`); `record_id` differs between fast and full paths.
   **Preview v0.9 exception:** the 8 fleet tails are separate worlds whose serials, job numbers and order ids
   collide — dedupe and key fleet records by (`tail_no`, `record_id`) and serials by (`tail_no`, `serial_no`).
5. **Quality:** no NaN exists — mask `SENTINEL`, treat `validity != NORMAL` as missing, keep `OUT_OF_RANGE`
   as signal; some artefacts (freezes, top-of-scale glitches) are deliberately unflagged.
6. **Serials are opaque and move between tails**; health follows the serial, not the tail.
7. **Decisions act only through `orders.commands`**; impact is shown with CRN-paired forks vs the
   `StatusQuoPolicy` baseline. Mods, software loads, monitoring-config changes and servicing deferrals need a
   HUMAN issuer.
8. Everything (ICD, codes, part numbers) is **synthetic**, and v0.9 behaviour is **not validated**; never
   present values as real Tejas/IAF data or as validated physics.

## Rules for IBM Z / LinuxONE (s390x, big-endian)

1. **Never read or write Parquet on s390x** — pyarrow on big-endian corrupts Parquet with nulls or lists. Runs are
   written as Arrow IPC (`proto/runner/ipcstore.py`); the preview is read from its IPC copy
   (`data/v0.9/fleet_ipc`). The contract-hash gate applies to both formats.
2. **One Anaconda environment** (`~/envs/phx`, `$PHX_PY`) — PyPI has no s390x wheels for the scientific stack. The
   simulator runs with the pure-Python numba stand-in (`PHX_NUMBA_SHIM=1`); zen-engine is built from source.
3. **Run heavy work on the server, not the Mac** — at most 2 worker processes (3 vCPUs, 7.8 GB). Use
   `proto/deploy/sync.sh --restart` after Python changes and `proto/deploy/services.sh reset` before a demo.
4. **Keep results reproducible across architectures** — any change that alters simulated records must still pass
   `proto/runner/gonogo.py` (row-for-row equality with the reference) on LinuxONE.
