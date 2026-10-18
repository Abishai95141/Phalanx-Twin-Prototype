# Phalanx Twin film — production status and remaining steps

Updated 18 Oct 2026. Team **Dilijens** · IBM Z Datathon · theme "Real-time AI for critical decisions".

## Current cut: v2 — `renders/phalanx_twin_film_v2.mp4` (3:39.8)

Delivered 18 Oct 2026 — 3:39.8, 1920×1080/30, H.264 + AAC 48 kHz, −16.0 LUFS, −1.7 dBTP (two-pass loudnorm +
limiter, same targets as v1); reviewed every 2 s and frame by frame at every join, S04 and the end card.

What changed from v1 (4:51.5):
- **Cut:** S13–S16 (data contract, as-of store, state, model zoo), S25 + Manim M1 (probability maths), S29 + M3
  (lead-time maths), S32 (gates), S33A–D (assistant segment). Problem (S01–S10) and solution (S11–S12, S17–S18,
  demonstration S19–S24, S26–S28, S30–S31, result S34) are kept with their v1 narration and lengths.
- **New LinuxONE section** after S31 (30.9 s, three narration lines L1–L3 in the same Kokoro af_heart voice at
  speed 0.97): `film/linuxone.html` → `renders/linuxone.mp4`.
- **Credits:** S04 reads "Dilijens · IBM Z Datathon" (`film/act01.html`); the end card keeps "One state. One loop.
  One log." and the PHALANX logotype, adds the line "Real-time AI for critical decisions · live on IBM LinuxONE"
  and the credit "Dilijens · IBM Z Datathon" (`film/act4.html`, act lengthened by 1.0 s so the card holds).
  Both are in the source renders, not patched.
- Triage kicker in Act 2 is now "Triage" (was "04 · Triage", which pointed at cut sections).

| Piece | File | State |
|---|---|---|
| Act 0–1 (S01–S10, 66.6 s) | `film/act01.html` → `renders/act01_v2.mp4` | re-rendered 18 Oct (credit) |
| Act 2 (S11–S18, 67.2 s; v2 uses 0–10.85 and 50.12–67.2) | `film/act2.html` → `renders/act2_v2.mp4` | re-rendered 18 Oct (kicker) |
| Act 3a (S19–S27; v2 uses 0–37.2 and 48.7–63.07) | `renders/act3a.mp4` | v1 render, unchanged |
| S26 cut-in | `renders/ins_hyd.mp4` | v1 render, unchanged |
| Act 3b (S28–S32; v2 uses 0–9.2 and 18.33–33.17) | `renders/act3b.mp4` | v1 render, unchanged |
| LinuxONE (L1–L3, 30.9 s) | `film/linuxone.html` → `renders/linuxone.mp4` | new, final |
| Act 4 (57.3 s; v2 uses S34–S35 from 37.63) | `film/act4.html` → `renders/act4_v2.mp4` | re-rendered 18 Oct (end card) |
| Manim M5 (S28) | `renders/manim/M5_paired_forks_S28.mp4` | v1, unchanged (M1, M3 no longer used) |
| Narration | `edit/narration.json` (L1–L3 added), `edit/vo/L1–L3.wav` | v1 clips reused for every kept shot |
| Timing | `edit/build_timing_v2.py` → `edit/timing_v2.json` | segments, shot film times, music sections |
| Captions / music | `edit/captions_v2.ass`, `edit/music/bed_v2.wav` | `make_captions.py` / `make_music.py` take `timing_v2.json` |
| Master | `zsh edit/master_v2.sh` → `renders/phalanx_twin_film_v2.mp4` | delivered |

### Rebuild v2
1. Acts that changed: `cd film && HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_NO_UPDATE_CHECK=1 npx hyperframes render --composition <act>.html --quality high --no-experimental-fast-capture --output ../renders/<act>_v2.mp4` (`act01`, `act2`, `act4`; `linuxone` renders to `../renders/linuxone.mp4`). If `film/node_modules` is missing: `cd film && npm ci --prefer-offline`.
2. LinuxONE narration: `HF_HOME=tools/cache/hf HF_HUB_OFFLINE=1 .venv/bin/python -I edit/make_vo.py L1 L2 L3` (always pass shot ids, or every clip is regenerated). If L1–L3 change length, update the word times and `END`/`B`/`C` in `film/linuxone.html` from `timing_v2.json` → `linuxone.shots` and re-render it.
3. Master: `zsh edit/master_v2.sh` (rebuilds timing, captions, music, timeline, assembly and loudness).

## v1 — `renders/phalanx_twin_film.mp4` (4:51.5, kept unchanged)

Delivered 16 Oct 03:21; built by `zsh edit/master.sh` from `edit/timing.json` and the v1 act renders
(`renders/act01.mp4`, `act2.mp4`, `act3a.mp4`, `act3b.mp4`, `act4.mp4`). Those v1 act renders still carry the old
team credit; the act sources now carry the Dilijens credit, so a v1 rebuild needs the acts re-rendered first.
`edit/make_captions.py` and `edit/make_music.py` with no arguments still reproduce the v1 captions and bed
byte for byte.

1. Any act: `cd film && HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_NO_UPDATE_CHECK=1 npx hyperframes render --composition actX.html --quality high --no-experimental-fast-capture --output ../renders/actX.mp4`
2. If a plate changes: `cd film/assets/illustrations/src && python3 build.py`, then `python3 film/tools/inline_illus.py`, then re-render the acts that use it (`ins_hyd`, `act4`).
3. If narration changes: `edit/make_vo.py <ids>` → `edit/build_timing.py` → `edit/make_captions.py` → `edit/make_music.py`, then re-time the acts.
4. Master: `zsh edit/master.sh`.

Final review fixes (16 Oct): M3 subtitle shortened; part number `SYN-PN-HYDP` removed from the twin card.
Known and accepted: "Release v0.9 · dictionary 0.1.3" appears as a data-release label on the drift/provenance
screens (reads as a version, not a preview). S10 states the requirement that answers "run fully offline" and
shows "Nothing leaves an air-gapped base" — it is the problem statement's constraint, not a claim about the
LinuxONE deployment.
