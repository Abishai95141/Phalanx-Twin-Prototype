"""M18 Maintenance, logistics and records simulator (architecture §6 M18, §10).

Public API (see README.md):

- :class:`~phalanx.maintenance.world.MaintenanceWorld` - the event-only M18 module; :class:`FleetSpec`,
  :class:`OpsTargets`, :class:`InternalPolicy`;
- :func:`~phalanx.maintenance.config.load_m18_config` - typed parameters (M18.yaml, catalogue, code tables);
- :mod:`~phalanx.maintenance.scir` - SCIR states, binning reference and KPI arithmetic;
- :class:`~phalanx.maintenance.defects.DefectInjector` - post-truth data-quality defects with a manifest;
- :func:`~phalanx.maintenance.rules.cann_plan` - the status-quo maintenance-control rule (shared with M21
  policies).
"""

from .catalogue import Catalogue, CodeTables, ItemClass, load_catalogue, load_codes
from .config import DefectRates, M18Config, load_m18_config
from .defects import DefectInjector
from .rules import AwpJob, FleetView, TailView, cann_plan
from .world import FleetSpec, InternalPolicy, MaintenanceWorld, OpsTargets

__all__ = [
    "AwpJob",
    "Catalogue",
    "CodeTables",
    "DefectInjector",
    "DefectRates",
    "FleetSpec",
    "FleetView",
    "InternalPolicy",
    "ItemClass",
    "M18Config",
    "MaintenanceWorld",
    "OpsTargets",
    "TailView",
    "cann_plan",
    "load_catalogue",
    "load_codes",
    "load_m18_config",
]
