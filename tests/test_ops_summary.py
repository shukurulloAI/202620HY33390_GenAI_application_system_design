"""Summary of live use from traces, errors and feedback."""
from __future__ import annotations

from eval.ops_summary import load, markdown, percentile, summarize
from rag.files import append_jsonl


def trace(trace_id, day, status, total, lang="en"):
    return {"trace_id": trace_id, "time": f"{day}T10:00:00+00:00", "answer": {"status": status},
            "resolved": {"lang": lang}, "timings": {"total_s": total, "generate_s": total / 2},
            "checks": {"validation": {"downgraded": status == "INSUFFICIENT_CONTEXT"}},
            "contract_problems": []}


def test_percentile_nearest_rank():
    assert percentile([5, 1, 3, 2, 4], 50) == 3 and percentile([5, 1, 3, 2, 4], 90) == 5
    assert percentile([], 50) is None


def test_summary_joins_feedback_to_answers(tmp_path):
    append_jsonl(tmp_path / "2026-11-10.jsonl", trace("a", "2026-11-10", "ANSWER", 20.0))
    append_jsonl(tmp_path / "2026-11-11.jsonl", trace("b", "2026-11-11", "INSUFFICIENT_CONTEXT",
                                                      10.0, "vi"))
    append_jsonl(tmp_path / "feedback.jsonl", {"trace_id": "a", "rating": "down",
                                               "time": "2026-11-10T10:01:00+00:00"})
    append_jsonl(tmp_path / "errors.jsonl", {"error": "ConnectionError('down')",
                                             "time": "2026-11-11T09:00:00+00:00"})
    s = summarize(*load(tmp_path, None))
    assert s["requests"] == 2 and s["declined_rate"] == 0.5 and s["downgraded"] == 1
    assert s["thumbs_down_by_status"] == {"ANSWER": 1} and s["error_types"] == {
        "ConnectionError": 1}
    assert s["latency_s"]["total_s"] == {"n": 2, "p50": 10.0, "p90": 20.0}
    from datetime import date
    recent = summarize(*load(tmp_path, date(2026, 11, 11)))
    assert recent["requests"] == 1 and recent["feedback"] == {}
    assert "| total_s | 2 | 10.0 | 20.0 |" in markdown(s, "all")
