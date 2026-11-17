import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import CourseSelection, DraftPlan
from planner_service import PlannerError, run_planner

STUDENT = "SYNTHETIC_001"
GOOD = ["CSC 60", "CSC 130", "CSC 131", "PHIL 103"]  # 3 units each = 12


def draft(*codes):
    return DraftPlan(
        courses=[CourseSelection(code=c, reason="test reason") for c in codes],
        assumptions=["Full time"],
        unresolved_questions=["Confirm offerings"],
    )


class FakeCrew:
    """Hands out one prepared result (or error) per attempt, like the real crew would."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.inputs = []

    def factory(self):
        return self

    def kickoff(self, inputs):
        self.inputs.append(dict(inputs))
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(pydantic=outcome)


def run(crew, **kwargs):
    return run_planner(STUDENT, crew_factory=crew.factory, **kwargs)


def test_good_plan_returns_plan_and_passing_validation():
    result = run(FakeCrew(draft(*GOOD)))
    plan, report = result["plan"], result["validation"]
    assert [c["code"] for c in plan["courses"]] == GOOD
    assert plan["courses"][0]["name"] == "Introduction to Systems Programming in UNIX"  # name comes from the CSV
    assert plan["courses"][0]["credit_hours"] == 3
    assert report["passed"] is True and report["planned_credit_hours"] == 12
    assert report["issues"] == [] and report["limitations"]


def test_unresolved_questions_are_not_sent_to_the_page():
    assert "unresolved_questions" not in run(FakeCrew(draft(*GOOD)))["plan"]


def test_unit_overrides_reach_the_crew():
    crew = FakeCrew(draft(*GOOD))
    run(crew, min_units=9, max_units=15)
    assert (crew.inputs[0]["min_unit_load"], crew.inputs[0]["max_unit_load"]) == (9, 15)


def test_profile_units_used_when_not_overridden():
    crew = FakeCrew(draft(*GOOD))
    run(crew)
    assert (crew.inputs[0]["min_unit_load"], crew.inputs[0]["max_unit_load"]) == (12, 18)


def test_unknown_student_is_404():
    with pytest.raises(PlannerError) as err:
        run_planner("NOPE", crew_factory=FakeCrew(draft(*GOOD)).factory)
    assert err.value.status == 404 and "not found" in err.value.message


def test_min_above_max_is_400():
    with pytest.raises(PlannerError) as err:
        run(FakeCrew(draft(*GOOD)), min_units=15, max_units=12)
    assert err.value.status == 400


def test_invented_course_is_dropped_by_python():
    result = run(FakeCrew(draft("CSC 999", *GOOD)))
    assert "CSC 999" not in [c["code"] for c in result["plan"]["courses"]]
    assert result["validation"]["passed"] is True
    assert any("CSC 999" in note for note in result["validation"]["selection_notes"])


def test_too_few_courses_is_reported_after_a_correction_attempt():
    crew = FakeCrew(draft("CSC 60"))
    result = run(crew)
    assert len(crew.inputs) == 2  # first try plus one correction attempt
    assert "issues_to_fix" in crew.inputs[1]["revision_feedback"]
    assert result["validation"]["passed"] is False and result["validation"]["issues"]


def test_second_attempt_can_rescue_a_failed_first_attempt():
    crew = FakeCrew(RuntimeError("model hiccup"), draft(*GOOD))
    result = run(crew)
    assert len(crew.inputs) == 2 and result["validation"]["passed"] is True
    assert "Previous attempt failed" in crew.inputs[1]["revision_feedback"]


def test_failure_on_both_attempts_is_502_with_ollama_hint():
    with pytest.raises(PlannerError) as err:
        run(FakeCrew(ConnectionError("refused")))
    assert err.value.status == 502 and "Ollama" in err.value.message


def test_unstructured_result_twice_is_502():
    with pytest.raises(PlannerError) as err:
        run(FakeCrew(None))
    assert err.value.status == 502


def test_department_count_must_match_when_given():
    result = run(FakeCrew(draft(*GOOD)), dept_course_count=5)
    assert result["validation"]["passed"] is False
    assert any("department-selected count is 5" in i for i in result["validation"]["issues"])
    assert run(FakeCrew(draft(*GOOD)), dept_course_count=4)["validation"]["passed"] is True


def test_bad_department_count_is_400():
    with pytest.raises(PlannerError) as err:
        run(FakeCrew(draft(*GOOD)), dept_course_count=0)
    assert err.value.status == 400
