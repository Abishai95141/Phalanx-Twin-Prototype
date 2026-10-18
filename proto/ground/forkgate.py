"""Fork gate: paired simulations of each issue's candidate orders, before the board freezes.

For every issue with orders on today's board, the runner forks the tail's live world from the 06:00 snapshot and
runs N CRN pairs (status quo vs status quo + this issue's orders) over the horizon. Results are cached by
(snapshot, order ids), logged as FORK_RESULT on each order, and shown as the decision card's "Impact".
An issue whose orders change nothing in any pair is dropped (FORK_DROPPED), as the film did for TJ105's tyres.
Jobs run in priority order (P1 first) in a background thread; the screens show "running" until they finish.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict
from typing import Any

import httpx

PAIRS = {"P1": 10, "P2": 10, "P3": 6, "P4": 0}
HORIZON_DAYS = 30
SKIP = {"MONITOR"}


class ForkGate:
    def __init__(self, runner_url: str, log) -> None:
        self.http = httpx.Client(base_url=runner_url, timeout=30)
        self.log = log
        self.results: dict[str, dict[str, Any]] = {}  # issue_id -> {status, result?, job}
        self._lock = threading.Lock()

    def start(self, ep) -> None:
        """Queue one fork job per issue with orders (P1 first). Non-blocking."""
        by_issue: dict[str, list] = defaultdict(list)
        for d in ep.desk.drafts.values():
            if d.candidate.action not in SKIP:
                by_issue[d.candidate.issue_id].append(d)
        band = {i.issue_id: i.band or "P4" for i in ep.issues}
        order = sorted(by_issue, key=lambda k: (band.get(k, "P4"), k))
        with self._lock:
            self.results = {k: {"status": "queued"} for k in order if PAIRS.get(band.get(k, "P4"), 0) > 0}
        threading.Thread(target=self._run, args=(ep, order, by_issue, band), daemon=True).start()

    def _run(self, ep, order, by_issue, band) -> None:
        for issue_id in order:
            n = PAIRS.get(band.get(issue_id, "P4"), 0)
            if n == 0:
                continue
            drafts = by_issue[issue_id]
            tail = drafts[0].tail
            key = hashlib.blake2b(f"{ep.snapshot_id}|{sorted(d.order_id for d in drafts)}|{n}".encode(), digest_size=12).hexdigest()
            try:
                r = self.http.post("/fork", json={"tail": tail, "orders": [d.command() for d in drafts], "n": n,
                                                  "horizon_days": HORIZON_DAYS, "key": key})
                r.raise_for_status()
                with self._lock:
                    self.results[issue_id] = {"status": "running", "job": key}
                while True:
                    s = self.http.get(f"/fork/{key}").json()
                    if s["status"] in ("done", "failed"):
                        break
                    time.sleep(5)
            except Exception as e:  # noqa: BLE001 — the gate never blocks the board
                with self._lock:
                    self.results[issue_id] = {"status": "failed", "error": str(e)}
                continue
            if s["status"] == "failed":
                with self._lock:
                    self.results[issue_id] = {"status": "failed", "error": s.get("error")}
                continue
            res = s["result"]
            with self._lock:
                self.results[issue_id] = {"status": "done", "result": res}
            d_mc = res["diffs"].get("mc", {})
            logged = {e.payload.get("job") for e in self.log.events(type="FORK_RESULT")}
            for d in drafts:
                if key not in logged:  # an API restart re-attaches the same job: log its result once
                    self.log.append("FORK_RESULT", f"order:{d.order_id}", {
                        "job": key, "issue_id": issue_id, "pairs": res["pairs"], "horizon_days": res["horizon_days"],
                        "mode": res["mode"], "d_mc": [d_mc.get("mean", 0.0), d_mc.get("ci_low", 0.0), d_mc.get("ci_high", 0.0)],
                        "diffs": res["diffs"], "verdicts": res["verdicts"], "no_change": res["no_change"]}, ep.clock_now())
                if res["no_change"] and d.state == "PROPOSED":
                    d.state, d.note = "DROPPED", f"no change in {res['pairs']} paired simulations"
                    self.log.append("FORK_DROPPED", f"order:{d.order_id}", {"reason": d.note}, ep.clock_now())

    def impact(self, issue_id: str) -> dict[str, Any] | None:
        """``PHX_ISSUE.impact`` (null until the job is done)."""
        with self._lock:
            r = self.results.get(issue_id)
        if not r or r["status"] != "done":
            return None
        res = r["result"]
        d = res["diffs"]

        def fmt(k: str, scale: float = 1.0, nd: int = 1) -> str:
            v = d.get(k)
            if not v:
                return "—"
            sig = not (v["ci_low"] <= 0 <= v["ci_high"])
            return f"{v['mean'] * scale:+.{nd}f}".replace("-", "\u2212") + ("" if sig else " · not significant")

        mc = d.get("mc", {"mean": 0, "ci_low": 0, "ci_high": 0})
        return {
            "horizon_days": res["horizon_days"], "pairs": res["pairs"],
            "d_mc": [round(mc["mean"] * 100, 1), round(mc["ci_low"] * 100, 1), round(mc["ci_high"] * 100, 1)],
            "source": f"Simulated fleet · {res['pairs']} paired simulations vs doing nothing ({res['mode']} mode)",
            "rows": [
                {"k": "Maintenance man-hours", "v": fmt("man_hours", nd=0)},
                {"k": "Days grounded for parts", "v": fmt("aog_days")},
                {"k": "In-flight failures", "v": fmt("in_flight_failures", nd=2), "muted": True},
            ],
            "no_change": res["no_change"],
        }

    def status(self) -> dict[str, str]:
        with self._lock:
            return {k: v["status"] for k, v in self.results.items()}

    def donothing(self, issue_id: str, tail: str | None) -> dict[str, Any] | None:
        """``PHX_ISSUE.donothing`` from the same paired simulations: mission capable over the horizon with no
        action (status quo) and with this issue's orders (status quo + the paired difference)."""
        with self._lock:
            r = self.results.get(issue_id)
        if not r or r["status"] != "done":
            return None
        res = r["result"]
        sq = (res.get("status_quo_mean") or {}).get("mc")
        dm = (res["diffs"].get("mc") or {}).get("mean")
        if sq is None or dm is None:
            return None
        return {"tail": tail, "horizon_days": res["horizon_days"], "pairs": res["pairs"],
                "status_quo": round(sq * 100, 1), "with_plan": round((sq + dm) * 100, 1),
                "note": f"Mission capable over the next {res['horizon_days']} days, mean of {res['pairs']} paired simulations",
                "source": "Simulated fleet"}
