from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator


class ModelCfg(BaseModel):
    base_url: str
    model: str
    api_key: str = "local"  # most local servers ignore it; some require a non-empty value
    timeout_s: float = 600


class Sampling(BaseModel):
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 512


class Config(BaseModel):
    run_name: str
    seed: int = 42
    repeats: int = 3
    concurrency: int = 1
    warmup: int = 3
    concurrency_sweep: list[int] = []  # e.g. [1, 2, 4, 8]; empty = skip
    models: dict[str, ModelCfg]
    sampling: Sampling = Sampling()
    judge: ModelCfg | None = None
    suites: list[str] = ["latency"]
    suites_dir: Path = Path("suites")

    @model_validator(mode="after")
    def _check(self):
        if set(self.models) != {"A", "B"}:
            raise ValueError("models must define exactly A and B")
        if self.judge and any(
            (m.base_url, m.model) == (self.judge.base_url, self.judge.model) for m in self.models.values()
        ):
            raise ValueError("judge must not be one of the compared models")
        return self


def load(path: str | Path) -> Config:
    return Config.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
