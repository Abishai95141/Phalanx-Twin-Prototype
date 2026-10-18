"""Ground API (port 8700): serves ``/api`` and the screens in ``proto/web``.

Phase 1-A: readiness, twin, serial lineage, search, health. Phase 2 adds the epoch loop, board and orders.
Responses for the readiness page keep the film's ``window.PHX_DATA`` shape (``proto/web/assets/SHAPES.md``).

Config (environment): ``PHX_RUN_DIR`` — the run to serve (default ``proto/runs/gonogo``); ``PHX_ASOF`` — the
default as-of time (ISO, default 2026-06-22T06:00+05:30). Every endpoint takes ``?asof=`` (ISO or UTC ns).
Start: python -m uvicorn api:app --app-dir proto/ground --host 127.0.0.1 --port 8700
"""

from __future__ import annotations

import datetime as dt
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

import present
import visits
from interfaces import NS, SOURCE_LABEL, Source
from store import Store
from twin import IST, MC_STATES, Twin, ist

PROTO = Path(__file__).resolve().parents[1]
WEB = PROTO / "web"
RUN_DIR = Path(os.environ.get("PHX_RUN_DIR", PROTO / "runs" / "gonogo"))
DEFAULT_ASOF = os.environ.get("PHX_ASOF", "2026-06-22T06:00+05:30")

app = FastAPI(title="Phalanx Twin (ground side)")
_lock = threading.Lock()


@lru_cache(maxsize=1)
def _state() -> tuple[Store, Twin]:
    store = Store.for_run(RUN_DIR)
    return store, Twin(store)


def parse_t(asof: str | None) -> int:
    if not asof and _loop_ready():
        return _loop().current.t_snapshot
    s = asof or DEFAULT_ASOF
    if s.isdigit():
        return int(s)
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError as e:
        raise HTTPException(422, f"asof must be ISO time or UTC ns: {s}") from e
    if d.tzinfo is None:
        d = d.replace(tzinfo=IST)
    return int(d.timestamp()) * NS + d.microsecond * 1000


def iso_ist(t: int) -> str:
    return dt.datetime.fromtimestamp(t / NS, IST).isoformat(timespec="minutes")


_cache: dict[tuple, Any] = {}
_static: dict[tuple, Any] = {}  # per-epoch results of the slow engine calls (keyed with the epoch's snapshot time)
_MISS = object()


def static(kind: str, key: str, t: int, fn):
    """Cache an engine result for the open epoch (the data cannot change until the next epoch)."""
    k = (kind, key, t)
    v = _static.get(k, _MISS)
    if v is _MISS:
        v = fn()
        _static[k] = v
    return v


def _evals_cached():
    ev = _evaluations()
    if ev is None:
        return None
    return lambda store, twin, t: static("evals", "", t, lambda: ev(store, twin, t))


def _warm(loop) -> None:
    """Pre-compute every board issue's detail and workbench, every twin and the governance pages in the background,
    so the screens answer at once."""
    import threading

    def run() -> None:
        t = loop.current.t_snapshot
        try:
            ids = [i.issue_id for i in loop.current.issues]
            for iid in ids:
                with _lock:
                    _issue_static(iid, t)
            store, twin = _state()
            for tail in twin.tails(t):
                twin_tail(tail, None)
            readiness(None)
            policies_page(None)
            assurance_page()
        except Exception:  # noqa: BLE001 — warming is best effort
            pass

    threading.Thread(target=run, daemon=True).start()


def cached(key: tuple, fn):
    with _lock:
        if key not in _cache:
            _cache[key] = fn()
        return _cache[key]


@app.get("/api/health")
def health() -> dict[str, Any]:
    store, _ = _state()
    return {
        "status": "ok",
        "run": RUN_DIR.name,
        "default_asof": DEFAULT_ASOF,
        "files": {k: len(v) for k, v in store.files.items()},
        "rejected": [{"path": str(r.path.name), "reason": r.reason} for r in store.rejected[:20]],
    }


@app.post("/api/refresh")
def refresh() -> dict[str, Any]:
    """Load part files the runner has published since the last refresh."""
    store, twin = _state()
    with _lock:
        new = store.refresh()
        twin.invalidate()
        _cache.clear()
    return {"loaded": new}


@app.get("/api/readiness")
def readiness(asof: str | None = Query(None)) -> dict[str, Any]:
    t = parse_t(asof)

    def build() -> dict[str, Any]:
        _, twin = _state()
        fs = twin.fleet(t)
        rows = [twin.fleet_row(t, ts) for ts in fs.tails.values()]
        cards_fn = _engine("readiness_cards")
        if cards_fn is not None:
            try:
                cards = cards_fn(_state()[0], twin, t) or {}
                for r in rows:
                    if r["tail"] in cards:
                        r["card"] = cards[r["tail"]]
            except Exception:  # noqa: BLE001 — the page falls back to state-based card text
                pass
        mc_now = sum(1 for r in rows if r["state"] in MC_STATES)
        sn = twin.snap(t)
        return {
            "asof": iso_ist(t),
            "snapshot_id": fs.snapshot_id,
            "source": SOURCE_LABEL[Source.FLEET],
            "now": {"mc": mc_now, "of": len(rows)},
            "fleet": rows,
            "kpis": {"d30": fs.kpis_30d, "all": fs.kpis_all, "norm_mc": 0.75},
            "mc_daily": [{"d": d, **{k: c.get(k, 0) for k in ("mc", "nmcs", "nmcm", "nmcd")}} for d, c in fs.mc_daily],
            "triage": {"alert_rows": fs.funnel["alert_rows"], "events_total": len(sn.bit), "cautions_total": len(sn.cautions)},
        }

    return cached(("readiness", t), build)


@app.get("/api/twin/{tail}")
def twin_tail(tail: str, asof: str | None = Query(None)) -> dict[str, Any]:
    t = parse_t(asof)

    def build() -> dict[str, Any]:
        _, twin = _state()
        if tail not in twin.tails(t):
            raise HTTPException(404, f"unknown tail {tail}")
        ts = twin.tail(t, tail)
        s = twin.sorties(t, tail)
        sn = twin.snap(t)
        import pandas as pd

        ev = pd.concat([sn.bit, sn.cautions], ignore_index=True)
        ev = ev[ev.tail_no == tail]
        codes_by_sortie = ev.groupby("sortie_id").event_code.apply(lambda c: sorted(set(c))).to_dict()
        return {
            "tail": tail,
            "asof": iso_ist(t),
            "snapshot_id": ts.snapshot_id,
            "source": SOURCE_LABEL[Source.FLEET],
            "status": ts.status.value,
            "state": twin.state_at(t, t).get(tail, ("UNKNOWN", None))[0],
            "status_since": ist(ts.status_since),
            "down_reason": ts.down_reason,
            "last_ingest": ist(ts.last_ingest),
            "usage": {"sorties": ts.sorties, "fh": ts.flight_hours, "landings": ts.landings,
                      "sorties_30d": ts.sorties_30d, "fh_30d": ts.flight_hours_30d},
            "sorties": [
                {"id": r.sortie_id, "t": ist(int(r.t_event)), "fh": float(r.flight_hours or 0),
                 "landings": int(r.landings or 0), "codes": codes_by_sortie.get(r.sortie_id, [])}
                for r in s.itertuples()
            ],
            "installed": [
                {"position": i.position, "serial": i.serial_no, "part_no": i.part_no, "since": ist(i.since),
                 "inferred": i.inferred}
                for i in ts.installed
            ],
            "alarms": [
                {"code": a.code, "count": a.count, "last_seen": ist(a.last_seen),
                 "consecutive_sorties": a.consecutive_sorties, "severity": a.severity}
                for a in ts.alarms
            ],
            "open_jobs": list(ts.open_jobs),
            "open_demands": list(ts.open_demands),
        }

    def build_with_view() -> dict[str, Any]:
        d = build()
        fn = _engine("twin_view")
        if fn is not None:
            try:
                v = fn(_state()[0], _state()[1], t, tail)
                if v:
                    d.update({k: val for k, val in v.items() if val is not None})
            except Exception as e:  # noqa: BLE001 — required fields still render; say why the lenses are missing
                d["foot"] = [f"Model views unavailable: {type(e).__name__}"]
        return d

    return cached(("twin", tail, t), build_with_view)


@app.get("/api/serial/{tail}/{serial}")
def serial(tail: str, serial: str, asof: str | None = Query(None)) -> dict[str, Any]:
    t = parse_t(asof)
    _, twin = _state()
    st = twin.serial(t, tail, serial)
    if not st.history:
        raise HTTPException(404, f"no history for {serial} on {tail}")
    return {
        "tail": tail, "serial": serial, "part_no": st.part_no, "asof": iso_ist(t),
        "history": [{"installed": ist(h.installed), "removed": ist(h.removed), "job_no": h.job_no,
                     "finding": h.finding} for h in st.history],
    }


@app.get("/api/search")
def search(q: str = Query(..., min_length=2), asof: str | None = Query(None)) -> dict[str, Any]:
    t = parse_t(asof)
    _, twin = _state()
    ql = q.lower()
    out: list[dict[str, Any]] = []
    for tail in twin.tails(t):
        if ql in tail.lower():
            out.append({"kind": "tail", "id": tail, "tail": tail, "label": tail})
        for i in twin.installed(t, tail):
            if ql in i.serial_no.lower():
                out.append({"kind": "serial", "id": i.serial_no, "tail": tail, "label": f"{i.serial_no} · {i.part_no} · {tail}"})
    sn = twin.snap(t)
    codes = sorted(set(sn.bit.event_code) | set(sn.cautions.event_code))
    out += [{"kind": "code", "id": c, "tail": None, "label": c} for c in codes if ql in c.lower()]
    jobs = twin.jobs(t)
    hits = jobs[jobs.job_no.fillna("").str.lower().str.contains(ql, regex=False)]
    out += [{"kind": "job", "id": r.job_no, "tail": r.tail_no, "label": f"{r.job_no} · {r.tail_no} · {r.status}"}
            for r in hits.head(20).itertuples()]
    return {"q": q, "results": out[:50]}


# ---- the daily loop (Phase 2) ---------------------------------------------------------------------------
RUNNER_URL = os.environ.get("PHX_RUNNER_URL", "http://127.0.0.1:8710")
_loop_obj: dict[str, Any] = {}


def _board_builder():
    """S2's triage entry point when it exists (``triage.build_board``); until then the board is empty."""
    try:
        from triage import build_board  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — engines not delivered yet
        return None
    return build_board


def _evaluations():
    """S2's policy evaluations per issue (zen-engine results with trace hashes), for the log and for replay."""
    try:
        from triage import evaluate
    except Exception:  # noqa: BLE001
        return None
    return lambda store, twin, t: evaluate(store, twin, t).evaluations


def _parse_until(v: Any, default: int) -> int:
    """Snooze end: UTC ns, an ISO date (06:00 IST that day) or an ISO date-time; default otherwise."""
    if v in (None, ""):
        return default
    if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
        return int(v)
    try:
        d = dt.datetime.fromisoformat(str(v))
    except ValueError as e:
        raise HTTPException(422, f"until must be an ISO date, date-time or UTC ns: {v}") from e
    if len(str(v)) <= 10:
        d = d.replace(hour=6, minute=0)
    if d.tzinfo is None:
        d = d.replace(tzinfo=IST)
    return int(d.timestamp()) * NS


def _loop_ready() -> bool:
    return "loop" in _loop_obj and _loop_obj["loop"].current is not None


def _loop():
    from epoch import Loop
    from lel import EventLog

    if "loop" not in _loop_obj:
        st = _runner_status()
        if st.get("replaying"):
            raise HTTPException(503, "The simulated fleet is being rebuilt after a restart — ready in a few minutes.")
        store, twin = _state()
        log = EventLog(RUN_DIR / "lel.sqlite")
        loop = Loop(store, twin, log, RUNNER_URL, _board_builder(), evaluations=_evaluations())
        t0 = st.get("t_published") or parse_t(DEFAULT_ASOF)
        if not any(True for _ in log.events(type="RUN_STARTED")):
            log.append("RUN_STARTED", f"run:{RUN_DIR.name}", {"run": RUN_DIR.name, "start": t0}, t0)
        from forkgate import ForkGate

        loop.forkgate = ForkGate(RUNNER_URL, log)
        loop.open(t0)
        loop.forkgate.start(loop.current)
        try:
            import governance

            governance.register_models(loop)
        except Exception:  # noqa: BLE001 — registration is bookkeeping; never blocks the loop
            pass
        _loop_obj["loop"] = loop
        _warm(loop)
    return _loop_obj["loop"]


def _runner_status() -> dict[str, Any]:
    try:
        import httpx

        return httpx.get(f"{RUNNER_URL}/status", timeout=10).json()
    except Exception:  # noqa: BLE001 — runner down: the data endpoints still work, the loop does not
        return {}


def _resync(loop) -> None:
    """Keep the open epoch on the runner's day (after a runner restart, replay or reset)."""
    st = _runner_status()
    if st.get("replaying"):
        raise HTTPException(503, "The simulated fleet is being rebuilt after a restart — ready in a few minutes.")
    t = st.get("t_published")
    if t and loop.current is not None and t != loop.current.t_snapshot:
        loop.open(t)
        loop.forkgate.start(loop.current)
        _cache.clear()
        _static.clear()
        _warm(loop)


def _decide(loop, issue_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """A decision on an issue applies to every order of that issue on today's board."""
    desk = loop.current.desk
    drafts = [d for d in desk.drafts.values() if d.candidate.issue_id == issue_id and d.state not in ("REJECTED", "NOT_ISSUED")]
    if not drafts:
        raise HTTPException(404, "no open order for this issue in the current epoch")
    who, action = body.get("by") or "SEO", (body.get("action") or "").lower()
    try:
        for d in drafts:
            if action == "approve":
                desk.approve(d.order_id, who)
            elif action == "reject":
                desk.reject(d.order_id, who, body.get("reason", ""))
            elif action == "snooze":
                desk.snooze(d.order_id, who, _parse_until(body.get("until"), loop.current.t_snapshot + 86_400 * NS))
            elif action == "modify":
                if d.candidate.authority.value == "AGENT":
                    desk.approve(desk.modify(d.order_id, who, body.get("params") or dict(d.candidate.parameters)).order_id, who)
            else:
                raise HTTPException(422, "action must be approve | modify | reject | snooze")
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e
    label = {"approve": "APPROVED", "reject": "REJECTED", "snooze": "SNOOZED", "modify": "MODIFIED"}[action]
    out = {"action": label, "by": who, "at": present.hm(loop.current.clock_now())}
    if action == "snooze":
        out["until"] = present.iso(_parse_until(body.get("until"), loop.current.t_snapshot + 86_400 * NS))
    return {"decision": out}


@app.get("/api/epoch")
def epoch_state() -> dict[str, Any]:
    with _lock:
        loop = _loop()
        _resync(loop)
        return present.epoch_view(loop)


def _advance(n: int, approve: str) -> dict[str, Any]:
    loop = _loop()
    _resync(loop)
    for _ in range(n):
        if approve == "agent":  # autoplay: AGENT orders approved as recommended; HUMAN orders are never auto-signed
            for d in list(loop.current.desk.drafts.values()):
                if d.state == "PROPOSED" and not d.needs_signature:
                    loop.current.desk.approve(d.order_id, "AUTOPLAY")
        loop.advance()
        loop.forkgate.start(loop.current)
    _cache.clear()
    _static.clear()
    _warm(loop)
    return present.epoch_view(loop)


@app.get("/api/board")
def board() -> dict[str, Any]:
    with _lock:
        loop = _loop()
        _, twin = _state()
        sn = twin.snap(loop.current.t_snapshot)
        return present.board_view(loop, len(sn.bit) + len(sn.cautions))


def _engine(name: str):
    try:
        mod = __import__("triage")
        return getattr(mod, name)
    except Exception:  # noqa: BLE001 — S2's engines not delivered yet
        return None


@app.get("/api/issues/{issue_id}")
def issue(issue_id: str) -> dict[str, Any]:
    fn = _engine("issue_detail")
    if fn is None:
        raise HTTPException(404, "issue detail is not available yet")
    with _lock:
        loop = _loop()
        store, twin = _state()
        base, has_wb = _issue_static(issue_id, loop.current.t_snapshot)
        if base is None:
            raise HTTPException(404, f"no issue {issue_id} on this board")
        d = dict(base)
        drafts = [x for x in loop.current.desk.drafts.values() if x.candidate.issue_id == issue_id]
        d["orders"] = [{"order_id": x.order_id, "action": x.candidate.action,
                        "text": present.WHAT.get(x.candidate.action, lambda _: x.candidate.rationale)(dict(x.candidate.parameters)),
                        "authority": "HUMAN" if x.needs_signature else "AGENT", "mode": x.candidate.mode,
                        "signed_by": x.signed_by, "parameters": dict(x.candidate.parameters), "status": present.order_status(x)}
                       for x in drafts if x.state not in ("REJECTED",)]
        last = max((h for x in drafts for h in x.history if h.get("state") in ("APPROVED", "REJECTED", "SNOOZED")),
                   key=lambda h: 0, default=None)
        d["decision"] = None if last is None else {"action": last["state"], "by": last["by"],
                                                   "at": present.hm(last.get("t") or loop.current.clock_now())}
        if not d["orders"]:  # work already under way from an earlier day
            d["orders"] = present.prior_orders(loop.log, issue_id, loop.current.t_orders)
        d["impact"] = loop.forkgate.impact(issue_id)
        d["impact_status"] = loop.forkgate.status().get(issue_id, "none")
        if not d.get("donothing"):
            d["donothing"] = loop.forkgate.donothing(issue_id, d.get("tail"))
        d["workbench"] = has_wb
        return d


def _issue_static(issue_id: str, t: int):
    """(S2's issue detail, whether a workbench exists) for the epoch, computed once."""
    def build():
        store, twin = _state()
        fn, wb = _engine("issue_detail"), _engine("workbench")
        detail = fn(store, twin, t, issue_id) if fn else None
        try:
            w = wb(store, twin, t, issue_id) if wb else None
        except Exception:  # noqa: BLE001
            w = None
        _static[("wb", issue_id, t)] = w
        return detail, w is not None

    return static("issue", issue_id, t, build)


@app.get("/api/workbench/{issue_id}")
def workbench(issue_id: str) -> dict[str, Any]:
    fn = _engine("workbench")
    if fn is None:
        raise HTTPException(404, "workbench is not available yet")
    with _lock:
        loop = _loop()
        store, twin = _state()
        t = loop.current.t_snapshot
        d = static("wb", issue_id, t, lambda: fn(store, twin, t, issue_id))
        if d is None:
            raise HTTPException(404, f"no workbench for {issue_id}")
        return d


@app.post("/api/workbench/{issue_id}/draft")
def workbench_draft(issue_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Put the chosen workbench test on today's board as a consent order of this issue."""
    from dataclasses import replace

    from interfaces import Authority, CandidateOrder

    fn = _engine("workbench")
    if fn is None:
        raise HTTPException(404, "workbench is not available yet")
    with _lock:
        loop = _loop()
        store, twin = _state()
        wb = fn(store, twin, loop.current.t_snapshot, issue_id) or {}
        test = next((x for x in wb.get("tests", []) if x.get("test_id") == body.get("test_id")), None)
        if test is None or not test.get("order"):
            raise HTTPException(404, "unknown test for this issue")
        base = next((d.candidate for d in loop.current.desk.drafts.values() if d.candidate.issue_id == issue_id), None)
        if base is None:
            raise HTTPException(409, "this issue has no order on today's board to attach the test to")
        try:
            from policies import authority_of

            auth = authority_of(test["order"]["action"])
        except Exception:  # noqa: BLE001
            auth = Authority.AGENT
        c = replace(base, row="WB", action=test["order"]["action"], parameters=dict(test["order"]["parameters"]),
                    authority=auth, rationale=f"Workbench test {test.get('name', body.get('test_id'))}")
        semver = base.policy_version.split("/")[1].split("+")[0] if "/" in (base.policy_version or "") else "1.0.0"
        d = loop.current.desk.propose(c, semver)
        loop.log.append("RECOMMENDATION_PROPOSED", f"order:{d.order_id}", {
            "issue_id": issue_id, "rule": c.rule, "row": "WB", "policy_version": c.policy_version, "action": c.action,
            "parameters": dict(c.parameters), "authority": c.authority.value, "mode": c.mode, "rationale": c.rationale},
            loop.current.t_orders)
        _cache.clear()
        return {"order_id": d.order_id}


@app.get("/api/policies")
def policies_page(issue: str | None = Query(None)) -> dict[str, Any]:
    import governance

    with _lock:
        loop = _loop()
        store, twin = _state()
        t = loop.current.t_snapshot
        return static("policies", issue or "", t, lambda: governance.policies_view(store, twin, t, issue))


@app.get("/api/assurance")
def assurance_page() -> dict[str, Any]:
    import governance

    with _lock:
        loop = _loop()
        store, twin = _state()
        t = loop.current.t_snapshot
        base = static("assurance", "", t, lambda: governance.assurance_view(store, twin, t, loop))
        return governance.refresh_dynamic(base, loop)


@app.post("/api/epoch/advance")
def epoch_advance(body: dict[str, Any] | None = None) -> dict[str, Any]:
    with _lock:
        return _advance(1, (body or {}).get("approve", "none"))


@app.post("/api/epoch/autoplay")
def epoch_autoplay(body: dict[str, Any] | None = None) -> dict[str, Any]:
    n = int((body or {}).get("n", 3))
    if not 1 <= n <= 30:
        raise HTTPException(422, "n must be 1–30")
    with _lock:
        return _advance(n, (body or {}).get("approve", "agent"))


@app.post("/api/issues/{issue_id}/decision")
def issue_decision(issue_id: str, body: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        return _decide(_loop(), issue_id, body)


@app.post("/api/orders/{order_id}/sign")
def order_sign(order_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    with _lock:
        desk = _loop().current.desk
        if order_id not in desk.drafts:
            raise HTTPException(404, "unknown order for this epoch")
        try:
            d = desk.sign(order_id, (body or {}).get("by") or "ENGG-OFFICER")
        except (ValueError, PermissionError) as e:
            raise HTTPException(409, str(e)) from e
        return {"order_id": d.order_id, "signed_by": d.signed_by}


@app.get("/api/provenance/{order_id:path}")
def provenance(order_id: str) -> dict[str, Any]:
    with _lock:
        store, twin = _state()
        view = present.provenance_view(_loop(), order_id, store, twin, _evals_cached())
    if view is None:
        raise HTTPException(404, "no events for this order")
    return view


@app.post("/api/provenance/verify")
def provenance_verify(body: dict[str, Any] | None = None) -> dict[str, Any]:
    with _lock:
        loop = _loop()
        v = loop.log.verify()
        loop.log.append("CHAIN_VERIFIED", "log", v, loop.current.t_orders)
        return {"ok": v["ok"], "events": v["events"], "head": v.get("head", "")[:16], "first_bad": v.get("broken_at")}


@app.post("/api/provenance/replay")
def provenance_replay(body: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store, twin = _state()
        view = present.provenance_view(_loop(), body.get("order_id", ""), store, twin, _evals_cached())
    if view is None:
        raise HTTPException(404, "no events for this order")
    return {"order_id": view["order_id"], "replay": view["replay"]}


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse("/readiness.html")


visits.install(app)  # visitor log, read-only report at /ops/<token> (visits.py)
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
