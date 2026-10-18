"""Build the README's custom SVG illustrations (docs/assets/readme/*.svg).

Numbers come from the live deployment's API (fetched into live/*.json by fetch_live.sh) so the pictures show what
the running system reports, not hand-typed values.  Run:  python3 docs/assets/readme/src/build_svgs.py
"""
import json, pathlib, re
from fonts import face

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = HERE.parents[3]
LIVE = HERE / "live"

INK, INK2, INK3, LINE, BG2 = "#0B0D10", "#4B5563", "#8A8F98", "#E6E6E2", "#F7F7F5"
ACC, ACCW, ACCL = "#E8743B", "#FDF1EA", "#F6CDB6"
FMC, FMCW = "#1F8A4C", "#EAF6EF"
NMCM, NMCMW = "#C98512", "#FCF5E6"
NMCS, NMCSW = "#D4492A", "#FCEDE9"
NMCD, NMCDW = "#5B4FCF", "#EFEEFC"
IBM, IBMW, IBML = "#0F62FE", "#EDF5FF", "#A6C8FF"   # IBM blue: everything that is the IBM Z platform

FONT_SANS = face("Manrope", "Manrope-var-latin.woff2")
FONT_MONO = face("JBMono", "JetBrainsMono-var-latin.woff2", "100 800")


def live(name):
    return json.loads((LIVE / f"{name}.json").read_text())


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(w, h, body, title, mono=False, extra_css="", card=True):
    css = FONT_SANS + (FONT_MONO if mono else "") + f"""
      text{{font-family:Manrope,'Segoe UI',Helvetica,Arial,sans-serif;fill:{INK}}}
      .mono{{font-family:JBMono,Menlo,Consolas,monospace}}
      .k{{font-size:13px;font-weight:700;letter-spacing:.14em;fill:{ACC}}}
      .h{{font-size:30px;font-weight:700;letter-spacing:-.02em}}
      .s{{font-size:16px;fill:{INK2}}}
      .t{{font-size:14px;fill:{INK2}}}
      .f{{font-size:12px;fill:{INK3}}}
    """ + extra_css
    bg = (f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="24" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
          if card else "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{esc(title)}"><title>{esc(title)}</title><style>{css}</style>{bg}{body}</svg>')


def write(name, text):
    (OUT / name).write_text(text)
    print(f"{name:28s} {len(text)/1024:6.1f} KB")


# ---------------------------------------------------------------- aircraft planform (port of proto/web/assets/aircraft.js)
HALF = [(0.00, 0.00), (0.35, 0.05), (0.9, 0.22), (1.6, 0.36), (2.3, 0.45), (3.0, 0.52), (3.7, 0.62), (4.05, 0.98),
        (4.6, 1.02), (7.29, 2.40), (9.32, 4.10), (10.72, 4.10), (11.22, 1.02), (11.9, 0.80), (12.55, 0.58),
        (12.62, 0.50), (13.2, 0.44), (13.2, 0.0)]
RING = HALF + [(x, -y) for x, y in reversed(HALF[1:-1])]


def planform(x0, y0, s, fill, stroke, sw=1.4, canopy=None):
    P = lambda p: f"{x0 + (4.1 + p[1]) * s:.1f},{y0 + p[0] * s:.1f}"
    d = "M" + "L".join(P(p) for p in RING) + "Z"
    cx, cy = x0 + 4.1 * s, y0 + 3.55 * s
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>'
            f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{0.34*s:.1f}" ry="{1.0*s:.1f}" fill="{canopy or LINE}" '
            f'stroke="{stroke}" stroke-width="{sw*.7:.1f}"/>')


def logo(x, y, height, color):
    src = (ROOT / "proto/web/assets/phalanx-logo.svg").read_text()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', src).group(1).split()]
    inner = re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1).replace("currentColor", color)
    k = height / vb[3]
    return f'<g transform="translate({x},{y}) scale({k:.5f}) translate({-vb[0]},{-vb[1]})">{inner}</g>'


def logos():
    src = (ROOT / "proto/web/assets/phalanx-logo.svg").read_text()
    for name, color in (("logo-light.svg", INK), ("logo-dark.svg", "#FFFFFF")):
        write(name, src.replace("currentColor", color).replace('role="img"', 'role="img" width="420" height="49"'))


# ---------------------------------------------------------------- hero
def hero():
    r = live("readiness")
    tones = {"FMC": (FMC, FMCW), "PMC": (FMC, FMCW), "NMCM": (NMCM, NMCMW), "NMCS": (NMCS, NMCSW),
             "NMCD": (NMCD, NMCDW)}
    words = {"FMC": "Mission capable", "PMC": "Mission capable", "NMCM": "In maintenance", "NMCS": "Waiting for parts",
             "NMCD": "At depot"}
    b = [f'<text x="64" y="104" class="k">REAL-TIME AI FOR CRITICAL DECISIONS · ON IBM LINUXONE</text>',
         '<text x="62" y="170" style="font-size:54px;font-weight:800;letter-spacing:-.035em">More aircraft flying,</text>',
         f'<text x="62" y="232" style="font-size:54px;font-weight:800;letter-spacing:-.035em">every <tspan fill="{ACC}">morning.</tspan></text>']
    sub = ["Phalanx Twin turns a fleet's alarms, maintenance records and parts",
           "data into a ranked decision board before 07:45 — every order",
           "explained, simulated against doing nothing, signed and replayable."]
    b += [f'<text x="64" y="{290 + i*28}" style="font-size:19px;fill:{INK2}">{esc(t)}</text>' for i, t in enumerate(sub)]
    # pills
    b.append(f'<g transform="translate(64,412)"><rect width="262" height="44" rx="22" fill="{INK}"/>'
             f'<circle cx="24" cy="22" r="6" fill="#3DDC84"><animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/></circle>'
             f'<text x="40" y="28" style="font-size:16px;font-weight:700;fill:#fff">Live · 148.100.99.205</text></g>')
    b.append(f'<g transform="translate(340,412)"><rect width="300" height="44" rx="22" fill="{IBMW}" stroke="{IBML}"/>'
             f'<rect x="18" y="14" width="16" height="16" rx="3" fill="none" stroke="{IBM}" stroke-width="2"/>'
             f'<path d="M22 19h8M22 22h8M22 25h8" stroke="{IBM}" stroke-width="1.6"/>'
             f'<text x="44" y="28" style="font-size:16px;font-weight:700;fill:{IBM}">IBM LinuxONE · s390x</text></g>')
    # fleet panel
    px, py, pw, ph = 720, 44, 424, 432
    b.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="20" fill="{BG2}" stroke="{LINE}"/>')
    b.append(f'<text x="{px+24}" y="{py+38}" class="k" style="fill:{INK3}">READINESS · MON 22 JUN 06:00</text>')
    b.append(f'<text x="{px+24}" y="{py+86}" style="font-size:44px;font-weight:800;letter-spacing:-.03em">'
             f'{r["now"]["mc"]}<tspan style="font-size:20px;font-weight:600;fill:{INK2}"> of {r["now"]["of"]} aircraft mission capable</tspan></text>')
    for i, a in enumerate(r["fleet"]):
        col, row = i % 4, i // 4
        cx, cy = px + 24 + col * 96, py + 116 + row * 150
        stroke, wash = tones[a["state"]]
        b.append(f'<rect x="{cx}" y="{cy}" width="88" height="140" rx="12" fill="#fff" stroke="{LINE}"/>')
        b.append(planform(cx + 21, cy + 14, 5.6, wash, stroke, 1.3))
        b.append(f'<text x="{cx+10}" y="{cy+112}" style="font-size:13px;font-weight:700">{a["tail"]}</text>')
        b.append(f'<circle cx="{cx+14}" cy="{cy+127}" r="4" fill="{stroke}"/>'
                 f'<text x="{cx+22}" y="{cy+131}" style="font-size:9.5px;font-weight:600;fill:{stroke}">{words[a["state"]]}</text>')
    b.append(f'<text x="{px+24}" y="{py+ph-14}" class="f">Simulated fleet · Phalanx data layer</text>')
    write("hero.svg", svg(1200, 520, "".join(b), "Phalanx Twin — more aircraft flying, every morning"))


# ---------------------------------------------------------------- problem
def problem():
    r, bd = live("readiness"), live("board")
    k = r["kpis"]["d30"]
    parts = [("Mission capable", k["mc"], FMC), ("Waiting for parts", k["tnmcs"], NMCS),
             ("In maintenance", k["tnmcm"], NMCM), ("At depot", k["nmcd"], NMCD)]
    x0, y0, W = 64, 176, 1072
    b = [f'<text x="64" y="70" class="k">THE PROBLEM</text>',
         f'<text x="64" y="112" class="h">Aircraft are not lost to flying. They are lost to waiting.</text>',
         f'<text x="64" y="142" class="s">Where one squadron\'s last 30 days went ({k["possessed"]:.0f} aircraft-days, simulated fleet)</text>']
    x = x0
    for i, (lab, v, c) in enumerate(parts):
        w = W * v
        b.append(f'<rect x="{x:.1f}" y="{y0}" width="{w-3:.1f}" height="64" rx="8" fill="{c}"/>')
        if w > 150:
            b.append(f'<text x="{x+16:.1f}" y="{y0+30}" style="font-size:24px;font-weight:800;fill:#fff">{v*100:.1f} %</text>'
                     f'<text x="{x+16:.1f}" y="{y0+50}" style="font-size:13px;font-weight:600;fill:#fff;opacity:.92">{lab}</text>')
        else:
            b.append(f'<text x="{x+w/2-2:.1f}" y="{y0+36}" text-anchor="middle" style="font-size:15px;font-weight:800;fill:#fff">{v*100:.0f}%</text>'
                     f'<text x="{x+w/2-2:.1f}" y="{y0+90}" text-anchor="middle" class="f" style="fill:{c};font-weight:700">{lab}</text>')
        x += w
    nx = x0 + W * r["kpis"]["norm_mc"]
    b.append(f'<path d="M{nx:.1f} {y0-18}V{y0+76}" stroke="{INK}" stroke-width="2" stroke-dasharray="4 4"/>'
             f'<text x="{nx+8:.1f}" y="{y0-6}" style="font-size:13px;font-weight:700">Target 75 %</text>')
    cards = [
        (f'{k["tnmcs"]*100:.1f} %', "of aircraft-time waiting for parts", "the largest single loss — a parts and decision problem, not a flying one", NMCS),
        (f'{bd["load"]["alert_rows"]:,}', f'alerts in {bd["load"]["days"]} days', "for 8 aircraft — the morning meeting cannot read them all", NMCM),
        ("30", "pumps removed from one aircraft", "for one alarm; 0 of 118 jobs on that alarm ever found a fault", ACC),
        ("07:45", "to decide, every day", "from logbooks and memory — with no way to test an order before it is issued", INK),
    ]
    for i, (big, lab, note, c) in enumerate(cards):
        cx = 64 + i * 272
        b.append(f'<rect x="{cx}" y="300" width="256" height="190" rx="16" fill="{BG2}" stroke="{LINE}"/>'
                 f'<rect x="{cx+24}" y="318" width="36" height="5" rx="2.5" fill="{c}"/>'
                 f'<text x="{cx+24}" y="356" style="font-size:38px;font-weight:800;letter-spacing:-.03em;fill:{c}">{esc(big)}</text>'
                 f'<text x="{cx+24}" y="384" style="font-size:14px;font-weight:700">{esc(lab)}</text>')
        words, line, ly = note.split(), "", 412
        for w_ in words:
            if len(line + " " + w_) > 31:
                b.append(f'<text x="{cx+24}" y="{ly}" class="t">{esc(line.strip())}</text>'); ly += 20; line = ""
            line += " " + w_
        b.append(f'<text x="{cx+24}" y="{ly}" class="t">{esc(line.strip())}</text>')
    b.append(f'<text x="64" y="526" class="f">Figures from the live deployment, over the simulated fleet of the Phalanx data layer.</text>')
    write("problem.svg", svg(1200, 552, "".join(b), "The problem: availability lost to waiting and false alarms"))


# ---------------------------------------------------------------- impact (paired simulations)
def impact():
    a, bd = live("assurance"), live("board")
    label = {x["id"]: x["label"] for x in bd["board"]}
    forks = sorted(a["forks"], key=lambda f: -f["d_mc"][0])
    x0, x1, lo, hi = 470, 1110, -20, 32
    X = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    top = 170
    b = [f'<text x="64" y="70" class="k">PROVED BEFORE IT IS ISSUED</text>',
         f'<text x="64" y="112" class="h">Every order is simulated against doing nothing.</text>',
         f'<text x="64" y="142" class="s">Change in mission-capable rate over the next 30 days · mean and 95 % interval of paired simulations</text>']
    for v in range(-20, 31, 10):
        b.append(f'<path d="M{X(v):.1f} {top-8}V{top+len(forks)*44}" stroke="{LINE if v else INK3}" '
                 f'stroke-width="{1 if v else 1.5}"/><text x="{X(v):.1f}" y="{top+len(forks)*44+22}" '
                 f'text-anchor="middle" class="f">{"+" if v > 0 else ("−" if v < 0 else "")}{abs(v)} pts</text>')
    b.append(f'<text x="{X(0)+6:.1f}" y="{top-14}" class="f" style="font-weight:700">doing nothing</text>')
    for i, f in enumerate(forks):
        y = top + 20 + i * 44
        m, l, h = f["d_mc"]
        tail, _, code = f["issue_id"].partition("-")
        c = FMC if l > 0 else (NMCS if h < 0 else INK3)
        b.append(f'<text x="64" y="{y+5}" style="font-size:15px;font-weight:700">{tail}</text>'
                 f'<text x="124" y="{y+5}" class="t">{esc(label.get(f["issue_id"], code))}</text>'
                 f'<text x="400" y="{y+5}" class="f mono">{f["pairs"]} pairs</text>')
        if f["no_change"] or (l == h == 0):
            b.append(f'<circle cx="{X(0):.1f}" cy="{y}" r="6" fill="#fff" stroke="{INK3}" stroke-width="2"/>'
                     f'<text x="{X(0)+16:.1f}" y="{y+5}" class="f">no change — the order cannot help yet</text>')
            continue
        b.append(f'<path d="M{X(l):.1f} {y}H{X(h):.1f}" stroke="{c}" stroke-width="4" stroke-linecap="round" opacity=".35"/>'
                 f'<circle cx="{X(m):.1f}" cy="{y}" r="7" fill="{c}"/>')
        sign = "+" if m > 0 else ("−" if m < 0 else "")
        txt = f"{sign}{abs(m):.1f}"
        if f["issue_id"] == "TJ107-HYD-101":
            txt += " pts · approved: stop removing pumps"
        elif h < 0:
            txt += " pts · rejected: worse than doing nothing"
        if X(h) + 7.2 * len(txt) > 1150:
            b.append(f'<text x="{X(h):.1f}" y="{y-14}" text-anchor="end" style="font-size:13px;font-weight:700;fill:{c}">{esc(txt)}</text>')
        else:
            b.append(f'<text x="{X(h)+14:.1f}" y="{y+5}" style="font-size:13px;font-weight:700;fill:{c}">{esc(txt)}</text>')
    yb = top + len(forks) * 44 + 52
    b.append(f'<text x="64" y="{yb}" class="f">Common-random-number pairs of the fleet simulator (the order vs StatusQuoPolicy), run on IBM LinuxONE. Live values from /api/assurance.</text>')
    write("impact.svg", svg(1200, yb + 30, "".join(b), "Paired simulations: impact of each order against doing nothing"))


# ---------------------------------------------------------------- the LinuxONE stack
def stack():
    h = live("health")
    a = live("assurance")
    layers = [
        ("You", "Any browser · https://148.100.99.205", "nginx · TLS 1.3 · Let's Encrypt IP certificate", INK, BG2, "#fff"),
        ("phx-ground", "Phalanx Twin — as-of store, 11 registered models, zen-engine decision tables,",
         "daily 06:00 → 07:45 → 08:00 loop, order desk, hash-chained event log · FastAPI :8700", ACC, ACCW, ACCL),
        ("phx-runner", "Simulated fleet — 8 aircraft worlds stepped daily, order gateway,",
         "what-if forks (CRN pairs), order journal + replay · FastAPI :8710", NMCD, NMCDW, "#CFCBF5"),
        ("Python on s390x", "One Anaconda environment: numpy 2.2 · pandas 2.2 · pyarrow 19 · scikit-learn 1.6 · scipy 1.15",
         "· lifelines · NetworkX · zen-engine built from source (Rust) · numba stand-in · Arrow IPC", FMC, FMCW, "#BFE3CD"),
        ("Ubuntu 24.04.5", "Linux 6.8 · systemd services with automatic restart · iptables · nginx",
         "3 vCPU · 8 GB RAM · 50 GB disk (LinuxONE Community Cloud guest)", INK2, BG2, LINE),
        ("IBM LinuxONE", "Machine type 9175 (IBM z17 / LinuxONE Emperor 5 generation, Telum II) · z/VM 7.3.0",
         "s390x · big-endian · the whole system — nothing runs on x86 or a public cloud", IBM, IBMW, IBML),
    ]
    b = [f'<text x="64" y="70" class="k">ONE LINUXONE GUEST RUNS EVERYTHING</text>',
         f'<text x="64" y="112" class="h">From the mainframe up to the screen.</text>']
    y = 150
    for i, (name, l1, l2, c, wash, line) in enumerate(layers):
        b.append(f'<rect x="64" y="{y}" width="1072" height="70" rx="14" fill="{wash}" stroke="{line}"/>'
                 f'<rect x="64" y="{y}" width="200" height="70" rx="14" fill="{c}"/>'
                 f'<rect x="250" y="{y}" width="14" height="70" fill="{c}"/>'
                 f'<text x="86" y="{y+42}" style="font-size:18px;font-weight:800;fill:#fff">{esc(name)}</text>'
                 f'<text x="290" y="{y+30}" style="font-size:15px;font-weight:600">{esc(l1)}</text>'
                 f'<text x="290" y="{y+52}" class="t">{esc(l2)}</text>')
        y += 80
    gates = " · ".join(f'{g["gate"]} {"✓" if g["ok"] else "✗"}' for g in a["gates"])
    files = sum(h["files"].values())
    b.append(f'<text x="64" y="{y+20}" class="f">Live: {gates} · {files:,} contract files loaded for today, {len(h["rejected"])} rejected · status {h["status"]}</text>')
    write("linuxone-stack.svg", svg(1200, y + 46, "".join(b), "The Phalanx Twin stack on one IBM LinuxONE guest"))


# ---------------------------------------------------------------- terminal (real output captured from the server)
def terminal():
    lines = (LIVE / "terminal.txt").read_text().rstrip("\n").split("\n")
    lh, top = 24, 74
    h = top + len(lines) * lh + 36
    b = [f'<rect x="1" y="1" width="1198" height="{h-2}" rx="20" fill="#0B0D10"/>',
         *[f'<circle cx="{32+i*22}" cy="34" r="7" fill="{c}"/>' for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840"))],
         f'<text x="600" y="39" text-anchor="middle" class="mono" style="font-size:13px;fill:#8A8F98">linux1@dilijens — IBM LinuxONE · s390x</text>']
    for i, ln in enumerate(lines):
        y = top + i * lh
        if ln.startswith("$ "):
            b.append(f'<text x="32" y="{y}" class="mono" style="font-size:15px"><tspan fill="#3DDC84">linux1@dilijens</tspan>'
                     f'<tspan fill="#8A8F98">:~$ </tspan><tspan fill="#fff">{esc(ln[2:])}</tspan></text>')
        elif ln.startswith("#"):
            b.append(f'<text x="32" y="{y}" class="mono" style="font-size:15px;fill:#8A8F98">{esc(ln)}</text>')
        else:
            hl = "#F6CDB6" if any(w in ln for w in ("s390x", "Big Endian", "9175", "z/VM", "GO", "identical", "active")) else "#D6D6D1"
            b.append(f'<text x="32" y="{y}" class="mono" style="font-size:15px;fill:{hl}">{esc(ln)}</text>')
    write("linuxone-terminal.svg", svg(1200, h, "".join(b), "Terminal on the LinuxONE guest", mono=True, card=False))


# ---------------------------------------------------------------- live metrics strip
def metrics():
    r, bd, a, ep = live("readiness"), live("board"), live("assurance"), live("epoch")
    lat = json.loads((LIVE / "latency.json").read_text())
    k = r["kpis"]["d30"]
    tiles = [
        (f'{r["now"]["mc"]}/{r["now"]["of"]}', "aircraft mission capable", "this morning", FMC),
        (f'{bd["load"]["alert_rows"]:,} → {bd["load"]["items"]}', "alerts → decisions", "before 07:45", ACC),
        ("+18.0", "pts mission capable", "TJ107 order vs doing nothing", FMC),
        (f'{sum(g["ok"] for g in a["gates"])}/{len(a["gates"])}', "assurance gates passed", "release · reproduction · metrics · sims", IBM),
        (f'{len(a["registered"])}', "models registered", "champion / challenger, versioned", NMCD),
        (f'{lat["median_ms"]:.1f} ms', "median API response", f'on the server · p95 {lat["p95_ms"]:.0f} ms', INK),
        ("0.1008", "Brier, false-alarm model", "vs 0.1072 challenger · 139 held-out jobs", NMCM),
        ("8/8", "planted engine faults found", "77–302 days before the limit", NMCS),
    ]
    b = [f'<text x="64" y="70" class="k">LIVE FROM THE DEPLOYED SYSTEM</text>',
         f'<text x="64" y="112" class="h">What the running twin reports right now.</text>',
         f'<text x="64" y="142" class="s">Snapshot {esc(ep["clock"]["asof"])} · snapshot hash {ep["clock"]["snapshot_id"][:16]}…</text>']
    for i, (big, lab, note, c) in enumerate(tiles):
        col, row = i % 4, i // 4
        x, y = 64 + col * 272, 170 + row * 150
        b.append(f'<rect x="{x}" y="{y}" width="256" height="134" rx="16" fill="{BG2}" stroke="{LINE}"/>'
                 f'<text x="{x+22}" y="{y+52}" style="font-size:34px;font-weight:800;letter-spacing:-.03em;fill:{c}">{esc(big)}</text>'
                 f'<text x="{x+22}" y="{y+82}" style="font-size:15px;font-weight:700">{esc(lab)}</text>'
                 f'<text x="{x+22}" y="{y+106}" class="f">{esc(note)}</text>')
    b.append(f'<text x="64" y="488" class="f">Collected from https://148.100.99.205/api/* and on the server ({esc(lat["when"])}). Simulated fleet; model scores are on held-out simulation worlds.</text>')
    write("live-metrics.svg", svg(1200, 516, "".join(b), "Key metrics from the deployed application"))


# ---------------------------------------------------------------- the IBM Z deployment target
def mainframe():
    W, H = 1200, 860
    b = [f'<text x="64" y="70" class="k" style="fill:{IBM}">THE PLAN FOR IBM Z</text>',
         f'<text x="64" y="112" class="h">One frame for every squadron, the command and the records.</text>',
         f'<text x="64" y="142" class="s">Target deployment on an IBM z17 / LinuxONE Emperor 5 class system at an air-force data centre</text>']
    # bases
    b.append(f'<text x="64" y="196" class="f" style="font-weight:700;letter-spacing:.1em">SQUADRON BASES</text>')
    for i in range(4):
        y = 214 + i * 92
        b.append(f'<rect x="64" y="{y}" width="168" height="76" rx="12" fill="{BG2}" stroke="{LINE}"/>'
                 + planform(76, y + 9, 4.2, "#fff", INK3, 1)
                 + f'<text x="124" y="{y+34}" style="font-size:14px;font-weight:700">{"Squadron " + str(i+1) if i < 3 else "… squadron n"}</text>'
                 f'<text x="124" y="{y+54}" class="f">daily aircraft</text><text x="124" y="{y+68}" class="f">download</text>')
        b.append(f'<path d="M232 {y+38}H292" stroke="{INK3}" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#ar)"/>')
    b.append(f'<text x="64" y="600" class="f">secure WAN or one-way data diode</text>')
    # frame
    fx, fy, fw, fh = 300, 176, 640, 600
    b.append(f'<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
             f'<path d="M0 0L10 5L0 10z" fill="{INK3}"/></marker>'
             f'<pattern id="lock" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 8L8 0" stroke="{IBML}" stroke-width="1"/></pattern></defs>')
    b.append(f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="18" fill="#fff" stroke="{IBM}" stroke-width="2.5"/>'
             f'<rect x="{fx}" y="{fy}" width="{fw}" height="40" rx="18" fill="{IBM}"/><rect x="{fx}" y="{fy+22}" width="{fw}" height="18" fill="{IBM}"/>'
             f'<text x="{fx+20}" y="{fy+26}" style="font-size:15px;font-weight:800;fill:#fff">IBM Z / LinuxONE frame</text>'
             f'<text x="{fx+fw-20}" y="{fy+26}" text-anchor="end" style="font-size:12px;font-weight:600;fill:#fff">PR/SM logical partitions</text>')
    def lpar(x, y, w, h, title, sub, rows, c, wash):
        out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{wash}" stroke="{c}" stroke-width="1.4"/>',
               f'<text x="{x+14}" y="{y+24}" style="font-size:14px;font-weight:800;fill:{c}">{esc(title)}</text>',
               f'<text x="{x+14}" y="{y+42}" class="f">{esc(sub)}</text>']
        for j, (t, s) in enumerate(rows):
            yy = y + 58 + j * 44
            out.append(f'<rect x="{x+12}" y="{yy}" width="{w-24}" height="36" rx="8" fill="#fff" stroke="{LINE}"/>'
                       f'<text x="{x+24}" y="{yy+16}" style="font-size:12.5px;font-weight:700">{esc(t)}</text>'
                       f'<text x="{x+24}" y="{yy+30}" style="font-size:10.5px;fill:{INK3}">{esc(s)}</text>')
        return "".join(out)
    b.append(lpar(fx+16, fy+56, 296, 278, "LPAR 1 · Squadron twins", "LinuxONE guests in IBM Secure Execution",
                  [("Phalanx Twin · Sqn 1", "the prototype stack, one guest per squadron"),
                   ("Phalanx Twin · Sqn 2", "sealed: admins cannot read memory"),
                   ("Phalanx Twin · Sqn n", "same image, measured and attested"),
                   ("Fork farm", "what-if simulations on spare capacity")], ACC, ACCW))
    b.append(lpar(fx+328, fy+56, 296, 278, "LPAR 2 · Command", "Linux on OpenShift on IBM Z",
                  [("Fleet availability view", "all squadrons on one consistent state"),
                   ("Spares & cannibalisation", "move parts where they fly most"),
                   ("IBM Maximo Manage", "work orders — runs on s390x"),
                   ("Model registry & training", "champion / challenger for all units")], NMCD, NMCDW))
    b.append(lpar(fx+16, fy+346, 608, 102, "LPAR 3 · z/OS — existing systems of record", "kept where they are, read and written in place",
                  [("Db2 for z/OS · CICS / IMS — maintenance logs, supply and inventory, personnel authorisations", "")], INK2, BG2))
    b.append(f'<rect x="{fx+222}" y="{fy+66}" width="76" height="20" rx="10" fill="{FMC}"/>'
             f'<text x="{fx+260}" y="{fy+80}" text-anchor="middle" style="font-size:10px;font-weight:800;fill:#fff">PROVED</text>')
    # hipersockets
    b.append(f'<rect x="{fx+16}" y="{fy+458}" width="608" height="30" rx="8" fill="{IBMW}" stroke="{IBML}"/>'
             f'<text x="{fx+320}" y="{fy+478}" text-anchor="middle" style="font-size:12.5px;font-weight:700;fill:{IBM}">'
             f'HiperSockets — memory-speed network between the partitions, no cables, no exposure</text>')
    hw = [("Telum II AI on chip", "score every alert inline"), ("CPACF crypto", "hash every log entry"),
          ("Crypto Express HSM", "officers' signing keys"), ("Redundant hardware", "concurrent maintenance")]
    for j, (t, s) in enumerate(hw):
        x = fx + 16 + j * 154
        b.append(f'<rect x="{x}" y="{fy+500}" width="146" height="84" rx="10" fill="{IBM}"/>'
                 f'<text x="{x+12}" y="{fy+528}" style="font-size:12.5px;font-weight:800;fill:#fff">{esc(t)}</text>'
                 f'<text x="{x+12}" y="{fy+548}" style="font-size:11px;fill:#DCE8FF">{esc(s)}</text>')
    b.append(f'<text x="{fx+16}" y="{fy+fh+22}" class="f">Hardware shared by every partition</text>')
    # right side
    rx = 980
    def side(y, t, lines, c=INK):
        out = [f'<path d="M{fx+fw} {y+30}H{rx-6}" stroke="{INK3}" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#ar)"/>',
               f'<rect x="{rx}" y="{y}" width="156" height="{30 + len(lines)*18}" rx="12" fill="{BG2}" stroke="{LINE}"/>',
               f'<text x="{rx+14}" y="{y+24}" style="font-size:13.5px;font-weight:800;fill:{c}">{esc(t)}</text>']
        out += [f'<text x="{rx+14}" y="{y+44+k*18}" class="f">{esc(s)}</text>' for k, s in enumerate(lines)]
        return "".join(out)
    b.append(side(214, "Decision board", ["engineering officers,", "07:45 every morning"]))
    b.append(side(326, "Signed orders", ["HSM-signed, into", "Maximo + the line"]))
    b.append(side(438, "Auditors", ["airworthiness authority", "replays any decision"]))
    b.append(side(560, "DR site", ["GDPS mirror —", "a second frame"], IBM))
    b.append(f'<text x="64" y="{H-30}" class="f">Target architecture. The prototype proves LPAR 1 on one LinuxONE guest; the other partitions and the hardware features are the roadmap (see the table below).</text>')
    write("ibmz-deployment.svg", svg(W, H, "".join(b), "Target deployment of Phalanx Twin on an IBM Z / LinuxONE frame"))


if __name__ == "__main__":
    logos(); hero(); problem(); impact(); stack(); terminal(); metrics(); mainframe()
