"""Build the solution-context kit ``solution_context/`` (work package SC, brief
``docs/build_briefs/SC_solution_context_kit.md``).

The kit is one folder for the team that builds the downstream solution on top of this data layer. It holds:

- ``contract/``: a byte copy of the published contract artefacts (``docs/contract/contract/<line>/``);
- ``dictionary/``: byte copies of the compiled dictionary and its generated artefacts (``docs/contract/``);
- ``reference/``: snapshots of ``docs/architecture.md``, ``docs/behavioural_targets.md``,
  ``docs/assumptions.md``, the order authority matrix and the per-action order parameter schemas;
- ``modules/``: snapshots of every ``src/phalanx/*/README.md`` (and the nested contract and decoder READMEs),
  named ``<module id>_<package>.md`` from the architecture §16 package table;
- ``examples/``: FORMAT EXAMPLES for every consumer-visible topic, produced by the real producers and written
  through the real contract writer (``phalanx.streaming.ParquetStore``) and validators;
- ``README.md``: the hand-written master README; this script refreshes only its generated blocks (between
  ``<!-- BEGIN GENERATED: name -->`` and ``<!-- END GENERATED: name -->``);
- ``MANIFEST.json``: every file with its source, sha256 and size, plus the source commit and the contract,
  dictionary and generator identities.

Determinism: the same source tree (and the same HEAD) gives byte-identical output. Nothing reads the
wall clock; JSON is written with sorted keys; Parquet bytes come from the store's fixed writer options;
the examples come from fixed literal roots and identity-keyed streams.

Never edit the copies or the generated blocks by hand: run ``make solution-context``.
``tests/unit/test_solution_context.py`` checks the kit against its sources.

Usage (from a checkout)::

    python -I tools/build_solution_context.py [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GENERATOR = "tools/build_solution_context.py"
GENERATOR_VERSION = "1.0.0"
KIT_DIR = "solution_context"
README = "README.md"
README_SOURCE = "hand-written; generated blocks refreshed by " + GENERATOR
MANIFEST = "MANIFEST.json"
MANAGED_DIRS = ("contract", "dictionary", "reference", "modules", "examples")
FORMAT_EXAMPLE = "FORMAT EXAMPLE, not physics, behaviour not validated"
LABEL_SUFFIX = ".FORMAT_EXAMPLE"
BEGIN = "<!-- BEGIN GENERATED: {} -->"
END = "<!-- END GENERATED: {} -->"
_BLOCK = re.compile(
    r"<!-- BEGIN GENERATED: (?P<name>[a-z0-9-]+) -->\n.*?<!-- END GENERATED: (?P=name) -->", re.DOTALL
)

#: the three reference documents (snapshots at the manifest commit)
REFERENCE_DOCS = (
    ("docs/architecture.md", "reference/architecture.md"),
    ("docs/behavioural_targets.md", "reference/behavioural_targets.md"),
    ("docs/assumptions.md", "reference/assumptions.md"),
    ("configs/policies/authority.yaml", "reference/order_authority.yaml"),
)
#: dictionary artefacts copied from docs/contract/ (the compiled JSON is added by version)
DICTIONARY_FILES = ("parameters.md", "icd.md", "icd.csv", "tmats.txt", "tmats_setup_record.c10")
#: file-name prefix of a module README whose package is not in the architecture §16 package table
UNMAPPED_PACKAGE = "PKG"
#: paths whose uncommitted changes would make the recorded source commit incomplete
SOURCE_PATHS = ("docs", "src", "configs", GENERATOR)


# ------------------------------------------------------------------------------------------------------------
# small helpers
# ------------------------------------------------------------------------------------------------------------
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(obj: Any) -> bytes:
    """Deterministic JSON text: sorted keys, two-space indent, UTF-8, trailing newline."""
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def cell(x: Any) -> str:
    """A Markdown table cell: no pipes or line breaks."""
    s = "" if x is None else str(x)
    return " ".join(s.replace("|", "\\|").split())


def code(x: Any) -> str:
    return f"`{cell(x)}`" if x not in (None, "") else ""


def table(header: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += [
        "| " + " | ".join(cell(c) if not str(c).startswith("`") else str(c) for c in r) + " |" for r in rows
    ]
    return "\n".join(out)


_ABBREV = ("e.g.", "i.e.", "etc.", "vs.", "cf.")


def first_sentence(s: str, min_len: int = 25) -> str:
    """The first sentence of ``s`` (abbreviations such as "e.g." do not end it); a very short first sentence
    (for example "RESTRICTED.") takes the next one too."""
    s = " ".join(s.split())
    masked = s
    for a in _ABBREV:
        masked = masked.replace(a, a.replace(".", "\0"))
    ends = [m.end(1) for m in re.finditer(r"(\.)(\s|$)", masked)]
    for e in ends:
        if e >= min_len or e == ends[-1]:
            return s[:e]
    return s


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def source_commit() -> tuple[str, list[str]]:
    """(the last commit that changed a source path, sorted source paths with uncommitted changes, untracked
    files included). Commits that touch only the kit or the tests do not change it, so regenerating a
    committed kit gives the same bytes."""
    last = git("log", "-1", "--format=%H", "--", *SOURCE_PATHS).strip()
    status = git("status", "--porcelain", "--untracked-files=all", "--", *SOURCE_PATHS)
    dirty = sorted({line[3:].strip() for line in status.splitlines() if line.strip()})
    return last, dirty


# ------------------------------------------------------------------------------------------------------------
# kit files
# ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class KitFile:
    """One file of the kit: its kit-relative path, where it comes from, what kind it is, and its bytes."""

    path: str
    source: str
    kind: str  # contract | dictionary | reference | module | example | readme
    data: bytes
    meta: Mapping[str, Any] | None = None


def contract_line() -> tuple[str, str]:
    """(spec line directory, semantic version) of the newest built-in contract (e.g. ("v0", "0.1.0"))."""
    from phalanx.dictionary.contract import available_versions

    versions = available_versions()

    def key(item: tuple[str, str]) -> tuple[int, ...]:
        return tuple(int(x) for x in item[1].split("."))

    return max(versions.items(), key=key)


def contract_files(root: Path) -> list[KitFile]:
    line, _ = contract_line()
    src = root / "docs" / "contract" / "contract" / line
    if not (src / "contract.md").is_file():
        raise SystemExit(f"{src} has no contract.md: run `make contract-docs` first")
    out = []
    for p in sorted(src.rglob("*")):
        if p.is_file():
            rel = p.relative_to(src).as_posix()
            out.append(KitFile(f"contract/{rel}", p.relative_to(root).as_posix(), "contract", p.read_bytes()))
    return out


def dictionary_identity(root: Path) -> dict[str, str]:
    line, _ = contract_line()
    binding = json.loads(
        (root / "docs/contract/contract" / line / "dictionary_binding.json").read_text("utf-8")
    )
    return {"dict_version": binding["dict_version"], "dict_hash": binding["dict_hash"]}


def dictionary_files(root: Path) -> list[KitFile]:
    ver = dictionary_identity(root)["dict_version"]
    names = (f"dictionary.{ver}.json", *DICTIONARY_FILES)
    out = []
    for name in names:
        p = root / "docs" / "contract" / name
        if not p.is_file():
            raise SystemExit(f"missing {p}: run `make contract-docs` first")
        out.append(KitFile(f"dictionary/{name}", f"docs/contract/{name}", "dictionary", p.read_bytes()))
    return out


def module_ids(architecture: str) -> dict[str, str]:
    """Package -> module id from the architecture §16 package table (``core`` is the kernel, ``KERNEL``)."""
    sec = architecture.split("## 16. Repository and package layout", 1)[1].split("\n## 17.", 1)[0]
    block = sec.split("```text", 1)[1].split("```", 1)[0]
    ids = {
        pkg: ("KERNEL" if mid == "kernel" else mid)
        for pkg, mid in re.findall(r"(\w+)/\s+(M\d{2}|kernel)\b", block)
    }
    if len(ids) < 20:
        raise SystemExit(f"architecture §16 package table not parsed ({len(ids)} packages)")
    return ids


def module_files(root: Path) -> list[KitFile]:
    ids = module_ids((root / "docs" / "architecture.md").read_text("utf-8"))
    out = []
    pkg_root = root / "src" / "phalanx"
    readmes = sorted([*pkg_root.glob("*/README.md"), *pkg_root.glob("*/*/README.md")])
    for p in readmes:
        parts = p.relative_to(pkg_root).parts[:-1]
        mid = ids.get(
            parts[0], UNMAPPED_PACKAGE
        )  # a package outside the §16 table (e.g. a W2 integration package)
        name = f"{mid}_{'.'.join(parts)}.md"
        out.append(KitFile(f"modules/{name}", p.relative_to(root).as_posix(), "module", p.read_bytes()))
    return out


def reference_files(root: Path) -> list[KitFile]:
    out = [KitFile(dst, src, "reference", (root / src).read_bytes()) for src, dst in REFERENCE_DOCS]
    from phalanx.orders.model import ACTION_SCHEMAS

    doc = {
        "description": (
            "Per-action JSON-Schema bodies of the orders.commands `parameters` object, as enforced by the "
            "M21 gateway (src/phalanx/orders/model.py ACTION_SCHEMAS; assumption A-W1.8-19). Each body is "
            "used as {'type': 'object', 'additionalProperties': false, **body}. Snapshot at the manifest "
            "commit; the contract itself leaves `parameters` open (contract field description; A-W0.4-14)."
        ),
        "source": "src/phalanx/orders/model.py ACTION_SCHEMAS",
        "actions": ACTION_SCHEMAS,
    }
    out.append(
        KitFile(
            "reference/order_parameter_schemas.json",
            "src/phalanx/orders/model.py (ACTION_SCHEMAS)",
            "reference",
            json_bytes(doc),
        )
    )
    return out


# ------------------------------------------------------------------------------------------------------------
# format examples
# ------------------------------------------------------------------------------------------------------------
NS = 10**9
HOUR = 3600 * NS
DAY = 24 * HOUR
EXAMPLE_ROOT = (
    0x5C_E7A3_0D17_2026_1010  # fixed literal 128-bit root of the example world (no seed arithmetic)
)
EXAMPLE_SCENARIO = "solution-context-example"
EXAMPLE_EPOCH = 1_791_590_400 * NS  # 2026-10-10T00:00:00Z: kernel time 0 of the example world
EXAMPLE_TAIL = "TJ101"  # synthetic tail number (configs/scenarios/tejas_two_squadrons.yaml, A-W1.1-32)
EXAMPLE_BASE = "SUL"
EXAMPLE_CREW = "PLT-sqa-01"  # the M02 pilot-id form (src/phalanx/scenario/pilots.py)
T_START = 9 * HOUR  # engine start, kernel time
T_TAKEOFF = T_START + 150 * NS
T_LANDING = T_START + 1650 * NS
T_END = T_START + 1800 * NS  # engine shut-down


@dataclass
class ExampleWorld:
    """Everything the examples share: identities, the contract and dictionary, and the produced tables."""

    contract: Any
    dictionary: Any
    sortie_id: str
    engine_serial: str
    tables: dict[str, list[tuple[str, Any]]]  # topic -> [(store name, table)]
    notes: dict[str, str]


def _flight_cir(dictionary: Any, t0: int) -> Any:
    """FORMAT EXAMPLE input for M14: 30 min of piecewise-linear CIR rows (10 Hz) for the channels M14 reads.

    Not physics: the shapes are hand-set ramps (engine start, take-off, a 10 s EGT bump, a 3 g pull, landing)
    so that the real M14 code emits every record kind once. Same construction as the M14 unit-test fixture
    (tests/unit/test_monitoring_module.py ``cir_flight``)."""
    import numpy as np
    import pyarrow as pa

    from phalanx.ground.cir import CIR_SCHEMA

    t = np.arange(0.0, 1800.0, 0.1)
    n2 = np.interp(t, [0, 60, 120, 600, 700, 1600, 1700, 1760, 1800], [0, 65, 97, 97, 75, 75, 70, 0, 0])
    chans = {
        ("ENG.N2", "V"): n2,
        ("ENG.PS3", "V"): n2 / 100 * 380,
        ("ENG.T5", None): 15 + n2 / 100 * 780 + 60.0 * (np.abs(t - 300) < 5),
        ("ENG.PLA", "V"): np.where(n2 > 96, 100.0, 40.0),
        ("LG.WOW", None): np.where((t > 150) & (t < 1650), 0.0, 1.0),
        ("FCS.VOTED.NZ", None): 1.0 + 3.0 * np.exp(-(((t - 1000) / 5.0) ** 2)),
    }
    rows: dict[str, list[Any]] = {k: [] for k in CIR_SCHEMA.names}
    ts = (
        np.rint(t * 10).astype(np.int64) * (NS // 10) + np.int64(EXAMPLE_EPOCH + t0)
    ).tolist()  # exact int ns
    for (pid, lane), v in chans.items():
        loc = dictionary.contract_location(pid + (f".{lane}" if lane else ""))
        n = t.size
        rows["param_id"] += [pid] * n
        rows["source_lru"] += [loc["source_lru"]] * n
        rows["lane"] += [lane] * n
        rows["sample_index"] += list(range(n))
        rows["t_true"] += ts
        rows["t_sample"] += ts
        rows["value"] += v.tolist()
        rows["truth_value"] += v.tolist()
        rows["validity"] += ["NORMAL"] * n
        rows["quality_flags"] += [0] * n
        rows["rng_key_path"] += [None] * n
    return pa.table(rows, schema=CIR_SCHEMA)


def _monitoring_tables(w: ExampleWorld) -> int:
    """events.bit_faults / events.exceedances / events.cautions / usage.counters from the real M14 module."""
    import numpy as np

    from phalanx.core.events import Event
    from phalanx.core.rng import KeyPath, RngService, StreamRegistry
    from phalanx.core.scheduler import System
    from phalanx.monitoring import (
        MonitoringConfig,
        MonitoringModule,
        bit_report_payload,
        cir_chunk_payload,
        contract_tables,
        load_code_table,
        load_monitoring_params,
    )

    d = w.dictionary
    params = load_monitoring_params()
    cfg = MonitoringConfig.from_dictionary(d, load_code_table(d, params), (w.engine_serial,), regime="mature")
    m14 = MonitoringModule("monitoring", params, config=cfg)
    system = System(
        [m14],
        [],
        rng=RngService(EXAMPLE_ROOT, StreamRegistry()),
        identity=KeyPath.of(scenario=EXAMPLE_SCENARIO, tail=EXAMPLE_TAIL),
    )
    pay = cir_chunk_payload(cfg, _flight_cir(d, T_START), epoch_utc_ns=EXAMPLE_EPOCH)
    events = [
        Event(T_START, "monitor.sortie_start", "monitoring", {"sortie_id": w.sortie_id}),
        Event(T_START + 1, "monitor.observe", "monitoring", pay),
        # a controller (M08/M05/M09) BIT declaration, as those modules report their own codes to M14
        Event(
            T_START + 400 * NS, "monitor.bit_report", "monitoring", bit_report_payload("ENG-001", lane="A")
        ),
        Event(T_LANDING + 50 * NS, "monitor.landing", "monitoring", {}),
        Event(
            T_END + 1,
            "monitor.sortie_end",
            "monitoring",
            {
                "flight_time_s": np.array(float((T_LANDING - T_TAKEOFF) // NS)),
                "landings": np.array(1.0),
                "ab_lights": np.array([1.0]),
                "starts": np.array([1.0]),
            },
        ),
    ]
    world = system.inject(system.start(), events)
    world, _ = system.run(world, (T_END // NS + 10) * 240)
    t_ingest = EXAMPLE_EPOCH + T_END + int(params.value("download_delay")) * NS
    tabs = contract_tables(
        m14,
        world.states["monitoring"],
        dictionary=d,
        tail_no=EXAMPLE_TAIL,
        epoch_utc_ns=EXAMPLE_EPOCH,
        t_ingest_utc_ns=t_ingest,
        sortie_id=w.sortie_id,
        contract=w.contract,
    )
    for topic, tab in tabs.items():
        w.tables.setdefault(topic, []).append(("store", tab))
    return t_ingest


def _operations_tables(w: ExampleWorld, bit_table: Any) -> dict[str, Any]:
    """maint.records / orders.commands / orders.status from the real M18 + M21 operations world (usage mode,
    ``phalanx.fork.OpsSession`` over ``OpsOnlyBuilder``), driven by the events M02 and M14 send in the
    operations protocol (README of src/phalanx/maintenance, "Event protocol")."""
    from phalanx.core.events import Event
    from phalanx.dictionary.contract.jsonschema_gen import table_to_json_docs
    from phalanx.fork.builder import OpsOnlyBuilder
    from phalanx.fork.session import OpsSession
    from phalanx.health.protocol import plain_payload
    from phalanx.maintenance.world import FleetSpec
    from phalanx.orders.model import Order
    from phalanx.scenario.config import MISSION_NAMES

    def ev(t: int, kind: str, doc: Mapping[str, Any]) -> Event:
        return Event(int(t), kind, "m18", plain_payload(doc), source="example")

    builder = OpsOnlyBuilder(
        FleetSpec((EXAMPLE_TAIL,), (EXAMPLE_BASE,), (0,)), EXAMPLE_EPOCH, scenario=EXAMPLE_SCENARIO
    )
    s = OpsSession(builder, EXAMPLE_ROOT)
    bit_doc = table_to_json_docs(w.contract, "events.bit_faults", bit_table)[0]
    done = {
        "sortie_id": w.sortie_id,
        "tail_no": EXAMPLE_TAIL,
        "t_takeoff": T_TAKEOFF,
        "t_landing": T_LANDING,
        "flight_hours": (T_LANDING - T_TAKEOFF) / HOUR,
        "landings": 1,
        "engine_cycles": 1.0,
        "engine_starts": 1,
        "chute_streamed": 0,
        "mission_type": MISSION_NAMES[1],
        "crew_id": EXAMPLE_CREW,
    }
    s.world = s.system.inject(
        s.world,
        [
            ev(T_START, "ops.launch", {"sortie_id": w.sortie_id, "tail_no": EXAMPLE_TAIL}),
            ev(T_END, "ops.sortie_done", done),
            ev(
                bit_doc["t_ingest"] - EXAMPLE_EPOCH,
                "obs.event",
                {"topic": "events.bit_faults", "row": bit_doc},
            ),
        ],
    )
    t_decision = builder.calendar.next_epoch(bit_doc["t_ingest"] - EXAMPLE_EPOCH + NS)
    s.run_until(t_decision)
    wo = [
        r
        for r in s.obs.as_of(EXAMPLE_EPOCH + s.t, "maint.records").to_pylist()
        if r["record_type"] == "DEFECT_WO"
    ]
    if not wo:
        raise SystemExit("example: M18 opened no defect work order for the BIT event")
    now = EXAMPLE_EPOCH + s.t
    accepted = Order(
        order_id="EXAMPLE:20261011:001",
        issuer_id="EXAMPLE-PLANNER",
        issuer_kind="HUMAN",
        t_issued=now,
        t_effective=now,
        action="TROUBLESHOOT",
        parameters={"code": "ENG-001"},
        target_tail_no=EXAMPLE_TAIL,
        evidence=(bytes(wo[0]["record_id"]),),
    )
    rejected = Order(
        order_id="EXAMPLE:20261011:002",
        issuer_id="EXAMPLE-AGENT",
        issuer_kind="AGENT",
        t_issued=now,
        t_effective=now,
        action="INSPECT",
        parameters={"type": "BORESCOPE"},
        target_tail_no=EXAMPLE_TAIL,
        evidence=(bytes(16),),  # a record_id that is not in the observation set: the gateway rejects it
        policy_version="example-policy-0",
    )
    results = s.submit([accepted, rejected])
    verdicts = [r.verdict for r in results]
    if verdicts != ["ACCEPTED", "REJECTED"]:
        raise SystemExit(f"example: unexpected order verdicts {verdicts}")
    s.run_until(t_decision + DAY)
    t_now = EXAMPLE_EPOCH + s.t
    for topic in ("maint.records", "orders.commands", "orders.status"):
        w.tables.setdefault(topic, []).append(("store", s.obs.as_of(t_now, topic)))
    st = s.world.states["m18"]
    return {"session": s, "state": st, "config_hash": s.system.config_hash, "t_now": t_now}


def _fast_path_samples(w: ExampleWorld, t_ingest: int) -> None:
    """param.samples on the fast path (provenance direct) from ``phalanx.ground.examples`` CIR batches."""
    import pyarrow as pa

    from phalanx.ground import CirBatch, FastPathConfig, cir_to_param_samples
    from phalanx.ground.examples import example_cir_batch

    t0 = EXAMPLE_EPOCH + T_START + 400 * NS
    # value = sample index (deterministic ramp); first indices chosen inside each channel's dictionary range
    n2 = example_cir_batch(
        EXAMPLE_TAIL,
        w.sortie_id,
        t0,
        4,
        streams=(
            ("ENG.N2", "FADEC", "A", 60, "percent"),
            ("ENG.N2", "FADEC", "B", 60, "percent"),
            ("ENG.N2", "FADEC", "V", 60, "percent"),
        ),
        first_index=90,
    )
    t5 = example_cir_batch(
        EXAMPLE_TAIL, w.sortie_id, t0, 4, streams=(("ENG.T5", "FADEC", None, 60, "degC"),), first_index=600
    )
    cir = CirBatch(EXAMPLE_TAIL, w.sortie_id, pa.concat_tables([n2.table, t5.table]))
    cfg = FastPathConfig.from_dictionary(w.dictionary, engine_serial=w.engine_serial)
    w.tables.setdefault("param.samples", []).append(
        ("store", cir_to_param_samples(cir, cfg, t_ingest=t_ingest))
    )


def _full_path_samples(w: ExampleWorld) -> None:
    """param.samples on the full path (provenance full_path): a 2 s FADEC CIR on the M13 FADEC crystal,
    through M15 (bus) -> M16 (Ch10 recording, download) -> M17 (ground decoder)."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.compute as pc

    from phalanx.bus.clocks import STREAMS as BUS_STREAMS
    from phalanx.bus.clocks import SortieIdentity, acquisition_oscillators
    from phalanx.bus.icd import BusIcd
    from phalanx.core.rng import RngService, StreamRegistry
    from phalanx.ground.cir import StreamSamples, cir_from_streams
    from phalanx.recorder.full_path import run_full_path
    from phalanx.recorder.writer import STREAMS as REC_STREAMS

    d = w.dictionary
    items = {it.channel_id: it for it in BusIcd.from_dictionary(d).items}
    oscs = acquisition_oscillators(d, EXAMPLE_EPOCH)
    dom = oscs["FADEC"].tick_domain()
    t_a = EXAMPLE_EPOCH + T_START + 400 * NS
    t_b = t_a + 2 * NS
    n0, n1 = dom.indices_in(t_a - NS, t_b)
    t = dom.sample_times_ns(n0, n1 - n0)
    idx = np.arange(n0, n1, dtype=np.int64)
    levels = {"ENG.N1.V": 82.0, "ENG.N2.V": 91.0, "ENG.T5": 620.0, "ENG.WFM": 4200.0}  # constant levels
    streams = []
    for cid, level in levels.items():
        c0, c1 = items[cid].cal
        v = np.full(t.size, c0 + c1 * np.rint((level - c0) / c1))  # on the recorder lattice
        loc = d.contract_location(cid)
        streams.append(
            StreamSamples(
                param_id=loc["param_id"],
                source_lru=loc["source_lru"],
                lane=loc["lane"],
                sample_index=idx,
                t_sample=t,
                value=v,
                truth_value=v,
                validity=np.full(t.size, "NORMAL", dtype=object),
            )
        )
    cir = cir_from_streams(w.contract, EXAMPLE_TAIL, w.sortie_id, streams)
    ident = SortieIdentity(
        scenario=EXAMPLE_SCENARIO, tail_no=EXAMPLE_TAIL, sortie_id=w.sortie_id, engine_serial=w.engine_serial
    )
    rng = RngService(EXAMPLE_ROOT, StreamRegistry([*BUS_STREAMS, *REC_STREAMS]))
    res = run_full_path(
        cir, ident=ident, rng=rng, t_start=t_a, t_end=t_b, oscillators=oscs, contract=w.contract
    )
    dec = next(x for x, dl in zip(res.decoded, res.deliveries, strict=True) if dl.complete)
    s = dec.samples
    keep: list[int] = []
    pids = s.column("param_id").to_pylist()
    order = np.argsort(s.column("t_sample").to_numpy(), kind="stable")
    wanted = {"ENG.N1": 3, "ENG.N2": 3, "ENG.T5": 3, "ENG.WFM": 3, "ENG.OIL_P": 2}
    seen: Counter[str] = Counter()
    for i in order.tolist():
        p = pids[i]
        if p in wanted and seen[p] < wanted[p]:
            seen[p] += 1
            keep.append(i)
    sub = s.take(pa.array(sorted(keep), pa.int64()))
    if not pc.all(pc.equal(sub.column("provenance"), "full_path")).as_py():
        raise SystemExit("example: full-path decode did not give provenance full_path")
    w.tables.setdefault("param.samples", []).append(("full_path", sub))
    w.notes["full_path_deliveries"] = str(len(res.deliveries))


def _sortie_manifest(w: ExampleWorld, ops: Mapping[str, Any], t_ingest: int, commit: str) -> None:
    """sortie.manifest: no module emits it yet, so the example row is assembled from the example world's own
    records and identities (see examples/README.md); the restricted fields are null."""
    import importlib.metadata as md

    import pyarrow as pa

    from phalanx.ground.rid import record_id

    c, d = w.contract, w.dictionary
    rows = ops["session"].obs.as_of(ops["t_now"], "maint.records").to_pylist()
    sortie = next(r for r in rows if r["record_type"] == "SORTIE" and r["sortie_id"] == w.sortie_id)
    installs = [r for r in rows if r["record_type"] == "COMPONENT_LIFE" and r["install_action"] == "INSTALL"]
    st, cat = ops["state"], ops["session"].builder.m18_cfg.catalogue
    ser_no = [str(x) for x in st["ser_no"].tolist()]
    ser_cls = st["ser_cls"].tolist()
    lru_serials = []
    for r in sorted(installs, key=lambda r: r["serial_no"]):
        cls = cat.classes[int(ser_cls[ser_no.index(r["serial_no"])])].code
        if cls == "ENG":
            continue
        lru_serials.append(
            {"lru": cls, "part_no": r["part_no"], "serial_no": r["serial_no"], "maker": r["maker"]}
        )
    libs = [{"name": n, "version": md.version(n)} for n in ("numba", "numpy", "pyarrow", "scipy")]
    row = {
        "record_id": record_id(c, "sortie.manifest", {"tail_no": EXAMPLE_TAIL, "sortie_id": w.sortie_id}),
        "dict_version": d.dict_version,
        "dict_hash": d.dict_hash,
        "tail_no": EXAMPLE_TAIL,
        "sortie_id": w.sortie_id,
        "base": EXAMPLE_BASE,
        "mission_type": sortie["mission_type"],
        "crew_id": sortie["crew_id"],
        "sw_config_id": sortie["sw_config_id"],
        "engine_serials": [{"position": "1", "serial": w.engine_serial}],
        "lru_serials": lru_serials,
        "t_start": EXAMPLE_EPOCH + T_START,
        "t_takeoff": EXAMPLE_EPOCH + T_TAKEOFF,
        "t_landing": EXAMPLE_EPOCH + T_LANDING,
        "t_end": EXAMPLE_EPOCH + T_END,
        "t_ingest": t_ingest,
        "contract_version": c.version,
        "config_hash": ops["config_hash"],
        "code_commit": commit,
        "library_versions": libs,
        "run_manifest_hash": None,
        "root_seed": None,
        "rng_stream_table": None,
        "provenance": "direct",
    }
    tab = pa.Table.from_pylist([row], schema=c.schemas["sortie.manifest"])
    c.validate("sortie.manifest", tab)
    w.tables.setdefault("sortie.manifest", []).append(("store", tab))


def build_examples(out: Path, contract: Any, dictionary: Any, commit: str) -> list[KitFile]:
    """Produce the examples into ``out/examples`` through the real producers and the real contract writer."""
    from phalanx.dictionary.contract.jsonschema_gen import table_to_json_docs
    from phalanx.scenario.generator import sortie_id
    from phalanx.streaming import ParquetStore

    sid = sortie_id(EXAMPLE_TAIL, (EXAMPLE_EPOCH + T_TAKEOFF) / NS)
    w = ExampleWorld(contract, dictionary, sid, "", {}, {})
    # the engine serial comes from M18's configuration control (the system of record for installed serials)
    probe = _operations_probe_engine_serial()
    w.engine_serial = probe
    t_ingest = _monitoring_tables(w)
    ops = _operations_tables(w, w.tables["events.bit_faults"][0][1])
    _fast_path_samples(w, t_ingest)
    _full_path_samples(w)
    _sortie_manifest(w, ops, t_ingest, commit)

    ex = out / "examples"
    stores = {
        "store": ParquetStore(ex / "store", contract),
        "full_path": ParquetStore(ex / "full_path", contract),
    }
    files: list[KitFile] = []
    for topic in contract.topic_names:
        if contract.topics[topic].restricted:
            continue  # labels.truth is never part of the kit
        for store_name, tab in w.tables.get(topic, []):
            for p in stores[store_name].write(topic, tab):
                labelled = p.with_name(p.name[: -len(".parquet")] + LABEL_SUFFIX + ".parquet")
                p.rename(labelled)
                rel = labelled.relative_to(out).as_posix()
                files.append(
                    KitFile(
                        rel,
                        "generated by " + GENERATOR + " (see examples/README.md)",
                        "example",
                        labelled.read_bytes(),
                        {"topic": topic, "rows": int(_parquet_rows(labelled)), "format": "parquet"},
                    )
                )
    missing = [t for t in contract.topic_names if not contract.topics[t].restricted and t not in w.tables]
    if missing:
        raise SystemExit(f"example: no producer output for {missing}")
    # JSON documents (consumer view) for the topics that define JSON-Schema
    for topic in contract.topic_names:
        spec = contract.topics[topic]
        if spec.restricted or not spec.json_schema:
            continue
        tab = stores["store"].read(topic)
        docs = table_to_json_docs(contract, topic, tab, audience="consumer")
        _validate_json_docs(contract, topic, docs)
        doc = {
            "label": FORMAT_EXAMPLE,
            "topic": topic,
            "contract_version": contract.version,
            "contract_hash": contract.hash,
            "json_schema": f"contract/jsonschema/{topic}.json",
            "records": docs,
        }
        rel = f"examples/json/{topic}{LABEL_SUFFIX}.json"
        data = json_bytes(doc)
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(data)
        files.append(
            KitFile(
                rel,
                "generated by " + GENERATOR + " (consumer view of examples/store)",
                "example",
                data,
                {"topic": topic, "rows": len(docs), "format": "json"},
            )
        )
    readme = examples_readme(contract, files, w)
    (ex / README).write_bytes(readme)
    files.append(KitFile("examples/README.md", "generated by " + GENERATOR, "example", readme))
    return sorted(files, key=lambda f: f.path)


def _operations_probe_engine_serial() -> str:
    """The engine serial M18 installs on the example tail at t = 0 (same builder and root as the example)."""
    from phalanx.fork.builder import OpsOnlyBuilder
    from phalanx.fork.session import OpsSession
    from phalanx.maintenance.world import FleetSpec

    builder = OpsOnlyBuilder(
        FleetSpec((EXAMPLE_TAIL,), (EXAMPLE_BASE,), (0,)), EXAMPLE_EPOCH, scenario=EXAMPLE_SCENARIO
    )
    s = OpsSession(builder, EXAMPLE_ROOT)
    st = s.world.states["m18"]
    pos = builder.m18_cfg.catalogue.pos("ENG").index
    return str(st["ser_no"][int(st["tail_inst"][0, pos])])


def _parquet_rows(path: Path) -> int:
    import pyarrow.parquet as pq

    return pq.ParquetFile(path).metadata.num_rows


def _validate_json_docs(contract: Any, topic: str, docs: Sequence[Mapping[str, Any]]) -> None:
    import jsonschema

    schema = contract.json_schema(topic, audience="consumer")
    v = jsonschema.Draft202012Validator(schema)
    for doc in docs:
        v.validate(doc)


def examples_readme(contract: Any, files: Sequence[KitFile], w: ExampleWorld) -> bytes:
    rows = []
    for f in files:
        if f.meta is None:
            continue
        rows.append(
            [code(f.path.removeprefix("examples/")), code(f.meta["topic"]), f.meta["rows"], f.meta["format"]]
        )
    deliveries = w.notes.get("full_path_deliveries", "?")
    production = [[a, b, c.replace("{deliveries}", deliveries)] for a, b, c in PRODUCTION_ROWS]
    text = EXAMPLES_README.format(
        label=FORMAT_EXAMPLE,
        tail=EXAMPLE_TAIL,
        sortie=w.sortie_id,
        engine=w.engine_serial,
        base=EXAMPLE_BASE,
        contract_version=contract.version,
        file_table=table(["File", "Topic", "Rows", "Format"], rows),
        production_table=table(["Topic", "Producer (real code)", "Input (FORMAT EXAMPLE)"], production),
    )
    return text.encode()


#: how each example was produced: (topics, producer, input); rendered as a table in examples/README.md
PRODUCTION_ROWS = (
    (
        "`param.samples` (`store/`)",
        "`phalanx.ground.cir_to_param_samples` (fast path, `provenance = direct`)",
        "`phalanx.ground.examples.example_cir_batch`: value = sample index (deterministic ramp); "
        "ENG.N2 lanes A/B/V and ENG.T5",
    ),
    (
        "`param.samples` (`full_path/`)",
        "`phalanx.recorder.full_path.run_full_path`: M15 bus encoder, M16 Ch10 writer and download, "
        "M17 ground decoder",
        "2 s of constant levels for ENG.N1.V, ENG.N2.V, ENG.T5 and ENG.WFM on the M13 FADEC crystal. "
        "ENG.OIL_P was not supplied, so its words decode with `validity = BUS_INVALID` (an answering RT "
        "marks items with no data invalid; M15 README). {deliveries} download(s); rows kept: the first few "
        "per parameter",
    ),
    (
        "`events.bit_faults`, `events.exceedances`, `events.cautions`, `usage.counters`",
        "`phalanx.monitoring.MonitoringModule` + `contract_tables` (M14)",
        "30 min of piecewise-linear CIR (engine start, take-off, a 10 s EGT bump over the limit, a 3 g pull, "
        "landing) and one controller BIT report (`ENG-001`, lane A)",
    ),
    (
        "`maint.records`, `orders.commands`, `orders.status`",
        "`phalanx.fork.OpsSession` over `OpsOnlyBuilder` (M18 maintenance world + M21 orders gateway); "
        "consumer view `as_of` the end of the run",
        "M02-style `ops.launch` / `ops.sortie_done` events for the sortie, the `events.bit_faults` row "
        "delivered as `obs.event` at its `t_ingest`, then two orders at the next decision epoch: one "
        "TROUBLESHOOT citing the defect work order (accepted, runs to COMPLETED), one INSPECT citing a "
        'record_id that is not in the observation set (REJECTED: "evidence not ingested by t_issued")',
    ),
    (
        "`sortie.manifest`",
        "**No module emits this topic yet.** The row is assembled by the kit builder from the example world: "
        "identities, M18's installed serials (`COMPONENT_LIFE` rows), the SORTIE record's mission, crew and "
        "software configuration, the operations System's `config_hash`, the source commit and the library "
        "versions",
        "`run_manifest_hash` is null; the restricted fields `root_seed` and `rng_stream_table` are null and "
        "are not present in the consumer files",
    ),
)

EXAMPLES_README = """# Format examples ({label})

> **{label}.** Every file in this folder is a FORMAT EXAMPLE: it shows the exact schema, types,
> nullability, identities, partitioning and file layout of the contract topics. The values are **not
> physics** and the behaviour is **not validated**: the inputs are hand-set ramps and constant levels chosen
> only so that the real producers emit each record kind. Never use these rows as simulation output or as a
> behavioural reference. `labels.truth` (restricted truth) is never part of the kit, and the restricted fields
> of `sortie.manifest` are absent (consumer view).

Generated by `tools/build_solution_context.py` (`make solution-context`); do not edit by hand. Contract
{contract_version}. Identities shared by every example: tail `{tail}` (synthetic tail number), base `{base}`,
sortie `{sortie}`, engine serial `{engine}` (the serial M18 installs at t = 0).

## Files

Parquet files are written by the real contract writer `phalanx.streaming.ParquetStore` into a **consumer
tree**, the layout a downstream team receives:
`<topic>/date=YYYY-MM-DD/<partition field>=<value>/part-<min ingest>-<digest>.parquet` (architecture AD-13,
assumption A-W0.4-17). The only change after writing is the `{suffix}` label inserted in each file name;
the bytes are the writer's. `store/` holds every consumer-visible topic; `full_path/` holds `param.samples`
decoded from a Ch10 recording (`provenance = full_path`). The JSON files hold the same records as `store/` for
the topics with a JSON-Schema (`contract/jsonschema/`), wrapped in an envelope whose `records` list validates
record by record.

{file_table}

## How each example was produced

{production_table}

Data-quality defect injection (architecture §10) is off in this example world.

## Reading a topic and checking its schema (pyarrow only)

```python
import base64, hashlib, json, pathlib
import pyarrow as pa, pyarrow.parquet as pq

kit = pathlib.Path("solution_context")
manifest = json.loads((kit / "MANIFEST.json").read_text())
topic = "param.samples"

# the consumer schema shipped with the contract (Arrow IPC, base64)
b64 = (kit / "contract" / "arrow" / f"{{topic}}.consumer.schema.b64").read_text()
expected = pa.ipc.read_schema(pa.py_buffer(base64.b64decode(b64)))

for path in sorted((kit / "examples" / "store" / topic).rglob("*.parquet")):
    t = pq.read_table(path)  # one file: no partition columns are added
    md = t.schema.metadata
    assert md[b"phalanx.topic"].decode() == topic
    assert md[b"phalanx.contract_hash"].decode() == manifest["contract"]["hash"]
    assert t.schema.equals(expected, check_metadata=True)
    # per-topic consumer schema hash, as recorded in MANIFEST.json
    assert hashlib.sha256(t.schema.serialize().to_pybytes()).hexdigest() == \\
        manifest["contract"]["consumer_schema_sha256"][topic]
    print(path.name, t.num_rows)
```

With the `phalanx` package on the path, the contract-aware reader does the same checks and de-duplicates by
`record_id`: `ParquetStore(kit / "examples" / "store", load_contract("v0")).read(topic)` (it refuses
`labels.truth` and any file written under a different contract hash).
""".replace("{suffix}", LABEL_SUFFIX)


# ------------------------------------------------------------------------------------------------------------
# README generated blocks
# ------------------------------------------------------------------------------------------------------------
def _enum_block(c: Any, name: str) -> str:
    e = c.enums[name]
    head = f"*{cell(e.description)}* (basis: {cell(e.basis)})\n\n"
    return head + table(["Value", "Meaning"], [[code(s.name), s.description] for s in e.symbols])


def _type_label(f: Any) -> str:
    t = f.type
    if t.kind == "primitive" and t.name == "time_ns":
        return f"time_ns ({f.time_scale})"
    return t.render()


def block_topics(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for t in c.topic_names:
        s = c.topics[t]
        rows.append(
            [
                code(t),
                first_sentence(s.description),
                code(s.event_time),
                code(s.ingest_time) if s.ingest_time else "none (not streamed)",
                code("/".join(("date", *s.partition_by))),
                "no (RESTRICTED)" if s.restricted else "yes",
                "Parquet, Avro" + (", JSON-Schema" if s.json_schema else ""),
            ]
        )
    return table(
        ["Topic", "Purpose", "Event time", "Ingest time", "Partitioning", "Consumer-visible", "Formats"], rows
    )


def block_record_id_keys(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for t in c.topic_names:
        s = c.topics[t]
        comps = ", ".join(f"`{k.name}` ({k.type}, {k.source})" for k in s.record_id_key)
        rows.append([code(t), comps])
    out = table(["Topic", "record_id key components (type, source)"], rows)
    notes = []
    for t in c.topic_names:
        for k in c.topics[t].record_id_key:
            if k.source == "path":
                notes.append(f"- `{t}` / `{k.name}`: {cell(k.description)}")
    return (
        out
        + "\n\nComponents with source `path` are supplied by the producing path, not stored as columns:\n\n"
        + "\n".join(notes)
    )


#: identity and linkage fields (architecture §5.3 identities, §10 linkage keys, §11.1 order target, evidence)
LINKAGE_FIELDS = (
    "record_id", "tail_no", "sortie_id", "engine_serial", "item_serial", "engine_serials", "lru_serials",
    "param_id", "source_lru", "lane", "event_id", "event_code", "limit_id", "suspect_lrus", "record_type",
    "record_key", "record_version", "job_no", "linked_job_no", "demand_no", "part_no", "serial_no", "maker",
    "donor_tail_no", "sw_config_id", "order_id", "status_seq", "target_tail_no", "target_base", "target_lru",
    "target_serial", "evidence", "evidence_record_ids", "result_record_ids", "base",
)  # fmt: skip


def block_linkage(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for t in c.topic_names:
        s = c.topics[t]
        if s.restricted:
            continue
        present = [f"`{f.name}`" for f in s.fields if f.name in LINKAGE_FIELDS and not f.restricted]
        rows.append([code(t), ", ".join(present)])
    return table(
        ["Topic", "Identity and linkage fields present (see Appendix A for types and nullability)"], rows
    )


def block_record_id_rules(c: Any, d: Mapping[str, Any]) -> str:
    r = c.record_id_rules
    rows = [
        ["Algorithm", f"{r['algorithm']}, {r['digest_bytes']} bytes, person `{r['person']}`"],
        ["Encoding", r["encoding"]],
        ["Representation", r["representation"]],
        ["Basis", r["basis"]],
    ]
    return table(["Rule", "Value"], rows)


def block_time_scales(c: Any, d: Mapping[str, Any]) -> str:
    rows = [[code(k), v] for k, v in c.time["scales"].items()]
    t = c.time
    head = (
        f"All contract times are `{t['dtype']}` `{t['unit']}` (basis: {cell(t['basis'])}; "
        f"scales: {cell(t['scale_basis'])}).\n\n"
    )
    return head + table(["Scale", "Definition"], rows)


def block_time_fields(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for t in c.topic_names:
        s = c.topics[t]
        for f in s.fields:
            if f.type.kind == "primitive" and f.type.name == "time_ns":
                role = []
                if f.name == s.event_time:
                    role.append("event time")
                if f.name == s.ingest_time:
                    role.append("ingest time")
                rows.append(
                    [
                        code(t),
                        code(f.name),
                        code(f.time_scale),
                        "yes" if f.nullable else "no",
                        ", ".join(role),
                        f.description,
                    ]
                )
    return table(["Topic", "Field", "Scale", "Nullable", "Role", "Description"], rows)


def block_policies(c: Any, d: Mapping[str, Any]) -> str:
    return table(
        ["Policy", "Contract text"],
        [["NaN", c.nan_policy], ["Restricted data", c.restriction_policy]],
    )


def block_quality_flags(c: Any, d: Mapping[str, Any]) -> str:
    fs = c.quality_flags
    head = f"*{cell(fs.description)}* (basis: {cell(fs.basis)}; carrier: uint{fs.width})\n\n"
    rows = [[f.bit, code(f"0x{1 << f.bit:08x}"), code(f.name), f.scope, f.description] for f in fs.flags]
    tail = f"\n\nReserved mask (must be zero): `0x{fs.reserved_mask:08x}`."
    return head + table(["Bit", "Mask", "Flag", "Scope (stage that may set it)", "Meaning"], rows) + tail


def block_row_invariants(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for t in c.topic_names:
        parts = []
        for ch in c.topics[t].checks:
            if ch.check == "order":
                parts.append(f"`{ch.get('left')} {ch.get('op')} {ch.get('right')}` (where both non-null)")
            else:
                parts.append(
                    f"`{ch.get('field')}` required when `{ch.get('when_field')} == {ch.get('equals')}`"
                )
        parts.append("record_id unique per batch")
        rows.append([code(t), "; ".join(parts)])
    return table(["Topic", "Row invariants (validated on every batch)"], rows)


def block_restricted(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for t in c.topic_names:
        s = c.topics[t]
        if s.restricted:
            rows.append([code(t), "whole topic", "never in the consumer view; consumer readers refuse it"])
        else:
            for f in s.fields:
                if f.restricted:
                    rows.append([code(t), code(f.name), first_sentence(f.description)])
    return table(["Topic", "Restricted part", "Note"], rows)


def _field_rows(fields: Sequence[Any], prefix: str = "") -> list[list[str]]:
    rows = []
    for f in fields:
        if f.restricted:
            continue
        extra = []
        if f.units:
            extra.append(f"units `{f.units}`")
        if f.type.kind in ("enum", "flags"):
            extra.append(f"{f.type.kind} `{f.type.name}`")
        if f.pattern:
            extra.append(f"pattern `{f.pattern}`")
        if f.minimum is not None or f.maximum is not None:
            lo = "-inf" if f.minimum is None else f.minimum
            hi = "inf" if f.maximum is None else f.maximum
            extra.append(f"range [{lo}, {hi}]")
        rows.append(
            [
                code(prefix + f.name),
                code(_type_label(f)),
                "yes" if f.nullable else "no",
                "; ".join(extra),
                first_sentence(f.description),
            ]
        )
        t = f.type
        if t.kind == "list" and t.item is not None and t.item.kind == "struct":
            rows.extend(_field_rows(t.item.fields, prefix=f"{prefix}{f.name}[]."))
        if t.kind == "struct":
            rows.extend(_field_rows(t.fields, prefix=f"{prefix}{f.name}."))
    return rows


def block_field_summary(c: Any, d: Mapping[str, Any]) -> str:
    """Consumer view of every consumer-visible topic, from the generated consumer Arrow schemas."""
    import pyarrow as pa

    parts = []
    for t in c.topic_names:
        s = c.topics[t]
        if s.restricted:
            continue
        schema = c.consumer_schema(t)
        arrow = {f.name: f for f in schema}
        rows = _field_rows(s.fields)
        for r in rows:
            name = r[0].strip("`")
            top = name.split("[]")[0].split(".")[0]
            if top in arrow and name == top:
                r.insert(2, code(str(arrow[top].type)))
            else:
                r.insert(2, "")
        parts.append(
            f"#### `{t}` ({len(schema)} consumer fields)\n\n"
            + table(
                [
                    "Field",
                    "Contract type",
                    "Arrow type",
                    "Null",
                    "Constraints",
                    "Description (first sentence)",
                ],
                rows,
            )
        )
        assert isinstance(schema, pa.Schema)
    return "\n\n".join(parts)


def block_dict_overview(c: Any, d: Mapping[str, Any]) -> str:
    st = d["stats"]
    rows = [
        ["Title", d["title"]],
        ["Platform", d["platform"]],
        ["Version / hash", f"`{d['dict_version']}` / `{d['dict_hash']}`"],
        ["Parameters (inventory rows)", st["parameters"]],
        ["Physical channels", st["channels"]],
        ["Channels recorded on a bus/recorder sink", st["recorded_channels"]],
        [
            "Channels depending on an ASSUMPTION or PROXY rule",
            st["channels_depending_on_assumption_or_proxy"],
        ],
        ["PROXY placeholder channels", ", ".join(d["proxy_items"])],
        [
            "Provenance coverage",
            f"{st['provenance_coverage_pct']} % of {st['provenance_valued_fields']} valued fields",
        ],
        ["Synthetic label", d["synthetic_label"]],
    ]
    return table(["Item", "Value"], rows)


def _counts_table(title: str, counts: Mapping[str, int]) -> str:
    rows = [[code(k), v] for k, v in sorted(counts.items())]
    rows.append(["**total**", sum(counts.values())])
    return table([title, "Channels"], rows)


def block_dict_subsystems(c: Any, d: Mapping[str, Any]) -> str:
    return _counts_table("Subsystem", d["stats"]["channels_by_subsystem"])


def block_dict_roles(c: Any, d: Mapping[str, Any]) -> str:
    return _counts_table("Role", d["stats"]["channels_by_role"])


def block_dict_transport(c: Any, d: Mapping[str, Any]) -> str:
    return _counts_table("Transport", d["stats"]["channels_by_transport"])


def block_dict_prefixes(c: Any, d: Mapping[str, Any]) -> str:
    params = d["parameters"]
    chans = d["channels"]
    by: dict[str, dict[str, Any]] = {}
    for pid, p in params.items():
        pre = pid.split(".")[0]
        e = by.setdefault(pre, {"params": 0, "channels": 0, "subsystems": set(), "example": pid})
        e["params"] += 1
        e["channels"] += len(p["channel_ids"])
        for cid in p["channel_ids"]:
            e["subsystems"].add(chans[cid]["subsystem"])
    rows = [
        [code(pre), e["params"], e["channels"], ", ".join(sorted(e["subsystems"])), code(e["example"])]
        for pre, e in sorted(by.items())
    ]
    return table(["Prefix", "Parameters", "Channels", "Subsystem(s)", "Example parameter"], rows)


def block_dict_lrus(c: Any, d: Mapping[str, Any]) -> str:
    rows = [
        [
            code(k),
            v.get("name", ""),
            v.get("role", ""),
            v.get("frame_hz", ""),
            (v.get("evidence") or {}).get("tag", ""),
        ]
        for k, v in sorted(d["lrus"].items())
    ]
    return table(["LRU", "Name", "Role", "Frame (Hz)", "Evidence tag"], rows)


def block_dict_rate_groups(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for k, v in sorted(d["rate_groups"].items()):
        rate = v.get("rate_hz", "")
        band = v.get("band_hz")
        rows.append(
            [
                code(k),
                v.get("kind", ""),
                rate,
                f"{band[0]}-{band[1]}" if band else "",
                v.get("domain", ""),
                ", ".join(v.get("stages", [])),
            ]
        )
    return table(["Rate group", "Kind", "Rate (Hz)", "Band (Hz)", "Clock domain", "Stages"], rows)


def block_dict_sinks(c: Any, d: Mapping[str, Any]) -> str:
    rows = [
        [
            code(k),
            v.get("name", ""),
            v.get("kind", ""),
            v.get("lru", ""),
            (v.get("evidence") or {}).get("tag", ""),
        ]
        for k, v in sorted(d["sinks"].items())
    ]
    return table(["Sink", "Name", "Kind", "LRU", "Evidence tag"], rows)


def block_dict_buses(c: Any, d: Mapping[str, Any]) -> str:
    b = d["buses"]
    rows = []
    for name, v in sorted(b["mil1553"].items()):
        rts = ", ".join(
            f"{k} (RT {x['address']})" for k, x in sorted(v["rts"].items(), key=lambda kv: kv[1]["address"])
        )
        rows.append(
            [
                code(name),
                "MIL-STD-1553B",
                v["bc"],
                rts or "-",
                ", ".join(v.get("monitors", [])) or "-",
                v["title"],
            ]
        )
    for name, v in sorted(b["arinc429"].items()):
        rows.append(
            [
                code(name),
                f"ARINC 429 ({v['speed']})",
                v["transmitter"],
                ", ".join(v["receivers"]),
                "-",
                v["title"],
            ]
        )
    for name, v in sorted(b["fti_pcm"].items()):
        rows.append(
            [
                code(name),
                f"PCM {v['word_bits']}-bit @ {v['minor_frame_hz']} Hz",
                v["transmitter"],
                "-",
                "-",
                v["title"],
            ]
        )
    return f"**{cell(b['label'])}**\n\n" + table(
        ["Bus / link", "Type", "Controller / transmitter", "Terminals / receivers", "Monitors", "Title"], rows
    )


def block_dict_code_tables(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for k, v in sorted(d["code_tables"].items()):
        if "codes" in v and isinstance(v["codes"], Mapping):
            n = len(v["codes"])
        elif "bits" in v:
            n = len(v["bits"])
        elif "values" in v:
            n = len(v["values"])
        elif "slots" in v:
            n = v["slots"]
        else:
            n = ""
        rows.append([code(k), v.get("title", ""), n, "yes" if v.get("synthetic") else "no"])
    return table(["Code table", "Title", "Entries", "Synthetic"], rows)


def block_dict_validity_codes(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for name in ("mil1553_validity_bit", "ssm_bnr", "ssm_dis"):
        tab = d["code_tables"].get(name)
        if tab is None:
            continue
        for k, v in sorted(tab["codes"].items(), key=lambda kv: kv[0]):
            rows.append([code(name), tab.get("title", ""), code(k), code(v)])
    return table(["Code table", "Title", "Bus value", "Contract validity"], rows)


def block_dict_keys(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for k, v in sorted(d.items()):
        if isinstance(v, Mapping):
            desc = f"object, {len(v)} entries"
        elif isinstance(v, list):
            desc = f"array, {len(v)} items"
        else:
            desc = f"`{cell(v)}`" if len(str(v)) <= 80 else f"text, {len(str(v))} characters"
        rows.append([code(k), desc])
    return table(["Top-level key", "Content"], rows)


def block_dict_channel_example(c: Any, d: Mapping[str, Any]) -> str:
    chans = d["channels"]
    cid = (
        "ENG.N2.V"
        if "ENG.N2.V" in chans
        else next(k for k, v in sorted(chans.items()) if v.get("role") == "voted")
    )
    body = json.dumps(chans[cid], indent=1, sort_keys=True, ensure_ascii=False)
    return f"```json\n{body}\n```"


def block_dict_bit_codes(c: Any, d: Mapping[str, Any]) -> str:
    bc = d["code_tables"]["bit_codes"]
    codes = bc["codes"]
    fmt = d["code_tables"]["bit_code_format"]
    by_prefix = Counter(k.split("-")[0] for k in codes)
    sev = Counter((v.get("sev"), v.get("list")) for v in codes.values())
    mech = Counter(v.get("mech") for v in codes.values())
    prefixes = fmt.get("prefixes", {})
    t1 = table(
        ["Prefix", "Meaning", "Codes"],
        [[code(p), prefixes.get(p, ""), n] for p, n in sorted(by_prefix.items())],
    )
    t2 = table(
        ["Number block", "Meaning"], [[code(k), v] for k, v in sorted(fmt.get("number_blocks", {}).items())]
    )
    t3 = table(
        ["Severity", "Fault list", "Codes"],
        [
            [code(s), code(fl) if fl else "", n]
            for (s, fl), n in sorted(sev.items(), key=lambda x: (str(x[0][0]), str(x[0][1])))
        ],
    )
    t4 = table(
        ["Detection mechanism", "Codes"],
        [[code(m), n] for m, n in sorted(mech.items(), key=lambda x: str(x[0]))],
    )
    synthetic = "yes" if bc.get("synthetic") else "no"
    head = (
        f"`{bc.get('title', 'bit_codes')}`: {len(codes)} codes, pattern `{fmt.get('pattern', '')}`, "
        f"synthetic: {synthetic}.\n\n"
    )
    return head + t1 + "\n\n" + t2 + "\n\n" + t3 + "\n\n" + t4


def block_dict_usage_counters(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for pid, p in sorted(d["parameters"].items()):
        if not pid.startswith(("LUI.", "USAGE.", "STRUCT.NZ")):
            continue
        ch0 = d["channels"][p["channel_ids"][0]]
        rows.append(
            [
                code(pid),
                ch0["name"].split(" (")[0] if ch0.get("name") else "",
                ", ".join(f"`{x}`" for x in p["channel_ids"]),
                code(ch0["units"]),
                ch0["subsystem"],
                (p.get("evidence") or {}).get("tag", ""),
            ]
        )
    return table(
        [
            "Parameter",
            "Name",
            "Channels (contract `param_id` = measurand)",
            "Units",
            "Subsystem",
            "Evidence tag",
        ],
        rows,
    )


GLOSSARY_PARAMS = (
    "ENG.N1", "ENG.N2", "ENG.T5", "ENG.WFM", "ENG.WFAB", "ENG.PLA", "ENG.PS3", "ENG.A8", "ENG.FVG", "ENG.CVG",
    "ENG.T1", "ENG.T25", "ENG.AB_LIT", "ENG.FADEC_STATUS", "FCS.VOTED.NZ", "LG.WOW", "SYS.PHASE", "USAGE.TAC",
)  # fmt: skip


def block_dict_glossary(c: Any, d: Mapping[str, Any]) -> str:
    rows = []
    for pid in GLOSSARY_PARAMS:
        p = d["parameters"].get(pid)
        if p is None:
            continue
        ch0 = d["channels"][p["channel_ids"][0]]
        rows.append(
            [
                code(pid),
                (p.get("inventory") or {}).get("fields", {}).get("name") or ch0.get("name", ""),
                code(ch0["units"]),
                ", ".join(f"`{x}`" for x in p["channel_ids"]),
            ]
        )
    return table(["Parameter", "Dictionary name", "Units", "Channels"], rows)


# ---- reference (snapshot) blocks: generated from the kit's own reference/ copies ---------------------------
def _md_section(text: str, heading: str) -> str:
    """Text from the Markdown heading line that starts with ``heading`` to the next heading of its level."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(heading))
    level = len(heading) - len(heading.lstrip("#"))
    out = []
    for ln in lines[start + 1 :]:
        if ln.startswith("#") and len(ln) - len(ln.lstrip("#")) <= level:
            break
        out.append(ln)
    return "\n".join(out)


def _md_tables(text: str) -> list[list[str]]:
    """Markdown tables (lists of lines) in ``text``."""
    tables, cur = [], []
    for ln in text.splitlines():
        if ln.startswith("|"):
            cur.append(ln)
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


def _row_cells(line: str) -> list[str]:
    """Cells of a Markdown table row. Cells are separated by `` | `` (pipe between spaces), so a pipe inside
    text such as ``|x| <= 0.1`` (no space on one side) stays in its cell."""
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") else body
    return [x.strip() for x in re.split(r" \| ", f" {body} ")]


def block_battery(kit: Path) -> str:
    arch = (kit / "reference" / "architecture.md").read_text("utf-8")
    sec = _md_section(arch, "### 14.1")
    return "\n".join(_md_tables(sec)[0])


def block_bt_bars(kit: Path) -> str:
    bt = (kit / "reference" / "behavioural_targets.md").read_text("utf-8")
    sec = _md_section(bt, "## The pass rule")
    return "\n\n".join("\n".join(t) for t in _md_tables(sec))


def block_bt_b1(kit: Path) -> str:
    bt = (kit / "reference" / "behavioural_targets.md").read_text("utf-8")
    parts = []
    for h in (
        "## Correlation (B1)",
        "## Lead–lag order (B2)",
        "## Dynamic response (B3 ii)",
        "## Physical laws (B5)",
    ):
        sec = _md_section(bt, h)
        parts.append(
            f"*{h.lstrip('# ')}* (`reference/behavioural_targets.md`)\n\n" + "\n".join(_md_tables(sec)[0])
        )
    return "\n\n".join(parts)


def block_records_table(kit: Path) -> str:
    arch = (kit / "reference" / "architecture.md").read_text("utf-8")
    sec = _md_section(arch, "## 10. Maintenance, logistics, records and availability")
    return "\n".join(_md_tables(sec)[0])


def block_decision_index(kit: Path) -> str:
    arch = (kit / "reference" / "architecture.md").read_text("utf-8")
    sec = _md_section(arch, "## 17. Architecture decision register")
    rows = []
    for ln in _md_tables(sec)[0][2:]:
        cells = _row_cells(ln)
        rows.append([cells[0], cells[1], cells[-1]])
    return table(["ID", "Decision", "Status"], rows)


ASSUMPTION_COLUMNS = 9  # ID, Statement, Tag, Source, Sweep, Affects, Exposing test, Replacement route, Status


def _assumption_rows(kit: Path) -> list[tuple[str, list[str]]]:
    """(registry section, 9 cells) per row of reference/assumptions.md. A malformed row with more cells is
    read best-effort: the extra cells are merged back into the statement."""
    text = (kit / "reference" / "assumptions.md").read_text("utf-8")
    out, section = [], ""
    for ln in text.splitlines():
        if ln.startswith("## "):
            section = ln[3:].strip()
        elif re.match(r"^\| (A|P)-W", ln):
            cells = _row_cells(ln)
            extra = len(cells) - ASSUMPTION_COLUMNS
            if extra > 0:
                cells = [cells[0], "|".join(cells[1 : 2 + extra]), *cells[2 + extra :]]
            out.append((section, cells))
    return out


def block_assumption_counts(kit: Path) -> str:
    rows: dict[str, Counter[str]] = {}
    for section, cells in _assumption_rows(kit):
        tag = "PROXY" if _is_proxy(cells) else "ASSUMPTION"
        rows.setdefault(section, Counter())[tag] += 1
    body = [[s, c["ASSUMPTION"], c["PROXY"], c["ASSUMPTION"] + c["PROXY"]] for s, c in rows.items()]
    tot = [sum(r[1] for r in body), sum(r[2] for r in body)]
    body.append(["**total**", tot[0], tot[1], sum(tot)])
    return table(["Registry section (work package)", "ASSUMPTION rows", "PROXY rows", "Rows"], body)


def _is_proxy(cells: Sequence[str]) -> bool:
    """A registry row is a PROXY item when its tag column says PROXY or its statement is marked **PROXY**."""
    return "PROXY" in cells[2] or "**PROXY" in cells[1]


def block_proxy_items(kit: Path) -> str:
    rows = []
    for _, cells in _assumption_rows(kit):
        if not _is_proxy(cells):
            continue
        stmt = re.sub(r"\*\*", "", cells[1])
        stmt = stmt if len(stmt) <= 220 else stmt[:217].rsplit(" ", 1)[0] + " ..."
        repl = cells[7] if len(cells) > 7 else ""
        repl = repl if len(repl) <= 160 else repl[:157].rsplit(" ", 1)[0] + " ..."
        rows.append([code(cells[0]), stmt, repl, cells[8] if len(cells) > 8 else ""])
    return table(
        [
            "ID",
            "Statement (abridged; full row in reference/assumptions.md)",
            "Replacement route (abridged)",
            "Status",
        ],
        rows,
    )


def block_module_map(kit: Path) -> str:
    arch = (kit / "reference" / "architecture.md").read_text("utf-8")
    ids = module_ids(arch)
    titles = {}
    for ln in _md_section(arch, "## 6. Module specifications").splitlines():
        m = re.match(r"^### (M\d{2}): (.+)$", ln)
        if m:
            titles[m.group(1)] = m.group(2)
    rows = []
    for p in sorted((kit / "modules").glob("*.md")):
        mid, pkg = p.stem.split("_", 1)
        title = titles.get(mid, "")
        if mid == "KERNEL":
            title = "kernel (no module id in architecture §16)"
        elif mid == UNMAPPED_PACKAGE:
            title = "package not in the architecture §16 table"
        rows.append([code(mid), title, code(f"phalanx.{pkg}"), code(f"modules/{p.name}")])
    assert ids
    return table(["Module", "Architecture title (§6)", "Python package", "README snapshot"], rows)


def block_order_parameters(kit: Path) -> str:
    doc = json.loads((kit / "reference" / "order_parameter_schemas.json").read_text("utf-8"))
    rows = []
    for action, body in sorted(doc["actions"].items()):
        props = body.get("properties", {})
        req = body.get("required", [])
        any_of = [" or ".join(f"`{x}`" for x in alt.get("required", [])) for alt in body.get("anyOf", [])]
        params = []
        for k, v in props.items():
            desc = ", ".join(f"{a}={json.dumps(b, sort_keys=True)}" for a, b in sorted(v.items()))
            params.append(f"`{k}` ({desc})")
        rows.append([code(action), "; ".join(params), ", ".join(f"`{x}`" for x in req), "; ".join(any_of)])
    return table(["Action", "Parameters (JSON-Schema)", "Required", "At least one of"], rows)


def block_order_authority(kit: Path) -> str:
    import yaml

    doc = yaml.safe_load((kit / "reference" / "order_authority.yaml").read_text("utf-8"))
    rows = [
        [
            "(default for every other action)",
            ", ".join(doc.get("default_issuers", [])),
            "",
            (doc.get("evidence") or {}).get("tag", ""),
        ]
    ]
    for action, v in sorted(doc.get("actions", {}).items()):
        extra = ", ".join(f"{k}={v[k]}" for k in sorted(v) if k not in ("issuers", "evidence"))
        rows.append(
            [code(action), ", ".join(v.get("issuers", [])), extra, (v.get("evidence") or {}).get("tag", "")]
        )
    return table(["Action", "Issuer kinds allowed", "Other limits", "Evidence tag"], rows)


# ---- manifest blocks ---------------------------------------------------------------------------------------
def block_kit_identity(kit: Path) -> str:
    m = json.loads((kit / MANIFEST).read_text("utf-8"))
    n_managed = sum(1 for f in m["files"] if f["path"].split("/")[0] in MANAGED_DIRS)
    c, g = m["contract"], m["generator"]
    rows = [
        [
            "Source commit (last commit that changed `docs/`, `src/`, `configs/` or the builder)",
            code(m["source"]["commit"]),
        ],
        [
            "Source paths changed since that commit",
            ", ".join(f"`{x}`" for x in m["source"]["dirty_paths"]) or "none",
        ],
        ["Contract", f"`{c['name']}` `{c['version']}` ({c['status']}), spec line `{c['spec_line']}`"],
        ["Contract hash (blake2b-256 of the canonical spec)", code(c["hash"])],
        ["Schema hash (blake2b-256 of the generated Arrow schemas)", code(c["schema_hash"])],
        ["Dictionary", f"`{m['dictionary']['platform']}` `{m['dictionary']['version']}`"],
        ["Dictionary hash (blake2b-256)", code(m["dictionary"]["hash"])],
        ["Generator", f"`{g['name']}` `{g['version']}` (sha256 `{g['sha256'][:16]}…`)"],
        ["Generated and copied files (excluding README.md and MANIFEST.json)", n_managed],
    ]
    return table(["Item", "Value"], rows)


FOLDER_NOTES = {
    "contract": "Byte copy of the published contract (`docs/contract/contract/<line>/`); equals its source.",
    "dictionary": "Byte copies of the compiled dictionary and artefacts (`docs/contract/`); equal sources.",
    "reference": "Snapshots at the manifest commit (checked by manifest hash only).",
    "modules": "Snapshots of the module READMEs at the manifest commit (checked by manifest hash only).",
    "examples": "FORMAT EXAMPLES (not physics, behaviour not validated).",
}


def block_file_index(kit: Path) -> str:
    m = json.loads((kit / MANIFEST).read_text("utf-8"))
    rows = [
        ["`README.md`", "this file (hand-written; generated blocks refreshed by the builder)", ""],
        ["`MANIFEST.json`", "file list with sources, sha256 and sizes; identities", ""],
    ]
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for f in m["files"]:
        top = f["path"].split("/")[0]
        if top in MANAGED_DIRS:
            groups.setdefault(top, []).append(f)
    for top in MANAGED_DIRS:
        fs = groups.get(top, [])
        rows.append([f"**`{top}/`**", FOLDER_NOTES[top], f"{len(fs)} files"])
        for f in fs:
            rows.append(
                [
                    code(f["path"]),
                    code(f["source"]) if not f["source"].startswith("generated") else f["source"],
                    f["size"],
                ]
            )
    return table(["Path", "Source / content", "Size (bytes)"], rows)


def block_examples_index(kit: Path) -> str:
    m = json.loads((kit / MANIFEST).read_text("utf-8"))
    rows = [[code(f["path"]), code(f["topic"]), f["rows"], f["format"]] for f in m["files"] if f.get("topic")]
    return table(["Example file", "Topic", "Rows", "Format"], rows)


BlockFn = Callable[[Any, Mapping[str, Any]], str]
CONTRACT_BLOCKS: dict[str, BlockFn] = {
    "topics": block_topics,
    "linkage": block_linkage,
    "record-id-keys": block_record_id_keys,
    "record-id-rules": block_record_id_rules,
    "time-scales": block_time_scales,
    "time-fields": block_time_fields,
    "policies": block_policies,
    "quality-flags": block_quality_flags,
    "row-invariants": block_row_invariants,
    "restricted": block_restricted,
    "field-summary": block_field_summary,
    "dict-overview": block_dict_overview,
    "dict-keys": block_dict_keys,
    "dict-channel-example": block_dict_channel_example,
    "dict-validity-codes": block_dict_validity_codes,
    "dict-subsystems": block_dict_subsystems,
    "dict-roles": block_dict_roles,
    "dict-transport": block_dict_transport,
    "dict-prefixes": block_dict_prefixes,
    "dict-lrus": block_dict_lrus,
    "dict-rate-groups": block_dict_rate_groups,
    "dict-sinks": block_dict_sinks,
    "dict-buses": block_dict_buses,
    "dict-code-tables": block_dict_code_tables,
    "dict-bit-codes": block_dict_bit_codes,
    "dict-usage-counters": block_dict_usage_counters,
    "dict-glossary": block_dict_glossary,
}
SNAPSHOT_BLOCKS: dict[str, Callable[[Path], str]] = {
    "battery": block_battery,
    "bt-bars": block_bt_bars,
    "bt-tables": block_bt_b1,
    "records-table": block_records_table,
    "decision-index": block_decision_index,
    "assumption-counts": block_assumption_counts,
    "proxy-items": block_proxy_items,
    "module-map": block_module_map,
    "order-parameters": block_order_parameters,
    "order-authority": block_order_authority,
}
MANIFEST_BLOCKS: dict[str, Callable[[Path], str]] = {
    "kit-identity": block_kit_identity,
    "file-index": block_file_index,
    "examples-index": block_examples_index,
}


def enum_block_names(contract: Any) -> list[str]:
    return [f"enum-{n.lower()}" for n in contract.enums]


def render_blocks(contract: Any, dictionary_content: Mapping[str, Any], kit: Path) -> dict[str, str]:
    """Every generated README block. Contract and dictionary blocks come from the given (current) contract and
    dictionary; snapshot blocks from the kit's own reference/ and modules/ copies; manifest blocks from the
    kit's MANIFEST.json. ``tests/unit/test_solution_context.py`` compares the README with this."""
    out = {name: fn(contract, dictionary_content) for name, fn in CONTRACT_BLOCKS.items()}
    for n in contract.enums:
        out[f"enum-{n.lower()}"] = _enum_block(contract, n)
    out.update({name: fn(kit) for name, fn in SNAPSHOT_BLOCKS.items()})
    out.update({name: fn(kit) for name, fn in MANIFEST_BLOCKS.items()})
    return out


def apply_blocks(readme: str, blocks: Mapping[str, str]) -> str:
    """Replace every generated block of ``readme``; every block must appear exactly once."""
    found = [m.group("name") for m in _BLOCK.finditer(readme)]
    dup = sorted({n for n in found if found.count(n) > 1})
    missing = sorted(set(blocks) - set(found))
    unknown = sorted(set(found) - set(blocks))
    if dup or missing or unknown:
        raise SystemExit(f"README generated blocks: duplicated={dup} missing={missing} unknown={unknown}")

    def sub(m: re.Match[str]) -> str:
        n = m.group("name")
        return f"{BEGIN.format(n)}\n{blocks[n].rstrip()}\n{END.format(n)}"

    return _BLOCK.sub(sub, readme)


def readme_blocks(readme: str) -> dict[str, str]:
    """The generated blocks of a README as written (name -> content without the markers)."""
    return {m.group("name"): m.group(0).split("\n", 1)[1].rsplit("\n", 1)[0] for m in _BLOCK.finditer(readme)}


# ------------------------------------------------------------------------------------------------------------
# build
# ------------------------------------------------------------------------------------------------------------
def consumer_schema_hashes(contract: Any) -> dict[str, str]:
    """sha256 of the Arrow IPC bytes of each consumer-visible topic's consumer schema."""
    return {
        t: sha256(contract.consumer_schema(t).serialize().to_pybytes())
        for t in contract.topic_names
        if not contract.topics[t].restricted
    }


def build(out: Path, *, source: tuple[str, list[str]] | None = None) -> dict[str, Any]:
    """Regenerate the kit in ``out`` (its hand-written README.md must exist). ``source`` overrides the
    recorded (commit, changed paths); by default they come from git (a test rebuilds at the manifest
    commit)."""
    from phalanx.dictionary import load_dictionary
    from phalanx.dictionary.contract import load_contract

    readme_path = out / README
    if not readme_path.is_file():
        raise SystemExit(f"{readme_path} (the hand-written master README) is missing")
    commit, dirty = source if source is not None else source_commit()
    line, version = contract_line()
    contract = load_contract(line)
    dictionary = load_dictionary()
    ident = dictionary_identity(ROOT)
    if (dictionary.dict_version, dictionary.dict_hash) != (ident["dict_version"], ident["dict_hash"]):
        raise SystemExit(
            "docs/contract is stale against the dictionary sources: run `make contract-docs` first"
        )

    for sub in MANAGED_DIRS:
        if (out / sub).exists():
            shutil.rmtree(out / sub)
    files = contract_files(ROOT) + dictionary_files(ROOT) + reference_files(ROOT) + module_files(ROOT)
    for f in files:
        p = out / f.path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f.data)
    files += build_examples(out, contract, dictionary, commit)
    files.sort(key=lambda f: f.path)

    gen_bytes = (ROOT / GENERATOR).read_bytes()
    dict_json = json.loads(
        (out / "dictionary" / f"dictionary.{ident['dict_version']}.json").read_text("utf-8")
    )
    manifest: dict[str, Any] = {
        "kit": KIT_DIR,
        "label": "Synthetic data; the ICD and code tables are synthetic, not the real Tejas ICD.",
        "source": {"commit": commit, "dirty_paths": dirty, "repository_paths": list(SOURCE_PATHS)},
        "generator": {"name": GENERATOR, "version": GENERATOR_VERSION, "sha256": sha256(gen_bytes)},
        "contract": {
            "name": contract.name,
            "version": contract.version,
            "status": contract.status,
            "spec_line": line,
            "hash": contract.hash,
            "schema_hash": contract.schema_hash,
            "consumer_schema_sha256": consumer_schema_hashes(contract),
        },
        "dictionary": {
            "platform": dict_json["platform"],
            "version": dict_json["dict_version"],
            "hash": dict_json["dict_hash"],
        },
        "files": [],
    }
    assert version == contract.version

    def entry(f: KitFile) -> dict[str, Any]:
        e: dict[str, Any] = {
            "path": f.path,
            "source": f.source,
            "kind": f.kind,
            "sha256": sha256(f.data),
            "size": len(f.data),
        }
        if f.meta:
            e.update(f.meta)
        return e

    # The README's manifest blocks read MANIFEST.json, and the manifest lists the README: write the manifest
    # without the README entry, render the README, then write the final manifest. The manifest blocks never
    # depend on the README entry, so the README rendered from either manifest is the same (checked).
    manifest["files"] = [entry(f) for f in files]
    (out / MANIFEST).write_bytes(json_bytes(manifest))
    readme = apply_blocks(readme_path.read_text("utf-8"), render_blocks(contract, dict_json, out)).encode()
    readme_path.write_bytes(readme)
    files.append(KitFile(README, README_SOURCE, "readme", readme))
    files.sort(key=lambda f: f.path)
    manifest["files"] = [entry(f) for f in files]
    (out / MANIFEST).write_bytes(json_bytes(manifest))
    if apply_blocks(readme.decode(), render_blocks(contract, dict_json, out)).encode() != readme:
        raise SystemExit("README generated blocks depend on the README's own manifest entry (builder defect)")
    return manifest


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--out", type=Path, default=ROOT / KIT_DIR, help="kit directory (default: solution_context)"
    )
    args = ap.parse_args(argv)
    from phalanx.core import configure_numba_cache

    configure_numba_cache()  # production entry point: before any kernel module is imported (core README)
    manifest = build(args.out.resolve())
    data = (args.out / MANIFEST).read_bytes()
    print(
        f"build_solution_context: {len(manifest['files'])} files under {args.out}; "
        f"MANIFEST.json sha256 {sha256(data)}; source commit {manifest['source']['commit']}"
        + (
            f" (changed paths: {manifest['source']['dirty_paths']})"
            if manifest["source"]["dirty_paths"]
            else ""
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
