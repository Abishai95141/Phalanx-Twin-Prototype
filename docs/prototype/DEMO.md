# Phalanx Twin prototype — demo guide

**Link:** https://148.100.99.205/ (plain http:// works too; on an IPv6-only network: http://148-100-99-205.sslip.io/). Everything runs on the
team's LinuxONE server: the simulated fleet (the Phalanx data layer), the models, the policies, the daily loop,
the event log, the API and the screens. All data is synthetic and not validated.

**Before a demo:** `proto/deploy/remote.sh 'proto/deploy/services.sh reset'` — archives the live run and rebuilds the
fleet at **Mon 22 Jun 2026 06:00 IST** (~4 min); the paired simulations for the board then pre-run (~25 min).

## Open with the platform (≈ 1 minute)

- "Everything you are about to see runs on **IBM LinuxONE** — a mainframe-class Linux server on the s390x
  architecture: the fleet simulator, the models, the rules engine, the daily loop, the audit log and this web app."
- "We rebuilt the whole simulated fleet on LinuxONE and it matches the reference data **row for row** — the same
  decisions can be reproduced on any architecture" (Assurance → gate G1).
- "Why IBM Z: the system that keeps aircraft available should itself be built for availability, cryptographic audit
  and confidential computing — and the AI can sit next to the data." Details and sources: `docs/ibmz/README.md`.

## The walk-through (≈ 8 minutes)

| # | Page | Click / show | What is real behind it |
|---|---|---|---|
| 1 | **Readiness** | 6 of 8 mission capable; MC 54.5 % over 30 days vs the 75 % norm; 25.4 % of time waiting for parts; the eight aircraft cards | as-of store over the data layer's records (only what was ingested by 06:00); triage writes each card |
| 2 | **Decisions** | "How 1,192 alerts became 9 decisions"; P1 gear warnings, P2 TJ107 hydraulic alarm, TJ108 chute… | episodes → issues → hard gates → consequence × urgency → zen-engine decision tables |
| 3 | **Recommendation** (TJ107) | 30 pump removals, 0 of 118 confirmed, 98.6 % no-fault-found forecast; two orders; **Impact +18 pts MC** | false-alarm model (Beta-Binomial champion vs logistic-regression challenger); paired what-if runs of the simulator (10 CRN pairs) |
| 4 | **Why / Why not** | evidence rows all ingested before 06:00; the P-DEC-01 rule trace; alternatives | zen-engine trace; evidence checked against ingest time |
| 5 | **Workbench** | the alarm follows the aircraft, not the pump; suspects (indication path 0.56, gearbox drive 0.44, pump < 0.0001); best next test; **Draft as order** | noisy-OR isolation + expected information gain over 24 assumption settings |
| 6 | **Aircraft twin** | lenses: status, evidence, false alarm, life, **removal risk**, **engine margin**; pump panel with removal risk and 80 % interval | removal-risk Weibull model (champion on a held-out seed: Brier 0.059 vs 0.074); engine-health Kalman + CUSUM on the generated engine trend (8/8 planted faults caught) |
| 7 | Back on **Recommendation** | **Approve**; on TJ102 HYD-001 show Impact −10.6 pts → **Reject** ("worse than doing nothing") | the human gate: consent by default, every action on the hash-chained log |
| 8 | **Epoch** | **Sign** the monitoring change (HUMAN-only); then **Advance** | 07:45 freeze → 08:00 orders through the data layer's own gateway → the fleet simulated to the next 06:00 |
| 9 | **Readiness / Decisions** (Tue 23 Jun) | the new day; TJ107's page shows yesterday's orders and their data-layer status | outcomes come back as records (orders.status), logged each morning |
| 10 | **Provenance** | the chain of TJ107's order from snapshot → triage → policy evaluation → evidence → recommendation → fork → approval → freeze → gateway → status; **Verify**, **Replay** | one blake2b hash chain; replay recomputes the snapshot hash, order id and policy trace |
| 11 | **Policies / Assurance** | the six decision tables and their versions; the authority matrix; gates G0–G3; model cards | everything read from the running system |

## What is honest to say

- Models and policies are real (scikit-learn, lifelines, numpy, NetworkX, zen-engine) and trained or evaluated on
  the team's simulator data. They show the system works end to end — not that they predict real Tejas failures.
- The engine trend is generated (labelled "Generated engine trend"); the engine model finds faults we planted.
- Removal risk exists only for hydraulic pumps; every other part says "insufficient evidence".
- Moving parts between aircraft is not simulated (each aircraft is its own world in data-layer preview v0.9).
