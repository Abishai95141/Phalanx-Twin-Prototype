"""M17 Ground decoder -> canonical contract (architecture §6 M17, §12).

W0.4 provides the CIR definition (:mod:`.cir`), the deterministic ``record_id`` (:mod:`.rid`) and the
fast path CIR -> contract (:mod:`.fast_path`). The full-path decoder (Ch10 -> contract) is W1.7 and must emit
the identical schema (AD-12).
"""

from .cir import (
    CIR_SCHEMA,
    CIR_VERSION,
    CirBatch,
    CirViolation,
    StreamSamples,
    assign_sample_index,
    cir_from_streams,
    cir_schema,
    truth_at_samples,
    validate_cir,
)
from .fast_path import FastPathConfig, cir_to_param_samples, cir_to_truth_labels, fast_path_channel_ids
from .rid import (
    RECORD_ID_TYPE,
    RID_DIGEST_SIZE,
    RID_PERSON,
    encode_key,
    from_hex,
    record_id,
    record_ids,
    to_hex,
)

__all__ = [
    "CIR_SCHEMA",
    "CIR_VERSION",
    "RECORD_ID_TYPE",
    "RID_DIGEST_SIZE",
    "RID_PERSON",
    "CirBatch",
    "CirViolation",
    "FastPathConfig",
    "StreamSamples",
    "assign_sample_index",
    "cir_from_streams",
    "cir_schema",
    "cir_to_param_samples",
    "cir_to_truth_labels",
    "encode_key",
    "fast_path_channel_ids",
    "from_hex",
    "record_id",
    "record_ids",
    "to_hex",
    "truth_at_samples",
    "validate_cir",
]
