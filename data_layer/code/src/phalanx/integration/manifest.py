"""``sortie.manifest``: one contract record per telemetry sortie (contract v0; architecture §12, §15).

The manifest is produced on the ground, so its provenance is ``direct`` (fast-path runs, CIR -> contract);
``full_path`` when the sortie's data were decoded from its recording. It is built against the generated Arrow
schema and checked with the contract's own validator (``Contract.validate``, producer audience: the restricted
``root_seed`` and ``rng_stream_table`` are present; the consumer view drops them).

Contents and sources:
- linkage keys ``tail_no`` / ``sortie_id``: the telemetry window's (the same values the recorder writes into
  the CIR, hence into ``param.samples`` and M14's ``events.*``); ``record_id`` from (tail_no, sortie_id);
- ``engine_serials`` from the plan (position "1" ... in engine order); ``mission_type`` the M02 mission name;
  ``crew_id`` the plan's pseudonymous pilot id (M02 ``ops.sortie_done`` convention, no traits); ``base`` the
  squadron base name when the caller knows it;
- ``t_start`` = the window start (recorder start at post-start idle, AD-46), ``t_takeoff`` / ``t_landing`` =
  the realised first lift-off and last touchdown (main-gear WoW from truth; null when none), ``t_end`` = the
  recorder stop (the runner's current step), all simulated UTC;
- ``config_hash`` = ``System.config_hash`` (AD-48.8: it covers the serials and the per-tail configuration);
  ``code_commit``, ``library_versions`` and ``run_manifest_hash`` from the run manifest
  (``phalanx.core.manifest``), whose hash also covers the Numba cache key and source digest (the contract has
  no field of its own for them; adding one is a contract change);
- ``root_seed`` (RESTRICTED) the run's 128-bit root; ``rng_stream_table`` (RESTRICTED) every key path the
  sortie's RNG service opened, sorted, with ``stream_ref`` = blake2b-128 of the canonical key path;
- ``sw_config_id``: **ASSUMPTION A-W2.1-7**, the M18 fleet's initial software configuration ("SW-BASE",
  ``maintenance.world.FleetSpec``) until M18 drives the runner in operations mode; ``lru_serials``: empty
  (**PROXY A-W2.1-7**: telemetry mode has no installed-LRU configuration feed; M18 owns the component
  triplets).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from phalanx.core.canonical import PERSON_RNG_KEY, digest
from phalanx.core.time import truth_step_time_ns

if TYPE_CHECKING:
    from phalanx.core.manifest import RunManifest

    from .sortie import SortieRunner, SortieState

TOPIC = "sortie.manifest"
#: M18 FleetSpec initial software configuration (ASSUMPTION A-W2.1-7)
DEFAULT_SW_CONFIG = "SW-BASE"
PROVENANCES = ("direct", "full_path")
REPO = Path(__file__).resolve().parents[3]


def build_run_manifest(
    runner: SortieRunner,
    st: SortieState,
    *,
    git_commit: str | None = None,
    git_dirty: bool | None = None,
    repo: str | Path | None = None,
) -> RunManifest:
    """The run manifest of the runner's System at ``st`` (order log so far; Numba cache key included)."""
    from phalanx.core.manifest import build_manifest

    ss = runner.ss
    compiled = bool(getattr(ss.spec, "compiled", True))
    return build_manifest(
        ss.system,
        git_commit=git_commit,
        git_dirty=git_dirty,
        repo=None if git_commit is not None else (repo or REPO),
        backend="numba" if compiled else "numpy-reference",
        order_log_hash=ss.system.order_log_hash(st.world),
        extra={"sortie_id": ss.window.sortie_id, "fused": bool(ss.spec.fused)},
    )


def stream_table(runner: SortieRunner) -> list[dict[str, str]]:
    """Every key path the sortie's RNG service has opened, canonical and sorted, with its stream reference.

    Reads the service's memo of opened streams (``RngService._streams``: a pure cache keyed by key path); a
    public accessor in ``phalanx.core.rng`` is proposed to the coordinator."""
    paths = sorted(p.canonical() for p in getattr(runner.ss.system.rng, "_streams", {}))
    return [{"key_path": p, "stream_ref": digest(p.encode(), PERSON_RNG_KEY, size=16)} for p in paths]


def sortie_manifest(
    runner: SortieRunner,
    st: SortieState,
    *,
    t_ingest: int | None = None,
    provenance: str = "direct",
    run_manifest: RunManifest | None = None,
    sw_config_id: str = DEFAULT_SW_CONFIG,
    base: str | None = None,
    lru_serials: Sequence[dict[str, Any]] = (),
    contract=None,
) -> pa.Table:
    """The validated one-row ``sortie.manifest`` table of the runner's sortie at ``st`` (module docstring).

    Args:
        t_ingest: when the manifest reached the ground (sim UTC ns); default: the recorder stop ``t_end``.
        provenance: ``direct`` (fast path, ground producer) or ``full_path`` (decoded from the recording).
        run_manifest: the run's manifest; default: built for this System (``git rev-parse`` on the repo).
    """
    from phalanx.dictionary.contract import load_contract
    from phalanx.ground.rid import record_ids
    from phalanx.scenario.config import MISSION_NAMES

    if provenance not in PROVENANCES:
        raise ValueError(f"provenance must be one of {PROVENANCES}")
    c = contract or load_contract("v0")
    ss = runner.ss
    plan = ss.window
    d = ss.dictionary
    rm = run_manifest or build_run_manifest(runner, st, git_commit=runner.git_commit)
    epoch = int(ss.epoch_utc_ns)

    def utc(k: int) -> int:
        return epoch + int(truth_step_time_ns(int(k)))

    k_to, k_ld = int(st.usage["k_takeoff"][0]), int(st.usage["k_landing"][0])
    t_start, t_end = utc(0), utc(st.world.k)
    t_ing = t_end if t_ingest is None else int(t_ingest)
    row = {
        "record_id": None,
        "dict_version": d.dict_version,
        "dict_hash": d.dict_hash,
        "tail_no": plan.tail,
        "sortie_id": plan.sortie_id,
        "base": base,
        "mission_type": MISSION_NAMES.get(int(plan.mission_type), "GROUND_RUN"),
        "crew_id": plan.pilot_id or None,
        "sw_config_id": sw_config_id,
        "engine_serials": [{"position": str(i + 1), "serial": s} for i, s in enumerate(plan.engine_serials)],
        "lru_serials": [dict(x) for x in lru_serials],
        "t_start": t_start,
        "t_takeoff": utc(k_to) if k_to >= 0 else None,
        "t_landing": utc(k_ld) if k_ld >= 0 and k_ld > k_to >= 0 else None,
        "t_end": t_end,
        "t_ingest": t_ing,
        "contract_version": c.version,
        "config_hash": ss.system.config_hash,
        "code_commit": rm.git_commit,
        "library_versions": [{"name": n, "version": v} for n, v in sorted(rm.library_versions.items())],
        "run_manifest_hash": rm.hash,
        "root_seed": ss.system.rng.root_hex,
        "rng_stream_table": stream_table(runner),
        "provenance": provenance,
    }
    schema = c.schemas[TOPIC]
    rid = record_ids(c, TOPIC, {"tail_no": plan.tail, "sortie_id": plan.sortie_id}, 1)
    cols = []
    for f in schema:
        if f.name == "record_id":
            cols.append(rid)
        else:
            cols.append(pa.array([row[f.name]], type=f.type))
    out = pa.Table.from_arrays(cols, schema=schema)
    c.validate(TOPIC, out)
    return out


__all__ = [
    "DEFAULT_SW_CONFIG",
    "PROVENANCES",
    "TOPIC",
    "build_run_manifest",
    "sortie_manifest",
    "stream_table",
]
