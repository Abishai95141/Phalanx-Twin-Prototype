"""Kernel: 240 Hz scheduler, rate groups, event queue, module base, ports/units,
RNG key paths, state and snapshot I/O (architecture §5.5, §8, §15).

Public API for Wave-1 modules (see ``core/README.md``). Submodules:
``time`` (AD-35 time base, rate groups, clock domains), ``rng`` (identity-keyed streams),
``state`` (typed state trees and their canonical encoding), ``module`` (ports, params, Module contract),
``units`` (SI checks), ``events`` (event queue), ``scheduler`` (System, World, run), ``snapshot``,
``manifest``, ``sampling`` (clock-domain sample buffers), ``layout`` (AD-22 flat vectors);
``example_kernel`` is the AD-22 worked example (imports numba; not imported here) and ``toy`` is a kernel
test fixture, not a physics deliverable.
"""

from .events import Event, EventQueue
from .layout import ParamLayout, StateLayout
from .module import (
    ContractError,
    EvidenceTag,
    Inputs,
    Module,
    ModuleBase,
    Outputs,
    Param,
    ParamSet,
    Port,
)
from .numba_cache import configure_numba_cache, numba_cache_dir, numba_cache_status, source_digest
from .rng import (
    DrawLedger,
    KeyPath,
    Keys,
    RngService,
    Stream,
    StreamDecl,
    StreamRegistry,
    Variate,
    crn_audit,
)
from .sampling import StepSamples, max_samples_per_step, sample_ports, samples_for_steps
from .scheduler import Connection, FusedGroup, System, Trace, World
from .snapshot import read_snapshot, restore, snapshot, snapshot_id
from .state import Field, State, StateSchema
from .time import (
    NS_PER_S,
    TRUTH_DT_S,
    TRUTH_HZ,
    ClockDomain,
    RateGroup,
    latest_truth_step,
    truth_interp,
    truth_step_time_ns,
    truth_step_times_ns,
)
from .units import UnitError, UnitMismatchError

__all__ = [
    "NS_PER_S",
    "TRUTH_DT_S",
    "TRUTH_HZ",
    "ClockDomain",
    "Connection",
    "ContractError",
    "DrawLedger",
    "Event",
    "EventQueue",
    "EvidenceTag",
    "Field",
    "FusedGroup",
    "Inputs",
    "KeyPath",
    "Keys",
    "Module",
    "ModuleBase",
    "Outputs",
    "Param",
    "ParamLayout",
    "ParamSet",
    "Port",
    "RateGroup",
    "RngService",
    "State",
    "StateLayout",
    "StateSchema",
    "StepSamples",
    "Stream",
    "StreamDecl",
    "StreamRegistry",
    "System",
    "Trace",
    "UnitError",
    "UnitMismatchError",
    "Variate",
    "World",
    "configure_numba_cache",
    "crn_audit",
    "latest_truth_step",
    "max_samples_per_step",
    "numba_cache_dir",
    "numba_cache_status",
    "read_snapshot",
    "restore",
    "sample_ports",
    "samples_for_steps",
    "snapshot",
    "snapshot_id",
    "source_digest",
    "truth_interp",
    "truth_step_time_ns",
    "truth_step_times_ns",
]
