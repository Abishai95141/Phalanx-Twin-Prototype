# Phalanx Twin — screen build spec (for the product film)

Every screen is a standalone **1920 × 1080** HTML page in `video/screens/`, sharing one design system. The
screens will be filmed with HyperFrames (camera pushes, highlights, typed input), so they must look like a
finished, shipping product: no lorem ipsum, no "mock", "demo", "preview", "synthetic", "sample" or "placeholder"
text anywhere in the UI. Do not brand anything "IAF" or use real squadron names/numbers; the station is
"Station Sulur", the fleet is eight Tejas-class aircraft TJ101–TJ108.

Reference pages to copy patterns from (read both first): `readiness.html` (dense dashboard) and `twin.html`
(three-column workspace + 3D). Shared assets: `assets/app.css` (tokens + components — read it fully),
`assets/shell.js` (window chrome, sidebar, page head, icon sprite), `assets/logo.js`, `assets/data.js`
(`window.PHX_DATA`), `assets/aircraft.js` (`PHX_AC.planform/side`), `assets/twin3d.js` (three.js twin).

## DESIGN SYSTEM v2 — overrides any denser pattern below (user feedback: "too complicated and clumsy")

The first screens were too dense. Every screen now follows these rules; when a page needs more than this allows,
**split it into several screens** (e.g. `insights.html` + `insights-nff.html` + `insights-integrity.html`) and
link them with tabs (`.tabs2`) under the page head.

1. **One question per screen; at most three regions** (one hero + up to two supporting). If a fourth thing is
   needed, it is a new screen or a tab.
2. **12-column grid** `.v2` with 24 px gutters; regions are `.panel2` cards spanning `.c3…c12`. Card padding 28,
   region gap 24, ≥ 48 px of white space somewhere on every screen.
3. **Card anatomy** (`.panel2`): `.kick` label → `.t2` title (one sentence, plain English) → `.sub2` one line →
   body → optional `.lnk` footer. **One hero number per card** (`.big` or `.mid`); its interval or n goes
   underneath in `.ci`, never inline in every row.
4. **Type scale only**: display 56 (`.big`) · 36 (`.mid`) · h1 30 · h2 22 (`.t2`) · h3 17 (`.t3`) · body 15 ·
   small 13 · label 11.5 (`.kick`) · mono 13. No other sizes.
5. **Lists** use `.rows2` / `.r2` (≥ 72 px rows): at most **three data points + one action** per row. The
   selected row is `.r2.on`.
6. **Progressive disclosure:** record ids, order ids, hashes, rule traces, confidence intervals and model
   versions appear only on the screen whose job is to explain them (Why / Provenance / Assurance). Main screens
   state the conclusion in words plus one number.
7. **Colour budget per card:** ink + at most one semantic colour + the accent. Tier badges: one per card, in
   the card header.
8. **Page head:** title + one-line subtitle + **at most two chips** (as-of and one status).
9. No inline code strings, no mono paragraphs, no more than one row of chips anywhere.

## Page skeleton

```html
<!doctype html><html lang="en"><head><meta charset="utf-8"><title>X — Phalanx Twin</title>
<link rel="stylesheet" href="assets/app.css"><style>/* page-only styles */</style></head>
<body data-page="decisions"><div id="content"> …page body… </div>
<script src="assets/logo.js"></script><script src="assets/data.js"></script><script src="assets/shell.js"></script>
<script> /* build dynamic parts BEFORE mount (they live inside #content) */
PHX.mount({ page: 'decisions', title: 'Decision board', sub: '…', chips: [{k:'ok',i:'lock',t:'Air-gapped'}, …] });
</script></body></html>
```
`page` must be one of the sidebar keys: readiness, decisions, twin, plan, spares, insights, assurance (sub-pages
such as the workbench use the parent key). Icons: `<i data-i="name" class="ico-sm"></i>` (or `ico`). Names:
readiness decisions twin plan spares insights assurance assistant search chevDown chevRight chevLeft arrowRight
arrowUpRight clock calendar lock shield server cpu check x alert info wrench fork link hash pen signature user
layers eye cube sliders table wave flag tyre drop bolt engine radar play pause rewind download filter refresh
sparkle book history scale grid list target xray explode section inbox snooze tag gauge route dot minus plus
more paperclip send command.

## Canvas and layout

- Content area (inside `.content`, after padding) is **≈ 1460 × 812 px** (x 392→1852, y 214→1024 on the stage).
  Nothing may clip or overflow; nothing may scroll. Use CSS grid with fixed row heights that sum to ≤ 812.
- Verify every page: server is running at `http://127.0.0.1:8137`; run `../shoot.sh <page>.html [name]` from
  `video/screens/` → PNG in `video/stills/`; **Read the PNG** and fix clipping, overlaps, wrapping, empty
  space and misalignment. Iterate until it is clean at full resolution. Also check the browser console has no
  errors (a missing `#id` before mount is the usual bug).
- Mark regions the camera will push into with `data-shot="name"`.
- States for the film: support `?state=…` URL params that switch a page into a later state (e.g. approved,
  frozen, signed). Default load = the main state.

## Visual language (non-negotiable)

- White-first, ink typography (Manrope; JetBrains Mono for ids, codes, numbers in tables, axis labels),
  generous whitespace, 1-px hairlines (`--line`), radius 14–18 px cards, almost no shadow. One warm accent
  (`--accent` #E8743B) for focus, the loop, selection and meters. **No dark surfaces anywhere**: no black/ink
  cards, panels, code blocks, banners or dark modal backdrops (use white frosted backdrops). Black only for
  small primary buttons, priority/authority badges and pills. Highlight cards = accent-wash + accent-line border.
- Colours carry meaning only: SCIR state (`fmc/pmc/nmcm/nmcs/nmcd` pills and fills), priority bands
  (`.prio.p1…p4`), analytics tiers (`.tier.desc/.diag/.pred/.presc` — show them on cards so viewers see the
  descriptive/diagnostic/predictive/prescriptive capability), authority (`.auth.agent` grey, `.auth.human`
  black with signature icon), record ids (`.rid` blue chips), codes (`.code`). Blue `--wire` = evidence links /
  data lineage.
- Uncertainty is always visible: intervals `0.31 [0.22, 0.41]` in muted brackets, quantile dotplots, CI bars;
  "no estimate" = hatched grey (`.hatch`), never green. Small sample → say n.
- Charts: hand-built inline SVG only (no chart libraries). Axis/tick labels 11 px JetBrains Mono `--ink-4`,
  gridlines `--line-2`, data in ink or semantic colours, direct labels instead of legends where possible.
- Every recommendation uses the **same five-part card**: STATE → WHY (record ids, with t_ingest ≤ snapshot)
  → FORECAST (with uncertainty) → ORDERS (action + AGENT/HUMAN badge) → IMPACT (paired-fork KPI delta vs
  status quo, n pairs, CI) — plus Why / Why not / What if tabs and Approve · Modify · Reject · Snooze.
- Tone of copy: precise, calm, operational. Short labels. No marketing words, no exclamation marks, no emoji.

## Data rules (credibility is the point)

- **Every number must come from the data or a computation you actually run**, or from the architecture docs in
  `docs/architecture/`. Never invent metrics that look impressive. Identifiers (versions like
  `P-DEC-01/1.4.0+jdm.c9b849a8e719`, model names, job ids) may be product metadata but must stay consistent with
  other pages. Hashes you display should be real hashes you computed (blake2b/sha256) of the thing they name.
- Snapshot (the "now") is **Mon 22 Jun 2026, 06:00 IST**; epoch 08:00; board freezes 07:45; session clock
  06:12. Read the data strictly as of `t_ingest ≤ 2026-06-22 06:00 IST`.
- Data sources: `video/data/*.json|csv` (already computed: `fleet_asof_20260704.json` is a later snapshot —
  ignore it; use `kpis_asof_20260622.json`, `triage_asof_20260622.json`, `issues_asof_20260622.csv`,
  `code_outcomes_asof_20260622.csv`, `downtime_attribution_asof_20260622.json`, `daily_state.csv`,
  `telemetry_TJ212_1hz.csv`) and `window.PHX_DATA` in `assets/data.js`. For new computations use the raw
  Parquet at `/Users/abishaikc/Downloads/phalanx_data_layer_preview/data/v0.9/fleet/` with the helper
  `<scratch>`
  (`rd(topic)` → pandas with `*_dt` IST columns, scoped dedupe by (tail_no, record_id)) run with
  `<scratch>`
  (pyarrow + pandas). Write your scripts to `video/data/scripts/` and their outputs to `video/data/`.
  **Never open `_restricted_labels/`.** Each world is one tail: key everything by (tail_no, id).
- If a number cannot be computed honestly, design the state so it isn't needed (e.g. a model gate shows
  `INSUFFICIENT_EVIDENCE · 0 confirmed failures`), rather than faking it.

## Shared facts (as of 22 Jun 06:00 IST)

- Fleet: 8 aircraft, 6 mission capable. TJ101 NMCD (ROH depot since 27 May 08:00), TJ108 NMCS since 3 Apr
  08:00 (job sulur-26093-0003 AWAITING_PARTS brake parachute, AOG demand D-sulur-26093-0002 opened 3 Apr; tyre
  demand D-sulur-26093-0001 same day). Others FMC.
- 168 days: MC 0.608, FMC 0.589, TNMCM 0.173, TNMCS 0.195, NMCD 0.019; last 30 d MC 0.545, TNMCS 0.254.
  497.3 FH, 588 sorties. Downtime: NMCS 262.6 tail-days (tyres 92.4, chutes 88.6, hyd pumps 32.6, engine
  32.4), NMCM 237.8 (SRV-L2 major 94.5, SRV-L1 37.7, tyres 26.2, SRV-L2 minor 20.7), NMCD 25.9 (ROH).
- Alerts → issues: 921 BIT events + 271 cautions = 1,192 alert rows → 326 issues; 33 open; ≈ 2 new/day.
  Severity ADVISORY 650 / CAUTION 240 / WARNING 31. Top codes ENG-201 186, HYD-101 121, AVI-201 106, AVI-203 96.
- 907 defect jobs: AT-CND 360, AT-RR 358, AT-ADM 156, AT-DEF 17, AT-TS 1. Shop findings 54, all RTOK.
  Defect man-hours 5,700. XXX (unreadable) serials in 23 records.
- HYD-101 (hydraulic pump fault, CAUTION, reporter BHEEM_EU, suspects HYD_PUMP 0.8 / AMAGB 0.2): fleet 107
  jobs → 71 CND, 35 R/R (all RTOK), 1 TS, 0 confirmed. TJ107: fired on 59 of 61 sorties; standing for 34
  consecutive flights; 64 jobs, 792.3 man-hours; 28 pump removals across 10 pump serials (+1 unreadable record); installed SYS1 serial
  HYDP-000010 (inferred from job sulur-26169-0006 text; install record not yet ingested), SYS2 HYDP-000002.
  Latest HYD-101 event record_id `fcf0b94962735ffc27d5f5664c2c4d02` (sortie TJ107-20260618T1430, ingested
  18 Jun 21:08). TJ102 shows the same pattern (24 flights since 9 Apr).
- Board for epoch 22 Jun 08:00 (7 items): P1 TJ103 LGB-501 gear unsafe (WARNING ×2, 15 & 19 Jun) →
  TROUBLESHOOT; P1 TJ106 LGB-501 (10 & 18 Jun) → TROUBLESHOOT; P2 TJ107 HYD-101 standing → stop R/R,
  TROUBLESHOOT indication path, HUMAN-only CHANGE_MONITORING_CONFIG draft (rule P-DEC-01 r3 + D8 nuisance
  review); P2 TJ108 AOG brake chute open 80 d → EXPEDITE_SPARES; P3 TJ105 tyre at 7/8 landings →
  REQUISITION_SPARES; P3 TJ105 SPS-501 JFS start fail 4× in 10 d → TROUBLESHOOT; P4 grouped: 9 advisory
  issues (ENG-201, AVI-201/203/204, ADC-002, ELE-405) CND-dominated → MONITOR.
- Supply lead time (127 closed demands): median 4.6 d, p90 38.3 d, mean 12.6 d, max 91.6 d; tyres median
  4.5 d (n 117), chutes 12.2 d (n 6), pumps 9.5 d (n 4).
- Decision latency: the loop decides new evidence at the next 08:00 epoch — median 18.4 h, max 23.4 h after
  ingest; status quo evidence → job close median 18.6 h, p90 147 h (6.1 d).
- Contract 0.2.0 hash `a4396f1d5482ce78…`, dictionary tejas 0.1.3 `9428d30f578f0318…`, release code commit
  `6d4dc52`. Order id format `phx:<rule>:<policy semver>:<epoch YYYYMMDDTHHMM>:<tail>:<action>:<blake2b8>`.
- Station server (sidebar) is fixed by the shell; don't restyle it.
