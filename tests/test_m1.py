import asyncio
import json

import httpx

from evalh import latency, report, runner
from test_m0 import SSE, cfg


def test_pct():
    assert latency.pct([1, 2, 3, 4], 50) == 2.5
    assert latency.pct([5], 99) == 5
    assert latency.pct([None], 50) is None


def test_per_request_uses_server_usage():
    t = {"ttft_s": 0.5, "total_s": 2.5, "n_chunks": 3, "usage": {"prompt_tokens": 100, "completion_tokens": 40}}
    r = latency.per_request(t)
    assert r["decode_tps"] == 20 and r["prefill_tps"] == 200 and r["token_source"] == "server"
    r = latency.per_request({**t, "usage": None})
    assert r["out_tokens"] == 3 and r["prefill_tps"] is None and r["token_source"] == "chunks"


def test_filler_padding():
    msg = runner.messages({"id": "x", "prompt": "Q?", "filler_words": 30})[0]["content"]
    assert len(msg.split()) == 31 and msg.endswith("Q?")


def test_run_sweep_and_report(tmp_path):
    ok = lambda r: httpx.Response(200, text=SSE, headers={"content-type": "text/event-stream"})
    client = httpx.AsyncClient(transport=httpx.MockTransport(ok))
    c = cfg(tmp_path, concurrency_sweep=[1, 2])
    run_dir = asyncio.run(runner.run(c, tmp_path / "runs", client))

    html = report.render(run_dir).read_text(encoding="utf-8")
    m = json.loads((run_dir / "metrics.json").read_text())["latency"]
    assert [s["concurrency"] for s in m["A"]["sweep"]] == [1, 2]
    assert [s["n"] for s in m["B"]["sweep"]] == [2, 4]
    assert m["A"]["overall"]["n"] == 4 and m["A"]["errors"] == 0
    assert "Latency scorecard" in html and "Plotly.newPlot" in html
