import asyncio
import json
from pathlib import Path

import typer

from . import config, runner

app = typer.Typer(no_args_is_help=True)


@app.command()
def run(c: Path = typer.Option(..., "-c", "--config", exists=True), out: Path = Path("runs")):
    """Run all configured suites for models A and B; write runs/<ts>/traces.jsonl."""
    cfg = config.load(c)
    run_dir = asyncio.run(runner.run(cfg, out))
    lines = (run_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()
    errors = sum(1 for l in lines if json.loads(l)["error"])
    typer.echo(f"{run_dir}: {len(lines)} traces, {errors} errors")


@app.callback()
def main():
    """evalh: A/B eval & red-teaming harness for local models."""
