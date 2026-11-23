"""Score a run dir from its traces (no model calls) and render metrics.json + report.html."""
import json
from html import escape
from pathlib import Path

from . import latency

# ponytail: plotly.js from CDN (report needs network to draw charts); inline it if offline viewing matters
PLOTLY = "https://cdn.plot.ly/plotly-2.35.2.min.js"

SCORECARD = [  # (label, path, higher_is_better)
    ("TTFT p50 (s)", ("overall", "ttft_p50"), False),
    ("TTFT p95 (s)", ("overall", "ttft_p95"), False),
    ("E2E p50 (s)", ("overall", "e2e_p50"), False),
    ("E2E p95 (s)", ("overall", "e2e_p95"), False),
    ("E2E p99 (s)", ("overall", "e2e_p99"), False),
    ("Decode tok/s p50", ("overall", "decode_tps_p50"), True),
    ("Prefill tok/s p50", ("overall", "prefill_tps_p50"), True),
    ("Peak VRAM (MiB)", ("system", "vram_peak_mib"), False),
    ("Errors", ("errors",), False),
]


def load_traces(run_dir: Path) -> list[dict]:
    return [json.loads(l) for l in (run_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def score(run_dir: Path) -> dict:
    metrics = {"latency": latency.summarize(load_traces(run_dir))}
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def _get(d, path):
    for p in path:
        d = (d or {}).get(p)
    return d


def _fmt(x):
    return "–" if x is None else f"{x:,.3f}" if isinstance(x, float) and abs(x) < 100 else f"{x:,.0f}"


def scorecard_rows(lat: dict) -> str:
    rows = []
    for label, path, higher in SCORECARD:
        a, b = _get(lat.get("A"), path), _get(lat.get("B"), path)
        delta, cls = "–", ""
        if a is not None and b is not None and a != 0:
            d = (b - a) / abs(a) * 100
            delta = f"{d:+.1f}%"
            cls = "" if abs(d) < 1 else "good" if (d > 0) == higher else "bad"
        rows.append(f"<tr><td>{label}</td><td>{_fmt(a)}</td><td>{_fmt(b)}</td><td class='{cls}'>{delta}</td></tr>")
    return "\n".join(rows)


def charts(lat: dict) -> list[dict]:
    keys = [k for k in ("A", "B") if k in lat]
    buckets = sorted({b for k in keys for b in lat[k]["buckets"]})
    bar = lambda metric: [{"type": "bar", "name": f"{k}: {lat[k]['model']}", "x": buckets,
                           "y": [_get(lat[k], ("buckets", b, metric)) for b in buckets]} for k in keys]
    return [
        {"title": "End-to-end latency by bucket (s)", "data": [
            {"type": "box", "name": f"{k}: {lat[k]['model']}", "boxpoints": "all",
             "x": [b for b in buckets for _ in lat[k]["raw_e2e"].get(b, [])],
             "y": [v for b in buckets for v in lat[k]["raw_e2e"].get(b, [])]} for k in keys],
         "layout": {"boxmode": "group"}},
        {"title": "TTFT p50 by bucket (s)", "data": bar("ttft_p50"), "layout": {"barmode": "group"}},
        {"title": "Decode tok/s p50 by bucket", "data": bar("decode_tps_p50"), "layout": {"barmode": "group"}},
        {"title": "Concurrency sweep: throughput (tok/s)", "data": [
            {"type": "scatter", "mode": "lines+markers", "name": f"{k}: {lat[k]['model']}",
             "x": [s["concurrency"] for s in lat[k]["sweep"]], "y": [s["throughput_tps"] for s in lat[k]["sweep"]]}
            for k in keys], "layout": {"xaxis": {"title": "parallel requests", "type": "log"}}},
    ]


def render(run_dir: Path) -> Path:
    metrics = score(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    lat = metrics["latency"]
    models = "".join(f"<li><b>{k}</b>: {escape(v['base_url'])} · <code>{escape(v['model'])}</code></li>"
                     for k, v in meta["config"]["models"].items())
    divs = "".join(f"<h3>{escape(c['title'])}</h3><div id='c{i}' class='chart'></div>" for i, c in enumerate(charts(lat)))
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>evalh: {escape(meta['config']['run_name'])}</title>
<script src="{PLOTLY}"></script>
<style>body{{font:14px/1.5 system-ui,sans-serif;max-width:1100px;margin:2em auto;padding:0 16px;color:#222}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:4px 10px;text-align:right}}td:first-child{{text-align:left}}
.good{{color:#0a7d32;font-weight:600}}.bad{{color:#c0262d;font-weight:600}}.chart{{height:380px}}code{{background:#f3f3f3;padding:1px 4px}}
.meta{{color:#555}}</style></head><body>
<h1>{escape(meta['config']['run_name'])}</h1>
<ul>{models}</ul>
<p class="meta">GPU: {escape(str(meta.get('gpu')))} · CPU: {escape(str(meta.get('cpu')))} · {escape(meta['platform'])}<br>
config {meta['config_hash']} · commit {escape(str(meta.get('git_commit'))[:10])} · token counts:
{escape(', '.join(f"{k}={'/'.join(v['token_source'])}" for k, v in lat.items()))}</p>
<h2>Latency scorecard</h2>
<table><tr><th>Metric</th><th>A</th><th>B</th><th>Δ (B vs A)</th></tr>{scorecard_rows(lat)}</table>
{divs}
<script>const C={json.dumps(charts(lat))};
C.forEach((c,i)=>Plotly.newPlot('c'+i,c.data,Object.assign({{margin:{{t:10}}}},c.layout),{{responsive:true}}));</script>
</body></html>"""
    path = run_dir / "report.html"
    path.write_text(html, encoding="utf-8")
    return path
