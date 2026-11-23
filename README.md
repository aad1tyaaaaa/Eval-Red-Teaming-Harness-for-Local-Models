# evalh — Eval & Red-Teaming Harness for Local Models

A/B compare two local models (or two quantizations) over any OpenAI-compatible server. Full design: [plan.md](plan.md).

```bash
uv sync
uv run evalh run -c configs/example.compare.yaml   # -> runs/<ts>_<name>/{meta.json,traces.jsonl}
uv run pytest
```

## Phases

Each phase ships as its own branch + PR into `main`.

| Phase | Branch | Scope |
|---|---|---|
| M0 Skeleton | `phase/m0-skeleton` | Config, streaming OpenAI-compat adapter, raw JSONL traces, `evalh run` |
| M1 Latency | `phase/m1-latency` | TTFT, tok/s, percentiles, VRAM sampler, concurrency sweep, first HTML report |
| M2 JSON | `phase/m2-json` | JSON cases, 3 modes, validation ladder, repair pass |
| M3 RAG | `phase/m3-rag` | Corpus + QA, fixed retrieval, faithfulness, abstention |
| M4 Adversarial | `phase/m4-adversarial` | Seeds + mutators, canary detection, refusal classifier, ASR vs over-refusal |
| M5 Stats & verdict | `phase/m5-stats` | Bootstrap CIs, McNemar/Wilcoxon, flip analysis, thresholds |
| M6 Polish | `phase/m6-polish` | Judge κ, docs, Dockerfile, CI |

## Commands

```bash
evalh run -c <config>          # run suites, write traces, build report
evalh score runs/<dir>         # recompute metrics.json from traces (no model calls)
evalh report runs/<dir> --open # rebuild report.html
```
