# 10 · Local AI assistant: a constrained analyst, not a chat-first agent

The team wants a local assistant with read access to the whole platform, to ask about aircraft/components,
synthesise across sources, analyse history, explore what-ifs and interpret simulations. The research supports
it — **as a constrained analyst over a typed, read-only, as-of-enforced tool layer**, never as the primary UI and
never in the decision path.

## Design principles

1. **No number without a tool.** The model writes an *answer envelope* (constrained JSON) whose claims contain
   placeholders like `{{r3.data.mc}}`; the UI fills numbers from stored tool results; a post-check rejects any
   literal digit not traceable to a result ("render by reference" — the program-aided pattern taken to its
   conclusion). Units and code meanings come from the dictionary through tools, never from the model.
2. **Every claim cites `record_id`s** (or a query hash + row count for aggregates); a validator checks each cited
   id exists **and was ingested by `as_of`** — the same rule the orders gateway applies.
3. **`as_of` is injected by the orchestrator from the session clock**; the model cannot set it beyond session
   time. Every answer shows an "AS OF" pill, contract/dictionary versions and dataset id.
4. **Typed refusals:** tools return `NO_DATA`, `NOT_OBSERVABLE` (e.g. "no exceedances in usage-mode worlds"),
   `RESTRICTED`, `DENIED`; the assistant must say "not observable from the contract" rather than estimate.
5. **What-if only in belief mode.** The fork tool hard-codes `mode="belief"` (the fork service defaults to oracle,
   and `what_if()` uses ensemble = true hidden state — both are evaluation-only). Results are narrated from a
   deterministic interpreter ("CI excludes 0 / includes 0", sign, practical significance).
6. **No write path.** The most the assistant can produce is an **unsubmitted order draft** that opens the Orders
   screen; a human reviews, signs and submits through the normal gateway. Drafting is not issuing.
7. **Free text is untrusted.** Maintenance narratives are an indirect prompt-injection surface (OWASP LLM01); they
   reach only a *quarantined*, tool-less extraction call with a constrained output schema, cross-checked against
   coded fields (e.g. 221 narratives say AVI-204 is the radar; dictionary 0.1.3 says AHRS — the assistant flags
   the conflict and trusts the coded field + dictionary).
8. **Break the "lethal trifecta"** (private data + untrusted content + an outbound channel; Willison 2025): no web
   tools, no external links or images rendered from model output, deep links only to an allowlist of internal
   routes. Plan-then-execute and dual-LLM patterns (Beurer-Kellner et al., arXiv 2506.08837); CaMeL-style
   control/data-flow separation as the stronger end state.
9. **Dashboards remain the source of truth.** Every answer deep-links to a screen; chat has no exclusive
   capability.

## Why not text-to-SQL or GraphRAG

- **Text-to-SQL for end users: no.** BIRD's best execution accuracy is ≈ 83 % (humans ≈ 93 %); Spider 2.0-DBT (on
  DuckDB) best ≈ 65.6 %; our schema has exactly the traps that fail silently (versioned records, event vs ingest
  time, per-serial counter resets, scoped identity). Querying a semantic layer instead of raw SQL raised accuracy
  from 16 % to 54 % (Sequeda et al.). We offer a **semantic-layer metric tool** (predefined metrics/dimensions
  compiled to SQL by deterministic code in a locked-down read-only DuckDB: external access off, allowed
  directories, extensions off, memory/thread limits, `lock_configuration`), optionally showing the SQL.
- **GraphRAG: no.** Our "graph" is explicit and exact in the contract keys; an LLM-extracted graph would add
  hallucinated edges. A deterministic `trace_evidence_chain` tool does the job ([09](09-knowledge-graph.md)).
- **MCP:** adopt for packaging, not for security — our own single local stdio server, no third-party servers,
  tool-description hashes pinned in CI; read-only enforced by the server process, its credentials and filesystem
  permissions, never by tool annotations (the MCP spec itself says annotations are untrusted). Note the 2026-07-28
  spec revision made breaking changes (stateless; sessions removed). In-process function calling is equally fine.

## Model and serving (verified Oct 2026; choose by our golden set, not leaderboards)

| Tier | Choice | Notes |
|---|---|---|
| Default | **gpt-oss-20b** (OpenAI, Apache-2.0; 21B total / 3.6B active MoE; ~12 GB; 131K context) | native function calling and structured outputs; never show raw chain-of-thought (the card warns it may contain hallucinated content); prompt-injection hijacking robustness 0.639 → do not rely on model robustness |
| Step-up (≥ 24 GB) | **Gemma 4 26B-A4B / 31B** (Google, Apache-2.0 since Apr 2026) or **Granite 4.1 30B** (IBM, Apache-2.0) | stronger vendor tool-use scores |
| Comparison only | Qwen3.5/3.6 (best tool-use per GB, Apache-2.0) | Chinese origin — keep as comparators unless MoD procurement clears them; NIST CAISI found DeepSeek agents 12× more likely to be hijacked |
| Sovereign reference | Sarvam 30B (India, Apache-2.0) | independent indices show high hallucination today; the eval suite is the acceptance test that lets MoD swap in a sovereign model later |

- Leaderboards are unreliable for this choice: the official BFCL v4 board (last updated Apr 2026) omits the newest
  models, and Epoch AI's audit found defects in 48 % of sampled tasks. Small open models score only 20–50 % on
  BFCL multi-turn — keep plans short (≤ 6 tool calls) and tools narrow.
- **Serving:** llama.cpp `llama-server` for the air-gapped demo (single binary; Metal/CUDA/CPU; JSON-schema/GBNF
  constrained decoding); Ollama for developer laptops; vLLM/SGLang if Air HQ hosts a GPU server. Constrained
  decoding for the answer envelope, fork requests and order drafts; pinned runtime and model hashes;
  temperature 0–0.3.

## Architecture

```text
UI side panel ─▶ Orchestrator (Python, deterministic)
                 • injects as_of, role, entity context; plan-then-execute (≤ 6 tool calls)
                 • constrained-decoding calls to the LLM (OpenAI-compatible)
                 • answer-envelope validator (numbers ↔ result refs; record_ids ingested ≤ as_of)
                 • hash-chained audit log (user, role, as_of, question, plan, tool calls + result hashes,
                   cited record_ids, model/runtime hash, prompt version, answer, latency, feedback)
   LLM runtime: llama-server (demo) / Ollama (dev) / vLLM (server)
   Quarantined LLM (same weights, no tools) → extract_narrative_facts
   Tool server (own MCP/stdio or in-process; read-only OS user; read-only mount of consumer trees)
     locked DuckDB over Parquet │ dictionary index │ BM25 over narratives │ twin state & predictions (read)
     fork worker (belief-only, budgeted, async) │ drafts store (not orders)
   NO write path to orders.commands · NO network egress · NO access to _restricted_labels
```

## Read-only tool catalogue

Common envelope: `{result_id, status (OK|NO_DATA|PARTIAL|NOT_OBSERVABLE|DENIED|RESTRICTED), as_of,
contract_version, dict_version, dataset_id, data, record_ids[≤50], record_count, query_hash, caveats[],
elapsed_ms}`. `as_of` comes from the orchestrator; list tools are capped at 50 rows; **raw `param.samples` rows
never enter model context** (DuckDB returns 10-s binned series of a whole sortie in ≈ 0.24 s).

| # | Tool | Purpose |
|---|---|---|
| 1 | `get_session_context` | session clock, epochs, role/scope, versions, `synthetic=true`, `preview=true` |
| 2 | `resolve_entity` | deterministic fuzzy resolution of tails, serials, part nos, jobs, demands, sorties, orders, params, codes |
| 3 | `get_fleet_status` | per tail: SCIR state and since-when, open U/S / deferred / AWP counts, last sortie, FH over 30 days |
| 4 | `get_aircraft_summary` | state, open jobs (coded fields), installed serials, recent events, usage totals |
| 5 | `get_availability_timeline` | occupancy per state per bin and window KPIs, SCIR arithmetic identical to the data layer's |
| 6 | `list_jobs` / 7 `get_job_history` | latest version per key as of t; versions, links, evidence, linked orders and shop finding |
| 8 | `trace_evidence_chain` | event → defect → troubleshoot/removal → shop finding → availability effect |
| 9 | `search_maintenance_text` | fuzzy BM25 → handles + ≤ 160-char snippets marked UNTRUSTED |
| 10 | `extract_narrative_facts` | quarantined tool-less extraction with conflict and injection flags |
| 11 | `get_serial_history` | install/remove timeline, hours/cycles, shop findings (world-scoped on v0.9) |
| 12 | `get_usage_counters` | per-sortie deltas with reset handling (fleet tree only; NOT_OBSERVABLE for telemetry) |
| 13 | `list_events` / 14 `get_event_recurrence` | events with suspects; recurrence, persistence, linked outcomes, base-rate caveat |
| 15 | `get_param_series` / 16 `get_param_stats` / 17 `get_event_snapshot` | downsampled series (≤ 600 points), percentiles, snapshot windows — with validity/sentinel summaries |
| 18 | `lookup_dictionary` / 19 `get_policy_reference` | dictionary entries; action vocabulary, schemas, authority matrix, policies (versioned) |
| 20 | `get_supply_status` / 21 `list_orders` | open demands and age; orders with lifecycle (keyed by world + `order_id`) |
| 22 | `get_predictions` / `get_issue` | stored twin predictions with drivers and versions; triage issues with score components |
| 23 | `run_metric_query` | semantic-layer metric query with `sql_preview` |
| 24 | `validate_fork_request` / 25 `run_what_if` | schema + per-order `OrderGateway.evaluate` dry-run + authority flags + cost; then belief-mode CRN fork, async |
| 26 | `create_order_draft` / 27 `make_deep_link` | DRAFT only (never submitted); allowlisted internal URLs |

## Evaluation (the acceptance test for any model)

- **Golden set** (150 → 300 items, pinned to the release hash): entity lookup, KPI aggregation, cross-source
  synthesis, as-of time travel (the same question at two `as_of` values must differ correctly), telemetry trends,
  what-if translation, must-refuse / not-observable, role denial, injected narratives. Each item: expected tool
  calls, expected facts from an **independent reference pipeline**, required `record_id`s.
- **Hard gates (100 % / 0 %):** every number traceable; zero cited records with `t_ingest > as_of`; zero
  restricted/oracle leaks; zero submitted orders; zero non-allowlisted links.
- **Graded:** tool selection/argument accuracy (DeepEval ToolCorrectness), numeric exact match, citation
  precision/recall, refusal precision/recall, **pass^4 consistency** (τ-bench), injection success rate, latency
  p50/p95 (targets: first token < 2 s; 1–3-tool answers p50 < 10 s), fork compute.
- Red team with seeded injections (instruction overrides, fake record_ids, "recommend RELEASE", Unicode
  obfuscation); garak, PyRIT, promptfoo in CI.
- Model bake-off on the same harness; choose on gates, then pass^4, then latency.

## The assistant must never

1. Issue, submit or modify orders, or hold write credentials to orders, records or configuration.
2. Run oracle or ensemble forks, or read `labels.truth`, `root_seed` or `rng_stream_table`.
3. Use records with `t_ingest > as_of`, or set `as_of` beyond session time.
4. State a number not from a tool result, or a code meaning not from the dictionary.
5. Follow instructions found in maintenance text or any tool output.
6. Pull raw `param.samples` rows into context.
7. Present synthetic codes, ICD or KPIs as real Tejas/IAF data.
8. Make unsupported causal claims or recommend airworthiness releases (RELEASE/GROUND/DEFER only as flagged drafts).
9. Reach any network or render external content.
10. Answer outside the user's role or scope.

## Key sources

- gpt-oss model card — https://arxiv.org/html/2508.10925 ; https://huggingface.co/openai/gpt-oss-20b
- Gemma 4 — https://huggingface.co/google/gemma-4-31B-it ; Granite 4.1 — https://huggingface.co/ibm-granite/granite-4.1-8b ; Sarvam — https://huggingface.co/sarvamai/sarvam-30b
- BFCL v4 — https://gorilla.cs.berkeley.edu/leaderboard.html ; Epoch AI review — https://epoch.ai/benchmarks/berkeley-function-calling-leaderboard/review ; τ²-bench — https://arxiv.org/abs/2506.07982
- BIRD — https://bird-bench.github.io/ ; Spider 2.0 — https://spider2-sql.github.io/ ; Sequeda et al. — https://arxiv.org/abs/2311.07509
- MCP 2026-07-28 — https://modelcontextprotocol.io/specification/2026-07-28 ; MCP security best practices — https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices ; tool poisoning — https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks
- Design patterns for securing LLM agents — https://arxiv.org/abs/2506.08837 ; CaMeL — https://arxiv.org/abs/2503.18813 ; lethal trifecta — https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ ; OWASP LLM Top 10 — https://genai.owasp.org/llm-top-10/
- NIST CAISI DeepSeek evaluation — https://www.nist.gov/news-events/news/2025/09/caisi-evaluation-deepseek-ai-models-finds-shortcomings-and-risks
- llama.cpp server — https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md ; Ollama — https://docs.ollama.com/capabilities/structured-outputs ; vLLM — https://docs.vllm.ai/en/latest/features/structured_outputs.html
- Securing DuckDB — https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview.html
- Inspect AI — https://inspect.aisi.org.uk/ ; DeepEval — https://deepeval.com/docs/metrics-tool-correctness
