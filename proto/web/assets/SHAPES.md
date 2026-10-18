# Screen data shapes — the `/api` contract of the loop pages

The eight loop pages (`readiness`, `decisions`, `decision`, `decision-why`, `workbench`, `twin`, `epoch`,
`provenance`) read only the JSON below. `assets/api.js` fetches it from the ground API
([DEVELOPMENT.md §2.11](../../../docs/prototype/DEVELOPMENT.md)) and stores it in a `window.PHX_*` global; with
`?source=film` the same shapes come from the film data files (`assets/data*.js`, adapted by
`assets/data-film.js`), so **`data-film.js` is the reference implementation of every shape here** — run it in a
browser console (`PHX_FILM.issue('TJ107-HYD-101')`) to see a complete example.

## Conventions

| Rule | |
|---|---|
| **req** / **opt** | *req* fields must be present. *opt* fields may be omitted (or `null`); the page then derives them as stated, or hides that part. Extra fields are ignored. |
| Times for display | strings in IST as the film shows them: `"19 Jun 22:27"` (day month hh:mm), `"06:00"` (hh:mm). ISO strings (`"2026-06-22T06:00+05:30"`) only where the type says *ISO*. |
| Display strings | fields typed *text* are shown as sent (the backend words them; templates are fine). Numbers typed *num* are formatted by the page. |
| Source labels | every generated or modelled value carries `source`: `"Simulated fleet"`, `"Simulated fleet history"` or `"Generated engine trend (overlay v0.1)"` (`interfaces.SOURCE_LABEL`). Never "real", "validated", "mock" or "preview". |
| Ids | issue ids as in triage (`"TJ107-HYD-101"`, `"P4-ADVISORY"`); order ids per §2.9; tails `"TJ101"`…; serials are opaque and scoped by tail (rule 4). |
| Errors | GET: `404` = nothing there (the page says so), anything else = the page shows which path failed. POST: return `{"detail": "…"}` with `404` (not implemented / unknown id) or `409` (refused: board frozen, already decided, signature missing …); the page shows the detail in a chip. |

Which page loads what (in this order; *optional* loads may 404 without breaking the page):

| Page | Loads |
|---|---|
| readiness | epoch *opt*, board *opt*, readiness |
| decisions | epoch, board |
| decision, decision-why | epoch, board, issue(`?issue=` or `board.focus` or `board.board[0].id`) |
| workbench | epoch, board, workbench(same issue id) |
| twin | epoch *opt*, board *opt*, readiness *opt*, twin(`?tail=` or `readiness.focus` or the focus issue's tail) |
| epoch | epoch |
| provenance | epoch, board, provenance(`?order=` or the focus issue's AGENT order) |

---

## `GET /api/epoch` → `PHX_EP`

The epoch state; also drives the sidebar (date, freeze countdown, decisions due) on every page.

| Field | Type | | Meaning |
|---|---|---|---|
| `clock.epoch` | text | req | `"20260622T0800"` |
| `clock.day` | text | req | `"Mon 22 Jun"` |
| `clock.asof` | text | req | snapshot time for the head chip, `"Mon 22 Jun 06:00 IST"` |
| `clock.now` | hh:mm | req | logical session time (`"06:12"`); sidebar countdown = next step − now |
| `clock.snapshot`, `clock.freeze`, `clock.issue` | hh:mm | req | `"06:00"`, `"07:45"`, `"08:00"` |
| `clock.engines` | hh:mm | opt | when engines sealed (`"06:04"`); sidebar shows "waiting" when absent |
| `clock.phase` | enum | req | `BOARD_OPEN` · `FROZEN` · `SUBMITTED` · `STEPPED` (the last two = orders issued) |
| `clock.due` | int | req | decisions on today's board |
| `timeline[]` | list | req | steps in order; keys used: `SNAPSHOT`, `ENGINES`, `BOARD_OPEN`, `FREEZE`, `SIGN`, `SUBMIT` |
| `timeline[].key`, `.t`, `.label`, `.state` | text, hh:mm, text, enum | req | `state`: `done` · `now` · `next` |
| `timeline[].done_label`, `.done_t` | text, hh:mm | opt | label/time once done (`"Board frozen"`; `"Signed"` at `"07:57"`) |
| `orders[]` | list | req | every candidate order of the epoch, kept or dropped |
| `orders[].order_id`, `.action`, `.target_tail_no`, `.item` | text | req | `item` = issue id the order belongs to |
| `orders[].what` | text | req | short object of the order: `"Gear unsafe · LGB-501"` |
| `orders[].authority` | `AGENT`\|`HUMAN` | req | HUMAN = needs a named signature |
| `orders[].status` | enum | req | `AWAITING_APPROVAL` · `READY` · `NEEDS_SIGNATURE` · `ACCEPTED` · `REJECTED` · `NOT_ISSUED` · `SNOOZED` · `DROPPED` |
| `orders[].desk_state` | enum | opt | the board's view: `PROPOSED` `APPROVED` `REJECTED` `SNOOZED` `DROPPED` `NOT_ISSUED` `SUBMITTED` |
| `orders[].snooze_until`, `orders[].note` | ISO, text | opt | shown as "snoozed until Tue 23 Jun" / "rejected: <note>" |
| `orders[].signed_by` | text\|null | req | signer name once signed |
| `orders[].dropped` | `{label, reason}`\|null | req | set when the fork gate dropped it: `{"label": "Tyre requisition", "reason": "no change in 30 paired simulations"}` |
| `orders[].dry` | object | req | gateway checks: `schema_ok`, `contract_ok`, `t_issued_ok`, `authority_ok`, `evidence_ok` (bool), `verdict` (`ACCEPTED` …) |
| `signatures[]` | list | opt | the sign sheet for HUMAN orders: `{order_id, title, text, rows: [{k, v, mono?, muted?}]}` |
| `previous` | object | opt | the last submitted epoch: `{epoch, day, accepted, orders: [{order_id, item, action, target_tail_no, what, verdict, status, status_at, signed_by}]}`; shown under the gateway card |
| `log_summary[]` | list | opt | "Written to the one log" card after submit: `[{label, hash}]` (hash ≥ 8 hex) |

```json
{ "clock": { "epoch": "20260622T0800", "day": "Mon 22 Jun", "asof": "Mon 22 Jun 06:00 IST", "now": "06:12",
             "snapshot": "06:00", "engines": "06:04", "freeze": "07:45", "issue": "08:00", "phase": "BOARD_OPEN", "due": 7 },
  "timeline": [ { "key": "SNAPSHOT", "t": "06:00", "label": "Snapshot sealed", "state": "done" },
                { "key": "FREEZE", "t": "07:45", "label": "Board freezes", "done_label": "Board frozen", "state": "next" } ],
  "orders": [ { "order_id": "phx:P-DEC-01:1.4.0:20260622T0800:TJ107:CHANGE_MONITORING_CONFIG:6c744e071d8445f0",
                "item": "TJ107-HYD-101", "action": "CHANGE_MONITORING_CONFIG", "target_tail_no": "TJ107", "what": "Filter HYD-101",
                "authority": "HUMAN", "status": "NEEDS_SIGNATURE", "signed_by": null, "dropped": null,
                "dry": { "schema_ok": true, "contract_ok": true, "t_issued_ok": true, "authority_ok": true, "evidence_ok": true, "verdict": "ACCEPTED" } } ],
  "signatures": [ { "order_id": "phx:…:6c744e071d8445f0", "title": "Filter HYD-101 on TJ107",
                    "text": "The code is masked while the indication path is troubleshot. It is still evaluated, only not recorded.",
                    "rows": [ { "k": "Order", "v": "CHANGE_MONITORING_CONFIG", "mono": true }, { "k": "In-flight failures", "v": "+0.07 · not significant", "muted": true } ] } ],
  "log_summary": [ { "label": "Board frozen", "hash": "b73e0c5c" }, { "label": "Chain head", "hash": "afd2fdab" } ] }
```

## `GET /api/readiness?asof=` → `PHX_DATA`

| Field | Type | | Meaning |
|---|---|---|---|
| `asof` | ISO | req | snapshot time |
| `fleet[]` | list | req | one row per tail, in display order |
| `fleet[].tail`, `.state` | text, enum | req | state ∈ `FMC` `PMCM` `NMCM_S` `NMCM_U` `NMCS` `NMCD` |
| `fleet[].since_days`, `.fh30` | num | req | down for (days) / flown in 30 days (FH) |
| `fleet[].open_jobs`, `.deferred`, `.tyre_ldg` | int | req | used for the default card text and the twin's life lens |
| `fleet[].card` | object | opt | `{headline, detail, tone?, zones: [{zone, tone}]}` — why it is down / what to watch. `zone` = a planform zone (`HYD_PUMP`, `MLG_L`, `MLG_R`, `CHUTE`, …, see `aircraft.js`), `tone` ∈ `p1` `accent` `nmcm` `nmcs` `nmcd`. **Absent:** headline from the state ("Waiting for parts", "Flying normally" …), detail "n open jobs · n deferred", no zones |
| `now` | `{mc, of}` | req if no `kpi` | aircraft mission capable now |
| `kpis.d30` | `{mc, fmc, tnmcs}` shares 0–1 | req if no `kpi` | 30-day KPIs; `kpis.norm_mc` (0.75) opt |
| `triage.alert_rows` | int | req if no `kpi` | alert rows this season |
| `kpi` | object | opt | `{mc_now, of, mc30, fmc30, norm, parts30, due, freeze, alert_rows}` (percent numbers). **Absent:** built from `now`, `kpis`, `triage`, and `due`/`freeze` from `/api/epoch` |
| `focus` | text | opt | tail to highlight (`"TJ107"`) |

## `GET /api/board` → `PHX_DEC`

| Field | Type | | Meaning |
|---|---|---|---|
| `board[]` | list | req | ranked rows, top first (band, then rank) |
| `board[].id`, `.band`, `.tail`, `.code` | text | req | band ∈ `P1`…`P4` |
| `board[].label` | text | req | plain title: `"Hydraulic alarm that never clears"` |
| `board[].why` | text | req | one line: `"34 flights in a row · 28 pump removals found nothing"` |
| `board[].act_label` | text\|null | req | action pill: `"STOP R/R · TROUBLESHOOT"`; `null` → dashed "NO ORDER" |
| `board[].auth_shown` | `AGENT`\|`HUMAN`\|null | req | HUMAN when any order of the item needs a signature |
| `board[].order_state` | `proposed`\|`dropped`\|`monitor` | req | dropped/monitor rows are shown muted |
| `board[].tail_label` | text | opt | for groups: `"6 tails"` (default `tail`) |
| `board[].reason`, `.basis`, `.C`, `.U`, `.u_basis`, `.p` `{v, lo, hi}`, `.p_n`, `.rule`, `.row`, `.action`, `.mode` | | opt | triage detail (used by the decision card when the issue has no typed text) |
| `load` | `{alert_rows, issues, open, items, days}` | req | funnel: alert rows over `days` → issues → open → decisions |
| `focus` | text | opt | issue id highlighted on the board and opened by default |

## `GET /api/issues/{id}` → `PHX_ISSUE`

One shape serves `decision.html` (card) and `decision-why.html` (why / why not).

| Field | Type | | Meaning |
|---|---|---|---|
| `id`, `tail`, `code`, `band` | text | req | |
| `title` | text | req | page title `"TJ107 · hydraulic alarm HYD-101"` |
| `standing` | text | req | `"Standing for 34 flights"` (sub line) |
| `decision` | `{action, by, at, until?}`\|null | req | `action` ∈ `APPROVED` `MODIFIED` `REJECTED` `SNOOZED`; non-null hides the buttons and shows "Approved · SEO · 06:41" |
| `reco.headline`, `reco.text` | text | req | |
| `facts.state` / `.why` / `.forecast` | `{tier, big, unit, text, ci?}` | req | tier DESC / DIAG / PRED; `big` text (`"98.5"`), `unit` text (`"% no fault found"`) |
| `orders[]` | `{order_id, action, text, authority, mode, signed_by, parameters?}` | req | `[]` = no order; `parameters` prefill Modify |
| `orders[].prior`, `.issued`, `.status`, `.status_at` | bool, text, enum, text | opt | an order from an earlier epoch: shown as "Issued Mon 22 Jun 08:00 · Completed Mon 22 Jun 10:04" with a status pill (data-layer status QUEUED · IN_WORK · COMPLETED …) |
| `impact` | object\|null | req | `{horizon_days, pairs, d_mc: [mean, lo, hi] (points), source, rows: [{k, v, muted?}]}`; null = "no paired simulations" |
| `evidence` | `{cited, rows[], order_id}` | req | `cited` = total records cited; `rows` = latest few |
| `evidence.rows[]` | `{rid, t_occ, t_ingest, before_snapshot, sortie?, persistence?, mech?}` | req | `t_occ` "11 Jun 12:08"; `before_snapshot` = `t_ingest ≤` snapshot |
| `rule.steps[]` | `{h, p, hit, tag?}` | req | rule trace, in order |
| `rule.note` | text | opt | |
| `whynot[]` | `{alt, text, verdict}` | req | `[]` allowed |
| `donothing` | `{tail, horizon_days, status_quo, with_plan, pairs, note?}`\|null | req | MC % over the horizon, status quo vs plan |
| `workbench` | bool | opt | true when `/api/workbench/{id}` exists (enables the tab) |

## `GET /api/workbench/{issue_id}` → `PHX_WB`

| Field | Type | | Meaning |
|---|---|---|---|
| `issue_id`, `tail`, `code`, `title`, `sub` | text | req | |
| `manual` | text | opt | manual reference chip (`"PHX-FIM-HYD"`) |
| `t0` | ISO date | req | day 0 of the sortie offsets |
| `sorties[]` | `[day, fired 0/1, serial, "06 Jan"]` | req | one per sortie, in order; `serial` = serial fitted in the position under test |
| `removals[]` | `[day, serial_out, serial_in]` | opt | |
| `strip` | `{title, ci, note}` | req | text around the strip |
| `suspects[]` | `{id, name, text, p}` | req | posterior, sums to ≈ 1, ordered |
| `suspects_note`, `source` | text | opt | |
| `tests[]` | `{test_id, name, text, man_h, value 0–1, robust}` | req | ranked; `value` = information gain relative to the best; `robust` = `"best in 19 of 24"` |

## `GET /api/twin/{tail}?asof=` → `PHX_TWIN`

The **required** part is the tail state S1 serves today; everything else is optional and, when absent, built in
the page by `assets/twin-view.js` (tree from `installed`, evidence lens from `alarms`, strip from `sorties`).

| Field | Type | | Meaning |
|---|---|---|---|
| `tail`, `asof` (ISO), `snapshot_id`, `source`, `status`, `last_ingest` | | req | |
| `usage` | `{sorties, fh, landings, sorties_30d, fh_30d}` | req | any may be null |
| `installed[]` | `{position, serial, part_no, since, inferred}` | req | `position` = `"SYN-PN-HYDP#1"` |
| `alarms[]` | `{code, count, last_seen, consecutive_sorties, severity}` | req | |
| `sorties[]` | `{id, t, fh, landings, codes[]}` | req | |
| `systems[]` | `{id, name, open?, tone?, count?, items: [{node, label, serial, inferred?}]}` | opt | tree; `node` = 3D component id (`twin3d.js`: `HYD_PUMP`, `AMAGB`, `BHEEM_EU`, `ENGINE`, `MLG_L` …) or null |
| `selected` | node | opt | |
| `lens` | lens id | opt | default lens |
| `lenses[]` | list | opt | `{id, label, icon, source, model?, paint: {node: tone \| "#hex"}, dim?, arcs?: [{from, to, weight 0–1}], reporter?, tags?: [{node, kind rep\|sus\|sus2, k, v, s, dx?, dy?}], legend: [{kind dot\|bar\|line\|text, color?, text}]}`. Ids used: `status`, `evidence`, `false_alarm`, `life`, `removal_risk`, `engine_margin`. **`source` is shown on the viewport and is required for every lens**; a lens with no output yet keeps its source and says so in `legend` |
| `panels` | `{node: panel}` | opt | component panel: `{title, serial, inferred, note, tiers[], status: {pill, kv[]}, assessment?: {scope, bar: [{n, tone, label}], confirmed, kv[], verdict?: [{label, value, on?}]}, projection?: {kv[]}, recommended?: {basis, items: [{action, authority, label, icon?, note?}]}, foot[]}`; `kv` rows are `{k, v, code?, ci?, num?}` |
| `insight` | `{label, title, text, swaps: [bool]}` | opt | the floating finding card |
| `strip` | `{t0, T, state: [[day, state]], sorties: [[day, fired]], removals: [[day, serial]], marks: [{day, label}], asof_label, labels: {sorties, removals}}`\|null | opt | as-of scrubber |
| `foot[]` | text | opt | provenance lines under the panel |

## `GET /api/serial/{tail}/{serial}`

| Field | Type | | |
|---|---|---|---|
| `tail`, `serial`, `part_no`, `asof` | | req | |
| `history[]` | `{installed, removed, job_no, finding, tail?, position?}` | req | `removed: null` = still fitted |
| `klass` | text | opt | |
| `beliefs[]` | `{name, value\|null, lo, hi, n, model_id, model_version, source, note}` | opt | `interfaces.Belief`; null value shown as `note` or INSUFFICIENT_EVIDENCE |

## `GET /api/search?q=`

`{q, results: [{kind: tail|serial|code|job, id, tail, label, sub?, issue_id?}]}` — `issue_id` (opt) lets a code
or job hit open its decision; a serial hit opens the lineage drawer; a tail hit opens its twin.

## `GET /api/provenance/{order_id}` → `PHX_PROV`

| Field | Type | | Meaning |
|---|---|---|---|
| `order_id`, `snapshot` (hex), `policy_version` | text | req | |
| `chain[]` | list | req | LEL events from release to outcome, oldest first |
| `chain[].event_id` (`"lel:0007"`), `.type`, `.t_valid` (ISO), `.actor` (`HUMAN:SEO`, `AGENT:…`), `.causation_id`, `.prev_hash`, `.hash` | | req | |
| `chain[].title`, `chain[].text` | text | req | row title and one line (`text` may hold a `<span class="rid2">` id) |
| `chain[].refs`, `.payload` | object | opt | `POLICY_EVALUATED.refs.trace_hash` is shown on the replay card |
| `chain[].scheduled` | bool | opt | not yet happened (before 08:00) |
| `replay[]` | `{seed, snapshot_equal, order_equal, trace_equal, policy_equal}` | req | |
| `verified` | bool | opt | head chip; default true only after Verify passes |
| `standards[]` | `{std, text, events}` | opt | assurance mapping card |

---

## POST endpoints

| Call | Body | 200 response the page uses |
|---|---|---|
| `POST /api/issues/{id}/decision` | `{action: approve\|modify\|reject\|snooze, by, params?, reason?, until?}` | `{decision: {action, by, at, until?}}` |
| `POST /api/orders/{order_id}/sign` | `{by}` | `{order_id, signed_by}` (page reloads the epoch) |
| `POST /api/workbench/{issue_id}/draft` | `{test_id}` | `{order_id}` |
| `POST /api/epoch/advance` | `{}` | any; page reloads |
| `POST /api/epoch/autoplay` | `{n}` | any; page reloads |
| `POST /api/provenance/verify` | `{order_id}` | `{ok, events, head, first_bad?}` |
| `POST /api/provenance/replay` | `{order_id}` | `{order_id, replay: [...]}` (same items as `PHX_PROV.replay`) |

`by` defaults to `SEO` (decisions) and `ENGG-OFFICER` (signatures); `?by=` / `?signer=` override it.

## `GET /api/policies?issue=` and `GET /api/assurance`

Read by `policies.html` and `assurance.html` as served by S1 (fields listed in S1's API; the pages tolerate missing
optional blocks). Assurance Backtests also reads, when present, `hazard.backtest.champion {model_id, model_version}`
and `hazard.backtest.candidates[] {name, brier, auc, c_index, promoted}` (shown as a held-out comparison table).

