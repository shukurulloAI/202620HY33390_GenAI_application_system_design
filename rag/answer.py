"""
The answer dict the website shows and evaluation scores (PLAN.md §4.8).

Takes what the pipeline produced and fills the fields of the contract (rag/contract.py, which
checks every answer). Facts that decide what someone does (days, times, places, phones, dates)
come from the tool's rows, never the LLM. Every fixed sentence is in the user's language
(rag/texts.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rag.contract import CONTRACT_VERSION
from rag.gate import GateDecision
from rag.handoff import build_handoff, message
from rag.korean import fit_to_show
from rag.router import Route
from rag.schedule_tool import (
    WASTE_TYPE_EN,
    DayRef,
    ScheduleResult,
    ScheduleRow,
    day_checks,
    put_out_days,
    waste_types,
)
from rag.texts import text

if TYPE_CHECKING:
    from rag.pipeline import Request


def build_answer(draft: dict, evidence: list, *, request: Request, route: Route,
                 gate: GateDecision, schedule: ScheduleResult | None, rows: list[ScheduleRow],
                 day: DayRef | None, trace_id: str) -> dict:
    """`draft` is the item answer (or a fixed message), with the schedule text merged in.
    `rows` are the schedule rows the gate allowed to be shown."""
    by_number = {e.n: e for e in evidence}
    cited = [by_number[n] for n in draft.get("citations", []) if n in by_number]
    answer = {
        "contract_version": CONTRACT_VERSION,
        "status": draft.get("status"),
        "lang": request.lang,
        "bin": draft.get("bin", ""),
        "bin_en": draft.get("bin_en", ""),
        "how_to_prepare": draft.get("how_to_prepare", []),
        "answer_text": draft.get("answer_text", ""),
        "citations": [citation(e) for e in cited],
        "missing": draft.get("missing", ""),
        "schedule": None,
        "data_date": None,
        "office_phone": None,
        "clarify": clarify(gate.clarify, request.lang),
        "notes": source_notes(cited, request.lang),
        "handoff": None,
        "trace_id": trace_id,
    }
    if schedule is not None:
        add_schedule(answer, schedule, rows, gate, request, day)
    if answer["status"] == "ANSWER":
        say_what_failed(answer, gate, request.lang)
    if needs_handoff(answer["status"], gate):
        answer["handoff"] = handoff(request, route, gate, schedule)
        answer["office_phone"] = answer["office_phone"] or answer["handoff"]["phone"]
    return answer


def citation(evidence) -> dict:
    """What a source card needs: the reference, where it is, and the text the model read."""
    meta = evidence.metadata
    return {**evidence.to_citation(), "page": meta.get("page"),
            "year": meta.get("source_year"), "data_date": meta.get("data_date"),
            "text": evidence.text}


def clarify(question: dict | None, lang: str | None) -> dict | None:
    """The gate's question, written in the user's language."""
    if not question:
        return None
    return {"kind": question["kind"], "options": question["options"],
            "question": text(f"clarify_{question['kind']}", lang, **question["args"])}


def source_notes(cited: list, lang: str | None) -> list[str]:
    """Which rules the answer rests on, so the user can judge how far to trust it."""
    years = {e.metadata.get("source_year") for e in cited if e.kind == "item"}
    notes = []
    if years == {2018}:
        notes.append(text("note_2018", lang))
    if 2026 in years:
        notes.append(text("note_2026", lang))
    return notes


def say_what_failed(answer: dict, gate: GateDecision, lang: str | None) -> None:
    """An ANSWER can cover one part of a two-part question. Say so in the text the user
    reads, not only in `missing`."""
    if gate.item == "abstain":
        answer["answer_text"] = f"{text('ITEM_FAILED', lang)}\n\n{answer['answer_text']}"
    if gate.schedule == "abstain":
        key = "SCHEDULE_VARIES" if gate.schedule_varies else "SCHEDULE_FAILED"
        answer["answer_text"] = f"{answer['answer_text'].rstrip()}\n\n{message(key, lang)}"


def add_schedule(answer: dict, schedule: ScheduleResult, rows: list[ScheduleRow],
                 gate: GateDecision, request: Request, day: DayRef | None) -> None:
    types = waste_types(request.waste_type)
    flat = schedule_fields(rows, types)
    answer["data_date"] = flat.pop("data_date")
    answer["office_phone"] = flat.pop("office_phone")
    answer["schedule"] = {"status": schedule.status, "message": schedule.message,
                          "options": schedule.options,
                          "zones": [zone_detail(r, types, day) for r in rows], **flat}
    if any(r.is_stale() for r in rows):
        answer["notes"].append(text("note_stale", request.lang, date=rows[0].data_date))
    if schedule.note and rows:
        answer["notes"].append(text(schedule.note["key"], request.lang,
                                    **schedule.note["args"]))
    if answer["status"] == "ANSWER" and gate.schedule == "abstain":   # say what was left out
        answer["missing"] = answer["missing"] or schedule.message


def zone_detail(row: ScheduleRow, types: list[str], day: DayRef | None) -> dict:
    return {
        "province": row.province, "district": row.district, "zone": row.zone,
        "areas": row.area_names, "place": f"{row.place_type} / {row.place}",
        "by_type": {t: {"days": row.rules[t].days_en(),
                        "start": row.rules[t].start, "end": row.rules[t].end,
                        "next_dates": put_out_days(row, t)}
                    for t in types if row.rules[t].days},
        "day_check": day_checks(row, types, day) if day else [],
        "no_collection": row.no_collection_days,
        "office": row.office, "phone": row.phone,
        "data_date": row.data_date, "stale": row.is_stale(),
        "row_id": row.row_id,
    }


def schedule_fields(rows: list[ScheduleRow], types: list[str]) -> dict:
    """The flat fields of the answer contract (PLAN.md §4.8), from the tool's rows. With
    several zones or waste types each value gets a label, so none of them is dropped;
    `zones` in the answer keeps the full detail. Oldest date: it decides how far to trust."""
    days, times = [], []
    for row in rows:
        for t in types:
            rule = row.rules[t]
            if not rule.days:
                continue
            label = " ".join(x for x in (row.zone if len(rows) > 1 else "",
                                         WASTE_TYPE_EN[t] if len(types) > 1 else "") if x)
            prefix = f"{label}: " if label else ""
            days.append(prefix + rule.days_en())
            if rule.start and rule.end:
                times.append(f"{prefix}{rule.start}-{rule.end}")
    return {"days": _join(days), "time": _join(times),
            "place": _join(f"{r.place_type} / {r.place}" for r in rows),
            "data_date": min((r.data_date for r in rows if r.data_date), default=None),
            "office_phone": _join(r.phone for r in rows)}


def _join(values) -> str | None:
    """Distinct non-empty values in order, or None when there are none."""
    return "; ".join(dict.fromkeys(v for v in values if v)) or None


def needs_handoff(status: str, gate: GateDecision) -> bool:
    """When it could not answer, or answered only part of the question."""
    return status == "INSUFFICIENT_CONTEXT" or (
        status == "ANSWER" and "abstain" in (gate.item, gate.schedule))


def handoff(request: Request, route: Route, gate: GateDecision,
            schedule: ScheduleResult | None) -> dict:
    checked = []
    if gate.item != "skip":
        checked.append(text("checked_guides", request.lang))
    if schedule is not None:
        place = " ".join(p for p in (request.district, request.dong) if p)
        checked.append(text("checked_district", request.lang, place=place))
    return build_handoff(lang=request.lang,
        item_ko=route.item_ko if fit_to_show(route.item_ko) else "",
        item_asked=route.item if route.checks.get("item_in_question") else "",
        waste_type=request.waste_type, district=request.district, dong=request.dong,
        schedule=schedule, asks_schedule=gate.schedule != "skip", checked=checked)
