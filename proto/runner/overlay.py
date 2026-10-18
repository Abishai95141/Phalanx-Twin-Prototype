"""Fleet side: generated engine trend (overlay v0.1) — DEVELOPMENT.md §2.3 "Generated data".

The preview has no engine sensor data for the fleet worlds (6 telemetry sorties, 5 ending in ``ground_impact``;
no ``param.samples`` in fleet worlds). This overlay generates, per sortie of a run's live (or training) world,
an engine-condition-monitoring style **takeoff** and **cruise** snapshot for the engine fitted to that tail:

    ENG.T5 (EGT, degC) · ENG.N2 (core speed, %) · ENG.WFM (main fuel flow, lb/hr) · ENG.T1 (inlet temp, degC)

as contract 0.2.0 ``param.samples`` rows built with the data layer's own ``rows_to_table`` (exact schema and
contract hash), fast-path form (``provenance = direct``; ``recording_id`` and ``sink`` null).

What drives the numbers (all synthetic, NOT validated physics, NOT Tejas / IAF / F404 data):

- true EGT margin per engine serial (keyed by ``tail_no`` + ``engine_serial``; health follows the serial):
  initial margin, permanent loss per engine flight hour (EFH), recoverable fouling loss per EFH that an engine
  **wash** (the fleet's own ``INSPECTION`` / ``WASH`` records, CLOSED) removes, flight-to-flight scatter;
- corrected EGT = 830 °C redline (dictionary ``ENG.T5`` steady max) − margin; raw EGT = corrected × θ^0.5,
  θ = (T1 + 273.15) / 288.15, with ambient from a seasonal + diurnal model of the base;
- sample noise, quantisation to each channel's recorder LSB, range clipping;
- defects at the preview's measured rates (v0.9 fast-path ``param.samples``, all channels: SENTINEL 0.582 %
  of samples; engine channels: non-NORMAL validity 6.7e-5) plus deliberately **unflagged** artefacts, as the
  preview has: frozen snapshots (repeat of the previous snapshot) and top-of-scale glitches;
- **2 planted faults** per world with recorded onset: one gradual (HPT-deterioration-like extra margin loss per
  EFH) and one step (FOD-like step loss, then faster loss).

Files are Arrow IPC by default (``ipcstore.store_class``; Parquet is unreliable on big-endian IBM Z).
Planted truth (per-sortie true margin, the fault list) goes to ``<run>/_restricted_labels/overlay/`` —
evaluation only; the consumer rows go to ``<run>/overlay/param.samples/…``.

``overlay_step(run_dir, t_from, t_to)`` publishes the rows of every sortie whose SORTIE record was first
ingested in (``t_from``, ``t_to``] (all up to ``t_to`` when ``t_from`` is None); each row's ``t_ingest`` is that
SORTIE record's first ingest. Each call recomputes the trajectories from the run's consumer tree, so the
output is a deterministic function of (run fleet tree, world seed); it never writes into ``fleet/``.

CLI: ``proto/runner/run.sh proto/runner/overlay.py <run_dir> [t_from_ns|none] <t_to_ns> [--seed k]``
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from datalayer import DAY, NS, bp, fmt_ist, rows_to_table
from ipcstore import ipc_bytes, store_class

OVERLAY_VERSION = "0.1"
SOURCE_LABEL = "Generated engine trend (overlay v0.1)"
TOPIC = "param.samples"

REDLINE_C = 830.0  # dictionary 0.1.3 ENG.T5 limits: steady_max 830 degC
#: channel -> (units, recorder LSB, range min, range max) from dictionary 0.1.3 (param ids as the preview writes them)
CHANNELS = {
    "ENG.T5": ("degC", 0.5, 371.0, 871.0),
    "ENG.N2": ("percent", 0.03125, 0.0, 110.0),
    "ENG.WFM": ("lb/hr", 8.0, 0.0, 12000.0),
    "ENG.T1": ("degC", 1.0, -54.0, 149.0),
}
SAMPLES_PER_SNAPSHOT = 3  # 1 Hz inside the ECMS takeoff window (dictionary rate group ECMS-TO: 6-10 s)
P_SENTINEL = 0.00582  # preview v0.9 fast-path param.samples, all channels: (932,756 + 15,042) / 162,883,442
P_INVALID = 6.7e-5  # preview v0.9 engine channels, full path: 1 BUS_INVALID in 14,998 ENG.N2 samples
P_FREEZE = 0.005  # unflagged: a whole snapshot repeats the previous one (freeze)
P_GLITCH = 0.002  # unflagged: one EGT sample at top of scale
SENTINEL_BIT, OUT_OF_RANGE_BIT = 1 << 0, 1 << 6
SEQ_BASE = 1 << 40  # overlay sample indices sit far above any real CIR sample index


@dataclass(frozen=True)
class PlantedFault:
    fault_id: str
    tail_no: str
    mode: str  # "gradual" | "step"
    onset_day: float  # days after the world's start (2026-01-05 00:00 IST)
    rate_c_per_efh: float  # extra margin loss per EFH after onset
    step_c: float = 0.0  # immediate margin loss at onset


def planted_faults(seed: int, tails: list[str]) -> list[PlantedFault]:
    """Two planted faults per world. Live run (seed 0): TJ106 gradual from 5 Apr, TJ102 step from 10 May.
    Training worlds: two distinct tails chosen from the seed."""
    if seed == 0:
        a, b = "TJ106", "TJ102"
    else:
        g = np.random.default_rng(_h64("faults", seed))
        a, b = (str(x) for x in g.choice(sorted(tails), size=2, replace=False))
    return [
        PlantedFault(f"OVL-F1-{a}", a, "gradual", 90.0, 0.9, 0.0),
        PlantedFault(f"OVL-F2-{b}", b, "step", 125.0, 0.35, 15.0),
    ]


# ---- deterministic randomness ------------------------------------------------------------------------------
def _h64(*parts: Any) -> int:
    return int.from_bytes(hashlib.blake2b("|".join(map(str, parts)).encode(), digest_size=8).digest(), "little")


def _rng(*parts: Any) -> np.random.Generator:
    return np.random.default_rng(_h64("phx-overlay", OVERLAY_VERSION, *parts))


@dataclass(frozen=True)
class EngineParams:
    margin0_c: float
    perm_c_per_efh: float
    foul_c_per_efh: float
    foul_cap_c: float
    wash_keep: float  # fraction of fouling loss left after a wash


def engine_params(seed: int, tail: str, serial: str) -> EngineParams:
    g = _rng("engine", seed, tail, serial)
    return EngineParams(
        margin0_c=float(g.uniform(45.0, 65.0)),
        perm_c_per_efh=float(g.uniform(0.05, 0.09)),
        foul_c_per_efh=float(g.uniform(0.08, 0.14)),
        foul_cap_c=8.0,
        wash_keep=0.15,
    )


# ---- reading the run's own consumer tree (runner side) -----------------------------------------------------
def _read(run_dir: Path, topic: str, cols: list[str]) -> pa.Table:
    """The run's own consumer files of ``topic`` (Arrow IPC ``.arrow`` or Parquet), selected columns."""
    p = run_dir / "fleet" / topic
    files = sorted([*p.rglob("part-*.arrow"), *p.rglob("part-*.parquet")]) if p.exists() else []
    if not files:
        return pa.table({c: pa.array([], pa.string()) for c in cols})
    tabs = []
    for f in files:
        if f.suffix == ".arrow":
            with pa.memory_map(str(f)) as src:
                tabs.append(pa.ipc.open_file(src).read_all().select(cols))
        else:
            tabs.append(pq.ParquetFile(f).read(columns=cols))
    return pa.concat_tables(tabs)


def _sorties(run_dir: Path, t_to: int) -> list[dict[str, Any]]:
    """One row per (tail_no, sortie_id): latest version ingested by ``t_to``, with the first ingest time."""
    cols = ["record_type", "tail_no", "sortie_id", "engine_serial", "flight_hours", "t_open", "t_close",
            "t_event", "t_ingest", "record_version", "dict_version", "dict_hash"]
    t = _read(run_dir, "maint.records", cols)
    t = t.filter(pc.and_(pc.equal(t["record_type"], "SORTIE"), pc.less_equal(t["t_ingest"], pa.scalar(t_to, pa.int64()))))
    by: dict[tuple[str, str], dict[str, Any]] = {}
    for r in t.to_pylist():
        if not r["sortie_id"] or not r["tail_no"]:
            continue
        k = (r["tail_no"], r["sortie_id"])
        cur = by.get(k)
        first = min(cur["first_ingest"], r["t_ingest"]) if cur else r["t_ingest"]
        if cur is None or (r["record_version"], r["t_ingest"]) > (cur["record_version"], cur["t_ingest"]):
            by[k] = dict(r)
        by[k]["first_ingest"] = first
    out = [s for s in by.values() if s["t_open"] is not None and s["engine_serial"]]
    out.sort(key=lambda s: (s["tail_no"], s["t_open"], s["sortie_id"]))
    return out


def _washes(run_dir: Path, t_to: int) -> dict[str, list[int]]:
    """Closed engine washes per tail (fleet INSPECTION records, inspection_type WASH), by close time."""
    cols = ["record_type", "tail_no", "inspection_type", "status", "t_close", "t_ingest"]
    t = _read(run_dir, "maint.records", cols)
    t = t.filter(pc.and_(pc.equal(t["inspection_type"], "WASH"), pc.less_equal(t["t_ingest"], pa.scalar(t_to, pa.int64()))))
    out: dict[str, set[int]] = {}
    for r in t.to_pylist():
        if r["status"] == "CLOSED" and r["t_close"] is not None and r["tail_no"]:
            out.setdefault(r["tail_no"], set()).add(int(r["t_close"]))
    return {k: sorted(v) for k, v in out.items()}


def _start_utc() -> int:
    from datalayer import ist_ns

    return ist_ns(2026, 1, 5)


# ---- trajectories ------------------------------------------------------------------------------------------
def _ambient_c(t_utc: int, g: np.random.Generator) -> float:
    """Base ambient temperature: seasonal (peak late April) + diurnal (peak 14:30 local) + weather noise."""
    doy = ((t_utc - _start_utc()) / DAY + 4) % 365.25
    hour = ((t_utc / NS + 5.5 * 3600) % 86400) / 3600
    return 26.0 + 4.0 * math.sin(2 * math.pi * (doy - 25) / 365.25) + 5.0 * math.sin(2 * math.pi * (hour - 8.5) / 24) + g.normal(0, 1.5)


def trajectories(run_dir: Path, t_to: int, seed: int) -> tuple[list[dict[str, Any]], list[PlantedFault]]:
    """Per sortie (ingested by ``t_to``): engine state and the true snapshot values."""
    sorties = _sorties(run_dir, t_to)
    washes = _washes(run_dir, t_to)
    tails = sorted({s["tail_no"] for s in sorties})
    faults = planted_faults(seed, tails)
    t0 = _start_utc()
    fault_by_tail = {f.tail_no: f for f in faults}
    fault_engine: dict[str, tuple[str, str]] = {}  # fault_id -> (tail, serial) it was planted on
    state: dict[tuple[str, str], dict[str, float]] = {}
    last_t: dict[tuple[str, str], int] = {}
    out = []
    for s in sorties:
        tail, ser = s["tail_no"], s["engine_serial"]
        key = (tail, ser)
        p = engine_params(seed, tail, ser)
        st = state.setdefault(key, {"efh": 0.0, "perm": 0.0, "foul": 0.0, "fault": 0.0, "faulty": 0.0})
        prev = last_t.get(key, t0)
        for tw in washes.get(tail, ()):  # washes on this tail since this engine's previous sortie
            if prev < tw <= s["t_open"]:
                st["foul"] *= p.wash_keep
        f = fault_by_tail.get(tail)
        if f is not None and s["t_open"] >= t0 + f.onset_day * DAY:
            if f.fault_id not in fault_engine:
                fault_engine[f.fault_id] = key
                st["fault"] += f.step_c
                st["onset_efh"] = st["efh"]
                st["onset_t"] = s["t_open"]
            if fault_engine[f.fault_id] == key:
                st["faulty"] = 1.0
        fh = float(s["flight_hours"] or 0.0)
        margin = p.margin0_c - st["perm"] - st["foul"] - st["fault"]
        out.append({**s, "seed": seed, "efh_before": st["efh"], "true_margin_c": margin, "foul_c": st["foul"],
                    "fault_c": st["fault"], "faulty": bool(st["faulty"]), "params": asdict(p)})
        # degrade over this sortie
        st["efh"] += fh
        st["perm"] += p.perm_c_per_efh * fh
        st["foul"] = min(p.foul_cap_c, st["foul"] + p.foul_c_per_efh * fh)
        if st["faulty"]:
            fl = next(x for x in faults if fault_engine.get(x.fault_id) == key)
            st["fault"] += fl.rate_c_per_efh * fh
        last_t[key] = s["t_open"]
    planted = []
    for f in faults:
        e = fault_engine.get(f.fault_id)
        planted.append({**asdict(f), "engine": list(e) if e else None,
                        "onset_t": state[e]["onset_t"] if e else None,
                        "onset_efh": state[e]["onset_efh"] if e else None})
    return out, planted


# ---- rows --------------------------------------------------------------------------------------------------
def _q(v: float, lsb: float, lo: float, hi: float) -> tuple[float, int]:
    flags = 0
    if v < lo or v > hi:
        flags |= OUT_OF_RANGE_BIT
    v = min(max(v, lo), hi)
    return round(round(v / lsb) * lsb, 6), flags


def snapshot_values(tr: dict[str, Any]) -> dict[str, list[tuple[int, dict[str, float]]]]:
    """True-plus-noise channel values per phase: {"takeoff"|"cruise": [(t_sample, {param: value})]}."""
    g = _rng("sortie", tr["seed"], tr["tail_no"], tr["sortie_id"])
    t_open, t_close = int(tr["t_open"]), int(tr["t_close"] or tr["t_open"] + 3600 * NS)
    amb = _ambient_c(t_open, g)
    scatter = g.normal(0, 2.0)  # flight-to-flight operating scatter of corrected EGT
    egt_c = REDLINE_C - tr["true_margin_c"] + scatter
    deficit = REDLINE_C - 50.0 - egt_c  # >0 healthy, <0 deteriorated
    out: dict[str, list[tuple[int, dict[str, float]]]] = {}
    for phase in ("takeoff", "cruise"):
        if phase == "takeoff":
            t_s = t_open + 6 * NS
            t1 = amb + g.normal(0, 0.4)
            ec, n2, wf = egt_c, 97.0 - 0.02 * deficit, 9300.0 * (1 - 0.0012 * deficit)
        else:
            t_s = t_open + (t_close - t_open) // 2
            t1 = amb - 22.0 + g.normal(0, 3.0)  # inlet total temperature at cruise (altitude cooling, ram rise)
            ec, n2, wf = 640.0 - 0.6 * deficit, 91.0 - 0.015 * deficit, 4200.0 * (1 - 0.001 * deficit)
        th = (t1 + 273.15) / 288.15
        egt_raw = (ec + 273.15) * math.sqrt(th) - 273.15
        n2_raw = n2 * math.sqrt(th)
        wf_raw = wf * th**0.5
        rows = []
        for k in range(SAMPLES_PER_SNAPSHOT):
            rows.append((t_s + k * NS, {
                "ENG.T5": egt_raw + g.normal(0, 1.5),
                "ENG.N2": n2_raw + g.normal(0, 0.12),
                "ENG.WFM": wf_raw + g.normal(0, 40.0),
                "ENG.T1": t1 + g.normal(0, 0.3),
            }))
        out[phase] = rows
    return out


def build_rows(trs: list[dict[str, Any]], contract, dict_version: str, dict_hash: str) -> tuple[list[dict], list[dict]]:
    """Contract rows for the given sorties (in trajectory order, which the freeze artefact depends on) and the
    defect truth."""
    from phalanx.ground.rid import record_id

    rows, truth = [], []
    prev_vals: dict[tuple[str, str], dict[str, list]] = {}
    for tr in trs:
        g = _rng("defects", tr["seed"], tr["tail_no"], tr["sortie_id"])
        snaps = snapshot_values(tr)
        key = (tr["tail_no"], tr["engine_serial"])
        frozen = g.random() < P_FREEZE and key in prev_vals
        if frozen:  # unflagged: the snapshot repeats the previous sortie's values
            snaps = {ph: [(t, dict(v)) for (t, _), (_, v) in zip(snaps[ph], prev_vals[key][ph], strict=True)]
                     for ph in snaps}
        prev_vals[key] = {ph: [(t, dict(v)) for t, v in snaps[ph]] for ph in snaps}
        n_def = {"sentinel": 0, "invalid": 0, "glitch": 0, "frozen": int(frozen)}
        for pi, phase in enumerate(("takeoff", "cruise")):
            for si, (t_s, vals) in enumerate(snaps[phase]):
                for ci, (pid, v) in enumerate(sorted(vals.items())):
                    units, lsb, lo, hi = CHANNELS[pid]
                    validity, flags = "NORMAL", 0
                    if pid == "ENG.T5" and g.random() < P_GLITCH:
                        v = hi  # unflagged top-of-scale glitch
                        n_def["glitch"] += 1
                    val, flags = _q(v, lsb, lo, hi)
                    if pid == "ENG.T5" and v == hi:
                        flags &= ~OUT_OF_RANGE_BIT  # the glitch stays unflagged, as in the preview
                    if g.random() < P_SENTINEL:
                        val, flags = lo, flags | SENTINEL_BIT  # bottom-of-scale sentinel word
                        n_def["sentinel"] += 1
                    if g.random() < P_INVALID:
                        validity = "BUS_INVALID"
                        n_def["invalid"] += 1
                    seq = SEQ_BASE + pi * 1000 + si * 10 + ci
                    rid = record_id(contract, TOPIC, {
                        "provenance": "direct", "tail_no": tr["tail_no"], "sortie_id": tr["sortie_id"],
                        "channel_id": "direct:FADEC:", "param_id": pid, "seq": seq, "msg_index": 0,
                    })
                    rows.append({
                        "record_id": rid.hex(), "dict_version": dict_version, "dict_hash": dict_hash,
                        "param_id": pid, "tail_no": tr["tail_no"], "sortie_id": tr["sortie_id"],
                        "engine_serial": tr["engine_serial"], "source_lru": "FADEC", "lane": None, "bus": None,
                        "rt_sa_word": None, "label_sdi": None, "t_sample": int(t_s), "t_bus": None,
                        "t_record": None, "t_utc": int(t_s), "t_ingest": int(tr["first_ingest"]),
                        "value_eu": float(val), "raw_counts": None, "units": units, "validity": validity,
                        "quality_flags": int(flags), "provenance": "direct", "recording_id": None, "sink": None,
                    })
        truth.append({
            "world_seed": tr["seed"], "tail_no": tr["tail_no"], "sortie_id": tr["sortie_id"],
            "engine_serial": tr["engine_serial"], "t_open": int(tr["t_open"]), "t_ingest": int(tr["first_ingest"]),
            "flight_hours": float(tr["flight_hours"] or 0.0), "efh_before": tr["efh_before"],
            "true_margin_c": tr["true_margin_c"], "foul_c": tr["foul_c"], "fault_c": tr["fault_c"],
            "faulty": tr["faulty"], **{f"defect_{k}": v for k, v in n_def.items()},
        })
    return rows, truth


def _run_seed(run_dir: Path) -> int:
    rj = run_dir / "run.json"
    if rj.exists():
        doc = json.loads(rj.read_text())
        if "overlay_seed" in doc:
            return int(doc["overlay_seed"])
    m = [p for p in run_dir.parts if p.startswith("seed=")]
    return int(m[-1].split("=")[1]) if m else 0


def overlay_step(run_dir: Path | str, t_from: int | None, t_to: int, *, seed: int | None = None) -> dict[str, Any]:
    """Publish the overlay rows of sorties first ingested in (t_from, t_to]. Returns counts and files."""
    run_dir = Path(run_dir)
    seed = _run_seed(run_dir) if seed is None else int(seed)
    c = bp._contract()
    trs, planted = trajectories(run_dir, t_to, seed)
    new = [tr for tr in trs if (t_from is None or tr["first_ingest"] > t_from) and tr["first_ingest"] <= t_to]
    # the fleet records carry the dictionary version and hash: the overlay rows carry the same
    dv, dh = (trs[0]["dict_version"], trs[0]["dict_hash"]) if trs else ("", "")
    # rows depend on the previous snapshot (freeze artefact), so build all and keep the new ones
    rows, truth = build_rows(trs, c, dv, dh)
    want = {(tr["tail_no"], tr["sortie_id"]) for tr in new}
    rows = [r for r in rows if (r["tail_no"], r["sortie_id"]) in want]
    truth = [r for r in truth if (r["tail_no"], r["sortie_id"]) in want]
    store = store_class()(run_dir / "overlay", c, restricted_root=run_dir / "_restricted_labels" / "overlay")
    files: list[Path] = []
    if rows:
        files = store.write(TOPIC, rows_to_table(c, TOPIC, rows))  # partitions: date / tail_no / sortie_id
    rdir = run_dir / "_restricted_labels" / "overlay"
    rdir.mkdir(parents=True, exist_ok=True)
    if truth:
        tt = pa.Table.from_pylist(truth)
        lo = "none" if t_from is None else str(t_from)
        (rdir / f"truth-{lo}-{t_to}.arrow").write_bytes(ipc_bytes(tt))  # Arrow IPC: safe on big-endian too
    (rdir / "planted_faults.json").write_text(json.dumps({
        "source_label": SOURCE_LABEL, "overlay_version": OVERLAY_VERSION, "world_seed": seed,
        "faults": planted, "as_of": fmt_ist(t_to),
        "rates": {"P_SENTINEL": P_SENTINEL, "P_INVALID": P_INVALID, "P_FREEZE": P_FREEZE, "P_GLITCH": P_GLITCH},
    }, indent=2) + "\n")
    return {"source_label": SOURCE_LABEL, "t_from": t_from, "t_to": t_to, "sorties": len(new), "rows": len(rows),
            "files": [str(p.relative_to(run_dir)) for p in files]}


if __name__ == "__main__":
    a = sys.argv[1:]
    seed = None
    if "--seed" in a:
        i = a.index("--seed")
        seed = int(a[i + 1])
        del a[i : i + 2]
    run, lo, hi = Path(a[0]), (None if a[1] == "none" else int(a[1])), int(a[2])
    print(json.dumps(overlay_step(run, lo, hi, seed=seed), indent=2))
