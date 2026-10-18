# Phalanx Twin — product film: script, flow and shot-by-shot storyboard

Team **Dilijens** · IBM Z Datathon · theme "Real-time AI for critical decisions" · "Air Power – Predictive Maintenance & Fleet Availability"
Length **3:39.8** in the v2 cut (`edit/timing_v2.json`; v1 was 4:51, `edit/timing.json`) · 1920 × 1080 · 30 fps · white-first product film.

Status: **draft for acceptance.** Nothing is rendered yet. The screens referenced below are built (see
`video/stills/` and `video/screens/`); every number on screen comes from the fleet records as of the demo
snapshot (Mon 22 Jun 2026, 06:00 IST), from runs we performed (forks, classifier, policy evaluation), from the
architecture research, or from cited public audits. Fork values come from `video/data/forks/results.json` (30 CRN pairs per scenario, belief mode).

---

## v2 cut — current (18 Oct 2026) · 3:39.8

`renders/phalanx_twin_film_v2.mp4`, built by `zsh edit/master_v2.sh` from `edit/timing_v2.json`
(`edit/build_timing_v2.py`). Problem and solution kept; data-contract/as-of/state/model-zoo detail (S13–S16), the
probability maths (S25 + Manim M1), the lead-time maths (S29 + M3), the gates (S32) and the assistant segment
(S33A–D) are cut; a new IBM LinuxONE section (L1–L3, `film/linuxone.html`) sits between S31 and S34. Kept shots
keep their v1 length and narration; acts are cut at shot boundaries (0.3 s crossfades at S12→S17, S28→S30 and
S31→L1; the other joins land on white). The sections of the storyboard below describe the full v1 film; the
shots listed above as cut are not in v2.

| Shot | Film start | Dur (s) | Source | Narration |
|---|---|---|---|---|
| S01 | 0:00.00 | 5.70 | `renders/act01_v2.mp4` @ 0.00 s | Every morning, before eight, someone decides which aircraft will fly. |
| S02 | 0:05.70 | 4.13 | `renders/act01_v2.mp4` @ 5.70 s | That decision should rest on everything the fleet already knows. |
| S03 | 0:09.83 | 5.00 | `renders/act01_v2.mp4` @ 9.83 s | Health data. Technical records. Spares. Work in progress. |
| S04 | 0:14.83 | 5.77 | `renders/act01_v2.mp4` @ 14.83 s | Phalanx Twin brings it together — and turns it into decisions. |
| S05 | 0:20.60 | 9.27 | `renders/act01_v2.mp4` @ 20.60 s | The problem statement is blunt. Availability is low because maintenance is reactive — and the data that could prevent it isn't integrated. |
| S06 | 0:29.87 | 6.83 | `renders/act01_v2.mp4` @ 29.87 s | Audits keep finding the same thing: aircraft are lost to waiting — for parts, for repair, for a decision. |
| S07 | 0:36.70 | 9.43 | `renders/act01_v2.mp4` @ 36.70 s | In our fleet, one aircraft has been on the ground for eighty days, waiting for a brake chute — a consumable whose demand simply follows landings. |
| S08 | 0:46.13 | 8.80 | `renders/act01_v2.mp4` @ 46.13 s | Another has had its hydraulic pump removed twenty-eight times for one alarm. Every pump the shop tested came back: no fault found. |
| S09 | 0:54.93 | 5.53 | `renders/act01_v2.mp4` @ 54.93 s | Nearly twelve hundred alerts this season. More prediction alone would only add more. |
| S10 | 1:00.47 | 6.13 | `renders/act01_v2.mp4` @ 60.47 s | And any answer must be explainable, honest about time — and run fully offline. |
| S11 | 1:06.60 | 4.83 | `renders/act2_v2.mp4` @ 0.00 s | Phalanx Twin is a decision-support digital twin for the flight line. |
| S12 | 1:11.43 | 5.87 | `renders/act2_v2.mp4` @ 4.83 s | It answers four questions: what's happening, why, what happens next — and what we should do. |
| S17 | 1:17.30 | 3.97 | `renders/act2_v2.mp4` @ 50.27 s | Triage turns twelve hundred alerts into seven decisions. |
| S18 | 1:21.26 | 12.97 | `renders/act2_v2.mp4` @ 54.23 s | Versioned policies and optimisers propose orders, simulation tests them against the status quo, a person approves — and every step lands on one tamper-evident log. |
| S19 | 1:34.23 | 5.37 | `renders/act3a.mp4` @ 0.00 s | Monday, 06:00. Six of eight aircraft are mission capable. |
| S20 | 1:39.60 | 7.13 | `renders/act3a.mp4` @ 5.37 s | This season, most of the waiting came from tyres and brake chutes — demand you can predict from the flying plan. |
| S21 | 1:46.73 | 5.17 | `renders/act3a.mp4` @ 12.50 s | Today's board has seven issues — each with the evidence and the score behind it. |
| S22 | 1:51.90 | 6.67 | `renders/act3a.mp4` @ 17.67 s | TJ107. The system doesn't say replace the pump. It says stop — and shows why. |
| S23 | 1:58.56 | 5.90 | `renders/act3a.mp4` @ 24.33 s | In the twin, the alarm's reporter and its suspects light up where they sit in the aircraft. |
| S24 | 2:04.46 | 6.97 | `renders/act3a.mp4` @ 30.23 s | It stayed with this aircraft through ten different pumps. The evidence follows the tail — not the part. |
| S26 | 2:11.43 | 5.03 | `renders/act3a.mp4` @ 48.70 s | So it recommends the test that resolves the most uncertainty per man-hour. |
| S27 | 2:16.46 | 9.33 | `renders/act3a.mp4` @ 53.73 s | Every recommendation comes from a rule you can read. Hard limits live in code; anything airworthiness-sensitive waits for a human signature. |
| S28 | 2:25.80 | 9.20 | `renders/act3b.mp4` @ 0.00 s | Before it reaches the board, each order is tested on paired simulations of the same futures — our plan against the status quo. |
| S30 | 2:34.70 | 8.53 | `renders/act3b.mp4` @ 18.33 s | At 07:45 the board freezes. At 08:00, orders go out — each one cited, signed where it must be, and safe to retry. |
| S31 | 2:43.23 | 6.00 | `renders/act3b.mp4` @ 26.87 s | Ask why any order was issued, and the chain answers — from data release to signature. |
| L1 | 2:49.23 | 9.50 | `renders/linuxone.mp4` @ 0.00 s | All of this runs live on IBM LinuxONE: the simulator, models, rules, daily loop and audit log — on one mainframe-class server. |
| L2 | 2:58.73 | 8.70 | `renders/linuxone.mp4` @ 9.50 s | Rebuilt there, it reproduces every record, row for row — and simulates a day for all eight aircraft in three and a half seconds. |
| L3 | 3:07.43 | 12.70 | `renders/linuxone.mp4` @ 18.20 s | IBM Z is built for exactly this: availability, hardware-protected keys, confidential computing and AI on the chip — real-time AI for critical decisions. |
| S34 | 3:20.13 | 11.83 | `renders/act4_v2.mp4` @ 37.63 s | On thirty paired simulations, the TJ107 decision adds twenty-two points of mission-capable time next month — and saves a hundred and sixteen man-hours. |
| S35 | 3:31.96 | 7.83 | `renders/act4_v2.mp4` @ 49.47 s | Phalanx Twin. One state. One loop. One log. |

LinuxONE section visuals (`film/linuxone.html`, 30.9 s, white/ink/one accent, IBM blue #0F62FE only for the
platform layer): **L1** the stack builds bottom-up on the narration (IBM LinuxONE s390x → Ubuntu 24.04 LTS →
Python/Anaconda s390x builds → fleet simulator → Phalanx Twin with models · rules · daily loop · audit log → web
app at https://148.100.99.205) beside a terminal card (`uname -m` → s390x; `lscpu` → Byte Order: Big Endian,
Machine type: 9175); **L2** stat cards: row for row · 3.5 s per simulated day (8 aircraft) · 0.6 ms median API
response · 74 tests, plus 64 aircraft-years of training history built on the guest; **L3** what IBM Z is built for
(availability, hardware-protected keys — CPACF / Crypto Express, confidential computing — Secure Execution, AI on
the chip — Telum), each marked READY FOR and captioned "on our roadmap, not yet used by the prototype", then the
line "Real-time AI for critical decisions."

---

## 1. Story spine

**Promise → Pain (explicit, then implicit) → Solution → How it works → Why the architecture solves the pain →
Demonstration → Proof → Close.**

| Act | Time | Job of the act | The viewer leaves with |
|---|---|---|---|
| 0 · Promise | 0:00–0:18 | One morning, one decision, all the evidence | "This is about the 08:00 decision" |
| 1 · Pain | 0:18–0:58 | PS pain (explicit) → what our fleet data reveals (implicit) | waiting, false removals, alert floods, trust |
| 2 · Solution & architecture | 0:58–1:58 | Build the architecture piece by piece, each piece answering a pain | one state · one loop · one log |
| 3 · Demonstration | 1:58–3:47 | One real morning: readiness → board → twin → maths → policy → fork → orders → audit → learning | the 3D twin is an instrument; decisions are explainable |
| 4 · Agentic, bounded + proof + close | 3:47–4:05 | Assistant and loop as bounded agents; paired-fork results; close | credible, deployable, human-in-command |

**How "agentic" is represented (the PS lists AI/ML predictive maintenance, IoT health monitoring, digital
twins and an integrated analytics platform; agentic capability is our framing of how the platform acts).**
Two bounded agents, both shown on screen:
1. **The decision loop** is a closed MAPE-K agent (monitor → analyse → plan → execute over shared knowledge)
   that acts on the fleet only through typed orders. It may issue AGENT-authority actions; anything
   airworthiness-sensitive (monitoring-config changes, software loads, mods, servicing deferrals) is drafted
   for a HUMAN signature. Deterministic and replayable — no LLM in the decision path.
2. **The assistant** is a tool-using agent (plan → read-only tools → cited answer → order *draft*), local
   gpt-oss-20b, air-gapped, belief-mode what-ifs only.

**Explicit pain (problem statement text):** low availability from fragmented, largely reactive maintenance; health
monitoring, technical records, spares and maintenance agencies not integrated → delayed fault prediction,
avoidable downtime, sub-optimal use of critical assets.

**Implicit pain (found in the architecture research and our fleet records):**
1. Availability is lost **waiting** (parts, repair, decisions), not repairing — and much of the waiting is
   predictable (tyres and brake chutes = 69 % of awaiting-parts time).
2. **False alarms feed the repair pipeline** — healthy units removed, shop says RTOK (54 of 54 findings), the
   aircraft waits for a spare it never needed.
3. **Alert floods** — 1,192 alert rows in 168 days; more prediction = more noise unless triaged.
4. **Prediction is useless if it doesn't beat the lead time.**
5. **Trust**: late data leaks into models (time honesty), black boxes can't sign for airworthiness, every
   decision must be auditable, and nothing may leave an air-gapped base.

---

## 2. Production workflow (tools, verified on this machine)

| Layer | Tool | Licence | Used for | Verified |
|---|---|---|---|---|
| Product screens | HTML/CSS/SVG + three.js r186 (`video/screens/`) | MIT | every UI shot; the 3D twin | 13 screens built, shot at 1920×1080 |
| Motion + UI camera | **HeyGen HyperFrames** 0.8.162 + GSAP | Apache-2.0 (+ GSAP licence) | camera pushes, cursor, typing, count-ups, highlight, SVG draw-on, architecture builds, titles, captions, transitions | smoke test + screen pattern rendered; ≈ 0.57 s render per s of video; three.js renders headless |
| Maths (3Blue1Brown style) | **Manim Community** | MIT | Bayes update, lead-time race, expected-cost threshold, CRN paired forks, memory/token budget | see `video/research/workflow.md` |
| Assembly / edit | **ffmpeg** filtergraphs (xfade, overlay, loudnorm, ass) driven from a cut list | LGPL/GPL | final conform, audio mix + ducking, captions burn-in, master | see `workflow.md` |
| Narration | Kokoro-82M TTS (scratch VO) → swap for a recorded human VO if preferred | Apache-2.0 | timing + temp VO | see `workflow.md` |
| Captions | faster-whisper word timestamps → .ass | MIT | burned-in captions, cut timing | see `workflow.md` |

**Pipeline:** cut list (`video/edit/cutlist.yaml`: shot id, in/out, source, transition) → HyperFrames renders
one composition per act (screens mounted as sub-compositions; one paused GSAP timeline per act) → Manim renders
maths clips (transparent ProRes 4444 where overlaid) → ffmpeg conforms acts + clips, mixes VO / music bed with
side-chain ducking, burns captions → `master_4k05.mp4` (H.264 high, 1080p30, −14 LUFS).

**Rules carried from the screens:** no CSS transitions in filmed pages (GSAP only, seekable), local woff2
fonts, no network fetches, deterministic `renderAt(t)` for the twin.

---

## 3. Visual language

- **Palette:** white surfaces; ink #0B0D10; hairlines #E6E6E2; one accent "afterburner" #E8743B for focus,
  the loop and selection. Status colours are reserved for aircraft state (FMC green, NMCM amber, NMCS red,
  NMCD violet) and priority bands; blue #2563C9 only for evidence / data lineage.
- **Type:** Manrope (UI and titles), JetBrains Mono (ids, codes, numbers, axes). Titles 64–96 px in
  motion-graphics frames, sentence case, tight tracking. The PHALANX stencil logotype is the only display face.
- **Illustration:** engineering-blueprint line art on white — 0.8–1.4 px ink lines, dimension lines,
  station markers, faint 48 px grid. The aircraft is our own parametric delta-wing schematic (planform, side
  profile, 3D x-ray). Components render as solid matte shapes inside a ghosted airframe. No stock imagery,
  no real insignia.
- **Motion:** easing `power3.out` for entrances, `expo.inOut` for camera moves; 12–18 frame entrances; camera
  never moves faster than ~35 % of frame width per second; one idea per shot; cuts on narration beats.
- **Captions:** bottom-centre, Manrope 600 34 px, ink on 92 % white pill, max 2 lines, word-timed.
- **Math frames:** white background, ink strokes, accent for the quantity that matters, equations in
  LaTeX-rendered Computer Modern replaced by Manrope-matched math where possible.

---

## 4. Screens inventory (built for acceptance)

| # | Screen | File | Role in film |
|---|---|---|---|
| 1 | Readiness (home) | `readiness.html` | Act 3 opener: 6 of 8, the eight aircraft |
| 2 | Decisions · today's board | `decisions.html` | seven decisions, triage funnel |
| 3 | Decision · recommendation (+ `?state=approved`) | `decision.html` | state · why · forecast · orders · impact |
| 4 | Decision · why / why not (`?tab=whynot`) | `decision-why.html` | evidence before 06:00, rule steps, alternatives |
| 5 | Decision · workbench | `workbench.html` | the alarm follows the aircraft; next best test |
| 6 | Aircraft twin — Evidence lens (+ Systems / exploded states) | `twin.html` | the 3D instrument |
| 7 | Orders · 08:00 (+ `?state=sign`, `?state=submitted`) | `epoch.html` | signed orders, gateway check, the log |
| 8 | Plan & what-if (+ schedule) | `plan.html`, `plan-schedule.html` | paired simulations vs doing nothing |
| 9 | Spares (+ lead time) | `spares.html`, `spares-leadtime.html` | what grounds aircraft; useful lead time |
| 10 | Fleet insights (+ NFF, integrity) | `insights.html`, `insights-nff.html`, `insights-integrity.html` | where availability went; alarms that find nothing |
| 11 | Assurance · models (+ drift) | `assurance.html`, `assurance-drift.html` | gates, drift vs change-points |
| 12 | Assurance · policies | `policies.html` | readable, versioned rules |
| 13 | Assurance · provenance | `provenance.html` | "why was this order issued?" |
| 14 | Assurance · data foundation | `data.html` | release gate, as-of store |
| 15 | Assistant drawer (over twin) | `assistant.html` | bounded agent, runtime on hardware |

All screens follow **design system v2** (`screens/SPEC.md`): one question per screen, at most three regions,
one hero number per card; detail lives on its own screen.

---

## 5. Shot-by-shot storyboard

Legend — **N** narration · **V** visual · **UI** state · **Cam** camera · **Anim** animation · **Tr**
transition out · **OST** on-screen text · **Concept** · **Tool** · **Assets**.

### ACT 0 · PROMISE (0:00–0:18)

**S01 · 0:00.0–0:04.0 (4.0 s)**
- N: "Every morning, before eight, someone decides which aircraft will fly."
- V: Pure white field (the whole film stays on white — no dark frames, no dark overlays), faint blueprint grid fades up. A single ink line draws the delta-wing planform (nose up),
  then station ticks and a dimension line "13.2 m".
- UI: none. Cam: locked, 4 % slow push-in. Anim: SVG stroke draw-on 2.4 s, ticks stagger 40 ms.
- Tr: planform scales down to become one of eight (match cut). OST: none.
- Concept: the decision, not the dashboard. Tool: HyperFrames. Assets: `aircraft.js` planform, grid.

**S02 · 0:04.0–0:09.0 (5.0 s)**
- N: "That decision should rest on everything the fleet already knows."
- V: Eight planforms in a flight-line row labelled TJ101–TJ108; six fill green (FMC), TJ101 violet hatch
  (depot), TJ108 red (awaiting parts). Clock "06:00 IST" ticks in top-right.
- Cam: slow lateral truck left→right. Anim: fills wipe bottom-up, staggered 90 ms.
- Tr: lines begin to stream out of each aircraft. OST: "Station Sulur · 06:00".
- Concept: fleet state. Tool: HyperFrames. Assets: planform ×8, SCIR palette.

**S03 · 0:09.0–0:14.0 (5.0 s)**
- N: "Health data. Technical records. Spares. Work in progress."
- V: Four streams flow right into a single point: real TJ212 sortie traces (N2, T5, HYD SYS1 pressure),
  BIT codes (HYD-101, ENG-201, LGB-501), maintenance-record rows (job ids), spares demands (D-sulur-26093-0002).
  Each stream labelled as it is named.
- Cam: pull back 10 %. Anim: traces draw left→right at sortie time scale; labels snap on the VO words.
- Tr: streams converge and draw the PHALANX logotype. OST: the four nouns.
- Concept: the four data silos the PS names. Tool: HyperFrames. Assets: `telemetry_TJ212_1hz.csv`, logo SVG.

**S04 · 0:14.0–0:18.0 (4.0 s)**
- N: "Phalanx Twin brings it together — and turns it into decisions."
- V: Logotype completes; subtitle types: "one state · one loop · one log". Small credit lower-left:
  "Dilijens · IBM Z Datathon".
- Cam: locked. Anim: logo stroke→fill 0.6 s; subtitle character stagger.
- Tr: hard cut to black text on white (problem statement). OST: as above.
- Concept: product + team. Tool: HyperFrames. Assets: `phalanx-logo.svg`.

### ACT 1 · THE PAIN (0:18–0:58)

**S05 · 0:18.0–0:25.0 (7.0 s)** — explicit pain
- N: "The problem statement is blunt. Availability is low because maintenance is reactive — and the data
  that could prevent it isn't integrated."
- V: The PS description set in Manrope like a document card ("Problem statement · Ministry of Defence · Defence
  Services Staff College"). Phrases highlight in accent as spoken: "fragmented and largely reactive",
  "not adequately integrated", "delayed fault prediction", "avoidable aircraft downtime".
- Cam: slow push to the highlighted lines. Anim: highlighter sweep 0.4 s each.
- Tr: card slides left, stat tiles enter right. OST: PS excerpt (≤ 30 words).
- Concept: explicit pain. Tool: HyperFrames. Assets: PS text.

**S06 · 0:25.0–0:32.0 (7.0 s)** — evidence that it is real
- N: "Audits keep finding the same thing: aircraft are lost to waiting — for parts, for repair, for a
  decision."
- V: Three tiles count up: "55.5–59.7 % serviceability vs a 75 % norm — Su-30MKI, CAG Report 38/2015";
  "AOG demands met within 15 days: 10.8 % — IL-76, CAG Report 24/2017"; "No weapon system had fully
  implemented predictive maintenance — main obstacle 'a lack of quality data' — DoD IG, 2022".
- Cam: locked. Anim: count-ups 0.8 s; source lines fade 0.2 s after.
- Tr: tiles collapse into a single timeline bar (S07). OST: the three facts + sources.
- Concept: waiting dominates (refined thesis, doc 01). Tool: HyperFrames.

**S07 · 0:32.0–0:40.0 (8.0 s)** — implicit pain 1: waiting
- N: "In our fleet, one aircraft has been on the ground for eighty days, waiting for a brake chute — a
  consumable whose demand simply follows landings."
- V: TJ108's 168-day availability ribbon (real states) scrolls; the NMCS block from 3 Apr grows to 80 days;
  tag "AOG demand D-sulur-26093-0002 · open 80 d". A small chute-streaming counter beside it.
- Cam: push into the red block. Anim: day counter 0→80.
- Tr: whip-pan (horizontal blur 6 frames) to TJ107. OST: "TJ108 · 80 days · awaiting brake chute".
- Concept: predictable waiting. Tool: HyperFrames. Assets: `daily_state.csv`, readiness card TJ108.

**S08 · 0:40.0–0:48.0 (8.0 s)** — implicit pain 2: false alarms feed the pipeline
- N: "Another has had its hydraulic pump removed twenty-eight times for one alarm. Every pump the shop
  tested came back: no fault found."
- V: TJ107's 61 sortie columns; 59 light up with HYD-101; wrench markers drop for each of 28 removals;
  "RTOK" stamps stack on a shop tray (33 of 33). Counters: "28 removals · 10 pumps · 792 man-hours ·
  0 confirmed".
- Cam: locked, slight parallax on stamps. Anim: columns fire in sortie order (≈ 70 ms each).
- Tr: stamps fly up and become falling alert rows (S09). OST: the counters.
- Concept: self-inflicted demand / NFF. Tool: HyperFrames. Assets: `PHX_DATA.tj107`.

**S09 · 0:48.0–0:54.0 (6.0 s)** — implicit pain 3: alert flood
- N: "Nearly twelve hundred alerts this season. More prediction alone would only add more."
- V: 1,192 tiny alert rows rain into an open funnel; counter "1,192 alerts · 168 days". The funnel stays
  clogged (resolved later in S17).
- Cam: locked. Anim: particle rain (deterministic seeded positions).
- Tr: cut to three statements. OST: "1,192 alert rows · 168 days".
- Concept: alert fatigue. Tool: HyperFrames (canvas).

**S10 · 0:54.0–0:58.0 (4.0 s)** — implicit pain 4: trust
- N: "And any answer must be explainable, honest about time — and run fully offline."
- V: Three short lines set left-aligned, each with a line icon: "A black box can't sign for airworthiness." ·
  "A model that peeks at tomorrow's data is wrong today." · "Nothing leaves an air-gapped base."
- Cam: locked. Anim: lines stagger 0.3 s.
- Tr: soft white bloom 4 frames → product window. OST: the three lines.
- Concept: trust, information discipline, air-gap. Tool: HyperFrames.

### ACT 2 · THE SOLUTION, BUILT PIECE BY PIECE (0:58–1:58)

**S11 · 0:58.0–1:04.0 (6.0 s)**
- N: "Phalanx Twin is a decision-support digital twin for the flight line."
- V: The Readiness screen flies in as a product shot (window on light stage, 8° tilt settling to flat).
- UI: `readiness.html` default. Cam: settle + 6 % push. Anim: window scale 0.92→1, shadow grows.
- Tr: window dissolves into a white canvas with the architecture's first row. OST: none.
- Tool: HyperFrames. Assets: readiness screen.

**S12 · 1:04.0–1:10.0 (6.0 s)** — Required capabilities
- N: "It answers four questions: what's happening, why, what happens next — and what we should do."
- V: Four columns draw: DESCRIPTIVE · DIAGNOSTIC · PREDICTIVE · PRESCRIPTIVE, each with its question and one
  example from our fleet ("6 of 8 mission capable" · "HYD-101 is an indication fault" · "P(RTOK) 0.98" ·
  "stop removals; troubleshoot").
- Cam: locked. Anim: columns rise with tier-badge colours.
- Tr: the columns slide up and shrink to a header strip. OST: tier names + questions.
- Concept: the four analytics tiers as a spine, not a menu. Tool: HyperFrames.

**S13 · 1:10.0–1:18.0 (8.0 s)** — Data foundation
- N: "Everything starts from one frozen data contract. A release gate admits it, and an as-of store
  guarantees we only use what was known at the time."
- V: Contract topics (param.samples · events · usage.counters · maint.records · orders) flow into a gate;
  checks tick: sha256 ✓, contract a4396f1d ✓, schema ✓, invariants ✓, scoped identity "3,388 colliding ids
  resolved" ✓ → cylinder "as-of store".
- UI cutaway (1 s): `data.html` gate card. Cam: track along the flow. Anim: ticks 120 ms apart.
- Tr: store cylinder becomes a timeline (S14). OST: "contract 0.2.0 · release gate · as-of store".
- Concept: data foundation. Tool: HyperFrames.

**S14 · 1:18.0–1:25.0 (7.0 s)** — information discipline (technical visual)
- N: "If a record wasn't ingested by six, no model, rule or order can use it."
- V: Timeline with two marks per record — t_event (hollow) and t_ingest (solid); a vertical 06:00 cut-off
  sweeps; records ingested after it turn grey "not yet known". Inline: `as_of(t): t_ingest ≤ t`.
- Cam: locked. Anim: cut-off line sweeps; grey-out.
- Tr: grey records drop away; remaining ones assemble into the twin outline. OST: `t_ingest ≤ 06:00`.
- Concept: information discipline. Tool: HyperFrames.

**S15 · 1:25.0–1:33.0 (8.0 s)** — One state
- N: "That builds one state: a belief about every aircraft and every serialised part — with its
  uncertainty."
- V: Blueprint 3-view plate (planform + side profile) draws, then lifts into the 3D x-ray twin
  (three.js) rotating 20°. Five facet labels orbit in: configuration · usage & life · evidence · health
  belief · work & availability.
- UI: twin viewport only. Cam: 3D orbit 20° in 8 s. Anim: plate → 3D cross-dissolve on matching silhouette.
- Tr: twin shrinks to the left third. OST: "one state · per tail · per serial".
- Concept: digital twin = probabilistic digital state (AIAA/NASEM; Kapteyn PGM). Tool: HyperFrames +
  three.js. Assets: `twin3d.js`.

**S16 · 1:33.0–1:43.0 (10.0 s)** — Where ML and AI fit
- N: "Engines read that state. We chose models that fit sparse, censored maintenance data — calibrated
  classifiers, Bayesian isolation, survival models — and kept time-series foundation models as baselines,
  not decision-makers."
- V: Three engine blocks fill right of the twin: DIAGNOSTIC (BIT/NFF episodes · residuals + CUSUM ·
  D-matrix + noisy-OR · sensor vs component), PREDICTIVE (CND classifier · Bayesian Weibull survival ·
  state-space degradation · usage · spares demand · lead-time survival), PRESCRIPTIVE (expected-cost rules +
  value of information · CP-SAT plan · METRIC spares · AOG desk). A side rail stamps "baseline only" on
  TimesFM-3 / Chronos-2 and "not used" on deep RUL and RL, each with a one-line reason (licence; censoring;
  no failure labels).
- Cam: slow push right. Anim: blocks build; arrows to and from the state ("findings + posteriors").
- Tr: arrows converge downward into triage. OST: model names, small.
- Concept: model selection on evidence. Tool: HyperFrames.

**S17 · 1:43.0–1:50.0 (7.0 s)** — Triage
- N: "Triage turns twelve hundred alerts into seven decisions."
- V: The S09 funnel returns and unclogs: 1,192 alert rows → 326 issues → 33 open → 7 on today's board,
  with the rule chips (dedupe · episodes · inhibition · standing/chatter · stale) and "gates → C×U → value".
- Cam: vertical tilt down the funnel. Anim: counters step with each stage.
- Tr: the 7 items become cards entering a ring (S18). OST: the four numbers.
- Concept: issues, not alerts (ISA-18.2). Tool: HyperFrames.

**S18 · 1:50.0–1:58.0 (8.0 s)** — Policies, fork gate, one loop, one log
- N: "Versioned policies and optimisers propose orders, simulation tests them against the status quo, a
  person approves — and every step lands on one tamper-evident log."
- V: The loop ring assembles clockwise: 06:00 SNAPSHOT → ANALYZE → PLAN (policies L1–L4, optimisers) →
  FORK GATE (paired simulations) → BOARD (human gate) → 07:45 FREEZE → 08:00 ORDERS → RECONCILE. Beneath the
  ring, a hash-chained log ribbon writes one block per stage; dashed arrow "outcomes → labels → learning"
  closes the loop back to the engines.
- Cam: pull back to reveal the full architecture (twin, engines, triage, loop, log). Anim: ring segments draw
  in time with VO.
- Tr: push through "BOARD" into the product. OST: "one state · one loop · one log".
- Concept: the whole architecture, cohesive. Tool: HyperFrames.

### ACT 3 · ONE REAL MORNING (1:58–3:47)

**S19 · 1:58.0–2:05.0 (7.0 s)**
- N: "Monday, six a.m. Six of eight aircraft are mission capable."
- UI: `readiness.html`. Cam: push to the "6 of 8" card (1.8×), then glide across the fleet cards to
  TJ107. Anim: hero count-up; fleet card highlight ring follows camera.
- Tr: camera continues down to the downtime card. OST: none (UI speaks).
- Concept: descriptive state. Tool: HyperFrames.

**S20 · 2:05.0–2:12.0 (7.0 s)**
- N: "This season, most of the waiting came from tyres and brake chutes — demand you can predict from the
  flying plan."
- UI: `insights.html` (Where availability went). Cam: push to the tyres + chutes finding. Anim: waterfall bars grow; finding highlights.
- Tr: cursor clicks "Open board". OST: "69 % of awaiting-parts time · tyres + brake chutes".
- Concept: diagnostic decomposition. Tool: HyperFrames.

**S21 · 2:12.0–2:18.0 (6.0 s)**
- N: "Today's board has seven issues — each with the evidence and the score behind it."
- UI: `decisions.html`. Cam: wide, then slow pan down the seven rows to the TJ107 row; the triage funnel counts down. Anim: rows
  enter with a 60 ms stagger; the funnel numbers count 1,192 → 326 → 33 → 7.
- Tr: cursor selects TJ107. OST: "7 issues · budget ≤ 10".
- Concept: triage output; no opaque scores. Tool: HyperFrames.

**S22 · 2:18.0–2:27.0 (9.0 s)**
- N: "TJ107. The system doesn't say replace the pump. It says stop — and shows why."
- UI: `decision.html` for TJ107 HYD-101. Cam: push to the recommendation, then STATE → WHY → FORECAST cards, then ORDERS and IMPACT; 1.5 s cutaway to `decision-why.html` (evidence ingested before 06:00). Anim: hero
  numbers count up (28 · 0 of 107 · 98 %); the impact +21.7 grows from 0; in the cutaway the six evidence rows
  tick ✓ one by one and rule steps 2–3 light.
- Tr: the pump chip expands into the twin (shared-element transition). OST: none.
- Concept: explainable recommendation (state · why · forecast · orders · impact). Tool: HyperFrames.

**S23 · 2:27.0–2:37.0 (10.0 s)**
- N: "In the twin, the alarm's reporter and its suspects light up where they sit in the aircraft."
- UI: `twin.html` Evidence lens. Cam: 3D orbit 25° around TJ107; HTML camera push to the viewport.
  Anim: reporter halo pulses; dashed evidence arcs flow BHEEM EU → pump (thick, 0.8) and → AMAGB (thin, 0.2);
  labels pop with leader lines.
- Tr: lens switches to Systems for 1.5 s (hydraulic SYS1/SYS2 networks), back to Evidence. OST: none.
- Concept: 3D as spatial index and lens. Tool: HyperFrames + three.js `renderAt(t)`.

**S24 · 2:37.0–2:46.0 (9.0 s)**
- N: "It stayed with this aircraft through ten different pumps. The evidence follows the tail — not the
  part."
- UI: twin insight panel + scrubber. Cam: push to the sortie strip; then down to the as-of scrubber.
  Anim: sortie strip fills; scrubber handle drags back to 21 May — the twin re-colours to what was known
  then (time travel), then returns to 22 Jun.
- Tr: match-cut the strip into a Manim axis. OST: "59 of 61 sorties · 10 pumps".
- Concept: sensor-vs-component natural experiment; as-of honesty. Tool: HyperFrames.

**S25 · 2:46.0–2:56.0 (10.0 s)** — maths: Bayes from outcomes (Manim M1)
- N: "Learned from outcomes, the chance this pump is actually faulty is half a percent. Remove it again,
  and it's ninety-eight percent likely to come back 'no fault found'."
- V: Left: the contract's suspect weight 0.8 as a bar. Right: Beta posterior density for P(confirmed |
  HYD-101) built from 0 of 107 jobs → collapses against zero; mean 0.005, 95 % interval [0.000, 0.023]
  shaded. Then a second density for P(RTOK | removal) from 33 of 33 → piles near 1: 0.985 [0.93, 1.00].
  Equation: P(θ | data) ∝ θ^k (1 − θ)^(n−k) · Beta(½, ½).
- Cam: locked, 3b1b-style. Anim: densities morph as counts increment.
- Tr: densities shrink into a chip inside the workbench. OST: the two intervals.
- Concept: uncertainty from base rates (diagnostic + predictive). Tool: Manim. Assets: counts above.

**S26 · 2:56.0–3:03.0 (7.0 s)**
- N: "So it recommends the test that resolves the most uncertainty per man-hour."
- UI: `workbench.html`. Cam: push to the next-best-test ranking; then the posterior sweep.
  Anim: information-gain bars grow; the top test highlights.
- Tr: cursor clicks the policy reference. OST: "information gain per man-hour".
- Concept: value of information. Tool: HyperFrames.

**S27 · 3:03.0–3:10.0 (7.0 s)**
- N: "Every recommendation comes from a rule you can read. Hard limits live in code; anything
  airworthiness-sensitive waits for a human signature."
- UI: `policies.html`: P-DEC-01 table, row r3 highlighted with the real zen-engine trace and evaluation time;
  layer stack L1–L4; HUMAN-only badge on CHANGE_MONITORING_CONFIG. Cam: push along the matched row.
- Tr: the row's output flows into a fork icon. OST: "P-DEC-01/1.4.0 · row r3".
- Concept: policies as code, bounded authority. Tool: HyperFrames.

**S28 · 3:10.0–3:19.0 (9.0 s)** — maths: paired forks (Manim M5) → Plan & what-if
- N: "Before it reaches the board, each order is tested on paired simulations of the same futures — our plan
  against the status quo."
- V: (4.2 s Manim) 30 futures run twice — status quo and plan — on the same random draws, joined pairwise;
  they collapse into the 30 paired differences with the 95 % CI (+0.217 [0.167, 0.268]). (5 s UI) `plan.html` scenario
  comparison with the S1 KPI deltas and CIs (MC +0.217 [+0.167, +0.268], man-hours −115.7 [−132.6, −98.7]).
- Cam: Manim locked → UI push to the delta table. Anim: CI bars grow from zero.
- Tr: cut. OST: "belief mode · n = 30 paired runs".
- Concept: common random numbers, fork gate. Tool: Manim + HyperFrames.

**S29 · 3:19.0–3:27.0 (8.0 s)** — maths: the lead-time race (Manim M3) → Spares
- N: "For parts, a warning only helps if it beats the lead time. Expediting TJ108's chute returns it
  eighty-five days sooner — and the fork gate drops orders, like early tyres, that change nothing."
- V: (3.6 s Manim) heavy-tailed lead-time distribution; a warning window slides; only the area it beats
  shades; expected remaining wait grows as a demand ages. (UI) `spares.html`: TJ108's chute demand (80 d) with
  its fork result — 30 days: no change; 400 days: back 85 days sooner, AOG days −62.1 [−83.8, −40.4]; then the
  TJ105 tyre requisition marked "dropped by fork gate · no KPI change in 30 d, cost +0.29".
- Cam: locked → push to the TJ108 row. Anim: shading sweeps.
- Tr: cursor "Approve". OST: "useful lead time = warning − lead time".
- Concept: prescriptive spares (METRIC, consumables). Tool: Manim + HyperFrames.

**S30 · 3:27.0–3:35.0 (8.0 s)**
- N: "At seven forty-five the board freezes. At eight, orders go out — each one cited, signed where it must
  be, and safe to retry."
- UI: `decision.html?state=approved` → `epoch.html` (07:52, one signature needed) → `epoch.html?state=sign` (signature sheet; "Sign with station key") →
  `epoch.html?state=submitted` (ACCEPTED → QUEUED). Cam: three quick pushes. Anim: status pills flip.
- Tr: the log panel slides into provenance. OST: order id typed: `phx:P-DEC-01:1.4.0:20260622T0800:TJ107:…`.
- Concept: human gate, idempotent orders, authority. Tool: HyperFrames.

**S31 · 3:35.0–3:41.0 (6.0 s)**
- N: "Ask why any order was issued, and the chain answers — from data release to signature."
- UI: `provenance.html`. Cam: vertical scroll down the hash chain. Anim: each block's hash links to the next
  (prev_hash → hash glow); "Replay → identical order ids ✓".
- Tr: cut. OST: none.
- Concept: one log; auditability. Tool: HyperFrames.

**S32 · 3:41.0–3:47.0 (6.0 s)**
- N: "Outcomes become labels. Models and rules are promoted only through gates — and it says so when the
  evidence isn't there yet."
- UI: `assurance.html`: registry states; the removal-hazard row reads INSUFFICIENT_EVIDENCE; drift panel
  with an "expected shift" at a known change-point. Cam: push to those two elements.
- Tr: assistant drawer slides in from the right. OST: none.
- Concept: learning & assurance (EASA learning assurance, DRDO ETAI). Tool: HyperFrames.

### ACT 4 · BOUNDED AGENTS, PROOF, CLOSE (3:47–4:05)

**S33A–S33D · 3:55–4:33 (37.6 s) — the assistant, shown by its value** (`film/act4.html`, built and rendered)
- **S33A · the pain (8.7 s).** N: "Today, one question means five places: the tech log, the BIT downloads, the parts
  ledger, the shop reports and the plan." V: the question types into a pill; five real system cards fan in on
  their spoken words (64 HYD-101 jobs · 63 events · 28 pump removals · 33 / 33 RTOK · 61 sorties), tilted in
  3D; a cursor zig-zags between them leaving a trail; counter "5 systems · 0 answers".
- **S33B · just ask (8.1 s).** N: "Here, you just ask. The assistant plans, then reads only what it needs — as of
  06:00 — through read-only tools." V: the cards collapse into the composer (match cut); the live 3D twin
  appears; a plan pill fans out five tool nodes; as each tool runs, a blue beam lands on the exact component it
  reads (aircraft summary → avionics bay, recurrence → BHEEM EU reporter, serial history → hydraulic pump,
  evidence chain → AMAGB, what-if → engine) and that part lights up in the twin while data packets flow back;
  "reads as of 22 Jun 06:00"; the not-yet-ingested INSTALL record is struck out "not used"; READ-ONLY badges.
- **S33C · the answer (11.5 s).** N: "Every number in its answer comes from a tool, never from the model, and every
  claim cites its records — even the what-if, from the same paired simulations the board uses." V: the answer
  streams at decode speed with numbers as tool placeholders `{{r2.fired}}` that decode into 59 of 61 · 28 ·
  10 · 33 / 33 · 107, each tagged ①–⑤; "gpt-oss-20b writes the words — never the numbers"; citation threads
  run from the gutter to six record chips "ingested before 06:00 ✓"; the what-if card "+21.7 pts · same
  simulations the decision board uses".
- **S33D · guardrails on hardware (9.4 s).** N: "It runs on one air-gapped box, first words in about a second — and
  it can only draft. The signature stays with the officer." V: the station server with an air-gap ring; the
  Model → Runtime → Hardware → Execution → Output strip counts up (gpt-oss-20b · llama.cpp · 15.3 / 128 GB ·
  1.1 s · 70 tok/s · cited, draft only); a "Submit order" button hits a "NO WRITE PATH" wall and becomes a
  DRAFT; the draft lands on the signature sheet and the Engineering Officer's signature draws.
- Tool: HyperFrames + live three.js twin. Music: riser into "Here, you just ask", full groove under the answer.

**S34 · 3:55.0–4:00.0 (5.0 s)** — observed result
- N: "On thirty paired simulations, the TJ107 decision adds twenty-two points of mission-capable time next
  month — and saves a hundred and sixteen man-hours."
- V: Result cards (belief mode, n = 30 CRN pairs, 30 days, vs status quo): MC +0.217 [+0.167, +0.268];
  man-hours −115.7 [−132.6, −98.7]; AOG days −3.7 [−5.3, −2.1]; flying task +0.224 [+0.185, +0.263];
  guardrail in-flight failures +0.07 [−0.03, +0.16] (CI includes 0). Small second row: TJ108 expedite (400 d)
  AOG days −62.1; TJ105 early tyres: no change → dropped.
- Cam: locked. Anim: CI bars grow. Tr: fade to white. OST: the KPI deltas above.
- Concept: credibility claim = fork deltas vs status quo. Tool: HyperFrames.

**S35 · 4:00.0–4:05.0 (5.0 s)** — close
- N: "Phalanx Twin. One state. One loop. One log."
- V: The three phrases stack; the planform from S01 redraws behind them; PHALANX logotype; tagline
  "Real-time AI for critical decisions · live on IBM LinuxONE"; credit "Dilijens · IBM Z Datathon" (v2).
- Anim: logo stroke→fill; music resolves. Tr: hold 1 s on white.
- Tool: HyperFrames.

**Narration total ≈ 560 words ≈ 3:45 of speech at 150 wpm, leaving ≈ 20 s of breathing room for music
hits and transitions.**

---

## 6. Maths and technical visualisation clips (Manim)

| Clip | Shot | Content | Data |
|---|---|---|---|
| M1 Bayes from outcomes | S25 | Beta(½,½) prior → posterior on 0/107 confirmed; RTOK 33/33 | records as of snapshot |
| M3 Lead-time race | S29 | lead-time density; warning window; conditional remaining wait | closed demands (median 4.6 d, p90 38.3 d, max 91.6 d) and the data layer's AOG lead-time model (median ≈ 29 d, mean ≈ 159 d) — labelled separately |
| M5 Paired forks | S28 | CRN lanes, paired vs unpaired Δ distribution, CI | S1 per-member paired KPI differences (`data/forks/scenario_S1.json`, 30 pairs) |
| (spare) M4 Expected-cost threshold | optional | act when p > C_FP/(C_FP+C_FN); VOI band p=0.2, d=0.7, f=0.05 → p⁻ 0.07, p⁺ 0.78 | doc 06 |
| (spare) M8 Memory budget | optional for S33 | 12.1 GB weights + 0.46 GB KV(16K) + 2.7 GB buffers = 15.3 GB of 128 GB | `research/metrics.md` |

---

## 7. Audio

- VO: one calm, mid-pitch narrator; scratch with Kokoro TTS; final either Kokoro or a recorded human voice.
- Music: minimal pulse/pad, 92–96 BPM, builds at S18 and S28, resolves at S35; −20 LUFS under VO with
  side-chain ducking (−8 dB). Needs a licence-clean track (CC0 or composed) — to be chosen.
- SFX: very soft UI ticks on clicks and status flips only; no whooshes.

---

## 8. Open items before production

1. Approve the 13 screens (or list changes).
2. Fork values are filled (S1–S3, 30 CRN pairs each, belief mode).
3. Choose the voice (Kokoro vs recorded) and a music track.
4. Confirm the "agentic" framing in §1 (bounded loop agent + bounded assistant).
