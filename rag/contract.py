"""
The answer contract (PLAN.md §4.8): what `rag.service.ask()` returns to the website and what
evaluation scores.

Typed models instead of a loose dict, for two reasons:
    - every answer is checked against them before it leaves the pipeline (`check()`), so a
      field cannot be dropped, renamed or mistyped without a failing test
    - `docs/answer_schema.json` is generated from them (`python -m rag.contract`), so the
      website has one written reference; tests/test_contract.py fails if it is out of date

Beyond types, `Answer` checks the rules between fields that the website relies on, e.g. a
CLARIFY answer always has a question, an abstention never names a bin, and a handoff is
always there when the assistant could not answer.

Changing a field means bumping CONTRACT_VERSION and updating the website (PLAN.md §10.2).
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from rag import paths
from rag.bins import BINS

CONTRACT_VERSION = "1.0"
SCHEMA_FILE = paths.ROOT / "docs" / "answer_schema.json"

Status = Literal["ANSWER", "CLARIFY", "INSUFFICIENT_CONTEXT", "OUT_OF_SCOPE"]
WasteType = Literal["general", "food", "recycling", "bulky"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(_Strict):
    """One source the answer cites: a guide chunk (kind=item) or a district row (schedule)."""
    n: int = Field(description="The number used in answer_text, e.g. [1]")
    kind: Literal["item", "schedule"]
    ref: str = Field(description="chunk_id (item) or 관리번호 (schedule)")
    source: str = Field(description="Readable source, e.g. '환경부 ... (2018) p.28'")
    page: int | None = Field(None, description="Guide page, for items")
    year: int | None = Field(None, description="Year of the guide (2018 or 2026), for items")
    data_date: str | None = Field(None, description="Date of the district row, for schedules")
    text: str = Field(description="The evidence text the model read, for the source card")


class TypeRule(_Strict):
    days: str = Field(description="English day list, e.g. 'Sun, Tue, Thu'")
    start: str | None
    end: str | None
    next_dates: list[str] = Field(description="ISO dates in the next 7 days (KST)")


class DayCheck(_Strict):
    waste_type: WasteType
    date: str
    weekday: str
    allowed: bool
    start: str | None
    end: str | None
    text: str


class Zone(_Strict):
    """One collection zone (one row of the district table), in full."""
    province: str
    district: str
    zone: str
    areas: list[str]
    place: str
    by_type: dict[WasteType, TypeRule]
    day_check: list[DayCheck]
    no_collection: str = Field(description="미수거일 as the source writes it (Korean)")
    office: str
    phone: str
    data_date: str | None
    stale: bool = Field(description="Data more than a year old")
    row_id: str = Field(description="관리번호")


class Schedule(_Strict):
    status: Literal["OK", "CLARIFY", "NO_DATA"]
    message: str = Field(description="The tool's own note, English (for debugging)")
    options: list[str]
    zones: list[Zone] = Field(description="Rows shown to the user (at most 4)")
    days: str | None
    time: str | None
    place: str | None


class Clarify(_Strict):
    kind: Literal["district", "province", "zones", "names"]
    question: str = Field(description="In the user's language")
    options: list[str] = Field(description="Choices to offer, at most 30 (Korean names)")


class Handoff(_Strict):
    office: str | None
    phone: str | None
    contact: str = Field(description="Who to call or visit, in the user's language")
    korean_sentence: str = Field(description="Always Korean: to show at the office")
    checked: list[str] = Field(description="What the assistant already checked")


class Answer(_Strict):
    contract_version: Literal["1.0"] = CONTRACT_VERSION
    status: Status
    lang: str | None
    bin: str = Field(description="Canonical bin (rag/bins.py) or ''")
    bin_en: str
    how_to_prepare: list[str]
    answer_text: str = Field(description="In the user's language; several lines; [n] cites")
    citations: list[Citation]
    missing: str = Field(description="What could not be answered (diagnostic, English)")
    schedule: Schedule | None
    data_date: str | None
    office_phone: str | None
    clarify: Clarify | None
    notes: list[str] = Field(description="Source-year and data-age warnings, user's language")
    handoff: Handoff | None
    trace_id: str

    @model_validator(mode="after")
    def _rules_between_fields(self) -> Answer:
        problems = []
        if self.bin and self.bin not in BINS:
            problems.append(f"unknown bin {self.bin!r}")
        if self.status != "ANSWER" and self.bin:
            problems.append(f"{self.status} answer names a bin")
        if self.status == "CLARIFY" and not self.clarify:
            problems.append("CLARIFY without a question")
        if self.status == "INSUFFICIENT_CONTEXT" and not self.handoff:
            problems.append("abstention without a handoff")
        if self.status == "ANSWER" and not self.answer_text.strip():
            problems.append("ANSWER with no text")
        if self.status == "ANSWER" and not self.citations:
            problems.append("ANSWER cites nothing")
        numbers = [c.n for c in self.citations]
        if len(numbers) != len(set(numbers)):
            problems.append(f"citation numbers repeat: {numbers}")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class ContractError(ValueError):
    """An answer broke the contract: a bug in the pipeline, not in the question."""


def problems(answer: dict) -> list[str]:
    """Every way `answer` breaks the contract; [] if it fits."""
    try:
        Answer.model_validate(answer)
    except ValidationError as exc:
        return [f"{'.'.join(map(str, e['loc'])) or 'answer'}: {e['msg']}" for e in exc.errors()]
    return []


def check(answer: dict) -> dict:
    """Raise ContractError unless `answer` fits the contract; returns it unchanged."""
    found = problems(answer)
    if found:
        raise ContractError("; ".join(found))
    return answer


def json_schema() -> dict:
    schema = Answer.model_json_schema()
    schema["$id"] = f"answer-contract-v{CONTRACT_VERSION}"
    return schema


def write_schema() -> None:
    SCHEMA_FILE.write_text(json.dumps(json_schema(), ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    write_schema()
    print(f"-> {paths.relative(SCHEMA_FILE)}")
