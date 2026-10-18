"""Model output for the Readiness cards and the Twin page (SHAPES.md: ``PHX_DATA.fleet[].card`` and the optional
``PHX_TWIN`` fields). Re-exported by ``triage``: ``readiness_cards(store, twin, t)``, ``twin_view(store, twin, t,
tail)``. The page (``assets/twin-view.js``) builds the tree, a default evidence lens and the strip from S1's
required fields; this module sends only what carries model output, each lens with its source label.

Lenses: ``status`` (twin state and the board), ``evidence`` (alarm reporter → suspects, from isolation),
``false_alarm`` (cnd), ``life`` (life), ``removal_risk`` (S3's hazard model, when its training worlds are built)
and ``engine_margin`` (S3's engine health on the run's overlay). A lens with no output keeps its source and says
why in its legend. Nodes, parts, positions and LRU names come from ``registry.yaml``.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml
from engines import cnd, isolation, life
from engines.common import MODELS, Context, context, ist, seq, text
from interfaces import DAY, SOURCE_LABEL, Source

HERE = Path(__file__).resolve().parent
SRC = {s: SOURCE_LABEL[s] for s in Source}
HEX = {"p1": "#D4492A", "accent": "#E8743B", "nmcs": "#D4492A", "nmcm": "#C98512", "nmcd": "#5B4FCF",
       "grey": "#C7C9CC", "muted": "#9AA0A8", "green": "#1F8A4C", "amber": "#C98512", "red": "#D4492A"}
BAND_TONE = {"P1": "p1", "P2": "accent", "P3": "accent", "P4": "nmcm"}


# ---- registry --------------------------------------------------------------------------------------------
class Registry:
    def __init__(self, path: Path = HERE / "registry.yaml") -> None:
        doc = yaml.safe_load(Path(path).read_text())
        if doc.get("format") != "phx.registry/1":
            raise ValueError("registry.yaml: unexpected format")
        self.systems: dict[str, str] = doc["systems"]
        self.nodes: dict[str, dict] = doc["nodes"]
        self.unplaced: dict[str, dict] = doc.get("unplaced", {})

    def node_of_lru(self, lru: str | None) -> str | None:
        return next((n for n, v in self.nodes.items() if lru in v["lrus"]), None)

    def nodes_of_lru(self, lru: str | None) -> list[str]:
        return [n for n, v in self.nodes.items() if lru in v["lrus"]]

    def node_of_slot(self, part_no: str | None, slot: int) -> str | None:
        return next((n for n, v in self.nodes.items() for p in v["parts"] if p["part_no"] == part_no and p["slot"] == slot), None)

    def nodes_of_part(self, part_no: str | None) -> list[str]:
        return [n for n, v in self.nodes.items() if any(p["part_no"] == part_no for p in v["parts"])]

    def position(self, part_no: str | None = None, slot: int = 1, lru: str | None = None) -> str | None:
        """Catalogue position for order parameters: of a part slot, or of the first node / item listing an LRU."""
        items = list(self.nodes.values()) + list(self.unplaced.values())
        if part_no is not None:
            return next((p["position"] for v in items for p in v["parts"] if p["part_no"] == part_no and p["slot"] == slot), None)
        v = next((v for v in items if lru in v["lrus"]), None)
        return v["parts"][0]["position"] if v and v["parts"] else None

    def zones_of_code(self, ctx: Context, code: str) -> list[str]:
        """Planform zones an alarm code points at: its top suspect LRU's node(s)."""
        o = ctx.occ[ctx.occ.event_code == code]
        if not len(o) or not seq(o.suspect_lrus.iloc[-1]):
            return []
        top = max(seq(o.suspect_lrus.iloc[-1]), key=lambda x: x["isolation_confidence"])["lru"]
        return [self.nodes[n]["zone"] for n in self.nodes_of_lru(top) if self.nodes[n]["zone"]]


@lru_cache(maxsize=1)
def registry() -> Registry:
    return Registry()


def _slot(position: str) -> tuple[str, int]:
    pn, _, k = position.rpartition("#")
    return pn, int(k) if k.isdigit() else 1


def fitted_nodes(ctx: Context, tail: str) -> dict[str, dict]:
    """node → {serial, part_no, since, inferred} for the serials the twin has fitted on the tail."""
    reg, out = registry(), {}
    for x in ctx.twin.installed(ctx.t, tail):
        pn, k = _slot(x.position)
        n = reg.node_of_slot(pn, k)
        if n and n not in out:
            out[n] = {"serial": x.serial_no, "part_no": pn, "since": ist(x.since), "inferred": x.inferred}
    return out


# ---- readiness cards -------------------------------------------------------------------------------------
def _zones(ctx: Context, f) -> list[str]:
    reg = registry()
    if f.kind == "alert":
        return reg.zones_of_code(ctx, f.code)
    return [reg.nodes[n]["zone"] for n in reg.nodes_of_part(f.part_no) if reg.nodes[n]["zone"]]


def readiness_cards(store, twin, t: int) -> dict[str, dict]:
    """``fleet[].card`` per tail from its top board issue, else from its state: {headline, detail, tone?, zones}."""
    import triage

    b = triage.evaluate(store, twin, t)
    ctx = context(store, twin, t)
    out = {}
    for tail in ctx.tails:
        state, since = ctx.state_now.get(tail, ("UNKNOWN", None))
        days = round((t - since) / DAY) if since else None
        top = next((i for i in b.issues if i.tail_no == tail), None)
        if state == "NMCD":
            us = ctx.unserviceable_jobs(tail)
            lat = ctx.latest
            roh = lat[(lat.tail_no == tail) & (lat.record_type == "INSPECTION") & lat.record_key.isin(us)]
            what = "overhaul" if len(roh) and (roh.inspection_type == "ROH").any() else "depot maintenance"
            out[tail] = {"headline": f"At depot for {what}", "detail": f"In depot {days} days", "tone": "nmcd", "zones": []}
            continue
        if top is not None:
            f = b.facts[top.issue_id]
            tone = "nmcs" if f.kind == "supply" else BAND_TONE.get(top.band, "accent")
            zones = [{"zone": z, "tone": tone} for z in _zones(ctx, f)]
            if f.kind == "life":
                unit = f.life_unit.rstrip("s")
                card = {"headline": f"{f.description.capitalize()} change due",
                        "detail": (f"Next {unit} is {f.life_used + 1:g} of {f.life_limit}" if f.life_left and f.life_left > 0
                                   else f"{f.life_used:g} of {f.life_limit} {f.life_unit} · change due")}
            elif f.kind == "supply":
                card = {"headline": f.title, "detail": f"Grounded {f.down_days:.0f} days", "tone": "nmcs"}
            elif f.gate == "G1":
                card = {"headline": f.title, "detail": f.reason.split(" · ")[0].replace("The same warning ", "").capitalize()}
            else:
                card = {"headline": f.title, "detail": f.reason}
            out[tail] = card | {"zones": zones}
            continue
        tl = ctx.tech_log.get(tail)
        deferred = []
        for part in text(tl.limitations_text if tl is not None else None).split(";"):
            if part.strip().startswith("DEFERRED:"):
                deferred += part.strip()[9:].split()
        watched = [m for m in b.monitoring if m.tail_no == tail]
        from triage import NUM

        if state in ("FMC", "PMCM", "PMCS"):
            head = "Flying normally" if state == "FMC" else "Partly mission capable"
        else:
            head = "In maintenance" if state.startswith("NMCM") else state
        if deferred:
            detail = f"{NUM.get(len(deferred), len(deferred)).capitalize()} defect{'s' if len(deferred) > 1 else ''} deferred"
        elif watched:
            detail = f"{len(watched)} issue{'s' if len(watched) > 1 else ''} being watched"
        else:
            detail = "No open issue"
        out[tail] = {"headline": head, "detail": detail, "zones": []}
    return out


# ---- twin lenses -----------------------------------------------------------------------------------------
def _model(name: str) -> str:
    mid, ver = MODELS[name]
    return f"{mid} {ver}"


def _lens_status(ctx: Context, b, tail: str) -> dict:
    reg = registry()
    paint = {}
    for m in b.monitoring:
        if m.tail_no == tail:
            for z in reg.zones_of_code(ctx, m.code):
                paint.setdefault(z, HEX["grey"])
    for i in reversed([i for i in b.issues if i.tail_no == tail]):  # the most urgent issue paints last
        f = b.facts[i.issue_id]
        tone = "nmcs" if f.kind == "supply" else BAND_TONE.get(i.band, "accent")
        for z in _zones(ctx, f):
            paint[z] = HEX[tone]
    return {"id": "status", "label": "Status", "icon": "target", "source": SRC[Source.FLEET], "model": _model("triage"),
            "paint": paint, "legend": [{"kind": "dot", "color": HEX["p1"], "text": "P1 or waiting for a part"},
                                       {"kind": "dot", "color": HEX["accent"], "text": "On today's board"},
                                       {"kind": "dot", "color": HEX["grey"], "text": "Being watched"}]}


def _top_alert(b, tail: str):
    on_board = [b.facts[i.issue_id] for i in b.issues if i.tail_no == tail and b.facts[i.issue_id].kind == "alert"]
    if on_board:
        return on_board[0]
    watched = [b.facts[m.issue_id] for m in b.monitoring if m.tail_no == tail and m.issue_id in b.facts]
    watched = [f for f in watched if f.kind == "alert"]
    return max(watched, key=lambda f: (f.consec, f.n_alerts), default=None)


def _lens_evidence(ctx: Context, b, tail: str, fitted: dict) -> tuple[dict, str | None]:
    reg = registry()
    lens = {"id": "evidence", "label": "Evidence", "icon": "link", "source": SRC[Source.FLEET], "model": _model("isolation"),
            "dim": True, "paint": {}, "arcs": [], "tags": [], "reporter": None}
    f = _top_alert(b, tail)
    iso = isolation.analyse(ctx, tail, f.code) if f else None
    if f is None or iso is None:
        lens["legend"] = [{"kind": "text", "text": "No open alarm issue on this tail"}]
        return lens, None
    o = ctx.occ[(ctx.occ.tail_no == tail) & (ctx.occ.event_code == f.code)]
    rep = reg.node_of_lru(o.source_lru.iloc[-1])
    flown = len(ctx.sorties(tail))
    fired = len(ctx.fired_sorties(tail, f.code) & set(ctx.sorties(tail).sortie_id))
    if rep:
        lens["reporter"] = rep
        lens["paint"][rep] = "reporter"
        lens["tags"].append({"node": rep, "kind": "rep", "k": "Reporter", "v": reg.nodes[rep]["label"],
                             "s": f"{f.code} · {fired} of {flown} sorties"})
    first = None
    for k, (lru, conf) in enumerate(sorted(iso.iso.items(), key=lambda x: -x[1])):
        node = reg.node_of_lru(lru)
        if not node:
            continue
        first = first or node
        lens["paint"][node] = "suspect" if k == 0 else "suspect2"
        if rep:
            lens["arcs"].append({"from": rep, "to": node, "weight": round(conf, 2)})
        kk, cc = iso.bench.get(lru, (0, 0))
        bench = f"{kk + cc} benched · {cc} confirmed" if kk + cc else "no removals on record"
        ser = fitted.get(node, {}).get("serial")
        lens["tags"].append({"node": node, "kind": "sus" if k == 0 else "sus2", "k": f"Suspect · {conf:g}",
                             "v": f"{reg.nodes[node]['label']}" + (f" · {ser}" if ser else ""),
                             "s": f"{bench} · posterior {iso.posterior[lru]:.2f}"})
    lens["legend"] = [{"kind": "dot", "color": "var(--wire)", "text": "Reporter"},
                      {"kind": "bar", "color": "var(--accent)", "text": "Suspect"},
                      {"kind": "text", "text": f"{f.code} · thickness = isolation confidence"}]
    return lens, first


def _lens_false_alarm(ctx: Context, b, tail: str) -> dict:
    reg = registry()
    paint, tags = {}, []
    codes = {b.facts[i.issue_id].code for i in (*b.issues, *b.monitoring)
             if i.tail_no == tail and i.issue_id in b.facts and b.facts[i.issue_id].kind == "alert"}
    for code in sorted(codes):
        r = cnd.code_rates(ctx, code)
        zones = reg.zones_of_code(ctx, code)
        if not zones or not r.labelled:
            continue
        p = r.p_confirmed
        for z in zones[:1]:
            paint[z] = HEX["muted"] if p[0] < 0.05 else HEX["accent"]
            tags.append({"node": z, "kind": "rep", "k": f"False alarm · {code}", "v": f"P(confirmed) {p[0]:.3f}",
                         "s": f"[{p[1]:.3f}, {p[2]:.3f}] · n = {r.labelled}"})
    lens = {"id": "false_alarm", "label": "False alarm", "icon": "scale", "source": SRC[Source.FLEET],
            "model": _model("cnd"), "paint": paint, "tags": tags}
    lens["legend"] = ([{"kind": "dot", "color": HEX["muted"], "text": "P(confirmed) < 0.05 · likely nuisance"},
                       {"kind": "dot", "color": HEX["accent"], "text": "≥ 0.05"}] if tags else
                      [{"kind": "text", "text": "No open alarm issue on this tail"}])
    return lens


def _lens_life(ctx: Context, tail: str) -> dict:
    reg = registry()
    paint, tags = {}, []
    for it in life.items(ctx):
        if it.tail_no != tail:
            continue
        frac = it.used / it.limit if it.limit else 0.0
        col = HEX["red"] if frac >= 0.85 else HEX["amber"] if frac >= 0.6 else HEX["green"]
        nodes = [n for n in reg.nodes_of_part(it.part_no)]
        for n in nodes:
            paint[n] = col
        if nodes:
            when = f"limit in {it.days_to_limit:g} d" if it.days_to_limit is not None and it.left > 0 else (
                "limit passed or change not on record" if it.left <= 0 else "not flying")
            tags.append({"node": nodes[-1], "kind": "rep", "k": f"Life · {it.label}", "v": f"{it.used:g} of {it.limit} {it.unit}",
                         "s": f"{it.left:g} left · {when}"})
    return {"id": "life", "label": "Life left", "icon": "tyre", "source": SRC[Source.FLEET], "model": _model("life"),
            "paint": paint, "tags": tags,
            "legend": [{"kind": "dot", "color": HEX["green"], "text": "< 60 % used"},
                       {"kind": "dot", "color": HEX["amber"], "text": "60–85 %"},
                       {"kind": "dot", "color": HEX["red"], "text": "> 85 %"}]}


def _hazard(ctx: Context) -> tuple[list, str | None]:
    """S3's removal-risk findings for the live fleet, or ([], why not)."""
    if "tv_hazard" not in ctx._memo:
        path = HERE.parent / "runs" / "train" / "hazard_model.json"
        try:
            from engines import hazard
        except Exception as e:  # noqa: BLE001 — S3's model is optional here
            ctx._memo["tv_hazard"] = ([], f"hazard model not importable ({type(e).__name__})")
        else:
            if not path.exists():
                ctx._memo["tv_hazard"] = ([], "INSUFFICIENT_EVIDENCE · the training worlds are not built yet")
            else:
                try:
                    ctx._memo["tv_hazard"] = (hazard.assess(ctx.store, ctx.t, hazard.HazardModel.from_json(path)), None)
                except Exception as e:  # noqa: BLE001
                    ctx._memo["tv_hazard"] = ([], f"hazard model failed ({type(e).__name__}: {e})")
    return ctx._memo["tv_hazard"]


def _risk_by_node(ctx: Context, tail: str, fitted: dict) -> dict[str, object]:
    """node → S3's removal-risk Belief for the serial fitted there (value None = INSUFFICIENT_EVIDENCE)."""
    fs, _ = _hazard(ctx)
    by_serial = {f.subject: f for f in fs if f.tail_no == tail and f.beliefs}
    return {node: by_serial[x["serial"]].beliefs[0] for node, x in fitted.items() if x["serial"] in by_serial}


def _champion(b) -> str | None:
    """The champion line S3's model writes into every sufficient belief's note ("champion: … (held-out Brier …)")."""
    m = re.search(r"champion: (.+?)(?:; age |$)", b.note or "")
    return f"{b.model_id} {b.model_version} — champion: {m.group(1)}" if m else None


def _horizon(b) -> str:
    m = re.search(r"next ([\d.]+) FH", b.note or "")
    return f"next {float(m.group(1)):.0f} FH" if m else "next 30 days"


def _p(x: float) -> str:
    """A probability with two decimals, three when it is below 0.01 (a new serial's risk is not zero)."""
    return f"{x:.3f}" if x < 0.01 else f"{x:.2f}"


def _risk_row(b) -> dict:
    return {"k": f"Removal risk · {_horizon(b)}", "v": _p(b.value),
            **({"ci": f"[{_p(b.lo)}, {_p(b.hi)}]"} if b.lo is not None and b.hi is not None else {}),
            "source": SRC[Source.TRAIN], "note": "80 % interval"}


def _lens_removal_risk(ctx: Context, tail: str, fitted: dict) -> dict:
    lens = {"id": "removal_risk", "label": "Removal risk", "icon": "wrench", "source": SRC[Source.TRAIN],
            "model": "hazard (Weibull AFT)", "paint": {}, "tags": []}
    fs, why = _hazard(ctx)
    by_serial = {f.subject: f for f in fs if f.tail_no == tail}
    insufficient = 0
    for node, x in fitted.items():
        f = by_serial.get(x["serial"])
        if f is None or not f.beliefs:
            continue
        b0 = f.beliefs[0]
        lens["model"] = f"{b0.model_id} {b0.model_version}"
        if b0.value is None:
            insufficient += 1
            continue
        lens["paint"][node] = HEX["red"] if b0.value >= 0.2 else HEX["amber"] if b0.value >= 0.05 else HEX["green"]
        lens["tags"].append({"node": node, "kind": "rep", "k": f"Removal risk · {_horizon(b0)}", "v": _p(b0.value),
                             "s": f"[{_p(b0.lo)}, {_p(b0.hi)}] · {x['serial']}" if b0.lo is not None else x["serial"]})
    champ = next((c for f in fs for c in [_champion(f.beliefs[0])] if f.beliefs and c), None)
    if why:
        lens["legend"] = [{"kind": "text", "text": why}]
    elif not lens["tags"]:
        lens["legend"] = [{"kind": "text", "text": f"INSUFFICIENT_EVIDENCE · {insufficient} fitted classes under 10 confirmed removals"}]
    else:
        lens["legend"] = [{"kind": "dot", "color": HEX["green"], "text": "< 0.05"}, {"kind": "dot", "color": HEX["amber"], "text": "0.05–0.2"},
                          {"kind": "dot", "color": HEX["red"], "text": "≥ 0.2"},
                          {"kind": "text", "text": f"Other classes: INSUFFICIENT_EVIDENCE ({insufficient} fitted here)"}]
    if champ and not why:
        lens["legend"].append({"kind": "text", "text": champ})
    return lens


def _lens_engine_margin(ctx: Context, tail: str) -> dict:
    lens = {"id": "engine_margin", "label": "Engine margin", "icon": "engine", "source": SRC[Source.OVERLAY],
            "model": "engine health (Kalman)", "paint": {}, "tags": []}
    if "tv_engine" not in ctx._memo:
        try:
            from engines import engine_health

            ctx._memo["tv_engine"] = (engine_health.assess(ctx.store, ctx.t), None)
        except Exception as e:  # noqa: BLE001 — S3's model is optional here
            ctx._memo["tv_engine"] = ([], f"engine health not available ({type(e).__name__})")
    fs, why = ctx._memo["tv_engine"]
    f = next((x for x in fs if x.tail_no == tail), None)
    if f is None:
        lens["legend"] = [{"kind": "text", "text": why or "No engine trend for this run"}]
        return lens
    bel = {b.name: b for b in f.beliefs}
    m, tr, dl = bel.get("egt_margin_c"), bel.get("egt_margin_trend_c_per_10efh"), bel.get("days_to_margin_limit_p10")
    alert = any(bel.get(k) and bel[k].value for k in ("egt_step_alert", "egt_trend_alert"))
    lens["model"] = f"{f.beliefs[0].model_id} {f.beliefs[0].model_version}"
    lens["paint"]["ENGINE"] = HEX["red"] if alert else HEX["amber"] if m and m.value is not None and m.value < 30 else HEX["green"]
    lens["tags"].append({"node": "ENGINE", "kind": "rep", "k": f"EGT margin · {f.subject}",
                         "v": f"{m.value:.0f} °C" if m and m.value is not None else "—",
                         "s": (f"trend {tr.value:+.1f} °C / 10 EFH" if tr and tr.value is not None else "")
                              + (f" · limit p10 {dl.value:.0f} d" if dl and dl.value is not None else "")
                              + (" · alert" if alert else "")})
    lens["legend"] = [{"kind": "dot", "color": HEX["green"], "text": "Margin holding"}, {"kind": "dot", "color": HEX["amber"], "text": "< 30 °C"},
                      {"kind": "dot", "color": HEX["red"], "text": "Step or trend alert"}]
    return lens


# ---- panel, insight, strip -------------------------------------------------------------------------------
def _panel(ctx: Context, b, f, node: str, fitted: dict) -> dict:
    from policies import candidate_order_id, policies

    reg = registry()
    r = cnd.code_rates(ctx, f.code)
    iso = isolation.analyse(ctx, f.tail_no, f.code)
    x = fitted.get(node, {})
    hist = cnd.issue_history(ctx, f.tail_no, f.code)
    lru = next((h for h in iso.iso if reg.node_of_lru(h) == node), None) if iso else None
    comp = iso.posterior.get(lru, 0.0) if iso and lru else None
    ind = iso.posterior.get("IND") if iso else None
    status_v = f"standing · {f.consec} flights" if f.consec >= 2 else f.reason
    pan = {
        "title": reg.nodes[node]["label"], "serial": x.get("serial"), "inferred": bool(x.get("inferred")),
        "note": ("Install record not yet ingested — position taken from a job" if x.get("inferred") else
                 (f"Installed {x['since']}" if x.get("since") else "")),
        "tiers": ["DIAG", "PRED", "PRESC"],
        "status": {"pill": ctx.state_now.get(f.tail_no, ("UNKNOWN", None))[0],
                   "kv": [{"k": "Open issue", "code": f.code, "v": status_v},
                          {"k": f"{f.tail_no} effort on {f.code}", "v": f"{hist['jobs']} jobs · {hist['man_hours']:,.0f} man-h", "num": True}]},
        "assessment": {
            "scope": f"fleet · {r.jobs} {f.code} jobs", "confirmed": f"{r.confirmed} confirmed",
            "bar": [{"n": r.no_fault, "tone": "ink-4", "label": f"{r.no_fault} CND"},
                    {"n": r.removed, "tone": "accent", "label": f"{r.removed} removed → {r.units_rtok} RTOK"}]
                   + ([{"n": r.ts, "tone": "ink", "label": f"{r.ts} TS"}] if r.ts else []),
            "kv": [{"k": "P(confirmed fault)", "v": f"{r.p_confirmed[0]:.3f}", "ci": f"[{r.p_confirmed[1]:.3f}, {r.p_confirmed[2]:.3f}]"}],
            "verdict": [{"label": "Component", "value": "—" if comp is None else ("Likely" if comp >= 0.5 else "Possible" if comp >= 0.1 else "Unlikely"),
                         "on": bool(comp is not None and comp >= 0.5)},
                        {"label": "Indication path", "value": "—" if ind is None else ("Likely" if ind >= 0.5 else "Possible" if ind >= 0.1 else "Unlikely"),
                         "on": bool(ind is not None and ind >= 0.5)},
                        {"label": "Undetermined", "value": "—" if "UNDETERMINED" not in (iso.posterior if iso else {}) else f"{iso.posterior['UNDETERMINED']:.2f}"}],
        },
        "foot": [f"snapshot {ist(ctx.t, '%H:%M')} · {ctx.store.snapshot_id(ctx.t)[:8]}… · {_model('cnd')}",
                 f"policy {policies().version['P-DEC-01']} · contract a4396f1d"],
    }
    if r.p_rtok is not None:
        part = iso.labels.get(lru, "unit") if iso and lru else "unit"
        pan["projection"] = {"kv": [{"k": "If removed again · P(RTOK)", "v": f"{r.p_rtok[0]:.3f}", "ci": f"[{r.p_rtok[1]:.2f}, {r.p_rtok[2]:.2f}]"},
                                    {"k": f"Shop history, {part}s", "v": f"{r.units_rtok} / {r.units_benched} RTOK", "num": True}]}
    orders = [c for c in b.orders if c.issue_id == f.issue_id]
    if orders:
        what = {"TROUBLESHOOT": lambda c: f"TROUBLESHOOT {c.parameters.get('code') or c.parameters.get('position')}",
                "CHANGE_MONITORING_CONFIG": lambda c: "CHANGE_MONITORING_CONFIG"}
        pan["recommended"] = {"basis": f.basis, "items": [
            {"action": what.get(c.action, lambda c: c.action)(c), "authority": c.authority.value, "label": c.authority.value,
             "icon": True, "order_id": candidate_order_id(c, ctx.t),
             **({"note": "Draft only · engineering officer signs"} if c.authority.value == "HUMAN" else {})} for c in orders]}
    return pan


def _strip(ctx: Context, f, part_no: str | None, label: str) -> dict:
    from engines.drift import _week0

    t0 = _week0(ctx)
    day = lambda x: round((int(x) - t0) / DAY, 3)
    av = ctx.availability[ctx.availability.tail_no == f.tail_no]
    fired = ctx.fired_sorties(f.tail_no, f.code)
    so = ctx.sorties(f.tail_no)
    events = ctx.removal_events(f.tail_no, part_no) if part_no else []
    return {"t0": ist(t0, "%Y-%m-%d"), "T": round((ctx.t - t0) / DAY, 3),
            "state": [[day(x), s] for x, s in zip(av.t_event, av.availability_state, strict=True)],
            "sorties": [[day(x), int(s in fired)] for x, s in zip(so.t_event, so.sortie_id, strict=True)],
            "removals": [[day(e["t"]), e["removed"]] for e in events], "marks": [],
            "asof_label": ist(ctx.t, "%d %b %H:%M"),
            "labels": {"sorties": f"Sorties · {f.code}", "removals": f"{label[:1].upper()}{label[1:]} removals" if part_no else "Removals"}}


def twin_view(store, twin, t: int, tail: str) -> dict | None:
    """Optional ``PHX_TWIN`` fields with model output: lenses, selected node and lens, panels, insight, strip."""
    import triage

    ctx = context(store, twin, t)
    if tail not in ctx.tails:
        return None
    b = triage.evaluate(store, twin, t)
    fitted = fitted_nodes(ctx, tail)
    evid, first = _lens_evidence(ctx, b, tail, fitted)
    lenses = [_lens_status(ctx, b, tail), evid, _lens_false_alarm(ctx, b, tail), _lens_life(ctx, tail),
              _lens_removal_risk(ctx, tail, fitted), _lens_engine_margin(ctx, tail)]
    out: dict = {"lenses": lenses, "lens": "evidence" if first else "status", "panels": {}, "insight": None, "strip": None}
    if first:
        out["selected"] = first
    f = _top_alert(b, tail)
    if f is not None and first:
        out["panels"][first] = _panel(ctx, b, f, first, fitted)
        iso = isolation.analyse(ctx, tail, f.code)
        lru = next((h for h, p in iso.parts.items() if p), None) if iso else None
        part_no = iso.parts.get(lru) if lru else None
        label = iso.labels.get(lru, "unit") if lru else "unit"
        out["strip"] = _strip(ctx, f, part_no, label)
        from policies import prefs

        if part_no and f.removals >= 2 and f.confirmed == 0 and f.consec >= prefs()["standing_flights"]:
            from triage import _chain

            seq, _ = _chain(ctx, tail, part_no)
            so = ctx.sorties(tail)
            fired = ctx.fired_sorties(tail, f.code)
            n_fired = sum(s in fired for s in so.sortie_id)
            out["insight"] = {
                "label": "Sensor vs component",
                "title": f"The alarm stayed with the aircraft through {f.removals} {label} removals.",
                "text": (f"{f.code} fired on {n_fired} of {len(so)} {tail} sorties while {len({s for _, s in seq})} different "
                         f"{label} serials rotated through that position. The evidence follows the tail, not the {label}."),
                "swaps": [bool(s in fired) for s in so.sortie_id]}
    risk = _risk_by_node(ctx, tail, fitted)
    for node, bel in risk.items():
        if bel.value is None:
            continue
        pan = out["panels"].get(node)
        if pan is None:
            x = fitted[node]
            pan = out["panels"][node] = {
                "title": registry().nodes[node]["label"], "serial": x["serial"], "inferred": bool(x["inferred"]),
                "note": ("Install record not yet ingested — position taken from a job" if x["inferred"] else
                         (f"Installed {x['since']}" if x.get("since") else "")),
                "tiers": ["PRED"], "status": {"pill": ctx.state_now.get(tail, ("UNKNOWN", None))[0],
                                              "kv": [{"k": "Open issue", "v": "none on this component"}]},
                "foot": [f"snapshot {ist(ctx.t, '%H:%M')} · {ctx.store.snapshot_id(ctx.t)[:8]}…", "contract a4396f1d"]}
        if "PRED" not in pan["tiers"]:
            pan["tiers"].append("PRED")
        pan.setdefault("projection", {"kv": []})["kv"].append(_risk_row(bel))
        pan["foot"] = [*pan.get("foot", []), f"removal risk: {bel.model_id} {bel.model_version} · {SRC[Source.TRAIN]}"]
    return out
