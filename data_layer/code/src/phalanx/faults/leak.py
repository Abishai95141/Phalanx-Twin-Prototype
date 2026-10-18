"""Label-leak audit, M11 side (binding guard, I6; W2.5).

The feature front end and the audit live in :mod:`phalanx.validation.guards.label_leak` (``leak_features``,
``paired_invariance``, ``label_leak_audit``); this module re-exports the front end for M11 users and says
which catalogue modes are *texture-visible by nature* (AD-48.7): a sensor fault whose physical effect is a
texture change (stuck value, intermittent dropout, spikes, open/short circuit, slow response) is excluded from
the texture-only audit and judged by the metadata-only audit, G0 and the paired invariance instead. Bias and
drift are level faults and stay in the texture-only audit.
"""

from __future__ import annotations

from collections.abc import Mapping

from phalanx.validation.guards.label_leak import FEATURE_SETS, RecordedRun, leak_features

from .catalogue import FaultMode

__all__ = ["FEATURE_SETS", "TEXTURE_SENSOR_MODES", "RecordedRun", "leak_features", "texture_visible"]

#: AD-48.7: sensor-fault modes whose physical effect is texture
TEXTURE_SENSOR_MODES = frozenset(
    {"stuck", "intermittent", "spikes", "open", "short", "probe_open", "probe_short", "slow"}
)


def texture_visible(mode: FaultMode, scripted: Mapping[str, object] | None = None) -> bool:
    """True when ``mode`` (as injected; ``scripted`` gives a generic sensor fault's ``sensor_mode``) has a
    sensor effect whose physical effect is texture (AD-48.7)."""
    for e in mode.effects:
        if e.target != "sensors":
            continue
        m = str(e.fields.get("mode", ""))
        if m == "*":
            m = str((scripted or {}).get("sensor_mode", "bias"))
        if m in TEXTURE_SENSOR_MODES:
            return True
    return False
