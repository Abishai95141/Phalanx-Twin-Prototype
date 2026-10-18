# Phalanx ground-decoder contract 0.2.0 (FROZEN)

> Generated from `src/phalanx/dictionary/contract/spec/` by `phalanx.dictionary.contract.markdown`. Do not edit by hand.
> Status: **frozen** by the owner (AD-41: a frozen version never changes); any change needs a semver bump, a migration note and a decision-register entry (architecture §12).

- **Contract:** `phalanx.ground_decoder_contract` version `0.2.0`
- **Contract hash (blake2b-256 of the canonical spec):** `a4396f1d5482ce7816354ed7c9b040179d3c1467a7ca6e75b21fd71e1a904566`
- **Schema hash (blake2b-256 of the generated Arrow schemas):** `e8313f4817131f2e5f62babb74c96a495ca407e7306af0c5da3ad8cfde13e7b1`
- **Topics:** 10; **enumerations:** 18; **flag sets:** 1

The stable boundary between the Phalanx data layer and downstream predictive-maintenance and availability solutions: the ground-decoder output. It is identical on the fast path (CIR -> contract, provenance=direct), on the full path (CIR -> bus -> Ch10 -> ground decoder, provenance=full_path) and for future real data. Synthetic code tables referenced by these records are labelled synthetic; nothing here is the real Tejas ICD.

## Conventions

- **Time** (ARCH §17 AD-35): every time field is `int64` `ns`. Scales:
  - `sim_utc`: Simulated UTC calendar: integer nanoseconds since 1970-01-01T00:00:00Z on the POSIX time scale (no leap seconds). The kernel's truth step k of a run whose epoch is E maps exactly to E + (k*10**9)//240 (AD-35). Valid range 0 .. 2**63-1.
  - `recorder_rtc`: Recorder relative time counter expressed in nanoseconds (IRIG 106 Ch10 10 MHz RTC ticks x 100 ns). The origin is the recorder's arbitrary free-running count, per recording; it is not comparable across recordings. Valid range 0 .. 2**63-1.
  - `duration`: Non-negative duration in nanoseconds.
- **record_id** (ARCH §12; ASSUMPTION: A-W0.4-2): blake2b, 16 bytes, person `phalanx.rid.v0`. Input bytes = enc_str(topic) followed by each identity component in the topic's record_id_key order. enc_str(s) = b'S' + uint32_le(len(utf8(s))) + utf8(s); a record_id component = b'R' + its 16 bytes; a null string or record_id = b'N'; an unsigned integer component = b'U' + uint64_le(v); a signed integer component = b'I' + int64_le(v). The encoding is injective, so two records share an id only on a blake2b collision. String and record_id components precede integer components. Representation: Arrow fixed_size_binary(16); Avro fixed(16) RecordId; JSON lower-case hex, 32 characters.
- **NaN:** The contract never carries NaN or infinities in a float field (validated). Missing values are null; a sentinel word is carried as its decoded value with the SENTINEL quality flag. Real recorder data are lattice-valued with no NaN [MEASURED: E1, analysis/dashlink_texture].
- **Restricted data:** A topic or field marked restricted carries truth or regeneration secrets. It is never part of the consumer view: Contract.consumer_schema() drops restricted fields, and consumer readers refuse restricted topics (invariant I5).
- **Nullability:** every field states it explicitly; a non-nullable field never holds null (validated, including nested list items and struct members).
- **Evidence basis:** `ARCH §n` = mandated by the binding architecture; `TRANSFER: src` = taken from a public standard or donor practice; `ASSUMPTION: A-W0.4-n` = W0.4 choice, listed below for review.
- **Formats (AD-13):** Arrow schemas are the source; Parquet on disk (partitioned by date / tail / sortie); Avro generated from Arrow for the v1.x Kafka adapter; manifests and orders also as JSON with JSON-Schema.

## Topics

| Topic | Event time | Ingest time | Partitioning | Visible to consumers | JSON-Schema |
|---|---|---|---|---|---|
| `param.samples` | `t_sample` | `t_ingest` | `date/tail_no/sortie_id` | yes | no |
| `events.bit_faults` | `t_occurrence` | `t_ingest` | `date/tail_no/sortie_id` | yes | no |
| `events.exceedances` | `t_occurrence` | `t_ingest` | `date/tail_no/sortie_id` | yes | no |
| `events.cautions` | `t_occurrence` | `t_ingest` | `date/tail_no/sortie_id` | yes | no |
| `usage.counters` | `t_update` | `t_ingest` | `date/tail_no/sortie_id` | yes | no |
| `sortie.manifest` | `t_start` | `t_ingest` | `date/tail_no/sortie_id` | yes | yes |
| `maint.records` | `t_event` | `t_ingest` | `date/tail_no` | yes | no |
| `orders.commands` | `t_issued` | `t_issued` | `date` | yes | yes |
| `orders.status` | `t_status` | `t_status` | `date` | yes | yes |
| `labels.truth` | `t_true` | `-` | `date/tail_no/sortie_id` | no (restricted) | no |

## Enumerations

### `Validity`

Per-sample validity. ARINC 429 SSM semantics (NORMAL, NO_COMPUTED_DATA, FUNCTIONAL_TEST, FAILURE_WARNING) plus BUS_INVALID from 1553 status or validity words. *Basis:* ARCH §12

| Symbol | Meaning |
|---|---|
| `NORMAL` | Normal operation; the value is valid. |
| `NO_COMPUTED_DATA` | Source cannot compute a valid value (ARINC 429 NCD). |
| `FUNCTIONAL_TEST` | Value produced under a functional test (ARINC 429 FT). |
| `FAILURE_WARNING` | Source declares a failure (ARINC 429 FW). |
| `BUS_INVALID` | 1553 status or validity word marks the data invalid. |

### `Provenance`

How the record reached the contract. full_path = via bus, Ch10 recorder and ground decoder; direct = fast path or a direct ground producer (M18 records, M21 order status, manifests). *Basis:* ARCH §12

| Symbol | Meaning |
|---|---|
| `full_path` | Bus -> Ch10 -> ground decoder (W1.7). |
| `direct` | Fast path (CIR -> contract) or a direct ground producer. |

### `DetectionMechanism`

How an event was detected. *Basis:* ARCH §12; TRANSFER: S5000F DetectionMechanism

| Symbol | Meaning |
|---|---|
| `PBIT` | Power-up built-in test. |
| `CBIT` | Continuous built-in test. |
| `MBIT` | Maintenance built-in test (ground). |
| `IBIT` | Initiated built-in test. |
| `EXCEEDANCE` | Limit-plus-persistence monitor (ECMS/HUMS/OAC). |
| `PILOT` | Pilot report. |

### `EventSeverity`

Alerting level of the event (S5000F eventSeverity). *Basis:* TRANSFER: MIL-STD-411C alerting (HAL CWS, research_notes tejas_avionics_and_parameter_inventory.md); ASSUMPTION: A-W0.4-10

| Symbol | Meaning |
|---|---|
| `ADVISORY` | Advisory; no crew action required. |
| `CAUTION` | Caution (amber); crew awareness and possible action. |
| `WARNING` | Warning (red); immediate crew action. |

### `ConfirmedStatus`

Confirmation state as known by the emitter at emission time. On-board events are emitted UNCONFIRMED; confirmation or refutation is a later maintenance outcome carried in maint.records. *Basis:* TRANSFER: S5000F eventConfirmedStatus; ASSUMPTION: A-W0.4-10

| Symbol | Meaning |
|---|---|
| `UNCONFIRMED` | Not yet confirmed or refuted. |
| `CONFIRMED` | Confirmed as a real fault. |
| `NOT_CONFIRMED` | Could not be confirmed (CND/NFF). |

### `FaultList`

Fault-list level. *Basis:* ARCH §12 (PFL/MFL level)

| Symbol | Meaning |
|---|---|
| `PFL` | Pilot fault list (cockpit or CWS visible). |
| `MFL` | Maintenance fault list (maintenance only). |

### `MaintRecordType`

The §10 record types. *Basis:* ARCH §10; TRANSFER: NAMP 4790.2E, TO 00-20, UK F700, S5000F

| Symbol | Meaning |
|---|---|
| `SORTIE` | Sortie / flight record (NAVFLIR, AFTO 781H). |
| `TECH_LOG` | Aircraft status / technical log (UK F700, AFTO 781K). |
| `DEFECT_WO` | Defect work order, a 'snag' (NAMP WO, AFTO 781A). |
| `COMPONENT_LIFE` | Component install/remove life record. |
| `INSPECTION` | Inspection or servicing (look/fix phases). |
| `SUPPLY_DEMAND` | Supply demand / AOG demand. |
| `CANNIBALISATION` | Cannibalisation (two linked jobs). |
| `MODIFICATION` | Modification or software load. |
| `EXCEEDANCE_INSPECTION` | Exceedance-triggered conditional inspection. |
| `SHOP_FINDING` | Shop / depot finding. |
| `AVAILABILITY_STATE` | Availability state for one 15-minute bin (SCIR-style). |

### `MaintStatus`

Lifecycle state of a maintenance record version. *Basis:* TRANSFER: NAMP job status (In Work/AWM/AWP/Complete); ASSUMPTION: A-W0.4-13

| Symbol | Meaning |
|---|---|
| `OPEN` | Raised; work not started. |
| `IN_WORK` | Work in progress. |
| `AWAITING_PARTS` | Awaiting parts (AWP). |
| `AWAITING_MAINTENANCE` | Awaiting maintenance (AWM). |
| `DEFERRED` | Deferred with limits or monitoring. |
| `CLOSED` | Closed or completed. |

### `SupplyPriority`

Supply demand priority. *Basis:* TRANSFER: IAF AOG/MCM/PHU demand priorities (research_notes maintenance_records_and_events.md)

| Symbol | Meaning |
|---|---|
| `AOG` | Aircraft on ground. |
| `MCM` | IAF MCM demand priority (definition not public; research-notes gap). |
| `PHU` | IAF PHU demand priority (definition not public; research-notes gap). |

### `InstallAction`

Component life-record action. *Basis:* ARCH §10 (component life record)

| Symbol | Meaning |
|---|---|
| `INSTALL` | Item installed. |
| `REMOVE` | Item removed. |

### `ShopFinding`

Shop or depot finding on a turned-in item. *Basis:* ARCH §10; TRANSFER: NAMP/USAF NRTS

| Symbol | Meaning |
|---|---|
| `CONFIRMED` | Failure confirmed. |
| `RTOK` | Retest OK (no fault found). |
| `BCM` | Beyond capability of maintenance. |

### `ComplianceStatus`

Compliance status of a modification or software-load order. *Basis:* ARCH §10 (modification compliance status); ASSUMPTION: A-W0.4-13

| Symbol | Meaning |
|---|---|
| `ISSUED` | Issued; not complied. |
| `COMPLIED` | Complied with. |
| `NOT_APPLICABLE` | Does not apply (QA-verified). |

### `AvailabilityState`

Mission-capability state of one 15-minute bin, highest degraded priority wins. *Basis:* ARCH §10; TRANSFER: NAMP SCIR binning (NMCD > NMCS > NMCM-U > NMCM-S > PMCS > PMCM)

| Symbol | Meaning |
|---|---|
| `FMC` | Fully mission capable. |
| `PMCM` | Partially mission capable, maintenance. |
| `PMCS` | Partially mission capable, supply. |
| `NMCM_S` | Not mission capable, scheduled maintenance. |
| `NMCM_U` | Not mission capable, unscheduled maintenance. |
| `NMCS` | Not mission capable, supply. |
| `NMCD` | Not mission capable, depot. |

### `IssuerKind`

Who issued an order. *Basis:* ARCH §11.1 (issuer: agent/human)

| Symbol | Meaning |
|---|---|
| `AGENT` | An automated decision agent. |
| `HUMAN` | A human planner or operator. |

### `OrderAction`

The order action vocabulary of architecture §11.1. *Basis:* ARCH §11.1 action vocabulary; ASSUMPTION: A-W0.4-14 (symbol names)

| Symbol | Meaning |
|---|---|
| `INSPECT` | Inspect (borescope, conditional, NDT); type in parameters. |
| `TROUBLESHOOT` | Troubleshoot a fault code. |
| `REMOVE_REPLACE` | Remove/replace (specific S/N or any serviceable). |
| `WASH_SERVICE` | Engine wash and servicing (oil, hydraulic, tyres). |
| `DEFER` | Defer a defect with limits and expiry. |
| `CANNIBALISE` | Cannibalise from a donor tail. |
| `REQUISITION_SPARES` | Requisition spares. |
| `EXPEDITE_SPARES` | Expedite spares. |
| `TRANSFER_STOCK` | Transfer stock between bases. |
| `GROUND` | Ground an aircraft. |
| `RELEASE` | Release an aircraft. |
| `BRING_FORWARD_SERVICING` | Bring forward scheduled servicing. |
| `DEFER_SERVICING` | Defer scheduled servicing. |
| `ASSIGN_SORTIE` | Assign or reassign sorties and mission types. |
| `RESTRICT_USAGE` | Restrict usage (e.g. AB or g limit). |
| `EMBODY_MODIFICATION` | Embody a modification. |
| `LOAD_SOFTWARE` | Embody a software load. |
| `CHANGE_MONITORING_CONFIG` | Change monitoring configuration (filter lists, thresholds). |

### `OrderPriority`

Order priority. *Basis:* ARCH §11.1 (priority); TRANSFER: AOG/MCM/PHU; ASSUMPTION: A-W0.4-14 (ROUTINE)

| Symbol | Meaning |
|---|---|
| `ROUTINE` | Routine. |
| `PHU` | IAF PHU priority (definition not public). Symbol order is not a ranking. |
| `MCM` | IAF MCM priority (definition not public). Symbol order is not a ranking. |
| `AOG` | Aircraft on ground. |

### `OrderStatus`

Order lifecycle state. *Basis:* ARCH §11.1 (orders.status lifecycle)

| Symbol | Meaning |
|---|---|
| `ACCEPTED` | Validated and accepted. |
| `QUEUED` | Waiting for resources or the next epoch. |
| `IN_WORK` | Being executed. |
| `COMPLETED` | Execution finished. |
| `REJECTED` | Rejected; reason required. |

### `LabelKind`

Kind of restricted truth label. *Basis:* ARCH §12 (labels.truth: hidden states, fault schedule, defect manifest); ASSUMPTION: A-W0.4-16

| Symbol | Meaning |
|---|---|
| `TRUTH_SAMPLE` | Truth value behind a CIR sample. |
| `HIDDEN_STATE` | Hidden health state per serial (M10). |
| `FAULT` | Fault schedule entry (M11). |
| `DEFECT` | Injected data-quality defect (defect manifest, M18). |

## Flag sets

### `QualityFlags` (uint32 carrier, 32 bits)

Quality flag bit set. Bit positions are stable for the life of the contract: a new flag takes the next free bit (minor version); bits 11-31 are reserved and must be zero. Scope says which stage may set a flag: acquisition (M12-M14, M08, M05; may appear in CIR), bus (M15), recorder (M16 time source and recorder), ground (M17 decoder and ingest only). *Basis:* ARCH §12; ASSUMPTION: A-W0.4-8 (bit positions, width, scopes)

| Bit | Mask | Flag | Scope | Meaning |
|---|---|---|---|---|
| 0 | `0x00000001` | `SENTINEL` | acquisition | Value is a sentinel word (e.g. bottom-of-scale in an analog slip window), not a measurement. |
| 1 | `0x00000002` | `GATED` | acquisition | Value gated by acquisition validity logic. |
| 2 | `0x00000004` | `HELD_STALE` | acquisition | Value held from an earlier sample (freeze or hold). |
| 3 | `0x00000008` | `DUPLICATE_POLL` | bus | Same producer update read twice by an asynchronous poll. |
| 4 | `0x00000010` | `SUBSTITUTED` | acquisition | Value synthesised by FADEC or a signal validator (model substitution). |
| 5 | `0x00000020` | `VOTED_OUT` | acquisition | Lane voted out by redundancy management. |
| 6 | `0x00000040` | `OUT_OF_RANGE` | acquisition | Value outside the declared range or saturated. |
| 7 | `0x00000080` | `CLOCK_SUSPECT` | recorder | Time base suspect (clock jump or drift beyond tolerance). |
| 8 | `0x00000100` | `TIME_SOURCE_INTERNAL` | recorder | Absolute time from the internal clock (GPS/IRIG lock lost). |
| 9 | `0x00000200` | `DUPLICATE_DOWNLOAD` | ground | Record first delivered by a repeat download of the same sortie; already-seen record_ids are dropped by idempotent ingest. |
| 10 | `0x00000400` | `DECODER_INTERPOLATED` | ground | Ground decoder interpolated the value or a time field. |

Reserved mask (must be zero): `0xfffff800`

## Topic definitions

### `param.samples`

Decoded parameter samples: one record per parameter value per acquisition, with six-time provenance (t_true is CIR- and labels-only), validity, quality flags and data-path provenance.

- **Basis:** ARCH §12
- **Event time:** `t_sample`; **ingest time:** `t_ingest`
- **Partitioning:** `date/tail_no/sortie_id`
- **JSON-Schema:** no; **consumer-visible:** yes
- **record_id key:** `provenance` (str, column), `tail_no` (str, column), `sortie_id` (str, column), `channel_id` (str, path), `param_id` (str, column), `seq` (u64, path), `msg_index` (u64, path)
  - `channel_id`: Full path: the IRIG 106 Ch10 channel ID, decimal, written '<recording_id>:<channel ID>' when the record's recording_id is set (0.2.0, A-W0.4-22: Ch10 channel IDs are unique only within one recording; a null recording_id keeps the 0.1.0 form). Fast path: 'direct:<source_lru>:<lane or empty>' (A-W0.4-3).
  - `seq`: Full path: cumulative, non-wrapping packet counter of the channel within the recording (the Ch10 8-bit sequence number wraps, so the decoder counts packets). Fast path: CIR sample_index.
  - `msg_index`: Full path: message (and word) index inside the packet. Fast path: 0.
- **Row invariants:** `t_ingest >= t_sample` (where both non-null); `t_bus >= t_sample` (where both non-null); record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key; blake2b-128 of the topic's record_id_key components (see record_id rules). | ARCH §12 |
| `dict_version` | `string` | no | Parameter-dictionary semantic version (M01) the record was produced against. | ARCH §12 |
| `dict_hash` | `string` | no | Parameter-dictionary content hash, lower-case hex (M01). Appears on every record.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12 |
| `param_id` | `string` | no | Parameter-dictionary key (M01). | ARCH §12 |
| `tail_no` | `string` | no | Aircraft tail number (linkage key).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage); ASSUMPTION: A-W0.4-7 (pattern) |
| `sortie_id` | `string` | no | Sortie identifier (tail + date + take-off time, M02).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §5.3, §12 (linkage); ASSUMPTION: A-W0.4-7 (pattern) |
| `engine_serial` | `string` | yes | Serial of the engine the parameter belongs to; null for non-engine parameters. | ARCH §12 (where relevant); ASSUMPTION: A-W0.4-7 |
| `source_lru` | `string` | no | LRU that acquired or computed the value (data-path provenance).[pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`] | ARCH §12; ASSUMPTION: A-W0.4-7 (pattern) |
| `lane` | `string` | yes | Redundancy lane or channel of a redundant source (e.g. DFCC channel); null if not redundant.[pattern `^[A-Za-z0-9]+$`] | ARCH §12; ASSUMPTION: A-W0.4-7 |
| `bus` | `string` | yes | Bus the value travelled on (synthetic Phalanx ICD bus name); null on the fast path and for direct analog channels. | ARCH §12; ASSUMPTION: A-W0.4-7 |
| `rt_sa_word` | `string` | yes | MIL-STD-1553 location 'RTnn/SAnn/Wnn' (remote terminal, subaddress, data-word index) in the synthetic Phalanx ICD; null if not 1553.[pattern `^RT([0-2][0-9]\|3[01])/SA([0-2][0-9]\|3[01])/W([0-2][0-9]\|3[01])$`] | ARCH §12; ASSUMPTION: A-W0.4-7 (format) |
| `label_sdi` | `string` | yes | ARINC 429 location 'Looo/SDIn' (octal label, source/destination identifier) in the synthetic Phalanx ICD; null if not ARINC 429.[pattern `^L[0-3][0-7][0-7]/SDI[0-3]$`] | ARCH §12; ASSUMPTION: A-W0.4-7 (format) |
| `t_sample` | `time_ns (sim_utc)` | no | When the owning LRU acquired the value, on its drifting oscillator. The event time of the record. | ARCH §8, §12; ASSUMPTION: A-W0.4-1 (scale) |
| `t_bus` | `time_ns (sim_utc)` | yes | When the value appeared on the bus, at the Ch10-defined bit. Null on the fast path and for non-bus channels. | ARCH §8, §12; ASSUMPTION: A-W0.4-4 |
| `t_record` | `time_ns (recorder_rtc)` | yes | Recorder RTC time of the sample (per-recording origin). Null on the fast path. | ARCH §8, §12; ASSUMPTION: A-W0.4-4 |
| `t_utc` | `time_ns (sim_utc)` | yes | Absolute time from the aircraft's simulated GPS/IRIG time source (TIME_SOURCE_INTERNAL when lock is lost). Fast path sets t_utc = t_sample (PROXY). | ARCH §8, §12; ASSUMPTION: A-W0.4-4 |
| `t_ingest` | `time_ns (sim_utc)` | no | Arrival at the ground (per-sortie download burst). Consumers see a record only once t_ingest <= t_now (I5). | ARCH §8, §12, I5; ASSUMPTION: A-W0.4-5 |
| `value_eu` | `float64` | no | Decoded engineering value in `units`. Never NaN; a sentinel is carried as its value with the SENTINEL flag. | ARCH §12; MEASURED: E1 (no NaN); ASSUMPTION: A-W0.4-7 |
| `raw_counts` | `int64` | yes | Raw bus word or ADC counts before engineering-unit conversion. Null on the fast path. | ARCH §12; ASSUMPTION: A-W0.4-4 |
| `units` | `string` | no | Engineering unit of value_eu as declared by the dictionary (pint-parseable). | ARCH §12 |
| `validity` | `enum:Validity` | no | Validity state (ARINC 429 SSM semantics plus 1553 BUS_INVALID). | ARCH §12 |
| `quality_flags` | `flags:QualityFlags` | no | Quality flag bit set (see QualityFlags). | ARCH §12; ASSUMPTION: A-W0.4-8 |
| `provenance` | `enum:Provenance` | no | full_path (bus, Ch10, decoder) or direct (fast path). | ARCH §12 |
| `recording_id` | `string` | yes | On-board recording the record was decoded from (one recording per recorder sink and sortie, AD-25), unique within (tail_no, sortie_id). t_record and the Ch10 channel ID are comparable only within one recording. Null on the fast path and for a sortie's single unattributed bus-monitor capture (the 0.1.0 full path).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §17 AD-25, AD-45; ASSUMPTION: A-W0.4-22 |
| `sink` | `string` | yes | Dictionary sink (M01 sinks table: CDR, ECMS_HUMS, MPDRU, FTI) whose recording carried the record; null exactly when recording_id is null.[pattern `^[A-Z][A-Z0-9_]*$`] | ARCH §17 AD-25; ASSUMPTION: A-W0.4-22 |

### `events.bit_faults`

Built-in-test fault events (PBIT/CBIT/MBIT/IBIT) as decoded on the ground. Every event is also present in the sortie's Ch10 file as a recording event (emitted twice, architecture §12).

- **Basis:** ARCH §12
- **Event time:** `t_occurrence`; **ingest time:** `t_ingest`
- **Partitioning:** `date/tail_no/sortie_id`
- **JSON-Schema:** no; **consumer-visible:** yes
- **record_id key:** `provenance` (str, column), `tail_no` (str, column), `sortie_id` (str, column), `channel_id` (str, path), `event_code` (str, column), `seq` (u64, path), `msg_index` (u64, path)
  - `channel_id`: Full path: Ch10 channel ID of the event/BIT-word channel, decimal. Fast path: 'direct:<source_lru>'.
  - `seq`: Full path: cumulative packet counter of that channel. Fast path: occurrence index of (source_lru, event_code) within the sortie, in t_occurrence order.
  - `msg_index`: Full path: event index inside the packet. Fast path: 0.
- **Row invariants:** `t_ingest >= t_occurrence` (where both non-null); `snapshot_t_end >= snapshot_t_start` (where both non-null); record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key; blake2b-128 of the topic's record_id_key components (see record_id rules). | ARCH §12 |
| `dict_version` | `string` | no | Parameter-dictionary semantic version (M01) the record was produced against. | ARCH §12 |
| `dict_hash` | `string` | no | Parameter-dictionary content hash, lower-case hex (M01). Appears on every record.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12 |
| `event_id` | `string` | no | Identifier of the event occurrence, stable between its Ch10 recording event and its ground record. | ARCH §12; TRANSFER: S5000F eventIdentifier |
| `tail_no` | `string` | no | Aircraft tail number.[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage) |
| `sortie_id` | `string` | yes | Sortie of the event; null for ground events outside a sortie (e.g. IBIT/MBIT on the line).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage); ASSUMPTION: A-W0.4-10 |
| `engine_serial` | `string` | yes | Engine serial for engine events; null otherwise. | ARCH §12 (linkage) |
| `source_lru` | `string` | no | LRU or monitor that detected and reported the event.[pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`] | ARCH §12; TRANSFER: S5000F EventReporter |
| `event_code` | `string` | no | Synthetic fault, exceedance or caution code from the M01 code tables (labelled synthetic; not a real Tejas code). | ARCH AD-19 (synthetic SSS-NNN codes); ASSUMPTION: A-W0.4-10 |
| `event_group` | `string` | no | Event group (subsystem class, e.g. ENGINE, HYDRAULICS), from the M01 code tables. | TRANSFER: S5000F eventGroup; ASSUMPTION: A-W0.4-10 |
| `severity` | `enum:EventSeverity` | no | Alerting level. | TRANSFER: S5000F eventSeverity, MIL-STD-411C; ASSUMPTION: A-W0.4-10 |
| `description` | `string` | yes | Code-table description of the event. | TRANSFER: S5000F eventDescription |
| `confirmed_status` | `enum:ConfirmedStatus` | no | Confirmation state known at emission (on-board events are UNCONFIRMED). | TRANSFER: S5000F eventConfirmedStatus; ASSUMPTION: A-W0.4-10 |
| `detection_mechanism` | `enum:DetectionMechanism` | no | PBIT, CBIT, MBIT, IBIT, EXCEEDANCE or PILOT. | ARCH §12; TRANSFER: S5000F detectionMechanismType |
| `detection_far_per_fh` | `float64` | yes | Nominal (specified) false-alarm rate of the detection mechanism per flight hour, from M01. Never the simulator's true rate.[units `1/h`; range [0.0, inf]] | ARCH §12; TRANSFER: S5000F detectionMechanismFalseAlarmRate; ASSUMPTION: A-W0.4-10 |
| `fault_list` | `enum:FaultList` | yes | PFL (pilot-visible) or MFL (maintenance-only); null where not applicable. | ARCH §12 |
| `latched` | `bool` | no | Latch state of the event at emission. | ARCH §12 (latch state) |
| `persistence_count` | `uint32` | yes | Consecutive frames or iterations the condition persisted before it was declared. | ARCH §12 (persistence count) |
| `suspect_lrus` | `list<struct<lru: string not null, isolation_confidence: float64 not null> not null>` | no | Suspect-LRU list in isolation order; empty when no isolation is made. | ARCH §12 (suspect-LRU list with isolation confidence) |
| `suspect_lrus[].lru` | `string` | no | Suspect LRU.[pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`] | ARCH §12 |
| `suspect_lrus[].isolation_confidence` | `float64` | no | Isolation confidence of this suspect, 0..1.[range [0.0, 1.0]] | ARCH §12 |
| `snapshot_t_start` | `time_ns (sim_utc)` | yes | Start of the event snapshot window (e.g. 5 s before); samples in the window are in param.samples. | ARCH §12 (snapshot window pointer) |
| `snapshot_t_end` | `time_ns (sim_utc)` | yes | End of the event snapshot window (e.g. 25-35 s after). | ARCH §12 (snapshot window pointer) |
| `ch10_event_number` | `uint32` | yes | IRIG 106 Ch10 recording-event number of the on-board copy; null on the fast path. | TRANSFER: IRIG 106 Ch10 recording event (report §13); ASSUMPTION: A-W0.4-10 |
| `t_occurrence` | `time_ns (sim_utc)` | no | When the event was declared on board. The event time of the record. | TRANSFER: S5000F eventOccurrenceDateTime; ASSUMPTION: A-W0.4-1 |
| `t_record` | `time_ns (recorder_rtc)` | yes | Recorder RTC time of the on-board copy; null on the fast path. | ARCH §8; ASSUMPTION: A-W0.4-4 |
| `t_utc` | `time_ns (sim_utc)` | yes | Absolute time from the aircraft time source. | ARCH §8; ASSUMPTION: A-W0.4-4 |
| `t_ingest` | `time_ns (sim_utc)` | no | Arrival at the ground. | ARCH §8, I5 |
| `quality_flags` | `flags:QualityFlags` | no | Quality flag bit set. | ARCH §12 |
| `provenance` | `enum:Provenance` | no | full_path or direct. | ARCH §12 |
| `lane` | `string` | yes | Lane or channel of a redundant LRU that reported the BIT fault; null if not redundant.[pattern `^[A-Za-z0-9]+$`] | ARCH §6 M05/M14 (per-channel BIT); ASSUMPTION: A-W0.4-10 |
| `raw_bit_word` | `int64` | yes | Raw BIT or status word as recorded; null on the fast path. | ARCH §6 M15 (status and BIT words); ASSUMPTION: A-W0.4-10 |

### `events.exceedances`

Limit exceedances declared by on-board monitoring (ECMS/HUMS/OAC): over-temperature, overspeed, over-g, hard landing. Each exceedance can trigger a conditional inspection in maint.records.

- **Basis:** ARCH §12
- **Event time:** `t_occurrence`; **ingest time:** `t_ingest`
- **Partitioning:** `date/tail_no/sortie_id`
- **JSON-Schema:** no; **consumer-visible:** yes
- **record_id key:** `provenance` (str, column), `tail_no` (str, column), `sortie_id` (str, column), `channel_id` (str, path), `event_code` (str, column), `seq` (u64, path), `msg_index` (u64, path)
  - `channel_id`: Full path: Ch10 channel ID of the event channel, decimal. Fast path: 'direct:<source_lru>'.
  - `seq`: Full path: cumulative packet counter of that channel. Fast path: occurrence index of (source_lru, event_code) within the sortie, in t_occurrence order.
  - `msg_index`: Full path: event index inside the packet. Fast path: 0.
- **Row invariants:** `t_ingest >= t_occurrence` (where both non-null); `snapshot_t_end >= snapshot_t_start` (where both non-null); `t_end >= t_occurrence` (where both non-null); record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key; blake2b-128 of the topic's record_id_key components (see record_id rules). | ARCH §12 |
| `dict_version` | `string` | no | Parameter-dictionary semantic version (M01) the record was produced against. | ARCH §12 |
| `dict_hash` | `string` | no | Parameter-dictionary content hash, lower-case hex (M01). Appears on every record.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12 |
| `event_id` | `string` | no | Identifier of the event occurrence, stable between its Ch10 recording event and its ground record. | ARCH §12; TRANSFER: S5000F eventIdentifier |
| `tail_no` | `string` | no | Aircraft tail number.[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage) |
| `sortie_id` | `string` | yes | Sortie of the event; null for ground events outside a sortie (e.g. IBIT/MBIT on the line).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage); ASSUMPTION: A-W0.4-10 |
| `engine_serial` | `string` | yes | Engine serial for engine events; null otherwise. | ARCH §12 (linkage) |
| `source_lru` | `string` | no | LRU or monitor that detected and reported the event.[pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`] | ARCH §12; TRANSFER: S5000F EventReporter |
| `event_code` | `string` | no | Synthetic fault, exceedance or caution code from the M01 code tables (labelled synthetic; not a real Tejas code). | ARCH AD-19 (synthetic SSS-NNN codes); ASSUMPTION: A-W0.4-10 |
| `event_group` | `string` | no | Event group (subsystem class, e.g. ENGINE, HYDRAULICS), from the M01 code tables. | TRANSFER: S5000F eventGroup; ASSUMPTION: A-W0.4-10 |
| `severity` | `enum:EventSeverity` | no | Alerting level. | TRANSFER: S5000F eventSeverity, MIL-STD-411C; ASSUMPTION: A-W0.4-10 |
| `description` | `string` | yes | Code-table description of the event. | TRANSFER: S5000F eventDescription |
| `confirmed_status` | `enum:ConfirmedStatus` | no | Confirmation state known at emission (on-board events are UNCONFIRMED). | TRANSFER: S5000F eventConfirmedStatus; ASSUMPTION: A-W0.4-10 |
| `detection_mechanism` | `enum:DetectionMechanism` | no | PBIT, CBIT, MBIT, IBIT, EXCEEDANCE or PILOT. | ARCH §12; TRANSFER: S5000F detectionMechanismType |
| `detection_far_per_fh` | `float64` | yes | Nominal (specified) false-alarm rate of the detection mechanism per flight hour, from M01. Never the simulator's true rate.[units `1/h`; range [0.0, inf]] | ARCH §12; TRANSFER: S5000F detectionMechanismFalseAlarmRate; ASSUMPTION: A-W0.4-10 |
| `fault_list` | `enum:FaultList` | yes | PFL (pilot-visible) or MFL (maintenance-only); null where not applicable. | ARCH §12 |
| `latched` | `bool` | no | Latch state of the event at emission. | ARCH §12 (latch state) |
| `persistence_count` | `uint32` | yes | Consecutive frames or iterations the condition persisted before it was declared. | ARCH §12 (persistence count) |
| `suspect_lrus` | `list<struct<lru: string not null, isolation_confidence: float64 not null> not null>` | no | Suspect-LRU list in isolation order; empty when no isolation is made. | ARCH §12 (suspect-LRU list with isolation confidence) |
| `suspect_lrus[].lru` | `string` | no | Suspect LRU.[pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`] | ARCH §12 |
| `suspect_lrus[].isolation_confidence` | `float64` | no | Isolation confidence of this suspect, 0..1.[range [0.0, 1.0]] | ARCH §12 |
| `snapshot_t_start` | `time_ns (sim_utc)` | yes | Start of the event snapshot window (e.g. 5 s before); samples in the window are in param.samples. | ARCH §12 (snapshot window pointer) |
| `snapshot_t_end` | `time_ns (sim_utc)` | yes | End of the event snapshot window (e.g. 25-35 s after). | ARCH §12 (snapshot window pointer) |
| `ch10_event_number` | `uint32` | yes | IRIG 106 Ch10 recording-event number of the on-board copy; null on the fast path. | TRANSFER: IRIG 106 Ch10 recording event (report §13); ASSUMPTION: A-W0.4-10 |
| `t_occurrence` | `time_ns (sim_utc)` | no | When the event was declared on board. The event time of the record. | TRANSFER: S5000F eventOccurrenceDateTime; ASSUMPTION: A-W0.4-1 |
| `t_record` | `time_ns (recorder_rtc)` | yes | Recorder RTC time of the on-board copy; null on the fast path. | ARCH §8; ASSUMPTION: A-W0.4-4 |
| `t_utc` | `time_ns (sim_utc)` | yes | Absolute time from the aircraft time source. | ARCH §8; ASSUMPTION: A-W0.4-4 |
| `t_ingest` | `time_ns (sim_utc)` | no | Arrival at the ground. | ARCH §8, I5 |
| `quality_flags` | `flags:QualityFlags` | no | Quality flag bit set. | ARCH §12 |
| `provenance` | `enum:Provenance` | no | full_path or direct. | ARCH §12 |
| `param_id` | `string` | no | Dictionary parameter whose limit was exceeded. | ARCH §10 (exceedance); ASSUMPTION: A-W0.4-10 |
| `limit_id` | `string` | no | Dictionary limit identifier that was exceeded (limit values may be [ASSUMPTION], swept). | ARCH §6 M01 (limits); ASSUMPTION: A-W0.4-10 |
| `limit_value` | `float64` | no | Limit value in `units`. | ASSUMPTION: A-W0.4-10 |
| `peak_value` | `float64` | no | Peak (or extreme) value of the parameter during the exceedance, in `units`. | ASSUMPTION: A-W0.4-10 |
| `units` | `string` | no | Engineering unit of limit_value and peak_value. | ASSUMPTION: A-W0.4-10 |
| `t_end` | `time_ns (sim_utc)` | yes | End of the exceedance; null if still active at the end of the recording. | ASSUMPTION: A-W0.4-10 |

### `events.cautions`

Centralised-warning-system cautions and warnings (30 legends, 4 voice warnings) as recorded. A caution can be recorded without reaching the pilot (displayed = false; F-35B ZM152 precedent).

- **Basis:** ARCH §12
- **Event time:** `t_occurrence`; **ingest time:** `t_ingest`
- **Partitioning:** `date/tail_no/sortie_id`
- **JSON-Schema:** no; **consumer-visible:** yes
- **record_id key:** `provenance` (str, column), `tail_no` (str, column), `sortie_id` (str, column), `channel_id` (str, path), `event_code` (str, column), `seq` (u64, path), `msg_index` (u64, path)
  - `channel_id`: Full path: Ch10 channel ID of the discrete/event channel, decimal. Fast path: 'direct:<source_lru>'.
  - `seq`: Full path: cumulative packet counter of that channel. Fast path: occurrence index of (source_lru, event_code) within the sortie, in t_occurrence order.
  - `msg_index`: Full path: event index inside the packet. Fast path: 0.
- **Row invariants:** `t_ingest >= t_occurrence` (where both non-null); `snapshot_t_end >= snapshot_t_start` (where both non-null); `t_cleared >= t_occurrence` (where both non-null); record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key; blake2b-128 of the topic's record_id_key components (see record_id rules). | ARCH §12 |
| `dict_version` | `string` | no | Parameter-dictionary semantic version (M01) the record was produced against. | ARCH §12 |
| `dict_hash` | `string` | no | Parameter-dictionary content hash, lower-case hex (M01). Appears on every record.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12 |
| `event_id` | `string` | no | Identifier of the event occurrence, stable between its Ch10 recording event and its ground record. | ARCH §12; TRANSFER: S5000F eventIdentifier |
| `tail_no` | `string` | no | Aircraft tail number.[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage) |
| `sortie_id` | `string` | yes | Sortie of the event; null for ground events outside a sortie (e.g. IBIT/MBIT on the line).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage); ASSUMPTION: A-W0.4-10 |
| `engine_serial` | `string` | yes | Engine serial for engine events; null otherwise. | ARCH §12 (linkage) |
| `source_lru` | `string` | no | LRU or monitor that detected and reported the event.[pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`] | ARCH §12; TRANSFER: S5000F EventReporter |
| `event_code` | `string` | no | Synthetic fault, exceedance or caution code from the M01 code tables (labelled synthetic; not a real Tejas code). | ARCH AD-19 (synthetic SSS-NNN codes); ASSUMPTION: A-W0.4-10 |
| `event_group` | `string` | no | Event group (subsystem class, e.g. ENGINE, HYDRAULICS), from the M01 code tables. | TRANSFER: S5000F eventGroup; ASSUMPTION: A-W0.4-10 |
| `severity` | `enum:EventSeverity` | no | Alerting level. | TRANSFER: S5000F eventSeverity, MIL-STD-411C; ASSUMPTION: A-W0.4-10 |
| `description` | `string` | yes | Code-table description of the event. | TRANSFER: S5000F eventDescription |
| `confirmed_status` | `enum:ConfirmedStatus` | no | Confirmation state known at emission (on-board events are UNCONFIRMED). | TRANSFER: S5000F eventConfirmedStatus; ASSUMPTION: A-W0.4-10 |
| `detection_mechanism` | `enum:DetectionMechanism` | no | PBIT, CBIT, MBIT, IBIT, EXCEEDANCE or PILOT. | ARCH §12; TRANSFER: S5000F detectionMechanismType |
| `detection_far_per_fh` | `float64` | yes | Nominal (specified) false-alarm rate of the detection mechanism per flight hour, from M01. Never the simulator's true rate.[units `1/h`; range [0.0, inf]] | ARCH §12; TRANSFER: S5000F detectionMechanismFalseAlarmRate; ASSUMPTION: A-W0.4-10 |
| `fault_list` | `enum:FaultList` | yes | PFL (pilot-visible) or MFL (maintenance-only); null where not applicable. | ARCH §12 |
| `latched` | `bool` | no | Latch state of the event at emission. | ARCH §12 (latch state) |
| `persistence_count` | `uint32` | yes | Consecutive frames or iterations the condition persisted before it was declared. | ARCH §12 (persistence count) |
| `suspect_lrus` | `list<struct<lru: string not null, isolation_confidence: float64 not null> not null>` | no | Suspect-LRU list in isolation order; empty when no isolation is made. | ARCH §12 (suspect-LRU list with isolation confidence) |
| `suspect_lrus[].lru` | `string` | no | Suspect LRU.[pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`] | ARCH §12 |
| `suspect_lrus[].isolation_confidence` | `float64` | no | Isolation confidence of this suspect, 0..1.[range [0.0, 1.0]] | ARCH §12 |
| `snapshot_t_start` | `time_ns (sim_utc)` | yes | Start of the event snapshot window (e.g. 5 s before); samples in the window are in param.samples. | ARCH §12 (snapshot window pointer) |
| `snapshot_t_end` | `time_ns (sim_utc)` | yes | End of the event snapshot window (e.g. 25-35 s after). | ARCH §12 (snapshot window pointer) |
| `ch10_event_number` | `uint32` | yes | IRIG 106 Ch10 recording-event number of the on-board copy; null on the fast path. | TRANSFER: IRIG 106 Ch10 recording event (report §13); ASSUMPTION: A-W0.4-10 |
| `t_occurrence` | `time_ns (sim_utc)` | no | When the event was declared on board. The event time of the record. | TRANSFER: S5000F eventOccurrenceDateTime; ASSUMPTION: A-W0.4-1 |
| `t_record` | `time_ns (recorder_rtc)` | yes | Recorder RTC time of the on-board copy; null on the fast path. | ARCH §8; ASSUMPTION: A-W0.4-4 |
| `t_utc` | `time_ns (sim_utc)` | yes | Absolute time from the aircraft time source. | ARCH §8; ASSUMPTION: A-W0.4-4 |
| `t_ingest` | `time_ns (sim_utc)` | no | Arrival at the ground. | ARCH §8, I5 |
| `quality_flags` | `flags:QualityFlags` | no | Quality flag bit set. | ARCH §12 |
| `provenance` | `enum:Provenance` | no | full_path or direct. | ARCH §12 |
| `legend` | `string` | no | CWS legend identifier (synthetic legend table from M01). | ARCH §6 M14 (CWS legends); ASSUMPTION: A-W0.4-10 |
| `displayed` | `bool` | no | Whether the caution reached the cockpit display. | ARCH §10 (recorded health data never shown to the pilot); ASSUMPTION: A-W0.4-10 |
| `voice_warning` | `bool` | no | Whether a voice warning accompanied the caution. | ARCH §6 M14 (4 voice warnings); ASSUMPTION: A-W0.4-10 |
| `t_cleared` | `time_ns (sim_utc)` | yes | When the caution cleared; null if still active at the end of the recording. | ASSUMPTION: A-W0.4-10 |

### `usage.counters`

Life-usage and usage counters as reported by their source (ECMS LUIs updated twice per flight, TAC, cycles, starts, landings, Nz level-crossing counts, chute streamings). One record per counter update.

- **Basis:** ARCH §12
- **Event time:** `t_update`; **ingest time:** `t_ingest`
- **Partitioning:** `date/tail_no/sortie_id`
- **JSON-Schema:** no; **consumer-visible:** yes
- **record_id key:** `provenance` (str, column), `tail_no` (str, column), `sortie_id` (str, column), `engine_serial` (str, column), `item_serial` (str, column), `param_id` (str, column), `update_seq` (u64, column)
- **Row invariants:** `t_ingest >= t_update` (where both non-null); record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key; blake2b-128 of the topic's record_id_key components (see record_id rules). | ARCH §12 |
| `dict_version` | `string` | no | Parameter-dictionary semantic version (M01) the record was produced against. | ARCH §12 |
| `dict_hash` | `string` | no | Parameter-dictionary content hash, lower-case hex (M01). Appears on every record.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12 |
| `param_id` | `string` | no | Dictionary counter parameter (e.g. LUI.TYPE3, USAGE.TAC, USAGE.LANDINGS, STRUCT.NZ_COUNTERS). | ARCH §12; ASSUMPTION: A-W0.4-11 |
| `tail_no` | `string` | no | Aircraft tail number.[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage) |
| `sortie_id` | `string` | yes | Sortie the update belongs to; null for ground-computed counters not tied to a sortie.[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage); ASSUMPTION: A-W0.4-11 |
| `engine_serial` | `string` | yes | Engine serial for engine counters (LUIs, TAC, engine starts); null otherwise. | ARCH §12 (linkage); ASSUMPTION: A-W0.4-11 |
| `item_serial` | `string` | yes | Serial of a life-tracked non-engine item the counter belongs to (e.g. chute); null otherwise. | ARCH §5.3 (component identity); ASSUMPTION: A-W0.4-11 |
| `source_lru` | `string` | no | Source of the counter (ECMS, OAC, fatigue meter, ground station).[pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`] | ASSUMPTION: A-W0.4-11 |
| `update_seq` | `uint32` | no | Index of this update of this counter within the sortie (or within the ground period when sortie_id is null). | ARCH §6 M14 (LUIs updated twice per flight); ASSUMPTION: A-W0.4-11 |
| `value_eu` | `float64` | no | Counter reading as reported by the source (cumulative), in `units`.[range [0.0, inf]] | ASSUMPTION: A-W0.4-11 |
| `increment_eu` | `float64` | yes | Increment attributed to this update when the source reports one; null otherwise.[range [0.0, inf]] | ASSUMPTION: A-W0.4-11 |
| `units` | `string` | no | Unit of the counter (count, h). | ARCH §12 |
| `t_update` | `time_ns (sim_utc)` | no | When the source updated the counter. The event time of the record. | ASSUMPTION: A-W0.4-11 |
| `t_record` | `time_ns (recorder_rtc)` | yes | Recorder RTC time; null on the fast path or for ground counters. | ARCH §8 |
| `t_utc` | `time_ns (sim_utc)` | yes | Absolute time from the aircraft time source. | ARCH §8 |
| `t_ingest` | `time_ns (sim_utc)` | no | Arrival at the ground. | ARCH §8, I5 |
| `validity` | `enum:Validity` | no | Validity of the counter reading. | ARCH §12 |
| `quality_flags` | `flags:QualityFlags` | no | Quality flag bit set. | ARCH §12 |
| `provenance` | `enum:Provenance` | no | full_path or direct. | ARCH §12 |

### `sortie.manifest`

One record per sortie: configuration and provenance of the data (tail, engine and LRU serials, software configuration, mission, dictionary and contract versions, code commit, library versions). Seeds and the RNG stream table are restricted fields (A-W0.4-12).

- **Basis:** ARCH §12
- **Event time:** `t_start`; **ingest time:** `t_ingest`
- **Partitioning:** `date/tail_no/sortie_id`
- **JSON-Schema:** yes; **consumer-visible:** yes
- **record_id key:** `tail_no` (str, column), `sortie_id` (str, column)
- **Row invariants:** `t_ingest >= t_start` (where both non-null); `t_takeoff >= t_start` (where both non-null); `t_landing >= t_takeoff` (where both non-null); `t_end >= t_start` (where both non-null); record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key; blake2b-128 of the topic's record_id_key components (see record_id rules). | ARCH §12 |
| `dict_version` | `string` | no | Parameter-dictionary semantic version (M01) the record was produced against. | ARCH §12 |
| `dict_hash` | `string` | no | Parameter-dictionary content hash, lower-case hex (M01). Appears on every record.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12 |
| `tail_no` | `string` | no | Aircraft tail number (linkage key).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §12 (linkage); ASSUMPTION: A-W0.4-7 (pattern) |
| `sortie_id` | `string` | no | Sortie identifier (tail + date + take-off time, M02).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §5.3, §12 (linkage); ASSUMPTION: A-W0.4-7 (pattern) |
| `base` | `string` | yes | Operating base of the sortie. | ARCH §6 M02 (bases); ASSUMPTION: A-W0.4-12 |
| `mission_type` | `string` | no | Mission type from the M02 mission mix. | ARCH §12 (mission) |
| `crew_id` | `string` | yes | Pseudonymous crew identifier (no latent pilot traits). | ARCH §10 (sortie record: crew); ASSUMPTION: A-W0.4-12 |
| `sw_config_id` | `string` | no | Software-configuration identifier of the aircraft for this sortie. | ARCH §5.3, §12 (software config) |
| `engine_serials` | `list<struct<position: string not null, serial: string not null> not null>` | no | Installed engine serials by position. | ARCH §12 (serials) |
| `engine_serials[].position` | `string` | no | Engine position (e.g. '1'). | ARCH §12 |
| `engine_serials[].serial` | `string` | no | Engine serial number. | ARCH §12 |
| `lru_serials` | `list<struct<lru: string not null, part_no: string not null, serial_no: string not null, maker: string> not null>` | no | Installed serialised LRUs (component triplet). | ARCH §12 (serials); ARCH §5.3 (component triplet) |
| `lru_serials[].lru` | `string` | no | LRU name. | ARCH §12 |
| `lru_serials[].part_no` | `string` | no | Part number. | ARCH §5.3 (component triplet) |
| `lru_serials[].serial_no` | `string` | no | Serial number. | ARCH §5.3 (component triplet) |
| `lru_serials[].maker` | `string` | yes | Maker. | ARCH §5.3 (component triplet) |
| `t_start` | `time_ns (sim_utc)` | no | Start of the sortie record (engine start or recorder start). The event time of the record. | ASSUMPTION: A-W0.4-12 |
| `t_takeoff` | `time_ns (sim_utc)` | yes | Take-off time; null for a ground abort. | ARCH §5.3 (sortie_id = tail + date + take-off time) |
| `t_landing` | `time_ns (sim_utc)` | yes | Landing time; null if not airborne. | ASSUMPTION: A-W0.4-12 |
| `t_end` | `time_ns (sim_utc)` | yes | End of the sortie record (engine shutdown or recorder stop). | ASSUMPTION: A-W0.4-12 |
| `t_ingest` | `time_ns (sim_utc)` | no | When the manifest reached the ground (download). | ARCH §8, I5 |
| `contract_version` | `string` | no | Contract semantic version the sortie's records conform to. | ARCH §12 (versioning) |
| `config_hash` | `string` | no | Hash of the run configuration. | ARCH §15 (manifest) |
| `code_commit` | `string` | no | Git commit of the generating code. | ARCH §12 (code commit) |
| `library_versions` | `list<struct<name: string not null, version: string not null> not null>` | no | Library versions, sorted by name. | ARCH §15 (manifest: library versions) |
| `library_versions[].name` | `string` | no | Library name. | ARCH §15 |
| `library_versions[].version` | `string` | no | Library version. | ARCH §15 |
| `run_manifest_hash` | `string` | yes | Content hash of the full run manifest (core/manifest.py) this sortie belongs to. | ARCH §15; ASSUMPTION: A-W0.4-12 |
| `root_seed` | `string` | yes | 128-bit root seed, hex. RESTRICTED (with the code commit it regenerates truth).[**RESTRICTED**; pattern `^[0-9a-f]{32}$`] | ARCH §12 (seeds), §15; ASSUMPTION: A-W0.4-12 (restricted) |
| `rng_stream_table` | `list<struct<key_path: string not null, stream_ref: string not null> not null>` | yes | RNG stream table of the sortie. RESTRICTED.[**RESTRICTED**] | ARCH §12 (seeds), §15 (stream table); ASSUMPTION: A-W0.4-12 (restricted) |
| `rng_stream_table[].key_path` | `string` | no | Canonical text form of the core.rng key path. | ARCH §15 |
| `rng_stream_table[].stream_ref` | `string` | no | Stream reference (digest of the key path). | ARCH §15 |
| `provenance` | `enum:Provenance` | no | direct (manifests are produced on the ground) or full_path (decoded from a recording). | ARCH §12 |

### `maint.records`

The §10 record types in one topic, discriminated by record_type, with linkage keys (tail, sortie, job number, component triplet, demand number, engine serial, sw_config_id, telemetry record_id). Each status change of a record is a new record version. Codes are synthetic IAF-relabelled tables (AD-19). Data-quality defects are injected after truth and listed only in labels.truth.

- **Basis:** ARCH §10, §12
- **Event time:** `t_event`; **ingest time:** `t_ingest`
- **Partitioning:** `date/tail_no`
- **JSON-Schema:** no; **consumer-visible:** yes
- **record_id key:** `record_type` (str, column), `record_key` (str, column), `record_version` (u64, column)
- **Row invariants:** `t_ingest >= t_event` (where both non-null); `t_close >= t_open` (where both non-null); record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key; blake2b-128 of the topic's record_id_key components (see record_id rules). | ARCH §12 |
| `dict_version` | `string` | no | Parameter-dictionary semantic version (M01) the record was produced against. | ARCH §12 |
| `dict_hash` | `string` | no | Parameter-dictionary content hash, lower-case hex (M01). Appears on every record.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12 |
| `record_type` | `enum:MaintRecordType` | no | Record type. | ARCH §10 |
| `record_key` | `string` | no | Natural identity of the record across its versions (job number, demand number, or a synthetic key for logs and bins). | ASSUMPTION: A-W0.4-13 |
| `record_version` | `uint32` | no | Version of the record; a new version is emitted at every status change. | ASSUMPTION: A-W0.4-13 |
| `status` | `enum:MaintStatus` | yes | Lifecycle state of this version; null for records without a lifecycle (e.g. availability bins). | TRANSFER: NAMP job status; ASSUMPTION: A-W0.4-13 |
| `tail_no` | `string` | yes | Aircraft tail; null for base-level records (e.g. stock).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §10 (linkage) |
| `base` | `string` | yes | Base or maintenance organisation. | ARCH §10; ASSUMPTION: A-W0.4-13 |
| `sortie_id` | `string` | yes | Sortie the record refers to (sortie records, write-ups).[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §10 (linkage) |
| `job_no` | `string` | yes | Job ('snag') number. | ARCH §10 (linkage: job number) |
| `linked_job_no` | `string` | yes | Linked job number (cannibalisation donor/recipient, troubleshooting parent). | ARCH §10 (cannibalisation: two linked jobs) |
| `demand_no` | `string` | yes | Supply demand number. | ARCH §10 (linkage: demand number) |
| `engine_serial` | `string` | yes | Engine serial. | ARCH §10 (linkage) |
| `part_no` | `string` | yes | Part number of the item concerned. | ARCH §5.3 (component triplet) |
| `serial_no` | `string` | yes | Serial number of the item concerned (may be a defective default such as 'XXX', ARCH §10). | ARCH §5.3 (component triplet) |
| `maker` | `string` | yes | Maker of the item concerned. | ARCH §5.3 (component triplet) |
| `sw_config_id` | `string` | yes | Software configuration identifier (modification / software load records). | ARCH §10 (linkage) |
| `order_id` | `string` | yes | Order that caused the record, if any. | ARCH §11.1 (every executed order produces normal records) |
| `evidence_record_ids` | `list<record_id not null>` | no | Telemetry or event record_ids that triggered or support the record; empty if none. | ARCH §10 (linkage: telemetry record_id) |
| `when_discovered` | `string` | yes | When-discovered code (synthetic Phalanx table). | TRANSFER: NAMP/TO 00-20 When-Discovered; ARCH AD-19 (synthetic codes) |
| `system_code` | `string` | yes | System / work-unit code (synthetic Phalanx table). | TRANSFER: WUC; ARCH AD-19 (synthetic codes) |
| `malfunction_code` | `string` | yes | How-malfunctioned code (synthetic Phalanx table). | TRANSFER: NAMP MAL / USAF HMC; ARCH AD-19 (synthetic codes) |
| `action_taken_code` | `string` | yes | Action-taken code (synthetic Phalanx table). | TRANSFER: NAMP/USAF Action Taken; ARCH AD-19 (synthetic codes) |
| `type_maint_code` | `string` | yes | Type-of-maintenance code (synthetic Phalanx table). | TRANSFER: NAMP Type Maintenance; ARCH AD-19 (synthetic codes) |
| `discrepancy_text` | `string` | yes | Discrepancy narrative (free text, may carry injected noise). | ARCH §10 (free text) |
| `corrective_action_text` | `string` | yes | Corrective-action narrative. | ARCH §10 (free text) |
| `limitations_text` | `string` | yes | Limitations or deferral conditions (technical log). | ARCH §10 (technical log: limitations, deferred defects) |
| `corrected_by` | `string` | yes | Pseudonymous identifier of the technician who did the work. | ARCH §10 (signatures) |
| `inspected_by` | `string` | yes | Pseudonymous identifier of the inspector. | ARCH §10 (signatures) |
| `man_hours` | `float64` | yes | Man-hours booked.[units `h`; range [0.0, inf]] | TRANSFER: NAMP MAN HRS |
| `priority` | `enum:SupplyPriority` | yes | Supply demand priority. | ARCH §10 (demand priority AOG/MCM/PHU) |
| `quantity` | `uint32` | yes | Quantity demanded or issued. | TRANSFER: NAMP requisition QTY |
| `install_action` | `enum:InstallAction` | yes | Install or remove (component life records). | ARCH §10 (component life record) |
| `item_hours` | `float64` | yes | Item operating hours at removal or installation.[units `h`; range [0.0, inf]] | ARCH §10 (time at removal/installation) |
| `item_cycles` | `float64` | yes | Item cycles at removal or installation.[units `count`; range [0.0, inf]] | ARCH §10 (cycles at removal/installation) |
| `donor_tail_no` | `string` | yes | Donor tail of a cannibalisation.[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §10 (cannibalisation donor) |
| `inspection_type` | `string` | yes | Inspection or servicing type (e.g. scheduled, conditional, borescope), synthetic table. | ARCH §10 (inspection / servicing) |
| `shop_finding` | `enum:ShopFinding` | yes | Shop finding on a turned-in item. | ARCH §10 (shop / depot finding) |
| `compliance_status` | `enum:ComplianceStatus` | yes | Compliance status of a modification or software load. | ARCH §10 (modification compliance status) |
| `availability_state` | `enum:AvailabilityState` | yes | Mission-capability state of the 15-minute bin starting at t_event (AVAILABILITY_STATE records). | ARCH §10 (15-min mission-capability bins) |
| `mission_type` | `string` | yes | Mission flown (SORTIE records). | ARCH §10 (sortie record: mission) |
| `crew_id` | `string` | yes | Pseudonymous crew identifier (SORTIE records). | ARCH §10 (sortie record: crew) |
| `flight_hours` | `float64` | yes | Flight hours (SORTIE records).[units `h`; range [0.0, inf]] | ARCH §10 (sortie record: hours) |
| `landings` | `uint32` | yes | Landings (SORTIE records). | ARCH §10 (sortie record: landings) |
| `engine_cycles` | `float64` | yes | Engine cycles (SORTIE records).[units `count`; range [0.0, inf]] | ARCH §10 (sortie record: cycles) |
| `engine_starts` | `uint32` | yes | Engine starts (SORTIE records). | ARCH §10 (sortie record: starts) |
| `t_event` | `time_ns (sim_utc)` | no | Instant this record version refers to (discovery, status change, bin start). The event time of the record. | ASSUMPTION: A-W0.4-13 |
| `t_open` | `time_ns (sim_utc)` | yes | When the job or record was opened. | TRANSFER: NAMP RECEIVED date-time |
| `t_close` | `time_ns (sim_utc)` | yes | When the job or record was closed. | TRANSFER: NAMP COMPLETED date-time |
| `t_ingest` | `time_ns (sim_utc)` | no | When this record version became visible in the maintenance system (includes reconciliation lag). | ARCH §10 (reconciliation lag), I5 |
| `provenance` | `enum:Provenance` | no | direct (records are produced on the ground by M18). | ARCH §12; ASSUMPTION: A-W0.4-13 |

### `orders.commands`

Inbound decisions (orders) from downstream agents or human planners. Orders are requests: M21 validates them for authority, airworthiness and resources and applies them at the next decision epoch in simulation time. Re-sending an order_id is a no-op (idempotent). An order whose evidence cites a record not yet ingested at t_issued is rejected (no look-ahead).

- **Basis:** ARCH §11.1
- **Event time:** `t_issued`; **ingest time:** `t_issued`
- **Partitioning:** `date`
- **JSON-Schema:** yes; **consumer-visible:** yes
- **record_id key:** `order_id` (str, column)
- **Row invariants:** `t_effective >= t_issued` (where both non-null); record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key = blake2b-128 of the order_id. | ARCH §12 |
| `dict_version` | `string` | yes | Dictionary version the issuer observed, if known. | ARCH §12 (dictionary on every record); ASSUMPTION: A-W0.4-14 (nullable for external issuers) |
| `dict_hash` | `string` | yes | Dictionary hash the issuer observed, if known.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12; ASSUMPTION: A-W0.4-14 |
| `order_id` | `string` | no | Globally unique order identifier chosen by the issuer.[pattern `^[A-Za-z0-9][A-Za-z0-9._:-]*$`] | ARCH §11.1 (idempotent order_id) |
| `issuer_id` | `string` | no | Issuer identity (agent or human planner). | ARCH §11.1 (issuer) |
| `issuer_kind` | `enum:IssuerKind` | no | AGENT or HUMAN. | ARCH §11.1 (issuer: agent/human) |
| `policy_version` | `string` | yes | Policy or model version of an agent issuer. | ARCH §11.1 (policy version) |
| `t_issued` | `time_ns (sim_utc)` | no | Simulation time the order was issued. The event and availability time of the record. | ARCH §11.1 |
| `t_effective` | `time_ns (sim_utc)` | no | Simulation time the order should take effect (at or after the next decision epoch; M21 enforces the epoch). | ARCH §11.1 (t_effective >= next decision epoch) |
| `target_tail_no` | `string` | yes | Target tail.[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §11.1 (target) |
| `target_base` | `string` | yes | Target base. | ARCH §11.1 (target) |
| `target_lru` | `string` | yes | Target LRU. | ARCH §11.1 (target) |
| `target_serial` | `string` | yes | Target serial number. | ARCH §11.1 (target) |
| `action` | `enum:OrderAction` | no | Requested action. | ARCH §11.1 (action vocabulary) |
| `parameters` | `json_object` | no | Action-specific parameters as a JSON object (canonical JSON text in Arrow; '{}' when none). Per-action schemas are M21's. | ARCH §11.1 (parameters); ASSUMPTION: A-W0.4-14 |
| `priority` | `enum:OrderPriority` | no | Priority. | ARCH §11.1 (priority); ASSUMPTION: A-W0.4-14 |
| `evidence` | `list<record_id not null>` | no | record_ids of the samples, events or records that justify the order; all must be ingested by t_issued. | ARCH §11.1 (evidence: record_ids) |

### `orders.status`

Order lifecycle: accepted, queued, in work, completed, rejected (with reason). One record per status change.

- **Basis:** ARCH §11.1, §12
- **Event time:** `t_status`; **ingest time:** `t_status`
- **Partitioning:** `date`
- **JSON-Schema:** yes; **consumer-visible:** yes
- **record_id key:** `order_id` (str, column), `status_seq` (u64, column)
- **Row invariants:** `reason` required when `status == REJECTED`; record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key; blake2b-128 of the topic's record_id_key components (see record_id rules). | ARCH §12 |
| `dict_version` | `string` | no | Parameter-dictionary semantic version (M01) the record was produced against. | ARCH §12 |
| `dict_hash` | `string` | no | Parameter-dictionary content hash, lower-case hex (M01). Appears on every record.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12 |
| `order_id` | `string` | no | Order this status refers to.[pattern `^[A-Za-z0-9][A-Za-z0-9._:-]*$`] | ARCH §11.1 |
| `status_seq` | `uint32` | no | Index of this status change within the order (0, 1, 2, ...). | ASSUMPTION: A-W0.4-15 |
| `status` | `enum:OrderStatus` | no | Lifecycle state. | ARCH §11.1 |
| `reason` | `string` | yes | Reason; required when status is REJECTED. | ARCH §11.1 (rejected, with reason) |
| `t_status` | `time_ns (sim_utc)` | no | Simulation time of the status change. The event and availability time of the record. | ARCH §11.1; ASSUMPTION: A-W0.4-15 |
| `result_record_ids` | `list<record_id not null>` | no | record_ids of the normal records the execution produced; empty if none. | ARCH §11.1 (every executed order produces normal records); ASSUMPTION: A-W0.4-15 |

### `labels.truth` (RESTRICTED)

RESTRICTED. Truth for validation and scoring only: truth values behind CIR samples, hidden health states per serial, the fault schedule and the data-quality defect manifest. Never part of the downstream contract view (invariant I5); consumer readers refuse this topic.

- **Basis:** ARCH §5.1, §12
- **Event time:** `t_true`; **ingest time:** `none (not streamed)`
- **Partitioning:** `date/tail_no/sortie_id`
- **JSON-Schema:** no; **consumer-visible:** no
- **record_id key:** `label_kind` (str, column), `subject_id` (str, column), `tail_no` (str, column), `sortie_id` (str, column), `serial_no` (str, column), `related_record_id` (rid, column), `t_true` (i64, column)
- **Row invariants:** `t_end >= t_true` (where both non-null); record_id unique per batch

| Field | Type | Null | Description | Basis |
|---|---|---|---|---|
| `record_id` | `record_id` | no | Idempotency key; blake2b-128 of the topic's record_id_key components (see record_id rules). | ARCH §12 |
| `dict_version` | `string` | no | Parameter-dictionary semantic version (M01) the record was produced against. | ARCH §12 |
| `dict_hash` | `string` | no | Parameter-dictionary content hash, lower-case hex (M01). Appears on every record.[pattern `^[0-9a-f]{16,128}$`] | ARCH §12 |
| `label_kind` | `enum:LabelKind` | no | Kind of label. | ARCH §12; ASSUMPTION: A-W0.4-16 |
| `subject_id` | `string` | no | param_id (TRUTH_SAMPLE), hidden-state id (HIDDEN_STATE, from not_measured_states.csv), fault id (FAULT) or defect id (DEFECT). | ASSUMPTION: A-W0.4-16 |
| `tail_no` | `string` | yes | Tail the label belongs to.[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §5.3 |
| `sortie_id` | `string` | yes | Sortie the label belongs to, if any.[pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`] | ARCH §5.3 |
| `serial_no` | `string` | yes | Serial of the component or engine the label belongs to, if any. | ARCH §5.3, §9.1 (hidden state per serial) |
| `t_true` | `time_ns (sim_utc)` | no | Physics time the label refers to (start time for faults and defects). The event time of the record. | ARCH §8 (t_true only in CIR and labels) |
| `t_end` | `time_ns (sim_utc)` | yes | End time for faults or defects with a duration. | ASSUMPTION: A-W0.4-16 |
| `value` | `float64` | yes | Truth value (TRUTH_SAMPLE, HIDDEN_STATE) or fault severity, in `units`. | ASSUMPTION: A-W0.4-16 |
| `units` | `string` | yes | Unit of value. | ASSUMPTION: A-W0.4-16 |
| `category` | `string` | yes | Fault mode, defect type or observability class. | ASSUMPTION: A-W0.4-16 |
| `related_record_id` | `record_id` | yes | Contract record this label refers to (the sample behind a TRUTH_SAMPLE, the defected record of a DEFECT). | ARCH §10 (defect manifest); ASSUMPTION: A-W0.4-16 |
| `source_module` | `string` | no | Module that produced the label (e.g. M10, M11, M13, M18). | ASSUMPTION: A-W0.4-16 |

## Derived choices for owner review

These are W0.4 decisions where no source decides. Each is registered in `docs/assumptions.md`.

| ID | Statement |
|---|---|
| A-W0.4-1 | Contract time scales: every time field except t_record is int64 ns on the simulated UTC calendar (POSIX ns since 1970-01-01Z); kernel time maps by adding the run epoch (exact integer). t_record is the recorder RTC in ns from the recording's own origin. |
| A-W0.4-2 | record_id = blake2b-128 (person 'phalanx.rid.v0') over a typed, length-prefixed encoding of the topic and its record_id_key. The sample key adds param_id (the item) to the §12 tuple, because one bus message carries several parameters. 128 bits keeps the birthday bound negligible at fleet scale (1e10 records: p ~ 1e-19). |
| A-W0.4-3 | Fast-path record_id components: channel_id = 'direct:<source_lru>:<lane or empty>', seq = CIR sample_index (per-stream acquisition tick index within the sortie), msg_index = 0. |
| A-W0.4-4 | PROXY (fast path only): t_utc = t_sample (perfect time-source lock). t_bus, t_record, raw_counts, bus, rt_sa_word and label_sdi are null; the fast path never sets bus, recorder or ground flags. Replaced by the full path (W1.7). |
| A-W0.4-5 | Fast-path t_ingest is supplied by the caller as the sortie's download instant (from the scenario or M16 download schedule); it must be >= every t_sample of the batch. No download-delay model in W0.4. |
| A-W0.4-6 | CIR values (value, truth_value) are in the dictionary engineering unit of the parameter, not SI, because the recorder lattice is defined in EU; M13 performs the SI->EU conversion at digitisation. |
| A-W0.4-7 | Nullability and formats derived where §12 is silent: engine_serial, lane, bus, rt_sa_word, label_sdi, t_bus, t_record, t_utc and raw_counts nullable; value_eu and t_sample non-null; identifier patterns for tail_no, sortie_id, source_lru (filesystem- and key-safe); rt_sa_word 'RTnn/SAnn/Wnn', label_sdi 'Looo/SDIn'. |
| A-W0.4-8 | quality_flags is a uint32 bit set with bit positions in §12 order (bit 0 SENTINEL ... bit 10 DECODER_INTERPOLATED); bits 11-31 reserved (zero); each flag has a producing-stage scope. |
| A-W0.4-9 | Enumerations are carried as UTF-8 strings validated against the spec tables (Arrow string, Avro enum, JSON-Schema enum), not as Arrow dictionary arrays, so Parquet bytes stay deterministic across batches. |
| A-W0.4-10 | Event record: S5000F Event fields (event_id, t_occurrence, event_group, severity, description, confirmed_status) + §12 (detection mechanism, PFL/MFL, latch, persistence, suspect LRUs with isolation confidence, snapshot window) + IRIG Ch10 recording-event number; severity ADVISORY/CAUTION/WARNING (MIL-STD-411C); detection_far_per_fh is the nominal (specified) rate from M01, never the simulator's true rate; topic-specific fields for BIT, exceedances and cautions. |
| A-W0.4-11 | usage.counters: one record per counter update (LUIs update twice per flight), cumulative value as reported plus optional increment; counters are dictionary params (param_id). |
| A-W0.4-12 | sortie.manifest: §12 content as typed fields; seeds and the RNG stream table are field-level restricted (dropped from the consumer view) because seeds + code commit would let a consumer regenerate truth (I5). |
| A-W0.4-13 | maint.records: one topic with a record_type discriminator and typed nullable columns (NAMP / TO 00-20 / F700 / S5000F); a new record version per status change; the five coded dimensions are synthetic IAF-relabelled code strings (AD-19). |
| A-W0.4-14 | The order record (§11.1) lives on topic orders.commands (name from report §13); action symbols are upper-snake renderings of the §11.1 vocabulary; parameters is a JSON object (canonical JSON string in Arrow); priority adds ROUTINE to AOG/MCM/PHU; dict_version/dict_hash are nullable on orders.commands. |
| A-W0.4-15 | orders.status: one record per status change with a per-order status_seq; reason required when REJECTED; result_record_ids links the normal records an executed order produced. |
| A-W0.4-16 | labels.truth: restricted topic with label_kind TRUTH_SAMPLE / HIDDEN_STATE / FAULT / DEFECT, a subject id, the truth time and value, and an optional link to the record it labels. |
| A-W0.4-17 | Storage: Parquet (zstd level 3, fixed row-group size, format 2.6, Arrow schema stored), rows sorted by (event time, record_id) before writing, Hive-style directories date=/<partition fields>=, file name from the file's content digest. The only version-dependent bytes are the pinned writer's created_by string. |
| A-W0.4-18 | Replay: delivery bursts ordered by (t_ingest, tail_no, sortie_id); within a burst, topics in rank order and rows in (event time, record_id) order; per-sortie watermark = max event time delivered so far; duplicate record_ids keep the earliest ingest; topics without an ingest time (labels.truth) are not streamed. |
| A-W0.4-19 | Every time field is non-negative (validated); writers and readers reject a file whose embedded contract hash differs from the loaded contract. |
| A-W0.4-20 | Avro mapping: int8/int16/int32/uint8/uint16 -> int; int64/uint32/flags/time -> long (time carries phalanx.time_unit=ns, since Avro 1.11 has no ns logical type); record_id -> fixed(16); enums -> Avro enum; nullable -> ["null", T] with default null. |
| A-W0.4-22 | Contract 0.2.0 (W2.2, additive): a sortie can have several on-board recordings, one per recorder sink (AD-25). param.samples carries recording_id (unique within tail_no and sortie_id, set by the recorder; key-safe pattern, no ':') and sink (the M01 sinks-table id of that recording), both null on the fast path and for a single unattributed bus-monitor capture, and both null or both set. On the full path the record_id channel_id component becomes '<recording_id>:<Ch10 channel ID>' when recording_id is set, because Ch10 channel IDs are unique only within one recording; a null recording_id keeps the bare channel ID, so every 0.1.0 record id is unchanged. New fields are appended after the 0.1.0 fields. |
