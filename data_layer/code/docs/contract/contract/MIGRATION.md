# Ground-decoder contract: migration notes

Every contract change needs a semver bump, a migration note and a decision-register entry (AD-41, architecture
§12, RULES.md rule 6). Frozen versions stay loadable by their exact version (`load_contract("0.1.0")`); the
spec line `v0` is the current minor version of major 0.

## 0.1.0 → 0.2.0 (W2.2, additive; frozen by the owner, AD-56)

**Why.** AD-25 keeps the on-board sinks separate (crash recorder, ECMS/HUMS log, OAC maintenance log, FTI):
one sortie has several recordings. AD-45 noted that per-sink recordings need a recording/sink identity in the
contract; until then the full path writes one bus-monitor capture per sortie (PROXY A-W1.7-11). Two facts force
the field: `t_record` is relative to each recording's own RTC origin, and a Ch10 channel ID is unique only
within one recording.

**What changed** (assumption A-W0.4-22):

| Topic | Change |
|---|---|
| `param.samples` | Two nullable string fields appended after `provenance`: `recording_id` (pattern `^[A-Za-z0-9][A-Za-z0-9._-]*$`, unique within `tail_no` + `sortie_id`) and `sink` (pattern `^[A-Z][A-Z0-9_]*$`, an M01 sinks-table id: CDR, ECMS_HUMS, MPDRU, FTI). Both null on the fast path and for a single unattributed bus-monitor capture; both null or both set. |
| `param.samples` record_id | Full path only: the `channel_id` component is `<recording_id>:<Ch10 channel ID>` when `recording_id` is set. With a null `recording_id` it is the bare channel ID, exactly as in 0.1.0. |
| everything else | Unchanged: no field removed, renamed, retyped or reordered; enums, flags, time fields, partitioning and record-id components identical (checked by `phalanx.ground.migrate.additive_changes`). |

**What a 0.1.0 consumer sees.**
- Readers that select columns by name are unaffected. Positional readers see two extra trailing columns.
- Every record that 0.1.0 could produce keeps its `record_id` and values: the fast path and the single-capture
  full path give byte-identical 0.1.0 columns (`tests/unit/test_w22_contract_020.py`,
  `tests/integration/test_w22_datapath_migrations.py`).
- Parquet files embed the exact contract hash (A-W0.4-19), so a 0.1.0 `ParquetStore` refuses 0.2.0 files.
  Bridge explicitly:

```python
from phalanx.dictionary.contract import load_contract
from phalanx.ground.migrate import project, upgrade

c010, c020 = load_contract("0.1.0"), load_contract("0.2.0")
old_view = project(table_020, c020, c010, "param.samples")  # drop the added fields, validated under 0.1.0
new_view = upgrade(table_010, c010, c020, "param.samples")  # added fields null, validated under 0.2.0
```

**What a producer must do.** Fill `recording_id` and `sink` when a record comes from an identified on-board
recording (`run_full_path(..., recording_id=..., sink=...)`, `decode_recording(..., recording_id=..., sink=...)`);
leave both null otherwise. Use `phalanx.ground.rid.full_path_channel_id` for the record-id channel component.

**Still open** (not part of the contract change): per-sink setup records from M01 (channel subsets, record rate
groups, recorder ids per sink) and the M16 per-sink writer that replaces the single bus-monitor capture
(PROXY A-W1.7-11 stays on the producer side until then); the same recording identity on `events.*` when events
take the full path (W2.2 phase B).
