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
from .latency import GpuSampler

FILLER = ("The archive held ledgers of grain shipments, weather notes, tide tables and letters between "
          "harbour masters, each page catalogued by date, port and the clerk who copied it. ").split()


def load_cases(cfg: Config, suite: str) -> list[dict]:
    # ponytail: one file per suite for now; multi-file suites (adversarial/*.jsonl) come with M4
    path = cfg.suites_dir / suite / "prompts.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def messages(case: dict) -> list[dict]:
    if case.get("messages"):
        return case["messages"]
    prompt = case["prompt"]
    if n := case.get("filler_words"):  # deterministic padding for long-prompt (prefill) buckets
        prompt = " ".join(FILLER[i % len(FILLER)] for i in range(n)) + "\n\n" + prompt
    return [{"role": "user", "content": prompt}]


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

    with (run_dir / "traces.jsonl").open("w", encoding="utf-8") as f:
        def write(rec):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()

        for key, m in cfg.models.items():  # A fully, then B: never interleave on one GPU
            with GpuSampler() as gpu:
                for _ in range(cfg.warmup):
                    await chat(client, m, [{"role": "user", "content": "Hello"}], cfg.sampling, cfg.seed)

                sem = asyncio.Semaphore(cfg.concurrency)

                async def one(suite, case, rep, sem=sem, **tags):
                    msgs = messages(case)
                    async with sem:
                        res = await chat(client, m, msgs, cfg.sampling, cfg.seed)
                    write({"model_key": key, "model": m.model, "suite": suite, "case_id": case["id"],
                           "repeat": rep, "case": case, "messages": msgs, **tags, **res})

                await asyncio.gather(*(one(s, c, r) for s in cfg.suites for c in load_cases(cfg, s)
                                       for r in range(cfg.repeats)))

                if cfg.concurrency_sweep and "latency" in cfg.suites:
                    case = load_cases(cfg, "latency")[0]
                    for n in cfg.concurrency_sweep:
                        # ponytail: fixed 2 rounds per level; make configurable if CIs on throughput are too wide
                        level = asyncio.Semaphore(n)
                        await asyncio.gather(*(one("sweep", case, r, sem=level, concurrency=n) for r in range(2 * n)))
            write({"model_key": key, "model": m.model, "suite": "system", **gpu.summary()})
    return run_dir
