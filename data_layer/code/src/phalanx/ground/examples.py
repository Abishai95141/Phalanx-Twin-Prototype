"""EXAMPLE CIR batches for interface tests and documentation.

EXAMPLE DATA, not physics: values are deterministic ramps, not the output of M12/M13. They exercise the CIR ->
contract -> storage -> replay path (schema, identity, ordering, idempotency, information discipline), nothing
about realism. Never use them as simulation output.
"""

from __future__ import annotations

from collections.abc import Sequence

import pyarrow as pa

from phalanx.core.rng import KeyPath

from .cir import CIR_SCHEMA, CirBatch, key_path_text

#: (param_id, source_lru, lane, rate_hz, units). Lane A/B shows redundancy; lane None shows a simplex source.
EXAMPLE_STREAMS: tuple[tuple[str, str, str | None, int, str], ...] = (
    ("ENG.N2", "FADEC", "A", 50, "%"),
    ("ENG.N2", "FADEC", "B", 50, "%"),
    ("ENG.EGT", "ECMS", None, 10, "degC"),
)


def example_cir_batch(
    tail_no: str,
    sortie_id: str,
    epoch_ns: int,
    n_per_stream: int,
    *,
    streams: Sequence[tuple[str, str, str | None, int, str]] = EXAMPLE_STREAMS,
    first_index: int = 0,
) -> CirBatch:
    """A deterministic EXAMPLE CIR batch: ``n_per_stream`` samples per stream, starting at ``first_index``.

    Sample k of a stream at rate f is acquired at ``epoch_ns + (k*10**9)//f + phase`` (integer ns, AD-35),
    with a small per-stream phase so streams are not simultaneous; ``t_true`` is 1 ms earlier; value = k (EU),
    truth = k + 0.25.
    """
    rows = []
    for s, (param, lru, lane, rate, _units) in enumerate(streams):
        phase = 1_000_000 * (s + 1)
        for k in range(first_index, first_index + n_per_stream):
            t_sample = epoch_ns + (k * 10**9) // rate + phase
            rows.append(
                {
                    "param_id": param,
                    "source_lru": lru,
                    "lane": lane,
                    "sample_index": k,
                    "t_true": t_sample - 1_000_000,
                    "t_sample": t_sample,
                    "value": float(k),
                    "truth_value": float(k) + 0.25,
                    "validity": "NORMAL",
                    "quality_flags": 0,
                    "rng_key_path": key_path_text(
                        KeyPath.of(
                            scenario="example",
                            tail=tail_no,
                            sortie=sortie_id,
                            subsystem="acquisition",
                            sensor=f"{lru}.{param}" + (f".{lane}" if lane else ""),
                            component="noise",
                        )
                    ),
                }
            )
    return CirBatch(tail_no, sortie_id, pa.Table.from_pylist(rows, schema=CIR_SCHEMA))


def example_units(
    streams: Sequence[tuple[str, str, str | None, int, str]] = EXAMPLE_STREAMS,
) -> dict[str, str]:
    return {p: u for p, _, _, _, u in streams}
