"""Decision tables (zen-engine) and preferences.

``Policies`` loads every table in ``manifest.yaml`` once, versions it as ``<name>/<semver>+jdm.<sha256[:12]>`` from
the file bytes, and evaluates it with tracing on. Each ``Evaluation`` keeps the matched row, the output, the
engine trace (node id, input, output, traceData) and a blake2b hash of that trace for the event log.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
BANNED = [(r"\bd\(\s*\)", "zero-argument d() reads the clock"), (r"\bisToday\s*\(", "isToday() reads the clock"),
          (r"\bnow\s*\(", "now()"), (r"\brand(om)?\s*\(", "random()"), (r"Math\.random", "Math.random")]


def canon(o: Any) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class Evaluation:
    policy: str
    version: str  # "<name>/<semver>+jdm.<sha12>"
    row: str | None  # matched rule id (hit policy first)
    output: dict
    input: dict
    trace: dict  # node id → {id, input, output, traceData}
    trace_hash: str  # blake2b-32 of the canonical trace

    @property
    def rec(self) -> dict:
        return self.output.get("rec", {}) or {}


class Policies:
    def __init__(self, folder: Path = HERE) -> None:
        import zen

        doc = yaml.safe_load((folder / "manifest.yaml").read_text())
        self.meta: dict[str, dict] = doc["policies"]
        self.raw: dict[str, bytes] = {n: (folder / m["file"]).read_bytes() for n, m in self.meta.items()}
        self.sha = {n: hashlib.sha256(b).hexdigest() for n, b in self.raw.items()}
        self.version = {n: f"{n}/{m['semver']}+jdm.{self.sha[n][:12]}" for n, m in self.meta.items()}
        self.semver = {n: str(m["semver"]) for n, m in self.meta.items()}
        self.engine = zen.ZenEngine()
        self._dec = {n: self.engine.create_decision(b.decode()) for n, b in self.raw.items()}

    def evaluate(self, name: str, inp: dict) -> Evaluation:
        res = self._dec[name].evaluate(inp, {"trace": True})
        trace = {k: {kk: v.get(kk) for kk in ("id", "input", "output", "traceData")} for k, v in res["trace"].items()}
        row = None
        for v in trace.values():
            td = v.get("traceData") or {}
            if isinstance(td, dict) and isinstance(td.get("rule"), dict):
                row = td["rule"].get("_id")
        h = hashlib.blake2b(canon(trace).encode(), digest_size=32).hexdigest()
        return Evaluation(name, self.version[name], row, res["result"], inp, trace, h)

    def rows(self, name: str) -> list[dict]:
        j = json.loads(self.raw[name])
        return next(n for n in j["nodes"] if n["type"] == "decisionTableNode")["content"]["rules"]

    def lint(self) -> list[str]:
        """Determinism lint: no function nodes, no clock or random calls in any expression."""
        out = []
        for name, b in self.raw.items():
            for n in json.loads(b)["nodes"]:
                if n["type"] in ("functionNode", "customNode"):
                    out.append(f"{name}:{n['id']} {n['type']}")
                for r in (n.get("content") or {}).get("rules", []):
                    for k, v in r.items():
                        if k != "_id" and v:
                            out += [f"{name}:{r['_id']}:{k} {why}" for pat, why in BANNED if re.search(pat, v)]
        return out


@lru_cache(maxsize=1)
def policies() -> Policies:
    return Policies()


class Prefs(dict):
    """Preferences with bounds enforced at load: ``prefs()["budget"]`` → 10."""


@lru_cache(maxsize=1)
def prefs(path: Path = HERE / "prefs.yaml") -> Prefs:
    doc = yaml.safe_load(Path(path).read_text())
    out = Prefs()
    for k, v in doc.items():
        if isinstance(v, dict) and "value" in v:
            lo, hi = v.get("bounds", [None, None])
            if (lo is not None and v["value"] < lo) or (hi is not None and v["value"] > hi):
                raise ValueError(f"prefs.{k} = {v['value']} outside bounds {v['bounds']}")
            out[k] = v["value"]
        else:
            out[k] = v
    return out
