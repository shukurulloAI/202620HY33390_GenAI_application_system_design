from rag.llm_client import CachedClient, LLMResult


class CountingClient:
    model_id = "counting"

    def __init__(self):
        self.calls = 0

    def generate(self, *, system, prompt, json_schema=None, temperature=0.0, seed=0,
                 max_tokens=0):
        self.calls += 1
        return LLMResult(text=f"{prompt}#{self.calls}", model_id=self.model_id, latency_s=1.5)


def test_identical_requests_replay_with_their_latency(tmp_path):
    inner = CountingClient()
    llm = CachedClient(inner, tmp_path)
    first = llm.generate(system="s", prompt="p")
    again = llm.generate(system="s", prompt="p")
    assert inner.calls == 1 and llm.cached == 1
    assert again.text == first.text and again.latency_s == 1.5


def test_a_different_request_or_sampling_is_not_replayed(tmp_path):
    inner = CountingClient()
    llm = CachedClient(inner, tmp_path)
    llm.generate(system="s", prompt="p")
    llm.generate(system="s", prompt="q")
    llm.generate(system="s", prompt="p", seed=2)
    llm.generate(system="s", prompt="p", temperature=0.7)
    llm.generate(system="s", prompt="p", temperature=0.7)
    assert inner.calls == 5 and llm.cached == 0


class _Response:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _client(monkeypatch, outcomes):
    """An OllamaClient whose HTTP calls return/raise `outcomes` in order."""
    import json
    import urllib.request

    from rag import config
    from rag.llm_client import OllamaClient
    calls = []

    def urlopen(request, timeout=None):
        calls.append(json.loads(request.data))
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(json.dumps(outcome).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(config, "OLLAMA_RETRY_WAIT_S", 0)
    return OllamaClient("qwen2.5:7b"), calls


OK = {"message": {"content": "{}"}, "prompt_eval_count": 3, "eval_count": 2,
      "done_reason": "stop"}


def test_ollama_retries_once_after_a_connection_error(monkeypatch):
    import urllib.error
    client, calls = _client(monkeypatch, [urllib.error.URLError(ConnectionRefusedError()), OK])
    result = client.generate(system="s", prompt="p")
    assert result.text == "{}" and len(calls) == 2
    assert calls[0]["keep_alive"] == "30m"


def test_ollama_does_not_retry_a_timeout_or_an_unknown_model(monkeypatch):
    import urllib.error

    import pytest
    for error in (urllib.error.URLError(TimeoutError()),
                  urllib.error.HTTPError("u", 404, "not found", None, None)):
        client, calls = _client(monkeypatch, [error, OK])
        with pytest.raises(RuntimeError):
            client.generate(system="s", prompt="p")
        assert len(calls) == 1
