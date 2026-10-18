# HeyGen HyperFrames: evaluation for the Phalanx launch video

*Researched and tested 2026-10-16 on an Apple M4 with 16 GB RAM, macOS 26.2 and Node 22.16.0. Sandbox: `video/tools/hyperframes-sandbox/`.*

## 1. Verdict

**Use HyperFrames for every product-UI scene, diagram, title, lower-third and caption overlay in the
launch video.** Use Manim for maths and ffmpeg for final assembly.

- Each product screen can stay a standalone 1920×1080 HTML page with its own CSS. HyperFrames mounts it as a
  *full-document sub-composition*, and one "director" timeline drives everything: camera push-ins,
  a cursor and click, typing into an `<input>`, count-ups, progress bars, row highlights, SVG
  draw-ons and crossfades. All of this was rendered and checked frame by frame (§6).
- On this Mac, ordinary UI scenes render in **about 0.6 s per second of video** (60 s → 33–35 s). Short
  clips cost more because of a fixed 2–4 s of startup. With default flags, one render took about twice as long,
  because the experimental fast-capture path failed its self-check and the whole capture was redone. Pass
  `--no-experimental-fast-capture` (§8).
- Output is deterministic. Three 60 s DOM-only renders were byte-identical MP4s. Scenes with video
  layers or WebGL differ between runs by at most 1/255 on a few pixels, which nobody can see.
- Nothing blocks us. There are three operational traps (§10): `init` installs agent skills, `preview`
  rewrites source files, and telemetry is on by default. Run everything with
  `HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_NO_UPDATE_CHECK=1`.

## 2. What it is, licence, versions

| Item | Value |
|---|---|
| What | Open-source framework that turns HTML + CSS + seekable animation + media into video. Headless Chrome seeks frame by frame, then FFmpeg encodes and mixes audio. "Write HTML. Render video. Built for agents." It is HeyGen's rendering engine and is separate from their avatar product. |
| Repo | https://github.com/heygen-com/hyperframes. Created 2026-03-10, about 64k stars, very active (HEAD `cea8aa8`, 2026-10-15) |
| Licence | **Apache-2.0**: no per-render fees and no commercial thresholds. GSAP, its main animation library, uses the separate *GSAP Standard "no charge" licence*, which is free including commercial use but is not OSI-approved. three.js is MIT. |
| npm | `hyperframes` (CLI). It bundles `@hyperframes/core`, `/engine` and `/producer`. Other packages: `@hyperframes/player`, `/studio`, `/shader-transitions`, `/aws-lambda`. |
| Installed here | `hyperframes@0.8.162` (npm `latest`, published the same day), `gsap@3.14.2`, `three@0.181.2`. All are local in the sandbox; nothing is global. Lockfile: `video/tools/hyperframes-sandbox/package-lock.json`. |
| Render browser | `chrome-headless-shell` 152.0.7977.30, already cached in `~/.cache/hyperframes/chrome` from an earlier run on this machine. `doctor` also lists a Puppeteer 150 build. |
| FFmpeg | Tested with 8.1.2 and then 9.0.2. A separate `brew upgrade ffmpeg` (not started by this task) ran while we were working. For about two minutes ffmpeg was broken (missing `libx265.216.dylib`) and HyperFrames reported "FFmpeg cannot start". Everything was re-rendered successfully on 9.0.2. |
| Requirements | Node ≥ 22, FFmpeg. Docker is optional, for pinned and reproducible renders. It is installed but was not running, so it was not tested. |
| Docs | https://hyperframes.heygen.com (introduction, concepts, guides, CLI reference), https://hyperframes.dev (playground/studio). The docs are also in the repo under `docs/` and `skills/`. |

## 3. How a composition is written

- **A composition is an HTML file.** The root element carries `data-composition-id`, `data-start="0"`,
  `data-width`, `data-height` and usually `data-duration`. The root `data-duration` *is* the render length.
  It is read at compile time, so scripts and variables cannot change it.
- **Timed elements** (clips) carry `id`, `data-start`, `data-duration` and optionally `data-track-index`, plus
  `class="clip"` for DOM and image clips.
  - The runtime shows and hides clips by their time window, so do not tween `visibility`, `display` or `autoAlpha` on a `.clip`.
  - `data-start` also accepts relative references: `"intro"`, `"intro + 0.5"`, `"intro - 0.5"`.
  - `data-track-index` only sets the Studio lane. Paint order comes from CSS `z-index`.
- **Media.**
  - `<video>`: give it `muted`, or `data-has-audio="true"` if its sound should be heard.
  - `<audio>`: an `id` is mandatory. Without one the mixer ignores it and the render is silent.
  - Both accept `data-media-start` (trim), `data-volume` (0–3.98), `data-fade-in`/`data-fade-out` and `data-playback-rate`.
  - Images are clips too (default 3 s).
  - The framework owns media playback. Never call `play()`, `pause()` or set `currentTime`.
  - To move or resize a video, animate a wrapper element, not the `<video>`.
  - A `<video data-start>` must not sit inside another plain element that has `data-start` (lint error).
- **Sub-compositions.** A host element `<div data-composition-id="x" data-composition-src="path.html" data-start=…
  data-duration=…>` mounts another file. The file can be:
  - a `<template>`, the documented form, in which case its styles and scripts must sit inside the template;
  - a **plain full HTML document**, in which case the loader takes `<body>` and the `<head>` styles. This is what makes standalone screen pages work.

  Other rules:
  - The CSS of a sub-composition is **automatically scoped** with PostCSS to `[data-composition-id="x"]`. Bare `body`, `html` and `:root` selectors are remapped to the composition box. `*` is left unscoped.
  - Each nested composition keeps its own time. A child timeline holds its last frame if the host slot is longer.
  - Paths resolve from the project root.
  - Variables: declare them in `data-composition-variables`, set per-instance values with `data-variable-values`, and read them with `__hyperframes.getVariables()`. They can also be overridden at render time with `--variables` or `--batch`.
- **Determinism rules.**
  - Not allowed: `Date.now()`, `performance.now()`, `requestAnimationFrame`, unseeded `Math.random()`, fetching data mid-render, and hover/scroll/focus state.
  - Measure geometry once, at build time, not inside tween callbacks.
  - Infinite repeats are only allowed under a finite root duration.
  - Load every asset before frame 0. The runtime waits for fonts, media, `__tailwindReady` and three.js `DefaultLoadingManager`. Extra waits can be registered on `window.__hf.buildReady`.

## 4. How animation is driven

- **GSAP is the main runtime.** Create exactly one `gsap.timeline({ paused: true })` per composition and
  register it as `window.__timelines["<composition-id>"] = tl`.
  - The key must match the composition ID.
  - Register only after every tween has been added; asynchronous builds, such as after `document.fonts.load`, are allowed.
  - HyperFrames seeks the timeline to `frame / fps` for every frame and never plays it.
  - `onUpdate` callbacks fire on seek. That is how count-ups, typing and canvas redraws work deterministically.
  - Prefer `fromTo()`, which seeks safely in both directions.
  - Never combine a CSS initial `transform` with a GSAP tween of the same property (lint `gsap_css_transform_conflict`).
- **Other adapters are seeked automatically:**
  - CSS `@keyframes` animations, best with a finite iteration count and `animation-fill-mode: both`;
  - WAAPI, Anime.js, Lottie, TypeGPU, maps (Mapbox, Leaflet, …) and d3;
  - **three.js**: the adapter dispatches an `hf-seek` event with `detail.time` and sets `window.__hfThreeTime`. Your code renders the scene at that time. A three.js composition needs an explicit root `data-duration`.
- **CSS `transition` is not seekable.** It runs on the browser clock, and lint reports it as `css_transition_used`. Screens built for the web often
  carry hover transitions. They are harmless while nothing changes state, but any property GSAP tweens must not also have a CSS
  transition. Give video screens `transition: none`.
- A lower-level `FrameAdapter` interface (`init / getDurationFrames / seekFrame / destroy`) exists for custom
  runtimes. It is marked as experimental v0.

## 5. Media, fonts, transitions, captions, output

- **Video and images** decode frame-accurately. The testsrc2 timecode burned into the clip matched the
  composition time exactly (clip starting at 2.4 s: 0.267 at 2.65 s, 1.200 at 3.6 s, 2.200 at 4.6 s).
  - Source frames are extracted with FFmpeg (`--video-frame-format png` is available for colour-critical UI recordings).
  - HEVC and ProRes sources get browser proxies for preview.
  - **Alpha video inputs work**: both a VP9-alpha WebM and a ProRes 4444 MOV composited with real transparency.
- **Audio**: `<audio>` and audible `<video>` tracks are mixed by FFmpeg into AAC 48 kHz stereo. The WAV track was verified
  in the output, and repeat renders produced bit-identical audio. Mixing extras: per-clip effect chains, ducking ("voiceover carve"),
  automation envelopes and `<hf-audio-group>` buses.
- **Fonts**:
  - 18 families are resolved deterministically, among them Inter, Roboto, Montserrat, JetBrains Mono, IBM Plex Mono and Space Mono. They are fetched from Google Fonts at compile time, cached in `~/.cache/hyperframes/fonts`, and inlined as woff2. We saw "Fetched 11 font faces for Inter from Google Fonts".
  - Other Google fonts are fetched implicitly, with a lint warning.
  - Local `@font-face` woff2 files are embedded. This was tested with `assets/fonts/sandbox-local-mono-700.woff2`.
  - Locally installed system fonts are captured during local renders.
  - Gotcha: `Helvetica`, `Helvetica Neue` and `Arial` are **aliased to Inter**, and `Segoe UI` to Roboto.
  - **For our screens:** ship their fonts as local woff2 `@font-face` so the first render needs no network and output does not depend on the machine.
- **Transitions**:
  - CSS/GSAP transitions are written by hand: crossfade, push, wipe (clip-path), blur, zoom and so on. A clip-path wipe and an opacity crossfade were both tested.
  - `@hyperframes/shader-transitions` adds WebGL shader transitions (whip pan, cross-warp, glitch, light leak, and more).
  - The registry has 447 items (210 blocks, 237 components), installed with `npx hyperframes add <name>`. Examples: `transitions-*`, `directional-wipe`, `fade-through`, `iris-reveal`, `zoom-through-transition`, `push-in`, `ui-focus-zoom`, `count-up`, `agent-cursor`, `cursor-*`, `data-chart`, `flowchart`, `yt-lower-third`, and 20 `caption-*` styles.
- **Captions**:
  - Captions are ordinary timed HTML. `hyperframes transcribe` produces word-level timestamps with whisper-cpp, which is not installed here (`brew install whisper-cpp`), or imports an existing transcript. `init --video/--audio` patches captions in automatically.
  - Caption components come from the registry; the skills are `/embedded-captions` and `/talking-head-recut`.
  - Not exercised beyond a hand-written lower-third.
- **Output**:
  - `--format mp4|webm|mov|gif|png-sequence|hls`.
    - MP4 is H.264 yuv420p (High profile) with AAC.
    - WebM is VP9, **with alpha**.
    - MOV is **ProRes 4444 with alpha** (yuva444p12le). Verified: alpha was intact over a blue background.
    - `png-sequence` writes RGBA frames plus `audio.m4a`.
  - `--fps` accepts 1–240 or a rational such as `30000/1001`. The default is the root `data-fps`, otherwise 30.
  - `--resolution` supersamples, for example 1080p → 4K through `deviceScaleFactor`.
  - `--quality draft|standard|looks|high|delivery`:
    - `draft`: CRF 28, ultrafast;
    - `standard`: CRF 18, medium;
    - `looks`: the default, CRF 16;
    - `high` = `delivery`: CRF 15, slow.
  - `--crf` and `--video-bitrate` set the encoder directly. `--gpu` uses a hardware encoder (VideoToolbox on macOS; not tested).
  - Also available: `--hdr` (HDR10 MP4) and `--docker` (pinned Chrome, fonts and FFmpeg).
  - MP4 renders capture JPEG frames at quality 100 (80 for draft). Alpha outputs capture PNG.
  - Output files carry `hyperframes_renderer` and `hyperframes_version` container tags. Strip them with `-map_metadata -1`.

## 6. What we built and verified

All renders are at 1920×1080 and 30 fps. Frames were extracted with ffmpeg and inspected by eye. Evidence is in
`out/frames/` and `out/snap-screen/contact-sheet.jpg`.

| Test | Project | Result |
|---|---|---|
| White UI screen with sidebar, KPI cards and a table; camera push-in to one card (scale 2.1 with a measured translate), hold, pull back | `smoke/` | ✅ Text stays crisp when scaled. It is re-rasterised, not a scaled bitmap. |
| Count-up (0 → 78.4 %), progress bar `scaleX`, table-row highlight | `smoke/`, `screen-pattern/` | ✅ |
| Title fade and slide in (`power3.out`), then out | `smoke/` | ✅ |
| SVG paths drawing on (`strokeDashoffset`, staggered) and a pulsing node (`yoyo`, finite repeat) | `smoke/` | ✅ |
| Embedded MP4 clip (testsrc2), frame-accurate | `smoke/` | ✅ |
| Transparent overlays: VP9-alpha WebM **and** ProRes 4444 MOV | `smoke/` | ✅ both transparent |
| Audio track (440 Hz WAV) | `smoke/` | ✅ AAC stereo, 5.0 s, about −30 dB as expected |
| Clip-path wipe from scene A to scene B, including scene B's media | `smoke/` | ✅ |
| 2D canvas redrawn from a GSAP `onUpdate` proxy | `smoke/` | ✅ |
| three.js `TorusKnot` (WebGL) driven by `hf-seek` | `smoke/` | ✅ Works on the hardware GPU (ANGLE Metal) and with `--no-browser-gpu` (SwiftShader). The two look the same. |
| Local woff2 `@font-face` | `smoke/` | ✅ |
| **Standalone screen pages mounted as sub-compositions, animated from the parent** | `screen-pattern/` | ✅ See §7. Lint has 0 errors; `check` passes (runtime 0 errors, contrast 99/99). |
| Two screens using the **same class names** with opposite themes in one video | `screen-pattern/` | ✅ No CSS leakage in either direction |
| Same screen in an `<iframe>`, with the parent GSAP reaching into `contentDocument` | `iframe-pattern/` | ✅ Works, but forces screenshot capture and lies outside the HyperFrames font and asset pipeline. Not recommended. |
| Transparent lower-third rendered to WebM and MOV | `alpha-overlay/` | ✅ Alpha verified with the libvpx-vp9 decoder and composited over blue |
| 60 s throughput benchmark | `perf/` | ✅ See §8 |

## 7. The recommended pattern for product screens

**Screens are plain pages. Each video segment has one "director" `index.html` that mounts screens as full-document
sub-compositions and owns all motion in a single GSAP timeline.**

```
segment-xx/
  index.html                 ← director: camera wrappers, cursor, captions, ONE paused GSAP timeline
  screens/fleet-overview.html  ← product screen: normal standalone page, own <style>, no scripts
  screens/tail-health.html
  assets/vendor/gsap.min.js   ← vendored (no CDN at render time)
  assets/fonts/*.woff2        ← local @font-face for the screens' fonts
```

**Screen page.** It opens fine in any browser by itself. The only HyperFrames-specific part is the attributes on the root element:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <style>
      /* Generic selectors are fine: HyperFrames scopes them to [data-composition-id="fleet-overview"].
         body/html/:root are remapped to the composition box; `*` is NOT scoped (keep it to resets). */
      * { box-sizing: border-box; }
      body { margin: 0; background: #f5f7fb; font-family: Inter, sans-serif; }
      #app { position: relative; width: 1920px; height: 1080px; display: grid; grid-template-columns: 280px 1fr; }
      .card { border: 1px solid #e3e7ee; border-radius: 16px; /* NO css `transition:` on tweened props */ }
    </style>
  </head>
  <body>
    <!-- The only HF bits: id must match the host's data-composition-id; data-no-timeline = "the parent drives me" -->
    <div id="app" data-composition-id="fleet-overview" data-width="1920" data-height="1080" data-no-timeline>
      … sidebar, <input id="fo-search-input">, KPI <span id="fo-avail-num">78.4</span>, <i id="fo-avail-bar">, <tr id="fo-row-2"> …
    </div>
  </body>
</html>
```

**Director `index.html`.** This is condensed from `screen-pattern/index.html`, which renders.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <script src="assets/vendor/gsap.min.js"></script>            <!-- vendored, not CDN -->
  <style>
    html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #0b1220; }
    #root { position: relative; width: 100%; height: 100%; overflow: hidden; }
    .cam  { position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; transform-origin: 0 0; } /* camera */
    .screen-host { position: absolute; inset: 0; }
  </style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="10" data-width="1920" data-height="1080">
  <!-- Untimed camera wrapper around a TIMED host. data-layout-allow-overflow silences `check` while pushed in. -->
  <div id="cam-1" class="cam" data-layout-allow-overflow>
    <div id="scene-fleet" class="screen-host"
         data-composition-id="fleet-overview"                 
         data-composition-src="screens/fleet-overview.html"   
         data-start="0" data-duration="5.6" data-track-index="0"
         data-width="1920" data-height="1080" data-no-timeline></div>
  </div>
  <div id="cam-2" class="cam" data-layout-allow-overflow>
    <div id="scene-tail" class="screen-host" data-composition-id="tail-health"
         data-composition-src="screens/tail-health.html"
         data-start="5" data-duration="5" data-track-index="1"
         data-width="1920" data-height="1080" data-no-timeline></div>
  </div>
  <svg id="cursor" class="clip" data-start="0" data-duration="5" data-track-index="2">…</svg>
</div>
<script>
  const $ = (s) => document.querySelector(s);   // screen DOM is already inlined when this runs
  // 1) MEASURE ONCE, before any tween applies a transform (fromTo renders its from-state immediately).
  const box = (el) => { const r = el.getBoundingClientRect(); return { cx: r.left + r.width / 2, cy: r.top + r.height / 2, x: r.left }; };
  const camTo = (b, s) => ({ scale: s, x: 960 - b.cx * s, y: 540 - b.cy * s }); // centre target at scale s
  const row2 = box($("#fo-row-2")), search = box($("#fo-search"));
  const input = $("#fo-search-input");

  const tl = gsap.timeline({ paused: true });      // 2) ONE paused timeline
  // count-up + progress bar: proxy tween, onUpdate writes text (fires on every seek -> deterministic)
  const k = { v: 0 };
  tl.fromTo(k, { v: 0 }, { v: 78.4, duration: 1, ease: "power2.out",
    onUpdate: () => { $("#fo-avail-num").textContent = k.v.toFixed(1); } }, 0.5);
  tl.fromTo("#fo-avail-bar", { scaleX: 0 }, { scaleX: 0.784, duration: 1, ease: "power2.out" }, 0.5);
  // cursor + click + focus ring (tl.set is seek-safe; class toggles are not)
  tl.fromTo("#cursor", { x: 1500, y: 900 }, { x: search.x + 60, y: search.cy, duration: 0.9, ease: "power2.inOut" }, 0.7);
  tl.set("#fo-search", { borderColor: "#2563eb", boxShadow: "0 0 0 4px rgba(37,99,235,.15)" }, 1.66);
  // typing into an <input>
  const q = "T-04 fuel pump", t = { n: 0 };
  tl.fromTo(t, { n: 0 }, { n: q.length, duration: 1, ease: "none",
    onUpdate: () => { input.value = q.slice(0, Math.round(t.n)); } }, 1.8);
  // row highlight + dim the others
  tl.fromTo("#fo-row-2 td", { backgroundColor: "rgba(254,243,199,0)" }, { backgroundColor: "rgba(254,243,199,1)", duration: 0.35 }, 2.9);
  tl.fromTo(["#fo-row-1", "#fo-row-3"], { opacity: 1 }, { opacity: 0.35, duration: 0.35 }, 2.9);
  // camera push-in on the row (later camera tweens on the same wrapper: immediateRender:false)
  tl.fromTo("#cam-1", { scale: 1, x: 0, y: 0 }, { ...camTo(row2, 1.7), duration: 1, ease: "power3.inOut", immediateRender: false }, 3.2);
  // crossfade to the next screen (both hosts overlap 5.0–5.6 s)
  tl.fromTo("#cam-2", { opacity: 0, scale: 1.06 }, { opacity: 1, scale: 1, duration: 0.6, ease: "power2.out" }, 5.0);

  window.__timelines["main"] = tl;                 // 3) register LAST, key == data-composition-id
</script>
</body></html>
```

Why this pattern:

- Screens stay reusable as design artefacts. You can open them, review them and screenshot them directly.
- HyperFrames scopes the CSS of each screen.
- The compiler inlines sub-compositions before the director script runs. Preview, `snapshot`, `check` and `render` all bundle the same way (`bundleToSingleHtml`). That is why parent selectors like `#fo-row-2` resolve.

Requirements for this to work:

- Element IDs must be unique across all screens in a segment. Prefix them per screen (`fo-…`, `th-…`).
- Camera framing has to be clamped by you. A push-in that centres an element near an edge exposes the background beyond the page; the iframe test shows this.

**Alternatives we tested and rejected:**

- **iframe.** It works: the parent GSAP can tween elements in a same-origin `contentDocument`, and the camera moves the iframe wrapper. But it forces screenshot capture, disables static-frame dedup, sits outside the font embedding and asset rewriting, and triggers lint warnings. Use it only for a page that cannot be edited at all.
- **Inlining screen markup by hand** is unnecessary, because the full-document mount does the same thing.
- **A per-screen timeline inside the screen file** (the documented `<template>` sub-composition) is still worth using when a screen
  needs complex self-contained motion. The cost is that screens stop being plain pages.

## 8. Measured performance

All runs are local with hardware GPU and screenshot capture. On macOS, multi-worker capture is always screenshot-based.
Each run picked 4 workers automatically. "Render" is the CLI's own figure; add about 1–2 s for `npx` startup.

| Composition | Video | Settings | Render | Seconds of render per second of video |
|---|---|---|---|---|
| `smoke/` (UI, camera, SVG, MP4, 2 alpha overlays, WAV, three.js, canvas) | 5 s | standard, first run (compile 3.8 s incl. Google-Fonts fetch) | 11.9 s | 2.4 |
| `smoke/` | 5 s | high, warm cache | 12.0 s | 2.4 (about 3–4 s of fixed compile and setup; capture 4.8 s, encode 3.4 s) |
| `screen-pattern/` (2 mounted screens, director timeline) | 10 s | standard / high | 9.2 s / 8.8–11.5 s | 0.9–1.15 |
| `screen-pattern/` | 10 s | **draft** | 17.9 s | 1.8 (draft takes a different streaming path and was *slower*) |
| `perf/` (12 × 5 s dashboard scenes, continuous motion) | 60 s | standard, **default flags** | 67.4 s / 78.4 s | 1.1–1.3 |
| `perf/` | 60 s | standard, `--no-experimental-fast-capture` | 35.1 s | **0.58** |
| `perf/` | 60 s | high, `--no-experimental-fast-capture` | 33.4 s | **0.56** |
| `alpha-overlay/` → WebM / MOV | 2 s | default | 7.1 s / 6.5 s | mostly fixed overhead |

- **Fast-capture trap.** By default the CLI tries Chrome `drawElementImage` capture. On `perf/` its
  self-verification failed at frame 1710 (25.5 dB against a 32 dB threshold), so the whole capture was redone with screenshots, adding about 32–37 s.
  Pass `--no-experimental-fast-capture`, or set `PRODUCER_EXPERIMENTAL_FAST_CAPTURE=false`, for predictable timings.
  Fast capture is also switched off automatically when WebGL or an iframe is present.
- **Projection.** A 4-minute video made entirely of UI scenes would take roughly 2.5–3 minutes of rendering on this Mac. Rendering per segment of 10–40 s
  keeps iteration around 10–25 s. `snapshot --at …` takes stills in seconds, with no encode.
- **Resources.** Temporary disk use for the 60 s render peaked at about 0.3 GB, because frames are JPEG. Each worker is one Chrome (about 256 MB). Below 8 GB of RAM the CLI
  switches to `--low-memory-mode` on its own.

## 9. Determinism

| Comparison | Result |
|---|---|
| `perf/` 60 s MP4, rendered 3 times (one with fast-capture fallback, two without) | **Byte-identical files** (same MD5) |
| `smoke/` lossless PNG sequence, run A against run B, same settings | 132 of 150 frames bit-identical. 18 frames (all after the wipe, with video and alpha layers) differ by at most **1/255** on a handful of pixels. |
| `smoke/` PNG sequence with 4 workers against 1 worker | 24 frames differ by at most 1/255, on one anti-aliased edge line during the 2.1× push-in |
| three.js canvas region, run A against run B | **0** differing frames. Three frames differ against the 1-worker run, at most 1/255. |
| Audio, across 4 renders | Bit-identical |
| Hardware GPU against SwiftShader (`--no-browser-gpu`) | Every pixel differs slightly, but the images look the same. Pick one mode and keep it for the whole project. |

For bit-exact output on any machine, the docs prescribe `render --docker`, which pins Chrome, fonts and FFmpeg.
Docker Desktop was not running here, so this was not tested.

## 10. Limitations and gotchas

1. **`init` installs agent skills.** After scaffolding it installs the HyperFrames core skills from GitHub into every agent it detects.
   It also writes agent instruction files into the project, telling agents to install more skills.
   - We ran with `HYPERFRAMES_SKIP_SKILLS=1`, deleted the generated the generated agent instruction file, and kept `smoke/AGENTS.md` for reference.
   - No HyperFrames skills or plugins are installed on this machine. `the local skills folder` contains only graphify and scroll-world.
2. **`preview` (Studio) changes source files.** On start it stamps `data-hf-id="hf-xxxx"` onto every element of
   `index.html` **and of every mounted screen file**, and records them in `.hyperframes/hf-ids-stamped.json`. These stamps were stripped again
   from the sandbox. `render`, `snapshot`, `check` and `lint` do not do this. Preview a copy, or accept the attribute churn.
3. **Telemetry is on by default.** It covers command names, render stats, OS and CPU, and which coding agent is in use. Disable it with `HYPERFRAMES_NO_TELEMETRY=1`
   or `npx hyperframes telemetry disable`. This machine's `~/.hyperframes/config.json` already had it disabled. There is also an
   auto-update check: `HYPERFRAMES_NO_UPDATE_CHECK=1`. `snapshot --describe` sends frames to Gemini when
   `GEMINI_API_KEY` is set.
4. The **experimental fast capture** can silently double render time (§8).
5. **Shared state outside the repo:** Chrome cache (`~/.cache/hyperframes/chrome`), font cache (`~/.cache/hyperframes/fonts`),
   config (`~/.hyperframes/`), extract cache (`$TMPDIR/hyperframes-extract-cache-501`), preview state
   (`~/.local/state/hyperframes/`). `npx hyperframes clean` prunes leftovers.
6. **Network at compile time.** The template loads GSAP from jsDelivr, and named fonts come from Google Fonts on first use. Vendor GSAP
   (done in the sandbox) and use local woff2 to render offline. Cloud and Lambda renders fail closed if Google Fonts is unreachable.
7. **Lint rules that bite UI scenes:**
   - `css_transition_used` (CSS transitions are not seekable);
   - `gsap_css_transform_conflict`;
   - `gsap_animates_clip_element`;
   - `video_nested_in_timed_element`;
   - `media_missing_id` (silent audio);
   - `missing_data_no_timeline`: a composition that never registers a timeline makes every render wait out the 45 s ready timeout;
   - `multiple_root_compositions`: only one root HTML per project, which is why `iframe-pattern/` is its own project.

   Some warnings are noise: `nested_structure_needs_subcomposition`, which is about the Studio timeline layout, and
   `gsap_repeated_fromto_without_baseline` on separate proxy objects.
8. **Camera targets** must be measured at build time, before the first `fromTo` sets a transform. Never call `getBoundingClientRect` inside `onUpdate`, because the renderer seeks out of order across workers.
9. **Fonts:** `Helvetica` and `Arial` are silently replaced by Inter. 18 families are guaranteed, and only in the weights listed.
10. **WebGL** works, but switches capture to screenshots. Under WSL or Linux without a GPU it falls back to slower software
    rendering. macOS is fine.
11. **Docs and version drift.** The release cadence is several per day (0.8.162; 516 versions). Pin the exact version, which the
    sandbox does, and read `npx hyperframes <cmd> --help`, because it is the authority. Some docs disagree slightly; for example, the bundled fonts
    are described as "pre-bundled" but were fetched from Google on first use.
12. **The root `data-duration` is fixed at compile time.** Scripts and variables cannot change the length of a render.
13. **v0.9 data honesty (our rule, not theirs).** Every number on screen in these test scenes is synthetic. Real scenes must
    label Phalanx values as synthetic or not validated, as `RULES.md` requires.

## 11. Where HyperFrames fits in our pipeline

| Use HyperFrames for | Use something else for |
|---|---|
| Every **product UI scene**: screens mounted as sub-compositions, camera moves, cursor and clicks, typing, count-ups, highlights, state changes | **Maths and model explanations** (equations, derivations, survival or hazard curves with mathematical semantics): **Manim**. Its clip can be dropped into a HyperFrames scene as a `<video>`, which is frame-accurate. |
| **Diagrams and architecture flows** (SVG draw-ons, pulsing nodes, data-flow arrows) and **charts** (GSAP or registry `data-chart`) | **Final assembly** (concat segment renders, voiceover and music mix, loudness normalisation with `loudnorm`, one final encode, metadata strip): **ffmpeg**, which is simpler, faster and scriptable. |
| **Title cards, lower-thirds, captions** as transparent **WebM or ProRes 4444** overlays when they must sit over Manim or other footage | Long, untouched screen recordings, if we have any: pass them through ffmpeg rather than re-capturing them in Chrome. |
| Transitions *inside* a segment (crossfade, wipe, push, shader transitions) | Cuts between segments: a plain concat, or an ffmpeg `xfade` if a transition is wanted. |

**Suggested flow:**

1. Write each segment of about 10–40 s as one HyperFrames project or director composition.
2. Render it with `--quality high --no-experimental-fast-capture` to MP4. Use CRF 15 or lower with `--crf 10`. Use ProRes MOV when the segment needs alpha or another generation of editing.
3. Render Manim clips separately.
4. Run an ffmpeg assembly script that concatenates the segments, mixes voiceover and music, normalises loudness and makes the single final H.264 encode.

Do one segment end to end before building the rest.

HyperFrames *could* also be the master timeline. It mixes audio, places Manim MP4s frame-accurately and has `--batch`. But
re-capturing a 4-minute timeline in Chrome on every tweak is slower than re-encoding with ffmpeg, so keep it per segment.

## 12. Exact commands that worked

```bash
cd /Users/abishaikc/Phalanx-Solution/video/tools/hyperframes-sandbox
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_NO_UPDATE_CHECK=1

npm install --save-exact hyperframes@0.8.162 gsap@3.14.2 three@0.181.2   # local only
npx hyperframes --version                    # 0.8.162
npx hyperframes doctor                       # Node/FFmpeg/Chrome/disk check
npx hyperframes init smoke --non-interactive --resolution landscape     # scaffold (then vendor GSAP)

cd screen-pattern
npx hyperframes lint                         # static contract
npx hyperframes check                        # browser gate: runtime + layout + motion + contrast
npx hyperframes compositions                 # lists main + mounted screens
npx hyperframes snapshot --at 1.2,3.1,5.3,9.5 --no-end --output ../out/snap-screen   # stills + contact sheet
npx hyperframes render --quality high --no-experimental-fast-capture --output ../out/screen-pattern.mp4

# other formats
npx hyperframes render --format webm --output ../out/lt.webm            # VP9 + alpha
npx hyperframes render --format mov  --output ../out/lt.mov             # ProRes 4444 + alpha
npx hyperframes render --format png-sequence --output ../out/seq        # lossless RGBA frames + audio.m4a
npx hyperframes render --composition other.html --output x.mp4          # non-index standalone composition

# verification
ffprobe -v error -show_entries format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,sample_rate,channels -of compact out.mp4
ffmpeg -ss 3.6 -i out.mp4 -frames:v 1 frame.png
ffmpeg -c:v libvpx-vp9 -i lt.webm -frames:v 1 -pix_fmt rgba alpha_check.png   # alpha-aware VP9 decode
```

Shortcuts (from `package.json`): `npm run render:smoke`, `render:screens`, `snapshot:screens`, `render:iframe`,
`render:perf`, `render:overlay-webm`, `render:overlay-mov`, `doctor`.

## 13. Sandbox layout (kept for reuse)

```
video/tools/hyperframes-sandbox/
  package.json, package-lock.json   pinned hyperframes 0.8.162, gsap 3.14.2, three 0.181.2 + npm scripts
  .gitignore                        node_modules, renders, .hyperframes state, big media in out/
  smoke/            5 s capability smoke test (UI camera, SVG, MP4, alpha WebM+MOV, WAV, wipe, canvas, three.js, local woff2)
  screen-pattern/   ★ recommended pattern: screens/*.html (standalone pages) + director index.html (10 s, 2 screens)
  iframe-pattern/   same screen via <iframe> (works; not recommended)
  alpha-overlay/    transparent lower-third → WebM / ProRes 4444
  perf/             60 s throughput benchmark (seeded, script-generated scenes)
  out/              renders (*.mp4/webm/mov, git-ignored), frames/ (evidence PNGs), snap-screen/ (contact sheet)
```

## Sources

- GitHub repo, README, `docs/` and `skills/`: https://github.com/heygen-com/hyperframes (read at commit `cea8aa8`, 2026-10-15)
- npm package: https://www.npmjs.com/package/hyperframes (`npm view hyperframes`: 0.8.162, Apache-2.0)
- Official docs: https://hyperframes.heygen.com/introduction, `/concepts/compositions`, `/concepts/determinism`,
  `/reference/html-schema`, `/guides/rendering`, `/guides/gsap-animation`, `/guides/performance`, `/guides/troubleshooting`,
  `/packages/cli`, `/reference/lint-rules`
- Skills read in the repo but not installed: `skills/hyperframes-core/SKILL.md`, `skills/hyperframes-core/references/determinism-rules.md`,
  `skills/hyperframes-animation/adapters/{css-animations,three}.md`, `skills/hyperframes-animation/blueprints/camera-journey.md`,
  `skills/hyperframes-animation/transitions/overview.md`, `skills/hyperframes-creative/references/typography.md`
- Source checked to confirm behaviour: `packages/core/src/compiler/compositionScoping.ts` (CSS scoping),
  `packages/core/src/runtime/compositionLoader.ts` (full-document mounts), `packages/core/src/runtime/adapters/three.ts` (`hf-seek`),
  `packages/producer/src/services/htmlCompiler.ts` (iframe forces screenshot mode),
  `packages/producer/src/services/render/captureImageFormat.ts` (JPEG q100 or PNG capture),
  `packages/engine/src/services/chunkEncoder.ts` (quality presets), `packages/cli/src/server/studioServer.ts`
  (preview bundles the same way as render)
- GSAP licence: https://gsap.com/standard-license
