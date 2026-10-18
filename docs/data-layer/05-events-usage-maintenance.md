# 05 · Events, usage counters, maintenance records and availability

References: kit `README.md` §9; `reference/architecture.md` §9.4, §10; modules M14 (monitoring), M18
(maintenance); contract topics `events.*`, `usage.counters`, `maint.records`.

## On-board events (M14) — what the aircraft says about itself

M14 **never reads truth**. It sees recorded values (CIR), controller fault reports (FADEC/DFCC/utilities) and
physical LRU conditions from M11. So false alarms, missed detections, persistence and bursts arise from the same
path for healthy and faulty aircraft (I6).

### BIT model (imperfect by design)

- Test statistic = unit offset (per LRU serial) + flight offset + LRU condition + AR(1) heavy-tailed noise,
  evaluated against threshold k with **m-of-n windows**; declarations latch and clear after consecutive passes.
- Two calibrated regimes: **immature** (k = 3.0, 3-of-4; target 0.1–1 FH between false alarms) and **mature**
  (k = 5.0, 4-of-5; ≥ 50 FH between false alarms, ≤ 1 per 1,000 flights for gas-path EHM).
- A **software load** lowers k temporarily → a burst of codes (~×10), decaying over ~10 sorties.
- Sympathetic codes cascade; 10–18 % of false alarms persist ≥ 3 flights.
- Evidence anchoring this: F-35 0.09–1.03 FH between false alarms; F/A-18E/F BIT false alarms 33.5–86 %;
  NFF 29.5–63 % by LRU technology.
- Each code carries suspect LRUs (isolation order + confidence) and a CND (could-not-duplicate) propensity.

**Implication:** a raw BIT code is weak evidence. Real value comes from *persistence across flights*,
co-occurrence with exceedances/parameter trends, and confirmation outcomes in `maint.records`.

### Limit monitors (exceedances)

Persistence in samples, clear count, hysteresis, running peak and gates (engine running, airborne). Limits come
from dictionary limit kinds or M14 parameters (restricted-manual values never used; limits are ASSUMPTIONs,
swept). Each exceedance → `EXCEEDANCE_INSPECTION` in maintenance ("down until inspected").

### Code table (synthetic, `SSS-NNN`, 104 codes in the dictionary)

| Prefix | System | Codes | | Number block | Meaning |
|---|---|---|---|---|---|
| `ENG` | engine & FADEC | 50 | | 001–099 | sensor / input |
| `AVI` | avionics & buses | 6 | | 100–199 | actuator / output |
| `ELE` | electrical | 6 | | 200–299 | processor / memory / software |
| `ECM` | ECMS / engine monitoring | 5 | | 300–399 | interface / bus |
| `HYD` | hydraulics | 5 | | 400–499 | power supply |
| `ADC` | air data | 4 | | 500–699 | function / performance monitor |
| `CWS` | warning system | 4 | | 700–899 | exceedance / limit |
| `FCS` | DFCC & actuators | 7 | | 900–999 | reserved |
| `ECS`, `FUE`, `LGB`, `STR` | ECS, fuel, gear/brakes, structure | 3 each | | | |
| `NAV`, `SPS`, `FIR` | nav, secondary power, fire | 2, 2, 1 | | | |

Severity × fault list: ADVISORY/MFL 41, ADVISORY/PFL 1, CAUTION/MFL 3, CAUTION/PFL 45, WARNING/PFL 14.
Mechanisms in the table: CBIT 83, EXCEEDANCE 21. (M14's own code file lists 102 codes: 33 internal, 48 external,
21 CIR monitors.) **Known collision:** M08's FADEC codes and M14's table are joined by a provisional translation;
some ids mean different things (e.g. `ENG-501` flameout in M08 vs stall in M14) until one dictionary table lands.

### CWS cautions

30 synthetic red/amber legends, master warning/caution, 4 voice warnings (AOA, canopy, low altitude,
undercarriage). `displayed = false` means recorded but not shown to the pilot. Pilot master-caution reset is not
modelled; open cautions from a previous flight keep `t_cleared` null.

## Usage counters (M14 on board + ground)

- ECMS **LUIs** (F404 IECMS definitions; gates/weights not public → ASSUMPTION): `LUI.TYPE1` (full N2 cycle),
  `LUI.TYPE3` (partial N2 cycle), `LUI.EFTC` (equivalent full thermal cycles, rainflow), `LUI.SRC`
  (stress-rupture counts), `LUI.TAMP` (time ≥ intermediate), `LUI.EOT` (engine operating time), `LUI.PS3_FULL`
  / `PS3_PART`. Written **twice per flight** (landing and shutdown).
- `USAGE.TAC` (total accumulated cycles; cross-checked 0.4–15 per FH), flight hours, landings, engine starts
  (ground / air relights), AB light-ups, JFS start attempts/successes/consecutive, gear cycles, chute
  streamings, brake applications/energy, g/AoA/overspeed exceedance counts, AMAGB hours.
- `STRUCT.NZ_COUNTERS.L1–L8`: normal-acceleration level-crossing counts (fatigue meter; individual aircraft
  tracking). In usage mode these come only from peak Nz (PROXY A-W1.5-18: a **lower bound**).
- Usage gates (plan level): Type III cycles ≈ 5 ± 2 / FH, AB lights 4–5 / FH, TAC 2.2–3.3 / FH, time ≥ IRP
  17–20 %, AB ≈ 5 %, EOT/EFH 1.56.

Counters are **cumulative as reported**; compute deltas per serial yourself and watch for resets on
engine/component change (serials move — see [02](02-contract-topics.md)).

## Maintenance world (M18) — what the maintainers record

M18 is a discrete-event maintenance organisation: configuration control, snags and troubleshooting, supply,
servicing, inspections, modifications, hard-time retirement, depot turnaround, manpower, hangar slots.
**It decides only from tech-log knowledge**; hidden truth decides only *outcomes* (does a ground check reproduce
the fault, is the removed unit really bad, does an inspection find the latent defect). So `RTOK`/NFF findings
arise from truth, not from a label.

### Record types (`record_type`)

| Type | Trigger | Key fields |
|---|---|---|
| `SORTIE` | each flight (0.5 h after landing) | sortie_id, mission_type, crew_id, flight_hours, landings, engine_cycles, engine_starts |
| `TECH_LOG` | continuous | instantaneous `availability_state`, `limitations_text` (U/S jobs, deferrals, `GROUNDED BY ORDER`) |
| `DEFECT_WO` ("snag") | pilot write-up, BIT/HMS code, inspection, order | job_no, when_discovered, system/malfunction/action/type-maint codes, discrepancy & corrective-action text, man_hours, evidence_record_ids |
| `COMPONENT_LIFE` | install / remove | part_no, serial_no, maker, install_action, item_hours, item_cycles |
| `INSPECTION` | interval, exceedance, order | inspection_type, findings |
| `SUPPLY_DEMAND` | part needed | demand_no, priority (AOG/MCM/PHU), quantity |
| `CANNIBALISATION` | part robbed | job_no + linked_job_no, donor_tail_no |
| `MODIFICATION` | mod / software load order | order_id, sw_config_id, compliance_status (ISSUED/COMPLIED/NOT_APPLICABLE) |
| `EXCEEDANCE_INSPECTION` | over-temp/overspeed/over-g/hard landing | aircraft down until inspected |
| `SHOP_FINDING` | turn-in | shop_finding: `CONFIRMED` / `RTOK` (no fault found) / `BCM` (beyond capability) |
| `AVAILABILITY_STATE` | binned state change | 15-min SCIR bin state |

Lifecycle `status`: OPEN → IN_WORK → AWAITING_PARTS (AWP) / AWAITING_MAINTENANCE (AWM) / DEFERRED → CLOSED
(null for records without lifecycle, e.g. availability bins). Coded fields (when-discovered, system,
malfunction, action-taken, type-maint, inspection) are **synthetic IAF-relabelled codes** (NAMP / TO 00-20 / UK
F700 / S5000F structure).

### How on-board events become maintenance work

`events.*` row arrives at its `t_ingest` → **0.33 h later** M18 reviews it and either opens a defect, **defers
and monitors** (non-grounding BIT, typically for 3 flights), or raises a **conditional inspection**
(exceedance). The defect's `evidence_record_ids` point back to the event `record_id`s — this is the join that
gives us *labels* (event → defect → troubleshooting → removal → shop finding CONFIRMED/RTOK).

### Event chains modelled (architecture §10)

1. engine lube (oil) anomaly; 2. BIT false alarm with defer-and-monitor for 3 flights; 3. exceedance →
conditional inspection; 4. scheduled servicing; 5. modification / life-limited part; 6. Tejas JFS cold start;
7. Tejas brake-software configuration (→ tyre burst → excursion → fleet grounding); 8. Tejas fuel-gauging
artefact (false low fuel at > 40° pitch, max AB, < 1,200 kg).

### Supply and cannibalisation

- Wholesale lead time: log-normal fitted to **CAG IL-76 AOG bins** [DIRECT IAF] × Tejas OEM-support factor
  **0.3** [ASSUMPTION, sweep 0.1–1]; priority multipliers AOG 1 / MCM 1.5 / PHU 2.5. (IL-76 reality: AOG met
  ≤ 15 days only 10.8 % of the time; 22.5 % > 6 months.)
- **PROXY A-W1.8-17:** single-echelon pipeline (base stock + base shop/depot loop + wholesale pool); reality is
  multi-echelon (base / BRD / HAL / OEM). Wholesale stock is unlimited (lead time only).
- Status-quo cannibalisation rule is built in (`InternalPolicy(cann=True)`), switchable off when a policy issues
  CANNIBALISE orders.
- Anchors: CAG 17/2015 (4 reserve engines per 20 aircraft), AMAGB 750 h life, drag chute 45 streamings / 8 years.

## Availability (computed, never asserted)

- Computed from job states, **SCIR-style 15-minute bins**. An `AVAILABILITY_STATE` record is written per tail for
  each bin where the binned state changes (state persists until the next record). Bin state = most degraded of
  carried-in state and every state entered in the bin.
- Precedence: **NMCD > NMCS > NMCM_U > NMCM_S > PMCS > PMCM > FMC** (NAMP).
  - FMC fully mission capable; PMCM/PMCS partially (maintenance/supply); NMCM_S/NMCM_U not mission capable,
    scheduled/unscheduled maintenance; NMCS supply; NMCD depot.
- Priors from CAG: Su-30MKI ≈ 20 % in 1st/2nd-line maintenance, 11–12 % in HAL R&O, 13–14 % AOG, serviceability
  55–60 % vs 75 % norm. **Not yet calibrated** (strict expected failures until W2.6); a Tejas supply-chain events
  layer sits on top because CAG priors are pessimistic for an OEM-supported F404 fleet.
- KPIs (M22, from records only): `mc`, `fmc`, `nmcs`, `nmcm`, `nmcd` occupancy, `flying_task` (flown/planned
  FH), `flown_fh`, `sorties`, `aog_days`, `cann`, `cann_rate` (per 100 sorties), `man_hours`, `cost` (relative
  proxy), `in_flight_failures`.

## Data-quality defects (realism we must clean)

Injected **after** truth, per record identity, listed only in restricted `labels.truth` (`DEFECT` rows):

| Defect | Evidence anchor |
|---|---|
| Cannibalisation under-reporting (up to 50 %) | GAO / F-35 sites |
| Missing part records | 81 % at one F-35 site |
| Under-reported aircraft, unfilled log books, wrong form | NAMP practice |
| Reconciliation lag | 14 days |
| Free-text noise | 97 of 106 tokens non-standard |
| Default `XXX` serial numbers | |
| Duplicate snags | |
| Recorded health data never shown to the pilot | |

Example kit data has defect injection **off**. Our record pipeline needs entity resolution (serials, duplicate
snags), text normalisation, and tolerance for lagged/missing component records.

## Sink fragmentation (architecture §10, AD-25)

Each signal reaches a different subset of sinks — cockpit, CDR (crash recorder), ECMS/HUMS, maintenance
download (MPDRU), FTI — "emitted as separate streams, so downstream must reconcile them, as real maintainers do".
**At the snapshot this is a PROXY:** one Ch10 recording per sortie captures every bus (A-W1.7-11); a
recording/sink id arrives with contract 0.2.0.
