# 09 · What this means for our solution, and open questions

This is our interpretation of the data layer for building our solution. It is understanding, not a
design: it maps the PS onto the data layer, lists the consumer rules we must not break, and records what we
still need from the data-layer team.

## The PS mapped onto the data layer

| PS phrase | Real-world system | Where it lives in Phalanx |
|---|---|---|
| "aircraft health-monitoring systems" | ECMS/HUMS, FDR/CDR, BIT, CWS | `param.samples` (sampled sorties), `events.bit_faults` / `.exceedances` / `.cautions`, `usage.counters` |
| "technical records" | IAF e-MMS, F700-style tech log, log cards | `maint.records`: SORTIE, TECH_LOG, DEFECT_WO, COMPONENT_LIFE, INSPECTION, MODIFICATION, EXCEEDANCE_INSPECTION |
| "spares" | IMMOLS, equipment depots, AOG demands | `maint.records`: SUPPLY_DEMAND (AOG/MCM/PHU), CANNIBALISATION; orders REQUISITION/EXPEDITE/TRANSFER_STOCK |
| "maintenance agencies" | squadron / BRD / HAL / OEM | `maint.records`: SHOP_FINDING (CONFIRMED/RTOK/BCM), NMCD depot state; **single-echelon PROXY** today |
| "not adequately integrated" | silos | the contract's linkage keys (tail, sortie, serial triplet, job/demand no., `evidence_record_ids`, `order_id`) are exactly the integration seams |
| "delayed fault prediction" | reactive maintenance | latency chain: sortie → download (≥ 10 min, ~2 h typical) → event review (+0.33 h) → defect → troubleshoot → spares lead time |
| "avoidable downtime, sub-optimal utilisation" | low serviceability | SCIR availability states + KPIs (`mc`, `fmc`, `nmcs`, `nmcm`, `nmcd`, `aog_days`, `cann_rate`, `flying_task`) |
| "AI/ML predictive maintenance, IoT/HM, digital twin, integrated analytics" | | ML on contract data; the data layer's own fork service is a world twin we can drive; our twin = per-serial belief state |

## What the data will look like when it arrives

- **Dense, fleet-scale:** `maint.records`, `usage.counters`, `events.*`, `sortie.manifest` for all sorties
  (usage mode).
- **Sparse, high-rate:** `param.samples` only for sampled sorties and fault-onset/exceedance windows
  (telemetry mode), plus event snapshot windows (−5 s / +25–35 s).
- **Imperfect on purpose:** immature/mature BIT false-alarm regimes, NFF/RTOK, unflagged texture artefacts,
  clock-domain misalignment, record defects (CANN under-reporting, missing part records, `XXX` serials,
  duplicate snags, 14-day lag, noisy free text), sink fragmentation.
- **Latent truth is rich:** 50 hidden states, 83 fault modes, separate sensor bias vs deterioration — so
  credible RUL/health estimation and diagnosis can be *scored* against `labels.truth` offline.

## Consumer rules we must not break (engineering checklist)

1. Pin contract 0.1.0 + its hash; validate every file's schema metadata; carry `dict_version`/`dict_hash`.
2. Everything "as of" `t_ingest` (features, labels, KPIs, orders). Build the pipeline around an
   `as_of(t)` observation view from day one.
3. Dedupe by `record_id` (earliest ingest); expect re-downloads, partial downloads and late rows.
4. Never cross-match fast-path and full-path rows by `record_id`.
5. Time = int64 ns; never compare `t_record` across recordings; local ops time is IST.
6. Mask sentinels, respect validity, keep OUT_OF_RANGE, detect unflagged freezes/glitches.
7. Resample per clock domain explicitly; channels are not synchronous.
8. Treat serials as opaque; build per-serial histories (installs/removals) — health follows the serial.
9. Counters are cumulative; diff per serial, handle renewals/swaps.
10. `maint.records` are versioned; current state = max `record_version` per (`record_type`, `record_key`) as of t.
11. `confirmed_status` on events is always UNCONFIRMED; confirmation comes later via maintenance records.
12. `detection_far_per_fh` is the *nominal* spec rate, not the true one — estimate real FAR from data.
13. Labels from observable outcomes only; `labels.truth` and oracle forks for evaluation only.
14. Orders: `t_issued` = session time, evidence must be ingested, per-action schema, authority (HUMAN-only
    actions), applied at 08:00 IST epochs; handle REJECTED with reasons.
15. Everything is synthetic — say so in any demo; don't present codes/ICD as real Tejas/IAF data.
16. Bottom-of-scale values are ambiguous: slip sentinel (flag is a decoder heuristic on the full path) vs a
    genuine open-circuit / probe-short sensor fault, which also reads bottom of range.
17. Know which mode produced the data (usage vs telemetry; Tejas vs proxy). Usage-mode health is driven by an
    expanded sortie summary (EOT = 1.35 × flight time; Nz crossings a lower bound), not by telemetry.
18. Normalise time zones: ops planning is at 00:00 UTC, waves in UTC, night wave and decision epoch in IST.
19. Don't trust early-run age↔health relations: units installed at t = 0 are new in M10 but M18 assigns them a
    random life fraction (see [08](08-assumptions-and-limits.md) contradiction 7).
20. Several registry contradictions (validity-bit decode, thresholds, drop tanks, EOT ratio) are unresolved —
    see [08](08-assumptions-and-limits.md) before hard-coding any of them.

## Opportunities the data layer makes possible

- **Prediction lead time vs logistics lead time:** supply lead times are explicit (log-normal, CAG-anchored ×
  OEM factor, priority multipliers). A prediction is only worth something if it fires early enough to
  requisition/expedite before the failure → we can quantify "useful lead time" per part class.
- **NFF reduction:** RTOK outcomes are truth-driven; a model that suppresses false-alarm-driven removals has a
  measurable KPI (man-hours, cann rate, availability).
- **Belief-state digital twin:** the fork service accepts a pluggable `BeliefPosterior` — our per-serial health
  posterior can drive belief forks to evaluate decisions under uncertainty, honestly (no oracle).
- **Policy comparison with CRN:** paired KPI deltas with CIs vs `StatusQuoPolicy` / `ScheduledPolicy` /
  `ConditionBasedPolicy` — a rigorous "we improve availability by X ± Y" claim.
- **Real-data readiness:** if our ingestion respects the contract, future real ECMS/HUMS extracts decoded to the
  same contract plug in unchanged (P5) — a strong story for DSSC/IAF judges.

## Open questions for the data-layer team

1. **Interface across repos:** how do we submit orders and request forks from a separate repo — import
   `phalanx` as a library (in-process `OpsSession`/`ForkService`), or a service wrapper? Which Python/NumPy
   versions are pinned (bitwise claims are darwin-arm64, NumPy 2.5.4)?
2. **Dataset delivery:** when is the first calibrated fleet dataset (consumer tree) expected, at what scale
   (tails × years), and which sorties/windows get telemetry? Can we get an *early* usage-mode fleet run (M18 +
   fixture fleet already works) to start on records/availability now?
3. **Not-simulated channels:** how will the contract mark them (W2.2 coverage plan)? Until then, which of the
   464 channels will actually carry data (261 had no producer at Wave-1 exit)?
4. **Vibration / oil debris observability:** the dictionary defines the lube/vibration channels we need —
   `ENG.OIL_P`, `ENG.OIL_T`, `ENG.OIL_LEVEL`, `ENG.CHIP` (chip detector discrete), `ENG.VIB.OVERALL` /
   `N1_1REV` / `N2_1REV` (in/s, 1 Hz features from the HF front end), and ground inspection channels
   `MX.SOAP.FE` (ppm), `MX.OIL_SERVICING.ENGINE|AMAGB|JFS` (oil added, L — i.e. oil consumption),
   `MX.BORESCOPE`, `MX.BRAKE_WEAR`, `MX.TYRE_P.*`, `MX.ACCUM_PRECHARGE`. But at the snapshot M12 does not
   model `ENG.VIB.*`, the vibration source is a PROXY with no unbalance/fault terms (A-W1.3a-14), and spall /
   oil-Fe are hidden states without ports. Which of these will carry fault-driven signal, and **how do `MX.*`
   inspection values reach the contract** (their transport is `maint_record`, but `maint.records` has no
   generic measurement-value column)? This is the canonical PdM story (cf. AL-31FP oil-chip failures).
5. **Events on the full path** (W2.2) and **contract 0.2.0** (sink id): timeline, and will 0.1.0 consumers be
   served both?
6. **Code-table collision** (M08 vs M14 `ENG-5xx`): when does the unified dictionary table land (0.1.3?)?
7. **`sortie.manifest`:** which module will emit it, and when?
8. **Labels access for evaluation:** how do we get a restricted `labels.truth` tree for offline scoring (who
   holds it, what audience/process)?
9. **Decision epochs:** is the daily 08:00 IST epoch fixed, or can we request more frequent epochs (e.g.
   sortie-boundary decisions)?
10. **Multi-echelon supply:** is replacing the single-echelon PROXY (base/BRD/HAL/OEM) planned? The PS
    stresses "maintenance agencies", so agency turnaround realism matters for our demo.
