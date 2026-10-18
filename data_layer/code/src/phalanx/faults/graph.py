"""Typed dependency graph (AD-27; architecture §6 M11, §9.3; report §9 "Propagation follows documented
cascades").

One graph serves three uses:

1. **Propagation of faults** (M11): a root fault activates a node; activations travel along typed edges, each
with a transfer function and a latency, to downstream physical-state nodes.
2. **Normal coupling** (documentation of the coupling map, e.g. N2 -> AMAGB -> hydraulic pumps and generator).
3. **Validation invariants** (M20, B7): the observed order and latency of a cascade in a run must match the
edges.

Nodes are *physical states* (``eng.stall``, ``elec.gen_offline``), never fault codes: codes are observations
produced by monitoring (M08/M05/M14) from the states (invariant I6, no different generation path).

**Edge mechanism** (proposed decision PD-W1.5-1): ``physics`` edges are realised by module dynamics in
telemetry mode (the graph is then an invariant) and by M11 events in usage mode; ``graph`` edges are always
realised by M11 (discrete consequences no module models, e.g. EGI invalid without a flag); ``health`` edges
are realised by M10 damage processes (crack growth to a failure threshold).

**Acyclic per step:** the sub-graph of edges whose latency can be zero (instantaneous within one truth step)
must be a DAG; edges with a strictly positive minimum latency may close loops across steps.

Transfer functions (steady activation y from source activation x in [0, 1]; ``threshold`` of the destination
node decides activation):

| kind | y | time to cross the destination threshold θ after the latency |
|---|---|---|
| ``gain`` | g·x | 0 |
| ``threshold`` | 1 if x ≥ θ_edge else 0 | 0 |
| ``lag`` | g·x (first order, τ) | −τ ln(1 − θ / y) if y > θ, never otherwise |
| ``delay`` | x | 0 (pure delay = the latency) |
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from phalanx.core.module import EvidenceTag
from phalanx.dictionary.yamlio import load_yaml

__all__ = [
    "EDGE_TYPES",
    "Activation",
    "Edge",
    "FaultGraph",
    "GraphError",
    "Template",
    "load_graph",
]

EDGE_TYPES = ("shaft", "hydraulic", "thermal", "data_electrical", "discrete", "mechanical")
MECHANISMS = ("physics", "graph", "health")
TRANSFER_KINDS = ("gain", "threshold", "lag", "delay")
LATENCY_DISTS = ("fixed", "uniform", "loguniform")
_REPO = Path(__file__).resolve().parents[3]
GRAPH_PATH = _REPO / "configs" / "tejas" / "faults" / "graph.yaml"


class GraphError(ValueError):
    pass


@dataclass(frozen=True)
class Node:
    """A physical-state node. ``effects`` are the state perturbations M11 emits when it realises the node
    (same target vocabulary as catalogue effects); a node reached through a ``physics`` edge in telemetry
    mode is produced by the module dynamics instead, so its effects are not emitted then."""

    id: str
    subsystem: str
    threshold: float = 0.5
    gate: str = "or"  # "and": activates when every parent has arrived
    description: str = ""
    effects: tuple[Mapping[str, object], ...] = ()


@dataclass(frozen=True)
class Edge:
    id: str
    src: str
    dst: str
    type: str
    transfer: Mapping[str, float | str]
    latency: Mapping[str, float | str]
    mechanism: str
    evidence: str
    tag: str

    @property
    def min_latency_s(self) -> float:
        d = self.latency["dist"]
        if d == "fixed":
            return float(self.latency["s"])
        return float(self.latency["lo"])

    def draw_latency(self, u: float) -> float:
        """Latency [s] from a uniform variate ``u`` in [0, 1) (fixed; uniform; log-uniform)."""
        d = self.latency["dist"]
        if d == "fixed":
            return float(self.latency["s"])
        lo, hi = float(self.latency["lo"]), float(self.latency["hi"])
        if d == "uniform":
            return lo + u * (hi - lo)
        return math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo)))

    def steady(self, x: float) -> float:
        """Steady destination activation for source activation ``x``."""
        k = self.transfer["kind"]
        if k == "gain" or k == "lag":
            return float(self.transfer.get("gain", 1.0)) * x
        if k == "threshold":
            return 1.0 if x >= float(self.transfer["threshold"]) else 0.0
        return x  # delay

    def time_to_cross(self, y: float, theta: float) -> float:
        """Time after the latency for the destination input to reach ``theta`` (inf if it never does)."""
        if y < theta or y <= 0.0:
            return math.inf
        if self.transfer["kind"] == "lag":
            if y == theta:
                return math.inf
            return -float(self.transfer["tau_s"]) * math.log(1.0 - theta / y)
        return 0.0

    def response(self, x: float, t_since_latency: float) -> float:
        """Destination input ``t`` seconds after the latency elapsed, for a step of size ``x`` (edge transfer
        test): first-order rise for ``lag``, immediate otherwise."""
        if t_since_latency < 0.0:
            return 0.0
        y = self.steady(x)
        if self.transfer["kind"] == "lag":
            return y * (1.0 - math.exp(-t_since_latency / float(self.transfer["tau_s"])))
        return y


@dataclass(frozen=True)
class Template:
    """A documented cascade (AIB) with its node sequence and the evidenced time window of each node, measured
    from the root activation."""

    id: str
    name: str
    root: str
    sequence: tuple[str, ...]
    windows_s: Mapping[str, tuple[float, float]]
    conditions: tuple[str, ...]
    evidence: str


@dataclass(frozen=True)
class Activation:
    t_s: float
    node: str
    magnitude: float
    via: str  # edge id ("" for roots)


@dataclass
class FaultGraph:
    nodes: Mapping[str, Node]
    edges: tuple[Edge, ...]
    templates: Mapping[str, Template]
    _out: dict[str, list[Edge]] = field(default_factory=dict, repr=False)
    _in: dict[str, list[Edge]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for e in self.edges:
            self._out.setdefault(e.src, []).append(e)
            self._in.setdefault(e.dst, []).append(e)

    def out_edges(self, node: str) -> list[Edge]:
        return self._out.get(node, [])

    def in_edges(self, node: str) -> list[Edge]:
        return self._in.get(node, [])

    # ------------------------------------------------------------------ structure
    def instantaneous_edges(self) -> list[Edge]:
        """Edges that can act within one truth step (minimum latency 0 and no lag)."""
        return [e for e in self.edges if e.min_latency_s == 0.0 and e.transfer["kind"] != "lag"]

    def step_cycle(self) -> list[str] | None:
        """A cycle among instantaneous edges (a violation of 'acyclic per step'), or None."""
        adj: dict[str, list[str]] = {}
        for e in self.instantaneous_edges():
            adj.setdefault(e.src, []).append(e.dst)
        color: dict[str, int] = {}
        stack: list[str] = []

        def visit(n: str) -> list[str] | None:
            color[n] = 1
            stack.append(n)
            for m in sorted(adj.get(n, [])):
                if color.get(m, 0) == 1:
                    return [*stack[stack.index(m) :], m]
                if color.get(m, 0) == 0:
                    found = visit(m)
                    if found:
                        return found
            stack.pop()
            color[n] = 2
            return None

        for n in sorted(adj):
            if color.get(n, 0) == 0:
                found = visit(n)
                if found:
                    return found
        return None

    def step_order(self) -> list[str]:
        """Topological order of the nodes under instantaneous edges (raises GraphError on a step cycle)."""
        cyc = self.step_cycle()
        if cyc:
            raise GraphError(f"graph is not acyclic per step: {' -> '.join(cyc)}")
        indeg = {n: 0 for n in self.nodes}
        adj: dict[str, list[str]] = {}
        for e in self.instantaneous_edges():
            adj.setdefault(e.src, []).append(e.dst)
            indeg[e.dst] += 1
        ready = sorted(n for n, d in indeg.items() if d == 0)
        out: list[str] = []
        while ready:
            n = ready.pop(0)
            out.append(n)
            for m in sorted(adj.get(n, [])):
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m)
                    ready.sort()
        return out

    # ------------------------------------------------------------------ propagation
    def propagate(
        self,
        root: str,
        *,
        magnitude: float = 1.0,
        t0_s: float = 0.0,
        uniforms: Sequence[float] | Mapping[str, float] = (),
        conditions: Sequence[str] = (),
        mechanisms: Sequence[str] = MECHANISMS,
        horizon_s: float = math.inf,
    ) -> list[Activation]:
        """Activations caused by ``root`` (event-driven, earliest first).

        ``uniforms``: latency variates, either a mapping edge id -> u or a sequence consumed in edge-id order
        of traversal (missing values -> 0.5, the median). ``conditions``: nodes active from the start (e.g.
        ``env.cold_soak``) that satisfy AND gates. Only edges whose mechanism is in ``mechanisms`` propagate.
        """
        if root not in self.nodes:
            raise GraphError(f"unknown root node {root!r}")
        u_map = dict(uniforms) if isinstance(uniforms, Mapping) else None
        u_seq = list(uniforms) if not isinstance(uniforms, Mapping) else []
        active: dict[str, Activation] = {c: Activation(t0_s, c, 1.0, "") for c in conditions}
        arrived: dict[str, dict[str, float]] = {}
        heap: list[tuple[float, int, str, float, str]] = [(t0_s, 0, root, magnitude, "")]
        seq = 1
        out: list[Activation] = []
        while heap:
            t, _, node, mag, via = heapq.heappop(heap)
            if node in active or t > horizon_s:
                continue
            act = Activation(t, node, mag, via)
            active[node] = act
            out.append(act)
            for e in sorted(self.out_edges(node), key=lambda x: x.id):
                if e.mechanism not in mechanisms:
                    continue
                dst = self.nodes[e.dst]
                y = e.steady(mag)
                tc = e.time_to_cross(y, dst.threshold)
                if math.isinf(tc):
                    continue
                if u_map is not None:
                    u = u_map.get(e.id, 0.5)
                else:
                    u = u_seq.pop(0) if u_seq else 0.5
                t_dst = t + e.draw_latency(u) + tc
                if dst.gate == "and":
                    arr = arrived.setdefault(e.dst, {})
                    arr[e.src] = t_dst
                    parents = {p.src for p in self.in_edges(e.dst) if p.mechanism in mechanisms}
                    have = set(arr) | {c for c in conditions if c in parents}
                    if not parents <= have:
                        continue
                    t_dst = max([*arr.values(), t_dst])
                heapq.heappush(heap, (t_dst, seq, e.dst, min(1.0, y), e.id))
                seq += 1
        return out

    def check_template(
        self, template_id: str, activations: Sequence[Activation], *, t0_s: float = 0.0
    ) -> list[str]:
        """Problems with ``activations`` against a documented cascade: missing nodes, order, windows."""
        tpl = self.templates[template_id]
        at = {a.node: a.t_s - t0_s for a in activations}
        problems = [f"{n} not reached" for n in tpl.sequence if n not in at]
        if problems:
            return problems
        times = [at[n] for n in tpl.sequence]
        for a, b, ta, tb in zip(tpl.sequence, tpl.sequence[1:], times, times[1:], strict=False):
            if tb < ta:
                problems.append(f"order: {b} at {tb:.3f} s before {a} at {ta:.3f} s")
        for n, (lo, hi) in tpl.windows_s.items():
            if not lo <= at[n] <= hi:
                problems.append(f"{n} at {at[n]:.3f} s outside [{lo}, {hi}] s")
        return problems


def _parse(doc: Mapping) -> FaultGraph:
    if doc.get("format") != "phalanx.fault_graph/1":
        raise GraphError("graph.yaml: format must be phalanx.fault_graph/1")
    nodes = {}
    node_keys = {"subsystem", "threshold", "gate", "description", "effects"}
    for nid, n in doc["nodes"].items():
        if set(n) - node_keys:
            raise GraphError(f"node {nid}: unknown keys {sorted(set(n) - node_keys)}")
        if n.get("gate", "or") not in ("or", "and"):
            raise GraphError(f"node {nid}: gate must be or/and")
        effects = tuple(dict(e) for e in n.get("effects", ()))
        for e in effects:
            if "target" not in e:
                raise GraphError(f"node {nid}: effect without target")
            if e["target"] == "airframe":
                from .catalogue import airframe_effect_errors

                errs = airframe_effect_errors(e)
                if errs or e.get("leg") == "key":  # a node has no trigger key
                    raise GraphError(f"node {nid}: {'; '.join(errs) or 'leg key needs a trigger key'}")
        nodes[nid] = Node(
            nid,
            n["subsystem"],
            float(n.get("threshold", 0.5)),
            n.get("gate", "or"),
            n.get("description", ""),
            effects,
        )
    edges = []
    seen = set()
    for e in doc["edges"]:
        eid = e["id"]
        if eid in seen:
            raise GraphError(f"duplicate edge id {eid}")
        seen.add(eid)
        for end in ("src", "dst"):
            if e[end] not in nodes:
                raise GraphError(f"edge {eid}: unknown {end} node {e[end]!r}")
        if e["type"] not in EDGE_TYPES:
            raise GraphError(f"edge {eid}: type {e['type']!r} not in {EDGE_TYPES}")
        if e["mechanism"] not in MECHANISMS:
            raise GraphError(f"edge {eid}: mechanism {e['mechanism']!r} not in {MECHANISMS}")
        tr = dict(e["transfer"])
        if tr.get("kind") not in TRANSFER_KINDS:
            raise GraphError(f"edge {eid}: transfer kind {tr.get('kind')!r} not in {TRANSFER_KINDS}")
        if tr["kind"] == "lag" and float(tr.get("tau_s", 0)) <= 0:
            raise GraphError(f"edge {eid}: lag needs tau_s > 0")
        lat = dict(e["latency"])
        if lat.get("dist") not in LATENCY_DISTS:
            raise GraphError(f"edge {eid}: latency dist {lat.get('dist')!r} not in {LATENCY_DISTS}")
        if lat["dist"] == "fixed" and float(lat["s"]) < 0:
            raise GraphError(f"edge {eid}: negative latency")
        if lat["dist"] != "fixed" and not 0 <= float(lat["lo"]) <= float(lat["hi"]):
            raise GraphError(f"edge {eid}: latency needs 0 <= lo <= hi")
        if lat["dist"] == "loguniform" and float(lat["lo"]) <= 0:
            raise GraphError(f"edge {eid}: log-uniform latency needs lo > 0")
        ev = e["evidence"]
        EvidenceTag.parse(ev["tag"])
        edges.append(
            Edge(eid, e["src"], e["dst"], e["type"], tr, lat, e["mechanism"], ev["source"], ev["tag"])
        )
    templates = {}
    for tid, t in doc.get("templates", {}).items():
        for n in (t["root"], *t["sequence"], *t.get("conditions", ())):
            if n not in nodes:
                raise GraphError(f"template {tid}: unknown node {n!r}")
        templates[tid] = Template(
            tid,
            t["name"],
            t["root"],
            tuple(t["sequence"]),
            {k: (float(v[0]), float(v[1])) for k, v in t["windows_s"].items()},
            tuple(t.get("conditions", ())),
            t["evidence"],
        )
    return FaultGraph(nodes, tuple(edges), templates)


@lru_cache(maxsize=4)
def load_graph(path: str | None = None) -> FaultGraph:
    """The typed graph from ``configs/tejas/faults/graph.yaml`` (validated)."""
    return _parse(load_yaml(Path(path) if path else GRAPH_PATH))


def parse_graph(doc: Mapping) -> FaultGraph:
    """Build a graph from an in-memory document (tests, alternative platforms)."""
    return _parse(doc)
