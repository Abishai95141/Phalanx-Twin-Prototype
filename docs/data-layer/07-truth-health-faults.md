# 07 · Hidden truth: health, degradation, faults and labels

References: kit `README.md` §3, §11; `reference/architecture.md` §5, §9; modules M10 (health), M11 (faults),
M12 (sensors); contract `labels.truth`.

## Truth vs observation

Each tail holds a truth state: kinematics, engine stations, utility states, **hidden health state per serial**,
sensor installation states, clock phases. Observations are functions of truth through the measurement chain.
**Truth is never part of the consumer contract** — it goes only to the restricted `labels.truth` store.

## Hidden health states (M10)

50 hidden states (`not_measured_states.csv`) + per-serial life consumption, in four **observability classes**:

| Class | Examples | What it means for PdM |
|---|---|---|
| Model-observable | component health (η, flow), tip clearance, pump efficiency, sensor biases | detectable from in-flight parameter residuals |
| Usage-inferred | disc LCF, creep, brake/tyre wear, chute life | estimate from usage counters, not sensors |
| Late-symptom | bearing spall, cracks, seal wear, wiring | visible only shortly before failure (or via debris/oil) |
| Ground-inspection | accumulator precharge, filter loading, fluid contamination | only visible through inspections (`MX.*` channels / INSPECT orders) |

Physics sees health through four held ports: `health.engine` (per engine, 10 fractional deltas: fan/HPC/HPT/LPT
η and flow, combustor η, nozzle area), `health.utility` (23 entries: hydraulic leaks, compensator drift,
filters, precharge, ECS, battery, JFS, AMAGB, brakes, tyres, fuel transfer), `health.sensor_bias`,
`health.actuator` (13). Engine auxiliary/mechanical states (VG offset, spall, crack, **oil Fe**, seals,
FADEC/nozzle hardware) exist **only as hidden states and labels** today — no port — so their observable
signature depends on what monitoring/inspection exposes.

**Sensor bias and component deterioration are separate latent processes with separate truth (AD-26).** They
are observationally confounded (NASA TM-4551). Downstream models will be tested on whether they confuse them —
we should explicitly model sensor bias vs true degradation (e.g. cross-sensor consistency, lane disagreement).

## Degradation process families (architecture §9.2)

| Mechanism | Process | Anchor |
|---|---|---|
| Recoverable fouling | Wiener with drift ∝ dust index; partial reset by wash (fraction ρ) | ≈ 1 % Γ and η per roughness step |
| Erosion, clearance, wear | Gamma process × **fighter severity S = 1.5–2** (swept) | HPC η ≈ −5 % at 5,000 flights (ProDiMES) |
| Early-life rub-in | step + exponential after each build/overhaul | ≈ 1 % TSFC on flight 1 |
| Abnormal onset | usage-energy vs random threshold, then `A(exp(a(t/τ)^b) − 1)` | N-CMAPSS form (HPT) |
| Cracks and spalls | Weibull initiation + Paris/exponential growth; **debris ∝ growth** | incubation 50–100 FH; 0.08–0.34 mm/h; 2–50 mg per mm |
| Shocks (FOD, bird) | Poisson with severity; seasonal/base dependence | step loss + imbalance |
| Latent maintenance-induced defects | per-action probability with latency | 1 flight to ≈ 6 years |
| Intermittents | two-state Markov, environment-dependent | NFF 30–60 % (avionics) |
| Utility wear | monitoring curves | case-drain ΔT flat ≈ 5 mo → limit ≈ 11.5 mo; filter ΔP rise ≈ 4 weeks; carbon brakes 1,400 landings; tyres 4–12 landings; HX fouling 3–9 mo |
| Structural fatigue | Miner damage per Nz level crossing | |
| Tejas-specific events | discrete | JFS cold/altitude start failure; gauging artefact; brake-software defect → tyre burst → excursion → fleet grounding; FCS channel dropout |

Units installed at t = 0 start new (no initial ageing yet). Health advances once per sortie from usage drivers
(cycles, time at temperature, g, landings, starts, dust and salt exposure). Removed units' states wait "on the
shelf" under their serial and come back with it.

**Faults are differences from a healthy per-tail baseline.** The research basis notes features built on a per-tail
healthy baseline transfer far better to real data (52.9 % → 85.5 % in a sim-to-real study) — a strong hint for
our feature design.

## Fault injection (M11)

- Catalogue: **83 modes** covering 38 + 41 research-catalogue rows plus Tejas-specific events and scripted hooks
  (backup generator failure, fire-loop open/short, actuator jam, servo coil).
- Typed dependency graph: 45 nodes, 42 edges (shaft, hydraulic, thermal, data/electrical, discrete, mechanical)
  with transfer gain/threshold/lag and latency; six accident-board cascade templates (engine → electrical, engine
  → AB → electrical, hydraulic, utility → braking, contamination → control law, electrical → avionics).
- Sensor-fault modes: bias, drift, stuck, open, short, intermittent, spikes, slow, probe_open, probe_short.
  Texture-visible ones (spikes, stuck, intermittent) are *meant* to be visible in data.
- Faults are applied only as state perturbations to the owning module (I6). Fault truth leaves only as FAULT labels.
- Randomness keyed by (scenario, tail, sortie) / (tail, job) / (tail, instance) → a sortie flown in two forks gets
  the same exogenous faults.
- Fault-signature library (from released fighter traces): pop stall (PS3 85 → 10–15 psia), mechanical stall
  (N falls while T5 rises, codes at +2/+4/+10/+13 s), AB no-light at 2.5 s, quickfill stall ≈ 1 per 994 lights,
  nozzle limit cycle 1–2 Hz, MFC over-fuelling, hung start (N2 < 60 % not rising for 1 s), shut-off valve partially
  closed **with no caution**, bleed leak −2–3 % thrust per lb/s; CF-18 direction matrix for corrected cross-plots.
- Signatures are weak at low power and depend on operating point (closed-loop physics).

## `labels.truth` (RESTRICTED) — what can be scored

| `label_kind` | `subject_id` | Use |
|---|---|---|
| `TRUTH_SAMPLE` | param_id | true value behind a CIR sample (`related_record_id` → the sample) — sensor-error evaluation |
| `HIDDEN_STATE` | `<NM id>/<slot>`, category = observability class | RUL / health-estimation scoring |
| `FAULT` | `<mode>#<instance>[@key]`, category = mode id, `serial_no` = engine serial | fault detection/diagnosis scoring (onset `t_true`, `t_end`) |
| `DEFECT` | defect id | data-cleaning scoring (`related_record_id` → the defected record) |

Fields: `tail_no`, `sortie_id`, `serial_no`, `t_true`, `t_end`, `value`, `units`, `category`,
`related_record_id`, `source_module`.

**Rules for us:**
- Labels are for **offline evaluation only** — never features, never inside a live decision path. Readers refuse
  the topic in the consumer audience; the kit contains no label data at all.
- The consumer tree is leak-audited (names, metadata, bytes, values). A G0 trivial-cue audit and a label-leak
  audit (texture-only / metadata-only classifiers must be at chance) guard against shortcuts — the leak audit's
  feature front end is still a STUB until W2.5.
- Our *training* labels must come from **observable outcomes**: `maint.records` defect → removal → shop finding
  (CONFIRMED / RTOK / BCM), exceedance inspections, component life records. Truth labels then tell us how good
  those proxy labels and our predictions are.
