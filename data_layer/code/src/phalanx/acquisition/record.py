"""M13 recording entry point: every acquired channel at its acquisition rate -> CIR (W1_interfaces §3).

``AcquisitionRecorder`` consumes contiguous blocks of M12 output frames
(``sens.s_<group>``/``sens.x_<group>``, e.g. a ``core.scheduler.Trace`` chunk) and LRU-computed values for
computed channels, runs the shared ``AcquisitionCore``, and accumulates per-stream samples. ``to_cir`` builds
a validated ``CirBatch`` (``phalanx.ground.cir.cir_from_streams``): ``param_id``/``source_lru``/``lane`` from
``Dictionary.contract_location``, ``sample_index`` = absolute acquisition index, ``t_sample`` = epoch + kernel
time, ``t_true = t_sample`` (truth interpolated at the tick, A-W0.4-21), ``value`` in dictionary EU (AD-38),
``truth_value`` restricted, acquisition-scope ``quality_flags`` and ``rng_key_path`` = the noise stream's key
path.

The state is explicit (arrays), so the recorder can be snapshotted and continued bitwise, and its output does
not depend on the block length.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from phalanx.core.module import ContractError
from phalanx.core.rng import Keys
from phalanx.core.time import truth_step_times_ns
from phalanx.ground.cir import CirBatch, StreamSamples, cir_from_streams
from phalanx.sensors.config import SensorConfig, engine_of

from . import kernel as K
from .config import AcqConfig
from .core import STREAMS, AcquisitionCore


@dataclass
class ChannelRecord:
    """Accumulated samples of one acquisition stream (lists of per-block arrays)."""

    sample_index: list[np.ndarray] = field(default_factory=list)
    t_sample: list[np.ndarray] = field(default_factory=list)
    code: list[np.ndarray] = field(default_factory=list)
    value: list[np.ndarray] = field(default_factory=list)
    truth: list[np.ndarray] = field(default_factory=list)
    flags: list[np.ndarray] = field(default_factory=list)
    validity: list[np.ndarray] = field(default_factory=list)

    def cat(self, name: str, dtype: Any) -> np.ndarray:
        parts = getattr(self, name)
        return np.concatenate(parts).astype(dtype, copy=False) if parts else np.zeros(0, dtype=dtype)


def frames_from_trace(sensors: SensorConfig, trace_ports: Mapping[str, np.ndarray], module_id: str):
    """(S, X) (L, n_m12) SI frames from recorded M12 ports ``<module_id>.s_<g>`` / ``.x_<g>``."""
    first = trace_ports[f"{module_id}.s_{next(iter(sensors.groups))}"]
    L = first.shape[0]
    S = np.empty((L, sensors.n_ch), dtype=np.float64)
    X = np.empty((L, sensors.n_ch), dtype=np.float64)
    for g, idx in sensors.groups.items():
        ii = np.asarray(idx, dtype=np.int64)
        S[:, ii] = trace_ports[f"{module_id}.s_{g}"]
        X[:, ii] = trace_ports[f"{module_id}.x_{g}"]
    return S, X


class AcquisitionRecorder:
    """Recording entry point of M13 (pure transitions over explicit state).

    Args:
        acq: acquisition configuration of the recorded channels (M12 channels and computed channels).
        keys: identity-scoped stream factory with the run's (scenario, tail, sortie) identity: the same
        identity
            as the System the in-loop module runs in, so both entry points draw the same keyed noise.
        compiled: False runs the NumPy reference kernel.
    """

    def __init__(self, acq: AcqConfig, keys: Keys, *, compiled: bool = True) -> None:
        self.acq = acq
        self.keys = keys
        missing = [d.key for d in STREAMS if d.key not in keys.service.registry]
        if missing:
            raise ContractError(
                f"declare the acquisition streams {missing} in the run's StreamRegistry before recording "
                "(phalanx.acquisition.core.STREAMS)"
            )
        self._kernel = K.acq_kernel if compiled else K.acq_kernel.py_func
        self.core = AcquisitionCore(acq, lambda comp, cid: keys.stream("acquisition", comp, sensor=cid))
        self.external = tuple(c for c, s in zip(acq.channels, acq.sensor_index, strict=True) if s < 0)

    def init_state(self) -> dict[str, np.ndarray]:
        return self.core.init_state()

    def process(
        self,
        state: Mapping[str, np.ndarray],
        k0: int,
        S_sens: np.ndarray,
        X_sens: np.ndarray,
        phase: np.ndarray,
        external: Mapping[str, tuple[np.ndarray, np.ndarray]] | None = None,
        records: dict[str, ChannelRecord] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, ChannelRecord]]:
        """Acquire truth steps ``k0 .. k0 + L - 1`` (frame ends ``t_{k+1}``).

        Args:
            S_sens, X_sens: (L, n_m12) M12 sensor outputs / truth at the frame ends (``frames_from_trace``).
            phase: (L,) flight-phase codes; external: computed channel -> (value SI (L,), truth SI (L,)).
            records: accumulator to extend (a new one if None).
        """
        acq = self.acq
        L = int(np.asarray(phase).size)
        k = np.arange(k0, k0 + L, dtype=np.int64)
        t_start = truth_step_times_ns(k)
        t_end = truth_step_times_ns(k + 1)
        S = np.zeros((L, acq.n), dtype=np.float64)
        X = np.zeros((L, acq.n), dtype=np.float64)
        external = external or {}
        missing = [c for c in self.external if c not in external]
        if missing:
            raise ContractError(f"computed channels need externally supplied values: {missing}")
        for c, (cid, si) in enumerate(zip(acq.channels, acq.sensor_index, strict=True)):
            if si >= 0:
                S[:, c] = S_sens[:, si]
                X[:, c] = X_sens[:, si]
            else:
                v, tr = external[cid]
                S[:, c] = np.asarray(v, dtype=np.float64).reshape(L)
                X[:, c] = np.asarray(tr, dtype=np.float64).reshape(L)
        new, doms = self.core.process(dict(state), S, X, t_start, t_end, phase, kernel=self._kernel)
        records = records if records is not None else {}
        for ds in doms:
            idx = ds.sample_index
            for j, c in enumerate(ds.channels):
                r = records.setdefault(acq.channels[c], ChannelRecord())
                r.sample_index.append(idx)
                r.t_sample.append(ds.times)
                r.code.append(ds.code[:, j])
                r.value.append(ds.value[:, j])
                r.truth.append(ds.truth[:, j])
                r.flags.append(ds.flags[:, j])
                r.validity.append(ds.validity[:, j])
        return new, records

    def noise_key_path(self, channel_id: str) -> str:
        return self.keys.stream("acquisition", "noise", sensor=channel_id).path.canonical()

    def to_cir(
        self,
        contract: Any,
        tail_no: str,
        sortie_id: str,
        records: Mapping[str, ChannelRecord],
        *,
        epoch_ns: int,
        channels: Sequence[str] | None = None,
    ) -> CirBatch:
        """Build and validate the CIR batch of the accumulated samples (sim UTC = epoch + kernel time)."""
        sym = np.array(K.VALIDITY_SYMBOLS, dtype=object)
        streams = []
        chans = tuple(channels if channels is not None else self.acq.channels)
        inst = [c for c in chans if engine_of(c) >= 0]
        if inst:  # U3 (W2.4a): the contract location has no engine/unit identity yet (coordinator item)
            raise ContractError(
                f"engine-instance channels {inst[:3]}... have no CIR identity per engine in contract v0; "
                "record them through the samples (proxy mode) until the contract carries a unit identity"
            )
        for cid in chans:
            r = records.get(cid)
            if r is None:
                continue
            loc = self.acq.location[self.acq.index(cid)]
            streams.append(
                StreamSamples(
                    param_id=loc["param_id"],
                    source_lru=loc["source_lru"],
                    lane=loc["lane"],
                    sample_index=r.cat("sample_index", np.int64),
                    t_sample=r.cat("t_sample", np.int64) + np.int64(epoch_ns),
                    value=r.cat("value", np.float64),
                    truth_value=r.cat("truth", np.float64),
                    validity=sym[r.cat("validity", np.int64)],
                    quality_flags=r.cat("flags", np.int64),
                    rng_key_path=self.noise_key_path(cid),
                )
            )
        return cir_from_streams(contract, tail_no, sortie_id, streams)
