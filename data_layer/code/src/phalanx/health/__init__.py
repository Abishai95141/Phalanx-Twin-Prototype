"""M10 Health state, usage damage and degradation (architecture §6 M10, §9).

Public API: :class:`HealthModule`, :class:`HealthConfig`, :func:`load_health_params`, :class:`SortieUsage`,
:func:`usage_from_truth`, :func:`health_labels`, the index maps in :mod:`phalanx.health.layout` and the
process families in :mod:`phalanx.health.processes`. See ``README.md``.
"""

from .labels import build_label_table, health_labels, hidden_state_catalogue
from .layout import (
    ACTUATORS,
    AIRFRAME_NAMES,
    ENGINE_DELTAS,
    BiasChannel,
    UtilityEntry,
    hidden_entries,
    hidden_index,
    sensor_bias_channels,
    utility_entries,
    utility_index,
)
from .module import UTIL_TRIGGERS, HealthConfig, HealthModule, load_health_params, merged_params, serial_value
from .usage import LuiGates, SortieUsage, tac, usage_from_truth

__all__ = [
    "ACTUATORS",
    "AIRFRAME_NAMES",
    "ENGINE_DELTAS",
    "UTIL_TRIGGERS",
    "BiasChannel",
    "HealthConfig",
    "HealthModule",
    "LuiGates",
    "SortieUsage",
    "UtilityEntry",
    "build_label_table",
    "health_labels",
    "hidden_entries",
    "hidden_index",
    "hidden_state_catalogue",
    "load_health_params",
    "merged_params",
    "sensor_bias_channels",
    "serial_value",
    "tac",
    "usage_from_truth",
    "utility_entries",
    "utility_index",
]
