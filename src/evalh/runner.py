"""Run every suite case against A then B (sequentially) and append raw traces to JSONL."""
import asyncio
import hashlib
import json
import platform
import subprocess
from datetime import datetime
from pathlib import Path

import httpx

from .adapter import chat
from .config import Config


def load_cases(cfg: Config, suite: str) -> list[dict]:
    # ponytail: one file per suite for now; multi-file suites (adversarial/*.jsonl) come with M4
    path = cfg.suites_dir / suite / "prompts.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def fingerprint(cfg: Config) -> dict:
    def sh(*cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            return None
    return {
        "platform": platform.platform(), "cpu": platform.processor(), "python": platform.python_version(),
        "gpu": sh("nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"),
        "git_commit": sh("git", "rev-parse", "HEAD"),
        "config_hash": hashlib.sha256(cfg.model_dump_json().encode()).hexdigest()[:12],
        "config": cfg.model_dump(mode="json"),
    }


async def run(cfg: Config, out_root: Path = Path("runs"), client: httpx.AsyncClient | None = None) -> Path:
    run_dir = out_root / f"{datetime.now():%Y-%m-%d_%H%M%S}_{cfg.run_name}"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps(fingerprint(cfg), indent=2), encoding="utf-8")
    client = client or httpx.AsyncClient()
    sem = asyncio.Semaphore(cfg.concurrency)

    with (run_dir / "traces.jsonl").open("w", encoding="utf-8") as f:
        for key, m in cfg.models.items():  # A fully, then B: never interleave on one GPU
            for _ in range(cfg.warmup):
                await chat(client, m, [{"role": "user", "content": "Hello"}], cfg.sampling, cfg.seed)

            async def one(suite, case, rep):
                msgs = case.get("messages") or [{"role": "user", "content": case["prompt"]}]
                async with sem:
                    res = await chat(client, m, msgs, cfg.sampling, cfg.seed)
                f.write(json.dumps({"model_key": key, "model": m.model, "suite": suite, "case_id": case["id"],
                                    "repeat": rep, "messages": msgs, **res}, ensure_ascii=False) + "\n")
                f.flush()

            await asyncio.gather(*(one(s, c, r) for s in cfg.suites for c in load_cases(cfg, s)
                                   for r in range(cfg.repeats)))
    return run_dir
