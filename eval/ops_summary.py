"""
What the live system did (Lesson 7: measure the deployed workflow, not only the test set).
Reads the website's own records: traces/<date>.jsonl, traces/errors.jsonl and
traces/feedback.jsonl. No models.

    python -m eval.ops_summary                 # everything still kept (rag/tracing.py)
    python -m eval.ops_summary --days 7        # the last 7 days
    python -m eval.ops_summary --out ops.md

Reports requests per day, the status mix (answers, abstentions, questions back), latency
p50/p90 per stage, validation downgrades and contract problems, errors, and the 👍/👎
feedback joined to its answers by trace_id. These numbers describe use, not correctness:
a 👍 is not a verified answer.
"""
from __future__ import annotations

import argparse
import math
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from rag import paths
from rag.files import read_jsonl
from rag.tracing import _DAILY

STAGES = ("route_s", "retrieve_s", "rerank_s", "schedule_s", "generate_s", "schedule_text_s",
          "total_s")
DECLINED = ("INSUFFICIENT_CONTEXT", "OUT_OF_SCOPE")


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile (q in 0-100)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q / 100 * len(ordered)) - 1)]


def load(directory: Path, since: date | None) -> tuple[list[dict], list[dict], list[dict]]:
    traces = []
    for path in sorted(directory.glob("*.jsonl")):
        match = _DAILY.match(path.name)
        if match and (since is None or date.fromisoformat(match[1]) >= since):
            traces.extend(read_jsonl(path))

    def records(name: str) -> list[dict]:
        path = directory / name
        rows = read_jsonl(path) if path.exists() else []
        return [r for r in rows if since is None or str(r.get("time", ""))[:10] >= str(since)]

    return traces, records("errors.jsonl"), records("feedback.jsonl")


def summarize(traces: list[dict], errors: list[dict], feedback: list[dict]) -> dict:
    statuses = Counter((t.get("answer") or {}).get("status", "?") for t in traces)
    n = len(traces)
    latency = {}
    for stage in STAGES:
        values = [t["timings"][stage] for t in traces if stage in t.get("timings", {})]
        if values:
            latency[stage] = {"n": len(values), "p50": percentile(values, 50),
                              "p90": percentile(values, 90)}
    by_trace = {t["trace_id"]: t for t in traces}
    ratings = Counter(f["rating"] for f in feedback)
    down_status = Counter((by_trace.get(f["trace_id"], {}).get("answer") or {}).get("status",
                                                                                     "not kept")
                          for f in feedback if f["rating"] == "down")
    return {
        "requests": n,
        "per_day": dict(sorted(Counter(t["time"][:10] for t in traces).items())),
        "statuses": dict(statuses.most_common()),
        "declined_rate": round(sum(statuses[s] for s in DECLINED) / n, 3) if n else None,
        "languages": dict(Counter((t.get("resolved") or {}).get("lang") or "?"
                                  for t in traces).most_common()),
        "latency_s": latency,
        "downgraded": sum(bool(((t.get("checks") or {}).get("validation") or {})
                               .get("downgraded")) for t in traces),
        "output_truncated": sum(bool((t.get("checks") or {}).get("output_truncated"))
                                for t in traces),
        "contract_problems": sum(bool(t.get("contract_problems")) for t in traces),
        "errors": len(errors),
        "error_types": dict(Counter(e.get("error", "?").split("(")[0] for e in errors)),
        "feedback": dict(ratings), "feedback_rate": round(len(feedback) / n, 3) if n else None,
        "thumbs_down_by_status": dict(down_status),
    }


def markdown(s: dict, period: str) -> str:
    lines = [f"# Live use: {period}", "",
             f"{s['requests']} requests, {s['errors']} errors (handed off). Feedback on "
             f"{s['feedback_rate'] if s['feedback_rate'] is not None else '–'} of answers.", "",
             "| | |", "|---|---|",
             f"| Requests per day | {', '.join(f'{d}: {k}' for d, k in s['per_day'].items())} |",
             f"| Status | {', '.join(f'{k} {v}' for k, v in s['statuses'].items())} |",
             f"| Declined (abstained or out of scope) | {s['declined_rate']} |",
             f"| Languages | {', '.join(f'{k} {v}' for k, v in s['languages'].items())} |",
             f"| Downgraded by validation / output cut off / contract problems | "
             f"{s['downgraded']} / {s['output_truncated']} / {s['contract_problems']} |",
             f"| Errors | {s['error_types'] or 'none'} |",
             f"| Feedback | {s['feedback'] or 'none'}; 👎 by status: "
             f"{s['thumbs_down_by_status'] or 'none'} |", "",
             "| Stage | n | p50 (s) | p90 (s) |", "|---|---|---|---|"]
    for stage, v in s["latency_s"].items():
        lines.append(f"| {stage} | {v['n']} | {v['p50']} | {v['p90']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=paths.TRACE_DIR)
    parser.add_argument("--days", type=int, help="only the last N days")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    since = (datetime.now(UTC).date() - timedelta(days=args.days - 1)) if args.days else None
    traces, errors, feedback = load(args.dir, since)
    text = markdown(summarize(traces, errors, feedback),
                    f"since {since}" if since else "all kept records")
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
