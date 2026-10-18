"""M19 Streaming and storage (architecture §6 M19, AD-13).

v1 is file-backed and deterministic: a Parquet store partitioned by date / tail / sortie, with restricted data
physically separated into its own tree (:mod:`.parquet_store`), idempotent de-duplication on ``record_id``
(:mod:`.dedup`), a replay streamer with per-sortie watermarks plus the information-discipline view ``as_of``
(:mod:`.replay`), and a consumer-tree leak audit (:mod:`.leak_audit`). The Kafka/Avro adapter is v1.x.
"""

from .dedup import RecordIdConflict, dedup_by_record_id, record_id_words
from .leak_audit import audit_consumer_tree, restricted_names
from .parquet_store import (
    CONSUMER,
    PARQUET_WRITE_OPTIONS,
    RESTRICTED,
    ROW_GROUP_SIZE,
    ParquetStore,
    StoreError,
    canonical_order,
    parquet_bytes,
    project_consumer,
    utc_date,
)
from .replay import ObservationView, ReplayBatch, ReplayStreamer, Watermark

__all__ = [
    "CONSUMER",
    "PARQUET_WRITE_OPTIONS",
    "RESTRICTED",
    "ROW_GROUP_SIZE",
    "ObservationView",
    "ParquetStore",
    "RecordIdConflict",
    "ReplayBatch",
    "ReplayStreamer",
    "StoreError",
    "Watermark",
    "audit_consumer_tree",
    "canonical_order",
    "dedup_by_record_id",
    "parquet_bytes",
    "project_consumer",
    "record_id_words",
    "restricted_names",
    "utc_date",
]
