"""M14 Monitoring and BIT (architecture §6 M14, §9.4).

Public API: :class:`MonitoringModule`, :class:`MonitoringConfig`, :func:`load_monitoring_params`,
:func:`load_code_table`, :func:`contract_tables`, the payload builders of :mod:`phalanx.monitoring.io`,
the decision kernels of :mod:`phalanx.monitoring.logic` and the CWS words (:mod:`phalanx.monitoring.cws`,
published as held outputs listed in ``phalanx.monitoring.ports.RECORDED``). See ``README.md``.
"""

from .codes import Code, CodeTable, Monitor, load_code_table
from .contract_out import contract_tables
from .cws import CWS_PORTS, CwsMap, build_cws_map
from .io import bit_report_payload, cir_chunk_payload, lru_condition_payload, sortie_end_payload
from .logic import bit_test_kernel, limit_kernel
from .module import COUNTERS, MonitoringConfig, MonitoringModule, cws_words_at


def load_monitoring_params(**kw):
    """The merged ParamSet of ``configs/tejas/params/M14.yaml``."""
    from phalanx.dictionary.params import load_params
    from phalanx.health.module import merged_params

    return merged_params(load_params("M14", **kw), "tejas.M14")


__all__ = [
    "COUNTERS",
    "CWS_PORTS",
    "Code",
    "CodeTable",
    "CwsMap",
    "Monitor",
    "MonitoringConfig",
    "MonitoringModule",
    "bit_report_payload",
    "bit_test_kernel",
    "build_cws_map",
    "cir_chunk_payload",
    "contract_tables",
    "cws_words_at",
    "limit_kernel",
    "load_code_table",
    "load_monitoring_params",
    "lru_condition_payload",
    "sortie_end_payload",
]
