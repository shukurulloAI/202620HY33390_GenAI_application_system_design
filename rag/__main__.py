"""
Ask one question from the command line.

    python -m rag "Where do I throw away a pizza box?"
    python -m rag "Can I put food waste out tonight? I live in Seongdong-gu Haengdang-dong"
    python -m rag "..." --baseline                  # Phase 1 configuration
    python -m rag "..." --set retrieval=dense --set rerank=false
    python -m rag "..." --llm fixture               # offline contract test
"""
from __future__ import annotations

import argparse
import json

from rag.config import load_config
from rag.llm_client import make_client
from rag.pipeline import Pipeline
from rag.schedule_tool import WASTE_TYPES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--lang", help="answer language code (en, ko, zh, uz, vi, ...)")
    parser.add_argument("--district")
    parser.add_argument("--province")
    parser.add_argument("--dong")
    parser.add_argument("--waste-type", choices=sorted(WASTE_TYPES))
    parser.add_argument("--baseline", action="store_true", help="Phase 1 configuration")
    parser.add_argument("--config", help="JSON file with PipelineConfig fields")
    parser.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE",
                        help="override one config field, e.g. --set retrieval=dense")
    parser.add_argument("--llm", default="ollama", choices=["ollama", "fixture"])
    parser.add_argument("--show-trace", action="store_true")
    args = parser.parse_args()

    cfg = load_config("baseline" if args.baseline else args.config, args.set)
    pipeline = Pipeline(cfg, make_client(args.llm, cfg.llm_model))
    trace = pipeline.run(args.question, args.lang, args.district, args.province,
                         args.dong, args.waste_type)
    print(json.dumps(trace if args.show_trace else trace["answer"],
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
