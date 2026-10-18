# Phalanx Twin film — motion & composition guide (read fully before building)

You are building one **act** of a 4½-minute, white-first product launch film for "Phalanx Twin" (team
Dilijens, IBM Z Datathon). Read first: `video/STORYBOARD.md` (the shot list — follow it),
`video/edit/timing.json` (exact shot times), `video/screens/SPEC.md` (design + data rules),
`video/research/hyperframes.md` §3–§7 (HyperFrames rules), this file, and `video/film/test.html` (a working
director that mounts frozen screens, pushes a camera and drives the live 3D twin).

## Project layout (single HyperFrames project = `video/film/`)

- `film/<act>.html` — your director composition (`act01`, `act2`, `act3a`, `act3b`). Root:
  `<div id="root" data-composition-id="main" data-start="0" data-duration="<act dur from timing.json>"
  data-width="1920" data-height="1080">`, one paused GSAP timeline registered last as `window.__timelines["main"]`.
- `film/screens/<key>.html` — **frozen** product screens (static DOM, ids prefixed `<key>-`, root
  `#<key>-root`). Create/refresh with `cd video/film && python3 tools/freeze.py <page.html[?state=…]> <key>`
  (the screens server runs at http://127.0.0.1:8137; restart it with `python3 -m http.server 8137 --bind
  127.0.0.1 --directory video/screens` if it is down). Never hand-edit frozen files; change the source page
  (only if it is yours) or ask in your report.
- `film/assets/` — shared: `vendor/gsap.min.js`, `twin3d.bundle.js` (`PHX_TWIN.createTwin`), `phx-film.js`
  (`PHXF.box, camTo, count, type, draw, mountTwin, driveTwin, CURSOR`), `fonts/` (Manrope, JetBrains Mono
  woff2), `img/phalanx-logo.svg`. Put act-specific assets in `film/assets/<act>/`. Do not edit shared files;
  if you need a helper, define it in your act file.
- Motion-graphic scenes (non-UI) are written directly in your act file (or as `film/scenes/<act>-<shot>.html`
  sub-compositions if they are big). Use inline SVG and HTML; no images from the internet.

## Hard rules

1. **White film.** Background is white (#FFFFFF) in every frame; the faint blueprint grid (#EFEFEC, 48 px) is
   allowed. No dark screens, no dark overlays, no black flashes, no vignettes. Black (#0B0D10) only for type,
   thin lines, small buttons and badges. One accent #E8743B; SCIR/priority colours only with meaning
   (`video/screens/assets/app.css` tokens).
2. **Deterministic.** No `Date.now`, `performance.now`, `requestAnimationFrame`, `setTimeout`, unseeded
   `Math.random` (use a seeded LCG), no network. No CSS `transition`. Prefer `fromTo`. Measure geometry once
   before tweens (`PHXF.box`). The twin renders only through `PHXF.driveTwin`.
3. **Timing comes from `edit/timing.json`.** Shot S starts at `shots[S].act_start` (seconds within your act)
   and lasts `shots[S].dur`; narration for S starts at `vo_at_in_act`. Word timings are in
   `video/edit/vo/<S>.tokens.json` (seconds from the start of that shot's narration): land key reveals on the
   spoken word (e.g. a counter hits its value as the number is said). Your act's root duration must equal the
   act's `dur` exactly (to the frame).
4. **Narration is not in your render** (assembly adds VO, music and captions). Keep the bottom 150 px free of
   essential text in motion-graphic frames (captions sit there); UI shots may run under captions.
5. **Numbers.** Only numbers that appear in `STORYBOARD.md`, `screens/SPEC.md`, the frozen screens or the
   data files. Never invent.
6. **Maths inserts.** S25 (whole shot), the first 4.2 s of S28 and the first 3.6 s of S29 are Manim clips laid
   over your render in assembly: leave those windows as clean white frames (no content), and make your
   adjacent shots transition into/out of white.

## Motion language

- **Ease:** entrances `power3.out` 0.45–0.7 s; exits `power2.in` 0.3–0.4 s; camera `expo.inOut` 1.0–1.6 s or
  `power2.inOut` for slow drifts; never linear except for typing, data streams and continuous drifts.
- **Camera on UI:** wrap each mounted screen in a `.cam` div (`transform-origin: 0 0`) and tween
  `{scale, x, y}` with `PHXF.camTo(box, s)`. Push-ins 1.4×–2.4×; always keep a slow drift (≈ 2 % per 3 s) so
  no frame is static for more than ~1.5 s. Clamp so the stage edge is never exposed.
- **Focus:** when pushing into a region, softly fade the rest: an overlay of white at 0–55 % opacity with a
  rounded "spotlight" cut-out (CSS `mask` or an SVG with a hole), plus an accent 2 px ring that draws on.
- **Cursor:** `PHXF.CURSOR` SVG; moves on `power2.inOut` arcs, clicks as a 0.12 s scale dip + accent ring
  ripple (r 0→28 px, opacity .5→0). Typing: `PHXF.type` at ~22 chars/s.
- **Transitions between shots** (pick the one that carries meaning): match-cut on a shared element
  (planform → planform; chip → panel), push-through (scale 1→1.06 + crossfade 0.5 s), white wipe with a soft
  12 px feathered edge, or a camera move that travels to the next element. Avoid generic dissolves.
- **Type in motion frames:** Manrope. Kicker 22 px 700 uppercase tracking .14em in accent; headline
  64–88 px 650 tracking −0.03em; body 30–36 px 500 ink-2; numbers 96–160 px 650 tabular. JetBrains Mono for
  ids, codes, hashes, equations-as-code and axis labels (18–24 px).
- **Illustration:** blueprint line art — 1.2–2 px ink strokes, dimension lines with ticks, station
  callouts, accent for the subject, blue #2563C9 for data lineage/evidence. Draw-on with `PHXF.draw`.
  Diagrams build piece by piece in step with narration; each new node pulses once (scale 1→1.04→1, accent
  ring) then settles.
- **Data streams:** real series from `video/data/telemetry_TJ212_1hz.csv` (or `screens/assets/data.js` →
  `PHX_DATA.tel_TJ212_10s`) — never sine waves pretending to be data.
- Each shot ends cleanly on its last beat; no element should pop off without an exit.

## Render & check

```sh
cd video/film
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_NO_UPDATE_CHECK=1
npx hyperframes lint
npx hyperframes snapshot --composition <act>.html --at 2.0,5.5,9.0 --no-end --output ../renders/snap-<act>   # stills
npx hyperframes render --composition <act>.html --quality high --no-experimental-fast-capture --output ../renders/<act>.mp4
```
Render at most one full act at a time. After rendering, extract one frame per shot (mid-point) and at every
transition with ffmpeg, **Read them**, and fix anything clipped, misaligned, static, dark or illegible.
Verify duration/fps with ffprobe (must equal the act duration, 30 fps, 1920×1080).
