"""
Judged citation metrics from Lesson 6 ("Citation metrics need a consistent counting unit"):

    citation precision  = cited claims whose cited sources support them / all cited claims
    citation coverage   = claims supported by their own citations     / all claims

    python -m eval.answer_judge eval/reports/<name>/traces.jsonl       # judge, writes
                                                                       #   traces.judged.json
    python -m eval.run_eval --name <name> --rescore                    # report picks it up

One claim = one sentence of the text the LLM wrote
(answer_text in its raw output); every sentence is treated as material. Schedule lines are
not claims here: code writes them from the district rows (rag/schedule_text.py) and they are
scored exactly by rows_found / only_gold_rows. A claim's cited set is the [n] marks in its
sentence. Each cited claim is shown to the judge with the full text of the sources it cites
and only those, so a correct claim with a wrong citation counts as unsupported, as in Lesson
6's example. An uncited claim is not in the precision denominator; in coverage it counts as
a claim without support.

Judge: the same pinned local judge as the Ragas scores (eval/ragas_eval.py, exaone3.5:7.8b,
another model family than the generator), temperature 0, its digest recorded. A reply that
is not valid JSON leaves that claim unjudged (counted as failed, in no denominator).
Judge labels need a human audit before they are trusted (Lesson 6).

The judging is a separate step because it needs Ollama, and the metrics (eval/metrics.py)
run offline. Its output is written next to the traces, so experiment variants work too.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from eval.ragas_eval import JUDGE_MODEL  # one pinned judge for every judged metric

PROMPT_ID = "answer_judge_v1"
# A v2 that told the judge omissions and paraphrases are fine passed 12 of 15 cited claims in
# the baseline's false answers (v1: 7), contradictions included, so v1 stays: it errs strict,
# and its citation precision is a lower bound. The 7.8B judge needs a human audit either way.

_MARK = re.compile(r"\[(\d+(?:\s*[-–,]\s*\d+)*)\]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])|\n+")

SCHEMA = {"type": "object", "properties": {"reason": {"type": "string"},
                                           "supported": {"type": "boolean"}},
          "required": ["reason", "supported"]}

CLAIM_SYSTEM = ("You check citations. You compare one statement with the source text it cites "
                "and decide whether the source supports it. You use only the source text, "
                "never your own knowledge.")
CLAIM_PROMPT = """Source text cited by the statement:
{sources}

The whole answer, only to understand words like "it" or "them" in the statement:
{answer}

Statement to check:
{claim}

The statement and the source may be in different languages (the sources are Korean). Compare
meaning, not wording: a translation or paraphrase of what the source says is supported.

Is every fact in the statement stated by the source text above: the bin or container, any
preparation step, condition, day, time and place? If any part is missing from the source or
contradicts it, it is not supported. Facts that appear only in other sentences of the answer
are not checked here.

Return JSON: {{"reason": "<one short sentence>", "supported": true or false}}"""



# ---------------------------------------------------------------------------- claims

def _numbers(mark: str) -> list[int]:
    out = []
    for part in re.split(r"\s*,\s*", mark):
        bounds = [int(x) for x in re.split(r"\s*[-–]\s*", part) if x]
        out += list(range(bounds[0], bounds[-1] + 1)) if bounds else []
    return out


def claims(text: str) -> list[dict]:
    """Text -> [{"text", "cited": [n, ...]}], one per sentence or line. A piece that is only
    citation marks (as in "... bag. [1]") belongs to the sentence before it."""
    out: list[dict] = []
    for sentence in _SENTENCE_END.split(text or ""):
        sentence = sentence.strip()
        if not sentence:
            continue
        cited = [n for mark in _MARK.findall(sentence) for n in _numbers(mark)]
        clean = re.sub(r"\s+([.!?,;:。！？])", r"\1",
                       re.sub(r"\s+", " ", _MARK.sub("", sentence))).strip()
        if not re.search(r"[^\W\d_]", clean):          # marks only
            if out:
                out[-1]["cited"] = sorted(set(out[-1]["cited"]) | set(cited))
            continue
        out.append({"text": clean, "cited": sorted(set(cited))})
    return out


def llm_text(trace: dict) -> str:
    """The answer_text the LLM wrote, before code added schedule lines; "" if none."""
    raw = (trace.get("llm") or {}).get("raw_output")
    try:
        return (json.loads(raw).get("answer_text") or "") if raw else ""
    except (ValueError, AttributeError):
        return ""


# ---------------------------------------------------------------------------- judge

def _ask(client, system: str, prompt: str) -> dict:
    result = client.generate(system=system, prompt=prompt, json_schema=SCHEMA,
                             temperature=0.0, seed=0, max_tokens=300)
    try:
        reply = json.loads(result.text)
        return {"supported": bool(reply["supported"]), "reason": str(reply.get("reason", ""))}
    except (ValueError, KeyError, TypeError):
        return {"supported": None, "reason": f"unparsed judge reply: {result.text[:200]}"}


def judge_claim(client, claim: dict, sources: dict[int, str], answer_text: str = "") -> dict:
    """One cited claim -> {"supported": bool | None, "reason"}. A citation number with no
    source in the answer cannot support anything."""
    texts = [f"[{n}] {sources[n]}" for n in claim["cited"] if n in sources]
    if not texts:
        return {"supported": False, "reason": "cites a number with no source"}
    return _ask(client, CLAIM_SYSTEM, CLAIM_PROMPT.format(
        sources="\n\n".join(texts), answer=answer_text or claim["text"], claim=claim["text"]))


def judge_trace(client, trace: dict) -> dict | None:
    """Claims of one answered trace, labelled; None if the trace is not an ANSWER."""
    answer = trace.get("answer") or {}
    if answer.get("status") != "ANSWER":
        return None
    sources = {c["n"]: c.get("text", "") for c in answer.get("citations", [])}
    written = llm_text(trace)
    context = _MARK.sub("", written)
    labelled = []
    for claim in claims(written):
        label = judge_claim(client, claim, sources, context) if claim["cited"] else \
            {"supported": None, "reason": "uncited"}
        labelled.append({**claim, **label})
    return summarize(labelled)


def summarize(labelled: list[dict]) -> dict:
    """Counts per case. Failed judge replies are in no denominator."""
    cited = [c for c in labelled if c["cited"]]
    judged = [c for c in cited if c["supported"] is not None]
    supported = sum(c["supported"] for c in judged)
    failed = len(cited) - len(judged)
    return {"claims": labelled, "n_claims": len(labelled),
            "cited": len(judged), "supported": supported,                    # precision
            "claims_judged": len(labelled) - failed,                         # coverage
            "uncited": len(labelled) - len(cited), "failed": failed}


# ---------------------------------------------------------------------------- files

def judged_path(traces_path: Path) -> Path:
    return traces_path.with_name(traces_path.stem + ".judged.json")


def load_labels(traces_path: Path) -> dict[str, dict] | None:
    """{case_id: counts} from the judge file next to the traces, or None when the traces
    have not been judged."""
    path = judged_path(Path(traces_path))
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def _rate(k: int, n: int) -> float | None:
    return round(k / n, 3) if n else None


def run(traces_path: Path, model: str = JUDGE_MODEL, limit: int | None = None) -> Path:
    from rag.files import read_jsonl
    from rag.llm_client import CachedClient, OllamaClient, ollama_digest
    traces = read_jsonl(traces_path)[:limit] if limit else read_jsonl(traces_path)
    inner = OllamaClient(model)
    client = CachedClient(inner)
    out_cases = {}
    for i, trace in enumerate(traces, 1):
        result = judge_trace(client, trace)
        if result is not None:
            out_cases[trace["case_id"]] = result
            print(f"\r{i}/{len(traces)} {trace['case_id']:8} claims {result['supported']}/"
                  f"{result['cited']} cited, {result['claims_judged']} in all   ",
                  end="", flush=True)
    print()

    def total(key: str) -> int:
        return sum(c[key] for c in out_cases.values())
    out = {"traces": str(traces_path), "prompt_id": PROMPT_ID,
           "judge": {"model": model, "digest": ollama_digest(model, inner.url),
                     "temperature": 0.0, "replayed": client.cached},
           "time": datetime.now().isoformat(timespec="seconds"),
           "overall": {"citation_precision": _rate(total("supported"), total("cited")),
                       "citation_coverage": _rate(total("supported"), total("claims_judged")),
                       "cited_claims": total("cited"), "claims": total("claims_judged"),
                       "supported_claims": total("supported"), "failed": total("failed")},
           "cases": out_cases}
    path = judged_path(traces_path)
    if limit:
        path = path.with_name(path.stem + f"_first{limit}.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["overall"]), "->", path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("traces", type=Path, help="a traces .jsonl file")
    parser.add_argument("--judge", default=JUDGE_MODEL)
    parser.add_argument("--limit", type=int, help="judge only the first N traces (smoke test)")
    args = parser.parse_args()
    run(args.traces, args.judge, args.limit)


if __name__ == "__main__":
    main()
