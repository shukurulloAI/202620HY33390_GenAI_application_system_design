"""
Stage 1 acceptance check (PLAN.md §10.4): every developer probe, run live through the full
system, returns an answer that fits the contract (rag/contract.py).

    python -m experiments.check_contract              # 49 probes, ~15 min, needs Ollama
    python -m experiments.check_contract --cases eval/cases/dev.jsonl

Prints the statuses seen and every contract problem; exits 1 if there is any.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from eval.cases import case_id, load_cases
from rag import paths
from rag.contract import problems
from rag.pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=Path, nargs="*",
                        default=[paths.PROBES, paths.SCHEDULE_PROBES])
    args = parser.parse_args()
    cases = [c for path in args.cases for c in load_cases(path)]
    pipeline = Pipeline(write_traces=False)
    statuses, failures = Counter(), {}
    for i, case in enumerate(cases, 1):
        answer = pipeline.run_case(case)["answer"]
        statuses[answer["status"]] += 1
        found = problems(answer)
        if found:
            failures[case_id(case)] = found
        print(f"\r{i}/{len(cases)} {dict(statuses)} problems: {len(failures)}", end="",
              flush=True)
    print()
    for cid, found in failures.items():
        print(cid, found)
    print(f"{len(cases)} answers, statuses {dict(statuses)}, {len(failures)} break the contract")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
