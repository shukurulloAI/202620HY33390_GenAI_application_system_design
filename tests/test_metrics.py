"""Counts over traces."""
from __future__ import annotations

from eval.metrics import schedule_summary
from rag.schedule_tool import default_table


def test_schedule_summary_counts():
    table = default_table()
    first_seen = {}
    for row in table.rows:                             # two districts, one food schedule
        rule = row.rules["food"]
        twin = first_seen.setdefault((tuple(rule.days), rule.start, rule.end), row)
        if twin.district != row.district:
            one, same_days = twin.row_id, row.row_id
            break

    def trace(cid, status, shown):
        return {"case_id": cid, "answer": {"status": status, "schedule": {
            "zones": [{"row_id": i} for i in shown]}}}
    cases = [{"case_id": "a", "waste_type": "food", "expected_behavior": "answer",
              "expected_schedule": {"row_ids": [one]}},
             {"case_id": "b", "waste_type": "food", "expected_behavior": "abstain",
              "expected_schedule": {"row_ids": []}}]
    good = schedule_summary([trace("a", "ANSWER", [one]),
                             trace("b", "INSUFFICIENT_CONTEXT", [])], cases, table)
    assert good == {"cases": 2, "behaviour_ok": 2, "wrong_place": 0, "answerable": 1, "empty": 0,
                    "row_found": 1, "top_row": 1, "only_correct_rows": 1, "day_time_match": 1}
    # Another district's row with the same days: the day/time still matches, the place does not.
    lucky = schedule_summary([trace("a", "ANSWER", [same_days]),
                              trace("b", "ANSWER", [one])], cases, table)
    assert (lucky["day_time_match"], lucky["row_found"], lucky["wrong_place"]) == (1, 0, 2)
    # Rows of a refused answer are not shown to the user.
    refused = schedule_summary([trace("a", "INSUFFICIENT_CONTEXT", [one])], cases[:1], table)
    assert (refused["empty"], refused["row_found"]) == (1, 0)
