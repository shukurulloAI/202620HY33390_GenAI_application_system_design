"""
Evidence gate (PLAN.md §4.6; Lessons 4-7): decide, before generation, whether there is
enough evidence to answer each part of the question.

    item part      top rerank score >= tau          -> answer, else abstain
                   (tau = None or no reranker       -> gate off: always answer)
    schedule part  tool OK (<= MAX_ZONES zones)     -> answer
                   no district given                -> clarify ("which district?")
                   tool CLARIFY (name in many cities) or too many zones -> clarify
                   tool NO_DATA                     -> abstain
                   neighbourhood with more than MAX_ZONES rows on different days:
                       several names to pick from   -> clarify
                       one name, many collection points -> abstain (office hand-off)
                       same days in every row       -> answer
    out_of_scope                                    -> refuse, explain the scope

Overall: ANSWER if any part can be answered (the generator only sees the parts that
passed), else CLARIFY if any part needs it, else INSUFFICIENT_CONTEXT, which skips the
LLM entirely. A wrong bin is costlier than an abstention, so tau is chosen on the dev
set to keep false answers low (E5); the default in config.py is provisional.

Also records (no effect on the decision) whether the router's Korean item name
appears in the selected evidence (`item_match`), and the source years of the evidence
for the conflict policy (§4.6, E8).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

MAX_ZONES = 4          # more zones than this and no neighbourhood -> ask for it


@dataclass
class GateDecision:
    status: str                    # ANSWER | CLARIFY | INSUFFICIENT_CONTEXT | OUT_OF_SCOPE
    item: str                      # answer | abstain | skip
    schedule: str                  # answer | abstain | clarify | skip
    reasons: list = field(default_factory=list)
    top_rerank_score: float | None = None
    tau: float | None = None
    item_match: bool | None = None
    source_years: list = field(default_factory=list)
    clarify: dict | None = None    # {"question": ..., "options": [...]}
    schedule_varies: bool = False  # days differ between collection points, no name separates them

    def to_trace(self) -> dict:
        return asdict(self)


def decide(intent: str, selected: list, schedule, district: str | None,
           dong: str | None, tau: float | None, item_ko: str = "") -> GateDecision:
    if intent == "out_of_scope":
        return GateDecision("OUT_OF_SCOPE", "skip", "skip",
                            ["router: question is outside household waste in Korea"])
    reasons = []
    needs_item = intent in ("item", "both", "unknown")
    needs_schedule = intent in ("schedule", "both") or (intent == "unknown" and bool(district))

    # ---- item part
    top = max((c.rerank_score for c in selected if c.rerank_score is not None), default=None)
    if not needs_item:
        item = "skip"
    elif not selected:
        item = "abstain"
        reasons.append("no item evidence retrieved")
    elif tau is None or top is None:
        item = "answer"
        reasons.append("gate off (no threshold or no reranker)")
    elif top >= tau:
        item = "answer"
        reasons.append(f"top rerank score {top:.3f} >= tau {tau}")
    else:
        item = "abstain"
        reasons.append(f"top rerank score {top:.3f} < tau {tau}")

    item_match = None
    if needs_item and item_ko and selected:
        key = item_ko.replace(" ", "")
        item_match = any(key in (c.metadata.get("item") or "").replace(" ", "")
                         or key in c.text.replace(" ", "") for c in selected)

    # ---- schedule part
    clarify, varies = None, False
    if not needs_schedule:
        sched = "skip"
    elif not district:
        sched = "clarify"
        clarify = {"question": "Which district (구) and neighbourhood (동) do you live in? "
                               "Collection days depend on the area.", "options": []}
        reasons.append("schedule asked but no district given")
    elif schedule is None or schedule.status == "NO_DATA":
        sched = "abstain"
        reasons.append(f"schedule tool: {schedule.message if schedule else 'not run'}")
    elif schedule.status == "CLARIFY":
        sched = "clarify"
        clarify = {"question": f"{schedule.message}. Which one do you mean?",
                   "options": schedule.options}
        reasons.append(f"schedule tool: {schedule.message}")
    elif len(schedule.rows) > MAX_ZONES and not (dong and schedule.matched_on == "area"):
        sched = "clarify"
        areas = sorted({a for r in schedule.rows for a in r.area_names})
        clarify = {"question": f"{schedule.rows[0].district} has {len(schedule.rows)} "
                               "collection zones. Which neighbourhood (동) do you live in?",
                   "options": areas[:30]}
        reasons.append(f"{len(schedule.rows)} zones and no neighbourhood")
    elif len(schedule.rows) > MAX_ZONES and schedule.schedules_differ():
        # Only MAX_ZONES rows reach the answer, so it would state a day that many rows
        # here do not have. E.g. 고흥군 도덕면: 287 collection points, Monday to Friday.
        if schedule.options:
            sched = "clarify"
            clarify = {"question": f"Which of these do you live in: {dong}?",
                       "options": schedule.options[:30]}
            reasons.append(schedule.message)
        else:
            sched = "abstain"
            varies = True
            reasons.append(f"{len(schedule.rows)} collection points in '{dong}' "
                           "with different days")
    else:
        sched = "answer"

    parts = {item, sched}
    status = ("ANSWER" if "answer" in parts else
              "CLARIFY" if "clarify" in parts else "INSUFFICIENT_CONTEXT")
    years = sorted({c.metadata.get("source_year") for c in selected
                    if c.metadata.get("source_year")}) if item == "answer" else []
    return GateDecision(status, item, sched, reasons, top, tau, item_match, years, clarify,
                        varies)
