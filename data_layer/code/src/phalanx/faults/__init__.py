"""M11 Fault injection and propagation graph (architecture §6 M11, AD-18, AD-27).

Public API: :class:`FaultInjector`, :class:`FaultConfig`, :func:`load_fault_params`, :func:`load_catalogue`,
:func:`load_graph`, :func:`fault_labels`, the M11 -> M12 sensor-fault payload (:func:`sensor_fault_payload`,
AD-42) and the label-leak feature front end (:func:`leak_features`). See ``README.md``.
"""

from .catalogue import FaultMode, load_catalogue
from .graph import Activation, FaultGraph, GraphError, load_graph
from .labels import fault_labels
from .leak import leak_features
from .module import FaultConfig, FaultInjector, load_fault_params
from .sensor_faults import SENSOR_FAULT_EVENT, SENSOR_FAULT_KEYS, SENSOR_FAULT_MODES, sensor_fault_payload

__all__ = [
    "SENSOR_FAULT_EVENT",
    "SENSOR_FAULT_KEYS",
    "SENSOR_FAULT_MODES",
    "Activation",
    "FaultConfig",
    "FaultGraph",
    "FaultInjector",
    "FaultMode",
    "GraphError",
    "fault_labels",
    "leak_features",
    "load_catalogue",
    "load_fault_params",
    "load_graph",
    "sensor_fault_payload",
]
