"""Binding and diagnostic guards (architecture §14.1).

- G0 trivial-cue audit (binding): pipeline-only metadata at chance.
- G1 quantiser residue fidelity (diagnostic).
- Label-leak audit (binding in the fault build, W2.5): paired pipeline invariance, texture-only and
  metadata-only classifier audits (``label_leak``).
"""

from phalanx.validation.guards.g0 import PIPELINE_ONLY, GuardResult, g0_audit, metadata_features
from phalanx.validation.guards.g1 import G1_PERIOD, g1_counts, g1_distance
from phalanx.validation.guards.label_leak import (
    FEATURE_SETS,
    RecordedRun,
    label_leak_audit,
    leak_features,
    paired_invariance,
)

__all__ = [
    "FEATURE_SETS",
    "G1_PERIOD",
    "PIPELINE_ONLY",
    "GuardResult",
    "RecordedRun",
    "g0_audit",
    "g1_counts",
    "g1_distance",
    "label_leak_audit",
    "leak_features",
    "metadata_features",
    "paired_invariance",
]
