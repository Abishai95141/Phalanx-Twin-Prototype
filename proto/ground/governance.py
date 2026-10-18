"""Policies and Assurance views (``/api/policies``, ``/api/assurance``) — built only from real outputs.

Policies: the zen-engine decision tables (version = semver + content hash), their rules and lint, the data layer's
authority matrix, the Python invariants, and the live evaluation + trace of any issue on today's board.
Assurance: every model's card (method, source label, version), the false-alarm champion vs its learned challenger
on held-out data, the removal-risk and engine-health evaluations written by S3, and the gates — release gate (G0),
reproduction (G1), offline metrics (G2) and paired-simulation outcomes (G3). Model versions are registered on the
event log once per run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

PROTO = Path(__file__).resolve().parents[1]
EVAL = PROTO / "eval"

INVARIANTS = [
    ("Human-only actions", "Monitoring-config changes, modifications, software loads and servicing deferrals need a named "
     "signature; the system only drafts them."),
    ("No automatic grounding", "No rule or model issues GROUND; airworthiness stays with the tech log and the release authority."),
    ("Evidence ingested first", "Every record an order cites must have been received before the decision time "
     "(checked here and again by the data layer's gateway)."),
    ("One open order per target", "Never two open orders for the same tail, action and target."),
    ("Bounded extensions", "A servicing extension may not exceed the authority matrix's cap."),
]


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001 — a missing report is shown as missing
        return None


def policies_view(store, twin, t: int, issue_id: str | None) -> dict[str, Any]:
    from policies import policies
    from triage import evaluate

    pol = policies()
    tables = []
    for name in sorted(pol.raw):
        rows = pol.rows(name)
        tables.append({"name": name, "version": pol.version[name], "semver": pol.semver[name],
                       "sha12": pol.sha[name][:12], "rules": rows, "n_rules": len(rows)})
    auth = yaml.safe_load((PROTO / "ground" / "policies" / "authority.yaml").read_text())
    authority = [{"action": a, "issuers": v.get("issuers", auth.get("default_issuers")),
                  "evidence": (v.get("evidence") or {}).get("tag"), "source": (v.get("evidence") or {}).get("source")}
                 for a, v in (auth.get("actions") or {}).items()]
    board = evaluate(store, twin, t)
    ids = [i.issue_id for i in board.issues]
    focus = issue_id if issue_id in board.evaluations else (ids[0] if ids else None)
    evals = []
    for name, ev in (board.evaluations.get(focus) or {}).items():
        evals.append({"policy": name, "version": ev.version, "row": ev.row, "input": ev.input, "output": ev.output,
                      "trace_hash": ev.trace_hash,
                      "trace": [{"node": k, "output": (v or {}).get("output")} for k, v in (ev.trace or {}).items()]})
    return {"tables": tables, "lint": pol.lint(), "authority": authority, "default_issuers": auth.get("default_issuers"),
            "invariants": [{"name": n, "text": x} for n, x in INVARIANTS], "issues": ids, "focus": focus,
            "evaluations": evals, "engine": "zen-engine 2.1.3"}


def model_cards() -> list[dict[str, Any]]:
    from engines.common import MODELS

    out = [{"model_id": mid, "model_version": ver, "engine": key, "source_label": "Simulated fleet"}
           for key, (mid, ver) in MODELS.items()]
    s3 = _json(EVAL / "model_cards.json") or {}
    for m in s3.get("models", []):
        out.append({k: m.get(k) for k in ("model_id", "model_version", "method", "source_label", "status", "outputs")}
                   | {"engine": m.get("model_id")})
    return out


def assurance_view(store, twin, t: int, loop) -> dict[str, Any]:
    from engines import cnd
    from engines.common import context

    cmp = cnd.challenger(context(store, twin, t))
    gonogo = _json(PROTO / "runs" / "gonogo" / "gonogo_report.json") or {}
    forks = []
    if loop is not None and getattr(loop, "forkgate", None) is not None:
        for iid, st in loop.forkgate.status().items():
            imp = loop.forkgate.impact(iid)
            forks.append({"issue_id": iid, "status": st, "d_mc": imp and imp["d_mc"], "pairs": imp and imp["pairs"],
                          "no_change": imp and imp.get("no_change")})
    registered = [e.payload for e in loop.log.events(type="MODEL_REGISTERED")] if loop is not None else []
    return {
        "models": model_cards(),
        "registered": registered,
        "cnd": {"champion": cmp.champion, "brier_champion": cmp.brier_champion, "brier_challenger": cmp.brier_challenger,
                "auc_champion": cmp.auc_champion, "auc_challenger": cmp.auc_challenger,
                "d_brier_ci": cmp.d_brier_ci, "n_train": cmp.n_train, "n_test": cmp.n_test},
        "hazard": {"backtest": _json(EVAL / "hazard_backtest.json"), "counts": _json(EVAL / "train_counts.json"),
                   "report_md": (EVAL / "hazard_backtest.md").read_text() if (EVAL / "hazard_backtest.md").exists() else None},
        "engine_health": {"eval": _json(EVAL / "engine_health_eval.json")},
        "gates": [
            {"gate": "G0", "name": "Release gate", "ok": not store.rejected,
             "text": f"{sum(len(v) for v in store.files.values()):,} files accepted under contract 0.2.0 · {len(store.rejected)} rejected"},
            {"gate": "G1", "name": "Reproduction", "ok": gonogo.get("verdict") == "GO",
             "text": "Rebuilt on IBM LinuxONE (s390x): simulated history and one-day step equal the reference row for row"
             if gonogo.get("verdict") == "GO"
             else "go/no-go report missing"},
            {"gate": "G2", "name": "Offline metrics", "ok": cmp.brier_champion is not None,
             "text": f"False-alarm champion Brier {cmp.brier_champion:.4f} vs challenger {cmp.brier_challenger:.4f} on "
                     f"{cmp.n_test} held-out jobs → {cmp.champion}" if cmp.brier_champion is not None else "not run"},
            {"gate": "G3", "name": "Paired simulations", "ok": any(f["status"] == "done" for f in forks),
             "text": f"{sum(f['status'] == 'done' for f in forks)} of {len(forks)} board issues simulated against doing nothing"},
        ],
        "forks": forks,
    }


def register_models(loop) -> None:
    """Log MODEL_REGISTERED once per model version on this run's event log."""
    have = {(e.payload.get("model_id"), e.payload.get("model_version")) for e in loop.log.events(type="MODEL_REGISTERED")}
    for m in model_cards():
        key = (m["model_id"], m["model_version"])
        if key not in have and m["model_id"]:
            loop.log.append("MODEL_REGISTERED", f"model:{m['model_id']}", {k: v for k, v in m.items() if v is not None},
                            loop.current.t_orders)


def refresh_dynamic(view: dict[str, Any], loop) -> dict[str, Any]:
    """The parts of the assurance view that change during an epoch: fork outcomes, registrations, gate G3."""
    v = dict(view)
    forks = []
    for iid, st in loop.forkgate.status().items():
        imp = loop.forkgate.impact(iid)
        forks.append({"issue_id": iid, "status": st, "d_mc": imp and imp["d_mc"], "pairs": imp and imp["pairs"],
                      "no_change": imp and imp.get("no_change")})
    v["forks"] = forks
    v["registered"] = [e.payload for e in loop.log.events(type="MODEL_REGISTERED")]
    done = sum(f["status"] == "done" for f in forks)
    v["gates"] = [g if g["gate"] != "G3" else {**g, "ok": done > 0,
                  "text": f"{done} of {len(forks)} board issues simulated against doing nothing"} for g in view["gates"]]
    return v
