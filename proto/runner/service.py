"""Runner HTTP service (fleet side, port 8710). Internal: only the ground side calls it.

POST /init   {run_id, start?}            build the 8 tail worlds and publish history ingested by ``start``
POST /step   {to?, orders?}              advance to ``to`` (default: one day after the last publish), submitting
                                         ``orders`` (tail -> orders.commands rows) at the 08:00 epoch they name
GET  /status                             run id, logical time, tails

Start with: ./run.sh -m uvicorn service:app --host 127.0.0.1 --port 8710
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from datalayer import Order, fmt_ist, ist_ns
from world import DEFAULT_DAYS, Fleet, fleet_store

RUNS = Path(__file__).resolve().parents[1] / "runs"
DEFAULT_START = ist_ns(2026, 6, 22, 6)

app = FastAPI(title="Phalanx runner (fleet side)")
_lock = threading.Lock()
_state: dict[str, Any] = {"fleet": None, "run_id": None, "replaying": False}


class InitBody(BaseModel):
    run_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    start: int = DEFAULT_START  # UTC ns
    days: int = DEFAULT_DAYS


class OrderBody(BaseModel):
    order_id: str
    issuer_id: str
    issuer_kind: str  # AGENT | HUMAN
    t_issued: int  # UTC ns of an 08:00 IST epoch inside the step
    action: str
    parameters: dict[str, Any] = {}
    priority: str = "ROUTINE"
    target_tail_no: str | None = None
    target_base: str | None = None
    evidence: list[str] = []  # record ids, hex
    policy_version: str | None = None


class StepBody(BaseModel):
    to: int | None = None
    orders: dict[str, list[OrderBody]] = {}


def _fleet() -> Fleet:
    if _state.get("replaying"):
        raise HTTPException(409, f"rebuilding run {_state['run_id']} from its journal after a restart; try again shortly")
    f = _state["fleet"]
    if f is None:
        raise HTTPException(409, "no run: POST /init first")
    return f


def _orders(rows_by_tail: dict[str, list[OrderBody]]) -> dict[str, dict[int, list[Order]]]:
    by_tail: dict[str, dict[int, list[Order]]] = {}
    for tail, rows in rows_by_tail.items():
        grouped: dict[int, list[Order]] = defaultdict(list)
        for o in rows:
            grouped[o.t_issued].append(Order(
                order_id=o.order_id, issuer_id=o.issuer_id, issuer_kind=o.issuer_kind, t_issued=o.t_issued,
                t_effective=o.t_issued, action=o.action, parameters=o.parameters, priority=o.priority,
                target_tail_no=o.target_tail_no or tail, target_base=o.target_base,
                evidence=tuple(bytes.fromhex(e) for e in o.evidence), policy_version=o.policy_version))
        by_tail[tail] = dict(grouped)
    return by_tail


# ---- journal: every init/step is appended, so a restarted runner can rebuild the same world -------------
CURRENT = RUNS / "current.json"


def _overlay(run_dir: Path, t_from: int | None, t_to: int) -> dict[str, Any]:
    """Generated engine trend (overlay v0.1) for the sorties ingested in the window; never fails the step."""
    try:
        from overlay import overlay_step

        out = overlay_step(run_dir, t_from, t_to)
        return {"rows": out.get("rows", out.get("n_rows")), "ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _journal(run_dir: Path, entry: dict[str, Any]) -> None:
    with open(run_dir / "journal.jsonl", "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def _replay(run_id: str) -> None:
    """Rebuild the in-memory tail worlds by re-running the journal (deterministic: same seeds, same orders).
    Publishing goes to a scratch tree, so the run's published files are never touched."""
    run_dir = RUNS / run_id
    lines = [json.loads(x) for x in (run_dir / "journal.jsonl").read_text().splitlines() if x.strip()]
    init = next(e for e in lines if e["kind"] == "init")
    scratch = run_dir / ".replay_scratch"
    fleet = Fleet(scratch, days=init["days"])
    fleet.step(init["start"])
    for e in lines:
        if e["kind"] == "step":
            fleet.step(e["to"], _orders({t: [OrderBody(**o) for o in rows] for t, rows in e["orders"].items()}))
    fleet.run_dir, fleet.store = run_dir, fleet_store(run_dir)
    shutil.rmtree(scratch, ignore_errors=True)
    _state.update(fleet=fleet, run_id=run_id, replaying=False)


@app.on_event("startup")
def _resume() -> None:
    if CURRENT.exists():
        run_id = json.loads(CURRENT.read_text())["run_id"]
        if (RUNS / run_id / "journal.jsonl").exists():
            _state.update(run_id=run_id, replaying=True)
            threading.Thread(target=_replay, args=(run_id,), daemon=True).start()


@app.post("/init")
def init(body: InitBody) -> dict[str, Any]:
    with _lock:
        run_dir = RUNS / body.run_id
        if (run_dir / "fleet").exists():
            raise HTTPException(409, f"run {body.run_id} already exists")
        fleet = Fleet(run_dir, days=body.days)
        doc = fleet.step(body.start)
        _journal(run_dir, {"kind": "init", "start": body.start, "days": body.days})
        doc["overlay"] = _overlay(run_dir, None, body.start)
        CURRENT.write_text(json.dumps({"run_id": body.run_id}))
        _state.update(fleet=fleet, run_id=body.run_id)
        return {"run_id": body.run_id, "t": body.start, "t_ist": fmt_ist(body.start), "build_s": fleet.build_s, **_summary(doc)}


@app.post("/step")
def step(body: StepBody) -> dict[str, Any]:
    with _lock:
        fleet = _fleet()
        to = body.to if body.to is not None else fleet.day_ahead()
        by_tail = _orders(body.orders)
        try:
            doc = fleet.step(to, by_tail)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        doc["overlay"] = _overlay(fleet.run_dir, doc["t_from"], to)
        _journal(fleet.run_dir, {"kind": "step", "to": to,
                                 "orders": {t: [o.model_dump() for o in rows] for t, rows in body.orders.items()}})
        return {"run_id": _state["run_id"], "t": to, "t_ist": fmt_ist(to), **_summary(doc)}


class ForkBody(BaseModel):
    tail: str
    orders: list[OrderBody]
    n: int = Field(default=10, ge=3, le=30)
    horizon_days: int = Field(default=30, ge=1, le=120)
    key: str | None = None  # caller's cache key (snapshot id + order digests)


_jobs: dict[str, dict[str, Any]] = {}
_fork_queue: list[str] = []
_fork_cv = threading.Condition()


def _fork_worker() -> None:
    """One fork job at a time (the server has 3 vCPUs and other work)."""
    from forks import run_pairs

    while True:
        with _fork_cv:
            while not _fork_queue:
                _fork_cv.wait()
            jid = _fork_queue.pop(0)
        job = _jobs[jid]
        job["status"] = "running"
        try:
            job["result"] = run_pairs(job["runner"], job["snap"], job["orders"], n=job["n"], horizon_days=job["horizon_days"])
            job["status"] = "done"
        except Exception as e:  # noqa: BLE001 — report the failure to the caller
            job["status"], job["error"] = "failed", f"{type(e).__name__}: {e}"
        finally:
            job.pop("snap", None)


threading.Thread(target=_fork_worker, daemon=True).start()


@app.post("/fork")
def fork(body: ForkBody) -> dict[str, Any]:
    with _lock:
        fleet = _fleet()
        if body.tail not in fleet.tails:
            raise HTTPException(404, f"unknown tail {body.tail}")
        if body.key and body.key in _jobs:
            j = _jobs[body.key]
            return {"job": body.key, "status": j["status"]}
        tr = fleet.tails[body.tail]
        orders = _orders({body.tail: body.orders})[body.tail]
        snap = tr.fork_service().snapshot(tr.session)  # immutable copy of the live world, taken under the lock
        jid = body.key or f"fork-{len(_jobs) + 1}"
        _jobs[jid] = {"status": "queued", "runner": tr, "snap": snap, "n": body.n, "horizon_days": body.horizon_days,
                      "orders": [o for v in orders.values() for o in v], "tail": body.tail, "t": fleet.t_published}
    with _fork_cv:
        _fork_queue.append(jid)
        _fork_cv.notify()
    return {"job": jid, "status": "queued"}


@app.get("/fork/{jid}")
def fork_status(jid: str) -> dict[str, Any]:
    j = _jobs.get(jid)
    if j is None:
        raise HTTPException(404, "unknown fork job")
    return {"job": jid, "status": j["status"], "tail": j["tail"], "result": j.get("result"), "error": j.get("error"),
            "queue_position": _fork_queue.index(jid) + 1 if jid in _fork_queue else 0}


class ResetBody(BaseModel):
    run_id: str = Field(default="live", pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    start: int = DEFAULT_START
    days: int = DEFAULT_DAYS


@app.post("/reset")
def reset(body: ResetBody) -> dict[str, Any]:
    """Archive the run (moved to runs/archive/, never deleted) and start it again from ``start``."""
    with _lock:
        run_dir = RUNS / body.run_id
        if run_dir.exists():
            arch = RUNS / "archive"
            arch.mkdir(exist_ok=True)
            run_dir.rename(arch / f"{body.run_id}-{time.strftime('%Y%m%dT%H%M%S')}")
        _state.update(fleet=None, run_id=None, replaying=False)
    return init(InitBody(run_id=body.run_id, start=body.start, days=body.days))


@app.get("/status")
def status() -> dict[str, Any]:
    f = _state["fleet"]
    return {
        "replaying": bool(_state.get("replaying")),
        "run_id": _state["run_id"],
        "t_published": None if f is None else f.t_published,
        "t_published_ist": None if f is None or f.t_published is None else fmt_ist(f.t_published),
        "tails": [] if f is None else list(f.tails),
    }


def _summary(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "t_from": doc["t_from"],
        "wall_s": doc["wall_s"],
        "rows": {t: v["rows"] for t, v in doc["tails"].items()},
        "verdicts": {t: v["verdicts"] for t, v in doc["tails"].items()},
        "overlay": doc.get("overlay"),
    }
