import asyncio
import json

import httpx
import pytest

from evalh import config, runner

SSE = (
    'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
    'data: {"choices":[{"delta":{"content":"lo"},"finish_reason":"stop"}]}\n\n'
    'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2}}\n\n'
    "data: [DONE]\n\n"
)


def cfg(tmp_path, **kw):
    (tmp_path / "suites/latency").mkdir(parents=True)
    (tmp_path / "suites/latency/prompts.jsonl").write_text('{"id":"p1","prompt":"hi"}\n{"id":"p2","prompt":"yo"}\n')
    base = {"run_name": "t", "repeats": 2, "warmup": 1, "suites_dir": str(tmp_path / "suites"),
            "models": {"A": {"base_url": "http://a/v1", "model": "a"}, "B": {"base_url": "http://b/v1", "model": "b"}}}
    return config.Config.model_validate({**base, **kw})


def test_run_writes_traces(tmp_path):
    seen = []

    def handler(req):
        seen.append(json.loads(req.content))
        return httpx.Response(200, text=SSE, headers={"content-type": "text/event-stream"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    run_dir = asyncio.run(runner.run(cfg(tmp_path), tmp_path / "runs", client))
    traces = [json.loads(l) for l in (run_dir / "traces.jsonl").read_text().splitlines()]

    assert len(traces) == 2 * 2 * 2  # models x cases x repeats
    assert len(seen) == len(traces) + 2  # + 1 warmup per model
    t = traces[0]
    assert t["text"] == "Hello" and t["usage"]["completion_tokens"] == 2
    assert t["finish_reason"] == "stop" and t["ttft_s"] is not None and t["error"] is None
    assert [t["model_key"] for t in traces] == ["A"] * 4 + ["B"] * 4  # sequential, not interleaved
    assert json.loads((run_dir / "meta.json").read_text())["config_hash"]


def test_http_error_recorded(tmp_path):
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="boom")))
    run_dir = asyncio.run(runner.run(cfg(tmp_path, warmup=0, repeats=1), tmp_path / "runs", client))
    t = json.loads((run_dir / "traces.jsonl").read_text().splitlines()[0])
    assert t["error"].startswith("HTTP 500")


def test_judge_cannot_be_candidate(tmp_path):
    with pytest.raises(ValueError, match="judge"):
        cfg(tmp_path, judge={"base_url": "http://a/v1", "model": "a"})
