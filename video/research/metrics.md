# Phalanx Twin — demo-video metrics fact sheet

Compiled 2026-10-16 for the product demo video. Every number we put on screen must come from this file or
from our own logged measurement.

**Status tags:** **M** = measured by the cited source (third-party hardware, not ours) · **V** = vendor or
spec-sheet claim · **D** = derived by us (the arithmetic is shown) · **A** = assumption (a design budget, not
a measurement). None of the hardware figures were measured by us. We have no gpt-oss weights or GPU here, and
nothing was installed or downloaded. Before the final cut, re-run `llama-bench` and log our own numbers on the
demo box, then replace **M**/**D** with our own **M**.

**Honesty rules for the video:** the fleet is simulated and the KPIs come from synthetic, unvalidated
data-layer v0.9. Never present them as real IAF or Tejas figures. Section 3 contains public reference
ranges for sanity checks only.

---

## 0. On-screen cheat sheet: recommended station-server profile

**Station server = one NVIDIA GB10 ("DGX Spark-class") box**, 128 GB unified memory. Choose either the NVIDIA
DGX Spark itself or an OEM GB10 system from Acer, ASUS, Dell, GIGABYTE, HP, Lenovo or MSI. The box runs
gpt-oss-20b (MXFP4 GGUF) on llama.cpp `llama-server` with a 16K context and one user at a time.

| On-screen label | Value to show | Tag | Basis (details in §1) |
|---|---|---|---|
| Model | gpt-oss-20b · 21 B params (3.6 B active) · MXFP4 · Apache-2.0 | V | OpenAI model card |
| Model on disk | **12.1 GB** (11.28 GiB) | M | HF file size `gpt-oss-20b-MXFP4.gguf` = 12,109,566,624 B |
| KV cache @ 16K context | **≈ 0.46 GB** (438 MiB, F16) | D | 12 full-attention layers × 16,384 × 2 KiB + 12 SWA layers × 2,304 cells × 2 KiB |
| Memory resident (weights + KV + compute buffers) | **≈ 15 GB of 128 GB** | D | 12.1 GB + 0.46 GB + 2.7 GB (llama.cpp guide compute buffers) |
| Prefill speed | **≈ 4,500 tokens/s** (pp2048) | M | llama.cpp `benches/dgx-spark`, build 7941, 2026-02-05: 4,505.82 t/s |
| Decode speed | **≈ 83 tokens/s** at empty context · **≈ 70 tokens/s at 16K** | M | same: tg32 83.43; tg32 @ d16384 70.36 |
| Time to first token, 5K-token prompt | **≈ 1.1 s** | D | measured 4,096-token prefill 0.907 s + 904 tok ÷ 4,158 t/s + 1 decode step |
| 3-tool answer, end to end | **≈ 9–12 s** (base case 11.7 s) | D+A | token budget in §1.9; decode is ~73 % of the time |
| Power while answering | **≈ 60–90 W** (240 W max PSU) | M | ServeTheHome review, 2025-10-14 ("60-90W" in LLM inference) |
| Concurrent users | 4 users ≈ **36 tok/s each**; 8 users ≈ **29 tok/s each** (4K prompts) | M+D | `benches/dgx-spark` llama-batched-bench, B=4: 144.11 t/s; B=8: 233.11 t/s |
| Degraded mode (no GPU, CPU-only) | 5K-prompt first token **≈ 37 s** · decode **≈ 27 tok/s** · 3-tool answer **≈ 80 s** | M+D | Ryzen 9 9950X CPU-only (OpenBenchmarking, 2025-09-08) |

Suggested caption wording: *"gpt-oss-20b, local and air-gapped · 12 GB on disk, ≈ 15 GB in memory · first
token ≈ 1 s · ≈ 70–80 tokens/s · ≈ 60–90 W"*. Add a small footnote: *"Third-party llama.cpp benchmarks on GB10;
re-measured on our demo unit before release"*. Once we re-measure, the footnote becomes *"measured on our
unit"*.

Do not put these on screen: "real-time", "instant", the raw tokens/s of a different card than the one shown,
and any number for RTX 4000 Ada, RTX A4000/A5000, L4 or base M4 (no measured data exists, see §1.10).

---

## 1. Local LLM runtime: gpt-oss-20b on llama.cpp

### 1.1 Model facts

| Item | Value | Tag | Source (date) |
|---|---|---|---|
| Total / active params | 20.91 B total, 3.61 B active per token; 24 layers; 32 experts, top-4 | V | gpt-oss model card, Table 1 — https://arxiv.org/html/2508.10925 (card dated 2025-08-05; arXiv v1 2025-08-08) |
| Context | 131,072 tokens (YaRN ×32 over a 4,096 base) | V | same; `config.json` `max_position_embeddings`, `rope_scaling` — https://huggingface.co/openai/gpt-oss-20b/blob/main/config.json |
| Memory claim | "run on systems with as little as 16GB memory" | V | model card §2.1 |
| Attention config | 64 query heads, **8 KV heads**, head_dim **64**; layers alternate `sliding_attention` (window **128**) / `full_attention` → **12 full + 12 SWA** | V | `config.json` (`num_key_value_heads`, `head_dim`, `sliding_window`, `layer_types`) |
| Checkpoint (original, safetensors) | 12.8 GiB | V | model card Table 1 |
| GGUF used by llama.cpp | `ggml-org/gpt-oss-20b-GGUF/gpt-oss-20b-MXFP4.gguf` = **12,109,566,624 B = 12.11 GB = 11.28 GiB**; llama-bench prints "11.27 GiB, 20.91 B" | M | HF API tree listing (read 2026-10-16) — https://huggingface.co/ggml-org/gpt-oss-20b-GGUF |
| Other quants | Q4_K_M 11.62 GB, Q8_0 12.11 GB, F16 13.79 GB. Expert tensors stay MXFP4 in every variant, so "smaller quants" barely shrink the file | M | https://huggingface.co/unsloth/gpt-oss-20b-GGUF (API listing 2026-10-16) |
| Reasoning length | low / medium / high effort; on AIME at high effort, gpt-oss-20b averages > 20k CoT tokens per problem. **We must run low effort with a reasoning budget.** | V | model card §2.5.2 / §2.6.1 |
| llama-server levers | `--reasoning-effort`, `--reasoning-budget N`, prompt cache on by default, `--ctx-checkpoints` (default 32, needed for SWA cache reuse), `json_schema` / `response_format` grammar sampling, OpenAI-style tools with `--jinja` | V | https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md (master as of 2026-10-15) |

### 1.2 KV cache for ~16K context (derived)

llama.cpp keeps a full-length cache only for the 12 full-attention layers. The 12 SWA layers get
`GGML_PAD(min(ctx, n_swa·n_seq + n_ubatch), 256)` cells; see `src/llama-kv-cache-iswa.cpp`, line 73
(https://github.com/ggml-org/llama.cpp/blob/master/src/llama-kv-cache-iswa.cpp, master 2026-10-15).

- Per token per layer (F16): K+V = 2 × 8 KV heads × 64 dims × 2 bytes = **2,048 B**.
- Full layers at 16,384 ctx: 12 × 16,384 × 2,048 B = 402,653,184 B = **384 MiB**.
- SWA layers (n_ubatch 2048): cells = pad(128 + 2048, 256) = 2,304. Then 12 × 2,304 × 2,048 B = **54 MiB**.
- **Total ≈ 438 MiB ≈ 0.43 GiB ≈ 0.46 GB.** At 32K: 822 MiB. At 131K: 3.05 GiB. With `--swa-full`, 16K
  needs 768 MiB. Four parallel 16K slots sharing a unified KV pool (64K) need ≈ 1.56 GiB.
- Cross-check: the llama.cpp guide lists "KV cache per 8 192 tokens: 0.2 GB". Our full-layer figure at 8K is
  192 MiB = 0.20 GB, so the two agree.

### 1.3 Memory resident

| Context | Model data | Compute buffers | KV | Total | Tag | Source |
|---|---|---|---|---|---|---|
| 8,192 | 12.0 GB | 2.7 GB | 0.2 GB | **14.9 GB** | M (guide table) | llama.cpp gpt-oss guide, "Minimum requirements" — https://github.com/ggml-org/llama.cpp/discussions/15396 (2025-08-18, live doc) |
| 32,768 | 12.0 | 2.7 | 0.8 | **15.5 GB** | M | same |
| 131,072 | 12.0 | 2.7 | 3.2 | **17.9 GB** | M | same |
| **16,384 (ours)** | 12.1 | 2.7 | 0.46 | **≈ 15.3 GB (≈ 14.2 GiB)** | D | file size + guide buffers + §1.2 |

The guide also states that 16 GB NVIDIA cards fit the 20B fully on the GPU with a 32K context cap. 16 GB Macs
need `--n-cpu-moe 12 -c 32768 --no-mmap`. Apple recommends keeping usage under ~70 % of unified memory.

### 1.4 Measured `llama-bench`: gpt-oss-20b MXFP4, flash-attention on

All runs use `ggml-org/gpt-oss-20b-GGUF` (11.27 GiB, 20.91 B params), batch/ubatch 2048 unless stated.
"pp" = prompt processing (prefill), "tg" = token generation (decode), "@ dN" = after N tokens already in
context.

#### (b) NVIDIA DGX Spark / GB10, the recommended profile

| Test | t/s | Tag | Config / build | Source (date) |
|---|---|---|---|---|
| pp512 (batched-bench, B=1) | 1,895.57 (0.270 s for 512 tok) | M | DGX Spark, CUDA 13.0, driver 580.95.05, `-fa 1 -ub 2048 --no-mmap` | https://github.com/ggml-org/llama.cpp/blob/master/benches/dgx-spark/dgx-spark.md (commit 3795cc1e8, 2026-02-05) |
| pp4096 (batched-bench, B=1) | 4,513.91 (**0.907 s** for 4,096 tok) | M | same | same |
| pp2048 | **4,505.82 ± 12.90** | M | llama-bench `-fa 1 -d 0,4096,8192,16384,32768 -p 2048 -n 32 -ub 2048 -mmp 0`, build 11fb327bf (7941) | same |
| tg32 | **83.43 ± 0.59** | M | same | same |
| pp2048 @ d4096 / tg32 @ d4096 | 4,158.34 / 79.22 | M | same | same |
| pp2048 @ d8192 / tg32 @ d8192 | 3,993.81 / 75.22 | M | same | same |
| pp2048 @ d16384 / tg32 @ d16384 | **3,449.98 / 70.36** | M | same | same |
| pp2048 @ d32768 / tg32 @ d32768 | 2,689.42 / 61.65 | M | same | same |
| Cross-check (ASUS Ascent GX10, same GB10) | pp2048 3,729.54; pp8192 3,664.00; pp16384 3,469.56; pp32768 3,065.79; tg128 **84.18** | M | `-t 1 -fa 1 -b 2048 -ub 2048` | https://github.com/ggml-org/llama.cpp/discussions/15396#discussioncomment-15079003 (2025-11-25) |
| Runtime sensitivity: Ollama on DGX Spark | prefill 2,053, decode **49.7** (batch 1) | M | Ollama, MXFP4 | LMSYS, https://www.lmsys.org/blog/2025-10-13-nvidia-dgx-spark (2025-10-13) |
| Early llama.cpp on DGX Spark | decode ≈ 57 t/s (reported via comment) | M (secondary) | The Register review | https://www.theregister.com/2025/10/14/dgx_spark_review/ via https://github.com/ggml-org/llama.cpp/discussions/15396#discussioncomment-14723402 (2025-10-19) |

The figures depend on the build and runtime: Ollama and Oct-2025 builds are 30–40 % slower on decode. Quote
the Feb-2026 llama.cpp numbers only together with "llama.cpp, 2026 build". Pin our build and re-measure it.

#### (a) Single NVIDIA workstation / desktop GPU

| GPU (VRAM, board power) | pp2048 | pp8192 | pp16384 | pp32768 | tg128 | Tag | Build / source (date) |
|---|---|---|---|---|---|---|---|
| RTX 4090 (24 GB) | 8,022.33 | 7,264.73 | 6,298.35 | 5,112.35 | 221.95 | M | build 6210; guide body, https://github.com/ggml-org/llama.cpp/discussions/15396 (Aug 2025) |
| RTX 4090 (24 GB), newer build | 10,365.85 | 10,480.32 | 9,883.74 | 8,516.20 | **254.63** | M | build 8244; https://github.com/ggml-org/llama.cpp/discussions/15396#discussioncomment-16063223 (2026-03-10) |
| RTX 5090 (32 GB) | 9,848.38 | 8,834.14 | 7,802.21 | 6,290.76 | 282.51 | M | build 6210; guide body (Aug 2025) |
| RTX 4080 SUPER (16 GB) | 8,170.95 | 7,989.22 | 7,517.93 | 6,739.51 | 186.51 | M | build 6316; guide body |
| RTX 5060 Ti (16 GB) | 3,839.21 | 3,695.85 | 3,472.60 | 3,078.06 | 111.51 | M | build 6208; guide body |
| RTX 3090 (24 GB) | 5,170.56 | 4,771.74 | 4,289.11 | 3,577.10 | 161.77 | M | build 6210; guide body |
| Tesla V100 (16 GB) | 3,526.65 | 3,320.62 | 2,768.99 | 2,096.44 | 117.71 | M | build 6129; guide body |
| **RTX 2000 Ada (16 GB, 70 W max, ECC)** | 2,625.97 | 2,443.16 | 2,230.95 | 1,876.70 | **70.46** | M | `-fa 1 -b 4096 -ub 4096`, VM with PCIe passthrough; https://github.com/ggml-org/llama.cpp/discussions/15396#discussioncomment-14771850 (2025-10-24); 70 W and ECC: https://www.nvidia.com/en-us/products/workstations/rtx-2000/ |
| RTX PRO 6000 Blackwell Max-Q (96 GB, 300 W) | 9,480.55 | 8,921.62 | 8,196.12 | 7,050.35 | 249.96 | M | build 6199; guide body |
| RTX PRO 6000 Blackwell WS (96 GB, 600 W) | 11,521.95 | 10,673.03 | 9,772.06 | 8,267.46 | 286.91 | M | build 6205; https://github.com/ggml-org/llama.cpp/discussions/15396#discussioncomment-14153871 (2025-08-19) |

Measured power on workstation cards (nvtop, GPU only): the RTX PRO 6000 WS drew "around 390W out of the
maximum 600W" (same comment). The Max-Q drew "~250W during pp, and ~280W during tg"
(https://github.com/ggml-org/llama.cpp/discussions/15396#discussioncomment-14155177, 2025-08-19).

**No measured gpt-oss-20b llama-bench result was found** for the RTX 4000 Ada (20 GB), RTX A4000, RTX A5000,
RTX PRO 4000 Blackwell or L4 as of 2026-10-16. Only fit-calculator estimates exist, and we do not use them.
For relative scale only, the llama.cpp CUDA scoreboard (Llama-2-7B Q4_0, tg128) lists these decode rates:
RTX 4090 186.21, RTX PRO 4000 Blackwell 131.66, RTX A5000 130.07, RTX A4000 83.77, "RTX A4000 Ada" (20 GB /
160-bit, i.e. RTX 4000 Ada) 61.83, RTX 2000 Ada 50.62
(https://github.com/ggml-org/llama.cpp/discussions/15013, scoreboard updated through 2026-10-01). That
scoreboard suggests an RTX 4000 Ada would decode gpt-oss-20b at roughly the RTX 2000 Ada's speed or a little
faster. Treat that as **D**, not for screen.

#### (c) Apple Silicon (Metal)

| Machine | pp2048 | pp8192 | pp16384 | pp32768 | tg128 | Tag | Source (date) |
|---|---|---|---|---|---|---|---|
| M4 Max (36 GB) | 1,277.42 | 1,030.28 | 779.44 | 568.13 | 92.36 (95.88 when run alone, build 6293) | M | guide body, build 6123 (Aug 2025); tg-alone: https://github.com/ggml-org/llama.cpp/discussions/15396#discussioncomment-14225207 (2025-08-26) |
| Mac mini M4 Pro (64 GB) | 700.78 | 618.59 | 534.95 | 419.74 | **63.34** | M | build 6280; https://github.com/ggml-org/llama.cpp/discussions/15396#discussioncomment-14226807 (2025-08-26) |
| M4 Pro, **CPU-only** (`-ngl 0`, 6 threads) | pp256 76.57 | – | – | – | tg64 55.66 | M | https://github.com/ggml-org/llama.cpp/pull/16833 (2025-10-29) |
| M4 base (16–32 GB) | — | — | — | — | — | none | No measured llama-bench found. 16 GB needs `--n-cpu-moe 12`. A third-party oMLX run on M4/32 GB reported ~23 t/s decode, but it is not llama.cpp, so we do not use it. |
| M2 Ultra (192 GB), depth sweep | pp2048 2,713.40; @d16384 1,556.54 | – | – | @d32768 1,122.63 | tg32 129.97; @d16384 109.75; @d32768 98.25 | M | https://github.com/ggml-org/llama.cpp/blob/master/benches/mac-m2-ultra/mac-m2-ultra.md (build 7948, 2026-02-05) |

MacBook Pros throttle under sustained load. The maintainer attributes low M3 Max tg numbers to heat
throttling (comment -14225207). Use a desktop Mac for any Apple-based demo.

### 1.5 Decode speed vs. context depth

| Platform | tg @ 0 | @ 4K | @ 8K | @ 16K | @ 32K | Drop 0→16K | Tag / source |
|---|---|---|---|---|---|---|---|
| DGX Spark (GB10) | 83.43 | 79.22 | 75.22 | **70.36** | 61.65 | −15.7 % | M — benches/dgx-spark (2026-02-05) |
| M2 Ultra | 129.97 | 123.38 | 117.39 | 109.75 | 98.25 | −15.6 % | M — benches/mac-m2-ultra (2026-02-05) |
| M4 Max 36 GB (batched-bench, after a PP-token prompt, tg128) | 94.17 | 88.30 (@2K) | 82.47 | 76.67 | 64.76 | −18.6 % | M — guide body (build 6123) |
| M1 Pro 32 GB | 45.62 | 41.61 (@2K) | 38.45 | 33.86 | – | −25.8 % | M — guide body |

Rule of thumb from these measurements (**D**): decode falls about 15–19 % by 16K on current chips (26 % on the older M1 Pro) and about 24–31 % by 32K.
Prefill also slows with depth (Spark: 4,506 → 3,450 t/s at 16K).

### 1.6 Concurrency (several officers at once) on DGX Spark

`llama-batched-bench -fa 1 -c 300000 -ub 2048 -npp 4096,8192 -ntg 32 -npl 1..32` (benches/dgx-spark,
2026-02-05), PP = 4,096:

| Parallel requests | Total decode t/s | Per-user decode t/s (**D** = total ÷ B) |
|---|---|---|
| 1 | 78.54 | 78.5 |
| 2 | 102.37 | 51.2 |
| 4 | 144.11 | **36.0** |
| 8 | 233.11 | 29.1 |

If 8 officers submit 4K-token questions at the same instant, prefill for all eight finishes after 7.2 s (T_PP 7.184 s at B = 8). Expect the worst-case first token under that burst to be ≈ 7 s (**D**).

### 1.7 Load time

- The 120B (59 GiB) on DGX Spark with `--no-mmap` loads in 22 s cold on kernel 6.17 and 15 s with NVMe
  read-ahead 8192 KB. With mmap it takes ~1.5 min. Source: **M**,
  https://github.com/ggml-org/llama.cpp/discussions/16578#discussioncomment-14853641 (2025-11-03) and
  -15042534 (2025-11-21). On kernel 6.14, 27 s (-15016441, 2025-11-19).
- **20B (11.3 GiB) on Spark ≈ 3–5 s cold with `--no-mmap`** (**D**: 11.28/59.02 × 15–22 s = 2.9–4.2 s, plus
  warm-up). Always launch with `--no-mmap` on GB10.

### 1.8 Power

| Item | Value | Tag | Source (date) |
|---|---|---|---|
| DGX Spark power supply / system peak | 240 W external PSU; "peak total system power is 240W" | V | https://docs.nvidia.com/dgx/dgx-spark/hardware.html ; NVIDIA forum "DGX Spark Power Clarification" https://forums.developer.nvidia.com/t/dgx-spark-power-clarification/349668 (2025-10-31) |
| GB10 SoC TDP (CPU+GPU) | 140 W; 100 W reserved for the rest of the system | V | same |
| Idle | 40–45 W (pre-production unit) | M | ServeTheHome, P. Kennedy, https://servethehome.com/nvidia-dgx-spark-review-the-gb10-machine-is-so-freaking-cool/4 (2025-10-14) |
| **LLM inference** | **60–90 W** | M | same |
| CPU+GPU stress | "just under 200W" | M | same |
| Note | `nvidia-smi` reports GPU power only, so measure at the wall for the video | V | NVIDIA forum (above) |
| Size / weight / temp | 150 × 150 × 50.5 mm, 1.2 kg; operating 5–30 °C, 10–90 % RH | V | NVIDIA hardware overview (above) |
| Memory / storage | 128 GB LPDDR5x, 273 GB/s; 1 or 4 TB self-encrypting NVMe | V | same |

### 1.9 Latency model for the assistant (derived)

**Assumed budgets (A):**
- First prompt: 5,000 tokens (system prompt, tool schemas, question, retrieved context).
- Each tool-call turn generates 120 tokens: ~60 tokens of low-effort reasoning plus ~60 tokens of tool-call JSON.
- Each tool result adds 600 tokens. Raw series never enter context.
- The final turn generates 300 tokens: ~80 reasoning plus ~220 answer.
- Each tool executes in 0.3 s. The team measured a DuckDB sortie series query at ≈ 0.24 s
  (docs/architecture/03).
- The prompt cache plus SWA checkpoints mean later turns re-process only the new 720 tokens (assistant message + tool result).

**Rates (M):**
- Spark first prefill: measured 0.907 s for 4,096 tokens, then 4,158 t/s.
- Later short prefills: 1,896 t/s (the measured pp512 rate, conservative).
- Decode: interpolated from the depth table in §1.5.

| Profile | TTFT (5K prompt) | Prefill total | Decode total | Tools | **3-tool answer** | First *answer* token (after reasoning) |
|---|---|---|---|---|---|---|
| **DGX Spark (GB10)** | **1.14 s** | 2.26 s | 8.58 s | 0.9 s | **11.7 s** | ≈ 8.9 s |
| DGX Spark, tight budget (80 tok per tool turn, 200 final) | 1.14 s | 2.20 s | 5.71 s | 0.9 s | **8.8 s** | ≈ 7.0 s |
| RTX 4090 (2026 build), Spark depth-decay applied | 0.48 s | 0.98 s | 2.81 s | 0.9 s | 4.7 s | ≈ 3.7 s |
| RTX 2000 Ada 16 GB (70 W) | 1.99 s | 3.93 s | 10.16 s | 0.9 s | 15.0 s | ≈ 11.6 s |
| M4 Max 36 GB | 4.35 s | 8.36 s | 7.85 s | 0.9 s | 17.1 s | ≈ 14.5 s |
| M4 Pro 64 GB (Mac mini) | 7.58 s | 14.89 s | 11.31 s | 0.9 s | 27.1 s | ≈ 23.3 s |
| **CPU-only, Ryzen 9 9950X** (degraded) | **36.5 s** | 51.2 s | 26.6 s | 0.9 s | **78.7 s** | ≈ 70 s |

Notes:
- TTFT is the first *generated* token, which is a reasoning token for gpt-oss. Stream a status line
  ("querying records…") so the officer sees progress within ~1 s.
- Decode is ~73 % of the Spark total, so cut reasoning and output tokens (low effort, `--reasoning-budget`,
  compact JSON) rather than buying a faster prefill.
- The architecture targets (first token < 2 s; 1–3-tool p50 < 10 s, docs/architecture/10) hold on Spark for
  1–2 tools. For 3 tools they hold only with the tight budget.
- Grammar-constrained decoding overhead is small by design. llama.cpp samples first, checks a single token
  against the grammar and re-samples with the full grammar only on rejection (`common/sampling.cpp`,
  `common_sampler_sample`). llguidance (optional backend) states ≈ 50 µs CPU per token mask for a 128k
  tokenizer (https://github.com/guidance-ai/llguidance README). **A**: < 5 % decode overhead. Measure it.
- OpenAI recommends `temperature=1.0, top_p=1.0` for gpt-oss (https://github.com/openai/gpt-oss README), but our design uses 0–0.3. Any latency or quality
  numbers must come from our own golden-set runs at our setting.

### 1.10 Recommendation

**Recommended "station server": one GB10 box (NVIDIA DGX Spark or an OEM GB10 system), 128 GB, 4 TB SED NVMe,
running gpt-oss-20b MXFP4 on a pinned llama.cpp build, `--no-mmap -c 16384 --jinja -fa on -ub 2048`.**

Why this profile is defensible for an air-gapped squadron or base deployment:
1. It is the best-documented option. The llama.cpp maintainers publish a full depth sweep and a concurrency
   sweep for it in the repository itself (`benches/dgx-spark`).
2. It is a single small box (1.2 kg) drawing 60–90 W while answering, which is UPS- and generator-friendly.
3. The 128 GB unified memory hosts the LLM (≈ 15 GB) plus DuckDB, CP-SAT, PyMC and the UI on one machine.
   The same box can step up to gpt-oss-120b (59.02 GiB) without new hardware. On Spark it measures pp2048 2,443.91 and tg32 58.72 t/s, falling to 49.45 t/s at 16K (**M**, benches/dgx-spark, 2026-02-05).
4. Local self-encrypting storage and no cloud dependency.
5. Seven OEMs ship GB10 systems (NVIDIA newsroom, 2025-10-13).

Caveats:
- The operating range is **5–30 °C**, so the box needs an air-conditioned tech or ops room.
- It is aarch64 (Arm). DuckDB 1.5.6 and OR-Tools 9.15 ship Linux aarch64 wheels, and PyMC/PyTensor are pure-Python wheels that need a C compiler (PyPI, checked 2026-10-16). Verify the full stack.
- It is not ruggedised.
- Model loading is slow with mmap.

The fallback hardware is a conventional x86 workstation with an NVIDIA pro GPU of 16–24 GB. Measured
examples: the RTX 2000 Ada (70 W) at 70 t/s decode, and the RTX PRO 6000 Max-Q at 250 t/s.

**Degraded / fallback profile to show: "GPU unavailable, CPU-only".**
- Hardware: Ryzen 9 9950X (16 cores, 2 × DDR5-6000), llama.cpp b6401 CPU BLAS, gpt-oss-20b Q8_0 (12.11 GB,
  same footprint as MXFP4).
- Measured (**M**, https://openbenchmarking.org/result/2509083-NE-LLAMACPU914, 2025-09-08): tg128 26.94 t/s,
  pp512 147.29 t/s, pp2048 139.79 t/s.
- Derived (**D**): TTFT for a 5K prompt ≈ 36.5 s; 3-tool answer ≈ 79 s.
- Message for the video: "assistant slows to about a minute per answer. Rules, plans, forecasts and the
  decision board are unaffected (no LLM in any decision step)."
- Larger CPUs do better on decode, but prefill stays CPU-bound at ~160–240 t/s:
  - EPYC 9755 (128 cores, 12-ch DDR5-5200): tg128 67.84, pp512 240.67 (**M**,
    https://openbenchmarking.org/result/2602217-PTS-LLAMACPP51, 2026-02-21).
  - Threadripper PRO 9995WX: tg128 ≈ 48.7, pp512 ≈ 188 (**M**,
    https://openbenchmarking.org/result/2511187-PTS-LLAMACPP54, 2025-11-18).

---

## 2. Other runtime figures

Re-measure every figure in this section on the demo machine before it goes on screen. The tags follow the
legend at the top. "≈ chart" means we read the value off a published chart.

### 2.1 GoRules ZEN decision-table evaluation (Rust core, Python binding `zen-engine`)

| Figure | Config | Tag | Source (date) |
|---|---|---|---|
| **64.3 µs/op (Rust) · 103.6 µs/op (Python) · 234.7 µs/op (Node)**; median of 23 snapshots: Rust 64.5, Python 99.4 µs | Fixture `decision-table-discounts`: 3 rules × 4 inputs, collect hit policy. GitHub `ubuntu-latest` runner, 500 iterations, Python 3.13. **Every call re-reads and re-parses the JSON via `FilesystemLoader`**, so this is an upper bound that includes loading. | M (vendor CI) | https://gorules.github.io/zen/bench (data: https://gorules.github.io/zen/dev/bench/data.js, commit c747ea2, 2026-10-13); harness https://github.com/gorules/zen/tree/master/benchmark |
| 91,000 evals/s average over 74 decision benchmarks (**D**: ≈ 11 µs/eval). Pure decision tables "150K+" evals/s (**D**: ≤ 7 µs) | MacBook Pro M3, single core. Excludes I/O and decision loading. | V | https://docs.gorules.io/developers/overview/performance (undated, read 2026-10-16) |
| Python binding overhead | rated "Low"; no number published | V | same page |
| Python, precompiled single expression node: 2.62 µs/op (0.37.1). **≈ 290 µs/op in ≥ 0.38.4**, a ~30× regression; the issue is open | Intel Core Ultra 7 265K, Python 3.10 | M (third party) | https://github.com/gorules/zen/issues/441 (2026-03-20) |
| Large table: 1,418 rows × 13 cols, match at the last row ≈ 2.6 ms; match at row 8 ≈ 141 µs | Rust 0.29.1 | M (user) | https://github.com/gorules/zen/issues/276 (2024-11) |

**On screen:** "≈ 0.1 ms per decision-table evaluation" (basis: vendor CI, Python, load included), or more
safely "< 1 ms". Do not quote the 11 µs vendor figure. Pin the `zen-engine` version, because of the open
regression in issue 441.

### 2.2 OR-Tools CP-SAT: rolling-horizon flight-and-maintenance plan

**We found no published CP-SAT benchmark for military FMP**, with or without a 30–120 s limit. The FMP
literature (Peschiera et al.) uses CPLEX.

| Figure | Config | Tag | Source (date) |
|---|---|---|---|
| FMP MIP base scenario (60 monthly periods, 15–60 aircraft, ~4.3k vars / 6.3k constraints): **avg 310.6 s, min 2.2 s, avg gap 0.3 %** under a 1 h limit. Larger cases: \|T\| = 140 → 1,651 s, gap 3.3 % | CPLEX 12.8, 12-core, 64 GB | M (not CP-SAT) | Peschiera, Battaïa, Haït, Dupin, arXiv:2001.09856 (2020-01-27), Tables 10/12 — https://arxiv.org/abs/2001.09856 |
| Simulated-annealing heuristic, time to first feasible: avg 23.7 s | same | M | same, Table 14 |
| Closest CP-SAT analogue, rostering: **30 staff × 14 days → feasible at 87.3 s, gap 5.8 %**; 10 × 14 → optimal in 4.7 s; 5 × 7 → optimal in 0.8 s | OR-Tools 9.12, 16-core, 120 s limit | M (industry preprint, not peer-reviewed, internally inconsistent) | arXiv:2608.30419 (2026-08-31), Table 4 — https://arxiv.org/html/2608.30419 |
| Default `num_workers = 0`, meaning all cores (the old "8 workers" default is outdated) | OR-Tools v9.15 | V | https://github.com/google/or-tools/blob/stable/ortools/sat/sat_parameters.proto |
| CP-SAT took gold in the MiniZinc Challenge 2025, Fixed / Free / Parallel categories | ranking only | M | https://www.minizinc.org/challenge/2025/results/ |
| Recent FMP shape: 25 aircraft, 5 docks, 24-month receding window. No runtime reported | – | – | arXiv:2609.11710 (2026-09-10) |

**On screen:** show our own budget and outcome, e.g. "plan optimised within a 60 s CP-SAT budget · best plan
found · gap x %", measured on our box. Do not quote literature solve times as ours.

### 2.3 DuckDB as-of (ASOF JOIN) queries

| Figure | Config | Tag | Source (date) |
|---|---|---|---|
| AsOf join, small probe (1–2,048 rows) against a build table of **10 M rows ≈ 0.2–0.3 s · 100 M ≈ 2.5–3.2 s** · 1 B ≈ 42–60 s. Memory 256 MB at 10 M, 6 GB at 100 M | iMac Pro, 18-core Xeon W, 128 GB, 9–36 threads, in-memory tables (not Parquet) | M (≈ chart) | DuckDB blog "Planning AsOf Joins", https://duckdb.org/2025/02/19/asof-plans (2025-02-19) |
| 5 M-row self-join: **0.425 s** (IEJoin 3.52 s). 100 K × 1 M: 0.077 s | not stated | M | https://duckdb.org/2023/09/15/asof-joins-fuzzy-temporal-lookups (2023-09-15) |
| DuckDB 1.5.1, 100 M × 100 M ASOF: **3.62 s** | 16 cores, 64 GB, 16 threads | M (secondary, competitor vendor) | https://www.velodb.io/blog/asof-join-benchmark-apache-doris-vs-clickhouse-and-duckdb (2026-06-11) |
| 5 M trades × 15 M quotes from **Parquet**, 3 equality keys: 8.95 s, including materialising 4.9 M rows to pandas | not stated | M (secondary) | https://dataintellect.com/blog/duckdb-asof-joins/ (2023-11-15) |
| Our own: binned series for a whole sortie ≈ 0.24 s | Apple M4 laptop, preview v0.9 | M (team, unlogged) | docs/architecture/03-data-foundation.md |

**On screen:** for an `as_of(t)` point lookup (small probe), "≈ 0.2–0.3 s at 10⁷ rows, ≈ 3 s at 10⁸ rows" is
consistent with DuckDB's published charts. Better: show our own logged timing on the 163 M-row preview, on the
M4 laptop.

### 2.4 PyMC NUTS fit time (small hierarchical / survival models)

PyMC's "took N s" message times only the sampling loop. Compilation and NUTS init are excluded
(`pymc/sampling/mcmc.py`). No notebook states its hardware.

| Model, N | Chains × iterations | Wall | Tag | Source (date) |
|---|---|---|---|---|
| Weibull AFT with censoring, mastectomy, **N = 44** | 4 × (1,000 tune + 1,000 draws) | **14 s** (log-logistic 11 s) | M | pymc-examples `survival_analysis/bayes_param_survival.ipynb` (PyMC 5.28 dev, run 2026-04-25) — https://github.com/pymc-devs/pymc-examples/blob/main/examples/survival_analysis/bayes_param_survival.ipynb |
| Hierarchical radon, **N = 919, 85 groups** | 4 × (2,000–3,000 + 1,000) | partial pooling 2 s; non-centred slopes 7 s; LKJ correlated 24 s | M | `generalized_linear_models/multilevel_modeling.ipynb` (PyMC 5.25.1, 2025-11-27) |
| Hierarchical binomial, 71 groups | 4 × (2,000 + 2,000) | 15 s | M | `GLM-hierarchical-binomial-model.ipynb` (2026-04-27) |
| Weibull AFT, N = 3,770, 10 predictors / frailty Cox | 4 × (1,000 + 1,000) | 91 s / 162 s | M | `survival_analysis/frailty_models.ipynb` (PyMC 5.3, 2023-11-28) |
| Backend effect (probabilistic PCA, N = 5,000) | 4 × (1,000 + 1,000) | C backend 47.6 s, numpyro 12.9 s, blackjax 11.6 s, nutpie 16.1 s | M | `samplers/fast_sampling_with_jax_and_numba.ipynb` (2023-07-11) |

**On screen:** "Bayesian refit (hierarchical Weibull, a few hundred obs, 4 chains): ≈ 15–30 s" (**D** from the
rows above; excludes compile), or more safely "under a minute". Re-measure on the demo box.

### 2.5 MLflow registry alias swap (`set_registered_model_alias`)

**Undocumented. No published latency exists.** The implementation is one SELECT plus a one-row upsert in a
single DB session
(https://github.com/mlflow/mlflow/blob/fb519dbbc82746675ff8ab9c2b5386c17a73fe46/mlflow/store/model_registry/sqlalchemy_store.py#L1511-L1537).
**Do not show a number** unless we measure p50/p99 on our own SQLite or Postgres store.

---

## 3. Fleet KPI reference ranges (to sanity-check the simulated KPIs)

**Definitions differ, so label every on-screen KPI with its metric.**
- **IAF "serviceability"** means "aircraft are airworthy" (CAG 38/2015, fn 67). The norm is **75 %** for
  fighters and 70 % for the IL-76/78.
- **US "mission capable" (MC)** means the aircraft can fly at least one tasked mission. **FMC** means it can
  fly all of them. MC excludes depot-possessed aircraft.
- **CAG 7/2018** helicopter serviceability excludes AOG aircraft from the denominator.
- **CAG anonymises aircraft types.** Fleet 'C' is the Su-30MKI by press identification (Defense News,
  2015-12-21) and by CAG's own description.

### 3.1 Indian fleets (CAG audits = primary)

| Figure | Fleet / period | Source (date) |
|---|---|---|
| Serviceability **55.50–59.73 %** against a **75 %** norm; AOG 10.90–15.32 % of fleet; flying-task shortfall 31.13–43.05 % | 'C' (Su-30MKI), calendar 2006–2010 (shortfall 2004-05 to 2008-09) | CAG Report 38 of 2015 (Air Force), para 2.3.3.1, Table 2.8, pp. 61–62 — https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015_chap_2.pdf (tabled 2015-12-18; table verified by us) |
| Serviceability 41.32–51.52 %; AOG 23.02–37.34 % | 'D' (MiG-21 Bison), 2004-05 to 2008-09 | CAG 38/2015, Table 2.9, p. 75 |
| Availability ≈ 66 % against 75 % planned; flying-task shortfall 43 % | 'AA' (AWACS), 2011-12 to 2013-14 | CAG 38/2015, Table 2.1, p. 12 |
| Serviceability IL-76 avg **37.99 %**, IL-78 avg **48.51 %**, against a 70 % target; grounded 41.39 % / 31.90 % | 2010-11 to 2015-16 | CAG Report 24 of 2017, para 2.7.4, Table 1, pp. 35–36 — https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Chapter_2_-_Audit_Findings_of_Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf (2017-07-28) |
| ALH serviceability IAF 56–61 %, Army 44–56 % (desired 80 %) | 2014-15 to 2016-17 | CAG 7/2018 press release — https://d7i5wg8xwe4hf.cloudfront.net/uploads/PressRelease/PR-Press-7-of-2018-05f5f6d33be55e9-01952327.pdf |
| MiG-29K serviceability 15.93–37.63 % | Indian Navy, 2009-10 to 2014-15 | CAG 17/2016, para 2.5.5, p. 60 |
| Su-30MKI planned utilisation **240 FH per aircraft per year**; overhaul cycle planned **22 months per aircraft** | contract planning | CAG Report 35 of 2014, Ch. 9, paras 9.1.4.3 / 9.1.3.6 — https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2014/Union_Compliance_Defence_Army_Ordnance_Factories_35_2014_Chapter_9.pdf |
| Su-30MKI serviceability "slipped to 46 percent, is today above 63 percent" | Defence Minister Parrikar, ~Jan 2017 (S) | AIN, 2017-01-25 — https://backend.ainonline.com/aviation-news/defense/2017-01-25/russia-and-india-negotiating-su-30-combat-jet-support-deal |
| Su-30MKI 48 % → 55 %; non-availability split ≈ 20 % 1st/2nd-line maintenance, 11–12 % HAL repair and overhaul, 13–14 % AOG | MoD figures, Sep–Oct 2014 (S) | Business Standard (A. Shukla), 2014-10-23 — https://www.ajaishukla.com/2014/10/government-takes-note-of-su-30mkis-poor.html |

There is **no verified official figure for "Su-30MKI ≥ 70 %"**: 70–75 % are norms. Do not use "46 % per
CAG": 46 % is Parrikar's figure.

### 3.2 US mission-capable rates (MC, Air Force-provided via Air & Space Forces Magazine unless noted)

| Type | FY2022 | FY2023 | FY2024 | Notes |
|---|---|---|---|---|
| F-16C | 70.7 | 69 | 64 (Defense News) | FY2019 73 |
| F-15E | 51.6 | 55 | n/p | |
| F-15EX | 84.6 | 85 | 83.13 | small fleet |
| F-22A | 57.4 | 52 | 40.19 | |
| F-35A | 56 (text/GAO) | 51 | 51.5 | **FY2025 38.6 % MC, 28.5 % FMC** |
| A-10C | 69.7 | 67 | 67 | |
| USAF average (unweighted) | 71.24 | 69.92 | **67.15** | weighted 62 (Defense News) |

Sources:
- FY2024: A&SF, 2025-02-18, https://www.airandspaceforces.com/air-force-mission-capable-rates-fiscal-2024/ ;
  Defense News, 2025-03-06, https://www.defensenews.com/air/2025/03/06/air-force-aircraft-readiness-plunges-to-new-low-alarming-chief/
- FY2022–23: A&SF, 2024-05-29, https://www.airandspaceforces.com/air-force-mission-capable-rates-2023/
- Per-type USAF FY2025 rates are not public.

**F-35, GAO (primary):**
- Fleet MC **67 % → 44 %**, fleet FMC **38 % → 25 %**, FY2021 → FY2025. Reset targets: 80 % MC and 65 % FMC
  by 2030 (GAO-26-108113, 2026-06-11, https://files.gao.gov/reports/GAO-26-108113/index.html).
- NMCS ≈ 17 % (FY2020) → ≈ 27 % (Mar 2023), against a funded level of ~15 % (GAO-23-105341, 2023-09-21,
  https://www.gao.gov/assets/gao-23-105341.pdf).

**Goals are generally missed:**
- GAO-23-106217 (2022-11-10): only 4 of 49 types met their MC goal in most years FY2011–21; 26 never met it.
- GAO-21-101SU: none of the F-35, F-22, F-16 or F/A-18 reached 80 % MC on a daily-average FY2019 basis.

**USN F/A-18E/F:** ≈ 50 % MC in Oct 2018 → 341 MC jets (the 80 % target) in Sep 2019. That 80 % was measured
on PMAI, not the whole fleet (Military.com, 2019-09-24, S).

### 3.3 BIT false alarms and NFF

| Figure | System | Source (date) | Type |
|---|---|---|---|
| BIT false-alarm requirement: objective **30 %**, threshold **45 %**. Demonstrated **86.0 %** (Dec 2010) → **33.5 %** (Dec 2012); fault isolation demonstrated 90.5 % (threshold 85 %) | F/A-18E/F, all avionics | DoD SARs, 31 Dec 2010 and 31 Dec 2012 (GlobalSecurity mirror) — https://www.globalsecurity.org/military/library/budget/fy2012/sar/f-a-18e-f_december_2012_sar.pdf | P. **The source is the SARs, not DOT&E** (correct docs/architecture/04 accordingly) |
| ≈ 1 false alarm per flight hour against a requirement of 1 per 50 FH | F-35 diagnostics, IOT&E report Feb 2024 | Bloomberg via Stars and Stripes, 2024-11-21 — https://www.stripes.com/theaters/us/2024-11-21/f-35-study-problems-reliability-maintenance-weapons-15923799.html | S |
| ≈ 80 % of ALIS-flagged issues false positives | F-35 ALIS, Eglin, anecdote at a 2015 hearing | Air Force Times, 2015-04-15 | S (anecdotal; disputed by the JPO) |
| CND "more than 85% of all observed field failures in avionics" | avionics (UK MoD / CALCE) | Williams et al., *QREI* 14 (1998) — https://web.calce.umd.edu/articles/abstracts/1998/cndfail.htm | peer-reviewed, upper bound |
| NFF 38 % of removed LRUs (BA); > 50 % (747-400 EFIS units, Thai) | commercial avionics, 1995 | FlightGlobal, 1996-03-20 — https://flightglobal.com/biting-into-false-alarms/10024.article | S |
| NFF + CND = 40–60 % of reported component failures (airlines); ~35 % NFF of incoming repairs (Rockwell Collins) | commercial, 2005 | Avionics Magazine, 2005-08-01 — https://aviationtoday.com/2005/08/01/special-report-avoiding-nff | S |
| 72 % of LRUs failed the ATE test although serviceable (test-equipment false rejection) | IAF 'AA' ATE | CAG 38/2015, para 2.1.3.2 | P |

We could not verify specific percentages in Khan et al. 2014 or Söderholm 2007 (paywalled). Cite them only
as background reviews.

### 3.4 AOG and repair lead times

| Figure | Fleet / period | Source | Type |
|---|---|---|---|
| AOG spares demands met within 1–15 days: IL-76 **10.83 %**, IL-78 **2.59 %**. After more than 6 months: **22.49 %** / **32.72 %**. Norm: issue within **24 h** if stocked | 2010-11 to 2014-15 (2,899 and 770 demands) | CAG 24/2017, para 2.7.4(a), Tables 2–3, pp. 36–37 | P |
| Second-line servicing done on time: IL-76 36.84 %, IL-78 30 % | 2012-13 to 2014-15 | CAG 24/2017, Tables 4–5 | P |
| F-35 component repair time **172 → 131 → 141 days** (Oct 2017 → Aug 2020 → Feb 2023), against a 60–90-day goal; 73 % of components go to the OEM; backlog > 10,000 parts | 2017–2023 | GAO-23-105341, pp. 10–12 | P |
| Share of USAF depot aircraft delayed: 31 % (FY2019) → 73–74 % (FY2024) | USAF | GAO-26-107890 via Air Force Times, 2026-05-15 | S citing P |
| Commercial AOG convention ≈ 4 h response | commercial | contract samples only; ATA Spec 2000 text not public | unverified, context only |

### 3.5 Sanity ranges for our simulated KPIs

| KPI | Credible band from public data | Our preview v0.9 (synthetic) |
|---|---|---|
| Fighter serviceability / MC | IAF 41–64 % observed (75 % norm); US fighters 40–74 % MC (goals 75–90 %). **> 80 % would beat every published figure** | MC mean 0.60, FMC 0.58 (docs/architecture/01) — inside the band |
| FMC | F-35 fleet 25–38 % (FY2021–25) | – |
| Spares-driven non-availability (NMCS / AOG share) | Su-30MKI AOG 11–15 % of fleet; F-35 NMCS 17–27 % | NMCS 285 of 1,440 tail-days ≈ 20 % — inside the band |
| AOG fill within 15 days | 3–11 % (IL-78 / IL-76); 22–33 % take more than 6 months | – |
| Component repair turnaround | F-35 131–172 days (goal 60–90) | – |
| BIT false-alarm share | requirement ≤ 30–45 %; demonstrated 33.5–86 % (F/A-18E/F) | – |
| NFF / CND share of removals | 35–60 % commercial; up to > 85 % CND in avionics | – |
| Flying-task shortfall | 31–43 % (Su-30MKI 2004–09; AWACS) | – |
| Utilisation | Su-30MKI planned 240 FH per aircraft per year | – |

On screen, label Indian figures "CAG audit, fleet anonymised (year)" and US figures "MC rate, FYxx (not FMC
or availability)". Label our simulated KPIs "synthetic simulation, not validated; public reference band
shown".

**Narrative context (S, re-check on the day):**
- IAF fighter squadrons: 29 after the MiG-21 retired (26 Sep 2025), against 42 sanctioned (Tribune,
  2025-07-23).
- Tejas Mk1A: 83 + 97 ordered. HAL cited 5 aircraft ready and awaiting GE engines (All India Radio,
  2026-02-05). No formal handover was confirmed as of Oct 2026.

---

## 4. Open items before the final cut

1. Run `llama-bench -fa 1 -d 0,4096,8192,16384,32768 -p 2048 -n 32 -ub 2048 -mmp 0` and
   `llama-batched-bench` on the actual demo box. Log the build hash, then replace §0 with our own **M**.
   Meter wall power.
2. Run our golden-set harness at the chosen reasoning effort and budget. Record real tokens per turn and
   p50/p95 latency to replace the **A** budget in §1.9.
3. Time `as_of(t)`, the ZEN eval, the CP-SAT plan (60 s budget), the PyMC refit and the MLflow alias swap on
   the demo box. Show only logged numbers.
4. Two corrections to our architecture docs:
   - The "F/A-18E/F BIT false alarms 33.5–86 %" figure is from DoD SARs, not DOT&E.
   - "Su-30MKI 55–60 %" is calendar 2006–2010 data from CAG 38/2015.
