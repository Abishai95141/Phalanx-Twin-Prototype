# 04 · Parameter dictionary, signals and the synthetic ICD

References: kit `dictionary/dictionary.0.1.2.json` (1.26 MB, `format: phalanx.dictionary/1`), `parameters.md`,
`icd.md` / `icd.csv`, `tmats.txt` / `tmats_setup_record.c10`, `contract/dictionary_binding.json`; modules
M01; kit `README.md` §8. Dictionary `tejas` **0.1.2**, hash `a8b02cab…17ce` (blake2b-256, person
`phx.dict.v1`, over canonical content without `dict_hash` — verified reproducible).

The dictionary is the **single source of truth** for every channel, unit, scaling, rate, bus address, limit,
code table and evidence tag. TMATS, the synthetic ICD and the contract schemas are generated from it. **Never
hard-code bus addresses, labels, codes or limits — read them from the dictionary.**

## Identity: parameter → measurand → channel

| Level | Count | Example | Contract field |
|---|---|---|---|
| `param_id` (inventory row) | 189 | `ENG.N2`, `ELEC.BATT` | — |
| `measurand_id` = `param_id[.unit][.component]` (one unit each) | 358 | `ENG.N2`, `ELEC.BATT.AH` | **`param.samples.param_id`** |
| `channel_id` = `measurand_id[.lane]` | 464 | `ENG.N2.A`, `ENG.N2.B`, `ENG.N2.V` | (`param_id` + `lane`) |

Lanes: `""` simplex (→ contract `lane` null), `A`–`D` DFCC/ADC quadruplex, `A`/`B` FADEC lanes / sensor cores,
`V` voted/validated. Roles: single 322, lane 108, voted 32, placeholder 2. Naming:
`SUBSYS.PARAM[.UNIT][.COMPONENT][.LANE]`, upper case, dots (e.g. `ELEC.TRU.VI.TRU1.CURR`,
`FCS.SLAT.POS.IB_L.A`). **Prefer `.V` channels** for modelling (FCS.RSA.Q / FCS.ASA.NZ have lanes but no V —
use `FCS.VOTED.Q` / `FCS.VOTED.NZ`). Use lanes A/B for lane-disagreement / sensor-fault features.

## Top-level keys of the JSON

`format`, `dict_version`, `dict_hash`, `platform`, `title`, `release_date` (2026-10-15), `synthetic_icd`
(true), `synthetic_label`, `generators`, `proxy_items` (`DVR.VIDEO`, `FTI.ALL`), `parameters` (189),
`channels` (464), `lrus` (30), `buses`, `rate_groups` (30), `sinks` (8), `code_tables` (15), `constants`
(`channel_reference`), `rules` (62 provenance rules R-*/P-*), `assumption_register` (45), `stats`.

There are **no** separate tables for messages, units, calibrations, limits or derived params — they live on
channel records. `contract/dictionary_binding.json` holds only `dict_hash`, `dict_version` and a
`measurand_id → unit` map (358 entries); code tables, limits and locations must be read from the full dictionary.

### Channel record (key fields)

| Group | Fields |
|---|---|
| Identity | `channel_id`, `measurand_id`, `param_id`, `lane`, `role`, `name`, `subsystem`, opt. `unit_id`, `component` |
| Physics | `quantity` (38 classes), `units` (pint), opt. `pressure_ref` (absolute/gauge/dynamic/differential), `signal` (computed 203, analog 181, counter 33, discrete 25, frequency 10, inspection 9, …), `sensor_type` |
| Data path | `source_lru` (producer, 28 values), `acq_lru` (digitiser = clock domain, 17 values → contract `source_lru`), `transport`, `rates {acquisition, bus, producer}`, `sinks[]` |
| Quantisation | `range {min,max}` (null on 139), `native_step`, `recorder_lsb` (null on 249), `adc_bits`, opt. `converter_step`, `encoding`, `calibration` (170 channels: linear, EU = LSB × counts) |
| Validity | `validity_word` (260), `ssm` (8), `rt_status` (16), `frame_sync` (10), `none` (170) |
| Other | `limits` (only 26 channels), `inputs` (lanes feeding a voted/averaged output, 35 channels), `proxy`, `prov` (per-field evidence rule), `notes` |

Evidence (parameter `evidence.primary`): DIRECT 111, TRANSFER 54, DIRECT-part 13, ASSUMPTION 9, DIRECT-unnamed 1,
MEASURED 1. **452 of 464 channels depend on an ASSUMPTION or PROXY rule.** Provenance coverage 100 %.

## Inventory

| Subsystem | Params | Channels | Notes |
|---|---|---|---|
| flight_control | 31 | 126 | 68 lane channels, 19 voted; DFCC at 80 Hz |
| avionics_status | 20 | 96 | per-RT BIT/health/status words, CWS, stores, Nz counters, system/time |
| air_data | 20 | 54 | ADC quadruplex lanes (RS-422, not recorded) + voted |
| engine | 32 | 44 | FADEC/ECMS gas path, oil, vibration, status, fault codes |
| navigation | 14 | 25 | INS/GPS, AHRS, radar altimeter |
| electrical | 8 | 20 | generator, DC buses, battery, TRUs |
| ecs_life_support | 9 | 17 | bleed, avionics cooling, OBOGS, LOX |
| usage / engine_usage | 10 / 9 | 16 / 9 | ground-computed counters and ECMS LUIs (download) |
| fuel | 6 | 15 | |
| landing_gear | 7 | 13 | gear, brakes, NWS, chute |
| hydraulics | 10 | 12 | two 280 bar systems |
| ground_inspection | 6 | 9 | `MX.*` (transport `maint_record`) |
| secondary_power | 6 | 7 | AMAGB, JFS |
| fire | 1 | 1 | |

Transport: mil1553 260, internal 84 (never leaves the LRU), download 46 (sortie record), rs422 28 (not
recorded), fti_pcm 10 (test aircraft only), maint_record 9, mil1553 mode-code 8, status 8, arinc429 8, video 1,
placeholder 1, recorder_time 1. **278 channels are recorded on a bus/recorder sink.**

No ATA chapter or work-unit code exists in the dictionary — only the 15 `subsystem` values. If we want ATA
mapping (useful for IAF-familiar UIs) we must build it (e.g. engine 71–80, hydraulics 29, electrical 24, fuel
28, ECS 21/35, gear 32, flight controls 27, nav 34, fire 26, secondary power 49).

**Coverage warning:** at Wave-1 exit, 261 of 464 channels had neither a sensor model nor an LRU-computed
producer. M12 does not yet model e.g. `ENG.FUEL_INLET_T`, ECS temperatures/pressures, brake pressure,
electrical (battery/generator/TRU), `NAV.RADALT`, `ENG.VIB.*`, `SPS.*`. A coverage plan arrives in W2.2.

## Units and scaling

- 33 pint unit strings, a **deliberate SI/imperial mix**: %, deg, degC, degF (LRU health temps only), psi,
  bar, mbar, kPa, lb/hr, kg, ft, knot, in/s, lbf, `pound_force/foot**2` (AD.QBAR), standard_gravity, …
  Contract `value_eu` is in these **engineering units**, not SI.
- SI conversion constants (`constants.channel_reference`): 100 % N1 = 13,270 rpm, 100 % N2 = 16,810 rpm,
  JFS rated 60,000 rpm, AMAGB rated 16,810 rpm, Nz envelope +8 / −3.5 g.
- LSB sources: DASHlink B757 lattice (N1/N2 0.03125 %, WFM 8 lb/h, oil P 2.442 psi, oil T 1.343 °C, T5 0.5 °C,
  vibration 0.03125 in/s), F404-400 chain (PS3 0.5 psi, T1 1 K, P5 0.06 psi), power-of-two from range, or
  inventory recommendation. Native step = LSB except a few (Nz 0.002 g native; FADEC lanes have a finer
  `converter_step` = span/2¹⁴, to be reflected in 0.1.3).
- **Coarse resolution for trending** (oil P 2.442 psi steps, oil T 1.343 °C) — trend models must handle
  lattice-valued data (no sub-LSB smoothing assumptions).
- `ENG.T5` range starts at **371 °C** — cold/shut-down engine values are OUT_OF_RANGE.
- Unit quirks: `ENG.OIL_P` is a differential pressure stored as `psi`; `AD.DPA/DPB` are absolute despite the
  name; `AV.LRU.HEALTH.*.TEMP` is degF.

## LRUs, buses and rates

**LRUs (30)**, with frame rates: DFCC 80 Hz ×4 (quadruplex, CCDL), ADC 80 ×4, FADEC 60 ×2 (with the ECMS 1553
gateway), INGPS 100, AHRS 100, OAC 50 (mission computer, 1553 bus controller, maintenance log/MPDRU), RADAR 50,
SMS 50, BHEEM_EU 40 (utility management: hydraulics, electrical, secondary power, gear/brakes/NWS/chute, fire),
ECFM_C 40 (fuel, ECS, life support), CWS 40, RADALT 25, ECMS 10, FTI_DAS 64; plus GCU, TRU ×2, BDU, DC_GCU,
MASTER_BOX, OBOGS, CPCS, HALD_CB, FDCU, NWS_CTRL, ANTISKID (digitised by BHEEM_EU / ECFM_C), CDR, HUMS_DAU, DVR,
FTP, GROUND.

**Buses (synthetic Phalanx ICD — not the real Tejas ICD):**

| Bus | Type | Controller | Terminals | Monitors (recorders) |
|---|---|---|---|---|
| AV-MUX-1 (mission) | MIL-STD-1553B | OAC | INGPS RT10, AHRS RT11, RADAR RT12, SMS RT13 | CDR, HUMS_DAU |
| AV-MUX-2 (vehicle systems) | MIL-STD-1553B | OAC | DFCC RT1 (mirrored RT2–4), FADEC/ECMS RT5, BHEEM_EU RT7, ECFM_C RT8; OAC broadcast RT31 | CDR, HUMS_DAU |
| WPN-MUX | MIL-STD-1553B (1760 stores) | SMS | none in inventory | — |
| CWS-OAC | ARINC 429 low | CWS | OAC | labels 100–106 octal |
| RADALT-OAC | ARINC 429 high | RADALT | OAC | label 100 octal |
| FTI-PCM | 12-bit PCM @ 64 Hz | FTI_DAS | test aircraft only | |
| ADC-DFCC, FTP-DFCC | RS-422 | | not recorded | |

FADEC RT5 messages: SA1 gas path (AV25), SA2 status/discretes/oil P (AV12.5), SA3 fuel-inlet T + oil T
(AV6.25), SA4 vibration (SLOW1, 1 Hz). Each RT also has a mode-code-19 BIT word (AV12.5) and a status word (AV50).

**Rate groups (30).** Acquisition: FCS80 (174 channels), LRU-INT (91), SORTIE (46), EVT (41), LRU-INT-SLOW
10 Hz (34), FADEC-INT 60 Hz (30), LRU-INT-INS 100 Hz (21), FTI 64 Hz, INSP (9), HF 10 kHz (vibration → 1 Hz
features), LRU-INT-MODEL 200 Hz. Bus: AV50 (86), AV25 (50), AV12.5 (98), AV6.25 (36), SLOW1 (14), none (123).
Recorder: CDR16/8/4/1, ECMS10/1, ECMS-TO (take-off window 6–10 s), HUMS 1 Hz, LOG, DISPLAY. Producer: FCS40 on
57 DFCC channels (40 Hz buffer polled at 50 Hz → duplicate polls).

**Sinks (8):** COCKPIT, CDR (crash recorder loop), ECMS_HUMS (ECMS log + Mk1A HUMS DAU), MPDRU (OAC maintenance
download), FTI, GROUND (ground-computed sortie products), INTERNAL (never leaves the LRU), MAINT_RECORD
(e-MMS-like). Each channel reaches a different subset (sink fragmentation).

## Synthetic ICD details (for anyone decoding raw data)

- 1553 words: AS15532-style 16-bit BNR (two's complement), 32-bit values two words MSW first, discretes
  bit-packed (`encoding.fields`). Each message starts with one **validity word per 16 items; bit order is
  MSB-first** (item i → validity word ⌊i/16⌋+1, bit 15 − (i mod 16)); set bit = BUS_INVALID.
- **Word indexing:** contract `rt_sa_word` is 0-based; dictionary/ICD/TMATS are 1-based. Status words SA00/W00;
  MC19 BIT word SA31/W00. ARINC labels are decimal ints in the JSON (64) but octal (100) in ICD/contract.
- ARINC 429: 19-bit fields in bits 11–29, SDI 0; SSM tables run in **opposite orders** (`ssm_bnr` 3 = NORMAL,
  `ssm_dis` 0 = NORMAL).
- `icd.csv` (294 rows, 25 columns) **starts with a `# SYNTHETIC…` comment line** before the header.
- TMATS (IRIG 106-07 Ch 9): G group, R-1 recorder with 7 data sources (Ch10 channel IDs: 1 TIME, 2 AV-MUX-1,
  3 AV-MUX-2, 4 WPN-MUX, 5 CWS-OAC, 6 RADALT-OAC, 7 FTI-PCM), recorder events REC_START / TIME_LOCK_LOST /
  TIME_LOCK_REGAINED, 10 s time index; B-1…B-5 bus messages; P-1/D-1 PCM; C-1…C-294 data conversions.
  `tmats_setup_record.c10` is one Ch10 packet whose payload is byte-identical to `tmats.txt`.

## Code tables (15)

| Table | Content |
|---|---|
| `bit_codes` | 104 synthetic `SSS-NNN` codes (M14's 102 + ENG-509/510) with `desc`, `sev`, `list` (PFL/MFL), `mech` (CBIT 83, EXCEEDANCE 21), `lru`, `lane`, `src` (external/internal/cir), `legend`, `voice`, `monitor {channel, limit, sense, gate}` (21 CIR monitors), `legacy.M08` map |
| `bit_code_format` | code word: prefix index k bits 15–10, NNN bits 9–0; EU = k × 1000 + NNN; 0 = none. `ENG.FAULT_CODES` (prefixes ENG, ECM) and `FCS.BIT.LOG` (FCS) only; one code per word (highest priority) |
| `cws_legends` | 30 slots CWS-L01…L30 (legends are shared between codes — a legend alone doesn't identify a fault) |
| `flight_phase` | 0 UNKNOWN, 1 PREFLIGHT, 2 TAXI, 3 TAKEOFF, 4 CLIMB, 5 CRUISE, 6 APPROACH, 7 ROLLOUT, 8 ENGINE_START, 9 MISSION, 10 DESCENT, 11 PATTERN, 12 TOUCH_AND_GO, 13 SHUTDOWN, 14 GROUND_RUN, 15 HOT_REFUEL (8–15 synthetic) |
| `fcs_law` | 0 SCHEDULED_GAIN, 1 FIXED_GAIN_REVERSION, 2 SPIN_RECOVERY, 3 GROUND |
| `borescope_grade` | PASS / LIMIT / REJECT |
| `mil1553_status_word`, `mil1553_validity_bit`, `ssm_bnr`, `ssm_dis`, `validity` | bus status → contract validity |
| `gps_fix`, `gps_fom` (1–9), `ins_mode`, `store_station` | navigation / stores |

Known glitches: `ins_mode` code "0" coerced to boolean `false`; AVI-205/AVI-301 `lru: "MC"` (not an LRU id;
probably OAC); ADC-401 has `lru: DFCC`; ENG-013 missing; some severity/list combinations odd (ELE-404 ADVISORY
on PFL; STR-701…703 CAUTION on MFL). The M08 ↔ M14 code collision is handled by a provisional translation.

## Limits and thresholds

Only **26 channels carry limits** in the dictionary, e.g. `ENG.T5` steady_max 830 °C; `ENG.VIB.*` steady 1.0 /
transient 2.0 in/s; ECS bleed PHX in/out 578 / 170 °C, bleed P 2.8–6.4 bar; DC buses 22–29 V (emergency
16–29, starting 12–29); generator 108–118 V, 393–407 Hz; battery warning_low 30 A·h; `FCS.VOTED.NZ` −3.5…+8 g;
hydraulics nominal 280 bar; accumulator precharge 50 bar; tyres 16.9 / 7 bar; AMAGB life 750 h; chute life
45 streamings. **Most caution/exceedance thresholds are M14 module limits not in the dictionary**
(n1/n2_overspeed, oil_p_low, hyd_low, low_fuel, mach_max, aoa_voice, low_alt, obogs_o2_low — values in
[08](08-assumptions-and-limits.md)). Monitors are gated `engine_running` or `airborne`.

## PdM-relevant channels (shortlist)

| Channel | Meaning | Units / range / LSB | Rates (acq → bus) | Monitor / limit |
|---|---|---|---|---|
| `ENG.N1.V`, `ENG.N2.V` | fan / core speed (validated) | %, 0–115 / 0–110, 0.03125 | 60 → 25 Hz | ENG-702 / 703 overspeed |
| `ENG.T5` (+ `HARNESS_A/B`) | EGT (T56), harness average | degC, 371–871, 0.5 | 60 → 25 | 830 °C; ENG-701; open-probe codes |
| `ENG.T1.V`, `ENG.T25` | inlet / HPC-inlet temperature | degC | 60 → 25 | |
| `ENG.PS3.V`, `ENG.P5` | CDP / turbine discharge pressure | psi, 0–500 (0.5) / 0–60 (0.06) | 60 → 25 | |
| `ENG.WFM`, `ENG.WFAB` | main / AB fuel flow | lb/hr, 0–12,000, 8 | 60 → 25 (WFAB on FTI) | ENG-103 |
| `ENG.A8.V`, `ENG.FVG`, `ENG.CVG`, `ENG.PLA.V` | nozzle, variable geometry, throttle | %, deg | 60 → 25 | ENG-011/101/102 |
| `ENG.OIL_P`, `ENG.OIL_T`, `ENG.OIL_LEVEL`, `ENG.LUBE_DP` | lube system | psi 0–200 (2.442); degC (1.343); bits | 60 → 12.5 / 6.25 | ECM-702 oil_p_low (20 psi, engine_running) |
| `ENG.CHIP` | chip detector discrete | bit | EVT → 12.5 | ECM-001 (CWS-L10) |
| `ENG.VIB.OVERALL`, `N1_1REV`, `N2_1REV` | vibration velocity features | in/s, 0–5, 0.03125 | 10 kHz raw → 1 Hz | 1.0 / 2.0 in/s; ECM-701 |
| `ENG.FADEC_STATUS`, `ENG.FAULT_CODES`, `ENG.LIMIT_FLAGS` | channel in control, substitution active; fault list; limit bits | bitfield / code word | EVT/LRU → 12.5 | ENG-201/202/508 |
| `ENG.FLAMEOUT`, `ENG.AB_LIT`, `ENG.IGN` | discretes | bits | | ENG-502/503/509/510 |
| `ENG.THRUST_EST` | take-off thrust check | lbf | ECMS10 / ECMS-TO | (take-off record not in contract v0) |
| `LUI.*`, `USAGE.TAC` | life usage indices | count / hour | per sortie | |
| `HYD.SYS1/2.P`, `.T`, `.LEVEL`, `HYD.FILTER_DP` | hydraulics | bar 0–350; degC; %; 9 clog bits | 200 → 25; 10 → 6.25 | HYD-501/502 hyd_low (196 bar), HYD-701 |
| `FUEL.TOTAL.TOTAL`, `FUEL.TEMP`, `FUEL.BOOST_P` | fuel | kg 0–6,000 | → 12.5 / 6.25 | FUE-501 low_fuel (800 kg), FUE-401 |
| `ELEC.GEN.V.PH_A/B/C`, `ELEC.GEN.F/I`, `ELEC.DCBUS.V.*`, `ELEC.BATT.*`, `ELEC.TRU.VI.*` | electrical | V, Hz, A, A·h | 10 → 6.25 / 1 | ELE-701/702/703/405 |
| `ECS.BLEED_T.*`, `ECS.BLEED_P`, `ECS.AVIONICS_T.*`, `LSS.OBOGS.O2` | ECS / life support | degC, bar, % | 10 → 6.25 / 1 | ECS-701/501/503 |
| `SPS.AMAGB.OIL_T`, `SPS.AMAGB.OIL_LOW`, `SPS.JFS.EGT` | secondary power | degC, bits | | SPS-001/501; AMAGB life 750 h |
| `FCS.VOTED.NZ`, `STRUCT.NZ_COUNTERS.L1–L8`, `USAGE.G_EXCEEDANCE.*` | loads / fatigue | g; counts | 80 → 50; per sortie | STR-701/702 |
| `FCS.ACT.BIT.*` (13 actuators), `FCS.CH.STATUS.A–D` | servo / LVDT / hydraulic-fail bits per lane | bitfield | 80 → 50 | FCS-101/102/201 |
| `AV.LRU.BIT.*`, `AV.LRU.HEALTH.*.TEMP`, `AV.RT.STATUS.*` | per-RT BIT, device temperature (degF), 1553 status | | 12.5 / 50 | AVI-201…205, 301 |
| `MX.SOAP.FE`, `MX.OIL_SERVICING.*`, `MX.BORESCOPE`, `MX.BRAKE_WEAR`, `MX.TYRE_P.*`, `MX.ACCUM_PRECHARGE` | ground inspections (oil Fe ppm, oil added L, borescope grade, wear %, pressures) | | INSP | how these reach the contract is an open question ([09](09-implications-and-open-questions.md)) |

Notes: `ENG.CHIP` and `ENG.VIB.*` have `source_lru` ECMS but ride FADEC RT5 — the contract `source_lru` says
ECMS. Raw 10 kHz vibration never leaves the aircraft (1 Hz features only). The FADEC's `ENG.LIMIT_FLAGS`
oil-pressure and vibration bits are always 0 (not M08's job — M14 monitors those).
