"""Runs the planner for one web request and returns a result the page can show.

main.py prints to the terminal; this module follows the same steps as main.py
(load the student, find eligible courses, ask the crew for a plan, let Python pick
and check a valid subset, allow one correction attempt) but returns a dictionary so
frontend/server.py can send it back as JSON:

    {"plan": {courses, assumptions},
     "validation": {passed, issues, limitations, planned_credit_hours, selection_notes}}

main.py is not changed. Problems are raised as PlannerError with an HTTP status code
and a message that is safe to show to the person using the page.
"""
import json

from course_counts import course_count_issues
from models import DraftPlan
from planning_check import eligible_catalog, select_valid_subset
from student_inputs import load_student
from tools.course_tools import course_catalog

MAX_ATTEMPTS = 2  # the first try plus one correction attempt, like main.py

# main.py leaves unresolved_questions out of its printed plan, so the page does too.
PLAN_FIELDS_HIDDEN = {"unresolved_questions"}


class PlannerError(Exception):
    """An error with an HTTP status code and a message meant for the user."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _load_profile(student_id: str) -> dict:
    try:
        return load_student(student_id)
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise PlannerError(status, str(exc)) from exc
    except Exception as exc:  # missing CSV, unreadable file, ...
        raise PlannerError(500, f"Could not load the student data: {exc}") from exc


def _unit(profile: dict, field: str, default: int, override: int | None) -> int:
    if override is not None:
        return override
    text = str(profile.get(field, "")).strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError as exc:
        raise PlannerError(400, f"Student field {field!r} must be a whole number; got {text!r}.") from exc


def _default_crew_factory():
    try:
        from workflow import make_planning_crew
    except ModuleNotFoundError as exc:
        missing = exc.name or "a required package"
        raise PlannerError(
            500,
            f"The planner cannot start because {missing!r} is not installed. "
            "Run: pip install -r requirements.txt",
        ) from exc
    except Exception as exc:
        raise PlannerError(500, f"The planner could not be initialized: {type(exc).__name__}: {exc}") from exc
    return make_planning_crew


def run_planner(
        student_id: str,
        min_units: int | None = None,
        max_units: int | None = None,
        dept_course_count: int | None = None,
        crew_factory=None,
) -> dict:
    """Create and check a plan for one student.

    min_units / max_units replace the unit range in the student's profile when given.
    crew_factory is only passed in by tests; normally workflow.make_planning_crew is used.
    """
    profile = _load_profile(student_id)
    completed = profile.get("completed_courses", "")

    min_total = _unit(profile, "min_unit_load", 0, min_units)
    max_total = _unit(profile, "max_unit_load", 18, max_units)
    if not 0 <= min_total <= max_total:
        raise PlannerError(
            400,
            f"Unit range must satisfy 0 <= minimum <= maximum (got {min_total} to {max_total}).",
        )

    try:
        candidates = eligible_catalog(course_catalog, completed)
    except Exception as exc:
        raise PlannerError(500, f"Could not read the course catalog: {type(exc).__name__}: {exc}") from exc
    if not candidates:
        raise PlannerError(500, "No supported candidates; catalog/eligibility needs review.")

    make_crew = crew_factory or _default_crew_factory()

    inputs = {
        "intended_semester": profile.get("intended_semester", "Not supplied"),
        "major": profile.get("major", "Not supplied"),
        "completed_courses": completed,
        "preferences": profile.get("preferences", "None supplied"),
        "required_courses": profile.get("remaining_required_courses", ""),
        "remaining_choice_groups": profile.get("remaining_choice_groups", ""),
        "min_unit_load": min_total,
        "max_unit_load": max_total,
        "course_candidates": "\n".join(
            f"{code} | {row['Name']} | {row['Credit Hours']} | "
            f"{row['Requirement Group']} | Prerequisites: {row['Prerequisites']}"
            for code, row in candidates.items()
        ),
        "revision_feedback": "First attempt; no previous selection.",
    }

    plan = report = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = make_crew().kickoff(inputs=inputs)
            if result.pydantic is None:
                raise ValueError("No structured DraftPlan returned.")
            draft = DraftPlan.model_validate(result.pydantic.model_dump())
            plan, report = select_valid_subset(
                draft, candidates, completed, min_total, max_total,
                required_courses=inputs["required_courses"],
            )
        except PlannerError:
            raise
        except Exception as exc:
            if attempt == MAX_ATTEMPTS:
                raise PlannerError(
                    502,
                    f"Planning failed: {type(exc).__name__}: {exc}. "
                    "Check that Ollama is running and the llama3.2 model is installed.",
                ) from exc
            inputs["revision_feedback"] = (
                "Previous attempt failed. Return the requested DraftPlan JSON with courses "
                "containing only code and reason, plus assumptions and unresolved_questions."
            )
            continue

        if report["passed"]:
            break

        inputs["revision_feedback"] = json.dumps({
            "previous_codes": [course.code for course in draft.courses],
            "issues_to_fix": report["issues"],
        })

    # Like main.py, compare with the department's count only when one was given.
    if dept_course_count is not None:
        try:
            report["issues"].extend(course_count_issues(
                planned_count=len(plan.courses),
                min_units=min_total,
                max_units=max_total,
                dept_target=dept_course_count,
            ))
        except ValueError as exc:
            raise PlannerError(400, str(exc)) from exc
        report["passed"] = not report["issues"]

    report.setdefault("limitations", [])
    report.setdefault("selection_notes", [])
    return {"plan": plan.model_dump(exclude=PLAN_FIELDS_HIDDEN), "validation": report}
