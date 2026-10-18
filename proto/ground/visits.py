"""Visitor log for the public prototype: who opened the app, what they looked at and what they tried.

Kept apart from the decision system's hash-chained event log (nothing here is a decision record). Every screen
load and every action (approve, sign, advance the day, verify, replay, draft) is written to a small SQLite file,
grouped by an anonymous browser id cookie; ``shell.js`` adds a beacon with screen size and time on page.

The report is a read-only page at ``/ops/<token>`` (no buttons; it refreshes itself). The token lives only on the
server in ``$PHX_HOME/visits.token`` (created on first start), so the link is not guessable from this repository.
Optional ``$PHX_HOME/visits.team`` lists ``<ip> <label>`` lines to mark the team's own addresses.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import secrets
import socket
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
HOME = Path(os.environ.get("PHX_HOME", Path.home() / "phalanx"))
DB = Path(os.environ.get("PHX_VISITS_DB", HOME / "visits.db"))
COOKIE = "phx_vid"
SCREENS = {
    "readiness": "Readiness", "decisions": "Decisions", "decision": "Recommendation", "decision-why": "Why",
    "workbench": "Workbench", "twin": "Aircraft twin", "epoch": "Orders / epoch", "provenance": "Provenance",
    "policies": "Policies", "policies-authority": "Authority", "policies-lifecycle": "Policy lifecycle",
    "assurance": "Assurance", "assurance-backtest": "Backtest", "assurance-drift": "Drift", "insights": "Insights",
    "insights-nff": "No-fault-found", "insights-integrity": "Integrity", "spares": "Spares",
    "spares-leadtime": "Lead times", "plan": "Plan", "plan-schedule": "Schedule", "data": "Data",
    "data-ingest": "Ingest", "data-telemetry": "Telemetry", "assistant": "Assistant",
}
ACTIONS = [  # (method, path regex, label)
    ("POST", r"^/api/issues/[^/]+/decision$", "decided on a recommendation"),
    ("POST", r"^/api/orders/.+/sign$", "signed an order"),
    ("POST", r"^/api/epoch/advance$", "advanced the day"),
    ("POST", r"^/api/epoch/autoplay$", "ran autoplay"),
    ("POST", r"^/api/workbench/[^/]+/draft$", "drafted an order"),
    ("POST", r"^/api/provenance/verify$", "verified the hash chain"),
    ("POST", r"^/api/provenance/replay$", "replayed a decision"),
    ("POST", r"^/api/refresh$", "refreshed data"),
    ("GET", r"^/api/search$", "searched"),
]
BOT = re.compile(r"^$|\(\+?https?://|research|zgrab|masscan|nmap|nuclei|censys|shodan|expanse|bot|crawl|spider|slurp|curl|wget|python|httpx|go-http|java/|headless|check-host|uptime|monitor|"
                 r"scan|preview|facebookexternalhit|whatsapp|telegram|discord|slack|lighthouse|pingdom", re.I)

_lock = threading.Lock()
_rdns: dict[str, str] = {}
_pool = ThreadPoolExecutor(4)


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=5, check_same_thread=False)
    c.execute("""CREATE TABLE IF NOT EXISTS hits (t REAL, vid TEXT, ip TEXT, ua TEXT, kind TEXT, path TEXT,
                 detail TEXT, ref TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS hits_vid ON hits(vid)")
    return c


_conn = _db()


def token() -> str:
    f = HOME / "visits.token"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(12) + "\n")
        f.chmod(0o600)
    return f.read_text().strip()


def _team() -> dict[str, str]:
    f = HOME / "visits.team"
    out = {}
    if f.exists():
        for ln in f.read_text().splitlines():
            p = ln.split(None, 1)
            if p and not ln.startswith("#"):
                out[p[0]] = p[1] if len(p) > 1 else "team"
    return out


def _ip(req: Request) -> str:
    xff = req.headers.get("x-forwarded-for", "")
    return (xff.split(",")[0].strip() if xff else "") or (req.client.host if req.client else "")


def _log(vid, ip, ua, kind, path, detail="", ref=""):
    with _lock:
        _conn.execute("INSERT INTO hits VALUES (?,?,?,?,?,?,?,?)", (time.time(), vid, ip, ua[:400], kind, path[:300],
                                                                     detail[:600], ref[:300]))
        _conn.commit()


def install(app: FastAPI) -> str:
    tok = token()

    @app.middleware("http")
    async def _visits(req: Request, call_next):
        path, method = req.url.path, req.method
        resp: Response = await call_next(req)
        if path.startswith("/ops/") or path == "/api/_v":
            return resp
        vid = req.cookies.get(COOKIE)
        page = path.endswith(".html") or path == "/"
        action = next((lab for m, rx, lab in ACTIONS if m == method and re.match(rx, path)), None)
        if page and method == "GET":
            if not vid:
                vid = secrets.token_hex(6)
                resp.set_cookie(COOKIE, vid, max_age=3600 * 24 * 365, samesite="lax", httponly=False)
            _log(vid, _ip(req), req.headers.get("user-agent", ""), "page", path + (f"?{req.url.query}" if req.url.query else ""),
                 ref=req.headers.get("referer", ""))
        elif action:
            _log(vid or "-", _ip(req), req.headers.get("user-agent", ""), "action", path, action)
        return resp

    @app.post("/api/_v", include_in_schema=False)
    async def _beacon(req: Request):
        try:
            body = json.loads((await req.body())[:2000] or b"{}")
        except ValueError:
            body = {}
        _log(req.cookies.get(COOKIE, "-"), _ip(req), req.headers.get("user-agent", ""), "beacon",
             str(body.get("page", ""))[:200], json.dumps({k: body.get(k) for k in ("ms", "w", "h", "tz", "lang", "ev")}))
        return Response(status_code=204)

    @app.get("/ops/{tok}", include_in_schema=False)
    def _report(tok: str, format: str = ""):
        if not secrets.compare_digest(tok, token()):
            return Response(status_code=404)
        data = summary()
        if format == "json":
            return JSONResponse(data)
        return HTMLResponse(render(data), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})

    return tok


# ------------------------------------------------------------------------------------------------ analysis
def _device(ua: str) -> str:
    if BOT.search(ua):
        return "automated"
    os_ = next((n for rx, n in [(r"iPhone", "iPhone"), (r"iPad", "iPad"), (r"Android.*Mobile", "Android phone"),
                                (r"Android", "Android tablet"), (r"Windows", "Windows"), (r"Mac OS X", "Mac"),
                                (r"CrOS", "ChromeOS"), (r"Linux", "Linux")] if re.search(rx, ua)), "other")
    br = next((n for rx, n in [(r"Edg/", "Edge"), (r"OPR/", "Opera"), (r"SamsungBrowser", "Samsung"),
                               (r"Firefox/", "Firefox"), (r"Chrome/", "Chrome"), (r"Safari/", "Safari")] if re.search(rx, ua)), "")
    return f"{br} · {os_}" if br else os_


def _rev(ip: str) -> str:
    if ip in _rdns:
        return _rdns[ip]
    _rdns[ip] = ""
    def look():
        try:
            _rdns[ip] = socket.gethostbyaddr(ip)[0]
        except (OSError, UnicodeError):
            _rdns[ip] = ""
    _pool.submit(look)
    return ""


def _ist(t: float) -> str:
    return dt.datetime.fromtimestamp(t, IST).strftime("%d %b %H:%M")


def summary() -> dict:
    with _lock:
        rows = _conn.execute("SELECT t, vid, ip, ua, kind, path, detail, ref FROM hits ORDER BY t").fetchall()
    team = _team()
    vis: dict[str, dict] = {}
    for t, vid, ip, ua, kind, path, detail, ref in rows:
        if vid == "-":   # an action or beacon without a cookie: attach to the latest visitor from the same address
            vid = next((k for k, v in reversed(list(vis.items())) if v["ip"] == ip), f"ip:{ip}")
        v = vis.setdefault(vid, {"vid": vid, "ip": ip, "ua": ua, "first": t, "last": t, "pages": 0, "screens": set(),
                                 "actions": [], "ms": 0, "screen": "", "tz": "", "ref": "", "ips": set()})
        v["last"] = max(v["last"], t); v["ips"].add(ip)
        if kind == "page":
            v["pages"] += 1
            name = path.split("?")[0].strip("/").removesuffix(".html") or "readiness"
            v["screens"].add(SCREENS.get(name, name))
            if ref and not v["ref"] and "148.100.99.205" not in ref and "148-100-99-205" not in ref:
                v["ref"] = ref
        elif kind == "action":
            v["actions"].append(detail)
        elif kind == "beacon":
            try:
                b = json.loads(detail)
            except ValueError:
                b = {}
            v["ms"] += int(b.get("ms") or 0)
            if b.get("w"):
                v["screen"] = f'{b["w"]}×{b["h"]}'
            v["tz"] = b.get("tz") or v["tz"]
    out = []
    for v in vis.values():
        dev = _device(v["ua"])
        span_min = (v["last"] - v["first"]) / 60
        active_min = max(v["ms"] / 60000, 0)
        n_scr, n_act = len(v["screens"]), len(v["actions"])
        who = team.get(v["ip"]) or ("automated" if dev == "automated" else "")
        if who == "automated":
            verdict = "automated"
        elif n_act >= 1 and n_scr >= 4 or n_scr >= 6 and max(span_min, active_min) >= 3:
            verdict = "evaluated"
        elif n_scr >= 3:
            verdict = "explored"
        else:
            verdict = "glanced"
        out.append({"vid": v["vid"], "ip": v["ip"], "host": _rev(v["ip"]), "device": dev, "who": who,
                    "first": v["first"], "last": v["last"], "first_ist": _ist(v["first"]), "last_ist": _ist(v["last"]),
                    "pages": v["pages"], "screens": sorted(v["screens"]), "actions": v["actions"],
                    "span_min": round(span_min, 1), "active_min": round(active_min, 1), "screen": v["screen"],
                    "tz": v["tz"], "ref": v["ref"], "verdict": verdict, "ua": v["ua"]})
    out.sort(key=lambda r: -r["last"])
    people = [r for r in out if r["verdict"] != "automated" and not (r["who"] and r["who"] != "automated")]
    feed = [{"t": _ist(t), "vid": vid, "ip": ip, "kind": kind, "path": path, "detail": detail}
            for t, vid, ip, ua, kind, path, detail, ref in rows[-150:] if kind != "beacon"][::-1]
    return {"generated": _ist(time.time()), "visitors": out, "feed": feed,
            "counts": {"outside_visitors": len(people), "evaluated": sum(r["verdict"] == "evaluated" for r in people),
                       "explored": sum(r["verdict"] == "explored" for r in people),
                       "team": sum(1 for r in out if r["who"] and r["who"] != "automated"),
                       "automated": sum(r["verdict"] == "automated" for r in out), "hits": len(rows)}}


# ------------------------------------------------------------------------------------------------ page
def render(d: dict) -> str:
    e = lambda s: html.escape(str(s or ""))
    c = d["counts"]
    ev = [r for r in d["visitors"] if r["verdict"] == "evaluated" and not r["who"]]
    if ev:
        r = ev[0]
        head = (f'<div class="hero ok"><b>Yes — evaluated.</b> Latest in-depth session {e(r["last_ist"])} IST from '
                f'{e(r["ip"])}{" (" + e(r["host"]) + ")" if r["host"] else ""}: {len(r["screens"])} screens, '
                f'{len(r["actions"])} actions, {r["span_min"]:.0f} min.</div>')
    elif c["outside_visitors"]:
        head = '<div class="hero warn"><b>Visited, not yet evaluated in depth.</b> Outside visitors have opened the app but none has explored six or more screens or tried an action.</div>'
    else:
        head = '<div class="hero"><b>No outside visitors yet.</b> This page refreshes every minute.</div>'
    tag = {"evaluated": "ok", "explored": "acc", "glanced": "grey", "automated": "grey"}
    cards = []
    for r in d["visitors"]:
        who = r["who"] or ("" if r["verdict"] != "automated" else "automated")
        cards.append(f"""<div class="v {'dim' if r['who'] or r['verdict'] == 'automated' else ''}">
  <div class="vt"><span class="tag {tag[r['verdict']]}">{e(r['verdict'])}</span>{f'<span class="tag grey">{e(who)}</span>' if who and who != 'automated' else ''}
    <b class="mono">{e(r['ip'])}</b><span class="m">{e(r['host'])}</span></div>
  <div class="vg">
    <span>When</span><span>{e(r['first_ist'])} → {e(r['last_ist'])} IST · {r['span_min']:.0f} min{f" · {r['active_min']:.0f} min on page" if r['active_min'] else ''}</span>
    <span>Device</span><span>{e(r['device'])}{' · ' + e(r['screen']) if r['screen'] else ''}{' · ' + e(r['tz']) if r['tz'] else ''}</span>
    <span>Screens</span><span>{len(r['screens'])} — {e(', '.join(r['screens']))} ({r['pages']} page loads)</span>
    <span>Actions</span><span>{e(', '.join(dict.fromkeys(r['actions']))) or '—'}</span>
    {f"<span>Came from</span><span>{e(r['ref'])}</span>" if r['ref'] else ''}
  </div></div>""")
    feed = "".join(f'<tr><td class="mono">{e(f["t"])}</td><td class="mono">{e(f["ip"])}</td><td>{e(f["kind"])}</td>'
                   f'<td class="mono">{e(f["path"])}</td><td>{e(f["detail"])}</td></tr>' for f in d["feed"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60"><meta name="robots" content="noindex"><title>Visitors — Phalanx Twin</title>
<style>
@font-face{{font-family:Manrope;src:url(/assets/fonts/Manrope-var-latin.woff2) format('woff2');font-weight:200 800}}
@font-face{{font-family:JBM;src:url(/assets/fonts/JetBrainsMono-var-latin.woff2) format('woff2');font-weight:100 800}}
:root{{--ink:#0B0D10;--ink3:#62676F;--ink4:#8E939A;--line:#E6E6E2;--bg2:#F7F7F5;--acc:#E8743B;--ok:#1F8A4C}}
*{{box-sizing:border-box;margin:0}} body{{font-family:Manrope,system-ui,sans-serif;color:var(--ink);background:#fff;padding:32px 20px 60px;max-width:1100px;margin:0 auto;font-size:15px;line-height:1.45}}
.mono{{font-family:JBM,ui-monospace,monospace;font-size:.92em}} h1{{font-size:28px;letter-spacing:-.02em}} .sub{{color:var(--ink3);margin:4px 0 22px}}
.k{{font-size:12px;font-weight:700;letter-spacing:.14em;color:var(--acc);text-transform:uppercase}}
.hero{{border-radius:16px;padding:18px 20px;background:var(--bg2);margin-bottom:20px}} .hero.ok{{background:#EAF6EF;color:#17693A}} .hero.warn{{background:#FDF6E8;color:#8A5A12}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:28px}}
.s{{border:1px solid var(--line);border-radius:14px;padding:14px 16px}} .s b{{font-size:30px;letter-spacing:-.03em;display:block}} .s span{{color:var(--ink3);font-size:13px}}
.v{{border:1px solid var(--line);border-radius:16px;padding:16px 18px;margin-bottom:12px}} .v.dim{{opacity:.6}}
.vt{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}} .vt .m{{color:var(--ink4);font-size:13px}}
.vg{{display:grid;grid-template-columns:110px 1fr;gap:4px 12px;font-size:14px}} .vg span:nth-child(odd){{color:var(--ink4)}} .vg span{{overflow-wrap:anywhere}}
.tag{{font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;border-radius:7px;padding:3px 8px;background:var(--bg2);color:var(--ink3)}}
.tag.ok{{background:#EAF6EF;color:var(--ok)}} .tag.acc{{background:#FDF1EA;color:#B4511F}}
h2{{font-size:18px;margin:34px 0 12px}} .feed{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:13px}}
td{{border-top:1px solid var(--line);padding:7px 8px;vertical-align:top;white-space:nowrap}} td:last-child{{white-space:normal}}
@media (max-width:600px){{.vg{{grid-template-columns:1fr}} .vg span:nth-child(odd){{margin-top:6px}}}}
</style></head><body>
<div class="k">Phalanx Twin · visitor log</div><h1>Who opened the prototype</h1>
<div class="sub">https://148.100.99.205 · updated {e(d['generated'])} IST · refreshes every minute · times in IST</div>
{head}
<div class="stats"><div class="s"><b>{c['outside_visitors']}</b><span>outside visitors</span></div>
<div class="s"><b>{c['evaluated']}</b><span>evaluated in depth</span></div><div class="s"><b>{c['explored']}</b><span>explored (3+ screens)</span></div>
<div class="s"><b>{c['team']}</b><span>team visitors</span></div><div class="s"><b>{c['automated']}</b><span>automated / link previews</span></div>
<div class="s"><b>{c['hits']}</b><span>events logged</span></div></div>
<p class="sub">"Evaluated" means at least 6 screens over 3+ minutes, or at least one action (approve, sign, advance the day, verify, replay) with 4+ screens. One card per browser.</p>
{''.join(cards) or '<p class="sub">Nothing logged yet.</p>'}
<h2>Latest events</h2><div class="feed"><table>{feed}</table></div>
</body></html>"""
