"""The package layering: rag/ is the core, and nothing in it imports from above."""
from __future__ import annotations

import ast

from rag import paths

ABOVE_RAG = {"app", "preprocess", "ingest", "eval", "experiments", "tests"}


def imported_packages(source: str) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_rag_imports_nothing_from_the_layers_above_it():
    offenders = {path.name: sorted(imported_packages(path.read_text(encoding="utf-8")) & ABOVE_RAG)
                 for path in (paths.ROOT / "rag").glob("*.py")}
    assert not any(offenders.values()), offenders
