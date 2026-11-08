"""
Provider boundary for the generator (Lesson 1: "a provider boundary keeps the
experiment portable").

Every client returns an LLMResult with the raw text, the model ID and measured token
counts, so traces record exactly what was sent and received.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from rag import config


@dataclass
class LLMResult:
    text: str
    model_id: str
    prompt_tokens: int | None = None       # measured by the provider
    completion_tokens: int | None = None
    latency_s: float = 0.0
    done_reason: str | None = None         # "stop" or "length" (output cut off)


class LLMClient(Protocol):
    model_id: str

    def generate(self, *, system: str, prompt: str, json_schema: dict | None = None,
                 temperature: float = config.TEMPERATURE, seed: int = config.SEED,
                 max_tokens: int = config.LLM_OUTPUT_RESERVE) -> LLMResult: ...


class OllamaClient:
    """Local model served by Ollama (`ollama serve`, `ollama pull <model>`)."""

    def __init__(self, model: str = config.LLM_MODEL, url: str = config.OLLAMA_URL,
                 num_ctx: int = config.LLM_CONTEXT, timeout_s: float = 300):
        self.model_id = model
        self.url = url.rstrip("/")
        self.num_ctx = num_ctx
        self.timeout_s = timeout_s

    def generate(self, *, system, prompt, json_schema=None,
                 temperature=config.TEMPERATURE, seed=config.SEED,
                 max_tokens=config.LLM_OUTPUT_RESERVE) -> LLMResult:
        body = {
            "model": self.model_id,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "seed": seed,
                        "num_predict": max_tokens, "num_ctx": self.num_ctx},
        }
        if json_schema is not None:
            body["format"] = json_schema          # structured output (constrained JSON)
        request = urllib.request.Request(
            f"{self.url}/api/chat", data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                data = json.loads(response.read())
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama is not reachable at {self.url}. Start it with `ollama serve` "
                f"and run `ollama pull {self.model_id}`.") from exc
        return LLMResult(
            text=data["message"]["content"],
            model_id=self.model_id,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            latency_s=round(time.perf_counter() - start, 3),
            done_reason=data.get("done_reason"),
        )


class FixtureClient:
    """Offline, deterministic stand-in for contract tests (no semantic quality)."""

    model_id = "offline-fixture-v1"

    def generate(self, *, system, prompt, json_schema=None, temperature=0.0, seed=0,
                 max_tokens=0) -> LLMResult:
        text = json.dumps({
            "status": "INSUFFICIENT_CONTEXT", "bin": "", "bin_en": "",
            "how_to_prepare": [], "answer_text": "Fixture client: no generation.",
            "citations": [], "missing": "fixture client does not read evidence",
        })
        return LLMResult(text=text, model_id=self.model_id, done_reason="stop")


class CachedClient:
    """Replays identical requests at temperature 0 from disk (experiments only: variants
    that change retrieval send the router the same request). A replayed result keeps its
    recorded latency, so stage timings stay true; `cached` counts the replays."""

    def __init__(self, inner: LLMClient, directory=None):
        from rag import paths
        self.inner, self.model_id = inner, inner.model_id
        self.directory = directory or paths.ROOT / ".cache" / "llm"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cached = 0

    def generate(self, *, system, prompt, json_schema=None, temperature=config.TEMPERATURE,
                 seed=config.SEED, max_tokens=config.LLM_OUTPUT_RESERVE) -> LLMResult:
        if temperature != 0:
            return self.inner.generate(system=system, prompt=prompt, json_schema=json_schema,
                                       temperature=temperature, seed=seed, max_tokens=max_tokens)
        key = hashlib.sha256(json.dumps(
            [self.model_id, getattr(self.inner, "num_ctx", None), system, prompt, json_schema,
             seed, max_tokens], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        path = self.directory / f"{key}.json"
        if path.exists():
            self.cached += 1
            return LLMResult(**json.loads(path.read_text(encoding="utf-8")))
        result = self.inner.generate(system=system, prompt=prompt, json_schema=json_schema,
                                     temperature=temperature, seed=seed, max_tokens=max_tokens)
        path.write_text(json.dumps(result.__dict__, ensure_ascii=False), encoding="utf-8")
        return result


def make_client(name: str = "ollama", model: str | None = None) -> LLMClient:
    if name == "fixture":
        return FixtureClient()
    if name == "ollama":
        return OllamaClient(model or config.LLM_MODEL)
    raise ValueError(f"unknown LLM client: {name}")
