# Illustration plates — Phalanx Twin film

Thirteen blueprint plates and one style key, all clean SVG in a `viewBox="0 0 1600 900"`. At 1:1 (1600 px wide)
the strokes are ink 1.5 / 0.9 / 0.6 px. Accent `#E8743B` marks only the subject of each plate. Blue `#2563C9`
marks only data, evidence and signals. Each plate is also mirrored to `video/screens/assets/illus/` for the contact sheet
`video/screens/illustrations.html`. The sheet takes `?p=1…4` for pages, `?one=N` for one plate at 1:1, and
`&z=2&cx=…&cy=…` to zoom.

Rebuild everything with `cd src && python3 build.py`. Do not hand-edit the SVGs. Geometry lives in `src/plateNN_*.py`, and the
shared style is in `src/lib.py`.

## Using them in a composition

- **Inline the SVG.** Do not use `<img>`. Inline SVG lets the page fonts (Manrope, JetBrains Mono) apply and lets
  GSAP reach the parts. Each root is `svg#ill-<prefix>.phx-ill`. All ids carry the plate prefix, so plates can share a
  page.
- **Draw-on.** Stroke geometry carries the class `draw`, so use `root.querySelectorAll('.draw')` with `PHXF.draw`.
  Callouts are `g.callout`, and each has a `.leader` and a `.bubble`.
- **Sheet chrome.** Hide the frame and title block with `#<prefix>-sheet` when a shot only wants the drawing.
- **Explode.** In `hyd-pump.svg`, each assembled part carries `data-explode-x` / `data-explode-y`. Tween it by those
  offsets and it lands on its exploded twin, the `#pump-…-x` group.
- **Fill-ins.** `#srv-slot-<model|runtime|memory|exec>-value` are empty `<g>` anchors for typed runtime stats. The
  LRU data plate leaves `#lru-plate-pn` and `#lru-plate-sn` blank.

## Ids worth animating

| # | File | Subject (accent) | Main ids |
|---|---|---|---|
| 1 | `aircraft-3view.svg` | AMAGB + hydraulic pumps | `#ac-plan`, `#ac-plan-outline`, `#ac-side`, `#ac-side-outline`, `#ac-front`, `#ac-stations`, `#ac-dim-length` / `-span` / `-height`, `#ac-c1…7`, `#ac-zone-amagb`, `#ac-side-amagb`, `#ac-zone-radar` / `-cockpit` / `-avionics` / `-engine` / `-chute` / `-mlg-l` / `-mlg-r`, `#ac-legend`, `#ac-proj` |
| 2 | `hydraulic-system.svg` | indication path | `#hyd-sys1`, `#hyd-sys2` (each with `-reservoir`, `-pump`, `-filter`, `-check`, `-accumulator`, `-pressure`, `-return`, `-indication`, `-pressure-switch`, `-transducer`), `#hyd-eu`, `#hyd-bus`, `#hyd-caution`, `#hyd-c1…5` (path order), `#hyd-amagb`, `#hyd-fcs`, `#hyd-act-*` |
| 3 | `hyd-pump.svg` | swashplate | `#pump-assembled` → `#pump-housing`, `#pump-shaft`, `#pump-seal`, `#pump-bearing`, `#pump-control-piston`, `#pump-swashplate`, `#pump-slippers`, `#pump-barrel`, `#pump-pistons`, `#pump-valveplate`, `#pump-portblock`; `#pump-exploded` (same parts with `-x`), `#pump-alpha`, `#pump-viewb`, `#pump-dataplate` (`#pump-plate-sn` = HYDP-000010) |
| 4 | `f404-engine.svg` | FADEC | `#eng-section` / `#eng-section-lower` → `#eng-fan`, `#eng-hpc`, `#eng-combustor`, `#eng-turbines`, `#eng-exhaust`, `#eng-afterburner`, `#eng-nozzle`, `#eng-flow`; `#eng-stations`, `#eng-st-2` / `-25` / `-3` / `-4` / `-5` / `-7`; `#eng-fadec`, `#eng-harness`, `#eng-agb` |
| 5 | `main-gear-tyre.svg` | tyre | `#mlg-tyre`, `#mlg-tyre-section`, `#mlg-leg` (`#mlg-strut`, `#mlg-torque-links`, `#mlg-drag-brace`, `#mlg-retraction`), `#mlg-gauge`, `#mlg-wear-limit`, `#mlg-tread-dim`, `#mlg-counter` (`#mlg-count-used`, `#mlg-cell-1…8`), `#mlg-dim-dia` |
| 6 | `brake-chute.svg` | chute (packed + canopy) | `#chute-airframe`, `#chute-canister`, `#chute-packed`, `#chute-deployed` (`#chute-riser`, `#chute-lines`, `#chute-canopy`, `#chute-pilot`), `#chute-detail-d`, `#chute-streamings` (`#chute-tick-1…45`), `#chute-signal` |
| 7 | `avionics-lru.svg` | BIT indicator | `#lru-body` (`#lru-front`, `#lru-side`, `#lru-top`), `#lru-j1…3`, `#lru-bit` (`#lru-bit-led`), `#lru-handle`, `#lru-dataplate`, `#lru-tray`, `#lru-view-a` |
| 8 | `station-server.svg` | air gap | `#srv-appliance`, `#srv-desk`, `#srv-ports`, `#srv-power-cord`, `#srv-airgap` (`#srv-plug`, `#srv-gap`, `#srv-shield`), `#srv-slot-model` / `-runtime` / `-memory` / `-exec` |
| 9 | `sortie-download.svg` | removable recorder | `#dl-aircraft`, `#dl-bay`, `#dl-recorder`, `#dl-move-1`, `#dl-ground-station`, `#dl-move-2`, `#dl-topic-param-samples` / `-events` / `-usage-counters` / `-maint-records` / `-orders` |
| 10 | `contract-gate.svg` | 06:00 cut-off plane | `#gate-pipe-*` (with `.packet` / `.flow`), `#gate-gate`, `#gate-manifold`, `#gate-store` (`.slice.known` / `.slice.future`, `.record`), `#gate-cutoff`, `#gate-check-1…5` |
| 11 | `hash-chain.svg` | chain head | `#chain-block-1`, `-2`, `-3`, `-4-10`, `-11`, `-12`, `-13`, `-14-19`, `-20` (each with `-prev` / `-hash`), `#chain-link-r1-0…3`, `#chain-link-wrap`, `#chain-link-r2-0…2`, `#chain-formula`, `#chain-head-hash` |
| 12 | `mapek-loop.svg` | the loop ring | `#loop-seg-1…8`, `#loop-node-snapshot` / `-analyse` / `-plan` / `-forkgate` / `-board` / `-freeze` / `-orders` / `-reconcile`, `#loop-knowledge`, `#loop-learning`, `#loop-log-1…9` |
| 13 | `assistant-tools.svg` | plan node | `#tool-plan`, `#tool-aircraft-summary`, `-event-recurrence`, `-serial-history`, `-evidence-chain`, `-what-if`, `#tool-call-<fn>` / `#tool-result-<fn>`, `#tool-output` |
| – | `style-key.svg` | — | the key itself (weights, line types, hatching, colours, type) |

## Sources of every value

- **Aircraft geometry:** `screens/assets/aircraft.js`, at 13.2 m long, 8.2 m span and 4.4 m high.
- **Dictionary values:** HYD.*/ENG.*/USAGE.*/MX.* channel ids, 280 bar, 26 in tyre, 16.9 bar,
  chute life 45, BHEEM_EU RT 7 and 40 Hz, and the recorder sinks MPDRU / HUMS DAU / ECMS.
- **Gate checks:** `data/data_foundation_asof_20260622.json`.
- **Chain hashes and times:** `data/decision_flow.json`. The values are real blake2b hashes.
- **Spec values:** HYDP-000010, TJ107, HYD-101 and 7 / 8 come from `screens/SPEC.md`.

Everything is a synthetic schematic, labelled "Phalanx Twin · schematic". None of it is a real Tejas or IAF drawing.
