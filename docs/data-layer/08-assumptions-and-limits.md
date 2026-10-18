# 08 · Assumptions, PROXYs, validation status and known contradictions

Source: kit `reference/assumptions.md` (the "Assumption and proxy registry", 332 rows), `reference/
behavioural_targets.md`, `reference/order_authority.yaml`, `reference/order_parameter_schemas.json`, kit
`README.md` §13–15. Every number below is an **[ASSUMPTION] or PROXY with a sweep range** unless marked
otherwise — the data layer's own rule is "swept, not asserted".

## How to read the registry

- One table per work package (W0.2 kernel … W1.8 operations); IDs `A-<WP>-<n>`; columns: Statement | Tag |
  Source/evidence | Sweep range | Affects | Exposing test | Replacement route | Status.
- 332 rows: 309 ASSUMPTION, 23 involving PROXY. 323 open; nothing is validated against Tejas data.
- Evidence tags: `DIRECT` (Tejas/IN20/IAF), `TRANSFER: <donor>` (F404-400, F-16, F100, T-50, HARV, B757…),
  `MEASURED` (almost always on NASA DASHlink B757 QAR data, Tails 687/652 — **not IAF aircraft**), INFERENCE,
  SYNTHETIC. "Tail 687 / 652" anywhere = DASHlink proxy aircraft, not fleet tails.
- Two modes: **Tejas mode** (single F404-IN20) and **proxy mode** (four-engine DASHlink regional jet, used to
  validate texture/dynamics). Tejas mode must reproduce the *structure* of real behaviour, not magnitudes.

## Numbers that shape what we will see in the data

### Operations, calendar and missions (W1.1, W1.8)
- Flying Mon–Fri; day waves 03:00 / 06:30 / 09:30 UTC; night wave 20:00 IST on 60 % of peace days; surge ≈ 6
  waves/day. Planned sorties per available aircraft per flying day: 1.5 peace, 5 surge. Daily planning at
  **00:00 UTC** on the tails M18 offers; maintenance window 06:00–22:00 local; decision epoch 08:00 local.
  **Ops times mix UTC and IST** — normalise.
- Weather wave-cancel probabilities: fog 0.8 (morning), thunder 0.6, dust storm 0.7, precipitation 0.15.
- Mission mixes — OCU: GH 35, instrument/nav 20, formation 20, BFM 15, ground attack 10 %. Operational:
  ACM/intercept 30, ground attack 25, composite 15, AAR 10, navigation 10, air test 10 %.
- Flight time lognormal, median 47.4 min, σ 0.33 (+15–30 min with drop tanks/AAR).
- Usage counting: PLA levels OFF < 10°, IDLE ≤ 37°, CRUISE, MAX ≥ 87° (IRP), AB light > 94°; rainflow
  (ASTM E1049); Type I = OFF↔MAX, Type III = IDLE↔MAX, Type IV = CRUISE↔MAX.
- Denied launch loses its slot (no spare-aircraft substitution); `ASSIGN_SORTIE` only counts if it arrives before
  that date's 00:00 UTC planning; ground runs report usage to M10 only (not M18).
- Bases: Sulur, Nal (fleet), also Naliya (salt index 1), Jaisalmer, Jodhpur in climatology. Dust and salt
  exposure indices drive degradation.

### Status-quo maintenance policy (W1.8) — the baseline we must beat
- Servicing L1 / L2-minor / L2-major / R&O at **25 / 100 / 300 / 1,200 FH** or 15 / 180 / 365 / 2,920 days;
  34 % finish on time.
- Engine hard time **1,000 FH**; **4 reserve engines per 20 aircraft** (CAG 17/2015).
- Cannibalisation after **24 h** awaiting parts.
- Manpower: 4 teams of 3; 2 hangar slots per base.
- Fault isolation: p_isolate, else a wrong position in the ambiguity group is replaced; an unreproduced report
  still gets its top suspect replaced with p 0.35 (**main NFF source**). Rogue units; depot condemn rate 0.05.
- Inspection POD 0.3 / 0.5 / 0.7 / 0.9 by level; borescope 0.7; NDT 0.8.
- Record defects (defaults): CANN under-reporting 0.25, missing component records 0.05, wrong form 0.01,
  14-day reconciliation lag on 30 % of records, `XXX` serials 0.02, duplicate snags 0.03.
- Supply lead time: log-normal from CAG IL-76 AOG bins × Tejas factor 0.3; the fit is ambiguous (median ≈ 29 d
  or ≈ 107 d after the factor, depending on how 38.1 % unreported CAG demands are treated — A-W1.8-10).
- Reference-policy thresholds: wash every 50 FH, borescope every 150 FH (Scheduled); troubleshoot when a
  deferred BIT code recurs ≥ 2× in 10 days, borescope after ≥ 2 exceedances in 30 days (Condition-based).
- IAF "serviceability %" is mapped to **MC %** (A-W1.8-15).

### Degradation and faults (W1.5) — priors with no public basis
- Fighter severity S = 1.75. Fouling Wiener drift 2e-5/h, diffusion 1e-4/√h (∝ dust); wash removes ρ = 0.8.
- Erosion gamma (fan 0.5 × HPC rate, CV 0.3), HPC rate doubles after 3,000 flights; overhaul keeps 10 %.
- HPT abnormal onset (N-CMAPSS form): threshold mean 1,500 h-eq (EOT + 3 × TAMP), CV 0.2.
- **Bearing spall: Weibull β 1.5, η 8,000 EOT h; 0.5 ppm Fe per mg debris** (the lube-anomaly chain).
- Blade crack: Weibull in TAC (β 3, η 20,000) then Paris growth. Life limits: disk LCF 4,300 TAC; HPT blade
  creep 2,000 h.
- Sensor installation bias SD 0.25 % of span; drift 0.2 % (temperature) / 0.1 % (other) per √1,000 h; speed
  pickups don't drift.
- Onset rates: LRU failure 3e-4/h; AB no-light 0.002; hung start 0.002; hot start 0.001; JFS cold-start
  failure 0.2; maintenance-induced defects 0.002 per engine/airframe action, 0.01 per software load (latency
  median 50 FH); sensor faults 1e-5/h per mode; detection coverage 0.3–1.0 per mode.
- Structural fatigue: Miner, N(7 g) = 20,000 crossings, exponent 4.
- **Initial ageing contradiction:** M10 installs at t = 0 are *new* units while M18 starts each item at a random
  fraction of its life — hidden degradation is uncorrelated with recorded age at run start. Discard an early
  burn-in window when learning age→health relations.

### BIT, cautions, exceedances (W1.5)
- BIT statistic AR(1) (φ 0.5) heavy-tailed (mixture p 0.05 × 3), evaluated 100×/h; immature 3σ 3-of-4, mature
  5σ 4-of-5; software load ≈ 10× code rate. CND propensity 29.5 % (RF) – 63 % (analog).
- Caution thresholds: overspeed N1 107 %, N2 105 %; oil pressure low **20 psi**; hydraulic low 196 bar; low fuel
  800 kg; OBOGS O2 low 40 %; low-altitude voice 200 ft. Exceedances need ≥ 3 samples, 1 % hysteresis.
- LUI gates: N2 run 45 %, IRP 95 %. Nz counter levels −1, 0, 2–7 g. LUIs written at landing and shutdown.
- FADEC protection: T5 limit 830 °C, over-temp 850 °C for 1 s, overspeed 106 % for 0.5 s, stall on single-frame
  PS3 drop > 40 %, hung start N2 < 60 % not rising 1 s, AB no-light 2.5 s → 3 retries → lockout. The FADEC
  `FAULT_CODES` word holds only the highest-priority active code; **oil-pressure and vibration limit bits stay 0**.

### Sensors, clocks, texture (W1.6, W1.7)
- Clocks: FADEC 60 Hz +50 ppm (phase 3.1 ms); DFCC exactly 80 Hz; utility EU +30 ppm; ECFM-C −40 ppm; FTI
  +20 ppm; other LRUs Δ ~ N(0, 20 ppm) per serial. The 40 Hz DFCC buffer polled at 50 Hz → duplicate polls.
- `t_bus − t_sample` = 8 ms acquisition latency (+1 ms relayed). GPS/IRIG lock loss Poisson 0.5/h, median 20 s.
- Slip windows only on BHEEM-EU, ECFM-C, FTI DAS (w 2 ms, p 0.25). Glitch = top of scale 5e-5 per channel-hour
  (unflagged). Freezes: T5 0.04/h, WFM 0.05/h airborne, 30 s + Exp (unflagged). N2 < 4.854 %, N1 < 2 % read 0
  with NO_COMPUTED_DATA + GATED.
- Sensor time constants: T5 1.75 s ∝ W^-0.5; T1 2 s; T25 1 s; PS3 20 ms; P5 50 ms; oil & hydraulic temperature
  5 s; FF meter 0.218 s.
- Full-path decoder marks a jump > 10 LSB to range minimum as SENTINEL — **can be confused with an open-circuit /
  probe-short fault** (which also reads bottom of range).

## PROXY items (unavoidable simplifications, registered and tested)

| ID | What is simplified | Consequence for us |
|---|---|---|
| A-W0.4-4 | Fast path: perfect time source, no bus/recorder fields | fast-path data is cleaner than reality |
| A-W1.5-44 | Events/counters `t_utc` = event time | event timing differs systematically from full-path samples |
| A-W1.7-11 | One Ch10 recording per sortie for all sinks | no sink fragmentation yet |
| A-W1.8-17 | Single-echelon supply; unlimited wholesale stock | agency/BRD/HAL dynamics are coarse |
| A-W1.8-23 | Reference belief posterior: Weibull TTF conditioned on survival; no undetected latent faults | baseline posterior is weak — room for ours |
| A-W1.5-18 | Usage-mode Nz crossings from peak Nz only (lower bound) | structural-fatigue features biased low in usage mode |
| A-W1.5-26 | Usage-mode detection stand-in: covered fault shifts first code's BIT statistic by 8σ | usage-mode BIT is cruder than telemetry-mode |
| A-W1.3a-3 | Engine sub-idle/start not usable → **telemetry starts at post-start idle** | no start-transient features in telemetry |
| A-W1.3a-9 | Surge is a discrete event (no post-stall dynamics) | stall signatures simplified |
| A-W1.3a-14 | Vibration = 3 bands ∝ (N/N_des)^2.5, **no unbalance/fault terms in W1** | vibration carries no fault signal yet |
| A-W1.3b-7, -11 | FADEC on-board model fixture-matched (check off); P0 from truth | |
| A-W1.1-27 | Plan-level fuel estimator | |
| A-W1.2-8/10/29 | Drag build-up; ground model without tyre slip (no skid/lock); no Kalman/notch/autopilot | no skid events |
| A-W1.4-15/24 | Lumped fuel slosh (pitch only); single-turbine ACM | |
| A-W1.6-12/17 | Mach-only static-source error; fuel gauge without tank geometry | |
| A-W0.3-38/39 | `FTI.ALL`, `DVR.VIDEO` placeholders | don't build features on them |

Channels never produced: `FCS.KALMAN_ATT`, BIT log, RT status, LRU health, software-config words of the DFCC
(8 of 56 DFCC channels NOT_MODELLED), `FTI.ALL`, `DVR.VIDEO`; ECMS take-off records have no contract topic.

## Validation status (as of 2026-10-15)

| Claim | Status |
|---|---|
| Determinism, snapshot/restore, CRN forks, order-log replay | **Proved** in tests (bitwise only on Apple M4 / darwin-arm64) |
| Texture noise ceiling on real flights | **Proved** (20 + 20 real flights) |
| Data-path decode (CIR → Ch10 → decode = CIR on the lattice) | **Proved** |
| Subsystem behaviour | Proved at module level only |
| B1–B6 behavioural battery on synthetic flights | **Not yet** (no integrated flights) |
| Fan–core (N1–N2) structure, EGT timing | **Not yet** (MF1 open) |
| Fault signatures at fleet scale (B7), BIT/event behaviour (B8), downstream fitness (B9) | **Not yet** (not ported to the harness) |
| Availability and cannibalisation priors | **Not calibrated** (W2.6) |
| Usage gates | plan level only; engine dispersion 1.14 vs ≈ 1.3 (xfail) |

Round-2 evidence: downstream fitness already reasonable on proxy data (B9 TSTR/TRTR 0.92–0.95; model ranking
agreed in every arm) — supports a "fit for purpose" framing, not a verdict.

### Behavioural targets (real DASHlink data, the structure Tejas mode must reproduce)
- Fast-band correlations (Tail 652): N1–N2 0.47, N1–EGT 0.56, N1–FF 0.65, N2–FF 0.67.
- Lead–lag: FF→N2 −0.50 s (fuel *responds* to speed error), N2→N1 +0.5 s (fan follows core), FF→EGT +0.75 s.
- Deceleration much slower than acceleration (N1 τ 1.03 s up / 3.06 s down; EGT 3.45 / 4.70 s).
- EGT corrected-temperature exponent ≈ 0.73. Fan lags core ≈ 55° at 0.19–0.5 Hz.
- Pass rule: D_sim ≤ D_tail (as close to real as one real tail to another); never "indistinguishable".

## Known contradictions to keep in mind (from the registry digest)

1. Clock offset 910 ppm (M13 analog converter) vs 20 ppm (crystal error, M15/M16) — different things, still
   flagged open.
2. Slip-window width default 2 ms vs DASHlink measurement 9–22 ms (outside the sweep).
3. **Validity-bit decode:** A-W0.3-9 says set bit → `BUS_INVALID`; A-W1.7-7 decodes as `FAILURE_WARNING`; AD-45
   says `BUS_INVALID` (contract precedence) and the dictionary table is "corrected in the next release". Treat
   both values as "invalid".
4. FCS law code 3 = GROUND: one entry says dictionary has 0–2 only, another says 0.1.2 added it.
5. Drop-tank stations, sizes and densities differ across M01/M02/M12 entries; internal tank split differs
   (5 equal vs 4 unequal).
6. EOT ratio: usage mode EOT = 1.35 × flight time vs gate EOT/EFH 1.56 ± 0.15.
7. Initial ageing: new at t = 0 (M10) vs random life fraction (M18).
8. Telemetry starts at post-start idle, but plans include 40 s start phases and JFS start events.
9. Multiple overspeed/over-temperature thresholds (limiter vs protection vs caution): N2 103/106/105 %, N1
   102/107 %, T5 830/850/760 °C — pick by purpose.
10. Supply lead-time fit ambiguity (see above).

These need a data-layer coordinator decision before we bake any of them into features or business rules.
