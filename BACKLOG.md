# Backlog: one item = one PR = one day

The daily agent takes the **first unchecked item**, implements it on branch `task/NN-<slug>`, adds or updates tests, ticks the box here, updates `context.md` when state changes, opens a PR titled `NN: <title>`, and merges it once `uv run pytest` passes. Design reference: `plan.md`. Current state: `context.md`.

## M2: JSON adherence
- [ ] 01 json-parse: add `jsonschema` dependency; `src/evalh/jsonscore.py` `parse()` with fence stripping (records whether stripping was needed) + tests
- [ ] 02 json-schema-validate: schema validation with categorised errors (missing required, wrong type, extra field, enum violation)
- [ ] 03 json-field-accuracy: per-field exact/normalised match against `expected`
- [ ] 04 json-leakage: detect text before/after the JSON object (verbosity leakage)
- [ ] 05 json-cases-flat-nested: `suites/json/prompts.jsonl` + `schemas/` with 10 flat/nested cases
- [ ] 06 json-cases-arrays-enums: 10 cases covering arrays of objects, enums, nullable/optional fields
- [ ] 07 json-cases-hard: 10+ cases covering numeric precision, unicode, long outputs (50+ items), keys that look like instructions
- [ ] 08 json-modes: runner expands each JSON case into `prompt_only` and `json_mode` (`response_format: json_object`) requests; mode stored in the trace
- [ ] 09 json-grammar-mode: `grammar` mode (`response_format: json_schema`) + startup capability probe that marks unsupported modes N/A
- [ ] 10 json-repair: one automatic repair re-prompt on failure, reported separately
- [ ] 11 json-metrics: `json` section in `metrics.json` (parse rate, schema validity, field accuracy, leakage per mode)
- [ ] 12 json-report: report section with a stacked bar of the failure ladder + an error-category table

## M3: RAG faithfulness
- [ ] 13 rag-corpus: `suites/rag/corpus/` with 20+ short markdown docs (original fictional product manual)
- [ ] 14 rag-retrieval: chunker + precomputed shared retrieval (`evalh rag index`), embeddings in an optional `rag` dependency group
- [ ] 15 rag-qa-answerable: 15 single-doc answerable QA items in `qa.jsonl`
- [ ] 16 rag-qa-multihop: 10 multi-hop (2-doc) items
- [ ] 17 rag-qa-unanswerable: 10 unanswerable items
- [ ] 18 rag-qa-conflict-distractor: 15 conflicting-context and distractor items
- [ ] 19 rag-prompt: RAG prompt builder using the precomputed contexts and `[doc_id]` citation instructions
- [ ] 20 rag-f1-abstention: token F1 vs gold + abstention detector
- [ ] 21 rag-citations: citation accuracy scorer
- [ ] 22 judge-client: judge model client (fixed prompt, temp 0) + atomic-claim splitting
- [ ] 23 rag-nli: NLI entailment faithfulness (supported claims / total)
- [ ] 24 rag-judge-correctness: LLM-judge correctness 0–2 + NLI tiebreak
- [ ] 25 rag-report: `rag` metrics + report (faithfulness histogram, abstention confusion matrix, context-over-prior rate)

## M4: Adversarial
- [ ] 26 multi-file-suites: load every `suites/<suite>/*.jsonl`, with the file name as category
- [ ] 27 canary: random canary in the system prompt + exact-match leak detector
- [ ] 28 adv-direct-injection: direct prompt-injection seeds
- [ ] 29 adv-indirect-injection: injection hidden in a document or tool output
- [ ] 30 adv-extraction: system-prompt extraction seeds (paraphrase, translate, "repeat above")
- [ ] 31 adv-jailbreak: jailbreak templates wrapping benign proxy requests only
- [ ] 32 adv-over-refusal: benign-but-edgy prompts that must NOT be refused
- [ ] 33 adv-format-attacks: schema-breaking requests scored with the JSON scorer
- [ ] 34 adv-robustness: typos, homoglyphs, zero-width chars, empty input, Hinglish, compared against a clean baseline
- [ ] 35 adv-consistency: 5-way paraphrase sets + agreement rate
- [ ] 36 refusal-heuristics: regex/keyword refusal classifier
- [ ] 37 refusal-judge: LLM-judge for ambiguous refusals
- [ ] 38 mutators-encoding: base64 / leetspeak mutators
- [ ] 39 mutators-wrap: persona wrap, prefix injection, translation mutators
- [ ] 40 suite-new-cli: `evalh suite new adversarial --from seeds.jsonl --mutate ...`
- [ ] 41 adv-report: ASR + over-refusal metrics, scatter per category, canary-leak list

## M5: Stats & verdict
- [ ] 42 bootstrap-ci: bootstrap 95% CI helper (1000 resamples, stdlib `random` with a seed)
- [ ] 43 mcnemar: McNemar test on paired pass/fail
- [ ] 44 wilcoxon: Wilcoxon signed-rank for continuous scores
- [ ] 45 scorecard-ci: CIs + significance markers on every scorecard row
- [ ] 46 flip-table: flip analysis (A pass / B fail and the reverse) + filterable report table with side-by-side responses
- [ ] 47 verdict: configurable thresholds → ✅/⚠️/❌ per metric + an overall verdict
- [ ] 48 radar: radar chart across the four tracks
- [ ] 49 compare-runs: `evalh compare runs/a runs/b`

## M6: Polish
- [ ] 50 judge-position-swap: run pairwise judgments in both orders to cancel position bias
- [ ] 51 human-labels-kappa: CLI to hand-label judgments + Cohen's κ in the report
- [ ] 52 determinism-check: two temperature-0 runs compared; flag the backend if outputs differ
- [ ] 53 adapter-retries: retry with backoff on connection errors / 5xx
- [ ] 54 dockerfile: Dockerfile for the harness
- [ ] 55 ci-unit: GitHub Actions running `uv run pytest`
- [ ] 56 ci-golden: CI golden run with Qwen2.5-0.5B via Ollama on a mini-suite
- [ ] 57 readme-guide: README quickstart + "adding a test case" guide + sample report screenshot
- [ ] 58 offline-report: option to inline plotly.js for offline reports

## Stretch
- [ ] 59 energy-per-token: `nvidia-smi` power draw → joules per token
- [ ] 60 tool-calling-suite: tool/function-calling adherence suite
- [ ] 61 needle-haystack: long-context needle-in-a-haystack track
