# Launch-video workflow: maths animation, assembly, narration and captions

Status: verified on this Mac (Apple M4, 16 GB, macOS 26.2) on 2026-10-16. Every command below ran as written.
Timings were taken **while other agents were also rendering** (load average 5–10), so they are pessimistic.

Sandboxes: `video/tools/{manim,assembly,tts,align,fonts}`. The Python env is `video/.venv` (CPython 3.12.12 via `uv`).
Model caches are in `video/tools/cache/hf`. Nothing is committed to git.

All numbers, codes, tails and Bayes/Weibull parameters in the sandboxes are **synthetic and illustrative**. They are not
Tejas/F404 data and are not validated physics (see the project's RULES.md rule 8).

---

## 0. Decisions at a glance

| Job | Pick | Licence | Why, in one line |
|---|---|---|---|
| 3Blue1Brown-style maths clips | **Manim Community (ManimCE) 0.22.0** | MIT | Headless Cairo renderer, real LaTeX (`MathTex`, `TransformMatchingTex`), alpha output, active releases |
| LaTeX for Manim | **Homebrew `texlive` 20260301 + `dvisvgm` 3.6.1** | TeX Live mix (free) / GPL-3 | Manim 0.22 groups TeX substrings with `\special{dvisvgm:raw …}`, so only real latex + dvisvgm keeps `set_color_by_tex` and `TransformMatchingTex` working |
| No-LaTeX fallback | `MathTypst` (`manim[typst]`, bundled Typst 0.15) | Apache-2.0 | Verified to render. Use it if TeX Live is ever unavailable |
| Final assembly | **FFmpeg (`ffmpeg-full` 9.0.2, keg-only) driven by `tools/assembly/assemble.py`** (a JSON timeline compiled into one filtergraph) | LGPL/GPL (our script is ours) | Frame-exact, deterministic, fastest. It has the only first-class burned-in captions (libass `.ass`), xfade, overlay with alpha, zoompan, deterministic ducking and loudnorm. An agent edits JSON, not filtergraph strings |
| Secondary / fallback | MoviePy 2.2.1 (verified), plain hand-written ffmpeg | MIT / LGPL | For per-frame Python effects. About 1.6× slower here, and no libass |
| Narration TTS | **Kokoro-82M via `kokoro` 0.9.4 (PyTorch, CPU)** | Apache-2.0 (code, weights **and** voices) | Best permissive-licence quality. Generates 3–8× faster than real time on CPU and returns its own word timestamps |
| Word alignment | **Kokoro's own token timestamps** (primary). **faster-whisper 1.2.1** `small.en` as an independent check, or for any non-TTS voice | MIT | The two agree to a median of about 0.08 s. Captions always show the script text, never the ASR text |
| Captions | `.ass` (phrase per line, current word in accent `#E8743B`) + `.srt`, burned in with libass | — | Brand font (Manrope SemiBold) through `fontsdir` |

**HyperFrames** (separate agent, Apache-2.0) renders the UI scenes to MP4. Manim renders the maths clips.
`assemble.py` stitches them and adds narration, music, ducking and captions. A two-pass `loudnorm` then produces the master.

---

## A. 3Blue1Brown-style programmatic visualisation

### A1. Choosing between options (primary sources)

| | ManimCE (`ManimCommunity/manim`) | ManimGL (`3b1b/manim`) | Motion Canvas | Revideo |
|---|---|---|---|---|
| Licence | MIT | MIT | MIT | MIT |
| Latest | **v0.22.0, 2026-10-08**; active (last push 2026-10-12) | Last release v1.7.2 (2024-12); master active but moving to wgpu/rendercanvas, so release and master diverge | v3.17.2 (2024-12); effectively dormant since 2025-02 | Repo moved to `midrender/revideo`; dormant 2025-02 → 2026-06, revived as v0.11.0 (2026-07-10) |
| Python / runtime | `>=3.11`, classifiers 3.11–3.14 | Python | TypeScript, browser editor | TypeScript + headless Chrome, Node ≥22.12 |
| Headless on macOS | **Yes.** Cairo CPU renderer, no window or GPU (`-l` live preview is the only windowed mode) | Needs an OpenGL context (`moderngl.create_standalone_context`) even with `-w`; fragile headless | **No official headless render** (issues #415, #1218 open) | Yes (`renderVideo()`), but it **sends anonymous render telemetry** |
| Transparent output | `-t`: qtrle `.mov` (argb, lossless) by default; `--format webm` gives VP9 `yuva420p`; ProRes is selectable through `--video-codec` (see the gotcha below) | `-t` gives prores_ks `.mov` | n/a (PNG sequence) | n/a |
| Frame output | `--format png` (last frame), `png-sequence`, `gif`, `mp4`, `webm`, `mov`; `-s`; `--save_sections` | `-s`, PNG | PNG sequence | MP4 |
| Maths typesetting | `MathTex`/`Tex` need latex + **dvisvgm**; or native `Typst`/`MathTypst` (since 0.21) | latex + dvisvgm | MathJax (`mathjax-full`), no TeX needed | MathJax |

**Pick: ManimCE.** It is the only option that is MIT, actively released, headless on macOS without a GPU context,
documented, and able to do real TeX morphs (`TransformMatchingTex`). Manim 0.22 changed the CLI:
`--format` replaces `-g`, `-i` and `--write_to_movie`, and `--video-codec`, `--pixel-format` and `--encoder-option` were added.
Motion Canvas cannot render headless and is dormant. Revideo is viable but adds a browser stack and telemetry, and
HyperFrames already covers the "HTML/TS animation" lane.

### A2. Install (what actually ran)

```sh
cd video
uv venv --python 3.12 .venv                      # 3.12, not 3.14: kokoro/misaki require <3.13 and everything shares one venv
uv pip install --python .venv/bin/python "manim[typst]==0.22.0" "moviepy==2.2.1"
# system deps: cairo 1.18.6, pango 1.58.2, pkgconf 3.0.7 were already present (brew)
HOMEBREW_NO_AUTO_UPDATE=1 brew install texlive ffmpeg-full espeak-ng   # ~6 min; texlive is a 2.2 GB bottle, 4.7 GB installed
HOMEBREW_NO_AUTO_UPDATE=1 brew install dvisvgm                           # NOT included in the texlive formula
.venv/bin/manim checkhealth     # latex PASSED, dvisvgm PASSED (the "manim not on PATH" failure is harmless; call .venv/bin/manim)
```

TeX route options considered:

- **Tectonic** (already installed, 0.16.9) **does not work with Manim 0.22 MathTex as it stands.**
  - Manim only accepts `latex`, `pdflatex`, `luatex`, `lualatex` or `xelatex` as `tex_compiler`.
  - MathTex isolates substrings with `\special{dvisvgm:raw <g id='unique…'>}`, which only dvisvgm understands.
  - A PDF → `pdftocairo` shim would render but break `set_color_by_tex` and `TransformMatchingTex`.
  - Homebrew's `dvisvgm` formula depends on the full `texlive` formula anyway.
  - Native tectonic support is an open issue (#4042) with a PR (#4977) that has not merged.
- **MathJax → SVG → `SVGMobject`**: possible, but wrapping substrings in `\cssId{}` changes TeX spacing (for example around
  `=`). Not worth it.
- **Typst** (`MathTypst`, verified): no TeX at all, and `{{ … : label }}` groups give `eq.select("label")`.
  - Gotcha: write `P("fault" mid(|) "code")`.
  - Gotcha: add `space.thin` between juxtaposed factors.
  - This is the fallback if TeX Live has to go.

### A3. Render settings and commands

`video/tools/manim/manim.cfg` (picked up when you run from that directory):

```ini
[CLI]
pixel_width = 1920
pixel_height = 1080
frame_rate = 30
background_color = #FFFFFF
media_dir = ./media
```

```sh
cd video/tools/manim
../../.venv/bin/manim render smoke_scenes.py WeibullCurves      # → media/videos/smoke_scenes/1080p30/WeibullCurves.mp4
../../.venv/bin/manim render smoke_scenes.py BayesUpdate
../../.venv/bin/manim render smoke_scenes.py BayesEquation
../../.venv/bin/manim render -s smoke_scenes.py BayesEquation   # last frame only, PNG (fast layout check)
# transparent overlays
../../.venv/bin/manim render -t --format mov  -o BayesEquation_alpha_qtrle smoke_scenes.py BayesEquation   # RECOMMENDED: lossless argb
../../.venv/bin/manim render -t --format webm -o BayesEquation_alpha_vp9   smoke_scenes.py BayesEquation   # small (1.6 MB), lossy
# ProRes 4444 for an NLE: transcode the qtrle with ffmpeg (Manim's own ProRes is mis-tagged, see gotchas)
ffmpeg -i BayesEquation_alpha_qtrle.mov -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -alpha_bits 16 -vendor apl0 BayesEquation_alpha_prores4444_ffmpeg.mov
```

Scenes in `smoke_scenes.py` (house style: white paper, ink `#0B0D10`, one accent `#E8743B`, ghost grey `#9AA0A6`):

- `WeibullCurves`: two axes draw on. The left is survival `S(t)=e^{-(t/η)^β}` in ink; the right is hazard `h(t)` in accent. Each has
  a LaTeX label, plus a dot, a dashed guide and a live `DecimalNumber` readout sweeping along `S(t)` (`ValueTracker` + `always_redraw`).
- `BayesUpdate`: a Beta(2,18) prior with a filled area morphs into a Beta(5,25) posterior as the α/β trackers animate. The prior
  stays as a grey ghost, and a dashed line marks E[p] = 0.17.
- `BayesEquation`: `MathTex` Bayes' rule is written on.
  - The LHS is coloured and the prior term boxed.
  - `TransformMatchingTex` turns it into `0.90×0.02 / 0.05`.
  - It then becomes `= 0.36`, with a grey "illustrative numbers" note.

Verified frames are in `tools/manim/frames/`: `weibull_end.png`, `bayesupdate_end.png`, `bayeseq_box.png`,
`bayeseq_morph.png` (mid-transform) and `bayeseq_end.png`. Equations are crisp Computer Modern, with antialiased 5 px strokes.

Brand fonts in Manim (verified in `font_check.py`):

```python
import manimpango
for ttf in Path("video/tools/fonts/static").glob("*.ttf"):
    manimpango.register_font(str(ttf))
Text("Phalanx Twin", font="Manrope", weight=SEMIBOLD)      # also "JetBrains Mono"
```

### A4. Measured performance (Cairo, 1920×1080@30, under load)

| Render | Clip length | Wall time |
|---|---|---|
| WeibullCurves (first run, includes LaTeX compiles) | 9.2 s | 11.0 s |
| WeibullCurves (edit + re-render, cached TeX) | 9.2 s | 3.8–6.8 s |
| BayesUpdate (`always_redraw` area every frame) | 7.9 s | 8.1–8.9 s |
| BayesEquation | 8.1 s | 8.6 s |
| BayesEquation `-t` qtrle `.mov` / VP9 `.webm` / ProRes via Manim | 8.1 s | 2.6 s / 12.3 s / 7.6 s |
| `-s` last frame (MathTypst) | — | 2.1 s |
| ffmpeg qtrle → ProRes 4444 | 8.1 s | 9.2 s |

That is roughly real time. Budget about 1–1.5 min of wall time for 60 s of maths animation. TeX results are cached in `media/Tex`.

### A5. Alpha verification (commands that proved it)

```sh
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,codec_tag_string,profile,pix_fmt:stream_tags=alpha_mode -of compact=p=0 FILE
#   qtrle:  codec_name=qtrle  pix_fmt=argb
#   prores (ffmpeg): profile=4444 codec_tag_string=ap4h pix_fmt=yuva444p12le
#   vp9:    pix_fmt=yuv420p  tag:alpha_mode=1      (alpha is in side data; decode with -c:v libvpx-vp9 → yuva420p)
# composite over white and sample a background patch: must stay 255,255,255 (or 253 for lossy codecs)
ffmpeg -v error -f lavfi -i color=white:s=1920x1080:r=30:d=1 [-c:v libvpx-vp9] -ss 4 -i FILE \
  -filter_complex "[0][1]overlay=format=auto,crop=50:50:10:10,format=rgb24" -frames:v 1 -f rawvideo - | od -An -tu1 -N6
```

Results for the background patch: qtrle and Manim ProRes gave 255 255 255, ffmpeg ProRes 4444 gave 253, VP9 gave 253.
The alpha plane of qtrle spans 0–255.

### A6. Manim gotchas

- **Manim's `--video-codec prores_ks --encoder-option profile=4444` writes `apch` (ProRes HQ) as the fourcc while the
  frames are 4444 + alpha.** ffmpeg decodes it fine, but NLEs may ignore the alpha. Render qtrle and transcode with the
  ffmpeg line above, which gives a correct `ap4h` file.
- The default `Mobject` colour is white, so it is invisible on a white background. Set `Text/MathTex/DecimalNumber.set_default(color=INK)` and give axes `color=INK`.
  Axis numbers need `.set_color(INK)` after construction.
- Keep about 180 px at the bottom of the frame free for burned-in captions. Axis labels collided with captions in the smoke test.
- `TransformMatchingTex` cross-fades unmatched glyphs, which is a busy look. For cleaner morphs isolate parts as separate
  `MathTex` arguments, as `smoke_scenes.py` does, or use `FadeTransform` per part.
- Run `manim` from `tools/manim/` so `manim.cfg` applies. Otherwise `-qh` gives 1080p **60**.
- `pydub` prints `SyntaxWarning: invalid escape sequence` on import under 3.12. It is harmless.

---

## B. Final assembly and editing

### B1. Evaluation (primary sources: repos, licences and release pages as of 2026-10)

| Tool | Licence | Precision / determinism | Transitions, zoom, overlay | Audio mix and ducking | Burned-in captions | Mixes HTML MP4 + Manim alpha + audio | Agent-drivability | Verdict |
|---|---|---|---|---|---|---|---|---|
| **FFmpeg filtergraph** (ffmpeg-full 9.0.2) | LGPL-2.1+ (GPL with x264) | Frame-exact, deterministic | `xfade` (~50 types), `overlay` with alpha, `zoompan`, `fade:alpha=1` | `amix`, `sidechaincompress`, `volume` expressions, `loudnorm` (EBU R128) | **libass `.ass`** (styled, word highlight, brand fonts) | Yes | Raw strings are fragile, so we **generate them from JSON** | **Primary (as engine)** |
| MoviePy 2.2.1 | MIT | Deterministic, per-frame Python | `CrossFadeIn`, `resized(fn)`, masks | `CompositeAudioClip`, custom envelopes | Pillow `TextClip` only (no libass) | Yes (verified) | Python API, but v1 → v2 broke it (`with_*`, effect classes); LLMs often write v1 code. README says "Maintainers wanted!"; last code commit 2025-09 | Fallback |
| MLT `melt` 7.42 (+ Shotcut/Kdenlive) | LGPL-2.1 | Deterministic XML | Rich (luma, affine) | Mix, keyframed gain | `subtitle` filter since 7.26 | Yes | Verbose XML. Upside: a human can open Shotcut `.mlt` | Only if a human GUI pass is wanted; heavy brew deps (Qt, OpenCV) |
| Editly 0.14.2 / 0.15.0-rc.1 | MIT | JSON spec | gl-transitions | `audioNorm` (dynaudnorm), not true ducking | Simple text layer | Yes | Good JSON | **Blocked:** headless-gl fails to build on macOS 26 Tahoe (stackgl/headless-gl#328); last commit 2025-02 |
| Remotion 4.0.535 | **Source-available, not OSI.** Free for individuals, ≤3-employee companies and non-profits; Company License otherwise | Deterministic (Chrome) | Excellent | Good | Via React | Yes | Excellent | Licence and stack duplicate HyperFrames (Apache-2.0); not needed |
| Motion Canvas 3.17.2 | MIT | — | — | — | — | — | — | No headless render, dormant |
| Revideo 0.11.0 | MIT | Deterministic | Good | Good | Components | Yes | Good | Workable, but browser render, telemetry and a startup owner; HyperFrames already fills this lane |
| auto-editor 31.7.2 | Unlicense | — | — | — | — | — | — | It is a silence/motion **cutter** that exports Premiere/Resolve/FCP/Shotcut/Kdenlive timelines, not an assembler. Useful only for trimming a human VO take |

**Recommendation.** Use FFmpeg as the engine and drive it with `video/tools/assembly/assemble.py`: a declarative
JSON timeline compiled into one `ffmpeg-full` command.

- It meets every criterion: captions, ducking, alpha overlays, xfade, zoom/pan, loudness.
- It was the fastest renderer we measured (below).
- The full command is written next to the output as `<out>.ffmpeg.sh`, so every render is reproducible and diffable.
- An agent changes timings by editing numbers in JSON, never by hand-editing escaped filtergraph strings.
- MoviePy 2.2.1 stays installed as the fallback for one-off per-frame Python effects.
- Plain `ffmpeg` (Homebrew 9.0.2) is the universal fallback for trims and transcodes.

### B2. Important FFmpeg facts on this machine

- Homebrew's default `ffmpeg` (now **9.0.2** at `/opt/homebrew/bin/ffmpeg`) has **no libass and no freetype**, so it has
  no `subtitles`, `ass` or `drawtext`. Captions need the keg-only **`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`**.
  - ffmpeg-full also has `drawtext` and a `whisper` audio filter.
  - Keg-only means it does not shadow the default ffmpeg that HyperFrames uses.
- `xfade` inputs must share size, pixel format, fps and timebase. `assemble.py` normalises every clip with
  `fps=30,scale…,pad…,setsar=1,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS`.
- VP9-alpha `.webm` must be decoded with `-c:v libvpx-vp9` placed before `-i`. Otherwise alpha is silently dropped.
  `assemble.py` does this automatically.
- In zsh, `$VAR:l…` is a parameter modifier (lower-case), so a variable followed by `:linear=true` was silently corrupted. Write `${VAR}:…`.

### B3. Assembly smoke test (verified)

Stand-in assets come from `tools/assembly/make_test_assets.py`:

- a mock fleet-board PNG, standing in for a HyperFrames render;
- a synthetic 24 s ambient pad, standing in for licensed music;
- the Manim clips;
- the Kokoro narration with its `.ass` captions.

Timeline (`tools/assembly/timeline_smoke.json`), 16.6 s total:

1. 0–8 s: UI still with a Ken Burns zoom from 1.00× to 1.08× about (0.35, 0.45).
2. 7.4–8.0 s: 0.6 s `fade` xfade into `WeibullCurves.mp4`.
3. 0.8–7.2 s: transparent `BayesEquation_alpha_qtrle.mov` overlay at 50 %, with alpha fades.
4. Narration from 1.0 s. Music bed at −4 dB with a 1 s fade in and 2 s fade out, **ducked 12 dB under narration**.
5. Captions `.ass` shifted +1.0 s, in Manrope SemiBold through `fontsdir`.
6. `loudnorm` I=−16 LUFS, TP=−1.5.

```sh
cd video
.venv/bin/python -I tools/assembly/assemble.py tools/assembly/timeline_smoke.json             # → out/smoke_ffmpeg.mp4 (+ .ffmpeg.sh)
.venv/bin/python -I tools/assembly/assemble.py tools/assembly/timeline_smoke.json --dry-run   # only writes the command
# verification
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,sample_rate,channels,nb_frames,duration -of compact=p=0 tools/assembly/out/smoke_ffmpeg.mp4
#   h264 1920x1080 30/1 yuv420p 498 frames 16.600000 | aac 48000 Hz stereo 16.600000
for t in 0.0 3.0 5.5 7.7 9.0 13.5; do ffmpeg -v error -y -ss $t -i tools/assembly/out/smoke_ffmpeg.mp4 -frames:v 1 tools/assembly/out/frames/ffmpeg_t$t.png; done
ffmpeg -nostats -hide_banner -i tools/assembly/out/smoke_ffmpeg.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -A14 Summary
```

What was checked:

- **Frames.** `ffmpeg_t5.5.png` shows the zoomed UI, the alpha equation mid-morph, and a caption with the current word in accent.
  `ffmpeg_t7.7.png` shows the crossfade. `ffmpeg_t9.0.png` and `ffmpeg_t13.5.png` show the Manim clip with Manrope captions.
- **Ducking.** The ducked music bus is written to `out/smoke_ffmpeg.ducked_music.wav` (`debug_outputs`) and compared with an
  un-ducked reference in 0.5 s windows:
  - **0.0 dB** before speech;
  - **−12.0 dB** throughout narration, through 2.0–13.5 s;
  - smooth −5 dB ramps at 1.0 s and 14.0 s;
  - **0.0 dB** after.
- **Sidechain mode for comparison** (`timeline_smoke_sidechain.json`, `sidechaincompress` threshold 0.015, ratio 10,
  release 500 ms): −9 to −13 dB under speech, but it **pumps back to 0 dB in sentence pauses** (for example 7.0 s and 12.0 s).
  That is why the default is the envelope mode, which is computed from the known narration spans.
- **Loudness.** The single-pass `loudnorm` in the graph gives −16.4 to −16.8 LUFS. The two-pass master below lands exactly on
  **−16.0 LUFS, −1.6 dBTP**.

```sh
# two-pass loudness master (video stream copied; ~1 s)
J=$(ffmpeg -hide_banner -nostats -i in.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
MI=$(echo "$J" | video/.venv/bin/python -I -c "import json,sys; d=json.load(sys.stdin); print(f\"measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}:measured_thresh={d['input_thresh']}:offset={d['target_offset']}\")")
ffmpeg -i in.mp4 -c:v copy -af "loudnorm=I=-16:TP=-1.5:LRA=11:${MI}:linear=true,aresample=48000" -c:a aac -b:a 192k master.mp4
```

The MoviePy version of the same timeline is `tools/assembly/assemble_moviepy.py`:

```sh
IMAGEIO_FFMPEG_EXE=/opt/homebrew/bin/ffmpeg .venv/bin/python -I tools/assembly/assemble_moviepy.py   # → out/smoke_moviepy.mp4
```

It produced an identical layout (Ken Burns, crossfade, alpha overlay, envelope duck), but its captions are plain Pillow text with no word highlight.

### B4. Measured assembly performance (16.6 s timeline, under load)

| Variant | Wall time | × real time |
|---|---|---|
| ffmpeg-full, full timeline (with Ken Burns still) | 15.7–31 s | 0.5–1.06× |
| ffmpeg-full, same without Ken Burns | 3.4–6.0 s | **2.8–4.9×** |
| MoviePy 2.2.1, full timeline | 27.3 s | 0.61× |
| two-pass loudnorm master (video copied) | 1.1 s | — |

`zoompan` on a 2×-upscaled still is the bottleneck: it is single-threaded inside the big graph.

- **Do camera moves on UI inside HyperFrames** (CSS transforms, GPU-quality), and use `kenburns` only for the odd still.
- If needed, pre-render Ken Burns clips as separate jobs in parallel.

For a 4-minute cut of cuts, fades, overlays and captions, expect roughly 1–2 minutes per full render.

### B5. `assemble.py` timeline schema (see the docstring for the full version)

```jsonc
{
  "fps": 30, "size": [1920, 1080], "background": "white",
  "video":    [ {"src": "scene01.mp4", "in": 0, "dur": 12.0},
                {"src": "eq_weibull.mp4", "dur": 9.2, "transition": {"type": "fade", "dur": 0.6}} ],  // any xfade type
  "overlays": [ {"src": "eq_alpha.mov", "at": 14.0, "dur": 6, "scale": 0.5, "x": "W-w-40", "y": "H-h-150",
                 "fade_in": 0.2, "fade_out": 0.5} ],
  "audio": {
    "narration": [ {"src": "vo/s01.wav", "at": 1.0, "speech": [0.27, 13.07]} ],   // speech span from word timestamps
    "music": {"src": "music.wav", "gain_db": -4, "fade_in": 1, "fade_out": 2,
              "duck": {"mode": "envelope", "depth_db": -12, "attack": 0.25, "release": 0.6, "merge_gap": 1.2}},
    "sfx": [ {"src": "tick.wav", "at": 7.4, "gain_db": -8} ]
  },
  "captions": {"ass": "captions.ass", "offset": 1.0, "fontsdir": "../fonts/static"},
  "loudness": {"I": -16, "TP": -1.5, "LRA": 11},
  "encode": {"crf": 18, "preset": "medium"},
  "out": "out/master_pre.mp4"
}
```

Notes on the schema:

- **Clip audio:** audio embedded in source clips is ignored. Every sound is an explicit `narration`, `music` or `sfx` entry.
- **Durations:** total duration is the sum of clip durations minus the transition overlaps.

---

## C. Narration and captions

### C1. TTS evaluation

| Model | Code licence | Weights / voices licence | Notes |
|---|---|---|---|
| **Kokoro-82M** (`kokoro` 0.9.4, `hexgrad/Kokoro-82M`) | Apache-2.0 | **Apache-2.0, voices included** | 82 M params, CPU-fast; misaki G2P (dictionary + espeak-ng fallback); returns per-token timestamps |
| kokoro-onnx 0.6.1 | MIT | same Kokoro weights (onnx 310 MB / int8 88 MB) | Lighter (onnxruntime), but espeak-only phonemes are slightly worse than misaki. Not installed |
| Piper (`OHF-Voice/piper1-gpl`, v1.8.0) | GPL-3.0 | **Per voice.** e.g. en_US-lessac is research-only; ryan, hfc_* and en_GB-semaine are CC BY-NC-SA; libritts_r and vctk are CC BY; joe is CC0 | Fast, but robotic next to Kokoro, and many US/GB voices are non-commercial |
| Chatterbox (Resemble) | MIT | MIT | Good, but heavier and **watermarks every output** (PerTh) |
| F5-TTS | MIT | **CC-BY-NC-4.0** | Non-commercial weights |
| XTTS-v2 | MPL (fork) | **Coqui Public Model Licence, non-commercial** | Excluded |
| StyleTTS2 | MIT | Must disclose synthetic speech; GPL phonemizer | Excluded on friction |
| Dia-1.6B / KittenTTS / VibeVoice-1.5B | Apache / Apache / MIT | permissive | Larger or less proven for long-form narration; not tried |

### C2. Install and generate

```sh
cd video
uv pip install --python .venv/bin/python "kokoro==0.9.4" "faster-whisper==1.2.1" soundfile
# pre-install the spaCy model so misaki does NOT pip-download it at runtime:
uv pip install --python .venv/bin/python "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
export HF_HOME=$PWD/tools/cache/hf HF_HUB_DISABLE_TELEMETRY=1
.venv/bin/python -I tools/tts/kokoro_tts.py --voice af_heart --speed 1.0 \
  --text "Every morning, before eight, a squadron engineering officer decides which aircraft will fly. Phalanx Twin turns the fleet's evidence into a handful of signed decisions — and shows exactly why." \
  --out tools/tts/out/af_heart_1.0.wav        # writes .wav (24 kHz mono) + .tokens.json (word start/end)
```

The first run downloads `kokoro-v1_0.pth` (327 MB) plus about 0.5 MB per voice into `tools/cache/hf`. Both weights and voices
load with `torch.load(weights_only=True)`.

`--seed` (default 0) seeds torch, so a re-run gives a bit-identical WAV.

### C3. Voices tried (same 29-word script, CPU, M4)

| Voice | Kokoro grade (VOICES.md) | Audio | Synthesis | Words per minute | Unbiased Whisper round-trip |
|---|---|---|---|---|---|
| af_heart (US F) | flagship, A-level | 13.2 s | 5.5 s (first, warm-up) | 132 | 28/29 (only "eight" → "8") |
| af_bella (US F) | A- | 13.5 s | 5.9 s | 129 | 28/29 |
| am_michael (US M) | C+ | 14.3 s | 4.2 s; 2.1 s at speed 0.95 | 122 | 28/29 |
| am_fenrir (US M) | C+ | 12.9 s | 3.7 s | 135 | 28/29 |
| am_puck (US M) | C+ | 12.7 s | 3.7 s | 137 | 28/29 |
| bm_george (UK M) | C | 13.9 s | 3.8 s; 1.8 s at speed 0.95 | 125 | 28/29 |
| bm_fable (UK M) | C | 11.6 s | 3.9 s | 150 | 28/29 |
| bf_emma (UK F) | B- | 12.0 s | 4.4 s | 145 | **27/29: "Phalanx" heard as "Falang's"** |

- **Speed:** real-time factor 0.13–0.44 on CPU, so it generates 2.3–7.7× faster than real time. Model load is about 2 s once cached.
- **Quality:** I could not listen, so quality was judged with objective proxies: Kokoro's own data-quality grades, an unbiased ASR round trip, and speaking rate.
- **Pick:** **af_heart** as narrator, the top-graded voice. If a male narrator is preferred, **am_michael at speed 0.95–1.0**
  is the most measured male voice. A human should listen to the eight WAVs in `tools/tts/out/` before the final pick.
- **Rate:** narration at 122–150 wpm is right for a 4-minute explainer, which comes to roughly 500–560 words of script.
- **Pronunciation of "Phalanx":**
  - US voices say "FAY-lanks" (`fˈAlˌæŋks`); UK voices say "FAL-anks".
  - To force one, write `[Phalanx](/fˈælæŋks/)`. This is verified: the tokens come back as `fˈælæŋks`.
  - `align_captions.py` strips this markup from caption text.

### C4. Word alignment and captions

```sh
# timings from Kokoro itself (exact for TTS):
.venv/bin/python -I tools/align/align_captions.py --wav tools/tts/out/af_heart_1.0.wav --script-file tools/tts/script_test.txt --source kokoro
# timings from faster-whisper small.en (int8, CPU) — any recording; --no-prompt for an unbiased intelligibility check:
.venv/bin/python -I tools/align/align_captions.py --wav tools/tts/out/af_heart_1.0.wav --script-file tools/tts/script_test.txt --source whisper
# → <wav>.<source>.words.json, .srt, .ass
```

How it works:

- ASR or TTS words are mapped onto the **script** words with `difflib`, so captions show the exact script ("eight", not "8").
- Phrases break on sentence punctuation, an em-dash, pauses over 0.6 s, or more than 42 characters.
- Phrase ends get a 0.15 s hold, clamped so captions never overlap.
- The `.ass` has one event per word: the whole phrase is in ink (`#0B0D10`) on a white box, and the current word is in accent `#E8743B`.

Whisper speed: `small.en` (about 460 MB download) loads in 1–2 s and transcribes 13–14 s of audio in about 5 s.

**Alignment sanity check (Kokoro vs Whisper, 29 words):**

| Voice | Start-time difference, median | Start-time difference, max | End-time difference, median | End-time difference, max |
|---|---|---|---|---|
| af_heart | 0.075 s | 0.275 s | 0.107 s | 0.52 s |
| am_michael | 0.090 s | 0.375 s | 0.090 s | 0.51 s |

The largest gaps are Whisper's first word starting at 0.00 s inside the 0.3 s leading silence, and a sentence-final word.
Kokoro timings are the better source for our own TTS. Sample `.srt` (af_heart, Kokoro timings):

```
1  00:00:00,275 --> 00:00:02,065  Every morning, before eight,
2  00:00:02,075 --> 00:00:04,477  a squadron engineering officer decides
3  00:00:04,487 --> 00:00:06,400  which aircraft will fly.
4  00:00:06,475 --> 00:00:08,777  Phalanx Twin turns the fleet's evidence
5  00:00:08,787 --> 00:00:11,152  into a handful of signed decisions —
6  00:00:11,162 --> 00:00:13,075  and shows exactly why.
```

Brand fonts for libass:

- Steps:
  - The repo's `screens/assets/fonts/*.woff2` are variable fonts.
  - libass cannot select variable instances, and the Manrope variable font's default family name is "Manrope ExtraLight".
  - So `woff2_decompress` (brew `woff2`) and `tools/fonts/make_static_fonts.py` (fontTools 4.67) produce renamed static TTFs in `tools/fonts/static/`:
    - Manrope Regular, Medium, SemiBold and Bold;
    - JetBrains Mono Regular and Bold.
- Use `Fontname = Manrope SemiBold` and `fontsdir=…/fonts/static`. Verified in `tools/assembly/out/fonttest/fonts.png`; before the fix, libass silently fell back to Helvetica.

### C5. Gotchas

- `faster-whisper` 1.2.1's own decoder calls `av.open(..., metadata_errors=...)`, which PyAV 19 (pulled in by Manim 0.22) rejects.
  `align_captions.py` decodes with system ffmpeg to 16 kHz float32 and passes a numpy array.
- `moviepy.__version__` reports "2.1.2" although 2.2.1 is installed (a stale string upstream). Trust `importlib.metadata`.
- Whisper with `initial_prompt=script` simply echoes the script, em-dash included. Use `--no-prompt` to judge intelligibility.
- `misaki` will `spacy.cli.download()` at runtime if `en_core_web_sm` is missing. Pre-install it, as above.

---

## D. Recommended end-to-end pipeline

```
script.md  ──►  vo/sNN.txt (one file per scene, plain text + optional [word](/phonemes/) overrides)
                  │  kokoro_tts.py  (af_heart, speed 1.0)            → vo/sNN.wav + vo/sNN.tokens.json
                  │  align_captions.py --source kokoro               → vo/sNN.kokoro.{words.json,srt,ass}
                  ▼  (scene length = narration length + pads; feed these durations to the scene authors)
HyperFrames scenes (HTML/CSS/SVG, 1920×1080@30)  → scenes/NN_*.mp4        (camera moves, UI motion, no captions, no VO)
Manim clips (manim.cfg, white bg)                → maths/*.mp4 or *_alpha_qtrle.mov (overlays)
                  ▼
timeline.json  (clips + transitions, overlays, narration "at"/"speech", music + envelope duck, sfx,
                captions = all scene .ass files merged with offsets, loudness)
                  │  assemble.py  → out/master_pre.mp4 (+ out/master_pre.ffmpeg.sh)
                  ▼
two-pass loudnorm (−16 LUFS, −1.5 dBTP), video stream-copied        → out/Phalanx_Twin_launch_master.mp4
QA: ffprobe (1920×1080, 30/1, yuv420p, AAC 48 k stereo, duration), frames every 10 s → PNG review, ebur128 summary
```

Practical rules:

1. **Narration drives timing.** Generate VO first, per scene, and give each scene author the exact duration.
   - Re-render only the scene whose text changed. The vocoder is stochastic, so the same text, voice and speed give the
     same length and timings but different samples. With `torch.manual_seed`, which `kokoro_tts.py --seed` defaults to 0,
     the WAV is bit-identical (verified by SHA-256).
2. **Keep captions out of HyperFrames and Manim** and burn them in once at assembly. Reserve the bottom ~180 px in every scene.
3. **Transparent Manim overlays: qtrle `.mov`.** Transcode to ProRes 4444 only for an NLE.
4. **Keep one fps everywhere (30)** and render every scene at 1920×1080. `assemble.py` normalises anyway, but resampling costs quality.
5. **Music:** use a licensed or CC0 track. Duck with `mode: envelope`; it uses the narration spans and does not pump.
6. **Single-command rebuild:** `assemble.py timeline.json`, then the two-pass loudnorm.
   - The emitted `.ffmpeg.sh` is the audit trail. Keep it next to each master.
7. Honesty overlays (for example "synthetic data · illustrative") should be part of the scene or an overlay PNG, never only spoken.

---

## E. Environment changes made (and one incident)

| Change | Notes |
|---|---|
| Homebrew installs | `texlive` 20260301_1 (4.7 GB), `dvisvgm` 3.6.1, `ffmpeg-full` 9.0.2 (keg-only), `espeak-ng` 1.52.0, `woff2`, `whisper.cpp` 1.9.5 (an ffmpeg-full dependency) |
| Dependency upgrades pulled in by those installs | x265 4.2 → 4.3, python@3.14 3.14.6 → 3.14.8, cairo, glib, harfbuzz, openjdk 27, lame 4.0, libvpx 1.17, svt-av1 4.2 |
| **Incident** | The x265 upgrade broke the existing `ffmpeg` 8.1.2 binary (`libx265.216.dylib` not found) for a few minutes. Fixed with `brew upgrade ffmpeg`, so system ffmpeg is now **9.0.2**. The HyperFrames agent saw "FFmpeg cannot start" during that window and re-rendered successfully on 9.0.2. `brew linkage --test` is now clean |
| Python | `video/.venv` (3.12.12): manim 0.22.0, manimpango 0.7.0, pycairo 1.29.2, av 19.0.1, moviepy 2.2.1, kokoro 0.9.4, misaki 0.9.4, torch 2.14.1, spacy 3.8.16 + en_core_web_sm 3.8.0, faster-whisper 1.2.1, ctranslate2 4.8.3, typst 0.15.0, fonttools 4.67.0 (1.3 GB) |
| Model caches | `video/tools/cache/hf` (780 MB): Kokoro-82M + 8 voices, Systran faster-whisper small.en |
| Not touched | No sudo, no global npm, no git commits |
