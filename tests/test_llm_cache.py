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
