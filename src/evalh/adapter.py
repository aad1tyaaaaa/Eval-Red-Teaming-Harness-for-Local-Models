"""OpenAI-compatible streaming chat client (Ollama, llama.cpp, vLLM, LM Studio)."""
import json
import time

import httpx

from .config import ModelCfg, Sampling


async def chat(client: httpx.AsyncClient, m: ModelCfg, messages: list[dict], s: Sampling,
               seed: int, **extra) -> dict:
    """Stream one completion; return text + timings + server-reported usage (if any)."""
    body = {
        "model": m.model, "messages": messages, "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": s.temperature, "top_p": s.top_p, "max_tokens": s.max_tokens, "seed": seed,
        **extra,
    }
    out = {"text": "", "ttft_s": None, "total_s": None, "n_chunks": 0, "usage": None,
           "finish_reason": None, "error": None}
    t0 = time.perf_counter()
    try:
        async with client.stream("POST", f"{m.base_url.rstrip('/')}/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {m.api_key}"}, timeout=m.timeout_s) as r:
            if r.status_code >= 400:
                out["error"] = f"HTTP {r.status_code}: {(await r.aread()).decode(errors='replace')[:500]}"
                return out
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                if chunk.get("usage"):
                    out["usage"] = chunk["usage"]
                for ch in chunk.get("choices") or []:
                    delta = (ch.get("delta") or {}).get("content")
                    if delta:
                        if out["ttft_s"] is None:
                            out["ttft_s"] = time.perf_counter() - t0
                        out["text"] += delta
                        out["n_chunks"] += 1
                    out["finish_reason"] = ch.get("finish_reason") or out["finish_reason"]
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        out["error"] = f"{type(e).__name__}: {e}"
    out["total_s"] = time.perf_counter() - t0
    return out
