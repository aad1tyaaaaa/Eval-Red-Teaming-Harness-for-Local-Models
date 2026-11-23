import asyncio
import json
import webbrowser
from pathlib import Path

import typer

from . import config, report, runner

app = typer.Typer(no_args_is_help=True)


@app.command()
def run(c: Path = typer.Option(..., "-c", "--config", exists=True), out: Path = Path("runs")):
    """Run all configured suites for models A and B, then build the report."""
    cfg = config.load(c)
    run_dir = asyncio.run(runner.run(cfg, out))
    traces = report.load_traces(run_dir)
    errors = sum(1 for t in traces if t.get("error"))
    typer.echo(f"{run_dir}: {len(traces)} traces, {errors} errors")
    typer.echo(f"report: {report.render(run_dir)}")


@app.command()
def score(run_dir: Path = typer.Argument(..., exists=True, file_okay=False)):
    """Recompute metrics.json from traces (no model calls)."""
    typer.echo(json.dumps(report.score(run_dir), indent=2))


@app.command("report")
def report_cmd(run_dir: Path = typer.Argument(..., exists=True, file_okay=False), open_: bool = typer.Option(False, "--open")):
    """Re-score from traces and write report.html."""
    path = report.render(run_dir)
    typer.echo(path)
    if open_:
        webbrowser.open(path.resolve().as_uri())
