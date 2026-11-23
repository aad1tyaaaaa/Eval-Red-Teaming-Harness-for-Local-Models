# Project Context: evalh

Read this first to pick up work on the project. `plan.md` is the full design; this file is the **current state**: what exists, how it fits together, the decisions made, and what comes next.

---

## 1. What this is

`evalh` is a Python CLI that compares two local LLMs (**A** vs **B**) under identical conditions. They can be two different models or two quantizations of one model, e.g. `llama3.1:8b-q4_K_M` vs `q8_0`. It answers one question: *is B good enough to replace A, and where does it break?*

It has four evaluation tracks:

1. **Latency & throughput**: done (M1)
2. **Structured JSON adherence**: not started (M2)
3. **RAG faithfulness**: not started (M3)
4. **Adversarial / red-team**: not started (M4)

It works with any **OpenAI-compatible** server: Ollama, llama.cpp `llama-server`, vLLM, LM Studio.

---

## 2. Status

| Phase | Branch | State | PR |
|---|---|---|---|
| M0 Skeleton | `phase/m0-skeleton` | ✅ merged | #1 |
| M1 Latency | `phase/m1-latency` | ✅ merged | #2 |
| M2 JSON | `phase/m2-json` | ⏭ next | – |
| M3 RAG | `phase/m3-rag` | todo | – |
| M4 Adversarial | `phase/m4-adversarial` | todo | – |
| M5 Stats & verdict | `phase/m5-stats` | todo | – |
| M6 Polish | `phase/m6-polish` | todo | – |

Tests: 7 passing (`uv run pytest`). The code has not been run against a live model server yet; it has only been tested against mock transports.

---

## 3. Workflow conventions

- **One branch and one PR per phase**, merged into `main` with a merge commit, and the branch deleted afterwards.
- **No Claude co-author / attribution** in commits or PR bodies.
- Remote: `github.com/aad1tyaaaaa/Eval-Red-Teaming-Harness-for-Local-Models`. Use the `gh` CLI for PRs.
- Tooling: `uv` (Python 3.11+, developed on 3.13, Windows). `uv sync` installs; `uv run pytest` runs the tests.
- Style: minimal code. Prefer the stdlib, add no speculative abstractions, and mark deliberate shortcuts with a `# ponytail:` comment that names the limit and the upgrade path.

---

## 4. Repository layout (as built)

```
plan.md                      full design doc (source of truth for scope)
context.md                   this file
README.md                    quickstart, phase table, commands
pyproject.toml / uv.lock     deps: typer, httpx, pydantic, pyyaml; dev: pytest
configs/example.compare.yaml example A/B config (Ollama q4 vs q8)
suites/latency/prompts.jsonl 6 bucketed latency prompts
src/evalh/
  config.py    Pydantic config + validation
  adapter.py   streaming OpenAI-compat chat client
  runner.py    orchestration: warmup, repeats, concurrency, sweep, traces
  latency.py   GpuSampler + latency metrics from traces
  report.py    score (metrics.json) + render (report.html)
  cli.py       Typer app: run / score / report
tests/
  test_m0.py   SSE parsing, sequential A→B, HTTP errors, judge validation
  test_m1.py   percentiles, token-source fallback, filler, sweep + report
runs/          output (gitignored)
```

The layout deliberately differs from `plan.md`. The plan has an `adapters/`, `suites/` and `scorers/` package; the code uses flat modules. Split a module into a package only once a second implementation exists.

---

## 5. Data flow

```
config.yaml ─► config.load() ─► runner.run()
                                   │  for model in [A, B] (sequential, never interleaved):
                                   │    GpuSampler on
                                   │    warmup × N (discarded)
                                   │    every suite case × repeats  (semaphore = concurrency)
                                   │    concurrency sweep (latency only)
                                   │    GpuSampler off → "system" trace
                                   ▼
                     runs/<ts>_<run_name>/
                       meta.json      hardware fingerprint, config hash, git commit, full config
                       traces.jsonl   one line per request (raw, unscored)
                                   ▼
                     report.score()  ─► metrics.json      (pure function of traces)
                     report.render() ─► report.html
```

**Core principle: traces are stored before any scoring.** All metrics are recomputed from `traces.jsonl` (`evalh score` / `evalh report`) with no model calls. New scorers must read only the traces.

---

## 6. Key formats

### Config (`config.py`)
| Field | Default | Notes |
|---|---|---|
| `run_name` | required | used in the run dir name |
| `seed` | 42 | sent as `seed` in every request |
| `repeats` | 3 | repeats per case |
| `concurrency` | 1 | keep at 1 for clean latency numbers |
| `warmup` | 3 | discarded requests per model |
| `concurrency_sweep` | `[]` | e.g. `[1,2,4,8]`; each level sends 2×n requests of the first latency case |
| `models` | required | must be exactly `A` and `B`; each has `base_url`, `model`, `api_key="local"`, `timeout_s=600` |
| `sampling` | temp 0, top_p 1, max_tokens 512 | identical for A and B |
| `judge` | optional | validation **rejects** a judge that equals A or B (same base_url + model) |
| `suites` | `["latency"]` | each name maps to `suites/<name>/prompts.jsonl` |
| `suites_dir` | `suites` | |

### Suite case (`suites/<suite>/prompts.jsonl`)
```json
{"id": "long-1", "bucket": "3-long", "filler_words": 1500, "prompt": "Summarize the text above..."}
```
- `id` (required). Then either `prompt` or a full `messages` list.
- `filler_words`: deterministic padding text placed before the prompt, used for the prefill buckets.
- `bucket`: groups latency metrics. The number prefix gives the sort order.
- Any extra fields are stored with the trace (as `case`), so scorers can use them later (e.g. `expected`, `schema`).

### Trace line (`traces.jsonl`)
```
model_key, model, suite, case_id, repeat, case, messages,
text, ttft_s, total_s, n_chunks, usage, finish_reason, error, t_start, t_end,
[concurrency]              # sweep traces only (suite="sweep")
```
There is also one `suite: "system"` line per model with `vram_start_mib`, `vram_peak_mib` and `gpu_util_mean` (null if there's no NVIDIA GPU).

### Metrics (`metrics.json`)
`{"latency": {"A": {...}, "B": {...}}}`. Each side holds `model`, `errors`, `token_source`, `overall` and `buckets[bucket]` stats (n, ttft p50/p95, e2e p50/90/95/99, decode_tps_p50, prefill_tps_p50, prompt_tokens_p50), plus `raw_e2e`, `sweep[]` and `system`. Later phases add top-level keys (`json`, `rag`, `adversarial`).

---

## 7. Design decisions & known limits

| Decision | Why / limit |
|---|---|
| `httpx` only, no `openai` SDK | SSE parsing is about 20 lines; one fewer dependency |
| JSONL only, no SQLite yet | Add it in M2/M5 if cross-run querying needs it |
| `stream_options.include_usage` | Server token counts are preferred; otherwise output tokens are approximated by stream chunks, and `token_source` labels which was used |
| A fully, then B | Avoids GPU contention. Ollama may keep A resident while B runs, so VRAM is **whole-GPU**; compare start vs peak |
| `nvidia-smi -lms 200` subprocess | Avoids a `pynvml` dependency. Multi-GPU lines count as separate samples (`ponytail:` note) |
| Plotly.js from a CDN | The report needs network access to draw charts (`ponytail:` note). Inline it if offline viewing matters |
| Sweep = 2×n requests per level | A fixed constant (`ponytail:` note) |
| One `prompts.jsonl` per suite | Multi-file suites (adversarial) come in M4 |
| Very-long bucket (4500 words) | Needs a context window of 8k or more. Silent truncation shows up as a low `prompt_tokens_p50` |
| HTTP/parse errors are recorded, not raised | A run never crashes on one bad request; errors are counted in the scorecard |

---

## 8. Next steps (M2: JSON adherence), per plan §6.2

- `suites/json/prompts.jsonl` with 40–60 cases plus `suites/json/schemas/*.json`. Categories: flat, nested, arrays, enums, nullable, numeric, unicode, long outputs, adversarial keys.
- Modes: `prompt_only`, `json_mode` (`response_format: json_object`) and `grammar` (schema-constrained). A capability probe marks unsupported modes N/A. The runner needs per-mode request extras (`chat(**extra)` already accepts them).
- A scoring ladder in a pure-function scorer: parse (with fence stripping) → schema valid (with categorised `jsonschema` errors) → field accuracy against `expected` → verbosity leakage. The repair re-prompt is reported separately.
- New dependency: `jsonschema`. Add a `json` section to `metrics.json` and the report.

After M2: M3 RAG (needs `sentence-transformers` and an NLI model; retrieval is precomputed and shared), M4 adversarial (canary tokens, refusal classifier, ASR vs over-refusal, mutators; keep harmful seeds as benign proxies), M5 stats (bootstrap CIs, McNemar/Wilcoxon, flip table, verdict thresholds), M6 polish (judge–human κ, Dockerfile, CI with Qwen2.5-0.5B).
