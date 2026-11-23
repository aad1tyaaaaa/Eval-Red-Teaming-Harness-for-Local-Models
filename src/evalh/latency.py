"""Latency/throughput metrics computed purely from traces, plus an nvidia-smi VRAM sampler."""
import subprocess
import threading
from collections import defaultdict


class GpuSampler:
    """Polls nvidia-smi every 200 ms while active. No-op without an NVIDIA GPU.

    VRAM is whole-GPU (includes other processes / a still-resident model A), so the report shows start vs peak.
    """

    def __enter__(self):
        self.samples = []  # (mem_used_mib, util_pct)
        try:
            self.proc = subprocess.Popen(
                ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits",
                 "-lms", "200"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        except OSError:
            self.proc = None
            return self
        threading.Thread(target=self._read, daemon=True).start()
        return self

    def _read(self):
        # ponytail: multi-GPU lines are treated as independent samples; sum per tick if you shard models
        for line in self.proc.stdout:
            try:
                mem, util = (float(x) for x in line.split(","))
                self.samples.append((mem, util))
            except ValueError:
                pass

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()

    def summary(self) -> dict:
        if not self.samples:
            return {"vram_start_mib": None, "vram_peak_mib": None, "gpu_util_mean": None}
        return {"vram_start_mib": self.samples[0][0], "vram_peak_mib": max(s[0] for s in self.samples),
                "gpu_util_mean": sum(s[1] for s in self.samples) / len(self.samples)}


def pct(xs: list[float], p: float) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def per_request(t: dict) -> dict:
    usage = t.get("usage") or {}
    out_tok = usage.get("completion_tokens") or t["n_chunks"]  # chunks ~= tokens on most servers
    ttft, total = t["ttft_s"], t["total_s"]
    decode = total - ttft if ttft is not None else None
    return {
        "ttft_s": ttft, "e2e_s": total, "out_tokens": out_tok, "prompt_tokens": usage.get("prompt_tokens"),
        "decode_tps": out_tok / decode if decode and out_tok > 1 else None,
        "prefill_tps": usage["prompt_tokens"] / ttft if ttft and usage.get("prompt_tokens") else None,
        "token_source": "server" if usage.get("completion_tokens") else "chunks",
    }


def stats(rows: list[dict]) -> dict:
    col = lambda k: [r[k] for r in rows]
    return {
        "n": len(rows),
        "ttft_p50": pct(col("ttft_s"), 50), "ttft_p95": pct(col("ttft_s"), 95),
        **{f"e2e_p{p}": pct(col("e2e_s"), p) for p in (50, 90, 95, 99)},
        "decode_tps_p50": pct(col("decode_tps"), 50), "prefill_tps_p50": pct(col("prefill_tps"), 50),
        "prompt_tokens_p50": pct(col("prompt_tokens"), 50),
    }


def summarize(traces: list[dict]) -> dict:
    out = {}
    for key in sorted({t["model_key"] for t in traces}):
        mine = [t for t in traces if t["model_key"] == key]
        ok = [t for t in mine if t.get("suite") in ("latency", "sweep") and not t.get("error")]
        lat = [(t, per_request(t)) for t in ok if t["suite"] == "latency"]
        buckets = defaultdict(list)
        for t, r in lat:
            buckets[t["case"].get("bucket", "default")].append(r)

        sweep = []
        for n in sorted({t["concurrency"] for t in ok if t["suite"] == "sweep"}):
            reqs = [t for t in ok if t["suite"] == "sweep" and t["concurrency"] == n]
            wall = max(t["t_end"] for t in reqs) - min(t["t_start"] for t in reqs)
            sweep.append({"concurrency": n, "n": len(reqs),
                          "throughput_tps": sum(per_request(t)["out_tokens"] for t in reqs) / wall,
                          "e2e_p50": pct([t["total_s"] for t in reqs], 50)})

        out[key] = {
            "model": mine[0]["model"],
            "errors": sum(1 for t in mine if t.get("error")),
            "token_source": sorted({r["token_source"] for _, r in lat}),
            "overall": stats([r for _, r in lat]),
            "buckets": {b: stats(rs) for b, rs in buckets.items()},
            "raw_e2e": {b: [r["e2e_s"] for r in rs] for b, rs in buckets.items()},
            "sweep": sweep,
            "system": next(({k: v for k, v in t.items() if k.startswith(("vram", "gpu"))}
                            for t in mine if t.get("suite") == "system"), {}),
        }
    return out
