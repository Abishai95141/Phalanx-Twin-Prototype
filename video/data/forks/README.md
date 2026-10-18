# What-if fork results for the three demo decisions (S1–S3)

> **PREVIEW v0.9 simulator: synthetic fleet, behaviour not validated.** Every number here comes from a real
> run of the Phalanx data layer's own fork service (`phalanx.fork`), done in-process on the v0.9 preview code
> snapshot. Tails, codes, part numbers and the ICD are synthetic. The availability model is not calibrated.
> `cost` is a unitless relative proxy (assumption A-W1.8-11), not money. Do not present any value as real
> Tejas or IAF data, or as validated physics.

## Headline results

Decision epoch **2026-06-22 08:00 IST**. Horizon **30 days**. **n = 30 CRN pairs** (members 0–29). Δ = treatment
minus status quo, with a Student-t 95 % CI over the pairs.

**Mode labelling.** The `belief` numbers are the in-loop what-if, the ones the product may show. The
`ensemble` numbers are offline evaluation only. In every scenario the two modes came out **identical**: all
record digests matched, member by member. The caveats below explain why, and what that means for the claim
"belief mode".

### S1 · TJ107: HUMAN `CHANGE_MONITORING_CONFIG {filter_codes_add:["HYD-101"]}` + AGENT `TROUBLESHOOT {code:"HYD-101"}`

Both orders were ACCEPTED at 08:00 and reached COMPLETED in 30/30 members. Troubleshooting finished at 10:04
IST. Snapshot `366d18f6…124fb`. Evidence: the 6 most recent HYD-101 `events.bit_faults` rows (sorties of 11,
15 and 18 June). 63 HYD-101 BIT rows had been ingested by the epoch.

| KPI (TJ107, 30 d) | Status quo mean [95 % CI] | Treatment mean [95 % CI] | **Δ mean [95 % CI]** (belief = ensemble) |
|---|---|---|---|
| mc | 0.630 [0.593, 0.668] | 0.848 [0.811, 0.884] | **+0.217 [+0.167, +0.268]** |
| fmc | 0.628 [0.591, 0.665] | 0.819 [0.782, 0.856] | **+0.191 [+0.142, +0.240]** |
| nmcs | 0.165 [0.123, 0.207] | 0.042 [0.008, 0.077] | **−0.123 [−0.176, −0.069]** |
| nmcm | 0.205 [0.194, 0.216] | 0.110 [0.098, 0.122] | **−0.095 [−0.109, −0.081]** |
| aog_days | 4.95 [3.69, 6.21] | 1.27 [0.24, 2.30] | **−3.68 [−5.27, −2.08]** |
| man_hours | 339.9 [324.0, 355.7] | 224.2 [209.4, 238.9] | **−115.7 [−132.6, −98.7]** |
| cost (relative proxy) | 7.23 [5.74, 8.71] | 3.38 [3.20, 3.55] | **−3.85 [−5.41, −2.29]** |
| flown_fh | 11.87 [11.23, 12.52] | 18.50 [17.36, 19.64] | **+6.63 [+5.31, +7.94]** |
| sorties | 14.0 | 21.7 | +7.7 [+6.2, +9.2] |
| in_flight_failures | 0.033 (1 in 30 runs) | 0.100 (3 in 30 runs) | **+0.067 [−0.028, +0.161]** (not significant; see caveats) |
| removals (derived) | 11.5 | 10.2 | **−1.27 [−2.27, −0.26]** |

Most of the removals effect is hydraulic pumps: 5.17 → 0.43 SYN-PN-HYDP removals per 30 days. Tyre and brake
removals go up (5.33 → 8.07 and 0.43 → 0.97) because the aircraft flies more. With only the first 10 pairs,
the nmcs and aog_days differences have CIs that include 0 (−0.073 [−0.178, +0.033] and −2.18 [−5.35, +0.99]).
That is one reason n = 30 was run.

### S2 · TJ108 (NMCS since 2026-04-03 08:00 IST): AGENT `EXPEDITE_SPARES {demand_no:"D-sulur-26093-0002"}`

The order was ACCEPTED and COMPLETED at 08:00 in 30/30 members. Snapshot `79838678…1392b`. The expedited
demand is the AOG brake-chute demand of U/S job `sulur-26093-0003`. Evidence: that SUPPLY_DEMAND record, the
DEFECT_WO record and the latest TECH_LOG record.

| KPI (TJ108, 30 d) | Status quo | Treatment | **Δ [95 % CI]** |
|---|---|---|---|
| aog_days | 30.0 | 30.0 | **0 [0, 0]** |
| nmcs | 1.000 | 1.000 | **0 [0, 0]** |
| mc / fmc / nmcm | 0 / 0 / 0 | 0 / 0 / 0 | **0 [0, 0]** |
| flown_fh | 0 | 0 | **0 [0, 0]** |
| cost (relative proxy) | 0.778 | 0.778 | **0 [0, 0]** (the expedite premium is booked only when the demand closes) |

**Over the next 30 days the expedite changes nothing.** M18 halves the demand's *remaining* lead time
(`expedite_factor` 0.5), but the chute still arrives long after the window.

The supplementary 400-day run (`scenario_S2_h400.json`, n = 10, 2026-06-22 → 2027-07-27, belief = ensemble)
shows the size of the effect:
- In the status quo, TJ108 leaves NMCS on **2027-07-06 21:30 IST** in every member, when an MCM replenishment
  chute arrives.
- With the expedite it leaves NMCS on **2027-04-12 07:30 IST**, 85 days earlier.
- Over the 400 days: aog_days Δ **−62.1 [−83.8, −40.4]**, mc **+0.137 [+0.089, +0.185]**, flown_fh **+33.8
  [+22.1, +45.5]**, cost **+12.3 [+7.5, +17.0]**. Cost rises because the aircraft flies and is maintained
  again, and the premium is booked.
- in_flight_failures Δ +0.3 [−1.0, +1.6].

The honest demo message: expediting alone does not return TJ108 within a month. In these single-tail worlds
cannibalisation or a stock transfer is not available as an alternative (see caveats).

### S3 · TJ105 (7 of 8 landings on the fitted tyre): AGENT `REQUISITION_SPARES {part_no:"SYN-PN-TYRE", quantity:2}`, target_base `sulur`, priority MCM

The order was ACCEPTED in 30/30 members. Both tyres arrived within the window (COMPLETED) in 16 members; in
the other 14 the order was still QUEUED at the window end. Snapshot `9f1ecc80…ce3f5`. Evidence: the last tyre
INSTALL record plus the 6 SORTIE records since it.

| KPI (TJ105, 30 d) | Status quo mean [95 % CI] | Treatment | **Δ [95 % CI]** |
|---|---|---|---|
| nmcs | 0.017 [0.002, 0.031] | same | **0 [0, 0]** |
| aog_days | 0.49 [0.05, 0.94] | same | **0 [0, 0]** |
| mc | 0.317 [0.272, 0.362] | same | **0 [0, 0]** |
| fmc / nmcm / flown_fh | 0.309 / 0.666 / 7.97 | same | **0 [0, 0]** |
| cost (relative proxy) | 7.11 [5.50, 8.72] | 7.40 [5.80, 9.00] | **+0.287 [+0.236, +0.337]** |

**The requisition buys nothing in this world.** In all 30 members the base already holds the tyres for
TJ105's next hard-time change: no tyre job waited for parts in either arm. The only effect is the cost of the
two tyres, booked when they arrive. This is a useful negative what-if, not a showcase gain. The small NMCS in
both arms comes from other parts.

### Timings (wall clock, Apple M4, other jobs running, load average about 10; every process `nice 10`, single thread)

| Step | Time |
|---|---|
| Rebuild a tail world and run it to the epoch (168 days, closed loop) | 5.5–13.6 s (about 7 s unloaded) |
| `ForkService.snapshot` | about 4 ms |
| 30-day branch, belief / ensemble, mean (max) | S1 4.2 (9.7) / 2.8 (4.6) s; S2 1.0 (1.7) / 1.1 (2.7) s; S3 3.2 (7.2) / 2.0 (3.5) s |
| 30-day pair (both arms), belief mode, mean (max) | S1 8.3 (15.0) s; S2 2.1 (3.0) s; S3 6.3 (13.8) s |
| 400-day branch (S2 supplementary), mean (max) | 15.3 (27.7) s |
| Whole scenario: 30 pairs × 2 modes + oracle check | S1 436 s, S2 145 s, S3 336 s (three processes in parallel) |

Per-branch and per-pair times for every member are in `scenario_*.json` under `members[].wall_s`.


## Files

| File | Content |
|---|---|
| `results.json` | The summary. Per scenario and mode: arm means with 95 % CIs, CRN-paired differences with 95 % CIs (all 14 KPIs), the first-10-pair differences, order payloads, evidence `record_id`s, snapshot id, gateway verdicts, order end states, timings, and the reproduction checks. |
| `scenario_S1.json`, `scenario_S2.json`, `scenario_S3.json` | Raw data for each member: KPIs of both arms, record digests, order-log hashes, `orders.status` trails, root, and wall time per branch. |
| `scenario_S2_h400.json` | Extra S2 run over a 400-day horizon (n = 10). See S2. |
| `reproduction_TJ101.json` … `reproduction_TJ108.json` | Reproduction of each preview tail world up to the decision epoch. |
| `belief_check.json` | Which modules' state the reference belief posterior changes at the snapshot (module names only). |

Scripts (in `video/tools/forks/`): `phx_forks.py` (world, session, fork service), `reproduce.py` (step 1),
`run_forks.py` (step 2), `belief_check.py` (posterior footprint), `assemble.py` (step 3), `run.sh` (environment wrapper), `requirements.lock.txt`
(exported from the data layer's `uv.lock`).

```sh
cd video/tools/forks
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.lock.txt
./run.sh reproduce.py TJ101 TJ102 TJ103 TJ104 TJ105 TJ106 TJ107 TJ108
./run.sh run_forks.py S1 --n 30 --modes belief,ensemble --horizon-days 30     # same for S2, S3
./run.sh run_forks.py S2 --n 10 --modes belief,ensemble --horizon-days 400 --fleet-days 600 --tag _h400 --no-oracle-check
./run.sh belief_check.py TJ107 TJ108 TJ105
./run.sh assemble.py
```

`run.sh` puts `.../phalanx_data_layer_preview/code/src` on `PYTHONPATH`. It also sets
`PYTHONDONTWRITEBYTECODE=1` and points `NUMBA_CACHE_DIR` at `video/tools/forks/.numba_cache`, so nothing is
written into the read-only preview folder. A `find -newer` check after all the runs found no changed or new
files there. Python 3.12.12; packages are pinned exactly as in the data layer's `uv.lock` (numpy 2.5.4, scipy
1.18.1, pyarrow 26.0.0, numba 0.68.0).

## How the numbers were produced

1. **World.** Each tail's world is built by the preview builder's own function, `_fleet_world(k, days)`,
   loaded from `code/tools/build_preview.py`. It uses the real M02, M10, M11 and M14 for that tail, plus M18,
   M21 and the record sink. The settings match the preview: scenario key `preview09-ops`, root `0x9F1EE7`,
   start 2026-01-05, M14 regime `immature`, and the M18 `DefectInjector` with the same root.
2. **Run to the decision epoch.** The builder's loop runs `ScheduledPolicy` (`scheduled/1.0.0`) at every
   08:00 IST decision epoch, up to **2026-06-22 08:00 IST** (02:30Z, kernel t = 168 d 2.5 h). Events at that
   instant are not yet processed. A `SessionSnapshot` is taken there. Its content hash is in `snapshot_id`.
3. **Orders.** Orders are built only from the session's observation set as of the epoch
   (`obs.as_of(t_issued, …)`), never from truth. `t_issued` = `t_effective` = the epoch. Every evidence
   `record_id` was ingested by `t_issued`. The gateway accepted every order (verdicts are in `results.json`).
   `CHANGE_MONITORING_CONFIG` has a HUMAN issuer (`HUMAN-ENGG-OFFICER`). The other orders are AGENT
   (`PHALANX-PDM-AGENT`, `policy_version` `phalanx-solution-demo/0.1`).
4. **Arms.**
   - Status quo: `ScheduledPolicy` at every decision epoch in the window, with no extra orders. This is
     exactly the preview's policy. It equals `StatusQuoPolicy` plus fixed-interval engine wash and borescope.
   - Treatment: the same policy plus the scenario's orders, issued at the epoch.
5. **Pairs.** Members m = 0…29 are run in both arms from the same snapshot. Member m of both arms shares one
   exogenous future (root = `member_root(0x9F1EE7, "preview09-ops", m)`, a SeedSequence spawn key), so the
   comparison uses common random numbers (CRN). `ForkService.compare(paired=True)` returns, for each KPI, the
   mean of treatment minus status quo, the sd, and a Student-t 95 % CI (`M22.yaml` `ci_level` 0.95). The
   request asked for n = 10. Branches were cheap, so n = 30 was run. The first 10 pairs (members 0–9) are
   also reported in `results.json` under `paired_difference_first_10_pairs`. The horizon is 30 days:
   2026-06-22 08:00 → 2026-07-22 08:00 IST.
6. **Modes.**
   - `belief`: the in-loop number, the one the product can show. It uses `BranchSpec(mode="belief",
     belief=SurvivalPosterior("m10"))`, the data layer's reference posterior, then runs as ensemble member m.
   - `ensemble`: offline evaluation only. It starts from the true snapshot state, which is privileged
     information a deployed product would not have.
   - `oracle`: one status-quo run per scenario, used only to check that the fork continues the published
     preview bit for bit. Its results are never reported as what-if numbers.
7. **KPIs.** The data layer's `compute_kpis` computes them from each branch's record log over the window, for
   the one tail in the world. `mc`, `fmc`, `nmcs`, `nmcm` and `nmcd` are fractions of the window (0–1).
   `aog_days` is aircraft-days in NMCS. `man_hours` counts hours on jobs closed in the window. "Removals" is
   not a KPI of the fork service, so it is not reported. Definitions are in `scenario_*.json` under
   `kpi_definitions`.

## Reproduction check (step 1)

All 8 tail worlds were rebuilt and run to the epoch. For each tail, **every consumer row ingested before
2026-06-22 08:00 IST is identical in every column** to the published `data/v0.9/fleet` tree. That covers
`maint.records`, `orders.commands`, `orders.status`, `events.bit_faults` and `events.cautions` (for example,
1,343 / 126 / 74 rows for TJ107). `orders.status` was compared as "every session row is in the preview tree",
because order ids collide across the preview's per-tail worlds.

The two named checks also match:
- **TJ107: 63 HYD-101 `events.bit_faults` rows ingested by 2026-06-22 06:00 IST**, the same 63 `record_id`s as
  the preview.
- **TJ108 is NMCS since 2026-04-03 08:00 IST** at the epoch.

The **oracle status-quo branch** (validation only) continues the published preview **bit for bit** from the
epoch to the end of the preview data (2026-07-04 05:30 IST). For TJ107, `maint.records` 137, BIT 15 and
caution 9 rows are identical; TJ108 and TJ105 are identical too.

The data were generated at commit `6d4dc52`; the code snapshot used here is `fda9f98`. The match shows the
two behave identically for these worlds.


## Deviations from the request, and why

- **Events copied into the observation set (`MirrorSession`).** In the preview session, M14's BIT, caution
  and exceedance rows (`obs.event` downloads to M18) are captured for the consumer tree but never reach the
  observation set that the orders gateway checks evidence against. An order citing HYD-101 BIT events would
  therefore be rejected with "evidence not ingested". `MirrorSession` appends those rows, at their own
  `t_ingest`, to the observation set. They are the same rows as the published `fleet/events.*` (row-for-row
  identical, see the reproduction checks). `ScheduledPolicy` reads only `maint.records`, so no decision
  changes. Every snapshot hash and reproduction check matches.
- **Builder `scenario` attribute.** The preview's world object lacks the `scenario` field that the
  `WorldBuilder` protocol requires. The preview never forked in ensemble or belief mode. It is set to the
  wrapped world's key, `preview09-ops`, which `member_root` and the belief stream key on.
- **World length 205 days instead of 180.** The 30-day horizon ends 2026-07-22, after the preview's last day
  (2026-07-04). M02 schedules each next flying day only while `day + 1 < days`, so the world is built with
  205 days (600 for the 400-day S2 run). This changes nothing before day 180: the snapshot id at the epoch is
  identical whether the world is built with 205 or 360 days (checked for TJ108), and the oracle continuation
  matches the preview to the end of its data.
- **Status quo is `scheduled/1.0.0`, as requested, not the bare `StatusQuoPolicy`.** That is what the preview
  ran, and it lets the oracle check continue the published data.
- **S2 demand choice.** See S2.
- **S3 lever.** `REQUISITION_SPARES`, not `WASH_SERVICE TYRES`. See S3.

## Caveats: read before showing any number

1. **Belief mode is a PROXY, and here it is numerically the same as the true-state ensemble.**
   - **What the posterior changes.** The reference `SurvivalPosterior` (assumption A-W1.8-23) changes only
     two things:
     - It resamples each installed engine's bearing-spall initiation life and operating-hour clock in M10,
       from a Weibull prior conditioned on the hours observed in `maint.records`.
     - It removes faults the maintenance organisation does not know about from M18's fault ledger.
   - **What it leaves alone.** It does not resample the M11 fault-injector state, the hydraulic, landing-gear
     or avionics hidden states, M14's BIT nuisance behaviour, tyre and brake wear, or supply ETAs and lead
     times. All of these carry over from the true snapshot.
   - **Footprint check (`belief_check.json`).** Only M10's state differs from the ensemble fork; M18's state is
     unchanged.
   - **Effect in these windows.** That M10 change altered no emitted record within the windows. In all 30
     members of every scenario (and all 10 of the 400-day run), the belief branch has the same record digest
     as the ensemble branch.
   - **What to say.** The in-loop numbers are honest outputs of the data layer's belief mode. They are,
     however, effectively conditioned on the true hidden state of everything that drives these scenarios
     (for S2, the true remaining lead time of the chute). Say "belief mode (reference posterior, PROXY)". Do
     not say "computed only from observations".
2. **S1 safety signal.** Masking HYD-101 in M14 means HYD-101 BIT rows *and their cautions* are no longer
   recorded for TJ107, and M18 also ignores the code. Most of the gain comes from no longer opening HYD-101
   jobs and pulling hydraulic pumps. in_flight_failures rose from 1/30 to 3/30 runs. That is not significant
   (Δ +0.067 [−0.028, +0.161]), but it is in the unsafe direction. This is why the filter is a HUMAN-only
   order. Whether HYD-101 on TJ107 is a nuisance code is a property of the unvalidated preview BIT model (M14
   regime `immature`), not a fact about any real aircraft.
3. **S2 demand choice.** The consumer view at the epoch lists two "open" AOG demands for TJ108:
   - `D-sulur-26055-0001` (tyre, 2026-02-24). Its job is closed and is not in the tech log. Stale or lagged
     supply records are a deliberate data-quality defect (RECON_LAG and others).
   - `D-sulur-26093-0002` (chute, 2026-04-03). It belongs to the only U/S job in the latest TECH_LOG entry.

   The rule used: the oldest open AOG demand whose job is still open and is the U/S entry. The 30-day result
   depends on a supply ETA that a deployed product would not know. The data layer publishes no ETA in
   `maint.records`, and the belief posterior does not resample it.
4. **S3 lever.** M18's `WASH_SERVICE TYRES` resets only M10 tyre pressure-loss states (servicing). It does
   not renew landing life, so it is not the lever for an 8-landing hard-time change. `REQUISITION_SPARES`
   raises base stock. Priority MCM was chosen: lead-time ×1.5, the priority M18 uses for its own
   replenishment. ROUTINE would map to PHU (×2.5); AOG (×1.0) is meant for an aircraft on ground. The tyre
   landing count comes from the consumer view (last tyre INSTALL record plus SORTIE landings since). Note
   that MISSING_PART_RECORD can hide install records.
5. **Single-tail worlds.** The preview simulates each tail as its own world (the M18 router comes in W2.6).
   So there is no shared spares pool, no cannibalisation donor and no second base. All KPIs are for that one
   tail; "fleet" deltas cannot be shown on v0.9.
6. **Uncalibrated and synthetic.**
   - Availability priors are uncalibrated (W2.6), and the preview fails the B8 NFF/CND behaviour check.
   - Lead times are CAG IL-76 fits × an assumed Tejas factor.
   - `cost` is a relative proxy: spares + 0.3 × unit cost per depot repair + man-hours × `mh_cost` +
     expedite premiums. Show it as an index, never as rupees.
   - Codes (HYD-101), part numbers (SYN-PN-…), job and demand numbers are synthetic.
7. **Removals** come from this folder's own count of COMPONENT_LIFE REMOVE rows in each branch's record log,
   the same log `compute_kpis` reads. They are not a fork-service KPI. They were not computed for the S2
   400-day run.
8. **Information discipline.**
   - Orders and evidence come only from `obs.as_of(epoch)`.
   - Nothing under `_restricted_labels/` and no `labels.truth` rows were read. The session's record log holds
     defect-label rows, which were never accessed.
   - The KPIs and diagnostics (removals, NMCS exit times) are computed from each branch's truth record log.
     That is how the data layer's fork service defines what-if KPIs: they are the outcome of a simulated
     future, not an input to a decision.
9. **Determinism.** Re-running any command reproduces the same digests. The `record_digest` and
   `order_log_hash` of every branch are stored in `scenario_*.json`.

