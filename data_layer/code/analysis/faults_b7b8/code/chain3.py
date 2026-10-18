"""B8-CHAIN3 (PREREGISTRATION.md §4): an exceedance found in recorded data opens a conditional inspection and the
aircraft is not mission-capable until it is inspected.

Generation: the B7-ELEC-GEN faulty bench run of pair 0 (a ground run with a generator rectifier-diode fault:
the main DC bus is shed when the generator drops) is recorded by M13 exactly as in B7. Its recorded samples of
the channels M14 consumes are delivered to the M14 of a one-tail operations world (``fleet.OneTailWorld``,
mature regime) as one ``monitor.observe`` chunk (the CIR payload form of ``phalanx.monitoring.io``: channel
index, kernel time, EU value, validity; no truth column) followed by ``monitor.download``, at a time when the
tail is on the ground: a recorded ground run downloaded after it. Everything after that is the real M14 and
M18: M14's limit monitors declare from the recorded values, the download carries ``events.exceedances`` to
M18, M18 files the record and grounds the tail until the inspection is done.

PASS iff (1) M18 opens an EXCEEDANCE_INSPECTION for the exceedance and (2) no sortie of the tail takes off
between the inspection's opening and its closing and M18's availability state is NMC throughout that window. The inspection's duration is reported. The reference world
(same root, no delivery) gives the sortie timeline before and after, so the difference is the chain's effect.

n = 1 world and 1 delivery: the chain is a deterministic routing question (does the record reach M18, does M18
ground the tail); its timing is reported, not tested against a band (no released anchor beyond "same day").

Usage: python -I chain3.py OUT_DIR
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import b7_bench_misc as M  # noqa: E402
import bench as B  # noqa: E402
import fleet as F  # noqa: E402

from phalanx.core.events import Event  # noqa: E402
from phalanx.fork.session import OpsSession  # noqa: E402
from phalanx.monitoring.module import KIND_EXCEED  # noqa: E402

NS = 10**9
DAY = 86_400 * NS
DAYS = 30
ROOT = 0xC3A1
WORLD_K = 0
REGIME = "mature"


def observe_payload(run: B.BenchRun, channels: tuple[str, ...], t0_ns: int) -> dict[str, np.ndarray]:
    """``monitor.observe`` payload of one bench recording shifted to kernel time ``t0_ns`` (the
    ``cir_chunk_payload`` form: ``ch`` index into M14's channel list, ``t``, ``v``, ``validity``)."""
    index = {c: i for i, c in enumerate(channels)}
    ch, t, v, val = [], [], [], []
    for cid in sorted(run.value):
        if cid not in index:
            continue
        n = run.value[cid].size
        ch.append(np.full(n, index[cid], np.int64))
        t.append(run.t_sample[cid].astype(np.int64) + int(t0_ns))
        v.append(run.value[cid].astype(np.float64))
        val.append(run.validity[cid].astype(np.int64))
    ch_a, t_a, v_a, val_a = (np.concatenate(x) for x in (ch, t, v, val))
    order = np.lexsort((ch_a, t_a))
    return {"ch": ch_a[order], "t": t_a[order], "v": v_a[order], "validity": val_a[order]}


def _kernel(t: int, epoch: int) -> int:
    return int(t) - epoch if int(t) >= epoch else int(t)


def _sorties(s: OpsSession, epoch: int) -> list[tuple[int, int]]:
    """(take-off, landing) kernel times of the tail's flown sorties from the SORTIE records."""
    out = []
    last: dict[str, dict] = {}
    for r in s.records("maint.records"):
        if r["record_type"] != "SORTIE":
            continue
        k = str(r["record_key"])
        if k not in last or int(r["record_version"]) >= int(last[k]["record_version"]):
            last[k] = r
    for r in last.values():
        if r.get("t_open") is not None and r.get("flight_hours") is not None:
            t_to = _kernel(r["t_open"], epoch)
            out.append((t_to, t_to + round(float(r["flight_hours"]) * 3600 * NS)))
    return sorted(out)


def _availability(s: OpsSession, epoch: int):
    """The tail's SCIR availability state as a step function of kernel time (M18 AVAILABILITY_STATE rows,
    published when a 15-min bin's worst state changes; latest version per bin)."""
    last: dict[str, dict] = {}
    for r in s.records("maint.records"):
        if r["record_type"] != "AVAILABILITY_STATE":
            continue
        k = str(r["record_key"])
        if k not in last or int(r["record_version"]) >= int(last[k]["record_version"]):
            last[k] = r
    steps = sorted((_kernel(r["t_event"], epoch), str(r["availability_state"])) for r in last.values())
    ts = np.array([x[0] for x in steps], np.int64)

    def at(t: int) -> str:
        j = int(np.searchsorted(ts, t, side="right")) - 1
        return steps[j][1] if j >= 0 else "FMC"

    return at


def _ground_time(sorties: list[tuple[int, int]], after_ns: int, margin_ns: int) -> int:
    """The first whole-second instant after ``after_ns`` with ``margin_ns`` clear of every sortie."""
    t = after_ns
    for to, ld in sorties:
        if t + margin_ns <= to:
            break
        if t < ld + margin_ns:
            t = ld + margin_ns
    return -(-t // NS) * NS


def run(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    ident = B.bench_identity("B7GEN", "G0", "P0")
    bench = B.run_bench(M.GEN_PROG, ident, M._gen_events(0))
    world = F.OneTailWorld(WORLD_K, DAYS, REGIME)
    epoch = world.epoch_utc_ns
    ref = OpsSession(world, ROOT)
    ref.run_until(DAYS * DAY)
    ref_sorties = _sorties(ref, epoch)
    t_dl = _ground_time(ref_sorties, 2 * DAY, 3600 * NS)

    s = OpsSession(F.OneTailWorld(WORLD_K, DAYS, REGIME), ROOT)
    s.run_until(t_dl)
    m14 = s.system.modules["m14"]
    pay = observe_payload(bench, tuple(m14.config.channels), t_dl)
    t_end_chunk = int(pay["t"].max())
    evs = [
        Event(t_dl, "monitor.observe", "m14", pay, source="chain3"),
        Event(-(-(t_end_chunk + 1) // NS) * NS, "monitor.download", "m14", {}, source="chain3"),
    ]
    s.world = s.system.inject(s.world, evs)
    s.run_until(DAYS * DAY)
    sorties = _sorties(s, epoch)
    last: dict[str, dict] = {}
    for r in s.records("maint.records"):
        k = str(r["record_key"])
        if k not in last or int(r["record_version"]) >= int(last[k]["record_version"]):
            last[k] = r
    insp = [r for r in last.values() if r["record_type"] == "EXCEEDANCE_INSPECTION"]
    ref_insp = [
        r for r in ref.records("maint.records") if r["record_type"] == "EXCEEDANCE_INSPECTION"
    ]
    av, av_ref = _availability(s, epoch), _availability(ref, epoch)
    rows = []
    for r in insp:
        t_open = _kernel(r["t_open"], epoch) if r.get("t_open") is not None else None
        t_close = _kernel(r["t_close"], epoch) if r.get("t_close") is not None else None
        flown = [to for to, _ in sorties if t_open is not None and to >= t_open and (t_close is None or to < t_close)]
        # availability sampled each minute strictly inside the open window (15-min bins: the bin holding the
        # opening instant may carry the earlier state, so the first and last bins are excluded)
        grid = (
            np.arange(t_open + 15 * 60 * NS, t_close - 15 * 60 * NS, 60 * NS)
            if t_open is not None and t_close is not None
            else np.zeros(0, np.int64)
        )
        states = sorted({av(int(x)) for x in grid})
        ref_states = sorted({av_ref(int(x)) for x in grid})
        rows.append(
            {
                "malfunction_code": r.get("malfunction_code"),
                "inspection_type": r.get("inspection_type"),
                "status": r.get("status"),
                "t_open_h_after_download": None if t_open is None else (t_open - t_dl) / NS / 3600.0,
                "duration_h": None if (t_open is None or t_close is None) else (t_close - t_open) / NS / 3600.0,
                "sorties_flown_while_open": len(flown),
                "availability_while_open": states,
                "reference_availability_same_window": ref_states,
                "nmc_throughout": bool(states) and all(x.startswith("NMC") for x in states),
            }
        )
    m14st = s.world.states["m14"]
    codes = m14.config.codes.codes
    exc = [
        codes[int(c)].code
        for c, k, t in zip(m14st["o_code"], m14st["o_kind"], m14st["o_t"], strict=True)
        if int(k) == KIND_EXCEED and int(t) >= t_dl
    ]
    res = {
        "n_worlds": 1,
        "world": {"tail": world.tail, "regime": REGIME, "days": DAYS, "root": ROOT},
        "download_day": t_dl / DAY,
        "chunk_samples": int(pay["t"].size),
        "m14_exceedances_from_chunk": exc,
        "reference_world_exceedance_inspections": len(ref_insp),
        "inspections": rows,
        "sorties_reference": len(ref_sorties),
        "sorties_with_chain": len(sorties),
        "verdict_opens": "PASS" if rows else "FAIL",
        "verdict_nmc_until_inspected": "PASS"
        if rows and all(r["sorties_flown_while_open"] == 0 and r["nmc_throughout"] for r in rows)
        else "FAIL",
    }
    (out / "b8_chain3.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=str), encoding="utf-8")
    return res


if __name__ == "__main__":
    print(json.dumps(run(Path(sys.argv[1])), indent=1, default=str))
